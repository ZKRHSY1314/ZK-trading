# 2026-06-13 Round 21: 浏览器学习 + Dataset1/2 策略合成

## 外部学习映射

本轮用浏览器核对了四类开源量化项目：

- QSTrader: 事件/调度式回测框架，启发是“同一套信号事件可以在历史回放和模拟运行之间复用”，但执行层仍必须独立受控。
- VectorBT: 批量参数实验和组合结果分析，启发是非交易时段继续做大规模参数网格、complete-window、walk-forward，而不是凭单次高收益改权重。
- Microsoft Qlib: AI-oriented quant research 平台，启发是把 AI 放在研究、解释、归因和候选模型层，而不是让模型直接改生产规则。
- vn.py: 国内事件驱动交易框架，启发是未来可以学习其行情事件、策略事件、风控事件分层，但本项目当前不接真实券商网关。

对应到 ZK-trading：V5.7 以后应继续强化“事件驱动研究循环 + 批量验证 + 审查队列 + 模拟盘训练闭环”，而不是跳到真实交易。

## Dataset1 学习结论

Dataset1 的交易宪法和案例库反复强调四件事：

- 买强不买弱，只做熟悉、趋势内、能解释主力阶段的股票。
- 禁止越跌越补，买早、买高、硬上板是主要亏损来源。
- 大涨后要轻仓或分批兑现，三维通信这类主升成功样本的核心不是追涨，而是识别主升后的执行纪律。
- 第一笔应小，第二笔要等启稳、均线支撑、强制分歧点或收盘前确认。

因此 Dataset1 更适合作为“交易纪律和阶段归因层”：它不直接产生买点，而是决定同一个 Dataset2 信号应该升权、观察、降级还是阻断。

## Dataset2 学习结论

Dataset2 当前有 225 条结构化规则：

- `SIM_BUY_CANDIDATE`: 63 条
- `WAIT_CONFIRMATION`: 59 条
- `REDUCE_OR_EXIT`: 64 条
- `HOLD_OR_TRAIL`: 19 条
- 其余为 `AVOID_OR_WAIT`、`RISK_ALERT`、`NO_TRADE`

Dataset2 的优势是覆盖量价、分时、筹码峰、盘口语言、K 线组合和集合竞价；弱点是大多数规则是“形态/解释标签”，不是带完整 entry/exit 的盈利标签。因此它应该继续做候选生成和风险解释，必须经过历史 replay、complete-window、walk-forward 和模拟成交样本再进入权重调整。

## 与原方案结合后的策略框架

当前最合理的是四轨并行：

1. 宽口径发现轨  
   用 Dataset2 的 `SIM_BUY_CANDIDATE` 和 `WAIT_CONFIRMATION` 扫潜力股，扩大观察池，尤其捕捉低位放量、试盘、强势回踩、near-reclaim。

2. 回踩确认轨  
   `near_reclaim_watch` 只观察，不 dry-run；只有重新站回信号价且没有弱开/弱收和硬风险标签，才变为 `reclaim_review`，进入小额 dry-run 证据。

3. 稳定确认轨  
   继续保留 run 57 的稳定候选：`entry_delay=1`、`horizon=3`、`stop_loss=6%`、`take_profit=18%`、`strong_reclaim + star_and_turning_point_quality_gate`。该轨用于降低买早和追高风险。

4. 仓位纪律轨  
   初始模拟复核仍应限制在 100 股或约 2% 模拟资金内。只有出现 fresh quote、组合风控通过、模拟窗口验证、干跑成功、成交/持仓回读成功、且后续走势确认主力拉升，才允许分布加仓。

## 本轮工程落地

本轮已把 `dataset2_reclaim_watchlist` 接入 Sim-Cockpit 干跑链：

- `reclaim_review` 会生成 `dataset2_reclaim_review` dry-run action。
- `near_reclaim_watch` 会被跳过，只记录 `not_reclaimed_for_dry_run`。
- dry-run 的 `risk_result` 明确 `simulation_allowed=false`、`all_gates_passed=false`，避免被误读为可点击交易许可。
- 外层审计仍保留 `simulation_only=true`、`live_trading_enabled=false`。

这一步的意义是：系统可以开始把高质量研究候选转成模拟盘训练证据，但仍不会自动触发真实点击。

## 2026-06-13 23:05 运行结果补充

- 非交易研究 run 59 已完成，50 条信号进入研究，`signal_optimization_status=passed_for_simulation_review`。
- run 59 的当前稳定候选：`entry_delay_days=1`、`horizon_days=8`、`stop_loss_pct=0.04`、`take_profit_pct=0.12`、`attribution_filter=star_and_turning_point_quality_gate`。
- run 59 walk-forward：33 笔、加权胜率 66.67%、加权平均收益 3.72%、等权累计收益 211.82%；最弱折胜率 50.00%、最弱折累计收益 7.90%。
- reclaim watch 当前仍为 `pending_future_data=17`、`blocked_failed_markup_risk=3`，没有 `near_reclaim_watch` 或 `reclaim_review` 活跃项；下一交易日 ready bar 或盘中事件更新后再分类。
- Dataset2 受控训练 run 118 已完成，但只是 `majority_label_classifier` 管道自检：120 条样本，验证准确率 13.89%，不具备预测模型价值，不得写模型 artifact。
- 结论：当前更可信的调控依据仍是 complete-window + walk-forward + reclaim 状态机 + 模拟盘回读样本，而不是 Dataset2 majority baseline。

## 2026-06-13 继续优化：稳定候选冠军选择

本轮发现一个重要问题：如果交易时段 planner 总是读取最新 offhour run，那么 run 59 这类“通过但弱于 run 57”的候选会覆盖更强证据。已修正为最近 12 个 run 内选择通过 gate 的冠军候选。

当前真实库选择结果：

- champion run: 57
- selected_from_candidate_count: 8
- champion_score: 511.021504
- 参数：`entry_delay_days=1`、`horizon_days=3`、`stop_loss_pct=0.06`、`take_profit_pct=0.18`、`attribution_filter=turning_point_requires_green_or_strong`
- 验证集：15 笔，胜率 73.33%，平均收益 8.17%，等权累计收益 199.53%
- walk-forward：33 笔，加权胜率 72.73%，等权累计收益 1156.83%

这一步提高的是“选择更可信策略证据”的能力，不扩大交易权限。planner 仍只把冠军候选写入 review-only 风险说明，不改变仓位、数量、风控 gate 或生产规则。

## 2026-06-13 训练基线升级：Dataset2 分组标签记忆

此前 Dataset2 受控训练 run 118 只是 `majority_label_classifier`，120 条样本验证准确率 13.89%，价值主要是管道自检。本轮升级为 `hierarchical_grouped_label_classifier`：

- 训练模式：`in_memory_grouped_label_baseline`
- 分组层级：`source+action+status+risk_level` -> `source+action+status` -> `source+action` -> `source` -> majority fallback
- 样本数：120
- train/validation: 84 / 36
- grouped validation accuracy: 61.11%
- majority validation accuracy: 13.89%
- lift vs majority: +47.22 percentage points
- correct validation count: 22 / 36
- model artifact written: false
- live trading enabled: false

解释：这不是可以交易的盈利模型，而是“策略/动作/状态标签记忆”终于超过了盲猜多数类。它能帮助后续把 Dataset2 规则族、Sim-Cockpit action/readback 和 offhour 回测证据合并，逐步形成更可靠的候选优先级。

下一步应把这个分组标签记忆扩展为“规则族表现记忆”：同一 `pattern_id/category/action_label/risk_level` 不只预测标签，还要统计模拟回测收益、阻断率、dry-run 成功率、成交回读质量，作为 candidate scoring 的附加证据。

## 下一步策略调控建议

- 周末/非交易时段：继续跑 offhour-research-loop，重点扩大 complete-window 样本和 walk-forward 分层。
- 交易时段：只对 `reclaim_review` 做 dry-run；`near_reclaim_watch` 等待盘中或日线重新站回信号价。
- 模拟盘：若 dry-run 坐标、窗口、风控全通过，可以用 100 股小额模拟单收集成交/未成交/撤单/阻断样本。
- 权重调整：只有当某个过滤器在 complete-window 和 walk-forward 中持续超过现有策略，且样本量足够，才进入 review-only 权重候选；不自动改 `rules.yaml`。

## 安全边界

- 不接真实券商。
- 不保存账号、密码、token、cookie 或 API key。
- 不把模拟盘逻辑切换到真实交易。
- 不绕过 PortfolioRisk、Sim-Cockpit window verification、`SIMULATION_SCREEN_CLICK` 或人工确认。
- 所有模型和策略输出只允许作为候选评分、解释、回测或模拟训练证据。
