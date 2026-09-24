# M2a technical acceptance — offline pilot runner

Reviewer: Codex. Date: 2026-09-07, approximately 00:04 Asia/Taipei.

**Decision: technically VALIDATED for the current offline pilot-runner scope.** The remaining R2.1/R2.2 counterexamples are closed, and the previously reviewed R1/R3/R4 controls remain green. No outstanding blocker was found in this bounded closure review. User acceptance is a separate project status; this report does not authorize any live execution.

M1's existing technical validation stands. Do not reopen M0/M1 or repeat the completed M2a repair cycle without new evidence.

## Evidence independently executed

1. Delivered `test_m2a.py`: **79 cases, 0 unexpected, exit 0**.
2. Independent `review_m2a_receipts.py`: **12 scenario groups passed**, followed by unchanged-production/input and cleanup assertions; exit 0. Unlike earlier defect-observation scripts, this script requires safe behavior to pass.
3. The independent full-chain fixtures use the actual approved 50-stock/two-benchmark manifest and pinned calendar, with synthetic response bodies only. They exercise the actual collector, decoder, both disposable staging databases, runner-owned `validate_candidate`, unchanged M1 validation, and receipt-based finalization.

Reproduce from the repository root:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m2_pilot\test_m2a.py'
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m2_codex_review\review_m2a_receipts.py'
```

The new reviewer script reuses the prior reviewer's fixed-control helper definitions from `review_m2a_binding.py`, but does not run that historical script's now-obsolete defect expectations. Historical reviews and probes were preserved unchanged.

## Closure results

| Requirement | Independent observed result |
|---|---|
| R1: one response-body path | The removed body override is refused before any request or staging creation; actual HTML yields no successful jobs. |
| R2: mandatory contract checks | No enforcement bypass; truncated hashes, missing calendar pins and contradictory verdicts are refused. |
| R2.1: old report/new candidate mix-up | A's genuine report can still be interpreted by the low-level parser with B's fingerprint, but the resulting ordinary Verdict objects are refused by finalization. B's official validation actually runs against B, detects its missing research row and rejects publication. A's genuine receipts also cannot publish B. |
| R2.2: research cannot replace warm-up | Candidate C's research passes while actual warm-up integrity fails W1_pricing. Two research receipts, a single research receipt, and the honest failed warm-up pair are all refused. |
| Binding during validation | The actual M1 research gate first returns exit 0 on good data; the probe changes a temporary candidate before the wrapper's second fingerprint. The wrapper refuses to certify it, isolating the binding check from gate-content failures. |
| Binding after validation | Previously valid receipts cannot publish the subsequently modified candidate. |
| R3: sticky abort | Two attempted calls after an inner abort produce one underlying attempt and retain the original stop reason. |
| R4: protected publication paths | An existing hardlinked pointer temporary aliasing a protected disposable sentinel is refused; an unowned temporary is not reused/deleted; an injected pointer replace failure preserves the previous pointer. |
| Healthy full chain | 52 jobs succeed; each view contains **45,935 synthetic rows**; research exits 0; warm-up exits 1 with exactly the approved 14-security depth shortfall, whose collection integrity is accepted. Finalization succeeds and records both required validation modes and the candidate fingerprint. |

The official validation path now owns the actual M1 invocation. Finalization requires mode-specific `ValidationReceipt` objects for the same run and candidate, with matching manifest/calendar pins. The earlier two blocking counterexamples no longer reach publication through that path.

## Precisely what has—and has not—been validated

Validated: the current **offline, trusted single-process engineering workflow** and its reviewed rejection/publication behavior on synthetic fixtures.

Not validated or authorized:

- Real Sina payload decoding or live transport. Both remain deliberately unsupported/disabled in this milestone.
- Live source semantics, amount meaning, unit correctness, adjustment evidence, endpoint completeness, vendor limits or independent corroboration.
- A completed three-year market corpus, full-market coverage, strict historical point-in-time reconstruction, feature readiness, trained models, strategy effectiveness or profitability.
- Production migration/promotion, services, commits or pushes.

`ValidationReceipt` is an ordinary Python dataclass, not a cryptographic capability or a security boundary against hostile code manufacturing objects inside the process. This acceptance covers accidental stale-report/wrong-mode mix-ups through the reviewed official API, not arbitrary in-process code tampering or hostile concurrent filesystem modification. Future execution must retain trusted validation ownership and immutable candidate/input handling.

Warm-up collection integrity is not feature readiness: the approved 14-stock IPO depth exception remains explicit. A2 and the 746 legacy evaluations remain a separate prerequisite before official historical evaluation consumption, not work performed in M2a.

## Next stage: prepare bounded real-source verification

The next useful step is to prepare a small real-source capability check, **not** to jump to the 52-symbol collection or model training. The current live decoder gap must be made explicit in that plan.

Prepare one English request covering:

1. An exact three-symbol selection from the approved manifest: one ordinary stock, one BJ stock and one benchmark, with rationale.
2. The minimal raw-response capture/decoder workflow. State which adapter/decoder code must exist before execution and what remains unknown; synthetic envelopes do not establish live payload support.
3. Exact endpoints and expected request count (currently proposed 5 without retries, ceiling 15), finite timeouts, pacing, concurrency, and stop conditions. Reconfirm counts from the adapter path; do not treat vendor quotas as proven.
4. Explicit temporary-only output paths, protected production inputs, provenance/body hashes, cleanup/recovery and no production promotion.
5. Pass/fail checks for identity, source schema, raw-basis evidence, OHLCV/amount semantics, units and date coverage, including separate benchmark handling. Do not label an outstanding-share series as traded amount without evidence.
6. A separate authorization boundary for real calls, and another later boundary for the 52-symbol pilot. No calls/downloads are authorized merely by preparing this request.

The currently active Section 14 of `THREE_YEAR_RESEARCH_EXECUTION_GOAL.md` still reports **48** tests and presents live smoke versus the 52-symbol pilot as the immediate choice. Synchronize this stale current-handoff section with the latest progress entries and this acceptance result. This is a documentation follow-up, not a reason to reopen the validated code. Preserve historical sections as clearly superseded records.

## Safety and workspace evidence

The independent script blocked socket connections. All database writes and pointer publications used temporary synthetic fixtures; all were cleaned up. Reviewed M1/M2 Python files, the approved manifest and calendar retained their hashes. Production main/WAL metadata remained at the established baseline:

| Repository-root file | Bytes | mtime_ns |
|---|---:|---:|
| trading_local.sqlite3 | 1,346,048,000 | 1788517646307317700 |
| market_history.sqlite3 | 1,234,956,288 | 1788493486739967200 |
| market_history.sqlite3-wal | 0 | 1788493486748601200 |

These production checks are metadata checks, not new full-content hashes. HEAD remains `73f266d`; index empty; no real `staging/pilot_20260906` exists. `git diff --check` exited 0 with line-ending warnings, not whitespace errors. No broad backend/M1 suite was rerun by Codex in this closure; the actual unchanged M1 gate was exercised repeatedly through the synthetic integration checks.

This review added only its local English acceptance report and independent script. Claude's implementation, goal ledger and existing evidence were not edited. Reviewer artifacts, datasets, strategy sets, methodology and all Codex/Claude-related files remain outside any Git submission.

Reviewed SHA-256:

```text
pilot_runner.py   943a8c3f5f34a0739115771ac952dd3576ae1ccf4df2b1bf7089de00c90b97cb
test_m2a.py       5ec054560fbc92fcd9a30cccbf37dffbf20327389e53922eb8ce3efd52bc4ac1
pilot_symbols.csv 97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe
```
