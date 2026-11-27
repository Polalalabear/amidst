# 協調者交接合集（2026-10-25 至 2026-11-27）

本文把 14 份舊協調者交接合併成一份歷史文件（[#93 D408](https://github.com/Polalalabear/amidst/issues/93#issuecomment-7212792189)，使用者 2026-11-27 核准；追蹤 [#756](https://github.com/Polalalabear/amidst/issues/756)）。原檔已在同一個 PR 刪除，需要時可從 git 歷史取回（merge 前的 `main`）。

- **內容**：14 份交接全文，依日期排序，內容不改寫。每份放在 `## <日期>（原 <舊路徑>）` 段落下；原文標題降兩級（原 H1 → `###`），讓段落標題在最上層。這比 D408 清單寫的「降一級」多降一級，因為段落標題本身已占 `##`。
- **連結**：交接之間的互相連結改成指向本文的錨點（`#h<日期>`，原連結的段內錨點省略）；其他相對連結與原位置同深度（`docs/history/` 與 `docs/agents/`），未受影響。內文裡以反引號寫的舊檔名、路徑不改，改用下面的對照表查。
- **未併入**：`docs/agents/COORDINATOR_HANDOFF_20261027.md`（authority pin A5）與 `docs/agents/COORDINATOR_HANDOFF_20261127b.md`（現行交接）仍在原處。
- 現行狀態不看本文，看 [#93](https://github.com/Polalalabear/amidst/issues/93) 和最新交接。

## 目錄

- [2026-10-25](#h20261025)：協調者交接（2026-10-25）
- [2026-10-26](#h20261026)：協調者交接（2026-10-26）
- [2026-11-15](#h20261115)：協調者交接 2026-11-15
- [2026-11-16](#h20261116)：協調者交接 2026-11-16
- [2026-11-17](#h20261117)：協調者交接 2026-11-17（晚間快照）
- [2026-11-18](#h20261118)：協調者交接 2026-11-18
- [2026-11-22](#h20261122)：協調者交接（2026-11-22）
- [2026-11-23](#h20261123)：協調者交接（2026-11-23）
- [2026-11-23b](#h20261123b)：協調者交接（2026-11-23 第二份）
- [2026-11-23c](#h20261123c)：協調者交接（2026-11-23 第三份）
- [2026-11-24](#h20261124)：協調者交接（2026-11-24）
- [2026-11-24b](#h20261124b)：協調者交接 2026-11-24（下午，第二份）
- [2026-11-26](#h20261126)：協調者交接 2026-11-26
- [2026-11-27](#h20261127)：協調者交接（2026-11-27）

## 舊路徑 → 新段落

| 舊路徑（已刪除） | 新段落 |
| --- | --- |
| `docs/agents/COORDINATOR_HANDOFF_20261025.md` | [2026-10-25](#h20261025) |
| `docs/agents/COORDINATOR_HANDOFF_20261026.md` | [2026-10-26](#h20261026) |
| `docs/agents/COORDINATOR_HANDOFF_20261115.md` | [2026-11-15](#h20261115) |
| `docs/agents/COORDINATOR_HANDOFF_20261116.md` | [2026-11-16](#h20261116) |
| `docs/agents/COORDINATOR_HANDOFF_20261117.md` | [2026-11-17](#h20261117) |
| `docs/agents/COORDINATOR_HANDOFF_20261118.md` | [2026-11-18](#h20261118) |
| `docs/agents/COORDINATOR_HANDOFF_20261122.md` | [2026-11-22](#h20261122) |
| `docs/agents/COORDINATOR_HANDOFF_20261123.md` | [2026-11-23](#h20261123) |
| `docs/agents/COORDINATOR_HANDOFF_20261123b.md` | [2026-11-23b](#h20261123b) |
| `docs/agents/COORDINATOR_HANDOFF_20261123c.md` | [2026-11-23c](#h20261123c) |
| `docs/agents/COORDINATOR_HANDOFF_20261124.md` | [2026-11-24](#h20261124) |
| `docs/agents/COORDINATOR_HANDOFF_20261124b.md` | [2026-11-24b](#h20261124b) |
| `docs/agents/COORDINATOR_HANDOFF_20261126.md` | [2026-11-26](#h20261126) |
| `docs/agents/COORDINATOR_HANDOFF_20261127.md` | [2026-11-27](#h20261127) |

---

<a id="h20261025"></a>

## 2026-10-25（原 docs/agents/COORDINATOR_HANDOFF_20261025.md）

> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

### 協調者交接（2026-10-25）

> 最新交接見 [COORDINATOR_HANDOFF_20261026.md](#h20261026)。

- 前一個協調者 session 在 2026-10-25 封存。新的協調者先讀本文，再讀 [任務板 #93](https://github.com/Polalalabear/amidst/issues/93)、[驗收計畫](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) 和 [進度導覽](../operations/Q1Q5_PROGRESS.md)。
- 即時狀態以 GitHub 為準。本文只寫交接當下的快照、慣例和待辦。

#### 1. 交接當下的狀態

| 項目 | 狀態 |
| --- | --- |
| `mainline/q1q5` | 今天合入 #213（staging 第 1 批：#136、#139、#140、#141、#143、#132）、#90、#215（驗收計畫）、#217（本機測試文件），以及本文所在的 PR |
| `codex/q1q5-staging` | @`a958dd4`，剩 21 個 PR 等修正後分批合（依賴 #142、#148 契約、#149 的修正） |
| `main` | 不動（D72） |
| 測試包 #127 | v0.3.0-rc2 @`8a2c4a5`（Draft）。rc1 的 6 個 FAIL 已消失；176 份 D73 之前的錄製各缺 `reasons[]`（1 FAIL），要等產品依 D73 補欄位後重錄 |
| 契約 | 3873ff2 已核准；staging 版審查結論 NEEDS_CHANGES（R1–R8，#144 issuecomment-6393318061）；§14 已全部決定（D73），等 Codex 寫進條文 |
| r004 | v2 圖不能照現狀凍結（#117 收據 issuecomment-6395932781）；等 Codex 圖 v3（D74、D77） |
| 正式 baseline | BLOCKED：圖 v3 → G4 → #115 渲染 → #118 索引 → CX-8 |
| P1 工程預驗收 | 8 秒工程場景可以在本機啟動（`docs/operations/Q1Q5_LOCAL_TEST_SETUP.md`）；等 CX-4 整合分支與 CX-5 預驗收版 |

#### 2. 今天的決定（全文在 #93）

- **D72**：`main` 不動，等正式 baseline 和 #127 通過後再問。
- **D73**：§14 全部決定：
  - 維持 D65 預算；
  - 第一版不設 LOST 期限；
  - #183 空候選可以引用 evidence hash；
  - Q1 只限單 run；
  - `reasons[]`；
  - raw-bytes journal hash；
  - 逐事件決策窗；
  - X2：Agent 被接手後，手動改選時由使用者在前端決定是否重啟 Agent。
- **D74**：圖 v3 全部修完並複核後，才核 G4、才渲染；CAM_ENTRY 不進自動切鏡。
- **D75**：
  - 正式索引用 §11 的 HSV 初值；
  - Q1／Q3 人工答案由 Claude 直接轉換；
  - Q5 決策窗寬由 Claude 提案、使用者核定；
  - 關閉 #126，#90 當紀錄合併；
  - Codex 收斂 baseline Draft。
- **D76**：
  - CAM_WIDE 維持 90°；
  - Q3 的 8 題由組員自己出；
  - 組員包格式（說明檔＋RETURN）；
  - Qwen 不截斷的延遲量測；
  - P1／P2 兩階段驗收。
- **D77**：r004 重疊區（BRANCH↔WIDE、EXT_CAR↔EXT_CLEAR）延後到 Q5 穩定後；工程場景的盲區照現狀保留。

#### 3. 今天的審查結論

- **PASS**：#136、#140、#141、#143、#150、#152、#166、#167、#151。
- **PASS_WITH_NOTES**：#139、#132、#155、#162、#159、#165、#181、#182、#212、#214、#216。
- **NEEDS_CHANGES**：#142、#148–#179 契約鏈、#149、#160、#164。修正指派在 #93（issuecomment，標題「Claude 10/25 staging 審查結果與修正指派」）。
- **#216 的發現**：A→B 空檔有一大段是追蹤失敗，不是幾何盲區（漏檢就判暫失，回原鏡頭只比對凍結框）。已開 [#218](https://github.com/Polalalabear/amidst/issues/218)，Codex 先提 §14 選項。

#### 4. 等 Codex（全部已貼 #93；清單見驗收計畫 §4）

- CX-1 契約修正（R1–R8 加上 D73）。
- CX-2 staging 修正（#142、#149、#160、#164、v0-pilot 包）。
- CX-3 圖 v3（10 項，第 6 項依 D77 列排除）。
- CX-4 baseline 整合分支。
- CX-5 P1 預驗收版。
- CX-6 Qwen 不截斷量測。
- CX-7 渲染與索引（G4 之後）。
- CX-8 正式 baseline。
- CX-10 組員可攜測試包。
- #218 選項。
- 依新的 AGENTS.md 規則（Handoff documents go on GitHub），把只存在 LOCAL 的交接文件上傳。

#### 5. Claude 的待辦

| 何時 | 工作 | 模型 |
| --- | --- | --- |
| 現在就能做 | 修 #83 組員交接包（改成無 Git 資料夾流程，加說明檔與 RETURN） | Opus（文件與決策） |
| 現在就能做 | 起草 Q5 決策窗寬提案（D75），交使用者核定 | Opus |
| Codex 交件後 | 複核 CX-1（Opus）、CX-2、CX-4（Sonnet，程式）；staging 第 2 批之後分批合主線，合完後關閉 #135 | Sonnet／Opus |
| CX-3 之後 | 複核圖 v3，出 G4 收據，問使用者 | Opus |
| 契約定版後 | #127 綁定契約 SHA 後合併（#145） | Sonnet |
| CX-5 之後 | P1 瀏覽器預走查與截圖，交使用者驗收 | Sonnet |
| 組員交回後 | 匯入 yyin 的澄清回覆，併入圖 v3 的複核 | Haiku 匯入，Opus 判斷 |
| 正式輸出後 | 轉換組員的 Q1／Q3 CSV、跑評分、#124 Demo 腳本與 P2 驗收 | Sonnet／Opus |

#### 6. 使用者待決

- 現在：把組員包傳給 yyin。
- 之後依序：#218 的選項 → G4（圖 v3 複核後）→ Q5 決策窗寬 → P1 驗收 → `exit_rule` 的 `boundary_inclusive` → 是否更新 `main`。
- OpenAI API 排在 baseline 之後；接之前要先決定 D64 的規則例外。

#### 7. 組員（yyin）

- **已交回**：r004 前置審查 v2，132 項全部有效（123 T／7 F／2 不確定；70 題 HSV 全填 T，正式 Q4 時建議改成盲測）。
- **待交**：r004 澄清 3 題，LOCAL `$AMIDST_ARTIFACTS/team-handoff-yyin-20261025.zip`。
  - 2.8 MB，ZIP SHA-256 `c6ac1cee61676614263c592e45a5c5a8fde3ca97bba922dbe5fdc7008a2339e7`，MANIFEST SHA-256 `d84bfbb6bdc6685e6abcc29603377535db259ab4d4b98c79a87c0a8ec3b73657`。
  - 瀏覽器填表，格式與 r004 v2 相同；附 `tools/verify_pack.py`。
  - 回交檔是 `RETURN/審查表_yyin_YYYY-MM-DD.csv`。
  - 原本的 24 張畫面試填和 r004 包的 70 題 HSV T／F 重疊，已經拿掉。
- **之後**：Q1／Q3 出題（含 Q3 的 8 題，等 #149 修好）、正式 Q4 T／F（等正式輸出）。每份包都要有說明檔和 RETURN。

#### 8. 協調者慣例（使用者規定）

- 回覆用繁體中文；以 Default（ask）模式執行，GitHub 寫入逐一由使用者核准。
- 模型分級：
  - 開 PR、開 issue、貼文、查 PR／issue：用 **Haiku**（先整理，再交給高階模型判斷）；
  - 決策與非程式審查：用 **Opus**；
  - 程式碼審查：用 **Sonnet**。
- 新工作開新的 session，或用 subagent；由 session 事件喚醒的回合不能開 session，只能用提案卡或 subagent。
- 寫檔的 session 最多 2 個，各用 scratchpad 的精簡 clone（`git clone --shared` 從 canonical repo），用完刪除。
- 不動 amidst-claude 的 6 個未追蹤檔。
- 只用 merge commit；合併前核對 head SHA（`--match-head-commit`）。
- 決定用 AskUserQuestion 問（建議選項放第一個，附優缺點），並記成 D 編號貼到 #93。
- 給 Codex 的指派要寫成可直接貼上的文字，也同步貼到 GitHub。
- 每個 PR 都要更新 `docs/operations/Q1Q5_PROGRESS.md`。交接文件一律上傳 GitHub（AGENTS.md 新規則）。
- 可用磁碟低於 8 GiB 要停；交接當下約 12.8 GiB。

---

<a id="h20261026"></a>

## 2026-10-26（原 docs/agents/COORDINATOR_HANDOFF_20261026.md）

### 協調者交接（2026-10-26）

> **最新交接見 [2026-10-27](../agents/COORDINATOR_HANDOFF_20261027.md)。**本文為 2026-10-26 的快照。

- 本文接續 [2026-10-25 交接](#h20261025)。新的協調者先讀本文，再讀 [任務板 #93](https://github.com/Polalalabear/amidst/issues/93)、[驗收計畫](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) 和 [進度導覽](../operations/Q1Q5_PROGRESS.md)。
- 即時狀態以 GitHub 為準。本文只寫交接當下的快照、慣例和待辦。

#### 1. 交接當下的狀態

| 項目 | 狀態 |
| --- | --- |
| `mainline/q1q5` | @`f5168f6`。今天合入 [#229](https://github.com/Polalalabear/amidst/pull/229)（D79 決策窗文件，merge `f5168f6`） |
| `codex/q1q5-staging` | @`7b05211`。今天合入 [#237](https://github.com/Polalalabear/amidst/pull/237)（契約 B，merge `83da40f`）和 [#239](https://github.com/Polalalabear/amidst/pull/239)（Qwen 報告註記，merge `7b05211`）。#237 取代 #219；#219 被 GitHub 經 `635a102` 自動標成 MERGED，分支保留 |
| `main` | @`519e874`，不動（D72） |
| 開著的 PR | 41 個 |

#### 2. 今天的決定（全文在 #93）

- **D83**：P1 回交表用人工閱讀，不寫 importer，不進正式指標（[issuecomment-6415107757](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6415107757)）。
- **D84**：目錄凍結和 G4 脫鉤。
  - 照現狀凍結 `3eba8572…`；
  - A4／B4 的 run 登記放在另一個檔案；
  - 註記 `static_validity` 為 `NOT_EVALUATED`；
  - #229 現在合，#228 等 CL-4 後再合（[issuecomment-6416451756](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6416451756)）。
- **D85**：停止後 API 輪詢的內層 Q2 依契約回 `PARTIAL`＋`USER_STOPPED`；#231 在 N1／N4 修好後合（[issuecomment-6416508414](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6416508414)）。
- 下一個編號：**D86**。
- 使用者選定 A4 為 2026-11-01 14:00、B4 為 14:10（Asia/Taipei），兩個獨立的 demo 時鐘（[#238](https://github.com/Polalalabear/amidst/pull/238)）。

#### 3. 今天的審查結論（Claude，全部貼在 PR 留言）

| PR | 結論 | 重點 |
| --- | --- | --- |
| #233 | PASS_WITH_NOTES | — |
| #234 | PASS_WITH_NOTES | 加做 D83 後續檢查；備註 3–5 仍開著 |
| #237 | PASS_WITH_NOTES → 複核 PASS_WITH_NOTES | 已合入 staging |
| #239 | PASS_WITH_NOTES → PASS | 已合入 staging |
| #236 | PASS_WITH_NOTES | 75 個測試通過 |
| #238 | PASS_WITH_NOTES | 時鐘 OK，目錄凍結待辦 |
| #235 | PASS_WITH_NOTES，含 M1 | W1↔W2 的空路徑被算成 `APPROVED_WALKABLE`，G4 之後會變成合法切換；必須列為 G4 的明確項目 |
| #231 | 複核 PASS_WITH_NOTES | 507 個 pytest、69 個 node 測試通過。N1：D82 輪詢；N2：G4 收據只有布林值；N3：無 scope 的舊圖；N4：base 過期；N5：v2 schemas |

CL-4 P1 瀏覽器走查貼在 #228（[issuecomment-6416532488](https://github.com/Polalalabear/amidst/pull/228#issuecomment-6416532488)）：

- AC2、AC3、AC6、AC8 PASS；
- AC1、AC4、AC5 部分通過；
- AC7 BLOCKED（rc2）；
- 8 秒播放是否連續：`UNKNOWN`，因為瀏覽器窗格被隱藏，需要人眼確認；
- #228 的 AC2 查詢句要先和套件文件對齊才能合。

#### 4. Claude 自己的 PR 今天的更新

- [#127](https://github.com/Polalalabear/amidst/pull/127) 測試包 rc3 @`b995fe8`：綁定契約檔 SHA `b700bf86…`／`83da40f`；311 個單元測試通過；176 份 D73 之前的錄製各仍有 1 個 `COMMON_REASONS_LIST` FAIL，要等重錄。
- [#240](https://github.com/Polalalabear/amidst/pull/240)：yyin Q1／Q3 包設計（Draft，base mainline）。
- [#83](https://github.com/Polalalabear/amidst/pull/83)：T-2 已修（`1a03d8b`），等 Codex 審。

#### 5. 等 Codex

- [#231](https://github.com/Polalalabear/amidst/pull/231)：N1／N4（D85）；之後關閉 #212、#214、#216（保留分支），再用 `reasons[]` 重錄三份交接包，並做 #127／AC7 用的 link-record v2。
- [#238](https://github.com/Polalalabear/amidst/pull/238)：目錄凍結收據和 run 登記檔（D84）。
- [#235](https://github.com/Polalalabear/amidst/pull/235)：L1 hash、L2 標題、M1 的兩個選項。
- [#236](https://github.com/Polalalabear/amidst/pull/236)：`\Z`、註明多出的規則、時鐘值標為待定。
- [#234](https://github.com/Polalalabear/amidst/pull/234)：README 加 D83 一行；備註 3–5。
- 契約後續：§14 第 6 項的 v2 註記、§5.1 空行、可信 G4 收據格式提案。
- CX-7、CX-8：G4 之後。

#### 6. Claude 的待辦

| 何時 | 工作 | 模型 |
| --- | --- | --- |
| Codex 交件後 | 複核 #231、#238、#235、#236、#234 | Sonnet（程式）；Opus（圖、契約、資料） |
| 現在 | 修 #228 的 AC2 查詢句，再合 | Sonnet |
| #238 合併後 | 依 #240 設計建 yyin 包 | Sonnet |
| yyin 交回後 | 匯入 | Haiku |
| 匯入後 | 併入圖 v3 複核；G4 收據（逐邊核准加 M1） | Opus |
| 重錄之後 | 重跑 #127 rc3 | Sonnet |
| staging 併入 mainline 時 | 補 7 列進度（#220、#221、#222、#224、#226、#230、#232）加今天的 | Haiku |

#### 7. 使用者待辦

- 人眼確認 P1 套件的 8 秒播放（LOCAL，路徑在本機）：`cd "/Users/Shared/amidst-p1-clean-room-20261026/Amidst P1 最終測試" && ./start.command`
- 貼上 Claude 準備好的 Codex 回覆文字。
- 之後：G4 決定（含 M1），再做 P2。

#### 8. 組員（yyin）

- 正在看 r004 的三個澄清問題。
- 下一份 Q1／Q3 包在目錄凍結後出：靜態家具 Q1，加 Q3 的 8 題。人物／車輛 Q1 放第二包，等 CX-7 之後。

#### 9. 協調者慣例（使用者規定）

沿用 [10/25 的慣例](#h20261025)，加上今天新增的：

- 決策卡要列出每個選項的優點／缺點，建議選項放第一個。
- Codex 自己提的澄清問題，用「可直接貼上的回覆文字」給使用者，不用卡片。
- GitHub 留言和紀錄直接貼，不先問。
- 合併仍要使用者按；合併前核對 head SHA。
- 可用磁碟低於 8 GiB 要停。

---

<a id="h20261115"></a>

## 2026-11-15（原 docs/agents/COORDINATOR_HANDOFF_20261115.md）

> 已由 [COORDINATOR_HANDOFF_20261116.md](#h20261116) 取代。

### 協調者交接 2026-11-15

前一位協調者是 Claude Opus 5.5，從 `HANDOFF_COORDINATOR_20261110_B.md` 接手。下一個決策編號是 **D220**，要同步到 [#93](https://github.com/Polalalabear/amidst/issues/93)。

#### 2026-11-16 更新

以這一節為準。§1–§6 是 2026-11-15 交接時的原文，保留作為紀錄。問題和解法的完整清單在 `docs/operations/ISSUES_AND_FIXES_20261115.md`。

| 項目 | 值 |
|---|---|
| 主線 | `main` @ `8b023775`（#545 的 merge） |
| 8785 | pin `b24d6a26`（tree `ca6d0687`）。使用者 11-15 照 #545 的步驟更新，閘門全過（D234、D235）。舊 pin 備份在 LOCAL `local/demo-pin.74b84463.bak.json` |
| 下一個決策編號 | **D239**（D220–D238 在 [#93](https://github.com/Polalalabear/amidst/issues/93)） |

**已合併**（都由使用者執行，merge commit）：

| PR | 內容 | merge |
|---|---|---|
| [#537](https://github.com/Polalalabear/amidst/pull/537) | API 預算護欄 `ApiGuard` | `57dd761b` |
| [#538](https://github.com/Polalalabear/amidst/pull/538) | WP5 比較 harness，修好 OpenAI 繞過護欄的問題 | `18715e69` |
| [#539](https://github.com/Polalalabear/amidst/pull/539) | Codex N6 人物和烘焙場景 | `1aea09cd` |
| [#540](https://github.com/Polalalabear/amidst/pull/540) | 本交接文件 | `52b3ab2b` |
| [#541](https://github.com/Polalalabear/amidst/pull/541) | Argon N3：DP4 API／Agent 排序器（#532 已關閉） | `80f36220` |
| [#542](https://github.com/Polalalabear/amidst/pull/542) | core-e2e check 91 修正、`env_templates.sh` grep | `b24d6a26` |
| [#543](https://github.com/Polalalabear/amidst/pull/543) | WP5 Colab L4 和 Windows 資料包 | `4972f0f9` |
| [#545](https://github.com/Polalalabear/amidst/pull/545) | 8785 更新計畫，launcher 加 `--root-8cam` | `8b023775` |

**開著的 PR**：

- [#544](https://github.com/Polalalabear/amidst/pull/544)（Draft，`claude/feat-live-mode`）：即時模式 spike 報告和 N6 整合。可用設定是 3 鏡頭×2 fps（p50 約 240 ms）或 2 鏡頭×3 fps（p50 約 160 ms）；N6×烘焙場景的偵測率 69.1%。
- [#546](https://github.com/Polalalabear/amidst/pull/546)（`claude/feat-wp5`）：WP5 Colab DP1/DP3 修正（Colab v2 已驗證），加上 OpenAI 試跑校準 `f1ebdded`（實際花費 USD 0.1025）。D238：可以合併。session `wp5-calib-finish` 還在這條分支上收尾。
- [#547](https://github.com/Polalalabear/amidst/pull/547)（Draft，`claude/feat-live-llm-decision`）：即時模式的 LLM 決策設計 v1，使用者自己開的。

**§4 未完成工作（現況，依優先序）**：

1. **WP5 收尾**（進行中，session `wp5-calib-finish`）：降低 Colab v2 的 `INVALID_RESPONSE`（qwen 17–21%、llama 63–71%），修 `ollama ps` 的抓取時機（GPU 還沒證實）和 NL rule_agree 0/24 的指標，重產一鍵筆記本 v3；補完 OpenAI 校準報告。完成後由使用者合併 #546。
2. **待使用者決定**：OpenAI 正式額度（A USD 4／B USD 12／C USD 46）和 formal 2 s 逾時要不要放寬；真人模型對照實驗（D236）；8785 新 UI 要不要加 8CAM run（D234）；#547 的設計方向。
3. **即時模式**：#544 還是 Draft。CAM_ENTRY（19%）、R101_IN（47%）偵測率偏低。Codex 的偵測器加速和偵測改進，等真人模型的決定之後再寫指派（D230、D236）。
4. **延後**：N6 天花板亮度和接縫（D227）；`start_all_demo.ps1` 同步 `--root-8cam` 和 `.command` 的啟動時間註解（D234）；下次更新 8785 pin 時帶上 #543、#545。
5. **WP5 DP4 實跑**：runner 的 DP4 即時呼叫還是預留掛點（`DP4_LIVE_NOT_WIRED`，用 `--skip-types DP4`）。#541 的排序器已經合併，接上 runner 的工作還沒派。
6. 之後：Spotlight「追蹤」接 DP4 和即時模式；ENTRY 鏡頭加進 graph；第 5 章補 WP5 數字（`docs/report/CH5_CONCLUSION_DRAFT.md`）。
7. **流程教訓**（第 15、16 條）：長任務要分段 commit、分段 push；demo 和延遲量測期間不同時跑閘門，量測要記錄 load1。

#### 1. 現況與 SHA

| 項目 | 值 |
|---|---|
| 主線 | `main` @ `fe7b9d55`（GitHub 預設分支，D214）；`mainline/q1q5` 凍結在 `8c741451` |
| 本機 `~/amidst` | 分支 `main`、HEAD `74b84463`、工作樹乾淨，也就是 8785 demo pin（`local/demo-pin.json`） |
| 8785 | 仍鎖在 `74b84463`。更新到 `fe7b9d55` 被 core-e2e 擋住（見 §4-2） |
| 磁碟 | 約 11 GiB 可用。session 剩 5 GiB 就停，程式內建保護在 8 GiB |
| 遠端分支 | 40 條（11-15）。清理狀況見 §5 |
| Codex | 工作區已改為 `/Users/polalabear/amidst`（11-15 Codex 確認：實體目錄、`main`、`74b84463`、乾淨）；只在 scratchpad clone 寫檔 |

#### 2. 先讀

1. `CLAUDE.md`、`AGENTS.md`、`CLAUDE.local.md`（本機規則：協調者只派工，不在 `~/amidst` 改檔）
2. 本文件
3. [#93](https://github.com/Polalalabear/amidst/issues/93) 的 D200–D219（主線 main、單分支一功能 D216、D210 新方向）
4. `docs/operations/LOCAL_FOLDER_FINALIZE_20261115.md`（本機資料夾定案）
5. 需要時再讀：`docs/contracts/DP4_ATTENTION_RANKING_V1.md`、`docs/contracts/NL_QUERY_PARSE_V1.md`、`docs/contracts/R004_V2_4ACTOR_PRODUCTION_GATES_V1.md`

#### 3. 流程

- 每個任務都開新 session；模型照 `CLAUDE.md` 的表：雜務 Haiku low；程式、前端、審查、量測 Sonnet medium（難的用 high）；設計、文件、決策 Opus。
- 寫檔：`git clone --shared --no-checkout ~/amidst <scratch>/clone`，origin 設 GitHub，用完刪。同時最多 3 個寫檔 session，檔案不重疊。純審查用 `gh pr diff`，不 clone。
- 一條功能線一個 `claude/feat-<線>` 分支、一個 PR（D216），後續修正都 commit 在同一條。
- PR base 一律是 `main`，CI `checks` 要綠，只用 merge commit。**合併、刪分支、刪檔、kill 都由使用者在終端執行**（auto 模式會擋轉述的授權）；給指令要帶 `--repo Polalalabear/amidst`。
- Codex 和 Argon（Antigravity 的工具）的 PR：審查，有問題就直接修。Codex 的成果先給使用者看畫面再採用。
- 付費 API 一律經過 `ApiGuard`（#537）；先 dry-run，使用者核准金額才實跑。不讀 API key。
- 被 session 事件喚醒的回合不能開 session，改用提案卡。
- 決策寫到 #93，清理寫到 #486，報告素材寫到 #479。

#### 4. 未完成工作（依優先序）

> 這是 2026-11-15 的原文。現況見最上面的〈2026-11-16 更新〉。

1. **待合併**（使用者執行）：
   - [#537](https://github.com/Polalalabear/amidst/pull/537) API 預算護欄：審查通過。殘留 P2 #5：`OpenAIProvider` 繞過護欄，DP4 和 WP5 實跑前要接上護欄。
   - [#538](https://github.com/Polalalabear/amidst/pull/538) WP5 比較 harness、Colab L4、dry-run：CI 綠，**尚未正式審查**（已有提案卡 rv-538-wp5，Sonnet medium）。
2. **8785 更新準備**（未完成）：在 `fe7b9d55` 上，unit（2574 passed）、dependency、HTTP 200 都通過；core-e2e **失敗**，check 91「D139 multi view: active tile keeps a loaded image while playing」和 check 84 失敗，原因未查。real-e2e 900/1300 未跑，截圖和 `UPDATE_PLAN.md` 也未做。A4-1-8CAM 和 B4-1-8CAM 兩個 run 沒出現在 run 清單裡。另有 `scripts/local/env_templates.sh build` 的 relocate `grep` 無匹配時 exit 1 的 bug。紀錄：LOCAL `local/evidence/demo-update-prep-20261115/gate-out-rerun/`，以及 [#486 留言](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6890067952)。**下一步**：Sonnet medium 查修 core-e2e，在 `claude/feat-workbench-8cam` 這條線上，PR 開新的，因為舊 PR 已合併。pin 要使用者核准。
3. **即時模式 spike**（部分完成）：分支 `claude/feat-live-mode` @ `0fe62c29`，未開 PR。含 three.js 操作端和系統端兩個視窗（`frontend/live-mode/`）及後端 `src/amidst/live_mode/`。偵測：膠囊人形在 320×180 下只有 16.7%。MPS 延遲矩陣已跑完，5 組設定，檔案在 LOCAL `local/evidence/live-mode-spike-20261115/lat/*.latency.json`，**尚未解讀**。初步看 3 鏡頭在 5 fps 下跟不上（顯示 95–114 tick，丟 140–156 tick）。**還要做**：讀 p50/p95、first-lock、switch，跑 CPU 對照，截並排圖，寫報告，開 Draft PR。外觀要等 Codex N6。
4. **Codex N6**：[#539](https://github.com/Polalalabear/amidst/pull/539) Draft，含人物骨架、走/跑/待機動畫、烘焙光照的場景，CI 通過。要審查，給使用者看外觀，然後整合進即時模式。
5. **Argon N3**（[#532](https://github.com/Polalalabear/amidst/issues/532)）：DP4 的 API／Agent 版本，要經過 #537 護欄（用法已貼在 #532）。等 Argon 開 PR 後審查，20 個 xfail 閘門在 `tests/q1q5/test_dp4_attention_gates.py`。
6. **模型分析**：#537 和 #538 合併後重新打包 Windows/Colab 資料包，跑本機模型（L4，D175）；OpenAI pilot 要使用者核准金額（USD 100 分階段，D165/D166）。
7. 之後：Spotlight「追蹤」接 DP4 和即時模式；ENTRY 鏡頭加進 graph；第 5 章補 WP5 數字和 Argon 全名（`docs/report/CH5_CONCLUSION_DRAFT.md`）；研究計畫更新延後。

#### 5. 專案整理狀態（[#486](https://github.com/Polalalabear/amidst/issues/486)）

- 本機：home 只剩 `~/amidst`。11-15 刪了 6 個過時媒體資料夾，約 2.1 GiB（[#486 留言](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6889929146)）。B 組保留：`evidence/r004-cx7-d115-*` 2.1 GiB，舊 event-viewer 用；`q1q5-dynamic-baseline`；`p1-clean-room` 等。
- `~/Developer` 三個舊 symlink（`amidst` → office-canonical、`amidst-claude`、`amidst-q1q5`）：Codex 已換資料夾，可以刪了，指令在 `LOCAL_FOLDER_FINALIZE_20261115.md` (c)。
- 已合併、可刪的遠端分支（11-15 盤點，全部是 main 的祖先）：`argon/511-agent-wp3`、`argon/515-eval-toolchain`、`claude/445-demo-integration`、`claude/d211-gate-516-8cam`、`claude/d212-wb-8cam-grid`、`claude/d214-dp4-contract`、`claude/d214-wb-8cam-data`、`claude/feat-nl-search`、`claude/feat-ops-cleanup`、`claude/feat-workbench-8cam`、`claude/ui-redesign-v1`、`codex/486-vendor-deps`、`codex/516-eight-camera-completion`、`codex/d139-class-counts`、`codex/d147-d149-backend`。
- 保留：`archive/*`；關閉未合併的證據分支（argon/424、425、426、429，codex/445-independent-previews、467、516-four-actor-delivery、516-natural-walk-sample）；開著的 PR 分支；`claude/feat-live-mode`。
- [#445](https://github.com/Polalalabear/amidst/issues/445) 已於 11-15 關閉（Demo A 已驗收）。

#### 6. 第一個任務

1. 確認使用者已執行 §5 的刪除，然後在 #486 結案或留下剩餘項目。
2. 開 Sonnet medium session 查修 8785 core-e2e（§4-2），同時讓使用者決定 #537 和 #538 的合併。

---

<a id="h20261116"></a>

## 2026-11-16（原 docs/agents/COORDINATOR_HANDOFF_20261116.md）

### 協調者交接 2026-11-16

> 已被 [`COORDINATOR_HANDOFF_20261117.md`](#h20261117)（11-17 版）取代；本檔保留作為紀錄。

這份文件是新協調者對話的入口，取代 `COORDINATOR_HANDOFF_20261115.md`（舊檔保留作為紀錄）。前一位協調者是 Claude Opus 5.5。下一個決策編號是 **D242**，要同步到 [#93](https://github.com/Polalalabear/amidst/issues/93)。

- Model / effort：Opus 5.5 / medium（交接文件 session `ops-handoff-1116`）。
- 核對方式：下面每個 SHA 和狀態都在 2026-11-16 用 `gh pr view`、`gh issue view`、`gh api`、`git log` 逐條查過；查不到的寫 `UNKNOWN`。和協調者轉述不一致的地方在文中用「**核對**」標出。

#### 1. 現況與 SHA

| 項目 | 值 |
|---|---|
| 主線 | `main` @ `1fe6e716`（[#549](https://github.com/Polalalabear/amidst/pull/549) 的 merge）。`mainline/q1q5` 凍結在 `8c741451` |
| 本機 `~/amidst` | 8785 demo 的資料夾。分支 `main`、HEAD `b24d6a26`，工作樹乾淨（`git status --porcelain` 0 行） |
| 8785 | `local/demo-pin.json` 鎖在 `b24d6a26`（2026-11-15，使用者核准；閘門 `local/evidence/demo-update-prep-20261115/gate-20261115-1829/RESULT.txt`；D234、D235）。**不要在 `~/amidst` 改檔、切分支或 commit** |
| 磁碟 | 約 13 GiB 可用（`df -h ~`，2026-11-16）。session 剩 5 GiB 就停，程式內建保護在 8 GiB |
| 下一個決策編號 | **D242**（D241 是即時模式線的現況紀錄，[#93 留言](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6916303608)） |
| Codex | 目前沒有派工 |

**11-15～16 合併的 PR**（都由使用者執行，merge commit）：

| PR | 內容 | merge |
|---|---|---|
| [#537](https://github.com/Polalalabear/amidst/pull/537) | 付費 API 預算護欄 `ApiGuard` | `57dd761b` |
| [#538](https://github.com/Polalalabear/amidst/pull/538) | WP5 比較 harness（DP1/DP3/DP4/NL）、Colab L4、dry-run | `18715e69` |
| [#539](https://github.com/Polalalabear/amidst/pull/539) | Codex N6 人物和烘焙場景（#516） | `1aea09cd` |
| [#540](https://github.com/Polalalabear/amidst/pull/540) | 協調者交接 2026-11-15 | `52b3ab2b` |
| [#541](https://github.com/Polalalabear/amidst/pull/541) | Argon N3：DP4 API／Agent 排序器（#532） | `80f36220` |
| [#542](https://github.com/Polalalabear/amidst/pull/542) | core-e2e check 91 修正、`env_templates.sh` grep（= 8785 pin） | `b24d6a26` |
| [#543](https://github.com/Polalalabear/amidst/pull/543) | WP5 Colab L4 和 Windows 本機模型包 | `4972f0f9` |
| [#545](https://github.com/Polalalabear/amidst/pull/545) | 8785 更新計畫、launcher 加 `--root-8cam` | `8b023775` |
| [#548](https://github.com/Polalalabear/amidst/pull/548) | 進度導覽補到 #548（D239） | `17a480a6` |
| [#549](https://github.com/Polalalabear/amidst/pull/549) | 問題與解法紀錄 11-15～16、11-15 交接的更新節 | `1fe6e716` |

**關閉的 issue**：[#486](https://github.com/Polalalabear/amidst/issues/486)（大掃除，11-15）、[#532](https://github.com/Polalalabear/amidst/issues/532)（N3 DP4，11-15）、[#516](https://github.com/Polalalabear/amidst/issues/516)（4 人場景產製，11-16）。

#### 2. 先讀

1. `CLAUDE.md`、`AGENTS.md`、`CLAUDE.local.md`（本機規則：協調者只派工，不在 `~/amidst` 改檔）
2. 本文件
3. [#93](https://github.com/Polalalabear/amidst/issues/93) 的 D220–D241，以及 D241 前面三則還沒編號的即時模式留言（[6909798873](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6909798873)、[6910613701](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6910613701)、[6911702981](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6911702981)，第三則更正第二則）
4. `docs/operations/ISSUES_AND_FIXES_20261115.md`（11-15～16 的 16 個問題和解法）
5. 即時模式線：`docs/operations/LIVE_MODE_HANDOFF_20261116.md`（在 #544 分支 `claude/feat-live-mode` @ `ce948e59`，還沒進 main）
6. WP5：`docs/evaluation/WP5_OPENAI_CALIBRATION_20261115.md`（在 #546 分支 `claude/feat-wp5` @ `297e03e2`，還沒進 main）

#### 3. 流程

沿用 11-15 版 §3：

- 每個任務都開新 session；模型照 `CLAUDE.md` 的表：雜務 Haiku low；程式、前端、審查、量測 Sonnet medium（難的用 high）；設計、文件、決策 Opus。
- 寫檔：`git clone --shared --no-checkout ~/amidst <scratch>/clone`，origin 設 `https://github.com/Polalalabear/amidst.git`，用完刪。同時最多 3 個寫檔 session，檔案不重疊。純審查用 `gh pr diff`，不 clone。
- 一條功能線一個 `claude/feat-<線>` 分支、一個 PR（D216），後續修正都 commit 在同一條。
- PR base 一律是 `main`，CI `checks` 要綠，只用 merge commit。**合併、刪分支、刪檔、kill 都由使用者在終端執行**（auto 模式會擋轉述的授權）；給指令要帶 `--repo Polalalabear/amidst`。
- Codex 和 Argon 的 PR：審查，有問題就直接修。Codex 的成果先給使用者看畫面再採用。
- 付費 API 一律經過 `ApiGuard`（#537）；先 dry-run，使用者核准金額才實跑。不讀 API key。
- 被 session 事件喚醒的回合不能開 session，改用提案卡。
- 決策寫到 #93，報告素材寫到 #479。（#486 已關閉。）

11-16 新增：

- **同一條分支同時只能有一個寫手。** 11-16 有兩個 session 先後推上 #546（`claude/feat-wp5`），審查過的 head 因此過時、要重審（D240）。派工前先查 `list_sessions {"linked": true}`，同分支有 session 在跑就等它結束。
- **長任務要分段 commit、分段 push。** 11-15 有兩個 session 用完 5 小時額度，進度沒推上去（`ISSUES_AND_FIXES_20261115.md`）。brief 裡寫明每完成一段就 commit 並 push。

#### 4. 開著的 PR（CI `checks` 都綠，2026-11-16 查）

- **[#546](https://github.com/Polalalabear/amidst/pull/546)** `claude/feat-wp5` @ `297e03e2`（非 Draft）：WP5 Colab DP1/DP3 修正、OpenAI 校準、一鍵筆記本 v3。上次審查（APPROVE，head `fae92353`，D236）之後又加了 5 個 commit 和 1 個 merge：`f1ebdded`、`abcb18d0`、`e58ee033`、`4ec00d46`、`05a9e547`、merge `297e03e2`，要重新審查（D240 說提案卡 rv-546-v3 已放上；卡片現況這個 session 無法查，`UNKNOWN`）。使用者還要用 v3 在 Colab 重跑。兩邊都過才合併（D236、D240）。
- **[#544](https://github.com/Polalalabear/amidst/pull/544)** `claude/feat-live-mode` @ `ce948e59`（Draft）：即時模式的程式、量測、報告、Colab 包、交接文件。**還沒正式審查**；`tracker.py`、`people.py`、`advisor.py` 改了追蹤行為，照 `CLAUDE.md` 屬於複雜程式碼。
- **[#547](https://github.com/Polalalabear/amidst/pull/547)** `claude/feat-live-llm-decision` @ `77f64e6e`（Draft）：即時模式 LLM 決策設計稿 `docs/design/LIVE_MODE_LLM_DECISION_V1.md`，§0F 是問題和決定的總表。上一版 `34683b9c` 審查 NEEDS_CHANGES（P1 3、P2 7，[審查留言](https://github.com/Polalalabear/amidst/pull/547#issuecomment-6900140128)）。之後加了 6 個 commit（`ab47a9ba` … `77f64e6e`）；#544 的交接文件說「已經回覆並修改，沒有複審」，所以 P1/P2 是否都處理了要再審。

#### 5. 即時模式線現況（D241，已用 #544 核對）

來源：#544 的 `docs/operations/LIVE_MODE_HANDOFF_20261116.md`、`docs/evaluation/LIVE_MODE_TRACKER_20261116.md`、`docs/evaluation/LIVE_MODE_SPIKE_20261115.md` §10；#547 §0F。

**已完成**：

- 操作端用 WASD 操作，後台只看 8 個虛擬鏡頭的像素做偵測與追蹤；人物和場景已換成 N6 素材。
- 影像裁決（兩個以上候選人時把畫面送 OpenAI 判斷）已接進後台，預設關閉，預設模型 sol6.1（`gpt-6.1-sol`；使用者 11-16 決定，只在即時模式範圍取代 D237 的 terra）。
- 關聯範圍預設 3 m → 4 m：20 次實跑跟對 0.47 → 0.65；重播 0.51 → 0.63。
- 實跑記錄、評分、重播測試工具都有了。
- Colab 測試包使用者已在 L4 跑完。
- 單元測試：pytest `tests/live_mode` 29 項通過，node 測試 13 項通過（2026-11-16，交接文件 §9）。

**只有設計稿**（`docs/design/LIVE_MODE_GAME_DESIGN_V1.md`、`V2.md` §8）：越肩鏡頭、動畫混合、HUD 四項、小地圖、B 畫面跟隨視角、後台紀錄。

**未解決**（依重要程度）：

1. **4 m 加上正確的裁決後，A4 路線反而變差**：重播 A4 路線鏡頭跟對 0.41 → 0.32，回答越快越差，原因不明。**這條線的第一件事**，不花錢，全用重播（交接文件 §8 有指令和驗收條件）。
2. 影像裁決沒有證明能讓追蹤變好：放寬到 4 m 就有同樣效果，兩者疊加沒有更好。
3. A4 室外鏡頭偵測率低：N6 × 烘焙場景整體 69.1%，CAM_ENTRY 19%、R101_IN 47%、EXT_CAR 67%（`LIVE_MODE_SPIKE_20261115.md` §10）。
4. 程式沒有經過正式審查。
5. 其他（交接文件 §6）：8 鏡頭全推論每秒不到 1 輪；參數只在 A4/B4 調過；追蹤編號每 100 次觀測約對調 1.3 次；後台從標明 `must_not_enter: RUNTIME_INFERENCE` 的 `R004_SCENE_GEOMETRY_2D_V1.json` 讀攝影機參數，要改讀攝影機 catalog。

**延遲**：可用設定是 3 鏡頭 × 2 fps（p50 約 240 ms）、2 鏡頭 × 3 fps（p50 約 160 ms）（`LIVE_MODE_SPIKE_20261115.md` §10）。

#### 6. 預算

| 用途 | 核准上限 | 實際花費 | 出處 |
|---|---:|---:|---|
| WP5 OpenAI 試跑校準 | USD 3 | 0.113（帳本上界 0.1465） | `WP5_OPENAI_CALIBRATION_20261115.md`、D240 |
| 即時模式：單題影像裁決測試 | USD 4 | 0.88 | #544 交接文件 §5 |
| 即時模式：第一輪實跑 | USD 1 | 0.12 | 同上 |
| 即時模式：第二輪實跑 | USD 0.5 | 0.07 | 同上 |
| **合計** | | **約 1.18** | |

- **核對**：D241 寫「合計約 USD 1.07（WP5 校準 0.113＋即時模式線）」。#544 的帳本表顯示 **即時模式線自己就是 1.07**，加上 WP5 的 0.113，合計約 **USD 1.18**。新協調者要在 #93 用 D242 更正這個數字。花費是回應 token 數乘 D237 價目算的，不是 OpenAI 帳單。
- 先前核准的額度不能沿用；任何新的付費呼叫都要使用者在對話裡重新核准金額。
- 待使用者決定的額度：WP5 方案 **A terra USD 4（建議）**／B 混合 USD 12／C 三個模型 USD 46（D240）；#547 的 T2 約 USD 1.7（金額出自協調者轉述，在 #547 @ `77f64e6e` 找不到這個數字，`UNKNOWN`；另外 #547 §0F.4 說 T2 的單題延遲已經在 §0D 量過，即上表 USD 0.88 那一項，T2 還要不要另外花錢要先確認）。
- 預設模型 terra（D237）；即時模式的影像裁決用 sol6.1。要不要統一由使用者決定。

#### 7. 等使用者決定

1. #546：重新審查和 Colab v3 都過之後合併。
2. OpenAI 額度（§6）。
3. formal 的 2 s 逾時要不要放寬（所有模型延遲中位數約 2.7–4.7 s，D240）。
4. #547 的決策點（D240 交給使用者的 4 個）：先不接進 demo 預設、預設用「LLM 覆核」、先做不花錢的備援方案、T2 另外核准。**核對**：#547 §0F.3 和 #544 交接文件 §5 都記錄使用者 2026-11-16 已決定「B 畫面的 demo 預設用 LLM 覆核，LLM 主導做成可切換」，所以實際還待決定的是其餘 3 點。
5. 真人模型對照實驗（D236）。
6. 8785 新 UI 要不要加 8CAM run（D234）。
7. N6 天花板亮度和接縫（D227）。

#### 8. 之後要做

- 8785 下次更新時，一起帶上 #543、#545 的 launcher 修改，以及兩項 P2：`start_all_demo.ps1` 同步 `--root-8cam`、`.command` 的啟動時間註解（D234）。pin 要使用者核准。
- 第 5 章補 WP5 數字（`docs/report/CH5_CONCLUSION_DRAFT.md`）。
- 把 #93 上三則即時模式留言的使用者決定編成 D 號（交接文件 §5 請協調者編）。
- WP5 DP4 實跑：runner 的 DP4 呼叫還是預留掛點（`DP4_LIVE_NOT_WIRED`），接上的工作還沒派（11-15 交接更新節 §4-5）。
- Codex 目前沒有派工。

#### 9. 第一個任務（建議）

1. 確認 #546 的重新審查（Sonnet medium）和使用者的 Colab v3 結果，兩邊都過就請使用者合併。
2. 派 Sonnet medium 正式審查 #544（diff、`tests/live_mode`、`git diff --check`、merge-tree）；複雜程式碼部分由 Opus 判定被標出的點。
3. 派 Sonnet high 查「4 m 加裁決後 A4 變差」（在 `claude/feat-live-mode` 上；和 #544 審查的修改不能同時寫同一條分支，見 §3）。
4. 讓使用者一次決定第 7 節的額度、逾時和 #547 的其餘 3 點；同時用 D242 更正花費合計。

---

<a id="h20261117"></a>

## 2026-11-17（原 docs/agents/COORDINATOR_HANDOFF_20261117.md）

### 協調者交接 2026-11-17（晚間快照）

**快照時間：2026-11-17 晚間（UTC 約 15:55，#93 最後一則是 D277，15:51 UTC）。** 這份文件改寫了同日早上的版本（#562 合併的 `306dc2fa` 版，保留在 git 歷史）。早上版本之後的決策是 #93 的 D257–D277；本文整理到 D277 為止（第一版晚間快照到 D273，見本 PR 的 `c6e03889`）。

**新的協調者對話全程用繁體中文回覆**（D255、`CLAUDE.md`「Handoff」）。下一個決策編號是 **D278**，同步到 [#93](https://github.com/Polalalabear/amidst/issues/93)。

- Model / effort：Opus 5.5 / medium（交接文件 session `handoff-1117pm`）。
- 核對方式：PR、issue、分支、CI 狀態都在快照時用 `gh pr view`、`gh issue view`、`gh issue list`、`gh api repos/Polalalabear/amidst/branches` 重新查過；`~/amidst` 只讀了 HEAD、`git status --porcelain` 和 `local/demo-pin.json`。查不到的寫 `UNKNOWN`。

#### 1. 現況與 SHA

| 項目 | 值 |
|---|---|
| 主線 | `main` @ `0606b164`（[#563](https://github.com/Polalalabear/amidst/pull/563) 的 merge，2026-11-17 晚間）。`mainline/q1q5` 凍結在 `8c741451` |
| 本機 `~/amidst` | 8785 demo 的資料夾，分支 `main`、HEAD `e9db4fdf`、工作樹乾淨（0 行）。**不改檔、不切分支、不 commit、不 fetch** |
| 8785 pin | `local/demo-pin.json`：commit `e9db4fdf`、2026-11-17、gate `local/evidence/demo-update-prep-20261117/gate-20261117/RESULT.txt`（D270）。**比 main 舊一個 merge（缺 #563）**，等 #559 合併後一起更新 |
| 8785 執行方式 | **在終端面板分頁「8785 demo」前景執行**：`start_445_demo.command --port 8785 \| tee -a local/logs/demo-8785-20261117.log`（D277 第 4 點）。原因：用 `nohup`＋`&` 背景啟動兩次，都收到結束訊號停止（log 無錯誤，同 D269）。**關掉這個分頁 8785 就會停** |
| 8791 | `local/runtime/live-main` @ `e9db4fdf`，由 `local/runtime/start_live_8791.sh` 啟動（D264、D269；pid 24417 是 D269 當時的值，現在 `UNKNOWN`） |
| 磁碟 | 快照時約 12 GiB 可用（`df -h`）。早上曾掉到 7.6 GiB（D257），B3、B1 刪除後回升。第三個寫手要 9 GiB 以上，剩 5 GiB 就停 |
| 下一個決策編號 | **D278** |

**今天（11-17）合併的 PR**（都由使用者執行，merge commit）：

| PR | 內容 | merge |
|---|---|---|
| [#556](https://github.com/Polalalabear/amidst/pull/556) | 即時模式 `people.py` 併人修正 | `547a9e61` |
| [#546](https://github.com/Polalalabear/amidst/pull/546) | WP5 修正、OpenAI 校準、Colab v3.1 | `febc1707` |
| [#547](https://github.com/Polalalabear/amidst/pull/547) | 即時模式 LLM 決策設計稿 v1.9.1 | `da0dfe60` |
| [#557](https://github.com/Polalalabear/amidst/pull/557) | AGENTS／CLAUDE 規則、進度導覽 | `31a69177` |
| [#551](https://github.com/Polalalabear/amidst/pull/551) | 即時模式 B 畫面跟隨視角＋HUD | `21aacc8e` |
| [#562](https://github.com/Polalalabear/amidst/pull/562) | 交接規則（D255）＋早上的交接文件 | `444d15f3` |
| [#560](https://github.com/Polalalabear/amidst/pull/560) | WP5 DP4 實跑接線（Codex，#554） | `4142e26c` |
| [#561](https://github.com/Polalalabear/amidst/pull/561) | 即時模式推論排程（Codex，#553） | `e9db4fdf` |
| [#563](https://github.com/Polalalabear/amidst/pull/563) | LLM 開關（workbench-v2 設定 → 即時模式，預設關；P2 Host 檢查已補，head `6737accf`） | `0606b164` |

**開著的 PR：**

| PR | 分支 @ head | 狀態 |
|---|---|---|
| [#558](https://github.com/Polalalabear/amidst/pull/558) | `claude/experiment-record-latex` @ `b3246e00` | 非 Draft；`rv-558` 審查 NEEDS_CHANGES（[留言 6952193830](https://github.com/Polalalabear/amidst/pull/558#issuecomment-6952193830)），原 session `record-live-vs-offline` 修正中（D274 第 2 點） |
| [#559](https://github.com/Polalalabear/amidst/pull/559) | `codex/feat-live-detection` @ `2e654b26` | Draft，CI 綠；修改 C 聯合驗證 NOT_PASSED，Codex 做第三份指示中 |
| [#564](https://github.com/Polalalabear/amidst/pull/564) | `claude/feat-workbench-v2-ux` @ `b01f9ddc` | Draft，CI 綠；五點已完成，**待正式審查**，尚未在真的 8785 驗證（D274 第 3 點） |
| [#567](https://github.com/Polalalabear/amidst/pull/567) | `claude/feat-live-ab` @ `b8359bfb` | LIVE A/B 雙畫面規格與介面契約 `docs/specs/LIVE_MODE_AB_V1.md`（D275–D277）；§11 有 7 個待使用者決定的點（都有預設） |
| 本 PR | `claude/feat-ops-docs` | 交接文件、AGENTS.md 主要 UI、進度導覽 |

**還在的分支**（`gh api .../branches`）：`main`、`mainline/q1q5`、上表五條（含本 PR 的 `claude/feat-ops-docs`）、`claude/epic-d-agentic`（等使用者刪）、`argon/424-colab-oneclick-notebook`、`argon/425-research-m1-m4-baseline`、`argon/426-q4-tf-eval-tool`、`argon/429-windows-demo-start-eval`、`codex/467-r005-person-clip-proposal`（五條待判斷）、`archive/*` 9 條。今天合併的 `codex/feat-wp5-dp4`、`codex/feat-live-schedule`、`claude/feat-workbench-llm-toggle` 已刪。刪除建議見過時項目總清單（[#486 留言 6953090327](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6953090327) §1）。

#### 2. 先讀

1. `CLAUDE.md`、`AGENTS.md`、`CLAUDE.local.md`（本機規則：協調者只派工，不在 `~/amidst` 改檔）
2. 本文件
3. [#93](https://github.com/Polalalabear/amidst/issues/93) 的 D257–D277（`gh issue view 93 --repo Polalalabear/amidst --comments`，從 D257 開始逐則讀）
4. 即時模式：`docs/operations/LIVE_MODE_HANDOFF_20261116.md`、`docs/design/LIVE_MODE_LLM_DECISION_V1.md` §0F
5. #559 的聯合驗證報告（[`docs/evaluation/LIVE_DETECTION_SCHEDULE_JOINT_20261117.md` @ `2e654b26`](https://github.com/Polalalabear/amidst/blob/2e654b268624d023ac2d16f9e90c6fdaf4778198/docs/evaluation/LIVE_DETECTION_SCHEDULE_JOINT_20261117.md)）和第三份指示（[#559 留言 6952347393](https://github.com/Polalalabear/amidst/pull/559#issuecomment-6952347393)）
6. WP5：formal 結果（[#93 留言 6941051090](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6941051090)）、逾時分析（[#93 留言 6950053674](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6950053674)）
7. 舊工作台下線計畫（[#486 留言 6950051568](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6950051568)）與 Opus 決定（[#486 留言 6952944724](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6952944724)）
8. 過時項目總清單（[#486 留言 6953090327](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6953090327)）
9. LIVE A/B 規格：[#567](https://github.com/Polalalabear/amidst/pull/567) 的 `docs/specs/LIVE_MODE_AB_V1.md`（§11 待決定）與 Codex issue [#566](https://github.com/Polalalabear/amidst/issues/566)

#### 3. 流程（今天新增或再確認的）

沿用早上版本 §3 與 `CLAUDE.md`、`AGENTS.md`。今天的補充：

- **主要 UI 是 `frontend/workbench-v2/`**（8785 由 `scripts/serve_demo_integration.py` 提供）。舊的 `frontend/workbench/` 下線中（D268）。今天 #563 的 brief 寫成舊工作台而做錯一次（D267），寫 brief 時要寫 workbench-v2。
- **8785 的更新流程**（D269、D270）：在 clone 跑 gate（node、focused pytest、`check_demo_dependencies.py --smoke`、real-e2e）→ 寫 `RESULT.txt` → 使用者在終端快轉 `~/amidst`、`scripts/demo_pin.py approve`、`start_445_demo.command --port 8785`。gate 24 小時內有效。
- **8785 在終端面板分頁「8785 demo」前景執行**（D277 第 4 點）：背景啟動（`nohup`＋`&`）兩次都收到結束訊號停止，改前景後正常。之後重啟 8785 也照這個方式，不要關那個分頁。
- **8791 從 `local/runtime/live-main` 跑 main**（`local/runtime/start_live_8791.sh`），不再用舊 scratchpad clone（C1）。
- **Sonnet 每週額度曾用完**（D272，原本 11/22 09:00 重置）；使用者已重置（D273）。額度再用完時改用 Opus medium 派同樣的工作，並在 #93 記一筆。
- **中斷或失敗的 session 不會自己回報**：用 `gh` 查產出（PR head、留言），再對原 session 發訊息續做。

#### 4. 所有工作，依類型分類

##### 4.1 8785 demo

| 工作 | 預計產出 | 目前進度 | 卡住的部分（卡在誰、等什麼） |
|---|---|---|---|
| 8785 更新到 main | 8785 跑 main 最新版 | **已完成**（D270）：`~/amidst` 快轉到 `e9db4fdf`，`scripts/demo_pin.py approve` 通過（gate `local/evidence/demo-update-prep-20261117/gate-20261117/RESULT.txt`），`start_445_demo.command --port 8785` 啟動；`/workbench-v2/` 回 200，四個 run（B-05、A4-1、B4-1、r005）載入 | 無 |
| 8791 改從 main | 即時模式跑 main | **已完成**（D264、D269）：`local/runtime/live-main` @ `e9db4fdf`，`start_live_8791.sh`；改用 N6 正式資產 `local/data/live-assets-20261115` | 無 |
| 8785／8791 下午停止原因 | 查明 | **已查**（D269 第 1 點）：兩者都收到結束訊號後正常退出（8785 14:15:17、8791 14:58:03），不是系統殺、不是崩潰或重開機；送訊號者查不到 | 無（原因 `UNKNOWN`，再發生時再查） |
| 8785 晚間又停止 | 8785 持續可用 | 晚間又收到結束訊號停止（log 無錯誤）。協調者改在終端面板分頁「8785 demo」前景執行，`/workbench-v2/` 回 200（D277 第 4 點） | 無；關掉分頁就會停。送結束訊號的來源仍 `UNKNOWN` |
| 合併後再更新一次 | 8785、8791 含 #559、#563（和 #564） | 未開始。#563 已合併（`0606b164`），但兩個介面仍在 `e9db4fdf` | 等 #559 合併（一起含 #563）；之後照 §3 的流程跑 gate，pin 和啟動交使用者（8785 照前景方式） |
| N6 天花板亮度和接縫 | — | 未決（D227） | **等使用者決定** |
| 新 UI 要不要加 8CAM run | — | 未決（D234） | **等使用者決定** |

##### 4.2 即時模式

| 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|
| 推論排程 #553／#561（Codex） | 只推論作用中鏡頭和鄰居 | **已合併** `e9db4fdf`；#553 已關閉 | 無 |
| 偵測率＋demo 啟動入口 #552、#555／[#559](https://github.com/Polalalabear/amidst/pull/559)（Codex） | A4 室外鏡頭偵測率提高；即時模式啟動入口 | 修改 A 完成（`efb2f498`，ENTRY 0.05 保留，D266）；修改 C（merge main、聯合驗證）**NOT_PASSED**（[Codex 留言 6941946203](https://github.com/Polalalabear/amidst/pull/559#issuecomment-6941946203)）：固定 RGB A4 跟對 0.705→0.695（tick 56 adaptive 漏看）、新實跑 B4 跟對 0.451→0.333、失聯 0.235→0.303、ENTRY 重新鎖定兩模式皆 censored；adaptive 每秒輪數 +20–30%。**使用者決定：先修排程與重新鎖定再合併**，不改回 `--schedule all`（D273） | **卡在 Codex**：做第三份指示（[#559 留言 6952347393](https://github.com/Polalalabear/amidst/pull/559#issuecomment-6952347393)：漏看修正、B4 原因、ENTRY 可量測定義；通過條件不變）。交回後派審查（複雜程式），通過再請使用者合併 |
| LLM 開關 [#563](https://github.com/Polalalabear/amidst/pull/563) | workbench-v2「設定 → 即時模式」切換 LLM 覆核／主導，預設關、不接付費 provider | **已合併** `0606b164`（D276 第 3 點）：瀏覽器直連 live `/config`，live 端只對本機工作台來源開 CORS；差異重審的 P2（`Host` 檢查）已補（head `6737accf`） | 無。8785／8791 還沒含它（等 #559 一起更新）；P3（`advisor_model` 非字串、IPv6）未處理 |
| workbench-v2 五點易用性 [#564](https://github.com/Polalalabear/amidst/pull/564) | (1) 搜尋 Enter 直接進入；(2) 追蹤分頁搜尋＋`FORBIDDEN_DATA_SCOPE` 原因；(3) 概況卡片排版；(4) 易讀地點／鏡頭名稱；(5) live 模式入口（D271） | 五點完成，head `b01f9ddc`，CI 綠（D274 第 3 點）。`FORBIDDEN_DATA_SCOPE` 不是 GT 隔離，而是伺服器重啟後 session 失效（改自動續期）與拒絕原因碼被遮掉（改具體說明）；3 個鏡頭名稱標 UNKNOWN | **待正式審查**（Sonnet medium）；尚未在真的 8785 驗證；3 個 UNKNOWN 名稱等使用者確認；之後使用者看截圖、合併 |
| LIVE A/B 雙畫面 規格 [#567](https://github.com/Polalalabear/amidst/pull/567)／實作 [#566](https://github.com/Polalalabear/amidst/issues/566)（CX-L5） | A（操作端）WASD、開始前選角色（中途不可換）；B（系統端）和 8785 追蹤模式一樣選要追蹤的人，只用鏡頭畫面（GT 隔離）；沒被選的人物照腳本移動；人物不碰撞（半徑預設 0.30 m）；目的只是展示即時追蹤（D275、D276） | 規格與介面契約已起草（`live-ab-spec`，`docs/specs/LIVE_MODE_AB_V1.md`）；Codex issue #566 標 `blocked` | **規格 §11 的 7 點等使用者決定**（都有預設）；#566 等 #559 合併與 Codex 確認契約，可先做 `crowd.mjs`＋`sim.mjs`＋A 選單與 `scripts/live_ab_score.py`（D277 第 1 點）。實作交 Codex，Claude 寫規格與審查 |
| 失聯後重新取得 | 分段門檻：短失聯自動接回；超過門檻放寬搜尋 | 協調者建議（D254 第 3 點） | **等使用者決定**（D254-3 分段門檻） |
| 真模型在「目標不在名單」時怎麼答 | 驗證模型會答「都不是」 | 未驗證（`LIVE_MODE_LLM_DECISION_V1.md` §0F.4 第 2 項：sol6.1 約 USD 0.2、三模型約 USD 1，或不測） | **等使用者決定**花費（不能用 WP5 的 USD 46） |
| 不花錢的備援方案與 T2 | 失聯主動接回、候選名單改用速度預測，用重播驗收 | §0F.4 第 1 項建議先做 | **等使用者決定** |

##### 4.3 WP5 與 Agent 決策

| 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|
| 方案 C pilot | terra／sol／astra 各 72 步 | **完成**（D256 與補充）：格式錯誤 0；逾時退回（模型合計）terra 11%、sol 19%、astra 60%；實測約 USD 0.51（帳本估計 1.73） | 無 |
| 方案 C formal | terra、sol 的 5 s 正式組＋NL 10 s 放寬組（astra 不跑、DP4 跳過） | **完成**（D260 另開帳本、上限 USD 6；結果 [留言 6941051090](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6941051090)）：格式錯誤 0、無 DENIED；逾時退回 terra 10.7%、sol 20.0%（sol DP3 35.6%）；NL 放寬到 10 s 後兩模型 0／40。**實測 USD 0.854**（帳本估計 1.233）。執行時以環境變數把每日／每分鐘呼叫次數上限調高（金額上限不變） | 無 |
| 逾時原因分析 | 為什麼逾時、怎麼改 | **完成**（[留言 6950053674](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6950053674)，0 次付費呼叫）：5 s 上限落在模型延遲分布中間；自由文字 `rationale` 讓輸出過長；pilot 樣本小且模型依序跑；astra 固定開銷約 2.2 s，5 s 不可行。建議：逾時分題型（NL／DP3 用 10 s）、縮短輸出、加大 pilot 並讓合成題有分歧 | **等使用者決定**要不要採用改善建議（要改程式和再花錢） |
| DP4 實跑接線 #554／#560（Codex） | runner 真的呼叫 DP4 | **已合併** `4142e26c`（D266）；#554 issue 還開著（工作已完成，可關） | 真實 provider 的 DP4 smoke **等使用者核准金額**（不擋合併，D261） |
| 預算 | — | 專案 OpenAI 累計實測約 **USD 1.36**（pilot 0.51＋formal 0.854；不含 11-16 以前的約 1.18，含的話約 2.54）；帳本估計約 2.96（兩本帳分開）。方案 C 總上限 USD 46 不變，只給 WP5 | 額度不跨用途（D242） |

> 註：D266 寫「專案 OpenAI 累計實測約 1.36」，口徑是方案 C 的 pilot＋formal；早上版本的「約 1.69」含 11-16 以前的 1.18。兩個數字口徑不同，引用時寫清楚。

##### 4.4 研究紀錄與報告

| 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|
| 實驗紀錄 v4 [#558](https://github.com/Polalalabear/amidst/pull/558) | 新章：預錄與 live 的差異、參數依據、LLM 介入 | `rv-558` 審查 **NEEDS_CHANGES**：P1「formal 未跑」已過時；P2 `decision_source` 在預設 `reseed` 下不會出現 `AGENT`、4 m 候選名單只適用 `SILENT_PICK`；P3 三項。原 session `record-live-vs-offline` 修正並重編 PDF 中（D274 第 2 點），head 已到 `b3246e00` | 等寫手交回 → 複審 → 使用者合併 |
| 報告素材 #479 | 持續追加「報告素材」留言 | 進行中（owner:argon epic，實際由 Claude 追加） | 今天的 WP5 formal、逾時分析、#559 聯合驗證都還沒追加到 #479（`UNKNOWN`，快照時沒逐則查） |
| 第 5 章 WP5 數字 | `docs/report/CH5_CONCLUSION_DRAFT.md` 5.3、5.4 補數字 | 未做；pilot 與 formal 數字都有了 | 可派（Opus medium），建議等 #558 修正後一起對齊口徑 |

##### 4.5 流程與整理

| 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|
| 冗餘檔案清理（#486） | 刪重複的 LOCAL 檔 | 盤點（`inv-redundant`）→ Opus 決定（[#486 留言 6940461147](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6940461147)）。**B3（143 MB）、B1（488 MB）已刪**；**C1**（舊 scratchpad clone 223 MB）原因是 8791 用它當 cwd，8791 已改從 `local/runtime/live-main` 跑，可以刪 | C1、舊 pid、`/private/tmp/claude-501/glb` 的刪除指令已交使用者（D264、D268）；使用者是否已執行 `UNKNOWN`，下次要確認 |
| ledger 小修（R3） | `CO-claude` 改 `deletable`；`LOC-shared-cleanroom` 更新檔數／SHA／大小、註明刪除日期（D262 第 2 點） | 未做；已併入過時清單的 R3 | #565 合併後，在 `claude/feat-ops-docs` 做 |
| 舊工作台 `frontend/workbench/` 下線（R1） | 刪 `frontend/workbench/` 62 檔（33,410 行），改 15 檔；`/`（8016）302 轉到 `/workbench-v2/`；不打 tag，以 `0606b164` 留存 | **Opus 決定完成**（`opus-retire-old-wb`，[#486 留言 6952944724](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6952944724)）：盤點更正 4 處，`office_demo_backend.py`、`core-legacy-e2e.mjs` 保留；過時清單另補列 Office 舊 demo 8 檔（併入 commit 3）。實作分支 `claude/feat-retire-old-workbench`，4 個 commit。本 PR 已把 AGENTS.md 主要 UI 改成 workbench-v2 | **等使用者確認 Office 舊啟動器 3 檔下線**（建議是）；建議 #565 先合再派實作；`office_display` 被 `configs/q1q5/*_sources.json` 列出，實作前要先確認（UNKNOWN） |
| 過時項目總清單 | 分支、文件、程式碼、issue、LOCAL 的過時項目與終端指令、依賴順序 | **完成**（Opus high，[#486 留言 6953090327](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6953090327)）。可立即執行：刪 5 條分支（`claude/epic-d-agentic`＋4 條有同 SHA tag 的 `archive/local/phase1/*`）、關 #554、刪 C1（222 MB）、搬 tmp 雜項。約 30 份文件封存（留原位加頭＋索引，不刪）。需改 repo 的 R1（舊工作台下線＋Office 補列 8 檔）、R2（文件封存）、R3（ledger）、R4（`frontend/live-mode/measure/smoke.mjs` 不寫 `/private/tmp`） | 可立即執行的刪除／關閉交使用者在終端執行；argon/424、425、426、429、codex/467 **等使用者確認**；R1 走 `claude/feat-retire-old-workbench`，R2–R4 進 `claude/feat-ops-docs`，都等 #565 合併後派 |
| 進度導覽 | 補到 #564 | 本 PR 做 | 等合併 |
| 舊分支 | `argon/424`、`425`、`426`、`429`、`codex/467` 去留；`claude/epic-d-agentic` 刪除 | 過時清單建議：`claude/epic-d-agentic` 可立即刪；五條舊分支建議刪（commit 都留在 `refs/pull/<n>/head`） | 五條**等使用者確認**；刪除由使用者在終端執行 |
| `archive/*` 9 條 | — | 過時清單：4 條 `archive/local/phase1/*` 有同 SHA tag，可立即刪；另 5 條（被 main 引用或沒有其他副本）保留 | 刪除由使用者在終端執行 |
| 磁碟 | 維持 9 GiB 以上 | 快照時約 12 GiB | 系統 swap、Chrome 更新暫存、Claude `vm_bundles` 11 GiB 等 repo 外大項（D257）由使用者決定 |

##### 4.6 Codex 與 Argon

| 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|
| Codex：#559 第三份指示 | 修漏看、查 B4、定義 ENTRY 可量測；通過聯合驗證 | 進行中（D273；同分支、保持 Draft） | 等 Codex 交回。#552、#555 都併在 #559 |
| Codex：#566 CX-L5 LIVE A/B 實作 | 照 #567 規格實作 A 選角色、B 選目標、人物不碰撞 | 已開 issue，`blocked` | 等 #559 合併與 Codex 確認契約；可先做不和 #559 重疊的部分（D277 第 1 點） |
| Codex：#554 | 關 issue | 工作已由 #560 合併；過時清單列為可立即關閉 | 協調者或 Haiku 留言關閉 |
| Argon | — | 沒有派工。`owner:argon` 開著的只有 epic [#479](https://github.com/Polalalabear/amidst/issues/479)；Argon／Codex 拉取佇列 [#434](https://github.com/Polalalabear/amidst/issues/434) 已在 2026-11-08 關閉（D132 改到 #93） | 需要時再派 |

#### 5. 等使用者決定

1. **LIVE A/B 規格 §11 的 7 點**（#567，都有預設）。
2. **舊工作台下線時 Office 舊啟動器 3 檔是否一起下線**（建議是；#486 留言 6952944724）。
3. **過時清單**：可立即執行的項目（刪 5 條分支、關 #554、刪 C1、搬 tmp 雜項）交使用者執行；`argon/424`、`425`、`426`、`429`、`codex/467` 去留。
4. **#565**（本 PR）合併——R1–R4 和舊工作台下線實作都排在它後面。
5. **#559**：Codex 第三份指示交回後的審查結果與合併（D273）。
6. **#564**：審查後看截圖、確認 3 個 UNKNOWN 鏡頭名稱、合併。
7. **#558**：修正後合併。
8. **失聯後重新取得的分段門檻**（D254 第 3 點）。
9. **LLM 不花錢的備援與 T2**（§0F.4 第 1 項）；**真模型驗證花費**（§0F.4 第 2 項：sol6.1 約 USD 0.2、三模型約 USD 1，或不測）。
10. **WP5 改善建議**（逾時分題型、縮短輸出、加大 pilot）要不要做，以及 DP4 smoke 的金額。
11. **N6 天花板亮度和接縫**（D227）；新 UI 要不要加 8CAM run（D234）。

#### 6. 給新協調者的第一件事（依 D277 的順序）

開始前先用 `gh pr view 558 559 564 565 567` 和 `gh issue view 93 --comments`（D277 之後）確認快照後有沒有新進度。

1. **LIVE A/B**（D277 第 1 點）：把 #567 規格 §11 的 7 點問使用者（AskUserQuestion，附預設），決定後更新規格、合併 #567；把可先做的部分（`crowd.mjs`＋`sim.mjs`＋A 選單、`scripts/live_ab_score.py`）告訴 Codex（給可直接貼上的文字）。#566 在 #559 合併、Codex 確認契約後改 `ready`。
2. **舊工作台下線**（D277 第 2 點）：問使用者 Office 舊啟動器 3 檔是否下線；#565 合併後派實作（分支 `claude/feat-retire-old-workbench`，照 #486 留言 6952944724 的 4 個 commit，含過時清單補列的 Office 8 檔；先確認 `office_display` 的來源 pin）。
3. **過時項目**（D277 第 3 點）：可立即執行的刪除／關閉指令（#486 留言 6953090327）交使用者在終端執行；問五條舊分支去留；#565 合併後派 R2–R4（進 `claude/feat-ops-docs`）。
4. **8785**（D277 第 4 點）：維持終端面板分頁「8785 demo」前景執行，不要關。#559 合併後照 §3 的流程把 8785、8791 更新到 main（含 #563），8785 照前景方式重啟。
5. **開著的 PR**（D277 第 5 點）：#558 修正交回後複審；#559 等 Codex，交回後 Sonnet 審查＋Opus 判定；#564 派正式審查（Sonnet medium）；#565 請使用者合併；#567 見第 1 點。

#### 7. Session 清單（快照時）

`list_sessions {"linked": true}` 列得到時以它為準。快照時與前一位協調者連結的 session：

| 名稱 | session id | 狀態 | 內容 |
|---|---|---|---|
| `wb2-ux-opus` | `local_a9d969c1-ec18-433c-a79c-2bdb2771696e` | 快照時 `UNKNOWN` | #564 workbench-v2 五點（已完成五點） |
| `live-ab-spec` | `UNKNOWN` | `UNKNOWN` | #567 LIVE A/B 規格、#566 |
| `opus-retire-old-wb` | `UNKNOWN` | 完成 | 舊工作台下線決定（#486 留言 6952944724） |
| 過時清單（Opus high） | `UNKNOWN` | 完成 | #486 留言 6953090327 |
| `rv-563-v2` | `local_87e00904-c5b9-4d65-aede-7b0600b4513f` | 完成 | #563 差異重審 APPROVE |
| `rv-558` | `local_ebe77247-9a07-4b56-b782-46c5c360156c` | 完成 | #558 審查 NEEDS_CHANGES |
| `llm-toggle` | `local_0c115a14-faa9-4091-a055-70d6c0ea5f53` | 完成 | #563 寫手（P2 已補、已合併） |
| `563-llm` | `local_111a94ce-cce7-4eff-9cc7-6ef6e147007a` | 完成 | #563 |
| `wp5-c-formal` | `local_d877f162-0e11-42db-83f0-e0d43516e6f5` | 閒置 | WP5 formal 執行 |
| `wp5-api-analysis` | `local_396faf85-524a-407c-a03f-a867132c0c76` | 閒置 | WP5 逾時分析 |
| `live-8791-main` | `local_6f39c05e-fb5c-45df-9938-dbc0483b3681` | 閒置 | 8791 改從 main |
| `demo-ports-main` | `local_bc7f709c-1848-4b09-816d-af72fdf25297` | 閒置 | 8785／8791 停止原因與 8785 gate |
| `retire-old-wb-plan` | `local_c841eca7-cd71-402e-9075-bcbd424afa5c` | 閒置 | 舊工作台下線計畫 |
| `inv-redundant` | `local_8c9d9584-3c47-47c1-a1fb-c18221a0949f` | 閒置 | 冗餘檔案盤點 |
| `sonnet-486` | `local_ffa8eab6-d802-41f7-9ad2-da46d163a878` | 閒置 | 清理候選核對 |
| `opus-486-b3-c1-b1` | `local_cddff288-6b2f-46a6-a865-e494bb562eca` | 閒置 | 清理刪除決定 |
| `opus-559-560-561` | `local_266aae80-db7d-4be5-b60f-b99b306bf92a` | 完成 | Codex 三個 PR 的 Opus 判定 |
| `rv-559`、`rv-560`、`rv-561` | `local_9e90289a-…`、`local_d6eacff2-…`、`local_f92543b6-…` | 完成 | Codex 三個 PR 的 Sonnet 審查 |
| `handoff-1117pm` | （本 session） | — | 本文件 |

`record-live-vs-offline`（#558 寫手，D274 已請它修正）、`live-ab-spec`、`opus-retire-old-wb` 不在本 session 看得到的連結清單內，id `UNKNOWN`；用 `list_sessions {"linked": true}` 找，找不到就開新 session。

---

<a id="h20261118"></a>

## 2026-11-18（原 docs/agents/COORDINATOR_HANDOFF_20261118.md）

### 協調者交接 2026-11-18

**快照時間：2026-11-18（UTC 約 02:45，#93 最後一則是 D310，02:39 UTC）。** 前一份是 `docs/agents/COORDINATOR_HANDOFF_20261117.md`（11-17 晚間快照，整理到 D277）。本文整理 D278–D310（D283 是無編號留言索引，補編 D284–D301）。

**新的協調者對話全程用繁體中文回覆**（D255、`CLAUDE.md`「Handoff」）。下一個決策編號是 **D311**，同步到 [#93](https://github.com/Polalalabear/amidst/issues/93)。

**工作清單的唯一來源是 [#93](https://github.com/Polalalabear/amidst/issues/93) 本文**（D281）。本文 §4 是快照，和 #93 本文不一致時以 #93 本文為準。

- Model / effort：Opus 5.5 / medium（交接文件 session `handoff-1118`）。
- 核對方式：`gh issue view 93`（本文與留言）、`gh pr list --state open`、`gh pr list --state merged`、`gh pr checks`、`gh issue list --state open`、`gh api repos/Polalalabear/amidst/branches`、`git ls-remote`；`~/amidst` 只讀了 HEAD、`git status --porcelain` 和 `local/demo-pin.json`；session 用 `list_sessions {"linked": true}`。查不到的寫 `UNKNOWN`。

#### 1. 現況與 SHA

| 項目 | 值 |
|---|---|
| 主線 | `main` @ `894bdd9e`（[#559](https://github.com/Polalalabear/amidst/pull/559) 的 merge，2026-11-18 02:34 UTC）。`mainline/q1q5` 凍結在 `8c741451` |
| 本機 `~/amidst` | 8785 demo 的資料夾，分支 `main`、HEAD `e9db4fdf`、工作樹乾淨（`git status --porcelain` 0 行）。**不改檔、不切分支、不 commit、不 fetch** |
| 8785 pin | `local/demo-pin.json`：commit `e9db4fdf`、2026-11-17、gate `local/evidence/demo-update-prep-20261117/gate-20261117/RESULT.txt`（SHA-256 `4d9d6930febf123daa9c19b8205ad0a311c4be08ae64b2ed87e3f85afa267887`）、approved_by 使用者（D270）。**比 main 舊**（缺 #563、#558、#567、#575、#586、#587、#590、#595、#559），等 [#576](https://github.com/Polalalabear/amidst/issues/576) 一起更新 |
| 8785 執行方式 | 在終端面板分頁「8785 demo」**前景執行**（D277 第 4 點）。背景啟動兩次都收到結束訊號停止。**關掉這個分頁 8785 就會停** |
| 8791 | 從 `local/runtime/live-main` @ `e9db4fdf` 跑（`local/runtime/start_live_8791.sh`，D264、D269）；pid `UNKNOWN` |
| 磁碟 | 快照時約 12 GiB 可用（`df -h ~`）。第三個寫手要 9 GiB 以上，剩 5 GiB 就停 |
| OpenAI | 專案實測至今不到 USD 3；**可用額度約 USD 50**（D306） |
| 下一個決策編號 | **D311** |

**11-17 晚間到 11-18 合併的 PR**（merge commit；11-18 起依 D305 由協調者直接合併）：

| PR | 內容 | merge |
|---|---|---|
| [#565](https://github.com/Polalalabear/amidst/pull/565) | 11-17 晚間交接文件、AGENTS 主要 UI 改 workbench-v2 | `3137a1ca` |
| [#558](https://github.com/Polalalabear/amidst/pull/558) | 實驗紀錄 v4.2（預錄與 live 的差異、參數依據、LLM 介入） | `edb96a31` |
| [#567](https://github.com/Polalalabear/amidst/pull/567) | LIVE A/B 雙畫面規格與介面契約 v2（D279） | `2f013cb8` |
| [#575](https://github.com/Polalalabear/amidst/pull/575) | 舊工作台 `frontend/workbench/` 與 Office 舊啟動器下線（R1） | `59782b1d` |
| [#586](https://github.com/Polalalabear/amidst/pull/586) | 報告第 5 章 WP5 數字（#581） | `bd1dc614` |
| [#587](https://github.com/Polalalabear/amidst/pull/587) | LIVE A/B v2.1（C-5 補定義）＋重新取得契約 v1（#585） | `590afb34` |
| [#590](https://github.com/Polalalabear/amidst/pull/590) | R2 文件封存、R3 ledger、進度導覽、工作清單指向 #93（#580） | `703ce625` |
| [#595](https://github.com/Polalalabear/amidst/pull/595) | Office 補列檔下線（#579） | `6bf287d7` |
| [#559](https://github.com/Polalalabear/amidst/pull/559) | 即時模式偵測率＋隔離 demo 啟動入口（Codex，#552、#555） | `894bdd9e` |

**開著的 PR：**

| PR | 分支 @ head | CI | 狀態 |
|---|---|---|---|
| [#564](https://github.com/Polalalabear/amidst/pull/564) | `claude/feat-workbench-v2-ux` @ `a2c80351` | 綠 | Draft；審查 APPROVE（D280）；D302 鏡頭改名已推；**等使用者看五點截圖**（`local/evidence/wb2-ux-564-20261118/`（SHA256SUMS.txt `4eb1e6dcd8617f14d5a072c884bc8d18902f8944bdf5a7d79f565d3f64b8de2e`）），OK 就合併 |
| [#584](https://github.com/Polalalabear/amidst/pull/584) | `codex/feat-live-ab` @ `96c73e0e` | 跑中（快照時） | Draft；Codex 交 #568–#570、#573，#568 C-5 已通過（D309）；預審 P2 兩點交 Codex（D308 第 5 點）；**`rv-584` 正式審查中** |
| [#599](https://github.com/Polalalabear/amidst/pull/599) | `codex/feat-n6-ceiling` @ `3c545fe5` | 綠 | Draft；N6 天花板（#593，CAM_WIDE 天花板平均亮度 137.72→121.25），**`rv-599-603` 正式審查中** |
| [#603](https://github.com/Polalalabear/amidst/pull/603) | `codex/feat-workbench-8cam` @ `7b170f52` | 綠 | Draft；8785 加 8CAM run（#594），獨立埠 smoke 通過；完整 gate 隨 #576；**`rv-599-603` 正式審查中** |
| [#604](https://github.com/Polalalabear/amidst/pull/604) | `claude/feat-recorded-openai-agent` @ `9d23883d` | **紅**（快照時） | Draft；#601 預錄 OpenAI Agent，`agent-openai-601` 還在做 |

**還在的分支**（`gh api .../branches`）：`main`、`mainline/q1q5`、上表五條、`archive/*` 5 條（`archive/amidst-claude-wip-20261109`、`archive/canonical-uncommitted-20261109`、`archive/finalization-uncommitted-20261109`、`archive/local/codex/controlled-scene-real-v2-2a`、`archive/local/phase1/physical-policy-approval`，被 main 引用或沒有其他副本，保留）。

**刪掉的分支**：D278 清理 10 條（`claude/epic-d-agentic`、`argon/424`、`425`、`426`、`429`、`codex/467`、4 條 `archive/local/phase1/*`）；合併後刪 `claude/experiment-record-latex`、`claude/feat-live-ab`（D280）、`claude/feat-retire-old-workbench`（D282）、`claude/feat-research-report`、`claude/feat-live-relock`、`claude/feat-ops-docs`（D305；本 PR 重新開同名分支）、`codex/feat-live-detection`、`claude/feat-retire-office-display`（D308）。

#### 2. 先讀

1. `CLAUDE.md`、`AGENTS.md`、`CLAUDE.local.md`（本機規則：協調者只派工，不在 `~/amidst` 改檔）
2. 本文件
3. [#93](https://github.com/Polalalabear/amidst/issues/93) 本文（工作清單）和 D278–D310 的留言（D283 是無編號留言的索引）
4. LIVE A/B：`docs/specs/LIVE_MODE_AB_V1.md`（v2.1）、重新取得契約（#587 合併的檔，見 [#585](https://github.com/Polalalabear/amidst/issues/585)）、Codex 總項 [#566](https://github.com/Polalalabear/amidst/issues/566)
5. 評估方向 D304 與 [#597](https://github.com/Polalalabear/amidst/issues/597) 的錄製指引 v1（[留言 6967247222](https://github.com/Polalalabear/amidst/issues/597#issuecomment-6967247222)）
6. 即時模式背景：`docs/operations/LIVE_MODE_HANDOFF_20261116.md`、`docs/design/LIVE_MODE_LLM_DECISION_V1.md` §0F
7. 前一份交接 `docs/agents/COORDINATOR_HANDOFF_20261117.md` §3（8785 更新流程、前景執行）

#### 3. 流程（今天新增的）

沿用前一份 §3 與 `CLAUDE.md`、`AGENTS.md`。今天的補充：

- **工作清單只在 #93 本文**（D281）：派工、取工、更新都在 issue 上做，每件可派的工作都有自己的 issue；brief 指向 issue 編號。狀態要標全：ready／in-progress／review／waiting（寫明等誰、等什麼）／blocked／deferred／done／abandoned（寫原因）／superseded（寫被誰取代）。**做完當下就更新**那一列，並在 issue 留言；完成或廢棄的移到「最近結束」。
- **合併不問使用者**（D305）：審查通過、CI 綠、可合併的 PR 由協調者直接合併（merge commit）並刪掉已合併分支。例外仍要問：使用者要先看截圖的 UI（#564）、8785 pin、付費、刪除原始資產。
- **OpenAI 額度**（D306）：可用約 USD 50，用於專案測試（#597、#601 smoke 等）。每次先 ApiGuard dry-run，在 issue 貼預估與實際花費；**單次預估超過 USD 10 先問使用者**。
- **研究文件分兩份**（D308）：研究紀錄（`docs/research/experiment_record/`，LaTeX）記使用者在專案中提出要記錄和分析的東西，隨進度追加；研究計畫（較嚴謹）最後才動，main 上目前沒有對應檔案（`UNKNOWN`），要做時另開 issue。
- **目前以專案實際運行為主**（D308）：優先 #576、#566、#588、#601、#602（D309 起只做 LIVE 外圍）；研究計畫和跨平台（#598，D304）延後。
- **評估方向**（D304）：LIVE 玩一次錄下玩家軌跡，同一劇本重播（只用規則／LLM 覆核），用 GT 逐 tick 評分（GT 只用於評分）。預錄三事件不再拿來證明 LLM。
- **`gh api -X DELETE` 前加 `PAGER=cat`**，不然 gh 會開分頁器卡住。
- **被 session 事件喚醒的回合不能開 session**，改用提案卡。

#### 4. 所有工作，依類型分類

每項分成三組：**現在能做的**、**收尾中的**（等審查、等使用者看圖、等合併）、**還沒做的（含延後）**。

##### 4.1 8785 demo

| 組 | 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|---|
| 現在能做 | 8785／8791 更新到 main [#576](https://github.com/Polalalabear/amidst/issues/576)（claude） | 兩介面含 #559、#563、#564、#594 | ready（#559 已合併，D308）。8785、8791 都還在 `e9db4fdf` | 建議等 #564 合併（和 #603 視審查結果）再一起跑 gate；**pin 要使用者核准**；8785 前景重啟 |
| 收尾中 | 預錄模式可切 OpenAI Agent [#601](https://github.com/Polalalabear/amidst/issues/601)／[#604](https://github.com/Polalalabear/amidst/pull/604)（claude） | 四個 run 可選 Agent，預設關、經 ApiGuard | in-progress；Draft #604，**CI 紅**（快照時） | `agent-openai-601` 還在做；交件後派審查；真 provider smoke 先 dry-run，>USD 10 才問 |
| 收尾中 | 8CAM run [#594](https://github.com/Polalalabear/amidst/issues/594)／[#603](https://github.com/Polalalabear/amidst/pull/603)（codex） | 8785 多一個 8 鏡頭 run | review；Draft，CI 綠，獨立埠 8CAM／dependency smoke 通過 | `rv-599-603` 正式審查中（D309）；完整 gate 隨 #576 |
| 還沒做 | 預錄俯視圖改成 LIVE 式 3D 場景視圖 [#605](https://github.com/Polalalabear/amidst/issues/605)（claude） | 只畫系統估計、不畫 GT；先出示意圖 | ready（D310） | 等寫檔名額（快照時三個寫手：#601、交接文件、#602） |

##### 4.2 即時模式（LIVE）

| 組 | 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|---|
| 收尾中 | 場景外圍實作 [#602](https://github.com/Polalalabear/amidst/issues/602)（claude） | **只做 LIVE**（操作端與系統端鏡頭畫面）的外圍背景，可走範圍不變；預錄畫面是原始渲染影片，不重新渲染（D309）；前後截圖 | in-progress；示意通過（D307，LOCAL `local/evidence/live-exterior-mock-20261118/`（SHA256SUMS.txt `32b42386683a3372a6048ca4cb65f4edfe584e955293370c955e533fdb3b8727`）） | session `exterior-602` 執行中；和 #593（`codex/feat-n6-ceiling`）協調檔案 |
| 現在能做 | #563 的 P3＋#559 審查 P2-1 [#577](https://github.com/Polalalabear/amidst/issues/577)（claude） | `advisor_model` 非字串、IPv6、缺 `t_capture_ms` 時略過記憶 | ready | 無 |
| 現在能做 | 後台 `/track/*` 端點 [#571](https://github.com/Polalalabear/amidst/issues/571)（codex） | session、Q3 句子接線 | ready（#559 已合併） | 等 Codex 取工 |
| 現在能做 | 重新取得 R1 [#588](https://github.com/Polalalabear/amidst/issues/588)（codex） | tracker 分段門檻、速度預測、門檻量測，重播驗收 | ready | 等 Codex 取工 |
| 收尾中 | 人物不碰撞 [#568](https://github.com/Polalalabear/amidst/issues/568)（codex） | crowd＋sim，C-1～C-8 | review；C-5 通過（D309：無玩家基線 0、`player_phase_shift` 11 次另計、78.7 s 反例保留），在 Draft #584 | `rv-584` 正式審查中 |
| 收尾中 | A 場景＋角色選單＋滑鼠 [#569](https://github.com/Polalalabear/amidst/issues/569)、離線評分 [#570](https://github.com/Polalalabear/amidst/issues/570)、`smoke.mjs` 不寫 `/private/tmp` [#573](https://github.com/Polalalabear/amidst/issues/573)（codex） | — | review；都在 Draft #584 | #584 預審 P2 兩點（評分器在 ACQUIRING／NEEDS_PICK 誤判失聯；tick 層 `gt_visible` 被覆寫，[留言 6967155738](https://github.com/Polalalabear/amidst/pull/584#issuecomment-6967155738)）等 Codex 修 |
| 收尾中 | N6 天花板亮度與接縫 [#593](https://github.com/Polalalabear/amidst/issues/593)／[#599](https://github.com/Polalalabear/amidst/pull/599)（codex） | 材質調整＋截圖 | review；Draft，CI 綠，A4-1 同秒前後截圖已交 | `rv-599-603` 正式審查中（D309） |
| 收尾中 | workbench-v2 五點易用性 [#564](https://github.com/Polalalabear/amidst/pull/564)（claude） | 搜尋 Enter、追蹤分頁搜尋、概況排版、易讀名稱、live 入口 | waiting；審查 APPROVE；D302 改名（室外西側／轉角／轉角廣角）已推 `a2c80351` | **等使用者看截圖**（`local/evidence/wb2-ux-564-20261118/`（SHA256SUMS.txt `4eb1e6dcd8617f14d5a072c884bc8d18902f8944bdf5a7d79f565d3f64b8de2e`）） |
| 還沒做 | #564 的 3 個 P3 [#578](https://github.com/Polalalabear/amidst/issues/578)（claude） | — | blocked | 等 #564 合併 |
| 還沒做 | B 選目標流程 [#572](https://github.com/Polalalabear/amidst/issues/572)、整合驗收 [#574](https://github.com/Polalalabear/amidst/issues/574)（codex） | — | blocked | #572 等 #571；#574 等全部子項 |
| 還沒做 | 重新取得 R2 [#589](https://github.com/Polalalabear/amidst/issues/589)（codex） | 後台接線＋ENTRY 驗收；交件補 `accepted_by: D282` | blocked | 等 #588 |
| 還沒做 | LIVE 錄製與重播 [#596](https://github.com/Polalalabear/amidst/issues/596)（codex） | 玩家軌跡存成可重播劇本＋決定性測試 | blocked | 等 #568、#569、#574 |
| 總項 | LIVE A/B [#566](https://github.com/Polalalabear/amidst/issues/566)（codex） | 雙畫面展示即時追蹤 | in-progress | 看子項 |

##### 4.3 預錄模式與 Agent

| 組 | 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|---|
| 收尾中 | #601 預錄 OpenAI Agent | 見 4.1 | 見 4.1 | 見 4.1 |
| 總項 | Agentic epic [#489](https://github.com/Polalalabear/amidst/issues/489)（claude） | 自然語言、數位孿生點選、Agent 實際決策、OpenAI | in-progress；子項勾到 #582 為止 | — |
| 已取代 | WP5 合成題重跑 #592、sol6.1 單獨驗證 #591 | — | superseded（D304，併入 #597；額度不沿用） | — |

##### 4.4 評估（難題集）

| 組 | 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|---|
| 還沒做 | LIVE 難題集：規則 vs LLM 重播比較 [#597](https://github.com/Polalalabear/amidst/issues/597)（claude） | 逐案結果、報告素材、demo 並排重播；含「目標不在名單」 | blocked；錄製指引與評分定義 v1 已備（[留言 6967247222](https://github.com/Polalalabear/amidst/issues/597#issuecomment-6967247222)），付費粗估 sol 約 USD 1.6、terra 約 USD 0.8（未 dry-run） | 等 LIVE A/B（#566）、#588、#596 完成；使用者錄難題集；付費先 dry-run |

##### 4.5 研究紀錄與報告

| 組 | 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|---|
| 現在能做 | 報告素材 epic [#479](https://github.com/Polalalabear/amidst/issues/479)（argon／claude） | 持續追加「報告素材」留言 | in-progress；第 5 章 WP5 數字已合併（#586） | 無 |
| 還沒做 | 研究紀錄追加 | 使用者提出要記錄的項目進 `docs/research/experiment_record/` | v4.2 已合併（#558）；之後隨使用者提出追加 | 等使用者提出 |
| 延後 | 研究計畫（嚴謹版） | — | 最後才動（D308）；檔案 `UNKNOWN` | 要做時另開 issue |

##### 4.6 流程與整理

| 組 | 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|---|
| 收尾中 | 本交接（handoff-1118） | 本文件、CLAUDE.md／AGENTS.md 連結 | 本 PR | 等 CI、協調者合併 |
| 已完成 | 舊工作台下線 R1、Office 補列檔、R2 封存、R3 ledger、#93 工作清單、D 號補編 | — | #575、#595、#590、D281、D283 | — |
| 延後 | 跨平台 [#598](https://github.com/Polalalabear/amidst/issues/598)（claude） | Windows／Linux 跑 demo | deferred（D304） | 使用者決定延後 |

##### 4.7 Codex 與 Argon

| 組 | 工作 | 目前進度 | 卡住的部分 |
|---|---|---|---|
| 現在能做（Codex） | #571、#588（ready）；#584 預審 P2 兩點與正式審查的修正 | — | 等 Codex 取工 |
| 收尾中（Codex） | #584（#568–#570、#573）、#599（#593）、#603（#594） | Draft | 正式審查中：`rv-584`、`rv-599-603`（D309） |
| 還沒做（Codex） | #572、#574、#589、#596 | blocked | 見 4.2 |
| Argon | 沒有派工；`owner:argon` 只有 epic #479 | — | 需要時再派 |

#### 5. 等使用者決定

> **已過時，見[晚間交接（D311–D330）](#9-晚間交接d311d330)。**以下保留原文。

1. **#564 五點截圖**（`local/evidence/wb2-ux-564-20261118/`（SHA256SUMS.txt `4eb1e6dcd8617f14d5a072c884bc8d18902f8944bdf5a7d79f565d3f64b8de2e`））：OK 就合併。
2. **#576 的 8785 pin**：gate 通過後由使用者在終端核准（`scripts/demo_pin.py approve`）並前景重啟 8785。
3. **#601 真 provider smoke 金額**：先 dry-run；預估 ≤ USD 10 可直接跑（D306），超過才問。
4. **#597 難題集**：使用者要親自錄 LIVE 難題集（LIVE A/B 和 #596 完成後）；付費同上。

快照時 #93 沒有其他 `needs-auth` 項目（#583 已在 D282、D302 全部決定）。

#### 6. 給新協調者的第一件事（依優先順序）

> **已過時，見[晚間交接（D311–D330）](#9-晚間交接d311d330)。**以下保留原文。

開始前先用 `gh issue view 93 --repo Polalalabear/amidst --comments` 看 D310 之後有沒有新留言，`gh pr list --repo Polalalabear/amidst` 看 PR 有沒有新進度。

1. **#564**：問使用者看截圖（`local/evidence/wb2-ux-564-20261118/`（SHA256SUMS.txt `4eb1e6dcd8617f14d5a072c884bc8d18902f8944bdf5a7d79f565d3f64b8de2e`）），OK 就合併並刪分支，解除 #578。
2. **#576**：把 8785／8791 更新到 main。照 D269／D270 的 gate 流程（clone 跑 node、focused pytest、`check_demo_dependencies.py --smoke`、real-e2e → `RESULT.txt`），8785 用前景方式重啟（終端分頁「8785 demo」），**pin 要使用者核准**。
3. **#577**：派寫手（#563 的 P3＋#559 審查 P2-1）。
4. **#602**：追 `exterior-602`（只做 LIVE 外圍，D309）的進度，交件後派審查；寫手名額空出後派 #605 示意圖（D310）。
5. **#601**：追 `agent-openai-601` 的進度（#604 快照時 CI 紅），交件後派審查。
6. **Codex**：收 `rv-584`、`rv-599-603` 的審查結果（#568–#570、#573、#593、#594），通過就合併（D305）；#571、#588 和 #584 預審的 P2 兩點交 Codex；給 Codex 的指派寫成可直接貼上的文字。
7. **#597** 在 LIVE A/B（#566）和 #596 完成後才開始。

#### 7. Session 清單（快照時）

`list_sessions {"linked": true}` 列得到時以它為準。快照時與前一位協調者（`local_98bbf379-97a0-48c7-9325-c3ae1ceaac25`）連結的 session：

| 名稱 | session id | 狀態 | 內容 |
|---|---|---|---|
| `exterior-602` | `local_ae2d568d-49a9-4cd0-8085-71af26586bf2` | **執行中** | #602 LIVE 場景外圍實作（D309） |
| `rv-584` | `local_5e481ed7-f22f-4762-a0f5-622decdfee18` | **執行中** | #584 LIVE A/B 正式審查 |
| `rv-599-603` | `local_f44c4a73-f4e0-4b26-b09b-5f697b031154` | **執行中** | #599 天花板＋#603 8CAM 正式審查 |
| `agent-openai-601` | `local_2e85950a-dd9b-4df3-8f98-596cff16e6dd` | 閒置（快照時，#604 CI 紅） | #601／#604 預錄 OpenAI Agent |
| `guide-597` | `local_89972c0e-905f-4fab-bc5b-630066ca20ad` | 閒置（完成） | #597 錄製指引與評分定義 v1 |
| `wb2-rename-564` | `local_6fd2a7b7-bed7-4886-9af1-c3692a8a9ae0` | 閒置（完成） | #564 鏡頭改名＋五點截圖 |
| `rv-584-pre` | `local_26295735-4c30-4034-8241-103f47572cf6` | 閒置（完成） | #584 預審（P2 兩點） |
| `rv-559` | `local_663121b7-c5af-40e6-b97e-6359474d0920` | 完成 | #559 正式審查 |
| `office-579-impl` | `local_b756478f-f4df-440a-99fb-2431ccfde1ac` | 完成 | #579／#595 實作 |
| `rv-595` | `local_b104fcbb-1e28-4832-9eb5-a26966092f70` | 完成 | #595 審查 |
| `live-exterior-mock` | `local_012c8dce-5a6d-45f3-a9b2-7cec414e82c1` | 閒置（完成） | #600 場景外圍示意圖 |
| `live-relock-spec` | `local_00a07361-4e84-4384-8ff7-72b3eb029346` | 完成 | #585／#587 |
| `ops-docs-580` | `local_6b6eeddd-8689-4dd0-bb5a-24af35ef6aea` | 完成 | #580／#590 |
| `report-581` | `local_824712e6-8f97-4a9f-b704-56b0858fe621` | 完成 | #581／#586 |
| `inv-582` | `local_8c94e830-ce34-4f41-add7-b50eca31575f` | 閒置（完成） | #582 盤點＋D283 |
| `opus-579` | `local_a25afa7d-960c-4694-8e7e-c92b967d65c2` | 閒置（完成） | #579 Office 8 檔判定 |
| `board-1118` | `local_ea82c502-6f7c-4f0b-8dee-62200bc36099` | 閒置（完成） | #93 改寫成工作清單（D281） |
| `live-ab-spec-v2` | `local_92110ef1-0828-4cb4-94a3-d85b23f7ec76` | 完成 | #567 規格 v2＋Codex 子 issue |
| `retire-old-wb-impl` | `local_d4b1aa96-d6f6-4493-94ff-9540f41d3145` | 完成 | #575 實作 |
| `rv-575` | `local_1d9b5267-0826-4346-b82c-082960c21e00` | 完成 | #575 審查 |
| `rv-564` | `local_4db853ad-4eb1-4074-b06a-a703b4551522` | 完成 | #564 正式審查 |
| `rv-558-v42` | `local_2463ae51-072a-48d0-82f8-2eff90336f86` | 完成 | #558 差異複審 |
| `handoff-1118` | `UNKNOWN`（本 session） | — | 本文件 |

已完成的 session 可在使用者同意後封存。

#### 8. D311–D318 補記（2026-11-18，事實補記；前文不改）

> **已過時，見[晚間交接（D311–D330）](#9-晚間交接d311d330)。**以下保留原文。

快照：`main` 頭為 `b98fac2a`（#613 merge）。進度導覽已依 GitHub 逐項批次補列到 #613（見 [Q1Q5_PROGRESS.md](../operations/Q1Q5_PROGRESS.md)）。

| 決策 | 內容 | 結果 |
| --- | --- | --- |
| D311 | 收尾交接：#606、#599 合併；#584、#603 NEEDS_CHANGES；#564、#607、#604 等使用者 | #606 `b7ca80f2`、#599 `3c3e1267` 已合併 |
| D312 | 使用者同意合併 #564、#607 | #564 `eb06e9a0`、#607 `7f8e8443` 已合併（#602 關閉） |
| D313 | #604 逾時預設由使用者決定為每輪 8000 ms、總共 24000 ms | 已由 D317 指出 P1（LOCAL 參數檔仍 2000／5000），修後合併 |
| D314 | 新協調者派工：#604 修正、#577＋#578 P3、#584／#603 複審、#588 判定、#571 改走法 | #577＋#578 合併（D317）；#584、#603 合併（D315）；#604 合併（D318） |
| D315 | #584 `81ba829d`、#603 `3b5a987a` 合併；#571 改由 Codex 從最新 main 重開 `codex/feat-live-ab` 另開 Draft | #584、#603 已合併；Draft #610 為新開（待審） |
| D316 | Opus 判定 #588 有條件允許（gate 內唯一群可走 short_gate）；#605 照示意圖做 | #611 `4bf9b5ed` 已合併；#613 實作完成 |
| D317 | #609 `fb4b99b9`（#577、#578 P3）、#611 合併；#604 Opus NEEDS_CHANGES（P1） | #609、#611 已合併；#577、#578 關閉 |
| D318 | #604 `62da6464`、#613 `b98fac2a` 合併（#601、#605 關閉）；8785／8791 由 #576 更新到 `b98fac2a`，gate 後使用者核准 pin | #604、#613 已合併 |

目前等待（事實）：

- **使用者**：#576 的 8785／8791 pin 核准（gate 通過後）。
- **Codex**：#608（#588 relock R1，D316 驗收 B4 ≥58/60、錯接 0）、#610（D315 的 #571 端點 Draft）、#589、#596、#612（est_xy，#605 3D 視圖的估計位置）、#594（8CAM run，#603 已加入 A4-1-8CAM，是否關閉待確認）。
- **Claude**：#597（LIVE 難題集）、#576（8785／8791 更新，gate 後）。
- **未排程**：#598（跨平台，延後）、#566 母 issue（子項 #571、#572、#574 未完成）。

本補記不改 #93 的決策紀錄；D 編號下一個為 D319。

#### 9. 晚間交接（D311–D330）

2026-11-18 晚間快照，取代 §5、§6 與 §8 的狀態。數字和 SHA 已在撰寫時用 `gh`、`git` 核對。**新的協調者對話全程用繁體中文回覆**（D255）。協調者的 D331（難題集全由腳本產生、#608／#617 NEEDS_CHANGES、磁碟盤點結果）已貼 #93；本交接記為 **D332**，新協調者從 **D333** 起。

##### 9.1 現況

| 項目 | 值 |
| --- | --- |
| `main` | `7393bf62`（#615 merge） |
| 8785 pin | `b98fac2a`（`local/demo-pin.json`，gate `local/evidence/gate-576-20261118/RESULT.txt`（SHA-256 `60201b729e7c50eccfec1709e52803038a2425adf6c7f0fe14df15c165b8f927`），D324）；`~/amidst` 工作樹在 `b98fac2a`，終端分頁「8785 demo」前景執行 |
| 8791 | `50f2fd14`（#618 merge），`local/runtime/live-main`，用 `local/runtime/start_live_8791.sh` 啟動（D329） |
| 下一個決策編號 | D331（協調者）、D332（本交接）→ 新協調者用 **D333** |
| 磁碟 | 可用約 7–8 GiB（低於 9 GiB 不開第三個寫手，低於 5 GiB 停工）；盤點已完成：LOCAL `local/evidence/disk-inventory-20261118/INVENTORY.md`（SHA-256 `5afa743861e0c6d1f25fdee2e0f8840801e16bab5a65ff4c92ba20dafe6b7daa`，Haiku low，唯讀，未刪任何東西）。A 類約 1.77 GiB（npm／uv／torch／pip 快取＋2 個殘留 clone）等使用者授權（D331-3），殘留 clone 要等所有 session 結束才刪；B 類走 Sonnet 驗證 → Opus 決定 → 使用者授權 |
| OpenAI 額度 | D306 約 USD 50；今天花 USD 0.41（D325 預錄三事件分析）＋診斷約 USD 0.006 |

##### 9.2 所有工作，依類型分類

###### 即時模式（LIVE）

| 項目 | 預計產出 | 目前進度 | 卡在哪裡／在等誰 |
| --- | --- | --- | --- |
| #588／#608 重新取得 R1 | relock R1 合併，R-6、R-5a 過，runtime 預設不變 | D326：R-5 拆成 R-5a（相對 main 不新增錯接，R1 閘門）與 R-5b（LLM 救回同衣色錯接，移到 #597）。Codex 回報驗證完成（head `533b4e99`）。**NEEDS_CHANGES，原因是和 main 衝突，等 Codex 合 main**（D331-2；Sonnet [#608 留言](https://github.com/Polalalabear/amidst/pull/608#issuecomment-6980353441)）：數字核對全過，但 P1-1 `src/amidst/live_mode/tracker.py` 與 main 有語意衝突（main 已加 `target_color`、`project_detections()`、`seed()`、`_result(seen)`），合併 main 後要重跑 `replay_relock.py`、`replay_advisor.py`、逐位元組比對與 `pytest tests/live_mode`；P2 兩點、P3 四點；另有三個給 Opus 的問題 | **Codex**（用 merge commit 合 main 後重驗重送）→ Claude 複審；審查留給 Opus 的三題要協調者分派（R-5a 的 main 基準是否改同程式重播、NEEDS_CONFIRM 與 #610／#611 的銜接、接受 5 筆已知錯接是否已有 D 編號——D326 已記錄使用者同意 R-5 改寫） |
| R-5a／R-5b 契約條文 | `docs/specs/LIVE_MODE_RELOCK_V1.md` 補 R-5a、R-5b | 未開始 | 派 Claude 文件寫手（可和 #610 Opus 三點的 v2.2 規格補丁同一個 PR，D323） |
| #589 重新取得 R2 | 後台接線＋ENTRY 排程驗收 | blocked | 等 #608 合併 |
| #566 A/B 雙畫面（母） | 選角色、B 選目標、不碰撞 | #610 已合併（`118c2035`，D323）；#571、#572 由 #610 完成，本交接已關閉 | 等 #617、#574 |
| #617 pass 規則＋#596 錄製重播 | D327 pass 規則（只結束從未進入 2r 的 pass）＋確定性錄製重播 | Draft，head `50164136`，CI 綠；Codex 自報 C-2／C-6 回綠。**NEEDS_CHANGES，原因是和 main 衝突，等 Codex 合 main**（D331-2；Sonnet [#617 留言](https://github.com/Polalalabear/amidst/pull/617#issuecomment-6980418787)：程式核對通過，交接文件也過期） | **Codex**（合 main 重送）→ Claude 複審，通過就合併（D305） |
| #574 整合驗收 | A/B 整合、瀏覽器驗收、handoff 文件 | blocked | 等 #617 |
| #619 室外遠端目標偵測失敗（CX-L8） | 室外遠處目標能偵測與追蹤（難題集前置條件，D330-c） | 新開，`ready` | **Codex** |
| LIVE A 選單工作台風格 | — | #618 已合併（`50f2fd14`，D329），8791 已更新 | 無；8785 的轉址修正等下一次 pin |

###### 難題集與 LLM 價值證明

| 項目 | 預計產出 | 目前進度 | 卡在哪裡／在等誰 |
| --- | --- | --- | --- |
| #597 LIVE 難題集（CL-B11） | 規則 vs LLM 重播比較，證明 LLM 價值 | 事件表、答案表、腳本操作者已合併（#615，`7393bf62`，D330）。D330 三個決定：(a) H1、H4 以不計 CAM_ENTRY 的讀法為正式判定，**要驗證 ENTRY 畫面沒有進入追蹤或 LLM 覆核輸入**，有就改回嚴格讀法；(b) 開場就通過的 3 段改路線，其餘標註前置條件；(c) 室外遠端 → #619。**D331-1：難題集全部改由 Claude 的腳本操作者產生**（使用者不親自玩），H2（相似人物交錯）、H3（不照路線）也寫成 `?script=` 路線；報告要聲明所有段落都是照規則弱點設計的腳本、沒有真人的不可預測性 | `hardset-597-plan` 正在 `claude/feat-live-hardset` 做 D330 (a)(b)＋D331-1 → 交件後派審查、合併；#596（在 #617）合併後接錄製；然後跑規則 vs LLM（付費先 ApiGuard dry-run，單次 > USD 10 要問） |
| 預錄三事件分析（D325、D328） | 規則 vs LLM 在 A4-1、B4-1、B-05 的差異 | 完成：LLM 與規則相同（A4-1 0.970、B4-1 0.906；sol 在 B4-1 一次 0.901），題目太簡單；B-05 沒有 decider 注入點。報告 LOCAL `local/evidence/eval-recorded-llm-20261118/REPORT.md`（SHA-256 `2f6bd7c61c16aa158515e612c03b06c2eb98c38c6c16a6ef91c520c9e6013b31`） | 後續：`INVALID_RESPONSE`（`reason_codes` 超過 4 個）的提示修正，未開 issue |
| #620 CL-B16 Q2 Agent 開關 | 8785 的 Agent 開關（#604）在 A4-1、B4-1 可用；B-05 顯示「不適用」 | 本交接開的 issue（引用 D328）：三個事件回 `TRACKING_SCOPE_MISSING` | 派 Claude 寫手（`claude/feat-recorded-openai-agent`） |

###### 8785 預錄 demo

| 項目 | 預計產出 | 目前進度 | 卡在哪裡／在等誰 |
| --- | --- | --- | --- |
| 已合併 | — | #604（OpenAI Agent，D313 逾時 8000／24000 ms，`62da6464`）、#613（3D 場景視圖，2D 為預設，`b98fac2a`）、#603（A4-1-8CAM，`3b5a987a`）、#609（`fb4b99b9`）、#616（`d3dd2d65`） | — |
| #612 est_xy（CX-8E） | 預錄模式提供系統估計位置給 3D 視圖 | Codex 進行中，還沒開 PR | **Codex** |
| #594 其餘 8CAM run（CX-8C） | workbench-v2 加其餘 8CAM run | Codex 進行中 | **Codex** |
| 下一次 8785 更新 | pin 更新到含 #618 轉址修正、#617、#612 的 main | 未開始 | 等 #617、#612 合併；照 D269／D270 gate 流程：gate 的 `RESULT.txt` **每行必須以 PASS 結尾**（D324 教訓），**使用者**在終端執行 `scripts/demo_pin.py approve`，8785 前景重啟 |

###### 流程與整理

| 項目 | 預計產出 | 目前進度 | 卡在哪裡／在等誰 |
| --- | --- | --- | --- |
| 合併規則 | — | D305：審查過＋CI 綠就直接合併並刪分支；UI 要使用者先看截圖；pin、付費、刪原始資產要問 | — |
| gate 檔格式 | — | D323：協調者替 gate 檔改格式被安全機制擋下；gate 檔只能由產出的 session 重寫 | — |
| 磁碟清理 | 釋出空間到 ≥ 9 GiB | Haiku 盤點完成（見 9.1） | A 類約 1.77 GiB 等**使用者**授權（殘留 clone 等 session 結束）；B 類 Sonnet 驗證 → Opus 讀原始證據決定 → **使用者**授權並在自己的終端刪除 |
| 冗餘程式盤點 | 沒被引用的模組／腳本清單 | 延後（D319） | 等 #608、#571（已由 #610 完成）、#612 合併 |
| #598 跨平台 | — | 延後 | — |
| 進度導覽 | — | 本交接 PR 批次補列到 #620 | 下一批補列本 PR 自己的列 |

###### Codex 與 Argon

- **Codex** 正在做：#608（合併 main 重驗）、#617（含 #596）、#612、#594、#619。
- **給 Codex 的待貼文字**（還沒貼，交使用者轉給 Codex）：

  > 使用者桌面在 live 測試時一直彈出 Chrome 視窗。請把 live 測試（node／瀏覽器驗收腳本）預設改成 headless，只有明確加旗標時才開有視窗的瀏覽器。改在你下一個 LIVE PR（#617 或 #608）裡，並在實際產出紀錄寫明。

- **Argon**：#479 研究紀錄（沒有變動，沒有派工）。

##### 9.3 新協調者的第一件事（依優先順序）

開始前先 `gh api "repos/Polalalabear/amidst/issues/93/comments?per_page=30&page=15"`（`gh issue view 93 --comments` 在 444 則留言時會逾時）看 D332 之後有沒有新留言，`gh pr list --repo Polalalabear/amidst` 看 PR 進度。

1. **#608、#617**：兩者都是 NEEDS_CHANGES（和 main 衝突）。Codex 合 main 之後派 Sonnet 複審，通過就合併（D305）；#608 審查留給 Opus 的三題要派。
2. **難題集 PR**：`hardset-597-plan`（`claude/feat-live-hardset`，D330 (a)(b)＋D331-1 全腳本）交件後派審查、合併。
3. **磁碟**：A 類約 1.77 GiB 問使用者授權；B 類交 Sonnet 驗證、Opus 決定，使用者授權後由使用者刪除。
4. **#620 CL-B16**：派 Sonnet medium 寫手。
5. **下一次 8785 更新**：#617、#612 合併後照 gate 流程。

##### 9.4 Session（快照時，與前一位協調者連結）

以 `list_sessions {"linked": true}` 為準。快照時仍在執行：`disk-inventory`（`local_0808ab32-1f79-4c8b-88e7-db04514ffcc5`，盤點已產出）、`rv-608-617`（`local_fe212872-521f-436b-8939-8220b24e2c41`，#608、#617 結論都已貼）、`hardset-597-plan`（難題集路線修正＋全腳本）。閒置：`opus-588-gate`、`mock-605-3d`、`board-d315`、`576-8785-8791-main-gate`、`eval-recorded-llm`。其餘已完成，使用者同意後可封存。

##### 9.5 最終狀態補記（D333，2026-11-18 深夜）

本節是交接前最後一次核對（`gh pr view`、`gh pr checks`、`gh issue view`、`df`、`lsof`），只增補，§9.1–§9.4 與前文決策紀錄不改；狀態有出入時以本節為準。本補記在 #93 記為 **D333**，新協調者從 **D334** 起。

**研究紀錄**：預錄三事件規則 vs LLM（D325）已寫成 [`docs/evaluation/RECORDED_RULE_VS_LLM_D325_20261118.md`](../evaluation/RECORDED_RULE_VS_LLM_D325_20261118.md)：A4-1、B4-1 上 LLM 與規則相同（0.970／0.906，sol6.1 一次 0.901），A4-1 9.2 s、37.2 s 的 `INVALID_RESPONSE` 是 `reason_codes` 超過 4 個（37.4 s 請求已確認，9.4 s 未重現），B-05 不適用（#620、無 GT），花費 USD 0.4115。結論：這兩個基線事件沒有讓 LLM 贏的題目，要靠 #597 難題集。

**PR 與 issue（核對時）**

| 項目 | 狀態 | 下一步 |
| --- | --- | --- |
| [#622](https://github.com/Polalalabear/amidst/pull/622) 難題集 | `claude/feat-live-hardset` @ `de1be7e9`，Draft，可合併，CI `checks` 綠。內容：難題集全部由腳本產生（D331）、正式判定用 graph 讀法、H1-3／H4-2／H5-3 改路線（D330）；新一輪 9 段在 graph 讀法下全部成立，9 段中 5 段在難點前 3 s 規則跟對（H2-2、H2-3、H3-1、H3-2、H5-3）；smoke 改成只用無頭 Chrome（使用者不要彈視窗）。只跑了規則模式 | **待 Sonnet 正式審查後合併**（D305） |
| [#608](https://github.com/Polalalabear/amidst/pull/608) relock R1（#588） | `codex/feat-live-relock` @ `fe4f2541`，非 Draft，可合併，CI 綠。Codex 已用 merge commit 合入 main `7393bf62`，回報 D326 數字不變、runtime relock／predict 預設關閉 | 待 Claude 複審（§9.2 列的 Opus 三題仍要派） |
| [#617](https://github.com/Polalalabear/amidst/pull/617) pass 規則＋錄製重播（#596） | `codex/feat-live-ab` @ `c0498745`，Draft，可合併，CI 綠。已合 main；瀏覽器工具統一預設無頭（`--headful` 或 `AMIDST_HEADFUL=1` 才顯示），§9.2 的「給 Codex 的待貼文字」已由此處理 | 待 Claude 複審 |
| [#623](https://github.com/Polalalabear/amidst/pull/623) 3D 視圖 est_xy（#612） | `codex/feat-workbench-8cam` @ `e49a31af`，Draft，可合併，CI 綠。Codex 回報 A4 240 INFERRED／10 UNKNOWN、B4 209／1；完整服務啟動因磁碟門檻未驗證 | 待 Claude 審；#594 由同一條線後續處理 |
| #588 | open，`ready`、`in-progress`（經 #608） | 隨 #608 |
| #594 | open，`in-progress`（Codex，CX-8C） | 隨 #623 同線 |
| #612 | open，`in-progress`（經 #623） | 隨 #623 |
| #619 | open，`ready`（Codex，CX-L8 室外遠端偵測） | Codex 取件 |
| #571 | 已關閉（由 #610 完成） | — |
| #620 | open，`owner:claude`、`ready` | 派 Sonnet medium 寫手 |

**本機狀態**

- 磁碟：可用約 8.7–8.8 GiB（仍低於 9 GiB，不開第三個寫手）。
- 殘留 clone 與孤兒 8797／8798 伺服器已清；核對時只有 8785、8791 在監聽。
- 8785 pin `b98fac2a`（`local/demo-pin.json`）；8791 在 `50f2fd14`（`local/runtime/live-main`）。
- #618 的 308 轉址修正要到下一次 8785 pin 更新才生效。

**新協調者第一件事（取代 §9.3 的 1、2 項）**

1. 派 Sonnet 正式審查 #622、#608、#617、#623；審查過＋CI 綠即合併並刪分支（D305）。#608 審查留給 Opus 的三題照 §9.2 分派。
2. 把 LIVE 規則 vs LLM 重播比較（#597 CL-B11 本體）排上：等 #622、#617（#596 錄製重播）、#608 合併後跑，付費先 ApiGuard dry-run，單次超過 USD 10 要問。
3. §9.3 的 3–5 項（磁碟、#620、下一次 8785 更新）不變。
4. 下一個決策編號 **D334**。

#### 10. 2026-11-19 交接（最終狀態，D335）

給新協調者的最終狀態，取代 §9.3 與 §9.5 的狀態與「第一件事」；前文決策紀錄不改。PR、SHA、CI 都在撰寫時用 `gh`、`git` 核對。**新的協調者對話全程用繁體中文回覆**（D255）。本交接在 #93 記為 **D335**，新協調者從 **D336** 起。

##### 10.1 SHA 與今天合併

| 項目 | 值 |
| --- | --- |
| `main` | `8e892804`（#621 merge） |
| 8785 pin | `b98fac2a`（`local/demo-pin.json`，gate-576） |
| 8791 | `50f2fd14`（`local/runtime/live-main`） |
| 今天合併 | #622 → `ba535fef`（難題集全由腳本產生，smoke 預設無頭）；#621 → `8e892804`（研究紀錄 [`docs/evaluation/RECORDED_RULE_VS_LLM_D325_20261118.md`](../evaluation/RECORDED_RULE_VS_LLM_D325_20261118.md)、D334 四條規範） |

**D334 規範**（詳見 [AGENTS.md](../../AGENTS.md)）：瀏覽器測試一律無頭；每項工作先有 issue、以 PR 交付；相近工作共用一條 feature branch；工作狀態隨時更新在 issue 上，一次一人認領，審查者審完要更新 issue、#93 與受影響文件。

##### 10.2 開著的 PR

| PR | 分支 @ head | 狀態（核對時） | 下一步 |
| --- | --- | --- | --- |
| [#624](https://github.com/Polalalabear/amidst/pull/624) #597 規則 vs LLM runner／評分器／dry-run | `claude/feat-live-hardset` @ `29110958` | Draft；Opus 裁決的 8 項已修；CI 執行中（BLOCKED 是在等 checks） | **待 Sonnet 確認**，CI 綠就合併（D305）。實跑要等 #608 合併，並由使用者核准金額；dry-run 估 9 段最壞 USD 2.90 |
| [#625](https://github.com/Polalalabear/amidst/pull/625) CL-B16 8785 預錄 Q2 Agent 開關 | `claude/feat-recorded-openai-agent` @ `d46d55b5` | Draft，CI 綠；Opus **NEEDS_CHANGES**：3 項小修＋UI 截圖（A4-1、B4-1、B-05）。使用者選 A：demo 專用 APPROVED | **尚未派修正**。截圖要磁碟 ≥ 8 GiB，demo 伺服器才能啟動 |
| [#627](https://github.com/Polalalabear/amidst/pull/627) D319 第一次檢索 | `claude/feat-ops-docs` @ `3e888e93`（本交接段也在這條分支） | Draft，CI 綠；Sonnet 已核對約 130 項並修正，紀錄在 `docs/index/` | **待複審**，過了就合併（交接文件跟著一起合） |
| [#628](https://github.com/Polalalabear/amidst/pull/628) #619 室外遠端目標（Claude 接手） | `claude/feat-live-far-target` @ `7e2a1b91` | Draft，CI 綠；紅標籤 weak 0.3→0.2，標紅比例 78.8%；難題點前 3 s 跟對**沒有改善**，根因是覆蓋或排程缺口 | **待 Sonnet 審** |
| [#608](https://github.com/Polalalabear/amidst/pull/608) relock R1 | `codex/feat-live-relock` @ `fe4f2541` | 和 main 衝突（DIRTY）；Opus NEEDS_CHANGES | 等 Codex |
| [#617](https://github.com/Polalalabear/amidst/pull/617) LIVE A/B 錄製重播 | `codex/feat-live-ab` @ `c0498745` | Draft，和 main 衝突（DIRTY）；Opus NEEDS_CHANGES；**沒有對應 issue**，Codex 要補開（D334） | 等 Codex |
| [#623](https://github.com/Polalalabear/amidst/pull/623) 3D 視圖 est_xy（#612） | `codex/feat-workbench-8cam` @ `e49a31af` | Draft，CI 綠；Opus NEEDS_CHANGES | 等 Codex |

Codex 有沒推送的本機修改，額度用完，**2026-11-20 22:29** 才回來；在那之前 Claude 不接手 #608、#617、#623，以免衝突。

##### 10.3 待補

- **D319 第二輪檢索**：等 #608、#617、#623、#624、#625、#628 合併後，補 `docs/index/` 的「待補檢索」那節。
- **8785 pin 更新**：等 #625、#623 合併後跑 gate（`RESULT.txt` 每行以 PASS 結尾），使用者核准再更新；#618 的 308 轉址也要等這次 pin 更新才生效。
- **A4、B4 候選數為 0**（#625 Opus 另提）：原因未查，建議另開 issue。

##### 10.4 本機

- 磁碟約 7.6 GiB 可用；交換檔約 5 GiB，可用空間會跳動。低於 9 GiB 不開第三個寫手，低於 5 GiB 停工。
- 已刪：Xcode Previews、ShipIt、`~/.npm`。
- B 類候選（要先確認才能刪）：codex-runtimes 2.4G、`.codex/visualizations` 1.8G、Chrome 快取 1.1G、`local/archive/office-canonical` 921M（目錄層級的刪除候選，SHA-256 不適用）。

##### 10.5 新協調者第一批工作（依優先順序）

1. 派 Sonnet 確認 #624 → CI 綠即合併（D305）。
2. 派 #625 修正（3 項小修）；磁碟 ≥ 8 GiB 後補三張 UI 截圖。
3. 派 Sonnet 審 #628、複審 #627 → 過了就合併。
4. Codex 回來（11-20 22:29 後）推送修正後，審 #608、#617、#623。
5. 下一個決策編號 **D336**。

---

<a id="h20261122"></a>

## 2026-11-22（原 docs/agents/COORDINATOR_HANDOFF_20261122.md）

### 協調者交接（2026-11-22）

> **新的協調者對話全程用繁體中文回覆（D255）。**
> 快照時間：2026-11-22（台北時間）。現行決策與狀態以釘選任務板 [#93](https://github.com/Polalalabear/amidst/issues/93) 為準，本文件只是快照；上一份交接是 `docs/agents/COORDINATOR_HANDOFF_20261118.md`。

#### 1. 一句話現況

研究核心是證明「真正呼叫模型、看圖、知道空間資訊的 Agent，在複雜情況下的鏡頭切換決策勝過規則演算法（RT-DETR＋HSV＋規則閘門）」。

- 已完成的實驗（D325 更正、看圖先導、W1、W2）都只在簡單場景 A4-1、B4-1：離線有增益，即時增益 0（延遲約 4.3 s），**H1 還沒有數據**。
- 2026-11-22 定了三天計畫（到 11-25），依序做 F1 評分器→F2 空間圖→F3 H6→F4 E3 實驗→F5 論文。Claude 一次只開一個大 feature；Codex 同時做困難劇本 #652。

#### 2. 目前狀態

| 項目 | 狀態 |
| --- | --- |
| main 最新 | `802bc24fbb24d8c779c3e4a00ebb452855ba63a6`（#653 merge） |
| 近期 merge | #648 W2 `8290f190`；#653 D342 文件同步 `802bc24f`；#655 G7 ApiGuard `4f665d55`；#617 LIVE 錄製重播 `1742ed06`；#608 relock R1 `cfbfe4e9` |
| 8785 demo | pin `b98fac2a`（`local/demo-pin.json`，2026-11-18 核准）。網址 http://127.0.0.1:8785/workbench-v2/ 。在 `~/amidst` 執行 `./start_445_demo.command --port 8785` 啟動。**磁碟低於 8 GiB 時，程式內建的保護會擋下啟動**（`DISK_BELOW_8_GIB`）。2026-11-22 已重新啟動。 |
| 8791 LIVE | `local/runtime/live-main` @ `4f665d55`，PID 75703，網址 http://127.0.0.1:8791/ ，啟動腳本 `local/runtime/start_live_8791.sh`，沒有 pin。 |
| 磁碟 | 約 10 GiB 可用（`df -k` 計算）。第三個寫入 session 開工前需要 ≥ 9 GiB，剩 5 GiB 就停。 |
| 花費 | OpenAI 累計約 USD 22.4（ApiGuard 帳本，非 DENIED）。上限 USD 100，累計到 USD 90 之前不用問（D344）。 |

#### 3. 所有工作（依類型）

##### 3.1 即時模式（LIVE，8791）

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| #608 relock R1 | 失聯後重新找回目標的狀態機 | 已合併 `cfbfe4e9`。門檻 `t_short_s`、`tau_app`、`margin_app` 仍是 UNKNOWN，預設關閉，只列候選給人確認 | 自動選人要等 E3 量測門檻；#588 保持開啟 |
| #617 LIVE 錄製重播 | `live-ab.case.v1` 確定性案例 | 已合併 `1742ed06`。輸入側重播確定，偵測器和 Agent 的輸出不保證；schema 狀態是 PROPOSED | E3 開跑前要改成正式狀態並釘 SHA（由 #652 處理） |
| #633 LIVE 改成 workbench-v2 風格，第二段 | operator.mjs、server.py 部分的樣式統一 | 第一段已合併（#634）；#617 已合併，第二段可以開工 | 不在三天計畫內，排在 F5 之後 |
| LIVE 看不到鏡頭 | 使用者回報：人物移動時，場景裡看不到現有攝像頭 | 已併入 F2 #656 | 等 F1 完成 |
| #589 CX-L6b R2 後台接線 | 重新取得目標的後台接線＋排程驗收 | blocked | 等 relock 門檻量測（E3） |
| #574 CX-L5g A/B 整合驗收 | A/B 雙畫面整合與 handoff 文件 | blocked | 等 #589 |

##### 3.2 WP5 與 Agent 決策

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| [F1 #660](https://github.com/Polalalabear/amidst/issues/660) 統一 GT 評分器、重算凍結結果、E3 預先登記 | 單一評分模組（中心點準則和 IoU ≥ 0.3 都輸出；錯人、定位不準、失聯、錯鏡頭分開計；分母一律用 GT 可見時間）；D325、先導、W1、W2 的新舊數字對照；`docs/evaluation/E3_PREREGISTRATION_20261122.md` | **執行中**，session `local_80128dbb-6aa7-40d6-95d0-2c21fe64164c`（Opus high），分支 `claude/feat-e3-scorer` | 等它開 PR 並回報 |
| [F2 #656](https://github.com/Polalalabear/amidst/issues/656) E3 空間圖 | 用牆面裁切鏡頭覆蓋範圍（場景幾何＋鏡頭位置／FOV），寫進 `scene_context`；LIVE 畫面和小地圖顯示鏡頭、FOV、盲區 | blocked | 等 F1 合併（一次一個 feature） |
| [F3 #657](https://github.com/Polalalabear/amidst/issues/657) H6 統一決策路徑 | 8785 和 LIVE 的 Agent 模式真正接管；拿掉 C1–C5、C7、X1 的提前阻擋；用決策紀錄證明 Agent 的答案被採用。**#645 第二步和 #646 W3 都併入這裡** | blocked | 等 F2 |
| [F4 #658](https://github.com/Polalalabear/amidst/issues/658) E3 實驗 | B1、B2、A1、A2、A3 × 困難劇本 × K=3；A3 先在重播上依實測延遲模擬即時，再跑一小段真的 LIVE | blocked | 等 F1–F3 和 Codex #652 |
| #623 預錄 est_xy＋B4-1 8CAM | 系統估計位置顯示 | **暫緩**。Opus 三點裁決已通過，但 8CAM 的 est_xy 永遠是 UNKNOWN，workbench-v2 也沒畫出來，只在 API 回傳裡 | 三天內不處理；之後由 Codex 補齊再合併 |

##### 3.3 研究紀錄與報告

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| 論文版報告（Claude Docs） | https://claude.ai/artifact/B7oycBdnYfkeK1U1JiPWSL ，rev 52 | 已完成 H1–H6、更正章節、W1/W2 的段落（W2 措辭採用 #648 Opus 裁決） | E3 結果出來後由 F5 更新 |
| 交付資料夾 | `local/evidence/final-package-20261120/`（LOCAL，不打包 zip，使用者直接看資料夾）：diagrams、specs、data、figures、screenshots、report | 已完成。論文 PDF `report/amidst_paper_20261120.pdf` 27 頁，SHA-256 `12e048b1f48d25c6d25f25b1e64e3b9a1c729cd054f26754c78fa1ed5d99f3fb`；`MANIFEST.sha256` SHA-256 `9f1edca8db45c4b75335934f755180354b675368e923197b70803077f15515a4` | F5 定稿時更新 |
| 舊 zip | `local/evidence/amidst_final_package_20261120.zip`，SHA-256 `00bbd700212a6b006d4bbaecc94ad1cc27d0acb6b85a70c99d2e3c707d81c0d8` | 使用者改成看資料夾後就不再使用；保留，未刪 | 要刪需使用者同意 |
| [F5 #659](https://github.com/Polalalabear/amidst/issues/659) 論文與交付資料夾定稿 | 加入 E3 結果的論文、資料夾、圖表 | blocked | 等 F4 |

##### 3.4 8785 demo

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| 8785 Agent 模式真正接管 | 見 F3 | — | F3 |
| 8785 pin 更新 | 新 pin，包含 F3 | 現在是 `b98fac2a` | F3 合併後跑 gate，再由使用者核准 |

##### 3.5 流程與整理

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| 更新測試文件 | 測試文件和現況一致 | 未開始 | **使用者確認所有更新無誤之後，第一件事就是這個**（使用者 2026-11-20 指示） |
| D319 第二輪檢索 | `docs/index/` 更新 | 未開始 | 排在三天計畫之後 |
| PROGRESS | `docs/operations/Q1Q5_PROGRESS.md` | 已更新到 #655（D342） | #656–#660 由協調者在下一批補上 |

##### 3.6 Codex 與 Argon 的任務

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| [#652](https://github.com/Polalalabear/amidst/issues/652) CX-E3 困難劇本 | 4 類：A 相似衣著交錯、B 3–10 秒長盲區、C 多出口（含目標落在前 3 候選之外）、D 遮擋和真正離開。至少 8 段、約 40 個複雜決策點，錄成正式的 `live-ab.case.v1` 並釘 SHA | ready，派給 Codex；期限 2026-11-23 結束前 | 等 Codex 交件。Blender 渲染免問，但要回填 issue 和 PR |
| #623 | 見 3.2 | 暫緩 | — |
| W4（複雜場景渲染） | — | 還沒開 issue，內容已由 #652 涵蓋 | 若 #652 需要 Blender 新場景，由 Codex 在 #652 內處理 |
| Argon | — | 目前沒有派工 | — |

#### 4. 決策 D336–D344 摘要（下一個是 **D345**）

- **D336**：新協調者接手的第一批派工（#624、#628 等）。
- **D337**：LIVE 全面改成 workbench-v2 風格，分兩段做（#633）。
- **D338**：依 D319 第一輪檢索更新規格、文件與索引（#631／#632，已合併 `7ef1426b`）。
- **D339**：OpenAI 預算 USD 50 內不用問（已由 D344 取代）；#637 結論只限於覆核架構。
- **D340**：放寬 Agent 模式（取代 D64、D128）。Agent 可以看畫面、選任何偵測框（含低分和非人物類別），也可以回答「被遮住」「看不到」「下一台鏡頭」。場景資訊（鏡頭關係、可行走連通、FOV、覆蓋範圍）是必要輸入，只能來自設定檔和標定資料。規則閘門在 Agent 模式下只當資訊。GT 隔離、ApiGuard、身分 UNCONFIRMED、付費核准仍然是硬限制。補充：請求分三層，場景資訊做成固定前綴並使用提示快取。H6：Agent 和規則在所有模式都要能切換。
- **D341**：依 D340 和 H1–H6 重整工作清單（W1 #644、W2 #645、W3 #646）。
- **D342**：#648 合併後的全面文件同步（#653，`802bc24f`）。
- **D343**：#655、#617、#608 合併；#623 三點裁決（est_xy 只用於顯示，稱「速度上限可達半徑」；estimate 是附加欄位，不在 contract B 範圍內；接受 scripts→live_mode.Projector 的依賴）；E3 的三個事實（LIVE 有 8 台鏡頭含 CAM_ENTRY；相似衣色多人片段 5 段；輸入側重播確定）。
- **D344**：預算 USD 100，到 90 前不用問；Blender 渲染免問，但要回填 issue 和 PR；Claude 一次只開一個大 feature；三天計畫；#623 暫緩。

#### 5. 假設 H1–H6 的證據現況

| 假設 | 現況 |
| --- | --- |
| H1 複雜情況下切換決策勝過規則 | **尚無數據**（A4-1、B4-1 太簡單，規則本來就不會錯人）。由 E3（F4）驗證 |
| H2 增益來自看圖 | 有條件成立：不給圖時，跟對率掉到 0.55–0.65 |
| H3 閘門當資訊而不是硬擋 | D340 已落實在 W2 程式；系統路徑由 F3 處理 |
| H4 主動找鏡頭時用空間資訊 | 只有描述性訊號：B4-1 前 3 名 37/40 對 9/40，但前 1、前 2 名都只有 8/40，低於隨機；差異全部在第 3 順位。**不支持 H4**。F2 修正覆蓋範圍後再驗 |
| H5 辨識勝過 RT-DETR＋HSV | 有條件成立：在 RT-DETR 漏掉、誤分類、目標遠或被擋的情況下成立。整體 F1 0.955（mean）對 0.957（多數決） |
| H6 所有模式都能切換 | 前提條件，由 F3 處理 |

另外：在中心點準則下，W2「沒有變差」成立；改用 IoU ≥ 0.3，B4-1 跟對率是 0.761、錯人 6.3 s。即時模式下所有看圖組都和規則一樣，增益 0（p50 延遲 4.3 s）。

#### 6. 三天計畫（到 2026-11-25）與暫緩清單

- **Day 1**：F1 評分器、重算凍結結果、預先登記；Codex #652 困難劇本。
- **Day 2**：F2 空間圖 → F3 H6（一次一個）；F4 跑 B1、B2、A1、A2，A3 先模擬即時。
- **Day 3**：補跑、錯誤案例分析、F5 論文與資料夾、8785 pin（使用者核准）。
- 時間不夠時，先犧牲 A3 的真即時部分；不降低成立門檻，樣本不足就標為探索性結果。
- **暫緩**：更換 RT-DETR、ByteTrack／OSNet、大量比較不同 LLM、完整 3D 追蹤、完整外觀記憶、TLA+、真實世界資料集、UI 美化、#623 畫面補齊、#633 第二段。

#### 7. 流程規則重點

- Claude 一次只開一個大 feature（一個寫入 session），做完才開下一個（D344）。寫檔一律在 scratchpad 的精簡 clone 裡做，用完刪除；`~/amidst` 不能改、不能切分支、不能 commit、不能 fetch。
- 審查：每個程式 PR 由 Sonnet medium 做正式審查；complex code 或有決策點的交給 Opus，只看被標出的點。
- 審過且 CI 綠就直接用 merge commit 合併並刪分支（D305）。UI 和 pin 先給使用者看截圖。
- 合併如果被權限分類器擋下，就給使用者一條 `gh pr merge <n> --merge --delete-branch --repo Polalalabear/amidst` 指令自己跑（每條指令只給一次）。
- Blender 渲染免問，但要把渲染內容、張數或時長、產物路徑和 SHA-256 回填到 issue 和 PR（D344）。
- 付費呼叫一律先經 ApiGuard dry-run 並記帳；累計到 USD 90 前不用問。
- 被 session 事件喚醒的回合不能開新 session，只能用提案卡，或用 SendMessage 交給已經有脈絡的 session。
- 決策同步到 #93（D 編號接續）；每項工作都要有 issue 和 PR；瀏覽器測試一律無頭。
- 使用者確認更新無誤後，**第一件事是更新測試文件**。

#### 8. 新協調者要讀的文件

1. 本文件，以及 [#93](https://github.com/Polalalabear/amidst/issues/93) 本文和 D336–D344 的留言。
2. `docs/evaluation/AGENT_VS_RULE_HYPOTHESES_20261120.md`（H1–H6、§4 的衝突清單 C1–C8、X1）。
3. `docs/evaluation/W2_ACTIVE_AGENT_20261120.md`，以及 [#648 Opus 裁決](https://github.com/Polalalabear/amidst/pull/648#issuecomment-7029512103)（論文可引用的措辭）。
4. `docs/specs/DEVELOPMENT_RULES.md`、`docs/specs/Q1Q5_PRODUCT_SPEC.md`（D340、H6、資料流）。
5. F1 完成後：`docs/evaluation/E3_PREREGISTRATION_20261122.md`。
6. `docs/operations/Q1Q5_PROGRESS.md`。

#### 9. 第一件事

1. 讀 F1（[#660](https://github.com/Polalalabear/amidst/issues/660)，session `local_80128dbb-6aa7-40d6-95d0-2c21fe64164c`）的回報。
2. 審 F1 的 PR：Sonnet 做正式審查；評分器屬於 complex code，交給 Opus 看預先登記的成立門檻。通過且 CI 綠就合併。
3. 開 F2 #656（一次一個 feature）。同時追 Codex #652 的交件。

---

<a id="h20261123"></a>

## 2026-11-23（原 docs/agents/COORDINATOR_HANDOFF_20261123.md）

### 協調者交接（2026-11-23）

> **新的協調者對話全程用繁體中文回覆（D255）。**
> 依據：更新紀錄 [#674](https://github.com/Polalalabear/amidst/issues/674) 至第 18 則；`main` @ `c988ed607cb2941bde2b84688f9675213efd2a98`。本文件是快照；現行決策在 [#93](https://github.com/Polalalabear/amidst/issues/93)（D 號，下一個是 **D356**），所有更新追加在 #674（append-only）。上一份交接是 `docs/agents/COORDINATOR_HANDOFF_20261122.md`。

#### 1. 一句話現況

E3 跑完了：在 16 段困難劇本上，**這個整合下的看圖 Agent 沒有勝過規則**。H1、H2、H4 判「不成立」，Sonnet 和 Opus 都確認不是程式錯誤（D354）。使用者決定先做 **E4：條件式 Agent 覆寫**（探索性改良），再寫 F5 論文（D355）。期限 2026-11-25。

#### 2. 目前狀態

| 項目 | 狀態 |
| --- | --- |
| main | `c988ed60`（#671 合併） |
| 8785 demo | pin `c988ed60`（2026-11-23 使用者核准，gate `local/evidence/gate-pin-20261123/RESULT.txt` 15 項 PASS）。PID 23134，終端 tab 1。http://127.0.0.1:8785/workbench-v2/ |
| 8791 LIVE | `local/runtime/live-main` @ `c988ed60`，PID 22779，終端 tab 0。http://127.0.0.1:8791/ |
| 磁碟 | 約 11 GiB 可用（第三個寫入 session 前需要 ≥ 9 GiB；剩 5 GiB 就停；8785 在 < 8 GiB 時不啟動） |
| 花費 | 交接前累計 USD 22.4＋F3 0.33＋F4 27.28＋8785 gate 0.13 ≈ **USD 50**。上限 USD 100，累計到 90 前不用問（D344）。E4 預估 +15–20 |
| E3 分數 | 已評分並判定（#678）。凍結評分器 `src/amidst/evaluation/e3_scoring.py` SHA-256 `acacce39…7d08` |

#### 3. 所有工作（依類型）

##### 3.1 WP5 與 Agent 決策（核心）

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| [F1 #660](https://github.com/Polalalabear/amidst/issues/660) 評分器＋預先登記 | — | ✅ #662 `ea0db4fd`；修訂 #667 `744f9d7f`（D348、D349）、#671 `c988ed60`（D350 H2 補充診斷、A3 §7） | — |
| [F2 #656](https://github.com/Polalalabear/amidst/issues/656) 空間圖 | — | ✅ #664 `8af69ea4`。E3 前閘門：LIVE 8 台都沒通過，E3 不裁牆（D348） | — |
| [F3 #657](https://github.com/Polalalabear/amidst/issues/657) H6 Agent 接管 | — | ✅ #666 `61867089`（M1：答案無法採用→交回規則；M2 schema；M3 場景上下文失敗不靜默） | 8CAM／B-05 未接 → Codex #679 |
| [F4 #658](https://github.com/Polalalabear/amidst/issues/658) E3 實驗 | 報告 `docs/operations/F4_E3_REPORT_658.md` | **PR [#678](https://github.com/Polalalabear/amidst/pull/678) head `b4e6a07f`，CI 綠**。Sonnet 正式審查 PASS；Opus 裁決負面結果成立；M1–M5 文字已補 | **Sonnet 複審 M1–M5 中**（session `local_02bd80a4…`）。PASS 就依 D305 合併（不刪 `claude/feat-e3-run` 之前先確認工作線不再用） |
| **E4（D355）** 條件式 Agent 覆寫 | `E4_PREREGISTRATION_20261123.md`（跑前寫死）、實作（只改 Agent 路徑）、A2-E4 K=3 × 16 段、`E4_REPORT`；探索性 | 已交給工作線（分支 `claude/feat-e4`，要開 issue＋PR） | 等 #678 合併後開工 |
| [F5 #659](https://github.com/Polalalabear/amidst/issues/659) 論文與交付資料夾 | 論文 md（唯一正本，進 git）→ PDF；研究更新稿進 `docs/operations/`；加 E4 探索性一節 | 未開始 | 等 E4。依 D355 可平行先寫 E3 章節（檔案不重疊時） |
| #623 預錄 est_xy／8CAM | — | 暫緩（D344） | 11-25 之後 |

**E3 結果（#678，預先登記 §6）**

| 假設 | 判定 | 數字 |
| --- | --- | --- |
| H1 | 不成立 | A2 − B1 錯人秒 +129.8 s [36.2, 218.5]；McNemar p = 0.648 |
| H1 次要（A3） | 探索性 | +4.3 s [−12.4, 23.6]（9 段／38 點；77/156 答案過期） |
| H2 | 不成立 | A1 − B1 +145.1 s；A2 − B2 +129.8 s（B2 追蹤＝B1） |
| H4 | 不成立 | A2 top-1 3/111；**102/111 點沒有排名**，有排名時 3/9；hint 只跟著 NOT_VISIBLE（62/1684） |
| H5 | 本次未判定 | 證據仍只有 W1 |
| H3 | 描述性（D353） | override 被採用 155 次，第一個 tick CORRECT 62（40%） |

**失敗機制（Opus）**：34% 被採用的 SELECT 落在看不到目標的鏡頭；AMBIGUOUS 時選錯人，且 LIVE 路徑每次採用都重設追蹤器（C3／C4／C6 的錯誤 75–79% 發生在規則正確的 tick）。可能歸給程式的上限 73.4 s 全扣掉，A2 仍比 B1 多約 56 s。**論文措辭**：範圍限「這個整合」；與 W1 對照（目標在畫面時辨識較好，F1 0.887 vs 0.518）；差距在「判斷不在」與「怎麼接進追蹤器」。不能寫「看圖 Agent 普遍比規則差」。

**E4 設計（D355）**：可信追蹤鎖定（規則穩定時 Agent 只提候選、不重設）＋條件式覆寫（失聯或可信度下降才採用，採用前驗證鏡頭／框／外觀／時間戳）＋短期追蹤記憶（有時限）＋ NOT_VISIBLE／UNCERTAIN／下一鏡頭排序分開（每次都給排序）＋執行紀錄補 `detection_id`、候選清單、請求原文。假設 H7a（錯人秒低於 E3 A2，對 B1 不差）、H7b（盲區誤鎖降）、H7c（有排名點增加）。B1／B2 沿用；同評分器、同 16 段；標探索性（看過 E3 後在同一批劇本上的改良）。

##### 3.2 即時模式（LIVE，8791）

| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| [#672](https://github.com/Polalalabear/amidst/issues/672) LIVE 追其他目標（探索性） | 設計在假設文件 §0.2（#673 `2f5e5a9f`） | E3 已凍結，但會改 `advisor.py`／`scheduler.py`，和 E4 重疊 → E4 之後 |
| #633 LIVE 改 workbench-v2 風格第二段 | — | 11-25 之後 |
| #588／#589／#574 relock 門檻、R2 接線、A/B 整合 | blocked | 等 relock 門檻量測 |

##### 3.3 研究紀錄與報告

| 工作 | 狀態 |
| --- | --- |
| 版本管理（D351） | 正本只在 main；論文以 md 為唯一正本，PDF 由 md 產生；Claude Docs 稿（`B7oycBdnYfkeK1U1JiPWSL`）不再手改；衍生文件標「依據 #674 至第 N 則／main @SHA」；E3／E4 判定進 main 後一次重產 |
| 研究更新稿 `local/evidence/research-update-20261122/RESEARCH_UPDATE_20261122.md` | 已標「已過時」，保留為歷史快照 |
| 論文 `local/evidence/final-package-20261120/report/amidst_paper_20261120.{md,pdf}` | 仍是 W2 前的數字 → F5 |
| 引用索引待更新清單 | #674 第 17 則（CODE_DOC_MAP、PROGRESS、假設文件 §0、論文、交付資料夾 README／MANIFEST、#479） |
| 外部審查回饋（D350） | 已採用 |

##### 3.4 8785 demo

| 工作 | 狀態 |
| --- | --- |
| pin 更新 | ✅ `c988ed60` |
| `real-e2e.mjs` 多畫面格數 | 仍斷言 F3 前的格數；gate 用本機補丁 `local/evidence/gate-pin-20261123/real-e2e-local-patch.diff`。已交給工作線，併進下一個 PR |
| 3D 按鈕、8791 透視預設關 | gate 沒驗（只有單元測試） |

##### 3.5 流程與整理

| 工作 | 狀態 |
| --- | --- |
| 更新測試文件 | **使用者確認整體更新無誤後的第一件事**（2026-11-20 指示），尚未開始 |
| `Q1Q5_PROGRESS.md` | 只到 #655；補列 #656–#680，來源用 #674 |
| D319 第二輪檢索 | 三天計畫之後 |

##### 3.6 Codex（可以平行多項，檔案不和 E4 重疊）

| 工作 | 產出 | 狀態 |
| --- | --- | --- |
| [#668](https://github.com/Polalalabear/amidst/issues/668) E3 論文素材（PR [#670](https://github.com/Polalalabear/amidst/pull/670) `d57b5319`） | 16 張前後拼圖、8 張決策地圖、八鏡頭總覽 | Sonnet NEEDS_CHANGES：只差圖說加「僅為示意；E3 推論未使用牆面裁切（D348）」。修好後交 Sonnet 複審 |
| [#679](https://github.com/Polalalabear/amidst/issues/679) CX-H6 8CAM／B-05 接 Agent＋手動改選 | Draft PR `codex/feat-h6-8cam`＋截圖 | ready，可以現在開工 |
| [#680](https://github.com/Polalalabear/amidst/issues/680) CX-F4R F4 主結果獨立重算 | `docs/evaluation/F4_INDEPENDENT_RECOMPUTE_20261123.md` | ready，可以現在開工 |
| #652 E3 困難劇本 | ✅ #663 `adb69449`、#665 `644ae036`（16 段、68 點、33 個 H4 點） | 可以關 issue |
| #623 | 暫緩 | — |

#### 4. 決策 D345–D355 摘要（下一個是 D356）

- **D345** Claude 單一工作線（F1→F4）；使用者實測三問題併入 F2／F3。
- **D346** 靜態牆與門可以進 `scene_context`（只限 `occluders_full_height`、`door_openings`，附 SHA）。
- **D347** 接受統一評分新尺；門檻寫成 `verdict_*`；樣本門檻不降；看到 E3 資料後 §4／§6 凍結。
- **D348** F2 閘門維持嚴格：E3 的 LIVE 不裁牆；H4 的空間資訊不含牆面裁切。
- **D349** #665 的 7 段納入 E3；兩批一起評分。
- **D350** 外部審查回饋：收斂到 E3；H2 補充診斷；GT 代理框抽查；F4 報告逐段。
- **D351** 報告版本管理：一個正本，衍生唯讀；論文 md 為唯一正本。
- **D352** F4 預算上限設定錯誤的重跑規則（只依 `CALL_BUDGET_EXHAUSTED` 欄位、同組 K 次全部重跑）。
- **D353** H3 只做描述（探索性）；H6 用完成度表；#666、#673 合併。
- **D354** F4 負面結果接受；報告補 M1–M5 後合併；接 F5。
- **D355** E4 採用；先 E4 再 F5；D344 的「一次一個大 feature」是避免處理零碎小問題，**不是禁止平行**。

#### 5. 進行中的 session

| session | 角色 | 狀態 |
| --- | --- | --- |
| `local_80128dbb-6aa7-40d6-95d0-2c21fe64164c`（F1 工作線） | Claude 工作線：F4 收尾 → E4 → F5 | 已收到 D355 的 E4 brief |
| `local_02bd80a4-e456-4919-93cb-8d82f3c681ff`（Sonnet 審查） | 所有 PR 的正式審查 | 正在複審 #678 M1–M5；#670 等 Codex 修完再審 |
| `local_364c082e-2607-49f5-88f3-671219bb10a2`（Opus） | complex code／決策裁決（做過 #662、#664、#666、#678） | 閒置，可用 SendMessage 續用 |
| `local_3b5c01e6-8e1b-416b-968b-9c480439816d`（pin gate） | 8785 gate | 已完成，可封存 |

#### 6. 流程規則重點

- 協調者只規劃、決策、寫 brief、合併。後續指示用 SendMessage 送給已有脈絡的 session。
- 審查：每個程式 PR 由 Sonnet 正式審查；complex code 或決策點交 Opus，只看被標出的點。審過且 CI 綠就用 merge commit 合併（D305）；UI 和 pin 先給使用者看截圖。
- `~/amidst` 是 8785 pin 資料夾：不改檔、不切分支、不 commit。寫檔一律在 scratchpad 精簡 clone。
- 合併、kill、approve 被權限擋下時，給使用者一條指令自己跑（每條只給一次）。
- 付費呼叫一律經 ApiGuard；每個行程用自己的帳本；到 USD 90 前不用問。
- Blender 渲染免問，但要回填 issue 和 PR。
- 每個節點都要在 #674 追加一則（格式見 #674 本文）；決策正文寫在 #93。
- 被 session 事件喚醒的回合不能開新 session，改用提案卡或 SendMessage。

#### 7. 新協調者第一件事

1. 讀本文件、[#674](https://github.com/Polalalabear/amidst/issues/674) 最後幾則、#93 的 D354、D355。
2. 等 Sonnet 複審 #678 M1–M5：PASS 且 CI 綠就合併，然後通知工作線開始 E4。
3. 把 Codex 的三個任務交給使用者貼上：#670 圖說修正、#679、#680（派工文字見交接訊息）。
4. E4 預先登記開出 PR 時，先審門檻（Opus），再讓工作線開跑。
5. 使用者確認整體無誤後，第一件事是更新測試文件。

---

<a id="h20261123b"></a>

## 2026-11-23b（原 docs/agents/COORDINATOR_HANDOFF_20261123b.md）

### 協調者交接（2026-11-23 第二份）

> **新的協調者對話全程用繁體中文回覆（D255）。**
> - 依據：`main` @ `ab51e5ac`（#686 合併）、更新紀錄 [#674](https://github.com/Polalalabear/amidst/issues/674) 共 47 則。
> - 本文件是快照。現行決策在 [#93](https://github.com/Polalalabear/amidst/issues/93)（下一個 D 號是 **D359**），更新一律追加在 #674。
> - 上一份交接：`docs/agents/COORDINATOR_HANDOFF_20261123.md`。

#### 1. 一句話現況

E3 的結論是：在依附規則的整合方式下，看圖 Agent 沒有勝過規則。使用者因此改做 **E5：完全開放的 Agent 對規則**（A-open，D356），只用資源限制約束 Agent。E4 已停，資料保留成探索性附錄。

E5 的預登記和介面契約在 PR #685，目前等 Codex 回覆「契約確認」。實作會在 Codex 的新對話裡做。海報和簡報素材已經做好，放在 LOCAL 資料夾。

#### 2. 工作方式（使用者 2026-11-23 指示）

- **協調者主對話只做決策。** 實作、審查交給子 session，按 CLAUDE.md 的模型分級表派工。
  - 例外：使用者要求審查直接在主對話做時，照使用者的意思。
- **要貼的文字放在回覆的 code block。** 給 Codex 的訊息、給使用者的指令都一樣，每條只給一次。
- **工作後的文件只做必要更新。** 大更新（PROGRESS 補列、index、CODE_DOC_MAP）之後再一起做。
- **合併規則（D305）：** 審查通過、CI 綠燈就用 merge commit 合併。UI 改動要先給使用者看截圖。
- **#676 的 Codex PR #690 在 E5 結束前不能合併。**
- **預算：** 上限 USD 100，累計到 90 前不用問。目前累計約 **USD 58**。E5 的費用上限是 USD 25，每次執行都要先 dry-run。
- **磁碟：** 剩約 9.7 GiB。開第三個寫入 session 前至少要 9 GiB，剩 5 GiB 就停。

#### 3. 所有工作（依類型）

##### 3.1 WP5 與 Agent 決策（核心）

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| [E5 #684](https://github.com/Polalalabear/amidst/issues/684) A-open（預登記＋契約） | `docs/contracts/E5_AOPEN_INTERFACE_V1.md`、E5 預登記 | PR [#685](https://github.com/Polalalabear/amidst/pull/685) head `0587ecf9`，CI 2/2 綠。協調者對三項待釐清事項的裁決已寫進契約：①API 分類 ②缺排名的表示法 ③OCCLUDED 維持條件。§4 評分和 §5 門檻沒改 | **等 Codex 在 #685 回覆「契約確認」**。協調者先看 `af71af55..0587ecf9` 的差異，確認只動到裁決的三項；Codex 確認後就合併 #685 |
| E5 實作與執行 | `decider.py`、`neutral.py`、`e5_run.py`，A-open × 16 段，報告 | 未開始 | 要等 #685 合併。由 Codex 新對話實作，Claude 審查（complex code，Opus 決定）。每次執行先 dry-run，費用上限 USD 25 |
| E4 | 探索性附錄 | 已停（D356）：跑了 10/48 次，花 USD 4.30，沒有評分。`claude/feat-e4` `f8f21afa` 保留 | — |
| F5 #659 論文 | 論文 md → PDF | 未開始 | 等 E5。E3 章節可以先寫（檔案不重疊時） |
| #623 預錄 est_xy／8CAM（Codex） | — | Draft，CI 綠，待 Claude 審查 | 暫緩到 11-25 之後（D344） |

##### 3.2 即時模式（LIVE，8791）

| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| #676 顏色接線＋#675 LIVE Agent 啟用（Codex PR [#690](https://github.com/Polalalabear/amidst/pull/690)） | #676 Codex 已完成，待 Claude 審查。#675 的啟動和開關都驗證過了 | ①#675 的真實回應要等**使用者核准資料外傳**。②**E5 結束前不能合併** |
| #689 未接入的 run 拒絕 manual_seed（Codex，Closes #688） | Codex 已完成，CI 綠 | 待 Claude 正式審查（Sonnet medium） |
| #672 LIVE 追其他目標 | 設計在假設文件 §0.2 | 會改 advisor／scheduler，排在 E5 之後 |
| #633 LIVE 改 workbench-v2 風格 | — | 11-25 之後 |

##### 3.3 研究紀錄、報告與發表

| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| PR [#687](https://github.com/Polalalabear/amidst/pull/687) D358 引用更新（交接指向 20261123、F4 E3 報告、假設文件 §0） | Draft，CI 綠 | 待審查；審查通過後依 D305 合併。合併後再把交接指向改成本文件（小改動，可以併進下一個文件 PR） |
| 海報（A1 直式、可編輯 .pptx）與簡報大綱（open-slide） | 已完成，放在 LOCAL `local/evidence/presentation-pack-20261123/`，內容見 §5 | ①使用者從三張架構圖選一張。②結果數字等 E5。③簡報要依 `slides/OUTLINE.md` 寫成 open-slide 專案（Claude 製作，Sonnet medium） |
| #479 報告素材、#674 更新紀錄 | 持續追加 | — |

##### 3.4 8785 demo

- 8785 的 pin 在 `c988ed60`（使用者 2026-11-23 核准；gate `local/evidence/gate-pin-20261123/RESULT.txt`）。
- main 已經前進到 `ab51e5ac`（#686）。要換 pin 時，跑 gate 再請使用者核准，不能自己改。

##### 3.5 Codex 的任務

- **Codex 新對話（E5 專責）：** 等它在 #685 回覆「契約確認」；#685 合併後實作 E5。
- **Codex 舊對話：** #690（#676、#675）、#689、#623。

#### 4. 新協調者的第一件事

1. 看 #685 的 `af71af55..0587ecf9` 差異，並查 Codex 有沒有回覆「契約確認」。有就合併 #685，在 #93 記 D359，在 #674 追加一則；還沒有就等。
2. 派一個 Sonnet medium 審查 #689 和 #687；審查通過、CI 綠就合併。
3. 等使用者選架構圖；派 Sonnet medium 依 OUTLINE 把簡報寫成 open-slide 專案。
4. #690 的資料外傳核准，要問使用者。

#### 5. LOCAL 產物

`local/evidence/presentation-pack-20261123/`，約 5.3 MB，可以用 `scripts/` 重建：

| 項目 | 內容 |
| --- | --- |
| `poster/poster_A1_academic.pptx` | 594×841 mm，原生文字、圖形和圖表，約 0.9 MB |
| `poster/poster_preview_quicklook.png` | 預覽 |
| `slides/OUTLINE.md` | 12 頁大綱，從動機開始，Demo 錄影 3–5 分鐘 |
| `images/` | 14 張圖：三張架構圖、決策流程圖、五張決策點圖、兩張八鏡頭畫面、鏡頭覆蓋圖、兩張工作台截圖 |
| `scripts/` | `poster_pptx.py`、`arch.py`、`flow_png.py`、`poster_v3.py`、`posters_v2.py`（python-pptx 1.0.2、Pillow 11.3.0） |
| `README.md` | 待填項目和列印說明 |

決策點圖和場景圖的來源是 `local/evidence/e3-figures-20261123/`（#670）。

---

<a id="h20261123c"></a>

## 2026-11-23c（原 docs/agents/COORDINATOR_HANDOFF_20261123c.md）

### 協調者交接（2026-11-23 第三份）

> **新的協調者對話全程用繁體中文回覆（D255）。**
> - 依據：`main` @ `ada45f31`（#695 合併）、更新紀錄 [#674](https://github.com/Polalalabear/amidst/issues/674) 共約 70 則。
> - 本文件是快照。現行決策在 [#93](https://github.com/Polalalabear/amidst/issues/93)（下一個 D 號是 **D362**），更新一律追加在 #674。
> - 上一份交接：`docs/agents/COORDINATOR_HANDOFF_20261123b.md`。

#### 1. 一句話現況

E5（完全開放的 Agent 對規則 B1）的預登記、契約、評分程式和實作都已合併，**AO 正式執行正在跑**。跑完就評分、寫報告，再決定要不要跑 AO-L。

##### 今天合併的 PR

| PR | 內容 | 合併 SHA |
| --- | --- | --- |
| [#685](https://github.com/Polalalabear/amidst/pull/685) | E5 預登記與 A-open 介面契約（D360） | `396be050` |
| [#689](https://github.com/Polalalabear/amidst/pull/689) | 未接入的 run 明確拒絕 manual_seed（Codex） | `d4521ee9` |
| [#687](https://github.com/Polalalabear/amidst/pull/687) | D358 引用更新 | `e6b4e22e` |
| [#692](https://github.com/Polalalabear/amidst/pull/692) | E5 評分程式 `e5_score.py`＋測試 | `fe442470` |
| [#693](https://github.com/Polalalabear/amidst/pull/693) | F5 論文 E3 章節（新檔 `docs/paper/F5_PAPER_DRAFT.md`） | `901e5953` |
| [#694](https://github.com/Polalalabear/amidst/pull/694) | E5 A-open 實作（Codex；Opus 裁決 D361：GT 隔離、§4、N4 接受，N2 要修） | `4ab7bc10` |
| [#696](https://github.com/Polalalabear/amidst/pull/696) | N2 修正：AO-L 搜尋排除 EXPIRED 排名（AO-L 可以跑） | `24c2dce9` |
| [#695](https://github.com/Polalalabear/amidst/pull/695) | #677 LIVE UI/UX（使用者看過截圖；**還沒部署到 8791**） | `ada45f31` |

##### 今天的決策

- **D359（使用者）**：#675 的資料外傳等 E5 結束再做；付費呼叫只要累計不會超過 USD 90 就不用問，每次仍然要先 dry-run 並記帳。
- **D360**：合併 #685。
- **D361**：合併 #694。

#### 2. 工作方式

- **協調者主對話只做決策。** 實作、審查交給子 session，按 CLAUDE.md 的模型分級表派工。使用者要求審查直接在主對話做時，照使用者的意思。
- **要貼的文字放在回覆的 code block。** 給 Codex 的訊息、給使用者的指令都一樣，每條只給一次。
- **工作後的文件只做必要更新。** 大更新（PROGRESS 補列、index、CODE_DOC_MAP）之後再一起做。
- **合併規則（D305）：** 審查通過、CI 綠燈就用 merge commit 合併。UI 改動要先給使用者看截圖。8785 換 pin 和花錢超過門檻仍要問。
- **#690 在 E5 結束前不能合併**（會改變 B1 快照的來源雜湊，見 §3.2）。
- **預算（D359）：** 上限 USD 100，累計不超過 USD 90 就不用問；E5 這邊以 USD 89 為上限。每次執行都要先 dry-run 並記帳（`ApiGuard`）。
- **磁碟：** 剩約 9.3 GiB（使用者今天刪了 Chrome-headless 快取，清出約 5 GiB）。開第三個寫入 session 前至少要 9 GiB，剩 5 GiB 就停。
- 每個子 session 完成後都要在 #674 追加一則。

#### 3. 所有工作（依類型）

##### 3.1 WP5 與 Agent 決策（核心）

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| E5 AO 正式執行（[#684](https://github.com/Polalalabear/amidst/issues/684)） | 16 段 × K=3 的 A-open 結果、評分、`docs/operations/E5_REPORT_*.md`、`claude/feat-e5` 上的 Draft PR | **進行中**：3 個行程並行，上限合計 USD 25。由子 session 「E5 AO 試跑」（Claude Code session `local_073d1ce8-8722-42b4-b1c2-1d65cdac1305`）負責，跑完會自己評分、寫報告、開 Draft PR。試跑：E3-A1 K=1，30 次呼叫，格式退回 0，provider 錯誤 0，USD 0.312。開跑前帳本累計 USD 59.11（含試跑），加上 25 為 84.11 | 等執行跑完。報告 PR 目前還沒開（UNKNOWN 何時完成） |
| E5 報告的偏差段 | 報告裡的「偏差」一節 | 待寫（由上面的子 session） | 必須寫到：①N4 的讀法；②N5：`calls[].tick` 是生效 tick；③AO 用的是 `4ab7bc10`（N2 當時還沒修，但 offline 路徑走不到 N2） |
| E5 AO-L（H8d） | AO-L 結果 | N2 已修（`24c2dce9`），可以跑 | 等 AO 的實際花費確定後再決定；累計不能超過 USD 89 |
| F5 [#659](https://github.com/Polalalabear/amidst/issues/659) 論文 | 論文 md → PDF | E3 章節已合併（#693，`docs/paper/F5_PAPER_DRAFT.md`） | E5 章節等結果；#659 仍是 `blocked` |
| E4 | 探索性附錄 | 暫停（D356）。`claude/feat-e4` `f8f21afa` 保留 | — |

##### 3.2 即時模式（LIVE，8791）

| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| Codex PR [#690](https://github.com/Polalalabear/amidst/pull/690)（Draft）：#676 顏色修正、#677 的四個後端欄位、三個小修正 | 審查 APPROVE（E5 後合併） | 會改變 B1 快照的來源雜湊（`scripts/evaluation/e3_cases/baseline.py:55-59`），**E5 結束前不能合併**。合併後 #676 不能關閉：主因可能是 gate 4 m／growth 0，要等 #589／R2 |
| [#675](https://github.com/Polalalabear/amidst/issues/675) LIVE 開放 Agent 決策（Codex） | 啟動和開關已驗證 | 資料外傳暫停到 E5 結束（D359） |
| [#677](https://github.com/Polalalabear/amidst/issues/677) LIVE UI/UX | 已合併（#695 `ada45f31`），issue 已關閉 | 還沒部署到 8791。後續：#690 合併後，前端改讀 `gate_m_effective`／`reject_reason`／`cand_id` |
| [#672](https://github.com/Polalalabear/amidst/issues/672) LIVE 追其他目標 | 設計在假設文件 §0.2 | 排在 E5 之後 |
| [#633](https://github.com/Polalalabear/amidst/issues/633) LIVE 改 workbench-v2 風格 | — | 11-25 之後 |

##### 3.3 研究紀錄、報告與發表

| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| 海報與簡報 | 已完成。使用者選了架構圖 ③ components。交付資料夾見 §5 | 結果數字等 E5；pptx 還沒在 PowerPoint 或 Keynote 開過 |
| open-slide 原始專案 | 在 `local/evidence/presentation-pack-20261123/slides/open-slide/`（資料夾，SHA-256 不適用） | `node_modules` 約 269 MB，不再需要時可以刪（使用者執行） |
| [#479](https://github.com/Polalalabear/amidst/issues/479) 報告素材、[#674](https://github.com/Polalalabear/amidst/issues/674) 更新紀錄 | 持續追加 | — |

##### 3.4 8785 demo

- 8785 的 pin 還在 `c988ed60`（使用者 2026-11-23 核准；gate `local/evidence/gate-pin-20261123/RESULT.txt`，SHA-256 `1f13c82beb36704e7ca653dd0b7041887ce290b2a17f93134654dea9496b92d2`）。
- main 已經前進到 `ada45f31`。要換 pin 就跑 gate，再請使用者核准，不能自己改。

##### 3.5 Codex 的任務

- 目前沒有可以做的工作，等 E5 結束；之後第一件事是合併 #690，再做 #675。
- [#623](https://github.com/Polalalabear/amidst/pull/623)、[#612](https://github.com/Polalalabear/amidst/issues/612)、[#594](https://github.com/Polalalabear/amidst/issues/594)：11-25 之後。
- [#589](https://github.com/Polalalabear/amidst/issues/589)、[#574](https://github.com/Polalalabear/amidst/issues/574)、[#566](https://github.com/Polalalabear/amidst/issues/566)：被擋住（#566 目前沒有 `blocked` 標籤）。

##### 3.6 流程與整理

| 工作 | 卡在哪裡 |
| --- | --- |
| PROGRESS 補列 #656–#696、CODE_DOC_MAP | 大更新，之後再做 |
| `real-e2e.mjs` 多畫面格數 | 未排定 |

#### 4. 新協調者的第一件事

1. 等 E5 AO 子 session（`local_073d1ce8-8722-42b4-b1c2-1d65cdac1305`） 回報，看報告 PR，派 Sonnet medium 審查；評分程式（complex code 邊界）有疑慮就交給 Opus。通過且 CI 綠就合併，在 #93 記 D362，在 #674 追加一則。
2. 依 AO 的實際花費決定要不要跑 AO-L（累計 ≤ USD 89）。
3. E5 結束後：合併 #690，請 Codex 做 #675；論文補 E5 章節，海報和簡報填入數字；8785 換 pin 要經過 gate，並由使用者核准。

#### 5. LOCAL 產物

`local/evidence/presentation-pack-20261123/deliverable/`：約 8.9 MB，18 個檔案；各檔 SHA-256 在 `deliverable/README.md`（該 README 的 SHA-256 `9e731177cc361aa765910410b2d402a1aea90a63fb67b9fadbaadc9e322e8f55`）。可以用 `local/evidence/presentation-pack-20261123/scripts/` 重建。

| 項目 | 內容 |
| --- | --- |
| `slides/amidst_slides.pptx`、`slides/amidst_slides.pdf` | 可編輯簡報（python-pptx 原生物件）和 PDF |
| `poster/poster_A1_academic.pptx`、`poster/poster_preview_quicklook.png` | 海報和預覽 |
| `images/` | 12 張圖：架構圖 ③ components、決策流程圖、五張決策點圖、兩張八鏡頭畫面、鏡頭覆蓋圖、兩張工作台截圖 |
| `README.md` | 檔案清單與 SHA-256 |

上一層 `local/evidence/presentation-pack-20261123/`（資料夾，SHA-256 不適用）另有 `images/`、`poster/`、`scripts/`、`slides/`（含 open-slide 專案）。決策點圖和場景圖的來源是 `local/evidence/e3-figures-20261123/`（#670）。

---

<a id="h20261124"></a>

## 2026-11-24（原 docs/agents/COORDINATOR_HANDOFF_20261124.md）

### 協調者交接（2026-11-24）

> **新的協調者對話全程用繁體中文回覆（D255）。**
> - 依據：`main` @ `edb642c67f0b87cd2dc80c3ab41bb2f920093c85`（#707 合併），2026-11-24 約 16:00（Asia/Taipei）的快照。
> - 現行決策在 [#93](https://github.com/Polalalabear/amidst/issues/93)（下一個 D 號是 **D370**），更新一律追加在 [#674](https://github.com/Polalalabear/amidst/issues/674)。
> - 上一份：`docs/agents/COORDINATOR_HANDOFF_20261123c.md`。**任務板寫的期限是 2026-11-25。**

#### 1. 一句話現況

E5 已結束並合併；Codex 的 demo 與 LIVE PR 都已合併。離驗收還差：8785 gate 與換 pin、#710（預設介面的 3D）、論文 E5 章節、海報與簡報的數字、README、重走 AC1–AC8。

#### 2. 今天的決策與合併

| 決策 | 內容 | 合併 SHA |
| --- | --- | --- |
| D362 | #698 E5 AO 報告 | `d52ce2f0` |
| D363 | #706 E5 AO-L（H8d）；E5 結束 | `ca635c2e` |
| D364 | #690 LIVE 修正 | `f7fdc74e` |
| D365 | #703 LIVE Agent 離線接線、契約（#675 的程式部分） | `d9ebacb5` |
| D366 | #705 LIVE 改 workbench-v2 風格（使用者看過截圖） | `21d6f4c5` |
| D367 | #623 8CAM run、display_estimate（使用者看過截圖） | `f8b1a454` |
| D368 | #709 UNKNOWN 原因文字、real-e2e B05（使用者看過服務畫面） | `579b431a` |
| D369 | #707 LIVE detector 測試 fixture | `edb642c6` |
| — | #701 ApiGuard 快取計費（`a9b45d38`）、#702 E5 數字總表（`595ec837`） | 見左 |

使用者決定：AO-L 費用上限由 7 改 8.5；#705 先修提示再合；#623 先合、文字後修；3D 在新版前台看不到的問題記下來後續改或交 Codex（#710）。

#### 3. 所有工作（依類型）

##### 3.1 WP5 與 Agent 決策
| 工作 | 預計產出 | 進度 | 卡在哪裡 |
| --- | --- | --- | --- |
| E5 [#684](https://github.com/Polalalabear/amidst/issues/684) | 報告、評分 | 完成：H8a、H8b 不成立；H8c 無法判斷；H8d 不成立（K=1）。`docs/operations/E5_REPORT_20261123.md` | 只適用於這個 A-open 設計和 E3 的 16 段 |
| 預算 | 累計 ≤ USD 90 不用問（D359） | ApiGuard 帳本 80.18（未計快取折扣的上界）；使用者 11-23 看到的 OpenAI 帳單是 35.72（11-08 至 11-23，不含之後的 AO-L） | 每次仍要先 dry-run |
| E4 [#681](https://github.com/Polalalabear/amidst/issues/681) | 探索性附錄 | 暫停（D356） | — |

##### 3.2 即時模式（LIVE，8791）
| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| 部署 #690／#695／#703／#705 到 8791 | 已合併，**都沒有部署** | 要使用者同意重啟 |
| [#675](https://github.com/Polalalabear/amidst/issues/675) Agent | 離線程式完成 | 真實模型驗證未做；要使用者核准外傳影格 |
| [#676](https://github.com/Polalalabear/amidst/issues/676) 藍衣失聯 | 修正與合成診斷已合併 | 原事件原因 UNKNOWN。E5 已結束，#589 的 E5 閘門已解除；剩 runtime 設定未核定：可由使用者核准契約 §4.5 的 UNKNOWN 回退（遠距候選走 NEEDS_CONFIRM，人工確認），見 `docs/operations/LIVE_RELOCK_R2_PLAN_20261124.md` |
| [#633](https://github.com/Polalalabear/amidst/issues/633) | Codex 部分已合併 | 工具面板蓋住場景標籤；鏡像退役 |
| #677 後續：前端讀 `gate_m_effective`／`reject_reason`／`cand_id` | 契約與 fixture 已在 main（#703） | 前端未接；#677 已關閉，要另開 issue |
| [#589](https://github.com/Polalalabear/amidst/issues/589)、[#574](https://github.com/Polalalabear/amidst/issues/574)、[#566](https://github.com/Polalalabear/amidst/issues/566)、[#672](https://github.com/Polalalabear/amidst/issues/672) | blocked | 11-25 之後 |

##### 3.3 研究紀錄、報告與發表
| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| 論文 [#659](https://github.com/Polalalabear/amidst/issues/659) | E3 章節完成；引言、方法、E5、結論是佔位 | **E5 已結束，還沒派人。** issue 標籤仍是 blocked＋in-progress，要更新 |
| 海報、簡報 | 版面完成，待填清單在 `local/evidence/presentation-pack-20261123/deliverable/README.md` 的「待填項目」 | **還沒派人**；封面的姓名、老師、系所要使用者提供；pptx 沒在 PowerPoint／Keynote 開過 |
| 數字總表 `docs/evaluation/E5_NUMBERS_TABLE_20261124.md` | AO 已收 | AO-L 未收 |
| 簡報的「F1 0.887 對 0.518」 | 出處已查到：W1 的 IoU 準則（`docs/evaluation/E3_SCORER_RECOMPUTE_20261122.md`「W1 整體（422 格）F1」表，`terra_vision_free`／`rule` 多數決；E3 報告 §1 也引用）。0.957 對 0.523 是主準則 | 填數字時要寫明是哪個準則 |
| README | 最後修改 2026-11-22，狀態段是 11-20 | 沒有 E3、E5 結論，W3／E3 的「下一步」過時，中英文都要改 |

##### 3.4 8785 demo
| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| 換 pin（[#700](https://github.com/Polalalabear/amidst/issues/700)） | 第一、二次 FAIL；第三次由 Codex-W 進行中，目標 `edb642c6`，結果在 `local/evidence/gate-pin-20261124-r3/`（執行中，SHA-256 未定） | 全 PASS 後要**使用者核准**。pin 仍是 `c988ed60` |
| [#710](https://github.com/Polalalabear/amidst/issues/710) 新版前台 3D | Codex-L 進行中（`codex/feat-workbench-3d`） | 合併前要看**預設網址**的截圖；不在第三次 gate 的目標裡，納入 pin 就要再跑 gate |
| 8785 服務 | 今天兩次檢查都沒有在聽 | 原因 UNKNOWN，還沒查 |
| [#612](https://github.com/Polalalabear/amidst/issues/612)、[#594](https://github.com/Polalalabear/amidst/issues/594) | 部分完成，保持開啟 | #612 等 #710；#594 的 B-05／r005-8CAM 來源 UNKNOWN |
| AC1–AC8 | 沒有在新 main 上重走 | gate 過後做 |

##### 3.5 流程與整理
| 工作 | 進度 | 卡在哪裡 |
| --- | --- | --- |
| CI 加入 `tests/live_mode/` | 子 session `local_4dc0df1a-8f32-4328-bb9f-ff39fee0f3cf` 進行中，會開 Draft PR（分支 `claude/feat-ci-live`） | 不擋驗收。它回報給上一個協調者，新協調者要自己查 |
| 磁碟 | 16:00 時 9.12 GiB，gate 進行中會再降 | `local/` B 類清理未決定：Sonnet 驗證在 #486（cx7r 的 RGB 約 1 GiB 有逐檔相同的副本）。刪除要 Opus 看原始證據、使用者授權並執行 |
| PROGRESS、CODE_DOC_MAP | 草稿與差異清單已有（#674、#702） | 大更新，之後做 |
| CLAUDE.md／AGENTS.md 的交接指向 | 仍指向 `20261123c`（CLAUDE.md 已查） | 下一個文件 PR 改成本檔 |
| #93 的 pin 列連結寫成 #702 | 應為 #700 | 下次同步改 |

##### 3.6 Codex 與 Argon
- **Codex-W**：gate 第三次（#700）。**Codex-L**：#710。其他：#699（#701 已合併）、#704（#702 已合併，仍 needs-claude-review）、#680 仍 OPEN，#612／#594 仍帶 needs-claude-review，標籤待更新。
- **Argon**：#479。

#### 4. 資料要一次補齊嗎（協調者建議，使用者還沒決定）

E5 數字已凍結，不會因 gate 或 #710 改變。所以分兩批：
1. **現在**：把 AO-L 補進數字總表（F1 的兩個準則寫清楚），再由總表一次填論文、海報、簡報。
2. **gate 與 #710 定案後**：只補截圖、Demo 錄影、最後的 pin SHA 和 README 的 demo 段。

`main` 每次合併就更新；8785 實際跑的是 pin。README 建議在論文數字定稿後開一個文件 PR。

#### 5. 這一輪協調的錯誤（避免重複）

- 對審查 session 寫「使用者已看過 #709 截圖」並要求合併，當時不是事實；訊息被權限檢查擋下，之後改成只審查，使用者看過服務畫面才合併。
- #690 只憑 APPROVE 與 CI 綠合併，但 CI 不含 `tests/live_mode/`，造成 pytest 回歸（#707 修）。之後又誤說起因是 #703。
- #623 請使用者核准時，沒說 3D 圖是 `?ui=legacy`、服務是 fixture 版 Demo。
- #623 的 Codex 指示寫「不起服務」，Codex-W 因此中斷第二次 gate。
- E5 結束後沒有馬上派論文與海報。

#### 6. 工作方式

- 實作、審查交子 session（CLAUDE.md 分級）；使用者要求時直接在主對話做。要貼的文字放 code block；終端機指令每條只給一次；GitHub 用 `gh`。
- 審查過且 CI 綠才用 merge commit 合併（D305），LIVE 的 PR 另看 `tests/live_mode/` 結果。UI 先給使用者看截圖，要說明是哪個網址、哪種服務。pin、部署、刪除、外傳影格要使用者同意。
- 寫入 session 最多三個；目前 Codex-W、Codex-L、CI session 已是三個。第三個開工前要 ≥ 9 GiB，程式保護 8 GiB，剩 5 GiB 就停。
- 只有使用者自己說的話是授權；不能替使用者轉述沒說過的同意。

#### 7. 新協調者的第一件事

1. 查 #700（gate 第三次）、#710、CI session 的 PR。
2. 派論文 E5 章節、海報與簡報的數字（期限最近；寫入名額滿時先等一個結束）。
3. gate 全 PASS 就請使用者決定：先用 `edb642c6` 換 pin，還是等 #710 後重跑 gate。
4. 換 pin 後重走 AC1–AC8，再請使用者驗收。

#### 8. LOCAL 產物

| 路徑 | 說明 |
| --- | --- |
| `local/evidence/e5-20261123/` | E5 AO；MANIFEST SHA-256 `f2afea147029affad9bcf5718b94eab29ee16163e9fc6938b6e0ffeecd2a5f3e`；重跑要付費 |
| `local/evidence/e5-aol-20261124/` | E5 AO-L；MANIFEST SHA-256 `5b389e3bb5733e5ad2277fee5586ca3505758d1c85093b64981792a2cb6e5fe8`；重跑要付費 |
| `local/evidence/gate-pin-20261124/` | gate 第二次；RESULT SHA-256 `693f7642e7541839dffc5ea43772238b1c84687e97002f7f202d7c76b053c365` |
| `local/evidence/shots-demo-fixes-20261124/service/` | #709 服務畫面 3 張；雜湊在同資料夾 `SHA256SUMS`；可重拍 |
| `local/evidence/shots-705-20261124/`、`local/evidence/shots-623-20261124/` | 截圖；雜湊在各自的 `SHA256SUMS`；可重拍 |
| `local/evidence/presentation-pack-20261123/deliverable/` | 海報與簡報；README SHA-256 `9e731177cc361aa765910410b2d402a1aea90a63fb67b9fadbaadc9e322e8f55`（2026-11-24 審查時重算相符） |

---

<a id="h20261124b"></a>

## 2026-11-24b（原 docs/agents/COORDINATOR_HANDOFF_20261124b.md）

### 協調者交接 2026-11-24（下午，第二份）

快照時間 2026-11-24 16:40。接在 [20261124](#h20261124) 之後，只寫變動；**之後的狀態以 #93、#674 和各 PR 為準**。新的協調者全程用繁體中文回覆。

#### 0. 版本與環境

- `main` = `6afb4f7614375abf67d3d640fb8abfb6585b0527`（含 #712、#713）。下一個決策號 **D373**。
- 8785 pin 仍是 `c988ed60`，8785 沒有在聽（原因 UNKNOWN）。8791（PID 45196，舊版 LIVE）、8795、8796 在聽，都沒動。
- 磁碟 9.8 GiB。第三個寫入者開工前要 ≥ 9 GiB；程式保護 8 GiB；剩 5 GiB 停。
- OpenAI 帳本上界 USD 80.18，另有 #686 的 USD 0.110643 是否已計入請看帳本；使用者要求用到 90 才叫（D372）。

#### 1. 本段新決策

| 號 | 內容 |
| --- | --- |
| D370 | E5 數字現在就填進論文、海報、簡報 |
| D371 | 合併 #712（`384e9327`）、#713（`6afb4f76`） |
| D372 | 同意把 gate 的 Agent 補跑所需合成影格送 OpenAI；費用用到 USD 90 前不用問。不含 #675 的 LIVE 外傳 |

封面的姓名、學號、指導老師、系所由使用者自己填。疑點不改系統，寫進論文討論，期限後再做。

#### 2. 工作（依類型）

##### 8785 demo 與驗收

| 項目 | 預計產出 | 進度 | 卡在 |
| --- | --- | --- | --- |
| #700 gate 第三次 | edb642c6 的 gate 全 PASS | `local/evidence/gate-pin-20261124-r3/RESULT.txt`（SHA-256 `9f8135c67a84ffa4fb5212bfbfd000dfba5c207e5ec27f14c3738e0995667b01`）只缺三項 Agent 重播的離線收據，其餘全 PASS | Codex-W 補跑 r3b（進行中，`local/evidence/gate-pin-20261124-r3b/`，尚無 RESULT） |
| 換 pin | 8785 換到新版 | 未開始 | gate 全 PASS；再問使用者：先用 edb642c6，或等 #714 合併後重跑 |
| #714（#710）前台 3D 與位置估計 | `/scene3d/`、估計與 UNKNOWN 標示 | head `e008d715`，CI 綠，Sonnet 複審 APPROVE（程式／Node 層） | 正式 launcher 另一 port 實跑、截圖給使用者看過才合併 |
| AC1–AC8 重走、README 中英文 | 驗收紀錄；README 補 E3、E5 結論 | 未開始 | 換 pin |

#714 的已知可見行為：2D 上下方向翻轉；多數播放時間估計顯示 UNKNOWN（最後觀測 A4-1 49.8 s、B4-1 41.8 s）；半徑圓可能被 SVG 裁切；`estimate_reason` 由 null 改 `EST_XY_MISSING` 要在 PR 註記。Opus 裁決留言的 effort 記為 low 是填錯，實際 UNKNOWN。

##### 研究紀錄與報告

| 項目 | 預計產出 | 進度 | 卡在 |
| --- | --- | --- | --- |
| #715 論文與 E5 數字總表 | 論文完整草稿 | head `3dcd505e`，CI 綠；Sonnet 審查 NEEDS_CHANGES：數字 2325 列 0 差異，只缺討論文字 | paper session 修改中（§4.6 第 9–12 點、§5、影格來源）；之後 review-715 複審，APPROVE＋CI 綠就合併 |
| 海報、簡報 | LOCAL PPTX／PDF | 完成，另有小修（影格來源寫法、規則 Agent 敘述、表 1 右緣） | poster session 修改中；沒用 PowerPoint／Keynote 開過 |
| 設計問答 | [DESIGN_QA_20261124](../evaluation/DESIGN_QA_20261124.md) | 本 PR | 審查 |
| H9、ReID、查找實驗 | 新的預先登記 | 未決定，期限後 | 使用者 |

研究結論（不變）：單張辨識 Agent 較好（H5 有條件成立）；接進追蹤未得到支持（H1、H8a、H8b、H8d 不成立，H8c 無法判斷）。

##### 即時模式／流程

- LIVE 外傳（#675）沒有同意；E3 預登 §7.7 真 LIVE 驗證沒跑。
- #713 後 CI 會跑 `tests/live_mode`，但瀏覽器類與 N6 的測試在 CI 仍會跳過。
- #699、#704、#680、#612、#594 仍 OPEN，標籤待整理。#676／#589 §4.5 UNKNOWN 回退：使用者沒有回答，**不算核准**。

#### 3. LOCAL 產物

| 路徑 | SHA-256 | 重建 |
| --- | --- | --- |
| `local/evidence/cx-h6-8cam-20261123/`（29 檔＋manifest，DELIVERY_MANIFEST） | `79ab85849c6c5a405f9ab950a1b477d41cb078e7da9382c60f6d9f90eb443a0e` | 付費收據，不可免費重建 |
| `local/evidence/presentation-pack-20261123/deliverable-e5-20261124/poster/poster_A1_academic_e5.pptx` | `3bffe1c9c1a48244b74ea828f0ff2e5054c1f3e5ce60ae42466280077135ea93`（小修前） | 可由 session 腳本重做 |
| 同上 `slides/amidst_slides_e5.pptx` | `09dc0c9bc292a4e3f75ce8c7949eae6f1158c22ee59073832cf9b9944d86a5e9`（小修前） | 同上 |
| 同上 `slides/amidst_slides_e5.pdf` | `4a6886d5fde3b91783ef9ea8ffaca3be8177f324abedb7d6b597cae1e6622006`（小修前） | 同上 |

小修後的雜湊以該資料夾 README 為準。

#### 4. 可續用的 session

| 用途 | id |
| --- | --- |
| 論文 #715 | `local_4671e5fe-f891-4d3f-a1cc-b2c086eb8b09` |
| #715 審查 | `local_5e831abb-6e81-46e6-8297-5f1159c3119c` |
| #714 審查 | `local_746d85c1-25fd-45c0-ab1f-994f340618de` |
| 海報、簡報 | `local_8e66df39-66b1-482c-95d5-e2efb440ed42` |
| GitHub 同步（Haiku） | `local_0db3f8d5-a5dd-417c-a570-fbe36e21625a` |

#### 5. 第一件事

1. 看 #715 新 head 與 CI，請 review-715 複審，APPROVE 就 merge commit。
2. 派 #714 實跑與截圖（正式 launcher、另一 port、預設網址、無頭），截圖給使用者看。
3. 等 r3b；全 PASS 就問換 pin 時機。
4. 看海報小修後的預覽。
5. 換 pin 後重走 AC1–AC8、更新 README、請使用者驗收。

#### 6. 2026-11-24 22:00 停工重排（取代 §2、§5 的派工）

- **使用者指示（D375、D376）**：先討論計畫，停下所有工作；Claude 額度將滿，工作全部開給 Argon 與 Codex，Claude 只審查，等全部交件後**一次審查**。（D377 改為分四批，見 E6_PLAN「審查批次」；批次內仍一次送審。）
- **費用**：使用者在 API platform 讀到的總花費是 **USD 38.17**（取代帳本上界 81.75）。調整檔 `local/evidence/api-usage/RECONCILIATION_20261124.json`（SHA-256 `a1bb6e9dabb1bce1eebef8934a294dec4c196a12c2722b93752aa86fb43c4635`）；各帳本列沒有改寫。累計 = 38.17 ＋ 之後新列；距 90 剩 51.83。
- **已停**：子 session 全部閒置；8797（#714 實跑）已關、它的 clone 已刪。8791、8795、8796 沒動。#714 截圖在 `local/evidence/screenshots-714-20261124/`（未完成，README 未寫；12 張，9 張＋3 張 tmp，MANIFEST SHA-256 `24a38dfcdec6893f7bba6b4efa87c67e8bb91d302166e4bef2c2ce4e15b61560`；由 #720 補 README）。
- **已合併**：#715、#716（`10a1384c`、`a3293368`）。#716 合併時沒含第 7 節（`c7c15566`），由本 PR 補。
- **gate r3b**：FAIL／NOT_READY（A4-8CAM 缺 9、B4-8CAM 缺 10 筆一字不差收據；Agent 採用已觀察到）。待使用者決定標準。
- **不做／暫停**：E4 #681、LIVE 外傳 #675、#589／#574／#566、#633、#672、#630、#598、A、B 跨規格重跑、解析度變因。期限 2026-11-25 後再議。
- **新派工**（D377：#717–#720 `ready`，#721 仍 `blocked`）：#717（Codex 答案表重算）、#721（Codex E6 實作）、#718（Argon 預登與劇本）、#719（Argon 論文與 README）、#720（Codex 8785 收尾）。計畫見 [E6 計畫](../evaluation/E6_PLAN_20261124.md)。

---

<a id="h20261126"></a>

## 2026-11-26（原 docs/agents/COORDINATOR_HANDOFF_20261126.md）

### 協調者交接 2026-11-26

接在 [20261124b](#h20261124b) 之後。**之後的狀態以 #93（工作清單與 D 決策）、#674（更新紀錄）和各 PR 為準**。新的協調者全程用繁體中文回覆（D255）。審查由另一個對話接手。

#### 0. 版本與環境

- `main` = `10a1384c`（#715、#716 已合併）。下一個決策號 **D382**。
- 8785 pin `c988ed60`（`local/demo-pin.json`，2026-11-23 核准），8785 沒在聽。8791（PID 45196，舊版 LIVE）、8795、8796 在聽，都沒動。
- 磁碟約 10 GiB。第三個寫入者開工前要 ≥ 9 GiB，程式保護 8 GiB，剩 5 GiB 停。
- 費用：使用者讀 API platform 的 **USD 38.17**（D375，`local/evidence/api-usage/RECONCILIATION_20261124.json`，SHA-256 `a1bb6e9dabb1bce1eebef8934a294dec4c196a12c2722b93752aa86fb43c4635`）＋之後新帳本列；上限 90。之後沒有新的付費呼叫。

#### 1. 本段決策（D376–D381，原文在 #93）

| D | 內容 |
| --- | --- |
| D376 | 工作全開給 Codex 與 Neon（原 Argon），Claude 只審查 |
| D377 | E6 方向：P1 去錨定對原 AO、P2 選定 Agent 組對 **B1**（Holm 校正，四元件取最大 p）；R-N（規則決策＋中性追蹤器）為機制與次要；3 段診斷和 12 段正式資料嚴格分離；**審查分四批**，每批 Codex、Neon 互審後一次送審 |
| D378 | Argon 改名 **Neon**；標籤 `owner:neon`；舊分支與紀錄不改寫 |
| D379 | 移機順序：第 1 批審查 → 盤點要搬的檔案（含 12 份 `.blend`，只列不刪）→ 核對可攜性 → 搬移驗證 → 才做 laya／本地模型。搬完後 Neon 可讀寫本機，和 Claude、Codex 同等級 |
| D380 | 媒介：使用者的雲端硬碟，只當私人搬移（不分享）；Claude Code 仍是最終審查者，像開源維護者一樣**從 GitHub 讀 PR／issue／決定**來審 |
| D381 | gate 標準 B：被採用的 Agent 回答全部有一字不差收據即 PASS；因 `PROVIDER_UNAVAILABLE` 沒收據的要明確退回規則並寫成記錄行（`... PASS`，不寫 FAIL） |

#### 2. 工作（依類型；預計產出／目前進度／卡住）

##### WP5 與 Agent 決策（E6、E7）

| 工作 | 預計產出 | 目前進度 | 卡住 |
| --- | --- | --- | --- |
| #717 → PR #723（Codex） | 16 段答案表、錯誤歸因、AO 描述性拆解、R-N | head `30563f0f`，CI 綠，Neon APPROVE（只審 GitHub，LOCAL 數字未重現） | 等 Claude 第 1 批審查；**PR 寫的輸出資料夾 `local/evidence/cx-e6-717-20261124/` 在 Mac 上找不到（SHA 不適用：資料夾不存在）**，審查時要 Codex 補或說明 |
| #718 → PR #726（Neon） | E6 預登草稿、12 段劇本規格、資料分離自動檢查 | head `9e6c54b6`，CI 綠；Codex 兩輪 NEEDS_CHANGES 後已修 | **等 Codex 第三輪複審**，之後進第 1 批 |
| #721（Codex） | 去錨定／歷史／摘要實作與 3 段診斷 | blocked | 等 #718 合併、付費與外傳影格同意（第 2 批） |
| #727 E7（新） | 本地決策器（Qwen-VL 類、laya）延遲與決策探索 | blocked-user | 等 #598 移機完成 |
| #684 E5 | — | 已判定（H8a、H8b、H8d 不成立，H8c 無法判斷）；事後檢查在留言 | 只剩收尾，可在 E6 後關 |

##### 研究紀錄與報告

| 工作 | 預計產出 | 目前進度 | 卡住 |
| --- | --- | --- | --- |
| #719 → PR #724（Neon） | 論文收尾、中英文 README（E3／E5） | head `32218a1a`，CI 綠，Codex APPROVE | 等 Claude 審查；**期限 11-25 已過**，可先審先合 |
| #659 F5 論文 | 交付資料夾定稿 | 進行中 | 依 #724 合併後收 |
| #722（協調者） | E6 計畫、交接、索引、進度導覽到 #722、本交接 | head 見 PR，CI 綠 | 第 1 批審查 |

##### 8785 demo

| 工作 | 預計產出 | 目前進度 | 卡住 |
| --- | --- | --- | --- |
| #720 → PR #725（Codex） | 零付費檢查、20 題 Q1–Q3 功能驗收（14/20） | head `d8ebdeb1`，CI 綠，Neon APPROVE | 等 Claude 審查；**輸出資料夾 `cx-demo-720-20261124/` 在 Mac 上找不到**；截圖與實跑未驗證 |
| #710 → PR #714（Codex） | 新版前台接上 3D 與 display_estimate | head `e008d715`，CI 綠，程式層 APPROVE | 截圖要先給使用者看（URL、服務種類）；#714 截圖在 `local/evidence/screenshots-714-20261124/`（MANIFEST SHA-256 `24a38dfcdec6893f7bba6b4efa87c67e8bb91d302166e4bef2c2ce4e15b61560`），README 由 #720 補 |
| #700 換 pin gate | 依 D381 標準 B 判定 | r3b（`edb642c6`）依新標準證據足夠，只當參考 | 第 1 批合併後定目標 commit，**在新 commit 重跑 gate**；換 pin 由使用者核准 |

##### 流程與整理

| 工作 | 預計產出 | 目前進度 | 卡住 |
| --- | --- | --- | --- |
| #598 Windows 移機 | 檔案盤點、可攜性核對、快照 S1、Windows 兩遍一致 | blocked-user，計畫在 issue 本文 | 等第 1 批合併 |
| 快照 S1 規則（建議，未寫進 #598） | Windows 唯讀快照；`AMIDST_ARTIFACTS`、`AMIDST_API_USAGE_DIR` 指到快照外；`demo-owned-v1/state/` 不搬（`state_root` 沒有環境變數可改）；要改就在 Mac 走 PR 再發 S2 | 已向使用者說明 | 使用者尚未確認是否寫進 #598 |
| 跨平台風險 | — | 已查 | repo 沒有 `.gitattributes`（Windows CRLF 會改 SHA）；3 個 git 符號連結（`docs/DEVELOPMENT_RULES.md` 等）；`local/` 最長路徑 205 字元。S1 前要處理 |
| 暫停到 11-25 後的項目 | — | 仍暫停 | #681、#675（`blocked-user`）、#589、#574、#566、#633、#672、#630；使用者還沒說要恢復 |

##### 即時模式

全部暫停（見上一列）。8791 仍是舊版，未部署 #703。

##### Codex 與 Neon 的任務

- Codex：#723、#725 等審查；#726 第三輪複審進行中；補兩個缺少的 LOCAL 輸出資料夾。
- Neon：#724、#726 等審查。搬完前 Neon 只用 GitHub。

#### 3. 審查交接（給審查對話）

- **第 1 批**：#722、#723、#724、#725、#726（等 Codex 第三輪 APPROVE），#714 可同批。依 D377，批內一次送審；依 D305，審查通過＋CI 綠就用 merge commit 合併並刪分支，但 **UI 先給使用者看截圖**、**換 pin 要問**。
- 審查方式（D380）：從 GitHub 讀 diff、跑 focused tests；PR 要附可重跑指令、彙總數字與 LOCAL SHA-256。抽查 LOCAL 時一次只取單一檔案。Neon 的 APPROVE 不含 LOCAL 數字重現。
- 合併後依序：定 pin 目標 commit → Codex 重跑 gate（標準 B）→ 使用者核准換 pin → #598 盤點與 S1。

#### 4. 待使用者決定

1. 快照 S1 規則是否寫進 #598。
2. 第 1 批合併後，8785 要釘哪個 commit（是否含 #714）。
3. 第 2 批的付費與外傳影格（#721）。
4. E7 是否微調（要用 GT 當標籤，牽涉 GT 隔離）；下載權重需同意。
5. 暫停項目何時恢復；#676、#589 §4.5。

#### 5. 第一件事

讀 #93 最新 D376–D381 與本文 §2，確認 #726 的 Codex 第三輪結果；等使用者說開始，就照 §3 審第 1 批。

---

<a id="h20261127"></a>

## 2026-11-27（原 docs/agents/COORDINATOR_HANDOFF_20261127.md）

### 協調者交接（2026-11-27）

快照時間 2026-11-27 約 08:40（+08:00）。main = `a90a7884`；8785 pin = `5727fc9a`；下一個決策號 **D399**。之後的狀態以 [#93](https://github.com/Polalalabear/amidst/issues/93)、[#674](https://github.com/Polalalabear/amidst/issues/674) 為準。新的協調對話**全程用繁體中文**（D255）。

#### 0. 先讀

1. 本文件。
2. #93 本文第 00 節，以及 D388–D398 留言。
3. #674 最新幾則。
4. 規則：`CLAUDE.md`、`AGENTS.md`、`CLAUDE.local.md`。

#### 1. 角色與規則（本段新增）

- **D389**：審查通過＋CI 綠，就由 Claude 用 merge commit 合併並刪分支。`--match-head-commit` 一定要用 `gh pr view --json headRefOid` 查到的完整 SHA。
- **D391／D396**：Codex 額度不足時由 Claude 代做，包括 E6 錄製。E6 是 LIVE WebGL 無頭錄製，不是 Blender 渲染。#732 的前提 G1–G5 全部由 Claude 做。
- **D395**：刪除和嚴重到需要使用者看的事以外，指令由 Claude 直接執行，包括快轉 `~/amidst`、以已審過的 gate 執行 `demo_pin.py approve`、重啟 8785／8791、合併。8785 的啟動指令是 `cd ~/amidst && ./start_445_demo.command --port 8785`。
- **D397**：費用累計 USD 38.17＋新帳本列，不超過 90 就不用問。每次先做 ApiGuard dry-run 並記帳。
- **額度**：使用者是 Pro 方案。五小時額度到 90% 時，用 scheduled task 排在重置後約 5 分鐘叫醒協調對話。叫醒後要**繼續把工作做完**，不只是審查。
- **effort**：子 session 的 effort 不能高於協調對話自己的。協調對話要設成 high，派出去的 session 才會是 high。

#### 2. 工作（依類型）

##### 2.1 實驗：E6／E7（#732 主線）

| 工作 | 預計產出 | 進度 | 卡在哪裡 |
|---|---|---|---|
| #732 FEAT-EXP-RUN（PR [#741](https://github.com/Polalalabear/amidst/pull/741)，`claude/feat-exp-run`，Draft） | E6 12 段＋3 段診斷錄製、API 各組、評分、統一分析、Colab 結果 | 第 1 輪零費用部分完成：AO-L 延遲歸零 0.2481 → 0.5741（仍低於 B1 0.7587）。G5 Colab 包建置器 `d0d47a01` 已審查通過（D392 白名單） | 等 G1–G4 |
| G5 E7 Colab 包（舊 16 段） | `local/evidence/e7-colab-pack-20261127/`（4253 檔、531 請求） | 完成，Sonnet＋Opus 審查通過 | **等使用者**上傳私人雲端硬碟，在 Colab 執行 Run All |
| G3 #721 各組（PR [#743](https://github.com/Polalalabear/amidst/pull/743)，`claude/feat-e6-arms`） | 去錨定、加歷史、加摘要三組的請求建構，以及 K=1 小型診斷 | Opus 定案 NEEDS_CHANGES（D398 四點）。原 session `local_1d45dee9-095e-4ecc-98c4-4cf350c52e1e` 修改中 | 修完 → Sonnet 複審 → 付費跑診斷（上界約 USD 7.88） |
| G1＋G2 E6 路線與干擾者（`claude/feat-e6-routes`） | 設計文件 `E6_ROUTES_DESIGN_20261127.md`、`configs/evaluation/e6_routes_v1.json`、錄製器支援、1 段診斷錄製 | session `local_7b1915af-6532-483a-92bc-33210b59f514` 進行中，還沒開 PR | 設計要 Opus 審過才能錄 12 段正式資料 |
| G4 `run_all.sh` Stage 2／3 接線 | 一鍵執行：3 段診斷 → 自動凍結 → 12 段正式 | 未開始 | 等 G1–G3 |

##### 2.2 8785 demo 與 LIVE（#735）

- 8785 已換 pin 到 `5727fc9a`（含 #714 前台 3D），gate r5 是 `local/evidence/gate-pin-20261127-r5/RESULT.txt`（SHA-256 `53e5a7be…04c6`），正在運作。
- #735 剩下：#675 Agent 預設設定（等 #732 的最佳設定），#566／#574 LIVE A／B 畫面（blocked，等 R2 #589）。

##### 2.3 重現包與清理（#733）

- PR #738 已合併 `a90a7884`（盤點工具＋Linux／macOS 重現包）。#728 剩下雲端位置補登和分析後定稿。
- D394：`local/` 必要性審查後，使用者決定全刪、不留備份（約 8.2 GB），已執行，磁碟可用約 16 GiB。刪除腳本 `local/evidence/delete-20261127/delete.sh`。引用這些項目的文件之後標成「已刪除（D394）」。
- [#740](https://github.com/Polalalabear/amidst/issues/740)（Neon）：盤點工具的兩個引用盲點。

##### 2.4 報告（#734）

- PR #736 骨架已合併 `c741c95d`。E6／E7 數字等 #732 跑完再另開 PR。小 nit：文件裡「等 #726 合併」要改掉。

##### 2.5 Codex 與 Neon

- Neon：#740。#731、#733、#734 本輪的 PR 都已合併。
- Codex：額度不足，原本的 #732、#735 工作由 Claude 代做（D391、D396）。

#### 3. 排程

- `amidst-coordinator-resume-0955`：2026-11-27 09:55 叫醒**舊**協調對話。交接後要改成叫醒新對話，或刪除後重建。

#### 4. 本段教訓

- 審 #737 時只核對了修正項目，沒有比對 #731 原本承諾的範圍，結果 #732 開工後才發現 G1–G5 不在 main 上。之後審 feature PR 時，要把 issue 的「包含」清單逐項對到 diff。
- 交給使用者跑的指令曾給錯啟動檔（`start_demo.command`）。D395 之後改成由 Claude 自己執行。
