#!/usr/bin/env bash
# D163 archive-then-delete for the 25 SAFE items of configs/provenance/artifact_ledger_v1.json.
# DRY-RUN BY DEFAULT: nothing is archived, moved or deleted unless --execute is given.
# Real execution needs the user's separate authorization (#431). This script was only syntax-checked (bash -n), never run.
#
#   bash docs/history/CLEANUP_EXECUTE_D163.sh                      # dry-run: checks + prints the plan
#   bash docs/history/CLEANUP_EXECUTE_D163.sh --execute            # archive, verify the archive, then delete
# Options: --archive-dir DIR  (default ~/amidst-artifacts/_archive_d138)   --repo DIR (default ~/Developer/amidst-q1q5)
#          --ref REF (default mainline/q1q5)   --skip-cache-archive (do not archive the 5 caches; default archives everything)
# Only the explicit paths below are touched: no wildcards, no sudo. Original Blender/video/dataset/calibration/GT assets,
# 8785 (~/amidst-demo-20261104) and demo-owned-v1 are not in the list and are only read (lsof, curl).
set -euo pipefail

EXECUTE=0; SKIP_CACHE_ARCHIVE=0
ARCHIVE_DIR="$HOME/amidst-artifacts/_archive_d138"
REPO="$HOME/Developer/amidst-q1q5"; REF="mainline/q1q5"
EXPECT_8785_PID="${EXPECT_8785_PID:-21060}"
while [ $# -gt 0 ]; do
  case "$1" in
    --execute) EXECUTE=1 ;;
    --archive-dir) ARCHIVE_DIR="$2"; shift ;;
    --repo) REPO="$2"; shift ;;
    --ref) REF="$2"; shift ;;
    --skip-cache-archive) SKIP_CACHE_ARCHIVE=1 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

ITEMS=(
  "CACHE-npm|~/.npm|cache"
  "LOC-fin-pytest_cache|~/Developer/amidst/.local-worktrees/phase1-finalization/.pytest_cache|cache"
  "LOC-fin-ruff_cache|~/Developer/amidst/.local-worktrees/phase1-finalization/.ruff_cache|cache"
  "LOC-main-pytest_cache|~/Developer/amidst/.pytest_cache|cache"
  "LOC-main-ruff_cache|~/Developer/amidst/.ruff_cache|cache"
  "UNT-configs--q1q5|~/Developer/amidst/configs/q1q5|dup"
  "UNT-docs--engineering--Q1Q5_BASELINE_ACCEPTANCE.md|~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_ACCEPTANCE.md|dup"
  "UNT-docs--engineering--Q1Q5_BASELINE_DECISIONS.md|~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_DECISIONS.md|dup"
  "UNT-docs--engineering--Q1Q5_BASELINE_RUNNER.md|~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_RUNNER.md|dup"
  "UNT-docs--engineering--Q1Q5_BASELINE_V1_PROTOCOL.md|~/Developer/amidst/docs/engineering/Q1Q5_BASELINE_V1_PROTOCOL.md|dup"
  "UNT-docs--engineering--Q1Q5_LINKED_ACCEPTANCE.md|~/Developer/amidst/docs/engineering/Q1Q5_LINKED_ACCEPTANCE.md|dup"
  "UNT-docs--engineering--Q1Q5_PRODUCTION_PREPARATION.md|~/Developer/amidst/docs/engineering/Q1Q5_PRODUCTION_PREPARATION.md|dup"
  "UNT-docs--engineering--Q1Q5_REVIEWED_INPUTS.md|~/Developer/amidst/docs/engineering/Q1Q5_REVIEWED_INPUTS.md|dup"
  "UNT-docs--evaluation|~/Developer/amidst/docs/evaluation|dup"
  "UNT-docs--history--Q1Q5_BASELINE_PREPARATION_RECEIPT_20261024.json|~/Developer/amidst/docs/history/Q1Q5_BASELINE_PREPARATION_RECEIPT_20261024.json|dup"
  "UNT-docs--history--Q1Q5_LINKED_ACCEPTANCE_20261024.json|~/Developer/amidst/docs/history/Q1Q5_LINKED_ACCEPTANCE_20261024.json|dup"
  "UNT-scripts--accept_q1q5_linked_baseline.py|~/Developer/amidst/scripts/accept_q1q5_linked_baseline.py|dup"
  "UNT-scripts--build_q1q5_pinned_index.py|~/Developer/amidst/scripts/build_q1q5_pinned_index.py|dup"
  "UNT-scripts--import_q3_minimum_review.py|~/Developer/amidst/scripts/import_q3_minimum_review.py|dup"
  "UNT-scripts--measure_q1q5_dynamic_rgb.py|~/Developer/amidst/scripts/measure_q1q5_dynamic_rgb.py|dup"
  "UNT-scripts--preflight_q1q5_production.py|~/Developer/amidst/scripts/preflight_q1q5_production.py|dup"
  "UNT-scripts--prepare_q1q5_baseline_source.py|~/Developer/amidst/scripts/prepare_q1q5_baseline_source.py|dup"
  "UNT-scripts--replay_q1q5_dynamic_evidence.py|~/Developer/amidst/scripts/replay_q1q5_dynamic_evidence.py|dup"
  "UNT-scripts--run_q1q5_linked_baseline.py|~/Developer/amidst/scripts/run_q1q5_linked_baseline.py|dup"
  "UNT-src--amidst--evaluation--q3_review_import.py|~/Developer/amidst/src/amidst/evaluation/q3_review_import.py|dup"
)
LEDGER="$REPO/configs/provenance/artifact_ledger_v1.json"
TOOL="$REPO/scripts/artifact_ledger.py"
log() { printf '[%s] %s\n' "$(date +%T)" "$*"; }
die() { echo "ABORT: $*" >&2; exit 1; }
expand() { printf '%s' "${1/#\~/$HOME}"; }
ids_csv() { local out="" i; for i in "${ITEMS[@]}"; do out+="${i%%|*},"; done; printf '%s' "${out%,}"; }

# ---- 0. preconditions (always run) -------------------------------------------------------------
[ -f "$LEDGER" ] && [ -f "$TOOL" ] || die "ledger or tool missing under $REPO"
git -C "$REPO" rev-parse --verify -q "$REF" >/dev/null || die "ref $REF not found in $REPO"
free_kb=$(df -k "$HOME" | awk 'NR==2{print $4}'); [ "$free_kb" -ge $((5*1024*1024)) ] || die "free disk below 5 GiB"
pid_before=$(lsof -nP -iTCP:8785 -sTCP:LISTEN -t | head -1 || true)
[ "$pid_before" = "$EXPECT_8785_PID" ] || die "8785 is not served by PID $EXPECT_8785_PID (got '${pid_before:-none}')"
[ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8785/)" = "200" ] || die "8785 does not answer HTTP 200"
log "ledger verify (size, file count, SHA-256/manifest of all SAFE items)"
python3 "$TOOL" validate --ledger "$LEDGER" >/dev/null || die "ledger validate failed"
python3 "$TOOL" verify --ledger "$LEDGER" --only "$(ids_csv)" || die "MISMATCH: an item changed since D163; re-run the gate"

log "lsof sample x3 (nothing may have the items open)"
for n in 1 2 3; do
  snap=$(lsof -nP 2>/dev/null)
  for i in "${ITEMS[@]}"; do
    p=$(expand "$(echo "$i" | cut -d'|' -f2)")
    c=$(printf '%s\n' "$snap" | grep -cF -- "$p" || true)
    [ "$c" = "0" ] || die "$p is open by a process (lsof hits: $c)"
  done
  cwdhits=$(printf '%s\n' "$snap" | grep ' cwd ' | grep -cE "$HOME/Developer/amidst(/|\$| )" || true)
  [ "$cwdhits" = "0" ] || die "a process has its cwd in ~/Developer/amidst"
  [ "$n" = 3 ] || sleep 5
done

log "byte-identity of duplicate copies against $REF"
check() {  # every file under $1 (relative to ~/Developer/amidst) must equal the blob in $REF
  local rel="$1" f
  while IFS= read -r f; do
    [ "$(git hash-object -- "$HOME/Developer/amidst/$f")" = "$(git -C "$REPO" rev-parse "$REF:$f" 2>/dev/null)" ] || die "DIFFERS from $REF: $f"
    ! git -C "$HOME/Developer/amidst" ls-files --error-unmatch -- "$f" >/dev/null 2>&1 || die "tracked in ~/Developer/amidst: $f"
  done < <(cd "$HOME/Developer/amidst" && find "$rel" -type f ! -name .DS_Store)
}
for i in "${ITEMS[@]}"; do
  kind=$(echo "$i" | cut -d'|' -f3); p=$(echo "$i" | cut -d'|' -f2)
  [ "$kind" = dup ] && check "${p#\~/Developer/amidst/}"
done
log "all preconditions passed"

# ---- plan ---------------------------------------------------------------------------------------
STAMP=$(date +%Y%m%d)
ARCHIVE="$ARCHIVE_DIR/d163_safe_items_$STAMP.tar.gz"
REL_LIST=()
for i in "${ITEMS[@]}"; do
  kind=$(echo "$i" | cut -d'|' -f3); p=$(expand "$(echo "$i" | cut -d'|' -f2)")
  if [ "$kind" = cache ] && [ "$SKIP_CACHE_ARCHIVE" = 1 ]; then continue; fi
  REL_LIST+=("${p#$HOME/}")
done
echo "plan: archive ${#REL_LIST[@]} paths -> $ARCHIVE ; then delete ${#ITEMS[@]} paths:"
for i in "${ITEMS[@]}"; do echo "  rm  $(expand "$(echo "$i" | cut -d'|' -f2)")"; done
if [ "$EXECUTE" != 1 ]; then log "DRY-RUN: nothing was changed. Re-run with --execute after the user's authorization."; exit 0; fi

# ---- 1. archive (never deletes) -----------------------------------------------------------------
mkdir -p "$ARCHIVE_DIR"; [ ! -e "$ARCHIVE" ] || die "$ARCHIVE already exists"
tar -C "$HOME" -czf "$ARCHIVE" -- "${REL_LIST[@]}"
( cd "$ARCHIVE_DIR" && shasum -a 256 "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE").sha256" )
log "archive written: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1)); sha256 in $ARCHIVE.sha256"

# ---- 2. verify the archive by extracting and comparing every file with the original -------------
TMP=$(mktemp -d "${TMPDIR:-/tmp}/d163-verify-XXXXXX")
tar -C "$TMP" -xzf "$ARCHIVE"
for rel in "${REL_LIST[@]}"; do
  diff -r -- "$HOME/$rel" "$TMP/$rel" >/dev/null || die "archive differs from original: $rel (nothing deleted)"
done
rm -r -- "$TMP"
log "archive verified against the originals"

# ---- 3. delete exactly the listed paths ---------------------------------------------------------
for i in "${ITEMS[@]}"; do
  p=$(expand "$(echo "$i" | cut -d'|' -f2)")
  [ -e "$p" ] || { log "already gone: $p"; continue; }
  rm -r -- "$p"; log "deleted $p"
done

# ---- 4. post-check ------------------------------------------------------------------------------
python3 "$TOOL" verify --ledger "$LEDGER" --only "$(ids_csv)" --skip-missing || true
pid_after=$(lsof -nP -iTCP:8785 -sTCP:LISTEN -t | head -1 || true)
[ "$pid_after" = "$pid_before" ] || die "8785 PID changed ($pid_before -> $pid_after)"
[ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8785/)" = "200" ] || die "8785 no longer answers HTTP 200"
log "done. 8785 PID $pid_after unchanged, HTTP 200. Restore: tar -C \"\$HOME\" -xzf \"$ARCHIVE\""
