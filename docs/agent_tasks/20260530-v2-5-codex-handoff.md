# V2.5 Codex Handoff

V2.5 adds a review-only experience memory layer on top of the V2.0 credibility milestone. The purpose is to make daily learning, strategy performance drift, and code evolution auditable without adding broker access, credentials, live order placement, or any production trading control.

## Implemented Scope
- Added SQLite tables for `experience_events`, `experience_reviews`, `strategy_performance_snapshots`, and `code_evolution_records`.
- Added `ExperienceMemoryService` to idempotently capture recent evidence from candidate lifecycle, monitoring alerts/actions, simulation fills, historical backtests, closed trades, AI proposal/audit logs, and price readiness reports.
- Added daily experience review generation that joins candidate/monitoring summaries, latest historical backtest metrics, benchmark evidence, execution warnings, portfolio risk gates, case classifications, and next actions.
- Extended the learning daily report with V2 credibility evidence: latest historical backtest, portfolio risk gates, AI proposal validation summary, and explicit review-only/simulation-only flags.
- Added API endpoints under `/api/experience/*` for capture, daily reviews, summary, events, strategy performance snapshots, and code evolution records.
- Added `automation_loop.py --mode experience-review` to run the memory review through the local backend API.
- Added a V2.5 dashboard panel showing event categories, daily reviews, strategy snapshots, recent events, and code evolution audit records.
- Added focused backend tests for idempotent capture, daily review persistence, API smoke, and simulation-only safety flags.

## Safety Boundary
- `settings.enable_live_trading` remains false by default and is surfaced in the experience summary/review.
- The new service only reads local evidence tables and writes review/audit tables.
- No broker adapter, account credential, live order endpoint, screen-control trade execution, or auto-approval path was added.

## Suggested V3.0 Direction
- Add richer sample attribution for why a candidate later succeeded or failed.
- Add visual trend/regime comparisons for repeated pattern families.
- Add a human review queue for accepting/rejecting code evolution proposals.
- Keep real trading unavailable until paper simulation has enough audited outcome history.
