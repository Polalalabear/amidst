# Q1–Q5 協作索引（驗收矩陣、文件地圖、驗證系統、基線、時程）

> 日期：2026-10-20（快照）。本文是**索引**，不是規格：不重抄 schema，每個條件都指向契約章節或計畫章節。與原文不一致時，以契約、計畫和 GitHub 原始決策留言為準。
> 即時狀態以 [#93 任務板](https://github.com/Polalalabear/amidst/issues/93)、各任務 issue 的 label 與 PR 狀態為準；本文的「目前狀態」欄是 2026-10-20 的快照，會過期。
> 找不到依據的寫 `UNKNOWN`。本文沒有執行任何程式、推論或渲染。

## 0. 先讀這幾點

1. **主線是 Q1–Q5**（D63、D63 修訂、D64）。2D→3D 重建線（2b–2d、CS-C、CS-D、#84、#85）暫停保留，不關、不刪。
2. **契約 #86 是草案，未核准**：現在是 `1d1e061`，**修訂中，待新 SHA**（Codex 要求修 §8.2、§8.3 兩處，見 [審查留言](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6291180958)）。核准前不寫任何產品程式（契約 §0.3 第 1 道 gate；含 `RULE_ONLY`）。
3. **整合分支是 `mainline/q1q5`**（預設分支、受保護、只用 merge commit）。`main` 不動，等第一版 Demo 通過且使用者授權。
4. 要做什麼：看 [#93](https://github.com/Polalalabear/amidst/issues/93) 的**自選規則**（摘要在 [TEAM_ONBOARDING §3](TEAM_ONBOARDING.md)）。

## 1. 驗收矩陣

怎麼讀這張表：

- **驗收條件**：取自契約 #86 @ `1d1e061`（**修訂中，待新 SHA**；§8.2、§8.3 會變）與 Codex 計畫 [#92](https://github.com/Polalalabear/amidst/pull/92) 的 §11「第一版完成條件」。這裡只寫重點，細節讀章節。**門檻數字一律「待約定」**（契約 §11；全部 PROPOSED，G6 未成立）。
- **任務**：[#93](https://github.com/Polalalabear/amidst/issues/93) 的任務 issue（#94–#124）與 #89。一個任務可橫跨多個 Q；每個 Q 只列它主要依賴的任務，完整對照以 #93 總表為準。
- **Gate**：[#93](https://github.com/Polalalabear/amidst/issues/93) 的 G1–G7、G75（定義見 §1.2）。
- **驗證**：測試包 = [#127](https://github.com/Polalalabear/amidst/pull/127) 的合約符合性測試包（只測契約層，見 §3）；審查 = 另一方的 PR 審查；瀏覽器驗收 = #124；使用者核准 = 檢查點或 issue 上的明確核准。
- **目前狀態**：2026-10-20 快照。**沒有任何 Q1–Q5 的產品程式存在**（契約未核准），所以沒有一格是「已驗收」。

### 1.1 逐 Q 驗收

| Q | 驗收條件（重點） | 來源 | 負責任務 | Gate | 驗證方式 | 目前狀態 |
| --- | --- | --- | --- | --- | --- | --- |
| **Q1** 依條件找相機 | ① 至少一台有車、一台無車的鏡頭，展示一個有支持的查詢和一個**支援類別**的零命中查詢；結果附模型、frame／camera／時間證據與取樣範圍 ② `status` 封閉清單（`READY`／`NO_MATCH`／`PARTIAL`／`UNSUPPORTED_CLASS`／`UNSUPPORTED_CONDITION`／`OUT_OF_RANGE`／`UNKNOWN`），`NO_MATCH` 只說「在已推論的影格中沒有找到」，不說「不存在」 ③ 三種「沒有」分開：條件不符（`no_match_cameras`）、沒推論（`not_evaluated_cameras`）、`MISSING` 格 ④ 排序 `first_match_us_asc → camera_id`，偵測數不進排序 ⑤ 手動輸入、預填、Q3 解析出的同一正規化請求，`output_sha256` 相同 ⑥ 類別別名表是封閉人工表，LLM 不能擴充；不支援的詞（例如「樹」）明列 | 契約 §6、§6.2、§6.3、§4；計畫 #92 §11 第 1 點 | 查詢模組 #109；依賴 #101（時間）、#102（store）、#103（索引）；端點 #112；UI #120（Q3 查詢列＋Q1 結果牆）；正式索引 #118 | G1；#112 另需 G75；#118 需 G6 | 測試包：`Q1_*` 六項、`TIME_COVERAGE_*`、`SCOPE_HASH_LINKS`；審查；瀏覽器驗收 #124；最終「有車／無車」要靠 r004 實際 RGB 的人工審核頁（測試包不證明辨識品質） | `#109` `blocked`（等 #101、#102、#103）；#120 `blocked`（等 #119）。契約修訂中 |
| **Q2** 在影片中找人 | ① 兩個 r004 事件案例展示：觀測、同鏡頭暫失、D28＋兩層圖合法候選、切鏡、無支持時回原鏡頭 ② 同鏡頭最小 IoU 連接器：只連 `person`、一對一匹配、缺格不內插、有歧義不硬接（`AMBIGUOUS_LINK`）、暫失門檻以**時長** `link_max_gap_us` 核定（取樣率改變不得默默改變暫失時長） ③ 狀態機 `PLAYING`／`TEMP_LOST`／`SEARCHING`／`SWITCHING`／`RETURNED_TO_ORIGIN`／`ENDED`，來源時間只往前走 ④ 身分一律 `UNCONFIRMED`；「沒偵測」不等於「已離開」 ⑤ 兩層圖與出口 ROI 的 hash 可核對，`PORTAL_R102`（`TOPOLOGICAL_ONLY`）不在任何路線 | 契約 §8.2（**修訂中**）、§8.5–§8.7、§5；計畫 #92 §11 第 3、5 點 | 連接器 #107；圖與候選 #104；Controller #110；r004 建檔 #113；事件 run #115；兩層圖資料 #116＋獨立檢查 #117；UI #121 | G1；#116 需 G4；#113、#115 需 G5 | 測試包：`SESSION_STATE_MACHINE`、`Q2_*` 三項、`DECISION_*`、`GRAPH_*`（**連接器 §8.2 的 `link` 紀錄沒有 schema，測試包查不了，U11**）；#117 獨立檢查；審查；瀏覽器驗收 #124 | #107 `blocked`、#110 `blocked`、#113／#115 `needs-auth`、#116 `blocked`、#117 `blocked` |
| **Q3** 理解使用者措辭 | ① 示例自然語言轉成有效的結構化查詢（Q1 或 Q2 請求），通過 strict schema 驗證 ② LLM 失敗退規則解析器（`PROVIDER_UNAVAILABLE`／`PROVIDER_TIMEOUT`／`INVALID_RESPONSE`），規則解析也失敗就 `PARSE_FAILED`，**不猜、不執行** ③ `NEEDS_CLARIFICATION` 附封閉表選項 ④ 詞語必須是使用者原文的片段，對到封閉表；時間換成來源微秒 ⑤ prompt、模型 digest、驗證結果都記錄；說明文字的 `cited_refs` 必須出自輸入，否則改模板 | 契約 §7（§7.1–§7.6）；計畫 #92 §11 第 2 點 | 薄 provider #105；解析 #106（依賴 #101、#105）；UI #120；測試集與評分器 #89（組員） | G1 | 測試包：`Q3_*` 六項、`EXPLANATION_CITED_REFS`（啟發式）；#89 的語意測試集（評 Q3 解析品質，與測試包互補）；審查；瀏覽器驗收 #124 | #89 `ready`；#105、#106 `blocked`（等 G1／#94） |
| **Q4** 模型判斷 2D 畫面是否含目標 | ① 只用偵測索引（RT-DETR＋上半身 HSV 摘要）；Qwen 是文字模型，不看影像；第一版無 VLM ② `target_presence` 封閉清單與**判定順序**：`MATCH_STRONG`／`MATCH_WEAK`／`PERSON_COLOR_UNKNOWN`／`PERSON_NO_COLOR_MATCH`／`NO_PERSON_DETECTED`／`PARTIAL_EVIDENCE`／`NOT_EVALUATED`；否定結果只在覆蓋完整時成立，沒推論的時段不能證明目標不在 ③ 切鏡進入點 `entry_observation_id` 由服務決定性選出，`timestamp_us ≥ decision_time_us`，播放時間不倒退 ④ 各授權鏡頭實際 RGB 的 RT-DETR 判斷，**不用 Blender 清單／GT 代答** ⑤ 衣服、廣角與遠距小框要有實測，不以「渲染完成」代替「辨識通過」 | 契約 §8.3（**修訂中**）、§4；計畫 #92 §11 第 2、5 點 | 索引產生器 #103；證據聚合 #108；HSV 參數提案 #114（依賴 r004 preview #113）；正式索引 #118；標註與評估 #123；UI #121 | G1；#118 需 G6 | **測試包不涵蓋 §8.3 的 `target_presence` 判定**（沒有對應檢查 ID；只有 `DECISION_SWITCH_GUARD` 用到它）；審查＋#123 的標註評估；瀏覽器驗收 #124。辨識品質只能靠 #123 與人工審核頁 | #103 `blocked`、#108 `blocked`、#114 `blocked`、#118 `blocked`、#123 `blocked`。§8.3 修訂中 |
| **Q5** 目標離開時是否切鏡 | ① 兩種模式 `RULE_ONLY`／`AGENT_SEQUENTIAL`：候選集合、順序、狀態機、紀錄格式相同，只差誰提出動作 ② 候選由兩層圖＋D28 原鍵（`relation_tier → overlap_area_m2_desc → camera_id`）**決定性**產生，Agent 不能改排序、不能發明候選 ③ Agent 只在合法 top-k 內決定切或不切；非法提交被拒且仍計預算；有輪數與時間上限 ④ 超限就由決定性規則兜底，兜底只在同一快照的前 `top_k` 內找，**不得因為 top-k 沒有支持就宣告「所有鏡頭都查無結果」** ⑤ 回應標 `agent_attempted`、`agent_used`、`decision_source`、`fallback_used`／`fallback_reason`；prompt、模型 digest 可查 ⑥ 切鏡 guard `switch_min_presence` 未核定前，Demo 只能 `RULE_ONLY` 顯示候選與證據，不自動切換 | 契約 §8.1、§8.4、§8.6、§8.7、§5.4、§0.3；計畫 #92 §11 第 3、4 點；預算提案 [#126](https://github.com/Polalalabear/amidst/pull/126) | 圖與候選 #104；Controller #110；Agent 模式 #111（依賴 #105、#110）；Agent 例外條文 #95；UI #121 | G1；`AGENT_SEQUENTIAL` 另需 **G3**（#125 經使用者核准合併）；#116 需 G4 | 測試包：`CANDIDATE_*`、`DECISION_*`、`SESSION_STATE_MACHINE`、`Q2_RESPONSE_VS_DECISIONS`、`AGENT_DECISION_FORMAT`、`COMMON_AGENT_FIELDS`；審查；瀏覽器驗收 #124。**切鏡好不好、有沒有誤切，測試包不評價**（人工審核頁） | #95 `ready`（PR #125 已開，描述寫 Draft、不合併；GitHub 狀態為非 Draft）；#110、#111 `blocked`。預算 #126 皆 PROPOSED |
| **共通**（契約、規則、驗證本身） | 契約 #86 定稿並經 Codex 確認 SHA、使用者核准；規則例外 PR 合併；測試包固定版本對齊；GT 隔離（§9）；參數組核定（§11） | 契約 §0.3、§9、§11、§14；#88 | #94（契約定稿）、#96（審查 #92）、#95（規則例外）、#99（測試包）、#98（參數組提案）、#97（r004 修改表） | G1、G2、G3、G6 | 審查；使用者在 [#88](https://github.com/Polalalabear/amidst/issues/88) 核准；測試包版本對契約 SHA | #94、#96、#97 `ready＋in-progress`；#99 `blocked`（等 #94），PR #127 已開、仍綁 `258c7e2`；#98 `blocked` |

### 1.2 Gate 一覽（#93 的 G1–G7、G75）

#93 本文的「目前」欄是建立時（2026-10-20 早）的快照。下表**加上**之後已知的事實；以各 gate 的連結為準。

| Gate | 內容 | 成立？（2026-10-20 快照） |
| --- | --- | --- |
| G1 | #88：使用者核准修訂稿 #92 與契約 #86（核准前不建 r004、不渲染、不改產品程式） | 未成立 |
| G2 | 契約 #86 新版固定 SHA，且 Codex 再確認 | 未成立（`1d1e061` 修訂中，待新 SHA） |
| G3 | DEVELOPMENT_RULES 的 Q1–Q5 Agent 有界例外 PR 經使用者核准合併 | 未成立（PR [#125](https://github.com/Polalalabear/amidst/pull/125) 已開，未合併） |
| G4 | O10 用途核准（D62）；r004 改動範圍需重做 K7 類型檢查 | 未成立 |
| G5 | r004 建檔／渲染的使用者明確授權 | 未成立 |
| G6 | §11 參數組經使用者核定 | 未成立（全部 PROPOSED；預算提案 #126 也是 PROPOSED） |
| G7 | #90 設計的待決 U-1–U-8 由使用者決定 | 未成立；但 **U-1 已有進展**：#74、#79、#71 已合入 `mainline/q1q5`（§4） |
| G75 | #75、#80 經審查並合入 `mainline/q1q5` | **PR 已合入**（§4）。#93 本文仍寫未成立；板上是否更新、使用者核准紀錄在哪：`UNKNOWN`（待協調者／board 更新） |

## 2. 文件地圖

| 文件 | 管什麼 | 位置（固定 SHA） |
| --- | --- | --- |
| **契約 #86** `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md` | Q1–Q5 第一版的權威規格草案：共通回應欄位 §2.3、時間 §3、偵測索引 §4、兩層圖 §5、Q1 §6、Q3 §7、Q2／Q4／Q5 §8、GT 隔離 §9、儲存 §10、參數表 §11、待決 §13、待使用者決定 §14 | PR [#86](https://github.com/Polalalabear/amidst/pull/86)（`claude/q1q2-contract-v1`）；現為 [`1d1e061`](https://github.com/Polalalabear/amidst/blob/1d1e061432a61a6216087020a79ce695a0b6e5f2/docs/contracts/Q1_Q2_FIRST_DEMO_V1.md)，**修訂中，待新 SHA**；前一版 `258c7e2`（#127 測試包仍綁這版）。核准前不合併 |
| **契約審查** `docs/engineering/Q1_Q5_CONTRACT_REVIEW_20261020.md` | Codex 對 Q-01–Q-19 的回覆與 7 項必要修正 | PR [#92](https://github.com/Polalalabear/amidst/pull/92)；契約引用 `80f5ca2`，PR 現 head `86877b2`（多了 D41 磁碟 gate 與 worktree 清理紀錄） |
| **計畫（Codex 修訂稿）** `docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md` | 工作計畫：兩層圖、RT-DETR／HSV、r004 修改提案、分工與實作順序（§10）、第一版完成條件（§11） | PR [#92](https://github.com/Polalalabear/amidst/pull/92)，[`80f5ca2`](https://github.com/Polalalabear/amidst/blob/80f5ca2137f077f359bc0f7587d057ae58bab75a/docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md)（契約引用的版本）；現 head `86877b2` |
| **工作台設計** `docs/agents/WORKBENCH_V2_Q1Q5_DESIGN.md` | workbench-v2 的 Q1–Q5 畫面、審核模式（§3）、Demo 與審核模式差異、實作切分 T1–T4（§5）、待使用者決定 U-1–U-8（§6） | PR [#90](https://github.com/Polalalabear/amidst/pull/90)，[`767a092`](https://github.com/Polalalabear/amidst/blob/767a092f874d3bba5e279938e63b72e9df5c0e3d/docs/agents/WORKBENCH_V2_Q1Q5_DESIGN.md)。它依據的契約是 `258c7e2`，欄位對應待對齊 |
| **合約符合性測試包** `docs/evaluation/Q1Q5_CONFORMANCE_KIT.md` | 54 項契約層檢查、24 項契約 UNKNOWN（U01–U24）、不能證明什麼 | PR [#127](https://github.com/Polalalabear/amidst/pull/127)，`7809649`；綁契約 `258c7e2`，之後會對齊 |
| **規則例外** `docs/specs/DEVELOPMENT_RULES.md`（`docs/DEVELOPMENT_RULES.md` 是指向它的 symlink） | D64 Q1–Q5 Agent 有界例外條文 | PR [#125](https://github.com/Polalalabear/amidst/pull/125)，`1f30232`；未合併 |
| **搜尋／兜底預算提案** `docs/engineering/Q1_Q5_SEARCH_BUDGET_PROPOSAL_20261020.md` | 6 項上限的 PROPOSED 值；已對齊 `1d1e061` §8.6 | PR [#126](https://github.com/Polalalabear/amidst/pull/126)，`5838108`；全部 PROPOSED |
| **任務板** | 31 個任務（#94–#124）＋#89、gate、自選規則、相依圖 | Issue [#93](https://github.com/Polalalabear/amidst/issues/93)（置頂）；milestone「Q1–Q5 第一版」（[milestone 2](https://github.com/Polalalabear/amidst/milestone/2)，無到期日） |
| **檢查點** | 使用者核准計畫與契約 | Issue [#88](https://github.com/Polalalabear/amidst/issues/88)。實作 PR 的合併檢查點（第一版 Demo 驗收）：尚未建立，`UNKNOWN`（#93 同） |
| **整理紀錄** | D63 後的盤點與暫停項 | Issue [#87](https://github.com/Polalalabear/amidst/issues/87) |
| **決策索引** | D1–D64 一句摘要與原始留言連結 | [DECISION_INDEX](DECISION_INDEX.md)；D63、D63 修訂、D64 的原文是 #65／#81／#86 上標題為「## D63」「## D63 修訂」「## D64」的留言 |
| **規則** | GT 隔離、來源資產、不確定度、研究邊界、角色分工、Git 流程、「實際產出」範本 | `AGENTS.md`、`CLAUDE.md`、`docs/DEVELOPMENT_RULES.md`（見 [TEAM_ONBOARDING §1](TEAM_ONBOARDING.md)）。注意：`mainline/q1q5` 上的 `AGENTS.md` 仍寫舊整合分支，[#91](https://github.com/Polalalabear/amidst/pull/91) 才改成 `mainline/q1q5`（未合併） |
| **受控場景契約 v1.1**（Q 契約沿用其 §2、§2.1、§2.3、§3.6、§3.7、§6.1、§7） | 時間慣例、hash、缺格、門、鏡頭、D28 排序、GT 隔離 | PR [#65](https://github.com/Polalalabear/amidst/pull/65)，已核准版本 `98451bd` |
| **系統導覽／組員上手** | 分層、名詞、組員流程 | [SYSTEM_OVERVIEW](SYSTEM_OVERVIEW.md)、[TEAM_ONBOARDING](TEAM_ONBOARDING.md)（本 PR #83） |
| **K7 r003 驗證** | `PORTAL_R102` 只當拓撲連通的依據；O10 的**建議**，不是核准 | PR [#82](https://github.com/Polalalabear/amidst/pull/82) `6e689f9`（Draft） |

## 3. 驗證系統

目的：Codex、Claude 與組員各做各的檔案集合，靠**可重跑的檢查**而不是靠互相相信來合流。每一層擋不同的錯，**沒有任何一層證明辨識品質或劇情正確**。

| 機制 | 擋什麼 | 在流程的哪裡 | 誰負責 | 做不到什麼 |
| --- | --- | --- | --- | --- |
| **合約符合性測試包**（[#127](https://github.com/Polalalabear/amidst/pull/127)，任務 #99） | 回應形狀、封閉清單、共通欄位、hash 可重算、候選順序（D28）、決策合法性與狀態機、時間涵蓋、`gt_read=false` 宣告 | Codex 的每個產品 PR 送出前，必須跑**固定版本**的測試包（#126 描述也這樣要求）；缺的參數回 `SKIPPED_PARAM_UNSET`，整體 `INCOMPLETE`，不算通過 | 維護：Claude（#99）。使用：Codex（自己跑）。Codex **不直接改**測試包；認為測試錯就開 issue 附報告，Claude 改（測試包 §9） | 不證明辨識品質、劇情正確、真實資料、GT 隔離的實際行為、身分、延遲；不涵蓋 §8.2 連接器 `link` 紀錄與 §8.3 `target_presence` 判定（U11）；契約修訂後要同步改版 |
| **交叉審查** | 規格符合、不變量、檔案集合越界、GT 洩漏、過度宣稱 | 每個 PR 都要另一方審查；合併前還要使用者核准（AGENTS.md） | 作者不審自己的 PR：Codex 的 PR 由 Claude 審（Opus／high，小型或純文件用 medium，見 `CLAUDE.md` 模型表）；Claude 的 PR 由 Codex 審；組員的 PR 由 Claude 或 Codex 審（指派：`UNKNOWN`，由使用者決定） | 審查是人為判斷，不可重跑；不取代測試包 |
| **獨立檢查**（#117） | r004 兩層圖與出口 ROI 是否符合靜態依據（K7 類型：只用核准的靜態幾何、不含人物的靜態畫面） | 兩層圖與 ROI 凍結 hash 之前；契約 §14 第 4 題建議在 r004 **事件渲染之前**凍結 | Claude（作者是 Codex，故由 Claude 獨立查） | 只檢查靜態圖依據；不是物理通行認證（通行性在核准範圍外一律 `UNKNOWN`） |
| **檢查點 gate**（#88、G1–G7、G75） | 還沒被使用者核准的東西被合併或被當成前提 | 檢查點範圍內的東西在使用者於檢查點 issue 核准前不合併；`blocked`／`needs-auth` 的任務不做 | 使用者核准；Claude 維護 label 與 #93 | 不審內容正確性，只管授權；「PR 能開、能被審，不能合併」 |
| **「實際產出」紀錄**（AGENTS.md） | 把規劃和結果混為一談；過度宣稱 | 每個任務的 PR 描述**與** issue 留言都附（Model／effort、PR／commits、Files changed、Commands run and results、Artifacts、Verified、Not verified、Deviations）；沒有就寫 `NONE`／`UNKNOWN` | 作者（Codex、Claude、組員自己的 agent）；審查者檢查「Not verified」有沒有誠實 | 是自述，不是證明；要靠審查與可重跑的指令核對 |
| **GT 隔離** | Ground Truth、renderer 軌跡、visibility、depth、事件腳本、產製路線進入推論、索引、圖、Agent、prompt、參數 | 全程。契約 §9 的表：偵測索引只讀 safe RGB；兩層圖只讀核准的靜態依據；Agent／LLM 看不到人物設定與事件腳本；第一版**不讀產製路線做驗收**（Q-12）；HSV 參數只用獨立 preview 的 RGB 裁切 | 所有人。實作面：Codex 的服務不得讀 GT；Claude 的測試包用 `NO_FORBIDDEN_CONTENT` 掃禁用內容；組員拿不到 GT（見 [TEAM_ONBOARDING §5、§7](TEAM_ONBOARDING.md)） | 回應裡的 `provenance.gt_read: false` 只是自己的宣告；真的沒讀要靠程式審查與行為探測（`PROBE_FORBIDDEN_FIELD_REJECTED`），不能靠報告擔保 |
| **瀏覽器驗收**（#124） | 畫面上能不能走完 Q1–Q5 流程、狀態標示是否誠實（`MISSING`／`UNKNOWN`／`SYNTHETIC` 不被畫成觀測） | 等後端端點、r004 資料與 UI 都就緒（#112、#116、#118、#120、#121、#122） | Claude | 工程驗收，不是研究級評估；SYNTHETIC 資料下的人工 PASS 照實記錄但不算驗收（#90 U-4 建議） |
| **人工審核頁**（#122，審核模式） | 劇情正確、辨識品質、切鏡好壞（測試包明說不證明的部分） | 資料就緒後由使用者或審核人逐項判斷 | Claude 做工具；使用者判斷 | 預期清單放 repo 外（#90 U-2、U-3 待決） |

## 4. 階段 A 基線

**階段 A 的定義：`UNKNOWN`。**在契約 #86 @ `1d1e061`、計畫 #92（`80f5ca2` 與 `86877b2`）、任務板 #93、設計 #90 都找不到「階段 A」這個詞（用 `grep` 搜過）。#92 §10 的分階段表用的名稱是「現在／定案／契約／場景與資料／Q1／Q2・Q5／收斂」，沒有 A、B 編號。要用「階段 A」這個說法的人，請在 #93 或 #92 留言補定義；本文先不猜。

**`mainline/q1q5` @ `9b4c9b1` 已有的內容**（都是進入 Q1–Q5 之前就存在的底座；**沒有任何 Q1–Q5 專屬的產品程式**）：

| PR | Merge commit | 內容 | 與 Q1–Q5 的關係 |
| --- | --- | --- | --- |
| [#75](https://github.com/Polalalabear/amidst/pull/75) | `4f193e6` | Codex：受控場景 safe loader 與 v2 fixture API 骨架（`src/amidst/workbench/controlled_scene_*`） | 後端底座；#112 要在上面接 Q 端點 |
| [#80](https://github.com/Polalalabear/amidst/pull/80) | `052abb1` | Codex：2a，接入 A／B1 真實 RGB 與 scoped media token | 影格取得與媒體權杖；r003 素材，不是 r004 |
| [#74](https://github.com/Polalalabear/amidst/pull/74) | `7904a48` | Claude：workbench-v2 V2-1 外框、token、store、時鐘 | Q 線 UI 外框（#119 在此改裝） |
| [#79](https://github.com/Polalalabear/amidst/pull/79) | `9b4c9b1` | Claude：workbench-v2 V2-2 api、不確定度驗證與 SYNTHETIC fixture | 資料層底座 |
| [#71](https://github.com/Polalalabear/amidst/pull/71) | `b9c7cfb` | Claude：player-grid 純模組（1／2／4／8 格同步） | 播放格底座 |

合併順序（`git log`）：#75 → #80 → #74 → #71 → #79。本文沒有重跑這些 PR 的測試。

**還沒有的**：Q1–Q5 契約核准、r004、偵測索引、兩層圖資料、Q3 解析、Q 端點、Q 線 UI、規則例外、參數組核定。

## 5. 時程估計

**結論：沒有可靠的日曆日期。**milestone「Q1–Q5 第一版」沒有到期日；#93 沒有任務工時；#92 沒有排程。以下只給**依賴結構的長度**（任務個數），不是工期。

### 5.1 假設

1. 依 #93 的相依圖與 gate；表列相依為準。
2. 一個任務算「一步」，**不估每步多久**（工時：`UNKNOWN`）。
3. 同一步內沒有相依的任務可以並行（Codex 與 Claude 各一個、一次一個任務，#93 自選規則第 3 點），所以實際會被兩人的產能拉長；這個產能限制本文**沒有**建模。
4. 使用者核准（G1、G3、G4、G5、G6、G7）與使用者審閱需要的時間：`UNKNOWN`。它們是目前最大的等待來源。
5. 契約 §8.2、§8.3 修訂後可能再引起欄位變動，測試包與設計要跟著改（重工量：`UNKNOWN`）。
6. 不含 r004 的渲染時間、模型推論時間、磁碟 gate（#92 的 D41：可用空間低於 12 GiB 不得開始渲染，低於 8 GiB 停止產製；#92 記錄 2026-10-20 的快照約 11.54 GiB、#126 記錄約 10.96 GiB，**都低於門檻**，仍不能開始 r004 或 preview 渲染）。清出空間要多久：`UNKNOWN`。

### 5.2 關鍵路徑（任務步數）

| 路徑 | 步驟（相依，來自 #93） | 步數 | 擋在哪個 gate |
| --- | --- | --- | --- |
| 後端 Q 線 | #94（契約定稿）→ **G1** → #102、#103（store、索引，可並行）→ #108（Q4 證據；另需 #94）→ #110（Controller；另需 #104、#107）→ #112（端點；另需 #106、#109）→ #124（端到端驗收） | 6 個任務步＋G1 | G1、G75（#112，PR 已合入） |
| r004 資料 | #97（r004 修改表）→ **G1、G5** → #113（r004 建檔、preview）→ #114（HSV 提案）→ **G6** → #118（正式索引）→ #123（標註評估）／#124 | 5 個任務步＋G1、G5、G6 | G1、G5、G6 |
| 兩層圖 | #104（schema／loader，依賴 #94）與 #113（r004 建檔）→ #116 → #124；#117 是 #116 的獨立檢查，**板上 #124 不直接依賴它** | #116 之後 2 個任務步（#116 另需 G4） | G4 |
| Agent 模式 | #105、#110 → #111。**板上 #124 不依賴 #111**；`AGENT_SEQUENTIAL` 要不要進 Demo 的驗收，板上沒寫：`UNKNOWN` | #111 為最後一步 | **G3**（#125 合併） |
| 前端 | #100（U-1，PR 已合入）→ #119（T1）→ #120／#121／#122（並行）→ #124 | #119 起 3 個任務步（#119 需 G1、G7） | G1、G7 |

最長的是 r004 資料鏈與後端 Q 線，兩者在 #124 匯合；#124 要等 #112、#116、#118、#120、#121、#122 全部完成。

### 5.3 現在可以做、不用等使用者的事（2026-10-20 快照）

- Codex：#97（r004 修改表，只寫文件，`ready＋in-progress`）。
- Claude：#94（契約定稿，進行中）、#96（審查 #92，進行中）、#95（規則例外 PR，已開 #125）。
- 組員：#89（Q3 測試集與評分器，`ready`）。
- 其他全部是 `blocked`（等 #94 或 G1）或 `needs-auth`。

### 5.4 `UNKNOWN`

- 第一版 Demo 的目標日期、各任務工時、使用者審閱速度、清出磁碟空間所需時間、契約修訂後的重工量。
- 「更新 `main`」的條件之一（第一版 Demo 通過）尚未定義驗收門檻（參數 G6）；實作 PR 合併檢查點未建立。
