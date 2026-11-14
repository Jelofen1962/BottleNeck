#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v uv >/dev/null 2>&1 || { echo "uv was not found. Install it from https://docs.astral.sh/uv/" >&2; exit 1; }
export BOTTLENECK_HOST="${BOTTLENECK_HOST:-0.0.0.0}"
export BOTTLENECK_PORT="${BOTTLENECK_PORT:-1939}"
export BOTTLENECK_BACKUP_INTERVAL_HOURS="${BOTTLENECK_BACKUP_INTERVAL_HOURS:-24}"
export BOTTLENECK_BACKUP_RETENTION="${BOTTLENECK_BACKUP_RETENTION:-14}"

echo "BottleNeck v0.6.0 | preparing Python 3.12 environment..."
uv sync --python 3.12
args=(run --python 3.12 uvicorn main:app --host "$BOTTLENECK_HOST" --port "$BOTTLENECK_PORT")
scheme="http"
if [[ -n "${BOTTLENECK_SSL_CERTFILE:-}" && -n "${BOTTLENECK_SSL_KEYFILE:-}" ]]; then
  [[ -f "$BOTTLENECK_SSL_CERTFILE" && -f "$BOTTLENECK_SSL_KEYFILE" ]] || { echo "HTTPS certificate/key file not found." >&2; exit 1; }
  args+=(--ssl-certfile "$BOTTLENECK_SSL_CERTFILE" --ssl-keyfile "$BOTTLENECK_SSL_KEYFILE")
  export BOTTLENECK_COOKIE_SECURE=1
  scheme="https"
else
  export BOTTLENECK_COOKIE_SECURE=0
fi

echo
echo "BottleNeck is listening on $BOTTLENECK_HOST:$BOTTLENECK_PORT"
echo "Local: ${scheme}://127.0.0.1:${BOTTLENECK_PORT}"
if command -v hostname >/dev/null 2>&1; then
  for ip in $(hostname -I 2>/dev/null || true); do echo "LAN:   ${scheme}://${ip}:${BOTTLENECK_PORT}"; done
fi
echo "Automatic backups: every ${BOTTLENECK_BACKUP_INTERVAL_HOURS}h; retain ${BOTTLENECK_BACKUP_RETENTION} copies."
echo "Keep the service on a trusted network; do not port-forward it directly to the public internet."
exec uv "${args[@]}"
