$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found. Install it from https://docs.astral.sh/uv/ and reopen PowerShell."
}

Write-Host "BottleNeck | preparing Python 3.12 environment..." -ForegroundColor Cyan
uv sync --python 3.12
if ($LASTEXITCODE -ne 0) { throw "uv sync failed. See the error above, then try: uv sync --python 3.12" }

Write-Host "BottleNeck is starting at http://127.0.0.1:8000" -ForegroundColor Green
uv run --python 3.12 uvicorn main:app --host 127.0.0.1 --port 8000
