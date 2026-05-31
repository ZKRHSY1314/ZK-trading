# V4.5-P2 Handoff: Local Safe Screen Capture Preflight

## Goal

Prepare the project for future real screenshot capture without enabling capture by default. V4.5-P2 adds a local-safe provider preflight that checks explicit configuration, harmless window allowlists, broker/trading deny terms, redaction requirements, and audit recording.

## Implemented Scope

- Added settings:
  - `SCREEN_CAPTURE_ALLOW_REAL_CAPTURE=false`
  - `SCREEN_CAPTURE_ALLOWED_WINDOWS=""`
  - `SCREEN_CAPTURE_BLOCK_BROKER_WINDOWS=true`
  - `SCREEN_CAPTURE_BROKER_WINDOW_TERMS=...`
- Added `LocalSafeScreenCaptureProvider`.
- Added `POST /api/screen-monitoring/capture-preflight`.
- Preflight records an observation with `capture_preflight_ready` or `capture_preflight_blocked`.
- Frontend V4.5 panel now has a screenshot preflight action and displays preflight evidence.

## Safety Boundary

- The endpoint does not capture a screenshot.
- The endpoint does not run OCR.
- Default configuration blocks all real capture.
- Broker/trading windows are blocked even if allowlisted.
- Passing preflight only means a later separately reviewed stage may attempt harmless-window capture; it does not enable broker observation or trading.
- All evidence remains `review_only=true`, `simulation_only=true`, and `live_trading_enabled=false`.

## Next Step

V4.5-P3 can add a harmless-window capture implementation behind the same preflight gates, storing only a redacted/local artifact reference. It should be tested against a non-broker fixture or harmless window before any trading software observation is considered.
