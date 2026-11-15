#!/usr/bin/env bash
set -euo pipefail
export BOTTLENECK_ENV="${BOTTLENECK_ENV:-production}"
export BOTTLENECK_ENABLE_API_DOCS="${BOTTLENECK_ENABLE_API_DOCS:-0}"
cd "$(dirname "$0")"
command -v uv >/dev/null 2>&1 || { echo "uv was not found. Install it from https://docs.astral.sh/uv/" >&2; exit 1; }
export BOTTLENECK_BACKUP_INTERVAL_HOURS="${BOTTLENECK_BACKUP_INTERVAL_HOURS:-24}"
export BOTTLENECK_BACKUP_RETENTION="${BOTTLENECK_BACKUP_RETENTION:-14}"

echo "BottleNeck v1.0.0 | preparing Python 3.12 environment..."
uv sync --python 3.12 --no-dev
if [[ -n "${BOTTLENECK_SSL_CERTFILE:-}" && -n "${BOTTLENECK_SSL_KEYFILE:-}" ]]; then
  export BOTTLENECK_COOKIE_SECURE=1
else
  export BOTTLENECK_COOKIE_SECURE="${BOTTLENECK_COOKIE_SECURE:-0}"
fi
uv run --no-sync --python 3.12 python bottleneck_cli.py setup --if-needed
serve_args=()
[[ -n "${BOTTLENECK_HOST:-}" ]] && serve_args+=(--host "$BOTTLENECK_HOST")
[[ -n "${BOTTLENECK_PORT:-}" ]] && serve_args+=(--port "$BOTTLENECK_PORT")
uv run --no-sync --python 3.12 python bottleneck_cli.py serve "${serve_args[@]}"
