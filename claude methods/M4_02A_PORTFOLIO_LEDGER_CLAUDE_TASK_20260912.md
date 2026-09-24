# M4-02A-PORTFOLIO-LEDGER-20260912

Owner: Claude, the existing ZK-trading / Fable 5.1 project advice (fork) session. Reviewer/integrator: Codex. User has authorized the next small step after acceptance and resumption of the 15-minute patrol. This is one bounded implementation task, not permission to dispatch other agents or advance other stages.

## Read first and pin

Read AGENTS.md, CODEX_CLAUDE_COLLABORATION.md, `_m4_20260912/PLAN.md`, current coordination state, `M4_01_CODEX_ACCEPTANCE_20260912.md`, `_m4_20260912/execution_freeze.json`, M4-01 CONTRACT, CORRECTION_MATRIX, and the final kernel and tests. The final source differs from Claude delivery 02 only by Codex's unit-based CNY numeric normalization and a regression test; inspect that integration correction, report any material concern, and do not silently revert it. Freeze pins override old delivery-02 hashes for the integrated code.

Frozen kernel: `backend/app/research/m4_execution.py`, SHA-256 `83a28b543b9ecc5edf8080ea39fa388f8b2bb5a8724ef68b4b532041216678c7`.
Frozen tests: `backend/tests/test_m4_execution.py`, SHA-256 `90d8790400a497f31868ab52f985f1fe98c98806871c7346f68e8e5821c19317`.

M4-01 passed 62 isolated unittest cases and 16 independent Codex checks. This proves only a synthetic, already-sized, single-order execution contract. M3 remains 0/50 dual-positive with 32 disputes, strict_pit=false and training_eligible=false. No historical execution or strategy validity is granted.

## Exclusive write scope

- NEW `backend/app/research/m4_portfolio.py`
- NEW `backend/tests/test_m4_portfolio.py`
- NEW `claude methods/_m4_20260912/claude_02a/` for runner, synthetic fixtures, reports and evidence

Codex owns all state, baseline, freezes, acceptance/task files and automation. All other files are read-only, especially M4-01 code/tests/claude_01, every M2/M3 artifact, original datasets, knowledge files and SQLite. Do not edit package initializers, application APIs, legacy backtest, configuration, dependency files or frontend. Do not stage/commit/push. No subprocess spawning from the test subject, no other agents, network, clients, credentials, accounts, production or screen-click simulation. No app/settings imports, pytest/conftest or legacy engine construction.

## Concrete deliverable

Implement a small stdlib-only, in-memory, deterministic portfolio ledger over the frozen execution kernel. It consumes explicitly ordered synthetic requests/events for already-sized orders; it is not yet a strategy engine. No default fees, market rules, calendar, clocks or prices. Use an injected execution module/dependency or an explicitly isolated import arrangement so tests never import `app` or initialize production. If the frozen contract cannot safely represent a required event, return a precise limitation and report it rather than editing the frozen kernel.

1. Keep cash, per-symbol inventory lots, acquired sessions, remaining cost basis and settled/unsettled quantities. Kernel requests must derive cash/inventory from actual ledger state; reject stale or mismatched externally supplied state. Preserve FIFO lot provenance and kernel result/policy/input identities. Reconcile cash exactly to initial cash plus applied deltas and positions to initial quantities plus applied fills.
2. Apply no cash/position effect for rejected/unfilled results; handle partial fills and their remaining orders explicitly. Reject oversized sells, negative cash and inventory, malformed or out-of-order events, mismatched symbols/policy/result hashes and tampered results. Keep failure reasons visible. Do not mutate inputs. Avoid a public bypass that permits arbitrary ledger deltas without the verified execution result.
3. Deduplicate attempts/fills deterministically. Replaying the same identity and payload must not charge fees or change cash/holdings twice; reusing an identity with conflicting content must fail explicitly. Preserve event ordering and report idempotent skips. Order quantity cumulatively filled must not exceed requested quantity. Model each partial execution charge according to the frozen per-attempt fee contract and disclose that assumption.
4. Shared liquidity is a resource across attempts/orders of the same evidence window. Track share consumption for share capacity and actual money consumed for CNY capacity, including different execution prices. Do not reset capacity with a new order id or convert previously consumed money at the next fill's price. Keep original capacity provenance and any residual-capacity transformation auditable. Demonstrate that multiple orders cannot overspend either a share or a CNY budget. If the primitive's consumed_quantity contract needs an adapter, explicitly declare and test it without changing the frozen module or fabricating evidence.
5. Allocate acquisition fees into lot cost and sale proceeds/fees into realized PnL with a declared cent rounding and deterministic residual rule. Partial-lot sales must conserve total cost to the cent; final disposal clears all remaining cost. Use a local Decimal context and stable canonical event/state identifiers; numeric representation and caller context must not alter the state. Keep capacity and FIFO quantities dimensionally explicit.
6. Provide a simple nonzero controlled fixture, including a complete round trip and a multi-lot partial FIFO sale. Hand anchor: synthetic cash 10000, buy 100 at 10 with commission 5 and transfer 0.01, next legal session sell 100 at 11 with commission 5, transfer 0.01 and stamp 0.55, zero slippage -> ending cash 10089.43, realized PnL 89.43, zero position. Rates used here are hypothetical arithmetic fixtures, not real tariffs. Include mixed old and same-session inventory to prove T+1 blocks only unavailable lots. Cover zero/partial/rejected fills, fees, duplicates, out-of-order events, multiple symbols and cumulative capacity with separate manually calculated expectations.
7. Demonstrate chronological causality: appending later events must not change earlier event/state prefixes. Do not use current-day closing marks to value earlier decisions. Supply an explicit interface for future sizing/valuation/risk integration, but do not implement position sizing, exposure, stops, exit selection, cooldown, benchmark or delisting strategy logic in this small step. Those are M4-02B after ledger acceptance. No historical reading or M4-03 work.

## Required evidence and stopping point

Before writing, verify all execution freeze pins and record source hashes, branch/HEAD and current git status. Preserve original baseline tracked files and production file positions; hashing file bytes is allowed, SQL queries are not. Preserve the current modified set; it is not yours to clean up.

Provide CONTRACT.md (ledger/event schema, dimensional units, FIFO/fee/residual/idempotency/ordering contracts and limitations), HAND_CALCULATED_BASELINE.md, runner source, actual unittest stdout and structured execution receipt, per-event ledger/reconciliation JSON, and source/preservation verification. Test subjects load by path or injection without app initialization. Install and self-check guards before importing subjects: deny SQLite, sockets/network, subprocess and writes outside claude_02a; bytecode disabled. Do not regenerate or overwrite previous evidence. No wall-clock waiting in tests.

Run focused checks, then the complete new isolated suite once on the final code. Re-running the frozen kernel suite read-only is allowed under the same guards with outputs confined to claude_02a. Distinguish tests actually run from plans and assertions. Keep review_only=true, live_trading_enabled=false, training_eligible=false, M4_complete=false in outputs.

Write artifact_manifest.json LAST, pinning every output and consumed source (including final code bytes and this task file), recording actual commands/exits, immutable preservation results and exclusions. The manifest need not contain its own hash. Report `M4-02A-PORTFOLIO-LEDGER-20260912 ready_for_review` with the final manifest SHA and stop. Do not self-accept, modify the freeze, start M4-02B/M4-03/M5, or resume/pause/create automation.
