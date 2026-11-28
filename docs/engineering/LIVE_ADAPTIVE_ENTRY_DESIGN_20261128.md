# LIVE #789 adaptive 排程的圖外鏡頭覆蓋

2026-11-28，D415 設計獲附條件核准，實作見 Draft #794。設計基線 `f18304d735b6d6855f0f24a69f330398b11d76f9`。關聯 [#589 的 R-4／R-6](../specs/LIVE_MODE_RELOCK_V1.md#6-可測驗收) 與 [D273 量測](../evaluation/LIVE_DETECTION_SCHEDULE_D273_20261118.md)。

## tick 62 根因與驗收範圍

D273 live 原始 `adaptive-A4.t1raw.json` 在 tick 59–65 是 `LOST`（lost 20–26），走 `LOST_ALL` 全掃 8 台。當時已掃到 ENTRY，tick 62 有 1 筆偵測，tick 63 有 3 筆。

漏掃只在以 relock fallback 重播同一凍結來源時出現。重播 tick 61 結束仍為 `TRACKING`、active `CAM_W2`、lost=0。tick 62 的半徑 `1 + 0 // 1 = 1`，計畫為 `CAM_W2` 加 `CAM_BRANCH`、`CAM_EXT_CAR`、`CAM_EXT_CLEAR`、`CAM_R101_IN`、`CAM_W1`、`CAM_WIDE`。兩秒內的同色候選記憶只有 `CAM_W1`、`CAM_W2`，兩台皆已入選。圖外的 `CAM_ENTRY` 在 tick 63 擴到兩跳仍未被排到，tick 64 的 `lost=2` 走 `LOST_ALL` 才掃回。

本項驗收為 adaptive／fallback 在 `lost<2`（D273 的 `expand_every=1`）的圖內分支也會排到唯一可用的圖外鏡頭，並用實際上傳的 JPEG 做推論。原重播歷史含一次自動錯接；追蹤估計偏離、R-4 正確候選與 R-5 自動錯接由 #589 追蹤。補掃後的 ENTRY 投影距 adaptive 前一估計 14.04 m，該群代表距 13.58 m，超出現行 8 m fallback 搜尋半徑。全掃參照有不同的追蹤歷史，ENTRY 投影距其前一估計 4.68 m，呈現合格的 `NEEDS_CONFIRM` 群（代表鏡頭為 `CAM_W2`）。

## 實作與閉環

`CameraScheduler` 的 keyword-only 選項 `cover_single_uncovered_camera` 預設 `False`，LIVE `State` 只在 `--relock fallback` 開啟。圖內鄰域分支先合併既有鄰域與近期同色記憶，再按 graph 節點成員判斷。可用清單由伺服器取 registered 與 A 申報 available 的交集。去重後恰有一台圖外鏡頭就納入，按原 available 順序輸出。零台或兩台以上時不補，即使其中一台已在近期候選清單。全掃分支依原規則處理。

`State.infer` 只推論當前計畫與收到的 JPEG 的交集。追蹤及 `observe` 後送出 `next_camera_ids`，A 依此清單進行下一輪擷取。缺 JPEG 或凍結來源沒拍到的畫面仍為 `MISSING`。現有 schedule keys 和 reason enum 沿用；實際新增的計畫鏡頭只在離線 `replay_safe` 的 `trace.supplemented_camera_ids` 記錄。LIVE CLI 預設 `--relock off`，重播用同一個內部參數選擇比較組。

`test_scheduler.py` 固定單一、零、兩台圖外、順序去重，以及全掃和預設關閉的序列化計畫。`test_track_endpoints.py` 驗證 registered∩available、前一個回應指示下一輪上傳的 JPEG 確實到達假 detector，以及缺 JPEG 時的缺觀測。`test_relock_replay.py` 驗證補掃記錄只在 trace，原有 GT 隔離測試維持通過。Node schedule／protocol 測試核對 A→B 欄位。

## 凍結重播

兩個 adaptive 臂皆使用 `RelockConfig()`，只切換排程選項。延遲從再入鏡 capture 起算，`null` 表示 episode 內沒有合格結果。GT 在決策完成後才由 `score_replays` 及 `entry_audit` 用於評分。

| 來源／排程 | ENTRY tick | 首次排到 ENTRY | ENTRY tick 計畫台數 | 該 tick 處理 ENTRY 偵測 | 正確候選 ms | 正確自動接回 ms | 全段自動錯接 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 69-tick adaptive-A4／現行 adaptive | 62 | 64 | 7 | 0／1 | null | null | 1 |
| 同來源／補掃 adaptive | 62 | 62 | 8 | 1／1 | null | null | 1 |
| 同來源／現行全掃參照 | 62 | 62 | 8 | 1／1 | 0 | null | 2 |
| 60-tick all-A4／現行與補掃 adaptive | 52 | 52 | 8 | 1／1 | 0 | null | 2 |

| 來源 | 計畫的相機影格數，現行 → 補掃 | 已處理的相機影格數，現行 → 補掃 | 跟對／失聯（前後相同） |
| --- | ---: | ---: | --- |
| 69-tick adaptive-A4 | 472 → 521 | 415 → 437 | 43/69、13/69 |
| 60-tick all-A4 | 411 → 431 | 411 → 431 | 7/60、29/60 |
| 固定 RGB A4 | 297 → 369 | 297 → 369 | 67/95、4/95 |
| 固定 RGB B4 | 243 → 243 | 243 → 243 | 58/60、1/60 |

補掃在 tick 62 處理 ENTRY 觀測。R-4 正確候選仍缺，R-6 整體驗收仍開啟。固定 A4 來源共有四台鏡頭，另一份 69-tick A4 有八台；兩者各自的計畫增幅為 24.2% 和 10.4%。

## D273 無頭 A→B 量測

在 Mac Apple M3、Torch 2.6.0 的 MPS 搭配真 RT-DETR，序列各跑一次 A4。八台，320×180，要求 5 fps，50 s 路線、58 s 量測，一般偵測門檻 0.15、ENTRY 0.05。兩組都從 fallback 啟動，只有補掃開關不同。使用原 `measure/latency.mjs` 配對 A capture 和 B display，首四個 display ticks 依 D273 方法排除於穩態統計。新 A 頁面的 reset 會回 IDLE，量測 server 在同一 session 呼叫與 B 紅色按鈕相同的 `State.track_start`，讓兩組皆進入追蹤。advisor 關閉，費用 USD 0。

| 58 s 量測 | B 顯示 tick／穩態 n | 穩態偵測台數分布（台數×tick） | 平均台數 | Capture→B p50／p95 ms | 實際輪/s | 協定違規 |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| 現行 | 52／48 | 3×5、4×1、5×6、6×1、7×35 | 6.25 | 815.6／1325.3 | 1.020 | 0 |
| 補掃 | 48／44 | 4×6、6×4、8×34 | 7.27 | 1047.3／1585.6 | 0.893 | 0 |

全段圖內分支實際偵測 ENTRY 為現行 0/52、補掃 46/46（lost=0 有 45 個、lost=1 有 1 個）。每個顯示 tick 的實際偵測相機、相機數、detector 時間與 capture→B 延遲列在兩份 `*.ticks.json`。這是各一次、不同 capture 時點的描述性量測；p50 增加 231.7 ms，p95 增加 260.3 ms。此結果供 Claude 判斷補掃成本；fallback 是否採用或改成週期掃描留待另定。兩組瀏覽器關閉時各有一筆仍在途的請求產生 BrokenPipe，兩個 runner 均 exit 0，owned server 正常關閉。

## 來源與可重跑指令

在獨立 scratchpad clone 執行 `npm ci --prefix frontend/live-mode`。D273 評分與 latency runner 都載入 `puppeteer-core`。錄製、模型與校正取既有唯讀 LOCAL 來源。首次使用的輸出路徑以 `AMIDST_ARTIFACTS` 指定。

| LOCAL 來源或產物 | Bytes／檔數 | SHA-256 | 重建 |
| --- | ---: | --- | --- |
| `local/evidence/cx552-d-20261118/fresh/latency/adaptive-A4.t1raw.json` | 212,476／1 | `f3fce7d92315b22247f29cdf55182d5c95bf242150f7d3cd1a6e20e8774c1c69` | D273 凍結來源 |
| `local/evidence/cx552-d-20261118/fresh/latency/all-A4.t1raw.json` | 207,268／1 | `308de2c315b5e2ac696d194a9a357ca98c1a01a26fe126b346c08dfbac74d003` | D273 凍結來源 |
| `local/evidence/cx552-d-20261118/baseline-fixed/all/fixed__a4_route_baseline.t1raw.json` | 178,954／1 | `e2e0547748cd242da6d84a404235a4cf108be91cac3de0e7e96af2779fe574be` | D273 凍結來源 |
| `local/evidence/cx552-d-20261118/baseline-fixed/all/fixed__b4_route_baseline.t1raw.json` | 164,669／1 | `984481f8b6e1372507d3a6dd8f950e555b7da921ed06ae214d6eb93c3ee79483` | D273 凍結來源 |
| `local/data/live-assets-20261115/cameras.catalog.json` | 12,793／1 | `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f` | 直接讀取 |
| `local/data/live-assets-20261115/MANIFEST.json` | 10,272／1 | `d92aa7453f13903252b306b42249239168561766677a5180a85afcc4dbff7b29` | 直接讀取 |
| `local/data/demo-owned-v1/models/rtdetr/rtdetr_r18vd_dec3_6x_coco_from_paddle.pth` | 81,001,853／1 | `3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0` | 直接讀取 |
| `$AMIDST_ARTIFACTS/789-native-replay.jsonl` | 3,069／1 | `40d5741919924168600dca9c2bd1e3ce917262ea5a2b0a50c3cf678cb5c368c7` | 下列凍結重播 |
| `$AMIDST_ARTIFACTS/current.ticks.json` | 26,987／1 | `efaf29468dc20226ca44a0a1bf0053442472467506074f9cc2dd3532644a859e` | 下列 MPS 量測，時鐘依每次執行而異 |
| `$AMIDST_ARTIFACTS/supplement.ticks.json` | 26,599／1 | `4296c8a95d83815a578cfdb7aa3a1c5b94af440797291fb1f3e25172070a1885` | 同上 |
| `$AMIDST_ARTIFACTS/summary.json` | 1,966／1 | `1f9e67109db802a9378720b150e1eb78dd1e59919887f4d4a1859f935c456622` | 同上 |
| `$AMIDST_ARTIFACTS/MANIFEST.sha256` | 851／1，涵蓋 10 檔 | `fc6180534ed688712689ea196861b39c8dfcf86e9080fc3050ed396d06558175` | 由本次執行輸出產生 |

鏡頭圖 SHA-256 `9896be113bf6e2b5f2d9344f1227484674fda2c2bb983d32a70d8ffcc4adfc7e`。本次瀏覽器量測的 scheduler SHA-256 `ded74e7da205200c506cc09ce4933ea6652faf83414e4de321ffddd0847020a8`，server SHA-256 `c872dc6ebf3063a567ef744561b853644c1844524519efda0c8e45a07357a598`。

### 凍結重播

`EVIDENCE` 指向唯讀 LOCAL evidence 根，`DATA` 指向唯讀 LOCAL data 根，輸出目錄先建立。

```sh
PYTHONPATH=src:scripts/live_mode "$PYTHON" -B - "$EVIDENCE/cx552-d-20261118" \
  "$DATA/live-assets-20261115/cameras.catalog.json" > "$AMIDST_ARTIFACTS/789-native-replay.jsonl" <<'PY'
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from replay_relock import (
    RelockConfig, entry_audit, episodes, inventory_file, observation_records,
    recovery_counts, replay_safe, score_replays,
)
from amidst.live_mode.scheduler import DEFAULT_GRAPH, DEFAULT_GRAPH_SHA256, load_graph
from amidst.live_mode.tracker import Projector, load_cameras

root, catalog = map(Path, sys.argv[1:])
paths = {
    "adaptive-A4": "fresh/latency/adaptive-A4.t1raw.json",
    "all-A4": "fresh/latency/all-A4.t1raw.json",
    "fixed-A4": "baseline-fixed/all/fixed__a4_route_baseline.t1raw.json",
    "fixed-B4": "baseline-fixed/all/fixed__b4_route_baseline.t1raw.json",
}
entries = [(label, root / path, json.loads((root / path).read_bytes())) for label, path in paths.items()]
projector = Projector(load_cameras(str(catalog)))
graph, _ = load_graph(DEFAULT_GRAPH, DEFAULT_GRAPH_SHA256, inventory_file(catalog)["sha256"], list(projector.cams))
observations = [observation_records(raw) for _, _, raw in entries]
for label, mode, enabled in (("current", "adaptive", False), ("supplement", "adaptive", True), ("all", "all", False)):
    traces = []
    for (_, _, raw), records in zip(entries, observations, strict=True):
        cfg = raw["cfg"]
        traces.append(replay_safe(records, cfg["cams"], (cfg["w"], cfg["h"]), projector, graph,
                                  mode=mode, config=RelockConfig(), cover_single_uncovered_camera=enabled))
    with TemporaryDirectory() as output:
        rows, rates = score_replays(entries, traces, Path(output))
    audit = entry_audit(entries, traces, rows)
    intervals = {name: episodes(run) for name, run in rows.items()}
    recoveries = recovery_counts(dict(zip(paths, traces, strict=True)), rows, intervals)
    for (name, _, _), trace in zip(entries, traces, strict=True):
        n = rates[name]["target_visible_ticks"]
        entry = []
        for episode in audit[name]:
            i = episode["entry_tick"]
            entry.append({
                "tick": i,
                "first_planned": next((j for j in range(i, len(trace))
                                       if "CAM_ENTRY" in trace[j]["schedule"]["camera_ids"]), None),
                "cameras_planned_at_entry": len(trace[i]["schedule"]["camera_ids"]),
                "entry_detections": len(trace[i]["dets"].get("CAM_ENTRY", ())),
                "supplemented": trace[i]["trace"].get("supplemented_camera_ids", []),
                "candidate_delay_ms": episode["candidate_delay_ms"], "auto_delay_ms": episode["auto_delay_ms"],
            })
        print(json.dumps({
            "arm": label, "source": name, "entry": entry,
            "visible": n, "on_target": round(n * rates[name]["on_target"]), "lost": round(n * rates[name]["lost"]),
            "planned_camera_frames": sum(len(row["schedule"]["camera_ids"]) for row in trace),
            "processed_camera_frames": sum(len(row["dets"]) for row in trace),
            "wrong_auto": recoveries[name]["wrong"],
        }, sort_keys=True))
PY
shasum -a 256 "$AMIDST_ARTIFACTS/789-native-replay.jsonl"
```

### 無頭 MPS 量測

使用新的 `AMIDST_ARTIFACTS` 路徑。Mac 需可使用 MPS、localhost 臨時埠和所安裝的 Chrome（可由 `CHROME` 指定）。

```sh
PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 AMIDST_API_ENABLED=0 \
  PYTHONPATH="src:$DATA/q1q5-dynamic-baseline-v1_20261025/runtime-deps" \
  "$PYTHON" -B - "$AMIDST_ARTIFACTS" "$DATA" <<'PY'
import json
import os
import platform
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import torch

from amidst.live_mode.scheduler import DEFAULT_GRAPH, DEFAULT_GRAPH_SHA256
from amidst.live_mode.server import FRONT, State, make_handler

out, data = map(Path, sys.argv[1:])
out.mkdir(parents=True)
assert torch.backends.mps.is_available(), "D273 measurement requires MPS"
assets = data / "live-assets-20261115"
state = State(SimpleNamespace(
    cameras=str(assets / "cameras.catalog.json"), camera_graph=DEFAULT_GRAPH,
    graph_sha256=DEFAULT_GRAPH_SHA256, expand_every=1, schedule="adaptive",
    models=str(data / "demo-owned-v1/models/rtdetr"), device="mps", threads=4,
    det_resize_mode="letterbox", min_score=0.15, camera_min_scores={"CAM_ENTRY": 0.05},
    assets=str(assets), gate_m=4.0, gate_growth=0.0, max_gate=8.0, relock="fallback",
    advisor="off", advisor_provider="fake", advisor_model="sol6.1",
    det_width=320, det_height=180,
))

class MeasurementHandler(make_handler(state)):
    def do_POST(self):
        if self.path != "/reset":
            return super().do_POST()
        with state.lock:
            session = state.reset()
        # The current operator resets to IDLE. Start the same red query as B's color chip.
        state.track_start({"session_id": session["session_id"], "color": "red"})
        self._send(200, json.dumps(session).encode())

query = "auto=A4&run=A4-1-v2-4actor&duration=50&model=glb&w=320&h=180&fps=5"
summary = {}
with ThreadingHTTPServer(("127.0.0.1", 0), MeasurementHandler) as server:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR", "CHROME") if k in os.environ}
    env.update(LIVE_BASE=f"http://127.0.0.1:{server.server_port}", RAW="1",
               OUT=str(out.resolve()), AMIDST_HEADFUL="0")
    try:
        for label, enabled in (("current", False), ("supplement", True)):
            with state.lock:
                state.scheduler.cover_single_uncovered_camera = enabled
                state.reset()
            print("START", label, flush=True)
            cmd = ["node", "measure/latency.mjs", label, query, "58"]
            with (out / f"{label}.log").open("w") as log:
                subprocess.run(cmd, cwd=FRONT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            result = json.loads((out / f"{label}.latency.json").read_text())
            raw = json.loads((out / f"{label}.t1raw.json").read_text())
            by_tick = {row["tick"]: row for row in raw["infer"]}
            rows = []
            for row in result["rows"]:
                infer = by_tick[row["tick"]]
                schedule = infer["schedule"]
                rows.append({
                    "tick": row["tick"], "camera_ids": schedule["camera_ids"],
                    "next_camera_ids": schedule["next_camera_ids"],
                    "inferred_camera_count": len(schedule["camera_ids"]),
                    "capture_to_b_ms": row["lat"], "detect_total_ms": infer["timing"]["detect_total"],
                    "reason": schedule["reason"], "lost_rounds": schedule["lost_rounds"],
                    "state": infer["tracking"]["state"],
                })
            summary[label] = {k: result[k] for k in (
                "ticks_displayed", "achieved_fps", "frame_latency_ms", "stage_ms_p50",
                "schedule", "protocol_violations",
            )}
            active = [row for row in rows if row["reason"] in ("ACTIVE_NEIGHBORS", "LOST_EXPAND")]
            summary[label]["graph_branch_ticks"] = len(active)
            summary[label]["graph_branch_entry_processed_ticks"] = sum("CAM_ENTRY" in row["camera_ids"] for row in active)
            (out / f"{label}.ticks.json").write_text(json.dumps(rows, indent=2) + "\n")
            print("END", label, json.dumps(summary[label]), flush=True)
            assert result["protocol_violations"] == 0
            assert active, "the run must exercise the graph branch"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        print("OWNED_SERVER_CLOSED", flush=True)
receipt = {"python": platform.python_version(), "torch": torch.__version__, "hardware": platform.machine(),
           "query": query, "relock": "fallback", "schedule": "adaptive", "paid_calls": 0, "arms": summary}
(out / "summary.json").write_text(json.dumps(receipt, indent=2) + "\n")
PY
```
