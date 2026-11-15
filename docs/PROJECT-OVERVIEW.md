# BottleNeck: project overview

BottleNeck is a self-hosted team workspace built around a practical constraint: small teams want shared work tools, but they don't always want a separate hosted service for tasks, notes, chat and files. The application keeps those workflows in one installation that the team controls.

## Product shape

The interface is Persian-first and RTL. It combines work tracking with a shared knowledge area, then adds an instance-level administration layer for the person responsible for the server. Workspace permissions and server permissions stay separate because a person who manages a department should not automatically control the whole installation.

## Engineering decisions

**FastAPI with SQLite.** FastAPI provides typed HTTP routes and WebSocket events without a large service stack. SQLite keeps a small self-hosted deployment easy to copy and restore; it also sets the current limit, so the app runs as a single process against local storage.

**Vanilla JavaScript frontend.** The browser client uses a small HTML/CSS/JavaScript stack rather than introducing a separate frontend build pipeline. The trade-off is that `static/app.js` has grown into a large module and deserves a future decomposition pass.

**Server-side permission checks.** Buttons reflect a user's privileges, but the API remains the authority. Custom workspace roles, server-owner roles and resource access rules use separate checks.

**Portable data operations.** Full installation backups include the database and private file areas; workspace export excludes credentials and sessions. Restore runs offline through the CLI because replacing a live database from a browser request would be unsafe.

## Operational details

The app defaults to port `1939` and stores runtime content under `data/`, backups under `backups/` and diagnostic logs under `logs/`. A first-run CLI creates the server owner before the web process starts. The launch scripts target Python 3.12.

## Current constraints

- One Uvicorn process and one local SQLite database per installation.
- No multi-node deployment or shared database model.
- No built-in antivirus inspection for uploaded files.
- External CDN dependencies remain for selected fonts, icons and Markdown rendering.
- The project has automated API smoke tests, but no independent penetration test or full cross-browser accessibility audit.

These constraints are documented so operators can choose an appropriate deployment rather than infer capabilities from the interface.
