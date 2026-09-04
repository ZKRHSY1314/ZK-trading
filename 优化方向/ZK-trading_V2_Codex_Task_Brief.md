# ZK-trading V2.0 Codex 任务说明

> 交给 Codex 使用。  
> 项目：`ZKRHSY1314/ZK-trading`  
> 当前建议阶段：`V2.0 - 模拟/回测/风控可信度增强`  
> 核心原则：**先让模拟盘和回测结果可信，再考虑更复杂的 AI 或实盘相关能力。**

---

## 0. 背景判断

当前项目已经完成到 `v1.5 simulation review milestone` 附近，不再是单纯骨架项目。现有系统已经包含：

- FastAPI 后端。
- Vue/Vite 前端控制台。
- SQLite 本地存储。
- AKShare / 本地缓存数据通路。
- 候选池扫描、生命周期、监控告警。
- 模拟交易与 T+1 等基础约束。
- 历史回测 API。
- 市场环境与组合风险状态。
- AI 参数提案与验证/审批流程。
- 前端 V1.2-V1.5 验证面板。

但当前下一阶段的关键问题不是“继续堆功能”，而是：

> 回测、模拟成交、组合风控、AI 调权依据是否足够可信。

因此 V2.0 应优先修正“可信度基础”，避免 AI 在不可靠回测指标上做调权。

---

## 1. 最高优先级安全边界

以下边界必须贯穿所有任务：

1. **禁止实盘自动下单。**
2. **禁止添加真实券商接口。**
3. **禁止添加券商登录、券商 API、账号密码、cookie、token、实盘订单控制。**
4. **禁止新增任何真实买入/卖出/委托接口。**
5. `/health` 必须继续返回：

```json
{
  "live_trading_enabled": false
}
```

6. 所有新增能力必须保持：

```text
simulation-only
review-only
audit-friendly
non-advisory
```

7. AI 可以做：

```text
解释
总结
提出参数调整 proposal
发起回测验证
输出风险提示
```

8. AI 不可以做：

```text
绕过硬风控
直接修改生产 rules.yaml
启用实盘权限
发真实订单
绕过人工审批
```

---

## 2. Codex 工作方式

本项目推荐工作流：

```text
Codex = 规划、架构、任务拆分、验收标准、最终审查
Antigravity = 批量实现、UI wiring、重复性修改、首轮 bugfix
Human = 实盘、凭证、破坏性操作、重大依赖变更审批
```

每个非平凡任务都应按以下流程：

1. Plan
2. Implement
3. Self-check
4. Review
5. Record

每个阶段完成后写 handoff 文档，说明：

```text
- 改了哪些文件
- 为什么改
- 跑了哪些命令
- 结果如何
- 已知风险
- 下一步建议
```

---

## 3. V2.0 总目标

```text
V2.0 目标：
不是让 AI 自动交易，
而是让模拟交易、历史回测、组合风控、盘中监控、AI 参数提案都变得可验证、可审计、可复盘。
```

具体目标：

1. 提高历史回测可信度。
2. 修正交易配对、胜率、盈亏比等核心指标。
3. 增强涨跌停、部分成交、流动性约束。
4. 增加 benchmark comparison。
5. 补全组合风控：日亏损、最大回撤、连续亏损冷却。
6. 打通 monitoring lifecycle 与 candidate lifecycle。
7. 引入 provider-neutral AI ModelGateway，但保持 review-only。
8. 前端增加回测曲线、回撤曲线、交易明细、证据展示。

---

## 4. V2.0 开始前：本地基线验收

在任何新开发前，先跑完整检查，确认当前 v1.5 是可靠基线。

### Backend

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend

.\.venv\Scripts\python.exe -m compileall app scripts tests
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

### Frontend

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend

npx vue-tsc --noEmit
npx vite build
npm audit --json --audit-level=moderate
```

### Repo safety

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system

git diff --check
git status --short
git ls-files | rg "数据集1|trading_local\.sqlite3|\.venv|node_modules|frontend/dist|backend/logs|__pycache__|\.pytest_cache"
```

### 预期结果

```text
- 后端 compileall 通过
- pytest 通过
- pip check 通过
- frontend type check 通过
- vite build 通过
- npm audit 无 moderate 以上不可接受漏洞
- git diff --check 无 trailing whitespace 等问题
- git status 不包含私有数据、数据库、日志、缓存、dist、node_modules、虚拟环境
- /health 仍然 live_trading_enabled=false
```

---

# 5. V2.0-P0：回测可信度增强

## 5.1 任务目标

当前优先级最高的是历史回测。后续 AI 调权、策略复盘、参数验证都依赖回测结果。  
如果回测不可信，AI 的参数建议也会不可信。

目标：

```text
把当前 event-driven backtest 从“能跑”升级为“指标可信、成交约束合理、风险解释清楚”。
```

---

## 5.2 子任务 A：修正交易配对与盈亏指标

### 当前问题

当前回测中，胜率和盈亏比计算仍偏粗糙：

- `win_rate` 不应简单用卖出价与股票平均买入价比较。
- `profit_loss_ratio` 不应使用总卖出额 / 总买入额。
- 应该基于每笔平仓交易的 realized P/L 计算。
- 当前 `trade_count` 也需要明确是成交笔数、开仓次数，还是完整 round-trip 次数。

### 建议实现

新增或扩展 backtest trade ledger：

```text
position_lots
closed_trades
realized_pnl
realized_pnl_pct
holding_days
entry_date
exit_date
entry_price
exit_price
exit_reason
fees
stamp_tax
slippage_cost
```

卖出时按以下方式之一匹配：

```text
- FIFO lots，推荐
- average cost，先保守实现也可接受，但必须文档注明
```

### 指标应改为

```text
total_return
annualized_return
max_drawdown
win_rate
profit_loss_ratio
average_win
average_loss
expectancy
trade_count
closed_trade_count
open_position_count
average_holding_days
max_consecutive_losses
exposure_ratio
skipped_due_to_data_count
rejected_by_risk_count
blocked_by_regime_count
```

### 涉及文件

优先查看并修改：

```text
backend/app/backtest/engine.py
backend/app/backtest/metrics.py
backend/tests/test_backtest_engine.py
backend/tests/test_v15_services.py
```

如需新增：

```text
backend/app/backtest/ledger.py
backend/tests/test_backtest_metrics.py
```

### 验收标准

```text
- 每笔卖出都能追踪对应成本
- realized_pnl 正确扣除 fee、stamp_tax、slippage
- win_rate 基于 closed trades
- profit_loss_ratio = average_win / abs(average_loss)
- expectancy = win_rate * average_win - loss_rate * abs(average_loss)
- 增加 fixture 测试覆盖盈利、亏损、部分持仓未平仓
```

---

## 5.3 子任务 B：增强涨跌停与成交模型

### 当前目标

A 股回测必须更保守地模拟以下情况：

```text
- 一字涨停无法买入
- 一字跌停无法卖出
- 涨停/跌停附近成交概率降低
- 部分成交
- 成交额不足时不能假设无限流动性
```

### 建议新增配置

可放入 config 或 rules：

```yaml
backtest_execution:
  max_participation_rate: 0.005
  default_partial_fill_ratio: 0.5
  limit_up_buy_policy: reject_if_one_word_limit
  limit_down_sell_policy: reject_if_one_word_limit
  conservative_gap_fill: true
```

### 成交规则建议

买入：

```text
- 如果 low >= limit_up_price * 0.99，视为一字/强封涨停，默认 reject
- 如果计划买入金额 > 当日 amount * max_participation_rate，则按流动性上限缩小或部分成交
- 如果最终数量不足 100 股，reject
```

卖出：

```text
- 如果 high <= limit_down_price * 1.01，视为跌停难卖，默认 reject
- 止损触发但跌停无法成交时，记录 blocked_exit
- 次日继续尝试退出
```

新增交易字段：

```text
fill_status: full | partial | rejected
reject_reason
requested_quantity
filled_quantity
liquidity_cap_amount
```

### 涉及文件

```text
backend/app/backtest/engine.py
backend/app/data/price_limits.py
backend/app/config.py
backend/tests/test_backtest_engine.py
```

如需新增：

```text
backend/app/backtest/execution.py
backend/tests/test_backtest_execution.py
```

### 验收标准

```text
- 一字涨停日不会产生买入成交
- 一字跌停日不会产生卖出成交
- 成交额太小时产生 partial 或 rejected
- 所有 rejected/partial 都写入 trades 或 execution_events
- 测试覆盖涨停、跌停、低流动性、正常成交
```

---

## 5.4 子任务 C：增加 benchmark comparison

### 目标

每次历史回测都必须回答：

```text
策略到底有没有跑赢基准？
是绝对赚钱，还是只是大盘上涨？
回撤是否比基准更小？
```

### 建议 benchmark

第一版支持：

```text
sh000001 上证指数
sh000300 沪深300
```

可选后续：

```text
zz1000 / 中证1000
创业板指
```

### 新增指标

```text
benchmark_symbol
benchmark_return
benchmark_max_drawdown
excess_return
strategy_vs_benchmark_drawdown_delta
correlation_to_benchmark
```

### 数据源要求

```text
- 优先使用 daily_bar_cache
- benchmark 数据不足时明确返回 insufficient_benchmark_data
- 不允许用 latest quote 伪造历史 benchmark
```

### 涉及文件

```text
backend/app/backtest/engine.py
backend/app/backtest/metrics.py
backend/app/data/daily_bar_cache.py
backend/app/api/routes.py
frontend/src/App.vue
```

### 验收标准

```text
- POST /api/backtest/runs 返回 metrics.benchmark_return
- GET /api/backtest/runs/{id} 返回 benchmark 信息
- benchmark 数据不足时不影响策略回测，但必须显示风险提示
- fixture 测试包含策略跑赢和跑输 benchmark 两种情况
```

---

## 5.5 子任务 D：样本内 / 样本外验证

### 目标

AI 参数提案不能只看最近一次回测，也不能只在同一段历史上验证。

新增验证方式：

```text
train_period
validation_period
out_of_sample_period
```

### 建议实现

在 backtest input 中支持：

```json
{
  "start_date": "2024-01-01",
  "end_date": "2025-12-31",
  "validation_split": {
    "train_ratio": 0.7,
    "mode": "time_series"
  }
}
```

或者先实现简单版本：

```text
前 70% 日期 = train
后 30% 日期 = out_of_sample
```

AI proposal validation 必须比较：

```text
before_config train
after_config train
before_config out_of_sample
after_config out_of_sample
```

### 验收标准

```text
- AI proposal validation 不再只取 latest completed run
- validation 结果包含 in_sample 和 out_of_sample
- out_of_sample 恶化时不得 approved_for_simulation
- trade_count 不足时 validation_failed
```

---

# 6. V2.0-P1：组合风控补全

## 6.1 任务目标

当前组合风控已有基础：

```text
max_total_exposure
max_single_position
market_regime gate
```

但还需要补齐：

```text
max_daily_loss
max_drawdown_stop
consecutive_loss_cooldown
max_new_positions_per_day
```

---

## 6.2 新增风控状态

建议在 `PortfolioRiskService.state()` 中输出：

```json
{
  "posture": "normal | reduce | stop_new_entries | cooldown",
  "gates": [
    {
      "name": "daily_loss",
      "status": "ok | reduced | blocked",
      "value": -0.021,
      "limit": -0.03,
      "reason": "..."
    }
  ]
}
```

新增 gates：

```text
daily_loss
max_drawdown
consecutive_losses
new_positions_today
total_exposure
single_position
market_regime
```

---

## 6.3 接入位置

必须接入：

```text
backend/app/simulation/planner.py
backend/app/backtest/engine.py
backend/app/monitoring/service.py
backend/app/risk/portfolio.py
frontend/src/App.vue
```

策略：

```text
normal: 正常模拟计划
reduce: 降低仓位
cooldown: 观察，不新增
stop_new_entries: 禁止新增模拟买入
```

---

## 6.4 验收标准

```text
- 当日亏损超过 max_daily_loss 后，不再新增模拟买入
- 最大回撤超过 max_drawdown_stop 后，进入 stop_new_entries
- 连续亏损达到阈值后，进入 cooldown
- weak market regime 降低 position_ratio
- extreme_risk market regime 禁止新开仓
- SimulationPlanner 和 BacktestEngine 行为一致
- 前端能展示每个 gate 的状态和原因
```

---

# 7. V2.0-P2：监控生命周期与候选生命周期打通

## 7.1 任务目标

当前项目已有 monitoring sessions、events、alerts、alert actions。  
下一步需要从“有告警”升级为“有生命周期”。

---

## 7.2 建议状态机

候选股生命周期：

```text
discovered
watching
strong_candidate
simulated_plan_ready
alerted
acknowledged
ignored_today
review_required
rejected
archived
```

状态转换必须可追踪：

```text
symbol
old_state
new_state
reason
trigger_rule
data_quality
market_regime
operator_action
created_at
```

---

## 7.3 Operator actions

保留并增强：

```text
acknowledge
ignore_today
add_to_review
simulate_buy_plan
simulate_sell_plan
reject
```

要求：

```text
- 任何 action 都不能触发实盘订单
- ignore_today 后当天不重复提醒同一 symbol/reason
- add_to_review 后进入收盘复盘列表
- simulate_buy_plan 只生成模拟计划，不执行真实交易
```

---

## 7.4 涉及文件

```text
backend/app/monitoring/service.py
backend/app/candidates/lifecycle.py
backend/app/storage/sqlite_store.py
backend/app/api/routes.py
frontend/src/App.vue
backend/tests/test_v15_services.py
```

可新增：

```text
backend/tests/test_monitoring_lifecycle.py
```

---

## 7.5 验收标准

```text
- alert action 会改变 lifecycle
- ignored_today 当天不重复提醒
- stale data 会 de-escalate
- hard risk 会进入 rejected 或 review_required
- lifecycle API 可以按 symbol 查询完整路径
- 前端显示当前状态、最近原因、可用操作
```

---

# 8. V2.0-P3：AI ModelGateway 与审计日志

## 8.1 任务目标

当前 AI review 仍然偏 mock。V2.0 可以加入 provider-neutral gateway，但必须保持：

```text
review-only
proposal-only
simulation-only
```

---

## 8.2 建议接口

新增：

```text
backend/app/ai/gateway.py
```

接口：

```python
class ModelGateway:
    def analyze_signal(self, context: dict) -> dict:
        ...

    def summarize_daily_review(self, context: dict) -> dict:
        ...

    def propose_parameter_change(self, context: dict) -> dict:
        ...

    def review_risk(self, context: dict) -> dict:
        ...
```

Provider：

```text
disabled
mock
openai_env
qwen_env
local_http
```

---

## 8.3 Provider 规则

```text
- API key 只从环境变量读取
- 不允许写入 SQLite
- 不允许返回给前端
- 无 key 时返回 provider_unavailable
- mock provider 用于测试
- disabled provider 必须稳定可用
```

---

## 8.4 AI audit log

新增或扩展表：

```text
ai_audit_logs
```

字段建议：

```text
id
provider
model
task_type
input_summary_json
output_summary_json
risk_flags_json
linked_symbol
linked_run_id
linked_proposal_id
status
created_at
```

禁止保存：

```text
raw secret
api key
credential
broker account
huge raw prompt
```

---

## 8.5 Proposal validation 增强

AI proposal 不得直接修改 `rules.yaml`。

必须流程：

```text
draft
validation_failed / validation_passed
pending_human_review
approved_for_simulation
rejected
```

通过条件：

```text
- enough trade count
- max_drawdown 不恶化
- win_rate 不恶化
- profit_loss_ratio 不恶化
- out_of_sample 不恶化
- hard risk blocks preserved
- live_trading_enabled=false
```

---

## 8.6 验收标准

```text
- 没有 API key 时 AI review 正常返回 unavailable，而不是报错
- mock provider 可以生成 deterministic proposal
- proposal 不能直接修改 rules.yaml
- approval 只表示 approved_for_simulation
- 所有 AI 调用有 audit log
- 测试覆盖 hard_block 不能被 AI 关闭
- 测试覆盖 enable_live_trading 不能被 AI 修改
```

---

# 9. V2.0-P4：前端证据面板增强

## 9.1 目标

前端不要做成营销页，而应变成交易控制台。  
下一步重点不是美观，而是展示证据链。

---

## 9.2 新增/增强面板

### A. 回测详情面板

展示：

```text
equity curve
drawdown curve
benchmark comparison
closed trades
open positions
skipped/rejected reasons
execution fill statuses
```

### B. 今日作战面板

展示：

```text
强候选
观察候选
禁止买入原因
盘中提醒
模拟计划
组合风控姿态
大盘环境
```

### C. 复盘面板

展示：

```text
今日提醒数量
确认/忽略/复盘数量
系统建议 vs 后续走势
错误归因：数据 / 规则 / 风控 / 人工执行
AI 总结，仅供复盘
```

---

## 9.3 推荐前端文件

```text
frontend/src/App.vue
frontend/src/api.ts
```

如果 App.vue 继续变大，建议拆分：

```text
frontend/src/components/BacktestPanel.vue
frontend/src/components/RiskPanel.vue
frontend/src/components/MonitoringLifecyclePanel.vue
frontend/src/components/AiReviewPanel.vue
```

---

## 9.4 验收标准

```text
- npx vue-tsc --noEmit 通过
- npx vite build 通过
- 前端不展示 raw prompt
- 前端明确显示 simulation-only / review-only
- live trading 按钮仍然 disabled
- 回测图表和交易表可读
```

---

# 10. 建议 Issue 拆分

## Issue 1：V2.0 回测成交模型增强

```text
目标：
增强涨跌停、部分成交、流动性限制。

验收：
- 一字涨停无法买入
- 一字跌停无法卖出
- 支持 partial/rejected fill
- 成交额上限生效
- 新增 fixture 测试
```

---

## Issue 2：修正回测交易配对和盈亏指标

```text
目标：
基于 closed trades 计算真实胜率、盈亏比、expectancy。

验收：
- realized_pnl 正确
- win_rate 基于 closed trades
- profit_loss_ratio 基于 average_win / average_loss
- 支持未平仓统计
- 新增 metrics 测试
```

---

## Issue 3：增加 benchmark comparison 和样本外验证

```text
目标：
回测必须和指数基准比较，AI proposal 必须有样本外验证。

验收：
- backtest metrics 包含 benchmark_return/excess_return
- benchmark 数据不足时明确提示
- proposal validation 包含 in_sample/out_of_sample
- out_of_sample 恶化时 validation_failed
```

---

## Issue 4：组合风控补全

```text
目标：
实现 daily loss、max drawdown、consecutive loss cooldown。

验收：
- SimulationPlanner 接入
- BacktestEngine 接入
- MonitoringService 接入
- 前端显示 gate 状态和原因
- 测试覆盖 blocked/reduced/cooldown
```

---

## Issue 5：监控生命周期和候选生命周期打通

```text
目标：
让每个候选股从发现到复盘都有状态轨迹。

验收：
- action 会改变 lifecycle
- ignore_today 防重复提醒
- hard risk 转入 rejected/review_required
- lifecycle API 可查询 symbol 状态历史
```

---

## Issue 6：AI ModelGateway 与审计日志

```text
目标：
加入 provider-neutral AI gateway，但保持 review-only。

验收：
- disabled/mock provider 可用
- env key only
- 不存储、不暴露 API key
- AI 只生成 proposal
- 所有 AI 调用有 audit log
```

---

## Issue 7：前端回测与复盘证据面板

```text
目标：
前端展示 equity、drawdown、benchmark、trades、risk gates、lifecycle。

验收：
- vue-tsc 通过
- vite build 通过
- 不展示 raw prompt
- live trading 仍禁用
```

---

# 11. 每个任务完成后的验证命令

Backend：

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\backend

.\.venv\Scripts\python.exe -m compileall app scripts tests
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Frontend：

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system\frontend

npx vue-tsc --noEmit
npx vite build
npm audit --json --audit-level=moderate
```

Repo：

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system

git diff --check
git status --short
git ls-files | rg "数据集1|trading_local\.sqlite3|\.venv|node_modules|frontend/dist|backend/logs|__pycache__|\.pytest_cache"
```

API smoke：

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/system/capabilities
curl http://127.0.0.1:8000/api/risk/portfolio-state
curl http://127.0.0.1:8000/api/market-regime/latest
curl http://127.0.0.1:8000/api/backtest/runs
```

---

# 12. 禁止事项

本阶段禁止：

```text
- 实盘自动下单
- 真实券商 API
- 券商网页登录自动点击买入/卖出
- 存储账号、密码、cookie、token
- 新增真实 order placement endpoint
- AI 直接修改 rules.yaml
- AI 自动启用新权重
- 未经验证的策略上线
- 提交本地 SQLite 数据库
- 提交私有数据集
- 提交 .env
- 提交 frontend/dist
- 提交 node_modules
- 提交 logs/cache
```

---

# 13. 建议 V2.0 完成定义

V2.0 可以视为完成，当且仅当：

```text
1. 回测指标基于真实 closed trades。
2. 涨跌停、流动性、部分成交有保守处理。
3. 回测结果包含 benchmark comparison。
4. AI proposal validation 包含样本外验证。
5. 组合风控包含 daily loss、max drawdown、consecutive loss cooldown。
6. monitoring lifecycle 和 candidate lifecycle 打通。
7. AI ModelGateway 存在，但只用于 review/proposal。
8. 前端能展示回测曲线、回撤、交易明细、风控 gate、候选生命周期。
9. 所有测试和 build 通过。
10. /health 始终 live_trading_enabled=false。
```

---

# 14. 给 Codex 的首个执行建议

建议 Codex 不要一次性做完整 V2.0。  
先做第一个小闭环：

```text
V2.0 Task 01:
修正 backtest trade ledger、closed trade matching、win_rate、profit_loss_ratio、expectancy，并补测试。
```

完成后再做：

```text
V2.0 Task 02:
增强涨跌停、部分成交、流动性限制。
```

原因：

```text
交易配对和指标是所有后续验证的地基。
先修指标，再修成交模型，再做 benchmark 和 AI proposal validation。
```

---

## 15. 首个任务的更详细 Prompt

可以直接给 Codex：

```text
请在 ZK-trading 项目中执行 V2.0 Task 01。

目标：
修正历史回测中的交易配对和核心绩效指标，使 win_rate、profit_loss_ratio、expectancy 等指标基于 closed trades / realized P&L，而不是粗糙的买卖总额或平均价格。

必须遵守：
- 不添加实盘交易能力。
- 不添加券商接口。
- 不保存任何凭证。
- 不修改 enable_live_trading 默认值。
- /health 必须继续返回 live_trading_enabled=false。
- 所有新增逻辑仅用于 historical backtest / simulation。

优先查看：
- backend/app/backtest/engine.py
- backend/app/backtest/metrics.py
- backend/tests/test_backtest_engine.py
- backend/tests/test_v15_services.py
- backend/app/storage/sqlite_store.py

实现要求：
1. 增加 closed trade / realized P&L 计算。
2. 卖出时按 FIFO 或明确文档化的 average-cost 方式匹配买入成本。
3. 每笔 closed trade 应记录：
   - symbol
   - entry_date
   - exit_date
   - quantity
   - entry_price
   - exit_price
   - fees
   - stamp_tax
   - realized_pnl
   - realized_pnl_pct
   - holding_days
   - exit_reason
4. 修正指标：
   - win_rate
   - profit_loss_ratio
   - average_win
   - average_loss
   - expectancy
   - closed_trade_count
   - open_position_count
   - average_holding_days
   - max_consecutive_losses
5. 保持现有 API 尽量兼容。
6. 为新指标增加 deterministic fixture tests。
7. 更新相关 handoff 文档。

验收命令：
cd backend
.\.venv\Scripts\python.exe -m compileall app scripts tests
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check

若修改前端：
cd frontend
npx vue-tsc --noEmit
npx vite build

最后请输出：
- Files changed
- Tests run
- Key behavior changes
- Safety confirmation
- Remaining risks
```

---

# 16. 备注

V2.0 的方向不是提高“预测能力”的宣传，而是提高“系统不会骗自己”的能力。

优先让系统诚实回答：

```text
这笔交易为什么买？
为什么不能买？
如果买了，真实约束下能不能成交？
成交后真实 P/L 是多少？
这个规则是否跑赢基准？
这个 AI 提案是否经过样本外验证？
为什么拒绝或批准？
```

只要这些问题能稳定回答，后续再做更复杂的 AI 才有意义。
