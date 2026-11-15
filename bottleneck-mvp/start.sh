#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v uv >/dev/null 2>&1 || { echo "uv was not found. Install it from https://docs.astral.sh/uv/" >&2; exit 1; }
export BOTTLENECK_BACKUP_INTERVAL_HOURS="${BOTTLENECK_BACKUP_INTERVAL_HOURS:-24}"
export BOTTLENECK_BACKUP_RETENTION="${BOTTLENECK_BACKUP_RETENTION:-14}"

echo "BottleNeck v0.9.0 | preparing Python 3.12 environment..."
uv sync --python 3.12
export BOTTLENECK_COOKIE_SECURE=0
if [[ -n "${BOTTLENECK_SSL_CERTFILE:-}" && -n "${BOTTLENECK_SSL_KEYFILE:-}" ]]; then export BOTTLENECK_COOKIE_SECURE=1; fi
uv run --python 3.12 python bottleneck_cli.py setup --if-needed
serve_args=()
[[ -n "${BOTTLENECK_HOST:-}" ]] && serve_args+=(--host "$BOTTLENECK_HOST")
[[ -n "${BOTTLENECK_PORT:-}" ]] && serve_args+=(--port "$BOTTLENECK_PORT")
uv run --python 3.12 python bottleneck_cli.py serve "${serve_args[@]}"
