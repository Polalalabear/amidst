#!/bin/bash
set -euo pipefail
demo_repo="$(cd "$(dirname "$0")" && pwd -P)"
demo_python="$demo_repo/.venv/bin/python"
[[ -x "$demo_python" ]] || { echo "缺少 checkout 自有 .venv；請依 #486 操作文件建立。" >&2; exit 1; }
# D171：local/demo-pin.json 存在時，HEAD 必須等於 pin 且工作樹乾淨（QA 埠可用 AMIDST_DEMO_ALLOW_UNPINNED=1）；沒有 pin 檔就照常啟動。
python3 "$demo_repo/scripts/demo_pin.py" check || exit 1
export PYTHONPATH="$demo_repo/src"
export PYTHONDONTWRITEBYTECODE=1
export UV_CACHE_DIR="$demo_repo/.local/demo-cache/uv"
# Deploy the existing safe bundle when it is present. An explicit --root-8cam
# in "$@" takes precedence over the checkout's default.
demo_eightcam="$demo_repo/local/data/r004-4actor-natural-walk-eightcam-20261114/bundle/safe"
if [[ -d "$demo_eightcam" ]]; then
  set -- --auto-root-8cam "$demo_eightcam" "$@"
fi
exec uv run --offline --no-project --python "$demo_python" python -B "$demo_repo/scripts/serve_demo_integration.py" "$@"
