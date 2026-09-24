# Reference basis lineage — independent review

2026-09-09. **Corrections required**, limited to two substantive findings in `M2B_REFERENCE_BASIS_LINEAGE_AUDIT.md` at SHA-256 `33ca83bcc3398ca84b06c12f50d13d631ccdfeac2d8f1f1eff0d4afe0b00c2c0`. Preserve the useful static trace. This is not source-capability or policy acceptance.

## Verified scope

Codex read the cited source regions as text, checked all eight complete source-file hashes, and independently grouped the retained reference JSON. All seven stock source/timestamp groups and four index groups match the audit (537 versus 538 distinctions in earlier price-pair work are not changed here). All 91 protected pins and all 46 G1 files match, with no G1 additions. HEAD `73f266d`, staging empty. No provider imports, network, SQLite, replay, services or production writes. The reviewed document and JSON verification are frozen under `_m2_codex_review/reference_basis_lineage_review_20260909_r1/`.

The request-derived attributes, cache writer's default, current source-based migration, upsert guard and missing provenance fields are useful findings. Do not repeat numerical studies or reopen their accepted results.

## RL-R1 — current-code implications become unsupported historical and upstream claims

**Priority P1 — audit lines 19–24, 201–205, 232–233, 255–260, 333–339, 419–435 and 455–456.** The matrix correctly distinguishes current code from row history, but the headline and conclusions override that distinction. Examples include “No reference source declares its basis,” “the label's observed uniformity is partly a selection effect,” and the claim that the daily/Tonghuashun retained labels “were not produced” by the migration and therefore originated in the writer path.

What the bytes establish is narrower:

- The inspected current paths assign/preserve labels in the ways described, and no independently verified basis declaration is retained for these reference rows. A parser discarding metadata does not prove the original response had none. Tonghuashun's optional field provides a response-value/request-code comparison; without the host contract or original response it proves neither an echo-only semantic nor that the host did not silently apply another convention.
- The shown migration cannot change `adjustment_mode` on a row whose source **at execution time** is either excluded string. It does not rule out an earlier source value, a different historical migration, another writer, or prove which path generated a retained label. “Not this current branch under these inputs” is not “historical origin established.”
- `ready` filtering combined with the shown stock writer can induce label uniformity **if that writer generated the rows**. The retained rows' historical path is unbound, so the filter's actual contribution to observed uniformity is not established. The observation of uniformity remains valid.
- `ALTER TABLE ... ADD COLUMN` supplies unknown only when that statement succeeds on a schema lacking the column. The code also creates a fresh table with the column already present and ignores duplicate-column errors. Do not assert that the retained database necessarily passed through that migration or that every preexisting row matched D-2's source predicate.

Correct these claims consistently in the headline, local trace, matrix, conclusions and recommendation. Keep the directly evidenced lack of historical binding; do not replace it with the opposite unproved claim. Also scope universal statements such as “no local file can supply” or “not pinned anywhere” to the actual inspected retained evidence; this task did not exhaust every possible local artifact.

**Acceptance:** conclusions are explicitly current-code conditionals or direct properties of named retained bytes. No historical origin, actual selection mechanism or upstream response semantics is asserted from the present source alone.

## RL-R2 — proposed re-extract would not provide the claimed discrimination

**Priority P1 — audit C-4 (line 404) and section 10, especially lines 486–496.** The suggested `created_at`/`updated_at` comparison is presented as discriminating a writer from a bulk migration stamp. The inspected D-2 statement (`sqlite_store.py:1978–1989`) updates **only `adjustment_mode`**, leaving both timestamps unchanged. The ordinary upsert (`daily_bar_cache.py:390–405`) can update a row while preserving `created_at`; a much older creation time therefore also arises without any label migration. Bulk ordinary insertion can create identical timestamps without migration. Additionally `created_at` defaults to SQLite `CURRENT_TIMESTAMP` while this upsert writes naive local `datetime.now()` to `updated_at`; raw timestamp subtraction cannot assume a common clock/timezone. No database was opened to establish its actual historical semantics.

Thus those timestamps alone would not identify whether D-2 ran or establish L-5/L-6. Correct C-4's proposed resolver and section 10; identify a migration/ingestion log or historically bound before/after evidence as the discriminating type. New timestamps could still provide bounded descriptive observations if ever authorized, but do not claim they resolve the path.

Likewise an unfiltered extract could reveal excluded rows and their recorded labels/quality flags; it would not decide whether the true convention was uniform or causally attribute observed uniformity to filtering. Remove that false dichotomy. Do not request or perform a re-extract.

**Acceptance:** next-step recommendations state what an observation can and cannot resolve, and do not sell database access as recovering provenance that those columns cannot contain.

## Consolidated correction assignment

Task `REF-LINEAGE-R1-20260909`. Modify **only** `claude methods/M2B_REFERENCE_BASIS_LINEAGE_AUDIT.md`. Resolve RL-R1 and RL-R2 in one pass; preserve correct source traces, hashes, segment counts and accepted evidence. Read directly relevant code as text as needed; do not create scratch scripts or output directories, import providers, open SQLite or run migrations. Do not execute the next writer-inventory or non-price study yet. No authorization or acknowledgment artifact.

The user already authorized continuous offline correction. No new approval is needed. All operational, data, policy, threshold, training and Git prohibitions remain. Deliver the revised document at `proposed for review` with its hash and preservation evidence. P1 open, U-6 deferred, all eligibility false, source capability FAIL, both capture authorizations consumed. Codex will review the revision and continue useful authorized work; this handoff is not an overall workflow stop.
