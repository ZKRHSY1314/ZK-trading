# V4.5-P21 Digest History Manual Release Package

## Summary

V4.5-P21 adds a final review-only manifest for the future screen readiness digest history migration. It aggregates P15-P20 evidence into one manual release package so the operator can see whether the migration review evidence is complete before any separate migration work is written.

## Added Surface

- `GET /api/screen-monitoring/readiness-health/history-migration-release-package`
- `ScreenMonitoringService.screen_readiness_digest_history_release_package()`
- Dashboard button: `最终发布包清单`
- Dashboard card: `Release Package`
- Release checklist V4.5-P21 entries
- Cockpit skill V4.5-P21 boundary notes

## Package Evidence

The package includes manifest items for:

- P15 retention proposal.
- P16 migration checklist.
- P17 dry-run migration spec verifier.
- P18 approval metadata.
- P19 release readiness.
- P20 approval freshness.

It also returns a deterministic `package_id` based on current statuses, spec hash, approval id/hash, release status, approval review status, and freshness window.

## Safety Evidence

The release package preserves:

- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`
- `migration_allowed_now=false`
- `execution_allowed_now=false`
- `executes_sql=false`
- `runs_migration_now=false`
- `creates_table_now=false`
- `writes_database_now=false`
- `writes_file=false`
- `download_created=false`
- `writes_migration_file_now=false`
- `writes_digest_history_table_now=false`

The package is delivered as an API response only. It does not write files, create downloads, write database records, apply migrations, execute SQL, create tables, capture pixels, run OCR, click screens, connect brokers, or change live-trading state.

## Validation Commands

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_screen_monitoring.py -q
backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts
Set-Location backend; .\.venv\Scripts\python.exe -m pytest -q
Set-Location frontend; npx vue-tsc --noEmit
Set-Location frontend; npx vite build
Set-Location frontend; npm audit --audit-level=moderate
git diff --check
codegraph status
```

## Next Step

V4.5 digest-history migration review scaffolding is now ready to pause. The next larger milestone should be V5.0 Trade Execution Gateway planning as review-only architecture metadata first, not broker integration or live order execution.
