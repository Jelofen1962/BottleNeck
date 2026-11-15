$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found. Install it from https://docs.astral.sh/uv/ and reopen PowerShell."
}

$env:BOTTLENECK_BACKUP_INTERVAL_HOURS = if ($env:BOTTLENECK_BACKUP_INTERVAL_HOURS) { $env:BOTTLENECK_BACKUP_INTERVAL_HOURS } else { "24" }
$env:BOTTLENECK_BACKUP_RETENTION = if ($env:BOTTLENECK_BACKUP_RETENTION) { $env:BOTTLENECK_BACKUP_RETENTION } else { "14" }

Write-Host "BottleNeck v0.9.0 | preparing Python 3.12 environment..." -ForegroundColor Cyan
uv sync --python 3.12
if ($LASTEXITCODE -ne 0) { throw "uv sync failed. Try: Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue; uv sync --python 3.12" }

# The CLI owns first-run server-owner setup and the actual server process.
$env:BOTTLENECK_COOKIE_SECURE = if ($env:BOTTLENECK_SSL_CERTFILE -and $env:BOTTLENECK_SSL_KEYFILE) { "1" } else { "0" }
Write-Host "`nRunning first-install / server-owner check..." -ForegroundColor Cyan
uv run --python 3.12 python bottleneck_cli.py setup --if-needed
if ($LASTEXITCODE -ne 0) { throw "BottleNeck server-owner setup failed." }
Write-Host "`nStarting the BottleNeck server through its operations CLI..." -ForegroundColor Green
$serveArgs = @()
if ($env:BOTTLENECK_HOST) { $serveArgs += @("--host", $env:BOTTLENECK_HOST) }
if ($env:BOTTLENECK_PORT) { $serveArgs += @("--port", $env:BOTTLENECK_PORT) }
uv run --python 3.12 python bottleneck_cli.py serve @serveArgs
