from decimal import Decimal
from pathlib import Path

from trading.persistence_sqlite import SQLitePersistence
from trading.position import PositionState


def test_multiple_positions_and_order_history(tmp_path: Path):
    db = tmp_path / "multi.db"
    p = SQLitePersistence(db)

    pos1 = PositionState(entry_price=Decimal('100'), qty_filled=Decimal('1'), highest_price_since_entry=Decimal('110'))
    pos2 = PositionState(entry_price=Decimal('200'), qty_filled=Decimal('2'), highest_price_since_entry=Decimal('210'))

    p.save_position(pos1, position_id="pos1")
    p.save_position(pos2, position_id="pos2")

    ids = p.list_positions()
    assert "pos1" in ids and "pos2" in ids

    # add orders
    order_a = {"price": "100", "qty": "1"}
    order_b = {"price": "101", "qty": "0.5"}
    p.save_order(order_id="oA", position_id="pos1", order_dict=order_a, state="open")
    p.save_order(order_id="oB", position_id="pos1", order_dict=order_b, state="filled")

    orders = p.list_orders("pos1")
    assert any(o.get("price") == "100" for o in orders)
    assert any(o.get("price") == "101" for o in orders)

    fetched = p.get_order("oA")
    assert fetched is not None
    assert fetched["order_id"] == "oA"

    p.close()
