# V5.0-P0 Trade Execution Gateway Review Scaffold

## Summary

V5.0-P0 starts the Trade Execution Gateway as review-only architecture metadata. It does not connect to brokers, store credentials, read account funds, place/cancel/modify real trades, click trading software, or enable live trading.

## Added Surface

- `GET /api/trade-execution-gateway/capabilities`
- `GET /api/trade-execution-gateway/review-gates`
- `TradeExecutionGatewayService`
- Dashboard panel: `V5.0 Trade Execution Gateway`
- Release checklist V5.0-P0 entries
- Cockpit skill V5.0-P0 boundary notes

## Current Behavior

The gateway reports:

- `gateway_enabled=false`
- `execution_enabled=false`
- `real_money_execution_enabled=false`
- `broker_adapter_enabled=false`
- `credential_storage_enabled=false`
- `screen_click_trading_enabled=false`
- `live_trading_enabled=false`
- `review_only=true`
- `simulation_only=true`

The first review gates require future manual-confirmation, risk-gate, audit-ledger, and rollback contracts before any real-money integration can even be reviewed.

## Forbidden In V5.0-P0

- Broker login or broker API integration.
- Credential input, storage, or account access.
- Real trade placement, cancellation, modification, or live position changes.
- Screen-click trading, OCR execution, keyboard input, or trading-client control.
- Any change to `settings.enable_live_trading` or `/health.live_trading_enabled=false`.

## Validation Commands

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_trade_execution_gateway.py backend\tests\test_api_contracts.py backend\tests\test_safety.py -q
backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts
Set-Location backend; .\.venv\Scripts\python.exe -m pytest -q
Set-Location frontend; npx vue-tsc --noEmit
Set-Location frontend; npx vite build
git diff --check
codegraph status
```

## Next Step

V5.0-P1 can design the manual confirmation contract and immutable audit evidence schema as review-only metadata. Do not add broker adapters or live execution.
