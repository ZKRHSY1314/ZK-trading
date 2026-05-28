$ErrorActionPreference = "Stop"

$AntigravityExe = Join-Path $env:LOCALAPPDATA "Programs\Antigravity\Antigravity.exe"
$LanguageServerLog = Join-Path $env:APPDATA "Antigravity\logs\language_server.log"

Write-Host "Antigravity executable:"
if (Test-Path -LiteralPath $AntigravityExe) {
    Write-Host "  OK  $AntigravityExe"
} else {
    Write-Host "  MISSING  $AntigravityExe"
}

Write-Host ""
Write-Host "Network location probe:"
try {
    $Location = Invoke-RestMethod -Uri "https://ipinfo.io/json" -TimeoutSec 10
    Write-Host "  Country: $($Location.country)"
    Write-Host "  Region:  $($Location.region)"
    Write-Host "  City:    $($Location.city)"
    Write-Host "  Org:     $($Location.org)"
} catch {
    Write-Host "  FAILED: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "Google connectivity:"
try {
    Invoke-WebRequest -Uri "https://www.gstatic.com/generate_204" -TimeoutSec 10 -UseBasicParsing | Out-Null
    Write-Host "  OK"
} catch {
    Write-Host "  FAILED: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "Recent Antigravity region errors:"
if (Test-Path -LiteralPath $LanguageServerLog) {
    Select-String -LiteralPath $LanguageServerLog -Pattern "User location is not supported|FAILED_PRECONDITION|agent executor error" |
        Select-Object -Last 10 |
        ForEach-Object { Write-Host "  $($_.Line)" }
} else {
    Write-Host "  Log not found: $LanguageServerLog"
}

