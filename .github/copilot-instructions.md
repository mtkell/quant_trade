# Copilot Instructions — Coinbase Spot Trading Engine (5m, Limit Entry, Dynamic Trailing Exit)

## Overview
This repository implements a real-time trading system for Coinbase Spot markets using:
- 5-minute OHLCV candles
- Multi-indicator entry confirmation
- Limit buy entries
- Synthetic dynamic trailing exit via stop-limit cancel/replace
- Persistent state and restart reconciliation

## Non-Negotiable Invariants
- Spot-only; no leverage/derivatives.
- No market orders unless explicitly requested.
- Entries: limit buy only.
- Exits: trailing stop only (no indicator-driven exits).
- Stops must never loosen (ratchet upward only).
- No exits before entry fill confirmation (partial fills count as positions).
- Must reconcile open orders and position state after restart; no orphaned orders.

## Signal Timing
- Entry signal evaluation occurs only on 5-minute candle close.
- Trailing updates occur on last-trade updates or periodic timer.

## Entry Logic
- Apply higher-timeframe regime filter; if it fails, HOLD.
- BUY requires >=2 of 3 confirmations (RSI rebound, MACD histogram positive flip, price above VWAP/fast EMA).
- If BUY, place limit order and cancel if not filled within max_entry_wait_candles.

## Trailing Exit Logic
State per position:
- entry_price, qty_filled, highest_price_since_entry
- current_stop_trigger, current_stop_limit, stop_order_id

Compute:
- highest = max(highest, last_trade_price)
- new_trigger = highest * (1 - trail_pct)
- new_limit   = new_trigger * (1 - stop_limit_buffer_pct)

Ratchet-only replace:
- Replace only if new_trigger > current_stop_trigger * (1 + min_ratchet)
- Cancel old stop then place new stop-limit for remaining quantity

Stop failure handling:
- If stop triggers but is not filling within stop_timeout_seconds,
  cancel and replace with more aggressive pricing.
  Never lower the stop trigger.

## Design Expectations
- Use explicit order state machine with clear transitions.
- Use typed models for state and persistence.
- Implement restart-safe reconciliation.
- Provide unit tests for trailing ratchet behavior and state transitions.

## What Copilot Should Produce
- Minimal, deterministic logic.
- Clear separation between market data, strategy, execution, and state.
- Structured logging at each state transition and order event.
- Tests whenever logic changes.

## What Copilot Must Not Produce
- Market orders by default.
- Indicator-driven SELL exits.
- Stops that move downward.
- Exit orders created before entry is filled.
- Code that ignores partial fills or restart reconciliation.