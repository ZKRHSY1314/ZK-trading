# Codex review of the M1 closure

Verdict: **do not start M2 downloads yet**. The corrected coverage audit is accepted for the pinned inputs, and the pilot selection is reproducible. The execution gate still has concrete false-pass paths. M1 remains unvalidated as a complete handoff; M0 is not reopened.

This review uses the data-quality review workflow. Production access was read-only; additional defect probes used in-memory SQLite fixtures. No runtime code, dataset, original evidence, frozen baseline, production database or service was changed. Only reviewer artifacts and the review ledger are written.

## What is independently accepted

- R2 coverage: rebuilding in memory reproduced **every CSV cell** and the recorded metadata totals. Calendar hash matches `f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656`. Eligible 3,900,763 = observed 2,888,185 + leading 1,004,942 + interior 4,611 + trailing 3,025. BJ920000 is correctly 728 = 501 + 227. Do not redo this audit.
- R4 selection component: independently reproduced all CSV cells, **50 unique stocks**, quotas 20/10/8/7/5, plus the two declared benchmarks. The list is a proposal, not download authorization.
- R1's intended separation of assumptions from evidence is correct. The six supplied proofs passed when rerun; the implementation still needs the validation below.
- All **22 supplied synthetic gate cases passed** when rerun. They do not cover the failing boundary cases below.
- The production diagnostic exactly matches the recorded baseline: D1 FAIL 1, D2 FAIL 6, D3 FAIL 4, D4 UNKNOWN, D5 PASS, D6 UNKNOWN. These are expected observations of poor source data, not themselves reasons to reject a data audit.
- Production main/WAL sizes and mtimes were identical before and after the independent checks. The four inspected Claude artifacts, including the frozen baseline, also retained their hashes. HEAD remains `73f266d`; nothing was staged.

## Remaining execution blockers

### F1 [P1] — Strict temporal admission still accepts missing evidence and later instants

Location: `_m1_closure/temporal_contract.py:91`, especially the checks at lines 116-130.

Two independent fixtures return `admitted=True`, reason `all_stamps_observed_and_before_cutoff`:

1. `observed_availability`, `ingestion_time`, `factor_vintage` and `provenance` are all empty strings. The checks reject only `None`.
2. Cutoff is `2024-06-28T10:00:00+08:00` (02:00 UTC); availability and ingestion are `2024-06-28T03:00:00Z` (03:00 UTC). This version is **one hour too late**, but string comparison admits it.

Required closure: validate inputs, reject blank/malformed provenance and times, and compare normalized instants. Declare how date-only event/factor values and cutoffs map to instants; do not silently mix date strings, local timestamps and UTC timestamps. Add these exact regressions, equivalent-instant clean controls, and malformed/blank cases. Keep this a local contract implementation until a runtime integration task is authorized.

### F2 [P1] — The quality checks are not yet fail-closed

Location: `_m1_closure/acceptance_runner.py:85-192`.

Reproduced findings:

- A positive raw-price/amount row with **`volume_unit=NULL` returns D4 PASS**, with `verifiable=1, contradicted=0, quarantined=0`. SQL NULL logic bypasses both the hand/share tests and `NOT IN`. This is missing unit evidence, not a verified unit.
- Empty tables return PASS from D1, D2, D3 and D5. The individual checks need a declared nonempty eligible population, and the aggregate admission gate must prove the expected symbols/session coverage before succeeding. Do not imply that the full current runner passes on empty data: D4 correctly returns UNKNOWN there.
- Two identical bars return PASS from D1-D4. The replacement registry omitted the former duplicate-key check. It also has no replacement for the required cross-store, same-basis price-reconciliation check, while price/date validation only targets the pricing table.

Required closure: NULL/blank/unsupported unit handling; an explicit expected-population/coverage gate; duplicate-key validation; date/price checks on every staged research/pricing view actually consumed; and reconciliation where two views claim the same source, basis and vintage. Legitimately different raw/adjusted views must be compared using a declared transformation, not by demanding raw price equality. Preserve typed UNKNOWN/FAIL outcomes and test the exact counterexamples.

### F3 [P1] — Archive protection and the runnable staging gate are incomplete

Locations: `_m1_closure/acceptance_runner.py:199`, `:250`, `:266-281`; `coverage_gap_generator.py:33-34` and `:73`.

- D6 hashes only symbol/date/adjustment/close/volume/amount. Changing an archive's **open price and provider** while leaving those columns unchanged still returns PASS. High/low, provenance, timestamps, schema and unrelated tables are also outside this hash. This is not preservation of the original database vintage.
- The documented command always calls `production_run()`, supplies no frozen D6 baseline, and overwrites `acceptance_baseline.json`. There is no command-line path/baseline selection or separate snapshot/validation operation. It exits 0 after reporting FAIL/UNKNOWN. Exit 0 is acceptable for a diagnostic collection mode, but must not be confused with a successful validation gate.
- The coverage generator also hardcodes production paths and the nominal research window. The documented command cannot perform the proposed staging-only, pilot-scoped, separate warm-up validation.

Required closure: a small explicit CLI (or an equally explicit reproducible entry point) for snapshot versus validation, with selected staging databases, original archives, expected pilot manifest, pinned calendar and read-only frozen baseline. Validation must not refresh its own baseline and must return an unsuccessful result when a required gate is FAIL/UNKNOWN. Protect complete, consistent snapshots of **both** original databases with file/content integrity verification covering the preserved data and schema. Separately verify intended staged changes. Prove successful clean staging validation, failing corrupted staging validation, baseline immutability, wrong-path protection and unchanged production metadata using temporary fixtures. Do not run production backups or promotion during this closure.

### F4 [P2, blocks this pilot specification] — Benchmark and price-basis rules need explicit routing

Location: `M1_CLOSURE.md:187-194` and `_m1_closure/acceptance_runner.py:104`, `:140`.

The pilot includes SH000300/SH000001 but D2 currently requires every symbol to be in the stock-only instruments catalog. A benchmark fixture fails D2. D4 requires positive amount/volume and unadjusted prices for every row; a valid price-only benchmark remains UNKNOWN. Thus the proposed mixed stock/benchmark batch cannot satisfy its stated unconditional gates without misclassifying indices as stocks or inventing liquidity evidence.

Required closure: explicitly separate stock and benchmark manifests/views. Check index identity, dates, prices and coverage, but do not apply stock trade-capacity requirements to a non-traded benchmark. A scoped not-applicable result must not hide unknown stock units. Specify the raw-price/amount evidence needed to validate stock units alongside any adjusted research series. Parameterize coverage for the expected 50 stocks plus two benchmarks, and measure the proposed 250-session warm-up separately, accounting for IPO eligibility. Keep 50,856 rows a gross upper bound, not an exact expected count for IPOs or suspensions.

## One bounded next step for Claude

Do not repeat the data census, coverage investigation or pilot selection. Fix F1-F4 in the local closure artifacts and run the targeted regressions plus one end-to-end temporary-staging acceptance test. Use the existing 50-stock proposal; any material universe or feature change still needs user approval. Do not launch broad parallel audits.

The next handoff must include:

1. A mapping from F1-F4 to fixes and exact test results.
2. A clean fixture that the real validation entry point accepts, and corrupted/empty/missing-evidence fixtures it rejects with non-success outcomes.
3. Proof that validation uses the supplied staging paths and frozen baseline without altering either original database or the baseline.
4. Updated pilot instructions distinguishing raw/adjusted stock evidence, benchmark evidence and warm-up coverage.

Production remains read-only. No network/plugin calls, downloads, runtime changes, migrations, services, commits or pushes. Stop for independent review before M2 execution. These are finite harness/contract fixes, not a request for another full M1 audit.

Once this gate passes, the recommended next authorized action is the **50-stock plus two-benchmark staging pilot only**. Full-market backfill and production promotion remain separate decisions.

## Important limit on the historical-data conclusion

The current local corpus cannot prove historical PIT availability. That does **not** establish that no external archived version or dated source evidence could ever improve it. Do not present the inability to recreate an unavailable historical system state as proof that all three-year exploratory research is impossible. Freeze the chosen data vintage, declare limitations, prevent revised-value leakage and keep any eventual research claim proportional to its evidence.

## Reproduction and scope

Commands independently run from the workspace:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m1_closure\temporal_contract.py'
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m1_closure\test_acceptance_gates.py'
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m1_codex_review\closure_review.py'
```

All three exited 0. The third is a diagnostic reproducer: it records the defects rather than claiming they are repaired. It calls the coverage builder, pilot selector and production diagnostic without invoking their artifact writers. No broad backend suite was rerun because production code was not modified.

Evidence: `_m1_codex_review/closure_results.jsonl`. Inspectable companion: `_m1_codex_review/M1_closure_review.ipynb`. All reviewer files remain uncommitted and excluded from Git submission.
