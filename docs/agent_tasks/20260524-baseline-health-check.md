# Agent Task Packet: Baseline Health Check

## Goal

Confirm the current project can still build/run in its existing local-first shape, then report the smallest useful next implementation tasks.

## Executor

Antigravity implements only documentation/report updates if needed. Codex reviews.

## Scope

In scope:

- Read `AGENTS.md`.
- Inspect backend and frontend startup instructions.
- Run safe local checks.
- Identify broken commands, missing dependencies, or stale docs.
- Produce a concise health report.

Out of scope:

- Live trading
- Broker automation
- Credential storage
- Changing trading rules or risk logic
- Broad refactors

## Likely Files

- `README.md`
- `docs/CODEX_ANTIGRAVITY_WORKFLOW.md`
- `docs/agent_tasks/20260524-baseline-health-check.md`
- Optional: a new `docs/HEALTH_CHECK.md`

## Requirements

- Do not edit `frontend/dist`.
- Do not delete or overwrite `backend/trading_local.sqlite3`.
- Prefer checks that do not require live market hours.
- If a command fails because of environment, record the exact reason.
- If documentation is garbled or outdated, note it instead of rewriting the whole project docs.

## Acceptance Checks

- Backend Python import or compile check is attempted.
- Frontend build check is attempted if dependencies are present.
- Health report lists commands run and results.
- Health report lists the top 3 next tasks with risk level.

## Suggested Commands

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -m compileall app scripts

cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend
npm run build
```

## Handoff Back To Codex

Return:

- Files changed
- Commands run
- Test/build results
- Known failures or skipped checks
- Questions or risks for review

