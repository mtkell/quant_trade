"""Realtime WebSocket client using aiohttp to subscribe to public feeds.

This client connects to Coinbase public WebSocket feed by default and
forwards messages to a provided async callback.
"""
from typing import List, Callable, Awaitable, Optional
import asyncio
import json
from aiohttp import ClientSession, ClientWebSocketResponse

DEFAULT_WS_URL = "wss://ws-feed.pro.coinbase.com"


class RealTimeWebSocketClient:
    def __init__(self, ws_url: str = DEFAULT_WS_URL):
        self.ws_url = ws_url
        self._session: Optional[ClientSession] = None
        self._ws: Optional[ClientWebSocketResponse] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def connect(self, product_ids: List[str], channels: List[str] = None):
        if channels is None:
            channels = ["ticker", "matches"]
        self._session = ClientSession()
        self._ws = await self._session.ws_connect(self.ws_url)

        subscribe_msg = {"type": "subscribe", "product_ids": product_ids, "channels": channels}
        await self._ws.send_str(json.dumps(subscribe_msg))

    async def _run_loop(self, on_message: Callable[[dict], Awaitable[None]]):
        assert self._ws is not None
        self._running = True
        try:
            async for msg in self._ws:
                if msg.type == 1:  # TEXT
                    try:
                        data = json.loads(msg.data)
                    except Exception:
                        continue
                    await on_message(data)
                elif msg.type == 3:  # BINARY
                    # ignoring binary
                    continue
                elif msg.type == 4:  # CLOSE
                    break
        finally:
            self._running = False

    async def start(self, product_ids: List[str], on_message: Callable[[dict], Awaitable[None]], channels: List[str] = None):
        """Connect and start message loop. This method returns immediately and runs a background task."""
        await self.connect(product_ids, channels=channels)
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._run_loop(on_message))

    async def stop(self):
        self._running = False
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()
        if self._task:
            await asyncio.shield(self._task)


if __name__ == "__main__":
    import asyncio

    async def on_msg(msg):
        print(msg)

    async def main():
        client = RealTimeWebSocketClient()
        await client.start(["BTC-USD", "ETH-USD"], on_msg)
        await asyncio.sleep(5)
        await client.stop()

    asyncio.run(main())
