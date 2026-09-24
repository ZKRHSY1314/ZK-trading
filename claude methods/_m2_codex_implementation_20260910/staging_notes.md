# Tonghuashun isolated staging API

`staging.py` creates a new candidate pair and publishes only a pointer below this phase's `staging_runs/` directory. It never opens a production database, enables trading, establishes credentials, contacts a server, or promotes a candidate to production. Existing candidates, source evidence and historical M1/M2 files are not overwritten.

The immutable pilot contract is 50 stocks and two benchmarks, 36,193 research rows plus 9,742 warmup rows, or **45,935 rows per view**. The writer derives every expected key from the exact pinned manifest and calendar. It refuses missing keys, duplicate keys, extra keys, bad dates or altered population/window pins. The two benchmark identities remain canonical `SH000300` and `SH000001`, with separate native/public source identifiers preserved in raw evidence.

## Construction and staging

```python
run = StagingRun(
    HERE / "staging_runs" / "pilot_qualified_20260910", "candidate_001",
    manifest_path=M1 / "pilot_symbols.csv", calendar_path=calendar,
    expected_manifest_sha256=MANIFEST_PIN,
    expected_calendar_sha256=CALENDAR_PIN,
    producer_files={
        "qualification_rules": (rules_path, rules_sha),
        "history_parser": (PARSER, parser_sha),
        "plugin": (plugin_dll_path, plugin_sha),
        "collector_qualification": (original_capture_path, original_capture_sha),
        "collector_pilot": (remaining_capture_path, remaining_capture_sha),
    },
    evidence_files={sha256_of_exact_bytes: retained_file_path, ...},
)
candidate = run.stage_from_evidence(qualification_bundle_sha256)
```

The original qualification collector must still have the pinned bytes. If it has changed, use its retained original copy as the producer file and ensure the corresponding producer manifest binds that path; do not silently repin historical capture code. The collector match currently requires the exact path-and-hash pair from its retained `producer_pins.json` inventory. A separate `collector_sha256` in each scope selects the relevant producer when more than one collector matches.

`stage_from_evidence` first reconstructs each raw point through the pinned pure history parser. It does not accept rows stamped with a basis inferred from `adjustment=0`. Qualification must already exist in a separately retained and pinned `m2.ths.qualification_evidence.v1` JSON artifact with an exact scope for each of the 52 symbols. Its `instrument_class` must match the frozen manifest. Stocks require `vendor_basis_status`, `unit_status` and `identity_status` equal to `verified`. Only the two frozen benchmarks require `unit_status="not_applicable"`, with both volume and amount units also `not_applicable`; their basis and identity still must be verified. Calling a stock a benchmark cannot bypass its unit checks. Every scope also requires a raw basis of `unadjusted`, reviewed evidence references, matching rule/plugin hashes, the exact window/period/adjustment, the body hash, capture receipt hash, and capture producer-manifest hash. Missing qualification remains an error before database creation.

`request_sha256` in this API is the SHA-256 of canonical UTF-8 JSON for `capture_receipt.job.payload`, using sorted keys, compact separators, `ensure_ascii=False` and `allow_nan=False`. It is deliberately distinct from a collector's optional byte hash of a pretty-printed `request_N.json`. The exact captured receipt bytes are independently pinned. The receipt must bind the same body, canonical symbol, native identifier, successful HTTP result and observation timestamp. Requests must have one security identifier, adjustment 0, period 7, limit 5000 and the full frozen date interval.

For callers that already hold normalized records, `records_from_evidence(bundle_sha)` returns records with `symbol`, `trade_date`, OHLCVA, `source="tonghuashun"`, raw/request/receipt/producer-manifest hashes, collector `producer_sha256`, `parser_sha256`, `observed_at`, and original `point_index`. `stage(records, bundle_sha)` rechecks every record against that exact raw point. A caller cannot substitute a symbol, date, value, observation time or row index merely by retaining an unrelated valid body in the inventory. Source names are independently marked invalid or missing; manifest names in the instrument catalog are not represented as names observed from the source.

Raw captures currently must exactly match the listing-aware eligible date set. A body containing pre-listing observations is retained but rejected by this writer; no hidden filtering occurs.

## Run A, Run B and publication

```python
receipts = [run.validate(mode,
    archive_trading=isolated_archive_trading,
    archive_history=isolated_archive_history,
    baseline=isolated_frozen_archive_baseline) for mode in MODES]
result = run.publish(receipts)
```

Validation archives and baseline must be retained within this new phase and distinct from each other and the new candidate databases. Validation executes the unchanged M1 gate in its read-only mode, then the unchanged M2 acceptance parser. The research receipt requires all required gates. The warmup receipt permits only the original exact 14-symbol V3b listing-depth shortfall. An exit code of 1 is not sufficient evidence of an acceptable Run B.

Receipts are issued only by the validation call for this run, bound to candidate, input and archive/baseline hashes, and written with their gate output. Publication requires both genuine receipt objects and verifies the receipt-file hashes again. Fabricated receipt copies, receipts from another run, changed candidates, changed inputs, changed archives or edited receipt artifacts cannot publish through this API. `CURRENT.json` is replaced at one atomic publication point; an exception preserves the prior pointer and retains the failed candidate for inspection. Run-local temporary-pointer cleanup cannot delete unrelated files. This is staging publication and does not establish strict point-in-time identity or production readiness.

## Offline verification boundary

`test_staging.py` synthesizes the complete 45,935-row population from the unchanged manifest/calendar and executes the real M1 gates. Synthetic evidence requires explicit `evidence_mode="synthetic_test_only"` and an isolated root whose name begins `synthetic_test_`. Its metadata and pointer remain visibly synthetic; the default retained-market mode rejects those qualification artifacts. Tests never open the production databases or import application startup.

The suite checks actual A/B gate behavior, row-lineage substitution, qualification status and scope, duplicate/missing keys, request-window and identifier errors, collector-manifest binding, receipt forgery/cross-run reuse, receipt/candidate/evidence tampering, archive aliasing and atomic replacement failure. A contradictory synthetic amount/volume observation passes structural staging but is rejected by the unchanged P4 gate, demonstrating that an external qualification claim cannot override required validation.

The saved test output is `test_staging_result.txt`. Synthetic success proves the staging machinery and its rejection paths; it does not qualify any actual captured market data or complete M2.

After the explicit benchmark applicability correction, two focused tests passed in 3.593 seconds: `test_only_frozen_benchmarks_can_use_unit_not_applicable` and `test_unverified_and_wrongly_scoped_qualifications_fail_closed`. These check the accepted benchmark branch and eight targeted attempts to bypass stock-unit, benchmark-identity or price-basis requirements. They inspect qualification artifacts without creating an actual staging candidate. The earlier saved full-suite output predates this correction and remains unchanged.
