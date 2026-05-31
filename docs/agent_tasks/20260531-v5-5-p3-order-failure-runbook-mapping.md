# V5.5-P3 Order Failure Runbook Mapping Handoff

## Summary

V5.5-P3 maps the six V5.5-P2 order lifecycle failure fixtures to manual runbook decisions and required audit evidence. This remains review-only metadata for operator inspection and does not execute runbooks, write audit rows, connect brokers, store credentials, read accounts, or submit/cancel/modify orders.

## Added

- Added `TradeExecutionGatewayService.order_failure_runbook_mapping()`.
- Added `GET /api/trade-execution-gateway/order-failure-runbook-mapping`.
- Extended gateway capabilities and review gates with `order_failure_runbook_mapping_review`.
- Updated the dashboard with `Failure Runbook Mapping` and `Runbook Mapping Safety` cards.
- Added backend tests and API contract coverage for mapping status, evidence fields, hashes, and safety flags.

## Mapping Coverage

The mapping covers:

- `broker_rejected_order_preview` -> reject preview and record reason.
- `partial_fill_preview` -> reduce or cancel preview.
- `stale_market_data_before_confirmation` -> expire confirmation and refresh market data.
- `manual_confirmation_expired` -> require a new confirmation.
- `risk_gate_changed_after_preview` -> discard preview and recompute risk.
- `limit_down_sell_blocked` -> block sell and escalate risk review.

## Safety Boundary

V5.5-P3 must preserve:

- `can_execute_runbook_now=false`
- `can_record_audit_now=false`
- `can_submit_order_now=false`
- `writes_database_now=false`
- `executes_runbook_now=false`
- `connects_broker=false`
- `requires_credentials=false`
- `live_trading_enabled=false`

No broker adapter, order endpoint, credential surface, account read, database persistence, migration, or screen control was added.

## Validation

Targeted backend validation:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_trade_execution_gateway.py backend\tests\test_api_contracts.py backend\tests\test_safety.py -q
```

Result: `29 passed`.

## Next Step

V5.5-P4 can design the disabled audit ledger storage plan for these mapping records. It should still avoid migrations, table creation, audit-row persistence, broker connectivity, credentials, account reads, orders, and screen control.
