# 第二批後端：真實資料接入 v2 整合規格

日期：2026-10-20（Asia/Taipei）

狀態：**規格草案，給 Codex 後端（2a–2d）與 Claude 前端（V2-3～V2-10）共同依循。**本文不改程式、契約或任何分支，也不定案 §5 的未決項目；那些要由協調者轉成使用者決策。數值與規則一律引用 D-編號或契約章節，找不到依據的寫 `UNKNOWN`。

## 0. 依據（固定版本）

| 來源 | 版本 |
| --- | --- |
| 契約 v1.1（已核准，D60） | `docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md` @ `98451bd60c0857f38d8638a2548029e557195bf5`（#65）。下文「契約 §x」都指這一版 |
| 契約 v1.2 草案（D61） | #65 @ `1c9669c82177dc0ad83e78c630efb7b304121c46`，只改 §6.3.1 第 4 步：外部視覺判斷 v1 固定 `NOT_USED` |
| 工作台 v2 設計 | #72 `claude/workbench-v2-design` @ `c4dbd46`，§4.3 Demo 1–7 步、§6.4 R1–R9、§6.6、§9 |
| #75 後端第一批 | `codex/controlled-scene-backend` @ `6e1c439`，交接 `docs/engineering/CONTROLLED_SCENE_BACKEND_FIRST_BATCH_20261018.md`；最新複審「需修改」N1–N4、契約問題 C1（[#75 留言](https://github.com/Polalalabear/amidst/pull/75)，2026-10-19T16:08Z） |
| #80 後端第二批 2a | `codex/controlled-scene-real-v2-2a` @ `207818308d16e451fd9ffcac1f167abc2bda0469`，交接 `docs/engineering/CONTROLLED_SCENE_BACKEND_BATCH2_20261020.md`（下稱「2a 交接」） |
| 舊模組重用盤點 | `codex/office-demo-rehearsal-docs` @ `812817f`，`docs/engineering/CONTROLLED_DEMO_PREPARATION_20261018.md` §3 |
| 門檻 | #76 @ `6f862e6`；D56 全文在 [#65 留言 6270650347](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6270650347) |
| K1／K8c 純模組 | 整合分支 `claude/office-demo-visualization` @ `f481fe0`：`src/amidst/blind_hypothesis/engine.py`（`workbench.blind-hypothesis.v1`）、`candidate_screen.py`（K8c，`workbench.candidate-screen.v1`）；盲區假設契約 `docs/contracts/OFFICE_BLIND_HYPOTHESIS_V1.md` |

使用者決定照引用，不重議：D25、D26、D28、D37、D38、D41、D42、D44–D47、D54、D56（Q5–Q26）、D57–D61。CS-B 已由 D59 通過。

## 1. 目標與完成定義

**目標：**v2 用真實 run `ctrl-lcorr-s1-a-5fps-v1-r001`（A，`[0,10)` s，W1／W2／R102_CTRL）與 `ctrl-lcorr-s1-b1-5fps-v1-r001`（B1，`[0,20)` s，加上 N1）跑完 Demo 7 步（#72 §4.3）。每一步只讀 Codex 端點，不回退到 fixture（2a 交接 §1）。

| Demo 步 | 需要的後端能力 | 批次 |
| --- | --- | --- |
| 1 A 2D 同步播放 | bootstrap、session、`synced_frames`、token 媒體 | 2a |
| 2 A 候選鏡頭查詢 | `candidate_cameras`（契約 §6.1）＋靜態可見範圍索引 | 2c |
| 3 A 3D 區間與點擊回溯 | `person_layer`（`ground_estimate`＋`composed_ground`，§6.3、§6.3.1）；同軌跡 `INFERRED_CONNECTOR`（§6.4）；`evidence_lookup`（§6.5） | 2b＋2d |
| 4 B1 進出查詢 | `candidate_cameras` | 2c |
| 5 B1 轉角盲區 | `curve_layer` 的 `BLIND_HYPOTHESIS`（K1＋負證據）；負證據需要 2c 的 `visible_floor` | 2c＋2d |
| 6 B1 N1 再出現 | `person_layer`（N1）＋未關聯基線與候選（CS-Q8、K8c） | 2b＋2d |
| 7 B1 8 格 | `synced_frames`；後 4 格空白，不補位 | 2a |

**一個端點算「接入完成（READY 接入）」的條件：**
1. 對 A、B1 的真實請求回 200，形狀照契約該節，帶 §6 共通欄位（`resolved_scope`、`provenance.gt_read: false`、`output_sha256`、`identity_verdict: "UNCONFIRMED"`、`agent_used: false`），不再回 `CONTROLLED_LAYER_NOT_MATERIALIZED`。
2. 內容狀態照契約規則可以是 `READY`、`PARTIAL` 或 `UNKNOWN`。例如靜態用途未核准時回 `UNKNOWN` 並附原因，這仍算接入完成；回 503 或拿 fixture 頂替則不算。
3. 完整性錯誤照 §2.3 fail closed（409），不降格為 `MISSING`。
4. 每個 `READY` 推論都帶 §2.4 的 `uncertainty`（D45），缺少時整個回應 fail closed。
5. 本批的 focused tests 全過，並有 Claude（Opus）獨立複審紀錄。

**本批完成後仍是 NOT_READY（不在第二批範圍，也不得宣稱已完成）：**
- `runtime_profile.runtime_readiness`：維持 `NOT_READY`，直到有另外的 checkpoint 核准（2a 交接 §2）。
- 輸出凍結、GT 評估（D26），以及 §8「凍結後評估」欄的所有指標（D56 Q19–Q23）。
- CS-D 物理曲線（D56 Q12 是方向，不是 API；契約 §6.4）與 `PREDICTION`（D 包）。
- 外部視覺判斷：v1 固定 `NOT_USED`（D61，v1.2 草案）；外部 API 另需授權（契約 §7）。
- launcher R7 改預設入口，要等 v2 瀏覽器驗收（#72 §6.4 R7）。
- checkpoint 核准、合併：照 AGENTS.md，本批都不授權。

## 2. 現況表（2026-10-20）

整合分支 head 是 `f481fe0`；下列 PR 都是 Draft，沒有一個合併進整合分支。「真實」指讀 safe RGB 的實際 Blender 產出（`data_origin: ACTUAL_BLENDER`），不代表場景或估計已驗收。

| 端點 | fixture（#75 @ `6e1c439`） | 真實資料 | 待做 |
| --- | --- | --- | --- |
| `GET /api/bootstrap?surface=workbench-v2` | `SYNTHETIC_FIXTURE`，`real_run_support: NOT_IMPLEMENTED` | #80 @ `2078183`：A、B1，`status: PARTIAL`，`real_run_support: RGB_PLAYBACK_ONLY`，新增 `scenes[].runs[]` | 寫進契約（§3.1 草稿 B1） |
| `POST /api/session` | fixture scene scope | #80：真實 scene scope（依 2a 交接 §4 第 1 點；本文未獨立驗證） | — |
| `POST /api/synced_frames` | 只有 `MISSING`／`OUT_OF_RANGE` tile，`media_tokens_issued=0` | #80：真實 tile＋token 媒體 URL | 契約條文（§3.1）；§5 O8、O9 |
| `GET /api/controlled_rgb?token=` | — | #80 | 同上 |
| `POST /api/candidate_cameras` | 骨架：所有候選 `UNKNOWN`，整體 `UNKNOWN` | 503 `CONTROLLED_LAYER_NOT_MATERIALIZED` | 2c |
| `POST /api/person_layer` | 骨架（`UNKNOWN` ground）；validator 還有 N1–N4 漏洞 | 503 | #75 N1–N4，然後 2b |
| `POST /api/curve_layer` | 骨架（假設範圍帶＋未關聯基線）；N3、N4 漏洞 | 503 | #75 N3、N4，然後 2d |
| `POST /api/evidence_lookup` | 骨架（未物化的 support 不跳轉） | 503 | 2d |

前端：V2-0 player-grid #71、V2-1 外框 #74、V2-2 `api.mjs`／`uncertainty.mjs`／fixture #79，都是 Draft。

**目前已知的資料阻擋（讀 B1 safe `scene_static.json` 與 `cameras.json` 的 metadata，沒有讀影像或 private 檔）：**
- 42 個 `objects[]` 的 `approval_status` 全部是 `NOT_EVALUATED`，其中 27 個宣告了 `OCCLUSION`／`COLLISION`／`VISIBILITY_INDEX`、8 個宣告了 `WALKABILITY`；6 個 `walkable[]` 的 `approval.status` 也都是 `NOT_EVALUATED`。
- 依契約 §3.3、§3.4、§6.3.1 第 1 步，未核准用途的幾何不能拿來判定遮擋、建索引或給 K1 當地圖。所以 2b 的 `occlusion_near`、2c、2d 會全部回 `UNKNOWN`，直到 §5 O10 有決定。
- 4 台鏡頭的 `run_bindings[].visibility_index_ref` 都是 `null`。
- `WALK_R102` 有 1 個 `holes_m`，K1 的 `polygon_floor_map` 只收外環（見 2d）。

## 3. 批次規格

### 3.0 四批共通規則

- **可讀：**只限 manifest allowlist 中、逐檔驗過 `file_sha256` 的 safe 檔（契約 §3.0、§3.10），以及已 pin 的公開 config。
- **禁止讀：**`private_evaluation/`、`event_*.validation.json`、`persons.sim.json`、GT、mask、depth、renderer visibility（契約 §7）。D47／D54 的 CS-B 篩選輸出、產製路線投影、人工審查 JSON 也不得進推論（契約 §7「投影比較基準」）。
- **時間：**比較、排序與 hash 一律用整數微秒（D56 Q14）；同步容差 1 ms（D41）。
- **完整性錯誤：**409，`controlled-scene.error.v1` 信封（§3.1 草稿 B3）；必要輸入缺失回 503。
- **不確定度：**每個 `READY` 推論都帶 §2.4 的六個欄位；`quality_grade` 依 D56 Q13 由 `extent_value` 推出；顯示精度一律往外進位（D56 Q24，前端負責）。
- **身份與物理：**`identity_verdict` 永遠是 `UNCONFIRMED`；`physical_verdict` 在核准範圍以外是 `UNKNOWN`（契約 §1）。
- **延遲：**LOCAL p95，同步影格 ≤200 ms、圖層 ≤1 s；不達標只記錄，不擋驗收（D56 Q26）。
- **每批交付：**獨立 Draft PR、focused tests、`git diff --check`、實際產出紀錄；不凍結、不讀 GT、不合併。

### 3.1 2a：真實 RGB 與 token 媒體（#80，已實作，待複審）

**輸入：**兩個 run 的 safe `manifest.json`、`scene_static.json`（只核 hash，不產生 authority）、`cameras.json`、`runtime_profile.json`、`rgb_index.json`（D57 adapter `controlled-scene.rgb-index-adapter`／`d57-v1`），以及 index 中已 pin 的 RGB PNG。

**處理：**`load_safe_run(purpose="RGB_PLAYBACK")` 讀上述檔案 → 依有理數 grid 選格（`LATEST_AT_OR_BEFORE_EXPECTED_GRID`，§6.2）→ 先驗所有請求的 tile，全部通過才發 token（atomic）→ GET 時再驗一次 hash，並移除 PNG 文字 chunk。

**輸出：**`controlled-scene.synced-frames.v1`（§6.2）＋ bootstrap `runs[]`＋媒體 bytes。

**檔案：**新增 `controlled_scene_rgb_data.py`、`controlled_scene_rgb_api.py`、`scripts/check_controlled_rgb_playback.py`、`tests/workbench/test_controlled_scene_rgb.py`；修改 `controlled_scene_data.py`、`service.py`、`scripts/office_demo_backend.py`。

**依賴：**#75（2a 堆在 #75 @ `6e1c439` 上）。

**Focused tests：**`test_controlled_scene_rgb.py`、`test_controlled_scene_service.py`、`test_controlled_scene_data.py`、`test_service.py`。Codex 自報 307 passed，真實 WSGI 21 次 GET PASS；本文未重跑。

**驗收條件：**
- 選格不回退；`missing[]` 的 sample 回 `MISSING`；`[0, duration)` 以外回 `OUT_OF_RANGE`（§2.2、§2.3）。
- `abs(clock_error_s) ≤ 0.001`（D41）；`sample_age_s` 分開記錄。
- hash 不符整份 409、不發 token；完整性錯誤後該 run 在這個 instance 鎖閉。
- `synced_frames` p95 ≤200 ms：`UNKNOWN`，尚未量測（D56 Q26，只記錄）。
- 補一條 focused test：請求帶禁用或額外欄位時回 422 `FORBIDDEN_INFERENCE_INPUT`。這是 D32 已核准的 CS-Q6 條文（契約 §7），2a 交接的錯誤表沒有列 422，實作是否符合 `UNKNOWN`。

**R4 審視：**

| # | Codex 提案 | 判定 |
| --- | --- | --- |
| R4-a | READY tile 的 `frame_ref` 直接放媒體 URL `/api/controlled_rgb?token=…` | **與契約衝突，需決定（§5 O8）。**§6.2 範例的 `frame_ref` 是穩定 ref `fr-…-CAM_W2-000062`，§6.3 與 §6.5 的 `frame_ref`／跳轉也用同一個 ref。改成隨機 URL 之後，同一格的 ref 每次都不同，§7「預填與手動查詢的比較」也無法比 `output_sha256` |
| R4-b | `t_s × 10⁶` 不是整數時回 400，不自行 round | **與 D56 Q14 的採用文字不同，需確認（§5 O9）。**D56 Q14「照建議」採 #76 B10 選項 1，原文是「請求的 `t_s` 先四捨五入到整數微秒」 |
| R4-c | token：`secrets.token_urlsafe(32)`、有效 120 s、上限 2048、只在當前 process 有效、不寫 log | 可接受。須標明是**工程預設，不是 CS-Q9 門檻**；前端遇到 410 或 403 就重取 `synced_frames` |
| R4-d | GET 只收 `token`；localhost Host、同源 Origin、`Sec-Fetch-Site: cross-site` 拒絕；`no-store`、`no-referrer`、`nosniff` | 可接受，照寫進契約 |
| R4-e | 回原檔 `file_sha256` 與 HTTP bytes 的 `served_sha256`，兩者不混用 | 可接受，符合 §2.1 命名原則 |
| R4-f | 錯誤表（400／403／409／410／503） | 可接受；另補 422（R4-c 驗收條件）與 C1 封閉清單（§5 O7） |
| R4-g | bootstrap 每個 run 的 `camera_ids` 為準；A 的 cameras 檔含 N1，但沒有 A 的 run binding，所以不列 N1 | 可接受，符合 §3.7 run binding 規則 |

**建議寫進契約（v1.2 或下一版）的條文草稿：**以下用 O8、O9 的建議選項起草；使用者選了其他選項時跟著改。

- **B1（新增 §6.0 bootstrap）：**`GET /api/bootstrap?surface=workbench-v2` 回 `controlled-scene.bootstrap.v1`，欄位如下：
  - 頂層：`data_origin`（`ACTUAL_BLENDER`、`SYNTHETIC_FIXTURE`）、`fixture_marker`、`status`、`real_run_support`、`gt_read: false`；
  - `scenes[].runs[]`：`{run_id, clock_id, sampling, camera_ids, manifest_sha256, source_sha256, input_adapter_receipts[], runtime_readiness, unavailable_inputs[], capabilities{<endpoint>: AVAILABLE | NOT_MATERIALIZED}}`。

  前端以每個 run 的 `camera_ids` 與 `sampling` 為準，不得用 scene 的鏡頭聯集補格。`capabilities.*: AVAILABLE` 只表示入口存在，不表示 `READY`。
- **B2（§6.2 補充）：**
  - READY tile 帶穩定的 `frame_ref`（`fr-<run_id>-<camera_id>-<frame_index:06d>`）、`file_sha256`、`served_sha256`，以及 `media_url`（`/api/controlled_rgb?token=<43 字元 base64url>`）與 `media_token_ttl_s`。
  - `media_url` 與 `media_tokens_issued` 不進語意 hash；`output_sha256` 照 §2.1 計算，但把每個 `media_url` 換成 `null`，所以同一請求可以重現。
  - token 是有範圍的 bearer capability，綁定 session、scene、run、source、manifest pin、camera、frame_index、`file_sha256`、`served_sha256`；有效期與上限是工程預設，不是 CS-Q9 門檻；不持久化、不寫 log。
  - 媒體 bytes 是移除 tEXt／iTXt／zTXt 之後的 PNG，其他 chunk 的位元組不變。
  - 所有請求的 tile 都驗過才發 token；任一失敗整份 409，不發 token。
- **B3（§7 錯誤表擴充）：**
  - 信封：`{"schema_version":"controlled-scene.error.v1","error":{"error_class":…,"reason":…}}`；
  - 對應：400 `InvalidRequest`、403 `AccessDenied`／`MediaAccessError`、409 `DataIntegrityError`、410 `MediaAccessError: MEDIA_TOKEN_EXPIRED`、422 `FORBIDDEN_INFERENCE_INPUT`（照 CS-Q6，不變）、503 `RequiredInputUnavailable`（含 `CONTROLLED_LAYER_NOT_MATERIALIZED`）。
  - 409 時前端清空或遮住全部舊 tile 與 3D 幾何，不畫成 `MISSING`。
- **B4（§6.2 時間輸入）：**回應帶 `t_us`、`expected_timestamp_us`；`_s` 欄位由整數微秒換算。非整數微秒的輸入照 O9 的決定處理。

### 3.2 2b：局部追蹤 → C4a → 軌跡身高 → `composed_ground` → `person_layer`

**輸入（只限 safe 與已 pin 的公開 config）：**
- 已驗 hash 的 safe RGB；`cameras.json` 光學校正，經 `adapt_calibration`、`FULL_RUNTIME` 讀取（2a 的 `RGB_PLAYBACK` scope 校正是空的）；`floors[]` 支撐面。
- `scene_static` 中 `allowed_purposes` 含 `OCCLUSION`、而且 `approval_status: APPROVED` 的幾何。目前沒有，見 §2 與 §5 O10。
- 新的偵測與追蹤設定 `configs/controlled_scene_perception_v1.json`，在產出前 pin。
- 人體先驗設定（manifest `config_pins.body_prior_sha256`；範圍 1.65–1.75 m，D42）；速度設定 `v_max = 2.0 m/s`（D56 Q5）。

**處理步驟：**
1. **偵測（只讀 RGB）：**逐格產出元件、bbox、`contact_quality`、`merged`／歧義旗標。不得沿用 `perception.py` 為舊小目標設的常數：人高 112 px 時，幾乎每個人都會被標成 `merged`（#76 §2.3 C8）。
2. **單鏡頭局部追蹤（§3.12）：**
   - 同一條 track 最多容忍 1 格沒有偵測；`missing[]` 的 sample 與歧義格一律斷開（D56 Q15）。
   - 跨缺口的位移要通過 `v_max` 速度閘（D56 Q5，追蹤閘共用）。
   - 記錄 `gap_reasons`、`termination_reason`、`ambiguity_reason`。
   - track 不跨鏡頭，不升級成身份。
3. **C4a 單格投影：**`ground_estimate`，`FOOT_RAY_PIXEL_BAND`，`PROJECTED_OBSERVATION`，照區間觀測 v1 原樣保留（§6.3.1）。
4. **靜態遮擋檢查：**用整條腳點像素帶再向外擴 2 px，只對已核准的 `OCCLUSION` 幾何檢查；未核准或 `UNKNOWN` 的幾何記為 `UNKNOWN`（D56 Q11、§6.3.1 第 1 步）。
5. **外部視覺判斷：**每格記為 `NOT_USED`（D61，v1.2 草案）。不接姿態模型，也不接 OpenAI API。
6. **軌跡身高 `track_height_estimate`（§3.12）：**
   - 只用高信心影格：單一元件、邊距 ≥16 px、人高 ≥112 px、`contact_quality: PASS`、未遮擋（D38、D56 Q6）；最少 5 格（D56 Q7）。
   - 不確定度用支持影格身高的全距，全距 ≤0.06 m；不比先驗窄 40% 以上就退回先驗（D56 Q8）。
   - `temporal_scope: WHOLE_TRACK`、`uses_future_frames: true`（D56 Q9）。
   - 不跨 track、不跨鏡頭；不出現在跨鏡頭候選的 payload。
7. **`composed_ground`（§6.3.1 組合規則）：**
   - 計算順序：頭部射線的身高範圍（`track_height` 或 `prior`）→ `occlusion_near`／`lowest_visible_far` 收緊兩端 → 與 `speed` 範圍取交集。
   - `speed` 的錨點只取同一條 track、時間在前、高信心的位置，Δt ≤1.0 s，而且不鏈接（D56 Q12）。
   - 交集為空時回 `UNKNOWN`／`CONSTRAINTS_INCONSISTENT`；所有條件都失效時回 `UNKNOWN`／`ALL_CONSTRAINTS_UNAVAILABLE`。
   - 每格都列出 `constraints_used` 與 `constraints_unavailable`。
8. **方向 heading：**同一條 track 的 5 格窗（D56 Q16；細則照 #76 B12 選項 1：起點格與終點格的區間不重疊才 `READY`，夾角 >90° 就是 `UNKNOWN`）；`READY` 時帶 `ANGLE_DEG` 不確定度。
9. **display：**只有 `quality_grade: HIGH` 而且區間 ≤0.25 m 時，`humanoid_range_allowed: true`（D56 Q25）。

**輸出：**`controlled-scene.person-layer.v1`（§6.3、§6.3.1）；局部軌跡與軌跡身高（§3.12），寫進 pin 過的感知索引（`perception_version`／hash）。

**重用與新寫（依準備文件 §3）：**

| 重用（核心不改） | 新寫或改造 |
| --- | --- |
| `engineering/hybrid_contact.py`：`estimate_contact`、`_foot_segment`、`_height_segment`（射線與平面求交、區間輸出、來源 hash gate） | 新 source／run／相機／floor 綁定；不套舊 Office 常數（§0.1「新場景不沿用」） |
| `engineering/perception_v2.py`、`workbench/contact_scene.py`：RGB hash 與尺寸驗證、元件與品質紀錄、原始 `MISSING` 與 sibling estimate 分開 | **局部追蹤器**：v2 目前 `_local_tracks=()`，要新寫 |
| `controlled_scene_data.load_safe_run`、`adapt_calibration`、`finite_number`、canonical hash | 偵測設定（不沿用 C8 常數）；遮擋射線檢查（只用已核准幾何）；軌跡身高；`composed_ground` 組合器；heading；`person_layer` 真實 adapter |

**檔案（2a 交接 §5）：**新增 `src/amidst/workbench/controlled_scene_perception.py`、`src/amidst/engineering/controlled_scene_contact.py`、`src/amidst/workbench/controlled_scene_person.py`、`configs/controlled_scene_perception_v1.json`、`tests/workbench/test_controlled_scene_person.py`；修改 `controlled_scene_data.py`、`controlled_scene_rgb_api.py`。

**依賴：**
- #75 N1–N4 修好（validator 會擋 `composed_ground` 缺少、幾何與 extent 不符、`evidence_state` 錯置、條件名不合法）。
- 2a 的 scope 與 RGB hash。
- §5 O10（遮擋幾何核准）；沒有決定時 `occlusion_near` 一律 `UNKNOWN`，其他條件照常。
- §5 O5、O6（`evidence_state` 名稱、`SEGMENT`／`POLYGON`）：未決定前照 #75 M2 的現況，不寫死新名稱。

**Focused tests：**`test_controlled_scene_person.py`，加上既有 `test_controlled_scene_service.py`、`test_controlled_scene_data.py`、`test_controlled_scene_rgb.py`。

**驗收條件：**
- 收據列出每條 track 的格數與缺口；沒有 track 跨過 >1 格的缺口或任何 `missing[]` sample（D56 Q15）。B1 同一台鏡頭兩人至少錯開 4 個空 sample（D37），所以不會有 track 同時含兩人；這一點只用 RGB 收據核對，不讀 GT。
- `track_height_estimate`：`READY` 時 `n_support_frames ≥ 5`、`upper_m − lower_m ≤ 0.06`；不符時是 `INSUFFICIENT_FRAMES` 或 `NOT_NARROWER_THAN_PRIOR`，`height_m` 與 `uncertainty` 都是 `null`。
- 每一筆 estimate 都有 `composed_ground`（N1）；`READY` 時 `extent_value ≥ geometry.length_m`（N2）；`evidence_state` 不是觀測或 `MISSING`（N3）；條件名只在 §6.3.1 的五種之內（N4）。
- `quality_grade` 與 D56 Q13 一致；`humanoid_range_allowed` 與 D56 Q25 一致。
- 每格的外部視覺判斷都是 `NOT_USED`（D61）。
- 交付 0／1／2／4 px 改判格數比較圖（D56 Q11 追加工作，凍結前）。
- `person_layer` p95 ≤1 s（D56 Q26，只記錄）。
- import graph 測試：正式路徑不 import 評估模組，不開 private 檔。
- **預期現象，不得為此調參：**W2 架高 1.8 m，和人頭差不多高。腳被遮住時，`prior` 或 `track_height` 給出的區間長達數公尺（#76 §2.4，設計估計），會分到 `LOW`。
- 準確度（涵蓋率 ≥0.70、HIGH ≥0.90，D56 Q21）屬凍結後評估，不是本批驗收。

### 3.3 2c：可見範圍索引 → `candidate_cameras`

**輸入：**
- `cameras.json` 光學校正與 `run_bindings[]`；`scene_static` 的 `floors[]`、`walkable[]`、`portals[]`、`AREA_*`（B1 有 `AREA_R101_FRONT`、`AREA_OBS_BAY_N`）。
- `allowed_purposes` 含 `VISIBILITY_INDEX`／`OCCLUSION`、而且 `APPROVED` 的幾何；只讀 manifest allowlist 中 pin 過的 safe `geometry/` 檔。
- 若需要從 `.blend` 重新匯出 mesh，屬 Blender 操作，要另外授權（AGENTS.md）。
- **不讀** renderer visibility、depth、GT、含人物的場景（契約 §7「靜態索引」）。

**處理：**
1. 對每台鏡頭，只用不含人物的靜態幾何做 raycast，得到地面足跡（`SOURCE_MESH_RAYCAST`）。D21 strict 與 suggestion 分開。
2. 把索引寫成 pin 過的檔案（`visibility_index_sha256`），由 `run_bindings[].visibility_index_ref` 引用。
3. 對查詢 polygon（頂點 ≤64，D56 Q17）計算四種 `relation`；`UNKNOWN` 不得寫成 `NO_INTERSECTION`。
4. 排序依 D28：`relation_tier → overlap_area_m2_desc → camera_id`。偵測數只放在 `image_evidence`；沒有感知時是 `NOT_EVALUATED`，`frames_with_detection` 是 `null`。
5. 分頁 cursor 綁 query、snapshot 與 pin；deadline 5 s，到期回 `PARTIAL`＋`truncated`（D56 Q18）。
6. 同一份索引的地面足跡，也提供 2d 的負證據 `visible_floor`（盲區假設契約 §3.3）。注意：地面看不到不證明全身看不到（2a 交接 §5）。

**輸出：**`controlled-scene.candidate-cameras.v1`（§6.1），以及可見範圍索引檔與它的 hash。

**重用：**`scripts/export_floor_visibility.py`、`scripts/build_floor_visibility_index.py`、`src/amidst/geometry/floor_visibility_index.py`（來源綁定、strict／suggestion 分離、`UNKNOWN` 不可偽造負證據）；`frame_retrieval.TimeFrameIndex` 的 metadata 核心。

**新寫或改造：**
- 新場景的相機與幾何角色 adapter。不得把新的正式幾何誤當 proxy 排除，也不得把舊 annotation proxy 升權（準備文件 §3）。
- 新候選 loader 從 safe catalog 取 provenance，不依賴 `_ground_estimates`（CS-Q12）。
- 演算法若要改，要先交 Claude（2a 交接 §5）。

**檔案：**新增 `src/amidst/workbench/controlled_scene_candidates.py`、`scripts/build_controlled_visibility_index.py`、`configs/controlled_scene_visibility_v1.json`、`tests/workbench/test_controlled_scene_candidates.py`；修改 `controlled_scene_data.py`、`controlled_scene_rgb_api.py`。

**依賴：**#75 候選 provenance 與錯誤規則、2a run binding、§5 O10（用途核准）、§5 O11（通路距離）。不必等 2b，因為 D28 不用偵測數排序。

**驗收條件：**
- 同一正規化 query 重跑，`output_sha256` 相同；預填與手動查詢的語意 payload 與 hash 相同（契約 §7）。
- 分頁不漏、不重；沒有靜默截斷；`unknown_camera_ids` 不省略。
- 沒有任何感知或接地結果時也能回答（CS-Q12）。
- 必要輸入缺失時不得回 `READY`。用途未核准時整體是 `UNKNOWN` 或 `PARTIAL`，並附原因。
- 圖層 p95 ≤1 s（D56 Q26，只記錄）。
- 召回目標 1.0（D56 Q19）屬凍結後評估。
- Demo 旁白「W2、W1 在前、R102 不相交、B1 是 PARTIAL」是 #72 mockup 的 SYNTHETIC 值，**不得當驗收答案**；旁白一律由真實 payload 計算。

### 3.4 2d：K1／C4b 新事件 adapter → `curve_layer`、`evidence_lookup`

**輸入：**
- 2b 的局部軌跡、`ground_estimate`、`composed_ground`（感知索引 pin）。
- 2c 的可見範圍索引（負證據的 `visible_floor`）。
- 已核准的 `walkable[]`／`portals[]`（§3.4）；`rgb_index.missing[]`。
- 速度設定 `v_max = 2.0 m/s`（D56 Q5，與 2b 共用同一份 config hash）；新的受控場景 K1 設定檔（`office-demo.blind-hypothesis-config.v1` 格式，新檔）。
- **不讀** `designed_blind_intervals`；缺口只由 RGB 紀錄判斷（§2.2）。

**處理：**
1. **候選端點組（CS-Q8）：**由局部軌跡的結束與開始產生，附兩端 ref、hash、clock、eligibility、`candidate_ref`；保留未關聯基線與多解；不讀 actor 或盲窗。沒有合法端點就回 `UNKNOWN`。
2. **K8c 篩選：**對每組呼叫 Claude 的 `screen_cross_camera_candidates`（`workbench.candidate-screen.v1`），結果分成 `REACHABLE`／`UNREACHABLE_UNDER_CONFIG(_AND_EVIDENCE)`／`UNDETERMINED`。這不是機率，不排序，也不選出「最可能」的一組。
3. **K1：**照原樣呼叫 `generate_blind_hypotheses`，請求格式照盲區假設契約 §3。
   - 端點只能是 `ground_estimate`（`PROJECTED_OBSERVATION`、`READY`；POINT 要 `contact_quality: PASS`）。K1 目前會拒絕推論狀態的端點（`EVIDENCE_STATE_NOT_PROJECTED_OBSERVATION`）。`composed_ground` 能不能當端點，見 §5 O12。
   - 端點替代照盲區假設契約 §3.1.1：同一條 track、只能往外、≤1.0 s。
4. **負證據：**
   - 只有「整格沒有任何偵測」的 sample 能產生 `NO_DETECTION`；畫面裡有人時，不能把「沒看到特定的人」當負證據（準備文件 §3）。
   - `DETECTION_PRESENT` 與 `UNKNOWN` 都不是負證據。
   - `visible_floor.method` 必須是 `SOURCE_MESH_RAYCAST`（盲區假設契約 §3.3）。
5. **地圖：**用 `polygon_floor_map` 與新的 descriptor `kind` 建圖，K1 不需要改。`WALK_R102` 的 hole 不能只丟掉外環以外的部分：要嘛把 hole 列進 `unknown_regions`，要嘛請 Claude 擴充 K1 支援 holes；選哪個由 Claude（K1 owner）決定。
6. **組成曲線（§6.4）：**
   - `OBSERVED`：單格區間序列；`INFERRED_CONNECTOR`：同一條 track、跨 ≤1 格缺口；`BLIND_HYPOTHESIS`：帶 K1 回應 hash 與 `per_sample_ref`（`reachable_regions[].area_m2`）；`MISSING_GAP`：只來自 `missing[]`。
   - kind 與 `evidence_state` 一一對應（#75 N3）；`PREDICTION` 只能出現在 `kinds_reserved`。
7. **`evidence_lookup`：**照 §6.5 的五種 `relation` 與穩定排序。`BLIND_HYPOTHESIS` 要列出兩端觀測與負證據影格，欄位待 §5 O2。

**輸出：**`controlled-scene.curve-layer.v1`（§6.4）、`controlled-scene.evidence-lookup.v1`（§6.5）；K1 回應的包裝格式待 §5 O3。

**重用：**K1 `engine.py`、K8c `candidate_screen.py`、K5 `pruning.py`／`retrieval_evidence.py`（Claude 擁有的純模組，整合分支 @ `f481fe0`）；C4b `blind_hypothesis_integration.bind_hypotheses`／`reconstruct` 的「封存回應、pin、append-only、provenance」概念。

**新寫：**`controlled_scene_hypotheses.py`（新事件 adapter）、`controlled_scene_curves.py`、`controlled_scene_evidence.py`。舊 D18 guard 原樣留給舊 run（§0.1），新 adapter 不呼叫它。

**檔案：**同上三個新檔，加上 `tests/workbench/test_controlled_scene_curves.py`、`test_controlled_scene_evidence.py`；修改 `controlled_scene_data.py`、`controlled_scene_rgb_api.py`。

**與 Claude 模組的交接：**
- Codex 照原樣呼叫 K1／K8c／K5，不改這些檔案；記錄模組來源 commit 與 config hash。
- adapter 需要 K1 行為變更時（O12 選 b、hole 支援、新 floor map 欄位），Codex 開 issue 給 Claude，由 Claude 另開 PR 改 K1 與盲區假設契約；Codex 等新版本 pin 之後再接。
- 交接面就是兩份 schema：`office-demo.blind-hypothesis-request.v1` → `workbench.blind-hypothesis.v1`，以及 `workbench.candidate-screen.v1`。

**依賴：**2b、2c、#75 N3／N4（M1／M2 已修）、2a token 媒體，以及 §5 O2、O3、O4、O10、O12。

**驗收條件：**
- B1 的兩人沒有被連成同一條已確認身份的曲線：`association.identity_verdict: UNCONFIRMED`，未關聯基線保留（§6.4、§8「B1 錯開」）。
- 每個 `READY` 的 `INFERRED_CONNECTOR`／`BLIND_HYPOTHESIS` 都帶 §2.4 `uncertainty`；`OBSERVED`／`MISSING_GAP` 不帶。
- 負證據只來自整格無偵測、而且 `SOURCE_MESH_RAYCAST` 的 `visible_floor`。
- K1 回應用同一輸入重跑，`output_sha256` 相同。
- `evidence_lookup` 距離相等時依 `timestamp_s → camera_id → observation_ref` 排序，結果穩定。
- 圖層 p95 ≤1 s（D56 Q26，只記錄）。
- K1 範圍帶涵蓋 0.25 m／目標 1.0（D56 Q20）、負證據錯誤剪枝 0（Q23）、錯連 0（Q22）屬凍結後評估。

## 4. 前端銜接

| 後端完成 | v2 可以從 fixture 切到真實資料的任務 | Demo 步 | 前端要注意 |
| --- | --- | --- | --- |
| 2a（#80 複審通過，契約條文 B1–B4 定稿） | V2-2 `api.mjs` 的 bootstrap／`synced_frames` 分支；V2-3 2D 格；V2-5 時間列與 sample grid；V2-10 只做 2D 部分 | 1、7 | 依 `data_origin` 分流，不套舊 `/api/media`；每個 run 用自己的 `camera_ids`。O8 選 a 時用 `media_url` 換圖、`frame_ref` 當 key；遇到 410／403 就重取 `synced_frames`，不換 run。要不要在瀏覽器驗 `served_sha256`（fetch＋SubtleCrypto）由 V2-3 決定；Codex 建議要驗 |
| 2b | V2-4 3D 人物與區間層；V2-7 inspector 的誤差來源（人物）；V2-8 第 3 步的區間部分 | 3（部分）、6（N1 區間） | 畫 `composed_ground`；`ground_estimate` 是可切換的追溯層；人形範圍只在 `humanoid_range_allowed` 時畫。`uncertainty.mjs` 的欄位名照 O5、O6 改，只改這一個檔（#72 §6.6） |
| 2c | V2-6 查找模式；V2-8 第 2、4 步 | 2、4 | `UNKNOWN` 不轉成不相交，`null` 不轉成 0；旁白由 payload 計算 |
| 2d | V2-4 曲線、緞帶與範圍帶；V2-5 時間軸區段；V2-7 點擊回溯；V2-8 第 3、5、6 步 | 3、5、6 | 內插與盲區的不確定度改讀 payload 的 `uncertainty`，不再由前端取兩端較大者（#72 §9 第 11 點，見 O13） |
| 2a–2d 全部 | V2-9 整合接線；V2-10 用真實 run 跑完整瀏覽器驗收 | 1–7 | MOCK 或 SYNTHETIC 下按「通過」，紀錄一律是 `UNKNOWN`（#72 §4.3） |

前端在 Codex 端點完成前，繼續用 #79 的 SYNTHETIC fixture 開發；fixture 與真實資料不混在同一畫面（#72 R6）。

## 5. 未決項目（給協調者轉成使用者決策；本文不定案）

| # | 題目與出處 | 選項（第一個是建議） | 影響 |
| --- | --- | --- | --- |
| O1 | 曲線「有偵測但接地 `UNKNOWN`」的時段沒有 kind（#72 §9 第 1、10 點） | **a** 新增 `UNKNOWN_GAP`：`evidence_state: UNKNOWN`、`reason`、`geometry: null`，點擊回 `NO_SUPPORT`<br>b 不加 kind，曲線在該處斷開成兩條<br>c 併入 `MISSING_GAP`（不建議：會把有影像的時段標成缺格） | 2d、V2-4／V2-5；#75 M2 的封閉 kind 清單要同步 |
| O2 | `evidence_lookup` 的負證據欄位（#72 §9 第 2 點；§6.5 只寫「列出」） | **a** `negative_evidence[]: {negative_evidence_ref, camera_id, frame_ref, timestamp_s, detection_result, used}`，對應盲區假設契約 §3.3 的子集<br>b 只回 `hypothesis_response_sha256`，前端另取 K1 回應<br>c 只回 `frame_refs[]` | 2d、V2-7 |
| O3 | 假設回應的 schema（#72 §9 第 4 點） | **a** 新包裝 `controlled-scene.blind-hypothesis.v1`：加上 §6 共通欄位（`resolved_scope`、provenance），內含原樣的 `workbench.blind-hypothesis.v1`<br>b 直接沿用 `workbench.blind-hypothesis.v1`，不包裝<br>c 把 K1 回應全文嵌進 `curve_layer` | 2d、V2-4（K4 範圍帶重用） |
| O4 | 曲線 `constraints_used` 的條件命名（CS-Q15 (11)） | **a** 封閉集合：D44 五種＋`endpoint_estimates`、`k1_reachability`（§2.4 已用的名稱）<br>b 只用 D44 五種，曲線另開 `curve_basis` 欄位<br>c 維持 OPEN，只驗非空字串（#75 N4 的暫行做法） | #75 N4、2d、`uncertainty.mjs` |
| O5 | `composed_ground` 的 `evidence_state` 名稱（CS-Q15 (6)） | **a** 採 `INFERRED_CONSTRAINED`<br>b 改名 `INFERRED_COMPOSED`<br>c 沿用 `INFERRED_INTERPOLATION`（不建議：§2.2 的語意不同） | 2b、#75 N3、V2-2／V2-4 |
| O6 | `SEGMENT` 與 `POLYGON` 的選用規則（CS-Q15 (7)） | **a** v1 一律 `SEGMENT`（`LENGTH_M`），像素敏感度另記欄位<br>b 橫向像素帶寬度超過門檻時用 `POLYGON`（門檻要另約定）<br>c 一律 `POLYGON`（`AREA_M2`） | 2b、#75 N2、V2-4 |
| O7 | `missing[].reason` 的封閉清單（#75 C1；§2.3 只寫「例如」） | **a** v1 只有 `RGB_RECORD_ABSENT`；新增原因要開新版本（D55 兩份 index 的 `missing[]` 都是空的，現在沒有影響）<br>b 封閉清單 `RGB_RECORD_ABSENT`、`RENDER_FAILED`、`EXPORT_FAILED`<br>c 開放字串，loader 只檢查非空 | #75 loader、§2.3 |
| O8 | 媒體 URL 放哪個欄位（2a R4-a） | **a** `frame_ref` 維持穩定 ref；新增 `media_url`，不進語意 hash（§3.1 草稿 B2）<br>b 照 #80：`frame_ref` 就是 URL<br>c 媒體端點改收 `frame_ref`＋session（不用 token） | #80、#71 `toDisplayModel`、§6.5 跳轉、§7 預填比較 |
| O9 | 非整數微秒的時間輸入（2a R4-b） | **a** 照 D56 Q14 採用的 #76 B10 選項 1：四捨五入到整數微秒（#80 要改）<br>b 照 #80 回 400（等於修改 D56 Q14 的採用文字，需要使用者明示）<br>c 無條件捨去 | #80；前端時鐘用整數毫秒，實際上不會送出次微秒值 |
| O10 | 靜態幾何用途核准（§2：全部 `NOT_EVALUATED`） | **a** 依 #77 validator、C7／K7 收據，由使用者核准；產生新的 `scene_static` 版本與 hash（§3.4「人工修訂要產生新的 map 版本」），RGB pin 不變<br>b 另立核准收據檔，由 manifest pin（要改契約 §3.3）<br>c 維持未核准；Demo 第 2–6 步的遮擋、候選、盲區都顯示 `UNKNOWN` | **2b `occlusion_near`、2c、2d 的前置阻擋** |
| O11 | 通路距離 `surrounding_policy`（CS-Q9 唯一仍 OPEN 的數值） | **a** 拓撲定義：經 `portals[]` 直接連到目標的 walkable 算通路，不用距離門檻<br>b 從目標邊界算 geodesic 距離 d（d 要另約定）<br>c v1 不產生 `ACCESS_PATH_INTERSECT` | 2c、Demo 第 4 步 |
| O12 | K1 端點用哪一種接地 | **a** 2d 只用 `ground_estimate`（K1 不改）；腳被遮的端點不合格，改走 §3.1.1 的端點替代或回 `UNKNOWN`<br>b K1 接受 `composed_ground` 當新的端點種類（Claude 改 K1 與盲區假設契約）<br>c 先 a，之後另開任務做 b | 2d、K1（Claude） |
| O13 | 內插與盲區不確定度由誰計算（#72 §9 第 11 點） | **a** 一律讀 `curve_layer` 的 `uncertainty`，前端不自己算<br>b 維持 v2 現行做法：取兩端半長的較大者 | V2-2 `connectorUncertainty`、V2-4 |
| O14 | §6.3 範例 `humanoid_range_allowed: true`，但 SEGMENT 長 0.85 m（[#65 留言 6271338272](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6271338272) 提出、未處理） | **a** 下一版契約把範例改成 `false`（D56 Q25）<br>b 不改，加註「範例數字示意」 | 只影響範例；2b 照 D56 Q25 實作 |

**不需要使用者決定、但要追蹤的事：**#75 N1–N4 修正與 L5 版本引用、2a 補 422 測試、D56 Q11 的 0／1／2／4 px 比較圖、`served_sha256` 前端驗證（V2-3 決定）。

## 6. 依據缺口（UNKNOWN）

- #80 是否已對禁用或額外欄位回 422：`UNKNOWN`，本文沒有跑測試。
- safe `geometry/*.geometry.json` 是否足以做 `SOURCE_MESH_RAYCAST`（精確 mesh，還是只有 footprint）：`UNKNOWN`。
- A run 的 `scene_static` 用途狀態：本文只讀了 B1；A 與 B1 共用 r003 source pin（2a 交接 §1），推定相同，未逐檔核對。
- 2b–2d 的工時：`UNKNOWN`（2a 交接 §5 也沒有估）。
- `/api/session` 對真實 scene 的 scope 行為：只依 2a 交接 §4，未獨立驗證。

## 7. 實際產出 / Actual output

- Model / effort: Claude Opus 5.5（`claude-opus-5-5`）／effort 由協調者設定，本 session 讀不到確切值：`UNKNOWN`
- PR / commits: 見 PR 描述（分支 `claude/batch2-integration-spec`，base 整合分支 @ `f481fe0`）
- Files changed: `docs/agents/CONTROLLED_SCENE_BATCH2_INTEGRATION_SPEC_20261020.md`（新增）
- Commands run and results:
  - 唯讀 `git show`：§0 列出的契約、設計、交接、準備文件、門檻提案，以及 K1／K8c 原始碼的介面段落。
  - `gh pr view 75`、`gh pr view 65`：讀 N1–N4／C1 與 D56、D60、D61 留言。
  - `git diff 6e1c439 2078183`：讀 #80 的 `service.py`、`controlled_scene_rgb_api.py` 變更。
  - Python 讀 B1 safe `scene_static.json` 與 `cameras.json` 的 metadata：approval 統計、`AREA_*` ID、`holes_m`、`visibility_index_ref`。
  - `git diff --check`：結果見 PR 描述。
- Artifacts: NONE
- Verified: 每個數值都對照了 D-編號原文（D56 留言、契約 `98451bd`）；2a 欄位對照 #80 原始碼（`TOKEN_TTL_S = 120`、`MAX_MEDIA_GRANTS = 2048`、tile `frame_ref` 就是媒體 URL）；K1 端點要求是 `PROJECTED_OBSERVATION`（`engine.py`）；`polygon_floor_map` 只收外環
- Not verified: 沒有跑任何程式或測試；沒有讀 RGB 影像、private 檔或 GT；沒有讀 A run 的 `scene_static`；Codex 自報的 307 passed 沒有重跑
- Deviations, UNKNOWN items and follow-ups: §5 共 14 項待決（O10 是 2b／2c／2d 的前置阻擋）；§6 列出 5 項 UNKNOWN
