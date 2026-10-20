# 系統總覽（受控場景 Demo）

> 日期：2026-10-20。本文是**導覽**，不是規格：不重抄 schema，每個數值或規則都指向 D-編號（見 [DECISION_INDEX](DECISION_INDEX.md)）或契約章節。與原文不一致時，以契約和 GitHub 原始決策留言為準。
> 契約：`docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md` v1.1 @ `98451bd`（D60 已核准）。下文「§x」都指這一版；v1.2 草案只差 D61、D62 的條文，尚未核准。
> 找不到依據的寫 `UNKNOWN`。這份文件**沒有**執行任何程式或推論。

## 0. 先讀這三點

1. **新 Demo 是「受控場景」**（D25）：兩個事件（A 單人直線經過、B1 兩人錯開跨轉角）、960×540／5 fps／PNG、固定 2 人。舊 Office 人形 run 已暫停（D25），舊分支與 PR 保留。
2. **GT 不進推論**：Ground Truth 只在輸出凍結並驗證預測 hash 之後，供評估使用（D1、D26、契約 §7）。目前**沒有凍結任何新場景輸出**，所以所有誤差數字都只能稱「設計估計」。
3. **大部分新程式還在 Draft PR，沒有進整合分支**。整合分支（`claude/office-demo-visualization` @ `f481fe0`）有的是舊 Office 時期的純模組與舊工作台；新場景的契約、後端、`workbench-v2` 都在 Draft PR（見 §4 文件地圖與各層的「位置」欄）。

狀態標記：✅ 已有（整合分支上有程式）　🟡 骨架或部分（程式在 Draft PR，或只對舊 run 能跑）　⬜ 未實作　`UNKNOWN` 找不到依據。

## 1. 分層架構 L0–L7

資料單向往上流：L0 產製 → L1 safe 資料 → L2 感知 → L3 幾何與接地 → L4 推論與檢索 → L5 後端 API → L6 前端；L7 評估在凍結之後，只讀凍結後的預測與 GT。

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
| 位置 | 資產 repo 的 `data/pilot/controlled_scene_v1/runs/<run_id>/`（被 `.gitignore` 排除，不在 git 內；組員取得方式見 [TEAM_ONBOARDING §6](TEAM_ONBOARDING.md)） | ✅ |
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
| 局部追蹤 | 2b（Codex）；缺口最多 1 格（D56 Q15） | ⬜ |
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
| 候選鏡頭排序 | `relation_tier → overlap_area_m2_desc → camera_id`，不用偵測數（D28、契約 §6.1）；通路用拓撲定義（D62 O11） | ⬜（2c） |
| 盲區假設 | `src/amidst/blind_hypothesis/`：K1 `engine.py`、`pruning.py`、`candidate_screen.py`（K8c）、`floor_map.py` 等 | ✅（純模組） |
| 整合 | `src/amidst/workbench/blind_hypothesis_integration.py`（C4b）；新事件 adapter 為 2d；端點先只用 `ground_estimate`（D62 O12） | 🟡／⬜（2d） |
| 跨鏡頭候選 | 身份一律 `UNCONFIRMED`；v1 不確認身份 | ⬜ |
| 3D 物理曲線 | CS-D 方向（D56 Q12），不是現在要實作的 API（D60 範圍） | ⬜ |
| 模型／資料庫 | 無 | — |

### L5　後端（Python WSGI）

| 項目 | 內容 | 狀態 |
| --- | --- | --- |
| 程式 | #75（`codex/controlled-scene-backend`）：`controlled_scene_{api,data,static,evaluation}.py`、`scripts/controlled_scene_backend.py`（`--fixture` SYNTHETIC 模式）；#80（2a，`codex/controlled-scene-real-v2-2a`）：`controlled_scene_rgb_{api,data}.py`。**兩者都是 Draft，未進整合分支，#75 審查為「需修改」** | 🟡 |
| 端點（層間 API，形狀見契約 §6、PR #81 的第二批整合規格 §2） | `GET /api/bootstrap?surface=workbench-v2`；`POST /api/session`、`/api/synced_frames`、`/api/candidate_cameras`、`/api/person_layer`、`/api/curve_layer`、`/api/evidence_lookup`；`GET /api/controlled_rgb?token=…`（#80；媒體網址欄位 `media_url`，D62 O8） | bootstrap／session／synced_frames／媒體：#80 有真實資料（待複審）；其餘 fixture 骨架，真實資料回 503 |
| 共通回應 | `resolved_scope`、`provenance.gt_read: false`、`output_sha256`、`identity_verdict: "UNCONFIRMED"`、`agent_used: false`（契約 §6）；完整性錯誤 409 fail closed（§2.3）；缺必要輸入 503 | — |
| 資料庫 | 新場景：無（safe JSON＋hash）。fixture 模式用暫存 SQLite（`ReviewStore`）。舊工作台另有 SQLite／PostgreSQL（`local_storage`、`product`），與新 Demo 無關 | — |
| 模型／Agent | 新 Demo 的查找不用 Agent（D56 Q18）。舊 Agent 程式在 `src/amidst/local_agent/`；使用的模型名稱與埠：`UNKNOWN`（協調者素材寫 Ollama `qwen2.5:7b-instruct` @ `127.0.0.1:11437`，但在 `src`、`scripts`、`configs`、`frontend` 內 grep 不到） | — |
| 舊工作台端點（備援，D35） | `src/amidst/workbench/service.py` 的舊路由；細節 `UNKNOWN`（本文未逐條核對） | ✅ |

### L6　前端（ES module＋three.js）

| 項目 | 內容 | 狀態 |
| --- | --- | --- |
| 新工作台 | `frontend/workbench-v2/`：V2-1 外框（#74）、V2-2 `api.mjs`／`uncertainty.mjs`／SYNTHETIC fixture（#79）、`player-grid`（#71，1／2／4／8 格同步）。設計見 #72（§6.1 模組結構）。**全部 Draft** | 🟡 |
| 尚未做 | grid-view、plan-layers、plan-view、timeline、query、inspector、demo（V2-3～V2-10，#81 §4） | ⬜ |
| 舊工作台 | `frontend/workbench/`，保留當備援，驗收後才改預設（D35） | ✅ |
| three.js | 0.186.1（`frontend/workbench/package.json`）；以 `/vendor/three.module.js` 提供，見 [TEAM_ONBOARDING §5](TEAM_ONBOARDING.md) | ✅ |

### L7　評估（輸出凍結之後，Claude）

| 項目 | 內容 | 狀態 |
| --- | --- | --- |
| 閘門 | 先驗證預測檔 SHA-256，才載入 GT（範例：`src/amidst/evaluation/rq1_ground_interval.py` 的 `load_frozen_predictions`） | ✅（舊 RQ1）／⬜（E1–E5） |
| 目標 | E1–E5（D56 Q19–Q23，見 §2「凍結後評估目標」） | ⬜ |
| 既有工具 | `src/amidst/evaluation/{rq1_ground_interval,metrics,configured}.py`、`src/amidst/engineering/contact_rq1_charts.py` | ✅（舊 Office） |
| 前提 | 輸出凍結（D26）；至今沒有任何新場景輸出被凍結 | ⬜ |

### 旁支（不在新 Demo 主線）

- 舊 Office Demo launcher：`start-office-demo.command`（R7 待改，#72 §6.4）；舊 Office 人形 run、舊 Demo 步驟（D22–D24）暫停（D25）。
- K8 合成展示（D23）：暫停（D25），#59 保留。

## 2. 規格總表

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

## 3. 名詞與證據狀態

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
| 設計估計 | 凍結前的估計誤差說法；不是實測誤差 | D26、D45 |
| 盲區／盲窗 | 兩段實際觀測之間的空白。partial 段不稱盲區 | D39 |
| run | 一次產製：A 是 `ctrl-lcorr-s1-a-5fps-v1-r001`、B1 是 `ctrl-lcorr-s1-b1-5fps-v1-r001`；`r003` 指 `.blend` 版本，不是 run 版本 | 契約 §3.10；D53 |

## 4. 文件地圖

「位置」欄的分支名稱在 GitHub 上；整合分支沒有的文件，用 `git fetch origin <分支>` 後 `git show origin/<分支>:<路徑>` 讀。PR 皆為 Draft，head 會變動，以 `gh pr view` 為準。

| 文件 | 管什麼 | 位置 |
| --- | --- | --- |
| 本索引的姊妹文件 [DECISION_INDEX](DECISION_INDEX.md)、[TEAM_ONBOARDING](TEAM_ONBOARDING.md) | 決策查找；組員上手 | 本 PR |
| `CLAUDE.md`、`AGENTS.md`、`docs/DEVELOPMENT_RULES.md`（連到 `docs/specs/`） | 角色分工、Git 流程、結果紀錄範本、GT 隔離等總規則 | 整合分支 |
| 受控場景契約 v1.1 `docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md` | **權威規格**：schema、API、驗收、GT 隔離、§0.2 使用者決定摘要 | PR #65（`claude/controlled-scene-a`）；已核准版本 `98451bd`（`git show 98451bd:docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md`）。v1.2 草案 `1c9669c`（D61）、`c4b863d`（D62）；未核准 |
| 工作台 v2 設計 `docs/agents/WORKBENCH_V2_DESIGN_20261018.md` | 功能保留矩陣、資訊架構、視覺規範、模組結構、任務拆分 | PR #72（`claude/workbench-v2-design`） |
| 第二批整合規格 `docs/agents/CONTROLLED_SCENE_BATCH2_INTEGRATION_SPEC_20261020.md` | 2a–2d 後端與 V2-3～V2-10 前端的共同依循；現況表、未決項目 O1–O14（已由 D62 決定） | PR #81（`claude/batch2-integration-spec`） |
| 門檻提案 `docs/agents/CONTROLLED_SCENE_THRESHOLDS_PROPOSAL_20261018.md` | 所有數值門檻的候選與理由（A1–A4、B1–B14、E1–E5、C1–C5）；決定在 D54、D56 | PR #76（`claude/thresholds-proposal`） |
| 協調者交接 `docs/agents/COORDINATOR_HANDOFF_20261018.md` | D1–D55 摘要表、檢查點狀態、子 session 對照表；進度為快照，即時狀態看 issue／PR | PR #70（`claude/docs-handoff-20261018`）；10/17 版在 `claude/docs-handoff-20261017` |
| Codex 提案與 B 包設計稿 | `docs/agents/CONTROLLED_SCENE_2D_TO_3D_PROPOSAL_20261018.md`、`docs/engineering/CONTROLLED_SCENE_B_DESIGN_20261018.md`、`CONTROLLED_DEMO_PREPARATION_20261018.md` | PR #54（`codex/office-demo-rehearsal-docs`） |
| 後端交接 | `docs/engineering/CONTROLLED_SCENE_BACKEND_FIRST_BATCH_20261018.md`（#75）、`CONTROLLED_SCENE_BACKEND_BATCH2_20261020.md`（#80，2a） | `codex/controlled-scene-backend`、`codex/controlled-scene-real-v2-2a` |
| Claude 回覆與 UX 草圖 | `docs/agents/CONTROLLED_SCENE_CLAUDE_REPLY_20261018.md`、`CONTROLLED_SCENE_UX_SKETCH_20261018.md`、`CONTROLLED_SCENE_ESTIMATION_QA_20261018.md` | PR #65 |
| 問答紀錄 `docs/qa/` | 使用者問答與導覽索引（78 題） | PR #73（`claude/docs-qa`） |
| 舊 Office 計畫與任務 | `docs/agents/OFFICE_DEMO_PLAN_20261101.md`、`OFFICE_DEMO_TASKS.md`、`OFFICE_DEMO_MVP.md`、`docs/contracts/OFFICE_*_V1.md` | 整合分支；D25 後以新契約為準，舊契約只在契約 §0.1「沿用」的部分仍適用 |
| 任務與決策的即時狀態 | 檢查點 issue #66–#69（label `checkpoint`）；2b–2d 的任務 issue：`UNKNOWN`（規格在 #81 §3） | GitHub issues、[milestone 1](https://github.com/Polalalabear/amidst/milestone/1) |

## 5. 查找方式

- 「這件事誰決定的、現在還算不算數」→ [DECISION_INDEX](DECISION_INDEX.md)，再讀原始留言。
- 「這個欄位／端點／驗收怎麼規定」→ 本文 §2 指到的契約章節。
- 「現在做到哪、誰在做」→ GitHub issue、Draft PR 與其留言（實際產出紀錄）。
