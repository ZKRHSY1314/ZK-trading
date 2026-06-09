# Codex Operating Rules

This project is a controlled A-share analysis, simulation, monitoring, and review cockpit. Continue development directly with Codex unless the user explicitly asks for an external agent workflow.

## Safety Boundaries

- Keep live trading disabled by default.
- Do not add broker login, credential storage, account/fund access, real order placement, real cancellation, or unrestricted screen-click trading.
- Treat general screen monitoring as read-only. The reviewed `/api/sim-cockpit/*` gateway is the only exception, and only for verified Tonghuashun `mncg` / simulated-account windows with desktop-adapter evidence, explicit `screen_click_simulation` mode, coordinate anchors, `SIMULATION_SCREEN_CLICK` confirmation, and passing simulation risk gates.
- Never use the simulation cockpit gateway for real accounts, broker login, credentials, fund-account views, bank-transfer views, or live entrusted orders.
- Do not modify local datasets, SQLite data, or knowledge files unless the task explicitly requires that mutation and includes validation.
- If data quality, market data, model confidence, or risk checks are unclear, degrade to review-only simulation or monitoring.

## Implementation Loop

1. Inspect current code and runtime state.
2. Make the smallest stage-aligned change.
3. Prove review-only / simulation-only / live-trading-disabled behavior in tests.
4. Run focused validation before broader checks.
5. Keep generated data, local databases, caches, `.venv`, `node_modules`, `frontend/dist`, logs, and `.codegraph` out of Git.

## Project Conventions

- Backend code lives under `backend/app`; backend scripts live under `backend/scripts`.
- Frontend code lives under `frontend/src`; do not edit `frontend/dist`.
- Prefer existing SQLite/service/API patterns over new infrastructure.
- Keep trading decisions auditable, explainable, and conservative.
