from decimal import Decimal
from pathlib import Path

from trading.execution import ExecutionEngine
from trading.execution import InMemoryAdapter
from trading.persistence_sqlite import SQLitePersistence


def test_reconciliation_preserves_existing_stop(tmp_path: Path):
    db = tmp_path / "state.db"
    adapter = InMemoryAdapter()
    persistence = SQLitePersistence(db)

    # First engine: submit entry and fill -> should place a stop
    engine1 = ExecutionEngine(adapter=adapter, persistence=persistence)
    oid = engine1.submit_entry(client_id="c1", price=Decimal('100'), qty=Decimal('1'))
    engine1.handle_fill(order_id=oid, filled_qty=Decimal('1'), fill_price=Decimal('100'))
    first_stop = engine1.osm.position.stop_order_id
    assert first_stop in adapter.orders

    # Restart: new engine with same adapter and persistence should detect stop exists and keep it
    engine2 = ExecutionEngine(adapter=adapter, persistence=persistence)
    assert engine2.osm.position is not None
    assert engine2.osm.position.stop_order_id == first_stop


def test_reconciliation_replaces_missing_stop(tmp_path: Path):
    db = tmp_path / "state2.db"
    adapter = InMemoryAdapter()
    persistence = SQLitePersistence(db)

    engine1 = ExecutionEngine(adapter=adapter, persistence=persistence)
    oid = engine1.submit_entry(client_id="c2", price=Decimal('50'), qty=Decimal('2'))
    engine1.handle_fill(order_id=oid, filled_qty=Decimal('2'), fill_price=Decimal('50'))
    first_stop = engine1.osm.position.stop_order_id
    assert first_stop in adapter.orders

    # simulate stop cancelled externally
    adapter.cancel_order(first_stop)

    # restart engine; it should detect stop missing/cancelled and place a replacement
    engine2 = ExecutionEngine(adapter=adapter, persistence=persistence)
    new_stop = engine2.osm.position.stop_order_id
    assert new_stop is not None
    assert new_stop != first_stop
    assert adapter.orders[new_stop]['state'] == 'open'
