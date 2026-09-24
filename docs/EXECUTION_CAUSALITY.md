# Backtest execution causality and the A/B harness

Status: `validated` in the cloud against synthetic bars. This does not qualify any historical execution. M4's frozen kernel (`backend/app/research/m4_*.py`) is untouched and remains the reference for a fully evidenced execution chain. This change corrects the production daily-bar engine's time-of-information errors so that it no longer contradicts that chain.

## What was wrong

`backend/app/backtest/engine.py` sized each next-open buy with `cash + positions_value(…, today)`, and `_positions_value` read **today's close**. Two further leaks sat in the same loop:

- Exits ran before entries. Stop-loss and take-profit fills were triggered by today's low and high, possibly at an intraday level, and their proceeds and freed slots funded the same open's buys.
- Each buy was sized from the cash left after the previous buy's daily-bar fill. That fill's capacity came from today's full-day amount.

`execution.py` then judged price bands from the day's high and low, and capacity from the day's amount, while filling at the open.

Measured with the synthetic fixture in `tests/test_backtest_causality.py`, running the pre-fix engine from commit `b0261f6` against the same bars, the entry's requested quantity at the check-day open was:

| Variant (only prices after the check-day open change) | Pre-fix engine | Fixed engine |
| --- | ---: | ---: |
| baseline | 14,800 | 14,800 |
| held stock's close only (10.4 → 12.9) | **15,900** | 14,800 |
| held stock crashes through its stop intraday | **14,400** | 14,800 |

## The contract: `backtest_execution.v2`

`backend/app/backtest/execution_contract.py` defines it. Every run records it in `metrics.execution_contract`, which is persisted with the run.

**Order intents are committed before the session opens.** They are built from:

- start-of-session cash;
- positions marked at their last *closed* bar, or at cost when there is no closed bar;
- the pre-open position count;
- the opening print, used as a market order's reference price;
- exit rules evaluated on closed bars.

Three rules follow from this:

- **Budget.** The entry budget is `min(cash_at_open − reserved, equity_at_open × cap)`. The quantity is the largest lot whose notional plus commission fits the budget. The budget and fee are reserved, so later entries in the session can never overdraw.
- **No same-session reuse.** Proceeds from this session's sales, and slots freed by this session's exits, are not reused until the next session. This is conservative: A-shares allow same-day reuse of sale proceeds, and that is not modelled.
- **Exits.** An MA break or the holding-day limit becomes one market-at-open sell. Otherwise the position carries a resting stop and, once per position, a resting take-profit, with triggers fixed from cost before the open.

`run(..., include_intents=True)` returns every intent with a SHA-256 fingerprint. The required metamorphic test is there:

- **Setup.** Hold every pre-open input fixed. Change only the close, high, low, amount or volume of the entry, the held stock or the index. This covers six variants, under both fill policies.
- **Required result.** No intent fingerprint, budget or quantity for that session may change.

**Fill adjudication happens afterwards, under a named policy.**

| | `daily_bar_retrospective` (default, the historical assumptions) | `pre_open_causal` |
| --- | --- | --- |
| Market-at-open price band | session high/low (`one_word_limit_*`) | opening print only (`open_at_limit_*`) |
| Market-at-open capacity | session amount (or volume × typical price proxy) | **prior** session amount; refused as `capacity_unproven` if there is none |
| Resting stop/take-profit | session high/low touch; stop precedes take-profit; intraday path unknown | same (inherently retrospective, labelled) |
| Market-at-open fill invariant to later session prices | no | yes |

The default remains retrospective so that existing callers and tests keep their fill semantics. Their intents are now causal either way. The contract always carries `qualified_historical_execution: false` and describes each unqualified assumption:

- fees are configured rates;
- capacity is a participation assumption;
- price limits use the inferred-board signal threshold, and ST status is not detected;
- the fundamentals point-in-time flag is recorded.

### Behaviour changes callers may see

- Buys are smaller when holdings rose on the session, and are not funded by same-session sale proceeds.
- An MA break or holding limit now exits at the open. Before, a same-day stop touch could pre-empt it at the stop price, which is usually a worse price and was decided with future information.
- A take-profit and an MA break on the same day now resolve to the MA-break exit at the open.
- The one defective path is gone: a buy whose cost exceeded the cash is no longer left in the trade list as a phantom fill.
- The trade rows gain `intent_id`, `order_type`, `price_band_basis` and `capacity_basis`. These are in-memory only; the persisted columns are unchanged.

## Deterministic A/B harness

`backend/app/backtest/ab_harness.py` runs two rule configurations from a predeclared manifest (`backtest_ab_manifest.v1`). A manifest must declare all of the following:

- a fixed, non-empty universe and window;
- capital;
- `fill_policy: pre_open_causal`, with projected fundamentals explicitly off;
- costs that must equal the costs actually in effect;
- exactly arms A and B;
- the primary metric;
- both controls;
- an evidence class, `engineering_synthetic` or `development_diagnostic`.

It may optionally pin `expected_input_sha256`.

A run works like this:

1. It fingerprints every row the engine can read: the universe, benchmark and regime-index bars up to the end date, plus fundamentals.
2. It runs A, then B, then A again, with persistence off.
3. It checks the controls. The A/A rerun must be byte-identical, and the input fingerprint must be unchanged. A failed control makes the report `invalid`.

The report always has `qualified_for_strategy_claim: false` and lists the reasons. A primary-metric difference is `None`, with a reason, whenever either arm has no value; a missing return is never treated as zero.

To run it locally against a **copy** of a database (the source is copied through SQLite's backup API from a read-only connection, then discarded):

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_backtest_ab.py --manifest experiment.json --database trading_local.sqlite3 --label my_experiment
```

The cloud has proved engineering behaviour only: determinism, the controls, the refusals and no persistence. That was on synthetic bars. It has proved nothing about profitable strategy performance or qualified historical trading.

## Not changed, and open

- The frozen M4 modules and their byte pins are untouched. No adapter from production intents to the M4 kernel was built. That would need real, time-stamped tradability, fee and capacity evidence, which is absent.
- `app/ai/review_worker.py` still compares configurations with the engine's default policy, over all cached symbols (`symbols=[]`). It also reads a missing `total_return` as 0 in its `out_of_sample_not_worse` check. It should move onto the harness; that is recorded as follow-up work.
- `allow_projected_fundamentals=True` remains an explicit, labelled approximation. The harness refuses it.
