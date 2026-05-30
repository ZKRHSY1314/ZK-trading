# Stage V1.3 Portfolio Risk & Market Regime Handoff

## Summary of Changes
Added portfolio-level risk gates and market environment filtering to limit exposure during unfavorable market conditions.

1. **Market Regime Service**:
   - Created `backend/app/market_regime/service.py` with `MarketRegimeService`.
   - Uses daily bars for major indices (`sh000001` / `sh000300`) to classify the market environment into `strong`, `neutral`, `weak`, or `extreme_risk` using moving average logic (MA5 and MA20).
2. **Simulation Planner Integration**:
   - Updated `backend/app/simulation/planner.py` to consult `MarketRegimeService`.
   - Halves the standard position sizing if the market is `weak`.
   - Completely blocks new entries (forces `observe` action) and adds risk notes if the market is in `extreme_risk`.
3. **Backtest Engine Integration**:
   - Updated `backend/app/backtest/engine.py` to dynamically fetch the market regime up to the specific simulated trade date (`as_of_date`).
   - Slices per-symbol capital allocations by half during `weak` regimes.
   - Clears all candidate signals, halting entries during `extreme_risk` periods.

## Validation Execution
- Simulated planning logic defaults to safe/neutral if index data is missing or incomplete (`insufficient_data`).
- `SimulationPlanner` and `BacktestEngine` correctly handle the data format from `get_latest_regime`.

## Safety Confirmations
- Does not interact with real broker accounts.
- Fail-safe default mode: If an index is unavailable, position sizing logic falls back safely and does not increase exposure.
