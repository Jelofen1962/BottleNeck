# BottleNeck v0.9.0 — Server Operations Release

BottleNeck is a Persian-first, RTL team workspace built with FastAPI, SQLite, HTML, CSS and vanilla JavaScript. It brings task/project management, collaboration, shared files and Markdown notes, team chat, productivity tools and server administration into one self-hosted installation.

The v0.9.0 release adds a dedicated server-owner CLI and a separate server-management GUI. Server-wide controls are not placed inside ordinary workspace settings. The default deployment is a trusted local network server on `0.0.0.0:1939`. The project follows the supplied anti-template design brief: restrained surfaces, purposeful type and interactions, no default indigo identity, no decorative hero gradients, no placeholder copy and no fabricated metrics.

## 1. Requirements

- Windows 10/11, Linux or macOS.
- [uv](https://docs.astral.sh/uv/).
- Python 3.12, downloaded/managed by uv if it is not already installed.
- A private/trusted LAN for multi-device access. On Windows, set the network profile to **Private**.

The project uses `uvicorn` plus the pure-Python `websockets` package. It deliberately does not install `uvicorn[standard]`, avoiding the optional PyYAML build dependency that previously required Microsoft C++ Build Tools on Python 3.15.

## 2. Fresh installation on Windows

1. Extract the ZIP to a folder that the Windows account can write to.
2. Open PowerShell in `bottleneck-mvp`.
3. Run:

   ```powershell
   .\start.ps1
   ```

4. On the first run, the **server-owner setup CLI** asks for the installation owner's display name, email, password and primary workspace name. This is a server-level identity, separate from ordinary workspace roles.
5. After setup, the CLI starts Uvicorn in the foreground. Keep this terminal open while the team uses BottleNeck.

The default addresses are:

- Host computer: `http://127.0.0.1:1939`
- Other devices on the same LAN: `http://<host-LAN-IP>:1939`
- API reference: `http://<host-LAN-IP>:1939/api/docs`

The CLI prints the detected LAN URLs. If Windows Firewall blocks connections, set the network profile to **Private**, then run `allow-lan-firewall.ps1` once from an elevated PowerShell window. The rule is restricted to the Private profile and local subnet.

Stop the foreground server with `Ctrl+C`.

## 3. Fresh installation on Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

The script runs `uv sync --python 3.12`, runs the server-owner setup prompt, then launches the CLI-managed Uvicorn process on the configured host and port.

## 4. Upgrade from v0.8.x

1. Stop the old BottleNeck server with `Ctrl+C`.
2. Make a separate copy of the complete `data` and `backups` directories. Do not rely only on the automatic backups stored on the same disk.
3. Extract v0.9.0 into a **new** folder.
4. Copy the old `data` and `backups` directories into the new `bottleneck-mvp` folder.
5. Run `start.ps1` (Windows) or `start.sh` (Linux/macOS).
6. The first v0.9 startup creates the server-operations tables and migrates the earliest workspace creator to the initial server-owner role. Existing user accounts, memberships, tasks, shared files and workspaces remain in the database.

For an older installation that has accounts but no workspace or no identifiable first owner, the CLI asks for credentials to link an existing account. It does not silently elevate a random account registered after the server is already running.

After the migration, sign in with the account that created the first workspace. The **مدیریت سرور** navigation group appears for server administrators only.

## 5. Server owner and server roles

BottleNeck distinguishes installation-wide administration from workspace administration.

| Server role | Capabilities |
|---|---|
| `owner` | Full instance administration, configuration, operators, backups, imports/exports and restore via local CLI |
| `operator` | View operational status/users/workspaces/logs/backup inventory; create backups; import and export data. Full backup ZIP downloads remain owner-only. |
| `auditor` | Read-only operational overview, users, workspaces, logs, backup inventory and data exports. Cannot create or download full backup archives. |
| regular account | No server-wide administration; workspace access follows workspace roles and permissions |

The initial server owner is configured by the installation CLI. An existing v0.8 installation is migrated by identifying the creator of its earliest workspace. The server-owner role is not a workspace role and cannot be granted through ordinary workspace member settings.

Only the installation owner can grant or revoke server operators/auditors. The web GUI cannot promote someone to `owner`. The owner account is protected from removal by the regular revoke operation.

## 6. Server management GUI

Open **مدیریت سرور** in the application sidebar. It is separate from workspace settings and visible only to users who have a server-admin role.

The page provides:

- Version, health, SQLite integrity, uptime, bound host and port.
- Account, workspace, active-session and server-admin counts.
- Database/data-folder size and free disk space.
- Server log size and recent audit events.
- Server configuration: bind host, port, automatic backup interval and retention.
- Workspace inventory with owner, member/task/file counts.
- Full workspace ZIP export and selected task/project CSV export.
- Task/project CSV imports and full workspace package import.
- Server user and operator/auditor listing and management.
- Backup listing, manual backup creation and download.

Changing the bind host or port requires a server restart. The GUI does not attempt to terminate its own server process. Use the CLI/terminal to stop it with `Ctrl+C`, then start it again.

Full-system restore is intentionally a local CLI operation. It must not be triggered from an ordinary browser session.

## 7. Server Operations CLI

Run commands from the project folder. The launcher has already installed the environment; otherwise run `uv sync --python 3.12` first.

### Status and diagnostics

```powershell
uv run --python 3.12 python bottleneck_cli.py status
uv run --python 3.12 python bottleneck_cli.py doctor
uv run --python 3.12 python bottleneck_cli.py logs --lines 100
```

`doctor` checks SQLite integrity, foreign keys, server-owner configuration, and write access to the database, backup, upload, shared-file, chat-file and server-log directories.

### Accounts, workspaces and server administrators

```powershell
uv run --python 3.12 python bottleneck_cli.py users list
uv run --python 3.12 python bottleneck_cli.py workspaces list
uv run --python 3.12 python bottleneck_cli.py admin list
uv run --python 3.12 python bottleneck_cli.py admin grant --email ops@example.com --role operator
uv run --python 3.12 python bottleneck_cli.py admin grant --email audit@example.com --role auditor
uv run --python 3.12 python bottleneck_cli.py admin revoke --email ops@example.com
```

The target must have a BottleNeck account first. The CLI supports `operator` and `auditor`; the installation owner is created only by first-run setup or the legacy migration path.

### Configuration

```powershell
uv run --python 3.12 python bottleneck_cli.py config show
uv run --python 3.12 python bottleneck_cli.py config set bind_host 0.0.0.0
uv run --python 3.12 python bottleneck_cli.py config set bind_port 1939
uv run --python 3.12 python bottleneck_cli.py config set backup_interval_hours 24
uv run --python 3.12 python bottleneck_cli.py config set backup_retention 14
```

Supported settings:

- `bind_host`: `0.0.0.0`, `localhost`, or a valid local IP address.
- `bind_port`: 1024–65535.
- `backup_interval_hours`: 1–720.
- `backup_retention`: 2–100 archives.

The bind host/port take effect after restart. The default is `0.0.0.0:1939`.

### Backup and restore

```powershell
uv run --python 3.12 python bottleneck_cli.py backup
```

A full backup is a ZIP containing the SQLite database, task uploads, shared-drive files, chat attachments and a manifest. The default automatic schedule is every 24 hours and the default retention is 14 archives. The scheduler runs inside the server process, so the server must be running. Backups are normally stored in `backups/`.

To restore, stop BottleNeck first, copy the current `data` folder somewhere safe, then run:

```powershell
uv run --python 3.12 python bottleneck_cli.py restore-backup --input .\backups\bottleneck-backup-example.zip --confirm-offline --yes
```

Both confirmation flags are mandatory. The CLI checks configured/local listening ports, validates the ZIP paths and manifest, checks the archive checksum and SQLite integrity/foreign keys, creates a pre-restore backup where possible, and uses rollback copies if file replacement fails. Start BottleNeck again with `start.ps1`.

### Selective data import/export

Export a full workspace package (JSON manifest/data plus related shared files; no passwords, credentials, sessions or global server settings):

```powershell
uv run --python 3.12 python bottleneck_cli.py export workspace --workspace "Workspace Name" --output .\workspace-export.zip
```

Import a workspace package as a **new workspace**:

```powershell
uv run --python 3.12 python bottleneck_cli.py import workspace --input .\workspace-export.zip
```

Export/import task or project CSV files:

```powershell
uv run --python 3.12 python bottleneck_cli.py export tasks --workspace "Workspace Name" --output .\tasks.csv
uv run --python 3.12 python bottleneck_cli.py export projects --workspace "Workspace Name" --output .\projects.csv
uv run --python 3.12 python bottleneck_cli.py import tasks --workspace "Workspace Name" --input .\tasks.csv
uv run --python 3.12 python bottleneck_cli.py import projects --workspace "Workspace Name" --input .\projects.csv
```

Task CSV import creates new tasks. Project CSV import updates a project with the same name or creates it if it does not exist. The full workspace importer matches members by email to existing accounts, maps unknown members to the importing server owner, regenerates resource IDs and creates a new workspace named with the suffix `(واردشده)`. It does not import user passwords or create user accounts.

## 8. Data layout

```text
bottleneck-mvp/
├── main.py
├── bottleneck_cli.py
├── schema.sql
├── index.html
├── static/
├── data/
│   ├── bottleneck.sqlite3
│   ├── uploads/
│   ├── shared/
│   └── chat_uploads/
├── backups/
├── logs/
│   └── server.log
├── start.ps1
└── start.sh
```

The actual SQLite location can be changed with `BOTTLENECK_DB`; upload, shared and backup directories also have environment overrides. Keep `data/`, `backups/` and any custom storage directories private. They contain team data and uploaded documents.

## 9. Optional HTTPS

For trusted certificates, set both environment variables before starting the launcher:

```powershell
$env:BOTTLENECK_SSL_CERTFILE = "C:\certs\bottleneck.crt"
$env:BOTTLENECK_SSL_KEYFILE = "C:\certs\bottleneck.key"
.\start.ps1
```

When both values are present, Uvicorn serves HTTPS and the session cookie is marked Secure. For microphone recording on other LAN devices, use HTTPS; browsers generally block microphone access on ordinary HTTP LAN origins (localhost is a special secure context).

## 10. Version and interface notes

- Persian-first RTL UI and Jalali date presentation; dates are stored as ISO Gregorian values in SQLite.
- Desktop interface scale is approximately 120%; narrow screens return to normal scale.
- LAN default is port 1939.
- Creator popup: black professional design, violet `ژلوفن`, white GitHub/Telegram/phone links and five-second GitHub redirect with a stay/close option.
- Static CSS/JS assets use the `0.9.0` cache version. If an older UI remains after upgrade, use `Ctrl+F5` once.

## 11. Security and MVP boundaries

- BottleNeck is intended for a trusted private LAN MVP. Do not expose port 1939 directly to the public Internet or forward it through a router without a separate production-hardening/security review.
- Server CLI commands run with the local operating-system account's filesystem permissions. Protect the host OS account and project folder.
- Server-owner setup is performed before the web server starts. Do not register the first user through a browser before running the installer CLI on a clean installation.
- Workspace packages deliberately exclude credentials, password hashes, session tokens, global configuration and server backups. They include member metadata and workspace content/files.
- Full backup archives contain the whole installation database and private files. Keep them restricted and store an off-device copy.
- Restore is offline-only and requires explicit confirmation flags. Test restore on a copy before relying on it for disaster recovery.
- The server log records operational errors and audit events; it avoids writing request query strings to reduce the chance of logging bearer tokens.
- Uploaded files are not antivirus-scanned. Use trusted team members and maintain OS-level malware protection.
- Rich Markdown rendering, remote fonts and some icons rely on external CDNs unless you vendor those assets locally.
- An independent penetration test and full browser-based visual acceptance test have not been performed for this release.

## 12. Creator credit

The application includes a black creator popup with **«ساخته شده با عشق توسط ژلوفن»**, violet creator name, white links to GitHub `https://github.com/Jelofen1962`, Telegram `https://t.me/jelofen1962` and phone `+989109721962`. If the popup remains open, it redirects to GitHub after five seconds; closing/staying cancels the redirect.
