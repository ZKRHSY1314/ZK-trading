# Shared, read-only preflight. Dot-sourcing this file does not launch anything.
$script:TonghuasunStartupScriptRoot = $PSScriptRoot

function Read-TonghuasunStartupJson {
    param([string]$LiteralPath, [string]$Label)

    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
        throw "$Label is missing. Configure the reviewed plugin separately; startup never installs it."
    }
    if ((Get-Item -LiteralPath $LiteralPath).Length -gt 65536) {
        throw "$Label is unexpectedly large."
    }
    try {
        return Get-Content -LiteralPath $LiteralPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        # JSON parsing errors can include input text; never echo the secret-bearing file.
        throw "$Label is not readable JSON."
    }
}

function Assert-TonghuasunLoopbackAddresses {
    param([object]$Addresses, [string]$Label)

    if (@($Addresses).Count -ne 1 -or [string]@($Addresses)[0] -cne '127.0.0.1') {
        throw "$Label must contain only the reviewed 127.0.0.1 listener."
    }
}

function Get-TonghuasunReadOnlyContext {
    param([string]$ProfilePath = '')

    if (-not $ProfilePath) {
        $ProfilePath = Join-Path $script:TonghuasunStartupScriptRoot 'tonghuasun_readonly.psd1'
    }

    $profile = Import-PowerShellDataFile -LiteralPath $ProfilePath
    if ($profile.SchemaVersion -ne 1 -or $profile.DailyBarSourcePolicy -cne 'akshare_first') {
        throw 'The Tonghuashun startup profile must use schema 1 and akshare_first.'
    }
    foreach ($key in @('ProductHome', 'ExecutablePath')) {
        $value = [string]$profile[$key]
        if ($value -notmatch '^[A-Za-z]:[\\/]' -or $value -match '[\r\n]') {
            throw "The Tonghuashun profile $key must be an absolute local-drive path."
        }
    }
    if (-not (Test-Path -LiteralPath $profile.ProductHome -PathType Container)) {
        throw 'The configured Tonghuashun product directory is missing; no fallback directory will be used.'
    }
    if (-not (Test-Path -LiteralPath $profile.ExecutablePath -PathType Leaf)) {
        throw 'The configured Tonghuashun Voyager executable is missing.'
    }
    $productDirectory = (Resolve-Path -LiteralPath $profile.ProductHome).Path
    $executable = (Resolve-Path -LiteralPath $profile.ExecutablePath).Path
    if ([IO.Path]::GetFileName($executable) -ine 'happ.exe') {
        throw 'Only the reviewed Voyager happ.exe host is supported.'
    }
    $config = Read-TonghuasunStartupJson `
        -LiteralPath (Join-Path $productDirectory 'config.json') -Label 'Tonghuashun configuration'
    foreach ($flag in @('enableTradeTools', 'enableAutomatedTradeApi')) {
        if ($config.$flag -isnot [bool] -or $config.$flag -ne $false) {
            throw 'Tonghuashun trading flags must both be explicit JSON false; startup will not rewrite them.'
        }
    }
    Assert-TonghuasunLoopbackAddresses -Addresses $config.listenAddresses -Label 'Tonghuashun configuration'

    $context = [ordered]@{
        schema_version = 'tonghuasun_readonly_startup.v1'
        product_home = $productDirectory
        executable_path = $executable
        daily_bar_source_policy = 'akshare_first'
        live_trading_enabled = $false
        market_data_only = $true
        host_status = 'not_running'
        host_process_id = $null
        market_data_verified = $false
    }
    $hosts = @(Get-CimInstance Win32_Process -Filter "Name = 'happ.exe'" -ErrorAction Stop)
    if ($hosts.Count -eq 0) {
        # Stale endpoint files are not proof of a running client.
        return $context
    }
    if ($hosts.Count -ne 1 -or [string]$hosts[0].ExecutablePath -ine $executable) {
        throw 'A different or ambiguous Voyager host is already running. Exit it normally before using the project launcher.'
    }
    $endpointPath = Join-Path $productDirectory 'runtime\endpoint.json'
    if (-not (Test-Path -LiteralPath $endpointPath -PathType Leaf)) {
        throw 'Voyager is running without endpoint evidence in the project directory. Wait for startup, or exit it normally and use the project launcher.'
    }
    $endpoint = Read-TonghuasunStartupJson -LiteralPath $endpointPath -Label 'Tonghuashun runtime endpoint'
    $uri = $null
    if (-not [Uri]::TryCreate([string]$endpoint.baseUrl, [UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -cne 'http' -or $uri.Host -cne '127.0.0.1' -or
        $uri.AbsolutePath -ne '/' -or $uri.Query -or $uri.Fragment -or $uri.UserInfo -or
        $uri.Port -lt 1024 -or $uri.Port -gt 65535 -or $endpoint.port -ne $uri.Port) {
        throw 'Tonghuashun runtime endpoint must be the reviewed numeric loopback HTTP origin.'
    }
    Assert-TonghuasunLoopbackAddresses -Addresses $endpoint.listenAddresses -Label 'Tonghuashun runtime endpoint'
    if (@($endpoint.lanBaseUrls).Count -gt 0) {
        throw 'Tonghuashun runtime advertises non-loopback addresses.'
    }
    try {
        $created = ([DateTimeOffset]$hosts[0].CreationDate).UtcDateTime
        $published = ([DateTimeOffset]$endpoint.startedAtUtc).UtcDateTime
        $ageFromCreation = ($published - $created).TotalSeconds
    }
    catch {
        throw 'Tonghuashun host startup identity cannot be verified.'
    }
    if ($endpoint.processId -ne $hosts[0].ProcessId -or
        $ageFromCreation -lt -2 -or $ageFromCreation -gt 300 -or
        (Get-Item -LiteralPath $endpointPath).LastWriteTimeUtc -lt $created.AddSeconds(-2)) {
        throw 'Tonghuashun endpoint does not match the running host. Exit Voyager normally and use the project launcher.'
    }
    $context.host_status = 'endpoint_identity_verified'
    $context.host_process_id = [int]$hosts[0].ProcessId
    # Identity checks do not authenticate or fetch candles; login and quote readiness remain separate.
    return $context
}

function Start-TonghuasunReadOnlyClient {
    param([System.Collections.IDictionary]$Context)

    if ($Context.host_status -eq 'endpoint_identity_verified') {
        return $Context
    }
    $priorDirectory = [Environment]::GetEnvironmentVariable('TONGHUASUN_AGENT_HOME', 'Process')
    try {
        # A scoped process environment also works with the existing Windows PowerShell 5.1 entrypoints.
        $env:TONGHUASUN_AGENT_HOME = $Context.product_home
        $client = Start-Process -FilePath $Context.executable_path `
            -WorkingDirectory (Split-Path -Parent $Context.executable_path) `
            -WindowStyle Normal -PassThru
        $Context.host_status = 'started_waiting_for_user_login_and_quote_check'
        $Context.host_process_id = $client.Id
        return $Context
    }
    finally {
        [Environment]::SetEnvironmentVariable('TONGHUASUN_AGENT_HOME', $priorDirectory, 'Process')
    }
}
