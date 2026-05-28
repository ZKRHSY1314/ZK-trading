# Stage V1 Task 06 Handoff: Simulation, Backtest, and Policy Validation

## 1. Objectives Completed
- **Simulation Accuracy:**
  - Implemented logic in `SimulatedBroker` to enforce A-share trading rules including 100-share lot minimums, T+1 sellable quantity limits, commission rates (min 5 CNY), stamp taxes on sells, and configurable slippage.
  - Cash constraints and positions are updated locally using `simulation_accounts` and `simulation_positions` without external APIs.
- **Backtest Metrics Enhancements:**
  - Expanded `LearningService.run_backtest` to include calculated `total_return`, `skipped_count` due to missing prices, and `data_source_quality`. The metrics are embedded into the returned backtest summary.
- **Policy Gate Hardening:**
  - Hardened `policy_summary` logic in `paper_simulation_evaluation.py`. A policy is now strictly evaluated against:
    - Minimum sample size threshold (`>= 10`)
    - Valid data quality error rate (`< 20%` skips/errors)
    - Strong/mild follow-through positive ratio (`> 50%`)
    - Strict risk check (zero `large_drawdowns`)
  - Policies not meeting these criteria will fallback to conservative conclusions like `insufficient_sample_size`, `insufficient_data_quality`, or `mixed_or_unproven_policy`.
- **Overfitting Guards:**
  - Draft simulation policies remain manual review only. `approve_policy` strictly requires explicit API calls without directly mutating real broker logic.
  - No settings, scoring rules, or active parameters are updated automatically.
  
## 2. Policy-Gate Examples

When `PaperSimulationEvaluationService.policy_summary()` runs, it strictly applies the new logic:
```json
{
  "policy_id": 1,
  "policy_type": "score_reduction",
  "total_evaluations": 15,
  "completed": 12,
  "pending_future_data": 3,
  "skipped_no_price": 0,
  "errors": 0,
  "strong_follow_through": 7,
  "mild_follow_through": 2,
  "failed_signal": 3,
  "large_drawdowns": 0,
  "conclusion": "promising_simulation_policy",
  "disclaimer": "Simulation only. Not investment advice."
}
```

If sample size was small (e.g., `completed = 5`), the conclusion safely shifts to `"insufficient_sample_size"`. If data skips exceed `20%`, it shifts to `"insufficient_data_quality"`.

## 3. Backtest Metric Examples

Metrics are now generated in `run_backtest` with added transparency:
```json
{
  "strategy_name": "local_rule_v1",
  "sample_count": 8,
  "win_rate": 0.0,
  "avg_return": -0.04,
  "profit_loss_ratio": 0.0,
  "max_drawdown": 0.04,
  "blocked_success_count": 0,
  "false_positive_count": 2,
  "pending_count": 0,
  "summary": {
    "predicted_trade_count": 2,
    "total_return": -0.08,
    "skipped_count": 1,
    "data_source_quality": "High (Local SQLite fallback)",
    "guardrail": "该结果只用于模拟权重评估，不产生实盘下单权限"
  }
}
```

## 4. Commands Run
```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app scripts
.\.venv\Scripts\python.exe -m pytest -q
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/learning/simulation-policies/draft-from-experiments"
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/learning/paper-simulations/run-approved?limit=20"
Invoke-RestMethod "http://127.0.0.1:8000/api/learning/paper-simulation-evaluations/summary"
```

## 5. Residual Risks
- The current A-share rules (like T+1) track strictly in the database but may diverge if live corporate actions (dividends/splits) occur since we are evaluating purely off simulated historical snapshots without external real-time data adjustments.
- Baseline comparisons for Sandbox metrics assume a simplified heuristic (`has_baseline_improvement = True` placeholder for `< 0.5` positive ratio gate). A more rigorous historical comparison logic should be adopted in future releases.
