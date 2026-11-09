# 核心功能契約 v1：查找與追蹤（`Q_CORE_SEARCH_TRACK_V1`）

- 狀態：**PROPOSED**（D126，2026-11-04；記錄於 [#93](https://github.com/Polalalabear/amidst/issues/93)）。本文件不核准任何參數、圖或 G4，也不宣告 Demo 通過。
- 分工：Claude 寫本契約與驗收測試；Codex 實作前後端。**驗收測試就是驗收標準**：測試全部通過（`AMIDST_REQUIRE_IMPL=1` 下不再 skip）才算做完。
- 機器可讀 schema：[`schemas/q-core.search-track.v1.schema.json`](schemas/q-core.search-track.v1.schema.json)。
- 驗收測試：
  - Python：[`tests/q1q5/test_core_search_track_t.py`](../../tests/q1q5/test_core_search_track_t.py)
  - 前端（node）：[`frontend/workbench-v2/core-search-track.test.mjs`](../../frontend/workbench-v2/core-search-track.test.mjs)
  - 合成多教室 fixture：[`tests/q1q5/fixtures/core_multi_room.synthetic.json`](../../tests/q1q5/fixtures/core_multi_room.synthetic.json)
- 沿用：[`Q1_Q2_FIRST_DEMO_V1`](Q1_Q2_FIRST_DEMO_V1.md) 的時鐘（§3）、偵測索引（§4）、兩層圖（§5）、Q1（§6）、Q2 連接器（§8.2）；[`DEMO_UI_SUPPORT_V1`](DEMO_UI_SUPPORT_V1.md) §6 的物理預測。本文件只新增包在它們外面的兩個核心入口，不改既有 Q1／Q2 wire。

## 0. 定位與原則

1. 系統是**輔助**：讓使用者快速知道目標大概在哪，不追求精確。所有輸出 `identity_verdict: UNCONFIRMED`，串起來的片段是「條件相符的候選」，不是「同一個人」。
2. 證據狀態分四種，欄位名一律 `evidence_state`：
   | 值 | 意思 | 例 |
   | --- | --- | --- |
   | `OBSERVED` | 偵測器在取樣畫面上實際看到 | 物件命中、追蹤的 `ON_CAMERA` 段 |
   | `INFERRED` | 由觀測推算，不是觀測 | 盲區的物理預測曲線 |
   | `MISSING` | 應該有來源但沒有（缺畫面、未推論） | 索引缺格 |
   | `UNKNOWN` | 沒有證據可判斷 | 追蹤的 `GAP`、`LOST` 段 |
3. 地點命中是**場景設定**（人工在靜態畫面標的涵蓋區域），不是看到目標。只靠地點命中的結果帶 `target_observed: false`。
4. GT、渲染軌跡、visibility、depth、腳本關鍵影格、情境卡計畫時刻，一律不得進入推論、測試輸入或畫面。請求含這些鍵時沿用 `api._safe_request`，回 422 `FORBIDDEN_INFERENCE_INPUT`；回應任何層級不得出現這些鍵。
5. 資料驅動：區域、鏡頭、類別、顏色都從 pinned 檔讀（region graph、camera graph、supported-classes／class map）。程式與測試不得寫死 `R101`、`R102` 或特定鏡頭；Codex 擴充教室（例如 R101～R104）時只改設定檔。

## 1. 路由

新增兩個 POST route，加入 `api.POST_ROUTES`：

| route | 用途 |
| --- | --- |
| `q_core_search` | case1 查找 |
| `q_core_track` | case2 追蹤 |

`q_physical_prediction` 維持現有路由名稱；接上前回 503 `Q_RESOURCE_UNAVAILABLE`（現況），接上後回 `q-demo.physical-prediction.v1`（§4.1）。授權、session、run 綁定沿用 `QAPI._run`（不需要 audit）。

錯誤一律 `APIError(code, status)`：

| 情況 | status | code |
| --- | --- | --- |
| 欄位缺漏、型別錯、違反本契約的驗證規則 | 422 | §2.3／§3.3 列的代碼 |
| 請求含 GT／私有鍵、多餘欄位 | 422 | `FORBIDDEN_INFERENCE_INPUT` |
| session 不符、跨 scene／run | 403 | `FORBIDDEN_DATA_SCOPE` |
| run 未設定 | 503 | `Q_RUN_NOT_CONFIGURED` |

## 2. case1 查找（`q_core_search`）

### 2.1 請求

```json
{
  "schema_version": "q-core.search-request.v1",
  "session_ref": "…",
  "scene_id": "…",
  "run_id": "…",
  "time": {"kind": "WALL", "timezone": "Asia/Taipei",
           "wall_range": ["2026-11-01T13:00:00+08:00", "2026-11-01T13:30:00+08:00"]},
  "region_ids": ["R101"],
  "feature": {"class_label": "person", "color_label": "red"}
}
```

| 欄位 | 規則 |
| --- | --- |
| `time` | **必填**。`kind` 固定 `WALL`；`timezone` 必須等於該 run `clock_mapping.timezone`（目前 `Asia/Taipei`）；`wall_range` 為兩個含 UTC 偏移的 ISO 8601，半開區間，結束晚於開始。換算沿用 `clock_mapping.resolve_wall_range`。前端把「13:00–13:30」用 `clock_mapping.wall_origin` 的日期與時區補成完整 ISO（§5.1），伺服器只收完整 ISO |
| `region_ids` | 選單值，來自 region graph 的 `regions[].region_id`。`[]` 表示不限地點。值不得重複，不得在圖外 |
| `feature` | `null` 表示不限特徵；否則 `class_label` 必填，必須在 supported-classes 的 `class_labels`（COCO 80 類，`coco80-v1`）或其 alias 裡；`color_label` 可為 `null`，非 null 時必須在 `color_vocabulary.labels` 裡，且 `class_label` 必須是 `person` |
| 至少一個 | `region_ids` 為空且 `feature` 為 `null` 時回 422 `LOCATION_OR_FEATURE_REQUIRED` |

客戶端**不得**傳 score、門檻、鏡頭清單或檔案路徑。物件查詢的 `query_min_score` 由伺服器決定：沿用 run 參數集中的 `query_min_score`（Q 線現有參數），參數集沒有這個參數時用索引 manifest 的 `detector.index_score_floor`；每格至少 1 個符合偵測。實際用值寫進 `resolved_scope.query_min_score`。

### 2.2 命中規則

- **地點命中**：camera graph 中 `covered_regions` 有任一 `region_id ∈ region_ids` 且 `basis == "MANUAL_ON_STATIC_FRAME"` 的鏡頭。其他 basis 不算命中，該鏡頭列入 `not_evaluated_cameras`，`reason: COVERAGE_BASIS_UNSUPPORTED`。命中鏡頭還必須在該 run 的鏡頭目錄（bootstrap `camera_ids`）裡；圖中有、run 沒有的鏡頭列 `not_evaluated_cameras`，`reason: CAMERA_NOT_IN_RUN`。命中依據帶 `region_id`、`coverage_basis`、`visibility_ref`。地點命中不代表目標被看到。
- **物件命中**：用現有 RT-DETR COCO 偵測索引（`detection_index.py`），以 `q1_search.search_cameras` 的語意查詢（單一 run、同一時間範圍、`min_count_per_frame: 1`、上述 score、顏色條件）。每個命中鏡頭帶 Q1 的 `matched_segments`；`evidence_state: OBSERVED`。
- **兩者都填**：鏡頭集合取交集；每筆命中的 `basis` 同時有 `LOCATION` 與 `OBJECT` 兩種；時間片段用物件片段。
- **只填地點**：每個命中鏡頭一筆，`source_range_us` 是解析後的整段時間，`target_observed: false`。
- 排序：有物件片段者依第一個片段起點升冪、再依 `camera_id`；只有地點者依 `camera_id`。

### 2.3 驗證錯誤代碼（422）

| code | 何時 |
| --- | --- |
| `TIME_REQUIRED` | 缺 `time` 或為 `null` |
| `TIME_INVALID` | 不是 WALL、ISO 無偏移、格式錯 |
| `TIME_ORDER` | 結束不晚於開始 |
| `TIME_CROSSES_MIDNIGHT` | 開始與結束在宣告時區不是同一天（沿用 Q1 §3.2 不跨午夜） |
| `TIME_ZONE_MISMATCH` | `timezone` 與 run 的宣告時鐘不同，或偏移與該時區不一致 |
| `LOCATION_OR_FEATURE_REQUIRED` | 地點與特徵都空 |
| `REGION_UNKNOWN` | 區域不在 region graph |
| `UNSUPPORTED_CLASS` | 類別不在 class map／alias |
| `COLOR_UNKNOWN` | 顏色不在 color vocabulary |
| `UNSUPPORTED_CONDITION` | 有顏色但類別不是 person |

不是 422、而是回應狀態的情況（沿用 Q1 §3.2／§3.3）：run 沒有宣告時鐘 → `status: UNKNOWN`、`reasons: ["CLOCK_MAPPING_MISSING"]`，不猜日期；時間只部分有資料 → `PARTIAL`、`TIME_SCOPE_PARTIAL`；完全沒交集 → `OUT_OF_RANGE`。

類別清單來源：`configs/q1q5/class_alias_v1.json`（`q-demo.supported-classes.v1`，COCO 80 類＋別名，PROPOSED），與 run 綁定的 supported-classes 相同。

### 2.4 回應

```json
{
  "schema_version": "q-core.search-response.v1",
  "status": "READY",
  "reasons": [],
  "query_id": "core-search-…",
  "normalized_request": {"…": "去掉 session_ref 的請求，class alias 已正規化"},
  "resolved_time": {"timezone": "Asia/Taipei", "wall_range": ["…", "…"], "source_range_us": [0, 1800000000],
                    "clock_id": "…", "clock_mapping_sha256": "…", "coverage_complete": true},
  "resolved_scope": {"scene_id": "…", "run_id": "…", "region_graph_sha256": "…", "camera_graph_sha256": "…",
                     "detection_index_sha256": "… 或 null", "query_min_score": 0.5},
  "hits": [
    {"rank": 1, "camera_id": "CAM_R101_IN", "target_observed": true,
     "source_range_us": [120000000, 180000000],
     "wall_range": ["2026-11-01T13:02:00+08:00", "2026-11-01T13:03:00+08:00"],
     "segments": [{"range_us": [120000000, 180000000], "matched_frames": 12,
                   "representative": {"frame_ref": "…", "observation_ids": ["…"], "media_token": "…"}}],
     "basis": [
       {"kind": "LOCATION", "region_id": "R101", "coverage_basis": "MANUAL_ON_STATIC_FRAME",
        "visibility_ref": "static-review:v3:CAM_R101_IN:R101"},
       {"kind": "OBJECT", "class_label": "person", "color_label": "red", "evidence_state": "OBSERVED",
        "observation_ids": ["…"], "detection_index_sha256": "…"}
     ]}
  ],
  "not_evaluated_cameras": [{"camera_id": "…", "reason": "INCOMPLETE_COVERAGE"}],
  "identity_verdict": "UNCONFIRMED",
  "provenance": {"producer": "q-core-search", "gt_read": false, "q1_query_id": "… 或 null"},
  "output_sha256": "…"
}
```

- `status` 封閉清單：`READY`（有命中）、`NO_MATCH`（完整評估、無命中）、`PARTIAL`（時間只部分涵蓋、圖或參數未核准、索引有缺；`reasons` 說明，沿用 Q1 的 reason 名稱與排序）、`OUT_OF_RANGE`（時間不在 run 內）、`UNKNOWN`（缺索引、缺時鐘等，`reasons` 說明）。地點-only 查詢不需要索引，不因缺索引變 UNKNOWN。
- `hits[].camera_id` 必須在 camera graph 裡；`wall_range` 由宣告時鐘從 `source_range_us` 換算，UI 標「展示時鐘」。
- `output_sha256 = canonical_hash(response, exclude=('output_sha256','stats'))`。

## 3. case2 追蹤（`q_core_track`）

### 3.1 請求

```json
{
  "schema_version": "q-core.track-request.v1",
  "session_ref": "…", "scene_id": "…", "run_id": "…",
  "feature": {"class_label": "person", "color_label": "red"},
  "region_ids": [],
  "time": null,
  "playback_now_us": 42000000
}
```

| 欄位 | 規則 |
| --- | --- |
| `feature` | **必填**，規則同 §2.1。缺或 `null` 回 422 `FEATURE_REQUIRED` |
| `region_ids` | 可為 `[]`。非空時只從涵蓋這些區域的鏡頭（§2.2 地點規則）挑起點 |
| `time` | `null` 表示「現在」：用 `playback_now_us`（回放時鐘目前時間，整數微秒，必填）；視窗為 `[max(0, now − track_lookback_us), now)`，`track_lookback_us` PROPOSED 預設 60 000 000。非 null 時同 §2.1 的 WALL 範圍，此時 `playback_now_us` 可省略，`as_of_us` 取範圍結束 |
| 不看未來 | 回應只能用 `source_time_us < as_of_us` 的證據（回放時不偷看之後的畫面） |

### 3.2 類別支援

追蹤建立在現有 Q2 同鏡頭 IoU 連接器（`linker.py`，契約 §8.2）上，目前**只支援 `person`**。其他 COCO 類別回 **200**，`status: UNSUPPORTED`、`reasons: ["CLASS_NOT_SUPPORTED_BY_LINKER"]`，`sightings`、`multi_view`、`single_view` 都是空陣列，`blind` 為 `null`。不得用偵測索引假裝有追蹤結果。不在 class map 的類別仍是 422 `UNSUPPORTED_CLASS`。

### 3.3 驗證錯誤代碼（422）

`FEATURE_REQUIRED`、`NOW_REQUIRED`（`time` 為 null 但沒有 `playback_now_us`，或不是非負整數）、以及 §2.3 的時間、區域、類別、顏色代碼。

### 3.4 回應

```json
{
  "schema_version": "q-core.track-response.v1",
  "status": "TRACKING",
  "reasons": [],
  "as_of_us": 42000000,
  "resolved_time": {"kind": "PLAYBACK_NOW", "source_range_us": [0, 42000000], "clock_mapping_sha256": "…"},
  "sightings": [
    {"camera_id": "CAM_W1", "range_us": [3000000, 9000000], "evidence_state": "OBSERVED",
     "observation_ids": ["…"], "track_ref": "…"}
  ],
  "multi_view": [{"camera_id": "CAM_W1", "first_us": 3000000, "last_us": 9000000}],
  "single_view": [
    {"kind": "ON_CAMERA", "camera_id": "CAM_W1", "range_us": [3000000, 9000000], "evidence_state": "OBSERVED"},
    {"kind": "GAP", "camera_id": null, "range_us": [9000000, 15000000], "evidence_state": "UNKNOWN"},
    {"kind": "ON_CAMERA", "camera_id": "CAM_W2", "range_us": [15000000, 30000000], "evidence_state": "OBSERVED"},
    {"kind": "LOST", "camera_id": null, "range_us": [30000000, 42000000], "evidence_state": "UNKNOWN"}
  ],
  "blind": {"status": "UNAVAILABLE", "reason": "PREDICTION_UNAVAILABLE", "estimate": null},
  "identity_verdict": "UNCONFIRMED",
  "physical_navigation": "UNKNOWN",
  "provenance": {"producer": "q-core-track", "gt_read": false, "linker": "q2-iou-linker"},
  "output_sha256": "…"
}
```

- **「完全跟丟」的定義**：`as_of_us` 之前最後一段 sighting 結束後，到 `as_of_us` 為止沒有任何鏡頭再看到目標，就標 `LOST`（§3.5 規則 6）。不另設逾時或輪數；Q2／Q5 狀態機的 W、R、`session_max_research_rounds` 不在核心追蹤使用。
- **預錄／合成資料的「現在」**：就是前端回放時鐘的目前來源時間 `playback_now_us`；伺服器不自己推「現在」。
- 圖未核准（DRAFT）時：`sightings` 與 `single_view` 照常（它們是觀測，不靠圖切鏡），`status` 不變但 `reasons` 加 `GRAPH_NOT_APPROVED`；只有用到圖的 `blind` 與 `region_ids` 起點篩選受影響。
- `status` 封閉清單：`TRACKING`（`as_of_us` 時仍有鏡頭看到）、`LOST`（最後一段是 `LOST`）、`NO_SIGHTING`（視窗內沒找到）、`UNSUPPORTED`（§3.2）、`PARTIAL`、`UNKNOWN`。
- `sightings`：每段是連接器在單一鏡頭串起來的觀測區間，`range_us` 半開，`range_us[1] ≤ as_of_us`。這是**多畫面**輸出的來源。
- `multi_view`：所有在視窗內有 sighting 的鏡頭，依 `first_us`、`camera_id` 排序。
- `single_view`：由 `sightings` 經 §3.5 純函式得出；伺服器輸出必須等於前端 `singleViewSequence(sightings, {asOfUs})` 的結果（同一規則，兩邊都有測試）。
- `GAP`／`LOST` 段的 `camera_id` 一律 `null`，觀測層不畫位置；盲區位置只出現在 `blind`，且一定是 `INFERRED`。

### 3.5 單畫面切鏡規則（純函式）

輸入 `sightings`（每筆 `{camera_id, range_us:[a,b]}`）與 `asOfUs`。

1. 丟掉 `a ≥ asOfUs` 的 sighting，`b` 截到 `asOfUs`；丟掉截完後 `a ≥ b` 的。
2. 起點：取最早開始者；同時開始取結束最晚者；再同就取 `camera_id` 字典序最小。
3. 目前鏡頭還看得到就不換（不因為別的鏡頭也看得到而跳動）。
4. 目前片段在 `t` 結束時，從「`a ≤ t < b`」的 sighting 中選結束最晚者（同分取 `camera_id` 最小），立即接上，不插 GAP。
5. `t` 沒有任何鏡頭看到：若之後還有 sighting，插一段 `GAP [t, 下一段開始)`，下一段依規則 2 選。
6. 最後一段結束在 `t_end < asOfUs`：補一段 `LOST [t_end, asOfUs)`；`t_end == asOfUs` 時不補（仍看得到）。
7. 相鄰且同鏡頭的 `ON_CAMERA` 段合併。沒有任何 sighting 時回空陣列。
8. `ON_CAMERA` 段 `evidence_state: OBSERVED`；`GAP`、`LOST` 段 `UNKNOWN`、`camera_id: null`。

### 3.6 盲區（`blind`）

- 只有 `single_view` 的最後一段是 `GAP` 或 `LOST` 時才需要盲區；否則 `blind: null`。
- 呼叫內部的物理預測（`physical_prediction.predict_next_cameras`，輸入只有偵測框、camera graph、靜態顯示座標；不得用 GT 等）。
- 預測服務還沒接上（`q_physical_prediction` 回 503）時：`blind = {"status": "UNAVAILABLE", "reason": "PREDICTION_UNAVAILABLE", "estimate": null}`，追蹤回應照常回 200，**不得**捏造位置或曲線（fail-closed）。
- 接上後：`blind = {"status": "ESTIMATED", "reason": null, "estimate": <§4.4>}`。

## 4. 物理預測接上後的形狀

### 4.1 路由與既有契約

`q_physical_prediction` 的請求與回應維持 [`DEMO_UI_SUPPORT_V1`](DEMO_UI_SUPPORT_V1.md) §6.4：請求 `{"session_ref", "response_ref", "as_of_us"}`，接上後回 `q-demo.physical-prediction.v1`（等於 `predict_next_cameras` 的輸出，既有測試 `test_demo_physical_route_t.py` 管）。本契約不改它，只定義核心追蹤怎麼包裝它：`q_core_track` 的 `blind.estimate = core_query.blind_estimate(<physical-prediction 文件>)`。

### 4.2 錯誤與 fail-closed

| 情況 | 行為 |
| --- | --- |
| `q_physical_prediction` 尚未接上（不在 `POST_ROUTES`，呼叫回 503 `Q_RESOURCE_UNAVAILABLE`） | `q_core_track` 的 `blind` 必須是 `UNAVAILABLE`／`PREDICTION_UNAVAILABLE`／`estimate: null`；UI 顯示「預測不可用」，不畫任何曲線 |
| 參數錯 | 422 `FORBIDDEN_INFERENCE_INPUT` |
| 不是自己的 session／response | 403 `FORBIDDEN_DATA_SCOPE` |
| 底層預測 `status` 是 `CAMERA_NOT_IN_GRAPH`／`NO_CANDIDATE` | `estimate.candidates: []`、`confidence: UNKNOWN` |

### 4.3 低信心規則

不論底層 `predict_next_cameras` 的 candidate confidence 是 HIGH／MEDIUM／LOW，核心輸出的 `confidence` **一律 `LOW`**（沒有足夠速度樣本時為 `UNKNOWN`），底層值放在 `model_confidence` 供除錯。

### 4.4 `estimate` 形狀（`q-core.blind-estimate.v1`）

```json
{
  "schema_version": "q-core.blind-estimate.v1",
  "evidence_state": "INFERRED",
  "confidence": "LOW",
  "used_for": "DISPLAY_ONLY",
  "display_label": "物理預測（示意，非實際路徑）",
  "as_of_us": 42000000,
  "last_observed": {"camera_id": "CAM_W1", "source_time_us": 30000000},
  "overhead": {"frame": "STATIC_PLAN_DISPLAY", "last_position": [12.5, 3.0] , "region_id": "CORR_W"},
  "curve": {"basis": "DISPLAY_POSITIONS_STRAIGHT_LINE", "points": [[12.5, 3.0], [18.0, 3.0]]},
  "candidates": [{"camera_id": "CAM_W2", "rank": 1, "window_us": [31000000, 40000000],
                  "confidence": "LOW", "model_confidence": "MEDIUM"}],
  "prediction_ref": {"schema_version": "q-demo.physical-prediction.v1", "content_sha256": "…"},
  "identity_verdict": "UNCONFIRMED", "physical_navigation": "UNKNOWN", "gt_read": false,
  "content_sha256": "…"
}
```

- `overhead.last_position`、`curve.points` 只能來自靜態顯示座標（場景平面圖上的鏡頭／區域顯示點）；沒有時為 `null`／`[]`，`curve.basis: NODE_GRAPH_ONLY`。不得用渲染軌跡或 depth 算位置。
- `evidence_state` 固定 `INFERRED`；UI 用虛線、低對比色，圖例寫「推論（低信心）」，不得和觀測同色同線型。
- 純函式入口：`core_query.blind_estimate(prediction_doc, *, display_positions=None)`，把 `q-demo.physical-prediction.v1` 轉成本形狀。`candidates` 保留底層順序與 `rank`、`camera_id`、`window_us`。

## 5. 前端（`frontend/workbench-v2/`）

新增純模組 `core-search-track-model.mjs`，匯出：

| 匯出 | 規則 |
| --- | --- |
| `regionOptions(regionGraph)` | 依 `regions[]` 順序回 `[{value: region_id, label}]`；`label` 用圖中的 `display_name`，沒有就用 `region_id` |
| `featureOptions(classLabels, colorLabels)` | `{classes: [...classLabels], colors: [...colorLabels]}`；不寫死類別 |
| `buildCoreSearchRequest(run, session, form, menus)` | `form = {start, end, regionIds, classLabel, colorLabel}`；`menus = {regions: regionOptions(...), classes, colors}`；`start`／`end` 收 `HH:MM` 或 `HH:MM:SS`（以 `run.clock_mapping.wall_origin` 的日期與偏移、`timezone` 補成完整 ISO）或完整 ISO；違反 §2.3 時 `throw new Error(code)`；回 §2.1 請求 |
| `buildCoreTrackRequest(run, session, form, menus, playbackNowUs)` | `form = {regionIds, classLabel, colorLabel, start, end}`；`start`、`end` 都空時 `time: null`、帶 `playback_now_us`（非負安全整數，否則 `NOW_REQUIRED`）；缺特徵 `throw new Error('FEATURE_REQUIRED')` |
| `trackClassSupport(classLabel)` | `person` → `'SUPPORTED'`，其他 → `'UNSUPPORTED'`（UI 預先提示；伺服器仍是最終判定） |
| `singleViewSequence(sightings, {asOfUs})` | §3.5 |
| `multiViewCameras(sightings, {asOfUs})` | §3.4 `multi_view` |
| `ERROR_TEXT` | 每個 §2.3／§3.3 代碼都有繁中訊息 |

- `run` 物件沿用 `q_bootstrap` 的 run（`scene_id`、`run_id`、`clock_mapping`）。選單來源：區域來自 region graph（bootstrap 要提供 region graph 的 `regions[]` 或等價清單），類別與顏色來自 `supported_classes`。
- 單畫面切鏡的測試向量放在 [`tests/q1q5/fixtures/core_single_view_vectors.synthetic.json`](../../tests/q1q5/fixtures/core_single_view_vectors.synthetic.json)，Python 與前端讀同一份。
- 盲區畫面：`blind.status == UNAVAILABLE` 時顯示「預測不可用」，不畫曲線；`ESTIMATED` 時用虛線畫 `curve.points`，標「推論（低信心）」。

## 6. Python 純模組（`src/amidst/q1q5/core_query.py`）

讓驗收測試不必起伺服器也能測規則：

| 函式 | 規則 |
| --- | --- |
| `CoreRequestError(code)` | `ValueError` 子類，帶 `.code` |
| `validate_search_request(request, *, region_ids, class_labels, class_aliases, color_labels, clock_mapping)` | §2.1／§2.3；回正規化後的請求（alias 轉成 class label） |
| `validate_track_request(request, *, …同上…)` | §3.1／§3.3 |
| `location_hits(camera_graph, region_ids, *, run_camera_ids=None)` | §2.2 地點規則（`run_camera_ids` 為 None 時不檢查 run 目錄）；回 `{"hits": {camera_id: [basis…]}, "not_evaluated": [{camera_id, reason}]}` |
| `intersect_hits(location, objects)` | 兩邊都有才留；`basis` 合併，順序 LOCATION 在前 |
| `single_view_sequence(sightings, *, as_of_us)` | §3.5，輸出與前端一致 |
| `blind_estimate(prediction_doc, *, display_positions=None)` | §4.3／§4.4；`prediction_ref.content_sha256` 等於輸入文件的 `content_sha256`；`content_sha256 = canonical_hash(estimate, exclude=('content_sha256',))` |

## 7. 驗收測試與 skip 規則

- 依賴未實作模組或路由的測試用 `demo_ui_support_helpers.missing(code)`：預設 **skip**，`AMIDST_REQUIRE_IMPL=1` 時改為 **fail**。Codex 完成後以 `AMIDST_REQUIRE_IMPL=1` 跑，0 skip、0 fail 才算過。
- node 測試相同：模組不存在時 `t.skip(code)`，`AMIDST_REQUIRE_IMPL=1` 時 fail。
- skip 代碼：`CORE_QUERY_MODULE_MISSING`、`CORE_SEARCH_ROUTE_MISSING`、`CORE_TRACK_ROUTE_MISSING`、`CORE_FRONTEND_MODEL_MISSING`、`SCENE_ROOM_COVERAGE_PENDING`（場景擴充：每個 `ROOM` 區域至少有一個 `MANUAL_ON_STATIC_FRAME` 室內鏡頭）。
- 已經能通過的測試（不 skip）：`q_physical_prediction` 目前的 503 fail-closed、合成 fixture 與向量檔的自我一致性、region graph 與 camera graph 的參照一致性。

## 8. 待決（不阻擋實作）

| # | 問題 | 提案 |
| --- | --- | --- |
| O1 | 多 run 查找 | v1 只收單一 `run_id`；多 run 另議 |
| O2 | `track_lookback_us` 數值 | PROPOSED 預設，寫進參數集；核准前回應帶 `PARAMETERS_NOT_APPROVED` |
| O3 | 非人物追蹤 | 待連接器支援後另立 v2；v1 回 UNSUPPORTED |
| O4 | 多教室靜態顯示座標的來源 | Codex 擴充場景時一併提供靜態平面圖顯示點（非渲染軌跡） |


### D145：D124 demo replay 的同鏡頭重現（2026-11-09）

此項僅適用 `demo-cross-camera-local-linker` 的 DEMO_DEFAULT replay，不改一般
`execute_core_track`、G4、原索引或既有首段產物。loader 以原 hash 綁定 records／config
重播全部 camera-local IoU 候選；首段結束或未匹配的合格觀測可以建立新的 local track_ref，
不復活舊 local segment。IoU、分數、取樣、最大局部缺口與歧義門檻保持原值；無最短段長。
多個種子／前驅爭用同一觀測保持 UNKNOWN，不以 camera_id 排名挑身分。

使用者 D145 授權：同鏡頭的新段可作重現候選，須符合既有 `handoff_max_gap_us = 6000000`、
`min_score = 0.4` 與共享非 NONE 顏色條件；使用新的 track_ref，不需要也不新增 self edge。
跨鏡頭仍須既有有向圖邊、同一時間窗與顏色條件。超窗、缺偵測、低於門檻或歧義都不硬接。
仍為條件相符候選，`identity_verdict = UNCONFIRMED`，`physical_navigation = UNKNOWN`。

Demo `sightings[].link_kind` 明列 `LOCAL_SEED`、`SAME_CAMERA_REACQUISITION` 或
`CROSS_CAMERA_HANDOFF`；同鏡頭重現時 top-level reasons 也含 `SAME_CAMERA_REACQUISITION`。
`single_view` 維持 §3.5 的純切鏡格式，可依重疊的 sightings／track_ref 區分重現，
不能把相鄰 ON_CAMERA 顯示合併當成相同身分。回應的 `association_audit` 與獨立 events 同步記錄 link_kind、
from_track_ref、to_track_ref、transition_id（同鏡頭為 null）及 gap_us。
此授權不放寬 6 秒窗、不核准圖、不觸發重新推論、不改 formal_eligible=false。

### D147／D148：跟丟後全程重掃、短缺口合併、不分類別框接續（2026-11-09，Codex 依指派確認）

只適用 DEMO_DEFAULT replay（同 D145 範圍）。驗收測試：`tests/q1q5/test_d147_acceptance.py`。

- **全程重掃（D147-1）**：跟丟（LOST）或遇到歧義後，查詢時段剩下的每一格都重新檢查所有鏡頭。第一個通過既有分數與顏色條件的候選就採用，不受 6 秒窗限制，也不需要圖邊。`sightings[].link_kind` 以 `REACQUISITION` 結尾（同鏡頭沿用 `SAME_CAMERA_REACQUISITION`；跨鏡頭用 `CROSS_CAMERA_REACQUISITION`）；`identity_verdict = UNCONFIRMED`、`physical_navigation = UNKNOWN`。歧義照樣寫進 `association_audit` 與 `reasons`，但追蹤繼續。6 秒窗內、有圖邊的接手仍標 `CROSS_CAMERA_HANDOFF`。
- **短缺口合併（D147-1）**：同一鏡頭相鄰的 ON_CAMERA 之間，缺口 ≤ 600000 µs 時，`single_view` 合併成一段。`sightings` 仍保留各自的 track_ref；這是顯示上的合併，不代表身分相同（D145 的限制不變）。
- **不分類別框接續（D148）**：camera-local 候選的起點是 person、分數 ≥ 0.3（索引下限），而且要有顏色判定（STRONG／WEAK）。之後任何類別、分數 ≥ 0.3 的框，只要 IoU ≥ 0.2 或中心距離 ≤ 0.6 倍參考框高，且面積在參考框的 1/12～12 倍之間，就可以接續。多個框符合時，取成本 `(1−IoU) + |ln(面積比)|/2 + 中心距離/框高` 最低者，成本相同時優先 person。參考框取勝出框的中心，尺寸只往新框移動一半。連續 2 格沒對到就結束。參考實作：`src/amidst/evaluation/track_recall.py::box_continuation_frames`（q1q5 不得 import 它，需要自行實作）。
- 由非 person 框接續的觀測，在 `association_audit` 標 `evidence_kind: "BOX_CONTINUATION"`，並附原始 `class_label`；顏色寫 `NOT_EVALUATED`，不能算顏色相符。`single_view` 照常為 ON_CAMERA。
- 驗收門檻：`configs/evaluation/d147_human_reference_v1.json` 每個參考段的召回率 ≥ 0.75（以 `score_single_view` 計算）。人工參考只用來評估，q1q5 不得讀取。

### D149：場景標註的靜態物件（2026-11-09，Codex 依指派確認）

偵測器認不出場景裡的方塊車（A4 CAM_EXT_CAR，250 格中沒有任何 car）。使用者決定改用場景標註：`configs/q1q5/scene_annotations_v1.json`（`q-demo.scene-annotations.v1`）。

- **查找**：`feature.class_label` 等於某筆標註的 `class_label`，且標註的 `run_id`、`camera_id` 在查詢範圍內時，回一筆命中：`target_observed: true`；`source_range_us` 取標註範圍與查詢時段的交集；`segments` 為一段，`representative` 取交集內第一格的 `frame_ref` 與 `media_token`（`observation_ids: []`）。`basis` 新增一種：
  `{"kind": "SCENE_ANNOTATION", "class_label": "car", "annotation_id": "…", "annotation_set_sha256": "<設定檔 SHA-256>", "evidence_state": "ANNOTATED"}`。
  同一鏡頭若同時有偵測命中，兩種 basis 都列。有地點條件時，依 §2.2 與地點命中取交集。
- **不混入偵測**：標註不進 `detected_class_counts`、不進索引，追蹤、排序與身分判斷都不使用。bootstrap 每個 run 另外列 `scene_annotations: [{"annotation_id", "class_label", "camera_ids"}]`（沒有時為 `[]`）。
- **前端**：命中卡片顯示「場景標註：車輛（非偵測）」；查找窗的場景物件鏡頭數，取偵測鏡頭與標註鏡頭的聯集，提示文字註明含場景標註。
- 標註框只用於顯示，不得當成偵測或位置證據；`identity_verdict` 仍為 `UNCONFIRMED`。

### D150：重疊鏡頭的雙指標驗收（2026-11-09，使用者決定）

適用 D147/D148 DEMO_DEFAULT replay；不改一般核心追蹤或原始索引。

- `sightings` 保留同時鏡頭的 camera-local 觀測假設。`selected_for_single_view: true`、
  `association_state: SELECTED_HYPOTHESIS` 表示選中的關聯鏈；其餘明列
  `selected_for_single_view: false`、`association_state: UNASSOCIATED_LOCAL_CANDIDATE`。
  後者只保留與起點共享非 NONE 顏色的局部候選，不確認身分，也不以顏色未驗證的非人物框建立 seed。
- DEMO_DEFAULT 的 `single_view` 以選中鏈的 sightings 產生（同鏡頭短缺口合併上限 600000 µs）；
  不把多畫面中保留的重疊候選強行當成單一身分。歧義不中止後續掃描。
- 每鏡頭召回：每個參考區間中，被該鏡頭實際 sighting 覆蓋的索引幀數 ÷ 參考幀數 ≥ 0.75。
  WIDE 與 BRANCH 分開算；顯示用短缺口合併不補 sighting，也不替此指標加分。
- 單畫面切鏡比例：該 run 所有參考區間的時間聯集中，`single_view` 為 ON_CAMERA 且鏡頭屬於
  當下參考鏡頭集合的時間比例 ≥ 0.75；重疊時間只計一次，以整數微秒區間計算。
- 短缺口驗收只檢查 GAP 前後是同一鏡頭的情形，此種 GAP 必須 > 0.6 s；跨鏡頭 GAP 無此限制。
- 評估函式 `score_sightings`、`score_single_view_switching` 留在 evaluation；人工參考檔不變，
  追蹤不讀取它。`scripts/eval_d147_recall.py --track ...` 同時列出兩張表。
- 原凍結設定仍保留；D148 replay 的明確覆寫為 seed/continuation 分數 0.3、面積比 12、
  IoU 0.2、中心距 0.6×高、尺寸平滑 0.5、最多容許 2 個漏格（第 3 個結束）。
  回應 provenance 明列此 replay policy；不宣稱正式參數已核准。
