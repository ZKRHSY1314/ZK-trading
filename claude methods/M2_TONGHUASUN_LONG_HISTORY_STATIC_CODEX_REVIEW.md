# M2 接管与同花顺长历史接口静态复核

开始日期：2026-09-09；收尾日期：2026-09-10，Asia/Taipei。目录中的20260909为本轮开始日期。负责人：本任务 Codex；使用两个 Codex 子代理做独立只读检查，未向 Claude 派单。

## 1. 结论

**不能因项目适配器的 500 根限制排除同花顺。磁盘已部署的同花顺插件存在更长计数请求与日期范围请求的实际实现，不能默认 M2 只能继续 Sina。**

本轮静态证据已深入到插件 IL 和客户端 SDK：插件的 `NormalizeLimit` 对正数采用 `min(value, 5000)`，非正数默认 200；正式、后备两条 candle 调用均根据是否给出开始时间，选择“数量 + 结束时间”或“开始时间 + 结束时间”重载。起止时间不是只有字段声明而没有实现。

**5000 也不能写成底层服务的绝对历史上限。** 这是所审插件的数量参数规范化规则；日期范围分支使用另一种客户端重载。没有真实调用就不能保证服务实际返回 978 个目标交易日，也不能保证北交所历史身份、全区间价格口径或数据质量。静态路线存在，不等于同花顺 M2 数据源已经验收通过。

进一步区分：MCP图表的 `CandleQuerySchema` 确有30–500、默认160的工具包装限制；REST未走这个图表schema。日期范围分支不将limit传入下游，在已检查的返回映射与显式窗口过滤中也没有按limit取尾部的裁剪。这并不证明服务端没有其他限制。

当前研究目标仍为三年已验证数据集。研究区间 2023-09-04 至 2026-09-04、预热区间 2022-08-24 至 2023-09-01，旧试点契约分别 728 与 250 个交易日；每只证券仍按冻结 manifest、上市日期、退市日期、日历确定应有键，不能给所有证券强加 978 行，也不能按源返回起点缩减应有键。

## 2. Claude 当前交付核实与接管

完整读过 `M2_NEW_CHAT_HANDOFF_20260909.md`；核对了项目规则、协作协议、目标 M2 定义与 Section 15、协调状态、最近审查及两份交付。

| 项目 | 本次核实 |
|---|---|
| 既有 Claude 任务 | `M2-BOUNDARY2-REQUIREMENTS-CORRECTION-20260909`，只涉及两份需求文档 |
| Draft SHA-256 | `205ae057fc2c3823f991e397a6389565f051551bae5a06859f31be5cfc750885` |
| Dependency map SHA-256 | `8f0b8228ac3634167039c27eff24eca4833fafac33d7b24f652286710584e849` |
| 文件稳定性 | 多次读取得到相同哈希，与交接一致；原始收到版本已单独冻结 |
| 文档引用 | 44 处引用、28 个去重文件，哈希全部匹配 |
| 保护基线 | 91 个受保护文件全部匹配；G1 冻结的 46 个文件及路径集合全部匹配 |
| 自动化 | 实读 `automations/claude/automation.toml` 为 `PAUSED`，仍绑定旧 Codex 任务；没有恢复或重新创建 |
| Claude UI | 枚举到原窗口，但首次读到的是 New chat 页面，未看到目标 fork 的完成响应。尝试导航出现 `coordinate input geometry is unavailable`，刷新窗口后的恢复尝试出现 `failed to activate captured window`，已停止 UI 操作 |

因此可确认交付字节已落盘且可审查，**不能确认唯一 Claude 会话已结束**。协调 JSON 的旧 `submitted_observed_running` 也不构成当前运行证明。本次不重复发送任务，不把文件稳定性冒称 UI 完成证明。

独立静态复核结论：

| 发现 | 原交付结论 | 精确残留 |
|---|---|---|
| BQ-R1 | 部分修正 | Draft 130–134、351–353 与 map 271 将未观测的源覆盖混入“应有键未知”。应有键是合同；未知的是返回日期、覆盖和历史身份；未知上市日期按原规则 UNRESOLVED |
| BQ-R2 | 本项修正已核实 | Draft 201、205–220 与 map 268 仅保留 `unverified` 审计状态，不作为价格口径前置条件的放行选项 |
| BQ-R3 | 部分修正 | C4 测量阶段、share-only 日期及可选因果解释已修正；Draft 397 仍写“其余 51”，应为 49 |
| BQ-R4 | 部分修正 | 重复委托循环已去掉；map 137 的隔离机制缺失断言仍未限定为已检查代码，236–240 的当前正文仍写分析进行中 |

Codex 已准备精确修订补丁 `_m2_codex_review/tonghuasun_static_20260909/requirements_correction.patch`，并更新补丁内 Draft 对修订后 map 的哈希引用。**补丁未应用**；原交付及历史修订记录保留，避免在会话完成尚未核实时覆盖潜在写入。无需重新派 Claude，后续由 Codex 在唯一写入状态核实后收口。补丁的提出不等于原交付已四项通过。

修订还明确：新版请求现在即可声明合同应有键，并把源覆盖/历史身份标为未观测；相关观测是之后获授权采集与验收要产生的证据，不能新增“先采完其余49标的才允许起草请求”的循环门槛。

## 3. 逐层静态证据

本轮证据文件：`_m2_codex_review/tonghuasun_static_20260909/ths_il_evidence.txt`。该文件记录程序集路径、SHA-256、MVID、方法 token、RVA 和 IL 偏移。使用 `System.Reflection.PortableExecutable.PEReader` 读取文件与 ECMA-335 元数据；**未加载或执行被审程序集**，没有请求本机 HTTP、市场接口或客户端数据库。

| 层 | 定位 | 能证明什么 |
|---|---|---|
| 项目上层 | `daily_bar_cache.py:46,76` | 两个股票刷新入口先把 days 截到 500 |
| 项目适配器 | `tonghuasun_provider.py:209–247` | 再次截到 500；起止时间都传 None；验证全部返回行后再取尾部 limit |
| 固定上游 Python SDK | `distribution/sdk/python/src/tonghuasun_codex/client.py:210–232,505–522,571–572` | candles 接受 limit/start/end，直接将时间转 ISO 字符串传至 candle 路径；其函数默认 limit=200，README 的500只是示例 |
| MCP图表schema | IL文件4138–4212，关键4189–4194 | `CandleQuerySchema` 限30–500、默认160；不能用于推断REST上限 |
| 插件请求契约 | `ThsPlugin.Contracts.dll` 的 QuoteSeriesRequest / QuoteCandleRequest | 存在 StartTimeUtc、EndTimeUtc、Limit、Period、Adjustment 字段 |
| 插件数量规范化 | IL 文件 3031–3040，`NormalizeLimit` token `0x06000266` | `value <= 0` 返回200；否则 `Math.Min(value,5000)`。ResolveCore 在 2547–2550 调用它 |
| 时间转换与检查 | IL 文件 2554–2598、2846–2873 | 读取起止时间，转到中国时区；拒绝 end < start；不能把 UTC 日期直接当交易日期 |
| 正式 candle 路线 | IL 文件 775–823，`<LoadSecurityAsync>d__4.MoveNext` token `0x0600053D` | 无 start 时 `Create(...limit,end)`；有 start 时 `Create(...start,end)`；随后 `IDataAccessor.RequestCandleDataAsync` |
| 后备 candle 路线 | IL 文件 514–592，`<LoadFallbackAsync>d__5.MoveNext` token `0x0600053B` | 同样有计数与日期范围两种 `DataCenterExtension.RequestCandleV2` 分支 |
| 返回窗口过滤 | IL 文件 630–645、858–875、2874–2972 | 正式与后备结果经过显式时间窗口过滤；过滤判断排除小于开始/大于结束的时间，因此所见过滤规则包含两端 |
| 客户端接口 | IL 中 `ICandleParameterFactory.Create` 和 `DataCenterExtension.RequestCandleV2` 的参数签名 | 客户端本身声明并具有 start/end 与 count/end 的不同重载，插件没有虚构日期参数 |
| REST入口 | IL文件4217–4233 | 证券标识验证后调用 `IQuoteCandleService.GetAsync`，不走图表schema |
| 返回映射 | IL文件1013起、1412–1495 | `MapFormalItem` 与 `MapCandleReply` 映射/排序；已检查路径未见limit裁剪，2774的Take用于字段诊断摘要 |
| 客户端请求终点 | IL文件4253、4297、4341、4388及5479–5487、5817–5825 | `RequestCandleV2` 的实际程序集是 `Hevo.Api.Quotes.dll`；按数量或日期传到 `DataCenter.RequestDataV2Async`，此路径未见新的500截断；服务端实现不在本轮证据范围 |

已审插件 `ThsPlugin.Adapters.Hevo.dll` SHA-256：`19fbd89528ebe933cee267de34d63171afd47aef230132bd3574a3b81883469b`；MVID：`a1601fcd-097a-49b3-9a0a-cdabfd43b0e5`。本机 release、部署目录及固定上游的五个插件 DLL 逐个哈希一致。这是**磁盘部署证据**，不是当前宿主已加载相同版本的运行时证明。

冻结IL证据共5979行，SHA-256：`9d5b4c93210c1d2abb459531017130c9220f54ff93ccd67781f098a08d2135df`。静态检查器 SHA-256：`87b64fc70739bd07c1d4515f3988b4cf1d73495c2bac83d03d894b261ffb4930`。运行记录和输入程序集哈希保存在证据文件中；这不是行情响应捕获。

本地固定上游根：`C:\Users\Administrator\.codex\vendor\tonghuasun-agent-3c8fc58-loopback\tonghuasun-mcp`；release：`D:\TonghuasunCodex\releases\0.2.13\ths-plugin`；宿主插件目录：`D:\同花顺软件\同花顺远航版\bin\PluginSdks`。未获取新版本、未安装依赖、未读产品配置令牌。

## 4. 为什么旧证据不能排除同花顺

旧 `_m1_evidence/backfill_verify_ths_500cap.py`、`backfill_verify_ths_span.py`、`backfill_verify_ths_reach.py` 是读取库内已存日期、统计深度并计算尾部500日期的脚本。本轮只读其源码，**没有运行脚本或打开数据库**。它们没有底层 candle 日期请求实验，不能回答插件是否能按日期取得更早数据。

`M2_PILOT_AUTHORIZATION_REQUEST.md:76,98,106` 的旧路线排除，只能理解为当时项目适配器没有利用长历史能力。旧缓存较短、源标签为同花顺、样本集中500行，都不能把软件包装层限制提升为客户端/供应商限制；库存随日累积到501行也不是单次请求上限的测量。

据此：保留旧 Sina 证据及 FAIL；对同花顺另建明确的能力验证，不要求“为了清 EV6 再跑 Sina”，也不让同花顺新结果改写旧 Sina 失败。

## 5. 扩展不能只把500改成5000

1. **交易所身份。** `tonghuasun_full_code`（provider 313–322）会把 `SH000300`、`SH000001`、`000300.SH` 分别错误地转为 `000300.SZ`、`000001.SZ`、`000300.SZ`。原因是未优先保留显式 SH，而先按数字0开头进入SZ。Codex只抽取两个纯函数到隔离标准库 namespace 求值，未导入生产模块。现有测试324–334没有显式SH指数用例。响应校验以错误转换后的代码为准，不能修复请求本身的身份。
2. **market=1 的含义。** 已读 Contracts 枚举为 Unknown=0/CnA=1/Hk=2/Us=3；不能将1误报为“股票而非指数”的硬编码。
3. **调用路线。** 日常基准刷新 `daily_bar_cache.py:295–320` 独立走 AkShare/Sina；没有本轮证据显示已有基准库被上述指数映射错误污染。M2 `_m2_pilot/pilot_runner.py:346,353,383` 及 `provenance.py:40–44,80–85` 仍使用 Sina 路线，生产 provider 的改动不会自动改变M2入口。
4. **价格口径与单位。** 请求 adjustment/响应回显不是整段价格已被独立验证；旧股票量单位对照也不是所有指数或所有日期的契约。保留原始响应、请求参数和生产者版本，才能区分接口事实、适配转换与已验证口径。
5. **完整性与失败处理。** 日期分段若将来采用，应核实是否真的向更早日期推进、边界重复、缺口、空结果与返回截断。不能拿到非空尾段就报整段覆盖成功，也不能静默切换到其他源后仍标同花顺。

本轮没有修改这些生产代码；它们构成后续同花顺 M2 接入与离线测试的明确输入。

## 6. 静态复核结束后的最小待验证问题

这些是需要真实观察的问题，**不是已授权或已武装的采集方案**，本文件没有创建请求执行器、运行时配置或待触发任务。

- 对冻结目标区间内的老股票，计数请求能否实际返回超过500根，并覆盖应有键，而非静默截断？
- 给定较早结束时间及明确起止时间，客户端是否真的返回该历史区间？日期范围与计数方式在重叠区间是否一致？
- 显式交易所标识的指数能否返回正确证券；BJ920000 的历史代码身份如何核实？
- 原始返回的日期、OHLC、量额及价格口径证据能否满足 M2 契约？缺失、停牌、历史代码变更与非法数据能否明确区分？

优先验证对象是**本机同花顺市场行情接口**；本轮不自动切换数据源、不打开数据库。新只读样本调用及证据留存需要独立授权；52标的试点、staging回填、生产集成和生产迁移仍是之后的边界。

## 7. 保留状态、实际验证与后续负责人

- M1/M2a 的既有技术验证保留；本轮未重跑已闭环 smoke。
- P1 open；U-6 deferred；既有 eligibility 全 false；已审 Sina M2b capability FAIL；两次历史采集授权已消耗；历史 EV6 不改。
- U-1…U-5/U-7 的采纳与模块授权归属仍为 **Claude-reported, not independently verified by Codex**；不伪造授权收据，也不推断此前没有授权。
- HEAD `73f266d4165df48bacc6112f037537aed5fb7a58`，分支 `codex/control-plane-refactor`；暂存区为空。既有未提交工作保留。生产代码、服务、数据库、策略和知识库未改，实盘未启用。
- 本轮验证包括静态源码/IL交叉核对、纯函数隔离求值、引用哈希核对、91个保护文件及G1 46文件校验；这些不是市场样本测试或数据集验收。
- 独立复核：Codex子代理已最终只读复核本报告、关键IL与未应用补丁，未发现新的事实错误、授权越界或把补丁当成已关闭的问题；这不是Claude复核。最终收据确认两份原交付及全部Git已跟踪文件与接管基线相同。
- 本轮输出、冻结交付、补丁与可复现验证脚本均在 `_m2_codex_review/tonghuasun_static_20260909/`；不暂存、不提交、不推送。
- 后续 M2 负责人为当前 Codex 任务。Claude 不再派单；旧巡检保持暂停。UI不能核实影响原两文的安全合入，不影响已完成的同花顺静态结论。
- 协调文件已记录Codex接管、新的静态审查结果和停止Claude派单；旧任务、旧审查、旧授权文字以及完整接管前JSON均保留。没有修改自动化TOML，也没有把仍指向旧任务的heartbeat恢复。

**阶段结论：同花顺长历史静态能力复核有明确正向证据；真实数据能力与三年数据集仍未完成验收。**
