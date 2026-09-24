# M3-02-FROZEN-READER-20260910 — Claude delivery

Status: **ready_for_review** (proposed; not Codex-validated; no actual case review performed; M3 not complete). Owner: Claude, existing ZK-trading / Fable 5.1 project advice (fork). Independent acceptance, actual case-review dispatch and coordination: Codex. Date: 2026-09-10.

Inputs verified before work: review `M3_01_R3_CODEX_REVIEW_20260910.md` `871999df…13ef`; `policy_freeze.json` `925ae86f…891f`; task `13908dc6…3d96`; accepted label module `e20eb21c…` and tests `41eba60b…` unchanged (re-verified after all work). Both in-task feedback notes from Codex were incorporated into this same delivery: `M3_02_WORKING_BOUNDARY_FEEDBACK.md` (`e39ac429…`) and `M3_02_WORKING_PACKET_CUTOFF_FEEDBACK.md` (`addaf3e1…`).

## 1. What was built

| Path | SHA-256 | Note |
| --- | --- | --- |
| `backend/app/research/m3_frozen_reader.py` | `288594cf0acf977c5ede3f5dec6584134a879889793c4c3542d01b1d7f7ae5af` | new; `m3_frozen_reader.v3`; 1,126 lines; stdlib only; loads the accepted label module by file path and verifies its pin |
| `backend/tests/test_m3_frozen_reader.py` | `22e79001acc1e58febd7865fbf01facd927488c87fc1ed2cfbd6d7c287b608ce` | new; 20 synthetic-fixture tests (exact M2 DDL, SYN symbols, scratch-confined) |
| `claude methods/_m3_20260910/claude_02/` | pinned in `artifact_manifest.json` | runner, verifier, manifest builder, data dictionary, transcripts, two runs |

Reader contract (all enforced in code and tested):

- **Fixed real configuration.** A non-synthetic `FrozenInputs` must equal `FROZEN_M2` field by field (exact paths, sha256, byte sizes, metadata/policy pins, development dates, `price_max_date`, benchmark role, evidence-assembly time); the comparison is pure and runs before any hashing, file read or connection (`validate_configuration` at the top of `run_development`, `reconcile` and `ReadOnlyStore.__enter__`). Synthetic sets are confined to `claude_02/scratch/`, can never name a real store, and cannot relabel real data by flipping the flag. A store cannot be opened without either the two fixed real specs or a validated synthetic set that lists it. Output directories must lie inside `claude_02/runs` or `claude_02/scratch` (pure path check) and are never overwritten.
- **No construction I/O.** `ReadOnlyStore.__init__` stores configuration only; verification (path/size/hash/sidecars) happens on `__enter__` immediately before connecting and again on `__exit__`. Connections use `mode=ro&immutable=1`, `PRAGMA query_only=ON` (read back = 1), extension loading disabled, an authorizer allowing SELECT/READ/FUNCTION and read-only pragmas only. Every statement is logged with its bound parameters and connection role; every OHLCVA `SELECT` carries `trade_date <= '2025-03-31'`.
- **Reconciliation** of every permitted row across both stores (six numerics, `none` mode, source, quality, units vs frozen scope), full `row_evidence` lineage against the frozen captures (`point_index` range, `observed_at == fetched_at == capture observed_at`, qualification sha), coverage inventory and suspension records (canonical ledger hash) in both stores, expected keys ↔ stored keys, price/suspension mutual exclusion. Structural problems refuse the run; row problems exclude rows with exact reasons.
- **Cutoff semantics.** `Cutoff(date, date+'T16:00:00+08:00', 'retrospective')` (`close+3600s`); calendar = pinned AkShare file sliced `2022-06-30..2025-03-31` (fingerprint `87014ce0…`), `available_at` = evidence assembly time (`2026-09-10T06:52:37Z`, explicitly not historical availability); coverage = per-session evidence-key coverage of the 50-stock cohort (benchmarks excluded); security context = listing date with source grade, ST/float/turnover/name unknown, partial known cash events with `ex_date <= cutoff` for SH600011/BJ920000 only, evidence assembly time as availability. Benchmarks keep `not_applicable` units, price-only regime (SH000300; SH000001 reconciled but not consumed).
- **Review-facing packets contain nothing after the representative cutoff** (feedback 2): `build_cutoff_packet` receives only the three prefix members, the representative and same-date controls; `verify_run.py` scans every date token of every packet; retrospective episode metadata (end, status, later transitions, censoring) is written separately to `episode_audit/` with `not_cutoff_known=true`, and `episodes.json` is labelled as retrospective inventory. `cutoff_packet_hash` is the stable review binding; a synthetic extension-invariance test proves it is unchanged when later records change while the retrospective audit legitimately differs.

## 2. Runs (both retained)

| Run | Reader | Result | Role |
| --- | --- | --- | --- |
| `runs/dev_run_01` | `01e2f1ca…` (v1) | completed, 243.3 s, 17,554 records; packets carried retrospective fields (Codex audit: 210/225, 39 with later transitions; reproduced by `verify_run.py`: `transcripts/verify_run_dev_run_01_pre_feedback.txt`) | earlier attempt, pre-feedback evidence |
| **`runs/dev_run_02`** | **`288594cf…` (v3)** | completed, 244.8 s, 17,554 records; `verify_run.py` → **0 problems** (17,554 records, 50 chronology files, 225 packets, 225 audits, 140 matches revalidated) | **final** |

Labels, counts, waterfall, inventory, coverage, exclusions and controls are byte-identical between the two runs (`waterfall.json`, `inventory.json`, `cohort_coverage.json`, `exclusions.json`, `decision_exclusions.json`, `controls.json` share hashes). Record hashes differ only because the universe provenance reference became content-bound (`pilot_symbols.csv sha256=97e251ae…` instead of an absolute path); no label changed.

Actual connections in the final run (from `run_receipt.json` / `real_run_transcript.json`): exactly two — `trading.sqlite3` (`c0b26660…`, 38,969,344 bytes) and `history.sqlite3` (`eda17434…`, 10,604,544 bytes), mode `real`, `query_only_read_back=1`, sha256 identical before and after, 0 denied actions, 24 statements (10 parameterised, all with `['2025-03-31']`). No production SQLite, no network, no subprocess. All frozen pins (both stores, qualification, calendar, universe, metadata index, policy freeze, label module and tests) unchanged before/after.

## 3. Development inventory and waterfall (`dev_run_02`)

- Universe: 50 stocks + 2 benchmarks; 378 development sessions (2023-09-04 … 2025-03-31); permitted rows 27,900 (identical in both stores), 200 evidenced suspensions, 17,785 rows beyond the bound counted but never selected; **0 row exclusions, 0 structural problems**; 49 symbols with permitted rows (BJ920003/BJ920005/BJ920007 list after the bound).
- Expected stock-session keys 18,900 → `not_listed` 1,346 (12 stocks listing inside or after the interval) → **17,554 decision records** (observed 17,402, suspended 152, missing 0; `no_observations_before_cutoff` 0).
- Quality gates at the decision: `missing_feature` 4,288, `insufficient_warmup` 2,451 (11 stocks with 82–249-bar deficits at their first decision), `known_corporate_action_in_window` 552, `many_suspensions_in_window` 454, `long_no_price_run_in_window` 452, `suspension_on_decision_session` 152, `stale_last_price` 141, `scope_exception_on_decision_bar` 1 (BJ920006/2023-12-04).
- Phases: accumulation 7,324; indeterminate 6,905; failed_markup 2,259; markup 966; distribution 100. Selection: candidate 6,221; non_candidate 4,428; indeterminate 6,905.
- Episodes (retrospective inventory): 1,626 total — accumulation 342, markup 412, failed_markup 347, distribution 81, indeterminate 444. Accumulation with an established three-session prefix: **225**; representative a candidate: 140; not a candidate: 85.
- Same-date matching (frozen rule): **32 episodes with 3–5 distinct controls** (15×3, 3×4, 14×5), 108 unmatched (0 controls: 38; 1: 58; 2: 12); 127 unique controls, no control reused. Representative dates 2023-11-20 … 2025-03-31; matched episodes concentrate in 18 symbols (SH600176 ×5, SH600777 ×4, SH600129 ×3 …).
- **Pending potential positives: 32; effective dependence groups among them: 23; independently reviewed positives: 0; qualified reviewed positive episodes: 0; target (≥ 50 reviewed positive episodes with 3–5 controls): not met.** Even if every pending episode were confirmed by actual individual reviews, the development interval under the frozen policy yields at most 32 candidate episodes (23 dependence groups) — an observed shortfall reported with the full waterfall, without tuning, universe/period extension or held-out use.
- `strict_pit_eligible` 0 and `training_eligible` 0 on every record; every ledger empty and `pending_review`.

## 4. Commands actually run (absolute paths) and results

```powershell
# pins (task/review/freeze; accepted label files)
sha256sum 'D:\codex-A股交易\claude methods\M3_01_R3_CODEX_REVIEW_20260910.md' 'D:\codex-A股交易\claude methods\_m3_20260910\policy_freeze.json' 'D:\codex-A股交易\claude methods\M3_02_FROZEN_READER_CLAUDE_TASK_20260910.md'
#   -> 871999df… / 925ae86f… / 13908dc6… (match); m3_labels.py e20eb21c…, test_m3_labels.py 41eba60b… (unchanged)

# synthetic reader tests (stdlib unittest by file path; fixtures under claude_02/scratch, removed afterwards; real stores never opened)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\backend\tests\test_m3_frozen_reader.py' -v
#   run_01: exit 1 (6 F + 1 E: fixture shape, nested-connection hash index, coverage/suspension ordering) — retained
#   run_02: exit 1 (2 F: CRLF write hashing, conflict ordering) — retained
#   run_03: exit 0, 16 passed
#   run_04 (after boundary feedback): exit 1 (1 F: construction-time expectation moved to enter) — retained
#   run_05: exit 0, 19 passed
#   run_06 (after packet feedback): exit 1 (1 F: fixture-path provenance in the invariance test) — retained
#   run_07 (final): exit 0, "Ran 20 tests in 13.874s", OK

# Codex's boundary file against the final reader (read-only; no Codex output written)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\codex\test_independent_reader_boundary.py' -v
#   -> exit 0, 4 ok (was 1 ok / 3 FAIL on the working reader 01e2f1ca…)

# lint (project rules, isolated because venv ruff 0.15.20 vs pyproject ==0.16.6); syntax via compile()/AST, no py_compile
& 'D:\codex-A股交易\backend\.venv\Scripts\ruff.exe' check --isolated --no-cache --select E4,E7,E9,F --line-length 100 --target-version py311 <reader> <tests> <claude_02 scripts>
#   -> All checks passed!

# bounded real runs (read-only; the only two connections are the pinned candidate stores)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\claude_02\run_real_development.py' dev_run_01   # exit 0, 243.3 s, reader 01e2f1ca… (pre-feedback; retained)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\claude_02\run_real_development.py' dev_run_02   # exit 0, 244.8 s, reader 288594cf… (final)

# independent re-verification without SQLite
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\claude_02\verify_run.py' dev_run_02   # exit 0, problems []
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\claude_02\verify_run.py' dev_run_01   # exit 1 (packet retrospective fields / later dates — the pre-feedback defect, retained)

# manifest (run last)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\claude_02\build_manifest.py' dev_run_02

# read-only git checks
git -C 'D:\codex-A股交易' status --short ; git -C 'D:\codex-A股交易' diff --check ; git -C 'D:\codex-A股交易' rev-parse --short HEAD
#   -> only the two new backend files (untracked) and claude_02/ are new; index empty; HEAD 73f266d; diff --check exit 0 (pre-existing CRLF warnings)
```

No `__pycache__` entry for the new files or Codex's test files; the scratch directory is empty after the suite.

## 5. Synthetic test coverage (20 tests)

Source boundary: invalid path / hash / size / sidecar refused before connecting; writes, ATTACH and PRAGMA writes denied on the read-only connection (file hash unchanged); `query_only` read-back; statements logged with parameters; fixed real configuration enforced before any I/O (widened cutoff, replaced source, changed pins/dates/benchmark → `real_configuration_not_frozen` with mocked I/O never reached); synthetic confinement (outside scratch, real store under a synthetic flag, price bound beyond development end, unauthorized store); construction performs no file I/O; output scope enforced without touching the path; label-module and policy pins enforced; real stores never opened by the suite. Reconciliation: clean fixture reconciles completely within the bound; corrupted fixtures (numeric mismatch, missing evidence, observed_at mismatch, price/suspension conflict, qualification hash) are excluded or refused; known events must agree with the frozen qualification; context filters events by cutoff and keeps unknowns. Development run: complete/bounded/pending-review receipt; every chronology record verified by the frozen module with pending ledgers and consumed dates within the bound; no held-out prices and late events filtered; suspension and late listing represented; cutoff packets bound to prefix/controls with no later dates and separate audit files; **extension invariance** (later records changed → identical cutoff packets and hashes, retrospective audits may differ); deterministic outputs; refusal to overwrite; structural problems refuse the run.

## 6. Sources read and preservation

Pinned in `artifact_manifest.json` (`sources_read`, `preserved_originals`): task/review/freeze, reader contract preparation, rubric, metadata index + README, R3 validation receipt, Codex's bound R3 test, R3 manifest and machine policy, goal document, AGENTS/COLLABORATION, frozen qualification, M2 staging sources (read-only, never imported), frozen schema/controls JSON, pilot CSV, calendar, both candidate stores, both feedback notes and the referenced Codex boundary/packet-audit sources and receipts. Preserved and re-verified: accepted label module/tests, policy freeze, R1/R2/R3 manifests, both candidate stores, calendar, universe, metadata index, feedback notes. No Codex file, prior delivery, M2 path, production database, legacy source/data/knowledge, configuration or Git index was touched.

## 7. Limitations (honest)

1. Retrospective only: every record is `strict_pit=false`, `training_eligible=false`; capture time (2026) is not historical availability; calendar/context/coverage availability is the evidence assembly time.
2. 48 stocks have unknown corporate-action coverage; the two partial sets gate windows only; ST/float/turnover/names unknown → conservative limit handling.
3. Listing dates outside the nine BJ official facts carry pilot-metadata grade; 11 stocks start the interval with a warmup deficit (82–249 bars); three stocks have no development observations at all.
4. Price feature windows count valid bars; calendar windows count sessions — windows compressed by suspensions are not fixed elapsed spans.
5. The 32 matched episodes are potential positives pending actual individual reviews (Claude and Codex, each with execution evidence and `case_prefix_hash` binding); none is a reviewed positive. The interval cannot reach 50 under the frozen policy; that shortfall is reported, not repaired.
6. Same-date matching is strict (108 of 140 candidate representatives found < 3 controls); this is the accepted rule, not a defect to tune here.

## 8. Rollback

Delete `backend/app/research/m3_frozen_reader.py`, `backend/tests/test_m3_frozen_reader.py` and `claude methods/_m3_20260910/claude_02/`. Nothing else changed.

## 9. Next step (Codex-owned; not started by Claude)

Independent validation of this stage; if accepted, dispatch of actual per-episode reviews (M3-03) using the cutoff packets only (`packets/`, not `episode_audit/`), with each reviewer binding `case_prefix_hash` and execution evidence, dependence and control-reuse audit, and an honest final M3 accounting.
