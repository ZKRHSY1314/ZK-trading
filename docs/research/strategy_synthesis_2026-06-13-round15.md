# 2026-06-13 Round 15: 外部框架 + Dataset1/2 融合笔记

## 边界

本文只用于研究、回测、沙盒、同花顺模拟盘训练和人工复核。当前仍保持：

- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`
- 不写生产 `configs/rules.yaml`
- 不连接券商、不保存凭证、不触碰真实资金账户

## 外部学习结论

1. VectorBT 的核心启发是批量实验：一次性比较多参数、多样本、多时期，避免只看单个成功样本。对应到本项目，就是继续扩大 `entry_delay_days`、`horizon_days`、`stop_loss_pct`、`take_profit_pct`、`confirmation_filter` 的 walk-forward 验证，而不是直接改生产权重。
   - Source: https://github.com/polakowo/vectorbt

2. QSTrader 的核心启发是调度/事件式回测：信号、组合、风控、执行、账户都要分层审计。对应到本项目，就是 Dataset2 只负责生成研究信号，PortfolioRisk 和执行模型负责阻断，Sim-Cockpit 只在全部模拟门通过后执行。
   - Source: https://github.com/mhallsmoore/qstrader

3. Backtrader 的 slippage 思路提醒我们：没有滑点、成交约束、涨跌停阻断的收益不可信。对应到本项目，V2.0 的一字板拒绝、成交额参与率、partial/rejected event 必须保留。
   - Source: https://www.backtrader.com/docu/slippage/slippage/

4. A 股涨跌停研究提醒我们，涨停附近可能存在价格吸引和次日兑现行为，不能把“接近涨停”简单视为买入信号。对应到本项目，涨停/放量强势只能进入候选和复核，必须再看可成交性、位置阶段、次日确认和风险门。
   - Source: https://voxchina.org/show-3-49.html

5. Wyckoff 的积累、试盘、主升、派发框架与用户的“三维通信/金螳螂/乐凯胶片”方法一致：重点不是单日强弱，而是主力在一年以上周期里的吸筹、试盘、突破、回踩确认和出货。
   - Sources: https://www.wyckoffanalytics.com/wyckoff-method/ and https://trendspider.com/learning-center/chart-patterns-wyckoff-accumulation/

## 本地数据学习结果

### 指数基准修复

- 已用 AkShare `stock_zh_index_daily` 补齐 `SH000300` 和 `SH000001`，各 500 根日线。
- 当前数据库：`daily_bar_cache` 里指数覆盖到 `2026-06-12`。
- 这修复了 phase confidence 鲁棒性里 `insufficient_benchmark_data` 的主要缺口。

### run_id 50: 本地研究循环

- Dataset2 replay 信号：60 条。
- 默认 signal backtest：60 笔闭合交易，胜率 63.33%，平均单笔收益 2.44%，等权累计收益 288.32%。
- 70/30 优化最佳收益候选：验证集 7 笔，胜率 71.43%，累计收益 26.23%。
- 结论：收益超过 20%，但验证交易数偏少，只能进入模拟复核，不足以放开生产规则。

### run_id 51: 深度参数网格

- 深度网格：504 组参数，360 次验证评估。
- 单纯收益最佳参数验证胜率 57.14%，未通过 58% 胜率线。
- 系统最终选择更稳的 Dataset1 对齐版本：
  - `entry_delay_days=1`
  - `horizon_days=3`
  - `stop_loss_pct=0.04`
  - `take_profit_pct=0.08`
  - `confirmation_filter=entry_close_above_signal`
- 该候选的 70/30 验证：5 笔，胜率 100%，累计收益 23.08%。
- walk-forward：4 折、28 笔，胜率 82.14%，累计收益 150.71%，最弱折胜率 60%，最弱折累计收益 12.44%。

### run_id 49 重算鲁棒性

补齐指数后，前一轮高/中置信 phase 组的市场分层已恢复：

- `SZ002115:markup`：累计收益 34.30%，胜率 83.33%；benchmark up 与 neutral 子组均为正。
- `SZ002081:markup`：累计收益 31.02%，胜率 62.50%；benchmark up/down/neutral 子组均为正。
- 仍有 `small_group_sample_count_for_robustness`，说明阶段样本还不够厚，不能据此放开真实交易。

## 融合后的策略框架

### 主线

当前最合理的框架不是“涨停就买”，而是：

1. 非交易时段用宽口径发现潜力股，优先看低位、首次放量、接近关键成本区、主力试盘痕迹。
2. Dataset2 负责把量价形态转成 `SIM_BUY_CANDIDATE` 或 `WAIT_CONFIRMATION`。
3. Dataset1 负责纪律过滤：不要买早、不要追高、不要越跌越补、强势时分批止盈、弱开要降级。
4. phase similarity 负责阶段解释：吸筹、试盘、主升、派发、派发后观察。
5. signal backtest 和 walk-forward 同时过线后，才允许进入模拟盘小额复核。
6. 模拟盘实操仍要求窗口验证、锚点识别、风险 gate、`SIMULATION_SCREEN_CLICK` 和 `simulation_allowed=true`。

### 仓位建议

模拟盘 20 万资金下，当前只建议：

- 第一笔试探：2%-4% 模拟资金。
- Dataset1 稳态确认 + 风控全通过：最多 6%-8%。
- 分布加仓：只在持仓回读、走势确认、无派发/失败拉升标签、市场环境不恶化时增加。
- 金螳螂这类已完成拉升出货样本：只作训练，不作短期新高追买模板。

### 当前可推进

- 继续让非交易循环积累样本，重点扩大 `entry_close_above_signal` 与 `dataset1_stabilized_reclaim` 的样本量。
- 将 `benchmark_history` 和市场分层结果展示到前端研究面板。
- 将 run 51 的稳态候选只接入 simulation planner 的 review note，不改变 `allowed`、数量、仓位和生产规则。

### 当前不能推进

- 不能把任何候选自动写入 `rules.yaml`。
- 不能因为 run 51 的验证收益超过 20% 就开实盘。
- 不能跳过同花顺模拟窗口验证和风险 gate。
- 不能把宽口径候选直接转成点击交易。

## 2026-06-13 Round 16: 稳态候选亏损归因

本轮新增 `signal_loss_attribution`，目标是回答一个更具体的问题：当前通过 walk-forward 的稳态候选，亏损到底集中在哪里。

### run_id 52 结果

- 稳态候选参数：
  - `entry_delay_days=1`
  - `horizon_days=3`
  - `stop_loss_pct=0.04`
  - `take_profit_pct=0.08`
  - `confirmation_filter=entry_close_above_signal`
- 闭合模拟交易：39 笔。
- 胜率：84.62%。
- 平均单笔收益：3.82%。
- 等权累计收益：317.04%。
- 亏损交易：6 笔。

### 亏损集中项

- `phase:distribution_or_failed_markup`：4 笔，胜率 0%，平均收益 -4.20%。
- `board:star`：7 笔，胜率 57.14%，平均收益 -0.04%，明显拖后腿。
- `reclaim:weak_positive_reclaim`：15 笔，胜率 66.67%，平均收益 1.72%，弱于整体。
- `tag:turning_point` / `LEGACY_VP_SINGLE_005`：6 笔，胜率 66.67%，平均收益 1.46%，存在弱确认亏损。

### 优势集中项

- `tag:limit_up`：5 笔，胜率 100%，平均收益 6.80%。
- `action:SIM_BUY_CANDIDATE` / `LEGACY_VP_SINGLE_001` / `big_yang`：9 笔，胜率 100%，平均收益 6.46%。
- `tag:bullish_attack`：8 笔，胜率 100%，平均收益 6.29%。
- `reclaim:strong_reclaim`：24 笔，胜率 95.83%，平均收益 5.13%。

### 新的监督建议

1. 科创板弱确认要收紧：科创板只在 `strong_reclaim` 或更高确认下进入模拟 dry-run。
2. `strong_reclaim` 只做信心加分和小额模拟复核前置条件，不直接变成交易触发器。
3. `WAIT_CONFIRMATION + turning_point` 需要 `entry_green_above_signal` 或 `strong_reclaim`，否则继续观察。

### 当前判断

这一轮让策略更清晰：收益不是来自随意放宽，而是来自“先发现机会，再用更强确认过滤弱跟随”。当前证据支持继续提高模拟复核优先级，但不支持写生产规则或放开真实账户权限。

## 2026-06-13 Round 17: 学习过滤器与外部框架再融合

### 浏览器学习参考

- VectorBT 文档强调高速批量参数实验和组合绩效分析；本项目采用“基础网格 + 少量学习过滤器复验”，避免把每个新想法都放进全量笛卡尔积导致运行过慢。参考：https://vectorbt.dev/
- scikit-learn `TimeSeriesSplit` 强调时间序列验证不能随机打乱；本项目继续坚持 70/30 时间切分和 walk-forward，避免未来数据泄漏。参考：https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- QSTrader 的启发是把信号、调度、组合、风控、执行分层；本项目继续让 Dataset2 只产出研究信号，风险门和 Sim-Cockpit 决定是否进入模拟复核。参考：https://github.com/mhallsmoore/qstrader

### 本轮代码推进

新增 `attribution_filter` 维度，但不进入实盘、不写 `rules.yaml`。基础网格仍保持 252 组，学习过滤器只对前排候选和经验对齐候选做二次复验，避免运行时间继续膨胀。

新增离线过滤器：

- `star_requires_strong_reclaim`：科创板候选必须强收复信号价后才进入模拟 dry-run 复核。
- `turning_point_requires_green_or_strong`：`WAIT_CONFIRMATION + turning_point` 必须次日红盘站回或强收复。
- `star_and_turning_point_quality_gate`：组合执行上述两个约束。
- `block_dataset1_distribution_risk`：带出货、滞涨、大阴、顶部风险等标签时，不转成新增买入优先级。

### run_id 54 结果

- 当前源码直跑完成，`live_trading_enabled=false`。
- 基础网格：252 组。
- 基础候选：126 组。
- 学习过滤器复验预算：12 个候选 × 4 个过滤器 = 48 组。
- 学习过滤器通过训练门槛后进入验证：36 组。
- 最优学习过滤候选：
  - `entry_delay_days=1`
  - `horizon_days=8`
  - `stop_loss_pct=0.04`
  - `take_profit_pct=0.12`
  - `confirmation_filter=dataset1_stabilized_reclaim`
  - `attribution_filter=star_and_turning_point_quality_gate`
  - 验证段 5 笔，胜率 60%，平均收益 4.82%，等权累计收益 24.82%。
- 但最终 `signal_optimization_gate=blocked`，原因是 `no_stable_candidate_meeting_validation_thresholds`。这表示收益超过 20% 还不够，必须继续满足 walk-forward 稳定性。

### 策略融合结论

当前最优方向不是“放松所有条件”，而是“宽入口发现机会，窄出口进入模拟复核”：

1. 非交易时段继续宽口径搜索涨停、放量、强势、低位和阶段相似候选。
2. Dataset2 负责把历史形态转成候选信号，不直接给交易权限。
3. Dataset1 负责纪律：不追已经出货的样本，不买弱确认，不把科创板高波动弱收复当成安全机会。
4. `strong_reclaim` 可以提高复核优先级，但不能直接触发买入。
5. 只有 70/30、walk-forward、风险 gate、模拟窗口识别全部通过后，才能进入小额模拟盘训练。

### 下一步

- 把 `attribution_filter` 的结果加入前端研究面板和模型候选 scorecard。
- 继续扩大样本，尤其补足 walk-forward 折数和每折交易数。
- 对 run 54 的学习过滤候选做后续交易日 replay，看它是否持续优于旧候选。
- 在模拟点击方面仍保持 dry-run 优先；没有新鲜 `action=buy`、`allowed=true`、窗口验证和风险 gate 全通过，不执行屏幕点击。

## 2026-06-13 Round 18: Scorecard 证据面板收口

本轮把 Round 17 的学习过滤器从“只在 run JSON 里出现”推进到候选模型 scorecard 和前端 V5.7 证据面板。

### 代码结果

- `offhour_model_candidate.v1` 的 `signal_optimization` 现在包含：
  - `signal_loss_attribution`
  - `learning_filter_candidates`
  - `optimization_budget.learning_filter_budget`
- `strategy_synthesis.active_simulation_hypothesis` 同步保留上述字段，方便前端和人工复核看到证据链。
- 前端 V5.7 面板新增：
  - `Learning Filters`：展示前排 attribution filter 候选及验证收益。
  - `Signal Loss Attribution`：展示亏损归因状态、交易数、亏损数和首条监督建议。

### run_id 55 验证

- `live_trading_enabled=false`。
- `learning_filter_budget.accepted_candidate_count=36`。
- 最新候选产物 hash：`24d0f173493f8e42e81ae01fe984c22706646a8a4d49f964aba68db4bd40debd`。
- `latest_model_candidate.artifact_detail.signal_optimization.learning_filter_candidates` 已能读取 5 条。
- `latest_model_candidate.artifact_detail.signal_optimization.signal_loss_attribution` 已能读取。
- 顶部学习过滤候选仍是：
  - `confirmation_filter=dataset1_stabilized_reclaim`
  - `attribution_filter=star_and_turning_point_quality_gate`
  - 验证段胜率 60%，平均收益 4.82%，等权累计收益 24.82%。
- 但 `signal_optimization_gate` 仍为 blocked，原因是 `no_stable_candidate_meeting_validation_thresholds`。结论不变：可以继续学习和模拟复核，但不能提升为自动交易权限。

### 验证命令

- `pytest -q`：103 passed。
- `npm run build`：通过。
- `vue-tsc --noEmit`：通过。
- `/health`：`live_trading_enabled=false`。
- Vite 代理可读到 run 55 和 5 条 learning filter 候选。

浏览器插件可以打开本地页面并识别 V5.7 区域，但在点击“刷新研究结果”时出现超时；因此本轮前端验收以 API 代理、类型检查和生产构建为主要证据。
