# D126 核心交付與報告摘要收據（2026-11-04）

- 日期：2026-11-04（Asia/Taipei）
- 依據決策：[D126（#93 comment 6621356045）](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6621356045)、[D125（#93 comment 6620998251）](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620998251)、[D124（#93 comment 6620431061）](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620431061)、[#279 協調留言](https://github.com/Polalalabear/amidst/issues/279#issuecomment-6620849868)
- 參考文件包：`docs/project/{README,PRD,SPEC,SYSTEM_ARCH,ROADMAP,DECISIONS,GLOSSARY,BUILD_FROM_SCRATCH}.md`
- 核心功能契約：PR [#410](https://github.com/Polalalabear/amidst/pull/410) [`docs/contracts/Q_CORE_SEARCH_TRACK_V1.md`](../contracts/Q_CORE_SEARCH_TRACK_V1.md)（PROPOSED，對應機器可讀 schema [`docs/contracts/schemas/q-core.search-track.v1.schema.json`](../contracts/schemas/q-core.search-track.v1.schema.json)）
- 整合基準：`mainline/q1q5` = `796cc17`；當前開發分支：`codex/d126-core-search-track`

---

## 1. 專案定位與核心收斂原則

依據 2026-11-04 決策 D126，Amidst 系統全面收斂聚焦於「**查找**（Search）」與「**追蹤**（Track）」兩大核心能力：

1. **核心定位**：多攝影機證據工作台，系統定位為**輔助工具**，強調「輔助、不追求精確、讓使用者快速知道目標大概在哪」。每個答案均保留完整來源追溯鏈（source / run / clock / hash provenance），做到寧可回答 `UNKNOWN` 也絕不假裝找到。
2. **非目標邊界**：本系統為工程 Demo，非身分識別、物理安全或正式研究驗收工具。身分判定一律標示為 `identity_verdict: UNCONFIRMED`；實體導航與通行狀態一律標示為 `physical_navigation: UNKNOWN`。
3. **選單優先**：工作台輸入介面以選單選取為主，降低人工輸入歧異與解析錯誤（D125-3、D126）。

---

## 2. 兩個核心功能與契約對應（#410 `Q_CORE_SEARCH_TRACK_V1.md`）

### 2.1 case1 查找（`q_core_search`）

使用者輸入時間範圍加上地點或物件特徵，系統回傳時間範圍內拍到目標或涵蓋指定區域的鏡頭畫面。

| 項目 | 規範說明 | 契約對應章節與錯誤代碼 |
| --- | --- | --- |
| **API 路由** | POST `q_core_search`（註冊於 `src/amidst/q1q5/api.py` 的 `POST_ROUTES`） | 契約 §1 |
| **請求綱要** | `q-core.search-request.v1`：包含 `time`、`region_ids`、`feature`、`scene_id`、`run_id`、`session_ref` | 契約 §2.1 |
| **時間欄位** | **必填**。`kind: "WALL"`，`timezone: "Asia/Taipei"`，`wall_range: [start_iso, end_iso]`。不跨午夜，透過宣告時鐘（`clock_mapping`）精確換算為微秒整數 `source_range_us` | 必填缺漏：`TIME_REQUIRED`<br/>格式錯誤：`TIME_INVALID`<br/>順序錯誤：`TIME_ORDER`<br/>跨午夜：`TIME_CROSSES_MIDNIGHT`<br/>時區不合：`TIME_ZONE_MISMATCH` |
| **地點欄位** | 選填。選單陣列 `region_ids`，節點 ID 取自 region graph（`regions[].region_id`）。空陣列 `[]` 代表不限地點 | 未知節點：`REGION_UNKNOWN` |
| **特徵欄位** | 選填。`feature: {class_label, color_label}`。支援完整 **COCO 80 類別**；顏色詞彙（HSV）**僅限** `person` 類別可用 | 未支援類別：`UNSUPPORTED_CLASS`<br/>未知顏色：`COLOR_UNKNOWN`<br/>非人物帶顏色：`UNSUPPORTED_CONDITION` |
| **輸入組合檢驗** | 地點 `region_ids` 為空且 `feature` 為 null 時前端與後端均攔截 | 422 `LOCATION_OR_FEATURE_REQUIRED` |
| **門檻控制** | 客戶端**不得**傳送 score 門檻；伺服器固定依 run 參數集或索引 manifest 之 `index_score_floor` 帶入 `query_min_score` | 契約 §2.1 |
| **命中機制** | - **地點命中**：查 camera graph 的 `covered_regions` 且標示 `basis == "MANUAL_ON_STATIC_FRAME"`。地點命中屬場景設定，`target_observed: false`<br/>- **物件命中**：讀取 RT-DETR COCO 離線偵測索引，命中者帶時間片段與代表影格，`evidence_state: "OBSERVED"`，`target_observed: true`<br/>- **雙重條件**：鏡頭取交集，命中依據 `basis` 包含 `LOCATION` 與 `OBJECT` | 契約 §2.2 |
| **回應綱要** | `q-core.search-response.v1`：含 `status`（`READY`、`NO_MATCH`、`PARTIAL`、`OUT_OF_RANGE`、`UNKNOWN`）、`hits`、`not_evaluated_cameras`、`identity_verdict: "UNCONFIRMED"`、`provenance`、`output_sha256` | 契約 §2.4 |

### 2.2 case2 追蹤（`q_core_track`）

使用者選定目標特徵，系統在單畫面自動隨目標移動切換鏡頭；多畫面同時展示所有看到目標的鏡頭；目標進入盲區時顯示俯視圖與物理預測輔助曲線。

| 項目 | 規範說明 | 契約對應章節與錯誤代碼 |
| --- | --- | --- |
| **API 路由** | POST `q_core_track`（註冊於 `src/amidst/q1q5/api.py` 的 `POST_ROUTES`） | 契約 §1 |
| **請求綱要** | `q-core.track-request.v1`：包含 `feature`、`region_ids`、`time`、`playback_now_us`、`scene_id`、`run_id`、`session_ref` | 契約 §3.1 |
| **特徵欄位** | **必填**。追蹤功能建立於 Q2 同鏡頭 IoU 連接器（`linker.py`），目前**僅支援 `person`**。若查詢其他 COCO 80 類別，回傳 200 `status: "UNSUPPORTED"`、`reasons: ["CLASS_NOT_SUPPORTED_BY_LINKER"]`，空陣列回傳，不偽造追蹤 | 特徵缺漏：422 `FEATURE_REQUIRED`<br/>非 person 類別：200 `UNSUPPORTED`<br/>非 COCO 類別：422 `UNSUPPORTED_CLASS` |
| **時間與回放視窗** | `time: null` 表示回放當前時刻，此時**必填** `playback_now_us`（來源時間微秒整數），回溯視窗為 `[max(0, now - track_lookback_us), now)`（預設 60 s）；非 null 時支援指定歷史區間 | `time` 為 null 且缺回放微秒：422 `NOW_REQUIRED` |
| **因果不溯既往** | 嚴格防護：回應僅能使用 `source_time_us < as_of_us` 之觀測證據，嚴禁讀取或推論未來影格 | 契約 §3.1 |
| **多畫面輸出** | `sightings`：同鏡頭 IoU 連接器產生的各鏡頭連續觀測區間，`evidence_state: "OBSERVED"`；`multi_view` 列出視窗內所有看到目標的鏡頭清單 | 契約 §3.4 |
| **單畫面切鏡** | 由純函式 `single_view_sequence`（後端）/ `singleViewSequence`（前端）依觀測區間推算：起點取最早；鏡頭可見時不換鏡；片段結束時重疊候選立即無縫切鏡；無鏡頭看見但後續仍有時補 `GAP`；完全跟丟時補 `LOST`。`GAP` 與 `LOST` 之 `camera_id: null`、`evidence_state: "UNKNOWN"` | 契約 §3.5 |
| **完全跟丟定義** | `as_of_us` 之前最後一段 sighting 結束後，至 `as_of_us` 均無任何鏡頭看見目標，即標記為 `LOST`。不另設上限輪數或逾時參數 | 契約 §3.4、§3.5 |
| **盲區與物理預測** | 僅在 `single_view` 最後一段為 `GAP` 或 `LOST` 時計算 `blind`；當前物理預測路由 `q_physical_prediction` 回 503 時，系統維持 fail-closed，回傳 `blind: {"status": "UNAVAILABLE", "reason": "PREDICTION_UNAVAILABLE", "estimate": null}`，不捏造曲線 | 契約 §3.6、§4.2 |
| **接線後盲區形狀** | `q-core.blind-estimate.v1`：由純函式 `core_query.blind_estimate` 包裝。<br/>- 證據狀態：固定標記 `evidence_state: "INFERRED"`<br/>- 信心等級：不論底層分數高低，**一律降為 `confidence: "LOW"`**（低信心標示；樣本不足為 `UNKNOWN`），底層分數保留於 `model_confidence`<br/>- 顯示標籤：`display_label: "物理預測（示意，非實際路徑）"`，UI 採用虛線、低對比色呈現，禁止與觀測實線混淆<br/>- 座標來源：僅能取自靜態平面圖標註顯示座標（`STATIC_PLAN_DISPLAY`），無座標時標記 `NODE_GRAPH_ONLY`，絕不使用 GT 軌跡或深度圖 | 契約 §4.3、§4.4 |
| **回應綱要** | `q-core.track-response.v1`：含 `status`（`TRACKING`、`LOST`、`NO_SIGHTING`、`UNSUPPORTED`、`PARTIAL`、`UNKNOWN`）、`sightings`、`multi_view`、`single_view`、`blind`、`identity_verdict: "UNCONFIRMED"`、`physical_navigation: "UNKNOWN"`、`output_sha256` | 契約 §3.4 |

---

## 3. 支援範圍與核心防線矩陣

### 3.1 支援範圍盤點

| 領域 | 支援項目與範圍 | 邊界與限制 |
| --- | --- | --- |
| **查找類別** | **COCO 80 類別**（`coco80-v1` / `configs/q1q5/class_alias_v1.json`） | 支援別名對照（如 cellphone → cell phone）；不支援自然語言自由文字（Q3 語意解析不在 D126 核心範圍） |
| **特徵顏色** | HSV 顏色詞彙表標籤 | **僅限** `person` 類別可帶顏色篩選；其他物件帶顏色會被拒絕（422 `UNSUPPORTED_CONDITION`） |
| **追蹤類別** | **僅限 `person`** | 非人物類別由 API 攔截並回傳 200 `UNSUPPORTED`，前端提示「追蹤僅支援人物」，不呼叫假連接 |
| **地點區域** | region graph 拓撲節點（如 r004 之 OUT_W、CORR_W、R101 等） | 僅支援靜態圖標定之區域；地點命中僅代表鏡頭視角涵蓋，不保證目標在場 |
| **播放倍速** | **1×、1.5×、2×**（D125-3、D126-4） | 畫面解碼跟不上時自動降速並提示實際倍速（如「設定 2× · 實際 1.4×」）；演示時間與宣告時鐘始終錨定來源時間，不跳格漂移 |
| **盲區輔助** | 俯視圖虛線預測與候選出口 | 標示為推論（低信心），僅供人工參考；底層服務不可用時 fail-closed，不畫假線 |

### 3.2 GT 隔離與推論邊界守門

系統實作嚴格依循 [`docs/DEVELOPMENT_RULES.md`](../DEVELOPMENT_RULES.md) 與 D124-1，建立多層防禦：

1. **資料層隔離**：
   - 渲染產生之輸出分為 `safe/`（RGB 影格與公開 metadata）與 `gt_private/`（Ground Truth、相機深度、真實軌跡）。
   - 後端 API 與前端僅能讀取 `safe/` 目錄；`gt_private/` 僅限離線評分端存取，生產環境服務對 `gt_private/` 請求一律回傳 404。
2. **推論輸入攔截**：
   - 所有推論與 API 請求經 `_safe_request` 檢核，凡含有 Ground Truth、渲染軌跡、可見性標籤（visibility）、深度資訊（depth）、情境卡計畫時刻者，一律回傳 422 `FORBIDDEN_INFERENCE_INPUT`。
3. **拓撲通道純粹性**：
   - 兩層圖通道連線標示 `traversability: TOPOLOGICAL_ONLY`、`state: UNKNOWN`，嚴禁用於物理碰撞或實體通行推論。
4. **架構守門驗證（Guard）**：
   - 執行 `python scripts/check_architecture_guard.py --repo . --base origin/mainline/q1q5`。
   - 確保權限鎖定（authority pins）、推論字串禁止詞（`ground_truth`、`visibility`、`depth`、`trajector*`、`renderer_track` 等）、以及 Schema Registry 註冊狀態均為 **0 findings / PASS**。

---

## 4. 擱置項目清單（D126-1 與 #279 ROADMAP）

依據 D126-1 決策，為集中資源達成核心交付，以下項目全面**擱置**（維持既有狀態，未來需使用者另行決策始得重啟）：

| # | 擱置項目 | 原規劃內容與目的 | 原決策出處 | 現行處理方式 |
| --- | --- | --- | --- | --- |
| **S1** | **M1–M4 模型實驗** | 研究企劃第二部分：RULE_ONLY 與 AGENT_SEQUENTIAL（LLM Agent 如 Qwen）在不同事件下之切鏡成效消融對比實驗 | [#397](https://github.com/Polalalabear/amidst/pull/397)、[D121](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6594412627) | **全面擱置**。不進行多模型對比測試與 API 耗能實驗；追蹤統一維持決定性規則連接 |
| **S2** | **Q4 正式標註包** | 組員負責之 Q4 正式 T/F 標註包（包含 dataset builder、README、`RETURN/` 樣本標註與一致性審查） | [#342](https://github.com/Polalalabear/amidst/issues/342)、[D125 補](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6621022288) | **全面擱置**。不推進組員外包資料標註流程 |
| **S3** | **Colab 外包測試包** | T3 外包測試包：將全流程打包為 Google Colab / Jupyter Notebook 一鍵式執行環境 | [D125-3](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620998251)、#279 T3 | **全面擱置**。不維護外部雲端筆記本執行環境 |
| **S4** | **大整理後半段（T4 後半）** | D116 / D125 決策之後半段：解除對外部本機 checkout 依賴、將所有成果併入 `main`、大量刪除歷史分支與清理關閉舊 PR | [D116](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6579537960)、[D125](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6620998251)、#279 T4 後半 | **大整理後半擱置**；分支與歷史 PR 保留證據價值，不執行批量刪除與合併 `main`。<br/>**僅保留 T4 前半**：乾淨 clone 驗證腳本（`verify_clean_clone`，D116-補、D126-1 保留項） |

---

## 5. 待補數據與未決事項清單（Data & Metrics Pending List）

彙整專案規格（PRD §6、SPEC §8、ROADMAP §1）中明確註記為「**待補**」或「**UNKNOWN**」的事項，作為後續產出之追蹤基準：

| # | 待補 / 未決項目 | 相關文件章節 | 現況說明與阻塞原因 | 後續行動與交付責任 |
| --- | --- | --- | --- | --- |
| **P1** | **量化效能指標門檻** | PRD §6 S8 | 系統回應時間（latency）、查找查全率／查準率、追蹤跟丟率、切鏡延遲等數值門檻目前無定量規格，標記為**待補** | 待使用者或產品規格定義基準 SLA |
| **P2** | **擴充 Office 場景參數** | PRD §7、ROADMAP C3 | 多間教室擴充（如 R101～R104）之確切教室數量、鏡頭佈設清單、COCO 物件配置表、渲染格數與 fps、磁碟容量估算皆為**待補** | 由 Codex 負責擴充渲染；執行前需受 D118 磁碟門檻（可用空間 ≥ 8 GiB）檢驗 |
| **P3** | **多教室靜態顯示座標** | 契約 §8 O4 | 盲區俯視圖所需之多教室 2D 平面顯示座標點（`STATIC_PLAN_DISPLAY`，非真實渲染軌跡）目前**待補** | Codex 產出場景時一併提供靜態平面標記檔 |
| **P4** | **A4-1 / B4-1 重渲染與真實追蹤輸出** | ROADMAP T2、SPEC §6 | 複雜事件 A4-1（50 s）與 B4-1（42 s）之人物轉身重渲染參數集**待使用者核定**；#118 偵測索引與 CX-8 追蹤輸出目前為**待補**（前端顯示「追蹤結果尚未產生 · UNKNOWN」） | 使用者核定參數集後，Codex 執行一次性重渲染與 RULE_ONLY 追蹤輸出 |
| **P5** | **追蹤回溯視窗常數（`track_lookback_us`）** | 契約 §8 O2 | PROPOSED 預設為 60 秒（60,000,000 µs），正式數值**待使用者核定**；核准前 API 回應標註 `PARAMETERS_NOT_APPROVED` | 待納入正式參數集送審 |
| **P6** | **目標使用者角色與場域規格** | PRD §2 | 監控室值班人員職責、操作硬體螢幕規格與作業環境標記為**待補** | 專案後續視實際展示環境補充 |
| **P7** | **物理預測服務實體接線** | SPEC §2.4、SYSTEM_ARCH §2 #6 | 後端 `q_physical_prediction` 路由目前回傳 503 `Q_RESOURCE_UNAVAILABLE`，尚未接通 | 待 Codex 與 Claude 依契約 §4 完成純函式與路由串接 |

---

## 6. 實作清單與驗證記錄（Unified Delivery Verification）

### 6.1 本次整合分支交付檔案清單（`codex/d126-core-search-track`）
- **D126 查找與追蹤核心後端与 API（C1/C4）**：
  - `src/amidst/q1q5/core_query.py`（`validate_search_request`、`validate_track_request`、`location_hits`、`intersect_hits`、`single_view_sequence`、`blind_estimate`、`execute_core_search`、`execute_core_track`）
  - `src/amidst/q1q5/api.py`（註冊並實作 `q_core_search`、`q_core_track`、`q_candidate_view`、`q_external_prediction`、錄影標題驗證與 `regions` 暴露）
  - `src/amidst/q1q5/demo_launcher.py`（`RecordedAPI.READ_ONLY` 納入 `q_candidate_view`）
- **D126 查找與追蹤核心前端與選單（C2）**：
  - `frontend/workbench-v2/core-search-track-model.mjs`（`regionOptions`、`featureOptions`、`buildCoreSearchRequest`、`buildCoreTrackRequest`、`trackClassSupport`、`singleViewSequence`、`multiViewCameras`、`ERROR_TEXT`）
  - `frontend/workbench-v2/search-dialog-model.mjs`、`frontend/workbench-v2/search-dialog-view.mjs`、`frontend/workbench-v2/search-dialog.test.mjs`（新增 `地點（區域）` `data-search-region` 選單與追蹤模式「空著代表現在」）
- **DEMO-UI 後端純函式補齊**：
  - `src/amidst/q1q5/camera_map.py`、`src/amidst/q1q5/candidate_view.py`、`src/amidst/q1q5/openai_prediction.py`
  - `configs/architecture/schema_registry_v1.json`（註冊 `q-demo.candidate-view.v1`）
- **複雜事件 T2 偵測索引跨平台化與 CX-8 規則追蹤轉接器**：
  - `scripts/build_q1q5_detection_index.py`（跨平台 `shutil.disk_usage` D118 8 GiB 硬體門檻）
  - `scripts/run_cx8_rule_tracking.py`、`tests/q1q5/test_cx8_tracking_adapter.py`
  - `frontend/workbench-v2/tracking-source.mjs`、`frontend/workbench-v2/event-menu.test.mjs`（`cx8Tracking` 真實輸出與 `SYNTHETIC` 回退）
- **跨平台開發環境、乾淨 Clone 驗證與擴充 Office 場景腳本（T1/T4/C3）**：
  - `scripts/ensure_env.py`、`scripts/verify_clean_clone.py`、`scripts/build_office_expanded_scene.py`、`start_all_demo.ps1`、`tests/q1q5/test_cross_platform_scripts.py`
- **專案文件包與交付收據更新**：
  - `docs/project/{README,SPEC,ROADMAP,BUILD_FROM_SCRATCH}.md`
  - `docs/engineering/D126_CORE_DELIVERY_RECEIPT_20261104.md`

### 6.2 自動化測試與架構守門結果
- **Python 契約與單元測試**：
  ```powershell
  python -m pytest -o pythonpath=src -q tests/q1q5/test_core_search_track_t.py tests/q1q5/test_demo_camera_map_t.py tests/q1q5/test_demo_recording_title_t.py tests/q1q5/test_demo_candidate_view_t.py tests/q1q5/test_openai_prediction_t.py tests/q1q5/test_physical_prediction.py tests/q1q5/test_cx8_tracking_adapter.py tests/q1q5/test_cross_platform_scripts.py
  ```
  - 結果：**215 passed, 4 skipped, 0 failed**（含 `AMIDST_REQUIRE_IMPL=1` 下 `test_core_search_track_t.py` 契約測試全數通過；僅 `test_r004_scene_rooms_have_an_indoor_manual_camera` 因 `camera_graph_v3_1.json` 受 A17 權限鎖定保護而依契約標記 `SCENE_ROOM_COVERAGE_PENDING`）。
- **Node.js 前端契約與選單測試（`AMIDST_REQUIRE_IMPL=1`）**：
  ```powershell
  $env:AMIDST_REQUIRE_IMPL="1"; node --test frontend/workbench-v2/core-search-track.test.mjs frontend/workbench-v2/search-dialog.test.mjs frontend/workbench-v2/event-menu.test.mjs
  ```
  - 結果：**50 passed, 0 failed, 0 skipped**。
- **架構守門檢查（Architecture Guard）**：
  ```powershell
  python scripts/check_architecture_guard.py --repo . --base origin/mainline/q1q5
  ```
  - 結果：**PASS**（`authority: 0 findings`, `inference: 0 findings`, `schemas: 0 findings`）。
- **格式與空白檢查**：
  ```powershell
  git diff --check
  ```
  - 結果：**PASS**（0 空白或格式錯誤）。
