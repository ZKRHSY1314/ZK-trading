# V2.0 Codex Handoff

## Summary
V2.0 upgrades the project from a simulation/review skeleton into a more credible simulation evidence system. The work remains review-only and simulation-only: no broker adapter, credential, live order endpoint, or real trading control was added.

## Implemented
- Historical backtests now use a conservative execution model and FIFO lot ledger.
- Backtest runs persist closed trades, benchmark comparison, execution warnings, daily equity, and filled/rejected execution events.
- Metrics now separate execution count from closed trade count and calculate realized P/L based win rate, profit/loss ratio, average win/loss, expectancy, and consecutive losses.
- AI parameter proposal validation uses a 70/30 time-series split and rejects proposals when out-of-sample or sample-size checks fail.
- AI proposal generation is routed through a provider-neutral local gateway and writes model audit logs.
- Portfolio risk gates now report exposure, single-position, market regime, daily-loss, drawdown, consecutive-loss cooldown, and daily new-position limits with explicit reasons.
- Monitoring alert actions can push symbols into candidate lifecycle states for review or simulation planning.
- The frontend V2.0 evidence panel shows backtest closed trades, benchmark evidence, execution warnings, risk gate reasons, lifecycle actions, and AI validation evidence.

## Validation
- Backend focused tests passed: `pytest tests/test_backtest_engine.py tests/test_v15_services.py -q`.
- Backend full suite passed before final release validation: `pytest -q`.
- Frontend type check passed: `npx vue-tsc --noEmit`.

## Safety
- `/health` must remain `live_trading_enabled=false`.
- AI can explain, propose, and validate, but cannot modify production `rules.yaml`, bypass hard risk gates, or place real orders.
- Runtime artifacts, SQLite databases, logs, virtualenvs, node_modules, and built frontend assets must stay ignored.
