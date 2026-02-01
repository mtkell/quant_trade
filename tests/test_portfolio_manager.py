"""Tests for portfolio management and multi-pair orchestration."""
import pytest
from decimal import Decimal

from trading.portfolio_manager import (
    PortfolioConfig, PortfolioManager, PairConfig, PortfolioPosition
)
from trading.position import PositionState


@pytest.fixture
def portfolio_config():
    """Create test portfolio configuration."""
    return PortfolioConfig(
        total_capital=Decimal('100000'),
        max_position_size_pct=Decimal('5'),
        max_positions=10,
        max_correlated_exposure_pct=Decimal('20'),
        rebalance_threshold_pct=Decimal('10'),
        emergency_liquidation_loss_pct=Decimal('-10')
    )


@pytest.fixture
def portfolio_manager(portfolio_config):
    """Create test portfolio manager."""
    return PortfolioManager(portfolio_config)


class TestPortfolioConfig:
    """Test portfolio configuration."""
    
    def test_portfolio_config_defaults(self):
        """Test portfolio config with defaults."""
        config = PortfolioConfig(total_capital=Decimal('50000'))
        assert config.total_capital == Decimal('50000')
        assert config.max_position_size_pct == Decimal('5')
        assert config.max_positions == 10
    
    def test_pair_config_creation(self):
        """Test pair configuration creation."""
        pair = PairConfig(
            product_id="BTC-USD",
            position_size_pct=Decimal('2'),
            trail_pct=Decimal('0.02')
        )
        assert pair.product_id == "BTC-USD"
        assert pair.position_size_pct == Decimal('2')
        assert pair.enabled is True


class TestPortfolioManagerRegistration:
    """Test portfolio pair registration."""
    
    def test_register_single_pair(self, portfolio_manager):
        """Test registering a single pair."""
        pair = PairConfig(product_id="BTC-USD", position_size_pct=Decimal('5'))
        portfolio_manager.register_pair(pair)
        
        assert "BTC-USD" in portfolio_manager.pair_configs
        assert portfolio_manager.pair_configs["BTC-USD"].product_id == "BTC-USD"
    
    def test_register_multiple_pairs(self, portfolio_manager):
        """Test registering multiple pairs."""
        pairs = [
            PairConfig(product_id="BTC-USD", position_size_pct=Decimal('3')),
            PairConfig(product_id="ETH-USD", position_size_pct=Decimal('2')),
            PairConfig(product_id="SOL-USD", position_size_pct=Decimal('2')),
        ]
        
        for pair in pairs:
            portfolio_manager.register_pair(pair)
        
        assert len(portfolio_manager.pair_configs) == 3
        assert "BTC-USD" in portfolio_manager.pair_configs
        assert "ETH-USD" in portfolio_manager.pair_configs
        assert "SOL-USD" in portfolio_manager.pair_configs
    
    def test_register_disabled_pair(self, portfolio_manager):
        """Test that disabled pairs are not registered."""
        pair = PairConfig(product_id="DOGE-USD", enabled=False)
        portfolio_manager.register_pair(pair)
        
        assert "DOGE-USD" not in portfolio_manager.pair_configs
    
    def test_register_exceeds_max_positions(self, portfolio_manager):
        """Test registration limit."""
        portfolio_manager.config.max_positions = 2
        
        portfolio_manager.register_pair(PairConfig(product_id="BTC-USD"))
        portfolio_manager.register_pair(PairConfig(product_id="ETH-USD"))
        
        with pytest.raises(ValueError, match="Max positions"):
            portfolio_manager.register_pair(PairConfig(product_id="SOL-USD"))


class TestPortfolioPositionSize:
    """Test position size calculations."""
    
    def test_get_position_size_usd(self, portfolio_manager, portfolio_config):
        """Test calculating position size in USD."""
        pair = PairConfig(product_id="BTC-USD", position_size_pct=Decimal('2'))
        portfolio_manager.register_pair(pair)
        
        size_usd = portfolio_manager.get_position_size_usd("BTC-USD")
        expected = portfolio_config.total_capital * Decimal('2') / 100
        assert size_usd == expected
    
    def test_get_position_size_unregistered_pair(self, portfolio_manager):
        """Test position size for unregistered pair."""
        size = portfolio_manager.get_position_size_usd("UNKNOWN-USD")
        assert size == Decimal('0')


class TestPortfolioPositionTracking:
    """Test portfolio position management."""
    
    def test_add_position(self, portfolio_manager):
        """Test adding a position to portfolio."""
        pair = PairConfig(product_id="BTC-USD", position_size_pct=Decimal('5'))
        portfolio_manager.register_pair(pair)
        
        pos_state = PositionState(
            entry_price=Decimal('50000'),
            qty_filled=Decimal('0.5'),
            highest_price_since_entry=Decimal('50000'),
            current_stop_trigger=Decimal('49000'),
            current_stop_limit=Decimal('48950'),
            stop_order_id="stop_123"
        )
        
        portfolio_manager.add_position("pos_001", "BTC-USD", pos_state)
        
        assert "pos_001" in portfolio_manager.positions
        assert portfolio_manager.positions["pos_001"].product_id == "BTC-USD"
    
    def test_add_position_unregistered_pair(self, portfolio_manager):
        """Test adding position for unregistered pair fails."""
        pos_state = PositionState(
            entry_price=Decimal('50000'),
            qty_filled=Decimal('0.5'),
            highest_price_since_entry=Decimal('50000'),
            current_stop_trigger=Decimal('49000'),
            current_stop_limit=Decimal('48950'),
            stop_order_id=None
        )
        
        with pytest.raises(ValueError, match="not registered"):
            portfolio_manager.add_position("pos_001", "BTC-USD", pos_state)
    
    def test_close_position(self, portfolio_manager):
        """Test closing a position."""
        pair = PairConfig(product_id="BTC-USD")
        portfolio_manager.register_pair(pair)
        
        pos_state = PositionState(
            entry_price=Decimal('50000'),
            qty_filled=Decimal('0.5'),
            highest_price_since_entry=Decimal('51000'),
            current_stop_trigger=Decimal('49000'),
            current_stop_limit=Decimal('48950'),
            stop_order_id=None
        )
        
        portfolio_manager.add_position("pos_001", "BTC-USD", pos_state)
        
        # Close at profit
        realized_pnl = portfolio_manager.close_position("pos_001", Decimal('51000'))
        
        assert "pos_001" not in portfolio_manager.positions
        assert len(portfolio_manager.closed_positions) == 1
        assert realized_pnl == Decimal('500')  # (51000 - 50000) * 0.5


class TestPortfolioMetrics:
    """Test portfolio metrics calculation."""
    
    def test_empty_portfolio_metrics(self, portfolio_manager, portfolio_config):
        """Test metrics for empty portfolio."""
        metrics = portfolio_manager.get_portfolio_metrics()
        
        assert metrics.total_capital == portfolio_config.total_capital
        assert metrics.available_capital == portfolio_config.total_capital
        assert metrics.deployed_capital == Decimal('0')
        assert metrics.active_positions == 0
        assert metrics.closed_positions == 0
        assert metrics.total_pnl == Decimal('0')
    
    def test_single_position_metrics(self, portfolio_manager):
        """Test metrics with single active position."""
        pair = PairConfig(product_id="BTC-USD", position_size_pct=Decimal('2'))
        portfolio_manager.register_pair(pair)
        
        pos_state = PositionState(
            entry_price=Decimal('50000'),
            qty_filled=Decimal('1'),
            highest_price_since_entry=Decimal('50000'),
            current_stop_trigger=Decimal('49000'),
            current_stop_limit=Decimal('48950'),
            stop_order_id=None
        )
        
        portfolio_manager.add_position("pos_001", "BTC-USD", pos_state)
        portfolio_manager.update_position("pos_001", pos_state, Decimal('51000'))
        
        metrics = portfolio_manager.get_portfolio_metrics()
        
        assert metrics.active_positions == 1
        assert metrics.deployed_capital == Decimal('50000')
        assert metrics.available_capital == Decimal('50000')
        assert metrics.unrealized_pnl == Decimal('1000')
    
    def test_closed_position_metrics(self, portfolio_manager):
        """Test metrics with closed positions."""
        pair = PairConfig(product_id="BTC-USD")
        portfolio_manager.register_pair(pair)
        
        pos_state = PositionState(
            entry_price=Decimal('50000'),
            qty_filled=Decimal('1'),
            highest_price_since_entry=Decimal('51000'),
            current_stop_trigger=Decimal('49000'),
            current_stop_limit=Decimal('48950'),
            stop_order_id=None
        )
        
        portfolio_manager.add_position("pos_001", "BTC-USD", pos_state)
        portfolio_manager.close_position("pos_001", Decimal('51000'))
        
        metrics = portfolio_manager.get_portfolio_metrics()
        
        assert metrics.active_positions == 0
        assert metrics.closed_positions == 1
        assert metrics.realized_pnl == Decimal('1000')
        assert metrics.win_rate_pct == Decimal('100')
    
    def test_multiple_positions_metrics(self, portfolio_manager):
        """Test metrics with multiple positions."""
        for i, (product, pct) in enumerate([("BTC-USD", Decimal('3')), ("ETH-USD", Decimal('2'))]):
            pair = PairConfig(product_id=product, position_size_pct=pct)
            portfolio_manager.register_pair(pair)
            
            pos_state = PositionState(
                entry_price=Decimal('1000'),
                qty_filled=Decimal('1'),
                highest_price_since_entry=Decimal('1000'),
                current_stop_trigger=Decimal('900'),
                current_stop_limit=Decimal('850'),
                stop_order_id=None
            )
            
            portfolio_manager.add_position(f"pos_{i:03d}", product, pos_state)
        
        metrics = portfolio_manager.get_portfolio_metrics()
        
        assert metrics.active_positions == 2
        assert metrics.deployed_capital == Decimal('2000')


class TestPortfolioRiskManagement:
    """Test portfolio risk management."""
    
    def test_check_risk_limits_ok(self, portfolio_manager):
        """Test risk checks pass when limits not violated."""
        pair = PairConfig(product_id="BTC-USD", position_size_pct=Decimal('2'))
        portfolio_manager.register_pair(pair)
        
        # Position size: 100000 * 2% = $2000
        # At $50000/BTC, that's 0.04 BTC
        pos_state = PositionState(
            entry_price=Decimal('50000'),
            qty_filled=Decimal('0.04'),
            highest_price_since_entry=Decimal('50000'),
            current_stop_trigger=Decimal('49000'),
            current_stop_limit=Decimal('48950'),
            stop_order_id=None
        )
        
        portfolio_manager.add_position("pos_001", "BTC-USD", pos_state)
        
        issues = portfolio_manager.check_risk_limits()
        assert len(issues) == 0
    
    def test_check_position_size_limit(self, portfolio_manager):
        """Test detection of position size violations."""
        portfolio_manager.config.max_position_size_pct = Decimal('2')
        
        pair = PairConfig(product_id="BTC-USD", position_size_pct=Decimal('3'))
        portfolio_manager.register_pair(pair)
        
        # Position that exceeds limit
        pos_state = PositionState(
            entry_price=Decimal('50000'),
            qty_filled=Decimal('3'),  # 150k > 2% of 100k
            highest_price_since_entry=Decimal('50000'),
            current_stop_trigger=Decimal('49000'),
            current_stop_limit=Decimal('48950'),
            stop_order_id=None
        )
        
        portfolio_manager.add_position("pos_001", "BTC-USD", pos_state)
        
        issues = portfolio_manager.check_risk_limits()
        assert "position_size" in issues
    
    def test_rebalance_detection(self, portfolio_manager):
        """Test detection of positions needing rebalancing."""
        portfolio_manager.config.rebalance_threshold_pct = Decimal('5')
        
        pair = PairConfig(product_id="BTC-USD", position_size_pct=Decimal('10'))
        portfolio_manager.register_pair(pair)
        
        pos_state = PositionState(
            entry_price=Decimal('50000'),
            qty_filled=Decimal('2'),  # 100k deployed = 100% (vs 10% target)
            highest_price_since_entry=Decimal('50000'),
            current_stop_trigger=Decimal('49000'),
            current_stop_limit=Decimal('48950'),
            stop_order_id=None
        )
        
        portfolio_manager.add_position("pos_001", "BTC-USD", pos_state)
        
        actions = portfolio_manager.get_rebalance_actions()
        
        assert len(actions) > 0
        assert actions[0]["position_id"] == "pos_001"
        assert actions[0]["action"] == "decrease"


class TestPortfolioWinRate:
    """Test win rate and performance tracking."""
    
    def test_win_rate_calculation(self, portfolio_manager):
        """Test win rate calculation from closed positions."""
        pair = PairConfig(product_id="BTC-USD")
        portfolio_manager.register_pair(pair)
        
        # Add and close profitable trade
        pos1 = PositionState(
            entry_price=Decimal('50000'),
            qty_filled=Decimal('1'),
            highest_price_since_entry=Decimal('51000'),
            current_stop_trigger=Decimal('49000'),
            current_stop_limit=Decimal('48950'),
            stop_order_id=None
        )
        portfolio_manager.add_position("pos_001", "BTC-USD", pos1)
        portfolio_manager.close_position("pos_001", Decimal('51000'))
        
        # Add and close losing trade
        pos2 = PositionState(
            entry_price=Decimal('50000'),
            qty_filled=Decimal('1'),
            highest_price_since_entry=Decimal('50000'),
            current_stop_trigger=Decimal('49000'),
            current_stop_limit=Decimal('48950'),
            stop_order_id=None
        )
        portfolio_manager.add_position("pos_002", "BTC-USD", pos2)
        portfolio_manager.close_position("pos_002", Decimal('49000'))
        
        metrics = portfolio_manager.get_portfolio_metrics()
        
        assert metrics.closed_positions == 2
        assert metrics.win_rate_pct == Decimal('50')
        assert metrics.total_pnl == Decimal('0')  # 1000 - 1000
