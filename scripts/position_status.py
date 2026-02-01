#!/usr/bin/env python
"""Position status CLI: query open positions and orders from the database.

Usage:
    python scripts/position_status.py --db state.db list
    python scripts/position_status.py --db state.db show <position_id>
"""
import argparse
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trading.persistence_sqlite import SQLitePersistence
from trading.position import PositionState


def format_decimal(d, decimals=2):
    """Format decimal for display."""
    return f"{d:.{decimals}f}"


def list_positions(persistence):
    """List all open positions."""
    position_ids = persistence.list_positions()
    
    if not position_ids:
        print("No open positions")
        return
    
    print(f"\n{'Position ID':<20} {'Qty':<12} {'Entry Price':<15} {'Highest':<15} {'Stop Trigger':<15} {'Status':<10}")
    print("-" * 90)
    
    for pos_id in position_ids:
        pos = persistence.load_position(pos_id)
        if pos:
            status = "OPEN" if pos.qty_filled > 0 else "CLOSED"
            print(
                f"{pos_id:<20} "
                f"{format_decimal(pos.qty_filled, 4):<12} "
                f"{format_decimal(pos.entry_price, 2):<15} "
                f"{format_decimal(pos.highest_price_since_entry, 2):<15} "
                f"{format_decimal(pos.current_stop_trigger or Decimal('0'), 2):<15} "
                f"{status:<10}"
            )


def show_position(persistence, position_id):
    """Show detailed position info."""
    pos = persistence.load_position(position_id)
    
    if not pos:
        print(f"Position not found: {position_id}")
        return
    
    print(f"\n=== Position: {position_id} ===")
    print(f"Status: {'OPEN' if pos.qty_filled > 0 else 'CLOSED'}")
    print(f"Entry Price: ${format_decimal(pos.entry_price, 2)}")
    print(f"Qty Filled: {format_decimal(pos.qty_filled, 4)}")
    print(f"Highest Price: ${format_decimal(pos.highest_price_since_entry, 2)}")
    print(f"Trailing Stop Trigger: ${format_decimal(pos.current_stop_trigger or Decimal('0'), 2)}")
    print(f"Stop Limit: ${format_decimal(pos.current_stop_limit or Decimal('0'), 2)}")
    print(f"Stop Order ID: {pos.stop_order_id or '(none)'}")
    
    # Show related orders
    orders = persistence.list_orders(position_id=position_id)
    if orders:
        print(f"\nRelated Orders ({len(orders)}):")
        print(f"{'Order ID':<20} {'Type':<10} {'State':<10} {'Created':<20}")
        print("-" * 60)
        for order in orders:
            order_id = order.get('order_id', 'unknown')
            order_type = order.get('type', 'unknown')
            state = order.get('state', 'unknown')
            created = order.get('created_at', 'N/A')
            print(f"{order_id:<20} {order_type:<10} {state:<10} {created:<20}")


def main():
    parser = argparse.ArgumentParser(description="Position status CLI")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    
    sub = parser.add_subparsers(dest="cmd")
    
    sub.add_parser("list")
    show = sub.add_parser("show")
    show.add_argument("position_id")
    
    args = parser.parse_args()
    
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)
    
    persistence = SQLitePersistence(db_path)
    
    if args.cmd == "list":
        list_positions(persistence)
    elif args.cmd == "show":
        show_position(persistence, args.position_id)
    else:
        parser.print_help()
    
    persistence.close()


if __name__ == "__main__":
    main()
