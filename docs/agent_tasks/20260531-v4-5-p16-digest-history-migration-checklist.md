# V4.5-P16 Digest History Migration Readiness Checklist

## Goal

Add a review-only migration readiness checklist for future `screen_readiness_digest_history` persistence.

This stage does not create a table, run a migration, write a migration file, backfill records, create downloads, execute commands, inspect windows, capture pixels, run OCR, click/type, connect brokers, or affect live trading.

## Implemented Scope

- Backend exposes `GET /api/screen-monitoring/readiness-health/history-migration-checklist`.
- `ScreenMonitoringService.screen_readiness_digest_history_migration_checklist()` derives its evidence from the V4.5-P15 history proposal and current health digest.
- The checklist reports:
  - target table and source schema
  - future metadata field mapping
  - excluded sensitive fields
  - migration readiness checks
  - required future artifacts
  - rollback and test requirements
  - safety evidence
- Frontend V4.5 panel shows a "迁移就绪清单" action and a compact migration readiness card.
- Release checklist and cockpit skill were updated for V4.5-P16.

## Safety Evidence

- `writes_database_now=false`
- `creates_table_now=false`
- `runs_migration_now=false`
- `writes_migration_file_now=false`
- `writes_file=false`
- `download_created=false`
- `executes_commands=false`
- `real_screen_capture=false`
- `pixel_data_stored=false`
- `ocr_executed=false`
- `broker_action=false`
- `order_action=false`
- `credential_access=false`
- `live_trading_enabled=false`

## Default Behavior

The endpoint returns `migration_review_ready` when there are no blocking checks. It still reports `migration_allowed_now=false` because the migration file, rollback plan, tests, and operator approval are future artifacts.

## Validation Commands

- `backend\\.venv\\Scripts\\python.exe -m pytest backend\\tests\\test_screen_monitoring.py -q`
- `backend\\.venv\\Scripts\\python.exe -m compileall backend\\app backend\\scripts`
- `backend\\.venv\\Scripts\\python.exe -m pip check`
- `npx vue-tsc --noEmit`
- `npx vite build`
- `npm audit --audit-level=moderate`
- `git diff --check`
- forbidden tracked-file scan
- `codegraph sync`
- `codegraph status`

## Next Candidate

V4.5-P17 can add a dry-run migration spec verifier that validates a proposed SQL migration text in memory only. It should still avoid writing files, creating tables, running migrations, executing commands, or storing digest snapshots.
