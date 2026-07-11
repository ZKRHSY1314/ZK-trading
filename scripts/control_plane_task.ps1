[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet("Install", "Uninstall", "Status", "RunOnce")]
    [string]$Action = "Status",
    [string]$TaskName = "ZKTrading-ReviewOnly-ControlPlane",
    [int]$EnsureIntervalMinutes = 5,
    [bool]$EnableCodexSearch = $true
)

$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "The persistent control-plane task is supported only on Windows."
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EnsureScript = Join-Path $PSScriptRoot "ensure_stack.ps1"
$PowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source

function Get-TaskStatus {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    $health = $null
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 3
    }
    catch {
        $health = @{ status = "offline"; error = $_.Exception.Message }
    }
    return [ordered]@{
        schema_version = "control_plane_task.v1"
        task_name = $TaskName
        installed = $null -ne $task
        task_state = if ($task) { [string]$task.State } else { "Missing" }
        live_trading_enabled = $health.live_trading_enabled
        health = $health
        project_root = $ProjectRoot
    }
}

switch ($Action) {
    "Install" {
        if (-not (Test-Path -LiteralPath $EnsureScript -PathType Leaf)) {
            throw "ensure_stack.ps1 not found: $EnsureScript"
        }
        $interval = [Math]::Max(2, [Math]::Min(60, $EnsureIntervalMinutes))
        $codexFlag = if ($EnableCodexSearch) { '$true' } else { '$false' }
        $arguments = @(
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle", "Hidden",
            "-ExecutionPolicy", "Bypass",
            "-File", ('"{0}"' -f $EnsureScript),
            "-EnableCodexSearch:$codexFlag"
        ) -join " "
        $taskAction = New-ScheduledTaskAction `
            -Execute $PowerShell `
            -Argument $arguments `
            -WorkingDirectory $ProjectRoot
        $logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
        $repeatTrigger = New-ScheduledTaskTrigger `
            -Once `
            -At ([DateTime]::Now.AddMinutes(1)) `
            -RepetitionInterval ([TimeSpan]::FromMinutes($interval))
        $settings = New-ScheduledTaskSettingsSet `
            -StartWhenAvailable `
            -MultipleInstances IgnoreNew `
            -ExecutionTimeLimit ([TimeSpan]::FromMinutes(15))
        $principal = New-ScheduledTaskPrincipal `
            -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
            -LogonType Interactive `
            -RunLevel Limited
        if ($PSCmdlet.ShouldProcess($TaskName, "Install review-only control-plane task")) {
            Register-ScheduledTask `
                -TaskName $TaskName `
                -Action $taskAction `
                -Trigger @($logonTrigger, $repeatTrigger) `
                -Settings $settings `
                -Principal $principal `
                -Description "Keeps the local ZK-trading review-only stack healthy; never enables live trading." `
                -Force | Out-Null
        }
        Get-TaskStatus | ConvertTo-Json -Depth 6
    }
    "Uninstall" {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($task -and $PSCmdlet.ShouldProcess($TaskName, "Uninstall control-plane task")) {
            Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        }
        Get-TaskStatus | ConvertTo-Json -Depth 6
    }
    "RunOnce" {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        if ($PSCmdlet.ShouldProcess($TaskName, "Start control-plane health task")) {
            Start-ScheduledTask -InputObject $task
        }
        Get-TaskStatus | ConvertTo-Json -Depth 6
    }
    default {
        Get-TaskStatus | ConvertTo-Json -Depth 6
    }
}
