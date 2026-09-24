# Turnover dependency assessment — completed delivery review, 2026-09-09

**Verdict: corrections required, bounded to the residuals below.** Claude's completed
handoff and idle sole session were observed. Reviewed document: 1,010 lines, SHA-256
`a0fcbd0529dc513d16826e098aef4c4f8db0171a483c4de1da89a4d9b50a6e3d`.
Frozen in `_m2_codex_review/turnover_dependency_review_20260909_r2/` with verification JSON.

TD-R2 is closed for these bytes: local unit convention, general versus denominator
provenance, numeric-zero fallback, separate score contributions, and conditional design
impact are now adequately distinguished. TD-R1's replay/U4/scaling distinction is also
resolved. Preserve these conclusions; no new broad search or numerical study is needed.

## TD-R1 residual — a writer/schema does not establish database contents

Sections 4, 6.2, 6.5 and 9 still assert "retained nowhere", "such a series does exist",
"a denominator exists in the database" and "a share count is not absent from the database".
The later explicit admission that no rows were inspected does not establish these claims.
Use precise code-level language throughout: an existing schema/writer/reader can store
derived share snapshots; actual rows and coverage are unverified. The inspected Sina
provider path drops its two columns before the cache; no universal storage absence is
proved. This was already required by TD-R1; do not replace it with a different universal
claim. No SQLite or additional data access is needed to correct this.

## TD-R4 — the new as-of precedent reverses the opt-in mode's behavior

Section 6.5's mechanism table says that a snapshot ingested today cannot enter an old
backtest, citing `as_of=None if self._project_fundamentals else current_date`.
That expression actually has two modes:

* Default False: `backtest/engine.py:500-501` supplies current_date, and
  `fundamentals.py:347-358` checks both snapshot as_of and available_at against that cutoff.
* Explicit True: it supplies None. `fundamentals.py:330,350-351` selects the latest row
  without that historical cutoff; the engine's warning at lines 106-110 explicitly says
  that current snapshots are projected onto historical closes and are not point-in-time.
  Labeling this approximation does not make it temporally verified.

Correct the table and the claimed analogy. The retained U4 rule carries a prior observation
forward; this optional projection can carry a later snapshot backwards. They are not
"structurally the same defect", and old denominator age is not proof of a defect at all.
The transferable precedent is explicit modes/provenance, not demonstrated turnover validity
or common temporal behavior. This is a documentation correction, not a production bug
claim or permission to alter either implementation.

## TD-R3 residual — keep the negative result at the actual dependency boundary

Section 7 still escalates zero literal references into "no module imports, opens, reads
... or is configured to reach". Replace that sentence with the bounded searched-token
result and preserve the runtime/configuration limits already stated.

Section 7.1 now identifies relevant files, which is useful. However, a token's absence
in the wrapper cannot prove absence of delegated behavior. `staging_gate.py:526` calls
imported `acceptance_runner.chk_units`, whose lines 188-205 explicitly inspect volume_unit
and amount/volume plausibility. Read and pin that short delegated body, state that unit
checking does exist, and distinguish it from a share-denominator turnover-rate check.
Do not extend the finding to "no M1 gate" beyond the inspected call path. No gate execution
or new corpus search is needed. Do not describe historical M1 document open items as
freshly established present-day status without a current status check.

## Verification and continued scope

All document-table pins verified (see JSON), 91 protected files unchanged, 46 G1 files
unchanged with identical path set. Static source/JSON reads and reviewer snapshots only;
no tests, runtime imports, SQLite, provider/replay/decoder, network, production/data change,
or Git write. HEAD remains `73f266d`, nothing staged. Claude reports its earlier search
workflow stopped; the UI shows a finished response. This is not independent authentication
of every action in that workflow, and no additional workflow is authorized by this review.

P1 remains open, U-6 deferred, every eligibility false, source capability FAIL including
historical EV6; both capture authorizations remain consumed. M2 is not complete.

## English next instruction

Task TURNOVER-FINAL-CORRECTION-20260909. Read this review and resolve only the residual
TD-R1/TD-R3 statements and TD-R4 in ONE concise revision of
`claude methods/M2B_TURNOVER_DEPENDENCY_ASSESSMENT.md`. Keep TD-R2 and the resolved replay
distinction intact. Do the indicated short source reads; no more agents, broad sweeps,
new numerical studies, scratch scripts, output directories or acknowledgment documents.
Use direct text edits. Do not mark reviewer findings closed on Codex's behalf; report
them addressed pending review. Preserve this and earlier review files and all accepted
artifacts. Existing continuous offline authorization is sufficient. All original prohibitions
remain, including SQLite of any kind, data/fixture access, imports/runtime execution,
network/capture/replay/decoder, services, production/schema/data/strategy/knowledge changes,
policy/gate/label/eligibility/threshold changes, training/pilot/backfill and Git actions.
Deliver the sole stable document hash, actual source pins and preservation evidence at
proposed for review. Codex will review and continue within the authorized scope.
