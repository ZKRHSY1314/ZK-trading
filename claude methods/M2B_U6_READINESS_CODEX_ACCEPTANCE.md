# U-6 readiness assessment — bounded technical validation

2026-09-09. **Revision 3 is technically validated for the documentation-only readiness-assessment scope.** R2-A and R2-B are closed; together with the previously validated corrections, the U6-R1 through U6-R4 correction loop is complete for this delivery. This is not policy adoption, a validated numerical model, source-capability acceptance or M2 completion.

## Reviewed delivery

`M2B_U6_READINESS_ASSESSMENT.md`: **609 lines**, SHA-256 **de130cf0bb5d02cd6a66a383eaa93188c7dbb2110337eb7e623a120b1ce368d2**. Claude's sole implementation fork displayed a completed revision-3 response and an empty composer. The reviewed bytes and preservation results are in `_m2_codex_review/u6_review_20260909_r3/`.

All **91 protected pins** match, including the five G3 r2 files and the retained basis/smoke evidence in that baseline. All **46 G1 files** match the accepted frozen delivery with no additions. Additional G1/G3 acceptance, proposal, goal/request and earlier review pins match. HEAD **73f266d**, staging empty. Existing unrelated working-tree changes were preserved. File equality verifies preservation of the checked artifacts; it does not prove every action Claude performed. No tests, replay, ratio recomputation, network or SQLite operation was performed by Codex in this review.

## Findings closed

- **R2-A:** section 3.1 states the additive and multiplicative cases directly as conditional pre-rounding relations. It no longer derives them from unspecified functions of a common underlying price. Mapping interval constants to corporate actions requires additional assumptions, and neither relation has been evaluated under a defined error model. Unsupported loose-fit judgments are withdrawn consistently in the headings, stock discussion and recommended study. Condition 5 now distinguishes a negative observed sign from model-dependent consistency; fulfillment is not established.
- **R2-B:** section 3.4 and M-3 acknowledge the two stocks' 30-session same-source/same-calendar tails, their differing fetch timestamps and uniformly zero differences. The limitation concerns the lack of a discriminating matched control on the long event-bearing spans, not absence of every shared span in the extract.
- The valid earlier corrections and observations remain: six identified in-interval comparisons, five exact difference matches, E-1's unresolved 0.01 difference, no demonstrated anchor or vendor-basis exclusion, a bounded index control, and separate reference-basis and identity questions.

**Non-blocking attribution clarification:** the revision-3 introduction summarizes the R2 review too broadly as having validated all U6-R1 through U6-R4. R2 actually closed U6-R2/U6-R4 and preserved substantial corrections while R2-A/R2-B remained. The final closure occurs in **this** review at the revision-3 hash. This historical wording does not change the present analysis or authority; no additional documentation round is required.

## Decision and remaining boundary

The assessment supports withholding vendor-basis certification: the reference basis is recorded but not independently established, and the observed numerical relations do not establish a supplier algorithm or causal explanation. Keep **P1 open, U-6 deferred, every eligibility false, source capability FAIL**, historical EV6 disagreements unchanged, and **both capture authorizations consumed**. The proposed description “evidence available but underdetermined” is explanatory; no policy or gate state is adopted here.

The authorized documentation task is complete. Pause the 10-minute heartbeat and notify the user because the next useful step would perform new calculations, which the present task expressly excludes. Do not create another acknowledgment or proposal revision.

## Concrete next decision for the user — not authorized or dispatched

Recommended: authorize **one bounded retained-artifact study**, combining M-1/M-2 with M-3 source stratification, with these limits:

- **Inputs:** existing accepted G1/G3 JSON and reports, the already retained reference-extract JSON, and current reviewed provenance/contract text only. No SQLite, fresh extract, network, adapter replay or capture; no expansion to more instruments. Read the two stock series over their documented 470-session spans, SH's 37-session comparison, and the already identified 30-session tails as contextual controls.
- **Work:** examine additive/multiplicative relations within identified inter-event intervals; inspect E-1's ex-date and immediately adjacent retained observations; stratify the reported observations by existing source and fetch-time metadata. State mathematical rounding assumptions explicitly before comparison and report sensitivity without tuning an acceptance threshold. Distinguish raw retained fields from values derived from them; if full-precision source values cannot be recovered from the permitted JSON, report that limitation rather than claim exact recovery or access another source. No empirical result can certify a vendor basis or identify a cause on its own.
- **Only new deliverable:** `claude methods/M2B_U6_RETAINED_STUDY.md`, with input hashes, exact calculation commands/code in the document, observed results, counterexamples and unresolved questions. No standalone script, new result directory, dataset or changes to accepted artifacts. Commands may compute in memory and record results in this document only. The review will check the calculations after delivery.
- **Unchanged limits:** no policy adoption, gate/label/eligibility change, production implementation, threshold calibration, services/accounts/tokens, production/dataset/strategy/knowledge mutation, trial collection, training, source expansion, staging/commit/push or live trading. Stop at `proposed for review`. This study does not authorize the later 52-symbol pilot or three-year backfill.

This is a proposed computation scope for a user decision, not a new instruction that Claude may execute. The current document's one-file follow-up suggestion is a proposal, not an already adopted policy. The study could narrow competing explanations; independently reliable reference-basis evidence and any later U-6 sufficiency decision would still be needed before certification. Do not promise M2 completion from this study.

## English instruction to Claude — hold

Codex has technically validated revision 3 of M2B_U6_READINESS_ASSESSMENT.md at SHA-256 de130cf0bb5d02cd6a66a383eaa93188c7dbb2110337eb7e623a120b1ce368d2. R2-A and R2-B are closed and the bounded documentation correction loop is complete. Preserve every file; create no acknowledgment or further revision. The study described above is a pending user decision, not authorization. Do not perform M-1/M-2/M-3 or any new computation, retrieval, implementation or operational action. P1 open, U-6 deferred, all eligibility false, source capability FAIL, both capture authorizations consumed. Hold for the next explicitly scoped user task.
