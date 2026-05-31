# V4.0-P1 Handoff: Realtime Refresh and Monitoring Bridge

## Scope

V4.0-P1 connects the V4.0 realtime event foundation to the monitoring alert surface:

1. Refresh configured realtime providers into `realtime_market_events`.
2. Record provider health, degradation, and fallback requirements.
3. Sync stored realtime events into review-only `monitoring_events` and `monitoring_alerts`.
4. Expose the loop in API, CLI, tests, and the V4.0 dashboard.

The default environment has no external realtime API key. In that state refresh must return disabled/needs_config/fallback-required evidence and must not invent realtime prices.

## Safety Boundary

- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`
- No broker API.
- No order, cancel, position, account, credential, screen-click, OCR, or live trading endpoint.
- Monitoring alerts are evidence for human review and simulation planning only.

## New/Changed Runtime Paths

- `POST /api/realtime/refresh?symbols=SZ002081,SZ002115&limit=20`
- `POST /api/realtime/monitoring-sync?limit=100`
- `GET /api/realtime/events?symbol=&limit=`
- `GET /api/monitoring/alerts?limit=`
- `backend/scripts/automation_loop.py --mode realtime-refresh --symbols SZ002081,SZ002115`
- `backend/scripts/automation_loop.py --mode realtime-monitoring-sync`

## Alert Rules

- `realtime_price_jump`: same-symbol adjacent persisted realtime events move at least 3%.
- `realtime_stale_data`: latency exceeds 60 seconds or quality is `stale_realtime`.
- `realtime_provider_degraded`: persisted provider health is degraded or fallback-required.

Every alert payload must include:

- `source_event_id`
- `quality_status`
- `latency_ms`
- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`

## Deduping

- One realtime event can create at most one monitoring event.
- One symbol/event timestamp/alert type can create at most one monitoring alert.
- Repeated syncs should be idempotent.

## Validation Commands

Run from `C:\Users\lenovo\Desktop\A股记录\ai_trading_system`:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_realtime_market.py -q
backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts
backend\.venv\Scripts\python.exe -m pytest -q
backend\.venv\Scripts\python.exe -m pip check
cd frontend; npm run type-check; npm run build; npm audit --audit-level=moderate
git diff --check
codegraph status
```

## Next Small Step

V4.0-P2 can add a scheduler-friendly realtime refresh runbook and richer signal replay summaries, still without broker/order/screen-click capabilities.
