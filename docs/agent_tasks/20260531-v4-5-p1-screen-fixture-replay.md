# V4.5-P1 Handoff: Screen Provider Interface and Fixture Replay

## Goal

Add the provider-neutral screen capture/OCR adapter boundary while keeping real desktop capture disabled. This step proves that future screenshot/OCR evidence can flow into the V4.5 observation ledger through fixture replay first.

## Implemented Scope

- Added screen provider abstractions:
  - `DisabledScreenCaptureProvider`
  - `FixtureScreenCaptureProvider`
- Added `SCREEN_CAPTURE_PROVIDER` setting with default `disabled`.
- Added provider capability API:
  - `GET /api/screen-monitoring/providers`
- Added fixture replay API:
  - `POST /api/screen-monitoring/observations/fixture-replay`
- Updated `ScreenMonitoringService.capabilities()` to report provider status, provider configuration, and fixture support.
- Updated the V4.5 dashboard to show provider status and run fixture replay.
- Added tests covering default disabled provider, fixture provider capability, fixture replay persistence, and API smoke.

## Safety Boundary

- Default provider remains disabled.
- Fixture replay does not capture the real screen.
- Fixture replay does not run OCR.
- No click, typing, broker action, order action, credential access, or live trading endpoint is added.
- All outputs remain `review_only=true`, `simulation_only=true`, and `live_trading_enabled=false`.

## Next Step

V4.5-P2 can add a real screenshot provider interface behind explicit local configuration, but it should first run against a harmless non-broker window and preserve redaction/audit behavior before any trading software observation is enabled.
