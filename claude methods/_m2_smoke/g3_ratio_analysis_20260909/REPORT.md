# G-3 ratio analysis — retained vendor closes versus the retained reference

> **Exploratory measurement only.** Exploratory measurement. No acceptance threshold is defined, no corporate action is inferred, no basis label or eligibility changes, U-6 and P1 stay open, and source capability remains FAIL.
> Offline: the vendor closes were **decoded** from retained bodies with the
> pinned routine; **the adapter was not replayed**. No network, SQLite,
> capture, service, production write, staging, commit or push.

* **Ratio direction:** ratio = vendor_close / reference_close (the live Sina close divided by the cached reference close)
* **Difference:** difference = vendor_close - reference_close
* **Normalization:** none - no rebasing, scaling, unit conversion or re-rounding of stored values; run-grouping rounds to 6 decimal places only to group exact repeats, which is not a tolerance
* Selected revision: `claude methods/_m2_smoke/revision_20260908T082833Z_r2abc_v2`

## Coverage, duplicates and validity

| symbol | class | vendor rows | reference rows | reference span | compared dates | ref dates missing from vendor | vendor dates in span missing from ref | duplicate dates | invalid closes |
|---|---|---|---|---|---|---|---|---|---|
| `sh600011` | stock | 5935 | 538 | 2024-06-21..2026-09-04 | 538 | 0 | 0 | vendor 0 / ref 0 | vendor 0 / ref 0 |
| `sh000300` | benchmark | 5987 | 538 | 2024-06-19..2026-09-02 | 538 | 0 | 0 | vendor 0 / ref 0 | vendor 0 / ref 0 |
| `bj920000` | stock | 1393 | 501 | 2024-08-13..2026-09-04 | 501 | 0 | 0 | vendor 0 / ref 0 | vendor 2 / ref 0 |

## `sh600011` (stock)

Reference basis stored: qfq. Sources: akshare.stock_zh_a_daily, akshare.stock_zh_a_hist, tonghuasun.local.quotes.candle. Distinct fetch times: 4.

Ratio over 538 compared dates: min 1, median 1.056140723, max 1.106097561; 241 distinct rounded values in 468 piecewise-constant runs.

Difference over the same dates: min +0.0000, median +0.4300, max +0.8700; 31 distinct rounded values in 233 runs.

| segment (source / updated_at) | rows | span | compared | ratio min..max | distinct ratios | distinct differences |
|---|---|---|---|---|---|---|
| `akshare.stock_zh_a_hist` / `2026-07-15T14:16:19` | 37 | 2024-06-21..2024-08-12 | 37 | 1.080722892..1.106097561 | 35 | 2 |
| `akshare.stock_zh_a_daily` / `2026-09-03T17:21:19` | 470 | 2024-08-13..2026-07-23 | 470 | 1..1.096153846 | 206 | 30 |
| `akshare.stock_zh_a_daily` / `2026-09-04T15:09:56` | 1 | 2026-07-24..2026-07-24 | 1 | 1..1 | 1 | 1 |
| `tonghuasun.local.quotes.candle` / `2026-09-04T18:06:09` | 30 | 2026-07-27..2026-09-04 | 30 | 1..1 | 1 | 1 |

Source / fetch-time boundary dates: `2024-08-13`, `2026-07-24`, `2026-07-27`.

## `sh000300` (benchmark)

Reference basis stored: none. Sources: akshare.stock_zh_index_daily. Distinct fetch times: 4.

Ratio over 538 compared dates: min 1, median 1, max 1; 1 distinct rounded values in 1 piecewise-constant runs.

Difference over the same dates: min +0.0000, median +0.0000, max +0.0000; 1 distinct rounded values in 1 runs.

| segment (source / updated_at) | rows | span | compared | ratio min..max | distinct ratios | distinct differences |
|---|---|---|---|---|---|---|
| `akshare.stock_zh_index_daily` / `2026-07-12T10:38:21` | 2 | 2024-06-19..2024-06-20 | 2 | 1..1 | 1 | 1 |
| `akshare.stock_zh_index_daily` / `2026-07-15T15:18:22` | 1 | 2024-06-21..2024-06-21 | 1 | 1..1 | 1 | 1 |
| `akshare.stock_zh_index_daily` / `2026-07-15T19:38:23` | 475 | 2024-06-24..2026-06-09 | 475 | 1..1 | 1 | 1 |
| `akshare.stock_zh_index_daily` / `2026-09-03T11:41:45` | 60 | 2026-06-10..2026-09-02 | 60 | 1..1 | 1 | 1 |

Difference runs, in full:

* `+0.0000` over 2024-06-19 .. 2026-09-02 (538 sessions)

Source / fetch-time boundary dates: `2024-06-21`, `2024-06-24`, `2026-06-10`.

## `bj920000` (stock)

Reference basis stored: qfq. Sources: akshare.stock_zh_a_daily, tonghuasun.local.quotes.candle. Distinct fetch times: 3.

Ratio over 501 compared dates: min 1, median 1.006833713, max 1.049913941; 383 distinct rounded values in 422 piecewise-constant runs.

Difference over the same dates: min +0.0000, median +0.1500, max +0.2900; 5 distinct rounded values in 5 runs.

| segment (source / updated_at) | rows | span | compared | ratio min..max | distinct ratios | distinct differences |
|---|---|---|---|---|---|---|
| `tonghuasun.local.quotes.candle` / `2026-09-03T19:39:41` | 470 | 2024-08-13..2026-07-23 | 470 | 1..1.049913941 | 383 | 5 |
| `akshare.stock_zh_a_daily` / `2026-09-04T15:02:08` | 1 | 2026-07-24..2026-07-24 | 1 | 1..1 | 1 | 1 |
| `tonghuasun.local.quotes.candle` / `2026-09-04T18:06:31` | 30 | 2026-07-27..2026-09-04 | 30 | 1..1 | 1 | 1 |

Difference runs, in full:

* `+0.2900` over 2024-08-13 .. 2024-09-27 (32 sessions)
* `+0.2300` over 2024-09-30 .. 2025-05-14 (147 sessions)
* `+0.1500` over 2025-05-15 .. 2025-09-17 (89 sessions)
* `+0.0800` over 2025-09-18 .. 2026-05-22 (159 sessions)
* `+0.0000` over 2026-05-25 .. 2026-09-04 (74 sessions)

Source / fetch-time boundary dates: `2026-07-24`, `2026-07-27`.

Non-positive closes: vendor ['2019-05-23', '2019-07-12']; reference none. 0 of the vendor ones fall inside the reference span and are therefore excluded from the comparison; the rest lie outside it.

## Documented 470-row segments

```json
{
  "expected": "each stock carries one 470-row segment sharing source AND updated_at over 2024-08-13..2026-07-23; SH600011's same-source span is 471 rows because 2026-07-24 has a different updated_at",
  "sh600011_470_row_segments": [
    {
      "rows": 470,
      "first_date": "2024-08-13",
      "last_date": "2026-07-23",
      "key": {
        "source": "akshare.stock_zh_a_daily",
        "updated_at": "2026-09-03T17:21:19"
      }
    }
  ],
  "bj920000_470_row_segments": [
    {
      "rows": 470,
      "first_date": "2024-08-13",
      "last_date": "2026-07-23",
      "key": {
        "source": "tonghuasun.local.quotes.candle",
        "updated_at": "2026-09-03T19:39:41"
      }
    }
  ],
  "sh600011_471_row_source_only_spans": [
    {
      "rows": 471,
      "first_date": "2024-08-13",
      "last_date": "2026-07-24"
    }
  ],
  "verified": true
}
```

## What this does and does not establish

It establishes the measured coverage, validity and the ratio and difference series over every available common date, per source-and-fetch-time segment. It **does not** interpret any change as a corporate action, define any tolerance or acceptance threshold, assign or alter a basis label, alter any eligibility result, close U-6 or P1, or change the capability verdict, which remains **FAIL**.
