[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($env:OS -ne 'Windows_NT') { throw 'CUA LAB requires Windows 10/11 x64.' }
& py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 x64 for source development, then rerun.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
$Driver = Get-Command cua-driver -ErrorAction SilentlyContinue
if (-not $Driver -and -not $env:CUA_DRIVER_PATH) { Write-Warning 'Cua Driver missing. Install from https://cua.ai/docs/how-to-guides/driver/install or set CUA_DRIVER_PATH.' }
if ($Driver) { & $Driver.Source --version; & $Driver.Source doctor }
if ([string]::IsNullOrWhiteSpace($env:OPENROUTER_API_KEY)) { Write-Warning 'OPENROUTER_API_KEY is missing. Set it in your Windows user environment and reopen CUA LAB.' }
& .\.venv\Scripts\python.exe main.py --smoke-test
if ($LASTEXITCODE -ne 0) { throw 'CUA LAB initialization failed. Close an existing instance if port 8768 is occupied.' }
Write-Host 'Setup complete. Run .\START-CUA-LAB.ps1. Use Health check in the GUI before tasks.'
