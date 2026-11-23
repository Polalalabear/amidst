# E5 A-open 介面契約 v1

狀態：**待 Codex 確認**（Claude 起草，2026-11-23，#684）。Codex 在 PR #685 上寫「契約確認」之後，PR 才合併，Codex 也才開始實作（D357）。確認後的細節，可以在試跑之前用預登的修訂紀錄補進來；試跑開始以後，契約凍結（預登 §0.1）。`e5.b-log.v1` 已在 `configs/architecture/schema_registry_v1.json` 登記（`PROPOSED_LITERAL_ONLY_NOT_ADOPTION`）。
預先登記：`docs/evaluation/E5_PREREGISTRATION_20261123.md`（以下寫「預登 §n」）。契約和預登不一致時，以預登為準，並回報 Claude 修正契約。

身分一律 `UNCONFIRMED`。GT、渲染軌跡、可見性和深度不得進入本契約的任何推論路徑：E3 預登 §5.2 列的欄位，推論端不得讀取或 import。

## 1. 範圍和檔案歸屬

| 項目 | 歸屬 | 建議路徑（Codex 可調整，但要回報） |
|---|---|---|
| A-open 決策器（請求、解析、套用） | Codex | `src/amidst/live_mode/aopen/decider.py` |
| 中性追蹤器 | Codex | `src/amidst/live_mode/aopen/neutral.py` |
| 離線重播入口（AO、AO-L） | Codex | `scripts/evaluation/e5_run.py` |
| 單元測試 | Codex | `tests/live_mode/test_aopen_*.py`、`tests/evaluation/test_e5_run.py` |
| 評分包裝程式、報告 | Claude | `scripts/evaluation/e5_score.py`、`docs/operations/E5_REPORT_*.md` |

不得修改的檔案見 §8。可以 import 共用的程式（`agent_service`、`scene_context`、`e3_f4_run.load_case`／`live_scene_context`、`service_decider.guarded_responses_transport`），但不改它們。

## 2. Agent 請求

- 傳輸：`service_decider.guarded_responses_transport`，所有付費呼叫都經 ApiGuard。帳本 caller 名稱是 `e5`，每個行程用自己的帳本（`--usage-dir`，D352）。
- 模型：`gpt-6.1-terra`。
- 請求本體：`agent_service.build_body`，前綴（`SYSTEM_TEXT`＋scene context）不變；E5 說明 `E5_EXTRA` 接在前綴後面（同 E4 的接法）。可變部分包含：
  - 每台鏡頭當下的畫面，框上標編號 `D1, D2…`（每台鏡頭各自從 D1 起編）；
  - 每個候選框：`camera_id`、`detection_id`、框、分數、類別、顏色，以及規則閘門的結果（只當資訊）；
  - 規則追蹤當下的狀態（`state`、`active_cam`、`lost_ticks`），只當資訊；
  - A-open 目前的狀態：顯示中的鏡頭和框、中性追蹤器的狀態（`FOLLOWING`／`COASTING`／`LOST`）、上次的排序；
  - 參考截圖。
- 候選框：E3 凍結偵測索引的人物框，分數 ≥ 0.15（`CAM_ENTRY` ≥ 0.05），和 B1 的輸入相同（`e3_f4_run.load_case`）。
- `E5_EXTRA` 至少要寫明：影像的實際像素大小（E3 劇本是 320×180），OWN_BOX 的座標以這個大小為準，取代 `SYSTEM_TEXT` 裡的「960x540 px」；可以選任何框，也可以自畫框；選中的框直接成為目標；每次回答都要給 `next_camera_ranking`；看不出來就回答 `UNCERTAIN`；目標不在任何畫面就回答 `NOT_VISIBLE`。提示全文由 Codex 寫，會進預登的附錄，**跑之前寫死**。

## 3. Agent 回應格式

JSON 物件：

```json
{"answer": "SELECT" | "OWN_BOX" | "NOT_VISIBLE" | "UNCERTAIN" | "STILL_HERE_OCCLUDED",
 "camera_id": "CAM_W2" | null,
 "detection_id": "D3" | null,
 "box_xyxy": [x0, y0, x1, y1] | null,
 "next_camera_ranking": ["CAM_W2", "CAM_WIDE", "CAM_BRANCH"],
 "confidence": "low" | "medium" | "high",
 "reason_codes": ["..."],
 "reason": "..."}
```

| answer | 必填 | 驗證（不合格就當作沒有回答，`fallback_reason` 寫下表的代碼；不是 JSON 或回答種類不對寫 `FORMAT_INVALID`） |
|---|---|---|
| SELECT | `camera_id`、`detection_id` | 這次請求裡要有這個 (`camera_id`, `detection_id`)，否則 `UNKNOWN_DETECTION` |
| OWN_BOX | `camera_id`、`box_xyxy` | 座標以請求影像的實際像素為單位（`service_decider._jpeg` 不縮放，E3 劇本是 320×180），0 ≤ x0 < x1 ≤ W、0 ≤ y0 < y1 ≤ H；鏡頭要在這次請求裡。否則 `BAD_OWN_BOX`。注意：`agent_service.parse_answer` 用 960×540 檢查，E5 要用自己的驗證 |
| STILL_HERE_OCCLUDED | `camera_id` | 鏡頭要在這次請求裡，否則 `BAD_CAMERA` |
| NOT_VISIBLE、UNCERTAIN | 無 | — |

- `next_camera_ranking`：每種回答都要給，最多 3 台，濾掉未知鏡頭和重複。沒給，或過濾後是空的，就記 `ranking_supplied=false`，排序是空的；**不拿 `next_camera_hint` 補**。回答裡如果有 `next_camera_hint`，只原樣記在 `calls[].next_camera_hint_raw`。
- `reason_codes` 最多保留 4 個，多的截掉，不算格式錯誤。

## 4. 軌跡建立和接管語意

A-open 的狀態：`target = {camera_id, box(320×180 像素), est_xy, source, since_tick}` 或 `None`。

| 回答 | 效果（離線同步：在提問後的下一個 tick 生效） |
|---|---|
| SELECT | `target` 設成那個偵測框（偵測索引的像素座標，E3 劇本就是 320×180），`source=AGENT_SELECT`。不論之前有沒有目標、在哪台鏡頭，一律接管。 |
| OWN_BOX | `target` 設成 Agent 畫的框（請求影像的像素座標，不換算），`source=AGENT_OWN_BOX`。中性追蹤器從這個框開始延續。 |
| STILL_HERE_OCCLUDED | 只有**目前有目標、而且 `camera_id` 和目前目標同一台**時才有效；否則 `applied=false`、`fallback_reason=OCCLUDED_NO_TARGET`，狀態不變。有效時進入保留：留在原鏡頭，`box=None`，以最後一個框的位置（`est_xy`，最後一個框底邊中點的地面投影）顯示，保留期是 [生效 tick, 生效 tick＋`occluded_hold_s` = 2.0 s)，共 10 個 tick，到期那個 tick 變成 LOST（`target=None`）。 |
| NOT_VISIBLE | `target=None`，記下排序。 |
| UNCERTAIN、沒有回答（錯誤、逾時、格式不合、達到呼叫上限） | 不改 `target`，中性追蹤器繼續。 |

- 保留期間（OCCLUDED）：
  - UNCERTAIN 和沒有回答都**不延長**保留期；
  - 新的有效 OCCLUDED 從新的生效 tick 重新計時；
  - SELECT／OWN_BOX 結束保留並接管；NOT_VISIBLE 結束保留並清掉目標；
  - 中性追蹤器**不**自動接回（保留期間不做 IoU 關聯）。
- 規則不否決：規則的狀態不會改變 `target`，也不會擋任何回答。
- 一開始：規則第一次 ACQUIRE 時截取參考截圖（同 E3），第一次提問就在那個 tick。在 Agent 第一次 SELECT／OWN_BOX 之前，AO 不顯示任何東西。
- 模擬即時（AO-L）：答案在「提問 tick 的時間＋實測延遲」之後的第一個 tick 生效。SELECT／OWN_BOX 生效前，要把提問時的框用 IoU ≥ 0.3，在同一台鏡頭裡逐 tick 串到生效那個 tick（每個 tick 取 IoU 最大、且 ≥ 0.3 的系統偵測框；同 `e3_f4_run.chain_box`）。串不上就記 `EXPIRED`，不套用。同一時間只有一個問題在途。

## 5. 中性追蹤器

```
NeutralTracker.step(tick, target, dets_by_cam) -> (target', status)
```

- 輸入：上一個 tick 的 `target`，和這個 tick 每台鏡頭的偵測框（和候選框同一份，不看顏色）。
- 規則：只看 `target.camera_id` 那台鏡頭。和 `target.box` 的 IoU 最大、且 ≥ `neutral_iou = 0.3` 的偵測框就是新的 `box`，狀態 `FOLLOWING`。沒有就保留舊框，狀態 `COASTING`，最多 `coast_ticks = 2`；之後 `target=None`，狀態 `LOST`。
- 不換鏡頭，不自己找新目標，也不用顏色、分數或圖的門檻。
- `est_xy`：框底邊中點經 `Projector.ground`（相機校正，和規則追蹤同一個投影）。投影失敗時保留上一個 `est_xy`；如果從來沒有成功過，這個 tick 不顯示，記 `NO_GROUND_POINT`。
- 失聯（`LOST` 或 NOT_VISIBLE）時，下一次提問提前到距離上一次 `min_interval_s` 之後；請求把 `next_camera_ranking` 裡的鏡頭排在前面。

## 6. 資源限制參數（名稱和預設）

| 參數 | 預設（預登主設定） | CLI |
|---|---|---|
| `poll_s` | 2.0 | `--poll-s` |
| `min_interval_s` | 1.0 | `--min-interval-s` |
| `call_cap_per_segment` | ⌈片段秒數 ÷ `poll_s` × 1.5⌉ | `--call-cap-factor 1.5` |
| `timeout_s` | 30.0（AO）；AO-L 用實測延遲生效，超過 30 s 算 `PROVIDER_TIMEOUT` | `--timeout-s` |
| `cost_cap_usd` | 這個行程的 ApiGuard 合計上限 | `--budget-usd`（必填，> 0） |
| `neutral_iou`、`coast_ticks`、`occluded_hold_s` | 0.3、2、2.0 | 寫死，不開 CLI |
| 模式 | `offline`（AO）或 `simlive`（AO-L） | `--mode` |

達到呼叫上限之後不再提問，中性追蹤器繼續。`CALL_CAP_REACHED` 是**控制事件，不是錯誤**：在達到上限的那個 tick，於 `rows[].events` 記一筆 `{"type": "CALL_CAP_REACHED"}`；不新增 `calls[]` 列、不計入呼叫數，也不計入 provider 錯誤率。報告另外列達到上限的次數。

## 7. 離線重播入口和輸出檔格式

```
python -B scripts/evaluation/e5_run.py --root <E3 root> --cameras <cameras.catalog.json> --out <runs> \
  --cases E3-A1 ... --k 3 --mode offline --budget-usd <cap> --usage-dir <ledger>
```

- 載入：`e3_f4_run.load_case`（凍結 PNG、偵測索引、tick 序列、擷取順序），`e3_f4_run.live_scene_context`（scene context）。規則追蹤用 `State._infer_tracking` 跑 B1 同一條路徑（同 `e3_f4_run.replay`，advisor off），只為了取得參考截圖的時刻和請求裡的規則資訊，不影響 AO 的顯示。
- 輸出：`<out>/<case_id>/<ARM>.k<n>.json`，`ARM` = `AO`（offline）或 `AOL`（simlive）。已經存在的檔案跳過。
- 檔案格式 `e5.b-log.v1`，必須能被 `e3_f4_score.run_scores` 直接讀：

```json
{"schema_version": "e5.b-log.v1", "case_id": "E3-A1", "arm": "AO", "k": 1, "tick_us": 200000, "size": [320, 180],
 "config": {"poll_s": 2.0, "min_interval_s": 1.0, "call_cap_per_segment": 0, "timeout_s": 30.0, "mode": "offline",
            "neutral_iou": 0.3, "coast_ticks": 2, "occluded_hold_s": 2.0, "model": "gpt-6.1-terra"},
 "inputs": {"index_content_sha256": "...", "records_file_sha256": "...", "rgb_index_sha256": "..."},
 "camera_catalog_sha256": "...", "graph_sha256": "...", "scene_context_sha256": "...", "source_sha256": {"<path>": "..."},
 "prompt_extra_sha256": "...", "identity": "UNCONFIRMED", "wall_s": 0.0,
 "rows": [{"tick": 0,
           "tracking": {"state": "TRACKING" | "LOST", "active_cam": "CAM_W2" | null, "est_xy": [x, y] | null, "lost_ticks": 0, "box": [x0, y0, x1, y1] | null},
           "ranking": ["CAM_W2"], "decision_source": "AGENT" | "NEUTRAL" | "NONE", "neutral_status": "FOLLOWING" | "COASTING" | "LOST" | "OCCLUDED_HOLD" | null,
           "events": [{"tick": 0, "type": "ADJUDICATE_ASK" | "ADJUDICATED" | "SWITCH" | "ACQUIRE" | "CALL_CAP_REACHED", "cam": null, "detail": {}}]}],
 "calls": [{"tick": 0, "kind": "POLL" | "LOST_EARLY" | "FIRST",
            "answer": "SELECT", "camera_id": "...", "detection_id": "...", "box_xyxy": null, "next_camera_ranking": [], "ranking_supplied": true,
            "next_camera_hint_raw": null,
            "confidence": "medium", "reason_codes": [], "reason": "...",
            "applied": true, "source": "AGENT" | "NEUTRAL",
            "fallback_reason": null | "PROVIDER_TIMEOUT" | "PROVIDER_ERROR" | "FORMAT_INVALID" | "UNKNOWN_DETECTION" | "BAD_OWN_BOX" | "BAD_CAMERA" | "CALL_BUDGET_EXHAUSTED" | "EXPIRED" | "OCCLUDED_NO_TARGET",
            "latency_ms": 0, "model_latency_s": 0.0, "usage": {"input_tokens": 0, "output_tokens": 0}, "scene_context_sha256": "...",
            "request": {"t_s": 0.0, "images": {"CAM_W2": "<sha256>"}, "reference": "<sha256>", "candidates": 0,
                        "candidate_list": [{"detection_id": "D1", "camera_id": "CAM_W2", "box": [0, 0, 0, 0], "score": 0.0, "class_label": "person", "colors": []}],
                        "variable_text": "<可變文字全文>", "prefix_sha256": "...", "rule_state": {"state": "...", "active_cam": "...", "lost_ticks": 0}},
            "error": null}]}
```

各欄位語意：
- **`tracking`（評分只看這一欄）**：
  - 顯示中：`state=TRACKING`、`lost_ticks=0`，`active_cam` 和 `est_xy` 都非空，`box` 是 320×180 像素。
  - OCCLUDED 保留期間：`box=null`，只顯示位置（`est_xy` 保留最後一個框的值），`neutral_status=OCCLUDED_HOLD`。
  - 不顯示：`state=LOST`，`active_cam=null`。
- **`ranking`**：永遠等於**最近一次有效回答**的 `next_camera_ranking`（H8c 取前一個 tick 的值）。最近一次有效回答沒給排序，就是空的 `[]`，不沿用更早的排序，也不拿 hint 補。第一次有效回答之前也是空的。`run_scores` 讀到空排序就算未命中（預登 §5 H8c）。
- **`calls[].applied`**：`true` 表示這次回答改了 `target`（SELECT／OWN_BOX 生效、NOT_VISIBLE 清掉目標、有效的 OCCLUDED 開始或重新開始保留）。UNCERTAIN 是 `false`、`fallback_reason=null`。
- **`source` 和 `fallback_reason`**：E5 **不用 `RULE_FALLBACK`**。有效回答是 `source=AGENT`；其他情況是 `source=NEUTRAL`（由中性追蹤器延續），`fallback_reason` 直接寫實際原因。分類如下，由 Claude 的 E5 評分包裝程式（`e5_score.py`）統一正規化，不改 `e3_f4_score.api_breakdown`：

  | 類別 | `fallback_reason` | 用途 |
  |---|---|---|
  | provider 錯誤 | `PROVIDER_TIMEOUT`、`PROVIDER_ERROR` | 預登 §7 的 10% 停止條件（照 D352 算缺漏資料） |
  | 格式退回 | `FORMAT_INVALID`、`UNKNOWN_DETECTION`、`BAD_OWN_BOX`、`BAD_CAMERA` | 試跑的 20% 退回率門檻 |
  | 預算拒絕 | `CALL_BUDGET_EXHAUSTED` | D352 重跑規則 |
  | 模擬即時過期 | `EXPIRED` | 只出現在 AO-L |
  | 無效的 OCCLUDED | `OCCLUDED_NO_TARGET` | 有效呼叫，不算錯誤 |
  | 控制事件（不是 `calls[]` 列） | `CALL_CAP_REACHED` 記在 `rows[].events` | 不計入呼叫數或錯誤率 |
- **`candidate_list` 和 `detection_id`**：補齊 E3 缺的欄位（Opus #678 裁決的後續）。影像本身不存，可以由凍結輸入和 SHA-256 重建。

## 8. 不能動的檔案

- E3 和 B1：`scripts/evaluation/e3_f4_run.py`、`scripts/evaluation/e3_f4_score.py`、`src/amidst/evaluation/e3_scoring.py`（評分器 `acacce39…`）。
- 規則路徑：`src/amidst/live_mode/tracker.py`、`src/amidst/live_mode/people.py`，以及 `src/amidst/live_mode/server.py` 的 `_infer_tracking`／`_new_tracker`。B1 要固定在 E3 版本（#676 等 E5 結束後才合併）。
- 共用的 Agent 程式：`src/amidst/q1q5/agent_service.py`、`src/amidst/q1q5/scene_context.py`、`src/amidst/live_mode/service_decider.py`。E5 要用自己的模組；需要擴充時，以子類或包裝的方式做（像 E4 的 `E5_EXTRA`）。
- E3 和 E4 的資料只讀：`local/evidence/f4-658-20261122/`（MANIFEST.sha256 SHA-256 `86899282f5e1d14a17a998c933d8f1407cc165042e0997b0d5ca414b66bc13a5`）、`local/evidence/e4-681-20261123/`（MANIFEST.sha256 SHA-256 `cbcc9c12b72409ee69d08c15fe41587303dcd2f40fb0d68af582618c5d1a6c60`）、`local/evidence/e3-*`（E3 案例輸入，SHA 見 F4 報告 §10）。
- 預登和本契約：要改的話，回報 Claude。

## 9. 驗收（Codex 交付時）

- 單元測試（不連網、沒有模型、沒有 GT）：
  - SELECT 和 OWN_BOX 的接管；
  - 中性追蹤器的 FOLLOWING／COASTING／LOST 和不換鏡頭；
  - NOT_VISIBLE／UNCERTAIN／OCCLUDED 的語意，包括 OCCLUDED_NO_TARGET（沒有目標、跨鏡頭）、保留期 10 個 tick 到期變 LOST、UNCERTAIN 不延長、新的 OCCLUDED 重新計時、SELECT／OWN_BOX 接管、NOT_VISIBLE 清除、保留期間不自動接回；
  - 缺排名時 `rows[].ranking=[]`、hint 只記在 `next_camera_hint_raw`；
  - 呼叫上限（只在 `rows[].events` 記一筆，不新增 `calls[]` 列）；
  - AO-L 的串接和 EXPIRED；
  - 每種格式錯誤；
  - 輸出檔能被 `e3_f4_score.run_scores` 讀取（用合成資料）。
- 試跑只能在 Claude 審查和預登合併之後進行（預登 §3）。Codex 交付時不付費執行。
- PR 照 AGENTS.md 的實際產出模板，連結 #684。

## Codex 的問題和裁決

Codex 對原本四個問題的回覆，協調者全部接受（#685）：

1. §1 的路徑：照 Codex 的回覆。
2. 規則資訊和參考截圖時刻由一份**獨立的 B1 sidecar 狀態**提供，不和 AO 狀態耦合。
3. OWN_BOX 用請求影像的實際像素（320×180），不用 `SYSTEM_TEXT` 的 960×540；`E5_EXTRA` 要覆寫這一句。E3 的 OWN_BOX 只記錄、不套用，所以這個不一致在 E3 沒有影響。
4. AO-L 同一時間只有一個在途問題。

協調者另外裁決了三項：API 分類（§7）、缺排名（§3、§7）、OCCLUDED（§4），已經寫進上面各節。Codex 確認後在 PR #685 寫「契約確認」。
