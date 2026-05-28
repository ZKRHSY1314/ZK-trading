# 自动化控制方案

## 当前阶段

自动化进程先以“模拟优先”运行。它可以自动完成：

1. 扫描候选池。
2. 读取用户确认知识和历史案例。
3. 分析重点股票。
4. 生成模拟交易计划。
5. 记录自动化事件，供复盘学习使用。

## 暂不开放

- 不自动操作真实券商客户端。
- 不自动点击真实下单按钮。
- 不绕过人工确认。
- 不把屏幕控制能力直接接入资金操作。

## 后续可接入的控制适配器

- Browser/Playwright：控制本地 Web 控制台、读取页面状态、点击模拟按钮。
- Codex Skills：读取文件、运行回测、检查日志、维护策略配置。
- 屏幕控制工具：未来可读取券商客户端界面，但只在审计后作为只读监控。
- 自动化调度：盘前扫描、开盘监控、收盘复盘。
- Agent Control Queue：允许外部智能体通过安全接口调度本地沙盒任务。

## 已加入的控制适配器

### 自动发现与候选池阶段风控

系统现在会在自动化循环开始时优先扫描涨停/接近涨停/强势上涨股票，并写入 `auto_discovered_candidates`。这些股票会合并进本地候选池，但默认只进入观察层，必须继续经过阶段相似度风控、模拟计划和监控复盘。

常用接口：

```powershell
POST /api/candidates/auto-discovery?limit=80&persist=true
GET  /api/candidates/auto-discovery/latest?limit=50
GET  /api/candidates/local-scan?limit=100&persist=true
```

安全全周期入口：

```powershell
POST /api/automation/cycles/run-once?limit=8&monitor_limit=5&review_symbol=SZ002081
```

Codex 本地安全任务循环：

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\scripts\start_codex_safe_task_loop.ps1
```

该循环只执行自动发现、候选池扫描、批量阶段风控、模拟计划、监控和复盘，不会打开实盘交易权限。

### Browser 控制适配器

脚本位置：

```powershell
C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend\scripts\browser_control_adapter.mjs
```

运行方式：

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend
npm run automation:browser
```

它会自动：

1. 打开本地控制台。
2. 确认“实盘禁用”按钮处于禁用状态。
3. 点击“本地扫描”。
4. 点击“运行自动化”。
5. 点击“生成模拟计划”。
6. 读取页面文字状态。
7. 将每一步写入后端自动化日志。

### 自动化循环进程

脚本位置：

```powershell
C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend\scripts\automation_loop.py
```

运行一次后端自动化循环：

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode api --max-cycles 1 --limit 5
```

运行一次安全闭环：

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/automation/cycles/run-once?limit=5&monitor_limit=5&review_symbol=SZ002081"
```

该接口会顺序触发候选扫描、模拟计划、学习报告、盘中监控和单股复盘。它只写入模拟、监控、告警和复盘数据，不会打开实盘交易权限。

运行一次浏览器控制循环：

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode browser --max-cycles 1
```

运行一次盘中监控循环：

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode monitor --max-cycles 1 --limit 5
```

循环日志写入：

```powershell
C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend\logs\automation_loop.jsonl
```

持续模拟守护进程：
```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\scripts\start_safe_simulation_loop.ps1 -Mode api -IntervalSeconds 300 -Limit 5
```

持续盘中监控循环：
```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\scripts\start_intraday_monitor_loop.ps1 -IntervalSeconds 60 -Limit 5
```

`automation_loop.py --max-cycles 0 --continue-on-error` 会持续运行，并在临时数据源故障时记录失败事件后继续下一轮。当前默认仍只执行候选扫描、知识引用、模拟计划和日志记录。

### 盘后潜力搜索

盘后或非交易日可以运行更广的潜力候选搜索。它复用自动发现数据源和现有评分/生命周期服务，搜索结果持久化到 `potential_search_runs` 和 `potential_search_items` 表。

### Agent Control Queue

引入了 Agent Control Queue (安全智能体控制队列)。它充当一个安全沙盒，允许外部智能体 (如 Codex) 调度执行安全仿真和观察任务。

该队列**明确阻断**实盘交易、券商登录、凭据存储以及破坏性的系统调用，保证 Agent 只能编排合规的扫描和模拟逻辑。
- 常用安全沙盒任务：`offhour_potential_search`, `auto_discovery_scan`, `monitoring_run`, `full_simulation_cycle`, `frontend_browser_check`
- 常用观察任务 (需要审批)：`local_dashboard_observation`
- 常用接口：
  - `GET /api/agent-control/capabilities`
  - `POST /api/agent-control/tasks/run-now?task_type=...` (自动审批并执行安全任务，观察任务将返回 pending)
  - `POST /api/agent-control/tasks/{id}/approve` (人工审批通过)
  - `POST /api/agent-control/tasks/{id}/reject` (人工审批拒绝)
  - `POST /api/agent-control/tasks/{id}/run` (执行已审批通过的任务)
  - `GET /api/agent-control/audit` (查看审批和拒绝操作的审计日志)
- 在前端“Agent Control Queue”面板中可以发起需要审批的观察任务，进行人工审批/拒绝，查看审计日志。

### 明确的安全限制

1. **Development-Agent Coordination**: Agent 控制队列只允许外部 Agent (如 Codex) 或者本地自动化脚本发起任务。
2. **App-internal Safe Simulation Tasks**: 运行扫描、生成模拟计划、测试前端等行为属于免审批的安全沙盒任务，可以自动执行。
3. **Observation-only Screen/Page Checks**: 检查本地网页状态或健康度的任务 (例如 `local_dashboard_observation`) 属于观察任务，会被挂起并等待人工 Approval 后才可以执行，防止不确定的状态读取泄露信息或造成意外循环。
4. **Prohibited Broker/Live-Trading Actions**: 任何包含 `live` 或 `broker` 等关键字的任务，或未被明确列入白名单的任务，都会被硬性**阻断 (Blocked)**，并在数据库层面拒绝进入 `pending` 状态。绝不允许在观察任务或普通任务中尝试操控真实券商软件或存放任何凭据密码。

常用接口：

```powershell
POST /api/candidates/potential-search/run?limit=100&persist=true
GET  /api/candidates/potential-search/latest
GET  /api/candidates/potential-search/runs?limit=20
```

命令行运行（需先启动后端服务）：

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode potential --max-cycles 1 --limit 100
```

输出内容包括：
- run_id、status、source
- total_scanned、stored_count、scored_count
- top_scored_symbols（前 5 名）
- errors（数据源降级等保守错误信息）

每个候选项包括：symbol、name、current_price、pct_change、turnover_rate/amount、lifecycle_state、potential_score、reasons/components、source。

前端控制台"盘后潜力搜索"面板展示最新搜索总计和前 5 候选。

### 模拟学习闭环

自动化运行完成后会额外触发学习闭环：
1. 将交易案例、历史交易、用户确认股票、自选股档案统一写入 `learning_samples`。
2. 用保守规则跑一轮 `local_rule_v1` 回测评分。
3. 生成 `learning_reports` 每日复盘，并把 `learning_report_id` 写回自动化摘要。
4. 前端控制台展示样本数量、胜率和下一步复盘动作。
5. 将金螳螂这类“吸筹-试盘-拉升-出货完成”结构化样本写入 `main_force_phase_patterns`，用于学习主力阶段变化；当前阶段只做复盘训练，短期不追高。
6. 主力阶段回放训练器会对金螳螂和三维通信拉取近 3 年日线，生成吸筹、试盘、拉升、派发、出货后观察的阶段片段，写入 `main_force_phase_replays`。
7. 阶段相似度匹配器会把目标股与金螳螂、三维通信做路径对照，输出最相似样本、相似度、诊断和复盘动作，结果写入 `main_force_phase_matches`。

常用接口：
```powershell
GET  /api/learning/summary
POST /api/learning/rebuild-samples
POST /api/learning/backtest
POST /api/learning/reports/daily
GET  /api/learning/reports/latest
GET  /api/knowledge/main-force-patterns?symbol=SZ002081
POST /api/learning/phase-replays/core-samples?lookback_years=3
GET  /api/learning/phase-replays?symbol=SZ002081
POST /api/learning/phase-matches/SH600135?name=乐凯胶片&lookback_years=3
GET  /api/learning/phase-matches?symbol=SH600135
```

### 行情兜底

市场快照优先使用 AKShare 日线。若日线接口临时失败，会尝试腾讯只读报价接口；如果拿到现价，训练候选会继续进入保守模拟计划。金螳螂这类用户确认训练候选因此不会因为单一数据源失败而直接跳过。所有兜底结果仍只进入模拟、复盘和学习报告。

### 盘中监控事件流

盘中监控会把每一轮候选股观察写入 `monitoring_events`，包括行情来源、价格、涨跌幅、与上一轮相比的变化、信号标签和模拟计划动作。常用信号包括 `risk_blocked`、`momentum_up`、`momentum_down` 和 `observe`。所有结果仍只进入模拟、复盘和学习报告。

常用接口：
```powershell
POST /api/monitoring/sessions
POST /api/monitoring/run-once?limit=5
GET  /api/monitoring/sessions/latest
GET  /api/monitoring/events?limit=100
GET  /api/monitoring/alerts?limit=100
GET  /api/monitoring/replay/SZ002081
POST /api/monitoring/reviews/SZ002081
GET  /api/monitoring/reviews
GET  /api/monitoring/summary
```

### 监控告警与回放

每轮监控事件会同步生成 `monitoring_alerts`。当前告警类型包括：
- `sim_buy_allowed`：模拟计划允许买入，需要人工复核。
- `signal_changed`：信号相对上一轮变化。
- `pct_delta` / `price_delta`：涨跌幅或价格变化超过阈值。
- `risk_blocked_observe`：仍被风控阻断，仅保留观察。
- `fallback_quote`：使用只读报价兜底，需要在复盘中标注数据源。

`/api/monitoring/replay/{symbol}` 用于回放单只股票的监控轨迹，适合后续生成主力动向复盘。

`/api/monitoring/reviews/{symbol}` 会生成单股监控复盘，内容包括事件数量、告警数量、价格区间、信号分布、风控阻断次数、诊断文字和下一步观察动作。前端“运行自动化”会通过安全闭环接口自动生成金螳螂 `SZ002081` 的复盘。

## 安全边界

真实交易自动化必须在后续版本单独增加：

1. 实盘权限开关。
2. 单日亏损熔断。
3. 单票仓位上限。
4. 人工确认模式。
5. 完整审计日志。
6. 只读模式回退。

## 观察到学习数据集 (Observation-to-Learning Dataset)

系统可以把已完成的安全 Agent 任务自动转换为结构化学习样本，用于后续的模型训练和策略评估。

### 工作流程

1. Agent Control Queue 的安全任务 (如 `potential_search`、`auto_discovery_scan`、`monitoring_run`) 正常执行并完成。
2. 调用学习提取接口，从每个已完成任务的 `result_json` 中提取候选项/事件作为独立学习样本。
3. 每个样本包含：
   - `source_task_id`：来源任务 ID
   - `sample_type`：样本类型 (`potential_search`、`auto_discovery_scan`、`monitoring_run`、`monitoring_alert`、`local_dashboard_observation`)
   - `symbol` / `name`：标的股票（系统健康类样本无此字段）
   - `features_json`：特征数据（价格、涨跌幅、换手率、潜力评分、生命周期状态等）
   - `decision_json`：决策上下文（来源、审批元数据等）
   - `risk_flags_json`：风险标签列表（`phase_guarded`、`risk_blocked`、`limit_up_chasing_risk`等）
   - `label` / `label_source`：标签和标签来源（自动提取或人工标注）
4. 支持幂等去重，同一任务+类型+标的不会重复创建样本。
5. `blocked`、`rejected`、`pending`、`failed` 状态的任务会被跳过。

### API 接口

```powershell
# 从单个任务提取
POST /api/learning/agent-samples/from-task/{task_id}

# 从最近完成的任务批量提取
POST /api/learning/agent-samples/from-recent?limit=20

# 查询样本列表
GET  /api/learning/agent-samples?limit=50&sample_type=potential_search&symbol=SZ002081

# 查询汇总统计
GET  /api/learning/agent-samples/summary
```

### CLI 模式

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode agent-learning --max-cycles 1 --limit 20
```

### 前端

在控制台底部的「Agent Learning Samples」面板中可以：
- 查看样本汇总统计（按类型、标签分组计数）
- 查看最近样本详情（标的、来源任务、类型、标签、风险标签）
- 点击「收集最近完成的任务」按钮一键收集

### 安全限制

- 学习样本仅用于训练和评估数据，不触发任何实际交易。
- 不存储凭据、不控制券商、不改变实盘设置。
- `/health` 始终报告 `live_trading_enabled=false`。

## Agent Learning Outcomes (样本结局评估)

为了闭环学习，系统支持对创建的 `learning_samples` 进行未来几天的行情结局评估，自动打上 `outcome_label` 和 `risk_outcome`。

### 评估逻辑

1. 获取样本创建日期，并向后抓取 `horizon_days` 天的行情（默认 5 天）。
2. 计算期间最大收益、最大回撤和最终收益。
3. 根据阈值划分为：`strong_follow_through`, `mild_follow_through`, `flat_or_noise`, `failed_signal`。
4. 根据最大回撤判定：`low_drawdown`, `normal_drawdown`, `large_drawdown`。
5. 若未来数据不足，标注为 `pending_future_data`，绝不虚构数据。
6. 系统健康类样本若等待时间足够，默认评估为 `system_stable`。

### API 接口

```powershell
# 评估单个样本
POST /api/learning/agent-outcomes/label-sample/{sample_id}?horizon_days=5

# 评估最近未处理样本
POST /api/learning/agent-outcomes/label-recent?limit=50&horizon_days=5

# 获取评估结果
GET  /api/learning/agent-outcomes?limit=50
GET  /api/learning/agent-outcomes/summary
```

### CLI 模式

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode agent-outcomes --max-cycles 1 --limit 50
```

### 安全与一致性保证

- **仅限观察**：结局标注只计算历史行情，绝不会触发实际买卖，仅用于后验策略质量。
- **幂等性**：对同一 `sample_id` 和 `horizon_days` 的重复标注，只会更新数据，不会生成重复记录。

## Signal Performance & Calibration Proposals (信号绩效与校准提案)

系统可以基于已标注的学习样本结局 (`agent_learning_outcomes`) 评估各信号组、样本类型、风险标签和评分组件的实际表现，并生成校准提案供人工审阅。

### 工作流程

1. 从 `agent_learning_outcomes` 和 `agent_learning_samples` 联表聚合数据。
2. 按 `sample_type`、`label`、`risk_flag`、`symbol`（样本数足够时）和评分组件分组。
3. 计算每组的样本数、结局数、待定率、强突破/弱突破/失败信号数、平均收益/最大收益/最大回撤、大回撤数。
4. 当样本数低于阈值（默认 10），标注 `small_sample_warning`。
5. 根据统计结果自动生成校准提案：
   - `increase_review_priority`：强绩效组建议提升审阅优先级。
   - `reduce_score_contribution`：高失败/大回撤组建议降低评分贡献。
   - `wait_for_future_data`：待定率过高时建议等待更多数据。
   - `wait_for_more_data`：小样本组不做判断。
   - `keep_current`：证据不充分时维持现状。
6. 所有提案存入 `agent_calibration_proposals` 表，状态为 `pending`。
7. 人工审阅后可 `approve` 或 `reject`。
8. **提案不会自动修改任何评分权重或交易规则。**

### API 接口

```powershell
# 获取信号绩效汇总
GET  /api/learning/signal-performance/summary

# 生成校准提案（提案保持 pending 状态等待审阅）
POST /api/learning/calibration-proposals/generate

# 查询提案列表
GET  /api/learning/calibration-proposals?status=pending&limit=50

# 审批提案（仅改变提案状态，不改变权重）
POST /api/learning/calibration-proposals/{id}/approve
POST /api/learning/calibration-proposals/{id}/reject
```

### CLI 模式

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode signal-performance --max-cycles 1
```

### 前端

在控制台底部的「Signal Performance & Calibration」面板中可以：
- 查看按 sample_type / label / risk_flag 分组的信号绩效汇总行
- 查看小样本警告
- 点击「生成校准提案」按钮一键生成
- 查看待审校准提案，点击 Approve/Reject 进行人工审阅
- 面板顶部有明确的 review-only 提示

### 安全限制

- **仅限审阅**：校准提案只是建议，不会自动修改评分权重、策略规则或交易行为。
- 不存储凭据、不控制券商、不改变实盘设置。
- 审批/拒绝提案只改变提案状态字段，不触发任何其他副作用。
- `/health` 始终报告 `live_trading_enabled=false`。

## Sandbox Experiments (沙盒实验)

系统可以将已审批通过的校准提案转为沙盒实验，模拟提案被执行后的效果。实验结果存储供人工审阅，但不改变任何生产评分规则、候选分数、策略规则或交易行为。

### 工作流程

1. 仅对 `status='approved'` 的提案运行实验。
2. 计算基线指标 (baseline_metrics)：从现有结局数据聚合当前表现。
3. 计算提案指标 (proposed_metrics)：模拟提案执行后的效果：
   - `increase_review_priority`：估算覆盖率/优先级影响。
   - `reduce_score_contribution`：估算多少样本会被降级，以及正面结局的误伤率。
   - `wait_for_more_data` / `wait_for_future_data`：标注无行为变化，仍需数据积累。
   - `keep_current`：标注无行为变化。
4. 构建 before/after 对比 (comparison_json)。
5. 根据对比结果生成结论 (conclusion)：
   - `priority_increase_viable`：优先级提升可行。
   - `reduction_justified`：降低贡献有依据。
   - `reduction_mixed`：降低贡献效果混合。
   - `reduction_high_collateral`：降低贡献误伤严重。
   - `no_behavior_change`：无行为改变。
   - `insufficient_evidence`：证据不足。
   - `inconclusive`：无法得出结论。
6. 所有实验结果持久化到 `agent_sandbox_experiments` 表。
7. **实验不改变任何评分权重、候选分数、策略规则或交易行为。**

### API 接口

```powershell
# 对单个已批准提案运行实验
POST /api/learning/sandbox-experiments/run/{proposal_id}

# 对所有已批准但尚未运行实验的提案批量运行
POST /api/learning/sandbox-experiments/run-approved?limit=20

# 查询实验列表
GET  /api/learning/sandbox-experiments?limit=50

# 查询实验汇总
GET  /api/learning/sandbox-experiments/summary
```

### CLI 模式

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode sandbox-experiments --max-cycles 1 --limit 20
```

### 前端

在控制台底部的「Sandbox Experiments」面板中可以：
- 查看实验总数和待运行提案数
- 查看按结论类型分组的统计
- 点击「运行已批准提案实验」按钮一键运行
- 查看实验结果详情，包括基线指标、提案指标和结论
- 面板顶部有明确的 sandbox-only 提示

### 安全限制

- **仅限沙盒模拟**：实验只做 what-if 评估，绝不修改评分权重、候选分数、策略规则或交易行为。
- 仅对 `status='approved'` 的提案可以运行实验，`pending` 和 `rejected` 的提案会被阻断。
- 不存储凭据、不控制券商、不改变实盘设置。
- `/health` 始终报告 `live_trading_enabled=false`。

## Paper Simulation Runner & Policy Gate (模拟策略运行器)

系统可以将已完成的沙盒实验转化为模拟策略草稿，经人工审批后运行纸面模拟交易。所有模拟动作仅限本地纸面交易表，不连接券商、不下单、不存储凭据。

### 工作流程

1. 从已完成沙盒实验中提取符合条件的结论 (`priority_increase_viable`、`reduction_justified`、`reduction_mixed`、`insufficient_evidence`)。
2. 为每个符合条件的实验生成一个模拟策略草稿 (`status='draft'`)，策略文本明确标注"仅限模拟"。
3. 避免为同一实验和策略类型创建重复的活跃草稿。
4. 策略**绝不自动批准**——必须经人工审阅后 approve 或 reject。
5. 仅 `approved` 状态的策略可以运行模拟；尝试运行 draft/rejected/archived 策略会返回 HTTP 400。
6. 模拟运行使用当前候选评分和本地历史数据生成模拟动作 (`observe`、`simulated_entry`、`simulated_exit`、`skip`)。
7. 保守风控限制：
   - 每轮最多候选数 (默认 30)
   - 最大模拟仓位比例 (默认 10%)
   - 无价格数据时跳过
   - 高风险标签除非策略指定观察否则跳过
8. 所有运行指标和动作存入本地纸面模拟表。
9. **模拟运行不会修改候选分数、评分规则、策略规则、设置或券商状态。**

### API 接口

```powershell
# 从符合条件的沙盒实验生成策略草稿
POST /api/learning/simulation-policies/draft-from-experiments?limit=20

# 查询策略列表
GET  /api/learning/simulation-policies?status=draft&limit=50

# 审批策略（必须人工操作）
POST /api/learning/simulation-policies/{policy_id}/approve
POST /api/learning/simulation-policies/{policy_id}/reject

# 运行单个已审批策略的模拟
POST /api/learning/paper-simulations/run/{policy_id}

# 批量运行所有已审批策略的模拟
POST /api/learning/paper-simulations/run-approved?limit=20

# 查询模拟运行列表
GET  /api/learning/paper-simulations?limit=50

# 查询模拟运行汇总
GET  /api/learning/paper-simulations/summary
```

### CLI 模式

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode paper-simulation --max-cycles 1 --limit 20
```

该模式会：
1. 从符合条件的沙盒实验生成策略草稿。
2. 仅运行已人工批准的策略。
3. **绝不自动批准策略。**

### 前端

在控制台底部的「Paper Simulation」面板中可以：
- 查看策略草稿/已批准/已拒绝计数
- 查看模拟运行和动作计数
- 点击「从实验生成策略草稿」按钮一键生成
- 对草稿策略进行 Approve/Reject 人工审阅
- 点击「运行已批准模拟」按钮运行
- 查看最近模拟运行的指标（候选数、观察数、模拟入场数、跳过数）
- 面板顶部有明确的 SIMULATION ONLY 提示

### 安全限制

- **仅限纸面模拟**：所有动作均为模拟或观察，不构成投资建议。
- 策略草稿必须经人工审批后才能运行模拟。
- 不存储凭据、不控制券商、不下真实订单。
- 不修改候选分数、评分规则、策略规则或设置。
- 模拟动作明确标注为 `SIMULATED` 或 `OBSERVATION ONLY`。
- `/health` 始终报告 `live_trading_enabled=false`。

## Paper Simulation Evaluation (模拟结果评估)

纸面模拟完成后，系统可将模拟动作与后续市场数据进行比对，评估策略在模拟环境下的真实盈亏与风险，最终产出策略效能结论。整个过程不改变生产环境候选评分。

### 评估逻辑

1. 获取近期 `completed` 状态的模拟运行记录及其动作。
2. 对于每个模拟动作，查询 `stock_profiles`（或监控事件）中在 `horizon_days`（默认 5 天）内的最高价、最低价和最新价。
3. 如果无价格数据，标记为 `skipped_no_price`。
4. 如果未到期且无数据，标记为 `pending_future_data`。
5. 有效数据计算最大收益、最低收益和期末收益，判定 outcome (例如 `strong_follow_through`, `failed_signal`) 及风险 (例如 `large_drawdown`)。
6. 根据评估结果聚合，打上保守结论标签：
   - `promising_simulation_policy`
   - `mixed_or_unproven_policy`
   - `weak_simulation_policy`
   - `pending_future_data`
   - `insufficient_price_data`

### API 接口

```powershell
# 评估近期模拟运行动作 (默认 horizon_days=5)
POST /api/learning/paper-simulation-evaluations/evaluate-recent?limit=100&horizon_days=5

# 评估单次运行
POST /api/learning/paper-simulation-evaluations/evaluate-run/{run_id}?horizon_days=5

# 获取评估列表
GET  /api/learning/paper-simulation-evaluations?limit=100

# 获取评估汇总
GET  /api/learning/paper-simulation-evaluations/summary

# 获取策略级结论
GET  /api/learning/paper-simulation-evaluations/policies
```

### CLI 模式

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode paper-evaluation --max-cycles 1 --limit 100
```

### 前端

在控制台底部新增「Simulation Evaluation」面板：
- 显式声明 `EVALUATION ONLY`，提示仅针对模拟动作。
- 展示总评估数、完成数、待定数及无价格跳过数。
- 点击「评估近期模拟动作」进行一键评估。
- 展示各策略级别的执行结果结论及回撤监控。

### 安全限制

- 评估完全基于本地已有历史价格数据。
- 仅处理 `agent_paper_simulation_actions` 表数据。
- 不影响真实系统的候选打分、监控规则和策略配置。
- 所有返回结果均带有 "Simulation only. Not investment advice." 声明。
- `/health` 始终为 `live_trading_enabled=false`。
