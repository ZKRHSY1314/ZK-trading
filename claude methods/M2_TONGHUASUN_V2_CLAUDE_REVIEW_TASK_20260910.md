# M2-THS-V2-INDEPENDENT-REVIEW-20260910

Owner for this task: Claude, in the existing **ZK-trading / Fable 5.1 project advice (fork)** session. Codex remains coordinator/integration owner. Do not start another agent, session, scheduler or email workflow.

The actual user has now requested: finish this step, write an acceptance document, resume delegated Claude work, and patrol every 15 minutes until M2 is complete. This supersedes the temporary no-Claude instruction. Earlier no-capture/no-database status paragraphs describe earlier stages; use the precise current scope below. Do not infer permission for production operations from this delegation.

## Read first and inspect actual state

Read AGENTS.md, CODEX_CLAUDE_COLLABORATION.md, the complete M2 definition and relevant current scope in `claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md`, then:

- `claude methods/M2_TONGHUASUN_V2_CODEX_ACCEPTANCE_20260910.md` in full.
- `claude methods/_m2_codex_implementation_20260910/v2_delivery_manifest.json` and its pinned artifacts.
- `acceptance_v2_authority.json`, the immutable `M2_ACCEPTANCE_REVISION_PROPOSAL.md`, `qualification_v2_reviewed.json`, `contract_v2.py`, `staging_v2.py`, `run_staging_v2.py`, and `verify_preservation_v2.py` in that phase directory.

The exact successful run is `ths_v2_20260910_041710_97ef9c09`. The two candidate files live under phase `staging_runs/<run-id>/run_<run-id>/`, and execution receipts under phase `contract_v2_runs/<run-id>/`. The pointer SHA is `a3d7b37b2315643970b983dedc8fa814d56219c63df350f382b9a60b0b163b35`; qualification SHA is `992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37`. Verify full hashes before using them.

## Concrete task

Independently review this actual retained Tonghuashun corpus and the complete M2 acceptance boundary. The goal is to finish the outstanding substantive verification, identify any actual blocker, and give Codex an executable closure/fix list in the same delivery. Do not respond with another request to draft a plan or with test counts alone.

1. Verify 52 identity mappings, the fixed research population/window, the 500-adapter-vs-native-interface distinction, and unadjusted basis/unit qualification. Replay relevant retained evidence independently, without changing its producers or old results. Do not use copied flags such as `scope_evidence_verified=True` as evidence by themselves.
2. Audit the 298 suspension records against retained issuer documents and the separately described exchange DOM observation, including start/resumption boundaries and the one ongoing interval. Date expectations must be derived from calendar/listings and verified suspension facts. A missing vendor row does not prove suspension. Check 48 added warmup rows, all overlap comparisons, both stores' exact price/suspension partition, and all 14 frozen listing-depth shortfalls. Unknowns may not disappear through set construction.
3. Specifically assess BJ920006 / 2023-12-04: the BSE PDF original bytes/page 12, source Volume/Turnover interpretation, official observed 837006 block record and old/new code mapping, exact volume/amount units and residual arithmetic, and unchanged raw totals. Determine whether the evidence justifies the v2 scope rule, separating a source interpretation from a direct vendor specification and mere arithmetic consistency. Report insufficient evidence candidly if applicable; do not waive P4 or fit a new tolerance.
4. Independently query ONLY the two published candidate SQLite files using explicit `mode=ro` and query-only connections; these read-only opens are authorized for this review. Check all OHLCVA, business keys, basis, source/availability timestamps, capture receipts/producer pins, both stores and materialized ledgers/views. Review write-path guards, input/pointer/receipt binding, atomic publication, protected path aliases, and fail-closed tests. Byte-read the production preservation receipts; do not open any production database. Optional isolated synthetic test DBs may be created only in your new review directory, using fresh filenames and no production imports.
5. Verify the original gate files and actual FAIL outputs remain intact. New research should pass integrity; new warmup should still fail V3b for exactly 14 listed-history shortfalls while collected-data integrity passes. Do not call this feature readiness, strict PIT, M3 readiness, or production promotion. Audit the 45,685 invalid raw source-name diagnostics and whether code-based identity prevents misuse.
6. Map each M2 acceptance criterion to actual proof. Explicitly decide whether the user-approved 52-security staging corpus satisfies this M2 delivery or whether a pre-existing unmet requirement remains; quote exact authoritative scope evidence rather than inventing a reduced or expanded definition. Preserve old Sina EV6 FAIL and unresolved nonrequired downstream capabilities separately.

## Write scope and delivery

Only create:

- `claude methods/M2_TONGHUASUN_V2_CLAUDE_INDEPENDENT_REVIEW_20260910.md`
- A new directory `claude methods/_m2_ths_v2_claude_review_20260910/` containing your own review scripts, isolated synthetic fixtures if needed, test output, row-level audit findings and a manifest of input/output hashes.

Everything else is read-only for this task, including Codex code/qualification files, all raw captures, old gates, official documents, both actual candidate databases, their CURRENT pointer, production databases/sidecars, historical accepted datasets, knowledge files and coordination JSON. Do not execute `--execute`, `--test-tamper`, collectors or old builders that rewrite retained outputs. Inspect entrypoints before running anything. No network/capture, client/login/token/account access, service operation, production write/promotion, threshold/policy change, training, live trading, Git staging/commit/push, or worker dispatch.

Use the project Python venv for pure offline checks and SQLite reads. Bundled PDF tools are available for retained PDFs. No dependency installation or broad backend application imports.

Report: verdict (`PASS`, `CORRECTIONS_REQUIRED`, or evidence-blocked), source/evidence confidence separately from code/test results, per-criterion proof, full hashes and exact commands actually run, all substantive findings with file/line and reproducer, whether M2 can close under the approved scope, and concrete minimal corrections if it cannot. Do not manufacture an independent reviewer result for work you did not perform. Do not ask permission for the bounded offline analysis or authorized read-only candidate queries above.

If a blocker needs implementation, deliver the review and specific fix requirements now; Codex will integrate or issue a separate exact write scope. Do not edit frozen producers in place or silently publish a replacement candidate. Do not spend rounds on style-only observations. Codex will inspect every 15 minutes and continue substantive closure work until M2 is actually complete.
