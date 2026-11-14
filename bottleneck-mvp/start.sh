#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v uv >/dev/null 2>&1 || { echo "uv was not found. Install it from https://docs.astral.sh/uv/" >&2; exit 1; }
export BOTTLENECK_PORT=1939
echo "BottleNeck v0.4.0 | preparing Python 3.12 environment..."
uv sync --python 3.12
echo
echo "BottleNeck is listening on 0.0.0.0:1939"
echo "Local: http://127.0.0.1:1939"
if command -v hostname >/dev/null 2>&1; then
  for ip in $(hostname -I 2>/dev/null || true); do echo "LAN:   http://${ip}:1939"; done
fi
echo "Keep this server on a trusted LAN; do not expose it directly to the public internet."
exec uv run --python 3.12 uvicorn main:app --host 0.0.0.0 --port 1939
