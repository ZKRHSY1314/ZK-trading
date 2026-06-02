# Task: V5.6-P55 Dataset2 Controlled Cleanup Apply Execution Plan Execution Final Execution Execution Execution Execution Dry-Run

## Goal

Add a metadata-only aggregate dry-run after the accepted V5.6-P54 preflight.

## Scope

- Read the latest or requested P54 preflight.
- Simulate aggregate cleanup impact using staging metadata only.
- Record a review-only event in the existing `events` table.
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

- Missing or blocked P54 preflight returns blocked metadata and writes no event.
- Passed P54 preflight plus the allowed dry-run decision records one aggregate-only event.
- Dry-run evidence keeps `can_execute_now=false`, `contains_sql=false`, `record_bodies_included=false`, `writes_learning_samples_now=false`, and `training_started_now=false`.
- API smoke covers POST/GET.
- Frontend exposes a dry-run button and report card without any execution/training control.
