# Agent Operating Rules

This project uses a low-Codex-budget, high-Antigravity-budget workflow.

Codex is the supervisor. Antigravity is the executor.

## Roles

- Codex owns product framing, architecture choices, task decomposition, acceptance criteria, risk review, final code review, and small critical fixes.
- Antigravity owns bulk implementation, repetitive edits, UI wiring, refactors that follow an accepted plan, and first-pass bug fixing.
- Human approval is required for live trading behavior, account credentials, broker automation, destructive file operations, and dependency changes that materially expand the project.

## Project Safety Boundaries

- The first version remains simulation-first. Do not enable live trading by default.
- Do not add code that clicks real broker buy/sell controls.
- Do not store secrets, cookies, tokens, account numbers, or broker credentials in this repo.
- Do not overwrite local SQLite data or user knowledge files unless the task explicitly asks for data migration and includes a backup step.
- Prefer local-only operation. Network data is allowed for market data providers already used by the project.
- Keep generated outputs out of source unless they are intentional docs or fixtures.

## Required Loop

Every non-trivial task should pass through these stages:

1. Plan
   - Codex writes the goal, scope, files likely affected, risks, and acceptance checks.
   - Antigravity must not start broad implementation until the plan is explicit.

2. Implement
   - Antigravity implements only the accepted task scope.
   - Keep changes small enough for review.
   - Preserve existing backend FastAPI, frontend Vue/Vite, and local-first patterns.

3. Self-check
   - Antigravity runs the relevant checks before handing back.
   - Backend changes should run focused Python tests or import checks.
   - Frontend changes should run `npm run build` when UI or TypeScript changes are involved.

4. Review
   - Codex reviews the diff for correctness, safety, missing tests, and scope creep.
   - Codex either accepts, requests fixes, or applies final narrow edits.

5. Record
   - Summarize what changed, what was verified, and what remains risky.

## Implementation Preferences

- Backend code lives under `backend/app`; scripts live under `backend/scripts`.
- Frontend source lives under `frontend/src`; do not edit `frontend/dist` by hand.
- Use the existing SQLite store and service boundaries before adding new persistence layers.
- Keep trading decisions explainable and auditable.
- If market data fails, degrade to conservative simulation or observation instead of inventing prices.
- UI should be operational and dense, not a landing page.

## Handoff Format

Use `tools/agent_task_template.md` for Antigravity execution requests.

Antigravity should return:

- Files changed
- Commands run
- Test/build results
- Known failures or skipped checks
- Questions for Codex review

