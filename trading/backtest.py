"""Backtesting framework for trading strategy validation.

Allows replaying historical OHLCV data through the same entry/exit logic
to validate strategy performance without live exchange connection.

Usage:

    from trading.backtest import BacktestEngine
    import csv

    # Load historical data
    trades = []
    with open("historical_data.csv") as f:
        for row in csv.DictReader(f):
            trades.append({
                "timestamp": float(row["timestamp"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })

    # Run backtest
    engine = BacktestEngine(config, initial_capital=Decimal('10000'))
    results = engine.run(trades)

    print(f"Win Rate: {results['win_rate_pct']:.2f}%")
    print(f"Total P&L: ${results['total_pnl']}")
    print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {results['max_drawdown_pct']:.2f}%")
"""

from decimal import Decimal
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import statistics


@dataclass
class OHLCV:
    """Open-High-Low-Close-Volume candle data."""

    timestamp: float
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass
class BacktestResults:
    """Results from a backtest run."""

    total_capital: Decimal
    final_capital: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal
    total_pnl: Decimal
    total_return_pct: Decimal
    max_drawdown_pct: Decimal
    sharpe_ratio: Optional[Decimal] = None
    trades: List[Dict[str, Any]] = None


class BacktestEngine:
    """Run backtests of trading strategy against historical data.

    Features:
    - Replay historical OHLCV data through entry/exit logic
    - Track position P&L
    - Calculate performance metrics (win rate, Sharpe ratio, drawdown)
    - Support multiple pairs simultaneously
    - Configurable entry/exit parameters

    """

    def __init__(self, config, initial_capital: Decimal = Decimal("10000")):
        """Initialize backtest engine.

        Args:
            config: TradingConfig object with strategy parameters
            initial_capital: Starting capital in USD
        """
        self.config = config
        self.initial_capital = initial_capital
        self.available_capital = initial_capital
        self.positions = {}  # position_id -> position state
        self.closed_positions = []
        self.trades = []

    def run(self, candles: List[OHLCV]) -> BacktestResults:
        """Run backtest against historical candles.

        Args:
            candles: List of OHLCV candle data, ordered by timestamp

        Returns:
            BacktestResults with performance metrics
        """
        portfolio_values = []
        returns = []

        for candle in candles:
            # Process candle
            self._process_candle(candle)

            # Track portfolio value for Sharpe/drawdown calcs
            portfolio_value = self.available_capital + self._unrealized_pnl()
            portfolio_values.append(portfolio_value)

            if len(portfolio_values) > 1:
                ret = (portfolio_value - portfolio_values[-2]) / portfolio_values[-2]
                returns.append(ret)

        # Calculate final metrics
        final_capital = self.available_capital + self._unrealized_pnl()
        total_pnl = final_capital - self.initial_capital
        total_return_pct = (
            (total_pnl / self.initial_capital * 100)
            if self.initial_capital > 0
            else Decimal("0")
        )

        winning_trades = len([t for t in self.closed_positions if t["pnl"] > 0])
        total_trades = len(self.closed_positions)
        win_rate_pct = (
            (Decimal(winning_trades) / Decimal(total_trades) * 100)
            if total_trades > 0
            else Decimal("0")
        )

        # Sharpe ratio (annualized, assuming 252 trading days)
        sharpe_ratio = None
        if returns and len(returns) > 1:
            try:
                mean_return = statistics.mean(returns)
                stdev = statistics.stdev(returns)
                if stdev > 0:
                    sharpe_ratio = Decimal(str((mean_return / stdev) * (252 ** 0.5)))
            except Exception:
                pass

        # Max drawdown
        max_drawdown_pct = self._calculate_max_drawdown(portfolio_values)

        return BacktestResults(
            total_capital=self.initial_capital,
            final_capital=final_capital,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=total_trades - winning_trades,
            win_rate_pct=win_rate_pct,
            total_pnl=total_pnl,
            total_return_pct=total_return_pct,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            trades=self.closed_positions,
        )

    def _process_candle(self, candle: OHLCV):
        """Process a single OHLCV candle.

        Simulates:
        - Entry signal evaluation
        - Order fills
        - Stop triggers
        - Exit fills
        """
        # TODO: Implement entry/exit logic replay
        # This would need to call the same indicator functions
        # and order execution logic as live trading

        pass

    def _unrealized_pnl(self) -> Decimal:
        """Calculate total unrealized P&L across open positions."""
        total = Decimal("0")
        for pos in self.positions.values():
            # P&L = (current_price - entry_price) * qty
            total += pos.get("pnl", Decimal("0"))
        return total

    def _calculate_max_drawdown(self, portfolio_values: List[Decimal]) -> Decimal:
        """Calculate maximum drawdown percentage.

        Args:
            portfolio_values: List of portfolio values over time

        Returns:
            Maximum drawdown as percentage
        """
        if not portfolio_values:
            return Decimal("0")

        max_value = portfolio_values[0]
        max_drawdown = Decimal("0")

        for value in portfolio_values:
            if value > max_value:
                max_value = value

            drawdown = (max_value - value) / max_value * 100 if max_value > 0 else Decimal("0")
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return max_drawdown


# Example usage and helpers
def load_candles_from_csv(filename: str) -> List[OHLCV]:
    """Load OHLCV candles from CSV file.

    CSV format should have columns:
    timestamp, open, high, low, close, volume

    Args:
        filename: Path to CSV file

    Returns:
        List of OHLCV candles
    """
    import csv

    candles = []
    with open(filename) as f:
        reader = csv.DictReader(f)
        for row in reader:
            candles.append(
                OHLCV(
                    timestamp=float(row["timestamp"]),
                    open=Decimal(row["open"]),
                    high=Decimal(row["high"]),
                    low=Decimal(row["low"]),
                    close=Decimal(row["close"]),
                    volume=Decimal(row["volume"]),
                )
            )
    return candles
