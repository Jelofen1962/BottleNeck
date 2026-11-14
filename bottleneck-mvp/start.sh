#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

command -v uv >/dev/null 2>&1 || { echo "uv was not found. Install it from https://docs.astral.sh/uv/" >&2; exit 1; }

echo "BottleNeck | preparing Python 3.12 environment..."
uv sync --python 3.12
echo "BottleNeck is starting at http://127.0.0.1:8000"
uv run --python 3.12 uvicorn main:app --host 127.0.0.1 --port 8000
