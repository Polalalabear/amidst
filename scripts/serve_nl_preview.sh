#!/usr/bin/env bash
# Serve the SYNTHETIC preview (new UI + Epic D path (b) sentence box) at http://127.0.0.1:${PORT:-8765}/workbench-v2/
# Synthetic data only: the sentence box is answered by the real nl_options parser replaying the SYNTHETIC_FIXTURE recording.
# Needs: python3 (>=3.12), node, a CLEAN checkout (the preview server refuses a dirty tree). No model, no key, no network.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${AMIDST_NL_VENV:-${TMPDIR:-/tmp}/amidst-nl-preview-venv}"
PORT="${PORT:-8765}"
cd "$ROOT"
[ -z "$(git status --porcelain)" ] || { echo "checkout is not clean; commit or discard changes first" >&2; exit 1; }
if [ ! -x "$VENV/bin/python" ]; then python3 -m venv "$VENV"; "$VENV/bin/pip" install -q -e "$ROOT"; fi
export AMIDST_PYTHON="$VENV/bin/python" CORE_INTEGRATION_HEAD="$(git rev-parse HEAD)"
exec node tests/browser/core-preview/preview-server.mjs --source="$ROOT" --port="$PORT"
