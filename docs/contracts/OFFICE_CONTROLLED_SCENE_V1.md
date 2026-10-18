# 受控場景契約 v1（`OFFICE_CONTROLLED_SCENE_V1`）

> 後端第一批工作副本（2026-10-18）：整合基準`f481fe0`尚無此檔，故由已核准的#65 @ `264377112d1859c5472a9a47dcb56c9b4b38e19e`原文物化。D32已在#66核准該版本；下列原狀態／「未實作」文字保留作當時記錄，不代表重新開啟CS-A。**本輪新增§2.3.1與§6.0的提案需Claude確認，不宣告已修改核准契約或C4a v1.1。**本輪明確授權的是無blend依賴的後端／fixture，不授權場景生成。實作範圍與精確wire補充見[後端第一批交接](../engineering/CONTROLLED_SCENE_BACKEND_FIRST_BATCH_20261018.md)。原文引用而本基準未包含的文件，以#65固定commit的同路徑為準。

狀態：**草案（第 3 版），2026-10-18，A 包。由 Claude 起草；Codex 已完成 CS-A 文件審查，本版依審查與使用者決定 D26–D28 修訂。CS-A 是否通過由使用者在 [#66](https://github.com/Polalalabear/amidst/issues/66) 決定；本文不宣告通過。**

在 CS-A 通過、並另外授權 B 包之前，不建 `.blend`、不渲染、不實作。

- 本文標示規則：
  - 「待約定」：數值門檻，本文不定。
  - 「CS-A 待核准的介面設計」：Codex 已提出、等使用者核准的設計。
  - `UNKNOWN`：沒有依據。
- 本文所有新增欄位與端點**都還沒有實作**。

| 版本 | Commit | 內容 |
| --- | --- | --- |
| 1 | `6cb2183` | 初稿 |
| 2 | `9848d5e` | 使用者決定（5 fps）、§2.1 內插規則、對齊 Codex 準備文件 |
| 3 | `11820c0` | 依 Codex CS-A 審查修訂；記錄 D26–D28 |
| 4 | 本版 | 依 Codex 對 `11820c0` 的複核（[留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6246035412)）R3：§6.1 範例改為 `PARTIAL`，新增整體 readiness 狀態的定義。R1、R2 只改回覆與 UX 草圖 |

## 0. 依據與使用者決定

### 0.1 依據（固定版本）

| 來源 | 版本 |
| --- | --- |
| Codex 提案 | `docs/agents/CONTROLLED_SCENE_2D_TO_3D_PROPOSAL_20261018.md` @ `59b8f5d91fe35812dfe0046c67709a519b46ed1e`（分支 `codex/office-demo-rehearsal-docs`），SHA-256 `80013790cda63af6cfd14c395989a2e137a7b50b3d7675bda7a702025744b88f` |
| Codex 準備文件 | `docs/engineering/CONTROLLED_DEMO_PREPARATION_20261018.md` @ `14a3ffbd1ed6fbef5952b3402fe46daf14be22fb` |
| Codex CS-A 審查 | [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6245504825)（審查對象 #65 @ `9848d5e`）。以留言全文為準；Codex 本機的 commit `f50fc37` 沒有推送，本文不引用 |
| 使用者決定 | D25（[#26](https://github.com/Polalalabear/amidst/issues/26)）、D26–D28（§0.2） |
| Claude 文件 | [回覆](https://github.com/Polalalabear/amidst/blob/264377112d1859c5472a9a47dcb56c9b4b38e19e/docs/agents/CONTROLLED_SCENE_CLAUDE_REPLY_20261018.md)、[UX 草圖](https://github.com/Polalalabear/amidst/blob/264377112d1859c5472a9a47dcb56c9b4b38e19e/docs/agents/CONTROLLED_SCENE_UX_SKETCH_20261018.md) |
| 規則 | [DEVELOPMENT_RULES](../DEVELOPMENT_RULES.md)；本契約不放寬 GT 隔離，D1 照舊 |

**沿用的既有契約（固定版本）：**

| 契約 | 版本 | 沿用的部分 |
| --- | --- | --- |
| [區間觀測 v1](OFFICE_INTERVAL_OBSERVATION_V1.md) | 整合分支 @ `dcb89f4` | `ground_estimate` 物件、§2.1 共用 provenance 區塊 |
| [盲區假設 v1](OFFICE_BLIND_HYPOTHESIS_V1.md) | 整合分支 @ `dcb89f4` | — |
| [畫面檢索 v1](OFFICE_FRAME_RETRIEVAL_V1.md) | 整合分支 @ `dcb89f4` | — |
| 契約 v1.1（[#45](https://github.com/Polalalabear/amidst/pull/45)） | @ `9e1234cc0e626abf49669f6ab0624c42f6e8bacf` | `FOOT_RAY_PIXEL_BAND`（R1／D17）、D21 strict／suggestion 規則 |

**新場景不沿用**的舊 Office 條文：
- `floor_z_m = 0.4959…` 與其他 Office 常數；
- D18 的固定端點與 `D18_INTERVAL_CONTAINS_OBSERVATION` guard（保留給舊 run）；
- annotation authority 與 proxy 排除規則；
- D15 禁止區、D16 座椅規則；
- `MAX_CAMERAS` 等 Office wrapper 的寫死值（見 CS-Q7、CS-Q14）。

名稱保留 `OFFICE_` 前綴，只是為了和既有契約並列；新場景本身不叫 Office。

### 0.2 使用者決定 D26–D28（2026-10-18，由協調者轉達，引號內是使用者選的選項原文）

| 決定 | 使用者選項 | 內容 | 落在本文 |
| --- | --- | --- | --- |
| **D26** GT 時機 | 「RGB 人工驗收」 | CS-B 只用 RGB 逐格人工核對覆蓋與 B1 錯開，加上靜態標記、校正核對與產製完整性。GT／mask 的數值評估延到輸出凍結後。D1 不放寬 | §7、§8 |
| **D27** CS-Q3 | 「雙鏡全身＋接地」 | 事件 A 雙鏡重疊的目標區域內，兩台鏡頭都要拍到全身（頭頂到腳），RGB 裡看得到接地。不能用 bbox 底邊推定腳 | §5.2 |
| **D28** CS-Q4 | 「不列入排序」 | v1 排序是 `relation_tier → overlap_area_m2_desc → camera_id`；偵測數只當附帶證據欄位，並標明評估範圍與數量是否完整 | §6.1 |

D25 的內容（960×540／5 fps／PNG、B1／B2、固定 2 人、轉角無鏡頭、D3 反轉、D8 改為 B2 驗收前）照舊適用。

## 1. 目的與權限

- 本契約描述一個新的、獨立的受控測試場景：靜態標記、攝影機、事件情境，以及工作台讀取的 API。
- 人物的位置、方向與跨鏡頭關聯，**只能從 RGB 影像證據推得**。靜態背景可以使用核准用途的模型與校正（§3.3 `allowed_purposes`）。
- 事件腳本只在隔離的產製端用來生成影像。GT、遮罩等評估資料只能在**輸出凍結且 hash 驗證後**讀取（D26）。
- 正式服務不得開啟 private 檔案，也不得以事件標籤決定排序或配對。
- 身分一律 `UNCONFIRMED`。實體通行性與碰撞，在已核准範圍以外一律 `UNKNOWN`。

## 2. 共通慣例

| 項目 | 規定 |
| --- | --- |
| 長度 | 公尺（m）。匯出檔寫 `"length_unit": "m"`，其他值 fail closed |
| 時間 | 秒（s），以 run 的來源時鐘為準 |
| 世界座標 | Blender 世界座標，右手系，Z 軸向上 |
| 地板 | 由 `floors[]` 宣告支撐面（§3.1）。讀取端不得寫死 0 或舊 Office 高度 |
| 取樣索引 | `frame_index` 是公開的、從 0 起算的 sample index，`timestamp_s = frame_index / fps`。Blender 的 `frame_start`、`frame_step`、`fps`、`fps_base` 對應只存在產製端的 private manifest |
| 時間區間 | run 用半開區間 `[0, duration_s)`，`duration_s × fps` 必須是整數。`duration_s` 與 `last_timestamp_s` 分成兩欄；不能把最後一張的時間當成結束時間 |
| 證據狀態 | `PROJECTED_OBSERVATION`、`INFERRED_INTERPOLATION`、`INFERRED_HYPOTHESIS`、`MISSING`、`UNKNOWN` 分開。sibling estimate 不回填原觀測的 `world_position` |
| 同步容差 | 待約定（CS-Q9） |

### 2.1 Hash 規則

- 檔案位元組的 hash 叫 `file_sha256`；canonical JSON 內容的 hash 叫 `content_sha256`。兩者不得混用同一個欄位名。
- canonical JSON 的序列化設定固定為 `sort_keys=True, separators=(',', ':'), allow_nan=False, ensure_ascii=True`，編碼 UTF-8。這與既有 `registry.content_hash` 的實作一致。
- 其他規則：
  - hash 不包含欄位自身，也不包含明列的計時欄位（例如 `stats.latency_ms`）。
  - 拒絕 NaN 與 Infinity。
  - 每個欄位要宣告數值型別。
  - 陣列的排序規則在各 schema 中寫明。
- 幾何 hash 另外由 `geometry_encoding_version` 固定以下規則：世界座標公尺、面索引、modifier 是否已評估、頂點與面的排序。

### 2.2 影格之間的時間內插

- 5 fps 時影格間隔 0.2 s。**只有 sample 時間點上的資料是觀測。**
- **2D：**依預期的 sample grid 選格（`LATEST_AT_OR_BEFORE`），即 `timestamp_s ≤ t` 的最後一個 sample。
  - 那個 sample 缺檔時，該格是 `MISSING`，**不得跳過它去找更早的可用影像**。
  - 影格本身是觀測，但它的時間是 `timestamp_s`，不是 `t`。
- **3D 內插的條件：**
  - 只能在**同一條 RGB 推得的局部軌跡**內做，而且兩端都有效時才做，範圍有界。
  - 不得跨過 `MISSING`、`UNKNOWN` 或未關聯的缺口。
  - 是不是缺口，由 RGB 記錄判斷，**不讀** private 的 `designed_blind_intervals`。
- **狀態標示：**
  - 單純移動播放頭只是時間控制，不產生證據狀態。
  - 只有內插算出來的空間幾何（位置、區間、刻度位置）標 `INFERRED_INTERPOLATION`，而且不得用觀測色。
  - 盲區中的 K1 假設切片維持 `INFERRED_HYPOTHESIS`，不得改標成內插。
- 把 5 fps 包成較高幀率播放，不會增加觀測。

### 2.3 缺影格與完整性錯誤

| 情況 | 處理 |
| --- | --- |
| 預期的 sample 檔案不存在 | 該格 `MISSING`（`reason: RGB_RECORD_ABSENT`）。不補位，不用鄰近影格或其他 run |
| 超出 run 的時間範圍 | `OUT_OF_RANGE` |
| hash、source 或 pin 不符 | **完整性錯誤**：`DataIntegrityError`，沿用既有原因碼（例如 `RGB_RECORD_HASH_MISMATCH`）。整個 run fail closed，不發 media token，**不得降格為 `MISSING`** |

### 2.3.1 後端第一批提案：完整性錯誤wire格式（R5，待Claude確認）

五個§6端點一致用HTTP **409 Conflict**、`Content-Type: application/json; charset=utf-8`，body：

```json
{"schema_version":"controlled-scene.error.v1","error":{"error_class":"DataIntegrityError","reason":"RGB_RECORD_HASH_MISMATCH"}}
```

`reason`保留具體安全原因碼（source/run/binding/hash/pin／D45 uncertainty錯誤），不傳例外原文、私有locator、session secret。無tile、人物、曲線、部分成功資料或media token；禁止把409映成單格MISSING／UNKNOWN或保留上一批圖層。此形狀相容#71 fixture的`error.error_class`／`error.reason`。必要技術輸入缺失為503 `RequiredInputUnavailable`、同一error envelope；真正預期RGB缺檔才是sample的MISSING。非法請求與session／scope拒絕仍沿用既有400／403，不冒稱完整性錯誤。

本批fixture mode須server顯式啟用；bootstrap與每個成功回應均帶`data_origin: SYNTHETIC_FIXTURE`、fixture marker與`gt_read:false`。真實run未接入時不得替換為fixture。同步fixture無實體影像，回MISSING且不發media token。正式`frame_ref`是opaque evidence ref，不能當路徑；未來media token／URL adapter另補，本批不提供影像路由。

## 3. Scene schema

### 3.0 檔案分成兩側

| 側別 | 檔案 | 讀取者 |
| --- | --- | --- |
| **safe** `runs/<run_id>/safe_bundle/` | `manifest.json`、`scene_static.json`、`cameras.json`、`event_A.query.json`／`event_B1.query.json`、`rgb_index.json`、`runtime_profile.json`、`outputs/`（日後凍結的 RGB 推得輸出） | 正式服務；只透過 safe manifest 的 allowlist 開啟 |
| **private** `private_evaluation/<run_id>/` | `production_manifest.json`、`event_A.validation.json`／`event_B1.validation.json`、`persons.sim.json`、`gt/` | 產製端；評估端只在輸出凍結後讀 |

- safe manifest 不得含事件腳本、私有 locator、generator script 或 config 的內容。它可以持有不透明的 source hash，但不得解析 private 內容。
- `event_*.validation.json` 不得出現在正式 loader 會遞迴開啟的檔案集合中。

### 3.1 座標、尺度與樓層（`scene_static.json`）

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `schema_version` | string | 是 | `controlled-scene.static.v1` |
| `scene_id` | string | 是 | `controlled-l-corridor`（不含版本號） |
| `scene_version` | integer | 是 | 初版 `1`；幾何改變就遞增 |
| `frame_id` | string | 是 | 世界座標系 ID |
| `length_unit`、`time_unit` | `"m"`、`"s"` | 是 | |
| `world_axes` | `"BLENDER_Z_UP_RIGHT_HANDED"` | 是 | |
| `floors[]` | array | 是 | `{floor_id, support_plane: {point_m, normal}, support_surface_ids[], source_static_sha256, approved_scope_ref}`。首版只有一層、一個平面；超出核准範圍一律 `UNKNOWN` |
| `source_static_sha256` | string | 是 | 靜態來源的 hash |

### 3.2 穩定 ID 規則

- 格式 `^[A-Z][A-Z0-9_]{2,63}$`。類別前綴：

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

- ID 存在 Blender 物件的 custom property `amidst_id`，不靠顯示名稱。
- 幾何修改不換 ID，只遞增 `geometry_version`。刪除的 ID 不得重用。
- 重複 ID 讓整份匯出無效。跨檔案的 ID 引用必須存在，類型也必須相符。

### 3.3 靜態物件（`objects[]`）與用途核准

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `id`、`class` | string、enum | 是 | `class`：`WALKABLE`、`WALL`、`OBSTACLE`、`PORTAL`、`STAIR`、`ROOM`、`CORRIDOR`、`AREA`、`DISPLAY_ONLY` |
| `source_mesh` | string | 是 | Blender 物件名稱，只作追溯 |
| `source_object_id` | string | 是 | 來源物件的穩定 ID |
| `geometry_ref`、`geometry_sha256` | string | 是 | 指向實際幾何檔與其 hash |
| `geometry_version`、`geometry_encoding_version` | integer、string | 是 | |
| `transform_applied` | `"WORLD_METRES"` | 是 | |
| `bounds_m` | `[[xmin,ymin,zmin],[xmax,ymax,zmax]]` | 是 | 只是外框；**hash 與外框都不能當碰撞或 raycast 幾何** |
| `source_method` | enum | 是 | `ANNOTATED_AT_CREATION` 或 `UNKNOWN`。這只描述來源方法，不代表用途已核准 |
| `allowed_purposes` | array | 是 | 從 `WALKABILITY`、`OCCLUSION`、`COLLISION`、`VISIBILITY_INDEX`、`DISPLAY` 中選 |
| `approval_status` | enum | 是 | `APPROVED`、`NOT_EVALUATED`、`REJECTED` |
| `scope_ref`、`approval_ref`、`approval_sha256` | string\|null | 是 | 核准範圍與核准紀錄 |
| `display_only` | boolean | 是 | `true` 時優先拒絕 walkability、occlusion、collision 用途 |

### 3.4 Walkable（`walkable[]`）：新場景唯一的推論用地圖

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `id`、`floor_id`、`support_surface_id` | string | 是 | |
| `polygon_m`、`holes_m` | polygon、array | 是 | 逆時針、不自交 |
| `geometry_ref`、`geometry_sha256` | string | 是 | |
| `status` | enum | 是 | `WALKABLE`、`BLOCKED`、`UNKNOWN`。未標的地面一律 `UNKNOWN` |
| `connections[]` | array | 是 | `{to_walk_id, via_portal_id or null}`，雙向各寫一次，必須對稱。`via_portal_id: null` 只用於已核准的連續地板接界，不代表可以穿牆 |
| `approval` | object | 是 | 見下 |

- 轉角這類重疊地板要有一致的聯集與歸屬規則：面積不得重複計算，也不得建立互相矛盾的連通。
- `approval`：
  - 還沒跑驗證時：`{status: "NOT_EVALUATED", verified_by: [], verification_sha256: null}`。
  - 跑過驗證後：填 verifier 名稱與版本、輸入 hash、報告 hash。
  - 不得預先寫成 C7、K7 都已驗證。
- K7 的 private 路線報告只留在 private 端。推論端能讀的收據，只含不洩漏路線的靜態核對結果。
- 驗證器（C7、K7）不自動改檔，只輸出 fail 或 `UNKNOWN` 報告。consumer 在不一致的範圍內 fail closed。人工修訂要產生新的 map 版本與 hash，舊檔不變。

### 3.5 牆與障礙物

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `id`、`floor_id` | string | 是 | |
| `footprint_m`、`base_z_m`、`height_m` | polygon、number、number | 是 | |
| `geometry_ref`、`geometry_sha256` | string | 是 | |
| `role` | enum | 是 | `PHYSICAL` 或 `DISPLAY`。`DISPLAY` 不進任何物理判斷 |
| `collision_scope` | enum | 是 | `EXACT_MESH` 必須能解析到實際 mesh；`FOOTPRINT_EXTRUDED` 只證明這個近似範圍內的碰撞，不能宣稱精確遮擋；`UNKNOWN` |
| `body_policy_ref`、`body_policy_sha256` | string | 是 | 淨空檢查依據的人體政策設定檔 |
| `allowed_purposes` | array | 是 | 同 §3.3 |

### 3.6 門與樓梯

**門（`portals[]`）：**

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `id`、`floor_id` | string | 是 | |
| `opening_m` | `{a:[x,y], b:[x,y], width_m, sill_z_m, height_m}` | 是 | 開口的兩端與底高 |
| `geometry_ref`、`geometry_sha256`、`geometry_version` | | 是 | |
| `connects` | `[walk_id, walk_id]` | 是 | 缺一側就是 `UNKNOWN` |
| `state` | enum | 是 | 首版固定 `OPEN`，是公開的靜態狀態；首版沒有動態門 |
| `allowed_purposes` | array | 是 | |

**樓梯（`stairs[]`）：**獨立分型，需要多層端點、支撐面與幾何，不套用門的 2D schema。首版 `stairs: []`。若預留了實體，標 `used_in_first_round: false, acceptance: NOT_ACCEPTED`，不進首版路徑。

### 3.7 攝影機：光學校正與 run 綁定分開

**光學校正（`cameras.json` 的 `cameras[]`，A、B1 共用）：**

| 新欄位 | 對應既有 safe camera 輸入（Codex 審查 §3） |
| --- | --- |
| `schema_version`、`camera_id` | `calibration.camera_id`；外層另有 `camera_ref`、`authority` |
| `camera_to_world` | 4×4，列優先，世界公尺；不轉置、不再縮放 |
| `convention: "BLENDER_NEG_Z_UP_Y"` | 沿用既有名稱：−Z 向前、+Y 向上；匯出時要核對旋轉矩陣與行列式 |
| `fx`、`fy`、`cx`、`cy`、`pixel_origin: "TOP_LEFT_CONTINUOUS"` | 不另加 0.5 pixel |
| `width`、`height`、`pixel_aspect_xy`、`render_resolution_percentage` | K 必須對應實際的 PNG |
| `shift_x`、`shift_y`、`sensor_fit`、`sensor_width_mm`、`sensor_height_mm`、`focal_length_mm` | 產製追溯；正式定位以核對後的 K 為準 |
| `clip_start`、`clip_end` | 公尺；不沿用 Office 的 24.7 m |
| `distortion: null`、`camera_model: "PINHOLE"` | |
| `floor_id`、`zone_id`、`meters_per_unit: 1.0` | 地板平面的 point、normal 與 source hash 另外綁定 |
| `static_validity` | 靜態 pose 的有效範圍 |
| `calibration_sha256` | canonical 光學內容的 hash。**不含 clock** |

新 JSON 不能直接送進舊的 strict schema，要透過明確的 adapter。

**run 綁定（`cameras.json` 的 `run_bindings[]`，每個 run 一份）：**`{run_id, camera_id, clock_id, valid_time_range_s, visibility_index_ref, binding_sha256}`。A 和 B1 不共用 clock。

### 3.8 事件情境

**`event_<A|B1>.query.json`（safe）：**

| 欄位 | 說明 |
| --- | --- |
| `schema_version`、`event_id`、`run_id` | `event_id` 只是 UI 選項，用來定位這個 run。source、run、clock 由 server 從 catalog 解析 |
| `duration_s`、`camera_ids`、`sampling_version` | 公開的技術資訊 |
| `suggested_queries[]` | `{target_region_ref, query_intent, time_range_s}`，只用來預填 UI，不參與配對或排序 |

safe 檔不得含人物數、路線、覆蓋時間窗或盲區答案。

**`event_<A|B1>.validation.json`（private）：**

| 欄位 | 說明 |
| --- | --- |
| `schema_version`、`source/run/clock` 的 ref 與 hash | |
| `target_area_id`、`entry_exit_portals[]` | |
| `observation_windows[]` | `{segment_id, time_range_s, region_m, required_cameras[], visible_part: FULL_BODY / FOOT / PARTIAL}` |
| `overlap_requirements[]` | `{cameras, region_m, time_range_s, visible_part}` |
| `designed_blind_intervals[]` | `{blind_id, region_polygon_m, expected_time_range_s, cameras_expected_blind: [這個 run 的鏡頭 ID]}` |
| `separation_requirements[]` | B1：`{rule: "MAX_ONE_PERSON_PER_CAMERA_FRAME", min_gap_s: 待約定}` |

時間、間隔、像素門檻都待約定。這個檔案**不進 runtime readiness**。

### 3.9 人物產製設定（private）

- `persons.sim.json` 的內容：`{person_sim_id, height_m, body_radius_m, gait, speed_mps, route_waypoints_m[], start_s, end_behavior, seed}`。
- 只供隔離的產製端，以及凍結後的評估。
- 固定 2 人是情境設定，不能拿來限制偵測數、替人物命名或挑選 prior。
- seed 不是正式推論的輸入。

### 3.10 Manifest

| safe `manifest.json` | private `production_manifest.json` |
| --- | --- |
| `schema_version`、`scene_id`、`scene_version`、`run_id`、`clock_id` | `blend_file_sha256`、`blender_version` |
| `sampling`：`{fps, image_size_px, format: "PNG_RGB8", sampling_version, duration_s, sample_count_per_camera, last_timestamp_s}` | Blender 影格對應（`frame_start`、`frame_step`、`fps`、`fps_base`） |
| allowlist：`scene_static`、`cameras`、`event query`、`rgb_index`、`runtime_profile` 的檔名與 `file_sha256` | generator script 與 config 的 hash、`random_seed` |
| 公共 config 的 hash（人體 prior、偵測器設定） | validation、`persons.sim`、GT 檔案清單與 hash |
| 不透明的 `source_sha256` | 作者路線、產製設定、完整相機與牆的細節 |

### 3.11 `rgb_index.json` 與 `runtime_profile.json`（safe）

- `rgb_index.json`：`{camera_id, frame_index, timestamp_s, rgb_ref, file_sha256}`，加上 expected grid 與 missing 紀錄。`rgb_ref` 是相對路徑，指向 canonical 檔；不用 symlink，也不複製。
- `runtime_profile.json`：技術準備度的期望值，只含 grid、hash、API 可用性。**不含**人物的預期位置、盲窗或配對。

### 3.12 RGB 推得的輸出（CS-A 待核准的介面設計，CS-Q10）

**局部軌跡（Codex 主責）：**
- 內容：`{source/run/clock/camera, local_track_ref, ordered observation_refs 與 frame_refs, sample_indices, timestamps, gap_reasons, termination_reason, ambiguity_reason, producer, config_sha256, output_sha256}`。
- 局部軌跡只在單一鏡頭內有效，不跨鏡頭升級成身份。

**跨鏡頭候選（Claude 主責純介面與演算法，Codex 整合）：**
- 內容：`{candidate_ref, endpoint local_track_ref 與 observation_ref, eligibility, alternatives, unassociated_baseline, evidence_refs, scope, config_sha256, output_sha256}`。

**共同規則：**
- 讀不到資料時填 `null` 或 `UNKNOWN`。
- 不得填 actor ID，也不得使用事件答案。
- 沒有局部軌跡時，方向是 `UNKNOWN`，曲線不連接。

## 4. 檔案與存放

依 Codex 審查 §5，屬於 CS-A 待核准的介面設計。

- 資料根是 `data/pilot/controlled_scene_v1`，位於資產 checkout 中被 Git 忽略的 data 範圍內。
  - 服務以相對於 checkout 的路徑解析，不把本機絕對路徑寫進公開 payload。
  - 「不放共用 checkout」的意思是「不追蹤 Git」。

```text
data/pilot/controlled_scene_v1/
  assets/controlled_scene_v1.blend
  runs/<run_id>/
    rgb/<CAM_ID>/frame_<frame_index:06d>.png
    safe_bundle/manifest.json
    safe_bundle/scene_static.json
    safe_bundle/cameras.json
    safe_bundle/event_<A|B1>.query.json
    safe_bundle/rgb_index.json
    safe_bundle/runtime_profile.json
    safe_bundle/outputs/
  private_evaluation/<run_id>/
    production_manifest.json
    event_<A|B1>.validation.json
    persons.sim.json
    gt/
  derived/<run_id>/
```

- **run ID：**格式是 `ctrl-lcorr-s<scene_version>-<a|b1|b2>-<sampling_version>-r<revision:03d>`。第一版預定為 `ctrl-lcorr-s1-a-5fps-v1-r001`、`ctrl-lcorr-s1-b1-5fps-v1-r001`。這兩個是預定的 ID，run 還不存在。
- **版本：**
  - 10 Hz 用 `…-10hz-v2-r001`。
  - 影像、相機、產製設定或 source 改變時，產生新的 revision（必要時連 scene version 一起升），不得就地覆寫已封存的檔案。
  - `.blend` 封存後不覆寫；重新設計要用新檔名。
- **clock ID 與檔名：**
  - clock ID 是 `clock:<run_id>`；同一 run 的鏡頭共用一個 sample grid。
  - 事件 A 每台的 index 是 0–49，B1 是 0–99，檔名例如 `frame_000049.png`。
- **讀取範圍：**
  - server 只解析已註冊 run 的 safe manifest。
  - media allowlist 逐項解析 `rgb/<CAM_ID>/frame_*.png`，拒絕 symlink、越界路徑、`private_evaluation`、`derived` 與 hash 不符的檔案。
  - 不把整個資料根當成靜態目錄提供。
- **磁碟：**A＋B1 共 550 張 PNG，估 0.133–0.398 GiB（外推，不是新場景實測）。資料加 staging 的峰值額度是 1.5 GiB，不含 OS swap。授權 B 包前要重查可用空間（CS-Q11）。
- **B 包第一步：**另開一個隔離的 preview run `ctrl-lcorr-s1-preview-5fps-v1-r001`，四台各渲染一張。
  - manifest 標 `purpose: CALIBRATION_PREVIEW, complete: false`。
  - 這四張只能檢查外觀、校正、輸出與每張大小，**不算整段場景驗收**，也不能用來凍結預測。
  - 選哪一個 sample 只記在 private 端。

## 5. 事件情境規格

### 5.0 取樣（D25）

| 版本 | 解析度 | 幀率 | 格式 | 事件 A | 事件 B1 | 合計 | 狀態 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `5fps-v1` | 960×540 | 5 fps | PNG，8-bit RGB | 3 台 × 50 張 = 150 | 4 台 × 100 張 = 400 | 550 | **第一版** |
| `10hz-v2` | 960×540 | 10 Hz | PNG，8-bit RGB | 3 台 × 100 = 300 | 4 台 × 200 = 800 | 1,100 | **後續版本**：5 fps 穩定後才做；新的 run ID、pin、hash；不覆寫 `5fps-v1`，也不自動產生 |

### 5.1 場景配置（起始候選幾何，未驗證）

以下尺寸是起始候選，**不標 VERIFIED**。B 包要補上：
- 牆厚與牆高；
- 門的開口；
- 正式支撐面；
- 幾何檔。

| ID | 範圍（m） | 說明 |
| --- | --- | --- |
| `CORR_W`／`WALK_CORR_W` | x 0–17.4，y 0–2.4 | 西走廊 |
| `CORR_N`／`WALK_CORR_N` | x 15–17.4，y 0–12 | 北走廊；轉角 x 15–17.4、y 0–2.4 與西走廊重疊，依 §3.4 的規則歸屬一次 |
| `ROOM_R101`／`WALK_R101` | x 5–11，y −5–0 | 目標房間，無鏡頭 |
| `PORTAL_R101` | y = 0，x 7.4–8.6 | R101 門 |
| `ROOM_R102`／`WALK_R102` | x 17.4–22.4，y 7–11 | 對照房間 |
| `PORTAL_R102` | x = 17.4，y 8.4–9.6 | R102 門 |
| `AREA_R101_FRONT` | x 6.5–9.5，y 0–2.4 | 目標區域 |

| 鏡頭 | 起始位置與朝向 | 名義地面視野 |
| --- | --- | --- |
| `CAM_W1` | (0.3, 1.2, 2.8)，朝 +x | x ≈ 1–9 |
| `CAM_W2` | (15.0, 1.2, 2.8)，朝 −x | x ≈ 6–14.5 |
| `CAM_N1` | (16.2, 11.8, 2.8)，朝 −y | y ≈ 3.5–11 |
| `CAM_R102_CTRL` | R102 角落（精確 pose 未定） | 只有 R102 室內 |

- 完整的 rotation、K、FOV、clip，以及 R102 的精確 pose 都還沒提供，**所有實際覆蓋都是 `UNKNOWN`**。
- 靜態地面足跡只用來建議候選鏡頭。**地面看不到，不能證明整個人看不到**：頭部或軀幹仍可能出現在畫面裡。
- 轉角不加鏡頭（D25）。

**設計盲區 `BLIND_CORNER`：**L 形 polygon，沿可走區域，不跨牆：

```text
[[14.5, 0.0], [17.4, 0.0], [17.4, 3.5], [15.0, 3.5], [15.0, 2.4], [14.5, 2.4]]
```

- 這是 private 的預期值，不供推論使用。
- 驗收時要用 RGB 核對頭、軀幹、腳都看不到，不能只看 C5 的地面足跡。

### 5.2 事件 A：單人直線經過

| 項目 | 規格 |
| --- | --- |
| 人數 | 1 |
| 路線 | (1.0, 1.2) → (14.0, 1.2)，名義速度 1.3 m/s |
| 時間 | `[0, 10)` s；sample 0–49；最後一個 sample 在 9.8 s（x ≈ 13.74）；x = 14 是半開區間的終點，沒有對應的 PNG |
| 渲染鏡頭 | `CAM_W1`、`CAM_W2`、`CAM_R102_CTRL`；不呼叫 C4b，不含 `CAM_N1` |
| 目標區域 | `AREA_R101_FRONT`；名義經過時間約 4.23–6.54 s |
| 全程覆蓋 | 每個 sample 至少一台的 RGB 看得到人 |
| **雙鏡重疊（D27）** | 人在目標區域內時，`CAM_W1` 和 `CAM_W2` **都要拍到全身（頭頂到腳），RGB 裡看得到接地**。不能用 bbox 底邊推定腳 |
| 近端出框風險 | 起點距 `CAM_W1` 水平只有 0.7 m，近端人物可能出框。這要在 B 包用 pose、FOV 或靜態結構解決，**不加第五台、不縮短盲窗**。調整後的實際覆蓋仍是 `UNKNOWN`，要在 CS-B 用 RGB 核對 |
| 設計盲區 | 無；任何缺檔記 `MISSING` |
| 對照鏡頭 | `CAM_R102_CTRL` 全程看不到人 |

### 5.3 事件 B1：兩人錯開、跨轉角

| 項目 | 規格（名義值） |
| --- | --- |
| 人數 | 2（固定；只是情境設定） |
| P1 | t = 0 從 (1.0, 1.2) 往東 → (16.2, 1.2) 轉北 → (16.2, 11.5)；25.5 m，約 19.6 s 抵達；之後停留或出場的方式寫在 private 設定 |
| P2 | t ≈ 8 s 從 (1.0, 1.2) 往東 → (8.0, 1.2)（約 13.4 s）→ 往南，約 14.3 s 穿過 `PORTAL_R101` → (8.0, −2.5)（約 16.2 s） |
| 時間 | `[0, 20)` s；sample 0–99 |
| 渲染鏡頭 | `CAM_W1`、`CAM_W2`、`CAM_N1`、`CAM_R102_CTRL` |
| 名義轉角時間窗 | 到 x = 14.5 約 10.4 s；到 y = 3.5 約 13.5 s。這約 3.1 s 只是地面 FOV 假設下的算術，**不是**人物已經看不到，也不是指定的 sample 全部都盲 |
| 名義錯開 | `CAM_W1`：P1 離開約 6.2 s，P2 約 8 s 進場，間隔約 1.8 s。`CAM_W2`：P1 離開約 10.4 s，P2 進入約 11.8 s，間隔約 1.5 s。都還沒用 RGB 驗證；最小間隔待約定 |
| **北端 y 11–11.5** | `CAM_N1` 的名義地面視野只到 y ≈ 11，P1 約 19.2 s 後走到 y > 11。**這段的覆蓋是 `UNKNOWN`**。B 包二選一：調整 `CAM_N1` 的 pose 讓它涵蓋，或在 private validation 中明列為「預期離開視野」。兩者都不是設計盲區，也不能默認唯一的缺口在轉角 |
| P2 進房後 | R101 內沒有鏡頭，但這不代表門外的鏡頭看不到門內。P2 是否可見，要由 RGB 判斷 |
| 驗收（D26） | 全身不可見、任一鏡頭任一影格最多 1 人，都要逐 sample 用 RGB 人工核對 |
| 負證據限制 | P2 出現的影格，對整張畫面是 `DETECTION_PRESENT`。沒偵測到特定的人，不等於整張影格 `NO_DETECTION`。D21 strict／suggestion 與可偵測性的區別照舊 |
| 關聯 | 不能用腳本把 `CAM_N1` 再出現的人認成 P1，也不能把 P2 接到 P1。沒有唯一的 RGB 證據時，保留多個候選或未關聯 |

### 5.4 事件 B2

- B2 另寫規格、另行驗收。
- B2 通過前，`AMBIGUOUS_MERGE` 不得當可用端點或位置（D8 修訂）。
- B1 不宣稱具備處理交會的能力。

## 6. Consumer API

### 6.0 後端第一批提案：D45 uncertainty及fixture scope（待Claude確認）

每個person estimate及curve的OBSERVED／INFERRED_CONNECTOR／BLIND_HYPOTHESIS／未來PREDICTION都必須帶`uncertainty`；任何嵌套物件若標`PROJECTED_OBSERVATION`、`INFERRED_INTERPOLATION`或`INFERRED_HYPOTHESIS`也同樣必填。最低欄位為`{status, method, units, bounds, reason, limitations[]}`。尚無實測誤差界時`status: UNKNOWN, bounds: null`，reason與limitations非空；明示「不是已量測準確度／機率／物理保證」。若有有界heuristic，標`BOUNDED_HEURISTIC`並提供界限、方法與單位，不當統計信賴界。缺少或無效回§2.3.1完整性錯誤，不填0或畫成確定人物／曲線。這是consumer驗證，**不修改C4a接地估計器**；D44的C4a v1.1另確認。

本批五端點的請求schema依`controlled-scene.<action-kebab>-request.v1`，**都帶session_ref／scene_id／run_id**（包括evidence_lookup），由server解析source／clock。person_layer、curve_layer以半開`time_range_s`查詢；curve_layer可加`t_s`只作高亮，不產新證據。fixture僅註冊`scene_id: controlled-l-corridor`／`run_id: fixture-controlled-5fps-v1-r001`，沒有影像、ground estimator、visibility index或可驗收的真實run。candidate骨架因索引未實作回UNKNOWN，已知／未知不相交不混用；不按偵測數排序。完整既有範例仍標NON_EXECUTABLE_EXCERPT，不能把本批骨架說成範例全部已實作。

端點（CS-Q5，**CS-A 待核准的介面設計**，都還沒實作）：
- `POST /api/candidate_cameras`
- `POST /api/synced_frames`
- `POST /api/person_layer`
- `POST /api/curve_layer`
- `POST /api/evidence_lookup`

這些端點都沿用 session／scene／run guard，不把新 payload 塞進舊的 D18 `target_reconstruction` 或舊 timeline；後端內部可以委派給舊核心。

**共通回應欄位：**
- `schema_version`；
- server 解析出的 `resolved_scope`（source、run、clock、sampling、scope、hash）；
- 完整 `provenance`（含 `gt_read: false`）、`output_sha256`；
- `identity_verdict: "UNCONFIRMED"`、`agent_used: false`。

回應不得含 session secret 或私有 locator。以下範例省略了部分欄位，標為 `NON_EXECUTABLE_EXCERPT`，不能當成可驗證的正式 payload。**數字都是示意。**

### 6.1 候選鏡頭查詢

請求（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "controlled-scene.candidate-cameras-request.v1",
  "session_ref": "sess-…",
  "scene_id": "controlled-l-corridor",
  "run_id": "ctrl-lcorr-s1-b1-5fps-v1-r001",
  "target_region_ref": "AREA_R101_FRONT",
  "target_polygon": null,
  "time_range_s": [8.0, 20.0],
  "query_intent": "ENTER_EXIT",
  "surrounding_policy_ref": "surround-policy-v1",
  "camera_ids": null,
  "page_size": 4,
  "cursor": null,
  "layout_capacity": 4
}
```

**請求規則：**
- `target_region_ref` 和 `target_polygon` 二選一。`target_polygon` 是 `{floor_id, frame_id, length_unit: "m", polygon_m}`；頂點數上限待約定。
- 時間用半開區間。`query_intent` 只有 `PASS_THROUGH`、`ENTER_EXIT`。
- 輸入的 `run_id` 只能選已註冊的 run，不能自訂 source pin。
- cursor 綁定 query、index、sampling 與 pin。
- 不接收：GT actor ID、renderer 路徑、已知的跨鏡頭身份、私有媒體路徑、事件答案。

回應（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "controlled-scene.candidate-cameras.v1",
  "status": "PARTIAL",
  "reason": "VISIBILITY_INDEX_UNAVAILABLE",
  "query_id": "cq-<由 query_sha256 導出>",
  "query_sha256": "…",
  "candidate_snapshot_sha256": "…",
  "resolved_scope": {
    "scene_id": "controlled-l-corridor", "scene_version": 1,
    "run_id": "ctrl-lcorr-s1-b1-5fps-v1-r001", "clock_id": "clock:ctrl-lcorr-s1-b1-5fps-v1-r001",
    "sampling_version": "5fps-v1", "time_range_s": [8.0, 20.0],
    "target_region_ref": "AREA_R101_FRONT", "floor_id": "FLOOR_1F", "length_unit": "m",
    "surrounding_policy_ref": "surround-policy-v1",
    "access_paths": [{"portal_id": "PORTAL_R101", "walk_ids": ["WALK_CORR_W", "WALK_R101"]}],
    "scene_static_sha256": "…", "camera_catalog_sha256": "…", "visibility_index_sha256": "…",
    "rgb_index_sha256": "…", "perception_version": null
  },
  "candidates": [
    {
      "camera_id": "CAM_W2",
      "rank": 1,
      "relation": "TARGET_FOOTPRINT_INTERSECT",
      "reason_codes": ["TARGET_FOOTPRINT_INTERSECT", "OVERLAP_AREA"],
      "related_region_refs": ["AREA_R101_FRONT", "PORTAL_R101"],
      "suggested_time_windows_s": [[8.0, 20.0]],
      "geometry_basis": {"footprint_method": "SOURCE_MESH_RAYCAST", "visibility_ref": "vis-…", "footprint_sha256": "…", "overlap_area_m2": 7.2, "detectability": "PASS"},
      "image_evidence": {"perception_status": "NOT_EVALUATED", "evaluated_frames": 0, "frame_records_read": 0, "frames_with_detection": null, "count_complete": false, "sample_frame_refs": []},
      "availability": "AVAILABLE",
      "unavailable_reason": null
    },
    {"camera_id": "CAM_W1", "rank": 2, "relation": "TARGET_FOOTPRINT_INTERSECT"},
    {"camera_id": "CAM_N1", "rank": 3, "relation": "NO_INTERSECTION"},
    {"camera_id": "CAM_R102_CTRL", "rank": 4, "relation": "UNKNOWN", "reason_codes": ["VISIBILITY_INDEX_UNAVAILABLE"], "availability": "PARTIAL"}
  ],
  "candidates_total": 4,
  "returned_count": 4,
  "next_cursor": null,
  "candidate_set_complete": false,
  "truncated": false,
  "unknown_camera_ids": ["CAM_R102_CTRL"],
  "recommended_camera_ids": ["CAM_W2", "CAM_W1", "CAM_N1", "CAM_R102_CTRL"],
  "ranking_basis": ["relation_tier", "overlap_area_m2_desc", "camera_id"],
  "stats": {"catalog_records_read": 4, "index_records_read": 3, "frame_records_read": 0, "latency_ms": {"total": 0}},
  "identity_verdict": "UNCONFIRMED",
  "agent_used": false,
  "provenance": {"producer": "candidate-cameras", "gt_read": false},
  "output_sha256": "…"
}
```

- **`relation`** 有四種：`TARGET_FOOTPRINT_INTERSECT`、`ACCESS_PATH_INTERSECT`、`NO_INTERSECTION`、`UNKNOWN`。
  - metadata 缺失時填 `UNKNOWN`，不能判成 `NO_INTERSECTION`。
  - 已知不相交的鏡頭也要保留在清單裡。
- **排序（D28）：**`relation_tier`（1 相交、2 通路、3 不相交、4 未知）→ `overlap_area_m2` 由大到小 → `camera_id`。
  - **偵測數不列入排序**，只是 `image_evidence` 中的附帶證據。
  - `perception_status` 與 `count_complete` 標明評估範圍與數量是否完整。
  - 沒有感知結果時，`frames_with_detection` 是 `null`，不是 0。
- **候選數量與完整性：**
  - `candidates_total` 是套用鏡頭目錄與篩選之後的集合大小；`returned_count` 是本頁筆數；還有下一頁時才有 `next_cursor`。
  - `candidate_set_complete` 表示整個集合都已經檢視過；分頁中的回應也可以是 complete。
  - `truncated` 只表示因為預算不足、無法完整求值。
  - metadata 未知的鏡頭列在 `unknown_camera_ids`，不省略。
- **其他：**
  - **整體狀態 `status`**（`READY`、`PARTIAL`、`UNKNOWN`）：
    - `READY`：在宣告的 scope 與 snapshot 下，候選所需的 metadata 與幾何都已完整求值。正常分頁本身不讓結果變成 `PARTIAL`；可選的感知未執行，也不會單獨讓結果變成 `PARTIAL`。
    - `PARTIAL`：部分必要的 metadata 或幾何缺失，或預算不足使部分結果無法求值。保留可用的候選，並附上 `unknown_camera_ids`、`truncated` 與 `reason`。上面的範例因為 `CAM_R102_CTRL` 的可見範圍索引缺失，所以是 `PARTIAL`。
    - `UNKNOWN`：無法提供有意義的候選結果。
    - **必要輸入缺失時，不得回 `READY`。**各狀態都不得把未知當成不相交，也不得把空結果解讀成「沒有人經過」。
  - 足跡或 suggestion 相交只是候選理由，不自動成為負證據。
  - 查詢在**沒有任何接地估計或局部追蹤**時也必須能回答（CS-Q12）。
  - `stats.latency_ms` 不計入 hash。

### 6.2 同步影格

請求：`{schema_version, session_ref, scene_id, run_id, t_s: 12.47, camera_ids: [最多 8 台]}`。單一 run、單一 clock、單一時間點。

回應（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "controlled-scene.synced-frames.v1",
  "t_s": 12.47,
  "clock_id": "clock:ctrl-lcorr-s1-b1-5fps-v1-r001",
  "sampling_version": "5fps-v1",
  "frame_rule": "LATEST_AT_OR_BEFORE_EXPECTED_GRID",
  "expected_frame_index": 62,
  "expected_timestamp_s": 12.4,
  "sample_age_s": 0.07,
  "tiles": [
    {"camera_id": "CAM_W2", "status": "READY", "frame_ref": "fr-…-CAM_W2-000062", "timestamp_s": 12.4, "clock_error_s": 0.0, "file_sha256": "…"},
    {"camera_id": "CAM_W1", "status": "READY", "frame_ref": "fr-…-CAM_W1-000062", "timestamp_s": 12.4, "clock_error_s": 0.0, "file_sha256": "…"},
    {"camera_id": "CAM_N1", "status": "MISSING", "frame_ref": null, "reason": "RGB_RECORD_ABSENT"},
    {"camera_id": "CAM_R102_CTRL", "status": "UNKNOWN", "frame_ref": null, "reason": "RUN_BINDING_UNAVAILABLE"}
  ]
}
```

- **選格規則：**依 sampling 的有理數 grid 算出預期的 index。該 sample 缺檔就回 `MISSING`，不回退到較早的可用影格。
- **時間欄位：**`sample_age_s = t − timestamp_s` 不是同步誤差；同步誤差另外記在 `clock_error_s`。邊界與容差寫在設定檔，不偷偷加 epsilon。
- **tile 狀態：**`READY`、`MISSING`、`OUT_OF_RANGE`、`UNKNOWN`。hash、source 或 pin 不符時是完整性錯誤，整個請求 fail closed（§2.3），不會出現在 tile 裡。
- **與 C5 的關係：**這不是 C5 `frame_retrieval`；C5 最多 64 張的建議影格，不能當同步影片的完整影格。
- **鏡頭數上限：**每次最多 8 台；超過 8 台時用候選目錄分頁（CS-Q13）。

### 6.3 3D 人物與區間圖層

回應（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "controlled-scene.person-layer.v1",
  "time_range_s": [12.0, 13.0],
  "estimates": [
    {
      "estimate_ref": "pe-…",
      "observation_ref": "obs-…-CAM_W1-000062-c0",
      "camera_id": "CAM_W1",
      "frame_ref": "fr-…-CAM_W1-000062",
      "rgb_file_sha256": "…",
      "calibration_sha256": "…",
      "floor_id": "FLOOR_1F",
      "timestamp_s": 12.4,
      "local_track_ref": null,
      "ground_estimate": {
        "status": "READY",
        "estimate_kind": "SEGMENT",
        "basis": "FOOT_RAY_PIXEL_BAND",
        "segment": {"near_m": [6.1, 1.0, 0.0], "far_m": [6.9, 1.3, 0.0], "raw_near_m": [6.0, 1.0, 0.0], "raw_far_m": [7.0, 1.3, 0.0], "length_m": 0.85},
        "constraints_applied": [],
        "contact_quality": {"status": "PASS"},
        "evidence_state": "PROJECTED_OBSERVATION",
        "output_sha256": "…"
      },
      "bbox_height_px": 214,
      "heading": {"state": "UNKNOWN", "reason": "LOCAL_TRACK_UNAVAILABLE", "direction_xy": null},
      "display": {"humanoid_range_allowed": true, "display_config_sha256": "…"},
      "identity_verdict": "UNCONFIRMED",
      "physical_verdict": "UNKNOWN"
    }
  ]
}
```

- **區間格式：**POINT 和 SEGMENT 都使用[區間觀測 v1 §3](OFFICE_INTERVAL_OBSERVATION_V1.md) 的完整 schema。
  - SEGMENT 的欄位是 `near_m`、`far_m`、`raw_near_m`、`raw_far_m`，加上 `height_prior` 等。
  - 原始觀測的 `MISSING` 或 `null` 不因 sibling estimate 是 READY 而被改寫。
- **方向：**沒有局部軌跡，或方向有歧義時，`heading` 是 `UNKNOWN`。不得拿區間的中點差分來假裝有方向。
- **display：**
  - display 是 UI 設定，有自己的 config hash，不從 `persons.sim.json` 取尺寸或姿態。
  - 人體 prior 要在評估前針對每個 run 宣告，套用到所有 RGB 元件，不依 actor 選。
  - D5 的常數不是新場景已通過的門檻。
  - 長區間不在中點放人形。

### 6.4 曲線圖層

回應（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "controlled-scene.curve-layer.v1",
  "curves": [
    {
      "curve_ref": "cv-…",
      "candidate_ref": null,
      "local_track_refs": ["lt-…"],
      "segments": [
        {"kind": "OBSERVED", "evidence_state": "PROJECTED_OBSERVATION", "sample_timestamps_s": [9.8, 10.0, 10.2], "support_refs": ["obs-…-000049-c0", "obs-…-000050-c0", "obs-…-000051-c0"], "geometry": {"type": "INTERVAL_SERIES"}},
        {"kind": "INFERRED_CONNECTOR", "evidence_state": "INFERRED_INTERPOLATION", "t_s": [10.0, 10.2], "support_refs": ["obs-…-000050-c0", "obs-…-000051-c0"], "local_track_ref": "lt-…", "geometry": {"type": "RIBBON"}},
        {"kind": "BLIND_HYPOTHESIS", "evidence_state": "INFERRED_HYPOTHESIS", "t_s": [10.4, 13.6], "hypothesis_response_sha256": "…", "hypothesis_refs": ["hyp-1"], "unassociated_baseline": true, "region_band": true},
        {"kind": "MISSING_GAP", "evidence_state": "MISSING", "t_s": [15.2, 15.4], "reason": "RGB_RECORD_ABSENT", "geometry": null}
      ],
      "result_sha256": "…",
      "map_sha256": "…",
      "policy_pins": {"body_policy_sha256": "…", "speed_config_sha256": "…"},
      "association": {"state": "INFERRED_HYPOTHESIS", "identity_verdict": "UNCONFIRMED"}
    }
  ],
  "time_highlight": {"t_s": 12.47, "window_s": 1.0},
  "kinds_reserved": ["PREDICTION"]
}
```

- **OBSERVED：**只存離散時間點上的區間序列。任何跨越 sample 的幾何都屬於 `INFERRED_CONNECTOR`。
- **連接：**只有同一條合法局部軌跡的兩端才能連接；連接一律畫虛線。單筆的橫向區間可以畫實線。
- **BLIND_HYPOTHESIS：**保留 K1 的多解與未關聯基線，不指定 actor。純時間高亮不會把假設切片改成內插。
- **MISSING_GAP：**原因不會是 hash 不符，因為完整性錯誤會中止載入。
- **B1：**不能把兩個人連成已確認身份。
- **PREDICTION：**留給 D 包。

### 6.5 點擊回溯證據

請求：`{schema_version, session_ref, pick: {layer: "curve", ref: "cv-…", result_sha256: "…", segment_index: 0, t_click_s: 10.27}}`

回應（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "controlled-scene.evidence-lookup.v1",
  "status": "READY",
  "nearest_support": {
    "observation_ref": "obs-…-CAM_W2-000051-c0",
    "camera_id": "CAM_W2",
    "frame_ref": "fr-…-CAM_W2-000051",
    "timestamp_s": 10.2,
    "support_offset_s": -0.07,
    "bbox_px": [412, 188, 470, 402]
  },
  "other_supports": ["obs-…-000050-c0", "obs-…-000052-c0"],
  "relation": "SUPPORTS_OBSERVED_SEGMENT",
  "jump": {"t_s": 10.2, "camera_ids": ["CAM_W2"]}
}
```

- server 會核對每個 ref 的 scene、run、clock 與 `result_sha256`；`segment_index` 指向的是那個版本的結果。
- `support_offset_s = timestamp_s − t_click_s`，和播放器的 `sample_age_s` 是不同的欄位。
- 距離相等時，依序以 `timestamp_s`、`camera_id`、`observation_ref` 決定，確保結果穩定。

| 點到的東西 | `relation` | 跳轉 |
| --- | --- | --- |
| 觀測區間或點 | `IS_OBSERVATION` | 跳到該觀測自己的影格 |
| `OBSERVED` 段 | `SUPPORTS_OBSERVED_SEGMENT` | 跳到時間最近的支持觀測自己的時間 |
| `INFERRED_CONNECTOR` | `ENDPOINTS_OF_CONNECTOR` | 跳到較近的一端；另一端列在 `other_supports` |
| `BLIND_HYPOTHESIS` | `HYPOTHESIS_ENDPOINTS_AND_NEGATIVE_EVIDENCE` | 不自動跳轉；列出兩端觀測與負證據影格 |
| `MISSING_GAP` | `NO_SUPPORT` | 不跳轉 |

不會自動補上 GT 或鄰近 run 的資料。

## 7. GT 隔離邊界

依 D26。

| 資料 | 正式系統（檢索、排序、關聯、定位、預測、播放、runtime readiness） | CS-B 場景驗收 | 凍結後評估 |
| --- | --- | --- | --- |
| safe RGB（經 hash 驗證） | 可讀 | 可讀（人工逐格看） | 可讀 |
| 已核准用途的靜態幾何、校正、只用靜態資料建的索引（D1） | 可讀 | 可讀 | 可讀 |
| `event_*.query.json` | 只用來預填 UI | 可讀 | 可讀 |
| `runtime_profile.json` | 可讀（只有技術期望值） | 可讀 | 可讀 |
| `event_*.validation.json`（覆蓋、盲窗、錯開） | **禁止** | 可讀，作為人工核對的清單 | 可讀 |
| `production_manifest.json`、generator 設定、seed | **禁止** | 可讀（核對產製完整性） | 可讀 |
| `persons.sim.json`、actor、路線 | **禁止** | 可讀（產製端知道作者路線） | 可讀 |
| GT 軌跡、mask、visibility、depth | **禁止** | **禁止**（D26） | 輸出凍結且 hash 驗證後才可讀 |

- **CS-B 的做法（D26）：**用 RGB 人工逐格核對覆蓋與 B1 錯開，加上靜態標記、校正核對與產製完整性。
  - 產製端可以依腳本生成 RGB，但腳本與 GT 不能當正式系統的輸入。
  - GT 與 mask 的數值評估延到輸出凍結後。若要提前讀 GT，需要使用者另外改訂邊界。
- **靜態索引：**靜態 raycast 只讀不含人物的靜態場景。
- **路徑防護：**
  - 採用遞迴 allowlist 與 realpath containment，拒絕 symlink 和路徑穿越；不只靠敏感欄位黑名單或目錄名稱。
  - 先做 schema 與路徑檢查，再做 IO，不能在開啟 GT 之後才回錯。
  - 錯誤訊息不得回顯私有路徑。
- **錯誤碼（CS-Q6，CS-A 待核准的介面設計）：**

  | 錯誤碼 | 狀況 |
  | --- | --- |
  | `FORBIDDEN_INFERENCE_INPUT`（HTTP 422） | 請求帶了禁用欄位或額外欄位 |
  | `FORBIDDEN_DATA_SCOPE`（HTTP 403） | server 拒絕 private 或 GT locator |
  | `DataIntegrityError`（附具體原因） | sealed 檔案、source 或 hash 錯誤；該 run 不可用 |

- **預填與手動查詢的比較：**在同一個正規化 query、snapshot、page、layout 與 session scope 下，比較 canonical 語意 payload 與 `output_sha256`。
  - latency 等計時欄位不比較。
  - `query_id` 由 hash 導出，不隨機產生。
  - 不得因為查詢來自預填或手動而產生不同的排序。
- **GT 面板：**正式播放沒有 GT fallback。GT 回放只出現在凍結後、標 `EVALUATION` 的獨立面板。

## 8. 驗收表

三欄分開驗收，不能互相代替。
- 數值門檻都待約定（CS-Q9），寫進版本化設定檔。
- 還沒執行的項目一律標 `NOT_EVALUATED`。
- validator 的 schema 零錯誤，不等於幾何或品質通過。

| 項目 | CS-B 場景符合條件（RGB 人工＋靜態／校正／產製完整性；不讀 GT） | 影像估計正確（正式系統，不讀 GT） | 凍結後評估（可讀 GT／mask） |
| --- | --- | --- | --- |
| 座標與尺度 | 單位 m；支撐面與相機 pose 互相一致 | 接地估計使用同一支撐面與尺度 | — |
| 標記 | §3 必填欄位齊全；ID 唯一；跨檔引用有效；用途核准狀態明確 | — | — |
| Walkable | C7 mesh 檢查與 K7 靜態檢查的報告已產生；不一致的範圍 fail closed | K1 只讀已核准的 walkable | 路線不違反地圖 |
| 攝影機 | 完整校正（§3.7）；K 對應 PNG；run binding 與 clock 完整 | 同步：`clock_error_s` ≤ 容差 | — |
| 覆蓋與重疊（D27） | 逐 sample RGB 人工核對：事件 A 全程至少一台可見；目標區域內 W1、W2 都拍到全身與接地 | 候選查詢可重現；分頁不漏不重；無靜默截斷；沒有定位也能查 | 候選召回（待約定） |
| 設計盲區 | 逐 sample RGB 人工核對 `BLIND_CORNER` 時段頭、軀幹、腳都看不到；北端 y 11–11.5 照 §5.3 處理 | 盲區不畫位置 | K1 範圍帶涵蓋率（待約定） |
| B1 錯開 | 逐 sample RGB 核對任一鏡頭任一影格最多 1 人 | 兩人沒被連成同一條曲線；同一鏡頭只有一人不代表身份已關聯 | 關聯正確率（待約定） |
| 人物 | 產製端確認接地動畫與淨空設定已套用；body policy 是預先宣告的設定 | — | 接地區間涵蓋率與長度（待約定）；淨空實際通過另外證明，未使用的範圍為 `UNKNOWN` |
| 缺影格與完整性 | 列出所有非設計的缺檔 | 缺檔顯示 `MISSING`；完整性錯誤 fatal | — |
| 內插 | — | 只有內插算出的幾何標 `INFERRED_INTERPOLATION`；假設切片維持 `INFERRED_HYPOTHESIS` | — |
| 點擊回溯 | — | 每個可點元素都回到支持證據或 `NO_SUPPORT`；距離相等時結果穩定 | — |
| GT 隔離 | — | 注入禁用目錄或欄位時拒絕；預填與手動語意相同；`gt_read: false` | GT 只在凍結並驗證 hash 後載入 |
| 取樣版本 | 5 fps 與 10 Hz 是不同的 run 與 hash；5 fps 封存後不變 | 回應帶 `sampling_version` | — |
| 原資產 | 舊校園、Office 的 `.blend`、RGB、GT 都不變 | — | — |
| 綠球 | — | 不出現綠球或球狀替身 | — |

## 9. 待決問題

共 14 題（CS-Q1–CS-Q14）。

| 編號 | 問題 | 狀態 |
| --- | --- | --- |
| CS-Q1 | 校正格式 | **CS-A 待核准的介面設計**：投影核心沿用；新 JSON 透過明確 adapter 轉換；光學校正與 run clock 分開（§3.7） |
| CS-Q2 | 資料根 | **CS-A 待核准的介面設計**：`data/pilot/controlled_scene_v1`，被 Git 忽略；只存一份 RGB；新的 allowlist 與 loader adapter 之後實作（§4） |
| CS-Q3 | 事件 A 重疊的可見部位 | **已關閉（D27）**：雙鏡全身＋接地 |
| CS-Q4 | 偵測數是否列入排序 | **已關閉（D28）**：不列入；只當附帶證據 |
| CS-Q5 | 端點 | **CS-A 待核准的介面設計**：五個新端點（§6） |
| CS-Q6 | GT 誤入的錯誤碼 | **CS-A 待核准的介面設計**：`FORBIDDEN_INFERENCE_INPUT`、`FORBIDDEN_DATA_SCOPE`、`DataIntegrityError`（§7） |
| CS-Q7 | C5 上限 | **CS-A 待核准的介面設計**：舊限制（4 鏡頭、20 s、64 張建議、512 筆、5 s）保留，不為新 Demo 全域放大。5 fps 的 B1 400 筆在 512 內，但 64 張建議不等於 400 張都能回傳。10 Hz 的 800 筆要用綁定穩定 snapshot 的半開時間分窗或鏡頭分批，跨窗去除重複的 frame key 並彙總完整性；整體預算待約定，不能用無限分頁繞過上限。同步播放走 §6.2，不占用 C5 的建議上限 |
| CS-Q8 | 多組端點 | **CS-A 待核准的介面設計**：新 adapter，舊 D18 guard 原樣保留給舊 run。事件 A 不呼叫。B1 由 RGB 局部軌跡的結束與開始產生候選端點組，附兩端 ref、hash、clock、eligibility、`candidate_ref`、未關聯基線、多解與整條路徑的時間與速度檢查。別人的觀測不再全域阻擋；同一候選若有中間支持就分段。配對不讀 actor 或盲窗；沒有合法端點就回 `UNKNOWN`。Claude 起草純候選介面，Codex 接 adapter |
| CS-Q9 | 所有數值門檻 | **OPEN**：同步誤差（與 sample age 分開）、人形區間門檻、通路距離、B1 間隔、召回與涵蓋率、polygon 頂點數、tracking 的缺口、速度與方向條件、批次預算。在生成或凍結前約定；會影響鏡頭或場景設計的門檻，要在生成前定。不看新 GT 之後倒推調整 |
| CS-Q10 | 局部軌跡與關聯的分工 | **CS-A 待核准的介面設計**：Codex 主責 RGB-only 局部追蹤與感知 wrapper；Claude 主責可分離的純關聯候選介面與演算法，Codex 整合（§3.12） |
| CS-Q11 | 磁碟 | 授權 B 包前重查。Codex 審查時量到約 16.90 GiB 可用（比準備文件時的 11.24 GiB 多，原因未推論）。產出規模維持 1.5 GiB；12 GiB 起跑目標只是既有建議，尚未實作成門檻 |
| CS-Q12 | 沒有定位時的候選查詢 | **CS-A 待核准的介面設計**：`TimeFrameIndex` 本身只需要 metadata；依賴 `_ground_estimates` 的是 `FrameRetrievalIndex` 的初始化與 provenance 抽取。新的候選 loader 從 safe catalog 與 run config 取 provenance，感知與定位只是可選的補充，不為了湊 provenance 造假估計 |
| CS-Q13 | 8 格 | **CS-A 待核准的介面設計**：8 格與超過 8 台先用 UI fixture 驗收，真實場景只有 3 或 4 台。`synced_frames` 每次最多 8 台；超過 8 台用目錄分頁並保留全集合。不並行呼叫兩次舊 timeline 再假裝是同一個 snapshot |
| CS-Q14 | wrapper 寫死值 | **CS-A 待核准的介面設計**：preset、launcher、rehearsal-check 改讀 safe manifest 的 `sampling`、`duration`、`camera_ids`、`rgb_index`，以及 `runtime_profile` 的技術期望值。**不讀** private 的情境驗收表 |

## 10. 對照紀錄

### 10.1 Codex CS-A 審查「修改」項目的處置

| Codex 審查條目 | 本版處置 |
| --- | --- |
| 標頭：依據改固定 SHA；舊 Office 條文不隨引用移入 | §0.1 |
| §1 模擬／評估資料 | §1、§7 |
| §2 影格對應：零起算 sample index、private Blender 對應、`duration_s` 與 `last_timestamp_s` 分開 | §2 |
| §2 Hash：`file` 與 `content` 分名、序列化設定、幾何 hash 規則 | §2.1 |
| §2.1 內插：同一軌跡、RGB 判斷缺口、假設切片不改標 | §2.2 |
| §3 檔案分成 safe 與 private manifest | §3.0、§3.10 |
| §3.1 scene ID 與版本分開、`frame_id`、支撐面 point 與 normal、核准範圍 | §3.1 |
| §3.3 幾何 ref、encoding、用途核准 | §3.3 |
| §3.4 approval 未評估時不預填；驗證器不改檔、fail closed | §3.4 |
| §3.5 牆的幾何、body policy、EXACT_MESH 規則 | §3.5 |
| §3.6 門的底高與幾何；樓梯獨立分型 | §3.6 |
| §3.7 完整校正映射；clock 不進光學 hash | §3.7 |
| §3.8 validation 檔全部 private，不進 runtime readiness | §3.8 |
| §3.10 safe 與 production manifest 分開 | §3.10、§3.11 |
| §5.1 起始幾何不標 VERIFIED；地面看不到不證明人物看不到；L 形盲區 | §5.1 |
| §5.2 雙鏡可見部位 | §5.2（D27） |
| §5.3 逐 sample RGB；房內可能可見；北端 y 11–11.5 | §5.3 |
| §6 共通回應、`NON_EXECUTABLE_EXCERPT` | §6 |
| §6.1 query hash、snapshot hash、`relation: UNKNOWN`、排序、`image_evidence`、完整性語意 | §6.1（D28） |
| §6.2 依 grid 選格、不回退、`sample_age_s` 與 `clock_error_s`、完整性錯誤不降格 | §6.2、§2.3 |
| §6.3 完整區間 schema、RGB ref、heading、display hash、人體 prior | §6.3 |
| §6.4 OBSERVED 與 CONNECTOR 的界線、軌跡 ref、pin、假設切片 | §6.4 |
| §6.5 ref 核對、`support_offset_s`、穩定排序 | §6.5 |
| §7 可讀邊界、allowlist、預填等價的定義 | §7（D26） |
| §8 RGB 驗收與 GT 指標分欄；新增注入、分頁、截斷、錯連、原資產檢查 | §8 |
| §9 共 14 題 | §9 |
| §10.2 Q14 不讀 private | CS-Q14 |

### 10.2 與 Codex 準備文件（`14a3ffb`）的對照

第 2 版已對齊的項目（半開區間、事件 A 3 台、550 張、一份 RGB、候選欄位、未物化的局部軌跡、多人負證據、同步與建議影格分開），第 3 版都保留。原本列為差異的項目，現在的狀態都併入 §9。
