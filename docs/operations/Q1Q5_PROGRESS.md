# Q1–Q5 進度導覽

快照時間：2026-11-01（`gh pr list --state all` 與 `gh issue list --state all` 重算；mainline `0d78599`、staging `434e579`，皆為撰寫時 `origin` 的 head）。資料來源：GitHub 上全部 PR 與 issue。
本文涵蓋 **#1–#382 共 382 項**（含本 PR #382；編號連續，無缺號），每項只列在一個主分類下。過時或已被取代的項目另列在 [廢棄／過時索引](DEPRECATION_INDEX_20261101.md)。
維護方式（D91-4）：本文的列由協調者在 mainline 批次補列，一般 PR／issue 不必各自更新，staging 的 PR 也不改本文；staging 併入 mainline 時，由協調者事後批次解導覽衝突，合併 PR 本身不改本文。即時狀態仍以[任務板 #93](https://github.com/Polalalabear/amidst/issues/93)為準。

## 分類方式

- **主分類：**Q1–Q5 五大問題；無法歸到單一問題的列在「共用」與「流程」；D87 開的第二條線（複雜場景）列在「Line 2 複雜場景」；D97 起新增的 #306 以後（架構基準、CQ 子任務、8 個 feature、demo UI 與規則 PR）列在「D97 後：架構基準、feature 與 demo UI」；2026-10-20 轉向 Q1–Q5 之前的工作列在「暫停」與「歷史」。「也涉及」欄列出其他相關問題。
- **已完成：**PR 已合併，或 issue 已完成關閉。合併進 `codex/q1q5-staging` 的 PR 標「待審入主線」，還沒進 `mainline/q1q5`（staging → mainline 的整合是 [#267](https://github.com/Polalalabear/amidst/pull/267)，Draft）。關閉未合併的 PR 也列在這裡，備註寫明。
- **進行中：**開著的 PR，或程式已有 PR／已併入 staging 的 issue。
- **未完成：**尚未開始、blocked 或等授權的 issue。
- **待確認：**是否保留、合併或關閉還沒決定，例如舊線遺留的 PR、等使用者決定的提案、工作已完成但 issue 還開著。

## 總覽

| 分類 | 已完成 | 進行中 | 未完成 | 待確認 | 合計 |
| --- | ---: | ---: | ---: | ---: | ---: |
| [Q1 依條件找鏡頭](#q1-依條件找鏡頭) | 4 | 0 | 1 | 0 | 5 |
| [Q2 在畫面中找人](#q2-在畫面中找人) | 4 | 0 | 0 | 0 | 4 |
| [Q3 理解使用者語意](#q3-理解使用者語意) | 16 | 3 | 3 | 0 | 22 |
| [Q4 判斷畫面是否含目標](#q4-判斷畫面是否含目標) | 3 | 0 | 4 | 1 | 8 |
| [Q5 決定是否切鏡](#q5-決定是否切鏡) | 15 | 1 | 2 | 2 | 20 |
| [共用：契約、規則、參數與一致性檢查](#共用契約規則參數與一致性檢查) | 21 | 6 | 8 | 1 | 36 |
| [共用：r004 場景、資料、索引與儲存](#共用r004-場景資料索引與儲存) | 22 | 7 | 7 | 0 | 36 |
| [共用：工作台、HTTP 與 Demo](#共用工作台http-與-demo) | 33 | 2 | 3 | 1 | 39 |
| [Line 2 複雜場景](#line-2-複雜場景) | 0 | 16 | 7 | 0 | 23 |
| [流程：任務板、交接與文件](#流程任務板交接與文件) | 29 | 6 | 2 | 1 | 38 |
| [D97 後：架構基準、feature 與 demo UI](#d97-後架構基準feature-與-demo-ui) | 0 | 60 | 16 | 1 | 77 |
| [暫停：跨鏡頭盲區 3D 重建線](#暫停跨鏡頭盲區-3d-重建線) | 37 | 0 | 0 | 1 | 38 |
| [歷史：Office Demo 與 Phase 1／2](#歷史office-demo-與-phase-12) | 36 | 0 | 0 | 0 | 36 |
| **合計** | **220** | **101** | **53** | **8** | **382** |

## 2026-11-01 快照（D95～D108）

### 決策摘要

| 決策 | 內容 |
| --- | --- |
| [D95](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6439940143) | Codex 任務佇列 #279（自取），Claude 負責審查；最低目標：完成複雜事件、組員能自己做模型評測 |
| [D96](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6442431884) | A4-c2、B4-e 先不計分待驗證；CQ-14 評測包重播凍結輸出（Python 3.12）；取消 #129 |
| [D97](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6461090575) | 到 demo 的工作全部開成任務（#306–#346），架構基準 #306；Claude 審查改集中做；車輛計入 Q1 |
| [D98](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6461263003)、[D99](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6461277019) | yyin 回件先用；A4-1／B4-1 與複雜事件甲卡的渲染預先授權（各有三個條件）；評分與打包歸 Codex |
| [D100](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6539701337)、[D100-8](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6539704056) | staging 歷史 pin、A15 例外；demo 目標日改 **2026-11-04**；沒有核准就走 P1 工程 fallback |
| [D101](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6552319555) | G4（#348）採最小範圍選項 A，生效條件 D101-2 |
| [D102](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6552376895) | Codex 佇列暫停等 Claude 審完（11-01 已由「佇列恢復」解除） |
| [D103](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6552386622) | 子任務歸成 8 個 feature 議題，以 feature 為單位認領 |
| [D104](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6552566523) | 一個 feature 一個 PR；整合驗收全綠；Claude 只審四件事；決策分層；demo 前要合併；Actual output 只貼 PR |
| [D105](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6556609083)＋[定案表](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6556607120) | U4 劇本凍結核准（`ab45a832…`）、U7 甲卡、U8 CQ-21a、U6 最小組；feature PR base 是 staging；11-03 批次順序；B-1～B-29 |
| [D106](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6556904620) | 子任務議題移除 `codex-queue`（標籤只留 feature 層級）；關閉 #163 與 9 個議題；5 個 PR 標不在 demo 範圍 |
| [D107](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6557260112) | 俯視圖物理預測（主）＋OpenAI 推測（輔、預設關、錄製重播）的限定例外 |
| [D108](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6557942628) | 規則檔改寫到 D104～D107（本 PR）、#306 pin 同步、`deprecated`／`superseded`／`out-of-demo-scope` 標記與廢棄索引、本機 checkout 規則 |

### 8 個 feature 與子 PR

整合分支都從 staging@`434e579` 開，feature PR 的 base 是 `codex/q1q5-staging`（D105-7）。子 PR 用 `git merge --no-ff` 依下列順序合入；細節與必修清單見各 feature 的歸併留言（D105-8）。11-03 批次順序：FEAT-7 → FEAT-3 → FEAT-2 → FEAT-5 → FEAT-1 → FEAT-4 → FEAT-6 → #240、#261（mainline 直合）→ #267。

| feature | 議題 | 整合分支 | 子 PR（合入順序） | 例外 |
| --- | --- | --- | --- | --- |
| FEAT-1 Baseline 正式鏈 | [#376](https://github.com/Polalalabear/amidst/issues/376)（[歸併](https://github.com/Polalalabear/amidst/issues/376#issuecomment-6556603824)） | `codex/feat-1-baseline` | #294 → #256 → #275 → #295 → #254 → #354 → #353 → #355 → #356 → #357 → #348 | #348 等 D101-2 第 3 步；還缺 #115 → #118 → #194／#202 → #314 |
| FEAT-2 yyin 主包與回件 | [#369](https://github.com/Polalalabear/amidst/issues/369)（[歸併](https://github.com/Polalalabear/amidst/issues/369#issuecomment-6556604125)） | `codex/feat-2-yyin-pack` | #269 → #350 → #359 → #358 → cherry-pick `e7edc98`、`3deee9e`（#361） | #240 mainline 直合；#349 不合（B-5） |
| FEAT-3 組員評測包 | [#370](https://github.com/Polalalabear/amidst/issues/370)（[歸併](https://github.com/Polalalabear/amidst/issues/370#issuecomment-6556604436)） | `codex/feat-3-team-eval` | #359 → #364 → #365 | 鍵名統一（B-10）；#293 builder |
| FEAT-4 複雜事件 | [#371](https://github.com/Polalalabear/amidst/issues/371)（[歸併](https://github.com/Polalalabear/amidst/issues/371#issuecomment-6556604761)） | `codex/feat-4-complex` | #266 → #271 → #258 → #360 → #366 → #362 → #254 → #367 → #363 → #294 → #272 → #260 → #351 → #352 → #243 → #255 → #273 | #261 mainline 直合；#274 不合（B-6） |
| FEAT-5 demo 工程 | [#372](https://github.com/Polalalabear/amidst/issues/372)（[歸併](https://github.com/Polalalabear/amidst/issues/372#issuecomment-6556605033)） | `codex/feat-5-demo` | #243 → #255 → #368 → #337 → #338 → #124 → #339 → #341 | #337 已認領 |
| FEAT-6 v2 回應與消費端 | [#373](https://github.com/Polalalabear/amidst/issues/373)（[歸併](https://github.com/Polalalabear/amidst/issues/373#issuecomment-6556605282)） | `codex/feat-6-response-v2` | #260 → #278 → #305 → #127 → #277 | 負責 A15 與 kit 下游 pin（B-20～B-22）；#267 排批次最後 |
| FEAT-7 架構守門 | [#374](https://github.com/Polalalabear/amidst/issues/374)（[歸併](https://github.com/Polalalabear/amidst/issues/374#issuecomment-6556605581)） | `codex/feat-7-arch-guard` | 無子 PR；#307 test-first | 批次第一 |
| FEAT-8 stretch | [#375](https://github.com/Polalalabear/amidst/issues/375)（[歸併](https://github.com/Polalalabear/amidst/issues/375#issuecomment-6556605861)） | — | #342～#345 | stretch |

### Claude 的新 PR（11-01）

| PR | 內容 | base |
| --- | --- | --- |
| [#377](https://github.com/Polalalabear/amidst/pull/377) | K-UI-1：workbench-v2 檢索彈窗與 search phase 狀態機 | `codex/q1q5-staging` |
| [#378](https://github.com/Polalalabear/amidst/pull/378) | K-UI-2：監控牆＋後台頁 | `codex/q1q5-staging` |
| [#379](https://github.com/Polalalabear/amidst/pull/379) | 相關工作與定位（研究文件） | `mainline/q1q5` |
| [#380](https://github.com/Polalalabear/amidst/pull/380) | 測試先行規格 `DEMO_UI_SUPPORT_V1`（PROPOSED）、-T、物理預測純模組（D107-4） | `codex/q1q5-staging` |
| [#381](https://github.com/Polalalabear/amidst/pull/381) | UI-C：追蹤模式俯視圖與物理預測虛線 | `codex/q1q5-staging` |
| [#382](https://github.com/Polalalabear/amidst/pull/382) | 本 PR：規則改寫、廢棄索引、本導覽刷新（D108） | `mainline/q1q5` |

### 11-01 關閉與標記

- 關閉未合併的 PR：#163（被 #227、#235、#294 取代）。
- 關閉的議題：#97、#98、#109、#131、#183、#184、#198、#204、#206（D106-2，附 merge SHA）；#110～#113、#200（D106 記為未抽查）；#133（B-14）；#208、#210、#283、#292（FEAT-7 歸併、CQ-04／CQ-13 完成）。
- 待合併後關閉：#144（B-15）；#153、#156、#170、#178（B-14）。
- 標記（D108-3，見[廢棄索引](DEPRECATION_INDEX_20261101.md)）：`out-of-demo-scope`：#268、#189、#158、#83、#82、#274、#249、#290；`superseded`：#163、#349、#361；`deprecated`：#87。

## 最近改動（2026-10-23 起）

- 2026-11-01 本 PR（#382，D108）：快照擴大到 #1–#382；新增「D97 後：架構基準、feature 與 demo UI」分類（#306–#382）與上方 11-01 快照；D106 與 11-01 關閉的 21 項移到已完成（#97、#98、#109～#113、#131、#133、#163、#183、#184、#198、#200、#204、#206、#208、#210、#276、#283、#292）。
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

### 已完成（4）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| [#109](https://github.com/Polalalabear/amidst/issues/109) | Issue | QT-16：Q1 依條件找相機（查詢模組＋類別別名表） | — | 2026-11-01 已完成關閉（D106-2，關閉留言附 merge SHA） |
| --- | --- | --- | --- | --- |
| [#164](https://github.com/Polalalabear/amidst/pull/164) | PR | Q1 evaluator for human expected cores and pinned frozen schemas (code only) | — | 已併入 staging，待審入主線 |
| [#157](https://github.com/Polalalabear/amidst/pull/157) | PR | Q1 index search and scoped pagination（依 #144 提案；blocked #156） | — | 已併入 staging（`15c0f79`），待審入主線 |
| [#224](https://github.com/Polalalabear/amidst/pull/224) | PR | CX-2／#164：隔離合成分母，補 Q1 請求與分頁檢查 | — | 已併入 staging（`08d4793`），待審入主線 |

### 未完成（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#138](https://github.com/Polalalabear/amidst/issues/138) | Issue | QT-37：組員 Q1 條件查詢測試集與評分器（SYNTHETIC） | — | 組員 Q1 測試集未交；評估器已併入 staging（#164） |

**其他分類中也涉及 Q1 的項目：**

- 已完成：[#86](https://github.com/Polalalabear/amidst/pull/86)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#100](https://github.com/Polalalabear/amidst/issues/100)、[#101](https://github.com/Polalalabear/amidst/issues/101)、[#102](https://github.com/Polalalabear/amidst/issues/102)、[#103](https://github.com/Polalalabear/amidst/issues/103)、[#112](https://github.com/Polalalabear/amidst/issues/112)、[#113](https://github.com/Polalalabear/amidst/issues/113)、[#119](https://github.com/Polalalabear/amidst/issues/119)、[#120](https://github.com/Polalalabear/amidst/issues/120)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#126](https://github.com/Polalalabear/amidst/pull/126)、[#133](https://github.com/Polalalabear/amidst/issues/133)、[#134](https://github.com/Polalalabear/amidst/pull/134)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#136](https://github.com/Polalalabear/amidst/pull/136)、[#139](https://github.com/Polalalabear/amidst/pull/139)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#146](https://github.com/Polalalabear/amidst/issues/146)、[#147](https://github.com/Polalalabear/amidst/issues/147)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#149](https://github.com/Polalalabear/amidst/pull/149)、[#151](https://github.com/Polalalabear/amidst/pull/151)、[#152](https://github.com/Polalalabear/amidst/pull/152)、[#155](https://github.com/Polalalabear/amidst/pull/155)、[#161](https://github.com/Polalalabear/amidst/pull/161)、[#167](https://github.com/Polalalabear/amidst/pull/167)、[#173](https://github.com/Polalalabear/amidst/pull/173)、[#175](https://github.com/Polalalabear/amidst/pull/175)、[#176](https://github.com/Polalalabear/amidst/pull/176)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#196](https://github.com/Polalalabear/amidst/issues/196)、[#197](https://github.com/Polalalabear/amidst/pull/197)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#204](https://github.com/Polalalabear/amidst/issues/204)、[#205](https://github.com/Polalalabear/amidst/pull/205)、[#206](https://github.com/Polalalabear/amidst/issues/206)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#221](https://github.com/Polalalabear/amidst/pull/221)、[#226](https://github.com/Polalalabear/amidst/pull/226)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#236](https://github.com/Polalalabear/amidst/pull/236)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#257](https://github.com/Polalalabear/amidst/pull/257)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#240](https://github.com/Polalalabear/amidst/pull/240)、[#243](https://github.com/Polalalabear/amidst/pull/243)、[#260](https://github.com/Polalalabear/amidst/pull/260)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#269](https://github.com/Polalalabear/amidst/pull/269)、[#277](https://github.com/Polalalabear/amidst/pull/277)、[#278](https://github.com/Polalalabear/amidst/pull/278)、[#303](https://github.com/Polalalabear/amidst/issues/303)、[#305](https://github.com/Polalalabear/amidst/pull/305)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#118](https://github.com/Polalalabear/amidst/issues/118)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#156](https://github.com/Polalalabear/amidst/issues/156)、[#284](https://github.com/Polalalabear/amidst/issues/284)、[#285](https://github.com/Polalalabear/amidst/issues/285)、[#296](https://github.com/Polalalabear/amidst/issues/296)、[#297](https://github.com/Polalalabear/amidst/issues/297)、[#300](https://github.com/Polalalabear/amidst/issues/300)、[#302](https://github.com/Polalalabear/amidst/issues/302)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#194](https://github.com/Polalalabear/amidst/issues/194)

## Q2 在畫面中找人

### 已完成（4）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#71](https://github.com/Polalalabear/amidst/pull/71) | PR | feat(workbench): player-grid pure module for 1/2/4/8 synced tiles | — | 已合併主線 |
| [#141](https://github.com/Polalalabear/amidst/pull/141) | PR | Q1–Q5 #107: 同鏡頭 selected-seed IoU 連接器與缺格邊界。 | — | 已合進主線（第 1 批，2026-10-25） |
| [#107](https://github.com/Polalalabear/amidst/issues/107) | Issue | QT-14：同鏡頭最小 IoU 連接器與暫失觸發 | — | 已完成關閉（2026-10-26）；原備註：同鏡頭 IoU 連接器已併入 staging（#141），待審入主線 |
| [#262](https://github.com/Polalalabear/amidst/pull/262) | PR | docs(p1): frame-by-frame diagnosis of 28 reported detection/link gaps | Q4、Q5 | 已併入 staging（`434e579`），待審入主線 |

**其他分類中也涉及 Q2 的項目：**

- 已完成：[#75](https://github.com/Polalalabear/amidst/pull/75)、[#80](https://github.com/Polalalabear/amidst/pull/80)、[#86](https://github.com/Polalalabear/amidst/pull/86)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#100](https://github.com/Polalalabear/amidst/issues/100)、[#101](https://github.com/Polalalabear/amidst/issues/101)、[#102](https://github.com/Polalalabear/amidst/issues/102)、[#104](https://github.com/Polalalabear/amidst/issues/104)、[#110](https://github.com/Polalalabear/amidst/issues/110)、[#112](https://github.com/Polalalabear/amidst/issues/112)、[#113](https://github.com/Polalalabear/amidst/issues/113)、[#119](https://github.com/Polalalabear/amidst/issues/119)、[#121](https://github.com/Polalalabear/amidst/issues/121)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#132](https://github.com/Polalalabear/amidst/pull/132)、[#133](https://github.com/Polalalabear/amidst/issues/133)、[#134](https://github.com/Polalalabear/amidst/pull/134)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#136](https://github.com/Polalalabear/amidst/pull/136)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#150](https://github.com/Polalalabear/amidst/pull/150)、[#152](https://github.com/Polalalabear/amidst/pull/152)、[#155](https://github.com/Polalalabear/amidst/pull/155)、[#163](https://github.com/Polalalabear/amidst/pull/163)、[#166](https://github.com/Polalalabear/amidst/pull/166)、[#169](https://github.com/Polalalabear/amidst/pull/169)、[#173](https://github.com/Polalalabear/amidst/pull/173)、[#175](https://github.com/Polalalabear/amidst/pull/175)、[#177](https://github.com/Polalalabear/amidst/pull/177)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#184](https://github.com/Polalalabear/amidst/issues/184)、[#185](https://github.com/Polalalabear/amidst/pull/185)、[#187](https://github.com/Polalalabear/amidst/pull/187)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#203](https://github.com/Polalalabear/amidst/pull/203)、[#206](https://github.com/Polalalabear/amidst/issues/206)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#208](https://github.com/Polalalabear/amidst/issues/208)、[#209](https://github.com/Polalalabear/amidst/pull/209)、[#210](https://github.com/Polalalabear/amidst/issues/210)、[#211](https://github.com/Polalalabear/amidst/pull/211)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#216](https://github.com/Polalalabear/amidst/pull/216)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#227](https://github.com/Polalalabear/amidst/pull/227)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#235](https://github.com/Polalalabear/amidst/pull/235)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#238](https://github.com/Polalalabear/amidst/pull/238)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#257](https://github.com/Polalalabear/amidst/pull/257)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#243](https://github.com/Polalalabear/amidst/pull/243)、[#247](https://github.com/Polalalabear/amidst/issues/247)、[#260](https://github.com/Polalalabear/amidst/pull/260)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#269](https://github.com/Polalalabear/amidst/pull/269)、[#273](https://github.com/Polalalabear/amidst/pull/273)、[#277](https://github.com/Polalalabear/amidst/pull/277)、[#278](https://github.com/Polalalabear/amidst/pull/278)、[#303](https://github.com/Polalalabear/amidst/issues/303)、[#305](https://github.com/Polalalabear/amidst/pull/305)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#114](https://github.com/Polalalabear/amidst/issues/114)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#116](https://github.com/Polalalabear/amidst/issues/116)、[#117](https://github.com/Polalalabear/amidst/issues/117)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#178](https://github.com/Polalalabear/amidst/issues/178)、[#285](https://github.com/Polalalabear/amidst/issues/285)、[#291](https://github.com/Polalalabear/amidst/issues/291)、[#296](https://github.com/Polalalabear/amidst/issues/296)、[#297](https://github.com/Polalalabear/amidst/issues/297)、[#300](https://github.com/Polalalabear/amidst/issues/300)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#158](https://github.com/Polalalabear/amidst/pull/158)、[#194](https://github.com/Polalalabear/amidst/issues/194)、[#202](https://github.com/Polalalabear/amidst/issues/202)、[#218](https://github.com/Polalalabear/amidst/issues/218)

## Q3 理解使用者語意

### 已完成（16）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| [#198](https://github.com/Polalalabear/amidst/issues/198) | Issue | Baseline 前置：最小 Q3 八題候選與獨立審核回收 | — | 2026-11-01 已完成關閉（D106-2，關閉留言附 merge SHA） |
| [#204](https://github.com/Polalalabear/amidst/issues/204) | Issue | 完整 baseline 條線 B：核定輸入與 Q3 人審回收 | Q1、Q4 | 2026-11-01 已完成關閉（D106-2，關閉留言附 merge SHA） |
| --- | --- | --- | --- | --- |
| [#140](https://github.com/Polalalabear/amidst/pull/140) | PR | feat(q1q5): audited loopback Ollama provider | Q5 | 已合進主線（第 1 批，2026-10-25） |
| [#149](https://github.com/Polalalabear/amidst/pull/149) | PR | docs(evaluation): #146 Q1 Q3 question authoring boundaries | Q1 | 已併入 staging，待審入主線 |
| [#152](https://github.com/Polalalabear/amidst/pull/152) | PR | feat(q1q5): #106 literal Q3 parsing and audited deterministic fallback | Q1、Q2 | 已併入 staging，待審入主線 |
| [#165](https://github.com/Polalalabear/amidst/pull/165) | PR | Q3 human-annotation evaluator with exact pinned source clocks (code only) | — | 已併入 staging，待審入主線 |
| [#105](https://github.com/Polalalabear/amidst/issues/105) | Issue | QT-12：Ollama 薄 provider（Q3／Q5 共用） | Q5 | 已完成關閉（2026-10-26）；原備註：Ollama provider 已併入 staging（#140），待審入主線 |
| [#106](https://github.com/Polalalabear/amidst/issues/106) | Issue | QT-13：Q3 解析：規則解析器、LLM 解析與兜底 | — | 已完成關閉（2026-10-26）；原備註：規則解析與兜底已併入 staging（#152）；LLM 解析等 Qwen3（#174、#186） |
| [#146](https://github.com/Polalalabear/amidst/issues/146) | Issue | QT-41：組員出題依據文件（格式、可填資料、找得到／找不到） | Q1 | 已完成關閉（2026-10-26）；原備註：出題指南已併入 staging（#149） |
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
| [#240](https://github.com/Polalalabear/amidst/pull/240) | PR（Draft） | docs(q1q3): yyin Q1／Q3 出題包設計稿（D80） | Q1 | Draft；yyin Q1／Q3 出題包設計稿（D80）；衝突已解（D88）；head `447da6c`，Claude 審查 NEEDS_CHANGES，已退回 CQ-05 [#284](https://github.com/Polalalabear/amidst/issues/284)（合併順序仍是 #276 → #240，D96-3） |
| [#269](https://github.com/Polalalabear/amidst/pull/269) | PR（Draft） | docs(evaluation): D86-2 selected-run time defaults in question guide | Q1、Q2 | Draft；D86-2 缺時間預設整段 run 的出題指南（base staging）；Claude 審查 NEEDS_CHANGES，已退回 CQ-06 [#285](https://github.com/Polalalabear/amidst/issues/285) |

### 未完成（3）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#89](https://github.com/Polalalabear/amidst/issues/89) | Issue | Q3：語意解析測試集與評分器（組員） | — | 組員 Q3 測試集未交；評分器已併入 staging（#165） |
| [#284](https://github.com/Polalalabear/amidst/issues/284) | Issue | CQ-05 修 #240：依 Opus 再審與使用者決定（P2-1～P2-4、P3-1～P3-6） | Q1 | CQ-05；#240 審查 NEEDS_CHANGES 退回此議題；D96-3 解除排在 CQ-04 之後的限制 |
| [#285](https://github.com/Polalalabear/amidst/issues/285) | Issue | CQ-06 修 #269：刪文件內 Actual output、補 D92-2 與過期句 | Q1、Q2 | CQ-06；#269 審查 NEEDS_CHANGES 退回此議題 |

### 待確認（0）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |

**其他分類中也涉及 Q3 的項目：**

- 已完成：[#86](https://github.com/Polalalabear/amidst/pull/86)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#101](https://github.com/Polalalabear/amidst/issues/101)、[#112](https://github.com/Polalalabear/amidst/issues/112)、[#119](https://github.com/Polalalabear/amidst/issues/119)、[#120](https://github.com/Polalalabear/amidst/issues/120)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#126](https://github.com/Polalalabear/amidst/pull/126)、[#133](https://github.com/Polalalabear/amidst/issues/133)、[#134](https://github.com/Polalalabear/amidst/pull/134)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#147](https://github.com/Polalalabear/amidst/issues/147)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#151](https://github.com/Polalalabear/amidst/pull/151)、[#173](https://github.com/Polalalabear/amidst/pull/173)、[#176](https://github.com/Polalalabear/amidst/pull/176)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#203](https://github.com/Polalalabear/amidst/pull/203)、[#206](https://github.com/Polalalabear/amidst/issues/206)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#214](https://github.com/Polalalabear/amidst/pull/214)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#226](https://github.com/Polalalabear/amidst/pull/226)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#257](https://github.com/Polalalabear/amidst/pull/257)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#260](https://github.com/Polalalabear/amidst/pull/260)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#277](https://github.com/Polalalabear/amidst/pull/277)、[#278](https://github.com/Polalalabear/amidst/pull/278)、[#303](https://github.com/Polalalabear/amidst/issues/303)、[#305](https://github.com/Polalalabear/amidst/pull/305)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#296](https://github.com/Polalalabear/amidst/issues/296)、[#297](https://github.com/Polalalabear/amidst/issues/297)、[#300](https://github.com/Polalalabear/amidst/issues/300)、[#302](https://github.com/Polalalabear/amidst/issues/302)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#194](https://github.com/Polalalabear/amidst/issues/194)、[#202](https://github.com/Polalalabear/amidst/issues/202)

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

- 已完成：[#86](https://github.com/Polalalabear/amidst/pull/86)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#103](https://github.com/Polalalabear/amidst/issues/103)、[#113](https://github.com/Polalalabear/amidst/issues/113)、[#121](https://github.com/Polalalabear/amidst/issues/121)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#132](https://github.com/Polalalabear/amidst/pull/132)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#136](https://github.com/Polalalabear/amidst/pull/136)、[#139](https://github.com/Polalalabear/amidst/pull/139)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#147](https://github.com/Polalalabear/amidst/issues/147)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#151](https://github.com/Polalalabear/amidst/pull/151)、[#155](https://github.com/Polalalabear/amidst/pull/155)、[#161](https://github.com/Polalalabear/amidst/pull/161)、[#177](https://github.com/Polalalabear/amidst/pull/177)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#196](https://github.com/Polalalabear/amidst/issues/196)、[#197](https://github.com/Polalalabear/amidst/pull/197)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#203](https://github.com/Polalalabear/amidst/pull/203)、[#204](https://github.com/Polalalabear/amidst/issues/204)、[#205](https://github.com/Polalalabear/amidst/pull/205)、[#206](https://github.com/Polalalabear/amidst/issues/206)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#226](https://github.com/Polalalabear/amidst/pull/226)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#262](https://github.com/Polalalabear/amidst/pull/262)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#277](https://github.com/Polalalabear/amidst/pull/277)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#118](https://github.com/Polalalabear/amidst/issues/118)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#153](https://github.com/Polalalabear/amidst/issues/153)、[#300](https://github.com/Polalalabear/amidst/issues/300)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#194](https://github.com/Polalalabear/amidst/issues/194)、[#202](https://github.com/Polalalabear/amidst/issues/202)

## Q5 決定是否切鏡

### 已完成（15）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| [#110](https://github.com/Polalalabear/amidst/issues/110) | Issue | QT-17：Q5 Controller：狀態機與 RULE_ONLY 決定性切鏡 | Q2 | 2026-11-01 關閉（D106 記為未抽查；完成處見關閉留言，11-05 抽查） |
| [#111](https://github.com/Polalalabear/amidst/issues/111) | Issue | QT-18：Q5 AGENT_SEQUENTIAL：typed tools 與有界輪詢 | — | 2026-11-01 關閉（D106 記為未抽查；完成處見關閉留言，11-05 抽查） |
| [#163](https://github.com/Polalalabear/amidst/pull/163) | PR | r004 static graph and eight exit ROI proposals (G4 pending) | Q2 | 2026-11-01 關閉未合併；被 #227 圖 v3、#235、#294 v3_1 取代（D106-2；標 `superseded`） |
| [#184](https://github.com/Polalalabear/amidst/issues/184) | Issue | Q5 雙模式工程比較：後端 FOUND／LOST 與 Agent 候選決策 | Q2 | 2026-11-01 已完成關閉（D106-2，關閉留言附 merge SHA） |
| --- | --- | --- | --- | --- |
| [#150](https://github.com/Polalalabear/amidst/pull/150) | PR | feat(q1q5): #104 pinned static graph validation and D28 candidates | Q2 | 已併入 staging，待審入主線 |
| [#160](https://github.com/Polalalabear/amidst/pull/160) | PR | Q5 evaluator verifies frozen outputs before reading evaluation script (code only) | — | 已併入 staging，待審入主線 |
| [#166](https://github.com/Polalalabear/amidst/pull/166) | PR | Restrict candidate run cameras before D28 ranking and top-k | Q2 | 已併入 staging，待審入主線 |
| [#104](https://github.com/Polalalabear/amidst/issues/104) | Issue | QT-11：兩層圖 schema／loader 與 D28 候選排序 | Q2 | 已完成關閉（2026-10-26）；原備註：靜態圖驗證與 D28 候選已併入 staging（#150、#166），待審入主線 |
| [#169](https://github.com/Polalalabear/amidst/pull/169) | PR | Q5 RULE_ONLY controller（依 #144 提案；blocked #145/#153） | Q2 | 已併入 staging（`efad835`），待審入主線 |
| [#172](https://github.com/Polalalabear/amidst/pull/172) | PR | feat(q5): sequential Agent, versioned guidance profiles and exact replay | — | 已併入 staging（`c0a1ce3`），待審入主線 |
| [#185](https://github.com/Polalalabear/amidst/pull/185) | PR | feat(q1q5): event-mode comparison and reproducible baseline telemetry | Q2 | 已併入 staging（`d8e6935`），待審入主線 |
| [#229](https://github.com/Polalalabear/amidst/pull/229) | PR | docs(q5): Q5 逐事件決策窗（D79 核定版） | — | 已合併主線（`f5168f6`，2026-10-26）；D79 核定的決策窗文件 |
| [#203](https://github.com/Polalalabear/amidst/pull/203) | PR | Connect same RGB detector index to Qwen/RULE baseline | Q2、Q3、Q4 | 已併入 staging（`10e94d6`），待審入主線 |
| [#222](https://github.com/Polalalabear/amidst/pull/222) | PR | CX-2／#160：Q5 拒絕空覆蓋得分，分列決策來源 | — | 已併入 staging（`0043097`），待審入主線 |
| [#129](https://github.com/Polalalabear/amidst/issues/129) | Issue | QT-33：組員 Q5 切鏡評估器 | — | 已取消（D96-4，2026-10-27，CLOSED／NOT_PLANNED）：組員之後當評測者，先寫答案會失去獨立性，Q5 參考答案改由我方從凍結劇本產生；原備註：組員 Q5 情境未交；評估器已併入 staging（#160） |

### 進行中（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#189](https://github.com/Polalalabear/amidst/pull/189) | PR（Draft） | Q5：As-Is Statechart 與獨立 Journal Invariants 驗證 | — | Draft（10-23 新增），Q5 As-Is 狀態圖與 journal 不變量檢查 |

### 未完成（2）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#116](https://github.com/Polalalabear/amidst/issues/116) | Issue | QT-23：r004 兩層圖資料與出口 ROI（靜態） | Q2 | blocked：兩層圖與出口 ROI #163（Draft）待 G4 |
| [#117](https://github.com/Polalalabear/amidst/issues/117) | Issue | QT-24：r004 靜態圖獨立檢查（K7 類型） | Q2 | 收據已出；圖 v3（#227、#235）已併入 staging，G4 未核 |

### 待確認（2）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#202](https://github.com/Polalalabear/amidst/issues/202) | Issue | 完整 baseline 條線 A：同源 RGB→真 RT-DETR→Qwen／RULE／replay | Q2、Q3、Q4 | 對應 PR #203 已併入 staging；issue 仍開著，是否關閉待確認 |
| [#218](https://github.com/Polalalabear/amidst/issues/218) | Issue | [Q2／Q5] 同鏡頭暫失後接不回：漏檢即暫失、回原鏡頭只比對凍結框（#216 審查發現） | Q2 | 同鏡頭暫失後接不回；D90-1：暫失 ≥ 1.8 s 歸 Line 2；P1 逐格診斷 #262 已併入 staging；issue 仍開著，是否關閉待確認 |

**其他分類中也涉及 Q5 的項目：**

- 已完成：[#86](https://github.com/Polalalabear/amidst/pull/86)、[#90](https://github.com/Polalalabear/amidst/pull/90)、[#92](https://github.com/Polalalabear/amidst/pull/92)、[#94](https://github.com/Polalalabear/amidst/issues/94)、[#95](https://github.com/Polalalabear/amidst/issues/95)、[#96](https://github.com/Polalalabear/amidst/issues/96)、[#97](https://github.com/Polalalabear/amidst/issues/97)、[#98](https://github.com/Polalalabear/amidst/issues/98)、[#105](https://github.com/Polalalabear/amidst/issues/105)、[#121](https://github.com/Polalalabear/amidst/issues/121)、[#122](https://github.com/Polalalabear/amidst/issues/122)、[#125](https://github.com/Polalalabear/amidst/pull/125)、[#126](https://github.com/Polalalabear/amidst/pull/126)、[#132](https://github.com/Polalalabear/amidst/pull/132)、[#135](https://github.com/Polalalabear/amidst/pull/135)、[#140](https://github.com/Polalalabear/amidst/pull/140)、[#142](https://github.com/Polalalabear/amidst/pull/142)、[#148](https://github.com/Polalalabear/amidst/pull/148)、[#161](https://github.com/Polalalabear/amidst/pull/161)、[#168](https://github.com/Polalalabear/amidst/pull/168)、[#171](https://github.com/Polalalabear/amidst/pull/171)、[#174](https://github.com/Polalalabear/amidst/pull/174)、[#177](https://github.com/Polalalabear/amidst/pull/177)、[#180](https://github.com/Polalalabear/amidst/pull/180)、[#181](https://github.com/Polalalabear/amidst/pull/181)、[#182](https://github.com/Polalalabear/amidst/pull/182)、[#183](https://github.com/Polalalabear/amidst/issues/183)、[#187](https://github.com/Polalalabear/amidst/pull/187)、[#192](https://github.com/Polalalabear/amidst/issues/192)、[#193](https://github.com/Polalalabear/amidst/pull/193)、[#195](https://github.com/Polalalabear/amidst/pull/195)、[#200](https://github.com/Polalalabear/amidst/issues/200)、[#201](https://github.com/Polalalabear/amidst/pull/201)、[#206](https://github.com/Polalalabear/amidst/issues/206)、[#207](https://github.com/Polalalabear/amidst/pull/207)、[#208](https://github.com/Polalalabear/amidst/issues/208)、[#209](https://github.com/Polalalabear/amidst/pull/209)、[#210](https://github.com/Polalalabear/amidst/issues/210)、[#211](https://github.com/Polalalabear/amidst/pull/211)、[#214](https://github.com/Polalalabear/amidst/pull/214)、[#215](https://github.com/Polalalabear/amidst/pull/215)、[#216](https://github.com/Polalalabear/amidst/pull/216)、[#219](https://github.com/Polalalabear/amidst/pull/219)、[#220](https://github.com/Polalalabear/amidst/pull/220)、[#227](https://github.com/Polalalabear/amidst/pull/227)、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#230](https://github.com/Polalalabear/amidst/pull/230)、[#231](https://github.com/Polalalabear/amidst/pull/231)、[#233](https://github.com/Polalalabear/amidst/pull/233)、[#234](https://github.com/Polalalabear/amidst/pull/234)、[#235](https://github.com/Polalalabear/amidst/pull/235)、[#237](https://github.com/Polalalabear/amidst/pull/237)、[#238](https://github.com/Polalalabear/amidst/pull/238)、[#239](https://github.com/Polalalabear/amidst/pull/239)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#253](https://github.com/Polalalabear/amidst/pull/253)、[#259](https://github.com/Polalalabear/amidst/pull/259)、[#262](https://github.com/Polalalabear/amidst/pull/262)、[#270](https://github.com/Polalalabear/amidst/pull/270)、[#276](https://github.com/Polalalabear/amidst/pull/276)
- 進行中：[#93](https://github.com/Polalalabear/amidst/issues/93)、[#127](https://github.com/Polalalabear/amidst/pull/127)、[#144](https://github.com/Polalalabear/amidst/issues/144)、[#186](https://github.com/Polalalabear/amidst/issues/186)、[#244](https://github.com/Polalalabear/amidst/issues/244)、[#245](https://github.com/Polalalabear/amidst/issues/245)、[#246](https://github.com/Polalalabear/amidst/issues/246)、[#248](https://github.com/Polalalabear/amidst/issues/248)、[#249](https://github.com/Polalalabear/amidst/issues/249)、[#251](https://github.com/Polalalabear/amidst/issues/251)、[#254](https://github.com/Polalalabear/amidst/pull/254)、[#255](https://github.com/Polalalabear/amidst/pull/255)、[#256](https://github.com/Polalalabear/amidst/pull/256)、[#258](https://github.com/Polalalabear/amidst/pull/258)、[#261](https://github.com/Polalalabear/amidst/pull/261)、[#263](https://github.com/Polalalabear/amidst/issues/263)、[#266](https://github.com/Polalalabear/amidst/pull/266)、[#271](https://github.com/Polalalabear/amidst/pull/271)、[#272](https://github.com/Polalalabear/amidst/pull/272)、[#274](https://github.com/Polalalabear/amidst/pull/274)、[#275](https://github.com/Polalalabear/amidst/pull/275)、[#277](https://github.com/Polalalabear/amidst/pull/277)、[#280](https://github.com/Polalalabear/amidst/issues/280)、[#282](https://github.com/Polalalabear/amidst/issues/282)、[#294](https://github.com/Polalalabear/amidst/pull/294)、[#295](https://github.com/Polalalabear/amidst/pull/295)
- 未完成：[#99](https://github.com/Polalalabear/amidst/issues/99)、[#115](https://github.com/Polalalabear/amidst/issues/115)、[#124](https://github.com/Polalalabear/amidst/issues/124)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#145](https://github.com/Polalalabear/amidst/issues/145)、[#170](https://github.com/Polalalabear/amidst/issues/170)、[#178](https://github.com/Polalalabear/amidst/issues/178)、[#281](https://github.com/Polalalabear/amidst/issues/281)、[#287](https://github.com/Polalalabear/amidst/issues/287)、[#288](https://github.com/Polalalabear/amidst/issues/288)、[#289](https://github.com/Polalalabear/amidst/issues/289)、[#290](https://github.com/Polalalabear/amidst/issues/290)、[#293](https://github.com/Polalalabear/amidst/issues/293)、[#298](https://github.com/Polalalabear/amidst/issues/298)、[#299](https://github.com/Polalalabear/amidst/issues/299)、[#300](https://github.com/Polalalabear/amidst/issues/300)、[#301](https://github.com/Polalalabear/amidst/issues/301)、[#304](https://github.com/Polalalabear/amidst/issues/304)
- 待確認：[#88](https://github.com/Polalalabear/amidst/issues/88)、[#194](https://github.com/Polalalabear/amidst/issues/194)

## 共用：契約、規則、參數與一致性檢查

### 已完成（21）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| [#98](https://github.com/Polalalabear/amidst/issues/98) | Issue | QT-05：§11 參數組 v1 提案（HSV 除外） | Q1、Q2、Q3、Q5 | 2026-11-01 已完成關閉（D106-2，關閉留言附 merge SHA） |
| [#133](https://github.com/Polalalabear/amidst/issues/133) | Issue | Conformance kit: CLOCK_MAPPING_RULES rejects an explicit DST fold offset | Q1、Q2、Q3 | 2026-11-01 關閉（D105 B-14：v0.2.1 `994d34c` 已修） |
| [#183](https://github.com/Polalalabear/amidst/issues/183) | Issue | [契約缺口] 空候選證據無法合法 NEXT_CANDIDATE，阻斷 Agent top-k 輪詢 | Q5 | 2026-11-01 已完成關閉（D106-2，關閉留言附 merge SHA） |
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

### 進行中（6）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#127](https://github.com/Polalalabear/amidst/pull/127) | PR（Draft） | feat(evaluation): Q1–Q5 contract conformance kit (draft) | Q1、Q2、Q3、Q4、Q5 | 一致性檢查包（Draft，head `e1415f3`，2026-10-28，Claude 審查 PASS_WITH_NOTES）；AC7 仍未通過（NOT_ACCEPTED）；重錄見 [#277](https://github.com/Polalalabear/amidst/pull/277)，收尾見 CQ-19 [#300](https://github.com/Polalalabear/amidst/issues/300) |
| [#144](https://github.com/Polalalabear/amidst/issues/144) | Issue | QT-39：契約 #135 補完（寫入 D69＋處理 Codex 跳過原因） | Q1、Q2、Q3、Q4、Q5 | §14 選項已併入 staging（#148、#161、#168、#171、#173、#179），待寫回 #135 |
| [#260](https://github.com/Polalalabear/amidst/pull/260) | PR（Draft） | docs(contract): U37 examples, link v2 note and D86/G4 interface proposals | Q1、Q2、Q3 | Draft；U37 範例、link v2 註記與 D86／G4 介面提案；D92 的 #260-A／C／B 待套用（base staging）；Claude 審查 PASS_WITH_NOTES；D92／零邊 authority 與 G4 回條格式修正見 CQ-16 [#297](https://github.com/Polalalabear/amidst/issues/297) |
| [#278](https://github.com/Polalalabear/amidst/pull/278) | PR（Draft） | feat(q1q5): add D92 v2 responses and parse provenance | Q1、Q2、Q3 | Draft；D92 的 Q1／Q2／Q3 v2 回應與解析來源（base staging）；Claude 審查 PASS_WITH_NOTES；修正見 CQ-15 [#296](https://github.com/Polalalabear/amidst/issues/296)、CQ-23 [#303](https://github.com/Polalalabear/amidst/issues/303) |
| [#303](https://github.com/Polalalabear/amidst/issues/303) | Issue | CQ-23 v2 消費端相容（#278 P2-4） | Q1、Q2、Q3 | CQ-23；PR [#305](https://github.com/Polalalabear/amidst/pull/305)（Draft，head `e23ef16`，Claude 審查 NEEDS_CHANGES） |
| [#305](https://github.com/Polalalabear/amidst/pull/305) | PR（Draft） | CQ-23：Q1／Q2／Q3 v2 消費端相容與預設時間計分隔離 | Q1、Q2、Q3 | Draft；CQ-23 的 v2 消費端相容與預設時間計分隔離（base staging）；Claude 審查 NEEDS_CHANGES |

### 未完成（8）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#99](https://github.com/Polalalabear/amidst/issues/99) | Issue | QT-06：Q1–Q5 合約符合性測試包 | Q1、Q2、Q3、Q4、Q5 | 標 blocked；一致性檢查包 #127 仍為 Draft（AC7 未過） |
| [#145](https://github.com/Polalalabear/amidst/issues/145) | Issue | QT-40：#127 測試包對齊契約 #135 最終版並合入 | Q1、Q2、Q3、Q4、Q5 | blocked：kit 對齊契約最終版 |
| [#153](https://github.com/Polalalabear/amidst/issues/153) | Issue | #127/#145: no-color Q4 MATCH_STRONG with null verdict fails presence invariant | Q4 | kit 問題：無顏色 Q4 的 null verdict 被拒，阻擋 #154 |
| [#156](https://github.com/Polalalabear/amidst/issues/156) | Issue | #127 Q1_RESULT_ORDER：最後一頁錯將 results_total 視為當頁筆數 | Q1 | kit 問題：Q1 最後一頁筆數判錯，阻擋 #157 |
| [#170](https://github.com/Polalalabear/amidst/issues/170) | Issue | Q5 conformance：D69 link 誤分類、失敗 digest 與正常候選耗盡的 Agent flags | Q5 | kit 問題：Q5 Agent flags 與 link 分類 |
| [#178](https://github.com/Polalalabear/amidst/issues/178) | Issue | [#127] 空 decisions／links journal 被 DOCUMENT_LOADABLE 判成未知 schema | Q2、Q5 | kit 問題：空 journal 被判成未知 schema |
| [#296](https://github.com/Polalalabear/amidst/issues/296) | Issue | CQ-15 修 #278（v2 回應） | Q1、Q2、Q3 | CQ-15；對象 #278 |
| [#297](https://github.com/Polalalabear/amidst/issues/297) | Issue | CQ-16 修 #260（D92／零邊 authority，以及 G4 回條格式） | Q1、Q2、Q3 | CQ-16；對象 #260 |

### 待確認（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#88](https://github.com/Polalalabear/amidst/issues/88) | Issue | QA：Q1–Q5 第一版計畫與契約 #86 核准 | Q1、Q2、Q3、Q4、Q5 | D65 已核准，#86、#92 已合併；待確認是否關閉 |

## 共用：r004 場景、資料、索引與儲存

### 已完成（22）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| [#97](https://github.com/Polalalabear/amidst/issues/97) | Issue | QT-04：r004 修改表提案定稿（文件） | Q1、Q2、Q4、Q5 | 2026-11-01 已完成關閉（D106-2，關閉留言附 merge SHA） |
| [#113](https://github.com/Polalalabear/amidst/issues/113) | Issue | QT-20：r004 建檔、靜態校正匯出與廣角小批 preview | Q1、Q2、Q4 | 2026-11-01 關閉（D106 記為未抽查；完成處見關閉留言，11-05 抽查） |
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
| [#102](https://github.com/Polalalabear/amidst/issues/102) | Issue | QT-09：store 介面（版本化 JSON＋每 run JSONL） | Q1、Q2 | 已完成關閉（2026-10-26）；原備註：store 已併入 staging（#136），待審入主線 |
| [#103](https://github.com/Polalalabear/amidst/issues/103) | Issue | QT-10：偵測索引產生器（RT-DETR＋上半身 HSV） | Q1、Q4 | 已完成關閉（2026-10-26）；原備註：偵測索引產生器與 HSV 證據已併入 staging（#139），待審入主線 |
| [#187](https://github.com/Polalalabear/amidst/pull/187) | PR | r004 v2: source-bound entry/exit zones and portal review packet | Q2、Q5 | 已併入 staging（`9402c91`），待審入主線 |
| [#196](https://github.com/Polalalabear/amidst/issues/196) | Issue | Baseline 前置：r004 產製設定與 pinned 索引入口 | Q1、Q4 | 已完成關閉（盤點留言） |
| [#197](https://github.com/Polalalabear/amidst/pull/197) | PR | feat(q1q5): r004 pinned 產製設定與索引入口 | Q1、Q4 | 已併入 staging（`de7046a`），待審入主線 |
| [#212](https://github.com/Polalalabear/amidst/pull/212) | PR | docs(r004): 更新 yyin 回收與 baseline 凍結前狀態，交 Claude 審查 | — | 關閉未合併（2026-10-27，盤點）；head 已含於 staging（經 #231 的 merge `680ca35`），分支保留 |
| [#227](https://github.com/Polalalabear/amidst/pull/227) | PR | CX-3：r004 圖 v3、26 ROI 與 56 有向對收據（G4 未核） | Q2、Q5 | 圖 v3、26 ROI、56 有向對收據；G4 未核；已併入 staging（`3cc0532`），待審入主線 |
| [#235](https://github.com/Polalalabear/amidst/pull/235) | PR | fix(r004): align W2 paths and add D81 corridor transitions | Q2、Q5 | 已併入 staging（`747bdfe`），待審入主線 |
| [#238](https://github.com/Polalalabear/amidst/pull/238) | PR | docs(r004): D89 50s/42s clocks, D84 catalog freeze and run registrations | Q2、Q5 | D89 時鐘（A4 50 s／B4 42 s）、D84 目錄凍結與 run 註冊；已併入 staging（`001cbcf`），待審入主線 |
| [#253](https://github.com/Polalalabear/amidst/pull/253) | PR | docs(evaluation): r004 A4／B4 情境卡 v1（D87） | Q5 | 已合併主線（`0edd8a3`，2026-10-27） |
| [#259](https://github.com/Polalalabear/amidst/pull/259) | PR | fix(review): finish #235 #236 #234 notes after #231 merge | Q5 | 已併入 staging（`7a33d6d`），待審入主線 |

### 進行中（7）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#254](https://github.com/Polalalabear/amidst/pull/254) | PR（Draft） | feat(evaluation): r004 A4-1/B4-1 劇本計畫 → q5-evaluation-script.v1 adapter | Q5 | Draft；r004 A4-1／B4-1 劇本計畫 → `q5-evaluation-script.v1` adapter（base staging）；Claude 審查 PASS_WITH_NOTES；adapter 修正見 CQ-20 [#301](https://github.com/Polalalabear/amidst/issues/301) |
| [#256](https://github.com/Polalalabear/amidst/pull/256) | PR（Draft） | docs(r004): D89 A4/B4 static feasibility and timing conflicts | Q5 | Draft；D89 A4／B4 靜態可行性與時間衝突；D92 採選項 1（base staging）；已交增量，尚未複審；A4-c2 靜態檢查見 CQ-17 [#298](https://github.com/Polalalabear/amidst/issues/298)（D96-1：先標不計分待驗證） |
| [#275](https://github.com/Polalalabear/amidst/pull/275) | PR（Draft） | docs(r004): unfrozen B4-1 producer script draft with B4-d non-scoring | Q5 | Draft；未凍結的 B4-1 劇本草稿，B4-d 不計分（D92；base staging）；已交增量，尚未複審；B4-1 劇本草稿修正見 CQ-18 [#299](https://github.com/Polalalabear/amidst/issues/299)（D96-1：B4-e 先標不計分待驗證） |
| [#280](https://github.com/Polalalabear/amidst/issues/280) | Issue | CQ-01 yyin 3 題澄清落實到 r004 圖 v3（BRANCH／WIDE 出口、W1↔EXT_CAR） | Q5 | CQ-01；PR [#294](https://github.com/Polalalabear/amidst/pull/294)（Draft，head `fc36b91`，Claude 審查 NEEDS_CHANGES） |
| [#282](https://github.com/Polalalabear/amidst/issues/282) | Issue | CQ-03 A4-1 producer-script 草案（UNFROZEN，不渲染） | Q5 | CQ-03；PR [#295](https://github.com/Polalalabear/amidst/pull/295)（Draft，head `2011837`，標 needs-claude-review） |
| [#294](https://github.com/Polalalabear/amidst/pull/294) | PR（Draft） | CQ-01: yyin BRANCH ROI v3_1 與三題缺項收據 | Q5 | Draft；CQ-01 的 yyin BRANCH ROI v3_1 與三題缺項收據（base staging）；Claude 審查 NEEDS_CHANGES |
| [#295](https://github.com/Polalalabear/amidst/pull/295) | PR（Draft） | CQ-03: A4-1 未凍結劇本草案與 D92 五事件邊界 | Q5 | Draft；CQ-03 的 A4-1 未凍結劇本草案與 D92 五事件邊界（base staging）；標 needs-claude-review |

### 未完成（7）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#115](https://github.com/Polalalabear/amidst/issues/115) | Issue | QT-22：A4／B4 事件 run 產製與 safe bundle | Q1、Q2、Q4、Q5 | 標 blocked（內文寫 needs-auth）：A4-1／B4-1 事件 run 待授權；D89 核定 50／42 s，時鐘 #238（已併入 staging）、可行性檢查 #256（Draft） |
| [#118](https://github.com/Polalalabear/amidst/issues/118) | Issue | QT-25：r004 正式偵測索引產製 | Q1、Q4 | blocked：r004 正式偵測索引，等 #115 |
| [#281](https://github.com/Polalalabear/amidst/issues/281) | Issue | CQ-02 r004 G4 回條草稿（Codex 起草、Claude 審、使用者核准） | Q5 | CQ-02；未開始；依賴 CQ-01 審查通過，核准只能由使用者做 |
| [#298](https://github.com/Polalalabear/amidst/issues/298) | Issue | CQ-17 修 #256（A4-c2 靜態檢查） | Q5 | CQ-17；對象 #256；D96-1 |
| [#299](https://github.com/Polalalabear/amidst/issues/299) | Issue | CQ-18 修 #275（B4-1 劇本草稿） | Q5 | CQ-18；對象 #275；D96-1 |
| [#301](https://github.com/Polalalabear/amidst/issues/301) | Issue | CQ-20 修 #254 adapter | Q5 | CQ-20；對象 #254 |
| [#302](https://github.com/Polalalabear/amidst/issues/302) | Issue | CQ-22 N1：yyin 確認題的疊圖 | Q1、Q3 | CQ-22 |

## 共用：工作台、HTTP 與 Demo

### 已完成（33）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| [#112](https://github.com/Polalalabear/amidst/issues/112) | Issue | QT-19：Q 線 HTTP 端點與 #80 接線（R-1–R-7） | Q1、Q2、Q3 | 2026-11-01 關閉（D106 記為未抽查；完成處見關閉留言，11-05 抽查） |
| [#200](https://github.com/Polalalabear/amidst/issues/200) | Issue | Baseline 前置總驗收：可重建來源、真本機 smoke 與決策清單 | Q1、Q2、Q3、Q4、Q5 | 2026-11-01 關閉（D106 記為未抽查；完成處見關閉留言，11-05 抽查） |
| [#206](https://github.com/Polalalabear/amidst/issues/206) | Issue | 完整 baseline 條線 C：工作台、重現入口與一次驗收 | Q1、Q2、Q3、Q4、Q5 | 2026-11-01 已完成關閉（D106-2，關閉留言附 merge SHA） |
| [#208](https://github.com/Polalalabear/amidst/issues/208) | Issue | 修正工作台黑畫面與完整播放，延長工程事件並量測連續性 | Q2、Q5 | 2026-11-01 改判已完成並關閉（FEAT-7 歸併） |
| [#210](https://github.com/Polalalabear/amidst/issues/210) | Issue | 動態 RGB baseline：8秒逐格人物、工作台有界快取與審查前完整驗收 | Q2、Q5 | 2026-11-01 改判已完成並關閉（FEAT-7 歸併） |
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

### 進行中（2）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#243](https://github.com/Polalalabear/amidst/pull/243) | PR（Draft） | feat(workbench): Q1 結果牆並排播放與追蹤單畫面預設（D86-3） | Q1、Q2 | Draft；Q1 結果牆並排播放與追蹤單畫面預設（D86-3） |
| [#277](https://github.com/Polalalabear/amidst/pull/277) | PR（Draft） | fix(rerecord): pin rc5 and deliver merged-product recordings | Q1、Q2、Q3、Q4、Q5 | Draft；固定 rc5 並交付合併產品的重錄（AC7 缺口，base staging）；Claude 審查 PASS_WITH_NOTES；收尾見 CQ-19 [#300](https://github.com/Polalalabear/amidst/issues/300) |

### 未完成（3）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#124](https://github.com/Polalalabear/amidst/issues/124) | Issue | QT-31：Q1–Q5 端到端 browser acceptance 與 Demo 腳本 | Q1、Q2、Q3、Q4、Q5 | blocked：端到端瀏覽器驗收；Demo 腳本草稿已併入 staging（#181、#182） |
| [#130](https://github.com/Polalalabear/amidst/issues/130) | Issue | QT-34：組員 瀏覽器驗收（人工操作） | Q1、Q2、Q3、Q4、Q5 | 組員瀏覽器驗收未開始 |
| [#300](https://github.com/Polalalabear/amidst/issues/300) | Issue | CQ-19 #277 收尾與 AC7 缺口 | Q1、Q2、Q3、Q4、Q5 | CQ-19；標 blocked-user；對象 #277 |

### 待確認（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#194](https://github.com/Polalalabear/amidst/issues/194) | Issue | Demo v1：baseline 執行入口、逐次紀錄／replay 與正式產製預檢 | Q1、Q2、Q3、Q4、Q5 | 對應 PR #195 已併入 staging；issue 仍開著，是否關閉待確認 |

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

### 未完成（7）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#287](https://github.com/Polalalabear/amidst/issues/287) | Issue | CQ-08 圖 v4 草案跟進 CQ-01 與 #272 note 1–2 | Q5 | CQ-08；依賴 CQ-01 |
| [#288](https://github.com/Polalalabear/amidst/issues/288) | Issue | CQ-09 #266 契約提案依複核 note 與 D93／D94 補註 | Q5 | CQ-09；對象 #266 |
| [#289](https://github.com/Polalalabear/amidst/issues/289) | Issue | CQ-10 #271 靜態可行性依複核修正（發現 1–7） | Q5 | CQ-10；對象 #271 |
| [#290](https://github.com/Polalalabear/amidst/issues/290) | Issue | CQ-11 #274 工程小場景規劃依複核修正（S6、遮擋類型、輪數） | Q5 | CQ-11；對象 #274 |
| [#291](https://github.com/Polalalabear/amidst/issues/291) | Issue | CQ-12 #273 文件移除自帶的實際產出 | Q2 | CQ-12；對象 #273 |
| [#293](https://github.com/Polalalabear/amidst/issues/293) | Issue | CQ-14 組員模型評測可攜包（Baseline＋複雜事件，可帶到別的環境跑） | Q5 | CQ-14；D96-2：重播凍結輸出、Python 3.12、以可攜包 v4 為基礎、GT 留在我方計分 |
| [#304](https://github.com/Polalalabear/amidst/issues/304) | Issue | CQ-21 逐轉移回條 adapter | Q5 | CQ-21；標 blocked-user |

## 流程：任務板、交接與文件

### 已完成（29）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| [#131](https://github.com/Polalalabear/amidst/issues/131) | Issue | QT-35：Codex finalization 搬移計畫（文件） | — | 2026-11-01 已完成關閉（D106-2，關閉留言附 merge SHA） |
| [#276](https://github.com/Polalalabear/amidst/pull/276) | PR | docs(progress): Q1–Q5 進度導覽與過期文件更新（#263 S3, D91） | Q1、Q2、Q3、Q4、Q5 | 已合併 `mainline/q1q5`（`0d78599`，2026-10-28） |
| [#283](https://github.com/Polalalabear/amidst/issues/283) | Issue | CQ-04 修 #276 的 P2-1～P2-5 與 P3-1、P3-3、P3-4、P3-6、P3-9 | — | 2026-11-01 關閉（CQ-04 已由 #276 完成） |
| [#292](https://github.com/Polalalabear/amidst/issues/292) | Issue | CQ-13 舊 Codex 範圍議題現行性判定（只留言，不關閉） | — | 2026-11-01 關閉（CQ-13 抽查 PASS_WITH_NOTES，FEAT-7 歸併） |
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
| [#191](https://github.com/Polalalabear/amidst/pull/191) | PR | docs(agents): update the Q1–Q5 progress guide with every new PR and issue | — | 已合併主線（`4fddbc3`，2026-10-24）；在 AGENTS.md／CLAUDE.md 加入本文維護規則（D91-4 後由協調者在 mainline 批次補列；staging 併入 mainline 時，由協調者事後批次解導覽衝突，合併 PR 本身不改本文） |
| [#147](https://github.com/Polalalabear/amidst/issues/147) | Issue | QT-42：組員審查包（資料夾）產生器與回收匯入器 | Q1、Q3、Q4 | 已完成關閉（2026-10-26）；原備註：文字審查包 #151 已併入 staging；圖片包等 #115、#118 |
| [#213](https://github.com/Polalalabear/amidst/pull/213) | PR | Merge staging batch 1 (#136 #139 #140 #141 #143 #132) into mainline/q1q5 | — | 已合併主線（`3ccaa3a`，2026-10-25） |
| [#214](https://github.com/Polalalabear/amidst/pull/214) | PR | 五項closeout：符合性重驗、Qwen診斷、回收補件、ROI與Q3審查準備 | Q3、Q5 | 關閉未合併（2026-10-27，盤點）；head 已含於 staging（經 #231 的 merge `680ca35`），分支保留 |
| [#215](https://github.com/Polalalabear/amidst/pull/215) | PR | docs: Q1–Q5 baseline acceptance plan and progress update (2026-10-25) | Q1、Q2、Q3、Q4、Q5 | 已合併主線（`7f08592`，2026-10-25） |
| [#217](https://github.com/Polalalabear/amidst/pull/217) | PR | docs: Q1–Q5 local test setup and progress update (2026-10-25) | — | 已合併主線（`e8f98dd`，2026-10-25） |
| [#223](https://github.com/Polalalabear/amidst/pull/223) | PR | docs: coordinator handoff 2026-10-25 and handoff-upload rule | — | 已合併主線（`1b6c56b`，2026-10-25） |
| [#226](https://github.com/Polalalabear/amidst/pull/226) | PR | CX-2／#147 #151：組員說明、逐列回收拒錯與 PILOT 隔離 | Q1、Q3、Q4 | 已併入 staging（`4c96140`），待審入主線 |
| [#232](https://github.com/Polalalabear/amidst/pull/232) | PR | 交接：公開 LOCAL 文件與相對路徑、大小及 hash 收據 | — | 已併入 staging（`63ce04d`），待審入主線 |
| [#241](https://github.com/Polalalabear/amidst/pull/241) | PR | docs(agents): 協調者交接 2026-10-26 與進度導覽更新 | — | 已合併主線（`2675c21`，2026-10-26） |
| [#252](https://github.com/Polalalabear/amidst/pull/252) | PR | docs(agents): 兩條線工作分配（D87） | — | 兩條線工作分配（D87）；已合併主線（`9708fb6`，2026-10-27） |
| [#264](https://github.com/Polalalabear/amidst/pull/264) | PR | docs(archive): 封存索引與歷史文件檔頭（#263 S1, D91） | — | 封存索引與歷史文件檔頭（#263 S1）；已合併主線（`564352a`，2026-10-28） |
| [#265](https://github.com/Polalalabear/amidst/pull/265) | PR | docs: 入口文件更新與 2026-10-27 協調者交接（D91, S2） | — | 入口文件更新與 2026-10-27 協調者交接（#263 S2）；已合併主線（`204a180`，2026-10-28） |
| [#270](https://github.com/Polalalabear/amidst/pull/270) | PR | docs(specs): Q1–Q5 產品規格（#263 S4, D91） | Q1、Q2、Q3、Q4、Q5 | Q1–Q5 產品規格（#263 S4）；已合併主線（`741996c`，2026-10-28） |

### 進行中（6）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#83](https://github.com/Polalalabear/amidst/pull/83) | PR | docs(agents): 決策索引、系統總覽、組員上手指南 | — | 組員上手文件、決策索引與系統總覽（非 Draft），待審查與合併 |
| [#93](https://github.com/Polalalabear/amidst/issues/93) | Issue | Q1–Q5 任務板（從這裡開始） | Q1、Q2、Q3、Q4、Q5 | Q1–Q5 任務板；決定已到 D96（2026-10-27，D97 尚無）；D95 Codex 任務佇列為 [#279](https://github.com/Polalalabear/amidst/issues/279) |
| [#263](https://github.com/Polalalabear/amidst/issues/263) | Issue | 文件封存與現況更新（D91） | Q1、Q2、Q3、Q4、Q5 | 文件封存與現況更新（D91）；S1 #264、S2 #265、S4 #270 已於 2026-10-28 合併主線，S3 為 #276（尚未合併） |
| [#267](https://github.com/Polalalabear/amidst/pull/267) | PR（Draft） | integration: prepare staging into mainline with D91 mainline docs preserved | — | Draft；staging → mainline 整合（D91 的 mainline 文件保留）；待 #260 等合入 staging 後更新，未合併；目前 CONFLICTING，說明寫明不可據此合併；刷新工作見 CQ-07 [#286](https://github.com/Polalalabear/amidst/issues/286)（blocked-user） |
| [#268](https://github.com/Polalalabear/amidst/pull/268) | PR（Draft） | docs(archive): mark six Codex historical handoffs under D91 | — | Draft；六份 Codex 歷史交接加 D91 封存註記（base staging） |
| [#279](https://github.com/Polalalabear/amidst/issues/279) | Issue | Codex 任務佇列（自取）2026-10-27 起 | — | D95 Codex 任務佇列（CQ-01～CQ-23，#280–#304，另含 #115、#118、#194、#202）；Claude 負責審查，標籤與本表由協調者維護 |

### 未完成（2）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#137](https://github.com/Polalalabear/amidst/issues/137) | Issue | QT-36：組員 交接試跑（照 TEAM_ONBOARDING 從零開始） | — | 組員交接試跑未開始 |
| [#286](https://github.com/Polalalabear/amidst/issues/286) | Issue | CQ-07 刷新 #267 staging→mainline 合併準備（必修 3 項） | — | CQ-07；標 blocked-user |

### 待確認（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#87](https://github.com/Polalalabear/amidst/issues/87) | Issue | GitHub 整理紀錄（2026-10-20，D63 後） | — | D63 後的 GitHub 整理紀錄，最後更新 10-20；待確認是否關閉 |

## D97 後：架構基準、feature 與 demo UI

#306–#382（D97 起新增），每項只列在這裡。feature 與子 PR 的對照見上方「2026-11-01 快照」。

### 進行中（60）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#306](https://github.com/Polalalabear/amidst/issues/306) | Issue | 架構基準：Q1–Q5 demo（2026-11-01）權威文件、模組邊界與不偏離規則 | — | 架構基準（checkpoint）；pin 只由協調者更新，D108-2 規則檔 pin 待更新 |
| [#308](https://github.com/Polalalabear/amidst/issues/308) | Issue | CQ-21a 回條綁定契約補充草案（A1–A5、B1–B3、C1–C3） | — | 子任務：PR #351（FEAT-4） |
| [#309](https://github.com/Polalalabear/amidst/issues/309) | Issue | CQ-21-T 回條 overlay adapter 的驗收測試（合成收據 fixture） | — | 子任務：PR #352（FEAT-4） |
| [#310](https://github.com/Polalalabear/amidst/issues/310) | Issue | CQ-24 A4-1／B4-1 劇本凍結候選（依 D96-1 驗證結果） | — | 子任務：PR #354（FEAT-1） |
| [#311](https://github.com/Polalalabear/amidst/issues/311) | Issue | CX-7-T 事件 run 與 safe bundle 產出檢查器（#115 CX-7 與複雜事件渲染共用） | — | 子任務：PR #353（FEAT-1） |
| [#312](https://github.com/Polalalabear/amidst/issues/312) | Issue | QT-25-T 正式偵測索引收據檢查器（#118 與複雜事件索引共用） | — | 子任務：PR #357（FEAT-1） |
| [#313](https://github.com/Polalalabear/amidst/issues/313) | Issue | CX-8-T 正式 baseline 凍結收據檢查器（#194／#202 與複雜事件執行共用） | — | 子任務：PR #355（FEAT-1） |
| [#315](https://github.com/Polalalabear/amidst/issues/315) | Issue | CQ-25-T P2 baseline 評分報告的驗收測試與重算腳本 | — | 子任務：PR #356（FEAT-1） |
| [#316](https://github.com/Polalalabear/amidst/issues/316) | Issue | CQ-26 r004 空場景可出題物件清單（每台鏡頭看得到哪些車輛與家具） | — | 子任務：PR #350（FEAT-2） |
| [#317](https://github.com/Polalalabear/amidst/issues/317) | Issue | CQ-27 yyin 主包 team-handoff-yyin-20261028：框架與 s2 Q1／Q3 出題段 | — | 子任務：PR #361（FEAT-2） |
| [#318](https://github.com/Polalalabear/amidst/issues/318) | Issue | CQ-27-T 交接包驗收測試與通用檢查器（主包與評測包共用） | — | 子任務：PR #359（FEAT-2） |
| [#319](https://github.com/Polalalabear/amidst/issues/319) | Issue | CQ-28 yyin 主包 s1 審圖段（CQ-22 疊圖、3 題確認） | — | 子任務：PR #361（FEAT-2）；blocked-user |
| [#321](https://github.com/Polalalabear/amidst/issues/321) | Issue | CQ-29-T 主包回件匯入的驗收測試（合成回件） | — | 子任務：PR #358（FEAT-2） |
| [#322](https://github.com/Polalalabear/amidst/issues/322) | Issue | CQ-30 #258 Q5 評分規則 v2 設計稿回修（J2 F1–F4、D93、D94、#266 C1–C10） | — | 子任務：PR #258（FEAT-4） |
| [#323](https://github.com/Polalalabear/amidst/issues/323) | Issue | CQ-31 #261 複雜情境卡 v2 回修（Codex 複核 F1–F3、#271／CQ-10） | — | 子任務：PR #261（FEAT-4）；blocked-user |
| [#324](https://github.com/Polalalabear/amidst/issues/324) | Issue | CQ-32 Q5 評分器 v2 實作 q5_switch_eval_v2.py（14 項待決可設定、預設 fail closed） | — | 子任務：PR #366（FEAT-4）；blocked-user |
| [#325](https://github.com/Polalalabear/amidst/issues/325) | Issue | CQ-32-T Q5 評分器 v2 的驗收測試（合成 controller 軌跡） | — | 子任務：PR #360（FEAT-4） |
| [#326](https://github.com/Polalalabear/amidst/issues/326) | Issue | CQ-33 複雜事件 v2 劇本與 adapter v2（q5-evaluation-script.v2） | — | 子任務：PR #367（FEAT-4）；blocked-user |
| [#327](https://github.com/Polalalabear/amidst/issues/327) | Issue | CQ-33-T adapter v2 的驗收測試（合成情境卡 v2） | — | 子任務：PR #362（FEAT-4） |
| [#331](https://github.com/Polalalabear/amidst/issues/331) | Issue | CQ-36-T 複雜事件報告的驗收測試與重算腳本 | — | 子任務：PR #363（FEAT-4） |
| [#332](https://github.com/Polalalabear/amidst/issues/332) | Issue | CQ-37 長時間軸／8 鏡頭牆接真實資料（#255、#246） | — | 子任務：PR #255（FEAT-4） |
| [#333](https://github.com/Polalalabear/amidst/issues/333) | Issue | CQ-38 J4 linker 離線重播（#273 未交的 replay_l2_linker_*） | — | 子任務：PR #273（FEAT-4）；blocked-user |
| [#334](https://github.com/Polalalabear/amidst/issues/334) | Issue | CQ-14-T 組員評測可攜包的驗收測試（Python 3.12、重播凍結輸出） | — | 子任務：PR #364（FEAT-3） |
| [#336](https://github.com/Polalalabear/amidst/issues/336) | Issue | CQ-39-T 評測回件計分流程的驗收測試（合成回件） | — | 子任務：PR #365（FEAT-3） |
| [#340](https://github.com/Polalalabear/amidst/issues/340) | Issue | CQ-42-T demo 腳本與彩排紀錄的檢查器（#124 與 CQ-42 共用） | — | 子任務：PR #368（FEAT-5）；blocked-user |
| [#348](https://github.com/Polalalabear/amidst/pull/348) | PR（Draft） | CQ-02: r004 G4 待決回條與可重算 payload 草稿 | — | FEAT-1（#376）子 PR，審查結論見歸併留言 |
| [#349](https://github.com/Polalalabear/amidst/pull/349) | PR（Draft） | CQ-22: yyin 三題靜態 A/B/C 確認疊圖 | — | FEAT-2（#369）子 PR，審查結論見歸併留言；標 `superseded`：被 D105 B-5 選項 1 取代，不合併 |
| [#350](https://github.com/Polalalabear/amidst/pull/350) | PR（Draft） | CQ-26: r004 空場景可出題物件清單 | — | FEAT-2（#369）子 PR，審查結論見歸併留言 |
| [#351](https://github.com/Polalalabear/amidst/pull/351) | PR（Draft） | CQ-21a: G4 回條綁定十一條補充草案（待 U8） | — | FEAT-4（#371）子 PR，審查結論見歸併留言 |
| [#352](https://github.com/Polalalabear/amidst/pull/352) | PR（Draft） | CQ-21-T: 合成 G4 收據檢查器與 fail-closed 驗收測試 | — | FEAT-4（#371）子 PR，審查結論見歸併留言 |
| [#353](https://github.com/Polalalabear/amidst/pull/353) | PR（Draft） | CX-7-T：事件 run 與 safe bundle 合成檢查器 | — | FEAT-1（#376）子 PR，審查結論見歸併留言 |
| [#354](https://github.com/Polalalabear/amidst/pull/354) | PR（Draft） | CQ-24：A4/B4 待核劇本凍結候選與檢查器 | — | FEAT-1（#376）子 PR，審查結論見歸併留言 |
| [#355](https://github.com/Polalalabear/amidst/pull/355) | PR（Draft） | CX-8-T：baseline 凍結與錄製 bytes 合成檢查器 | — | FEAT-1（#376）子 PR，審查結論見歸併留言 |
| [#356](https://github.com/Polalalabear/amidst/pull/356) | PR（Draft） | CQ-25-T：SYNTHETIC P2 報告重算檢查器與驗收測試 | — | FEAT-1（#376）子 PR，審查結論見歸併留言 |
| [#357](https://github.com/Polalalabear/amidst/pull/357) | PR（Draft） | test(qt25): SYNTHETIC 偵測索引收據與逐格 coverage 檢查 | — | FEAT-1（#376）子 PR，審查結論見歸併留言 |
| [#358](https://github.com/Polalalabear/amidst/pull/358) | PR（Draft） | CQ-29-T：合成主包回件驗收 probes（待 orchestration） | — | FEAT-2（#369）子 PR，審查結論見歸併留言 |
| [#359](https://github.com/Polalalabear/amidst/pull/359) | PR（Draft） | CQ-27-T：交接包機械檢查器與主包驗收測試 | — | FEAT-2（#369）子 PR，審查結論見歸併留言 |
| [#360](https://github.com/Polalalabear/amidst/pull/360) | PR（Draft） | CQ-32-T：Q5 v2 評分器合成驗收與缺實作紅燈 | — | FEAT-4（#371）子 PR，審查結論見歸併留言 |
| [#361](https://github.com/Polalalabear/amidst/pull/361) | PR（Draft） | CQ27/CQ28: offline authoring and review framework, production gate closed | — | FEAT-2（#369）子 PR，審查結論見歸併留言；head 標 `superseded`：FEAT-2 改 cherry-pick `e7edc98`、`3deee9e` |
| [#362](https://github.com/Polalalabear/amidst/pull/362) | PR（Draft） | CQ33-T: synthetic v2 script adapter acceptance tests | — | FEAT-4（#371）子 PR，審查結論見歸併留言 |
| [#363](https://github.com/Polalalabear/amidst/pull/363) | PR（Draft） | CQ36-T: synthetic report checker and pending native integration tests | — | FEAT-4（#371）子 PR，審查結論見歸併留言 |
| [#364](https://github.com/Polalalabear/amidst/pull/364) | PR（Draft） | CQ14-T: isolated offline team evaluation pack acceptance tests | — | FEAT-3（#370）子 PR，審查結論見歸併留言 |
| [#365](https://github.com/Polalalabear/amidst/pull/365) | PR（Draft） | CQ39-T: return integrity, freeze ordering and drift scoring tests | — | FEAT-3（#370）子 PR，審查結論見歸併留言 |
| [#366](https://github.com/Polalalabear/amidst/pull/366) | PR（Draft） | CQ-32: Q5 v2 評分器與預設未決設定，保留 v1 bytes | — | FEAT-4（#371）子 PR，審查結論見歸併留言 |
| [#367](https://github.com/Polalalabear/amidst/pull/367) | PR（Draft） | CQ-33: v2 adapter 共用評分公式與 UNFROZEN 甲卡計畫 | — | FEAT-4（#371）子 PR，審查結論見歸併留言 |
| [#368](https://github.com/Polalalabear/amidst/pull/368) | PR（Draft） | CQ-42-T: demo 腳本與彩排紀錄格式檢查器 | — | FEAT-5（#372）子 PR，審查結論見歸併留言 |
| [#369](https://github.com/Polalalabear/amidst/issues/369) | Issue | FEAT-2 yyin 主包與回件 | — | feature 議題（D103）；歸併留言見 #93 D105-8；批次順序 D105-7 |
| [#370](https://github.com/Polalalabear/amidst/issues/370) | Issue | FEAT-3 組員評測包 | — | feature 議題（D103）；歸併留言見 #93 D105-8；批次順序 D105-7 |
| [#371](https://github.com/Polalalabear/amidst/issues/371) | Issue | FEAT-4 複雜事件 | — | feature 議題（D103）；歸併留言見 #93 D105-8；批次順序 D105-7 |
| [#372](https://github.com/Polalalabear/amidst/issues/372) | Issue | FEAT-5 demo 工程 | — | feature 議題（D103）；歸併留言見 #93 D105-8；批次順序 D105-7 |
| [#373](https://github.com/Polalalabear/amidst/issues/373) | Issue | FEAT-6 v2 回應與消費端 | — | feature 議題（D103）；歸併留言見 #93 D105-8；批次順序 D105-7 |
| [#374](https://github.com/Polalalabear/amidst/issues/374) | Issue | FEAT-7 架構守門 | — | feature 議題（D103）；歸併留言見 #93 D105-8；批次順序 D105-7 |
| [#375](https://github.com/Polalalabear/amidst/issues/375) | Issue | FEAT-8 stretch 延伸項目 | — | feature 議題（D103）；歸併留言見 #93 D105-8；批次順序 D105-7 |
| [#376](https://github.com/Polalalabear/amidst/issues/376) | Issue | FEAT-1 Baseline 正式鏈 | — | feature 議題（D103）；歸併留言見 #93 D105-8；批次順序 D105-7 |
| [#377](https://github.com/Polalalabear/amidst/pull/377) | PR（Draft） | feat(workbench-v2): 檢索彈窗與 search phase 狀態機 (K-UI-1) | — | Claude K-UI-1 檢索彈窗與 search phase 狀態機；base staging（D107-4） |
| [#378](https://github.com/Polalalabear/amidst/pull/378) | PR（Draft） | feat(workbench-v2): 監控牆＋後台頁 (K-UI-2) | — | Claude K-UI-2 監控牆＋後台頁；base staging |
| [#379](https://github.com/Polalalabear/amidst/pull/379) | PR（Draft） | docs(research): 相關工作與定位 | — | Claude 相關工作與定位（研究文件）；base mainline |
| [#380](https://github.com/Polalalabear/amidst/pull/380) | PR（Draft） | DEMO_UI_SUPPORT_V1：俯視圖／錄製標題／候選檢視／OpenAI 轉接器規格與 -T，物理預測模組 | — | Claude 測試先行規格 DEMO_UI_SUPPORT_V1（PROPOSED）、-T 與物理預測模組（D107-4）；base staging |
| [#381](https://github.com/Polalalabear/amidst/pull/381) | PR（Draft） | feat(workbench-v2): 追蹤模式俯視圖與物理預測虛線 (UI-C) | — | Claude UI-C 俯視圖與物理預測顯示（D107-4）；base staging |
| [#382](https://github.com/Polalalabear/amidst/pull/382) | PR（Draft） | docs(rules): 規則改寫到 D104～D108 與廢棄／過時索引（D108） | — Claude 規則改寫到 D104～D108、廢棄索引、本導覽刷新（D108）；base mainline，合併需使用者授權 |

### 未完成（16）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#307](https://github.com/Polalalabear/amidst/issues/307) | Issue | ARCH-T 架構守門腳本 check_architecture_guard.py（test-first） | — | 子任務，FEAT-7（#374） |
| [#314](https://github.com/Polalalabear/amidst/issues/314) | Issue | CQ-25 P2 正式 baseline 評估（CL-5）：Baseline 評分與報告 | — | 子任務，FEAT-1（#376） |
| [#320](https://github.com/Polalalabear/amidst/issues/320) | Issue | CQ-29 yyin 主包回件匯入與驗證（s1 審圖、s2 出題） | — | 子任務，FEAT-2（#369） |
| [#328](https://github.com/Polalalabear/amidst/issues/328) | Issue | CQ-34 複雜事件資料產製（渲染；r004 v2 卡片或 L2-6 #249） | — | 子任務，FEAT-4（#371）；blocked-user |
| [#329](https://github.com/Polalalabear/amidst/issues/329) | Issue | CQ-35 複雜事件的偵測索引、兩模式執行與凍結輸出 | — | 子任務，FEAT-4（#371） |
| [#330](https://github.com/Polalalabear/amidst/issues/330) | Issue | CQ-36 複雜事件評分與報告（v2 評分器） | — | 子任務，FEAT-4（#371） |
| [#335](https://github.com/Polalalabear/amidst/issues/335) | Issue | CQ-39 組員評測回件的計分流程 | — | 子任務，FEAT-3（#370） |
| [#337](https://github.com/Polalalabear/amidst/issues/337) | Issue | CQ-40 workbench-v2 demo 模式（逐步導覽、資料來源標示） | — | 子任務，FEAT-5（#372）；已認領，做在 FEAT-5 整合分支 |
| [#338](https://github.com/Polalalabear/amidst/issues/338) | Issue | CQ-41 demo 一鍵啟動與 fallback（deterministic replay） | — | 子任務，FEAT-5（#372） |
| [#339](https://github.com/Polalalabear/amidst/issues/339) | Issue | CQ-42 demo 彩排紀錄（全流程、計時、fallback 演練） | — | 子任務，FEAT-5（#372） |
| [#341](https://github.com/Polalalabear/amidst/issues/341) | Issue | CQ-43 demo 組成收據（11/01 實際跑的每個 PR head 與 pins） | — | 子任務，FEAT-5（#372） |
| [#342](https://github.com/Polalalabear/amidst/issues/342) | Issue | CQ-44（stretch）Q4 正式 T／F 評估 | — | 子任務，FEAT-8（#375） |
| [#343](https://github.com/Polalalabear/amidst/issues/343) | Issue | CQ-45（stretch）複雜情境卡 v2 第二批（規格與可行性） | — | 子任務，FEAT-8（#375） |
| [#344](https://github.com/Polalalabear/amidst/issues/344) | Issue | CQ-46（stretch）Windows 啟動腳本 start.bat（主包、評測包、可攜包） | — | 子任務，FEAT-8（#375） |
| [#345](https://github.com/Polalalabear/amidst/issues/345) | Issue | CQ-47（stretch）L2-4 偵測改善參數實作（opt-in，只用於 Line 2） | — | 子任務，FEAT-8（#375）；blocked-user |
| [#347](https://github.com/Polalalabear/amidst/issues/347) | Issue | CQ-48 yyin 補交 templates/審查表.csv（併入主包 s0） | — | 子任務，FEAT-2（#369） |

### 待確認（1）

| 編號 | 類型 | 標題 | 也涉及 | 備註 |
| --- | --- | --- | --- | --- |
| [#346](https://github.com/Polalalabear/amidst/issues/346) | Issue | 完整 demo 驗收清單（11/01，使用者逐項驗收） | — | checkpoint；demo 日改為 11-04（D100-8），等使用者逐項驗收 |

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
