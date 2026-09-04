[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [string]$ProfilePath = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'tonghuasun_readonly.ps1')
$context = Get-TonghuasunReadOnlyContext -ProfilePath $ProfilePath
if (-not $CheckOnly) {
    $context = Start-TonghuasunReadOnlyClient -Context $context
}
$context | ConvertTo-Json -Depth 3
