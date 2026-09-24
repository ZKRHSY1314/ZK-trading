# claude_02 data dictionary — M3-02 frozen reader outputs

All outputs live under `claude methods/_m3_20260910/claude_02/runs/<run_name>/`. The final run is `dev_run_02` (reader `m3_frozen_reader.v3`); `dev_run_01` is retained as the earlier pre-feedback run (same labels/counts; its packets carried retrospective episode metadata, which Codex's audit found and which `verify_run.py` now flags). They are **derived, pending-review research data** produced by `backend/app/research/m3_frozen_reader.py` (`READER_VERSION = m3_frozen_reader.v3`) from the two hash-pinned M2 candidate stores under the frozen label policy `0.3.0-draft` (`policy_hash d436ba14…`, module `e20eb21c…`). Nothing here is a reviewed case, a review, a training set or a trading signal.

## Sources actually connected (read-only, `mode=ro&immutable=1`, `PRAGMA query_only=ON`, authorizer denying writes/ATTACH/PRAGMA-writes)

| Role | File | SHA-256 | Bytes |
| --- | --- | --- | --- |
| trading | `…/run_ths_v2_20260910_041710_97ef9c09/trading.sqlite3` | `c0b26660ab903541e7e213ee312c565be73547bb3cc8c142486999717e3edeca` | 38,969,344 |
| history | `…/run_ths_v2_20260910_041710_97ef9c09/history.sqlite3` | `eda17434ab67496c33eed275b35045c140bad72802b4dcbf981ff22422c53003` | 10,604,544 |

Other frozen inputs (read as files, never connected): `qualification_v2_reviewed.json` (`992bd79c…`), AkShare `calendar.json` (`f1f1ce33…`), `pilot_symbols.csv` (`97e251ae…`), `codex/metadata_index_01/index.json` (`14f1bad7…`, convenience index for listing-source grades and the partial known cash events, cross-checked against the qualification `controls` boundaries). Both stores are the same capture; agreement is storage reconciliation, not independent corroboration.

## Source-field mapping used by the reader

| Reader input | Store field(s) | Reconciliation rule (row excluded on failure; reason recorded in `exclusions.json`) |
| --- | --- | --- |
| `Observation` price row | `trading.daily_bar_cache` (symbol, trade_date, open, high, low, close, volume, amount, source, quality_status, adjustment_mode, volume_unit) | equals `history.daily_bars` on the six numerics; `adjustment_mode='none'` in both; `quality_status='qualified_candidate'`; `source`/`provider='tonghuashun'`; `volume_unit` equals the frozen scope; `amount_unit` from the frozen scope |
| `Observation.available_at` | `trading.row_evidence.observed_at` | equals `history.daily_bars.fetched_at` and the frozen capture `observed_at` — the 2026 capture time, **not** historical availability |
| `Observation.source_ref` | `row_evidence` key + `point_index` | `"<trade_date>#<point_index>"`; lineage (raw/request/producer/parser/receipt/manifest hashes) must equal one of the symbol's frozen captures; `point_index < capture.rows`; `qualification_sha256 == sha256(canonical(frozen scope))` |
| suspension `Observation` | `trading.suspension_records` (+ `coverage_inventory='full_day_suspension'`) | `evidence_sha256 == sha256(canonical(frozen ledger entry))`, `record_json == canonical(entry)`; identical in both stores; no OHLCVA; `source_ref = "suspension#<evidence_sha256[:16]>"`; `available_at` = evidence assembly time |
| expected keys | frozen scope `expected_price_dates` / `suspended_dates` | every expected key within the bound must be present (else `expected_*_missing_from_store`); every stored key must be expected |
| benchmark rows | same tables for `SH000300` | units `not_applicable/not_applicable` retained; index-level OHLC; volume/amount uninterpreted (excluded from identity) |

Price consumption bound: every OHLCVA `SELECT` carries `trade_date <= '2025-03-31'`; rows beyond the bound are only counted (`trading_rows_beyond_permitted_not_selected`).

## Files

| File | Content |
| --- | --- |
| `run_receipt.json` | reader/labels/policy pins, validated configuration mode and output dir, inputs before/after (path, sha256, bytes), read log (connections with mode, sha256/bytes before/after, `query_only_read_back`, every SQL statement with bound parameters and connection role, denied actions), reconciliation counts, waterfall, chronology index, `status` |
| `real_run_transcript.json` | runner transcript: command, timing, frozen pins before/after, sources before/after, connections, counts |
| `exclusions.json` | row-level reconciliation exclusions `{symbol, trade_date, reason, detail}` and structural problems |
| `decision_exclusions.json` | development stock-sessions with no decision record: `not_listed`, `no_observations_before_cutoff` |
| `inventory.json` | per stock: listing date and source grade, permitted rows/suspensions, first/last permitted observation, development sessions expected/listed, records, exclusions, warmup shortfall at the first decision, known cash events (retained total and inside development); benchmarks; calendar slice record; development session count |
| `cohort_coverage.json` | per development session: `expected_listed_frozen_stocks` (denominator: frozen pilot stocks with listing_date ≤ session; benchmarks excluded), `valid_price_keys`, `evidenced_suspension_keys`, `evidence_key_coverage` = (price + suspension)/expected, `price_availability` = price/expected, observation time = evidence assembly time. Not full-market coverage. `null` when no stock is expected. |
| `chronology/<symbol>.jsonl.gz` | deterministic gzip (mtime 0), one line per development decision: `{"record": <m3.labels.output.v3>, "source_map": {...}}` in chronological order. `record` is a verified core with an empty validated ledger; `source_map` gives consumed key count, first/last consumed date, `consumed_lineage_sha256` (over `trade_date|source_ref` of consumed observations), benchmark keys, and the row-evidence lookup rule |
| `chronology_index.json` | per symbol: record count, sha256 of the gzip file and of the uncompressed JSONL, bytes; `total_records` |
| `episodes.json` | retrospective inventory of all episodes of all phases (`build_episodes` on the complete chronology; `information_time` states it is not cutoff-known review input): start/end/sessions, selection path, `min_duration_established_at`, closed reason/status, `episode_key`, member ids/hashes; accumulation episodes carry `prefix_proof` (or `duration_not_established`), packet path/hash, `cutoff_packet_hash` and the audit path/hash; `packets` index |
| `packets/<episode_key>.json` | **cutoff review packet** (`m3.frozen_reader.cutoff_review_packet.v2`) per established accumulation episode, built only from the three prefix members, the representative record and same-date controls/context (`information_time` = the representative cutoff; nothing dated later; `verify_run.py` scans every date token): representative (date, episode_id, record_hash, cutoff, selection, phase, current_state, chronology locator), `prefix_proof`, three member bindings, `prefix_path` (the members' own phase/selection), price-context references (consumed keys, first/last source refs, max consumed date, input/benchmark/calendar fingerprints), `warmup_depth_at_representative` (bars available at the representative; distinct from the inventory's initial-development warmup deficit), numerical values at the representative, supporting and contradicting evidence (representative data quality, threshold proximity, prefix members not selected), uncertainties (data quality, adjustment, corporate-action status and ex-dates known at the cutoff, ST unknown, strict_pit, coverage, listing grade), regime/liquidity/limit, `control_pool` (all same-date summaries, benchmark excluded), `control_ranking`, `match` (`m3.labels.match.v3`), `controls` (cores by chronology locator, pending review), `exclusion` where applicable, and `cutoff_packet_hash` (stable binding over the packet minus review fields and file locators). `review_status = pending_review`, `reviews = []` |
| `episode_audit/<episode_key>.json` | **retrospective audit metadata** (`not_cutoff_known = true`, `information_time` = full development interval): end known at the development end, sessions, status/closed reason/censoring, full selection path, eligibility changes, member ids/hashes, `prefix_hash` binding. For exhaustive accounting and dependence analysis only; excluded from the M3-03 review input bundle |
| `controls.json` | per matched/unmatched episode: control episode ids, unmatched flag, rejected pool counts, pool size; global control uses; dependence groups over the matched pending episodes |
| `waterfall.json` | the exclusion waterfall (below) |
| `verify_run_result.json` | output of `verify_run.py` (re-verification without SQLite) |

## Waterfall fields

`expected_stock_session_keys` (50 stocks × 378 development sessions) → `not_listed` / `no_observations_before_cutoff` (decision exclusions) → `records_generated` → `current_state` (observed/suspended/missing) → `quality_gate_reasons` → `phase` / `selection` distributions → `episodes_total`, `episodes_by_phase` → `accumulation_episodes` → `accumulation_duration_established` → `representatives_candidate` / `representatives_not_candidate` → `matched_3_to_5_controls` / `unmatched` → `pending_review` (= matched; potential positives) → `independently_reviewed = 0`, `qualified_reviewed_positive_episodes = 0`, `target.met = false`. `effective_dependence_groups_of_pending_potential_positives`, `unique_controls_used`, `control_uses`, `control_reuse_max` are reported separately. `strict_pit_eligible = 0` and `training_eligible = 0` by construction.

## Cutoff and context semantics

* `Cutoff(date, date+'T16:00:00+08:00', 'retrospective')` (`close+3600s`) for every decision.
* Calendar: the pinned AkShare file sliced to `[first permitted observation .. 2025-03-31]`; `available_at` = evidence assembly time `2026-09-10T06:52:37Z` (metadata index `assembled_at_utc`), explicitly **not** historical availability.
* Security context per decision: `listing_date` (pilot CSV, grade from the metadata index), `st_status=unknown`, `name=None`, `float_shares=None`, `turnover_available=False`; `corporate_action_status=partial_known` with `known_ex_dates` = retained events with `ex_date ≤ cutoff` for SH600011/BJ920000 (complete coverage unknown), `unknown` for the other 48; `facts_available_at` = evidence assembly time → consumed with an availability violation in retrospective mode, `strict_pit_eligible=false`.
* Coverage: the cohort evidence-key coverage of the session (see `cohort_coverage.json`), `available_at` = evidence assembly time.
* Window bases: stock feature windows count valid price bars (preserved kernel); gaps, suspensions, staleness, episode continuity and holding use calendar sessions.
