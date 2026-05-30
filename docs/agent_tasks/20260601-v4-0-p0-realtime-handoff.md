# V4.0-P0 Realtime Event Foundation Handoff

V4.0-P0 starts the high-timeliness market-data and event-driven foundation. It does not add live trading, broker access, screen-click trading, or order execution. The milestone is limited to second-level monitoring, alerts, simulation evidence, event replay, latency tracking, and data-quality visibility.

## Implemented Scope
- Rewrote the `a-share-trading-cockpit` Codex skill as readable UTF-8 Chinese/English guidance and added V3.5/V4.0 stage boundaries.
- Added disabled-by-default realtime provider abstraction with:
  - `asharehub` as the first external provider candidate when explicitly configured.
  - `akshare_fallback` as delayed fallback labeling, never reliable realtime.
  - `vnapi` and `joinquant_enterprise` listed as future provider candidates.
- Added realtime market event and provider-health storage.
- Added event ingestion with latency calculation, quality status, fallback flag, payload, and same-source same-symbol same-second dedupe.
- Added replay that regenerates simulation-only signals from stored realtime events.
- Added readonly API endpoints:
  - `GET /api/realtime/capabilities`
  - `GET /api/realtime/provider-health`
  - `GET /api/realtime/snapshot/{symbol}`
  - `GET /api/realtime/events`
  - `POST /api/realtime/replay`
- Added V4.0 dashboard panel for provider status, latency, recent events, degraded/fallback state, and replay signals.

## Safety Boundary
- Realtime providers are disabled by default unless environment variables explicitly configure them.
- AKShare remains fallback/delayed and must not be labeled reliable second-level realtime.
- No broker, order, credential, screen-click, live-trading, or risk-control bypass capability was added.
- All API/UI outputs preserve `review_only=true`, `simulation_only=true`, and `live_trading_enabled=false`.

## Validation Targets
- `python -m compileall app scripts tests`
- `pytest -q`
- `python -m pip check`
- `npx vue-tsc --noEmit`
- `npx vite build`
- `npm audit --audit-level=moderate`
- `git diff --check`
- forbidden tracked-file scan
- `codegraph status`

## Suggested V4.0-P1 Direction
- Add a scheduled or manual provider refresh workflow once an external data account is configured.
- Feed realtime events into monitoring alerts while preserving stop-new-entries and simulation-only risk gates.
- Add performance pressure tests for high-volume event ingestion and replay.
