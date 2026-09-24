# Service profiles and controlled recovery

Status: `integration_pending`. The code and its portable tests are complete (cloud, 2026-09-24). Nothing in this document has run on the local Windows machine. Nobody has started a stack, installed a task or restored a database with it. Local acceptance is the checklist at the end.

## Why profiles

`scripts/run_stack.ps1` used to start everything, every time: backend, frontend and nine workers. Those workers score, forecast, run simulations, call models, calibrate, refresh market data and write reference data. So recovering the cockpit also silently restarted all of those writers.

`-ServiceProfile` now makes the choice explicit. The default is still `full`, so existing callers and the scheduled task behave exactly as before.

| Profile | Starts | Excluded (never launched) | Write targets |
| --- | --- | --- | --- |
| `review` | backend, frontend | all nine workers | runtime DB only |
| `full` (default) | backend, frontend, all workers; the two Codex workers only with `-EnableCodexSearch 1` | Codex workers when search is off | runtime DB, `market_history.sqlite3`, universe manifest |

`backend/scripts/stack_profiles.py` is the single source of truth. For each component it records the exact arguments, the heartbeat it writes, the configuration echo it must report, and the writes it makes. A test pins `run_stack.ps1`'s launch arguments to it.

**`review` is not read-only.** Starting the backend runs `SQLiteStore.init()`, which does all of the following to the runtime database:

- creates tables and indexes if they are missing;
- applies `ALTER TABLE` migrations, including the decision-day `run_kind` and evaluation policy-version migrations;
- runs normalisation `UPDATE`s on `daily_bar_cache`: `adjustment_mode`, `volume_unit`, and the Sina-fallback `quality_status`.

Any POST sent from the cockpit also writes. That includes a manual control-plane run, a backtest, a proposal action and ingest endpoints. Only the workers are excluded. **The runtime database must therefore be backed up before any profile starts.**

## Commands

Preview a plan. This starts nothing, touches no database and writes no file:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\stack_profiles.py plan --profile review
```

Start the minimal profile under supervision. `-SwitchProfile` is required whenever a tracked stack, or a stale PID file, was started under another profile:

```powershell
.\scripts\ensure_stack.ps1 -ServiceProfile review -EnableCodexSearch 0
```

Read-only diagnostics, unchanged: exit 0 means healthy, 2 means needs attention. This path reaches no helper, no start and no stop:

```powershell
.\scripts\ensure_stack.ps1 -CheckOnly
```

Stop, unchanged: this stops only the processes whose identity has been verified:

```powershell
.\scripts\stop_stack.ps1
```

### What a start records

Before launching anything, `run_stack.ps1` records two things:

- The plan, in `logs\stack_plan.json`: selected and excluded components, arguments, target paths, expected writes and `plan_sha256`. It writes this only after every preflight refusal has been checked, so a refused start never overwrites the plan of a stack that is still running.
- The PID file, `logs\run_stack.pids.json`, now `run_stack_pids.v2`. It records `service_profile`, `plan_sha256`, `selected_components` and `write_targets`. Each excluded component is recorded as `{enabled: false, reason: not_in_profile | codex_search_disabled}`. A v1 file has no profile and is read as `full`.

## Supervision behaviour

**Profile.** `ensure_stack.ps1` treats a stack as healthy only if its tracked profile equals the requested one, every selected component passes the existing identity and heartbeat checks, and every excluded component is recorded as disabled *and* is not running.

- A different tracked profile is never switched implicitly. The output is `status: profile_mismatch`, exit 2, and nothing is stopped or started.
- This matters because the scheduled task passes no profile, so it asks for `full`. It therefore cannot silently turn a manual `review` recovery into a full stack.

**Restart budget.** `backend/scripts/stack_recovery.py` allows at most 3 restarts per rolling hour, counting successful and failed attempts alike.

- Beyond that the output is `status: restart_suppressed`, exit 2, and there is no stop and no start.
- If the attempt log (`logs\ensure_stack_restarts.json`) is unreadable, malformed or dated in the future, restarts are suppressed. The log is never treated as empty; an operator inspects it and deletes it.

**Failed cycle versus dead process.**

- A worker whose process is verified but whose last cycle failed has a fresh heartbeat with status `failed`. It reads as `degraded` and does **not** trigger a restart.
- A restart is considered only for a missing or unverified process identity, a stale or invalid heartbeat, or a configuration mismatch.

**Heartbeat timestamps.**

- `/readyz` used to clamp a heartbeat dated in the future to age 0, so it looked fresh indefinitely. It now reports it as `invalid` with `reason: future_timestamp`; clock skew of up to 60 s is tolerated. `ensure_stack` treats `invalid` as unhealthy.
- `stack_diagnostics.py` now:
  - reports `disabled` for every profile-excluded worker, not only for the Codex workers;
  - reports `running_but_not_in_profile` if an excluded worker is found running;
  - reports `configuration_mismatch` when a heartbeat's configuration echo differs from the profile contract;
  - treats `skipped` (an idle, up-to-date cycle) as healthy;
  - still never reports the market data as fully healthy while the calendar is a weekday proxy.

## Backup, validation and rollback for local recovery

Scope of this procedure:

- **Always:** the runtime database `<root>\trading_local.sqlite3`.
- **Only if the `full` profile is used:** `<root>\market_history.sqlite3` and `<root>\backend\logs\current_a_share_universe.json`.

It covers no other file. The plan's `backup_before_start` field lists exactly the files to back up for the chosen profile.

1. **Stop and check.**
   - Stop the stack: `.\scripts\stop_stack.ps1`.
   - Confirm that nothing tracked remains: `.\scripts\ensure_stack.ps1 -CheckOnly` should report the backend as unavailable.
   - Confirm that no `trading_local.sqlite3-wal` or `-journal` file exists. If one does, stop and investigate before copying anything.
2. **Inventory before.** This step only reads the database:
   ```powershell
   backend\.venv\Scripts\python.exe backend\scripts\db_inventory.py --database trading_local.sqlite3 --label before
   ```
3. **Back up.**
   - Copy each target file to a dated folder outside the repository.
   - Record `Get-FileHash -Algorithm SHA256` for the original and for the copy. The two must be equal, and must equal `sha256` in `logs\db_inventory_before.json`.
4. **Start the chosen profile.** Use `ensure_stack.ps1 -ServiceProfile review ...` as shown above.
5. **Validate.**
   - Run `ensure_stack.ps1 -CheckOnly`. Expect `needs_attention` while the market data is stale or only calendar-proxied. Record the issue list rather than treating it as a failure.
   - Stop the stack, then take a second inventory:
     ```powershell
     db_inventory.py --database trading_local.sqlite3 --label after --compare-with logs\db_inventory_before.json
     ```
   - For `review`, the only acceptable changes are:
     - schema or migration differences from `SQLiteStore.init()`;
     - row counts affected by the `daily_bar_cache` normalisation;
     - rows written by cockpit actions you deliberately took.
   - Any other table growth means a writer outside the plan ran. **Roll back and investigate.**
6. **Roll back if needed.**
   - Run `stop_stack.ps1`.
   - Restore each backed-up file over the original.
   - Confirm that the file's SHA-256 equals the backup's and that `db_inventory.py --compare-with logs\db_inventory_before.json` reports `bytes_identical: true`.
   - Also remove `logs\stack_plan.json` and `logs\run_stack.pids.json` if they now describe a stack that is no longer running.

Never delete, compact or vacuum the database as part of recovery. Never refresh market data as a side effect. A market-data write scope must be defined separately.

## What the cloud proved, and what it did not

**Proven with portable fixtures on Linux**, by `tests/test_stack_profiles.py`, `tests/test_stack_recovery.py`, `tests/test_stack_diagnostics.py` and `tests/test_runtime_health.py`:

- the planner's selection, write declarations and determinism;
- the plan record cannot overwrite a database;
- `run_stack.ps1` launch arguments match the planner, and every worker launch is gated on the plan (static checks);
- the restart budget, including fail-closed state handling;
- stale, future, PID-mismatch, identity-mismatch (PID reuse), failed-cycle, configuration-mismatch and partially-updated-cache classifications;
- `/readyz` rejects future heartbeats;
- `ensure_stack.ps1` behaviour, run under **PowerShell 7 on Linux** with `run_stack` and `stop_stack` replaced by scripts that throw:
  - `-CheckOnly` never reaches a helper, start or stop;
  - `profile_mismatch` and `restart_suppressed` never reach a stop or start;
  - an allowed restart that fails is recorded and the failure propagates.

**Not proven, needs Windows:**

- Windows PowerShell 5.1 execution of the edited scripts;
- `Start-Process`, `Get-CimInstance` process identity and port checks;
- the backend actually starting under `review` with no workers;
- `stop_stack.ps1` against a `review` PID file;
- scheduled-task interaction;
- real heartbeats;
- the backup and rollback procedure itself.

## Local Windows acceptance checklist (review profile)

Run this in a normal interactive session with the persistent task **not installed**, or disabled. Do not run a broad "start everything" command.

1. **Get the branch and run the tests.**
   - `git fetch`, then check out this branch.
   - Run `backend\.venv\Scripts\python.exe -m pip install -e "backend[dev]"`.
   - Run `python -m pytest -q -rs` in `backend`. Expect 0 failures. The Windows-only tests should now run instead of being skipped.
2. **Check the scripts.**
   - Run `python -m ruff check app tests scripts`.
   - Parse all `.ps1` files with Windows PowerShell 5.1, as in the CI step.
3. **Preview the plan.** Run `stack_profiles.py plan --profile review` and confirm that `selected` is `["backend","frontend"]` and that `write_targets` contains only the runtime database.
4. **Record the state.** Run `.\scripts\ensure_stack.ps1 -CheckOnly` and save its output. Confirm that no Python, Node or `happ` process from this project is running.
5. **Back up.** Perform steps 1–3 of the backup procedure above for the runtime database only.
6. **Start review.**
   - Run `.\scripts\ensure_stack.ps1 -ServiceProfile review -EnableCodexSearch 0`.
   - Add `-SwitchProfile` if it reports `profile_mismatch` against an old full-profile PID file.
   - Expect `status: started` and `service_profile: review`.
7. **Check the recorded state.**
   - `logs\run_stack.pids.json` should be `run_stack_pids.v2`, with `service_profile: review`, all nine workers recorded as `enabled: false`, and only backend and frontend holding PIDs.
   - Task Manager should show exactly one uvicorn backend and one Vite frontend, and no worker scripts.
   - `/health.live_trading_enabled` should be `false`.
8. **Check supervision.**
   - Run `.\scripts\ensure_stack.ps1 -ServiceProfile review -EnableCodexSearch 0` again. Expect `already_running`, with no restart and no new PIDs.
   - Run `.\scripts\ensure_stack.ps1` (full) once. Expect `profile_mismatch`, exit 2, and nothing stopped.
   - Run `.\scripts\ensure_stack.ps1 -CheckOnly`. Every worker should read `disabled`, and no worker should appear as `not_running_or_unverified`.
9. **Test fault injection.**
   - Kill the backend process manually.
   - Run `ensure_stack -ServiceProfile review -EnableCodexSearch 0` up to four times within an hour. The first three runs restart; the fourth must report `restart_suppressed`.
   - Afterwards, delete `logs\ensure_stack_restarts.json` deliberately.
10. **Stop, compare and restore.**
    - Run `stop_stack.ps1`, then `db_inventory.py --label after --compare-with logs\db_inventory_before.json`.
    - Review the differences using the rules in step 5 of the backup procedure.
    - Restore if anything unexplained changed.
11. **Keep the persistent task inactive.** Do not install or activate it as part of this acceptance. It still runs the `full` profile; changing its definition is a separate, versioned decision.
