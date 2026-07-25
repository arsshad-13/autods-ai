# AutoDS AI Backend - Development Server Launcher
# Always uses the project's own venv, regardless of which Python is active in PATH.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Prefer local venv, fall back to .venv
if (Test-Path "$ScriptDir\venv\Scripts\python.exe") {
    $Python = "$ScriptDir\venv\Scripts\python.exe"
    Write-Host "[autods] Using venv: $Python" -ForegroundColor Cyan
} elseif (Test-Path "$ScriptDir\.venv\Scripts\python.exe") {
    $Python = "$ScriptDir\.venv\Scripts\python.exe"
    Write-Host "[autods] Using .venv: $Python" -ForegroundColor Cyan
} else {
    Write-Host "[autods] WARNING: No local venv found, falling back to system Python" -ForegroundColor Yellow
    $Python = "python"
}

# Verify critical packages before starting
Write-Host "[autods] Verifying dependencies..." -ForegroundColor Cyan
& $Python -c "import openpyxl, pandas, xlrd, fastapi, uvicorn; print('[autods] Dependencies OK')"

# Launch uvicorn
Set-Location $ScriptDir
& $Python -m uvicorn app.main:app --reload
