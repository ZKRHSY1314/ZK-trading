# U-6 retained study — Codex review R1

2026-09-09. **Verdict: core interval arithmetic independently reproduced; delivery and inference corrections required.** This review preserves the numerical work and requests one consolidated correction, not a restart of the study.

## Reviewed evidence and independent work

Study: `M2B_U6_RETAINED_STUDY.md`, 538 lines, SHA-256 **990395008c8767da3931c90460a8eb5c1d2cd44b3d3b4a93856105b62bd5a26b**. Snapshot, independent numerical output and preservation record: `_m2_codex_review/u6_study_review_20260909_r1/`. The Claude UI finished its handoff and refreshed to Idle; no queued task was observed.

Independent command: `python -X utf8 -B "claude methods/_m2_codex_review/review_u6_retained_study_r1.py"` using the bundled Python. Exit **0**. It reads only the two pinned JSON files, parses decimal tokens explicitly and uses rational interval intersections; no production module, replay, decoder, network or SQLite is involved.

**All 14 interval rows reproduce**, including sample counts, reference-price ranges, difference spreads, additive/multiplicative feasibility and the stated factor windows. The seven event-step comparisons reproduce, six in the principal interval plus contextual E-0. The disclosed amount is compatible with each reported conditional interval. For E-1/E-2, an additional construction with the latent prior vendor close fixed to the reconstructed cent value also admits a joint pairwise feasibility witness; this strengthens numerical compatibility, not causal identification. The 0.28 observed versus 0.27 disclosed difference remains a real stored comparison.

All **91 protected file pins** and **46 G1 files** match; no G1 additions. Readiness assessment remains `de130cf0…`; HEAD **73f266d**, staging empty. The checked inputs remain unchanged. This verifies these file contents, not every action in the implementation session.

## US-R1 — make the delivered calculation reproducible and account for scratch files

Section 4 claims three passes are reproduced verbatim, but sections 4.2/4.3 are fragments. `intervals`, `sym`, `prev`, `disc`, `ka`, `kb`, `ca`, `cb`, `mul_ok`, `add_ok` and `Rc` are not defined by those fragments in a runnable program. Running section 4.1 followed by 4.2 does not supply the missing interval function or event loops. The named scratch files are 8,634 / 7,270 / 4,791 bytes; naming their hashes does not include their content. The report's independent reproducer succeeds because Codex reconstructed the analysis, not because all supplied commands are executable as delivered.

Provide one complete self-contained code block (or complete separately runnable passes) in **this same Markdown file**, with a stdin execution command requiring no scratch script, explicit pinned-input assertions before computation, reconstruction validation and complete interval/event/result loops. Include every calculation supporting sections 5.2–5.7. A derived rational bound is not a tunable acceptance threshold; retain that distinction. Do not hardcode measured output as a substitute for calculation.

The assignment specified in-memory computation and only one output file. The report nevertheless says scratch scripts were used, while the header says nothing outside this file was created or modified. Account accurately for the **actual paths and creation/use** of those three existing scratch files, distinguish repository scope from global filesystem scope, and acknowledge the departure from the assigned single-file execution form. Do not delete or alter them to make the history disappear. No new standalone scratch files or acknowledgment artifact for this correction.

## US-R2 — E-1 compatibility is not an explanation of its cause

Sections 5.5/5.6/7 claim the discrepancy "is an artefact" of reading a multiplicative-feasible segment additively, even while the limitations disclaim causality. R1/A3/A4 plus feasibility of one candidate do not prove that this candidate generated the observations. Reporting an observed difference step is also not itself asserting a constant-difference model over the whole segment. Segment-wide rejection of H-add does not make the observed 28-versus-27 comparison erroneous or identify why it occurred.

Replace the artifact/explanation verdict consistently with **conditional compatibility**: the disclosed 0.27 is compatible with the examined multiplicative mapping and rounding envelope; it is not excluded by this test, but its causal role remains unestablished. The pairwise additive calculation needs its own conditional premise that the latent difference step equals 27 cents. Under that premise plus R1, 25–29 observed cents are permitted; this neither establishes that premise nor rescues the globally infeasible H-add intervals. E-2's exact difference remains an observation too, without declaring an identified price-level cause or assigning it a new evidentiary ranking.

## US-R3 — keep the source comparison and proposed non-price follow-up descriptive

Section 5.7 correctly observes different feasible relations for the same instrument across disjoint spans. This excludes only a simplistic explanation in which **instrument identity alone fixes one relation for all dates**, not a general instrument/time interaction or vendor-side change. Source, fetch time, event set, date span, prices and the vendor path still covary. Similar price-range ratios (1.24 versus 1.27) do not control for effect size, precision, sample size or the exact price path. Do not say the instrument confound is generally broken or the narrower-price-range explanation is eliminated.

These pairwise findings cannot be assigned exclusively to the reference side while excluding the vendor side. They do not establish that the uniform `qfq` label is less reliable or that different conventions caused the relations. The reference basis remains unverified, which was already sufficient to withhold certification. Describe the patterns and limits without promoting them to new evidence of which side is wrong.

Section 9's proposed non-price study has the same problem: volume/amount changes at a source boundary do not establish a pipeline cause rather than real market variation, and absence of such a change does not isolate price adjustment. Restate the possible payoff as detecting/describing field or unit inconsistencies and candidate anomalies; preserve alternative explanations. Do not execute that follow-up within this correction.

## US-R4 — numerical and modeling precision, corrected in the same pass

- `[18,22]` cents (and each analogous C-step interval) has **continuous width 4 cents**, containing five integer-cent grid points. The unknown constants are continuous under R1. Replace "5 cents wide" accordingly; do not change the validated endpoints.
- Section 5.4 uses a midpoint estimated from the **same observations**. It is a within-sample algebraic consistency check, not an independent prediction or validation. Keep the arithmetic but label its dependence accurately.
- The reconstruction residual in the supplied code compares to `Fraction(float).limit_denominator(10**15)`, an extra rational approximation. State precisely which representation is compared, or compute against an explicitly chosen exact retained representation and update the corresponding numbers. Codex's exact **JSON decimal-token** comparison gives maxima `2.88135593220339e-16` (SH) and `2.761743067345784e-16` (BJ); these differ from the report because the representations differ, not because reconstruction fails. Do not silently equate these metrics.
- R1 is a closed half-cent **nearest-rounding envelope**, not an envelope for arbitrary truncation. Feasibility is existential in that envelope and need not imply one deterministic tie rule is satisfied. Infeasibility is robust only to subsets of this envelope, as the report already largely states.
- Section 6.6's "an unidentified event ... would appear as an infeasibility" is not guaranteed. Some events could preserve the relation or remain within rounding bounds. Withdraw that detection claim while preserving G-e as unestablished.

## Single correction task: U6-STUDY-R1-20260909

Revise only `claude methods/M2B_U6_RETAINED_STUDY.md` to resolve US-R1 through US-R4. Preserve the validated 14 interval outcomes, the seven conditional step comparisons and all source evidence. New in-memory calculations and focused mathematical validation needed to supply complete reproducible code are authorized under the user's continuing offline scope; no separate permission is needed. Keep any representation-related metric changes explicit. Do not broaden into new model families, new thresholds, or another study.

No new retrieval, extract, capture, database/SQLite, adapter replay/decoder, services, accounts/tokens, production implementation, dataset/strategy/knowledge changes, policy/gate/label/eligibility changes, threshold calibration, pilot/backfill/training, source expansion, Git staging/commit/push or live trading. All other artifacts and prior reviews stay unchanged. Report actual side effects accurately; do not manufacture a clean history. Deliver at proposed for review with hash and preservation evidence. P1 open, U-6 deferred, all eligibility false, source capability FAIL, both capture authorizations consumed. Codex will review and continue the next useful authorized offline task; this correction does not pause the workflow.
