# Codex + Antigravity Workflow

This workflow lets Codex spend tokens only on planning and review while Antigravity does most implementation work.

## Local Tool Status

- Codex is available through the Codex desktop app in this environment.
- Antigravity is installed at:
  `C:\Users\lenovo\AppData\Local\Programs\Antigravity\Antigravity.exe`
- Antigravity is not currently on `PATH`, so use `tools/start_antigravity_project.ps1` to open it at this repo.
- WSL is present, but this project can use the Windows-native flow first.

## Default Workflow

1. Codex creates the task packet.
   - Fill in `tools/agent_task_template.md`.
   - Include exact scope, acceptance checks, and files likely affected.

2. Open the project in Antigravity.
   ```powershell
   cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system
   .\tools\start_antigravity_project.ps1
   ```

3. Ask Antigravity to implement only the task packet.
   - Paste the task packet.
   - Tell it to read `AGENTS.md` first.
   - Tell it to report commands run and files changed.

4. Codex reviews the result.
   - Review changed files.
   - Run focused checks.
   - Apply final narrow edits when needed.

5. Repeat.

## Recommended Prompt For Antigravity

Use this at the start of an Antigravity session:

```text
Read AGENTS.md first. You are the executor. Codex is the supervisor.
Implement only the task packet below. Do not expand scope.
Do not enable live trading, broker automation, credential storage, or destructive data changes.
Before handing back, list changed files, commands run, test/build results, skipped checks, and unresolved questions.
```

Then paste the filled task packet from `tools/agent_task_template.md`.

## Codex Review Checklist

- Scope matches the task packet.
- No real trading path was enabled.
- No secrets or credentials were added.
- Existing local-first architecture is preserved.
- Backend endpoints return stable, typed payloads.
- Frontend states handle loading, empty, error, and stale data.
- Risk notes are visible for trading-adjacent decisions.
- Build or focused checks were run, or skipped checks are explained.

## When Codex Should Spend Tokens

Use Codex for:

- Product design and architecture decisions
- Acceptance criteria
- Security and trading-risk boundaries
- Diff review
- Final fixes
- Debugging bugs Antigravity could not resolve after one or two attempts

Use Antigravity for:

- Bulk code edits
- UI layout and wiring
- Test scaffolding
- Refactors that follow a Codex-approved plan
- Documentation updates
- Repetitive bug fixes

## Project-Specific Guardrails

- This A-share system remains simulation-first.
- `settings.enable_live_trading` must stay false by default.
- Browser control is allowed only for the local web console and simulation workflows.
- Broker/client screen control stays read-only or disabled unless a future task explicitly designs a separate audited live-trading permission system.

## Troubleshooting: Location Not Supported

If Antigravity fails with this error:

```text
HTTP 400 Bad Request
FAILED_PRECONDITION
User location is not supported for the API use.
```

it means the Antigravity client reached Google, but the backend rejected the request based on Google account eligibility or the detected network location. It is not a project code error.

Run:

```powershell
cd C:\Users\lenovo\Desktop\A股记录\ai_trading_system
.\tools\check_antigravity_region.ps1
```

Checks:

- Antigravity is installed.
- Google connectivity works.
- The current network country/region as seen by `ipinfo.io`.
- Recent Antigravity language-server errors.

Fix options:

- Sign in with a personal Google account that is eligible for Antigravity/Gemini API.
- Verify the Google account age if prompted by Google.
- Use a network exit location supported by Google AI Studio and Gemini API.
- Restart Antigravity after changing account or network.
- If the detected country is supported but Google still rejects it, collect the TraceID and report it to Google AI Developer support/forums as an IP geolocation issue.
