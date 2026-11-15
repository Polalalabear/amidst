# DP4 下一步關注排序 契約 v1

- 狀態：**契約（normative）**。D210 新增決策點 DP4；D214 寫契約、關卡和 Rule 版本。
- 作者／Model / effort：Claude Code，Sonnet 5.5 / high。
- 關卡：[`tests/q1q5/test_dp4_attention_gates.py`](../../tests/q1q5/test_dp4_attention_gates.py)。共用介面與 Rule：[`src/amidst/q1q5/attention_ranking.py`](../../src/amidst/q1q5/attention_ranking.py)。
- 相關：[`AGENT_DECISION_V1.md`](../design/AGENT_DECISION_V1.md)（WP1/WP2 的 `Attempt`、退回原因）、#511／PR #526（轉接器）、#513。
- 注意：`AGENT_DECISION_V1.md` §1.2 的舊「DP4（查找結果排序）」已暫停，與本文的 DP4 是不同的決策點；本文的 DP4 取代它的編號。
- 範圍：只改新檔，不接進 `associate()`，不碰 `frontend/`。身分一律 `UNCONFIRMED`，物理導航一律 `UNKNOWN`。

## 1. 要解決什麼

目標還在畫面裡，或剛離開時，依鏡頭圖、目標最後的位置、方向和經過的時間，以及各鏡頭最近的偵測摘要，排出**接下來最可能出現的鏡頭**，提前把注意力放上去。三種方法吃同一個請求、吐同一種回應：

| 方法 | 做法 | 負責 |
| --- | --- | --- |
| `RULE` | 圖的鄰居加走路時間窗和方向，依固定公式排序；重用盲區假設（`physical_prediction.predict_next_cameras`）並加負證據剪枝 | 本 PR（已完成） |
| `API` | 一次呼叫，回傳固定格式 | Argon（N3） |
| `AGENT` | 多步驟加工具，有步數和預算上限 | Argon（N3） |

主要結果是**延遲（中位數、p95）和費用**；準確度（前 1／前 3 命中、提前量、誤切）**只記錄，不做通過條件**。

## 2. 輸入（`q-demo.dp4-attention-request.v1`）

三種方法的輸入只能有**偵測結果和鏡頭圖**。頂層欄位剛好是下表這些，多或少都拒絕（`UNKNOWN_OR_MISSING_FIELD`）。

| 欄位 | 型別／內容 |
| --- | --- |
| `schema_version` | 常數 `q-demo.dp4-attention-request.v1` |
| `as_of_us` | 整數 ≥ 0，決策當下的時間（微秒）。任何輸入都不能晚於它（`FUTURE_INPUT`） |
| `elapsed_us` | 整數 ≥ 0，必須等於 `as_of_us - last_observation.time_us`（`ELAPSED_MISMATCH`） |
| `last_observation` | `camera_id`（必須是圖的節點）、`time_us`、`bbox_xyxy_px`（`[x1,y1,x2,y2]`，偵測框），選填 `recent_boxes`（同一目標在該鏡頭、`time_us` 以前的偵測框，每筆只有 `time_us` 和 `bbox_xyxy_px`）、`direction_estimate`（`null` 或偵測框算出的影像速度摘要；Rule 自己用 `recent_boxes` 重算，不信這個欄位） |
| `graph` | 完整的 `q-demo.camera-transition-graph.v1` 文件（r004 graph v3：節點 `cameras[].camera_id`、邊 `transitions[]`、出口區 `exit_zones[]`）。圖的狀態維持 `DRAFT`／`GRAPH_NOT_APPROVED`，不因此獲得物理權威 |
| `camera_summaries` | 各鏡頭最近的偵測摘要陣列，每個鏡頭最多一筆：`camera_id`、`coverage_end_us`（偵測分析涵蓋到的時間，≤ `as_of_us`）、`person_detections_since_last_obs`（自目標最後觀測後的人物偵測數，整數）、選填 `last_person_detection_us`、`max_score`。**沒有人物 ID、座標、影像** |

### 2.1 禁止的欄位

請求的**任何層級**出現下列鍵（不分大小寫）就以 `AttentionInputError('FORBIDDEN_INFERENCE_INPUT')` 拒絕；API／Agent 必須在**呼叫模型之前**拒絕，並且送給模型的每一份內容（包含 Agent 每一輪的工具結果）也不得含這些鍵：

- Ground Truth 與評分用資料：`gt`、`ground_truth`、任何 `gt_` 開頭、`truth`、`truth_camera_id`、`truth_arrival_us`、`private_evaluation`、`production_manifest`、`persons.sim.json`；
- 渲染器資料：`renderer_trajectory`、`renderer_visibility`、`trajectory`、`visibility`、`depth`、`mask`、`event_script`、`script`、`actor`、`actor_id`、`material_id`；
- 即時模式操作者：任何 `operator_` 開頭、`live_operator`、`person_id`、`world_xy`、`world_position`、`position_m`、`identity`。

實作：`attention_ranking.FORBIDDEN_KEYS`／`scan_forbidden()`（含 `physical_prediction.FORBIDDEN_KEYS`）。標準答案只存在評分模組（§6），絕不進請求。

## 3. 輸出（`q-demo.dp4-attention-response.v1`）

```text
{"schema_version": <RESPONSE_SCHEMA>,
 "method": "RULE|API|AGENT", "requested_method": "RULE|API|AGENT",
 "ranking": [{"camera_id": "CAM_C", "score": 0.6, "reason": "EXIT_ALIGNED"}],
 "latency_ms": 12.3, "cost_usd": 0.0, "steps": 0, "fallback_reason": null}
```

- `ranking`：非空，依 `score` 由高到低，每個鏡頭最多一筆，`camera_id` **只能是請求 `graph` 的節點**（否則 `ILLEGAL_CANDIDATE`），`score` ∈ [0,1]，`reason` 是封閉 enum：`STILL_IN_VIEW`、`EXIT_ALIGNED`、`EXIT_LAST_POSITION`、`DIRECTION_UNKNOWN`、`OVERDUE`、`NEGATIVE_EVIDENCE`、`NOT_ADJACENT`、`MODEL_RANKED`（API／Agent 用）。Rule 一律回傳**所有**節點；API／Agent 至少回前 3 名（節點少於 3 個則全部）。
- `method`：實際產生這份排序的方法。退回 Rule 時 `method=RULE`、`requested_method` 保留原本要求的方法、`fallback_reason` 非 `null`；`method` 不是 `RULE` 時 `fallback_reason` 必須是 `null`。
- `latency_ms`：整次呼叫的牆鐘時間（Agent 為各步 `Attempt.wall_ms` 之和；退回 Rule 時再加上原本的呼叫時間）。
- `cost_usd`：依價目表 `price_per_mtok=(輸入, 輸出)`（USD 每百萬 token，**由使用者提供、附日期和來源**）與 `Attempt.prompt_tokens`／`completion_tokens` 計算；沒有價目表或沒有 token 數就是 `null`（UNKNOWN，不估）。Rule 是 `0.0`。
- `steps`：模型呼叫次數。Rule 為 0，API 為 1（退回時也是實際呼叫次數），Agent 為已用的步數。
- `fallback_reason`：沿用 `agent_decision.FALLBACK_REASONS`，**不新增 enum 值**：逾時 `PROVIDER_TIMEOUT`、連不上 `PROVIDER_UNAVAILABLE`、找不到錄製 `REPLAY_MISS`、格式錯 `INVALID_RESPONSE`、id 不在圖裡 `ILLEGAL_CANDIDATE`、步數用完 `ROUND_LIMIT`、費用超過上限 `CALL_BUDGET_EXHAUSTED`。
- 共用驗證：`attention_ranking.validate_response(response, request)`；三種方法的輸出都必須通過。

## 4. 方法細節

### 4.1 Rule（已實作）

`rank_attention(request, *, params)`，純函式、決定性（同請求同排序）。公式（參數是 PROPOSED，非核定參數組）：

1. 盲區假設：`predict_next_cameras`（出口區排序、方向、每跳時間窗 1–8 s）。
2. 分數：信心 `HIGH` 0.9、`MEDIUM` 0.6、`LOW` 0.3、`UNKNOWN` 0.2。
3. 時間：`as_of` 早於時間窗起點 ×0.7；晚於時間窗終點 ×0.5 並標 `OVERDUE`。
4. 負證據剪枝：鄰居鏡頭 `person_detections_since_last_obs == 0` 且空窗長度（`coverage_end_us - max(窗起點, 最後觀測時間)`）≥ 2 s 時，分數 ×0.2；涵蓋到時間窗終點則設為 0。標 `NEGATIVE_EVIDENCE`。
5. 目前鏡頭：`elapsed_us ≤ 1 s` 時 1.0（`STILL_IN_VIEW`），否則 0.05。
6. 非鄰居：0.01（`NOT_ADJACENT`）。
7. 排序：`(-score, camera_id)`。

預設行為不影響現有 demo：新模組沒有被任何其他模組匯入（關卡 `test_rule_does_not_touch_associate` 檢查），`associate()` 輸出不變。

### 4.2 API（Argon）

`amidst.q1q5.attention_api.ApiRanker(call, *, timeout_ms, max_output_tokens, price_per_mtok)`，`.rank(request) -> response`。`call` 就是 WP2 的 provider：`call(request, *, timeout_ms, max_output_tokens) -> agent_decision.Attempt`（#511／PR #526 的轉接器）。一次呼叫；`Attempt.response` 形如 `{"ranking": [...]}`。請求先驗證（禁止欄位在呼叫前拒絕，`.rank` 直接拋 `AttentionInputError`，且 `call` 一次都不能被呼叫）；任何失敗都退回 Rule，**絕不拋例外**（輸入本身不合法除外）。預設單次逾時 3000 ms（PROPOSED）。

### 4.3 Agent（Argon）

`amidst.q1q5.attention_agent.AgentRanker(call, *, max_steps, budget_usd, timeout_ms, max_output_tokens, price_per_mtok)`，並匯出 `TOOL_NAMES`，內容必須等於 `attention_ranking.AGENT_TOOLS`。

- 協定：每一步呼叫 `call({"request": ..., "tool_results": [...], "step": n}, ...)`；`Attempt.response` 是 `{"action":"TOOL","tool":<名稱>,"args":{...}}` 或 `{"action":"FINAL","ranking":[...]}`。
- **可用工具（只有這三個）**：
  1. `get_graph_neighbors(camera_id)`：查圖，回傳該節點的出邊（鄰居、關係、出口區 id）；
  2. `get_recent_detections(camera_id)`：回傳該鏡頭的 `camera_summaries` 那一筆（沒有就回「無資料」，不是零）；
  3. `update_hypothesis(ranking)`：把目前的暫定排序寫進工作記憶（驗證同 §3）。
  工具只讀請求裡的資料；沒有檔案、網路、影像或 GT。工具名稱不在清單（`INVALID_RESPONSE`）、參數的 `camera_id` 不在圖裡（`ILLEGAL_CANDIDATE`）都立刻退回 Rule，且該工具不執行。
- **上限（PROPOSED，可由參數覆寫）**：`max_steps = 5`、`budget_usd = 0.02`、單次逾時 `timeout_ms = 3000`。步數用完仍沒有 `FINAL` → `ROUND_LIMIT`；累計費用超過 `budget_usd` → `CALL_BUDGET_EXHAUSTED`（最多只為超過上限的那一次呼叫付費，之後不再呼叫）；任一次逾時 → `PROVIDER_TIMEOUT`。**一律退回 Rule**，`steps` 是已用的步數。
- 送給模型的每一份內容（包含每一輪工具結果）都不得含 §2.1 的禁止鍵。

## 5. 觸發與記錄

### 5.1 觸發（即時模式）

| 方法 | 何時跑 |
| --- | --- |
| Rule | 每一格（每個新的偵測時間點）都跑；輸入同一格的偵測摘要 |
| API／Agent | **事件觸發**：目標的 bbox 碰到出口區、目標從該鏡頭消失（`elapsed_us` 第一次超過 1 s）、`last_observation.camera_id` 改變（重新出現在別的鏡頭）、方向反轉（折返）；加上**低頻率定期更新**：預設每 2 s 一次（PROPOSED）、`elapsed_us > 0` 時才跑。非同步執行：不阻塞畫面，結果回來時若已有更新的請求（`as_of_us` 較大）就丟棄；回來之前畫面用 Rule 的排序 |

回放時三種方法用同一份請求清單（同一個 `request_sha256`，`attention_ranking.request_sha256()`），以便配對比較。

### 5.2 記錄欄位

每一次排序記一列（JSONL）：`request_sha256`、`as_of_us`、`method`、`requested_method`、`fallback_reason`、`latency_ms`、`cost_usd`、`steps`、`ranking`（前 3 名即可）、`trigger`（`TICK`／`EVENT_EXIT_ZONE`／`EVENT_LOST`／`EVENT_CAMERA_CHANGE`／`EVENT_REVERSAL`／`PERIODIC`）。**標準答案不寫進這一列**，評分時才由評分模組併入（§6）。

## 6. 指標定義

延遲和費用是主要結果；其餘只記錄。評分單位是「一次離開事件」（目標離開某鏡頭到第一次在另一個鏡頭重新被觀測，`arrival_us`）。標準答案 `truth_camera_id`／`arrival_us` 只存在評分模組，由 GT 算出，不進任何請求。

| 指標 | 定義 | 單位 |
| --- | --- | --- |
| 延遲 `latency_ms` | 每次排序的 `latency_ms`，報**中位數和 p95**（Rule／API／Agent 各自分開；退回 Rule 的列歸原本要求的方法，另報退回比例） | ms |
| 費用 `cost_usd` | 每次排序的 `cost_usd`，報每次中位數、p95 和總和；`null` 的列單獨計數，不當作 0 | USD |
| 退回比例 | `fallback_reason` 非 `null` 的列 ÷ 要求 API／Agent 的列，依原因分開列 | % |
| 前 1／前 3 命中 | 事件中，`as_of_us < arrival_us` 的**最後一次**排序，`truth_camera_id` 是否在 `ranking[:k]`（`hit_at_k`） | % |
| 提前量 | `arrival_us − t*`，`t*` 是最早的 `as_of_us`，使得從 `t*` 到 `arrival_us` 之前的每一次排序的第 1 名都是 `truth_camera_id`；最後一次排序第 1 名不是它則為 `null`（`lead_time_us`） | µs（報告時換成秒） |
| 誤切 | 事件內，`arrival_us` 之前第 1 名**改變**、且新的第 1 名不是 `truth_camera_id` 的次數；另報每分鐘誤切率（`false_switches`） | 次、次／分鐘 |

## 7. 完成條件

- Rule：本 PR 已完成，關卡全數 PASS。
- API、Agent：`tests/q1q5/test_dp4_attention_gates.py` 的 `API_GATE`、`AGENT_GATE` 兩組 `xfail(strict=True)` 全部轉成 PASS，**斷言不得修改**，兩個標記各自整組一起移除（自我測試依函式名計數，標記只能整組保留或整組移除）。等 #526 合併後才能開工。
- 斷言有問題時，在 issue 上提出，由 Claude 改契約和關卡，不由實作者自行改斷言。
