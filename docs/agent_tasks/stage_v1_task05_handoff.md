# Stage V1 Task 05 Handoff: AI Explanations, Case Retrieval, And Reports

## 1. Objectives Completed
- **Explanation Contract:** Created `Explanation` class in `backend/app/models.py` with `signal_summary`, `matched_rules`, `risk_blockers`, `data_quality`, `similar_cases`, `uncertainty_notes`, and a clear `simulation_disclaimer`.
- **Case Retrieval Integration:** The `DecisionAnalyzer` populates the `KnowledgeContext` deterministically (principles, strategies, similar trade cases, user notes), which is then passed to the `ModelGateway`.
- **AI Gateway Implementation:** Established `DisabledModelGateway` as the default local generator. It produces consistent, transparent explanations utilizing rules and local snapshot data without needing a paid LLM API.
- **Report Polish:** Updated `LearningService.generate_review_report` to include `monitoring_alerts`, `paper_simulation_outcomes`, `readiness_fallback_quality`, `lessons_learned`, and `open_review_items`.
- **Frontend Rendering:** Updated `frontend/src/App.vue` to fetch and render `analysis.explanation`. Added a dedicated **"生成分析解释" (Generate Analysis Explanation)** button alongside the simulation plan button.

## 2. Example Report Outputs

### AI Explanation Format
When `/api/decision/analyze-symbol/SH600135` is called, the explanation returned is:
```json
{
  "explanation": {
    "signal_summary": "[SH600135] 综合得分 50.0, 评级 rejected。价格: 9.72。 当前受到硬风控阻断。",
    "matched_rules": [],
    "risk_blockers": [
      "破位/均线空头排列: 连续 3 个交易日收盘价低于短期均线且均线呈空头排列",
      ...
    ],
    "data_quality": "AKShare (local)",
    "similar_cases": [],
    "uncertainty_notes": [
      "当前未连接外部大模型，此为基于规则引擎的本地确定性解释。",
      "若数据源存在延迟，可能影响评级准确性。"
    ],
    "simulation_disclaimer": "SIMULATION ONLY: This is an AI-generated analysis for simulation and review purposes only. Not investment advice."
  }
}
```

### Daily Learning Report Structure Updates
`/api/learning/reports/daily` now includes:
```json
{
  "monitoring_alerts": [...],
  "paper_simulation_outcomes": {
    "win_rate": 0.0,
    "avg_return": 0.0,
    "profit_loss_ratio": 0.0,
    "max_drawdown": 0.0
  },
  "readiness_fallback_quality": {
    "skipped_count": 0,
    "fallback_note": "部分数据源由于接口限制或网络问题导致兜底或跳过，将在复盘中继续追踪。"
  },
  "lessons_learned": "重点关注/优秀/高分样本优先，风险标记为大或有时降级观察",
  "open_review_items": {
    "pending_count": 0,
    "false_positives": 0
  }
}
```

## 3. UI Evidence
The frontend `App.vue` was updated to display the AI decision block cleanly under the Knowledge panel. Type checks (`vue-tsc`) and builds (`vite build`) have both successfully passed.

## 4. Next Steps
- Proceed to Task 06: Simulation Backtest and Policy Validation (`docs/agent_tasks/20260528-v1-task-06-simulation-backtest-and-policy-validation.md`).
