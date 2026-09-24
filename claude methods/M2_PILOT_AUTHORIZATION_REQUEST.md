# M2 pilot — authorization request (rev. 2)

**Status: NOT executable as written. Two prerequisites below must be closed first; authorization is requested for the plan, not for an immediate run.** Nothing has been fetched, written or started.

Scope: a **staging-only** collection of the already-approved 50 stocks + `SH000300` + `SH000001`, validated through the accepted M1 gate. Full-market rebuild, production promotion, training, service startup and Git operations are excluded and each remains a separate decision.

M1 is validated for the data-contract and staging-acceptance scope only — the contract and its rejection behaviour, not the corpus.

---

## 1. Pinned parameters

| Parameter | Value |
|---|---|
| **Population** | Unchanged: 50 stocks + `SH000300` + `SH000001` (`_m1_closure/pilot_symbols.csv`, sha256 `97e251ae84fc9274…`) |
| **Research interval** | 2023-09-04 .. 2026-09-04 — **728 sessions** |
| **Warm-up interval** | 2022-08-24 .. 2023-09-01 — **250 sessions**, ending strictly before the research start |
| **Pinned calendar** | sha256 `f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656` (offline audit reference, not the runtime calendar) |
| **Consumed views** | both — `--history-scope all`, `--warmup-consumers both` |
| **Price representation** | raw / unadjusted in both views with `amount` — **but see prerequisite P1: the current ingestion path cannot yet label this `none`** |
| **Adjusted (qfq)** | out of scope — no local factor series, so cross-view reconciliation would correctly block |
| **Staging destination** | `D:\codex-A股交易\staging\pilot_20260906\{pilot_trading,pilot_history}.sqlite3`, created only on authorization |
| **Production** | opened read-only for baseline fingerprinting; never written, migrated or promoted |
| **Expected volume** | 36,193 research + 9,742 warm-up = **45,935 eligible records per view** |

---

## 2. Acceptance procedure — warm-up integrity is blocking, depth is not

**Correction, stated plainly: the existing flag does *not* provide this separation.** In `staging_gate.py`, `W1_pricing`, `W1_history`, `W2` **and** `V3b` are all registered with `required=warm_required`. Omitting `--warmup-required` makes warm-up *integrity* advisory too, which would let corrupt or divergent warm-up data pass unremarked. The previous revision was wrong to present that as an acceptable separation.

The separation is therefore enforced by the **acceptance rule**, evaluated over per-gate statuses rather than the exit code alone:

**Run A — research interval, blocking.**
No warm-up flags. Every required gate must be PASS/NOT_APPLICABLE (`M1`,`M2`,`M3` membership and per-key completeness in both views; `P1`–`P6`; `H1`–`H5`; `X1`,`X2`). Exit 0 required.
**`P4` must move from UNKNOWN to PASS.** If the collected data still cannot verify volume units, the pilot has not achieved its purpose — reported as failure, not waived.

**Run B — warm-up, run *with* `--warmup-required` so integrity is enforced.**
```
… --warmup-consumers both --warmup-start 2022-08-24 --warmup-sessions 250 --warmup-required
```
Accepted **only if all** of the following hold:
1. `W1_pricing` = PASS — warm-up eligible-key completeness in the pricing view
2. `W1_history` = PASS — same in the research-history view
3. `W2` = PASS — cross-view warm-up identity over `open,high,low,close`
4. `V3b` is the **only** failing required gate, and its shortfall set is **exactly** the 14 securities pre-published below

Exit 1 is expected for Run B and is accepted **only** under that condition. Any `W1`/`W2` failure, or any `V3b` shortfall outside the pinned list, is a genuine failure. Research-only success (Run A) does **not** certify warm-up data; both runs are reported together.

### Pre-published warm-up shortfall (pinned, so it cannot be padded afterwards)

Zero eligible warm-up sessions — listed after 2022-08-24 (12):
`BJ920002 BJ920003 BJ920005 BJ920007 BJ920519 BJ920627 SH603075 SH688549 SH688702 SZ301251 SZ301507 SZ301529`

Partial (2): `BJ920001` = 167 sessions, `BJ920006` = 75 sessions.

Full 250-session depth attainable: **36 of 50**. No download can fix the other 14 — they did not exist. Shrinking the population or lowering the depth to hide this is refused. **No feature-readiness claim is made for any stock.**

---

## 3. Request budget — jobs, provider calls and HTTP attempts are different things

Measured from the installed code, not inferred.

| Layer | Stocks (50) | Benchmarks (2) | Total |
|---|---|---|---|
| Symbol jobs | 50 | 2 | **52** |
| Provider calls | 50 × `stock_zh_a_daily(adjust="")` | 2 × `stock_zh_index_daily` | **52** |
| **HTTP attempts, no retries** | 50 × **2** = 100 | 2 × **1** = 2 | **102** |
| Ceiling with 3 attempts/job | 300 | 6 | **306** |

`stock_zh_a_daily` with `adjust=""` issues **two** GETs per call — the price history (`…/hisdata_klc2/klc_kl.js`) and the outstanding-share/amount series (`StockService.getAmountBySymbol`) — at `stock_zh_a_sina.py:177` and `:196`. A `qfq`/`hfq` call would add a **third** for the factor (`:150`/`:162`); that path is out of scope. `stock_zh_index_daily` issues **one**.

**One combined fetch, not two.** Neither Sina URL takes a date parameter; the whole series is returned and `stock_zh_a_daily` slices it client-side (`temp_df[start_date:end_date]`, `:220`). Research and warm-up therefore come from a *single* call per symbol — the 250 warm-up sessions add **zero** extra HTTP attempts.

**Pagination: none available.** The Sina path has no pagination (full series in one response). The Tonghuashun path has none either — see §4 — so it contributes no usable calls and has been **removed from the plan**; the fallback budget is 0.

Pinned execution limits:

| Control | Value |
|---|---|
| Concurrency | 1 in-flight request per source (`max_workers = 1`); no parallel fan-out |
| Pacing | ≥ 1.5 s between Sina calls; ≥ 1.0 s for the Tonghuashun client throttle if it is ever re-enabled |
| Timeouts | connect 10 s, read 30 s, finite on every attempt; no unbounded waits |
| Retries | ≤ 3 attempts per symbol job, backoff 2 s / 8 s / 32 s, retry only on timeout/5xx/connection reset — never on a 4xx or an empty frame |
| Hard ceiling | **306** HTTP attempts for the whole run; the run aborts on reaching it |
| Stop conditions | abort on 20 consecutive symbol-job failures, on any 403/429, or on the ceiling — and report, rather than continuing into a rate-limited hole |
| Attribution | every batch records the source that actually served it; a fallback-served run is reported as a fallback run |

**No safe vendor quota is inferred from observed throughput.** The earlier 0.45–0.79 symbols/s figure is our own historical observation and says nothing about what the vendor permits; akshare's own docstring for this endpoint warns that bulk fetching readily gets an IP banned (`stock_zh_a_sina.py:134`). The pacing above is deliberately slower than anything previously observed, and measuring real limits is not a goal of this pilot.

---

## 4. Source capability — unresolved gaps, failing closed

| Path | Finding (from code) | Consequence |
|---|---|---|
| **Tonghuashun** `get_candles` | `limit = max(1, min(int(days), 500))`; `startTimeUtc: None`, `endTimeUtc: None`; `frame.tail(limit)` (`tonghuasun_provider.py:214-247`) | **Capped at 500 bars, no date-bounded pagination, tail-only.** The window needs 978 sessions. It **cannot** serve the full window and is **not** a proven fallback. Removed from the plan; capability left UNRESOLVED. |
| **Sina raw basis label** | `frame.attrs["adjustment_mode"] = "qfq" if adjust == "qfq" else "unknown"` (`akshare_provider.py:114`) | A raw call is labelled **`unknown`**, not `none`. `basis_gate` requires the *stored* basis to equal the declared one, so declaring `--pricing-basis none` against `unknown` rows fails — correctly. **Prerequisite P1 below.** |
| **Sina raw dedup** | `drop_duplicates(subset=["open","high","low","close","volume","amount"])` (`stock_zh_a_sina.py:222`) | Two genuinely identical sessions (e.g. a limit-locked or thin day) are silently dropped, producing missing keys that the gate will correctly fail. Known hazard; must be measured on the pilot, not worked around. |
| **Benchmark path** | `stock_zh_index_daily` returns date/open/high/low/close/volume — **no `amount`** (`index_stock_zh.py:299-316`) | Benchmarks cannot supply amount. They are already excluded from `P4` by the accepted F4 routing; no liquidity evidence is invented for them. |

### Prerequisites that block execution

- **P1 — raw-basis provenance.** The pilot cannot declare `--pricing-basis none` until the raw request/response path is validated and the stored `adjustment_mode` is *derived from the verified path*, not stamped. Stamping `none` on rows the adapter labelled `unknown` would defeat the gate that exists to catch exactly this. Closing P1 is a runtime change and is **not** requested or authorized here.
- **P2 — no full-window FALLBACK (a declared limitation, not a blocker to fix).** The primary path can supply the whole window: one `stock_zh_a_daily` call returns the entire series and is sliced client-side. What is missing is a *second* source able to do the same — the Tonghuashun adapter caps at 500 bars. Correcting my rev.2 wording: it was wrong to say *no* source can supply 978 sessions. This is a declared single-source limitation, and it is **not** a requirement to develop another provider. If the primary fails for a symbol, that job is a reported failure; no substitute is invented and no source is built to rescue it.

Until P1 and P2 are resolved, the honest expected outcome of Run A is `P6`/`H5` FAIL (stored basis `unknown` ≠ declared `none`) or `P4` UNKNOWN. That is the correct fail-closed behaviour and is stated here rather than discovered mid-run.

---

## 5. Rollback

The pilot writes only inside `staging\pilot_20260906\`; rollback is deleting that directory. `snapshot` refuses a `--baseline-out` that equals or aliases an archive or the calendar, with or without `--force` (15 path-safety checks). `validate` writes nothing and re-verifies both production archives against the frozen baseline on every run. No promotion step is included.

---

## 6. Limitations, not waived

Strict point-in-time evidence remains absent and cannot be created retroactively. Historical universe, ST history, suspension calendar, delisting register and BJ pre-2024-08-12 code mapping remain **UNKNOWN**; survivorship stays unquantifiable and gap causes stay `unknown`. Volume-unit evidence is UNKNOWN for the whole corpus and stays so unless raw price with amount arrives under a validated basis label; the 293 STAR-board near-100× boundary events remain a **hypothesis to test**, and nothing is rescaled on suspicion. Identity is the only supported cross-view transformation. Volume and amount are not reconciled across views. The 746 legacy evaluations and A2 remain a separate prerequisite. M1 validates the contract, not the corpus: 52 symbols say nothing about the other ~5,500, nor about strategy performance.

---

## 7. What is being asked

> Approve this plan — population, intervals, views, representation, budget, limits and acceptance rule — **and note that execution is blocked on P1 and P2**, which require a separate authorized change.

On execution authorization, after P1/P2 are closed, I will run the collection and both validation runs and report actual gate results — including failures, unresolved evidence and the pinned warm-up shortfall — without adjusting population, depth or thresholds to produce a pass.

Until then: no network or plugin call, no download, no dataset or production write, no runtime edit, no service, no staging directory, no commit, no push.
