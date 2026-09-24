# M2b R2-ABC 闭环独立复核（Codex，2026-09-08）

## 当前结论

**M2b R2-ABC 剩余修正已在限定离线范围内技术通过（validated）：零股本分母状态、R1 日期序列校验和现行授权交接均已闭环。来源能力仍为 FAIL；这不是 M2b 来源能力验收或用户最终 accepted。**

复核期间观察到 Claude 继续写入实现：先更新分母状态函数，再更新 R1、测试，产生独立的 `revision_20260908T082833Z_r2abc_v2/`，并于 17:27 更新交接文档。因此本报告针对下表所列最终代码哈希及 17:29–17:30 读取的交接状态，而不是本轮开始时仍有四项失败的旧实现。Codex 未改动 Claude 的实现、原报告、原验收脚本或交接文档。

两次真实采集分别为 `20260908T021722Z`、`20260908T082833Z`；两次单次授权均已消耗。**当前没有新采集授权。** 离线验证通过不授权再次采集、52 标的试点、生产入库或训练，也不代表三年数据、特征、标签或策略已就绪。

## 验收项

| 项目 | 本轮结果 | 证据 |
|---|---|---|
| 零股本观察中断旧分母 | 技术通过 | `sina_klc_decoder.py:487`、`:502`、`:550`；正—零—正、连续零值、末尾零值、前导零值、空序列、真实缺观测的向前沿用，以及逐日起点覆盖均按预期 |
| U4 实际消费修复 | 技术通过 | `smoke_checks.py:1179`；独立端到端夹具区分序列开始前缺失与显式无效状态，两者之和等于缺失分母行数；不把无效区间重新接回旧正值 |
| R1 日期序列及一致性 | 技术通过 | `smoke_checks.py:432`；拒绝无实际日期、行数不符、首尾元数据不符、重复、倒序、股票窗口外日期及伪造日期；合法短序列通过，指数全序列使用独立接口约束 |
| 新修订与证据保全 | 技术通过 | v2 的五个生产者哈希及七个输入哈希一致，离线重算与存储结果一致；旧修订没有被覆盖 |
| 当前交接状态清理 | 通过 | 执行目标文件第 15 节已明确两次执行、两次授权消耗、无第三次授权；旧冻结哈希与当前生产者哈希分开，旧授权文字标为历史；来源能力仍为 FAIL |

U4 的独立合成夹具以 **728 个研究交易日**为分母，另有 **250 个预热交易日**；不能将含预热的 978 行当成 U4 的研究行数。独立驱动初稿曾混淆此范围，已修正测试输入及期望，未修改实现。修正后 48 项契约与保全检查全部通过。

## 实际执行结果

工作目录：`D:\codex-A股交易`，分支 `codex/control-plane-refactor`，HEAD `73f266d4165df48bacc6112f037537aed5fb7a58`。

| 执行 | 结果 | 解释 |
|---|---|---|
| Claude 的 `test_m2_smoke.py` | **182 cases, 0 unexpected，exit 0** | 使用项目 Python、`-B -X utf8`，由 `runpy` 执行，并附加审计钩子拒绝文件型 SQLite 打开；套件自带网络/代理/HTTP 阻断 |
| 未改动的 `review_m2b_r2abc.py` | **39 项，36 通过，3 失败，exit 1** | 上轮四个功能失败断言现全部通过；三个失败分别为旧生产者哈希、旧存储重算一致性、旧确定性哈希，不是三个新功能缺陷 |
| 新的 `review_m2b_r2abc_closure_codex.py`，含 v2 重放 | **76 项全部通过，exit 0** | 48 项契约/保全检查加 28 项修订、来源及真实保留输入检查；并非与其他套件互不重叠的样本数 |
| Claude 新增的 `closure_r2abc_v2.py` | **49 项全部通过，exit 0** | 实际计数是 49，不是交接中写的 48；属非阻断的记录勘误，哈希与文档所列 `63f73196…` 一致 |
| `git diff --check` | **exit 0** | 仅有已有文件的 CRLF/LF 提示；此命令不覆盖未跟踪文件的所有格式检查 |

独立驱动复现命令：

```powershell
& 'backend/.venv/Scripts/python.exe' -B -X utf8 'claude methods/_m2_codex_review/review_m2b_r2abc_closure_codex.py' 'claude methods/_m2_smoke/revision_20260908T082833Z_r2abc_v2'
```

原始测试输出和保全结果保存在 `_m2_codex_review/r2abc_closure_codex_results.json`。没有重跑无关后端全套、M0/M1/M2a 或已验收 F8 修复周期。

## 新修订验证与边界

v2 的确定性 SHA-256 为：

`099640a21e5927a057f3d2d1468b5765312bf1b68ff0d056051a18317fc81292`

它与旧 `r2abc` 的 `c23f44bc…` 不同。对比两个确定性块，顶层仅 `checks` 改变；仍有 71 项检查，仅两项 U4 与三项 R1 的计数、阈值或说明改变，**没有任何检查状态、总判定或试点授权状态改变**。

真实保留输入上，两只股票的适配器分别返回 978 行，区间 `2022-08-24..2026-09-04`；指数返回 5,987 行，区间 `2002-01-04..2026-09-07`。D1、D5、R1 在适用标的上均通过。SH/BJ 辅助序列分别保持 26/42 条，其中 BJ 两个零值及原因保留。

仅两项必需检查失败：`EV6/sh600011` 和 `EV6/bj920000`，均为采集时 `undecodable` 与当前离线解析 `decoded` 的版本差异。EV6 没有被豁免；两个原始采集 FAIL 记录没有被改写。

两个真实研究窗口各有 728 行可用分母、零行缺失；本次修复针对一般无效区间，不声称这两个既有窗口已遭错误分母污染。SH600011 分母最大沿用年龄仍为 2,516 天，此处没有新股本观测。BJ920000 的结果也不能外推至其他 BJ 标的。

本次验证绑定的生产者哈希：

| 文件 | SHA-256 |
|---|---|
| smoke_capture.py | `059d0c43547db0bf520afc9c034dbc5c1638b3beb12c77e35e62ace03f85ad35` |
| smoke_checks.py | `4b062a55fae6f9bd348a7ffdf20073debababffafc71568e2aaaf8181c832bbe` |
| smoke_outcomes.py | `5bbb6ef052a309c84aaa69d43c721470670ca4428ab6747ad0993e5ad4607ec0` |
| sina_klc_decoder.py | `c6d736b170c29009ef273ed7705330f2a251545bca720d55c998d0a715f83fc8` |
| test_m2_smoke.py | `23b917c51d4bb3f880571df5baeabedd394a043654694643623d238c756742db` |

注意：v2 溯源中的 `accepted_in_revision_...r2abc` 字段及 “Codex accepted” 措辞只能指上一轮**部分技术通过**的生产者记录，不能解释为上一轮已最终验收。本报告澄清其含义；不要为修改措辞覆盖已保留修订。

## 交接复核与非阻断勘误

复核开始时，`THREE_YEAR_RESEARCH_EXECUTION_GOAL.md` 第 15 节存在四处主要冲突：只有一次采集、第二次授权未使用、165 项旧测试列为当前状态、历史段落结束后再次要求重触发。17:27 的更新已修正这些现行表述：

- 第 1028 行起的现行块明确两次采集、两个 FAIL、两次单次授权全部消耗、无新增授权、C1/C2 离线复核与 EV6 不豁免。
- Boundary 1b 标题及正文已改成两次执行；Current state 区分历史 D1/D2 冻结与当前五个生产者哈希，当前套件为 182 项。
- 历史授权段落及其中的旧纠正备注均有明确历史说明；最后的 Current position 再次明确两次授权已消耗。
- 请求文件第 24 节描述新 v2 修订、原 reviewer 的预期版本差异，以及来源能力 FAIL，未伪称获得新采集授权。

仍有一个**非阻断记录勘误**：执行目标第 955 行和请求文件第 1866 行将 Claude 闭环驱动写为 48/48；实际同哈希驱动输出为 **49/49**。这不改变任何 PASS/FAIL 或授权状态。只需纠正文档数字，不必改测试或重做采集。五个生产者之外的新驱动 SHA-256 为 `63f73196207f13c4c3e0fd9e1da1455e68cf5e997948c1e36e904648f694372d`。

## 数据、安全与写入范围

本轮建立基线的 **94 个旧文件**（既有证据、修订、回执、冻结实现、M1/M2a 与既有 reviewer 文件）哈希均未变化；新增 v2 采用新目录。独立 v2 验证期间全部九个保留目录及五个源文件也保持不变。

生产 SQLite 主文件及 WAL/SHM 的大小、修改时间保持一致。仅检查文件元数据，没有打开生产数据库；这不是生产库全内容哈希证明，也不证明此前全部活动。当前已知项目服务/行情循环匹配数为零，未观察到 8000/5173/4173 监听；这是一次只读快照。

Codex 写入范围仅为本报告、新独立驱动及本地结果 JSON；合成夹具使用临时目录并清理。未改动实现、数据集、策略集、知识库或原验收脚本；未启动/停止服务、采集、访问令牌、Git 暂存/提交/推送。HEAD 未变、暂存区为空。所有本轮文件仅供本地验收，不得提交。

## Follow-up instruction for Claude

Codex technically validates the bounded offline R2-ABC closure on the five producer hashes listed above. C1 denominator validity, C2 actual-date-sequence consistency, and the operative two-captures/two-consumed-authorizations handoff are closed. This is not source-capability acceptance, user acceptance, corpus certification, training readiness, or authorization for another capture. Preserve those sources and every existing evidence, revision, receipt, frozen directory, and reviewer artifact. Do not reopen the accepted M0/M1/M2a or F8 work.

Next action: record this bounded technical validation in the current handoff and correct the clerical closure-driver count from 48/48 to the actually observed 49/49 (same driver hash `63f73196...`). This is documentation-only; no implementation change or repeat test cycle is required for that number. Keep both consumed authorizations explicit. The current offline revision remains `revision_20260908T082833Z_r2abc_v2`, the smoke suite is 182/182, Codex's independent closure is 76/76, and source capability remains FAIL on the two EV6 parser-version disagreements. Preserve old pins, counts, and authorization terms as dated history.

Report the unchanged old reviewer's 36/39 result honestly: the original four functional expectations now pass, while the producer-pin and two stored-result comparisons fail across versions as expected. Never edit the old reviewer or old revision to turn them green. Treat the earlier R2-ABC review as partial technical acceptance, not final acceptance.

Stop after that documentation-only acknowledgment; do not mark the overall source-capability milestone accepted. Do not request or execute a third capture merely to clear EV6. No HTTP/plugin call, filesystem SQLite open, production mutation, service action, token access, dataset/strategy/knowledge edit, training, pilot, Git staging/commit/push, or source expansion is authorized. Do not commit any methodology or Codex/Claude-related file. Passing these tests establishes only this bounded offline correction scope.

## 后续文档闭环复核（2026-09-08，Codex）

**通过。上述非阻断的 48/49 计数勘误已关闭，技术通过结果的交接记录已完成；无需继续重复这轮修复或文档确认。** 前文及其英文后续指令保留为当时的审查记录，本节是该文档闭环的最新结果。

- 执行目标文件原第 955 行、请求文件当前第 1868 行均已写成 49/49，并说明原 48 是汇总笔误。读取上一轮保存的驱动输出确认 `total=49, passed=49, failed=0, exit=0`，本轮未运行驱动。
- 目标文件第 15 节与请求文件第 24/25 节准确区分限定离线范围的 `validated`、来源能力 FAIL、尚无用户 `accepted`、尚未具备训练就绪证据；两次单次授权均消耗，没有新增授权。
- 36/39 的一个生产者哈希比较与两个旧存储结果比较明确标成跨版本差异；上轮四项功能期望已通过，旧脚本与旧修订没有为变绿而修改。
- 五个生产者文件及闭环驱动 `63f73196…` 哈希与上轮复核一致；七个输入哈希在父证据和 v2 副本间一致；既有基线中的 94 个文件均无哈希变化。
- 仅读取 JSON 并重新计算其规范化摘要：旧修订仍为 `c23f44bc…`，v2 仍为 `099640a2…`，各 71 项检查，EV6 两项 FAIL、来源能力 FAIL、`authorizes_pilot=false`。这是文件完整性核对，不是再次执行适配器重放或测试。
- HEAD 仍为 `73f266d4165df48bacc6112f037537aed5fb7a58`、暂存区为空。生产库仅核对文件元数据，与已有基线一致；未打开 SQLite。本轮 Codex 仅追加本复核记录，未改 Claude 的两份文档、实现或保留证据。

本次核对的文档 SHA-256：执行目标 `004445834fc1e2d1ee9152300a1304b90d3bd26db84a71467de1d84a5c74f202`；请求 `3d4e057015e7f6b1e221c38653af6026b0b0c49273fb0f5f5679c728b9934e46`。核对范围内的文件与记录支持文档闭环结论，不将文件快照当作对全部历史进程活动的证明。

### Next-stage instruction for Claude

The documentation closure is verified. Do not reopen R2-ABC, rerun its unchanged suites, or produce another acknowledgment-only revision.

Prepare one concise offline decision memo for the next source-capability stage using only the current code, retained evidence, and existing request. Separate what is already established, what remains substantively unverified, and the historical EV6 parser-version disagreement. Explain whether an additional capture is justified by unanswered end-to-end questions rather than merely making EV6 green. If justified, describe a proposed validation boundary using the existing three symbols, five-request plan, and unchanged limits, with exact evidence, success/failure criteria, preservation rules, and required fresh authorization. If no additional capture is justified, say so. Planning does not authorize execution.

Limit writes to that local, uncommitted decision memo under `claude methods/`. Preserve all current sources, datasets, strategies, knowledge, evidence, revisions, receipts, frozen bundles, and reviewer artifacts. Both previous capture authorizations remain consumed. No HTTP/plugin call, capture, SQLite open, production mutation, service operation, token access, pilot, training, source expansion, Git staging/commit/push, or live trading. Stop at `proposed` for review; do not execute the plan or claim source-capability acceptance.
