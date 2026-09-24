# M3-01-R2 Codex 独立验收

结论：**changes_required，本轮不通过；M3 尚未完成。** R2 已修正原始接口中的多项问题，但审阅账本、摘要和匹配结果进入下游计数时仍能绕过必要验证。当前计数不能作为“至少 50 个已独立复核正例、每例 3–5 个对照”的可靠证据。继续修正规则实现，暂不启动真实案例提取。

验收日期：2026-09-10。负责人：Codex。交付人：原 Claude `Fable 5.1 project advice (fork)`。本次先确认实际任务完成，再按完整交付冻结、静态检查和隔离执行；没有重复派单。

## 1. 已确认的交付与保全

Claude 最终回复为 Message 51 / `M3-01-R2-CONTRACT-FIX-20260910 — ready_for_review`，界面显示 `Claude finished the response`、空输入框和 Send。普通壁纸屏保退出后，点击已选中的同一任务刷新了滞后的界面状态；没有重启或打断 Claude。

| 对象 | SHA-256 / 结果 |
| --- | --- |
| R2 `artifact_manifest.json` | `34b28360fc9842876a2c321d7316bec2b7f1e0b3935f1cfd17711ac1857d7451` |
| `backend/app/research/m3_labels.py` | `fe6046476f492aca4487492e47477166f47d1cfe052167adf021c0bf238d17e7` |
| `backend/tests/test_m3_labels.py` | `6fd2aa983f6ab3d15d1f9b679af9dd35a149d22f6f7c52bb0db373a0dace0a7b` |
| 策略 / schema | `0.2.0-draft` / `m3.labels.output.v2` |
| policy_hash | `e2620649cf20e2e1d80c2ddd711e6420ec2b8ea3a3d5f900c1226b1d150d37e8` |
| 完整交付快照 | `_m3_20260910/codex/review_02_input/`；13 个交付文件、16 个来源逐一核对并保存；另核对 3 个保留原件 |
| 快照回执 | `review_02_input/receipt.json`：`d840c21aaebf755dff9e68b49061095a32e2ead13e61a4bf04e484b762757c3c` |
| 原 R1 交付 | `claude_01/` 清单及其 6 个交付文件保持原哈希；两个旧 backend 文件仍在 `review_01_input/files/` |
| M2 / 原有源码 | 316 个原有受保护源码文件、16 个生产文件位置、M2 各冻结证据组全部通过保全核对；没有建立生产数据库连接 |
| 保全回执 | `codex/preservation_review_02.json`：`95ab804d6f6a19e5fd4afb8c4948ad0d701ed2662331faa746ac14affeaa6a9e` |

本次完整阅读了 R2 的 DELIVERY、LABEL_POLICY 和 REGRESSION_MAP，核对实现及测试代码。没有运行 Claude 的交付生成器以改写其历史清单。

## 2. 实际执行结果

均使用项目 Python `-B -X utf8` 和 `codex/run_offline_review.py`。该执行器禁止 SQLite、网络、子进程及新回执目录外写入，直接运行 stdlib unittest 文件，不导入 app/conftest。每次运行前后测试源码与模块哈希一致。

| 检查 | 结果 | 回执目录 |
| --- | --- | --- |
| Claude R2 自测 | 71 项通过，4.403 秒，exit 0 | `codex/review_02_claude_tests/` |
| Codex 独立数值检查 | 8 项通过，0.003 秒，exit 0 | `codex/review_02_feature_tests/` |
| Codex 独立消费者检查 | 15 项中 3 项通过、12 项失败，0.432 秒，exit 1 | `codex/review_02_independent_tests/` |
| 冻结输入和原有文件保全 | 通过 | `codex/preservation_review_02.json` |

三个 `execution.json` 哈希分别为：自测 `1cc1a6ef8ac708ea7ed164a76fa405ddadf36c40855855d7e2d877247209cb3b`；数值 `bed02a60c6fc1bd2ec89fb118cdd141cd589f60a8e93c50363f6d8bf22d54de0`；消费者 `9be46e85823fff0578a7bc538111d684db6544c8d357f641f5eb4a260ee78f7f`。

可复现命令模板（末尾输出目录必须是新的 Codex 目录）：

```powershell
& 'D:/codex-A股交易/backend/.venv/Scripts/python.exe' -B -X utf8 `
  'D:/codex-A股交易/claude methods/_m3_20260910/codex/run_offline_review.py' `
  'D:/codex-A股交易/claude methods/_m3_20260910/codex/test_independent_r2.py' `
  'D:/codex-A股交易/claude methods/_m3_20260910/codex/NEW_REVIEW_OUTPUT'
```

独立消费者测试 SHA：`656cc5c10ac40968ca707ce78efe1e7edd562d6e5793c4f4d05eb45578c196e3`；数值测试 SHA：`eb600ca23c310fbe242c7b745e0fe87279847f0393beee5af6c897263ea677da`；执行器 SHA：`2871e44cba97c52e87891e3474ff18a2028d20d2c8de9ec67ec3e546f01b049d`。

旧 R1 的 18 项检查需要适配新增日历、审阅绑定等 API。Claude 的对应映射及 71 项实际运行证明了具体适配场景；旧文件直接运行产生的 13 个 API 错误不计作本轮新缺陷。本轮 12 个失败均来自已适配 R2 的独立检查，没有 API 构造错误。不同测试集的失败数量不能直接比较为缺陷减少比例。

数值检查独立手算了回报端点、250 根价格区间、成交量均值排除当天、成交额均值包含当天、未知分母和未来尾部隔离。它们通过只证明这部分数学实现，不能代替案例准入验证。

## 3. 六组阻止采用的发现

### R2-A：审阅账本的绑定和替代链未贯穿读取、追加与计数（P1）

实现位置：`m3_labels.py:1798` 的 `review_status`、`:1819` 的 `attach_review`、`:1881` 的 `library_counts`。

把案例 A 的完整合法账本接到案例 B 的合法核心后，再添加一条绑定 B 的审阅，可以成功。账本顶层的 `bound_*` 与已有条目并没有逐项与 B 核对。计数路径进一步直接调用 `review_status`，篡改旧条目的 `execution_ref` 而不更新账本哈希，也不会被拒绝。

此外，同一旧审阅被明确替代后还能再次作为替代目标，留下同一审阅者多个有效分支；更早时间的记录也能替代更晚记录。最终状态靠遍历时最后一个字符串决定，可能掩盖分歧。

四个直接反例分别是 `test_transplanted_valid_ledger_cannot_accept_a_new_case_review`、`test_library_count_rejects_tampered_ledger`、`test_superseding_an_already_superseded_review_cannot_fork_current_verdict`、`test_superseding_review_must_be_later_than_original`。应建立统一账本验证流程，在加载、追加和计数时重用；旧条目绑定、每条哈希、替代链和时间关系均须核对。

### R2-B：摘要只携带哈希字符串，仍可改变对照结论（P1）

实现位置：`m3_labels.py:1612` 的 `case_summary` 及后续匹配。

先生成三个真实规则输出为 candidate 的合成股票记录，再将其摘要中的 selection 改成 non_candidate，保留原 record_hash，匹配结果仍为 3 个有效对照、unmatched=false。摘要携带某个哈希不代表摘要字段受该哈希约束。`z` 重复 64 次也通过了标注为“64-hex”的检查。

反例：`test_compact_summary_cannot_relabel_candidate_controls`、`test_compact_summary_cannot_invent_record_hash`。需要从摘要引用解析回完整已验证核心并逐字段一致性核对，或明确只接收完整核心；摘要不能独立成为可信输入。

### R2-C：计数信任可修改的匹配汇总和门槛（P1）

实现位置：`m3_labels.py:1881` 的 `library_counts`。

将合法匹配的 controls 清空，把调用方提供的 k_min 改为 0，保留 control_count=3、unmatched=false，仍得到 qualified_positives=1。将对照换成池外股票与无效哈希也同样可计数。重复输入同一合成审阅记录，则 independently_reviewed 从 1 变成 2。

反例：`test_counting_cannot_trust_caller_lowered_control_minimum`、`test_counting_cannot_trust_changed_control_identity`、`test_library_count_rejects_duplicate_case_records`。计数必须按固定策略重新检查实际对照、完整核心、身份/版本/用途与唯一性；不得由汇总对象里的 k_min、control_count 或布尔值决定是否达标。

### R2-D：一天的决策记录被计为已成立的 episode / 有效组（P1）

实现位置：`m3_labels.py:1481` 的 episode 生成与 `:1881` 的计数集成。

一个已审阅决策记录生成的 episode 明确 `meets_min_sessions=false`，计数仍报告一个 effective_dependence_groups。最短三次连续决策的要求没有接到准入路径上；当前 qualified_positives 实际按日记录累加。

反例：`test_single_decision_cannot_establish_minimum_episode_duration`。需保存当时已知的 episode 前缀、首次满足持续时间的截点及成员证据，将日记录、合格 episode、依赖组分开。不能用事后完整终点补写早期资格，也不能先过滤成少数已审阅日再据此重建连续性。

原始 M3 要求是至少 50 个独立复核的正例 episode、每例三至五个对照；有效依赖组是另一个必须报告的统计量。策略应清楚区分这两个数字的含义，不以未经采用的计数捷径或隐含改写目标替代原始标准。

### R2-E：不可得上下文仍改变已消费决策的身份（P2）

实现位置：`m3_labels.py:1303` 的 `generate_labels` 及其 decision_inputs。

两份在严格截点都不可得的 ST 事实产生完全相同标签，context_usable 均为 false，episode_id 却不同，因为完整未消费事实仍进入决策核心。与“未消费上下文尾部不改变当前核心”的契约不一致；会导致仅补入未来事实就更换历史案例身份和审阅绑定。

反例：`test_non_consumed_context_does_not_change_decision_identity`。保留不可得事实作为诊断；核心绑定实际消费的有效上下文与证据，不把待用事实内容混入。保守的 unknown/不可得状态及严格 PIT 限制仍需保留。

### R2-F：参考收盘价可以被声明在该交易日前已可得（P2）

实现位置：`m3_labels.py:1145` 的 `validate_position_state`。

给某历史交易日收盘参考价标注前一年 available_at，仍可生成持仓事件。当前只检查其不晚于决策截点，没有检查价格基础对应的最早可得时间。

反例：`test_session_close_reference_cannot_be_available_before_reference_date`。按 session_close / next_session_open / declared 等参考基础验证证据时间关系，未证明的基础保留 review_required，不能因数值恰好相等就称为已核实。

## 4. 测试证据与事实范围

所有反例均为内存构造价格和审阅引用，未读取真实市场价格。三个计数边界测试使用真实格式的股票代码和 flag 值，以覆盖非合成准入分支；引用始终明确 `syn:fixture-only`，没有保存为真实案例，也不代表实际审阅。Claude 自测中的零 qualified positives 主要覆盖合成排除分支，因此不能证明实际准入分支可靠。

工作版本预检查和本次正式验收分开存放。本报告只采用完成后固定的 `fe604647…` 版本及 `review_02_*` 执行证据作为验收依据。

M2 仍是 50 只股票与 2 个指数的冻结范围。股票中两只具有 9 次已知现金事件的部分证据，其他 48 只的公司行动覆盖未知；指数不能算作额外股票或股票公司行动案例。整体 strict PIT=false，尚无真实 M3 案例、独立真实审阅、训练或交易效能结论。

## 5. 后续任务与验收目标

保持 M3 原目标和 15 分钟巡检。R3 只修正以上消费者一致性、episode 准入和证据时间约束，继续使用合成输入；四类标签、已定的同日匹配要求、阶段阈值、流动性/市场状态阈值和研究切分不因凑数调整。

R3 通过后才冻结策略并派发开发区间的只读案例提取，随后完成真实正例和对照的逐案独立审阅、分歧处理及依赖审计。不会把模块测试通过等同于 M3 完成。

Claude: Read this review and `M3_01_R3_CLAUDE_TASK_20260910.md` in full. Fix the six coherent consumer-contract findings, retain meaningful prior scenarios, and deliver a new stable `claude_01_r3` manifest. Preserve R1/R2 evidence and all Codex/M2 files; do not start real-case extraction or claim M3 complete. Codex owns independent acceptance and the next dispatch.
