# Release checklist

Use this checklist before tagging a BottleNeck release.

## Source and tests

- [ ] Update the version in `pyproject.toml`, `main.py`, `index.html`, `static/app.js`, launch scripts and schema comments.
- [ ] Run Python compilation and JavaScript syntax checks.
- [ ] Run `uv run --group dev --python 3.12 pytest -q`.
- [ ] Test a fresh installation and a populated upgrade from the previous stable version.
- [ ] Exercise owner, operator, auditor and regular workspace roles.
- [ ] Verify import/export, backup creation and offline restore on a copy of real-shaped synthetic data.

## Browser acceptance

- [ ] Check desktop and narrow-screen layouts.
- [ ] Check RTL, mixed Persian/English text and Jalali date fields.
- [ ] Check login, remember-me, invitations, chat, uploads, Markdown and WebSocket reconnects.
- [ ] Check keyboard focus, dialog close behavior and error messages.
- [ ] Capture screenshots using synthetic data only.

## Packaging and operations

- [ ] Confirm runtime data, credentials, `.env`, backups, logs and virtual environments are absent from the archive.
- [ ] Verify launch scripts, dependency pins and documentation agree.
- [ ] Run `bottleneck_cli.py doctor` after installation.
- [ ] Verify health check and server logs.
- [ ] Verify HTTPS, allowed origins and firewall rules for the target deployment.
- [ ] Test a restore before publishing.

## GitHub release

- [ ] Update `CHANGELOG.md` and `ROADMAP.md`.
- [ ] Review `README.md`, links and hero image.
- [ ] Build and test the release ZIP.
- [ ] Publish checksums alongside the archive.
- [ ] Tag the release and attach the source archive.
