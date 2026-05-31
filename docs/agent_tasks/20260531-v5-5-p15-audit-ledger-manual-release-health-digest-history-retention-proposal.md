# V5.5-P15 Audit Ledger Manual Release Health Digest History Retention Proposal

## Goal
Add a review-only proposal for future manual release health digest history retention. This stage only describes metadata fields, excluded sensitive data, dedupe policy, retention limits, and review gates.

## Scope
- Add API-only proposal generation over the current P14 health digest.
- Show proposal status and persistence-blocked evidence in the V5.5 gateway dashboard.
- Keep all outputs metadata-only and non-executable.

## Safety Boundary
Do not create tables, write digest history rows, persist evidence, write migration files, execute SQL, approve releases, enable migrations, connect brokers, place trades, or change live trading state.

## Acceptance
- Backend unit/API smoke covers proposal generation and safety flags.
- Frontend typecheck/build passes.
- `live_trading_enabled=false` remains visible in health and proposal evidence.
