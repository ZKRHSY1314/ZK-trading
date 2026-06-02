# V5.6-P58 Dataset2 Training Convergence Review

## Goal

Add a concise Dataset2 convergence review that summarizes whether the current Dataset2 cleanup chain is ready to move toward a future controlled cleanup execution or training-freeze release review.

## Scope

- Add a metadata-only `dataset2_training_convergence_review` event.
- Expose short API routes:
  - `POST /api/learning/dataset2/training-convergence-review`
  - `GET /api/learning/dataset2/training-convergence-reviews`
- Summarize Dataset2 source readiness, staging records, learning-sample isolation, latest quality review, latest P57 approval, and `live_trading_enabled=false`.
- Add dashboard evidence and tests.

## Safety Boundary

- Do not execute cleanup.
- Do not mutate `dataset2_staging_records`.
- Do not write `learning_samples`.
- Do not modify Dataset2 source files.
- Do not export files or create downloads.
- Do not start training.
- Do not connect brokers, place orders, or control trading screens.

## Acceptance

- P58 returns `can_execute_cleanup_now=false`, `writes_learning_samples_now=false`, and `can_start_training_now=false`.
- P58 records only review metadata in `events`.
- Unit/API smoke tests cover the convergence review and history APIs.
- Frontend displays the convergence result without any training or execution button.
