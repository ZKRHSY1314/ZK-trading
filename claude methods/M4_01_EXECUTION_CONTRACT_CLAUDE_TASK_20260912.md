# M4-01 — Deterministic, causal execution contract and pure kernel

task_id: M4-01-EXECUTION-CONTRACT-20260912
Owner: Claude in the existing ZK-trading / Fable 5.1 project advice (fork) session.
Independent reviewer/coordinator: Codex. Status on dispatch: proposed, not accepted.
User authorization: 2026-09-12 “启动M4”, continuing the previously authorized Claude implementation / Codex independent review / 15-minute patrol workflow.

## Read first

- AGENTS.md and CODEX_CLAUDE_COLLABORATION.md.
- claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md, M4 requirements at lines209 onward.
- claude methods/M3_FINAL_ACCEPTANCE_20260910.md and _m3_20260910/codex/final_acceptance_01/completion.json.
- claude methods/_m4_20260912/PLAN.md, codex/INITIAL_STATIC_FINDINGS.md and baseline/start.json.
- Existing backend/app/backtest/{engine,execution,ledger}.py, tests/test_backtest_engine.py and tests/conftest.py as static reference only. Follow directly relevant imports statically where useful; do not instantiate legacy services or run legacy tests.

M3 is technically closed with 0/50 dual-positive cases,32 disputes, strict_pit=false and training_eligible=false. Starting M4 does not change M3, authorize training, expand the universe, or prove historical performance. M4's engine-validation baseline must be explicitly independent of positive-label training.

## Concrete scope

Implement a small pure execution kernel and its explicit versioned contract. This first task addresses execution-time correctness and accounting of one decision, not a complete portfolio/backtest service. Use standard-library types and explicit inputs. Reuse inspected semantics where sound; document material differences from the legacy engine. Do not create another general framework or copy the large M3 module.

Allowed new code files (exclusive Claude ownership):
- backend/app/research/m4_execution.py
- backend/tests/test_m4_execution.py (standalone unittest runnable without pytest/conftest)

Allowed output/document scope:
- claude methods/_m4_20260912/claude_01/** only.

Everything else is read-only, including M2/M3 trees and all legacy source. Codex owns baseline/, codex/, PLAN.md, coordination_state.json, task and acceptance documents. No agents/workflows or other delegation, automatic scheduling, Git stage/commit/push, service changes, client/market capture, network, credentials/accounts/funds/orders, SQLite connections, existing labels/knowledge changes, or M5. Do not edit configuration or package initializers.

## Required behavior

1. Represent decision timestamp, signal/input availability timestamps, order submission, eligible session/expiry and actual execution timestamp distinctly. Use timezone-aware instants and an injected ordered exchange-session calendar; reject impossible, duplicated, unordered, missing or mismatched temporal evidence. A prior-close decision cannot fill that close or before its declared next eligible execution point. A halted session is not silently removed from calendar-based expiry/T+1 calculations.
2. Explicit execution-time context only: symbol identity/role, observed price and observation/availability time, tradability/limit evidence, liquidity capacity with unit and availability time, side/quantity, settled sellable quantity and available cash. Reject future, unknown or inconsistent prerequisites with structured reasons and no cash/position effects. Reject benchmark/non-tradable identities. A declaration of a real-looking symbol or date is not sufficient market evidence.
3. Do not use an execution day's later high/low/close/full-day amount to decide an opening fill, size an opening order, determine available cash or enforce a participation cap at open. Distinguish predeclared model assumptions from contemporaneous observations. If daily OHLC cannot prove queue/auction availability, preserve that limitation rather than invent liquidity or a successful fill. A later historical adapter must expose assumptions separately; no real-data adapter in this task.
4. Price tick rounding, lot size, side-specific limit behavior, price-band/no-band state, slippage, participation capacity, partial/rejected fills and expiry must be explicit and deterministic. Validate finite positive money/price inputs and nonnegative bounded quantities/rates; no NaN/inf, negative cash, over-selling, or rounding into an illegal price/quantity. Unknown limit/ST/IPO state is not silently normal. Model accepted/rejected/unfilled distinctly; a skipped cash check must not leave a recorded fill.
5. Fees are injected, effective-dated, versioned assumptions with provenance: buy/sell commission and minimum, transfer fee and sell-side stamp duty, plus adverse slippage with no double counting. Do not hardcode unverified current or historical legal rates. Synthetic tests use clearly named hypothetical fixture schedules, never cited as real historical tariffs. Fee-schedule availability and applicability are checked. Arithmetic uses Decimal or equivalently justified deterministic currency rounding; rejected/unfilled orders have zero executed cash flow.
6. Buy affordability includes all charges before reporting a fill. Sell settlement and held quantity are explicit; fixture T+1 semantics must reject same-session acquired inventory, while original settled inventory remains sellable. Lot/odd-lot policy must be declared rather than assuming one rule covers every exchange. Expose enough signed cash/quantity and fee breakdown for a later independent cash/FIFO ledger reconciliation. Portfolio allocation, stop/exit priority and cooldown remain M4-02, but document the interface needed for them.
7. Stable policy/input/result identities and explicit synthetic/review-only flags; no live gateway, database, filesystem, network or settings import side effects in the new module. Unknown information stays unknown. Freeze by delivered file and canonical policy hashes only after Codex review, not by self-acceptance.

## Validation and delivery

Use meaningful unittest tests with hand-calculated expected results, not comparisons against the same function. Include at least: next-session positive execution; same-close/early execution refusal; availability later than execution; changed future suffix cannot alter earlier decision; matching symbol/calendar/role; suspension and expiry; side-specific limit and slippage/tick interaction; insufficient cash including minimum commission+transfer fees; lot rounding and partial capacity; cumulative/exhausted capacity contract; same-session sell rejection and settled inventory sale; NaN/inf/zero/negative invalids; nonzero synthetic buy and sell with exact fee/cash results. Make rejection, valid nonzero and boundary cases independently inspectable. State which checks cover isolated execution only and which remain portfolio-level work.

Run with backend/.venv/Scripts/python.exe -B -X utf8 and standalone unittest, avoiding backend/tests/conftest.py and legacy constructor imports. Put any runner and logs inside claude_01/. Configure the runner to deny SQLite, network, subprocesses and output writes outside claude_01/ during tests; no bytecode writes. Do not weaken tests to match failures. Static inspection of existing files is allowed; no original database reads by SQL and no historical price extraction this task.

Deliver under claude_01/: CONTRACT.md, LEGACY_GAPS.md with exact source lines and observed-vs-inferred distinctions, execution_policy.json, execution receipt (real command, UTC start/end, exit code, tests, file hashes), test stdout, runner, and artifact_manifest.json written last. Manifest must enumerate every written file and consumed source with explicit path-root convention, SHA256 and byte size, plus before/after preservation checks. Include remaining M4-02 portfolio and M4-03 historical-evidence requirements. This task is not M4 complete. End with task_id, ready_for_review and exact manifest SHA, then stop. Do not read Codex independent test opinions or claim independent acceptance.

Rollback: these are isolated new files. Preserve rejected drafts and run evidence; any revised delivery uses identifiable versions/snapshots. No reset, deletion or overwrite of pre-existing project work.
