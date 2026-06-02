# Task: V5.6-P56 Dataset2 Controlled Cleanup Apply Execution Plan Execution Final Execution Execution Execution Execution Dry-Run Review

## Goal

Add a metadata-only review gate after the V5.6-P55 aggregate dry-run.

## Scope

- Read the latest or requested P55 dry-run.
- Verify the dry-run is ready for review and aggregate-only.
- Record operator review metadata in the existing `events` table.
- Add backend API, dashboard display/action, tests, release checklist, and skill stage boundary.

## Safety Boundary

- Do not execute cleanup.
- Do not execute SQL payloads.
- Do not mutate `dataset2_staging_records`.
- Do not write `learning_samples`.
- Do not modify Dataset2 source files.
- Do not export files.
- Do not start training.
- Do not connect brokers, place orders, or change live-trading state.

## Acceptance

- Missing or blocked P55 dry-run returns blocked metadata and writes no event.
- Passed P55 dry-run plus the allowed review decision records one review-only event.
- Review evidence keeps `can_execute_now=false`, `contains_sql=false`, `record_bodies_included=false`, `writes_learning_samples_now=false`, and `training_started_now=false`.
- API smoke covers POST/GET.
- Frontend exposes a review button and report card without any execution/training control.
