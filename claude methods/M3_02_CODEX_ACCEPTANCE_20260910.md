# M3-02 冻结读取器与开发案例材料：Codex 独立验收

结论：**通过，允许进入 M3-03 的实际逐案例审阅。M3 尚未完成。**

本次验收针对 Claude 在同一 `Fable 5.1 project advice (fork)` 任务提交的 M3-02，最终运行是 `dev_run_02`。已观察 Message 63 的 `ready_for_review`、完成状态及清单哈希，核实文件与此前独立检查版本相同。期间未重复派单；两份有复现证据的反馈均并入原任务。

## 交付与版本

| 项目 | 固定值 |
|---|---|
| 最终清单 | `claude methods/_m3_20260910/claude_02/artifact_manifest.json` |
| 清单 SHA-256 | `4aa337d9840c970700bad7f2566af7e7a84a486ec8180c1b0295664bc0662962` |
| 读取器 | `backend/app/research/m3_frozen_reader.py`，`288594cf0acf977c5ede3f5dec6584134a879889793c4c3542d01b1d7f7ae5af` |
| 交付测试 | `backend/tests/test_m3_frozen_reader.py`，`22e79001acc1e58febd7865fbf01facd927488c87fc1ed2cfbd6d7c287b608ce` |
| 标签内核 | `e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393`，未修改 |
| 策略哈希 | `d436ba1402f9d0b53e1008c2a2bd50678a457c3e050561a59ded30dbbd21c025`，未修改 |

816 个声明产物、32 个来源及 20 项保留对象全部通过哈希核对。Codex 在 `codex/review_m3_02_input/` 保存完整产物及 30 个普通来源的字节快照；两个候选 SQLite 只校验字节哈希，不复制或连接。快照回执 SHA-256：`d685ab61c9cdf999324efb8d4983dbf1dfc8b94667c2c61850e58956c6c8beff`。

## 独立验证结果

| 层面 | 实测结果与证据 |
|---|---|
| 代码与交付测试 | 20 项通过。Codex 在自己的新临时目录执行原测试，仅在内存中重定位合成夹具和输出目录常量；原代码、真实来源与策略常量不变。独立审计钩子限制 SQLite 只能连接该临时夹具，禁止网络、子进程及目录外写入。`codex/reader_delivery_tests_isolated_01/execution.json`，哈希 `bfcc8eb85af2cb94dec629daf412061eec31063e99bc1a535e976900c4038a00`。 |
| 额外边界检查 | 4 项通过：扩大真实日期、替换真实来源在 I/O 前拒绝；构造不读文件；嵌套连接各自保存关闭后哈希。`codex/reader_working_boundary_tests_02/execution.json`，哈希 `b022ce18d8500b8b020c9103e9b0371a0be20c0757439af2dd6d27f68194aa9e`。 |
| 材料延伸不变性 | 4 项通过：有效路径仍产生 3–5 个对照；改变后续阶段终点、状态和资格轨迹不改变截点材料；错误前缀绑定及未来日期对照被拒绝。`codex/reader_working_packet_extension_tests_01/execution.json`，哈希 `12a293d914748ee7c2d4bfcecf36afde8bdd69d3f8ed1b6a08346e06fbba5def`。 |
| 独立来源对账 | 两个固定候选库只读核对：27,900 条价格（含预热）、200 条停牌证据；数值、键、证据关联、资格与日期完整性一致。`codex/development_input_audit_01/result.json`，哈希 `dd3ac6ffde13ba0127a39163d23e3cebb148ca9a93f90d25c17cd4a22402d157`。同源两库一致表示存储对账通过。 |
| 全部来源到记录复算 | 不导入 Claude 读取器，独立组装请求并使用已验收标签内核重算最终运行的全部 17,554 条记录。所有核心字段、特征、标签及哈希一致，0 差异；仅连接一次固定候选 trading 库，选取价格截至 2025-03-31，数值摘要与前述两库独立对账完全一致。`codex/reader_chronology_source_review_02/result.json`，哈希 `a0a0e3013ba3f796385fd2a886d4ce4bf0e737edf376b3072ad015ccda7ca4a1`。 |
| 全部阶段与对照材料 | 从已经来源复算的完整时间序列重建 1,626 个阶段，核验全部 225 个材料前缀、成员/代表记录、完整同日对照池、排序、选中对照、内容哈希及统计。32 个匹配、108 个对照不足、85 个代表日非候选；依赖组及复用统计一致。`codex/reader_episode_packet_review_03/result.json`，哈希 `b8d445a913bc5dac6386ad73696fc0084d84b7383e3005f22c5637c6edfbbde9`。 |
| 保留与运行边界 | M2 冻结证据、316 个原有跟踪文件、16 个生产文件位置，以及 M3-01/R2/R3 的现存交付文件通过保留检查。`codex/preservation_m3_02_checkpoint_01.json`，哈希 `80d8aea576c90ac6b4bf4766801416310e3a9b8eff7a43babb3b3bbc876b8694`；`codex/reader_delivery_static_validation_01.json`，哈希 `1a519998a90c15cbaef663f533a1cc3ab8e53a6b4639d76a69daec4c9f96df7b`。 |

上述“来源到记录复算”是实现与数据绑定验证，**不是实际逐案例审阅**。本阶段审阅账本均为空，实际审阅正例为 0。

读取器的最终真实运行记录两次候选库只读连接、24 条 SQL，其中 10 条带日期参数，参数均为 `2025-03-31`；读取了 `query_only=1`，两个库关闭后的哈希分别正确。Codex 的独立运行另有明确回执。没有生产 SQLite 连接、网络采集、账户/资金访问、订单或 M4 工作。

## 已闭环问题及保留记录

初版允许调用者替换真实配置，构造时读取文件，待审材料还混入代表日之后的完整阶段终点及资格变化。两份反馈分别是 `M3_02_WORKING_BOUNDARY_FEEDBACK.md` 与 `M3_02_WORKING_PACKET_CUTOFF_FEEDBACK.md`；原始测试与 225 份材料审计均保留。最终读取器固定真实配置、限定合成/输出范围、推迟文件读取、记录 SQL 参数，并把后续阶段信息移至明确标注的事后盘点文件。

首轮 `dev_run_01` 完整保留。最终运行统一了股票池来源引用的格式，所以记录及前缀哈希变化；未沿用旧哈希作验收。Codex 使用相应引用格式重新完成了全部 17,554 条最终记录复算。

独立材料核验的前两次未通过也保留：第一次拒绝将首轮字节哈希直接用于第二轮；第二次是 Codex 计数器遗漏显式 `missing=0` 键，非交付缺陷。修正核验器后完整重跑通过。交付测试内一条 `or True` 的冗余断言不作为后续阶段变化证据；实际后续记录变化检查及 Codex 的独立正向/反向材料测试提供了有效证据。

## 案例盘点与用途限制

开发区间为 2023-09-04 至 2025-03-31，共 378 个交易日。固定总体是 50 只股票和 2 个指数；股票的 18,900 个潜在“股票×日期”键中，1,346 个尚未上市，形成 17,554 条决策记录：17,402 条当日有价格、152 条当日停牌，未解释缺失为 0。预热数据另外保留，未消费验证期或最终留出期的价格。

阶段盘点得到 342 个吸筹代理阶段，其中 225 个达到三交易日前缀要求；140 个代表日是候选，32 个具有 3–5 个合格对照，108 个对照不足。32 个待审潜在正例对应 23 个依赖组、127 个不同对照记录及 127 次对照使用。阶段、决策记录与依赖组分别统计，不能相互替代。

即使后续 32 个案例全部获得实际双重审阅支持，固定开发区间仍不足原目标的 50 个正例。保留这一有穷盘点结论，不能调阈值、扩总体、挪用留出期或以合成数据补数。后续必须真实审阅现有案例，并报告拒绝、模糊和分歧，才能完成 M3 的最终技术收口与限制说明。

用途仍限回顾性、隔离的研究材料：`strict_pit=false`、`training_eligible=false`、`review_only=true`、实盘关闭。历史 ST、流通股本、换手和名称未知；公司行动仅有两股的部分已知现金事件，其他范围未知；上市证据等级、预热不足及 BJ 单一口径例外继续保留。当前结果没有证明市场预测或交易效果。

## 下一步

由 Codex 固定仅包含代表日及以前信息的审阅包，派发 M3-03：Claude 与 Codex 分别逐案检查 32 个待审潜在正例及其 3–5 个对照，保存具体依据、反证、限制、审阅类型、执行证据和前缀绑定。保留原核心与双方原结论，随后独立汇总分歧、实际通过数和依赖统计。15 分钟巡检继续；M4 另行启动。

Claude next-stage instruction: Execute only the subsequently dispatched M3-03 task against the pinned cutoff-only review bundle. Review each available episode and every selected control individually, retain uncertainty and dissent, bind each review to the exact core and prefix with actual agent execution evidence, preserve all M2/M3 deliveries and the frozen policy, and stop at ready_for_review. Do not treat automated recomputation as an individual review or use later episode information to decide a cutoff verdict.
