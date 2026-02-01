from decimal import Decimal

from trading.order_state import OrderStateMachine


def test_entry_fill_initializes_position():
    osm = OrderStateMachine()
    osm.place_entry(order_id="o1", price=Decimal('100'), qty=Decimal('1'))
    osm.on_fill(order_id="o1", filled_qty=Decimal('1'), fill_price=Decimal('100'))
    assert osm.position is not None
    assert osm.position.entry_price == Decimal('100')
    assert osm.position.qty_filled == Decimal('1')


def test_trade_triggers_stop_placement_and_ratcheting():
    osm = OrderStateMachine()
    osm.place_entry(order_id="o2", price=Decimal('50'), qty=Decimal('2'))
    osm.on_fill(order_id="o2", filled_qty=Decimal('2'), fill_price=Decimal('50'))

    # first trade above entry should set initial stop
    should_replace, stop = osm.on_trade(last_trade_price=Decimal('51'), trail_pct=Decimal('0.02'), stop_limit_buffer_pct=Decimal('0.005'), min_ratchet=Decimal('0'))
    assert should_replace is True
    assert stop is not None

    # small trade not exceeding min_ratchet shouldn't replace
    should_replace2, _ = osm.on_trade(last_trade_price=Decimal('51.1'), trail_pct=Decimal('0.02'), stop_limit_buffer_pct=Decimal('0.005'), min_ratchet=Decimal('0.1'))
    assert should_replace2 is False


def test_stop_timeout_replacement_makes_aggressive():
    osm = OrderStateMachine()
    osm.place_entry(order_id="o3", price=Decimal('10'), qty=Decimal('1'))
    osm.on_fill(order_id="o3", filled_qty=Decimal('1'), fill_price=Decimal('10'))

    osm.on_trade(last_trade_price=Decimal('12'), trail_pct=Decimal('0.1'), stop_limit_buffer_pct=Decimal('0.01'), min_ratchet=Decimal('0'))
    prev_trigger = osm.position.current_stop_trigger

    new_trigger, new_limit = osm.stop_timeout_replacement(aggressive_price_delta_pct=Decimal('0.02'))
    assert new_trigger >= prev_trigger
    assert new_limit <= new_trigger
