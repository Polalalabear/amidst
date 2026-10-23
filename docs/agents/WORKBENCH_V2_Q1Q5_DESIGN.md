# 工作台 v2：Q1–Q5 主線畫面設計（含審核模式）

狀態：**DRAFT，等使用者核准後才實作。**本文只是設計，沒有任何程式碼。文中的端點路徑、元件檔名與尺寸都是提案；標 `UNKNOWN` 的是契約或後端還沒定的部分。

- 撰寫：Claude Code（Opus 5.5／high），2026-10-20。
- 範圍：`frontend/workbench-v2/` 的 Q1–Q5 畫面、Demo 模式與審核模式。3D 重現線依 D63 (a) 暫停，本文不設計任何 3D 畫面。
- 不在範圍：後端、Agent、偵測索引、兩層圖的產生（都屬 Codex）；給 Codex 自測用的「合約符合性測試包」（另一個 session 在寫，路徑 `UNKNOWN`）。

## 0. 依據

### 0.1 讀過的版本

| 來源 | 版本 | 本文用到的部分 |
| --- | --- | --- |
| 契約草案 `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md`（[#86](https://github.com/Polalalabear/amidst/pull/86)，`claude/q1q2-contract-v1`） | **`258c7e2`**（DRAFT，未經 Codex 確認） | §2.3 共通回應欄位、§3 時間對應、§6 Q1、§7 Q3、§8 Q2／Q4／Q5、§9 GT 隔離、§13 待決 |
| v2 設計（[#72](https://github.com/Polalalabear/amidst/pull/72)，`claude/workbench-v2-design`） | `c4dbd46` | 只取 §1 原則 1、2、5、7，§4.1 外框，§4.2 側欄，§5.1 色彩 token，§5.2 字體，§5.4 SYNTHETIC，§5.7 文案，§6.1 模組分法。3D 部分（§4.4 的 3D、§5.3.1、§5.5）不用 |
| V2-1 外框（[#74](https://github.com/Polalalabear/amidst/pull/74)，`claude/wb2-shell`） | `72cc61e` | `tokens.mjs`、`store.mjs`、`layout.mjs`、`clock.mjs`、`shell-view.mjs`、`index.html`、`style.css` |
| V2-2 api 與 fixture（[#79](https://github.com/Polalalabear/amidst/pull/79)，`claude/workbench-v2-api`） | `3677135` | `api.mjs` 的 `createEpoch`、`apiError`、`errorFromBody`、fixture／live 切換、`validateBootstrap` 的 `data_origin` |
| player-grid（[#71](https://github.com/Polalalabear/amidst/pull/71)，`claude/player-grid`） | `7412bc4` | `layoutFor`、`createGridState`、`pageView`、`expectedFrame`、`toDisplayModel`、`renderGrid` |
| CS-B 人工審查頁（[#78](https://github.com/Polalalabear/amidst/pull/78)，`claude/cs-b-review-page`） | `6db93f5` | 只沿用用語與操作：`PASS`／`FAIL`／`UNSURE`／未審、`p`／`f` 快捷鍵、進度列。不 import 它的檔案 |
| D63 | [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6285089392)、[#81 留言](https://github.com/Polalalabear/amidst/pull/81#issuecomment-6285089691)，2026-10-20T06:44Z | (a) 主線、v2 外框沿用；(d) HSV 顏色訊號、身分 `UNCONFIRMED` |
| D63 修訂、D64 | **撰寫時（2026-10-20）在 #65、#81、#86 上都還沒有以「## D63」「## D64」開頭的新留言。**以下照協調者 brief 的摘要，原文貼出後如有不同，本文改版 | 見 §0.2 |

三個實作 PR（#71、#74、#79）都還是 Draft，沒有合入 `mainline/q1q5`（`f481fe0`）。本文的實作任務依賴它們，合併方式列為待決 U-1。

### 0.2 D63 修訂與 D64 的摘要（未貼出，依 brief）

- **D63 修訂**：主線擴為 Q1–Q5。Q1 依條件找相機；Q2 找畫面中某個人（固定鏡頭連續切換，仿《惡靈古堡 1》的固定機位）；Q3 理解語意；Q4 模型以自己的辨識判斷畫面是否含目標；Q5 目標離開鏡頭時判斷是否切鏡。
- **D64**：Agent 可以在合法 top-k 內決定切鏡，有輪數與時間上限，超限由規則兜底。Q4 第一版只用 RT-DETR＋HSV。
- 契約 §0.3 寫明：DEVELOPMENT_RULES 第 57、62 行修訂或列例外之前，Demo 只能啟用 `RULE_ONLY`。D64 是否已經解除這一條，本文不判斷（待決 U-6）。UI 兩種 `switch_mode` 都要能顯示。

### 0.3 使用者的要求（brief 轉達）

1. 審核頁整合在正式 Demo 頁面，做成審核模式。兩種模式共用 Q1 結果牆、Q2 切鏡主畫面與時間軸、Q3 解析結果、Q5 逐步紀錄。
2. 審核模式多出逐項 PASS／FAIL／備註，可匯出審核 JSON（帶回應 `output_sha256`、契約版本、審核人、時間）。
3. 劇情預期清單只從本機另一個檔案載入；後端與推論程式不讀；Demo 模式完全不載入。
4. 審核模式只讀，不改 API 請求；同一查詢在兩種模式下的 `output_sha256` 相同。
5. 畫面上分清觀測、推論、`MISSING`、`UNKNOWN`、「搜尋中／暫失」、「規則兜底」；身分一律 `UNCONFIRMED`。
6. 可以先用 SYNTHETIC 或錄好的回應驅動，後端接上後直接切換資料來源。

## 1. 畫面配置與操作流程

### 1.1 整體外框（沿用 #74）

外框照 #72 §4.1：頂欄、左側圖示列與面板、主要區域、緊貼其下的時間列、底部常駐圖例。改動只有三處：

1. 頂欄的模式鈕 `[瀏覽][查找][Demo]` 換成**任務鈕** `[Q1 找相機][Q2 找人]`。Q3 是共用的查詢列，Q4、Q5 在 Q2 裡面，不另設任務鈕。
2. 頂欄下方加一條 **Q3 查詢列**（40 px），兩個任務共用。
3. 主要區域上方的格數切換只在 Q1 出現；Q2 是單一主畫面加候選欄。

```text
┌ 資料來源條 24 px：SYNTHETIC／RECORDED 錄製回應（LIVE 時不出現）──────────────────────────────┐
├ 頂欄 44 px：AMIDST │ 場景▾ r004 │ run_id │ 展示時鐘 13:00–13:01（Asia/Taipei）│ [Q1 找相機][Q2 找人] │ 審核模式 ▣ │
├ Q3 查詢列 40 px：[ 穿紅衣服的人在下午 1 點到 1:30 經過哪裡？        ] [解析] │ 解析：LLM ▪ │ 結構化查詢 ▾ │
├────┬──────────────┬─────────────────────────────────────────────────────────────────────────┤
│ ≡  │ 面板 300 px    │ 主要區域標題 32 px：任務名 │ status │ 回應來源列（§1.6）                         │
│ Q1 │ ・查詢條件     ├─────────────────────────────────────────────────────────────────────────┤
│ Q2 │ ・逐步紀錄     │                                                                         │
│ 證據│ ・證據         │       Q1：結果牆        或       Q2：主畫面＋候選欄                          │
│ 來源│ ・來源與隔離   │                                                                         │
│ 審核│ ・審核（僅審核模式）├─────────────────────────────────────────────────────────────────────────┤
│    │              │ 時間列 112 px：來源 t 12.400 s／60 s │ 展示時鐘 13:00:12 │ ▶ 步進 │ 速度 │ 軌道   │
├────┴──────────────┴─────────────────────────────────────────────────────────────────────────┤
│ 圖例 28 px：觀測 ▭  推論 ▯  MISSING ╱╱  UNKNOWN ⋯?  暫失 ┈  規則兜底 ⓡ  SYNTHETIC      身分 UNCONFIRMED │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

- 1440×900 不捲動：資料來源條 24＋頂欄 44＋查詢列 40＋標題 32＋時間列 112＋圖例 28 ＝ 280 px，主要區域約 620 px 高。LIVE 時沒有資料來源條，多 24 px。
- 「審核模式 ▣」只是**狀態標籤**，不是按鈕；審核模式只能用網址進入（§3.1）。Demo 模式不顯示這個標籤，也沒有「審核」圖示。
- 時間讀數同時寫**來源時間**（`t 12.400 s`，等寬字）和**展示時鐘**（契約 §3.1 `DECLARED_DEMO_CLOCK`）。展示時鐘旁固定寫「展示時鐘」，不寫成拍攝時間。run 沒有 `clock_mapping` 時只顯示來源時間，牆鐘位置寫 `UNKNOWN · CLOCK_MAPPING_MISSING`。
- 窄版（< 760 px）沿用 #72 §4.2；Q2 的候選欄改到主畫面下方。只保證不破版。

### 1.2 Q3 查詢列（兩個任務共用）

```text
┌ Q3 ─────────────────────────────────────────────────────────────────────────────────────────┐
│ [ 穿紅衣服的人在下午 1 點到 1:30 經過哪裡？                         ] [解析]  PARSED · 解析：LLM  │
├ 展開「結構化查詢 ▾」後（面板內，可編輯）─────────────────────────────────────────────────────┤
│ intent      FIND_PERSON → Q2                                                                │
│ 類別        人 → person                          （別名表 class_alias@…）                     │
│ 顏色        紅 → red · 最低 STRONG                 （color_vocabulary@…）                      │
│ 時間        「下午 1 點」「1:30」→ 2026-11-01 13:00–13:30 +08:00（日期、時區取自 clock_mapping）    │
│             → 來源 [0, 60 000 000) µs · 時間只部分涵蓋：13:01–13:30 沒有資料                    │
│ 未對上的詞   （無）                                                                           │
│ LLM         qwen2.5:7b-instruct · digest 3f2a… · prompt 9c1e… · 嘗試 1 · 驗證 PASS             │
│ [以此查詢執行]  [重設]                                                                       │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

操作流程：

1. 使用者輸入句子，按「解析」或 Enter，送 `q3-parse-request.v1`（§7.1）。
2. 依 `q3-parse-response.v1` 的 `status`（§7.4）：
   - `PARSED`：顯示結構化查詢，依 `intent` 切到 Q1 或 Q2 任務並執行（契約 Q-09 的暫定處理：直接執行並顯示；見待決 U-7）。
   - `NEEDS_CLARIFICATION`：顯示 `clarification` 的問題與選項按鈕（選項來自封閉表）；**不執行**。
   - `UNSUPPORTED_CLASS`／`UNSUPPORTED_CONDITION`：顯示原因與「支援的類別」連結（`supported_classes_ref`）；不執行。
   - `PARSE_FAILED`／`TIME_EXPRESSION_INVALID`：顯示「請改寫，或用下方表單」；不執行、不猜。
3. 「解析：LLM」或「解析：規則 ⓡ」的徽章讀 `parsed_by`。規則解析時旁邊加 `fallback_reason`（`PROVIDER_UNAVAILABLE`、`PROVIDER_TIMEOUT`、`INVALID_RESPONSE`）。
4. 使用者改結構化查詢後按「以此查詢執行」：送出的是 Q1 或 Q2 請求，`origin: MANUAL`。正規化請求相同時 `output_sha256` 必須相同（§6.1 `origin`），審核模式會核對這一點（§3.3 的自動檢查 `C-ORIGIN`）。
5. LLM 說明文字（§7.5）放在主要區域底部的字幕條，標「說明（LLM，不進 hash）」；`cited_refs` 可點，跳到對應的結果或決策。說明被丟棄時標「模板說明 ⓡ · EXPLANATION_INVALID」。

### 1.3 Q1 結果牆

```text
┌ 主要區域標題：Q1 找相機 │ PARTIAL · TIME_SCOPE_PARTIAL │ 排序依據：第一次相符時間 → camera_id（建議檢視順序，不是機率） │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ ⚠ 只涵蓋 13:00–13:01；13:01–13:30 沒有資料，不代表沒有車（resolved_scope.time_coverage）      │
├─ 相符（results）──────────────────────────────────────────────────────────────────────────┤
│ ┌#1 CAM_OUT─────────────┐ ┌#2 CAM_GATE────────────┐ ┌#3 …                 ┐              │
│ │ [代表畫面＋bbox 觀測框] │ │ [代表畫面＋bbox]       │ │                     │              │
│ │ t 2.000–9.400 s        │ │ t 14.2–15.0 s         │ │                     │              │
│ │ 片段 ▭▭▭▭▭░░▭  37/38 格 │ │ 片段 ▭  4/4 格         │ │                     │              │
│ │ 涵蓋 已推論 300 · 缺 0  │ │ 涵蓋 … · MISSING 3 ╱╱  │ │                     │              │
│ │ [播放片段] [設為 Q2 起點]│ │                       │ │                     │              │
│ └───────────────────────┘ └───────────────────────┘ └─────────────────────┘              │
├─ 已推論、條件不符（no_match_cameras）── CAM_CORR（300 格已推論）  CAM_R2（…）                  │
├─ 未評估（not_evaluated_cameras）────── CAM_R1 ⋯? NOT_INFERRED                                │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

- 卡片排列用 #71 的 `layoutFor`、`pageView`（1／2／4／8 格與分頁），每格內容換成結果卡。卡片順序就是 `results[].rank`，UI 不重排。
- 三種「沒有」**分成三區，不合併**（§6.3）：相符、已推論但不符、未評估；`MISSING` 的格數只出現在卡片的涵蓋列。`NO_MATCH` 的文案固定是「在已推論的影格中沒有找到」，不寫「不存在」。
- `status` 不是 `READY` 時，標題列顯示 `status · reason`，並在牆頂放一條說明（`PARTIAL`、`OUT_OF_RANGE`、`UNKNOWN`、`GRAPH_NOT_APPROVED`）。`OUT_OF_RANGE` 時牆是空的，寫「請求時間和資料沒有交集，沒有查詢」，不寫「查無結果」。
- 片段列：每個 `matched_segments[]` 畫成觀測色實心段，旁邊寫 `matched_frames/evaluated_frames`。說明一行：「片段表示這段時間取樣到的格有相符，不表示每一格都相符」。
- 「播放片段」：主要區域切成單格播放該鏡頭，時間跳到片段起點（`range_us[0]`）。「設為 Q2 起點」：用代表畫面的 `observation_ids[0]` 組 `seed.kind: OBSERVATION` 的 Q2 請求，切到 Q2 任務（`decided_by: USER`）。
- `next_cursor` 不是 `null` 時，牆底有「載入更多（還有 n 筆）」；`results_total` 與 `returned_count` 都顯示。

### 1.4 Q2 主畫面與 Q5 切鏡

Q2 的版面是「一台固定鏡頭的大畫面＋右側候選欄」，像《惡靈古堡 1》的固定機位：主畫面一次只看一台鏡頭，目標離開後**硬切**到下一台，不做轉場動畫。

```text
┌ 主要區域標題：Q2 找人 │ COMPLETE │ switch_mode AGENT_SEQUENTIAL │ decision_source AGENT │ 條件相符的候選串接（不是同一人確認） │
├──────────────────────────────────────────────────────────┬─────────────────────────────────┤
│ 主畫面  CAM_A  #062  t 12.400 s               [SEARCHING] │ 候選欄（SEARCHING 時才有內容）     │
│ ┌┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┐ │ 快照 cand:9c1e… · top_k 3 · 出口 UNIQUE │
│ ┊                                                      ┊ │ ┌ #1 CAM_C ─────────────────┐   │
│ ┊       [CAM_A 在 t 的影格；暫失期間不畫框]              ┊ │ │ PERSON_NO_COLOR_MATCH       │   │
│ ┊                                                      ┊ │ │ 排除 CONDITION_MISMATCH     │   │
│ ┊   最後觀測 [縮圖] t 8.200 s                            ┊ │ │ NEXT_CANDIDATE · AG         │   │
│ └┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┘ │ └───────────────────────────┘   │
│ 狀態條：暫失 · 搜尋中 · 目前看 #2 CAM_B                     │ ┏▶#2 CAM_B ── 游標 ━━━━━━━━┓   │
│                                                          │ ┃ [CAM_B 同一來源時間的畫面]  ┃   │
│                                                          │ ┃ MATCH_STRONG · 6 筆相符     ┃   │
│                                                          │ ┃ 窗 [8.2, 14.2) s           ┃   │
│                                                          │ ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛   │
│                                                          │ ┌ #3 CAM_D ─ 尚未取證 ──────┐   │
│                                                          │ 被截斷 0 · 排除轉移 1（TOPOLOGICAL_ONLY_EDGE）│
├──────────────────────────────────────────────────────────┴─────────────────────────────────┤
│ 時間列：軌道 1 鏡頭段  ▭▭CAM_A▭▭▭┈┈暫失┈┈┊搜尋中┊│▭▭CAM_B▭▭▭▭▭▭ │                            │
│         軌道 2 決策點  ·                       ◆3 AG SWITCH → CAM_B                         │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

上圖是 `AGENT_SEQUENTIAL` 錄製回應在 `SEARCHING` 期間的示意（和下面 Q5 逐步紀錄的例子是同一次搜尋）；`RULE_ONLY` 時版面相同，`decided_by` 徽章換成 ⓡ。尺寸（1440×900、面板常駐、估算）：主要區域 1044×620；主畫面影像約 760×428（16:9），候選欄 270 px 寬、每個候選 256×144。實作時以 #74 的 `layout.mjs` 算，數字以實測為準。

**資料與播放：**Q2 回應（§8.7）是**整段已算完的 session**：`timeline` 加上 `decisions` 檔。UI 是重播，不在前端重算狀態機。時間 `t` 落在哪個 `timeline` 段，就決定主畫面：

| `t` 所在 | 主畫面 | 狀態條 | 候選欄 |
| --- | --- | --- | --- |
| `ON_CAMERA` 段 | 該段 `camera_id` 在時間 `t` 的影格；標出該格接上的觀測框（觀測色實線） | `PLAYING`；顯示最後一筆 `link` 的 `decision` | 空白，寫「PLAYING：目標在畫面中，沒有候選」 |
| `GAP` 段、`TEMP_LOST` | `camera_shown`（原鏡頭）在時間 `t` 的影格；**不畫框** | 「暫失 · 觀測缺失」＋最後觀測縮圖與其時間 | 空白 |
| `GAP` 段、`SEARCHING` | 同上；主畫面外框改點線（暫失色） | 「暫失 · 搜尋中」＋目前看的候選 | 依該次搜尋的決策紀錄顯示 top-k 候選（下表） |
| `GAP` 段、`RETURNED_TO_ORIGIN` | 原鏡頭在**目前來源時間**（不倒轉） | 「回到原鏡頭」＋原因 | 保留上一輪候選，全部標結果 |
| `timeline` 以外（§3.3 沒涵蓋的時段） | 不顯示影格 | `UNKNOWN · 沒有資料` | — |

- `GAP` 段的 `position` 一律 `null`：主畫面與時間軸都不畫盲區中的位置，也不在候選畫面上補框（§8.7）。
- 候選欄的畫面用 #71 的 `toDisplayModel`／`renderGrid`（1 欄 × top_k 列），顯示**同一來源時間**的候選鏡頭影格。這是方便使用者自己看，不是證據；證據是下面的 Q4 摘要。
- 每個候選卡片顯示：`rank`、`camera_id`、`relation`（`OVERLAP`／`BLIND_GAP`）、`window_us`、Q4 的 `target_presence`、排除原因、`action`、`decided_by`。游標所在的候選有選取外框（`--sel`）。
- **切鏡時**：時間走到 `executed_action: SWITCH` 的決策 `source_time_us`，主畫面硬切到新鏡頭；時間軸在該點畫一個決策點 ◆，旁邊寫 `decided_by` 與目標鏡頭。切過去後的第一個框，就是決策引用的觀測（`entered_by: SWITCH`）。
- **不能**把切鏡畫成「同一人」：跨段連線只寫「條件相符的候選串接」，`identity_verdict` 在標題列與圖例常駐。

**Q4 證據（點候選卡片，在面板「證據」區展開）：**

```text
候選 #2 CAM_B · cand:9c1e…:2 · 窗 [8.2, 14.2) s
target_presence  MATCH_STRONG（推論：條件相符的候選觀測，不是身分）
影格             已推論 30 · 未取樣 0 · 未推論 0 · MISSING 0
最佳觀測         [縮圖＋框] t 13.400 s · score 0.81 · red STRONG     （最多 evidence_max_observations 筆）
                 [縮圖＋框] t 13.600 s · score 0.77 · red WEAK
第一次相符        13.400 s · 相符觀測 6 筆 · evidence 7d0a…
```

- `NO_PERSON_DETECTED` 的固定文案是「窗內已推論的格都沒有人物框（不代表目標不在那裡）」。`NOT_EVALUATED`、`PARTIAL_EVIDENCE` 用 `UNKNOWN` 的點線樣式，寫哪幾格沒有推論或 `MISSING`。

**Q5 逐步紀錄（面板「逐步紀錄」區；時間軸決策點可點）：**

```text
#3  SEARCHING → PLAYING   t 13.400 s   AGENT_SEQUENTIAL
    出口 UNIQUE（CAM_A:EXIT_LEFT）· 快照 cand:9c1e…
    候選   #1 CAM_C  PERSON_NO_COLOR_MATCH  CONDITION_MISMATCH  NEXT_CANDIDATE  AGENT
           #2 CAM_B  MATCH_STRONG                               SWITCH          AGENT
    提交   SWITCH → cand:…:2   接受 ✓   執行 SWITCH → CAM_B
    LLM    qwen2.5:7b-instruct · digest … · prompt 9c1e… · 驗證 PASS        輪數 2/3 · 用時 1840/5000 ms
    工具   get_search_context · get_candidate_evidence ×2 · submit_decision   （request／response hash 可展開）
    理由   （Agent 的 rationale 原文，標「Agent 說明，不是證據」）
```

- 每筆讀 `decision-record.v1` 的欄位，被拒的提交（`accepted: false`）也列出，標 `rejection_code`。
- `decided_by` 用徽章：`AGENT`（外框方形）、`RULE_FALLBACK`（ⓡ 規則兜底＋`fallback_reason`）、`RULE_ONLY`（ⓡ 規則）、`USER`（人形符號）。四種都是單色，不用證據色（理由見 §1.5）。
- 點一筆紀錄：時間跳到 `source_time_us`，候選欄換成該筆的候選。

**使用者操作（Q2）：**選起點（Q1 卡片的「設為 Q2 起點」、或 `APPEARANCE` 起點清單中點選）→ 播放／步進 → 點決策點或逐步紀錄看證據。`seed.kind: APPEARANCE` 時，如果服務回傳多個起點候選，主畫面先顯示「起點候選」清單（依時間、`camera_id`、`observation_id` 排序），由使用者點選，不自動挑（§8.5）。這份清單的回應 schema 契約沒有定義（`UNKNOWN`，見 §2.4 需求 R-4）。

### 1.5 狀態編碼

沿用 #72 §1 原則 1：**只有證據有顏色**。Q 線的新狀態分兩類：

- 和證據有關的（觀測、推論、`MISSING`、`UNKNOWN`）用 #74 `tokens.mjs` 已有的顏色與線型。
- 「暫失／搜尋中」與「規則兜底」**不是證據**，是「沒有觀測」與「誰做的決定」。兩者用墨色、線型與符號，不用色相。這樣「規則兜底」不會被誤讀成一種證據強度。

| 畫面上的東西 | 契約值 | 文字碼 | 編碼 |
| --- | --- | --- | --- |
| 人物框、片段、時間軸的鏡頭段 | 偵測索引的 `detections[]`（`frame_state: INFERRED`） | OBS 觀測 | `--obs` 實線 3 px、實心段 |
| 顏色判定 | `color.verdicts` 的 `STRONG`／`WEAK`／`NONE` | INF 推論 | `--int` 空心小標籤：「red STRONG」；`WEAK` 標籤外框改短虛線 |
| 顏色判定 `UNKNOWN` | `color.verdicts = UNKNOWN`＋`unknown_reason` | UNK | `--unk` 點線標籤＋原因（`CROP_TOO_SMALL` 等） |
| Q4 判定 | `target_presence` 的 `MATCH_*`、`PERSON_*`、`NO_PERSON_DETECTED` | INF 推論 | `--int` 空心標籤＋原值 |
| Q4 判定 | `NOT_EVALUATED`、`PARTIAL_EVIDENCE` | UNK | `--unk` 點線 |
| 候選排序 | `rank`、`ranking_basis` | INF 推論 | 只用順序；附「排序依據」一行，不寫機率 |
| 缺格 | `frame_state: MISSING` | MISS | `--miss` 斜紋 |
| 未推論 | `frame_state: NOT_INFERRED` | UNK | 點線框「未推論」＋`state_reason`；**不和 MISSING 合併** |
| 未取樣 | `frame_state: NOT_SAMPLED` | — | 時間軸上留空、不畫斜紋；說明「依取樣策略沒選到」 |
| 必要輸入缺、無法回答 | `status: UNKNOWN` | UNK | 點線框「?」＋原因 |
| 暫失（容忍內） | `TEMP_LOST` | LOST 暫失 | 墨色 `--ink-3` 細點線段 `┈`；主畫面不畫框 |
| 暫失・搜尋中 | `SEARCHING` | SRCH 搜尋中 | 同上，加 `┊` 端點；主畫面外框改點線 |
| 回到原鏡頭 | `RETURNED_TO_ORIGIN` | RET | 墨色 ↩ 符號 |
| 決定來源 | `decided_by` = `AGENT`／`RULE_FALLBACK`／`RULE_ONLY`／`USER` | AG／ⓡ／ⓡ／U | 墨色徽章；兜底時徽章旁一定有 `fallback_reason` |
| 身分 | `identity_verdict` | — | 圖例與標題常駐「身分 UNCONFIRMED」 |

- 加進 `tokens.mjs` 的新條目放在另一個陣列（例如 `Q_STATES`），**不改**既有 `EVIDENCE_STATES` 的六項，3D 線恢復時不受影響。
- 「推論永遠不比觀測實」（#72 原則 3）照舊：顏色判定與 Q4 判定都是空心標籤，人物框才是實線。
- 實作前仍要做色盲模擬與灰階截圖（#72 §5.1 的要求），列在 §5 各任務的瀏覽器檢查。

### 1.6 回應來源列（兩種模式都有）

主要區域標題列右側，一行顯示目前回應的共通欄位（§2.3）：

```text
status READY · 解析 LLM · Agent 未呼叫 · 決定 RULE_ONLY · 兜底 否 · gt_read false · 身分 UNCONFIRMED · output 5c3e9a1f… · 來源 SYNTHETIC
```

- Demo 模式顯示這一行的精簡版（`status`、解析方式、決定來源、兜底、身分、資料來源）；滑過去看完整值。
- 審核模式顯示全部欄位，並在每個欄位旁加自動檢查結果（§3.3）。
- `provenance.gt_read` 不是 `false`、`identity_verdict` 不是 `UNCONFIRMED`、`schema_version` 不符：**整份回應不顯示**，改成阻擋式錯誤面板（沿用 #72 §4.5「完整性錯誤」的處理），兩種模式都一樣。

### 1.7 資料來源切換

沿用 #79 `createApi({mode})` 與 `validateBootstrap` 的做法，資料來源由 bootstrap 的 `data_origin` 決定，不由使用者在畫面上切：

| `data_origin` | 意思 | 頁面最上方 |
| --- | --- | --- |
| `SYNTHETIC_FIXTURE` | UI 自己產生的虛構回應（`frontend/workbench-v2/fixtures/q-*.json`） | SYNTHETIC 斜紋條（不能關） |
| `RECORDED` | 後端真實回應的錄製檔，原樣重播；檔案帶原始 `output_sha256` | 「RECORDED 錄製回應 · 錄製於 …」單色條 |
| `REAL`（live） | 直接呼叫 Codex 的服務 | 無 |

- 三種來源走**同一條**驗證路徑（§2.3 `q-validate.mjs`），切換只換 `fetch` 的目標，不換畫面程式。
- `RECORDED` 的檔案重播時要重算 `output_sha256`，和檔案內的值不符就 fail closed。
- 錄製檔放哪裡、由誰產生：建議 Codex 的服務提供「把這次回應存檔」的開發用功能，檔案放 repo 外；路徑 `UNKNOWN`（需求 R-5）。

## 2. 元件清單

### 2.1 沿用（不改原檔，除非另註）

| 來源 | 檔案與 export | Q 線用途 |
| --- | --- | --- |
| #74 | `layout.mjs`：`HEIGHTS`、`WIDTHS`、`fitTiles`、`mainAreaSize`、`gridShape` | Q1 牆與 Q2 主畫面的尺寸。`HEIGHTS` 要加 `q3bar: 40`（T1 改） |
| #74 | `clock.mjs`：`createPlayer`、`advance`、`stepTMs`、`formatSeconds` | 播放迴圈。契約用整數微秒；store 改存 `tUs`，`clock.mjs` 的毫秒函式只用在 rAF 的增量，比較一律用 µs（T1 改，見 §2.2 `q-time.mjs`） |
| #74 | `tokens.mjs`：`EVIDENCE_STATES`、`SYNTHETIC`、`IDENTITY_LEGEND`、`legendItems` | 證據編碼；另加 `Q_STATES`（§1.5） |
| #74 | `shell-view.mjs`：`mountShell`、`renderLegend`、側欄三態、`localStorage` 側欄偏好 | 外框。頂欄任務鈕與查詢列插槽由 T1 改 |
| #74 | `store.mjs`：`createStore`、`reduce` | 單一 state。`MODES` 換成任務 `q1`／`q2`；Demo 步驟欄位暫不用（T1 改） |
| #79 | `api.mjs`：`createEpoch`、`apiError`、`errorFromBody`、`validateBootstrap` | `q-api.mjs` import 這幾個；`api.mjs` 的五個 controlled-scene 端點與 `uncertainty.mjs` 是 3D 線用的，Q 線不用、不改 |
| #71 | `player-grid.mjs`：`layoutFor`、`createGridState`、`pageView`、`pageCount`、`expectedFrame`、`buildSyncedFramesRequest`、`toDisplayModel`、`renderGrid` | Q1 牆的格數與分頁；Q1「播放片段」與 Q2 主畫面、候選欄的影格顯示 |
| 舊工作台 | `../workbench/demo-mode.mjs`：`canonicalJSON`、`sha256Hex`、`isTypingTarget` | 重算 `output_sha256`、匯出審核 JSON 的 hash、快捷鍵。`canonicalJSON` 是否完全符合 v1.1 §2.1 的規則：**UNKNOWN**，T1 先比對；不符就在 v2 另寫，不改舊檔 |
| #78 | （只沿用用語，不 import） | `PASS`／`FAIL`／`UNSURE`／未審、`p`／`f`／`u` 快捷鍵、進度列格式 |

### 2.2 新增

所有純邏輯檔不碰 `document`，可直接 `node --test`。

| 檔案 | 類別 | 內容 | 讀的契約欄位 |
| --- | --- | --- | --- |
| `q-api.mjs` | 純 | Q1、Q3、Q2 請求建構與送出；fixture／recorded／live 三種來源；epoch 丟棄過期回應。**沒有 `mode` 參數**（審核與否不影響請求，§3.2） | 請求：§6.1、§7.1、§8.5 全部欄位 |
| `q-validate.mjs` | 純 | 共通欄位驗證（§2.3）、各端點 `status` 封閉清單、`output_sha256` 重算、`decision-record.v1` 與 `timeline` 結構檢查；失敗 fail closed | `schema_version`、`status`、`reason`、`identity_verdict`、`provenance.gt_read`、`output_sha256`、`stats`（排除）、`llm_parse_used`、`agent_attempted`、`agent_used`、`decision_source`、`fallback_used`、`fallback_reason` |
| `q-time.mjs` | 純 | 來源 µs 與展示時鐘換算、`[start, end)` 半開區間、`time_coverage` 文案 | §3.1 `clock_mapping`（`wall_origin`、`t0_us`、`timezone`、`rate`、`source_duration_us`）、`resolved_scope.requested_time`、`time_coverage` |
| `q-tokens.mjs`（或併入 `tokens.mjs` 的 `Q_STATES`） | 純 | §1.5 的新狀態、`decided_by` 徽章、`target_presence` 與顏色判定的文字碼 | `target_presence`、`color.verdicts`、`frame_state`、`decided_by` |
| `q3-bar-model.mjs`／`q3-bar-view.mjs` | 純／DOM | 查詢列、結構化查詢面板、澄清選項、解析徽章 | §7.4：`status`、`parsed_by`、`structured_query`、`unresolved_terms`、`clarification`、`llm_call.*`、`fallback_reason`；§7.5 說明文字與 `cited_refs` |
| `q1-wall-model.mjs`／`q1-wall-view.mjs` | 純／DOM | 三區分組、卡片 view model、分頁、「設為 Q2 起點」的請求組裝 | §6.3：`results[]`（`camera_id`、`rank`、`matched_segments[].range_us`、`matched_frames`、`evaluated_frames`、`representative.*`、`coverage.*`）、`no_match_cameras`、`not_evaluated_cameras`、`results_total`、`returned_count`、`next_cursor`、`ranking_basis`、`supported_classes_ref` |
| `q2-session-model.mjs` | 純 | 給定 `timeline`、`decisions` 與 `tUs`：主畫面鏡頭、狀態條、候選欄內容、游標、決策點清單 | §8.7 `timeline[]`（`segment_id`、`kind`、`camera_id`、`range_us`、`entered_by`、`decided_by`、`decision_id`、`observation_ids`、`presence_at_entry`、`gap_states`、`camera_shown`、`position`）、`decisions_ref`、`decisions_sha256` |
| `q2-view.mjs` | DOM | 主畫面、狀態條、候選欄（內含 #71 `renderGrid`） | 同上，加 Q4 摘要 |
| `q2-timeline-model.mjs`／`q2-timeline-view.mjs` | 純／DOM | 時間軸兩條軌道：鏡頭段／暫失段、決策點；點擊命中 | `timeline[]`、決策紀錄的 `source_time_us`、`executed_action`、`decided_by` |
| `q4-evidence-view.mjs` | DOM | Q4 證據摘要 | §8.3：`candidate_ref`、`camera_id`、`window_us`、`target_presence`、`frames.*`、`best_observations[]`、`matching_observation_count`、`first_match_us`、`evidence_sha256` |
| `q5-log-model.mjs`／`q5-log-view.mjs` | 純／DOM | 逐步紀錄清單與展開內容 | §8.7 `decision-record.v1` 全部欄位（`stats` 只顯示，不比對） |
| `provenance-bar.mjs` | 純＋DOM | §1.6 回應來源列 | §2.3 全部 |
| `review/review-model.mjs` | 純 | 審核項目產生、自動檢查、預期清單比對、洩漏探針、匯出 JSON（§3） | 同上各欄位＋`output_sha256` |
| `review/review-view.mjs` | DOM | 各元件旁的審核控制、審核面板、匯出 | — |
| `fixtures/q-*.json` | 資料 | SYNTHETIC 回應：Q1（`READY`、`PARTIAL`、`NO_MATCH`、`OUT_OF_RANGE`）、Q3（`PARSED` LLM、`PARSED` 規則兜底、`NEEDS_CLARIFICATION`、`PARSE_FAILED`）、Q2（`RULE_ONLY` 一次切鏡、`AGENT_SEQUENTIAL` 被拒後兜底、`RETURNED_TO_ORIGIN`、`gt_read: true` 負面案例）。每份標 `data_origin: SYNTHETIC_FIXTURE`，ID 用 `FICT_` 前綴 | — |
| `review/fixtures/expectations.synthetic.json` | 資料 | 只配合上面的 SYNTHETIC 回應、內容全虛構的預期清單範例（§3.4） | — |

`q-*.mjs` 檔名前綴是為了和 3D 線的 `plan-*`、`api.mjs` 分開，兩條線的檔案集合不重疊。

### 2.3 依賴關係

```text
app.mjs ─┬─ shell-view（#74）── store（#74，T1 改）
         ├─ q3-bar-view ── q3-bar-model ─┐
         ├─ q1-wall-view ── q1-wall-model ├─ q-api ── q-validate ── demo-mode.canonicalJSON（舊）
         ├─ q2-view ── q2-session-model ─┤            └─ api.createEpoch／apiError（#79）
         │     └─ player-grid（#71）       └─ q-time、q-tokens（tokens #74）
         ├─ q2-timeline-view、q4-evidence-view、q5-log-view、provenance-bar
         └─ （只在審核模式）動態 import('./review/review-view.mjs') ── review-model
```

`review/` 只依賴 view model 與已驗證的回應，**任何 `q-*` 檔都不 import `review/`**（§4.2 檢查 L-2）。

### 2.4 對 Codex 的需求（只列需求，不改 Codex 的檔案）

| # | 需求 | 原因 |
| --- | --- | --- |
| R-1 | Q1、Q3、Q2 的 HTTP 路徑與方法。契約 v1 草案沒有寫端點路徑；本文暫用 `POST /api/q1_camera_search`、`POST /api/q3_parse`、`POST /api/q2_session` | 端點路徑 `UNKNOWN` |
| R-2 | UI 讀決策紀錄：`decisions_ref` 怎麼取（`GET` 路徑、是否分頁）與 `decisions_sha256` 的計算範圍 | §8.7 只有 ref |
| R-3 | UI 讀 Q4 證據摘要與觀測摘要的唯讀端點（不是 Agent 的 typed tools；不受「依序」限制，但只能讀這個 session 已產生的 ref） | 候選卡片與 Q2 主畫面的框都需要 `bbox_xyxy_px`；`timeline` 只有 `observation_ids` |
| R-4 | `seed.kind: APPEARANCE` 有多個起點候選時的回應 schema 與 `status`（例如 `SEED_CHOICE_REQUIRED`） | §8.5 只說「由使用者選」 |
| R-5 | 開發用的「錄製回應」：原樣存檔，含 `output_sha256`；檔案放 repo 外 | §1.7 `RECORDED` |
| R-6 | Q2 播放時取任意鏡頭、任意來源時間影格的方式：沿用 v1.1 §6.2 的 `synced_frames` 與媒體權杖（#80 2a），或另訂 | q-demo 契約沒有影格端點 |
| R-7 | bootstrap 增加 `data_origin: RECORDED` 與錄製時間 | §1.7 |

## 3. 審核模式規格

### 3.1 開關

- **只用網址進入**：`/workbench-v2/?mode=review`。沒有這個參數就是 Demo 模式；頁面上**沒有**切換鈕。
- 模式在載入時決定，整個頁面生命週期不變；要換模式就換網址重新載入。這樣 Demo 模式的頁面從頭到尾不會載入任何審核程式或預期檔。
- 進入審核模式時：
  1. `app.mjs` 讀 `location.search`，`mode=review` 才 `import('./review/review-view.mjs')`。
  2. 頂欄出現「審核模式」標籤，圖示列多一個「審核」，面板多「審核」區。
  3. 審核人姓名欄（必填才能匯出），記在瀏覽器 `localStorage`（只是方便，讀不到就空白）。
  4. 「載入預期清單」按鈕：開檔案選擇器或拖放（§3.4）。不載也能審，只是沒有劇情對照。
- 審核模式**不加**任何查詢參數、標頭或請求欄位；`mode` 只存在網址與前端記憶體。

### 3.2 只讀的保證

| 規則 | 作法 |
| --- | --- |
| 請求不變 | `q-api.mjs` 的函式簽名沒有 `mode`；`review/` 拿不到 `q-api` 物件，只收到 store 中已驗證、`Object.freeze` 過的回應 |
| 不改回應 | 審核結果存在 `review` 自己的 state，不寫回 store 的回應物件 |
| 同一查詢同一 hash | 審核模式在面板顯示每份回應的 `output_sha256` 與前端重算值；測試用同一份 fixture 分別以兩種模式載入，比對請求本文與 `output_sha256`（§4.2 檢查 L-4） |
| 不觸發推論 | 審核模式沒有「重跑」以外的請求；重跑送的是和 Demo 完全相同的請求 |

### 3.3 逐項審核的資料結構

審核項目由 `review-model.mjs` 依**目前畫面上的回應**自動產生，每一項綁定一份回應的 `output_sha256`。回應換了（重查、換資料來源），舊的審核項目標「已過期」，不能匯出成目前回應的結果。

```json
{
  "item_id": "rv:5c3e9a1f2b7d4e60:Q5_DECISION:dec-…",
  "target": {
    "kind": "Q5_DECISION",
    "schema_version": "q-demo.decision-record.v1",
    "response_output_sha256": "5c3e9a1f…",
    "ref": {"session_id": "…", "decision_id": "…", "step_index": 3}
  },
  "auto_checks": [
    {"check_id": "C-DECIDED-BY", "result": "PASS", "detail": "decided_by AGENT 且 accepted true；回應層 agent_used true 一致"}
  ],
  "expectation_refs": [
    {"expectation_id": "EXP-FICT-002", "hint": "MATCHES", "detail": "預期切到 CAM_FICT_HALL，實際 CAM_FICT_HALL"}
  ],
  "verdict": "UNREVIEWED",
  "note": "",
  "reviewed_at": null
}
```

| 欄位 | 規則 |
| --- | --- |
| `target.kind` | 封閉清單：`RESPONSE_COMMON`（每份回應一項：共通欄位）、`Q3_PARSE`、`Q1_RESULT`（每台相符鏡頭一項）、`Q1_NO_MATCH_GROUP`、`Q1_NOT_EVALUATED_GROUP`、`Q2_TIMELINE_SEGMENT`（每段一項）、`Q4_EVIDENCE`（每個取過證據的候選一項）、`Q5_DECISION`（每筆決策一項） |
| `auto_checks[]` | 前端能自動算的契約檢查（下表）。`result`：`PASS`、`FAIL`、`NOT_APPLICABLE`。**只是提示**，不代替人工判定 |
| `expectation_refs[]` | 只在載入預期清單時出現。`hint`：`MATCHES`、`DIFFERS`、`CANNOT_EVALUATE`（例如回應 `PARTIAL`、時段沒涵蓋）。只是提示 |
| `verdict` | 人工判定：`UNREVIEWED`、`PASS`、`FAIL`、`UNSURE`。快捷鍵 `p`／`f`／`u`（輸入框聚焦時不觸發，沿用 `isTypingTarget`） |
| `note` | 自由文字。`FAIL` 時必填才能匯出 |

**自動檢查（全部來自契約，不含劇情）：**

| `check_id` | 對象 | 檢查 | 契約 |
| --- | --- | --- | --- |
| `C-SCHEMA` | 每份回應 | `schema_version` 正確、`status` 在該端點的封閉清單 | §6.3、§7.4、§8.7 |
| `C-IDENTITY` | 每份回應 | `identity_verdict == "UNCONFIRMED"` | §2.3 |
| `C-GT` | 每份回應 | `provenance.gt_read == false` | §2.3、§9 |
| `C-HASH` | 每份回應 | 前端重算 `output_sha256`（去掉 `output_sha256` 與 `stats`）與回應值相同 | §2.3 |
| `C-ORIGIN` | 同一正規化請求的多份回應 | `origin` 不同（`MANUAL`／`PREFILL`／`Q3_PARSED`）時 `output_sha256` 相同 | §6.1 |
| `C-READY-SCOPE` | 每份回應 | `time_coverage.coverage_complete: false` 時 `status` 不是 `READY` | §3.3 |
| `C-NONE-SPLIT` | Q1 | 同一鏡頭不同時出現在 `results`、`no_match_cameras`、`not_evaluated_cameras` 兩處以上 | §6.3 |
| `C-RANK` | Q1 | `rank` 與 `ranking_basis` 一致（第一次相符時間 → `camera_id`） | §6.3 |
| `C-TIMELINE` | Q2 | `timeline` 依時間排序、不重疊、`GAP` 的 `position` 是 `null` | §8.7 |
| `C-DECIDED-BY` | Q2／Q5 | `agent_used` 等於「有一步 `decided_by: AGENT` 且 `accepted: true`」；`decision_source` 等於最後一個切鏡決定的 `decided_by` | §2.3、§8.6 |
| `C-FALLBACK` | Q5 | `decided_by: RULE_FALLBACK` 的紀錄都有 `fallback_reason`，且值在封閉清單 | §8.6 |
| `C-GUARD` | Q5 | 每個被執行的 `SWITCH`，其候選的 `target_presence` 達到參數組的 `switch_min_presence` | §8.4、§8.6 |
| `C-ORDER` | Q5 | `candidates_considered` 的 `rank` 由小到大、不跳號（依序取證據） | §8.4 |

另一個 session 在寫給 Codex 的合約符合性測試包。上表若和那份測試包有重疊，實作時改用同一組 `check_id`；那份的路徑與格式 `UNKNOWN`。

### 3.4 劇情預期清單

**界線：**

- 預期清單是審核人自己寫的本機檔，**放在 repo 以外**（例如 `~/amidst-review/`）。repo 裡只有一份配合 SYNTHETIC fixture、內容全虛構的範例。
- 只經瀏覽器的檔案選擇器或拖放讀進前端記憶體。不上傳、不經任何 API、不寫進 `localStorage`。後端與推論程式沒有任何路徑能讀到它。
- Demo 模式不載入 `review/` 程式，也就沒有讀這個檔的程式碼。

**格式 `q-demo.review-expectations.v1`**（以下內容**全部虛構**，只示意欄位，和 r004 或任何真實事件無關）：

```json
{
  "schema_version": "q-demo.review-expectations.v1",
  "expectations_id": "EXPSET-FICT-001",
  "local_only": true,
  "author": "審核人甲",
  "written_at": "2026-10-20T16:00:00+08:00",
  "applies_to": {
    "scene_id": "FICT_SCENE_PLAZA",
    "scene_revision": "FICT_R1",
    "run_ids": ["FICT_RUN_01"]
  },
  "leak_probes": ["虛構路線甲", "黃色雨衣路人"],
  "items": [
    {
      "expectation_id": "EXP-FICT-001",
      "kind": "Q1_CAMERA_IN_RESULTS",
      "match": {"query": {"class_label": "bicycle"}},
      "expected": {"camera_id": "CAM_FICT_GATE"},
      "description": "腳踏車應出現在大門鏡頭的結果裡"
    },
    {
      "expectation_id": "EXP-FICT-002",
      "kind": "Q5_SWITCH_TO",
      "match": {"query": {"seed_color": "yellow"}, "from_camera_id": "CAM_FICT_GATE"},
      "expected": {"to_camera_id": "CAM_FICT_HALL", "within_source_range_us": [8000000, 16000000]},
      "description": "虛構路線甲：離開大門鏡頭後應切到大廳鏡頭"
    },
    {
      "expectation_id": "EXP-FICT-003",
      "kind": "Q2_NO_SWITCH_BEFORE",
      "match": {"query": {"seed_color": "yellow"}},
      "expected": {"source_time_us": 8000000},
      "description": "8 秒前不應切鏡"
    }
  ]
}
```

| 欄位 | 規則 |
| --- | --- |
| `local_only` | 必須是 `true`，否則拒絕載入 |
| `applies_to` | 和目前回應的 `resolved_scope` 不符時，整份清單不套用，面板寫「預期清單不適用於目前場景」 |
| `leak_probes` | 只寫劇情專用、正常回應不該出現的字串（路線名、腳本用語）。**不寫鏡頭 ID**，因為鏡頭 ID 本來就會出現在回應中。用途見 §4.2 檢查 L-5 |
| `items[].kind` | 第一版封閉清單：`Q1_CAMERA_IN_RESULTS`、`Q1_CAMERA_NOT_IN_RESULTS`、`Q3_INTENT`、`Q5_SWITCH_TO`、`Q2_NO_SWITCH_BEFORE`、`Q2_RETURNS_TO_ORIGIN`。不在清單的 `kind` 只顯示 `description`，`hint: CANNOT_EVALUATE` |
| `items[].match` | 用結構化查詢的欄位挑出適用的回應；比對只在前端記憶體中做 |
| `description` | 給審核人看的說明；匯出時**不帶**（§3.5） |

### 3.5 匯出 JSON

格式 `q-demo.review-record.v1`。匯出由瀏覽器下載成本機檔，**不送任何 API**。

```json
{
  "schema_version": "q-demo.review-record.v1",
  "review_id": "rvw:<content_sha256 前 16 碼>",
  "contract": {"name": "Q1_Q2_FIRST_DEMO_V1", "status": "DRAFT", "commit": "258c7e2"},
  "ui": {"app": "workbench-v2", "commit": "…", "review_model_version": "1"},
  "reviewer": {"name": "審核人甲"},
  "reviewed_at": "2026-10-20T16:30:00+08:00",
  "data_source": {"data_origin": "SYNTHETIC_FIXTURE", "recorded_at": null, "counts_for_acceptance": false},
  "parameter_set": {"parameter_set_id": "…", "parameter_set_sha256": "…"},
  "responses": [
    {"endpoint": "q2_session", "schema_version": "q-demo.q2-response.v1",
     "query_id": null, "session_id": "…",
     "output_sha256": "5c3e9a1f…", "output_sha256_recomputed": "5c3e9a1f…", "hash_match": true,
     "decisions_sha256": "…"}
  ],
  "expectations": {"loaded": true, "expectations_id": "EXPSET-FICT-001", "file_sha256": "…", "applied": true},
  "items": [
    {"item_id": "…", "target": {}, "auto_checks": [], "expectation_refs": [{"expectation_id": "EXP-FICT-002", "hint": "MATCHES"}],
     "verdict": "PASS", "note": "", "reviewed_at": "…"}
  ],
  "summary": {"items": 24, "pass": 20, "fail": 1, "unsure": 1, "unreviewed": 2, "auto_check_fail": 0, "leak_probe_hits": 0, "stale_items_excluded": 0},
  "content_sha256": "…"
}
```

| 欄位 | 規則 |
| --- | --- |
| `contract.commit` | 審核時對照的契約 commit。契約改版後，舊紀錄仍指舊 commit |
| `reviewer.name` | 必填 |
| `data_source.counts_for_acceptance` | `SYNTHETIC_FIXTURE` 一律 `false`；`RECORDED`、`REAL` 是 `true`。人工判定照實記錄，不改寫（待決 U-4） |
| `responses[]` | 每份被審的回應各一筆，`hash_match: false` 的回應其項目照樣匯出，但 `summary` 另計 |
| `expectations` | 只記 ID 與檔案 hash，**不記內容**；`description` 與 `expected` 都不進匯出檔（待決 U-3）。沒載入時整欄 `{"loaded": false}` |
| `items[].reviewed_at`、`reviewed_at` | 計時欄位，不進 `content_sha256`（v1.1 §2.1） |
| `content_sha256` | 去掉 `content_sha256`、`reviewed_at`、`items[].reviewed_at` 後的 canonical JSON hash |

- 有 `UNREVIEWED` 項目時可以匯出，但進度列與匯出檔都寫「仍有未審項目」（沿用 #78）。
- `FAIL` 沒有備註時不能匯出。
- 已過期（`response_output_sha256` 不是目前回應）的項目不匯出，數量記在 `stale_items_excluded`。
- 審核進度的草稿可以存在 `localStorage`，以 `output_sha256` 為鍵（待決 U-5）；正式紀錄只有匯出檔。

## 4. Demo 模式與審核模式

### 4.1 差異表

| 項目 | Demo 模式 | 審核模式 |
| --- | --- | --- |
| 進入 | `/workbench-v2/` | `/workbench-v2/?mode=review` |
| 載入的程式 | 不含 `review/` | 另動態載入 `review/review-view.mjs`、`review-model.mjs` |
| API 請求 | 依查詢 | **完全相同** |
| `output_sha256` | 回應值 | 同一回應值，另顯示前端重算值與比對 |
| Q1 牆、Q2 主畫面與時間軸、Q3 解析、Q4 證據、Q5 逐步紀錄 | 有 | 有，同一元件；每個元件旁多審核控制 |
| 回應來源列 | 精簡版 | 全部欄位＋自動檢查 |
| 逐步紀錄 | 預設收合，只展開目前決策 | 預設全部展開，顯示 hash、prompt ref、工具呼叫 |
| 劇情預期清單 | 不載入、沒有載入程式 | 審核人手動選本機檔才載入 |
| 審核面板、匯出 | 無 | 有 |
| 頂欄標籤 | 無 | 「審核模式」 |
| 資料來源條 | 有（SYNTHETIC／RECORDED） | 有，同 Demo |
| 錯誤處理（`gt_read` 不是 false 等） | 阻擋式錯誤面板 | 同 Demo；另記一筆 `C-GT: FAIL` 項目 |

### 4.2 防止答案洩漏的檢查

| # | 檢查 | 方式 | 在哪個任務 |
| --- | --- | --- | --- |
| L-1 | 後端與推論程式不讀預期清單 | 靜態測試：`src/`、`scripts/`、`frontend/workbench-v2/q-*.mjs` 內沒有 `review-expectations` 字串，也沒有讀 `review/` 的路徑。後端部分由 Codex 的符合性測試補（需求，不改 Codex 檔案） | T4 |
| L-2 | Demo 模式不載入審核程式 | 靜態測試：從 `app.mjs` 出發的靜態 import 圖不含 `review/`；`review/` 只出現在 `mode === 'review'` 分支的動態 `import()`。瀏覽器檢查：Demo 模式網路紀錄沒有 `review/*.mjs` 與任何 `.json` 預期檔 | T1（掛鉤）、T4 |
| L-3 | 預期檔不進 repo | `.gitignore` 加 `*.review-expectations.json`；測試：repo 中 `schema_version` 為 `q-demo.review-expectations.v1` 的檔只有 `review/fixtures/expectations.synthetic.json`，且其中所有 ID 都以 `FICT_`／`EXP-FICT-`／`EXPSET-FICT-` 開頭 | T4 |
| L-4 | 審核模式不改請求 | node 測試：同一份 fixture，以兩種模式啟動 store，攔截 `fetch`，比對請求本文逐位元組相同、回應 `output_sha256` 相同。瀏覽器檢查：兩種模式各跑一次同一查詢，網路紀錄的請求本文相同 | T4 |
| L-5 | 答案沒有從別處流進後端輸出 | 審核模式載入預期清單後，把 `leak_probes` 每個字串拿去掃目前所有回應（含 Q3 的 `llm_call`、Q5 的 `rationale`、說明文字；`prompt_ref` 能取到全文時也掃）。命中就新增一項 `C-LEAK: FAIL`，標出欄位路徑。這只能發現「字串剛好出現」，不能證明沒洩漏 | T4 |
| L-6 | 預期內容不外流到匯出檔 | 測試：匯出 JSON 不含預期清單的 `description`、`expected`、`leak_probes` 任何字串 | T4 |
| L-7 | 預期清單不寫進瀏覽器儲存 | 測試：審核流程結束後 `localStorage` 只有側欄偏好、審核人姓名與以 `output_sha256` 為鍵的判定草稿，沒有預期內容 | T4 |

## 5. 實作切分

前提：#74、#79、#71 的檔案要先在實作分支可用（待決 U-1）。每個任務只跑自己的 focused test 與 `git diff --check`。瀏覽器檢查都在 1440×900、SYNTHETIC fixture 下做；Codex 後端接上後另跑一輪 `RECORDED`／`REAL`。

### T1：Q 資料層與外框改裝

- **建議**：Sonnet／medium。
- **檔案**：新增 `q-api.mjs`、`q-validate.mjs`、`q-time.mjs`、`q-tokens.mjs`、`fixtures/q-*.json`、`fixtures/generate_q_fixtures.mjs`、`q1-wall-view.mjs`／`q2-view.mjs`／`q3-bar-view.mjs`／`q5-log-view.mjs` 四個 3 行空殼（照 #74 的作法），以及對應 `*.test.mjs`；修改 `store.mjs`（任務 `q1`／`q2`、`tUs`、目前回應）、`app.mjs`（掛載與 `mode=review` 動態 import 掛鉤）、`shell-view.mjs`（任務鈕、查詢列插槽、回應來源列插槽）、`layout.mjs`（`q3bar`）、`tokens.mjs`（`Q_STATES`）、`index.html`、`style.css`。
- **依賴**：#74、#79（`createEpoch` 等）、契約 #86 的 schema。
- **驗收**：
  - `node --test frontend/workbench-v2/q-api.test.mjs q-validate.test.mjs q-time.test.mjs q-tokens.test.mjs store.test.mjs layout.test.mjs`。至少涵蓋：每個端點的 `status` 封閉清單、`gt_read: true` 與 `identity_verdict` 錯誤時 fail closed、`output_sha256` 重算（含 `stats` 不進 hash）、過期 epoch 丟棄、`clock_mapping` 偏移與時區不符時 fail closed、半開區間邊界、`canonicalJSON` 與 v1.1 §2.1 的比對結果。
  - 瀏覽器：Demo 與審核兩種網址都能開；Demo 網路紀錄沒有 `review/`；資料來源條與圖例正確；1440×900 不捲動。

### T2：Q3 查詢列與 Q1 結果牆

- **建議**：Sonnet／medium。
- **檔案**：`q3-bar-model.mjs`、`q3-bar-view.mjs`、`q1-wall-model.mjs`、`q1-wall-view.mjs`、`provenance-bar.mjs` 與測試；`style.css` 只加 `.q1-`、`.q3-` 前綴的規則（和 T3 不重疊）。
- **依賴**：T1、#71。
- **驗收**：
  - `node --test frontend/workbench-v2/q3-bar-model.test.mjs q1-wall-model.test.mjs provenance-bar.test.mjs`：三種「沒有」分組不合併、`NO_MATCH` 與 `OUT_OF_RANGE` 文案、`PARTIAL` 時頂部說明、`rank` 原樣、Q3 每種 `status` 的處理（`NEEDS_CLARIFICATION` 不執行）、規則解析徽章與 `fallback_reason`、「設為 Q2 起點」組出的請求符合 §8.5。
  - 瀏覽器：Q3 四種 fixture 各一張截圖；Q1 四種 `status` 各一張；1／2／4／8 格與分頁；色盲模擬與灰階截圖。

### T3：Q2 主畫面、時間軸、Q4 證據、Q5 逐步紀錄

- **建議**：Sonnet／high（狀態多）。
- **檔案**：`q2-session-model.mjs`、`q2-view.mjs`、`q2-timeline-model.mjs`、`q2-timeline-view.mjs`、`q4-evidence-view.mjs`、`q5-log-model.mjs`、`q5-log-view.mjs` 與測試；`style.css` 只加 `.q2-`、`.q4-`、`.q5-` 前綴的規則。
- **依賴**：T1、#71。可與 T2 並行（檔案不重疊）。
- **驗收**：
  - `node --test frontend/workbench-v2/q2-session-model.test.mjs q2-timeline-model.test.mjs q5-log-model.test.mjs`：每種狀態的主畫面鏡頭與候選欄內容；`GAP` 不畫框、不畫位置；`RETURNED_TO_ORIGIN` 不倒轉；決策點時間與 `decided_by`；被拒的提交有列出；`RULE_FALLBACK` 一定有 `fallback_reason`；`timeline` 以外顯示 `UNKNOWN`。
  - 瀏覽器：三份 Q2 fixture 各跑完一次，停在 `PLAYING`、`TEMP_LOST`、`SEARCHING`、切鏡瞬間、`RETURNED_TO_ORIGIN` 五個時間點截圖；點決策點與逐步紀錄跳轉；色盲模擬與灰階截圖。

### T4：審核模式

- **建議**：Sonnet／medium 實作，Opus／high 審查（界線相關）。
- **檔案**：`review/review-model.mjs`、`review/review-view.mjs`、`review/fixtures/expectations.synthetic.json`、`review/*.test.mjs`、`isolation.test.mjs`（L-1、L-2、L-3 靜態檢查）、`.gitignore` 一行；`style.css` 只加 `.rv-` 前綴的規則。
- **依賴**：T1（模型可先做）；view 掛到各元件要等 T2、T3。
- **驗收**：
  - `node --test frontend/workbench-v2/review/review-model.test.mjs frontend/workbench-v2/isolation.test.mjs`：§3.3 每個 `check_id` 的正負案例；過期項目不匯出；`FAIL` 無備註不能匯出；`content_sha256` 穩定（改 `reviewed_at` 不變）；L-1 到 L-7。
  - 瀏覽器：審核模式載入虛構預期清單、逐項判定、匯出、重新開檔核對內容；`applies_to` 不符時不套用；Demo 與審核兩種模式跑同一查詢，網路紀錄請求本文相同。

### 依賴圖

```text
#74、#79、#71 可用（U-1）── T1 ──┬── T2 ──┐
                                 ├── T3 ──┼── T4（view 掛鉤）
                                 └── T4（model）
```

T2 與 T3 可以分在兩個 session 並行；`style.css` 用前綴分段避免衝突，`app.mjs`、`store.mjs` 只有 T1 改。

## 6. 待使用者決定

每題的第一個選項是建議。

**U-1　#74、#79、#71 尚未合入 `mainline/q1q5`，Q 線實作分支怎麼取得它們？**

1. **（建議）先把三個 PR 合入 `mainline/q1q5`，再從 `mainline/q1q5` 開 T1。**三個都是 Claude 的純前端檔，和 Codex 檔案不重疊；需要使用者授權合併。
2. T1 疊在 #74 上（stack），#79、#71 的檔案在 T1 中 cherry-pick。不用先合併，但之後要依序 rebase 或合併，SHA 引用較亂。
3. Q 線不依賴它們，T1 自己寫最小外框。最獨立，但重複 #74 的工作，外框會分叉。

**U-2　劇情預期清單怎麼載入？**

1. **（建議）瀏覽器檔案選擇器或拖放，檔案放 repo 外。**伺服器完全不經手，界線最清楚；缺點是每次開審核模式都要選一次檔。
2. 開發伺服器提供本機靜態路徑（gitignore 的目錄），審核模式自動載入。方便，但伺服器程式碰得到這個檔，要另外證明後端不讀。
3. 第一版不做預期清單，只審契約自動檢查與人工判定。最簡單，但「路線該切到哪台」只能靠審核人記憶。

**U-3　匯出的審核 JSON 要不要帶預期內容？**

1. **（建議）只帶 `expectation_id` 與預期檔的 `file_sha256`。**匯出檔可以放進 repo 或貼到 issue，不洩漏答案；要重現時另外拿預期檔對 hash。
2. 帶完整預期內容。單檔可重現，但匯出檔也變成答案檔，不能進 repo 或公開 issue。

**U-4　SYNTHETIC 資料下的人工 PASS 怎麼記？**

1. **（建議）照實記錄 `verdict`，`data_source.counts_for_acceptance: false`。**保留審核人的判斷，同時不會被當成驗收。
2. 沿用舊 K6 規則：SYNTHETIC 下的 PASS 一律改記 `UNKNOWN`。和舊工作台一致，但看不出審核人原本的判斷。

**U-5　審核進度要不要在瀏覽器暫存？**

1. **（建議）以 `output_sha256` 為鍵存在 `localStorage`，正式紀錄只有匯出檔。**重新整理不會丟；回應一變就自動失效。
2. 不暫存。最乾淨，但重新整理就要重審。

**U-6　Demo 模式能不能展示 `AGENT_SEQUENTIAL`？**（契約 §0.3、Q-01；D64 原文未貼出）

1. **（建議）UI 照回應的 `switch_mode` 顯示；Demo 預設送 `RULE_ONLY`，`AGENT_SEQUENTIAL` 只在 DEVELOPMENT_RULES 修訂或列例外後開放選擇。**後端回 `MODE_NOT_AUTHORIZED` 時照實顯示「規則兜底 ⓡ」。
2. 依 D64 直接開放兩種模式的選擇，畫面標「Agent 模式（規則修訂中）」。展示較完整，但和契約 §0.3 衝突，要先改契約。

**U-7　Q3 解析成功後要直接執行嗎？**（契約 Q-09）

1. **（建議）直接執行，並顯示可修改的結構化查詢。**示範流暢；改了查詢就以 `origin: MANUAL` 重查。
2. 先顯示結構化查詢，使用者按「執行」才查。多一步，但每次都讓人看清 LLM 解析的結果。

**U-8　Q5 切鏡時主畫面怎麼呈現？**

1. **（建議）硬切，時間軸畫決策點，候選欄在 `SEARCHING` 期間常駐。**最接近固定機位的切換感，也不會讓轉場被誤讀成連續觀測。
2. 切換前把被選中的候選放大 0.5 秒再切。較好看，但轉場期間畫面不是任何一台鏡頭的觀測。
3. 子母畫面：原鏡頭縮成角落小畫面，新鏡頭全畫面。能同時看兩台，但主畫面變小，和「一次一台」的設定不同。

## 7. UNKNOWN 與後續

- 契約仍是 DRAFT（#86 @ `258c7e2`）。Codex 確認後若欄位改名，本文 §2.2 的欄位對應與 §3.3 的檢查要同步改。
- D63 修訂與 D64 原文未貼出；貼出後若與 §0.2 不同，本文改版。
- 端點路徑、決策紀錄與證據的 UI 讀取方式、起點候選 schema、錄製回應、影格取得方式：§2.4 R-1 到 R-7，等 Codex 回覆。
- `demo-mode.mjs` 的 `canonicalJSON` 是否符合 v1.1 §2.1：T1 先比對。
- 合約符合性測試包的路徑與 `check_id`：等另一個 session 完成後對齊。
- Demo 旁白與步驟腳本（舊 #72 §4.3 的 7 步）不在本文範圍；Q1–Q5 的展示腳本另開任務。
