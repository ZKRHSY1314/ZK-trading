# M1 independent review — Codex, 2026-09-06

Verdict: **not yet technically validated**. The core diagnosis is substantiated, but the data contract and executable handoff need one bounded closure pass. This is not a request to repair production data or restart the audit. M0 remains validated. M2 remains unauthorized.

## Independently verified evidence

Used the data-quality review workflow: reconcile grains/denominators, separate observations from causal claims, and test whether proposed gates actually detect bad inputs.

Stdlib-only queries used explicit `mode=ro` connections, `query_only=ON`, and a read transaction against both production databases. No application constructors, migrations, network calls, service startup, commits, or pushes were used.

| Check | Codex result |
|---|---|
| Local calendar file | 728 nominal-window sessions; 141 head-gap sessions; 536 dense-period sessions |
| Pricing cache | 2,891,616 date-shaped rows; 587 distinct dates; first date 2024-04-09 |
| Research store | 2,787,736 rows; 586 distinct dates; last date 2026-09-03 |
| Missing head / pre-window warm-up | Zero rows in both stores |
| Coverage manifest | Calendar denominators match for 5,543 computable securities; median 73.6264% |
| Already listed at window start | 5,167 securities; best coverage 73.9011%; none reaches 95% |
| Price disagreement | 1,059,744 / 2,787,736 common keys differ by more than 0.005 |
| Known anomalies | 3 OHLC relation violations; 1 malformed date; 482 malformed-symbol rows |
| Unit warning | 293 near-100x volume drops at 6,243 source boundaries; 19 among nonboundary pairs |
| Tencent population | 306,543 rows / 4,946 symbols, all missing amount; not all individually proven to have wrong units |
| Historical universe | 5,561 instruments; no delist dates; only 7 snapshot dates |
| Legacy evidence | 20,082 decisions / 18,682 outcomes / 746 evaluations / 1 claim; policy column absent |
| Old backtests | 39 runs, all cash unchanged; zero trade rows |

The main database files and existing WAL had identical sizes/mtime values before and after this review. This supports the no-write review boundary; it is not a claim that all historical operations were audited. Current index is empty; HEAD remains `73f266d`; no listeners were observed on 8000/3000.

Reproducer: `claude methods/_m1_codex_review/review_m1.py`. Output: `claude methods/_m1_codex_review/observed_results.jsonl`. The first invocation failed on my assumption that `trade_count` was a physical run-table column; I corrected the reviewer query to count the actual trade table. The corrected production query pass and the separate in-memory gate probes both exited 0. No backend regression suite was rerun: this milestone changes audit artifacts, not runtime code.

## Four closure requirements

### R1 — Do not manufacture historical availability

Location: `M1_THREE_YEAR_DATA_READINESS.md:583-588` (T1/T2).

T1 assigns `available_at = trade-date close + assumed lag` to the row's content, and T2 admits it solely by `available_at <= cutoff`. A 2024 bar revised with a 2026 adjustment vintage would therefore pass a 2024 cutoff after its availability is backdated. Recording `factor_vintage` without filtering/handling it does not close this hole.

Separate event time, assumed publication time, observed/source-version availability, and ingestion time. Preserve unknowns and declare an availability basis. A same-day-close assumption is not observed historical provenance. Strict PIT admission must account for the bar version and every factor/corporate-action input used; otherwise label the dataset exploratory and fail closed for official PIT claims. A fixed-vintage adjusted series can be reproducible without being proven historically available. Forward outcome labels remain legitimate after maturity.

Deliver two small temporal contract examples: a genuinely available historical version is eligible; a later revision cannot become eligible merely by receiving an old trade date. Do not alter production timestamps.

### R2 — Reconcile both coverage artifacts and the executable source

Locations: `coverage_manifest.csv:6`, `coverage_gap_shape.csv:2`, `coverage_05_manifest.py:134`.

There are **5,286 denominator disagreements** between the two delivered CSVs. For BJ920000, the manifest reports 728 eligible / 501 observed, but the gap table reports 587 eligible / 501 observed / 86 missing. Under the declared calendar, 227 sessions are absent: the gap table omits the entire 141-session head gap. The supplied manifest generator still writes the old spine-based schema; running it would overwrite the corrected artifact.

Generate coverage and gap shape from one versioned, explicitly selected calendar and listing interval. Make observed + leading + interior + trailing equal eligible for each computable security, with separate unclassified/excluded records. Keep missing suspension/delist evidence unknown rather than inventing reasons. Retain any observed-spine diagnostics in explicitly named columns, not as the nominal denominator. Include zero-observation and unknown-listing securities in the audit inventory.

Consolidate the report's operative tables and gates to the corrected numbers. A corrections preamble does not make conflicting execution instructions safe. Pin the calendar file hash. Also correct the runtime-source claim: the installed `tool_trade_date_hist_sina()` performs an HTTP request; it does not read `calendar.json`. The local file is an offline audit reference, not proof of the calendar used by a historical runtime.

### R3 — Make the acceptance suite capable of failing

Locations: `backfill_acceptance.sql:116-172`, `backfill_acceptance_BEFORE.json`, report Section 9.6.

- The frozen JSON still contains only A1-A9, not the newly claimed V baselines. V4 and V6 remain absent from the SQL. The N identifiers also differ between report and SQL. Provide one keyed runner/registry with database routing, query, denominator, threshold, baseline, and PASS/FAIL/UNKNOWN status; missing evidence must not pass.
- I ran the delivered V2/V3 queries on an in-memory fixture containing `2025-02-30` and `XX123456`. Both reported zero violations. Shape matching does not validate calendar dates, trading sessions, or an SH/SZ/BJ stock namespace.
- V5b reports zero boundary violations on a single-source fixture even when the declared unit is deliberately wrong. Removing provider boundaries is not unit verification. Use independently evidenced provider units and comparable raw-price/amount units, or quarantine the unknown population. Do not compare raw CNY amount to adjusted prices without handling the adjustment basis. Do not divide all Tencent rows by 100 solely because some boundaries look suspicious.
- V7's row count/date range cannot prove preservation of prior values. Use a stable content/file fingerprint of the consistent archived snapshot, plus integrity checks. Preserving the same number of rows is insufficient.
- G5 must detect invalid run references, not just NULL IDs. Global date counts cannot substitute for eligible per-symbol coverage. Distinguish zero sampled rows from a passing quality check.

Add a bounded synthetic gate test set: impossible date, unsupported symbol, missing/nonpositive price, same-source wrong/unknown unit, missing provenance/run reference, altered archive values with unchanged row count, and clean controls. These tests belong only to the local audit artifacts for this closure.

### R4 — Deliver one safe, stage-aligned M2 proposal

Locations: report Sections 9.3-9.6 and 10.2, especially lines 824-836.

The recommended rebuild spans 2025 while N2 requires its values unchanged; the text acknowledges a separate intentional-rewrite approval but does not supply the corresponding final gate. The proposed schema/version contract appears after ingestion and promotion. The 5,561-stock request estimate does not include the separately missing benchmark, and pre-window warm-up is deferred despite the three-year objective.

Provide one coherent proposal, not another implementation pass:

1. Contract and acceptance harness first; all data writes remain staging-only after user authorization.
2. Propose a stratified 50-stock pilot plus the benchmark, with an exact symbol list, date range, source, request/depth limits and units/vintage checks. Include IPO, BJ/code-history, suspected unit-switch and ordinary controls. Verify measured capability before promising one request per symbol or fixed runtime.
3. Keep the research interval 2023-09-04..2026-09-04. State the proposed maximum feature lookback separately. The pinned local calendar gives **2022-08-24** for 250 preceding sessions. This is a planning option, not approval of a new feature specification or download.
4. Full staged rebuild follows pilot review and separate authorization. Distinguish preserved original/archive hashes from intentionally changed staged prices; preserve unrelated tables and document exact intended rewrites. Align all G/N/V identifiers and thresholds. The 90% per-symbol pilot diagnostic is not the project's final 95% coverage criterion.
5. Production promotion remains a separate stop gate after independent staging validation. Account for SQLite WAL, stopped writers, both database versions, partial two-file promotion and recoverable rollback. Two renames are not one cross-file atomic transaction. Preserve the original vintages; do not repair them in place first.

Include unknown historical universe/ST/suspension/code-history coverage as explicit limitations. Do not buy data or silently narrow the research population. A2 remains a separate prerequisite for official persisted evaluation consumers, not an unannounced part of backfill.

## Narrow wording corrections, not new audit work

- 7.43% versus 7.46% is not a NULL explanation: my query found zero NULL cache closes among the common keys. Using cache close as relative denominator gives 207,159; using history close gives 207,835, or 207,831 after ready+qfq filtering. The 40-key difference is the quality/adjustment filter. Name the denominator explicitly.
- Snapshot removals prove observed membership changes, not certified legal delist dates. Keep the event interval and source limitation.
- The old leakage probe does not establish the claimed 74.7% future-information usage. Nor does a same-rate control or a zero future-trade-date probe prove absence of revised-value leakage. Use `unsupported by this probe`, not a blanket clean bill of health.
- Zero trades and absent input snapshots mean the old runs are not performance evidence and reproducibility is unproven. Timestamp order alone does not prove reproducing the same numerical result is impossible. Do not delete or reclassify those records.

## Next instruction to Claude

Complete R1-R4 in a single bounded **M1 closure** pass using the existing evidence. Do not launch another broad multi-agent audit or generate hundreds of overlapping scripts. Use one report, one coverage/gap generator, and one acceptance runner with synthetic tests. Preserve the original evidence as historical, superseded material.

Write only local, uncommitted audit artifacts under `claude methods/` and your progress-ledger entry. Do not change runtime code, datasets, methodology/strategy sets, knowledge files, production databases, or the reviewed M0 candidate. No network/plugin calls, pilot downloads, services, commits or pushes. Stop at `ready_for_review`, linking each requirement to its artifact and test result. Codex will review the closure; the user then authorizes any M2 pilot. Poor data quality itself is not a reason to keep M1 open once its diagnosis and execution contract are sound.
