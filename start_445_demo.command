#!/bin/bash
set -euo pipefail
demo_repo="$(cd "$(dirname "$0")" && pwd -P)"
demo_python="${AMIDST_DEMO_PYTHON:-$HOME/Developer/amidst/.local-worktrees/phase1-finalization/.venv/bin/python}"
export PYTHONPATH="$demo_repo/src"
export PYTHONDONTWRITEBYTECODE=1
export UV_CACHE_DIR="${TMPDIR:-/private/tmp}/amidst-445-uv-cache"
exec uv run --offline --no-project --python "$demo_python" python -B "$demo_repo/scripts/serve_demo_integration.py" "$@"
