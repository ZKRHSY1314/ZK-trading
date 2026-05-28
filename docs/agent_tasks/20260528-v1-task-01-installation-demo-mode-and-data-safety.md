# V1 Task 01: Installation, Demo Mode, And Data Safety

## Goal

Make the project usable from a fresh clone without the private `数据集1` folder or local SQLite database, while keeping dataset and runtime files out of git forever.

## Scope

Likely files:

- `.gitignore`
- `README.md`
- `backend/.env.example`
- `backend/app/config.py`
- `backend/scripts/import_legacy_data.py`
- `backend/configs/user_knowledge_seed.json`
- New demo seed script or fixture under `backend/scripts/` or `backend/configs/`
- Optional release docs under `docs/`

## Requirements

1. Fresh-clone bootstrap
   - Add clear commands for backend install, frontend install, and local startup.
   - Support running without the private legacy dataset.
   - If `LEGACY_DATA_DIR` is missing, importer should report a friendly warning and continue with demo/user seed data where possible.

2. Demo seed mode
   - Provide a tiny non-private demo seed path that creates enough rows to show the dashboard, candidate scores, monitoring, paper simulation, and daily-bar readiness panels.
   - Do not include raw historical dataset files.
   - Do not fabricate real market history. Demo rows must be labeled as demo/fixture when they are synthetic.

3. Data safety
   - Ensure SQLite databases, logs, data exports, datasets, caches, and build artifacts are ignored.
   - Add a documented pre-push check that confirms forbidden files are not tracked.
   - Keep `backend/.env.example` tracked, but never commit `.env`.

4. User knowledge seed
   - Preserve Sanwei Communication, Gold Mantis, and Lucky Film knowledge seed entries.
   - Keep them clearly marked as user-provided learning/monitoring context, not investment advice.

## Acceptance Checks

Run from the repo root:

```powershell
git check-ignore -v backend\trading_local.sqlite3 backend\logs\automation_loop.jsonl frontend\node_modules backend\.venv
git ls-files | Select-String -Pattern '数据集1|trading_local\.sqlite3|node_modules|\.venv|__pycache__|backend/logs|frontend/dist'
```

Run backend checks:

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app scripts
.\.venv\Scripts\python.exe -m pip check
```

Run a fresh/demo bootstrap command added by this task and show it can produce a working `/health` plus at least one dashboard-visible sample without `数据集1`.

## Safety

- `/health` must stay `live_trading_enabled=false`.
- Do not add credentials or external broker access.
- Demo data must never be presented as real trading evidence.

## Handoff

Create `docs/agent_tasks/stage_v1_task01_handoff.md` with changed files, commands, results, and any fresh-clone caveats.

