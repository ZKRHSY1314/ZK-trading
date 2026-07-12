# A股 AI 自动化交易系统

这是一个本地优先的 A 股研究、模拟、监控和复盘驾驶舱。Control Plane 的 `full` 主路径固定为 Market Pulse → Decision Snapshot → Simulation Cycle → Forecast Feedback → Training Feedback；不接入实盘自动下单。

这是 `ZK-trading` 仓库中的 A股交易软件项目。

## 当前共识

- 运行方式：本地 Windows 优先，浏览器控制台使用，后续可迁移云端。
- 数据源：AKShare 免费数据优先；全市场历史覆盖需要通过显式 backfill 建立并核验。
- 行情兜底：AKShare 日线临时失败时，系统会尝试腾讯只读报价接口生成保守模拟快照。
- 扫描方式：Decision Snapshot 只使用决策时点可见且通过质量门禁的数据；全 A 股日线由独立、可续跑的 backfill 补齐。
- 策略方式：可配置规则引擎，网页可开关和调参，文件可版本管理。
- 决策顺序：交易铁律 > 风控 > 策略规则 > 案例相似度 > AI解释。
- 模拟交易：严格模拟 A股 T+1、涨跌停、集合竞价、手续费、印花税、100股最小交易单位。
- AI学习：Forecast Ledger 保存不可变预测，Forecast Feedback 在 1/3/5/10/20 个交易日到期后标注结果；不会自动改写或启用生产评分规则。
- 结构判断：使用可观察价格/成交量代理分别计算 `pre_markup_probability` 与 `distribution_probability`；这是待校准的基线，不声称直接观察到隐藏市场参与者。
- 安全边界：所有新增预测、披露、回填和反馈能力均为 review-only / simulation-only，`live_trading_enabled=false`。
- 实盘按钮：第一版仅显示禁用占位。

## 目录

- `docs/PRD.md`：产品需求文档。
- `docs/TECHNICAL_ROADMAP.md`：分阶段技术路线。
- `docs/RISK_BOUNDARIES.md`：风控和权限边界。
- `docs/AUTOMATION_CONTROL.md`：自动化运行文档。
- `docs/CONTROL_PLANE.md`：统一运行栈、调度和训练反馈说明。
- `docs/RELEASE_CHECKLIST.md`：发版自检清单。
- `backend/`：FastAPI 后端骨架。
- `frontend/`：Vue 控制台骨架。

## 首次安装与运行

本项目支持在没有私有数据集 `数据集1` 的情况下，使用内置的 Demo 种子数据进行运行体验。

依赖已安装时，在仓库根目录一键启动后端、前端和 review-only worker：

```powershell
cd D:\codex-A股交易
.\scripts\run_stack.ps1
```

启动脚本会固定使用仓库根目录的 `trading_local.sqlite3`，强制设置 `ENABLE_LIVE_TRADING=false`，启动 15 分钟 Control Plane worker、4 小时 reference-data worker，以及可选的 4 小时 Codex Market Pulse 深度搜索。若只想运行固定来源抓取，可使用 `.\scripts\run_stack.ps1 -EnableCodexSearch:$false`。启动后检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/readyz
Invoke-RestMethod http://127.0.0.1:8000/api/control-plane/status
```

- 控制台：`http://127.0.0.1:3000`
- API 文档：`http://127.0.0.1:8000/docs`
- Control Plane 心跳：`backend/logs/control_plane_heartbeat.json`
- 参考数据心跳：`backend/logs/reference_data_heartbeat.json`
- Codex 舆情心跳：`backend/logs/codex_market_pulse_heartbeat.json`

停止整套进程：

```powershell
.\scripts\stop_stack.ps1
```

停止脚本会校验 PID、可执行文件、完整命令行和进程创建时间；无法确认身份时只报告 `attention`，不会终止进程。Control Plane 还会检查日线日期、OHLC/质量状态和最新横截面覆盖率；行情过期或覆盖不足时跳过模拟周期与候选判断。

## Control Plane 执行顺序

`full` profile 的业务步骤严格按以下顺序执行：

1. **Market Pulse**：把可用时点内的政策、新闻和跨市场证据规范化为 Event Fact，并形成带方向、周期、衰减和失效条件的 Sector Thesis。
2. **Decision Snapshot**：先解析当时有效的公司—板块暴露，再结合双头结构代理和数据质量门禁生成候选排名；Market Pulse 写入板块预测，Decision Snapshot 写入股票预测，二者都进入不可变 Forecast Ledger。
3. **Simulation Cycle**：只消费已经完成的 Decision Snapshot；快照缺失或行情不新鲜时记录跳过，不回退到另一套候选入口。
4. **Forecast Feedback**：按下一交易日开盘到第 1/3/5/10/20 个交易日收盘的统一口径标注到期预测，并计算 coverage、Precision@K、Spearman Rank IC 和 Brier；样本不足时返回 `insufficient_data`。
5. **Training Feedback**：在 Forecast Feedback 之后更新原有安全任务样本和质量汇总，不自动改写生产规则。

行情不新鲜时，Control Plane 可能在 Decision Snapshot 前插入 `market_data_refresh` 支持步骤；它不改变上述业务顺序。各 profile 的语义为：

| Profile | 执行内容 |
| --- | --- |
| `pulse` | Market Pulse → Decision Snapshot |
| `full` | 完整五步链路 |
| `maintenance` | Market Pulse → Decision Snapshot → Forecast Feedback → Training Feedback，不运行 Simulation Cycle |
| `training` | Forecast Feedback → Training Feedback |
| `adaptive` | 按上海时区选择上述 profile |

Forecast Ledger 的每条记录包含 `decision_cutoff`、`available_at`、预测周期、版本、排名、概率和证据。`as_of` 查询不会读取决策时点以后才可用的事实。Event Fact、历史板块成员关系和 Disclosure Fact 也遵循相同的 point-in-time 约束。

当前披露事实入口支持资产负债表、利润表、现金流量表、业绩预告、回购、减持、解禁、定增和重大合同的幂等修订与只读摘要。真实采集器已接入回购事实；其他类型仍是待逐源验证的 schema/ledger 能力，不输出买卖判断。

## 参考数据与跨市场特征

`ingest_reference_data.py` 统一补齐三类 point-in-time 数据：

- 板块成分：东方财富行业/概念源，失败时使用新浪行业源。成功抓取保存完整不可变快照，成分移出后不再永久活跃，旧 cutoff 仍能看到当时成分。
- 公司披露：当前真实 adapter 采集回购，哈希排除动态“最新价/序号”，避免把行情变化伪造成公告修订。
- 跨市场日线：`SMH`/`NVDA` 使用前复权价；`CL`/`GC`/`BTC` 明确标记为未调整连续期货；`SOX` 可选。未收盘美股 bar 不进入 Market Regime 特征。

默认 dry-run 不写 ledger record：

```powershell
cd D:\codex-A股交易\backend
.\.venv\Scripts\python.exe -X utf8 -m scripts.ingest_reference_data `
  --board-limit 5 --disclosure-limit 100 --global-days 30 --skip-sox
```

人工核验后显式 `--apply` 才写本地参考 ledger，不会下单或连接券商：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.ingest_reference_data --apply `
  --board-limit 5 --disclosure-limit 100 --global-days 30 --skip-sox
```

`run_stack.ps1` 会启动独立的 `reference_data_loop.py`：首轮立即执行，之后每 4 小时一次，单例锁防止重复 worker，每轮最长 900 秒。某个源失败会记为 `partial` 并保留其他已验证 section，不冒充全源成功。

## 全市场日线 backfill

先在 `backend` 目录执行默认 dry-run，确认股票数量、批次和已有覆盖率；dry-run 不写入数据库。股票清单优先使用实时全 A 接口，失败时改用独立的 A 股代码清单；两者都不可用时只会把本地已知股票标为 `degraded_local_partial`，不会冒充全市场：

```powershell
cd D:\codex-A股交易\backend
.\.venv\Scripts\python.exe -X utf8 scripts\backfill_market_universe.py `
  --days 500 `
  --batch-size 200
```

确认数据源可用后，必须显式传入 `--apply` 才会写入 `daily_bar_cache`：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\backfill_market_universe.py `
  --apply `
  --days 500 `
  --batch-size 200 `
  --rate-limit-seconds 0.5
```

中断后可从最后一个已处理代码继续；也可用 `--limit` 做小批验证：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\backfill_market_universe.py `
  --apply `
  --resume-after SH600000 `
  --limit 200
```

结果分别报告日线股票覆盖、`amount` 完整度、最新交易日横截面覆盖，以及 Forecast Feedback 所需的 `SH000300` / `SH000001` 基准数据状态。任一基准刷新失败会单独列在 `reference_data` 并把任务降级为 `partial`，不会混入股票成功率。`--apply` 只授权写日线缓存，不授权任何模拟或实盘订单。

## Windows 持续运行

从仓库根目录执行 `ensure_stack.ps1`。它会先检查后端、前端、`readyz`、`live_trading_enabled=false`，以及 Control Plane / reference-data / Codex 舆情 worker 的进程身份和心跳；健康时复用现有进程，不健康时只按受跟踪 PID 安全重启：

```powershell
cd D:\codex-A股交易
.\scripts\ensure_stack.ps1
```

Windows Scheduled Task 是可选安装项，不会因拉取代码自动安装：

```powershell
# 查看状态
.\scripts\control_plane_task.ps1 -Action Status

# 安装：登录时启动，并每 5 分钟执行一次 ensure
.\scripts\control_plane_task.ps1 -Action Install -EnsureIntervalMinutes 5

# 手工触发已安装任务
.\scripts\control_plane_task.ps1 -Action RunOnce

# 卸载任务；不会修改交易配置
.\scripts\control_plane_task.ps1 -Action Uninstall
```

安装或触发后仍应核验：

```powershell
(Invoke-RestMethod http://127.0.0.1:8000/health).live_trading_enabled
Invoke-RestMethod http://127.0.0.1:8000/readyz
```

第一条命令必须返回 `False`；否则不要继续运行 Control Plane。

需要手工安装时：

```powershell
cd D:\codex-A股交易\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 导入种子数据（无私有数据时将自动使用 demo_seed）
python -X utf8 scripts\import_legacy_data.py

# 启动后端
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另一个终端启动前端：

```powershell
cd D:\codex-A股交易\frontend
npm ci
npm run dev
```

## 导入交易知识库

```powershell
cd D:\codex-A股交易\backend
.\.venv\Scripts\Activate.ps1
python -X utf8 scripts\import_legacy_data.py
```

导入结果会写入：

- `trading_local.sqlite3`（仓库根目录，唯一权威运行库）

当前导入内容包括：

- 原则库：交易铁律、灯盏策略原则
- 战法库：买入、卖出、仓位、选股策略
- 技术指标：强制分歧点、均线、涨停均价等
- 案例库：成功/失败案例
- 交易明细：历史交易流水
- 自选股档案：成本线、卖点、风险、评分
- 策略文档：灯盏策略、庄股成本计算法等结构化原文

常用查询接口：

- `GET /api/knowledge/summary`
- `GET /api/knowledge/principles`
- `GET /api/knowledge/strategies?category=buy`
- `GET /api/knowledge/cases?keyword=603618`
- `GET /api/knowledge/stocks?keyword=SH603015&limit=5`
- `GET /api/knowledge/user-notes`
- `GET /api/knowledge/main-force-patterns?symbol=SZ002081`
- `POST /api/decision/analyze`
- `GET /api/market/snapshot/603618`
- `GET /api/decision/analyze-symbol/603618`
- `POST /api/candidates/auto-discovery?limit=80&persist=true`
- `GET /api/candidates/auto-discovery/latest?limit=50`
- `GET /api/candidates/local-scan?limit=100&persist=true`
- `GET /api/candidates/lifecycle/summary`
- `GET /api/candidates/lifecycle?state=pending_review&limit=50`
- `GET /api/candidates/lifecycle/events?symbol=SH600135`
- `POST /api/candidates/scores/rebuild?limit=200&persist=true`
- `GET /api/candidates/scores?limit=50`
- `GET /api/candidates/scores/summary?limit=10`
- `GET /api/candidates/latest`
- `GET /api/simulation/account`
- `POST /api/simulation/orders`
- `POST /api/simulation/settle`
- `GET /api/simulation/fills`
- `GET /api/automation/capabilities`
- `POST /api/automation/run-once?limit=30`
- `POST /api/automation/cycles/run-once?limit=5&monitor_limit=5&review_symbol=SZ002081`
- `GET /api/automation/latest`
- `GET /api/automation/runs`
- `GET /api/automation/runs/{run_id}`
- `POST /api/automation/runs/start?mode=browser_control`
- `POST /api/automation/runs/{run_id}/events`
- `POST /api/automation/runs/{run_id}/finish`
- `GET /api/learning/summary`
- `POST /api/learning/rebuild-samples`
- `GET /api/learning/samples?label=success&limit=50`
- `POST /api/learning/backtest`
- `POST /api/learning/reports/daily`
- `GET /api/learning/reports/latest`
- `POST /api/learning/phase-replays/core-samples?lookback_years=3`
- `POST /api/learning/phase-replays/SZ002081?name=金螳螂&lookback_years=3`
- `GET /api/learning/phase-replays?symbol=SZ002081`
- `POST /api/learning/phase-matches/SH600135?name=乐凯胶片&lookback_years=3`
- `GET /api/learning/phase-matches?symbol=SH600135`
- `POST /api/monitoring/sessions`
- `POST /api/monitoring/run-once?limit=5`
- `GET /api/monitoring/sessions/latest`
- `GET /api/monitoring/events?limit=100`
- `GET /api/monitoring/alerts?limit=100`
- `GET /api/monitoring/replay/SZ002081`
- `POST /api/monitoring/reviews/SZ002081`
- `GET /api/monitoring/reviews`
- `GET /api/monitoring/summary`

## 浏览器控制适配器

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend
npm run automation:browser
```

该脚本会控制本地 Web 控制台完成扫描、自动化运行和模拟计划生成，并把每一步写入后端自动化日志。它会先检查“实盘禁用”按钮是否保持禁用。

## 旧版兼容自动化循环（非 Control Plane 主路径）

以下 `automation_loop.py` 和安全闭环接口为兼容、诊断及单项回放保留；新部署应以 Control Plane 五步链路作为主入口，不能把下面的 legacy 顺序当作新的 Decision Snapshot 调用顺序。

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode api --max-cycles 1 --limit 5
```

legacy 全周期模式会先自动扫描涨停/强势股并写入候选池，再做批量阶段风控、模拟计划、学习报告和盘中监控：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode cycle --max-cycles 1 --limit 8 --monitor-limit 5
```

持续 Codex 安全任务循环：

```powershell
.\scripts\start_codex_safe_task_loop.ps1
```

安全闭环接口会一次完成候选扫描、模拟计划、学习报告、盘中监控和单股复盘，仍然保持实盘禁用：

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/automation/cycles/run-once?limit=5&monitor_limit=5&review_symbol=SZ002081"
```

浏览器控制模式：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode browser --max-cycles 1
```

盘中监控模式：

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode monitor --max-cycles 1 --limit 5
```

持续模拟守护模式：

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\scripts\start_safe_simulation_loop.ps1 -Mode api -IntervalSeconds 300 -Limit 5
```

该模式会循环写入 `backend/logs/automation_loop.jsonl`，并使用 `--continue-on-error` 跳过临时数据源故障；实盘交易仍保持禁用。

盘中监控循环：

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\scripts\start_intraday_monitor_loop.ps1 -IntervalSeconds 60 -Limit 5
```

## 盘后潜力搜索

盘后或非交易日运行更广的潜力候选搜索，复用自动发现数据源和现有评分/生命周期服务：

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode potential --max-cycles 1 --limit 100
```

API 接口：

```powershell
POST /api/candidates/potential-search/run?limit=100&persist=true
GET  /api/candidates/potential-search/latest
GET  /api/candidates/potential-search/runs?limit=20
```

## 模拟学习闭环

当前版本已经把历史案例、交易记录、用户确认股票和自选股档案统一转成 `learning_samples`，并生成保守回测和每日复盘报告。自动化运行完成后会自动写入 `learning_report_id`。

金螳螂 `SZ002081` 已被标注为“主力拉升出货完成”的阶段训练样本：系统会学习大拉升前一到两年吸筹、试盘、启动拉升、出货完成这些阶段，但短期不按继续创新高或追高买入处理。该结构化样本写入 `main_force_phase_patterns`，并同步进入 `learning_samples`。

主力阶段回放训练器会拉取核心样本近 3 年日线，生成吸筹/试盘/拉升/派发/出货后观察片段，并写入 `main_force_phase_replays`。当前核心样本为金螳螂 `SZ002081` 和三维通信 `SZ002115`：

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/learning/phase-replays/core-samples?lookback_years=3"
```

阶段相似度匹配器会把目标股的阶段路径与金螳螂、三维通信两个核心样本对照，输出最相似样本、相似度分数、诊断和复盘动作。默认可先用于乐凯胶片：

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/learning/phase-matches/SH600135?name=乐凯胶片&lookback_years=3"
```

手动重建样本和生成复盘：

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 -c "from app.learning.service import LearningService; s=LearningService(); print(s.rebuild_samples()); print(s.run_backtest()); print(s.generate_review_report())"
```

复盘报告只用于模拟交易、策略权重评估和经验沉淀，不开启实盘下单权限。

## 行情兜底

`MarketSnapshotBuilder` 的顺序是：

1. AKShare 日线行情。
2. 腾讯只读实时报价兜底。
3. 本地自选股档案兜底。

如果只读报价能拿到现价，训练候选也会进入模拟计划；如果仍缺少行情，则继续保持跳过并写入复盘报告。该兜底只用于观察计划和学习闭环，不会打开实盘下单权限。

## 盘中监控事件流

`MonitoringService` 会从最新候选池中取强候选和观察候选，按轮记录：

- 行情快照来源、价格、涨跌幅
- 与上一轮相比的价格变化和涨跌幅变化
- 规则信号，如 `risk_blocked`、`momentum_up`、`momentum_down`
- 模拟计划动作和是否允许买入

所有事件写入 `monitoring_events`，会话写入 `monitoring_sessions`。前端“运行监控”按钮会触发一轮监控并展示最近事件摘要。

## 监控告警与回放

`MonitoringService` 会在每轮事件之后生成 `monitoring_alerts`：

- `sim_buy_allowed`：模拟计划允许买入，需要人工复核
- `signal_changed`：信号相对上一轮发生变化
- `pct_delta` / `price_delta`：涨跌幅或价格变化超过阈值
- `risk_blocked_observe`：仍被风控阻断，仅保留观察
- `fallback_quote`：使用只读报价兜底，需要在复盘中标注数据源

回放接口 `GET /api/monitoring/replay/{symbol}` 会返回某只股票在当前监控会话里的事件序列和告警序列，适合后续做主力动向复盘。

单股复盘接口 `POST /api/monitoring/reviews/{symbol}` 会把指定股票在当前监控会话中的事件、告警、价格区间、信号分布、风控阻断次数和下一步观察动作汇总到 `monitoring_reviews`。前端“运行自动化”会通过安全闭环接口自动生成金螳螂 `SZ002081` 的复盘；“运行监控”仍可单独触发一轮监控和复盘。

`/api/decision/analyze` 会同时返回：

- 规则评分和候选池分层
- 交易铁律
- 相关战法
- 相似成功/失败案例
- 自选股成本线和卖点档案
- 历史交易流水
- 风险提示和下一步建议

## 前端本地启动

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend
npm install
npm run dev
```

## 当前验证边界

- Forecast Ledger、事件到板块假设、历史板块暴露、双头结构门控、Disclosure Fact 和全市场 backfill 已有代码与聚焦测试，但这不等于已经证明选股准确率或收益。
- 全市场 coverage 和 `amount` 完整度仍需通过可续跑 backfill 持续提高。跨市场与回购 adapter 已能真实写入，但仍需监控新鲜度、来源错误和连续期货换月跳空；少量成功样本不代表数据完整。
- Forecast Feedback 在足够多独立 Decision Snapshot 和到期 Outcome 之前会保持 `insufficient_data`。不得把少量样本、回测完成状态或启发式概率写成稳定胜率。
- 所有结果只用于研究、人工复核和模拟训练；仓库默认并持续要求 `live_trading_enabled=false`。
