# V5.6-P1 Handoff: Dataset2 Cleanup Package

## Summary
V5.6-P1 turns the V5.6-P0 readiness findings into a review-only cleanup package. The package previews normalized records, hashes the source and normalized payloads, and lists the cleanup actions needed before any import, export, or training stage.

## Deliverables
- Add `Dataset2TrainingReadinessService.cleanup_package`.
- Add `POST /api/learning/dataset2/cleanup-package`.
- Add dashboard display for package id, review actions, blockers, and risk/list/evidence cleanup counts.
- Add backend tests for cleanup package safety and API smoke.
- Update release checklist and `a-share-trading-cockpit` skill with V5.6-P1 boundaries.

## Safety Rules
- Do not modify dataset2 source files.
- Do not write normalized records into SQLite.
- Do not create export files or downloads in this stage.
- Do not start model training.
- Do not treat weak rule labels as historical profitability evidence.
- Do not connect brokers, place real trades, click trading software, or change live-trading state.

## Next Step
V5.6-P2 can add a separate reviewed import queue or local export artifact plan. Training should remain disabled until evidence fields and historical outcome examples are sufficient.
