# 2026-06-13 Round 19: 完整窗口验证与外部策略学习合成

## 安全边界

本文只服务于研究、回测、沙盒模拟、同花顺模拟盘训练和人工复核。

- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`
- 不写生产 `configs/rules.yaml`
- 不连接真实券商，不保存凭证，不触发真实买入、卖出、撤单或资金操作

## 本轮工程推进

本轮修复了非交易时段研究循环里的一个关键验证问题：最新 Dataset2 信号虽然适合进入观察队列，但如果还没有足够未来日线完成 entry delay 和持仓 horizon，就不应该进入历史验证折。

新增逻辑：

- signal optimization 从 `signals` 扩展为 `signals + recent_signals`，最多取最近 120 条可操作信号。
- 参数网格按每组 `entry_delay_days / horizon_days` 计算完整回测窗口。
- 70/30 验证和 walk-forward 都只使用有完整未来窗口的信号。
- 输出 `complete_window` 证据，记录可验证信号数、无 entry bar 数和未满足 exit horizon 数。
- 前端 V5.7 面板展示优化样本数和去重样本数。

## run_id 57 关键证据

研究循环状态：

- `status=completed`
- `signal_optimization.status=passed_for_simulation_review`
- `live_trading_enabled=false`
- 样本：120 条优化信号，来自 20 条展示信号 + 119 条 recent signals 去重后的最近窗口
- 完整窗口：`entry_delay_days=1, horizon_days=3` 有 51 条可完整回测信号

当前稳定候选：

- `entry_delay_days=1`
- `horizon_days=3`
- `stop_loss_pct=0.06`
- `take_profit_pct=0.18`
- `confirmation_filter=none`
- `attribution_filter=turning_point_requires_green_or_strong`

70/30 样本外验证：

- 15 笔 closed trades
- 胜率 73.33%
- 平均单笔收益 8.17%
- 等权累计收益 199.53%
- 盈亏比 2.34

walk-forward：

- 4 折
- 33 笔 closed trades
- 加权胜率 72.73%
- 加权平均单笔收益 8.61%
- 总等权累计收益 1156.83%
- 最弱折胜率 62.50%
- 最弱折累计收益 41.29%

学习过滤器里最强候选：

- `confirmation_filter=strong_reclaim`
- `attribution_filter=star_and_turning_point_quality_gate`
- 验证 13 笔，胜率 84.62%，平均单笔收益 10.38%，等权累计收益 240.30%

解释：这不是放宽交易权限，而是把“尚不能验证的最新信号”从历史稳定性测试里剔除，让验证对象更干净。最新信号仍进入观察和 near-reclaim 队列，等待后续盘中/日线确认。

## 浏览器外部学习映射

本轮用浏览器对照了以下外部资料：

- VectorBT: https://vectorbt.dev/
- scikit-learn TimeSeriesSplit: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- QSTrader: https://github.com/mhallsmoore/qstrader
- Backtrader slippage: https://www.backtrader.com/docu/slippage/slippage/
- Wyckoff Method: https://www.wyckoffanalytics.com/wyckoff-method/

映射到 ZK-trading：

- VectorBT 的启发是批量参数实验，但要有预算边界。本项目保留 252 组基础网格，再对 top candidate 做 48 组 learning-filter 二次复验，避免无控制地拖慢运行。
- TimeSeriesSplit 的启发是时间序列不能随机打乱，也不能让未来数据泄漏。本轮新增的 complete-window 过滤就是为了解决“最新信号还没有未来 K 线，却被拿来做验证”的问题。
- QSTrader 的启发是信号、组合、风控、执行、账户要分层。本项目继续让 Dataset2 只生成研究信号，PortfolioRisk/执行模型/Sim-Cockpit 决定是否进入模拟复核。
- Backtrader slippage 的启发是没有滑点、涨跌停阻断、流动性约束的收益不可信。本项目必须继续保留一字板拒绝、partial/rejected、成交额参与率限制。
- Wyckoff 的启发与用户原方法一致：三维通信、金螳螂、乐凯胶片这类样本不能只看单日涨跌，而要看吸筹、试盘、主升、派发和派发后观察。

## 合成后的策略框架

当前最合理的主线不是“看到涨停就买”，而是双轨监督：

1. 宽口径发现轨：发现主力试盘、低位放量、强势跟随、near-reclaim 等潜力样本，只提高研究和观察优先级。
2. 稳定确认轨：用 `turning_point_requires_green_or_strong`、`strong_reclaim`、`star_and_turning_point_quality_gate` 等过滤器降低买早、弱确认和高波动板块风险。
3. 完整窗口验证：只有历史样本具备完整 entry/exit 观察窗口，才进入参数验证和 walk-forward。
4. 模拟盘执行前置：即使 review gate 通过，也仍需候选新鲜、风险 gate 通过、模拟窗口验证、锚点识别、`SIMULATION_SCREEN_CLICK` 和 `simulation_allowed=true`。
5. 仓位：20 万模拟资金下，首次小额复核仍建议 2%-4%；强确认后最多 6%-8%；分布加仓必须依赖持仓回读和二次确认。

## 下一步建议

- 把 run 57 的 stable candidate 写入 simulation planner 的 review-only note，不改变 `allowed`、仓位、数量或生产规则。
- 将 `complete_window` 和 `learning_filter_candidates` 在前端 V5.7 面板显示得更清楚。
- 对通过但未执行的 near-reclaim 候选做盘中监控：重新站上信号价且无硬风险时，才进入小额模拟 dry-run。
- 周末继续扩大历史样本和阶段标注，重点学习三维通信、金螳螂、乐凯胶片的吸筹/试盘/主升/派发差异。
- 真实交易人工确认权限仍不应打开；当前证据足以提升模拟复核优先级，但还不足以跨越真实资金边界。

## Round 20: Planner 监督证据接入

本轮已经把 run 57 的 stable candidate 接入 `SimulationPlanner` 的 review-only 说明层。

新增 planner 证据：

- `complete-window evidence`：展示 `input_signals=120`、`eligible_signals=51`、`no_entry_bar=14`、`incomplete_exit_window=55`。
- `learning-filter evidence`：展示 48 个 learning-filter 候选、top filter 为 `strong_reclaim + star_and_turning_point_quality_gate`，验证胜率 84.62%，验证累计收益 240.30%。
- `attribution_filter=turning_point_requires_green_or_strong` 会被识别为稳定确认轨，而不是裸宽口径轨。

安全约束：

- 这些证据只进入 `reasons` / `risk_notes`。
- 不改变 `allowed`。
- 不改变 `quantity`。
- 不改变 `position_ratio`。
- 不写 `rules.yaml`。
- 不绕过 PortfolioRisk、Sim-Cockpit window verification 或 `SIMULATION_SCREEN_CLICK` gate。

当前含义：

run 57 的结果足以提升模拟复核优先级，尤其适合“先 dry-run、再小额模拟试单、再根据持仓回读决定是否分布加仓”的训练流程。但它仍不是实盘依据，也不是自动放权依据。下一步应该把 near-reclaim 盘中监控和模拟执行 gate 串起来，让高胜率研究候选在真实模拟盘里积累成交/未成交/风控阻断样本。
