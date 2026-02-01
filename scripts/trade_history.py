#!/usr/bin/env python
"""Trade history and P&L reporter.

Usage:
    python scripts/trade_history.py --db state.db summary
    python scripts/trade_history.py --db state.db list
    python scripts/trade_history.py --db state.db position <position_id>
"""
import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trading.persistence_sqlite import SQLitePersistence
from trading.pnl import Fill, calculate_pnl, aggregate_pnl


def get_fills_from_orders(persistence, position_id=None):
    """Extract fills from order records."""
    fills = []
    
    position_ids = persistence.list_positions()
    
    for pos_id in position_ids:
        if position_id and pos_id != position_id:
            continue
        
        orders = persistence.list_orders(position_id=pos_id)
        
        for order in orders:
            if order.get("state") not in ("filled", "partially_filled"):
                continue
            
            # Extract fill info
            try:
                price = Decimal(str(order.get("price", 0)))
                qty = Decimal(str(order.get("qty", 0)))
                side = "buy" if order.get("type") == "entry" else "sell"
                
                fill = Fill(
                    order_id=order.get('order_id', 'unknown'),
                    side=side,
                    price=price,
                    qty=qty,
                    timestamp=0  # Would be parsed from created_at if needed
                )
                fills.append(fill)
            except (ValueError, TypeError):
                continue
    
    return fills


def summary(persistence):
    """Show P&L summary across all positions."""
    position_ids = persistence.list_positions()
    
    if not position_ids:
        print("No positions found")
        return
    
    # Collect all entry and exit fills
    analyses = []
    
    for pos_id in position_ids:
        orders = persistence.list_orders(position_id=pos_id)
        
        # Find entry and exit fills
        entries = [o for o in orders if o.get("type") == "entry" and o.get("state") == "filled"]
        exits = [o for o in orders if o.get("type") in ("exit", "force_sell") and o.get("state") == "filled"]
        
        # Calculate P&L for each position
        for entry in entries:
            entry_price = Decimal(str(entry.get("price", 0)))
            entry_qty = Decimal(str(entry.get("qty", 0)))
            
            # Find matching exit
            exit_price = None
            exit_qty = None
            for exit_order in exits:
                exit_price = Decimal(str(exit_order.get("price", 0)))
                exit_qty = Decimal(str(exit_order.get("qty", 0)))
                break
            
            if entry_price > 0 and entry_qty > 0:
                analysis = calculate_pnl(
                    entry_price=entry_price,
                    entry_qty=entry_qty,
                    exit_price=exit_price,
                    exit_qty=exit_qty
                )
                analyses.append(analysis)
    
    if not analyses:
        print("No completed trades found")
        return
    
    agg = aggregate_pnl(analyses)
    
    print("\n=== Trading Summary ===")
    print(f"Total Trades: {agg['total_trades']}")
    print(f"Realized P&L: ${agg['total_realized_pnl']:.2f}")
    print(f"Unrealized P&L: ${agg['total_unrealized_pnl']:.2f}")
    print(f"Total P&L: ${agg['total_pnl']:.2f}")
    print(f"Win Rate: {agg['win_rate_percent']:.1f}%")
    print(f"Avg Return: {agg['avg_pnl_percent']:.2f}%")


def list_trades(persistence):
    """List all filled trades."""
    position_ids = persistence.list_positions()
    
    if not position_ids:
        print("No trades found")
        return
    
    entry_orders = []
    exit_orders = []
    
    for pos_id in position_ids:
        orders = persistence.list_orders(position_id=pos_id)
        for order in orders:
            if order.get("state") != "filled":
                continue
            
            if order.get("type") == "entry":
                entry_orders.append((pos_id, order))
            elif order.get("type") in ("exit", "force_sell"):
                exit_orders.append((pos_id, order))
    
    if not entry_orders:
        print("No trades found")
        return
    
    print("\n=== Entry Fills ===")
    print(f"{'Pos ID':<20} {'Order ID':<20} {'Price':<12} {'Qty':<10} {'Time':<20}")
    print("-" * 82)
    for pos_id, order in sorted(entry_orders, key=lambda x: x[1].get("created_at", "")):
        print(f"{pos_id:<20} {order['order_id']:<20} ${order.get('price', 'N/A'):<11} {order.get('qty', 'N/A'):<10} {order.get('created_at', 'N/A'):<20}")
    
    print("\n=== Exit Fills ===")
    print(f"{'Pos ID':<20} {'Order ID':<20} {'Price':<12} {'Qty':<10} {'Time':<20}")
    print("-" * 82)
    for pos_id, order in sorted(exit_orders, key=lambda x: x[1].get("created_at", "")):
        print(f"{pos_id:<20} {order['order_id']:<20} ${order.get('price', 'N/A'):<11} {order.get('qty', 'N/A'):<10} {order.get('created_at', 'N/A'):<20}")
    
    print(f"\nTotal entries: {len(entry_orders)}, Total exits: {len(exit_orders)}")


def position_history(persistence, position_id):
    """Show history for a single position."""
    pos = persistence.load_position(position_id)
    
    if not pos:
        print(f"Position not found: {position_id}")
        return
    
    orders = persistence.list_orders(position_id=position_id)
    
    print(f"\n=== Position {position_id} ===")
    print(f"Entry Price: ${pos.entry_price}")
    print(f"Qty Filled: {pos.qty_filled}")
    print(f"Highest Price: ${pos.highest_price_since_entry}")
    print(f"Current Stop: ${pos.current_stop_trigger}")
    
    # Calculate P&L if we have entry and exit
    entries = [o for o in orders if o.get("type") == "entry" and o.get("state") == "filled"]
    exits = [o for o in orders if o.get("type") in ("exit", "force_sell") and o.get("state") == "filled"]
    
    if entries and exits:
        entry_price = Decimal(str(entries[0].get("price", 0)))
        entry_qty = Decimal(str(entries[0].get("qty", 0)))
        exit_price = Decimal(str(exits[0].get("price", 0)))
        exit_qty = Decimal(str(exits[0].get("qty", 0)))
        
        if entry_price > 0 and entry_qty > 0:
            analysis = calculate_pnl(
                entry_price=entry_price,
                entry_qty=entry_qty,
                exit_price=exit_price,
                exit_qty=exit_qty
            )
            print(f"\nRealized P&L: ${analysis.realized_pnl}")
            print(f"Return: {analysis.pnl_percent:.2f}%")
    
    if orders:
        print(f"\n=== Orders ===")
        print(f"{'Order ID':<20} {'Type':<12} {'State':<10} {'Price':<12} {'Qty':<10}")
        print("-" * 65)
        for order in orders:
            order_id = order.get('order_id', 'unknown')
            print(f"{order_id:<20} {order.get('type', 'unknown'):<12} {order.get('state', 'unknown'):<10} {order.get('price', 'N/A'):<12} {order.get('qty', 'N/A'):<10}")


def main():
    parser = argparse.ArgumentParser(description="Trade history and P&L reporter")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    
    sub = parser.add_subparsers(dest="cmd")
    
    sub.add_parser("summary")
    sub.add_parser("list")
    
    pos_cmd = sub.add_parser("position")
    pos_cmd.add_argument("position_id")
    
    args = parser.parse_args()
    
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)
    
    persistence = SQLitePersistence(db_path)
    
    if args.cmd == "summary":
        summary(persistence)
    elif args.cmd == "list":
        list_trades(persistence)
    elif args.cmd == "position":
        position_history(persistence, args.position_id)
    else:
        parser.print_help()
    
    persistence.close()


if __name__ == "__main__":
    main()
