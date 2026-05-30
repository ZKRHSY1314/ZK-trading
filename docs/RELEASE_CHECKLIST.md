# V1 Release Checklist

## 1. Backend Compile & Test
- [ ] Backend compiles successfully (`python -m compileall app scripts`)
- [ ] Backend test suite passes (`pytest tests/`)
- [ ] No `PermissionError` when running tests locally on Windows (verify SQLite tempfiles).

## 2. Frontend Type & Build
- [ ] TypeScript check passes (`npx vue-tsc --noEmit`)
- [ ] Vite build completes successfully (`npx vite build`)
- [ ] NPM audit reports acceptable levels (`npm audit --json --audit-level=moderate`)

## 3. Browser Smoke Test
- [ ] `node scripts/smoke.mjs` runs against local dev server and backend.
- [ ] Returns 0 `console_errors` and 0 `api_failures`.
- [ ] Verifies critical UI (Health Header, Price Readiness Panel, SIMULATION ONLY disclaimer).

## 4. API Health & Data Safety
- [ ] `/health` endpoint strictly reports `live_trading_enabled=false`.
- [ ] `broker_control_blocked` is explicitly enforced in capabilities.
- [ ] `.gitignore` rules actively ignore `local_overrides.py` and `*.db` preventing accidental real broker commits.
- [ ] Hard risk-control rules do not contribute positive score to candidate pools.
- [ ] Dynamic limit-up thresholds and market cap bounds are actively enforced.
- [ ] Fallback profiles and real-time quote fallbacks are strictly downgraded in confidence.

## 5. Automation One-Cycle Smoke
- [ ] `python scripts/automation_loop.py --mode daily-bar-cache --max-cycles 1` runs cleanly.
- [ ] `python scripts/automation_loop.py --mode paper-evaluation --max-cycles 1` runs cleanly.

## 6. Desired Workday Schedule Cadence
The following automation schedule is recommended during active trading days:
- **10:00 AM:** First cycle (Candidate scan, morning momentum check).
- **1:00 PM (13:00):** Mid-day cycle (Trend persistence, early reversals).
- **4:00 PM (16:00):** Post-market close cycle (Daily bars finalized, paper evaluation).

**Non-Trading Days (Weekends/Holidays):**
- Run `--mode potential` for broad off-hours potential searches (discovering 200+ candidates for the coming week).
