# 協調者交接（2026-10-25）

- 前一個協調者 session 在 2026-10-25 封存。新的協調者先讀本文，再讀 [任務板 #93](https://github.com/Polalalabear/amidst/issues/93)、[驗收計畫](Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) 和 [進度導覽](../operations/Q1Q5_PROGRESS.md)。
- 即時狀態以 GitHub 為準。本文只寫交接當下的快照、慣例和待辦。

## 1. 交接當下的狀態

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

## 2. 今天的決定（全文在 #93）

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

## 3. 今天的審查結論

- **PASS**：#136、#140、#141、#143、#150、#152、#166、#167、#151。
- **PASS_WITH_NOTES**：#139、#132、#155、#162、#159、#165、#181、#182、#212、#214、#216。
- **NEEDS_CHANGES**：#142、#148–#179 契約鏈、#149、#160、#164。修正指派在 #93（issuecomment，標題「Claude 10/25 staging 審查結果與修正指派」）。
- **#216 的發現**：A→B 空檔有一大段是追蹤失敗，不是幾何盲區（漏檢就判暫失，回原鏡頭只比對凍結框）。已開 [#218](https://github.com/Polalalabear/amidst/issues/218)，Codex 先提 §14 選項。

## 4. 等 Codex（全部已貼 #93；清單見驗收計畫 §4）

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

## 5. Claude 的待辦

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

## 6. 使用者待決

- 現在：把組員包傳給 yyin。
- 之後依序：#218 的選項 → G4（圖 v3 複核後）→ Q5 決策窗寬 → P1 驗收 → `exit_rule` 的 `boundary_inclusive` → 是否更新 `main`。
- OpenAI API 排在 baseline 之後；接之前要先決定 D64 的規則例外。

## 7. 組員（yyin）

- **已交回**：r004 前置審查 v2，132 項全部有效（123 T／7 F／2 不確定；70 題 HSV 全填 T，正式 Q4 時建議改成盲測）。
- **待交**：r004 澄清 3 題，LOCAL `$AMIDST_ARTIFACTS/team-handoff-yyin-20261025.zip`。
  - 2.8 MB，ZIP SHA-256 `c6ac1cee61676614263c592e45a5c5a8fde3ca97bba922dbe5fdc7008a2339e7`，MANIFEST SHA-256 `d84bfbb6bdc6685e6abcc29603377535db259ab4d4b98c79a87c0a8ec3b73657`。
  - 瀏覽器填表，格式與 r004 v2 相同；附 `tools/verify_pack.py`。
  - 回交檔是 `RETURN/審查表_yyin_YYYY-MM-DD.csv`。
  - 原本的 24 張畫面試填和 r004 包的 70 題 HSV T／F 重疊，已經拿掉。
- **之後**：Q1／Q3 出題（含 Q3 的 8 題，等 #149 修好）、正式 Q4 T／F（等正式輸出）。每份包都要有說明檔和 RETURN。

## 8. 協調者慣例（使用者規定）

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
