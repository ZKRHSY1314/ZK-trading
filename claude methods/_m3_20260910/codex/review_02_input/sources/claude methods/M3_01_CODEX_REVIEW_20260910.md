# M3-01 首轮独立验收：需要修正

日期：2026-09-10。实现者：Claude（既有 fork）；独立复核：Codex。**结论：首单交付齐全，基础合成测试通过，但标签契约尚未通过技术验收，不冻结为真实案例生成规则。M3 继续执行。**

## 验收对象和实测

- Claude 清单：`_m3_20260910/claude_01/artifact_manifest.json`，SHA-256 `428bb425661239de755dca6ac49e5128a923f8b90ebdb19e1c85d404e67a5147`。
- 模块：`backend/app/research/m3_labels.py`，SHA-256 `6a0590cf2dd9b7acbc9421c818e558e24d6c2877175c8a903d47dab375a99065`；策略版本 `0.1.0-draft`，policy hash `ea0f7630acc0c5175bab3b849eac606806a82b8ada53cd94dd714a219f1164e2`。
- 交付测试：SHA-256 `efa2e21cb70b70fbd0c39e3e4908a7a24f9837bb45889858979f6a99f09f0ab2`。8 个交付文件及 24 个声明引用的文件逐字节匹配；完整交付与协调状态快照保留在 `_m3_20260910/codex/review_01_input/`。未来协调状态的正常变化不改写该历史快照。
- 2026-09-10 06:32 UTC，在限定写入目录、禁止 SQLite/网络/子进程的运行器中独立复跑：Claude **41/41 PASS**，退出码 0，3.248 秒；Codex **18 个方法中 2 个通过、16 个未通过**，退出码 1，0.281 秒。unittest 报告 `failures=19`，因为一个方法的 4 个子场景分别失败；这不代表 19 个独立问题。
- Codex 检查源 `_m3_20260910/codex/test_independent_contract.py`，SHA-256 `69ffd819da5cf404e058b39e933dbfb0140b7e4bd2e79142ce1fa52695334cd6`。全部人工构造数据均为测试材料，实际案例数仍为 0。两个通过项是重复 cutoff 的拒绝与迟到基准数据降为 unknown，说明这些边界已有效实现。

实际执行命令（PowerShell）：

```powershell
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\codex\run_offline_review.py' 'D:\codex-A股交易\backend\tests\test_m3_labels.py' 'D:\codex-A股交易\claude methods\_m3_20260910\codex\review_01_claude_tests'
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\codex\run_offline_review.py' 'D:\codex-A股交易\claude methods\_m3_20260910\codex\test_independent_contract.py' 'D:\codex-A股交易\claude methods\_m3_20260910\codex\review_01_independent_tests'
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\codex\verify_preservation.py' 'D:\codex-A股交易\claude methods\_m3_20260910\codex\preservation_review_01.json'
```

前两项 `execution.json` SHA-256 分别为 `15d3b8ee82d23134e73c9013414d0b8399135acf2e3d0bd9bb48e1af24d4a83c`、`1c1b289f7efd7db2e03516298809543204b4f50700ea14d11f9b09e8f273b562`；对应 stderr 保留每条断言。运行期间模块/测试前后哈希一致，无被拒绝的运行时访问尝试。

保全检查退出 0：316 个既有跟踪文件、16 个生产文件位置、31 交付/479 传递/45 Claude 输入/14 输出/1 报告/137 采集计数输入/18 M2 收口文件全部匹配。回执 SHA-256 `de73a20134a732ae47db41757852ad575358f3c0cc04c6951a7ab681badb85f7`。这是字节与状态验证，不是生产 SQLite 查询。M2 数据、旧 FAIL、既有知识和标签未改变。

## 已复现的问题

行号对应上述固定模块，不跟随后续修订。

| 编号 | 优先级及位置 | 触发条件、影响与修正要求 |
| --- | --- | --- |
| R1 | P1；`match_controls:1143` | 同一对照记录复制 5 次，或同一证券提供 5 个邻近日，均得到满足 3–5 个对照的结果；不同 policy hash 的对照也被选入。必须按证券及案例版本去重、拒绝冲突重复，校验同一策略/范围/切分/截止口径，不能靠列表长度满足目标。 |
| R2 | P1；`ReviewRecord:1235`、`attach_review:1255` | 两个没有任何证据引用的 reviewer 字符串可得到 independently_reviewed；为案例 A 构造的审核对象可直接附到 B。需要绑定不可变案例内容 hash、episode id、policy、证据指纹和真实审核来源。代码不能证明某字符串确为一次独立审核，协调层仍须记录实际两次工作。缺失证据不能计数。静态复核还发现计数字段未联动 universe、holdout、有效对照与 consensus 类型；应提供明确区分库内记录数和合格正例数的计数口径，保持 disputed 可见。 |
| R3 | P1；`input_fingerprint:589`、`generate_labels:925`、`policy_document:1357` | 改变基准使 regime 改变，或改变证券背景使 phase 改变，episode id 仍相同。当前 record_hash 能反映部分内容变化，但匹配/审核只使用 episode id，未强制验证内容版本。必须把全套实际决策输入纳入身份或强制复合身份，防止审核错绑和覆盖。此外，修改 policy_document 返回的字典会实际改变标签，policy hash 却保持旧值；导出必须隔离，运行规则必须与声明 hash 一致。 |
| R4 | P1；`SecurityContext:375`、`label_regime:778` | corporate_action_status='KNOWN' 非法枚举被接受并绕过 known 分支；coverage=True/NaN/1.5/-1 均未被拒绝，其中 NaN/True/超界值可形成正常 regime。完整校验证券背景、数值、枚举、日期与布尔类型，并保留非价格事实的来源及可见时间。缺失覆盖信息应显式 unknown，而不是没有告警即当正常。 |
| R5 | P1；`_quality_gates:703` | 删除 decision_date 当天价格后，前一日价格仍可被标为当天 candidate。必须区分当前缺失、已证明停牌、非交易日和真正当前行情；没有当天完整证据不能生成确定的当天选择标签。交易日与 episode 连续性使用注入日历，不能用 7/20 个自然日近似后直接计为有效独立案例。 |
| R6 | P1；`label_position_event:875` | 已知除权在持有区间内，phase 已降为 indeterminate，价格比较仍产生 stop_event；reference_date 早于 entry_decision_date 也被接受。需验证位置状态来源/日期/可见时间/参考价依据，在价格基准不可靠时返回明确的 unknown/no-trade 复核状态，不能声称未复权价格已证明止损或止盈事件。 |
| R7 | P2；`build_episodes:1058`、`effective_decision_dates:1097` | phase 相同而 selection 改变时，selection_at_end 仍保留首项值。案例应保存真实末项、候选资格变化、连续性及最短持续期的确立时间；不能用后来延长的 episode 回写早期决策，不能把同一连续过程拆成多个“独立正例”。独立计数须按区间重叠/依赖组与日历验证，不凭函数硬编码 0 或自然日近似充当最终审查结果。 |
| R8 | P1；`guard_final_holdout:1335` | 将用途误写为 target_counts 时仍返回 holdout_protected=true；调用方若遗漏辅助 guard，匹配/审核计数也不受保护。用途必须用白名单，未知用途拒绝，病例集合的准入与计数流程必须实际调用切分保护。 |

R3 的 identity 反例不表示必须采用某个特定字段布局；可通过完整 decision fingerprint，或强制 `(episode_id, record_hash)` 复合引用修正。关键是所有消费路径都不能接受同一 id 下被替换的证据。审核附件不应悄悄使原始 record_hash 失效；原始标签与追加审核账本应有清晰的各自 hash 边界。

## 初始策略选择的复核意见

这部分是尚未采纳草案的设计评审，与上表已复现实现缺陷区分。

1. 250 根位置窗口、20/60/120 根收益窗口、原草案的阶段阈值、20 日失败/分布观察、流动性绝对分档、基准 ±5% 方向代理可保留为 **未拟合语料的研究假设**；不以凑足 50 个正例为由调阈值。未知公司行动仍可产生明确标注条件和不确定性的行为代理，但不得解释为已验证的经济收益或隐藏参与者事实。
2. 不采用 ±10 个交易日中可位于正例之后的对照匹配。独立反例确实选中了下一日对照；为明确截止口径，新版采用**同一 decision_date、同一策略、同一 split、同一 mode 与预先声明的日内决策时刻、同一流动性带和同一基准大类**。对照来自不同股票，3–5 只；不足则 unmatched。保持原窗口方案的提案证据，不伪称旧规则已经被接受。
3. 草案分期 development=2023-09-04..2025-03-31，validation=2025-04-01..2025-12-31，final_holdout=2026-01-01..2026-09-04 可作为新版初始分期，待修正后的契约一并冻结。真实案例初始构建只用 development；validation 后续单独只读验证，final holdout 不用于挑规则、凑数或反复看图修规则。本轮没有读取这些区间的真实价格来选择阈值。
4. 日历、证券属性、市场覆盖等也属于输入证据；strict 模式不能仅因价格字段 available_at 合规就声称全记录 PIT 合规。M2 仅能支持明确 retrospective 的可复现假设，training_eligible 继续为 false。
5. 不能把所有 M2 公司行动信息一律记为缺失。冻结的 `r06_basis_unit_controls.json` 及其证据支持 SH600011 的 3 个、BJ920000 的 6 个已知现金事件（含暖启动期事件）；上市日期也在已冻结清单/资格记录中。这是已知事件的部分集合，不是完整公司行动登记。后续读取器应携带这些事件、原始证据与实际观察时间；其他属性或无事件期间仍可能 unknown。不得在本轮重新采集或默认 none_verified。
6. 需纠正交付说明的“两处 py_compile 产物”边界：虽报告已移除，后续全部用 -B 与无写入的 compile/AST 检查；不要再次创建授权路径外的缓存。保全实测未发现既有数据/源码改变。

## 下一步

由同一 Claude 会话完成单一修正任务 `M3-01-R2-CONTRACT-FIX-20260910`，新交付写入 `claude_01_r2/`；原 `claude_01/`、本次快照和失败回执保留。Codex 继续独立复核后才放行真实案例读取。15 分钟巡检继续，M3 未完成，M4 未启动。

Claude: Read M3_01_R2_CLAUDE_TASK_20260910.md and address the consolidated findings in a new version. Preserve the original delivery and every failure receipt. Deliver the revised pure contract and meaningful synthetic regressions at ready_for_review; do not start real-corpus extraction or claim M3 completion.
