#!/bin/bash
# D178 session start: one command, from nothing to a ready checkout.
#
#   session_bootstrap.sh NAME [--base origin/main] [--branch claude/NAME] [--dest DIR]
#                             [--source DIR] [--no-templates] [--dry-run]
#
# Steps (each is logged; the script stops at the first failure):
#  1. Disk: free space must be >= 8 GiB, which real-data gates need. Below 5 GiB: STOP (project rule).
#  2. `clone --shared` from the single folder ~/amidst into the scratchpad.
#     Objects are shared through alternates; only the checkout files are written.
#  3. Point origin at GitHub and run `git fetch origin`. This is near-instant, because sync_main.sh has
#     already fetched into ~/amidst. Then branch from --base: origin/main by default, not the demo-pinned
#     local main.
#  4. Templates: env_templates.sh apply (cp -c of .venv and node_modules, then path verification).
#     If this branch's locks have no template yet, build one first; later sessions reuse it.
#     --no-templates skips this step.
#  5. Write session.env with AMIDST_ROOT, AMIDST_DEMO_HOME, UV_CACHE_DIR and PATH (.venv/bin first).
#     Then: source DEST/session.env
#
# Writes only inside DEST, plus local/env-templates when a template has to be built.
# Never touches the ~/amidst working tree.
set -euo pipefail

# ---------- arguments ----------
ROOT="${AMIDST_ROOT:-$HOME/amidst}"
NAME="${1:?usage: session_bootstrap.sh NAME [...]}"
shift
BASE=origin/main
BRANCH="claude/$NAME"
DEST=""
SOURCE="$ROOT"
TPL=1
DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --base)         BASE="$2"; shift 2 ;;
    --branch)       BRANCH="$2"; shift 2 ;;
    --dest)         DEST="$2"; shift 2 ;;
    --source)       SOURCE="$2"; shift 2 ;;   # tests only: clone from another local repo
    --no-templates) TPL=0; shift ;;
    --dry-run)      DRY=1; shift ;;
    *) echo "unknown $1"; exit 2 ;;
  esac
done
SCRATCH="${CLAUDE_SCRATCHPAD:-${TMPDIR:-/tmp}}"
DEST="${DEST:-$SCRATCH/$NAME}"
ORIGIN_URL="$(git -C "$SOURCE" remote get-url origin)"
HERE="$(cd "$(dirname "$0")" && pwd)"

# ---------- helpers ----------
t0=$(date +%s)
step(){ echo "[$(( $(date +%s) - t0 ))s] $*"; }
run(){
  if [ $DRY = 1 ]; then
    echo "  DRY: $*"
  else
    "$@"
  fi
}

# ---------- 1. disk ----------
mkdir -p "$SCRATCH"
free=$(df -g "$SCRATCH" | awk 'NR==2{print $4}')
step "disk free ${free} GiB"
if [ "$free" -lt 5 ]; then echo "STOP: free < 5 GiB"; exit 1; fi
if [ "$free" -lt 8 ]; then echo "WARN: free < 8 GiB: real-data gates and template builds will refuse"; fi
if [ -e "$DEST" ]; then echo "STOP: $DEST exists"; exit 1; fi

# ---------- 2. clone ----------
step "clone --shared $SOURCE -> $DEST"
run git clone -q --shared --no-checkout "$SOURCE" "$DEST"

# ---------- 3. origin, fetch, branch ----------
step "origin -> $ORIGIN_URL; fetch; branch $BRANCH from $BASE"
run git -C "$DEST" remote set-url origin "$ORIGIN_URL"
run git -C "$DEST" fetch -q --prune origin
run git -C "$DEST" switch -q -c "$BRANCH" --no-track "$BASE"

# ---------- 4. templates ----------
if [ $TPL = 1 ]; then
  step "templates"
  if [ $DRY = 1 ]; then
    echo "  DRY: env_templates.sh apply $DEST (build first if missing)"
  else
    if ! SRC="$DEST" bash "$HERE/env_templates.sh" check >/dev/null; then
      SRC="$DEST" bash "$HERE/env_templates.sh" build --execute
    fi
    bash "$HERE/env_templates.sh" apply "$DEST"
  fi
fi

# ---------- 5. session.env ----------
step "session.env"
CONTENT="export AMIDST_ROOT='$ROOT'
export AMIDST_DEMO_HOME='$ROOT/local/data/demo-owned-v1'
export UV_CACHE_DIR='$ROOT/.local/demo-cache/uv'
export UV_NO_MANAGED_PYTHON=1
export PATH='$DEST/.venv/bin':\"\$PATH\""
if [ $DRY = 1 ]; then
  echo "$CONTENT" | sed 's/^/  DRY: /'
else
  echo "$CONTENT" > "$DEST/session.env"
  # Keep session.env out of git status.
  echo "/session.env" >> "$DEST/.git/info/exclude"
fi
step "done: cd $DEST && source session.env"
