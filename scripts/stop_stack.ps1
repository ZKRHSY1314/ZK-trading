[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogsRoot = Join-Path $ProjectRoot "logs"
$PidFile = Join-Path $LogsRoot "run_stack.pids.json"

function Get-DescendantProcessIds {
    param([int[]]$RootProcessIds)

    $rows = @(Get-CimInstance Win32_Process)
    $byParent = @{}
    foreach ($row in $rows) {
        $parentId = [int]$row.ParentProcessId
        if (-not $byParent.ContainsKey($parentId)) {
            $byParent[$parentId] = [System.Collections.Generic.List[int]]::new()
        }
        $byParent[$parentId].Add([int]$row.ProcessId)
    }
    $descendants = [System.Collections.Generic.List[int]]::new()
    $queue = [System.Collections.Generic.Queue[int]]::new()
    foreach ($rootPid in $RootProcessIds) {
        $queue.Enqueue($rootPid)
    }
    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()
        if (-not $byParent.ContainsKey($current)) {
            continue
        }
        foreach ($childPid in $byParent[$current]) {
            if (-not $descendants.Contains($childPid)) {
                $descendants.Add($childPid)
                $queue.Enqueue($childPid)
            }
        }
    }
    return @($descendants)
}

if (-not (Test-Path -LiteralPath $PidFile -PathType Leaf)) {
    throw "Stack PID file not found: $PidFile"
}

$metadata = Get-Content -Raw -Encoding UTF8 -LiteralPath $PidFile | ConvertFrom-Json
if ([IO.Path]::GetFullPath([string]$metadata.project_root) -ne $ProjectRoot) {
    throw "PID metadata belongs to a different project root. Refusing to stop processes."
}

$components = @(
    @{ name = "backend"; data = $metadata.backend },
    @{ name = "frontend"; data = $metadata.frontend },
    @{ name = "control_worker"; data = $metadata.control_worker },
    @{ name = "codex_market_pulse"; data = $metadata.codex_market_pulse }
) | Where-Object { $null -ne $_.data.pid }
$rootPids = @($components | ForEach-Object { [int]$_.data.pid } | Select-Object -Unique)

$rows = @(Get-CimInstance Win32_Process)
$byParent = @{}
foreach ($row in $rows) {
    $parentId = [int]$row.ParentProcessId
    if (-not $byParent.ContainsKey($parentId)) {
        $byParent[$parentId] = [System.Collections.Generic.List[int]]::new()
    }
    $byParent[$parentId].Add([int]$row.ProcessId)
}

$targets = [System.Collections.Generic.List[int]]::new()
$validatedRoots = [System.Collections.Generic.List[int]]::new()
$skipped = [System.Collections.Generic.List[object]]::new()
$missing = [System.Collections.Generic.List[object]]::new()
foreach ($component in $components) {
    $rootPid = [int]$component.data.pid
    $rootRow = $rows | Where-Object { [int]$_.ProcessId -eq $rootPid } | Select-Object -First 1
    if ($null -eq $rootRow) {
        $missing.Add(@{ component = $component.name; pid = $rootPid; reason = "tracked_root_missing" })
        continue
    }
    if (
        -not $component.data.created_at -or
        -not $component.data.executable_path -or
        -not $component.data.command_line -or
        -not $component.data.command_marker
    ) {
        $skipped.Add(@{ component = $component.name; pid = $rootPid; reason = "identity_metadata_missing" })
        continue
    }
    $actualCreatedAt = ([DateTime]$rootRow.CreationDate).ToUniversalTime()
    $expectedCreatedAt = [DateTimeOffset]::Parse([string]$component.data.created_at).UtcDateTime
    $actualExecutable = [IO.Path]::GetFullPath([string]$rootRow.ExecutablePath)
    $expectedExecutable = [IO.Path]::GetFullPath([string]$component.data.executable_path)
    $actualCommandLine = [string]$rootRow.CommandLine
    $expectedCommandLine = [string]$component.data.command_line
    $commandMarker = [string]$component.data.command_marker
    if ([Math]::Abs(($actualCreatedAt - $expectedCreatedAt).TotalSeconds) -gt 5) {
        $skipped.Add(@{ component = $component.name; pid = $rootPid; reason = "creation_time_mismatch" })
        continue
    }
    if (-not $actualExecutable.Equals($expectedExecutable, [StringComparison]::OrdinalIgnoreCase)) {
        $skipped.Add(@{ component = $component.name; pid = $rootPid; reason = "executable_path_mismatch" })
        continue
    }
    if ($actualCommandLine -ne $expectedCommandLine -or -not $actualCommandLine.Contains($commandMarker)) {
        $skipped.Add(@{ component = $component.name; pid = $rootPid; reason = "command_line_mismatch" })
        continue
    }
    $validatedRoots.Add($rootPid)
    $queue = [System.Collections.Generic.Queue[int]]::new()
    $queue.Enqueue($rootPid)
    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()
        if (-not $targets.Contains($current)) {
            $targets.Add($current)
        }
        if ($byParent.ContainsKey($current)) {
            foreach ($childPid in $byParent[$current]) {
                $queue.Enqueue($childPid)
            }
        }
    }
}

$stopped = [System.Collections.Generic.List[int]]::new()
foreach ($rootPid in $validatedRoots) {
    if (Get-Process -Id $rootPid -ErrorAction SilentlyContinue) {
        Stop-Process -Id $rootPid -Force -ErrorAction SilentlyContinue
        $stopped.Add($rootPid)
    }
}
for ($index = $targets.Count - 1; $index -ge 0; $index--) {
    $targetPid = $targets[$index]
    if ($validatedRoots.Contains($targetPid)) {
        continue
    }
    if (Get-Process -Id $targetPid -ErrorAction SilentlyContinue) {
        Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
        $stopped.Add($targetPid)
    }
}

$sweepDeadline = [DateTime]::UtcNow.AddSeconds(3)
do {
    $lateDescendants = @(Get-DescendantProcessIds -RootProcessIds @($validatedRoots))
    foreach ($targetPid in $lateDescendants) {
        if (Get-Process -Id $targetPid -ErrorAction SilentlyContinue) {
            Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
            if (-not $stopped.Contains($targetPid)) {
                $stopped.Add($targetPid)
            }
        }
    }
    if ($lateDescendants.Count -eq 0 -or [DateTime]::UtcNow -ge $sweepDeadline) {
        break
    }
    Start-Sleep -Milliseconds 100
} while ($true)

$shutdownDeadline = [DateTime]::UtcNow.AddSeconds(3)
do {
    $remaining = @(
        foreach ($rootPid in $validatedRoots) {
            Get-Process -Id $rootPid -ErrorAction SilentlyContinue
        }
    )
    if ($remaining.Count -eq 0 -or [DateTime]::UtcNow -ge $shutdownDeadline) {
        break
    }
    Start-Sleep -Milliseconds 100
} while ($true)
$remainingDescendants = @(Get-DescendantProcessIds -RootProcessIds @($validatedRoots))
$remaining = @(
    @($remaining) + @(
        foreach ($descendantPid in $remainingDescendants) {
            Get-Process -Id $descendantPid -ErrorAction SilentlyContinue
        }
    ) | Sort-Object Id -Unique
)
if ($remaining.Count -eq 0) {
    $resolvedLogs = (Resolve-Path -LiteralPath $LogsRoot).Path
    if ($resolvedLogs -ne [IO.Path]::GetDirectoryName($PidFile)) {
        throw "PID file escaped the expected logs directory."
    }
    Remove-Item -LiteralPath $PidFile -Force
}

$result = [ordered]@{
    status = if ($remaining.Count -ne 0) {
        "attention"
    } elseif ($skipped.Count -gt 0 -or $missing.Count -gt 0) {
        "stale_metadata_removed"
    } else {
        "stopped"
    }
    project_root = $ProjectRoot
    stopped_pids = @($stopped)
    remaining_pids = @($remaining | ForEach-Object Id)
    remaining_descendant_pids = @($remainingDescendants)
    skipped = @($skipped)
    missing = @($missing)
}
$result | ConvertTo-Json -Depth 4
if ($result.status -eq "attention") {
    exit 1
}
