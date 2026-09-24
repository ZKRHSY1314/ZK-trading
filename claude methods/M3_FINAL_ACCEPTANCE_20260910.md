# M3 最终技术验收与证据限制

日期：2026-09-10。**M3 标签、冻结读取、实际逐案审阅和案例库合并已完成技术验收；至少 50 个双审正例的研究目标未达成，训练准入不通过。** 本轮按原目标中“证据不足如实报告”的分支收口，不把工程完成写成样本达标。

固定开发总体已穷尽盘点：最多只有 32 个具备 3–5 个合格对照的阶段；实际两名 agent 审阅后 32 个均有分歧，双审正例为 **0/50**。继续使用同一冻结总体和规则重跑不能补足目标。未调整阈值、扩大总体、挪用留出期、伪造审阅或凑合成正例。

## 已完成的交付

| 阶段 | 实际结果 | 验收 |
|---|---|---|
| M3-01 标签规范与内核 | 候选/非候选、五类阶段、入场资格、止损/退出/不交易、市场状态及流动性；版本化截点、输入和审阅契约 | [M3-01 R3 验收](<D:/codex-A股交易/claude methods/M3_01_R3_CODEX_REVIEW_20260910.md>) |
| M3-02 冻结读取与完整盘点 | 50 股票、2 指数；2023-09-04 至 2025-03-31，378 交易日；17,554 决策记录 | [M3-02 验收](<D:/codex-A股交易/claude methods/M3_02_CODEX_ACCEPTANCE_20260910.md>) |
| M3-03 实际审阅与案例库 | 每名 agent 实际审阅 32 个阶段、127 个对照和 8 个诊断；保留原意见与争议 | [M3-03 验收](<D:/codex-A股交易/claude methods/M3_03_CODEX_ACCEPTANCE_20260910.md>) |

可直接查阅 [逐案例索引](<D:/codex-A股交易/claude methods/M3_CASE_LIBRARY_INDEX_20260910.md>)；每项链接到原始截点材料、双方原始意见及合并账本。

## 数量与研究准入

| 口径 | 数量 / 状态 |
|---|---|
| 开发区间潜在股票日期键 | 18,900 |
| 尚未上市、按声明排除 | 1,346 |
| 当日价格 / 当日停牌 / 未解释缺失 | 17,402 / 152 / 0 |
| 全部阶段 / 吸筹代理阶段 | 1,626 / 342 |
| 达到三个连续交易日前缀 | 225；另 117 未达到 |
| 前缀代表日非候选 | 85 |
| 代表日候选 | 140：108 对照不足，32 有 3–5 个合格对照 |
| 已匹配阶段的依赖组 / 股票数 | 23 / 18 |
| 全部匹配对照 | 127 个不同日期记录，37 只股票 |
| Codex 原始意见 | 31 正例、1 不确定 |
| Claude 原始意见 | 0 正例、14 负例、18 不确定 |
| 合并账本 | 32 争议、0 一致通过、0 双审正例 |
| 最终合格正例的依赖组 / 对照使用 | 0 / 0 |
| ≥50 正例目标 / 训练准入 | 未达成 / 禁用 |

意见分歧集中于冻结代理与较严格形态解释的差别；两者都不构成隐蔽资金行为的真值。当前没有双审同意的正例，不应把 Codex 的单方 31 个正例用于已达标监督训练。负例、不确定、失败阶段和质量诊断均保留，未强制二值化。

## 验证证据与可用范围

标签阶段已实际通过 105 项交付、24 项消费者边界、8 项独立数值检查；读取器实际通过 20 项交付及 8 项额外边界/材料延伸检查。最终模块与测试文件哈希未改变，因此复用这些已封存运行结果，未用重复运行夸大数量。

真实来源对账覆盖 27,900 条含预热价格与 200 条停牌证据；独立来源重建复算全部 17,554 条最终记录，0 差异；全部 225 组截点材料、完整同日对照池及排序均已复核。这些自动复算与实际逐案审阅分别记录。合并后又用不调用标签/计数内核的核验程序逐条确认原字段与双方原条目，检查通过。

材料来自 2026 年捕获的回顾性历史数据，**strict_pit=false、training_eligible=false、review_only=true**。截点算法不看未来，不等于已证明历史时点真实可得。没有消费验证期或最终留出期价格。历史 ST、流通股本、换手、名称未知；公司行动只有两只股票的部分现金事件，其余覆盖未知。暖启动不足、上市证据等级和 BJ 单日例外继续限制使用。50 股票的日期覆盖不等于全市场覆盖。

止损、退出等有合成契约证明；本轮没有真实持仓、参考成交与订单证据，不能声称已实测真实退出或撮合。入场信号仍是未验证执行。种子三维通信不在固定总体，本轮未补造其案例。

生产 SQLite 没有连接或修改，没有替换旧数据/标签/知识、采集新行情、登录账户、资金或交易操作。最终 316 个原有跟踪文件、16 个生产文件位置及 M2 冻结证据均保全；原有工作区未提交变更保持原样。生成证据通过本地 Git exclude 排除，未暂存、提交或推送。

## 收口状态

机器回执明确使用 `M3_technical_complete=true`、`research_target_met=false`、`M3_complete=false`（严格的全部研究准入意义）、`training_eligible=false`。本轮已完成有限总体的研究材料交付与不足举证，状态为 `technically_closed_evidence_target_not_met`；没有隐含扩大授权，也不会自动重派同一批材料。

本验收与收口回执落盘后，结束原有 15 分钟 M3 巡检；实际暂停结果保存于独立运行回执。Claude 已完成并处于 Idle。M4 未启动。若后续继续，应先明确是修订有版本的研究假设、补充来源证据，还是独立启动 M4 的合成引擎验证；不能沿用本次成果宣称历史预测或收益有效。

收口证据：[completion.json](<D:/codex-A股交易/claude methods/_m3_20260910/codex/final_acceptance_01/completion.json>)；全链条哈希：[evidence.json](<D:/codex-A股交易/claude methods/_m3_20260910/codex/final_acceptance_01/evidence.json>)；巡检运行状态：[automation_closeout.json](<D:/codex-A股交易/claude methods/_m3_20260910/codex/final_acceptance_01/automation_closeout.json>)。

Claude next-stage instruction: The bounded M3 implementation and evidence review are technically closed, while the 50-positive research target and training gate remain unmet. Retain all frozen versions and dissent. No new task is dispatched. Remain idle; do not relabel, recapture, train, or start M4 without a separate explicitly scoped instruction from Codex under user authorization.
