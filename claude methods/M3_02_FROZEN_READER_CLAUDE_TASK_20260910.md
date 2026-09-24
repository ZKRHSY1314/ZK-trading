# M3-02-FROZEN-READER-20260910

Owner: Claude in the existing Fable 5.1 project advice (fork). Independent acceptance and coordination: Codex. User authorization: continue M3 with the same workflow and 15-minute inspections. This is the single next task after accepted R3; do not create another agent/session or redispatch yourself.

## Read first and verify pins

1. `AGENTS.md` and `CODEX_CLAUDE_COLLABORATION.md`.
2. `claude methods/M3_01_R3_CODEX_REVIEW_20260910.md`, SHA-256 `871999df90a932b69e7ca85e74b92e668ce5a0f5f43d2f0bb5caa3b8791313ef`.
3. `claude methods/_m3_20260910/policy_freeze.json`, SHA-256 `925ae86f772908babef6bc6a08a1ace58c2db7a5e71c7f97af8ad52f2c7a891f`.
4. `claude methods/_m3_20260910/codex/READER_CONTRACT_PREPARATION.md`, `codex/metadata_index_01/README.md`, `codex/CASE_REVIEW_RUBRIC.md`, and the original M3 criteria in `THREE_YEAR_RESEARCH_EXECUTION_GOAL.md:187-208`.

R3 manifest `7060f61f8eb637d6e92efb075e6a0cfdad041e370d30874afb9172a2d04fce39` is accepted. Module `backend/app/research/m3_labels.py` must remain `e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393`; its tests must remain `41eba60b21b507250f9a9a4f359fdc330232306c61b535f3d82db18ba9e45180`. Policy is `0.3.0-draft`, `m3.labels.output.v3`, policy_hash `d436ba1402f9d0b53e1008c2a2bd50678a457c3e050561a59ded30dbbd21c025`. Codex independently ran 105 delivery, 24 adapted consumer and 8 numerical tests successfully. The independent final-API source is `codex/test_independent_r3_bound.py`; the earlier R3 file is intentionally preserved, not a new unresolved defect.

## Objective and exact write scope

Implement and execute a deterministic, isolated, read-only reader of the exact M2 candidate stores. Reconcile the permitted development inputs, generate the complete development label chronology, episode-prefix inventory and same-date control evidence as **pending review**. Provide a complete eligibility/exclusion waterfall so later actual individual reviews can determine whether the original target is supported.

You may create and edit only:

- `backend/app/research/m3_frozen_reader.py`
- `backend/tests/test_m3_frozen_reader.py`
- `claude methods/_m3_20260910/claude_02/` (new code runners, synthetic fixtures, derived development outputs, evidence packets, transcripts and manifest)

Do not edit the accepted label module/tests, any prior delivery, Codex-owned files, coordination, PLAN, policy_freeze, M2, legacy sources/data/knowledge, services, configuration, package dependencies or Git index. Avoid bytecode/caches outside your own folder (`-B`, no py_compile). No client/Tonghuashun actions, new market capture, network, account/fund/order access, service startup, training/backtest/M4, scheduler changes, new agents, Git stage/commit/push/PR or external messages. Reader import and construction must have no I/O side effects. Preserve live trading disabled and review-only throughout.

This task explicitly authorizes creation of **new isolated derived M3 data** with the validation below. It authorizes no mutation of either M2 database or any existing dataset. Synthetic SQLite fixtures may be created only below your new `claude_02/` output/scratch scope and must never be mistaken for the actual sources.

## Exact real SQLite read boundary

Only these two real files may be connected, strictly read-only:

`D:\codex-A股交易\claude methods\_m2_codex_implementation_20260910\staging_runs\ths_v2_20260910_041710_97ef9c09\run_ths_v2_20260910_041710_97ef9c09\trading.sqlite3`

SHA-256 `c0b26660ab903541e7e213ee312c565be73547bb3cc8c142486999717e3edeca`, 38,969,344 bytes.

`D:\codex-A股交易\claude methods\_m2_codex_implementation_20260910\staging_runs\ths_v2_20260910_041710_97ef9c09\run_ths_v2_20260910_041710_97ef9c09\history.sqlite3`

SHA-256 `eda17434ab67496c33eed275b35045c140bad72802b4dcbf981ff22422c53003`, 10,604,544 bytes.

Resolve and validate these exact paths and byte hashes before connecting; reject missing/changed files, unexpected sidecars or other paths. Use SQLite read-only URI and query-only connection settings, with write/attach/extension denial where practical. Never instantiate existing application/staging service classes, which may create or mutate databases. Never fall back to a production database, default path, in-memory fake real source, or alternative provider. The two stores originate from the same capture: agreement is storage reconciliation, not independent market corroboration.

**Real price consumption is limited to trade_date <= 2025-03-31**, including frozen pre-2023-09-04 warmup. Generate labels only for development decisions 2023-09-04 through 2025-03-31. A whole-file hash, schema inspection or count/key metadata is allowed for integrity; do not select validation/final-holdout OHLCVA, generate their features, pick cases from them, or use future outcomes. Keep the original validation/holdout intervals unopened for analytical use.

Verify the frozen qualification `qualification_v2_reviewed.json` (`992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37`), candidate/contract identities and required evidence pins. Metadata index `codex/metadata_index_01/index.json` (`14f1bad7d393b4e15bf73111a9d96a78c8b156784f9ccbb084d6b606d3a152e9`) is a convenience index, not a substitute for row reconciliation. Its source data is ordinary frozen metadata/documents, not authorization for new network retrieval.

## Source mapping and cutoff semantics

Use the static mapping preparation document. Specifically:

- Reconcile each permitted trading `daily_bar_cache` row against history `daily_bars`: keys, six numeric fields, unadjusted mode, source and corresponding frozen qualification. Preserve exact stored values; no interpolation, zero filling, guessed adjustment factors or silently dropped abnormal rows.
- Join trading `row_evidence` to every price key and verify its complete raw/request/producer/parser/capture/qualification lineage and point index. Retain `observed_at` exactly; it must agree with history `fetched_at`. History has no row_evidence table. Verify stored qualification records against the corresponding frozen qualification, including record hashes and units.
- Stocks retain share/CNY; benchmarks retain not_applicable/not_applicable, with index-level OHLC and uninterpreted aggregates under the accepted API. Benchmarks are not cases or controls. Preserve the single conditional BJ920006/2023-12-04 scope interpretation without expanding it.
- Reconcile coverage_inventory and suspension_records in both stores. A full-day suspension has no OHLCVA; the suspension record hash binds the canonical full qualification entry, separately from the document hash. Preserve retrospective resumption evidence without pretending the resumption date was known earlier.
- Load the pinned calendar (`f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656`) and pilot universe (`97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe`). Keep all 50 stocks and 2 benchmarks in the inventory, including later-listed stocks with no development observations. A symbol outside the universe requires a separate future decision; do not add SZ002115/SZ002081.
- All actual labels use `Cutoff(date, date+'T16:00:00+08:00', mode='retrospective')`, i.e. close+3600s. Preserve the 2026 capture time as capture time, not historical system availability. Calendar/context original availability is unproved. If a present evidence-assembly timestamp is used, name it honestly as such and retain strict_pit=false/training_eligible=false; never substitute announcement URL dates or file mtimes.
- Keep historical ST, float shares, turnover and unavailable names unknown; do not infer them from present names. Preserve listing source grades. For partial known cash events, only events on/before the current cutoff can enter its context; keep complete action coverage unknown. The two stocks have nine known events over the full retained range, not nine events known at every cutoff.
- Report two distinct per-date cohort measures: evidence-key coverage `(valid price keys + evidenced full-day suspension keys) / expected listed frozen stocks`, and price availability `valid price keys / expected listed frozen stocks`. Use the evidence-key coverage, with explicit denominator/source/observation time, for `Coverage` in this task; do not call this full-market coverage or reuse old pilot coverage numbers. Exclude the two benchmarks from that stock denominator. No expected listed stock means explicit unknown, not 100%.
- Preserve the verified numerical kernel: stock feature windows count valid price bars; gap/suspension/episode/holding windows use exchange calendar sessions. Document the difference; do not tune the policy or imply fixed elapsed time for a window compressed by suspensions.

## Complete chronology and pending case evidence

For every stock, account for each development exchange session relative to its listing and source range. Generate all applicable decision records in chronology, including indeterminate/non-candidate/failed states and documented missing/suspended decisions. Do not filter to eligible or later successful days before forming episodes. Retain exclusions with exact symbol/date/reason and reconciled counts.

Use the accepted module and exact frozen policy hash. Output full verified cores with empty validated review ledgers; no fabricated reviewer ids or execution receipts. Preserve source mappings sufficient for Codex to independently tie a core to the actual input rows, and validate record/core fingerprints. Consider compressed deterministic JSONL (fixed gzip mtime) if full chronology is large; provide a simple reader and exact count/hash. Refuse to overwrite any pre-existing run directory.

Build complete episode inventories, immutable three-session prefix proofs and same-date control pools/sets using the policy. Retain all candidate episodes, missing-duration cases, unmatched candidates and reasons, dependence groups, control reuse and the original full eligible pool/ranking. No outcome or later-return fields enter selection. Positive counts remain **pending review**; do not call potential candidate episodes independently reviewed positives.

Produce compact per-episode evidence packets with representative cutoff/hash/prefix, first three member bindings, preceding price-context references and relevant numerical values, supporting and contradicting evidence, known uncertainties, matched control cores/evidence, and exclusion reasons where applicable. Preserve ambiguous/failed cases. The packets should support actual individual Claude and Codex reviews in a later bounded task, not substitute automatic labels for those reviews. Do not add review entries in this task.

Create a complete waterfall across expected stock-date keys, source-validated decisions, warmup/quality restrictions, phase and selection states, duration-established episodes, matched episodes, and pending reviews. The target is >=50 independently reviewed positive episodes with 3–5 controls each, with dependence groups reported separately. If the potential inventory is smaller, report the observed limitation with exhaustive counts; do not tune, extend the universe/period, or fabricate balance. This task alone cannot close M3.

## Validation and delivery

First test the reader using explicit synthetic fixtures in the new isolated scope. Cover invalid source path/hash, attempted writes/attach, missing/conflicting keys and lineage, stock/index unit distinctions, suspension-vs-price conflicts, no held-out price consumption, late event/context filtering, deterministic outputs, and preservation of review-only/live-off/training-ineligible status. Prove a meaningful admissible synthetic read-to-label-to-prefix/control path, and genuine failures on corrupted fixtures. Tests must not accidentally open real sources unless the explicit real-read entry point is being exercised.

Then execute the bounded real development run. Record actual commands, timing, code/input hashes, rows selected, row-level reconciliation, counts and failures. Before/after byte hashes and file/sidecar checks of both candidate stores and all frozen input artifacts must agree; no production SQLite connection. Keep unsuccessful attempts and new runs separately. Do not loop across new output names to hide a failure; explain corrections and rerun only where required.

Deliver `claude_02/DELIVERY.md`, source/read/output manifest, validation transcripts, data dictionary, development inventory/waterfall, complete chronology, episode/control packets and limitations. A stable final manifest must pin every declared output/source plus the accepted label policy/module and identify every actual database connection. Mark ready_for_review only when files exist and hashes match, then stop. Codex independently validates this stage, dispatches actual case review, and retains the existing 15-minute inspection schedule.
