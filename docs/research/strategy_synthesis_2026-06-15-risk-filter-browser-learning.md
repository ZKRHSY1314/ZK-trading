# 2026-06-15 Risk Filter And Browser Learning

This note records run 72 and the browser/data-set synthesis. It is review-only
research evidence. It does not change `rules.yaml`, broker permissions, or any
live-trading setting.

## Safety State

- `/health.live_trading_enabled=false`
- `run_id=72`
- `status=completed`
- `elapsed_seconds=21.613`
- `artifact=backend/output/model_candidates/offhour_model_candidate_41ec050ca2f8.json`
- `allowed_effect=review_only_filter_hypothesis_no_rule_or_trade_change`

## Run 72 Filter Experiments

`shadow_context_filter_experiments.v1` was added under
`shadow_phase_context_split.v1`. The purpose is to test the `risk_mixed`
bucket from run 71 with explicit filters instead of treating a high-return
bucket as directly tradable.

| experiment | status | trades | win_rate | avg_return_pct | cumulative_return_pct | walk_forward |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `strong_reclaim_confirmation` | `passed_metric_review_only` | 23 | 0.739130 | 4.890366 | 188.049031 | blocked |
| `base_shadow_candidate` | `passed_metric_review_only` | 26 | 0.692308 | 3.995078 | 164.572796 | blocked |
| `strong_reclaim_no_high_vol` | `passed_metric_review_only` | 12 | 0.833333 | 4.823777 | 73.931248 | blocked |
| `exclude_distribution_risk_tags` | `passed_metric_review_only` | 6 | 0.833333 | 9.437475 | 69.781356 | blocked |
| `low_risk_stabilized_reclaim` | `passed_metric_review_only` | 6 | 0.833333 | 9.437475 | 69.781356 | blocked |
| `exclude_high_volatility_board` | `passed_metric_review_only` | 13 | 0.769231 | 3.951284 | 63.308386 | blocked |
| `exclude_high_vol_and_distribution_risk` | `blocked` | 2 | 1.000000 | 7.788505 | 16.183619 | skipped |

All passed experiments are still metric-only. Walk-forward remains blocked,
mainly because fold trade count is too low and weak-fold win rate is not stable
enough. The result is strong enough for more research and simulation replay, but
not strong enough for permission expansion.

## Data-Set Reading

Dataset1 contains:

- 7 buy strategies
- 7 sell strategies
- 4 position-management rules
- 12 success cases
- 14 failure cases
- 10 trading discipline rules

The strongest Dataset1 themes that match run 72 are:

- Buy strength, not weakness.
- Do not chase after a large rise.
- Do not average down without the required phase signal.
- Use staged entries and staged exits.
- Follow the plan instead of cancelling exit plans because of emotion.

Dataset2 contains 225 structured rules:

- `SIM_BUY_CANDIDATE=63`
- `WAIT_CONFIRMATION=59`
- `REDUCE_OR_EXIT=64`
- `HOLD_OR_TRAIL=19`
- `AVOID_OR_WAIT=11`
- `RISK_ALERT=6`
- `NO_TRADE=3`

Dataset2 is already aligned with the project safety model: the strategy set mode
is `simulation_and_training_only`, and individual rules keep
`allow_live_order=false`.

## Browser Learning

I reviewed these references in the in-app browser:

- QSTrader: event-driven backtesting and trade-level/portfolio-level metrics.
- VectorBT: fast vectorized parameter sweeps across strategies, instruments,
  and periods.
- Backtrader: clear separation of strategy, indicators, orders, broker, sizer,
  and analyzers.
- AKShare: useful for broad historical data access, but it should remain a
  historical/fallback data source rather than being treated as a guaranteed
  low-latency real-time source.

The practical takeaway is to keep ZK-trading on its current architecture path:
event records, deterministic replay, strategy comparison, and strict safety
gates. Do not import a large external backtesting framework wholesale.

## Strategy Synthesis

Current best research hypothesis:

1. `strong_reclaim_confirmation` should become the next review-priority filter.
   It improved full-history win rate from `0.692308` to `0.739130` and
   cumulative return from `164.572796%` to `188.049031%`.
2. `low_risk_stabilized_reclaim` and `exclude_distribution_risk_tags` have the
   best per-trade quality, but only 6 trades. They need more historical samples
   before they can influence position sizing.
3. High-volatility boards should not be removed blindly. They contribute both
   return and risk. The better rule is: require stronger confirmation, lower
   initial position, stricter stop, and earlier review.
4. Dataset1 failure lessons should become negative training labels:
   buying early, buying high, averaging down too soon, cancelling a planned
   sell, and trading outside the familiar phase.
5. The next implementation should add a stable review queue for
   `strong_reclaim_priority_review`, still `review_only` and `simulation_only`.

## Next Action

Implement a review-only strategy comparison layer that ranks these filters
across more symbols and longer windows:

- `base_shadow_candidate`
- `strong_reclaim_confirmation`
- `strong_reclaim_no_high_vol`
- `low_risk_stabilized_reclaim`
- `exclude_distribution_risk_tags`
- high-volatility board with lower position sizing

Promotion rule: no filter may influence simulated screen-click permission until
it passes walk-forward and the Sim-Cockpit readback/fill loop is stable.

## Run 73 Strategy Comparison Layer

Implemented `shadow_filter_strategy_comparison.v1` under
`shadow_context_filter_experiments.v1`. This layer ranks filter experiments by
walk-forward status, cumulative return, win rate, average return, and sample
gap. It explicitly records a permission policy:

- `may_change_rules_yaml=false`
- `may_change_position_size=false`
- `may_enable_screen_click=false`
- `requires_human_review=true`

Main DB run:

- `run_id=73`
- `history_days=240`
- `elapsed_seconds=24.657`
- `live_trading_enabled=false`
- `stable_candidate_count=0`
- `metric_candidate_count=6`
- `next_action=expand_metric_candidates_across_more_symbols_and_time_windows`

Top review priorities:

| rank | experiment | tier | score | trades | win_rate | cumulative_return_pct | blocker |
| ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | `strong_reclaim_confirmation` | `metric_candidate_needs_walk_forward` | 112.234572 | 23 | 0.739130 | 188.049031 | weak walk-forward |
| 2 | `base_shadow_candidate` | `metric_candidate_needs_walk_forward` | 103.077371 | 26 | 0.692308 | 164.572796 | weak walk-forward |
| 3 | `exclude_distribution_risk_tags` | `metric_candidate_needs_walk_forward` | 77.095224 | 6 | 0.833333 | 69.781356 | sample gap |
| 4 | `low_risk_stabilized_reclaim` | `metric_candidate_needs_walk_forward` | 77.095224 | 6 | 0.833333 | 69.781356 | sample gap |
| 5 | `strong_reclaim_no_high_vol` | `metric_candidate_needs_walk_forward` | 74.677905 | 12 | 0.833333 | 73.931248 | sample gap |

Conclusion: the 240-day window confirms high full-history returns, but still
does not justify permission expansion. The correct next action is longer window
and broader sample replay.

## Run 74 Longer Window Replay

Ran the same comparison with a longer historical window:

- `run_id=74`
- `history_days=480`
- `limit=140`
- `strategy_limit=80`
- `elapsed_seconds=34.442`
- `live_trading_enabled=false`
- `stable_candidate_count=1`
- `metric_candidate_count=3`
- `next_action=human_review_stable_walk_forward_candidates`

The first stable review-only candidate appeared:

| experiment | tier | trades | win_rate | avg_return_pct | cumulative_return_pct | walk_forward |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `base_shadow_candidate` | `stable_walk_forward_candidate_review_only` | 31 | 0.580645 | 3.834167 | 199.300061 | passed |
| `strong_reclaim_confirmation` | `metric_candidate_needs_walk_forward` | 27 | 0.592593 | 4.211626 | 184.874139 | blocked |
| `low_risk_stabilized_reclaim` | `metric_candidate_needs_walk_forward` | 8 | 0.875000 | 10.202894 | 114.310307 | blocked |

`base_shadow_candidate` parameters:

- `confirmation_filter=dataset1_stabilized_reclaim`
- `entry_delay_days=1`
- `horizon_days=3`
- `stop_loss_pct=0.04`
- `take_profit_pct=0.12`
- `buy_position_ratio=0.08`
- `wait_position_ratio=0.06`

Walk-forward details for the passed candidate:

- `fold_count=4`
- `walk_forward_trade_count=23`
- `weighted_win_rate=0.739131`
- `weighted_average_return_pct=6.115915`
- `total_equal_weight_cumulative_return_pct=274.176860`
- `min_fold_trade_count=3`
- `min_fold_win_rate=0.571429`
- `min_fold_cumulative_return_pct=2.835995`

Fold returns:

| fold | dates | trades | win_rate | avg_return_pct | cumulative_return_pct |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | 2025-02-27 to 2025-03-05 | 7 | 0.571429 | 4.967565 | 38.809269 |
| 2 | 2025-03-05 to 2025-03-07 | 7 | 0.857143 | 5.312142 | 42.462099 |
| 3 | 2025-03-07 to 2025-03-11 | 3 | 0.666667 | 0.962177 | 2.835995 |
| 4 | 2025-03-11 to 2026-06-08 | 6 | 0.833333 | 10.970260 | 83.998366 |

Interpretation:

The 480-day test is the strongest evidence so far that Dataset1 stabilized
reclaim plus Dataset2 volume-price signals can exceed the 20% target. However,
the full-history win rate is only slightly above the gate, and fold 3 is thin.
This is a candidate for supervised simulation review, not an automatic trading
permission.

Updated next action:

1. Keep `base_shadow_candidate` in a stable review queue.
2. Test it on a larger symbol universe and with benchmark-relative market phase
   labels.
3. Let `strong_reclaim_confirmation` stay as a quality overlay; it improves
   average return but still needs more fold trades.
4. Keep `low_risk_stabilized_reclaim` as a high-quality small-sample subset,
   not a position-size booster.
5. Do not enable screen-click buying until Sim-Cockpit readback produces
   verified fills and positions in the simulated account.

## Run 75 Market Context Attribution

Added `shadow_filter_market_context.v1` to every filter experiment and included
`market_regime_context` in `shadow_filter_strategy_comparison.v1`.

Main DB run:

- `run_id=75`
- `history_days=480`
- `elapsed_seconds=33.768`
- `live_trading_enabled=false`
- `stable_candidate_count=1`
- `metric_candidate_count=3`

The stable `base_shadow_candidate` still passed walk-forward, but market
context exposed a weakness:

| market_regime | trades | win_rate | avg_return_pct | cumulative_return_pct |
| --- | ---: | ---: | ---: | ---: |
| `benchmark_down` | 13 | 0.769231 | 8.277218 | 174.085741 |
| `benchmark_neutral` | 13 | 0.307692 | -0.548099 | -8.403568 |
| `benchmark_up` | 5 | 0.800000 | 3.676127 | 19.217993 |

Interpretation:

The candidate is not simply "good everywhere". It performs best when the
benchmark is weak but selected stocks still reclaim and show relative strength.
It performs poorly in neutral benchmark context, where signals may be noisy and
lack directional pressure. This adds a new promotion blocker:
`market_context_needs_more_review`.

## Run 76 Benchmark-Neutral Filter Experiment

Added two review-only experiments:

- `exclude_benchmark_neutral`
- `strong_reclaim_exclude_benchmark_neutral`

Main DB run:

- `run_id=76`
- `history_days=480`
- `elapsed_seconds=35.590`
- `live_trading_enabled=false`
- `stable_candidate_count=1`
- `metric_candidate_count=5`

New experiment results:

| experiment | tier | trades | win_rate | avg_return_pct | cumulative_return_pct | market_context | walk_forward |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `strong_reclaim_exclude_benchmark_neutral` | metric candidate | 15 | 0.866667 | 8.415096 | 227.765008 | robust | blocked |
| `exclude_benchmark_neutral` | metric candidate | 18 | 0.777778 | 6.999137 | 226.759520 | robust | blocked |
| `base_shadow_candidate` | stable review candidate | 31 | 0.580645 | 3.834167 | 199.300061 | needs review | passed |

The new filters remove the bad neutral-market segment and materially improve
full-history quality. However, both remain blocked by
`walk_forward_fold_trade_count_too_low`.

Fold details:

- `exclude_benchmark_neutral`: walk-forward trade count `11`, weighted win rate
  `0.909091`, weighted average return `8.291957`, total cumulative return
  `135.401802`, but minimum fold trade count is only `1`.
- `strong_reclaim_exclude_benchmark_neutral`: walk-forward trade count `9`,
  weighted win rate `1.0`, weighted average return `9.956065`, total cumulative
  return `131.760410`, but minimum fold trade count is only `1`.

Updated judgment:

1. `base_shadow_candidate` remains the only walk-forward-passed stable review
   candidate, but it has a real neutral-market weakness.
2. `exclude_benchmark_neutral` and
   `strong_reclaim_exclude_benchmark_neutral` are higher-quality candidates, but
   currently sample-thin.
3. Do not lower the walk-forward threshold to force a pass. The right action is
   to expand symbols, history, and candidate discovery so the fold sample count
   rises naturally.
4. In simulated planning, neutral benchmark context should reduce review
   priority or require additional intraday confirmation. This is still a
   research and dry-run rule, not a permission change.

## Run 78-80 Expanded Sample Repair

The earlier optimization path found strong short-window candidates, but the
shadow review chain only accepted near-miss candidates. That meant a candidate
that had already passed walk-forward could still show
`expanded_history_review.reason=no_shadow_candidates`, so the system could not
explain why the selected strategy worked across the wider replay set.

This has now been repaired:

- `expanded_signals` now carries up to 600 actionable replay signals.
- The optimization sample filters out signals that do not yet have a complete
  entry/exit backtest window.
- `selected_stable_candidate` now enters `shadow_parameter_evidence` as a
  review-only evidence item.
- `shadow_filter_strategy_comparison.v1` keeps both `top_review_priority` and
  `top_review_priorities` for compatibility.

Main DB validation:

- `run_id=80`
- `history_days=480`
- `limit=140`
- `strategy_limit=80`
- `live_trading_enabled=false`
- `artifact=backend/output/model_candidates/offhour_model_candidate_2f212c9b41a6.json`
- `signal_optimization.status=passed_for_simulation_review`
- `shadow_parameter_evidence.status=review_ready`
- `selected_candidate_included=true`
- `expanded_history_review.status=review_ready`
- `expanded_history_review.walk_forward_review.status=passed_for_simulation_review`

Selected stable candidate:

- `confirmation_filter=entry_green_above_signal`
- `entry_delay_days=1`
- `horizon_days=5`
- `stop_loss_pct=0.06`
- `take_profit_pct=0.18`
- `buy_position_ratio=0.08`
- `wait_position_ratio=0.06`
- `fold_count=4`
- `weighted_win_rate=0.821429`
- `weighted_average_return_pct=12.646114`
- `total_equal_weight_cumulative_return_pct=2420.627518`
- `min_fold_trade_count=5`
- `min_fold_win_rate=0.666667`
- `min_fold_cumulative_return_pct=63.043419`

Filter priority from expanded review:

| rank | experiment | tier | trades | win_rate | avg_return_pct | cumulative_return_pct | market_context | walk_forward |
| ---: | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | `strong_reclaim_exclude_benchmark_neutral` | stable review | 45 | 0.800000 | 11.212487 | 9968.111278 | robust | passed |
| 2 | `exclude_distribution_risk_tags` | stable review | 45 | 0.777778 | 11.042761 | 8969.818380 | robust | passed |
| 3 | `strong_reclaim_no_high_vol` | stable review | 44 | 0.750000 | 11.161043 | 8665.794783 | robust | passed |
| 4 | `low_risk_stabilized_reclaim` | stable review | 32 | 0.750000 | 10.837631 | 2193.257274 | robust | passed |
| 5 | `exclude_benchmark_neutral` | stable review | 66 | 0.757576 | 8.684603 | 18508.153056 | robust | passed |

Interpretation:

The highest-quality branch is no longer just "buy any strong signal." The
current evidence favors a narrower rule family: wait for a green entry above
the signal, avoid neutral benchmark noise, and remove Dataset1 distribution or
stall-risk tags. This matches the user's original experience pattern: do not
buy early, do not chase distribution, and only add simulated exposure after
the main-force markup phase becomes visible.

## Dataset And Browser Learning Synthesis

Dataset1 is best treated as a discipline and phase-attribution layer:

- buy strategy rows: 7 data rows
- sell strategy rows: 7 data rows
- success cases: 12 data rows
- failure cases: 14 data rows
- constitution rules: 10 data rows
- trading record rows: 39 data rows

Dataset2 is best treated as the broad structured signal library:

- `mode=simulation_and_training_only`
- `rule_count=225`
- all `allow_live_order=false`
- top action labels: `REDUCE_OR_EXIT=64`, `SIM_BUY_CANDIDATE=63`,
  `WAIT_CONFIRMATION=59`, `HOLD_OR_TRAIL=19`
- top rule categories include volume-price patterns, chip-peak patterns,
  intraday accumulation/wash/distribution, K-line reversal, order-book
  language, opening, and trend-combo rules.

Browser review confirms the project direction:

- Vectorized parameter sweeps are useful for discovering candidate filters, but
  they must be followed by out-of-sample or walk-forward validation.
- Event/schedule-driven backtesting is the better mental model for this project
  than one-shot static reports, because signals, risk gates, fills, and
  readback must be replayable.
- A large external framework should not be imported wholesale right now. The
  project already has the important parts: event records, deterministic replay,
  strategy comparison, closed-trade metrics, market-context attribution, and
  safety gates.

Current combined strategy:

1. Dataset2 generates a broad candidate signal from volume-price, K-line,
   intraday, auction, chip, and order-book language.
2. Dataset1 blocks action when the signal looks like early entry, late chase,
   distribution, failed markup, or emotional averaging-down.
3. The optimization layer searches confirmation filters, entry delay, holding
   horizon, stop loss, and take-profit combinations.
4. Walk-forward and market-regime splits decide whether a rule becomes
   simulation-review priority.
5. Sim-Cockpit readback must verify actual simulated fills and positions before
   any screen-click mode can be trusted.

Permission conclusion:

Run 80 meets the research target for supervised simulation review, including
20%+ cumulative return evidence. It does not grant real-trading permission and
does not modify production rules. The next practical step is to use these
filters to rank tomorrow's simulated candidates, then execute only dry-run or
small simulated-account tests after all Sim-Cockpit gates pass.

## Run 83 Simulation Review Plan

Implemented `simulation_review_plan.v1` in the off-hour model candidate
artifact. This converts the learned filter comparison into a bounded
next-session simulation review plan.

Main DB validation:

- `run_id=83`
- `live_trading_enabled=false`
- `artifact=backend/output/model_candidates/offhour_model_candidate_96e4e5441f4a.json`
- `simulation_review_plan.status=ready_for_dry_run_review`
- `data_freshness.latest_signal_date=2026-06-12`
- `data_freshness.calendar_lag_days=3`
- `candidate_count=12`
- `ready_dry_run_candidate_count=12`

Portfolio limits for the 200,000 simulated account:

- first probe cap: `2%`, about `4,000` simulated cash
- high-volatility board first probe cap: `1%`, about `2,000` simulated cash
- confirmed staged exposure cap: `8%`, about `16,000` simulated cash
- high-volatility board confirmed staged cap: `4%`, about `8,000` simulated cash
- daily new-buy review limit: `5`
- one new position per symbol

Top dry-run candidates from the plan:

| rank | symbol | signal_date | pattern | mode | max_initial_cash | caution |
| ---: | --- | --- | --- | --- | ---: | --- |
| 1 | `SH603330` | 2026-06-11 | `LEGACY_VP_SINGLE_005` | dry-run candidate | 4000 | none |
| 2 | `SH603618` | 2026-06-10 | `LEGACY_VP_SINGLE_006` | dry-run candidate | 4000 | none |
| 3 | `SZ002806` | 2026-06-10 | `LEGACY_VP_SINGLE_006` | dry-run candidate | 4000 | none |
| 4 | `SH603120` | 2026-06-11 | `LEGACY_VP_SINGLE_001` | dry-run candidate | 4000 | none |
| 5 | `SH688010` | 2026-06-11 | `LEGACY_VP_SINGLE_001` | dry-run candidate | 2000 | high-volatility board |
| 6 | `SZ301323` | 2026-06-11 | `LEGACY_VP_SINGLE_001` | dry-run candidate | 2000 | high-volatility board |
| 7 | `SH688108` | 2026-06-10 | `LEGACY_VP_SINGLE_006` | dry-run candidate | 2000 | high-volatility board |
| 8 | `SZ301348` | 2026-06-10 | `LEGACY_VP_SINGLE_006` | dry-run candidate | 2000 | high-volatility board |

Required triggers before any simulated click mode:

1. fresh trading-time risk gates;
2. Sim-Cockpit readback and window verification;
3. `strong_reclaim` or the selected strategy's explicit confirmation rule.

New safety behavior:

- individual stale signals are blocked even if the overall cache is fresh;
- Dataset1 distribution or stall risk is a blocker, not a soft caution;
- high-volatility boards remain eligible for review only with smaller simulated
  probes;
- the plan can rank candidates and guide dry-runs, but cannot submit orders,
  change `rules.yaml`, enable screen click, or change live-trading settings.

## API And CLI Handoff

Implemented a read-only handoff for the latest simulation review plan:

- API: `GET /api/research/offhour/simulation-review-plan/latest?limit=5`
- CLI: `python backend/scripts/automation_loop.py --mode offhour-simulation-review-plan --limit 5`

The endpoint reads the latest ignored model-candidate artifact, extracts
`simulation_review_plan.v1`, bounds the returned candidate list, and returns
portfolio limits, permission policy, strategy overlays, freshness metadata, and
supervisor notes.

Safety contract:

- health must be checked first;
- `may_submit_order=false`;
- `may_enable_screen_click=false`;
- `review_only=true`;
- `simulation_only=true`;
- `live_trading_enabled=false`.

Validation note:

- the existing port `8000` process was stale after code edits and returned
  `404` for the new endpoint until reload;
- a temporary current-code FastAPI process on port `8011` passed `/health`, API
  smoke, and CLI smoke;
- tomorrow's automation should reload or restart the backend before relying on
  the new route.

## Run 84 Evidence-Quality Ranking

Added `simulation_candidate_evidence_quality.v1` to each generated simulation
review candidate. This separates raw priority from evidence quality, so a
candidate with attractive return evidence is still downgraded when it has stale
signals, sample gaps, weak walk-forward evidence, market-context warnings,
Dataset1 distribution/stall risk, or high-volatility-board caution.

Implementation effect:

- each candidate now has `evidence_quality.confidence_score`;
- each candidate now has `evidence_quality.confidence_tier`;
- each candidate now has `confidence_adjusted_priority_score`;
- candidate ordering now prioritizes blockers, confidence score,
  confidence-adjusted score, then raw priority;
- this changes review ranking only and does not change order permission,
  position sizing permission, `rules.yaml`, or live-trading state.

Main DB validation:

- `run_id=84`
- `live_trading_enabled=false`
- `artifact=backend/output/model_candidates/offhour_model_candidate_39fedd9fd9d2.json`
- `simulation_review_plan.status=ready_for_dry_run_review`
- `candidate_count=8`
- `ready_dry_run_candidate_count=8`

Top candidates after evidence-quality ranking:

| rank | symbol | mode | confidence_tier | confidence_score | priority_score | confidence_adjusted_priority_score | caution |
| ---: | --- | --- | --- | ---: | ---: | ---: | --- |
| 1 | `SH603120` | `dry_run_screen_candidate` | `high_confidence_dry_run_review` | 83 | 182.849948 | 151.765457 | none |
| 2 | `SH603330` | `dry_run_screen_candidate` | `medium_confidence_dry_run_review` | 79 | 185.349948 | 146.426459 | none |
| 3 | `SH603618` | `dry_run_screen_candidate` | `medium_confidence_dry_run_review` | 79 | 184.849948 | 146.031459 | none |
| 4 | `SZ002806` | `dry_run_screen_candidate` | `medium_confidence_dry_run_review` | 79 | 184.849948 | 146.031459 | none |
| 5 | `SH603186` | `dry_run_screen_candidate` | `medium_confidence_dry_run_review` | 79 | 179.171054 | 141.545133 | none |
| 6 | `SH688010` | `dry_run_screen_candidate` | `medium_confidence_dry_run_review` | 77 | 182.349948 | 140.409460 | high-volatility board |
| 7 | `SZ301323` | `dry_run_screen_candidate` | `medium_confidence_dry_run_review` | 77 | 182.349948 | 140.409460 | high-volatility board |
| 8 | `SZ300377` | `dry_run_screen_candidate` | `medium_confidence_dry_run_review` | 77 | 181.171054 | 139.501712 | high-volatility board |

Interpretation:

The system no longer lets raw backtest return dominate the next-session review
queue. `SH603120` moved above higher raw-priority candidates because its
evidence-quality tier is stronger. High-volatility-board candidates remain
eligible for review, but their confidence and first-probe cash stay lower.

Tomorrow's practical rule:

1. start with `SH603120` for manual review and dry-run planning;
2. keep `SH603330`, `SH603618`, `SZ002806`, and `SH603186` as medium-confidence
   backup candidates;
3. treat `SH688010`, `SZ301323`, and `SZ300377` as smaller-probe candidates
   only because of board volatility;
4. do not enter screen-click simulation until fresh trading-time risk gates,
   Sim-Cockpit verification/readback, coordinate anchors, and explicit
   `SIMULATION_SCREEN_CLICK` all pass.

## Dashboard And CLI Exposure

The evidence-quality ranking is now visible outside the raw artifact:

- CLI supervisor output includes
  `simulation_review_plan_supervisor_summary.v1`, with confidence-tier counts,
  top candidates, confidence-adjusted priority, blockers, caution flags, and
  max initial simulated cash.
- The V5.7 dashboard panel loads
  `/api/research/offhour/simulation-review-plan/latest?limit=8` when available,
  and falls back to the latest model-candidate artifact when the current
  backend process has not been restarted yet.
- The dashboard shows the plan status, ready/total candidate count, tier mix,
  submit/screen-click permission flags, and each candidate's confidence tier,
  confidence score, adjusted/raw priority, position cap, win rate, average
  return, blockers, and caution flags.

This makes tomorrow's supervision loop concrete: Codex should rank candidates
by evidence quality first, then raw return/priority. `high_confidence` can enter
manual review and dry-run planning; `medium_confidence` stays as backup; high
volatility or caution-tag candidates remain smaller-probe only.

## Planner Review-Note Integration

The latest simulation review plan is now also read by `SimulationPlanner` as a
symbol-level review note. When a symbol appears in the latest
`simulation_review_plan.v1`, generated simulation plans can show its confidence
tier, confidence score, adjusted/raw priority, max initial simulated cash,
strategy evidence, blockers, caution flags, and submit/screen-click permission
flags.

This integration is deliberately explanatory:

- it does not change `action`;
- it does not change `allowed`;
- it does not change `quantity`;
- it does not change `position_ratio`;
- it does not bypass risk gates;
- it does not enable screen-click mode;
- it does not modify production rules.

The reason for adding this layer is supervision quality. During trading-time
simulation review, Codex and the dashboard can see whether a generated buy or
observe plan is backed by the off-hour evidence-quality ranking, without
letting that ranking grant permission by itself.

Validation detail:

- the real latest run stores `simulation_review_plan.v1` under
  `offhour_research_runs.artifact_json`, not `backtest_json`;
- `SimulationPlanner` now reads that real storage path first and keeps
  `backtest_json` as a compatibility fallback;
- local smoke for `SH603120` found the run 84 high-confidence note:
  `confidence_tier=high_confidence_dry_run_review`,
  `confidence_score=83.0`, `max_initial_cash=4000.0`,
  `submit=False`, `screen_click=False`.

## Sim-Cockpit Dry-Run Sampling Integration

The latest off-hour simulation review plan now feeds the Sim-Cockpit supervised
cycle as review-only dry-run samples. When a verified simulated Tonghuashun
window exists, `simulation_cockpit_run` can record
`offhour_simulation_review_plan` buy dry-runs for Dataset2 evidence collection.
These samples write `sim_cockpit_actions` and `sim_cockpit_readbacks`; they do
not submit orders.

Important safeguards:

- `risk_result.simulation_allowed=false` and `all_gates_passed=false` remain set
  for off-hour review-plan samples;
- `permission_policy.may_submit_order=false` and `may_enable_screen_click=false`
  are preserved from the review plan;
- execution mode remains `dry_run_screen`;
- real screen click execution remains false;
- the latest simulation review plan can affect review priority and training
  samples only, not action permission.

Position-width adjustment:

`SH603120` was initially skipped by the 2% first-probe cash cap because 100
shares at `52.58` costs about `5258`, slightly above `4000`. Since the simulated
account reference cash is `200000`, the system now allows a one-lot dry-run
minimum probe only for high-confidence, non-high-volatility candidates when the
one-lot notional remains inside the existing 3% simulated screen-click cap. The
candidate is marked with `lot_rounding_minimum_probe=true`, so Codex can see
that the dry-run is a lot-size accommodation rather than a broader position-size
permission.

Runtime consistency fix:

The default `DATABASE_PATH` now resolves relative to the repository root instead
of the process working directory. This prevents the backend, CLI, and manual
Python service calls from splitting evidence across both
`trading_local.sqlite3` and `backend/trading_local.sqlite3`.

## Strategy Learning Supervisor Packet

The latest off-hour artifact is now exposed as a compact strategy-learning
packet:

- API: `/api/research/offhour/strategy-learning-packet/latest?limit=...`
- CLI: `automation_loop.py --mode offhour-strategy-learning-packet`
- schema: `offhour_strategy_learning_supervisor_packet.v1`

The packet combines:

- Dataset2 stable-candidate validation and walk-forward evidence;
- Dataset2 rule-family performance memory;
- Dataset1 focus-phase and phase-similarity constraints;
- loss attribution and parameter-failure attribution;
- the latest simulation-review candidates and next-session validation checklist.

Current Run 84 interpretation from the packet:

- `learning_readiness=ready_for_supervised_dry_run_learning`;
- selected stable candidate validation return is `203.48932%`;
- selected stable candidate validation win rate is `0.8`;
- the 20% review target is passed as evidence for supervised simulation learning;
- top dry-run learning candidate remains `SH603120`;
- medium-confidence backups are `SH603330`, `SH603618`, and `SZ002806`.

The packet now separates learning readiness from real-money human-confirmation
readiness. For the current database snapshot:

- `human_confirm_readiness.status=not_ready_for_human_confirm`;
- supervised off-hour dry-run sample count is `0`;
- supervised readback count is `0`;
- unique supervised symbol coverage is `0`;
- missing requirements are supervised dry-run samples, supervised readbacks,
  multi-symbol coverage, and multi-session outcome review.

Minimum simulated evidence targets before even discussing real-money
human-confirmation readiness:

- at least `20` supervised dry-run samples;
- at least `20` supervised readbacks;
- at least `3` unique symbols;
- at least `5` evaluated sessions;
- simulated win rate target `>=65%`;
- average simulated return target `>=5%`;
- average drawdown target `<=6%`.

Dry-run outcome review:

The packet now evaluates supervised Sim-Cockpit dry-run buy actions against
future local `daily_bar_cache` rows. For each recorded dry-run action it can
calculate 1-day, 3-day, and 5-day simulated returns, max return, and max
drawdown. If fewer than five future bars are available, the action remains
`pending_future_bars`; the system must not invent returns.

Current local snapshot still has no supervised off-hour dry-run actions, so:

- `simulation_training_evidence.dry_run_count=0`;
- `simulation_training_evidence.readback_count=0`;
- `outcome_review.status=pending`;
- `outcome_review.evaluated_session_count=0`.

Confidence calibration:

The packet now includes `strategy_learning_confidence_calibration.v1`, a
100-point reporting-only score that combines offline strategy evidence, rule
family memory, candidate quality, simulation execution evidence, and simulation
outcome evidence. Current local score is `75/100`:

- offline strategy evidence: `35/35`;
- rule-family evidence: `20/20`;
- candidate quality: `20/20`;
- simulation execution evidence: `0/15`;
- simulation outcome evidence: `0/10`;
- tier: `backtest_ready_simulation_needed`.

This is the intended interpretation: the historical strategy case is strong
enough to justify supervised dry-run learning, but not strong enough to open
human-confirm or screen-click authority. The missing pieces are still
supervised dry-runs, readbacks, multi-symbol coverage, multi-session outcome
review, simulated win rate, simulated average return, and drawdown evidence.

Simulation training plan:

The packet now also includes `strategy_learning_simulation_training_plan.v1`.
It converts the missing evidence into a bounded sample-collection queue. The
plan reports current counts, remaining requirements, candidate-level next dry-run
sample targets, required readbacks, outcome windows, and stop conditions. It is
instructional only:

- `allowed_effect=sample_collection_plan_only`;
- `do_not_submit_orders_from_this_plan=true`;
- every sample still requires `/health.live_trading_enabled=false`,
  simulated-window verification, fresh risk gates, dry-run audit logging, and
  readback;
- the queue may prioritize `SH603120`, but it cannot override symbol diversity,
  stale data, risk gates, or screen-click permissions.

CLI supervision shortcut:

`automation_loop.py --mode offhour-training-plan-summary` now extracts a compact
supervisor summary from the full learning packet. Current local output keeps the
same `confidence_score=75`, `confidence_tier=backtest_ready_simulation_needed`,
and `human_confirm_status=not_ready_for_human_confirm`, while making the next
batch explicit:

- total next dry-run sample target: `20`;
- `SH603120`: `8` dry-run/readback samples;
- `SH603330`: `6` dry-run/readback samples;
- `SH603618`: `6` dry-run/readback samples;
- extra candidates remain visible for later diversity, but the first batch is
  already spread across 3 symbols.

The shortcut still checks `/health` first and returns
`live_trading_enabled=false`; it is a supervisor summary only, not a run command
for orders or screen clicks.

Trading-time supervised cycle integration:

`automation_loop.py --mode sim-cockpit-supervised-cycle` now includes the same
compact training plan plus `sim_cockpit_supervised_sample_gate.v1`. The gate
joins three things in one place:

- Sim-Cockpit window detection status;
- current simulated-cockpit status;
- next-batch Dataset1/Dataset2 training sample queue.

Current local run status is blocked because no Tonghuashun simulated window was
detected:

- `supervised_sample_gate.status=blocked`;
- blocked by `window_detection_not_verified` and
  `sim_cockpit_status_not_verified`;
- next sample symbols are still visible as `SH603120:8`, `SH603330:6`,
  `SH603618:6`;
- `can_submit_order=false`;
- `can_enable_screen_click=false`.

This keeps the old no-order diagnosis discipline intact: first confirm whether
the window and gates are valid, then check whether there is an executable dry-run
sample target. Do not blame or debug screen clicking before those gates pass.

Current safety summary:

The supervised cycle now emits `sim_cockpit_current_safety_summary.v1` to avoid
confusing historical actions with current permission. In the current local run,
historical Sim-Cockpit action `id=6` did record a simulated screen click in the
past, but the current gate is still blocked:

- `current_window_verified=false`;
- `current_dry_run_collection_ready=false`;
- `current_order_submission_allowed=false`;
- `current_screen_click_allowed=false`;
- latest verification is blocked by missing Tonghuashun process/window text.

This means past successful simulation-click evidence can be used as training
context, but it cannot be reused as current authorization. Current authorization
must come from the latest window verification and sample gate.

This makes the next training task concrete: first verify the simulated
Tonghuashun window, then collect dry-run/readback samples for `SH603120` and
backup candidates, then let the outcome review convert those samples into
measured simulated win-rate, return, and drawdown evidence.

This is a learning and supervision artifact only. Passing the 20% review target
does not grant real-money permission, does not enable screen clicks, does not
write model artifacts, and does not modify `rules.yaml`. It says the next useful
step is to verify the simulated Tonghuashun window, collect dry-run/readback
evidence, and evaluate the simulated outcome over multiple sessions.

Window readiness checklist:

`automation_loop.py --mode sim-cockpit-supervised-cycle` now also emits
`sim_cockpit_window_readiness_checklist.v1`. This is a machine-readable operator
checklist for the exact step that was still ambiguous before: whether the current
desktop state is ready for supervised dry-run sample collection.

The checklist deliberately separates three different ideas:

- current simulated-window evidence;
- dry-run sample collection readiness;
- order or screen-click authority.

Even when all checklist items pass, it can only set
`can_collect_dry_run_samples=true`. It must keep `can_submit_order=false` and
`can_enable_screen_click=false` unless a separate reviewed simulation-only
screen-click gate is satisfied.

The current local run is blocked at the window-detection stage:

- Tonghuashun process/window text is not currently verified;
- no simulation marker is currently verified;
- no coordinate anchors are currently available;
- dangerous real-account terms are absent;
- the safe next action is to open Tonghuashun, switch to the simulated `mncg`
  window, and rerun the supervised cycle.

Browser and dataset learning synthesis:

Public references checked on 2026-06-15:

- VectorBT docs: https://vectorbt.dev/
- QuantStart event-driven backtesting article:
  https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-I/
- Shanghai Stock Exchange trading mechanism:
  https://english.sse.com.cn/start/trading/mechanism/
- Shenzhen Stock Exchange trading overview:
  https://www.szse.cn/English/services/trading/tradOverview/index.html

Engineering lessons from those references:

- Use vectorized/batch experimentation for wide parameter search, but never let
  speed replace chronological validation.
- Use event-driven replay for credibility: market event -> signal event -> risk
  gate -> simulated execution event -> readback/outcome event.
- Keep A-share execution constraints inside every backtest and simulation:
  100-share buy units, price/time priority, daily price limits, special handling
  for price-limit blocks, turnover/liquidity limits, fees, tax, slippage, and
  T+1-style sellability constraints.

Dataset1 learning:

Dataset1 should be treated as experience priors, not as direct model training
labels. The strongest reusable rules are:

- Prefer low-position, first-limit-up or recently activated candidates with
  moderate market cap and reasonable PB.
- Treat main-force cost-line analysis as long-horizon phase context: estimated
  operating cost and target zones can guide attention, but cannot override fresh
  risk gates.
- Entry quality matters more than eagerness: wait for forced-divergence points,
  moving-average stabilization, pullback washout, or near-close confirmation
  instead of buying too early into hard boards.
- Add positions in stages only after confirmation and readback; do not average
  down before the expected divergence/support area is actually reached.
- Exit discipline is part of the alpha: auction/open sell rules, before-10:30
  high-sell rules, staged profit-taking, big-rally selling, partial limit-up
  selling, and support-break stops all need to be audited as first-class rules.

Dataset2 learning:

Dataset2 should be treated as a structured rule library and weak-label source.
It contains broad volume-price pattern families, including:

- high-volume big-yang buy-candidate patterns;
- low-volume big-rise hold/trail patterns;
- high-volume stagnation and distribution warnings;
- shrinkage pullbacks and washout candidates;
- bottom/top K-line combinations;
- explicit safety patterns requiring simulation/training-only handling.

Dataset2 also has known data-quality limits. It is useful for explanation,
replay, and supervised sample design, but not yet sufficient for production model
training without normalized labels, historical instance rows, forward returns,
MFE/MAE, drawdown, benchmark regime, and out-of-sample splits.

Combined strategy framework:

The next strategy engine should score candidates through separate layers instead
of producing one opaque confidence number:

- `phase_score`: historical low position, long sideways base, prior limit-up
  memory, cost-line proximity, and main-force accumulation evidence.
- `volume_price_score`: Dataset2 volume-price rule family, volume expansion or
  shrinkage interpretation, limit-up quality, and stagnation/distribution risk.
- `entry_timing_score`: forced-divergence proximity, MA stabilization, pullback
  confirmation, near-close confirmation, and intraday failure avoidance.
- `exit_discipline_score`: staged profit-taking plan, auction/open rule,
  before-10:30 rule, support-break stop, and big-rally sell plan.
- `risk_penalty`: high-position chase, giant-volume stagnation, high PB, high
  market cap, stale data, completed distribution samples, limit-up/limit-down
  execution blocks, and insufficient liquidity.
- `execution_readiness_score`: health check, current simulated-window evidence,
  coordinate anchors, risk gates, sample gate, readback availability, and
  screen-click permission status.

Code implementation update:

`latest_strategy_learning_packet` now emits `strategy_learning_scoring_matrix.v1`.
The matrix turns the above framework into a bounded, review-only ranking for
candidate simulation learning. It scores each candidate by:

- phase evidence from Dataset1-style stabilization and validation context;
- volume-price evidence from Dataset2 rule-family memory;
- entry timing evidence from dry-run eligibility, walk-forward status, and
  blocker state;
- exit discipline evidence from small-probe sizing, staged policy, validation
  checks, and invalidation signals;
- execution readiness evidence from cash caps, training contracts, disabled live
  trading, and review priority;
- explicit risk penalties for blockers, caution flags, late-cycle/distribution
  terms, and weak global confidence.

The matrix is deliberately not a trading permission surface. Every row keeps
`may_change_strategy_weight_now=false`, `may_submit_order=false`, and
`may_enable_screen_click=false`. Its only permitted effect is to prioritize which
candidates should receive supervised detect-only or dry-run samples next.

CLI supervision update:

`automation_loop.py --mode offhour-training-plan-summary` now includes two
compact review fields:

- `strategy_scoring_matrix_summary`: the top scoring candidates, key component
  scores, risk penalties, and permission policy.
- `target_progress`: the gap between offline evidence and the real promotion
  target. It reports the 20% validation-return gate, dry-run sample count,
  readback count, unique-symbol coverage, evaluated sessions, simulated 5-day
  win rate, simulated 5-day average return, and simulated drawdown.

Current local evidence after backend reload:

- offline 20% validation-return gate: passed;
- stable candidate validation return: about `203.49%`;
- stable candidate validation win rate: `0.8`;
- top scoring symbol: `SH603120`;
- top scoring candidate strategy win rate: `0.8`;
- top scoring candidate average return: about `11.21%`;
- top scoring candidate supports the 20% offline target: `true`;
- supervised dry-run count: `0`;
- supervised readback count: `0`;
- unique supervised symbol count: `0`;
- evaluated session count: `0`;
- human-confirm readiness: `not_ready_for_human_confirm`.

This makes the gap visible in one CLI call: the system has strong offline
research evidence, but still lacks supervised simulation evidence.

The scoring matrix now carries per-candidate `outcome_evidence`, so a high
score must be accompanied by strategy win rate, average return, stable
validation return, stable validation win rate, and a boolean
`supports_20pct_goal`. This prevents a candidate from being promoted merely
because its rank is high. It still cannot grant permission: every candidate with
positive offline outcome evidence must pass supervised dry-run, readback,
multi-symbol, multi-session, and drawdown checks before any human-confirmation
discussion.

The packet now also carries `strategy_candidate_shadow_outcome_review.v1`.
This local-historical review checks current scored candidates against available
`daily_bar_cache` bars after their `signal_date` and reports 1/3/5-day returns,
win rate, average return, and drawdown. It is useful for learning whether the
candidate queue is improving, but it is explicitly shadow evidence:
`counts_toward_human_confirm=false` and
`allowed_effect=historical_shadow_review_only`. It cannot replace supervised
dry-run/readback evidence.

Browser research integration:

- VectorBT's official docs emphasize fast parameter-grid research over pandas
  and NumPy objects. This supports our current offline role: use broad grids to
  identify robust candidates, then require slower supervised simulation evidence
  before any permission changes. Source: https://vectorbt.dev/
- QSTrader's public project positions itself as a modular schedule-driven
  backtesting framework. This matches our need to keep market events, orders,
  fills, risk gates, and audit records separated instead of treating a signal as
  an immediate trade. Source: https://github.com/mhallsmoore/qstrader
- A-share price-limit research warns that upper-limit events can attract
  short-horizon buying and next-day selling by large investors. In our strategy
  language, a limit-up or near-limit-up is evidence of strength only when paired
  with phase context, liquidity, non-distribution evidence, next-session
  confirmation, and exit discipline. Source:
  https://www.princeton.edu/~wxiong/papers/PriceLimit.pdf
- China A-share price-limit studies also highlight delayed price discovery and
  possible volatility spillover after upper-limit hits. For this project, that
  reinforces the need to track stale/blocked execution, limit-up buy rejection,
  limit-down sell blockage, and shadow 1/3/5-day outcome review instead of
  treating a limit-up hit as clean execution evidence. Source:
  https://eprints.whiterose.ac.uk/id/eprint/138465/1/Shuxing%20Yin%20AYYZ-Price-Limits-Paper-181013.pdf

Practical conclusion:

The project is ready to deepen simulation learning, not to loosen execution
authority. The useful next step is to collect supervised dry-run/readback samples
for the current training queue (`SH603120`, `SH603330`, `SH603618`), then evaluate
1/3/5-day simulated outcomes. Strategy weights may be proposed only after those
outcomes show stable improvement across symbols and sessions. Until then, any
20%+ offline validation result remains a research signal, not a trading
permission.

## 2026-06-18 Buy Plan Generation Repair

Problem observed:

- The automation loop could discover and score limit-up candidates, but most
  plans were downgraded to `observe` by `constitution_no_high_position` or
  `phase_guardrail`.
- Tencent quote fallback amount was interpreted as yuan, while the quote field
  is in ten-thousand yuan. This made strong turnover look tiny and prevented the
  main-force markup confirmation rule from opening a small simulation probe.
- `AutomationSupervisor` also re-applied the phase guardrail after
  `SimulationPlanner`, so even an audited simulation-only relaxation could be
  overwritten back to observe.

Implemented repair:

- Tencent fallback turnover is now converted into yuan before building
  `MarketSnapshot.amount`.
- `SimulationPlanner` can downgrade a non-extreme `phase_distribution_guardrail`
  into a 100-share simulation learning probe only when:
  - `live_trading_enabled=false`;
  - the candidate has limit-up / near-limit-up strength;
  - price is near the session high;
  - amount or volume confirms main-force markup;
  - the phase similarity score is below the extreme hard-block threshold;
  - the min-lot amount stays inside the 3% simulated-cash probe cap.
- `AutomationSupervisor` now preserves this specific audited relaxation instead
  of overwriting it back to `observe`.

Live validation after backend reload:

- `/health`: `live_trading_enabled=false`.
- `automation_loop.py --mode cycle --limit 5 --max-cycles 1` produced three
  simulation buy plans:
  - `SZ300166`: `buy`, `allowed=true`, `quantity=100`;
  - `SZ300319`: `buy`, `allowed=true`, `quantity=100`;
  - `SZ301310`: `buy`, `allowed=true`, `quantity=100`.
- `SZ301687` stayed blocked because 100 shares exceeded the 3% simulated-cash
  probe cap.
- `SH688333` stayed blocked by phase/distribution risk and high min-lot notional.

This repair improves automated simulated training readiness, but it still does
not grant screen-click permission or real-trading permission. Every generated
plan remains subject to Sim-Cockpit window verification, risk gates, readback,
and later outcome review.
