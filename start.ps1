$ErrorActionPreference = "Stop"
$env:BOTTLENECK_ENV = if ($env:BOTTLENECK_ENV) { $env:BOTTLENECK_ENV } else { "production" }
$env:BOTTLENECK_ENABLE_API_DOCS = if ($env:BOTTLENECK_ENABLE_API_DOCS) { $env:BOTTLENECK_ENABLE_API_DOCS } else { "0" }
Set-Location $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found. Install it from https://docs.astral.sh/uv/ and reopen PowerShell."
}

$env:BOTTLENECK_BACKUP_INTERVAL_HOURS = if ($env:BOTTLENECK_BACKUP_INTERVAL_HOURS) { $env:BOTTLENECK_BACKUP_INTERVAL_HOURS } else { "24" }
$env:BOTTLENECK_BACKUP_RETENTION = if ($env:BOTTLENECK_BACKUP_RETENTION) { $env:BOTTLENECK_BACKUP_RETENTION } else { "14" }

Write-Host "BottleNeck v1.1.0 | preparing pinned Python 3.12 environment..." -ForegroundColor Cyan
uv sync --python 3.12 --no-dev
if ($LASTEXITCODE -ne 0) { throw "uv sync failed. Try: Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue; uv sync --python 3.12 --no-dev" }

# The CLI owns first-run server-owner setup and the actual server process.
if ($env:BOTTLENECK_SSL_CERTFILE -and $env:BOTTLENECK_SSL_KEYFILE) {
    $env:BOTTLENECK_COOKIE_SECURE = "1"
} elseif (-not $env:BOTTLENECK_COOKIE_SECURE) {
    $env:BOTTLENECK_COOKIE_SECURE = "0"
}
Write-Host "`nRunning first-install / server-owner check..." -ForegroundColor Cyan
uv run --no-sync --python 3.12 python bottleneck_cli.py setup --if-needed
if ($LASTEXITCODE -ne 0) { throw "BottleNeck server-owner setup failed." }
Write-Host "`nStarting the BottleNeck server through its operations CLI..." -ForegroundColor Green
$serveArgs = @()
if ($env:BOTTLENECK_HOST) { $serveArgs += @("--host", $env:BOTTLENECK_HOST) }
if ($env:BOTTLENECK_PORT) { $serveArgs += @("--port", $env:BOTTLENECK_PORT) }
uv run --no-sync --python 3.12 python bottleneck_cli.py serve @serveArgs
