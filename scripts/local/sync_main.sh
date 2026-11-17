#!/bin/bash
# D178: keep ~/amidst fresh. It is the single folder and the source of every session's `clone --shared`.
# launchd runs this every 10 min (com.amidst.sync-main.plist). Log: ~/amidst/local/logs/sync-main.log
#
#  1. Always `git fetch --prune origin`. New objects land in ~/amidst/.git, so every --shared clone
#     (its alternates point here) gets them for free, and session_bootstrap's own fetch is near-instant.
#  2. Fast-forward the local `main` only when all of these hold; otherwise log SKIP with the reason:
#     - the checkout is on branch main;
#     - there are no tracked or untracked (non-ignored) changes;
#     - no merge or rebase is in progress;
#     - a fast-forward is possible (never merge, never reset);
#     - demo pin guard: when local/demo-pin.json exists, a fast-forward would move HEAD away from the
#       approved 8785 version. 8785 serves frontend files live from this tree, and
#       start_445_demo.command refuses an unpinned HEAD. So with a pin present the fast-forward is
#       skipped unless AMIDST_SYNC_FF_PINNED=1.
#     Sessions never need this fast-forward: bootstrap checks out origin/main, which step 1 fetched.
set -u
ROOT="${AMIDST_ROOT:-$HOME/amidst}"
LOGDIR="$ROOT/local/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/sync-main.log"
log(){ echo "$(date -Iseconds) $*" >>"$LOG"; }
g(){ git -C "$ROOT" "$@"; }

# Only one run at a time. If the previous run is still going, skip this one.
exec 9>"$LOGDIR/.sync-main.lock"
/usr/bin/lockf -t 0 9 2>/dev/null || { log "SKIP locked"; exit 0; }

# Step 1: fetch.
if ! out=$(g fetch --prune --quiet origin 2>&1); then
  log "FAIL fetch: ${out//$'\n'/ }"
  exit 1
fi
head=$(g rev-parse --short HEAD)
remote=$(g rev-parse --short origin/main)

# Step 2: fast-forward main, if every guard passes.
if [ "$(g branch --show-current)" != main ]; then
  log "SKIP not-on-main head=$head origin/main=$remote"
  exit 0
fi
if [ -n "$(g status --porcelain)" ]; then
  log "SKIP local-changes head=$head origin/main=$remote"
  exit 0
fi
if [ -e "$(g rev-parse --git-path MERGE_HEAD)" ] || [ -d "$(g rev-parse --git-path rebase-merge)" ]; then
  log "SKIP merge-or-rebase-in-progress"
  exit 0
fi
if [ "$(g rev-parse HEAD)" = "$(g rev-parse origin/main)" ]; then
  log "OK up-to-date $head"
  exit 0
fi
if ! g merge-base --is-ancestor HEAD origin/main; then
  log "SKIP not-fast-forward head=$head origin/main=$remote"
  exit 0
fi
if [ -f "$ROOT/local/demo-pin.json" ] && [ "${AMIDST_SYNC_FF_PINNED:-0}" != 1 ]; then
  log "SKIP demo-pinned head=$head origin/main=$remote (fetched; a fast-forward needs the gate and demo_pin.py approve)"
  exit 0
fi
if out=$(g merge --ff-only --quiet origin/main 2>&1); then
  log "FF $head -> $remote"
else
  log "FAIL ff: ${out//$'\n'/ }"
  exit 1
fi
