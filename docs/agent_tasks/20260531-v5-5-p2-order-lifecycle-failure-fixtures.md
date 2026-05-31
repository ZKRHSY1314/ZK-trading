# V5.5-P2 Order Lifecycle Failure Fixtures Handoff

## Objective
Define review-only order lifecycle failure-mode fixtures on top of the V5.5 broker adapter contract verifier, without implementing an order lifecycle engine or any broker connectivity.

## Completed Scope
- Added `TradeExecutionGatewayService.order_lifecycle_failure_fixtures()`.
- Added API endpoint:
  - `GET /api/trade-execution-gateway/order-lifecycle-failure-fixtures`
- Extended capabilities and review gates with `order_lifecycle_failure_fixture_review`.
- Updated the V5 dashboard to show fixture suite, fixture state, per-fixture expected statuses, and no-submit/no-real-replay evidence.
- Updated backend tests and API contract tests for the failure fixture report.
- Updated release checklist with V5.5-P2 requirements.

## Fixture Suite
- `broker_rejected_order_preview`
- `partial_fill_preview`
- `stale_market_data_before_confirmation`
- `manual_confirmation_expired`
- `risk_gate_changed_after_preview`
- `limit_down_sell_blocked`

## Safety Boundary
V5.5-P2 is review-only metadata. It must not instantiate adapters, connect brokers, read accounts/funds/positions, store credentials, submit/cancel/modify orders, replay fixtures as real orders, click/type trading software, write env, write database rows, or enable live trading.

Required false flags:
- `can_replay_as_real_order=false`
- `can_submit_order_now=false`
- `can_cancel_order_now=false`
- `can_modify_order_now=false`
- `requires_broker_connection=false`
- `requires_credentials=false`
- `order_lifecycle_engine_implemented=false`
- `live_trading_enabled=false`

## Suggested Next Step
V5.5-P3 can map these failure fixtures to manual runbook decisions and required audit evidence. It should still avoid real broker connectivity, credentials, account reads, orders, database writes, and screen control.
