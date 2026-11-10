#!/bin/bash
set -euo pipefail

demo_repo="$(cd "$(dirname "$0")" && pwd)"
if [[ ! -x "$demo_repo/.venv/bin/python" ]]; then
  echo "找不到既有 Python 環境：$demo_repo/.venv/bin/python" >&2
  exit 1
fi
export PYTHONPATH="$demo_repo/src"
exec "$demo_repo/.venv/bin/python" "$demo_repo/scripts/start_local_demo.py" "$@"
