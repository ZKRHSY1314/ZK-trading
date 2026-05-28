# V1.0 Antigravity Task Pack Index

## Purpose

This pack turns the current A-share AI trading cockpit into a v1.0 local release candidate. It is designed for the Codex-Antigravity workflow:

- Antigravity implements each task card.
- Codex reviews the diff, runs acceptance checks, and performs final fixes.
- The system remains simulation-only and never enables broker control, credentials, real orders, or live trading.

## Current Completed Foundation

- Local FastAPI backend and Vue/Vite frontend.
- SQLite knowledge repository and legacy data importer.
- User knowledge seed for Sanwei Communication, Gold Mantis, and Lucky Film.
- Candidate scanning, auto-discovery, lifecycle, and potential search.
- Monitoring sessions, alerts, symbol replay, and review summaries.
- Safe automation loop with explicit blocked live/broker actions.
- Agent control queue and Codex-Antigravity handoff tooling.
- Learning samples, backtest skeleton, daily report skeleton, phase replay, and phase matching.
- Signal performance, calibration proposals, sandbox experiments, paper simulation policy gates, and paper simulation evaluations.
- Price readiness, daily-bar cache, resilient AKShare-to-Sina historical fallback, and source attribution.
- Workday automation schedule already set separately to 10:00, 13:00, and 16:00.

## V1.0 Remaining Work

V1.0 should be considered ready only after these are true:

- A fresh clone can be installed and run without the private dataset.
- The repo has a reproducible seed/demo mode that does not require `数据集1`.
- Backend and frontend have reliable regression checks.
- The main UI supports the complete daily workflow without needing raw API calls.
- Automation modes have clear runbooks, logs, retention, and failure summaries.
- AI explanations and reports cite rules, data source quality, and similar cases without sounding like investment advice.
- Simulation/backtest metrics are conservative, auditable, and clearly separated from real trading.
- Release documentation explains what is in v1.0, what is deliberately excluded, and how to recover from common local failures.

## Recommended Execution Batches

Batch A: v1.0 release foundation

1. `20260528-v1-task-01-installation-demo-mode-and-data-safety.md`
2. `20260528-v1-task-02-backend-regression-suite-and-api-contracts.md`
3. `20260528-v1-task-03-frontend-workflow-and-e2e-hardening.md`
4. `20260528-v1-task-04-automation-runbooks-and-release-packaging.md`

Batch B: v1.0 intelligence and simulation polish

5. `20260528-v1-task-05-ai-explanations-case-retrieval-and-reports.md`
6. `20260528-v1-task-06-simulation-backtest-and-policy-validation.md`

## Global Safety Requirements

Every task card must preserve these boundaries:

- `/health` reports `live_trading_enabled=false`.
- No code path controls broker software.
- No credentials, cookies, account numbers, API tokens, or broker login state are stored.
- No real orders are placed.
- Simulated orders and simulated signals are visibly labeled as simulation-only.
- Candidate scores, rules, policies, and settings are not silently mutated. Any proposed change must be recorded as a reviewable proposal.
- Missing data is reported honestly. Do not fabricate market bars, prices, fills, or labels.

## Master Prompt For Antigravity

Read `AGENTS.md`, `docs/CODEX_ANTIGRAVITY_WORKFLOW.md`, and this index first. Then execute the task cards in the recommended order. For each card:

1. Keep changes scoped to the listed files and nearby modules.
2. Run the acceptance checks in the card.
3. Create or update a handoff file under `docs/agent_tasks/` with:
   - files changed
   - commands run
   - test/build results
   - safety evidence
   - known risks or skipped checks
4. Do not generate the next task card yourself unless explicitly asked.

