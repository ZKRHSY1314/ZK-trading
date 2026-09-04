import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = PROJECT_ROOT / "scripts"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell.exe")
WINDOWS_POWERSHELL = shutil.which("powershell.exe")
requires_powershell = pytest.mark.skipif(
    sys.platform != "win32" or not POWERSHELL,
    reason="Windows PowerShell startup integration",
)


def _run_ps(script: str, executable: str | None = None) -> dict:
    encoded = base64.b64encode(
        (
            "$ErrorActionPreference = 'Stop'; "
            "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); "
            + script
        ).encode("utf-16-le")
    ).decode("ascii")
    shell = executable or POWERSHELL
    environment = os.environ.copy()
    if shell.lower().endswith("powershell.exe"):
        # Python launched from pwsh inherits Core module directories. Let 5.1
        # build its native module path, as the Windows scheduled task does.
        environment = {
            key: value for key, value in environment.items() if key.upper() != "PSMODULEPATH"
        }
    result = subprocess.run(
        # -ExecutionPolicy Bypass applies to this child process only and changes
        # no machine state. Without it the suite cannot dot-source the repo's own
        # .ps1 wherever the effective policy is Restricted - the Windows client
        # default, and what every scope reports on a fresh host - so these tests
        # failed for the environment rather than for the script under test.
        [
            shell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip())


def _fixture_script(changes: str = "", *, launch: bool = False) -> str:
    helper = str(SCRIPT_ROOT / "tonghuasun_readonly.ps1").replace("'", "''")
    return (
        f". '{helper}'\n"
        + r"""
$script:FixtureProfile = @{
    SchemaVersion = 1; ProductHome = 'C:\TonghuasunFixture';
    ExecutablePath = 'C:\TonghuasunFixture\bin\happ.exe';
    DailyBarSourcePolicy = 'akshare_first'
}
$script:FixtureConfig = [pscustomobject]@{
    enableTradeTools = $false; enableAutomatedTradeApi = $false;
    listenAddresses = @('127.0.0.1'); localAccessToken = 'SYNTHETIC-SECRET'
}
$script:FixtureEndpoint = [pscustomobject]@{
    baseUrl = 'http://127.0.0.1:17180'; port = 17180;
    listenAddresses = @('127.0.0.1'); lanBaseUrls = @();
    processId = 101; startedAtUtc = '2026-09-03T07:50:21Z'
}
$script:FixtureHosts = @([pscustomobject]@{
    ProcessId = 101; ExecutablePath = 'C:\TonghuasunFixture\bin\happ.exe';
    CreationDate = [datetime]'2026-09-03T07:50:20Z'
})
$script:MissingPath = ''
$script:StartCount = 0
$script:StartFails = $false
$script:ObservedEnvironment = ''
$script:ObservedWindow = ''
function Import-PowerShellDataFile { return $script:FixtureProfile }
function Test-Path {
    param($LiteralPath, $PathType)
    return $LiteralPath -ne $script:MissingPath
}
function Resolve-Path {
    param($LiteralPath)
    return [pscustomobject]@{ Path = $LiteralPath }
}
function Read-TonghuasunStartupJson {
    param($LiteralPath, $Label)
    if ($Label -eq 'Tonghuashun configuration') { return $script:FixtureConfig }
    return $script:FixtureEndpoint
}
function Get-CimInstance { return $script:FixtureHosts }
function Get-Item {
    return [pscustomobject]@{ LastWriteTimeUtc = [datetime]'2026-09-03T07:50:21Z' }
}
function Start-Process {
    param($FilePath, $WorkingDirectory, $WindowStyle, [switch]$PassThru)
    $script:StartCount += 1
    $script:ObservedEnvironment = $env:TONGHUASUN_AGENT_HOME
    $script:ObservedWindow = $WindowStyle
    if ($script:StartFails) { throw 'Synthetic launch failure' }
    return [pscustomobject]@{ Id = 202 }
}
$env:TONGHUASUN_AGENT_HOME = 'C:\PriorFixture'
$context = $null
$errorMessage = $null
"""
        + changes
        + "\ntry { $context = Get-TonghuasunReadOnlyContext; "
        + ("$context = Start-TonghuasunReadOnlyClient -Context $context; " if launch else "")
        + r"""
} catch { $errorMessage = $_.Exception.Message }
[ordered]@{
    context = $context; error = $errorMessage; starts = $script:StartCount;
    observed_environment = $script:ObservedEnvironment;
    observed_window = $script:ObservedWindow;
    restored_environment = $env:TONGHUASUN_AGENT_HOME
} | ConvertTo-Json -Depth 5
"""
    )


@requires_powershell
def test_readonly_profile_accepts_matching_host_without_starting_or_fetching():
    result = _run_ps(_fixture_script(launch=True))
    assert result["error"] is None
    assert result["starts"] == 0
    assert result["context"]["host_status"] == "endpoint_identity_verified"
    assert result["context"]["market_data_verified"] is False
    assert result["context"]["market_data_only"] is True
    assert result["context"]["live_trading_enabled"] is False
    assert result["context"]["daily_bar_source_policy"] == "akshare_first"
    assert "SYNTHETIC-SECRET" not in json.dumps(result)


@requires_powershell
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ("$script:MissingPath = 'C:\\TonghuasunFixture'", "directory is missing"),
        ("$script:FixtureConfig.enableTradeTools = $true", "explicit JSON false"),
        ("$script:FixtureConfig.enableAutomatedTradeApi = $true", "explicit JSON false"),
        ("$script:FixtureConfig.enableTradeTools = 'false'", "explicit JSON false"),
        ("$script:FixtureConfig.enableTradeTools = $null", "explicit JSON false"),
        ("$script:FixtureConfig.listenAddresses = @('0.0.0.0')", "127.0.0.1 listener"),
        ("$script:FixtureEndpoint.baseUrl = 'http://example.com:17180'", "loopback HTTP origin"),
        ("$script:FixtureEndpoint.lanBaseUrls = @('http://192.0.2.1:17180')", "non-loopback"),
        ("$script:FixtureEndpoint.processId = 999", "does not match"),
        ("$script:FixtureEndpoint.startedAtUtc = '2026-09-02T07:50:20Z'", "does not match"),
        ("$script:FixtureHosts[0].ExecutablePath = 'C:\\Other\\happ.exe'", "different or ambiguous"),
        ("$script:MissingPath = 'C:\\TonghuasunFixture\\runtime\\endpoint.json'", "without endpoint evidence"),
        ("$script:FixtureProfile.DailyBarSourcePolicy = 'tonghuasun_first'", "akshare_first"),
    ],
)
def test_unsafe_or_unverified_startup_fails_closed(changes: str, message: str):
    result = _run_ps(_fixture_script(changes, launch=True))
    assert message in result["error"]
    assert result["starts"] == 0
    assert result["restored_environment"] == r"C:\PriorFixture"
    assert "SYNTHETIC-SECRET" not in json.dumps(result)


@requires_powershell
def test_absent_host_check_does_not_launch_or_trust_stale_endpoint():
    result = _run_ps(_fixture_script("$script:FixtureHosts = @()"))
    assert result["error"] is None
    assert result["starts"] == 0
    assert result["context"]["host_status"] == "not_running"
    assert result["context"]["host_process_id"] is None
    assert result["context"]["market_data_verified"] is False


@requires_powershell
@pytest.mark.parametrize("fails", [False, True])
def test_explicit_client_launch_scopes_directory_and_restores_environment(fails: bool):
    changes = "$script:FixtureHosts = @(); "
    if fails:
        changes += "$script:StartFails = $true"
    result = _run_ps(_fixture_script(changes, launch=True))
    assert result["starts"] == 1
    assert result["observed_environment"] == r"C:\TonghuasunFixture"
    assert result["restored_environment"] == r"C:\PriorFixture"
    assert result["observed_window"] == "Normal"
    if fails:
        assert result["error"] == "Synthetic launch failure"
    else:
        assert result["error"] is None
        assert result["context"]["host_status"] == "started_waiting_for_user_login_and_quote_check"
        assert result["context"]["market_data_verified"] is False


@requires_powershell
def test_windows_powershell_51_imports_unicode_profile_and_parses_entrypoints():
    if not WINDOWS_POWERSHELL:
        pytest.skip("Windows PowerShell 5.1 unavailable")
    script_root = str(SCRIPT_ROOT).replace("'", "''")
    result = _run_ps(
        f"$taskScriptRoot = '{script_root}'; "
        + r"""
$profile = Import-PowerShellDataFile -LiteralPath (Join-Path $taskScriptRoot 'tonghuasun_readonly.psd1')
$errors = @()
foreach ($name in @('tonghuasun_readonly.ps1', 'start_tonghuasun_readonly.ps1', 'run_stack.ps1', 'ensure_stack.ps1')) {
    $tokens = $null; $parseErrors = $null
    [Management.Automation.Language.Parser]::ParseFile((Join-Path $taskScriptRoot $name), [ref]$tokens, [ref]$parseErrors) | Out-Null
    $errors += @($parseErrors | ForEach-Object Message)
}
@{ executable = $profile.ExecutablePath; errors = $errors } | ConvertTo-Json
""",
        executable=WINDOWS_POWERSHELL,
    )
    assert result["executable"] == r"D:\同花顺软件\同花顺远航版\bin\happ.exe"
    assert result["errors"] == []


def test_startup_scripts_do_not_mutate_global_plugin_state_or_query_accounts():
    helper = (SCRIPT_ROOT / "tonghuasun_readonly.ps1").read_text(encoding="utf-8")
    launcher = (SCRIPT_ROOT / "start_tonghuasun_readonly.ps1").read_text(encoding="utf-8")
    assert "if (-not $CheckOnly)" in launcher
    for forbidden in (
        "Set-Content",
        "Set-ItemProperty",
        "Stop-Process",
        "Stop-Service",
        "Invoke-RestMethod",
        "Invoke-WebRequest",
        "localAccessToken",
        "configure.mjs",
        "run_stack.ps1",
    ):
        assert forbidden not in helper + launcher
    assert "'Process')" in helper
    assert "'User')" not in helper
    assert "'Machine')" not in helper
