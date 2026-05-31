# V5.0-P2 Portfolio And Symbol Risk Gate Contract

## Summary

V5.0-P2 defines a review-only portfolio and symbol risk gate contract for the future Trade Execution Gateway. It explains what must block a future real-money review even if manual confirmation exists.

This stage still does not connect brokers, store credentials, read account funds, place/cancel/modify real trades, click trading software, write audit tables, create migrations, or enable live trading.

## Added Surface

- `GET /api/trade-execution-gateway/risk-gate-contract`
- `TradeExecutionGatewayService.risk_gate_contract()`
- Dashboard evidence for portfolio and symbol gates
- Release checklist V5.0-P2 entries
- Cockpit skill V5.0-P2 boundary notes

## Portfolio Gates

The contract maps existing simulated portfolio risk limits into future gateway review gates:

- total exposure
- single position exposure
- max daily loss
- max drawdown stop
- consecutive loss cooldown
- max new positions per day
- market regime block/reduce behavior

## Symbol Gates

The contract defines symbol-level blockers:

- stale, degraded, missing, or fallback-only quote data
- limit-up buy and limit-down sell realism
- low-liquidity participation limits
- A-share T+1 same-day sell block
- candidate lifecycle review state
- operator/system `stop_new_entries` flags

## Safety Evidence

- risk gates override manual confirmation
- manual confirmation cannot override risk gates
- AI cannot override risk gates
- `contract_allows_execution_now=false`
- `gateway_can_execute=false`
- `places_real_trade=false`
- `connects_broker=false`
- `live_trading_enabled=false`

## Next Step

V5.0-P3 can design the rollback runbook and final pre-live review package as metadata only. It should still avoid broker adapters, credential handling, real orders, screen-click trading, audit table creation, or live execution.
