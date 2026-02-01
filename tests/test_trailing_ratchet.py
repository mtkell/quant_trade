from decimal import Decimal

from trading.position import PositionState


def test_initial_stop_set():
    pos = PositionState(entry_price=Decimal('100'), qty_filled=Decimal('1'), highest_price_since_entry=Decimal('100'))
    changed = pos.ratchet_stop(last_trade_price=Decimal('101'), trail_pct=Decimal('0.02'), stop_limit_buffer_pct=Decimal('0.005'), min_ratchet=Decimal('0'))
    assert changed is True
    expected_trigger = pos.compute_new_stop(Decimal('0.02'), Decimal('0.005'))[0]
    assert pos.current_stop_trigger == expected_trigger


def test_min_ratchet_gating():
    pos = PositionState(entry_price=Decimal('100'), qty_filled=Decimal('1'), highest_price_since_entry=Decimal('120'))
    # initialize
    pos.ratchet_stop(last_trade_price=Decimal('120'), trail_pct=Decimal('0.1'), stop_limit_buffer_pct=Decimal('0.01'), min_ratchet=Decimal('0'))
    current = pos.current_stop_trigger

    # small increase that is below min_ratchet threshold
    # set min_ratchet to 1% and produce a new trigger that's only 0.5% higher
    pos.highest_price_since_entry = Decimal('121')
    changed = pos.ratchet_stop(last_trade_price=Decimal('121'), trail_pct=Decimal('0.1'), stop_limit_buffer_pct=Decimal('0.01'), min_ratchet=Decimal('0.01'))
    assert changed is False
    assert pos.current_stop_trigger == current

    # now a larger increase exceeding min_ratchet
    pos.highest_price_since_entry = Decimal('130')
    changed = pos.ratchet_stop(last_trade_price=Decimal('130'), trail_pct=Decimal('0.1'), stop_limit_buffer_pct=Decimal('0.01'), min_ratchet=Decimal('0.01'))
    assert changed is True
    assert pos.current_stop_trigger > current


def test_never_lower():
    pos = PositionState(entry_price=Decimal('100'), qty_filled=Decimal('1'), highest_price_since_entry=Decimal('150'))
    pos.ratchet_stop(last_trade_price=Decimal('150'), trail_pct=Decimal('0.1'), stop_limit_buffer_pct=Decimal('0.02'), min_ratchet=Decimal('0'))
    current = pos.current_stop_trigger

    # simulate a drop in price; highest should not decrease and stop should not move down
    changed = pos.ratchet_stop(last_trade_price=Decimal('140'), trail_pct=Decimal('0.1'), stop_limit_buffer_pct=Decimal('0.02'), min_ratchet=Decimal('0'))
    assert changed is False
    assert pos.current_stop_trigger == current


def test_new_limit_calculation():
    pos = PositionState(entry_price=Decimal('200'), qty_filled=Decimal('2'), highest_price_since_entry=Decimal('250'))
    pos.ratchet_stop(last_trade_price=Decimal('255'), trail_pct=Decimal('0.05'), stop_limit_buffer_pct=Decimal('0.01'), min_ratchet=Decimal('0'))
    new_trigger, new_limit = pos.compute_new_stop(Decimal('0.05'), Decimal('0.01'))
    assert pos.current_stop_limit == new_limit
    assert pos.current_stop_trigger == new_trigger
