# M4-02B hand-calculated baseline (synthetic fixtures; hypothetical fees and policy parameters)

All numbers were computed by hand before running the tests and are asserted verbatim in `backend/tests/test_m4_risk.py`; the
executed records are in `evidence/risk_scenarios.json` (scenario keys in brackets). Fixture: fees `HYPOTHETICAL_RISK_FEES`
(commission 0.0003 with 5.00 minimum, transfer 0.00001, sell stamp 0.0005), slippage 0.001, tick 0.01, 100-share lots
(`whole_odd_remainder_only`), T+1; calendar 2024-03-18 … 03-22, 03-25 … 03-27; policy `HYPOTHETICAL_RISK_POLICY_A`:
position weight 0.20, gross exposure 0.60, cash reserve 0, stop 5 %, target 10 %, max holding 5 sessions, cooldown 2 sessions,
mark age 0, gap 2 %, intent expiry 1 session, priority stop_loss > profit_target > max_holding.

## 1. End-to-end: decision → sizing → kernel → ledger → exit → cooldown → valuation / benchmark [`e2e.hand_calculated`]

| Step | Arithmetic | Result |
|---|---|---|
| D1 (03-18 close, cash 100 000): signal A, mark 10.00 | rooms: position 0.20 × 100 000 = 20 000; portfolio 0.60 × 100 000 = 60 000; cash 100 000 → budget **20 000.00**. Reserved price ceil_tick(10.00 × 1.001) = 10.01; floor(20 000 / 10.01) = 1998 → 1900; estimate 1900 × 10.01 = 19 019.00 + max(5.7057 → 5.71, 5.00) + 0.19 = **19 024.90** ≤ 20 000 | intent buy **1900**, limit ceil_tick(10.00 × 1.02) = 10.20, reserved 20 000.00 |
| X1 (03-19 open print 10.05) | kernel fill ceil_tick(10.05 × 1.001 = 10.06005) = **10.07**; re-check 1900 × 10.07 = 19 133.00 + max(5.7399 → 5.74, 5.00) + 0.19 = **19 138.93** ≤ 20 000 → full 1900 | cash 100 000 − 19 138.93 = **80 861.07**; lot cost 19 138.93; entry reference 19 138.93 / 1900 = **10.0731** |
| D2 (03-19 close, mark 10.30) | value 1900 × 10.30 = 19 570.00; equity 80 861.07 + 19 570.00 = **100 431.07**; weight 19 570 / 100 431.07 = **0.194860**; stop 10.0731 × 0.95 = 9.5695 (no), target 11.0804 (no), held 0 | hold |
| D3 (03-20 close, mark 9.50) | 9.50 ≤ 9.5695 → **stop_loss**; limit floor_tick(9.50 × 0.98 = 9.31) = 9.31 | exit intent sell 1900 |
| X2 (03-21 open print 9.40) | fill floor_tick(9.40 × 0.999 = 9.3906) = **9.39**; gross 17 841.00; commission max(5.3523 → 5.35, 5.00) = 5.35; transfer 0.18; stamp 8.9205 → 8.92; fees **14.45**; proceeds **17 826.55** | cash 80 861.07 + 17 826.55 = **98 687.62**; realized 17 826.55 − 19 138.93 = **−1 312.38**; position 0; cooldown from 03-21 |
| D4 (03-21) / D5 (03-22) signals | 0 and 1 of 2 cooldown sessions elapsed | refused `cooldown_active` |
| D6 (03-25, mark 9.80) | index(03-25) − index(03-21) = 2 → allowed; equity 98 687.62 → position room 19 737.524 → budget **19 737.52**; reserved price ceil_tick(9.80 × 1.001 = 9.8098) = 9.81; floor(19 737.52 / 9.81) = 2011 → 2000; estimate 19 620.00 + max(5.886 → 5.89, 5.00) + 0.20 = **19 626.09** | intent buy **2000**, limit ceil_tick(9.80 × 1.02 = 9.996) = 10.00 |
| Performance at 03-21 close | equity 98 687.62 → return (98 687.62 − 100 000) / 100 000 = **−0.013124**; benchmark 2960 / 3000 − 1 = **−0.013333** | complete, benchmark observed |

## 2. Sizing boundaries [`test_exact_exposure_boundary_and_zero_size`, `sizing.shared_reservations`, `sizing.gap_recheck`, `sizing.partial_and_release`]

* Cash 10 000: position room 2 000.00 → floor(2 000 / 10.01) = 199 → **100**; estimate 1 001.00 + 5.00 + 0.01 = **1 006.01**. Cash 5 000: room 1 000.00 < 1 006.01 → **zero_size** (no forced lot). Exact boundary: cash 5 030.05 → room 1 006.01 → 100 shares; cash 5 030.00 → room 1 006.00 → zero_size.
* Two simultaneous signals (position cap 0.50, gross cap 0.60, cash 100 000): A first (stable order) reserves 50 000.00; B then sees portfolio room 60 000 − 50 000 = **10 000.00** (cash room 50 000.00) → reserved price ceil(20.00 × 1.001) = 20.02; floor(10 000 / 20.02) = 499 → **400**; estimate 8 008.00 + 5.00 + 0.08 = **8 013.08**. Total reserved 60 000.00; a later signal on A is refused `symbol_pending_intent`.
* Gap re-check (position cap 0.30 on cash 10 000 → budget 3 000.00, intent 200 at reserved 10.01): print 14.99 → fill 15.01; 200 × 15.01 = 3 002.00 + 5.00 + 0.03 > 3 000 → **downsized to 100** (1 501.00 + 5.00 + 0.02 = 1 506.02); with limit 10.20 the kernel leaves it unfilled → expired, reservation released. With gap tolerance 50 % (limit 15.00): print 29.99 → fill 30.02 → one lot 3 002.00 + 5.00 + 0.03 > 3 000 → **cancelled** `gap_exceeds_budget`; print 14.97 → fill 14.99 → 200 × 14.99 = 2 998.00 + 5.00 + 0.03 = 3 003.03 > 3 000 → **100** shares filled at 14.99: 1 499.00 + 5.00 + 0.01 = 1 504.01; cash **8 495.99**.
* Partial fill: 1900-share intent, capacity 1000 at 10:00 → 1000 filled, remaining 900, reservation 20 000.00 retained; second attempt fills 900 → released. A suspended-at-open one-session intent → `expired`, reservation released; a kernel-rejected attempt (phase mismatch) → intent `pending`, reservation retained.

## 3. Exits, cooldown [`exits.stop_next_open`, `exits.partial_and_cooldown`, priority test]

* Held 1000 @ cost 10 073.12 (ref 10.0731, stop 9.5695): close 9.60 → hold (an intraday touch is not consulted); close 9.56 → stop, limit floor_tick(9.56 × 0.98 = 9.3688) = **9.36**. Open print 9.30 → fill 9.29 < 9.36 → unfilled, expired; position stays 1000, no cooldown. Next decision (close 9.30) re-issues the exit; open 9.35 → fill floor_tick(9.35 × 0.999 = 9.34065) = **9.34**; cooldown starts 03-22.
* Priority: close 11.09 ≥ 10.0731 × 1.10 = 11.0804 → profit_target when it precedes stop_loss; entry 03-18 with max holding 3 → hold at 03-20 (2 sessions), max_holding at 03-21 (3); stop and max_holding coinciding → the policy order decides.
* Partial exit: 600 of 1000 filled → residual 400, no cooldown; duplicate attempt id → `duplicate`, no ledger call; remainder fills → cooldown from 03-20; re-entry refused at 03-21 (1 of 2), allowed at 03-22 (2 of 2).
* Suspension → exit `expired` (position kept); limit-down with a 2-session intent → `unfilled_live`, no cooldown.

## 4. Benchmark and delisting [`test_benchmark_missing_is_not_zero…`, `delisting.unresolved`]

* Levels 3000.00 (03-18), 2960.00 (03-21): return **−0.013333**; 03-20 missing → `missing`, return null; a 03-22 level available at 16:30 for a 16:00 decision → `future_evidence`; a signal on the index → `benchmark_symbol`.
* Held 1000 A (cost 10 073.12): a `delisting_announced` status available 16:30 is refused at a 16:00 decision (A still `listed`, valued at 10.00 → equity 110 000, B sized with room 22 000.00); once available, B's buy is refused `security_not_tradable`; `delisted` on 03-21 → A unresolved, valuation incomplete, performance `equity=null`, ledger cash 100 000.00 unchanged; hypothetical terminal mark 0.00 → separately labelled scenario equity 100 000.00; earlier record hashes unchanged.

## 5. Determinism [`test_later_information…`, `test_numeric_spelling…`, `test_views_are_detached…`]

Two engines fed the same three events produce identical records and chain hashes; appending D3/X2 leaves the first three unchanged; `Decimal("100000")` / `Decimal("10")` / `3000` / `Decimal("10.050")` under a caller context of precision 6 with `ROUND_DOWN` and `Inexact` trapped produce the same record hashes; mutating returned records/intents changes nothing; a refused execute is an audit record only.
