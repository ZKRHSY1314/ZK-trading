# P1 basis contract proposal — Codex 独立复核

> **最新复核（2026-09-09）：Revision 6 的当前 v3 输入实施说明通过（`validated`，文档范围），A-R1–A-R3 关闭。** 同摘要旧版示例的检测能力按文末审查限定解释；不影响当前 v3 范围。此前政策建议和原 R1–R3 关闭状态保持。不采纳 Option C，不关闭 P1，不授权实施。下文原轮次结论和指令仅作历史记录。

日期：2026-09-08。被审文件：`M2B_P1_BASIS_CONTRACT_PROPOSAL.md`，SHA-256 `ca3c26ea37a04ed55c60971b68f11d7f4c26047da817e3e5cfae6b90a301a9ad`。

**结论：`changes_requested`。拆分“供应方价格复权属性”和“本地适配器变换”的方向合理，但本版还不足以作为实施契约。** 本轮只要求修订这份草案，不采纳 Option C，不实施，不重开已通过的决策备忘录。

## 已核实的部分

- `provenance.derive` 在缺少 response-declared basis 时返回 UNKNOWN，与 `basis_gate` 要求存储值匹配声明值的现状吻合。不能把 `adjust=""` 直接解释成供应方价格未经复权。
- S1/B1、B2、R1 与 I2/B4 的证据局限，以及 B3 不属于 P1 依据的区分可以保留。
- 两份保留 reference extract 字节相同，内部内容哈希为 `3a599027a963531f3bfcb504e00d6b69914a4c00e317db65fa27530b1fade6f9`。SH600011 / SH000300 / BJ920000 行数确为 538 / 538 / 501；存在超过十行尾段的已保留数据，可用于以后另行定界的离线分析。
- 106 个受保护文件与既有哈希基线匹配；已通过的决策备忘录保持 `536505ea…`，HEAD 为 `73f266d4165df48bacc6112f037537aed5fb7a58`，暂存区为空。这是有边界的文件核验，不是对全部历史操作的证明。

## R1（P1）— Option C 尚未定义消费门槛，不能只定义如何生成标签

位置：提案第 88–106、118–136、193–204 行。

提案说明了如何断言“本地未执行价格调整”，但没有明确 `(adapter transformation = none, vendor basis = unverified)` 是否通过 P1，以及允许什么用途。Option C 的成本栏又说新值/字段必须通过 `basis_gate`。现有 `staging_gate.py:303–321` 只是检查存储字符串是否与声明相同；如果把新标签同时放进存储和 CLI，二者相等本身并不能解决供应方复权属性未验证的问题。

这不表示 Claude 已经放宽了门槛——当前没有实现变更。问题是**草案缺少决定是否放行的关键规则**。同一批记录全都标为 unverified，也不证明供应方在整个时间区间使用一致的复权口径。

要求：推荐一种明确的字段/值表示方式，并给出包含“变换事实、供应方复权状态、证据有效性、声明用途、门槛结果”的消费判定表。明确区分可记录审计事实、P1 是否关闭、是否满足现有 `--pricing-basis none` 和 boundary-2 数据要求；未知供应方属性不得仅因换了字段名或字符串匹配而成为价格口径已验证。若消费策略仍待决定，明确标为未解决，不能说 Option C 已解决 P1。列明不同维度的混合状态分别怎样处理，不将“所有行都 unverified”当成价格口径同质。

## R2（P2）— 决策规则与失败/验证表仍有歧义

位置：提案第 118–132、156–170、193–204 行。

- D-1 对所有序列要求 `adjust=""` 与股票 B2 三条属性；V-7 又允许指数 URL/code 路径生成标签，而指数接口不接收该 adjust 参数。应分别写出股票/指数的适用条件与不适用项，不能让实施者自行决定是否豁免 D-1。
- 第 156 行说九个分支都输出 unknown，但第 8 项是指数单位 unknown 的正常情况，第 9 项明确保留 transformation label。须分别列 transformation、vendor basis、volume unit 和消费门槛结果，不能共用一个未指明字段的 unknown。
- D-2 说供应方 basis 只能在 discriminating observation 后断言，D-4 又允许未来响应声明；V-10 正确说阶跃本身仍不足以断言 none。需明确各条件是必要还是充分、声明是否需要交叉支持；尚不能定义充分证据时保留 vendor basis 未验证。不要由一条声明或一个阶跃直接升级。

这些是同一契约的分支一致性修正，不要求新算法、新阈值或测试执行。

## R3（P2）— 参考提取的范围与同质性结论需要限定

位置：提案第 227–230、245–251、268–274 行。

1. 保留 SQL 包含 `quality_status = 'ready'`，以及标的和日期条件。提取中没有更早记录只能证明**当时该提取条件下未包含更早 ready 记录**，不能证明整个缓存没有更早数据，也不能证明必须更换数据源。本轮未打开数据库，不作该断言。SH000300 的实际最早日期还是 2024-06-19；2024-06-21 应限定为 SH600011。G-5 也应按该证据范围修正。
2. SH600011 的 471 行确实同一 source，但不是同一 `updated_at`：470 行为 2024-08-13 至 2026-07-23、更新时间 `2026-09-03T17:21:19`；另 1 行为 2026-07-24、更新时间 `2026-09-04T15:09:56`。因此 2026-07-24 也是 SH600011 的更新时间边界，应纳入混杂因素，而不是只标出该日 BJ 的异源记录。
3. 以连续相同 source 和 updated_at 分组，两只股票均有 470 行的最大片段（2024-08-13 至 2026-07-23）。这只消除了已记录的两项元数据差异，不能证明片段价格口径完全同质或存在公司行动。471 行可保留为“同 source 片段”，不能将它作为已经排除 fetch-time 混杂的比较窗口。
4. BJ 的异源单行可称“不同 source 的记录”；现有字段不证明它经过插值，不应称 interpolated-source row。

要求只改限定语、分段表、G-5 和相关验证场景；不计算更宽价格比值，不打开数据库，也不查公司行动。可记录现有材料未证明的命题，不把未证明升级为全局不存在或必需新增来源。

## 本轮边界

只读取源码、提案、保留 JSON，计算文件哈希与 reference 元数据分组；未计算价格比值、运行测试/回放、执行实现模块、打开 SQLite、调用网络/插件、访问令牌、采集、操作服务或 Git 暂存/提交/推送。Codex 唯一写入为本报告。两次真实采集授权仍已消耗；M2b 能力 FAIL 与历史 EV6 保留，P1 未关闭，三年数据训练就绪未获确认。

## Follow-up instruction for Claude

Revise only `claude methods/M2B_P1_BASIS_CONTRACT_PROPOSAL.md` for R1–R3 in this review. Keep the separation between adapter transformations and vendor price basis, but do not adopt or implement Option C.

1. Propose concrete fields/values and a consumer decision table. State what `(no adapter adjustment, vendor basis unverified)` permits for audit storage, P1 closure, the existing `--pricing-basis none` requirement, and boundary-2 data eligibility. A matching new string must not certify an unverified price basis. Define mixed-state handling; uniformly unverified labels do not prove uniform vendor adjustment. Explicitly leave unresolved policy decisions open.
2. Make D-1–D-4, fail-closed cases, and validation scenarios consistent. Separate stock and index applicability. Give field-specific unknown/unverified outcomes. Distinguish necessary from sufficient evidence for vendor-basis assertions; neither a response declaration nor a ratio step alone should silently upgrade the basis.
3. Correct the reference claims: the filtered extract does not prove the whole cache lacks earlier data. Use per-symbol dates. Distinguish same-source spans from spans sharing both source and updated_at; SH600011's 471-row source span splits into 470 rows plus a differently updated row on 2026-07-24. Include that boundary as a confounder. Remove the unsupported interpolation claim. Do not compute wider ratios, obtain corporate-action data, or open SQLite.

Preserve all other files and artifacts. No implementation, label/schema/threshold/dataset/strategy/knowledge changes, tests/replay, turnover-policy decision, capture preparation, HTTP/plugin calls, SQLite opens, service actions, token access, production mutation, pilot, training, source expansion, Git staging/commit/push or live trading. Both capture authorizations remain consumed. Stop at `proposed for review` with a concise R1–R3 resolution summary; create no acknowledgment-only artifact.

## Revision 2 设计草案验收 — 2026-09-08

**结论：`validated`，本阶段设计草案验收通过，无剩余 R1–R3 阻断项。** 被审文件 SHA-256：`05448711415e784b70294076d4ba3c2c770d3b192020aa7153d77dca25026d9a`。本结论没有把一份含有明确待决策项的草案认定为可以实施的完整契约。

### 关闭依据

- **R1 关闭（第 119–179 行）。** 已提出四组字段、消费判定表及逐维度混合状态说明；`adapter_transform=none, vendor_basis=unverified` 明确不能满足现有 `--pricing-basis none`。字符串相等不构成供应方价格复权属性证明，全体 unverified 不构成口径同质。U1–U7 明确未决；Option C 本身不能声明 P1 已关闭。表内审计存储、未来映射与边界 2 资格均属提议，不是当前写入或使用授权。
- **R2 关闭（第 187–304 行）。** D-1a 与 D-1b 分开股票和指数参数/代码路径；F-1–F-9 分字段列明失败状态，N-1/N-2 正确区分正常的未知单位或未验证供应方状态。D-2/D-4 与第 3.3 节禁止声明或阶跃单独升级供应方 basis；充分证据规则 U-6 尚未定义，因此没有自动升级路径。指数 basis 的后续语义列入 U-7，不把其单位未知当成变换事实失败。未来规则仍需进一步决策，并未在本轮实施。
- **R3 关闭（第 322–419 行）。** 最早日期分别限定到标的，`quality_status='ready'` 的过滤限制得到保留；不再断言整个缓存没有更早数据。同 source 与同 source/updated_at 片段分开，SH600011 的 471 行拆为 470＋1，2026-07-24 的更新时间变化被列入混杂因素，BJ 插值断言移除。仅根据这些元数据分段不能证明价格口径一致或存在公司行动，提案已明确这一点。

### 独立核验

本轮直接读取保留 reference JSON 并重新按日期、source、updated_at 分组：SH600011 / SH000300 / BJ920000 总行数为 538 / 538 / 501；两只股票的最大双键连续片段均为 470 行（2024-08-13 至 2026-07-23），指数为 475 行（2024-06-24 至 2026-06-09）。没有计算价格比值、解码或执行适配器回放。

106 个受保护文件逐个 SHA-256 与既有基线匹配；决策备忘录仍为 `536505ea…`，goal/request 分别为 `00444583…` / `3d4e0570…`。v2 确定性哈希仍为 `099640a21e5927a057f3d2d1468b5765312bf1b68ff0d056051a18317fc81292`，capability FAIL。四个生产库/伴随文件的大小和修改时间匹配基线，仅 stat，未打开 SQLite 内容。HEAD 为 `73f266d4165df48bacc6112f037537aed5fb7a58`，暂存区为空；已有其他工作区变更未处理。这些检查有明确范围，不证明全部历史操作或整个工作区没有变化。

Codex 本轮只更新本报告；未修改 Claude 草案、实现或数据，未运行测试、回放、网络/插件、采集、服务、令牌访问或 Git 暂存/提交/推送。草案中的 proposed 状态可保留，不需要再制作确认式材料。

### 本次通过的限度及下一步

通过的是 **P1 契约设计草案**，不是 Option C 的采纳、P1 闭环或实施批准。U1–U7 的消费策略、存储方式与充分证据规则仍待决定。M2b 来源能力仍 FAIL，历史 EV6 不变，两次真实采集授权均已消耗；同版本真实运行、三年语料认证及训练就绪未获证明。

下一步只将 U1–U7 整理成可供决定的明确推荐方案和暂缓项。可在同一草案追加下一阶段章节，保留本版证据与修订记录；不执行推荐方案，不追加宽泛研究或确认式文件。

### Next-stage instruction for Claude

Revise only `claude methods/M2B_P1_BASIS_CONTRACT_PROPOSAL.md` to add a decision-ready U1–U7 recommendation section. Revision 2 passed the bounded design-proposal review; do not reopen R1–R3 or create an acknowledgment-only artifact. No option has been adopted and P1 remains open.

For each U item, give one recommended choice, its rationale, affected consumers, and the prerequisite for implementation. Distinguish policy choices that can be proposed now from evidence-dependent questions that must remain deferred. Recommend conservative defaults: keep the present price-basis meaning and block unverified/inconsistent vendor basis from raw-basis eligibility; retain mixed-basis failures; do not let mixed or stale producer pins silently certify a view. Prefer an evidence-side representation for an initial design over a production schema migration. Treat index semantics separately from stock corporate-action evidence.

For U-6, do not invent sufficient evidence or new thresholds. State what remains missing and keep vendor_basis unverified. Distinguish preserving historical audit facts from their eligibility for a current consumer. End with a minimal proposed implementation boundary and explicit remaining blockers, not a claim that P1 is closed. All recommendations remain proposed, not adopted.

Preserve all other files, sources, labels, datasets, strategies, knowledge, evidence, revisions, receipts, frozen bundles and reviewer artifacts. No implementation, schema/threshold changes, tests/replay, wider ratio computation, corporate-action lookup, turnover-policy decision, capture preparation, HTTP/plugin calls, SQLite opens, service actions, token access, production mutation, pilot, training, source expansion, Git staging/commit/push or live trading. Both capture authorizations remain consumed. Stop at `proposed for review`.

## Revision 3 政策建议复核 — 2026-09-08

**结论：本阶段 U1–U7 建议稿通过，`validated` 仅覆盖政策建议的形成与边界。** 被审文件共 657 行，SHA-256 `7ce77aa6f544fcc7c5bb29ea6096891795a4760192b7940d313226748addb6db`。不是对第 5.8 节未来代码或完整实施接口的验收，也不是用户采纳推荐项。此前设计草案 R1–R3 的关闭状态保持。

### 核实结论

- 第 425–597 行逐项给出了推荐、理由、消费者和前置条件。U1/U2 不允许未验证供应方 basis 通过现有 raw/none 要求；U3 拒绝混合状态且不将统一 unverified 当成同质证明；U4 分开不可改写的历史审计事实和当前使用资格；U5 推荐证据侧存储，不改生产表或连接现有 gate。
- U6 明确不定义充分证据规则、不发明阈值，仍保持 unverified；U7 不借股票公司行动规则替指数作断言。政策可推荐、证据尚不足的区分成立。
- 第 599–632 行把实现列为条件式未来工作，并保留能力 FAIL、历史 EV6、未采纳政策等限制。没有因本稿而取得新的采集、生产变更或试运行权限。

### 一项非阻断文字修正

第 626 行 B-3 写“pursuing option D cannot start without”新提取授权，范围过宽。第 407 行 G-3 已承认保留材料可做有界离线比值分析，第 571–574 行也把新提取限定为现有片段不可用时的后续选项。因此应改为：**新提取需要新授权；已有材料的离线研究不以新提取为逻辑前提；真实公司行动证据、离线计算、可能的新提取分别定界。** 这不意味着本轮或上一轮已经授权比值计算、外部查询或数据库读取。

该句不改变本轮保守的政策推荐，也没有放宽权限，不作为建议阶段阻断项；应随下一份具体实施说明一起更正，无需单开一轮确认式文档。

### 实施前尚须明确的接口边界

第 606–612 行的“从已有 S1/B1/B2/R1 生成记录和 eligibility”是范围摘要，不能直接当作完备输入契约。保留 v2 的 B2 记录的是**股票** adapter source hash，R1 记录行数、日期与列；这几个 check 的 PASS 字符串并不单独携带指数 adapter pin、全部调用参数或按行 provenance。不能补造历史字段，也不能把今天读取到的源码哈希冒称为当时已记录的 pin。

具体实现说明须列出每个输出字段来自哪份既有证据、记录粒度和覆盖的 symbol/date 范围、缺失时的处理、producer pin 与 run_id/输入标识的区别、新产物的独立存放路径，以及判定器的精确用途。对当前真实材料 vendor_basis 仍为 unverified，basis-dependent eligibility 必须为 false；该判定器不能授权采集、试采、生产消费，也不能代替 capability verdict。已保留的 captures/revisions/checks 不可就地改写。

这是下一阶段的实现准备内容，不重开 R1–R3，也不要求在本阶段执行代码或补充行情证据。

### 保存状态与本轮操作

106 个受保护文件逐个哈希匹配，五个 producer、闭环驱动和保留证据未漂移；决策备忘录仍为 `536505ea…`，v2 capability 仍 FAIL、`authorizes_pilot` 为 false。HEAD 为 `73f266d4165df48bacc6112f037537aed5fb7a58`，暂存区为空；四个生产库/伴随文件大小和修改时间匹配基线，只查元数据。未处理其他已有工作区变更。

本轮读取文档、源码相关记录和保留 JSON，计算哈希；未运行测试、回放、比值计算、公司行动查询、HTTP/插件、SQLite、服务、令牌访问、采集或 Git 暂存/提交/推送。Codex 仅更新本报告。受保护文件核验不能证明所有历史操作或整个工作区完全无变化。

**P1 仍未关闭，Option C 未采纳；M2b 来源能力 FAIL，历史 EV6 保留；两次真实采集授权均已消耗；三年语料和训练就绪未获确认。**

### Next-stage instruction for Claude — bounded implementation specification only

The Revision 3 U1–U7 recommendation stage passed its bounded review. No policy has been adopted and no implementation is authorized. Revise only `claude methods/M2B_P1_BASIS_CONTRACT_PROPOSAL.md` to add one compact implementation-specification appendix; preserve the reviewed recommendations and R1–R3 closures.

Correct B-3: a fresh extract requires fresh authorization, but it is not a prerequisite for every investigation using retained material. Keep external corporate-action evidence, offline ratio computation, and a possible fresh extract separately scoped. Do not perform any of them.

For the evidence-side record and evaluator, specify exact input artifacts and field mappings, stock/index differences, record granularity, covered symbols/dates, and missing-evidence outcomes. Identify which required pins and invocation facts are actually recorded. A current local source hash must not masquerade as a historical capture-time pin. Distinguish producer pins from run identifiers and input hashes; never synthesize missing provenance.

Specify separate new output paths, deterministic serialization, and preservation of every existing capture/revision. Define the evaluator as basis-dependent eligibility only, with explicit reasons; current unverified evidence cannot yield eligible. It must grant no operational authority and must not replace the existing capability verdict or gates. List a small future synthetic validation matrix and exact proposed file write scope. Stop before implementation and policy adoption.

No additional acknowledgment artifact, implementation, production/schema/label/threshold/dataset/strategy/knowledge changes, tests/replay, wider ratios, corporate-action lookup, capture preparation, HTTP/plugin calls, SQLite opens, service actions, token access, pilot, training, source expansion, Git staging/commit/push or live trading. Preserve all other files. Both capture authorizations remain consumed. Stop at `proposed for review`.

## Revision 4 实施说明复核 — 2026-09-08

**结论：`changes_requested`，附录 A 暂不能作为实施依据。** 被审提案 SHA-256 `141b2d42ed43173b2140785cadd371ff4fa0eb4358d4a07fc36edf2403063768`。只剩下面三个接口问题，不重开已通过的政策建议或原 R1–R3。

已正确补齐：B-3 分开已有材料研究与新提取；capture-time/check-time 信息分开；不补造指数 adapter 历史源码哈希；记录粒度限定到 capture/revision/job；独立输出目录且拒绝覆盖；不改原 producer、数据库或既有 gate。指数当前输出 unknown、所有当前真实材料 vendor_basis 为 unverified 的方向正确。

### A-R1（P1）— 输入核验链与新模块自身版本尚未进入契约

位置：附录 A.1–A.3，第 648–702 行；A.5、A.7，第 731–779 行。

记录只从旧 `PROVENANCE.producer_implementation` 继承五个 producer 哈希，而实际生成新记录、作出资格判断的是新增 `basis_record.py`。保持旧五个哈希不变是必要的，但不能代替记录新模块自己的版本。若新模块规则改变，按现有映射仍可得到完全相同的 producer pin 标签，无法识别由哪一版规则生成新事实和判定。

此外，附录列出了 input_hashes 和 deterministic_sha256 的读取位置，但没有规定生成记录前必须重算/比对这些哈希、核对 parent/revision/run/job 关系及拒绝不一致。只有复制输入自报哈希不是验证。A-7 针对输出单字段修改的例子也没有覆盖被改动的 checks、PROVENANCE 或交叉配错的输入。

要求：分开 `upstream_producer_pins` 与新输出自身的 producer/schema/rules/evaluator 版本；新输出 PROVENANCE 绑定 `basis_record.py` 等实际依赖、所消费 checks.json/PROVENANCE.json 的文件哈希及关联的旧证据身份。明确写入前的哈希、结构和跨文件关联检查顺序；任何缺失/不符拒绝生成可信记录或输出明确不可用的诊断，不得照抄 PASS。加入输入漂移、错配 revision/run、缺失输入以及新模块版本改变的未来合成用例。无需重放、重新解码或触碰数据库。

### A-R2（P2）— 计划/记录 URL、实际采集与离线回放 URL 不能合并成 observed_urls

位置：第 703 行和 A.3 的正向派生规则。

源码 `smoke_checks.py:970–980` 的 S1.measured 来自 manifest request records 中的 `requested_url` 集合，与 expected_requests 比较；它本身不检查这些请求是否真的发出。跳过的请求记录同样可携带 requested_url。`R1urls.measured` 来自离线 adapter replay（第 1460–1465 行），其 PASS 只保证没有访问未捕获 URL，并不是实际现场采集日志，也不证明集合完整。

因此 A.3 将二者一起写入一个 `observed_urls`，会让后续消费者误读证据发生的阶段。当前完整五请求样本中各集合恰好一致，不能据此定义通用映射。

要求：分别记录 manifest requested/expected URL、由请求 outcome/attempts 支持的实际采集访问以及 replay requested URL；给出各自的来源、含义和关联规则。跳过的请求不能被记成已访问，回放不能被记成新采集。正向 transform 派生需满足相应真实执行/回放证据与完整性条件，而非仅从 S1/R1urls 的 PASS 推断；增加 skipped-but-listed 和 replay-subset 的未来合成用例。不要改现有检查定义。

附带准确性修正：第 686–687 行称 adjust 只出现在 B4 prose 不准确，B2.detail 也含 `adjust=""`。实质结论仍成立：没有独立的调用参数字段；应写成“只有文字/源码推导信息，没有结构化调用参数记录”，不必依赖该全文搜索断言。

### A-R3（P1）— U6 未定义充分证据时，不能仅按标签和当前 pins 开放 true 分支

位置：A.6，第 750–759 行；A-7，第 793 行。

A.6 给出的条件是 vendor_basis=unadjusted、adapter_transform=none、pins 当前且一致；未包含供应方 basis 断言的有效来源/充分证据规则。A-7 只要求拒绝“没有 supporting evidence reference”的手改记录。但一份记录即使引用真实存在的旧证据，旧证据也从未证明供应方未复权。保留有效引用并把 unverified 改为 unadjusted，同样不能通过。

“当前生产者只生成 unverified”是对生产者的约束，不能代替对可被单独调用的 evaluator 输入的验证。U6 仍未定义，当前接口应默认不信任输入中声称已验证的标签。

要求：本初始模块不提供可由标签/哈希相等触发的 eligible=true 路径；对当前不支持的 vendor-basis assertion 明确拒绝，包括保留有效证据引用的伪升级。未来 true 分支需要另行采纳并验证充分证据规则，不能在本版预留可绕过的路径。区分 reason 中的未验证、未知规则版本、证据错配等原因，但不改变既有 capability 或操作权限。增加“真引用＋伪 unadjusted”“未知验证规则”用例。

### 本轮验证及权限

106 个受保护文件与既有哈希基线逐个匹配，决策备忘录/goal/request 保持 `536505ea…` / `00444583…` / `3d4e0570…`；四个生产库/伴随文件的大小与修改时间匹配，仅 stat。HEAD 为 `73f266d4165df48bacc6112f037537aed5fb7a58`，暂存区为空。v2 保存结果继续 capability FAIL。核验范围不等于全部工作区或历史操作无变化证明。

本轮只读文档、源码与保留 JSON 并计算哈希，未执行实现模块、测试、回放、比值计算、公司行动查询、HTTP/插件、SQLite、服务、令牌访问、采集或 Git 暂存/提交/推送。Codex 只更新本报告。

P1 未关闭、Option C 未采纳；M2b 来源能力 FAIL，历史 EV6 保留，两次真实采集授权均已消耗，三年语料与训练就绪未获证明。

### Next-stage instruction for Claude — three bounded specification fixes

Revise only `claude methods/M2B_P1_BASIS_CONTRACT_PROPOSAL.md` to address A-R1–A-R3 in this review. Preserve the reviewed U1–U7 recommendations, original R1–R3 closures, and corrected B-3. Do not implement anything.

1. Separate upstream producer pins from the new record/evaluator's own producer, schema and rules versions. Bind actual dependencies and consumed checks/PROVENANCE files. Specify mandatory pre-write hash, structure and cross-file identity verification, with fail-closed outcomes for missing, altered or mismatched inputs. Add future synthetic cases for these failures and new-module version changes.
2. Separate manifest requested/expected URLs, evidenced capture attempts, and offline replay URLs. S1 does not prove a request was issued; R1urls PASS only excludes uncaptured URLs. Define exact sources and completeness rules, including skipped requests and replay subsets. Correct the inaccurate claim that adjust appears only in B4 prose; there is no structured invocation-argument field.
3. While U6 has no adopted sufficiency rule, the initial evaluator must expose no label-driven eligible=true path. Reject unsupported unadjusted assertions even when they retain a genuine evidence reference and current pins. Add true-reference/false-assertion and unknown-rule-version cases. Any future positive path requires a separately reviewed evidence-validation rule.

Preserve all other files and evidence. No acknowledgment-only artifact, implementation, labels/schema/thresholds/datasets/strategies/knowledge changes, tests/replay, ratios, corporate-action lookup, capture preparation, HTTP/plugin calls, SQLite opens, service actions, token access, production mutation, pilot, training, source expansion, Git staging/commit/push or live trading. Both capture authorizations remain consumed. Stop at `proposed for review` with a concise three-item resolution summary.

## Revision 5 复核 — 2026-09-08

**结论：两项关闭，尚余一项有界修正，`changes_requested`。** 被审文件 SHA-256 `97977f343affe9470af2480d81abacd6c021323c5dcf1faa4cf3f980b5f81386`。不重开已通过的政策建议和原 R1–R3，也不要求重新设计整份附录。

### 已关闭内容

- **A-R2 关闭。** A.3.1 分开 manifest 请求地址、由 attempts 支持的访问尝试、离线 replay 地址；明确 S1 不证明发出、R1urls 不保证完整，skipped 和 replay subset 不得生成正向变换事实。两个保留 manifest 的例子核实：第一次只有请求 1/3 各一次尝试，其余三项 skipped；第二次五项各一次尝试。adjust 的文字描述已更正，结构化调用参数缺失仍明确保留。
- **A-R3 关闭。** A.6 明确初版没有 eligible=true 分支；真实引用＋当前 pins 也不能支持伪造 unadjusted 标签，未知规则版本拒绝解释，无可开关的预留正向路径。仅认可说明已修正，不冒称运行过尚不存在的 evaluator。
- **A-R1 大部分关闭。** 新模块自身 hash/schema/derivation/evaluator 版本与 upstream pins 分开；输入文件哈希、自身 deterministic hash、输入结构与身份检查已列为强制步骤。剩余缺口如下。

### A-R1 残余（P1）— 相同 capture_run_id 不能绑定具体 revision 的 checks

位置：A.5.2 第 802–810 行，以及 A-13 第 911 行。

步骤 4 检查 checks 是否与**它自己携带**的 deterministic_sha256 一致，步骤 5 检查 capture run_id 与 parent 的关系。两者不能排除**同一采集、不同 revision** 的 checks 被交叉配对。旧 `_r2abc` 和当前 `_r2abc_v2` 恰好都是采集 `20260908T082833Z` 的离线修订。

本轮仅在内存中读取既有 JSON、计算摘要并比较，没有复制、改写文件或执行检查器。用旧 `_r2abc/checks.json` 与当前 `_r2abc_v2/PROVENANCE.json` 对比，得到：

| 检查 | 实际结果 |
|---|---|
| 旧 checks 的 deterministic 内容与自身摘要一致 | true |
| checks.run_meta.run_id 与当前 parent manifest.run_id 一致 | true，均为 `20260908T082833Z` |
| 当前 PROVENANCE 的七个 parent input hashes 与实际文件一致 | true |
| 当前 PROVENANCE 的五个 upstream pins 与本地文件一致 | true |
| 旧 checks 摘要等于当前 PROVENANCE 声明的结果摘要 | **false**：`c23f44bc…` ≠ `099640a2…` |

这不需要“全部文件及哈希同时伪造”，只是交叉选错一份真实 checks。A.5.2 目前没有明确最后一项比对，A-13 也仅写了不同 revision 的泛称，容易只测试 run_id 不同的情况。

**所需最小修正：** 在受支持的当前 provenance schema 中，强制要求：

1. 所选目录的 revision 身份与 `PROVENANCE.revision` 精确一致；明确它与 capture_run_id 是不同层级的身份。
2. `canonical_sha256(checks.deterministic)` 同时等于 `checks.deterministic_sha256` **及** `PROVENANCE.revised_offline_result.deterministic_sha256`，不能只做前两者的自洽检查。
3. 如果支持其他 provenance schema，逐版定义等价的结果锚点；未知 schema 或缺少所需锚点必须拒绝，而不是回退到仅核对 capture_run_id。
4. 增加“同 capture、不同 revision、两份 checks 各自摘要均合法”的未来合成用例，要求拒绝。另明确改动 deterministic 并重算自带摘要但未改变选定 revision 的结果锚点，也必须拒绝。

仍可保留完全自洽伪造在缺少独立信任锚时不可检测的限制，但不能用该限制代替已有 `revised_offline_result` 的关联检查。

### 非阻断措辞收紧

第 721 行的 attempt-backed 记录应称“有记录的请求尝试”，而不是一律证明 URL 已在网络上到达。TLS/连接失败的 attempt 不证明端点收到了请求；是否收到 HTTP 响应应由 status/transport_outcome/served_url 分别表达。URL 三类分离这一主要修正已经通过，可在本次有界修改中顺手限定，不新增验收阶段。

### 本轮核验与权限

106 个受保护文件逐个哈希匹配；决策备忘录/goal/request 保持 `536505ea…` / `00444583…` / `3d4e0570…`。四个生产库/伴随文件大小和修改时间匹配基线，仅 stat。HEAD 为 `73f266d4165df48bacc6112f037537aed5fb7a58`，暂存区为空；不处理其他既有工作区变更。

本轮只读文档、保留 JSON 和文件元数据并计算哈希；上述交叉配对是内存中的静态对照，不是实现测试或 adapter replay。未运行套件、解码、比值计算、公司行动查询、HTTP/插件、SQLite、服务、令牌、采集或 Git 暂存/提交/推送。Codex 唯一写入为本报告。文件基线核验不能证明所有历史操作。

P1 未关闭、Option C 未采纳；来源能力仍 FAIL、历史 EV6 不变、两次真实采集授权均已消耗，三年语料和训练就绪未获证明。

### Next-stage instruction for Claude — close only the revision-binding gap

Revise only `claude methods/M2B_P1_BASIS_CONTRACT_PROPOSAL.md`. A-R2 and A-R3 are closed; preserve them and all previously reviewed policy recommendations. Do not implement anything.

Complete A-R1 by binding checks to the selected revision, not merely to its capture run. Require `PROVENANCE.revision` to match the selected revision identity. For the supported current schema, require the recomputed deterministic digest to equal BOTH `checks.deterministic_sha256` and `PROVENANCE.revised_offline_result.deterministic_sha256`. Define schema-specific anchors explicitly and reject missing anchors or unknown schemas.

Add future synthetic cases for: (1) old and current revisions of the SAME capture, each internally hash-valid, cross-paired with the selected provenance; (2) edited deterministic content with its self-reported digest recomputed but the selected revision anchor unchanged. Both must be rejected before any trusted record is written. The retained `_r2abc` and `_r2abc_v2` results illustrate the first case; do not edit or copy them to manufacture a fixture this round.

Also tighten the attempt wording: a recorded attempt does not by itself prove endpoint reachability or receipt of an HTTP response. Keep attempted access and response evidence distinct.

Preserve every other file. No implementation, tests/replay, data/schema/label/threshold changes, ratios, corporate-action lookup, capture preparation, HTTP/plugins, SQLite, service actions, token access, production mutation, pilot, training, source expansion, Git staging/commit/push or live trading. Both capture authorizations remain consumed. Stop at `proposed for review` with a concise closure summary; no acknowledgment-only artifact.

## Revision 6 实施说明收口 — 2026-09-09

**结论：`validated`，当前 `m2b.offline_revision.v3` 输入范围的实施说明技术验收通过。** 被审提案 SHA-256 `71e0dc52b8cf93281b1c09f501a62695915ef070a740dc378df2f1637a66007c`。A-R1 的主要缺口关闭，A-R2/A-R3 继续保持关闭；没有在本轮执行尚不存在的模块或验证其运行效果。

### 关闭依据

- 第 813–834 行同时要求：重算 deterministic 摘要与 checks 自带摘要一致、与所选 PROVENANCE 的结果锚点一致；PROVENANCE.revision 与所选目录身份一致。capture run_id 只作补充，不能替代 revision 身份。
- 第 840–857 行按 schema 列出结果锚点，未知 schema/缺失锚点拒绝；旧 v1/v2 缺少完整 input_hashes 等证据，不允许生成可信记录。当前 v3 使用 `revised_offline_result.deterministic_sha256`。
- A-20/A-21/A-22 将同次采集的跨 revision 配对、重算自带摘要后的内容改动、未知 schema/缺锚点纳入未来验证场景；第 732–746 行已分开 attempted/responded/usable，A-23 覆盖无响应的尝试。
- A.6 保持初版无 eligible=true 分支、无开关式正向路径；当前全部供应方 basis 仍未验证，不放行任何依赖已确认价格口径的用途。

### 非阻断审查限定：同摘要旧版示例不能证明目录匹配会发现一切替换

第 824–826、859–864 行及 A-20 的叙述需按以下边界理解：如果保留所选目录自己的 PROVENANCE，只替换 checks 文件，`PROVENANCE.revision == 所选目录名` 仍然成立。它能发现目录与 provenance 的错配，不能单独发现任意 checks 文件替换。

本轮确认 `_d1d2` / `_d2_literal` 的 deterministic 摘要确实相同（`784ffa66…`），完整文件哈希不同（`78819944…` / `2ef03476…`）。因此“只靠 step 5(b) 就能识别该 checks 互换”的说法过强。所幸这些旧版输入已经因为缺少完整证明材料被拒绝，不影响本次批准的当前 v3 范围。

以后实施时，入口应只接收一个所选 revision 目录，并从中解析 checks 与 PROVENANCE，避免开放任意文件拼接；测试应分别验证路径/provenance 错配、结果摘要不匹配、缺少证据。不要声称在没有独立的完整文件信任锚时，可由目录名证明同 deterministic 内容文件的全部历史来源。将此限定用于实现和测试即可，不需要再单独生成一轮确认式文档。

### 本轮静态核验

重新读取四个保留 revision，确认 schema/锚点字段与表格一致、每个 deterministic 摘要自洽。`_r2abc` 为 `c23f44bc…`，`_r2abc_v2` 为 `099640a2…`，新版双锚点规则能区分上轮提出的实际反例。

当前 v2 的五个 producer 文件哈希逐个匹配 PROVENANCE；七个 parent 输入文件哈希逐个匹配，闭环驱动仍为 `63f73196207f13c4c3e0fd9e1da1455e68cf5e997948c1e36e904648f694372d`。决策备忘录/goal/request 分别为 `536505ea…` / `00444583…` / `3d4e0570…`，与此前记录一致。没有 `basis_*` 新产物。

本轮没有可直接复用的完整 106 文件逐项基线，因此**不重复声称已重新验证全部 106 项**。上述为本轮实际完成的核验范围。四个生产库/伴随文件仅查询 stat 元数据，大小与此前记录一致，未读取 SQLite 内容。HEAD 为 `73f266d4165df48bacc6112f037537aed5fb7a58`，暂存区为空，其他既有变更未处理。

本轮仅静态读取与哈希计算，未运行测试/回放/解码/比值计算、公司行动查询、HTTP/插件、SQLite、服务、令牌访问、采集或 Git 暂存/提交/推送。Codex 唯一写入为本报告。

### 结束文档修订循环，下一步为单独的实施决定

本阶段文档验收完成。Option C 和 U1–U5/U7 尚未由用户采纳，本轮不把“验收文档”解释为批准实施。若用户决定推进，具体范围已经可审查：仅新增 `basis_record.py`、`test_basis_record.py` 和独立新输出目录，离线合成测试与保留文件核验，所有旧文件保持不变。没有必要继续增加建议稿或确认式文件。

P1 仍未关闭，U6 暂缓；M2b 来源能力 FAIL，历史 EV6 保留；两次真实采集授权均已消耗，没有新采集授权；三年语料或训练就绪没有获证。

### Next-stage instruction for Claude — conditional offline implementation handoff

Revision 6 is technically validated for the current v3-input specification, with the Codex clarification about same-digest file substitution. Stop further proposal-only revisions and do not create an acknowledgment artifact.

This review is not policy adoption or implementation authorization. Wait for an explicit user decision adopting the bounded U1–U5/U7 recommendations and authorizing the offline module. Until then, leave all files unchanged.

Once that decision is given, create only `claude methods/_m2_smoke/basis_record.py`, `test_basis_record.py`, and a fresh independent `basis_eval_*` output directory. Implement the reviewed specification with no eligible=true path. Accept one selected revision directory, bind its own checks/PROVENANCE, verify both digest anchors and required input hashes, and reject incomplete legacy schemas. Do not claim directory-name equality detects every same-digest file substitution; use distinct path/provenance and result-anchor cases in tests.

Run focused offline synthetic tests and validate against retained artifacts without adapter replay, network or SQLite. Preserve every existing source, dataset, strategy, knowledge file, capture, revision, receipt, frozen bundle and reviewer artifact. Do not wire any existing gate or modify production schemas/labels. No capture, services, token access, pilot, training, source expansion, Git staging/commit/push or live trading. Both capture authorizations remain consumed. Stop at `ready_for_review` with new-module hashes, commands, results and preservation evidence; do not claim P1 or source-capability acceptance.
