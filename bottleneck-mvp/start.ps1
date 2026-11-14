$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found. Install it from https://docs.astral.sh/uv/ and reopen PowerShell."
}

$env:BOTTLENECK_PORT = "1939"
Write-Host "BottleNeck v0.4.0 | preparing Python 3.12 environment..." -ForegroundColor Cyan
uv sync --python 3.12
if ($LASTEXITCODE -ne 0) { throw "uv sync failed. Try: Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue; uv sync --python 3.12" }

Write-Host "`nBottleNeck is listening on all network interfaces at port 1939." -ForegroundColor Green
Write-Host "This computer: http://127.0.0.1:1939" -ForegroundColor Green
try {
    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop | Where-Object {
        $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" -and $_.AddressState -eq "Preferred"
    } | Select-Object -ExpandProperty IPAddress -Unique
    if ($ips) {
        Write-Host "Local network addresses:" -ForegroundColor Cyan
        foreach ($ip in $ips) { Write-Host "  http://${ip}:1939" -ForegroundColor White }
    }
} catch { Write-Host "Open Settings > Network to find this computer's IPv4 address." -ForegroundColor Yellow }
Write-Host "`nFor LAN access, allow the Windows Firewall prompt on Private networks only." -ForegroundColor Yellow
Write-Host "Optional firewall helper (run as Administrator): .\allow-lan-firewall.ps1" -ForegroundColor Yellow
Write-Host "Do not port-forward this development server to the public internet.`n" -ForegroundColor Yellow
uv run --python 3.12 uvicorn main:app --host 0.0.0.0 --port 1939
