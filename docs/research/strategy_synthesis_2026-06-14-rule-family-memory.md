# 2026-06-14 策略学习记录：规则族表现记忆与深度研究合成

## 本轮目标

本轮继续把外部量化框架思路、Dataset1 交易经验、Dataset2 结构化规则和现有 offhour/sim-cockpit 证据合并。重点不是扩大交易权限，而是提高判断质量：让系统知道哪些规则族在历史 replay 中更有表现，哪些只应观察，哪些必须等待回踩确认和模拟盘回读。

当前边界保持不变：

- `live_trading_enabled=false`
- `review_only=true`
- `simulation_only=true`
- 不写生产模型 artifact
- 不自动修改 `rules.yaml`
- 不触碰真实账户、券商登录、资金账号、银证转账或真实委托

## 浏览器调研吸收

本轮通过浏览器核对了四类开源量化项目：

- QSTrader: 事件驱动回测。对本项目的启发是把信号、风险、成交、持仓、回读拆成事件流，同一套事件可以在历史 replay、模拟盘 dry-run、未来实盘人工确认中复用。
- vectorbt: 批量参数实验。对本项目的启发是周末和非交易时段应继续做参数网格、complete-window、walk-forward 和稳定候选筛选，而不是凭单次收益改权重。
- Microsoft Qlib: AI 投研工作流。对本项目的启发是 AI 应先做解释、归因、候选模型和审查建议，不能直接改生产规则或绕过风控。
- vn.py/VeighNa: 国内量化工程分层。对本项目的启发是行情、策略、风控、执行、回读、训练样本必须分层，尤其要避免把同花顺模拟盘执行能力误当成策略能力。

可借鉴但暂不整包引入。当前项目已经有本地事件、回测、审计、Dataset2 和 Sim-Cockpit 结构，最合适的路线是吸收框架思想而不是替换系统。

参考：

- https://github.com/quantstart/qstrader
- https://github.com/polakowo/vectorbt
- https://github.com/microsoft/qlib
- https://github.com/vnpy/vnpy

## Dataset1 学习合成

Dataset1 的价值主要是交易纪律和主力阶段归因，不适合作为单独买点模型。它反复强调：

- 只做熟悉、趋势内、能解释主力阶段的股票。
- 买强不买弱，但大涨后必须轻仓。
- 禁止越跌越补，补仓必须等强制分歧点、均线支撑或重新启稳。
- 第一笔要小，第二笔必须等待确认，最好接近收盘或确认支撑后再做。
- 三维通信这类成功样本的核心不是追涨，而是识别主升阶段后执行分批止盈纪律。
- 乐凯胶片等失败教训提醒：执行计划比临时情绪判断更重要。

因此 Dataset1 应作为风控和动作解释层：

- 对 Dataset2 的 `SIM_BUY_CANDIDATE` 做升权、观察、降权或阻断。
- 对 `WAIT_CONFIRMATION` 判断是否满足回踩确认。
- 对大涨后、买早、买高、越跌越补等情境输出硬风险标签。
- 对卖出侧维持分批止盈、破位止损、10 点前逢高处理等纪律。

## Dataset2 学习合成

Dataset2 目前更像规则知识库和弱标签库，而不是直接可交易模型。质量报告已经指出：它缺少真实 signal_date、stock_code、entry/exit 和 forward return，因此不能把 `SIM_BUY_CANDIDATE` 直接当买入许可。

本轮新增的规则族表现记忆开始补这个缺口：系统不再只记住一个 pattern 的文字标签，而是把同一个 `pattern_id/category/action_label/risk_level` 在 staging、offhour 回测和模拟盘执行中的表现放到一起看。

当前真实库状态：

- Dataset2 training status: `ready`
- 样本候选数：160
- 训练允许：true
- 受控训练 event_id：122
- 训练模式：`in_memory_grouped_label_baseline`
- train/validation: 112 / 48
- grouped validation accuracy: 70.83%
- majority validation accuracy: 22.92%
- lift vs majority: +47.92 percentage points
- model artifact written: false
- live trading enabled: false

这个结果的意义是：系统已经能从“多数类猜测”升级到“按 source/action/status/risk 分组记忆”。但它仍不是收益模型，只能作为候选优先级和审查证据。

## 规则族表现记忆

新增 `dataset2_rule_family_performance_memory.v1` 后，当前聚合结果：

- staging group count: 148
- backtest group count: 4
- backtest trade count: 446
- positive backtest group count: 4
- execution group count: 3

当前表现较好的规则族：

1. `LEGACY_VP_SINGLE_001 / 放量大阳线 / SIM_BUY_CANDIDATE / medium`
   - trade_count: 37
   - win_rate: 64.86%
   - average_return_pct: 3.80%
   - total_return_pct: 140.65%
   - worst_return_pct: -5.17%
   - 判断：适合作为强势候选发现器，但必须过滤高位追涨和大涨后重仓。

2. `LEGACY_VP_SINGLE_006 / 缩量小阴小阳线 / WAIT_CONFIRMATION / low_to_medium`
   - trade_count: 350
   - win_rate: 69.43%
   - average_return_pct: 3.03%
   - total_return_pct: 1059.60%
   - worst_return_pct: -5.21%
   - 判断：更像回踩确认和主力吸筹后的延续观察器。样本多、稳定性较好，但不能直接买，必须等待重新站回信号价或均线支撑。

3. `LEGACY_VP_UP_004 / 放量大涨 / SIM_BUY_CANDIDATE / medium_to_high`
   - trade_count: 13
   - win_rate: 69.23%
   - average_return_pct: 3.81%
   - total_return_pct: 49.55%
   - worst_return_pct: -5.20%
   - 判断：收益不错但样本少且风险等级偏高，只能做小额 dry-run 和人工复核，不应放大仓位。

4. `LEGACY_VP_SINGLE_005 / 放量小阴小阳线 / WAIT_CONFIRMATION / medium`
   - trade_count: 46
   - win_rate: 60.87%
   - average_return_pct: 1.22%
   - total_return_pct: 56.13%
   - worst_return_pct: -7.51%
   - 判断：可做辅助观察，优先级低于缩量小阴小阳线，且需要更强止损约束。

## 与原方案结合后的交易框架

当前最稳的框架是“四层合成”：

1. 潜力发现层
   - 用 Dataset2 的放量大阳线、放量大涨、缩量小阴小阳线等规则族扫描潜力股。
   - 优先找低位放量、试盘、回踩、重新站回、趋势未破坏的候选。
   - 涨停股优先扫描，但不等于优先买入。

2. 回踩确认层
   - `near_reclaim_watch` 只观察。
   - 只有重新站回信号价、均线支撑、强制分歧点或收盘前确认，才进入 `reclaim_review`。
   - `reclaim_review` 先做 dry-run_screen，不自动扩大仓位。

3. 稳定候选层
   - planner 当前选择近 12 轮中的 run 57 champion，而不是最新 run 59。
   - run 57 参数：`entry_delay_days=1`、`horizon_days=3`、`stop_loss_pct=0.06`、`take_profit_pct=0.18`、`attribution_filter=turning_point_requires_green_or_strong`。
   - validation: 15 笔，win_rate 73.33%，average_return_pct 8.17%，equal_weight_cumulative_return_pct 199.53%。
   - walk-forward: 33 笔，weighted_win_rate 72.73%，weighted_average_return_pct 8.61%，equal_weight_cumulative_return_pct 1156.83%。
   - 判断：这是当前策略调参最可信的证据来源之一，但仍只允许进入模拟盘复核。

4. 仓位纪律层
   - 模拟账户 20 万额度下，第一笔仍应以 100 股或 1%-3% 模拟资金为上限。
   - 确认主力拉升后可以分批加仓，但必须满足：fresh quote、组合风控通过、窗口验证通过、dry-run 成功、成交/持仓回读成功、后续走势确认。
   - 大涨后轻仓，不能因为规则族历史表现好就追涨重仓。

## 策略调控建议

下一步应优先提升“收益率超过 20%”所需的证据质量，而不是直接放开交易权限：

1. 把规则族表现记忆接入候选评分
   - `放量大阳线` 和 `缩量小阴小阳线` 可作为加分项。
   - 样本少的 `放量大涨` 只能小幅加分，并受高位风险惩罚。
   - `WAIT_CONFIRMATION` 默认不能直接买，只有回踩确认后才可进入 dry-run。

2. 扩展 offhour replay
   - 周末继续跑 complete-window 和 walk-forward。
   - 对每个规则族统计 1/3/5/8 日收益、MFE、MAE、最大回撤、成交拒绝和涨跌停阻断。
   - 目标不是更多交易，而是找到稳定超过 20% cumulative return 且折间不崩的组合。

3. 训练样本从“规则卡”转成“实例卡”
   - 每条训练样本必须包含 symbol、signal_date、entry/exit、forward_return、drawdown、volume_ratio、limit_status、benchmark_return。
   - Dataset2 原始规则只作为弱标签和解释，不作为最终监督标签。

4. 模拟盘训练只采集小额证据
   - 真实点击模拟盘前，仍要经过 detect -> dry_run_screen -> risk gate -> 100 股小额测试。
   - 成功、未成交、撤单、阻断、页面识别失败都要进入 Dataset2 候选样本。
   - 当某规则族在模拟盘回读中持续通过，才考虑提高模拟仓位。

5. AI/Codex 的角色
   - Codex 继续做监督者和调控者：检查安全、审查证据、调度 offhour/CLI、比较策略表现。
   - AI 可以提出权重候选和解释，但不能自动修改生产规则、不能绕过风控、不能开真实交易。

## 当前结论

这一轮学习后，系统判断力的提升点是：终于开始把“规则族文字标签”转成“规则族历史表现记忆”。目前最值得继续深挖的是：

- `LEGACY_VP_SINGLE_006` 缩量小阴小阳线：作为回踩确认/吸筹后延续观察器。
- `LEGACY_VP_SINGLE_001` 放量大阳线：作为强势启动候选发现器。
- run 57 champion 参数组：作为稳定候选和交易时段 planner 的主参考。

暂时不应做的事：

- 不根据 Dataset2 标签直接买入。
- 不因为回测 cumulative return 高就放开实盘。
- 不自动改 `rules.yaml`。
- 不扩大到真实交易。

下一轮工程重点：把 `rule_family_performance_memory` 接入 offhour model candidate 和 simulation planner 的候选评分说明，让候选不只看单次 run，还看规则族长期表现、回踩确认状态和模拟盘回读质量。

## 工程补充：planner 说明层接入

本轮已经把 `rule_family_performance_memory` 接入 `SimulationPlanner` 的 offhour review note 层。实现方式是读取最近一次 `dataset2_training_run` 审计事件中的规则族表现记忆，生成一条轻量说明：

- 当前真实库读取到 event_id: 122
- staging_groups: 148
- backtest_trades: 446
- top_family: `LEGACY_VP_SINGLE_001/放量大阳线/SIM_BUY_CANDIDATE`
- trades: 37
- win_rate: 64.86%
- avg_return: 3.80%
- worst_return: -5.17%

这个接入只影响 `risk_notes`/review explanation，不改变：

- `action`
- `allowed`
- `quantity`
- `position_ratio`
- risk gates
- production rules

也就是说，交易时段 planner 会“看见”规则族长期表现，但它仍不能因此自动扩大仓位或放开交易权限。

## 工程补充：offhour scorecard 接入

本轮进一步把规则族表现记忆接入非交易时段模型候选 scorecard。新生成的 offhour run 61 已验证：

- status: `completed`
- signal_count: 5
- sandbox evaluated_count: 5
- artifact_written: true
- `rule_family_review_gate.status`: `passed_for_review`
- `allowed_effect`: `scorecard_review_priority_only`
- `writes_rules_yaml`: false
- `auto_apply`: false
- `live_trading_enabled`: false

最新 artifact detail 中可见：

- memory_status: `ready`
- backtest_trade_count: 446
- top family: `LEGACY_VP_SINGLE_001 / 放量大阳线 / SIM_BUY_CANDIDATE`
- trade_count: 37
- win_rate: 64.86%
- average_return_pct: 3.80%
- worst_return_pct: -5.17%
- strategy synthesis 已包含 `rule_family_performance_memory`

这一步的意义是：非交易时段 scorecard 现在能同时表达“参数优化结果”和“规则族长期表现”。它仍然只是候选解释和人工审查材料，不会自动写入生产规则，也不会提升交易权限。

## 工程补充：三因子候选审查框架

本轮继续把 scorecard 从“展示证据”推进到“解释候选优先级”。新增 `candidate_review_priority_framework.v1`，使用四个 review-only 因子：

1. `stable_candidate_parameters`
   - 来自 stable candidate / signal optimization。
   - 衡量参数组是否通过验证收益、胜率和 walk-forward。

2. `rule_family_performance`
   - 来自 Dataset2 规则族表现记忆。
   - 衡量规则族历史 replay 胜率、平均收益、样本数和最差回撤。

3. `reclaim_confirmation_state`
   - 来自 reclaim watchlist。
   - 区分 `reclaim_review`、`near_reclaim_watch`、`pending_future_data` 和失败拉升风险。

4. `sim_cockpit_execution_evidence`
   - 来自模拟盘 action/readback 证据。
   - 衡量 dry-run、executed、readback 和 blocked 情况。

真实 offhour run 62 验证结果：

- status: `completed`
- artifact_written: true
- review_priority_score: 44
- review_priority_tier: `watch_for_confirmation`
- stable_candidate_parameters: 0
- rule_family_performance: 30
- reclaim_confirmation_state: 4
- sim_cockpit_execution_evidence: 10
- allowed_effect: `review_priority_only`
- live_trading_enabled: false
- next_action: `Watch for reclaim/support confirmation and collect more offhour or readback evidence.`

解释：当前规则族长期表现和模拟盘证据有价值，但本轮小规模 offhour 没有拿到足够强的 stable candidate 参数证据，reclaim 状态也主要是等待下一根 ready bar。因此系统正确地把候选留在“等待确认/观察”层，而不是提升为模拟执行优先级。

这比单看收益更稳：即便规则族历史平均收益为正，也必须同时看稳定参数、回踩确认和执行回读，才能逐步提高仓位信心。
