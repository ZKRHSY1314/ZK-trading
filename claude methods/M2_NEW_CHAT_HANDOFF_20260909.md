# M2 新对话交接说明

记录日期：2026-09-09（Asia/Taipei）。这是上下文交接，不是新授权，不是验收通过声明。接手时须核对实时文件、协调状态和自动化状态，不能把本文件的快照当成永远有效。

## 1. 用户目标与分工

项目：`D:\codex-A股交易`。

- 用户希望继续解决 M2，最终取得经过验证的三年数据集，而不是无限修订文档。
- **Claude 实施，Codex 独立复核。** 向用户解释用中文；每次验收结尾附下一阶段的英文指令。
- 用户已明确授权 Codex 在现有范围内持续离线分析、必要的既有文件计算和纠错，并通过屏幕界面向唯一 Claude 会话派单，不必每轮重复请求确认。
- 用户希望尽可能不停；确因新证据、权限或无法恢复的问题必须整体停止时，邮件通知 **9306443@qq.com**。邮件发送已获授权，但须验证已发送结果、记录消息 ID、对同一原因去重。普通巡检和任务交接不是必须发送停止邮件的事件。

## 2. 首先阅读的文件

以下路径均相对于项目根目录：

1. `AGENTS.md`
2. `CODEX_CLAUDE_COLLABORATION.md`
3. `claude methods/THREE_YEAR_RESEARCH_EXECUTION_GOAL.md`，尤其 M2 定义及 Section 15 当前说明。
4. `claude methods/_m2_codex_review/m2_claude_coordination_state.json`，以 `current_task` 和对应 `instruction_file` 确认唯一派单，不凭旧自动化提示猜任务。
5. `claude methods/M2_BOUNDARY2_EVIDENCE_REQUIREMENTS_CODEX_REVIEW.md`（最近一份待闭环审查）。
6. 两份当前待复核交付：`claude methods/M2_BOUNDARY2_EVIDENCE_REQUIREMENTS_DRAFT.md`、`claude methods/M2_REMAINING_DEPENDENCY_DECISIONS.md`。

历史背景按需查阅：`M2B_R2ABC_CODEX_REVIEW.md`、`M2B_REAL_SOURCE_VERIFICATION_REQUEST.md`、`M2_PILOT_AUTHORIZATION_REQUEST.md`、`M2B_P1_BASIS_CONTRACT_PROPOSAL.md`、`M2B_NEXT_STAGE_DECISION_MEMO.md`。历史文本里的“尚未实现”“等待授权”可能已被后续记录限定，不能整段当成当前状态。

## 3. 用户刚提出的关键疑问：数据源不是本地同花顺吗？

**是，项目日常行情的代码默认策略是同花顺优先；当前 M2b 验证的却是 AkShare/Sina 历史数据路径。两者必须分开解释。**

本次直接读取当前代码确认：

- `backend/app/config.py:35`：`daily_bar_source_policy` 默认 `tonghuasun_first`。这是代码默认值，本轮没有调用服务确认实际生效配置。
- `backend/app/data/daily_bar_cache.py:170`：该策略先取 `tonghuasun.local.quotes.candle`，之后可回退 Sina、Tencent、AkShare 其他路径；优先不等于只用同花顺。
- `backend/app/data/tonghuasun_provider.py:209-247`：`get_daily_bars` 把请求数限制在 500，起止时间填 None，最终取尾部 `limit` 行。此项目适配器未实现按日期分页。
- `claude methods/M2_PILOT_AUTHORIZATION_REQUEST.md:76,98`：旧方案因此把同花顺从本次历史回填路径排除，转而验证 Sina；三年研究 728 个交易日加预热 250 日，共需 978 日。

**重要纠偏：500 根限制是当前项目适配器的实现事实，不能据此断言同花顺客户端、插件或底层接口只能提供 500 根历史。当前 Sina 的 capability FAIL 也不等于本地同花顺整体不合格。**

用户没有在这次追问中授权采集、数据库访问、切换数据源或改生产代码。新对话应优先开展针对性的**已有本地代码/接口文档静态复核**：判断底层同花顺接口是否已有起止日期、历史分页或其他足以覆盖目标区间的机制，以及当前适配器为何没有利用它；区分“接口声明支持”“项目已实现”“真实数据已验证”。若静态证据不足，列明最小待验证问题，不能擅自发请求或读取客户端数据库。

这项同花顺长历史能力复核**尚未执行**，也尚未向 Claude 派发。不要把上一轮的建议写成已经完成的结论，更不要继续默认只有 Sina 路径可行。

## 4. M2 当前所在位置

- M1 数据契约与 staging 验收门禁：技术验证通过，保留。
- M2a 离线试点程序：合成数据验证通过，保留；不等于真实回填通过。
- **当前仍在 M2b：历史数据源验证、价格口径证据及后续试点前置条件审查。**
- 52 标的真实试点未启动；三年目标数据集尚未完成回填验收。
- 最近几轮主要完成证据分析和验收条件澄清，没有推进真实回填。不能按文档数/测试数给 M2 完成百分比，不能承诺还需几小时。

M2 的实际目标见 goal:173-185：先在 staging 或副本回填；记录前后清单、计数、哈希、覆盖、拒绝记录及来源；研究视图不含 ERROR 伪日期或重复业务键；整个区间复权一致；如另获生产迁移授权，迁移应可恢复并经独立核对。不得缩小这个目标来宣布完成。

目前不变的状态：**P1 open；U-6 deferred；所有 eligibility false；当前已审查 M2b source capability FAIL；历史 EV6 失败保留；两次边界 1b 采集授权均已消耗。** 新运行只能产生新结果，不能抹掉历史失败；也不能仅为了清掉 EV6 就要求第三次采集。

## 5. 当前 Claude 派单和未验收交付

唯一实施会话：Claude Windows 应用 → `ZK-trading` → **`Fable 5.1 project advice (fork)`**。原始同名非 fork 会话只读，不新建或并行启动第二个写入者。

当前任务 ID：`M2-BOUNDARY2-REQUIREMENTS-CORRECTION-20260909`。

完整指令：`claude methods/M2_BOUNDARY2_EVIDENCE_REQUIREMENTS_CODEX_REVIEW.md`。

允许 Claude 写入的范围仅为现有两份文件：

- `M2_BOUNDARY2_EVIDENCE_REQUIREMENTS_DRAFT.md`
- `M2_REMAINING_DEPENDENCY_DECISIONS.md` 中对应的当前状态/决定说明。

上次 UI 已确认 Message 219 可见，Claude 开始读取审查并响应。协调文件仍记录 `submitted_observed_running`；**本次交接没有重新观察 Claude 的完成界面**，所以不能据协调文件推断仍在运行，也不能仅凭文件更新断言任务完成。

本次交接读取到的最新 SHA-256（新修订已落盘，但尚未独立验收）：

| 文件 | SHA-256 |
|---|---|
| `M2_BOUNDARY2_EVIDENCE_REQUIREMENTS_DRAFT.md` | `205ae057fc2c3823f991e397a6389565f051551bae5a06859f31be5cfc750885` |
| `M2_REMAINING_DEPENDENCY_DECISIONS.md` | `8f0b8228ac3634167039c27eff24eca4833fafac33d7b24f652286710584e849` |

要验的四项实质问题：

1. **BQ-R1**：区分原始源返回日期、适配器返回日期、manifest/calendar/listing 定义的研究与预热应有键，以及实际可接受的 staging 键。指数接口返回全部历史不等于试点指数可以超出研究窗口；未知可用性不能缩减应有键。
2. **BQ-R2**：`unverified` 只能保留为审计事实，不能作为解除当前依赖价格口径的试点前置条件的替代选项；不能隐式推翻 U-1/U-2。
3. **BQ-R3**：C4 重复统计是在 decoded `in_window` 上计算，不能说它证明适配器删除了多少行；share-only 日期不当然是非交易日；52 减去 3 个样本是 49，不是 51；区分可观察覆盖事实与非必需的供应商内部因果解释。
4. **BQ-R4**：把已授权的非可执行需求分析真正完成，不再增加“要不要另写下一份草案”的权限循环；保留实际尚缺的证据、政策和操作条件；不缩小 M2 目标；不把局部未发现机制写成全仓库不存在。

下一次先检查文件稳定性及唯一会话状态，再复核这些点。不要重复发送当前任务；也不要为了同花顺新方向覆盖 Claude 正在修改的两份文件。完成/协调好当前派单后，再明确新任务的独立写入范围。

## 6. 已验证成果与证据位置

无需重新全量跑测试或重开已关闭问题：

- smoke 技术修正：历史记录为 182/182；独立 closure driver 49/49。旧 reviewer 的跨版本差异不能当成当前功能回归；也不能把这些测试数当源能力通过。
- P1 evidence-side module：`basis_record.py` 哈希 `0fda4f7e…`，测试文件 `51add34e…`，BR-R1…BR-R4 仅对已审查哈希关闭；没有 `eligible=true` 路径。
- G1 官方公司行动研究、G3 留存比值分析、U6 readiness/retained study，以及 reference lineage/cache write path/turnover/amount 四项静态审查已有有界技术结果。原报告和保留证据应只读。
- G1 有实际获授权的官方资料获取历史；G3/retained study 有离线计算历史。不能把整个工作流都说成“只读代码，从未获取或计算”。
- 最新四项审计文件：`M2B_REFERENCE_BASIS_LINEAGE_AUDIT.md`、`M2B_CACHE_WRITE_PATH_AUDIT.md`、`M2B_TURNOVER_DEPENDENCY_ASSESSMENT.md`、`M2B_AMOUNT_REPRESENTATION_AUDIT.md`；对应验收文件同目录。

最近独立快照：`claude methods/_m2_codex_review/boundary2_requirements_review_20260909_r1/`，冻结的是上一版被退回的两份文件；其中 `verification.json` 记录 26 个去重引用文件哈希（共 41 处引用）、91 个受保护文件、46 个 G1 文件核对无变化。

长期保护基线：`claude methods/_m2_codex_review/g3_ratio_codex_review_r2b_results.json` 的 `protected_before`；G1 对照冻结目录 `claude methods/_m2_codex_review/g1_review_20260909_r3_doc1/reviewed_delivery/`。不能用可变协调文件替代冻结证据。

goal/request 稳定哈希前缀仍为 `f8b699e5…` / `c39726d0…`。关于 U-1…U-5/U-7 的采纳及模块授权，必须保留 **Claude-reported, not independently verified by Codex** 的归属说明；既不能伪造授权收据，也不能推断“绝无授权”而重开已实施方案。

本次交接核对 Git HEAD：`73f266d`；暂存区为空。已有未提交工作不要重置、清理或提交。

## 7. 自动化与交接协调

自动化 ID：`claude`；名称：`M2 离线协作巡检`；周期：每 10 分钟。

**本次交接实读状态为 PAUSED。** 这覆盖此前聊天里“仍启用”的旧快照。本轮没有修改自动化，未核实它是由谁、因何暂停，不要编造原因。

它仍绑定旧 Codex 任务：`01a0804d-78a8-7403-85ff-78616de013c1`。本地配置位于 `C:\Users\Administrator\.codex\automations\claude\automation.toml`，只读检查；更新必须用 Codex 自动化工具，不直接改 TOML。

**先完成唯一协调者的交接，再恢复自动巡检。** 不要直接恢复仍绑定旧任务的 heartbeat，让旧/新 Codex 两边同时给同一个 Claude 派单。若用户需要在新对话继续自动巡检，先确认新对话目标并更新现有自动化，避免重复创建。新对话也不能把本交接说明当成已经恢复调度的证明。

邮件通知的授权与去重记录在协调 JSON 的 `email_notifications`。已验证连接器为 Gmail，记录发件账号 `zken93038@gmail.com`；发信只通知指定收件人，不附原始数据/敏感信息。发信前检查已发送记录，结果不确定先查询已发送邮件，再决定是否重试；不要谎称已发送。

## 8. 始终有效的边界与工具提示

没有新的采集、外部数据检索、数据库打开/提取/写入、生产实现/集成、服务操作、策略/数据集/知识库变更、政策采纳、门禁/标签/阈值/eligibility 变更、训练/试点/回填、Git 暂存提交推送或实盘授权。不要访问交易账户、令牌或凭据。

本地同花顺接口的静态能力复核可以按当前离线授权开展；实际调用接口、打开客户端数据库或修改适配器不能偷偷包含进去。生产数据和方法论、Codex/Claude 相关文件不得提交 Git。

屏幕操作使用 `computer-use` 技能，先读其 SKILL.md 及必需说明，再通过 `node_repl` 中 `@oai/sky` 操作。此前 Claude 窗口 ID 为 2689234，但接手时必须重新枚举；不盲用旧元素索引。普通联想屏保可以在确认后退出，不能把锁屏/登录当成普通屏保处理。检测到用户草稿、运行中任务或多写入者时不覆盖、不重复派单。

新对话的第一步应是读取本说明及当前协调文件、核实 Claude 的这轮交付，再把**本地同花顺长历史能力的已有接口静态复核**纳入下一项具体工作。不要先扩大 Sina 研究或请求第三次采集。
