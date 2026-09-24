# M3-01-R2-CONTRACT-FIX-20260910 — Claude delivery

Status: **ready_for_review** (proposed; not Codex-validated, not user-accepted; M3 not complete). Owner: Claude, existing ZK-trading / Fable 5.1 project advice (fork). Reviewer / coordinator: Codex. Date: 2026-09-10.

Inputs verified before editing: review `M3_01_CODEX_REVIEW_20260910.md` sha256 `19a825294c65f00edd8c2d78fc19b109fc92f485c6b1c04643711fd2bea111f0`; task `M3_01_R2_CLAUDE_TASK_20260910.md` `48bdad1e9ec9b07052822357c87bdf0a493932c11b634fdb8c9be7dbb1cadd09`; baseline module `6a0590cf…`, tests `efa2e21c…`, manifest `428bb425…` all matched on disk before the first write; no concurrent writer appeared in the two owned paths.

## 1. What changed (one coherent contract, policy `0.2.0-draft`, schema `m3.labels.output.v2`)

| Finding | Correction in `backend/app/research/m3_labels.py` |
| --- | --- |
| R1 matching identity/counts | `match_controls` now: same decision date, same mode + declared cutoff convention (`close+<s>`), same policy hash **and** version, same known band and known regime, same universe sha256/membership and synthetic flag, stock role only, `current_state="observed"`, distinct symbols; identical duplicates collapse (counted), conflicting duplicates (same symbol+date, different `record_hash`) raise; full records verified via `record_hash`, summaries must carry every field incl. `record_hash` (`malformed_summary`); outcome fields raise; `unmatched` explicit; split admission enforced via `guard_final_holdout`. The 0.1 ±10-session draft window is withdrawn and recorded as such in the policy. |
| R2 review provenance | `ReviewRecord` bound to `(case_episode_id, case_record_hash, case_policy_hash)` with non-empty `evidence_refs` and `execution_ref`, tz-aware time, `agent`/`human` only, `synthetic` flag; `attach_review` verifies the case, the binding, the ledger hash, rejects duplicates and conflicting duplicates unless explicitly superseded (own earlier entry hash + reason), preserves disagreement as `disputed`; ledger has its own `ledger_hash`, label `record_hash` unchanged; `independence_asserted_by_generator=false`. `library_counts` distinguishes records / review states / positively-reviewed / qualified positives (development-only, in-universe, observed, candidate, non-synthetic reviews, 3–5 distinct controls) / effective dependence groups; synthetic never counts. |
| R3 decision identity | `decision_fingerprint` over stock rows, benchmark rows, security facts, coverage, calendar, universe, cutoff, prior and position state → `episode_id`; `record_hash` over the core (excludes ledger + offered-only diagnostics); `verify_record` in every consumer. Rules read a private `_RULES` copy; `policy_document()` exports a deep copy; `assert_policy_integrity()` re-hashes live and exported copies on every entry point (`policy_hash_mismatch` fail-closed). |
| R4 non-price inputs | `SecurityContext.validated()` (enums, dates, numbers, bools, ordering, evidence + availability for any non-unknown fact; `partial_known` added; `none_verified` never inferred); `Coverage` object with evidence/availability, bool/NaN/out-of-range rejected, `None` = explicit unknown; facts not available at a strict cutoff are not used; whole-output `pit.facts` per consumed class; `captured_after_decision_window` diagnostic. |
| R5 calendar/current data | mandatory `SessionCalendar` with fingerprint/source/availability/synthetic flag; `current_state` observed/suspended/missing; determinate selection only when observed; interior missing sessions, no-price runs, suspension counts and staleness in sessions; observations outside the calendar rejected; `label_series` keeps the request's convention (no 15:00 reset). |
| R6 position events | `PositionState` with basis/evidence/availability; chronology and reference-price verification; determinate stop/exit/hold only with verified basis (`none_verified`/`complete_known`, no ex-date in the holding window, decision session observed, reference bar consumed); otherwise `review_required` (condition reported, not claimed) or `unknown`; invalidation remains a phase proxy. |
| R7 episodes/dependence | `build_episodes(outputs, calendar)`: verified records, chronological, unique dates, one symbol/policy/mode/convention/calendar/universe, consecutive sessions (series gap closes), real `selection_path`/`selection_at_end`/`eligibility_changes`, `min_duration_established_at` (never back-labelled), open/closed/ambiguous/failed kinds; `dependence_groups` chain-connects overlapping or ≤ 20-session-apart episodes. |
| R8 chronology | purpose allowlist (`unknown_purpose` otherwise); `match_controls`, `admit_cases`, `library_counts` apply the guard; intervals unchanged (development 2023-09-04…2025-03-31, validation 2025-04-01…2025-12-31, final holdout 2026-01-01…2026-09-04). |

Thresholds, windows, volume condition, liquidity and regime thresholds are unchanged from 0.1.0-draft (cited hypotheses; not tuned; no M2 price read). The M2 corporate-action statement is corrected (nine known cash events for SH600011/BJ920000 as a partial evidenced set, listing dates in frozen metadata) in `LABEL_POLICY.md §2` and `POLICY["corporate_actions"]["m2_partial_facts"]`.

## 2. Files

| Path | SHA-256 | Note |
| --- | --- | --- |
| `backend/app/research/m3_labels.py` | `fe6046476f492aca4487492e47477166f47d1cfe052167adf021c0bf238d17e7` | **supersedes** first version `6a0590cf…` (2,050 lines) |
| `backend/tests/test_m3_labels.py` | `6fd2aa983f6ab3d15d1f9b679af9dd35a149d22f6f7c52bb0db373a0dace0a7b` | **supersedes** first version `efa2e21c…` (1,512 lines, 71 tests) |
| `claude_01_r2/LABEL_POLICY.md` | `85da92b2f99b5497bb216937143462ac4980f476beea5e10a517ca8e1bd86b5e` | revised written policy |
| `claude_01_r2/LABEL_POLICY.json` | pinned in manifest | `policy_document()` export |
| `claude_01_r2/REGRESSION_MAP.md` | `cd375a49fd5c52afc17604b6b0c25d87ee43fbfc9a86111b8e8a484bfb79b72e` | Codex method → reproduction map |
| `claude_01_r2/test_output.txt` | `68fd1985bbe94df9b8954e3f14541645bef6c7bfbf3b9abccdc2e3e701d251b4` | final verbose run |
| `claude_01_r2/transcripts/*.txt` (4) | pinned in manifest | correction-work transcripts incl. the first failing run and the literal Codex file against the revised module |
| `claude_01_r2/synthetic_examples.json`, `build_artifacts.py`, `DELIVERY.md`, `artifact_manifest.json` | pinned in manifest | |

Policy identity: `m3.labels` / `m3_label_policy` / **`0.2.0-draft`**, policy_hash **`e2620649cf20e2e1d80c2ddd711e6420ec2b8ea3a3d5f900c1226b1d150d37e8`**; producer sha256 = the module hash above. `claude_01/` is byte-identical (its manifest still `428bb425…`; its builder was not rerun); Codex's `review_01_input/` originals still hash `6a0590cf…` / `efa2e21c…` (checked by the manifest's `preserved_originals`). No Codex file, coordination/PLAN/baseline, M2 path, other source, `__init__`, service, configuration, data or Git index was touched.

## 3. Commands actually run (absolute paths) and results

```powershell
# hashes of review/task and of the baseline before editing
sha256sum 'D:\codex-A股交易\claude methods\M3_01_CODEX_REVIEW_20260910.md' 'D:\codex-A股交易\claude methods\M3_01_R2_CLAUDE_TASK_20260910.md'
#   -> 19a82529…111f0 / 48bdad1e…add09 (match); module 6a0590cf…, tests efa2e21c…, claude_01 manifest 428bb425… (match)

# syntax check without py_compile (compile()/ast only), import, integrity
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 -c "import ast; src=open(r'D:\codex-A股交易\backend\app\research\m3_labels.py',encoding='utf-8').read(); compile(src,'m3_labels.py','exec'); ast.parse(src)"
#   -> exit 0

# revised suite (stdlib unittest by file path; no app package, no conftest, no SQLite, no network, no subprocess)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\backend\tests\test_m3_labels.py' -v
#   run_01_first_attempt: exit 1, 71 tests, failures=2 errors=1 (retained)
#   run_02_after_fixes:   exit 0, 71 passed, 4.277 s
#   run_03_after_session_view_fix: exit 0, 71 passed, 4.334 s
#   final test_output.txt: exit 0, "Ran 71 tests in 4.341s", OK (71 passed, 0 failed, 0 errors, 0 skipped)

# Codex's unchanged independent file against the revised module (read-only; their file not edited, no Codex output dir created)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\codex\test_independent_contract.py' -v
#   -> exit 1: 5 ok, 13 ERROR (10 calendar_required, 3 malformed_summary), 0 FAIL — API adaptation only; see REGRESSION_MAP.md §1

# lint with the project's rule selection (venv ruff 0.15.20 vs pyproject ==0.16.6, hence --isolated with the same rules)
& 'D:\codex-A股交易\backend\.venv\Scripts\ruff.exe' check --isolated --no-cache --select E4,E7,E9,F --line-length 100 --target-version py311 'D:\codex-A股交易\backend\app\research\m3_labels.py' 'D:\codex-A股交易\backend\tests\test_m3_labels.py'
#   -> All checks passed! (exit 0)

# artefacts (deterministic; pins everything in claude_01_r2 plus the two backend files, sources read and preserved originals)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\claude_01_r2\build_artifacts.py'
#   -> exit 0; prints policy_hash, producer_sha256, synthetic episode path, match (5, False), counts, preserved True, manifest sha256

# read-only git checks
git -C 'D:\codex-A股交易' status --short ; git -C 'D:\codex-A股交易' diff --check ; git -C 'D:\codex-A股交易' rev-parse --short HEAD
#   -> only the two owned backend paths (untracked, superseding their first versions) and claude_01_r2/ are new; diff --check exit 0 (pre-existing CRLF warnings only); HEAD 73f266d; index empty
```

No `__pycache__` entry exists for the two owned files or for Codex's test file after the runs (all commands used `-B`; `py_compile` was not used).

## 4. Sources read (read-only)

Pinned with hashes in `artifact_manifest.json` → `sources_read`: the Codex review and R2 task, the original M3-01 task, `M2_FINAL_ACCEPTANCE_20260910.md`, `AGENTS.md`, `CODEX_CLAUDE_COLLABORATION.md`, Codex's `test_independent_contract.py`, `review_01_independent_tests/execution.json` + `stderr.txt`, `review_01_input/receipt.json`, `run_offline_review.py`, `STATIC_RISKS.md`, the `claude_01` manifest and policy, the frozen `r06_basis_unit_controls.json` (nine known cash events; JSON metadata only) and `pilot_symbols.csv`. No SQLite file opened, no raw price body or candidate table read, no network, no service import, no collector/staging run, no new agents or scheduler changes, no Git mutation, no email.

Safety: review-only, simulation-only, live trading disabled; synthetic fixtures only; real case count and qualified positive count are **0**.

## 5. Limitations (still true after R2)

1. Policy remains a draft: no real cases, reviews or counts; Codex must review the revised contract and freeze the policy hash before any reader task.
2. Thirteen material choices are listed in `LABEL_POLICY.md §9`; nothing was tuned against M2 prices.
3. For the M2 corpus the contract yields retrospective-only labels, `review_required` position events for the 50 symbols with unknown corporate-action status, conservative limit handling (ST unknown), and requires the pinned AkShare calendar, the frozen universe and the nine known events as `partial_known` facts with capture-time availability.
4. The literal Codex test file cannot run against the revised API without its fixtures carrying a calendar and full summaries; its 16 findings are reproduced one-for-one in the revised suite (`REGRESSION_MAP.md §2`).

## 6. Rollback

Delete the two backend files (or restore the pinned first versions from `codex/review_01_input/files/`) and `claude methods/_m3_20260910/claude_01_r2/`. Nothing else changed.

## 7. Next step (Codex-owned; not started by Claude)

Independent review of the revised contract and of `REGRESSION_MAP.md`; if accepted, freeze policy hash `e2620649…` and dispatch the separate development-only, read-only reader task over the two M2 candidate stores (pinned calendar, frozen universe, partial known events, retrospective cutoffs). Claude does not dispatch or begin it and does not claim M3 completion.
