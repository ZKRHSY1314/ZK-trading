# ZK-trading V1.0 优化细节汇总

> 项目：`ZKRHSY1314/ZK-trading`  
> 目标：把当前 V1.0 从“AI 监控 + 模拟盘骨架”升级为“可验证、可复盘、可扩展的 A 股量化辅助交易系统”。  
> 定位：当前阶段仍建议保持 **模拟交易 + 人工确认**，不要直接接入实盘自动下单。

---

## 0. 总体判断

V1.0 的方向是正确的：  
系统没有急于做实盘自动下单，而是围绕 **规则优先、风控优先、模拟交易、人工确认、复盘学习** 搭建了较安全的工程骨架。

优点主要有：

1. 明确区分模拟盘与实盘权限，默认禁用实盘。
2. 决策顺序采用“交易铁律 > 风控 > 策略规则 > 案例相似度 > AI解释”。
3. 后端采用 FastAPI，前端控制台与后端接口分离。
4. 已有知识库、候选池、模拟交易、监控、复盘、学习样本等模块雏形。
5. 自动化任务中对 live trading、broker、credential、buy、sell、trade 等危险关键词有阻断设计。

但 V1.0 的主要短板也很明显：

1. 策略规则打分逻辑有偏差。
2. 部分配置参数没有真正生效。
3. 涨跌停、复权、板块差异等 A 股核心规则处理不足。
4. 回测不是严格历史行情回测，偏样本标签统计。
5. 模拟交易撮合过于理想化。
6. 数据源以免费 Pull 接口为主，盘中稳定性不足。
7. AI 学习和权重优化存在明显过拟合风险。
8. 缺少系统化测试和可复现实验报告。

---

# 一、V1.0 现有问题清单

## 1. 策略规则打分逻辑存在严重偏差

### 1.1 问题描述

当前规则引擎逻辑是：

```python
score += hit.score_delta
blocked = blocked or (hit.hard_block and not hit.passed)
```

也就是说，只要某条规则通过，就把它的权重加入总分。

但当前 `rules.yaml` 中：

```yaml
candidate_tiers:
  strong_min_score: 80
  watch_min_score: 60

rules:
  - id: constitution_no_high_position
    name: 不做高位股
    group: constitution
    enabled: true
    weight: 100
    hard_block: true
```

这会导致：

> 只要一只股票满足“不是高位股”，就可能直接获得 100 分，从而进入 strong 强候选。

这在交易逻辑上是不合理的。

“不做高位股”是 **准入过滤条件**，不是 **买入加分条件**。

### 1.2 风险后果

可能出现以下错误：

1. 低位但弱势的股票被误判为强候选。
2. 长期阴跌股因为价格远低于历史高点，被误认为“低位机会”。
3. 真正的策略触发条件，例如涨停、放量、分歧点、板块联动，被高位过滤规则的 100 分掩盖。
4. 候选池质量下降，后续学习样本被污染。

### 1.3 优化建议

将规则分为四类：

| 类型 | 作用 | 是否加分 |
|---|---|---|
| constitution | 交易铁律，只负责阻断 | 否 |
| risk | 风控规则，可阻断或降权 | 一般不加分 |
| strategy | 买入策略规则 | 是 |
| case_memory | 案例相似度 | 可加减分 |
| ai_explanation | 解释，不直接决策 | 否 |

建议修改：

```yaml
- id: constitution_no_high_position
  name: 不做高位股
  group: constitution
  enabled: true
  weight: 0
  hard_block: true
```

或者在 `RuleEngine` 中加入：

```python
if rule.get("group") in {"constitution", "risk"}:
    score_delta = 0
else:
    score_delta = float(rule.get("weight", 0)) if passed else 0
```

### 1.4 推荐优先级

**P0，必须优先修。**

---

## 2. 配置参数与代码实现不一致

### 2.1 问题描述

`rules.yaml` 中写了市值区间：

```yaml
min_market_cap_billion: 50
max_market_cap_billion: 200
```

但当前灯盏策略实际只检查：

1. 是否低位。
2. 是否涨停。
3. PB 是否超阈值。
4. 是否有量比。
5. 5 日涨幅是否过大。

市值参数没有真正参与判断。

### 2.2 风险后果

1. 配置文件看起来很完整，但实际规则没有生效。
2. 用户误以为系统筛掉了不符合市值要求的标的。
3. 回测和复盘结果会高估规则质量。
4. 后续 AI 学习会基于错误样本继续优化，形成错误闭环。

### 2.3 优化建议

在 `MarketSnapshot.metadata` 中增加：

```python
"market_cap_billion": ...,
"float_market_cap_billion": ...,
```

在 `DengZhanSignals.is_low_position_limit_up()` 中增加：

```python
market_cap = snapshot.metadata.get("market_cap_billion")
min_cap = params.get("min_market_cap_billion")
max_cap = params.get("max_market_cap_billion")

if market_cap is not None:
    if min_cap is not None and market_cap < float(min_cap):
        return False, f"总市值 {market_cap:.2f} 亿低于阈值 {float(min_cap):.2f} 亿"
    if max_cap is not None and market_cap > float(max_cap):
        return False, f"总市值 {market_cap:.2f} 亿高于阈值 {float(max_cap):.2f} 亿"
```

同时增加测试：

```text
市值 30 亿：不得通过 50 亿下限
市值 100 亿：通过
市值 300 亿：不得通过 200 亿上限
缺失市值：标记为 data_warning，不建议直接 strong
```

### 2.4 推荐优先级

**P0，必须优先修。**

---

## 3. 涨停判断硬编码，忽略 A 股板块差异

### 3.1 问题描述

当前策略中涨停判断默认：

```python
min_limit_up_pct = 9.9
```

这只适合多数主板非 ST 股票，并不适合全部 A 股。

A 股不同标的涨跌停制度不同：

| 类型 | 常见涨跌幅限制 |
|---|---:|
| 主板普通股 | 10% |
| ST / *ST | 5% |
| 创业板 | 20% |
| 科创板 | 20% |
| 北交所 | 30% |
| 新股上市前若干交易日 | 可能无常规涨跌停限制 |

### 3.2 风险后果

1. 创业板、科创板 20CM 股票可能被误判。
2. ST 票 5% 涨停可能被系统漏掉或错误处理。
3. 北交所 30CM 完全不适配。
4. 打板策略回测会严重失真。

### 3.3 优化建议

新增 `board_type` 和 `limit_up_pct` 计算函数。

建议在 `app/data/symbols.py` 中增加：

```python
def infer_board_type(code: str, name: str | None = None) -> str:
    if name and ("ST" in name.upper() or "*ST" in name.upper()):
        return "st"
    if code.startswith("300") or code.startswith("301"):
        return "chinext"
    if code.startswith("688"):
        return "star"
    if code.startswith(("8", "4", "9")):
        return "bse"
    return "main"
```

新增：

```python
def limit_up_threshold(board_type: str) -> float:
    mapping = {
        "main": 9.8,
        "st": 4.8,
        "chinext": 19.5,
        "star": 19.5,
        "bse": 29.0,
    }
    return mapping.get(board_type, 9.8)
```

在 Snapshot 中写入：

```python
metadata={
    "board_type": board_type,
    "limit_up_threshold": limit_up_threshold(board_type),
}
```

策略判断改为：

```python
threshold = snapshot.metadata.get("limit_up_threshold")
if pct_change < threshold:
    return False, f"涨幅 {pct_change:.2f}% 未达到 {board_type} 涨停候选阈值 {threshold:.2f}%"
```

### 3.4 推荐优先级

**P0，必须优先修。**

---

## 4. 历史高点计算没有处理复权和时间窗口

### 4.1 问题描述

当前低位判断逻辑是：

```python
ratio = snapshot.price / snapshot.historical_high
```

如果 `historical_high` 是未复权历史最高价，会存在严重失真。

例如一只股票历史上高送转、分红、除权之后，当前价格和未复权历史高点不能直接比较。

另外，如果用“上市以来最高价”，可能把长期下跌、基本面恶化的股票错误识别为“低位”。

### 4.2 风险后果

1. 除权股票被误判为低位。
2. 长期下降通道股票被误判为机会。
3. 低位策略信号质量下降。
4. 回测结果不可信。

### 4.3 优化建议

将 AKShare 日线改为前复权：

```python
ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
```

同时不要只用上市以来高点，建议增加滚动窗口：

```python
historical_high_250 = hist["最高"].tail(250).max()
historical_high_500 = hist["最高"].tail(500).max()
```

Snapshot 中保留：

```python
metadata={
    "high_250": historical_high_250,
    "high_500": historical_high_500,
    "price_to_high_250": price / historical_high_250,
    "price_to_high_500": price / historical_high_500,
}
```

低位判断建议：

```text
主判断：当前价 / 250日高点
辅助判断：当前价 / 500日高点
禁用：直接使用未复权上市以来最高价
```

### 4.4 推荐优先级

**P0，必须优先修。**

---

## 5. 数据源方案存在盘中稳定性隐患

### 5.1 问题描述

当前系统优先使用 AKShare 免费数据源，失败时使用腾讯只读报价接口兜底。

这种方式适合 Demo、复盘、低频扫描，但不适合大规模 1 分钟盘中监控。

### 5.2 风险后果

1. 高频请求可能触发反爬或 IP 限制。
2. 免费接口字段不稳定，容易变更。
3. 拉取模式延迟高。
4. 盘中数据缺失会导致监控连续性中断。
5. fallback 数据源不一定具备完整量价字段。

### 5.3 优化建议

短期：

1. 对 AKShare 和腾讯接口增加本地缓存。
2. 增加请求速率限制。
3. 对全 A 扫描和候选池监控分频处理。
4. 所有 fallback 数据生成的计划必须降低置信度。
5. 监控日志记录 `data_source`、`data_quality`、`latency_ms`。

中期：

1. 引入可配置多数据源：
   - AKShare。
   - 腾讯报价。
   - 东方财富接口。
   - Tushare。
   - JoinQuant。
   - QMT。
2. 建立统一 `MarketDataProvider` 抽象。
3. 增加 Provider 健康评分。

长期：

1. 使用 WebSocket / Tick 推送数据。
2. 使用异步队列处理行情事件。
3. FastAPI 只负责展示和控制，不直接承担高频行情采集。

### 5.4 推荐优先级

**P1。**

---

## 6. 回测逻辑不是真实历史行情回测

### 6.1 问题描述

当前 `LearningService.run_backtest()` 更像是基于学习样本标签的统计，而不是基于历史行情逐日回测。

典型逻辑是：

```python
if row["label"] in POSITIVE_LABELS:
    return 0.08
if row["label"] in NEGATIVE_LABELS:
    return -0.04
```

这意味着：

1. 正样本默认收益 8%。
2. 负样本默认亏损 4%。
3. 没有真实买入日期。
4. 没有真实卖出规则。
5. 没有逐日净值曲线。
6. 没有真实最大回撤。
7. 没有考虑涨停买不进、跌停卖不出。

### 6.2 风险后果

1. 胜率、盈亏比、最大回撤容易虚高。
2. 策略看起来有效，但实盘或真实回测可能完全失效。
3. AI 权重优化会在错误指标上优化。
4. 用户可能过早信任系统。

### 6.3 优化建议

新增真正的事件驱动回测模块：

```text
backend/app/backtest/
  engine.py
  broker.py
  metrics.py
  data_loader.py
  report.py
```

回测流程：

```text
1. 加载某日之前的历史数据
2. 用当日收盘或盘中数据生成候选信号
3. 次日按开盘价、涨停状态、成交量判断能否买入
4. 买入后逐日检查止损、止盈、持有期退出
5. 扣除手续费、印花税、滑点
6. 生成交易明细
7. 生成净值曲线
8. 计算最大回撤、年化收益、胜率、盈亏比、夏普、卡玛比率
```

回测结果需要至少输出：

```text
total_return
annual_return
max_drawdown
win_rate
profit_loss_ratio
sharpe
calmar
trade_count
avg_holding_days
turnover
fee_total
slippage_total
limit_up_miss_count
limit_down_exit_fail_count
```

### 6.4 推荐优先级

**P0/P1，策略上线前必须做。**

---

## 7. 模拟成交过于理想化

### 7.1 问题描述

当前模拟交易器已经实现：

1. 100 股整数倍。
2. 现金不足限制。
3. T+1 可卖数量。
4. 手续费。
5. 印花税。
6. 固定滑点。

但仍然存在理想化问题：

1. 默认下单即成交。
2. 没有涨停买不进。
3. 没有跌停卖不出。
4. 没有部分成交。
5. 没有成交量约束。
6. 没有盘口排队模型。
7. 没有开盘跳空、集合竞价成交规则。

### 7.2 风险后果

1. 打板策略收益被高估。
2. 跌停逃生能力被高估。
3. 模拟盘与实盘偏差大。
4. 训练样本可能产生错误标签。

### 7.3 优化建议

先加入简单成交约束：

```python
if order.side == "buy" and snapshot.is_limit_up:
    raise ValueError("涨停状态下默认无法保证买入成交")

if order.side == "sell" and snapshot.is_limit_down:
    raise ValueError("跌停状态下默认无法保证卖出成交")
```

再加入成交量约束：

```python
max_fill_quantity = int(snapshot.volume * 0.001)
filled_quantity = min(order.quantity, max_fill_quantity)
```

中期加入成交概率模型：

```text
涨停打板成交概率 = 当日成交额 / 封单金额 × 修正系数
跌停卖出成交概率 = 当日成交额 / 跌停封单金额 × 修正系数
炸板回封场景单独处理
```

长期升级为订单簿级别模拟：

```text
买一/卖一价格
买一/卖一封单量
成交量变化
撤单变化
排队位置估算
部分成交
未成交撤单
```

### 7.4 推荐优先级

**P1。**

---

## 8. 仓位管理没有使用账户实时资产

### 8.1 问题描述

当前 `SimulationPlanner` 里买入数量大致按：

```python
budget = settings.default_cash * position_ratio
```

也就是说，它使用默认初始资金，而不是当前模拟账户的实际现金或总资产。

### 8.2 风险后果

1. 已经买入多只股票后，后续计划仍按初始资金计算。
2. 可能生成超出实际可用现金的计划。
3. 组合风险不可控。
4. 不能反映连续亏损后的降仓逻辑。

### 8.3 优化建议

改成：

```python
account = SimulatedBroker().account()
available_cash = account.cash
total_equity = account.cash + estimated_position_value

target_amount = total_equity * position_ratio
order_amount = min(target_amount, available_cash * cash_usage_limit)
```

增加账户级风控：

```text
单票最大仓位：10%
单行业最大仓位：30%
当日最大新开仓：20%
总仓位上限：根据市场环境动态调整
连续亏损 3 笔：暂停新开仓
当日亏损超过 2%：停止交易
总回撤超过 8%：进入保护模式
```

### 8.4 推荐优先级

**P1。**

---

## 9. AI 权重优化存在过拟合风险

### 9.1 问题描述

系统设计中允许 AI 根据模拟盘收益改善来调整策略权重。

这个方向可以保留，但必须限制。

A 股风格轮动强，如果 AI 根据近期行情调参，很容易出现：

1. 最近小盘强，就加大小盘权重。
2. 最近涨停多，就提高打板策略权重。
3. 最近低价股强，就偏向低价股。
4. 一旦市场风格切换，策略大幅回撤。

### 9.2 风险后果

1. 过拟合最近行情。
2. 模拟收益上升，但样本外失效。
3. AI 越调越激进。
4. 规则体系失去可解释性。

### 9.3 优化建议

AI 只能提出候选方案，不能直接改生产规则。

权重更新流程：

```text
1. AI 生成参数修改 Proposal
2. 系统保存为 pending 状态
3. 自动进行多周期回测
4. 自动进行样本外测试
5. 自动进行压力测试
6. 指标达标后进入人工审核
7. 人工批准后才写入规则配置
8. 保留版本号和回滚点
```

必须加入验证集：

```text
训练集：最近 3 个月
验证集 1：过去 1 年
验证集 2：下跌行情区间
验证集 3：震荡行情区间
验证集 4：极端波动行情区间
```

参数更新门槛：

```text
验证集收益不得下降
最大回撤不得增加
交易次数不得过少
收益不能来自少数极端样本
单票贡献不得过高
换手率不能异常升高
```

### 9.4 推荐优先级

**P1。**

---

## 10. 大盘环境风控不足

### 10.1 问题描述

当前规则主要围绕个股信号，缺少市场环境过滤。

但对 A 股短线策略来说，大盘环境非常关键。

例如：

1. 指数跌破 20 日均线。
2. 全市场涨停家数极少。
3. 跌停家数明显增加。
4. 连板高度下降。
5. 成交额萎缩。
6. 情绪周期退潮。

这些情况下，即使个股满足局部形态，也应该降低仓位甚至空仓。

### 10.2 优化建议

新增市场环境模块：

```text
backend/app/market_regime/
  indicators.py
  service.py
  risk_switch.py
```

核心指标：

```text
上证指数 / 沪深300 / 中证1000 是否在20日均线上方
全市场涨跌家数
涨停家数
跌停家数
连板高度
炸板率
成交额变化
北向资金或主力资金趋势
行业轮动强度
```

输出：

```python
MarketRegime(
    regime="bullish" | "neutral" | "risk_off",
    max_total_position=0.8,
    max_single_position=0.1,
    allow_new_position=True,
    reason=[...]
)
```

策略计划必须读取该模块：

```python
if market_regime.regime == "risk_off":
    allowed = False
    action = "observe"
```

### 10.3 推荐优先级

**P1。**

---

## 11. AI 解释层目前不是真正 AI

### 11.1 问题描述

当前 `DisabledModelGateway` 是本地确定性解释器，不是真正大模型。

它会根据规则结果、风险说明、相似案例生成解释，但 OpenAI、Qwen、本地模型接口仍是 `NotImplementedError`。

### 11.2 优化建议

即使未来接入大模型，也不要让 AI 直接决定买卖。

AI 的角色应该是：

```text
解释为什么入选
总结相似案例
识别失败原因
生成复盘报告
提出规则修改建议
辅助用户理解信号
```

AI 不应该直接做：

```text
直接下单
直接改变策略权重
绕过硬风控
修改实盘权限
删除交易日志
```

### 11.3 推荐优先级

**P2。**

---

## 12. 监控信号过于简单

### 12.1 问题描述

当前监控信号主要根据：

1. 是否允许模拟买入。
2. 是否被风控阻断。
3. 涨跌幅变化是否超过 1%。
4. 价格是否变化。
5. 数据是否错误。

这对 v1.0 足够，但对短线交易不够。

### 12.2 优化建议

加入更细的盘中事件：

```text
首次涨停
开板
回封
炸板
放量突破
缩量回踩
跌破均线
跌破成本线
量比突增
封单增强
封单衰减
板块同步拉升
板块分歧
大盘跳水
```

每个事件都要有：

```text
事件时间
触发价格
触发原因
相关指标
建议动作
是否需要人工确认
后续验证结果
```

### 12.3 推荐优先级

**P2。**

---

## 13. 缺少自动化测试

### 13.1 问题描述

项目依赖中有 `pytest`，但目前没有看到系统化测试覆盖。

交易系统必须有测试，尤其是风控和撮合逻辑。

### 13.2 建议测试文件

```text
backend/tests/test_rule_engine.py
backend/tests/test_dengzhan_signals.py
backend/tests/test_simulated_broker.py
backend/tests/test_simulation_planner.py
backend/tests/test_snapshot_builder.py
backend/tests/test_learning_backtest.py
backend/tests/test_market_regime.py
```

### 13.3 必测用例

```text
高位股必须被 block
低位但不涨停不能 strong
市值不符合不能入池
创业板 19.8% 应识别为涨停候选
主板 9.9% 应识别为涨停候选
ST 4.9% 应识别为涨停候选
5 日涨幅过大必须降级
现金不足不能买
非 100 股整数倍不能买
T+1 当天不能卖
涨停默认不保证买入成交
跌停默认不保证卖出成交
fallback 数据不得直接给 strong
AI proposal 不得直接修改生产配置
```

### 13.4 推荐优先级

**P0/P1。**

---

# 二、建议的代码修改清单

## 1. `backend/app/rules/engine.py`

### 修改目标

区分硬风控、风险规则、策略规则的打分逻辑。

### 建议修改

```python
def _score_delta(self, rule: dict, passed: bool) -> float:
    if not passed:
        return 0.0

    group = rule.get("group")
    if group in {"constitution", "risk"}:
        return 0.0

    return float(rule.get("weight", 0))
```

并在 `_evaluate_rule()` 中使用：

```python
score_delta=self._score_delta(rule, passed)
```

---

## 2. `backend/configs/rules.yaml`

### 修改目标

避免硬风控规则直接给 100 分。

### 建议修改

```yaml
- id: constitution_no_high_position
  name: 不做高位股
  group: constitution
  enabled: true
  weight: 0
  hard_block: true
```

增加更合理的打分：

```yaml
- id: dengzhan_low_position_limit_up
  weight: 40

- id: dengzhan_forced_divergence
  weight: 30

- id: market_regime_positive
  weight: 20

- id: case_similarity_positive
  weight: 10
```

强候选：

```yaml
strong_min_score: 70
watch_min_score: 40
```

---

## 3. `backend/app/strategies/dengzhan.py`

### 修改目标

补齐板块涨停、复权高点、市值区间、fallback 降权。

### 建议新增判断

```python
def is_limit_up_candidate(self, snapshot: MarketSnapshot, params: dict) -> tuple[bool, str]:
    pct_change = snapshot.pct_change
    if pct_change is None:
        return False, "缺少涨跌幅，无法判断涨停"

    threshold = snapshot.metadata.get("limit_up_threshold") or params.get("min_limit_up_pct", 9.8)

    if pct_change < float(threshold):
        return False, f"涨幅 {pct_change:.2f}% 未达到动态涨停阈值 {float(threshold):.2f}%"

    return True, f"涨幅 {pct_change:.2f}% 达到动态涨停阈值"
```

---

## 4. `backend/app/data/akshare_provider.py`

### 修改目标

默认使用前复权数据。

### 建议修改

```python
def get_daily_bars(self, symbol: str) -> pd.DataFrame:
    import akshare as ak
    return ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
```

如果需要保留原始数据：

```python
def get_daily_bars(self, symbol: str, adjust: str = "qfq") -> pd.DataFrame:
    import akshare as ak
    return ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust=adjust)
```

---

## 5. `backend/app/data/snapshot_builder.py`

### 修改目标

增强 Snapshot 字段。

### 建议新增 metadata

```python
metadata={
    "board_type": board_type,
    "limit_up_threshold": limit_up_threshold,
    "high_250": high_250,
    "high_500": high_500,
    "price_to_high_250": price_to_high_250,
    "price_to_high_500": price_to_high_500,
    "market_cap_billion": market_cap_billion,
    "float_market_cap_billion": float_market_cap_billion,
    "data_quality": data_quality,
}
```

fallback 时增加：

```python
"data_quality": "fallback_quote",
"confidence": "low",
```

---

## 6. `backend/app/simulation/planner.py`

### 修改目标

用真实账户资金和市场环境决定仓位。

### 建议修改

```python
account = SimulatedBroker().account()
available_cash = account.cash
target_amount = total_equity * position_ratio
budget = min(target_amount, available_cash * 0.95)
```

加入市场环境：

```python
regime = MarketRegimeService().current()

if not regime.allow_new_position:
    return observe_plan(reason="市场环境风险较高，暂停新开仓")

position_ratio = min(position_ratio, regime.max_single_position)
```

---

## 7. `backend/app/simulation/broker.py`

### 修改目标

增加真实成交约束。

### 建议增加

```python
def validate_market_constraints(self, order, snapshot):
    if order.side == TradeSide.buy and snapshot.metadata.get("is_limit_up"):
        raise ValueError("涨停状态下不保证买入成交")

    if order.side == TradeSide.sell and snapshot.metadata.get("is_limit_down"):
        raise ValueError("跌停状态下不保证卖出成交")
```

---

## 8. 新增 `backend/app/backtest/`

### 建议目录

```text
backend/app/backtest/
  __init__.py
  engine.py
  broker.py
  metrics.py
  data_loader.py
  report.py
```

### 回测核心能力

```text
真实日线/分钟线回放
信号生成
撮合成交
持仓管理
止损止盈
交易成本
净值曲线
绩效指标
报告输出
```

---

## 9. 新增 `backend/app/market_regime/`

### 建议目录

```text
backend/app/market_regime/
  __init__.py
  indicators.py
  service.py
  risk_switch.py
```

### 输出结构

```python
class MarketRegime:
    regime: str
    allow_new_position: bool
    max_total_position: float
    max_single_position: float
    reason: list[str]
```

---

# 三、版本演进路线

## V1.1：修正核心规则

目标：让候选池不再被错误规则污染。

任务：

1. 硬风控不加分。
2. 市值区间真正生效。
3. 动态涨停阈值。
4. 前复权日线。
5. 250/500 日滚动高点。
6. fallback 数据降置信度。
7. 增加核心单元测试。

验收标准：

```text
低位但不涨停，不能进入 strong
高位股必须 rejected
创业板、科创板、ST 涨停识别正确
市值不符合条件必须被过滤或降级
所有硬风控测试通过
```

---

## V1.2：真实历史回测

目标：用真实行情验证策略，而不是用样本标签估算。

任务：

1. 新增 backtest 模块。
2. 建立事件驱动回测流程。
3. 输出交易明细和净值曲线。
4. 输出最大回撤、胜率、盈亏比等指标。
5. 加入涨停买不进、跌停卖不出约束。
6. 对不同市场阶段分段回测。

验收标准：

```text
可以对任意日期区间回测
可以导出 CSV/Excel 交易明细
可以生成回测报告
收益曲线和交易记录可复现
```

---

## V1.3：组合风控和大盘环境

目标：从单股判断升级为组合级交易系统。

任务：

1. 新增 market_regime 模块。
2. 增加指数趋势过滤。
3. 增加涨跌停家数、市场情绪指标。
4. 增加组合仓位上限。
5. 增加连续亏损暂停机制。
6. 增加回撤保护模式。

验收标准：

```text
弱市自动降低仓位
极端风险环境自动停止新开仓
组合仓位不超过设定上限
连续亏损后自动进入观察模式
```

---

## V1.4：盘中监控增强

目标：从“价格变化提醒”升级为“短线事件识别”。

任务：

1. 增加 1 分钟 K 线。
2. 增加首次涨停、炸板、回封事件。
3. 增加封单金额和开板次数。
4. 增加板块联动信号。
5. 增加盘中事件复盘。

验收标准：

```text
能识别涨停、炸板、回封
能记录事件时间和价格
能生成单股盘中复盘
能区分主动上涨和板块带动
```

---

## V1.5：AI 辅助复盘与参数建议

目标：让 AI 做解释和复盘，而不是直接做交易决策。

任务：

1. 接入 OpenAI/Qwen/本地模型之一。
2. AI 生成复盘报告。
3. AI 生成参数修改 proposal。
4. 参数 proposal 必须经过样本外回测。
5. 人工审核后才允许写入规则配置。
6. 所有修改可回滚。

验收标准：

```text
AI 不得绕过硬风控
AI 不得直接下单
AI 不得直接修改生产规则
所有参数修改都有版本号
所有参数修改都有回测报告
```

---

## V2.0：实盘网关隔离设计

目标：如果未来接实盘，必须保持决策系统和执行系统物理/进程隔离。

架构建议：

```text
Decision System
    ↓
Signal Review Queue
    ↓
Human Confirmation
    ↓
OrderExecutionGateway
    ↓
QMT / PTrade / Broker API
```

实盘网关必须具备：

```text
独立进程
独立配置
安全签名
订单白名单
单日额度限制
一键熔断
一键撤单
日志不可篡改
默认关闭
人工确认
```

短期不建议启用实盘自动下单。

---

# 四、推荐优先级总表

| 优先级 | 任务 | 原因 |
|---|---|---|
| P0 | 修正硬风控加分问题 | 当前会污染候选池 |
| P0 | 动态涨停阈值 | A 股板块制度不同 |
| P0 | 前复权和滚动高点 | 低位判断基础错误会导致全局误判 |
| P0 | 市值参数真正生效 | 配置和代码不一致 |
| P0 | 核心单元测试 | 防止风控逻辑回归错误 |
| P1 | 真实历史回测 | 当前回测不够可信 |
| P1 | 模拟撮合增强 | 当前成交过于理想 |
| P1 | 仓位按实际账户计算 | 当前组合风险不可控 |
| P1 | 大盘环境风控 | 避免弱市硬做个股 |
| P1 | 防过拟合验证集 | 防止 AI 权重乱调 |
| P2 | 盘中事件增强 | 提升短线监控质量 |
| P2 | AI 复盘报告 | 提升解释和总结能力 |
| P3 | 实盘执行网关 | 未来方向，暂不建议急做 |

---

# 五、给 Codex 的建议执行顺序

可以把下面内容直接拆给 Codex 做任务。

## Task 1：修正规则引擎打分

```text
修改 backend/app/rules/engine.py：
1. constitution 和 risk 规则默认不加正向分。
2. hard_block 规则失败时只负责 blocked。
3. strategy 规则通过时才加分。
4. 增加单元测试覆盖高位阻断、低位不涨停不得 strong。
```

## Task 2：加入动态涨跌停阈值

```text
新增 board_type 判断：
1. 主板 10%
2. ST 5%
3. 创业板 20%
4. 科创板 20%
5. 北交所 30%

修改 dengzhan.py：
不再硬编码 9.9%，改用 snapshot.metadata.limit_up_threshold。
```

## Task 3：改为前复权和滚动高点

```text
修改 akshare_provider.py：
默认 adjust='qfq'。

修改 snapshot_builder.py：
计算 high_250、high_500、price_to_high_250、price_to_high_500。
低位判断优先使用 250 日高点。
```

## Task 4：补齐市值过滤

```text
在 snapshot metadata 中加入 market_cap_billion 和 float_market_cap_billion。
在 dengzhan_low_position_limit_up 中真正检查 min_market_cap_billion 和 max_market_cap_billion。
```

## Task 5：重构模拟仓位计算

```text
SimulationPlanner 不再使用 settings.default_cash 计算仓位。
改为读取 SimulatedBroker().account()。
根据账户现金、总资产、市场环境计算买入金额。
```

## Task 6：新增真实回测模块

```text
新增 backend/app/backtest。
实现日线级事件回测。
输出 trades、equity_curve、metrics。
考虑手续费、印花税、滑点、涨停买不进、跌停卖不出。
```

## Task 7：AI 权重 proposal 机制

```text
AI 只能生成 calibration proposal。
proposal 必须 pending。
必须通过样本外回测和人工审批。
不能直接改 rules.yaml。
```

---

# 六、最终建议

当前 V1.0 不建议理解为“已经能赚钱的交易软件”。

更准确的定位应该是：

> 一个具备安全边界的 A 股交易经验结构化、模拟监控和复盘学习系统原型。

下一步最重要的不是增加 AI，而是先把以下三件事做好：

1. **规则真实生效**：配置和代码一致，风控不乱加分。  
2. **回测真实可信**：基于历史行情逐日回放，而不是样本标签估算。  
3. **模拟接近实盘**：处理涨跌停、滑点、成交概率、账户仓位和市场环境。

等系统能连续稳定模拟 1 到 3 个月，且复盘结果和真实行情表现一致，再考虑进一步做半自动提醒。  
实盘自动下单应放在最后，并且必须独立网关、人工确认、可熔断。

---

# 七、补充优化需求：UI 界面简化与中文一致性

## 1. 当前 UI 存在的问题

当前前端界面功能较多，适合开发调试，但作为日常使用的交易驾驶舱，存在以下问题：

1. 页面信息密度过高，用户容易找不到最关键的信号。
2. 功能按钮全部平铺展示，导致界面冗杂。
3. 部分内容存在中英文夹杂，例如 `strong`、`watch`、`rejected`、`sim_buy_allowed`、`risk_blocked` 等直接暴露给用户。
4. 技术日志、调试信息、系统状态、交易建议混在一起，降低了可读性。
5. 重要提醒和普通信息没有明确视觉层级。
6. 对新手用户不够友好，容易误把调试字段当作交易建议。

## 2. UI 优化原则

在不改变现有功能的前提下，建议采用：

```text
核心信息前置
高级功能折叠
调试信息隐藏
中文术语统一
风险提醒突出
操作入口分层
```

## 3. 建议的页面结构

推荐将首页改成 4 个主区域：

```text
1. 今日总览
2. 候选池
3. 模拟计划
4. 复盘与日志
```

### 3.1 今日总览

只展示最关键内容：

```text
系统状态
今日市场环境
当前候选数量
强候选数量
观察候选数量
风险阻断数量
最近一次扫描时间
当前是否允许新开仓
```

避免在首页直接展示大量 JSON、调试字段和英文枚举值。

### 3.2 候选池

候选池建议按 Tab 分组：

```text
强候选
观察池
已阻断
已跳过
```

每只股票卡片只展示：

```text
股票代码
股票名称
当前价格
涨跌幅
候选等级
核心触发原因
主要风险
建议动作
```

详细规则命中情况放入“展开详情”。

### 3.3 模拟计划

模拟计划建议展示：

```text
建议动作：观察 / 模拟买入 / 模拟卖出
参考价格
建议仓位
建议数量
止损价
目标价
触发依据
风险说明
人工确认状态
```

高级字段如 `raw_json`、`metadata`、`snapshot`、`plan_json` 默认折叠。

### 3.4 复盘与日志

复盘区建议分为：

```text
每日复盘
单股复盘
自动化运行日志
数据源日志
错误日志
```

默认只显示“每日复盘”和“关键异常”，其余日志折叠到“开发者模式”。

---

## 4. 功能键位折叠建议

### 4.1 一级常用按钮

首页只保留：

```text
刷新系统状态
运行一次候选扫描
运行一次盘中监控
生成今日复盘
查看模拟账户
```

### 4.2 二级高级按钮

折叠进“高级操作”：

```text
重建学习样本
重新计算候选评分
刷新日线缓存
运行阶段回放
运行阶段匹配
生成参数校准建议
查看自动化任务队列
查看 Agent 审计日志
```

### 4.3 开发者按钮

折叠进“开发者模式”，默认关闭：

```text
查看原始 JSON
查看 API 响应
查看规则命中明细
查看数据库表统计
手动触发指定接口
查看错误堆栈
```

建议增加一个开关：

```text
普通模式 / 开发者模式
```

普通模式面向交易使用，开发者模式面向调试。

---

## 5. 中英文夹杂问题处理

建议建立统一前端翻译映射表。

例如新增：

```text
frontend/src/i18n/zhCN.ts
```

示例映射：

```typescript
export const zhCN = {
  strong: "强候选",
  watch: "观察",
  rejected: "已剔除",
  observe: "观察",
  buy: "模拟买入",
  sell: "模拟卖出",
  sim_buy_allowed: "模拟买入待确认",
  risk_blocked: "风控阻断",
  momentum_up: "动量增强",
  momentum_down: "动量转弱",
  price_changed: "价格变化",
  data_error: "数据异常",
  fallback_quote: "备用行情源",
  daily_bar: "日线数据",
  realtime_quote_fallback: "实时备用报价",
}
```

前端展示时不要直接渲染后端枚举值，而应通过：

```typescript
formatLabel(value)
```

统一转换。

## 6. UI 输出内容优化

### 6.1 风险提示标准化

建议风险提示统一格式：

```text
风险等级：高 / 中 / 低
风险来源：规则 / 数据 / 市场环境 / 历史案例 / AI解释
风险说明：一句话说明
建议动作：观察 / 降仓 / 剔除 / 人工复核
```

### 6.2 AI 解释标准化

AI 输出不建议长篇大段直接堆在页面上，建议分块：

```text
信号摘要
触发规则
相似案例
主要风险
建议观察点
禁止动作
```

### 6.3 日志展示标准化

日志建议使用：

```text
时间
模块
事件类型
严重程度
摘要
详情
```

详情默认折叠。

---

## 7. UI 优化的 Codex 任务

```text
Task UI-1：整理前端页面结构
在不删除功能的前提下，把页面分成 今日总览 / 候选池 / 模拟计划 / 复盘日志 四个区域。

Task UI-2：增加高级操作折叠区
把低频按钮折叠进“高级操作”，默认收起。

Task UI-3：增加开发者模式
raw JSON、API 响应、数据库统计、错误堆栈默认隐藏，仅开发者模式显示。

Task UI-4：统一中文术语映射
新增 zhCN 映射表，所有英文枚举值前端展示时统一转中文。

Task UI-5：优化卡片展示
候选股票、模拟计划、风险提示、AI解释全部改成结构化卡片展示。

Task UI-6：增加视觉优先级
高风险提示、风控阻断、数据异常必须用醒目的状态标签显示。
```

## 8. UI 优化推荐优先级

**P1。**

原因：不影响核心交易逻辑，但会显著提升可用性，降低误操作和误解信号的概率。

---

# 八、补充优化需求：AI 双模型接入与实盘功能边界增强

## 1. 需求理解

用户希望进一步增强 AI 接入能力，考虑配置 AI API 接口，实现：

```text
Codex + 另外一个大模型
双模型交替
互相校验
辅助实盘功能增强
```

这里需要特别强调：

> AI 可以增强分析、复盘、解释、参数建议和人工确认流程，但不建议让 AI 直接获得实盘自动下单权限。

更安全的方向是：

```text
AI 双模型共识 → 生成交易建议 → 风控系统校验 → 模拟盘验证 → 人工确认 → 实盘网关执行
```

而不是：

```text
AI 判断 → 直接下单
```

---

## 2. 双模型架构建议

建议新增统一模型网关：

```text
backend/app/ai/
  model_gateway.py
  providers/
    openai_provider.py
    qwen_provider.py
    deepseek_provider.py
    local_provider.py
  consensus.py
  prompts.py
  audit.py
```

核心结构：

```python
class AIProvider:
    name: str
    role: str

    def analyze_signal(self, context: dict) -> AIAnalysis:
        ...

    def review_risk(self, context: dict) -> AIRiskReview:
        ...

    def propose_calibration(self, context: dict) -> CalibrationProposal:
        ...
```

支持配置：

```env
AI_PRIMARY_PROVIDER=openai
AI_SECONDARY_PROVIDER=qwen
AI_PRIMARY_API_KEY=...
AI_SECONDARY_API_KEY=...
AI_MODE=review_only
AI_CONSENSUS_REQUIRED=true
```

---

## 3. Codex 与另一个模型的分工

### 3.1 Codex 的定位

Codex 更适合：

```text
代码修改
策略规则实现
测试用例生成
回测模块重构
日志和报告格式化
检查配置和代码是否一致
```

不建议 Codex 直接做：

```text
实盘买卖判断
绕过风控
直接执行交易
修改实盘权限
```

### 3.2 另一个模型的定位

另一个模型，例如 OpenAI、Qwen、DeepSeek 或本地模型，更适合：

```text
解释信号
总结风险
比较相似案例
生成复盘报告
提出参数优化建议
识别用户交易经验中的规则
```

### 3.3 双模型交替机制

建议三种模式：

```text
primary_only：只用主模型
dual_review：主模型给建议，副模型审核
debate：两个模型分别给出结论，再由规则系统汇总
```

默认建议使用：

```text
dual_review
```

流程：

```text
1. 规则引擎生成候选信号
2. 主模型解释信号与机会
3. 副模型专门审查风险
4. 若两个模型结论冲突，则降级为“人工复核”
5. 风控规则始终拥有最终否决权
```

---

## 4. AI 共识决策机制

建议输出结构：

```python
AIConsensusResult(
    primary_action="observe",
    secondary_action="observe",
    consensus="agree" | "disagree" | "risk_conflict",
    confidence=0.0,
    final_ai_suggestion="observe",
    must_human_review=True,
    reasons=[...],
    risk_notes=[...],
)
```

决策原则：

```text
两个模型都看多 ≠ 允许买入
两个模型有分歧 = 必须人工复核
任一模型发现重大风险 = 降级观察
规则风控阻断 = AI 无权解除
数据质量低 = AI 只能建议观察
```

---

## 5. AI 接入实盘功能的安全边界

### 5.1 推荐权限分层

```text
Level 0：AI 只解释，不参与建议
Level 1：AI 生成观察建议
Level 2：AI 生成模拟盘计划
Level 3：AI 生成待确认实盘计划
Level 4：人工确认后发送到实盘网关
Level 5：全自动实盘，当前不建议开放
```

当前项目建议最多做到：

```text
Level 3 或 Level 4
```

不建议开放：

```text
Level 5 全自动实盘
```

### 5.2 实盘指令必须经过的关卡

```text
规则风控通过
市场环境允许
账户风控通过
模拟盘计划存在
双模型共识或人工复核
人工确认
实盘网关二次校验
订单额度限制
可撤单机制
完整审计日志
```

### 5.3 实盘交易白名单

建议加入：

```text
允许交易标的白名单
禁止交易标的黑名单
单日最大交易次数
单日最大亏损
单票最大金额
总仓位上限
禁止追高规则
禁止 ST 规则
禁止北交所规则
```

---

## 6. API Key 与配置安全

AI API 接口必须通过 `.env` 或系统环境变量配置，不得写死在代码里。

建议：

```env
OPENAI_API_KEY=
QWEN_API_KEY=
DEEPSEEK_API_KEY=
AI_PRIMARY_PROVIDER=openai
AI_SECONDARY_PROVIDER=qwen
AI_MODE=dual_review
AI_ALLOW_LIVE_ORDER=false
```

安全要求：

```text
API Key 不提交 GitHub
.env 加入 .gitignore
日志中不打印 API Key
错误信息中不回显 API Key
前端不暴露 API Key
生产环境与测试环境分离
```

---

## 7. AI 结果审计日志

每次 AI 分析必须记录：

```text
请求时间
模型名称
模型版本
输入摘要
输出摘要
token 消耗
最终建议
风险提示
是否参与实盘计划
人工确认人
确认时间
订单编号
```

不建议完整保存过长 prompt，但必须保存可追溯摘要。

---

## 8. 防止 AI 幻觉和越权

必须加入硬性规则：

```text
AI 不得修改 enable_live_trading
AI 不得直接写入 broker credential
AI 不得直接调用 buy/sell/order 接口
AI 不得绕过 hard_block
AI 不得删除日志
AI 不得修改历史交易记录
AI 不得把模拟收益描述成实盘收益
```

前端显示 AI 建议时必须加：

```text
AI 建议仅供复核，不构成投资建议；最终操作需人工确认。
```

---

## 9. 双模型实盘增强的 Codex 任务

```text
Task AI-1：新增统一 AIProvider 接口
支持 primary_provider 和 secondary_provider，通过 .env 配置。

Task AI-2：实现 dual_review 共识流程
主模型负责机会解释，副模型负责风险审查；分歧时必须人工复核。

Task AI-3：新增 AI 审计日志表
记录模型、输入摘要、输出摘要、最终建议、人工确认状态。

Task AI-4：增加 AI 权限等级
支持 review_only、simulation_plan、live_plan_pending_confirmation 三种模式。

Task AI-5：前端增加 AI 共识卡片
展示主模型意见、副模型意见、共识结论、风险分歧、人工确认状态。

Task AI-6：强化实盘网关隔离
AI 只能生成 pending live plan，不能直接下单；实盘执行必须由独立 OrderExecutionGateway 完成。

Task AI-7：增加安全测试
测试 AI 在任何情况下都不能绕过 hard_block、不能修改 enable_live_trading、不能直接调用实盘下单。
```

## 10. AI 双模型与实盘增强推荐优先级

**P2 / P3。**

说明：

1. 双模型复盘、解释、风险审查可以放在 P2。
2. 待确认实盘计划可以放在 P3。
3. 全自动实盘不建议开放。

---

# 九、更新后的优先级补充

| 优先级 | 新增任务 | 原因 |
|---|---|---|
| P1 | UI 信息层级重构 | 降低误读信号和误操作概率 |
| P1 | 功能按钮折叠 | 保留功能同时减少界面冗杂 |
| P1 | 中文术语统一 | 提升使用体验，避免中英文混乱 |
| P2 | AI 双模型复盘与风险审查 | 提升解释质量，但不直接参与下单 |
| P2 | AI 共识卡片 | 让用户看到模型分歧与风险 |
| P3 | 待确认实盘计划 | 只生成计划，不直接下单 |
| P3 | 独立实盘执行网关 | 为未来实盘做安全隔离 |
| 禁止 | AI 全自动实盘下单 | 当前阶段风险过高 |

---

# 十、补充后的最终建议

在原有技术路线之外，建议新增两条并行主线：

```text
主线 A：交易逻辑可信化
规则修正 → 真实回测 → 模拟撮合 → 组合风控

主线 B：产品体验可用化
界面简化 → 中文统一 → 功能折叠 → AI 共识卡片

主线 C：AI 安全增强
双模型解释 → 双模型风控审查 → 待确认实盘计划 → 独立执行网关
```

建议近期执行顺序：

```text
1. 先修规则和回测
2. 同步优化 UI
3. 再接 AI 双模型
4. 最后才考虑实盘网关
```

也就是说：

> UI 可以尽快优化，AI 可以先接入做解释和复盘，但实盘自动化必须继续保持克制。  
> 最安全的方向是让 AI 变成“副驾驶”，而不是“自动驾驶”。

