# M4-02A hand-calculated baseline (synthetic fixtures; rates are arithmetic fixtures, not real tariffs)

All numbers below were computed by hand before running the tests and are asserted verbatim in
`backend/tests/test_m4_portfolio.py`; the executed per-event ledger records are in `evidence/ledger_scenarios.json`
(scenario keys in brackets). Fixture: fee schedule `HYPOTHETICAL_LEDGER_FEES` — buy/sell commission 0.0003 with a
5.00 minimum, transfer fee 0.00001 both sides, sell stamp duty 0.0005; zero slippage; tick 0.01; 100-share lots with
`whole_odd_remainder_only`; T+1 on the injected exchange calendar 2024-03-18 … 2024-03-25; `max_participation_rate` 1
unless stated. Money is CNY quantized to 0.01 with ROUND_HALF_UP per charge (kernel) and per lot allocation (ledger).

## 1. Round trip — the task's anchor [`anchor.round_trip`]

| Step | Arithmetic | Result |
|---|---|---|
| Initial | synthetic cash | 10 000.00 |
| Buy 100 @ 10.00 on 2024-03-19 (prior-close decision 03-18) | gross 1 000.00; commission max(1 000 × 0.0003 = 0.30, 5.00) = 5.00; transfer 1 000 × 0.00001 = 0.01 | cost **1 005.01**; cash 8 994.99; lot `SYN_LEDGER_01:O-BUY:A1` = 100 shares, cost 1 005.01, sellable from 03-20 |
| Sell 100 @ 11.00 on 2024-03-20 (decision 03-19; lot settled T+1) | gross 1 100.00; commission max(0.33, 5.00) = 5.00; transfer 0.01; stamp 1 100 × 0.0005 = 0.55; fees 5.56 | proceeds **1 094.44**; FIFO full disposal allocates 1 005.01 |
| Realized PnL | 1 094.44 − 1 005.01 | **89.43** |
| Ending cash | 8 994.99 + 1 094.44 | **10 089.43** = 10 000.00 + 89.43 |
| Position | 100 − 100 | **0** |

Reconciliation: cash = initial + Σ deltas (−1 005.01 + 1 094.44); acquisitions 1 005.01 = allocated 1 005.01 + remaining 0.00.

## 2. Multi-lot partial FIFO sale with cent conservation [`fifo.multi_lot_partial`]

| Step | Arithmetic | Result |
|---|---|---|
| Buy 100 @ 10.00 (03-19) | as above | lot1 cost 1 005.01 |
| Buy 300 @ 10.33 (03-20) | gross 3 099.00; commission max(0.9297 → 0.93, 5.00) = 5.00; transfer 0.03099 → 0.03 | lot2 cost **3 104.03**; cash 10 000 − 1 005.01 − 3 104.03 = **5 890.96** |
| Sell 200 @ 12.00 (03-21) | gross 2 400.00; commission max(0.72, 5.00) = 5.00; transfer 0.024 → 0.02; stamp 1.20; fees 6.22 | proceeds **2 393.78** |
| FIFO allocation | lot1 full → 1 005.01; lot2 partial 100/300 → 3 104.03 × 100 / 300 = 1 034.6766… → **1 034.68** (HALF_UP) | allocated 2 039.69; lot2 remaining 200 shares, cost 3 104.03 − 1 034.68 = **2 069.35** |
| Realized (sale 1) | 2 393.78 − 2 039.69 | **354.09** |
| Sell 200 @ 12.00 (03-22) | same fees → proceeds 2 393.78; final disposal allocates the exact remainder 2 069.35 | realized **324.43** |
| Totals | realized 354.09 + 324.43 = **678.52**; cash 5 890.96 + 2 × 2 393.78 = **10 678.52** = 10 000 + 678.52 | acquisitions 4 109.04 = allocated 4 109.04 + remaining 0.00 |

## 3. Declared opening lot [`TestFIFOCostAllocation.test_declared_initial_lot_participates_in_fifo`]

Initial lot 100 shares acquired 03-18 with declared cost 950.00; sell 100 @ 10.00 on 03-19: proceeds 1 000.00 − 5.00 − 0.01 − 0.50 = 994.49; realized 994.49 − 950.00 = **44.49**.

## 4. T+1 with mixed inventory [`settlement.mixed_inventory`]

Initial lot 100 (acquired 03-18, cost 1 000.00) + buy 200 @ 10.00 on 03-19 (cost 2 005.02). On 03-19: held 300, settled 100, unsettled 200. Sell 150 on 03-19 → kernel `insufficient_settled_inventory` (no effect). Sell 100 on 03-19 → fills from the settled 03-18 lot (FIFO). On 03-20 the 03-19 lot is settled: sell 200 → position 0.

## 5. Partial fills, remaining order, per-attempt fees [`orders.partial_and_remaining`]

Continuous buy order of 300 @ 10.00. Capacity evidence `CAP-C` = 150 shares (rate 1): attempt A1 fills one whole lot, 100 (cost 1 005.01; remaining 200). Attempt A2 against the same evidence: 50 shares of allowance remain → `capacity_below_minimum_lot`, order stays live. Attempt A3 for 300 (> remaining 200) → ledger `order_quantity_exceeds_remaining`. Attempt A4 with fresh evidence `CAP-D` (500) fills 200: gross 2 000.00; commission max(0.60, 5.00) = 5.00 (**second minimum commission — per-attempt fee contract, disclosed**); transfer 0.02 → cost 2 005.02. Order complete, `live=false`; A5 → `order_not_live`. Cash 10 000 − 1 005.01 − 2 005.02 = **6 989.97**; position 300.

## 6. Shared share budget [`capacity.shares_shared`]

`CAP-S` = 500 shares, rate 1 → budget 500. O1 buys 300 (consumed 300); O2 requests 300 → the kernel receives `consumed_quantity=300` and fills 200 (consumed 500); O3 → `capacity_exhausted`. A new order id does not reset the budget; an event carrying `consumed_quantity=999` → `capacity_consumption_mismatch`; changed evidence quantity → `capacity_evidence_conflict`; changed participation rate → `capacity_rate_conflict`.

## 7. Shared CNY budget at different prices [`capacity.cny_money_budget`]

`CAP-M` = 5 000.00 CNY, rate 1 → budget 5 000.00.

| Order | Price | Residual presented to the kernel | Kernel allowance | Fill | Money consumed after |
|---|---|---|---|---|---|
| O1 | 10.00 | 5 000.00 | floor(5 000 / 10) = 500 | 300 (order size) → gross 3 000.00 | 3 000.00 |
| O2 | 10.50 | 5 000 − 3 000 = 2 000.00 | floor(2 000 / 10.5) = 190 → one lot | 100 → gross 1 050.00 | 4 050.00 |
| O3 | 9.00 | 950.00 | floor(950 / 9) = 105 → one lot | 100 → gross 900.00 | 4 950.00 |
| O4 | 9.00 | 50.00 | floor(50 / 9) = 5 < lot | unfilled `capacity_below_minimum_lot` | 4 950.00 |

Budget never exceeded (4 950.00 ≤ 5 000.00). Re-pricing the 400 consumed shares at the third fill's 9.00 would have pretended 3 600 spent and left 1 400 of "room" — the money-based adapter removes that overspend.

With rate 0.5 [`test_cny_budget_with_participation_rate_below_one`]: `CAP-R` = 10 000.00 → budget 5 000.00; residual presented = floor_cents(5 000 / 0.5) = 10 000.00; O1 400 @ 10 → consumed 4 000.00; residual (5 000 − 4 000) / 0.5 = 2 000.00 → kernel allowance floor(2 000 × 0.5 / 10) = 100 → O2 fills 100 (consumed 5 000.00); O3 → `capacity_exhausted`.

## 8. Multi-symbol and prefix invariance [`chronology.prefix`, `test_multiple_symbols_keep_separate_lots`]

E1 buy 100 SYN_LEDGER_01 @ 10.00 (03-19, cost 1 005.01); E2 buy 200 SYN_LEDGER_02 @ 12.00 (03-19): gross 2 400.00, commission max(0.72, 5.00) = 5.00, transfer 0.024 → 0.02, cost **2 405.02**; E3 sell 100 SYN_LEDGER_01 @ 11.00 (03-20) → proceeds 1 094.44, realized 89.43. Cash 10 000 − 1 005.01 − 2 405.02 + 1 094.44 = **7 684.41**; positions {SYN_LEDGER_02: 200}. Appending E4/E5 leaves the first three records and state hashes byte-identical.

## 9. Duplicates, ordering, guards [`idempotency.replays`, `account_guard`, `no_effect.results`]

Replaying E1 (same id and payload) → `skipped_duplicate`, cash stays 8 994.99 (fees not charged twice); same id with a different quantity → `duplicate_event_conflict`; same (order, attempt) with a different price → `attempt_identity_conflict`. A stale account state (cash 10 000 after the buy) → `account_state_mismatch` showing supplied 10000 vs derived 8994.99. Kernel rejections/unfilled results (insufficient cash with 500.00 cash, suspension, missing capacity) leave cash and positions untouched with the kernel reasons visible.
