# M4-01 执行内核验收

结论：M4-01 技术验收通过，可以进入 M4-02A 组合账本小步。此次仅验收隔离的合成执行内核，不代表 M4 整体完成、历史成交真实性或策略有效性通过。

Claude 第二次交付已实际停止并声明 ready_for_review。界面给出的清单哈希与磁盘一致：`c3e2d6a54f0838f59032b89b9c64c053067e5e51a1a62ac00f1b1c9159ed312f`。其 29 项 written 文件与 2 个代码文件核验一致；31 项 sources_read 中仅 Codex 自有协调状态发生已授权的暂停/复核更新，其余一致。

## 修复与实测

第一轮六类问题均已修复：连续委托按实际时刻过期、零股容量、日历可得时间、结算日参与输入身份、Decimal 上下文隔离、价格金额格式归一。Codex 原始 9 项探针对 Claude 交付和最终整合版本均实际通过。

验收补查发现 CNY 成交容量仍按 Python 类型处理整数，且结果记录保留金额原始小数格式，使相同经济输入产生不同标识。Claude 停笔后，Codex 明确接管两处代码/测试的最终修正，保存其原始模块、测试、清单和失败回执，再按 `unit == CNY` 统一输入及结果中的金额格式；share 数量继续要求整数。此项修正由 Codex 完成，不冒称 Claude 已交付或第三方独立审查。最终代码的来源是 Claude 第二版加这项 Codex 修正；Claude 原清单保留历史效力，整合版以 `execution_freeze.json` 为准。

实际执行：

- `codex/run_acceptance_01.py`：62 项 unittest 全通过（Claude 原 61 项 + Codex 新增 1 项），0 失败/错误/跳过。
- 同次运行的 7 项额外检查全通过：含费现金不足无成交、100 股卖出手算现金 +1094.44 元、T+1、250 股容量按手数部分成交、CNY 金额身份、基准不可交易、未来价格不可用于开盘成交。
- `codex/probe_m4_final_01.py`：原始 9 项探针全通过，预期没有放宽。
- 测试均使用标准库隔离加载，未导入 app、conftest 或旧引擎；无数据库连接、网络、子进程和越界写入，执行前后源码哈希一致。假设费率仅用于算术夹具。
- 316 个原有受跟踪文件、42 个固定证据文件、16 个生产数据库相关文件位置核验一致；没有暂存、提交或推送。

原始失败、修复中间失败以及最终通过均保存在 `_m4_20260912/codex/acceptance_review_01/`；原始探针证据另保留，最终复现位于 `codex/final_probe_01/`。

## 冻结范围与限制

最终模块 SHA-256：`83a28b543b9ecc5edf8080ea39fa388f8b2bb5a8724ef68b4b532041216678c7`。

最终测试 SHA-256：`90d8790400a497f31868ab52f985f1fe98c98806871c7346f68e8e5821c19317`。

原合同版本字符串仍为 `0.1.0-draft`；Codex 的整合冻结标识为 `M4-01-codex-integration-1`，绑定实际字节哈希及本验收补充。合同中有关 CNY quantity 由数值类型推断的文字，以本验收所述按 unit 解释为准。策略哈希保持 `9bea83482d545e6f39dd8eb70e89d674dd5d900378b596c243da8e122c273e62`。

仍需下阶段实现组合状态、FIFO 成本/现金核对、订单及成交去重、累计容量、仓位/最大暴露、止损/退出/冷却、基准与退市处理以及合格历史数据的非零基线。当前接受的是已定量订单的一次执行尝试；所有状态/价格/容量证据由调用方显式提供，假设重放不得冒称真实历史执行证明。并未接入生产服务。

M3 仍为双审正例 0/50、32 个争议，M3_complete=false、training_eligible=false、strict_pit=false；实盘关闭，M5 未启动。

## Next instructions to Claude

Read `M4_02A_PORTFOLIO_LEDGER_CLAUDE_TASK_20260912.md` and the Codex execution freeze. Implement only the isolated synthetic portfolio/FIFO ledger and its tests under that task's write scope. Treat the final Codex CNY normalization as an explicit integration change to inspect before consuming the kernel. Keep M4-01 and all M2/M3 evidence read-only. Deliver a hand-calculated nonzero round trip, guarded test evidence, reconciliation and a final hash manifest; then stop for Codex review. Do not start strategy/risk integration, historical data access, M4-02B, M5 or training.
