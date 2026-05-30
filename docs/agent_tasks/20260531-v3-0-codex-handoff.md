# V3.0 Codex Handoff

V3.0 introduces a controlled code evolution review queue. It converts V2.5 experience-memory evidence into reviewable engineering suggestions, validates them through local CLI checks, and leaves acceptance or rejection to a human reviewer.

## Implemented Scope
- Initialized local CodeGraph for this workspace and added `.codegraph/` to `.gitignore`.
- Added `CodeEvolutionService` with deterministic review-only generation from experience reviews, events, and strategy snapshots.
- Added code evolution APIs for generate, list, detail, validation recording, approve, and reject.
- Added `automation_loop.py --mode code-evolution-review` for local API-based suggestion generation.
- Added `backend/scripts/code_evolution_validate.py` to run backend checks, frontend checks, `git diff --check`, and a forbidden tracked-file scan, then optionally POST validation results back to a record.
- Added a V3.0 dashboard panel that displays review items, evidence/risk summary, validation status, and human accept/reject controls.
- Added backend tests for generation idempotency, status transitions, API smoke, and live-trading safety boundaries.

## Safety Boundary
- The backend API never runs shell commands; validation is CLI-triggered only.
- No patch application, branch creation, PR creation, broker access, credential storage, live order endpoint, or screen-click trading control was added.
- All generated records include `review_only`, `simulation_only`, and `live_trading_enabled=false` evidence.
- `.codegraph/`, local SQLite databases, datasets, virtualenvs, build outputs, logs, and caches remain untracked.

## Suggested V3.5 Direction
- Add provider-neutral model support for explaining review items and grouping similar failure cases.
- Keep model output limited to explanation, proposal, and validation request objects.
- Continue requiring human approval before any strategy, rule, or code change moves beyond review.
