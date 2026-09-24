# Historical market research database

`market_history.sqlite3` is an independent SQLite database for historical market-data
research and training-dataset provenance. It is deliberately separate from
`trading_local.sqlite3`, which remains the running application's operational database.

The history database is research-only:

- `research_only=true` and `live_trading_enabled=false` are stored in schema metadata.
- Ingest runs and training manifests enforce the same flags with SQLite checks.
- The schema has no broker, credential, account, position, order, fill, or cancellation
  capability.
- Initialization never copies or backfills data from the operational database.

## Safe initialization

Run commands from `backend`:

```powershell
.\.venv\Scripts\python.exe scripts\init_market_history.py
```

The default command is a read-only inspection. If the database does not exist, it prints
the planned schema as JSON and creates no file. Explicitly initialize it with:

```powershell
.\.venv\Scripts\python.exe scripts\init_market_history.py --apply
```

Both commands default to the project-root `market_history.sqlite3`. The existing
`*.sqlite3` and `*.sqlite3-*` ignore rules keep the database, WAL, and shared-memory
files out of Git. Passing the configured `trading_local.sqlite3` path is rejected before
SQLite opens the file.

Initialization is idempotent and configures WAL, a 5-second busy timeout, foreign-key
enforcement, and schema version 1. It creates schema only; it does not run a market-data
provider or a historical backfill.

## Schema responsibilities

- `instruments`: stable symbol identity and listing metadata.
- `universe_snapshots` and `universe_members`: point-in-time universe membership, so
  research does not silently use today's constituents for old dates.
- `ingest_runs`: provider, adjustment mode, status, counts, parameters, and errors for
  each bounded ingest.
- `daily_bars`: OHLCV and amount keyed by
  `(symbol, trade_date, adjustment_mode)`, with provider, fetch time, ingest run, and
  row hash provenance.
- `bar_quality_issues`: appendable data-quality findings and resolution timestamps.
- `training_dataset_manifests`: immutable-by-convention dataset recipes, feature/label
  schemas, splits, source date range, source hash, and optional artifact reference.

Every daily bar must declare its adjustment mode. `volume_unit` is limited to `hand`,
`share`, or `unknown` and defaults to `unknown`; provider adapters must not guess a unit.
`rule_regime` is nullable so a later ingest can explicitly separate observations before
and after a market-rule boundary such as 2026-07-06 without rewriting source data.

## Current role and full-market expansion

Keep `daily_bar_cache` in the operational database for current screening and runtime
readiness. Full-market refresh discovers Shanghai main board, STAR, Shenzhen A shares,
and Beijing Exchange independently, so one failing exchange endpoint cannot erase healthy
markets. The apply path is bounded, resumable, and defaults to Tencent qfq first; a failing
Eastmoney proxy therefore cannot stall every stock. `--max-workers` is clamped to 1-20.

### Optional local Tonghuashun candle source

The operational cache can use the third-party `tonghuasun-codex` local service as a
read-only first source. The project adapter is deliberately narrower than the plugin: it
calls only the exact loopback REST path `/api/v2/quotes/candle`, rejects redirects and
non-loopback endpoints, reads the plugin-owned token only at runtime, and exposes no
account, position, order, cancellation, credential, or trading operation. It writes
validated candles through the existing `DailyBarCacheService`; it does not create a
parallel score or selection path.

The default remains `akshare_first` until the installed local client passes a real-sample
review. Inspect configuration without revealing the token or contacting an account API:

The project startup profile now pins the reviewed local product directory without
enabling Tonghuashun-first ingestion. See `docs/TONGHUASUN_COMPARISON.md` for the
read-only launcher, measured retrieval timings, remaining adjustment differences,
and why no history/cache writes were enabled by this integration.

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/data/tonghuasun/status"
```

After confirming the local listener, validate a small read-only candle sample and check
that dates use the Shanghai session, prices are qfq, and `transaction_amount` is populated
in yuan. Then opt in explicitly for an applied cache refresh:

```powershell
$env:DAILY_BAR_SOURCE_POLICY = "tonghuasun_first"
.\.venv\Scripts\python.exe scripts\backfill_market_universe.py --apply `
  --days 120 --batch-size 20 --source-policy tonghuasun_first --max-workers 2
```

`tonghuasun_first` falls back to the existing public providers; `tonghuasun_only` is for
bounded diagnostics. A missing amount, invalid OHLC, mismatched security, non-finite value,
wrong echoed adjustment mode, or conflicting duplicate date rejects the local response.
Amount is never estimated as price times volume. Keep both upstream trading switches off;
the project does not depend on or import the plugin's broader MCP account/trading surface.

Tencent `qfqday` rows are stored as `adjustment_mode=qfq`. If the primary bounded
`fqkline` request fails or returns only raw `day`, the adapter makes one bounded request to
the same provider's `newfqkline` endpoint. That fallback is accepted only when the response
itself contains a `qfqday` array and is persisted with the distinct provider provenance
`tencent.newfqkline.qfq`. A response containing only raw `day` rows is never promoted to
qfq: primary raw rows remain `adjustment_mode=none` with
`quality_status=review_only_unadjusted`, while an unproven fallback response is rejected.
Both Tencent paths are capped at 500 requested bars. Amount is never fabricated, and an
amount-less fallback cannot overwrite an existing ready row that already has amount data.

There is one exact unit-factor exception for Beijing, Shanghai, and Shenzhen symbols. Raw
Tencent rows may be admitted as qfq only when the independently retrieved Sina qfq-factor
series covers the required dates, contains no future dates, is strictly positive, and every
factor is exactly `1`. Such rows retain the composite provenance
`tencent.fqkline.raw+sina.qfq_factor.unit_verified`; this exact string is the only composite
source on the qfq whitelist used by cache readiness, completed-session refresh, and research
history seeding. Generic Sina history, non-unit factors, incomplete factor coverage, and any
other composite provenance remain excluded rather than being relabelled qfq.

Plan the current full universe from `backend` without writes:

```powershell
.\.venv\Scripts\python.exe scripts\backfill_market_universe.py `
  --source-policy tencent_first --max-workers 10
```

Apply in bounded 200-symbol cache batches with an atomic checkpoint:

```powershell
.\.venv\Scripts\python.exe scripts\backfill_market_universe.py --apply `
  --days 500 --batch-size 200 --rate-limit-seconds 0.2 `
  --source-policy tencent_first --max-workers 10

# Continue after interruption using the persisted last symbol.
.\.venv\Scripts\python.exe scripts\backfill_market_universe.py --apply `
  --resume-from-checkpoint --days 500 --batch-size 200 `
  --source-policy tencent_first --max-workers 10
```

The checkpoint records the source policy, worker bound, success/error/isolation counts,
and `live_trading_enabled=false` evidence. Runtime retry state and current-universe
membership are deliberately separate: `logs/universe_backfill_checkpoint.json` remains
resumable retry state, while `logs/current_a_share_universe.json` is the atomic official
membership manifest. A no-op resume updates the latter but never erases unresolved retry
symbols from the former.

## Bounded candidate hot-cache seed

After initializing the research database, inspect the current candidate import plan from
`backend`:

```powershell
.\.venv\Scripts\python.exe scripts\seed_market_history.py
```

This is a dry run. It opens `trading_local.sqlite3` with SQLite `mode=ro` and
`query_only=ON`, selects at most 200 current candidate symbols and at most 500 ready qfq
daily bars per symbol, then prints JSON statistics. The hard ceilings are 500 symbols and
1,000 bars per symbol. Override the default bounds or choose an already completed cutoff
when needed:

```powershell
.\.venv\Scripts\python.exe scripts\seed_market_history.py `
  --candidate-limit 100 --bars-per-symbol 300 --as-of 2026-07-14
```

The automatic cutoff uses the newest eligible cache date no later than the latest
completed Shanghai session. Before 15:15 Asia/Shanghai, the current date is ineligible;
an explicit current-session `--as-of` is blocked. After 15:15, a current-date row still
needs a source-cache `updated_at` at or after 15:15, so a stale intraday half-bar remains
excluded. Only rows with
`quality_status=ready` and `adjustment_mode=qfq` are eligible. Sina stock-history rows
are excluded even if incorrectly labelled qfq, and unknown-adjustment rows remain
isolated in the operational cache.

The operational cache also prevents an amount-less fallback row from replacing an
existing `ready` row that already has amount data. The fallback may insert a genuinely
new date, but lower-information refreshes cannot silently downgrade complete historical
rows before they reach this research database.

Review the JSON plan, then explicitly apply it:

```powershell
.\.venv\Scripts\python.exe scripts\seed_market_history.py --apply
```

Apply uses one target connection and one write transaction. It upserts instruments,
creates a content-addressed `candidate_hot_cache` universe snapshot, records an ingest
run, and idempotently upserts daily bars. Provider, amount, volume unit, and the source
cache `updated_at` are preserved. The stable row hash excludes fetch timestamps, so an
unchanged bar keeps its identity across refreshes; the 2026-07-06 rule boundary is stored
in `rule_regime`. A repeated identical apply creates a new audit ingest run but does not
duplicate snapshots or bars, and it does not rewrite an unchanged bar's original ingest
provenance.

## Full-market research seed

After the operational-cache backfill, seed the research database in deterministic symbol
batches. Every batch uses the same content-addressed full-universe snapshot, while only the
bounded symbol slice is loaded into memory and written as daily bars:

```powershell
# Inspect the first 500-symbol batch.
.\.venv\Scripts\python.exe scripts\seed_market_history.py `
  --universe-scope full_market_cache `
  --universe-manifest-path logs\current_a_share_universe.json `
  --symbol-limit 500 --bars-per-symbol 500

# Apply it, then continue from the reported last_processed_symbol.
.\.venv\Scripts\python.exe scripts\seed_market_history.py --apply `
  --universe-scope full_market_cache `
  --universe-manifest-path logs\current_a_share_universe.json `
  --symbol-limit 500 --bars-per-symbol 500

.\.venv\Scripts\python.exe scripts\seed_market_history.py --apply `
  --universe-scope full_market_cache `
  --universe-manifest-path logs\current_a_share_universe.json `
  --resume-after SH600000 `
  --symbol-limit 500 --bars-per-symbol 500
```

`--symbol-limit` is clamped to 500 and `resume_after` uses deterministic normalized-symbol
ordering. Re-running a completed batch is idempotent. Only `ready + qfq` rows enter
`daily_bars`; raw/unadjusted and other quarantined rows remain in the operational database
for audit and coverage reporting. The manifest, not every symbol ever observed in
`daily_bar_cache`, defines membership; this prevents delisted or stale cached symbols from
silently entering a current-universe training snapshot.

If any official member lacks eligible qfq history, the full-market result and ingest run
remain `partial`. The complete membership snapshot is still written, but
`missing_qfq_symbols`, exchange-level coverage, and raw-newer-than-qfq gaps are reported.
The P2 provider probe on 2026-07-16 verified that `newfqkline` returns an explicit
`qfqday` array for current Beijing Exchange symbols `BJ920000`, `BJ920002`, and
`BJ920016`. Across the latest 500 overlapping sessions, their qfq closes differed from
the separately requested raw `day` closes on every returned date, so the adapter does not
infer adjustment from numerically equal prices or from the request parameter alone.
Legacy 43xxxx/8xxxxx aliases and any response without `qfqday` remain in the reported gap;
they are not relabelled. The bounded full-universe backfill must still be applied before
the newly supported provider path changes research-database coverage.

## Incremental full-market feature scan

`market_history.sqlite3` is also the read-only input for the post-close horizontal-structure
scan. The scanner always joins the newest `a_share_full_market_cache` snapshot, so cached
indices and symbols that have left the official universe cannot enter the candidate set.
Only `quality_status=ready` and `adjustment_mode=qfq` rows are eligible. A symbol needs at
least 60 bars and a latest bar no more than five calendar days behind the snapshot date.

Run a bounded scan through the local API:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/candidates/full-market-scan/run?candidate_limit=300&lookback_bars=120&persist=true"
```

Review the latest reduced set:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/candidates/full-market-scan/latest?limit=300"
```

The operational database keeps one auditable row per scan in
`full_market_feature_runs` and only the latest state per symbol in
`full_market_feature_state`. Each state stores an input revision derived from the latest
bar date, source update time, bar count, universe snapshot, parameters, and feature
version. An unchanged rerun reuses the state; a revised symbol alone is recomputed. The
top bounded set is marked `is_candidate=1` and consumed directly by Selection V2. It is
deliberately not mirrored into `auto_discovered_candidates`, whose existing API remains
reserved for real-time strength/anomaly discovery. Old feature candidates are cleared
transactionally inside their independent state table.

The score combines range compression, realized volatility, ATR, volume contraction,
moving-average support, and distance to the recent pressure level. It is explicitly an
`uncalibrated_structure_score`, not an estimated probability of a future rise. It produces
review/watch evidence only and never enables execution. The independent
`full_market_feature_loop.py` worker runs immediately at stack startup, then every four
hours after success or after fifteen minutes following a failed/partial cycle.

## Completed-session daily refresh

`market_history_refresh_loop.py` keeps the research history moving forward independently
from the feature scanner. Before opening either database it verifies both the backend
health response and local settings still have live trading disabled. It resolves the latest
completed Shanghai session from the exchange calendar and the 15:15 finalization boundary;
when history is already current it performs no remote bar refresh.

When a completed session is missing, the worker refreshes official-universe symbols with
provenance-safe qfq history and also attempts at most 500 missing-qfq symbols per cycle.
Tencent requests are capped to the requested 150-bar overlap window and run in bounded
200-symbol batches with at most 20 workers. The fallback accepts only an explicit `qfqday`
payload; a raw `day` response is never relabelled as adjusted history. Each successful or
unchanged row is then idempotently seeded into `market_history.sqlite3` in 500-symbol
transactions, after which the full-market feature scan is triggered. Unresolved symbols
remain an explicit qfq gap with before/planned/recovered/remaining counts in the heartbeat.
Remote failures preserve the prior cache, produce structured per-symbol errors, and shorten
only this worker's next retry to 15 minutes; a complete/up-to-date cycle returns to four
hours. Progress phases and counts are written to
`backend/logs/market_history_refresh_heartbeat.json`.

## Official instrument catalog refresh

`instrument_catalog_refresh_loop.py` runs once at stack startup and then daily after a
complete refresh, with a fifteen-minute retry after a partial, blocked, or failed cycle.
It commits a new immutable official-universe snapshot only when every required exchange
segment is complete and the full-market and per-segment shrink guards pass. New listings
are added, renamed securities update their display name, and symbols absent from a complete
new catalog become inactive. Existing snapshots and daily bars are retained; incomplete
external discovery does not mutate the database or manifest. The heartbeat is
`backend/logs/instrument_catalog_refresh_heartbeat.json`.

## Limited historical score calibration

`full_market_calibration_loop.py` runs at stack startup and then daily, with a thirty-minute
retry after an incomplete cycle and a 900-second deadline. It labels historical anchors by
an explicit future return event and uses a chronological validation window separated from
training by the label horizon. Each structure-score bin reports sample count, event count,
estimated rate, and Wilson interval. A probability is exposed only when the run and the bin
both satisfy their sample thresholds; otherwise the result remains `insufficient_data`.

This output is labelled `limited_historical_calibration`. It does not turn the independent
`uncalibrated_structure_score` into a probability. Current-universe survivorship, latest-qfq
revision, and overlapping-label limitations remain machine-readable in the run record. The
worker is review-only, cannot submit orders, and writes
`backend/logs/full_market_calibration_heartbeat.json`.
