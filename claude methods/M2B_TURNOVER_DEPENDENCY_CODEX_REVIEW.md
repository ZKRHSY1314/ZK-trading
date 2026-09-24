# Turnover dependency assessment — Codex interim review, 2026-09-09

Status: **substantive corrections required; interim feedback, not final acceptance**.
Claude was still running the original TURNOVER-DEPENDENCY-20260909 task when inspected.
The 727-line artifact frozen for this review has SHA-256
`58f776853cae5e4d70091eef510ebdc0d62729d9ef07116d4921937c3b6c5aca`.
Earlier in-progress bytes differed; this is not a claim of a completed handoff or a new task.
Snapshot and verification: `_m2_codex_review/turnover_dependency_review_20260909_r1/`.

## Verified scope and useful findings

Static source and retained JSON reads only. No module import, replay, decoder execution,
tests, SQLite, network, services, production mutation or Git write. The 28 listed source
pins match; all 91 protected baseline files and 46 G1 files match, with no G1 additions
or removals. HEAD is `73f266d`, staging is empty. These checks do not authenticate every
past action or establish runtime/database contents.

Preserve the useful separation of retained U4 evidence, adapter-computed rates,
quote-provided turnover_rate and monetary amount. The production Sina provider drops
turnover/outstanding_share before normalization; U4 retains denominator diagnostics rather
than per-session rate values. Long denominator age alone proves neither invalidity nor
freshness. None of these facts adopts a downstream policy.

## TD-R1 — Bound the computation and denominator-storage claims

The headline and sections 4, 6.2, 8 and 9 conflate U4's output with the entire smoke replay
and daily_bar_cache with all production storage.

* `smoke_checks.py:288-328` calls the installed AkShare function and retains frame metadata.
  The reviewed AkShare source computes outstanding_share and turnover at lines 207-208.
  Retained v2 R1 for both stocks reports 978 rows and columns including outstanding_share
  and turnover. This evidences a replay frame with those columns, not validation or
  retention of their individual numeric values. U4's separate as-of interruption logic
  must not be attributed to that adapter calculation. State precisely that U4 emits no
  rate series, rather than that the smoke work never computes any turnover.
* `backend/app/data/fundamentals.py:121` derives total_share_billion from total_cap/price;
  lines 179-225 contain a snapshot writer and reader. The schema at
  `backend/app/storage/sqlite_store.py:1645` includes total_share_billion. Therefore
  "no share count retained anywhere in production storage" and database-wide absence
  conclusions are unsupported by this static audit. Read the units, as-of and provenance
  of this existing route. Its code does **not** establish current rows, historical coverage,
  free-float validity, or equivalence to the retained denominator. Do not open the database
  or propose it as a verified replacement.
* T1 emits no defined/scaled rate. Do not silently give it T2's fraction units in the
  T1-versus-T3 comparison. "New store and writer required" depends on the selected future
  consumer/design, and is not proved by the absence of a daily_bar_cache column.

## TD-R2 — Preserve actual metadata and missing-value effects in the decision matrix

Sections 5.2, 5.4, 8 and 10 overstate provenance absence and understate default effects.

* `auto_discovery.py:244-270` persists source, reasons_json and raw_json alongside
  turnover_rate. `learning_extraction.py:255-271,295-310` retains task/source metadata,
  and the former path also records a signal date. Trace which fields survive each
  relevant hop; generic source/time metadata is not denominator provenance, but it is
  not "no provenance at all" or "nothing to annotate". Withdraw "weaker on every axis"
  and compare supported provenance dimensions without a universal ranking.
* Local percent formatting and thresholds establish the code's expected convention,
  not independent verification of the vendor's unit. Attribute the claim accordingly.
* `scoring.py:184` selects `auto.get("turnover_rate") or raw.get("turnover_rate")`.
  A numeric zero in auto can select a nonzero raw fallback. Only after selection does
  the later `or 0` apply. Describe absent/None/zero/fallback cases separately. Optional
  input means no hard required-field gate; it does not mean no effect on score, ranking
  or downstream outcome. Distinguish the 10.5 turnover-score component from the separate
  auto_priority contribution (up to 15) already cited in the document.
* The matrix cannot assume unwired T1 will enter today's quote scorer, that age is
  established staleness, or that annotation is strictly more costly regardless of
  design. Keep all such consequences conditional; preserve no substitution/no policy
  adoption and the unchanged capability FAIL.

## TD-R3 — Apply coverage limits where conclusions are made; finish the requested gate trace

The headline "nothing reads any M2 smoke output" and repository-wide nonexistence claims
are stronger than the later acknowledged literal-token/tree coverage. Bring the same
bounds into the headline, quantity table and recommendations. A later caveat does not
prove a universal negative. Also complete the original assignment's directly relevant
M1/M2 contract/gate source inspection, which is not identified in this artifact's pins;
give precise searched files/tokens and actual handling, or the bounded negative result.
Reconcile sections 7 and 11's stated search scopes without claiming unperformed searches.

Do the short source traces needed to close these findings in this task. Do not grow this
into a new broad sweep, a new numerical study, or cosmetic follow-up rounds. Additional
learning-producer classification is needed only where it changes this decision analysis.

## English continuation instruction — same active task

Continue TURNOVER-DEPENDENCY-20260909 and incorporate TD-R1 through TD-R3 above in one
consolidated revision of ONLY `claude methods/M2B_TURNOVER_DEPENDENCY_ASSESSMENT.md`.
This is interim feedback while you finish the original task, not a duplicate task or
new operational authorization. Read this review in full. Use current source text and
the already-authorized retained JSON/documents; keep this review and every accepted
artifact unchanged. Finish relevant short traces now and deliver a concise stable handoff
with the sole document hash, source pins and preservation evidence. Do not launch more
agent workflows or broaden the sweep just to prolong offline work.

No scratch scripts/output directories, datasets/fixtures, SQLite of any kind, provider or
service imports, network/retrieval/capture, replay/decoder execution, production/schema/data
or strategy/knowledge mutation, policy/gate/label/eligibility/threshold changes, training,
pilot/backfill, Git staging/commit/push or trading. No additional approval or acknowledgment
artifact. P1 open; U-6 deferred; all eligibility false; source capability FAIL including
historical EV6; both capture authorizations consumed. Stop at proposed for review for Codex
inspection; continuous authorized coordination remains active.
