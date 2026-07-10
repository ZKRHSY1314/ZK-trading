# Domain language

## Cockpit

The local Windows application used to inspect A-share market data, generate review-only decisions, run simulated workflows, and examine evidence. The Cockpit never implies broker or live-account access.

## Control Plane

The single operational entrypoint that coordinates Market Pulse capture, a Simulation Cycle, Training Feedback, and a Decision Snapshot. It records semantic step status instead of treating a successful function call as a successful business result.

## Market Pulse

A time-bounded, source-backed digest of policy, market, and sector evidence. A Market Pulse includes freshness, source coverage, sector signals, and links to its evidence.

## Decision Snapshot

A point-in-time, review-only ranking of candidates produced from market features, rules, Market Pulse evidence, and data-quality gates. Every Decision Snapshot carries its data time and never grants live execution.

## Simulation Cycle

An audited run that discovers candidates, evaluates them, creates simulation plans, monitors results, and records review evidence. A Simulation Cycle can be completed, partial, blocked, or failed.

## Training Feedback

The incremental workflow that converts completed safe tasks into samples, labels matured outcomes from cached market data, and reports decision quality. Training Feedback does not directly rewrite active rules or enable execution.

## Outcome

The future 1/3/5-day observation attached to an earlier prediction after enough trading bars exist. Pending future data is not counted as an accuracy result.

## Schedule Slot

One idempotent time window in which the Control Plane may run a profile. A worker heartbeat proves whether scheduled operation is currently alive.

## Review-only

The operating invariant that permits reading, analysis, simulation, evidence persistence, and human review while excluding broker login, credentials, fund access, and real order placement.
