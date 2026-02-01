import os
from decimal import Decimal
from pathlib import Path

from trading.execution import InMemoryAdapter, FilePersistence, ExecutionEngine


STATE_FILE = Path(".test_state.json")


def teardown_function():
    try:
        STATE_FILE.unlink()
    except FileNotFoundError:
        pass


def test_full_flow_place_fill_persist_and_stop():
    adapter = InMemoryAdapter()
    persistence = FilePersistence(STATE_FILE)
    engine = ExecutionEngine(adapter=adapter, persistence=persistence)

    oid = engine.submit_entry(client_id="c1", price=Decimal('100'), qty=Decimal('1'))

    # simulate fill
    engine.handle_fill(order_id=oid, filled_qty=Decimal('1'), fill_price=Decimal('100'))

    # position persisted
    assert STATE_FILE.exists()

    # initial stop should have been placed in adapter and persisted
    pos = engine.osm.position
    assert pos is not None
    assert pos.stop_order_id in adapter.orders


def test_on_trade_ratcheting_replaces_stop():
    adapter = InMemoryAdapter()
    persistence = FilePersistence(STATE_FILE)
    engine = ExecutionEngine(adapter=adapter, persistence=persistence)

    oid = engine.submit_entry(client_id="c2", price=Decimal('10'), qty=Decimal('1'))
    engine.handle_fill(order_id=oid, filled_qty=Decimal('1'), fill_price=Decimal('10'))

    old_stop = engine.osm.position.stop_order_id
    engine.on_trade(last_trade_price=Decimal('12'), trail_pct=Decimal('0.1'), stop_limit_buffer_pct=Decimal('0.01'), min_ratchet=Decimal('0'))
    new_stop = engine.osm.position.stop_order_id
    assert new_stop != old_stop
    assert adapter.orders[old_stop]['state'] == 'cancelled'


def test_handle_stop_timeout_replaces_stop_and_persists():
    adapter = InMemoryAdapter()
    persistence = FilePersistence(STATE_FILE)
    engine = ExecutionEngine(adapter=adapter, persistence=persistence)

    oid = engine.submit_entry(client_id="c3", price=Decimal('20'), qty=Decimal('2'))
    engine.handle_fill(order_id=oid, filled_qty=Decimal('2'), fill_price=Decimal('20'))

    prev_stop = engine.osm.position.stop_order_id
    engine.handle_stop_timeout(aggressive_price_delta_pct=Decimal('0.03'))
    new_stop = engine.osm.position.stop_order_id
    assert new_stop != prev_stop
    assert adapter.orders[prev_stop]['state'] == 'cancelled'
    # verify persisted file updated
    assert STATE_FILE.exists()
