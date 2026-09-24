[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($env:OS -ne 'Windows_NT') { throw 'Windows x64 is required to build CUA LAB.' }
$Python = Get-Command py -ErrorAction SilentlyContinue
if (-not $Python) { throw 'Install Python 3.12 x64 with the Python launcher for development/building.' }
& py -3.12 -m venv --clear .venv-build
if ($LASTEXITCODE -ne 0) { throw 'Failed to create Python 3.12 build environment.' }
$BuildPython = Join-Path $PSScriptRoot '.venv-build\Scripts\python.exe'
& $BuildPython -m pip install --disable-pip-version-check -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build dependencies failed.' }
& $BuildPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Installed dependency constraints are inconsistent.' }
& $BuildPython -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; packaging aborted.' }
& $BuildPython -m PyInstaller --noconfirm --clean --onedir --windowed --name CUA-LAB --add-data 'cua_lab/static;cua_lab/static' --add-data 'cua_knowledge;cua_knowledge' --collect-all webview --collect-all llama_cpp --hidden-import uvicorn.logging --hidden-import uvicorn.loops.asyncio --hidden-import uvicorn.protocols.http.h11_impl --hidden-import uvicorn.protocols.websockets.websockets_impl --hidden-import uvicorn.lifespan.on main.py
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
$SmokeData = Join-Path ([System.IO.Path]::GetTempPath()) ('cua-lab-build-smoke-' + [guid]::NewGuid())
$PreviousData = $env:CUA_LAB_DATA_DIR
try {
    $env:CUA_LAB_DATA_DIR = $SmokeData
    $Process = Start-Process -FilePath '.\dist\CUA-LAB\CUA-LAB.exe' -ArgumentList '--smoke-test' -WindowStyle Hidden -PassThru
    if (-not $Process.WaitForExit(45000)) { $Process.Kill(); throw 'Packaged startup smoke test timed out.' }
    if ($Process.ExitCode -ne 0) { throw "Packaged startup smoke test failed. Diagnostics: $SmokeData\logs\startup.log" }
    $SmokeReport = Join-Path $SmokeData 'smoke-test.json'
    if (-not (Test-Path -LiteralPath $SmokeReport)) { throw 'Packaged startup smoke test produced no success report.' }
    if ((Get-Content -LiteralPath $SmokeReport -Raw | ConvertFrom-Json).status -ne 'passed') { throw 'Packaged startup smoke report did not pass.' }
} finally { $env:CUA_LAB_DATA_DIR = $PreviousData }
Compress-Archive -Path '.\dist\CUA-LAB' -DestinationPath '.\dist\CUA-LAB-windows-x64.zip' -Force
Write-Host 'Built dist\CUA-LAB\CUA-LAB.exe and dist\CUA-LAB-windows-x64.zip'
Write-Host 'Desktop acceptance tests are still required in an interactive Windows session.'
