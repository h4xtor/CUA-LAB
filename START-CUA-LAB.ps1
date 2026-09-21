[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (Test-Path '.\dist\CUA-LAB\CUA-LAB.exe') { & '.\dist\CUA-LAB\CUA-LAB.exe'; exit $LASTEXITCODE }
if (-not (Test-Path '.\.venv\Scripts\python.exe')) { throw 'Run .\INSTALL-CUA-LAB.ps1 first, or download the packaged Windows bundle.' }
& .\.venv\Scripts\python.exe main.py
exit $LASTEXITCODE
