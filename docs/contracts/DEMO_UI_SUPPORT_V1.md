# Demo UI 支援介面 v1（DEMO_UI_SUPPORT_V1）

- **狀態：PROPOSED**。Claude 起草，Codex 確認後才生效（AGENTS.md「介面契約由 Claude 起草、Codex 確認」）。確認前，本文件定義的路由、欄位、模組都只是提案；實作只能做成可設定的開關，預設 fail closed（#306 §3）。
- 日期：2026-11-01。起草：Claude Opus 5.5／high。
- 基準：產品程式 `codex/q1q5-staging`@`434e57922a24d2422226871c0bb672dc7bc3584b`；架構基準 #306；流程 #93 D104～D106；D107（OpenAI 只作俯視圖輔助推測，預設關閉，錄製重播）。**撰寫時 #93 上還沒有 D107 的留言**，本文件依協調 session 轉述的 D107 內容起草；D107 貼出後若有出入，以 D107 為準並回修本文件。
- 來源需求：demo 缺口報告 G5（俯視圖）、G6（預測虛線）、G7（後台標題），以及使用者的 demo 要求「追蹤單畫面自動切鏡並顯示俯視圖與預測虛線」「後台選預設事件與查找模擬錄製」。

## 0. 不變條件（每一節都適用）

1. **GT 隔離**：Ground Truth、渲染軌跡、visibility、depth、劇本（含 t_X／t_N、評分窗）、actor 資訊不進入本文件的任何輸入、輸出或外部請求（DEVELOPMENT_RULES、#306 §2）。
2. 身分一律 `UNCONFIRMED`；物理通行與碰撞 `UNKNOWN`（輸出欄位 `physical_navigation: "UNKNOWN"`）。observed、inferred、`MISSING`、`UNKNOWN` 分開。
3. 本文件的輸出**只用於畫面示意**（`used_for: "DISPLAY_ONLY"`），不進 Q1～Q5 判斷、不進 Q5 切鏡（D64 的 Agent 例外不延伸到這裡）、不進評分、不改候選集合或排序。
4. **回放不洩漏未來**：凡是帶 `as_of_us` 的介面，只能使用 `source_time_us ≤ as_of_us` 的資料；系統在 t 時刻已算出的預測窗（例如候選快照的 `window_us`）可以指向 t 之後，那是當時的預測，不是後見之明。
5. 不新增 authority：圖的 `DRAFT`、邊的 `UNKNOWN`、G4 未生效都照實傳到前端；前端不得把 `TOPOLOGICAL_ONLY` 畫成可通行路徑。
6. 前端只經 HTTP API 或錄製回應取得資料（#306 §2 UI 列）；不直接讀 `configs/`、GT 或劇本。

## 1. 共用規則

| 項目 | 規則 |
| --- | --- |
| 路由 | 新路由都加進 `src/amidst/q1q5/api.py` 的 `POST_ROUTES`，payload 一律 JSON 物件，欄位集合**完全相等**檢查（多欄位就拒絕）。 |
| 授權 | 新路由都用 `self._authorize(session_ref, scene_id, authorize)`，**`audit=False`**（非 review 模式）。review 專用路徑（`q2_artifact` kind=snapshot 等）不變。 |
| 錯誤 | 沿用 `APIError`：欄位或型別不符 422 `FORBIDDEN_INFERENCE_INPUT`；越權 403 `FORBIDDEN_DATA_SCOPE`；run 未設定 503 `Q_RUN_NOT_CONFIGURED`；完整性 409 `DataIntegrityError`。 |
| `as_of_us` | 非負 `int`（`bool`、浮點、字串都 422）。 |
| 雜湊 | `content_sha256` 用 `amidst.q1q5.store.canonical_hash(doc, exclude=("content_sha256",))`。 |
| 禁用鍵 | 至少 `ground_truth`、`gt`、`gt_*`（前綴）、`actor`、`actor_id`、`material_id`、`event_script`、`script`、`renderer_trajectory`、`trajectory`、`visibility`、`depth`、`mask`、`private_evaluation`、`production_manifest`；以**整個鍵名**比對（不做子字串，避免 `visibility_ref` 這種既有圖欄位被誤殺）。出現就 fail closed，錯誤碼 `FORBIDDEN_INFERENCE_INPUT`。 |
| 標籤 | 輸出固定帶 `identity_verdict: "UNCONFIRMED"`、`physical_navigation: "UNKNOWN"`、`gt_read: false`。 |

## 2. (a) 鏡頭圖 API

### 2.1 來源

| 場景 | 圖 | pin（檔案 bytes SHA-256） | 鏡頭示意座標 |
| --- | --- | --- | --- |
| r004 | `configs/q1q5/graphs/r004/camera_graph_v3_1.json`、`region_graph_v3_1.json`（#306 A17，PROPOSED_PARTIAL，G4 前） | `e250413a0d0a2aeb61bd98bb1763236b1e39127f919cee1ee3ca3bd906b78409`、`a2f737805cf5446c6ba01fa4bebfddd2186d040cbd94314cf573c082191b24e1` | **UNKNOWN**：圖裡只有 `calibration_sha256`，repo 沒有 r004 的校正檔或相機位姿。前端退回節點圖。 |
| r004 tracking scope | `tracking_scope_v3_1.json`（#294@`0c34287`） | `ed5b68995094b060b21a9dba6a05e26a21aa0af15c0f8dcb7fd0bd56424af80a` | — |
| P1 工程場景 | `docs/history/q1q5_ab_gap_20261025/audit.json` 的 `graph_caveat`（approval_ref `SYNTHETIC_ENGINEERING_ONLY`） | `80fe6aee4e8f778d22b18b4f1184600eda20abbf5691db83a761aaf5336408a4` | 同檔 `camera_calibration.*.position` 的 x、y（A≈(2.0,−5.5)、B≈(16.0,−5.5) m）。靜態校正，沒有讀 actor／動畫（檔內 `gt_or_private_motion_read` 與 `topdown-static.json` 的 `actor_objects_read=false`）。 |

- v3_1 目前只在 #294（`codex/cq01-r004-v3-yyin-exits`，未合併），staging 只有 v3。實作本節的 feature 必須帶入 #294；-T 在 strict 模式下沒有 v3_1 會以 `R004_V3_1_GRAPH_NOT_IN_TREE` 失敗。
- tracking scope v3_1 的 SHA 不在 #306 的權威表裡，**由協調者決定是否補登**；補登前它只是本文件引用的 #294 head 值。
- 已知不一致（照實顯示，不修正）：r004 的 run `r004_a4_v1.json` 有 `CAM_ENTRY`，v3_1 圖沒有這台；tracking scope 把它列為 `query_only_camera_ids`（D74）。

### 2.2 純函式（Codex 實作）

`src/amidst/q1q5/camera_map.py`

```python
class CameraMapError(ValueError):  # 有 .code
    ...

def build_camera_map(*, scene_id, run_id, camera_graph, region_graph,
                     camera_graph_sha256, region_graph_sha256, run_camera_ids,
                     tracking_scope=None, tracking_scope_sha256=None,
                     display_positions=None) -> dict
```

- `camera_graph_sha256`／`region_graph_sha256` 是圖的 `content_sha256`（和 run binding、bootstrap 同一套）。重算不符或互相引用不符 → `GRAPH_PIN_MISMATCH`。禁用鍵 → `FORBIDDEN_INFERENCE_INPUT`（先於 pin 檢查）。
- `display_positions`：`{camera_id: {"xy_m": [x, y], "basis_ref": str, "basis_sha256": str}}`。camera 不在圖或 run 裡、座標不是兩個有限數 → `DISPLAY_POSITION_INVALID`；`basis_ref` 的路徑段落含 `gt`、`private`、`trajectory`、`ground_truth` 等 → `FORBIDDEN_INFERENCE_INPUT`。
- 不讀檔、不連網；同輸入同輸出；`run_camera_ids` 的順序和重複不影響結果。

### 2.3 輸出 `q-demo.camera-map.v1`

| 欄位 | 內容 |
| --- | --- |
| `schema_version`、`scene_id`、`scene_revision`、`run_id` | — |
| `graph` | `camera_graph_sha256`、`region_graph_sha256`、`camera_graph_id`、`approval_status`、`approval_ref`、`tracking_scope_sha256`、`tracking_scope_status`（`PROPOSED`／`APPROVED`／`NONE`）、`g4_approved`（bool） |
| `layout` | 所有鏡頭都有示意座標 → `METRIC_STATIC`；否則 `NODE_GRAPH` |
| `display_note` | `NODE_GRAPH`：「示意圖，非實際座標」；`METRIC_STATIC`：「靜態校正位置（示意，無遮擋計算）」 |
| `cameras[]`（依 `camera_id` 排序；圖裡的鏡頭 ∪ run 的鏡頭） | `camera_id`、`in_graph`、`role`（`TRACKING`／`QUERY_ONLY`／`NOT_IN_GRAPH`）、`covered_region_ids`、`exits[]`（只有 `exit_zone_id`、`leads_to_edge_ids`）、`display_position`（`status` `CALIBRATED_STATIC`／`UNKNOWN`、`xy_m`、`basis_ref`、`basis_sha256`；UNKNOWN 時後三者為 null） |
| `regions[]` | `region_id`、`kind` |
| `edges[]` | `edge_id`、`regions`、`state`（照圖，r004 全是 `UNKNOWN`）、`traversability`、`direction` |
| `transitions[]`（依 `transition_id` 排序） | `transition_id`、`from_camera_id`、`to_camera_id`、`relation`、`path_traversability`、`path_has_unknown_state`、`via_exit_zone_ids`、`to_entry_zone_ids`、`edge_path`、`region_path`、`edge_states`、`authority` |
| `identity_verdict`、`physical_navigation`、`gt_read`、`content_sha256` | 見 §1 |

- `authority`：兩張圖都 `APPROVED`，且（沒有 tracking scope，或 scope `status=APPROVED` 且 `G4_approved=true`）才是 `APPROVED`，否則 `DRAFT`。所以 r004 v3_1 的 22 條轉移全是 `DRAFT`，連 `T_CAM_W1__CAM_W2`（圖上 `APPROVED_WALKABLE`）也是。
- 輸出**不帶**像素 ROI、靜態影格 ref／hash、`calibration_sha256`、`visibility_ref`：前端用不到，少一層外流面。

### 2.4 路由 `q_camera_map`

- payload：`{"session_ref", "scene_id", "run_id"}`。
- live run：由 run binding 的 `graphs`、pins、`tracking_scope` 與 `index.manifest.sampling.per_camera` 組圖，示意座標取 `QAPI(..., camera_display_positions={(scene_id, run_id): {...}})`。回應的兩個 graph SHA 必須等於 bootstrap 該 run 的值。
- 錄製重播（沒有 live run）：`QAPI(..., camera_maps=[doc, ...])` 傳入預先建好的地圖。建構時驗 `content_sha256`；若同 scene/run 的錄製 `resolved_scope.camera_graph_sha256` 不為 null，必須相等；任何不符 409。
- bootstrap 新增 `camera_maps: [{"scene_id", "run_id", "layout"}]`（只列錄製模式預建的地圖）。
- 未知 run 503 `Q_RUN_NOT_CONFIGURED`；越權 403。

## 3. (b) 錄製索引的人類可讀標題

- 標題由**伺服器端的錄製 pin** 帶入：`QAPI(recordings=[{"recording_id", "file", "file_sha256", "title"?}])`，`title` 可省略。來源是啟動器／後台設定（#338 的錄製清單），不是前端 payload。
- `api.RECORDING_TITLE_MAX_CHARS = 80`。`title` 必須是 1～80 字、去空白後非空、全部可列印（不含換行、tab、控制字元）；明寫 `null`、非字串都算不合法。不合法 → 建構時 409。其他多出的 pin 鍵仍拒絕。
- bootstrap 的 `recordings[]` 每列加 `title`（無則 null）與 `title_source`（`RECORDING_INDEX`／`UNTITLED`）。其他欄位不變。
- 標題**不寫進錄製檔**，不改 `file_sha256`、`content_sha256`，`q_recorded_response` 回放的 response 不含標題。`q_record_response` 不接受 `title`。
- 標題內容由設定者負責：只寫場景、run、操作類型與來源類別（例如「P1 工程場景・追蹤 A→B（SYNTHETIC）」），**不得寫劇本內容**（actor、t_X、預期答案）。

## 4. (c) 回放時的候選快照唯讀檢視

目前前端只在 `?mode=review` 才讀候選快照（`app.mjs` 的 `REVIEW_ONLY`；API 端 `q2_artifact` 讀 snapshot 時要求 audit 角色）。本節新增一條**非 review** 的唯讀路徑，欄位白名單如下；review 路徑不變。

### 4.1 純函式（Codex 實作）

`src/amidst/q1q5/candidate_view.py`：`candidate_view(*, snapshots, decisions_jsonl, as_of_us, response_ref) -> dict`

- 一個快照只有在某一筆 decision 的 `candidate_snapshot_sha256` 指向它、且該 decision 的 `source_time_us ≤ as_of_us` 時才出現；`first_decision_source_time_us` 取這些 decision 的最小 `source_time_us`。沒被任何 decision 引用的快照永遠不出現。
- 依 `(first_decision_source_time_us, candidate_snapshot_sha256)` 排序。

### 4.2 輸出 `q-demo.candidate-view.v1`

| 層 | 欄位（白名單，完全相等） |
| --- | --- |
| 頂層 | `schema_version`、`response_ref`、`as_of_us`、`snapshots`、`display_role`＝`SYSTEM_CANDIDATES_READ_ONLY`、`identity_verdict`、`physical_navigation`、`gt_read` |
| 快照 | `candidate_snapshot_sha256`、`first_decision_source_time_us`、`exit_resolution`、`candidate_set_complete`、`truncated`、`truncated_count`、`candidates` |
| 候選 | `camera_id`、`rank`、`relation`、`transition_id`、`region_path`、`window_us`、`path_traversability`、`path_has_unknown_state` |

不輸出：`ranking_basis`、`candidate_ref`、`alternative_transition_ids`、`window_truncated_us`、`excluded_transitions`，以及 decision 的 `tool_calls`、`llm_calls`、agent trace、evidence。

### 4.3 路由 `q_candidate_view`

payload `{"session_ref", "response_ref", "as_of_us"}`；只能讀同一 session 已有的 response（live 或 `q_recorded_response` 載入的錄製）；`audit=False`。Q1 response 沒有快照，回空陣列。

## 5. (d) OpenAI 預測轉接器（D107）

### 5.1 定位

- 只給俯視圖一條「外部模型推測」示意線；**預設關閉**；demo 用「錄製回應重播」。
- 不是 Agent、不參與 Q5 切鏡或候選排序、不進評分或 Q1～Q5 判斷（`scoring_use: false`）。這是 DEVELOPMENT_RULES「不接外部模型 API」的 D107 例外，範圍僅限本節。
- 任何錯誤、逾時、格式不符、超過上限、關閉、缺 key、重播找不到 → 一律 `UNAVAILABLE`，前端退回物理預測，標「外部推測不可用」。

### 5.2 請求建構 `build_prediction_request`（Codex 實作）

`src/amidst/q1q5/openai_prediction.py`：`build_prediction_request(*, camera_map, observed, as_of_us, last_exit=None) -> dict`

- `camera_map`：§2 的輸出；`observed`：`[{"camera_id", "range_us"}]`（取自 Q2 timeline 的 ON_CAMERA 段）；`last_exit`：`{"camera_id", "exit_zone_id", "direction_status"}`（取自 §6 物理預測的最佳出口）。
- 輸出 `q-demo.external-prediction-request.v1`，**只有**下列結構（白名單，完全相等）：

```json
{
  "schema_version": "q-demo.external-prediction-request.v1",
  "as_of_us": 600000,
  "topology": {
    "cameras": [{"camera_id": "A", "role": "TRACKING", "exit_zone_ids": ["A:east"]}],
    "transitions": [{"from_camera_id": "A", "to_camera_id": "B", "relation": "BLIND_GAP", "via_exit_zone_ids": ["A:east"]}]
  },
  "observed": [{"camera_id": "A", "range_us": [0, 400000]}],
  "last_exit": {"camera_id": "A", "exit_zone_id": "A:east", "direction_status": "KNOWN"},
  "candidate_camera_ids": ["B", "C"]
}
```

- `observed` 起點晚於 `as_of_us` 的段丟掉，跨過 `as_of_us` 的段截到 `as_of_us`。
- `candidate_camera_ids`：從 `last_exit.camera_id`（沒有就用最後觀測鏡頭）出發的轉移終點，排序；都沒有時列全部鏡頭。
- 不送：影像、bbox、像素、示意座標、`region_path`、authority、scene／run 名稱、時鐘以外的任何來源欄位。輸入含禁用鍵 → `FORBIDDEN_INFERENCE_INPUT`。

### 5.3 轉接器 `OpenAIPredictionAdapter`

```python
OpenAIPredictionAdapter(*, enabled=False, mode="LIVE", model=None, transport=None,
                        env=os.environ, replay=None, recorder=None,
                        timeout_s=5.0, max_calls_per_session=6, clock=time.monotonic)
adapter.predict(*, session_id, query_id, request) -> dict
```

| 規則 | 內容 |
| --- | --- |
| 預設關閉 | `enabled=False` → `DISABLED`，不呼叫 transport。伺服器只有在設定 `AMIDST_OPENAI_PREDICTION=live` 或 `replay` 時才建啟用的轉接器（預設 `off`）。 |
| key | 只從 `env["OPENAI_API_KEY"]` 讀（正式環境 `env=os.environ`）。只放在 transport 的 `Authorization: Bearer` 標頭；不得出現在結果、錄製檔、log、例外訊息、`repr()`、任何檔案或回應。缺 key（LIVE）→ `API_KEY_MISSING`。REPLAY 不需要 key。 |
| 每次檢索 | 同一 `(session_id, query_id)` 只做一次邏輯呼叫；再叫一次回上次結果，`attempts=0`（成功時 `source="CACHE"`）。 |
| 重試 | 傳輸錯誤或回應格式不符，最多再試 1 次（每次 `predict` 最多 2 次 transport 呼叫）。逾時不重試。 |
| 逾時 | 每次 `predict` 的總期限 `timeout_s`（0 < `timeout_s` ≤ 5.0，預設 5.0）；傳給 transport 的 `timeout_s` 是剩餘時間。transport 丟 `TimeoutError`，或回應到達時已過期限 → `TIMEOUT`，回應丟棄。 |
| 快取 | 相同請求（`request_sha256` 相同）成功過就直接回快取，不呼叫。失敗不快取。 |
| session 上限 | 每個 session 的 transport 呼叫數（含重試）上限 `max_calls_per_session`（預設 6，PROPOSED，使用者可改）。到達後該 session 鎖定：之後需要呼叫的請求一律 `SESSION_CALL_LIMIT_LOCKED`（快取命中仍可回）；重試遇到上限就不重試。其他 session 不受影響。 |
| 請求檢查 | `predict` 會再驗一次請求：結構不是 §5.2 的白名單或含禁用鍵 → `REQUEST_NOT_WHITELISTED`；任何 `observed.range_us` 超過 `as_of_us` → `FUTURE_DATA_IN_REQUEST`。都不呼叫 transport。 |
| 設定檢查 | `mode` 只能 `LIVE`／`REPLAY`；`timeout_s` 超出 (0, 5]、`max_calls_per_session < 1` → 建構時 `ValueError`。 |

#### transport 與 HTTP 形狀

- `transport(*, url, headers, body: bytes, timeout_s: float) -> bytes`；正式實作用標準庫 HTTPS（不加新依賴），不跟隨重導。
- `url = "https://api.openai.com/v1/chat/completions"`；body 是 JSON：`model`（`AMIDST_OPENAI_MODEL`，未設時建構啟用的轉接器要失敗）、`response_format: {"type": "json_object"}`、`messages`：一則固定的 system 指示，加一則 user，其 `content` **恰好**是請求的 canonical JSON（`sort_keys`、`separators=(",", ":")`、`ensure_ascii=True`）。
- body 不得含影像內容（`image_url`、`input_image`、`data:image`），system 指示文字也不得含 §1 的禁用字詞。

#### 模型回應格式（嚴格）

`choices[0].message.content` 解析成 JSON 物件，鍵**只有** `candidates`：0～3 個 `{"camera_id", "likelihood", "reason"}`；`camera_id` 必須在 `candidate_camera_ids` 裡且不重複；`likelihood` ∈ `HIGH`／`MEDIUM`／`LOW`；`reason` 是 ≤200 字的字串。任何偏差 → `RESPONSE_SCHEMA_INVALID`。

#### 結果 `q-demo.external-prediction.v1`

| 欄位 | AVAILABLE | UNAVAILABLE |
| --- | --- | --- |
| `status`、`reason` | `AVAILABLE`、null | `UNAVAILABLE`、原因碼 |
| `label` | 「外部模型推測（非系統判斷）」 | 「外部推測不可用」 |
| `fallback` | null | `PHYSICAL_PREDICTION` |
| `candidates` | 驗證過的候選 | `[]` |
| `request_sha256`、`source`（`LIVE`／`REPLAY`／`CACHE`／`NONE`）、`attempts`、`model` | — | — |
| `used_for`＝`DISPLAY_ONLY`、`scoring_use`＝false、`identity_verdict`＝`UNCONFIRMED`、`gt_read`＝false | — | — |

原因碼：`DISABLED`、`API_KEY_MISSING`、`REQUEST_NOT_WHITELISTED`、`FUTURE_DATA_IN_REQUEST`、`TIMEOUT`、`TRANSPORT_ERROR`、`RESPONSE_SCHEMA_INVALID`、`SESSION_CALL_LIMIT_LOCKED`、`REPLAY_MISS`。

#### 錄製與重播

- LIVE 成功時呼叫 `recorder(record)`，`record` 的鍵**只有** `schema_version`（`q-demo.external-prediction-recording.v1`）、`request_sha256`、`request`、`response`（`{"candidates": [...]}`，已驗證）、`model`；不含標頭或 key。
- 錄製檔放 repo 外的 LOCAL 目錄（比照 `RecordingStore`），路徑由 `AMIDST_OPENAI_PREDICTION_REPLAY` 指定；不提交。
- `mode="REPLAY"`：`replay=[record, ...]` 在建構時逐筆驗證（`request_sha256` 重算相符、回應格式合法），不合法 → `ValueError`。重播只查表，不呼叫 transport；找不到 → `REPLAY_MISS`。

#### log

只記原因碼、例外類別名、`request_sha256`、`attempts`；不記例外訊息原文（可能夾帶 key）、標頭、body。

### 5.4 路由 `q_external_prediction`

- payload `{"session_ref", "response_ref", "as_of_us"}`；`audit=False`。
- 伺服器從該 response 的 timeline（只取 ≤ `as_of_us`）、§2 的鏡頭圖、§6 的最佳出口組請求，交給轉接器；`query_id` 用 `response_ref` 加 `as_of_us` 的整秒值（同一秒內不重叫）。
- bootstrap 新增 `external_prediction: {"enabled": bool, "mode": "OFF"|"LIVE"|"REPLAY"}`；未設定時 `{"enabled": false, "mode": "OFF"}`，路由回 `DISABLED` 的 UNAVAILABLE 結果。

## 6. 物理預測（Claude 擁有的純模組）

### 6.1 模組

`src/amidst/q1q5/physical_prediction.py`（本 PR 交付）：

```python
predict_next_cameras(*, last_camera_id, last_observed_us, as_of_us, boxes,
                     camera_graph, display_positions=None, params=None) -> dict
```

- `boxes`：`[{"camera_id", "source_time_us", "bbox_xyxy_px"}]`，取自目標在最後一個 ON_CAMERA 段的偵測框（`response.timeline[].observation_ids` → bundle `observations`）。
- `camera_graph`：pinned 的 `q-demo.camera-transition-graph.v1`（要用 exit ROI 多邊形，所以吃完整圖，不吃 §2 的瘦身版）。
- `display_positions`：`{camera_id: [x, y]}`，取自 §2 的 `display_position.xy_m`；沒有就不出示意點。
- 純函式：不讀檔、不連網、不 import 評分端；同輸入同輸出（輸入順序不影響），輸出帶 `content_sha256`。

### 6.2 演算法

1. **時間截斷**：`source_time_us > as_of_us` 的框丟掉並計數（`inputs_after_as_of_dropped`）；`last_observed_us > as_of_us` 直接 `FUTURE_INPUT`。只用 `last_camera_id` 上、`last_observed_us` 之前 `max_sample_span_us` 內的框。
2. **移動方向**：取框底邊中點（腳點），對時間做最小平方法得影像平面速度（px/s）。樣本少於 `min_samples` 或速度低於 `min_speed_px_s` → 方向 `UNKNOWN`。
3. **出口排序**：最後腳點落在出口 ROI 內的優先，其次依速度方向和「腳點→出口多邊形重心」的夾角餘弦。`ALIGNED`＝在 ROI 內或餘弦 ≥ `aligned_cosine`；方向未知時只分 `LAST_POSITION_INSIDE`／`UNRANKED`。
4. **候選鏡頭**：從最後鏡頭出發的轉移，依（最佳出口名次、relation：OVERLAP＜BLIND_GAP＜UNKNOWN、transition_id）排序，取前 `max_candidates`，多的計 `truncated_count`。
5. **時間窗**：有 `nominal_path_length_m` → `[last + L/v_max, last + L/v_min]`；否則 `[last + hops×每跳下限, last + hops×每跳上限]`。OVERLAP 的起點是 `last`。`window_basis` 寫明用哪一種。
6. **信心分級**（文字）：
   - `UNKNOWN`（未知）：方向未知且最後腳點不在任何出口內；
   - `MEDIUM`（中）：經過名次第一的出口，且該出口 `ALIGNED` 或 `LAST_POSITION_INSIDE`；
   - `HIGH`（較高）：在 MEDIUM 之上，再要求方向已知、圖 `APPROVED`、轉移 `APPROVED_WALKABLE` 且 `path_has_unknown_state=false`、該出口只通往這一台。**r004 v3／v3_1 是 DRAFT，所以永遠不會出 HIGH**；
   - `LOW`（低）：其餘。
7. **示意點**：兩端鏡頭都有示意座標時給 `[[x0, y0], [x1, y1]]`（`DISPLAY_POSITIONS_STRAIGHT_LINE`）；否則 null（`NODE_GRAPH_ONLY`，前端在節點圖上連線）。這是示意直線，**不是路徑**，不穿牆判斷、不代表可通行。

### 6.3 參數（PROPOSED 預設，非核准參數集）

`min_samples=3`、`max_sample_span_us=2 000 000`、`min_speed_px_s=20`、`aligned_cosine=0.5`、`per_hop_window_us=(1 000 000, 8 000 000)`、`speed_range_m_s=(0.5, 2.0)`、`max_candidates=3`。輸出帶 `parameter_status: "PROPOSED_DEFAULT"`。要改成正式值需另走參數核准，不在本文件範圍。

### 6.4 路由 `q_physical_prediction`（Codex 接線）

payload `{"session_ref", "response_ref", "as_of_us"}`；`audit=False`。伺服器取 `range_us[0] ≤ as_of_us` 的最後一個 ON_CAMERA 段、其中 `timestamp_us ≤ as_of_us` 的觀測當 `boxes`，`last_observed_us` 取這些觀測的最大時間，圖用 run binding 的 `graphs.camera`（錄製模式用與 §2.4 同一份註冊、pin 相符的圖），示意座標用 §2 的設定，呼叫 `predict_next_cameras` 原樣回傳。回應必須和直接呼叫純函式的結果完全相同（-T 會比對）。

### 6.5 限制

- 方向是影像平面方向，不是地板座標；沒有用相機投影換算，也沒有遮擋計算。
- 時間窗是參數推算，不是量測；r004 的 `nominal_path_length_m` 全是 null。
- 結果只用於畫面示意。

## 7. UI-C 規格（給之後的 UI-C 實作 session）

範圍：`frontend/workbench-v2/` 的追蹤單畫面旁加一個俯視圖面板。檔名前綴 `track-map-*`（DEMO_GAP §3）；共用檔只加一行掛載。資料只經 §2、§4、§5.4、§6.4 的路由或錄製回應。

### 7.1 畫面

1. **底圖**：`layout=METRIC_STATIC` 時，以 `xy_m` 畫鏡頭點（P1 可加 `topdown-static.json` 的地板與牆，`role=display_only_static`）；`layout=NODE_GRAPH` 時畫節點圖（版面由前端固定排版，**不得**從任何 GT、軌跡或劇本推位置），角落固定顯示 `display_note`。`role=QUERY_ONLY` 與 `NOT_IN_GRAPH` 的鏡頭畫成無連線的灰點並加註。
2. **實線＝已觀測**：依 Q2 timeline 中 `range_us[0] ≤ t` 的 ON_CAMERA 段，依序連接鏡頭；目前鏡頭高亮。
3. **虛線＝物理預測**：`q_physical_prediction` 的候選，從最後鏡頭畫到候選鏡頭；線旁標名次、`window_us`（換成 hh:mm:ss）、`confidence_label_zh`；線的粗細或透明度可依信心，但 `UNKNOWN` 必須有可辨識的樣式（例如灰色），不能看起來像有信心。圖例寫「虛線＝物理預測（示意，非實際路徑）」。
4. **系統候選**（可選）：`q_candidate_view` 的候選可在節點上加名次徽章，標「系統候選（唯讀）」。
5. **外部模型推測**：只在 `external_prediction.enabled=true` 且結果 `AVAILABLE` 時畫，用與物理預測明顯不同的樣式（例如點虛線＋不同色相），每條線旁固定標「外部模型推測（非系統判斷）」。`UNAVAILABLE` 時不畫線，面板角落顯示「外部推測不可用」。
6. **狀態照實顯示**：`MISSING` 與 `UNKNOWN` 分開樣式；`authority=DRAFT` 的轉移在 hover 說明裡標「圖未核准（DRAFT）」；`edge_states` 有 `UNKNOWN` 時標「通行狀態未知」。固定標語「身分未確認 · 物理通行與碰撞 UNKNOWN」。

### 7.2 回放與時間

- 面板的時間 t 跟著現有的 Q2 時間軸或播放時鐘。每次 t 改變（拖曳、逐格、播放）都以新的 `as_of_us=t` 取預測（可節流到每 250 ms 一次，或只在 GAP／TEMP_LOST／SEARCHING 狀態取）。
- 只能用 `≤ t` 的資料：實線只畫起點 ≤ t 的段；虛線只用 `as_of_us=t` 的回應；不得預先載入整段 timeline 後畫出 t 之後才會出現的鏡頭。往回拖時要移除 t 之後才出現的線。
- 外部推測：每次檢索最多觸發一次（交給後端的 `(response_ref, 秒)` 去重），前端不得自行重試或輪詢。

### 7.3 測試要求（node 測試）

- 給定 t，畫出的實線只含起點 ≤ t 的段；t 往回時線變少。
- 回應帶 `gt_*`、`actor_id`、`renderer_trajectory` 等誘餌欄位時不顯示、不影響畫面。
- `NODE_GRAPH` 時不出現任何公尺座標文字；`UNKNOWN` 信心有獨立樣式；外部推測 `UNAVAILABLE` 時沒有外部線且顯示「外部推測不可用」。
- 外部推測線一定帶「外部模型推測（非系統判斷）」標籤。

## 8. 實作清單與驗收（給 Codex）

| -T | 測試檔 | 要實作 | 介面 |
| --- | --- | --- | --- |
| DEMO-UI-A-T | `tests/q1q5/test_demo_camera_map_t.py` | 新 `src/amidst/q1q5/camera_map.py`；`api.py` 加 `q_camera_map`、`QAPI(camera_maps=..., camera_display_positions=...)`、bootstrap `camera_maps`；帶入 #294 的 v3_1 三檔 | §2 |
| DEMO-UI-B-T | `tests/q1q5/test_demo_recording_title_t.py` | `api.py`：`RECORDING_TITLE_MAX_CHARS=80`、`RecordingStore.load`／`QAPI` 接受可選 `title`、bootstrap `title`／`title_source` | §3 |
| DEMO-UI-C-T | `tests/q1q5/test_demo_candidate_view_t.py` | 新 `src/amidst/q1q5/candidate_view.py`；`api.py` 加 `q_candidate_view` | §4 |
| DEMO-UI-D-T | `tests/q1q5/test_openai_prediction_t.py` | 新 `src/amidst/q1q5/openai_prediction.py`（`build_prediction_request`、`OpenAIPredictionAdapter`、標準庫 HTTPS transport）；`api.py` 加 `q_external_prediction`、bootstrap `external_prediction`；啟動器讀 `AMIDST_OPENAI_PREDICTION`／`AMIDST_OPENAI_MODEL`／`AMIDST_OPENAI_PREDICTION_REPLAY` | §5 |
| DEMO-UI-E-T | `tests/q1q5/test_demo_physical_route_t.py` | `api.py` 加 `q_physical_prediction`（呼叫本 PR 的 `physical_prediction.py`，不改它） | §6.4 |

- 一般模式：沒實作時 skip，原因碼 `*_IMPLEMENTATION_MISSING`。`AMIDST_REQUIRE_IMPL=1`：同原因碼失敗；v3_1 不在樹上時 `R004_V3_1_GRAPH_NOT_IN_TREE` 失敗。
- 測試可用環境變數換模組：`AMIDST_CAMERA_MAP_MODULE`、`AMIDST_CANDIDATE_VIEW_MODULE`、`AMIDST_OPENAI_PREDICTION_MODULE`。
- OpenAI 測試全部用假 transport、假 key，並封鎖 socket；**不連網**，也不讀真實的 `OPENAI_API_KEY`（轉接器收的是測試傳入的 `env`）。
- 整合驗收命令：

```bash
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/q1q5/test_demo_camera_map_t.py tests/q1q5/test_demo_recording_title_t.py tests/q1q5/test_demo_candidate_view_t.py tests/q1q5/test_openai_prediction_t.py tests/q1q5/test_demo_physical_route_t.py tests/q1q5/test_physical_prediction.py
git diff --check origin/codex/q1q5-staging HEAD
```

- 不得修改本 PR 的 -T 斷言或 `physical_prediction.py`；認為規格有誤時照 #306 §3 寫偏離提案。

## 9. UNKNOWN 與待決

- D107 的正式條文（撰寫時未貼出）。
- r004 鏡頭示意座標：UNKNOWN（repo 沒有校正檔）。
- tracking scope v3_1 SHA 是否補登 #306：待協調者。
- `max_calls_per_session` 正式值、`AMIDST_OPENAI_MODEL` 選哪個模型：待使用者（PROPOSED 預設 6）。
- P1 錄製是否帶候選快照：本文件沒有開 P1 可攜包，UNKNOWN；合成 fixture 有。
- 多鏡頭同時播放與俯視圖同時運作的瀏覽器效能：UNKNOWN（UI-C 實作時實測）。
