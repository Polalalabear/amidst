#!/bin/bash
set -euo pipefail
launcher_repo="$(cd "$(dirname "$0")" && pwd -P)"
launcher_common="$(git -C "$launcher_repo" rev-parse --git-common-dir)"
[[ "$launcher_common" = /* ]] || launcher_common="$launcher_repo/$launcher_common"
# D171: OFFICE_ASSETS_REPO, else local/archive/office-canonical, else the Git common dir.
if [[ -n "${OFFICE_ASSETS_REPO:-}" ]]; then
  launcher_assets="$OFFICE_ASSETS_REPO"
elif [[ -d "$launcher_repo/local/archive/office-canonical" ]]; then
  launcher_assets="$launcher_repo/local/archive/office-canonical"
else
  launcher_assets="$(cd "$launcher_common/.." && pwd -P)"
fi
launcher_evidence="${OFFICE_EVIDENCE_REPO:-$launcher_assets/.local-worktrees/phase1-finalization}"
launcher_evidence="$(cd "$launcher_evidence" && pwd -P)"
export OFFICE_EVIDENCE_REPO="$launcher_evidence"
launcher_python="${OFFICE_PYTHON:-$launcher_repo/.venv/bin/python}"   # 由 scripts/setup_env.sh 建立
if [[ ! -x "$launcher_python" ]]; then
  echo "缺少 Python：$launcher_python；請先執行 scripts/setup_env.sh。" >&2
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
export UV_CACHE_DIR="${TMPDIR:-/tmp}/amidst-office-uv-cache"
exec "$launcher_uv" run --offline --no-project --python "$launcher_python" \
  python "$launcher_repo/scripts/start_office_demo.py" "$@"
