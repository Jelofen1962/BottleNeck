$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found. Install it from https://docs.astral.sh/uv/ and reopen PowerShell."
}

$env:BOTTLENECK_HOST = if ($env:BOTTLENECK_HOST) { $env:BOTTLENECK_HOST } else { "0.0.0.0" }
$env:BOTTLENECK_PORT = if ($env:BOTTLENECK_PORT) { $env:BOTTLENECK_PORT } else { "1939" }
$env:BOTTLENECK_BACKUP_INTERVAL_HOURS = if ($env:BOTTLENECK_BACKUP_INTERVAL_HOURS) { $env:BOTTLENECK_BACKUP_INTERVAL_HOURS } else { "24" }
$env:BOTTLENECK_BACKUP_RETENTION = if ($env:BOTTLENECK_BACKUP_RETENTION) { $env:BOTTLENECK_BACKUP_RETENTION } else { "14" }

Write-Host "BottleNeck v0.6.0 | preparing Python 3.12 environment..." -ForegroundColor Cyan
uv sync --python 3.12
if ($LASTEXITCODE -ne 0) { throw "uv sync failed. Try: Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue; uv sync --python 3.12" }

$uvicornArgs = @("run", "--python", "3.12", "uvicorn", "main:app", "--host", $env:BOTTLENECK_HOST, "--port", $env:BOTTLENECK_PORT)
$scheme = "http"
if ($env:BOTTLENECK_SSL_CERTFILE -and $env:BOTTLENECK_SSL_KEYFILE) {
    if (-not (Test-Path $env:BOTTLENECK_SSL_CERTFILE) -or -not (Test-Path $env:BOTTLENECK_SSL_KEYFILE)) {
        throw "HTTPS certificate or key file was not found. Check BOTTLENECK_SSL_CERTFILE and BOTTLENECK_SSL_KEYFILE."
    }
    $uvicornArgs += @("--ssl-certfile", $env:BOTTLENECK_SSL_CERTFILE, "--ssl-keyfile", $env:BOTTLENECK_SSL_KEYFILE)
    $env:BOTTLENECK_COOKIE_SECURE = "1"
    $scheme = "https"
} else {
    $env:BOTTLENECK_COOKIE_SECURE = "0"
}

Write-Host "`nBottleNeck is listening on $($env:BOTTLENECK_HOST):$($env:BOTTLENECK_PORT)." -ForegroundColor Green
Write-Host "This computer: ${scheme}://127.0.0.1:$($env:BOTTLENECK_PORT)" -ForegroundColor Green
try {
    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop | Where-Object {
        $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" -and $_.AddressState -eq "Preferred"
    } | Select-Object -ExpandProperty IPAddress -Unique
    if ($ips) {
        Write-Host "Local network addresses:" -ForegroundColor Cyan
        foreach ($ip in $ips) { Write-Host "  ${scheme}://${ip}:$($env:BOTTLENECK_PORT)" -ForegroundColor White }
    }
} catch { Write-Host "Open Settings > Network to find this computer's IPv4 address." -ForegroundColor Yellow }
Write-Host "`nAutomatic backups: every $($env:BOTTLENECK_BACKUP_INTERVAL_HOURS) hours; retain $($env:BOTTLENECK_BACKUP_RETENTION) copies." -ForegroundColor Cyan
Write-Host "HTTPS: set BOTTLENECK_SSL_CERTFILE and BOTTLENECK_SSL_KEYFILE before launch." -ForegroundColor Cyan
Write-Host "For LAN access, allow the Windows Firewall prompt on Private networks only." -ForegroundColor Yellow
Write-Host "Do not port-forward this server directly to the public internet.`n" -ForegroundColor Yellow
uv @uvicornArgs
