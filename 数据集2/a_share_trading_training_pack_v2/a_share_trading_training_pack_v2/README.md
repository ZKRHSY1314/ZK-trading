# A股训练数据集与策略集 v0.2.0

生成日期：2026-05-31

本包把本轮上传的三份资料和上一轮已整理的《量价交易宝典》合并为可供软件学习的结构化数据集。

## 文件说明

| 路径 | 用途 |
|---|---|
| `dataset/all_training_patterns.jsonl` | 主训练数据集，一行一个策略/形态/风控规则 |
| `dataset/new_sources_training_patterns.jsonl` | 本轮新增资料规则，不含上一轮 legacy |
| `dataset/all_training_patterns.csv` | 人工查看和二次标注用表格版 |
| `dataset/instruction_tuning_examples.jsonl` | LLM 指令学习样本 |
| `dataset/rule_classification_examples.jsonl` | 规则分类/监督学习样本 |
| `strategies/strategy_set.json` | 可供规则引擎读取的策略集 |
| `strategies/risk_controls.json` | 全局安全边界和训练约束 |
| `schemas/pattern_schema.json` | 主数据集 JSON Schema |
| `schemas/event_feature_schema.json` | 行情事件特征建议 schema |
| `codex/a_share_rule_engine_reference.py` | 只读规则引擎参考实现 |
| `codex/codex_import_prompt.md` | 给 Codex 导入项目的提示词 |
| `docs/source_coverage.md` | 来源覆盖和规则数量统计 |
| `docs/strategy_cards.md` | 人类可读策略卡片 |

## 重要边界

这些数据是从教学资料抽取出来的**规则知识库 / 弱标签训练集**，不是经过历史行情回测验证的盈利模型。所有 `action_label` 都被限制为模拟候选、风险提示或等待确认，不能直接触发实盘交易。
