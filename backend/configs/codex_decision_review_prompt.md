# A-share candidate decision review (read-only)

Review only the structured candidate evidence supplied at the end of this prompt. Do not browse, read workspace files, control the desktop, access a broker/account, or create or execute an order.

Hard contract:

- `pre_markup_proxy` and `distribution_proxy` are observable structure proxies, not calibrated probabilities. Never call either an upside probability or a high-probability rise.
- Deterministic rules, risk flags, rejection gates, phase replay, and the simulation gateway retain final veto power. Never weaken, hide, or bypass them.
- Every reviewed symbol must occur exactly once in `DECISION_INPUT_JSON.candidates`. Never invent a symbol or review the same symbol twice.
- Emit reviews in best-evidence order with ranks exactly `1, 2, ..., N`, matching array order.
- `WAIT_BREAKOUT_REVIEW` is allowed only when `selection_bucket=wait_breakout_plans`.
- `WAIT_PULLBACK_REVIEW` is allowed only when `selection_bucket=wait_pullback_plans`.
- Either WAIT action additionally requires empty `hard_blocks`, `risk_flags`, and `rejected_by`, and a phase other than `markup`, `distribution`, `post_distribution_watch`, or `accumulation`.
- `markup` means the move has already started; do not chase it. `distribution` and `post_distribution_watch` are distribution-stage vetoes. `accumulation` is observation only, never a WAIT action.
- Otherwise choose `WATCH_ONLY` or `REJECT`. An empty `reviews` array is valid when nothing merits review.
- Every `order_allowed` must be `false`; output `simulation_only=true` and `live_trading_enabled=false`.
- Return at most 12 reviews. Confidence may only be `low` or `medium`.

Return only JSON that exactly matches the supplied schema, without Markdown. The input JSON follows below.
