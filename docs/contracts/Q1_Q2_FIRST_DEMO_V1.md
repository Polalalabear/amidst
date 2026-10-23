# Q1–Q5 第一版 Demo 契約 v1 草案（`Q1_Q2_FIRST_DEMO_V1`）

狀態：**`3873ff2` 已由使用者核准**（D65，[#88 留言](https://github.com/Polalalabear/amidst/issues/88#issuecomment-6291477432)；檔案 bytes SHA-256 `924c4365…8078`），以 merge commit `f62ab72` 合入 `mainline/q1q5`。**本版是釐清版（DRAFT）**：只回答 #127 符合性測試包回報的歧義（§15），不改任何已核准的語意或數值；本版仍要 Codex 確認 SHA、使用者在 #88 核准後才能合併，在那之前以 `3873ff2` 為準。需要新語意決定的項目不在本版定，列在 §14 第 5–8 項。本文所有欄位、端點與工具**都還沒有實作**；#86 核准前不得實作任何產品程式（含 `RULE_ONLY`，§0.3）。

本文的「**定案**」指 Codex 已確認、本文不再當成待決問題；整份契約仍待使用者核准。

- 用途：Codex、Claude 與組員並行開發 Q1–Q5 第一版時的交接依據。資料在模組之間只透過本文的 schema 傳遞。
- 本文標示規則（沿用 [受控場景契約 v1.1](#01-依據固定版本) 的寫法）：
  - **「待約定」**：數值門檻。一律由 Codex 提案、使用者核定，本文不定數字。全部列在 §11 參數表。
  - `UNKNOWN`：沒有依據。
  - `NON_EXECUTABLE_EXCERPT`：範例只示意欄位，不是可執行的 fixture；範例中的數字不是門檻。
- 本文不重抄 v1.1 的條文，只引用章節。引用的 v1.1 一律指 `98451bd` 版（`docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md`，在 #65 分支上）。

| 版本 | Commit | 內容 |
| --- | --- | --- |
| v1 草案 | `20c597c` | 初稿：偵測索引、兩層圖、Q1／Q3／Q2・Q4・Q5、時間對應、共通回應欄位、參數表、待決問題 |
| v1 草案（續） | `258c7e2` | 對齊 Codex 討論稿修訂版（SHA-256 `33a11dab…`）：§5.4 排序改回 D28 原鍵、`agent_used`／`llm_parse_used` 分開、fallback 原因碼、同鏡頭連接器加中心距離與局部片段、時間對應欄位、§10 儲存、§11 加 Codex 提案值欄、§12 對照表 |
| v1 草案（D63 修訂／D64） | `b0a49f0` | §0.2 依 D63 修訂原文校正；Q-01、Q-08 依 D64 已決；Q-02 已解決 |
| v1 草案（Codex 確認／X1） | `1d1e061` | 依 [Codex 19 題回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795) 與 #92 審查 X1：§0.1 改引已提交討論稿；§0.3 去掉「schema 可以先實作」；§5.4 tier 判定順序、面積定義、R102 不自動解除；§8.6 兜底限在 top-k 快照內並加兜底與 session 上限；§8.2 來源格、索引格與缺格時長；§8.3 Q4 混合判定與覆蓋；§8.3／§8.6 切鏡進入觀測不倒退；§4.2 填入實際權重 metadata、`nms.applied: false`；`agent_used` 語意寫死（N6）；§13 依回覆改定案；§11 補提案值與新參數；新增 §14 待使用者決定 |
| v1 草案（Codex 核對 1d1e061） | `3873ff2`（D65 已核准） | 依 [Codex 核對](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6291180958)：§8.2／§8.6／§11 缺格門檻改成 `elapsed_us ≥ link_max_gap_us`、`link_max_gap_samples` 由它導出（`÷ index_interval_us − 1`），寫清 `gap_samples` 含目前失配格與 grid 檢查；§8.3 `NOT_EVALUATED` 移到判定第一、`PARTIAL_EVIDENCE` 要 `evaluated > 0`、空窗不算覆蓋完整；§2.2 定自我導出 ID 的 hash preimage（#127 U21／U22／U24）。提案值不變 |
| v1 釐清（#127） | 本版 | 只釐清、不改語意與數值：#127 回報的 tier 4 標記、tier 窮舉、link 紀錄的空值、`window_truncated_us` 形狀、grid 檢查的鏡頭範圍、U25／U26 的已定部分，以及測試包 6 條推論檢查的判定（逐項見 §15）；需要新決定的 U25 狀態、U11 link 檔、U27 計數、U28 取樣關係列在 §14 第 5–8 項 |

## 0. 依據與決定

### 0.1 依據（固定版本）

| 來源 | 版本 | 用途 |
| --- | --- | --- |
| D63（使用者決定，2026-10-20） | [#65 留言](https://github.com/Polalalabear/amidst/pull/65)、[#81 留言](https://github.com/Polalalabear/amidst/pull/81)，標題「## D63」，2026-10-20T06:44Z | 主線範圍、r004、RT-DETR、HSV 顏色訊號、身分 |
| D63 修訂（使用者決定，2026-10-20） | [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6286155884)、[#81 留言](https://github.com/Polalalabear/amidst/pull/81#issuecomment-6286156319)，標題「## D63 修訂」 | Q1–Q5、Agent 輪詢 top-k 與兜底、不做同色干擾、RT-DETR 權重下載授權 |
| D64（使用者決定，2026-10-20） | [#86 留言](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6286156727)、[#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6286157140)，標題「## D64」 | Q-01 列 Q1–Q5 規則例外；Q-08 第一版只用 RT-DETR＋HSV |
| Codex 討論稿（已提交） | [#92](https://github.com/Polalalabear/amidst/pull/92) @ `80f5ca2`：[`docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md`](https://github.com/Polalalabear/amidst/blob/80f5ca2137f077f359bc0f7587d057ae58bab75a/docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md)，檔案 SHA-256 `958ad267f92f8cea7efcbf142eafd327032c501f92dc0a96c80fe08af49159ef`。它是 `60fa8ef` 的 docs-only 移植（`dce1490`，SHA-256 `666263f449259f2bbe93fd78e6f654e05920d1b45cd50a3ea2f3c0c5444672c6`）再加 D64 對齊 | 兩層圖、流程、提案值（§11）、r004 修改提案、RT-DETR 權重紀錄 |
| Codex 契約審查 | #92 @ `80f5ca2`：[`docs/engineering/Q1_Q5_CONTRACT_REVIEW_20261020.md`](https://github.com/Polalalabear/amidst/blob/80f5ca2137f077f359bc0f7587d057ae58bab75a/docs/engineering/Q1_Q5_CONTRACT_REVIEW_20261020.md)，檔案 SHA-256 `eb48ab86a1f5e517d98ef44834c760e3d752108c6e75bdfceb25dd15907fed57`；§2 與 [#86 留言](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)逐行相同 | Q-01–Q-19 確認、7 項修正、離線索引評估 |
| （歷史）未提交的討論稿 | 初稿依據 SHA-256 `ba9a3170…aa0d`；`258c7e2` 對齊的中間態 SHA-256 `33a11dab…2bec`。兩者都**未提交**，已由上列已提交版取代，只留作版本表的歷史紀錄 | — |
| 受控場景契約 v1.1 | `98451bd` | §2 時間慣例、§2.1 hash、§2.3 缺格、§3.6 門、§3.7 鏡頭、§6.1 候選鏡頭與 D28 排序、§7 GT 隔離 |
| Agent 檢索邊界 | 資產 repo `docs/engineering/AGENT_RETRIEVAL_BOUNDARY.md`，檔案 SHA-256 `3e8fb2ded00ac4010b3c660bba6ef4518d51b72fbe3e0d0c4515d48b8af11743` | Agent 只用 typed tools、有界動作、排序歸決定性服務 |
| K7 r003 靜態幾何驗證 | [#82](https://github.com/Polalalabear/amidst/pull/82) @ `6e689f9`（未合併、未核准） | `PORTAL_R102` 只當拓撲連通 |
| 開發規則 | `docs/specs/DEVELOPMENT_RULES.md` @ `f481fe0` | GT 隔離、Agent 不做幾何與排序；見 §0.3 的衝突 |

本文已逐項對齊已提交的討論稿（§12）；提案值只列在 §11 的「Codex 提案」欄，仍是**待使用者核定**，本文不把它們當成已定值。D63 修訂原文 (f) 已確認權重下載授權（須記錄檔名、來源 URL、大小、授權條款與 SHA-256），Codex 已完成下載並記錄（§4.2、Q-14）。討論稿與 Codex 回覆另說使用者也授權了 A／B1 小批接線測試；D63 修訂原文未提這一項，本文記為 REPORTED。接線結果只證明舊素材上的接線，不是 r004 或 Q1–Q5 的驗收。

### 0.2 D63 與修訂摘要

**D63（已貼出，原文見上表連結）：**
- (a) Q1／Q2 是主線；3D 重現線（#81 的 2b–2d、CS-C／CS-D、#84、#85）暫停保留，不關、不刪。2a（#80）與 workbench-v2 外框照常沿用。
- (b) 場景修改**另存 r004**；r003 與 A／B1 的 pin（D53、D59）不變。紅衣／藍衣只用於 r004 的新 run。
- (c) 原文：LLM 只做語意解析與說明，切鏡由決定性規則決定，`agent_used` 維持 `false`；LLM 選鏡留第二階段，需先修 DEVELOPMENT_RULES。**此項已由下面的修訂取代。**
- (d) 允許在 RT-DETR 人物框上半身做最小 HSV 顏色統計，輸出 `STRONG`／`WEAK`／`NONE`／`UNKNOWN`，記錄方法版本與 hash；身分一律 `UNCONFIRMED`；不導入 ByteTrack／OSNet／ReID。
- 不授權：建 r004、渲染、下載 RT-DETR 權重、合併、凍結、讀 GT、外部 API。（歷史原文保留；其中「下載 RT-DETR 權重」已由下面 D63 修訂 (f) 取代，其餘仍有效。）

**D63 修訂（已貼出，原文見 [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6286155884)、[#81 留言](https://github.com/Polalalabear/amidst/pull/81#issuecomment-6286156319)）：**
- 修改 (c)：改成 Agent 輪詢 top-k，超過上限由演算法兜底，取代原 (c)。候選集合與順序由兩層圖與 D28 決定性產生；Agent 依序向合法 top-k 候選取偵測與顏色證據，判斷是否切鏡；超過輪數或時間上限就改由決定性規則決定（上限由 Codex 提案、使用者核定）；回應標 `agent_used` 與 fallback 原因，並記錄 prompt；排序不交給 Agent。LLM 另負責自然語言解析（Q3）與說明。
- 新增 (e)：第一版不放同色干擾人物，也不列同色歧義的完成條件。
- 新增 (f)：授權 Codex 下載 RT-DETR 權重，須記錄檔名、來源 URL、大小、授權條款與 SHA-256。
- 首要目標是 Q1–Q5，其餘先擺著：
  - **Q1** 依某個條件調出相機。
  - **Q2** 找畫面中某個人。
  - **Q3** 盡可能理解使用者語意。
  - **Q4** 模型以自己的辨識判斷任意鏡頭 2D 畫面是否含目標。
  - **Q5** 目標離開鏡頭時，模型以現有資訊判斷是否切鏡，以維持追蹤。
- 其餘 (a)(b)(d) 不變；「不授權」清單不再包含下載 RT-DETR 權重。
- 修訂原文未指定 Agent 使用的模型；本文的 Qwen（本機 Ollama）取自 Codex 討論稿（§1）。身分一律 `UNCONFIRMED`、GT 不進推論沿用 D63 (d) 與現行規則。

### 0.3 與現行規則的衝突（實作前要先處理）

`docs/specs/DEVELOPMENT_RULES.md` @ `f481fe0` 第 57、62 行寫：Semantic Ranking 在決定性閉環完成後才考慮；基底演算法模式不經 Agent 決策。D63 修訂讓 Agent 決定「是否切到某個合法候選」，雖然不改候選集合與順序，仍屬於 Agent 決策。

**D64 已決（[#86 留言](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6286156727)）：列例外，`AGENT_SEQUENTIAL` 可在 Demo 啟用（規則 PR 合併後生效）。**例外條文見規則 PR [#125](https://github.com/Polalalabear/amidst/pull/125)：候選集合與排序仍由決定性模組產生；Agent 只在合法 top-k 內決定是否切鏡；有輪數與時間上限及決定性兜底；全程記錄 prompt、模型 digest、決策來源與 fallback 原因；GT 仍不得進入 Agent；只適用 Q1–Q5 主線。

本文的處理（Q-01 定案，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)）：
- Q5 定義兩種模式（§8.1）：`RULE_ONLY`（決定性規則，符合現行規則）與 `AGENT_SEQUENTIAL`（D63 修訂）。
- 兩道 gate，依序：
  1. **本契約（#86）經使用者核准前，不寫任何產品程式**，`RULE_ONLY` 也一樣。
  2. **規則 PR #125 經使用者核准合併前，`AGENT_SEQUENTIAL` 不得在 Demo 啟用**；「已提出例外」不等於例外已生效。合併後兩種模式都可在 Demo 啟用。
- 本文不改規則。
- Q3 的 LLM 解析與說明不改排序與候選，D63 (c) 已允許，不受第 2 道 gate 限制（仍受第 1 道）。

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
  - `index_id`、`graph_id`：`<kind>:<scene_revision>:<run_id 或 static>:<hash16>`。`<hash16>` 的 preimage 見本節最後一點（`graph_id` 取 `content_sha256` 前 16 碼；`index_id` 取索引鍵）。
  - `observation_id`：`obs:<index_id 的 hash 段>:<camera_id>:<frame_index>:<det_ordinal>`。同一格內的偵測依 `score` 由大到小、再依 `bbox` 四值由小到大排序後編號。
  - `query_id`、`session_id`、`decision_id`：由正規化請求的 `content_sha256` 導出（同 v1.1 §7 的作法）。
- 換模型、換權重、換顏色方法或換取樣都會產生新的 `index_id`；舊 ID 不回收、不改寫。
- **自我導出 ID 的 hash preimage**（#127 U21、U22、U24；Codex 核對 1d1e061 的提醒）。ID 內嵌的 hash 不能涵蓋 ID 自己，下列 preimage 是唯一做法，後端不得自行選擇。全部用 v1.1 §2.1 的 canonical JSON，計時欄位（`stats`）一律不進：
  - **一般文件**（`graph_id`、`parameter_set_id` 這類 ID 內嵌 `<hash16>` 的文件；U24）：`content_sha256` 的 preimage 是整份文件去掉 `content_sha256` 本身與這份文件自己的 ID 欄位（`graph_id`、`parameter_set_id`）。ID 的 `<hash16>` 是這個 `content_sha256` 的前 16 個小寫十六進位字元。
  - **偵測索引**（U21）：`observation_id` 內嵌索引的 hash 段，逐格紀錄又被 `records_file_sha256` 涵蓋，所以 `index_id` 的 hash 段**不取** manifest 的 `content_sha256`，改取「索引鍵」：manifest 去掉 `index_id`、`content_sha256`、`records_ref`、`records_file_sha256` 之後的 canonical `content_sha256`，取前 16 碼。索引鍵包含 detector、顏色方法、取樣、run、`rgb_index_sha256` 與 `per_camera` 的推論範圍，都在寫逐格紀錄之前就確定。產生順序：推論 → 算索引鍵與 `index_id` → 編 `observation_id` → 寫逐格紀錄 → `records_file_sha256` → manifest 的 `content_sha256`（preimage 是 manifest 去掉 `content_sha256` 與 `index_id`，**含** `records_file_sha256`，所以仍綁定逐格內容）。同一個 `index_id` 出現兩個不同的 `content_sha256`（例如重跑推論結果不同）是 `DataIntegrityError`，不得覆寫。
  - **候選快照**（U22）：`candidate_ref` 是 `cand:<snapshot_hash16>:<rank>`，所以 `candidate_snapshot_sha256` 的 preimage 是快照去掉 `candidate_snapshot_sha256` 本身與每個候選的 `candidate_ref` 之後的 canonical JSON；快照內的候選以 `rank` 識別。`<snapshot_hash16>` 是它的前 16 碼。
  - 引用這些 ID 的其他文件（例如證據摘要的 `evidence_sha256`、決策紀錄的 `content_sha256`）照常把 ID 字串算進自己的 hash，不構成循環。

### 2.3 共通回應欄位

Q1、Q2、Q3 的每個回應都帶以下欄位；Q5 沒有獨立回應，它的每筆決策紀錄（§8.7）帶 `fallback_reason`、`decided_by`（回應層的 `agent_used`、`decision_source` 由它導出）與 hash 欄位（`NON_EXECUTABLE_EXCERPT`）：

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
  "llm_parse_used": false,
  "agent_attempted": false,
  "agent_used": false,
  "decision_source": "RULE_ONLY",
  "fallback_used": false,
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
| `llm_parse_used` | 這個回應所依據的結構化查詢，是否採用了 Q3 的 LLM 解析結果（§7.3）。**不影響 `agent_used`** |
| `agent_attempted` | Q5 的 Agent 是否曾被呼叫（含逾時、格式錯誤） |
| `agent_used` | **只指 Q5 切鏡 Agent**，判定只有一條：session 中**至少一個** `submit_decision` 被 Controller 接受（`SWITCH`、`NEXT_CANDIDATE` 或 `RETURN_TO_ORIGIN`），也就是至少一步 `decided_by: AGENT` 而且 `accepted: true`。Agent 有決定被接受之後才兜底時仍是 `true`，同時 `fallback_used: true`，不掩蓋歷程。Agent 只呼叫了工具、取了證據，但沒有任何決定被接受就兜底時，是 `false`（`agent_attempted: true`，工具呼叫照樣記在逐步紀錄）：取證本身不改變控制結果，兜底只重用證據，游標也不會因取證前進。討論稿 §3.2 第 5 點的「有效查證」以本列為準（N6）。Q1、Q3 固定 `false` |
| `decision_source` | 最後一個切鏡決定的來源：`AGENT`、`RULE_FALLBACK`、`RULE_ONLY`、`USER`；沒有切鏡決定時是 `null` |
| `fallback_used`、`fallback_reason` | 原本要用 LLM 或 Agent、最後改用規則時，`fallback_used: true`，`fallback_reason` 填 §8.6 的原因碼（多次兜底時填第一個，全部見逐步紀錄）；沒有兜底時是 `false`／`null` |
| `provenance.gt_read` | 固定 `false`。正式服務讀了 GT 或 private 檔案就是錯誤，不得回應 |
| `provenance.input_refs` | 讀過的索引、圖、參數組與媒體的 ref，不含本機路徑 |
| `stats.latency_ms` | 不進 hash，也不進預填與手動查詢的比較 |
| `output_sha256` | 回應去掉 `output_sha256` 與 `stats` 後的 canonical `content_sha256`（v1.1 §2.1） |

**錯誤碼：**沿用 v1.1 §7 的 `FORBIDDEN_INFERENCE_INPUT`（422）、`FORBIDDEN_DATA_SCOPE`（403）、`DataIntegrityError`。本文新增的原因碼分列在各節。

- **釐清（#127 U25，§15 C6）：**錯誤碼只有上面三個。`GRAPH_NOT_APPROVED`（§5.1）、`PARAMETERS_NOT_APPROVED`（§11）、`PARAMETER_GRID_MISMATCH`（§8.2）是本文新增的**原因碼**，填在回應的 `reason`，回應照常帶本節的共通欄位；它們不是錯誤碼，不另訂 HTTP 狀態或錯誤回應格式。後兩者搭配的 `status` 值沒有寫在條文裡，待 §14 第 5 項決定。

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
  "t0_us": 0,
  "mapping_version": "…",
  "declaration_source": "…",
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
| `t0_us`、`declaration_source` | `t0_us` 是對到 `wall_origin` 的來源時間（整數微秒）。`declaration_source` 記這份設定的出處（哪份設定檔、誰宣告）；不得依事件的到達答案回推時鐘 |
| 換算 | `wall = wall_origin + (source_us − t0_us)`；反向換算後，牆鐘範圍要落在 run 的 `[0, source_duration_us)` 才有來源資料 |

- **同一事件的所有鏡頭共用一個 run 與 clock**（Q-11 定案，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)）。例如 A4、B4 是兩個獨立的 run／clock，各有自己的日期、時區、`wall_origin`、`t0_us` 與 hash。
- 同一個查詢涉及多個 run 時，每個 run 各用自己的對應；結果可以一起顯示，但牆鐘範圍重疊不代表兩個 run 是同一段時間的不同鏡頭，**不得跨 run 串接人物**，也不得把兩個事件當成同一條時間或身分鏈。
- 對應改了，`clock_mapping_sha256` 就變，所有依賴它的 `query_id` 與 `output_sha256` 也跟著變。

### 3.2 牆鐘輸入的解析

- 使用者輸入「下午 1 點到 1:30」時，日期與時區的預設值來自目前選定 run 的 `clock_mapping`（`wall_origin` 的日期與 `timezone`）。預設值要寫進 `resolved_scope.requested_time`，讓使用者看得到。
- run 沒有 `clock_mapping`，或缺日期、時區或起點時，牆鐘查詢回 `CLOCK_MAPPING_MISSING`；不得猜成今天下午。
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
- 產生索引是離線批次；Q1–Q5 只讀索引，**查詢時不補推論**（Q-07 定案，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)）。查詢遇到 `NOT_INFERRED` 照實回報。重新產生索引是另一次有版本、hash 與授權的離線工作，不能藏在 GET 或查詢裡。

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
    "variant": "rtdetr_r18vd_dec3_6x_coco_from_paddle",
    "framework": "torch", "framework_version": "2.6.0", "torchvision_version": "0.21.0",
    "code_source": {"repo": "lyuwenyu/RT-DETR", "commit": "df2a96c8c3a098567a1149bf0248da6efe6d495d"},
    "weights_file": "rtdetr_r18vd_dec3_6x_coco_from_paddle.pth",
    "weights_file_bytes": 81001853,
    "weights_file_sha256": "3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0",
    "weights_source": "https://github.com/lyuwenyu/storage/releases/download/v0.1/rtdetr_r18vd_dec3_6x_coco_from_paddle.pth",
    "weights_license": {"code": "Apache-2.0", "training_data_terms": "UNKNOWN"},
    "load": {"strict": true, "num_classes": 80},
    "config_sha256": "…",
    "class_map": {"version": "coco80-v1", "num_classes": 80, "source_file_sha256": "4d5b85566bbf29bf245e74fdca34e44b4c3a36d144f6679ba81ca2803bb15431", "content_sha256": "…"},
    "input_preprocess": {"resize_policy": "PIL_BILINEAR_STRETCH", "input_size_px": [640, 640], "color": "RGB", "scale": "1/255", "dtype": "FP32"},
    "postprocess": {"top_k_queries": 300},
    "index_score_floor": "待約定",
    "nms": {"applied": false, "iou": null},
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
| `detector.variant` | 實際的 RT-DETR 型號與權重名稱。範例是 Codex 已下載並記 hash 的官方 PyTorch R18 COCO 權重（討論稿 §8） |
| `detector.weights_*`、`code_source`、`load` | 範例填的是 Codex 已下載並記錄的實際值（Q-14 定案，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)；討論稿 §8）。`weights_file_sha256` 必填，缺了就不得產生索引；`load.strict` 必須是 `true`，類別數必須和權重的分類 head 與實際輸出維度一致。上游沒有公布 digest，hash 是本機實測值 |
| `weights_license` | `code` 是官方程式庫的授權。COCO 訓練資料的條款沒有審過，記 `UNKNOWN`；第一版不散布權重 |
| `class_map.source_file_sha256` 與 `content_sha256` | 兩者不同：前者是官方配套類別表**來源檔**的 bytes hash；後者是本文 canonical class map JSON 的 `content_sha256`（v1.1 §2.1），要等正式 `detector_config` 產生後才有，**不得拿來源檔 hash 代替** |
| `nms` | smoke 沿官方 top-300 後處理，**不另做 NMS**，所以 `applied: false`、`iou: null`。正式索引若要加 NMS，是新的 `detector_config` 與新的 `index_id` |
| `input_preprocess` | 範例是 smoke 的設定（960×540 拉伸到 640×640）。正式值寫在 `detector_config`，`config_sha256` 綁定 |
| `detector.class_map` | 模型實際的類別表，取自**所用權重的配套設定與輸出維度**，不得拿通用 COCO 清單代替。Q1 能查的類別只來自這張表加上 §6.2 的別名表 |
| `index_score_floor` | 低於這個分數的偵測不寫入索引。查詢端另有 `query_min_score`（§6.1），兩者分開。smoke 報表用的 0.30 **不是提案值**，也不是門檻 |
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

**來源格與索引格（Codex 修正第 4 項）：**`sampling.per_camera[]` 每台鏡頭另記下列欄位：

| 欄位 | 意思 |
| --- | --- |
| `source_frame_interval_us` | 來源格的間隔，由 run 的 fps 決定（例如 5 fps 是 200000） |
| `stride_samples` | 每幾個來源格取一格 |
| `index_interval_us` | `stride_samples × source_frame_interval_us`，也就是索引格的間隔 |
| `index_grid_origin_frame` | 索引格的第一個 `frame_index` |

- **索引格**是 `frame_index = index_grid_origin_frame + n × stride_samples` 的格；只有索引格是「預期取樣格」。不在索引格上的格是 `NOT_SAMPLED`。
- 索引格上的格只能是 `INFERRED`、`NOT_INFERRED` 或 `MISSING`，不得是 `NOT_SAMPLED`；否則是 `DataIntegrityError`。
- `index_interval_us` 變了，就是新的 `index_id`；依賴缺格時長的參數組要跟著重驗（§8.2）。

## 5. 兩層圖

### 5.1 共通規則

**可用的輸入（只有這四類）：**
1. `scene_static` 中 `approval_status: APPROVED`、而且 `allowed_purposes` 含對應用途的靜態幾何（v1.1 §3.3、§7）。
2. 靜態光學校正（v1.1 §3.7）。
3. 只用不含人物的靜態場景建的可見範圍索引（v1.1 §7「靜態索引」）。
4. 不含人物的靜態畫面（`static_frame_ref`，附 `file_sha256`），用來人工標出口 ROI。

**禁止的輸入：**事件腳本、作者路線、`persons.sim.json`、`event_*.validation.json`、GT、mask、depth、visibility、任何含人物的 RGB、偵測索引。**不得在事件 RGB 上標出口或入口 ROI。**兩層圖**不存任何人物的實際下一站或到達時間**。

**先定圖、後看證據：**兩層圖要在檢查事件證據之前定版。之後若要修圖，另出新版並記理由，重新檢查；不得依答案改圖。

**版本與 hash：**每張圖有 `graph_id`、`content_sha256`、`inputs[]`（每個輸入的 ref 與 hash）、作者、`approval_status`（`DRAFT`、`APPROVED`）與核准來源。r003 的 O10 用途核准尚未完成（K7 #82 只是建議）；r004 改過的幾何與鏡頭要重新做用途審查，不得沿用 r003 的核准字樣。圖要在最終鏡頭配置固定後重建；r004 改了鏡頭或門，圖就要改版。

**誰做、誰查、誰核准（Q-15 定案，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)）：**Codex 產生圖與 ROI，Claude 獨立檢查，使用者核准。r004 的幾何與鏡頭固定後，對受影響的靜態範圍重做 K7 類型的檢查，保留方法、source、calibration、static frame 與圖的 hash。O10 用途核准完成前，圖只能是 `DRAFT`。r003 的檢查收據不得直接當成 r004 的依據。

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
| `traversability` | `APPROVED_WALKABLE`：門與兩側 walk 都經核准可通行。`TOPOLOGICAL_ONLY`：只表示拓撲相連，不保證人可通過。依 K7（#82），r003 的 `PORTAL_R102` 屬於後者。第一版依使用者指示，r004 的 `PORTAL_R102` 也維持 `TOPOLOGICAL_ONLY`；r004 要重新驗證，但**驗證結果不能自動解除這個限制**，解除要使用者另行明確決定（Q-04 定案，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)）。`TOPOLOGICAL_ONLY` 的邊不得用於路線、路徑長度或可通行證明 |

LLM 與 Agent 不得新增、刪除或改變任何邊；門的狀態未知時不能自行補通路。

**釐清（#127 U08，§15 C2）：**
- `traversability` 的封閉清單只有上表兩個值。沒有核准可通行的邊一律是 `TOPOLOGICAL_ONLY`（它的意思就是「只知道拓撲相連，通行性未核准」，與 §1「核准範圍以外的通行性一律 `UNKNOWN`」一致），不另設 `UNKNOWN`。
- `CLOSED` 的邊不進搜尋，所以 Camera Graph 的 `transitions[].edge_path` 不會含 `CLOSED` 的邊（§5.4 第 2 步「`CLOSED` 的邊已排除」指的就是這件事）。萬一含了，那條轉移照樣不進候選，不進 tier 判定。

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
     "ranking_area_m2": null,
     "ranking_area_refs": ["…"],
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
| `relation` | `OVERLAP`：兩台鏡頭在核准的可見範圍內有共同區域。`BLIND_GAP`：經過沒有鏡頭的區域才到。`UNKNOWN`：這條轉移需要的鏡頭涵蓋、可見範圍或出口資料缺失，算不出前兩者（§5.4 tier 4）。由圖與可見範圍算出，不由人物事件決定；資料缺失時不得猜成 `OVERLAP` 或 `BLIND_GAP`。`UNKNOWN` 是本版補上的封閉清單值（釐清 #127，§15 C1；依據：#92 討論稿 §3.2 第 1 點「關係／面積缺件保持 `UNKNOWN`」與 §12 對照表該列） |
| `path_traversability` | 路徑上最弱的一段：任一邊是 `TOPOLOGICAL_ONLY`，整條就是 `TOPOLOGICAL_ONLY` |
| `ranking_area_m2`、`ranking_area_refs` | §5.4 排序用的面積（m²）與它的幾何、校正、可見範圍 refs。只從核准的靜態幾何與靜態可見範圍算，算不出就是 `null`。`ranking_area_m2` 不是 `null` 時，`ranking_area_refs` 必須非空（§5.4「附 `ranking_area_refs`」；§15 C7-3） |
| `nominal_path_length_m` | 只有核准的 walkable 幾何能算時才填，否則 `null`；不讀人物路線 |

不是世界座標最近的鏡頭就相連；轉移只來自 Region Graph 的連通加上鏡頭涵蓋。

### 5.4 候選鏡頭的產生與排序（兩層圖＋D28）

決定性服務 `transition_candidates` 依下列步驟產生 Q5 的候選，Agent 與 LLM 都不能改：

1. **出口判定**：用目標最後一筆連接上的觀測（§8.2）的 bbox，對 `from_camera` 的 `exit_zones` 做判定。Codex 提案第一版用 **bbox 底邊中點落在 ROI 內**（Q-06，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)；PROPOSED，待使用者核定，精確邊界規則見 §11）。底邊中點只是 2D 框的代理點，不是腳點、世界座標或人體接地。ROI 優先在不含人物的靜態畫面上人工標記，附校正、靜態影像、方法版本與 hash；經核准的純靜態校正投影也可以。
   - 剛好命中一個出口：用該出口。
   - 命中零個或多個：用該鏡頭**全部**出口，`exit_resolution: AMBIGUOUS`，不強選一個。
2. **展開**：取出這些出口對應的 `transitions`。`CLOSED` 的邊已排除；含 `UNKNOWN` 狀態邊的轉移保留，但標 `path_has_unknown_state: true`（Q-04 定案）。
3. **排序（D28 原鍵，Q-03 定案，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)）**：沿用 v1.1 §6.1 的 `relation_tier → overlap_area_m2_desc → camera_id`，Camera Graph 只決定哪些轉移合法。轉移版本的對應：

   | 鍵 | 本文的值 |
   | --- | --- |
   | `relation_tier` | 依下面的判定順序，**先符合的層就是答案**，不往後比 |
   | `overlap_area_m2` | 取轉移的 `ranking_area_m2`。`OVERLAP`：兩台鏡頭在核准靜態可見範圍內的共同可見面積。`BLIND_GAP`：**目標入口區域 ∩ 目標鏡頭核准靜態可見範圍**的面積。單位 m²，附 `ranking_area_refs`。不是整台鏡頭的可見面積、像素 ROI 面積或任何事件框面積。缺值是 `null`，在同一層內排最後 |
   | `camera_id` | 字典序 |

   `relation_tier` 判定順序：
   1. 鏡頭的涵蓋、可見範圍或出口資料缺失 → **4**。
   2. 否則，路徑含 `state: UNKNOWN` 的邊 → **3**。即使 `relation` 是 `OVERLAP` 也是 3，不升回 1。
   3. 否則，`relation: OVERLAP` → **1**。
   4. 否則，`relation: BLIND_GAP`，而且路徑全部 `OPEN` 與 `APPROVED_WALKABLE` → **2**。

   含 `TOPOLOGICAL_ONLY` 邊的轉移在這之前就排除了（見下）。面積與 tier 都不得依事件 RGB 回頭調圖。

   **釐清（#127 U08，§15 C1、C2）：**
   - 第 1 步的「資料缺失」就是轉移的 `relation: UNKNOWN`（§5.3）；tier 4 只看這個值，不另設標記欄位。候選的 `ranking_basis.relation_tier` 記 4。
   - 這四步是窮舉的。進入判定的轉移，路徑上的邊只會是 `APPROVED_WALKABLE`，狀態只會是 `OPEN` 或 `UNKNOWN`：`CLOSED` 的邊不會出現在路徑上（§5.2 釐清），含 `TOPOLOGICAL_ONLY` 邊的轉移已先排除，`traversability` 沒有第三個值。所以「`BLIND_GAP`、沒有 `UNKNOWN` 邊、又不是全部 `OPEN`＋`APPROVED_WALKABLE`」的組合在合規的圖裡不存在；不得自行替它指定 tier。

   - 出口不明時展開的多個出口，候選取聯集；同一台鏡頭出現多次時保留排序最前的那筆，其他轉移列在該候選的 `alternative_transition_ids`。
   - 路徑含 `TOPOLOGICAL_ONLY` 邊的轉移**不進候選**（K7、討論稿 §4.1），但列在回應的 `excluded_transitions`，附原因 `TOPOLOGICAL_ONLY_EDGE`（Q-04 定案）。`state: UNKNOWN` 的邊保留並明示，不代表人可通過。
   - `relation_tier` 4 的鏡頭仍列入，不得當成不相連。
   - **偵測數與顏色不進排序**（D28 原則）；它們只是 §8.3 取到的證據。排序鍵與值要寫進每個候選的 `ranking_basis`。
   - **不加**「出口命中層級」與「區域跳數」作次要鍵（Q-03 定案）。每個候選的 `ranking_basis` 列出實際用到的三個鍵值。
4. **截斷**：取前 `top_k`（待約定）個，`candidate_set_complete` 與 `truncated` 的意思同 v1.1 §6.1。被截掉的候選要列數量，不得當成「不可能」。
5. **快照**：輸出 `candidate_snapshot_sha256`（preimage 不含 `candidate_ref`，見 §2.2）。Agent 的每個選擇都要引用這個快照。

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
  "resolved_scope": {}, "identity_verdict": "UNCONFIRMED", "llm_parse_used": false, "agent_attempted": false, "agent_used": false, "decision_source": null, "fallback_used": false, "fallback_reason": null,
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
5. 驗證成功就直接執行（Q-09 定案，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)）；UI 一律顯示組出來的結構化查詢，使用者可修改後重查。含糊、缺時鐘或不支援的條件先回明確狀態，不猜、不執行。

驗證失敗時可以重問 LLM，次數上限 `q3_max_llm_attempts`（待約定）；每次呼叫有逾時 `q3_llm_timeout_ms`（待約定）。

### 7.3 失敗與兜底

| 狀況 | 處理 | `llm_parse_used` | `fallback_reason` |
| --- | --- | --- | --- |
| LLM 輸出通過驗證並被採用 | 執行 | `true` | `null` |
| LLM 不可用、逾時或重試後仍驗證失敗 | 改用規則式解析器（關鍵字＋別名表＋時間正則）；UI 標示「規則解析」 | `false` | `PROVIDER_UNAVAILABLE`、`PROVIDER_TIMEOUT`、`INVALID_RESPONSE` |
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
  "resolved_scope": {}, "identity_verdict": "UNCONFIRMED", "llm_parse_used": true, "agent_attempted": false, "agent_used": false, "decision_source": null, "fallback_used": false, "fallback_reason": null,
  "provenance": {"producer": "q3-parser", "gt_read": false}, "output_sha256": "…"
}
```

`status` 封閉清單：`PARSED`、`NEEDS_CLARIFICATION`、`UNSUPPORTED_CLASS`、`UNSUPPORTED_CONDITION`、`PARSE_FAILED`、`TIME_EXPRESSION_INVALID`。

### 7.5 LLM 說明文字

- 說明的輸入只有回應中已有的結構化資料（refs、狀態、時間、原因碼）。
- 輸出要附 `cited_refs[]`；每個 ref 都必須出現在輸入中，否則整段說明丟棄，改用模板說明（`fallback_reason: EXPLANATION_INVALID`）。
- 說明不得引入新事實、不得把 `WEAK` 說成確定、不得說「同一個人」。
- 說明文字不進 `output_sha256`（它可能因模型而變）；它的 `content_sha256` 另外記錄。

### 7.6 prompt 紀錄

每次 LLM 呼叫（Q3、說明、Q5）都記錄：模型 tag、Ollama 回報的 digest、prompt 模板版本與 hash、實際送出的完整 prompt 或 `prompt_ref`＋`prompt_sha256`、取樣參數（temperature、seed 等）、原始輸出與 hash、驗證結果、逾時與延遲。prompt 不得含 §9 禁止的內容與本機路徑。

## 8. Q2／Q4／Q5：找人與切鏡

### 8.1 模式

| `switch_mode` | 誰決定切到哪個候選 | 可用時機 |
| --- | --- | --- |
| `RULE_ONLY` | 決定性規則（§8.6 兜底規則本身） | #86 經使用者核准後（§0.3 第 1 道 gate） |
| `AGENT_SEQUENTIAL` | Agent 依序看合法候選的證據後決定；超限由規則兜底 | D64 已決：列例外，可在 Demo 啟用（規則 PR 合併後生效，§0.3） |

兩種模式的候選集合、順序、狀態機與紀錄格式完全相同，差別只在「誰提出動作」。

### 8.2 同鏡頭最小 IoU 連接器

在同一鏡頭內，把目標從一個取樣格接到下一個取樣格。這不是追蹤模型，不產生身分。

參數（全部「待約定」，寫在參數組 §11）：

| 參數 | 意思 |
| --- | --- |
| `link_iou_min` | 前後兩格 bbox 的 IoU 下限 |
| `link_max_gap_us` | **`SEARCHING` 的觸發門檻**（時長）：目前索引格沒接上，而且它到最後接上的觀測的 `elapsed_us ≥ link_max_gap_us`，就進 `SEARCHING`。核定的是這個值 |
| `link_max_gap_samples` | 最多容許幾個連續**索引格**（§4.4）沒有接上，仍算同一段（`TEMP_LOST`）。**不另外核定**，由 `link_max_gap_us ÷ index_interval_us − 1` 導出；下一個沒接上的格就進 `SEARCHING` |
| `link_min_score` | 參與連接的偵測分數下限 |
| `link_color_rule` | 起始條件有顏色時，下一格的顏色判定要求（例如不得是 `NONE`） |
| `link_ambiguity_margin` | 兩個候選框的 IoU 差小於此值時算歧義 |
| `link_center_dist_max_diag_ratio` | 新框中心與最後匹配框中心的距離，上限是最後框對角線的幾倍 |

規則：
- 只在同一 run、clock、鏡頭的**索引格**（§4.4）上連，只連 `class_label: person`。下一格中 IoU 與中心距離都達標的框，以穩定的一對一匹配選取：IoU 最大者；同值依 `score`，再依 `observation_id`。
- 連上的觀測屬於同一個 `local_segment_id`（範圍為 run＋鏡頭，不跨鏡頭、不跨 run）。超過缺格容忍後再出現的人物框，是新的局部片段，不接回舊 ID。
- 缺格不內插、不補框；中心點不代表世界位置。
- 有歧義時不硬接：該格標 `AMBIGUOUS_LINK`，計入暫失，並把所有候選框記入紀錄。
- 不在索引格上的 `NOT_SAMPLED` 格跳過、不算缺；索引格上的 `NOT_INFERRED` 與 `MISSING` 算沒接上，但原因分開記。
- 每次連接產生一筆 `link` 紀錄：`{prev_observation_id, next_observation_id, iou, elapsed_us, gap_samples, decision: LINKED | NO_CANDIDATE | AMBIGUOUS_LINK | FRAME_NOT_INFERRED | FRAME_MISSING}`。
  - `elapsed_us`：這一格的 `timestamp_us` 減最後接上的觀測的 `timestamp_us`。
  - `gap_samples`：從最後接上的觀測**之後（不含）**到**這一格（含）**為止，沒接上的索引格數。所以 `decision` 不是 `LINKED` 時**含目前這個失配格**，`gap_samples = elapsed_us ÷ index_interval_us`；`decision: LINKED` 時這一格已接上、不算，`gap_samples = elapsed_us ÷ index_interval_us − 1`（緊鄰的下一格接上時是 0）。`NOT_SAMPLED` 格不在索引格上，不算。
  - **釐清（#127 U11，§15 C3）：**`prev_observation_id` 一律是最後接上的觀測。`next_observation_id` 只指「這一格接上的觀測」，`iou` 只指這一對（`prev`、`next`）的 IoU；所以只有 `decision: LINKED` 時兩者有值（`iou ≥ link_iou_min`），其他四種 `decision` 兩者都是 `null`，鍵不省略。`AMBIGUOUS_LINK` 時「所有候選框」另外記，不放進 `next_observation_id`／`iou`。`elapsed_us` 與 `gap_samples` 在五種 `decision` 都照上面的定義填。
  - link 紀錄的 `schema_version`、檔案位置、session 綁定與 `AMBIGUOUS_LINK` 候選框的欄位名，條文沒有定，待 §14 第 6 項決定。
- **缺格判定（Codex 核對 1d1e061 第 4 項）：**每個索引格依序處理：
  1. 這一格接上（`LINKED`）：留在同一段（`TEMP_LOST` 時回 `PLAYING`）。`elapsed_us` 剛好等於 `link_max_gap_us` 的那一格也可以接上，因為它不是失配格。
  2. 沒接上，而且 `gap_samples ≤ link_max_gap_samples`（等價於 `elapsed_us < link_max_gap_us`）：`TEMP_LOST`。
  3. 沒接上，而且 `gap_samples > link_max_gap_samples`（等價於 `elapsed_us ≥ link_max_gap_us`）：進 `SEARCHING`，這一格的 `timestamp_us` 就是 `decision_time_us`（§8.3）。導出的 `link_max_gap_samples` 是 0 時，第一個沒接上的格先記 `TEMP_LOST`，同一格接著進 `SEARCHING`。
  - 兩種寫法在下面的 grid 檢查通過時一定一致；實作用整數 `gap_samples` 判定，`elapsed_us` 照樣記錄供核對。
- **grid 檢查（fail closed）：**下列任一成立就回 `PARAMETER_GRID_MISMATCH`，不得四捨五入、取整或改用最接近的格數。「用到的鏡頭」是這個回應的 `resolved_scope.camera_ids`（§2.3：`resolved_scope` 是實際用到的範圍），不是索引內全部鏡頭；Q2 請求沒有鏡頭過濾，起點可以在任一台、候選也可以是任一台，所以 Q2 的 `resolved_scope.camera_ids` 就是請求的 run 的偵測索引中 `sampling.per_camera` 的全部鏡頭。檢查在找起點之前一次做完；不通過就不找起點、不開 session，不會跑到一半才因切到某台鏡頭而失敗（「回」是回應層的結果，§2.3 釐清；§15 C5）：
  - 某台用到的鏡頭的 `index_interval_us` 不是正整數（例如來源 fps 換算成微秒除不盡），或和參數組的 `applies_to.index_interval_us` 不同（§11）。
  - `link_max_gap_us` 不是 `index_interval_us` 的正整數倍（含小於 `index_interval_us`）。這時 grid 表示不出這個門檻。
  - 參數組另外列了 `link_max_gap_samples`，而它不等於 `link_max_gap_us ÷ index_interval_us − 1`。
- **為什麼門檻是 `(link_max_gap_samples + 1) × index_interval_us`、用 `≥`：**這保留原意「容許 N 個未接格、第 N＋1 個未接格進 `SEARCHING`」，觸發時刻剛好落在索引格上，不會有「等號那一格不觸發」的邊界；§11 已提案的 600000 與 2 也不必改值就能同時成立。另一種寫法（門檻 `= N × index_interval_us`、用 `>`）也自洽，但會把 600000 改成 400000，等於改動提案值，所以不採用。
- **例子（5 fps、stride 1，`index_interval_us` 200000；數值都是 §11 的 PROPOSED）：**最後接上的觀測在 t。t＋0.2 s 沒接上：`gap_samples` 1，`TEMP_LOST`；t＋0.4 s 沒接上：2，仍是 `TEMP_LOST`；t＋0.6 s 沒接上：3 ＞ 2（`elapsed_us` 600000 ≥ 600000），進 `SEARCHING`。如果 t＋0.6 s 那一格接上了，就留在同一段，那筆 `LINKED` 紀錄的 `gap_samples` 是 2。
- **取樣率改變不得默默改變暫失時長**（Codex 修正第 4 項）：參數組核定的是 `link_max_gap_us`；改 `stride_samples` 時 `link_max_gap_samples` 要重新導出，並出新參數組，不能沿用舊格數。例如上面的例子改成 stride 5（`index_interval_us` 1000000）後若仍用「2 格」，暫失會拉長成 3 s，這是不允許的；而 600000 不是 1000000 的整數倍，grid 檢查直接 fail closed，要另外核定新的 `link_max_gap_us`。
- 不得跨未觀測的間隔補框或內插。

### 8.3 Q4：候選畫面是否含目標

Q4 是對一個候選鏡頭、一段時間窗的判定，**只用偵測索引（RT-DETR＋顏色摘要）**。Qwen 是文字模型，不看影像；它只讀這裡的結構化結果。

`target_presence` 封閉清單：

以下「人物框」都指窗內索引格上、`class_label: person`、分數達 `query_min_score` 的偵測。

**覆蓋的計數（Codex 核對 1d1e061 第 5 項）：**窗指候選的 `window_us` 裁掉 `window_truncated_us` 之後的部分。`window_us` 本身是**未裁切**的窗（長度固定是 `search_window_us`，§8.6），`window_truncated_us` 的形狀見 §8.6 釐清。
- 預期索引格數 `N` ＝ 窗內的索引格數（§4.4）＝ `frames.evaluated + frames.not_inferred + frames.missing`。`frames.not_sampled` 只記錄，不算進 `N`。
- `frames.evaluated` 是窗內 `INFERRED` 的索引格數。
- **覆蓋完整**（`coverage_complete: true`）只在 `N > 0` **而且** `evaluated == N` 時成立。
- **空窗**（`N == 0`，例如窗整段被裁掉，或窗內沒有任何索引格）：`coverage_complete: false`，`target_presence` 一律是 `NOT_EVALUATED`。空窗不是「全部推論過」，不得當成覆蓋完整，也不得回 `NO_PERSON_DETECTED`。

| 值 | 條件 |
| --- | --- |
| `NOT_EVALUATED` | `evaluated == 0`：窗內沒有 `INFERRED` 的索引格，包括空窗與「全部是 `NOT_INFERRED`／`MISSING`」。這時不會有人物框 |
| `MATCH_STRONG` | 至少一個人物框的查詢顏色判定是 `STRONG` |
| `MATCH_WEAK` | 沒有 `STRONG`，至少一個是 `WEAK` |
| `PERSON_COLOR_UNKNOWN` | 沒有 `STRONG`、`WEAK`，至少一個是 `UNKNOWN`（其他可以是 `NONE`） |
| `PERSON_NO_COLOR_MATCH` | 有人物框，全部是 `NONE`，**而且覆蓋完整** |
| `NO_PERSON_DETECTED` | 沒有人物框，**而且覆蓋完整** |
| `PARTIAL_EVIDENCE` | `0 < evaluated < N`：覆蓋不完整（有 `NOT_INFERRED` 或 `MISSING`），而且已推論的格只有全 `NONE` 的人物框或沒有人物框。`partial_basis` 填 `PERSON_NO_COLOR_MATCH` 或 `NO_PERSON_DETECTED`，表示已推論部分的情況；其他值的 `partial_basis` 是 `null` |

**判定順序**（Codex 修正第 5 項；Codex 核對 1d1e061 第 5 項把 `NOT_EVALUATED` 移到第一）：由上往下，先符合的就是答案。七個值互斥，每個窗只會落在一個值。
- 先看 `evaluated == 0`：成立就是 `NOT_EVALUATED`，不再往下判定。「窗內全部索引格 `NOT_INFERRED`／`MISSING`、沒有任何 `INFERRED`」只會落在這裡，不會是 `PARTIAL_EVIDENCE`。
- 有 `STRONG` 或 `WEAK` 就記正向支持，覆蓋不完整也一樣；覆蓋另外在 `frames` 與 `coverage_complete` 回報。
- 沒有相符、但仍有 `UNKNOWN` 時，不得當成「全部條件不符」：`NONE` 加 `UNKNOWN` 混合是 `PERSON_COLOR_UNKNOWN`，不是 `PERSON_NO_COLOR_MATCH`。
- 兩種否定結果（`PERSON_NO_COLOR_MATCH`、`NO_PERSON_DETECTED`）只在覆蓋完整時成立。`evaluated > 0`、但因未推論或缺媒體而覆蓋不完整時，一律是 `PARTIAL_EVIDENCE`；`PARTIAL_EVIDENCE` 必須 `evaluated > 0`。不得用沒推論的時段證明目標不在。
- 起始條件沒有顏色時，只有 `MATCH_STRONG`（有人物框）、`NO_PERSON_DETECTED`、`PARTIAL_EVIDENCE`（`partial_basis: NO_PERSON_DETECTED`）、`NOT_EVALUATED` 四種。
- 任何一種都不代表身分；`MATCH_STRONG` 只表示「條件相符的候選觀測」。
- `NO_PERSON_DETECTED` 也不等於「目標不在那裡」。

Q4 的證據摘要（工具回傳，見 §8.4）：

```json
{
  "schema_version": "q-demo.candidate-evidence.v1",
  "candidate_ref": "cand:<snapshot_hash16>:2",
  "camera_id": "CAM_B",
  "window_us": [12000000, 18000000],
  "target_presence": "MATCH_STRONG",
  "frames": {"evaluated": 30, "not_sampled": 0, "not_inferred": 0, "missing": 0},
  "coverage_complete": true,
  "partial_basis": null,
  "decision_time_us": 12600000,
  "entry_observation_id": "…",
  "entry_timestamp_us": 13400000,
  "best_observations": [
    {"observation_id": "…", "frame_ref": "…", "timestamp_us": 13400000, "score": 0.0, "color_verdict": "STRONG", "bbox_xyxy_px": [0, 0, 0, 0]}
  ],
  "matching_observation_count": 6,
  "first_match_us": 13400000,
  "evidence_sha256": "…"
}
```

`best_observations` 最多 `evidence_max_observations`（待約定）筆，依顏色判定強弱、分數、時間、`observation_id` 排序。**這個排序只用於顯示與引用，不決定切到哪一格。**

**證據摘要的釐清（#127 U26 與測試包推論，§15 C7、C8）：**
- `schema_version` 是 `q-demo.candidate-evidence.v1`（§2.2 命名規則）。它是 §8.4 `get_candidate_evidence` 的回應，兜底取證也用同一個形狀；HTTP 端點屬於 #127 U04，本版不定。
- `evidence_sha256`：摘要去掉 `evidence_sha256` 本身與 `stats`（若有）之後的 canonical `content_sha256`（v1.1 §2.1；與 §2.3 `output_sha256` 同一作法）。摘要沒有自我導出的 ID，`candidate_ref` 照常當字串算進去（§2.2 最後一點）。
- `window_us` 等於快照中該候選的 `window_us`（未裁切）。Agent 與兜底都不能改時間窗（§8.4、§8.6 兜底規則第 1 點），所以兩者不同就是錯誤。
- `best_observations` 只從這個窗內的「人物框」（本節開頭的定義）選。因此 `PARTIAL_EVIDENCE` 時每一筆的 `color_verdict` 都是 `NONE`（有 `STRONG`／`WEAK`／`UNKNOWN` 就會先落在前面的值）；起始條件沒有顏色時，`PARTIAL_EVIDENCE` 表示沒有人物框，`best_observations` 是空陣列。
- 起始條件沒有顏色時，`color_verdict` 是 `null`（沒有查詢顏色，就沒有顏色判定；不得填成 `STRONG`）。排序的第一鍵全部相同，由分數、時間、`observation_id` 決定。
- `entry_observation_id` 不是 `null` 時，`target_presence` 一定達到 `switch_min_presence`，因此只會是 `MATCH_STRONG` 或 `MATCH_WEAK`：進入觀測本身就是窗內達到 guard 的人物框。反過來不成立：`target_presence` 達到 guard、但達到的觀測都早於 `decision_time_us` 時，`entry_observation_id` 是 `null`（`NO_ALIGNABLE_OBSERVATION`）。

**切鏡的進入觀測（Codex 修正第 6 項）：**
- `decision_time_us`：這次 `SEARCHING` 開始的來源時間（§8.6）。Agent 與兜底在牆鐘上花的時間不推進來源時間，所以同一快照的重播結果相同。
- `entry_observation_id`：由服務決定性選出，條件全部成立：同一 run 與 clock、在候選的 `window_us` 內、`timestamp_us ≥ decision_time_us`、達到 `switch_min_presence` 的觀測。多筆時取 `timestamp_us` 最早的，再依分數由大到小、`observation_id`。
- 沒有符合的觀測時 `entry_observation_id` 是 `null`。例如目標只在 `decision_time_us` 之前出現在候選鏡頭：這些觀測可以當證據顯示，但不能當進入點，否則播放時間會倒退。
- `entry_timestamp_us` 晚於 `decision_time_us` 時，中間是前方缺口：`timeline` 的 `GAP` 段延伸到 `entry_timestamp_us`，主畫面仍是原鏡頭，UI 標出進入觀測的來源時間，不得把它當成「目前畫面」。

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
| `SWITCH` | 切到 `candidate_ref`，進入點一律是該候選證據的 `entry_observation_id`（§8.3），Agent 不能指定別的觀測 |
| `NEXT_CANDIDATE` | 這個候選不切，游標前進到下一個 |
| `RETURN_TO_ORIGIN` | 不再看候選，維持暫失並顯示原鏡頭（討論稿的「維持暫失」） |

**Controller 拒絕下列選擇**（`accepted: false`，記錄 `rejection_code`，算一輪）：

| `rejection_code` | 狀況 |
| --- | --- |
| `UNKNOWN_REF` | `candidate_ref` 或 `observation_id` 不在快照中 |
| `STALE_SNAPSHOT` | `candidate_snapshot_sha256` 不是目前的快照 |
| `ILLEGAL_ORDER` | `SWITCH` 或 `NEXT_CANDIDATE` 指的候選不是游標所在、已取過證據的那一個 |
| `EVIDENCE_NOT_FETCHED` | 沒先 `get_candidate_evidence` 就要 `SWITCH` 或 `NEXT_CANDIDATE` |
| `INSUFFICIENT_EVIDENCE` | 該候選的 `target_presence` 低於 `switch_min_presence`（待約定，例如只允許 `MATCH_STRONG`，或也允許 `MATCH_WEAK`），或 `entry_observation_id` 是 `null` |
| `UNCITED_OR_FOREIGN_REF` | `cited_observation_ids` 為空，或含不屬於該候選證據的 ref |
| `SCHEMA_INVALID` | 輸出不是合法的 `agent-decision.v1` |

游標規則：取完某個候選的證據後，游標停在該候選，直到 `submit_decision` 被接受；`NEXT_CANDIDATE` 被接受後游標加一。`RETURN_TO_ORIGIN` 不需要先取證據。游標只在快照的前 `top_k` 個候選內移動；走完 `top_k` 個就沒有下一個候選，Controller 結束這次搜尋（§8.6）。

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
| `TEMP_LOST` | 連接器沒接上，但還在 `link_max_gap_samples` 內 | 目前鏡頭；從第一個缺格起標「觀測缺失」，可顯示最後觀測縮圖並標時間 |
| `SEARCHING` | 超過缺格容忍，目標暫失；已產生候選，正在依序取證據與決定 | 原鏡頭；標「暫失／搜尋中」與目前看的候選，以及被排除的候選與原因 |
| `SWITCHING` | 決定已被接受，正在切換（瞬時狀態，只記紀錄） | — |
| `RETURNED_TO_ORIGIN` | 候選都不切或搜尋結束，切回原鏡頭 | 原鏡頭在**目前的來源時間**，不倒轉 |
| `ENDED` | 時間範圍結束、run 結束或使用者停止 | — |

轉移：

| 從 | 條件 | 到 | 紀錄 |
| --- | --- | --- | --- |
| （開始） | 起點已選 | `PLAYING` | `seed` |
| `PLAYING` | 連接器沒接上 | `TEMP_LOST` | `link` 紀錄 |
| `TEMP_LOST` | 在 `link_max_gap_samples` 內重新接上（§8.2 缺格判定第 1 步） | `PLAYING` | `link` 紀錄 |
| `TEMP_LOST` | 沒接上而且 `gap_samples > link_max_gap_samples`，即 `elapsed_us ≥ link_max_gap_us`（§8.2 缺格判定第 3 步） | `SEARCHING` | 出口判定、候選快照 |
| `SEARCHING` | 決定 `SWITCH` 被接受 | `SWITCHING` → `PLAYING`（新鏡頭；起始觀測是 `entry_observation_id`，從 `entry_timestamp_us` 起） | 決策紀錄 |
| `SEARCHING` | top-k 候選全部 `NEXT_CANDIDATE`、決定 `RETURN_TO_ORIGIN`、兜底規則找不到可切的候選，或兜底超過 `fallback_budget_ms` | `RETURNED_TO_ORIGIN` | 決策紀錄；沒取證的候選記 `NOT_EVALUATED` |
| `RETURNED_TO_ORIGIN` | 原鏡頭重新接上 | `PLAYING` | `link` 紀錄 |
| `RETURNED_TO_ORIGIN` | 經過 `research_interval_us`（待約定）仍未接上 | `SEARCHING`（新快照，時間窗往後移） | 新快照 |
| 任何狀態 | 達到 `session_max_research_rounds` 或 `session_max_agent_rounds`（待約定）、時間範圍結束或使用者停止 | `ENDED` | 結束原因 |
| 任何狀態 | `DataIntegrityError`（v1.1 §2.3） | `ENDED`（`reason` 填錯誤碼） | 錯誤；不改標成暫失 |

- 來源時間只往前走；切鏡與回原鏡頭都在同一條來源時間軸上。
- 切鏡由觀測驅動（決定被接受時引用的觀測），不依預先排好的動畫時間表。
- 每個候選的時間窗 `window_us` 從暫失開始時間（第一個沒接上的索引格）算起，長度是固定的 `search_window_us`（待約定）。**第一版不依路徑長度或速度縮窗**（Q-05 定案，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)），也不讀人物腳本速度。
- 時間窗只在同一 run 與 clock、而且有媒體與索引的範圍內；超出的部分裁掉，裁掉的範圍寫進候選的 `window_truncated_us`，不得當成「查過沒有」。
  - **釐清（#127 U05，§15 C4）：**`window_truncated_us` 是半開區間 `[start_us, end_us)` 的陣列（§2.1），依時間排序、不重疊，每段都在 `window_us` 內；沒有裁切時是空陣列 `[]`，不是 `null`。媒體或索引範圍在窗中間有空檔時（例如 `sampled_ranges_us` 有兩段），窗中間也會有裁掉的段，所以是陣列而不是單一區間。寫法與 §4.4 的 `sampled_ranges_us` 相同。
- 決策的來源時刻是 `decision_time_us`（這次 `SEARCHING` 開始的來源時間，§8.3）。切鏡只能進到 `timestamp_us ≥ decision_time_us` 的觀測；切回原鏡頭也在目前的來源時間，不倒轉。

**輪數與時間上限：**

| 參數 | 範圍 | 意思 |
| --- | --- | --- |
| `agent_max_rounds` | 一次 `SEARCHING` | LLM 往返的上限。每次 LLM 呼叫算一輪，不論它要求工具、提交決定、重試或輸出無效 |
| `agent_total_budget_ms` | 一次 `SEARCHING` | 牆鐘總預算，**含證據查取與模型等待**；重試不重置 |
| `agent_call_timeout_ms` | 單次呼叫 | 單次 provider 呼叫逾時 |
| `agent_max_illegal_submissions` | 一次 `SEARCHING` | 被拒的提交（§8.4）累計幾次後直接兜底 |
| `fallback_budget_ms` | 一次兜底 | 兜底取證的牆鐘上限（`RULE_ONLY` 與 Agent 超限後都適用）。超過就停止，剩下的候選記 `NOT_EVALUATED` |
| `session_max_research_rounds` | 整個 session | `SEARCHING` 的次數上限 |
| `session_max_agent_rounds` | 整個 session | 所有 `SEARCHING` 的 LLM 往返累計上限 |

前四項只用於 `AGENT_SEQUENTIAL`；全部「待約定」，Codex 提案值見 §11。兜底能取證的候選數不另設參數：**最多就是快照剩下的 `top_k` 個**。

**兜底規則（`RULE_ONLY` 的規則，也是 `AGENT_SEQUENTIAL` 超限後的規則；有界，Codex 修正第 3 項）：**
1. 只在**同一個快照的前 `top_k` 個候選**、各自已定的 `window_us` 內取證。從游標所在的候選起，依 §5.4 的順序逐一取 §8.3 的證據，到第 `top_k` 個為止；不往快照外、`top_k` 以後或時間窗外找。
2. 第一個 `target_presence` 達到 `switch_min_presence`、而且 `entry_observation_id` 不是 `null` 的候選：`SWITCH`，進入點是 `entry_observation_id`。
3. 沒達到的候選照樣記錄：`PERSON_NO_COLOR_MATCH`（例如明確是藍衣）記排除原因 `CONDITION_MISMATCH`；`MATCH_WEAK`、`PERSON_COLOR_UNKNOWN` 不自動切換，記 `BELOW_SWITCH_GUARD` 並保留為候選；`NOT_EVALUATED`、`PARTIAL_EVIDENCE` 記 `INSUFFICIENT_COVERAGE`；達到 guard 但 `entry_observation_id` 是 `null` 的記 `NO_ALIGNABLE_OBSERVATION`。
4. 都沒有可切的，或超過 `fallback_budget_ms`：`RETURN_TO_ORIGIN`。
5. 沒取證的候選（含超過預算而停下的）記 `NOT_EVALUATED`；`top_k` 以後被截掉的候選照 §5.4 列數量與 `truncated`。**不得因為 top-k 都沒有支持，就宣告「所有鏡頭都查無結果」。**

`switch_min_presence` 未核定前，切鏡 guard 不得宣稱可用：Demo 只能以 `RULE_ONLY` 顯示候選與證據，不自動切換。

兜底接手時，Agent 已被接受的 `NEXT_CANDIDATE` 保留（游標不倒回），已取的證據重用。

**使用者手動改選（Q-18 定案，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)）：**使用者明確手動改選起點或候選時，先終結並保留舊決策，再用新的 `decision_id`、seed 與快照開一次新的 `SEARCHING`，`decided_by: USER`。新的 `SEARCHING` 有自己的 `agent_max_rounds`、`agent_total_budget_ms` 等預算，但**不重置** session 累計上限（`session_max_research_rounds`、`session_max_agent_rounds`）與查詢時間範圍。無效提交或 Agent 重試不得偽裝成手動改選。來源時間不倒退；要回看或跨 run，另開一個查詢。

**`fallback_reason` 封閉清單**（名稱沿用討論稿 §3.2 的提案，再補三個）：`ROUND_LIMIT`（超過 `agent_max_rounds`）、`TIME_BUDGET`（超過 `agent_total_budget_ms`）、`PROVIDER_UNAVAILABLE`、`PROVIDER_TIMEOUT`（單次逾時；本文新增，與總預算分開）、`INVALID_RESPONSE`（輸出不合 schema）、`ILLEGAL_CANDIDATE`（被拒的提交達 `agent_max_illegal_submissions`）、`EXPLANATION_INVALID`（§7.5；本文新增）、`MODE_NOT_AUTHORIZED`（要求 `AGENT_SEQUENTIAL` 但 §0.3 的條件未滿足時，整個 session 用 `RULE_ONLY` 並標此原因）。

**`decided_by`（每一步）：**`AGENT`、`RULE_FALLBACK`（Agent 模式下由規則接手）、`RULE_ONLY`、`USER`（使用者手動選起點或手動改切）。回應層的 `agent_used` 是「有沒有任何一步 `decided_by: AGENT` 且 `accepted: true`」，只取證不算（§2.3）；`decision_source` 是最後一個切鏡決定的 `decided_by`。

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
  "resolved_scope": {}, "identity_verdict": "UNCONFIRMED", "llm_parse_used": false, "agent_attempted": false, "agent_used": false, "decision_source": "RULE_ONLY", "fallback_used": false, "fallback_reason": null,
  "provenance": {"producer": "q2-controller", "gt_read": false}, "output_sha256": "…"
}
```

- `timeline` 依來源時間排序、不重疊、涵蓋整個查詢時段（扣掉 §3.3 沒涵蓋的部分）。
- `GAP` 段的 `position` 一律 `null`：不畫盲區中的位置。
- **釐清（#127 測試包推論，§15 C7-4）：**`entered_by: SWITCH` 的 `ON_CAMERA` 段，`range_us` 的起點等於所引用決策的證據摘要的 `entry_timestamp_us`，`observation_ids` 的第一筆是該決策的 `entry_observation_id`（§8.6 轉移表「起始觀測是 `entry_observation_id`，從 `entry_timestamp_us` 起」、§8.3 前方缺口）。
- `status` 封閉清單：`COMPLETE`（時段走完）、`PARTIAL`（時間只部分涵蓋、索引有缺，或圖未核准）、`NO_SEED`、`ENDED_BY_LIMIT`（達到 `session_max_research_rounds`）、`UNKNOWN`。
- 串起來的片段是「條件相符的候選串接」，UI 與說明都不得寫成「同一個人」。

**逐步紀錄**（`decisions` 檔，每個決策一筆，append-only）：

```json
{
  "schema_version": "q-demo.decision-record.v1",
  "decision_id": "…", "session_id": "…", "step_index": 3,
  "state_before": "SEARCHING", "state_after": "PLAYING",
  "source_time_us": 13400000,
  "decision_time_us": 12600000,
  "switch_mode": "AGENT_SEQUENTIAL",
  "candidate_snapshot_sha256": "…",
  "exit_resolution": "UNIQUE",
  "candidates_considered": [{"candidate_ref": "…", "rank": 1, "evidence_sha256": "…", "target_presence": "PERSON_NO_COLOR_MATCH", "exclusion_reason": "CONDITION_MISMATCH", "action": "NEXT_CANDIDATE", "decided_by": "AGENT"}],
  "tool_calls": [{"tool": "get_candidate_evidence", "request_sha256": "…", "response_sha256": "…"}],
  "llm_calls": [{"model": "…", "model_digest": "…", "prompt_sha256": "…", "prompt_ref": "…", "raw_output_sha256": "…", "validation": "PASS"}],
  "submitted": {"action": "SWITCH", "candidate_ref": "…"},
  "accepted": true, "rejection_code": null,
  "executed_action": "SWITCH", "executed_candidate_ref": "…", "entry_observation_id": "…",
  "decided_by": "AGENT", "fallback_reason": null,
  "rounds_used": 2, "budget_used_ms": 0,
  "content_sha256": "…",
  "stats": {"latency_ms": {"agent": 0, "evidence": 0}}
}
```

- 被拒的提交也要有紀錄（`accepted: false`）。
- **釐清（#127 測試包推論，§15 C7-5）：**每筆紀錄都滿足 `source_time_us ≥ decision_time_us`（§8.6「來源時間只往前走」、切鏡只能進到 `timestamp_us ≥ decision_time_us` 的觀測、切回原鏡頭不倒轉）。條文不要求兩者相等，也不要求其他動作的 `source_time_us` 取特定值；`source_time_us` 的精確定義本版不另定。
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
- **第一版不讀產製路線做驗收**（Q-12 定案，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)）：以 safe RGB、靜態依據與操作紀錄做工程驗收。日後若要讀路線核對（類似 v1.1 §7 D54 A2），要另立隔離的驗收授權，結果不得回填圖、ROI、排序、索引、Agent 或參數。
- **HSV 參數的資料來源**（Q-19 定案，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)）：Codex 提案、Claude 獨立檢查、使用者核定。只用授權後 r004 小批 preview 的 RGB 人物裁切與可見色彩，不讀 actor、材質 ID、事件腳本或 GT；在獨立的 preview 上選參數，凍結方法版本與 hash 之後才產生 Demo 索引，不得看 Demo 答案調參數。現有 A／B1 的白色人形不能決定紅藍衣品質或 HSV 閾值。

## 10. 儲存

**第一版不用 PG**（Q-13 定案，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)）：圖、相機與參數組用版本化 JSON；偵測索引每 run 一份 JSONL＋manifest／hash（優先）或 SQLite，放在單一 store 介面後面；新的 Q3／Q5 經薄 provider 直接呼叫 Ollama，不啟動舊 Agent 初始化，不碰 PG；權重設定指向既有位置，不搬檔。本文的 schema 不依賴哪一種。要求：
- 圖與參數組是版本化 JSON 檔。
- 偵測索引與查詢狀態透過單一 store 介面讀取；介面輸出必須是本文的 schema，與底層儲存無關。
- 媒體、`.blend`、權重不放進資料庫。
- 舊 PG 中的 local-camera-test 資料不是 r004 的模型結果，不得當成本文的索引（Codex 討論稿 §8）。

## 11. 參數表（全部待約定：Codex 提案、使用者核定）

參數組沿用 #76 的「提案 → 使用者核定 → 版本與 hash 綁定」流程（Q-17 定案，[Codex 回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)）。#76 沒有定 Q1–Q5 的參數檔格式，所以格式由本文定，不複製舊研究門檻，也不改舊的 parameter set。本文不給預設值。

`parameter_set.json`（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "q-demo.parameter-set.v1",
  "parameter_set_id": "pset:q-demo:<hash16>",
  "applies_to": {"scene_revision": "r004", "run_ids": ["…"], "detection_index_ids": ["…"], "index_interval_us": 200000},
  "parameters": [
    {"name": "link_max_gap_us", "value": 600000, "unit": "us", "status": "PROPOSED", "proposed_by": "codex", "proposal_ref": "…"}
  ],
  "approval": {"status": "PROPOSED", "approved_by": null, "approval_ref": null},
  "content_sha256": "…"
}
```

- 每個參數都有值、單位、`status`（`PROPOSED` 或 `APPROVED`）與提案出處。`approval.status` 不是 `APPROVED` 時，回應的 `status` 不得是 `READY`／`COMPLETE`，`reason` 填 `PARAMETERS_NOT_APPROVED`（原因碼，不是錯誤碼；§2.3 釐清）。改填哪個 `status` 待 §14 第 5 項。
- `applies_to.index_interval_us` 必須和所用索引中**每一台用到的鏡頭**的 `index_interval_us` 一致（§4.4、§8.2），否則 fail closed（`PARAMETER_GRID_MISMATCH`）。「用到的鏡頭」是回應的 `resolved_scope.camera_ids`（§8.2 grid 檢查的釐清）。`link_max_gap_samples` 可以不列；列出時只是導出值的核對欄，不是另一個核定值（§8.2 grid 檢查）。

「Codex 提案」欄取自已提交的討論稿 §3.2、§3.3 與 Codex 回覆（#92 @ `80f5ca2`），標 **PROPOSED**，未經使用者核定，不得當預設值實作。空白表示還沒有提案。

| 參數 | 單位 | 用在 | Codex 提案（PROPOSED） |
| --- | --- | --- | --- |
| `index_score_floor` | 分數 | §4.2 索引寫入 | 無（smoke 報表的 0.30 不是提案） |
| `nms.iou` | IoU | §4.2 | 不另做 NMS（`applied: false`、`iou: null`），沿官方 top-300；是 smoke 實際設定，正式 `detector_config` 未產生 |
| `stride_samples`（取樣率） | 取樣格數 | §4.2、§4.4 取樣 | 無提案。Codex 只評估了 5、2.5、1 fps 三種情境的離線索引時間；取樣率未核定前，缺格參數不改 |
| 上半身裁切比例 | bbox 高度比例 | §4.3 | |
| `color_crop_min_pixels` | 像素數 | §4.3 `CROP_TOO_SMALL` | |
| `color_truncation_max_ratio` | 比例 | §4.3 `CROP_TRUNCATED` | |
| HSV 各顏色的色相範圍與 S、V 下限 | HSV 值 | §4.3 | |
| `STRONG`／`WEAK` 分界 | 比例 | §4.3 | |
| `query_min_score` | 分數 | §6.1、§8.3 | |
| `segment_merge_gap_us` | 微秒 | §6.3 | |
| `link_iou_min` | IoU | §8.2 | 0.30 |
| `link_center_dist_max_diag_ratio` | 倍 | §8.2 | 0.50 |
| `link_max_gap_us` | 微秒 | §8.2、§8.6 | 600000：`SEARCHING` 觸發門檻（`elapsed_us ≥ 600000`）。5 fps、stride 1 時是第 3 個缺格。只有 `index_interval_us` 整除 600000 時 grid 才表示得出來（§8.2 grid 檢查）；Codex 評估過的 2.5 fps（400000）與 1 fps（1000000）都不整除，選這兩種取樣率時要另提新值 |
| `link_max_gap_samples` | 索引格 | §8.2、§8.6 | 2：**導出值，不另核定**，`600000 ÷ 200000 − 1 = 2`（容許 0.2 s、0.4 s 兩個缺格，0.6 s 的第 3 個缺格進 `SEARCHING`）。換 stride 時由 `link_max_gap_us` 重新導出，不沿用 2 |
| `link_min_score`、`link_color_rule`、`link_ambiguity_margin` | 各自 | §8.2 | 歧義時不強配（無數值） |
| 出口判定規則與門檻 | — | §5.4 | bbox 底邊中點落在 ROI 內；邊界、多出口與零命中保留歧義、展開全部出口（Q-06）。邊界上的點算不算在內，尚無提案 |
| `top_k` | 個 | §5.4 | 3 |
| `search_window_us` | 微秒 | §8.6 | |
| `research_interval_us`、`session_max_research_rounds` | 微秒、次 | §8.6 | |
| `session_max_agent_rounds` | 次 | §8.6 | |
| `fallback_budget_ms` | 毫秒 | §8.6 兜底 | |
| `switch_min_presence` | `MATCH_STRONG` 或 `MATCH_WEAK` | §8.4、§8.6 | `MATCH_STRONG`（`WEAK`、`UNKNOWN` 不自動切換） |
| `evidence_max_observations` | 筆 | §8.3 | |
| `agent_max_rounds` | 次 | §8.6 | 3 |
| `agent_total_budget_ms` | 毫秒 | §8.6 | 5000 |
| `agent_call_timeout_ms` | 毫秒 | §8.6 | 2000 |
| `agent_max_illegal_submissions` | 次 | §8.6 | |
| `q3_max_llm_attempts` | 次 | §7.2 | |
| `q3_llm_timeout_ms` | 毫秒 | §7.2 | 2000 |
| LLM 取樣參數（temperature、seed） | — | §7.6 | |

效能（查詢與切鏡延遲）只量測與記錄，第一版不訂門檻（Codex 討論稿 §11）。離線索引時間的估算見 Codex 契約審查 §4：CPU forward median 1108.41 ms／格；4＋5 台、各 30 s、5 fps 合計 1,350 格約 24.94 min（只算 forward）。這是以舊素材 35 張 smoke 為基礎的估算，鏡頭範圍、時長與 fps 都未核定，不是實測，也不是門檻。

## 12. 與 Codex 討論稿的對照

初稿與 Codex 討論稿初版有三處不同（r003 原地修改、RGB 顏色統計、Qwen 自由建議候選）；修訂版已改成與 D63 一致，這三處不再有差異。下表以已提交的討論稿（#92 @ `80f5ca2`，SHA-256 `958ad267…`）為準；`258c7e2` 對齊的是未提交的中間態（`33a11dab…`），該版已無法取得；本版改對已提交版重新核對下表各列。

| 討論稿位置 | 討論稿內容 | 本文處理 |
| --- | --- | --- |
| §2 | 另存 r004；r003 與 A／B1 pin 不變 | §2.1 以 `scene_revision` 引用 |
| §3.1 | 上半身 HSV 四級；class map 以實際權重為準 | §4.2、§4.3；HSV 參數全部列在 §11，尚無提案值 |
| §3.2 第 1 點 | D28 原鍵；`UNKNOWN` 要有穩定排序與截斷標記 | §5.4：`relation_tier` 4 與 `null` 面積排最後 |
| §3.2 第 2–4 點 | Agent 依序取 top-k 證據；跳序、集合外、虛構 ref 拒絕；兜底只切 `STRONG` | §8.4 拒絕碼、§8.6 兜底規則 |
| §3.2 第 5 點 | `agent_used` 與 `llm_parse_used` 分開；有效查證後兜底仍保留 `agent_used: true`；精確語意由契約定 | §2.3：「有效查證」定為「至少一個決定被接受」，只取證不算（N6） |
| §3.2 末段 | 兜底證據範圍、額外額度與耗時由契約明列，不能變成無界掃描 | §8.6：兜底限在快照的 top-k 內，另有 `fallback_budget_ms` 與 session 上限 |
| §3.2 原因碼提案 | `ROUND_LIMIT`、`TIME_BUDGET`、`PROVIDER_UNAVAILABLE`、`INVALID_RESPONSE`、`ILLEGAL_CANDIDATE` | §8.6 沿用，另加 `PROVIDER_TIMEOUT`、`EXPLANATION_INVALID`、`MODE_NOT_AUTHORIZED` |
| §3.3 | IoU＋中心距離、缺格容忍、歧義不強配、局部 ID | §8.2；數值在 §11「Codex 提案」欄 |
| §4.1 | `PORTAL_R102` 只當拓撲連通，route builder 排除 | §5.2 `TOPOLOGICAL_ONLY`、§5.4 不進候選 |
| §4.2 | 不在事件 RGB 上標 ROI；先定圖、後看證據 | §5.1 |
| §5 | r004 鏡頭與事件 A4、B4 提案 | 不在本文範圍；影響 §5 的圖內容，不影響 schema |
| §6 | 13:00–13:30 的時間對應欄位 | §3.1（`t0_us`、`declaration_source`、`mapping_version`） |
| §7 | 不用 PG；JSONL 或 SQLite | §10 |
| §8 | RT-DETR-R18 下載紀錄（檔名、來源、大小、授權、SHA-256）與 A／B1 接線測試 | §4.2 範例填入實際值；接線結果不是 r004 驗收 |
| 開頭「D64 與發布補充」 | Agent 例外要等規則 PR 經使用者核准合併才生效；#86 核准前不改產品程式 | §0.3 兩道 gate |

## 13. 待決問題與處置

Codex 已逐題回覆（[回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)，與 [#92 契約審查 §2](https://github.com/Polalalabear/amidst/blob/80f5ca2137f077f359bc0f7587d057ae58bab75a/docs/engineering/Q1_Q5_CONTRACT_REVIEW_20261020.md) 相同）。下表「定案」指 Codex 已確認、本文已寫入；整份契約仍待使用者核准。數值一律仍是 PROPOSED。

| # | 問題 | 處置 |
| --- | --- | --- |
| Q-01 | DEVELOPMENT_RULES 第 57、62 行與 D63 修訂的 Agent 切鏡衝突 | **D64 已決，定案**（[D64](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6286156727)、[回覆](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6285790795)）：列例外，規則 PR [#125](https://github.com/Polalalabear/amidst/pull/125) 經使用者核准合併後 `AGENT_SEQUENTIAL` 才能在 Demo 啟用；#86 核准前連 `RULE_ONLY` 也不寫產品程式（§0.3） |
| Q-02 | D63 修訂原文是否與 §0.2 摘要一致 | **已解決**：原文已貼出（[#65](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6286155884)、[#81](https://github.com/Polalalabear/amidst/pull/81#issuecomment-6286156319)），§0.2 依原文；舊「不授權下載」保留為歷史並註明已取代。A／B1 接線測試的授權記為 REPORTED |
| Q-03 | `relation_tier` 四層與面積定義；是否加次要鍵 | **定案**：只用 D28 三個原鍵，不加次要鍵；tier 判定順序 4 → 3 → 1 → 2，`OVERLAP` 有 `UNKNOWN` 門也是 3；`BLIND_GAP` 面積是入口區域 ∩ 核准靜態可見範圍（§5.3、§5.4） |
| Q-04 | `UNKNOWN` 邊保留、`TOPOLOGICAL_ONLY` 排除 | **定案**；另加：r004 驗證不能自動解除 `PORTAL_R102` 的限制，解除要使用者決定（§5.2） |
| Q-05 | 候選時間窗固定或依長度與速度調整 | **定案**：固定 `search_window_us`，第一版不縮窗；窗裁切範圍明示（§8.6）。數值待約定 |
| Q-06 | 出口判定規則與 ROI 來源 | **方法定案、數值待核定**：Codex 提案 bbox 底邊中點落在 ROI 內（PROPOSED）；ROI 優先在靜態畫面人工標記，允許核准的純靜態投影（§5.4、§11） |
| Q-07 | 偵測索引是否一律離線、查詢是否補推論 | **定案**：一律離線，查詢不補推論；重產索引是另一次有授權的離線工作（§4.1） |
| Q-08 | Q4 是否只靠 RT-DETR＋HSV | **D64 已決，定案**：第一版只用 RT-DETR＋HSV；VLM 留到第二版；不接外部 API |
| Q-09 | Q3 解析後先確認或直接執行 | **定案**：直接執行並顯示，可修改重查；含糊或缺時鐘不猜、不執行（§7.2） |
| Q-10 | Agent 與規則是否用同一個 guard | **定案**：同一個 guard，Agent 不能降低；`MATCH_STRONG` 是待核定的提案值 |
| Q-11 | r004 的 run／clock 分配 | **定案**：同一事件所有鏡頭共用一個 run／clock；A4、B4 各自獨立，不跨 run 串人（§3.1） |
| Q-12 | 驗收是否讀產製路線 | **定案**：第一版不讀；日後另立隔離授權，不回填（§9） |
| Q-13 | store 由 PG 或本機檔案實作 | **定案**：不用 PG；JSONL＋manifest（優先）或 SQLite；薄 provider 直連 Ollama（§10） |
| Q-14 | RT-DETR 權重 hash、配套設定與 class map | **定案**：權重 SHA-256 `3ba8b5c9…66f0`、81,001,853 bytes、strict load、80 類、類別表來源檔 hash `4d5b8556…1431`、不另做 NMS（§4.2）。canonical class map 與正式 `detector_config` 的 hash 仍待產生 |
| Q-15 | 兩層圖誰標、誰查、何時核准；r004 是否重跑 K7 類檢查 | **定案**：Codex 產生、Claude 獨立檢查、使用者核准；r004 固定後重做 K7 類檢查；O10 前只能 `DRAFT`（§5.1） |
| Q-16 | `AMBIGUOUS_LINK` 算暫失或讓使用者選框 | **定案**：算暫失，保留所有框；使用者可明確手動改選，記 `USER` |
| Q-17 | 參數組是否沿用 #76 的流程與格式 | **流程定案、格式由本文定**：#76 沒有 Q1–Q5 的參數檔格式；§11 新增 `parameter-set.v1` |
| Q-18 | 手動改選是否重置搜尋預算 | **定案**：開新一次 `SEARCHING` 預算，不重置 session 累計上限與查詢時間範圍（§8.6） |
| Q-19 | HSV 參數由誰提案、用什麼資料 | **定案**：Codex 提案、Claude 檢查、使用者核定；只用 r004 小批 preview 的 RGB；A／B1 不能決定（§9）。數值待 preview |

## 14. 待使用者決定（第 1–4 項由 `1d1e061` 新增，第 5–8 項由釐清版新增）

建議的選項放第一個。這些都不擋 Codex 確認本版 SHA；使用者可在 checkpoint #88 一起回答。

1. **候選都沒有支持時，兜底能不能往 top-k 之後找？**（§8.6）
   - (a) **建議：**不能，只在快照的前 `top_k` 個內找；沒取證和被截掉的候選標 `NOT_EVALUATED`／`truncated`。符合 D63 修訂「Agent 輪詢 top-k」與 Codex 的有界要求。代價是 `top_k` 太小時比較常回原鏡頭。
   - (b) 兜底可以再往後取固定個數（新參數 `fallback_extra_candidates`），仍受 `fallback_budget_ms` 限制。找到的機會較多，但多一個要核定的參數，Agent 與兜底看的範圍也不同。
2. **目標只在決策時刻之前出現在候選鏡頭時，要不要切？**（§8.3）
   - (a) **建議：**不切，記 `NO_ALIGNABLE_OBSERVATION`，保留為候選。播放時間永不倒退，但重疊鏡頭中「目標早已進入」的情況會錯過。
   - (b) 切到候選鏡頭的目前來源時間，標「最後觀測在 t」。畫面會跟過去，但主畫面可能沒有目標框，切鏡就不再是由觀測驅動。
3. **`agent_used` 的語意**（§2.3，N6）
   - (a) **建議：**至少一個 Agent 決定被接受才算；只取證就兜底是 `false`（`agent_attempted: true`）。和「被接受的決定才影響結果」一致。
   - (b) Agent 有任何合法工具呼叫就算 `true`。比較貼近討論稿「有效查證」的字面，但 Agent 沒有影響任何結果時也會顯示「Agent 已使用」。
4. **兩層圖與出口 ROI 什麼時候凍結？**（§5.1；#92 審查 N5）
   - (a) **建議：**r004 **事件渲染之前**凍結 hash，並先經 Claude 獨立檢查。作者知道路線，提早凍結最好查核；代價是 ROI 要在靜態 preview 上先標完才能渲染事件。
   - (b) 維持現文「檢查事件證據之前」凍結。排程彈性較大，但事件 RGB 已存在時較難證明圖沒有參考答案。

**以下第 5–8 項是釐清版（#127）新增**：條文沒有給答案，選哪一個都是新的語意或 schema 決定，所以本版不定。未決前，以 `3873ff2` 的條文為準；測試包可以用建議選項當暫定形狀（標 PROVISIONAL），但不得當成已核准。

5. **`PARAMETER_GRID_MISMATCH` 與 `PARAMETERS_NOT_APPROVED` 搭配的 `status`**（§2.3 釐清、§8.2、§11；#127 U25）。兩者是原因碼、填 `reason` 已由條文決定，這裡只決定 `status`。不提供「HTTP 錯誤回應」選項：§2.3 的錯誤碼只有三個，新增的碼是原因碼。
   - (a) **建議：**`PARAMETER_GRID_MISMATCH` 不執行查詢，`status: UNKNOWN`（比照 Q1 `UNKNOWN`「必要輸入缺失，無法回答」；Q2 用同名狀態），`results`／`timeline` 為空陣列。`PARAMETERS_NOT_APPROVED` 照常計算，原本會是 `READY`／`COMPLETE` 的改為 `PARTIAL`（比照 Q2 `PARTIAL` 已含「圖未核准」），其他狀態不變。不改任何封閉清單。代價是 `UNKNOWN`、`PARTIAL` 的涵義變寬，UI 要看 `reason` 才分得出原因。
   - (b) Q1、Q2 的 `status` 封閉清單各加專用值（例如 `PARAMETERS_INVALID`）。UI 一眼看得出，但要改兩個封閉清單與測試包，也和 `GRAPH_NOT_APPROVED` 只填 `reason` 的作法不一致。
6. **link 紀錄放哪裡、怎麼綁 session**（§8.2；#127 U11）。空值規則已釐清（§8.2），這裡決定檔案與欄位。
   - (a) **建議：**每個 Q2 session 一份 append-only 的 link 檔（JSONL），每筆 `schema_version: q-demo.link-record.v1`，除 §8.2 的六個欄位外加 `session_id`、`link_index`（session 內從 0 連號）、`run_id`、`camera_id`、`frame_ref`（這一格）、`local_segment_id`、`ambiguous_candidates`（只在 `AMBIGUOUS_LINK` 時是 `[{observation_id, iou}]`，其他是 `null`）；Q2 回應在 `decisions_ref` 旁加 `links_ref`、`links_sha256`。和測試包暫定的 `<stem>.links.jsonl` 一致，改動最少。代價是多一個要 hash 綁定的檔。
   - (b) link 紀錄併入 `decisions` 檔，用不同的 `schema_version` 交錯記錄，可順便解 #127 U23 的 `step_index` 連號。代價是要改 §8.7「每個決策一筆」，`decisions_sha256` 涵蓋的內容也變多。
   - (c) 第一版不落檔，只在記憶體與 UI。最省事，但 §8.6 轉移表引用的 link 紀錄無法事後核對，`TEMP_LOST`／`SEARCHING` 的觸發時刻（§8.2）也驗不了。
7. **session 上限與 `fallback_budget_ms` 的可驗計數**（§8.6；#127 U27）。
   - (a) **建議：**決策紀錄加 `searching_index`（session 內第幾次 `SEARCHING`，從 1 起）與 `session_agent_rounds_used`（到這筆為止的 LLM 往返累計），兩者進 hash；兜底的牆鐘用量記在 `stats.latency_ms.fallback`（計時欄位不進 hash，§2.1），因預算停下時另記 `fallback_stopped_by_budget: true`（進 hash）。session 兩個上限可直接核對。
   - (b) 只在 Q2 回應記 session 總計（例如 `session_counters`）。欄位較少，但核對不到每一次 `SEARCHING`。
   - (c) 第一版不做可驗計數，測試包不檢查這三個上限。代價是 `ENDED_BY_LIMIT` 無法事後核對。
   - 不論選哪個：`fallback_budget_ms` 是牆鐘上限，是否觸發會讓 `RULE_ONLY` 重跑的結果不同，和 §8.7「同參數組、同快照重跑 hash 必須相同」有張力。本版不處理，列為待 Codex 回覆的問題（§15 末段）。
8. **頂層 `sampling.stride_samples` 與每台鏡頭 `stride_samples` 的關係**（§4.2、§4.4；#127 U28）。
   - (a) **建議：**每台鏡頭的 `stride_samples` 必須等於頂層值；頂層是取樣策略的值，`per_camera` 是逐台寫出的同一個值，不一致的 manifest 不合本契約。理由：§11 只有一個 `stride_samples` 參數、`applies_to.index_interval_us` 只有一個值，同一 run 的來源 fps 也相同（§4.4），逐台不同的索引本來就過不了 §8.2 grid 檢查。代價是不能讓個別鏡頭用較稀的取樣來省索引時間（Codex 契約審查 §4 的估算式允許每台 stride 不同）。
   - (b) 頂層是預設值，個別鏡頭可以覆寫。彈性較大；但混用時同一份參數組一定在 §8.2 grid 檢查 fail closed，參數組格式要改成逐台 `index_interval_us` 才用得上。
   - (c) 刪掉頂層 `stride_samples`，只留逐台的值。語意最單純，但要改 §4.2 的 manifest schema，測試包與索引鍵（§2.2）也跟著變。

## 15. 釐清紀錄（#127 符合性測試包回報）

#127（測試包 v0.2.0，head `e0ddf6a`，[回報留言](https://github.com/Polalalabear/amidst/pull/127#issuecomment-6291882477)）對 `3873ff2` 回報的歧義。「釐清」表示答案已由現有條文、決定或 #92 計畫決定，本版只是寫明；「待決」表示需要新決定，列在 §14。本表不改任何已核准的語意或數值。

| # | #127 項目 | 處置 | 寫在 | 依據 |
| --- | --- | --- | --- | --- |
| C1 | tier 4 在 transition 上沒有標記欄位（U08） | **釐清**：`relation` 補 `UNKNOWN`；tier 4 ⇔ `relation: UNKNOWN`；不另設欄位 | §5.3 `relation`、§5.4 | §5.4 tier 第 1 步；§5.3「由圖與可見範圍算出」（資料缺失就算不出）；#92 討論稿 §3.2 第 1 點「關係／面積缺件保持 `UNKNOWN`」；§12 對照表 §3.2 第 1 點；Codex 契約審查 Q-03「缺可見範圍／出口資料先為 tier 4」 |
| C2 | `BLIND_GAP` 但既非全 `OPEN`＋`APPROVED_WALKABLE`、也沒有 `UNKNOWN` 邊時沒有 tier（U08） | **釐清**：組合不存在，四步是窮舉 | §5.2 釐清、§5.4 | §5.2「`CLOSED` 的邊不進搜尋」、`traversability` 只有兩個值；§5.4 第 2 步「`CLOSED` 的邊已排除」、「含 `TOPOLOGICAL_ONLY` 邊的轉移在這之前就排除了」 |
| C3 | link 紀錄非 `LINKED` 時 `next_observation_id`、`iou` 的值（U11） | **釐清**：只在 `LINKED` 有值，其他是 `null`；`AMBIGUOUS_LINK` 的候選框另記。檔案位置、`schema_version`、session 綁定 **待決**（§14 第 6 項） | §8.2 | §8.2「每次連接產生一筆 link 紀錄」的欄位意義（`next` 是接上的觀測）、「有歧義時不硬接…把所有候選框記入紀錄」；#92 討論稿 §3.3「無唯一匹配時…不強配」；本文對「沒有符合的觀測」一律用 `null`（§8.3 `entry_observation_id`） |
| C4 | `window_truncated_us` 的形狀（U05 的一部分） | **釐清**：半開區間陣列，依時間排序、不重疊；沒裁切是 `[]` | §8.6 | §2.1 半開區間；§8.6「裁掉的範圍」；§4.4 `sampled_ranges_us` 的寫法；媒體／索引範圍可以有多段（§4.4） |
| C5 | §8.2 grid 檢查的「用到的鏡頭」 | **釐清**：`resolved_scope.camera_ids`；Q2 沒有鏡頭過濾，所以等於所請求 run 的索引 `per_camera` 全部鏡頭；找起點前一次檢查 | §8.2、§11 | §2.3「`resolved_scope`：實際用到的範圍」；§8.5 Q2 請求沒有鏡頭欄位、`APPEARANCE` 起點不限鏡頭；§8.2「回 `PARAMETER_GRID_MISMATCH`」是回應層結果 |
| C6 | U25：`PARAMETER_GRID_MISMATCH`／`PARAMETERS_NOT_APPROVED` 的回傳形式 | **釐清**：原因碼，填 `reason`，不是錯誤碼、不另訂 HTTP 狀態。搭配的 `status` **待決**（§14 第 5 項） | §2.3、§11 | §2.3「錯誤碼：沿用…三個；本文新增的原因碼分列在各節」；§11「`reason` 填 `PARAMETERS_NOT_APPROVED`」；§5.1 `GRAPH_NOT_APPROVED` 同一作法 |
| C8 | U26：證據摘要的 `schema_version`、`evidence_sha256` preimage、無顏色時的 `color_verdict`、`window_us` 是否裁切 | **釐清**：`q-demo.candidate-evidence.v1`；preimage 去掉 `evidence_sha256` 與 `stats`；無顏色時 `null`；`window_us` 未裁切 | §8.3 | §2.2 命名規則與最後一點；v1.1 §2.1、§2.3 `output_sha256` 作法；§8.3「窗指候選的 `window_us` 裁掉 `window_truncated_us` 之後的部分」、§8.6「長度是固定的 `search_window_us`」；§8.3「起始條件沒有顏色時」只看人物框 |
| C9 | U27：session 上限與 `fallback_budget_ms` 的可驗計數 | **待決**（§14 第 7 項） | — | 條文沒有任何計數欄位；新增欄位是 schema 決定 |
| C10 | U28：頂層與每台鏡頭 `stride_samples` 的關係 | **待決**（§14 第 8 項） | — | §11 單一 `stride_samples`、單一 `applies_to.index_interval_us` 傾向 (a)；但 Codex 契約審查 §4 的估算式允許每台 stride 不同，所以不是單純釐清 |

**測試包從條文推論的檢查**（#127 描述 Deviations 段，共 6 條；交辦時寫 5 條，實際列了 6 條）。全部判定為**契約本意**，已寫進條文，#127 不必移除：

| # | 測試包的推論 | 判定 | 寫在 | 依據 |
| --- | --- | --- | --- | --- |
| C7-1 | 證據的 `window_us` 等於快照候選的 `window_us` | 本意 | §8.3 證據摘要釐清 | §8.4「Agent 不能…改時間窗」；§8.6 兜底規則第 1 點「各自已定的 `window_us` 內取證」；§8.3 窗的定義 |
| C7-2 | `entry_observation_id` 非 `null` 時 `target_presence` 只能是 `MATCH_STRONG`／`MATCH_WEAK` | 本意（條文其實更強：一定達到 `switch_min_presence`） | §8.3 證據摘要釐清 | §8.3 進入觀測條件「達到 `switch_min_presence` 的觀測」；§11 `switch_min_presence` 只能是 `MATCH_STRONG` 或 `MATCH_WEAK` |
| C7-3 | 非 `null` 的 `ranking_area_m2` 要附 `ranking_area_refs` | 本意 | §5.3 | §5.4「單位 m²，附 `ranking_area_refs`」；§5.3 該列 |
| C7-4 | `SWITCH` 段從證據的 `entry_timestamp_us` 起 | 本意 | §8.7 | §8.6 轉移表「起始觀測是 `entry_observation_id`，從 `entry_timestamp_us` 起」；§8.3 前方缺口 |
| C7-5 | `source_time_us ≥ decision_time_us`（只用 `≥`） | 本意；條文不要求相等 | §8.7 | §8.6「來源時間只往前走」、「切鏡只能進到 `timestamp_us ≥ decision_time_us` 的觀測」 |
| C7-6 | `PARTIAL_EVIDENCE` 的最佳觀測只能是 `NONE` | 本意；無顏色時 `best_observations` 為空 | §8.3 證據摘要釐清 | §8.3 判定順序（`STRONG`／`WEAK`／`UNKNOWN` 都排在 `PARTIAL_EVIDENCE` 前）；「人物框」定義；`PARTIAL_EVIDENCE`「已推論的格只有全 `NONE` 的人物框或沒有人物框」 |

**本版沒處理、待 Codex 回覆的新問題**（測試包可另編 U 號）：
- 起點鏡頭完全沒有 `exit_zones` 時，§5.4 第 1 步「用該鏡頭全部出口」是空集合，展開不出任何轉移；這和「tier 4 的鏡頭仍列入」怎麼對上，要由產生圖的一方（Codex）說明 `relation: UNKNOWN` 的轉移在出口資料缺失時怎麼掛在出口上。
- `reason` 只有一格：`TIME_SCOPE_PARTIAL`、`GRAPH_NOT_APPROVED`、`PARAMETERS_NOT_APPROVED` 同時成立時填哪一個，條文只說「寫主要原因」（§6.3），沒有優先順序。
- `fallback_budget_ms` 與 `RULE_ONLY` 重跑 hash 相同（§8.7）的張力（§14 第 7 項末點）。
