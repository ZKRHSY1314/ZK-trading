# Stage V1.5 AI Review & Parameter Proposals Handoff

## Summary of Changes
Added a specialized worker and API endpoints to extract simulated trading history, format it into an AI prompt, and parse the resulting `rules.yaml` parameter proposals, with strict safety enforcements.

1. **AI Review Worker**:
   - Created `backend/app/ai/review_worker.py`.
   - Extracts the last 50 simulated trades from `historical_backtest_trades`.
   - Generates a proposed parameter patch (simulated to output a JSON patch).
2. **Safety Gates**:
   - Hardcoded safety floors and ceilings inside the worker before any proposal is persisted.
   - Enforced `min_market_cap >= 5,000,000,000`.
   - Enforced `max_position_ratio <= 0.20`.
   - Prevented disabling of `hard_block` rules (AI cannot set `hard_block = False` on existing blocked rules).
3. **Persistence and API**:
   - Stores reviewed proposals in a new `ai_parameter_proposals` table, retaining both the proposed patch and a log of which safety blocks were applied.
   - Added `POST /api/ai/review/run` and `GET /api/ai/review/proposals`.

## Validation Execution
- Tested the review worker locally by making it generate a mock proposal with invalid bounds (e.g., market cap 3B, position ratio 0.5, and hard block disabled).
- Verified that the `safety_blocks_applied` correctly intercept these modifications, force the values into safe thresholds (5B market cap, 0.2 ratio, true hard block), and records the interventions.

## Safety Confirmations
- The system only creates proposals. It **does not** automatically overwrite `rules.yaml`.
- The AI is structurally prevented from suggesting unsafe parameters via hardcoded runtime intercepts.
