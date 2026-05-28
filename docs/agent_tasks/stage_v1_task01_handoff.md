# Stage V1 Task 01 Handoff

## Task Status
**Completed**

## Files Changed
- `backend/scripts/import_legacy_data.py`: Modified to check if `LEGACY_DATA_DIR` exists. If not, warns and uses demo data + user seed to avoid crashing on fresh clones.
- `backend/configs/demo_seed.json` (New): Created a tiny demo seed fixture with a mock principle, strategy, and trade record.
- `README.md`: Replaced the backend local run instructions with a unified "首次安装与运行 (Demo Mode)" guide, providing clear steps for fresh clones without private datasets.

## Commands Run
- `git check-ignore -v backend\trading_local.sqlite3 backend\logs\automation_loop.jsonl frontend\node_modules backend\.venv`
- `git ls-files | Select-String -Pattern '数据集1|trading_local\.sqlite3|node_modules|\.venv|__pycache__|backend/logs|frontend/dist'`
- `.\.venv\Scripts\python.exe -m compileall app scripts`
- `.\.venv\Scripts\python.exe -m pip check`
- `.\.venv\Scripts\python.exe -X utf8 scripts\import_legacy_data.py`
- `.\.venv\Scripts\python.exe -c "from fastapi.testclient import TestClient; from app.main import app; print(TestClient(app).get('/health').json())"`

## Results
- `git check-ignore` correctly confirmed that `trading_local.sqlite3`, `automation_loop.jsonl`, `node_modules`, and `.venv` are ignored.
- `git ls-files` returned empty output, verifying no forbidden files are currently tracked.
- Python compilation and `pip check` completed successfully with no broken requirements.
- Import script successfully falls back to demo mode when the legacy data directory is missing.
- `/health` endpoint correctly responded with `{'status': 'ok', 'environment': 'local', 'live_trading_enabled': False}`.

## Safety & Data-Safety Evidence
- `/health` clearly reports `live_trading_enabled: False`.
- `trading_local.sqlite3` and `demo_seed.json` are isolated and do not expose real broker access or credentials.
- `.gitignore` successfully prevents SQLite runtime databases, log files, node_modules, and `.venv` from being committed. `.env` is ignored while `.env.example` is tracked.
- No live trading functionality was added or activated.

## Known Risks / Skipped Checks
- The frontend was not fully started via `npm run dev` since it requires an interactive browser session, but the backend demo API is confirmed working.

## Unresolved Questions for Codex Review
- None. Ready for Task 02.
