# V4.0-P4 Handoff: Realtime Scheduler Runbook

## Scope

V4.0-P4 exposes scheduler/runbook metadata for the realtime cycle without enabling live automation by default.

The system now documents:

- recommended `realtime-cycle` cadence
- CLI commands
- pause controls
- degradation behavior
- forbidden actions
- dashboard visibility

## Runtime Paths

- `GET /api/realtime/scheduler-plan`
- `POST /api/realtime/cycle`
- `GET /api/realtime/cycles`
- `GET /api/realtime/provider-health`

## Recommended Cadence

Workday trading hours:

- 10:00: morning momentum and provider health check
- 13:00: midday trend persistence check
- 16:00: post-market replay and alert audit

Non-trading days:

- 20:00: off-hours candidate discovery using lower-risk `potential` mode

## Safe Commands

Run from the project root:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\automation_loop.py --mode realtime-cycle --symbols SZ002081,SZ002115 --limit 20 --max-cycles 1
backend\.venv\Scripts\python.exe backend\scripts\automation_loop.py --mode realtime-refresh --symbols SZ002081,SZ002115 --limit 20 --max-cycles 1
backend\.venv\Scripts\python.exe backend\scripts\automation_loop.py --mode realtime-monitoring-sync --limit 100 --max-cycles 1
```

## Pause Controls

- Pause the Codex/OS automation that calls `realtime-cycle`.
- Keep `REALTIME_PROVIDER=disabled` until an authorized realtime provider is configured.
- Review `/api/realtime/provider-health` and `/api/realtime/cycles/latest` before resuming.

## Degradation Rules

- `fallback_required` means `review_required`, not `realtime_ok`.
- Disabled/unconfigured providers must not write fake realtime prices.
- Monitoring alerts are review evidence only and never trigger broker/order actions.

## Safety Boundary

- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`
- no backend endpoint creates recurring jobs automatically
- no broker/order/credential/screen-click/live-trading route

## Next Step

V4.0-P5 can optionally create a reviewed Codex app automation proposal for `realtime-cycle`, or the project can move into V4.5 screen read-only monitoring after the user confirms scheduler behavior.
