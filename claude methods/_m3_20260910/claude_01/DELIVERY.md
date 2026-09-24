# M3-01-LABEL-SPEC-20260910 — Claude delivery

Status: **ready_for_review** (proposed; not Codex-validated, not user-accepted). Owner: Claude, existing ZK-trading / Fable 5.1 project advice (fork). Reviewer / coordinator: Codex. Date: 2026-09-10.

Task file verified: `claude methods/M3_01_LABEL_SPEC_CLAUDE_TASK_20260910.md` SHA-256 `9d05c9579c58f8ce02f19448ffcf4f29781eeab4b652441145b36d28d8d2ef7c` (matches the dispatched hash). `M2_FINAL_ACCEPTANCE_20260910.md` (`ee245b61…`) read in full before starting; its seven record corrections are carried into the policy (AI readings ≠ human review → reviewer kinds `agent`/`human` are distinct; the BJ interpretation is a pinned scope exception, not a rule; SSE/BSE scope difference is not relied on; `source_name` NULL → ST status unknown → conservative limit handling; strict_pit=false → retrospective mode only).

## 1. Files written (exclusively; all absent before creation, no concurrent writer observed)

| Path | SHA-256 | Lines / bytes |
| --- | --- | --- |
| `backend/app/research/m3_labels.py` | `6a0590cf2dd9b7acbc9421c818e558e24d6c2877175c8a903d47dab375a99065` | 1,372 lines |
| `backend/tests/test_m3_labels.py` | `efa2e21cb70b70fbd0c39e3e4908a7a24f9837bb45889858979f6a99f09f0ab2` | 895 lines |
| `claude methods/_m3_20260910/claude_01/LABEL_POLICY.md` | `deee83578c30bb18b146dc04c5167412c4b80718972e0a1fdca54e2b9c9de2bd` | written policy |
| `claude methods/_m3_20260910/claude_01/LABEL_POLICY.json` | `c484d46177114e6c149d83fdce9e8fc612737a8f463f9a04921ebfb387bf8ffc` | machine-readable `POLICY` + hash |
| `claude methods/_m3_20260910/claude_01/test_output.txt` | `b992cc943643c683fb96a51637fbe5bf813d79ed06b19acd39e2a7448b9dec15` | verbose unittest transcript |
| `claude methods/_m3_20260910/claude_01/synthetic_examples.json` | `fc1fdbf44e0941239c4e63469b0285c54cd9cc7b39d808041cbdbf0a2f735ce2` | example records (all `SYN######`, `synthetic=true`) |
| `claude methods/_m3_20260910/claude_01/build_artifacts.py` | `79cadc3cf86be68728c3bbdc39ed22e7ae2d511fd57c984b5b2ad2041cb33a91` | deterministic artefact builder |
| `claude methods/_m3_20260910/claude_01/DELIVERY.md` | this file (pinned in the manifest) | |
| `claude methods/_m3_20260910/claude_01/artifact_manifest.json` | pins everything above and every source read | reported in the handoff message |

Policy identity: namespace `m3.labels`, policy id `m3_label_policy`, version `0.1.0-draft`, **policy_hash `ea0f7630acc0c5175bab3b849eac606806a82b8ada53cd94dd714a219f1164e2`**, producer (module bytes) `6a0590cf…` (same as the module hash above).

No other file was created or modified. No `__init__.py` change (`backend/app/research/__init__.py` unchanged, `6555a240…`). Two `.pyc` byproducts created by a one-off `py_compile` check were deleted; no `__pycache__` entry for either new file remains. Nothing staged; HEAD `73f266d` unchanged; branch `codex/control-plane-refactor`. Pre-existing dirty files (28 modified + untracked per `git status`) were left untouched.

## 2. Commands actually run (absolute paths) and results

```powershell
# 1. task hash verification
sha256sum "D:\codex-A股交易\claude methods\M3_01_LABEL_SPEC_CLAUDE_TASK_20260910.md"
#   -> 9d05c957…2ef7c  (match)

# 2. test suite: stdlib unittest, module loaded by file path, no app package, no conftest, no SQLite, no network
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\backend\tests\test_m3_labels.py' -v
#   -> exit 0, "Ran 41 tests in 3.203s", OK (41 passed, 0 failed, 0 errors, 0 skipped); transcript in test_output.txt

# 3. lint with the project's rule selection (the venv ruff is 0.15.20, pyproject requires ==0.16.6, so --isolated with the same rules)
& 'D:\codex-A股交易\backend\.venv\Scripts\ruff.exe' check --isolated --no-cache --select E4,E7,E9,F --line-length 100 --target-version py311 'D:\codex-A股交易\backend\app\research\m3_labels.py' 'D:\codex-A股交易\backend\tests\test_m3_labels.py'
#   -> "All checks passed!" (exit 0)

# 4. artefacts (LABEL_POLICY.json, synthetic_examples.json, artifact_manifest.json); deterministic, run last
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\claude_01\build_artifacts.py'
#   -> exit 0; prints policy_hash, producer_sha256, the synthetic episode path, match (5, False), manifest sha256

# 5. read-only git checks
git -C 'D:\codex-A股交易' status --short ; git -C 'D:\codex-A股交易' diff --check ; git -C 'D:\codex-A股交易' rev-parse --short HEAD
#   -> only the two new backend files and claude_01/ are new; diff --check exit 0 (CRLF warnings are pre-existing); HEAD 73f266d; index empty
```

No full backend suite was run (unrelated to this task). The pytest path with `backend/tests/conftest.py` was deliberately not used: that conftest creates a temporary SQLite bootstrap database on import.

## 3. What the 41 tests cover (all synthetic, `SYN######`, excluded from counts by the module)

- Identity/hash: namespace distinct from legacy, `POLICY_HASH == sha256(canonical(POLICY))`, module imports are stdlib-only and the source contains no clock/SQLite/network calls.
- Input rejection: wrong security identity, duplicate keys, unsorted input, empty input; NaN/inf/bool/None numerics; high < low, zero/negative prices, close outside range, negative volume, zero volume with amount, vwap outside [0.98·low, 1.02·high]; availability before close, naive datetime, missing/invalid availability; qfq adjustment, `hand` volume unit, unknown kind, missing source_ref, `ERROR` date, suspension with prices; cutoff before close, strict cutoff > 72 h after close, unknown mode, naive cutoff.
- Causality: strict mode excludes late-available rows (and consumes them once declared in time); an M2-style single-day capture yields **0 rows** under a strict 2024 cutoff and is labelled only in retrospective mode with `strict_pit_eligible=false`, `training_eligible=false`; suffix mutation/truncation invariance of the stable record, `record_hash` and `episode_id`; past accumulation unchanged by a future markup; state isolation and repeatability across interleaved symbols and series runs.
- Phase sequence: constructed positive → markup → failed_markup path with ordering assertions; `failed_markup` requires a prior observable markup (a plain decline is not failed_markup); accumulation right after a failed markup is `non_candidate`; episode contract (pending review, never counts, chronological, single symbol, single policy hash).
- Negative and ambiguity: distribution fixture → `distribution`/`non_candidate`; transition window → `indeterminate`/`no_rule_matched` with indeterminate selection/entry and `no_trade`.
- Data quality: insufficient warmup; suspension on the last observation; many suspensions; long gap; stale last bar; known corporate action in window → indeterminate; unknown status → `adjustment_uncertainty` carried, label still produced, `turnover_unavailable`/`float_shares_unavailable` recorded; BJ920006/2023-12-04 pinned exception accepted while the same anomaly on another symbol or date is rejected, its volume excluded from ratios, decision bar → indeterminate.
- Trade state: signal eligible on a confirmed candidate day with `tradability="unverified"` and `legal_next_session="unknown"`; unknown ST → lowest threshold 4.8 → `limit_like_possible` blocks entry; declared not-ST → 9.8; BSE 29.0, ChiNext/STAR 19.5; limit-down; unknown move; volume ratio below 1.5 blocks; position events hold/exit/stop/invalidation/max-holding and every binding rejection; prior-state binding (consistent, inconsistent phase, wrong policy, not earlier, later as_of).
- Context: liquidity bands; bull/bear/range from a benchmark; unknown when benchmark absent, short, missing on the decision date, or universe coverage < 0.90; benchmark without symbol rejected.
- Case library: deterministic matching independent of pool order, 3–5 controls, different symbol, same band/regime, period tolerance rejections enumerated, outcome-field leakage rejected on either side, non-candidate positive rejected; unmatched flag and reuse counts; stable episode ids sensitive to symbol/date/fingerprint/policy; no fabricated reviews, single review not independent, same agent twice still not independent, disagreement preserved as `disputed`, agreement → `independently_reviewed`, synthetic never counts, invalid reviewer kind/naive time/empty id rejected; synthetic episodes excluded from effective counts; later-known outcome annotation separate and never inside labels.
- Protection: split roles for the proposed intervals; `guard_final_holdout` raises for rule/threshold/target/parameter purposes; seed context (SZ002115, SZ002081) legacy-unverified with zero contribution; frozen-universe checks; required provenance keys and JSON serialisability without NaN.

## 4. Sources read (read-only) with SHA-256

| Source | SHA-256 |
| --- | --- |
| `claude methods/M3_01_LABEL_SPEC_CLAUDE_TASK_20260910.md` | `9d05c9579c58f8ce02f19448ffcf4f29781eeab4b652441145b36d28d8d2ef7c` |
| `claude methods/M2_FINAL_ACCEPTANCE_20260910.md` | `ee245b6161ebc7cfc49d38d4ad1d8b0ab14b3550323f458919a8364781096018` |
| `claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md` (mission, §2, §4, §6, M3 `:187-208`) | `f8b699e531ab4e98e7bccd17bc0c2850355ed0ea75e5038cfecaa216a6266164` |
| `AGENTS.md` | `cb6b114f1a88521873c632d12fea9e67579ab30b1b60864e9e7d5d5a522a85c3` |
| `CODEX_CLAUDE_COLLABORATION.md` | `f17d42e4d56713ade00eb31010494f76fdfecb8c68be2eb9f2ea9f86c6191992` |
| `CLAUDE.md` | `7eb150e519ccd826b9d5f041fabc4ca0275280eec50da03ae94dc19387d17039` |
| `claude methods/_m3_20260910/PLAN.md` | `cff466abc502f65176cca53cb77ed5337174b34fd936cceb9136cd801a34b519` |
| `claude methods/_m3_20260910/coordination_state.json` | `1a4f350173304ba8d4ff40f2f2cfa3f106d1f4c6dfc4621c120574891b32ecee` |
| `claude methods/_m3_20260910/baseline/baseline.json` | `e7f2fd8692b7de1ff16560ab36e161ed8f9f4c7e6906ec23e1cf9f8d79a8c231` |
| `claude methods/_m3_20260910/codex/bootstrap.py` (listed only; not executed) | `ffaea98db7e3b69f4569d9bbe3a61008ed813cbc5ddc3aa7d1bf3c1e29643117` |
| `backend/app/learning/phase_replay.py` | `67e0061859fe3b5894d7077f8edc5ff4a83b88b08051fa2fcd645ab8cdab94ce` |
| `backend/app/learning/structure_scoring.py` | `27316df97bad1471bc099695564660e6300ab4b1232a7efd3a8df7bf26327f51` |
| `backend/app/learning/phase_matcher.py` | `9c0f28ea4e8addf09aa952115bf404b3dbf551415284269446f21708af9138eb` |
| `backend/app/agent_control/outcome_labeling.py` | `53fd7cc265249709a4add64cba809fbf7c670d4bba343f3499295c5ebc637f58` |
| `backend/app/strategies/dengzhan.py` | `76e144d8c0d5e7bcc3a8db1908669cf81e604eb783020245340c6976b98d1694` |
| `backend/app/research/offhour.py` (structure survey; `:2735-2736`, `:5370-5378`, `:6472-6555`, `:6903-6906`) | `fadd607da1d449ab5fa71d7ee8337092afa3c165831bc0e1a95c7d1e95fc3534` |
| `backend/app/data/price_limits.py` | `3d7bca77a4b5c848d6ef4c03cc6611b3921647b6732bc79fd24fbbc46eb30eae` |
| `backend/app/research/__init__.py` | `6555a240eea8fe44ab9fe4de692878867a4f36b12eadac7b7db1e98e4daa37d5` |
| `backend/tests/conftest.py` (first 30 lines) | `45351d5b050c423d9e0e1150a964c148ffa0386460f760f267269347b67a702a` |
| `backend/pyproject.toml` (ruff section) | `714188f122ab8a45332ff825e3c746cf27936592bde6de233904be02aab083b9` |
| `claude methods/_m1_closure/pilot_symbols.csv` (header + benchmark rows) | `97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe` |
| `…/run_ths_v2_20260910_041710_97ef9c09/contract_v2.json` (scalar fields only) | `b3aeb7e86ace9fbc66b23766592cacfe1837dc939909c52dddc86df87eb71031` |
| `claude methods/_m2_ths_v2_claude_review_20260910/r02_db_schema.json` (frozen DDL, from my M2 review) | `4298b9d866c34dc0fc16f1204c8e2fb72597a2f824f4bbeb5c27fbd002c4ee1c` |
| `claude methods/_m2_codex_implementation_20260910/contract_v2.py` (`:252` unit declaration) | `14b87fdad0f8e25dc13150d5d43a0971c9477d025d3d4ebd92baf430db84b26b` |

Data impact: **none**. No SQLite file was opened (the M2 schema came from the frozen JSON of my earlier review), no raw price body or candidate price table was read, no market/disclosure request was made, no collector/staging runner/preservation finalizer was run, no legacy service was imported or instantiated. Thresholds were taken from the cited legacy hypotheses only.

Safety: review-only, simulation-only, live trading disabled (`live_trading_enabled=false` in every output and in the policy). No account/login/credential/fund access, no training, no Git stage/commit/push/PR, no email, no new agents/automations/scheduler changes (ultracode was on in the session; the task's "no new agents" boundary was honoured — everything here was done solo).

## 5. Current limitations (honest scope of M3-01)

1. This is a policy draft with a passing synthetic suite, not a case library: zero real cases, zero reviewed positives, `training_eligible=false` everywhere.
2. Nine material choices are listed in `LABEL_POLICY.md §9` and need Codex review before adoption (250-bar position window, failed-markup threshold, selection veto, band/regime thresholds, lowest-threshold limit rule, 72 h strict window, split intervals, corporate-action gate, gap gates).
3. The M2 corpus can only be labelled in `retrospective` mode; strict-PIT provenance is impossible for it and the policy says so in every output.
4. `SecurityContext` inputs (ST status, corporate actions, float, turnover, listing date) are unavailable in the M2 store; the reader task will have to declare them `unknown`, which blocks some entry signals by design.
5. Calendar gaps and dependence grouping use calendar-day approximations unless a session index is injected; the later reader should inject the pinned AkShare calendar.
6. Synthetic sequences show that the inherited volume-ratio markup rule is short-lived and that indeterminate transition windows are common; that is a property of the hypothesis, not tuned away.
7. No performance, precision, return or effectiveness claim is made or possible.

## 6. Rollback

Delete the two new backend files and `claude methods/_m3_20260910/claude_01/`. Nothing else was touched; no data, index, branch or production state changed.

## 7. Concrete next step (for Codex; not started by Claude)

Codex reviews `LABEL_POLICY.md` §4/§8/§9 and the module semantics (cutoff/availability, split, matching), records findings as `优先级 → 文件:行号 → 触发条件 → 实际影响 → 修复/验收建议`. Only after a frozen, reviewed policy hash exists should a separate task create the isolated, hash-bound read-only reader over the two M2 candidate stores (`mode=ro`, injected calendar, retrospective cutoffs, frozen universe) that emits pending-review episodes and matched controls into a new M3 output directory. Claude does not dispatch or begin that task.
