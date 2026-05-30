# Stage V1.2 Event-Driven Historical Backtesting Handoff

## Summary of Changes
Replaced the sample/statistics-based backtest with a real daily-bar event-driven engine.
1. **Backtest Engine**: Created `backend/app/backtest/engine.py` with `BacktestEngine`. It processes historical daily bars chronologically, constructs `MarketSnapshot` on the fly, and uses the `RuleEngine` to determine signals.
2. **Persistence**: Added SQLite tables (`historical_backtest_runs`, `historical_backtest_trades`, `historical_backtest_daily_equity`) in `sqlite_store.py` to store metrics, trade history, and equity curve.
3. **Exits and Costs**: Implemented T+1 enforcement, 100-share lots, transaction fees (0.0003), stamp tax (0.0005 for sell), and simple exits (stop loss, take profit, max holding days).
4. **Data Fallback Safety**: Engine only processes bars marked as 'ready' and bypasses incomplete fallback profiles for entries.
5. **API & CLI**: Added `/api/backtest/runs` endpoints in `routes.py` and the `--mode backtest` option in `scripts/automation_loop.py`.

## Validation Execution
- Ran compilation checks and `pytest tests/test_backtest_engine.py` successfully.
- Engine creates a run, saves trades, and generates metrics without calling real broker operations.

## Safety Confirmations
- No live trading capability introduced. `/health` remains `live_trading_enabled=false`.
- Missing history gracefully skips without generating fabricated trades.
- No broker capability added.
