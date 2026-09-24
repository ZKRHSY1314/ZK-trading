# Read-only runtime metadata. Never print process command lines or configuration secrets.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$expectedHost = Join-Path 'D:\同花顺软件\同花顺远航版\bin' 'happ.exe'
$expectedPlugin = Join-Path (Split-Path -Parent $expectedHost) 'PluginSdks\ThsPlugin.Adapters.Hevo.dll'
$expectedHash = '19fbd89528ebe933cee267de34d63171afd47aef230132bd3574a3b81883469b'
$hostProcesses = @(Get-Process -Name happ -ErrorAction SilentlyContinue)
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort 17180 -ErrorAction SilentlyContinue)
$inventory = @(Get-CimInstance Win32_Process)
$problems = @()
$hostInfo = $null
if ($hostProcesses.Count -ne 1) {
    $problems += 'host_process_not_unique'
} else {
    $hostProcess = $hostProcesses[0]
    $modulePaths = @($hostProcess.Modules | Where-Object { $_.ModuleName -eq 'ThsPlugin.Adapters.Hevo.dll' } | ForEach-Object { $_.FileName })
    $hostInfo = @{ pid=$hostProcess.Id; path=$hostProcess.Path; started_utc=$hostProcess.StartTime.ToUniversalTime().ToString('o'); adapter_loaded_paths=$modulePaths }
    if ($hostProcess.Path -ne $expectedHost) { $problems += 'unexpected_host_executable' }
    if ($modulePaths.Count -ne 1 -or $modulePaths[0] -ne $expectedPlugin) { $problems += 'expected_adapter_not_loaded' }
    $adapterHash = (Get-FileHash -LiteralPath $expectedPlugin -Algorithm SHA256).Hash.ToLowerInvariant()
    $hostInfo['adapter_sha256'] = $adapterHash
    if ($adapterHash -ne $expectedHash) { $problems += 'adapter_pin_mismatch' }
}
if ($listeners.Count -ne 1 -or $listeners[0].LocalAddress -ne '127.0.0.1') { $problems += 'listener_not_exact_loopback' }
$queueEvidence = $null
if ($listeners.Count -eq 1 -and $hostProcesses.Count -eq 1) {
    if ($listeners[0].OwningProcess -eq $hostProcess.Id) {
        $queueEvidence = @{kind='direct_host_listener';application_pid=$hostProcess.Id}
    } elseif ($listeners[0].OwningProcess -eq 4) {
        $serviceState = (& netsh http show servicestate view=requestq verbose=yes) -join "`n"
        if ($LASTEXITCODE -ne 0) { throw 'HTTP.sys request queue inventory failed' }
        $blocks = [regex]::Split($serviceState, '(?m)^Request queue name:')
        $matches = @($blocks | Where-Object { $_ -match '(?im)^\s+HTTP://127\.0\.0\.1:17180(?::127\.0\.0\.1)?/\s*$' })
        if ($matches.Count -ne 1) { $problems += 'http_sys_exact_url_queue_not_unique' }
        else {
            $applicationRows = @([regex]::Matches($matches[0], '(?m)^\s+ID:\s*(\d+), image:\s*(.+?)\s*$'))
            if ($applicationRows.Count -ne 1 -or [int]$applicationRows[0].Groups[1].Value -ne $hostProcess.Id -or $applicationRows[0].Groups[2].Value -ne $expectedHost) {
                $problems += 'http_sys_url_not_owned_by_expected_host'
            } else {
                $queueEvidence = @{kind='http_sys_request_queue';listener_pid=4;application_pid=$hostProcess.Id;application_path=$expectedHost;exact_loopback_url_verified=$true}
            }
        }
    } else { $problems += 'listener_owner_not_expected_host_or_http_sys' }
}
$conflicts = @()
foreach ($process in $inventory) {
    # Git diff/status names source paths but is not a market worker. Spawned workers are checked separately.
    if ($process.Name -ieq 'git.exe') { continue }
    $command = [string]$process.CommandLine
    if ($command -match '(uvicorn|control_plane_loop\.py|market_history_refresh_loop\.py|codex_market_pulse\.py|pilot_runner\.py|run_stack\.ps1|ensure_stack\.ps1)') {
        $conflicts += @{name=$process.Name;pid=$process.ProcessId;reason='possible_project_writer_or_market_worker'}
    }

}
if ($conflicts.Count) { $problems += 'concurrent_runtime_requires_review' }
$now = [DateTimeOffset]::UtcNow
$china = $now.ToOffset([TimeSpan]::FromHours(8))
$tod = $china.TimeOfDay
# Remaining pilot policy: fixed completed-history end 2026-09-04; no current-session bars accepted.
@{ checked_utc=$now.ToString('o'); china_time=$china.ToString('o'); passed=($problems.Count -eq 0);
   problems=$problems; host_process=$hostInfo; listeners=@($listeners | Select-Object LocalAddress,LocalPort,OwningProcess);
   request_queue_binding=$queueEvidence; process_inventory_count=$inventory.Count; conflicts=$conflicts; service_actions=0; market_requests=0 } | ConvertTo-Json -Depth 8
