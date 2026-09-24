# ZK-trading 长期执行计划

> 状态：开发完成后启用。当前阶段只用于学习、排期和设计对齐，不用于训练、调参、实盘执行或自动交易。
>
> 启用条件：核心软件开发完成、基础测试通过、回测/模拟/风控/审计链路可复现、数据集2完成清洗与版本冻结后，才能进入本计划的训练和调整阶段。

## 0. 总开关

本计划继承 `ZK_trading_V4_to_V9_learning_guide.md` 的原则：先做系统能力，再追求策略收益；先做数据可信、实验可信、指标可信，再谈模型效果。

任何阶段都必须保持：

- 模型输出只作为候选评分、风险提示、解释材料或人审建议。
- 不直接实盘下单，不点击券商软件，不保存券商凭据。
- 新策略、新因子、新模型先进入模拟盘和观察期。
- 风控、审计、回滚优先级高于收益。
- 训练和调参只能在开发完成后启动。

## 1. 启用前准备

目标：把“能训练”之前的地基修平。

交付物：

- 数据集2清洗版：修正 `risk_level` 枚举、字符串化列表、缺失证据摘要、缺失触发/失效条件。
- 严格 schema：能拦截非法枚举、空证据、缺失安全字段。
- 历史行情实例集设计：包含 `signal_date`、`stock_code`、特征快照、未来收益、最大有利/不利波动、回撤、基准收益。
- 数据切分规则：按时间切分 train / validation / test / out-of-sample，禁止随机泄漏。
- 版本冻结包：manifest、sha256、schema、切分说明、数据来源说明。

通过条件：

- 数据校验全部通过。
- 没有未来函数字段。
- 每个训练标签都有可追溯来源。
- 所有输出仍为模拟/解释/人审建议。

## 2. V4.0 底座阶段：数据、特征、实验记录

学习锚点：

- Qlib 的 Data Layer / Data Handler 思路：原始数据、特征、学习处理和推理处理要分层。
- vectorbt 的快速参数扫描思路：只作为研究筛选，不替代 A股真实撮合。

执行任务：

- 建立 `features/`：技术、量价、分时、竞价、板块、资金流特征分层。
- 建立 `research/experiments/`：每次实验必须记录数据版本、特征版本、标签版本、模型版本和指标。
- 建立 `models/registry/`：登记模型用途、输入字段、输出字段、禁用状态和审核状态。
- 建立最小泄漏检查：所有特征必须有 `as_of_timestamp` 和 `lookback_window`。

通过条件：

- 任一候选评分都能追溯到数据版本和特征版本。
- 同一实验可以重跑并得到可解释差异。
- 低质量数据默认暂停，不输出交易建议。

## 3. V6.5 策略库阶段：规则先行，模型后置

目标：先把教学经验和数据集2变成可审查规则库，而不是马上训练模型。

执行任务：

- 把每条 `pattern_id` 映射为只读规则卡片。
- 为每类策略建立黄金测试：T+1、涨跌停、停牌、手续费、滑点、流动性。
- 为 `SIM_BUY_CANDIDATE`、`REDUCE_OR_EXIT`、`WAIT_CONFIRMATION` 建立人工复盘面板。
- 每条策略只输出 `candidate_score`、`risk_warning`、`explanation`、`simulation_plan`。

通过条件：

- 规则触发可解释。
- 规则失效条件明确。
- 模拟盘归因可以统计胜率、盈亏比、回撤、交易次数和换手率。

## 4. V7.0 Alpha 因子阶段

目标：建立小而可信的因子生命周期。

执行任务：

- 先实现 20 个基础因子：动量、反转、波动、量比、换手、均线偏离、板块强弱、资金流等。
- 每个因子必须记录 `factor_name`、`factor_value`、`as_of_date`、`source`、`lookback_window`。
- 输出因子报告：IC、RankIC、分组收益、换手、容量、极端行情表现。
- 对所有因子做横截面标准化和缺失值处理。

通过条件：

- 因子报告能说明有效、无效或暂缓。
- 因子不能直接生成实盘动作。
- 因子进入策略前必须通过样本外观察。

## 5. V7.5 金融机器学习阶段

目标：在数据足够干净之后再训练。

执行任务：

- 设计标签：固定窗口收益、三重障碍标签、风险优先标签、观望/不交易标签。
- 做样本权重和标签唯一性检查，减少重叠事件造成的泄漏。
- 建立 walk-forward 训练框架。
- 输出统一评分：`score`、`confidence`、`horizon_days`、`risk_notes`、`requires_human_review`。

通过条件：

- 训练集、验证集、测试集、样本外集按时间隔离。
- 指标同时报告收益、回撤、胜率、盈亏比、换手、滑点敏感性、容量和极端行情。
- 模型在样本外失效时自动降级为规则/观望。

## 6. V8.0 轻量 MoE 阶段

目标：先做轻量路由，不急着上大型 MoE。

执行任务：

- 建立 Market State Router：趋势市、震荡市、弱市、极端市。
- 建立专家类型：规则专家、因子专家、风险专家、解释专家。
- 专家投票只输出候选评分和风险解释。
- 记录专家分歧，分歧较大时默认等待确认。

通过条件：

- 路由器比单一模型更稳，且不是靠提高风险获得收益。
- 专家分歧可追踪。
- 风险专家拥有否决权。

## 7. V8.5 图数据与时序图阶段

目标：先做图特征，再做图模型。

执行任务：

- 建立行业图、概念图、相关性图、资金流图。
- 先做图特征：邻居收益、板块扩散、相关性风险聚类。
- 再尝试 GNN/RNN/Temporal GNN 候选评分。
- 图快照必须按时间生成，禁止使用未来边和未来权重。

通过条件：

- 图特征能独立解释增益。
- 图模型样本外表现稳定。
- 图模型不直接接交易执行。

## 8. V9.0 研究自动化与受控进化

目标：让系统帮助提出研究和代码修改，但不能绕过人审。

执行任务：

- 自动生成研究报告草稿。
- 自动提出小 patch 候选。
- 自动运行回测、样本外验证和风险检查。
- 进入人工审批队列后才能合并。

通过条件：

- 每个 patch 有数据证据、测试证据、回滚说明。
- 风险升高的修改默认拒绝或要求额外审核。
- 自动化只能生成建议，不能批准自己。

## 9. 周期节奏

每周：

- 清理一个数据质量问题。
- 补一个测试或验证报告。
- 复盘一次模拟盘归因。

每月：

- 冻结一个数据/特征/模型版本。
- 做一次样本外报告。
- 删除或降级无效策略。

每季度：

- 做一次阶段门禁复核。
- 重新评估是否进入下一阶段。
- 更新学习路线和风险清单。

## 10. 停止条件

出现以下任一情况，暂停训练或调参：

- 数据来源不可追溯。
- 发现未来函数或时间泄漏。
- 样本外回撤超过预设阈值。
- 风险类样本不足以支撑模型判断。
- 模型输出试图绕过人审或风控。
- 回测和模拟盘差异无法解释。

## 11. 外部项目与论文资料库

这些资料只作为开发完成后的工程设计参考。当前阶段不安装、不训练、不调参、不回测、不连接券商、不执行交易。具体实现必须服从本项目的 A股规则、回测可信度、模拟盘验证、风控和人审边界。

### 11.1 数据清洗

- [Pandera](https://pandera.readthedocs.io/)：学习 DataFrame schema、字段枚举、类型约束和数据质量单测。落到本项目时，用于数据集2清洗版、行情实例集、因子输入表的本地校验。
- [Great Expectations](https://greatexpectations.io/)：学习可读的数据质量期望、校验报告和数据文档。落到本项目时，用于数据来源审计、缺失率/异常值/枚举值检查和版本冻结报告。
- [OpenBB](https://github.com/OpenBB-finance/OpenBB)：学习多源金融数据入口和 provider 抽象。落到本项目时，只评估数据入口设计和 provider 元数据，不直接依赖其数据作为训练真值。

### 11.2 特征底座

- [Qlib](https://github.com/microsoft/qlib)：学习 AI 量化研究平台的数据层、特征表达、模型训练、回测和分析链路。落到本项目时，重点参考 Alpha158/Alpha360 思路、Data Handler 分层、实验记录和模型注册。
- [Feast](https://github.com/feast-dev/feast)：学习 Feature Store、特征注册、离线/在线一致性和 point-in-time 特征。落到本项目时，只先借鉴特征定义、版本、血缘和训练/推理分层，不急于引入服务化组件。

### 11.3 策略库和回测

- [RQAlpha](https://github.com/ricequant/rqalpha)：学习 A股语境下的回测、模拟、Mod Hook、事前风控、交易税费和模拟撮合结构。落到本项目时，只借鉴扩展机制、规则拆分和风控前置。
- [Hikyuu](https://github.com/fasiondog/hikyuu)：学习系统条件、信号、止盈止损、资金管理、滑点、多因子和组合拆分。落到本项目时，只借鉴策略部件复用思想，不迁移 C++ 核心。
- [Lean](https://github.com/QuantConnect/Lean)：学习事件驱动交易引擎、数据处理、结果处理、调度和回测/实时模块边界。落到本项目时，只借鉴模块拆分和事件流，不接 live broker。
- [NautilusTrader](https://github.com/nautechsystems/nautilus_trader)：学习确定性事件驱动、数据 catalog、回放和 backtest/live parity 思路。落到本项目时，只借鉴事件持久化和可回放设计，不追求低延迟实盘执行。
- [vectorbt](https://github.com/polakowo/vectorbt)：学习快速参数扫描、批量回测和交互式分析。落到本项目时，vectorbt 只做研究筛选，最终必须回到 A股真实撮合验证 T+1、涨跌停、停牌、手续费、滑点和流动性。

### 11.4 Alpha 因子

- [Alphalens Reloaded](https://github.com/stefan-jansen/alphalens-reloaded)：学习预测性 alpha 因子的 IC、RankIC、分组收益、换手和前瞻收益分析。落到本项目时，用于设计因子报告模板和因子准入门槛。
- [Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib)：学习组合风险、资产配置、风险预算和约束优化。落到本项目时，只作为组合风险评估参考，不自动生成真实仓位调整。
- [Qlib](https://github.com/microsoft/qlib)：继续学习 Alpha 因子表达、模型 zoo、组合构建和 benchmark。落到本项目时，因子必须带 `as_of_date`、`source`、`lookback_window`，并通过样本外观察。

### 11.5 金融 ML

- [MLFinPy](https://github.com/baobach/mlfinpy)：学习三重障碍标签、样本权重、并发事件、序列自助采样和金融 ML 防泄漏。落到本项目时，用于训练标签设计和 walk-forward 前的数据准备。
- [FinRL](https://github.com/zhaoranwang/FinRL-Library)：学习金融强化学习环境、agent 训练和研究沙盒。落到本项目时，FinRL 只能作为模拟研究参考，不能让 RL agent 控制实盘。
- [sktime](https://www.sktime.net/)：学习时间序列 forecasting、classification、anomaly detection 的统一接口。落到本项目时，用于基准模型和异常检测，不把一般时序预测直接当交易指令。
- [PyTorch Forecasting](https://pytorch-forecasting.readthedocs.io/)：学习 TFT、DeepAR、N-BEATS 等深度时序模型和可解释变量处理。落到本项目时，必须先通过小样本过拟合检查、样本外验证和概率校准。

### 11.6 轻量 MoE

- [Time-MoE](https://github.com/Time-MoE/Time-MoE)：学习时间序列 foundation model 和稀疏 MoE 的建模思路。落到本项目时，只参考专家路由和多尺度时间模式，不直接部署大模型。
- [Moirai-MoE](https://arxiv.org/abs/2410.10469)：学习面向异质时间序列的稀疏专家分配。落到本项目时，先做市场状态路由和轻量专家投票，不上大型分布式 MoE。
- [Tutel](https://github.com/microsoft/tutel)：学习高性能 MoE 系统的工程边界。落到本项目时，只作为远期参考，不在早期引入分布式训练复杂度。

### 11.7 图时序模型

- [PyTorch Geometric Temporal](https://github.com/benedekrozemberczki/pytorch_geometric_temporal)：学习时序图快照、GConvGRU、动态图信号和图时序数据加载。落到本项目时，用于行业图、概念图、相关性图、资金流图的实验。
- [PyG](https://github.com/pyg-team/pytorch_geometric)：学习节点分类、链接预测、图采样和异构图建模。落到本项目时，先做图特征，不急于复杂 GNN。
- [DGL](https://github.com/dmlc/dgl)：学习图神经网络训练和图数据管线。落到本项目时，用作备选图框架评估，必须保证图边、图权重和图快照不使用未来信息。

### 11.8 受控进化

- [Microsoft RD-Agent](https://github.com/microsoft/RD-Agent)：学习研究自动化、假设生成、代码生成、实验反馈和迭代闭环。落到本项目时，只生成研究建议和待审 patch，不自动合并高风险策略/风控修改。
- [R&D-Agent-Quant](https://arxiv.org/abs/2505.15155)：学习数据中心的因子与模型联合优化、多 agent 研究流程和回测反馈。落到本项目时，只作为 V9.0 受控进化参考，必须保留人工审批、回滚和审计。
- [TradingAgents](https://github.com/TauricResearch/TradingAgents)：学习分析师、研究员、交易员、风控、组合经理等多角色分工。落到本项目时，只借鉴角色分工、辩论和风险审查，不采用自动交易执行。

## 12. 分阶段资料使用清单

| 阶段 | 先读资料 | 本项目落地动作 | 禁止照搬内容 |
|---|---|---|---|
| 数据清洗（开发完成后使用） | Pandera、Great Expectations、OpenBB | 清洗数据集2；修正枚举、缺失证据、字符串化列表；建立数据质量报告和来源审计 | 不把外部 provider 数据直接当训练真值；不跳过人工复核 |
| 特征底座（开发完成后使用） | Qlib、Feast | 建立特征注册、point-in-time 特征、训练/推理数据分层、特征血缘 | 不引入重服务化复杂度；不允许未来函数 |
| 策略库和回测（开发完成后使用） | RQAlpha、Hikyuu、Lean、NautilusTrader、vectorbt | 设计策略部件、事件流、模拟撮合、风控前置、参数筛选和 A股规则黄金测试 | 不接券商；不下单；不把 vectorbt 筛选结果直接当真实回测 |
| Alpha 因子（开发完成后使用） | Alphalens Reloaded、Riskfolio-Lib、Qlib | 建立因子报告、IC/RankIC、分组收益、换手、容量和组合风险评估 | 不把单因子漂亮指标直接变成交易动作 |
| 金融 ML（开发完成后使用） | MLFinPy、FinRL、sktime、PyTorch Forecasting | 建立三重障碍标签、样本权重、walk-forward、概率校准和样本外报告 | 不让 RL 或深度模型控制实盘；不随机切分时间序列 |
| 轻量 MoE（开发完成后使用） | Time-MoE、Moirai-MoE、Tutel | 先做市场状态路由、规则专家、因子专家、风险专家、解释专家投票 | 不上大型分布式 MoE；不把专家投票当实盘指令 |
| 图时序模型（开发完成后使用） | PyTorch Geometric Temporal、PyG、DGL | 建立行业图、概念图、相关性图、资金流图和动态图快照实验 | 不使用未来边/未来权重；不让图模型直接接交易执行 |
| 受控进化（开发完成后使用） | RD-Agent、R&D-Agent-Quant、TradingAgents | 建立研究假设、实验反馈、待审 patch、人工审批和审计队列 | 不自动合并策略/风控修改；不采用自动交易执行 |

## 13. 后续维护规则

- 每季度复查一次外部链接、项目活跃度、许可证、依赖风险和是否仍适合本项目。
- 新论文或项目只能先进入“资料候选”，不能直接变成训练任务或实施任务。
- 资料进入执行前必须补充用途、适用阶段、风险、替代方案、退出条件和人工审核人。
- 任何模型资料都必须映射到候选评分、风险提示、解释材料或人审建议之一，不允许映射到实盘动作。
- 含 live、execution、broker、order、portfolio allocation 的资料，只能借鉴架构、事件、风控、审计和模拟回放，不接券商、不下单、不读取账户、不保存凭据。
- 如果资料建议与本项目风控冲突，默认放弃该资料或降级为只读学习笔记。
