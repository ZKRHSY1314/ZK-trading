# U-6 readiness assessment — Codex review R1

2026-09-09. Reviewed task `U6-READINESS-20260909`; verdict **corrections required** for the analysis, not for the preserved source artifacts. The central recommendation to keep U-6 deferred is reasonable; several supporting exclusions and proposed next-step claims are not established.

## Reviewed state

Claude's sole implementation fork was Idle with a completed `proposed for review` response. The 449-line document `M2B_U6_READINESS_ASSESSMENT.md`, SHA-256 **7f0430942f2aa1b82c789e264d9bd4752f624430b82bb7cfe7ee2024fe5afa4c**, was copied unchanged into `_m2_codex_review/u6_review_20260909_r1/`. That folder's `review_results.json` records checks.

All 46 G1 file pins match the accepted delivery; all five G3 r2 pins match; the 91 previously protected paths have no mismatch. HEAD is `73f266d`, staging empty. No tests, replay, ratio recomputation, network or SQLite were used for this review. The review reads already retained results and checks the logic of the document; no proposed M-1/M-2/M-3 study has been executed.

Valid contributions to preserve: the old G-1/G-3 deferral premises are outdated; early reference coverage is still absent; adapter transformation, vendor basis and reference-basis reliability must stay separate; six identified cash implementations and five exact difference comparisons remain observations, with E-1 discrepant; source/fetch-time homogeneity is only metadata homogeneity; new work and policy adoption remain separate decisions.

## U6-R1 — unsupported rejection and counting of price-basis hypotheses

Locations: sections 3.1–3.3, 3.7 (especially lines 233–235), and the final handoff's “two hypotheses eliminated.”

1. **The sign of vendor minus reference does not exclude hfq.** The reference basis and anchors are themselves unverified. Algebraically, a positive rescaling `V = a P` and a downward rescaling `R = b P`, with `a > 1 > b > 0`, give `V > R`. Thus the observed inequality alone cannot identify which side is unadjusted or exclude a positively rescaled candidate. Remove the purported hfq exclusion. Nonzero differences establish that the retained numerical series differ; they do not prove different adjustment *conventions* or exclude every qfq implementation with another anchor/amount/rounding rule.
2. **H-add/H-mul need explicit conditional assumptions.** For example, the predicted difference shape assumes a specified relationship between the vendor series and the same underlying unadjusted price, a stated cash-only adjustment construction, anchoring and rounding. These are candidate relational models, not established supplier algorithms. Aggregate distinct-value/run counts do not by themselves test constancy *between* event dates. In particular, a rounded multiplicative relation may vary numerically within an event interval. The document proposes that very unresolved test in M-1; do not declare it already refuted elsewhere.
3. **E-4/E-2 are transitions into an observed zero-difference tail, not independently identified anchors.** Equality after a date does not force the preceding gap to equal an independently disclosed dividend amount. That implication requires first assuming the adjustment mechanism being tested. Keep all six identified comparisons and five exact matches; optionally tag the two transitions into the zero tail, but withdraw the “honest scoreboard” of four and the asserted loss of independence. Independence/relative evidentiary weight has not been established for any of these pairs. The extract's actual common anchor is also not demonstrated merely by its end date or by a stored qfq label.

Repair these points as analysis text only. No new fitting or computation is requested.

## U6-R2 — controls and identity observations were promoted into exclusions

Locations: section 3.5 lines 206–211; section 3.6 lines 218–221; section 3.7 lines 245–248; P-4 and Q-5.

- Exact index agreement supports agreement for that tested instrument/path at stored precision. It does **not** rule out stock-specific decode, source, rounding, unit or transport errors, shared errors on both legs, or a different stock code path. Replace the machine-level exclusion/P-4 claim with a bounded control observation. Keep U-7's separation of stocks and index.
- G-g is the missing **legal effective date**, not absence of issuer identity or of exchange-level code continuity. G1 includes official old/new mapping, matching issuer identity and an exchange continuity statement. Separate those established facts from the lack of proof that a particular vendor implemented the mapping correctly. Do not expand G-g into a claim that the issuer's identity/continuity itself is unexplained.
- The collaboration protocol's four non-substitutable states is a governance rule, not a current runtime or source-acceptance finding. If asserting a current acceptance status, cite an actual retained status review; otherwise say that this assessment has no independent certification of the relevant reference basis. “Least independently validated” is an unsupported comparative ranking and should be withdrawn.

## U6-R3 — prerequisite and next-study claims contain invalid implications

Locations: sections 2.2–2.3, 4–6, and alternatives A/B/C/D.

- The proposal's condition 5 is **ratio behaviour** consistent in direction and magnitude, not merely an exact **difference** step. Do not silently replace it. Its satisfaction remains conditional on a defined, supported model and reference basis. Condition 4 is expressly unestablished; E-1 is expressly discrepant. Therefore the blanket claims that 1/2/3/5 are all met, all five are arguably met, and V-13 literally settles the present condition ledger are not supported. Record observations per symbol/span and preserve unknowns.
- “Any rule that counts E-1 as failure declares the vendor basis not unadjusted” is false. A fail-closed rule can decline certification and retain **unverified** without proving the opposite basis. The current contract already requires this distinction.
- A **single mechanism for both instruments/references** is not an existing adopted prerequisite. Heterogeneous reference pipelines could have different transformations while the vendor uses one basis. State this as an exploratory modeling preference if retained, not as a mandatory condition whose failure alone makes every scoped rule impossible. Missing certified reference basis is a sufficient practical reason to withhold certification without inventing new prerequisites.
- M-1: if BJ fits an additive relation and SH fits a multiplicative relation, that does not establish a single common mechanism; it may support heterogeneous reference transformations. If neither *raw stored* ratio nor difference is exactly constant, rounding, unknown actions or misspecified models remain possible. Do not promise to refute both model families outright without a specified rounding/error model, which this task does not authorize.
- M-2/M-3: describe what an additional read of retained numerical evidence could narrow, not unique identification of causes. The named source/instrument/time confound remains unbroken by grouping those same records. A different document's net/gross tax values do not support a net/gross explanation of the E-1 discrepancy, and “only rounding is compatible with an exact-match rule” is not established.
- M-5: earlier dates within one extract are not automatically out-of-sample, and do not supply a second anchoring. A valid holdout requires a design that avoids selection/calibration leakage; changing observation dates is different from obtaining differently anchored snapshots. Remove “the only” route and the claim that an earlier span necessarily reveals multiple anchors. Do not perform or solicit new extraction here.

The assessment can still recommend a bounded retained-artifact follow-up as potentially informative. It must say what would remain unidentifiable and avoid overstating its expected payoff. A categorical universal impossibility proof is not required to conclude that the currently reviewed evidence is insufficient for certification.

## U6-R4 — existing data is not authorization to perform another computation

Location: section 8 rationale (“neither requires an authorization anyone would have to grant”) and the same sentence in the handoff.

This directly conflicts with both this task's express no-recomputation boundary and section 8's own recommendation to authorize the study separately. Replace it with: the candidate study needs no newly acquired data, but **does require a separately scoped authorization for computation and outputs**. No M-1/M-2/M-3 work is authorized by the present task. Distinguish a recommendation for a future user decision from an operational request that has been approved. Also distinguish “proposed reclassification” from an adopted change to U-6; leave the original proposal unchanged.

## Single correction task: U6-DOC-R1-20260909

Revise only `claude methods/M2B_U6_READINESS_ASSESSMENT.md` to address U6-R1 through U6-R4 consistently, including the evidence-to-claim table, prerequisite ledger, recommendation and final handoff. Preserve valid counts, facts and uncertainty. Use explicit conditional hypotheses and a fail-closed/unverified outcome; retain the distinction between insufficient certification evidence and proof that a hypothesis is false. Do not compensate for uncertain claims by adding new prerequisites or demanding exhaustive data.

Read existing accepted artifacts as necessary. No tests, replay, ratio computation, fitting, calibration, supporting scripts/output directories, network, source queries, extracts, SQLite, captures, services/tokens/accounts, production/dataset/strategy/knowledge changes, policy adoption, thresholds/tolerances, code/gates/labels/eligibility changes, training/pilot/source integration, staging/commit/push or live trading. All existing artifacts and reviewer files remain unchanged. Stop at `proposed for review` / `ready_for_review` with the revised document hash and preservation evidence. P1 open, U-6 deferred, all eligibility false, source capability FAIL, both capture authorizations consumed. This is a correction within the already authorized documentation task, not a request to execute the suggested numerical follow-up.
