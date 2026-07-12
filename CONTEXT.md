# Domain language

## Cockpit

The local Windows application used to inspect A-share market data, generate review-only decisions, run simulated workflows, and examine evidence. The Cockpit never implies broker or live-account access.

## Control Plane

The single operational entrypoint. Its `full` profile runs Market Pulse -> Decision Snapshot -> Simulation Cycle -> Forecast Feedback -> Training Feedback. It records semantic step status instead of treating a successful function call as a successful business result. The `maintenance` profile omits Simulation Cycle, while `training` runs only Forecast Feedback -> Training Feedback.

## Market Pulse

A time-bounded, source-backed digest of policy, market, and sector evidence. A Market Pulse includes freshness, source coverage, structured Event Facts, cross-market context, Sector Theses, and links to its evidence.

## Decision Snapshot

A point-in-time, review-only ranking of candidates produced from market features, rules, Market Pulse evidence, sector exposure, observable structure proxies, and data-quality gates. Every Decision Snapshot carries its decision cutoff and never grants live execution.

## Forecast Ledger

The immutable point-in-time record of sector and stock forecasts. Every record carries a decision cutoff, `available_at`, horizon, model and data versions, evidence, rank, score, and review-only status. A changed forecast requires a new identity; future evidence cannot rewrite history.

## Simulation Cycle

An audited run that consumes the completed Decision Snapshot, creates simulation plans, monitors results, and records review evidence. A Simulation Cycle can be completed, partial, blocked, or failed; it never authorizes a real order.

## Forecast Feedback

The point-in-time workflow that matures Forecast Ledger records after enough trading sessions exist. Stock outcomes use the next session open as entry and the horizon session close as exit. Sector outcomes use the point-in-time latest membership snapshots, equal-weight complete member windows, and an aligned index benchmark. Evaluation reports coverage, Precision@K, rank IC, and calibrated Brier score; insufficient samples remain explicitly `insufficient_data`.

## Training Feedback

The incremental workflow that converts completed safe tasks into legacy training samples and quality summaries after Forecast Feedback. Training Feedback does not directly rewrite active rules or enable execution.

## Outcome

The future 1/3/5/10/20-session observation attached to an earlier prediction only after enough point-in-time market bars exist. Pending future data and proxy sector returns are not presented as proven accuracy.

## Event Fact

An immutable, source-backed event observation with event and cluster identities, entities, geography, direction, magnitude, publication/retrieval/availability times, source tier, revision, evidence URLs, and a raw hash. It is usable only when `available_at` is not later than the decision cutoff.

## Sector Thesis

A review-only hypothesis mapping available Event Facts and cross-market features to a sector, direction, horizon, decay rule, invalidation conditions, confidence, and industry-chain edges. It is a forecast to evaluate, not a fact or trading instruction.

## Sector Exposure

The point-in-time company-to-sector membership used to connect a Sector Thesis to a stock. External board providers are stored as append-only complete membership snapshots; a query selects the latest snapshot per source and sector available at its cutoff, so removals and later re-additions do not rewrite earlier membership. Legacy interval records remain supported.

## Global Market Bar

An immutable, revisioned daily observation used as cross-market context. Current adapters cover qfq-adjusted SMH/NVDA and explicitly unadjusted continuous CL/GC/BTC futures, with optional SOX. A revised value is appended with a later `available_at`; an unfinished U.S. session bar is provisional and excluded from regime features.

## Structure Gate

The observable two-head stock-structure baseline: `pre_markup_probability` competes with `distribution_probability`. A sufficiently confident distribution signal produces `distribution_veto`. These values are explainable proxies to calibrate through the Forecast Ledger and never claim direct observation of a hidden market actor.

## Disclosure Fact

An immutable, revisioned, point-in-time company disclosure such as a balance sheet, income statement, cash-flow statement, earnings forecast, buyback, shareholder reduction, unlock, private placement, or major contract. Disclosure summaries remain factual and review-only; they do not emit buy or sell decisions.

## Universe Backfill

The resumable review-only workflow for discovering Shanghai/Shenzhen A-share symbols and filling `daily_bar_cache`. It is dry-run by default, requires explicit `--apply` to write cache rows, isolates per-symbol failures, refreshes the two reference indices required by Forecast Feedback, and reports bar, amount, latest-cross-section, and reference-data coverage.

## Reference Data Worker

The independent four-hour worker that refreshes immutable sector membership snapshots, normalized share-buyback facts, and cross-market bars. It has an OS-backed single-instance lock, a bounded child-process timeout, a heartbeat, and the same live-trading-disabled gate as the Control Plane; it is not an extra trading step.

## Ensure Stack

The Windows health-and-recovery command that checks backend, frontend, worker identities and heartbeats, readiness, and `live_trading_enabled=false` before reusing or restarting the local stack. The optional scheduled task invokes this command; it does not broaden trading permissions.

## Schedule Slot

One idempotent time window in which the Control Plane may run a profile. A worker heartbeat proves whether scheduled operation is currently alive.

## Review-only

The operating invariant that permits reading, analysis, simulation, evidence persistence, and human review while excluding broker login, credentials, fund access, and real order placement.
