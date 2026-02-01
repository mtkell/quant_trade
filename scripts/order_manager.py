#!/usr/bin/env python
"""Order management CLI: cancel/replace orders, force exits.

Usage:
    python scripts/order_manager.py --db state.db list
    python scripts/order_manager.py --db state.db cancel <order_id>
    python scripts/order_manager.py --db state.db force-exit <position_id> <exit_price>
"""
import argparse
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trading.persistence_sqlite import SQLitePersistence


def list_orders(persistence):
    """List all orders grouped by position."""
    position_ids = persistence.list_positions()
    
    if not position_ids:
        print("No positions found")
        return
    
    total_orders = 0
    for pos_id in position_ids:
        pos = persistence.load_position(pos_id)
        orders = persistence.list_orders(position_id=pos_id)
        if orders:
            print(f"\n=== Position {pos_id} ===")
            print(f"{'Order ID':<20} {'Type':<12} {'State':<10} {'Price':<12} {'Qty':<10}")
            print("-" * 65)
            for order in orders:
                order_id = order.get('order_id', 'unknown')
                order_type = order.get('type', 'unknown')
                state = order.get('state', 'unknown')
                price = order.get('price', 'N/A')
                qty = order.get('qty', 'N/A')
                print(f"{order_id:<20} {order_type:<12} {state:<10} {price:<12} {qty:<10}")
                total_orders += 1
    
    print(f"\nTotal orders: {total_orders}")


def cancel_order(persistence, order_id):
    """Mark an order as cancelled (for tracking; actual cancellation via API)."""
    # Get the order to find its position
    all_positions = persistence.list_positions()
    target_position = None
    
    for pos_id in all_positions:
        orders = persistence.list_orders(position_id=pos_id)
        for order in orders:
            if order.get('order_id') == order_id:
                target_position = pos_id
                break
    
    if not target_position:
        print(f"Order not found: {order_id}")
        return
    
    # Update order state to cancelled
    cur = sqlite3.connect(str(persistence.path)).cursor()
    cur.execute(
        "UPDATE orders SET state = ? WHERE order_id = ?",
        ("cancelled", order_id)
    )
    cur.connection.commit()
    cur.connection.close()
    
    print(f"Order marked as cancelled: {order_id}")
    print("Note: Use Coinbase API to actually cancel the order on the exchange")


def force_exit(persistence, position_id, exit_price):
    """Record a forced exit for a position (e.g., manual sell)."""
    pos = persistence.load_position(position_id)
    
    if not pos:
        print(f"Position not found: {position_id}")
        return
    
    if pos.qty_filled <= 0:
        print(f"Position is already closed: {position_id}")
        return
    
    exit_price_dec = Decimal(str(exit_price))
    qty_at_exit = pos.qty_filled
    
    # Create exit order record
    exit_order = {
        "type": "force_sell",
        "side": "sell",
        "price": str(exit_price_dec),
        "qty": str(qty_at_exit),
        "state": "filled",
        "created_at": "",
    }
    
    persistence.save_order(f"{position_id}_force_exit", position_id, exit_order, "filled")
    
    # Calculate P&L before closing position
    realized_pnl = (exit_price_dec - pos.entry_price) * qty_at_exit
    realized_pnl_percent = (realized_pnl / (pos.entry_price * qty_at_exit) * 100) if pos.entry_price > 0 else Decimal('0')
    
    # Update position: mark as closed
    pos.qty_filled = Decimal('0')
    persistence.save_position(pos, position_id)
    
    print(f"Position {position_id} force-exited at ${exit_price_dec}")
    print(f"Entry: ${pos.entry_price}, Exit: ${exit_price_dec}")
    print(f"Realized P&L: ${realized_pnl} ({realized_pnl_percent:.2f}%)")


def main():
    parser = argparse.ArgumentParser(description="Order management CLI")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    
    sub = parser.add_subparsers(dest="cmd")
    
    sub.add_parser("list")
    
    cancel = sub.add_parser("cancel")
    cancel.add_argument("order_id")
    
    exit_cmd = sub.add_parser("force-exit")
    exit_cmd.add_argument("position_id")
    exit_cmd.add_argument("exit_price", type=float)
    
    args = parser.parse_args()
    
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)
    
    persistence = SQLitePersistence(db_path)
    
    if args.cmd == "list":
        list_orders(persistence)
    elif args.cmd == "cancel":
        cancel_order(persistence, args.order_id)
    elif args.cmd == "force-exit":
        force_exit(persistence, args.position_id, args.exit_price)
    else:
        parser.print_help()
    
    persistence.close()


if __name__ == "__main__":
    main()
