param([switch]$Browser)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$uvPath = if (Test-Path '.tools/bin/uv.exe') { (Resolve-Path '.tools/bin/uv.exe').Path } else { 'uv' }
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
Invoke-Checked $uvPath @('run','ruff','check','services','tests','db')
Invoke-Checked $uvPath @('run','pytest','-q')
Invoke-Checked 'npm.cmd' @('run','typecheck')
Invoke-Checked 'npm.cmd' @('test')
Invoke-Checked 'npm.cmd' @('run','build')
if ($Browser) {
    Invoke-Checked $uvPath @('run','alembic','upgrade','head')
    Invoke-Checked 'npm.cmd' @('run','test:e2e')
}
