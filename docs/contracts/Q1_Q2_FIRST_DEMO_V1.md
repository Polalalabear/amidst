# Q1–Q5 第一版 Demo 契約 v1 草案（`Q1_Q2_FIRST_DEMO_V1`）

狀態：**DRAFT，等 Codex 確認、使用者核准。**本文所有欄位、端點與工具**都還沒有實作**；確認前不得當成已核准契約實作。

- 用途：Codex、Claude 與組員並行開發 Q1–Q5 第一版時的交接依據。資料在模組之間只透過本文的 schema 傳遞。
- 本文標示規則（沿用 [受控場景契約 v1.1](#01-依據固定版本) 的寫法）：
  - **「待約定」**：數值門檻。一律由 Codex 提案、使用者核定，本文不定數字。全部列在 §11 參數表。
  - `UNKNOWN`：沒有依據。
  - `NON_EXECUTABLE_EXCERPT`：範例只示意欄位，不是可執行的 fixture；範例中的數字不是門檻。
- 本文不重抄 v1.1 的條文，只引用章節。引用的 v1.1 一律指 `98451bd` 版（`docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md`，在 #65 分支上）。

| 版本 | Commit | 內容 |
| --- | --- | --- |
| v1 草案 | 本版 | 初稿：偵測索引、兩層圖、Q1／Q3／Q2・Q4・Q5、時間對應、共通回應欄位、參數表、待決問題 |

## 0. 依據與決定

### 0.1 依據（固定版本）

| 來源 | 版本 | 用途 |
| --- | --- | --- |
| D63（使用者決定，2026-10-20） | [#65 留言](https://github.com/Polalalabear/amidst/pull/65)、[#81 留言](https://github.com/Polalalabear/amidst/pull/81)，標題「## D63」，2026-10-20T06:44Z | 主線範圍、r004、RT-DETR、HSV 顏色訊號、身分 |
| D63 修訂 | **本文撰寫時（2026-10-20）尚未貼出。**以協調者交接摘要為準，見 §0.2 | Q1–Q5、Agent 依序取證與兜底 |
| Codex 討論稿 | 資產 repo 工作樹 `docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md`，**未提交、沒有 commit**；本文讀到的版本檔案 SHA-256 `ba9a317022db73c07ca91120ca71e1e2acf94660c34fae3d8029132d3478aa0d` | 兩層圖、第一版流程、最小資料契約 |
| 受控場景契約 v1.1 | `98451bd` | §2 時間慣例、§2.1 hash、§2.3 缺格、§3.6 門、§3.7 鏡頭、§6.1 候選鏡頭與 D28 排序、§7 GT 隔離 |
| Agent 檢索邊界 | 資產 repo `docs/engineering/AGENT_RETRIEVAL_BOUNDARY.md`，檔案 SHA-256 `3e8fb2ded00ac4010b3c660bba6ef4518d51b72fbe3e0d0c4515d48b8af11743` | Agent 只用 typed tools、有界動作、排序歸決定性服務 |
| K7 r003 靜態幾何驗證 | [#82](https://github.com/Polalalabear/amidst/pull/82) @ `6e689f9`（未合併、未核准） | `PORTAL_R102` 只當拓撲連通 |
| 開發規則 | `docs/specs/DEVELOPMENT_RULES.md` @ `f481fe0` | GT 隔離、Agent 不做幾何與排序；見 §0.3 的衝突 |

Codex 正在依協調者的審查修訂討論稿（加入 r004 修改表、提案門檻等）。本文**沒有等那一版**；修訂稿出來後，以 §12 對照表逐項對齊，數值一律留在 §11。

### 0.2 D63 與修訂摘要

**D63（已貼出，原文見上表連結）：**
- (a) Q1／Q2 是主線；3D 重現線（#81 的 2b–2d、CS-C／CS-D、#84、#85）暫停保留，不關、不刪。2a（#80）與 workbench-v2 外框照常沿用。
- (b) 場景修改**另存 r004**；r003 與 A／B1 的 pin（D53、D59）不變。紅衣／藍衣只用於 r004 的新 run。
- (c) 原文：LLM 只做語意解析與說明，切鏡由決定性規則決定，`agent_used` 維持 `false`；LLM 選鏡留第二階段，需先修 DEVELOPMENT_RULES。**此項已由下面的修訂取代。**
- (d) 允許在 RT-DETR 人物框上半身做最小 HSV 顏色統計，輸出 `STRONG`／`WEAK`／`NONE`／`UNKNOWN`，記錄方法版本與 hash；身分一律 `UNCONFIRMED`；不導入 ByteTrack／OSNet／ReID。
- 不授權：建 r004、渲染、下載 RT-DETR 權重、合併、凍結、讀 GT、外部 API。

**D63 修訂（尚未貼出，依協調者交接摘要；貼出後以原文為準，不一致時本文改版）：**
- 主線擴為 Q1–Q5：
  - **Q1** 依條件找相機。
  - **Q2** 找畫面中某個人。
  - **Q3** 理解語意（自然語言 → 結構化查詢）。
  - **Q4** 模型以自己的辨識判斷畫面是否含目標。
  - **Q5** 目標離開鏡頭時判斷是否切鏡。
- 候選集合與順序由兩層圖＋D28 決定性產生。Agent（Qwen，本機 Ollama）**依序**向合法 top-k 候選取證據並判斷是否切鏡；超過輪數或時間上限時改由決定性規則兜底。回應標 `agent_used` 與 fallback 原因，並記錄 prompt。
- LLM 也做自然語言解析與說明。
- 第一版不做同色干擾。身分一律 `UNCONFIRMED`。GT 不進推論。

### 0.3 與現行規則的衝突（實作前要先處理）

`docs/specs/DEVELOPMENT_RULES.md` @ `f481fe0` 第 57、62 行寫：Semantic Ranking 在決定性閉環完成後才考慮；基底演算法模式不經 Agent 決策。D63 修訂讓 Agent 決定「是否切到某個合法候選」，雖然不改候選集合與順序，仍屬於 Agent 決策。

本文的處理：
- Q5 定義兩種模式（§8.1）：`RULE_ONLY`（決定性規則，符合現行規則）與 `AGENT_SEQUENTIAL`（D63 修訂）。
- **規則負責人修訂 DEVELOPMENT_RULES 或列出例外之前，只能實作與展示 `RULE_ONLY`**；`AGENT_SEQUENTIAL` 的 schema 可以先實作與測試，但不得在 Demo 中啟用。本文不改規則（待決 Q-01）。
- Q3 的 LLM 解析與說明不改排序與候選，D63 (c) 已允許，不受此限。

## 1. 範圍與權限

**本契約涵蓋：**
1. 偵測索引（§4）：RT-DETR 對 safe RGB 的偵測結果與顏色摘要。
2. 兩層圖（§5）：Region Connectivity Graph 與 Camera Transition Graph。
3. Q1 查詢（§6）、Q3 自然語言解析（§7）、Q2／Q4／Q5 找人與切鏡（§8）。
4. 時間對應（§3）與共通回應欄位（§2.3）。

**權限邊界：**
- 人物的出現、位置與跨鏡頭串接，只能從 safe RGB 的偵測結果推得（v1.1 §1）。跨鏡頭結果是「條件相符的候選串接」，`identity_verdict` 一律 `UNCONFIRMED`。
- 「沒有偵測」不等於「不在畫面」或「已離開」。沒有其他觀測支持時，不斷言原因（遮擋、出視野、太小或漏檢）。
- 兩層圖只表示「依配置可能連通」，不是人體通行或碰撞認證；在 K7 等核准範圍以外的通行性一律 `UNKNOWN`。
- Agent 與 LLM 只能經 §8.4 與 §7 列出的 typed tools 讀資料，不能掃描檔案、跑任意 SQL 或 shell，也不能產生新的鏡頭、區域或觀測 ID（Agent 檢索邊界）。
- 第一版只用本機 Ollama 的 Qwen；不串接外部模型 API（v1.1 §7 外部 API 條文仍適用）。

**第一版不做：**同色干擾、ByteTrack／OSNet／ReID、跨鏡頭身分確認、3D 重現與接地、魚眼／PTZ、GT 對照、研究級評估。

## 2. 共通慣例

### 2.1 沿用 v1.1 的條文

| 主題 | 沿用 | 本文補充 |
| --- | --- | --- |
| 單位、世界座標、`frame_index` | v1.1 §2 | 無 |
| 時間 | v1.1 §2：比較、排序與 hash 一律用**整數微秒**；區間一律**半開** `[start, end)` | 本文時間欄位用 `_us` 結尾的整數。`_s` 只是顯示值，不進比較與 hash |
| 選格規則 | v1.1 §2.2 `LATEST_AT_OR_BEFORE`；不跳過 `MISSING` 去找更早的影格 | 無 |
| Hash | v1.1 §2.1：`file_sha256` 與 `content_sha256` 分開；canonical JSON 規則；計時欄位不進 hash | 本文所有 `*_sha256` 欄位都遵守這組規則 |
| 缺格與完整性錯誤 | v1.1 §2.3 全表 | `MISSING` 與 `DataIntegrityError` 的區分照舊；偵測索引另加 §4.3 的狀態 |
| 鏡頭校正與 run 綁定 | v1.1 §3.7 | 本文以 `camera_id` 與 `calibration_sha256` 引用，不另訂鏡頭 schema |
| 門 | v1.1 §3.6 `portals[]` | Region Graph 的邊以 `portal_id` 引用（§5.2） |
| 像素座標 | v1.1 §3.7 `pixel_origin: "TOP_LEFT_CONTINUOUS"` | bbox 用 `[x_min, y_min, x_max, y_max]`，單位為實際 PNG 的像素 |
| GT 隔離 | v1.1 §7 | 本文 §9 列出新增的禁止輸入 |

r004 的新 run 需要自己的 `rgb_index`、`cameras.json` run 綁定與 `scene_static`。r004 尚未授權建立；本文以 `scene_revision` 欄位引用，值待 r004 產生後填入。

### 2.2 ID 與命名

- schema 名稱前綴一律 `q-demo.`，例如 `q-demo.detection-index.v1`。
- ID 由內容決定，不隨機產生：
  - `index_id`、`graph_id`：`<kind>:<scene_revision>:<run_id 或 static>:<content_sha256 前 16 碼>`。
  - `observation_id`：`obs:<index_id 的 hash 段>:<camera_id>:<frame_index>:<det_ordinal>`。同一格內的偵測依 `score` 由大到小、再依 `bbox` 四值由小到大排序後編號。
  - `query_id`、`session_id`、`decision_id`：由正規化請求的 `content_sha256` 導出（同 v1.1 §7 的作法）。
- 換模型、換權重、換顏色方法或換取樣都會產生新的 `index_id`；舊 ID 不回收、不改寫。

### 2.3 共通回應欄位

Q1、Q2、Q3 的每個回應都帶以下欄位；Q5 沒有獨立回應，它的每筆決策紀錄（§8.7）帶 `fallback_reason`、`decided_by`（回應層的 `agent_used` 由它導出）與 hash 欄位（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "q-demo.<kind>.v1",
  "status": "READY",
  "reason": null,
  "resolved_scope": {
    "scene_id": "…", "scene_revision": "r004",
    "run_ids": ["…"], "clock_ids": ["…"],
    "clock_mapping_sha256": "…",
    "requested_time": {"kind": "WALL", "wall_range": ["2026-11-01T13:00:00+08:00", "2026-11-01T13:30:00+08:00"]},
    "resolved_source_ranges_us": [{"run_id": "…", "range_us": [0, 60000000]}],
    "time_coverage": {"coverage_complete": false, "uncovered_wall_ranges": [["2026-11-01T13:01:00+08:00", "2026-11-01T13:30:00+08:00"]]},
    "camera_ids": ["…"],
    "detection_index_id": "…", "detection_index_sha256": "…",
    "region_graph_sha256": "…", "camera_graph_sha256": "…",
    "class_map_sha256": "…", "color_method_version": "…",
    "parameter_set_id": "…", "parameter_set_sha256": "…"
  },
  "identity_verdict": "UNCONFIRMED",
  "agent_used": false,
  "fallback_reason": null,
  "provenance": {"producer": "…", "producer_version": "…", "gt_read": false, "input_refs": ["…"]},
  "stats": {"latency_ms": {"total": 0}},
  "output_sha256": "…"
}
```

| 欄位 | 規則 |
| --- | --- |
| `status` | 各端點自己的封閉清單（§6.3、§7.4、§8.7）。必要輸入缺失時不得回 `READY` |
| `resolved_scope` | 實際用到的範圍與每個輸入的版本或 hash。只列有用到的欄位；沒用到的填 `null`，不省略鍵 |
| `resolved_scope.time_coverage` | §3.3。展示資料只涵蓋部分請求時段時，`coverage_complete: false`，並列出沒涵蓋的時段 |
| `identity_verdict` | 固定 `UNCONFIRMED`。任何其他值都是 schema 錯誤 |
| `agent_used` | 這個回應的結果中，有沒有任何一步是 LLM 或 Agent 的輸出被採用。Q1 固定 `false`；Q3 依 §7.3；Q2／Q5 依 §8.6 |
| `fallback_reason` | 原本要用 LLM 或 Agent、最後改用規則時填 §8.6 的原因碼；沒有發生兜底時是 `null`。多步驟的回應另有逐步紀錄 |
| `provenance.gt_read` | 固定 `false`。正式服務讀了 GT 或 private 檔案就是錯誤，不得回應 |
| `provenance.input_refs` | 讀過的索引、圖、參數組與媒體的 ref，不含本機路徑 |
| `stats.latency_ms` | 不進 hash，也不進預填與手動查詢的比較 |
| `output_sha256` | 回應去掉 `output_sha256` 與 `stats` 後的 canonical `content_sha256`（v1.1 §2.1） |

**錯誤碼：**沿用 v1.1 §7 的 `FORBIDDEN_INFERENCE_INPUT`（422）、`FORBIDDEN_DATA_SCOPE`（403）、`DataIntegrityError`。本文新增的原因碼分列在各節。

## 3. 時間對應

### 3.1 來源時鐘與展示時鐘

- 每個 run 只有一個來源時鐘（`clock_id`，v1.1 §3.7 run 綁定）。來源時間從 0 開始，單位為整數微秒。
- Blender 產生的影像沒有真實的拍攝時刻。Q2 的「下午 1 點到 1:30」要靠一份**宣告的展示時鐘對應**，把牆鐘時間換成來源時間。這份對應是設定，不是觀測；回應中要標明。

`clock_mapping`（每個 run 一份，`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "q-demo.clock-mapping.v1",
  "run_id": "…", "clock_id": "…",
  "mapping_kind": "DECLARED_DEMO_CLOCK",
  "timezone": "Asia/Taipei",
  "wall_origin": "2026-11-01T13:00:00+08:00",
  "source_origin_us": 0,
  "rate": 1,
  "source_duration_us": 60000000,
  "declared_by": "…", "declared_at": "…",
  "content_sha256": "…"
}
```

| 欄位 | 規則 |
| --- | --- |
| `mapping_kind` | 第一版只有 `DECLARED_DEMO_CLOCK`。UI 要顯示「展示時鐘」，不得寫成實際拍攝時間 |
| `timezone` | IANA 名稱。`wall_origin` 必須是含 UTC 偏移的 ISO 8601，且偏移要和 `timezone` 在該日期一致，不一致就 fail closed |
| `rate` | 固定整數 1（來源 1 秒 ＝ 牆鐘 1 秒）。其他值第一版不支援 |
| 換算 | `wall = wall_origin + (source_us − source_origin_us)`；反向換算後，牆鐘範圍要落在 run 的 `[0, source_duration_us)` 才有來源資料 |

- 同一個查詢涉及多個 run 時，每個 run 各用自己的對應；牆鐘範圍重疊不代表兩個 run 是同一段時間的不同鏡頭（待決 Q-11）。
- 對應改了，`clock_mapping_sha256` 就變，所有依賴它的 `query_id` 與 `output_sha256` 也跟著變。

### 3.2 牆鐘輸入的解析

- 使用者輸入「下午 1 點到 1:30」時，日期與時區的預設值來自目前選定 run 的 `clock_mapping`（`wall_origin` 的日期與 `timezone`）。預設值要寫進 `resolved_scope.requested_time`，讓使用者看得到。
- 解析是決定性的（§7.2）：LLM 只抽出字面上的時間片段，換算由程式做。
- 跨午夜、缺結束時間、結束早於開始，都回 `TIME_EXPRESSION_INVALID`，不猜。

### 3.3 部分涵蓋要明示

把請求的牆鐘範圍和所有 run 的涵蓋範圍取交集：

| 情況 | 處理 |
| --- | --- |
| 請求範圍完全落在資料範圍內 | `coverage_complete: true` |
| 只有一部分有資料 | 只查有資料的部分；`coverage_complete: false`；`uncovered_wall_ranges` 列出沒涵蓋的時段；`status` 不得是 `READY`，改為 `PARTIAL`（`reason: TIME_SCOPE_PARTIAL`） |
| 完全沒有交集 | `status: OUT_OF_RANGE`，不查詢，不回「查無結果」 |

- 「查無結果」只能對有資料、而且已推論的時段成立（§6.3）。不得因為只渲染了 1 分鐘，就說 13:00–13:30「沒有紅衣人經過」。
- 偵測索引的取樣與推論範圍另外計算（§4.4），和時間涵蓋分開報告。

## 4. 偵測索引

### 4.1 來源與產生者

- 輸入只有 safe RGB（hash 驗證過，v1.1 §2.3）與模型檔。不讀 Blender 物件清單、事件腳本、`persons.sim.json`、GT、mask、depth、visibility。
- 索引記的是模型實際辨識出的內容。靜態設定（鏡頭朝向、區域、出口）放在 §5 的圖，不能代替畫面上的物件證據。
- 產生索引是離線批次；Q1–Q5 只讀索引，不在查詢時重跑模型（待決 Q-07 是否允許補推論）。

### 4.2 索引 manifest

`detection_index.json`（每個 run 一份，`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "q-demo.detection-index.v1",
  "index_id": "detidx:r004:<run_id>:<hash16>",
  "scene_id": "…", "scene_revision": "r004", "run_id": "…", "clock_id": "…",
  "rgb_index_sha256": "…",
  "detector": {
    "family": "RT-DETR",
    "variant": "UNKNOWN",
    "framework": "…", "framework_version": "…",
    "weights_file_sha256": "…",
    "weights_source": "…",
    "config_sha256": "…",
    "class_map": {"version": "coco80-v1", "content_sha256": "…"},
    "input_preprocess": {"resize_policy": "…", "input_size_px": [0, 0]},
    "index_score_floor": "待約定",
    "nms": {"applied": true, "iou": "待約定"},
    "device": "…"
  },
  "color_method": {
    "version": "upper-hsv-v1",
    "content_sha256": "…",
    "applies_to_classes": ["person"],
    "color_vocabulary": {"version": "colors-v1", "labels": ["red", "blue"], "content_sha256": "…"}
  },
  "sampling": {
    "policy": "EVERY_NTH_SAMPLE",
    "stride_samples": "待約定",
    "per_camera": [
      {"camera_id": "…", "sampled_ranges_us": [[0, 60000000]], "inferred_ranges_us": [[0, 60000000]], "not_inferred": [{"range_us": [0, 0], "reason": "…"}]}
    ]
  },
  "records_ref": "…", "records_file_sha256": "…",
  "content_sha256": "…",
  "provenance": {"producer": "detection-indexer", "producer_version": "…", "gt_read": false}
}
```

| 欄位 | 規則 |
| --- | --- |
| `detector.variant` | 實際的 RT-DETR 型號與權重名稱。權重下載未授權，現在是 `UNKNOWN` |
| `detector.weights_file_sha256` | 必填。缺了就不得產生索引 |
| `detector.class_map` | 模型實際的類別表。Q1 能查的類別只來自這張表加上 §6.2 的別名表 |
| `index_score_floor` | 低於這個分數的偵測不寫入索引。查詢端另有 `query_min_score`（§6.1），兩者分開 |
| `color_method` | 只對 `applies_to_classes` 的偵測算顏色；方法版本、參數與顏色詞彙都進 `content_sha256` |
| `sampling` | 見 §4.4 |

### 4.3 逐格紀錄

`records` 檔每格一筆，依 `(camera_id, frame_index)` 排序（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "frame_ref": "frame:<run_id>:<camera_id>:<frame_index>",
  "camera_id": "CAM_X", "frame_index": 12, "timestamp_us": 2400000,
  "rgb_file_sha256": "…",
  "frame_state": "INFERRED",
  "state_reason": null,
  "detections": [
    {
      "observation_id": "obs:…:CAM_X:12:0",
      "class_id": 0, "class_label": "person",
      "bbox_xyxy_px": [412.0, 180.5, 470.2, 355.0],
      "score": 0.0,
      "color": {
        "method_version": "upper-hsv-v1",
        "crop_box_xyxy_px": [0, 0, 0, 0],
        "crop_pixels": 0,
        "hsv_stats": {"hue_hist": [], "sat_mean": 0.0, "val_mean": 0.0},
        "verdicts": {"red": "STRONG", "blue": "NONE"},
        "unknown_reason": null
      }
    }
  ]
}
```

**`frame_state` 是封閉清單，每格只有一個：**

| `frame_state` | 意思 | `detections` |
| --- | --- | --- |
| `INFERRED` | 模型已在這格跑完 | 陣列；**空陣列才代表「無偵測」** |
| `NOT_SAMPLED` | 依取樣策略沒有選到這格 | `null` |
| `NOT_INFERRED` | 選到了，但沒有推論結果（例如尚未跑、推論失敗）；`state_reason` 必填 | `null` |
| `MISSING` | 這格列在 `rgb_index.missing[]`（v1.1 §2.3） | `null` |

- `NOT_SAMPLED`、`NOT_INFERRED`、`MISSING` 都不得解讀成「無偵測」。
- 已 pin 的影格檔案不存在、hash 不符或索引缺格，照 v1.1 §2.3 是 `DataIntegrityError`，整個 run fail closed，不寫成 `MISSING`。
- 「條件不符」不是索引狀態，是查詢結果（§6.3、§8.3）。索引只存模型輸出，不存任何查詢條件的答案。
- 第一版沒有跨格的 track ID。同鏡頭的連接只在 Q2 執行時由 §8.2 的連接器產生。

**顏色摘要（D63 (d)）：**
- 範圍是人物框的**上半身**；`crop_box_xyxy_px` 怎麼由 bbox 算出，寫在 `color_method` 的參數裡（比例「待約定」）。
- `verdicts` 對 `color_vocabulary` 中的每個顏色都要有值，只能是 `STRONG`、`WEAK`、`NONE`、`UNKNOWN`。分界「待約定」。
- 下列情況是 `UNKNOWN`，並填 `unknown_reason`：裁切像素數低於下限（`CROP_TOO_SMALL`）、框被畫面邊緣截斷超過比例（`CROP_TRUNCATED`）、亮度或飽和度不足（`LOW_LIGHT_OR_SATURATION`）。下限與比例「待約定」。
- 顏色是**輔助訊號**：不改 RT-DETR 的分數，不代表身分；`STRONG` 也只是「條件相符」。

### 4.4 取樣與推論範圍

- `sampled_ranges_us`：取樣策略涵蓋的時間。`inferred_ranges_us`：真的有推論結果的時間。兩者都是半開區間、依時間排序、不重疊。
- 查詢回應要報告查詢範圍內各鏡頭的取樣與推論涵蓋（§6.3 `coverage`），不得假定沒推論的時段和推論過的時段內容相同。
- 第一版可以先用少量代表影格建快速目錄（Codex 討論稿 §6），但那份目錄也要用同一個 schema 與 `frame_state`，不能另訂「這台有車」的旗標。

## 5. 兩層圖

### 5.1 共通規則

**可用的輸入（只有這四類）：**
1. `scene_static` 中 `approval_status: APPROVED`、而且 `allowed_purposes` 含對應用途的靜態幾何（v1.1 §3.3、§7）。
2. 靜態光學校正（v1.1 §3.7）。
3. 只用不含人物的靜態場景建的可見範圍索引（v1.1 §7「靜態索引」）。
4. 不含人物的靜態畫面（`static_frame_ref`，附 `file_sha256`），用來人工標出口 ROI。

**禁止的輸入：**事件腳本、作者路線、`persons.sim.json`、`event_*.validation.json`、GT、mask、depth、visibility、任何含人物的 RGB、偵測索引。兩層圖**不存任何人物的實際下一站或到達時間**。

**版本與 hash：**每張圖有 `graph_id`、`content_sha256`、`inputs[]`（每個輸入的 ref 與 hash）、`approval_status`（`DRAFT`、`APPROVED`）與核准來源。圖要在最終鏡頭配置固定後重建；r004 改了鏡頭或門，圖就要改版。

**未核准的圖：**`DRAFT` 的圖可以用於開發，但回應的 `status` 不得是 `READY`，`reason` 填 `GRAPH_NOT_APPROVED`。

### 5.2 Region Connectivity Graph

`region_graph.json`（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "q-demo.region-graph.v1",
  "graph_id": "rgraph:r004:static:<hash16>",
  "scene_id": "…", "scene_revision": "r004",
  "scene_static_sha256": "…",
  "approval_status": "DRAFT", "approval_ref": null,
  "regions": [
    {"region_id": "REG_CORR_W", "kind": "CORRIDOR_SEGMENT", "floor_id": "FLOOR_1F",
     "walk_ids": ["WALK_CORR_W"], "polygon_ref": "…", "polygon_sha256": "…"}
  ],
  "edges": [
    {"edge_id": "E_CORR_W__R101", "regions": ["REG_CORR_W", "REG_R101"],
     "via": {"kind": "PORTAL", "ref": "PORTAL_R101"},
     "direction": "BIDIRECTIONAL",
     "state": "OPEN",
     "traversability": "APPROVED_WALKABLE",
     "basis_refs": ["…"]}
  ],
  "inputs": [{"ref": "…", "sha256": "…"}],
  "content_sha256": "…"
}
```

| 欄位 | 規則 |
| --- | --- |
| `regions[].kind` | 封閉清單：`OUTDOOR`、`ENTRANCE`、`CORRIDOR_SEGMENT`、`CORNER`、`ROOM`、`STAIR_LANDING`。一個區域可對應多個 walk |
| `edges[].via.kind` | `PORTAL`（引用 v1.1 §3.6 `portals[].id`）、`ADJACENT`（同一 walk 內的分段界線，附界線 ref）、`STAIR`（第一版不用，`stairs: []`） |
| `direction` | `BIDIRECTIONAL` 或 `ONE_WAY`（附 `from`、`to`） |
| `state` | `OPEN`、`CLOSED`、`UNKNOWN`。`CLOSED` 的邊不進搜尋。`UNKNOWN` 的處理見 §5.4 |
| `traversability` | `APPROVED_WALKABLE`：門與兩側 walk 都經核准可通行。`TOPOLOGICAL_ONLY`：只表示拓撲相連，不保證人可通過。依 K7（#82），r003 的 `PORTAL_R102` 屬於後者；r004 要重新驗證 |

LLM 與 Agent 不得新增、刪除或改變任何邊；門的狀態未知時不能自行補通路。

### 5.3 Camera Transition Graph

`camera_graph.json`（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "q-demo.camera-transition-graph.v1",
  "graph_id": "cgraph:r004:static:<hash16>",
  "scene_id": "…", "scene_revision": "r004",
  "region_graph_sha256": "…", "camera_catalog_sha256": "…",
  "approval_status": "DRAFT", "approval_ref": null,
  "cameras": [
    {
      "camera_id": "CAM_A", "calibration_sha256": "…",
      "covered_regions": [{"region_id": "REG_CORR_W", "basis": "STATIC_VISIBILITY_INDEX", "visibility_ref": "…", "visible_area_m2": null}],
      "exit_zones": [
        {"exit_zone_id": "CAM_A:EXIT_LEFT",
         "roi_polygon_px": [[0, 300], [80, 300], [80, 540], [0, 540]],
         "leads_to_edge_ids": ["E_CORR_W__R101"],
         "mapping_basis": "MANUAL_ON_STATIC_FRAME",
         "static_frame_ref": "…", "static_frame_sha256": "…"}
      ],
      "entry_zones": []
    }
  ],
  "transitions": [
    {"transition_id": "T_CAM_A__CAM_B__1",
     "from_camera_id": "CAM_A", "to_camera_id": "CAM_B",
     "via_exit_zone_ids": ["CAM_A:EXIT_LEFT"],
     "to_entry_zone_ids": ["CAM_B:ENTRY_RIGHT"],
     "region_path": ["REG_CORR_W", "REG_CORNER", "REG_CORR_N"],
     "edge_path": ["…"],
     "relation": "BLIND_GAP",
     "region_hops": 2,
     "path_traversability": "TOPOLOGICAL_ONLY",
     "path_has_unknown_state": false,
     "nominal_path_length_m": null,
     "basis_refs": ["…"]}
  ],
  "inputs": [{"ref": "…", "sha256": "…"}],
  "content_sha256": "…"
}
```

| 欄位 | 規則 |
| --- | --- |
| `covered_regions[].basis` | `STATIC_VISIBILITY_INDEX`（核准的靜態可見範圍）或 `MANUAL_ON_STATIC_FRAME`（在不含人物的靜態畫面上人工標）。一台鏡頭可涵蓋多區；在同一區不代表看得到區內全部位置 |
| `exit_zones[]` | 畫面上的出口 ROI 對應 Region Graph 的邊。**畫面左側不等於世界左側**，對應要經校正投影或在靜態畫面上標記，並記 `mapping_basis` |
| `relation` | `OVERLAP`：兩台鏡頭在核准的可見範圍內有共同區域。`BLIND_GAP`：經過沒有鏡頭的區域才到。由圖與可見範圍算出，不由人物事件決定 |
| `path_traversability` | 路徑上最弱的一段：任一邊是 `TOPOLOGICAL_ONLY`，整條就是 `TOPOLOGICAL_ONLY` |
| `nominal_path_length_m` | 只有核准的 walkable 幾何能算時才填，否則 `null`；不讀人物路線 |

不是世界座標最近的鏡頭就相連；轉移只來自 Region Graph 的連通加上鏡頭涵蓋。

### 5.4 候選鏡頭的產生與排序（兩層圖＋D28）

決定性服務 `transition_candidates` 依下列步驟產生 Q5 的候選，Agent 與 LLM 都不能改：

1. **出口判定**：用目標最後一筆連接上的觀測（§8.2）的 bbox，對 `from_camera` 的 `exit_zones` 做判定，規則「待約定」（例如 bbox 底邊中點落在 ROI 內，或 bbox 與 ROI 的重疊比例達門檻）。
   - 剛好命中一個出口：用該出口。
   - 命中零個或多個：用該鏡頭**全部**出口，`exit_resolution: AMBIGUOUS`，不強選一個。
2. **展開**：取出這些出口對應的 `transitions`。`CLOSED` 的邊已排除；含 `UNKNOWN` 狀態邊的轉移保留，但標 `path_has_unknown_state: true`（待決 Q-04）。
3. **排序**：沿用 D28 的結構（v1.1 §6.1：關係層級 → 面積 → `camera_id`）並改成轉移版本：

   | 順位 | 排序鍵 |
   | --- | --- |
   | 1 | `exit_match_tier`：1 直接命中的出口、2 出口不明時展開的出口 |
   | 2 | `relation_tier`：1 `OVERLAP`、2 `BLIND_GAP` 且路徑全部 `OPEN`、3 路徑含 `UNKNOWN` 狀態邊 |
   | 3 | `region_hops`，由少到多 |
   | 4 | 目標鏡頭對入口區域的 `visible_area_m2`，由大到小；`null` 排最後 |
   | 5 | `camera_id`（字典序） |

   **偵測數與顏色不進排序**（D28 原則）；它們只是 §8.3 取到的證據。排序鍵與值要寫進每個候選的 `ranking_basis`。這個排序表本身也待 Codex 確認（待決 Q-03）。
4. **截斷**：取前 `top_k`（待約定）個，`candidate_set_complete` 與 `truncated` 的意思同 v1.1 §6.1。被截掉的候選要列數量，不得當成「不可能」。
5. **快照**：輸出 `candidate_snapshot_sha256`。Agent 的每個選擇都要引用這個快照。

## 6. Q1：依條件找相機

### 6.1 請求

```json
{
  "schema_version": "q-demo.q1-request.v1",
  "session_ref": "sess-…",
  "scene_id": "…", "run_ids": ["…"],
  "time": {"kind": "SOURCE", "run_id": "…", "range_us": [0, 60000000]},
  "condition": {
    "class_label": "car",
    "min_count_per_frame": 1,
    "color": null,
    "query_min_score": "待約定"
  },
  "camera_ids": null,
  "region_ids": null,
  "page_size": 12, "cursor": null,
  "origin": "MANUAL"
}
```

| 欄位 | 規則 |
| --- | --- |
| `time` | `kind: SOURCE`（指定 run 與來源微秒）或 `kind: WALL`（`wall_range`，經 §3 換算）。二選一 |
| `condition.class_label` | 必須在 `class_map` 或 §6.2 的別名表中。不在就回 `UNSUPPORTED_CLASS`（§6.3），不查詢 |
| `condition.color` | 只能用在 `person`；值必須在 `color_vocabulary`；附 `min_verdict`（`STRONG` 或 `WEAK`）。用在其他類別回 `UNSUPPORTED_CONDITION` |
| `query_min_score` | 不得低於索引的 `index_score_floor`；低於時回 `FORBIDDEN_INFERENCE_INPUT` |
| `region_ids` | 只用 Camera Graph 的 `covered_regions` 過濾鏡頭，不代表物件在該區域內 |
| `origin` | `MANUAL`、`PREFILL`、`Q3_PARSED`。不影響結果；同一正規化請求的 `output_sha256` 必須相同（v1.1 §7） |
| 不接收 | GT actor ID、Blender 物件名、事件答案、私有路徑、自訂 source pin（v1.1 §6.1） |

### 6.2 類別別名表

- `class_alias.json`：把使用者用語（例如「車」「汽車」）對到 `class_map` 的標籤，有版本與 `content_sha256`。
- 別名表是人工維護的封閉表，LLM 不能擴充。表裡沒有的詞，就是不支援。
- 已知不支援的需求要明列，回應時附上原因，例如「樹」（COCO 類別沒有樹，不以 `potted plant` 代替）。

### 6.3 回應

```json
{
  "schema_version": "q-demo.q1-response.v1",
  "status": "READY",
  "reason": null,
  "query_id": "q1-<hash>", "query_sha256": "…",
  "normalized_condition": {"class_label": "car", "min_count_per_frame": 1, "color": null, "query_min_score": "…"},
  "results": [
    {
      "camera_id": "CAM_OUT",
      "rank": 1,
      "matched_segments": [
        {"range_us": [2000000, 9400000], "matched_frames": 37, "evaluated_frames": 38,
         "representative": {"frame_ref": "…", "observation_ids": ["…"], "media_token": "…"}}
      ],
      "coverage": {"evaluated_frames": 300, "not_sampled_frames": 0, "not_inferred_frames": 0, "missing_frames": 0}
    }
  ],
  "no_match_cameras": [{"camera_id": "CAM_CORR", "coverage": {"evaluated_frames": 300, "not_inferred_frames": 0, "missing_frames": 0}}],
  "not_evaluated_cameras": [{"camera_id": "CAM_R1", "reason": "NOT_INFERRED"}],
  "results_total": 1, "returned_count": 1, "next_cursor": null,
  "ranking_basis": ["first_match_us_asc", "camera_id"],
  "supported_classes_ref": "…",
  "resolved_scope": {}, "identity_verdict": "UNCONFIRMED", "agent_used": false, "fallback_reason": null,
  "provenance": {"producer": "q1-camera-search", "gt_read": false}, "output_sha256": "…"
}
```

**`status` 封閉清單：**

| `status` | 條件 |
| --- | --- |
| `READY` | 範圍內所有鏡頭都已推論，至少一個結果 |
| `NO_MATCH` | 範圍內所有鏡頭都已推論（沒有 `NOT_INFERRED`、`NOT_SAMPLED` 只按宣告的取樣策略出現），沒有任何一格相符。訊息寫「在已推論的影格中沒有找到」，不寫「不存在」 |
| `PARTIAL` | 有結果或沒結果，但部分鏡頭或時段沒有推論、缺格，或時間只部分涵蓋（§3.3）。`reason` 寫主要原因 |
| `UNSUPPORTED_CLASS` | 類別不在 `class_map` 與別名表；`results` 為空，附 `supported_classes_ref` |
| `UNSUPPORTED_CONDITION` | 條件組合不支援（例如顏色用在非人物） |
| `OUT_OF_RANGE` | 時間和資料沒有交集（§3.3） |
| `UNKNOWN` | 必要輸入缺失（索引不存在、圖或參數組缺），無法回答 |

- **片段合併**：同一鏡頭中，相符的取樣格依時間合併成 `matched_segments`；間隔超過 `segment_merge_gap_us`（待約定）就斷開。片段只表示「這段時間內取樣到的格有相符」，不表示每一格都相符。
- **代表畫面**：片段內分數最高的相符格；同分取最早。
- **排序**：依第一個相符時間由早到晚，再依 `camera_id`。偵測數不進排序。
- **三種「沒有」分開**：`no_match_cameras`（已推論、條件不符）、`not_evaluated_cameras`（沒推論或沒取樣）、`MISSING` 格（數在 `coverage` 裡）。三者不得合併。
- 每筆結果都要能開代表縮圖與從片段起點播放（`media_token` 沿用 v1.1 §6.2 的媒體權杖規則）。

## 7. Q3：自然語言 → 結構化查詢

### 7.1 請求與輸出

請求：

```json
{
  "schema_version": "q-demo.q3-parse-request.v1",
  "session_ref": "sess-…",
  "text": "穿紅衣服的人在下午 1 點到 1:30 經過哪裡？",
  "locale": "zh-TW",
  "context": {"scene_id": "…", "run_ids": ["…"], "clock_mapping_sha256": "…"},
  "parser_mode": "LLM_WITH_RULE_FALLBACK"
}
```

LLM 的輸出必須是下列 JSON，**先過 schema 驗證，才可能被採用**：

```json
{
  "schema_version": "q-demo.q3-llm-output.v1",
  "intent": "FIND_PERSON",
  "class_term": "人",
  "color_term": "紅",
  "time_literal": {"start": "下午 1 點", "end": "1:30", "date": null},
  "camera_terms": [],
  "region_terms": [],
  "needs_clarification": false,
  "clarification_question": null
}
```

| 欄位 | 規則 |
| --- | --- |
| `intent` | 封閉清單：`FIND_CAMERAS`（Q1）、`FIND_PERSON`（Q2）、`EXPLAIN`、`UNSUPPORTED` |
| `class_term`、`color_term` | 使用者原文的片段。對應到 `class_map`、別名表與 `color_vocabulary` 由程式做；對不上就是不支援，不由 LLM 換詞 |
| `time_literal` | 只放字面上的時間片段；換算成微秒由 §3.2 的決定性解析器做 |
| `camera_terms`、`region_terms` | 只能對到目錄中已有的 `camera_id`、`region_id`；對不上的詞列在回應的 `unresolved_terms` |
| 額外欄位 | 任何沒列在 schema 的欄位都讓驗證失敗 |

### 7.2 驗證與解析步驟

1. 呼叫 LLM，取得原始輸出。
2. 解析 JSON，對 `q3-llm-output.v1` 做 strict 驗證。
3. 程式把詞語對到封閉表，把時間換成來源微秒，組成 Q1 或 Q2 的請求。
4. 組出來的請求再對 §6.1 或 §8.5 的 schema 驗證一次。
5. 回給使用者確認或直接執行（待決 Q-09）；UI 一律顯示組出來的結構化查詢。

驗證失敗時可以重問 LLM，次數上限 `q3_max_llm_attempts`（待約定）；每次呼叫有逾時 `q3_llm_timeout_ms`（待約定）。

### 7.3 失敗與兜底

| 狀況 | 處理 | `agent_used` | `fallback_reason` |
| --- | --- | --- | --- |
| LLM 輸出通過驗證並被採用 | 執行 | `true` | `null` |
| LLM 不可用、逾時或重試後仍驗證失敗 | 改用規則式解析器（關鍵字＋別名表＋時間正則）；UI 標示「規則解析」 | `false` | `LLM_UNAVAILABLE`、`LLM_TIMEOUT`、`LLM_SCHEMA_INVALID` |
| 規則式解析也失敗 | 回 `PARSE_FAILED`，請使用者改寫或用表單；**不猜、不執行** | 依實際情況 | 同上 |
| `needs_clarification: true` 或詞語對不上 | 回 `NEEDS_CLARIFICATION`，附問題與可選項（來自封閉表）；不執行 | `true` | `null` |
| 類別不支援 | 回 `UNSUPPORTED_CLASS`，同 §6.3 | 依實際情況 | — |

規則式解析器的版本與 hash 寫進 `provenance`。

### 7.4 回應

```json
{
  "schema_version": "q-demo.q3-parse-response.v1",
  "status": "PARSED",
  "parsed_by": "LLM",
  "structured_query": {"schema_version": "q-demo.q2-request.v1"},
  "unresolved_terms": [],
  "clarification": null,
  "llm_call": {"model": "qwen2.5:7b-instruct", "model_digest": "…", "prompt_sha256": "…", "prompt_ref": "…", "raw_output_sha256": "…", "attempts": 1, "validation_errors": []},
  "resolved_scope": {}, "identity_verdict": "UNCONFIRMED", "agent_used": true, "fallback_reason": null,
  "provenance": {"producer": "q3-parser", "gt_read": false}, "output_sha256": "…"
}
```

`status` 封閉清單：`PARSED`、`NEEDS_CLARIFICATION`、`UNSUPPORTED_CLASS`、`UNSUPPORTED_CONDITION`、`PARSE_FAILED`、`TIME_EXPRESSION_INVALID`。

### 7.5 LLM 說明文字

- 說明的輸入只有回應中已有的結構化資料（refs、狀態、時間、原因碼）。
- 輸出要附 `cited_refs[]`；每個 ref 都必須出現在輸入中，否則整段說明丟棄，改用模板說明（`fallback_reason: LLM_EXPLANATION_INVALID`）。
- 說明不得引入新事實、不得把 `WEAK` 說成確定、不得說「同一個人」。
- 說明文字不進 `output_sha256`（它可能因模型而變）；它的 `content_sha256` 另外記錄。

### 7.6 prompt 紀錄

每次 LLM 呼叫（Q3、說明、Q5）都記錄：模型名稱、Ollama 回報的 digest、完整 prompt 或 `prompt_ref`＋`prompt_sha256`、取樣參數（temperature、seed 等）、原始輸出與 hash、驗證結果、逾時與延遲。prompt 不得含 §9 禁止的內容與本機路徑。

## 8. Q2／Q4／Q5：找人與切鏡

### 8.1 模式

| `switch_mode` | 誰決定切到哪個候選 | 可用時機 |
| --- | --- | --- |
| `RULE_ONLY` | 決定性規則（§8.6 兜底規則本身） | 現在 |
| `AGENT_SEQUENTIAL` | Agent 依序看合法候選的證據後決定；超限由規則兜底 | DEVELOPMENT_RULES 修訂或列例外之後（§0.3） |

兩種模式的候選集合、順序、狀態機與紀錄格式完全相同，差別只在「誰提出動作」。

### 8.2 同鏡頭最小 IoU 連接器

在同一鏡頭內，把目標從一個取樣格接到下一個取樣格。這不是追蹤模型，不產生身分。

參數（全部「待約定」，寫在參數組 §11）：

| 參數 | 意思 |
| --- | --- |
| `link_iou_min` | 前後兩格 bbox 的 IoU 下限 |
| `link_max_gap_samples` | 最多容許幾個取樣格沒有接上，仍算同一段（超過就進 `TEMP_LOST`） |
| `link_min_score` | 參與連接的偵測分數下限 |
| `link_color_rule` | 起始條件有顏色時，下一格的顏色判定要求（例如不得是 `NONE`） |
| `link_ambiguity_margin` | 兩個候選框的 IoU 差小於此值時算歧義 |

規則：
- 只連 `class_label: person`。下一格中 IoU 達標的框取 IoU 最大者；同值依 `score`，再依 `observation_id`。
- 有歧義時不硬接：該格標 `AMBIGUOUS_LINK`，計入暫失，並把所有候選框記入紀錄。
- `NOT_SAMPLED` 的格跳過、不算缺；`NOT_INFERRED` 與 `MISSING` 的格算沒接上，但原因分開記。
- 每次連接產生一筆 `link` 紀錄：`{prev_observation_id, next_observation_id, iou, decision: LINKED | NO_CANDIDATE | AMBIGUOUS_LINK | FRAME_NOT_INFERRED | FRAME_MISSING}`。

### 8.3 Q4：候選畫面是否含目標

Q4 是對一個候選鏡頭、一段時間窗的判定，**只用偵測索引（RT-DETR＋顏色摘要）**。Qwen 是文字模型，不看影像；它只讀這裡的結構化結果。

`target_presence` 封閉清單：

| 值 | 條件 |
| --- | --- |
| `MATCH_STRONG` | 窗內至少一格有人物框，顏色判定為 `STRONG`，分數達 `query_min_score` |
| `MATCH_WEAK` | 最好的只有 `WEAK` |
| `PERSON_NO_COLOR_MATCH` | 有人物框，但顏色判定全是 `NONE` |
| `PERSON_COLOR_UNKNOWN` | 有人物框，顏色判定都是 `UNKNOWN` |
| `NO_PERSON_DETECTED` | 窗內所有取樣格都已推論，都沒有人物框 |
| `NOT_EVALUATED` | 窗內沒有已推論的格 |
| `PARTIAL_EVIDENCE` | 部分格已推論、部分沒有或 `MISSING`，而且已推論的格沒有相符 |

- 起始條件沒有顏色時，只有 `MATCH_STRONG`（有人物框）、`NO_PERSON_DETECTED`、`NOT_EVALUATED`、`PARTIAL_EVIDENCE` 四種。
- 任何一種都不代表身分；`MATCH_STRONG` 只表示「條件相符的候選觀測」。
- `NO_PERSON_DETECTED` 也不等於「目標不在那裡」。

Q4 的證據摘要（工具回傳，見 §8.4）：

```json
{
  "candidate_ref": "cand:<snapshot_hash16>:2",
  "camera_id": "CAM_B",
  "window_us": [12000000, 18000000],
  "target_presence": "MATCH_STRONG",
  "frames": {"evaluated": 30, "not_sampled": 0, "not_inferred": 0, "missing": 0},
  "best_observations": [
    {"observation_id": "…", "frame_ref": "…", "timestamp_us": 13400000, "score": 0.0, "color_verdict": "STRONG", "bbox_xyxy_px": [0, 0, 0, 0]}
  ],
  "matching_observation_count": 6,
  "first_match_us": 13400000,
  "evidence_sha256": "…"
}
```

`best_observations` 最多 `evidence_max_observations`（待約定）筆，依顏色判定強弱、分數、時間、`observation_id` 排序。

### 8.4 Agent 的 typed tools

Agent 只有下列工具。工具由本機服務執行，參數與 ref 都在服務端驗證，綁定 `session_id` 與 `candidate_snapshot_sha256`。

| 工具 | 請求 | 回應 | 限制 |
| --- | --- | --- | --- |
| `get_search_context` | `{session_id, decision_id}` | 目前狀態、最後連接觀測的摘要（時間、bbox、出口判定）、`candidates[]`（`candidate_ref`、`camera_id`、`rank`、`relation`、`region_path`、`window_us`、`ranking_basis`）、目前游標 `next_candidate_rank`、剩餘輪數與時間 | 只讀；不含影像 |
| `get_candidate_evidence` | `{session_id, decision_id, candidate_ref}` | §8.3 的證據摘要 | 只能取 `rank == next_candidate_rank` 的候選，也就是**依序**；跳號或重複取回 `ILLEGAL_ORDER` |
| `get_observation_summary` | `{session_id, observation_id}` | 該觀測的格、時間、bbox、分數、顏色判定 | 只能取本次 `get_candidate_evidence` 或 `get_search_context` 回傳過的 `observation_id` |
| `submit_decision` | 見下 | `{accepted, rejection_code, executed_action}` | 每輪一次 |

`submit_decision` 的請求：

```json
{
  "schema_version": "q-demo.agent-decision.v1",
  "session_id": "…", "decision_id": "…",
  "candidate_snapshot_sha256": "…",
  "action": "SWITCH",
  "candidate_ref": "cand:<snapshot_hash16>:2",
  "cited_observation_ids": ["…"],
  "rationale": "…"
}
```

`action` 封閉清單：

| `action` | 意思 |
| --- | --- |
| `SWITCH` | 切到 `candidate_ref` |
| `NEXT_CANDIDATE` | 這個候選不切，游標前進到下一個 |
| `RETURN_TO_ORIGIN` | 不再看候選，切回原鏡頭 |

**Controller 拒絕下列選擇**（`accepted: false`，記錄 `rejection_code`，算一輪）：

| `rejection_code` | 狀況 |
| --- | --- |
| `UNKNOWN_REF` | `candidate_ref` 或 `observation_id` 不在快照中 |
| `STALE_SNAPSHOT` | `candidate_snapshot_sha256` 不是目前的快照 |
| `ILLEGAL_ORDER` | `SWITCH` 或 `NEXT_CANDIDATE` 指的候選不是游標所在、已取過證據的那一個 |
| `EVIDENCE_NOT_FETCHED` | 沒先 `get_candidate_evidence` 就要 `SWITCH` 或 `NEXT_CANDIDATE` |
| `INSUFFICIENT_EVIDENCE` | 該候選的 `target_presence` 低於 `switch_min_presence`（待約定，例如只允許 `MATCH_STRONG`，或也允許 `MATCH_WEAK`） |
| `UNCITED_OR_FOREIGN_REF` | `cited_observation_ids` 為空，或含不屬於該候選證據的 ref |
| `SCHEMA_INVALID` | 輸出不是合法的 `agent-decision.v1` |

游標規則：取完某個候選的證據後，游標停在該候選，直到 `submit_decision` 被接受；`NEXT_CANDIDATE` 被接受後游標加一。`RETURN_TO_ORIGIN` 不需要先取證據。

Agent 可以對合法、有證據的候選選 `NEXT_CANDIDATE`（不切）；這不算違規，但要記錄理由。Agent 不能新增、刪除或重排候選，也不能改時間窗。

### 8.5 Q2 請求與起點

```json
{
  "schema_version": "q-demo.q2-request.v1",
  "session_ref": "sess-…",
  "scene_id": "…", "run_ids": ["…"],
  "time": {"kind": "WALL", "wall_range": ["2026-11-01T13:00:00+08:00", "2026-11-01T13:30:00+08:00"]},
  "seed": {"kind": "APPEARANCE", "class_label": "person", "color": {"label": "red", "min_verdict": "STRONG"}},
  "switch_mode": "RULE_ONLY",
  "parameter_set_id": "…"
}
```

- `seed.kind`：
  - `OBSERVATION`：使用者在畫面上點的人物框，附 `observation_id`。
  - `APPEARANCE`：依外觀與時間找起點。服務回傳符合條件、時間最早的候選起點清單（依時間、`camera_id`、`observation_id` 排序）；**多個候選時由使用者選**，不自動挑，也不靠 Blender actor ID 解歧義。
- 找不到合適起點時回 `NO_SEED`，附 Q1 式的涵蓋報告；不得換到請求時間窗外找。
- 第一版只有一種外觀條件（一種顏色）；同色干擾不做。

### 8.6 狀態機

狀態封閉清單：

| 狀態 | 意思 | 主畫面 |
| --- | --- | --- |
| `PLAYING` | 在目前鏡頭，連接器持續接上 | 目前鏡頭；標出接上的框 |
| `TEMP_LOST` | 連接器沒接上，未超過 `lost_grace_us`（待約定） | 目前鏡頭；標「暫失」，可顯示最後觀測縮圖並標時間 |
| `SEARCHING` | 已產生候選，正在依序取證據與決定 | 原鏡頭；標「搜尋中」與目前看的候選 |
| `SWITCHING` | 決定已被接受，正在切換（瞬時狀態，只記紀錄） | — |
| `RETURNED_TO_ORIGIN` | 候選都不切或搜尋結束，切回原鏡頭 | 原鏡頭在**目前的來源時間**，不倒轉 |
| `ENDED` | 時間範圍結束、run 結束或使用者停止 | — |

轉移：

| 從 | 條件 | 到 | 紀錄 |
| --- | --- | --- | --- |
| （開始） | 起點已選 | `PLAYING` | `seed` |
| `PLAYING` | 連接器沒接上 | `TEMP_LOST` | `link` 紀錄 |
| `TEMP_LOST` | 在 `lost_grace_us` 內重新接上 | `PLAYING` | `link` 紀錄 |
| `TEMP_LOST` | 超過 `lost_grace_us` | `SEARCHING` | 出口判定、候選快照 |
| `SEARCHING` | 決定 `SWITCH` 被接受 | `SWITCHING` → `PLAYING`（新鏡頭；起始觀測為引用的觀測） | 決策紀錄 |
| `SEARCHING` | 候選全部 `NEXT_CANDIDATE`、決定 `RETURN_TO_ORIGIN`，或兜底規則找不到可切的候選 | `RETURNED_TO_ORIGIN` | 決策紀錄 |
| `RETURNED_TO_ORIGIN` | 原鏡頭重新接上 | `PLAYING` | `link` 紀錄 |
| `RETURNED_TO_ORIGIN` | 經過 `research_interval_us`（待約定）仍未接上 | `SEARCHING`（新快照，時間窗往後移） | 新快照 |
| 任何狀態 | 達到 `session_max_research_rounds`（待約定）、時間範圍結束或使用者停止 | `ENDED` | 結束原因 |

- 來源時間只往前走；切鏡與回原鏡頭都在同一條來源時間軸上。
- 切鏡由觀測驅動（決定被接受時引用的觀測），不依預先排好的動畫時間表。
- 每個候選的時間窗 `window_us` 從暫失開始時間算起，長度 `search_window_us`（待約定）；若圖有 `nominal_path_length_m`，可另依公開速度設定縮窗（是否採用待決 Q-05）。不讀人物腳本速度。

**輪數與時間上限（`AGENT_SEQUENTIAL`）：**

| 參數 | 意思 |
| --- | --- |
| `agent_max_turns` | 一次 `SEARCHING` 中 Agent 最多可提出幾次 `submit_decision`（被拒的也算） |
| `agent_max_wall_ms` | 一次 `SEARCHING` 的牆鐘時間上限 |
| `agent_call_timeout_ms` | 單次 LLM 呼叫逾時 |
| `agent_max_invalid_outputs` | 連續幾次 `SCHEMA_INVALID` 或被拒後直接兜底 |

全部「待約定」。

**兜底規則（`RULE_ONLY` 的規則，也是 `AGENT_SEQUENTIAL` 超限後的規則）：**
1. 從游標所在的候選起，依 §5.4 的順序逐一取 §8.3 的證據。
2. 第一個 `target_presence` 達到 `switch_min_presence` 的候選：`SWITCH`，引用 `best_observations` 的第一筆。
3. 都沒有：`RETURN_TO_ORIGIN`。

兜底接手時，Agent 已被接受的 `NEXT_CANDIDATE` 保留（游標不倒回），已取的證據重用。

**`fallback_reason` 封閉清單：**`AGENT_MAX_TURNS`、`AGENT_TIMEOUT`、`AGENT_INVALID_OUTPUT`、`LLM_UNAVAILABLE`、`LLM_TIMEOUT`、`LLM_SCHEMA_INVALID`、`LLM_EXPLANATION_INVALID`、`MODE_NOT_AUTHORIZED`（要求 `AGENT_SEQUENTIAL` 但 §0.3 的條件未滿足時，整個 session 用 `RULE_ONLY` 並標此原因）。

**`decided_by`（每一步）：**`AGENT`、`RULE_FALLBACK`（Agent 模式下由規則接手）、`RULE_ONLY`、`USER`（使用者手動選起點或手動改切）。回應層的 `agent_used` 是「有沒有任何一步 `decided_by: AGENT`」。

### 8.7 Q2 回應與逐步紀錄

```json
{
  "schema_version": "q-demo.q2-response.v1",
  "status": "COMPLETE",
  "reason": null,
  "session_id": "…",
  "timeline": [
    {"segment_id": "seg-0", "kind": "ON_CAMERA", "camera_id": "CAM_A", "range_us": [0, 8200000],
     "entered_by": "SEED", "decided_by": "USER", "observation_ids": ["…"], "presence_at_entry": "MATCH_STRONG"},
    {"segment_id": "seg-1", "kind": "GAP", "range_us": [8200000, 13400000],
     "gap_states": ["TEMP_LOST", "SEARCHING"], "camera_shown": "CAM_A", "position": null},
    {"segment_id": "seg-2", "kind": "ON_CAMERA", "camera_id": "CAM_B", "range_us": [13400000, 21000000],
     "entered_by": "SWITCH", "decided_by": "RULE_ONLY", "decision_id": "…", "observation_ids": ["…"], "presence_at_entry": "MATCH_STRONG"}
  ],
  "decisions_ref": "…", "decisions_sha256": "…",
  "resolved_scope": {}, "identity_verdict": "UNCONFIRMED", "agent_used": false, "fallback_reason": null,
  "provenance": {"producer": "q2-controller", "gt_read": false}, "output_sha256": "…"
}
```

- `timeline` 依來源時間排序、不重疊、涵蓋整個查詢時段（扣掉 §3.3 沒涵蓋的部分）。
- `GAP` 段的 `position` 一律 `null`：不畫盲區中的位置。
- `status` 封閉清單：`COMPLETE`（時段走完）、`PARTIAL`（時間只部分涵蓋、索引有缺，或圖未核准）、`NO_SEED`、`ENDED_BY_LIMIT`（達到 `session_max_research_rounds`）、`UNKNOWN`。
- 串起來的片段是「條件相符的候選串接」，UI 與說明都不得寫成「同一個人」。

**逐步紀錄**（`decisions` 檔，每個決策一筆，append-only）：

```json
{
  "schema_version": "q-demo.decision-record.v1",
  "decision_id": "…", "session_id": "…", "step_index": 3,
  "state_before": "SEARCHING", "state_after": "PLAYING",
  "source_time_us": 13400000,
  "switch_mode": "AGENT_SEQUENTIAL",
  "candidate_snapshot_sha256": "…",
  "exit_resolution": "UNIQUE",
  "candidates_considered": [{"candidate_ref": "…", "rank": 1, "evidence_sha256": "…", "target_presence": "PERSON_NO_COLOR_MATCH", "action": "NEXT_CANDIDATE", "decided_by": "AGENT"}],
  "tool_calls": [{"tool": "get_candidate_evidence", "request_sha256": "…", "response_sha256": "…"}],
  "llm_calls": [{"model": "…", "model_digest": "…", "prompt_sha256": "…", "prompt_ref": "…", "raw_output_sha256": "…", "validation": "PASS"}],
  "submitted": {"action": "SWITCH", "candidate_ref": "…"},
  "accepted": true, "rejection_code": null,
  "executed_action": "SWITCH", "executed_candidate_ref": "…",
  "decided_by": "AGENT", "fallback_reason": null,
  "turns_used": 2,
  "content_sha256": "…",
  "stats": {"latency_ms": {"agent": 0, "evidence": 0}}
}
```

- 被拒的提交也要有紀錄（`accepted: false`）。
- 用同一參數組、同一快照、`RULE_ONLY` 重跑，`timeline` 與 `decisions` 的 `content_sha256` 必須相同。`AGENT_SEQUENTIAL` 的重播以紀錄中的原始輸出重放，不重新呼叫 LLM。

## 9. GT 隔離與來源

沿用 v1.1 §7 的邊界表、路徑防護與錯誤碼。本文新增：

| 資料 | 偵測索引產生 | 兩層圖產生 | Q1–Q5 查詢、Agent、LLM prompt |
| --- | --- | --- | --- |
| safe RGB（hash 驗證） | 可讀 | **禁止**（不含人物的靜態畫面除外） | 只經媒體權杖顯示給使用者；不送進 LLM |
| 偵測索引 | — | **禁止** | 可讀（經工具） |
| 核准的 `scene_static`、校正、靜態可見範圍 | 不需要 | 可讀 | 可讀（經圖） |
| r004 的人物設定（紅衣、藍衣、路線、速度）、事件腳本、`persons.sim.json`、`event_*.validation.json` | **禁止** | **禁止** | **禁止**；prompt 也不得寫「紅衣人會走到教室」這類內容 |
| GT 軌跡、mask、visibility、depth | **禁止** | **禁止** | **禁止** |

- 查詢中的「紅色」來自使用者輸入，不來自人物設定。
- 第一版展示時，事件的 `query.json` 可以預填 UI（v1.1 §7），預填結果和手動輸入必須相同（§6.1 `origin`）。
- 驗收時若要用產製路線核對（類似 v1.1 §7 D54 A2），只能在驗收端，結果不回填任何推論輸出；是否需要另行決定（待決 Q-12）。

## 10. 儲存

本文不指定 PostgreSQL 或本機檔案。要求：
- 圖與參數組是版本化 JSON 檔。
- 偵測索引與查詢狀態透過單一 store 介面讀取；介面輸出必須是本文的 schema，與底層儲存無關。
- 媒體、`.blend`、權重不放進資料庫。
- 舊 PG 中的 local-camera-test 資料不是 r004 的模型結果，不得當成本文的索引（Codex 討論稿 §8）。

## 11. 參數表（全部待約定：Codex 提案、使用者核定）

參數組 `parameter_set.json` 有 `parameter_set_id` 與 `content_sha256`，每個回應都引用。本文不給預設值。

| 參數 | 單位 | 用在 |
| --- | --- | --- |
| `index_score_floor` | 分數 | §4.2 索引寫入 |
| `nms.iou` | IoU | §4.2 |
| `stride_samples` | 取樣格數 | §4.2 取樣 |
| 上半身裁切比例 | bbox 高度比例 | §4.3 |
| `color_crop_min_pixels` | 像素數 | §4.3 `CROP_TOO_SMALL` |
| `color_truncation_max_ratio` | 比例 | §4.3 `CROP_TRUNCATED` |
| HSV 各顏色的色相範圍與 S、V 下限 | HSV 值 | §4.3 |
| `STRONG`／`WEAK` 分界 | 比例 | §4.3 |
| `query_min_score` | 分數 | §6.1、§8.3 |
| `segment_merge_gap_us` | 微秒 | §6.3 |
| `link_iou_min`、`link_max_gap_samples`、`link_min_score`、`link_color_rule`、`link_ambiguity_margin` | 各自 | §8.2 |
| 出口判定規則與門檻 | — | §5.4 |
| `top_k` | 個 | §5.4 |
| `lost_grace_us` | 微秒 | §8.6 |
| `search_window_us` | 微秒 | §8.6 |
| `research_interval_us`、`session_max_research_rounds` | 微秒、次 | §8.6 |
| `switch_min_presence` | `MATCH_STRONG` 或 `MATCH_WEAK` | §8.4、§8.6 |
| `evidence_max_observations` | 筆 | §8.3 |
| `agent_max_turns`、`agent_max_wall_ms`、`agent_call_timeout_ms`、`agent_max_invalid_outputs` | 次、毫秒 | §8.6 |
| `q3_max_llm_attempts`、`q3_llm_timeout_ms` | 次、毫秒 | §7.2 |
| LLM 取樣參數（temperature、seed） | — | §7.6 |

效能（查詢與切鏡延遲）只量測與記錄，第一版不訂門檻（Codex 討論稿 §11）。

## 12. 與 Codex 討論稿的對照

| 討論稿位置 | 討論稿內容 | 本文處理 |
| --- | --- | --- |
| §2、§5 | 直接修改 r003，不另存 r004 | 依 D63 (b) 改為**另存 r004**；本文以 `scene_revision` 引用 |
| §3.1 | 建議做 RGB 衣服顏色統計 | 依 D63 (d) 改為**上半身 HSV**，四級判定 |
| §3.2、§6 Q2 步驟 4 | Qwen 建議下一個候選，Controller 驗證 | 依 D63 修訂：候選與順序固定，Agent 只能依序取證並決定切或不切（§8.4）；受 §0.3 規則限制 |
| §4.1、§4.2 | 兩層圖 | §5，加上可用輸入、版本與 hash、`traversability` |
| §6 Q1 | 未取樣／未推論標明範圍 | §4.3 `frame_state` 與 §6.3 的三種「沒有」 |
| §6 Q2 步驟 6 | 回原鏡頭不倒轉時間 | §8.6 `RETURNED_TO_ORIGIN` |
| §6 末段 | 13:00–13:30 需要日期、時區與映射 | §3 |
| §7 | 最小資料契約 | §4–§8 的 schema |
| §11 | 不訂效能門檻 | §11 末段 |
| 修訂中 | r004 修改表、提案門檻 | 等修訂稿；門檻填入 §11，修改表影響 §5 的圖 |

## 13. 待決問題（請 Codex 確認）

| # | 問題 | 本文的暫定處理 |
| --- | --- | --- |
| Q-01 | DEVELOPMENT_RULES 第 57、62 行與 D63 修訂的 Agent 切鏡衝突：由誰、何時修訂或列例外？ | 修訂前只啟用 `RULE_ONLY`（§0.3、§8.1） |
| Q-02 | D63 修訂原文尚未貼出；本文 §0.2 的摘要是否與原文一致？ | 以交接摘要為準，原文貼出後改版 |
| Q-03 | §5.4 的轉移排序鍵（出口命中層級 → 關係層級 → 區域跳數 → 入口可見面積 → `camera_id`）是否接受？是否要和 v1.1 §6.1 的 `relation` 名稱統一？ | 暫用本文的鍵 |
| Q-04 | Region Graph 中 `state: UNKNOWN` 的邊：保留在候選內但排到後面，還是排除？ | 保留，`relation_tier` 3 |
| Q-05 | 候選時間窗：只用固定 `search_window_us`，還是依 `nominal_path_length_m` 與公開速度設定調整？ | 固定窗；調整列為可選 |
| Q-06 | 出口判定：bbox 底邊中點在 ROI 內，還是 bbox 與 ROI 的重疊比例？ROI 用人工標記還是校正投影？ | 規則與門檻待約定；兩種 `mapping_basis` 都允許 |
| Q-07 | 偵測索引是否一律離線產生？查詢時遇到 `NOT_INFERRED` 是否允許即時補推論？ | 一律離線；查詢不補推論 |
| Q-08 | Q4 是否只靠 RT-DETR＋HSV？D63 修訂的「模型以自己的辨識判斷」是否預期第一版就要看圖模型（VLM）？ | 只靠 RT-DETR＋HSV；VLM 不在第一版 |
| Q-09 | Q3 解析後要先讓使用者確認，還是直接執行並顯示結構化查詢？ | 直接執行並顯示；使用者可修改後重查 |
| Q-10 | `switch_min_presence` 是否允許 `MATCH_WEAK` 觸發切鏡？ | 待約定 |
| Q-11 | 第一版 r004 是否所有鏡頭在同一個 run 與同一個 clock？若有多個 run，牆鐘對應如何分配？ | 假定同一事件的鏡頭共用一個 run／clock |
| Q-12 | 驗收時是否需要讀產製路線做核對（類似 D54 A2）？ | 不在本契約範圍；需另行決定 |
| Q-13 | store 介面由 PG 或本機檔案實作？舊 Agent 的 PG 耦合如何解除？ | 本文只定輸出 schema（§10） |
| Q-14 | RT-DETR 的實際型號、權重來源與授權？`class_map` 是 COCO 80 類嗎？ | `UNKNOWN`；權重下載未授權 |
| Q-15 | 兩層圖由誰標記、誰檢查、何時核准？r004 鏡頭固定後是否需要再跑 K7 類型的驗證？ | 建議 Codex 產生、Claude 獨立檢查、使用者核准 |
| Q-16 | `AMBIGUOUS_LINK` 是否直接算暫失，還是讓使用者在畫面上選框？ | 算暫失；使用者可手動改選（`decided_by: USER`） |
| Q-17 | 參數組（§11）是否和 #76 的門檻提案用同一套流程與檔案格式？ | 建議同一套 |
