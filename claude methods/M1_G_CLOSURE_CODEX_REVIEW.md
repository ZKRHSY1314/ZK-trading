# M1 G1-G3 closure acceptance review — Codex, 2026-09-06

## Verdict and verified progress

**G3's reproduced overwrite defect is closed. G1 and G2 are partially repaired but not yet accepted. M1 remains unvalidated as an executable M2 handoff; no downloads are authorized.**

Independent reruns:
- `temporal_contract.py`: 13/13, exit 0.
- `test_acceptance_gates.py`: 46/46, exit 0.
- `test_staging_gate_e2e.py`: 36 checks, 0 unexpected, exit 0.

The supplied tests now exercise history date/price/duplicate/FK errors, explicit transformation declarations, the 305-session IPO clean control, and Windows normalized/case/hardlink output collisions. Preserve these fixes. M0, the accepted coverage census and the 50-stock selection are not being reopened.

The data-quality review targeted the grain actually consumed: a security/session/basis record in each staging view. Marginal counts and matching CLI strings are not sufficient evidence of that contract.

## G1a [P1] — Research completeness and symbol identity still bypass the command

Locations: `_m1_closure/staging_gate.py:373-383`, `:406-417`; `acceptance_runner.py:273-305`.

H0 checks only distinct symbol and global session counts. V1/V2 check only pricing rows. X2 uses an inner join, so missing or replaced history keys disappear from reconciliation.

Independent real-command probes:
- Clean control: 5 securities × 728 sessions = 3,640 records per view; exit 0.
- Delete one required history security/session: H0 still reports 5/728, X2 common count falls to 3,639, but the command still exits 0.
- Replace one history stock's entire 728-row series with `XX123456`: H0 still reports 5/728, X2 compares only the remaining 2,912 common keys, and the command still exits 0.

Impact: an incomplete or incorrectly identified research series can be certified for downstream features and backtesting.

Required closure:
- Validate history symbol identities against the declared manifest, not just symbol counts.
- Apply listing-aware eligible-key coverage to both consumed views.
- Under the declared identity/two-view contract, explicitly detect missing and unexpected keys in both directions. Account explicitly for any declared scoped subsets instead of silently dropping nonmatches.
- Keep expected populations independent of observed data. No success based solely on a nonempty intersection.
- Add real-CLI tests for a single missing history key and a substituted/unknown symbol while marginal counts remain unchanged.

## G1b [P1] — Representation checks trust arguments instead of data

Locations: `_m1_closure/staging_gate.py:384-409`; `acceptance_runner.py:293-305`.

Two independent probes still exit 0:
- Set every actual history `adjustment_mode` to `qfq`, but invoke the command with both bases declared `none` and transformation `identity`. X1 calls the bases common without checking stored values.
- Change one history high from 11 to 12, preserving valid OHLC relationships and the same close. X2 checks close alone and reports identity reconciliation passed.

Impact: the common-basis claim is not verified, and differing price paths can reach shape/stop-loss research under an identity label.

Required closure:
- Validate supported, nonmissing actual representation metadata in each consumed view against its declared basis. Reject mismatches and unintended mixed bases before reconciliation.
- Define the fields promised by the identity contract and compare those fields, including OHLC, with explicit tolerances. Do not infer source/vintage equivalence from numeric agreement alone.
- Do not demand raw/adjusted equality or implement speculative factor conversions. Unsupported required transformations remain blocking.
- Add CLI regressions for actual metadata/argument disagreement, mixed bases, and individually changed open/high/low values with close unchanged.

## G2a [P1] — The delivered pilot manifest cannot pass with complete data

Locations: `_m1_closure/staging_gate.py:205-218`, `:414-417`; `pilot_symbols.csv:52-53`.

The actual manifest declares two index benchmarks with blank `list_date`. The coverage code nevertheless applies the stock listing-date requirement to them.

I used that actual manifest unchanged and built disposable complete, consistent two-view data:
- 50 stocks: all 34,737 eligible research records, V1 PASS.
- Two benchmarks: all 728 sessions each.
- Total: 36,193 records in each view, reconciliation PASS.
- V2: UNKNOWN with both benchmark symbols unresolved; command exits 1.

The supplied clean tests conceal this integration failure by inventing nonempty fixture listing dates for indices.

Required closure:
- Give benchmarks an explicit, separately defined research-coverage contract. Do not fabricate a stock IPO date for an index.
- Keep the approved full pilot at exactly the existing 50 stocks plus SH000300 and SH000001. Do not remove benchmarks or scope V2 away merely to obtain success.
- Drive a genuine complete two-view control from the actual delivered manifest and accepted eligibility rules, not a replacement manifest with invented metadata. Delete a required benchmark session and verify failure.
- Correct the report's assertion that P0 always catches an accidentally omitted benchmark: its expected symbol total is derived from the same manifest, not an independent 52-member contract. Generic benchmark-free sub-batches may be explicitly supported, but are not this approved pilot.

## G2b [P2] — An explicit required warm-up can be silently disabled

Location: `_m1_closure/staging_gate.py:419-445`.

With no warm-up data, `--warmup-required --warmup-sessions 250` and no `--warmup-start` returns exit 0; V3 becomes NOT_APPLICABLE/advisory.

Required closure:
- Treat the incomplete required configuration as an input error, or derive and validate the preceding interval from the pinned calendar and the requested depth.
- A required warm-up must never become advisory/NOT_APPLICABLE just because an associated option is omitted.
- Keep research coverage separate from per-security feature readiness. For a new listing, all eligible bars can be present while 250 observations are unavailable; report that honestly.
- Add CLI boundary tests for missing start, insufficient per-security depth and the non-overlap condition. An explicitly advisory pilot may report insufficient warm-up, but must not claim feature readiness.

## Bounded next handoff

Close **G1a, G1b, G2a and G2b only**, retaining G3 and all passing work. These are remaining pieces of the existing data-validation contract, not a new broad audit. Add the missing real-command tests; do not merely add more primitive-function tests or change assertions to accept the false passes.

Write scope: local closure/review artifacts under `claude methods/`, including necessary pilot contract metadata and documentation without changing selected securities. Production databases, existing datasets, methodology/knowledge materials, runtime code and unrelated changes remain read-only. No providers, network/plugin calls, downloads, migration, services, staging, commits or pushes.

Update the English report and Progress Ledger with exact commands, actual results and limitations. Stop at `ready_for_review`. A later accepted gate permits a request for separate authorization for the bounded staging pilot, not automatic execution or full-market promotion.

## Evidence and safety

- Reproducer: `_m1_codex_review/gclosure_review.py`.
- Actual captured CLI output: `_m1_codex_review/gclosure_results.jsonl`.
- Supplied-suite outputs: `_m1_codex_review/gclosure_suite_results.json`.
- Inspectable companion: `_m1_codex_review/M1_gclosure_review.ipynb`.

Run from the repository root:

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m1_codex_review\gclosure_review.py'
```

The independent diagnostic exited 0, meaning the observations were collected successfully, not that the rejected candidate is fixed. All mutations occurred in newly created temporary fixtures, which were cleaned up. Archive fixture files, the frozen baseline and the calendar were hash-identical after the probes. Production main/WAL sizes and mtimes remained unchanged, and the reviewed Claude artifact hashes stayed unchanged during the probes. No broad backend suite was rerun because no runtime code was changed.
