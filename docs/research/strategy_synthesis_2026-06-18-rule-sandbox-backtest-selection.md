# 2026-06-18 规则沙盒与 A 股历史回测：规则筛选、买入明细与代码整理

## 运行边界

本轮按用户要求选择合适规则进入沙盒，并使用本地 A 股历史数据做回测复核。全程只做 review-only / simulation-only：

- `/health.status=ok`
- `/health.environment=local`
- `/health.live_trading_enabled=false`
- 不连接券商。
- 不保存凭证。
- 不提交真实委托。
- 不修改 `rules.yaml`。
- 不写入生产模型。

执行命令：

```powershell
$env:PYTHONUTF8='1'
$env:OFFHOUR_RESEARCH_DEEP_BACKTEST='1'
backend\.venv\Scripts\python.exe backend\scripts\automation_loop.py --mode offhour-research-loop --api-base http://127.0.0.1:8000 --limit 20 --max-cycles 1 --continue-on-error
```

整理脚本：

```powershell
$env:PYTHONUTF8='1'
backend\.venv\Scripts\python.exe backend\scripts\summarize_rule_sandbox_backtest.py --format markdown
```

## 本轮结果总览

最新 off-hour run：

- `offhour_research_runs.id=86`
- `status=completed`
- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`
- `next_action=Recent Dataset2 signals are waiting for the next ready bar; rerun after the next trading session to classify near-reclaim, reclaim-review, or failed-markup risk.`

Dataset2 replay：

- `signal_count=20`
- `recent_signal_count=120`
- `expanded_signal_count=600`
- 样本股票：`SH600110`、`SH600500`、`SH603186`、`SH603330`、`SH603618`、`SH688010`、`SH688108`、`SH688507`、`SZ002254`、`SZ002806`、`SZ002971`
- 动作分布：`SIM_BUY_CANDIDATE=3`、`WAIT_CONFIRMATION=17`

沙盒结果：

- `evaluated_count=20`
- `pending_count=0`
- `strong_follow_through=8`
- `mild_follow_through=5`
- `flat_or_noise=3`
- `failed_signal=4`

Dataset2 signal backtest：

- `trade_count=20`
- `win_rate=0.45`
- `average_return_pct=0.609497`
- `profit_loss_ratio=1.588387`
- `equal_weight_cumulative_return_pct=9.724277`

生产规则历史回测：

- `status=completed`
- `trade_count=0`
- `rejected_by_risk_count=1468`
- `benchmark_return=0.03713`
- `excess_return=-0.03713`

解释：Dataset2 信号层能产生买入样本和收益，但当前生产 `RuleEngine` 仍由旧规则驱动，所有候选都被挡在强候选之外。因此本轮不能把规则直接写入生产，只能进入沙盒候选和模拟复核队列。

## 决定加入的规则

这里的“加入”只指加入沙盒候选 / 模拟复核规则，不是加入生产 `rules.yaml`。

### 1. `LEGACY_VP_SINGLE_005` 放量小阴小阳线

结论：加入沙盒候选，作为 `WAIT_CONFIRMATION` / 站回确认类规则。

证据：

- 沙盒样本数：9
- 沙盒胜率：0.777778
- 沙盒平均收盘收益：0.374769%
- signal backtest 交易数：9
- signal backtest 胜率：0.555556
- signal backtest 平均收益：0.518174%

限制：

- 不能直接买入。
- 必须叠加 `entry_close_above_signal` 或 `entry_green_above_signal`。
- 出现 `top_risk`、`volume_up_price_stall`、`distribution_or_stall_risk` 时只做观察或过滤。

### 2. `LEGACY_VP_SINGLE_006` 缩量小阴小阳线

结论：加入沙盒候选，作为低波动整理 / 站回确认类规则。

证据：

- 沙盒样本数：8
- 沙盒胜率：0.625
- 沙盒平均收盘收益：2.360363%
- signal backtest 交易数：8
- signal backtest 胜率：0.5
- signal backtest 平均收益：2.622849%

限制：

- 仍属于 `WAIT_CONFIRMATION`，不是买入许可。
- 需要等待下一根 K 线站回信号收盘价。
- 若进入高波动板块或高位风险，只能保留为观察。

### 3. `entry_close_above_signal` 确认过滤

结论：加入稳定参数候选的沙盒复核队列。

推荐参数：

```json
{
  "confirmation_filter": "entry_close_above_signal",
  "entry_delay_days": 1,
  "horizon_days": 8,
  "stop_loss_pct": 0.06,
  "take_profit_pct": 0.12,
  "buy_position_ratio": 0.08,
  "wait_position_ratio": 0.06
}
```

扩展历史 / walk-forward 证据：

- expanded signal count：488
- walk-forward fold count：4
- trade count：172
- weighted win rate：0.767442
- weighted average return：6.926177%
- min fold trade count：25
- min fold win rate：0.72
- gate status：`passed_for_simulation_review`

限制：

- 只通过“simulation review”，还不能写生产规则。
- 需要继续做监督 dry-run/readback，尤其验证真实成交与滑点。

### 4. `entry_green_above_signal` 经验对齐过滤

结论：加入保守沙盒对照组。

推荐参数：

```json
{
  "confirmation_filter": "entry_green_above_signal",
  "entry_delay_days": 2,
  "horizon_days": 3,
  "stop_loss_pct": 0.04,
  "take_profit_pct": 0.12,
  "buy_position_ratio": 0.08,
  "wait_position_ratio": 0.06
}
```

验证集证据：

- validation trade count：8
- validation win rate：1.0
- validation average return：14.545455%
- validation equal weight cumulative return：195.016576%

解释：它更符合 Dataset1 的“不买早、等启稳”纪律，但样本数少于 `entry_close_above_signal`，所以应作为保守对照组，而不是主规则。

## 暂不加入的规则

### `LEGACY_VP_SINGLE_001` 放量大阳线

结论：不加入直接买入规则，只保留为形态解释或观察标签。

原因：

- 沙盒样本数只有 2。
- 沙盒平均收盘收益为 -14.464862%。
- signal backtest 胜率为 0。
- signal backtest 平均收益为 -2.846264%。

质疑点：放量大阳经常带 `top_risk`，如果没有低位和站回确认，容易变成追高。

### `LEGACY_VP_UP_004` 放量大涨

结论：不加入。

原因：

- 样本数只有 1。
- 沙盒胜率 0。
- 沙盒平均收盘收益 -12.177986%。
- signal backtest 平均收益 -7.763896%。

质疑点：这个规则太像“已经涨完后再追”，必须先通过高位过滤、分发风险过滤、成交可得性过滤。

## 沙盒买入明细

这些是 Dataset2 signal backtest 的模拟买入，不是真实买入。

| 股票 | 规则 | 信号日 | 买入日 | 数量 | 退出日 | 退出原因 | 收益% |
|---|---|---:|---:|---:|---:|---|---:|
| SH688108 | LEGACY_VP_SINGLE_001 | 2025-10-23 | 2025-10-24 | 500 | 2025-10-28 | signal_stop_loss | -5.162451 |
| SH600500 | LEGACY_VP_SINGLE_005 | 2025-10-24 | 2025-10-27 | 2800 | 2025-11-03 | horizon_exit | 1.687929 |
| SH688010 | LEGACY_VP_SINGLE_005 | 2025-10-24 | 2025-10-27 | 400 | 2025-10-30 | signal_stop_loss | -5.182313 |
| SH688507 | LEGACY_VP_SINGLE_001 | 2025-10-24 | 2025-10-27 | 100 | 2025-11-03 | horizon_exit | -0.530077 |
| SH688507 | LEGACY_VP_SINGLE_005 | 2025-10-27 | 2025-10-28 | 100 | 2025-10-30 | signal_stop_loss | -5.786996 |
| SH600110 | LEGACY_VP_SINGLE_005 | 2025-10-28 | 2025-10-29 | 1800 | 2025-10-31 | signal_take_profit | 7.805489 |
| SH603186 | LEGACY_VP_UP_004 | 2025-10-28 | 2025-10-29 | 200 | 2025-10-30 | signal_stop_loss | -7.763896 |
| SZ002254 | LEGACY_VP_SINGLE_006 | 2025-10-28 | 2025-10-29 | 1100 | 2025-11-05 | horizon_exit | -0.538754 |
| SH603330 | LEGACY_VP_SINGLE_005 | 2025-10-29 | 2025-10-30 | 1400 | 2025-11-06 | horizon_exit | 2.453199 |
| SH688108 | LEGACY_VP_SINGLE_005 | 2025-10-29 | 2025-10-30 | 500 | 2025-11-06 | horizon_exit | -0.880010 |
| SZ002806 | LEGACY_VP_SINGLE_005 | 2025-10-29 | 2025-10-30 | 800 | 2025-11-03 | signal_stop_loss | -5.183535 |
| SZ002806 | LEGACY_VP_SINGLE_006 | 2025-10-30 | 2025-10-31 | 800 | 2025-11-07 | horizon_exit | -1.782787 |
| SZ002971 | LEGACY_VP_SINGLE_006 | 2025-10-30 | 2025-10-31 | 300 | 2025-11-04 | signal_take_profit | 7.794528 |
| SH600500 | LEGACY_VP_SINGLE_005 | 2025-10-31 | 2025-11-03 | 2800 | 2025-11-10 | horizon_exit | 5.005493 |
| SZ002971 | LEGACY_VP_SINGLE_006 | 2025-10-31 | 2025-11-03 | 300 | 2025-11-04 | signal_take_profit | 7.794417 |
| SH600500 | LEGACY_VP_SINGLE_005 | 2025-11-03 | 2025-11-04 | 2800 | 2025-11-11 | horizon_exit | 4.744307 |
| SH603186 | LEGACY_VP_SINGLE_006 | 2025-11-03 | 2025-11-04 | 200 | 2025-11-05 | signal_stop_loss | -6.972742 |
| SH603618 | LEGACY_VP_SINGLE_006 | 2025-11-03 | 2025-11-04 | 1400 | 2025-11-10 | signal_take_profit | 7.800708 |
| SH688010 | LEGACY_VP_SINGLE_006 | 2025-11-03 | 2025-11-04 | 400 | 2025-11-11 | horizon_exit | -0.905229 |
| SZ002971 | LEGACY_VP_SINGLE_006 | 2025-11-03 | 2025-11-04 | 300 | 2025-11-05 | signal_take_profit | 7.792651 |

## 代码整理

### 1. 沙盒与回测主流程

入口：

- `backend/app/research/offhour.py`
- 类：`OffhourResearchLoopService`
- 方法：`run(...)`

流程：

```text
health_guard
-> Dataset2StrategyAdapter.load()
-> _run_potential_search()
-> _select_symbols()
-> _coverage()
-> _strategy_replay()
-> _backtest()
-> _signal_backtest()
-> _signal_parameter_grid()
-> _reclaim_watchlist()
-> _reclaim_transition_study()
-> _sandbox()
-> _write_model_candidate()
```

用途：

- `_strategy_replay()`：把 Dataset2 规则映射到本地 `daily_bar_cache` 的历史 K 线。
- `_sandbox()`：对 replay 信号做未来 5 日收益分类。
- `_signal_backtest()`：模拟延迟买入、止盈、止损和持有期退出。
- `_signal_parameter_grid()`：筛选更稳的确认过滤器、延迟天数、止损止盈组合。
- `_write_model_candidate()`：只写 candidate-only artifact，不自动加载生产。

### 2. 沙盒如何判断信号

位置：

- `backend/app/research/offhour.py`
- 方法：`_sandbox(signals, horizon_days)`

逻辑摘要：

```python
rows = daily_bar_cache[symbol, trade_date > signal_date][:horizon_days]
entry = signal["close"]
max_return = (max(future_close) - entry) / entry * 100
min_return = (min(future_close) - entry) / entry * 100
close_return = (last_future_close - entry) / entry * 100

if max_return >= 3:
    outcome_label = "strong_follow_through"
elif max_return >= 1:
    outcome_label = "mild_follow_through"
elif close_return <= -3 or min_return <= -4:
    outcome_label = "failed_signal"
else:
    outcome_label = "flat_or_noise"
```

### 3. 历史回测如何买入

位置：

- `backend/app/backtest/engine.py`
- 类：`BacktestEngine`
- 方法：`run(...)`

当前生产回测逻辑：

```text
for each date:
  first sell existing positions using stop_loss / take_profit / max_holding_days
  then evaluate each symbol with RuleEngine.evaluate(snapshot)
  only CandidateTier.strong enters candidates
  candidates sorted by score
  buy up to max_positions
```

买入约束：

- 单票仓位上限：`per_symbol_cap`
- 弱势市场减半：`regime == "weak"`
- 最小交易单位：`settings.min_order_lot`
- 涨停一字板拒单：`one_word_limit_up`
- 跌停一字板拒卖：`one_word_limit_down`
- 流动性参与率限制：`backtest_max_participation_rate`
- 佣金、印花税、滑点都进入成交模型。

本轮生产回测 0 成交，是因为 `RuleEngine` 只认强候选，而当前生产 `rules.yaml` 的硬约束过严，不代表 Dataset2 signal backtest 没有效果。

### 4. 规则筛选摘要脚本

新增脚本：

- `backend/scripts/summarize_rule_sandbox_backtest.py`

用途：

- 读取最新 `offhour_research_runs`。
- 汇总 sandbox 规则表现。
- 汇总 Dataset2 signal backtest 买入明细。
- 对规则输出 `include_sandbox_candidate` / `watch_only` / `needs_more_samples` / `exclude_direct_buy_or_context_only`。

规则筛选阈值：

```python
MIN_TRADE_COUNT = 5
MIN_SANDBOX_WIN_RATE = 0.6
MIN_SIGNAL_AVG_RETURN_PCT = 0.0
```

筛选逻辑：

```python
if trade_count < MIN_TRADE_COUNT:
    action = "needs_more_samples"
elif sandbox_win_rate >= MIN_SANDBOX_WIN_RATE and signal_avg_return > MIN_SIGNAL_AVG_RETURN_PCT:
    action = "include_sandbox_candidate"
elif signal_avg_return <= 0 or sandbox_avg_close <= 0:
    action = "exclude_direct_buy_or_context_only"
else:
    action = "watch_only"
```

## 最终判断

本轮可加入沙盒/模拟复核的规则：

1. `LEGACY_VP_SINGLE_005`：放量小阴小阳线，作为站回确认候选。
2. `LEGACY_VP_SINGLE_006`：缩量小阴小阳线，作为低波动整理后确认候选。
3. `entry_close_above_signal + entry_delay_days=1 + horizon_days=8 + stop_loss=6% + take_profit=12%`：作为当前主沙盒参数候选。
4. `entry_green_above_signal + entry_delay_days=2 + horizon_days=3 + stop_loss=4% + take_profit=12%`：作为 Dataset1 纪律对齐的保守对照组。

本轮不应加入生产或直接买入的规则：

1. `LEGACY_VP_SINGLE_001`：放量大阳线，样本少且收益为负，容易追高。
2. `LEGACY_VP_UP_004`：放量大涨，当前样本失败，先排除。
3. 任何带 `top_risk`、`volume_up_price_stall`、`distribution_or_stall_risk` 的信号，不能直接转为买入。

下一步：

1. 等下一个交易日后重跑，解决“最近 Dataset2 signals 等待下一根 ready bar”的问题。
2. 把 `LEGACY_VP_SINGLE_005/006` 与 `entry_close_above_signal` 组合继续进监督 dry-run/readback。
3. 对 `LEGACY_VP_SINGLE_001/UP_004` 只做低位过滤和分发风险过滤实验，不允许直接买。
4. 若要真正写入 `rules.yaml`，必须先有监督 dry-run/readback、样本外、walk-forward 和人工确认。
