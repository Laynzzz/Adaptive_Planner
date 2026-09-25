param([ValidateSet('setup','api','web','worker','stop')] [string]$Action = 'setup')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$uvPath = if (Test-Path '.tools/bin/uv.exe') { (Resolve-Path '.tools/bin/uv.exe').Path } else { 'uv' }
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
switch ($Action) {
    'setup' {
        Invoke-Checked $uvPath @('sync','--frozen','--all-extras')
        Invoke-Checked 'npm.cmd' @('ci')
        Invoke-Checked 'docker' @('compose','up','-d','--wait','postgres','oidc')
        Invoke-Checked $uvPath @('run','alembic','upgrade','head')
        Write-Output 'Setup complete. In separate terminals: ./scripts/dev.ps1 api, ./scripts/dev.ps1 worker, ./scripts/dev.ps1 web'
    }
    'api' { Invoke-Checked $uvPath @('run','python','-m','planner.cli','serve') }
    'web' { Invoke-Checked 'npm.cmd' @('run','dev') }
    'worker' { Invoke-Checked $uvPath @('run','python','-m','planner.jobs.worker') }
    'stop' { Invoke-Checked 'docker' @('compose','stop') }
}
