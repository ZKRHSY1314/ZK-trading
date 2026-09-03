[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet("Install", "Uninstall", "Status", "RunOnce")]
    [string]$Action = "Status",
    [string]$TaskName = "ZKTrading-ReviewOnly-ControlPlane",
    [int]$EnsureIntervalMinutes = 5,
    [ValidateSet(0, 1)]
    [int]$EnableCodexSearch = 1
)

$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "The persistent control-plane task is supported only on Windows."
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EnsureScript = Join-Path $PSScriptRoot "ensure_stack.ps1"
$PowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
$CurrentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$CurrentUser = $CurrentIdentity.Name
$CurrentUserSid = $CurrentIdentity.User.Value
$ExpectedIntervalMinutes = [Math]::Max(2, [Math]::Min(60, $EnsureIntervalMinutes))
$BaseArguments = @(
    "-NoProfile",
    "-NonInteractive",
    "-WindowStyle", "Hidden",
    "-ExecutionPolicy", "Bypass",
    "-File", ('"{0}"' -f $EnsureScript)
)
$CodexFlag = [string]$EnableCodexSearch
$ExpectedArguments = ($BaseArguments + @("-EnableCodexSearch", $CodexFlag)) -join " "
$AllowedArguments = @(
    (($BaseArguments + @("-EnableCodexSearch", "1")) -join " "),
    (($BaseArguments + @("-EnableCodexSearch", "0")) -join " ")
)
$LegacyArguments = @(
    (($BaseArguments + @('-EnableCodexSearch:$true')) -join " "),
    (($BaseArguments + @('-EnableCodexSearch:$false')) -join " ")
)
$ExpectedDescription = "Keeps the local ZK-trading review-only stack healthy; never enables live trading."

function Test-PrincipalMatchesCurrentUser {
    param([string]$UserId)

    if ([string]::IsNullOrWhiteSpace($UserId)) {
        return $false
    }
    if ($UserId.Equals($CurrentUser, [StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    try {
        $principalSid = if ($UserId -match '^S-\d-') {
            [System.Security.Principal.SecurityIdentifier]::new($UserId)
        }
        else {
            ([System.Security.Principal.NTAccount]::new($UserId)).Translate(
                [System.Security.Principal.SecurityIdentifier]
            )
        }
        return $principalSid.Value -eq $CurrentUserSid
    }
    catch {
        return $false
    }
}

function Test-TaskDefinition {
    param([object]$Task)

    if ($null -eq $Task) {
        return [ordered]@{
            valid = $false
            migratable = $false
            reason = "task_missing"
            checks = [ordered]@{}
        }
    }
    $actions = @($Task.Actions)
    $action = if ($actions.Count -eq 1) { $actions[0] } else { $null }
    $triggers = @($Task.Triggers)
    $logonTriggers = @($triggers | Where-Object { $_.CimClass.CimClassName -eq "MSFT_TaskLogonTrigger" })
    $repeatTriggers = @($triggers | Where-Object { $_.CimClass.CimClassName -eq "MSFT_TaskTimeTrigger" })
    $logonTrigger = if ($logonTriggers.Count -eq 1) { $logonTriggers[0] } else { $null }
    $repeatTrigger = if ($repeatTriggers.Count -eq 1) { $repeatTriggers[0] } else { $null }
    $safeRepeatInterval = $false
    $repeatIntervalMatchesRequested = $false
    $safeStartBoundary = $false
    if ($repeatTrigger -and $repeatTrigger.Repetition.Interval) {
        try {
            $repeatMinutes = [Xml.XmlConvert]::ToTimeSpan(
                [string]$repeatTrigger.Repetition.Interval
            ).TotalMinutes
            $safeRepeatInterval = $repeatMinutes -ge 2 -and $repeatMinutes -le 60
            $repeatIntervalMatchesRequested = (
                [Math]::Abs($repeatMinutes - $ExpectedIntervalMinutes) -lt 0.01
            )
            $startBoundary = [DateTimeOffset]::Parse([string]$repeatTrigger.StartBoundary)
            $safeStartBoundary = ($startBoundary - [DateTimeOffset]::Now).TotalMinutes -le 5
        }
        catch {
            $safeRepeatInterval = $false
            $repeatIntervalMatchesRequested = $false
            $safeStartBoundary = $false
        }
    }
    $indefiniteRepeat = $null -ne $repeatTrigger -and (
        [string]::IsNullOrWhiteSpace([string]$repeatTrigger.EndBoundary)
    ) -and (
        [string]::IsNullOrWhiteSpace([string]$repeatTrigger.Repetition.Duration)
    )
    $noRandomDelay = $triggers.Count -eq 2 -and @(
        $triggers | Where-Object {
            -not [string]::IsNullOrWhiteSpace([string]$_.RandomDelay)
        }
    ).Count -eq 0
    $legacyArguments = $null -ne $action -and [string]$action.Arguments -in $LegacyArguments
    $knownArguments = $null -ne $action -and (
        [string]$action.Arguments -in ($AllowedArguments + $LegacyArguments)
    )
    $checks = [ordered]@{
        single_action = $actions.Count -eq 1
        executable = $null -ne $action -and (
            [IO.Path]::GetFullPath([string]$action.Execute)
        ).Equals([IO.Path]::GetFullPath($PowerShell), [StringComparison]::OrdinalIgnoreCase)
        arguments_safe = $null -ne $action -and [string]$action.Arguments -in $AllowedArguments
        arguments_match_requested = $null -ne $action -and (
            [string]$action.Arguments -eq $ExpectedArguments
        )
        working_directory = $null -ne $action -and (
            [IO.Path]::GetFullPath([string]$action.WorkingDirectory)
        ).Equals([IO.Path]::GetFullPath($ProjectRoot), [StringComparison]::OrdinalIgnoreCase)
        principal = Test-PrincipalMatchesCurrentUser -UserId ([string]$Task.Principal.UserId)
        logon_type = [string]$Task.Principal.LogonType -eq "Interactive"
        run_level = [string]$Task.Principal.RunLevel -eq "Limited"
        description = [string]$Task.Description -eq $ExpectedDescription
        trigger_shape = $triggers.Count -eq 2 -and $logonTriggers.Count -eq 1 -and $repeatTriggers.Count -eq 1
        triggers_enabled = $triggers.Count -eq 2 -and @(
            $triggers | Where-Object { $_.Enabled -ne $true }
        ).Count -eq 0
        logon_user = $null -ne $logonTrigger -and (
            Test-PrincipalMatchesCurrentUser -UserId ([string]$logonTrigger.UserId)
        )
        repeat_interval_safe = $safeRepeatInterval
        repeat_interval_matches_requested = $repeatIntervalMatchesRequested
        start_boundary_active = $safeStartBoundary
        indefinite_repeat = $indefiniteRepeat
        no_random_delay = $noRandomDelay
        task_enabled = $Task.Settings.Enabled -eq $true
        not_idle_only = $Task.Settings.RunOnlyIfIdle -eq $false
        allow_demand_start = $Task.Settings.AllowDemandStart -eq $true
        allow_hard_terminate = $Task.Settings.AllowHardTerminate -eq $true
        network_not_required = $Task.Settings.RunOnlyIfNetworkAvailable -eq $false
        multiple_instances = [string]$Task.Settings.MultipleInstances -eq "IgnoreNew"
        execution_time_limit = [string]$Task.Settings.ExecutionTimeLimit -eq "PT15M"
        start_when_available = $Task.Settings.StartWhenAvailable -eq $true
        allow_start_on_batteries = $Task.Settings.DisallowStartIfOnBatteries -eq $false
        continue_on_batteries = $Task.Settings.StopIfGoingOnBatteries -eq $false
    }
    $valid = -not ($checks.Values -contains $false)
    $migrationChecks = @(
        "single_action", "executable", "working_directory", "principal", "run_level", "description"
    )
    $migratable = -not $valid -and $knownArguments
    foreach ($name in $migrationChecks) {
        if (-not $checks[$name]) {
            $migratable = $false
        }
    }
    return [ordered]@{
        valid = $valid
        migratable = $migratable
        reason = if ($valid) {
            $null
        }
        elseif ($migratable) {
            if ($legacyArguments) { "legacy_boolean_arguments" } else { "task_definition_upgrade" }
        }
        else {
            "task_definition_mismatch"
        }
        checks = $checks
    }
}

function Get-TaskStatus {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    $definition = Test-TaskDefinition -Task $task
    $taskInfo = if ($task) {
        Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
    }
    else {
        $null
    }
    $configurationMatches = [bool](
        $definition.checks.arguments_match_requested -and
        $definition.checks.repeat_interval_matches_requested
    )
    $neverRun = $null -ne $taskInfo -and (
        [int64]$taskInfo.LastTaskResult -eq 267011 -or
        $taskInfo.LastRunTime.Year -lt 2000
    )
    $taskRunning = $null -ne $task -and [string]$task.State -eq "Running"
    $lastRunOk = if ($null -eq $taskInfo -or $neverRun) {
        $null
    }
    else {
        [int64]$taskInfo.LastTaskResult -eq 0 -or (
            $taskRunning -and [int64]$taskInfo.LastTaskResult -eq 267009
        )
    }
    $lastRunRecent = if ($null -eq $taskInfo -or $neverRun) {
        $null
    }
    else {
        $taskInfo.LastRunTime -ge [DateTime]::Now.AddMinutes(
            -[Math]::Max(15, $ExpectedIntervalMinutes * 3)
        )
    }
    $nextRunScheduled = $null -ne $taskInfo -and (
        $taskInfo.NextRunTime -ge [DateTime]::Now.AddMinutes(-1) -and
        $taskInfo.NextRunTime -le [DateTime]::Now.AddMinutes($ExpectedIntervalMinutes + 5)
    )
    $taskStateRunnable = $null -ne $task -and [string]$task.State -in @("Ready", "Running")
    $operationalStatus = if ($null -eq $task) {
        "missing"
    }
    elseif ($null -eq $taskInfo) {
        "task_info_unavailable"
    }
    elseif (-not $definition.valid) {
        "definition_invalid"
    }
    elseif ($neverRun) {
        "awaiting_first_run"
    }
    elseif (-not $lastRunOk) {
        "last_run_failed"
    }
    elseif (-not $lastRunRecent) {
        "last_run_stale"
    }
    elseif (-not $nextRunScheduled) {
        "next_run_invalid"
    }
    elseif (-not $taskStateRunnable) {
        "task_state_invalid"
    }
    else {
        "healthy"
    }
    $operationalOk = $operationalStatus -eq "healthy"
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
        definition_migratable = $definition.migratable
        configuration_matches = $configurationMatches
        definition = $definition
        task_state = if ($task) { [string]$task.State } else { "Missing" }
        operational_ok = $operationalOk
        operational_status = $operationalStatus
        operational_checks = [ordered]@{
            last_run_ok = $lastRunOk
            last_run_recent = $lastRunRecent
            next_run_scheduled = $nextRunScheduled
            task_state_runnable = $taskStateRunnable
        }
        last_task_result = if ($taskInfo) { [int64]$taskInfo.LastTaskResult } else { $null }
        last_run_time = if ($taskInfo) { $taskInfo.LastRunTime.ToString("o") } else { $null }
        next_run_time = if ($taskInfo) { $taskInfo.NextRunTime.ToString("o") } else { $null }
        missed_runs = if ($taskInfo) { [int64]$taskInfo.NumberOfMissedRuns } else { $null }
        requested_configuration = [ordered]@{
            enable_codex_search = [bool]$EnableCodexSearch
            ensure_interval_minutes = $ExpectedIntervalMinutes
        }
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
            if (-not $existingDefinition.valid -and -not $existingDefinition.migratable) {
                throw "Refusing to overwrite mismatched scheduled task '$TaskName'."
            }
        }
        $taskAction = New-ScheduledTaskAction `
            -Execute $PowerShell `
            -Argument $ExpectedArguments `
            -WorkingDirectory $ProjectRoot
        $logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
        $repeatTrigger = New-ScheduledTaskTrigger `
            -Once `
            -At ([DateTime]::Now.AddMinutes(1)) `
            -RepetitionInterval ([TimeSpan]::FromMinutes($ExpectedIntervalMinutes))
        $settings = New-ScheduledTaskSettingsSet `
            -StartWhenAvailable `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -RunOnlyIfIdle:$false `
            -DisallowDemandStart:$false `
            -DisallowHardTerminate:$false `
            -RunOnlyIfNetworkAvailable:$false `
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
        if ($task) {
            $definition = Test-TaskDefinition -Task $task
            if (-not $definition.valid -and -not $definition.migratable) {
                throw "Refusing to remove mismatched scheduled task '$TaskName'."
            }
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
