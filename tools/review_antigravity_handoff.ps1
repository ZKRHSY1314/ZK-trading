param(
    [string]$HandoffPath = "docs\agent_tasks\20260524-stage3-offhour-potential-search-handoff.md"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendRoot = Join-Path $ProjectRoot "backend"
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$ResolvedHandoff = Join-Path $ProjectRoot $HandoffPath

if (-not (Test-Path -LiteralPath $ResolvedHandoff)) {
    throw "Handoff file not found yet: $ResolvedHandoff"
}

Write-Host "Reviewing Antigravity handoff:"
Write-Host $ResolvedHandoff
Write-Host ""
Get-Content -Raw -LiteralPath $ResolvedHandoff

Write-Host ""
Write-Host "Running backend compile check..."
Push-Location $BackendRoot
try {
    & .\.venv\Scripts\python.exe -m compileall app scripts
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Running frontend type/build checks..."
Push-Location $FrontendRoot
try {
    & npx vue-tsc --noEmit
    & npx vite build
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Review script completed. Codex should still inspect changed files before acceptance."
