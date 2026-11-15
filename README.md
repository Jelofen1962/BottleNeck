<div align="center">
  <img src="https://github.com/user-attachments/assets/c71d944d-14fa-4459-9f77-190d090b4a59" alt="BottleNeck, a self-hosted workspace for team collaboration" width="100%" />
</div>

<div align="center">

[![Release](https://img.shields.io/badge/release-v1.1.0-C65C42?style=flat-square)](CHANGELOG.md)
[![CI](https://github.com/Jelofen1962/BottleNeck/actions/workflows/ci.yml/badge.svg)](https://github.com/Jelofen1962/BottleNeck/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-6B8068?style=flat-square)](LICENSE)
[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-8B6BB1?style=flat-square)](CONTRIBUTING.md)

**A self-hosted workspace for teams that want their work and files on their own server.**

[Quick start](#quick-start) · [Features](#what-you-can-do) · [Documentation](#documentation) · [فارسی](README.fa.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

</div>

BottleNeck brings tasks, projects, team chat, shared notes, concept boards and file storage into one place. It runs on a machine you control; your team connects through a browser on the local network or through a deployment you configure yourself.

The interface is Persian-first and right-to-left, with English support in technical content. The server uses FastAPI and SQLite, while the frontend stays deliberately small: HTML, CSS and vanilla JavaScript.

> **Project status: stable v1.1.0.** The experimental label ends here. This release is intended for self-hosted use on a trusted private network. Internet-facing deployments need HTTPS, a correctly configured reverse proxy, secure backups and an environment-specific security review; see [Deployment](docs/DEPLOYMENT.md).

## What you can do

| Area | What it covers |
|---|---|
| **Tasks and projects** | Assign work, set deadlines, track status, use checklists, dependencies, approvals, templates and time entries. |
| **Team collaboration** | Workspace and team chat, replies, mentions, file attachments, voice notes, online presence and named cursors. |
| **Shared knowledge** | Markdown notes with live preview, collaborative concept boards, shared text and resource links. |
| **Files and folders** | Upload and download files, organize folders, and set workspace, team, password and role-based access rules. |
| **Workspace access** | Multiple workspaces per account, invitation links, short-lived join codes and custom roles with granular permissions. |
| **Server operations** | First-run owner setup, a dedicated administration area, CLI diagnostics, backups, restore and selective import/export. |

BottleNeck also includes a Jalali calendar, a guided first-run tour, a Persian user handbook and a 120%-scale desktop layout that returns to normal sizing on narrow screens.

## Quick start

### Requirements

- Windows 10/11, Linux or macOS.
- [uv](https://docs.astral.sh/uv/) for Python environment management.
- Python 3.12. The launcher asks `uv` to use this version; Python 3.15 is not supported by this release.
- A writable project directory. Keep the database and uploaded files outside public web roots.

The project pins its direct runtime and development dependencies in `pyproject.toml`; `uv` resolves compatible transitive dependencies for the host platform during setup.

### Windows

1. Download the [latest release](https://github.com/Jelofen1962/BottleNeck/releases/latest) and extract the archive.
2. Open PowerShell in the `bottleneck-mvp` folder.
3. Run the installer:

   ```powershell
   .\start.ps1
   ```

On a fresh installation, the setup CLI asks for the server owner's name, email, password and primary workspace name. Keep the terminal open while BottleNeck runs; `Ctrl+C` stops the server cleanly.

### Linux and macOS

```bash
chmod +x start.sh
./start.sh
```

The same first-run owner setup runs before Uvicorn starts. The launcher creates the Python environment and starts the application on port `1939`.

### Open the workspace

On the host computer:

```text
http://127.0.0.1:1939
```

On another device connected to the same network, use the LAN URL printed by the installer:

```text
http://<server-lan-ip>:1939
```

If Windows Firewall blocks access, set the network profile to **Private** and run `allow-lan-firewall.ps1` from an elevated PowerShell window. The rule is scoped to the Private profile and local subnet.

<details>
  <summary>Manual setup and server commands</summary>

  ```powershell
  uv sync --python 3.12 --no-dev
  uv run --no-sync --python 3.12 python bottleneck_cli.py setup --if-needed
  uv run --no-sync --python 3.12 python bottleneck_cli.py serve --host 0.0.0.0 --port 1939
  ```

  The API reference is disabled by default in production mode. To enable it temporarily on a trusted development network, set `BOTTLENECK_ENABLE_API_DOCS=1` before starting the server; the endpoints are `/api/docs` and `/api/openapi.json`.
</details>

## Screenshots

The image at the top of this page is an illustration of the product, not a captured application screen. Replace it with a real screenshot whenever you have a clean demo workspace ready. The [media guide](docs/assets/README.md) explains the expected path and dimensions.

Suggested screenshots for a public release:

- `docs/assets/screenshot-dashboard.webp`: overview with non-sensitive sample data.
- `docs/assets/screenshot-chat.webp`: chat with mentions and an attachment preview.
- `docs/assets/screenshot-editor.webp`: Markdown editor with live preview.
- `docs/assets/screenshot-server-admin.webp`: server operations page with test data only.

Do not commit screenshots containing real member names, private messages, invitation links, email addresses or internal files.

## How BottleNeck is put together

```text
Browser
  ├── RTL web interface (HTML, CSS, vanilla JavaScript)
  ├── REST requests and authenticated WebSocket events
  │
  ▼
FastAPI application (single Uvicorn process)
  ├── Account sessions and workspace permissions
  ├── Tasks, projects, chat, notes and boards
  ├── Server-owner CLI and administration API
  └── Scheduled backups, recurring work and notification delivery
  │
  ├── SQLite database
  ├── Private upload directories
  ├── Shared workspace files
  └── Backup archives and operational logs
```

SQLite keeps installation simple and makes a workspace easy to back up. The trade-off matters: run one application process against one local database. Do not add Uvicorn workers or mount the SQLite data directory on a network share. For a larger multi-server deployment, the storage and job architecture needs a separate PostgreSQL-backed release.

More detail lives in [Architecture](docs/ARCHITECTURE.md), [Deployment](docs/DEPLOYMENT.md) and the [UI design contract](docs/UI-DESIGN-SYSTEM.md).

## Documentation

| Guide | Use it for |
|---|---|
| [Persian user handbook](HANDBOOK.md) | Every screen, task workflow, shared area and workspace permission. |
| [Installation and upgrade guide](docs/DEPLOYMENT.md) | LAN setup, HTTPS, backups, service management and safe upgrades. |
| [Server operations](docs/SERVER-OPERATIONS.md) | Owner setup, CLI commands, server roles, restore and data portability. |
| [Architecture notes](docs/ARCHITECTURE.md) | Application layers, data layout, events and design constraints. |
| [Release history](CHANGELOG.md) | Changes from the early MVP releases through v1.1.0. |
| [Publishing guide](docs/PUBLISHING.md) | Push the repository, publish a release and pin it to the maintainer profile. |
| [Release checklist](docs/RELEASE-CHECKLIST.md) | Checks to run before tagging a new release. |
| [UI design system](docs/UI-DESIGN-SYSTEM.md) | Shared rules for layout, typography, color, dialogs, chat and feedback. |
| [UX audit, v1.1.0](docs/UX-AUDIT-v1.1.0.md) | Findings and changes from the latest interface review. |
| [Roadmap](ROADMAP.md) | Planned work and known gaps. |

## Configuration and data

BottleNeck stores runtime data under the project directory unless you set a custom path. The important directories are:

```text
bottleneck-mvp/
├── data/
│   ├── bottleneck.sqlite3
│   ├── uploads/
│   ├── shared/
│   └── chat_uploads/
├── backups/
├── logs/
└── ...application source...
```

Copy [`.env.example`](.env.example) to `.env` only if you manage environment variables through a tool that reads that file; the current launcher does not automatically load `.env`. Set variables in your service manager or shell instead. Never commit `.env`, `data/`, `backups/` or `logs/`.

For example, direct HTTPS through Uvicorn uses a certificate and matching private key:

```powershell
$env:BOTTLENECK_SSL_CERTFILE = "C:\certs\workspace.crt"
$env:BOTTLENECK_SSL_KEYFILE = "C:\certs\workspace.key"
$env:BOTTLENECK_COOKIE_SECURE = "1"
.\start.ps1
```

The deployment guide covers reverse proxies, allowed origins, firewall scope and off-device backup copies.

## Security at a glance

The application stores password hashes, hashed session tokens and hashed join/reset tokens; session cookies use `HttpOnly` and `SameSite=Lax`, and HTTPS deployments can enable the `Secure` cookie flag. v1.1.0 adds persistent authentication throttles, origin checks for state-changing API requests, security response headers, a Content Security Policy and rotating server logs.

Those controls reduce common risks, but they don't replace network isolation or a security review. BottleNeck does not scan uploaded files for malware, and the project has not undergone an independent penetration test. Read [SECURITY.md](SECURITY.md) before deploying outside a trusted LAN.

## Contributing

BottleNeck is open to outside contributions. Bug reports, Persian copy edits, better documentation, accessibility fixes and focused code changes are all welcome; start with [CONTRIBUTING.md](CONTRIBUTING.md) so local changes follow the same setup and test commands.

Before opening a pull request, run:

```bash
python -m py_compile main.py bottleneck_cli.py
node --check static/app.js
python scripts/ui_audit.py
uv run --group dev --python 3.12 pytest -q
```

Please don't include personal data or real workspace exports in issues, pull requests or screenshots. See the [Code of Conduct](CODE_OF_CONDUCT.md) and [security reporting guide](SECURITY.md).

## Roadmap

The stable release concentrates on the core self-hosted workflow. Follow [ROADMAP.md](ROADMAP.md) for work under consideration; proposed items are not promises or release dates.

## Maintainer

BottleNeck is maintained by **Jelofen** ([@Jelofen1962](https://github.com/Jelofen1962)). The product includes the creator credit «ساخته شده با عشق توسط ژلوفن».

For project questions, use the repository's [Issues](https://github.com/Jelofen1962/BottleNeck/issues) or [Discussions](https://github.com/Jelofen1962/BottleNeck/discussions) once those features are enabled. You can also reach the maintainer on [Telegram](https://t.me/jelofen1962).

## License

BottleNeck is released under the [MIT License](LICENSE). Contributions are submitted under the same license.
