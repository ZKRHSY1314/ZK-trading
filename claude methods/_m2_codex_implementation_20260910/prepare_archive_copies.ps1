# New-phase byte copies for unchanged M1 read-only validation; never SQLite-open production.
$ErrorActionPreference = 'Stop'
$phaseDirectory = [System.IO.Path]::GetFullPath($PSScriptRoot)
$workspaceDirectory = [System.IO.Path]::GetFullPath((Join-Path $phaseDirectory '..\..'))
$copyDirectory = [System.IO.Path]::GetFullPath((Join-Path $phaseDirectory 'archive_copies'))
if (-not $copyDirectory.StartsWith($phaseDirectory + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'copy_target_outside_phase' }
if (Test-Path -LiteralPath $copyDirectory) { throw 'archive_copy_claim_already_exists' }
$previous = Get-Content -LiteralPath (Join-Path $phaseDirectory 'baseline\production_files_before.json') -Raw | ConvertFrom-Json -AsHashtable
$sources = @()
foreach ($database in @('trading_local.sqlite3','market_history.sqlite3')) {
    foreach ($suffix in @('','-wal','-shm','-journal')) {
        $sourcePath = [System.IO.Path]::GetFullPath((Join-Path $workspaceDirectory ($database+$suffix)))
        if (-not $sourcePath.StartsWith($workspaceDirectory+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'source_outside_workspace' }
        $sources += $sourcePath
    }
}
$leases = @{}
$records = [ordered]@{}
$hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
try {
    # Acquire every existing source first. FileShare.Read denies concurrent write/delete opens.
    foreach ($sourcePath in $sources) {
        if (Test-Path -LiteralPath $sourcePath) {
            $lease = [System.IO.FileStream]::new($sourcePath,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::Read)
            $leases[$sourcePath] = $lease
            if (($sourcePath.EndsWith('-wal') -or $sourcePath.EndsWith('-journal')) -and $lease.Length -ne 0) { throw 'nonempty_transaction_sidecar_requires_review' }
        } elseif ($previous.files[$sourcePath].exists -ne $false) { throw 'production_file_disappeared' }
    }
    foreach ($sourcePath in $sources) {
        if (-not $leases.ContainsKey($sourcePath)) { $records[$sourcePath]=@{exists=$false}; continue }
        $lease=$leases[$sourcePath]
        $lease.Position=0
        $digest=[Convert]::ToHexString($hashAlgorithm.ComputeHash($lease)).ToLowerInvariant()
        if ($digest -ne $previous.files[$sourcePath].sha256) { throw 'production_changed_since_phase_baseline' }
        $records[$sourcePath]=@{exists=$true;length=$lease.Length;source_sha256_before=$digest}
    }
    [System.IO.Directory]::CreateDirectory($copyDirectory) | Out-Null
    foreach ($sourcePath in $sources) {
        if (-not $leases.ContainsKey($sourcePath)) { continue }
        $destination=[System.IO.Path]::GetFullPath((Join-Path $copyDirectory ([System.IO.Path]::GetFileName($sourcePath))))
        if (-not $destination.StartsWith($copyDirectory+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'destination_outside_allowlist' }
        $lease=$leases[$sourcePath];$lease.Position=0
        $writer=[System.IO.FileStream]::new($destination,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
        try { $lease.CopyTo($writer);$writer.Flush($true) } finally { $writer.Dispose() }
        $copyDigest=(Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        $lease.Position=0
        $afterDigest=[Convert]::ToHexString($hashAlgorithm.ComputeHash($lease)).ToLowerInvariant()
        if ($copyDigest -ne $records[$sourcePath].source_sha256_before -or $afterDigest -ne $copyDigest) { throw 'source_copy_byte_mismatch' }
        $records[$sourcePath].destination=$destination
        $records[$sourcePath].copy_sha256_before_sqlite=$copyDigest
        $records[$sourcePath].source_sha256_after=$afterDigest
    }
    $receipt=@{created_at_utc=[DateTimeOffset]::UtcNow.ToString('o');kind='new_phase_copy_baseline_not_historical_baseline';
        source_sqlite_connections=0;source_checkpoint_operations=0;source_locks='FileAccess.Read FileShare.Read held simultaneously';
        files=$records;all_existing_copies_byte_equal=$true}
    $json=$receipt|ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText((Join-Path $copyDirectory 'copy_receipt.json'),$json,[System.Text.UTF8Encoding]::new($false))
    @{archive_copies_created=$true;existing_files_copied=$leases.Count;all_byte_equal=$true;production_sqlite_connections=0}|ConvertTo-Json
} finally {
    foreach ($lease in $leases.Values) { $lease.Dispose() }
    $hashAlgorithm.Dispose()
}
