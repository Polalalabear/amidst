#!/bin/bash
# 即時N6模式；獨立埠，advisor固定off，不讀API key。
# 請在自己的 clone 執行；uv cache 預設寫入該 clone，勿在 pin 住的 checkout 執行。
set -euo pipefail
LIVE_REPO="$(cd "$(dirname "$0")" && pwd -P)"
LIVE_PYTHON="${PYTHON:-$LIVE_REPO/.venv/bin/python}"
[[ -x "$LIVE_PYTHON" ]] || { echo "缺少Python環境：$LIVE_PYTHON；請先uv sync或用PYTHON指定。" >&2; exit 1; }
export PYTHONPATH="$LIVE_REPO/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
export UV_CACHE_DIR="${UV_CACHE_DIR:-$LIVE_REPO/.local/demo-cache/uv}"
cd "$LIVE_REPO"
exec uv run --offline --no-project --python "$LIVE_PYTHON" python -B scripts/start_live_mode.py "$@"
