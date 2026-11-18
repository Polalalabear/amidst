#!/bin/bash
# #601: OpenAI Agent gateway for the 8785 recorded demo. Off unless you export the approval below first, e.g.
#   export OPENAI_API_KEY=...            (not stored anywhere by this script)
#   export AMIDST_API_ENABLED=1 AMIDST_API_MAX_USD_TOTAL=1
# Start the demo itself with AMIDST_RECORDED_AGENT=openai to expose the Agent switch.
set -euo pipefail
demo_repo="$(cd "$(dirname "$0")" && pwd -P)"
demo_python="$demo_repo/.venv/bin/python"
[[ -x "$demo_python" ]] || { echo "缺少 checkout 自有 .venv；請依 #486 操作文件建立。" >&2; exit 1; }
export PYTHONPATH="$demo_repo/src"
export PYTHONDONTWRITEBYTECODE=1
exec "$demo_python" -B "$demo_repo/scripts/openai_agent_gateway.py" "$@"
