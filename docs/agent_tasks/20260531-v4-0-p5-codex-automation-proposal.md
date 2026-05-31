# V4.0-P5 Handoff: Codex Automation Proposal Metadata

## Goal

V4.0-P5 adds a review-only layer that describes how Codex app automations should run the realtime cycle and off-hour potential search workflows. It must not create backend recurring jobs, execute shell commands from the API, or enable live trading.

## Implemented Scope

- `GET /api/realtime/automation-proposal` returns proposed automation cards for:
  - `realtime-cycle` on workdays at 10:00 / 13:00 / 16:00 Asia/Shanghai.
  - `potential` off-hour candidate search at 20:00 Asia/Shanghai.
- Each proposal includes cadence text, command text, evidence endpoints, expected output, default paused status, and safety flags.
- The V4.0 dashboard displays proposal count, proposal cards, and automation guardrails.
- Tests assert the proposal remains `review_only=true`, `simulation_only=true`, and `live_trading_enabled=false`.

## Safety Boundary

- Backend APIs only return metadata.
- No API executes shell commands, creates OS jobs, edits Codex app automations, places orders, clicks broker software, reads credentials, or enables live trading.
- Proposed automations must be reviewed and explicitly enabled outside the backend.
- External realtime providers can remain disabled; unconfigured realtime-cycle runs must report `needs_config` / `fallback_required` without fake prices.

## Validation Targets

- `pytest backend/tests/test_realtime_market.py -q`
- `python -m compileall backend/app backend/scripts`
- Full backend/frontend validation from `docs/RELEASE_CHECKLIST.md`
- `git diff --check`
- forbidden tracked-file scan
- `codegraph status`

## Next Step

After validation, create paused/reviewable Codex app automation proposals for the two workflows and let the operator approve them in the app UI.
