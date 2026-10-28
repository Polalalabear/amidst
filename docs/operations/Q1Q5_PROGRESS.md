# Q1–Q5 進度導覽

快照時間：2026-10-26（表格與計數仍為 10-25 版，下方「最近改動」補記 10-26 事項）。資料來源：GitHub 上全部 PR 與 issue（`gh pr list`／`gh issue list --state all`）。
本文涵蓋 **112 個 PR 與 80 個 issue，共 194 項**（含本 PR #229；編號連續性以 `gh` 清單為準），每項只列在一個主分類下。
依 [AGENTS.md](../../AGENTS.md) 的「Progress guide」維護：每次開 PR 或 issue 都在 PR 中更新本文。即時狀態仍以[任務板 #93](https://github.com/Polalalabear/amidst/issues/93)為準。

## 分類方式

- **主分類：**Q1–Q5 五大問題；無法歸到單一問題的列在「共用」與「流程」；2026-10-20 轉向 Q1–Q5 之前的工作列在「暫停」與「歷史」。「也涉及」欄列出其他相關問題。
- **已完成：**PR 已合併，或 issue 已完成關閉。合併進 `codex/q1q5-staging` 的 PR 標「待審入主線」，還沒進 `mainline/q1q5`。關閉未合併的 PR 也列在這裡，備註寫明。
- **進行中：**開著的 PR，或程式已有 PR／已併入 staging 的 issue。
- **未完成：**尚未開始、blocked 或等授權的 issue。
- **待確認：**是否保留、合併或關閉還沒決定，例如舊線遺留的 PR、標示不合併的設計稿、等使用者決定的提案、工作已完成但 issue 還開著。

## 總覽

| 分類 | 已完成 | 進行中 | 未完成 | 待確認 | 合計 |
| --- | ---: | ---: | ---: | ---: | ---: |
| [Q1 依條件找鏡頭](#q1-依條件找鏡頭) | 1 | 1 | 2 | 0 | 4 |
| [Q2 在畫面中找人](#q2-在畫面中找人) | 2 | 1 | 0 | 0 | 3 |
| [Q3 理解使用者語意](#q3-理解使用者語意) | 4 | 5 | 1 | 0 | 10 |
| [Q4 判斷畫面是否含目標](#q4-判斷畫面是否含目標) | 2 | 1 | 4 | 1 | 8 |
| [Q5 決定是否切鏡](#q5-決定是否切鏡) | 3 | 7 | 5 | 1 | 16 |
| [共用：契約、規則、參數與一致性檢查](#共用契約規則參數與一致性檢查) | 13 | 4 | 8 | 2 | 27 |
| [共用：r004 場景、資料、索引與儲存](#共用r004-場景資料索引與儲存) | 9 | 4 | 3 | 0 | 16 |
| [共用：工作台、HTTP 與 Demo](#共用工作台http-與-demo) | 7 | 4 | 7 | 0 | 18 |
| [流程：任務板、交接與文件](#流程任務板交接與文件) | 9 | 7 | 2 | 1 | 19 |
| [暫停：跨鏡頭盲區 3D 重建線](#暫停跨鏡頭盲區-3d-重建線) | 36 | 0 | 0 | 2 | 38 |
| [歷史：Office Demo 與 Phase 1／2](#歷史office-demo-與-phase-12) | 36 | 0 | 0 | 0 | 36 |
| **合計** | **122** | **33** | **32** | **7** | **194** |

## 最近改動（2026-10-23 起）

- 2026-10-27 決定 D87（兩條線）：工作分配見 [Q1Q5_TWO_LINE_PLAN_20261027.md](../agents/Q1Q5_TWO_LINE_PLAN_20261027.md)；Line 2 傘狀 issue [#251](https://github.com/Polalalabear/amidst/issues/251)（L2-1..L2-7 為 #244–#250）。
- 2026-10-27 新 Draft PR（分支 `claude/r004-a4b4-scenario-cards`）：r004 A4／B4 情境卡 v1（D87），文件 `docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md`；待使用者核定後才交 Codex 做 Blender 可行性檢查（不渲染）。
- 2026-10-26 協調者交接：[COORDINATOR_HANDOFF_20261026.md](../agents/COORDINATOR_HANDOFF_20261026.md)（最新交接）。
- 2026-10-26 合併：[#229](https://github.com/Polalalabear/amidst/pull/229) 以 merge commit `f5168f6` 進 `mainline/q1q5`。[#237](https://github.com/Polalalabear/amidst/pull/237)（契約 B，`83da40f`）、[#239](https://github.com/Polalalabear/amidst/pull/239)（Qwen 報告註記，`7b05211`）進 `codex/q1q5-staging`；#237 取代 #219（GitHub 經 `635a102` 自動標成 MERGED，分支保留）。
- 2026-10-26 新 Draft PR [#240](https://github.com/Polalalabear/amidst/pull/240)：yyin Q1／Q3 包設計。
- 2026-10-26 決定：D83（P1 回交表人工閱讀）、D84（目錄凍結與 G4 脫鉤）、D85（停止後輪詢回 `PARTIAL`＋`USER_STOPPED`），見 [#93](https://github.com/Polalalabear/amidst/issues/93)。
- 2026-10-25 新 Draft PR [#229](https://github.com/Polalalabear/amidst/pull/229)：Q5 逐事件決策窗（D79 核定版），文件 `docs/evaluation/Q5_DECISION_WINDOW_D79.md`。
- 2026-10-25 [#83](https://github.com/Polalalabear/amidst/pull/83) 修正：`TEAM_ONBOARDING.md` 改寫為資料夾流程（不用 Git／分支／PR），`DECISION_INDEX.md` 補 D68–D78，`Q1Q5_COLLABORATION_INDEX.md` 與 `SYSTEM_OVERVIEW.md` 補現況段與關卡；本表其餘項目與總覽數字未變。
- 2026-10-25 新 Draft PR [#228](https://github.com/Polalalabear/amidst/pull/228)：P1 工程預驗收走查清單（AC1–AC8），分支 `claude/q1q5-p1-walkthrough-checklist`。
- 2026-10-25 新 PR [#225](https://github.com/Polalalabear/amidst/pull/225)：CLAUDE.md 閱讀順序改指向 Q1–Q5 交接文件（已標 ready，分支 `claude/current-instructions-q1q5`）。
- 2026-10-25 協調者交接：[COORDINATOR_HANDOFF_20261025.md](../agents/COORDINATOR_HANDOFF_20261025.md)；AGENTS.md 新增「Handoff documents go on GitHub」（交接與重現文件一律上傳 GitHub，LOCAL 只放原始資料）；新 issue [#218](https://github.com/Polalalabear/amidst/issues/218)（Q2／Q5 同鏡頭暫失後接不回）。
- 2026-10-25 新增文件：[Q1Q5_LOCAL_TEST_SETUP.md](Q1Q5_LOCAL_TEST_SETUP.md)（工作台本機測試啟動方式、所需檔案與 GitHub 拿不到的項目；組員可攜測試包交 Codex CX-10）。D77：r004 重疊區延後到 Q5 穩定後（[#93](https://github.com/Polalalabear/amidst/issues/93)）。
- 2026-10-25 合併：[#90](https://github.com/Polalalabear/amidst/pull/90) 以 merge commit `19fd4f5` 合進 `mainline/q1q5`（10:00:32Z）。原標示 do-not-merge，合併依據為 D75（[#93](https://github.com/Polalalabear/amidst/issues/93)）。
- 2026-10-25 關閉未合併：[#126](https://github.com/Polalalabear/amidst/pull/126)（09:54:20Z）。
- 決定：D72–D75 見 [#93](https://github.com/Polalalabear/amidst/issues/93)；D73 擋 baseline；D74 規定 r004 圖 R01–R08 全部修完、經 Claude 複核凍結後才產生正式事件 run；D75 規定正式索引用 §11 HSV 初值；D76 見 #93（本 PR 同時貼出）。
- 審查：[#212](https://github.com/Polalalabear/amidst/pull/212) Claude 審查 PASS_WITH_NOTES（09:26Z）；[#214](https://github.com/Polalalabear/amidst/pull/214) Claude 程式碼審查 PASS_WITH_NOTES（09:56Z，唯讀，不代替 G4／HSV 核定）。
- 收據：[#117](https://github.com/Polalalabear/amidst/issues/117) 獨立檢查收據已出；r004 圖 v2 不能照現狀凍結，須先修 v3 的 R01–R08（D74）。
- 新增文件：本 PR 加入 `docs/agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md`（驗收計畫，AC1–AC8，依協調者版本原樣保存，SHA-256 `0b2cd266…`）。
- 合進主線：第 1 批 [#136](https://github.com/Polalalabear/amidst/pull/136)、[#139](https://github.com/Polalalabear/amidst/pull/139)、[#140](https://github.com/Polalalabear/amidst/pull/140)、[#141](https://github.com/Polalalabear/amidst/pull/141)、[#143](https://github.com/Polalalabear/amidst/pull/143)、[#132](https://github.com/Polalalabear/amidst/pull/132) 經 10/25 Claude 審查，以 merge commit 合進 `mainline/q1q5`（批次 PR [#213](https://github.com/Polalalabear/amidst/pull/213)）。
- 合併：[#188](https://github.com/Polalalabear/amidst/pull/188) README 改寫（`f0b2336`）、[#190](https://github.com/Polalalabear/amidst/pull/190) 本文初版（`43ce67e`），都進主線。`codex/q1q5-staging` 這段期間沒有新合併。
- 規則：[#191](https://github.com/Polalalabear/amidst/pull/191) 在 AGENTS.md／CLAUDE.md 加入「開 PR 或 issue 都要更新本文」。
- 新增：PR [#187](https://github.com/Polalalabear/amidst/pull/187) r004 v2 審查包、[#189](https://github.com/Polalalabear/amidst/pull/189) Q5 狀態圖與 journal 檢查；issue [#186](https://github.com/Polalalabear/amidst/issues/186) Qwen3 流程未通過。
- 更新中的 Draft PR：[#172](https://github.com/Polalalabear/amidst/pull/172) Agent、[#174](https://github.com/Polalalabear/amidst/pull/174) Qwen3 執行環境、[#185](https://github.com/Polalalabear/amidst/pull/185) 雙模式比較。
- 更新的 issue：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#111](https://github.com/Polalalabear/amidst/issues/111)、[#112](https://github.com/Polalalabear/amidst/issues/112)、[#117](https://github.com/Polalalabear/amidst/issues/117)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#184](https://github.com/Polalalabear/amidst/issues/184)。沒有項目被關閉。

## Q1 依條件找鏡頭

### 已完成（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#164](https://github.com/Polalalabear/amidst/pull/164) | PR | Q1 evaluator for human expected cores and pinned frozen schemas (code only) | — | 已併入 staging，待審入主線 |

### 進行中（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#157](https://github.com/Polalalabear/amidst/pull/157) | PR（Draft） | Q1 index search and scoped pagination（依 #144 提案；blocked #156） | — | Draft，等 #156 |

### 未完成（2）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#109](https://github.com/Polalalabear/amidst/issues/109) | Issue | QT-16：Q1 依條件找相機（查詢模組＋類別別名表） | — | blocked：Q1 搜尋 #157 等 kit 修正 #156 |
| [#138](https://github.com/Polalalabear/amidst/issues/138) | Issue | QT-37：組員 Q1 條件查詢測試集與評分器（SYNTHETIC） | — | 組員 Q1 測試集未交；評估器已併入 staging（#164） |

**其他分類中也涉及 Q1 的項目：**

- 已完成：[#86](https://github.com/Polalalabear/amidst/pull/86)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#100](https://github.com/Polalalabear/amidst/issues/100)、[#101](https://github.com/Polalalabear/amidst/issues/101)、[#134](https://github.com/Polalalabear/amidst/pull/134)、[#136](https://github.com/Polalalabear/amidst/pull/136)、[#139](https://github.com/Polalalabear/amidst/pull/139)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#149](https://github.com/Polalalabear/amidst/pull/149)、[#151](https://github.com/Polalalabear/amidst/pull/151)、[#152](https://github.com/Polalalabear/amidst/pull/152)、[#155](https://github.com/Polalalabear/amidst/pull/155)、[#161](https://github.com/Polalalabear/amidst/pull/161)、[#167](https://github.com/Polalalabear/amidst/pull/167)、[#173](https://github.com/Polalalabear/amidst/pull/173)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#102](https://github.com/Polalalabear/amidst/issues/102)、[#103](https://github.com/Polalalabear/amidst/issues/103)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#146](https://github.com/Polalalabear/amidst/issues/146)、[#175](https://github.com/Polalalabear/amidst/pull/175)、[#176](https://github.com/Polalalabear/amidst/pull/176)、[#180](https://github.com/Polalalabear/amidst/pull/180)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#112](https://github.com/Polalalabear/amidst/issues/112)、[#113](https://github.com/Polalalabear/amidst/issues/113)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#118](https://github.com/Polalalabear/amidst/issues/118)、[#119](https://github.com/Polalalabear/amidst/issues/119)、[#120](https://github.com/Polalalabear/amidst/issues/120)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#133](https://github.com/Polalalabear/amidst/issues/133)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#147](https://github.com/Polalalabear/amidst/issues/147)、[#156](https://github.com/Polalalabear/amidst/issues/156)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#126](https://github.com/Polalalabear/amidst/pull/126)

## Q2 在畫面中找人

### 已完成（2）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#71](https://github.com/Polalalabear/amidst/pull/71) | PR | feat(workbench): player-grid pure module for 1/2/4/8 synced tiles | — | 已合併主線 |
| [#141](https://github.com/Polalalabear/amidst/pull/141) | PR | Q1–Q5 #107: 同鏡頭 selected-seed IoU 連接器與缺格邊界。 | — | 已合進主線（第 1 批，2026-10-25） |

### 進行中（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#107](https://github.com/Polalalabear/amidst/issues/107) | Issue | QT-14：同鏡頭最小 IoU 連接器與暫失觸發 | — | 同鏡頭 IoU 連接器已併入 staging（#141），待審入主線 |

**其他分類中也涉及 Q2 的項目：**

- 已完成：[#75](https://github.com/Polalalabear/amidst/pull/75)、[#80](https://github.com/Polalalabear/amidst/pull/80)、[#86](https://github.com/Polalalabear/amidst/pull/86)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#100](https://github.com/Polalalabear/amidst/issues/100)、[#101](https://github.com/Polalalabear/amidst/issues/101)、[#132](https://github.com/Polalalabear/amidst/pull/132)、[#134](https://github.com/Polalalabear/amidst/pull/134)、[#136](https://github.com/Polalalabear/amidst/pull/136)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#150](https://github.com/Polalalabear/amidst/pull/150)、[#152](https://github.com/Polalalabear/amidst/pull/152)、[#155](https://github.com/Polalalabear/amidst/pull/155)、[#166](https://github.com/Polalalabear/amidst/pull/166)、[#173](https://github.com/Polalalabear/amidst/pull/173)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#102](https://github.com/Polalalabear/amidst/issues/102)、[#104](https://github.com/Polalalabear/amidst/issues/104)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#169](https://github.com/Polalalabear/amidst/pull/169)、[#175](https://github.com/Polalalabear/amidst/pull/175)、[#177](https://github.com/Polalalabear/amidst/pull/177)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#184](https://github.com/Polalalabear/amidst/issues/184)、[#185](https://github.com/Polalalabear/amidst/pull/185)、[#187](https://github.com/Polalalabear/amidst/pull/187)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#110](https://github.com/Polalalabear/amidst/issues/110)、[#112](https://github.com/Polalalabear/amidst/issues/112)、[#113](https://github.com/Polalalabear/amidst/issues/113)、[#114](https://github.com/Polalalabear/amidst/issues/114)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#116](https://github.com/Polalalabear/amidst/issues/116)、[#117](https://github.com/Polalalabear/amidst/issues/117)、[#119](https://github.com/Polalalabear/amidst/issues/119)、[#121](https://github.com/Polalalabear/amidst/issues/121)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#133](https://github.com/Polalalabear/amidst/issues/133)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#178](https://github.com/Polalalabear/amidst/issues/178)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#158](https://github.com/Polalalabear/amidst/pull/158)、[#163](https://github.com/Polalalabear/amidst/pull/163)

## Q3 理解使用者語意

### 已完成（4）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#140](https://github.com/Polalalabear/amidst/pull/140) | PR | feat(q1q5): audited loopback Ollama provider | Q5 | 已合進主線（第 1 批，2026-10-25） |
| [#149](https://github.com/Polalalabear/amidst/pull/149) | PR | docs(evaluation): #146 Q1 Q3 question authoring boundaries | Q1 | 已併入 staging，待審入主線 |
| [#152](https://github.com/Polalalabear/amidst/pull/152) | PR | feat(q1q5): #106 literal Q3 parsing and audited deterministic fallback | Q1、Q2 | 已併入 staging，待審入主線 |
| [#165](https://github.com/Polalalabear/amidst/pull/165) | PR | Q3 human-annotation evaluator with exact pinned source clocks (code only) | — | 已併入 staging，待審入主線 |

### 進行中（5）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#105](https://github.com/Polalalabear/amidst/issues/105) | Issue | QT-12：Ollama 薄 provider（Q3／Q5 共用） | Q5 | Ollama provider 已併入 staging（#140），待審入主線 |
| [#106](https://github.com/Polalalabear/amidst/issues/106) | Issue | QT-13：Q3 解析：規則解析器、LLM 解析與兜底 | — | 規則解析與兜底已併入 staging（#152）；LLM 解析等 Qwen3（#174、#186） |
| [#146](https://github.com/Polalalabear/amidst/issues/146) | Issue | QT-41：組員出題依據文件（格式、可填資料、找得到／找不到） | Q1 | 出題指南已併入 staging（#149） |
| [#174](https://github.com/Polalalabear/amidst/pull/174) | PR（Draft） | feat(q1q5): pinned Qwen3 runtime, grounded schemas and contention measurements | Q5 | Draft；#186 未通過 |
| [#186](https://github.com/Polalalabear/amidst/issues/186) | Issue | 本機 Qwen3：schema／工具流程未通過，原呼叫預算仍逾時 | Q5 | Qwen3 schema／工具流程未通過，原呼叫預算逾時 |

### 未完成（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#89](https://github.com/Polalalabear/amidst/issues/89) | Issue | Q3：語意解析測試集與評分器（組員） | — | 組員 Q3 測試集未交；評分器已併入 staging（#165） |

**其他分類中也涉及 Q3 的項目：**

- 已完成：[#86](https://github.com/Polalalabear/amidst/pull/86)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#101](https://github.com/Polalalabear/amidst/issues/101)、[#134](https://github.com/Polalalabear/amidst/pull/134)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#151](https://github.com/Polalalabear/amidst/pull/151)、[#173](https://github.com/Polalalabear/amidst/pull/173)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#176](https://github.com/Polalalabear/amidst/pull/176)、[#180](https://github.com/Polalalabear/amidst/pull/180)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#112](https://github.com/Polalalabear/amidst/issues/112)、[#119](https://github.com/Polalalabear/amidst/issues/119)、[#120](https://github.com/Polalalabear/amidst/issues/120)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#133](https://github.com/Polalalabear/amidst/issues/133)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#147](https://github.com/Polalalabear/amidst/issues/147)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#126](https://github.com/Polalalabear/amidst/pull/126)

## Q4 判斷畫面是否含目標

### 已完成（2）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#159](https://github.com/Polalalabear/amidst/pull/159) | PR | Q4 frozen claim sampling and human TF evaluator (code only) | — | 已併入 staging，待審入主線 |
| [#167](https://github.com/Polalalabear/amidst/pull/167) | PR | Preserve finite raw detector boxes beyond image boundaries | Q1 | 已併入 staging，待審入主線 |

### 進行中（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#154](https://github.com/Polalalabear/amidst/pull/154) | PR（Draft） | feat(q1q5): #108 candidate evidence (blocked on no-color kit alignment) | — | Draft，等 #153 |

### 未完成（4）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#108](https://github.com/Polalalabear/amidst/issues/108) | Issue | QT-15：Q4 候選畫面證據聚合 | — | blocked：Q4 證據 #154 等無顏色 kit 對齊（#153） |
| [#114](https://github.com/Polalalabear/amidst/issues/114) | Issue | QT-21：HSV 顏色參數提案（r004 preview，Q-19） | Q2 | blocked：HSV 參數提案 #158 待 G6 |
| [#123](https://github.com/Polalalabear/amidst/issues/123) | Issue | QT-30：Q4 標註與評估（RT-DETR＋HSV） | — | blocked：Q4 標註與評估；評估器已併入 staging（#159） |
| [#128](https://github.com/Polalalabear/amidst/issues/128) | Issue | QT-32：組員 Q4 標註與偵測評估（人工標註） | — | 組員 Q4 人工標註未交 |

### 待確認（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#158](https://github.com/Polalalabear/amidst/pull/158) | PR（Draft） | HSV RGB proposal and measured ambiguity (G6 pending) | Q2 | Draft，HSV 參數待 G6 決定 |

**其他分類中也涉及 Q4 的項目：**

- 已完成：[#86](https://github.com/Polalalabear/amidst/pull/86)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#132](https://github.com/Polalalabear/amidst/pull/132)、[#136](https://github.com/Polalalabear/amidst/pull/136)、[#139](https://github.com/Polalalabear/amidst/pull/139)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#151](https://github.com/Polalalabear/amidst/pull/151)、[#155](https://github.com/Polalalabear/amidst/pull/155)、[#161](https://github.com/Polalalabear/amidst/pull/161)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#103](https://github.com/Polalalabear/amidst/issues/103)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#177](https://github.com/Polalalabear/amidst/pull/177)、[#180](https://github.com/Polalalabear/amidst/pull/180)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#113](https://github.com/Polalalabear/amidst/issues/113)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#118](https://github.com/Polalalabear/amidst/issues/118)、[#121](https://github.com/Polalalabear/amidst/issues/121)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#147](https://github.com/Polalalabear/amidst/issues/147)、[#153](https://github.com/Polalalabear/amidst/issues/153)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#90](https://github.com/Polalalabear/amidst/pull/90)

## Q5 決定是否切鏡

### 已完成（3）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#150](https://github.com/Polalalabear/amidst/pull/150) | PR | feat(q1q5): #104 pinned static graph validation and D28 candidates | Q2 | 已併入 staging，待審入主線 |
| [#160](https://github.com/Polalalabear/amidst/pull/160) | PR | Q5 evaluator verifies frozen outputs before reading evaluation script (code only) | — | 已併入 staging，待審入主線 |
| [#166](https://github.com/Polalalabear/amidst/pull/166) | PR | Restrict candidate run cameras before D28 ranking and top-k | Q2 | 已併入 staging，待審入主線 |

### 進行中（7）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#104](https://github.com/Polalalabear/amidst/issues/104) | Issue | QT-11：兩層圖 schema／loader 與 D28 候選排序 | Q2 | 靜態圖驗證與 D28 候選已併入 staging（#150、#166），待審入主線 |
| [#169](https://github.com/Polalalabear/amidst/pull/169) | PR（Draft） | Q5 RULE_ONLY controller（依 #144 提案；blocked #145/#153） | Q2 | Draft，等 #145、#153 |
| [#172](https://github.com/Polalalabear/amidst/pull/172) | PR（Draft） | feat(q5): sequential Agent, versioned guidance profiles and exact replay | — | Draft，依序查證 Agent、guidance profiles 與精確重播 |
| [#184](https://github.com/Polalalabear/amidst/issues/184) | Issue | Q5 雙模式工程比較：後端 FOUND／LOST 與 Agent 候選決策 | Q2 | Q5 雙模式比較，載體為 #185 |
| [#185](https://github.com/Polalalabear/amidst/pull/185) | PR（Draft） | feat(q1q5): event-mode comparison and reproducible baseline telemetry | Q2 | Draft，FOUND／LOST 與 Agent 比較、baseline telemetry |
| [#189](https://github.com/Polalalabear/amidst/pull/189) | PR（Draft） | Q5：As-Is Statechart 與獨立 Journal Invariants 驗證 | — | Draft（10-23 新增），Q5 As-Is 狀態圖與 journal 不變量檢查 |
| [#229](https://github.com/Polalalabear/amidst/pull/229) | PR（Draft） | docs(q5): Q5 逐事件決策窗（D79 核定版） | — | Draft（10-25 新增）；上傳 D79 核定的決策窗提案，更正 K1 公式筆誤，交 Codex 的 #219／#115 引用 |

### 未完成（5）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#110](https://github.com/Polalalabear/amidst/issues/110) | Issue | QT-17：Q5 Controller：狀態機與 RULE_ONLY 決定性切鏡 | Q2 | blocked：RULE_ONLY 控制器 #169 等 #145、#153 |
| [#111](https://github.com/Polalalabear/amidst/issues/111) | Issue | QT-18：Q5 AGENT_SEQUENTIAL：typed tools 與有界輪詢 | — | blocked：Agent #172 仍為 Draft；空候選契約缺口 #183 |
| [#116](https://github.com/Polalalabear/amidst/issues/116) | Issue | QT-23：r004 兩層圖資料與出口 ROI（靜態） | Q2 | blocked：r004 兩層圖與出口 ROI #163 待 G4 |
| [#117](https://github.com/Polalalabear/amidst/issues/117) | Issue | QT-24：r004 靜態圖獨立檢查（K7 類型） | Q2 | 收據已出；v2 不能照現狀凍結，待 Codex 修 v3 的 R01–R08（D74） |
| [#129](https://github.com/Polalalabear/amidst/issues/129) | Issue | QT-33：組員 Q5 切鏡評估器 | — | 組員 Q5 情境未交；評估器已併入 staging（#160） |

### 待確認（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#163](https://github.com/Polalalabear/amidst/pull/163) | PR（Draft） | r004 static graph and eight exit ROI proposals (G4 pending) | Q2 | Draft，待 G4；r004 v2（#187）可能取代，待確認 |

**其他分類中也涉及 Q5 的項目：**

- 已完成：[#86](https://github.com/Polalalabear/amidst/pull/86)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#125](https://github.com/Polalalabear/amidst/pull/125)、[#132](https://github.com/Polalalabear/amidst/pull/132)、[#140](https://github.com/Polalalabear/amidst/pull/140)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#161](https://github.com/Polalalabear/amidst/pull/161)、[#168](https://github.com/Polalalabear/amidst/pull/168)、[#171](https://github.com/Polalalabear/amidst/pull/171)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#105](https://github.com/Polalalabear/amidst/issues/105)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#174](https://github.com/Polalalabear/amidst/pull/174)、[#177](https://github.com/Polalalabear/amidst/pull/177)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#186](https://github.com/Polalalabear/amidst/issues/186)、[#187](https://github.com/Polalalabear/amidst/pull/187)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#121](https://github.com/Polalalabear/amidst/issues/121)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#170](https://github.com/Polalalabear/amidst/issues/170)、[#178](https://github.com/Polalalabear/amidst/issues/178)、[#183](https://github.com/Polalalabear/amidst/issues/183)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#95](https://github.com/Polalalabear/amidst/issues/95)、[#126](https://github.com/Polalalabear/amidst/pull/126)

## 共用：契約、規則、參數與一致性檢查

### 已完成（13）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#86](https://github.com/Polalalabear/amidst/pull/86) | PR | docs(contracts): Q1–Q5 first-demo contract v1 draft (Q1_Q2_FIRST_DEMO_V1) — do not merge | Q1、Q2、Q3、Q4、Q5 | 已合併主線 |
| [#92](https://github.com/Polalalabear/amidst/pull/92) | PR | docs: Q1–Q5 first demo plan, D64 gates and contract review | Q1、Q2、Q3、Q4、Q5 | 已合併主線 |
| [#94](https://github.com/Polalalabear/amidst/issues/94) | Issue | QT-01：契約 #86 定稿：處理 Codex 7 項修正與 D64 | Q1、Q2、Q3、Q4、Q5 | 已完成 |
| [#96](https://github.com/Polalalabear/amidst/issues/96) | Issue | QT-03：審查 Codex 修訂稿 #92 | Q1、Q2、Q3、Q4、Q5 | 已完成 |
| [#125](https://github.com/Polalalabear/amidst/pull/125) | PR | docs(rules): D64 Q1–Q5 Agent camera-switch exception (draft, do not merge) | Q5 | 已合併主線 |
| [#142](https://github.com/Polalalabear/amidst/pull/142) | PR | docs(q1q5): bind D65 D67 D68 initial parameters and unresolved fields | Q1、Q2、Q3、Q4、Q5 | 已併入 staging，待審入主線 |
| [#148](https://github.com/Polalalabear/amidst/pull/148) | PR | docs(contracts): #144 D69 D71 decisions and remaining wire proposals | Q1、Q2、Q3、Q4、Q5 | 已併入 staging，待審入主線 |
| [#161](https://github.com/Polalalabear/amidst/pull/161) | PR | Contract §14: evaluation, media grants and HSV options (PROPOSED only) | Q1、Q4、Q5 | 已併入 staging，待審入主線 |
| [#168](https://github.com/Polalalabear/amidst/pull/168) | PR | Contract §14: controller journal and manual-control options (PROPOSED) | Q5 | 已併入 staging，待審入主線 |
| [#171](https://github.com/Polalalabear/amidst/pull/171) | PR | Contract §14: Agent trace and failure-provenance options (PROPOSED) | Q5 | 已併入 staging，待審入主線 |
| [#173](https://github.com/Polalalabear/amidst/pull/173) | PR | Contract §14: Q transport and parse-lineage options (PROPOSED) | Q1、Q2、Q3 | 已併入 staging，待審入主線 |
| [#179](https://github.com/Polalalabear/amidst/pull/179) | PR | 契約 §14：審核 hash 與預期清單隔離選項（依 #144 提案） | — | 已併入 staging，待審入主線 |
| [#126](https://github.com/Polalalabear/amidst/pull/126) | PR | docs: propose bounded Q1-Q5 search and fallback budgets | Q1、Q3、Q5 | 關閉未合併（2026-10-25 09:54Z）；D67 初始值的記載不變 |

### 進行中（4）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#98](https://github.com/Polalalabear/amidst/issues/98) | Issue | QT-05：§11 參數組 v1 提案（HSV 除外） | Q1、Q2、Q3、Q5 | §11 參數組已部分綁定（#142，staging） |
| [#127](https://github.com/Polalalabear/amidst/pull/127) | PR（Draft） | feat(evaluation): Q1–Q5 contract conformance kit (draft) | Q1、Q2、Q3、Q4、Q5 | 一致性檢查包 v0.2.1（Draft），等 #145 對齊 |
| [#135](https://github.com/Polalalabear/amidst/pull/135) | PR（Draft） | docs(contracts): Q1–Q5 契約釐清版（#127 回報，不改語意與數值） | Q1、Q2、Q3、Q4、Q5 | 契約釐清版（Draft）；補完見 #144 |
| [#144](https://github.com/Polalalabear/amidst/issues/144) | Issue | QT-39：契約 #135 補完（寫入 D69＋處理 Codex 跳過原因） | Q1、Q2、Q3、Q4、Q5 | §14 選項已併入 staging（#148、#161、#168、#171、#173、#179），待寫回 #135 |

### 未完成（8）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#99](https://github.com/Polalalabear/amidst/issues/99) | Issue | QT-06：Q1–Q5 合約符合性測試包 | Q1、Q2、Q3、Q4、Q5 | 標 blocked；一致性檢查包 #127 仍為 Draft |
| [#133](https://github.com/Polalalabear/amidst/issues/133) | Issue | Conformance kit: CLOCK_MAPPING_RULES rejects an explicit DST fold offset | Q1、Q2、Q3 | kit 問題：DST fold 偏移被拒，尚無修正 PR |
| [#145](https://github.com/Polalalabear/amidst/issues/145) | Issue | QT-40：#127 測試包對齊契約 #135 最終版並合入 | Q1、Q2、Q3、Q4、Q5 | blocked：kit 對齊契約最終版 |
| [#153](https://github.com/Polalalabear/amidst/issues/153) | Issue | #127/#145: no-color Q4 MATCH_STRONG with null verdict fails presence invariant | Q4 | kit 問題：無顏色 Q4 的 null verdict 被拒，阻擋 #154 |
| [#156](https://github.com/Polalalabear/amidst/issues/156) | Issue | #127 Q1_RESULT_ORDER：最後一頁錯將 results_total 視為當頁筆數 | Q1 | kit 問題：Q1 最後一頁筆數判錯，阻擋 #157 |
| [#170](https://github.com/Polalalabear/amidst/issues/170) | Issue | Q5 conformance：D69 link 誤分類、失敗 digest 與正常候選耗盡的 Agent flags | Q5 | kit 問題：Q5 Agent flags 與 link 分類 |
| [#178](https://github.com/Polalalabear/amidst/issues/178) | Issue | [#127] 空 decisions／links journal 被 DOCUMENT_LOADABLE 判成未知 schema | Q2、Q5 | kit 問題：空 journal 被判成未知 schema |
| [#183](https://github.com/Polalalabear/amidst/issues/183) | Issue | [契約缺口] 空候選證據無法合法 NEXT_CANDIDATE，阻斷 Agent top-k 輪詢 | Q5 | 契約缺口：空候選無法 NEXT_CANDIDATE，阻擋 Agent 輪詢 |

### 待確認（2）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#88](https://github.com/Polalalabear/amidst/issues/88) | Issue | QA：Q1–Q5 第一版計畫與契約 #86 核准 | Q1、Q2、Q3、Q4、Q5 | D65 已核准，#86、#92 已合併；待確認是否關閉 |
| [#95](https://github.com/Polalalabear/amidst/issues/95) | Issue | QT-02：DEVELOPMENT_RULES：Q1–Q5 Agent 有界例外條文（D64） | Q5 | 條文已由 #125 合入主線；待確認是否關閉 |

## 共用：r004 場景、資料、索引與儲存

### 已完成（9）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#75](https://github.com/Polalalabear/amidst/pull/75) | PR | Add controlled scene safe loaders and v2 fixture API skeletons | Q2 | 已合併主線 |
| [#80](https://github.com/Polalalabear/amidst/pull/80) | PR | feat(v2): 接入 A／B1 真實 RGB 與 scoped media token（2a） | Q2 | 已合併主線 |
| [#101](https://github.com/Polalalabear/amidst/issues/101) | Issue | QT-08：時間對應模組（來源時鐘 ↔ 牆鐘） | Q1、Q2、Q3 | 已完成 |
| [#132](https://github.com/Polalalabear/amidst/pull/132) | PR | docs: propose r004 camera scope and bounded preview plan | Q2、Q4、Q5 | 已合進主線（第 1 批，2026-10-25） |
| [#134](https://github.com/Polalalabear/amidst/pull/134) | PR | feat(q1q5): resolve declared clocks and bounded time coverage | Q1、Q2、Q3 | 已合併主線 |
| [#136](https://github.com/Polalalabear/amidst/pull/136) | PR | Q1–Q5 #102: Pinned JSON/JSONL store with fail-closed metadata access | Q1、Q2、Q4 | 已合進主線（第 1 批，2026-10-25） |
| [#139](https://github.com/Polalalabear/amidst/pull/139) | PR | Q1–Q5 #103: Offline source-pinned index producer and parameterized HSV evidence | Q1、Q4 | 已合進主線（第 1 批，2026-10-25） |
| [#155](https://github.com/Polalalabear/amidst/pull/155) | PR | docs(r004): #113 static export and measured 45-frame preview receipt | Q1、Q2、Q4 | 已併入 staging，待審入主線 |
| [#162](https://github.com/Polalalabear/amidst/pull/162) | PR | r004 receipt: user selects 90 degree CAM_WIDE | — | 已併入 staging，待審入主線 |

### 進行中（4）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#97](https://github.com/Polalalabear/amidst/issues/97) | Issue | QT-04：r004 修改表提案定稿（文件） | Q1、Q2、Q4、Q5 | r004 修改表提案 #132 已併入 staging；r004 v2 預審見 #187 |
| [#102](https://github.com/Polalalabear/amidst/issues/102) | Issue | QT-09：store 介面（版本化 JSON＋每 run JSONL） | Q1、Q2 | store 已併入 staging（#136），待審入主線 |
| [#103](https://github.com/Polalalabear/amidst/issues/103) | Issue | QT-10：偵測索引產生器（RT-DETR＋上半身 HSV） | Q1、Q4 | 偵測索引產生器與 HSV 證據已併入 staging（#139），待審入主線 |
| [#187](https://github.com/Polalalabear/amidst/pull/187) | PR（Draft） | r004 v2: source-bound entry/exit zones and portal review packet | Q2、Q5 | Draft（B 級），r004 v2 出入口區與門洞審查包 |

### 未完成（3）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#113](https://github.com/Polalalabear/amidst/issues/113) | Issue | QT-20：r004 建檔、靜態校正匯出與廣角小批 preview | Q1、Q2、Q4 | 標 blocked（內文寫 needs-auth）；r004 靜態匯出 #155、廣角鏡頭 #162 已併入 staging |
| [#115](https://github.com/Polalalabear/amidst/issues/115) | Issue | QT-22：A4／B4 事件 run 產製與 safe bundle | Q1、Q2、Q4、Q5 | 標 blocked（內文寫 needs-auth）：A4／B4 事件 run 待授權 |
| [#118](https://github.com/Polalalabear/amidst/issues/118) | Issue | QT-25：r004 正式偵測索引產製 | Q1、Q4 | blocked：r004 正式偵測索引，等 #115 |

## 共用：工作台、HTTP 與 Demo

### 已完成（7）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#72](https://github.com/Polalalabear/amidst/pull/72) | PR | docs(agents): 工作台 v2 設計（功能保留矩陣、資訊架構、視覺規範、實作計畫） | — | 關閉未合併 |
| [#74](https://github.com/Polalalabear/amidst/pull/74) | PR | feat(workbench-v2): V2-1 外框、token、store、時鐘 | — | 已合併主線 |
| [#79](https://github.com/Polalalabear/amidst/pull/79) | PR | feat(workbench-v2): V2-2 api、不確定度驗證與 SYNTHETIC fixture | — | 已合併主線 |
| [#100](https://github.com/Polalalabear/amidst/issues/100) | Issue | QT-07：workbench-v2 底座合入 mainline（U-1：#74、#79、#71） | Q1、Q2 | 已完成 |
| [#181](https://github.com/Polalalabear/amidst/pull/181) | PR | Demo 腳本草稿與可重現工程啟動指令（依 #144 提案） | Q1、Q2、Q3、Q4、Q5 | 已併入 staging，待審入主線 |
| [#182](https://github.com/Polalalabear/amidst/pull/182) | PR | Demo 草稿：固定最終 replay provenance 工程包（依 #144 提案） | Q1、Q2、Q3、Q4、Q5 | 已併入 staging，待審入主線 |
| [#90](https://github.com/Polalalabear/amidst/pull/90) | PR | docs(agents): workbench-v2 Q1–Q5 畫面設計與審核模式（draft）— do not merge | Q1、Q2、Q3、Q4、Q5 | 已合併主線（merge commit `19fd4f5`，2026-10-25 10:00Z）；原標示 do-not-merge，合併依據待 #93 核對 |

### 進行中（4）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#175](https://github.com/Polalalabear/amidst/pull/175) | PR（Draft） | workbench T1：Q 資料層與外框（依 #144 提案） | Q1、Q2 | Draft，工作台 T1 |
| [#176](https://github.com/Polalalabear/amidst/pull/176) | PR（Draft） | workbench T2：Q3 直接執行與 Q1 三區結果牆（依 #144 提案） | Q1、Q3 | Draft，工作台 T2 |
| [#177](https://github.com/Polalalabear/amidst/pull/177) | PR（Draft） | workbench T3：多鏡頭、事件硬切與審核紀錄（依 #144 提案） | Q2、Q4、Q5 | Draft，工作台 T3 |
| [#180](https://github.com/Polalalabear/amidst/pull/180) | PR（Draft） | workbench T4：唯讀審核、凍結 pins 與匯出隔離（依 #144 提案） | Q1、Q2、Q3、Q4、Q5 | Draft，工作台 T4 |

### 未完成（7）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#112](https://github.com/Polalalabear/amidst/issues/112) | Issue | QT-19：Q 線 HTTP 端點與 #80 接線（R-1–R-7） | Q1、Q2、Q3 | blocked：Q 線 HTTP 端點與 #80 接線；本機模型接線在 #174 |
| [#119](https://github.com/Polalalabear/amidst/issues/119) | Issue | QT-26：workbench-v2 T1：Q 資料層與外框改裝 | Q1、Q2、Q3 | blocked：對應 PR #175（Draft） |
| [#120](https://github.com/Polalalabear/amidst/issues/120) | Issue | QT-27：workbench-v2 T2：Q3 查詢列與 Q1 結果牆 | Q1、Q3 | blocked：對應 PR #176（Draft） |
| [#121](https://github.com/Polalalabear/amidst/issues/121) | Issue | QT-28：workbench-v2 T3：Q2 主畫面、時間軸、Q4 證據、Q5 逐步紀錄 | Q2、Q4、Q5 | blocked：對應 PR #177（Draft） |
| [#122](https://github.com/Polalalabear/amidst/issues/122) | Issue | QT-29：workbench-v2 T4：審核模式 | Q1、Q2、Q3、Q4、Q5 | blocked：對應 PR #180（Draft） |
| [#124](https://github.com/Polalalabear/amidst/issues/124) | Issue | QT-31：Q1–Q5 端到端 browser acceptance 與 Demo 腳本 | Q1、Q2、Q3、Q4、Q5 | blocked：端到端瀏覽器驗收；Demo 腳本草稿已併入 staging（#181、#182） |
| [#130](https://github.com/Polalalabear/amidst/issues/130) | Issue | QT-34：組員 瀏覽器驗收（人工操作） | Q1、Q2、Q3、Q4、Q5 | 組員瀏覽器驗收未開始 |

## 流程：任務板、交接與文件

### 已完成（9）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#3](https://github.com/Polalalabear/amidst/pull/3) | PR | docs: update main README with current demo and research progress | — | 已合併 `main` |
| [#52](https://github.com/Polalalabear/amidst/pull/52) | PR | docs(agents): 2026-10-17 status update and coordinator handoff | — | 關閉未合併，由 #70 取代 |
| [#70](https://github.com/Polalalabear/amidst/pull/70) | PR | docs(agents): coordinator handoff 2026-10-18 (D25 pivot) | — | 關閉未合併 |
| [#73](https://github.com/Polalalabear/amidst/pull/73) | PR | docs(qa): 使用者問答紀錄與導覽索引（78 題） | — | 關閉未合併 |
| [#91](https://github.com/Polalalabear/amidst/pull/91) | PR | docs(agents): make mainline/q1q5 the integration branch (D63) | — | 已合併主線 |
| [#143](https://github.com/Polalalabear/amidst/pull/143) | PR | Q1–Q5 #131: 將既有 LOCAL finalization 移除計畫整理為 repo 文件。 | — | 已合進主線（第 1 批，2026-10-25） |
| [#151](https://github.com/Polalalabear/amidst/pull/151) | PR | feat(evaluation): #147 deterministic pilot packs and human-return importer | Q1、Q3、Q4 | 已併入 staging，待審入主線 |
| [#188](https://github.com/Polalalabear/amidst/pull/188) | PR | docs(readme): rewrite README for the Q1–Q5 first demo and current progress | — | 已合併主線 |
| [#190](https://github.com/Polalalabear/amidst/pull/190) | PR | docs(progress): classify every PR and issue by Q1–Q5 and status | — | 已合併主線 |

### 進行中（7）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#228](https://github.com/Polalalabear/amidst/pull/228) | PR | docs(q1q5): P1 工程預驗收走查清單（AC1–AC8） | Q1、Q2、Q3、Q4、Q5 | Draft；CL-4 準備，新增 [走查清單](Q1Q5_P1_WALKTHROUGH_CHECKLIST.md)，等 CX-5 交付後走查；P1 不是正式成績（D76） |
| [#225](https://github.com/Polalalabear/amidst/pull/225) | PR | docs(claude): point CLAUDE.md reading order at Q1–Q5 handoff | — | CLAUDE.md 閱讀順序改指向 Q1–Q5 交接文件，Office 分工限定 Office demo；Sonnet 正式審查 PASS，待合併 |
| 本 PR（分支 `claude/q1q5-baseline-acceptance-plan`） | PR | docs: Q1–Q5 baseline acceptance plan and progress update (2026-10-25) | Q1、Q2、Q3、Q4、Q5 | 新增驗收計畫文件並更新本文；待協調者核對後合併 |
| [#83](https://github.com/Polalalabear/amidst/pull/83) | PR | docs(agents): 決策索引、系統總覽、組員上手指南 | — | 依 Codex 審查（6309402033）修正：組員流程改成不用 Git 的資料夾包（說明檔＋`RETURN/`＋核對工具）、補 D68–D78、關卡與兩種組員工作；已 merge 最新 `mainline/q1q5`，待 Codex 複審，未合併 |
| [#93](https://github.com/Polalalabear/amidst/issues/93) | Issue | Q1–Q5 任務板（從這裡開始） | Q1、Q2、Q3、Q4、Q5 | Q1–Q5 任務板，10-23 更新 |
| [#131](https://github.com/Polalalabear/amidst/issues/131) | Issue | QT-35：Codex finalization 搬移計畫（文件） | — | 標 ready（內文寫 needs-auth）；搬移計畫文件已併入 staging（#143） |
| [#191](https://github.com/Polalalabear/amidst/pull/191) | PR | docs(agents): update the Q1–Q5 progress guide with every new PR and issue | — | 在 AGENTS.md／CLAUDE.md 加入本文的維護規則，待合併 |

### 未完成（2）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#137](https://github.com/Polalalabear/amidst/issues/137) | Issue | QT-36：組員 交接試跑（照 TEAM_ONBOARDING 從零開始） | — | 組員交接試跑未開始 |
| [#147](https://github.com/Polalalabear/amidst/issues/147) | Issue | QT-42：組員審查包（資料夾）產生器與回收匯入器 | Q1、Q3、Q4 | 文字審查包 #151 已併入 staging；圖片包等 #115、#118 |

### 待確認（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#87](https://github.com/Polalalabear/amidst/issues/87) | Issue | GitHub 整理紀錄（2026-10-20，D63 後） | — | D63 後的 GitHub 整理紀錄，最後更新 10-20；待確認是否關閉 |

## 暫停：跨鏡頭盲區 3D 重建線

**已完成（36）**

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#10](https://github.com/Polalalabear/amidst/pull/10) | PR | docs(contracts): K0 interval observation, blind hypothesis and frame retrieval drafts | — | 已合併 `claude/office-demo-visualization` |
| [#11](https://github.com/Polalalabear/amidst/pull/11) | PR | feat(eval): RQ1 single-camera ground-contact report and charts (K2) | — | 已合併 `claude/office-demo-visualization` |
| [#14](https://github.com/Polalalabear/amidst/issues/14) | Issue | K0: Confirm interval / hypothesis / retrieval data contracts | — | 已完成 |
| [#16](https://github.com/Polalalabear/amidst/issues/16) | Issue | K1: Blind-interval hypothesis module | — | 已完成 |
| [#20](https://github.com/Polalalabear/amidst/issues/20) | Issue | K3: Workbench: scene presets, quality flags and interval observations | — | 已完成 |
| [#21](https://github.com/Polalalabear/amidst/issues/21) | Issue | K4: Workbench: hypothesis bundle and reachable-region bands (P0) | — | 已完成 |
| [#22](https://github.com/Polalalabear/amidst/issues/22) | Issue | K5: Suggested-frames wall and negative-evidence pruning (P1) | — | 已完成 |
| [#23](https://github.com/Polalalabear/amidst/issues/23) | Issue | K6: Demo mode, browser acceptance and backup recording | — | 已完成 |
| [#30](https://github.com/Polalalabear/amidst/issues/30) | Issue | K7: Verify the derived map against annotations and offline routes | — | 已完成 |
| [#31](https://github.com/Polalalabear/amidst/pull/31) | PR | K3: workbench scene presets, contact_quality flags and unavailable layers | — | 已合併 `claude/office-demo-visualization` |
| [#33](https://github.com/Polalalabear/amidst/pull/33) | PR | K1: blind-interval hypothesis module (CP2 #26 — do not merge) | — | 已合併 `claude/office-demo-visualization` |
| [#34](https://github.com/Polalalabear/amidst/pull/34) | PR | C6: screen fixed 5 Hz routes and rerender person-sized Office (CP1 — do not merge) | — | 關閉未合併 |
| [#35](https://github.com/Polalalabear/amidst/pull/35) | PR | K4: blind-interval hypothesis bundle and reachable-region layer (CP3 #27 — do not merge) | — | 已合併 `claude/office-demo-visualization` |
| [#36](https://github.com/Polalalabear/amidst/pull/36) | PR | feat(hypothesis): K5 pruning re-run + retrieval negative evidence (CP3 #27 — do not merge) | — | 已合併 `claude/office-demo-visualization` |
| [#38](https://github.com/Polalalabear/amidst/pull/38) | PR | K6: Demo mode skeleton + acceptance record + script draft (CP3 #27 — do not merge) | — | 已合併 `claude/office-demo-visualization` |
| [#41](https://github.com/Polalalabear/amidst/pull/41) | PR | feat(eval): K7 independent map verification — CP2 #26 — do not merge | — | 已合併 `claude/office-demo-visualization` |
| [#42](https://github.com/Polalalabear/amidst/pull/42) | PR | feat(workbench): K3 ground_estimate point/segment display — CP2 #26 — do not merge | — | 已合併 `claude/office-demo-visualization` |
| [#45](https://github.com/Polalalabear/amidst/pull/45) | PR | docs(contracts): K0 v1.1 — R1, D15–D18, K5 revisions (needs Codex confirmation) | — | 關閉未合併 |
| [#48](https://github.com/Polalalabear/amidst/pull/48) | PR | feat(hypothesis): K1 native D15 restricted-policy layer — CP2 #26 — do not merge | — | 已合併 `claude/office-demo-visualization` |
| [#56](https://github.com/Polalalabear/amidst/pull/56) | PR | docs(agents): K8 synthetic capability demo design (D23) — do not merge | — | 關閉未合併 |
| [#57](https://github.com/Polalalabear/amidst/pull/57) | PR | feat(hypothesis): K8c S2 cross-camera candidate screen | — | 已合併 `claude/office-demo-visualization` |
| [#58](https://github.com/Polalalabear/amidst/pull/58) | PR | feat(hypothesis): K8a synthetic declared footprint (contract v1.2 draft) | — | 關閉未合併 |
| [#59](https://github.com/Polalalabear/amidst/issues/59) | Issue | K8 合成能力展示（D23／D24） | — | 已完成 |
| [#60](https://github.com/Polalalabear/amidst/pull/60) | PR | feat(synthetic): K8b synthetic S1/S2/S3 generator and frontend fixture — do not merge | — | 關閉未合併 |
| [#61](https://github.com/Polalalabear/amidst/pull/61) | PR | feat(evaluation): RQ1 single-camera ground-interval evaluation | — | 已合併 `claude/office-demo-visualization` |
| [#62](https://github.com/Polalalabear/amidst/pull/62) | PR | test(k5): frozen real person frame-wall HTTP fixtures | — | 關閉未合併 |
| [#65](https://github.com/Polalalabear/amidst/pull/65) | PR | docs(agents): controlled-scene demo work package A — Claude reply, contract v1 and UX sketch (draft) | — | 關閉未合併 |
| [#66](https://github.com/Polalalabear/amidst/issues/66) | Issue | CS-A：A 包（Claude 回覆、契約、UX 草圖）與 Codex 可行性確認 | — | 已完成 |
| [#67](https://github.com/Polalalabear/amidst/issues/67) | Issue | CS-R：可重用模組併入整合分支 | — | 已完成 |
| [#68](https://github.com/Polalalabear/amidst/issues/68) | Issue | CS-B：場景驗收（事件 A、B1） | — | 已完成 |
| [#69](https://github.com/Polalalabear/amidst/issues/69) | Issue | CS-C：查找與重現 | — | 已完成 |
| [#76](https://github.com/Polalalabear/amidst/pull/76) | PR | docs(agents): 受控場景數值門檻提案（CS-Q9／CS-Q15／D44／D45／D47）— do not merge | — | 關閉未合併 |
| [#78](https://github.com/Polalalabear/amidst/pull/78) | PR | feat(cs-b): D47 本機人工審查頁 | — | 關閉未合併 |
| [#81](https://github.com/Polalalabear/amidst/pull/81) | PR | docs(agents): 第二批後端真實資料接入 v2 整合規格（2a–2d） | — | 關閉未合併 |
| [#84](https://github.com/Polalalabear/amidst/issues/84) | Issue | E1–E5：凍結後評估工具（D56 Q19–Q23） | — | 已完成 |
| [#85](https://github.com/Polalalabear/amidst/issues/85) | Issue | Q11：靜態遮擋邊緣容差 0／1／2／4 px 改判格數比較 | — | 已完成 |

**待確認（2）**

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#77](https://github.com/Polalalabear/amidst/pull/77) | PR（Draft） | feat(scene-markers): E 包 受控場景標記範本與 safe 側 validator | — | 受控場景 E 包標記範本與 validator（舊 3D 線），base 為主線；待確認保留或關閉 |
| [#82](https://github.com/Polalalabear/amidst/pull/82) | PR（Draft） | feat(eval): K7 r003 static-geometry verification for O10 — do not merge before user approval | — | K7 r003 靜態幾何驗證（舊線），標示使用者核准前不合併；r004 改由 #117 檢查，待確認是否關閉 |

## 歷史：Office Demo 與 Phase 1／2

**已完成（36）**

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#1](https://github.com/Polalalabear/amidst/pull/1) | PR | docs: refresh current engineering navigation and references | — | 已合併 `codex/simulation-engineering` |
| [#2](https://github.com/Polalalabear/amidst/pull/2) | PR | docs: align scoped Phase1 navigation with final acceptance | — | 已合併 `phase1/finalization-sprint` |
| [#4](https://github.com/Polalalabear/amidst/pull/4) | PR | fix(workbench): keep review markers from implying continuity across breaks (Task B) | — | 已合併 `claude/office-demo-visualization` |
| [#5](https://github.com/Polalalabear/amidst/pull/5) | PR | docs: audit Auditorium geometry omissions and bounded repair plan (Task C) | — | 關閉未合併 |
| [#6](https://github.com/Polalalabear/amidst/pull/6) | PR | fix(workbench): restore source-bound Auditorium display geometry | — | 已合併 `claude/office-demo-visualization` |
| [#7](https://github.com/Polalalabear/amidst/pull/7) | PR | fix(workbench): make Office 2D/3D evidence correspondence explicit | — | 已合併 `claude/office-demo-visualization` |
| [#8](https://github.com/Polalalabear/amidst/pull/8) | PR | fix(demo): reliable latest Office launcher and bounded contact QA | — | 已合併 `claude/office-demo-visualization` |
| [#9](https://github.com/Polalalabear/amidst/pull/9) | PR | docs(engineering): add Office green-marker pipeline map | — | 已合併 `claude/office-demo-visualization` |
| [#12](https://github.com/Polalalabear/amidst/pull/12) | PR | feat: Office 多場景預設與接地品質旗標 | — | 已合併 `claude/office-demo-visualization` |
| [#13](https://github.com/Polalalabear/amidst/issues/13) | Issue | C3b: Per-scene isolation in Office preset loading | — | 已完成 |
| [#15](https://github.com/Polalalabear/amidst/issues/15) | Issue | C4a: Hybrid contact estimator (foot point or head-ray interval) | — | 已完成 |
| [#17](https://github.com/Polalalabear/amidst/issues/17) | Issue | C4b: Integrate blind-interval hypotheses into the backend API | — | 已完成 |
| [#18](https://github.com/Polalalabear/amidst/issues/18) | Issue | C5: Camera floor-visibility index, retrieval API and scale-up latency | — | 已完成 |
| [#19](https://github.com/Polalalabear/amidst/issues/19) | Issue | C6: Multi-camera feasibility check and benchmark routes | — | 已完成 |
| [#24](https://github.com/Polalalabear/amidst/issues/24) | Issue | R1: Merge integration into main, tag, and fill README results | — | 已完成 |
| [#25](https://github.com/Polalalabear/amidst/issues/25) | Issue | CP1 (target 10/18): Foundations review | — | 已完成 |
| [#26](https://github.com/Polalalabear/amidst/issues/26) | Issue | CP2 (target 10/24): Integration review | — | 已完成 |
| [#27](https://github.com/Polalalabear/amidst/issues/27) | Issue | CP3 (10/29): Feature freeze review | — | 已完成 |
| [#28](https://github.com/Polalalabear/amidst/issues/28) | Issue | CP4 (10/30–31): Release review | — | 已完成 |
| [#29](https://github.com/Polalalabear/amidst/issues/29) | Issue | C7: Map authority — derive walkable area, portals and obstacles from source geometry | — | 已完成 |
| [#32](https://github.com/Polalalabear/amidst/pull/32) | PR | fix: C3b Office 場景與品質失敗隔離 | — | 已合併 `claude/office-demo-visualization` |
| [#37](https://github.com/Polalalabear/amidst/pull/37) | PR | C4a: per-run hybrid contact estimates (CP2 — do not merge) | — | 已合併 `claude/office-demo-visualization` |
| [#39](https://github.com/Polalalabear/amidst/pull/39) | PR | docs(agents): Office demo Q&A 2026-10-17 (C4a/C6 analysis) — do not merge without approval | — | 關閉未合併 |
| [#40](https://github.com/Polalalabear/amidst/pull/40) | PR | feat(c7): derive Demo source floor map and audit Office geometry | — | 已合併 `claude/office-demo-visualization` |
| [#43](https://github.com/Polalalabear/amidst/pull/43) | PR | feat(presets): independent Office person fixture and D18 endpoints | — | 已合併 `claude/office-demo-visualization` |
| [#44](https://github.com/Polalalabear/amidst/pull/44) | PR | feat(c4b): source-bound Office person hypothesis API and K5 evidence | — | 已合併 `claude/office-demo-visualization` |
| [#46](https://github.com/Polalalabear/amidst/pull/46) | PR | feat(c4a): implement v1.1 FOOT_RAY_PIXEL_BAND and confirm contract | — | 已合併 `claude/office-demo-visualization` |
| [#47](https://github.com/Polalalabear/amidst/pull/47) | PR | feat(c5): visibility retrieval API and real baseline/feedback evidence | — | 已合併 `claude/office-demo-visualization` |
| [#49](https://github.com/Polalalabear/amidst/issues/49) | Issue | C7 follow-up (low): camera-specific foot-hidden masks and C4a interface | — | 已完成 |
| [#50](https://github.com/Polalalabear/amidst/pull/50) | PR | fix(demo): person launcher readiness, D19 modes and v1.1 freeze | — | 已合併 `claude/office-demo-visualization` |
| [#51](https://github.com/Polalalabear/amidst/pull/51) | PR | fix(presets): integrity markers, stderr diagnostics and focused guards | — | 關閉未合併 |
| [#53](https://github.com/Polalalabear/amidst/pull/53) | PR | feat(c5): D21 strict visibility and reviewed K1/K5 frame deduplication | — | 已合併 `claude/office-demo-visualization` |
| [#54](https://github.com/Polalalabear/amidst/pull/54) | PR | docs(demo): rehearsal environment and B1 person panel scope | — | 關閉未合併 |
| [#55](https://github.com/Polalalabear/amidst/issues/55) | Issue | Office 人形場景加入第二人形干擾者（11/01 後） | — | 已完成 |
| [#63](https://github.com/Polalalabear/amidst/pull/63) | PR | chore(c4b): pre-sync K8a with unchanged real responses | — | 關閉未合併 |
| [#64](https://github.com/Polalalabear/amidst/pull/64) | PR | feat: add rehearsal readiness receipts | — | 關閉未合併 |
