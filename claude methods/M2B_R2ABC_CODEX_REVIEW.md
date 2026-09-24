# M2b R2-A/B/C independent review — 2026-09-08

## Verdict

**Partial technical acceptance; correction closure remains blocked. No progression to a new live capture, staging pilot, or training is approved.** The retained-body parsing, exact JS-variable binding, and explicitly dated stock-adapter replay work on the actual retained inputs. One denominator-validity defect remains. R1 also needs a small defensive validation improvement. Do not reopen the already accepted F8 or earlier milestones.

This is a code-and-evidence review, not investment advice or a claim of strategy effectiveness. Data-validation and data-quality review distinguish implementation success from source capability and denominator validity.

## Independently verified

- Claude's smoke suite: **175 cases, 0 unexpected, exit 0**.
- New reviewer: `backend/.venv/Scripts/python.exe -B -X utf8 "claude methods/_m2_codex_review/review_m2b_r2abc.py"`: **39 checks, 35 passed, 4 failed, exit 1**. Three failed assertions demonstrate one denominator defect; the fourth demonstrates R1's defensive gap. These are not four independent defects.
- Offline replay exactly reproduces `c23f44bcea71e89d5ee0c0b6bfedf4532dcae3daed71deb5f51b93fe91ff3743`.
- All actual D1/D5/R1 checks pass. The two stocks each return 978 rows from 2022-08-24 through 2026-09-04. The index returns its full 5,987-row series; it does not accept the stock date arguments.
- The auxiliary objects decode into 26 SH rows and 42 BJ rows, including two preserved unusable zero observations in the BJ series.
- Capability remains **FAIL**, with exactly two EV6 failures: capture-time `undecodable` versus corrected offline `decoded` for the stock auxiliary bodies. This is a declared parser-version disagreement, not evidence that the retained bodies changed. Neither the old capture verdict nor EV6 was waived.
- Current producer hashes match the new revision's provenance. Its seven input hashes match both the parent and copied inputs. Original run-1/run-2 checks retain their prior-review hashes. All eight retained evidence/revision/receipt/frozen directories are unchanged during this review.
- Production database size/mtime metadata is unchanged during review; this is a bounded observation, not proof about all earlier activity. No database opens or remote requests were permitted by the reviewer guards.
- HEAD remains `73f266d`; staging is empty. No implementation changes, service actions, or capture were performed by this review. Only this report and its independent reviewer were added locally.

## Required correction: explicit invalid observations must interrupt denominator validity

Location: `claude methods/_m2_smoke/sina_klc_decoder.py`, `outstanding_share_as_of()` around line 487; consumed by U4 in `smoke_checks.py` around line 1143 and by `share_series_quality()`.

Counterexample: Jan 1 = 100, Jan 3 = 0, Jan 5 = 200. On Jan 3 and Jan 4 the current function returns the Jan 1 value, and a window starting Jan 4 reports `covers_window_start=True`. It skips the newer invalid observation and silently restores an older denominator.

The docstring's equivalence to pandas `ffill` is incorrect. Independently, `[100, 0, missing, 200].ffill()` produces `[100, 0, 0, 200]`, not `[100, 100, 100, 200]`. An explicit zero and an absent observation are different states.

Use the latest observation at or before the query date as the state. If it is unusable, return no usable denominator until a later valid observation; preserve the raw zero and its reason. Do not backfill from the future. Update U4 missing-denominator counts and coverage accordingly. Add positive-zero-positive and repeated-zero tests, including an end-to-end U4 assertion. Leading-zero coverage alone does not exercise this defect.

This is a general validity bug, not a demonstrated corruption of the two retained research windows: their observed BJ zeros precede the first positive observation. Long carry-in age alone also does not prove a change-series value wrong.

## Small R1 hardening item

Location: `smoke_checks.py`, `_replay_verdict()` around line 432.

`{rows: 1, first_date: "2023-01-03", last_date: null, dates: []}` currently receives PASS. Validate a nonempty actual date sequence and consistency of row count and first/last dates, rather than treating first-date metadata as proof of returned dates. Preserve the existing no-fabricated-date rule. Stock results must respect the declared stock window; do not incorrectly apply that window to the index's full-series interface.

The real current adapter returns internally consistent results. This is defensive hardening, not a claim that its retained replay returned empty dates, and not a new completeness requirement that every security must always return 978 rows.

## Current-state handoff still contradicts itself

Section 15 of `THREE_YEAR_RESEARCH_EXECUTION_GOAL.md` has an updated heading but still says "it is the only one", "a second is authorized and unused", and presents old pins/165 tests under "Current state". Its final present-tense paragraph again says a run is unused. The newer Run 2 paragraph correctly says both authorizations are consumed.

Replace the operative current-state block with one concise authoritative state: two captures occurred; both one-run authorizations are consumed; R2-ABC is under offline review; source capability remains FAIL; no further capture is authorized. Preserve old text as explicitly dated history, not another active handoff. Distinguish old accepted frozen pins from the current revision's producer pins. No broad documentation rewrite is needed.

## Next bounded step for Claude

Fix the invalid-observation interval, harden R1, and reconcile only the operative handoff. Keep this reviewer unchanged and rerun it plus the smoke suite. Preserve the existing revision and produce a new separately named offline revision with current producer provenance after changes. A cross-version producer-pin mismatch against the old revision is expected and must be reported, not erased; use a separately versioned closure driver for the new revision if needed. Recompute the retained-byte result, keep EV6 visible, and stop at `ready_for_review`.

No HTTP capture, production database opens/migrations, service start/stop, token access, dataset changes, Git staging/commit/push, source expansion, or training. Do not request a third capture merely to make a version gate green before these offline corrections have been reviewed.
