# LIVE #789 adaptive 排程的圖外鏡頭覆蓋

2026-11-28，D415 提案，待 Claude 確認。程式基線 `f18304d735b6d6855f0f24a69f330398b11d76f9`。關聯 [#589 的 R-4／R-6](../specs/LIVE_MODE_RELOCK_V1.md#6-可測驗收) 與 [D273 量測](../evaluation/LIVE_DETECTION_SCHEDULE_D273_20261118.md)。

## tick 62 根因

`State.infer` 先用上一輪的 `tracker.active`、`tracker.lost` 和本輪 capture clock 排程，再推論有收到的 JPEG。完成追蹤與 `scheduler.observe` 後，同一時鐘算 `next_camera_ids`；A 螢幕依該清單選擇下次上傳。凍結重播用相同的「先 plan，後 observe」順序，按當輪 capture clock 與凍結觀測交集取資料。

- adaptive＋fallback 在 tick 61 結束仍是 `CAM_W2`、`lost=0`。tick 62 的半徑為 `1 + 0 // 1 = 1`，排 `CAM_W2` 加 `CAM_BRANCH`、`CAM_EXT_CAR`、`CAM_EXT_CLEAR`、`CAM_R101_IN`、`CAM_W1`、`CAM_WIDE`。兩秒內實際處理過的同色候選只保留 `CAM_W1`、`CAM_W2`，已在清單中。原來源 tick 62 的一筆 ENTRY 偵測因此未進 tracker。
- `load_graph` 的 SHA 綁定結果列 `CAM_ENTRY` 為唯一 `uncovered_cameras`。它是已註冊且可提供的鏡頭，沒有圖節點。tick 63 的 `lost=1`、半徑 2，`LOST_EXPAND` 仍只選這 7 台。tick 64 的 `lost=2 >= 2 * expand_every` 先走 `LOST_ALL`，掃回 8 台。ENTRY 首次重排距 tick 62 約 2,000 ms capture clock。
- 補掃時 ENTRY 偵測投影距 **adaptive 重播**的前一估計 14.04 m，該群代表距 13.58 m，超出 §4.5 的 8 m fallback 搜尋半徑。全掃參照從 tick 0 就有不同觀測歷史，在 tick 62 的 ENTRY 投影距其前一估計 4.68 m，呈現一個正確群的 `NEEDS_CONFIRM`，代表鏡頭為 `CAM_W2`。評分以群的投影位置辨識正確候選，與代表鏡頭相同並非必要。

## 提案與驗證

對明確啟用 `--relock fallback` 的 adaptive 排程，在 `CameraScheduler.plan` 的圖內鄰域分支先照常合併鄰域與近期同色鏡頭。若餘下可用鏡頭中恰有一台沒有圖節點，將它加入計畫，依原 available 順序輸出。每次最多多一台，不需要新增時鐘或掃描記憶。多台圖外鏡頭的選擇政策另待設計。本提案依已核定的攝影機清單及 graph membership 求覆蓋，沒有場景專名或硬編碼 ENTRY；新觀測仍走原 detector、投影和追蹤門檻。

Claude 確認後，預計在 `src/amidst/live_mode/scheduler.py` 增加預設關閉的內部選項，由 `server.py` 在 fallback 模式接線，在 `scripts/live_mode/replay_relock.py` 提供同一選項。HTTP、A→B 白名單與 reason enum 維持現況。同步更新本設計記錄及 #589 §5 目前所指向的排程說明。

- `tests/live_mode/test_scheduler.py` 驗單一圖外鏡頭、無圖外鏡頭、兩台圖外鏡頭、registered／available 交集、順序去重及 `all`／預設 `off` 回歸。`tests/live_mode/test_track_endpoints.py` 驗前一回應的 `next_camera_ids` 讓假 detector 在下一個 capture 實際收到補掃 JPEG，以及缺 JPEG 時觀測仍缺失。用 `frontend/live-mode/test/schedule.test.mjs` 和 `protocol.test.mjs` 核對既有網路介面。
- 用同一凍結輸入重跑 R-4／R-6，分開計算候選呈現及自動接回延遲，另外計數 R-5 自動錯接、每輪規劃與實際處理相機數。瀏覽器 A→B 違規數與 R2 latency 需要單獨的無頭整合量測。固定來源 A4 的計畫增加約 24.2%，須先看實際成本才能判定採用。
- 請 Claude 確認 #789 是否以補掃為獨立排程改動，並將追蹤估計偏離／R-4 正確候選與 R-5 留在 #589 的後續設計。用本試算無法核定距離或外觀門檻。

## 凍結重播比較（D415 重播試算）

每組用 `RelockConfig()`。先比較 `plan` 和同一凍結來源下實際可處理的相機觀測，再由既有 scorer 評分。括號內為 ENTRY tick 的相機數。延遲從再入鏡 capture 起算，`null` 表示 episode 內沒有合格結果。

| 來源／排程 | ENTRY tick | 首次排到 ENTRY | 該 tick 處理 ENTRY 偵測 | 正確候選 ms | 正確自動接回 ms | 自動錯接 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 69-tick adaptive-A4／現行 adaptive | 62 | 64（tick 62 為 7 台） | 0／1 | null | null | 1 |
| 同來源／提案 adaptive | 62 | 62（8 台） | 1／1 | null | null | 1 |
| 同來源／現行全掃參照 | 62 | 62（8 台） | 1／1 | 0 | null | 2 |
| 60-tick all-A4／現行 adaptive | 52 | 52（8 台） | 1／1 | 0 | null | 2 |
| 同來源／提案 adaptive | 52 | 52（8 台） | 1／1 | 0 | null | 2 |

| 來源 | 計畫的相機影格數，現行 → 提案 | 已處理的相機影格數，現行 → 提案 | 跟對／失聯（前後相同） |
| --- | ---: | ---: | --- |
| 69-tick adaptive-A4 | 472 → 521 | 415 → 437 | 43/69、13/69 |
| 60-tick all-A4 | 411 → 431 | 411 → 431 | 7/60、29/60 |
| 固定 RGB A4 | 297 → 369 | 297 → 369 | 67/95、4/95 |
| 固定 RGB B4 | 243 → 243 | 243 → 243 | 58/60、1/60 |

固定 RGB 的 R-6 跟對率與失聯率達門檻。tick 62 補掃已在試算重現，完整 R-4／R-6 尚未通過，R-5 已可見自動錯接。adaptive 來源只包含原始捕捉的觀測，缺影格記為 `MISSING`。真實捕捉時間、負載、A→B 違規數維持 `UNKNOWN`。

## 來源與重跑

在獨立 scratchpad clone 的本 PR 基線執行。先用 `npm ci --prefix frontend/live-mode` 安裝評分器間接載入的 `puppeteer-core`。無瀏覽器、模型或服務呼叫。各來源只供既有 replay adapter 擷取 capture clock 與像素偵測欄位，校正只讀；`score_replays` 及 `entry_audit` 在所有決策結束後才接回評分欄位。用新輸出路徑。

| LOCAL 來源或產物 | Bytes／檔數 | SHA-256 | 重建 |
| --- | ---: | --- | --- |
| `local/evidence/cx552-d-20261118/fresh/latency/adaptive-A4.t1raw.json` | 212,476／1 | `f3fce7d92315b22247f29cdf55182d5c95bf242150f7d3cd1a6e20e8774c1c69` | D273 凍結來源 |
| `local/evidence/cx552-d-20261118/fresh/latency/all-A4.t1raw.json` | 207,268／1 | `308de2c315b5e2ac696d194a9a357ca98c1a01a26fe126b346c08dfbac74d003` | D273 凍結來源 |
| `local/evidence/cx552-d-20261118/baseline-fixed/all/fixed__a4_route_baseline.t1raw.json` | 178,954／1 | `e2e0547748cd242da6d84a404235a4cf108be91cac3de0e7e96af2779fe574be` | D273 凍結來源 |
| `local/evidence/cx552-d-20261118/baseline-fixed/all/fixed__b4_route_baseline.t1raw.json` | 164,669／1 | `984481f8b6e1372507d3a6dd8f950e555b7da921ed06ae214d6eb93c3ee79483` | D273 凍結來源 |
| `local/data/live-assets-20261115/cameras.catalog.json` | 12,793／1 | `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f` | 直接讀取 |
| `$AMIDST_ARTIFACTS/789-design-replay.jsonl` | 31,954／1 | `269bdd1e3f33040c78c74f59709786a535bc069770110934a46befe5ba6ae3b3` | 下列指令，需 `puppeteer-core` |

[Camera graph](../../configs/q1q5/graphs/r004/camera_graph_v3.json) SHA-256 `9896be113bf6e2b5f2d9344f1227484674fda2c2bb983d32a70d8ffcc4adfc7e`。下列試算只在行程中替換 replay 使用的 scheduler，將現行邏輯與提案分開比較。

```sh
PYTHONPATH=src:scripts/live_mode "$PYTHON" -B - "$EVIDENCE/cx552-d-20261118" \
  "$DATA/live-assets-20261115/cameras.catalog.json" > "$AMIDST_ARTIFACTS/789-design-replay.jsonl" <<'PY'
"""D415 offline design probe. The scheduler substitution is confined to this process."""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import replay_relock as replay
from amidst.live_mode.relock import RelockConfig
from amidst.live_mode.scheduler import DEFAULT_GRAPH, DEFAULT_GRAPH_SHA256, CameraScheduler, load_graph
from amidst.live_mode.tracker import Projector, load_cameras

d273, catalog = map(Path, sys.argv[1:])
paths = {
    "adaptive-A4": "fresh/latency/adaptive-A4.t1raw.json",
    "all-A4": "fresh/latency/all-A4.t1raw.json",
    "fixed-A4": "baseline-fixed/all/fixed__a4_route_baseline.t1raw.json",
    "fixed-B4": "baseline-fixed/all/fixed__b4_route_baseline.t1raw.json",
}
entries = [(label, d273 / path, json.loads((d273 / path).read_bytes())) for label, path in paths.items()]
projector = Projector(load_cameras(str(catalog)))
graph, binding = load_graph(DEFAULT_GRAPH, DEFAULT_GRAPH_SHA256, replay.inventory_file(catalog)["sha256"], list(projector.cams))
inputs = [replay.observation_records(raw) for _, _, raw in entries]
records = []
class ProbeScheduler(CameraScheduler):
    def reset(self):
        super().reset()
        self.last_scan = {}

    def observe(self, detections, t_s):
        super().observe(detections, t_s)
        self.last_scan.update((cam, t_s) for cam in detections)

    def plan(self, active, lost_rounds, available, *, t_s=None):
        plan = super().plan(active, lost_rounds, available, t_s=t_s)
        omitted = [c for c in dict.fromkeys(available) if c not in plan["camera_ids"]]
        extra = None
        if variant == "cover-unknown":
            unknown = [c for c in omitted if c not in self.adj]
            if len(unknown) == 1:
                extra = unknown[0]
        if extra is not None:
            selected = set(plan["camera_ids"]) | {extra}
            plan["camera_ids"] = [c for c in dict.fromkeys(available) if c in selected]
        records.append({"active": active, "neighbors": sorted(self.adj.get(active, ())),
                        "recent": sorted(self._recent_candidates),
                        "last_entry_scan_s": self.last_scan.get("CAM_ENTRY"),
                        "capture_s": t_s, "extra": extra, **plan})
        return plan

replay.CameraScheduler = ProbeScheduler
for variant, mode in [
    ("current", "adaptive"), ("cover-unknown", "adaptive"), ("current", "all"),
]:
    traces, diagnostics = [], {}
    for (label, _, raw), rows in zip(entries, inputs, strict=True):
        records.clear()
        cfg = raw["cfg"]
        traces.append(replay.replay_safe(rows, cfg["cams"], (cfg["w"], cfg["h"]),
                                         projector, graph, mode=mode, config=RelockConfig()))
        diagnostics[label] = records.copy()
    with TemporaryDirectory() as scores:
        rows, rates = replay.score_replays(entries, traces, Path(scores))
    audit = replay.entry_audit(entries, traces, rows)
    spans = {label: replay.episodes(rows[label]) for label in rows}
    recovered = replay.recovery_counts(dict(zip(paths, traces, strict=True)), rows, spans)
    for (label, _, _), trace, raw_obs in zip(entries, traces, inputs, strict=True):
        diag = diagnostics[label]
        episodes = []
        for incident in audit[label]:
            i = incident["entry_tick"]
            first_scheduled = next((j for j in range(i, len(trace)) if "CAM_ENTRY" in diag[j]["camera_ids"]), None)
            episodes.append({"schedule": first_scheduled,
                             "raw_entry_dets_at_tick": len(raw_obs[i]["dets"].get("CAM_ENTRY", [])),
                             "processed_entry_dets_at_tick": len(trace[i]["dets"].get("CAM_ENTRY", [])),
                             "state_at_tick": trace[i]["tracking"]["state"],
                             "before_state": trace[i - 1]["tracking"]["state"],
                             "before_est": trace[i - 1]["tracking"]["est_xy"],
                             "entry_boxes": trace[i]["dets"].get("CAM_ENTRY"),
                             "options": trace[i]["tracking"].get("confirm_candidates"),
                             "groups": trace[i]["trace"]["groups"],
                             **incident})
        print(json.dumps({
            "mode": mode, "variant": variant, "label": label, "ticks": len(trace),
            "entry": episodes, "rate_counts": rates[label],
            "wrong_auto": recovered[label]["wrong"], "unknown_auto": recovered[label]["unknown"],
            "planned_frames": sum(len(item["camera_ids"]) for item in diag),
            "observed_frames": sum(len(item["dets"]) for item in trace),
            "key_ticks": {i: {**diag[i], "result": trace[i]["tracking"]["state"],
                              "after_active": trace[i]["tracking"]["active_cam"],
                              "after_lost": trace[i]["tracking"]["lost_ticks"]}
                          for i in range(60, 65)} if label == "adaptive-A4" else {},
        }, sort_keys=True))
PY
shasum -a 256 "$AMIDST_ARTIFACTS/789-design-replay.jsonl"
```
