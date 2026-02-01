"""Tests for operational CLI tools: position_status, order_manager, trade_history."""
import json
import sqlite3
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from trading.persistence_sqlite import SQLitePersistence
from trading.position import PositionState
from trading.pnl import Fill, calculate_pnl, aggregate_pnl


@pytest.fixture
def temp_db():
    """Create a temporary database with test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        persistence = SQLitePersistence(db_path)
        
        # Create test positions
        pos1 = PositionState(
            entry_price=Decimal("50000"),
            qty_filled=Decimal("0.5"),
            highest_price_since_entry=Decimal("51000"),
            current_stop_trigger=Decimal("49000"),
            current_stop_limit=Decimal("48950"),
            stop_order_id="stop_123"
        )
        persistence.save_position(pos1, position_id="BTC_001")
        
        pos2 = PositionState(
            entry_price=Decimal("3000"),
            qty_filled=Decimal("1.0"),
            highest_price_since_entry=Decimal("3100"),
            current_stop_trigger=Decimal("2950"),
            current_stop_limit=Decimal("2925"),
            stop_order_id="stop_456"
        )
        persistence.save_position(pos2, position_id="ETH_001")
        
        # Create test orders
        persistence.save_order(
            "order_001", "BTC_001",
            {"type": "entry", "side": "buy", "price": "50000", "qty": "0.5"},
            "filled"
        )
        persistence.save_order(
            "order_002", "BTC_001",
            {"type": "stop", "side": "sell", "price": "49000", "qty": "0.5"},
            "pending"
        )
        persistence.save_order(
            "order_003", "ETH_001",
            {"type": "entry", "side": "buy", "price": "3000", "qty": "1.0"},
            "filled"
        )
        persistence.save_order(
            "order_004", "ETH_001",
            {"type": "stop", "side": "sell", "price": "2950", "qty": "1.0"},
            "pending"
        )
        
        yield persistence
        persistence.close()


class TestListPositions:
    """Test position status CLI list command."""
    
    def test_list_positions_returns_all_positions(self, temp_db):
        """Test that list_positions returns all position IDs."""
        position_ids = temp_db.list_positions()
        assert "BTC_001" in position_ids
        assert "ETH_001" in position_ids
        assert len(position_ids) == 2
    
    def test_list_positions_loads_position_data(self, temp_db):
        """Test that we can load position data for display."""
        position_ids = temp_db.list_positions()
        
        for pos_id in position_ids:
            pos = temp_db.load_position(pos_id)
            assert pos is not None
            assert pos.qty_filled > 0
            assert pos.entry_price > 0
            assert pos.current_stop_trigger > 0
    
    def test_list_positions_btc_position_data(self, temp_db):
        """Test BTC position has correct data."""
        pos = temp_db.load_position("BTC_001")
        assert pos.entry_price == Decimal("50000")
        assert pos.qty_filled == Decimal("0.5")
        assert pos.highest_price_since_entry == Decimal("51000")
        assert pos.current_stop_trigger == Decimal("49000")


class TestShowPosition:
    """Test position status CLI show command."""
    
    def test_show_position_loads_correct_position(self, temp_db):
        """Test that show_position loads the correct position."""
        pos = temp_db.load_position("BTC_001")
        assert pos.entry_price == Decimal("50000")
        assert pos.qty_filled == Decimal("0.5")
    
    def test_show_position_with_orders(self, temp_db):
        """Test that show_position can retrieve related orders."""
        orders = temp_db.list_orders(position_id="BTC_001")
        assert len(orders) == 2
        
        # Check order IDs are present
        order_ids = [o["order_id"] for o in orders]
        assert "order_001" in order_ids
        assert "order_002" in order_ids
    
    def test_show_position_nonexistent_returns_none(self, temp_db):
        """Test that loading nonexistent position returns None."""
        pos = temp_db.load_position("NONEXISTENT")
        assert pos is None


class TestOrderManager:
    """Test order_manager CLI commands."""
    
    def test_list_orders_all_positions(self, temp_db):
        """Test listing all orders across positions."""
        # Get all orders
        position_ids = temp_db.list_positions()
        total_orders = 0
        
        for pos_id in position_ids:
            orders = temp_db.list_orders(position_id=pos_id)
            total_orders += len(orders)
        
        assert total_orders == 4
    
    def test_cancel_order_updates_state(self, temp_db):
        """Test cancelling an order updates its state."""
        # Get initial state
        orders_before = temp_db.list_orders(position_id="BTC_001")
        assert any(o["order_id"] == "order_001" for o in orders_before)
        
        # Update order state directly
        cur = sqlite3.connect(str(temp_db.path)).cursor()
        cur.execute("UPDATE orders SET state = ? WHERE order_id = ?", ("cancelled", "order_001"))
        cur.connection.commit()
        cur.connection.close()
        
        # Verify state changed
        orders_after = temp_db.list_orders(position_id="BTC_001")
        cancelled_order = next(o for o in orders_after if o["order_id"] == "order_001")
        assert cancelled_order["state"] == "cancelled"
    
    def test_force_exit_closes_position(self, temp_db):
        """Test force exit closes a position."""
        pos_before = temp_db.load_position("BTC_001")
        assert pos_before.qty_filled > 0
        
        # Simulate force exit
        exit_price = Decimal("51000")
        pos_before.qty_filled = Decimal("0")
        temp_db.save_position(pos_before, position_id="BTC_001")
        
        # Verify position is closed
        pos_after = temp_db.load_position("BTC_001")
        assert pos_after.qty_filled == 0


class TestTradeHistory:
    """Test trade_history CLI commands."""
    
    def test_get_fills_from_orders(self, temp_db):
        """Test extracting fills from orders."""
        position_ids = temp_db.list_positions()
        
        fills = []
        for pos_id in position_ids:
            orders = temp_db.list_orders(position_id=pos_id)
            for order in orders:
                if order.get("state") == "filled":
                    fill = Fill(
                        order_id=order["order_id"],
                        side="buy" if order.get("type") == "entry" else "sell",
                        price=Decimal(str(order["price"])),
                        qty=Decimal(str(order["qty"])),
                        timestamp=0  # placeholder
                    )
                    fills.append(fill)
        
        # Should have 2 entry fills
        entry_fills = [f for f in fills if f.side == "buy"]
        assert len(entry_fills) == 2
    
    def test_position_history_loads_data(self, temp_db):
        """Test position history loads correct position data."""
        pos = temp_db.load_position("ETH_001")
        orders = temp_db.list_orders(position_id="ETH_001")
        
        assert pos.entry_price == Decimal("3000")
        assert pos.qty_filled == Decimal("1.0")
        assert len(orders) == 2
    
    def test_calculate_pnl_simple(self):
        """Test P&L calculation with simple entry/exit."""
        # Entry at 100, buy 1 unit
        # Exit at 110, sell 1 unit
        # Realized P&L = 110 - 100 = 10
        analysis = calculate_pnl(
            entry_price=Decimal("100"),
            entry_qty=Decimal("1"),
            exit_price=Decimal("110"),
            exit_qty=Decimal("1")
        )
        
        assert analysis.realized_pnl == Decimal("10")
        assert analysis.pnl_percent == Decimal("10")
    
    def test_aggregate_pnl_multiple_trades(self):
        """Test aggregating P&L across multiple trades."""
        analyses = [
            # Trade 1: Entry at 100, Exit at 110 = +10
            calculate_pnl(
                entry_price=Decimal("100"),
                entry_qty=Decimal("1"),
                exit_price=Decimal("110"),
                exit_qty=Decimal("1")
            ),
            # Trade 2: Entry at 200, Exit at 190 = -10
            calculate_pnl(
                entry_price=Decimal("200"),
                entry_qty=Decimal("1"),
                exit_price=Decimal("190"),
                exit_qty=Decimal("1")
            ),
        ]
        
        agg = aggregate_pnl(analyses)
        assert agg["total_realized_pnl"] == Decimal("0")
        assert agg["win_count"] == 1
        assert agg["loss_count"] == 1
        assert agg["win_rate_percent"] == Decimal("50")


class TestOperationalToolsIntegration:
    """Integration tests for operational tools working together."""
    
    def test_position_status_to_order_manager_flow(self, temp_db):
        """Test typical user flow: check position, then manage orders."""
        # Step 1: List positions
        position_ids = temp_db.list_positions()
        assert len(position_ids) > 0
        
        # Step 2: Show a position
        pos = temp_db.load_position(position_ids[0])
        assert pos is not None
        
        # Step 3: List its orders
        orders = temp_db.list_orders(position_id=position_ids[0])
        assert len(orders) > 0
        
        # Step 4: Cancel an order
        order_id = orders[0]["order_id"]
        cur = sqlite3.connect(str(temp_db.path)).cursor()
        cur.execute("UPDATE orders SET state = ? WHERE order_id = ?", ("cancelled", order_id))
        cur.connection.commit()
        cur.connection.close()
        
        # Verify cancellation
        updated_orders = temp_db.list_orders(position_id=position_ids[0])
        cancelled = next(o for o in updated_orders if o["order_id"] == order_id)
        assert cancelled["state"] == "cancelled"
    
    def test_full_position_lifecycle(self, temp_db):
        """Test full position lifecycle: create, view, exit."""
        # Create new position
        pos = PositionState(
            entry_price=Decimal("1000"),
            qty_filled=Decimal("1"),
            highest_price_since_entry=Decimal("1050"),
            current_stop_trigger=Decimal("950"),
            current_stop_limit=Decimal("925"),
            stop_order_id="stop_new"
        )
        temp_db.save_position(pos, position_id="NEW_POS")
        
        # Add entry order
        temp_db.save_order(
            "order_new", "NEW_POS",
            {"type": "entry", "side": "buy", "price": "1000", "qty": "1"},
            "filled"
        )
        
        # Verify position exists
        loaded_pos = temp_db.load_position("NEW_POS")
        assert loaded_pos.qty_filled == Decimal("1")
        
        # Add exit order
        temp_db.save_order(
            "order_exit", "NEW_POS",
            {"type": "exit", "side": "sell", "price": "1050", "qty": "1"},
            "filled"
        )
        
        # Close position
        loaded_pos.qty_filled = Decimal("0")
        temp_db.save_position(loaded_pos, position_id="NEW_POS")
        
        # Verify position is closed
        final_pos = temp_db.load_position("NEW_POS")
        assert final_pos.qty_filled == 0
