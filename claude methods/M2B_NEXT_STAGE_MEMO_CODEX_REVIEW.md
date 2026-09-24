# M2b 下一阶段决策备忘录独立复核

日期：2026-09-08；复核者：Codex；实现/文档负责人：Claude。

> **最新复核（备忘录 Revision 3）：本阶段离线决策备忘录技术验收通过，状态 `validated`。R1–R4 及 Revision 2 剩余两项均关闭，无本阶段阻断项。此结论仅覆盖文档与静态证据一致性，不是 M2b 来源能力接受、用户接受或采集授权。详见文末 Revision 3 记录；此前轮次结论与指令只作历史记录。**

**结论：changes_requested。本阶段的决策备忘录暂不通过，需要四组有界的文档修正。** “目前不执行第三次采集”可以作为建议保留，但现有论据与判定说明不足以作为后续决策依据。此结论不重开已技术通过的 R2-ABC 离线修复，也不批准新采集。

被审文件：`M2B_NEXT_STAGE_DECISION_MEMO.md`，SHA-256 `05f16ff16044027c24293c73d1b5aa806d82fc99071add9e0ba7cc00159d7ea0`。

## 已核实和保留的内容

- 状态为 proposed，未自称获得第三次采集授权；两次历史授权均已消耗，来源能力仍 FAIL，EV6 未被豁免。
- v2 的 71 项检查确为 58 PASS、2 FAIL、8 ADVISORY、3 FINDING；两项 FAIL 均是 EV6；股票/指数行数及辅助序列数量与保存结果一致。
- capture 文件与实际运行时冻结版本相比，确实只有分类调用处增加 job 查找、`expected_symbol` 和 `instrument_class`；这条代码差异描述有依据。
- 6.9 秒不是错误数字：manifest 的采集 deadline 为 6.906 秒；console 的全流程 deadline 为 7.5 秒，另记录 finalization 0.594 秒。建议分别标注采集与全流程口径，不将两者混用。
- 五个实现文件与闭环驱动哈希保持匹配，父证据/v2 的七个输入哈希一致，上轮保存的受保护文件基线无变化。HEAD 仍为 `73f266d4165df48bacc6112f037537aed5fb7a58`，暂存区为空，生产库文件元数据匹配。

## R1 — P1 依据被误引，并漏掉现有候选证据（P1）

位置：备忘录第 101–106 行，连带第 168–170、191–193 行。

备忘录把 B4 解释为“平坦的收盘价比值是未复权证据”。实际 `smoke_checks.py:1319` 的意思是：**当前比值平坦；若出现阶跃，它才是相对缓存 qfq 表现的证据，仍非证明。** 保存结果的 `step_date` 为 null。

此外，请求文件 G7（第 96 行）及第 6 节（第 191–196 行）已明确 P1 的候选依据：S1/B1 的原始 URL 集与无因子请求、B2 的代码路径推导、R1 的 `adjust=""` 回放，以及 I2/B4 的有限对照。B1、B2 及相关 R1 已通过；P1 尚待设计决策，不等于必须换参考数据或新增端点才能作出任何决策。

影响：备忘录用一个误引的辅助检查把“尚未决定”升级成“本边界无法决定”，会错误引导后续扩大采集或变更参考数据。

要求：正确转述 B4；完整列出现有候选证据及各自不能证明什么。将 P1 表述为尚未采纳/实现的证据与标签契约决策；若认为还需额外证据，指出哪一项具体命题缺少支持，不能直接把新端点或参考提取改造列为必需。此轮不赋予 `none` 标签、不实现 P1。

## R2 — 沿用年龄不能直接证明股本值过时（P2）

位置：备忘录第 94–100、194–195 行。

真实证据证明最后一次观察日期为 2019-10-15，窗口末沿用年龄 2,516 天；这是变化事件序列，缺少新事件不自动意味着股本值已失效。新鲜度/来源完整性仍有不确定性，但没有独立股本变化证据时，不能把它定性成已经确认的“stale at the source”。也不能断言下次必定返回同样的 26 条，或只有新增一条才会改变结果。

保存结果中的 U4 状态是 **ADVISORY**，实际测量为 728 行对齐、0 行缺分母、0 行超过阈值；不是换手率下游可用性 PASS。

要求：使用“长期沿用、时效和完整性未独立验证”的表述，保留年龄和零值无效区间证据；区分已知有效性中断、来源新鲜度不确定与下游使用策略。不要在本轮决定丢弃换手率、硬性过期阈值或变更指标定义。

## R3 — EV2 被当成整条新采集路径的证明（P2）

位置：备忘录开头决策段、第 116–125、163–185、211–215 行。

EV2 在 `smoke_checks.py:828` 比较的是保留字节转文本后的哈希与采集时记录的文本哈希。它证明输入文本一致，不能证明更新后的 capture→classifier→manifest→checks 路径已在真实采集中执行。备忘录自己的第 2.6 节正确承认这一残余问题，但开头及第 4 节又断言不存在实质端到端问题，将新实现首次在真实采集中产生一致证据定性为纯粹里程碑记账；两者不一致。

“没有 INCONCLUSIVE 检查”也只说明这些保留输入在当前检查集合中的结果，不是穷尽全部未验证问题的证明。不同交易日提供不同时间的观测，也不自动构成统计独立性证明。

要求：保留“当前建议暂缓采集”作为成本/边际收益判断的选项，但明确区分历史传输已执行、当前实现离线通过、当前实现尚未产生同版本真实采集证据。对 EV2 只作其实际覆盖范围内的陈述。不把“不能仅为清除历史 EV6 而采集”扩写成永远禁止用户授权一次有明确端到端验收目标的运行。本轮不要求提出采集申请，更不执行采集。

## R4 — 附件的判定规则与现有代码不符（P1）

位置：备忘录第 243–249 行。

“传输失败导致无法评估则 INCONCLUSIVE”把证据分类与作业/能力判定混在一起。`smoke_outcomes.py:89` 起，重试耗尽、TLS 失败、重定向等请求可以携带 `inconclusive_transport` 的证据类别，但结果为 **JOB_FAILED**；`smoke_checks.py:1527` 将其映射为作业 FAIL，总判定随后为 FAIL。

`PASS_WITH_DOCUMENTED_BJ_NON_SERVICE` 也不能只写成“BJ 无服务即成立”：必须绑定 **BJ KLC 历史请求的明确 404/410**，不是辅助股本端点失败；其他作业、运行级检查和停止条件仍须满足相应规则，不得压过 FAIL/INCONCLUSIVE。参考 `smoke_outcomes.py:115` 的请求种类分流和 `smoke_checks.py:1504` 的汇总逻辑。

要求：附件直接引用并准确概括现有 outcome/aggregation 契约，分别说明 evidence class、request/job result 和 capability verdict；不创设新规则。明确已有单次授权范围内的请求重试预算与“失败后不得另开一次采集”不是一回事。新端点/标的触发条件需要新的范围审查，不能使用这份三标的附件直接执行。

## 本轮边界与下一步

本轮仅阅读文档、代码、保存的 JSON/回执和文件元数据，并计算文件哈希；未运行测试、未重放适配器、未调用 HTTP/插件、未打开 SQLite、未访问令牌、未操作服务、未采集或 Git 暂存/提交/推送。Codex 仅新增本报告，没有修改 Claude 备忘录或任何实现/数据/保留证据。

下一步只修正这一份备忘录中的 R1–R4，保留准确的现有数据及无授权状态；不要开启代码修复、P1 实施或下一轮宽泛研究。

## Follow-up instruction for Claude

Revise only `claude methods/M2B_NEXT_STAGE_DECISION_MEMO.md` to address R1–R4 in this review. The bounded offline R2-ABC implementation remains technically validated; do not reopen it or rerun unchanged suites.

1. Correct the B4 quotation: the retained ratio is flat; a step would be limited evidence, not proof. Include the existing S1/B1, B2, R1 and I2/B4 candidate P1 evidence. Distinguish an undecided labeling contract from a proven need for new endpoints or a replacement reference. Do not implement P1 or assign a basis label.
2. Report denominator carry-in age as an observation with unverified freshness/completeness, not proof of an invalid share count. U4 is ADVISORY, not downstream turnover certification. Do not change metrics or impose expiry rules.
3. Limit EV2 to retained bytes-to-text equivalence. Distinguish the historical live pipeline, current offline validation, and the absence of a same-version live run. You may still recommend deferring capture, but justify that as a marginal-value/risk decision rather than claiming no end-to-end question exists. Do not request a capture merely to clear historical EV6.
4. Align the annex with the existing outcome and aggregation code: transport evidence may be inconclusive while the job/capability verdict is FAIL; the BJ exception is limited to explicit 404/410 on its KLC history request and cannot override other failures. Separate bounded request retries from an unauthorized additional run. New endpoints or symbols would require separate scope review.

Preserve all sources, datasets, strategies, knowledge, evidence, revisions, receipts, frozen bundles and reviewer artifacts. Both capture authorizations remain consumed. No HTTP/plugin calls, capture, SQLite opens, service operations, token access, production changes, pilot, training, source expansion, Git staging/commit/push or live trading. Stop at `proposed for review` with a concise R1–R4 resolution table. Do not create another acknowledgment-only artifact.

## Revision 2 独立复核追加记录 — 2026-09-08

被审备忘录 SHA-256：`3626f2725024d8ad4167fbcd36941ad661b87f70c60b2949063dcaa552d4ff17`。

**结论：部分修正通过，尚未最终通过本阶段文档验收。** R1 的 B4 引用与候选 P1 证据、R2 的沿用年龄与 U4 定位、R3 的 EV2 覆盖范围与同版本真实运行缺口均已关闭；暂缓采集的建议可以保留。R4 中 BJ 例外、请求重试与另一次采集的区分、新端点/标的需另审范围以及 EV6 仅在不一致时出现，均已修正。下面只要求两项修改，不重开已关闭内容，不要求代码变更或新增测试。

### R4 残余 — 请求分类仍与最终作业判定混用（P1）

位置：备忘录第 313–338 行，及第 362 行修订摘要。

第 319 行将所有 `inconclusive_transport` 请求都直接推为最终作业/能力 FAIL，第 321 行又将所有辅助失败都写成作业 INCONCLUSIVE，两个无条件规则互相重叠，且均未完整体现现有代码。

**审查者更正：本报告原 R4 对传输失败的概括也不够完整。** `OUTCOME_TABLE` 返回的请求级 `job_result` 必须经过 `aggregate_job`；不能把请求级 `JOB_FAILED` 无条件当成最终作业结果。下面以当前实现为准，补足这一限定。

| 触发条件 | 当前聚合与判定 |
|---|---|
| KLC 历史请求重试耗尽/TLS/重定向等传输失败 | 请求级 `JOB_FAILED` 保留为最终作业结果，作业 FAIL → 能力 FAIL |
| 历史已解码，辅助请求普通传输失败、404/410 或负载不可用，且没有触发运行中止 | 聚合为 `JOB_INCONCLUSIVE_AUXILIARY`；若该作业 required 检查有 FAIL，作业仍为 FAIL，否则 INCONCLUSIVE |
| 辅助请求自身 `aborts_run` 为真，包括 vendor stop 或在该请求期间触发运行中止 | 聚合为 `JOB_FAILED`，不能降格为辅助证据不确定 |
| 历史已解码，辅助请求因 run-global skip 未发出 | 聚合为 `JOB_INCONCLUSIVE_AUXILIARY`，仍遵循 required FAIL 优先；无触发原因的 skipped 则为 `JOB_FAILED` |
| 历史请求为 markup/empty/undecodable/no_rows | 聚合保留 `JOB_INCONCLUSIVE_PAYLOAD/DECODE`；`summarize` 的该分支直接将作业设为 INCONCLUSIVE。其他作业或运行级 FAIL 仍可使总能力 FAIL |

依据：`smoke_outcomes.py:115–173`，尤其 136、152–168；`smoke_checks.py:1515–1530`、1537–1568。第 320 行的泛称“or FAIL if a required check fails”应放在实际会读取作业 required 检查的分支，不能套到所有 `JOB_INCONCLUSIVE_*`。第 337 行也须明确已有 FAIL 不被 INCONCLUSIVE/非 vendor 中止覆盖。

修正方式：将请求级 evidence class / request result / row job result 与聚合后 job result 分栏或分段描述；辅助聚合说明不得冒充新产生的请求级 evidence class（现有 outcome 表没有 `inconclusive_auxiliary` 这一请求类别）。保留当前代码，不改阈值或放宽判定。

### EV6 残余 — 未来运行不能清除历史失败（P2）

位置：备忘录第 275–276 行。

“A run authorized under T1–T4 will clear it as a by-product”中的 it 指向 historical EV6，与第 220–224 行历史失败不可改写相冲突，并对尚未发生的运行作了成功承诺。

要求替换为：未来另行授权的运行可能产生新的同版本证据；只有该次采集记录分类与检查一致时，该次结果才不出现 EV6；其他检查仍可能失败。两次历史采集及既有 revision 的 FAIL/EV6 永远保留，不豁免、不清除。

### 本轮核验与边界

- 在写入本复核追加记录之前，上轮保存的 **106 个受保护文件**逐个 SHA-256 匹配，包含五个 producer、闭环驱动和保留证据/修订/回执/冻结及审查产物；这是一组有边界的文件核验，不是对全部工作区或历史操作的无变化证明。
- goal 和 request 文档分别仍为 `00444583…`、`3d4e0570…`。v2 保存结果仍为 `099640a2…`、capability FAIL、`authorizes_pilot: false`。
- HEAD 为 `73f266d4165df48bacc6112f037537aed5fb7a58`，暂存区为空。四个生产库/伴随文件的大小与修改时间匹配之前的基线；仅 stat，没有打开 SQLite 内容。
- 本轮只读文档、代码及保存结果并计算哈希；未重跑套件或适配器，未采集、联网、访问令牌、操作服务、修改生产库或执行 Git 暂存/提交/推送。Codex 唯一写入为本报告。
- R2-ABC 有界离线技术验证继续有效；本轮不声明来源能力通过、用户接受、三年语料认证或训练就绪。两次采集授权仍已消耗。

### Current follow-up instruction for Claude

Revise only `claude methods/M2B_NEXT_STAGE_DECISION_MEMO.md`. R1–R3 are closed; preserve their substance. Address only these two remaining documentation issues:

1. Correct Annex A and its resolution summary by separating request-level outcome rows from `aggregate_job` and `summarize`. History transport failure yields a failed job. After decoded history, ordinary auxiliary failure/absence/unusable payload yields `JOB_INCONCLUSIVE_AUXILIARY`, with required job FAIL taking priority; auxiliary `aborts_run` and unexplained skips remain failed jobs. Distinguish run-global skips. For history payload/decode inconclusiveness, describe the actual summarize branch instead of attaching an unsupported required-check override. Preserve overall FAIL precedence, and do not invent a request-level `inconclusive_auxiliary` evidence class. The previous Codex R4 transport shorthand was also incomplete; use the current code as the authority.
2. Replace the claim that a future run will clear historical EV6. A separately authorized run may produce new same-version evidence; only matching classifications omit EV6 in that new result, and other gates can still fail. Historical captures and revisions retain their failures unchanged.

Do not change implementation, rerun tests/replay, decide P1 or turnover policy, or create another acknowledgment artifact. Preserve all other documents, sources, datasets, strategies, knowledge, evidence, revisions, receipts, frozen bundles and reviewer artifacts. Both capture authorizations remain consumed. No capture, HTTP/plugin calls, SQLite opens, service actions, token access, production mutation, pilot, training, source expansion, Git staging/commit/push or live trading. Stop at `proposed for review` with a concise two-item resolution summary.

## Revision 3 独立复核收口 — 2026-09-08

**结论：`validated`，本阶段离线决策备忘录技术验收通过。** 被审文件 `M2B_NEXT_STAGE_DECISION_MEMO.md` Revision 3，SHA-256 `536505ea4a29e506dadf3c510eab67dc8d52a84706f2288c85690af64aea0d4a`。Claude 文件保留 `proposed for review` 属于送审状态；本追加记录为 Codex 本轮审查结论，不要求再进行一轮确认式文档修改。

### 剩余两项关闭依据

1. **附录聚合规则已对齐。** 备忘录第 320–404 行分开请求 outcome、`aggregate_job`、`summarize` 三层；八个请求级 evidence class 与对源码 AST 的静态读取一致。历史请求传输失败、普通辅助失败、辅助中止、run-global skip、无触发 skip 均按当前代码分别处理；required FAIL 优先限定在 `CONTINUE` / `INCONCLUSIVE_AUXILIARY` 分支，总能力 FAIL 不被后续 INCONCLUSIVE 覆盖。BJ 历史明确 404/410 的例外及当前 JOBS 顺序、中止后降级均正确。依据：`smoke_outcomes.py:72–173`、`smoke_checks.py:1504–1576`、`smoke_capture.py:157–164`。没有通过修改实现来适配文档。
2. **历史 EV6 表述已修正。** 第 222–227、278–283、406–410 行明确未来采集只能产生独立新结果；分类一致时仅新结果不出现 EV6，其他检查仍可能失败，历史 FAIL/EV6 不被清除或豁免。第 429–439 行修订表正确标记 Revision 2 的不完整映射已被替代。

R1–R3 已关闭内容继续保留：P1 候选证据的能力与限制、股本沿用年龄与来源完整性不确定的区分、U4 的 ADVISORY 定位，以及 EV2 仅覆盖字节转文本和同版本真实采集尚未验证。建议暂缓第三次采集可以作为明确的边际收益判断保留，不能视为能力已通过或否定真实运行缺口。

### 保存状态与验证范围

- 上轮基线中的 **106 个受保护文件逐个 SHA-256 匹配**；五个 producer、闭环驱动及保留证据、修订、回执、冻结产物未漂移。goal 与 request 哈希分别保持 `00444583…`、`3d4e0570…`。此核验只覆盖列入基线的文件，不声称证明全部工作区或全部历史操作无变化。
- v2 的确定性哈希仍为 `099640a21e5927a057f3d2d1468b5765312bf1b68ff0d056051a18317fc81292`；股票两项作业 FAIL、指数 PASS，capability FAIL，`authorizes_pilot: false`。
- HEAD 保持 `73f266d4165df48bacc6112f037537aed5fb7a58`，暂存区为空。四个生产库/伴随文件的大小与修改时间匹配已有基线，仅查询文件元数据，未打开 SQLite。
- 本轮静态读取文档/源码/保存结果并计算哈希，未执行实现模块、测试或适配器回放，未进行 HTTP/插件调用、采集、令牌访问、服务操作、数据库内容读取/写入或 Git 暂存/提交/推送。Codex 只更新本审查报告。
- 182/182、76/76、49/49 等属于此前已记录的离线运行结果，本轮没有重跑，也不将其作为真实采集、语料或训练就绪证明。

本次通过的只是**下一阶段决策备忘录**。R2-ABC 有界离线技术验证保持有效；M2b 来源能力仍 FAIL 且未接受，历史 EV6 保留，同版本真实运行缺口仍存在，三年语料与训练就绪未获认证。两次真实采集授权均已消耗，没有新授权。

### 下一阶段范围与给 Claude 的指令

下一步限于一份可审查的 P1 复权标签/证据契约设计草案；不实施 P1、不决定换手率策略、不直接推进 52 标的试采。不要为了同步本次通过状态再创建确认式材料。

Create only `claude methods/M2B_P1_BASIS_CONTRACT_PROPOSAL.md` as an offline design proposal, stopping at `proposed for review`. The decision memo Revision 3 is technically validated; do not reopen it or create an acknowledgment-only artifact.

Use the current code, the existing request's G7 and Section 6, and retained evidence only. Explain the current `unknown` behavior and distinguish vendor price basis, transformations applied by the adapter, and the label/corroboration contract. Compare concrete options and recommend one without adopting or implementing it. Map S1/B1, B2, R1 and I2/B4 to exactly what they establish and leave unknown; B3 is not P1 evidence. Do not infer vendor-unadjusted prices merely from `adjust=""` or a flat ratio.

Specify proposed decision rules, evidence/version binding, fail-closed cases, affected code locations, and a focused future validation matrix. Check whether the retained reference actually contains a useful discriminating span using existing local extracts only; do not assume a wider window or a known corporate-action date exists. If evidence is insufficient, identify the precise missing proposition and leave the corresponding decision unresolved. Do not obtain new evidence or broaden sources.

Preserve all existing files, labels, datasets, strategies, knowledge, evidence, revisions, receipts, frozen bundles and reviewer artifacts. Do not change implementation or thresholds, rerun suites/replay, decide turnover policy, or prepare/arm a capture. Both capture authorizations remain consumed. No HTTP/plugin calls, SQLite opens, service actions, token access, production mutation, pilot, training, source expansion, Git staging/commit/push or live trading. This is a proposal for review, not operational authorization or source-capability acceptance.
