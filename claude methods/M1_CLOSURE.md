# M1 收口报告（bounded closure，回应 Codex 2026-09-06 独立复核）

- Status: **`validated`** by Codex on 2026-09-06 for the M1 data-contract and staging-acceptance scope (`M1_ACCEPTANCE_CODEX.md`). Not user acceptance, not dataset certification, not training readiness, and not authorization to begin M2. The next decision is the user's, on `M2_PILOT_AUTHORIZATION_REQUEST.md`.
- (原状态：`ready_for_review`)
- 范围：仅 R1–R4 四项收口。未重启审计、未新增多智能体审查、未改动运行时代码、未触碰生产库/数据集/方法论/知识库、无网络与插件调用、无迁移、无服务启动、无 commit/push。
- **执行路径唯一性**：本文件与 `_m1_closure/` 是**当前唯一可执行路径**。`M1_THREE_YEAR_DATA_READINESS.md` 保留为历史诊断材料；其第 9.6 节验收指令、`_m1_evidence/backfill_acceptance.sql`、`coverage_05_manifest.py`、`coverage_manifest.csv`、`coverage_gap_shape.csv` **全部作废**（已重命名为 `*.SUPERSEDED.*`）。Codex 指出"修正前言不能使冲突的执行指令变安全"，因此这里不是加一段说明，而是把旧执行入口移除。

---

## K1 empty-eligible-domain closure (2026-09-06, responding to `M1_K1K2_PROGRESS_CODEX_REVIEW.md`)

> Status: `ready_for_review`. This section is the **current execution contract**. Preserved unchanged: the K1 key-direction fix, the K2 warm-up consumer contract, G3 protections, M0, the accepted coverage census, and the selected 50 stocks plus `SH000300`/`SH000001`. All 55 previous end-to-end checks still run and pass; the suite is now **67**.

### The defect

`expected_key_map()` moved a known security with zero eligible sessions into a side list and omitted it from `expected`, while `membership_gate()` still required every declared security to appear. The outcome was inverted:

| Synthetic contract for one selected identifier | Records in the research interval | Before | After |
|---|---|---|---|
| Listed 2026-09-07 (after the window) | correctly empty in both views | exit 1, reported as **absent data** | exit 1, **manifest rejected** and named |
| Same | one ineligible 2025-06-10 record in each view | **exit 0** | exit 1, record named as ineligible |
| Listed 2000-01-01, delisted 2023-09-01 (before the window) | correctly empty in both views | exit 1, reported as absent data | exit 1, manifest rejected and named |
| Same | one ineligible 2025-06-10 record in each view | **exit 0** | exit 1, record named as ineligible |

Inserting invalid data turned a rejection into a success. That is now impossible.

### The fix

| Change | File:line |
|---|---|
| A known-empty eligible set is **kept** in `expected` as an empty set rather than dropped, so observed keys are still compared against it | `staging_gate.py:182`, `:200` |
| Only a security that **owes** eligible records can be "absent"; a known-empty one is *correctly* absent | `staging_gate.py:248` |
| `empty_domain` policy per interval: `reject` on the research interval (a pilot member contributing no eligible research record is a **manifest** error, rejected independently of the data) and `allow` on warm-up (a security listed after the warm-up interval legitimately supplies none) | `staging_gate.py:271`, `:609` |
| Known-empty (`known_empty` / `correctly_empty`) is reported separately from UNKNOWN (`unresolved`); the two are never conflated | `staging_gate.py:271` |

Under **both** policies an observed record inside an empty domain fails and names the security and session. The research rejection is data-independent: the empty case and the injected case both exit 1, for stated and different reasons.

### Research vs warm-up, kept distinct

An IPO listed after the warm-up interval has an **empty warm-up domain**, which is legitimate: `W1_*` reports `correctly_empty=1 empty_domain=allow` and does not fail on coverage. The same security still **fails required feature depth** at `V3b`. Complete eligible coverage and sufficient feature observations remain separate outcomes, and the suite asserts both on the same run.

### Exact commands and actual results

From `claude methods/_m1_closure/` with the project interpreter:

```bash
../../backend/.venv/Scripts/python.exe -B -X utf8 coverage_gap_generator.py   # exit 0, identity 3900763 == 3900763
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py        # exit 0, 13/13
../../backend/.venv/Scripts/python.exe -B -X utf8 acceptance_runner.py        # exit 0, DIAGNOSTIC only
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py    # exit 0, 46 cases, 0 unexpected
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py    # exit 0, 67 checks, 0 unexpected
../../backend/.venv/Scripts/python.exe -B -X utf8 pilot_selection.py          # exit 0, 50 stocks + 2 benchmarks
```

New checks (12), all passing:

```
[ok] K1e listed entirely AFTER the research window, correctly empty, is rejected on the MANIFEST   exit=1
[ok] K1e listed entirely AFTER the research window, correctly empty, is not reported as absent data
[ok] K1e listed entirely AFTER the research window, INJECTED record in both views, still fails     exit=1
[ok] K1e injected record is named as ineligible
[ok] K1e delisted entirely BEFORE the research window, correctly empty, is rejected on the MANIFEST exit=1
[ok] K1e delisted entirely BEFORE the research window, correctly empty, is not reported as absent data
[ok] K1e delisted entirely BEFORE the research window, INJECTED record in both views, still fails   exit=1
[ok] K1e injected record is named as ineligible
[ok] K1e empty WARM-UP domain is allowed, not a coverage failure          BJ920002 listed 2024-05-30
[ok] K1e that security still FAILS required feature depth (distinct outcome)  exit=1
[ok] K1e an ineligible WARM-UP record still fails and is named                exit=1
[ok] K1e unknown eligibility stays UNRESOLVED, distinct from known-empty      exit=1
```

The synthetic contracts reuse selected identifiers with **disposable** listing metadata in temporary manifests. The approved manifest is never modified, and these say nothing about any security's real listing history.

### Accepted note on V3b

`V3b` reports observation depth and can PASS while `W2` identity fails; overall validation still fails because both are required gates. The V3b count is **not** a standalone feature-readiness verdict and must not be consumed as one — the required gates have to pass together.

### Remaining limitations

1. Strict-PIT admissible rows remain **0** in the local corpus and cannot be created retroactively; only future collection can carry observed-availability evidence. This is not proof that external archived or dated source evidence could never supply it.
2. Historical universe, ST history, suspension calendar, delisting register and BJ pre-2024-08-12 code mapping remain **UNKNOWN**. Rejecting a record outside a declared interval is a statement about the **declared contract**, not a claim that such an observation is intrinsically fake; genuine predecessor or venue history would need its own evidenced, separately approved mapping, and none is invented.
3. `identity` is the only supported transformation; a real qfq↔raw reconciliation needs a declared factor series that does not exist locally, so the gate blocks rather than assuming comparability.
4. Identity covers `open,high,low,close`. Volume and amount are deliberately **not** reconciled across views because the stores legitimately differ on unit and amount availability; unit correctness is handled by `P4` and remains quarantined.
5. `--history-scope` and `--warmup-consumers` must be **declared**, not inferred.
6. On the current corpus every stock is short of a 250-session warm-up. That is reported rather than waived, and no feature- or training-readiness claim is made.
7. No backend regression suite was rerun because no runtime code was changed.

M2 remains unauthorized and M1 is not self-approved. Pilot execution requires separate user authorization after Codex acceptance; full-market rebuild, training-readiness claims and production promotion remain separate decisions.

---

## (superseded) K1 / K2 closure (2026-09-06, responding to `M1_KEY_CONTRACT_CODEX_REVIEW.md`)

> Status: `ready_for_review`. This section is the **current execution contract**. Preserved unchanged: G3 protections, the verified G1a/G1b/G2a/G2b behaviours, M0, the accepted coverage census, and the selected 50 stocks plus `SH000300`/`SH000001`. Nothing was restarted.

### Resolution table

| ID | Defect Codex reproduced | Fix | File:line | Real-CLI regressions |
|---|---|---|---|---|
| **K1** | `membership_gate` computed `want - seen` but never `seen - want`, and `identity_gate` only compared the two views to each other. Adding `BJ920002 / 2024-05-29` — one day before its declared listing date — to **both** views gave 36,194 records each and still **exited 0**. | Keys are compared in **both directions within each gate's own interval**. A record inside the interval that is not an eligible session is an `ineligible_records` violation, reported separately from missing keys and unexpected symbols. Two copies agreeing proves nothing about eligibility. | `staging_gate.py:205` (`membership_gate`), `:239` (`extra = got - want`) | 3 |
| **K2** | Readiness counted `daily_bar_cache` only and identity covered the research window only. Deleting **all** pre-window history while keeping pricing warm-up still returned exit 0 with V3b "ready"; changing a warm-up high went unnoticed. | The feature-warm-up consumer boundary must be **declared** (`--warmup-consumers pricing\|history\|both`) — omitting it while requesting warm-up is exit 2. Every declared consumer view is validated for warm-up eligibility and completeness (`W1_*`); `both` additionally reconciles warm-up identity (`W2`); a non-consumed view is reported `NOT CONSUMED` rather than silently certified; readiness counts **eligible** observations in the declared view(s) and states its scope. | `staging_gate.py:379` (declaration forced), `:563` (consumer map), `:581` (`NOT CONSUMED`), `:592` (`W2`), `:615` (`V3b` scoped) | 9 |

### The declared warm-up consumer contract

`--warmup-consumers` is mandatory whenever any warm-up option is supplied. It selects which view(s) are treated as the feature source, and everything downstream follows from it:

| Declared | Validated over the warm-up interval | Reported as not consumed | Readiness scope |
|---|---|---|---|
| `pricing` | `daily_bar_cache` membership + eligible-key completeness | `daily_bars` → `NOT_APPLICABLE`, explicitly **not certified** | `scope=pricing`; must not be read as history or both-view readiness |
| `history` | `daily_bars` membership + eligible-key completeness | `daily_bar_cache` → `NOT_APPLICABLE` | `scope=history` |
| `both` | both views' membership **plus** `W2` warm-up identity reconciliation over `open,high,low,close` | — | `scope=both`; a security is ready only if the **weakest** consumer view supplies enough eligible observations |

Two distinctions are preserved deliberately:

- **Eligible price coverage (`M1`) is not feature readiness (`V3b`).** A new listing can hold every eligible research record and still be short of 250 warm-up observations. The suite proves this: `BJ920002` (listed 2024-05-30) passes M1 in full and fails V3b, and the failure text says so.
- **Readiness counts eligible observations only.** Dates present before a security's listing are not evidence of warm-up depth; they are K1 violations.

### Exact commands and actual results

From `claude methods/_m1_closure/` with the project interpreter:

```bash
../../backend/.venv/Scripts/python.exe -B -X utf8 coverage_gap_generator.py   # exit 0, identity 3900763 == 3900763
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py        # exit 0, 13/13
../../backend/.venv/Scripts/python.exe -B -X utf8 acceptance_runner.py        # exit 0, DIAGNOSTIC only
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py    # exit 0, 46 cases, 0 unexpected
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py    # exit 0, 55 checks, 0 unexpected
../../backend/.venv/Scripts/python.exe -B -X utf8 pilot_selection.py          # exit 0, 50 stocks + 2 benchmarks
```

### Test preservation — 36 → 55, as a superset

The review correctly noted that an unchanged count of 36 did not prove earlier scenarios survived. The suite is now explicitly labelled by originating round, and the cases that had been dropped are **restored and marked `[restored]`**:

| Block | Cases | Note |
|---|---|---|
| G3 path safety | 15 | retained unchanged |
| G2a actual 50+2 manifest | 3 | clean control still passes at 36,193 records/view |
| **K1 key domain** | **3** | new |
| G1a membership | 4 | retained |
| G1b representation/identity | 5 | retained |
| **G1r restored** | **8** | malformed history date, nonpositive history price, duplicate history key, dangling `ingest_run_id`, missing transformation, unsupported transformation, mismatched bases, unknown eligibility |
| **K2 warm-up consumers** | **9** | new |
| G2b warm-up config | 3 | restored |
| invariants | 5 | baseline, archive hashes, production |

Selected results:

```
[ok] G2a ACTUAL 50+2 manifest with complete data SUCCEEDS   exit=0, 50 stocks + 2 benchmarks, 36193 records/view
[ok] K1 pre-listing record present in BOTH views fails      exit=1, BJ920002 @ 2024-05-29 (declared list_date 2024-05-30), 36194 records/view
[ok] K1 the ineligible record names the security and session
[ok] K1 declared post-delisting record fails                exit=1, BJ920002 @ 2025-01-13 (declared delist 2025-01-10)
[ok] K2 warm-up requested without --warmup-consumers is an input error
[ok] K2 clean eligible warm-up in BOTH views is ready        exit=0, 4 securities
[ok] K2 absent HISTORY warm-up blocks when history is a declared consumer   exit=1
[ok] K2 same data passes when only pricing is declared consumed             exit=0
[ok] K2 the unconsumed view is declared, not silently certified
[ok] K2 divergent WARM-UP high blocks when both views are consumed          exit=1
[ok] K2 the same divergence is out of scope for a pricing-only contract     exit=0
[ok] K2 legitimate warm-up is not counted as an unexpected research record  exit=0
[ok] K2 new listing: complete M1 coverage but insufficient warm-up is FAIL  exit=1 (BJ920002 listed 2024-05-30)
[ok] K2 that shortfall is stated as readiness, not as missing coverage
[ok] G1r [restored] malformed HISTORY date fails
[ok] G1r [restored] unknown eligibility is UNRESOLVED, not complete         exit=1
```

The K2 warm-up scenarios use a **disposable diagnostic subset** of two pre-window-listed stocks plus the two benchmarks, purely to isolate warm-up behaviour. It is never proposed as the pilot; the approved population is unchanged at 50 + 2, and the research-window control still runs on the actual delivered manifest.

### Protected inputs

Frozen baseline byte-identical and both archive SHA-256 values unchanged after every validation; all 15 G3 rejections still assert the target file is untouched. Both production databases unchanged in size and mtime across the whole run; the pinned calendar hash remains `f1f1ce33c5cceb5c…`.

### Remaining limitations

1. Strict-PIT admissible rows remain **0** in the local corpus and cannot be created retroactively; only future collection can carry observed-availability evidence. This is not proof that external archived or dated source evidence could never supply it.
2. Historical universe, ST history, suspension calendar, delisting register and BJ pre-2024-08-12 code mapping remain **UNKNOWN**. K1 rejects pre-listing records under the *declared* contract; it is **not** a claim that such observations are intrinsically fake. Genuine predecessor or venue history would need its own evidenced, separately approved mapping, and none is invented here.
3. `identity` is the only supported transformation. A real qfq↔raw reconciliation needs a declared factor series that does not exist locally, so the gate blocks rather than assuming comparability.
4. Identity covers `open,high,low,close`. Volume and amount are deliberately **not** reconciled across views, because the two stores legitimately differ on unit and amount availability; unit correctness is handled by `P4` and remains quarantined for the current corpus.
5. The history scope (`--history-scope`) and the warm-up consumers (`--warmup-consumers`) must be **declared**, not inferred. A wrong declaration surfaces as unexpected/absent symbols rather than silently passing.
6. On the current corpus every stock is short of a 250-session warm-up, which is reported rather than waived. No feature-readiness or training-readiness claim is made.
7. No backend regression suite was rerun because no runtime code was changed.

M2 remains unauthorized and M1 is not self-approved. Pilot execution requires separate user authorization after Codex acceptance; full-market rebuild, training-readiness claims and production promotion remain separate decisions.

---

## (superseded) G1a / G1b / G2a / G2b closure (2026-09-06, responding to `M1_G_CLOSURE_CODEX_REVIEW.md`)

> Status: `ready_for_review`. This section is the **current execution contract**. G3 is accepted and retained unchanged, as are the 13 temporal checks, 46 primitive checks, M0, the accepted coverage census and the selected 50 pilot securities. Nothing was restarted.

### Resolution table

| ID | Defect Codex reproduced | Fix | File:line | Real-CLI regressions |
|---|---|---|---|---|
| **G1a** | H0 compared only distinct symbol/session counts and X2 used an inner join, so deleting one history record (H0 still 5/728) and substituting a whole 728-row series with `XX123456` both **exited 0**. | Expected keys derived from the **manifest**, never from observed data. `membership_gate` compares actual key sets per security in **both** views and reports missing *and* unexpected symbols in both directions; `identity_gate` compares the full key union, not an inner join. | `staging_gate.py:182` (`expected_key_map`), `:205` (`membership_gate`), `:280` (`identity_gate`), `:484` (M1/M2/M3) | 4 |
| **G1b** | X1 trusted the `--pricing-basis` / `--history-basis` **arguments**: history stored entirely as `qfq` passed while both bases were declared `none`. X2 compared `close` alone, so changing a high from 11→12 with the same close passed as "identity reconciled". | `basis_gate` reads the **stored** `adjustment_mode` per view, rejects disagreement with the declaration and rejects mixed bases. Identity reconciles the declared field list `open,high,low,close` at an explicit tolerance (`--identity-tolerance`, default 0.005). | `staging_gate.py:259` (`basis_gate`), `:280` (`identity_gate`), `:478` (P6), `:504` (H5), `:528` (X2) | 5 |
| **G2a** | The delivered manifest leaves `list_date` blank for `SH000300`/`SH000001`, and the stock listing rule was applied to them, so **complete** benchmark data returned V2 UNKNOWN and the command exited 1. My earlier "clean" tests hid this by inventing index IPO dates. | Benchmarks carry their own `benchmark_research_window` eligibility contract — the full research window, honouring a `list_date` only if one is present. No IPO date is fabricated and neither index is removed. The clean control is now driven by the **actual delivered manifest**. | `staging_gate.py:131` (`load_manifest`), `:157` (`entry_eligibility`) | 2 |
| **G2b** | `--warmup-required --warmup-sessions 250` with no `--warmup-start` returned **exit 0** with V3 downgraded to NOT_APPLICABLE. | `resolve_warmup` derives the interval from the pinned calendar when a depth is given, and raises an input error (exit 2) when the required configuration is incomplete. A required warm-up can no longer become advisory. Feature readiness (V3b) is reported separately from eligible price coverage (M1). | `staging_gate.py:361` (`resolve_warmup`), `:548` (V3b) | 5 |

### Exact commands and actual results

From `claude methods/_m1_closure/` with the project interpreter:

```bash
../../backend/.venv/Scripts/python.exe -B -X utf8 coverage_gap_generator.py   # exit 0, identity 3900763 == 3900763
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py        # exit 0, 13/13
../../backend/.venv/Scripts/python.exe -B -X utf8 acceptance_runner.py        # exit 0, DIAGNOSTIC only
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py    # exit 0, 46 cases, 0 unexpected
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py    # exit 0, 36 checks, 0 unexpected
../../backend/.venv/Scripts/python.exe -B -X utf8 pilot_selection.py          # exit 0, 50 stocks + 2 benchmarks
```

### Clean and corrupted fixtures through the real CLI (36/36, exit 0)

The clean control is the **actual `pilot_symbols.csv`**: 50 stocks + `SH000300` + `SH000001`, with all eligible research records materialised in both views — **36,193 records per view** — reconciled under a declared `identity` on a common `none` basis.

```
[ok] G2a ACTUAL 50+2 manifest with complete data SUCCEEDS      exit=0, 50 stocks + 2 benchmarks, 36193 records/view
[ok] G2a benchmarks resolved without a fabricated IPO date
[ok] G2a missing required BENCHMARK session fails              exit=1
[ok] G1a single missing HISTORY record fails (marginal counts unchanged)      exit=1
[ok] G1a the missing record is named, not just counted
[ok] G1a substituted HISTORY symbol fails (symbol/session counts unchanged)   exit=1
[ok] G1a substitution reported in both directions
[ok] G1b stored history basis 'qfq' vs declared 'none' fails   exit=1
[ok] G1b MIXED stored bases in one view fails                  exit=1
[ok] G1b changed open with close unchanged fails identity      exit=1
[ok] G1b changed high with close unchanged fails identity      exit=1
[ok] G1b changed low  with close unchanged fails identity      exit=1
[ok] G2b required warm-up without --warmup-start is not silently advisory     exit=1
[ok] G2b --warmup-required with no depth and no start is an input error       exit=2
[ok] G2b advisory warm-up does not block a clean run           exit=0
[ok] G2b non-overlap with the research window is asserted
[ok] G2b feature readiness is stated separately from price coverage
[ok] frozen baseline byte-identical after every validation
[ok] archive hashes unchanged after every validation
[ok] production databases unchanged (size + mtime)
```

Plus the 15 retained G3 path-safety checks (identical/normalized/case/hardlink aliases, role collisions, force policy), each asserting the target's SHA-256 is unchanged after rejection.

### A defect this pass introduced and fixed before delivery

The first implementation ran `membership_gate` per sub-population against a shared table, so checking the stocks flagged the two benchmarks as `unexpected_symbols` and the real manifest failed with complete data. The unexpected-symbol test belongs to the **view**, not the sub-population, so it now takes an explicit `view_declared` set (`staging_gate.py:205`). Reported here because the transient failure is visible in the development history.

### Correction to my previous report

The earlier G-round report claimed that gate `P0` would catch an accidentally omitted benchmark. **That was wrong, and Codex is right**: `P0`'s expected total was derived from the same manifest, so it could not be an independent 52-member contract. `P0` has been removed entirely. Membership is now judged per security against the manifest's declared members in each view (M1/M2/M3), which is a real identity check rather than a count. Generic benchmark-free sub-batches remain expressible via `--history-scope stocks`, but that is a declared scope, not this approved pilot.

### Remaining limitations

1. Strict-PIT admissible rows remain **0** in the local corpus and cannot be created retroactively; only future collection can carry observed-availability evidence. This is not proof that external archived or dated source evidence could never supply it.
2. Historical universe, ST history, suspension calendar, delisting register and BJ pre-2024-08-12 code mapping remain **UNKNOWN**. Survivorship stays unquantifiable and gap causes stay `unknown` rather than being classified.
3. `identity` is the only supported transformation. A genuine qfq↔raw reconciliation needs a declared factor series that does not exist locally, so the gate blocks rather than assuming comparability or inventing factors.
4. The identity field list is `open,high,low,close`. Volume and amount are **not** reconciled across views, because the two stores legitimately differ on unit and amount availability; unit correctness is handled separately by `P4` and remains quarantined for the current corpus.
5. The history view's declared scope (`--history-scope all|stocks`) must be stated by the caller. An undeclared or wrong scope is caught by M3 as unexpected/absent symbols rather than being inferred.
6. Feature readiness (V3b) is only meaningful once warm-up data exists; on the current corpus every stock is short, which is reported honestly rather than waived.
7. No backend regression suite was rerun because no runtime code was changed.

### Pilot proposal — unchanged universe, three clarifications

Exactly the same 50 stocks plus `SH000300` and `SH000001`. The fixes clarify three things:

- **Benchmark coverage is contractually different from stock coverage.** Indices are judged over the research window, not a listing interval, and this is declared in the manifest rather than patched with a fake IPO date.
- **Coverage is per eligible listing interval.** The 8 in-window IPOs legitimately have fewer eligible sessions; that is not a gap and must not be padded with fabricated pre-listing bars.
- **Warm-up is a separate, honest statement.** With `--warmup-sessions 250` the interval is derived from the pinned calendar (anchoring at 2022-08-24 for the full depth). For stocks listed after that date the lookback is genuinely unavailable and V3b reports them short; whether the pilot treats warm-up as advisory or blocking is a decision for the authorization step, and an advisory pilot must not claim feature readiness.

M2 remains unauthorized. M1 is not self-approved. Pilot execution requires separate user authorization after Codex acceptance; full-market rebuild and production promotion remain separate gates.

---

## (superseded) G1–G3 gate-wiring closure (2026-09-06, responding to `M1_GATE_WIRING_CODEX_REVIEW.md`)

> Status: `ready_for_review`. This section is the **current execution contract** and is written in English for review. Sections below it are retained as the historical R1–R4 / F1–F4 record. The independently verified temporal fixes (13/13), primitive gate improvements (46/46), coverage census and deterministic pilot selection are preserved unchanged — none of them was redone.

### Resolution table

| ID | Defect Codex reproduced | Fix | File:line | Test |
|---|---|---|---|---|
| **G1** | `validate` ran date/price/unit/duplicate only on the pricing store, ran just the FK check on history, and **never called D8**. A history fixture with `trade_date='ERROR'`, `close=-999`, `high<low`, a wrong provider and a duplicate row still returned **exit 0 / SUCCEEDED**. | Both consumed views attached into one connection; history validated for population, dates, OHLC, duplicates and provenance (`H0`–`H4`); declared reconciliation wired as a **required** gate (`X1`/`X2`). Missing or unsupported transformation blocks instead of being skipped. | `staging_gate.py:315-321` (both views attached), `:363-381` (H0–H4), `:384-409` (X1/X2) | 12 CLI cases |
| **G2** | `load_manifest()` discarded listing metadata and `pilot_coverage()` applied the full research session set to every stock, so a stock listed 2025-06-10 holding **all 305** eligible sessions failed for missing pre-listing bars. | Manifest retains `list_date`/`delist_date`; per-symbol eligibility reuses the accepted listing-aware denominator; unknown listing stays UNRESOLVED; warm-up strictly precedes the research start and is a separate gate. | `staging_gate.py:135-148` (metadata kept), `:205-218` (`eligible_sessions`), `:220-262` (`coverage_gate`), `:411-441` (V1/V2/V3/V3b) | 7 CLI cases |
| **G3** | `--baseline-out` was never checked against inputs. Pointed at an archive with `--force` it returned **exit 0, changed the archive, and replaced the SQLite header with JSON**. | All roles resolved and validated **before any write**; output aliasing a protected input is rejected regardless of `--force`; role collisions rejected; `--force` may replace only a genuine baseline document. | `staging_gate.py:74-89` (`_alias`), `:92-112` (`guard_paths`), `:159-165` (snapshot guard), `:181-195` (force policy), `:295-300` (validate role guard) | 15 CLI cases |

### Exact commands and actual results

Run from `claude methods/_m1_closure/` with the project interpreter:

```bash
../../backend/.venv/Scripts/python.exe -B -X utf8 coverage_gap_generator.py   # exit 0, identity 3900763 == 3900763
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py        # exit 0, 13/13 proofs
../../backend/.venv/Scripts/python.exe -B -X utf8 acceptance_runner.py        # exit 0, DIAGNOSTIC only
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py    # exit 0, 46 cases, 0 unexpected
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py    # exit 0, 36 checks, 0 unexpected
../../backend/.venv/Scripts/python.exe -B -X utf8 pilot_selection.py          # exit 0, 50 stocks + 2 benchmarks
```

`staging_gate.py` has no default invocation: every path must be supplied.

```
snapshot  --archive-trading P --archive-history P --calendar P --baseline-out P [--force]
validate  --staging-trading P --staging-history P --archive-trading P --archive-history P
          --pilot-manifest P --calendar P --baseline P
          [--expected-sessions N] [--expected-history-symbols N] [--expected-history-sessions N]
          [--pricing-basis B] [--history-basis B] [--transformation T]
          [--coverage-threshold R] [--warmup-start D] [--warmup-sessions N] [--warmup-required]
```

Exit codes: `0` all required gates PASS/NOT_APPLICABLE · `1` a required gate is FAIL **or UNKNOWN** · `2` usage/path-role error raised before any write.

### Clean and corrupted fixtures through the real CLI (36/36, exit 0)

```
[ok] G3 normal baseline creation succeeds                               exit=0
[ok] G3 baseline-out == archive rejected even with --force              exit=2
[ok] G3 rejected write left the archive byte-identical
[ok] G3 normalized-path alias of an archive rejected                    exit=2
[ok] G3 archive unchanged after normalized-alias rejection
[ok] G3 baseline-out == calendar rejected                               exit=2
[ok] G3 calendar unchanged
[ok] G3 case-insensitive alias rejected on Windows                      exit=2
[ok] G3 archive unchanged after case-alias rejection
[ok] G3 filesystem hardlink alias rejected                              exit=2
[ok] G3 archive unchanged after hardlink rejection
[ok] G3 archive-trading == archive-history rejected                     exit=2
[ok] G3 replacing an existing baseline needs --force
[ok] G3 permitted baseline replacement with --force succeeds
[ok] G3 --force refuses to replace a non-baseline file
[ok] G1 complete consistent TWO-VIEW control succeeds                   exit=0
[ok] G1 history checks actually ran
[ok] G1 reconciliation actually ran
[ok] G1 corrupted HISTORY date fails the real command                   exit=1
[ok] G1 corrupted HISTORY price fails the real command                  exit=1
[ok] G1 duplicate HISTORY key fails the real command                    exit=1
[ok] G1 dangling HISTORY provenance fails the real command              exit=1
[ok] G1 missing HISTORY coverage fails the population gate              exit=1
[ok] G1 MISSING transformation blocks acceptance                        exit=1
[ok] G1 UNSUPPORTED transformation blocks acceptance                    exit=1
[ok] G1 identity declared across DIFFERENT bases fails                  exit=1
[ok] G1 same-basis divergence fails reconciliation                      exit=1
[ok] G2 IPO with ALL eligible post-listing sessions succeeds            exit=0 (305 eligible sessions)
[ok] G2 no pre-listing bar was demanded
[ok] G2 deleting one required post-listing session fails                exit=1
[ok] G2 unknown eligibility is UNRESOLVED, not complete                 exit=1
[ok] G2 warm-up interval ends strictly before the research start
[ok] G2 warm-up is a separate gate from V1
[ok] G2 declared 250-session warm-up depth blocks when unavailable      exit=1
[ok] frozen baseline byte-identical after every validation
[ok] production databases unchanged (size + mtime)
```

The clean control is a genuine two-view fixture: identical symbols and all 728 research sessions in **both** stores on a common declared basis, reconciled under `identity`. The earlier "clean" fixture had 728 pricing sessions against **three history rows** — that is what let corrupt history pass.

### Evidence that protected inputs and the frozen baseline are unchanged

- Every G3 rejection is asserted to leave the target's SHA-256 identical (`archive_trading`, `archive_history`, and the calendar file). Rejection happens in `guard_paths()` before any file is opened for writing.
- The frozen baseline is byte-compared against its original bytes after every validation probe in the run.
- Both production databases are compared by size and mtime-ns at the start and end of the whole suite and are unchanged. No production path is ever passed to the gate by these tests.
- `--force` may replace only a document whose `kind` is `frozen_archive_baseline`; anything else is rejected, so force cannot be aimed at an arbitrary file.

### One design decision worth flagging for review

`coverage_gate` distinguishes a manifest that **declares zero benchmarks** (→ `NOT_APPLICABLE`, scoped out) from a stock population that is empty (→ `UNKNOWN`, blocking). Without this, any benchmark-free sub-batch could never pass. The declared total is still cross-checked by the population gate `P0`, so a manifest that *accidentally* omits its benchmarks is caught there rather than silently excused. If Codex prefers benchmarks to be unconditionally mandatory, that is a one-line change to make `V2` blocking on empty.

### Remaining limitations

1. Strict-PIT admissible rows remain **0** in the local corpus, and no backfill can retroactively create observed-availability evidence. Only future collection can carry it. This is not proof that external archived or dated source evidence could never supply it.
2. Historical universe, ST history, suspension calendar, delisting register and BJ pre-2024-08-12 code mapping remain **UNKNOWN**; survivorship stays unquantifiable and gap causes stay `unknown` rather than being classified.
3. The only supported cross-view transformation is `identity`. A genuine qfq↔raw reconciliation needs a declared factor series, which does not exist locally; until then the gate blocks rather than assuming comparability.
4. `--expected-history-sessions` / `--expected-history-symbols` must be declared per batch; an undeclared population is UNKNOWN and blocks. This is deliberate but means the caller must state the expected shape.
5. No backend regression suite was rerun because no runtime code was changed.

### Clarifications to the 50-stock + 2-benchmark staging pilot

The universe and strategy are unchanged. Three clarifications follow from these fixes:

- **Coverage is judged per eligible listing interval, not against all 728 sessions.** The 8 `ipo_in_window` stocks will legitimately have far fewer eligible sessions; that is not a gap and must not be backfilled with fabricated pre-listing bars.
- **The pilot must fetch both consumed views, or declare that it does not.** A pricing-only pilot cannot satisfy `H0`–`H4`, and the reconciliation gate requires a declared basis on both sides. If the pilot intends to populate only the pricing store, that must be stated up front and the history gates scoped accordingly, rather than passing by absence.
- **Warm-up is separate and currently unsatisfiable for new listings.** `--warmup-start 2022-08-24` with `--warmup-sessions 250` blocks when the depth is unavailable; for stocks listed after that date the lookback is honestly unavailable rather than a failure to be engineered away. Whether warm-up is advisory or blocking for the pilot is a decision for the authorization step.

M2 remains unauthorized. Pilot execution requires separate user authorization after Codex acceptance; full-market rebuild and production promotion remain separate gates.

---

## F1–F4 targeted execution-gate closure（2026-09-06 第二轮，回应 `M1_CLOSURE_CODEX_REVIEW.md`）

> Codex 已独立复现覆盖度数据与 50 只试点清单，并确认 6 条时间证明与 22 个门测试通过；本轮**不重做**这些审计，只修 F1–F4 的假通过路径。R1–R4 的结论仍然成立，本节在其上收紧实现。

| 项 | 修复 | 证据 |
|---|---|---|
| **F1** 时间准入 | 输入校验 + 归一化为绝对时刻后再比较；空串/空白/畸形/无时区一律拒绝；显式声明 date-only 语义 | `temporal_contract.py`：**13/13**，exit 0 |
| **F2** 数据检查 fail-closed | 修复 `volume_unit=NULL` 的 SQL 三值逻辑漏洞；空表→UNKNOWN；新增总体门 D0、重复键 D7、跨库同基准对账 D8 | `test_acceptance_gates.py`：**46/46**，exit 0 |
| **F3** 归档保护 + 可执行 staging 门 | 全库指纹（schema + 所有表所有列）；`snapshot` / `validate` 分离的显式 CLI；validate 只读、绝不重写基线；FAIL/UNKNOWN → 非零退出 | `test_staging_gate_e2e.py`：**19/19**，exit 0 |
| **F4** 试点路由 | 股票与基准分离；基准不进股票目录、不要求流动性证据；原始/复权口径显式声明；warm-up 单独计量 | 见 §5.2/§5.3 与 F4a–F4e 用例 |

### F1 — 两条假通过路径已封闭

Codex 的两个夹具此前都返回 `admitted=True, all_stamps_observed_and_before_cutoff`：

1. **空串**：四个证据字段全为 `""`，而检查只拒绝 `None`。
2. **时区**：cutoff `2024-06-28T10:00:00+08:00`（02:00 UTC），可得性 `2024-06-28T03:00:00Z`（03:00 UTC）——**晚一小时**，但字符串比较里 `"0" < "1"`。

现在每个值先经 `to_instant()` 校验并归一化为带时区的绝对时刻，再比较。新增回归：

```
F1a all-blank stamps rejected (previously admitted)            PASS  observed_availability_blank
F1b blank provenance alone rejected                            PASS  provenance_blank
F1c 03:00Z availability rejected against a 10:00+08:00 cutoff  PASS  observed_availability_after_cutoff
F1d equivalent instants in three timezones give one verdict    PASS  distinct_verdicts=1
F1e naive timestamp rejected rather than assumed local         PASS  ..._naive_timestamp_ambiguous
F1f impossible event date rejected                             PASS  event_time_impossible_date
F1g same-day date-only vintage does not pass a same-day cutoff PASS  factor_vintage_after_cutoff
```

**声明的 date-only 语义**（两端都朝 fail-closed 方向加宽）：`event_time` / `observed_availability` / `ingestion_time` / `factor_vintage` 的纯日期 → **当日最后一刻** `23:59:59.999999+08:00`；`cutoff` 的纯日期 → **当日最初一刻** `00:00:00+08:00`。时区固定 `+08:00`（中国 1991 年后无夏令时），不查 tz 数据库，避免契约随 tzdata 更新而变。**无时区时间戳一律拒绝**，不假定本地时区——正是这种默默混用产生了第 2 条漏洞。

### F2 — 检查现在真的 fail-closed

- **`volume_unit=NULL` 曾返回 D4 PASS**（`verifiable=1, contradicted=0, quarantined=0`）。SQL 三值逻辑让 `volume_unit='hand'` 与 `NOT IN (...)` 双双求值为 NULL，该行既算"可验证"又永不"矛盾"。现在"可验证"必须满足 `volume_unit IS NOT NULL AND TRIM(volume_unit) <> '' AND volume_unit IN ('hand','share')`，缺失单位归入隔离区。
- **空表曾从 D1/D2/D3/D5 返回 PASS**。现在每个检查遇空总体返回 UNKNOWN，并新增 **D0 总体门**：必须声明期望的符号数/交易日数，否则 UNKNOWN。
- **D7 重复键**恢复（改写注册表时被丢掉）。
- **D8 跨库同基准对账**新增，且在**未声明变换**时返回 UNKNOWN——既不拿原始价与复权价强行比较（会制造假失败），也不默默略过（会制造假通过）。

新增用例含 `F2a`（NULL 单位）、`F2b`（空白单位）、`F2c–F2f`（四个空表）、`F2g/F2h`（重复键与干净对照）、`F2i–F2k`（总体门）、`F2l–F2n`（跨库变换声明）。

### F3 — 归档保护与真正的 staging 门

- **旧 D6 只哈希 symbol/date/adjustment/close/volume/amount**：改掉 open 价或 provider 仍返回 PASS。现在 `archive_fingerprint(full=True)` 覆盖 **schema（`sqlite_master`）+ 每张表每一列每一行**。`F3a` 用例同时断言**窄口径指纹确实察觉不到**被改的 open 价，以此证明旧门是盲的。
- **旧命令固定跑 `production_run()`、不接受路径、不接受冻结基线、每次都覆写 `acceptance_baseline.json`、报告 FAIL/UNKNOWN 后仍 exit 0**。现在拆成两个显式子命令：

```
staging_gate.py snapshot  --archive-trading P --archive-history P --calendar P --baseline-out P
staging_gate.py validate  --staging-trading P --staging-history P --archive-trading P \
                          --archive-history P --pilot-manifest P --calendar P --baseline P \
                          [--expected-sessions N] [--warmup-start DATE] [--warmup-required]
```

`snapshot` 是**唯一**写入模式，且已存在基线时拒绝覆盖（需 `--force`）。`validate` 全程只读，**从不写任何文件**。退出码：`0` 成功 / `1` 有必需门为 FAIL 或 UNKNOWN / `2` 输入错误。**UNKNOWN 在门里是失败**——诊断可以说"不知道"，授权下载的门不可以。

`acceptance_runner.py` 保留为**诊断模式**（始终 exit 0 并如此声明），不再写基线；`acceptance_baseline.json` 已作废重命名。

### F4 — 股票与基准分离

D2 此前要求每个符号都在股票目录里，D4 要求每行都有正的 amount/volume 与未复权价——因此一个合法的指数基准既过不了 D2，也只能在 D4 得到 UNKNOWN。现在：

| 检查 | 股票 | 基准 |
|---|---|---|
| D2 命名空间/目录 | 必须匹配 `^(SH|SZ|BJ)\d{6}$` 且在 `instruments` 中 | 按清单路由，**只验身份**，不要求进股票目录 |
| D4 单位 | 必须有**原始（未复权）价 + 正 amount + 正 volume + 受支持的已声明单位**才算可验证 | **排除**，并报告排除数量 |
| V1/V2 覆盖度 | 研究窗口内按日历逐只计量 | 单独一条门，与股票分开 |
| V3 warm-up | **单独计量**，默认为 advisory，可用 `--warmup-required` 改为阻断 | — |

`F4d` 专门证明**排除基准不能掩盖股票的未知单位**：一个被路由走的基准 + 一只缺 amount 的股票 → 整体仍是 UNKNOWN。

### F1–F4 端到端实测（临时数据库，19/19，exit 0）

```
[ok] snapshot writes a frozen baseline                              exit=0
[ok] snapshot refuses to clobber an existing baseline without --force
[ok] CLEAN staging validates successfully                           exit=0
[ok] clean run reports the supplied staging path
[ok] clean run reports the supplied frozen baseline path
[ok] impossible date fails validation                               exit=1
[ok] NULL volume_unit fails validation (was the D4 false pass)      exit=1
[ok] duplicate business key fails validation                        exit=1
[ok] EMPTY staging fails validation (no evidence is not a pass)     exit=1
[ok] short population fails the D0 population gate                  exit=1
[ok] tampered archive fails even with clean staging                 exit=1
[ok] restored archive validates again                               exit=0
[ok] absent warm-up is advisory by default (still exit 0)           exit=0
[ok] warm-up is reported as its own gate, not folded into V1
[ok] absent warm-up blocks when declared required                   exit=1
[ok] missing staging path is an input error (exit 2), not a pass    exit=2
[ok] frozen baseline byte-identical after every validation
[ok] production databases unchanged (size + mtime)
```

### 生产诊断口径的一处变化（需 Codex 注意）

D2 从 **FAIL 6** 变为 **FAIL 4**：`SH000001` / `SH000300` 现按基准路由，不再计为"不在股票目录中"。其余 4 项（裸 6 位符号 `000001` / `300750` / `600519` / `920099`）不变。新增 D0 UNKNOWN（生产未声明期望总体）、D7 PASS（无重复键）、D8 UNKNOWN（未声明变换，拒绝原始/复权比较）。D1 FAIL 1、D3 FAIL 4、D4 UNKNOWN、D5 PASS、D6 UNKNOWN 均与你复现的基线一致。

### 关于历史 PIT 结论的措辞更正（接受你的限定）

本项目**当前本地语料**无法证明历史 PIT 可得性。这**不等于**"任何外部归档版本或带日期的来源证据都不可能改善它"，也**不等于**"三年探索性研究不可能"。正确做法是：冻结所选数据 vintage、声明限制、阻断修订值回流，并让最终研究声明与证据强度相称。`temporal_contract.py` 的 `strict_pit_admissible_basis` 文案已按此改写。

---

## R1–R4 收口结果表

| 需求 | 交付物 | 结果 | 关键证据 |
|---|---|---|---|
| **R1** 历史可得性不得被制造 | `_m1_closure/temporal_contract.py` | **已解决**，原 6/6，经 F1 收紧后 **13/13**，exit 0 | 五类时间分离；`assumed_publication` 永不参与严格准入；P3 证明即使把可得性戳伪造成 2024，`factor_vintage=2026` 仍拒绝 |
| **R2** 覆盖度与缺口对账 | `_m1_closure/coverage_gap_generator.py` → `coverage_reconciled.csv` + `_meta.json` | **已解决**，恒等式全量成立，exit 0 | 单一钉定日历（sha256 `f1f1ce33…`）+ 单一上市区间定义；5,286 处分母分歧消除 |
| **R3** 验收门必须能失败 | `_m1_closure/acceptance_runner.py` + `test_acceptance_gates.py` | **已解决**，原 22/22，经 F2/F3/F4 扩充后 **46/46**，exit 0 | 四个被 Codex 攻破的门（V2/V3/V5b/V7）现在对当初骗过它们的输入全部 FAIL |
| **R4** 一份连贯的 M2 提案 | 本文件第 5 节 + `_m1_closure/pilot_selection.py` → `pilot_symbols.csv` | **已解决**（提案，未授权执行） | 契约与验收先于摄取；50 只分层试点 + 2 个基准，符号列表确定且可复现 |

---

## 1. R1 — 时间契约

### 1.1 被关闭的漏洞

旧报告 T1/T2 的组合会**制造**历史可得性：

```
T1: available_at := 交易日收盘 + 假定时滞
T2: 当 available_at <= cutoff 即准入
```

一根 2024 年的 bar，若其价格是在 2026 年的复权基准下被重算的，T1 会给它盖上 2024 年的戳，T2 便放行。**把 `factor_vintage` 记下来但不据以过滤，并不能堵住这个洞。**

### 1.2 五类时间，永不合并

| 概念 | 含义 | 在本项目中的状态 |
|---|---|---|
| `event_time` | bar 描述的交易日 | 有（`trade_date`） |
| `assumed_publication` | **模型**（"收盘 + 时滞"），永远不是证据 | 可构造，但严格准入**不予采信** |
| `observed_availability` | 该**版本**在某时刻确实可取得的证据 | **全库不存在** |
| `ingestion_time` | 本地写入时刻 | 有（`created_at` / `fetched_at`），是知识上界而非可得性下界 |
| `factor_vintage` | 价格所依据的复权/公司行动基准 | **全库无此列** |

### 1.3 准入规则与证明

`STRICT_PIT` 要求五项**全部已知且早于 cutoff**，任一未知即拒绝（fail closed）；`EXPLORATORY` 仅要求 `event_time <= cutoff` 并**返回标签**说明这是可复现性、不是历史有效性。二者不得用同一个词汇报告。

```
P1 genuine historical version admitted under strict PIT        PASS  all_stamps_observed_and_before_cutoff
P2 later revision rejected despite an old event_time           PASS  observed_availability_after_cutoff
P3 backdating the availability stamp does not rescue it        PASS  factor_vintage_after_cutoff
P4 production-shaped row (no evidence) rejected, not defaulted  PASS  observed_availability_unknown
P5 same row admitted EXPLORATORY, labelled non-PIT              PASS  reproducible_not_point_in_time
P6 future session rejected at an earlier cutoff                 PASS  event_time_after_cutoff
```

**P3 是关键**：把 `observed_availability` 伪造成 2024（即 T1 的产物），准入仍然失败，因为 `factor_vintage=2026-09-03` 晚于 cutoff。

### 1.4 对生产数据的后果（只读实测）

`available_at <> fetched_at` 的行数为 **0**，全表仅 **4** 个采集日；两库均无 `factor_vintage` 列。因此**当前生产数据可通过严格 PIT 准入的行数为 0**。这是证据本身的属性，不是缺陷；它意味着任何"历史 PIT 回测"声明目前都不成立，而 `EXPLORATORY` 口径的可复现研究仍然可做——**必须带标签报告**。

前瞻结果标签不受影响：成熟后使用 cutoff 之后的观测是合法的；被禁止的是让**后期修订值**回流到更早的特征、切分或决策。

---

## 2. R2 — 覆盖度与缺口对账

### 2.1 消除的分歧

Codex 实测两份交付物存在 **5,286 处分母分歧**。以 `BJ920000` 为例：

| 来源 | eligible | observed | leading | 合计 | 状态 |
|---|---|---|---|---|---|
| 旧 `coverage_manifest.csv` | 728 | 501 | — | — | 无缺口分解 |
| 旧 `coverage_gap_shape.csv` | **587** | 501 | 86 | 587 | 漏掉整个 141 天头部空档 |
| **新 `coverage_reconciled.csv`** | **728** | 501 | **227** | **728** | 恒等式成立 |

新生成器**同时**产出两类列，二者是同一条记录的投影，结构上无法再分歧；写盘前对每只可计算证券断言：

```
observed + leading_gap + interior_gap + trailing_gap == eligible
```

### 2.2 对账总量（实测，exit 0）

| 项 | 值 |
|---|---|
| 名义窗口（钉定日历） | **728** 个交易日 |
| 日历文件 sha256 | `f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656` |
| 清单内证券 | 5,567 |
| 有观测且分母可计算 | 5,542 |
| `list_date` 未知（不可计算） | 24 |
| 有分母但零观测 | 1 |
| 非日历交易日的行 | **0** |
| eligible 合计 | 3,900,763 |
| observed 合计 | 2,888,185 |
| leading / interior / trailing | 1,004,942 / 4,611 / 3,025 |
| **恒等式** | 2,888,185 + 1,004,942 + 4,611 + 3,025 = **3,900,763 ✔** |

覆盖率（唯一可用于横截面研究的口径）：**窗口起点前已上市的 5,167 只，max 0.7390，median 0.7363，≥0.95 为 0，≥0.80 为 0**。

缺口成因一律保留为 `unknown_no_suspension_or_delist_calendar`——本项目没有停牌/退市日历，写入任何具体原因都是伪造证据。

### 2.3 我方此前一项错误声明的撤回

我在上一轮收口中称"`trading_calendar.py:61` 本来就在消费这份 `calendar.json`"。**这是错的，予以撤回。** 实测 `ak.tool_trade_date_hist_sina()` 执行

```python
url = "https://finance.sina.com.cn/realstock/company/klc_td_sh.txt"
r = requests.get(url)
```

即一次 HTTP 请求；离线时 `trading_calendar.py` 回落到 `weekday_fallback`（对 A 股节假日是错的）。`calendar.json` 只是**离线审计参照**，不能证明任何历史运行时使用过哪份日历——该问题保持 UNKNOWN。此结论已写入生成器文档字符串与 `_meta.json` 的 `calendar_is_runtime_source: false`。

---

## 3. R3 — 可失败的验收门

### 3.1 生产实测（只读，exit 0）

| id | 门 | 路由 | 结果 | 观测 |
|---|---|---|---|---|
| D1 | 不可能日期 / 非交易日 | trading | **FAIL** | 1（`ERROR`） |
| D2 | 符号命名空间 + instruments 引用 | both | **FAIL** | 6（4 种裸 6 位拼写 + `SH000001`/`SH000300` 不在 instruments） |
| D3 | 缺失/非正价格 + OHLC 关系 | trading | **FAIL** | 4 |
| D4 | 单位可验证性 | trading | **UNKNOWN** | 2,891,617 行全部隔离 |
| D5 | ingest_run 引用完整性 | history | **PASS** | 0 |
| D6 | 归档值指纹 | history | **UNKNOWN** | 尚无冻结基线，已记录 `3cdd3bcf…` |

**UNKNOWN 永不计为 PASS**——这正是旧套件的失效模式：结构上无法发现问题的检查报"0 违规"，与真正干净的结果无法区分。

### 3.2 合成回归集：22/22，exit 0

每个当初骗过旧门的输入，现在都被拒绝：

| 旧门失效 | 新门 | 合成用例 | 结果 |
|---|---|---|---|
| V2 仅匹配形状，放行 `2025-02-30` | D1 | 真实日历日期校验 | **FAIL 命中** |
| V3 仅匹配形状，放行 `XX123456` | D2 | 命名空间 + instruments 引用 | **FAIL 命中** |
| V5b 单源夹具报 0 违规 | D4 | **同源、无 provider 边界、单位故意写错** | **FAIL 命中** |
| V7 行数不变即通过 | D6 | 改一个 close，行数不变 | **FAIL 命中** |
| G5 只查 NULL | D5 | 非 NULL 但悬空的 run id | **FAIL 命中** |

另有 6 个 clean control 用例通过（证明门不是恒 FAIL），3 个用例正确返回 UNKNOWN（缺表、无基线、不可验证总体）。

### 3.3 单位问题的口径收紧（重要，narrowing）

Codex 警告"不要因为部分边界可疑就把所有 tencent 行除以 100"。实测后我进一步收紧了自己的表述：

| 口径 | 数量 | 性质 |
|---|---|---|
| **有证据**的近 100 倍跃变 | **293** 只，全部 `SH688xxx`（科创板），全部 `tencent.fqkline → akshare.stock_zh_a_daily`，其中 218 次发生在 **2024-08-13** | 观测事实 |
| 不可验证总体（上界） | 306,543 行 / 4,946 只 tencent 行，`amount` 全为 NULL | **隔离，不断言错误** |

**我此前把 306,543 行 / 4,946 只表述为"受污染范围"，这是把上界当成了作用域，予以收紧。**证据支持的是**科创板特定**的边界单位差异，不是全体 tencent 行的 股/手 错误。科创板最小申报单位与主板不同，这是一个**待试点检验的假设，不是结论**。D4 门因此不做任何重标定，只做隔离。

---

## 4. 其余措辞更正（接受 Codex 的四点）

1. **7.43% vs 7.46% 不是 NULL 造成的**。Codex 查得共同键中 cache close 无 NULL。以 cache close 为相对分母得 207,159；以 history close 为分母得 207,835，经 ready+qfq 过滤后 207,831。40 键之差来自质量/复权过滤。**分母必须写明**，我此前的"NULL 保护"解释是错的。
2. **快照移除只证明观测到的成分变化，不等于法定退市日**。保留事件区间与来源限制表述。
3. **旧泄漏探针不支持 74.7% 的指控，同率对照与零未来交易日探针也不构成"清白证明"**。正确措辞是 `unsupported by this probe`，不是全面免责。
4. **零成交 + 输入快照缺失 ⇒ 旧运行不是绩效证据、可复现性未经证明**。仅凭时间戳先后**不能**证明"不可能复现同一数值"。相关记录不删除、不重分类。

---

## 5. R4 — M2 试点授权提案（**提案，未执行，未授权**）

### 5.1 顺序：契约与验收先于摄取

阶段 0（**已完成，即本次收口**）：时间契约、覆盖度对账、验收 runner 与合成回归集就位，且已在生产数据上跑出基线。**任何数据写入都在用户授权之后，且只写 staging。**

### 5.2 试点范围

| 项 | 值 |
|---|---|
| 标的 | **50 只股票 + 2 个基准**（`SH000300`、`SH000001`）；清单见 `_m1_closure/pilot_symbols.csv` |
| 分层 | ordinary_control 20 / suspected_unit_switch 10 / ipo_in_window 8 / bj_code_history 7 / largest_interior_gap 5 |
| 研究区间 | **2023-09-04 .. 2026-09-04**（728 个交易日，保持不变） |
| 特征回看（**单独声明，非新规格批准**） | 建议上限 250 个交易日 → 预取起点 **2022-08-24**；120 日方案对应 2023-03-10 |
| 试点抓取区间 | 2022-08-24 .. 2026-09-04 = 978 个交易日/只 → 52 只 **≤ 50,856 行（毛上界）**。IPO、停牌与北交所旧代码使实际行数必然更少；该数字用于容量规划，**不得作为期望行数验收** |
| 来源假设 | 主用 `akshare.stock_zh_a_daily`（新浪，带 amount）；同花顺本地插件仅作对照。**速率与"每符号一请求"均为待验证假设**——试点的目的之一就是实测它，不得据此承诺全量运行时 |

分层是为了让试点**能够失败**：`suspected_unit_switch` 全为科创板（因为证据本身如此，见 3.3），`bj_code_history` 检验 `8xxxxx → 920xxx` 映射，`ipo_in_window` 检验短上市区间，`largest_interior_gap` 检验成因未知的内部空洞。

### 5.3 试点验收标准（全部在 staging 上执行）

0. 入口是 `staging_gate.py validate`（**不是** `acceptance_runner.py`，后者只是诊断且始终 exit 0）。必需门任一为 FAIL 或 UNKNOWN 即整体失败（exit 1）。
1. D0/D1/D2/D3/D5/D7 在试点 staging 上必须 **PASS**（不是 UNKNOWN）；D0 需显式声明期望的 **52 个符号**与期望交易日数。
2. D4 必须从 UNKNOWN 转为 PASS。这要求抓回**原始（未复权）价 + 正 amount + 正 volume + 已声明且受支持的单位**四者齐备——复权价配原始金额无法构成有效检验。基准（`SH000300`/`SH000001`）**被显式排除于 D4 之外**：指数不可交易，向其索取流动性证据要么误伤合法基准、要么等于凭空发明成交量。排除数量会被打印，且已由 `F4d` 证明不能掩盖股票侧的未知。
2b. 若研究还需要复权序列，必须与原始序列**并存**并声明变换；D8 只在变换被显式声明时才做跨库对账，否则返回 UNKNOWN。
3. D6 对**原始归档**的指纹必须与试点前一致——试点不得改动任何既有数据。
4. 覆盖度按三条**互相独立**的门计量：**V1 股票**研究窗口覆盖、**V2 基准**研究窗口覆盖、**V3 warm-up**（`2022-08-24 .. 2023-09-04`）单独计量，默认 advisory，可用 `--warmup-required` 改为阻断。warm-up **不得**并入 V1。
   IPO 标的的 eligible 区间从其 `list_date` 起算，因此其缺口不等于抓取失败。
   **注意**：单只 90% 只是试点诊断阈值，**不是**项目最终 95% 覆盖标准。
5. 实测吞吐、请求数与失败率，用以替换 5.2 中的假设值。

### 5.4 原始 vintage 与有意重建数据的区分

| 类别 | 处理 |
|---|---|
| 原始 vintage（现有两库） | **只读保留**。先用 sqlite3 backup API 生成一致性副本并记录 D6 指纹；**不得先行原地修复** |
| staging 重建数据 | 明确标注为"有意重建"，与原始副本并存；差异必须是**声明过的**重写清单，不得包含未声明的表 |

Codex 指出旧方案的矛盾：推荐的重建跨越 2025 年，而 N2 要求 2025 年数值不变。**本提案取消该矛盾**——试点只写 staging，不触碰生产；全量重建的"有意重写区间"必须在授权时逐条列明，并配一个对应的最终门，而不是靠一句"另行批准"带过。

### 5.5 后续门（各自独立授权）

- **门 A（本次）**：收口交付 → Codex 复核。
- **门 B**：用户授权 50 只试点下载 → 只写 staging → Codex 独立复核试点结果。
- **门 C**：全量分阶段重建（仅在门 B 通过后单独授权）。
- **门 D**：生产提升——独立 stop gate。必须处理：SQLite WAL、停止所有写入者、**两个数据库文件**、部分提升（一个文件成功另一个失败）与可恢复回滚。**两次 rename 不是一个跨文件原子事务**，提案按"可回滚的两阶段"设计，并保留提升前副本至少 7 天。

### 5.6 明确列为限制、不在试点范围内

历史 universe、ST 标记历史、停牌日历、退市登记、北交所旧代码映射**均无本地来源**，不能靠回填解决；不购买数据，也不通过缩小研究总体来掩盖。**A2 仍是官方持久化评估消费者的独立前置条件**，不作为回填的附带项。

---

## 6. 复现命令与实测结果

在 `D:\codex-A股交易\claude methods\_m1_closure` 下，使用项目虚拟环境：

```bash
../../backend/.venv/Scripts/python.exe -B -X utf8 coverage_gap_generator.py   # exit 0, identity OK
../../backend/.venv/Scripts/python.exe -B -X utf8 temporal_contract.py        # exit 0, 13/13 proofs
../../backend/.venv/Scripts/python.exe -B -X utf8 acceptance_runner.py        # exit 0, DIAGNOSTIC only
../../backend/.venv/Scripts/python.exe -B -X utf8 test_acceptance_gates.py    # exit 0, 46/46
../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py    # exit 0, 19/19
../../backend/.venv/Scripts/python.exe -B -X utf8 pilot_selection.py          # exit 0, 50 + 2
```

真正的授权门是 `staging_gate.py`，它需要显式路径，因此没有默认调用；用法与退出码见上文 F3 节。

生成物：`coverage_reconciled.csv`、`coverage_reconciled_meta.json`、`acceptance_baseline.json`、`pilot_symbols.csv`、`pilot_symbols_meta.json`。

## 7. 剩余限制

1. 严格 PIT 可准入行数为 **0**，且无法靠回填补救——历史可得性证据一旦没有采集就不存在。只能对**未来**采集加装 `observed_availability` 与 `factor_vintage`。
2. 历史 universe / ST / 停牌 / 退市 / 北交所旧代码映射**全部 UNKNOWN**，幸存者偏差不可量化。
3. 两库 close 38.01% 分歧的**仲裁方**不存在（两库同源），需独立第三方来源，本次禁止联网。
4. 科创板单位假设**未经验证**，等待门 B 试点。
5. 未跑后端回归套件：本次只改 `claude methods/` 下的审计产物，未触碰运行时代码。
6. 日历本身只是离线参照；历史运行时使用过哪份日历仍 UNKNOWN。
