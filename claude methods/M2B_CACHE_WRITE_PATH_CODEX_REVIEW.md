# Cache write-path audit — independent review

2026-09-09. **Corrections required** for `M2B_CACHE_WRITE_PATH_AUDIT.md` at `1dbfb9af429a54a38cfdb6bd03cddc28663ff47d9a465b8c2d33d2527620cdb9`.

**The previous lineage audit is now technically validated within its static-source scope**, at `155207ffcee956a5a582bb993ef315a56345c7a854637c007f178ec0bf3ded92`. Its diff contains exactly the two requested section-10 corrections. **RL-R1 and RL-R2 are closed for that hash.** Do not edit or reopen that document again for the findings below. This validates neither a historical row origin nor a price basis or source capability.

Codex inspected the write audit, direct source regions and prior-lineage diff. All 15 cited source hashes, 91 protected file pins and all 46 G1 files match; no G1 additions. HEAD `73f266d`, staging empty. Reviewed documents and JSON verification are frozen in `_m2_codex_review/cache_write_paths_review_20260909_r1/`. No SQLite, provider imports, service calls, network, tests or dataset reads were used by Codex. Correctly identified facts include the local nature of the upsert predicate, deletion-before-insert sequencing, current incomplete-session date bounds, and the demo replacement's omission of basis/unit columns. Preserve those facts, with their existing conditional limits.

## CW-R1 — execution surface and caller map are not accurately bounded

**P1 — sections 4 and 7.** `SQLiteStore.fetch_all` and `fetch_one` (`sqlite_store.py:2044–2051`) are not enforced read-only APIs. They pass the supplied SQL directly to `conn.execute` on the writable connection, without a SELECT check or query-only mode. Calling `fetchall`/`fetchone` after execution does not make the preceding SQL read-only. The statement that the store exposes no generic write helper therefore misses these two generic execution surfaces. Do not execute a demonstration; the source is sufficient. Distinguish intended/read-only uses found at call sites from capabilities of the helper itself. The inventory need not enumerate every caller, but its limitation must cover these surfaces as well as direct `connect()`.

Two concrete activation/caller corrections belong in the same matrix:

- W-1 lists `refresh_benchmark_bars` as a `_upsert_bar` caller. In the current file that refresh calls **`_upsert_bars` at line 366**. `_save_error_bar` calls `_upsert_bar` at line 539. Therefore real index refreshes also traverse W-2 and its deletion logic, not the single-row path shown. Trace both actual call sites and correct the W-1/W-2 labels.
- W-9 correctly notes the Python function `import_all(reset=True)` default, but omits the CLI's different effective default. `main()` defines `--reset` with `action="store_true"` and passes `reset=args.reset` explicitly (`import_legacy_data.py:762–772`). Ordinary CLI invocation therefore does **not** inherit `True`; distinguish explicit `--reset`, direct Python calls omitting the argument, and other verified callers. Do not imply the importer resets by default in every entry mode.

Acceptance: the operation matrix identifies actual callers and entry-mode conditions, and generic SQL helpers are not represented as a safety boundary.

## CW-R2 — a coarse durable import record is overlooked, and evidence exhaustion is overstated

**P1 — W-9/W-10 Record cells and sections 8/10.** The importer executes `INSERT INTO import_runs(source_dir, status, summary_json)` at **`import_legacy_data.py:743–750`**, inside the import transaction. The DDL at `sqlite_store.py:27–33` adds `created_at`. Thus “every path records nothing” / uniformly no durable ingestion event is inaccurate for a successful importer run. Conversely, this is **not** per-row price-basis provenance: trace what the summary actually contains and what it omits, including whether it records `reset`, affected cache keys, invocation/code pins, or source-response metadata. A coarse run record does not prove W-10 wrote rows, establish migration execution, or close L-5/L-6. Note that `reset_knowledge()` uses its own connection before the import block; do not assume the later record proves or transactionally covers the reset. Read source only; do not inspect the database or fabricate a record.

Replace the opening section-10 claims “No further existing-file task would add evidence” and “every remaining question needs evidence that no local file contains” with the actual bounded conclusion: this search has not identified a further concrete existing-file source that resolves the historical binding, and the reviewed artifacts lack the required link. The audit itself says uninspected files may exist; it cannot prove the universal negative or decide that the overall M2 workflow must stop. Keep any remaining evidence proposal discriminating and scope-specific.

Also make the headline's counting unit explicit: W-1–W-10 includes DDL and an indirect wrapper, and W-2a/b/c adds grouped statements. “Two of ten paths protected” must not look like a quantitative coverage measure across independent mutation statements. Use named groups or omit the ratio; preserve all actual predicates.

Acceptance: distinguish a coarse import-run record from missing per-row historical binding, and avoid claiming every possible local evidence source is exhausted.

## CW-R3 — fixture read scope and activation evidence contradict the handoff

**P2 — section 4 W-10 paragraph and section 7 item 5.** The audit says `demo_seed.json` contains a particular key, checked by “key presence only,” while also claiming its contents were not read and no dataset was opened. Establishing key presence from that file consumes content; filesystem existence/size cannot establish a JSON key. The assignment was static source analysis and expressly said not to read raw legacy input datasets. No additional fixture read is necessary or authorized by this correction.

Accurately disclose the operation already used, from your existing command history: whether the fixture was opened/read, whether only a textual key match or parsed structure was tested, and what was actually observed. Do not re-open the fixture to clarify it, create a receipt, or silently erase the disclosure. Distinguish a fixture read from reading the private legacy corpus, rather than claiming neither occurred. If content was accessed outside the assigned source-only scope, record that limited departure plainly; this review does not retroactively authorize it.

Do not infer an actual W-10 INSERT from file existence plus a key: the outer array or inner `bars` collection may be empty, malformed or the earlier import may fail. State the code's necessary activation predicates without inventing actual values. No symbols/dates/price contents need to be read or reported.

Acceptance: read scope is internally consistent and the demonstrated observation is not stronger than the operation used.

## Consolidated correction assignment

Task **CACHE-WRITE-R1-20260909**. Modify **only** `claude methods/M2B_CACHE_WRITE_PATH_AUDIT.md`. Resolve CW-R1–CW-R3 in one concise correction; avoid an extended apology/change-history appendix. Preserve verified source traces, the now-validated lineage audit, all retained artifacts and reviewer files. Read directly relevant source as text only; inspect your already available command history for CW-R3 without another fixture read. Do not create scripts, output directories, receipts or acknowledgment artifacts.

No SQLite of any kind, module imports, network/retrieval/capture/replay/decoder, services, importer/migration execution, raw fixture/legacy datasets, production/data/strategy/knowledge mutation, policy/gate/label/eligibility changes, threshold calibration, pilot/backfill/training, source expansion, Git staging/commit/push or live trading. Existing offline correction authorization is sufficient; no user approval question. Deliver the revised sole document hash and preservation evidence at `proposed for review`. P1 open, U-6 deferred, all eligibility false, source capability FAIL, both capture authorizations consumed. Codex will independently review and decide the next useful authorized task; this implementation handoff is not an overall pause.
