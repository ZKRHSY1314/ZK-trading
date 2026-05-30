# Stage V1.1 P0 Rule Trustworthiness Repair Pack Handoff

## Summary of Changes
This repair pack addresses the four P0 credibility gaps identified in the V1.0 optimization review:

1. **Rule Scoring Semantics Refactored**: Modified the rule engine so that hard risk-control (`constitution`) and `risk` rules only act as blockers and do not contribute positive scores, preventing them from contaminating candidate tiers.
2. **Dynamic Limit-up Thresholds Added**: Replaced hardcoded 9.9% checks with a dynamic utility (`price_limits.py`) that infers board types (Main, ST, ChiNext, STAR, BSE) and applies conservative limit-up thresholds accordingly.
3. **Adjusted and Rolling Highs Implemented**: Switched AKShare provider to use forward-adjusted (`qfq`) daily bars. Snapshot builder now injects 250-day and 500-day rolling highs. The strategy prefers this rolling high over all-time unadjusted highs for low-position judgments.
4. **Market-Cap and Data-Quality Gates Enforced**: The strategy now rejects symbols outside of configured market cap bounds. Fallback profiles and real-time quote fallbacks are explicitly downgraded by the planner, preventing strong buy signals based on incomplete data.

## Safety Confirmations
- The `/health` endpoint strictly continues to report `live_trading_enabled=false`.
- No live trading, broker automation, credentials, real order placement, or screen-controlled broker operations have been added.
- The project remains strictly simulation-only and review-only.
- All files changed strictly relate to simulation, rule engine logic, and data processing.

## Validation Execution
The changes have been validated by running the backend compilation checks and the `pytest` suite.
New tests were added specifically for:
- Price limits and board inference.
- Rule engine scoring (constitution rules scoring zero).
- Strategy signals (dynamic limits, rolling highs, market cap bounds).
- Data quality gates (downgrading strong tier on fallback data).

## Codex Review Follow-Up Fixes

During review, Codex found and fixed four issues before final acceptance:

- Removed trailing whitespace reported by `git diff --check`.
- Standardized rolling-high metadata with `rolling_high_120`, `rolling_high_250`, `rolling_high_500`, and `high_window_used`, while keeping legacy `high_250` / `high_500` aliases for compatibility.
- Fixed ST board inference so ordinary names containing the letters `ST` (for example, `Test Success`) are not misclassified as risk-warning stocks.
- Tightened fallback quote/profile handling so low-quality data produces `observe` plans with zero quantity rather than downgraded buy plans.

Final Codex validation:

- `.\.venv\Scripts\python.exe -m compileall app scripts tests` passed.
- `.\.venv\Scripts\python.exe -m pytest -q` passed, 22 tests.
- `git diff --check` passed.
- `/health` returned `live_trading_enabled=False`.
- `git ls-files` forbidden-runtime scan returned no tracked dataset, database, virtualenv, node_modules, dist, logs, cache, or pycache matches.

## Next Steps (V1.2 and Beyond)
- Implement event-driven historical backtesting (moving away from sample label statistics).
- Enhance simulated trading to reflect bid-ask execution probabilities (e.g., limit-up buy failure probability, limit-down sell failure probability).
- UI refinements and further dual-model integration for AI explanations.
