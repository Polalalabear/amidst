#!/bin/bash
set -euo pipefail
launcher_repo="$(cd "$(dirname "$0")" && pwd -P)"
launcher_evidence="${OFFICE_EVIDENCE_REPO:-$launcher_repo/../amidst/.local-worktrees/phase1-finalization}"
launcher_evidence="$(cd "$launcher_evidence" && pwd -P)"
export OFFICE_EVIDENCE_REPO="$launcher_evidence"
launcher_python="${OFFICE_PYTHON:-$launcher_evidence/.venv/bin/python}"
if [[ ! -x "$launcher_python" ]]; then
  echo "缺少既有 Python：$launcher_python；未建立或安裝依賴。" >&2
  exit 1
fi
launcher_uv="$(command -v uv || true)"
if [[ -z "$launcher_uv" && -x /opt/homebrew/bin/uv ]]; then
  launcher_uv=/opt/homebrew/bin/uv
fi
if [[ -z "$launcher_uv" ]]; then
  echo "缺少 uv；未下載或安裝。" >&2
  exit 1
fi
export PYTHONPATH="$launcher_repo/src"
export PYTHONDONTWRITEBYTECODE=1
export UV_CACHE_DIR="${TMPDIR:-/private/tmp}/amidst-office-uv-cache"
exec "$launcher_uv" run --offline --no-project --python "$launcher_python" \
  python "$launcher_repo/scripts/start_office_demo.py" "$@"
