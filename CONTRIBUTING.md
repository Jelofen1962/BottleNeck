# Contributing to BottleNeck

Thanks for taking a look at BottleNeck. The project welcomes focused contributions from people who use it, test it or want to improve the parts that still feel rough.

You don't need to redesign the whole application to help. A reproducible bug report, a Persian wording fix, a keyboard-navigation improvement or a clear test can be more useful than a large patch with unclear scope.

## Before you start

For a new feature or a behavior change, open an issue first so we can agree on the problem and avoid overlapping work. Small documentation fixes can go straight to a pull request. Please search existing issues before creating another one.

If the change touches authentication, permissions, file handling, backups, imports or workspace isolation, describe the security implications in the pull request. Include a regression test where practical.

## Development setup

Use Python 3.12 and [uv](https://docs.astral.sh/uv/). Node.js is only needed for the JavaScript syntax check.

```bash
uv sync --group dev --python 3.12
```

Create a separate local data directory or use a temporary test database; never develop against a real team's workspace. First-run setup is available through:

```bash
uv run --python 3.12 python bottleneck_cli.py setup
uv run --python 3.12 python bottleneck_cli.py serve --host 127.0.0.1 --port 1939
```

## Checks before a pull request

Run the checks from the project root:

```bash
python -m py_compile main.py bottleneck_cli.py
node --check static/app.js
uv run --group dev --python 3.12 pytest -q
```

If your change affects SQLite, test both a fresh database and an upgrade from the prior schema. If it affects permissions, test allowed and denied requests with different roles. If it changes a user workflow, add a short manual test plan to the pull request.

## Code and interface conventions

- Keep the interface Persian-first and RTL. Check mixed Persian/English text, numbers, date fields and filenames.
- Preserve keyboard access, visible focus states, useful labels and responsive behavior.
- Keep the established neutral surfaces and restrained rust accent. Don't introduce a generic dashboard theme or decorative gradients.
- Keep server-wide administration separate from workspace administration.
- Enforce permissions in the API. Hiding a button is not access control.
- Use parameterized SQL. Don't build SQL values from untrusted strings.
- Store uploads outside the static web directory and validate file names, size and access on the server.
- Avoid new runtime dependencies unless they solve a concrete problem; pin direct dependencies in `pyproject.toml` and update documentation when installation changes.

## Pull request shape

A useful PR explains the user problem, the change, and how you tested it. Include screenshots for visible UI changes, but use synthetic data and remove names, email addresses, private notes and invitation tokens.

Keep changes reviewable. Split migrations, broad refactors and interface redesigns into separate PRs when possible. Update `HANDBOOK.md` for user-facing behavior and `CHANGELOG.md` for release-level changes.

## What must stay out of Git

Never commit `.env`, SQLite databases, `data/`, `backups/`, server logs, uploaded files, session cookies, invitation links or real workspace exports. The repository's `.gitignore` covers the usual runtime paths; check `git status` before committing.

## Licensing

By submitting a contribution, you agree to distribute it under the MIT License used by this repository. You retain copyright in your work while granting the project and its users the rights described by that license.

## Where to ask

Use the repository's issue tracker for bugs and feature discussions. For a security issue, follow [SECURITY.md](SECURITY.md) instead of publishing exploit details.
