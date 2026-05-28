param(
    [Parameter(Mandatory = $true)]
    [string]$Name
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Template = Join-Path $ProjectRoot "tools\agent_task_template.md"
$TaskDir = Join-Path $ProjectRoot "docs\agent_tasks"

if (-not (Test-Path -LiteralPath $Template)) {
    throw "Task template not found: $Template"
}

New-Item -ItemType Directory -Force -Path $TaskDir | Out-Null

$SafeName = ($Name -replace "[^\p{L}\p{Nd}\-_]+", "-").Trim("-")
if ([string]::IsNullOrWhiteSpace($SafeName)) {
    $SafeName = "task"
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Target = Join-Path $TaskDir "$Stamp-$SafeName.md"

Copy-Item -LiteralPath $Template -Destination $Target

Write-Host "Created task packet:"
Write-Host $Target

