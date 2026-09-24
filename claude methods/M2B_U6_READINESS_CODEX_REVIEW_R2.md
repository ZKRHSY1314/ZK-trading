# U-6 readiness assessment — Codex review R2

2026-09-09. **Verdict: substantial corrections validated; two bounded analytical corrections remain.** The recommendation to withhold certification is supported by the missing independently verified reference basis. This review does not adopt a policy or authorize a numerical follow-up.

## Reviewed delivery and preservation

Revision 2 of `M2B_U6_READINESS_ASSESSMENT.md`: **563 lines**, SHA-256 **b6d4b5d8daa49b6d8262bd01e67c0b8d12cf3c3a46ebdc9e600bc3a4ba5e7590**. The sole Claude fork was observed Idle with its completed handoff and an empty composer. The unchanged reviewed document and preservation results are retained in `_m2_codex_review/u6_review_20260909_r2/`.

All **91 protected file pins** match; the **46 G1 files** match the frozen accepted delivery with no extra file. G1/G3 acceptance reports, the R1 review, the proposal, and goal/request match their reviewed hashes. HEAD **73f266d**, staging empty. This is file-content verification, not proof of every action Claude took. Codex ran no tests, replay, ratio computation, network or SQLite operation in this review.

Validated corrections: unsupported hfq/convention exclusions withdrawn; six comparisons and five exact matches restored without an invented independence ranking; bounded index control; official identity/continuity distinguished from the missing legal date; reference labels distinguished from basis certification; condition 5 restored to ratio behaviour; fail-closed distinguished from disproof; mandatory common-mechanism prerequisite withdrawn; follow-up scope, holdout limitations and separate computation authorization corrected. U6-R2 and U6-R4 are closed for this document hash. Preserve these corrections.

## R2-A — finish U6-R1's relational assumptions and consistent inference limits

**Locations:** lines 147–165, 190–207, 246–249; condition-5 ledger lines 92–113.

A1 says only that V and R are functions of a common underlying price P. It does not constrain V enough for the conclusions at lines 155–159. For instance, if R* = P - C but V* = aP, then V* - R* = (a-1)P + C, which need not be constant while C is constant. Likewise R* = P/F does not make V*/R* constant when V* is an unspecified function of P. These are algebraic counterexamples, not fitted data or claims about either supplier.

Minimal fix: express the hypotheses directly as conditional relations between **pre-rounding** quantities, e.g. `V* - R* = C_j` or `V*/R* = K_j` within an identified inter-event interval. Relating changes in C_j to cash amounts or K_j to corporate actions needs additional stated assumptions. Alternatively, explicitly hypothesize the required V*-to-P relationship; never assert it is observed. Keep rounding unspecified and untested. Do not create a new model specification, threshold or calculation.

The counting argument at lines 196–201 does establish that changes occur away from the three identified event dates. It does **not** establish that H-add fails to describe the data "even loosely" (203–204) or that the difference is "not close" to piecewise constant (246). Those magnitude/model judgments conflict with the document's own untested-rounding qualification. Retain the counting observation and withdraw those judgments, including the heading's model verdict; neither candidate's fit has been evaluated under a defined error model.

For the condition-5 ledger, report the **observed negative sign** without marking consistency with a corporate action as established: that consistency is model-dependent on the same unresolved assumptions. Preserve the exact stored changes and the already correct statement that condition 5 is not satisfied as a whole.

## R2-B — narrow the confounding claim to the comparisons that lack a useful control

**Location:** lines 252–258, especially "no cell holds two instruments on one source over one span"; corresponding M-3 payoff wording.

The accepted G3 report itself contains a counterexample to an absence claim about the whole extract: **both stocks** have `tonghuasun.local.quotes.candle` rows over **2026-07-27 through 2026-09-04**, 30 sessions each, with zero differences. Fetch timestamps differ (`18:06:09` versus `18:06:31`), and these tails contain no identified cash implementation that would discriminate the candidate relations. Your own table at lines 243–244 lists them.

The useful narrower conclusion remains: the long nonzero, event-bearing comparison spans do not provide a matched control sufficient to identify whether the observed structure comes from source, instrument or adjustment. Acknowledge the existing same-source/same-calendar tail, its differing fetch timestamps, and its lack of discriminating variation. Do not say no such overlap exists, or that all source/instrument/span combinations are absent. No new regrouping or computation is needed.

## Single correction task — U6-DOC-R2-20260909

Revise **only** `claude methods/M2B_U6_READINESS_ASSESSMENT.md` for R2-A and R2-B and any directly inconsistent summaries. Keep this small; do not expand the assessment or reopen validated evidence. The certification-withheld recommendation remains supported regardless of these modeling corrections. Do not create acknowledgments, a new proposal, scripts, result directories or new research questions for this correction.

No tests, replay, numerical recomputation/fitting/calibration, network/retrieval, extract, SQLite, capture, service/account/token access, production/dataset/strategy/knowledge changes, policy adoption, threshold/tolerance, implementation/gate/label/eligibility change, pilot/training/source expansion, staging/commit/push or live trading. All other files, including reviewer artifacts, remain unchanged. Both capture authorizations are consumed. Stop at `proposed for review` with the document hash and preservation evidence. P1 open, U-6 deferred, all eligibility false, source capability FAIL. M-1/M-2/M-3 is still not authorized.
