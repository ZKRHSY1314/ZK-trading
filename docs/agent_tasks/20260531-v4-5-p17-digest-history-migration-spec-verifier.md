# V4.5-P17 Digest History Migration Spec Verifier

## Goal

Add an in-memory dry-run verifier for a future `screen_readiness_digest_history` SQLite migration spec.

This stage validates proposed migration text only. It does not execute SQL, create tables, run migrations, write migration files, persist snapshots, create downloads, execute commands, inspect windows, capture pixels, run OCR, click/type, connect brokers, or affect live trading.

## Implemented Scope

- Backend exposes `POST /api/screen-monitoring/readiness-health/history-migration-spec/verify`.
- `ScreenMonitoringService.verify_screen_readiness_digest_history_migration_spec()` derives its expected fields from the V4.5-P16 migration checklist.
- The verifier checks:
  - spec text is present
  - target table is named
  - guarded `CREATE TABLE IF NOT EXISTS` shape exists
  - all required metadata fields are covered
  - sensitive fields are absent
  - dangerous SQL/data-mutating terms are absent
  - operator review remains required
  - migration remains disallowed now
  - live trading remains disabled
- Frontend V4.5 panel adds a "校验迁移草案" action and compact verification status card.
- Release checklist and cockpit skill were updated for V4.5-P17.

## Safety Evidence

- `executes_sql=false`
- `runs_migration_now=false`
- `creates_table_now=false`
- `writes_database_now=false`
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

When no spec text is provided, the API verifies a generated safe default spec preview in memory. Unsafe text containing destructive SQL or sensitive fields returns `spec_verification_failed` with safety blocks, while still preserving all no-execution guarantees.

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

V4.5-P18 can add operator approval metadata for a verified migration spec. It should still avoid applying migrations, writing migration files, creating tables, or persisting digest snapshots.
