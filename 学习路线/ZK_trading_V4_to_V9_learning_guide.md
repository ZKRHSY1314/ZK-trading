# ZK-trading / A股 AI 交易驾驶舱学习指南

> 版本：2026-05-30  
> 当前项目阶段：V4.0  
> 适用范围：V4.0 之后的本地模型、多模型接入、高时效数据系统；V5.0 人审实盘执行网关；V6.0 风控笼子内的有限自动交易；V6.0 之后的策略库扩展、量化分析、Alpha 因子、MoE、图数据 + RNN / Temporal GNN 机器学习研究。  
> 核心定位：这是一份“学习与借鉴路线图”，不是实盘收益承诺，也不是自动下单方案。

---

## 0. 总原则：先学习系统能力，再追求策略收益

项目已经进入 V4.0，说明基础回测、模拟、经验记忆、代码进化、本地/多模型接入和高时效数据系统已经开始成形。接下来不要把学习重点放在“找一个神奇策略”，而应放在以下能力：

1. **数据可信**：行情、财务、板块、指数、资金流、新闻、盘口、复权、停牌、涨跌停、ST、T+1、手续费和印花税都要可追溯。
2. **实验可信**：所有策略、因子、模型都必须经过 train / validation / test / out-of-sample / walk-forward。
3. **指标可信**：不能只看收益率，必须同时看最大回撤、胜率、盈亏比、期望值、换手率、滑点敏感性、交易次数、容量、基准对比和极端行情表现。
4. **模型克制**：模型输出只能作为候选评分、概率判断、风险提示、解释材料或人审建议，不能直接越过风控变成实盘指令。
5. **风控优先**：任何新策略、新因子、新模型、新路由器都必须先进入模拟盘和观察期，再考虑小资金人审执行。
6. **代码可回滚**：策略、因子、模型和风控修改必须小 patch、可测试、可回滚、有审计日志。
7. **人审不可绕过**：V5.0 / V6.0 也只是允许通过 Trade Execution Gateway 产生“待确认计划”或“风控笼子内的有限自动化”，不是让模型直接控制账户。

---

## 1. 版本阶段与学习主题映射

| 阶段 | 项目状态 / 目标 | 学习重点 | 对应开源项目 | 本项目产出 |
|---|---|---|---|---|
| V4.0 当前 | 本地模型 / 多模型接入 / 高时效数据系统 | 数据管道、模型注册、特征库、候选评分、AI 解释、实验记录 | Qlib、vectorbt、AKQuant、PyTorch Forecasting、sktime | `data/`、`features/`、`models/`、`research/experiments/`、`memory/model_decisions/` |
| V5.0 | 人审实盘执行网关 | 交易意图、风控检查、人工确认、审计日志、执行网关抽象 | Lean、NautilusTrader、vn.py、RQAlpha | `trade_gateway/`、`risk/`、`audit/`、`ui/review_panel/` |
| V6.0 | 风控笼子内有限自动交易 | 一键暂停、熔断、仓位上限、连续亏损冷却、异常回切模拟盘 | NautilusTrader、Lean、vn.py riskmanager、Freqtrade dry-run | `risk_cage/`、`kill_switch/`、`execution_policy/` |
| V6.5 | 策略库扩展 | 趋势、均值回归、轮动、突破、配对、事件驱动、组合策略 | Hikyuu、Backtrader、vectorbt、Freqtrade strategies、TA-Lib | `strategies/`、`tests/strategy_fixtures/` |
| V7.0 | Alpha 因子平台 | Alpha158/360、技术因子、量价因子、基本面因子、情绪因子、IC/RankIC/分组收益 | Qlib、Alphalens、QuantStats、empyrical、TA-Lib、pandas-ta | `factors/`、`factor_store/`、`research/factor_reports/` |
| V7.5 | 金融机器学习 | 标签工程、三重障碍、去泄漏、滚动训练、模型集成、概率校准 | Qlib、MLFinLab/MLFinPy、sktime、PyTorch Forecasting、FinRL | `ml_pipeline/`、`labels/`、`walk_forward/` |
| V8.0 | MoE / 多专家系统 | 市场状态路由、策略专家、因子专家、模型专家、解释专家、负载均衡 | DeepSpeed MoE、Tutel、lucidrains MoE、Qlib model zoo | `moe_router/`、`experts/`、`model_votes/` |
| V8.5 | 图数据 + RNN / Temporal GNN | 股票关系图、行业图、概念图、相关性图、资金流图、动态图预测 | PyTorch Geometric Temporal、PyG、DGL、THGNN、PyTorch Forecasting | `graph/`、`temporal_graph/`、`graph_models/` |
| V9.0 | 研究自动化 / 受控进化 | 自动生成研究报告、自动提出 patch、自动回测、人工审批合并 | AutoQuant 思路、Qlib RD-Agent、Codex skill、项目 memory | `evolution_engine/`、`memory/code_evolution/` |

---

## 2. 开源项目学习总表

| 项目 | 类型 | 学习优先级 | 我们应学什么 | 不建议照搬什么 |
|---|---|---:|---|---|
| RQAlpha | 中国量化回测 / 模拟框架 | 高 | Mod 扩展机制、策略 API、A股回测习惯、多资产框架 | 数据服务依赖、直接实盘模块 |
| Hikyuu | A股适配的 C++/Python 研究框架 | 高 | 市场环境、系统条件、信号、止盈止损、资金管理、滑点、多因子、组合拆分 | 大规模迁移 C++ 核心 |
| Backtrader | Python 回测框架 | 高 | Broker simulation、订单、佣金、滑点、Analyzer、指标和策略结构 | 直接使用旧式 live trading 接口 |
| AKQuant | Rust + Python 量化研究框架 | 高 | Golden tests、T+1、涨跌停、walk-forward、Rust 加速边界 | 当前阶段不必重写 Rust 内核 |
| vectorbt | 向量化回测 / 大规模实验 | 高 | 参数网格、批量回测、交易分析、交互式可视化 | 用向量化结果直接替代真实撮合 |
| Qlib | AI 量化研究平台 | 高 | Alpha158/Alpha360、模型训练、数据集拆分、portfolio construction、benchmark | 复杂生产 pipeline 不宜一次接入 |
| QuantStats | 绩效分析 | 高 | Sharpe、Win rate、Volatility、回撤、HTML tear sheet | 只看漂亮报表不看交易明细 |
| Alphalens / alphalens-reloaded | 因子分析 | 高 | IC、分组收益、因子分层、前瞻收益分析 | 老版依赖可能陈旧，建议封装适配层 |
| empyrical / pyfolio | 风险绩效 | 中高 | alpha/beta、VaR、Sortino、回撤、组合风险 | 旧依赖直接进核心生产 |
| TA-Lib / pandas-ta / ta | 技术指标库 | 中高 | 技术因子快速生成、指标一致性测试 | 把指标堆叠当成 alpha |
| Lean | 专业事件驱动交易引擎 | 中高 | DataFeed、TransactionHandler、ResultHandler、RealtimeHandler、SetupHandler 思路 | 复杂 live 部署和券商接入 |
| NautilusTrader | 高性能事件驱动引擎 | 中高 | research / backtest / live parity、事件持久化、确定性回放 | 当前不追求低延迟生产交易 |
| vn.py / VeighNa | 国内量化交易平台 | 中高 | EventEngine、Gateway、风控模块、UI、交易接口抽象 | 当前阶段不接实盘 gateway |
| Freqtrade | dry-run-first 交易机器人 | 中 | dry-run、安全默认值、策略目录、WebUI、参数优化、SQLite 持久化 | 加密市场逻辑和自动实盘行为 |
| FinRL / FinRL-X | 强化学习交易研究 | 中 | market environment、agent 训练、RL 沙盒、AI-native modular infrastructure | RL 直接控制实盘 |
| Zipline Reloaded | 事件驱动研究框架 | 中 | Pipeline、因子研究、历史数据接口、事件驱动学习 | A股细节需自补 |
| backtesting.py | 极简回测 | 中 | 简洁策略 API、快速验证、教学样例 | 用它承担复杂 A股组合撮合 |
| MLFinLab / MLFinPy | 金融机器学习 | 中 | 三重障碍、标签、样本权重、去泄漏、特征重要性 | 依赖和许可证需单独核查 |
| sktime | 时间序列 ML | 中 | 统一的 forecasting / classification / anomaly detection 接口 | 直接把一般时序模型当交易模型 |
| PyTorch Forecasting | 深度时序预测 | 中 | TFT、N-BEATS、DeepAR、解释性、变量处理 | 大模型过拟合小样本 |
| PyTorch Geometric Temporal | 动态图 / 时序图 | 中高（V8.5） | GConvGRU、动态图快照、股票关系图时序建模 | 未验证前用于真实下单 |
| PyG / DGL | 图神经网络基础设施 | 中 | 节点分类、链路预测、异构图、图采样、扩展训练 | 一开始做过复杂图系统 |
| THGNN | 金融时序异构图论文代码 | 研究型 | 股票异构关系 + 时序预测设计参考 | 代码直接进生产 |
| DeepSpeed MoE / Tutel / lucidrains MoE | MoE 基础设施 | 研究型 | 稀疏专家、路由、负载均衡、专家容量 | 在本项目早期上分布式 MoE 大模型 |

---

## 3. V4.0 当前：数据、模型、特征与实验底座

### 3.1 V4.0 的核心问题

V4.0 不应只理解为“接入本地模型”，而应理解为：

- 能稳定拿到多源数据；
- 能把数据转为可追溯特征；
- 能把特征送给规则、模型、AI 解释层；
- 能记录每次模型输入、输出、版本、时间戳、置信度；
- 能区分研究结果、模拟结果、人审建议和真实执行结果。

### 3.2 V4.0 重点学习项目

#### Qlib

学习目标：

- 数据集组织方式；
- Alpha158 / Alpha360 因子表达；
- 模型训练与回测 pipeline；
- benchmark 与 portfolio construction；
- 研究结果如何落成可复现实验。

对应本项目模块：

```text
features/
  alpha158_like/
  alpha360_like/
  technical/
  fundamental/
research/
  qlib_style_experiments/
models/
  registry/
  checkpoints/
  inference_logs/
```

建议任务：

```text
请参考 Qlib 的 Alpha158 / Alpha360 思路，设计 ZK-trading 的第一版 A股因子表达层。
要求：
1. 每个因子必须带 timestamp，不允许未来数据；
2. 每个因子必须能追溯原始行情 / 财务 / 板块数据；
3. 输出 factor_name、factor_value、as_of_date、source、lookback_window；
4. 增加单元测试，证明不会读取交易日之后的数据；
5. 不接入实盘下单。
```

#### vectorbt

学习目标：

- 大规模参数扫描；
- 多资产、多周期、多策略实验；
- 交易明细级分析；
- 交互式实验报告。

对应本项目模块：

```text
research/experiments/
research/parameter_sweeps/
reports/vectorized_backtests/
```

注意：vectorbt 的向量化非常适合“研究筛选”，但不能代替 A股真实撮合。最终策略仍要回到你们自己的可信回测引擎，验证 T+1、涨跌停、停牌、手续费、滑点、部分成交和流动性限制。

#### AKQuant

学习目标：

- 用黄金测试验证交易规则；
- 用合成数据测试 T+1、涨跌停、保证金等规则；
- walk-forward validation 的工程化实现；
- Rust + Python 的性能边界。

对应本项目模块：

```text
tests/golden/
tests/fixtures/a_share_rules/
research/walk_forward/
```

建议先学“测试方法”，不要急着迁移 Rust。

---

## 4. V5.0：人审实盘执行网关学习路线

V5.0 的目标不是让系统自动交易，而是让系统能把策略输出变成“待确认交易意图”，经过风控、人审和审计后，再由用户决定是否执行。

### 4.1 学习项目映射

| 项目 | 学什么 | 本项目对应设计 |
|---|---|---|
| Lean | 引擎模块拆分、数据 / 交易 / 结果 / 实时事件处理 | `engine/handlers/` |
| NautilusTrader | 确定性事件驱动、backtest/live 一致性、事件回放 | `event_store/`、`replay/` |
| vn.py | EventEngine、Gateway、风控和 UI 交易界面 | `trade_gateway/`、`risk/`、`ui/review_panel/` |
| RQAlpha | Mod Hook、策略和执行环境解耦 | `plugins/`、`strategy_runtime/` |

### 4.2 Trade Execution Gateway 最小结构

```text
trade_gateway/
  intent.py              # 交易意图：symbol, side, qty, price, reason
  precheck.py            # 风控预检查
  review_ticket.py       # 人审工单
  executor_stub.py       # 默认只读 / 模拟，不真实下单
  audit_logger.py        # 审计日志
  rollback.py            # 异常回切模拟盘
```

### 4.3 必须禁止

- 禁止 Codex 或模型直接点击买入 / 卖出；
- 禁止自动提交委托；
- 禁止保存明文券商账号、密码、token、cookie；
- 禁止策略 patch 自动提高仓位或关闭风控；
- 禁止把模拟盘逻辑一键切到实盘。

---

## 5. V6.0：风控笼子内有限自动化

V6.0 可以学习自动化，但自动化的对象应该是：

- 风控检查自动化；
- 异常检测自动化；
- 模拟盘执行自动化；
- 报告生成自动化；
- 人审工单生成自动化；
- 一键暂停 / 熔断 / 回切模拟盘自动化。

不是让模型自由决定买卖。

### 5.1 V6.0 风控笼子

```text
risk_cage/
  position_limits.yaml
  daily_loss_limit.yaml
  drawdown_limit.yaml
  liquidity_limit.yaml
  concentration_limit.yaml
  cooldown_policy.yaml
  kill_switch.py
  read_only_mode.py
```

### 5.2 学习项目

- **NautilusTrader**：学习事件驱动、研究和交易一致性、确定性回放。
- **Lean**：学习交易引擎组件化。
- **vn.py riskmanager**：学习事前风控规则引擎。
- **Freqtrade**：学习 dry-run-first、安全默认值、WebUI、SQLite 持久化和参数优化流程。

### 5.3 V6.0 通过条件

- 所有策略能在模拟盘连续运行；
- 所有交易意图都能被审计；
- 所有风控拒绝都有原因；
- kill switch 可在任何状态强制进入只读；
- 数据异常时默认暂停；
- 模型低置信度时默认降级为规则策略或观望；
- 人审和实盘配置不能被模型自动修改。

---

## 6. V6.5：更多交易策略学习路线

### 6.1 策略分类

| 策略方向 | 目标 | 适合学习项目 | A股实现要点 | 关键风险 |
|---|---|---|---|---|
| 趋势 / 动量 | 捕捉持续上涨或下跌 | Backtrader、Hikyuu、TA-Lib、vectorbt | 均线、动量、突破、成交量确认 | 震荡市回撤、追高、涨停不可买 |
| 均值回归 | 捕捉短期偏离修复 | Backtrader、vectorbt、Alphalens | z-score、布林带、行业内相对强弱 | 趋势行情中逆势亏损 |
| 行业 / 主题轮动 | 在板块间切换 | Qlib、Hikyuu、QuantStats | 行业指数、概念板块、资金流、相对强度 | 热点衰减快、数据口径不一致 |
| 多因子选股 | 多维打分选股 | Qlib、Alphalens、QuantStats | 因子标准化、中性化、IC、组合构建 | 因子拥挤、过拟合、换手过高 |
| 配对 / 统计套利 | 相关资产价差回归 | vectorbt、Backtrader、MLFinLab | 协整、价差、行业内配对 | A股融券限制、流动性、交易成本 |
| 事件驱动 | 财报、公告、龙虎榜、资金流 | Qlib、FinRL、新闻 NLP 工具 | 事件时间戳、公告滞后、情绪评分 | 信息泄漏、不可交易时点 |
| 风险规避 / 市场状态 | 判断仓位水平 | Hikyuu、Qlib、sktime | 指数趋势、波动率、宽基强弱、成交额 | 错过反弹、过度择时 |
| 组合再平衡 | 控制风险暴露 | QuantStats、empyrical、pyfolio | 行业权重、个股权重、回撤控制 | 换手成本、风控参数不稳 |

### 6.2 策略统一接口建议

```python
class StrategySignal:
    strategy_id: str
    symbol: str
    as_of_date: str
    signal: str          # BUY_CANDIDATE / SELL_CANDIDATE / HOLD / AVOID
    score: float
    confidence: float
    horizon_days: int
    evidence: dict
    risk_notes: list[str]
```

每个策略都只输出候选信号，不直接下单。

### 6.3 每个新策略必须通过的测试

1. 是否有未来函数；
2. 是否违反 T+1；
3. 是否在涨停价假设能买入；
4. 是否在跌停价假设能卖出；
5. 是否考虑停牌；
6. 是否考虑手续费、印花税、滑点；
7. 是否过度依赖少数交易；
8. 是否在不同市场状态下都可解释；
9. 是否比基准更好；
10. 是否增加组合集中度和回撤。

---

## 7. V7.0：量化分析与 Alpha 因子提取

### 7.1 Alpha 因子平台目标

Alpha 因子平台不是“多做几百个指标”，而是要建立一套可检验、可复现、可退役的因子生命周期：

```text
原始数据 → 因子表达 → 时间戳校验 → 横截面标准化 → 中性化 → IC / RankIC → 分组收益 → 回测组合 → 换手与容量 → 退役/上线观察
```

### 7.2 因子分类

| 因子类型 | 示例 | 学习项目 | 验证指标 |
|---|---|---|---|
| 技术量价 | 动量、反转、波动率、成交量、换手率、均线斜率 | TA-Lib、pandas-ta、Qlib | IC、分组收益、换手率 |
| 风格因子 | 市值、估值、成长、质量、盈利能力 | Qlib、Alphalens | 中性化后 IC、行业暴露 |
| 资金流因子 | 主力净流入、北向资金、龙虎榜、融资融券 | Qlib 风格 pipeline | 事件后收益、衰减曲线 |
| 板块因子 | 行业强弱、概念热度、板块扩散度 | Hikyuu、vectorbt | 板块轮动胜率、组合贡献 |
| 情绪因子 | 新闻情绪、公告情绪、社媒热度 | NLP 模型 + Qlib pipeline | 滞后测试、事件时间校验 |
| 微观结构因子 | 价差、盘口不平衡、成交强度 | Nautilus 思路 | 高成本敏感性、容量 |
| 图因子 | 行业/概念/供应链/相关性中心度 | PyG / DGL | 图中心性 IC、邻居传播收益 |

### 7.3 因子文件结构

```text
factors/
  registry.yaml
  technical/
    momentum.py
    reversal.py
    volatility.py
  fundamental/
    valuation.py
    quality.py
  money_flow/
    northbound.py
    main_force.py
  sector/
    sector_strength.py
  sentiment/
    news_sentiment.py
  graph/
    industry_graph_centrality.py
factor_store/
  daily/
  metadata/
research/factor_reports/
```

### 7.4 因子报告模板

```text
# 因子研究报告：factor_name

## 1. 因子定义
- 原始数据来源：
- 计算公式：
- lookback window：
- as_of_date 规则：

## 2. 泄漏检查
- 是否使用未来价格：否
- 是否使用未来财报：否
- 是否使用不可交易时点数据：否

## 3. 因子有效性
- IC 均值：
- RankIC 均值：
- ICIR：
- 分组收益：
- 多空收益：
- 衰减周期：

## 4. 风险与成本
- 换手率：
- 行业暴露：
- 市值暴露：
- 滑点敏感性：
- 容量估计：

## 5. 结论
- 建议：观察 / 加入候选池评分 / 退役
- 不允许直接变成实盘下单规则。
```

### 7.5 推荐先实现的 20 个基础因子

1. 20 日动量；
2. 60 日动量；
3. 5 日反转；
4. 20 日波动率；
5. 20 日成交额均值；
6. 成交额放大倍数；
7. 换手率变化；
8. 价格距离 20 日均线；
9. 价格距离 60 日均线；
10. RSI；
11. MACD histogram；
12. Bollinger band percentile；
13. 行业 20 日相对强度；
14. 个股相对行业强度；
15. 涨停后 N 日行为因子；
16. 跌停回避因子；
17. 停牌恢复观察因子；
18. 北向资金变化因子；
19. 主力资金流变化因子；
20. 新闻情绪变化因子。

---

## 8. V7.5：金融机器学习路线

### 8.1 从传统 ML 到深度时序

| 学习层级 | 模型 / 方法 | 适合问题 | 推荐项目 |
|---|---|---|---|
| Level 1 | Logistic Regression、RandomForest、XGBoost、LightGBM | 候选股二分类、上涨概率、风险过滤 | Qlib、MLFinPy |
| Level 2 | 时间序列分类 / 回归 | 个股短周期走势、波动率、风险状态 | sktime |
| Level 3 | TFT、N-BEATS、DeepAR | 多变量时序预测、解释性特征选择 | PyTorch Forecasting |
| Level 4 | RL agent | 仓位控制、执行策略、组合调仓研究 | FinRL |
| Level 5 | 图时序模型 | 行业/概念/股票关系传播 | PyTorch Geometric Temporal、DGL、THGNN |
| Level 6 | MoE | 多市场状态、多策略、多模型路由 | DeepSpeed、Tutel、轻量自研 Router |

### 8.2 标签工程

建议不要只做“明天涨跌”标签，而要建立多种标签：

```text
labels/
  forward_return_1d
  forward_return_5d
  forward_return_20d
  outperform_index_5d
  drawdown_exceed_3pct_5d
  triple_barrier_label
  hit_take_profit_before_stop_loss
  liquidity_risk_label
```

三重障碍标签适合学习 MLFinLab / MLFinPy，但要注意依赖、许可证和维护状态。即使借鉴，也建议在本项目里实现一个轻量版本，并用单元测试覆盖。

### 8.3 金融 ML 必须做的防泄漏

1. 特征时间戳必须早于标签窗口；
2. 财务数据必须使用公告可见日期，不是报告期日期；
3. 新闻和公告必须使用发布时间，不是事件发生后整理日期；
4. 横截面标准化不能跨未来股票池；
5. 股票停牌 / 退市 / ST 不能被后验剔除；
6. 调参不能看测试集；
7. 使用 walk-forward，而不是一次随机切分；
8. 必要时使用 embargo / purging，避免相邻样本泄漏。

### 8.4 模型输出统一为评分

```python
class ModelScore:
    model_id: str
    model_version: str
    symbol: str
    as_of_date: str
    horizon_days: int
    score: float
    probability: float | None
    uncertainty: float | None
    top_features: list[dict]
    training_window: tuple[str, str]
    validation_metrics: dict
```

模型不能直接输出 `BUY 1000 shares`，只能输出候选评分和解释。

---

## 9. V8.0：MoE / 多专家系统路线

### 9.1 本项目里的 MoE 不一定要从大模型 MoE 开始

MoE 在本项目里可以分四层：

| 层级 | 解释 | 建议实现顺序 |
|---|---|---:|
| 策略 MoE | 趋势专家、反转专家、轮动专家、事件专家、风控专家分别打分 | 1 |
| 因子 MoE | 技术因子专家、基本面专家、资金流专家、情绪专家、图因子专家 | 2 |
| 模型 MoE | XGBoost、TFT、Graph-RNN、RL、LLM 解释模型互相投票 | 3 |
| 深度 MoE | DeepSpeed / Tutel 这类稀疏专家大模型 | 4 |

对 ZK-trading 来说，最先该做的是轻量 MoE：

```text
market_state_detector → router → expert_scores → risk_adjuster → candidate_score
```

### 9.2 Market State Router

先定义市场状态，再决定用哪个专家：

```text
market_state:
  trend_up
  trend_down
  range_bound
  high_volatility
  low_liquidity
  sector_rotation
  event_driven
  panic_mode
```

每个状态对应不同专家权重：

```yaml
trend_up:
  trend_expert: 0.40
  sector_rotation_expert: 0.25
  factor_expert: 0.20
  risk_expert: 0.15

high_volatility:
  risk_expert: 0.45
  reversal_expert: 0.20
  trend_expert: 0.10
  cash_expert: 0.25
```

### 9.3 MoE 目录结构

```text
moe_router/
  market_state.py
  router.py
  calibration.py
  load_balance.py
experts/
  trend_expert.py
  reversal_expert.py
  sector_rotation_expert.py
  factor_expert.py
  sentiment_expert.py
  graph_expert.py
  risk_expert.py
model_votes/
  YYYY-MM-DD.jsonl
```

### 9.4 MoE 验证指标

- Router 准确性：不同市场状态下是否选择了合理专家；
- 专家贡献：每个专家对最终收益和风险的边际贡献；
- 专家退化：某个专家是否长期无效；
- 负载平衡：是否总是只选一个专家；
- 稳定性：不同样本窗口下权重是否剧烈变化；
- 风控优先级：risk_expert 是否能覆盖收益专家；
- 人审解释：每次路由能否用自然语言解释。

### 9.5 MoE 学习顺序

1. 先手写规则 Router；
2. 再用 Logistic Regression / XGBoost 学 Router；
3. 再加入概率校准；
4. 再加入专家退役机制；
5. 再考虑深度 MoE；
6. 最后才学习 DeepSpeed / Tutel 的工程化大模型 MoE。

---

## 10. V8.5：图数据 → RNN / Temporal GNN 机器学习路线

### 10.1 为什么 A股适合图建模

A股不是一堆孤立股票，而是强关系网络：

- 行业关系；
- 概念板块关系；
- 上下游供应链；
- 共同基金持仓；
- 北向资金共同流入；
- 价格相关性；
- 新闻共现；
- 股东 / 实控人关系；
- 龙虎榜席位共现；
- 指数成分股关系。

图模型的目标不是“预测确定涨跌”，而是学习股票之间的风险与机会传播。

### 10.2 图数据类型

| 图类型 | 节点 | 边 | 更新时间 | 用途 |
|---|---|---|---|---|
| 行业图 | 股票 / 行业 | 属于同一行业 | 低频 | 行业中性化、板块轮动 |
| 概念图 | 股票 / 概念 | 属于同一概念 | 中频 | 题材扩散、热点传播 |
| 相关性图 | 股票 | 收益相关 / 残差相关 | 滚动 | 风险聚类、配对候选 |
| 资金流图 | 股票 | 资金共同流入 / 流出 | 日频 | 主线识别 |
| 供应链图 | 公司 | 上下游关系 | 低频 | 产业链传导 |
| 新闻共现图 | 股票 / 实体 | 同一新闻出现 | 高频 | 舆情扩散 |
| 持仓图 | 基金 / 股票 | 持仓关系 | 季频 | 拥挤度、机构偏好 |

### 10.3 Graph + RNN 的三种建模方式

#### 方式一：图特征 → RNN

```text
每日图指标（中心度、社区、邻居收益、邻居资金流）
→ 拼到个股时序特征
→ LSTM / GRU / TFT
→ 输出候选评分
```

优点：工程简单，适合先做。

#### 方式二：GNN → RNN

```text
每日股票图快照
→ GCN / GAT 提取节点 embedding
→ GRU / LSTM 处理时间序列
→ 预测未来收益 / 风险标签
```

适合用 PyG / DGL 自研。

#### 方式三：Temporal GNN

```text
动态图序列
→ GConvGRU / DCRNN / TGN / THGNN
→ 节点未来表现预测
```

适合学习 PyTorch Geometric Temporal、DGL temporal examples 和 THGNN。

### 10.4 图模型目录结构

```text
graph/
  builders/
    industry_graph.py
    concept_graph.py
    correlation_graph.py
    money_flow_graph.py
  snapshots/
    YYYY-MM-DD.parquet
  metadata/
    graph_schema.yaml

graph_models/
  baselines/
    graph_features_to_lgbm.py
  gnn/
    gcn_encoder.py
    gat_encoder.py
  temporal/
    gconvgru_model.py
    dcrnn_model.py
    thgnn_experiment.py
  reports/
```

### 10.5 图模型防泄漏规则

1. 相关性图只能用历史窗口计算，不能包含预测窗口；
2. 概念归属必须使用当日已知概念，不能用未来新概念；
3. 基金持仓只能在披露日之后可见；
4. 新闻共现只能使用发布时间之前的数据；
5. 不能因为未来退市 / ST / 暴雷而提前剔除股票；
6. 图快照必须有 `as_of_date`；
7. 每个边都必须有 `source` 和 `visible_at`。

### 10.6 图模型先做的三个实验

#### 实验 1：行业邻居收益因子

目标：验证“同一行业内强势股票是否带动邻居”。

输出：

```text
factor_name = industry_neighbor_return_5d
```

验证：Alphalens 风格 IC / 分组收益。

#### 实验 2：相关性图风险聚类

目标：当组合持仓股票高度相关时，是否增加回撤风险。

输出：

```text
portfolio_graph_concentration_score
```

验证：高图集中度组合 vs 低图集中度组合的回撤对比。

#### 实验 3：GConvGRU 候选评分

目标：用历史图快照和节点特征预测 5 日相对收益。

输出：

```text
graph_model_score_5d
```

验证：walk-forward + benchmark + 交易成本敏感性。

---

## 11. V9.0：研究自动化与受控代码进化

### 11.1 Evolution Engine 的输入

```text
memory/raw_events/
memory/trade_reviews/
memory/strategy_performance/
memory/model_decisions/
memory/risk_events/
research/experiments/
research/factor_reports/
reports/backtests/
audit/
```

### 11.2 Evolution Engine 的输出

```text
research_proposals/
  YYYY-MM-DD_strategy_ideas.md
  YYYY-MM-DD_factor_ideas.md
  YYYY-MM-DD_model_ideas.md
patch_proposals/
  YYYY-MM-DD_small_patch.md
tests/
  generated_regression_tests/
```

### 11.3 受控进化闭环

1. 收集模拟交易、候选池、回测、风控、模型投票；
2. 生成复盘报告；
3. 区分问题属于数据、策略、风控、执行、UI、指标还是模型；
4. 生成小 patch 草案；
5. 增加测试；
6. 运行回测；
7. 做样本外验证；
8. 对比 benchmark；
9. 检查是否提高风险；
10. 生成变更报告；
11. 等待人工确认；
12. 合并后进入模拟盘观察期。

### 11.4 Codex 默认任务模板

```text
请基于 ZK-trading 当前 V4.0 状态，完成一个受控研究任务。

任务主题：{策略 / 因子 / 模型 / 图数据 / MoE / 风控}

要求：
1. 先阅读 README、docs、tests、相关模块；
2. 不接入实盘下单；
3. 不绕过风控；
4. 不修改实盘配置；
5. 所有模型输出只能是评分、解释或候选建议；
6. 必须检查未来函数和数据泄漏；
7. 必须补充测试；
8. 必须给出 benchmark comparison；
9. 必须说明是否需要写入 memory/；
10. 最后输出：涉及文件、改动摘要、测试结果、风险提示、下一步建议。
```

---

## 12. 12 周学习与落地计划

### 第 1-2 周：V4.0 研究底座加固

- 阅读 Qlib、vectorbt、AKQuant；
- 建立 `research/experiments/`；
- 建立模型输入输出日志；
- 建立特征时间戳测试；
- 做第一个 vectorbt 参数扫描，但最终回到自研回测引擎复核。

交付物：

```text
research/experiments/README.md
features/feature_schema.yaml
tests/test_feature_no_leakage.py
reports/v4_research_stack_gap_analysis.md
```

### 第 3-4 周：Alpha 因子最小平台

- 实现 20 个基础因子；
- 建立 factor registry；
- 引入 Alphalens 风格报告；
- 引入 QuantStats 风格组合报告；
- 做 IC / RankIC / 分组收益 / 换手分析。

交付物：

```text
factors/registry.yaml
factors/technical/*.py
research/factor_reports/first_20_factors.md
tests/test_factor_asof_date.py
```

### 第 5-6 周：策略库扩展

- 实现趋势、反转、行业轮动、多因子、风险规避 5 类策略；
- 统一 StrategySignal 接口；
- 每个策略必须跑成本、滑点、基准、极端行情测试。

交付物：

```text
strategies/trend/
strategies/reversal/
strategies/sector_rotation/
strategies/multifactor/
strategies/risk_off/
reports/strategy_library_v1.md
```

### 第 7-8 周：金融 ML 与 walk-forward

- 实现标签模块；
- 实现 walk-forward runner；
- 先用 LightGBM / XGBoost 做候选评分；
- 暂不引入复杂深度模型；
- 输出模型解释和不确定性。

交付物：

```text
labels/
ml_pipeline/
walk_forward/
reports/ml_candidate_scoring_v1.md
```

### 第 9 周：轻量 MoE Router

- 定义 market_state；
- 定义专家接口；
- 建立策略专家、因子专家、风险专家；
- 用规则 Router，不急着用 DeepSpeed；
- 每次路由写入 `memory/model_decisions/`。

交付物：

```text
moe_router/market_state.py
moe_router/router.py
experts/risk_expert.py
experts/factor_expert.py
reports/lightweight_moe_router_v1.md
```

### 第 10-11 周：图数据实验

- 建行业图、概念图、相关性图；
- 先做图特征，不急着 GNN；
- 然后做 GCN/GAT embedding；
- 最后尝试 GConvGRU。

交付物：

```text
graph/builders/
graph/snapshots/
graph_models/baselines/
reports/graph_factor_experiment_v1.md
```

### 第 12 周：整合复盘与受控进化

- 把策略、因子、模型、图、MoE 的输出统一进候选池评分；
- 建立 daily research review；
- 让 Codex 生成小 patch proposal，但不自动合并；
- 输出 V7-V8 的技术债清单。

交付物：

```text
memory/trade_reviews/YYYY-MM-DD.md
memory/model_decisions/YYYY-MM-DD_model_votes.jsonl
research_proposals/YYYY-MM-DD_next_experiments.md
reports/v7_v8_integration_review.md
```

---

## 13. 推荐阅读顺序

### 第一层：当前必须读

1. AKQuant：测试、黄金测试、walk-forward；
2. Qlib：AI 量化 pipeline、Alpha158 / Alpha360；
3. vectorbt：批量实验；
4. QuantStats：绩效报表；
5. Alphalens：因子有效性分析。

### 第二层：工程架构读

1. Hikyuu：A股策略组件拆分；
2. Backtrader：回测引擎和 Analyzer；
3. RQAlpha：Mod 扩展机制；
4. Lean：专业交易引擎架构；
5. NautilusTrader：确定性事件驱动和回放；
6. vn.py：Gateway、EventEngine、风控和 UI。

### 第三层：模型研究读

1. MLFinPy / MLFinLab：金融机器学习标签和去泄漏；
2. sktime：时间序列 ML；
3. PyTorch Forecasting：TFT 和深度时序；
4. FinRL：强化学习沙盒；
5. PyTorch Geometric Temporal / DGL / THGNN：动态图和股票关系图；
6. DeepSpeed / Tutel：MoE 工程思想。

---

## 14. 项目目录建议

```text
zk-trading/
  docs/
    learning/
      V4_to_V9_learning_guide.md
      open_source_mapping.md
      factor_research_guide.md
      moe_graph_ml_guide.md
  data/
  features/
  factors/
  factor_store/
  strategies/
  research/
    experiments/
    parameter_sweeps/
    factor_reports/
    model_reports/
    graph_reports/
  models/
    registry/
    checkpoints/
    inference_logs/
  labels/
  ml_pipeline/
  walk_forward/
  moe_router/
  experts/
  graph/
  graph_models/
  trade_gateway/
  risk_cage/
  audit/
  memory/
    raw_events/
    trade_reviews/
    strategy_performance/
    code_evolution/
    model_decisions/
    risk_events/
```

---

## 15. 每个研究任务的验收清单

### 策略任务

- [ ] 有明确策略假设；
- [ ] 有交易规则；
- [ ] 有退出规则；
- [ ] 有风控规则；
- [ ] 有交易成本；
- [ ] 有 benchmark；
- [ ] 有 out-of-sample；
- [ ] 有极端行情测试；
- [ ] 有交易明细；
- [ ] 有审计记录。

### 因子任务

- [ ] 有因子定义；
- [ ] 有 as_of_date；
- [ ] 无未来函数；
- [ ] 有 IC / RankIC；
- [ ] 有分组收益；
- [ ] 有换手率；
- [ ] 有行业 / 市值暴露；
- [ ] 有衰减曲线；
- [ ] 有容量评估；
- [ ] 有退役规则。

### ML 任务

- [ ] 有标签定义；
- [ ] 有训练 / 验证 / 测试 / 样本外；
- [ ] 有 walk-forward；
- [ ] 有泄漏检查；
- [ ] 有概率校准；
- [ ] 有特征重要性；
- [ ] 有不确定性；
- [ ] 有 benchmark；
- [ ] 有模型版本；
- [ ] 模型只输出评分或解释。

### MoE 任务

- [ ] 有专家定义；
- [ ] 有路由规则；
- [ ] 有市场状态识别；
- [ ] 有专家贡献分析；
- [ ] 有负载平衡；
- [ ] 有风险专家覆盖机制；
- [ ] 有模型投票日志；
- [ ] 有回测对比；
- [ ] 有人工解释；
- [ ] 不直接下单。

### 图模型任务

- [ ] 有图 schema；
- [ ] 每条边有 source；
- [ ] 每条边有 visible_at；
- [ ] 图快照有 as_of_date；
- [ ] 相关性图只用历史窗口；
- [ ] 有 graph baseline；
- [ ] 有 GNN / RNN 对比；
- [ ] 有 walk-forward；
- [ ] 有风控解释；
- [ ] 输出只作为候选评分。

---

## 16. 最适合下一步交给 Codex 的任务

```text
请在 ZK-trading 当前 V4.0 基础上，创建 docs/learning/V4_to_V9_learning_guide.md，
并基于该学习指南生成第一批可执行工程任务清单。

任务清单必须分为：
1. V4.0 研究底座；
2. V6.5 策略库；
3. V7.0 Alpha 因子；
4. V7.5 金融 ML；
5. V8.0 轻量 MoE；
6. V8.5 图数据 + RNN / Temporal GNN；
7. V9.0 受控代码进化。

每个任务必须包含：
- 目标；
- 涉及目录；
- 需要参考的开源项目；
- 风险边界；
- 测试要求；
- 预期交付物；
- 是否需要写入 memory/。

限制：
- 不接入实盘下单；
- 不保存凭证；
- 不绕过风控；
- 所有模型输出只能是评分、解释或候选建议；
- 策略、因子和模型改动必须通过测试、回测、样本外验证和人工确认。
```

---

## 17. 参考来源

> 以下来源用于学习方向和项目映射。实际接入前仍需再次检查许可证、维护状态、依赖版本和适配成本。

| 来源 | 链接 | 本指南使用点 |
|---|---|---|
| RQAlpha | https://github.com/ricequant/rqalpha | 可扩展、可替换的 Python 回测 / 交易框架，Mod Hook 思路 |
| Hikyuu | https://hikyuu.readthedocs.io/zh-cn/latest/overview.html | A股适配、市场环境、信号、止盈止损、资金管理、滑点、多因子、组合 |
| Backtrader | https://www.backtrader.com/ | 可复用策略、指标、Analyzer、回测与交易框架 |
| vectorbt | https://github.com/polakowo/vectorbt | 大规模策略实验、交易分析、组合可视化 |
| Qlib | https://github.com/microsoft/qlib | AI 量化平台、Alpha158 / Alpha360、模型 pipeline |
| Lean | https://github.com/QuantConnect/Lean | 专业算法交易引擎、回测与 live 架构参考 |
| NautilusTrader | https://nautilustrader.io/ | Rust/Python 事件驱动、backtest/live 一致性 |
| vn.py / VeighNa | https://github.com/vnpy/vnpy | EventEngine、Gateway、风控、国内量化平台架构 |
| AKQuant | https://github.com/akfamily/akquant | Golden tests、T+1、涨跌停、walk-forward |
| Freqtrade | https://github.com/freqtrade/freqtrade | dry-run、backtesting、机器学习参数优化、安全默认值 |
| FinRL | https://github.com/AI4Finance-Foundation/FinRL | 金融强化学习沙盒 |
| QuantStats | https://github.com/ranaroussi/quantstats | 绩效指标、图表、HTML 报告 |
| Alphalens | https://github.com/quantopian/alphalens | Alpha 因子表现分析 |
| empyrical | https://github.com/quantopian/empyrical | 风险和绩效指标 |
| pyfolio | https://github.com/quantopian/pyfolio | 组合风险分析 |
| TA-Lib | https://ta-lib.org/ | 技术指标与形态识别 |
| pandas-ta | https://pypi.org/project/pandas-ta/ | Pandas 技术指标库 |
| ta | https://github.com/bukosabino/ta | 金融时间序列特征工程 |
| MLFinLab | https://github.com/hudson-and-thames/mlfinlab | 金融机器学习、标签、回测统计；需核查依赖和维护状态 |
| MLFinPy | https://mlfinpy.readthedocs.io/ | 金融机器学习工具箱，受 MLFinLab 启发 |
| sktime | https://github.com/sktime/sktime | 时间序列 forecasting / classification / anomaly detection |
| PyTorch Forecasting | https://github.com/sktime/pytorch-forecasting | 深度时序预测、TFT、解释性 |
| PyTorch Geometric | https://github.com/pyg-team/pytorch_geometric | GNN 基础设施 |
| PyTorch Geometric Temporal | https://github.com/benedekrozemberczki/pytorch_geometric_temporal | 动态图 / 时序图神经网络 |
| DGL | https://github.com/dmlc/dgl | 高性能图深度学习库 |
| THGNN | https://github.com/TongjiFinLab/THGNN | 金融时序异构图研究参考 |
| DeepSpeed MoE | https://github.com/deepspeedai/DeepSpeed | MoE 训练 / 推理基础设施 |
| Tutel | https://github.com/microsoft/tutel | 优化的 MoE 实现 |
| lucidrains MoE | https://github.com/lucidrains/mixture-of-experts | PyTorch MoE 教学实现 |

---

## 18. 最终建议

在 V4.0 之后，最优路线不是“立刻堆很多 AI 模型”，而是：

```text
可信数据 → 因子平台 → 策略库 → 金融 ML → 轻量 MoE → 图时序模型 → 受控代码进化
```

其中最关键的是：

1. **V4.0 先把数据、特征、模型日志、实验复现做好**；
2. **V6.0 之前所有模型都不能越过人审和风控**；
3. **V6.0 之后先扩展策略库和 Alpha 因子平台，再做复杂 ML**；
4. **MoE 先做轻量路由器，不要一开始上分布式大模型**；
5. **图数据 + RNN / Temporal GNN 先做图特征基线，再做 GNN，再做动态图深度模型**；
6. **任何新策略、新因子、新模型必须能写入 memory、能审计、能回放、能退役**。

这条路线能让系统越来越聪明，但仍然被风控、审计、人审和版本控制约束住。
