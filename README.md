# A股 AI 自动化交易系统

这是第一版项目骨架，目标是先完成“AI 盘中监控 + 严格模拟交易 + 人工确认 + 复盘学习”，暂不接入实盘自动下单。

这是 `ZK-trading` 仓库中的 A股交易软件项目。

## 当前共识

- 运行方式：本地 Windows 优先，浏览器控制台使用，后续可迁移云端。
- 数据源：AKShare 免费数据优先。
- 行情兜底：AKShare 日线临时失败时，系统会尝试腾讯只读报价接口生成保守模拟快照。
- 扫描方式：集合竞价和开盘阶段全A扫描，之后只监控候选池。
- 策略方式：可配置规则引擎，网页可开关和调参，文件可版本管理。
- 决策顺序：交易铁律 > 风控 > 策略规则 > 案例相似度 > AI解释。
- 模拟交易：严格模拟 A股 T+1、涨跌停、集合竞价、手续费、印花税、100股最小交易单位。
- AI学习：AI 可自动调整策略权重，但只能作用于模拟盘评分，必须经过回测/模拟指标验证。
- 实盘按钮：第一版仅显示禁用占位。

## 目录

- `docs/PRD.md`：产品需求文档。
- `docs/TECHNICAL_ROADMAP.md`：分阶段技术路线。
- `docs/RISK_BOUNDARIES.md`：风控和权限边界。
- `docs/AUTOMATION_CONTROL.md`：自动化运行文档。
- `docs/RELEASE_CHECKLIST.md`：发版自检清单。
- `backend/`：FastAPI 后端骨架。
- `frontend/`：Vue 控制台骨架。

## 首次安装与运行 (Demo Mode)

本项目支持在没有私有数据集 `数据集1` 的情况下，使用内置的 Demo 种子数据进行运行体验。

1. **后端安装与运行**

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .

# 导入种子数据（无私有数据时将自动使用 demo_seed）
python -X utf8 scripts\import_legacy_data.py

# 启动后端
uvicorn app.main:app --reload
```
API 健康检查：`http://127.0.0.1:8000/health`
API 文档：`http://127.0.0.1:8000/docs`

2. **前端安装与运行**

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend
npm install
npm run dev
```
前端访问地址详见终端输出（通常为 `http://127.0.0.1:3000` 或 `http://localhost:5173`）。

## 导入交易知识库

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\Activate.ps1
python -X utf8 scripts\import_legacy_data.py
```

导入结果会写入：

- `backend/trading_local.sqlite3`

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

## 自动化循环进程

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend
.\.venv\Scripts\python.exe -X utf8 scripts\automation_loop.py --mode api --max-cycles 1 --limit 5
```

全周期模式会先自动扫描涨停/强势股并写入候选池，再做批量阶段风控、模拟计划、学习报告和盘中监控：

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

## 下一步

第一轮实现建议从这 4 件事开始：

1. 导入 `数据集1` 中的原则库、战法库、案例库、交易记录。
2. 用 AKShare 拉取日线和分钟行情，先验证字段稳定性。
3. 实现灯盏策略的选股、情景识别、买卖信号。
4. 让模拟账户产生可回放的交易流水和复盘报告。
