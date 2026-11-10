#!/bin/bash
# 一鍵啟動 2026-11-04 demo 的全部進程（段 A 錄製、段 B live、段 C 複雜事件），印出工作台網址並開瀏覽器。
# 指令與參數照 docs/operations/DEMO_RUNBOOK_20261104.md 第 2、3、4 節；不需要、也不讀取 OpenAI key。
# 可用環境變數覆蓋：P1_BUNDLE、CX7_ROOT、STATE_PARENT、PYTHON、PORT_REC、PORT_LIVE、PORT_CX、NO_OPEN=1
# 結束：在這個視窗按 Ctrl-C，會關掉三個子進程。
set -u
set -m  # 每個子進程各自一個 process group，Ctrl-C 時整組關閉
cd "$(dirname "$0")" || exit 1
ROOT="$PWD"

# D171：預設位置都在本 repo 的 local/ 之下；搬遷前若新位置還不存在，才退回舊位置（過渡用，之後可刪）。
pick() { if [ -e "$1" ] || [ ! -e "$2" ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }
P1_BUNDLE="${P1_BUNDLE:-$(pick "$ROOT/local/archive/p1-clean-room-20261026/Amidst P1 最終測試" "/Users/Shared/amidst-p1-clean-room-20261026/Amidst P1 最終測試")}"
CX7_ROOT="${CX7_ROOT:-$(pick "$ROOT/local/evidence/r004-cx7-d115-20261102-01a199f8" "$HOME/amidst-artifacts/r004-cx7-d115-20261102-01a199f8")}"
STATE_PARENT="${STATE_PARENT:-$(pick "$ROOT/local/data/demo-state" "$HOME/amidst-demo-state")}"
PYTHON="${PYTHON:-python3}"
PORT_REC="${PORT_REC:-8766}"
PORT_LIVE="${PORT_LIVE:-8765}"
PORT_CX="${PORT_CX:-8780}"
MANIFEST_SHA=6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7
SCOPE_SHA=e2ca308b13181346707660a1ae4edcd7b8cc594709a3e009c2db0a9fea3374b8
STAMP="$(date +%H%M%S)"
PIDS=()

die() { echo "錯誤：$*" >&2; exit 1; }

cleanup() {
  trap - INT TERM EXIT
  if [ "${#PIDS[@]}" -gt 0 ]; then
    echo; echo "關閉所有子進程…"
    for p in "${PIDS[@]}"; do kill -TERM -- "-$p" 2>/dev/null || kill -TERM "$p" 2>/dev/null; done
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      alive=0; for p in "${PIDS[@]}"; do kill -0 "$p" 2>/dev/null && alive=1; done
      [ "$alive" = 0 ] && break; sleep 0.5
    done
    for p in "${PIDS[@]}"; do kill -KILL -- "-$p" 2>/dev/null; done
    wait 2>/dev/null
  fi
  echo "已結束。"
}
trap 'exit 130' INT TERM
trap cleanup EXIT

# --- 事前檢查（任何一項不過就停，不啟動任何進程）---
command -v "$PYTHON" >/dev/null 2>&1 || die "找不到 Python：$PYTHON（可用 PYTHON=… 指定，需 ≥3.12）"
command -v node >/dev/null 2>&1 || die "找不到 node"
[ -d "$P1_BUNDLE" ] || die "P1 包不存在：$P1_BUNDLE（可用 P1_BUNDLE=… 覆蓋）"
[ -f "$P1_BUNDLE/MANIFEST.json" ] || die "P1 包缺少 MANIFEST.json：$P1_BUNDLE"
[ -d "$CX7_ROOT" ] || die "複雜事件資料根不存在：$CX7_ROOT（可用 CX7_ROOT=… 覆蓋）"
[ -f "$ROOT/configs/q1q5/p1_live_tracking_scope.json" ] || die "找不到 tracking scope：configs/q1q5/p1_live_tracking_scope.json"
FREE_GIB="$(df -g / | awk 'NR==2{print $4}')"
[ "${FREE_GIB:-0}" -ge 8 ] || die "磁碟可用 ${FREE_GIB:-?} GiB，低於 8 GiB，不啟動"
for spec in "段 A 錄製:$PORT_REC" "段 B live:$PORT_LIVE" "段 C 複雜事件:$PORT_CX"; do
  name="${spec%%:*}"; port="${spec##*:}"
  case "$port" in ''|*[!0-9]*) die "$name 的埠不是整數：$port";; esac
  [ "$port" -ge 1024 ] && [ "$port" -le 65535 ] || die "$name 的埠需在 1024–65535：$port"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    die "[Errno 48] 埠 $port 已被占用（$name）。用 lsof -iTCP:$port -sTCP:LISTEN 看是誰；是自己上一輪的進程就先 Ctrl-C，不認得的程序不要殺；或改用 PORT_REC / PORT_LIVE / PORT_CX 換埠。"
  fi
done
[ "$PORT_REC" != "$PORT_LIVE" ] && [ "$PORT_REC" != "$PORT_CX" ] && [ "$PORT_LIVE" != "$PORT_CX" ] || die "三個埠不能相同"

mkdir -p "$STATE_PARENT" || die "無法建立 state 目錄的父目錄：$STATE_PARENT"
STATE_PARENT="$(cd "$STATE_PARENT" && pwd -P)"   # 絕對、正規路徑（launcher 不接受相對或符號連結）
REC_STATE="$STATE_PARENT/rec-$STAMP"; LIVE_STATE="$STATE_PARENT/live-$STAMP"
LOG_DIR="$STATE_PARENT/logs-$STAMP"; mkdir -p "$LOG_DIR"
export PYTHONDONTWRITEBYTECODE=1
export P1_BUNDLE

# --- 啟動（每個進程各自新的 state 目錄；A 與 B 必須是兩個獨立進程）---
echo "啟動段 A（錄製）埠 $PORT_REC、段 B（live）埠 $PORT_LIVE、段 C（複雜事件）埠 $PORT_CX …"
"$PYTHON" -S scripts/start_q1q5_p1.py --bundle "$P1_BUNDLE" --manifest-sha256 "$MANIFEST_SHA" \
  --state-root "$REC_STATE" --current-ui --no-open --port "$PORT_REC" >"$LOG_DIR/a-rec.log" 2>&1 &
PIDS+=($!)
"$PYTHON" -S scripts/start_q1q5_p1.py --bundle "$P1_BUNDLE" --manifest-sha256 "$MANIFEST_SHA" \
  --state-root "$LIVE_STATE" --tracking-scope "$ROOT/configs/q1q5/p1_live_tracking_scope.json" \
  --tracking-scope-sha256 "$SCOPE_SHA" --current-ui --no-open --port "$PORT_LIVE" >"$LOG_DIR/b-live.log" 2>&1 &
PIDS+=($!)
node frontend/event-viewer/server.mjs --root "$CX7_ROOT" --port "$PORT_CX" >"$LOG_DIR/c-events.log" 2>&1 &
PIDS+=($!)

# --- 等全部 ready（段 C 啟動會全量驗證約 1.2 GB PNG，約 15 秒）---
ready() { curl -fsS -o /dev/null --max-time 2 "http://127.0.0.1:$1$2" 2>/dev/null; }
check_one() {  # 名稱 埠 路徑 pid 日誌
  if ! kill -0 "$4" 2>/dev/null; then
    echo "錯誤：$1 啟動失敗，日誌 $5：" >&2; tail -n 15 "$5" >&2
    grep -q "Errno 48" "$5" 2>/dev/null && echo "（埠 $2 已被占用）" >&2
    return 2
  fi
  ready "$2" "$3"
}
declare -a DONE=(0 0 0)
deadline=$((SECONDS + 180))
while [ "${DONE[0]}${DONE[1]}${DONE[2]}" != "111" ]; do
  [ "$SECONDS" -lt "$deadline" ] || die "等待逾時（180 s）；日誌在 $LOG_DIR"
  i=0
  for spec in "段 A:$PORT_REC:/workbench-v2/:a-rec" "段 B:$PORT_LIVE:/workbench-v2/:b-live" "段 C:$PORT_CX:/api/runs:c-events"; do
    if [ "${DONE[$i]}" = 0 ]; then
      IFS=: read -r n p path log <<<"$spec"
      check_one "$n" "$p" "$path" "${PIDS[$i]}" "$LOG_DIR/$log.log"; rc=$?
      [ "$rc" = 2 ] && exit 1
      [ "$rc" = 0 ] && { DONE[$i]=1; echo "  ✔ $n ready（埠 $p）"; }
    fi
    i=$((i + 1))
  done
  sleep 1
done
grep -h "OK\|UNAVAILABLE\|INTEGRITY" "$LOG_DIR/c-events.log" | sed 's/^/  段 C：/'

URL="http://127.0.0.1:$PORT_REC/workbench-v2/?ev=wall&ev_live=$PORT_LIVE&ev_cx=$PORT_CX"
echo
echo "全部 ready。工作台：$URL"
echo "日誌：$LOG_DIR　state：$REC_STATE、$LIVE_STATE"
echo "結束：在這個視窗按 Ctrl-C。"
[ "${NO_OPEN:-0}" = 1 ] || open "$URL" 2>/dev/null || true

# 任何子進程中途死掉就報錯並收掉其餘進程
while true; do
  for p in "${PIDS[@]}"; do
    kill -0 "$p" 2>/dev/null || { echo "錯誤：子進程 $p 已結束，日誌在 $LOG_DIR" >&2; exit 1; }
  done
  sleep 2
done
