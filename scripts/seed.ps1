$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$uvPath = if (Test-Path '.tools/bin/uv.exe') { (Resolve-Path '.tools/bin/uv.exe').Path } else { 'uv' }
& $uvPath run python -m planner.cli seed-demo
if ($LASTEXITCODE -ne 0) { throw "Demo seed failed with exit code $LASTEXITCODE" }
