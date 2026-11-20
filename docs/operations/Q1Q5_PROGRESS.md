# Q1–Q5 進度導覽

快照時間：2026-11-18 晚間（D332 批次補列，`gh` 逐項重查 #608、#610、#614–#620 與相關 issue；`main` `7393bf62`，為撰寫時 `origin/main` 的 head）。資料來源：GitHub 上全部 PR 與 issue。
本文涵蓋 **358 個 PR 與 262 個 issue，共 620 項**（編號 #1–#620 連續，無缺號；本 PR 依 CLAUDE.md 不列自己的列，下次批次補列），每項只列在一個主分類下。
維護方式（D91-4）：本文的列由協調者批次補列，一般 PR／issue 不必各自更新，2026-11-10 起主線改為 `main`（D200），PR 的 base 一律是 `main`；`mainline/q1q5` 凍結，staging 已不再使用。即時狀態仍以[任務板 #93](https://github.com/Polalalabear/amidst/issues/93)為準。

## 分類方式

- **主分類：**Q1–Q5 五大問題；無法歸到單一問題的列在「共用」與「流程」；D87 開的第二條線（複雜場景）列在「Line 2 複雜場景」；2026-10-20 轉向 Q1–Q5 之前的工作列在「暫停」與「歷史」。「也涉及」欄列出其他相關問題。
- **已完成：**PR 已合併，或 issue 已完成關閉。合併進 `codex/q1q5-staging` 的 PR 標「待審入主線」，還沒進 `mainline/q1q5`（staging → mainline 的整合是 [#267](https://github.com/Polalalabear/amidst/pull/267)，Draft）。這是 2026-10 的分類方式；2026-11-10 起整合分支是 `main`（D200），`codex/q1q5-staging` 與 `mainline/q1q5`（凍結在 `8c741451`）只是歷史，見下一項。關閉未合併的 PR 也列在這裡，備註寫明。
- **2026-11 補列：**#306–#585 與 #1–#305 的狀態變更依 `gh` 原始輸出補到 2026-11-18。合併與關閉日期取 GitHub 的 UTC 日期。已合併的 PR 備註寫實際合併到的 base（2026-11-10 起為 `main`，D200；之前為 `codex/q1q5-staging`、`mainline/q1q5` 或功能整合分支），關閉未合併的寫「關閉未合併」；issue 依 GitHub 關閉原因寫「已完成關閉」或「關閉（不處理）」。狀態變更的舊列移到「已完成」，原備註保留在「原備註」之後；舊備註中的「待審入主線」是當時狀態，不再更新。2026-11-08 的大批關閉（#306–#347 的 deferred 項、#348–#368 的 CQ PR、W 系列等）原樣依 GitHub 狀態記錄。
- **2026-11 新增分類：**「Agent：WP／DP4 與評估」（WP1–WP6、DP4、Agent 決策與 OpenAI／Ollama）、「即時模式（Live mode）」（#544、#547、#551、#552、#553、#556、#559、#561、#563）、「4 人場景、8 鏡頭與 N6 素材（#516）」、「Demo 整合、前台 UI 與 8785 更新（#445）」、「W 系列：D126 查找與追蹤核心」（#411–#478 的 Argon／Codex 拉取佇列，D127）、「大掃除、CI 與可攜性（#486）」。CQ／FEAT 議題（#306–#347、#369–#376）及其 PR 歸入原有的 Line 2、r004、工作台與流程分類。「也涉及」欄只在能判斷時填寫，新列一律 `—`。
- **進行中：**開著的 PR，或程式已有 PR／已併入 staging 的 issue。
- **未完成：**尚未開始、blocked 或等授權的 issue。
- **待確認：**是否保留、合併或關閉還沒決定，例如舊線遺留的 PR、等使用者決定的提案、工作已完成但 issue 還開著。

## 總覽

| 分類 | 已完成 | 進行中 | 未完成 | 待確認 | 合計 |
| --- | ---: | ---: | ---: | ---: | ---: |
| [Q1 依條件找鏡頭](#q1-依條件找鏡頭) | 5 | 0 | 0 | 0 | 5 |
| [Q2 在畫面中找人](#q2-在畫面中找人) | 6 | 0 | 0 | 0 | 6 |
| [Q3 理解使用者語意](#q3-理解使用者語意) | 22 | 0 | 0 | 0 | 22 |
| [Q4 判斷畫面是否含目標](#q4-判斷畫面是否含目標) | 9 | 0 | 0 | 0 | 9 |
| [Q5 決定是否切鏡](#q5-決定是否切鏡) | 20 | 0 | 0 | 0 | 20 |
| [共用：契約、規則、參數與一致性檢查](#共用契約規則參數與一致性檢查) | 44 | 0 | 0 | 0 | 44 |
| [共用：r004 場景、資料、索引與儲存](#共用r004-場景資料索引與儲存) | 51 | 0 | 0 | 0 | 51 |
| [共用：工作台、HTTP 與 Demo](#共用工作台http-與-demo) | 62 | 0 | 0 | 0 | 62 |
| [Line 2 複雜場景](#line-2-複雜場景) | 50 | 0 | 0 | 0 | 50 |
| [流程：任務板、交接與文件](#流程任務板交接與文件) | 89 | 2 | 0 | 0 | 91 |
| [Agent：WP／DP4 與評估](#agentwpdp4-與評估) | 25 | 1 | 1 | 0 | 27 |
| [即時模式（Live mode）](#即時模式live-mode) | 26 | 4 | 5 | 0 | 35 |
| [4 人場景、8 鏡頭與 N6 素材（#516）](#4-人場景8-鏡頭與-n6-素材516) | 16 | 0 | 0 | 0 | 16 |
| [Demo 整合、前台 UI 與 8785 更新（#445）](#demo-整合前台-ui-與-8785-更新445) | 25 | 0 | 1 | 1 | 27 |
| [W 系列：D126 查找與追蹤核心](#w-系列d126-查找與追蹤核心) | 61 | 0 | 0 | 0 | 61 |
| [大掃除、CI 與可攜性（#486）](#大掃除ci-與可攜性486) | 19 | 0 | 1 | 0 | 20 |
| [暫停：跨鏡頭盲區 3D 重建線](#暫停跨鏡頭盲區-3d-重建線) | 38 | 0 | 0 | 0 | 38 |
| [歷史：Office Demo 與 Phase 1／2](#歷史office-demo-與-phase-12) | 36 | 0 | 0 | 0 | 36 |
| **合計** | **604** | **7** | **8** | **1** | **620** |

## 最近改動（2026-10-23 起）

- 2026-11-18 晚間（協調者批次補列，D91-4，D332，隨晚間交接 PR）：快照擴大到 #1–#620。新增 #614–#620；已合併移到「已完成」：#610（`118c2035`）、#614（`1f6ecacd`）、#615（`7393bf62`）、#616（`d3dd2d65`）、#618（`50f2fd14`）；已關閉的 issue 移到「已完成」：#571、#572（由 #610 完成）、#576（D324）；#617 列「進行中」（Draft），#619、#620 列「未完成」；#608 改為非 Draft；#608、#617 NEEDS_CHANGES（和 main 衝突，D331）。
- 2026-11-18（協調者批次補列，D91-4，D311–D318）：快照擴大到 #1–#613。新增 #586–#613；已合併（merge commit）移到「已完成」：#559、#564、#584、#587、#590、#595、#599、#603、#604、#606、#607、#609、#611、#613，已關閉的 issue 亦移到「已完成」：#552、#555、#568–#570、#573、#577–#583、#585、#591、#593、#600–#602、#605；#571、#572、#576、#588、#589、#596、#597、#598、#612 列「未完成」，#608、#610 列「進行中」（Draft），#594 列「待確認」。#599、#603 等已合併的 PR 的 merge commit 見各列。
- 2026-11-18（#580 批次補列，D91-4、D281）：快照擴大到 #1–#585。新增 #565、#567、#575、#584（PR）與 #566、#568–#574（CX-L5 A/B 子項）、#576–#583、#585（CL-B 系列、待使用者決定）；#558（`edb96a31`）、#563（`0606b164`）、#565（`3137a1ca`）、#567（`2f013cb8`）、#575（`59782b1d`）已合併，#554 已關閉，移到「已完成」；#559、#564 仍開著。`main` 頭為 `59782b1d`。工作清單改在 [#93](https://github.com/Polalalabear/amidst/issues/93) 本文（D281）。
- 2026-11-17 晚間（協調者批次補列，D91-4，隨晚間交接 PR）：快照擴大到 #1–#564。新增 #558（實驗紀錄 v4）、#559（Codex 偵測＋啟動入口，Draft）、#560、#561（Codex，已合併）、#562（交接，已合併）、#563（LLM 開關，Draft）、#564（workbench-v2 易用性，Draft）；#546、#547、#551、#556、#557 已合併、#553 已完成關閉，移到「已完成」；#554 工作已由 #560 合併但 issue 還開著，列「待確認」；#552、#555 的程式在 #559，改列「進行中」。`main` 頭為 `e9db4fdf`。
- 2026-11-17 本 PR（#557）：協調者批次補列（D91-4），快照擴大到 #1–#557。新增 #549–#557（#549、#550 已合併；#551、#556 即時模式 Draft PR；#552–#555 Codex 佇列 CX-L1–CX-L4，D248）；#544（`7d612aa7`）、#548 已合併，#516 已完成關閉，移到「已完成」。`main` 頭為 `7d612aa7`。
- 2026-11-16 本 PR（#548）：協調者批次補列（D91-4），快照擴大到 #1–#548。補上 #306–#547（2026-11-01 之後的 CQ／FEAT 議題、D126 W 系列、WP1–WP6 Agent、8 鏡頭與 4 人場景、大掃除 #486、live mode、8785 更新）；#1–#305 中 105 列狀態有變，移到「已完成」。`main` 頭為 `8b023775`。
- 2026-11-10 主線改為 `main`（D200，[#512](https://github.com/Polalalabear/amidst/pull/512) 把 `mainline/q1q5` 併入 `main`）；2026-11-15 前後的新 PR 都以 `main` 為 base，即時狀態以[任務板 #93](https://github.com/Polalalabear/amidst/issues/93)為準。
- 2026-10-28 本 PR（#276）依 Opus 審查 P3-5 刷新（協調者批次刷新，D91-4）：快照擴大到 #1–#305；補上 #277–#305（#277、#278、#294、#295、#305 為 Draft PR；#279 佇列與 #280–#304 的 CQ 議題）；#129 依 D96-4 改為已取消；#240、#127、#260、#278、#254、#256、#269、#275、#277 補上 Claude 審查結論與 head。
- 2026-10-28 合併（使用者授權的 D91 文件批次，[紀錄](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6460927941)）：[#264](https://github.com/Polalalabear/amidst/pull/264)（`564352a`）、[#265](https://github.com/Polalalabear/amidst/pull/265)（`204a180`）、[#270](https://github.com/Polalalabear/amidst/pull/270)（`741996c`）進 `mainline/q1q5`，mainline 頭為 `741996c`；#276 待刷新後另行授權，#240 待 CQ-05（[#284](https://github.com/Polalalabear/amidst/issues/284)）修正。
- 2026-10-28 Claude 審查第一批結論：#260、#278 PASS_WITH_NOTES；#305、#294、#269、#240 NEEDS_CHANGES；#276、#127（head `e1415f3`，AC7 仍未通過）、#254、#277 PASS_WITH_NOTES；#256、#275 已交增量，尚未複審。
- 2026-10-27 決定 D95、D96（[#93](https://github.com/Polalalabear/amidst/issues/93)）：[D95](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6439940143) Codex 任務佇列 [#279](https://github.com/Polalalabear/amidst/issues/279)（自取）與 Claude 審查分工，最低目標是完成複雜事件且組員能自己做模型評測；[D96](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6442431884) A4-c2（#256）與 B4-e（#275）先標不計分待驗證、CQ-14 可攜包採重播凍結輸出（Python 3.12）、解除 CQ-05 排在 CQ-04 之後的順序、取消 #129。#93 目前沒有 D97。
- 2026-10-27 本 PR（#276，#263 的 S3）：用 `gh` 重算全部 PR 與 issue。這次重算發現 #192–#274 之間先前缺 80 列（不只 D91-4 列的 #220、#221、#222、#224、#226、#230、#232 七列），一併補上；同時補入 issue #244–#251、#263 與 PR #242–#274，新增「Line 2 複雜場景」分類，已合併或關閉的項目（例如 #228、#252、#253、#257）移到已完成。
- 2026-10-27 決定 D88–D94（全文見 [#93](https://github.com/Polalalabear/amidst/issues/93)）：[D88](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6422147844) 本機清理，#240、#228 修衝突，#163、#82 先留著；[D89](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423194857) 核定 r004 情境卡 v1（A4-1＋B4-1，50 s／42 s，NO_SWITCH 讓位）；[D90](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423575212) Line 2 決策（長時間 LOST 由評估端分類、重疊接手、磁碟維持現狀[定案](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423763378)、第二版範圍暫定）；[D91](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434355675) 文件封存與現況更新（#263）；[D92](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434464633)（另見[補充](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434474506)）情境卡調整（A4-e、B4-d 不計分，計分事件 8 → 6 或 5）與 #260 決定；[D93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434812845) Line 2 重疊對評分（只評有出口條帶的對，不併入主比率）；[D94](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434821818) Line 2 RETURN 邊界（STANDARD 只收 d ≤ 1.6 s，adapter 拒絕 1.6 < d < 1.8 s，Line 1 不變）。
- 2026-10-27 Codex 派工與交件（#93）：第一批 [派工](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423281851) 與 [交件索引](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6424123274)；第二批 [派工](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434379604) 與 [交件索引](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434641943)；第三批 [派工](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434474862)。
- 2026-10-27 盤點關閉（[紀錄](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6422095384)）：7 個 PR（#77、#135、#209、#211、#212、#214、#216）與 15 個 issue（#95、#102–#107、#119–#122、#146、#147、#192、#196），分支一律保留。
- 2026-10-27 合併：[#257](https://github.com/Polalalabear/amidst/pull/257) 進 staging（`c1d9cbd`）；[#242](https://github.com/Polalalabear/amidst/pull/242)（`d6a9e21`）、[#238](https://github.com/Polalalabear/amidst/pull/238)（`001cbcf`）、[#259](https://github.com/Polalalabear/amidst/pull/259)（`7a33d6d`）、[#262](https://github.com/Polalalabear/amidst/pull/262)（`434e579`）進 staging；[#228](https://github.com/Polalalabear/amidst/pull/228)（`bd44ff2`）、[#252](https://github.com/Polalalabear/amidst/pull/252)（`9708fb6`）、[#253](https://github.com/Polalalabear/amidst/pull/253)（`0edd8a3`）進 mainline。#253 是 r004 A4／B4 情境卡 v1（`docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md`），D89 核定；#252 是兩條線工作分配（D87，[Q1Q5_TWO_LINE_PLAN_20261027.md](../agents/Q1Q5_TWO_LINE_PLAN_20261027.md)）。
- 2026-10-27 決定 D87（兩條線）：Line 2 傘狀 issue [#251](https://github.com/Polalalabear/amidst/issues/251)（L2-1..L2-7 為 #244–#250）。
- 2026-10-27 D91 文件整理（[#263](https://github.com/Polalalabear/amidst/issues/263)）：S1 [#264](https://github.com/Polalalabear/amidst/pull/264)（封存索引）、S2 [#265](https://github.com/Polalalabear/amidst/pull/265)（入口文件與 10-27 交接）、S4 [#270](https://github.com/Polalalabear/amidst/pull/270)（產品規格）已於 2026-10-28 合併，S3 本 PR 仍為 Draft；最新的協調者交接是 [COORDINATOR_HANDOFF_20261027.md](../agents/COORDINATOR_HANDOFF_20261027.md)（隨 #265 併入 mainline）。
- 2026-10-26 合併：[#231](https://github.com/Polalalabear/amidst/pull/231) baseline 整合進 staging（`680ca35`）；[#241](https://github.com/Polalalabear/amidst/pull/241) 進 mainline（`2675c21`）；[#229](https://github.com/Polalalabear/amidst/pull/229) 以 merge commit `f5168f6` 進 `mainline/q1q5`。[#237](https://github.com/Polalalabear/amidst/pull/237)（契約 B，`83da40f`）、[#239](https://github.com/Polalalabear/amidst/pull/239)（Qwen 報告註記，`7b05211`）進 `codex/q1q5-staging`；#237 取代 #219（GitHub 經 `635a102` 自動標成 MERGED，分支保留）。
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

### 已完成（5）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#109](https://github.com/Polalalabear/amidst/issues/109) | Issue | QT-16：Q1 依條件找相機（查詢模組＋類別別名表） | — | 已完成關閉（2026-11-01）；原備註：blocked：Q1 搜尋 #157 已併入 staging；等 kit 修正 #156 |
| [#138](https://github.com/Polalalabear/amidst/issues/138) | Issue | QT-37：組員 Q1 條件查詢測試集與評分器（SYNTHETIC） | — | 已完成關閉（2026-11-08）；原備註：組員 Q1 測試集未交；評估器已併入 staging（#164） |
| [#157](https://github.com/Polalalabear/amidst/pull/157) | PR | Q1 index search and scoped pagination（依 #144 提案；blocked #156） | — | 已併入 staging（`15c0f79`），待審入主線 |
| [#164](https://github.com/Polalalabear/amidst/pull/164) | PR | Q1 evaluator for human expected cores and pinned frozen schemas (code only) | — | 已併入 staging，待審入主線 |
| [#224](https://github.com/Polalalabear/amidst/pull/224) | PR | CX-2／#164：隔離合成分母，補 Q1 請求與分頁檢查 | — | 已併入 staging（`08d4793`），待審入主線 |

**其他分類中也涉及 Q1 的項目：**
- 已完成：[#146](https://github.com/Polalalabear/amidst/issues/146)、[#149](https://github.com/Polalalabear/amidst/pull/149)、[#152](https://github.com/Polalalabear/amidst/pull/152)、[#204](https://github.com/Polalalabear/amidst/issues/204)、[#205](https://github.com/Polalalabear/amidst/pull/205)、[#221](https://github.com/Polalalabear/amidst/pull/221)、[#236](https://github.com/Polalalabear/amidst/pull/236)、[#240](https://github.com/Polalalabear/amidst/pull/240)、[#269](https://github.com/Polalalabear/amidst/pull/269)、[#284](https://github.com/Polalalabear/amidst/issues/284)、[#285](https://github.com/Polalalabear/amidst/issues/285)、[#167](https://github.com/Polalalabear/amidst/pull/167)、[#86](https://github.com/Polalalabear/amidst/pull/86)、[#88](https://github.com/Polalalabear/amidst/issues/88)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#99](https://github.com/Polalalabear/amidst/issues/99)、[#126](https://github.com/Polalalabear/amidst/pull/126)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#133](https://github.com/Polalalabear/amidst/issues/133)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#156](https://github.com/Polalalabear/amidst/issues/156)、[#161](https://github.com/Polalalabear/amidst/pull/161)、[#173](https://github.com/Polalalabear/amidst/pull/173)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#260](https://github.com/Polalalabear/amidst/pull/260)、[#278](https://github.com/Polalalabear/amidst/pull/278)、[#296](https://github.com/Polalalabear/amidst/issues/296)、[#297](https://github.com/Polalalabear/amidst/issues/297)、[#303](https://github.com/Polalalabear/amidst/issues/303)、[#305](https://github.com/Polalalabear/amidst/pull/305)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#101](https://github.com/Polalalabear/amidst/issues/101)、[#102](https://github.com/Polalalabear/amidst/issues/102)、[#103](https://github.com/Polalalabear/amidst/issues/103)、[#113](https://github.com/Polalalabear/amidst/issues/113)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#118](https://github.com/Polalalabear/amidst/issues/118)、[#134](https://github.com/Polalalabear/amidst/pull/134)、[#136](https://github.com/Polalalabear/amidst/pull/136)、[#139](https://github.com/Polalalabear/amidst/pull/139)、[#155](https://github.com/Polalalabear/amidst/pull/155)、[#196](https://github.com/Polalalabear/amidst/issues/196)、[#197](https://github.com/Polalalabear/amidst/pull/197)、[#302](https://github.com/Polalalabear/amidst/issues/302)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#100](https://github.com/Polalalabear/amidst/issues/100)、[#112](https://github.com/Polalalabear/amidst/issues/112)、[#119](https://github.com/Polalalabear/amidst/issues/119)、[#120](https://github.com/Polalalabear/amidst/issues/120)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#175](https://github.com/Polalalabear/amidst/pull/175)、[#176](https://github.com/Polalalabear/amidst/pull/176)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#194](https://github.com/Polalalabear/amidst/issues/194)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#206](https://github.com/Polalalabear/amidst/issues/206)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#243](https://github.com/Polalalabear/amidst/pull/243)、[#257](https://github.com/Polalalabear/amidst/pull/257)、[#277](https://github.com/Polalalabear/amidst/pull/277)、[#300](https://github.com/Polalalabear/amidst/issues/300)、[#147](https://github.com/Polalalabear/amidst/issues/147)、[#151](https://github.com/Polalalabear/amidst/pull/151)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#226](https://github.com/Polalalabear/amidst/pull/226)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)

## Q2 在畫面中找人

### 已完成（6）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#71](https://github.com/Polalalabear/amidst/pull/71) | PR | feat(workbench): player-grid pure module for 1/2/4/8 synced tiles | — | 已合併主線 |
| [#107](https://github.com/Polalalabear/amidst/issues/107) | Issue | QT-14：同鏡頭最小 IoU 連接器與暫失觸發 | — | 已完成關閉（2026-10-26）；原備註：同鏡頭 IoU 連接器已併入 staging（#141），待審入主線 |
| [#141](https://github.com/Polalalabear/amidst/pull/141) | PR | Q1–Q5 #107: 同鏡頭 selected-seed IoU 連接器與缺格邊界。 | — | 已合進主線（第 1 批，2026-10-25） |
| [#262](https://github.com/Polalalabear/amidst/pull/262) | PR | docs(p1): frame-by-frame diagnosis of 28 reported detection/link gaps | Q4、Q5 | 已併入 staging（`434e579`），待審入主線 |
| [#387](https://github.com/Polalalabear/amidst/pull/387) | PR | DEMO-UI-F-T：live 追蹤（Q2）test-first 測試 | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#388](https://github.com/Polalalabear/amidst/pull/388) | PR | DEMO-UI-F: 修復 live Q2 scope/session binding 與 P1 起點 | — | 已合併 `codex/q1q5-staging`（2026-11-03） |

**其他分類中也涉及 Q2 的項目：**
- 已完成：[#152](https://github.com/Polalalabear/amidst/pull/152)、[#269](https://github.com/Polalalabear/amidst/pull/269)、[#285](https://github.com/Polalalabear/amidst/issues/285)、[#114](https://github.com/Polalalabear/amidst/issues/114)、[#158](https://github.com/Polalalabear/amidst/pull/158)、[#104](https://github.com/Polalalabear/amidst/issues/104)、[#110](https://github.com/Polalalabear/amidst/issues/110)、[#116](https://github.com/Polalalabear/amidst/issues/116)、[#117](https://github.com/Polalalabear/amidst/issues/117)、[#150](https://github.com/Polalalabear/amidst/pull/150)、[#163](https://github.com/Polalalabear/amidst/pull/163)、[#166](https://github.com/Polalalabear/amidst/pull/166)、[#169](https://github.com/Polalalabear/amidst/pull/169)、[#184](https://github.com/Polalalabear/amidst/issues/184)、[#185](https://github.com/Polalalabear/amidst/pull/185)、[#202](https://github.com/Polalalabear/amidst/issues/202)、[#203](https://github.com/Polalalabear/amidst/pull/203)、[#218](https://github.com/Polalalabear/amidst/issues/218)、[#86](https://github.com/Polalalabear/amidst/pull/86)、[#88](https://github.com/Polalalabear/amidst/issues/88)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#99](https://github.com/Polalalabear/amidst/issues/99)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#133](https://github.com/Polalalabear/amidst/issues/133)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#173](https://github.com/Polalalabear/amidst/pull/173)、[#178](https://github.com/Polalalabear/amidst/issues/178)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#260](https://github.com/Polalalabear/amidst/pull/260)、[#278](https://github.com/Polalalabear/amidst/pull/278)、[#296](https://github.com/Polalalabear/amidst/issues/296)、[#297](https://github.com/Polalalabear/amidst/issues/297)、[#303](https://github.com/Polalalabear/amidst/issues/303)、[#305](https://github.com/Polalalabear/amidst/pull/305)、[#75](https://github.com/Polalalabear/amidst/pull/75)、[#80](https://github.com/Polalalabear/amidst/pull/80)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#101](https://github.com/Polalalabear/amidst/issues/101)、[#102](https://github.com/Polalalabear/amidst/issues/102)、[#113](https://github.com/Polalalabear/amidst/issues/113)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#132](https://github.com/Polalalabear/amidst/pull/132)、[#134](https://github.com/Polalalabear/amidst/pull/134)、[#136](https://github.com/Polalalabear/amidst/pull/136)、[#155](https://github.com/Polalalabear/amidst/pull/155)、[#187](https://github.com/Polalalabear/amidst/pull/187)、[#227](https://github.com/Polalalabear/amidst/pull/227)、[#235](https://github.com/Polalalabear/amidst/pull/235)、[#238](https://github.com/Polalalabear/amidst/pull/238)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#100](https://github.com/Polalalabear/amidst/issues/100)、[#112](https://github.com/Polalalabear/amidst/issues/112)、[#119](https://github.com/Polalalabear/amidst/issues/119)、[#121](https://github.com/Polalalabear/amidst/issues/121)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#175](https://github.com/Polalalabear/amidst/pull/175)、[#177](https://github.com/Polalalabear/amidst/pull/177)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#194](https://github.com/Polalalabear/amidst/issues/194)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#206](https://github.com/Polalalabear/amidst/issues/206)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#208](https://github.com/Polalalabear/amidst/issues/208)、[#209](https://github.com/Polalalabear/amidst/pull/209)、[#210](https://github.com/Polalalabear/amidst/issues/210)、[#211](https://github.com/Polalalabear/amidst/pull/211)、[#216](https://github.com/Polalalabear/amidst/pull/216)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#243](https://github.com/Polalalabear/amidst/pull/243)、[#257](https://github.com/Polalalabear/amidst/pull/257)、[#277](https://github.com/Polalalabear/amidst/pull/277)、[#300](https://github.com/Polalalabear/amidst/issues/300)、[#247](https://github.com/Polalalabear/amidst/issues/247)、[#273](https://github.com/Polalalabear/amidst/pull/273)、[#291](https://github.com/Polalalabear/amidst/issues/291)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)

## Q3 理解使用者語意

### 已完成（22）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#89](https://github.com/Polalalabear/amidst/issues/89) | Issue | Q3：語意解析測試集與評分器（組員） | — | 已完成關閉（2026-11-08）；原備註：組員 Q3 測試集未交；評分器已併入 staging（#165） |
| [#105](https://github.com/Polalalabear/amidst/issues/105) | Issue | QT-12：Ollama 薄 provider（Q3／Q5 共用） | Q5 | 已完成關閉（2026-10-26）；原備註：Ollama provider 已併入 staging（#140），待審入主線 |
| [#106](https://github.com/Polalalabear/amidst/issues/106) | Issue | QT-13：Q3 解析：規則解析器、LLM 解析與兜底 | — | 已完成關閉（2026-10-26）；原備註：規則解析與兜底已併入 staging（#152）；LLM 解析等 Qwen3（#174、#186） |
| [#140](https://github.com/Polalalabear/amidst/pull/140) | PR | feat(q1q5): audited loopback Ollama provider | Q5 | 已合進主線（第 1 批，2026-10-25） |
| [#146](https://github.com/Polalalabear/amidst/issues/146) | Issue | QT-41：組員出題依據文件（格式、可填資料、找得到／找不到） | Q1 | 已完成關閉（2026-10-26）；原備註：出題指南已併入 staging（#149） |
| [#149](https://github.com/Polalalabear/amidst/pull/149) | PR | docs(evaluation): #146 Q1 Q3 question authoring boundaries | Q1 | 已併入 staging，待審入主線 |
| [#152](https://github.com/Polalalabear/amidst/pull/152) | PR | feat(q1q5): #106 literal Q3 parsing and audited deterministic fallback | Q1、Q2 | 已併入 staging，待審入主線 |
| [#165](https://github.com/Polalalabear/amidst/pull/165) | PR | Q3 human-annotation evaluator with exact pinned source clocks (code only) | — | 已併入 staging，待審入主線 |
| [#174](https://github.com/Polalalabear/amidst/pull/174) | PR | feat(q1q5): pinned Qwen3 runtime, grounded schemas and contention measurements | Q5 | 已併入 staging（`bc26d95`），待審入主線 |
| [#186](https://github.com/Polalalabear/amidst/issues/186) | Issue | 本機 Qwen3：schema／工具流程未通過，原呼叫預算仍逾時 | Q5 | 已完成關閉（2026-11-08）；原備註：Qwen3 schema／工具流程未通過，原呼叫預算逾時；Qwen3 執行環境 #174 已併入 staging |
| [#198](https://github.com/Polalalabear/amidst/issues/198) | Issue | Baseline 前置：最小 Q3 八題候選與獨立審核回收 | — | 已完成關閉（2026-11-01）；原備註：對應 PR #199 已併入 staging；issue 仍開著，是否關閉待確認 |
| [#199](https://github.com/Polalalabear/amidst/pull/199) | PR | docs(q3): 固定最小八題候選與獨立審核模板 | — | 已併入 staging（`57d8f35`），待審入主線 |
| [#204](https://github.com/Polalalabear/amidst/issues/204) | Issue | 完整 baseline 條線 B：核定輸入與 Q3 人審回收 | Q1、Q4 | 已完成關閉（2026-11-01）；原備註：對應 PR #205 已併入 staging；issue 仍開著，是否關閉待確認 |
| [#205](https://github.com/Polalalabear/amidst/pull/205) | PR | Wire reviewed baseline gates and independent Q3 review import | Q1、Q4 | 已併入 staging（`0efda15`），待審入主線 |
| [#221](https://github.com/Polalalabear/amidst/pull/221) | PR | CX-2／#149：補齊組員 CSV 填法與出題邊界 | Q1 | 已併入 staging（`e52ace3`），待審入主線 |
| [#230](https://github.com/Polalalabear/amidst/pull/230) | PR | CX-6：Qwen3 不截斷診斷，完整延遲與 token 收據 | Q5 | 已併入 staging（`7adf60b`），待審入主線 |
| [#236](https://github.com/Polalalabear/amidst/pull/236) | PR | fix(evaluation): enforce D80 return mappings and external query bindings | Q1 | 已併入 staging（`08d7202`），待審入主線 |
| [#239](https://github.com/Polalalabear/amidst/pull/239) | PR | docs：澄清 Q5 離群值與小樣本 p95 | Q5 | 已併入 staging（`7b05211`），待審入主線 |
| [#240](https://github.com/Polalalabear/amidst/pull/240) | PR | docs(q1q3): yyin Q1／Q3 出題包設計稿（D80） | Q1 | 關閉未合併（2026-11-08）；原備註：Draft；yyin Q1／Q3 出題包設計稿（D80）；衝突已解（D88）；head `447da6c`，Claude 審查 NEEDS_CHANGES，已退回 CQ-05 [#284](https://github.com/Polalalabear/amidst/issues/284)（合併順序仍是 #276 → #240，D96-3） |
| [#269](https://github.com/Polalalabear/amidst/pull/269) | PR | docs(evaluation): D86-2 selected-run time defaults in question guide | Q1、Q2 | 已合併 `codex/q1q5-staging`（2026-11-03）；原備註：Draft；D86-2 缺時間預設整段 run 的出題指南（base staging）；Claude 審查 NEEDS_CHANGES，已退回 CQ-06 [#285](https://github.com/Polalalabear/amidst/issues/285) |
| [#284](https://github.com/Polalalabear/amidst/issues/284) | Issue | CQ-05 修 #240：依 Opus 再審與使用者決定（P2-1～P2-4、P3-1～P3-6） | Q1 | 已完成關閉（2026-11-08）；原備註：CQ-05；#240 審查 NEEDS_CHANGES 退回此議題；D96-3 解除排在 CQ-04 之後的限制 |
| [#285](https://github.com/Polalalabear/amidst/issues/285) | Issue | CQ-06 修 #269：刪文件內 Actual output、補 D92-2 與過期句 | Q1、Q2 | 已完成關閉（2026-11-08）；原備註：CQ-06；#269 審查 NEEDS_CHANGES 退回此議題 |

**其他分類中也涉及 Q3 的項目：**
- 已完成：[#202](https://github.com/Polalalabear/amidst/issues/202)、[#203](https://github.com/Polalalabear/amidst/pull/203)、[#86](https://github.com/Polalalabear/amidst/pull/86)、[#88](https://github.com/Polalalabear/amidst/issues/88)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#99](https://github.com/Polalalabear/amidst/issues/99)、[#126](https://github.com/Polalalabear/amidst/pull/126)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#133](https://github.com/Polalalabear/amidst/issues/133)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#173](https://github.com/Polalalabear/amidst/pull/173)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#260](https://github.com/Polalalabear/amidst/pull/260)、[#278](https://github.com/Polalalabear/amidst/pull/278)、[#296](https://github.com/Polalalabear/amidst/issues/296)、[#297](https://github.com/Polalalabear/amidst/issues/297)、[#303](https://github.com/Polalalabear/amidst/issues/303)、[#305](https://github.com/Polalalabear/amidst/pull/305)、[#101](https://github.com/Polalalabear/amidst/issues/101)、[#134](https://github.com/Polalalabear/amidst/pull/134)、[#302](https://github.com/Polalalabear/amidst/issues/302)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#112](https://github.com/Polalalabear/amidst/issues/112)、[#119](https://github.com/Polalalabear/amidst/issues/119)、[#120](https://github.com/Polalalabear/amidst/issues/120)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#176](https://github.com/Polalalabear/amidst/pull/176)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#194](https://github.com/Polalalabear/amidst/issues/194)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#206](https://github.com/Polalalabear/amidst/issues/206)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#257](https://github.com/Polalalabear/amidst/pull/257)、[#277](https://github.com/Polalalabear/amidst/pull/277)、[#300](https://github.com/Polalalabear/amidst/issues/300)、[#147](https://github.com/Polalalabear/amidst/issues/147)、[#151](https://github.com/Polalalabear/amidst/pull/151)、[#214](https://github.com/Polalalabear/amidst/pull/214)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#226](https://github.com/Polalalabear/amidst/pull/226)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)

## Q4 判斷畫面是否含目標

### 已完成（9）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#108](https://github.com/Polalalabear/amidst/issues/108) | Issue | QT-15：Q4 候選畫面證據聚合 | — | 已完成關閉（2026-11-08）；原備註：blocked：Q4 證據 #154 已併入 staging；等無顏色 kit 對齊（#153） |
| [#114](https://github.com/Polalalabear/amidst/issues/114) | Issue | QT-21：HSV 顏色參數提案（r004 preview，Q-19） | Q2 | 已完成關閉（2026-11-08）；原備註：blocked：HSV 參數提案 #158 待 G6 |
| [#123](https://github.com/Polalalabear/amidst/issues/123) | Issue | QT-30：Q4 標註與評估（RT-DETR＋HSV） | — | 已完成關閉（2026-11-08）；原備註：blocked：Q4 標註與評估；評估器已併入 staging（#159） |
| [#128](https://github.com/Polalalabear/amidst/issues/128) | Issue | QT-32：組員 Q4 標註與偵測評估（人工標註） | — | 已完成關閉（2026-11-08）；原備註：組員 Q4 人工標註未交 |
| [#154](https://github.com/Polalalabear/amidst/pull/154) | PR | feat(q1q5): #108 candidate evidence (blocked on no-color kit alignment) | — | 已併入 staging（`cfcf0e0`），待審入主線 |
| [#158](https://github.com/Polalalabear/amidst/pull/158) | PR | HSV RGB proposal and measured ambiguity (G6 pending) | Q2 | 關閉未合併（2026-11-08）；原備註：Draft，HSV 參數待 G6 決定 |
| [#159](https://github.com/Polalalabear/amidst/pull/159) | PR | Q4 frozen claim sampling and human TF evaluator (code only) | — | 已併入 staging，待審入主線 |
| [#167](https://github.com/Polalalabear/amidst/pull/167) | PR | Preserve finite raw detector boxes beyond image boundaries | Q1 | 已併入 staging，待審入主線 |
| [#342](https://github.com/Polalalabear/amidst/issues/342) | Issue | CQ-44（stretch）Q4 正式 T／F 評估 | — | 已完成關閉（2026-11-08）；owner:codex |

**其他分類中也涉及 Q4 的項目：**
- 已完成：[#262](https://github.com/Polalalabear/amidst/pull/262)、[#204](https://github.com/Polalalabear/amidst/issues/204)、[#205](https://github.com/Polalalabear/amidst/pull/205)、[#202](https://github.com/Polalalabear/amidst/issues/202)、[#203](https://github.com/Polalalabear/amidst/pull/203)、[#86](https://github.com/Polalalabear/amidst/pull/86)、[#88](https://github.com/Polalalabear/amidst/issues/88)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#99](https://github.com/Polalalabear/amidst/issues/99)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#153](https://github.com/Polalalabear/amidst/issues/153)、[#161](https://github.com/Polalalabear/amidst/pull/161)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#103](https://github.com/Polalalabear/amidst/issues/103)、[#113](https://github.com/Polalalabear/amidst/issues/113)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#118](https://github.com/Polalalabear/amidst/issues/118)、[#132](https://github.com/Polalalabear/amidst/pull/132)、[#136](https://github.com/Polalalabear/amidst/pull/136)、[#139](https://github.com/Polalalabear/amidst/pull/139)、[#155](https://github.com/Polalalabear/amidst/pull/155)、[#196](https://github.com/Polalalabear/amidst/issues/196)、[#197](https://github.com/Polalalabear/amidst/pull/197)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#121](https://github.com/Polalalabear/amidst/issues/121)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#177](https://github.com/Polalalabear/amidst/pull/177)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#194](https://github.com/Polalalabear/amidst/issues/194)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#206](https://github.com/Polalalabear/amidst/issues/206)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#277](https://github.com/Polalalabear/amidst/pull/277)、[#300](https://github.com/Polalalabear/amidst/issues/300)、[#147](https://github.com/Polalalabear/amidst/issues/147)、[#151](https://github.com/Polalalabear/amidst/pull/151)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#226](https://github.com/Polalalabear/amidst/pull/226)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)

## Q5 決定是否切鏡

### 已完成（20）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#104](https://github.com/Polalalabear/amidst/issues/104) | Issue | QT-11：兩層圖 schema／loader 與 D28 候選排序 | Q2 | 已完成關閉（2026-10-26）；原備註：靜態圖驗證與 D28 候選已併入 staging（#150、#166），待審入主線 |
| [#110](https://github.com/Polalalabear/amidst/issues/110) | Issue | QT-17：Q5 Controller：狀態機與 RULE_ONLY 決定性切鏡 | Q2 | 已完成關閉（2026-11-01）；原備註：blocked：RULE_ONLY 控制器 #169 已併入 staging；等 #145、#153 |
| [#111](https://github.com/Polalalabear/amidst/issues/111) | Issue | QT-18：Q5 AGENT_SEQUENTIAL：typed tools 與有界輪詢 | — | 已完成關閉（2026-11-01）；原備註：Agent #172 已併入 staging；空候選契約缺口 #183 未解 |
| [#116](https://github.com/Polalalabear/amidst/issues/116) | Issue | QT-23：r004 兩層圖資料與出口 ROI（靜態） | Q2 | 已完成關閉（2026-11-08）；原備註：blocked：兩層圖與出口 ROI #163（Draft）待 G4 |
| [#117](https://github.com/Polalalabear/amidst/issues/117) | Issue | QT-24：r004 靜態圖獨立檢查（K7 類型） | Q2 | 已完成關閉（2026-11-08）；原備註：收據已出；圖 v3（#227、#235）已併入 staging，G4 未核 |
| [#129](https://github.com/Polalalabear/amidst/issues/129) | Issue | QT-33：組員 Q5 切鏡評估器 | — | 已取消（D96-4，2026-10-27，CLOSED／NOT_PLANNED）：組員之後當評測者，先寫答案會失去獨立性，Q5 參考答案改由我方從凍結劇本產生；原備註：組員 Q5 情境未交；評估器已併入 staging（#160） |
| [#150](https://github.com/Polalalabear/amidst/pull/150) | PR | feat(q1q5): #104 pinned static graph validation and D28 candidates | Q2 | 已併入 staging，待審入主線 |
| [#160](https://github.com/Polalalabear/amidst/pull/160) | PR | Q5 evaluator verifies frozen outputs before reading evaluation script (code only) | — | 已併入 staging，待審入主線 |
| [#163](https://github.com/Polalalabear/amidst/pull/163) | PR | r004 static graph and eight exit ROI proposals (G4 pending) | Q2 | 關閉未合併（2026-11-01）；原備註：Draft，待 G4；圖 v3（#227、#235）已併入 staging；D88 決定先留著，是否關閉待確認 |
| [#166](https://github.com/Polalalabear/amidst/pull/166) | PR | Restrict candidate run cameras before D28 ranking and top-k | Q2 | 已併入 staging，待審入主線 |
| [#169](https://github.com/Polalalabear/amidst/pull/169) | PR | Q5 RULE_ONLY controller（依 #144 提案；blocked #145/#153） | Q2 | 已併入 staging（`efad835`），待審入主線 |
| [#172](https://github.com/Polalalabear/amidst/pull/172) | PR | feat(q5): sequential Agent, versioned guidance profiles and exact replay | — | 已併入 staging（`c0a1ce3`），待審入主線 |
| [#184](https://github.com/Polalalabear/amidst/issues/184) | Issue | Q5 雙模式工程比較：後端 FOUND／LOST 與 Agent 候選決策 | Q2 | 已完成關閉（2026-11-01）；原備註：Q5 雙模式比較，載體 #185 已併入 staging |
| [#185](https://github.com/Polalalabear/amidst/pull/185) | PR | feat(q1q5): event-mode comparison and reproducible baseline telemetry | Q2 | 已併入 staging（`d8e6935`），待審入主線 |
| [#189](https://github.com/Polalalabear/amidst/pull/189) | PR | Q5：As-Is Statechart 與獨立 Journal Invariants 驗證 | — | 關閉未合併（2026-11-08）；原備註：Draft（10-23 新增），Q5 As-Is 狀態圖與 journal 不變量檢查 |
| [#202](https://github.com/Polalalabear/amidst/issues/202) | Issue | 完整 baseline 條線 A：同源 RGB→真 RT-DETR→Qwen／RULE／replay | Q2、Q3、Q4 | 已完成關閉（2026-11-08）；原備註：對應 PR #203 已併入 staging；issue 仍開著，是否關閉待確認 |
| [#203](https://github.com/Polalalabear/amidst/pull/203) | PR | Connect same RGB detector index to Qwen/RULE baseline | Q2、Q3、Q4 | 已併入 staging（`10e94d6`），待審入主線 |
| [#218](https://github.com/Polalalabear/amidst/issues/218) | Issue | [Q2／Q5] 同鏡頭暫失後接不回：漏檢即暫失、回原鏡頭只比對凍結框（#216 審查發現） | Q2 | 已完成關閉（2026-11-08）；原備註：同鏡頭暫失後接不回；D90-1：暫失 ≥ 1.8 s 歸 Line 2；P1 逐格診斷 #262 已併入 staging；issue 仍開著，是否關閉待確認 |
| [#222](https://github.com/Polalalabear/amidst/pull/222) | PR | CX-2／#160：Q5 拒絕空覆蓋得分，分列決策來源 | — | 已併入 staging（`0043097`），待審入主線 |
| [#229](https://github.com/Polalalabear/amidst/pull/229) | PR | docs(q5): Q5 逐事件決策窗（D79 核定版） | — | 已合併主線（`f5168f6`，2026-10-26）；D79 核定的決策窗文件 |

**其他分類中也涉及 Q5 的項目：**
- 已完成：[#262](https://github.com/Polalalabear/amidst/pull/262)、[#105](https://github.com/Polalalabear/amidst/issues/105)、[#140](https://github.com/Polalalabear/amidst/pull/140)、[#174](https://github.com/Polalalabear/amidst/pull/174)、[#186](https://github.com/Polalalabear/amidst/issues/186)、[#230](https://github.com/Polalalabear/amidst/pull/230)、[#239](https://github.com/Polalalabear/amidst/pull/239)、[#86](https://github.com/Polalalabear/amidst/pull/86)、[#88](https://github.com/Polalalabear/amidst/issues/88)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#95](https://github.com/Polalalabear/amidst/issues/95)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#99](https://github.com/Polalalabear/amidst/issues/99)、[#125](https://github.com/Polalalabear/amidst/pull/125)、[#126](https://github.com/Polalalabear/amidst/pull/126)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#161](https://github.com/Polalalabear/amidst/pull/161)、[#168](https://github.com/Polalalabear/amidst/pull/168)、[#170](https://github.com/Polalalabear/amidst/issues/170)、[#171](https://github.com/Polalalabear/amidst/pull/171)、[#178](https://github.com/Polalalabear/amidst/issues/178)、[#183](https://github.com/Polalalabear/amidst/issues/183)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#132](https://github.com/Polalalabear/amidst/pull/132)、[#187](https://github.com/Polalalabear/amidst/pull/187)、[#227](https://github.com/Polalalabear/amidst/pull/227)、[#235](https://github.com/Polalalabear/amidst/pull/235)、[#238](https://github.com/Polalalabear/amidst/pull/238)、[#253](https://github.com/Polalalabear/amidst/pull/253)、[#254](https://github.com/Polalalabear/amidst/pull/254)、[#256](https://github.com/Polalalabear/amidst/pull/256)、[#259](https://github.com/Polalalabear/amidst/pull/259)、[#275](https://github.com/Polalalabear/amidst/pull/275)、[#280](https://github.com/Polalalabear/amidst/issues/280)、[#281](https://github.com/Polalalabear/amidst/issues/281)、[#282](https://github.com/Polalalabear/amidst/issues/282)、[#294](https://github.com/Polalalabear/amidst/pull/294)、[#295](https://github.com/Polalalabear/amidst/pull/295)、[#298](https://github.com/Polalalabear/amidst/issues/298)、[#299](https://github.com/Polalalabear/amidst/issues/299)、[#301](https://github.com/Polalalabear/amidst/issues/301)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#121](https://github.com/Polalalabear/amidst/issues/121)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#177](https://github.com/Polalalabear/amidst/pull/177)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#194](https://github.com/Polalalabear/amidst/issues/194)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#206](https://github.com/Polalalabear/amidst/issues/206)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#208](https://github.com/Polalalabear/amidst/issues/208)、[#209](https://github.com/Polalalabear/amidst/pull/209)、[#210](https://github.com/Polalalabear/amidst/issues/210)、[#211](https://github.com/Polalalabear/amidst/pull/211)、[#216](https://github.com/Polalalabear/amidst/pull/216)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#277](https://github.com/Polalalabear/amidst/pull/277)、[#300](https://github.com/Polalalabear/amidst/issues/300)、[#244](https://github.com/Polalalabear/amidst/issues/244)、[#245](https://github.com/Polalalabear/amidst/issues/245)、[#246](https://github.com/Polalalabear/amidst/issues/246)、[#248](https://github.com/Polalalabear/amidst/issues/248)、[#249](https://github.com/Polalalabear/amidst/issues/249)、[#251](https://github.com/Polalalabear/amidst/issues/251)、[#255](https://github.com/Polalalabear/amidst/pull/255)、[#258](https://github.com/Polalalabear/amidst/pull/258)、[#261](https://github.com/Polalalabear/amidst/pull/261)、[#266](https://github.com/Polalalabear/amidst/pull/266)、[#271](https://github.com/Polalalabear/amidst/pull/271)、[#272](https://github.com/Polalalabear/amidst/pull/272)、[#274](https://github.com/Polalalabear/amidst/pull/274)、[#287](https://github.com/Polalalabear/amidst/issues/287)、[#288](https://github.com/Polalalabear/amidst/issues/288)、[#289](https://github.com/Polalalabear/amidst/issues/289)、[#290](https://github.com/Polalalabear/amidst/issues/290)、[#293](https://github.com/Polalalabear/amidst/issues/293)、[#304](https://github.com/Polalalabear/amidst/issues/304)、[#214](https://github.com/Polalalabear/amidst/pull/214)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)

## 共用：契約、規則、參數與一致性檢查

### 已完成（44）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#86](https://github.com/Polalalabear/amidst/pull/86) | PR | docs(contracts): Q1–Q5 first-demo contract v1 draft (Q1_Q2_FIRST_DEMO_V1) — do not merge | Q1、Q2、Q3、Q4、Q5 | 已合併主線 |
| [#88](https://github.com/Polalalabear/amidst/issues/88) | Issue | QA：Q1–Q5 第一版計畫與契約 #86 核准 | Q1、Q2、Q3、Q4、Q5 | 已完成關閉（2026-11-08）；原備註：D65 已核准，#86、#92 已合併；待確認是否關閉 |
| [#92](https://github.com/Polalalabear/amidst/pull/92) | PR | docs: Q1–Q5 first demo plan, D64 gates and contract review | Q1、Q2、Q3、Q4、Q5 | 已合併主線 |
| [#94](https://github.com/Polalalabear/amidst/issues/94) | Issue | QT-01：契約 #86 定稿：處理 Codex 7 項修正與 D64 | Q1、Q2、Q3、Q4、Q5 | 已完成 |
| [#95](https://github.com/Polalalabear/amidst/issues/95) | Issue | QT-02：DEVELOPMENT_RULES：Q1–Q5 Agent 有界例外條文（D64） | Q5 | 已完成關閉（2026-10-26）；條文已由 #125 合入主線 |
| [#96](https://github.com/Polalalabear/amidst/issues/96) | Issue | QT-03：審查 Codex 修訂稿 #92 | Q1、Q2、Q3、Q4、Q5 | 已完成 |
| [#98](https://github.com/Polalalabear/amidst/issues/98) | Issue | QT-05：§11 參數組 v1 提案（HSV 除外） | Q1、Q2、Q3、Q5 | 已完成關閉（2026-11-01）；原備註：§11 參數組已部分綁定（#142，staging） |
| [#99](https://github.com/Polalalabear/amidst/issues/99) | Issue | QT-06：Q1–Q5 合約符合性測試包 | Q1、Q2、Q3、Q4、Q5 | 已完成關閉（2026-11-08）；原備註：標 blocked；一致性檢查包 #127 仍為 Draft（AC7 未過） |
| [#125](https://github.com/Polalalabear/amidst/pull/125) | PR | docs(rules): D64 Q1–Q5 Agent camera-switch exception (draft, do not merge) | Q5 | 已合併主線 |
| [#126](https://github.com/Polalalabear/amidst/pull/126) | PR | docs: propose bounded Q1-Q5 search and fallback budgets | Q1、Q3、Q5 | 關閉未合併（2026-10-25 09:54Z）；D67 初始值的記載不變 |
| [#127](https://github.com/Polalalabear/amidst/pull/127) | PR | feat(evaluation): Q1–Q5 contract conformance kit (draft) | Q1、Q2、Q3、Q4、Q5 | 已合併 `mainline/q1q5`（2026-11-03）；原備註：一致性檢查包（Draft，head `e1415f3`，2026-10-28，Claude 審查 PASS_WITH_NOTES）；AC7 仍未通過（NOT_ACCEPTED）；重錄見 [#277](https://github.com/Polalalabear/amidst/pull/277)，收尾見 CQ-19 [#300](https://github.com/Polalalabear/amidst/issues/300) |
| [#133](https://github.com/Polalalabear/amidst/issues/133) | Issue | Conformance kit: CLOCK_MAPPING_RULES rejects an explicit DST fold offset | Q1、Q2、Q3 | 已完成關閉（2026-11-01）；原備註：kit 問題：DST fold 偏移被拒，尚無修正 PR |
| [#135](https://github.com/Polalalabear/amidst/pull/135) | PR | docs(contracts): Q1–Q5 契約釐清版（#127 回報，不改語意與數值） | Q1、Q2、Q3、Q4、Q5 | 關閉未合併（2026-10-26）；已由 #237 取代（`83da40f`，盤點留言） |
| [#142](https://github.com/Polalalabear/amidst/pull/142) | PR | docs(q1q5): bind D65 D67 D68 initial parameters and unresolved fields | Q1、Q2、Q3、Q4、Q5 | 已併入 staging，待審入主線 |
| [#144](https://github.com/Polalalabear/amidst/issues/144) | Issue | QT-39：契約 #135 補完（寫入 D69＋處理 Codex 跳過原因） | Q1、Q2、Q3、Q4、Q5 | 已完成關閉（2026-11-08）；原備註：§14 選項已併入 staging（#148、#161、#168、#171、#173、#179），待寫回 #135 |
| [#145](https://github.com/Polalalabear/amidst/issues/145) | Issue | QT-40：#127 測試包對齊契約 #135 最終版並合入 | Q1、Q2、Q3、Q4、Q5 | 已完成關閉（2026-11-08）；原備註：blocked：kit 對齊契約最終版 |
| [#148](https://github.com/Polalalabear/amidst/pull/148) | PR | docs(contracts): #144 D69 D71 decisions and remaining wire proposals | Q1、Q2、Q3、Q4、Q5 | 已併入 staging，待審入主線 |
| [#153](https://github.com/Polalalabear/amidst/issues/153) | Issue | #127/#145: no-color Q4 MATCH_STRONG with null verdict fails presence invariant | Q4 | 已完成關閉（2026-11-08）；原備註：kit 問題：無顏色 Q4 的 null verdict 被拒，阻擋 #154 |
| [#156](https://github.com/Polalalabear/amidst/issues/156) | Issue | #127 Q1_RESULT_ORDER：最後一頁錯將 results_total 視為當頁筆數 | Q1 | 已完成關閉（2026-11-08）；原備註：kit 問題：Q1 最後一頁筆數判錯，阻擋 #157 |
| [#161](https://github.com/Polalalabear/amidst/pull/161) | PR | Contract §14: evaluation, media grants and HSV options (PROPOSED only) | Q1、Q4、Q5 | 已併入 staging，待審入主線 |
| [#168](https://github.com/Polalalabear/amidst/pull/168) | PR | Contract §14: controller journal and manual-control options (PROPOSED) | Q5 | 已併入 staging，待審入主線 |
| [#170](https://github.com/Polalalabear/amidst/issues/170) | Issue | Q5 conformance：D69 link 誤分類、失敗 digest 與正常候選耗盡的 Agent flags | Q5 | 已完成關閉（2026-11-08）；原備註：kit 問題：Q5 Agent flags 與 link 分類 |
| [#171](https://github.com/Polalalabear/amidst/pull/171) | PR | Contract §14: Agent trace and failure-provenance options (PROPOSED) | Q5 | 已併入 staging，待審入主線 |
| [#173](https://github.com/Polalalabear/amidst/pull/173) | PR | Contract §14: Q transport and parse-lineage options (PROPOSED) | Q1、Q2、Q3 | 已併入 staging，待審入主線 |
| [#178](https://github.com/Polalalabear/amidst/issues/178) | Issue | [#127] 空 decisions／links journal 被 DOCUMENT_LOADABLE 判成未知 schema | Q2、Q5 | 已完成關閉（2026-11-08）；原備註：kit 問題：空 journal 被判成未知 schema |
| [#179](https://github.com/Polalalabear/amidst/pull/179) | PR | 契約 §14：審核 hash 與預期清單隔離選項（依 #144 提案） | — | 已併入 staging，待審入主線 |
| [#183](https://github.com/Polalalabear/amidst/issues/183) | Issue | [契約缺口] 空候選證據無法合法 NEXT_CANDIDATE，阻斷 Agent top-k 輪詢 | Q5 | 已完成關閉（2026-11-01）；原備註：契約缺口：空候選無法 NEXT_CANDIDATE，阻擋 Agent 輪詢 |
| [#219](https://github.com/Polalalabear/amidst/pull/219) | PR | 契約：R1–R8、D73 與 D78 已核定條文 | Q1、Q2、Q3、Q4、Q5 | GitHub 標為 MERGED（base staging，`635a102`）；#237 取代，分支保留 |
| [#220](https://github.com/Polalalabear/amidst/pull/220) | PR | CX-2／#142：fallback 預算明列為效能觀察值 | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`2edd32f`），待審入主線 |
| [#237](https://github.com/Polalalabear/amidst/pull/237) | PR | 契約 B：對齊 D78 audit、D82 stop 與 D80/D81 介面 | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`83da40f`），待審入主線 |
| [#260](https://github.com/Polalalabear/amidst/pull/260) | PR | docs(contract): U37 examples, link v2 note and D86/G4 interface proposals | Q1、Q2、Q3 | 已合併 `codex/q1q5-staging`（2026-11-03）；原備註：Draft；U37 範例、link v2 註記與 D86／G4 介面提案；D92 的 #260-A／C／B 待套用（base staging）；Claude 審查 PASS_WITH_NOTES；D92／零邊 authority 與 G4 回條格式修正見 CQ-16 [#297](https://github.com/Polalalabear/amidst/issues/297) |
| [#278](https://github.com/Polalalabear/amidst/pull/278) | PR | feat(q1q5): add D92 v2 responses and parse provenance | Q1、Q2、Q3 | 已合併 `codex/q1q5-staging`（2026-11-03）；原備註：Draft；D92 的 Q1／Q2／Q3 v2 回應與解析來源（base staging）；Claude 審查 PASS_WITH_NOTES；修正見 CQ-15 [#296](https://github.com/Polalalabear/amidst/issues/296)、CQ-23 [#303](https://github.com/Polalalabear/amidst/issues/303) |
| [#296](https://github.com/Polalalabear/amidst/issues/296) | Issue | CQ-15 修 #278（v2 回應） | Q1、Q2、Q3 | 已完成關閉（2026-11-08）；原備註：CQ-15；對象 #278 |
| [#297](https://github.com/Polalalabear/amidst/issues/297) | Issue | CQ-16 修 #260（D92／零邊 authority，以及 G4 回條格式） | Q1、Q2、Q3 | 已完成關閉（2026-11-08）；原備註：CQ-16；對象 #260 |
| [#303](https://github.com/Polalalabear/amidst/issues/303) | Issue | CQ-23 v2 消費端相容（#278 P2-4） | Q1、Q2、Q3 | 已完成關閉（2026-11-08）；原備註：CQ-23；PR [#305](https://github.com/Polalalabear/amidst/pull/305)（Draft，head `e23ef16`，Claude 審查 NEEDS_CHANGES） |
| [#305](https://github.com/Polalalabear/amidst/pull/305) | PR | CQ-23：Q1／Q2／Q3 v2 消費端相容與預設時間計分隔離 | Q1、Q2、Q3 | 已合併 `codex/q1q5-staging`（2026-11-03）；原備註：Draft；CQ-23 的 v2 消費端相容與預設時間計分隔離（base staging）；Claude 審查 NEEDS_CHANGES |
| [#307](https://github.com/Polalalabear/amidst/issues/307) | Issue | ARCH-T 架構守門腳本 check_architecture_guard.py（test-first） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#348](https://github.com/Polalalabear/amidst/pull/348) | PR | CQ-02: D101 選項 A 選定副本與重算 G4 hash（尚未生效） | — | 關閉未合併（2026-11-08） |
| [#351](https://github.com/Polalalabear/amidst/pull/351) | PR | CQ-21a: G4 回條綁定十一條補充草案（待 U8） | — | 關閉未合併（2026-11-08） |
| [#352](https://github.com/Polalalabear/amidst/pull/352) | PR | CQ-21-T: 合成 G4 收據檢查器與 fail-closed 驗收測試 | — | 關閉未合併（2026-11-08） |
| [#386](https://github.com/Polalalabear/amidst/pull/386) | PR | G4-A-T：D101 選項 A 選定副本檢查器與測試（#348 第 2 步） | — | 關閉未合併（2026-11-08） |
| [#391](https://github.com/Polalalabear/amidst/pull/391) | PR | FEAT-7: source-bound architecture guard and fixed-head acceptance | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#393](https://github.com/Polalalabear/amidst/pull/393) | PR | FEAT-6: v2／rc5 成對整合與 176 份凍結重跑（PARTIAL） | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#410](https://github.com/Polalalabear/amidst/pull/410) | PR | docs(contracts): PROPOSED core search/track contract + acceptance tests (D126) | — | 關閉未合併（2026-11-08） |

## 共用：r004 場景、資料、索引與儲存

### 已完成（51）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#75](https://github.com/Polalalabear/amidst/pull/75) | PR | Add controlled scene safe loaders and v2 fixture API skeletons | Q2 | 已合併主線 |
| [#80](https://github.com/Polalalabear/amidst/pull/80) | PR | feat(v2): 接入 A／B1 真實 RGB 與 scoped media token（2a） | Q2 | 已合併主線 |
| [#97](https://github.com/Polalalabear/amidst/issues/97) | Issue | QT-04：r004 修改表提案定稿（文件） | Q1、Q2、Q4、Q5 | 已完成關閉（2026-11-01）；原備註：r004 修改表提案 #132 已併入 staging；r004 v2 審查包 #187 已併入 staging |
| [#101](https://github.com/Polalalabear/amidst/issues/101) | Issue | QT-08：時間對應模組（來源時鐘 ↔ 牆鐘） | Q1、Q2、Q3 | 已完成 |
| [#102](https://github.com/Polalalabear/amidst/issues/102) | Issue | QT-09：store 介面（版本化 JSON＋每 run JSONL） | Q1、Q2 | 已完成關閉（2026-10-26）；原備註：store 已併入 staging（#136），待審入主線 |
| [#103](https://github.com/Polalalabear/amidst/issues/103) | Issue | QT-10：偵測索引產生器（RT-DETR＋上半身 HSV） | Q1、Q4 | 已完成關閉（2026-10-26）；原備註：偵測索引產生器與 HSV 證據已併入 staging（#139），待審入主線 |
| [#113](https://github.com/Polalalabear/amidst/issues/113) | Issue | QT-20：r004 建檔、靜態校正匯出與廣角小批 preview | Q1、Q2、Q4 | 已完成關閉（2026-11-01）；原備註：標 blocked（內文寫 needs-auth）；r004 靜態匯出 #155、廣角鏡頭 #162 已併入 staging |
| [#115](https://github.com/Polalalabear/amidst/issues/115) | Issue | QT-22：A4／B4 事件 run 產製與 safe bundle | Q1、Q2、Q4、Q5 | 已完成關閉（2026-11-08）；原備註：標 blocked（內文寫 needs-auth）：A4-1／B4-1 事件 run 待授權；D89 核定 50／42 s，時鐘 #238（已併入 staging）、可行性檢查 #256（Draft） |
| [#118](https://github.com/Polalalabear/amidst/issues/118) | Issue | QT-25：r004 正式偵測索引產製 | Q1、Q4 | 已完成關閉（2026-11-08）；原備註：blocked：r004 正式偵測索引，等 #115 |
| [#132](https://github.com/Polalalabear/amidst/pull/132) | PR | docs: propose r004 camera scope and bounded preview plan | Q2、Q4、Q5 | 已合進主線（第 1 批，2026-10-25） |
| [#134](https://github.com/Polalalabear/amidst/pull/134) | PR | feat(q1q5): resolve declared clocks and bounded time coverage | Q1、Q2、Q3 | 已合併主線 |
| [#136](https://github.com/Polalalabear/amidst/pull/136) | PR | Q1–Q5 #102: Pinned JSON/JSONL store with fail-closed metadata access | Q1、Q2、Q4 | 已合進主線（第 1 批，2026-10-25） |
| [#139](https://github.com/Polalalabear/amidst/pull/139) | PR | Q1–Q5 #103: Offline source-pinned index producer and parameterized HSV evidence | Q1、Q4 | 已合進主線（第 1 批，2026-10-25） |
| [#155](https://github.com/Polalalabear/amidst/pull/155) | PR | docs(r004): #113 static export and measured 45-frame preview receipt | Q1、Q2、Q4 | 已併入 staging，待審入主線 |
| [#162](https://github.com/Polalalabear/amidst/pull/162) | PR | r004 receipt: user selects 90 degree CAM_WIDE | — | 已併入 staging，待審入主線 |
| [#187](https://github.com/Polalalabear/amidst/pull/187) | PR | r004 v2: source-bound entry/exit zones and portal review packet | Q2、Q5 | 已併入 staging（`9402c91`），待審入主線 |
| [#196](https://github.com/Polalalabear/amidst/issues/196) | Issue | Baseline 前置：r004 產製設定與 pinned 索引入口 | Q1、Q4 | 已完成關閉（盤點留言） |
| [#197](https://github.com/Polalalabear/amidst/pull/197) | PR | feat(q1q5): r004 pinned 產製設定與索引入口 | Q1、Q4 | 已併入 staging（`de7046a`），待審入主線 |
| [#212](https://github.com/Polalalabear/amidst/pull/212) | PR | docs(r004): 更新 yyin 回收與 baseline 凍結前狀態，交 Claude 審查 | — | 關閉未合併（2026-10-27，盤點）；head 已含於 staging（經 #231 的 merge `680ca35`），分支保留 |
| [#227](https://github.com/Polalalabear/amidst/pull/227) | PR | CX-3：r004 圖 v3、26 ROI 與 56 有向對收據（G4 未核） | Q2、Q5 | 圖 v3、26 ROI、56 有向對收據；G4 未核；已併入 staging（`3cc0532`），待審入主線 |
| [#235](https://github.com/Polalalabear/amidst/pull/235) | PR | fix(r004): align W2 paths and add D81 corridor transitions | Q2、Q5 | 已併入 staging（`747bdfe`），待審入主線 |
| [#238](https://github.com/Polalalabear/amidst/pull/238) | PR | docs(r004): D89 50s/42s clocks, D84 catalog freeze and run registrations | Q2、Q5 | D89 時鐘（A4 50 s／B4 42 s）、D84 目錄凍結與 run 註冊；已併入 staging（`001cbcf`），待審入主線 |
| [#253](https://github.com/Polalalabear/amidst/pull/253) | PR | docs(evaluation): r004 A4／B4 情境卡 v1（D87） | Q5 | 已合併主線（`0edd8a3`，2026-10-27） |
| [#254](https://github.com/Polalalabear/amidst/pull/254) | PR | feat(evaluation): r004 A4-1/B4-1 劇本計畫 → q5-evaluation-script.v1 adapter | Q5 | 已合併 `codex/q1q5-staging`（2026-11-03）；原備註：Draft；r004 A4-1／B4-1 劇本計畫 → `q5-evaluation-script.v1` adapter（base staging）；Claude 審查 PASS_WITH_NOTES；adapter 修正見 CQ-20 [#301](https://github.com/Polalalabear/amidst/issues/301) |
| [#256](https://github.com/Polalalabear/amidst/pull/256) | PR | docs(r004): D89 A4/B4 static feasibility and timing conflicts | Q5 | 已合併 `codex/q1q5-staging`（2026-11-03）；原備註：Draft；D89 A4／B4 靜態可行性與時間衝突；D92 採選項 1（base staging）；已交增量，尚未複審；A4-c2 靜態檢查見 CQ-17 [#298](https://github.com/Polalalabear/amidst/issues/298)（D96-1：先標不計分待驗證） |
| [#259](https://github.com/Polalalabear/amidst/pull/259) | PR | fix(review): finish #235 #236 #234 notes after #231 merge | Q5 | 已併入 staging（`7a33d6d`），待審入主線 |
| [#275](https://github.com/Polalalabear/amidst/pull/275) | PR | docs(r004): unfrozen B4-1 producer script draft with B4-d non-scoring | Q5 | 已合併 `codex/q1q5-staging`（2026-11-03）；原備註：Draft；未凍結的 B4-1 劇本草稿，B4-d 不計分（D92；base staging）；已交增量，尚未複審；B4-1 劇本草稿修正見 CQ-18 [#299](https://github.com/Polalalabear/amidst/issues/299)（D96-1：B4-e 先標不計分待驗證） |
| [#280](https://github.com/Polalalabear/amidst/issues/280) | Issue | CQ-01 yyin 3 題澄清落實到 r004 圖 v3（BRANCH／WIDE 出口、W1↔EXT_CAR） | Q5 | 已完成關閉（2026-11-08）；原備註：CQ-01；PR [#294](https://github.com/Polalalabear/amidst/pull/294)（Draft，head `fc36b91`，Claude 審查 NEEDS_CHANGES） |
| [#281](https://github.com/Polalalabear/amidst/issues/281) | Issue | CQ-02 r004 G4 回條草稿（Codex 起草、Claude 審、使用者核准） | Q5 | 已完成關閉（2026-11-08）；原備註：CQ-02；未開始；依賴 CQ-01 審查通過，核准只能由使用者做 |
| [#282](https://github.com/Polalalabear/amidst/issues/282) | Issue | CQ-03 A4-1 producer-script 草案（UNFROZEN，不渲染） | Q5 | 已完成關閉（2026-11-08）；原備註：CQ-03；PR [#295](https://github.com/Polalalabear/amidst/pull/295)（Draft，head `2011837`，標 needs-claude-review） |
| [#294](https://github.com/Polalalabear/amidst/pull/294) | PR | CQ-01: yyin BRANCH ROI v3_1 與三題缺項收據 | Q5 | 已合併 `codex/q1q5-staging`（2026-11-03）；原備註：Draft；CQ-01 的 yyin BRANCH ROI v3_1 與三題缺項收據（base staging）；Claude 審查 NEEDS_CHANGES |
| [#295](https://github.com/Polalalabear/amidst/pull/295) | PR | CQ-03: A4-1 未凍結劇本草案與 D92 五事件邊界 | Q5 | 已合併 `codex/q1q5-staging`（2026-11-03）；原備註：Draft；CQ-03 的 A4-1 未凍結劇本草案與 D92 五事件邊界（base staging）；標 needs-claude-review |
| [#298](https://github.com/Polalalabear/amidst/issues/298) | Issue | CQ-17 修 #256（A4-c2 靜態檢查） | Q5 | 已完成關閉（2026-11-08）；原備註：CQ-17；對象 #256；D96-1 |
| [#299](https://github.com/Polalalabear/amidst/issues/299) | Issue | CQ-18 修 #275（B4-1 劇本草稿） | Q5 | 已完成關閉（2026-11-08）；原備註：CQ-18；對象 #275；D96-1 |
| [#301](https://github.com/Polalalabear/amidst/issues/301) | Issue | CQ-20 修 #254 adapter | Q5 | 已完成關閉（2026-11-08）；原備註：CQ-20；對象 #254 |
| [#302](https://github.com/Polalalabear/amidst/issues/302) | Issue | CQ-22 N1：yyin 確認題的疊圖 | Q1、Q3 | 已完成關閉（2026-11-08）；原備註：CQ-22 |
| [#310](https://github.com/Polalalabear/amidst/issues/310) | Issue | CQ-24 A4-1／B4-1 劇本凍結候選（依 D96-1 驗證結果） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#311](https://github.com/Polalalabear/amidst/issues/311) | Issue | CX-7-T 事件 run 與 safe bundle 產出檢查器（#115 CX-7 與複雜事件渲染共用） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#312](https://github.com/Polalalabear/amidst/issues/312) | Issue | QT-25-T 正式偵測索引收據檢查器（#118 與複雜事件索引共用） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#313](https://github.com/Polalalabear/amidst/issues/313) | Issue | CX-8-T 正式 baseline 凍結收據檢查器（#194／#202 與複雜事件執行共用） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#314](https://github.com/Polalalabear/amidst/issues/314) | Issue | CQ-25 P2 正式 baseline 評估（CL-5）：Baseline 評分與報告 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#315](https://github.com/Polalalabear/amidst/issues/315) | Issue | CQ-25-T P2 baseline 評分報告的驗收測試與重算腳本 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#316](https://github.com/Polalalabear/amidst/issues/316) | Issue | CQ-26 r004 空場景可出題物件清單（每台鏡頭看得到哪些車輛與家具） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#350](https://github.com/Polalalabear/amidst/pull/350) | PR | CQ-26: r004 空場景可出題物件清單 | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#353](https://github.com/Polalalabear/amidst/pull/353) | PR | CX-7-T：事件 run 與 safe bundle 合成檢查器 | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#354](https://github.com/Polalalabear/amidst/pull/354) | PR | CQ-24：A4/B4 待核劇本凍結候選與檢查器 | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#355](https://github.com/Polalalabear/amidst/pull/355) | PR | CX-8-T：baseline 凍結與錄製 bytes 合成檢查器 | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#356](https://github.com/Polalalabear/amidst/pull/356) | PR | CQ-25-T：SYNTHETIC P2 報告重算檢查器與驗收測試 | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#357](https://github.com/Polalalabear/amidst/pull/357) | PR | test(qt25): SYNTHETIC 偵測索引收據與逐格 coverage 檢查 | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#394](https://github.com/Polalalabear/amidst/pull/394) | PR | FEAT-1: integrate frozen baseline checks and fix private-token rejection | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#402](https://github.com/Polalalabear/amidst/pull/402) | PR | D119: A4/B4 production safe bundle wire 與 #118 產製前計畫 | — | 已合併 `mainline/q1q5`（2026-11-04） |

## 共用：工作台、HTTP 與 Demo

### 已完成（62）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#72](https://github.com/Polalalabear/amidst/pull/72) | PR | docs(agents): 工作台 v2 設計（功能保留矩陣、資訊架構、視覺規範、實作計畫） | — | 關閉未合併 |
| [#74](https://github.com/Polalalabear/amidst/pull/74) | PR | feat(workbench-v2): V2-1 外框、token、store、時鐘 | — | 已合併主線 |
| [#79](https://github.com/Polalalabear/amidst/pull/79) | PR | feat(workbench-v2): V2-2 api、不確定度驗證與 SYNTHETIC fixture | — | 已合併主線 |
| [#90](https://github.com/Polalalabear/amidst/pull/90) | PR | docs(agents): workbench-v2 Q1–Q5 畫面設計與審核模式（draft）— do not merge | Q1、Q2、Q3、Q4、Q5 | 已合併主線（merge commit `19fd4f5`，2026-10-25 10:00Z）；原標示 do-not-merge，合併依據待 #93 核對 |
| [#100](https://github.com/Polalalabear/amidst/issues/100) | Issue | QT-07：workbench-v2 底座合入 mainline（U-1：#74、#79、#71） | Q1、Q2 | 已完成 |
| [#112](https://github.com/Polalalabear/amidst/issues/112) | Issue | QT-19：Q 線 HTTP 端點與 #80 接線（R-1–R-7） | Q1、Q2、Q3 | 已完成關閉（2026-11-01）；原備註：blocked：Q 線 HTTP 端點與 #80 接線；本機模型接線 #174 已併入 staging |
| [#119](https://github.com/Polalalabear/amidst/issues/119) | Issue | QT-26：workbench-v2 T1：Q 資料層與外框改裝 | Q1、Q2、Q3 | 已完成關閉（2026-10-26）；對應 PR #175 已併入 staging |
| [#120](https://github.com/Polalalabear/amidst/issues/120) | Issue | QT-27：workbench-v2 T2：Q3 查詢列與 Q1 結果牆 | Q1、Q3 | 已完成關閉（2026-10-26）；對應 PR #176 已併入 staging |
| [#121](https://github.com/Polalalabear/amidst/issues/121) | Issue | QT-28：workbench-v2 T3：Q2 主畫面、時間軸、Q4 證據、Q5 逐步紀錄 | Q2、Q4、Q5 | 已完成關閉（2026-10-26）；對應 PR #177 已併入 staging |
| [#122](https://github.com/Polalalabear/amidst/issues/122) | Issue | QT-29：workbench-v2 T4：審核模式 | Q1、Q2、Q3、Q4、Q5 | 已完成關閉（2026-10-26）；對應 PR #180 已併入 staging |
| [#124](https://github.com/Polalalabear/amidst/issues/124) | Issue | QT-31：Q1–Q5 端到端 browser acceptance 與 Demo 腳本 | Q1、Q2、Q3、Q4、Q5 | 已完成關閉（2026-11-08）；原備註：blocked：端到端瀏覽器驗收；Demo 腳本草稿已併入 staging（#181、#182） |
| [#130](https://github.com/Polalalabear/amidst/issues/130) | Issue | QT-34：組員 瀏覽器驗收（人工操作） | Q1、Q2、Q3、Q4、Q5 | 已完成關閉（2026-11-08）；原備註：組員瀏覽器驗收未開始 |
| [#175](https://github.com/Polalalabear/amidst/pull/175) | PR | workbench T1：Q 資料層與外框（依 #144 提案） | Q1、Q2 | 已併入 staging（`a0a4398`），待審入主線 |
| [#176](https://github.com/Polalalabear/amidst/pull/176) | PR | workbench T2：Q3 直接執行與 Q1 三區結果牆（依 #144 提案） | Q1、Q3 | 已併入 staging（`601e69b`），待審入主線 |
| [#177](https://github.com/Polalalabear/amidst/pull/177) | PR | workbench T3：多鏡頭、事件硬切與審核紀錄（依 #144 提案） | Q2、Q4、Q5 | 已併入 staging（`4893f49`），待審入主線 |
| [#180](https://github.com/Polalalabear/amidst/pull/180) | PR | workbench T4：唯讀審核、凍結 pins 與匯出隔離（依 #144 提案） | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`15e27d2`），待審入主線 |
| [#181](https://github.com/Polalalabear/amidst/pull/181) | PR | Demo 腳本草稿與可重現工程啟動指令（依 #144 提案） | Q1、Q2、Q3、Q4、Q5 | 已併入 staging，待審入主線 |
| [#182](https://github.com/Polalalabear/amidst/pull/182) | PR | Demo 草稿：固定最終 replay provenance 工程包（依 #144 提案） | Q1、Q2、Q3、Q4、Q5 | 已併入 staging，待審入主線 |
| [#192](https://github.com/Polalalabear/amidst/issues/192) | Issue | Demo v1：最小 baseline 測試規格與工程配置（Qwen3＋RT-DETR） | Q1、Q2、Q3、Q4、Q5 | baseline 最小規格；已完成關閉（盤點留言） |
| [#193](https://github.com/Polalalabear/amidst/pull/193) | PR | docs(q1q5): 最小 baseline v1 協定與工程配置 | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`89bd04c`），待審入主線 |
| [#194](https://github.com/Polalalabear/amidst/issues/194) | Issue | Demo v1：baseline 執行入口、逐次紀錄／replay 與正式產製預檢 | Q1、Q2、Q3、Q4、Q5 | 已完成關閉（2026-11-08）；原備註：對應 PR #195 已併入 staging；issue 仍開著，是否關閉待確認 |
| [#195](https://github.com/Polalalabear/amidst/pull/195) | PR | feat(q1q5): baseline 工程入口、完整錄製／replay 與產製預檢 | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`816650c`），待審入主線 |
| [#200](https://github.com/Polalalabear/amidst/issues/200) | Issue | Baseline 前置總驗收：可重建來源、真本機 smoke 與決策清單 | Q1、Q2、Q3、Q4、Q5 | 已完成關閉（2026-11-01）；原備註：對應 PR #201 已併入 staging；issue 仍開著，是否關閉待確認 |
| [#201](https://github.com/Polalalabear/amidst/pull/201) | PR | feat(q1q5): 可重建 baseline 前置、publication 修正與一次驗收 | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`9821249`），待審入主線 |
| [#206](https://github.com/Polalalabear/amidst/issues/206) | Issue | 完整 baseline 條線 C：工作台、重現入口與一次驗收 | Q1、Q2、Q3、Q4、Q5 | 已完成關閉（2026-11-01）；原備註：對應 PR #207 已併入 staging；issue 仍開著，是否關閉待確認 |
| [#207](https://github.com/Polalalabear/amidst/pull/207) | PR | Deliver reproducible linked baseline and Workbench acceptance | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`b8a1cd0`），待審入主線 |
| [#208](https://github.com/Polalalabear/amidst/issues/208) | Issue | 修正工作台黑畫面與完整播放，延長工程事件並量測連續性 | Q2、Q5 | 已完成關閉（2026-11-01）；原備註：對應 PR #209 關閉未合併（head 已含於 staging，經 #231）；issue 仍開著，是否關閉待確認 |
| [#209](https://github.com/Polalalabear/amidst/pull/209) | PR | 修正黑畫面、6秒工程事件與播放連續性量測 | Q2、Q5 | 關閉未合併（2026-10-27，盤點）；head 已含於 staging（經 #231 的 merge `680ca35`），分支保留 |
| [#210](https://github.com/Polalalabear/amidst/issues/210) | Issue | 動態 RGB baseline：8秒逐格人物、工作台有界快取與審查前完整驗收 | Q2、Q5 | 已完成關閉（2026-11-01）；原備註：對應 PR #211 關閉未合併（head 已含於 staging，經 #231）；issue 仍開著，是否關閉待確認 |
| [#211](https://github.com/Polalalabear/amidst/pull/211) | PR | 真動態8秒baseline：逐格RGB、有界播放與完整工程驗收 | Q2、Q5 | 關閉未合併（2026-10-27，盤點）；head 已含於 staging（經 #231 的 merge `680ca35`），分支保留 |
| [#216](https://github.com/Polalalabear/amidst/pull/216) | PR | A→B 約3–5秒盲區審查：逐格數據、俯視圖與重現入口 | Q2、Q5 | 關閉未合併（2026-10-27，盤點）；head 已含於 staging（經 #231 的 merge `680ca35`），分支保留 |
| [#231](https://github.com/Polalalabear/amidst/pull/231) | PR | baseline整合：完成11項重審修正與契約B接線 | Q1、Q2、Q3、Q4、Q5 | 已併入 staging（`680ca35`），待審入主線 |
| [#233](https://github.com/Polalalabear/amidst/pull/233) | PR | CX-5：P1 一行啟動、真實選取與8秒播放實測（AC7仍待rc2） | Q1、Q2、Q3、Q4、Q5 | CX-5：P1 一行啟動與 8 秒播放；AC7 另依 #127；已併入 staging（`66762ab`），待審入主線 |
| [#234](https://github.com/Polalalabear/amidst/pull/234) | PR | CX-10：可重現 LOCAL P1 測試包、相對路徑與瀏覽器回交表 | Q1、Q2、Q3、Q4、Q5 | CX-10：LOCAL P1 可攜測試包 v4；已併入 staging（`9c052fb`），待審入主線 |
| [#242](https://github.com/Polalalabear/amidst/pull/242) | PR | fix(recordings): rc4 scope migration and public locator cleanup; rerun after B1 merge | Q1、Q2、Q3、Q4、Q5 | rc4 重錄與公開路徑清理；已併入 staging（`d6a9e21`）；fresh recordings=0，AC7 仍 NOT_ACCEPTED（Codex 回報） |
| [#243](https://github.com/Polalalabear/amidst/pull/243) | PR | feat(workbench): Q1 結果牆並排播放與追蹤單畫面預設（D86-3） | Q1、Q2 | 已合併 `codex/q1q5-staging`（2026-11-03）；原備註：Draft；Q1 結果牆並排播放與追蹤單畫面預設（D86-3） |
| [#257](https://github.com/Polalalabear/amidst/pull/257) | PR | fix(q1q5): pin engineering tracking scope for rc4 and Q2 production | Q1、Q2、Q3 | 已併入 staging（`c1d9cbd`），待審入主線 |
| [#277](https://github.com/Polalalabear/amidst/pull/277) | PR | fix(rerecord): pin rc5 and deliver merged-product recordings | Q1、Q2、Q3、Q4、Q5 | 已合併 `codex/q1q5-staging`（2026-11-03）；原備註：Draft；固定 rc5 並交付合併產品的重錄（AC7 缺口，base staging）；Claude 審查 PASS_WITH_NOTES；收尾見 CQ-19 [#300](https://github.com/Polalalabear/amidst/issues/300) |
| [#300](https://github.com/Polalalabear/amidst/issues/300) | Issue | CQ-19 #277 收尾與 AC7 缺口 | Q1、Q2、Q3、Q4、Q5 | 已完成關閉（2026-11-08）；原備註：CQ-19；標 blocked-user；對象 #277 |
| [#337](https://github.com/Polalalabear/amidst/issues/337) | Issue | CQ-40 workbench-v2 demo 模式（逐步導覽、資料來源標示） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#338](https://github.com/Polalalabear/amidst/issues/338) | Issue | CQ-41 demo 一鍵啟動與 fallback（deterministic replay） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#339](https://github.com/Polalalabear/amidst/issues/339) | Issue | CQ-42 demo 彩排紀錄（全流程、計時、fallback 演練） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#340](https://github.com/Polalalabear/amidst/issues/340) | Issue | CQ-42-T demo 腳本與彩排紀錄的檢查器（#124 與 CQ-42 共用） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#341](https://github.com/Polalalabear/amidst/issues/341) | Issue | CQ-43 demo 組成收據（11/01 實際跑的每個 PR head 與 pins） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#344](https://github.com/Polalalabear/amidst/issues/344) | Issue | CQ-46（stretch）Windows 啟動腳本 start.bat（主包、評測包、可攜包） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#346](https://github.com/Polalalabear/amidst/issues/346) | Issue | 完整 demo 驗收清單（11/01，使用者逐項驗收） | — | 已完成關閉（2026-11-08） |
| [#368](https://github.com/Polalalabear/amidst/pull/368) | PR | CQ-42-T: demo 腳本與彩排紀錄格式檢查器 | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#377](https://github.com/Polalalabear/amidst/pull/377) | PR | feat(workbench-v2): 檢索彈窗與 search phase 狀態機 (K-UI-1) | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#378](https://github.com/Polalalabear/amidst/pull/378) | PR | feat(workbench-v2): 監控牆＋後台頁 (K-UI-2) | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#380](https://github.com/Polalalabear/amidst/pull/380) | PR | DEMO_UI_SUPPORT_V1：俯視圖／錄製標題／候選檢視／OpenAI 轉接器規格與 -T，物理預測模組 | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#381](https://github.com/Polalalabear/amidst/pull/381) | PR | feat(workbench-v2): 追蹤模式俯視圖與物理預測虛線 (UI-C) | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#383](https://github.com/Polalalabear/amidst/issues/383) | Issue | FEAT-9 Claude demo UI（檢索流程、監控牆／後台、俯視圖與預測、demo 腳本） | — | 已完成關閉（2026-11-08）；owner:claude |
| [#384](https://github.com/Polalalabear/amidst/pull/384) | PR | docs(demo): QT-31 demo 腳本與 browser acceptance 表（#124，FEAT-9） | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#385](https://github.com/Polalalabear/amidst/pull/385) | PR | FEAT-9: Claude demo UI 整合分支 (#383) | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#392](https://github.com/Polalalabear/amidst/pull/392) | PR | FEAT-5: pinned replay launcher 分段（待 #337／live 交接） | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#400](https://github.com/Polalalabear/amidst/pull/400) | PR | fix(workbench-v2): 俯視圖開啟時不遮擋攝影機畫面 (demo 驗收 #279) | — | 已合併 `mainline/q1q5`（2026-11-03） |
| [#401](https://github.com/Polalalabear/amidst/pull/401) | PR | docs(operations): 2026-11-04 demo 運行手冊 (#279) | — | 已合併 `mainline/q1q5`（2026-11-03） |
| [#403](https://github.com/Polalalabear/amidst/pull/403) | PR | fix(q1q5): allow repeated identical session artifacts | — | 已合併 `mainline/q1q5`（2026-11-03） |
| [#404](https://github.com/Polalalabear/amidst/pull/404) | PR | fix(demo): 攝影機畫格左上角加來源時間標籤（workbench-v2） | — | 已合併 `mainline/q1q5`（2026-11-03） |
| [#405](https://github.com/Polalalabear/amidst/pull/405) | PR | fix(q1q5): 明確回報俯視圖支援路由不可用（demo 後） | — | 已合併 `mainline/q1q5`（2026-11-04） |
| [#406](https://github.com/Polalalabear/amidst/pull/406) | PR | feat(workbench-v2): demo 單純顯示模式 | — | 已合併 `mainline/q1q5`（2026-11-04） |
| [#575](https://github.com/Polalalabear/amidst/pull/575) | PR | chore: retire old workbench and Office launcher (D268, D279) | — | 已合併 `main`（2026-11-18，`59782b1d`）；舊 `frontend/workbench/` 與 Office 啟動器刪除 |

## Line 2 複雜場景

### 已完成（50）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#244](https://github.com/Polalalabear/amidst/issues/244) | Issue | L2-1 Q5 評分器擴充：一窗多次 RETURN、長時間 LOST、重疊接手 | Q5 | 已完成關閉（2026-11-08）；原備註：L2-1 Q5 評分器擴充；設計稿 PR #258（Draft） |
| [#245](https://github.com/Polalalabear/amidst/issues/245) | Issue | L2-2 複雜情境卡 v2 | Q5 | 已完成關閉（2026-11-08）；原備註：L2-2 複雜情境卡 v2；PR #261（Draft） |
| [#246](https://github.com/Polalalabear/amidst/issues/246) | Issue | L2-3 workbench 長時間軸 | Q5 | 已完成關閉（2026-11-08）；原備註：L2-3 workbench 長時間軸；PR #255（Draft） |
| [#247](https://github.com/Polalalabear/amidst/issues/247) | Issue | L2-4 漏檢診斷與偵測改善 | Q2 | 已完成關閉（2026-11-08）；原備註：L2-4 漏檢診斷與偵測改善；PR #273（Draft） |
| [#248](https://github.com/Polalalabear/amidst/issues/248) | Issue | L2-5 linker／Q5 controller：反覆暫失與 LOST 期限契約提案 | Q5 | 已完成關閉（2026-11-08）；原備註：L2-5 linker／controller 契約提案；PR #266（Draft） |
| [#249](https://github.com/Polalalabear/amidst/issues/249) | Issue | L2-6 工程小場景：2–3 台鏡頭、約 30 秒、含一個轉角 | Q5 | 已完成關閉（2026-11-08）；原備註：L2-6 工程小場景；規劃 PR #274（Draft）；渲染延後（D90-3） |
| [#250](https://github.com/Polalalabear/amidst/issues/250) | Issue | L2-7 使用者決策清單 | — | 已完成關閉（2026-11-08）；原備註：L2-7 使用者決策清單；D90 已回答（第 3 題磁碟已定案，第 4 題第二版範圍暫定）；issue 仍開著 |
| [#251](https://github.com/Polalalabear/amidst/issues/251) | Issue | L2-0 第二條線：複雜場景（D87） | Q5 | 已完成關閉（2026-11-08）；原備註：L2-0 第二條線傘狀 issue（D87）；工作分配見 [兩條線計畫](../agents/Q1Q5_TWO_LINE_PLAN_20261027.md) |
| [#255](https://github.com/Polalalabear/amidst/pull/255) | PR | feat(workbench-v2): L2-3 長時間軸／8 鏡頭牆（依賴 #243） | Q5 | 關閉未合併（2026-11-08）；原備註：Draft；L2-3 長時間軸／8 鏡頭牆；base 為 #243 的分支，依賴 #243 |
| [#258](https://github.com/Polalalabear/amidst/pull/258) | PR | docs(evaluation): Q5 評分規則 v2 設計稿（L2-1，#244） | Q5 | 關閉未合併（2026-11-08）；原備註：Draft；Q5 評分規則 v2 設計稿（L2-1，#244） |
| [#261](https://github.com/Polalalabear/amidst/pull/261) | PR | docs(evaluation): 複雜情境卡 v2（L2-2，#245） | Q5 | 關閉未合併（2026-11-08）；原備註：Draft；複雜情境卡 v2（L2-2，#245） |
| [#266](https://github.com/Polalalabear/amidst/pull/266) | PR | docs(contract): Line 2 C1–C10 answers and linker/Q5 proposal | Q5 | 關閉未合併（2026-11-08）；原備註：Draft；Line 2 C1–C10 回答與 linker／Q5 契約提案（base staging） |
| [#271](https://github.com/Polalalabear/amidst/pull/271) | PR | docs(r004): Line 2 static path feasibility and V1–V10 answers | Q5 | 關閉未合併（2026-11-08）；原備註：Draft；Line 2 靜態路徑可行性與 V1–V10 回答（base staging） |
| [#272](https://github.com/Polalalabear/amidst/pull/272) | PR | docs(graph): v4 overlap draft with pending M1 and missing exits | Q5 | 關閉未合併（2026-11-08）；原備註：Draft；r004 圖 v4 重疊草案（M1 待 G4、出口缺項；不取代 v3）（base staging） |
| [#273](https://github.com/Polalalabear/amidst/pull/273) | PR | feat(diagnostics): opt-in offline score and IoU gate comparison | Q2 | 關閉未合併（2026-11-08）；原備註：Draft；離線分數與 IoU 門檻比較（opt-in，預設 runtime 不變）（base staging） |
| [#274](https://github.com/Polalalabear/amidst/pull/274) | PR | docs(l2): 30-second two-camera corner scene plan and resource budget | Q5 | 關閉未合併（2026-11-08）；原備註：Draft；30 秒、兩鏡頭含轉角的工程場景規劃與資源預算（base staging） |
| [#287](https://github.com/Polalalabear/amidst/issues/287) | Issue | CQ-08 圖 v4 草案跟進 CQ-01 與 #272 note 1–2 | Q5 | 已完成關閉（2026-11-08）；原備註：CQ-08；依賴 CQ-01 |
| [#288](https://github.com/Polalalabear/amidst/issues/288) | Issue | CQ-09 #266 契約提案依複核 note 與 D93／D94 補註 | Q5 | 已完成關閉（2026-11-08）；原備註：CQ-09；對象 #266 |
| [#289](https://github.com/Polalalabear/amidst/issues/289) | Issue | CQ-10 #271 靜態可行性依複核修正（發現 1–7） | Q5 | 已完成關閉（2026-11-08）；原備註：CQ-10；對象 #271 |
| [#290](https://github.com/Polalalabear/amidst/issues/290) | Issue | CQ-11 #274 工程小場景規劃依複核修正（S6、遮擋類型、輪數） | Q5 | 已完成關閉（2026-11-08）；原備註：CQ-11；對象 #274 |
| [#291](https://github.com/Polalalabear/amidst/issues/291) | Issue | CQ-12 #273 文件移除自帶的實際產出 | Q2 | 已完成關閉（2026-11-08）；原備註：CQ-12；對象 #273 |
| [#293](https://github.com/Polalalabear/amidst/issues/293) | Issue | CQ-14 組員模型評測可攜包（Baseline＋複雜事件，可帶到別的環境跑） | Q5 | 已完成關閉（2026-11-08）；原備註：CQ-14；D96-2：重播凍結輸出、Python 3.12、以可攜包 v4 為基礎、GT 留在我方計分 |
| [#304](https://github.com/Polalalabear/amidst/issues/304) | Issue | CQ-21 逐轉移回條 adapter | Q5 | 已完成關閉（2026-11-08）；原備註：CQ-21；標 blocked-user |
| [#308](https://github.com/Polalalabear/amidst/issues/308) | Issue | CQ-21a 回條綁定契約補充草案（A1–A5、B1–B3、C1–C3） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#309](https://github.com/Polalalabear/amidst/issues/309) | Issue | CQ-21-T 回條 overlay adapter 的驗收測試（合成收據 fixture） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#322](https://github.com/Polalalabear/amidst/issues/322) | Issue | CQ-30 #258 Q5 評分規則 v2 設計稿回修（J2 F1–F4、D93、D94、#266 C1–C10） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#323](https://github.com/Polalalabear/amidst/issues/323) | Issue | CQ-31 #261 複雜情境卡 v2 回修（Codex 複核 F1–F3、#271／CQ-10） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#324](https://github.com/Polalalabear/amidst/issues/324) | Issue | CQ-32 Q5 評分器 v2 實作 q5_switch_eval_v2.py（14 項待決可設定、預設 fail closed） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#325](https://github.com/Polalalabear/amidst/issues/325) | Issue | CQ-32-T Q5 評分器 v2 的驗收測試（合成 controller 軌跡） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#326](https://github.com/Polalalabear/amidst/issues/326) | Issue | CQ-33 複雜事件 v2 劇本與 adapter v2（q5-evaluation-script.v2） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#327](https://github.com/Polalalabear/amidst/issues/327) | Issue | CQ-33-T adapter v2 的驗收測試（合成情境卡 v2） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#328](https://github.com/Polalalabear/amidst/issues/328) | Issue | CQ-34 複雜事件資料產製（渲染；r004 v2 卡片或 L2-6 #249） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#329](https://github.com/Polalalabear/amidst/issues/329) | Issue | CQ-35 複雜事件的偵測索引、兩模式執行與凍結輸出 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#330](https://github.com/Polalalabear/amidst/issues/330) | Issue | CQ-36 複雜事件評分與報告（v2 評分器） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#331](https://github.com/Polalalabear/amidst/issues/331) | Issue | CQ-36-T 複雜事件報告的驗收測試與重算腳本 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#332](https://github.com/Polalalabear/amidst/issues/332) | Issue | CQ-37 長時間軸／8 鏡頭牆接真實資料（#255、#246） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#333](https://github.com/Polalalabear/amidst/issues/333) | Issue | CQ-38 J4 linker 離線重播（#273 未交的 replay_l2_linker_*） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#334](https://github.com/Polalalabear/amidst/issues/334) | Issue | CQ-14-T 組員評測可攜包的驗收測試（Python 3.12、重播凍結輸出） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#335](https://github.com/Polalalabear/amidst/issues/335) | Issue | CQ-39 組員評測回件的計分流程 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#336](https://github.com/Polalalabear/amidst/issues/336) | Issue | CQ-39-T 評測回件計分流程的驗收測試（合成回件） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#343](https://github.com/Polalalabear/amidst/issues/343) | Issue | CQ-45（stretch）複雜情境卡 v2 第二批（規格與可行性） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#345](https://github.com/Polalalabear/amidst/issues/345) | Issue | CQ-47（stretch）L2-4 偵測改善參數實作（opt-in，只用於 Line 2） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#360](https://github.com/Polalalabear/amidst/pull/360) | PR | CQ-32-T：Q5 v2 評分器合成驗收與缺實作紅燈 | — | 關閉未合併（2026-11-08） |
| [#362](https://github.com/Polalalabear/amidst/pull/362) | PR | CQ33-T: synthetic v2 script adapter acceptance tests | — | 關閉未合併（2026-11-08） |
| [#363](https://github.com/Polalalabear/amidst/pull/363) | PR | CQ36-T: synthetic report checker and pending native integration tests | — | 關閉未合併（2026-11-08） |
| [#366](https://github.com/Polalalabear/amidst/pull/366) | PR | CQ-32: Q5 v2 評分器與預設未決設定，保留 v1 bytes | — | 關閉未合併（2026-11-08） |
| [#367](https://github.com/Polalalabear/amidst/pull/367) | PR | CQ-33: v2 adapter 共用評分公式與 UNFROZEN 甲卡計畫 | — | 關閉未合併（2026-11-08） |
| [#395](https://github.com/Polalalabear/amidst/pull/395) | PR | FEAT-8: 第二批候選規格與 safe_static 複核（PARTIAL） | — | 關閉未合併（2026-11-08） |
| [#396](https://github.com/Polalalabear/amidst/pull/396) | PR | [BLOCKED] FEAT-4: integrate settled scoring and source-bound scenario plans | — | 關閉未合併（2026-11-08） |
| [#399](https://github.com/Polalalabear/amidst/pull/399) | PR | feat(event-viewer): 複雜事件 A4-1/B4-1 唯讀多鏡頭播放（獨立包，D120） | — | 已合併 `mainline/q1q5`（2026-11-03） |

## 流程：任務板、交接與文件

### 已完成（89）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#3](https://github.com/Polalalabear/amidst/pull/3) | PR | docs: update main README with current demo and research progress | — | 已合併 `main` |
| [#52](https://github.com/Polalalabear/amidst/pull/52) | PR | docs(agents): 2026-10-17 status update and coordinator handoff | — | 關閉未合併，由 #70 取代 |
| [#70](https://github.com/Polalalabear/amidst/pull/70) | PR | docs(agents): coordinator handoff 2026-10-18 (D25 pivot) | — | 關閉未合併 |
| [#73](https://github.com/Polalalabear/amidst/pull/73) | PR | docs(qa): 使用者問答紀錄與導覽索引（78 題） | — | 關閉未合併 |
| [#83](https://github.com/Polalalabear/amidst/pull/83) | PR | docs(agents): 決策索引、系統總覽、組員上手指南 | — | 關閉未合併（2026-11-08）；原備註：組員上手文件、決策索引與系統總覽（非 Draft），待審查與合併 |
| [#87](https://github.com/Polalalabear/amidst/issues/87) | Issue | GitHub 整理紀錄（2026-10-20，D63 後） | — | 已完成關閉（2026-11-08）；原備註：D63 後的 GitHub 整理紀錄，最後更新 10-20；待確認是否關閉 |
| [#91](https://github.com/Polalalabear/amidst/pull/91) | PR | docs(agents): make mainline/q1q5 the integration branch (D63) | — | 已合併主線 |
| [#131](https://github.com/Polalalabear/amidst/issues/131) | Issue | QT-35：Codex finalization 搬移計畫（文件） | — | 已完成關閉（2026-11-01）；原備註：標 ready（內文寫 needs-auth）；搬移計畫文件已併入 staging（#143） |
| [#137](https://github.com/Polalalabear/amidst/issues/137) | Issue | QT-36：組員 交接試跑（照 TEAM_ONBOARDING 從零開始） | — | 已完成關閉（2026-11-08）；原備註：組員交接試跑未開始 |
| [#143](https://github.com/Polalalabear/amidst/pull/143) | PR | Q1–Q5 #131: 將既有 LOCAL finalization 移除計畫整理為 repo 文件。 | — | 已合進主線（第 1 批，2026-10-25） |
| [#147](https://github.com/Polalalabear/amidst/issues/147) | Issue | QT-42：組員審查包（資料夾）產生器與回收匯入器 | Q1、Q3、Q4 | 已完成關閉（2026-10-26）；原備註：文字審查包 #151 已併入 staging；圖片包等 #115、#118 |
| [#151](https://github.com/Polalalabear/amidst/pull/151) | PR | feat(evaluation): #147 deterministic pilot packs and human-return importer | Q1、Q3、Q4 | 已併入 staging，待審入主線 |
| [#188](https://github.com/Polalalabear/amidst/pull/188) | PR | docs(readme): rewrite README for the Q1–Q5 first demo and current progress | — | 已合併主線 |
| [#190](https://github.com/Polalalabear/amidst/pull/190) | PR | docs(progress): classify every PR and issue by Q1–Q5 and status | — | 已合併主線 |
| [#191](https://github.com/Polalalabear/amidst/pull/191) | PR | docs(agents): update the Q1–Q5 progress guide with every new PR and issue | — | 已合併主線（`4fddbc3`，2026-10-24）；在 AGENTS.md／CLAUDE.md 加入本文維護規則（D91-4 後由協調者在 mainline 批次補列；staging 併入 mainline 時，由協調者事後批次解導覽衝突，合併 PR 本身不改本文） |
| [#213](https://github.com/Polalalabear/amidst/pull/213) | PR | Merge staging batch 1 (#136 #139 #140 #141 #143 #132) into mainline/q1q5 | — | 已合併主線（`3ccaa3a`，2026-10-25） |
| [#214](https://github.com/Polalalabear/amidst/pull/214) | PR | 五項closeout：符合性重驗、Qwen診斷、回收補件、ROI與Q3審查準備 | Q3、Q5 | 關閉未合併（2026-10-27，盤點）；head 已含於 staging（經 #231 的 merge `680ca35`），分支保留 |
| [#215](https://github.com/Polalalabear/amidst/pull/215) | PR | docs: Q1–Q5 baseline acceptance plan and progress update (2026-10-25) | Q1、Q2、Q3、Q4、Q5 | 已合併主線（`7f08592`，2026-10-25） |
| [#217](https://github.com/Polalalabear/amidst/pull/217) | PR | docs: Q1–Q5 local test setup and progress update (2026-10-25) | — | 已合併主線（`e8f98dd`，2026-10-25） |
| [#223](https://github.com/Polalalabear/amidst/pull/223) | PR | docs: coordinator handoff 2026-10-25 and handoff-upload rule | — | 已合併主線（`1b6c56b`，2026-10-25） |
| [#225](https://github.com/Polalalabear/amidst/pull/225) | PR | docs(claude): point CLAUDE.md reading order at Q1–Q5 handoff | — | 已合併主線（`549d8ac`，2026-10-25）；CLAUDE.md 閱讀順序改指向 Q1–Q5 交接文件 |
| [#226](https://github.com/Polalalabear/amidst/pull/226) | PR | CX-2／#147 #151：組員說明、逐列回收拒錯與 PILOT 隔離 | Q1、Q3、Q4 | 已併入 staging（`4c96140`），待審入主線 |
| [#228](https://github.com/Polalalabear/amidst/pull/228) | PR | docs(q1q5): P1 工程預驗收走查清單（AC1–AC8） | Q1、Q2、Q3、Q4、Q5 | 已合併主線（`bd44ff2`，2026-10-27）；P1 工程預驗收走查清單 [走查清單](Q1Q5_P1_WALKTHROUGH_CHECKLIST.md)；P1 不是正式成績（D76） |
| [#232](https://github.com/Polalalabear/amidst/pull/232) | PR | 交接：公開 LOCAL 文件與相對路徑、大小及 hash 收據 | — | 已併入 staging（`63ce04d`），待審入主線 |
| [#241](https://github.com/Polalalabear/amidst/pull/241) | PR | docs(agents): 協調者交接 2026-10-26 與進度導覽更新 | — | 已合併主線（`2675c21`，2026-10-26） |
| [#252](https://github.com/Polalalabear/amidst/pull/252) | PR | docs(agents): 兩條線工作分配（D87） | — | 兩條線工作分配（D87）；已合併主線（`9708fb6`，2026-10-27） |
| [#263](https://github.com/Polalalabear/amidst/issues/263) | Issue | 文件封存與現況更新（D91） | Q1、Q2、Q3、Q4、Q5 | 已完成關閉（2026-11-08）；原備註：文件封存與現況更新（D91）；S1 #264、S2 #265、S4 #270 已於 2026-10-28 合併主線，S3 為 #276（尚未合併） |
| [#264](https://github.com/Polalalabear/amidst/pull/264) | PR | docs(archive): 封存索引與歷史文件檔頭（#263 S1, D91） | — | 封存索引與歷史文件檔頭（#263 S1）；已合併主線（`564352a`，2026-10-28） |
| [#265](https://github.com/Polalalabear/amidst/pull/265) | PR | docs: 入口文件更新與 2026-10-27 協調者交接（D91, S2） | — | 入口文件更新與 2026-10-27 協調者交接（#263 S2）；已合併主線（`204a180`，2026-10-28） |
| [#267](https://github.com/Polalalabear/amidst/pull/267) | PR | integration: prepare staging into mainline with D91 mainline docs preserved | — | 已合併 `mainline/q1q5`（2026-11-03）；原備註：Draft；staging → mainline 整合（D91 的 mainline 文件保留）；待 #260 等合入 staging 後更新，未合併；目前 CONFLICTING，說明寫明不可據此合併；刷新工作見 CQ-07 [#286](https://github.com/Polalalabear/amidst/issues/286)（blocked-user） |
| [#268](https://github.com/Polalalabear/amidst/pull/268) | PR | docs(archive): mark six Codex historical handoffs under D91 | — | 關閉未合併（2026-11-08）；原備註：Draft；六份 Codex 歷史交接加 D91 封存註記（base staging） |
| [#270](https://github.com/Polalalabear/amidst/pull/270) | PR | docs(specs): Q1–Q5 產品規格（#263 S4, D91） | Q1、Q2、Q3、Q4、Q5 | Q1–Q5 產品規格（#263 S4）；已合併主線（`741996c`，2026-10-28） |
| [#276](https://github.com/Polalalabear/amidst/pull/276) | PR | docs(progress): Q1–Q5 進度導覽與過期文件更新（#263 S3, D91） | Q1、Q2、Q3、Q4、Q5 | 已合併 `mainline/q1q5`（2026-10-28）；原備註：Draft；重算全部 PR／issue 並補 PR #242–#305、issue #244–#304 與漏列項目，新增「Line 2 複雜場景」分類；同時更新驗收計畫、本機測試設定、D79 文件、workbench v2 設計、finalization 計畫；Opus 審查 PASS_WITH_NOTES，P3-5 刷新已於 2026-10-28 完成；待使用者授權後合併 |
| [#279](https://github.com/Polalalabear/amidst/issues/279) | Issue | Codex 任務佇列（自取）2026-10-27 起 | — | 已完成關閉（2026-11-08）；原備註：D95 Codex 任務佇列（CQ-01～CQ-23，#280–#304，另含 #115、#118、#194、#202）；Claude 負責審查，標籤與本表由協調者維護 |
| [#283](https://github.com/Polalalabear/amidst/issues/283) | Issue | CQ-04 修 #276 的 P2-1～P2-5 與 P3-1、P3-3、P3-4、P3-6、P3-9 | — | 已完成關閉（2026-11-01）；原備註：CQ-04；#276 的 P2／P3 修正已由協調者處理並經 Opus 複審 PASS_WITH_NOTES；此議題是否仍需處理 UNKNOWN |
| [#286](https://github.com/Polalalabear/amidst/issues/286) | Issue | CQ-07 刷新 #267 staging→mainline 合併準備（必修 3 項） | — | 已完成關閉（2026-11-08）；原備註：CQ-07；標 blocked-user |
| [#292](https://github.com/Polalalabear/amidst/issues/292) | Issue | CQ-13 舊 Codex 範圍議題現行性判定（只留言，不關閉） | — | 已完成關閉（2026-11-01）；原備註：CQ-13；只留言，不關閉 |
| [#306](https://github.com/Polalalabear/amidst/issues/306) | Issue | 架構基準：Q1–Q5 demo（2026-11-01）權威文件、模組邊界與不偏離規則 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#317](https://github.com/Polalalabear/amidst/issues/317) | Issue | CQ-27 yyin 主包 team-handoff-yyin-20261028：框架與 s2 Q1／Q3 出題段 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#318](https://github.com/Polalalabear/amidst/issues/318) | Issue | CQ-27-T 交接包驗收測試與通用檢查器（主包與評測包共用） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#319](https://github.com/Polalalabear/amidst/issues/319) | Issue | CQ-28 yyin 主包 s1 審圖段（CQ-22 疊圖、3 題確認） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#320](https://github.com/Polalalabear/amidst/issues/320) | Issue | CQ-29 yyin 主包回件匯入與驗證（s1 審圖、s2 出題） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#321](https://github.com/Polalalabear/amidst/issues/321) | Issue | CQ-29-T 主包回件匯入的驗收測試（合成回件） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#347](https://github.com/Polalalabear/amidst/issues/347) | Issue | CQ-48 yyin 補交 templates/審查表.csv（併入主包 s0） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#349](https://github.com/Polalalabear/amidst/pull/349) | PR | CQ-22: yyin 三題靜態 A/B/C 確認疊圖 | — | 關閉未合併（2026-11-08） |
| [#358](https://github.com/Polalalabear/amidst/pull/358) | PR | CQ-29-T：合成主包回件驗收 probes（待 orchestration） | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#359](https://github.com/Polalalabear/amidst/pull/359) | PR | CQ-27-T：交接包機械檢查器與主包驗收測試 | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#361](https://github.com/Polalalabear/amidst/pull/361) | PR | CQ27/CQ28: offline authoring and review framework, production gate closed | — | 關閉未合併（2026-11-08） |
| [#364](https://github.com/Polalalabear/amidst/pull/364) | PR | CQ14-T: isolated offline team evaluation pack acceptance tests | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#365](https://github.com/Polalalabear/amidst/pull/365) | PR | CQ39-T: return integrity, freeze ordering and drift scoring tests | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#369](https://github.com/Polalalabear/amidst/issues/369) | Issue | FEAT-2 yyin 主包與回件 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#370](https://github.com/Polalalabear/amidst/issues/370) | Issue | FEAT-3 組員評測包 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#371](https://github.com/Polalalabear/amidst/issues/371) | Issue | FEAT-4 複雜事件 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#372](https://github.com/Polalalabear/amidst/issues/372) | Issue | FEAT-5 demo 工程 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#373](https://github.com/Polalalabear/amidst/issues/373) | Issue | FEAT-6 v2 回應與消費端 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#374](https://github.com/Polalalabear/amidst/issues/374) | Issue | FEAT-7 架構守門 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#375](https://github.com/Polalalabear/amidst/issues/375) | Issue | FEAT-8 stretch 延伸項目 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#376](https://github.com/Polalalabear/amidst/issues/376) | Issue | FEAT-1 Baseline 正式鏈 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#379](https://github.com/Polalalabear/amidst/pull/379) | PR | docs(research): 相關工作與定位 | — | 關閉未合併（2026-11-08） |
| [#382](https://github.com/Polalalabear/amidst/pull/382) | PR | docs(rules): 規則改寫到 D104～D108 與廢棄／過時索引（D108） | — | 關閉未合併（2026-11-08） |
| [#389](https://github.com/Polalalabear/amidst/pull/389) | PR | FEAT-3: 原生離線評測包與 Baseline-only RETURN（PARTIAL） | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#390](https://github.com/Polalalabear/amidst/pull/390) | PR | FEAT-2: yyin s2 v0-pilot 可重現主包（分段） | — | 已合併 `codex/q1q5-staging`（2026-11-03） |
| [#397](https://github.com/Polalalabear/amidst/pull/397) | PR | docs(research): 模組上的模型實驗分析企劃（demo 後執行，不進 11-03 批次） | — | 關閉未合併（2026-11-08） |
| [#398](https://github.com/Polalalabear/amidst/pull/398) | PR | docs(specs): Q1–Q5 現行系統架構 spec（草稿，不進 11-03 批次） | — | 關閉未合併（2026-11-08） |
| [#407](https://github.com/Polalalabear/amidst/pull/407) | PR | feat(research): experiment-env schema, analysis scripts, baseline table (#397) | — | 已合併 `mainline/q1q5`（2026-11-04） |
| [#409](https://github.com/Polalalabear/amidst/pull/409) | PR | docs(project): D126 專案文件包（目標與架構） | — | 關閉未合併（2026-11-08） |
| [#488](https://github.com/Polalalabear/amidst/pull/488) | PR | [DO NOT MERGE] docs(research): LaTeX experiment record | — | 關閉未合併（2026-11-15） |
| [#524](https://github.com/Polalalabear/amidst/pull/524) | PR | docs(report): 第五章 結論與建議初稿 (D209) | — | 已合併 `main`（2026-11-11） |
| [#540](https://github.com/Polalalabear/amidst/pull/540) | PR | docs(ops): coordinator handoff 2026-11-15 | — | 已合併 `main`（2026-11-15） |
| [#548](https://github.com/Polalalabear/amidst/pull/548) | PR | docs(ops): 進度導覽補到 #548（D91-4 批次補列） | — | 已合併 `main`（2026-11-15，`17a480a6`） |
| [#549](https://github.com/Polalalabear/amidst/pull/549) | PR | docs(ops): issues and fixes 2026-11-15~16; handoff 11-16 update | — | 已合併 `main`（2026-11-15，`1fe6e716`） |
| [#550](https://github.com/Polalalabear/amidst/pull/550) | PR | docs(ops): coordinator handoff 2026-11-16 | — | 已合併 `main`（2026-11-16，`ccbd9533`） |
| [#557](https://github.com/Polalalabear/amidst/pull/557) | PR | docs(agents): 2026-11-16/17 流程規則寫進 AGENTS/CLAUDE；進度導覽補到最新 | — | 已合併 `main`（2026-11-17，`31a69177`）；原備註：本 PR；待審，未合併 |
| [#558](https://github.com/Polalalabear/amidst/pull/558) | PR | docs(record): 實驗紀錄 v4——預錄與 live 的差異、參數依據、LLM 介入 | — | 已合併 `main`（2026-11-17，`edb96a31`）；原備註：審查 NEEDS_CHANGES 後修正 |
| [#562](https://github.com/Polalalabear/amidst/pull/562) | PR | docs(agents): 交接規則寫進 CLAUDE.md（D255）＋協調者交接 2026-11-17 | — | 已合併 `main`（2026-11-17，`444d15f3`） |
| [#565](https://github.com/Polalalabear/amidst/pull/565) | PR | docs(agents): 協調者交接 11-17 晚間快照；AGENTS 主要 UI 改 workbench-v2；進度導覽補到 #564 | — | 已合併 `main`（2026-11-17，`3137a1ca`）；分支 `claude/feat-ops-docs` |
| [#576](https://github.com/Polalalabear/amidst/issues/576) | Issue | CL-B1 8785／8791 更新到 main（含 #559、#563、#564） | — | 已完成關閉（2026-11-18）；D324：gate 通過、使用者核准 pin `b98fac2a`，8785、8791 重啟；owner:claude |
| [#577](https://github.com/Polalalabear/amidst/issues/577) | Issue | CL-B2 #563 的 P3：advisor_model 非字串、IPv6 | — | 已完成關閉（2026-11-18）；由 #609 合併（`fb4b99b9`）；原備註：blocked；owner:claude |
| [#578](https://github.com/Polalalabear/amidst/issues/578) | Issue | CL-B3 #564 審查的 3 個 P3 | — | 已完成關閉（2026-11-18）；由 #609 合併（`fb4b99b9`）；原備註：blocked；owner:claude |
| [#579](https://github.com/Polalalabear/amidst/issues/579) | Issue | CL-B4 Office 補列 8 檔的後續處理（office_demo_backend 仍 import office_display） | — | 已完成關閉（2026-11-18）；原備註：進行中（in-progress）；owner:claude |
| [#580](https://github.com/Polalalabear/amidst/issues/580) | Issue | CL-B5 流程文件：R2 封存＋R3 ledger＋進度導覽＋AGENTS/CLAUDE 指向 #93（claude/feat-ops-docs） | — | 已完成關閉（2026-11-18）；原備註：進行中；本 PR（`claude/feat-ops-docs`）處理；owner:claude |
| [#581](https://github.com/Polalalabear/amidst/issues/581) | Issue | CL-B6 #479 報告素材追加＋第 5 章補 WP5 數字 | — | 已完成關閉（2026-11-18）；原備註：進行中（in-progress）；owner:claude |
| [#582](https://github.com/Polalalabear/amidst/issues/582) | Issue | CL-B7 #479／#489 子項勾選盤點＋#93 無編號留言編 D 號 | — | 已完成關閉（2026-11-18）；原備註：進行中（in-progress）；owner:claude |
| [#583](https://github.com/Polalalabear/amidst/issues/583) | Issue | 待使用者決定（協調者維護） | — | 已完成關閉（2026-11-18）；原備註：needs-auth；等使用者決定的項目，由協調者維護 |
| [#585](https://github.com/Polalalabear/amidst/issues/585) | Issue | CL-B8 LIVE 規格補丁：C-5 定義＋重新取得契約（分段門檻） | — | 已完成關閉（2026-11-18）；原備註：進行中（in-progress）；owner:claude |
| [#586](https://github.com/Polalalabear/amidst/pull/586) | PR | docs(report): CH5 補 WP5 數字（5.3、5.4 第 5 點，#581） | — | 已合併 `main`（2026-11-18，`bd1dc614`） |
| [#590](https://github.com/Polalalabear/amidst/pull/590) | PR | docs(ops): R2 文件封存、R3 ledger、進度導覽補到 #585、工作清單指向 #93（#580） | — | 已合併 `main`（2026-11-18，`703ce625`） |
| [#606](https://github.com/Polalalabear/amidst/pull/606) | PR | docs(agents): 協調者交接 2026-11-18（D278–D308）；CLAUDE/AGENTS 連結改新檔 | — | 已合併 `main`（2026-11-18，`b7ca80f2`） |
| [#614](https://github.com/Polalalabear/amidst/pull/614) | PR | docs(ops): 進度導覽批次補列到 #613（D311–D318）；交接 11-18 補記 | — | 已合併 `main`（2026-11-18，`1f6ecacd`）；分支 `claude/feat-ops-docs` |

### 進行中（2）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#93](https://github.com/Polalalabear/amidst/issues/93) | Issue | Q1–Q5 任務板（從這裡開始） | Q1、Q2、Q3、Q4、Q5 | Q1–Q5 任務板；決定已到 D332（2026-11-18 晚間交接，下一個 D333）；D95 Codex 任務佇列為 [#279](https://github.com/Polalalabear/amidst/issues/279) |
| [#479](https://github.com/Polalalabear/amidst/issues/479) | Issue | B｜實驗紀錄與研究報告（LaTeX 紀錄、RQ1–RQ5、延遲、評估） | — | 進行中；issue 開著；owner:argon |

## Agent：WP／DP4 與評估

### 已完成（25）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#480](https://github.com/Polalalabear/amidst/issues/480) | Issue | W-X1 自然語言：文字轉選單輸入框（#469 提前） | — | 已完成關閉（2026-11-08） |
| [#481](https://github.com/Polalalabear/amidst/issues/481) | Issue | W-X2 數位孿生：俯視圖點選教室即查找（r005） | — | 已完成關閉（2026-11-08） |
| [#482](https://github.com/Polalalabear/amidst/issues/482) | Issue | W-X3 AI agent：放寬逾時探索組，讓 Qwen 真的參與決策 | — | 已完成關閉（2026-11-08） |
| [#483](https://github.com/Polalalabear/amidst/issues/483) | Issue | W-C14 OpenAI API 接入決策與解析（baseline 後），使用者驗收完整操作 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#490](https://github.com/Polalalabear/amidst/pull/490) | PR | [DO NOT MERGE] feat: Epic D path (b) natural-language to options + design v1 | — | 關閉未合併（2026-11-15）；設計稿 `docs/specs/EPIC_D_AGENTIC_V1.md` 已搬進 main（#557，D250），路徑 (b) 的實作未進 main（已被 N1 取代） |
| [#502](https://github.com/Polalalabear/amidst/pull/502) | PR | docs(design): Agent 決策設計稿 v1（DRAFT，D152） | — | 已合併 `mainline/q1q5`（2026-11-09） |
| [#505](https://github.com/Polalalabear/amidst/pull/505) | PR | feat(agent): WP1 agent-decision v1 contract, validators, rule decider and call caps | — | 已合併 `mainline/q1q5`（2026-11-10） |
| [#511](https://github.com/Polalalabear/amidst/issues/511) | Issue | WP3｜OpenAI（astra6/sol6.1/terra6.1）與 Ollama 轉接器＋錄製／重播（Argon） | — | 已完成關閉（2026-11-15）；owner:argon |
| [#513](https://github.com/Polalalabear/amidst/pull/513) | PR | feat(agent): WP2 wire agent decision into associate() (default off, byte-identical) | — | 已合併 `mainline/q1q5`（2026-11-10） |
| [#515](https://github.com/Polalalabear/amidst/issues/515) | Issue | Agent 評估工具鏈：題庫、合成干擾、R1、評分、實測 runner、Windows 包（Argon） | — | 已完成關閉（2026-11-15）；owner:argon |
| [#518](https://github.com/Polalalabear/amidst/pull/518) | PR | test: Argon eval-toolchain acceptance gates (xfail) (D200) | — | 已合併 `main`（2026-11-10） |
| [#525](https://github.com/Polalalabear/amidst/pull/525) | PR | feat(agent-eval): WP4-WP6 question bank, S2 synthetic, R1, scoring, runner, and Windows pack (#515) | — | 已合併 `main`（2026-11-15） |
| [#526](https://github.com/Polalalabear/amidst/pull/526) | PR | feat(agent): WP3 OpenAI & Ollama providers, JSONL recording and replay (#511) | — | 已合併 `main`（2026-11-15） |
| [#531](https://github.com/Polalalabear/amidst/pull/531) | PR | feat(dp4): attention ranking contract, Rule method, xfail gates for API/Agent (D214) | — | 已合併 `main`（2026-11-15） |
| [#532](https://github.com/Polalalabear/amidst/issues/532) | Issue | N3｜DP4 主動關注：API 與 Agent 版本（Argon） | — | 已完成關閉（2026-11-15）；owner:argon |
| [#537](https://github.com/Polalalabear/amidst/pull/537) | PR | Shared paid-API spend guard (server switch, layered caps, ledger, dry-run) | — | 已合併 `main`（2026-11-15） |
| [#538](https://github.com/Polalalabear/amidst/pull/538) | PR | WP5: Rule/local/OpenAI comparison harness (DP1/DP3/DP4/NL), Colab L4, dry-run estimate | — | 已合併 `main`（2026-11-15） |
| [#541](https://github.com/Polalalabear/amidst/pull/541) | PR | feat(q1q5): implement DP4 attention API and Agent rankers (#532) | — | 已合併 `main`（2026-11-15） |
| [#543](https://github.com/Polalalabear/amidst/pull/543) | PR | feat(wp5): Colab L4 and Windows local-model packs (main 18715e69) | — | 已合併 `main`（2026-11-15） |
| [#546](https://github.com/Polalalabear/amidst/pull/546) | PR | fix(wp5): DP1/DP3 never reached Ollama on Colab L4 (dangling $ref); checks, one-click notebook v2 | — | 已合併 `main`（2026-11-17，`febc1707`，D251）；原備註：進行中；開著，未合併 |
| [#554](https://github.com/Polalalabear/amidst/issues/554) | Issue | CX-L3 WP5：把 DP4 的實跑接上 runner（移除 DP4_LIVE_NOT_WIRED） | — | 已完成關閉（2026-11-17，#560 `4142e26c`）；真實 provider DP4 smoke 等使用者核准金額；owner:codex |
| [#560](https://github.com/Polalalabear/amidst/pull/560) | PR | feat(wp5): wire guarded DP4 API and agent ranking | — | 已合併 `main`（2026-11-17，`4142e26c`，D266）；Codex，#554 |
| [#592](https://github.com/Polalalabear/amidst/issues/592) | Issue | CL-B10 WP5 改善：逐題型逾時＋縮短輸出＋加大 pilot＋DP4 smoke（上限 USD 3） | — | 關閉（不處理）（2026-11-18） |
| [#601](https://github.com/Polalalabear/amidst/issues/601) | Issue | CL-B13 預錄模式（8785）追蹤方式可切換 OpenAI Agent | — | 已完成關閉（2026-11-18） |
| [#604](https://github.com/Polalalabear/amidst/pull/604) | PR | feat(demo): 預錄模式（8785）可切 OpenAI Agent（CL-B13 #601） | — | 已合併 `main`（2026-11-18，`62da6464`） |

### 進行中（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#489](https://github.com/Polalalabear/amidst/issues/489) | Issue | D｜讓 Agentic 成立：自然語言、數位孿生點選、Agent 實際決策、OpenAI | — | 進行中；issue 開著 |

### 未完成（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#620](https://github.com/Polalalabear/amidst/issues/620) | Issue | CL-B16 8785 預錄 Q2 Agent 開關在 A4-1／B4-1／B-05 回 TRACKING_SCOPE_MISSING | — | D328 發現；D332 開；owner:claude |

## 即時模式（Live mode）

### 已完成（26）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#544](https://github.com/Polalalabear/amidst/pull/544) | PR | Live mode spike: latency matrix, CPU comparison, report (D210) | — | 已合併 `main`（2026-11-16，`7d612aa7`，D247） |
| [#547](https://github.com/Polalalabear/amidst/pull/547) | PR | docs(design): 即時模式的 LLM 決策：接法和測試設計 v1（DRAFT） | — | 已合併 `main`（2026-11-17，`da0dfe60`）；原備註：Draft；進行中 |
| [#551](https://github.com/Polalalabear/amidst/pull/551) | PR | feat(live-mode): B 畫面跟隨視角＋HUD | — | 已合併 `main`（2026-11-17，`21aacc8e`）；原備註：Draft；進行中（`claude/feat-live-bscreen`，D247） |
| [#552](https://github.com/Polalalabear/amidst/issues/552) | Issue | CX-L1 即時模式：A4 室外鏡頭偵測率（CAM_ENTRY 19%、R101_IN 47%、EXT_CAR 67%） | — | 已完成關閉（2026-11-18）；程式在 #559（`894bdd9e`）；原備註：程式在 #559（Draft）；owner:codex |
| [#553](https://github.com/Polalalabear/amidst/issues/553) | Issue | CX-L2 即時模式：推論排程（只推論作用中鏡頭和鄰居） | — | 已完成關閉（2026-11-17，#561）；owner:codex |
| [#556](https://github.com/Polalalabear/amidst/pull/556) | PR | fix(live-mode): people grouping dedup + 1.0 m cross-camera pairing (#544 follow-up) | — | 已合併 `main`（2026-11-17，`547a9e61`）；原備註：Draft；進行中（`claude/feat-live-people`，D247） |
| [#559](https://github.com/Polalalabear/amidst/pull/559) | PR | fix(live): improve camera detection and add an isolated demo launcher | — | 已合併 `main`（2026-11-18，`894bdd9e`）；原備註：Draft；聯合驗證 NOT_PASSED，Codex 依第三份指示修排程與重新鎖定（D273）；#552、#555 |
| [#561](https://github.com/Polalalabear/amidst/pull/561) | PR | feat(live): schedule camera inference from safe graph neighborhoods | — | 已合併 `main`（2026-11-17，`e9db4fdf`）；Codex，#553 |
| [#563](https://github.com/Polalalabear/amidst/pull/563) | PR | feat(live-mode): LLM decision switch (default off, rule fallback with reason) | — | 已合併 `main`（2026-11-17，`0606b164`）；原備註：改接 workbench-v2，差異重審 APPROVE（附 P2） |
| [#567](https://github.com/Polalalabear/amidst/pull/567) | PR | docs(specs): LIVE A/B dual-screen spec and interface contract v2 | — | 已合併 `main`（2026-11-17，`2f013cb8`）；分支 `claude/feat-live-ab` |
| [#568](https://github.com/Polalalabear/amidst/issues/568) | Issue | CX-L5a 即時模式 A/B：人物不碰撞（crowd＋sim，C-1～C-8） | — | 已完成關閉（2026-11-18）；隨 #584 合併（`81ba829d`）；原備註：進行中；#584；C-5 改分類中（D282）；owner:codex |
| [#569](https://github.com/Polalalabear/amidst/issues/569) | Issue | CX-L5b 即時模式 A/B：A 場景＋角色選單、滑鼠轉視角 | — | 已完成關閉（2026-11-18）；隨 #584 合併（`81ba829d`）；原備註：進行中；已交 #584（Draft）；owner:codex |
| [#570](https://github.com/Polalalabear/amidst/issues/570) | Issue | CX-L5c 即時模式 A/B：離線評分 scripts/live_ab_score.py | — | 已完成關閉（2026-11-18）；隨 #584 合併（`81ba829d`）；原備註：進行中；已交 #584（Draft）；owner:codex |
| [#571](https://github.com/Polalalabear/amidst/issues/571) | Issue | CX-L5d 即時模式 A/B：後台 /track/* 端點＋session＋Q3 句子接線（blocked on #559） | — | 已完成關閉（2026-11-18）；由 #610 合併（`118c2035`，D323）；owner:codex |
| [#572](https://github.com/Polalalabear/amidst/issues/572) | Issue | CX-L5e 即時模式 A/B：B 選目標流程＋句子輸入＋HUD＋協定（blocked on #559） | — | 已完成關閉（2026-11-18）；由 #610 合併（`118c2035`，D323）；owner:codex |
| [#573](https://github.com/Polalalabear/amidst/issues/573) | Issue | CX-L5f R4：smoke.mjs 預設輸出不寫 /private/tmp | — | 已完成關閉（2026-11-18）；隨 #584 合併（`81ba829d`）；原備註：進行中；已交 #584（Draft）；owner:codex |
| [#584](https://github.com/Polalalabear/amidst/pull/584) | PR | feat(live-ab): add operator crowd and offline evaluation in stages | — | 已合併 `main`（2026-11-18，`81ba829d`）；原備註：Draft；進行中（`codex/feat-live-ab`），#568–#570、#573 |
| [#587](https://github.com/Polalalabear/amidst/pull/587) | PR | docs(specs): LIVE A/B v2.1（C-5 補定義）＋重新取得契約 v1（#585） | — | 已合併 `main`（2026-11-18，`590afb34`）；即時模式 A/B 規格 v2.1＋重新取得契約 v1 |
| [#591](https://github.com/Polalalabear/amidst/issues/591) | Issue | CL-B9 即時模式 LLM：sol6.1「目標不在名單」驗證（上限 USD 0.2） | — | 關閉（不處理）（2026-11-18） |
| [#600](https://github.com/Polalalabear/amidst/issues/600) | Issue | CL-B12 即時模式場景外圍：從車子那側看出去直接看到房子建模，先出示意圖 | — | 已完成關閉（2026-11-18） |
| [#602](https://github.com/Polalalabear/amidst/issues/602) | Issue | CL-B14 場景外圍實作：LIVE 加真實世界外圍（可走範圍不變） | — | 已完成關閉（2026-11-18） |
| [#607](https://github.com/Polalalabear/amidst/pull/607) | PR | feat(live-mode): 場景外圍背景（LIVE，可走範圍不變）#602 | — | 已合併 `main`（2026-11-18，`7f8e8443`） |
| [#610](https://github.com/Polalalabear/amidst/pull/610) | PR | feat(live-ab): session-scoped target selection and B controls | — | 已合併 `main`（2026-11-18，`118c2035`，D323）；#571、#572；Opus 三點判定的修正在 #617 |
| [#611](https://github.com/Polalalabear/amidst/pull/611) | PR | docs(live): 重新取得契約補 NEEDS_CONFIRM 的 short_gate 出口（#588, D314-4） | — | 已合併 `main`（2026-11-18，`4bf9b5ed`） |
| [#615](https://github.com/Polalalabear/amidst/pull/615) | PR | feat(live-mode): LIVE 難題集 v1 事件與答案表＋腳本操作者（#597） | — | 已合併 `main`（2026-11-18，`7393bf62`，D330）；分支 `claude/feat-live-hardset` |
| [#618](https://github.com/Polalalabear/amidst/pull/618) | PR | fix(ui): LIVE A 選單改工作台風格＋修 / 與 /workbench-v2 跑版 | — | 已合併 `main`（2026-11-18，`50f2fd14`，D329）；8791 已更新；8785 等下一次 pin |

### 進行中（4）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#566](https://github.com/Polalalabear/amidst/issues/566) | Issue | CX-L5 即時模式 A/B 雙畫面：選角色、B 選目標、人物不碰撞 | — | 子項 #568–#573 已完成關閉（#571、#572 由 #610），#574 未完成（等 #617）；原備註：進行中；母 issue，子項 #568–#574；owner:codex |
| [#588](https://github.com/Polalalabear/amidst/issues/588) | Issue | CX-L6a 重新取得 R1：tracker 分段門檻狀態機＋外觀特徵＋門檻量測 | — | CX-L6a；D326：R-5 拆成 R-5a（R1 閘門）與 R-5b（移到 #597）；#608 驗證完成，NEEDS_CHANGES（和 main 衝突，等 Codex 合 main，D331-2）；owner:codex |
| [#608](https://github.com/Polalalabear/amidst/pull/608) | PR | LIVE relock R1 with fixed replay and prediction checkpoint | — | head `533b4e99`（D326）；NEEDS_CHANGES（D331-2）：和 main 衝突（tracker.py 語意衝突），等 Codex 合 main 重跑驗收；#588 的實作 |
| [#617](https://github.com/Polalalabear/amidst/pull/617) | PR（Draft） | feat(live-ab): record deterministic cases and audit lingering passes | — | head `50164136`；D327 pass 規則＋#596 錄製重播；NEEDS_CHANGES（D331-2）：和 main 衝突，等 Codex 合 main |

### 未完成（5）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#574](https://github.com/Polalalabear/amidst/issues/574) | Issue | CX-L5g 即時模式 A/B：整合、瀏覽器驗收、handoff 文件 | — | blocked（等 #617；#571、#572 已由 #610 完成）；owner:codex |
| [#589](https://github.com/Polalalabear/amidst/issues/589) | Issue | CX-L6b 重新取得 R2：後台接線＋#559 adaptive 排程驗收（ENTRY） | — | CX-L6b；等 #608 合併；owner:codex |
| [#596](https://github.com/Polalalabear/amidst/issues/596) | Issue | CX-L7 LIVE 錄製與重播：玩家軌跡存成可重播劇本 | — | CX-L7；D326 可開始；實作在 #617（`50164136`）；owner:codex |
| [#597](https://github.com/Polalalabear/amidst/issues/597) | Issue | CL-B11 LIVE 難題集：規則 vs LLM 重播比較（含「目標不在名單」） | — | CL-B11；事件表、答案表、腳本操作者已由 #615 合併；D330：H1／H4 讀法、路線修正、#619；D331：全部改腳本產生；owner:claude |
| [#619](https://github.com/Polalalabear/amidst/issues/619) | Issue | CX-L8 LIVE 室外遠端目標的偵測／追蹤失敗（難題集前置條件） | — | D330-c；owner:codex |

## 4 人場景、8 鏡頭與 N6 素材（#516）

### 已完成（16）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#516](https://github.com/Polalalabear/amidst/issues/516) | Issue | 4 人場景產製：Blender 可行性檢查、A4/B4 渲染、RT-DETR 索引、safe bundle（Codex） | — | 已完成關閉（2026-11-15）；owner:codex |
| [#519](https://github.com/Polalalabear/amidst/pull/519) | PR | docs(eval): r004 A4/B4 scenario cards v2 (4 actors) + clearance checker (D198) | — | 已合併 `main`（2026-11-10） |
| [#520](https://github.com/Polalalabear/amidst/pull/520) | PR | test: Codex #516 r004 4-actor production gates (xfail) (D206) | — | 已合併 `main`（2026-11-10） |
| [#521](https://github.com/Polalalabear/amidst/pull/521) | PR | docs(eval): r004 A4/B4 scenario cards v2.1 — 4-actor routes PASS on measured geometry (D207, #516) | — | 已合併 `main`（2026-11-10） |
| [#522](https://github.com/Polalalabear/amidst/pull/522) | PR | fix(#516 G1): boundary allows wrote_local_dir with local_dir under local/evidence (D208) | — | 已合併 `main`（2026-11-10） |
| [#523](https://github.com/Polalalabear/amidst/pull/523) | PR | feat(516): deliver verified four-actor r004 scenes, indexes and safe bundle | — | 關閉未合併（2026-11-15） |
| [#527](https://github.com/Polalalabear/amidst/pull/527) | PR | feat(producer): full corrected A4 B4 walking movies at approved 5fps | — | 關閉未合併（2026-11-15） |
| [#528](https://github.com/Polalalabear/amidst/pull/528) | PR | test(#516): gates require 8 render cameras, draft priority v2.3 (D211) | — | 已合併 `main`（2026-11-14） |
| [#529](https://github.com/Polalalabear/amidst/pull/529) | PR | feat(#516): complete eight-camera natural-walk runs and fresh RT-DETR bundles | — | 已合併 `main`（2026-11-15） |
| [#530](https://github.com/Polalalabear/amidst/pull/530) | PR | feat(event-viewer): 查看模式一次顯示全部鏡頭（8 台不捲動）(D212) | — | 已合併 `main`（2026-11-15） |
| [#533](https://github.com/Polalalabear/amidst/pull/533) | PR | feat(workbench): show #529 eight-camera 4-actor runs in view mode (D214) | — | 已合併 `main`（2026-11-15） |
| [#534](https://github.com/Polalalabear/amidst/pull/534) | PR | feat(event-viewer): 格狀／焦點兩種版面與切換 | — | 已合併 `main`（2026-11-15） |
| [#539](https://github.com/Polalalabear/amidst/pull/539) | PR | feat(N6): articulated r004 live assets and baked scene (#516) | — | 已合併 `main`（2026-11-15） |
| [#593](https://github.com/Polalalabear/amidst/issues/593) | Issue | CX-N6b 即時模式 N6 場景：天花板亮度與接縫 | — | 已完成關閉（2026-11-18） |
| [#599](https://github.com/Polalalabear/amidst/pull/599) | PR | Soften the baked N6 ceiling material | — | 已合併 `main`（2026-11-18，`3c3e1267`） |
| [#603](https://github.com/Polalalabear/amidst/pull/603) | PR | Add A4-1-8CAM to workbench-v2 from the pinned safe bundle | — | 已合併 `main`（2026-11-18，`3b5a987a`） |

## Demo 整合、前台 UI 與 8785 更新（#445）

### 已完成（25）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#408](https://github.com/Polalalabear/amidst/pull/408) | PR | feat(demo): 全部 demo 事件整合進 workbench-v2 事件選單＋一鍵啟動 | — | 關閉未合併（2026-11-08） |
| [#445](https://github.com/Polalalabear/amidst/issues/445) | Issue | A｜Demo 驗收：新 UI＋真實資料（case1／case2 × 三事件） | — | 已完成關閉（2026-11-15）；owner:codex |
| [#484](https://github.com/Polalalabear/amidst/pull/484) | PR | docs(specs): 工作台 UI 改版規格 v1（PROPOSED） | — | 關閉未合併（2026-11-08） |
| [#485](https://github.com/Polalalabear/amidst/pull/485) | PR | demo integration (Refs #445) | — | 已合併 `mainline/q1q5`（2026-11-09） |
| [#487](https://github.com/Polalalabear/amidst/pull/487) | PR | feat(ui): redesigned front desk and admin on the integration branch | — | 已合併 `claude/445-demo-integration`（2026-11-09） |
| [#492](https://github.com/Polalalabear/amidst/pull/492) | PR | test(ui): #487 P3-4 DOM test and core-e2e 900/1300 viewports (draft, do not merge) | — | 關閉未合併（2026-11-08） |
| [#493](https://github.com/Polalalabear/amidst/pull/493) | PR | D139 / #445: 前台展示調整（展示模式、速度下拉、單一時間軸、追蹤時段、盲區終點；特徵分組待資料來源） | — | 已合併 `claude/ui-redesign-v1`（2026-11-09） |
| [#494](https://github.com/Polalalabear/amidst/pull/494) | PR | docs(readme): update README to 2026-11-08 state (#445) | — | 已合併 `claude/ui-redesign-v1`（2026-11-09） |
| [#495](https://github.com/Polalalabear/amidst/pull/495) | PR | feat(api): expose index-bound detected class counts for D139 | — | 已合併 `claude/ui-d139`（2026-11-08） |
| [#496](https://github.com/Polalalabear/amidst/pull/496) | PR | D144/D145: replay all local candidates, mark reacquisition and count cameras | — | 已合併 `claude/ui-d139`（2026-11-08） |
| [#497](https://github.com/Polalalabear/amidst/pull/497) | PR | test(perf): measurement B in-page latency tool (dry run only) | — | 已合併 `claude/ui-d139`（2026-11-09） |
| [#498](https://github.com/Polalalabear/amidst/pull/498) | PR | D147/D148/D149: replay reacquisition, box continuation and annotated car search (D150 acceptance) | — | 已合併 `claude/ui-d139`（2026-11-09） |
| [#499](https://github.com/Polalalabear/amidst/pull/499) | PR | fix(ui): 後台分段按鈕排版、展示模式事件短名稱 | — | 已合併 `claude/ui-d139`（2026-11-09） |
| [#500](https://github.com/Polalalabear/amidst/pull/500) | PR | fix(q1q5): 回應／job／media ref 滿了改成淘汰最舊，不再 Q_RESPONSE_LIMIT | — | 已合併 `claude/ui-redesign-v1`（2026-11-09） |
| [#504](https://github.com/Polalalabear/amidst/pull/504) | PR | fix(q1q5): #498 P2 — local-track score floor from Parameters; receipt marked regression pin | — | 已合併 `mainline/q1q5`（2026-11-09） |
| [#510](https://github.com/Polalalabear/amidst/pull/510) | PR | fix(ui): hide location field in 追蹤新目標 window (D185) | — | 已合併 `mainline/q1q5`（2026-11-10） |
| [#535](https://github.com/Polalalabear/amidst/pull/535) | PR | N1: Spotlight 搜尋欄（一句話 → 標籤面板，API/本機/固定句型備援） | — | 已合併 `main`（2026-11-15） |
| [#542](https://github.com/Polalalabear/amidst/pull/542) | PR | fix(workbench): frame swap never leaves an unloaded <img> (core-e2e check 91) + env_templates grep | — | 已合併 `main`（2026-11-15） |
| [#545](https://github.com/Polalalabear/amidst/pull/545) | PR | docs(ops): 8785 update plan and 8CAM launcher fix | — | 已合併 `main`（2026-11-15） |
| [#555](https://github.com/Polalalabear/amidst/issues/555) | Issue | CX-L4 8785 更新準備：launcher 兩項 P2 與即時模式啟動入口 | — | 已完成關閉（2026-11-18）；原備註：程式併在 #559（Draft）；8785 已在 2026-11-17 更新到 main `e9db4fdf`（D270）；owner:codex |
| [#564](https://github.com/Polalalabear/amidst/pull/564) | PR | workbench-v2: 搜尋 Enter、追蹤分頁搜尋、概況排版、易讀名稱、live 入口 | — | 已合併 `main`（2026-11-18，`eb06e9a0`）；原備註：Draft；進行中（`claude/feat-workbench-v2-ux`，D271–D272） |
| [#605](https://github.com/Polalalabear/amidst/issues/605) | Issue | CL-B15 預錄模式俯視圖改成 LIVE 式 3D 場景視圖（先出示意圖） | — | 已完成關閉（2026-11-18）；實作在 #613（`b98fac2a`） |
| [#609](https://github.com/Polalalabear/amidst/pull/609) | PR | fix: #563/#564 review P3s (#577, #578) | — | 已合併 `main`（2026-11-18，`fb4b99b9`）；#577、#578 一併關閉 |
| [#613](https://github.com/Polalalabear/amidst/pull/613) | PR | feat(workbench-v2): 預錄模式俯視圖 2D/3D 切換（LIVE 式 3D 場景，#605） | — | 已合併 `main`（2026-11-18，`b98fac2a`） |
| [#616](https://github.com/Polalalabear/amidst/pull/616) | PR | test(ui): real-e2e 配合 #564 易讀鏡頭名稱 | — | 已合併 `main`（2026-11-18，`d3dd2d65`，D324） |

### 未完成（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#612](https://github.com/Polalalabear/amidst/issues/612) | Issue | CX-8E 預錄模式提供系統估計位置 est_xy（給 #605 3D 視圖） | — | CX-8E；D318：等 Codex 實作；owner:codex |

### 待確認（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#594](https://github.com/Polalalabear/amidst/issues/594) | Issue | CX-8C 8785 workbench-v2 加 8CAM run | — | #603 已合併（`3b5a987a`）加入 A4-1-8CAM；是否仍需本 issue 待確認；owner:codex |

## W 系列：D126 查找與追蹤核心

### 已完成（61）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#411](https://github.com/Polalalabear/amidst/pull/411) | PR | feat(q1q5): implement D126 core search & track, CX-8 tracking adapter, and cross-platform scripts | — | 關閉未合併（2026-11-08） |
| [#412](https://github.com/Polalalabear/amidst/issues/412) | Issue | W-C1 審查 Argon 的 #411，決定採用範圍 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#413](https://github.com/Polalalabear/amidst/issues/413) | Issue | W-C2 審 #408 增量（6de481d..eb10d4c，倍速自動降速） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#414](https://github.com/Polalalabear/amidst/issues/414) | Issue | W-C3 T2 重渲染 A4-1／B4-1（轉彎會轉身、看得出正反面） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#415](https://github.com/Polalalabear/amidst/issues/415) | Issue | W-C4 把本機建檔／渲染腳本與鏡頭參數整理進 repo（不含 GT） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#416](https://github.com/Polalalabear/amidst/issues/416) | Issue | W-C5 打包給 Argon 的 safe 資料（manifest＋SHA-256，不含 GT） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#417](https://github.com/Polalalabear/amidst/issues/417) | Issue | W-C6 T2 #118 r004 偵測索引與 CX-8 RULE_ONLY（新 run） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#418](https://github.com/Polalalabear/amidst/issues/418) | Issue | W-C7 擴充 Office 場景：多間標註教室＋COCO 物件 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#419](https://github.com/Polalalabear/amidst/issues/419) | Issue | W-A1 Windows 乾淨 clone 基準報告（ensure_env／verify_clean_clone） | — | 已完成關閉（2026-11-08）；owner:argon |
| [#420](https://github.com/Polalalabear/amidst/issues/420) | Issue | W-A2 依 W-C1 判定修 #411 並拆成 feature PR | — | 已完成關閉（2026-11-08）；owner:argon |
| [#421](https://github.com/Polalalabear/amidst/issues/421) | Issue | W-A3 物理預測接線：q_physical_prediction 503 → 盲區曲線 | — | 已完成關閉（2026-11-08）；owner:argon |
| [#422](https://github.com/Polalalabear/amidst/issues/422) | Issue | W-A4 非人物追蹤（契約 O3）：車輛等 COCO 類別 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#423](https://github.com/Polalalabear/amidst/issues/423) | Issue | W-A5 工作台兩核心畫面：查找結果牆、追蹤單畫面／多畫面、俯視圖 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#424](https://github.com/Polalalabear/amidst/issues/424) | Issue | W-A6 Colab 一鍵測試 notebook（環境自檢→資料 sha256→測試→匯出） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#425](https://github.com/Polalalabear/amidst/issues/425) | Issue | W-A7 研究：模型組合 M1～M4 與 baseline 執行與分析 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#426](https://github.com/Polalalabear/amidst/issues/426) | Issue | W-A8 Q4 正式 T／F 評估工具（組員標註包＋計分） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#427](https://github.com/Polalalabear/amidst/issues/427) | Issue | W-A9 研究報告用的分析與圖表腳本 | — | 已完成關閉（2026-11-08）；owner:argon |
| [#428](https://github.com/Polalalabear/amidst/issues/428) | Issue | W-A10 文件對齊：#409 專案文件包 ↔ #410 契約 ↔ 實作 | — | 已完成關閉（2026-11-08）；owner:argon |
| [#429](https://github.com/Polalalabear/amidst/issues/429) | Issue | W-A11 Windows 一鍵啟動 demo 實測（start_all_demo.ps1） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#432](https://github.com/Polalalabear/amidst/issues/432) | Issue | W-K1 Claude 週日一次審查（review:claude 全部） | — | 已完成關閉（2026-11-08）；owner:claude |
| [#433](https://github.com/Polalalabear/amidst/issues/433) | Issue | W-K2 研究報告新初稿（11-09 那週） | — | 已完成關閉（2026-11-08）；owner:claude |
| [#434](https://github.com/Polalalabear/amidst/issues/434) | Issue | 工作總表：Argon／Codex 自取（D127，2026-11-04 起） | — | 已完成關閉（2026-11-08）；owner:codex、owner:argon |
| [#435](https://github.com/Polalalabear/amidst/pull/435) | PR | W-A4 非人物追蹤 O3：class-agnostic linker 與提案 (#422) | — | 關閉未合併（2026-11-08） |
| [#436](https://github.com/Polalalabear/amidst/pull/436) | PR | W-A8 Q4 正式 T/F 標註包與計分工具 (#426) | — | 關閉未合併（2026-11-08） |
| [#437](https://github.com/Polalalabear/amidst/pull/437) | PR | W-A9 研究報告表格與圖表腳本 (#427) | — | 關閉未合併（2026-11-08） |
| [#438](https://github.com/Polalalabear/amidst/pull/438) | PR | W-A6 Colab 一鍵測試 notebook 與 runner (#424) | — | 關閉未合併（2026-11-08） |
| [#439](https://github.com/Polalalabear/amidst/pull/439) | PR | W-A3 物理預測接線：盲區曲線純函式與俯視圖支援 (#421) | — | 關閉未合併（2026-11-08） |
| [#440](https://github.com/Polalalabear/amidst/pull/440) | PR | W-A1 Windows 乾淨 clone 基準報告與環境腳本 (#419) | — | 關閉未合併（2026-11-08） |
| [#442](https://github.com/Polalalabear/amidst/pull/442) | PR | D124: 重渲染 A4/B4 轉身與正反面 safe runs (#414) | — | 關閉未合併（2026-11-08） |
| [#443](https://github.com/Polalalabear/amidst/pull/443) | PR | W-C1: 審查並修復 Argon #411 的來源與接線問題 (#412) | — | 關閉未合併（2026-11-08） |
| [#444](https://github.com/Polalalabear/amidst/pull/444) | PR | W-C2: 倍速審查、播放代理與 Mac 延遲量測 (#413) | — | 關閉未合併（2026-11-08） |
| [#446](https://github.com/Polalalabear/amidst/pull/446) | PR | W-C4: 整理 LOCAL 建檔工具與安全渲染入口 (#415) | — | 關閉未合併（2026-11-08） |
| [#447](https://github.com/Polalalabear/amidst/pull/447) | PR | W-C7: 四教室 Office v2 靜態預覽與來源綁定 graphs (#418) | — | 關閉未合併（2026-11-08） |
| [#449](https://github.com/Polalalabear/amidst/pull/449) | PR | W-C5: Argon safe 資料包與 P1 無損 metadata 副本 (#416) | — | 關閉未合併（2026-11-08） |
| [#451](https://github.com/Polalalabear/amidst/pull/451) | PR | W-A10 文件對齊：專案文件包與契約核對 (#428) | — | 關閉未合併（2026-11-08） |
| [#452](https://github.com/Polalalabear/amidst/pull/452) | PR | W-A5 工作台核心畫面與純函式模型 (#423) | — | 關閉未合併（2026-11-08） |
| [#453](https://github.com/Polalalabear/amidst/pull/453) | PR | feat(q1q5): W-A2 依 W-C1 判定修 #411 並拆成 feature PR (#420) | — | 關閉未合併（2026-11-08） |
| [#454](https://github.com/Polalalabear/amidst/pull/454) | PR | feat(research): W-A7 Baseline and M1~M4 model combination evaluation and analysis (Closes #425) | — | 關閉未合併（2026-11-08） |
| [#455](https://github.com/Polalalabear/amidst/pull/455) | PR | feat(ops): W-A11 Windows demo startup evaluation and fixes (Closes #429) | — | 關閉未合併（2026-11-08） |
| [#457](https://github.com/Polalalabear/amidst/issues/457) | Issue | W-A15 新場景 office_expanded_r005 的 graph 載入與 source-bound 測試（純程式） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#458](https://github.com/Polalalabear/amidst/issues/458) | Issue | W-A16 查找輸入的中文別名：「101 教室」「筆電」→ 區域與 COCO 類別 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#459](https://github.com/Polalalabear/amidst/issues/459) | Issue | W-A17 工作台瀏覽器 E2E 測試（Playwright，合成 API fixture） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#460](https://github.com/Polalalabear/amidst/issues/460) | Issue | W-A18 契約待決 O1、O2、O4 的 PROPOSED 提案（多 run、往回看時長、多教室座標來源） | — | 已完成關閉（2026-11-08）；owner:argon |
| [#461](https://github.com/Polalalabear/amidst/issues/461) | Issue | W-A19 追蹤評估工具：切鏡一致性與跟丟時間（CX-8 輸出格式，合成先行） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#462](https://github.com/Polalalabear/amidst/issues/462) | Issue | W-A20 查找評估工具：case1 命中率（對人工覆蓋標註） | — | 已完成關閉（2026-11-08）；owner:argon |
| [#463](https://github.com/Polalalabear/amidst/issues/463) | Issue | W-A21 兩核心 demo 腳本與操作說明（給展示者） | — | 已完成關閉（2026-11-08）；owner:argon |
| [#464](https://github.com/Polalalabear/amidst/issues/464) | Issue | W-C10 r005 靜態圖：COCO 物件辨識實測與人工覆蓋標註 | — | 已完成關閉（2026-11-08）；owner:codex |
| [#465](https://github.com/Polalalabear/amidst/issues/465) | Issue | W-C11 錄製兩核心 demo 影片（三種事件 × 查看／查找／追蹤單、多畫面） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#466](https://github.com/Polalalabear/amidst/issues/466) | Issue | W-C12 Q4 正式標註包產製（真實資料，給組員） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#467](https://github.com/Polalalabear/amidst/issues/467) | Issue | W-C13 r005 人物短片的參數提案（只寫提案，不渲染） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#468](https://github.com/Polalalabear/amidst/issues/468) | Issue | W-A22 研究報告參考文獻核對（標「待核」的頁次、卷期、作者） | — | 已完成關閉（2026-11-08）；owner:argon |
| [#469](https://github.com/Polalalabear/amidst/issues/469) | Issue | W-A23 查找與追蹤的文字輸入（之後再做，現在延後） | — | 關閉（不處理）（2026-11-08）；owner:argon |
| [#470](https://github.com/Polalalabear/amidst/pull/470) | PR | feat: r005 source-bound graph skeleton and scene selector (#457) | — | 關閉未合併（2026-11-08） |
| [#471](https://github.com/Polalalabear/amidst/pull/471) | PR | feat: Chinese query aliases and pinned region options (#458) | — | 關閉未合併（2026-11-08） |
| [#472](https://github.com/Polalalabear/amidst/pull/472) | PR | feat: proposed case2 tracking evaluation tools (#461) | — | 關閉未合併（2026-11-08） |
| [#473](https://github.com/Polalalabear/amidst/pull/473) | PR | W-C10: r005 static RGB detection probe and partial coverage handoff | — | 關閉未合併（2026-11-08） |
| [#474](https://github.com/Polalalabear/amidst/pull/474) | PR | W-C13: propose bounded r005 person clip parameters | — | 關閉未合併（2026-11-08） |
| [#475](https://github.com/Polalalabear/amidst/pull/475) | PR | DEMO_DEFAULT: 試跑 D124 偵測索引與有界 RULE_ONLY (#417) | — | 關閉未合併（2026-11-08） |
| [#476](https://github.com/Polalalabear/amidst/pull/476) | PR | Mac 合成核心畫面 Playwright E2E (#459) | — | 關閉未合併（2026-11-08） |
| [#477](https://github.com/Polalalabear/amidst/pull/477) | PR | docs(445): persistent independent previews and integration conflict plan | — | 關閉未合併（2026-11-08） |
| [#478](https://github.com/Polalalabear/amidst/pull/478) | PR | feat(417): DEMO_DEFAULT cross-camera replay with source-pinned single view | — | 關閉未合併（2026-11-08） |

## 大掃除、CI 與可攜性（#486）

### 已完成（19）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#430](https://github.com/Polalalabear/amidst/issues/430) | Issue | W-A12 大整理前半：分支與文件盤點、刪除候選清單（不刪） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#431](https://github.com/Polalalabear/amidst/issues/431) | Issue | W-A13 大整理後半：執行刪除與合進 main（等 Claude 審查） | — | 已完成關閉（2026-11-08）；owner:argon |
| [#441](https://github.com/Polalalabear/amidst/pull/441) | PR | W-A12 大整理前半：分支與文件盤點、刪除候選清單（不刪） (#430) | — | 關閉未合併（2026-11-08） |
| [#448](https://github.com/Polalalabear/amidst/issues/448) | Issue | W-C9 本機磁碟清理盤點：重複渲染、無用 .blend、快取（只盤點不刪） | — | 已完成關閉（2026-11-08）；owner:codex |
| [#450](https://github.com/Polalalabear/amidst/pull/450) | PR | docs: #448 本機清理候選與 #441 交叉盤點（不刪除） | — | 關閉未合併（2026-11-08） |
| [#456](https://github.com/Polalalabear/amidst/issues/456) | Issue | W-A14 GitHub Actions：PR 自動跑守門、node、聚焦 pytest | — | 已完成關閉（2026-11-08）；owner:argon |
| [#486](https://github.com/Polalalabear/amidst/issues/486) | Issue | C｜大掃除與可攜性：依賴收編、清理盤點、Windows／Linux、CI | — | 已完成關閉（2026-11-15）；owner:codex |
| [#491](https://github.com/Polalalabear/amidst/pull/491) | PR | [DO NOT MERGE] chore: pin Python 3.12, lock deps, annotate old indexes (Refs #486) | — | 已合併 `claude/445-demo-integration`（2026-11-09） |
| [#501](https://github.com/Polalalabear/amidst/pull/501) | PR | feat(ci): GitHub Actions CI + provenance record script (#486) | — | 已合併 `mainline/q1q5`（2026-11-09） |
| [#503](https://github.com/Polalalabear/amidst/pull/503) | PR | docs(history): D138 artifact ledger and cleanup candidates (no deletions) | — | 已合併 `mainline/q1q5`（2026-11-09） |
| [#506](https://github.com/Polalalabear/amidst/pull/506) | PR | test: fix flaky baseline_runner (disk gate) and e2e comment (D164) | — | 已合併 `mainline/q1q5`（2026-11-10） |
| [#507](https://github.com/Polalalabear/amidst/pull/507) | PR | docs(cleanup): D163 evidence re-check at e85b51e + verification gate results (nothing deleted) | — | 已合併 `mainline/q1q5`（2026-11-09） |
| [#508](https://github.com/Polalalabear/amidst/pull/508) | PR | docs(history): D176 research timeline and branch archive | — | 已合併 `mainline/q1q5`（2026-11-09） |
| [#509](https://github.com/Polalalabear/amidst/pull/509) | PR | feat(paths): repo-relative local paths and AMIDST_ROOT (D171, cleanup step 4) | — | 已合併 `mainline/q1q5`（2026-11-10） |
| [#512](https://github.com/Polalalabear/amidst/pull/512) | PR | merge: mainline/q1q5 into main (D172 step 6, D188) | — | 已合併 `main`（2026-11-10） |
| [#514](https://github.com/Polalalabear/amidst/pull/514) | PR | ci: authority guard base for PRs into main = mainline tip (D188) | — | 已合併 `mainline/q1q5`（2026-11-10） |
| [#517](https://github.com/Polalalabear/amidst/pull/517) | PR | ci: guard base for PRs into main back to the PR base (D200) | — | 已合併 `main`（2026-11-10） |
| [#536](https://github.com/Polalalabear/amidst/pull/536) | PR | ops: 大掃除收尾 — AGENTS/CLAUDE 對齊 main、相對輸出路徑、LOCAL 引用檢查、資料夾收尾交接 (#486) | — | 已合併 `main`（2026-11-15） |
| [#595](https://github.com/Polalalabear/amidst/pull/595) | PR | refactor(office): retire Office display and rehearsal check (#579) | — | 已合併 `main`（2026-11-18，`6bf287d7`） |

### 未完成（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#598](https://github.com/Polalalabear/amidst/issues/598) | Issue | 跨平台：Windows／Linux 執行 demo（延後） | — | 延後（標題無 owner 前綴） |

## 暫停：跨鏡頭盲區 3D 重建線

**已完成（38）**

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
| [#77](https://github.com/Polalalabear/amidst/pull/77) | PR | feat(scene-markers): E 包 受控場景標記範本與 safe 側 validator | — | 關閉未合併（2026-10-26）；Office 時期的 E 包，已過時（盤點留言） |
| [#78](https://github.com/Polalalabear/amidst/pull/78) | PR | feat(cs-b): D47 本機人工審查頁 | — | 關閉未合併 |
| [#81](https://github.com/Polalalabear/amidst/pull/81) | PR | docs(agents): 第二批後端真實資料接入 v2 整合規格（2a–2d） | — | 關閉未合併 |
| [#82](https://github.com/Polalalabear/amidst/pull/82) | PR | feat(eval): K7 r003 static-geometry verification for O10 — do not merge before user approval | — | 關閉未合併（2026-11-08）；原備註：K7 r003 靜態幾何驗證（舊線），標示使用者核准前不合併；D88 決定先留著；r004 改由 #117 檢查，待確認是否關閉 |
| [#84](https://github.com/Polalalabear/amidst/issues/84) | Issue | E1–E5：凍結後評估工具（D56 Q19–Q23） | — | 已完成 |
| [#85](https://github.com/Polalalabear/amidst/issues/85) | Issue | Q11：靜態遮擋邊緣容差 0／1／2／4 px 改判格數比較 | — | 已完成 |


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
