# Q1–Q5 進度導覽

快照時間：2026-10-27（`gh pr list --state all` 與 `gh issue list --state all` 重算；mainline `9708fb6`、staging `434e579`，皆為撰寫時 `origin` 的 head）。資料來源：GitHub 上全部 PR 與 issue。
本文涵蓋 **176 個 PR 與 100 個 issue，共 276 項**（含本 PR #276；編號 #1–#276 連續，無缺號），每項只列在一個主分類下。
維護方式（D91-4）：本文的列由協調者或 mainline 的 docs PR 批次補，一般 PR／issue 不必各自更新，staging 的 PR 也不改本文。即時狀態仍以[任務板 #93](https://github.com/Polalalabear/amidst/issues/93)為準。

## 分類方式

- **主分類：**Q1–Q5 五大問題；無法歸到單一問題的列在「共用」與「流程」；D87 開的第二條線（複雜場景）列在「Line 2 複雜場景」；2026-10-20 轉向 Q1–Q5 之前的工作列在「暫停」與「歷史」。「也涉及」欄列出其他相關問題。
- **已完成：**PR 已合併，或 issue 已完成關閉。合併進 `codex/q1q5-staging` 的 PR 標「待審入主線」，還沒進 `mainline/q1q5`（staging → mainline 的整合是 [#267](https://github.com/Polalalabear/amidst/pull/267)，Draft）。關閉未合併的 PR 也列在這裡，備註寫明。
- **進行中：**開著的 PR，或程式已有 PR／已併入 staging 的 issue。
- **未完成：**尚未開始、blocked 或等授權的 issue。
- **待確認：**是否保留、合併或關閉還沒決定，例如舊線遺留的 PR、等使用者決定的提案、工作已完成但 issue 還開著。

## 總覽

| 分類 | 已完成 | 進行中 | 未完成 | 待確認 | 合計 |
| --- | ---: | ---: | ---: | ---: | ---: |
| [Q1 依條件找鏡頭](#q1-依條件找鏡頭) | 3 | 0 | 2 | 0 | 5 |
| [Q2 在畫面中找人](#q2-在畫面中找人) | 4 | 0 | 0 | 0 | 4 |
| [Q3 理解使用者語意](#q3-理解使用者語意) | 14 | 3 | 1 | 2 | 20 |
| [Q4 判斷畫面是否含目標](#q4-判斷畫面是否含目標) | 3 | 0 | 4 | 1 | 8 |
| [Q5 決定是否切鏡](#q5-決定是否切鏡) | 10 | 2 | 5 | 3 | 20 |
| [共用：契約、規則、參數與一致性檢查](#共用契約規則參數與一致性檢查) | 18 | 4 | 8 | 1 | 31 |
| [共用：r004 場景、資料、索引與儲存](#共用r004-場景資料索引與儲存) | 20 | 4 | 3 | 0 | 27 |
| [共用：工作台、HTTP 與 Demo](#共用工作台http-與-demo) | 28 | 1 | 3 | 5 | 37 |
| [Line 2 複雜場景](#line-2-複雜場景) | 0 | 16 | 0 | 0 | 16 |
| [流程：任務板、交接與文件](#流程任務板交接與文件) | 22 | 10 | 1 | 1 | 34 |
| [暫停：跨鏡頭盲區 3D 重建線](#暫停跨鏡頭盲區-3d-重建線) | 37 | 0 | 0 | 1 | 38 |
| [歷史：Office Demo 與 Phase 1／2](#歷史office-demo-與-phase-12) | 36 | 0 | 0 | 0 | 36 |
| **合計** | **195** | **40** | **27** | **14** | **276** |

## 最近改動（2026-10-23 起）

- 2026-10-27 本 PR（#276，#263 的 S3）：用 `gh` 重算全部 PR 與 issue。這次重算發現 #192–#274 之間先前缺 80 列（不只 D91-4 列的 #220、#221、#222、#224、#226、#230、#232 七列），一併補上；同時補入 issue #244–#251、#263 與 PR #242–#274，新增「Line 2 複雜場景」分類，已合併或關閉的項目（例如 #228、#252、#253、#257）移到已完成。
- 2026-10-27 決定 D88–D93（全文見 [#93](https://github.com/Polalalabear/amidst/issues/93)）：[D88](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6422147844) 本機清理，#240、#228 修衝突，#163、#82 先留著；[D89](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423194857) 核定 r004 情境卡 v1（A4-1＋B4-1，50 s／42 s，NO_SWITCH 讓位）；[D90](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423575212) Line 2 決策（長時間 LOST 由評估端分類、重疊接手、磁碟維持現狀[定案](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423763378)、第二版範圍暫定）；[D91](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434355675) 文件封存與現況更新（#263）；[D92](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434464633)（另見[補充](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434474506)）情境卡調整（A4-e、B4-d 不計分，計分事件 8 → 6 或 5）與 #260 決定；[D93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434812845) Line 2 重疊對評分（只評有出口條帶的對，不併入主比率）。
- 2026-10-27 Codex 派工與交件（#93）：第一批 [派工](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423281851) 與 [交件索引](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6424123274)；第二批 [派工](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434379604) 與 [交件索引](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434641943)；第三批 [派工](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434474862)。
- 2026-10-27 盤點關閉（[紀錄](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6422095384)）：7 個 PR（#77、#135、#209、#211、#212、#214、#216）與 15 個 issue（#95、#102–#107、#119–#122、#146、#147、#192、#196），分支一律保留。
- 2026-10-27 合併：[#231](https://github.com/Polalalabear/amidst/pull/231) baseline 整合進 staging（`680ca35`）；[#257](https://github.com/Polalalabear/amidst/pull/257) 進 staging（`c1d9cbd`）；[#241](https://github.com/Polalalabear/amidst/pull/241) 進 mainline（`2675c21`）；[#228](https://github.com/Polalalabear/amidst/pull/228)（`bd44ff2`）、[#252](https://github.com/Polalalabear/amidst/pull/252)（`9708fb6`）、[#253](https://github.com/Polalalabear/amidst/pull/253)（`0edd8a3`）進 mainline。#253 是 r004 A4／B4 情境卡 v1（`docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md`），D89 核定；#252 是兩條線工作分配（D87，[Q1Q5_TWO_LINE_PLAN_20261027.md](../agents/Q1Q5_TWO_LINE_PLAN_20261027.md)）。
- 2026-10-27 決定 D87（兩條線）：Line 2 傘狀 issue [#251](https://github.com/Polalalabear/amidst/issues/251)（L2-1..L2-7 為 #244–#250）。
- 2026-10-27 D91 文件整理（[#263](https://github.com/Polalalabear/amidst/issues/263)）：S1 [#264](https://github.com/Polalalabear/amidst/pull/264)（封存索引）、S2 [#265](https://github.com/Polalalabear/amidst/pull/265)（入口文件與 10-27 交接）、S3 本 PR、S4 [#270](https://github.com/Polalalabear/amidst/pull/270)（產品規格）皆為 Draft；2026-10-26 協調者交接 [COORDINATOR_HANDOFF_20261026.md](../agents/COORDINATOR_HANDOFF_20261026.md) 是目前 mainline 上最新的一份，10-27 交接在 #265。
- 2026-10-26 合併：[#229](https://github.com/Polalalabear/amidst/pull/229) 以 merge commit `f5168f6` 進 `mainline/q1q5`。[#237](https://github.com/Polalalabear/amidst/pull/237)（契約 B，`83da40f`）、[#239](https://github.com/Polalalabear/amidst/pull/239)（Qwen 報告註記，`7b05211`）進 `codex/q1q5-staging`；#237 取代 #219（GitHub 經 `635a102` 自動標成 MERGED，分支保留）。
- 2026-10-26 新 Draft PR [#240](https://github.com/Polalalabear/amidst/pull/240)：yyin Q1／Q3 包設計。
- 2026-10-26 決定：D83（P1 回交表人工閱讀）、D84（目錄凍結與 G4 脫鉤）、D85（停止後輪詢回 `PARTIAL`＋`USER_STOPPED`），見 [#93](https://github.com/Polalalabear/amidst/issues/93)。
- 2026-10-25 新 Draft PR [#229](https://github.com/Polalalabear/amidst/pull/229)：Q5 逐事件決策窗（D79 核定版），文件 `docs/evaluation/Q5_DECISION_WINDOW_D79.md`。
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

### 已完成（3）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#164](https://github.com/Polalalabear/amidst/pull/164) | PR | Q1 evaluator for human expected cores and pinned frozen schemas (code only) | — | 已併入 staging，待審入主線 |
| [#157](https://github.com/Polalalabear/amidst/pull/157) | PR | Q1 index search and scoped pagination（依 #144 提案；blocked #156） | — | 已併入 staging（`15c0f79`），待審入主線 |
| [#224](https://github.com/Polalalabear/amidst/pull/224) | PR | CX-2／#164：隔離合成分母，補 Q1 請求與分頁檢查 | — | 已併入 staging（`08d4793`），待審入主線 |

### 未完成（2）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#109](https://github.com/Polalalabear/amidst/issues/109) | Issue | QT-16：Q1 依條件找相機（查詢模組＋類別別名表） | — | blocked：Q1 搜尋 #157 已併入 staging；等 kit 修正 #156 |
| [#138](https://github.com/Polalalabear/amidst/issues/138) | Issue | QT-37：組員 Q1 條件查詢測試集與評分器（SYNTHETIC） | — | 組員 Q1 測試集未交；評估器已併入 staging（#164） |

**其他分類中也涉及 Q1 的項目：**

- 已完成：[#86](https://github.com/Polalalabear/amidst/pull/86)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#100](https://github.com/Polalalabear/amidst/issues/100)、[#101](https://github.com/Polalalabear/amidst/issues/101)、[#102](https://github.com/Polalalabear/amidst/issues/102)、[#103](https://github.com/Polalalabear/amidst/issues/103)、[#119](https://github.com/Polalalabear/amidst/issues/119)、[#120](https://github.com/Polalalabear/amidst/issues/120)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#126](https://github.com/Polalalabear/amidst/pull/126)、[#134](https://github.com/Polalalabear/amidst/pull/134)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#136](https://github.com/Polalalabear/amidst/pull/136)、[#139](https://github.com/Polalalabear/amidst/pull/139)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#146](https://github.com/Polalalabear/amidst/issues/146)、[#147](https://github.com/Polalalabear/amidst/issues/147)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#149](https://github.com/Polalalabear/amidst/pull/149)、[#151](https://github.com/Polalalabear/amidst/pull/151)、[#152](https://github.com/Polalalabear/amidst/pull/152)、[#155](https://github.com/Polalalabear/amidst/pull/155)、[#161](https://github.com/Polalalabear/amidst/pull/161)、[#167](https://github.com/Polalalabear/amidst/pull/167)、[#173](https://github.com/Polalalabear/amidst/pull/173)、[#175](https://github.com/Polalalabear/amidst/pull/175)、[#176](https://github.com/Polalalabear/amidst/pull/176)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#196](https://github.com/Polalalabear/amidst/issues/196)、[#197](https://github.com/Polalalabear/amidst/pull/197)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#205](https://github.com/Polalalabear/amidst/pull/205)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#221](https://github.com/Polalalabear/amidst/pull/221)、[#226](https://github.com/Polalalabear/amidst/pull/226)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#236](https://github.com/Polalalabear/amidst/pull/236)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#257](https://github.com/Polalalabear/amidst/pull/257)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#240](https://github.com/Polalalabear/amidst/pull/240)、[#243](https://github.com/Polalalabear/amidst/pull/243)、[#260](https://github.com/Polalalabear/amidst/pull/260)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#269](https://github.com/Polalalabear/amidst/pull/269)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#112](https://github.com/Polalalabear/amidst/issues/112)、[#113](https://github.com/Polalalabear/amidst/issues/113)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#118](https://github.com/Polalalabear/amidst/issues/118)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#133](https://github.com/Polalalabear/amidst/issues/133)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#156](https://github.com/Polalalabear/amidst/issues/156)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#194](https://github.com/Polalalabear/amidst/issues/194)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#204](https://github.com/Polalalabear/amidst/issues/204)、[#206](https://github.com/Polalalabear/amidst/issues/206)

## Q2 在畫面中找人

### 已完成（4）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#71](https://github.com/Polalalabear/amidst/pull/71) | PR | feat(workbench): player-grid pure module for 1/2/4/8 synced tiles | — | 已合併主線 |
| [#141](https://github.com/Polalalabear/amidst/pull/141) | PR | Q1–Q5 #107: 同鏡頭 selected-seed IoU 連接器與缺格邊界。 | — | 已合進主線（第 1 批，2026-10-25） |
| [#107](https://github.com/Polalalabear/amidst/issues/107) | Issue | QT-14：同鏡頭最小 IoU 連接器與暫失觸發 | — | 已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：同鏡頭 IoU 連接器已併入 staging（#141），待審入主線 |
| [#262](https://github.com/Polalalabear/amidst/pull/262) | PR | docs(p1): frame-by-frame diagnosis of 28 reported detection/link gaps | Q4、Q5 | 已併入 staging（`434e579`），待審入主線 |

**其他分類中也涉及 Q2 的項目：**

- 已完成：[#75](https://github.com/Polalalabear/amidst/pull/75)、[#80](https://github.com/Polalalabear/amidst/pull/80)、[#86](https://github.com/Polalalabear/amidst/pull/86)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#100](https://github.com/Polalalabear/amidst/issues/100)、[#101](https://github.com/Polalalabear/amidst/issues/101)、[#102](https://github.com/Polalalabear/amidst/issues/102)、[#104](https://github.com/Polalalabear/amidst/issues/104)、[#119](https://github.com/Polalalabear/amidst/issues/119)、[#121](https://github.com/Polalalabear/amidst/issues/121)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#132](https://github.com/Polalalabear/amidst/pull/132)、[#134](https://github.com/Polalalabear/amidst/pull/134)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#136](https://github.com/Polalalabear/amidst/pull/136)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#150](https://github.com/Polalalabear/amidst/pull/150)、[#152](https://github.com/Polalalabear/amidst/pull/152)、[#155](https://github.com/Polalalabear/amidst/pull/155)、[#166](https://github.com/Polalalabear/amidst/pull/166)、[#169](https://github.com/Polalalabear/amidst/pull/169)、[#173](https://github.com/Polalalabear/amidst/pull/173)、[#175](https://github.com/Polalalabear/amidst/pull/175)、[#177](https://github.com/Polalalabear/amidst/pull/177)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#185](https://github.com/Polalalabear/amidst/pull/185)、[#187](https://github.com/Polalalabear/amidst/pull/187)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#203](https://github.com/Polalalabear/amidst/pull/203)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#209](https://github.com/Polalalabear/amidst/pull/209)、[#211](https://github.com/Polalalabear/amidst/pull/211)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#216](https://github.com/Polalalabear/amidst/pull/216)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#227](https://github.com/Polalalabear/amidst/pull/227)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#235](https://github.com/Polalalabear/amidst/pull/235)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#238](https://github.com/Polalalabear/amidst/pull/238)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#257](https://github.com/Polalalabear/amidst/pull/257)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#184](https://github.com/Polalalabear/amidst/issues/184)、[#243](https://github.com/Polalalabear/amidst/pull/243)、[#247](https://github.com/Polalalabear/amidst/issues/247)、[#260](https://github.com/Polalalabear/amidst/pull/260)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#269](https://github.com/Polalalabear/amidst/pull/269)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#273](https://github.com/Polalalabear/amidst/pull/273)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#110](https://github.com/Polalalabear/amidst/issues/110)、[#112](https://github.com/Polalalabear/amidst/issues/112)、[#113](https://github.com/Polalalabear/amidst/issues/113)、[#114](https://github.com/Polalalabear/amidst/issues/114)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#116](https://github.com/Polalalabear/amidst/issues/116)、[#117](https://github.com/Polalalabear/amidst/issues/117)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#133](https://github.com/Polalalabear/amidst/issues/133)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#178](https://github.com/Polalalabear/amidst/issues/178)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#158](https://github.com/Polalalabear/amidst/pull/158)、[#163](https://github.com/Polalalabear/amidst/pull/163)、[#194](https://github.com/Polalalabear/amidst/issues/194)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#202](https://github.com/Polalalabear/amidst/issues/202)、[#206](https://github.com/Polalalabear/amidst/issues/206)、[#208](https://github.com/Polalalabear/amidst/issues/208)、[#210](https://github.com/Polalalabear/amidst/issues/210)、[#218](https://github.com/Polalalabear/amidst/issues/218)

## Q3 理解使用者語意

### 已完成（14）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#140](https://github.com/Polalalabear/amidst/pull/140) | PR | feat(q1q5): audited loopback Ollama provider | Q5 | 已合進主線（第 1 批，2026-10-25） |
| [#149](https://github.com/Polalalabear/amidst/pull/149) | PR | docs(evaluation): #146 Q1 Q3 question authoring boundaries | Q1 | 已併入 staging，待審入主線 |
| [#152](https://github.com/Polalalabear/amidst/pull/152) | PR | feat(q1q5): #106 literal Q3 parsing and audited deterministic fallback | Q1、Q2 | 已併入 staging，待審入主線 |
| [#165](https://github.com/Polalalabear/amidst/pull/165) | PR | Q3 human-annotation evaluator with exact pinned source clocks (code only) | — | 已併入 staging，待審入主線 |
| [#105](https://github.com/Polalalabear/amidst/issues/105) | Issue | QT-12：Ollama 薄 provider（Q3／Q5 共用） | Q5 | 已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：Ollama provider 已併入 staging（#140），待審入主線 |
| [#106](https://github.com/Polalalabear/amidst/issues/106) | Issue | QT-13：Q3 解析：規則解析器、LLM 解析與兜底 | — | 已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：規則解析與兜底已併入 staging（#152）；LLM 解析等 Qwen3（#174、#186） |
| [#146](https://github.com/Polalalabear/amidst/issues/146) | Issue | QT-41：組員出題依據文件（格式、可填資料、找得到／找不到） | Q1 | 已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：出題指南已併入 staging（#149） |
| [#174](https://github.com/Polalalabear/amidst/pull/174) | PR | feat(q1q5): pinned Qwen3 runtime, grounded schemas and contention measurements | Q5 | 已併入 staging（`bc26d95`），待審入主線 |
| [#199](https://github.com/Polalalabear/amidst/pull/199) | PR | docs(q3): 固定最小八題候選與獨立審核模板 | — | 已併入 staging（`57d8f35`），待審入主線 |
| [#205](https://github.com/Polalalabear/amidst/pull/205) | PR | Wire reviewed baseline gates and independent Q3 review import | Q1、Q4 | 已併入 staging（`0efda15`），待審入主線 |
| [#221](https://github.com/Polalalabear/amidst/pull/221) | PR | CX-2／#149：補齊組員 CSV 填法與出題邊界 | Q1 | 已併入 staging（`e52ace3`），待審入主線 |
| [#230](https://github.com/Polalalabear/amidst/pull/230) | PR | CX-6：Qwen3 不截斷診斷，完整延遲與 token 收據 | Q5 | 已併入 staging（`7adf60b`），待審入主線 |
| [#236](https://github.com/Polalalabear/amidst/pull/236) | PR | fix(evaluation): enforce D80 return mappings and external query bindings | Q1 | 已併入 staging（`08d7202`），待審入主線 |
| [#239](https://github.com/Polalalabear/amidst/pull/239) | PR | docs：澄清 Q5 離群值與小樣本 p95 | Q5 | 已併入 staging（`7b05211`），待審入主線 |

### 進行中（3）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#186](https://github.com/Polalalabear/amidst/issues/186) | Issue | 本機 Qwen3：schema／工具流程未通過，原呼叫預算仍逾時 | Q5 | Qwen3 schema／工具流程未通過，原呼叫預算逾時；Qwen3 執行環境 #174 已併入 staging |
| [#240](https://github.com/Polalalabear/amidst/pull/240) | PR（Draft） | docs(q1q3): yyin Q1／Q3 出題包設計稿（D80） | Q1 | Draft；yyin Q1／Q3 出題包設計稿（D80）；D88 決定修衝突後再審 |
| [#269](https://github.com/Polalalabear/amidst/pull/269) | PR（Draft） | docs(evaluation): D86-2 selected-run time defaults in question guide | Q1、Q2 | Draft；D86-2 缺時間預設整段 run 的出題指南（base staging） |

### 未完成（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#89](https://github.com/Polalalabear/amidst/issues/89) | Issue | Q3：語意解析測試集與評分器（組員） | — | 組員 Q3 測試集未交；評分器已併入 staging（#165） |

### 待確認（2）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#198](https://github.com/Polalalabear/amidst/issues/198) | Issue | Baseline 前置：最小 Q3 八題候選與獨立審核回收 | — | 對應 PR #199 已併入 staging；issue 仍開著，是否關閉待確認 |
| [#204](https://github.com/Polalalabear/amidst/issues/204) | Issue | 完整 baseline 條線 B：核定輸入與 Q3 人審回收 | Q1、Q4 | 對應 PR #205 已併入 staging；issue 仍開著，是否關閉待確認 |

**其他分類中也涉及 Q3 的項目：**

- 已完成：[#86](https://github.com/Polalalabear/amidst/pull/86)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#101](https://github.com/Polalalabear/amidst/issues/101)、[#119](https://github.com/Polalalabear/amidst/issues/119)、[#120](https://github.com/Polalalabear/amidst/issues/120)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#126](https://github.com/Polalalabear/amidst/pull/126)、[#134](https://github.com/Polalalabear/amidst/pull/134)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#147](https://github.com/Polalalabear/amidst/issues/147)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#151](https://github.com/Polalalabear/amidst/pull/151)、[#173](https://github.com/Polalalabear/amidst/pull/173)、[#176](https://github.com/Polalalabear/amidst/pull/176)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#203](https://github.com/Polalalabear/amidst/pull/203)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#214](https://github.com/Polalalabear/amidst/pull/214)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#226](https://github.com/Polalalabear/amidst/pull/226)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#257](https://github.com/Polalalabear/amidst/pull/257)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#260](https://github.com/Polalalabear/amidst/pull/260)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#112](https://github.com/Polalalabear/amidst/issues/112)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#133](https://github.com/Polalalabear/amidst/issues/133)、[#145](https://github.com/Polalalabear/amidst/issues/145)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#194](https://github.com/Polalalabear/amidst/issues/194)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#202](https://github.com/Polalalabear/amidst/issues/202)、[#206](https://github.com/Polalalabear/amidst/issues/206)

## Q4 判斷畫面是否含目標

### 已完成（3）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#159](https://github.com/Polalalabear/amidst/pull/159) | PR | Q4 frozen claim sampling and human TF evaluator (code only) | — | 已併入 staging，待審入主線 |
| [#167](https://github.com/Polalalabear/amidst/pull/167) | PR | Preserve finite raw detector boxes beyond image boundaries | Q1 | 已併入 staging，待審入主線 |
| [#154](https://github.com/Polalalabear/amidst/pull/154) | PR | feat(q1q5): #108 candidate evidence (blocked on no-color kit alignment) | — | 已併入 staging（`cfcf0e0`），待審入主線 |

### 未完成（4）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#108](https://github.com/Polalalabear/amidst/issues/108) | Issue | QT-15：Q4 候選畫面證據聚合 | — | blocked：Q4 證據 #154 已併入 staging；等無顏色 kit 對齊（#153） |
| [#114](https://github.com/Polalalabear/amidst/issues/114) | Issue | QT-21：HSV 顏色參數提案（r004 preview，Q-19） | Q2 | blocked：HSV 參數提案 #158 待 G6 |
| [#123](https://github.com/Polalalabear/amidst/issues/123) | Issue | QT-30：Q4 標註與評估（RT-DETR＋HSV） | — | blocked：Q4 標註與評估；評估器已併入 staging（#159） |
| [#128](https://github.com/Polalalabear/amidst/issues/128) | Issue | QT-32：組員 Q4 標註與偵測評估（人工標註） | — | 組員 Q4 人工標註未交 |

### 待確認（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#158](https://github.com/Polalalabear/amidst/pull/158) | PR（Draft） | HSV RGB proposal and measured ambiguity (G6 pending) | Q2 | Draft，HSV 參數待 G6 決定 |

**其他分類中也涉及 Q4 的項目：**

- 已完成：[#86](https://github.com/Polalalabear/amidst/pull/86)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#103](https://github.com/Polalalabear/amidst/issues/103)、[#121](https://github.com/Polalalabear/amidst/issues/121)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#132](https://github.com/Polalalabear/amidst/pull/132)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#136](https://github.com/Polalalabear/amidst/pull/136)、[#139](https://github.com/Polalalabear/amidst/pull/139)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#147](https://github.com/Polalalabear/amidst/issues/147)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#151](https://github.com/Polalalabear/amidst/pull/151)、[#155](https://github.com/Polalalabear/amidst/pull/155)、[#161](https://github.com/Polalalabear/amidst/pull/161)、[#177](https://github.com/Polalalabear/amidst/pull/177)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#196](https://github.com/Polalalabear/amidst/issues/196)、[#197](https://github.com/Polalalabear/amidst/pull/197)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#203](https://github.com/Polalalabear/amidst/pull/203)、[#205](https://github.com/Polalalabear/amidst/pull/205)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#226](https://github.com/Polalalabear/amidst/pull/226)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#262](https://github.com/Polalalabear/amidst/pull/262)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#113](https://github.com/Polalalabear/amidst/issues/113)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#118](https://github.com/Polalalabear/amidst/issues/118)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#153](https://github.com/Polalalabear/amidst/issues/153)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#194](https://github.com/Polalalabear/amidst/issues/194)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#202](https://github.com/Polalalabear/amidst/issues/202)、[#204](https://github.com/Polalalabear/amidst/issues/204)、[#206](https://github.com/Polalalabear/amidst/issues/206)

## Q5 決定是否切鏡

### 已完成（10）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#150](https://github.com/Polalalabear/amidst/pull/150) | PR | feat(q1q5): #104 pinned static graph validation and D28 candidates | Q2 | 已併入 staging，待審入主線 |
| [#160](https://github.com/Polalalabear/amidst/pull/160) | PR | Q5 evaluator verifies frozen outputs before reading evaluation script (code only) | — | 已併入 staging，待審入主線 |
| [#166](https://github.com/Polalalabear/amidst/pull/166) | PR | Restrict candidate run cameras before D28 ranking and top-k | Q2 | 已併入 staging，待審入主線 |
| [#104](https://github.com/Polalalabear/amidst/issues/104) | Issue | QT-11：兩層圖 schema／loader 與 D28 候選排序 | Q2 | 已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：靜態圖驗證與 D28 候選已併入 staging（#150、#166），待審入主線 |
| [#169](https://github.com/Polalalabear/amidst/pull/169) | PR | Q5 RULE_ONLY controller（依 #144 提案；blocked #145/#153） | Q2 | 已併入 staging（`efad835`），待審入主線 |
| [#172](https://github.com/Polalalabear/amidst/pull/172) | PR | feat(q5): sequential Agent, versioned guidance profiles and exact replay | — | 已併入 staging（`c0a1ce3`），待審入主線 |
| [#185](https://github.com/Polalalabear/amidst/pull/185) | PR | feat(q1q5): event-mode comparison and reproducible baseline telemetry | Q2 | 已併入 staging（`d8e6935`），待審入主線 |
| [#229](https://github.com/Polalalabear/amidst/pull/229) | PR | docs(q5): Q5 逐事件決策窗（D79 核定版） | — | 已合併主線（`f5168f6`，2026-10-26）；D79 核定的決策窗文件 |
| [#203](https://github.com/Polalalabear/amidst/pull/203) | PR | Connect same RGB detector index to Qwen/RULE baseline | Q2、Q3、Q4 | 已併入 staging（`10e94d6`），待審入主線 |
| [#222](https://github.com/Polalalabear/amidst/pull/222) | PR | CX-2／#160：Q5 拒絕空覆蓋得分，分列決策來源 | — | 已併入 staging（`0043097`），待審入主線 |

### 進行中（2）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#184](https://github.com/Polalalabear/amidst/issues/184) | Issue | Q5 雙模式工程比較：後端 FOUND／LOST 與 Agent 候選決策 | Q2 | Q5 雙模式比較，載體 #185 已併入 staging |
| [#189](https://github.com/Polalalabear/amidst/pull/189) | PR（Draft） | Q5：As-Is Statechart 與獨立 Journal Invariants 驗證 | — | Draft（10-23 新增），Q5 As-Is 狀態圖與 journal 不變量檢查 |

### 未完成（5）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#110](https://github.com/Polalalabear/amidst/issues/110) | Issue | QT-17：Q5 Controller：狀態機與 RULE_ONLY 決定性切鏡 | Q2 | blocked：RULE_ONLY 控制器 #169 已併入 staging；等 #145、#153 |
| [#111](https://github.com/Polalalabear/amidst/issues/111) | Issue | QT-18：Q5 AGENT_SEQUENTIAL：typed tools 與有界輪詢 | — | Agent #172 已併入 staging；空候選契約缺口 #183 未解 |
| [#116](https://github.com/Polalalabear/amidst/issues/116) | Issue | QT-23：r004 兩層圖資料與出口 ROI（靜態） | Q2 | blocked：兩層圖與出口 ROI #163（Draft）待 G4 |
| [#117](https://github.com/Polalalabear/amidst/issues/117) | Issue | QT-24：r004 靜態圖獨立檢查（K7 類型） | Q2 | 收據已出；圖 v3（#227、#235）已併入 staging，G4 未核 |
| [#129](https://github.com/Polalalabear/amidst/issues/129) | Issue | QT-33：組員 Q5 切鏡評估器 | — | 組員 Q5 情境未交；評估器已併入 staging（#160） |

### 待確認（3）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#163](https://github.com/Polalalabear/amidst/pull/163) | PR（Draft） | r004 static graph and eight exit ROI proposals (G4 pending) | Q2 | Draft，待 G4；圖 v3（#227、#235）已併入 staging；D88 決定先留著，是否關閉待確認 |
| [#202](https://github.com/Polalalabear/amidst/issues/202) | Issue | 完整 baseline 條線 A：同源 RGB→真 RT-DETR→Qwen／RULE／replay | Q2、Q3、Q4 | 對應 PR #203 已併入 staging；issue 仍開著，是否關閉待確認 |
| [#218](https://github.com/Polalalabear/amidst/issues/218) | Issue | [Q2／Q5] 同鏡頭暫失後接不回：漏檢即暫失、回原鏡頭只比對凍結框（#216 審查發現） | Q2 | 同鏡頭暫失後接不回；D90-1：暫失 ≥ 1.8 s 歸 Line 2；P1 逐格診斷 #262 已併入 staging；issue 仍開著，是否關閉待確認 |

**其他分類中也涉及 Q5 的項目：**

- 已完成：[#86](https://github.com/Polalalabear/amidst/pull/86)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#95](https://github.com/Polalalabear/amidst/issues/95)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#105](https://github.com/Polalalabear/amidst/issues/105)、[#121](https://github.com/Polalalabear/amidst/issues/121)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#125](https://github.com/Polalalabear/amidst/pull/125)、[#126](https://github.com/Polalalabear/amidst/pull/126)、[#132](https://github.com/Polalalabear/amidst/pull/132)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#140](https://github.com/Polalalabear/amidst/pull/140)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#161](https://github.com/Polalalabear/amidst/pull/161)、[#168](https://github.com/Polalalabear/amidst/pull/168)、[#171](https://github.com/Polalalabear/amidst/pull/171)、[#174](https://github.com/Polalalabear/amidst/pull/174)、[#177](https://github.com/Polalalabear/amidst/pull/177)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#187](https://github.com/Polalalabear/amidst/pull/187)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#209](https://github.com/Polalalabear/amidst/pull/209)、[#211](https://github.com/Polalalabear/amidst/pull/211)、[#214](https://github.com/Polalalabear/amidst/pull/214)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#216](https://github.com/Polalalabear/amidst/pull/216)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#227](https://github.com/Polalalabear/amidst/pull/227)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#230](https://github.com/Polalalabear/amidst/pull/230)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#235](https://github.com/Polalalabear/amidst/pull/235)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#238](https://github.com/Polalalabear/amidst/pull/238)、[#239](https://github.com/Polalalabear/amidst/pull/239)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#253](https://github.com/Polalalabear/amidst/pull/253)、[#259](https://github.com/Polalalabear/amidst/pull/259)、[#262](https://github.com/Polalalabear/amidst/pull/262)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#186](https://github.com/Polalalabear/amidst/issues/186)、[#244](https://github.com/Polalalabear/amidst/issues/244)、[#245](https://github.com/Polalalabear/amidst/issues/245)、[#246](https://github.com/Polalalabear/amidst/issues/246)、[#248](https://github.com/Polalalabear/amidst/issues/248)、[#249](https://github.com/Polalalabear/amidst/issues/249)、[#251](https://github.com/Polalalabear/amidst/issues/251)、[#254](https://github.com/Polalalabear/amidst/pull/254)、[#255](https://github.com/Polalalabear/amidst/pull/255)、[#256](https://github.com/Polalalabear/amidst/pull/256)、[#258](https://github.com/Polalalabear/amidst/pull/258)、[#261](https://github.com/Polalalabear/amidst/pull/261)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#266](https://github.com/Polalalabear/amidst/pull/266)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#271](https://github.com/Polalalabear/amidst/pull/271)、[#272](https://github.com/Polalalabear/amidst/pull/272)、[#274](https://github.com/Polalalabear/amidst/pull/274)、[#275](https://github.com/Polalalabear/amidst/pull/275)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#170](https://github.com/Polalalabear/amidst/issues/170)、[#178](https://github.com/Polalalabear/amidst/issues/178)、[#183](https://github.com/Polalalabear/amidst/issues/183)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#194](https://github.com/Polalalabear/amidst/issues/194)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#206](https://github.com/Polalalabear/amidst/issues/206)、[#208](https://github.com/Polalalabear/amidst/issues/208)、[#210](https://github.com/Polalalabear/amidst/issues/210)

## 共用：契約、規則、參數與一致性檢查

### 已完成（18）

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
| [#135](https://github.com/Polalalabear/amidst/pull/135) | PR | docs(contracts): Q1–Q5 契約釐清版（#127 回報，不改語意與數值） | Q1、Q2、Q3、Q4、Q5 | 關閉未合併（2026-10-26）；已由 #237 取代（`83da40f`，盤點留言） |
| [#95](https://github.com/Polalalabear/amidst/issues/95) | Issue | QT-02：DEVELOPMENT_RULES：Q1–Q5 Agent 有界例外條文（D64） | Q5 | 已完成關閉（2026-10-26）；條文已由 #125 合入主線 |
| [#219](https://github.com/Polalalabear/amidst/pull/219) | PR | 契約：R1–R8、D73 與 D78 已核定條文 | Q1、Q2、Q3、Q4、Q5 | GitHub 標為 MERGED（base staging，`635a102`）；#237 取代，分支保留 |
| [#220](https://github.com/Polalalabear/amidst/pull/220) | PR | CX-2／#142：fallback 預算明列為效能觀察值 | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`2edd32f`），待審入主線 |
| [#237](https://github.com/Polalalabear/amidst/pull/237) | PR | 契約 B：對齊 D78 audit、D82 stop 與 D80/D81 介面 | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`83da40f`），待審入主線 |

### 進行中（4）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#98](https://github.com/Polalalabear/amidst/issues/98) | Issue | QT-05：§11 參數組 v1 提案（HSV 除外） | Q1、Q2、Q3、Q5 | §11 參數組已部分綁定（#142，staging） |
| [#127](https://github.com/Polalalabear/amidst/pull/127) | PR（Draft） | feat(evaluation): Q1–Q5 contract conformance kit (draft) | Q1、Q2、Q3、Q4、Q5 | 一致性檢查包（Draft，head 為 rc4）；AC7 尚未通過（NOT_ACCEPTED），rc5 待 B1（#257 已併入 staging）後重跑 |
| [#144](https://github.com/Polalalabear/amidst/issues/144) | Issue | QT-39：契約 #135 補完（寫入 D69＋處理 Codex 跳過原因） | Q1、Q2、Q3、Q4、Q5 | §14 選項已併入 staging（#148、#161、#168、#171、#173、#179），待寫回 #135 |
| [#260](https://github.com/Polalalabear/amidst/pull/260) | PR（Draft） | docs(contract): U37 examples, link v2 note and D86/G4 interface proposals | Q1、Q2、Q3 | Draft；U37 範例、link v2 註記與 D86／G4 介面提案；D92 的 #260-A／C／B 待套用（base staging） |

### 未完成（8）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#99](https://github.com/Polalalabear/amidst/issues/99) | Issue | QT-06：Q1–Q5 合約符合性測試包 | Q1、Q2、Q3、Q4、Q5 | 標 blocked；一致性檢查包 #127 仍為 Draft（AC7 未過） |
| [#133](https://github.com/Polalalabear/amidst/issues/133) | Issue | Conformance kit: CLOCK_MAPPING_RULES rejects an explicit DST fold offset | Q1、Q2、Q3 | kit 問題：DST fold 偏移被拒，尚無修正 PR |
| [#145](https://github.com/Polalalabear/amidst/issues/145) | Issue | QT-40：#127 測試包對齊契約 #135 最終版並合入 | Q1、Q2、Q3、Q4、Q5 | blocked：kit 對齊契約最終版 |
| [#153](https://github.com/Polalalabear/amidst/issues/153) | Issue | #127/#145: no-color Q4 MATCH_STRONG with null verdict fails presence invariant | Q4 | kit 問題：無顏色 Q4 的 null verdict 被拒，阻擋 #154 |
| [#156](https://github.com/Polalalabear/amidst/issues/156) | Issue | #127 Q1_RESULT_ORDER：最後一頁錯將 results_total 視為當頁筆數 | Q1 | kit 問題：Q1 最後一頁筆數判錯，阻擋 #157 |
| [#170](https://github.com/Polalalabear/amidst/issues/170) | Issue | Q5 conformance：D69 link 誤分類、失敗 digest 與正常候選耗盡的 Agent flags | Q5 | kit 問題：Q5 Agent flags 與 link 分類 |
| [#178](https://github.com/Polalalabear/amidst/issues/178) | Issue | [#127] 空 decisions／links journal 被 DOCUMENT_LOADABLE 判成未知 schema | Q2、Q5 | kit 問題：空 journal 被判成未知 schema |
| [#183](https://github.com/Polalalabear/amidst/issues/183) | Issue | [契約缺口] 空候選證據無法合法 NEXT_CANDIDATE，阻斷 Agent top-k 輪詢 | Q5 | 契約缺口：空候選無法 NEXT_CANDIDATE，阻擋 Agent 輪詢 |

### 待確認（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#88](https://github.com/Polalalabear/amidst/issues/88) | Issue | QA：Q1–Q5 第一版計畫與契約 #86 核准 | Q1、Q2、Q3、Q4、Q5 | D65 已核准，#86、#92 已合併；待確認是否關閉 |

## 共用：r004 場景、資料、索引與儲存

### 已完成（20）

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
| [#102](https://github.com/Polalalabear/amidst/issues/102) | Issue | QT-09：store 介面（版本化 JSON＋每 run JSONL） | Q1、Q2 | 已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：store 已併入 staging（#136），待審入主線 |
| [#103](https://github.com/Polalalabear/amidst/issues/103) | Issue | QT-10：偵測索引產生器（RT-DETR＋上半身 HSV） | Q1、Q4 | 已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：偵測索引產生器與 HSV 證據已併入 staging（#139），待審入主線 |
| [#187](https://github.com/Polalalabear/amidst/pull/187) | PR | r004 v2: source-bound entry/exit zones and portal review packet | Q2、Q5 | 已併入 staging（`9402c91`），待審入主線 |
| [#196](https://github.com/Polalalabear/amidst/issues/196) | Issue | Baseline 前置：r004 產製設定與 pinned 索引入口 | Q1、Q4 | 已完成關閉（盤點留言） |
| [#197](https://github.com/Polalalabear/amidst/pull/197) | PR | feat(q1q5): r004 pinned 產製設定與索引入口 | Q1、Q4 | 已併入 staging（`de7046a`），待審入主線 |
| [#212](https://github.com/Polalalabear/amidst/pull/212) | PR | docs(r004): 更新 yyin 回收與 baseline 凍結前狀態，交 Claude 審查 | — | 關閉未合併（2026-10-27，盤點）；head 已含於 staging（經 #231 的 merge `680ca35`），分支保留 |
| [#227](https://github.com/Polalalabear/amidst/pull/227) | PR | CX-3：r004 圖 v3、26 ROI 與 56 有向對收據（G4 未核） | Q2、Q5 | 圖 v3、26 ROI、56 有向對收據；G4 未核；已併入 staging（`3cc0532`），待審入主線 |
| [#235](https://github.com/Polalalabear/amidst/pull/235) | PR | fix(r004): align W2 paths and add D81 corridor transitions | Q2、Q5 | 已併入 staging（`747bdfe`），待審入主線 |
| [#238](https://github.com/Polalalabear/amidst/pull/238) | PR | docs(r004): D89 50s/42s clocks, D84 catalog freeze and run registrations | Q2、Q5 | D89 時鐘（A4 50 s／B4 42 s）、D84 目錄凍結與 run 註冊；已併入 staging（`001cbcf`），待審入主線 |
| [#253](https://github.com/Polalalabear/amidst/pull/253) | PR | docs(evaluation): r004 A4／B4 情境卡 v1（D87） | Q5 | 已合併主線（`0edd8a3`，2026-10-27） |
| [#259](https://github.com/Polalalabear/amidst/pull/259) | PR | fix(review): finish #235 #236 #234 notes after #231 merge | Q5 | 已併入 staging（`7a33d6d`），待審入主線 |

### 進行中（4）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#97](https://github.com/Polalalabear/amidst/issues/97) | Issue | QT-04：r004 修改表提案定稿（文件） | Q1、Q2、Q4、Q5 | r004 修改表提案 #132 已併入 staging；r004 v2 審查包 #187 已併入 staging |
| [#254](https://github.com/Polalalabear/amidst/pull/254) | PR（Draft） | feat(evaluation): r004 A4-1/B4-1 劇本計畫 → q5-evaluation-script.v1 adapter | Q5 | Draft；r004 A4-1／B4-1 劇本計畫 → `q5-evaluation-script.v1` adapter（base staging） |
| [#256](https://github.com/Polalalabear/amidst/pull/256) | PR（Draft） | docs(r004): D89 A4/B4 static feasibility and timing conflicts | Q5 | Draft；D89 A4／B4 靜態可行性與時間衝突；D92 採選項 1（base staging） |
| [#275](https://github.com/Polalalabear/amidst/pull/275) | PR（Draft） | docs(r004): unfrozen B4-1 producer script draft with B4-d non-scoring | Q5 | Draft；未凍結的 B4-1 劇本草稿，B4-d 不計分（D92；base staging） |

### 未完成（3）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#113](https://github.com/Polalalabear/amidst/issues/113) | Issue | QT-20：r004 建檔、靜態校正匯出與廣角小批 preview | Q1、Q2、Q4 | 標 blocked（內文寫 needs-auth）；r004 靜態匯出 #155、廣角鏡頭 #162 已併入 staging |
| [#115](https://github.com/Polalalabear/amidst/issues/115) | Issue | QT-22：A4／B4 事件 run 產製與 safe bundle | Q1、Q2、Q4、Q5 | 標 blocked（內文寫 needs-auth）：A4-1／B4-1 事件 run 待授權；D89 核定 50／42 s，時鐘 #238（已併入 staging）、可行性檢查 #256（Draft） |
| [#118](https://github.com/Polalalabear/amidst/issues/118) | Issue | QT-25：r004 正式偵測索引產製 | Q1、Q4 | blocked：r004 正式偵測索引，等 #115 |

## 共用：工作台、HTTP 與 Demo

### 已完成（28）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#72](https://github.com/Polalalabear/amidst/pull/72) | PR | docs(agents): 工作台 v2 設計（功能保留矩陣、資訊架構、視覺規範、實作計畫） | — | 關閉未合併 |
| [#74](https://github.com/Polalalabear/amidst/pull/74) | PR | feat(workbench-v2): V2-1 外框、token、store、時鐘 | — | 已合併主線 |
| [#79](https://github.com/Polalalabear/amidst/pull/79) | PR | feat(workbench-v2): V2-2 api、不確定度驗證與 SYNTHETIC fixture | — | 已合併主線 |
| [#100](https://github.com/Polalalabear/amidst/issues/100) | Issue | QT-07：workbench-v2 底座合入 mainline（U-1：#74、#79、#71） | Q1、Q2 | 已完成 |
| [#181](https://github.com/Polalalabear/amidst/pull/181) | PR | Demo 腳本草稿與可重現工程啟動指令（依 #144 提案） | Q1、Q2、Q3、Q4、Q5 | 已併入 staging，待審入主線 |
| [#182](https://github.com/Polalalabear/amidst/pull/182) | PR | Demo 草稿：固定最終 replay provenance 工程包（依 #144 提案） | Q1、Q2、Q3、Q4、Q5 | 已併入 staging，待審入主線 |
| [#90](https://github.com/Polalalabear/amidst/pull/90) | PR | docs(agents): workbench-v2 Q1–Q5 畫面設計與審核模式（draft）— do not merge | Q1、Q2、Q3、Q4、Q5 | 已合併主線（merge commit `19fd4f5`，2026-10-25 10:00Z）；原標示 do-not-merge，合併依據待 #93 核對 |
| [#175](https://github.com/Polalalabear/amidst/pull/175) | PR | workbench T1：Q 資料層與外框（依 #144 提案） | Q1、Q2 | 已併入 staging（`a0a4398`），待審入主線 |
| [#176](https://github.com/Polalalabear/amidst/pull/176) | PR | workbench T2：Q3 直接執行與 Q1 三區結果牆（依 #144 提案） | Q1、Q3 | 已併入 staging（`601e69b`），待審入主線 |
| [#177](https://github.com/Polalalabear/amidst/pull/177) | PR | workbench T3：多鏡頭、事件硬切與審核紀錄（依 #144 提案） | Q2、Q4、Q5 | 已併入 staging（`4893f49`），待審入主線 |
| [#180](https://github.com/Polalalabear/amidst/pull/180) | PR | workbench T4：唯讀審核、凍結 pins 與匯出隔離（依 #144 提案） | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`15e27d2`），待審入主線 |
| [#119](https://github.com/Polalalabear/amidst/issues/119) | Issue | QT-26：workbench-v2 T1：Q 資料層與外框改裝 | Q1、Q2、Q3 | 已完成關閉（2026-10-26）；對應 PR #175 已併入 staging |
| [#120](https://github.com/Polalalabear/amidst/issues/120) | Issue | QT-27：workbench-v2 T2：Q3 查詢列與 Q1 結果牆 | Q1、Q3 | 已完成關閉（2026-10-26）；對應 PR #176 已併入 staging |
| [#121](https://github.com/Polalalabear/amidst/issues/121) | Issue | QT-28：workbench-v2 T3：Q2 主畫面、時間軸、Q4 證據、Q5 逐步紀錄 | Q2、Q4、Q5 | 已完成關閉（2026-10-26）；對應 PR #177 已併入 staging |
| [#122](https://github.com/Polalalabear/amidst/issues/122) | Issue | QT-29：workbench-v2 T4：審核模式 | Q1、Q2、Q3、Q4、Q5 | 已完成關閉（2026-10-26）；對應 PR #180 已併入 staging |
| [#192](https://github.com/Polalalabear/amidst/issues/192) | Issue | Demo v1：最小 baseline 測試規格與工程配置（Qwen3＋RT-DETR） | Q1、Q2、Q3、Q4、Q5 | baseline 最小規格；已完成關閉（盤點留言） |
| [#193](https://github.com/Polalalabear/amidst/pull/193) | PR | docs(q1q5): 最小 baseline v1 協定與工程配置 | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`89bd04c`），待審入主線 |
| [#195](https://github.com/Polalalabear/amidst/pull/195) | PR | feat(q1q5): baseline 工程入口、完整錄製／replay 與產製預檢 | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`816650c`），待審入主線 |
| [#201](https://github.com/Polalalabear/amidst/pull/201) | PR | feat(q1q5): 可重建 baseline 前置、publication 修正與一次驗收 | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`9821249`），待審入主線 |
| [#207](https://github.com/Polalalabear/amidst/pull/207) | PR | Deliver reproducible linked baseline and Workbench acceptance | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`b8a1cd0`），待審入主線 |
| [#209](https://github.com/Polalalabear/amidst/pull/209) | PR | 修正黑畫面、6秒工程事件與播放連續性量測 | Q2、Q5 | 關閉未合併（2026-10-27，盤點）；head 已含於 staging（經 #231 的 merge `680ca35`），分支保留 |
| [#211](https://github.com/Polalalabear/amidst/pull/211) | PR | 真動態8秒baseline：逐格RGB、有界播放與完整工程驗收 | Q2、Q5 | 關閉未合併（2026-10-27，盤點）；head 已含於 staging（經 #231 的 merge `680ca35`），分支保留 |
| [#216](https://github.com/Polalalabear/amidst/pull/216) | PR | A→B 約3–5秒盲區審查：逐格數據、俯視圖與重現入口 | Q2、Q5 | 關閉未合併（2026-10-27，盤點）；head 已含於 staging（經 #231 的 merge `680ca35`），分支保留 |
| [#231](https://github.com/Polalalabear/amidst/pull/231) | PR | baseline整合：完成11項重審修正與契約B接線 | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`680ca35`），待審入主線 |
| [#233](https://github.com/Polalalabear/amidst/pull/233) | PR | CX-5：P1 一行啟動、真實選取與8秒播放實測（AC7仍待rc2） | Q1、Q2、Q3、Q4、Q5 | CX-5：P1 一行啟動與 8 秒播放；AC7 另依 #127；已併入 staging（`66762ab`），待審入主線 |
| [#234](https://github.com/Polalalabear/amidst/pull/234) | PR | CX-10：可重現 LOCAL P1 測試包、相對路徑與瀏覽器回交表 | Q1、Q2、Q3、Q4、Q5 | CX-10：LOCAL P1 可攜測試包 v4；已併入 staging（`9c052fb`），待審入主線 |
| [#242](https://github.com/Polalalabear/amidst/pull/242) | PR | fix(recordings): rc4 scope migration and public locator cleanup; rerun after B1 merge | Q1、Q2、Q3、Q4、Q5 | rc4 重錄與公開路徑清理；已併入 staging（`d6a9e21`）；fresh recordings=0，AC7 仍 NOT_ACCEPTED（Codex 回報） |
| [#257](https://github.com/Polalalabear/amidst/pull/257) | PR | fix(q1q5): pin engineering tracking scope for rc4 and Q2 production | Q1、Q2、Q3 | 已併入 staging（`c1d9cbd`），待審入主線 |

### 進行中（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#243](https://github.com/Polalalabear/amidst/pull/243) | PR（Draft） | feat(workbench): Q1 結果牆並排播放與追蹤單畫面預設（D86-3） | Q1、Q2 | Draft；Q1 結果牆並排播放與追蹤單畫面預設（D86-3） |

### 未完成（3）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#112](https://github.com/Polalalabear/amidst/issues/112) | Issue | QT-19：Q 線 HTTP 端點與 #80 接線（R-1–R-7） | Q1、Q2、Q3 | blocked：Q 線 HTTP 端點與 #80 接線；本機模型接線 #174 已併入 staging |
| [#124](https://github.com/Polalalabear/amidst/issues/124) | Issue | QT-31：Q1–Q5 端到端 browser acceptance 與 Demo 腳本 | Q1、Q2、Q3、Q4、Q5 | blocked：端到端瀏覽器驗收；Demo 腳本草稿已併入 staging（#181、#182） |
| [#130](https://github.com/Polalalabear/amidst/issues/130) | Issue | QT-34：組員 瀏覽器驗收（人工操作） | Q1、Q2、Q3、Q4、Q5 | 組員瀏覽器驗收未開始 |

### 待確認（5）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#194](https://github.com/Polalalabear/amidst/issues/194) | Issue | Demo v1：baseline 執行入口、逐次紀錄／replay 與正式產製預檢 | Q1、Q2、Q3、Q4、Q5 | 對應 PR #195 已併入 staging；issue 仍開著，是否關閉待確認 |
| [#200](https://github.com/Polalalabear/amidst/issues/200) | Issue | Baseline 前置總驗收：可重建來源、真本機 smoke 與決策清單 | Q1、Q2、Q3、Q4、Q5 | 對應 PR #201 已併入 staging；issue 仍開著，是否關閉待確認 |
| [#206](https://github.com/Polalalabear/amidst/issues/206) | Issue | 完整 baseline 條線 C：工作台、重現入口與一次驗收 | Q1、Q2、Q3、Q4、Q5 | 對應 PR #207 已併入 staging；issue 仍開著，是否關閉待確認 |
| [#208](https://github.com/Polalalabear/amidst/issues/208) | Issue | 修正工作台黑畫面與完整播放，延長工程事件並量測連續性 | Q2、Q5 | 對應 PR #209 關閉未合併（head 已含於 staging，經 #231）；issue 仍開著，是否關閉待確認 |
| [#210](https://github.com/Polalalabear/amidst/issues/210) | Issue | 動態 RGB baseline：8秒逐格人物、工作台有界快取與審查前完整驗收 | Q2、Q5 | 對應 PR #211 關閉未合併（head 已含於 staging，經 #231）；issue 仍開著，是否關閉待確認 |

## Line 2 複雜場景

### 進行中（16）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#244](https://github.com/Polalalabear/amidst/issues/244) | Issue | L2-1 Q5 評分器擴充：一窗多次 RETURN、長時間 LOST、重疊接手 | Q5 | L2-1 Q5 評分器擴充；設計稿 PR #258（Draft） |
| [#245](https://github.com/Polalalabear/amidst/issues/245) | Issue | L2-2 複雜情境卡 v2 | Q5 | L2-2 複雜情境卡 v2；PR #261（Draft） |
| [#246](https://github.com/Polalalabear/amidst/issues/246) | Issue | L2-3 workbench 長時間軸 | Q5 | L2-3 workbench 長時間軸；PR #255（Draft） |
| [#247](https://github.com/Polalalabear/amidst/issues/247) | Issue | L2-4 漏檢診斷與偵測改善 | Q2 | L2-4 漏檢診斷與偵測改善；PR #273（Draft） |
| [#248](https://github.com/Polalalabear/amidst/issues/248) | Issue | L2-5 linker／Q5 controller：反覆暫失與 LOST 期限契約提案 | Q5 | L2-5 linker／controller 契約提案；PR #266（Draft） |
| [#249](https://github.com/Polalalabear/amidst/issues/249) | Issue | L2-6 工程小場景：2–3 台鏡頭、約 30 秒、含一個轉角 | Q5 | L2-6 工程小場景；規劃 PR #274（Draft）；渲染延後（D90-3） |
| [#250](https://github.com/Polalalabear/amidst/issues/250) | Issue | L2-7 使用者決策清單 | — | L2-7 使用者決策清單；D90 已回答（第 3 題磁碟已定案，第 4 題第二版範圍暫定）；issue 仍開著 |
| [#251](https://github.com/Polalalabear/amidst/issues/251) | Issue | L2-0 第二條線：複雜場景（D87） | Q5 | L2-0 第二條線傘狀 issue（D87）；工作分配見 [兩條線計畫](../agents/Q1Q5_TWO_LINE_PLAN_20261027.md) |
| [#255](https://github.com/Polalalabear/amidst/pull/255) | PR（Draft） | feat(workbench-v2): L2-3 長時間軸／8 鏡頭牆（依賴 #243） | Q5 | Draft；L2-3 長時間軸／8 鏡頭牆；base 為 #243 的分支，依賴 #243 |
| [#258](https://github.com/Polalalabear/amidst/pull/258) | PR（Draft） | docs(evaluation): Q5 評分規則 v2 設計稿（L2-1，#244） | Q5 | Draft；Q5 評分規則 v2 設計稿（L2-1，#244） |
| [#261](https://github.com/Polalalabear/amidst/pull/261) | PR（Draft） | docs(evaluation): 複雜情境卡 v2（L2-2，#245） | Q5 | Draft；複雜情境卡 v2（L2-2，#245） |
| [#266](https://github.com/Polalalabear/amidst/pull/266) | PR（Draft） | docs(contract): Line 2 C1–C10 answers and linker/Q5 proposal | Q5 | Draft；Line 2 C1–C10 回答與 linker／Q5 契約提案（base staging） |
| [#271](https://github.com/Polalalabear/amidst/pull/271) | PR（Draft） | docs(r004): Line 2 static path feasibility and V1–V10 answers | Q5 | Draft；Line 2 靜態路徑可行性與 V1–V10 回答（base staging） |
| [#272](https://github.com/Polalalabear/amidst/pull/272) | PR（Draft） | docs(graph): v4 overlap draft with pending M1 and missing exits | Q5 | Draft；r004 圖 v4 重疊草案（M1 待 G4、出口缺項；不取代 v3）（base staging） |
| [#273](https://github.com/Polalalabear/amidst/pull/273) | PR（Draft） | feat(diagnostics): opt-in offline score and IoU gate comparison | Q2 | Draft；離線分數與 IoU 門檻比較（opt-in，預設 runtime 不變）（base staging） |
| [#274](https://github.com/Polalalabear/amidst/pull/274) | PR（Draft） | docs(l2): 30-second two-camera corner scene plan and resource budget | Q5 | Draft；30 秒、兩鏡頭含轉角的工程場景規劃與資源預算（base staging） |

## 流程：任務板、交接與文件

### 已完成（22）

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
| [#228](https://github.com/Polalalabear/amidst/pull/228) | PR | docs(q1q5): P1 工程預驗收走查清單（AC1–AC8） | Q1、Q2、Q3、Q4、Q5 | 已合併主線（`bd44ff2`，2026-10-27）；P1 工程預驗收走查清單 [走查清單](Q1Q5_P1_WALKTHROUGH_CHECKLIST.md)；P1 不是正式成績（D76） |
| [#225](https://github.com/Polalalabear/amidst/pull/225) | PR | docs(claude): point CLAUDE.md reading order at Q1–Q5 handoff | — | 已合併主線（`549d8ac`，2026-10-25）；CLAUDE.md 閱讀順序改指向 Q1–Q5 交接文件 |
| [#191](https://github.com/Polalalabear/amidst/pull/191) | PR | docs(agents): update the Q1–Q5 progress guide with every new PR and issue | — | 已合併主線（`4fddbc3`，2026-10-24）；在 AGENTS.md／CLAUDE.md 加入本文維護規則（D91-4 後改由協調者或 mainline 的 docs PR 批次補） |
| [#147](https://github.com/Polalalabear/amidst/issues/147) | Issue | QT-42：組員審查包（資料夾）產生器與回收匯入器 | Q1、Q3、Q4 | 已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：已完成關閉（2026-10-26）；原備註：文字審查包 #151 已併入 staging；圖片包等 #115、#118 |
| [#213](https://github.com/Polalalabear/amidst/pull/213) | PR | Merge staging batch 1 (#136 #139 #140 #141 #143 #132) into mainline/q1q5 | — | 已合併主線（`3ccaa3a`，2026-10-25） |
| [#214](https://github.com/Polalalabear/amidst/pull/214) | PR | 五項closeout：符合性重驗、Qwen診斷、回收補件、ROI與Q3審查準備 | Q3、Q5 | 關閉未合併（2026-10-27，盤點）；head 已含於 staging（經 #231 的 merge `680ca35`），分支保留 |
| [#215](https://github.com/Polalalabear/amidst/pull/215) | PR | docs: Q1–Q5 baseline acceptance plan and progress update (2026-10-25) | Q1、Q2、Q3、Q4、Q5 | 已合併主線（`7f08592`，2026-10-25） |
| [#217](https://github.com/Polalalabear/amidst/pull/217) | PR | docs: Q1–Q5 local test setup and progress update (2026-10-25) | — | 已合併主線（`e8f98dd`，2026-10-25） |
| [#223](https://github.com/Polalalabear/amidst/pull/223) | PR | docs: coordinator handoff 2026-10-25 and handoff-upload rule | — | 已合併主線（`1b6c56b`，2026-10-25） |
| [#226](https://github.com/Polalalabear/amidst/pull/226) | PR | CX-2／#147 #151：組員說明、逐列回收拒錯與 PILOT 隔離 | Q1、Q3、Q4 | 已併入 staging（`4c96140`），待審入主線 |
| [#232](https://github.com/Polalalabear/amidst/pull/232) | PR | 交接：公開 LOCAL 文件與相對路徑、大小及 hash 收據 | — | 已併入 staging（`63ce04d`），待審入主線 |
| [#241](https://github.com/Polalalabear/amidst/pull/241) | PR | docs(agents): 協調者交接 2026-10-26 與進度導覽更新 | — | 已合併主線（`2675c21`，2026-10-26） |
| [#252](https://github.com/Polalalabear/amidst/pull/252) | PR | docs(agents): 兩條線工作分配（D87） | — | 兩條線工作分配（D87）；已合併主線（`9708fb6`，2026-10-27） |

### 進行中（10）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#83](https://github.com/Polalalabear/amidst/pull/83) | PR | docs(agents): 決策索引、系統總覽、組員上手指南 | — | 組員上手文件、決策索引與系統總覽（非 Draft），待審查與合併 |
| [#93](https://github.com/Polalalabear/amidst/issues/93) | Issue | Q1–Q5 任務板（從這裡開始） | Q1、Q2、Q3、Q4、Q5 | Q1–Q5 任務板；決定已到 D93（2026-10-27） |
| [#131](https://github.com/Polalalabear/amidst/issues/131) | Issue | QT-35：Codex finalization 搬移計畫（文件） | — | 標 ready（內文寫 needs-auth）；搬移計畫文件已併入 staging（#143） |
| [#263](https://github.com/Polalalabear/amidst/issues/263) | Issue | 文件封存與現況更新（D91） | Q1、Q2、Q3、Q4、Q5 | 文件封存與現況更新（D91）；S1 #264、S2 #265、S3 本 PR、S4 #270 |
| [#264](https://github.com/Polalalabear/amidst/pull/264) | PR（Draft） | docs(archive): 封存索引與歷史文件檔頭（#263 S1, D91） | — | Draft；封存索引與歷史文件檔頭（#263 S1） |
| [#265](https://github.com/Polalalabear/amidst/pull/265) | PR（Draft） | docs: 入口文件更新與 2026-10-27 協調者交接（D91, S2） | — | Draft；入口文件更新與 2026-10-27 協調者交接（#263 S2） |
| [#267](https://github.com/Polalalabear/amidst/pull/267) | PR（Draft） | integration: prepare staging into mainline with D91 mainline docs preserved | — | Draft；staging → mainline 整合（D91 的 mainline 文件保留）；待 #260 等合入 staging 後更新，未合併 |
| [#268](https://github.com/Polalalabear/amidst/pull/268) | PR（Draft） | docs(archive): mark six Codex historical handoffs under D91 | — | Draft；六份 Codex 歷史交接加 D91 封存註記（base staging） |
| [#270](https://github.com/Polalalabear/amidst/pull/270) | PR（Draft） | docs(specs): Q1–Q5 產品規格（#263 S4, D91） | Q1、Q2、Q3、Q4、Q5 | Draft；Q1–Q5 產品規格（#263 S4） |
| [#276](https://github.com/Polalalabear/amidst/pull/276) | PR（Draft） | docs(progress): Q1–Q5 進度導覽與過期文件更新（#263 S3, D91） | Q1、Q2、Q3、Q4、Q5 | Draft；重算全部 PR／issue 並補 PR #242–#274、issue #244–#251、#263 與漏列項目，新增「Line 2 複雜場景」分類；同時更新驗收計畫、本機測試設定、D79 文件、workbench v2 設計、finalization 計畫的檔頭或狀態 |

### 未完成（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#137](https://github.com/Polalalabear/amidst/issues/137) | Issue | QT-36：組員 交接試跑（照 TEAM_ONBOARDING 從零開始） | — | 組員交接試跑未開始 |

### 待確認（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#87](https://github.com/Polalalabear/amidst/issues/87) | Issue | GitHub 整理紀錄（2026-10-20，D63 後） | — | D63 後的 GitHub 整理紀錄，最後更新 10-20；待確認是否關閉 |

## 暫停：跨鏡頭盲區 3D 重建線

**已完成（37）**

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
| [#77](https://github.com/Polalalabear/amidst/pull/77) | PR | feat(scene-markers): E 包 受控場景標記範本與 safe 側 validator | — | 關閉未合併（2026-10-26）；Office 時期的 E 包，已過時（盤點留言） |

**待確認（1）**

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#82](https://github.com/Polalalabear/amidst/pull/82) | PR（Draft） | feat(eval): K7 r003 static-geometry verification for O10 — do not merge before user approval | — | K7 r003 靜態幾何驗證（舊線），標示使用者核准前不合併；D88 決定先留著；r004 改由 #117 檢查，待確認是否關閉 |

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
