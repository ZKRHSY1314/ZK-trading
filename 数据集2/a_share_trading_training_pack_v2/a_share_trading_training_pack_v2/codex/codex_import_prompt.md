# Codex 导入提示词：A股训练数据集与策略集 v0.2.0

你正在开发“ A股 AI 交易驾驶舱 ”。请把本包作为**规则知识库 / 弱标签训练集 / 模拟信号解释库**导入。

## 必须遵守

- 不允许直接实盘下单。
- 不允许绕过风控。
- 不允许自动修改实盘配置。
- 所有策略输出只能是候选评分、概率判断、风险提示或模拟交易计划。
- 在没有回测、样本外验证、人工确认前，不得将任何规则升级为实盘规则。

## 推荐导入顺序

1. 读取 `schemas/pattern_schema.json` 和 `schemas/event_feature_schema.json`。
2. 读取 `dataset/all_training_patterns.jsonl` 作为主知识库。
3. 读取 `strategies/strategy_set.json` 作为规则引擎输入。
4. 读取 `strategies/risk_controls.json` 覆盖任何高风险输出。
5. 使用 `codex/a_share_rule_engine_reference.py` 做只读候选评分测试。

## 任务建议

- 先写单元测试，确认每个 `action_label` 都不会触发真实交易。
- 为每个 pattern_id 回测 1/3/5/10 日后续表现、最大浮盈、最大浮亏、胜率、盈亏比、期望值和最大回撤。
- 将结果写入 `memory/strategy_performance/{strategy_id}.json`，再决定是否进入模拟盘观察。
