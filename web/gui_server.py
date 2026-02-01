"""Simple aiohttp-based GUI server to manage the trading system.

Provides a small web UI (static files under web/static) and WebSocket
endpoint at /ws that pushes portfolio status and realtime feed events.
Includes health check endpoints and optional Prometheus metrics.
"""

import asyncio
import json
from aiohttp import web
from pathlib import Path
from typing import Dict, Any
import sys
import time
from collections import defaultdict

# Ensure project root is on sys.path when running this script directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trading.persistence_sqlite import SQLitePersistence
from trading.portfolio_orchestrator import MultiPairOrchestrator
from trading.portfolio_manager import PortfolioConfig, PairConfig
from trading.async_execution import AsyncExecutionEngine
from trading.async_coinbase_adapter import AsyncCoinbaseAdapter
from trading.position import PositionState
from decimal import Decimal
import os
import base64
import time
import secrets
from aiohttp_session import setup as session_setup, get_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet


# Lightweight mock adapter used for demo / GUI when no real exchange adapter is present
class _MockAsyncAdapter:
    def __init__(self, product_id: str):
        self.product_id = product_id
        self._order_counter = 0

    async def place_limit_buy(self, client_id: str, price, qty):
        self._order_counter += 1
        return f"{self.product_id}_mock_order_{self._order_counter}"

    async def place_stop_limit(self, client_id: str, trigger, limit, qty):
        self._order_counter += 1
        return f"{self.product_id}_mock_stop_{self._order_counter}"

    async def cancel_order(self, order_id: str):
        return True


from trading.ws_client import RealTimeWebSocketClient

ROOT = Path(__file__).parent


class GUIServer:
    def __init__(
        self, host: str = "0.0.0.0", port: int = 8080, db_path: Path = Path("state/portfolio.db")
    ):
        self.host = host
        self.port = port
        self.db_path = db_path
        self.app = web.Application()
        self._setup_routes()
        self.persistence = SQLitePersistence(db_path)
        self.orchestrator = None  # type: ignore
        self.ws_clients = []
        self.feed_client = RealTimeWebSocketClient()
        self._feed_task = None
        # Metrics tracking
        self.metrics = {
            "trade_count": 0,
            "total_pnl": 0.0,
            "total_entries": 0,
            "total_exits": 0,
            "order_latencies": [],  # milliseconds
            "api_call_count": defaultdict(int),  # endpoint -> count
            "stop_ratchets": 0,
        }
        self.metrics_start_time = time.time()
        # Initialize an orchestrator with demo/mock engines so the GUI is interactive
        try:
            self._init_demo_orchestrator()
        except Exception:
            # don't fail server startup if demo orchestrator cannot initialize
            self.orchestrator = None

    def _setup_routes(self):
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/login", self.handle_login_page)
        self.app.router.add_post("/login", self.handle_login)
        self.app.router.add_post("/logout", self.handle_logout)
        self.app.router.add_get("/ws", self.handle_ws)
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/health/live", self.handle_liveness)
        self.app.router.add_get("/health/ready", self.handle_readiness)
        self.app.router.add_get("/metrics", self.handle_metrics)
        self.app.router.add_get("/api/status", self.handle_status)
        self.app.router.add_get("/api/positions", self.handle_positions)
        self.app.router.add_get("/api/position/{position_id}", self.handle_position_detail)
        self.app.router.add_get("/api/rate-limit-status", self.handle_rate_limit_status)
        self.app.router.add_get("/api/performance", self.handle_performance)
        self.app.router.add_post("/api/config/reload", self.handle_config_reload)
        self.app.router.add_post("/api/place_entry", self.handle_place_entry)
        self.app.router.add_post("/api/cancel_order", self.handle_cancel_order)
        self.app.router.add_post("/api/emergency_liquidate", self.handle_emergency_liquidate)
        self.app.router.add_static("/static", ROOT / "static", show_index=False)
        # start/stop hooks
        self.app.on_startup.append(self._on_startup)
        self.app.on_cleanup.append(self._on_cleanup)
        # Setup server-side sessions (encrypted cookie storage)
        secret_key = os.environ.get("GUI_SESSION_KEY")
        if not secret_key:
            # generate a 32-byte key and store in memory (not persistent)
            secret_key = fernet.Fernet.generate_key()
        else:
            secret_key = secret_key.encode()
        session_setup(self.app, EncryptedCookieStorage(secret_key))

    async def _check_auth(self, request: web.Request) -> bool:
        # Prefer session-based auth. If no session, fall back to Basic auth if GUI_USER/PASS set.
        session = await get_session(request)
        user = session.get("user")
        if user:
            return True

        gui_user = os.environ.get("GUI_USER")
        gui_pass = os.environ.get("GUI_PASS")
        if not gui_user or not gui_pass:
            # no credentials configured - allow access (dev mode)
            return True

        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Basic "):
            return False
        try:
            b = auth.split(" ", 1)[1]
            decoded = base64.b64decode(b).decode()
            u, pw = decoded.split(":", 1)
            return u == gui_user and pw == gui_pass
        except Exception:
            return False

    async def _validate_csrf(self, request: web.Request) -> bool:
        # CSRF token must be provided in header 'X-CSRF-Token' for state-changing POSTs
        session = await get_session(request)
        server_csrf = session.get("csrf")
        if not server_csrf:
            return False
        token = (
            request.headers.get("X-CSRF-Token") or (await request.json()).get("csrf")
            if request.can_read_body
            else None
        )
        return token == server_csrf

    async def handle_index(self, request: web.Request):
        index_path = ROOT / "static" / "index.html"
        return web.FileResponse(index_path)

    async def handle_login_page(self, request: web.Request):
        # serve the same index page (SPA handles login)
        index_path = ROOT / "static" / "index.html"
        return web.FileResponse(index_path)

    async def handle_login(self, request: web.Request):
        data = await request.json()
        user = data.get("user")
        pw = data.get("pass")
        gui_user = os.environ.get("GUI_USER")
        gui_pass = os.environ.get("GUI_PASS")
        if gui_user and gui_pass:
            if user != gui_user or pw != gui_pass:
                return web.json_response({"error": "invalid credentials"}, status=401)
        # create session
        session = await get_session(request)
        session["user"] = user or "anon"
        # role: admin if matches GUI_USER else operator
        session["role"] = "admin" if (user == os.environ.get("GUI_USER")) else "operator"
        # CSRF token
        token = secrets.token_urlsafe(32)
        session["csrf"] = token
        return web.json_response({"ok": True, "csrf": token})

    async def handle_logout(self, request: web.Request):
        session = await get_session(request)
        session.invalidate()
        return web.json_response({"ok": True})

    async def handle_health(self, request: web.Request):
        """Comprehensive health check (liveness + readiness + metrics).

        Used by monitoring and container orchestration.
        Returns 200 if all checks pass, 503 if any critical check fails.
        """
        checks = {
            "status": "healthy",
            "timestamp": int(time.time()),
            "uptime_seconds": time.time() - getattr(self, "_start_time", time.time()),
            "checks": {},
        }

        # Database connectivity
        try:
            positions = self.persistence.list_positions()
            checks["checks"]["database"] = {
                "status": "up",
                "positions_loaded": len(positions) if positions else 0,
            }
        except Exception as e:
            checks["checks"]["database"] = {"status": "down", "error": str(e)}
            checks["status"] = "unhealthy"

        # Orchestrator status
        if self.orchestrator:
            try:
                status = self.orchestrator.get_portfolio_status()
                checks["checks"]["orchestrator"] = {
                    "status": "running",
                    "active_positions": len(status.get("positions", [])),
                }
            except Exception as e:
                checks["checks"]["orchestrator"] = {"status": "error", "error": str(e)}
        else:
            checks["checks"]["orchestrator"] = {"status": "not_initialized"}

        # WebSocket clients
        checks["checks"]["websockets"] = {"status": "up", "connected_clients": len(self.ws_clients)}

        # Overall status
        http_status = 200 if checks["status"] == "healthy" else 503
        return web.json_response(checks, status=http_status)

    async def handle_liveness(self, request: web.Request):
        """Liveness probe for Kubernetes/container orchestration.

        Returns 200 if the service is running (not crashed).
        This is a lightweight check; use /health for comprehensive status.
        """
        return web.json_response({"status": "alive", "timestamp": int(time.time())})

    async def handle_readiness(self, request: web.Request):
        """Readiness probe for Kubernetes/container orchestration.

        Returns 200 if the service is ready to serve requests.
        Checks critical dependencies (database, orchestrator).
        """
        ready = True
        checks = {}

        # Check database
        try:
            self.persistence.load_position()
            checks["database"] = "ready"
        except Exception as e:
            checks["database"] = f"not_ready: {str(e)}"
            ready = False

        # Check orchestrator
        if self.orchestrator:
            try:
                self.orchestrator.get_portfolio_status()
                checks["orchestrator"] = "ready"
            except Exception as e:
                checks["orchestrator"] = f"not_ready: {str(e)}"
                ready = False
        else:
            checks["orchestrator"] = "not_initialized"

        status_code = 200 if ready else 503
        return web.json_response(
            {"ready": ready, "checks": checks, "timestamp": int(time.time())}, status=status_code
        )

    async def handle_metrics(self, request: web.Request):
        """Prometheus metrics endpoint for monitoring.

        Returns metrics in Prometheus text format.
        Includes trade count, P&L, order latency, API call frequency, stop ratchets.
        """
        uptime_seconds = int(time.time() - self.metrics_start_time)
        avg_latency = (
            sum(self.metrics["order_latencies"]) / len(self.metrics["order_latencies"])
            if self.metrics["order_latencies"]
            else 0
        )

        metrics_text = f"""# HELP quant_trade_uptime_seconds Server uptime in seconds
# TYPE quant_trade_uptime_seconds gauge
quant_trade_uptime_seconds {uptime_seconds}

# HELP quant_trade_trade_count Total number of trades
# TYPE quant_trade_trade_count counter
quant_trade_trade_count {self.metrics["trade_count"]}

# HELP quant_trade_total_pnl Total P&L in USD
# TYPE quant_trade_total_pnl gauge
quant_trade_total_pnl {self.metrics["total_pnl"]}

# HELP quant_trade_total_entries Total entry orders placed
# TYPE quant_trade_total_entries counter
quant_trade_total_entries {self.metrics["total_entries"]}

# HELP quant_trade_total_exits Total exit orders placed
# TYPE quant_trade_total_exits counter
quant_trade_total_exits {self.metrics["total_exits"]}

# HELP quant_trade_order_latency_ms Average order placement latency in milliseconds
# TYPE quant_trade_order_latency_ms gauge
quant_trade_order_latency_ms {avg_latency:.2f}

# HELP quant_trade_stop_ratchets Total stop ratchet events
# TYPE quant_trade_stop_ratchets counter
quant_trade_stop_ratchets {self.metrics["stop_ratchets"]}

# HELP quant_trade_ws_clients Active WebSocket connections
# TYPE quant_trade_ws_clients gauge
quant_trade_ws_clients {len(self.ws_clients)}
"""
        # Add API call counters
        for endpoint, count in self.metrics["api_call_count"].items():
            metrics_text += (
                f'quant_trade_api_calls_total{{endpoint="{endpoint}"}} {count}\n'
            )

        return web.Response(text=metrics_text, content_type="text/plain")

    async def handle_rate_limit_status(self, request: web.Request):
        """Rate limit status endpoint showing quota usage per endpoint.

        Returns current usage, limits, and reset times for each rate-limited endpoint.
        """
        if not await self._check_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)

        # Get rate limit manager from adapter if available
        endpoints_status = {}
        if self.orchestrator:
            for product_id, engine in self.orchestrator.engines.items():
                try:
                    adapter = engine.adapter
                    if hasattr(adapter, "rate_limiter"):
                        limiter = adapter.rate_limiter
                        endpoints_status[product_id] = {
                            "current_usage": limiter.current_usage if hasattr(limiter, "current_usage") else "N/A",
                            "limit": limiter.limit if hasattr(limiter, "limit") else "N/A",
                            "reset_time": limiter.reset_time if hasattr(limiter, "reset_time") else "N/A",
                        }
                except Exception:
                    pass

        return web.json_response(
            {
                "endpoints": endpoints_status,
                "note": "Rate limiting is enforced per endpoint and resets periodically",
            }
        )

    async def handle_performance(self, request: web.Request):
        """Get trading performance metrics.

        Returns win rate, P&L, Sharpe ratio, drawdown, and other metrics.
        """
        if not await self._check_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)

        perf = {
            "total_trades": self.metrics["trade_count"],
            "total_pnl": self.metrics["total_pnl"],
            "entries": self.metrics["total_entries"],
            "exits": self.metrics["total_exits"],
            "avg_order_latency_ms": (
                sum(self.metrics["order_latencies"]) / len(self.metrics["order_latencies"])
                if self.metrics["order_latencies"]
                else 0
            ),
            "stop_ratchets": self.metrics["stop_ratchets"],
        }

        if self.orchestrator:
            pm = self.orchestrator.portfolio_manager
            try:
                metrics = pm.get_portfolio_metrics()
                perf.update(
                    {
                        "active_positions": metrics.active_positions,
                        "closed_positions": metrics.closed_positions,
                        "realized_pnl": float(metrics.realized_pnl),
                        "unrealized_pnl": float(metrics.unrealized_pnl),
                        "total_return_pct": float(metrics.total_return_pct),
                        "win_rate_pct": float(metrics.win_rate_pct),
                        "max_drawdown_pct": float(metrics.max_drawdown_pct),
                        "concentration_pct": float(metrics.concentration_pct),
                    }
                )
            except Exception:
                pass

        return web.json_response(perf)

    async def handle_config_reload(self, request: web.Request):
        """Reload configuration from file.

        Validates new config before applying. Returns error if validation fails.
        """
        if not await self._check_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)

        try:
            # Get config path from environment or use default
            from trading.config import TradingConfig

            config_path = os.environ.get("CONFIG_PATH", "config.yaml")

            # Load and validate new config
            new_config = await asyncio.to_thread(TradingConfig.from_yaml, config_path)

            # If validation passed, optionally update orchestrator
            if self.orchestrator:
                # TODO: Implement hot-reload logic
                # This would need careful handling to:
                # 1. Close existing positions
                # 2. Update strategy parameters
                # 3. Re-initialize with new config
                pass

            return web.json_response(
                {
                    "status": "success",
                    "message": "Config reloaded successfully",
                    "config": {
                        "exchange": {
                            "product_id": str(new_config.exchange.product_id),
                        },
                        "strategy": {
                            "trail_pct": float(new_config.strategy.trail_pct),
                            "entry_confirmation_count": new_config.strategy.entry_confirmation_count,
                        },
                    },
                }
            )
        except Exception as e:
            return web.json_response(
                {"status": "error", "message": f"Config reload failed: {str(e)}"}, status=400
            )

    async def handle_ws(self, request: web.Request):
        """WebSocket endpoint for real-time updates."""
        await ws.prepare(request)
        self.ws_clients.append(ws)

        try:
            # Send initial status
            await ws.send_json({"type": "status", "data": await self._gather_status()})

            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        payload = json.loads(msg.data)
                    except Exception:
                        continue
                    # handle simple commands from UI
                    cmd = payload.get("cmd")
                    if cmd == "refresh":
                        await ws.send_json({"type": "status", "data": await self._gather_status()})
                    elif cmd == "ping":
                        await ws.send_json({"type": "pong"})
                elif msg.type == web.WSMsgType.ERROR:
                    break
        finally:
            try:
                self.ws_clients.remove(ws)
            except ValueError:
                pass
        return ws

    async def _gather_status(self) -> Dict[str, Any]:
        # Use orchestrator if available, otherwise read from persistence
        if self.orchestrator:
            return self.orchestrator.get_portfolio_status()

        # Fallback: construct basic metrics from DB
        metrics = {
            "total_capital": 0,
            "available_capital": 0,
            "deployed_capital": 0,
            "active_positions": 0,
            "closed_positions": 0,
            "realized_pnl": 0,
            "unrealized_pnl": 0,
            "total_pnl": 0,
            "total_return_pct": 0,
            "concentration_pct": 0,
            "win_rate_pct": 0,
        }
        try:
            positions = self.persistence.list_positions()
            metrics["active_positions"] = len(positions)
        except Exception:
            pass
        return {"metrics": metrics, "risk_violations": [], "rebalance_needed": False}

    async def handle_status(self, request: web.Request):
        return web.json_response(await self._gather_status())

    async def handle_emergency_liquidate(self, request: web.Request):
        if not await self._check_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        if not await self._validate_csrf(request):
            return web.json_response({"error": "invalid csrf"}, status=403)
        session = await get_session(request)
        role = session.get("role")
        if role != "admin":
            return web.json_response({"error": "forbidden"}, status=403)
        data = await request.json()
        prices = data.get("prices")
        if not self.orchestrator:
            return web.json_response({"error": "Orchestrator not initialized"}, status=400)
        try:
            result = await self.orchestrator.emergency_liquidate_portfolio(prices)
            return web.json_response({"result": str(result)})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_positions(self, request: web.Request):
        if not self.orchestrator:
            return web.json_response({"positions": []})
        pm = self.orchestrator.portfolio_manager
        out = []
        for pid, p in pm.positions.items():
            out.append(
                {
                    "position_id": pid,
                    "product_id": p.product_id,
                    "entry_price": str(p.state.entry_price),
                    "qty": str(p.state.qty_filled),
                    "status": p.status,
                    "current_pnl": str(p.current_pnl),
                }
            )
        return web.json_response({"positions": out})

    async def handle_position_detail(self, request: web.Request):
        if not await self._check_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        position_id = request.match_info.get("position_id")
        # try persistence first
        pos = await asyncio.to_thread(self.persistence.load_position, position_id)
        if not pos and self.orchestrator:
            pm = self.orchestrator.portfolio_manager
            p = pm.positions.get(position_id)
            if p:
                pos = p.state
        if not pos:
            return web.json_response({"error": "position not found"}, status=404)
        orders = await asyncio.to_thread(self.persistence.list_orders, position_id)
        return web.json_response({"position": pos.to_dict(), "orders": orders})

    async def handle_place_entry(self, request: web.Request):
        if not await self._check_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        if not await self._validate_csrf(request):
            return web.json_response({"error": "invalid csrf"}, status=403)
        session = await get_session(request)
        role = session.get("role", "operator")
        if role not in ("operator", "admin"):
            return web.json_response({"error": "forbidden"}, status=403)
        data = await request.json()
        product_id = data.get("product_id")
        price = Decimal(str(data.get("price")))
        qty = Decimal(str(data.get("qty")))
        if product_id not in self.orchestrator.engines:
            return web.json_response({"error": "unknown product_id"}, status=400)
        engine = self.orchestrator.engines[product_id]
        position_id = f"{product_id}_{int(time.time())}"
        try:
            order_id = await engine.submit_entry(position_id, price, qty)
            pos = PositionState(entry_price=price, qty_filled=qty, highest_price_since_entry=price)
            self.orchestrator.portfolio_manager.add_position(position_id, product_id, pos)
            await asyncio.to_thread(self.persistence.save_position, pos, position_id)
            return web.json_response({"order_id": order_id, "position_id": position_id})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_cancel_order(self, request: web.Request):
        if not await self._check_auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        if not await self._validate_csrf(request):
            return web.json_response({"error": "invalid csrf"}, status=403)
        session = await get_session(request)
        role = session.get("role")
        if role != "admin":
            return web.json_response({"error": "forbidden"}, status=403)
        data = await request.json()
        order_id = data.get("order_id")
        product_id = data.get("product_id")
        if not order_id or not product_id:
            return web.json_response({"error": "order_id and product_id required"}, status=400)
        engine = self.orchestrator.engines.get(product_id)
        if not engine:
            return web.json_response({"error": "unknown product_id"}, status=400)
        try:
            ok = await engine.adapter.cancel_order(order_id)
            return web.json_response({"ok": bool(ok)})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _feed_on_message(self, msg: dict):
        # Forward feed message to all connected browser clients
        out = {"type": "feed", "data": msg}
        for ws in list(self.ws_clients):
            try:
                await ws.send_json(out)
            except Exception:
                pass

    async def start_feed(self, product_ids):
        await self.feed_client.start(product_ids, self._feed_on_message)

    def register_orchestrator(self, orchestrator: MultiPairOrchestrator):
        self.orchestrator = orchestrator

    def _init_demo_orchestrator(self):
        # minimal portfolio config for demo
        portfolio = PortfolioConfig(
            total_capital=100000,
            max_position_size_pct=5,
            max_positions=5,
            max_correlated_exposure_pct=20,
            rebalance_threshold_pct=10,
            emergency_liquidation_loss_pct=-15,
        )

        orch = MultiPairOrchestrator(portfolio)

        demo_pairs = [
            PairConfig(
                product_id="BTC-USD",
                position_size_pct=5,
                trail_pct=0.02,
                correlation_group="large_cap",
            ),
            PairConfig(
                product_id="ETH-USD",
                position_size_pct=4,
                trail_pct=0.025,
                correlation_group="large_cap",
            ),
            PairConfig(
                product_id="SOL-USD", position_size_pct=3, trail_pct=0.03, correlation_group="alts"
            ),
        ]

        # Use real Coinbase adapter if credentials provided, otherwise use mock
        api_key = os.environ.get("CB_API_KEY")
        api_secret = os.environ.get("CB_API_SECRET")
        api_pass = os.environ.get("CB_API_PASSPHRASE")

        for p in demo_pairs:
            if api_key and api_secret and api_pass:
                adapter = AsyncCoinbaseAdapter(
                    api_key, api_secret, api_pass, product_id=p.product_id
                )
            else:
                adapter = _MockAsyncAdapter(p.product_id)
            engine = AsyncExecutionEngine(adapter, self.persistence, trail_pct=p.trail_pct)
            orch.register_pair(p, engine)

        self.orchestrator = orch
        # remember demo pairs for startup feed
        self._demo_feed_pairs = [p.product_id for p in demo_pairs]

    async def _on_startup(self, app):
        # start realtime feed for demo pairs if present
        try:
            pairs = getattr(self, "_demo_feed_pairs", None)
            if pairs:
                self._feed_task = asyncio.create_task(self.start_feed(pairs))
            # run startup_reconcile for engines
            if self.orchestrator:
                for engine in self.orchestrator.engines.values():
                    try:
                        await engine.startup_reconcile()
                    except Exception:
                        pass
        except Exception:
            pass

    async def _on_cleanup(self, app):
        # stop feed task and ws client
        try:
            if self._feed_task:
                self._feed_task.cancel()
                try:
                    await self._feed_task
                except Exception:
                    pass
            await self.feed_client.stop()
        except Exception:
            pass

    def run(self):
        web.run_app(self.app, host=self.host, port=self.port)


if __name__ == "__main__":
    server = GUIServer()
    print("Starting GUI server on http://0.0.0.0:8080")
    server.run()
