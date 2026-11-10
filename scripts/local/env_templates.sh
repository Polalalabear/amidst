#!/bin/bash
# D178 environment templates: a prebuilt .venv and node_modules, copied into each session with
# APFS `cp -c`. That is a copy-on-write clone: about 1.7 s, and about 0 extra disk until a file changes.
#
# Commands:
#   env_templates.sh key                 print the venv and node keys for the current locks
#   env_templates.sh check               is there a template for the current locks? (rc 1 if not)
#   env_templates.sh build [--execute]   build the missing templates (needs network unless the uv cache is warm)
#   env_templates.sh apply DEST          clone the templates into checkout DEST, then verify the paths
#   env_templates.sh prune [--execute]   drop templates whose key matches no lock on ~/amidst
#
# Location: $ROOT/local/env-templates/{venv,node}-<key>/. It sits inside the gitignored local/,
# so a single ignore rule covers it.
#
# Key: the first 16 hex characters of a SHA-256 over the inputs that decide the content.
#   venv: uv.lock, .python-version, pyproject.toml, and the base interpreter path
#   node: tests/browser/core-preview/package-lock.json, package.json, .node-version
#
# Relocation:
#   - The venv is created with `uv venv --relocatable`. pyvenv.cfg gets `relocatable = true`,
#     activate computes VIRTUAL_ENV from its own location, and uv writes relative entry-point
#     shebangs (a trampoline).
#   - build then proves it: no file under bin/ may still name the template path, and no .pth,
#     RECORD or direct_url.json file may contain it. Anything left over is rewritten to uv's
#     relocatable trampoline and checked again.
#   - pyvenv.cfg `home` stays absolute on purpose. It names the owned base interpreter
#     (local/data/demo-owned-v1/runtime/python), which is the same for every session.
#     install_owned_io_guard needs base_prefix under that runtime and sys.prefix == <checkout>/.venv;
#     a copied venv meets both, because Python finds pyvenv.cfg next to the bin/python it was started
#     from (the symlink is not resolved first).
set -euo pipefail

# ---------- configuration ----------
ROOT="${AMIDST_ROOT:-$HOME/amidst}"
OWNED="${AMIDST_DEMO_HOME:-$ROOT/local/data/demo-owned-v1}"
PY="$OWNED/runtime/python/bin/python3.12"
T="$ROOT/local/env-templates"
NODE_PKG=tests/browser/core-preview
export UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT/.local/demo-cache/uv}"
export UV_NO_MANAGED_PYTHON=1

# ---------- helpers ----------

# Template keys for checkout $1.
vkey(){ (cd "$1" && { cat uv.lock .python-version pyproject.toml; echo "$PY"; } | shasum -a 256 | cut -c1-16); }
nkey(){ (cd "$1" && cat "$NODE_PKG/package-lock.json" "$NODE_PKG/package.json" .node-version | shasum -a 256 | cut -c1-16); }

# Remove a directory, but only somewhere under $T or under the destination checkout.
# Guards against an empty or unexpected variable.
safe_rmdir(){
  case "${1:?}" in
    "$T"/*|"${DEST_GUARD:-/nonexistent}"/*) rm -rf -- "$1" ;;
    *) echo "REFUSE rm outside templates: $1"; exit 1 ;;
  esac
}

# List the files in venv $1 that still name path $2.
abs_left(){
  {
    grep -rIl -- "$2" "$1/bin" 2>/dev/null
    grep -rIl --include='*.pth' --include='RECORD' --include='direct_url.json' -- "$2" "$1/lib" 2>/dev/null
  } | sort -u
}

# Rewrite leftover absolute shebangs in venv $1 to uv's relocatable trampoline.
# Also delete activate.csh: even with --relocatable, uv writes the absolute venv path into it
# (seen with uv 0.9.26), and no Amidst launcher or session uses csh.
relocate(){
  local v="$1"
  rm -f -- "${v:?}/bin/activate.csh"
  grep -rIl -- "^#!$v/bin/python" "$v/bin" 2>/dev/null | while read -r f; do
    python3 -I -c '
import sys
f = sys.argv[1]
lines = open(f).read().split("\n", 1)
tramp = "#!/bin/sh\n" + chr(39) * 3 + "exec" + chr(39) + " \"$(dirname -- \"$(realpath -- \"$0\")\")\"/" \
        + chr(39) + "python" + chr(39) + " \"$0\" \"$@\"\n" + chr(39) + " " + chr(39) * 3
open(f, "w").write(tramp + "\n" + (lines[1] if len(lines) > 1 else ""))
' "$f"
  done
}

# Check venv $1: sys.prefix must be $2, path $3 must appear nowhere, and pytest must run.
verify_venv(){
  local v="$1" bad
  "$v/bin/python" -c "import sys; assert sys.prefix == '$2', sys.prefix; assert sys.base_prefix.startswith('$OWNED/runtime'), sys.base_prefix"
  bad=$(abs_left "$v" "$3" || true)
  if [ -n "$bad" ]; then
    echo "ABSOLUTE PATHS LEFT:"
    echo "$bad" | head
    return 1
  fi
  grep -q '^relocatable = true' "$v/pyvenv.cfg"
  "$v/bin/python" -m pytest --version >/dev/null
  if [ -e "$v/bin/pytest" ]; then "$v/bin/pytest" --version >/dev/null; fi
  echo "venv OK: $v"
}

# ---------- commands ----------
cmd="${1:-check}"
shift || true
SRC="${SRC:-$ROOT}"
for f in uv.lock .python-version pyproject.toml .node-version "$NODE_PKG/package-lock.json" "$NODE_PKG/package.json"; do
  if [ ! -f "$SRC/$f" ]; then echo "STOP: $SRC/$f missing (wrong base branch?)"; exit 1; fi
done
VK=$(vkey "$SRC")
NK=$(nkey "$SRC")

case "$cmd" in

key)
  echo "venv-$VK node-$NK"
  ;;

check)
  rc=0
  for d in "venv-$VK" "node-$NK"; do
    if [ -f "$T/$d/TEMPLATE.json" ]; then
      echo "present $d"
    else
      echo "MISSING $d"
      rc=1
    fi
  done
  exit $rc
  ;;

build)
  ex=0
  if [ "${1:-}" = --execute ]; then ex=1; fi
  free=$(df -g "$ROOT" | awk 'NR==2{print $4}')
  if [ "$free" -lt 8 ]; then echo "STOP free ${free} GiB < 8"; exit 1; fi
  mkdir -p "$T"

  # venv template
  if [ -f "$T/venv-$VK/TEMPLATE.json" ]; then
    echo "present venv-$VK"
  else
    echo "build venv-$VK from $SRC (uv sync --frozen --no-install-project; network unless the cache is warm)"
    if [ $ex = 1 ]; then
      tmp="$T/.building-venv-$VK"
      if [ -e "$tmp" ]; then safe_rmdir "$tmp"; fi
      b0=$(date +%s)
      uv venv -q --relocatable --no-project --no-python-downloads --python "$PY" "$tmp"
      (cd "$SRC" && UV_PROJECT_ENVIRONMENT="$tmp" uv sync -q --frozen --no-install-project \
        --link-mode copy --no-python-downloads --python "$tmp/bin/python")
      relocate "$tmp"
      verify_venv "$tmp" "$tmp" "$tmp"
      # Same volume, so this is a rename. The trampolines do not depend on the location.
      mv "$tmp" "$T/venv-$VK"
      verify_venv "$T/venv-$VK" "$T/venv-$VK" "$tmp"
      printf '{"kind":"venv","key":"%s","build_seconds":%s,"uv":"%s","base_python":"%s","uv_lock_sha256":"%s","source_commit":"%s","files":%s,"created":"%s"}\n' \
        "$VK" "$(( $(date +%s) - b0 ))" "$(uv --version)" "$PY" "$(shasum -a 256 "$SRC/uv.lock" | cut -d' ' -f1)" \
        "$(git -C "$SRC" rev-parse HEAD)" "$(find "$T/venv-$VK" -type f | wc -l | tr -d ' ')" \
        "$(date -Iseconds)" > "$T/venv-$VK/TEMPLATE.json"
    fi
  fi

  # node_modules template
  if [ -f "$T/node-$NK/TEMPLATE.json" ]; then
    echo "present node-$NK"
  else
    echo "build node-$NK (npm ci --ignore-scripts)"
    if [ $ex = 1 ]; then
      if [ "$(node --version)" != "v$(cat "$SRC/.node-version")" ]; then
        echo "STOP node != .node-version"
        exit 1
      fi
      tmp="$T/.building-node-$NK"
      if [ -e "$tmp" ]; then safe_rmdir "$tmp"; fi
      mkdir -p "$tmp"
      cp "$SRC/$NODE_PKG/package.json" "$SRC/$NODE_PKG/package-lock.json" "$tmp/"
      npm ci --prefix "$tmp" --ignore-scripts --no-audit --no-fund
      if [ -n "$(find "$tmp/node_modules" -type l -lname '/*')" ]; then
        echo "STOP absolute symlinks in node_modules"
        exit 1
      fi
      mv "$tmp/node_modules" "$T/node-$NK"
      safe_rmdir "$tmp"
      printf '{"kind":"node","key":"%s","node":"%s","lock_sha256":"%s","created":"%s"}\n' \
        "$NK" "$(node --version)" "$(shasum -a 256 "$SRC/$NODE_PKG/package-lock.json" | cut -d' ' -f1)" \
        "$(date -Iseconds)" > "$T/node-$NK/TEMPLATE.json"
    fi
  fi
  ;;

apply)
  D="$(cd "${1:?DEST}" && pwd)"
  DV=$(vkey "$D")
  DN=$(nkey "$D")
  if [ ! -f "$T/venv-$DV/TEMPLATE.json" ]; then
    echo "MISSING venv-$DV for $D: run SRC=$D env_templates.sh build --execute"
    exit 1
  fi
  if [ -e "$D/.venv" ]; then echo "STOP $D/.venv exists"; exit 1; fi

  # The copy keeps TEMPLATE.json. It is harmless, and records which template the venv came from.
  cp -c -R "$T/venv-$DV" "$D/.venv"
  verify_venv "$D/.venv" "$D/.venv" "$T/venv-$DV"

  if [ -f "$T/node-$DN/TEMPLATE.json" ] && [ ! -e "$D/$NODE_PKG/node_modules" ]; then
    cp -c -R "$T/node-$DN" "$D/$NODE_PKG/node_modules"
    echo "node OK"
  else
    echo "node template missing or node_modules exists: skipped"
  fi
  ;;

prune)
  keep="$(SRC=$ROOT bash "$0" key)"
  for d in "$T"/venv-* "$T"/node-*; do
    [ -e "$d" ] || continue
    case " $keep " in
      *" $(basename "$d") "*) ;;
      *)
        if [ "${1:-}" = --execute ]; then
          echo "RUN rm $d"
          safe_rmdir "$d"
        else
          echo "PLAN rm $d"
        fi
        ;;
    esac
  done
  ;;

*)
  echo "usage: $0 key|check|build [--execute]|apply DEST|prune [--execute]"
  exit 2
  ;;

esac
