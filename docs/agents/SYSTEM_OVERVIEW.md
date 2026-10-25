# 系統總覽（Q1–Q5 主線與受控場景底座）

> 日期：2026-10-25 更新（§0 第 5 點是 D78 之後的現況；§0 第 1–4 點與 §1 的「狀態」欄是 2026-10-20 D67 之後的快照，衝突時以第 5 點為準）。本文是**導覽**，不是規格：不重抄 schema，每個數值或規則都指向 D-編號（見 [DECISION_INDEX](DECISION_INDEX.md)）或契約章節。與原文不一致時，以契約和 GitHub 原始決策留言為準。
> **主線契約**：Q1–Q5 第一版 `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md`（PR [#86](https://github.com/Polalalabear/amidst/pull/86)）。**已定稿並核准**（D65）：固定在 `3873ff2`（bytes SHA-256 `924c4365…78078`），merge `f62ab72` 已合入 `mainline/q1q5`；§8.2、§8.3 的修訂已併入。下文「契約 §x」指它，除非標明 v1.1。
> **底座契約**：受控場景契約 `OFFICE_CONTROLLED_SCENE_V1.md` v1.1 @ `98451bd`（D60 已核准）。Q 契約沿用它的 §2、§2.1、§2.3、§3.6、§3.7、§6.1、§7。
> 驗收條件、文件位置、驗證方式、時程見 [Q1Q5_COLLABORATION_INDEX](Q1Q5_COLLABORATION_INDEX.md)。找不到依據的寫 `UNKNOWN`。這份文件**沒有**執行任何程式或推論。

## 0. 先讀這幾點

1. **主線是 Q1–Q5**（D63、D63 修訂、D64；D65–D67 放行第一版的計畫、契約與多數 gate）：Q1 依條件找相機、Q2 在影片中找人、Q3 理解使用者措辭、Q4 模型依自己的偵測判斷 2D 畫面是否含目標、Q5 目標離開時判斷是否切鏡。**2D→3D 重建線暫停保留**（2b–2d、CS-C、CS-D、#84、#85），不關、不刪（§2、§3 是它與共用底座的記錄）。
2. **GT 不進推論**：Ground Truth 只在輸出凍結並驗證預測 hash 之後，供評估使用（D1、D26）。Q 線額外禁止：r004 的人物設定（衣色、路線、速度）、事件腳本、`event_*.validation.json` 進入偵測索引、兩層圖、Agent／LLM prompt 與參數（契約 §9）。所有誤差數字在凍結前只能稱「設計估計」。
3. **`mainline/q1q5` 目前只有底座與文件，沒有 Q1–Q5 專屬的產品程式**（2026-10-20 檢查，head `10070eb`）。它含：後端 safe loader 與 A／B1 真實 RGB（#75、#80）、workbench-v2 外框／api／player-grid（#74、#79、#71）、舊 Office 時期的純模組（K1 盲區假設等），以及已核准的契約 #86（`3873ff2`）、計畫 #92、更新後的 `AGENTS.md`（#91）。契約已核准，Q 線產品程式現在可以寫（契約 §0.3 第 1 道 gate 通過）；已開的第一個 Draft PR 是 Codex 的 [#134](https://github.com/Polalalabear/amidst/pull/134)（#101 時間對應）。
4. **Q 線用 r004，不是 r003**：場景修改另存 r004（D63 (b)），r003 與 A／B1 的 pin（D53、D59）不變。r004 **尚未建檔**。D67 **只授權 Codex 建檔（r003 的複本）與靜態校正匯出**（前提：#132 經 Claude 審查通過），**不授權任何渲染**（廣角小批 preview、A4／B4 事件 run），渲染待磁碟 ≥ 12 GiB（D41）後另問使用者（#93 的 G5）。**（D70 之後已改：渲染已授權，但在 G4 凍結之後才做，見第 5 點。）**

5. **現況更新（2026-10-25，D68–D78；全文見 [DECISION_INDEX](DECISION_INDEX.md)）**：
   - **主線**：Codex 在 `codex/q1q5-staging` 自審後合進 staging，Claude 審後分批合進 `mainline/q1q5`（D70、D75）；第 1 批已合（[#213](https://github.com/Polalalabear/amidst/pull/213)）。staging 合併不是正式驗收；`main` 不動（D72）。**G3 已成立**（#125，merge `f915fb0`）。
   - **r004 與渲染**：D70 已授權 45 格廣角 preview、A4／B4 事件 run 與正式索引 #118（可用空間低於 8 GiB 立刻停）；但 D74 規定圖 v3 修完、Claude 複核、凍結並經使用者核定 **G4** 之後才產生正式事件 run，所以第 0 點的「沒有 Q 線產品程式」「尚未渲染」仍描述正式資料；CAM_WIDE 維持 90°（D76）；重疊區延後（D77）；牆與地板改色避開紅藍（D71）。
   - **Q5 與兜底**：兜底不是牆鐘截斷，是 Agent 故障時的下位替代（等同 `RULE_ONLY`，可從任一點接手到 session 結束，`fallback_budget_ms` 只記 `stats`）；**每台鏡頭都必須畫出口區域**，缺漏 fail closed（D71）。D73 維持 D65 預算、第一版不設 LOST 期限；D78 為同鏡頭重取得與 SWITCHING／stop 完成規格採案（尚未實作）。
   - **評估與驗收**：Q2、Q5 輸出凍結後和劇本自動比對；Q4 由組員對最終結果做 T／F；Q1、Q3 由組員出題（D71、D75、D76）。分兩階段驗收：P1 工程預驗收、P2 正式 baseline 驗收（[驗收計畫](Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)）。
   - **組員**：資料夾包、瀏覽器填表、`RETURN/` 回交，不用 Git（[TEAM_ONBOARDING](TEAM_ONBOARDING.md)）。

狀態標記：✅ 已有（`mainline/q1q5` 上有程式）　🟡 骨架或部分（只對舊素材能跑，或只有骨架）　⬜ 未實作　`UNKNOWN` 找不到依據。

## 1. Q1–Q5 資料流（契約 #86）

資料單向往上流。**下表全部是契約規格，除標 ✅／🟡 的底座外都還沒有實作**（⬜）。位置欄的路徑是提案（#93 說「檔案路徑多為提案」），以任務 issue 為準。

| 層 | 內容 | 來源（契約） | 負責任務 | 狀態 |
| --- | --- | --- | --- | --- |
| **Q-0　r004 素材** | 另存的場景版本；每台鏡頭的 safe RGB（解析度與鏡頭參數：`UNKNOWN`，待 r004 小批 preview 定案，計畫 #92 §12）。r004 修改表、靜態校正匯出、廣角小批 preview、A4／B4 事件 run 與 safe bundle | 計畫 #92 §5；契約 §0.2 | #97（提案，PR #132 待修）、#113（建檔與靜態匯出已授權、preview 渲染未授權）、#115（`needs-auth`，需渲染）（皆 Codex） | ⬜ |
| **Q-1　時間對應** | 展示時鐘（`DECLARED_DEMO_CLOCK`，IANA 時區、`t0_us`）↔ 來源時鐘；部分涵蓋要明示 | 契約 §3 | #101 | ⬜ |
| **Q-2　偵測索引** | RT-DETR 對 safe RGB 的偵測（模型版本與權重 SHA-256、`class_map`、`nms.applied: false`）＋人物框上半身最小 HSV 顏色摘要（`STRONG`／`WEAK`／`NONE`／`UNKNOWN`）；每 run 一份 JSONL＋manifest。`frame_state`：`INFERRED`／`NOT_SAMPLED`／`NOT_INFERRED`／`MISSING`；離線產生，查詢時不補推論 | 契約 §4、§10；D63 (d) | #103（產生器）、#102（store 介面）、#118（r004 正式索引）、#114（HSV 參數提案） | ⬜ |
| **Q-3　兩層圖** | Region Connectivity Graph＋Camera Transition Graph；只用核准的 `scene_static`、靜態校正、靜態可見範圍、不含人物的靜態畫面；`TOPOLOGICAL_ONLY` 邊（如 `PORTAL_R102`）不進候選；候選排序用 D28 原鍵 | 契約 §5 | #104（schema／loader、排序）、#116（r004 資料與出口 ROI）、#117（獨立檢查，Claude） | ⬜ |
| **Q-4　Q3 解析** | 自然語言 → 結構化查詢；LLM（本機 Ollama Qwen）輸出 strict schema 驗證，失敗退規則解析器，不猜、不執行；LLM 說明文字附 `cited_refs` | 契約 §7 | #105（provider）、#106（解析） | ⬜ |
| **Q-5　Q1 查詢** | 依條件找相機；類別別名表是封閉人工表；`UNSUPPORTED_CLASS`／`NO_MATCH`／`PARTIAL` 與三種「沒有」分開 | 契約 §6 | #109 | ⬜ |
| **Q-6　Q2／Q4／Q5 找人與切鏡** | 同鏡頭最小 IoU 連接器（暫失觸發）→ Q4 `target_presence` 證據聚合 → Controller 狀態機（`PLAYING`／`TEMP_LOST`／`SEARCHING`／`SWITCHING`／`RETURNED_TO_ORIGIN`／`ENDED`）。模式 `RULE_ONLY`（決定性規則）與 `AGENT_SEQUENTIAL`（Agent 依序看合法 top-k 候選的證據後決定，超限由規則兜底） | 契約 §8 | #107、#108、#110、#111 | ⬜ |
| **Q-7　HTTP 端點** | Q 線端點與 #80 的接線（R-1–R-7） | 設計 #90 §2.4；契約 §2.3 | #112 | ⬜ |
| **Q-8　工作台** | `frontend/workbench-v2/`：Q 資料層、Q3 查詢列與 Q1 結果牆、Q2 主畫面／時間軸／Q4 證據／Q5 逐步紀錄、審核模式 | 設計 #90 | #119–#122（Claude） | 外框、api、player-grid ✅（#74、#79、#71）；Q 線畫面 ⬜ |
| **Q-9　驗證與評估** | 合約符合性測試包、Q4 標註與評估、端到端瀏覽器驗收與 Demo 腳本 | INDEX §3 | #99（#127）、#123、#124 | 測試包 🟡（PR #127 v0.2.1，綁 `3873ff2`，未合併） |

共通回應欄位（契約 §2.3）：`resolved_scope`、`provenance.gt_read: false`、`identity_verdict: "UNCONFIRMED"`、`llm_parse_used`、`agent_attempted`、`agent_used`、`decision_source`、`fallback_used`／`fallback_reason`、`output_sha256`。

邊界（契約 §1、§9、§10）：

- Agent 與 LLM 只能經 typed tools 讀資料，不能掃檔案、跑 SQL、產生新的鏡頭／區域／觀測 ID；**候選集合與排序由決定性模組產生**，Agent 只在合法 top-k 內決定切不切。
- 第一版不用 PG：圖與參數組是版本化 JSON，偵測索引每 run 一份 JSONL＋manifest／hash（或 SQLite），放在單一 store 介面後面；權重、媒體、`.blend` 不放資料庫。
- 第一版不做：同色干擾、ByteTrack／OSNet／ReID、跨鏡頭身分確認、3D 重現與接地、魚眼／PTZ、VLM、GT 對照、研究級評估。
- 數值門檻：契約 §11 參數組已由 D65 核定為**第一版初值**（綁 `parameter_set` hash，前提索引 5 fps），#126 預算由 D67 當第一版初值；之後只能用 r004 preview 另出新版、由使用者核定。

## 2. 受控場景底座與暫停的 3D 線（L0–L7）

> 這一節記錄 A／B1（r003）受控場景的分層。**3D 線（2b–2d、CS-C、CS-D）暫停保留**；底座中 L0–L1（safe 資料）、L5 後端 loader／媒體權杖、L6 workbench-v2 外框仍是 Q 線的基礎。資料單向往上流：L0 產製 → L1 safe 資料 → L2 感知 → L3 幾何與接地 → L4 推論與檢索 → L5 後端 API → L6 前端；L7 評估在凍結之後，只讀凍結後的預測與 GT。L2–L4 與 L7 對 Q 線**不是前置條件**。
> 狀態欄保留原本的記錄，並依 `mainline/q1q5` @ `9b4c9b1` 更新了 L5、L6（之後合入 `mainline/q1q5` 的 #86、#92、#91 都是文件，不改這些層的狀態）。

### L0　產製端（private，只有 Codex 能碰）

| 項目 | 內容 | 狀態 |
| --- | --- | --- |
| 輸入 | Blender 場景 `controlled_scene_v1_s001_r003.blend`（`manifest.source_sha256` = `6e7de38d…ae6d8e`，D53）、事件腳本、人物產製設定（`persons.sim.json`，private，契約 §3.9） | ✅ |
| 判斷／元件 | Blender 渲染（`rgb/<CAM>/frame_NNNNNN.png`）；靜態唯讀匯出（`Blender --background --disable-autoexec`，只抽明列的 48 個靜態來源與鏡頭，不讀人物／動畫／GT，見 [#68 留言](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6270258238)） | ✅ |
| 產出 | A：3 台鏡頭各 50 張；B1：4 台各 100 張；共 550 張，缺格 0（D55；本機 `ls` 核對 150／400 張） | ✅ |
| 層間 API | 無（檔案）。GT 在 `private_evaluation/<run>/`，凍結前不得被 L1 以上讀取（契約 §7） | ✅ |
| 模型／資料庫 | 無 | — |

### L1　safe 資料層（JSON 檔＋hash，沒有資料庫）

| 項目 | 內容 | 狀態 |
| --- | --- | --- |
| 輸入 | L0 的 r003 safe 匯出 | ✅ |
| 位置 | 資產 repo 的 `data/pilot/controlled_scene_v1/runs/<run_id>/`（被 `.gitignore` 排除，不在 git 內；組員**不需要**取得這批資料；組員工作是資料夾包，見 [TEAM_ONBOARDING](TEAM_ONBOARDING.md)） | ✅ |
| 內容 | `safe_bundle/`：`manifest.json`（allowlist＋各檔 `file_sha256`）、`scene_static.json`、`cameras.json`、`rgb_index.json`（`records[]`／`missing[]`，D57）、`runtime_profile.json`、`body_policy.json`、`rgb_sha256.txt`、`geometry/*.json`（每 run 44 檔）；`rgb/`；`acceptance/`（驗收收據與 validator 報告，正式 loader 不讀） | ✅ |
| 驗證 | E 包 validator v2（#77 @ `7bc345f`）；兩個 run 都 48/48 PASS（D59，[#68](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6271380297)） | ✅ |
| 用途核准 | `objects[]` 42 個、`walkable[]` 6 個全部 `NOT_EVALUATED`（PR #81 的第二批整合規格 §2）；D62 O10：先跑 K7 再由使用者核准。核准前遮擋判斷、可見範圍索引、K1 地圖都回 `UNKNOWN`（契約 §3.3、§3.4） | 🟡 |
| `event_*.query.json`、`outputs/`（日後凍結的推論輸出） | 目前 `safe_bundle/` 內**沒有** `event_*.query.json` 與 `outputs/`（`ls` 核對）；但 #75 的 loader `REQUIRED_FILES` 含 `event_query`。如何銜接：`UNKNOWN`（待 Codex 說明） | ⬜／`UNKNOWN` |
| 模型／資料庫／API | 無 | — |

### L2　感知（只讀 RGB；傳統影像處理，沒有神經網路）

| 項目 | 內容 | 狀態 |
| --- | --- | --- |
| 輸入 | `rgb/` 影格 | ✅ |
| 判斷／元件 | `src/amidst/engineering/perception_v2.py`：時序中位數背景 → 前景差分 → 元件 → bbox → 腳點像素（bbox 底部中央）→ 品質旗標與像素敏感度。對 A／B1 尚未執行 | 🟡 |
| 局部追蹤 | 2b（Codex）；缺口最多 1 格（D56 Q15）。**暫停**（D63）；Q 線改用同鏡頭最小 IoU 連接器（契約 §8.2，#107） | ⬜ |
| 外部視覺判斷 | 欄位保留、v1 固定 `NOT_USED`（D61；契約 v1.2 草案）。日後可能接 OpenAI 視覺判斷，需另行決策與契約 §7 的外部 API 授權（D47） | ⬜ |
| 模型 | 無神經網路模型。不串入姿態模型（D61） | — |

### L3　幾何與接地

| 項目 | 內容 | 狀態 |
| --- | --- | --- |
| 元件 | `src/amidst/geometry/inverse_projection.py`（像素射線與地板求交）；`src/amidst/engineering/hybrid_contact.py`（C4a：腳點像素帶、頭部射線、身高先驗 → `ground_estimate`，`PROJECTED_OBSERVATION`）；`composed_ground`（D44：軌跡身高、靜態遮擋、速度界，契約 §6.3.1）；`src/amidst/evaluation/map_verification.py`（K7 地圖驗證） | `inverse_projection` ✅；C4a 🟡（舊 Office run 可跑，A／B1 接入屬 2b）；`composed_ground` ⬜；K7 對 r003 進行中，結果 `UNKNOWN` |
| 層間 | 輸出為契約 §3.12／§6.3 的 `ground_estimate`／`composed_ground`；證據狀態 `INFERRED_CONSTRAINED`（D62 O5）；v1 一律 `SEGMENT`（D62 O6） | ⬜ |
| 資料庫 | 無 | — |

### L4　推論與檢索

| 項目 | 內容 | 狀態 |
| --- | --- | --- |
| 檢索 | `src/amidst/workbench/frame_retrieval.py`（TimeFrameIndex）✅；`src/amidst/geometry/floor_visibility_index.py`（新鏡頭的索引未建，`run_bindings[].visibility_index_ref` 目前為 `null`，2c） | ✅／🟡 |
| 候選鏡頭排序 | `relation_tier → overlap_area_m2_desc → camera_id`，不用偵測數（D28、v1.1 §6.1）；通路用拓撲定義（D62 O11）。3D 線的 2c **暫停**；Q 線的候選排序見 §1 的 Q-3（契約 §5.4，#104） | ⬜ |
| 盲區假設 | `src/amidst/blind_hypothesis/`：K1 `engine.py`、`pruning.py`、`candidate_screen.py`（K8c）、`floor_map.py` 等 | ✅（純模組） |
| 整合 | `src/amidst/workbench/blind_hypothesis_integration.py`（C4b）；新事件 adapter 為 2d；端點先只用 `ground_estimate`（D62 O12） | 🟡／⬜（2d） |
| 跨鏡頭候選 | 身份一律 `UNCONFIRMED`；v1 不確認身份 | ⬜ |
| 3D 物理曲線 | CS-D 方向（D56 Q12），不是現在要實作的 API（D60 範圍） | ⬜ |
| 模型／資料庫 | 無 | — |

### L5　後端（Python WSGI）

| 項目 | 內容 | 狀態 |
| --- | --- | --- |
| 程式 | #75（`codex/controlled-scene-backend`）：`controlled_scene_{api,data,static,evaluation}.py`、`scripts/controlled_scene_backend.py`（`--fixture` SYNTHETIC 模式）；#80（2a，`codex/controlled-scene-real-v2-2a`）：`controlled_scene_rgb_{api,data}.py`。**兩者都已合入 `mainline/q1q5`**（merge commit #75 `4f193e6`、#80 `052abb1`；原審查「需修改」之後的修正含在內，本文未重跑測試）。Q 線端點與 #80 的接線是 #112（R-1–R-7），尚未做 | ✅（底座）／🟡（只有舊 A／B1 素材） |
| 端點（層間 API，形狀見契約 §6、PR #81 的第二批整合規格 §2） | `GET /api/bootstrap?surface=workbench-v2`；`POST /api/session`、`/api/synced_frames`、`/api/candidate_cameras`、`/api/person_layer`、`/api/curve_layer`、`/api/evidence_lookup`；`GET /api/controlled_rgb?token=…`（#80；媒體網址欄位 `media_url`，D62 O8） | bootstrap／session／synced_frames／媒體：#80 有真實資料（待複審）；其餘 fixture 骨架，真實資料回 503 |
| 共通回應 | `resolved_scope`、`provenance.gt_read: false`、`output_sha256`、`identity_verdict: "UNCONFIRMED"`、`agent_used: false`（契約 §6）；完整性錯誤 409 fail closed（§2.3）；缺必要輸入 503 | — |
| 資料庫 | 新場景：無（safe JSON＋hash）。fixture 模式用暫存 SQLite（`ReviewStore`）。舊工作台另有 SQLite／PostgreSQL（`local_storage`、`product`），與新 Demo 無關 | — |
| 模型／Agent | **3D 線**的查找不用 Agent（D56 Q18）。**Q 線**：Q3 解析與說明用本機 Ollama 的 Qwen（文字模型，不看影像）；Q5 的 `AGENT_SEQUENTIAL` 在 D64 例外內（規則 PR #125 合併前不得啟用；D67：Codex 審查通過後由協調者合併）。模型 tag 與 digest 由回應記錄；契約範例寫 `qwen2.5:7b-instruct`，**實際使用的模型與埠：`UNKNOWN`**（尚未實作）。舊 Agent 程式在 `src/amidst/local_agent/`，Q 線不啟動它（契約 §10） | ⬜ |
| 舊工作台端點（備援，D35） | `src/amidst/workbench/service.py` 的舊路由；細節 `UNKNOWN`（本文未逐條核對） | ✅ |

### L6　前端（ES module＋three.js）

| 項目 | 內容 | 狀態 |
| --- | --- | --- |
| 新工作台 | `frontend/workbench-v2/`：V2-1 外框（#74）、V2-2 `api.mjs`／`uncertainty.mjs`／SYNTHETIC fixture（#79）、`player-grid`（#71，1／2／4／8 格同步）。**已合入 `mainline/q1q5`**（#74 `7904a48`、#71 `b9c7cfb`、#79 `9b4c9b1`）。3D 線版設計見 `archive/3d-line` 的 `WORKBENCH_V2_DESIGN_20261018.md`（原 #72）；Q1–Q5 版設計是 PR #90 | ✅（外框、api、player-grid）／🟡（只有 SYNTHETIC fixture 與 A／B1） |
| 尚未做 | Q 線畫面（Q 資料層、查詢列、結果牆、時間軸、證據與逐步紀錄、審核模式）= #119–#122；3D 線的 plan-layers、plan-view 等（V2-3～V2-10，原 #81 §4）暫停 | ⬜ |
| 舊工作台 | `frontend/workbench/`，保留當備援，驗收後才改預設（D35） | ✅ |
| three.js | 0.186.1（`frontend/workbench/package.json`）；以 `/vendor/three.module.js` 提供 | ✅ |

### L7　評估（輸出凍結之後，Claude）

| 項目 | 內容 | 狀態 |
| --- | --- | --- |
| 閘門 | 先驗證預測檔 SHA-256，才載入 GT（範例：`src/amidst/evaluation/rq1_ground_interval.py` 的 `load_frozen_predictions`） | ✅（舊 RQ1）／⬜（E1–E5） |
| 目標 | E1–E5（D56 Q19–Q23，見 §3「凍結後評估目標」） | ⬜ |
| 既有工具 | `src/amidst/evaluation/{rq1_ground_interval,metrics,configured}.py`、`src/amidst/engineering/contact_rq1_charts.py` | ✅（舊 Office） |
| 前提 | 輸出凍結（D26）；至今沒有任何新場景輸出被凍結 | ⬜ |

### 旁支（不在 Q1–Q5 主線，歷史）

- 舊 Office Demo launcher：`start-office-demo.command`；舊 Office 人形 run、舊 Demo 步驟（D22–D24）暫停（D25），Q 線不使用。
- K8 合成展示（D23）：暫停（D25），#59 保留。

## 3. 規格總表（底座與暫停的 3D 線）

> 本節是受控場景（A／B1，r003）與 3D 線的規格摘要；影像、時間、缺格、鏡頭的慣例仍是 Q 線的底座，遮擋／接地／誤差／曲線／E1–E5 屬暫停的 3D 線。**Q1–Q5 的規格在 §1 與契約 #86。**

每格只寫重點與出處；數值與欄位請讀出處，不要以本表為準。

### 影像與場景

| 項目 | 規格（重點） | 出處 |
| --- | --- | --- |
| 影像 | 960×540、PNG；5 fps，10 Hz 另開新版，不覆寫 5 fps run | D25；契約 §5.0 |
| 事件與長度 | A：10 s、50 sample、3 台（W1、W2、R102_CTRL）；B1：20 s、100 sample、4 台（加 N1） | D55；契約 §5.2、§5.3 |
| 鏡頭 | 針孔、無畸變；內外參在 `cameras.json` | 契約 §3.7 |
| 地板 | 所有可走地板統一 z=0 | D36 |
| 人物 | 固定 2 人、中性外觀；名義人體與包絡（可見／不可見判定）的尺寸 | D25、D42、D51 |
| B1 時序 | P2 11.0 s 進場；轉角盲窗 3.4 s | D37、D48 |
| 時間 | 半開區間、整數微秒比較、同步容差 1 ms；非整數微秒輸入四捨五入 | 契約 §2；D41；D56 Q14；D62 O9 |
| 影格缺失 | `rgb_index.missing[]` 才是 `MISSING`（v1 原因只有 `RGB_RECORD_ABSENT`）；已 pin 的檔案不存在、hash 不符是完整性錯誤 | 契約 §2.3、§3.11；D57；D62 O7 |

### 影像驗收（CS-B，已通過）

| 項目 | 規格（重點） | 出處 |
| --- | --- | --- |
| 可見性門檻 | 全身＋接地、距邊與人高的像素下限 | D38、D27 |
| 流程 | 模型先篩＋人工看重點格；A1–A4（標記條件、投影比較基準、抽樣、邊界格） | D47、D54；契約 §8.1 |
| validator | 48 條規則；重疊容差以穿透深度判定 | D58、D59；契約 §3.5.1 |
| 範圍限制 | 不含推論正確性、凍結、GT、runtime READY；其餘格只經模型篩選，不能宣稱 550 格都有人工結論 | D59 |

### 遮擋與接地

| 項目 | 規格（重點） | 出處 |
| --- | --- | --- |
| 腳點射線 | C4a 以像素帶射線與地板求交 | 契約 §6.3；D17 |
| 靜態遮擋 | 像素帶與已核准的靜態遮擋幾何相交（含邊緣容差）→ 腳被遮住；未核准用途的幾何不能用 | D56 Q11；契約 §6.3.1、§3.3；D62 O10 |
| 被遮時 | 頭部射線、軌跡身高、速度界組合 | D44；契約 §6.3.1 |
| 軌跡身高 | 同一台鏡頭、連續 local track；最少格數、全距上限、`WHOLE_TRACK` | D56 Q6–Q9 |
| 速度界 | `v_max` 與錨點不鏈接的時間差上限 | D56 Q5、Q12 |
| 追蹤與方向 | tracking 缺口、heading 視窗 | D56 Q15、Q16 |
| 負證據 | 腳＋腰可見且達可偵測像素下限；回傳 `negative_evidence[]` | D21；D62 O2 |
| 姿態模型 | 不串入；外部視覺判斷 v1 `NOT_USED` | D61 |
| 區間型態 | v1 一律 `SEGMENT`；evidence_state `INFERRED_CONSTRAINED` | D62 O5、O6 |

### 誤差與不確定度

| 項目 | 規格（重點） | 出處 |
| --- | --- | --- |
| 必帶欄位 | 每個 `READY` 推論帶六欄 `uncertainty`，缺欄位整個回應 fail closed | D45；契約 §2.4 |
| 分級 | `quality_grade` 依寬度分 HIGH／MEDIUM／LOW（長度、面積、角度各有界線），**不是機率** | D56 Q13 |
| 顯示精度 | 往外進位 | D56 Q24 |
| 凍結前的說法 | 只能稱「設計估計」；文件引用的估計都要附誤差，沒有就寫 `UNKNOWN` | D26、D45 |
| 內插與盲區不確定度 | 一律後端計算，前端只讀 | D62 O13 |
| 身份與物理 | `identity_verdict` 永遠 `UNCONFIRMED`；核准範圍外物理判定 `UNKNOWN` | 契約 §1 |

### 凍結後評估目標（E1–E5，D56 Q19–Q23）

| 編號 | 目標 | 出處 |
| --- | --- | --- |
| E1 | 候選鏡頭召回（另報排序位置） | D56 Q19；契約 §8 |
| E2 | K1 範圍帶涵蓋（長度容差與目標比例） | D56 Q20 |
| E3 | 接地區間涵蓋（整體與 HIGH 的目標、等級單調；另報偏移距離中位數與最大值） | D56 Q21 |
| E4 | 關聯：錯連數與真解是否在候選中（另報候選數） | D56 Q22 |
| E5 | 負證據錯誤剪枝數 | D56 Q23 |

所有 E 項只能在輸出凍結、預測 hash 驗證之後計算（D26）。

### 畫面與介面

| 項目 | 規格（重點） | 出處 |
| --- | --- | --- |
| 2D 同步 | 1／2／4／8 格同步（8 格先用 UI fixture 驗收，`synced_frames` 每次最多 8 台）；內插算出的空間幾何標 `INFERRED_INTERPOLATION`，單純移動播放頭不產生證據狀態 | 契約 §6.2、§2.2、§9 CS-Q13 |
| 3D 人物 | 只顯示由 2D 重現的結果；無 GT 對照圖層 | D46；契約 §7 |
| 人形範圍 | 只有 HIGH 才畫、只畫當下一格；非 HIGH 畫區間條 | D56 Q25 |
| 曲線 | 控制點與缺段處理（CS-D 方向）；曲線 kind 加 `UNKNOWN_GAP`；`constraints_used` 封閉清單 | D56 Q12；D62 O1、O4；契約 §6.4 |
| 假設回應包裝 | 新包裝 `controlled-scene.blind-hypothesis.v1` | D62 O3 |
| 預算與延遲 | `target_polygon` 頂點上限、deadline、批次上限；同步影格與圖層的 LOCAL p95 目標（不達標只記錄） | D56 Q17、Q18、Q26 |
| 視覺與資訊架構 | 深色 token、模式、Demo 7 步 | #72（`WORKBENCH_V2_DESIGN_20261018.md`）；D43 |
| 點擊回溯證據 | `evidence_lookup` | 契約 §6.5 |

## 4. 名詞與證據狀態

| 名詞 | 意思 | 定義處 |
| --- | --- | --- |
| `OBSERVED`／原始觀測 | 曲線圖層中 `kind: OBSERVED` 的段落；影格本身是觀測，但其時間是 `timestamp_s`，不是播放頭時間 `t`。只有 sample 時間點上的資料是觀測 | 契約 §2.2、§6.4 |
| `PROJECTED_OBSERVATION` | 觀測經投影得到的 `evidence_state`（例如 `ground_estimate`：腳點射線與地板的交點／區間）；來自觀測，不含額外假設 | 契約 §3.12、§6.3 |
| `INFERRED_*` | 推論，不是觀測。契約內出現的四種：`INFERRED_CONSTRAINED`（`composed_ground`，D62 O5）、`INFERRED_INTERPOLATION`（跨影格內插的空間幾何）、`INFERRED_HYPOTHESIS`（盲區中的 K1 假設）、`INFERRED_CONNECTOR`（曲線 `kind`，連接同一局部軌跡，其 `evidence_state` 是 `INFERRED_INTERPOLATION`）。完整清單以契約為準；標 `NON_EXECUTABLE_EXCERPT` 的名稱不算已核准（D60） | 契約 §2.2、§6.3、§6.4 |
| `MISSING` | **預期有、但記錄為缺**：只指列在 `rgb_index.missing[]` 的缺格。已 pin 的檔案不見或 hash 不符不是 `MISSING`，是完整性錯誤（409） | 契約 §2.3；D57 |
| `UNKNOWN` | 沒有依據、不能判斷（例如未核准用途的幾何、條件全部失效）。與 `MISSING` 分開 | 契約 §1、§6.3.1 |
| `UNCONFIRMED` | 身份判定永遠是這個值；系統不確認「同一個人」 | 契約 §1 |
| `NOT_EVALUATED` | 靜態物件或 walkable 的用途／可走性尚未核准 | 契約 §3.3、§3.4 |
| `NOT_USED` | 保留欄位但 v1 不啟用（外部視覺判斷，D61） | 契約 v1.2 草案 §6.3.1 |
| 凍結（freeze） | 推論輸出寫成不可變檔案並記錄 SHA-256；之後才可讀 GT 做評估。D26：GT／mask 評估延到凍結後。至今新場景尚無凍結輸出 | D1、D26；契約 §7 |
| safe／private | **safe**：manifest allowlist 內、逐檔驗 `file_sha256` 的檔案，可被推論與工作台讀取。**private**：GT、`persons.sim.json`、產製設定、`private_evaluation/`、`production/`、`.blend`、`review_only/` 等，推論與正式服務不得開啟 | 契約 §3.0、§7 |
| `SYNTHETIC`／fixture | 為開發而造的假資料，畫面必須標示，不得冒充真實 run | 契約 §6；#72 §5.4 |
| `target_presence` | Q4 對「一個候選鏡頭、一段時間窗」的判定，只用偵測索引。封閉清單：`MATCH_STRONG`／`MATCH_WEAK`／`PERSON_COLOR_UNKNOWN`／`PERSON_NO_COLOR_MATCH`／`NO_PERSON_DETECTED`／`PARTIAL_EVIDENCE`／`NOT_EVALUATED`。任何一種都不代表身分；「沒偵測」不等於「目標不在那裡」 | Q 契約 §8.3 |
| `frame_state`（偵測索引） | `INFERRED`／`NOT_SAMPLED`／`NOT_INFERRED`／`MISSING`。「條件不符」是查詢結果，不是索引狀態 | Q 契約 §4 |
| `NO_MATCH`／`PARTIAL`／`UNSUPPORTED_CLASS`（Q1） | `NO_MATCH`：範圍內全部已推論、沒有一格相符（只說「在已推論的影格中沒有找到」）；`PARTIAL`：有鏡頭或時段沒推論、缺格或時間只部分涵蓋；`UNSUPPORTED_CLASS`：類別不在 `class_map` 與別名表。三種「沒有」（條件不符／沒推論／`MISSING` 格）不得合併 | Q 契約 §6.3 |
| `switch_mode`：`RULE_ONLY`／`AGENT_SEQUENTIAL` | 誰提出切鏡動作。候選集合、順序、狀態機與紀錄格式完全相同；`AGENT_SEQUENTIAL` 超限由規則兜底 | Q 契約 §8.1；D64 |
| `agent_attempted`／`agent_used`／`decision_source`／`fallback_*` | Agent 是否曾被呼叫；是否至少一個 Agent 決定被接受；最後一個切鏡決定的來源（`AGENT`／`RULE_FALLBACK`／`RULE_ONLY`／`USER`）；兜底與原因碼 | Q 契約 §2.3、§8.6 |
| 兩層圖 | Region Connectivity Graph（區域連通）＋Camera Transition Graph（鏡頭轉移）；只表示「依配置可能連通」，不是人體通行認證 | Q 契約 §5 |
| `TOPOLOGICAL_ONLY` | 只當拓撲連通的邊（例如 `PORTAL_R102`），不進轉移候選 | Q 契約 §5.4；PR #82 |
| `PROPOSED`／`APPROVED`（參數組） | Q 契約 §11 的參數先是 `PROPOSED`（Codex 提案），使用者核定後才是 `APPROVED`；D65 把 §11 當第一版初值核定（#126 預算由 D67 當初值），其餘未核定的值不得當預設值，未核定時回應不得是 `READY` | Q 契約 §11；G6 ✅（第一版初值） |
| r004 | Q 線用的新場景版本，另存；r003 與 A／B1 的 pin 不變。尚未建檔（D67 只授權建檔與靜態匯出，不授權渲染） | D63 (b)、D67；G5 |
| 設計估計 | 凍結前的估計誤差說法；不是實測誤差 | D26、D45 |
| 盲區／盲窗 | 兩段實際觀測之間的空白。partial 段不稱盲區 | D39 |
| run | 一次產製：A 是 `ctrl-lcorr-s1-a-5fps-v1-r001`、B1 是 `ctrl-lcorr-s1-b1-5fps-v1-r001`；`r003` 指 `.blend` 版本，不是 run 版本 | 契約 §3.10；D53 |

## 5. 文件地圖

Q1–Q5 主線的文件（契約、計畫、設計、測試包、規則例外、預算提案、任務板、檢查點）在 [Q1Q5_COLLABORATION_INDEX §2](Q1Q5_COLLABORATION_INDEX.md)，不在這裡重複。下表是**底座與歷史**文件。

2026-10-20 的整理（[#87](https://github.com/Polalalabear/amidst/issues/87)）：3D 線的 PR（#65、#72、#76、#78、#81）依序合入封存分支 `archive/3d-line`（`6db45a7`）後關閉；其他舊 PR 打 `archive/<head>` tag 後關閉；分支都保留。所以下列「PR #xx」已 **CLOSED（未合入 `mainline/q1q5`）**，要讀檔案用 `git fetch origin archive/3d-line` 後 `git show FETCH_HEAD:<路徑>`，或讀各自的 tag／分支。

| 文件 | 管什麼 | 位置 |
| --- | --- | --- |
| [DECISION_INDEX](DECISION_INDEX.md)、[TEAM_ONBOARDING](TEAM_ONBOARDING.md)、[Q1Q5_COLLABORATION_INDEX](Q1Q5_COLLABORATION_INDEX.md) | 決策查找；組員上手；Q1–Q5 協作索引 | 本 PR（#83） |
| `AGENTS.md`、`CLAUDE.md`、`docs/DEVELOPMENT_RULES.md`（連到 `docs/specs/`） | 角色分工、Git 流程、結果紀錄範本、GT 隔離等總規則 | `mainline/q1q5`。[#91](https://github.com/Polalalabear/amidst/pull/91)（merge `10070eb`）已把 `AGENTS.md` 改成以 `mainline/q1q5` 為整合分支並指向 #93；`CLAUDE.md` 的閱讀順序是否已更新：`UNKNOWN` |
| 受控場景契約 v1.1 `docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md` | 底座的權威規格：schema、API、驗收、GT 隔離、§0.2 使用者決定摘要。Q 契約沿用其部分章節 | 已核准版本 `98451bd`（`git show 98451bd:docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md`，為 `archive/3d-line` 的祖先）；v1.2 草案 `1c9669c`（D61）、`c4b863d`（D62）未核准 |
| 工作台 v2 設計（3D 線版）`docs/agents/WORKBENCH_V2_DESIGN_20261018.md` | 功能保留矩陣、資訊架構、視覺規範、模組結構 | `archive/3d-line`（原 PR #72）。Q1–Q5 版設計見 INDEX §2（PR #90） |
| 第二批整合規格 `docs/agents/CONTROLLED_SCENE_BATCH2_INTEGRATION_SPEC_20261020.md` | 2a–2d 後端與 V2-3～V2-10 前端；現況表、O1–O14（D62） | `archive/3d-line`（原 PR #81） |
| 門檻提案 `docs/agents/CONTROLLED_SCENE_THRESHOLDS_PROPOSAL_20261018.md` | 3D 線所有數值門檻的候選與理由（A1–A4、B1–B14、E1–E5、C1–C5）；決定在 D54、D56 | `archive/3d-line`（原 PR #76） |
| 協調者交接（10/18 版） | D1–D55 摘要表、檢查點狀態 | tag `archive/claude/docs-handoff-20261018`（`0d16a43`，原 PR #70；`docs/agents/COORDINATOR_HANDOFF_20261018.md` 不在 `archive/3d-line`） |
| Codex 提案與 B 包設計稿 | `CONTROLLED_SCENE_2D_TO_3D_PROPOSAL_20261018.md`、`CONTROLLED_SCENE_B_DESIGN_20261018.md`、`CONTROLLED_DEMO_PREPARATION_20261018.md` | tag `archive/codex/office-demo-rehearsal-docs`（`812817f`，原 PR #54） |
| 後端交接 | `docs/engineering/CONTROLLED_SCENE_BACKEND_FIRST_BATCH_20261018.md`（#75）、`CONTROLLED_SCENE_BACKEND_BATCH2_20261020.md`（#80，2a） | `mainline/q1q5` |
| Claude 回覆與 UX 草圖 | `CONTROLLED_SCENE_CLAUDE_REPLY_20261018.md`、`CONTROLLED_SCENE_UX_SKETCH_20261018.md`、`CONTROLLED_SCENE_ESTIMATION_QA_20261018.md` | `archive/3d-line`（原 PR #65） |
| 問答紀錄 `docs/qa/` | 使用者問答與導覽索引（78 題） | tag `archive/claude/docs-qa`（`97fae37`，原 PR #73） |
| K7 r003 驗證 | `PORTAL_R102` 只當拓撲連通；O10 的建議，**不是核准** | PR [#82](https://github.com/Polalalabear/amidst/pull/82) `6e689f9`（Draft，base `mainline/q1q5`） |
| E 包 validator v2 | 受控場景 48 條規則 | PR [#77](https://github.com/Polalalabear/amidst/pull/77)（Draft，base `mainline/q1q5`；`7bc345f` 為 D59 時的版本，現 head：`UNKNOWN`） |
| 舊 Office 計畫與任務 | `docs/agents/OFFICE_DEMO_PLAN_20261101.md`、`OFFICE_DEMO_TASKS.md`、`OFFICE_DEMO_MVP.md`、`docs/contracts/OFFICE_*_V1.md` | `mainline/q1q5` 上仍在；**歷史**，D25、D63 後以 Q 契約為準 |
| 舊整合分支 | `claude/office-demo-visualization`（`f481fe0`） | 分支與 tag `archive/office-demo-visualization` 保留；**歷史** |

## 6. 查找方式

- 「這件事誰決定的、現在還算不算數」→ [DECISION_INDEX](DECISION_INDEX.md)，再讀原始留言。
- 「Q1–Q5 這個欄位／端點／驗收怎麼規定」→ 契約 #86（INDEX §2 有固定 SHA）；「底座（A／B1）怎麼規定」→ 本文 §3 指到的 v1.1 章節。
- 「Q1–Q5 各自怎樣算完成、怎麼驗證」→ [Q1Q5_COLLABORATION_INDEX](Q1Q5_COLLABORATION_INDEX.md) §1、§3。
- 「現在做到哪、誰在做」→ [#93 任務板](https://github.com/Polalalabear/amidst/issues/93)、GitHub issue 與 PR 及其留言（實際產出紀錄）。
