[CmdletBinding()]
param([switch]$SaveReport)
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $ProjectRoot 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Project Python runtime missing; diagnostics will not install dependencies or start workers.'
}
$DiagnosticScript = Join-Path $ProjectRoot 'backend\scripts\stack_diagnostics.py'
$Arguments = @('-B', '-X', 'utf8', $DiagnosticScript, '--project-root', $ProjectRoot)
if ($SaveReport) {
    $Arguments += @('--output', (Join-Path $ProjectRoot 'logs\stack_diagnostics.json'))
}
& $Python @Arguments
exit $LASTEXITCODE
