# V4.0-P3 Handoff: Realtime Cycle Audit History

## Scope

V4.0-P3 makes scheduler-safe realtime cycles auditable:

1. Persist every `realtime-cycle` run into `realtime_cycle_runs`.
2. Expose recent/latest cycle evidence through read-only API.
3. Display recent run history in the V4.0 dashboard.

This is still evidence for monitoring, replay, and review. It does not trigger trades, broker operations, screen clicks, or credential access.

## Runtime Paths

- `POST /api/realtime/cycle?symbols=SZ002081,SZ002115&refresh_limit=20&sync_limit=100&replay_limit=100`
- `GET /api/realtime/cycles?limit=20`
- `GET /api/realtime/cycles/latest`
- `backend/scripts/automation_loop.py --mode realtime-cycle --symbols SZ002081,SZ002115 --limit 20`

## Persisted Evidence

`realtime_cycle_runs` stores:

- status
- symbols
- provider
- refresh status
- monitoring session id
- refreshed count
- failed refresh count
- created alert count
- replay event count
- fallback-required flag
- summary JSON
- step JSON
- review/simulation/live-trading safety flags

## Safety Boundary

- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`
- no broker/order/credential/screen-click/live-trading route
- no API shell execution
- no fake realtime prices when providers are disabled

## Next Step

V4.0-P4 should wire a documented automation cadence for `realtime-cycle`, with operator-facing runbook instructions and a pause/disable posture. After that, V4.5 screen read-only monitoring can start from a stable evidence layer.
