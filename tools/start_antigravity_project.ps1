$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$AntigravityExe = Join-Path $env:LOCALAPPDATA "Programs\Antigravity\Antigravity.exe"

if (-not (Test-Path -LiteralPath $AntigravityExe)) {
    throw "Antigravity executable not found: $AntigravityExe"
}

Write-Host "Opening Antigravity for project:"
Write-Host $ProjectRoot

Start-Process -FilePath $AntigravityExe -ArgumentList @($ProjectRoot) -WorkingDirectory $ProjectRoot

