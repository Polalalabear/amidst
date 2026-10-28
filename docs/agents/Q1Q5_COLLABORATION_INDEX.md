# Q1–Q5 協作索引（驗收矩陣、文件地圖、驗證系統、基線、時程）

> 日期：2026-10-25 更新（§0.1、§1.2 與 §5.3 已更新到 D78；§1.1 的「目前狀態」欄與 §4、§5.2 仍是 2026-10-20 D67 之後的歷史快照）。本文是**索引**，不是規格：不重抄 schema，每個條件都指向契約章節或計畫章節。與原文不一致時，以契約、計畫和 GitHub 原始決策留言為準。
> 即時狀態以 [#93 任務板](https://github.com/Polalalabear/amidst/issues/93)、各任務 issue 的 label 與 PR 狀態為準；本文 §1.1 的「目前狀態」欄是 2026-10-20（D65–D67 之後）的快照，會過期，以 §0.1 的現況為準；板上內文與 label 不一致時，以 label 與最新留言為準。
> 找不到依據的寫 `UNKNOWN`。本文沒有執行任何程式、推論或渲染。組員從 [TEAM_ONBOARDING](TEAM_ONBOARDING.md)（資料夾流程，不用 Git）開始。

## 0. 先讀這幾點

1. **主線是 Q1–Q5**（D63、D63 修訂、D64）。2D→3D 重建線（2b–2d、CS-C、CS-D、#84、#85）暫停保留，不關、不刪。
2. **契約 #86 已定稿並核准**：固定在 `3873ff2dbe97c88b3de2cfcdfc7df393fdff23d2`（bytes SHA-256 `924c4365…78078`），經 Codex 確認（G2），D65 由使用者在 [#88](https://github.com/Polalalabear/amidst/issues/88) 核准，merge `f62ab72` 已合入 `mainline/q1q5`；計畫 #92 @ `86877b2`（merge `b1a1b32`）。契約 §0.3 的第 1 道 gate 已通過，Q 線產品程式可以開始寫。**§8.2、§8.3 的修訂已併入 `3873ff2`**。
3. **整合分支是 `mainline/q1q5`**（預設分支、受保護、只用 merge commit；2026-10-20 檢查 head `10070eb`）。`main` 不動，等第一版 Demo 通過且使用者授權。
4. **D65–D67（2026-10-20，使用者決定）**：D65 核准 #88 並把契約 §11 參數當第一版初值（前提索引 5 fps）；D66 決定 #90 的 U-1–U-8（全採建議）；D67 決定 #125 由 Codex 審查通過後合併、#126 預算當第一版初值、r004 **只授權建檔與靜態校正匯出、不授權渲染**、#131 先寫計畫 PR、Codex 任務 PR 審查通過即合、允許疊分支。細節見 [DECISION_INDEX](DECISION_INDEX.md)。
5. 要做什麼：Codex 與 Claude 看 [#93](https://github.com/Polalalabear/amidst/issues/93) 的**自選規則**與 [驗收計畫](Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) §4 的分工；組員不自選任務，使用者交給哪一包做哪一包（[TEAM_ONBOARDING](TEAM_ONBOARDING.md)）。

### 0.1 現況更新（2026-10-25，D68–D78）

下列取代上面第 3、4 點與 §1.2 舊狀態的衝突處；全文與連結見 [DECISION_INDEX](DECISION_INDEX.md)。

- **主線與 staging（D70、D75）**：Codex 在 `codex/q1q5-staging` 自審、自己用 merge commit 合進 staging（條件：#127 測試包與 focused 測試通過）；Claude 審 staging 後分批合進 `mainline/q1q5`。第 1 批已在 2026-10-25 合進主線（[#213](https://github.com/Polalalabear/amidst/pull/213)）。**staging 合併不是正式驗收**；`main` 不動（D72）。
- **G3 已成立**：規則例外 [#125](https://github.com/Polalalabear/amidst/pull/125) 已合進主線（merge `f915fb0`）。`AGENT_SEQUENTIAL` 的使用範圍仍受 D64 的有界例外約束。
- **渲染（D70）**：已授權 #132 的 45 格廣角 preview、A4／B4 事件 run（A4 四台、B4 五台各 30 s，5 fps，960×540）與正式索引 #118；磁碟 12 GiB 的開始門檻由使用者判斷，**可用空間低於 8 GiB 立刻停**，每次產製前後記 `df -k`。但 D74 規定圖 v3 修完、Claude 複核、凍結（**G4 一次核定**）之後才產生正式事件 run，所以現在仍未產製。
- **兜底（D71）**：不是牆鐘截斷；是 Agent 故障時的下位替代，等同 `RULE_ONLY` 的決定性 Controller，可從任一點接手到 session 結束；`fallback_budget_ms` 只記 `stats`。**每台鏡頭都必須畫出口區域**，缺漏 fail closed。D73 維持 D65 預算、第一版不設 LOST 期限；D78 完成同鏡頭重取得與 SWITCHING／stop 的規格採案（尚未實作）。
- **評估（D71、D75、D76）**：Q2、Q5 輸出凍結後和劇本自動比對（只在評估端讀劇本）；Q4 由組員對抽樣的最終結果做 T／F；Q1、Q3 由組員出題與寫標準答案，Claude 轉換成評分格式。驗收分兩階段：P1 工程預驗收、P2 正式 baseline 驗收（[驗收計畫](Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) AC1–AC8）。
- **組員流程**：資料夾包、瀏覽器填表、`RETURN/` 回交檔，不用 Git（D76、#147）。見 [TEAM_ONBOARDING](TEAM_ONBOARDING.md)。

## 1. 驗收矩陣

怎麼讀這張表：

- **驗收條件**：取自契約 #86 @ `3873ff2`（已核准）與 Codex 計畫 [#92](https://github.com/Polalalabear/amidst/pull/92) 的 §11「第一版完成條件」。這裡只寫重點，細節讀章節。**門檻數字**：契約 §11 的參數組已由 D65 核定為**第一版初值**（綁 `parameter_set` hash；前提索引 5 fps），#126 的搜尋／兜底預算由 D67 當第一版初值；之後只能用 r004 preview 另出新版、由使用者核定。D65 列出的初值不含 `switch_min_presence`，它是否已核定：`UNKNOWN`（讀契約 §11 確認）。
- **任務**：[#93](https://github.com/Polalalabear/amidst/issues/93) 的任務 issue（#94–#124）與 #89。一個任務可橫跨多個 Q；每個 Q 只列它主要依賴的任務，完整對照以 #93 總表為準。
- **Gate**：[#93](https://github.com/Polalalabear/amidst/issues/93) 的 G1–G7、G75（定義與現況見 §1.2）。
- **驗證**：測試包 = [#127](https://github.com/Polalalabear/amidst/pull/127) 的合約符合性測試包（v0.2.1，綁 `3873ff2`；只測契約層，見 §3）；審查 = 另一方的 PR 審查；瀏覽器驗收 = #124；使用者核准 = 檢查點或 issue 上的明確核准。
- **目前狀態**：2026-10-20 快照。契約已核准，但檢查時 `mainline/q1q5` 上仍**沒有 Q1–Q5 專屬的產品程式**（Codex 的 [#134](https://github.com/Polalalabear/amidst/pull/134)〔#101 時間對應〕是第一個 Draft PR），所以沒有一格是「已驗收」。

### 1.1 逐 Q 驗收

| Q | 驗收條件（重點） | 來源 | 負責任務 | Gate | 驗證方式 | 目前狀態 |
| --- | --- | --- | --- | --- | --- | --- |
| **Q1** 依條件找相機 | ① 至少一台有車、一台無車的鏡頭，展示一個有支持的查詢和一個**支援類別**的零命中查詢；結果附模型、frame／camera／時間證據與取樣範圍 ② `status` 封閉清單（`READY`／`NO_MATCH`／`PARTIAL`／`UNSUPPORTED_CLASS`／`UNSUPPORTED_CONDITION`／`OUT_OF_RANGE`／`UNKNOWN`），`NO_MATCH` 只說「在已推論的影格中沒有找到」，不說「不存在」 ③ 三種「沒有」分開：條件不符（`no_match_cameras`）、沒推論（`not_evaluated_cameras`）、`MISSING` 格 ④ 排序 `first_match_us_asc → camera_id`，偵測數不進排序 ⑤ 手動輸入、預填、Q3 解析出的同一正規化請求，`output_sha256` 相同 ⑥ 類別別名表是封閉人工表，LLM 不能擴充；不支援的詞（例如「樹」）明列 | 契約 §6、§6.2、§6.3、§4；計畫 #92 §11 第 1 點（契約 @ `3873ff2`） | 查詢模組 #109；依賴 #101（時間）、#102（store）、#103（索引）；端點 #112；UI #120（Q3 查詢列＋Q1 結果牆）；正式索引 #118 | G1 ✅；#112 另需 G75 ✅；#118 需 G6 ✅（第一版初值），另需 #114、#115（渲染未授權） | 測試包：`Q1_*` 六項、`TIME_COVERAGE_*`、`SCOPE_HASH_LINKS`；審查；瀏覽器驗收 #124；最終「有車／無車」要靠 r004 實際 RGB 的人工審核頁（測試包不證明辨識品質） | #109 `blocked`（等 #101、#102、#103，三者 `ready`；#101 已有 Draft PR [#134](https://github.com/Polalalabear/amidst/pull/134)）；#120 `blocked`（等 #119，`ready`）。契約已固定 `3873ff2` |
| **Q2** 在影片中找人 | ① 兩個 r004 事件案例展示：觀測、同鏡頭暫失、D28＋兩層圖合法候選、切鏡、無支持時回原鏡頭 ② 同鏡頭最小 IoU 連接器：只連 `person`、一對一匹配、缺格不內插、有歧義不硬接（`AMBIGUOUS_LINK`）、暫失門檻以**時長** `link_max_gap_us` 核定（取樣率改變不得默默改變暫失時長） ③ 狀態機 `PLAYING`／`TEMP_LOST`／`SEARCHING`／`SWITCHING`／`RETURNED_TO_ORIGIN`／`ENDED`，來源時間只往前走 ④ 身分一律 `UNCONFIRMED`；「沒偵測」不等於「已離開」 ⑤ 兩層圖與出口 ROI 的 hash 可核對，`PORTAL_R102`（`TOPOLOGICAL_ONLY`）不在任何路線 | 契約 §8.2、§8.5–§8.7、§5；計畫 #92 §11 第 3、5 點 | 連接器 #107；圖與候選 #104；Controller #110；r004 建檔 #113；事件 run #115；兩層圖資料 #116＋獨立檢查 #117；UI #121 | G1 ✅；#116 需 G4 ❌；#113 建檔 D67 已授權、**渲染未授權**；#115 事件 run 需渲染授權（G5 渲染部分 ❌） | 測試包：`SESSION_STATE_MACHINE`、`Q2_*` 三項、`DECISION_*`、`GRAPH_*`（連接器 §8.2 的 `link` 紀錄契約沒有 schema，測試包 `LINK_RECORD_GAP_RULES` 用暫定形狀，U11）；#117 獨立檢查；審查；瀏覽器驗收 #124 | #107 `ready`、#110 `blocked`、#113 `blocked`、#115 `needs-auth`、#116 `blocked`、#117 `blocked` |
| **Q3** 理解使用者措辭 | ① 示例自然語言轉成有效的結構化查詢（Q1 或 Q2 請求），通過 strict schema 驗證 ② LLM 失敗退規則解析器（`PROVIDER_UNAVAILABLE`／`PROVIDER_TIMEOUT`／`INVALID_RESPONSE`），規則解析也失敗就 `PARSE_FAILED`，**不猜、不執行** ③ `NEEDS_CLARIFICATION` 附封閉表選項 ④ 詞語必須是使用者原文的片段，對到封閉表；時間換成來源微秒 ⑤ prompt、模型 digest、驗證結果都記錄；說明文字的 `cited_refs` 必須出自輸入，否則改模板 | 契約 §7（§7.1–§7.6）；計畫 #92 §11 第 2 點 | 薄 provider #105；解析 #106（依賴 #101、#105）；UI #120；測試集與評分器 #89（組員） | G1 ✅ | 測試包：`Q3_*` 六項、`EXPLANATION_CITED_REFS`（啟發式）；#89 的語意測試集（評 Q3 解析品質，與測試包互補）；審查；瀏覽器驗收 #124 | #89 `ready`（組員，無人認領）；#105 `ready`；#106 `blocked`（等 #101、#105）；#101 已有 Draft PR #134 |
| **Q4** 模型判斷 2D 畫面是否含目標 | ① 只用偵測索引（RT-DETR＋上半身 HSV 摘要）；Qwen 是文字模型，不看影像；第一版無 VLM ② `target_presence` 封閉清單與**判定順序**：`MATCH_STRONG`／`MATCH_WEAK`／`PERSON_COLOR_UNKNOWN`／`PERSON_NO_COLOR_MATCH`／`NO_PERSON_DETECTED`／`PARTIAL_EVIDENCE`／`NOT_EVALUATED`；否定結果只在覆蓋完整時成立，沒推論的時段不能證明目標不在 ③ 切鏡進入點 `entry_observation_id` 由服務決定性選出，`timestamp_us ≥ decision_time_us`，播放時間不倒退 ④ 各授權鏡頭實際 RGB 的 RT-DETR 判斷，**不用 Blender 清單／GT 代答** ⑤ 衣服、廣角與遠距小框要有實測，不以「渲染完成」代替「辨識通過」 | 契約 §8.3、§4；計畫 #92 §11 第 2、5 點 | 索引產生器 #103；證據聚合 #108；HSV 參數提案 #114（依賴 r004 preview #113）；正式索引 #118；標註與評估 #123；UI #121 | G1 ✅；#118 需 G6 ✅（第一版初值），另需 #114、#115（渲染未授權） | 測試包 v0.2.x 的 `EVIDENCE_PRESENCE_RULES`、`DECISION_EVIDENCE_AND_ENTRY` 檢查 §8.3 的判定順序與進入點（證據摘要 schema 是暫定，U26）；審查＋#123 的標註評估（人工標註交給組員 #128）；瀏覽器驗收 #124。辨識品質只能靠 #123／#128 與人工審核頁 | #103 `ready`、#108 `blocked`（等 #102、#103）、#114 `blocked`（等 #113）、#118 `blocked`、#123 `blocked`、#128（組員標註）`blocked` |
| **Q5** 目標離開時是否切鏡 | ① 兩種模式 `RULE_ONLY`／`AGENT_SEQUENTIAL`：候選集合、順序、狀態機、紀錄格式相同，只差誰提出動作 ② 候選由兩層圖＋D28 原鍵（`relation_tier → overlap_area_m2_desc → camera_id`）**決定性**產生，Agent 不能改排序、不能發明候選 ③ Agent 只在合法 top-k 內決定切或不切；非法提交被拒且仍計預算；有輪數與時間上限 ④ 超限就由決定性規則兜底，兜底只在同一快照的前 `top_k` 內找，**不得因為 top-k 沒有支持就宣告「所有鏡頭都查無結果」** ⑤ 回應標 `agent_attempted`、`agent_used`、`decision_source`、`fallback_used`／`fallback_reason`；prompt、模型 digest 可查 ⑥ 切鏡 guard `switch_min_presence` 未核定前，Demo 只能 `RULE_ONLY` 顯示候選與證據，不自動切換（D65 列出的初值不含它，是否已核定：`UNKNOWN`） | 契約 §8.1、§8.4、§8.6、§8.7、§5.4、§0.3；計畫 #92 §11 第 3、4 點；預算提案 [#126](https://github.com/Polalalabear/amidst/pull/126) | 圖與候選 #104；Controller #110；Agent 模式 #111（依賴 #105、#110）；Agent 例外條文 #95；UI #121 | G1 ✅；`AGENT_SEQUENTIAL` 另需 **G3 ❌**（D67：#125 經 Codex 審查通過後由協調者合併）；#116 需 G4 ❌ | 測試包：`CANDIDATE_*`、`DECISION_*`、`SESSION_STATE_MACHINE`、`Q2_RESPONSE_VS_DECISIONS`、`AGENT_DECISION_FORMAT`、`COMMON_AGENT_FIELDS`；審查；瀏覽器驗收 #124。**切鏡好不好、有沒有誤切，測試包不評價**（人工審核頁） | #95 `ready`（PR #125 已開，描述寫 Draft、不合併；GitHub 狀態為非 Draft；待 Codex 審查）；#110、#111 `blocked`。預算 #126 由 D67 當第一版初值（PR 仍未合併）；評估器 #129（組員）`blocked` |
| **共通**（契約、規則、驗證本身） | 契約 #86 定稿並經 Codex 確認 SHA、使用者核准（✅ `3873ff2`）；規則例外 PR 合併（G3 ❌）；測試包固定版本對齊（✅ v0.2.1）；GT 隔離（§9）；參數組核定（§11，✅ 第一版初值） | 契約 §0.3、§9、§11、§14；#88 | #94（契約定稿）、#96（審查 #92）、#95（規則例外）、#99（測試包）、#98（參數組提案）、#97（r004 修改表） | G1 ✅、G2 ✅、G3 ❌、G6 ✅ | 審查；使用者在 [#88](https://github.com/Polalalabear/amidst/issues/88) 核准；測試包版本對契約 SHA | #94、#96 已完成（關閉）；#97 已交付 Draft PR [#132](https://github.com/Polalalabear/amidst/pull/132)（Claude 審查：需修改 X1、X2）；#99 label `blocked`，PR #127 已更新到 v0.2.1（綁 `3873ff2`，head `994d34c`）；#98 `ready`；#95 `ready` |

### 1.2 Gate 一覽（#93 的 G1–G7、G75）

下表原是 2026-10-20（D65–D67 之後）的現況，G3、G4、G5 列已更新到 2026-10-25；以各 gate 的連結為準。

| Gate | 內容 | 成立？（2026-10-20） |
| --- | --- | --- |
| G1 | #88：使用者核准修訂稿 #92 與契約 #86 | ✅ 成立：[D65](https://github.com/Polalalabear/amidst/issues/88#issuecomment-6291477432)；契約 `3873ff2`（merge `f62ab72`）、計畫 `86877b2`（merge `b1a1b32`） |
| G2 | 契約 #86 新版固定 SHA，且 Codex 再確認 | ✅ 成立：`3873ff2`，Codex [已確認](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6291339657) |
| G3 | DEVELOPMENT_RULES 的 Q1–Q5 Agent 有界例外 PR 經使用者核准合併 | ✅ 成立（2026-10-25 更新）：PR [#125](https://github.com/Polalalabear/amidst/pull/125) 依 [D67](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6292484288) 以 merge `f915fb0` 合進主線 |
| G4 | O10 用途核准（D62）；r004 改動範圍需重做 K7 類型檢查 | ❌ 未成立（2026-10-25 更新）：[D74](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6396154980) 規定圖 v3 的 R01–R08 全部修完、Claude 複核後由使用者**一次核定**，凍結後才渲染事件 run；v2 不能照現狀凍結（#117 收據） |
| G5 | r004 建檔／渲染的使用者明確授權 | 🟡 部分（2026-10-25 更新）：D67 授權建檔與靜態校正匯出；[D70](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6307788539) 另授權 #132 的 45 格廣角 preview、A4／B4 事件 run（A4 四台、B4 五台各 30 s）與 #118，開始門檻由使用者判斷、**可用空間低於 8 GiB 立刻停**；D74 要求 G4 凍結後才產生正式事件 run。r003 與其 pin 不動 |
| G6 | §11 參數組經使用者核定 | ✅ 成立：D65 把 §11 當第一版初值（前提索引 5 fps；改取樣率會 `PARAMETER_GRID_MISMATCH`）；D67 把 #126 預算當第一版初值（#126 PR 仍未合併） |
| G7 | #90 設計的待決 U-1–U-8 由使用者決定 | ✅ 成立：[D66](https://github.com/Polalalabear/amidst/pull/90#issuecomment-6291537538) 全採建議 |
| G75 | #75、#80 經審查並合入 `mainline/q1q5` | ✅ 成立：#75 → `4f193e6`、#80 → `052abb1` |

## 2. 文件地圖

| 文件 | 管什麼 | 位置（固定 SHA） |
| --- | --- | --- |
| **契約 #86** `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md` | Q1–Q5 第一版的權威規格：共通回應欄位 §2.3、時間 §3、偵測索引 §4、兩層圖 §5、Q1 §6、Q3 §7、Q2／Q4／Q5 §8、GT 隔離 §9、儲存 §10、參數表 §11、待決 §13、待使用者決定 §14 | PR [#86](https://github.com/Polalalabear/amidst/pull/86)，**已合入 `mainline/q1q5`**（merge `f62ab72`）；固定版本 [`3873ff2`](https://github.com/Polalalabear/amidst/blob/3873ff2dbe97c88b3de2cfcdfc7df393fdff23d2/docs/contracts/Q1_Q2_FIRST_DEMO_V1.md)，bytes SHA-256 `924c4365ab3b3169eb9192296a26eede9d558d885410e7e80197d00a77978078`（D65）。更早的 `258c7e2`、`1d1e061` 是歷史版本，不再引用 |
| **契約審查** `docs/engineering/Q1_Q5_CONTRACT_REVIEW_20261020.md` | Codex 對 Q-01–Q-19 的回覆與 7 項必要修正（已處理於 `3873ff2`） | PR [#92](https://github.com/Polalalabear/amidst/pull/92)，**已合入**（merge `b1a1b32`）；契約引用 `80f5ca2`，合入版本 `86877b2`（多了 D41 磁碟 gate 與 worktree 清理紀錄） |
| **計畫（Codex 修訂稿）** `docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md` | 工作計畫：兩層圖、RT-DETR／HSV、r004 修改提案、分工與實作順序（§10）、第一版完成條件（§11） | PR [#92](https://github.com/Polalalabear/amidst/pull/92)，**已合入**（`86877b2`，merge `b1a1b32`） |
| **工作台設計** `docs/agents/WORKBENCH_V2_Q1Q5_DESIGN.md` | workbench-v2 的 Q1–Q5 畫面、審核模式（§3）、Demo 與審核模式差異、實作切分 T1–T4（§5）、待使用者決定 U-1–U-8（§6） | PR [#90](https://github.com/Polalalabear/amidst/pull/90)（Draft，未合併），[`767a092`](https://github.com/Polalalabear/amidst/blob/767a092f874d3bba5e279938e63b72e9df5c0e3d/docs/agents/WORKBENCH_V2_Q1Q5_DESIGN.md)。U-1–U-8 已由 D66 決定；它依據的契約是 `258c7e2`，欄位對應待對齊 `3873ff2`（#119 起處理） |
| **合約符合性測試包** `docs/evaluation/Q1Q5_CONFORMANCE_KIT.md` | 63 項契約層檢查（v0.2.0 起）、仍待確認的契約 UNKNOWN（U01–U28）、不能證明什麼 | PR [#127](https://github.com/Polalalabear/amidst/pull/127)（Draft，未合併）；**v0.2.1，head `994d34c`，綁契約 `3873ff2`**（v0.2.0 `e0ddf6a` 已被取代：修了 DST fold 的誤報 [#133](https://github.com/Polalalabear/amidst/issues/133)）。檢查數與 U 項數以 PR 為準，本文未重跑 |
| **規則例外** `docs/specs/DEVELOPMENT_RULES.md`（`docs/DEVELOPMENT_RULES.md` 是指向它的 symlink） | D64 Q1–Q5 Agent 有界例外條文 | PR [#125](https://github.com/Polalalabear/amidst/pull/125)，`1f30232`；未合併（D67：Codex 審查通過後由協調者合併） |
| **搜尋／兜底預算提案** `docs/engineering/Q1_Q5_SEARCH_BUDGET_PROPOSAL_20261020.md` | 6 項上限（D67 當第一版初值：`agent_max_illegal_submissions` 2、`search_window_us` 6,000,000、`research_interval_us` 1,000,000、`session_max_research_rounds` 6、`fallback_budget_ms` 1,000、`session_max_agent_rounds` 12） | PR [#126](https://github.com/Polalalabear/amidst/pull/126)，`5838108`；PR 未合併 |
| **任務板** | 任務 #94–#131、#89、#128–#130（組員），gate、自選規則、相依圖 | Issue [#93](https://github.com/Polalalabear/amidst/issues/93)（置頂）；milestone「Q1–Q5 第一版」（[milestone 2](https://github.com/Polalalabear/amidst/milestone/2)，無到期日） |
| **檢查點** | 使用者核准計畫與契約（✅ D65） | Issue [#88](https://github.com/Polalalabear/amidst/issues/88)。實作 PR 的合併檢查點（第一版 Demo 驗收）：尚未建立，`UNKNOWN`（#93 同） |
| **整理紀錄** | D63 後的盤點與暫停項 | Issue [#87](https://github.com/Polalalabear/amidst/issues/87) |
| **決策索引** | D1–D78 一句摘要與原始留言連結 | [DECISION_INDEX](DECISION_INDEX.md)；D63、D63 修訂、D64 的原文是 #65／#81／#86 上標題為「## D63」「## D63 修訂」「## D64」的留言；D65 在 #88、D66 在 #90、D67 與 D68、D70–D78 在 #93、D69 在 #135 |
| **規則** | GT 隔離、來源資產、不確定度、研究邊界、角色分工、Git 流程、「實際產出」範本 | `AGENTS.md`、`CLAUDE.md`、`docs/DEVELOPMENT_RULES.md`（見 [TEAM_ONBOARDING §5、§9](TEAM_ONBOARDING.md)）。[#91](https://github.com/Polalalabear/amidst/pull/91)（merge `10070eb`）已把 `AGENTS.md` 的整合分支改成 `mainline/q1q5` 並指向 #93；`CLAUDE.md` 的閱讀順序是否已更新：`UNKNOWN`（本文只確認 `AGENTS.md`） |
| **受控場景契約 v1.1**（Q 契約沿用其 §2、§2.1、§2.3、§3.6、§3.7、§6.1、§7） | 時間慣例、hash、缺格、門、鏡頭、D28 排序、GT 隔離 | PR [#65](https://github.com/Polalalabear/amidst/pull/65)，已核准版本 `98451bd` |
| **系統導覽／組員上手** | 分層、名詞、組員資料夾流程（不用 Git；包格式、兩種組員工作、關卡） | [SYSTEM_OVERVIEW](SYSTEM_OVERVIEW.md)、[TEAM_ONBOARDING](TEAM_ONBOARDING.md)（PR #83） |
| **K7 r003 驗證** | `PORTAL_R102` 只當拓撲連通的依據；O10 的**建議**，不是核准 | PR [#82](https://github.com/Polalalabear/amidst/pull/82) `6e689f9`（Draft） |

## 3. 驗證系統

目的：Codex、Claude 與組員各做各的檔案集合，靠**可重跑的檢查**而不是靠互相相信來合流。每一層擋不同的錯，**沒有任何一層證明辨識品質或劇情正確**。

| 機制 | 擋什麼 | 在流程的哪裡 | 誰負責 | 做不到什麼 |
| --- | --- | --- | --- | --- |
| **合約符合性測試包**（[#127](https://github.com/Polalalabear/amidst/pull/127)，任務 #99） | 回應形狀、封閉清單、共通欄位、hash 可重算、候選順序（D28）、決策合法性與狀態機、時間涵蓋、`gt_read=false` 宣告 | Codex 的每個產品 PR 送出前，必須跑**固定版本**的測試包（#126 描述也這樣要求；D67 的「Codex 任務 PR 審查通過即合」條件之一是測試包通過，且對的是當時綁定的契約版本）；缺的參數回 `SKIPPED_PARAM_UNSET`，整體 `INCOMPLETE`，不算通過 | 維護：Claude（#99）。使用：Codex（自己跑）。Codex **不直接改**測試包；認為測試錯就開 issue 附報告，Claude 改（前例 [#133](https://github.com/Polalalabear/amidst/issues/133)）。跑法：測試包分支的 `docs/evaluation/Q1Q5_CONFORMANCE_KIT.md`（組員不跑，見 [TEAM_ONBOARDING §8](TEAM_ONBOARDING.md)） | 不證明辨識品質、劇情正確、真實資料、GT 隔離的實際行為、身分、延遲；連接器 link 紀錄與 Q4 證據摘要的形狀是暫定（U11、U26）；契約修訂後要同步改版 |
| **交叉審查** | 規格符合、不變量、檔案集合越界、GT 洩漏、過度宣稱 | 每個 PR 都要另一方審查。合併：**Codex 任務 PR** 經 Claude 審查通過＋測試包通過＋head SHA 相符，協調者以 merge commit 合併（D67 第 5 點）；規則、契約、r004／渲染、finalization 類 PR 與 `main` 仍要使用者核准；組員目前**不開 PR**（資料夾流程，D76／#147）：回交的 CSV 由 Claude 轉換或匯入（D75、CL-7），核對方式見 [TEAM_ONBOARDING §7](TEAM_ONBOARDING.md) | 作者不審自己的 PR：Codex 的 PR 由 Claude 審（Opus／high，小型或純文件用 medium，見 `CLAUDE.md` 模型表）；Claude 的 PR 由 Codex 審 | 審查是人為判斷，不可重跑；不取代測試包 |
| **獨立檢查**（#117） | r004 兩層圖與出口 ROI 是否符合靜態依據（K7 類型：只用核准的靜態幾何、不含人物的靜態畫面） | 兩層圖與 ROI 凍結 hash 之前；契約 §14 第 4 題建議在 r004 **事件渲染之前**凍結 | Claude（作者是 Codex，故由 Claude 獨立查） | 只檢查靜態圖依據；不是物理通行認證（通行性在核准範圍外一律 `UNKNOWN`） |
| **檢查點 gate**（#88、G1–G7、G75） | 還沒被使用者核准的東西被合併或被當成前提 | 檢查點範圍內的東西在使用者於檢查點 issue 核准前不合併；`blocked`／`needs-auth` 的任務不做 | 使用者核准；Claude 維護 label 與 #93 | 不審內容正確性，只管授權；「PR 能開、能被審，不能合併」 |
| **「實際產出」紀錄**（AGENTS.md） | 把規劃和結果混為一談；過度宣稱 | 每個任務的 PR 描述**與** issue 留言都附（Model／effort、PR／commits、Files changed、Commands run and results、Artifacts、Verified、Not verified、Deviations）；沒有就寫 `NONE`／`UNKNOWN` | 作者（Codex、Claude、組員自己的 agent）；審查者檢查「Not verified」有沒有誠實 | 是自述，不是證明；要靠審查與可重跑的指令核對 |
| **GT 隔離** | Ground Truth、renderer 軌跡、visibility、depth、事件腳本、產製路線進入推論、索引、圖、Agent、prompt、參數 | 全程。契約 §9 的表：偵測索引只讀 safe RGB；兩層圖只讀核准的靜態依據；Agent／LLM 看不到人物設定與事件腳本；第一版**不讀產製路線做驗收**（Q-12）；HSV 參數只用獨立 preview 的 RGB 裁切 | 所有人。實作面：Codex 的服務不得讀 GT；Claude 的測試包用 `NO_FORBIDDEN_CONTENT` 掃禁用內容；組員拿不到 GT（見 [TEAM_ONBOARDING §5](TEAM_ONBOARDING.md)） | 回應裡的 `provenance.gt_read: false` 只是自己的宣告；真的沒讀要靠程式審查與行為探測（`PROBE_FORBIDDEN_FIELD_REJECTED`），不能靠報告擔保 |
| **瀏覽器驗收**（#124） | 畫面上能不能走完 Q1–Q5 流程、狀態標示是否誠實（`MISSING`／`UNKNOWN`／`SYNTHETIC` 不被畫成觀測） | 等後端端點、r004 資料與 UI 都就緒（#112、#116、#118、#120、#121、#122） | Claude | 工程驗收，不是研究級評估；SYNTHETIC 資料下的人工 PASS 照實記錄但不算驗收（#90 U-4 建議） |
| **人工審核頁**（#122，審核模式） | 劇情正確、辨識品質、切鏡好壞（測試包明說不證明的部分） | 資料就緒後由使用者或審核人逐項判斷 | Claude 做工具；使用者判斷 | 預期清單放 repo 外（#90 U-2、U-3 待決） |

## 4. 階段 A 基線

**階段 A 的定義：`UNKNOWN`。**用 `grep` 在契約 #86 @ `3873ff2`（`mainline/q1q5` 上的檔案）、計畫 #92 的文件（`mainline/q1q5` 上的檔案）與任務板 #93 內文都找不到「階段 A」這個詞。#92 §10 的分階段表用的名稱是「現在／定案／契約／場景與資料／Q1／Q2・Q5／收斂」，沒有 A、B 編號。要用「階段 A」這個說法的人，請在 #93 或 #92 留言補定義；本文先不猜。

**`mainline/q1q5` @ `10070eb` 已有的內容**（2026-10-20 檢查）：

| PR | Merge commit | 內容 | 與 Q1–Q5 的關係 |
| --- | --- | --- | --- |
| [#75](https://github.com/Polalalabear/amidst/pull/75) | `4f193e6` | Codex：受控場景 safe loader 與 v2 fixture API 骨架（`src/amidst/workbench/controlled_scene_*`） | 後端底座；#112 要在上面接 Q 端點 |
| [#80](https://github.com/Polalalabear/amidst/pull/80) | `052abb1` | Codex：2a，接入 A／B1 真實 RGB 與 scoped media token | 影格取得與媒體權杖；r003 素材，不是 r004 |
| [#74](https://github.com/Polalalabear/amidst/pull/74) | `7904a48` | Claude：workbench-v2 V2-1 外框、token、store、時鐘 | Q 線 UI 外框（#119 在此改裝） |
| [#71](https://github.com/Polalalabear/amidst/pull/71) | `b9c7cfb` | Claude：player-grid 純模組（1／2／4／8 格同步） | 播放格底座 |
| [#79](https://github.com/Polalalabear/amidst/pull/79) | `9b4c9b1` | Claude：workbench-v2 V2-2 api、不確定度驗證與 SYNTHETIC fixture | 資料層底座 |
| [#86](https://github.com/Polalalabear/amidst/pull/86) | `f62ab72` | Claude：Q1–Q5 契約 @ `3873ff2`（D65 核准） | **主線契約**（文件，不是程式） |
| [#92](https://github.com/Polalalabear/amidst/pull/92) | `b1a1b32` | Codex：Q1–Q5 第一版計畫、契約審查（D65 核准） | **主線計畫**（文件） |
| [#91](https://github.com/Polalalabear/amidst/pull/91) | `10070eb` | Claude：`AGENTS.md` 以 `mainline/q1q5` 為整合分支並指向 #93 | 規則（文件） |

合併順序（`git log --merges`）：#75 → #80 → #74 → #71 → #79 → #86 → #92 → #91。本文沒有重跑這些 PR 的測試。

**已開 Draft PR、未合併**（2026-10-20）：Codex 的 [#134](https://github.com/Polalalabear/amidst/pull/134)（#101 時間對應）、[#132](https://github.com/Polalalabear/amidst/pull/132)（#97 r004 修改表提案，Claude 審查「需修改」）、[#126](https://github.com/Polalalabear/amidst/pull/126)（預算）；Claude 的 [#127](https://github.com/Polalalabear/amidst/pull/127)（測試包 v0.2.1）、[#125](https://github.com/Polalalabear/amidst/pull/125)（規則例外，GitHub 狀態非 Draft）、[#90](https://github.com/Polalalabear/amidst/pull/90)（工作台設計）、[#82](https://github.com/Polalalabear/amidst/pull/82)（K7）、本 PR #83。

**還沒有的**：Q 線產品程式（時間對應以外的 Codex 任務尚未開 PR）、r004（D67 只授權建檔，尚未建）、偵測索引、兩層圖資料、Q3 解析、Q 端點、Q 線 UI、規則例外合併（G3）。

## 5. 時程估計

**結論：沒有可靠的日曆日期。**milestone「Q1–Q5 第一版」沒有到期日；#93 沒有任務工時；#92 沒有排程。以下只給**依賴結構的長度**（任務個數），不是工期。

### 5.1 假設

1. 依 #93 的相依圖與 gate；表列相依為準。
2. 一個任務算「一步」，**不估每步多久**（工時：`UNKNOWN`）。
3. 同一步內沒有相依的任務可以並行（Codex 與 Claude 各一個、一次一個任務，#93 自選規則第 3 點），所以實際會被兩人的產能拉長；這個產能限制本文**沒有**建模。D67 第 6 點允許疊分支，會縮短等待，但同樣沒有建模。
4. 使用者的決定與審閱需要的時間：`UNKNOWN`。G1、G2、G6、G7 已成立；目前最大的等待來源是 **G5 的渲染部分**（D67 不授權，要等磁碟 ≥ 12 GiB 後另問）、**G4**（O10／K7）與 **G3**（#125 的 Codex 審查）。
5. 契約 §8.2、§8.3 的修訂已併入 `3873ff2`；契約之後若再改版，測試包與設計要跟著改（重工量：`UNKNOWN`）。
6. 不含 r004 的渲染時間、模型推論時間、磁碟 gate（#92 的 D41：可用空間低於 12 GiB 不得開始渲染，低於 8 GiB 停止產製；#92 記錄 2026-10-20 的快照約 11.54 GiB、#126 記錄約 10.96 GiB，**都低於門檻**）。清出空間要多久：`UNKNOWN`。

### 5.2 關鍵路徑（任務步數）

| 路徑 | 步驟（相依，來自 #93） | 步數 | 擋在哪個 gate |
| --- | --- | --- | --- |
| 後端 Q 線 | （#94 ✅、G1 ✅）→ #101、#102、#103（`ready`，可並行）→ #108（Q4 證據；另需 #102、#103）→ #110（Controller；另需 #104、#107）→ #112（端點；另需 #106、#109）→ #124（端到端驗收） | 5 個任務步 | 無使用者 gate（G75 ✅）；#124 還要等其他鏈 |
| r004 資料 | #97（r004 修改表，PR #132 待修）→ #113（建檔與靜態校正匯出可做；**廣角小批 preview 要渲染**）→ #114（HSV 提案）→ #118（正式索引，另需 #98、#103、#115）→ #123（標註評估）／#128（組員標註）／#124 | 5 個任務步 | **G5 渲染部分 ❌**、磁碟 ≥ 12 GiB（D41） |
| 兩層圖 | #104（schema／loader）與 #113（r004 建檔）→ #116 → #124；#117 是 #116 的獨立檢查，**板上 #124 不直接依賴它** | #116 之後 2 個任務步（#116 另需 G4） | **G4 ❌** |
| Agent 模式 | #105、#110 → #111。**板上 #124 不依賴 #111**；`AGENT_SEQUENTIAL` 要不要進 Demo 的驗收，板上沒寫：`UNKNOWN` | #111 為最後一步 | **G3 ❌**（#125 合併） |
| 前端 | #100 ✅ → #119（T1，`ready`）→ #120／#121／#122（並行）→ #124 | #119 起 3 個任務步 | 無使用者 gate（G1、G7 ✅） |
| 組員 | #89（`ready`，獨立）；#128 ← #118；#129 ← #110、#115；#130 ← #124 | #89 一步；#128–#130 接在其上游之後 | 同 r004 資料鏈（渲染）與 #124 的前提 |

最長的是 r004 資料鏈與後端 Q 線，兩者在 #124 匯合；#124 要等 #112、#116、#118、#120、#121、#122 全部完成。**D67 之後，卡住整條 r004 鏈的是渲染授權與磁碟空間，不是契約。**

### 5.3 現在可以做、不用等使用者的事（Codex、Claude 兩條是 2026-10-20 D67 後的快照，以 label 與驗收計畫 §4 為準；組員條已更新到 2026-10-25）

- **Codex**（`ready`）：#101（Draft PR #134 已開）、#102、#103、#104、#105、#107、#98；#97 的 PR #132 要修 X1、X2；#131（finalization 搬移計畫，文件＋Draft PR，**不執行搬移**）。#113 的建檔與靜態校正匯出已由 D67 授權，但 #132 審查通過前不開始、渲染不做。
- **Claude**（`ready`）：#119（workbench-v2 T1）、#95（規則例外，PR #125 已開）；審查 Codex 的 Draft PR（#132、#134）。#99 由 #127 處理。
- **組員**（2026-10-25 更新）：T-1 r004 澄清 3 題的包已備好（LOCAL）；T-2 Q1／Q3 出題等 #149 修正；T-3 Q4 正式 T／F 等 CX-8 的正式輸出（[TEAM_ONBOARDING §4.2](TEAM_ONBOARDING.md)）。
- 其他是 `blocked`（等上游）或 `needs-auth`（#115）。

### 5.4 `UNKNOWN`

- 第一版 Demo 的目標日期、各任務工時、使用者審閱速度、清出磁碟空間所需時間、契約再改版時的重工量。
- 「更新 `main`」的條件之一（第一版 Demo 通過）尚未定義驗收門檻；實作 PR 合併檢查點未建立。
