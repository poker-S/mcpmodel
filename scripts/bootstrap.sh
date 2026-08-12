#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple}"
PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-mirrors.aliyun.com}"
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install \
  --index-url "$PIP_INDEX_URL" \
  --trusted-host "$PIP_TRUSTED_HOST" \
  --upgrade pip setuptools wheel
.venv/bin/python -m pip install \
  --index-url "$PIP_INDEX_URL" \
  --trusted-host "$PIP_TRUSTED_HOST" \
  -e '.[dev,model]'

echo "Bootstrap complete: $ROOT/.venv"
echo "Run: source .venv/bin/activate && make check validate test lint"
