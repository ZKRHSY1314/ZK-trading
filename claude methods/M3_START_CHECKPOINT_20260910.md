# M3 启动检查与首单交接

日期：2026-09-10。状态：`in_progress`；M3 尚未完成。用户要求：“开始M3吧，一样的流程”。

已恢复 Claude 具体任务委派、Codex 独立验收和每 15 分钟巡检。本次仅完成启动检查与首单提交，不能将其当作 M3 标签/案例库验收通过。

## 已核实

- M2 的 18 项最终收口文件、31 项交付文件和 479 项传递证据均匹配冻结指纹；生产数据库及伴随文件 16 个位置未变。继续沿用 52 标的暂存总体，原库和旧标签不修改。
- 当前分支 `codex/control-plane-refactor`，HEAD `73f266d4165df48bacc6112f037537aed5fb7a58`。316 个已有跟踪文件记录新的 M3 哈希基线；启动前全部已有未提交差异均排除在本次写入范围之外。Git 没有暂存、提交或推送。
- Claude 唯一既有会话 `ZK-trading / Fable 5.1 project advice (fork)` 已确认 Idle、完成 M2 回复，输入框没有用户草稿。恢复窗口操作后，M3-01 已显示为 Message 48；实际截图显示 `Ran 25 commands`、`3m 16s / 2.1k tokens / Almost done thinking` 和 Stop 按钮，足以证明实际启动，不是仅生成任务书。UIA 文本仍显示早先 Sending，运行判断以本次截图为依据。
- 原自动化 `claude` 已更新为“ M3 标签与案例协作巡检”，同一 Codex 任务、15 分钟间隔、ACTIVE；工具成功后已读回实际 automation.toml 核对。采用同一任务持续检查，完成或出现不可自行解决的边界时报告；无变化不重复发消息。官方机制说明见 [Scheduled tasks](https://learn.chatgpt.com/docs/automations?surface=app)。

## 首单范围和后续验收

任务书：`M3_01_LABEL_SPEC_CLAUDE_TASK_20260910.md`，SHA-256 `9d05c9579c58f8ce02f19448ffcf4f29781eeab4b652441145b36d28d8d2ef7c`。

Claude 仅可新增 `backend/app/research/m3_labels.py`、`backend/tests/test_m3_labels.py` 及 `_m3_20260910/claude_01/` 内文件，完成纯标签模块、初始版本规则和合成防泄漏测试。本单不读取真实价格来选阈值/案例，不连接 SQLite，不访问网络，不启动旧回放服务。Codex 拥有基线、审查目录、协调状态和验收文件。

现有回放服务会初始化生产库、使用运行当天日期截取历史，并包含特定股票的人工作结论；不能直接作为新 M3 标签。三维通信和金螳螂不在冻结 M2 总体中，只保留有来源标记的历史种子语境。严格区分可计算的回溯截断与历史 PIT 来源真实性，也不把原始不复权价格自动当成公司行动中性收益。

M3 完整要求保持：所有标签家族、不确定和失败案例、每例同期间/流动性/市场状态对照、真实独立审阅和来源/版本/截止时间记录。至少 50 个独立审阅正例、每例 3–5 个匹配对照是超出探索性监督研究前的证据目标；不凑数、不回填未来、不拿合成测试当真实案例。

下一步：Claude 交付稳定后，Codex 同轮独立检查规则、完整测试和输入时间约束，冻结通过审查的初始政策；随后另发明确的真实案例提取任务，只读固定 M2 候选库并写新的隔离 M3 产物。当前尚未生成真实 M3 案例，未宣布政策已采用。

## 实测与保全

```powershell
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\codex\bootstrap.py'
& 'D:\codex-A股交易\backend\.venv\Scripts\python.exe' -B -X utf8 'D:\codex-A股交易\claude methods\_m3_20260910\codex\verify_preservation.py' 'D:\codex-A股交易\claude methods\_m3_20260910\codex\preservation_after_dispatch.json'
```

两条命令实际退出 0；保全问题 0。bootstrap 只允许首次建立基线，不能覆盖重跑。第二条必须使用新的回执路径。没有 M3 功能测试通过数可报告：Claude 正在实现，尚待交付。生产 SQLite 连接数 0、行情请求数 0、原数据写入 0；新增内容为本阶段代码/计划/基线和审查材料。

安全状态：review_only=true，live_trading=false，production_promoted=false，strict_pit=false。回退时仅停止使用新的 M3 产物；保留 M2 和既有代码/知识，不清理用户工作。M3 未完成前保持本轮巡检；不自动进入 M4。

Claude next instruction: Complete M3-01 within its exclusive write scope and return the frozen policy, pure implementation, adversarial test evidence and manifest at ready_for_review. Do not select real cases or start another task before Codex reviews this delivery.
