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
$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$CodexFlag = if ($EnableCodexSearch) { '$true' } else { '$false' }
$ExpectedArguments = @(
    "-NoProfile",
    "-NonInteractive",
    "-WindowStyle", "Hidden",
    "-ExecutionPolicy", "Bypass",
    "-File", ('"{0}"' -f $EnsureScript),
    "-EnableCodexSearch:$CodexFlag"
) -join " "
$ExpectedDescription = "Keeps the local ZK-trading review-only stack healthy; never enables live trading."

function Test-TaskDefinition {
    param([object]$Task)

    if ($null -eq $Task) {
        return [ordered]@{ valid = $false; reason = "task_missing" }
    }
    $actions = @($Task.Actions)
    $action = if ($actions.Count -eq 1) { $actions[0] } else { $null }
    $checks = [ordered]@{
        single_action = $actions.Count -eq 1
        executable = $null -ne $action -and (
            [IO.Path]::GetFullPath([string]$action.Execute)
        ).Equals([IO.Path]::GetFullPath($PowerShell), [StringComparison]::OrdinalIgnoreCase)
        arguments = $null -ne $action -and [string]$action.Arguments -eq $ExpectedArguments
        working_directory = $null -ne $action -and (
            [IO.Path]::GetFullPath([string]$action.WorkingDirectory)
        ).Equals([IO.Path]::GetFullPath($ProjectRoot), [StringComparison]::OrdinalIgnoreCase)
        principal = [string]$Task.Principal.UserId -eq $CurrentUser
        run_level = [string]$Task.Principal.RunLevel -eq "Limited"
        description = [string]$Task.Description -eq $ExpectedDescription
    }
    return [ordered]@{
        valid = -not ($checks.Values -contains $false)
        reason = if ($checks.Values -contains $false) { "task_definition_mismatch" } else { $null }
        checks = $checks
    }
}

function Get-TaskStatus {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    $definition = Test-TaskDefinition -Task $task
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
        definition_valid = $definition.valid
        definition = $definition
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
        $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($existingTask) {
            $existingDefinition = Test-TaskDefinition -Task $existingTask
            if (-not $existingDefinition.valid) {
                throw "Refusing to overwrite mismatched scheduled task '$TaskName'."
            }
        }
        $interval = [Math]::Max(2, [Math]::Min(60, $EnsureIntervalMinutes))
        $taskAction = New-ScheduledTaskAction `
            -Execute $PowerShell `
            -Argument $ExpectedArguments `
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
            -UserId $CurrentUser `
            -LogonType Interactive `
            -RunLevel Limited
        if ($PSCmdlet.ShouldProcess($TaskName, "Install review-only control-plane task")) {
            Register-ScheduledTask `
                -TaskName $TaskName `
                -Action $taskAction `
                -Trigger @($logonTrigger, $repeatTrigger) `
                -Settings $settings `
                -Principal $principal `
                -Description $ExpectedDescription `
                -Force | Out-Null
        }
        Get-TaskStatus | ConvertTo-Json -Depth 6
    }
    "Uninstall" {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($task -and -not (Test-TaskDefinition -Task $task).valid) {
            throw "Refusing to remove mismatched scheduled task '$TaskName'."
        }
        if ($task -and $PSCmdlet.ShouldProcess($TaskName, "Uninstall control-plane task")) {
            Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        }
        Get-TaskStatus | ConvertTo-Json -Depth 6
    }
    "RunOnce" {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        if (-not (Test-TaskDefinition -Task $task).valid) {
            throw "Refusing to run mismatched scheduled task '$TaskName'."
        }
        if ($PSCmdlet.ShouldProcess($TaskName, "Start control-plane health task")) {
            Start-ScheduledTask -InputObject $task
        }
        Get-TaskStatus | ConvertTo-Json -Depth 6
    }
    default {
        Get-TaskStatus | ConvertTo-Json -Depth 6
    }
}
