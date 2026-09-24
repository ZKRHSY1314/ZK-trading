# Monday Buy Plan 2026-06-22

Review-only / simulation-only. This file is a conditional plan, not an order list.

## Safety Gate

- live_trading_enabled_required_false: True
- writes_rules_yaml: False
- live_ordering: False

## Data

- generated_at: 2026-06-20T17:23:48
- expected_last_trade_date: 2026-06-18
- refresh_sina: True
- universe_size: 60
- action_counts: `{"watch_for_monday_confirmation": 6, "skip": 7, "avoid_chase": 47}`
- amount_proxy_used: True

## Conditional Buys

No conditional_buy candidates passed all filters. Keep plan at watch-only.

## Watch List

| rank | action | symbol | name | phase | close | avg cost | cost x | vol x | score | plan price | TP watch | main reasons |
|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | watch_for_monday_confirmation | SH603082 | 北自科技 | unknown | 41.03 | 38.03 | 1.08 | 1.54 | 63.5 | 42.26 | 98.88 | long_base_stable, price_near_base_cost, close_above_ma20, volume_ratio_below_entry_filter |
| 2 | watch_for_monday_confirmation | SZ002354 | 天娱数科 | unknown | 7.73 | 6.77 | 1.14 | 1.35 | 54.1 | 7.96 | 17.59 | long_base_stable, price_near_base_cost, close_above_ma20, volume_ratio_below_entry_filter |
| 3 | watch_for_monday_confirmation | SH600259 | 中稀有色 | unknown | 116.28 | 91.24 | 1.27 | 1.94 | 38.9 | 114.05 | 237.22 | long_base_stable, close_above_ma20, ma60_reclaim_ok, near_120d_high_chase_risk, price_not_in_pre_markup_cost_zone |
| 4 | watch_for_monday_confirmation | SH600392 | 盛和资源 | unknown | 31.66 | 25.31 | 1.25 | 2.62 | 38.6 | 31.64 | 65.81 | long_base_stable, volume_breakout_confirmed, close_above_ma20, price_not_in_pre_markup_cost_zone, return_20_overextended |
| 5 | watch_for_monday_confirmation | SH600397 | 江钨装备 | unknown | 20.20 | 15.36 | 1.31 | 2.55 | 35.2 | 19.21 | 39.95 | long_base_stable, volume_breakout_confirmed, close_above_ma20, price_not_in_pre_markup_cost_zone, return_20_overextended |
| 6 | watch_for_monday_confirmation | SZ002842 | 翔鹭钨业 | unknown | 47.72 | 35.51 | 1.34 | 1.69 | 23.6 | 44.39 | 92.33 | long_base_stable, close_above_ma20, ma60_reclaim_ok, near_120d_high_chase_risk, price_not_in_pre_markup_cost_zone |

## Avoid Chasing

| rank | action | symbol | name | phase | close | avg cost | cost x | vol x | score | plan price | TP watch | main reasons |
|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | avoid_chase | SH688729 | 屹唐股份 | unknown | 33.07 | 25.74 | 1.28 | 3.49 | 48.9 | 32.18 | 66.93 | long_base_stable, volume_breakout_confirmed, close_above_ma20, near_120d_high_chase_risk, price_not_in_pre_markup_cost_zone |
| 2 | avoid_chase | SH688671 | 碧兴物联 | unknown | 30.78 | 24.03 | 1.28 | 2.06 | 43.8 | 30.03 | 62.47 | long_base_stable, volume_breakout_confirmed, close_above_ma20, near_120d_high_chase_risk, price_not_in_pre_markup_cost_zone |
| 3 | avoid_chase | SH688108 | 赛诺医疗 | 出货后观察 | 20.16 | 20.97 | 0.96 | 0.78 | 40.7 | 20.76 | 54.51 | long_base_stable, close_above_ma20, not_single_day_chase, close_below_ma60_reclaim_zone, phase_risk:post_distribution_watch |
| 4 | avoid_chase | SZ300861 | 美畅股份 | unknown | 24.32 | 18.30 | 1.33 | 1.97 | 39.7 | 22.87 | 47.58 | long_base_stable, close_above_ma20, ma60_reclaim_ok, near_120d_high_chase_risk, price_not_in_pre_markup_cost_zone |
| 5 | avoid_chase | SH688333 | 铂力特 | 出货后观察 | 107.28 | 98.19 | 1.09 | 1.98 | 39.6 | 110.50 | 255.28 | long_base_stable, price_near_base_cost, close_above_ma20, phase_risk:post_distribution_watch, single_day_chase_too_high |
| 6 | avoid_chase | SZ301360 | 荣旗科技 | 出货后观察 | 78.29 | 75.20 | 1.04 | 0.56 | 37.5 | 80.64 | 195.52 | long_base_stable, price_near_base_cost, close_above_ma20, phase_risk:post_distribution_watch, volume_ratio_below_entry_filter |
| 7 | avoid_chase | SH688126 | 沪硅产业 | 拉升 | 32.20 | 22.37 | 1.44 | 0.93 | 34.7 | 27.96 | 58.16 | close_above_ma20, ma60_reclaim_ok, not_single_day_chase, base_not_stable_enough, price_not_in_pre_markup_cost_zone |
| 8 | avoid_chase | SZ301348 | 蓝箭电子 | 出货后观察 | 28.20 | 26.23 | 1.07 | 0.93 | 34.3 | 29.05 | 68.20 | long_base_stable, price_near_base_cost, close_above_ma20, phase_risk:post_distribution_watch, volume_ratio_below_entry_filter |

## Monday Execution Conditions

These conditions are for simulation/review only:

1. Do not act before 09:35. Require opening auction and first minutes to confirm price is not a one-day chase.
2. For a conditional_buy candidate, simulated entry is allowed only if opening gap is <= 3%, price stays <= plan price, and first-30-minute volume confirms active demand.
3. Reject immediately if price is at/near limit-up with no liquidity, intraday upper-shadow distribution appears, or price reaches the invalid 2.30x cost warning zone.
4. Split the simulated position: 50% fixed track with 15% take-profit, 8% stop-loss, 5-day max hold; 50% runner track with 2.45x/2.60x staged exits.
5. Total simulated exposure should remain capped; no real order, no broker API, no Tonghuashun click.

## Full Result JSON

```json
{
  "plan_date": "2026-06-22",
  "expected_last_trade_date": "2026-06-18",
  "action_counts": {
    "watch_for_monday_confirmation": 6,
    "skip": 7,
    "avoid_chase": 47
  },
  "conditional_buy": [],
  "watch": [
    {
      "symbol": "SH603082",
      "name": "北自科技",
      "source": "sina.cn.kline_daily_fallback",
      "candidate_best_score": 123.3915,
      "status": "watch",
      "action": "watch_for_monday_confirmation",
      "score": 63.5156,
      "latest_date": "2026-06-18",
      "latest_close": 41.03,
      "latest_volume_ratio": 1.5352,
      "daily_return_pct": 10.0,
      "upper_shadow_pct": 0.0,
      "return_20_pct": -4.1355,
      "return_60_pct": 16.6288,
      "position_120": 0.4645,
      "latest_phase": null,
      "latest_phase_name": "unknown",
      "base_len": 240,
      "base_start": "2025-06-23",
      "base_end": "2026-06-17",
      "avg_cost": 38.0297,
      "price_multiple": 1.0789,
      "base_cv": 0.0649,
      "base_range_pct": 57.963,
      "target_245": 93.1727,
      "target_260": 98.8771,
      "max_buy_price": 42.2609,
      "invalid_price_gte": 87.4682,
      "positive": [
        "long_base_stable",
        "price_near_base_cost",
        "close_above_ma20",
        "ma60_reclaim_ok",
        "not_single_day_chase",
        "upper_shadow_ok"
      ],
      "reasons": [
        "volume_ratio_below_entry_filter"
      ],
      "warnings": [
        "phase_unknown_or_unmatched:None"
      ],
      "amount_proxy_used": true
    },
    {
      "symbol": "SZ002354",
      "name": "天娱数科",
      "source": "sina.cn.kline_daily_fallback",
      "candidate_best_score": 127.1337,
      "status": "watch",
      "action": "watch_for_monday_confirmation",
      "score": 54.1037,
      "latest_date": "2026-06-18",
      "latest_close": 7.73,
      "latest_volume_ratio": 1.3523,
      "daily_return_pct": 9.9573,
      "upper_shadow_pct": 0.0,
      "return_20_pct": 13.6765,
      "return_60_pct": 33.506,
      "position_120": 0.6752,
      "latest_phase": null,
      "latest_phase_name": "unknown",
      "base_len": 200,
      "base_start": "2025-08-18",
      "base_end": "2026-06-17",
      "avg_cost": 6.7664,
      "price_multiple": 1.1424,
      "base_cv": 0.1022,
      "base_range_pct": 63.9556,
      "target_245": 16.5776,
      "target_260": 17.5925,
      "max_buy_price": 7.9619,
      "invalid_price_gte": 15.5626,
      "positive": [
        "long_base_stable",
        "price_near_base_cost",
        "close_above_ma20",
        "ma60_reclaim_ok",
        "not_single_day_chase",
        "upper_shadow_ok"
      ],
      "reasons": [
        "volume_ratio_below_entry_filter"
      ],
      "warnings": [
        "phase_unknown_or_unmatched:None"
      ],
      "amount_proxy_used": true
    },
    {
      "symbol": "SH600259",
      "name": "中稀有色",
      "source": "sina.cn.kline_daily_fallback",
      "candidate_best_score": 122.395,
      "status": "watch",
      "action": "watch_for_monday_confirmation",
      "score": 38.9205,
      "latest_date": "2026-06-18",
      "latest_close": 116.28,
      "latest_volume_ratio": 1.9401,
      "daily_return_pct": 9.9991,
      "upper_shadow_pct": 0.0,
      "return_20_pct": 33.886,
      "return_60_pct": 45.8971,
      "position_120": 1.0,
      "latest_phase": null,
      "latest_phase_name": "unknown",
      "base_len": 80,
      "base_start": "2026-02-12",
      "base_end": "2026-06-17",
      "avg_cost": 91.2396,
      "price_multiple": 1.2744,
      "base_cv": 0.0915,
      "base_range_pct": 49.5406,
      "target_245": 223.5371,
      "target_260": 237.223,
      "max_buy_price": 114.0495,
      "invalid_price_gte": 209.8511,
      "positive": [
        "long_base_stable",
        "close_above_ma20",
        "ma60_reclaim_ok",
        "not_single_day_chase",
        "upper_shadow_ok"
      ],
      "reasons": [
        "near_120d_high_chase_risk",
        "price_not_in_pre_markup_cost_zone",
        "volume_ratio_below_entry_filter"
      ],
      "warnings": [
        "phase_unknown_or_unmatched:None"
      ],
      "amount_proxy_used": true
    },
    {
      "symbol": "SH600392",
      "name": "盛和资源",
      "source": "sina.cn.kline_daily_fallback",
      "candidate_best_score": 125.06,
      "status": "watch",
      "action": "watch_for_monday_confirmation",
      "score": 38.6144,
      "latest_date": "2026-06-18",
      "latest_close": 31.66,
      "latest_volume_ratio": 2.6161,
      "daily_return_pct": 10.0069,
      "upper_shadow_pct": 0.0,
      "return_20_pct": 37.2345,
      "return_60_pct": 42.2921,
      "position_120": 0.8531,
      "latest_phase": null,
      "latest_phase_name": "unknown",
      "base_len": 80,
      "base_start": "2026-02-12",
      "base_end": "2026-06-17",
      "avg_cost": 25.3101,
      "price_multiple": 1.2509,
      "base_cv": 0.1064,
      "base_range_pct": 57.1629,
      "target_245": 62.0098,
      "target_260": 65.8063,
      "max_buy_price": 31.6377,
      "invalid_price_gte": 58.2133,
      "positive": [
        "long_base_stable",
        "volume_breakout_confirmed",
        "close_above_ma20",
        "ma60_reclaim_ok",
        "not_single_day_chase",
        "upper_shadow_ok"
      ],
      "reasons": [
        "price_not_in_pre_markup_cost_zone",
        "return_20_overextended"
      ],
      "warnings": [
        "phase_unknown_or_unmatched:None"
      ],
      "amount_proxy_used": true
    },
    {
      "symbol": "SH600397",
      "name": "江钨装备",
      "source": "sina.cn.kline_daily_fallback",
      "candidate_best_score": 124.9257,
      "status": "watch",
      "action": "watch_for_monday_confirmation",
      "score": 35.173,
      "latest_date": "2026-06-18",
      "latest_close": 20.2,
      "latest_volume_ratio": 2.5462,
      "daily_return_pct": 10.0218,
      "upper_shadow_pct": 0.0,
      "return_20_pct": 58.1832,
      "return_60_pct": 30.2386,
      "position_120": 0.85,
      "latest_phase": null,
      "latest_phase_name": "unknown",
      "base_len": 80,
      "base_start": "2026-02-12",
      "base_end": "2026-06-17",
      "avg_cost": 15.3642,
      "price_multiple": 1.3147,
      "base_cv": 0.1321,
      "base_range_pct": 68.5983,
      "target_245": 37.6424,
      "target_260": 39.947,
      "max_buy_price": 19.2053,
      "invalid_price_gte": 35.3378,
      "positive": [
        "long_base_stable",
        "volume_breakout_confirmed",
        "close_above_ma20",
        "ma60_reclaim_ok",
        "not_single_day_chase",
        "upper_shadow_ok"
      ],
      "reasons": [
        "price_not_in_pre_markup_cost_zone",
        "return_20_overextended"
      ],
      "warnings": [
        "phase_unknown_or_unmatched:None"
      ],
      "amount_proxy_used": true
    },
    {
      "symbol": "SZ002842",
      "name": "翔鹭钨业",
      "source": "sina.cn.kline_daily_fallback",
      "candidate_best_score": 132.5,
      "status": "watch",
      "action": "watch_for_monday_confirmation",
      "score": 23.6102,
      "latest_date": "2026-06-18",
      "latest_close": 47.72,
      "latest_volume_ratio": 1.6851,
      "daily_return_pct": 10.0046,
      "upper_shadow_pct": 0.0,
      "return_20_pct": 49.125,
      "return_60_pct": 50.5363,
      "position_120": 0.9788,
      "latest_phase": null,
      "latest_phase_name": "unknown",
      "base_len": 80,
      "base_start": "2026-02-12",
      "base_end": "2026-06-17",
      "avg_cost": 35.5121,
      "price_multiple": 1.3438,
      "base_cv": 0.1143,
      "base_range_pct": 53.8845,
      "target_245": 87.0047,
      "target_260": 92.3315,
      "max_buy_price": 44.3902,
      "invalid_price_gte": 81.6779,
      "positive": [
        "long_base_stable",
        "close_above_ma20",
        "ma60_reclaim_ok",
        "not_single_day_chase",
        "upper_shadow_ok"
      ],
      "reasons": [
        "near_120d_high_chase_risk",
        "price_not_in_pre_markup_cost_zone",
        "return_20_overextended",
        "volume_ratio_below_entry_filter"
      ],
      "warnings": [
        "phase_unknown_or_unmatched:None"
      ],
      "amount_proxy_used": true
    }
  ],
  "avoid_chase": [
    {
      "symbol": "SH688729",
      "name": "屹唐股份",
      "source": "sina.cn.kline_daily_fallback",
      "candidate_best_score": 140.9392,
      "status": "risk_reject",
      "action": "avoid_chase",
      "score": 48.9279,
      "latest_date": "2026-06-18",
      "latest_close": 33.07,
      "latest_volume_ratio": 3.4897,
      "daily_return_pct": 19.9927,
      "upper_shadow_pct": 0.0,
      "return_20_pct": 17.3111,
      "return_60_pct": 43.3463,
      "position_120": 1.0,
      "latest_phase": null,
      "latest_phase_name": "unknown",
      "base_len": 200,
      "base_start": "2025-08-18",
      "base_end": "2026-06-17",
      "avg_cost": 25.7422,
      "price_multiple": 1.2847,
      "base_cv": 0.0841,
      "base_range_pct": 50.2086,
      "target_245": 63.0685,
      "target_260": 66.9299,
      "max_buy_price": 32.1778,
      "invalid_price_gte": 59.2072,
      "positive": [
        "long_base_stable",
        "volume_breakout_confirmed",
        "close_above_ma20",
        "ma60_reclaim_ok",
        "upper_shadow_ok"
      ],
      "reasons": [
        "near_120d_high_chase_risk",
        "price_not_in_pre_markup_cost_zone",
        "single_day_chase_too_high"
      ],
      "warnings": [
        "phase_unknown_or_unmatched:None"
      ],
      "amount_proxy_used": true
    },
    {
      "symbol": "SH688671",
      "name": "碧兴物联",
      "source": "sina.cn.kline_daily_fallback",
      "candidate_best_score": 126.6137,
      "status": "risk_reject",
      "action": "avoid_chase",
      "score": 43.7618,
      "latest_date": "2026-06-18",
      "latest_close": 30.78,
      "latest_volume_ratio": 2.056,
      "daily_return_pct": 20.0,
      "upper_shadow_pct": 0.0,
      "return_20_pct": 22.3857,
      "return_60_pct": 41.1927,
      "position_120": 1.0,
      "latest_phase": null,
      "latest_phase_name": "unknown",
      "base_len": 160,
      "base_start": "2025-10-21",
      "base_end": "2026-06-17",
      "avg_cost": 24.0271,
      "price_multiple": 1.2811,
      "base_cv": 0.0765,
      "base_range_pct": 44.6078,
      "target_245": 58.8665,
      "target_260": 62.4705,
      "max_buy_price": 30.0339,
      "invalid_price_gte": 55.2624,
      "positive": [
        "long_base_stable",
        "volume_breakout_confirmed",
        "close_above_ma20",
        "ma60_reclaim_ok",
        "upper_shadow_ok"
      ],
      "reasons": [
        "near_120d_high_chase_risk",
        "price_not_in_pre_markup_cost_zone",
        "single_day_chase_too_high"
      ],
      "warnings": [
        "phase_unknown_or_unmatched:None"
      ],
      "amount_proxy_used": true
    },
    {
      "symbol": "SH688108",
      "name": "赛诺医疗",
      "source": "sina.cn.kline_daily_fallback",
      "candidate_best_score": 130.0001,
      "status": "risk_reject",
      "action": "avoid_chase",
      "score": 40.6575,
      "latest_date": "2026-06-18",
      "latest_close": 20.16,
      "latest_volume_ratio": 0.775,
      "daily_return_pct": 1.0526,
      "upper_shadow_pct": 0.4464,
      "return_20_pct": -1.7544,
      "return_60_pct": -0.7874,
      "position_120": 0.3326,
      "latest_phase": "post_distribution_watch",
      "latest_phase_name": "出货后观察",
      "base_len": 80,
      "base_start": "2026-02-12",
      "base_end": "2026-06-17",
      "avg_cost": 20.9671,
      "price_multiple": 0.9615,
      "base_cv": 0.0496,
      "base_range_pct": 23.7426,
      "target_245": 51.3695,
      "target_260": 54.5145,
      "max_buy_price": 20.7648,
      "invalid_price_gte": 48.2244,
      "positive": [
        "long_base_stable",
        "close_above_ma20",
        "not_single_day_chase",
        "upper_shadow_ok"
      ],
      "reasons": [
        "close_below_ma60_reclaim_zone",
        "phase_risk:post_distribution_watch",
        "price_not_in_pre_markup_cost_zone",
        "volume_ratio_below_entry_filter"
      ],
      "warnings": [],
      "amount_proxy_used": true
    },
    {
      "symbol": "SZ300861",
      "name": "美畅股份",
      "source": "sina.cn.kline_daily_fallback",
      "candidate_best_score": 127.8254,
      "status": "risk_reject",
      "action": "avoid_chase",
      "score": 39.7259,
      "latest_date": "2026-06-18",
      "latest_close": 24.32,
      "latest_volume_ratio": 1.9742,
      "daily_return_pct": 19.9803,
      "upper_shadow_pct": 0.0,
      "return_20_pct": 19.862,
      "return_60_pct": 43.3117,
      "position_120": 1.0,
      "latest_phase": null,
      "latest_phase_name": "unknown",
      "base_len": 80,
      "base_start": "2026-02-12",
      "base_end": "2026-06-17",
      "avg_cost": 18.2986,
      "price_multiple": 1.3291,
      "base_cv": 0.0965,
      "base_range_pct": 42.607,
      "target_245": 44.8316,
      "target_260": 47.5764,
      "max_buy_price": 22.8733,
      "invalid_price_gte": 42.0868,
      "positive": [
        "long_base_stable",
        "close_above_ma20",
        "ma60_reclaim_ok",
        "upper_shadow_ok"
      ],
      "reasons": [
        "near_120d_high_chase_risk",
        "price_not_in_pre_markup_cost_zone",
        "single_day_chase_too_high",
        "volume_ratio_below_entry_filter"
      ],
      "warnings": [
        "phase_unknown_or_unmatched:None"
      ],
      "amount_proxy_used": true
    },
    {
      "symbol": "SH688333",
      "name": "铂力特",
      "source": "sina.cn.kline_daily_fallback",
      "candidate_best_score": 133.36,
      "status": "risk_reject",
      "action": "avoid_chase",
      "score": 39.5708,
      "latest_date": "2026-06-18",
      "latest_close": 107.28,
      "latest_volume_ratio": 1.9827,
      "daily_return_pct": 20.0,
      "upper_shadow_pct": 0.0,
      "return_20_pct": 23.9945,
      "return_60_pct": 17.8254,
      "position_120": 0.5086,
      "latest_phase": "post_distribution_watch",
      "latest_phase_name": "出货后观察",
      "base_len": 120,
      "base_start": "2025-12-16",
      "base_end": "2026-06-17",
      "avg_cost": 98.1851,
      "price_multiple": 1.0926,
      "base_cv": 0.1191,
      "base_range_pct": 89.4516,
      "target_245": 240.5535,
      "target_260": 255.2812,
      "max_buy_price": 110.4984,
      "invalid_price_gte": 225.8257,
      "positive": [
        "long_base_stable",
        "price_near_base_cost",
        "close_above_ma20",
        "ma60_reclaim_ok",
        "upper_shadow_ok"
      ],
      "reasons": [
        "phase_risk:post_distribution_watch",
        "single_day_chase_too_high",
        "volume_ratio_below_entry_filter"
      ],
      "warnings": [],
      "amount_proxy_used": true
    },
    {
      "symbol": "SZ301360",
      "name": "荣旗科技",
      "source": "sina.cn.kline_daily_fallback",
      "candidate_best_score": 126.5542,
      "status": "risk_reject",
      "action": "avoid_chase",
      "score": 37.5413,
      "latest_date": "2026-06-18",
      "latest_close": 78.29,
      "latest_volume_ratio": 0.5643,
      "daily_return_pct": 1.5962,
      "upper_shadow_pct": 1.2645,
      "return_20_pct": -11.1653,
      "return_60_pct": 16.503,
      "position_120": 0.5131,
      "latest_phase": "post_distribution_watch",
      "latest_phase_name": "出货后观察",
      "base_len": 200,
      "base_start": "2025-08-18",
      "base_end": "2026-06-17",
      "avg_cost": 75.1984,
      "price_multiple": 1.0411,
      "base_cv": 0.1341,
      "base_range_pct": 85.9138,
      "target_245": 184.236,
      "target_260": 195.5157,
      "max_buy_price": 80.6387,
      "invalid_price_gte": 172.9562,
      "positive": [
        "long_base_stable",
        "price_near_base_cost",
        "close_above_ma20",
        "ma60_reclaim_ok",
        "not_single_day_chase",
        "upper_shadow_ok"
      ],
      "reasons": [
        "phase_risk:post_distribution_watch",
        "volume_ratio_below_entry_filter"
      ],
      "warnings": [],
      "amount_proxy_used": true
    },
    {
      "symbol": "SH688126",
      "name": "沪硅产业",
      "source": "sina.cn.kline_daily_fallback",
      "candidate_best_score": 131.27,
      "status": "risk_reject",
      "action": "avoid_chase",
      "score": 34.748,
      "latest_date": "2026-06-18",
      "latest_close": 32.2,
      "latest_volume_ratio": 0.9268,
      "daily_return_pct": -0.6173,
      "upper_shadow_pct": 2.795,
      "return_20_pct": 16.3295,
      "return_60_pct": 76.7289,
      "position_120": 0.8167,
      "latest_phase": "markup",
      "latest_phase_name": "拉升",
      "base_len": 200,
      "base_start": "2025-08-18",
      "base_end": "2026-06-17",
      "avg_cost": 22.3698,
      "price_multiple": 1.4394,
      "base_cv": 0.1477,
      "base_range_pct": 96.5683,
      "target_245": 54.806,
      "target_260": 58.1615,
      "max_buy_price": 27.9623,
      "invalid_price_gte": 51.4505,
      "positive": [
        "close_above_ma20",
        "ma60_reclaim_ok",
        "not_single_day_chase",
        "upper_shadow_ok",
        "phase_support:markup"
      ],
      "reasons": [
        "base_not_stable_enough",
        "price_not_in_pre_markup_cost_zone",
        "return_60_overextended",
        "volume_ratio_below_entry_filter"
      ],
      "warnings": [],
      "amount_proxy_used": true
    },
    {
      "symbol": "SZ301348",
      "name": "蓝箭电子",
      "source": "sina.cn.kline_daily_fallback",
      "candidate_best_score": 128.0179,
      "status": "risk_reject",
      "action": "avoid_chase",
      "score": 34.3379,
      "latest_date": "2026-06-18",
      "latest_close": 28.2,
      "latest_volume_ratio": 0.9315,
      "daily_return_pct": -3.2922,
      "upper_shadow_pct": 0.4255,
      "return_20_pct": -6.6534,
      "return_60_pct": 5.4994,
      "position_120": 0.4859,
      "latest_phase": "post_distribution_watch",
      "latest_phase_name": "出货后观察",
      "base_len": 120,
      "base_start": "2025-12-16",
      "base_end": "2026-06-17",
      "avg_cost": 26.2321,
      "price_multiple": 1.075,
      "base_cv": 0.1384,
      "base_range_pct": 86.4536,
      "target_245": 64.2686,
      "target_260": 68.2034,
      "max_buy_price": 29.046,
      "invalid_price_gte": 60.3338,
      "positive": [
        "long_base_stable",
        "price_near_base_cost",
        "close_above_ma20",
        "ma60_reclaim_ok",
        "not_single_day_chase",
        "upper_shadow_ok"
      ],
      "reasons": [
        "phase_risk:post_distribution_watch",
        "volume_ratio_below_entry_filter"
      ],
      "warnings": [],
      "amount_proxy_used": true
    }
  ]
}
```
