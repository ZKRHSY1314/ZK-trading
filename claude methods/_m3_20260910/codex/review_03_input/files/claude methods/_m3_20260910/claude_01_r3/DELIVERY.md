# M3-01-R3-CONSUMER-INTEGRITY-20260910 — Claude delivery

Status: **ready_for_review** (proposed; not Codex-validated, not user-accepted; M3 not complete). Owner: Claude, existing ZK-trading / Fable 5.1 project advice (fork). Reviewer / coordinator: Codex. Date: 2026-09-10.

Inputs verified before editing: review `M3_01_R2_CODEX_REVIEW_20260910.md` `d417099d…86a1`; task `M3_01_R3_CLAUDE_TASK_20260910.md` `1d92d9cb…22ab`; the two working paths matched Codex's `review_02_input/files` snapshot (`fe604647…` / `6fd2aa98…`) and the R2 manifest `34b28360…` before the first write; no competing writer appeared. Two in-task supplements from Codex were incorporated into this same delivery: `R3_BENCHMARK_INTEGRATION_SUPPLEMENT.md` (`a66f1db5…`) and `R3_IN_PROGRESS_FEEDBACK.md` (`e0092b69…`).

## 1. What changed (policy `0.3.0-draft`, schema `m3.labels.output.v3`)

| Finding | Correction (`backend/app/research/m3_labels.py`) |
| --- | --- |
| **A** ledger validation | one authoritative `validate_ledger(record)` (binding to the exact core, ledger hash, per-entry fields/content hash/binding/synthetic flag, supersession chain: own current entry only, reason, strictly later instant, no fork/stale branch/unknown target, duplicates/conflicts, cached status vs reconstruction) reused by `review_status`, `attach_review` (before and after the tentative append), `RecordRegistry`, `admit_cases`, `library_counts` |
| **B** summaries / records | `validate_summary_format` (types/enums/finite/canonical hex/derived split); `RecordRegistry` resolves summaries to verified cores and compares field by field; a bare summary is rejected; `verify_record` checks derived fields and — feedback 2 — recomputes `decision_fingerprint` from `identity.decision_inputs` and cross-checks the declared duplicates |
| **C** counting revalidation | `revalidate_match(match, registry, purpose)`: fixed policy `k_min/k_max`, every positive/control reference resolved (absent → fail closed), match recomputed and compared; identical records collapse, conflicting cores/ledgers fail; unique records reported apart from raw input length; control evidence and review status preserved per qualified episode |
| **D** episode qualification | `episode_prefix_proof` / `qualified_episodes` / `prefix_proof_for`; the unit of admission is an established three-session prefix with a representative at `established_at`; counts report daily records, episodes, qualified reviewed positive episodes, unique controls / uses and effective groups separately; `target_met` is defined against the original criterion (≥ 50 reviewed positive episodes with 3–5 controls); feedback 1 — `ReviewRecord.case_prefix_hash` binds episode reviews to the recomputed proof (`review_not_bound_to_prefix`, `review_prefix_binding_mismatch`) |
| **E** consumed identity | offered-but-unavailable context/coverage stays in `request_diagnostics`; the core keeps a deterministic unavailable state; benchmark identity over price fields only |
| **F** reference chronology | basis-specific earliest observation (`next_session_open` = next calendar session, ≥ 09:30 open; `session_close` ≥ 15:00 close); `declared` never verified → `review_required` |
| supplement | role-aware benchmark contract: retained M2 units `not_applicable` mandatory, index-level OHLC, aggregates uninterpreted/validated/excluded from identity, price-only regime kernel; stock share/CNY/vwap checks and the BJ scope exception unchanged |

Thresholds, windows, matching rule and split intervals are unchanged; no M2 price was read.

## 2. Files

| Path | SHA-256 | Note |
| --- | --- | --- |
| `backend/app/research/m3_labels.py` | `e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393` | **supersedes** `fe604647…` (R2) and `6a0590cf…` (R1); 2,559 lines |
| `backend/tests/test_m3_labels.py` | `41eba60b21b507250f9a9a4f359fdc330232306c61b535f3d82db18ba9e45180` | **supersedes** `6fd2aa98…` (R2) and `efa2e21c…` (R1); 2,141 lines, 105 tests |
| `claude_01_r3/LABEL_POLICY.md`, `LABEL_POLICY.json`, `REGRESSION_MAP.md`, `synthetic_examples.json`, `build_artifacts.py`, `test_output.txt`, `transcripts/*` (8), `DELIVERY.md`, `artifact_manifest.json` | pinned in the manifest | |

Policy identity: `m3.labels` / `m3_label_policy` / **`0.3.0-draft`**, policy_hash **`d436ba1402f9d0b53e1008c2a2bd50678a457c3e050561a59ded30dbbd21c025`**; producer = the module hash above. Preserved and re-verified by the manifest (`preserved_originals`, all `match=true`): both Codex snapshots of the earlier backend versions, the R1 and R2 manifests, the two supplements, Codex's R2/R3 test files and the feature oracle. `claude_01/` and `claude_01_r2/` were not rebuilt. No Codex file, coordination/PLAN, baseline, M2 path, other source, `__init__`, service, configuration, data or Git index was touched.

## 3. Commands actually run (absolute paths) and results

```powershell
# baseline verification
sha256sum 'D:\codex-A股交易\claude methods\M3_01_R2_CODEX_REVIEW_20260910.md' 'D:\codex-A股交易\claude methods\M3_01_R3_CLAUDE_TASK_20260910.md'   # d417099d… / 1d92d9cb… (match)
sha256sum 'D:\codex-A股交易\backend\app\research\m3_labels.py' 'D:\codex-A股交易\backend\tests\test_m3_labels.py'                       # fe604647… / 6fd2aa98… before edits (= review_02_input/files)

# syntax (compile()/ast only — no py_compile), import, integrity, lint (venv ruff 0.15.20 vs pyproject ==0.16.6 → --isolated with the project's rules)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 -c "import ast; src=open(r'D:\codex-A股交易\backend\app\research\m3_labels.py',encoding='utf-8').read(); compile(src,'m3_labels.py','exec'); ast.parse(src)"
& 'D:\codex-A股交易\backend\.venv\Scripts\ruff.exe' check --isolated --no-cache --select E4,E7,E9,F --line-length 100 --target-version py311 'D:\codex-A股交易\backend\app\research\m3_labels.py' 'D:\codex-A股交易\backend\tests\test_m3_labels.py'
#   -> All checks passed! (exit 0)

# revised suite (stdlib unittest by file path; no app package, no conftest, no SQLite, no network, no subprocess)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\backend\tests\test_m3_labels.py' -v
#   run_01_first_attempt:        exit 1, 103 tests, failures=5 errors=1 (retained)
#   run_02_after_fixes:          exit 0, 103 passed, 5.989 s
#   run_03_after_feedback_fixes: exit 0, 105 passed, 6.174 s
#   final test_output.txt:       exit 0, "Ran 105 tests in 6.233s", OK (105 passed, 0 failed, 0 errors, 0 skipped)

# Codex's unchanged files against the delivered module (read-only; no Codex output directory created)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\codex\test_independent_r3.py' -v      # exit 1: 21 ok / 2 FAIL (unbound positive-control reviews; see REGRESSION_MAP §2)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\codex\test_independent_r2.py' -v      # exit 1: 1 ok / 14 ERROR benchmark_units_must_be_not_applicable (fixture units; REGRESSION_MAP §1)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\codex\test_independent_contract.py' -v  # exit 1: 5 ok / 13 ERROR (R1 API adaptations, unchanged since R2)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\codex\test_feature_oracle.py' -v        # exit 0: 8 ok
#   (before the benchmark supplement the R2 file gave 13 ok / 2 ERROR — transcripts/codex_r2_consumer_tests_literal_against_r3_run01.txt)

# artefacts (deterministic; run last)
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\claude_01_r3\build_artifacts.py'
#   -> exit 0; positive control 1 qualified / 1 group / 3 controls; single day 0; forged match -> match_record_mismatch; synthetic same path 0;
#      ledger disputed -> independently_reviewed after explicit supersession, transplant -> ledger_binding_mismatch; benchmark bull with retained units,
#      identity stable under changed aggregates, share units -> benchmark_units_must_be_not_applicable; preserved True; missing sources 0

# read-only git checks
git -C 'D:\codex-A股交易' status --short ; git -C 'D:\codex-A股交易' diff --check ; git -C 'D:\codex-A股交易' rev-parse --short HEAD
#   -> only the two owned backend paths (untracked, superseding) and claude_01_r3/ are new; diff --check exit 0 (pre-existing CRLF warnings); HEAD 73f266d; index empty
```

No `__pycache__` entry exists for the owned files or Codex's test files after the runs (all commands used `-B`; `py_compile` was not used).

## 4. Validation coverage (task §Validation)

1. Both rejection paths and a genuinely admissible, fully bound episode + controls fixture go through the **same** `library_counts`: `EpisodeAndCountingTests.test_admissible_positive_control_counts_exactly_once` (fixture-only real-format codes, prefix-bound non-synthetic fixture reviews, revalidated 3 controls → exactly 1 qualified episode, 3 unique controls, 1 group, `target_met=false`), `test_counting_rejections_through_the_same_path`, `test_review_must_bind_the_recomputed_episode_prefix`, `test_split_admission_in_counting`. Nothing is saved as a case; no review work is claimed; no production bypass.
2. All 15 Codex R2 methods, all 8 oracle methods, all 18 R1 methods and the 8 new R3 methods are mapped to actual results in `REGRESSION_MAP.md`; the only API adaptations are the mandatory benchmark units and the prefix-bound positive control that Codex's own supplement/feedback asked for.
3. Transcripts retained (`transcripts/`, `test_output.txt`); syntax via `compile()`/AST; policy and code agree (`LABEL_POLICY.md`, `LABEL_POLICY.json` = `policy_document()`).
4. Manifest pins every output, every source read (including the supplement, the feedback, Codex's probes/receipts/test files) and re-verifies the preserved originals.

## 5. Data impact and safety

None. No SQLite file opened, no raw price body or candidate table read, no network, no collector/staging run, no service import, no desktop/client action, no credentials/funds/orders, no training, no Git stage/commit/push/PR, no email, no new agents or scheduler changes. Review-only, simulation-only, live trading disabled. Real cases: 0. Real reviews: 0. Qualified real positives: 0.

## 6. Limitations and material choices

`LABEL_POLICY.md §3` lists choices 14–17 added this round (mandatory `not_applicable` benchmark units; prefix-bound episode reviews; fail-closed absent controls; revalidation from the referenced set). The M2 corpus remains retrospective-only with unknown action coverage for 48 stocks and partial known events for 2; benchmarks are not stocks; `strict_pit=false`; `training_eligible=false`. The literal Codex R2/R3 files need the two fixture adaptations to run against this API; their intended conditions are reproduced without weakening.

## 7. Rollback

Delete the two backend files (or restore the pinned R2 versions from `codex/review_02_input/files/`) and `claude methods/_m3_20260910/claude_01_r3/`. Nothing else changed.

## 8. Next step (Codex-owned; not started by Claude)

Independent acceptance of the R3 contract; if accepted, freeze policy hash `d436ba14…` and dispatch the separate development-only, read-only reader over the two M2 candidate stores (pinned calendar, frozen universe, partial known events, retained benchmark units, retrospective cutoffs). Claude does not dispatch or begin it and does not claim M3 completion.
