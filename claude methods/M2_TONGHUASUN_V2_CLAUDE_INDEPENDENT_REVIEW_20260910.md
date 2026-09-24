# M2 — Tonghuashun v2 staging corpus: Claude independent review

> **Verdict: `PASS` — the published 52-security staging corpus `ths_v2_20260910_041710_97ef9c09`
> is independently verified against the user-approved `real_session_v2` contract and against
> the M2 acceptance criteria of `THREE_YEAR_RESEARCH_EXECUTION_GOAL.md:173-185`. M2 can close
> as a *staging* delivery under the approved 52-security scope.** Three non-blocking record
> corrections are recommended (§8), one pre-promotion evidence item is named (§5.4), and
> production promotion remains **unauthorized and not recommended** until that item is either
> closed or explicitly accepted by the user.
>
> Task `M2-THS-V2-INDEPENDENT-REVIEW-20260910` (`733b195f6ed9fb3396b0fadd4f88a5063b977f07d8376209d033ab9a933100f8`).
> Reviewer: Claude, this fork. Date: 2026-09-10. Codex owns coordination, integration and any
> automation; nothing here is a production operation.
>
> **What was and was not done.** Read-only queries of **exactly the two published candidate
> stores** (`mode=ro` URI + `PRAGMA query_only=ON`), as authorized. No production database was
> opened; production preservation was checked by **reading Codex's byte-hash receipts**, not by
> touching production files. No network, capture, client/login/token, service, production
> write, threshold or policy change, training, Git action, agent, scheduler or email. Nothing
> in the phase directory was modified; the tamper-test candidate's stores were **not** opened.
> Codex's `--execute`, `--test-tamper`, collectors and builders were not run.
>
> **Preserved separately and unchanged:** the old Sina/AkShare capability **FAIL** and its two
> immutable `EV6` results; P1/U-6 as open items of the *Sina reference-basis* workstream;
> both spent Sina capture grants. None of them is required by, or altered by, this THS
> delivery (§6).

---

## 1. Read scope and pins verified before use

| Object | sha256 | Result |
|---|---|---|
| `v2_delivery_manifest.json` | `eca6bea3c47ef0d37573f4b20d10d6ffe7956738a98118b7298e703142f7154e` | **matches the dispatched hash**; all **31 artifacts** and all **479 transitive pins** match disk (R01) |
| `M2_TONGHUASUN_V2_CODEX_ACCEPTANCE_20260910.md` | `71330b5de05b721ac2304f8b472199ed2ac7b55a5f88b9c429fd2e3afc035c76` | read in full |
| `acceptance_v2_authority.json` | `4214896dd68cddabcc3767a5b3711e64e1f2dfd8609e940e6a3918198a10c8eb` | user reply `可以`, **Codex-recorded** |
| `M2_ACCEPTANCE_REVISION_PROPOSAL.md` | `939357d0e44428bc1f7f074e1edc60cb762b6d80fc4f100f411ac2c2849a35c1` | immutable proposal, read in full |
| `qualification_v2_reviewed.json` | `992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37` | matches the dispatched hash |
| `CURRENT.json` (pointer) | `a3d7b37b2315643970b983dedc8fa814d56219c63df350f382b9a60b0b163b35` | matches the dispatched hash |
| `contract_v2.py` / `staging_v2.py` / `run_staging_v2.py` / `verify_preservation_v2.py` | `14b87fda…` / `df4506f7…` / `f3985459…` / `a0da496a…` | read in full |
| `staging.py` (V1 base) / `run_actual_staging.py` | `ab976f63…` / `d3a530e4…` | guard, write and publication paths read |
| `backend/app/data/tonghuasun_history.py` (parser) | `605d65965b1aee56f0f64c5c2446078aefa8d237d7a3d09b5f7403e4a24c2779` | stdlib-only module; loaded **by file path** for replay |
| `calendar.json` / `pilot_symbols.csv` / `pilot52_blocker_review_v3.json` | `f1f1ce33…` / `97e251ae…` / `58214acb…` | pinned inputs re-hashed |
| `trading.sqlite3` / `history.sqlite3` | `c0b26660ab903541e7e213ee312c565be73547bb3cc8c142486999717e3edeca` / `eda17434ab67496c33eed275b35045c140bad72802b4dcbf981ff22422c53003` | 38,969,344 / 10,604,544 bytes; `integrity_check` ok; `foreign_key_check` empty |
| Candidate fingerprint | `d0c606fe385d54cfd9c5857864eb3e16a625fea8ee9a13e0f29de2e73eae973c` | **recomputed independently** from the four candidate files (R02) — matches the pointer |
| `row_records_sha256` | `5bf0da0fe7049997ce13d1f3d10c00ce142669d4c6ce33d9c82d14e385ad0832` | **recomputed independently from raw bytes** (R05) — matches the bundle and manifest |

Full input/output inventory with hashes: `_m2_ths_v2_claude_review_20260910/review_manifest.json`.

---

## 2. Exact commands run (all from the project venv, `-B -X utf8`)

```
backend/.venv/Scripts/python.exe -B -X utf8 _m2_ths_v2_claude_review_20260910/r01_manifest_pins.py        # exit 0
backend/.venv/Scripts/python.exe -B -X utf8 _m2_ths_v2_claude_review_20260910/r02_db_schema.py            # exit 0
backend/.venv/Scripts/python.exe -B -X utf8 _m2_ths_v2_claude_review_20260910/r03_expected_keys.py        # exit 0
backend/.venv/Scripts/python.exe -B -X utf8 _m2_ths_v2_claude_review_20260910/r04_suspension_audit.py     # exit 0
backend/.venv/Scripts/python.exe -B -X utf8 _m2_ths_v2_claude_review_20260910/r05_raw_replay.py           # exit 0
backend/.venv/Scripts/python.exe -B -X utf8 _m2_ths_v2_claude_review_20260910/r06_basis_unit_controls.py  # exit 0
backend/.venv/Scripts/python.exe -X utf8 -B -m unittest -v test_contract_v2 \
    test_run_actual_staging.BoundaryTests.test_encoded_absolute_candidate_and_readonly_archive_allowed \
    test_run_actual_staging.BoundaryTests.test_production_unc_relative_implicit_and_duplicate_modes_denied \
    test_run_actual_staging.BoundaryTests.test_attach_only_readonly_allowlisted_files
    # cwd = phase directory; 8 tests OK, exit 0; output retained as r07_focused_tests_output.txt
backend/.venv/Scripts/python.exe -B -X utf8 _m2_ths_v2_claude_review_20260910/r08_review_manifest.py      # exit 0
```

The ninth focused test, `test_real_audit_hook_blocks_attach_connect_socket_and_process`, was
**deliberately not re-run**: it spawns a child that *attempts* a production-path connect in
order to prove the audit hook blocks it. Codex's `v2_focused_test_observation.json` records
9/9 passing; I report 8/9 re-run by me and 1 not re-run, not 9/9.

Every script opens only the two published stores, read-only. `r01` … `r08` and their JSON
outputs are in `claude methods/_m2_ths_v2_claude_review_20260910/`.

---

## 3. Independent results, by task item

### 3.1 Identity, population, window, interface depth, basis and units

* **52 identities.** All 52 response identities re-parsed from the raw bodies match the
  reviewed bundle; the 50 stock host codes end in the manifest code (`USHA`/`USZA`/`USTM`
  markets; `SH600289` on `USHT` with retained mapping evidence
  `identity_search_600289/response.bin` = `5ad4d502…`). The two benchmarks are the frozen
  official mappings `SH000300 → USZI399300 (399300.SZ)` and `SH000001 → USHI1A0001 (10001.SH)`;
  `official/NewIndexConfig.xml` and `official/sse_csi300_method.html` are retained as
  backing. The **9 BJ identity facts** (5 old→new code mappings, 4 original `920` IPOs) all
  point to retained documents whose hashes match (R06/`qualification_pilot52.json`).
* **Population and window.** 52 manifest entries (`97e251ae…`); research 2023-09-04…2026-09-04
  (728 sessions); warm-up 2022-08-24…2023-09-01 (250 sessions), extended to 2022-05-01 for
  the three named stocks only. Recomputed independently in R03 from calendar + listing dates.
* **500-adapter vs native interface.** 49 of 52 single-request bodies contain **> 500 rows**
  (max 978, min 203 — the short ones are recent listings). A 500-row cap on this interface
  is contradicted by the retained bytes themselves (R06 `native_depth`).
* **Unadjusted basis — independently replayed, not copied.** With my own implementation of
  the cash-forward relation over the six retained control bodies (adjustment 0/1/2 for
  `SH600011` and `BJ920000`): **0 mismatches over 3,912 OHLC checks per symbol**; volume and
  amount **identical across all three modes**; mode 1 differs from mode 0 on 932 / 904 dates
  and mode 2 on 978 / 978; every ex-date step equals the official cash amount exactly
  (0.20 / 0.27 / 0.40; 0.068 / 0.11 / 0.06 / 0.08 / 0.07 / 0.08); all 9 cash-event documents
  hash-match on disk (7 are the notices I retrieved and Codex accepted under G1 yesterday).
  **The staged rows for both control symbols equal the mode-0 series on all 978 dates.** The
  parser itself returns `vendor_basis: unverified`; the "verified" label is the qualification
  layer's conclusion from these controls plus per-row P4 (below). No response declares an
  adjustment (`response_adjustment: None` on all 55 captures) — the basis is established by
  request contract + discrimination + controls, not by a vendor declaration.
* **Units.** THS `Volume`/`Turnover` map to host fields 13/19 with no scaling in the plugin
  (static IL review, `7e2d12f3…`); two SSE 龙虎榜 anchors for `SH600011` match THS to
  binary32 precision (volume exact / 2 shares; amount −2 / +20 CNY). Decimal differences are
  **retained, not waived**; `all_value_accuracy_verified` is `false` in the bundle and I do not
  upgrade it.

### 3.2 The 298 suspensions, the 48 added rows, the partition, the 14 shortfalls

* **Expected keys derived independently** (R03, no phase module imported): 36,193 research
  keys = **35,943 prices + 250 suspensions**; **9,742 warm-up prices + 48 suspensions**;
  45,685 + 298 = **45,983**. The 14 frozen shortfalls reproduce exactly (`BJ920001` 167,
  `BJ920006` 75, twelve at 0). All 52 `expected_price_dates` and `suspended_dates` in the
  reviewed bundle equal my derivation.
* **Both stores partition exactly**: zero mismatches on price-vs-derived, suspension-vs-
  derived and inventory-vs-table per symbol; zero price/suspension overlaps; **0** off-
  calendar dates, **0** dates between the warm-up end and research start, **0** dates before
  2022-05-01, **0** `ERROR` pseudo-dates, **0** duplicate business keys.
* **Suspension evidence** (R04): the 298 ledger dates fall into **25 intervals**; **all 28
  referenced evidence files exist at their recorded SHA-256**; for every interval the ledger
  dates equal exactly the pinned-calendar days of `[start, resume)` inside the symbol's
  windows; the last trading day before each interval and each `resume` day carry price rows;
  no price row lies inside any interval. **The one ongoing interval** — `SZ002731` from
  2026-09-01 — has no price row through the research end 2026-09-04 and a
  `confirmed_suspended_through` that covers it; **no resumption date is invented**. The one
  exchange-confirmed date, `SH600110` 2022-10-20, is a **DOM observation excerpt**
  (`raw_http_response_retained: false`), adjacent to the issuer-confirmed interval
  2022-10-21…2022-10-31; the last price row before the pair is 2022-10-19.
  **No suspension is inferred from a missing vendor row**: each date is inside an evidence
  interval.
* **Warm-up extension** (R05): `SZ002656` 289 captured / 211 overlap / **39** added,
  `SH600110` 320 / 242 / **8**, `SH600226` 327 / 249 / **1** — 48 total; **all 702 overlap
  rows are value-identical across the two captures** (4,212 field checks); the extra earlier
  rows (39 / 70 / 77) are retained audit-only and are **not** in either store.

### 3.3 `BJ920006` / 2023-12-04 — assessed separately (§5)

### 3.4 Stores, lineage, guards, publication

* **Full raw replay** (R05): every one of the **45,685** rows in **both** stores equals the
  value re-parsed from the raw bytes — **274,110 field comparisons per store, 0 mismatches**,
  0 extra, 0 missing. `row_records_sha256` recomputed from raw bytes + receipts =
  `5bf0da0f…` (matches). All **45,685 `row_evidence` lineage rows** match (raw / request /
  producer / parser / receipt / manifest hashes, `observed_at`, `point_index`, qualification
  hash). `qualification_records` equal the reviewed scopes. Every row is
  `adjustment_mode='none'`, `source='tonghuashun'`, `quality_status='qualified_candidate'`;
  `volume_unit='share'` for 50 stocks, `not_applicable` for the 2 benchmarks. 55 distinct
  capture timestamps; **no `trade_date` later than its `observed_at`**.
* **Guards** (`staging.py`): `PRODUCTION` = the two project-root databases; every input pin
  and destination is `.resolve()`d and compared against it; `_safe_existing_chain` rejects
  symlinks, reparse points and hard-linked files (**path-alias protection**); staging root
  must lie under `staging_runs/`; database files are refused as evidence inputs;
  `_open_write` accepts only the two run-dir destinations and **denies ATTACH/DETACH** via the
  SQLite authorizer. `run_actual_staging.AuditBoundary` additionally denies non-allowlisted
  connections, UNC/relative/implicit-mode URIs, sockets and processes (3 boundary tests
  re-run and passing).
* **Binding and atomic publication** (`staging.py:615-657`): both receipts must be issued by
  this run, `accepted`, bound to the same candidate fingerprint and input fingerprint, with
  unchanged validation inputs and unchanged receipt files; the pointer is written to a
  temporary and moved by a **single `os.replace`** after a full re-verification; failure
  leaves the previous pointer. `previous: null` in `CURRENT.json` — first publication.
* **Fail-closed tests.** 5 contract tests re-run: unknown/extra/duplicate/conflicting dates
  rejected; unverified/wrong-date/wrong-unit/non-positive-residual block scope rejected;
  rewritten or incomplete rows rejected; a partial "success" gate report rejected; the pinned
  replay reproduces 45,685 / 35,943 / 9,742 and the 39/8/1 extension.
* **Tamper run** `test_v2_20260910_041620_5f1eafd6`: `status: test_only_tamper_rejected`,
  `published: false`, no `CURRENT.json` in its root. Its stores were **not** opened by me.

### 3.5 Original gates and preservation

* **Original contract, unmodified, still FAILS and is retained**: research `exit 1` — P4 /
  M1 / M3 FAIL, `stock_rows=43729 verifiable=43729 contradicted=1`; warm-up `exit 1` — P4 /
  M1 / M3 / W1_pricing / W1_history / V3b FAIL. Retained at `research_original_gate.json`
  (`2b32454e…`) and `warmup_collection_original_gate.json` (`466b5164…`), and bound into the
  v2 receipts by hash. **The v2 P4 rule touched exactly one row** (the single contradicted
  row is `BJ920006` 2023-12-04).
* **v2 gates**: research — 20 required PASS, V3 not applicable; warm-up collection — 24
  required PASS, **V3b FAIL for exactly the frozen 14**. Not feature readiness, not strict
  PIT, not M3 readiness, not promotion — and the receipts say so.
* **Circularity note, resolved.** The v2 gate run substitutes `entry_eligibility` with the
  bundle's own key sets (`staging_v2.py:194-198`), so a v2 M1/M3/W1 PASS on its own would be
  partly self-referential. That is why R03 re-derives the keys from calendar + listing +
  suspension facts **without** the bundle and compares them to the stores directly. They
  agree.
* **Production preservation**: five byte-hash checkpoints (`before_stage` … `after_publication`)
  over **16 file positions**, all `matches: true`, method *"byte reads only; no production
  SQLite connection"*, baseline pinned `ad8c4b94…`; `production_sqlite_connections: 0`,
  `network_requests: 0`, `audit_denials: []`. I verified the receipts, not the files.
* **Source-name diagnostics.** All 45,685 rows carry `invalid_source_name`; the raw strings
  are runs of the private-use character U+F8F5 — a correct classification. Identity
  is by verified code mapping; the `instruments` table carries official issuer names; the
  gate's membership checks use symbol codes. **Code-based identity does prevent misuse of
  the garbled names.** One accuracy point: `row_evidence.source_name` is **NULL on every
  row** — the original text survives only in the raw `.bin` bodies (§8).

---

## 4. Source/evidence confidence, stated separately from code/test results

| Layer | Confidence | Basis |
|---|---|---|
| Code/test integrity of the candidate | **High** | full raw replay, recomputed fingerprints, lineage, partition, guards, tests |
| Coverage contract (keys, suspensions, extension, shortfalls) | **High** | independent derivation; 28/28 evidence files hash-verified; interval boundaries checked against the stores |
| Unadjusted basis | **High for the two controls; strong-by-inference for the other 50** | replayed cash-forward controls; identical request contract on one interface; per-row P4 amount/volume-vs-price consistency on 43,728 stock rows unconditionally |
| Units (share / CNY) | **High for scale; exactness not claimed** | static field chain + two SSE anchors binary32-equal; decimal differences retained |
| Issuer-document suspensions (297) | **High** | retained originals with hashes; boundaries consistent with prices |
| Exchange-DOM-only facts (1 suspension, 1 block trade) | **Medium** | excerpts without raw HTTP/screenshot — as Codex disclosed |
| `BJ920006` block-scope rule | **Medium-high, interpretation-level** | §5 |
| v2 contract authority | **Codex-recorded** user reply | symmetrical to the Claude-reported P1 adoption; corroborated by the user's own instruction to finish this step |

---

## 5. `BJ920006` / 2023-12-04 — independent assessment

**Stored values (both stores, unchanged):** O 12.45 · H 12.75 · L 12.15 · C 12.58 ·
V 1,610,724 · A 18,876,856; previous close (2023-12-01) 12.45.

**5.1 What the evidence chain actually is.**

1. **Exchange rule — proven from retained bytes, read by me.** Page 12 of the retained BSE
   《交易规则解读》 PDF (`faa129e2…`, 17 pages, 1,844,945 bytes) states:
   *大宗交易行情：不纳入指数和即时行情，成交量、成交金额分别计入当日该证券总成交量、总成交金额*
   — block-trade **volume and amount are each counted into the security's daily total
   volume and total amount**. The same page gives the price constraint *前收盘价的±30%或当日
   最高最低价之间* (§3.6.5). Both statements were read from the rendered page, not from an
   index excerpt.
2. **Official block record — DOM observation only.** `bse_837006_20231204`: 400,000 shares at
   9.25 (buyer/seller branches recorded), `raw_http_response_retained: false`. Amount
   3,700,000 is *derived* (400,000 × 9.25), not an observed field.
3. **Old/new code mapping.** `837006 ↔ BJ920006` via the retained BSE code-mapping file
   (`95d43bba…`, row 54).
4. **THS field scope — inferred.** The static review shows fields 13/19 are the host's
   *total* volume/turnover with no plugin scaling, but the embedded `QuoteFieldData.xml`
   carries **no unit, currency or scope attribute** — nothing in the vendor material says
   whether block trades are inside those totals.

**5.2 What the arithmetic proves, and what it does not.** With `Decimal`:
whole-day average 18,876,856 / 1,610,724 = **11.7195**, below `0.98 × low = 11.907` (P4
FAIL) — and, more tellingly, **below the auction low 12.15 itself**. An auction-only total
**cannot** average below the auction low; therefore THS's total for this key *necessarily
includes at least one trade below 12.15*. The only disclosed sub-low trade is the official
block at 9.25, which under §3.6.5 is permitted (9.25 lies within ±30% of the previous close
12.45 → [8.715, 16.185]) precisely *because* it is a block. Removing exactly that block:
(18,876,856 − 3,700,000) / (1,610,724 − 400,000) = **12.5353557045**, which lies **strictly
inside [12.15, 12.75]** — stronger than the 2% envelope requires. The block is 24.8% of
volume and 19.6% of amount. So the data itself proves *some* non-auction trade is included,
and the official block explains it exactly. What the arithmetic does **not** prove: that the
block is the *only* non-auction trade that day, or that THS's totals equal the exchange's
published daily totals in general.

**5.3 Classification.** This is a **reviewed source interpretation** — exchange rule (proven)
+ vendor field identity (static, scope-silent) + one official block record (DOM) + internal
consistency (strong) — **not a direct vendor specification**, and not "mere arithmetic
consistency" either, because the whole-day average being below the auction low is an
independent impossibility argument, not a fitted tolerance. The `scope_evidence_verified: True`
flag in the bundle is a **literal set by `contract_v2.build()` (line 173)**; the code itself
verifies only the PDF hash pin, the block-observation inventory, the identity mapping and the
arithmetic — page-12 *content* is a human reading (Codex's, and now mine, independently).
I did not treat the flag as evidence.

**5.4 One consistency point Codex's acceptance does not mention.** The SSE unit anchors'
own `reference_scope` reads *"single-day auction trades; exchange excludes block and
after-hours fixed-price trades"* — and THS matched those SSE figures to binary32 precision.
That is consistent with the BJ920006 interpretation **only if `SH600011` had no block or
after-hours trades on 2022-11-29 and 2026-05-29**, which is plausible but **unverified**.
The two observations that would turn the interpretation into direct evidence, either of which
Codex could retain with a single authorized retrieval:

* an official BSE daily statistic for `837006` on 2023-12-04 showing total volume
  **1,610,724** and total amount **18,876,856** (would prove THS total = exchange total incl.
  block; a differing official total would **refute** the rule and reinstate the P4 failure);
* the SSE block-trade disclosure for `600011` on the two anchor dates (expected: none).

**5.5 Decision on the rule.** Under the user-approved contract item 3 the rule is
**adequately supported for this one business key**: raw totals are unchanged in both stores,
the exception is recorded with its residual, P4 is not waived and no tolerance is fitted, and
the applicability condition (exchange totals include blocks) is proven from a retained
official document. It is **not a blocker to staging acceptance**. I recommend it be treated
as a **pre-promotion evidence item** (§5.4) rather than left as an interpretation when
production promotion is eventually considered.

---

## 6. M2 acceptance criteria — proof map and closure decision

Authoritative scope is quoted from `THREE_YEAR_RESEARCH_EXECUTION_GOAL.md:173-185`
(`f8b699e5…`) and the user-approved `real_session_v2` contract. No reduced or expanded
definition is used.

| Criterion (goal line) | Proof | Status |
|---|---|---|
| Prerequisite — explicit user authorization after M1 review | M1 validated; v2 contract adopted by user reply `可以` (`acceptance_v2_authority.json`, Codex-recorded); user's own instruction for this task confirms the step | **Met** (attribution recorded) |
| `:181` backfill runs to a staging or copied database first | two isolated stores under `staging_runs/…/run_…/`; production untouched at 5 byte-hash checkpoints; `production_promoted: false` everywhere | **Met** |
| `:182` before/after manifests, counts, hashes, coverage, rejected rows, source lineage | production baseline before/after (16 positions); candidate fingerprint; `coverage_inventory` 45,983 keys; `row_evidence` lineage on all 45,685 rows; 298 suspensions with evidence hashes; 1 rejected capture attempt (`empty_points`) and 186 audit-only extension rows recorded | **Met** |
| `:183` no `ERROR` pseudo-dates or duplicate `(symbol, trade_date, adjustment)` in the research view | R03: 0 and 0 on both stores; `research_prices` = 35,943 rows, all `adjustment_mode='none'` | **Met** |
| `:184` corporate-action adjustment consistent through the entire interval | corpus is uniformly **unadjusted**: fixed request contract on one interface; 0/1/2 discrimination and cash-forward controls independently replayed (0 mismatches); the two control symbols' staged rows equal mode 0 on all 978 dates; per-row P4 raw-basis consistency on 43,728 stock rows unconditionally and 1 row under the source-qualified block scope | **Met**, with §5 recorded |
| `:185` production promotion, if authorized, atomic/recoverable and independently checked | **not requested and not authorized**; the staging pointer publication is atomic and is now independently checked | **N/A — remains a separate authorization** |

**Closure decision.** Under the approved 52-security scope and the user-approved v2 contract,
**this delivery satisfies M2 as a validated three-year staging corpus.** No pre-existing
*required* M2 condition is unmet. The following are explicitly **not** required by
`:173-185` and are preserved as separate, unchanged facts rather than blockers:

* the Sina/AkShare route's capability **FAIL** and its two immutable `EV6` results, both spent
  Sina capture grants — a different source, not superseded and not repaired;
* the Sina reference-basis items **P1 (open)** and **U-6 (deferred)**, whose evaluator
  exposes no `eligible=true` path — they concern the *Sina* basis label and are not inputs to
  this corpus;
* the 14 listing-depth shortfalls (collection integrity only; **no** 250-bar feature
  readiness is claimed for them);
* strict point-in-time reconstruction, M3 labels, training and production promotion.

---

## 7. Substantive findings (with reproducers)

| # | Finding | Severity | Where | Reproducer |
|---|---|---|---|---|
| F1 | `scope_evidence_verified: True` is a literal, not a computed verification; page-12 content rests on human reading | Record accuracy | `contract_v2.py:173`; bundle `block_scope` | read line 173; R06 output + §5 |
| F2 | SSE anchor `reference_scope` excludes block trades while THS matched them — the BJ920006 interpretation assumes no blocks on the anchor dates (unverified) | Evidence gap, non-blocking | `unit_anchor_evidence.json` `anchors[*].reference_scope` | grep `reference_scope`; §5.4 |
| F3 | `row_evidence.source_name` is NULL on all 45,685 rows; the acceptance's "原文及诊断保留" holds only for the raw `.bin` bodies, not the store | Record accuracy | `contract_v2.py:113`; R05 `source_name_null_rows` | `SELECT COUNT(*) FROM row_evidence WHERE source_name IS NULL` (ro) |
| F4 | v2 gate M1/M3/W1 use bundle-derived keys via monkeypatched `entry_eligibility` (self-referential on its own) | Design note, resolved by independent derivation | `staging_v2.py:194-198` | R03 |
| F5 | Benchmark `instruments.name` is empty for both indices | Cosmetic | `instruments` table | `SELECT * FROM instruments WHERE symbol LIKE 'SH000%'` |
| F6 | The block record and one suspension are DOM excerpts without raw HTTP/screenshot | Disclosed evidence-strength limit | `exchange_dom_observations_20260910.json` | read file |

No finding changes any stored value, any key, any gate outcome or the verdict.

---

## 8. Recommended corrections and next steps (for Codex; nothing implemented here)

**Non-blocking record corrections (documentation/bundle wording only, no data change):**

1. State in the acceptance record that `scope_evidence_verified` is asserted by `build()`
   after hash, inventory, identity and arithmetic checks, and that the page-12 rule content
   was verified by **two independent human readings** (Codex, Claude) of the retained PDF.
2. Correct "原文及诊断保留" to: diagnostics are stored per row; the original garbled name
   strings are retained **in the raw response bodies only**, `row_evidence.source_name` is
   NULL by design.
3. Record the SSE-anchor `reference_scope` point (§5.4) alongside the BJ920006 interpretation.

**Pre-promotion evidence item (one authorized retrieval, not requested here):** retain an
official BSE daily total for `837006` / 2023-12-04 and, optionally, the SSE block-trade
disclosure for `600011` on 2022-11-29 and 2026-05-29. Matching figures convert §5 from
interpretation to observation; a differing BSE total would refute the rule and must reinstate
the original P4 failure for that key.

**Nothing else is required to close M2 at staging level.** Production promotion, strict PIT,
M3 and training remain separate decisions and separate authorizations.

---

## 9. Preservation statement

Files created: `claude methods/M2_TONGHUASUN_V2_CLAUDE_INDEPENDENT_REVIEW_20260910.md` (this
report) and `claude methods/_m2_ths_v2_claude_review_20260910/` (r01–r08 scripts, their JSON
outputs, the focused-test transcript, `review_manifest.json`). Nothing else was written. The
phase directory, both candidate stores, the pointer, the tamper-test run, all captures, old
gates, official documents, production databases and sidecars, historical datasets, knowledge
files and coordination JSON are unchanged; the manifest's 31 artifacts and 479 transitive pins
re-verified at the start of this review. Live trading disabled throughout.

**Status: `proposed for review` — Codex to integrate.**
