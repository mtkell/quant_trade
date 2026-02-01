#!/usr/bin/env python
"""Integration test demonstrating all three operational tools working together."""
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading.persistence_sqlite import SQLitePersistence
from trading.position import PositionState


def setup_test_db(db_path):
    """Create test database with sample data."""
    persistence = SQLitePersistence(db_path)
    
    # Create position
    pos = PositionState(
        entry_price=Decimal("50000"),
        qty_filled=Decimal("0.5"),
        highest_price_since_entry=Decimal("51000"),
        current_stop_trigger=Decimal("49000"),
        current_stop_limit=Decimal("48950"),
        stop_order_id="stop_123"
    )
    persistence.save_position(pos, position_id="BTC_001")
    
    # Create orders
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
    
    persistence.close()
    return persistence


def test_operational_tools_integration():
    """Test all tools can read and modify position state."""
    
    # Get workspace root
    workspace_root = Path(__file__).parent.parent
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        # Setup
        persistence = setup_test_db(db_path)
        
        print("=" * 70)
        print("OPERATIONAL TOOLS INTEGRATION TEST")
        print("=" * 70)
        
        # Test 1: Position Status - List
        print("\n[1] Testing Position Status CLI - List Command")
        print("-" * 70)
        result = subprocess.run(
            [
                "python", "scripts/position_status.py",
                "--db", str(db_path),
                "list"
            ],
            cwd=workspace_root,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        assert result.returncode == 0, f"List failed: {result.stderr}"
        assert "BTC_001" in result.stdout, "Position not found in list"
        print("✓ Position list command successful")
        
        # Test 2: Position Status - Show
        print("\n[2] Testing Position Status CLI - Show Command")
        print("-" * 70)
        result = subprocess.run(
            [
                "python", "scripts/position_status.py",
                "--db", str(db_path),
                "show", "BTC_001"
            ],
            cwd=workspace_root,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        assert result.returncode == 0, f"Show failed: {result.stderr}"
        assert "50000" in result.stdout, "Entry price not shown"
        assert "order_001" in result.stdout, "Order not shown"
        print("✓ Position show command successful")
        
        # Test 3: Order Manager - List
        print("\n[3] Testing Order Manager CLI - List Command")
        print("-" * 70)
        result = subprocess.run(
            [
                "python", "scripts/order_manager.py",
                "--db", str(db_path),
                "list"
            ],
            cwd=workspace_root,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        assert result.returncode == 0, f"List failed: {result.stderr}"
        assert "order_001" in result.stdout, "Order not listed"
        assert "filled" in result.stdout, "Order state not shown"
        print("✓ Order list command successful")
        
        # Test 4: Trade History - Summary
        print("\n[4] Testing Trade History CLI - Summary Command")
        print("-" * 70)
        result = subprocess.run(
            [
                "python", "scripts/trade_history.py",
                "--db", str(db_path),
                "summary"
            ],
            cwd=workspace_root,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        assert result.returncode == 0, f"Summary failed: {result.stderr}"
        assert "Trading Summary" in result.stdout, "Summary header not found"
        print("✓ Trade history summary command successful")
        
        # Test 5: Trade History - List
        print("\n[5] Testing Trade History CLI - List Command")
        print("-" * 70)
        result = subprocess.run(
            [
                "python", "scripts/trade_history.py",
                "--db", str(db_path),
                "list"
            ],
            cwd=workspace_root,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        assert result.returncode == 0, f"List failed: {result.stderr}"
        assert "order_001" in result.stdout, "Order not listed"
        print("✓ Trade history list command successful")
        
        # Test 6: Trade History - Position
        print("\n[6] Testing Trade History CLI - Position Command")
        print("-" * 70)
        result = subprocess.run(
            [
                "python", "scripts/trade_history.py",
                "--db", str(db_path),
                "position", "BTC_001"
            ],
            cwd=workspace_root,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        assert result.returncode == 0, f"Position history failed: {result.stderr}"
        assert "BTC_001" in result.stdout, "Position not shown"
        print("✓ Trade history position command successful")
        
        # Test 7: Workflow - Check position, then modify order
        print("\n[7] Testing Workflow - Check Position, Then Cancel Order")
        print("-" * 70)
        
        # First, list position
        result1 = subprocess.run(
            [
                "python", "scripts/position_status.py",
                "--db", str(db_path),
                "show", "BTC_001"
            ],
            cwd=workspace_root,
            capture_output=True,
            text=True
        )
        
        # Then check the order
        result2 = subprocess.run(
            [
                "python", "scripts/order_manager.py",
                "--db", str(db_path),
                "list"
            ],
            cwd=workspace_root,
            capture_output=True,
            text=True
        )
        
        # Cancel the order
        result3 = subprocess.run(
            [
                "python", "scripts/order_manager.py",
                "--db", str(db_path),
                "cancel", "order_002"
            ],
            cwd=workspace_root,
            capture_output=True,
            text=True
        )
        
        print(result3.stdout)
        assert result3.returncode == 0, f"Cancel failed: {result3.stderr}"
        assert "cancelled" in result3.stdout, "Cancellation not confirmed"
        print("✓ Workflow: Check and modify order successful")
        
        # Test 8: Workflow - Force exit
        print("\n[8] Testing Workflow - Force Exit Position")
        print("-" * 70)
        
        result = subprocess.run(
            [
                "python", "scripts/order_manager.py",
                "--db", str(db_path),
                "force-exit", "BTC_001", "51000"
            ],
            cwd=workspace_root,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        assert result.returncode == 0, f"Force exit failed: {result.stderr}"
        assert "51000" in result.stdout, "Exit price not shown"
        print("✓ Force exit command successful")
        
        # Verify position is closed
        result = subprocess.run(
            [
                "python", "scripts/position_status.py",
                "--db", str(db_path),
                "show", "BTC_001"
            ],
            cwd=workspace_root,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        assert "CLOSED" in result.stdout, "Position should be closed"
        print("✓ Position verified as closed")
        
        print("\n" + "=" * 70)
        print("ALL OPERATIONAL TOOLS INTEGRATION TESTS PASSED ✓")
        print("=" * 70)


if __name__ == "__main__":
    test_operational_tools_integration()
