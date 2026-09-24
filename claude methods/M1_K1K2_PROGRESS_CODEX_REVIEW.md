# M1 K1/K2 progress review — 2026-09-06

Verdict: the original K1 counterexample is fixed and the tested K2 required-consumer behavior is validated. One bounded K1 empty-eligible-domain defect remains before accepting the general executable handoff. Do not restart M0, the census, or a broad audit. M2 remains unauthorized.

## Verified progress

- Supplied end-to-end suite: 55 checks, 0 unexpected, exit 0.
- Primitive suite: 46 cases, 0 unexpected, exit 0.
- Temporal proofs: 13/13 true (called directly without the production-query wrapper).
- Independent expected-key construction from the actual 50-stock/two-benchmark manifest: 36,193 records per view; actual subprocess CLI exits 0.
- Original BJ920002/2024-05-29 addition in both views: exits 1, fails M1/M3, names the security/session.
- Required 250-session warm-up with both consumers: clean control passes; missing history or divergent history high causes overall failure.
- Explicit pricing-only warm-up: these history faults are outside the declared warm-up consumer scope and the result explicitly marks history NOT CONSUMED.
- Earlier history date/price/duplicate/provenance and transformation regressions are present in the current supplied suite.

## Remaining K1 issue: known, empty eligible sets are skipped

Locations: `_m1_closure/staging_gate.py:182-193` and `:225-239`.

`expected_key_map()` moves known securities with no eligible sessions into `outside` and omits them from `expected`. `membership_gate()` then observes and compares keys only for securities in `expected`, while `absent` still requires every declared security to appear.

Independent synthetic probes keep the actual selected security identifiers and both benchmarks, changing listing metadata only in disposable test manifests. The approved manifest is never changed. For SH688001:

| Synthetic contract | Records in the research interval | Actual CLI result |
|---|---|---|
| Listed 2026-09-07, after the research window | Correctly empty in both views | Exit 1: absent symbol |
| Same contract | One ineligible 2025-06-10 record in each view | **Exit 0** |
| Listed 2000-01-01, delisted 2023-09-01, before the research window | Correctly empty in both views | Exit 1: absent symbol |
| Same contract | One ineligible 2025-06-10 record in each view | **Exit 0** |

These are synthetic boundary tests, not assertions about SH688001's real listing history. Agreement between views is still insufficient when the expected key set is empty. This is the remaining part of K1, not a new broad audit.

### Smallest closure

1. Keep known empty eligible sets in the key comparison. Any observed key in that interval must fail, naming the security/session.
2. Do not classify zero observed rows as missing data when eligibility is known to be empty. Report outside-window/not-applicable distinctly. If the batch contract forbids an outside-window member, reject the manifest explicitly; inserting rows must never turn rejection into success.
3. Preserve UNKNOWN for genuinely unknown eligibility; do not conflate unknown and known-empty sets.
4. Apply the same rule in research and consumed warm-up intervals. An IPO after warm-up can have complete eligible coverage (zero expected observations) but still fail required feature-depth readiness. Those must remain distinct outcomes.
5. Add focused CLI regressions for both fully-outside cases, empty versus injected, in both views. Preserve the actual 50+2 clean control and all current K2/G3 regressions.

K2 note: V3b reports observation depth and can PASS while W2 fails identity. Overall validation correctly fails. Do not consume the V3b count alone as final feature readiness; the required gates must pass together. No additional runtime implementation is requested here.

## Reproduction

From the repository root:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m1_closure\test_staging_gate_e2e.py'
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m1_closure\test_acceptance_gates.py'
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m1_codex_review\k1k2_progress_review.py'
```

The independent diagnostic exits 0 when its execution and already-fixed assertions succeed; the per-case false passes above remain findings, not acceptance. The companion notebook is `_m1_codex_review/M1_k1k2_progress_review.ipynb`. It runs the inspectable script and prints the individual observations. An initial reviewer-only fixture writer omitted the synthetic delist column; that harness error was corrected before the successful full diagnostic run and is not a product finding.

## Safety and next action

Production main/WAL sizes and nanosecond mtimes matched the previous baseline and remained unchanged. Reviewed code, pilot manifest, fixture archives, calendar and frozen fixture baseline retained their hashes during the probes. Temporary synthetic fixtures were cleaned up. HEAD remains `73f266d`; staging is empty. The reviewer changed no implementation or existing progress documents.

Claude should close only the remaining empty-domain behavior in local closure artifacts and English handoff/progress documents under `claude methods/`, then stop at `ready_for_review`. Preserve production databases, datasets, strategies, existing methodology/knowledge materials, runtime code and unrelated edits. No network/plugin calls, downloads, migrations, services, staging, commits, pushes or broad multi-agent audit. Pilot downloads still require separate authorization after review.
