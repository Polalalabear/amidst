# 受控場景契約 v1（`OFFICE_CONTROLLED_SCENE_V1`）

狀態：**草案，2026-10-18，A 包。由 Claude 起草，等 Codex 確認可供應的欄位與邊界。**使用者確認範圍之前，不建 `.blend`、不渲染、不實作。標 **OPEN** 的項目需要 Codex 回覆；本文沒有找到依據的名稱或路徑標 `UNKNOWN`。門檻一律標「待約定」，本文不發明通過數字。

- 依據：
  - Codex 提案（LOCAL，SHA-256 `80013790cda63af6cfd14c395989a2e137a7b50b3d7675bda7a702025744b88f`）；
  - [Claude 回覆](../agents/CONTROLLED_SCENE_CLAUDE_REPLY_20261018.md)；
  - [UX 草圖](../agents/CONTROLLED_SCENE_UX_SKETCH_20261018.md)。
- 規則：[DEVELOPMENT_RULES](../DEVELOPMENT_RULES.md)。本契約不放寬 GT 隔離。
- 沿用的既有契約：
  - [區間觀測 v1](OFFICE_INTERVAL_OBSERVATION_V1.md)：`ground_estimate` 物件與 §2.1 共用 provenance 區塊；
  - [盲區假設 v1](OFFICE_BLIND_HYPOTHESIS_V1.md)；
  - [畫面檢索 v1](OFFICE_FRAME_RETRIEVAL_V1.md)：C5 可見範圍索引、`TIME_RANGE` 檢索、負證據。

本文只新增受控場景需要的部分；與上述契約重疊的欄位以原契約為準。名稱保留 `OFFICE_` 前綴是為了和既有契約並列，新場景本身不叫 Office。

## 1. 目的與權限

- 描述一個新的、獨立的受控測試場景：它的靜態標記、攝影機、事件情境，以及工作台讀取的 API。
- 人物的位置、方向與跨鏡頭關聯，**只能從 RGB 影像證據推得**。靜態標記與相機校正是允許使用的輸入。
- 人物 GT、renderer 軌跡、逐影格 visibility、depth、演員 ID、事件腳本只屬於模擬與評估端（§7）。
- 身分一律 `UNCONFIRMED`。實體通行性與碰撞，在已確認範圍外一律 `UNKNOWN`。

## 2. 共通慣例

| 項目 | 規定 |
| --- | --- |
| 長度 | 公尺（m）。所有匯出檔都寫 `"length_unit": "m"`，讀取端遇到其他值時 fail closed |
| 時間 | 秒（s），以 run 的來源時鐘為準，`t = 0` 是第一張影格 |
| 世界座標 | Blender 世界座標：右手系、Z 軸向上、XY 為地面。不另做軸轉換 |
| 地板 | 建議新場景地板 z = 0.000 m，避免舊 Office 的 0.496 m 地板高度造成混淆。實際值由 `floors[].z_m` 宣告，讀取端不得寫死 |
| 影格對應 | `timestamp_s = frame_index / fps`。`fps` 由 run 宣告。同步容差「待約定」 |
| 穩定 ID | 見 §3.2 |
| Hash | SHA-256，十六進位小寫。JSON 用正規化序列化（鍵排序、UTF-8、無多餘空白），規則同區間觀測 v1 §2 |
| 證據狀態 | 沿用既有用詞：`PROJECTED_OBSERVATION`、`INFERRED_INTERPOLATION`、`INFERRED_HYPOTHESIS`、`MISSING`、`UNKNOWN` |

## 3. Scene schema（提案 §4.3 的九類）

匯出成以下幾個檔案，每個檔案都有自己的 SHA-256，並由 manifest 綁定：
- `scene_static.json`：座標、靜態物件、walkable、牆與障礙物、門與樓梯
- `cameras.json`
- `event_<id>.query.json`：推論端可讀的情境資訊
- `event_<id>.validation.json`：只限模擬與評估端
- `manifest.json`

### 3.1 座標與尺度（`scene_static.json` → `frame`）

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `schema_version` | string | 是 | `controlled-scene.static.v1` |
| `scene_id` | string | 是 | 例 `controlled-l-corridor-v1`（建議名，**OPEN**） |
| `scene_version` | string | 是 | 幾何改變就遞增；ID 不因版本改變 |
| `length_unit` | `"m"` | 是 | |
| `time_unit` | `"s"` | 是 | |
| `world_axes` | `"BLENDER_Z_UP_RIGHT_HANDED"` | 是 | |
| `floors[]` | array | 是 | `{floor_id, z_m, support_surface_ids[]}`，首輪只有一層 |

### 3.2 穩定 ID 規則

- 格式 `^[A-Z][A-Z0-9_]{2,63}$`，以類別前綴開頭：

  | 前綴 | 類別 |
  | --- | --- |
  | `WALK_` | 可走區域 |
  | `OBSTACLE_` | 障礙物 |
  | `WALL_` | 牆 |
  | `PORTAL_` | 門、開口 |
  | `STAIR_` | 樓梯 |
  | `ROOM_` | 房間 |
  | `CORR_` | 走廊 |
  | `AREA_` | 查詢用的目標區域 |
  | `CAM_` | 攝影機 |
  | `FLOOR_` | 樓層 |

  沿用舊標註的 `WALK_*`、`PORTAL_*`、`AREA_*`、`OBSTACLE_*` 慣例。
- ID 在 Blender 物件上以 custom property `amidst_id` 存放，**不靠顯示名稱**。改名不影響 ID。
- 幾何修改不換 ID，只遞增 `geometry_version`，並更新 `geometry_sha256`。
- 刪除的 ID 不得重用。重複 ID 讓整份匯出無效。

### 3.3 靜態物件（`objects[]`）

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `id` | string | 是 | §3.2 |
| `class` | enum | 是 | `WALKABLE`、`WALL`、`OBSTACLE`、`PORTAL`、`STAIR`、`ROOM`、`CORRIDOR`、`DISPLAY_ONLY` |
| `source_mesh` | string | 是 | Blender 物件名稱（只作追溯，不作 ID） |
| `geometry_version` | integer | 是 | 從 1 開始 |
| `geometry_sha256` | string | 是 | 世界座標頂點與面（正規化後）的 hash |
| `bounds_m` | `[[xmin,ymin,zmin],[xmax,ymax,zmax]]` | 是 | |
| `authority` | enum | 是 | `ANNOTATED_AT_CREATION`（建立時就標）或 `UNKNOWN` |
| `display_only` | boolean | 是 | `true` 時不得參與可走、遮擋或碰撞判斷 |

### 3.4 Walkable（`walkable[]`）：新場景唯一的推論用地圖

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `id` | string | 是 | `WALK_*` |
| `floor_id` | string | 是 | |
| `support_surface_id` | string | 是 | 支撐面物件 ID |
| `polygon_m` | `[[x,y],...]` | 是 | 逆時針、不自交；洞用 `holes_m` |
| `holes_m` | array | 是 | 可為空 |
| `status` | enum | 是 | `WALKABLE`、`BLOCKED`、`UNKNOWN`。未標的地面一律視為 `UNKNOWN`，不推定可走 |
| `connections[]` | array | 是 | `{to_walk_id, via_portal_id or null}`，雙向各寫一次 |
| `approval` | object | 是 | `{method: "ANNOTATED_AT_CREATION", verified_by: ["C7_MESH_CHECK","K7_ROUTE_CHECK"], verification_sha256}` |

- 推論端（K1、C5 的通路計算、查找模式）只讀這一份。C7 與 K7 是驗證器：它們的輸出只記在 `approval.verified_by` 與驗證報告裡，不另外產生地圖。
- 驗證器發現不一致時，walkable 不自動修改，該區域改標 `UNKNOWN`，等人工決定。

### 3.5 牆與障礙物

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `id` | string | 是 | `WALL_*`／`OBSTACLE_*` |
| `footprint_m` | polygon | 是 | 地面投影邊界 |
| `height_m` | number | 是 | 地板以上高度 |
| `role` | enum | 是 | `PHYSICAL`（實體，參與碰撞與遮擋）或 `DISPLAY` |
| `collision_scope` | enum | 是 | `EXACT_MESH`、`FOOTPRINT_EXTRUDED`、`UNKNOWN` |
| `clearance_basis` | string | 是 | 淨空檢查依據，例 `BODY_RADIUS_0_25_M`（D5）。數值以人體政策設定檔為準 |

### 3.6 門與樓梯

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `id` | string | 是 | `PORTAL_*`／`STAIR_*` |
| `opening_m` | `{a:[x,y], b:[x,y], width_m, height_m}` | 是 | 門洞兩端點 |
| `connects` | `[walk_id, walk_id]` | 是 | 兩側連接，缺一側即 `UNKNOWN` |
| `state` | enum | 是 | `OPEN`（首輪固定開啟）、`CLOSED`、`UNKNOWN` |
| `used_in_first_round` | boolean | 是 | 樓梯為 `false`，並標 `acceptance: NOT_ACCEPTED` |

### 3.7 攝影機（`cameras.json`）

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `camera_id` | string | 是 | `CAM_*` |
| `matrix_world` | 4×4，列優先 | 是 | Blender 相機的世界矩陣，相機慣例 `BLENDER_CAMERA_NEG_Z_FORWARD_Y_UP` |
| `intrinsics` | object | 是 | `{fx_px, fy_px, cx_px, cy_px, sensor_fit, sensor_width_mm, focal_length_mm}` |
| `image_size_px` | `[w,h]` | 是 | 建議 `[960, 540]` |
| `clip_m` | `[near, far]` | 是 | 公尺，與校正同一尺度 |
| `distortion` | `null` | 是 | Blender 針孔，無畸變 |
| `clock` | object | 是 | `{clock_id, fps, frame_start, frame_end}` |
| `valid_time_range_s` | `[t0,t1]` | 是 | |
| `visibility_index_ref` | string\|null | 是 | C5 索引條目；未建立時為 `null` |
| `calibration_sha256` | string | 是 | |

舊 Office bundle 的校正格式與本表的對應關係是 `UNKNOWN`。Codex 確認後，以舊格式為準或提供轉換（**OPEN CS-Q1**）。

### 3.8 事件情境

分成兩個檔案，邊界見 §7。

**`event_<id>.query.json`（推論端可讀）：**

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `event_id` | string | `EVT_A`、`EVT_B1`、`EVT_B2` |
| `run_id` | string | 每個事件一個獨立 run |
| `time_range_s` | `[t0,t1]` | 這個 run 的整段時間 |
| `suggested_queries[]` | array | Demo 預設查詢：`{target_area_id, template, time_range_s}`。只是預填 UI，系統不得因此改變排序 |

**`event_<id>.validation.json`（只限模擬與評估端）：**

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `target_area_id` | string | 目標區域 |
| `entry_exit_portals[]` | array | 進出口 |
| `observation_windows[]` | array | `{segment_id, time_range_s, region_m, required_cameras[], min_simultaneous_cameras}` |
| `overlap_requirements[]` | array | `{cameras:[...], region_m, time_range_s}` |
| `designed_blind_intervals[]` | array | `{blind_id, region_m, expected_time_range_s, cameras_expected_blind:[all]}` |
| `separation_requirements[]` | array | B1：`{rule: "MAX_ONE_PERSON_PER_CAMERA_FRAME", min_gap_s: 待約定}` |

### 3.9 人物產製設定（只限模擬與評估端）

`persons.sim.json`：`{person_sim_id, height_m, body_radius_m, gait, speed_mps, route_waypoints_m[], start_s, seed}`。`person_sim_id` 不是推論身份，不得出現在任何推論端 payload。

### 3.10 來源紀錄（`manifest.json`）

| 欄位 | 說明 |
| --- | --- |
| `scene_id`、`scene_version`、`run_id`、`clock_id` | |
| `blend_sha256` | 新 `.blend` 的 hash |
| `generator_script_sha256`、`generator_config_sha256` | 產生腳本與設定 |
| `blender_version`、`random_seed` | |
| `files[]` | `{name, sha256, side: "INFERENCE_ALLOWED" or "SIM_EVAL_ONLY"}` |
| `rgb_index` | `{camera_id, frame_index, timestamp_s, png_sha256}` 對應表的 hash；路徑不公開 |
| `provenance` | 區間觀測 v1 §2.1 的共用區塊 |

## 4. 檔案與存放（建議，**OPEN CS-Q2**）

| 目錄（資產 repo，不進 Git） | 內容 | 讀取端 |
| --- | --- | --- |
| `data/pilot/<run>/rgb/` | PNG 960×540 | 推論端（經安全 bundle） |
| `data/pilot/<run>/bundle/` | `scene_static.json`、`cameras.json`、`event_*.query.json`、`manifest.json` | 推論端 |
| `data/pilot/<run>/sim_eval/` | `event_*.validation.json`、`persons.sim.json`、GT 軌跡、人物遮罩 | 只限評估端 |

磁碟估算見 [回覆 §1 §4](../agents/CONTROLLED_SCENE_CLAUDE_REPLY_20261018.md#4-新-blend-的規劃修改補磁碟解析度格式存放位置)：960×540 兩事件合計約 0.5 GB。不輸出逐影格深度。

## 5. 事件情境規格

以下尺寸是**建議值**，等 Codex 做可行性檢查（不渲染的視線測試）後確認。

### 5.1 場景配置

| ID | 範圍（m） | 說明 |
| --- | --- | --- |
| `CORR_W`／`WALK_CORR_W` | x 0–17.4，y 0–2.4 | 西走廊 |
| `CORR_N`／`WALK_CORR_N` | x 15–17.4，y 0–12 | 北走廊；與西走廊共用轉角 x 15–17.4、y 0–2.4 |
| `ROOM_R101`／`WALK_R101` | x 5–11，y −5–0 | 目標房間，無鏡頭 |
| `PORTAL_R101` | y = 0，x 7.4–8.6 | R101 門（寬 1.2 m） |
| `ROOM_R102`／`WALK_R102` | x 17.4–22.4，y 7–11 | 對照房間 |
| `PORTAL_R102` | x = 17.4，y 8.4–9.6 | R102 門 |
| `AREA_R101_FRONT` | x 6.5–9.5，y 0–2.4 | 目標區域（R101 門前的走廊） |

| 鏡頭 | 位置（建議） | 預期地面視野（建議） |
| --- | --- | --- |
| `CAM_W1` | (0.3, 1.2, 2.8)，朝 +x | x ≈ 1–9 |
| `CAM_W2` | (15.0, 1.2, 2.8)，朝 −x | x ≈ 6–14.5 |
| `CAM_N1` | (16.2, 11.8, 2.8)，朝 −y | y ≈ 3.5–11（北走廊） |
| `CAM_R102_CTRL` | R102 角落 | 只有 R102 室內 |

設計盲區 `BLIND_CORNER`：x 14.5–17.4、y 0–3.5。沒有任何鏡頭看得到這塊地面，但盲區的地面視野要由 C5 索引實際算出來確認。

### 5.2 事件 A：單人直線經過

| 項目 | 規格 |
| --- | --- |
| 人數 | 1 |
| 路線 | (1.0, 1.2) → (14.0, 1.2)，沿 y = 1.2 直線，約 1.3 m/s |
| 時間窗 | 0 – 約 10 s |
| 目標區域 | `AREA_R101_FRONT`；預期經過時間約 4.2–6.5 s |
| 進出口 | 走廊兩端；不進 R101 |
| 覆蓋 | 0–約 6.2 s（x 1–9）：`CAM_W1`；約 3.8–10 s（x 6–14）：`CAM_W2` |
| 重疊需求 | 經過目標區域的整段，`CAM_W1` 和 `CAM_W2` 都要看得到全身，或至少看得到腳點（「全身」或「腳點」由使用者決定，**OPEN CS-Q3**） |
| 設計盲區 | 無。全程至少 1 台看得到；任何缺影格都記 `MISSING` |
| 無關鏡頭 | `CAM_N1`、`CAM_R102_CTRL` 全程看不到人 |

### 5.3 事件 B1：兩人錯開、跨轉角

| 項目 | 規格 |
| --- | --- |
| 人數 | 2（固定） |
| P1 路線 | t = 0 從 (1.0, 1.2) 往東 → (16.2, 1.2) 轉北 → (16.2, 11.5)；約 1.3 m/s，約 20 s |
| P2 路線 | t ≈ 8 s 從 (1.0, 1.2) 往東 → (8.0, 1.2) 轉南 → 穿過 `PORTAL_R101` → (8.0, −2.5) 停在房內 |
| 時間窗 | 0 – 約 20 s |
| 目標區域 | `AREA_R101_FRONT`；P1 約 4.2–6.5 s 經過；P2 約 12.2–14.3 s 進入、穿門進房 |
| 進出口 | `PORTAL_R101`、走廊兩端、轉角 |
| 覆蓋 | P1：`CAM_W1` → `CAM_W2` → 盲區 → `CAM_N1`。P2：`CAM_W1` →（`CAM_W1`∩`CAM_W2`）→ 穿門後離開所有視野 |
| 設計盲區 | `BLIND_CORNER`：P1 約 10.4–13.5 s（約 3 s）不在任何鏡頭視野內 |
| 錯開條件 | 任一鏡頭任一影格最多 1 人。預估 P1 離開 `CAM_W2` 視野（約 10.4 s）約 1.5 s 後 P2 才進入（約 11.9 s）；最小間隔「待約定」 |
| 可檢驗情況 | P2 進入目標區域時（約 12.2 s），P1 仍在轉角盲區（到約 13.5 s） |

### 5.4 事件 B2：交會或分離（只列需求，不在 v1 規格化）

- 兩人在同一鏡頭內交會、遮擋，再分開。
- 要驗收的是：多解、未關聯基線、`AMBIGUOUS_MERGE`（D8 建議改成 B2 驗收前不可用）。
- B1 通過 CS-B 之後再另寫 v1.1。

## 6. Consumer API（payload 範例）

端點名稱由 Codex 決定（**OPEN CS-Q5**）；以下用描述性名稱。所有回應都帶 `provenance`、`output_sha256`、`identity_verdict: "UNCONFIRMED"`、`agent_used: false`。**數字都是示意，不是量測。**

### 6.1 候選鏡頭查詢

請求 `controlled-scene.camera-candidates-request.v1`：

```json
{
  "schema_version": "controlled-scene.camera-candidates-request.v1",
  "scene_id": "controlled-l-corridor-v1",
  "run_id": "EVT_B1-run-v1",
  "template": "ENTER_EXIT",
  "target_region": {"area_id": "AREA_R101_FRONT", "polygon_m": null},
  "time_range_s": [8.0, 20.0],
  "access_distance_m": "待約定",
  "page": {"size": 4, "index": 0}
}
```

- `target_region` 二選一：`area_id`，或使用者畫的 `polygon_m`（在單一 `floor_id` 上，頂點數上限待約定）。
- `template`：`PASS_THROUGH` 或 `ENTER_EXIT`。

回應 `controlled-scene.camera-candidates.v1`：

```json
{
  "status": "READY",
  "query_id": "cq-3f9a…",
  "query": {"template": "ENTER_EXIT", "target_area_id": "AREA_R101_FRONT", "time_range_s": [8.0, 20.0]},
  "access_paths": [
    {"portal_id": "PORTAL_R101", "walk_ids": ["WALK_CORR_W", "WALK_R101"], "polygon_m": [[6.5,0],[9.5,0],[9.5,2.4],[6.5,2.4]]}
  ],
  "candidates": [
    {
      "camera_id": "CAM_W2",
      "relation": "TARGET_FOOTPRINT_INTERSECT",
      "overlap_area_m2": 7.2,
      "frames_in_range": 120,
      "frames_with_detection": 31,
      "rank": 1,
      "rank_reasons": [
        "相交等級 1：足跡與目標區域相交",
        "重疊面積 7.2 m²",
        "時間範圍內 31 張影格有偵測（不代表同一人）"
      ],
      "footprint_method": "SOURCE_MESH_RAYCAST",
      "visibility_ref": "vis-CAM_W2-…",
      "retrieval_query_id": "fr-…"
    },
    {"camera_id": "CAM_W1", "relation": "TARGET_FOOTPRINT_INTERSECT", "overlap_area_m2": 6.1, "rank": 2},
    {"camera_id": "CAM_N1", "relation": "NO_INTERSECTION", "overlap_area_m2": 0.0, "rank": 3,
     "rank_reasons": ["相交等級 3：足跡與目標區域及通路都不相交"]},
    {"camera_id": "CAM_R102_CTRL", "relation": "NO_INTERSECTION", "overlap_area_m2": 0.0, "rank": 4}
  ],
  "candidates_total": 4,
  "page": {"size": 4, "index": 0, "pages": 1},
  "ranking_basis": ["relation_tier", "overlap_area_m2_desc", "frames_with_detection_desc", "camera_id"],
  "identity_verdict": "UNCONFIRMED",
  "agent_used": false,
  "provenance": {"producer": "camera-candidates", "visibility_index_sha256": "…", "scene_static_sha256": "…"},
  "output_sha256": "…"
}
```

- `relation` 三級：`TARGET_FOOTPRINT_INTERSECT`、`ACCESS_PATH_INTERSECT`、`NO_INTERSECTION`。第三級也要回傳，不能丟掉。
- `frames_with_detection` 來自既有偵測結果，是否列入排序是 **OPEN CS-Q4**。
- 禁止輸入或輸出：GT、`person_sim_id`、`event_*.validation.json` 的任何欄位。

### 6.2 格狀播放的同步影格

請求：`{scene_id, run_id, t_s: 12.4, camera_ids: ["CAM_W2","CAM_W1","CAM_N1","CAM_R102_CTRL"]}`

回應 `controlled-scene.synced-frames.v1`：

```json
{
  "t_s": 12.4,
  "clock_id": "EVT_B1-clock",
  "tolerance_s": "待約定",
  "tiles": [
    {"camera_id": "CAM_W2", "status": "READY", "frame_ref": "fr-CAM_W2-0124", "timestamp_s": 12.4, "delta_s": 0.0, "media_sha256": "…"},
    {"camera_id": "CAM_W1", "status": "READY", "frame_ref": "fr-CAM_W1-0124", "timestamp_s": 12.4, "delta_s": 0.0, "media_sha256": "…"},
    {"camera_id": "CAM_N1", "status": "MISSING", "frame_ref": null, "reason": "RGB_RECORD_HASH_MISMATCH"},
    {"camera_id": "CAM_R102_CTRL", "status": "OUT_OF_RANGE", "frame_ref": null, "reason": "OUTSIDE_VALID_TIME_RANGE"}
  ]
}
```

- `status` 只有 `READY`、`MISSING`、`OUT_OF_RANGE` 三種。`MISSING` 時不得改用其他 run 或鄰近影格補位。
- `frame_ref` 沿用既有不透明的 site/run 綁定參照；不回傳私有路徑。

### 6.3 3D 人物與區間圖層

回應 `controlled-scene.person-layer.v1`（某個時間窗內的所有估計）：

```json
{
  "time_range_s": [12.0, 13.0],
  "estimates": [
    {
      "estimate_ref": "pe-CAM_W1-0124-c0",
      "observation_ref": "obs-CAM_W1-0124-c0",
      "camera_id": "CAM_W1",
      "timestamp_s": 12.4,
      "local_track_ref": "lt-CAM_W1-002",
      "ground_estimate": {
        "status": "READY",
        "estimate_kind": "SEGMENT",
        "basis": "FOOT_RAY_PIXEL_BAND",
        "segment": {"a_m": [6.1, 1.0, 0.0], "b_m": [6.9, 1.3, 0.0], "length_m": 0.85},
        "evidence_state": "PROJECTED_OBSERVATION"
      },
      "bbox_height_px": 214,
      "heading": {"state": "INFERRED_INTERPOLATION", "from_refs": ["obs-CAM_W1-0123-c0", "obs-CAM_W1-0124-c0"], "direction_xy": [0.97, 0.24]},
      "display": {
        "humanoid_range_allowed": true,
        "rule": "length_m <= HUMANOID_DISPLAY_MAX_INTERVAL_M（待約定）",
        "settings_source": "DISPLAY_SETTING_D5",
        "height_m": 1.70,
        "body_radius_m": 0.25
      },
      "identity_verdict": "UNCONFIRMED"
    }
  ]
}
```

- `ground_estimate` 的欄位以區間觀測 v1 §3 為準。上面只列出部分欄位。
- `local_track_ref` 只在同一鏡頭內有效，不代表跨鏡頭身份。
- `display` 的內容不是量測。前端不得把 `SEGMENT` 收成中點來放人形。

### 6.4 曲線圖層

回應 `controlled-scene.curve-layer.v1`：

```json
{
  "curves": [
    {
      "curve_ref": "cv-001",
      "segments": [
        {"kind": "OBSERVED", "evidence_state": "PROJECTED_OBSERVATION", "t_s": [9.8, 10.4], "support_refs": ["obs-CAM_W2-0098-c0", "…"], "geometry": {"type": "INTERVAL_SERIES"}},
        {"kind": "INFERRED_CONNECTOR", "evidence_state": "INFERRED_INTERPOLATION", "t_s": [10.0, 10.1], "geometry": {"type": "RIBBON", "edge_a_m": [[…],[…]], "edge_b_m": [[…],[…]]}, "support_refs": ["obs-…-0100", "obs-…-0101"]},
        {"kind": "BLIND_HYPOTHESIS", "evidence_state": "INFERRED_HYPOTHESIS", "t_s": [10.4, 13.5], "hypothesis_response_sha256": "…", "hypothesis_refs": ["hyp-1"], "region_band": true},
        {"kind": "MISSING_GAP", "evidence_state": "MISSING", "t_s": [15.2, 15.4], "reason": "RGB_RECORD_HASH_MISMATCH", "geometry": null}
      ],
      "association": {"state": "INFERRED_HYPOTHESIS", "identity_verdict": "UNCONFIRMED"}
    }
  ],
  "time_highlight": {"t_s": 12.4, "window_s": 1.0},
  "kinds_reserved": ["PREDICTION"]
}
```

- `MISSING_GAP` 的 `geometry` 一定是 `null`。3D 不畫連線。
- `BLIND_HYPOTHESIS` 的內容引用 K1 回應（盲區假設 v1），不重複定義。
- `PREDICTION` 留給 D 包，v1 不輸出。

### 6.5 點擊回溯證據

請求：`{pick: {layer: "curve", ref: "cv-001", segment_index: 0, t_click_s: 10.3}}`

回應 `controlled-scene.evidence-lookup.v1`：

```json
{
  "status": "READY",
  "nearest_support": {
    "observation_ref": "obs-CAM_W2-0103-c0",
    "camera_id": "CAM_W2",
    "frame_ref": "fr-CAM_W2-0103",
    "timestamp_s": 10.3,
    "delta_s": 0.0,
    "bbox_px": [412, 188, 470, 402]
  },
  "other_supports": ["obs-CAM_W2-0102-c0", "obs-CAM_W2-0104-c0"],
  "relation": "SUPPORTS_OBSERVED_SEGMENT",
  "jump": {"t_s": 10.3, "camera_ids": ["CAM_W2"]}
}
```

| 點到的東西 | `relation` | 跳轉 |
| --- | --- | --- |
| 觀測區間或點 | `IS_OBSERVATION` | 該觀測的影格 |
| `OBSERVED` 段 | `SUPPORTS_OBSERVED_SEGMENT` | 時間最接近的支持觀測 |
| `INFERRED_CONNECTOR` | `ENDPOINTS_OF_CONNECTOR` | 較近的一端；另一端列在 `other_supports` |
| `BLIND_HYPOTHESIS` | `HYPOTHESIS_ENDPOINTS_AND_NEGATIVE_EVIDENCE` | 不自動跳轉；列出兩端觀測與負證據影格 |
| `MISSING_GAP` | `NO_SUPPORT` | 不跳轉，`status: UNKNOWN`，`reason: NO_SUPPORTING_EVIDENCE` |

## 7. GT 隔離邊界

| 資料 | 推論端（檢索、排序、關聯、定位、預測、前端正式播放） | 模擬／評估端 |
| --- | --- | --- |
| RGB PNG（經安全 bundle、hash 驗證） | 可讀 | 可讀 |
| `scene_static.json`（walkable、牆、障礙物、門） | 可讀 | 可讀 |
| `cameras.json`、C5 靜態可見範圍索引（D1） | 可讀 | 可讀 |
| `event_*.query.json` | 可讀（只用來預填 UI） | 可讀 |
| `event_*.validation.json`（覆蓋表、設計盲區、錯開條件） | **禁止** | 可讀（場景驗收） |
| `persons.sim.json`（路線、速度、`person_sim_id`、seed） | **禁止** | 可讀 |
| GT 軌跡、人物遮罩、逐影格 visibility、depth | **禁止** | 可讀；只在預測凍結且 SHA 驗證後由評估工具載入 |
| 事件腳本與演員 ID | **禁止** | 產製用 |

- 推論端的載入程式要拒絕 `sim_eval/` 目錄下的路徑，並且有測試覆蓋（照 RQ1 工具「GT 拒絕載入」的做法）。
- 推論端 payload 中出現 `person_sim_id`、`route_waypoints_m` 或 validation 欄位時，一律 fail closed（**OPEN CS-Q6**：錯誤碼名稱）。
- `suggested_queries` 只預填 UI；它的存在不得改變候選排序。測試要比對「有預填」和「手動輸入相同查詢」兩種情況，回應必須逐位元相同。
- 正式播放不能退回 GT。GT 回放只能出現在標 `EVALUATION` 的獨立面板。

## 8. 驗收表

兩欄分別驗收，不能互相代替。所有數字門檻都是「待約定」，要在凍結前寫入版本化設定檔。

| 項目 | 場景符合條件（模擬／評估端，可讀 GT） | 影像估計正確（正式系統，不讀 GT；凍結後評估） |
| --- | --- | --- |
| 座標與尺度 | 匯出單位為 m；地板 z 與支撐面一致；相機高度與 `matrix_world` 相符 | 接地估計使用同一地板高度與尺度 |
| 標記完整 | §3 每類必填欄位齊全；ID 唯一；validator 0 錯誤 | — |
| Walkable | C7 mesh 檢查與 K7 路線檢查通過；不一致處已標 `UNKNOWN` | K1 只讀 walkable 標記；路徑不穿過已確認障礙物 |
| 攝影機 | 校正、`image_size_px`、時鐘、`frame ↔ timestamp` 對應完整 | 同步影格 `delta_s` ≤ 容差（待約定） |
| 覆蓋與重疊 | 每段 `observation_windows` 指定的鏡頭在指定時間看得到人（GT 遮罩）；重疊需求成立 | 候選鏡頭查詢的召回（待約定）；排序理由可重現 |
| 設計盲區 | `BLIND_CORNER` 時間窗內所有鏡頭都看不到人 | 盲區內不畫位置；K1 範圍帶涵蓋率（待約定） |
| 錯開（B1） | 任一鏡頭任一影格最多 1 人；間隔 ≥ 待約定 | 兩人不被連成同一條曲線 |
| 人物 | 接地、身體淨空（半徑 0.25 m）不穿牆與障礙物 | 接地區間涵蓋率與區間長度（待約定；RQ1 指標沿用） |
| 缺影格 | 列出所有非設計的缺影格 | 一律顯示 `MISSING`，不補位 |
| 點擊回溯 | — | 每個可點元素都回到支持證據，或明確 `NO_SUPPORT` |
| 來源與 hash | manifest 每個檔案 hash 可重算；原資產不變 | 回應的 `output_sha256` 可重現 |
| GT 隔離 | — | 載入程式拒絕 `sim_eval/`；預填與手動查詢回應相同 |
| 綠球 | — | 工作台不出現綠球或球狀人物替身 |

## 9. 待決問題

| 編號 | 問題 | 回覆者 |
| --- | --- | --- |
| CS-Q1 | 舊 Office bundle 的校正格式能否直接沿用；與 §3.7 的對應 | Codex |
| CS-Q2 | 存放目錄的實際路徑與安全 bundle 格式 | Codex |
| CS-Q3 | 事件 A 的重疊需求是「全身可見」還是「腳點可見」 | 使用者 |
| CS-Q4 | `frames_with_detection` 是否列入排序 | 使用者、Codex |
| CS-Q5 | 各 API 的端點名稱，以及是否併入既有 `target_reconstruction`、`frame_retrieval` | Codex |
| CS-Q6 | GT 欄位誤入推論端時的錯誤碼 | Codex |
| CS-Q7 | C5 的 `MAX_CAMERAS = 4` 是否放寬；候選鏡頭查詢會跨所有鏡頭 | Codex |
| CS-Q8 | C4b 改成多組端點（B1 有兩人）的契約；這是 #55 評估中指出的限制 | Claude 起草、Codex 確認 |
| CS-Q9 | 所有「待約定」門檻：同步容差、`HUMANOID_DISPLAY_MAX_INTERVAL_M`、`access_distance_m`、B1 錯開間隔、涵蓋率、召回率 | 使用者 |
