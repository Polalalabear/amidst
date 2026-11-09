#!/bin/bash
set -euo pipefail
demo_repo="$(cd "$(dirname "$0")" && pwd -P)"
demo_python="$demo_repo/.venv/bin/python"
[[ -x "$demo_python" ]] || { echo "缺少 checkout 自有 .venv；請依 #486 操作文件建立。" >&2; exit 1; }
export PYTHONPATH="$demo_repo/src"
export PYTHONDONTWRITEBYTECODE=1
export UV_CACHE_DIR="$demo_repo/.local/demo-cache/uv"
exec uv run --offline --no-project --python "$demo_python" python -B "$demo_repo/scripts/serve_demo_integration.py" "$@"
