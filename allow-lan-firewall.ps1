# Optional helper: run this script from an elevated PowerShell window.
$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Open PowerShell as Administrator, then run .\allow-lan-firewall.ps1"
}
$existing = Get-NetFirewallRule -DisplayName "BottleNeck LAN TCP 1939" -ErrorAction SilentlyContinue
if ($existing) { Remove-NetFirewallRule -DisplayName "BottleNeck LAN TCP 1939" }
New-NetFirewallRule -DisplayName "BottleNeck LAN TCP 1939" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 1939 -Profile Private -RemoteAddress LocalSubnet | Out-Null
Write-Host "Allowed BottleNeck TCP 1939 from the local subnet on Private networks only." -ForegroundColor Green
