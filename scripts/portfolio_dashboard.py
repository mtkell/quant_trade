#!/usr/bin/env python
"""Portfolio dashboard CLI: view portfolio status and multi-pair metrics."""
import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trading.persistence_sqlite import SQLitePersistence


def format_currency(amount, decimals=2):
    """Format amount as currency."""
    return f"${amount:,.{decimals}f}"


def format_pct(pct, decimals=2):
    """Format percentage."""
    color = "+" if pct >= 0 else "-"
    return f"{color}{abs(pct):.{decimals}f}%"


def portfolio_summary(persistence):
    """Show portfolio-level summary."""
    position_ids = persistence.list_positions()
    
    if not position_ids:
        print("No positions found")
        return
    
    total_capital = Decimal('100000')  # Would come from config
    total_entry_capital = Decimal('0')
    total_unrealized_pnl = Decimal('0')
    total_realized_pnl = Decimal('0')
    active_count = 0
    closed_count = 0
    
    print("\n" + "=" * 90)
    print("PORTFOLIO DASHBOARD")
    print("=" * 90)
    
    for pos_id in position_ids:
        pos = persistence.load_position(pos_id)
        if pos and pos.qty_filled > 0:
            active_count += 1
            entry_notional = pos.entry_price * pos.qty_filled
            total_entry_capital += entry_notional
        else:
            closed_count += 1
    
    available_capital = total_capital - total_entry_capital
    deployed_pct = (total_entry_capital / total_capital * 100) if total_capital > 0 else 0
    
    print(f"\nCapital Allocation:")
    print(f"  Total Capital:      {format_currency(total_capital)}")
    print(f"  Deployed Capital:   {format_currency(total_entry_capital)} ({deployed_pct:.1f}%)")
    print(f"  Available Capital:  {format_currency(available_capital)}")
    
    print(f"\nPosition Tracking:")
    print(f"  Active Positions:   {active_count}")
    print(f"  Closed Positions:   {closed_count}")
    
    print(f"\nPairs Status:")
    print(f"{'Product':<15} {'Qty':<12} {'Entry Price':<15} {'Highest':<15} {'Stop':<15} {'Status':<10}")
    print("-" * 90)
    
    for pos_id in position_ids:
        pos = persistence.load_position(pos_id)
        if pos:
            status = "OPEN" if pos.qty_filled > 0 else "CLOSED"
            # Extract product from position_id (e.g., "BTC_001" → "BTC-USD")
            product = pos_id.replace("_001", "-USD").replace("_", "-")
            print(
                f"{product:<15} "
                f"{float(pos.qty_filled):<12.4f} "
                f"{float(pos.entry_price):<15.2f} "
                f"{float(pos.highest_price_since_entry):<15.2f} "
                f"{float(pos.current_stop_trigger or 0):<15.2f} "
                f"{status:<10}"
            )


def position_concentration(persistence):
    """Show position concentration analysis."""
    position_ids = persistence.list_positions()
    
    if not position_ids:
        print("No positions found")
        return
    
    positions_by_size = []
    total_capital = Decimal('100000')
    
    for pos_id in position_ids:
        pos = persistence.load_position(pos_id)
        if pos and pos.qty_filled > 0:
            notional = pos.entry_price * pos.qty_filled
            pct_of_capital = (notional / total_capital * 100) if total_capital > 0 else 0
            positions_by_size.append((pos_id, notional, pct_of_capital))
    
    # Sort by size
    positions_by_size.sort(key=lambda x: x[1], reverse=True)
    
    print("\n" + "=" * 70)
    print("POSITION CONCENTRATION")
    print("=" * 70)
    
    cumulative_pct = 0
    print(f"\n{'Rank':<6} {'Position':<20} {'Size':<15} {'% Capital':<15} {'Cumulative':<15}")
    print("-" * 70)
    
    for idx, (pos_id, notional, pct) in enumerate(positions_by_size, 1):
        cumulative_pct += pct
        print(
            f"{idx:<6} "
            f"{pos_id:<20} "
            f"{format_currency(notional):<15} "
            f"{pct:>6.2f}%{' '*6} "
            f"{cumulative_pct:>6.2f}%"
        )
    
    if positions_by_size:
        top_3_pct = sum(pct for _, _, pct in positions_by_size[:3])
        print(f"\nTop 3 Concentration: {top_3_pct:.1f}%")
        largest_pct = positions_by_size[0][2]
        print(f"Largest Position: {largest_pct:.1f}%")


def pair_comparison(persistence):
    """Compare performance across pairs."""
    position_ids = persistence.list_positions()
    
    if not position_ids:
        print("No positions found")
        return
    
    pairs_data = {}
    
    for pos_id in position_ids:
        pos = persistence.load_position(pos_id)
        if pos:
            # Extract product from position_id
            product = pos_id.split("_")[0]
            if product not in pairs_data:
                pairs_data[product] = {
                    "positions": [],
                    "total_entry": Decimal('0'),
                    "total_current_price": Decimal('0'),
                }
            
            pairs_data[product]["positions"].append(pos)
            if pos.qty_filled > 0:
                entry_notional = pos.entry_price * pos.qty_filled
                pairs_data[product]["total_entry"] += entry_notional
    
    print("\n" + "=" * 100)
    print("PAIR COMPARISON")
    print("=" * 100)
    
    print(f"\n{'Pair':<15} {'Positions':<15} {'Capital':<15} {'Avg Entry':<15} {'Status':<20}")
    print("-" * 100)
    
    for product in sorted(pairs_data.keys()):
        data = pairs_data[product]
        pos_count = len(data["positions"])
        avg_entry = data["total_entry"] / pos_count if pos_count > 0 else Decimal('0')
        active_count = sum(1 for p in data["positions"] if p.qty_filled > 0)
        status = f"{active_count} active, {pos_count - active_count} closed"
        
        print(
            f"{product:<15} "
            f"{pos_count:<15} "
            f"{format_currency(data['total_entry']):<15} "
            f"{format_currency(avg_entry):<15} "
            f"{status:<20}"
        )


def main():
    parser = argparse.ArgumentParser(description="Portfolio dashboard CLI")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("summary")
    sub.add_parser("concentration")
    sub.add_parser("pairs")
    
    args = parser.parse_args()
    
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)
    
    persistence = SQLitePersistence(db_path)
    
    # Import Decimal here to avoid circular imports
    from decimal import Decimal
    globals()['Decimal'] = Decimal
    
    if args.cmd == "summary":
        portfolio_summary(persistence)
    elif args.cmd == "concentration":
        position_concentration(persistence)
    elif args.cmd == "pairs":
        pair_comparison(persistence)
    else:
        parser.print_help()
    
    persistence.close()


if __name__ == "__main__":
    main()
