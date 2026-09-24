# M3-01 R3：Codex 独立验收

日期：2026-09-10。结论：**M3-01 标签与消费者契约通过技术验收，可冻结用于下一步开发区间的回顾性案例准备。M3 整体尚未完成。**

本结论包含对实际 Claude 结束状态、完整交付清单、源码、合成运行、数值核算和旧证据保全的独立核对。真实案例提取、逐案例双重审核、目标数量与不足证据仍待完成；没有训练就绪、投资有效性或实盘能力结论。

## 1. 接收的完整版本

已在原 `Fable 5.1 project advice (fork)` 核实 Message 57：`ready_for_review`、指定清单哈希、`Claude finished the response`、Idle、空输入框和 Send。没有依据文件出现就提前认定交付完成，也没有重复派单。

| 项目 | 冻结值 |
| --- | --- |
| R3 清单 | `7060f61f8eb637d6e92efb075e6a0cfdad041e370d30874afb9172a2d04fce39` |
| 标签模块 | `e20eb21cdea032ced319a8f45a34cdeb03fd4d8b357ac31403306fa73b225393` |
| Claude 测试文件 | `41eba60b21b507250f9a9a4f359fdc330232306c61b535f3d82db18ba9e45180` |
| 策略 | `0.3.0-draft` / `m3.labels.output.v3` |
| policy_hash | `d436ba1402f9d0b53e1008c2a2bd50678a457c3e050561a59ded30dbbd21c025` |
| Codex 快照回执 | `b93345206aae5f3292e85bcc8e97bfa7b4011bbff1c3364736d81eafb6d75f0c` |

17 个交付文件、31 个声明来源及 11 个保留原件逐项核对通过。快照位于 `claude methods/_m3_20260910/codex/review_03_input/`，包含交付与来源当时版本。机器策略规范化 JSON 重算的哈希与模块运行、清单一致。版本名保留 `draft`，避免改名引起无意义的身份变化；采用范围由本验收及独立 `policy_freeze.json` 明确限定为 M3 探索性研究。

## 2. 运行证据及修复结果

| 独立执行 | 结果 | 能证明什么 |
| --- | --- | --- |
| Claude 交付测试 | 105/105 通过，6.317 秒 | 新旧接口及主要回归场景运行通过 |
| Codex 准入检查 | 24/24 通过，1.190 秒 | 有效阶段能计数，篡改、缺证据和未绑定审核不能计数 |
| Codex 数值检查 | 8/8 通过，0.003 秒 | 关键价格窗口、均值、收益端点、零分母和未来后缀的算术符合当前定义 |

三组执行均退出 0，执行前后模块哈希一致，并与最终交付一致。目录为 `codex/r3_working_claude_tests_01/`、`r3_working_bound_tests_01/`、`r3_working_feature_tests_01/`；名称中的 working 表示这些执行略早于 UI 最终结束观察，不表示另一版代码。最终逐项绑定结果保存在 `codex/review_03_validation.json`，没有用旧版本结果替代当前结果。

受限执行器禁止 SQLite 连接、网络、子进程和输出目录之外的写入；三次执行均没有触发被拒事件。所有输入是内存中的合成数据。采用真实格式证券代码和 synthetic=false 的少量夹具明确标注为 fixture-only，仅覆盖真实格式准入分支，没有保存为实际案例或实际审核。

本轮关闭的主要问题：

- 审核账本在加载、追加和计数时验证完整绑定、条目哈希、替代关系、时间先后和缓存状态；移植另一案例的账本被拒绝。
- 摘要必须解析到已验证原记录，计数重新检查所引用的正例和对照；伪造数量、阈值、证券身份与重复记录不能增加合格数量。
- 三个连续交易日的阶段证据与代表记录对应。审核显式绑定 `case_prefix_hash`；替换早期成员证据后，原审核不能转移到新前缀。仅有日级审核、单日记录或中间缺日不构成合格阶段。
- 决策指纹重算其声明的输入，并检查关键重复字段。未来不可用的上下文和覆盖率留在诊断中，不改变已消费输入的身份。
- 参考价按下一交易日开盘或相应交易日收盘核验可观察时间；仅声明而未证明的口径维持 review_required。
- M2 指数的 not_applicable 单位得到保留，指数点位仅用于价格状态判断。指数成交量/额不冒充股票股数/人民币均价，股票原有单位和价格域检查仍有效。

Codex 的原 23 项工作检查文件未改写。新增 `test_independent_r3_bound.py` 通过公开 API 重建同一未审核代表记录，并使用新公开接口生成前缀证据、绑定审核；原拒绝断言原样保留，另加“日级审核不能认可阶段”检查。因此最终 24 项通过是有效接口适配，不是删除失败测试。实际正向夹具计数为 **1 个阶段、3 个不同对照、1 个依赖组**，目标仍为 false。

## 3. 采用范围和真实数据阶段必须保留的限制

策略阈值是待真实案例检验的研究假设，不能据此声称其识别了隐蔽资金行为或具有交易有效性。初始案例库只用开发区间 2023-09-04 至 2025-03-31；验证与最终留出用途限制保持原样。

价格指标的实际核算窗口为有效价格柱；缺口、停牌时长、阶段连续性和持有时长使用注入交易日历。不能把停牌后压缩的 20 根价格柱宣传为固定跨度的 20 个全市场交易日。后续读取和报告应明确这两种口径，保持已检验算法，不借机调整阈值。

当前摘要/哈希检查证明内部一致性；冻结来源、真实执行身份、完整开发日期序列仍必须由下一阶段的读取器和独立审核证明。控制组重验验证已声明集合的合规性，不重建原始完整池中的最优排序；下一阶段必须保留原控制池与确定性匹配结果。审核中的两个名字也不能替代两次真实审核执行。

M2 为 50 只股票和两个基准指数。两只股票有部分已知现金分红，其余 48 只覆盖未知；整体历史可得时间未证明，保持回顾性、strict PIT=false、training_eligible=false。种子三维通信不在冻结证券池，不补造其案例。真实正例、实际审核和合格真实阶段在本验收时均为 **0**。

M3 原目标为至少 50 个独立审核正例阶段，每例 3–5 个匹配对照；依赖组数量另报。若证据不能支持目标，需要完整范围与逐级排除证据，不能用日记录充数、调阈值、扩证券池或偷用留出期。

## 4. 保全和下一步

`codex/preservation_r3_checkpoint_01.json` 检查通过：316 个原有跟踪文件、16 个生产文件位置、M2 交付/传递证据/采集核算/最终闭环均保全。另逐项核对 R1 的 8 个、R2 的 13 个声明交付文件，后端旧版本采用已保留快照，其余仍为原文件。没有生产晋升、新采集、账户、资金、委托或实盘操作。

下一步为独立的 M3-02 冻结读取与待审核案例准备任务，先实现、验证严格只读来源边界，再完整处理开发区间。新输出隔离，真实审核保持待办。15 分钟巡检继续，只有 M3 最终验收才能结束该里程碑。

## Next instructions for Claude

R3 is technically accepted for isolated retrospective M3 research. Preserve the exact accepted module, tests, policies, R1/R2/R3 outputs and all Codex/M2 evidence. Read the separate M3-02 task and policy_freeze.json when dispatched. Implement only its new reader/test/output paths, verify the exact frozen candidate inputs, use read-only connections, retain benchmark units and cutoff provenance, produce the complete development chronology and pending episode/control evidence, and stop at a stable ready_for_review manifest. Do not manufacture reviews, tune thresholds, touch production, use held-out prices, or start M4.
