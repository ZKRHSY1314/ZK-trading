# 2026-06-09 同花顺模拟盘训练日志

## 本次目标

- 阶段：开盘前调试与模拟训练预检。
- 范围：只验证同花顺模拟炒股窗口、UIA 坐标锚点、监督 CLI、Dataset2 dry-run 训练链路。
- 禁止项：不触碰真实账户，不连接券商 API，不保存账号密码，不修改 `.env` / `rules.yaml`，不写模型 artifact。

## 安全门槛

- `/health`：`status=ok`，`live_trading_enabled=false`。
- 后端启动库：`C:\Users\lenovo\Desktop\A股记录\ai_trading_system\trading_local.sqlite3`。
- 同花顺进程：`xiadan.exe`。
- 窗口标题：`网上股票交易系统5.0`。
- 模拟标识：`mncg`、`模拟`、`模拟炒股` 已识别。
- 危险实盘词：空。
- 非阻断菜单词：`银证`、`银证转账`，仅作为菜单风险留痕，不作为本次模拟页硬阻断。

## 今日调试记录

1. 修复窗口误识别风险：
   - 问题：Codex 聊天/日志里也可能出现 `mncg`、`同花顺`、`xiadan.exe` 等字样，旧评分逻辑有误把可见文本当成进程证据的风险。
   - 修复：`process_terms` 只从窗口标题、进程路径、进程名中提取；可见文本只用于模拟标识和危险词检测。
   - 文件：`C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend\app\sim_cockpit\desktop_adapter.py`。

2. 修复 UIA 锚点兼容：
   - 问题：同花顺真实 UIA 返回正常中文 `买入[F1]` / `卖出[F2]` / `撤单[F3]`，旧代码只兼容乱码名，容易导致锚点缺失。
   - 修复：锚点匹配同时支持正常中文和历史乱码名。
   - 覆盖：新增正常中文 UIA 锚点回归测试。

3. 只执行导航级点击：
   - 动作：仅点击 `买入[F1]` 切到买入页面。
   - 未执行：未输入证券代码、未输入价格、未输入数量、未点击买入提交。
   - 点击前截图：`C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend\logs\sim_cockpit_screenshots\20260609_075640_253122_debug_pre_market_before_buy_tab_debug.png`。
   - 点击后截图：`C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend\logs\sim_cockpit_screenshots\20260609_075652_411367_debug_pre_market_after_buy_tab_debug.png`。

## 当前模拟窗口状态

- 最新 verification id：`28`。
- 当前页面：买入股票页。
- 当前可用锚点：
  - buy：`buy_tab`、`symbol_input`、`price_input`、`quantity_input`、`submit_button`。
  - sell：`sell_tab`、`symbol_input`、`price_input`、`quantity_input`。
  - cancel：`cancel_tab`。
- 买入页关键 UIA：
  - 证券代码输入框：`automation_id=1032`。
  - 买入价格输入框：`automation_id=1033`。
  - 买入数量输入框：`automation_id=1034`。
  - 买入按钮：`automation_id=1006`。

## 监督 CLI 预检

- 命令模式：`sim-cockpit-supervised-cycle`。
- 日志文件：`C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend\logs\sim_cockpit_supervised_cycle_20260609_preopen.jsonl`。
- started_at：`2026-06-09T07:58:58`。
- status：`completed`。
- window_detection：`verified`。
- simulation_cockpit_run id：`19`。
- candidate_plan_count：`20`。
- attempted_count：`0`。
- executed_count：`0`。
- blocked_count：`0`。
- 结论：预开盘监督循环只完成检测、状态读取和 Dataset2 dry-run，没有发起模拟下单动作。

## Dataset2 训练状态

- stage：`dataset2_controlled_training`。
- status：`ready`。
- sample_candidate_count：`20`。
- source_counts：
  - `dataset2_staging_records=8`
  - `sim_cockpit_actions=6`
  - `sim_cockpit_readbacks=6`
- split：`time_ordered_70_30`，训练 `14`，验证 `6`。
- 最新 dry-run event id：`109`。
- training_status：`completed`。
- training_mode：`in_memory_majority_label_baseline`。
- validation_accuracy：`1.0`。
- model_artifact_written：`false`。
- 注意：当前只是审计元数据上的内存基线，不能当成可部署交易模型。

## 验证结果

- `python -m compileall backend\app backend\scripts`：通过。
- `pytest backend\tests\test_sim_cockpit.py -q`：`12 passed`。
- `git diff --check`：无空白错误；仅出现既有 CRLF/LF 提醒。
- `codegraph sync`：已执行并报告同步 3 个变更文件。
- `codegraph status`：仍提示 `Pending Changes: Modified 3 files`，晚间需要复查索引状态。
- `a-share-trading-cockpit` skill：已补充 2026-06-09 调试规则，记录误识别防线和中文锚点兼容要求。

## 晚间复查清单

- 查看今天交易时段后是否新增 sim-cockpit actions/readbacks。
- 核对是否仍只有模拟账户证据，且 `live_trading_enabled=false`。
- 查看最新截图是否仍停留在模拟炒股页面。
- 复查 Dataset2 event id 是否晚于 `109`，并确认仍未写模型 artifact。
- 复查 codegraph 是否还显示 3 个 pending modified 文件。
- 若要进入小额模拟训练，首单仍应限制为 100 股、低金额、全程截图留痕，并继续禁止真实盘。
