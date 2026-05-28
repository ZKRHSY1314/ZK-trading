param(
    [Parameter(Mandatory = $true)]
    [string]$TaskPath
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$AntigravityExe = Join-Path $env:LOCALAPPDATA "Programs\Antigravity\Antigravity.exe"
$ResolvedTask = Resolve-Path -LiteralPath $TaskPath

if (-not (Test-Path -LiteralPath $AntigravityExe)) {
    throw "Antigravity executable not found: $AntigravityExe"
}

$TaskText = Get-Content -Raw -LiteralPath $ResolvedTask
$Prompt = @"
Read AGENTS.md first. You are the executor. Codex is the supervisor.
Implement only the task packet below. Do not expand scope.
Do not enable live trading, broker automation, credential storage, or destructive data changes.
Before handing back, list changed files, commands run, test/build results, skipped checks, and unresolved questions.

$TaskText
"@

Set-Clipboard -Value $Prompt

Write-Host "Opening Antigravity for project:"
Write-Host $ProjectRoot
Write-Host ""
Write-Host "Task prompt copied to clipboard. Paste it into Antigravity's agent input."
Write-Host $ResolvedTask

Start-Process -FilePath $AntigravityExe -ArgumentList @($ProjectRoot) -WorkingDirectory $ProjectRoot
