# M1 execution-gate wiring review — Codex, 2026-09-06

Verdict: **the earlier primitive-check defects are repaired, but M1 is not yet validated as an executable M2 handoff**. Do not start downloads. Close the three concrete issues below; do not repeat the data audit, coverage census, pilot selection or M0 work.

## Verified progress

Independent reruns of Claude's supplied commands passed:

- `temporal_contract.py`: **13/13**, exit 0. The previously reproduced blank-provenance and mixed-timezone admission defects are closed under the documented date-only semantics.
- `test_acceptance_gates.py`: **46/46**, exit 0. NULL units, empty-population checks, duplicate detection, whole-database fingerprint primitives and benchmark routing now have passing regressions.
- `test_staging_gate_e2e.py`: **19/19**, exit 0. Explicit staging paths and baseline preservation are exercised by these tests.

The data-quality review focused on whether the checks are connected to the real command. It found three remaining integration/safety defects, not a reason to restart the audit.

## G1 [P1] — Corrupt research data bypasses the actual validation command

Location: `_m1_closure/staging_gate.py:205-225`; `acceptance_runner.py:273`.

The command invokes date/price/unit/duplicate checks on `staging_t`, but invokes only the ingest-run foreign-key check on `staging_h`. The new D8 cross-store function is never called by `validate`.

Independent end-to-end reproduction:

1. The supplied clean fixture has 728 sessions in the pricing store, but only **three history rows across three stocks and one session**. It returns exit 0.
2. I changed that disposable history fixture to `trade_date='ERROR'`, `close=-999`, `high=1`, `low=100`, an incorrect provider, and inserted a duplicate row. The actual command still returned **exit 0 / RESULT: SUCCEEDED**. D8 was absent from the executed checks.

Required fix: define the expected history representation for this pilot, then validate every consumed staging view for expected population, dates, OHLC, duplicate keys and provenance. Wire the declared same-basis/transformation reconciliation into the real command as a required gate. An unavailable or unsupported required transformation must not be silently skipped. Do not manufacture raw/adjusted equality; declare the representation first.

Acceptance: drive the real CLI with separately corrupted **history** fixtures (bad date, bad price, duplicate, missing coverage, unsupported/missing transformation and same-basis divergence), and require non-success. Keep a genuine clean two-view control that succeeds. A unit test of D8 alone does not close this issue.

## G2 [P1] — Valid IPO coverage is rejected as missing pre-listing data

Location: `_m1_closure/staging_gate.py:76-82`, `:119-139`, `:218-225`.

`load_manifest()` discards listing metadata, and `pilot_coverage()` applies the entire research-session set to every stock. This reverses the listing-aware denominator already fixed in the accepted coverage audit.

Independent fixture: a stock listed on **2025-06-10**, with **all 305 eligible post-listing sessions** present and no fabricated pre-listing bars, fails V1 and exits 1 solely because the gate still demands the earlier sessions.

Required fix: retain and validate per-symbol eligibility metadata and reuse the accepted listing-aware coverage rules. Measure research and warm-up coverage separately. Pre-IPO sessions are outside eligibility, not missing bars. Unknown listing or suspension evidence remains explicitly unresolved; do not invent classifications or bars to satisfy a gate. The warm-up interval must end strictly before the research start rather than double-counting the first research session. If 250 preceding sessions are required, encode that requirement explicitly and report unavailable new-stock lookback honestly.

Acceptance: full eligible IPO coverage passes; deleting one required post-listing session fails under the declared threshold; a pre-listing session is never required; unknown eligibility does not masquerade as complete; warm-up and research boundary tests do not overlap. Keep benchmark eligibility separate.

## G3 [P1] — Snapshot output can overwrite an input database

Location: `_m1_closure/staging_gate.py:87-108`.

The output path is not checked against input paths. On a **disposable archive only**, I invoked `snapshot` with `--baseline-out` pointing to its own `--archive-trading` file and `--force`. It returned exit 0, changed the archive, and replaced the SQLite header with JSON. The statement that the mode only writes a baseline is therefore unsafe without path validation.

Required fix: resolve and validate all input/output roles before writing. Reject a baseline output that equals or aliases either archive, the calendar or any other protected input, regardless of `--force`. Force may replace an eligible baseline, not an input database. Also reject invalid role collisions for staging/archive paths according to the declared workflow. Keep the validation operation read-only.

Acceptance: temporary-fixture tests for identical and normalized/aliasing input-output paths fail before any write, and input hashes remain unchanged. A normal baseline creation succeeds; deliberate replacement of an eligible baseline follows the documented policy. Do not test this on production files.

## Next instruction to Claude

Fix **G1-G3 only**, retaining the independently verified F1 and primitive-check improvements. Add the missing end-to-end failure cases to the actual staging command tests. Do not broaden the audit or change the pilot universe/strategy. Update the report and progress ledger with exact commands, counts and outcomes, then stop at `ready_for_review`.

Write scope remains local, uncommitted audit/closure artifacts under `claude methods/`. No runtime edits, network/plugin calls, downloads, production writes, migrations, services, commits or pushes. M2 can be proposed for user authorization only after this gate is independently validated; authorization would initially cover the 50-stock plus two-benchmark staging pilot, not full-market backfill or promotion.

## Evidence and safety

Independent reproducer: `_m1_codex_review/gate_wiring_review.py`.
Captured observations: `_m1_codex_review/gate_wiring_results.jsonl`.
Inspectable companion: `_m1_codex_review/M1_gate_wiring_review.ipynb`.

```powershell
& '.\backend\.venv\Scripts\python.exe' -B -X utf8 '.\claude methods\_m1_codex_review\gate_wiring_review.py'
```

The final diagnostic run exited 0; this means the observations were collected, not that the defects are fixed. An initial reviewer-fixture run left a SQLite handle open and failed on Windows cleanup; the reviewer script was corrected to close its connections before the successful rerun. The failed attempt's temporary directory was not removed after cleanup was denied; no alternate deletion route was attempted.

All destructive fault probes were confined to freshly created temporary fixture directories. Production main/WAL sizes and mtimes were unchanged through the successful run; the baseline was byte-identical through all validation probes. No production database was backed up, overwritten or migrated. The index remains empty and HEAD remains `73f266d`. No broad backend suite was rerun because runtime code was not changed.
