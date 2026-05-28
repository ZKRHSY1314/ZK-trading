# V1 Task 03: Frontend Workflow And E2E Hardening

## Goal

Make the Vue dashboard feel like a v1.0 local cockpit: daily workflow sections are easy to scan, simulation-only boundaries are obvious, and the page survives API failures without confusing the user.

## Scope

Likely files:

- `frontend/src/App.vue`
- `frontend/package.json`
- `frontend/scripts/`
- Optional frontend test or Playwright smoke script
- README docs for UI workflow

## Requirements

1. Workflow layout
   - Organize the first screen around the daily operator flow:
     - health/safety status
     - candidate discovery and lifecycle
     - price readiness and daily-bar coverage
     - monitoring alerts and symbol replay
     - paper simulation and evaluation
     - learning/reporting
   - Avoid landing-page marketing layout. This is an operational dashboard.

2. Error and loading states
   - Every API panel should show useful loading, empty, and error states.
   - A failed data provider should be shown as data quality/fallback status, not as a broken app.

3. Safety UI
   - Simulation-only and no-broker disclaimers must remain visible.
   - Live trading controls must stay disabled or absent.
   - Never label simulated actions as real buy/sell advice.

4. E2E smoke
   - Add or document a repeatable browser smoke check that validates:
     - app loads
     - Daily Bar Coverage renders
     - key buttons exist
     - no 4xx/5xx API calls during initial load
     - no console errors

## Acceptance Checks

```powershell
cd frontend
npx vue-tsc --noEmit
npx vite build
npm audit --json --audit-level=moderate
```

Run the browser smoke check against a running backend and frontend. Capture a concise JSON result in the handoff.

## Safety

- Do not add UI affordances for real broker login or real order execution.
- Simulated actions must remain visually labeled as simulation-only.

## Handoff

Create `docs/agent_tasks/stage_v1_task03_handoff.md` with screenshots or browser-smoke evidence, build results, and any UI risks.

