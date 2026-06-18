# 2026-06-13 策略学习与融合笔记

## 安全边界

- 本文只服务于研究、回测、沙盒模拟和同花顺模拟盘训练。
- 不连接真实券商，不保存真实账户凭证，不生成真实委托。
- 候选权重只能先进入 review-only / simulation-only 证据链；不得自动写入 `configs/rules.yaml`。

## 外部学习结论

1. QSTrader 的核心价值是把信号生成、组合构建、风控、执行和模拟账户解耦。这个思想适合 ZK-trading：Dataset2 负责信号，simulation planner 负责是否允许行动，execution model 负责成交约束，Dataset2/经验库负责复盘。
   来源：https://github.com/mhallsmoore/qstrader

2. VectorBT 的价值不是替代当前系统，而是提醒我们在非交易时段做批量参数实验。适合用来指导本项目的“候选权重网格”：例如成交额阈值、量比阈值、涨幅区间、回踩天数、持有期、止盈止损。
   来源：https://vectorbt.dev/

3. Backtrader 的滑点文档强调：没有滑点和成交约束的回测会高估结果。本项目 V2.0 的涨跌停阻断、成交额参与率、partial/rejected execution event 必须继续保留。
   来源：https://www.backtrader.com/docu/slippage/slippage/

4. A 股涨跌停制度会带来上限附近的磁吸和次日获利了结风险。因此涨停/接近涨停不能简单视为买入信号，必须结合是否一字板、成交额、封单持续性、次日可成交性和位置阶段。
   来源：https://voxchina.org/show-3-49.html

5. Wyckoff 与 Accumulation/Distribution 的共同启发是：主力行为不能只看一天的强弱，要看长期吸筹、试盘、突破、回踩确认和派发。它和项目中三维通信、金螳螂、乐凯胶片这类阶段样本是同一类分析框架。
   来源：https://www.wyckoffanalytics.com/wyckoff-method/
   来源：https://trendspider.com/learning-center/accumulation-distribution-a-d-trading-strategies/

## 与原方案的融合

### 当前最有价值的策略方向

`LEGACY_VP_SINGLE_006` 在最近非交易时段沙盒中表现最好，属于“量价单日形态 + 后续跟随确认”方向。它不应该直接变成追高买入，而应转成三段式模拟策略：

1. 观察确认：出现 Dataset2 匹配信号后，只进入 watch/confirmation。
2. 小额试单：次日或回踩确认后，若成交额、涨跌停、市场环境、组合风控全部通过，最多用模拟资金 4%-8% 做一笔测试。
3. 分布加仓：只有已成交持仓回读、走势不破关键成本线、成交没有明显派发，才允许第二段模拟加仓。

### 需要重点避免

- 大阳线后无量冲高：容易是假突破或派发末端。
- 一字涨停：回测必须拒绝买入，模拟盘也不应假设可成交。
- 一字跌停：回测必须阻断卖出，风控要把这种情况标为 liquidity/exit risk。
- 高位阶段相似金螳螂派发完成：只作为训练样本，不作为短线追高样本。

## 已落地的代码方向

本次新增 Dataset2 signal-level backtest：

- 输入：Dataset2 replay 的 `SIM_BUY_CANDIDATE` / `WAIT_CONFIRMATION` 信号。
- 买入：信号后一根可用日线的开盘价，带滑点、100 股最小手数、成交额参与率、涨跌停阻断。
- 卖出：5 日内止损、止盈或持有期退出，同样带成交约束。
- 输出：closed signal trades、pattern performance、simulation weight gate。

它解决的问题是：以前沙盒能看出信号有效，但正式 RuleEngine backtest 没有成交；现在可以先验证“Dataset2 信号如果进入模拟计划，是否会产生可成交闭环”。

## 权重调整原则

只有同时满足以下条件，才进入模拟权重候选：

- 沙盒样本数不少于 10。
- 沙盒胜率不低于 65%。
- 沙盒平均收盘收益为正且至少 1%。
- Dataset2 signal-level backtest 产生闭合交易。
- signal backtest 胜率不低于 50%，平均收益为正。
- 仍然 `writes_rules_yaml=false`、`auto_apply=false`，需要人工 review。

只有在 RuleEngine formal backtest 也有成交、收益为正、回撤可控后，才考虑把候选权重变成生产规则修改。

## 下一步研究任务

1. 把 `LEGACY_VP_SINGLE_006` 的 signal backtest 结果接到前端非交易研究面板。
2. 为 `LEGACY_VP_SINGLE_006` 增加回踩确认版本：突破后 1-3 日不破关键成本线再模拟买入。
3. 增加参数网格：量比阈值、涨幅阈值、成交额阈值、持有期、止盈止损。
4. 对三维通信、金螳螂、乐凯胶片做同一套阶段复盘，明确哪些是可买阶段，哪些只是训练阶段。
5. 只有当候选策略连续多轮 signal backtest 和 formal backtest 都优于基线，才提交权重修改建议。

## 2026-06-13 第二轮优化结果

本轮把数据集1和数据集2分工明确：

- 数据集2负责结构化信号：量价标签、`SIM_BUY_CANDIDATE`、`WAIT_CONFIRMATION`、风险标签。
- 数据集1负责经验约束：不要买早、等启稳、分批试探、卖强不追高、弱开减仓。

在 30 条 Dataset2 replay 信号上做时间顺序 70/30 切分和参数网格：

- 固定参数基线：29 笔闭合模拟交易，胜率 62.07%，平均单笔收益 1.93%，等权复利收益 67.42%。
- 总体最佳参数：`entry_delay_days=1`、`horizon_days=3`、`stop_loss_pct=0.06`、`take_profit_pct=0.18`。验证集 9 笔，胜率 77.78%，平均单笔收益 5.01%，等权复利收益 52.01%。
- 数据集1经验对齐最佳参数：`entry_delay_days=3`、`horizon_days=8`、`stop_loss_pct=0.04`、`take_profit_pct=0.12`。验证集 9 笔，胜率 44.44%，平均单笔收益 3.64%，等权复利收益 34.18%。

解释：

- 总体最佳更适合短线快速确认，胜率和平均收益都更好。
- 经验对齐版本符合“不要买早、等启稳”，收益仍超过 20%，但胜率不足，需要继续增加过滤条件。
- 下一轮重点不是放大仓位，而是减少经验对齐版本的失败交易：增加市场环境、阶段位置、成交额持续性、弱开过滤和金螳螂式派发风险过滤。

## 2026-06-13 第三轮优化结果

第三轮把数据集1的“等启稳后买”转成可回测的确认过滤器，加入参数网格：

- `entry_close_above_signal`：入场日收盘重新站上信号日收盘价。
- `entry_green_above_signal`：入场日收红，且重新站上信号价。
- `strong_reclaim`：站上信号价至少 1%，入场日收红，且不是明显弱开。

30 条信号样本：

- 最佳经验对齐参数：`entry_delay_days=3`、`horizon_days=8`、`stop_loss_pct=0.04`、`take_profit_pct=0.12`、`confirmation_filter=entry_close_above_signal`。
- 验证集 6 笔，胜率 66.67%，平均单笔收益 7.56%，等权复利收益 52.52%，过滤掉 3 条未重新站上信号价的交易。
- 对比上一轮经验对齐版本：胜率从 44.44% 提升到 66.67%，等权复利收益从 34.18% 提升到 52.52%。

60 条信号样本：

- 总体最佳参数：`entry_delay_days=1`、`horizon_days=10`、`stop_loss_pct=0.06`、`take_profit_pct=0.18`、`confirmation_filter=entry_close_above_signal`。验证集 12 笔，胜率 83.33%，平均单笔收益 6.19%，等权复利收益 101.49%。
- 最佳经验对齐参数：`entry_delay_days=2`、`horizon_days=5`、`stop_loss_pct=0.04`、`take_profit_pct=0.12`、`confirmation_filter=entry_green_above_signal`。训练集 21 笔，胜率 76.19%，等权复利收益 199.82%；验证集 7 笔，胜率 71.43%，平均单笔收益 4.85%，等权复利收益 36.66%。

当前判断：

- Dataset2 的缩量小阴小阳线 / 量价整理信号，在 Dataset1 的“等启稳”经验过滤后，胜率和收益都有明显改善。
- 新策略还不能进生产规则，因为正式 RuleEngine backtest 仍需打通成交与权重映射。
- 可以进入下一阶段：simulation planner 的 review-only 权重候选层。候选层只提高模拟计划排序或解释置信度，不自动下单、不写 `rules.yaml`、不触碰真实账户。

## 2026-06-13 第四轮学习融合

本轮把浏览器检索到的公开框架方法、数据集1经验、数据集2规则和当前系统能力合并成一个更清晰的研究闭环。

### 外部框架映射

- VectorBT 强调用向量化/批量方式快速测试大量策略、参数、资产和时期；本项目不整包引入，但采用其“参数网格 + 多样本比较”的思想，把 `entry_delay_days`、`horizon_days`、`stop_loss_pct`、`take_profit_pct`、`confirmation_filter` 纳入离线优化。
- QSTrader 强调模块化、调度式回测，并把信号生成、组合构建、风控、执行和模拟券商会计解耦；本项目对应为 Dataset2 replay、PortfolioRisk、BacktestExecutionModel、Sim-Cockpit audit 分层。
- Backtrader 的基础流程强调先定义策略参数、指标、进出场逻辑，再注入引擎运行；本项目对应为“先研究参数，不直接改生产规则”。
- vn.py 的事件驱动引擎思路适合后续 V4/V5：行情事件、监控提醒、模拟盘动作、回读和训练样本都应作为可审计事件流，而不是一段直接点击脚本。

### 数据集1经验变成硬约束

数据集1不是普通指标库，它更像交易纪律库：

- 成功样本反复证明：大涨要卖、分批止盈、强制分歧点和隔夜强势股可作为机会，但第一笔要小、后续要看反馈。
- 失败样本反复证明：买早、买高、第二笔太急、越跌越补、弱开未减仓，是主要亏损来源。
- 选股策略强调：低位、适中市值、较低 PB、首日涨停更适合作为重点候选；高位股、过大市值、高 PB、已派发样本只适合训练和观察。
- 庄股成本法强调：长期横盘后的主力成本线和目标线可以用于判断潜在空间，但不能替代入场确认；接近目标区时应优先考虑分批止盈而不是追买。

### 已落地到代码

- `dataset1_stabilized_reclaim` 已纳入参数网格：要求入场日重新站上信号价、低点不能明显跌破信号价、日内走势不能太弱。
- Dataset1 约束新增到候选 scorecard：低位涨停优质股、庄股成本目标、启稳确认、分批试探、弱开减仓。
- 候选 artifact 新增 `strategy_synthesis` 字段，保留外部框架映射、当前最优参数、推广路径和硬安全边界。

### 当前融合策略

现在最合理的主策略不是“看到涨停就买”，而是：

1. 非交易时段：搜索低位强势/首板/放量候选，补齐日线数据。
2. Dataset2：识别量价形态，先打 `SIM_BUY_CANDIDATE` 或 `WAIT_CONFIRMATION`。
3. Dataset1：用“等启稳、别买早、别越跌越补、大涨减仓”过滤候选。
4. 回测：用 70/30 时间切分，只有样本外胜率和收益过线才进入模拟权重候选。
5. 模拟盘：第一笔只做小额试探；确认主力拉升和持仓回读后，才允许分布加仓。
6. 复盘：成交、未成交、风控阻断、页面识别失败都进入 Dataset2 候选训练样本。

### 下一步

- 把本轮 `strategy_synthesis` 在前端非交易研究面板展示出来。
- 用更大的历史样本做滚动 walk-forward 验证，防止 60 条样本过拟合。
- 给三维通信、金螳螂、乐凯胶片建立阶段标签：吸筹、试盘、主升、派发、派发后观察。
- simulation planner 只读取 review-only 权重候选，不自动写 `rules.yaml`。

## 2026-06-13 第五轮本地缓存验证

在不刷新外部历史数据的情况下，直接使用本地 `daily_bar_cache` 跑了一轮 80/60 离线研究：

- run_id：18。
- 结果状态：completed。
- ready symbols：48。
- Dataset2 replay 信号：60 条，其中 `WAIT_CONFIRMATION` 47 条、`SIM_BUY_CANDIDATE` 13 条。
- 默认 signal backtest：60 笔闭合交易，胜率 63.33%，平均单笔收益 2.44%，等权累计收益 288.32%。
- 新增 `dataset1_stabilized_reclaim` 后的最佳经验对齐参数：
  - `entry_delay_days=2`
  - `horizon_days=10`
  - `stop_loss_pct=0.04`
  - `take_profit_pct=0.12`
  - `confirmation_filter=dataset1_stabilized_reclaim`
- 训练集：26 笔，胜率 76.92%，平均单笔收益 5.96%，等权累计收益 327.47%。
- 验证集：7 笔，胜率 57.14%，平均单笔收益 3.83%，等权累计收益 28.57%。

判断：

- 新过滤器符合数据集1“等启稳”思想，也让收益保持为正。
- 但验证胜率 57.14% 低于当前 58% 门槛，所以 `signal_optimization_gate` 正确保持 blocked。
- `simulation_weight_gate` 可以进入人工 review，但不能自动写入生产规则，也不能自动放大仓位。

工程修复：

- 历史数据刷新不能和大网格优化塞进同一个超大 API 请求里。
- 已给内联历史刷新加上上限：`limit<=20`、`history_days<=240`，并在结果中写入 `inline_refresh_budget`，记录用户请求值与实际执行值。
- 后续如果要深度补历史，应走分批后台任务，而不是一次 API 等待完成。

## 2026-06-13 第六轮双门槛稳定候选

本轮把单次 70/30 验证和 rolling walk-forward 验证合并为“双门槛”：

- 单次验证必须满足：胜率不低于 58%，等权累计收益不低于 20%，平均收益为正，闭合交易数不少于 3。
- walk-forward 必须满足：至少 3 折，总交易数不少于 6，每折交易数不少于 3，加权胜率不低于 58%，最低折胜率不低于 40%，累计收益不低于 20%，单折损失不低于 -8%。
- 最终 `selected_stable_candidate` 必须同时满足以上两套证据；不再只选单次收益最高参数。

本地缓存 run_id 23 的稳定候选已经通过：

- 参数：`entry_delay_days=1`、`horizon_days=3`、`stop_loss_pct=0.04`、`take_profit_pct=0.08`、`confirmation_filter=entry_close_above_signal`。
- 70/30 验证集：5 笔，胜率 100%，平均单笔收益 4.26%，等权累计收益 23.08%。
- walk-forward：4 折，28 笔，加权胜率 82.14%，加权平均单笔收益 3.44%，总等权累计收益 150.71%。
- 最弱折：胜率 60%，等权累计收益 12.44%，未触发折级阻断。

解释：

- `entry_green_above_signal` 的 walk-forward 总分更高，但其 70/30 验证累计收益只有 16.45%，未达到 20% 门槛，因此不能作为最终稳定候选。
- `entry_close_above_signal` 更宽一些，保留了足够交易数，同时通过 70/30 和 walk-forward，当前更适合进入 simulation planner 的 review-only 权重候选。
- 这不是生产规则，也不是实盘依据；它只说明“在当前本地缓存样本上，短持有期 + 重新站上信号价”的模拟候选值得下一阶段重点跟踪。

下一步：

- 把 `selected_stable_candidate` 接到前端非交易研究面板和 simulation planner 的 review-only 解释层。
- 用更多历史数据和更多市场阶段重新跑，不让 2025-06 这一段样本决定最终权重。
- 将三维通信、金螳螂、乐凯胶片阶段标签加入同一套 walk-forward 诊断，区分吸筹/试盘/主升/派发。

## 2026-06-13 第七轮 planner 监督接入

本轮把浏览器资料、Dataset1 纪律、Dataset2 形态信号和现有模拟计划器合并成一个更安全的落地路径：

- VectorBT 给出的启发是批量参数实验，不是替换系统；本项目继续用离线网格和 walk-forward 做候选筛选。
- QSTrader / vn.py 给出的启发是事件分层：信号、组合风控、执行约束、审计回读要分开，不把一个强信号直接变成动作。
- Backtrader 滑点资料继续提醒：必须保留滑点、涨跌停、成交额参与率和 partial/rejected 事件；否则收益会被高估。
- Dataset1 继续作为纪律库：买强不买弱、不要买早、禁止越跌越补、大涨后轻仓、确认主升后分批。
- Dataset2 继续作为形态信号库：`SIM_BUY_CANDIDATE` 和 `WAIT_CONFIRMATION` 只能先进入模拟研究和回测验证。

已落地到代码：

- `SimulationPlanner` 现在会读取最新通过双门槛的 `selected_stable_candidate`。
- 读取结果只写入 `reasons` / `risk_notes`，用于说明当前计划有一条非交易时段稳定候选作为 review-only 证据。
- 该证据不会改变 `position_ratio`、`quantity`、`allowed`、风控 gate、生产 `rules.yaml` 或任何下单权限。
- 新增测试确认：当稳定候选存在时，强候选仍按原 10% 模拟仓位计算，不会被候选参数中的 `buy_position_ratio=0.08` 偷偷覆盖。

当前结合后的主策略应描述为：

1. 非交易时段先搜索潜力股并补齐历史日线。
2. Dataset2 生成形态候选，不直接下单。
3. Dataset1 经验过滤买早、追高、派发末端、越跌越补。
4. 70/30 样本外验证和 rolling walk-forward 同时通过后，才生成 `selected_stable_candidate`。
5. simulation planner 读取该候选，只提高解释可信度和人工复核优先级。
6. 真正模拟盘点击仍需额外满足窗口识别、坐标锚点、`SIMULATION_SCREEN_CLICK`、风险 gate 和小额限制。

下一轮重点：

- 把同一套 stable candidate review 显示到前端非交易研究面板。
- 为三维通信、金螳螂、乐凯胶片建立阶段标签，并接入 walk-forward 分层诊断。
- 扩大本地历史样本，避免 run_id 23 的短期样本过拟合。
- 将 planner 的 review note 进一步结构化，方便自动化循环输出 JSONL 监督摘要。

## 2026-06-13 第九轮浏览器与数据集深度融合

本轮用浏览器查阅公开回测/策略工程资料，并重新读取 Dataset1、Dataset2、最新 offhour run 39 和候选 artifact。结论是：当前最优方向不是“继续放宽后直接买”，而是建立一个更清晰的三层监督模型。

### 新增外部学习结论

- VectorBT 强调用 pandas/NumPy/Numba/Rust 做大规模批量策略实验，适合本项目非交易时段做参数网格、walk-forward 和多样本比较；不适合直接替代模拟盘执行层。
- QSTrader 强调信号、组合构建、风控、执行和模拟会计解耦，适合继续约束 `offhour_research -> simulation planner -> sim-cockpit audit` 的分层。
- Backtrader 的滑点资料提醒：成交价格可能不按请求价成交，因此涨跌停阻断、成交额参与率、partial/rejected event 不能移除。
- A 股涨跌停研究提示：涨停或接近涨停可能带来磁吸效应与次日获利了结，不能把涨停标签直接等同于可成交买点。
- Wyckoff 的吸筹/派发框架适合解释三维通信、金螳螂、乐凯胶片这类阶段样本：长期横盘和试盘是候选证据，主升确认后才考虑分布式模拟加仓，派发完成后只能训练/观察。

参考来源：

- https://vectorbt.dev/
- https://github.com/mhallsmoore/qstrader
- https://www.backtrader.com/docu/slippage/slippage/
- https://voxchina.org/show-3-49.html
- https://www.wyckoffanalytics.com/wyckoff-method/

### 本地数据实证

- Dataset2 仍是弱标签知识库：225 条规则中 `SIM_BUY_CANDIDATE` 63 条、`WAIT_CONFIRMATION` 59 条，但缺少真实 `signal_date/stock_code/entry/exit` 标签，不能直接训练为盈利模型。
- 最新 run 39 完成：57 笔 signal backtest 交易，`signal_optimization_gate=passed_for_simulation_review`。
- run 39 的稳定候选为 `entry_delay_days=1`、`horizon_days=3`、`stop_loss_pct=0.06`、`take_profit_pct=0.18`、`buy_position_ratio=0.08`、`wait_position_ratio=0.06`。
- 该候选 walk-forward 46 笔，weighted win rate 76.09%，weighted average return 3.10%，total equal-weight cumulative return 278.46%；验证集 17 笔，胜率 88.24%，平均收益 4.29%。
- `blocked_failed_markup_risk` 仍不能放宽：11 个样本平均收益 -0.58%，累计 -13.82%，胜率 45.45%，应保持 observe-only。

### 融合后的主策略

1. 非交易时段继续扩大候选：低位、强势、首板/放量、流动性足够、不过度接近派发目标区。
2. Dataset2 只负责生成候选形态，不产生交易权限。
3. Dataset1 负责纪律过滤：不要买早、等启稳、小试单、分批加仓、大涨分批卖、弱开减仓。
4. 稳定候选只进入 simulation review：提高人工复核优先级和模拟计划解释置信度，不改变 `allowed`、`quantity`、真实交易权限或 `rules.yaml`。
5. 模拟盘若要点击，仍必须额外满足窗口验证、坐标锚点、`SIMULATION_SCREEN_CLICK`、组合风险 gate 和小额限制。

### 下一步工程动作

- 已将 `model-candidates/latest` 扩展为读取 ignored artifact 的有界摘要，前端可以显示 `strategy_synthesis`、稳定候选参数和外部学习映射。
- 已把 A 股涨跌停研究与 Wyckoff 阶段思想写入候选 artifact 的 `external_framework_lessons`。
- 下一轮应做阶段标签：三维通信=成功主升学习样本，金螳螂=拉升出货后训练样本，乐凯胶片=重点观察样本；随后接入 walk-forward 分层诊断。

## 2026-06-13 第十轮重点股票阶段样本接入

本轮把用户指定的三只重点股票接入 offhour 研究循环，形成 `focus_phase_diagnostics`：

- 三维通信 `SZ002115`：方法验证成功样本，重点学习拉升前吸筹、试盘、启动和大涨大卖纪律。
- 金螳螂 `SZ002081`：用户确认的拉升出货完成样本，重点学习主力大拉升前 1-2 年吸筹、试盘、拉升和派发后的风险。
- 乐凯胶片 `SH600135`：重点关注与执行纪律样本，历史教训包括未及时卖出、越跌越补、买早买高。

实现原则：

- 只读取本地已存 `main_force_phase_replays`，本轮不在研究循环里临时联网抓取，避免拖慢 offhour run。
- 诊断结果进入 `offhour_research_runs.backtest_json.focus_phase_diagnostics`，并写入候选 artifact。
- 前端 V5.7 面板显示 `Focus Phase Samples`，展示样本角色、当前阶段、训练用途和安全边界。
- 所有输出保持 `review_only=true`、`simulation_only=true`、`live_trading_enabled=false`。

run 44 结果：

- `focus_phase_status=stale_replay`。
- 三只股票当前最新已存阶段均为 `post_distribution_watch`。
- 由于阶段回放生成于 2026-06-05 或本地日线缓存已更新，系统标记为 `stale_replay`。
- 当前统一训练用途为 `training_or_observe_only_no_new_entry_priority`，即只能训练/观察，不提高新开仓优先级。

下一步：

- 刷新三只重点股票的阶段回放，让 `stale_replay` 变成 `ready`。
- 刷新后对三只股票做分层诊断：吸筹段、试盘段、主升段、派发段分别与 Dataset2 信号和稳定候选参数对齐。
- 只有当某类阶段样本在 walk-forward 中持续提高胜率和收益，才允许进入 simulation-planner 的 review-only 排序权重；仍不写生产规则、不触发真实交易。

## 2026-06-13 第八轮宽口径研究循环

本轮通过 `automation_loop.py --mode offhour-research-loop --max-cycles 1 --limit 60` 跑了一次受控非交易时段研究循环，仍然保持 review-only / simulation-only。

关键结果：

- run_id：24。
- potential search：partial，外部发现阶段出现 `Remote end closed connection without response`，但本地生命周期候选仍可评分。
- top scored symbols：`SH688507`、`SZ002971`、`SZ300593`、`SH688207`、`SH688010`。
- signal backtest：57 笔闭合交易，胜率 63.16%，平均单笔收益 2.30%，等权累计收益 239.99%。
- 最新 selected stable candidate：
  - `entry_delay_days=1`
  - `horizon_days=3`
  - `stop_loss_pct=0.06`
  - `take_profit_pct=0.18`
  - `confirmation_filter=none`
  - validation：17 笔，胜率 88.24%，平均单笔收益 4.29%，等权累计收益 99.55%。
  - walk-forward：4 折 46 笔，加权胜率 76.09%，加权平均收益 3.10%，总等权累计收益 278.46%，最低折胜率 58.33%，最低折累计收益 16.40%。
- artifact 已写入 ignored `backend/output/model_candidates/`，rule update gate 仍为 blocked，simulation weight gate 和 signal optimization gate 为 passed_for_simulation_review。

解释：

- 这轮是“宽口径模拟候选”，确实比 run_id 23 更宽，样本更多，收益更强。
- 但它没有 Dataset1 稳态确认过滤，容易把一部分早买/追高风险带回来。
- 因此它适合提高人工复核优先级和模拟沙盒关注度，不适合直接替代 `dataset1_stabilized_reclaim`、`entry_close_above_signal` 等稳态过滤。
- 真正进入模拟盘时，仍应让 PortfolioRisk、数据质量、涨跌停成交模型、同花顺模拟窗口验证和小额试单约束先通过。

下一轮建议：

- 同时保留两个候选轨道：`broad_momentum_candidate` 和 `dataset1_stabilized_candidate`。
- 在前端和 planner 中把候选类型显示清楚：宽口径候选负责发现机会，稳态候选负责降低买早风险。
- 对 run_id 24 的失败/亏损交易做归因，重点查看是否来自弱开、派发末端、过早入场或高位放量。
- 若宽口径候选连续多轮保持优势，可以作为模拟排序加权；若稳态候选在更多历史阶段胜率更稳，则用于小额实盘前人工确认模板。

## 2026-06-13 第九轮双轨候选落地

本轮把上一轮的判断落到后端结构里：`signal_optimization` 新增 `stable_candidate_tracks`。

双轨定义：

- `broad_momentum_candidate`：宽口径动量候选，允许 `confirmation_filter=none`。它用于发现机会和提高模拟复核优先级，但不能单独作为放大仓位或点击交易依据。
- `dataset1_stabilized_candidate`：Dataset1 稳态候选，要求 `entry_close_above_signal`、`entry_green_above_signal`、`strong_reclaim` 或 `dataset1_*` 过滤器。它用于降低买早、追高、派发末端误判风险。

工程约束：

- 两条轨道都只输出 review-only / simulation-only 摘要。
- `SimulationPlanner` 会在 `risk_notes` 中同时展示两条轨道状态，避免只看到收益最高的一条。
- 轨道摘要不会改 `position_ratio`、`quantity`、`allowed`、风控 gate 或 `rules.yaml`。
- 如果宽口径通过、稳态未通过，结论应是“可关注、需等确认”，而不是“可直接买”。

下一轮研究重点：

- 对宽口径通过但稳态未通过的交易做失败归因。
- 观察是否可以把稳态候选的交易数提高，同时维持验证收益超过 20%。
- 前端非交易研究面板应分别显示两条轨道，不要混在一个“最佳参数”里。

## 2026-06-13 第十轮双轨实跑结果

通过新结构跑了一轮 `offhour-research-loop --limit 60`，生成 run_id 25。

结果显示两条轨道都通过 review gate：

- `broad_momentum_candidate`
  - 参数：`entry_delay_days=1`、`horizon_days=3`、`stop_loss_pct=0.06`、`take_profit_pct=0.18`、`confirmation_filter=none`。
  - 验证集：17 笔，胜率 88.24%，平均单笔收益 4.29%，等权累计收益 99.55%。
  - walk-forward：4 折 46 笔，加权胜率 76.09%，总等权累计收益 278.46%，最低折胜率 58.33%。
- `dataset1_stabilized_candidate`
  - 参数：`entry_delay_days=1`、`horizon_days=3`、`stop_loss_pct=0.04`、`take_profit_pct=0.18`、`confirmation_filter=entry_close_above_signal`。
  - 验证集：12 笔，胜率 83.33%，平均单笔收益 4.16%，等权累计收益 60.36%，过滤掉 6 条未确认交易。
  - walk-forward：4 折 32 笔，加权胜率 81.25%，总等权累计收益 196.22%，最低折胜率 71.43%，最低折累计收益 25.78%。

解释：

- 宽口径轨道收益更高、样本更多，适合发现机会。
- 稳态轨道在过滤部分交易后仍然保持超过 20% 的验证收益，并且最低折表现更稳，适合作为模拟盘小额试探前的保守确认轨道。
- 当前最好的执行思想不是二选一，而是：宽口径负责提醒我“可能有机会”，稳态轨负责告诉我“是否值得进入模拟试单复核”。
- 这仍然不是生产规则，也不是实盘授权；它只是把我对 Dataset1/2 的学习变成更清楚的监督证据。

## 2026-06-13 第十一轮双轨差异归因

本轮在 `offhour-research-loop --limit 60` 上重新运行，生成 run_id 26，并把宽口径轨道和 Dataset1 稳态轨道之间的交易差异写入 `track_tradeoff_attribution`。

关键结果：

- 宽口径轨道继续通过 review gate：验证集 17 笔，胜率 88.24%，平均单笔收益 4.29%，等权累计收益 99.55%；walk-forward 46 笔，加权胜率 76.09%，总等权累计收益 278.46%。
- Dataset1 稳态轨道继续通过 review gate：验证集 12 笔，胜率 83.33%，平均单笔收益 4.16%，等权累计收益 60.36%；walk-forward 32 笔，加权胜率 81.25%，总等权累计收益 196.22%。
- 宽口径独有交易 17 笔，胜率 58.82%，平均收益 2.06%，累计收益 36.49%；其中包含 SH605358、SH601208、SH688507 等明显盈利样本，也包含 SZ301360、SH688368、SZ301348 等止损样本。
- 稳态轨道没有产生额外独有交易，它主要是过滤宽口径中的一部分未确认样本。
- 40 条共同信号中，稳态轨道相对宽口径的收益差异平均为 +0.16%，说明当前过滤器的主要价值不是创造新机会，而是降低早买/弱确认风险。

当前结论：

- `mixed_tradeoff_requires_review`：不能简单把宽口径替换成稳态，也不能只看宽口径收益高就直接放松交易。
- 最合理的组合方式是 `keep_broad_for_discovery_and_dataset1_for_confirmation`：宽口径负责发现机会和扩大研究覆盖，稳态轨道负责模拟试单前的确认与仓位保守化。
- 模拟盘执行上，宽口径单独命中只能进入观察或 dry-run；只有稳态确认、风控 gate、数据质量和模拟窗口识别全部通过后，才允许小额模拟试单。

下一步学习方向：

- 对宽口径独有盈利样本和止损样本分别做阶段标签：吸筹、试盘、主升、派发、派发后观察。
- 提取 SH605358、SH601208、SH688507 这类宽口径独有盈利样本的共同特征，判断是否存在“稳态过滤过严”的漏检模式。
- 提取 SZ301360、SH688368、SZ301348 这类止损样本的共同特征，增加弱开、高位放量、派发末端、科创/创业板波动过大等风险标签。
- 在 simulation planner 中继续保持 review-only note，不自动改变仓位、数量、allowed 状态或生产规则。

## 2026-06-13 第十二轮宽口径独有样本分层

本轮继续在 run_id 28 上学习 broad-only 样本，把“宽口径多出来的 17 笔交易”拆成阶段标签、机会标签和风险标签，而不是只看平均收益。

关键结果：

- broad-only 17 笔，胜率 58.82%，平均收益 2.06%，累计收益 36.49%。
- 机会交易 7 笔，其中 4 笔属于 `missed_large_winner`，代表稳态过滤可能漏掉了真正的短线主升/跟随机会。
- 硬风险交易 4 笔，主要来自 `signal_stop_loss`、`filtered_loss_sample`、`broad_only_risk`。
- 机会与风险共存 6 笔，说明宽口径不是不能用，而是必须经过二次确认和小额试探。
- 阶段分布：`missed_follow_through` 6 笔，`stabilization_probe` 7 笔，`distribution_or_failed_markup` 4 笔。

典型样本：

- SH605358、SH601208、SH688507、SH603011：被标记为 `missed_large_winner` 或 `missed_follow_through`，说明宽口径能够提前发现部分主升跟随机会。
- SZ301360、SH688368：被标记为 `distribution_or_failed_markup`、`stop_loss_triggered`、`high_volatility_board_risk`，说明创业板/科创板高波动和放量滞涨风险需要更强阻断。

新的监督规则：

- 宽口径命中且属于 `missed_follow_through`：进入重点观察和 dry-run，不直接点击。
- 宽口径命中且同时带 `distribution_or_stall_risk` 或 `high_volatility_board_risk`：只允许小额模拟前复核，不允许自动加仓。
- 出现 `hard_risk_trade_count` 同类特征时：优先降级为观察，除非 Dataset1 稳态轨道也通过。
- 如果某类 missed winner 在更多历史阶段中反复出现，再考虑新增一个“稳态过滤放宽但仓位更小”的候选轨道。

工程落地：

- closed signal trade 已携带 `signal_tags`、`matched_tags`、`risk_level`、`score` 等信号证据。
- `track_tradeoff_attribution` 新增 `broad_only_tag_summary` / `dataset1_only_tag_summary`。
- `SimulationPlanner` 的 risk note 会显示 broad-only 风险交易数、硬风险数、机会交易数、混合机会风险数和 top phases。
- 以上都仍然只是 review-only / simulation-only 证据，不改变真实交易权限、生产规则、风控 gate 或仓位计算。

## 2026-06-13 第十三轮强化观察轨与失败拉升阻断轨

本轮在 run_id 29 上把 broad-only 样本进一步拆成两个监督轨道：

- `broad_only_enhanced_watch`：宽口径强化观察轨，只提高复核优先级，建议小额复核比例为 2%，不改变实际仓位、不直接触发点击。
- `broad_only_failed_markup_block`：失败拉升阻断轨，识别止损、过滤失败、高波动板块、派发/放量滞涨等样本，允许效果只是降级为观察或 dry-run。

实跑结果：

- broad-only 总体：17 笔，胜率 58.82%，平均收益 2.06%，累计收益 36.49%。
- 强化观察轨：6 笔，胜率 100%，平均收益 9.69%，累计收益 73.68%，典型样本包括 SH605358、SH601208、SH688507。
- 失败拉升阻断轨：4 笔，胜率 0%，平均收益 -6.19%，累计收益 -22.55%，典型样本包括 SZ301360、SH688368。
- 混合机会风险样本：1 笔，需要人工阶段复核，不能直接放宽 Dataset1 稳态过滤。

策略解释：

- 宽口径轨道确实能发现 Dataset1 稳态过滤漏掉的主升/跟随机会，但它同时也会放进失败拉升和高波动止损样本。
- 因此不能把宽口径变成交易轨，而应该把它变成“强化观察 + 小额 dry-run + 二次确认”的研究轨。
- 当强化观察轨命中时，下一步只允许提高候选复核优先级；如果后续盘中重新站上信号价、风控通过、窗口验证通过，才允许小额模拟试单。
- 当失败拉升阻断轨命中时，即便宽口径分数高，也应降级为观察或 dry-run，等待 Dataset1 稳态确认。

新增工程证据：

- `broad_only_supervision.enhanced_watch_track` 保存强化观察样本、收益摘要、要求确认项和建议复核仓位。
- `broad_only_supervision.failed_markup_block` 保存阻断样本、阻断标签和允许效果。
- `SimulationPlanner` 的 risk note 会显示 `enhanced_watch` 和 `failed_markup_block` 状态，但不会修改 `allowed`、`quantity`、`position_ratio` 或风控 gate。

下一步：

- 把 `broad_only_enhanced_watch` 的样本特征做成更严格的二次确认：优先要求重新站上信号价、不能弱开、不能出现硬风险标签。
- 把 `failed_markup_block` 中的 SZ301360 / SH688368 类样本接入更强的模拟盘阻断解释，尤其是高波动板块和派发/失败拉升。
- 前端非交易研究面板应单独展示强化观察轨和阻断轨，让复核时一眼看到“机会在哪里、风险在哪里”。

## 2026-06-13 第十四轮二次确认与近信号价回踩观察

本轮把强化观察轨继续收紧，新增二次确认：

- `reclaimed_signal_price`：入场日收盘重新站上信号价。
- `no_weak_open`：不能明显弱开，且入场日不能弱收。
- `no_hard_risk_tags`：不能带止损、过滤失败、硬风险标签。
- `no_failed_markup_phase`：不能属于失败拉升/派发末端。

实跑 run_id 31 后发现：

- 原始 broad-only 机会样本 6 笔。
- 严格二次确认通过 0 笔，因为 6 笔都没有在入场日收盘重新站上信号价。
- 这不是坏事，说明“重新站上信号价才能 dry-run”足够保守，可以防止宽口径直接变成交易冲动。
- 但其中 5 笔满足 `near_reclaim_watch`：入场日收盘距离信号价不远、没有深度弱开、没有硬风险、不是失败拉升。
- near-reclaim 观察队列 5 笔，历史胜率 100%，平均收益 9.33%，累计收益 55.77%；典型样本包括 SH605358、SH688507、SH603011。

新的执行分层：

- 严格重新站上信号价：才允许进入 dry-run 复核候选。
- 近信号价回踩但未重新站上：只进入 `watch_for_reclaim`，等待后续盘中或日线重新站上，不 dry-run。
- 失败拉升/硬风险：继续进入阻断轨，降级为观察或 dry-run-only 解释，不允许试单。

策略含义：

- Dataset1 的“别买早、等启稳后买”不能只理解成多等几天，也可以理解成：宽口径先发现主力试盘或跟随机会，但必须等价格重新站上关键成本/信号价。
- near-reclaim 样本说明，有些主升机会会先回踩信号价附近再继续拉升；这类不该被丢弃，但也不能急着买。
- 下一步应把 near-reclaim 队列接到交易时段监控：只要后续重新站上信号价且无新硬风险，再进入小额模拟 dry-run 复核。

安全边界：

- `near_reclaim_watch_track` 只能等待确认，不触发 dry-run 或点击。
- `enhanced_watch_track` 即使通过，也只允许提高复核优先级和 dry-run，不修改仓位、不自动下单。
- 所有输出继续保持 review-only / simulation-only / live_trading_enabled=false。

## 2026-06-13 第十五轮浏览器学习与 reclaim watchlist 落地

本轮通过浏览器补充了三类外部参考，并和 Dataset1/Dataset2 的本地样本结论合并：

- 上交所交易机制说明强调 A 股买入单位、涨跌停、价格优先和时间优先等制度约束。因此研究信号不能跳过成交模型、最小 100 股单位、涨跌停阻断和流动性限制。
- VectorBT 的批量参数实验思路说明：策略不是凭单次收益判断，而要批量扫参数、按时间切分、比较不同市场阶段的稳定性。对应到本项目，就是继续保留 `signal_optimization` 和 walk-forward gate。
- QSTrader 的事件/组合/风控分层说明：信号生成、组合构建、执行和会计应当分离。对应到本项目，就是 `offhour_research -> simulation planner -> sim cockpit audit` 不能合并成一个直接点击脚本。
- 近期关于中国市场动量/反转的研究提示：A 股价格动量容易被新闻日、情绪买盘和非新闻日修正扰动。对应到本地结论，就是不能把 broad momentum 直接作为追涨买点，而要等待回踩、重新站回信号价和风险标签清除。

本轮工程落地：

- `OffhourResearchLoopService` 新增 `reclaim_watchlist`。
- `reclaim_watchlist` 从 Dataset2 replay 信号和 `daily_bar_cache` 最新可用 K 线中识别：
  - `near_reclaim_watch`：价格回踩到信号价附近，但尚未重新站回，只允许观察。
  - `reclaim_review`：已经重新站回信号价且没有弱开/弱收和硬风险标签，只允许人工复核或 dry-run 证据。
  - `blocked_failed_markup_risk`：出现放量滞涨、大阴、派发或失败拉升风险，只能观察。
- watchlist 写入 run 结果、latest run、scorecard artifact 和 strategy synthesis。
- `next_action` 会在出现 near-reclaim 或 reclaim-review 候选时给出明确监督建议。

当前策略组合结论：

- broad momentum 负责扩大机会发现，尤其捕捉 Dataset1 稳态过滤可能漏掉的主升/跟随样本。
- Dataset1 稳态过滤负责降低买早、追高、弱确认和派发末端风险。
- near-reclaim 不是交易触发器，而是介于 broad opportunity 和 stabilized confirmation 之间的观察层。
- 只有重新站回信号价、风险 gate 通过、数据质量通过、模拟窗口 gate 通过时，才可能进入小额模拟 dry-run 或模拟盘训练。

安全边界：

- 本轮没有修改 `rules.yaml`、没有写模型 artifact、没有修改实盘权限。
- `reclaim_watchlist` 只输出 review-only / simulation-only 证据。
- `allowed_effect` 明确区分 `watch_for_reclaim_only_not_dry_run` 与 `raise_review_priority_and_dry_run_only`。

### 直接验证结果

使用当前源码直接运行 `OffhourResearchLoopService().run(limit=60, strategy_limit=60)` 生成 run_id 35：

- `live_trading_enabled=false`。
- Dataset2 replay 输出 60 条主信号，并保留 120 条最近信号供 watchlist 使用。
- `reclaim_watchlist.counts` 为：`pending_future_data=16`，`blocked_failed_markup_risk=4`。
- `active_watch_count=0`，说明周末没有足够的新 K 线把 2026-06-12 的信号分成 near-reclaim 或 reclaim-review。
- `next_action` 已改为：等待下一交易日 ready bar 后再重新分类 near-reclaim、reclaim-review 或 failed-markup risk。

监督结论：

- 当前不应为了“尽快模拟交易”而强行放松到买入。
- 周一或下一交易日收盘/实时事件更新后，重新运行 offhour/realtime 研究循环；若出现 `reclaim_review`，仍只进入风险 gate + dry-run 证据，不直接点击。

## 2026-06-13 第十六轮交易时段计划接入 reclaim watch

本轮把 `reclaim_watchlist` 从非交易研究结果接入 `SimulationPlanner` 的监督备注。

工程变化：

- `SimulationPlanner` 新增 `Dataset2 reclaim watch context` 备注。
- planner 会读取最新 `offhour_research_runs.backtest_json.dataset2_reclaim_watchlist`，按 symbol 匹配当前计划对象。
- 支持状态：
  - `pending_future_data`：等待下一根 ready bar，不能从旧信号推断确认。
  - `near_reclaim_watch`：接近信号价，只观察，等站回。
  - `reclaim_review`：可进入人工复核或 dry-run 证据，但仍需要 fresh quote、portfolio gate 和 sim-cockpit gate。
  - `blocked_failed_markup_risk`：失败拉升/派发风险，保持 observe-only。
  - `stale_historical_signal`：只做历史研究，要求新的 Dataset2 信号。

重要边界：

- 本轮不改变 `action`、`allowed`、`quantity`、`position_ratio`、风控 gate 或生产规则。
- reclaim watch 只是把 Dataset1/Dataset2 学习到的“等待确认”逻辑显式写进计划证据。

API 验证：

- 后端已用项目根 `trading_local.sqlite3` 重启，`/health.live_trading_enabled=false`。
- 最新研究 run 仍为 run_id 35，`reclaim_watchlist.counts={pending_future_data:16, blocked_failed_markup_risk:4}`。
- 用 API 创建 SH688507 的模拟计划，risk notes 已包含：
  - `status=pending_future_data`
  - `signal_date=2026-06-12`
  - `allowed_effect=observe_only`
  - `waiting for the next ready bar`
- 计划结果保持 `action=observe`、`allowed=false`、`quantity=0`，没有因为研究信号而放开交易动作。

## 2026-06-13 第十七轮 reclaim transition study

本轮把“等待下一根 K 线确认”从观察名单进一步推进成可复盘的转移研究。

外部学习合并：
- 上交所交易机制提醒：A 股买入有最小交易单位、价格申报、涨跌停等约束，研究信号不能绕过成交模型和风控。
- VectorBT 的启发是批量信号与参数实验，重点不是追求单次最优，而是把参数、止损止盈、确认条件放进网格和样本外验证。
- QSTrader / 事件驱动回测的启发是分层：信号、风险、执行、审计不能合并成一个自动点击脚本。
- A 股动量/反转研究提醒：A 股里“纯动量追涨”不稳定，动量和反转会交织；因此应关注回踩、重新站回信号价、风险标签清除，而不是一看到强势就买。

工程落地：
- `OffhourResearchLoopService` 新增 `reclaim_transition_study`。
- 分类只看信号后的第一根 ready K 线，避免未来函数。
- 后续收益按 3/5/10 根 K 线计算，主视角为 5 日。
- 输出按状态聚合：`reclaim_review`、`near_reclaim_watch`、`blocked_failed_markup_risk` 等。
- 结果写入 run、latest run、model candidate artifact 和 strategy synthesis。
- 前端 V5.7 非交易时段研究面板新增 Reclaim Transition 展示：样本数、胜率、平均收益和监督建议。

当前策略含义：
- 可以适当放宽“观察宽度”，让 near-reclaim 进入观察名单，避免错过回踩后继续主升的样本。
- 但 near-reclaim 仍不是买入触发，只能等待重新站回信号价。
- reclaim-review 可以提高小额 dry-run 复核优先级，但仍需数据质量、组合风控、模拟窗口识别和小额限制。
- blocked failed-markup risk 继续保持 observe-only，尤其是放量滞涨、大阴、派发、失败拉升样本。

验证：
- `pytest backend/tests/test_offhour_research.py -q`：13 passed。
- `pytest backend/tests/test_data_quality_gates.py -q`：5 passed。
- `compileall backend/app/research/offhour.py`：通过。

安全边界：
- 本轮没有修改 `rules.yaml`，没有写生产模型，没有放开实盘。
- 所有新增输出继续保持 review-only / simulation-only / live_trading_enabled=false。

## 2026-06-13 第十八轮研究循环提速与风险标签归因

本轮继续优化非交易时段研究循环，并把 reclaim transition 的结果拆到风险标签层。

性能优化：
- 原先 `signal_optimization` 主要慢在每组参数反复查询 SQLite 日线。
- 已增加本轮内 symbol 日线序列缓存，`signal_optimization` 从约 40-46 秒降到约 2 秒。
- `BacktestEngine` 的完整 rule-engine 回测仍然较重，且当前在 offhour 候选上经常 0 笔交易。
- 默认 balanced 模式改为只做 10 只股票的 rule-engine sanity check，且不持久化 historical backtest 明细；需要周末深搜时使用 `OFFHOUR_RESEARCH_DEEP_BACKTEST=1` 恢复 20 只和持久化明细。
- 最新 balanced run_id 39 用时约 38.85 秒，仍保持 `live_trading_enabled=false`。

策略学习结果：
- `reclaim_review`：71 个样本，5 日胜率约 63.38%，平均收益约 4.02%，可以提高小额 dry-run 复核优先级。
- `near_reclaim_watch`：15 个样本，5 日胜率约 73.33%，平均收益约 3.83%，支持放宽观察宽度，但仍不允许直接买入。
- `blocked_failed_markup_risk`：继续 observe-only，不允许因为个别样本后续上涨而解除硬风险阻断。

新增风险标签归因：
- `reclaim_review:top_risk` 有 52 个样本，胜率约 65.38%，平均收益约 2.21%，但最差样本约 -30.42%，因此不能从“站回信号价”直接推导出加仓。
- `near_reclaim_watch:top_risk` 有 12 个样本，平均收益约 3.07%，但最差约 -8.95%，仍需等待重新站回信号价和风险 gate。
- `blocked_failed_markup_risk:reduce` 与 `blocked_failed_markup_risk:volume_up_price_stall` 继续归为 hard-risk observe-only。

当前调控原则：
- 放宽的是观察宽度，不是交易权限。
- `near_reclaim_watch` 仓位仍为 0，只负责盯盘。
- `reclaim_review` 最多进入小额 dry-run 优先级，建议初始模拟复核比例仍限制在 2% 左右。
- 带 `top_risk/down_phase` 的 reclaim 样本必须降级处理，至少需要额外的风险清除和组合风控通过。
- 所有输出仍不写 `rules.yaml`，不写生产模型，不改变同花顺模拟点击 gate，更不触碰真实交易。

## 2026-06-13 第十九轮交易时段 planner 接入风险标签归因

本轮把上一轮的 `risk_tag_attribution` 接入 `SimulationPlanner` 的 `risk_notes`。

落地方式：
- planner 读取最新 `offhour_research_runs.backtest_json.dataset2_reclaim_watchlist`。
- 同时读取同一 run 的 `dataset2_reclaim_transition_study.risk_tag_attribution.by_status_tag`。
- 如果当前 symbol 的 reclaim watch item 带有风险标签，就匹配 `status:risk_tag`，例如 `reclaim_review:top_risk` 或 `blocked_failed_markup_risk:top_risk`。
- 匹配结果只追加到 `risk_notes`，不会修改 `action`、`allowed`、`quantity`、`position_ratio`、风控 gate 或生产规则。

实测样本：
- 使用最新 run_id 39 中的 SH688783：
  - watch status：`blocked_failed_markup_risk`
  - risk tags：`big_yin, top_risk`
  - planner 输出：`action=observe`、`allowed=false`、`quantity=0`、`position_ratio=0`
  - risk note 增加：`blocked_failed_markup_risk:top_risk`，treatment=`observe_only_hard_risk`

策略意义：
- 交易时段不再只看“是否站回信号价”，还要看这个状态下的风险标签历史表现。
- `reclaim_review` 可以提高复核优先级，但如果带 `top_risk/down_phase`，必须降级为最小 dry-run 或观察。
- `blocked_failed_markup_risk` 即使历史中有个别后续上涨，也继续保持 hard-risk observe-only。
- 这一步让“放宽观察宽度”和“控制仓位”更细：宽的是候选观察面，紧的是风险标签和仓位执行。

## 2026-06-13 第十九轮浏览器学习与阶段相似收益分层

本轮用浏览器复核了外部量化框架与 A 股涨跌停研究，再和本地 Dataset1 / Dataset2 / 阶段样本合并：

- VectorBT 的启发：策略学习要批量比较参数、股票和时间段，不能靠单次高收益。工程上继续保留 `signal_optimization`、walk-forward 和样本外验证。
- QSTrader 的启发：信号、组合构建、执行、会计和风险报告要分层。工程上继续保持 `offhour_research -> simulation planner -> sim-cockpit audit` 分离，不能合并成直接点击脚本。
- Backtrader 滑点模型的启发：回测成交价可能无法匹配真实成交，涨停、跌停、流动性不足和滑点必须单独建模。
- A 股涨跌停研究的启发：接近涨停会有磁吸和次日反转风险，不能把强势冲板直接解释成可追高买点。

本轮新增工程落地：

- `OffhourResearchLoopService` 新增 `phase_similarity_performance`。
- 该指标只读取已有 `main_force_phase_matches` 和 sandbox outcomes，不抓取外部历史，不修改 `rules.yaml`。
- 按“目标股票当前阶段 + 最相似核心样本”分组，比较胜率、平均收盘收益、最大/最小收益。
- 三维通信相似且处于 `markup`、历史 sandbox 表现为正时，只能输出 `raise_review_priority_dry_run_only`。
- 金螳螂相似且处于 `distribution` / `post_distribution_watch` 时，输出 `observe_only_distribution_risk`，短期不作为新高/加仓训练方向。
- 前端 V5.7 非交易时段研究面板新增 Phase Similarity 卡片，显示 matched/evaluated/missing 和各组处理建议。

当前策略合并结论：

- Dataset2 负责发现量价机会，Dataset1 负责纪律过滤，阶段相似负责判断“更像三维通信主升前路径，还是更像金螳螂拉升出货后路径”。
- 阶段相似只能改变复核优先级和观察标签，不能改变 `allowed`、`quantity`、仓位、风险 gate 或真实交易权限。
- 对于相似三维通信且收益验证较好的组，可以进入重点观察和小额 dry-run 复核。
- 对于相似金螳螂出货完成的组，即使短线还有波动，也应优先降级为观察/训练样本，避免把派发后回抽误当成新主升。

安全边界：

- 本轮没有写生产模型，没有修改生产规则，没有放开真实交易。
- 所有输出继续保持 review-only / simulation-only / live_trading_enabled=false。

## 2026-06-13 第二十轮阶段相似覆盖补齐与 planner 接入

本轮把阶段相似从“研究面板证据”推进到“交易时段 planner 可读的风险说明”，但仍然只作为 review-only 证据层。

覆盖补齐：
- 最新 run_id 45 中有 20 只候选缺少阶段匹配，本轮逐只补齐 `main_force_phase_matches`。
- 新增匹配覆盖了 `SH600500`、`SH601208`、`SH603011`、`SH605358`、`SZ301360` 等样本。
- 重新运行非交易时段研究后生成 run_id 46：`evaluated_count=50`、`matched_count=50`、`missing_match_count=0`。

收益分层：
- `SZ002115:post_distribution_watch`：20 个样本，胜率 100%，平均收益约 3.08%，但处理建议仍是 `downgrade_to_smallest_dry_run_or_observe`，因为它属于出货后观察路径。
- `SZ002081:post_distribution_watch`：12 个样本，胜率约 66.67%，平均收益约 1.78%，处理建议为 `observe_only_distribution_risk`。
- `SZ002081:markup`：8 个样本，胜率 75%，平均收益约 3.52%，处理建议为 `review_momentum_but_require_distribution_check`。
- `SZ002115:markup`：6 个样本，胜率 100%，平均收益约 5.10%，处理建议为 `raise_review_priority_dry_run_only`。

Planner 接入：
- `SimulationPlanner` 会读取最新 `phase_similarity_performance`，把当前 symbol 的阶段相似、核心样本、胜率、平均收益和处理建议追加到 `risk_notes`。
- 对金螳螂式出货后路径，planner 会提示降级为观察或最小 dry-run。
- 对三维通信式主升相似路径，planner 只允许提高复核优先级或 dry-run 优先级。
- 实测 `SH600863`、`SZ301360`、`SH601208` 均保持 `action=observe`、`allowed=false`、`quantity=0`，只新增阶段相似解释。

当前监督结论：
- 阶段相似现在能帮助我区分“主升跟随机会”和“出货后回抽风险”，这比单纯看涨幅更接近你的原始交易经验。
- 但它仍然不能替代 Dataset1 稳态确认、Dataset2 信号、组合风控、成交模型和模拟窗口 gate。
- 当前最合理的执行逻辑是：放宽观察池，收紧点击权限；提高优质相似样本的复核优先级，但不自动放大仓位。
- 所有新增判断继续保持 review-only / simulation-only，不改 `rules.yaml`、不写生产模型、不放开真实交易。

## 2026-06-13 第二十一轮阶段相似信心校准

本轮把“阶段相似收益分层”继续推进成“信心校准层”。目的不是增加交易权限，而是让系统知道：哪些历史相似证据只适合训练，哪些可以提高小额 dry-run 复核优先级，哪些即使胜率高也必须因为阶段风险而降级。

新增工程落地：
- `phase_similarity_performance.by_group` 新增 `confidence_tier`、`confidence_score`、`confidence_reasons`、`downside_risk_note`。
- confidence 评分同时考虑样本数、胜率、平均收益、平均盘中下行、最高相似分和阶段处理建议。
- 出货/出货后路径会被 confidence cap 限制，避免“历史样本短线也涨过”被误读成可以买入或加仓。
- `SimulationPlanner` 的 phase note 会显示 confidence tier、score、avg min return 和下行风险说明，但仍不改变 `action`、`allowed`、`quantity`、`position_ratio` 或风控 gate。
- 前端 Phase Similarity 卡片展示 confidence tier、score、avg min，便于人工复核时直接看出信心与风险边界。

run_id 47 结果：
- 阶段匹配继续保持 `evaluated=50`、`matched=50`、`missing=0`。
- `SZ002115:markup`：6 个样本，胜率 100%，平均收益约 5.10%，平均最小收益约 -0.83%，`confidence_tier=high_review_confidence_dry_run_only`，只代表可以提高 dry-run 复核优先级。
- `SZ002081:markup`：8 个样本，胜率 75%，平均收益约 3.52%，`confidence_tier=medium_review_confidence_dry_run_only`，仍需要派发风险检查。
- `SZ002115:post_distribution_watch`：20 个样本，胜率 100%，平均收益约 3.08%，但因属于出货后观察路径，`confidence_tier=late_cycle_low_confidence_observe_or_smallest_dry_run`。
- `SZ002081:post_distribution_watch`：12 个样本，胜率约 66.67%，`confidence_tier=observe_only_distribution_risk_confidence`，继续作为出货风险训练/观察证据。

运行态验证：
- `SH601208` 命中 `SZ002115:markup`，planner note 给出 high review confidence，但计划仍保持 `action=observe`、`allowed=false`、`quantity=0`。
- `SZ301360` 命中 `SZ002081:post_distribution_watch`，planner note 明确出货风险信心，继续 observe-only。
- `SH600863` 命中 `SZ002115:post_distribution_watch`，即使历史分组胜率高，也因晚周期路径降级为 observe 或最小 dry-run。

当前监督结论：
- 这一步提升的是“判断力和信心的可解释性”，不是交易权限。
- 真正接近模拟盘点击之前，还必须叠加：最新交易日确认、Dataset1 稳态过滤、Dataset2 信号、组合风控、成交模型、同花顺模拟窗口识别、`SIMULATION_SCREEN_CLICK` 和小额仓位限制。
- 下一轮学习应把 high/medium confidence 的样本继续做滚动 walk-forward，并检查它们在不同市场状态和板块波动下是否还能保持超过 20% 的组合级累计收益。

## 2026-06-13 第二十二轮高/中信心阶段组滚动验证

本轮把上一轮的 `confidence_tier` 继续向“可验证信心”推进：只挑 `high_review_confidence_dry_run_only` 和 `medium_review_confidence_dry_run_only` 的阶段相似组，按信号时间切成 rolling folds，检查它们是否稳定超过 20% 累计收益门槛。

新增工程落地：
- 新增 `phase_confidence_walk_forward`，只读取 `phase_similarity_performance` 已有结果，不抓取外部数据，不写规则，不改模型。
- 验证门槛包括：样本数、折数、每折样本数、加权胜率、最差折胜率、累计收益超过 20%、最差折收益不能低于 -8%、平均收益必须为正。
- 输出进入 run、artifact、latest API、strategy synthesis 和前端非交易时段研究面板。
- 所有输出继续标记 `review_only=true`、`simulation_only=true`、`writes_rules_yaml=false`、`auto_apply=false`。

run_id 48 结果：
- `phase_confidence_walk_forward.status=passed_for_review`。
- `SZ002115:markup`：`high_review_confidence_dry_run_only`，6 个样本，3 折，加权胜率约 83.33%，折叠累计收益约 34.30%，最差折收益约 6.41%，通过 review gate。
- `SZ002081:markup`：`medium_review_confidence_dry_run_only`，8 个样本，4 折，加权胜率约 62.50%，折叠累计收益约 31.02%，最差折收益约 1.03%，通过 review gate。

策略含义：
- 这是目前最接近“收益率 20% 以上”目标的一层证据，因为它不仅看总体收益，也要求时间折稳定。
- 但样本数仍然偏小，尤其 `SZ002115:markup` 只有 6 个样本，所以当前结论只能提高“人工复核/小额 dry-run 优先级”，不能直接提高自动点击权限或仓位。
- 高/中信心组下一步应进入更大样本、更多市场状态、更多板块波动的滚动验证；只有连续多轮仍超过 20%，才考虑进入模拟盘小额测试 gate。

执行边界：
- 通过 `phase_confidence_walk_forward` 不等于买入信号。
- 模拟盘测试仍需：最新交易日信号、Dataset1 稳态确认、组合风控、成交模型、同花顺模拟窗口识别、`SIMULATION_SCREEN_CLICK`、小额仓位和动作审计全部通过。

## 2026-06-13 第二十三轮阶段信心鲁棒性分层

本轮继续追问一个更严格的问题：high/medium confidence 组虽然通过了 20% rolling gate，但它们是不是只在某些板块或某一种市场环境里有效？

新增工程落地：
- `phase_confidence_walk_forward.groups[].robustness` 新增 `phase_confidence_robustness.v1`。
- 按板块分层：`main`、`star`、`chinext`、`bse`、`st`。
- 按基准环境分层：读取 `daily_bar_cache` 中 `SH000300` / `SH000001` 的信号日前近 5-6 根 ready bar，分为 `benchmark_up`、`benchmark_neutral`、`benchmark_down` 或 `insufficient_benchmark_data`。
- 输出 `by_board`、`by_market_regime`、`market_context_examples` 和 warnings。
- warnings 不会改变交易权限，只会提醒“样本集中、市场覆盖不足、需要更多验证”。

run_id 49 结果：
- `phase_confidence_walk_forward.status=passed_for_review`，两个 high/medium 组仍通过收益 gate。
- `robust_group_count=0`，说明收益证据已经过 20%，但鲁棒性证据还不够。
- `SZ002115:markup`：累计收益约 34.30%，但 robustness 为 `needs_more_context`；板块上 `star` 和 `chinext` 表现强，`main` 只有 2 个样本且胜率 50%。
- `SZ002081:markup`：累计收益约 31.02%，但 robustness 为 `needs_more_context`；主板 5 个样本累计收益约 27.31%，科创板 3 个样本累计收益约 2.91%。
- 两组市场环境均为 `insufficient_benchmark_data`，说明需要补齐基准指数历史缓存，才能判断策略是否只在强势市场里有效。

当前判断：
- 20% 收益门槛已经在高/中阶段信心组上出现了，但鲁棒性还不足以支持扩大模拟盘仓位。
- 下一步不是放开权限，而是补齐 `SH000300` / `SH000001` 基准数据，并把 high/medium 组按市场环境继续验证。
- 如果补齐基准后，在 `benchmark_up / neutral / down` 至少两个环境里仍通过 20% gate，才可以考虑进入更靠前的模拟盘小额 dry-run 队列。
