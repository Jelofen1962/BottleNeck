# Deployment guide

BottleNeck v1.1.0 is a stable self-hosted release for a trusted private network. The included launcher is suitable for a small team on one host. Internet-facing deployments need HTTPS and a correctly configured reverse proxy; keep the SQLite database on local storage and run only one Uvicorn process.

## Windows LAN installation

1. Install [uv](https://docs.astral.sh/uv/), extract the release and open PowerShell in `bottleneck-mvp`.
2. Set the Windows network profile to **Private**.
3. Run `.\start.ps1` from a normal PowerShell window. First-run setup asks for the server owner.
4. If peers cannot connect, run `allow-lan-firewall.ps1` from an elevated PowerShell window. The rule applies to the Private profile and local subnet.
5. Copy the `data/` and `backups/` directories to a separate device on a schedule you control.

The server listens on `0.0.0.0:1939` by default. Keep port 1939 inside the LAN; don't create a router port-forward for it.

## Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

For a long-running Linux service, create a dedicated OS account and project directory, install the dependencies as that account, complete owner setup once, then use the sample [`deploy/bottleneck.service`](../deploy/bottleneck.service). Review every path and user name before enabling it.

## Environment variables

Copy `.env.example` as a reference, but note that the launcher does **not** load `.env` automatically. Set variables in PowerShell, your service manager or your container runtime.

| Variable | Purpose | Default |
|---|---|---|
| `BOTTLENECK_ENV` | Runtime mode. `production` disables API docs by default. | `production` in launch scripts |
| `BOTTLENECK_ENABLE_API_DOCS` | Expose `/api/docs` and `/api/openapi.json`. | `0` in production |
| `BOTTLENECK_HOST` | Uvicorn bind address. | `0.0.0.0` |
| `BOTTLENECK_PORT` | Listening port. | `1939` |
| `BOTTLENECK_COOKIE_SECURE` | Mark session cookies `Secure`. Set to `1` under HTTPS. | `0` for plain LAN HTTP |
| `BOTTLENECK_ALLOWED_ORIGINS` | Additional exact browser origins, comma-separated. | empty |
| `BOTTLENECK_TRUSTED_PROXY_IPS` | Explicit proxy IPs trusted for forwarded scheme/client headers. | empty |
| `BOTTLENECK_SSL_CERTFILE` / `BOTTLENECK_SSL_KEYFILE` | Direct Uvicorn TLS certificate and key. Set both. | unset |
| `BOTTLENECK_BACKUP_INTERVAL_HOURS` | Automatic full backup interval. | `24` |
| `BOTTLENECK_BACKUP_RETENTION` | Number of recent archives to keep. | `14` |

Custom database and file paths are available through `BOTTLENECK_DB`, `BOTTLENECK_UPLOAD_DIR`, `BOTTLENECK_SHARED_DIR` and `BOTTLENECK_BACKUP_DIR`.

## HTTPS

For direct TLS termination in Uvicorn, set both certificate variables before running the launcher:

```powershell
$env:BOTTLENECK_SSL_CERTFILE = "C:\certs\workspace.crt"
$env:BOTTLENECK_SSL_KEYFILE = "C:\certs\workspace.key"
$env:BOTTLENECK_COOKIE_SECURE = "1"
.\start.ps1
```

The launcher marks the session cookie `Secure` when both certificate variables are present. For microphone access from other devices, use HTTPS; browsers generally block microphone access on ordinary HTTP LAN origins.

## Reverse proxy

When Nginx or another reverse proxy terminates TLS, bind BottleNeck to localhost and trust only the proxy address. Example environment:

```bash
BOTTLENECK_ENV=production
BOTTLENECK_ENABLE_API_DOCS=0
BOTTLENECK_HOST=127.0.0.1
BOTTLENECK_PORT=1939
BOTTLENECK_COOKIE_SECURE=1
BOTTLENECK_TRUSTED_PROXY_IPS=127.0.0.1
BOTTLENECK_ALLOWED_ORIGINS=https://workspace.example.com
```

A sample Nginx configuration is available at [`deploy/nginx.conf.example`](../deploy/nginx.conf.example). Update the hostname, certificate paths and trusted proxy address before use. The proxy must forward WebSocket upgrade headers and must enforce HTTPS. Do not trust forwarded headers from arbitrary network clients.

## Firewall and network boundary

For a LAN install, permit port 1939 only on the private subnet. Avoid public DNS records or router port forwarding unless the server sits behind a reviewed HTTPS gateway. The app's origin checks and rate limits are useful layers, not a substitute for network controls.

## Updates

1. Stop BottleNeck.
2. Create a fresh off-device copy of `data/`, `backups/` and any custom upload directories.
3. Extract the new release into a new folder.
4. Copy the existing runtime data into that folder.
5. Run the new launcher and review its startup output.
6. Run `uv run --python 3.12 python bottleneck_cli.py doctor` and check `/api/health`.

Never replace the live database with a blank `schema.sql`. The application applies schema migrations at startup.

## Operational boundaries

- Use one Uvicorn process. Background schedulers run in-process, and SQLite serializes writes.
- Keep SQLite on local disk. Do not use a shared network filesystem for the database.
- Backups on the same disk do not protect against disk failure; copy them elsewhere.
- Restore is an offline CLI operation. Test it with a copy of a recent archive.
- Uploaded files are not malware-scanned by BottleNeck.
- The release has not received an independent penetration test. Review your deployment and access model before handling regulated or highly sensitive data.
