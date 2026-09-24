# M4-03B Codex 独立复核：需要两处定点修正

复核对象：Claude delivery 01，manifest SHA-256 `5ed90a61f37c0af812854d895b1ab1d803d06c8153ab2a23c636944c4412632a`。已在原生 ZK-trading / Fable 5.1 project advice (fork) 界面看到“Stopping here for Codex review.”。29/29 写入、32/32 消费文件哈希匹配；四份冻结清单、316 tracked、42 immutable、16 production positions 保持不变。原始交付已复制至 Codex 的 `replay_review_01/delivery_snapshot/`，只作证据，不允许 Claude 修改。

复核未连接 SQLite、网络或客户端。只读审阅 Q1-Q9、guard、runner、core、全部13项合成测试；隔离重跑13项全部通过。另执行26项独立检查，21项通过、5项失败归属以下两类问题。每个历史分支都独立按逐笔流水重新计算现金、费用、FIFO成本、已实现损益、T+1与容量；全部匹配。所有导出 output hashes、全局开盘先于收盘顺序、其他持仓只用前收盘、排除漏斗及假设标签通过。复核没有重新执行历史数据库读取，也没有将重复输出 hash 校验冒充历史全量重放。

1. **P2 — replay_core.py:565 — 自定义初始现金的绩效分母错误。** 构造器允许 `initial_cash`，但 `_finish()` 给 `performance()` 的值写死为全局1000000。独立零交易样本使用100000，终值100000，被报成 `-0.900000`，应为0。当前历史任务恰好使用1000000，因此已交付历史数值未受影响；已有多个合成fixture使用非默认现金，其绩效输出不可信。请保存并使用实例实际初始现金，覆盖非默认现金零交易和非零收益两个手算例子。

2. **P2 — replay_core.py:555–573 — 最终绩效缺少基准输入的结构化来源。** `_finish()` 用SH000300两个端点计算或拒绝基准，但 performance wrapper 的 `raw_provenance` 只导出持仓，四个分支都缺 `SH000300/2023-09-04` 与 `SH000300/2025-03-31`。这违反本任务包括benchmark/performance在内的逐记录来源要求。两个端点已存在于原始首/末 decision wrappers，无需再读数据库。请补起止角色、symbol/date/raw_sha256/point_index/captured_at，并明确基准的模型时间与假设；raw分支保留真实capture与拒绝原因。最终绩效使用默认listed状态的假设也应在wrapper声明。

证据：`replay_review_01/{hashes,preservation,delivered_tests,independent_checks}.json`；复现脚本 `codex/probe_replay_01.py`（Codex输出路径固定，不让Claude直接运行覆盖）。当前分支手算终值分别为 capacity_none=1000000.00、fixed_5000=1050431.74、full_fill=954371.97、raw=1000000.00。以上仅是假设下的账本核算，真实历史资格仍未通过。

## Claude correction instructions — same task, bounded revision 2

Fix only the two verified issues above within `claude methods/_m4_20260912/claude_03b/`. Keep the four prior freezes, all M2/M3 files, production, Codex files, PLAN and coordination state read-only. No new SQLite connection (the original two authorized read connections are consumed), network/client access, rerun of `run_m4_03b_replay.py`, or policy/strategy/fee/capacity tuning. Do not create a new historical read proposal merely for these output fixes.

Preserve delivery 01 scripts, report and manifest before replacing them; keep the original `runs/829d42809e978c04/` files byte-identical. Correct future core runs to use the actual instance initial cash and include complete benchmark/performance provenance. Re-run focused synthetic tests under a zero-SQL/network/outside-write guard, adding the two non-default-cash arithmetic tests and assumed/raw benchmark-endpoint provenance tests. The original frozen engines must remain byte-identical.

For existing historical output, implement a deterministic **export-only** repair that consumes the hash-verified original delivery outputs. Derive endpoint provenance strictly from the existing first/last decision wrappers, including both raw and assumed branches; do not invent or silently reconstruct missing sources. Write a distinct revision folder, never overwrite the original run. Preserve every nested engine record and ledger record byte-equivalent under canonical JSON, all prices/fills/cash/FIFO/PnL/performance numerical values, original input/model hashes and original historical run receipts. Only the enclosing performance metadata and resulting export hashes should change. The actual historical initial cash was already1000000, so it needs no numerical rewrite.

Apply this pure export transformation twice from identical original bytes and compare hashes; explicitly label this as deterministic export repair, **not** two new historical replays. Preserve the original historical two-repeat results separately. Pin corrected source hashes and transformation code/input/output lineage; a separate revision identifier must distinguish these corrected exports from the original run. Fail if endpoint records are absent or conflicting.

Write a concise revision report distinguishing (a) the original guarded two-connection historical run, (b) zero-connection export repair, and (c) corrected synthetic performance validation. Keep raw retrospective B0 diagnostics clearly unavailable, `M4_complete=false`, `strict_pit=false`, `training_eligible=false`, `review_only=true`, `live_trading_enabled=false`, `M5_started=false`. Reverify all freezes, 316/42/16 baseline entries and candidate hash/stat/sidecar state. Write final manifest last and stop ready_for_review; no self-acceptance or further stage.
