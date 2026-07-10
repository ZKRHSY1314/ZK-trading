# 2026-06-18 策略学习记录：Dataset1 / Dataset2 规则融合、反问与保守优化

## 安全边界与本轮证据

本轮只做研究、复盘和策略优化建议，不触碰实盘、券商、凭证、真实委托或 `rules.yaml`。

运行前安全状态：

- `/health.status=ok`
- `/health.environment=local`
- `/health.live_trading_enabled=false`

训练计划摘要：

- `packet_status=ready`
- `learning_readiness=ready_for_supervised_dry_run_learning`
- `confidence_score=67.0`
- `confidence_tier=backtest_ready_simulation_needed`
- `human_confirm_status=not_ready_for_human_confirm`
- `supervised_dry_run_count=0`
- `supervised_readback_count=0`
- `unique_symbol_count=0`
- `evaluated_session_count=0`
- `candidate_queue_count=5`
- `top_scored_symbol=SH603120`
- `stable_candidate_validation_return_pct=218.681581`
- `stable_candidate_validation_win_rate=0.833333`
- `may_submit_order=false`
- `may_enable_screen_click=false`
- `may_write_rules_yaml=false`
- `may_write_model_artifact=false`

解释：离线证据已经值得继续研究，但监督模拟样本和回读样本仍为空，所以任何结论只能用于学习优先级、观察队列和 detect-only / dry-run 样本收集，不能用于实盘或权限升级。

## Dataset1 学习心得

Dataset1 的核心价值不是“形态大全”，而是交易纪律、真实教训和执行约束。结构化统计显示：

- `trading_strategy.json`：买入策略 7 条、卖出策略 7 条、仓位管理 4 条、技术指标 5 条。
- `trading_constitution.json` / `原则库_Constitution.csv`：交易铁律 10 条。
- `trading_cases.json` / 案例库：成功案例 12 条、失败案例 14 条。
- `交易记录明细_Trading_Records.csv`：交易记录 39 条。
- `灯盏策略_完整数据.json`：低位强势、强制分歧点、5 日均线、跌破买入日阴线最低价止损等规则。

最重要的纪律：

- 买入不是越早越好，必须等启稳、均线支撑或站回确认。
- 第二笔加仓是高风险动作，不能因为第一笔想法正确就提前加。
- 大涨之后先轻仓或分批止盈，不能把浮盈当成确定收益。
- 弱开、低开不修复、跌破保护位时，卖出纪律优先于幻想反包。
- 计划执行失败本身应成为训练样本，不能只记录行情判断对错。

我对 Dataset1 的质疑：

- 成功案例和失败案例样本数都很小，不能直接推导稳定胜率。
- 个人交易记录容易带有幸存者偏差和记忆偏差，需要用历史 K 线实例补证。
- “强势股”“低位”“启稳”必须变成可计算字段，否则模型会学成模糊口号。
- “跌停价补仓”必须被重新审查：在 T+1、跌停不可卖、流动性不足时，它可能放大隔夜风险。

## Dataset2 学习心得

Dataset2 的核心价值是量价、筹码、竞价、分时和风险规则的弱标签库。结构化统计显示：

- 主数据集 `all_training_patterns.jsonl`：225 条规则。
- 动作标签分布：`REDUCE_OR_EXIT=64`、`SIM_BUY_CANDIDATE=63`、`WAIT_CONFIRMATION=59`、`HOLD_OR_TRAIL=19`、`AVOID_OR_WAIT=11`、`RISK_ALERT=6`、`NO_TRADE=3`。
- 周期分布：`daily=108`、`intraday=84`、`daily_3bar=12`、`intraday_orderbook=10`、`auction=7`。
- 规则来源覆盖：牛紫霞分时/量价/竞价资料 120 条、紫霞 PPT 57 条、量价交易宝典 24 条、做 T 资料 22 条、安全边界 2 条。
- `risk_controls.json` 明确 `simulation_and_training_only`，禁止直接实盘。

最值得吸收的规则族：

- 低位单峰密集、低位向上突破、底部放量上涨、放量突破阻力位：可作为候选池扩张信号。
- 上涨途中缩量回调、缩量小阴小阳、试盘后回踩：更适合等待确认，而不是立刻买入。
- 顶部放量滞涨、放量大阴、炸板、高位高换手、分时拉高出货：应优先降权、减仓或风险提示。
- 竞价、盘口、分时规则只适合交易时段确认；没有真实盘口和窗口验证时不能触发动作。

我对 Dataset2 的质疑：

- 它现在是教学规则库，不是历史监督样本；缺少 `signal_date`、`stock_code`、`entry_price`、`exit_price`、前瞻收益和回撤。
- `SIM_BUY_CANDIDATE` 只能表示“可以观察”，不能等同于买入信号。
- `risk_level` 仍有 `low_to_medium`、`medium_to_high`、`medium_high` 等非统一值，训练前必须规范化。
- `NO_TRADE`、`RISK_ALERT` 样本太少，若直接训练分类器，模型会偏向买入/卖出候选。
- 部分 `observable_features` 仍有字符串化列表，如 `"['大阳线']"`，会污染特征聚类。
- 大量规则缺少 `invalidation_conditions`，这会让模型只学会“什么像机会”，不会学会“什么时候失效”。

## 外部专业知识吸收

### A 股交易机制

上交所交易机制说明显示，A 股买入申报通常以 100 股整数倍，A 股最小价格变动单位为 0.01 元，主板 A 股日涨跌幅通常为 10%，风险警示股票为 5%，科创板股票日涨跌幅为 20%。上交所还说明连续竞价按价格优先、时间优先撮合。

对策略的影响：

- 所有模拟和回测必须按 100 股、0.01 元 tick、涨跌停、ST 风险警示、科创板 20% 限制处理。
- 涨停附近信号不能假设一定能买入，跌停附近也不能假设一定能卖出。
- T+1 与涨跌停叠加时，隔夜风险比普通回测更大。

### 成交与滑点建模

QuantConnect / LEAN 的 reality modeling 文档强调，滑点是预期成交价与实际成交价的差异，受交易引擎延迟、券商连接和市场波动影响；fill model 决定订单以什么价格和数量成交，并可结合 spread 和 slippage。

对策略的影响：

- 离线收益超过 20% 不能直接作为模拟/实盘收益预期；必须加入成交模型、滑点、涨跌停、流动性和部分成交。
- 站回确认策略如果经常发生在放量冲刺时，真实成交价可能显著差于回测价。
- 顶部放量、炸板、盘口撤单等规则应进入 fill risk，而不只是 pattern risk。

### 金融机器学习验证

RiskLab AI 对金融交叉验证的总结强调，金融数据常常不是独立同分布，反复使用测试集会产生选择偏差，训练和测试共享信息会造成泄漏；解决方向包括 purging 和 embargo。

对策略的影响：

- Dataset2 不能随机切 train/test；必须按时间切分、walk-forward、必要时做 purging / embargo。
- 同一只股票连续几天的样本高度相关，不能被当成完全独立交易。
- 参数优化必须看每个时间折叠表现，而不是只看总收益。

## 融合后的策略优化方向

### 1. 把“发现形态”和“允许动作”拆开

Dataset2 负责发现形态，Dataset1 负责约束动作，系统只输出候选评分、解释和样本收集优先级。

建议分层：

- `pattern_candidate_score`：量价、筹码、分时、竞价形态。
- `discipline_score`：是否买早、追高、弱开、未启稳、未到卖点。
- `execution_feasibility_score`：涨跌停、流动性、盘口、窗口验证、T+1 风险。
- `risk_override`：顶部放量、炸板、高位高换手、分发风险、跌破保护位。

### 2. 对站回确认策略继续做分阶段验证

当前训练摘要显示离线 20% 目标线有强证据，但监督样本为 0。此前 run 70 / run 71 已提示：`dataset1_stabilized_reclaim` 的高收益里混有风险机会和分发风险。

下一步不能放宽交易，而应分层：

- `follow_through`：扩样本，验证是否能稳定 20%+。
- `risk_mixed`：测试分发风险过滤、高波动板块过滤、强站回过滤。
- `stabilization`：继续观察，不提升仓位。

### 3. 增加 T+1 与隔夜风险惩罚

凡是买入后当天不能卖出的策略，都必须显式计算：

- 买入日收盘到次日开盘缺口风险。
- 次日低开不能及时卖出的风险。
- 跌停不可卖风险。
- 模拟计划是否需要隔夜持仓。

这会直接约束“早盘冲高回落”“分时追涨”“低开诱空承接”等日内规则。

### 4. 增强退出纪律权重

Dataset1 最大的价值是提醒：卖点执行不佳会吞掉判断收益。

卖出/减仓规则应在评分中具有更高优先级：

- 大涨分批卖。
- 涨停炸板先减。
- 高位放量滞涨先降权。
- 弱开不修复先保护。
- 跌破保护位先退出。
- 未按计划执行写入复盘样本。

### 5. 训练前先做数据清洗和实例化

Dataset2 训练前最小清洗任务：

- 统一 `risk_level` 枚举。
- 修复字符串化列表。
- 补齐 `evidence_summary`、`trigger_conditions`、`negative_filters`、`invalidation_conditions`。
- 扩充 `NO_TRADE`、`RISK_ALERT`、`AVOID_OR_WAIT`。
- 增加 `evidence_level`：原文规则、人工整理、回测验证、样本外验证、监督 dry-run。

实例级数据集字段建议：

```text
pattern_id
signal_date
stock_code
as_of_timestamp
feature_snapshot
action_label
forward_return_1d/3d/5d/10d
max_favorable_excursion
max_adverse_excursion
drawdown
turnover_rate
volume_ratio
limit_status
benchmark_return
split_tag
```

## 本轮结论

当前正确姿态是：

```text
Dataset2 找形态
Dataset1 管纪律
专业交易知识补成交与验证缺口
offhour / shadow / backtest 提供研究证据
supervised dry-run / readback 才能提供模拟执行证据
```

本轮我更愿意质疑三个看似乐观的点：

1. 离线收益很高，不代表真实可成交。
2. 站回确认有效，不代表所有阶段都有效。
3. 买入规则丰富，不代表系统已经会卖。

下一步建议：

1. 优先收集监督 `detect_only -> dry_run_screen -> readback` 样本，补齐 20 个 dry-run 和 20 个 readback 缺口。
2. 对 `dataset1_stabilized_reclaim` 做 phase/context split 后的过滤实验。
3. 把三维通信、沃尔核材、大族激光、乐凯胶片等 Dataset1 案例转成阶段卡。
4. 清洗 Dataset2 风险枚举和失效条件，在清洗前不做直接训练。
5. 将交易策略评分保持为 `candidate_learning_priority_only`，不写生产模型，不改规则文件，不启用实盘。

## 外部参考

- Shanghai Stock Exchange, Trading Mechanism: https://english.sse.com.cn/start/trading/mechanism/
- Shanghai Stock Exchange, Trading Rules of Shanghai Stock Exchange (2023 Revision): https://english.sse.com.cn/start/sserules/stocks/trading/c/10644064/files/7d100419dcca456b97cabaf2dfd3b904.pdf
- Shenzhen Stock Exchange, Trading Rules of Shenzhen Stock Exchange: https://docs.static.szse.cn/www/enSzhk/introduction/news/W020181124399984974002.pdf
- QuantConnect, Slippage Models: https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/slippage/key-concepts
- QuantConnect, Trade Fills: https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/key-concepts
- RiskLab AI, Cross-Validation in Finance: https://www.risklab.ai/research/financial-modeling/cross_validation
