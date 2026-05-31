# V5.6-P0 Handoff: Dataset2 Training Readiness Gate

## Summary
V5.6-P0 starts the path toward using dataset2 for training by adding a read-only readiness gate and normalized preview. The dataset2 quality report says the pack is useful as rule knowledge and weak-label material, but should not be used for direct training until schema, labels, evidence, and historical outcome gaps are fixed.

## Deliverables
- Add `Dataset2TrainingReadinessService` for read-only dataset2 inspection.
- Add `GET /api/learning/dataset2/readiness`.
- Add `POST /api/learning/dataset2/normalized-preview`.
- Add dashboard controls for readiness and preview.
- Add tests for invalid risk labels, stringified list cleanup, missing evidence, API smoke, and safety flags.
- Update release checklist and the `a-share-trading-cockpit` skill.

## Safety Rules
- Do not start model training in V5.6-P0.
- Do not write dataset2 records into SQLite.
- Do not modify dataset2 source files.
- Do not treat rule labels as proven profitable trading outcomes.
- Do not connect brokers, place real trades, click trading software, or change live-trading state.

## Next Step
V5.6-P1 can add a reviewed dataset2 cleanup/export stage or a database import queue for normalized rule-knowledge samples. It should still keep training disabled until the readiness gate is clean and historical outcome examples exist.
