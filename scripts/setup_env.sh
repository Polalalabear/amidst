#!/usr/bin/env bash
# One-step environment setup (D133): Python 3.12 venv from uv.lock + locked node dependencies.
# Usage: scripts/setup_env.sh        (run from anywhere; operates on the repo root)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
WANT="$(tr -d '[:space:]' < .python-version)"   # "3.12"

command -v uv >/dev/null 2>&1 || { echo "ERROR: uv not found. Install it from https://docs.astral.sh/uv/" >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: node not found (Node.js 20+ required)." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm not found." >&2; exit 1; }

uv python install "$WANT"
# Recreate the venv when it was built with another Python.
if [ -x .venv/bin/python ]; then
  HAVE="$(.venv/bin/python -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
  if [ "$HAVE" != "$WANT" ]; then
    echo "Existing .venv uses Python $HAVE, expected $WANT; recreating it."
    rm -rf .venv
  fi
fi
# --frozen: install exactly what uv.lock pins and never rewrite the lock file.
uv sync --frozen --python "$WANT" --extra product

GOT="$(.venv/bin/python -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
if [ "$GOT" != "$WANT" ]; then
  echo "ERROR: .venv is Python $GOT, expected $WANT." >&2
  exit 1
fi

# Node dependencies pinned by each package-lock.json (playwright-core downloads no browser).
for dir in frontend/workbench frontend/product tests/browser/core-preview; do
  (cd "$dir" && npm ci --no-audit --no-fund)
done

echo "OK: Python $GOT in .venv, node dependencies installed."
echo "Run tests with: .venv/bin/pytest tests/q1q5"
