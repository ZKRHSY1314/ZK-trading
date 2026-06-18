# 2026-06-15 策略学习记录：候选优先级与主力阶段复核

## 本轮目标

本轮把浏览器调研、Dataset1 交易经验、Dataset2 规则库、offhour run 63 的真实运行证据合并成一个可执行的研究框架。目标不是放大权限，而是提高判断质量：先把候选股按证据强弱排序，再等待交易时段的回踩/站回/风控确认，最后只进入模拟盘 dry-run 或小额模拟验证。

当前边界保持不变：
- `live_trading_enabled=false`
- `review_only=true`
- `simulation_only=true`
- 不改 `rules.yaml`
- 不写生产模型
- 不连接券商、不保存凭证、不触碰真实委托

## 浏览器调研吸收

本轮通过浏览器核对了三个公开量化框架，吸收方法，不整包引入：

- QSTrader: 事件驱动回测。对本项目的启发是把信号、风控、模拟成交、持仓回读、训练样本都变成同一条审计事件链，便于从历史 replay 平滑过渡到模拟盘。
- vectorbt: 批量参数实验。对本项目的启发是周末/非交易时段应该大规模跑 Dataset2 参数组合、确认窗口、回撤约束，而不是凭单次收益改权重。
- Investing Algorithm Framework: 回测结果索引和策略排序。对本项目的启发是保留每次研究循环的 scorecard、artifact hash、run_id，并让 Codex 只调整研究优先级，不直接改生产规则。

参考：
- https://github.com/quantstart/qstrader
- https://github.com/polakowo/vectorbt
- https://github.com/coding-kitties/investing-algorithm-framework

## Dataset1 学习结论

Dataset1 的强项是交易纪律和真实教训，不是机器学习强标签。当前最有价值的规律是：

- 成功样本常见结构：强势股或隔夜计划 -> 次日逢高/涨停分批卖 -> 不恋战。
- 失败样本高频结构：买早、第二笔加仓太急、上冲时全仓、未等均线/启稳、未按 10:30 前或集合竞价计划处理。
- 三维通信样本的价值不只是“赚到钱”，而是提示主升浪后要用分批卖和大涨大卖纪律锁定收益。
- 乐凯胶片样本提示：计划执行失败会比判断方向错误更伤收益，因此系统必须记录“应执行但未执行”的训练样本。

因此 Dataset1 应作为动作纪律层：
- 对 Dataset2 的 `SIM_BUY_CANDIDATE` 做升权、降权或阻断。
- 对 `WAIT_CONFIRMATION` 判断是否已经有回踩确认、均线支撑或重新站回。
- 对大涨、弱开、跌破保护位、未按计划卖出输出硬风险标签。

## Dataset2 学习结论

Dataset2 的强项是量价、筹码、竞价、分时形态规则。它适合做候选解释、弱标签、规则族归因；不适合直接训练成买卖模型，因为当前质量报告已经指出它缺少真实 `signal_date / stock_code / entry / exit / forward_return` 等监督字段。

本轮读到的关键规则族：
- 低位筹码密集后放量突破，更适合候选池扩张。
- 上涨途中缩量回调、缩量小阴小阳，更适合等待确认和回踩复核。
- 顶部放量滞涨、放量大阴、炸板和高位高换手，应优先降权或卖出/规避。
- 盘口、竞价和分时规则只能作为交易时段确认，不应在无实时读屏证据时直接触发动作。

## run 63 证据

本轮主库重新运行 offhour research：

- `run_id=63`
- `status=completed`
- `strategy_replay.signal_count=50`
- `model_candidate.artifact_written=true`
- `candidate_review_priority_score=40`
- `candidate_review_priority_tier=watch_for_confirmation`
- `allowed_effect=review_priority_only`
- `live_trading_enabled=false`

四因子拆解：
- `rule_family_performance`: 30 分。规则族样本数、胜率和平均收益通过复核。
- `sim_cockpit_execution_evidence`: 10 分。已有模拟驾驶舱证据和回读路径。
- `reclaim_confirmation_state`: 0 分。仍在等待下一根可确认 K 线或交易时段站回。
- `stable_candidate_parameters`: 0 分。稳定参数证据不足，不能提升仓位。

结论：当前不是买入许可，而是观察和确认队列。系统可以把它排到更高复核优先级，但不能放大仓位或自动买入。

## 融合后的策略框架

### 阶段 1：低位吸筹候选

候选条件偏重：
- 低位或非历史高位。
- 筹码密集、缩量整理、低位放量突破、倍量柱或温和放量。
- Dataset2 形态命中，但 Dataset1 纪律没有“买早/追高/大涨后重仓”风险。

动作：只进入候选池和 offhour replay，不进入模拟买入。

### 阶段 2：试盘与回踩确认

确认条件偏重：
- 信号后不破关键支撑、均线或前压力转支撑。
- 回踩缩量，重新站回信号价或均价线。
- 没有弱开、炸板、高位放量滞涨、连续亏损或组合风控阻断。

动作：进入 `watch_for_confirmation` 或 `dry_run_screen`，仍不自动真实下单。

### 阶段 3：模拟盘小额试单

只有同时满足以下条件才允许模拟点击：
- 同花顺模拟炒股窗口已验证。
- `SIMULATION_SCREEN_CLICK` 和坐标锚点全通过。
- 风控 gate 全通过。
- 候选 score 至少进入 `simulation_review_candidate`。
- 交易时段 fresh quote 仍确认站回/支撑。

仓位建议：20 万模拟资金下，第一笔只做 1%-2% 或 100 股级别验证；盈利、回读和风控均确认后再分批加仓。加仓不是因为看好，而是因为证据链变强。

### 阶段 4：退出与复盘

卖出纪律优先级高于买入冲动：
- 大涨、大幅冲高、涨停炸板、顶部放量滞涨时先减仓。
- 弱开不修复、跌破保护位、均价线压制时降低或退出。
- 所有“未成交、撤单、错过卖点、未按计划执行”都进入 Dataset2 候选训练样本。

## 下一轮研究任务

1. 非交易时段继续批量回测，重点提升 `stable_candidate_parameters` 因子。
2. 把 Dataset2 的规则族按 `pattern_id/category/action/risk` 做更多 walk-forward 分层，避免少数大样本掩盖高风险小样本。
3. 对三维通信、金螳螂、乐凯胶片建立阶段样本卡：吸筹、试盘、拉升、出货、失败执行。
4. 交易时段先做 detect-only 和 dry-run，只有 `watch_for_confirmation` 升级到 `simulation_review_candidate` 后才允许小额模拟。
5. 前端继续把候选优先级、风控 gate、模拟回读、Dataset2 训练样本挂到同一个审查面板。

## run 64 增量学习

本轮修正了一个信息损失点：候选优先级原本只读取“最近信号 watchlist”，没有吸收 `reclaim_transition_study` 中的历史回踩转换结果。这样会导致当前没有下一根 K 线时，系统只知道“等待确认”，却没有把历史上“站回信号价后的表现”作为审查证据。

修正后重新运行主库 offhour research：

- `run_id=64`
- `status=completed`
- `candidate_review_priority_score=48`
- `candidate_review_priority_tier=watch_for_confirmation`
- `reclaim_confirmation_state.score_points=8`
- `allowed_effect=review_priority_only`
- `live_trading_enabled=false`

新增 reclaim 证据理由：

- `waiting_for_next_ready_bar`
- `historical_reclaim_transition_positive`
- `historical_reclaim_cumulative_return_above_20pct`
- `failed_markup_risk_penalty`

解释：历史上 `reclaim_review` 的转换样本有正收益和较大累计收益，因此可以提高审查优先级；但当前最近信号仍缺少下一根可用 K 线，且存在失败拉升风险惩罚，所以不能升级为模拟买入，只能维持 `watch_for_confirmation`。这让系统比 run 63 更“懂证据”，但没有放松权限。

## run 65 参数失败归因

本轮新增 `signal_parameter_failure_attribution.v1`，用于解释 `stable_candidate_parameters` 为什么仍然是 0 分。它只做审计和复核，不放宽阈值、不修改 `rules.yaml`、不改变交易权限。

主库重新运行 offhour research：

- `run_id=65`
- `status=completed`
- `signal_optimization.status=blocked`
- `candidate_review_priority_score=48`
- `stable_candidate_parameters.score_points=0`
- `allowed_effect=review_priority_only`
- `live_trading_enabled=false`

失败归因：

- `train_win_rate_below_floor=210`
- `train_trade_count_too_low=180`
- `train_average_return_below_floor=66`
- `validation_trade_count_too_low=42`
- `walk_forward_blockers=["too_few_candidates_for_walk_forward"]`
- `base_candidate_count=0`

最关键的新发现是：验证集里已经出现了几组高收益影子参数，但验证交易数只有 2 笔，低于最低 3 笔要求，因此不能升级为稳定参数。代表性 near-miss：

- `confirmation_filter=dataset1_low_risk_stabilized_reclaim`
- `entry_delay_days=1`
- `horizon_days=3`
- `validation_trade_count=2`
- `validation_win_rate=1.0`
- `validation_average_return_pct=17.293508`
- `validation_equal_weight_cumulative_return_pct=37.391889`

解释：这不是“策略无效”，而是“有潜力但样本外证据不足”。下一步应扩大历史实例、补齐 recent signal 的可回测窗口、对站回确认类规则建立 shadow-to-reviewed 晋级机制。不能直接把 2 笔验证交易当作稳定参数，也不能据此放大仓位。

## 深度学习融合心得

本轮通过浏览器复核了几个外部思想，并和 Dataset1 / Dataset2 / run 65 证据合并：

- vectorbt / walk-forward 思路：参数优化必须看时间切分、样本外和参数面稳定性。映射到本项目，就是 `near_miss_validation_candidates` 可以进入 shadow evidence，但必须等更多历史实例和 walk-forward 通过后，才允许影响模拟权重。
- QSTrader / event-driven 思路：信号、风控、模拟成交、持仓、回读要分层。映射到本项目，就是 offhour replay 不能直接跳到同花顺点击，必须经过 planner、risk gate、sim-cockpit window verification 和 readback。
- Wyckoff 阶段思想：吸筹、试盘、拉升、出货要作为阶段序列，而不是单根 K 线。映射到本项目，就是三维通信、金螳螂、乐凯胶片这类样本应进入阶段卡：长期吸筹 -> 试盘线 -> 回踩站回 -> 主升 -> 出货/大涨大卖。
- A 股涨跌停研究：价格接近涨停会受到制度和情绪影响，不能把涨停附近信号当作必然可成交。映射到本项目，就是涨停、炸板、高位放量必须继续作为成交模型和风险模型的一部分。

Dataset1 与 Dataset2 的合并策略：

- Dataset2 负责“发现形态”：放量大阳、缩量回调、量价配合、竞价/分时弱标签。
- Dataset1 负责“约束动作”：不买早、不买高、不越跌越补、大涨大卖、分批止盈、计划执行。
- run 65 的 shadow 参数负责“提出候选”：站回确认类规则有高收益迹象，但需要更多样本。
- Codex 负责“监督”：只提升研究优先级和模拟复核优先级，不绕过风控，不碰真实交易。

下一步执行顺序：

1. 扩大 offhour replay 的历史实例集，优先补足 `dataset1_low_risk_stabilized_reclaim` 和 `dataset1_stabilized_reclaim` 的验证交易数。
2. 建立 `shadow_parameter_evidence` 到 `stable_candidate_parameters` 的晋级规则：至少 3 笔验证、walk-forward 候选数充足、累计收益超过 20%、平均收益为正、无重大回撤。
3. 对三维通信、金螳螂、乐凯胶片补阶段标签，训练“主力一到两年吸筹 -> 试盘 -> 拉升 -> 出货”的阶段识别。
4. 交易时段只在 fresh quote 确认站回、风控通过、模拟窗口验证通过后，执行小额模拟 dry-run 或模拟点击。

参考来源：

- https://vectorbt.dev/getting-started/resources/
- https://github.com/mhallsmoore/qstrader
- https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-I/
- https://www.wyckoffanalytics.com/wyckoff-method/
- https://voxchina.org/show-3-49.html
- https://www.princeton.edu/~wxiong/papers/PriceLimit.pdf

## run 66 shadow 参数证据层

本轮把 run 65 的 near-miss 参数正式升级为 `shadow_parameter_evidence.v1`。这不是稳定参数，也不会影响仓位和下单，只用于告诉系统：哪些参数已经出现 20%+ 收益迹象，但还缺样本外交易数。

主库运行结果：

- `run_id=66`
- `status=completed`
- `signal_optimization.status=blocked`
- `candidate_review_priority_score=48`
- `shadow_parameter_evidence.status=review_ready`
- `shadow_candidate_count=5`
- `live_trading_enabled=false`

最强 shadow candidate：

- `confirmation_filter=dataset1_low_risk_stabilized_reclaim`
- `entry_delay_days=1`
- `horizon_days=3`
- `stop_loss_pct=0.04`
- `take_profit_pct=0.08`
- `train_trade_count=3`
- `train_win_rate=1.0`
- `train_equal_weight_cumulative_return_pct=25.181742`
- `validation_trade_count=2`
- `validation_win_rate=1.0`
- `validation_average_return_pct=17.293508`
- `validation_equal_weight_cumulative_return_pct=37.391889`
- `missing_validation_trades=1`

证据标签：

- `validation_return_above_shadow_floor`
- `dataset1_experience_aligned_confirmation`
- `reclaim_confirmation_family`

解释：这组参数已经符合“收益超过 20%”的目标线索，但由于验证交易数只有 2 笔，仍被 `validation_trade_count_below_stable_floor` 阻断。它下一步只能触发 `expand_history_and_review_priority_only`，不能触发模拟买入、仓位增加、规则文件修改或真实交易。

下一步研究任务更新：

1. 专门扩充 `dataset1_low_risk_stabilized_reclaim`、`dataset1_stabilized_reclaim`、`strong_reclaim` 三类站回确认历史样本。
2. 补齐最近信号的可回测窗口，降低 `incomplete_exit_window_count` 对验证集的侵蚀。
3. 把 shadow candidate 加入周末深度研究清单：只有验证交易数 >= 3 且 walk-forward 候选数充足，才允许进入 `stable_candidate_parameters` 审查。
4. 继续保持模拟盘/审查边界：shadow 证据只是提高研究优先级，不直接下单。

## run 68 扩展历史与 walk-forward 复核

本轮新增 `shadow_parameter_expanded_history_review.v1`：主优化仍只用最近窗口，shadow 层单独用完整去重信号集复核高收益线索。这样可以回答一个关键问题：run 66 的 37.39% 是否只是 2 笔样本偶然值。

主库运行结果：

- `run_id=68`
- `status=completed`
- `expanded_signal_count=164`
- `stable_threshold_review_count=5`
- `walk_forward.status=blocked`
- `live_trading_enabled=false`

扩展验证最强参数：

- `confirmation_filter=dataset1_stabilized_reclaim`
- `entry_delay_days=1`
- `horizon_days=3`
- `stop_loss_pct=0.04`
- `take_profit_pct=0.08`
- `eligible_signal_count=57`
- `train_trade_count=16`
- `train_win_rate=0.625`
- `train_equal_weight_cumulative_return_pct=40.080345`
- `validation_trade_count=10`
- `validation_win_rate=0.8`
- `validation_average_return_pct=6.807137`
- `validation_equal_weight_cumulative_return_pct=88.872177`

这说明站回确认类参数不是 2 笔偶然值；在扩展历史上，它已经明显超过 20% 收益目标，并且交易数足够进入更严审查。

但是 walk-forward 仍阻断：

- `walk_forward_trade_count=19`
- `weighted_win_rate=0.631579`
- `weighted_average_return_pct=4.279578`
- `total_equal_weight_cumulative_return_pct=112.642737`
- `fold_count=4`
- `min_fold_trade_count=2`
- `min_fold_win_rate=0.333333`
- 阻断原因：`walk_forward_fold_trade_count_too_low`、`walk_forward_min_fold_win_rate_too_low`

解释：总收益和加权胜率已经很强，但时间折叠中有一段样本少且胜率低，说明策略可能依赖行情阶段。当前结论应从“扩样本”升级为“分阶段/分市场环境复核”，而不是直接放开交易。

下一步研究任务更新：

1. 对 `dataset1_stabilized_reclaim` 做 phase/context 分层：吸筹末端、试盘后回踩、主升初期、出货末端分别统计。
2. 对 walk-forward 的弱 fold 提取交易样本，查明是市场环境、板块、个股阶段还是信号质量导致胜率降到 0.333333。
3. 若分层后某一阶段满足 fold trade count、fold win rate、累计收益和回撤约束，再进入 `stable_candidate_parameters` 审查队列。
4. 继续禁止把 run 68 直接用于自动买入；它现在最多提高模拟复核优先级和周末研究优先级。

## run 69 监督建议落地

本轮只验证结构化 `next_action` 是否能在真实主库运行中输出：

- `run_id=69`
- `stable_threshold_review_count=5`
- `walk_forward.status=blocked`
- `walk_forward.reasons=["walk_forward_fold_trade_count_too_low", "walk_forward_min_fold_win_rate_too_low"]`
- `expanded_next_action=expand_reclaim_samples_across_more_time_folds`
- `live_trading_enabled=false`

结论：Codex 监督层现在会把高收益 shadow 参数导向“扩充时间折叠样本”，而不是导向“放宽交易”。这是当前阶段正确的风险姿态。

## run 70 弱 fold 归因

本轮新增 `shadow_walk_forward_weak_fold_attribution.v1`，专门解释 run 68/69 的 walk-forward 为什么挡住，而不是只报告 `blocked`。

主库运行结果：

- `run_id=70`
- `walk_forward.status=blocked`
- `walk_forward.reasons=["walk_forward_fold_trade_count_too_low", "walk_forward_min_fold_win_rate_too_low"]`
- `weak_fold_count=2`
- `weak_trade_count=5`
- `weak_next_action=expand_reclaim_samples_across_more_time_folds`
- `live_trading_enabled=false`

弱 fold 交易汇总：

- `weak_trade_count=5`
- `win_count=2`
- `loss_count=3`
- `win_rate=0.4`
- `average_return_pct=1.197152`
- `cumulative_return_pct=5.356569`
- `best_return_pct=7.815651`
- `worst_return_pct=-4.189149`

弱 fold 阶段分布：

- `distribution_or_failed_markup=2`
- `stabilization_probe=1`
- `missed_follow_through=2`

弱 fold 标签分布提示：

- `distribution_or_stall_risk=4`
- `strong_momentum_opportunity=4`
- `broad_only_risk=2`
- `filtered_loss_sample=2`
- `stop_loss_triggered=2`
- `follow_through_winner=2`

解释：弱 fold 并不是单纯亏损，5 笔交易整体仍为正收益；真正的问题是“机会”和“分发/失败拉升风险”混在一起。两笔止损样本都带有 `distribution_or_failed_markup` 或强分发风险标签，而两笔大肉样本是 `missed_follow_through`。这说明 `dataset1_stabilized_reclaim` 的下一步不是降低收益阈值，而是加入阶段/风险分层：

- 对 `distribution_or_failed_markup`、`distribution_or_stall_risk`、高位高波动板块样本继续降权或单独审查。
- 对 `missed_follow_through` 且无硬风险标签的站回样本提高模拟复核优先级。
- 对 `stabilization_probe` 样本继续收集，不急于下单。

下一步研究任务更新：

1. 在 shadow expanded review 之上新增 phase/context split，把 `dataset1_stabilized_reclaim` 分成 risk-mixed、follow-through、stabilization 三组。
2. 对 risk-mixed 组测试更强确认：`strong_reclaim`、低开过滤、失败拉升过滤、科创/创业板高波动过滤。
3. 对 follow-through 组测试是否能保持 20%+ 收益且通过 fold 交易数和 fold 胜率。
4. 只有分层后的子策略通过 walk-forward，才允许进入稳定参数候选；当前仍不允许自动买入。

## run 71 phase/context split

本轮新增 `shadow_phase_context_split.v1`，把 `dataset1_stabilized_reclaim` 的扩展历史交易按上下文分为：

- `risk_mixed`
- `follow_through`
- `stabilization`
- `other`

主库运行结果：

- `run_id=71`
- `phase_split.status=review_ready`
- `overall_trade_count=26`
- `overall_win_rate=0.692308`
- `overall_average_return_pct=3.995078`
- `overall_cumulative_return_pct=164.572796`
- `passed_context_buckets=["risk_mixed"]`
- `phase_split_next_action=test_distribution_and_high_volatility_filters`
- `live_trading_enabled=false`

分组结果：

### risk_mixed

- `trade_count=19`
- `win_rate=0.684211`
- `average_return_pct=4.799289`
- `cumulative_return_pct=133.993999`
- `best_return_pct=21.603745`
- `worst_return_pct=-4.189149`
- 主要 pattern：`LEGACY_VP_SINGLE_006`、`LEGACY_VP_SINGLE_005`、`LEGACY_VP_SINGLE_001`、`LEGACY_VP_UP_004`

解释：risk_mixed 组收益最强，但它同时包含大量 `distribution_or_stall_risk`、高波动板块风险和止损样本。它不能被直接当作可交易组；正确动作是测试分发风险过滤、高波动板块过滤和更强站回确认。

### follow_through

- `trade_count=1`
- `win_rate=1.0`
- `average_return_pct=7.786232`
- `cumulative_return_pct=7.786232`

解释：纯 follow-through 样本质量高，但样本太少，暂时只能作为扩样本方向。

### stabilization

- `trade_count=6`
- `win_rate=0.666667`
- `average_return_pct=0.816554`
- `cumulative_return_pct=4.900408`

解释：stabilization 组胜率还可以，但收益不足 20%，适合继续观察，不适合提升仓位。

综合判断：

`dataset1_stabilized_reclaim` 的收益优势真实存在，但当前收益主要集中在风险和机会混杂的样本中。下一步不应该放宽交易，而应该做过滤实验：

1. `risk_mixed` 去掉高波动板块后是否仍保持 20%+。
2. `risk_mixed` 去掉 Dataset1 分发风险标签后是否仍保持 20%+。
3. `risk_mixed` 改成 `strong_reclaim` 后是否减少止损并通过 walk-forward。
4. `follow_through` 扩样本后是否能达到稳定参数要求。
