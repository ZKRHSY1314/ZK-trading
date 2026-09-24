# M4-02B risk / exit policy contract — `backend/app/research/m4_risk.py` (contract `0.1.0-draft`)

Task `M4-02B-RISK-EXIT-20260912` (task file sha256 `86cffe0bb4692ba23340515b936d00d2d188d586f6c524ecbadd4025e3546ec8`). Status: **ready_for_review — proposed, not accepted.** A stdlib-only, in-memory, deterministic policy layer over the frozen M4-01 kernel (`83a28b54…`, policy `9bea8348…`) and the frozen M4-02A ledger (`2b3eec83…`, policy `633f78d9…`); both are injected and unmodified. Synthetic only: no signal generation, ranking, tuning, historical data, corporate actions or production service. M3 stays 0/50 dual-positive; `review_only=true`, `live_trading_enabled=false`, `training_eligible=false`, `M4_complete=false`; no M5.

* Module sha256 and test sha256: see `artifact_manifest.json` (`ledger`/`code` sections) — 17 tests, 8 recorded scenarios; risk policy hash `RISK_POLICY_HASH` (`sha256(canonical RISK_POLICY)`) is printed in `execution_policy` of the manifest.
* The engine refuses to start on a kernel/ledger whose policy hashes differ from the frozen ones it was built on (`frozen_policy_mismatch`).

## 1. Interfaces and units

| Type | Fields (units) |
|---|---|
| `Mark` | `symbol`, `price` (CNY, positive tick multiple; re-spelled at the tick scale), `observed_at`, `available_at` (aware instants), `source_ref`, `synthetic` |
| `Signal` | `signal_id`, `symbol`, `side` (`buy` only; exits come from the policy), `observed_at`, `available_at`, `source_ref`, `synthetic` |
| `SecurityStatus` | `symbol`, `status` ∈ {listed, suspended, delisting_announced, delisted}, instants, provenance |
| `BenchmarkObservation` | `symbol` (index, never traded), `level` (quantized to 0.01), instants, provenance |
| `RiskPolicy` | `max_position_weight`, `max_gross_exposure` ∈ (0,1]; `min_cash_reserve` (CNY ≥ 0); `stop_loss_pct` ∈ (0,1]; `profit_target_pct` (> 0 or None); `max_holding_sessions` ≥ 1; `cooldown_sessions` ≥ 0; `max_mark_age_sessions` ≥ 0; `max_gap_pct` ∈ (0, 0.5]; `intent_expiry_sessions` ≥ 1; `exit_priority` (distinct tuple of stop_loss / profit_target / max_holding); `provenance` |
| `UniverseMember` | `symbol`, `role=stock`, declared `board`, `listing_evidence_ref`; fixed at engine construction (a member that later suspends/delists stays a member) |
| `DecisionContext` | `decision_session`, `decided_at` (≥ that session's close), kernel `SessionCalendar`, `FeeSchedule`, `ExecutionAssumptions` (hypothetical) |
| `AttemptEvidence` | `attempt_id`, `executed_at`, `session`, `phase`, kernel `TradabilityEvidence`, `PriceObservation`, `LiquidityCapacity` |

Quantities are shares (int, lot-conformant); money is CNY `Decimal` quantized to 0.01; weights/returns are 6-decimal strings. All arithmetic runs under the kernel's fixed `Decimal` context; caller context and numeric spellings do not change records (tested).

Public surface: `decide(decision_id, ctx, marks, signals, statuses, benchmark) -> decision record`; `execute(intent_id, ctx, evidence) -> attempt record`; `cancel(intent_id, reason)`; `benchmark_return(start, end, observations, as_of, calendar)`; `performance(ctx, marks, statuses, benchmark, start_session, initial_cash, hypothetical_terminal_marks)`; read-only `records`, `intents()`, `reservations()`, `chain_hash`. Every returned object is a detached deep copy; the only path to the ledger is `PortfolioLedger.apply` with a kernel `ExecutionRequest` the engine builds — no delta bypass.

## 2. Causal boundaries

* **Evidence time.** An item is consumed by a decision only if `observed_at ≤ decided_at` and `available_at ≤ decided_at`; otherwise it is listed under `refusals` as `future_evidence` (a mark observed after the decision instant, a status published later, a future benchmark level). `available_at < observed_at` or missing provenance is `inconsistent_evidence`.
* **Valuation.** For each held symbol the latest mark observed on a session with `0 ≤ age ≤ max_mark_age_sessions` (calendar sessions) is the eligible mark; conflicting marks at the same instant are `inconsistent_evidence`. No eligible mark → the position is kept, listed under `incomplete_symbols` with the reason (`missing_mark` / `stale_mark` / `inconsistent_evidence`), and the valuation is `complete=false` (`equity=null`); there is no zero, cost-basis, later-close or last-price fallback. With a complete valuation: `equity = cash + Σ quantity × mark`, `gross_exposure`, per-symbol `weight`, `gross_weight`.
* **Decision ordering.** `decided_at` must not precede the session close nor the previous decision; `decision_id` is unique. Decisions on a session's close execute no earlier than the next session's open through the frozen kernel (`eligible_from = open(next_session)`, `submitted_at = decided_at`).

## 3. Sizing and reservations

Signals are processed in stable `(symbol, signal_id)` order. Refusals (each recorded per signal): `benchmark_symbol`, `symbol_not_in_universe`, `valuation_incomplete`, `symbol_held`, `symbol_pending_intent`, `cooldown_active`, `security_not_tradable` (suspended / delisting_announced / delisted at decision time), `missing_mark` / `stale_mark`, `duplicate_signal`, non-buy side.

Rooms at decision time: `position_room = max_position_weight × equity`, `portfolio_room = max_gross_exposure × equity − gross_exposure − reserved_exposure`, `cash_room = cash − min_cash_reserve − reserved_cash`; `budget = floor_cents(min(rooms))`. `reserved_price = ceil_tick(mark × (1 + slippage_rate))`; the quantity is the largest lot multiple whose `estimated_cost = gross + max(round(gross × buy_commission), min_commission) + round(gross × transfer_fee)` fits the budget (the frozen kernel's own charge rules). Below one minimum lot → `zero_size` with `insufficient_cash_or_room` and the one-lot cost shown; never a forced minimum lot. A buy intent reserves its `budget` (cash and exposure); the next signal in the same decision and later decisions see the reduced rooms, so pending intents cannot spend the same capacity. Limit price `ceil_tick(mark × (1 + max_gap_pct))`.

Reservation life-cycle: retained while `pending` / `partially_filled` / `unfilled_live` (for the remainder); released on `filled`, `expired` (unfilled at the final legal opportunity), `cancelled` (explicit or `gap_exceeds_budget`); a kernel-rejected or ledger-rejected attempt changes nothing (intent and reservation unchanged, audit only).

**Execution-time gap re-check.** At `execute`, the affordable quantity is recomputed at the kernel's slipped fill price of the *observed execution print* against the reserved budget only: full quantity, downsized to whole lots (`gap_downsized`, the intent quantity is reduced accordingly) or `cancelled` (`gap_exceeds_budget`). Never enlarged; never uses a later close. A print beyond the limit price is left unfilled by the kernel (`fill_price_exceeds_limit_price`).

## 4. Exit, cooldown and state transitions

`entry_cost_reference = FIFO cost_remaining / quantity_remaining` (fees included) from the ledger lots. On each decision with an eligible mark: `stop_loss: mark ≤ ref × (1 − stop_loss_pct)`; `profit_target: mark ≥ ref × (1 + profit_target_pct)`; `max_holding: sessions_held ≥ max_holding_sessions` (`sessions_held = index(decision) − index(entry_session)`; an entry session outside the injected calendar cannot be aged and never triggers). The first matching reason in `exit_priority` wins; all checks are recorded. Decisions use observed closes only — a bar touching a threshold intraday is not consulted and never fills. The exit intent sells the whole position with limit `floor_tick(mark × (1 − max_gap_pct))`; a gap below the limit leaves it unfilled (`fill_price_below_limit_price`), the position stays, and the next decision re-evaluates. T+1, suspension, limit states, expiry and capacity are enforced by the frozen kernel/ledger.

Intent states: `pending → filled | partially_filled | unfilled_live | expired | cancelled`; `partially_filled → filled | partially_filled | expired | cancelled`; `unfilled_live → filled | partially_filled | expired | cancelled`; `rejected` is reserved for kernel/ledger-level refusals that terminate nothing (the intent keeps its previous state). Attempt outcomes carry the ledger record (kernel status, reasons, `committed`, `event_record_hash`).

Cooldown starts only when an exit fill brings the symbol's position to zero (`cooldown_started_session` = the fill session); partial exits keep the residual, the pending remainder and no cooldown; duplicate attempts (`attempt_id` already recorded for the intent) are refused before touching the ledger; unfilled/rejected attempts never close holdings. Re-entry is allowed at decision sessions with `index(decision) − index(exit_session) ≥ cooldown_sessions` (exactly at the boundary; non-trading days do not count).

## 5. Benchmark and delisting

`benchmark_return(start, end, observations, as_of, calendar)`: levels on exactly the two decision sessions, available by `as_of`; missing → `status=missing, return=null` (a missing observation is not a zero return; no interpolation or lookahead); future levels are refused. The decision record carries the benchmark level of its session or `missing`. A signal on the benchmark symbol is refused (`benchmark_symbol`); the benchmark cannot be a universe member.

Statuses: the latest status with `available_at ≤ decided_at`; a `delisting_announced` published later is refused as future evidence and the holding is still valued; once available, no new buys (`security_not_tradable`), holdings kept and valued. `delisted`: the holding is retained as an **unresolved position**; valuation and performance are `complete=false` with the limitation — *the frozen contracts carry no verified executable exit, settlement or corporate-action support for a delisted holding; the position is retained unresolved and no liquidation cash is posted*. `hypothetical_terminal_marks` produce a separately labelled `hypothetical_terminal_scenario` (never posted; `ledger_cash_unchanged` shown). A terminal status never changes earlier records or membership (tested).

## 6. Audit chain and determinism

Every decision / attempt / cancel / refusal is an append-only record with `record_hash = sha256(previous + canonical record)` and a `state_summary` (intent statuses, reservations, exit sessions, ledger `state_hash`). Appending later events leaves earlier records and hashes unchanged (tested); refusals are atomic on this layer (working copy discarded) and the ledger is atomic on its own.

## 7. Unsupported / not implemented (explicit)

* Only prior-close decisions executing from the next session's open; no intraday decisions, no intrabar ordering inference.
* One exit intent per symbol at a time; exits sell the full position; no scaling out by rule.
* Entry sessions before the injected calendar cannot be aged for `max_holding`.
* Delisted holdings cannot be resolved (no settlement / corporate-action support in the frozen contracts); no real-data adapter; nothing here is historical execution evidence.
* Fees, slippage, lot and policy parameters are hypothetical fixtures; M4 is not complete.
