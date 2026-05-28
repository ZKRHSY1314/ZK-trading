# V1 Task 05: AI Explanations, Case Retrieval, And Reports

## Goal

Upgrade explanations and reports so each alert or simulation result cites rules, risk gates, data quality, and similar historical/user cases without pretending to be guaranteed prediction or investment advice.

## Scope

Likely files:

- `backend/app/ai/model_gateway.py`
- `backend/app/knowledge/repository.py`
- `backend/app/decision.py`
- `backend/app/learning/service.py`
- `backend/app/monitoring/service.py`
- `backend/app/api/routes.py`
- `frontend/src/App.vue`
- Docs under `docs/`

## Requirements

1. Explanation contract
   - Define a structured explanation object with:
     - signal summary
     - matched rules
     - risk blockers
     - data source and data quality
     - similar cases or phase samples
     - uncertainty notes
     - simulation-only disclaimer
   - The frontend should render this object cleanly.

2. Case retrieval
   - Retrieve relevant examples from:
     - user notes
     - main force phase patterns
     - learning samples
     - monitoring reviews
     - paper simulation evaluations
   - Keep retrieval deterministic and local-first for v1.

3. Report polish
   - Daily reports should summarize:
     - candidate changes
     - monitoring alerts
     - paper simulation outcomes
     - readiness/fallback quality
     - lessons learned
     - open review items
   - Reports must not include real trade instructions.

4. AI gateway
   - Keep LLM provider optional.
   - If no API key/provider is configured, produce deterministic local explanations.
   - Never require a paid API for v1 basic use.

## Acceptance Checks

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall app scripts
```

Run API checks against a running backend:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/decision/analyze-symbol/SH600135"
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/learning/reports/daily"
Invoke-RestMethod "http://127.0.0.1:8000/api/learning/reports/latest"
```

Run frontend type/build if UI is changed:

```powershell
cd frontend
npx vue-tsc --noEmit
npx vite build
```

## Safety

- Explanations must be phrased as review/simulation support, not buy/sell directives.
- Do not add external broker or credential features.

## Handoff

Create `docs/agent_tasks/stage_v1_task05_handoff.md` with sample explanation/report JSON and UI evidence if applicable.

