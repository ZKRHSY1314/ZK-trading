# Turnover dependency assessment — bounded technical validation

2026-09-09. **Technically validated within the reviewed static scope.**
Document: `M2B_TURNOVER_DEPENDENCY_ASSESSMENT.md`, revision 3, 1,078 lines,
SHA-256 `50261775464ba24cf5cedfd3bdc4ce002421f7bcf238ba96cc5d9637c3b3a1ec`.
Claude's completed UI handoff names this hash; the sole implementation session was idle.
Snapshot: `_m2_codex_review/turnover_dependency_review_20260909_r3/`.

TD-R1 through TD-R4 are closed for these bytes. The review establishes:

* U4 emits diagnostics, while the adapter replay computed columns whose names, not rate
  values, are retained. Neither proves validated research turnover values.
* The inspected Sina provider drops its share/rate columns; a separate fundamental
  snapshot schema/writer/reader exists. Actual database rows are unverified.
* Quote turnover retains general metadata but lacks denominator provenance. Its percent
  convention is locally expected, not independently verified here. Numeric zero can
  select a raw fallback; optional input can affect scores.
* Default historical resolution applies an as-of cutoff; explicit projection passes None
  and can project later snapshots backwards. Labels do not confer point-in-time validity.
* The inspected M1 wrapper delegates a real amount/volume unit check to chk_units; this
  is distinct from a share-denominator turnover check. Negative searches remain bounded.

Independent verification: 36 document-table pins match; all 91 protected baseline files
and 46 G1 files match, with identical G1 path sets. The diff was reviewed against the
prior frozen delivery and the short relevant source bodies. No runtime tests were needed
for these text corrections; no database, decoder, replay, provider or service was opened
or executed. HEAD `73f266d`, nothing staged. The JSON records the exact checked set; this
does not authenticate every historical action or certify all production behavior.

This is not adoption of used/annotated/withheld policy, user acceptance, source-capability
acceptance, corpus certification or training readiness. P1 open, U-6 deferred, every
eligibility false, source capability FAIL including historical EV6. Both capture grants
remain consumed. M2 is not complete.

## English next instruction

Preserve this assessment and all accepted artifacts. Continue with the bounded amount
representation audit in `_m2_codex_review/amount_representation_dispatch_20260909.txt`.
The next task is static source analysis only and does not authorize any production fix,
policy change, database access or data acquisition.
