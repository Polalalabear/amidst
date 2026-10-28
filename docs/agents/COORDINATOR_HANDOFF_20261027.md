# 協調者交接（2026-10-27）

- 本文接續 [2026-10-26 交接](COORDINATOR_HANDOFF_20261026.md)。新的協調者先讀本文，再讀 [任務板 #93](https://github.com/Polalalabear/amidst/issues/93)、[驗收計畫](Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) 和 [進度導覽](../operations/Q1Q5_PROGRESS.md)。文件整理（D91）的計畫與清單在 [#263](https://github.com/Polalalabear/amidst/issues/263)；舊資料見[封存索引](../archive/ARCHIVE_20261027.md)，新規格見 [Q1–Q5 產品規格](../specs/Q1Q5_PRODUCT_SPEC.md)（兩者由 #263 的 S1、S4 提供，本 PR 寫成時可能尚未合入）。
- 即時狀態以 GitHub 為準。本文只寫交接當下的快照、慣例和待辦；寫不確定的地方標 `UNKNOWN`。

## 1. 交接當下的狀態

| 項目 | 狀態 |
| --- | --- |
| `mainline/q1q5` | @`2675c21`（合入 [#241](https://github.com/Polalalabear/amidst/pull/241)，10-26 交接）。S2 初稿寫成時的快照；之後以 `git ls-remote` 為準 |
| `codex/q1q5-staging` | @`680ca35`（合入 [#231](https://github.com/Polalalabear/amidst/pull/231)：baseline 整合，含契約 B）。staging 尚未整批併入 mainline。之後 [#257](https://github.com/Polalalabear/amidst/pull/257) 已併入（merge `c1d9cbd`），頂端以 `git ls-remote` 為準 |
| `main` | @`519e874`，不動（D72） |
| 開著的 PR | 總數 UNKNOWN（以 `gh pr list` 為準）。2026-10-27 部分仍開著的（不完整）：[#83](https://github.com/Polalalabear/amidst/pull/83)、[#82](https://github.com/Polalalabear/amidst/pull/82)、[#163](https://github.com/Polalalabear/amidst/pull/163)（D88 先留著）、[#264](https://github.com/Polalalabear/amidst/pull/264)（S1）、[#265](https://github.com/Polalalabear/amidst/pull/265)（本文）、[#228](https://github.com/Polalalabear/amidst/pull/228)、[#238](https://github.com/Polalalabear/amidst/pull/238)、[#240](https://github.com/Polalalabear/amidst/pull/240)、[#242](https://github.com/Polalalabear/amidst/pull/242)、[#243](https://github.com/Polalalabear/amidst/pull/243)、[#252](https://github.com/Polalalabear/amidst/pull/252)–[#262](https://github.com/Polalalabear/amidst/pull/262)（#257 已合併除外） |

資料快照：r004 目錄凍結 `3eba8572…`（D84）；A4／B4 時鐘 50 s／42 s（D89，[#238](https://github.com/Polalalabear/amidst/pull/238) `f159ac8`）。

## 2. 今天的決定（D88–D91，全文在 #93）

- **D88**：本機清理先清安全項（舊暫存 96 個目錄，約 146 MiB）；Codex 的 `.local-worktrees` 先問 Codex；#240、#228 修衝突（merge commit 合入 mainline，不 force），#163、#82 先留著（[issuecomment-6422147844](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6422147844)）。
- **D89**：核定 A4／B4 情境卡 v1（[#253](https://github.com/Polalalabear/amidst/pull/253) `7554dc6`）：採 A4-1＋B4-1，A4-1 50 s、B4-1 42 s；NO_SWITCH 結束點讓位（U-C7）；U-C9 關閉；M1（U-C8）留給 G4（[issuecomment-6423194857](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423194857)）。
- **D90**：第二條線決策（[#250](https://github.com/Polalalabear/amidst/issues/250)）：(1) LOST 由評估端分類，≥ 1.8 s 的暫失歸 Line 2，產品端不加狀態；(2) 重疊對採失聯後接手，圖 v4 加 EXT_CAR↔EXT_CLEAR、BRANCH↔WIDE（W1↔W2 屬第二版），M1 不預先決定；(3) 磁碟維持現狀（三個 `.local-worktrees` 不動，8 GiB 停止線不變）（[issuecomment-6423575212](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423575212)、[-6423763378](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423763378)）；(4) 第二版範圍分兩批，暫定。
- **D91**：文件封存與現況更新（[issuecomment-6434355675](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434355675)）：封存方式 A（`docs/archive/ARCHIVE_20261027.md` 當索引，原檔留位、md 加檔頭）；`docs/specs/` 舊規格歸歷史並另寫新規格；寫本交接；進度導覽改由協調者批次補，AGENTS.md 該行跟著改。
- 前一日接續：**D86**（口語追蹤句擴 Q3 規則、缺時間預設整段 run、workbench 呈現缺口）、**D87**（Line 2 並行、先設計情境卡、寫入上限 2→3；[issuecomment-6421557959](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6421557959)）。
- **D92**（[issuecomment-6434464633](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434464633)、補記 [-6434474506](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434474506)）：
  1. **#256 可行性衝突 → 選項 1**：A4 室外端改走 EXT_CLEAR（A4-c1 seed 改 EXT_CLEAR，段 0 從 EXT_CLEAR:E_OUT_VEST 離開，時刻 8／11 s 不變）；A4-e、B4-d 改為不計分（路線不變）；A4-c2 保留但段 5 走 EXT_CLEAR 一側，EXT_CAR 的 `t_L` 是否落在 `[t_N − 4.0, t_N − 1.0]` 由 Codex 靜態投影確認，不過就改不計分。計分事件 8 → 6（或 5）；50／42 s、#238 時鐘、評分器、D79 不動。
  2. **#260-A**：要有追蹤動詞（如「去了哪裡」）才判 FIND_PERSON；只有「紅色的人」「那個人」時依查找規則判 Q1。D86-1 補註。
  3. **#260-C**：可信 G4 核准以 checkpoint issue 的核准留言＋協調者記錄的 D 決策為準。
  4. **#260-B（補記）**：Q1／Q2／Q3 回應升 v2，`resolved_scope` 只加必填鍵 `time_range_source`，v1 錄製原樣重播，不改 D80 query preimage。
- 下一個編號：**D93**。

## 3. 今天的派工與複核結果（只列已發生的）

### Codex（兩批派工：[第一批 -6423281851](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423281851)、[第二批 -6434379604](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434379604)；[交件索引 -6424123274](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6424123274)）

第一批已交件：A1 [#256](https://github.com/Polalalabear/amidst/pull/256)、A2 [#238](https://github.com/Polalalabear/amidst/pull/238)、B1 [#257](https://github.com/Polalalabear/amidst/pull/257)、B2 [#242](https://github.com/Polalalabear/amidst/pull/242)、C1 審查、C2 [#259](https://github.com/Polalalabear/amidst/pull/259)、C3、C4 [#260](https://github.com/Polalalabear/amidst/pull/260)、D1 [#262](https://github.com/Polalalabear/amidst/pull/262)、D2 [#250](https://github.com/Polalalabear/amidst/issues/250)。重點：

- A1 的結論**不是可行性 PASS**：A4 的 SOUTH→W1 直線下界 8.3634 m，最快 1.5 m/s 仍需 5.5756 s，不符 3 s／±0.5 s。D92-1 已採選項 1 修法；Codex 依此改寫 #256 並確認 A4-c2（第三批 I1）。其餘見 [#253 留言](https://github.com/Polalalabear/amidst/pull/253#issuecomment-6423680078)。修法待情境卡 owner 決定。
- B2 尚未真正重錄：待 B1 #257 合入，目前 fresh=0、AC7=NOT_ACCEPTED。
- 第二批（E1–E3、F1–F2、G1–G4）已派，交件狀態：UNKNOWN。
- 第三批（[issuecomment-6434474862](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434474862)，複核結果與 D92）：H1–H5 回修（#259 F1、#238 區間寫法、#262 參數註記、#257 N2、#242 N2）；I1 #256 依 D92-1 改寫；I2 #260 依 D92 修訂；I3 回應 v2 實作；I4 重錄與 kit rc5 同步；I5 第二批照舊。合併順序：#257 → #242 → #238 → #259 → #262 → #260，由使用者按 merge commit。
- [#257](https://github.com/Polalalabear/amidst/pull/257) 已合併進 staging（merge `c1d9cbd`），staging 頂端因此不再是 `680ca35`；B2 重錄（G1／I4）可以開始，結果 UNKNOWN。

### Claude（今天開的 PR；皆 Draft，皆未合併）

| PR | 內容 | 狀態 |
| --- | --- | --- |
| [#252](https://github.com/Polalalabear/amidst/pull/252) | 兩條線計畫（D87） | Draft，base mainline |
| [#253](https://github.com/Polalalabear/amidst/pull/253) | A4／B4 情境卡 v1（D89 核定） | Draft，base mainline |
| [#254](https://github.com/Polalalabear/amidst/pull/254) | r004 A4-1／B4-1 劇本 → `q5-evaluation-script.v1` adapter | 複核 PASS_WITH_NOTES；已有回修 session，回修結果 UNKNOWN |
| [#255](https://github.com/Polalalabear/amidst/pull/255) | L2-3 長時間軸／8 鏡頭牆（依賴 #243） | 複核 PASS_WITH_NOTES；回修結果 UNKNOWN |
| [#258](https://github.com/Polalalabear/amidst/pull/258) | Q5 評分規則 v2 設計稿（L2-1） | Draft；Codex 要答 §5 的 C1–C10（E1） |
| [#261](https://github.com/Polalalabear/amidst/pull/261) | 複雜情境卡 v2（L2-2） | Draft；Codex 做 §5 靜態可行性（E2） |
| [#243](https://github.com/Polalalabear/amidst/pull/243) | workbench Q1 結果牆與追蹤單畫面（D86-3） | Codex 審 NEEDS_CHANGES（[-6423865942](https://github.com/Polalalabear/amidst/pull/243#issuecomment-6423865942)：多段命中填平缺口）；已有回修 session，結果 UNKNOWN |
| [#228](https://github.com/Polalalabear/amidst/pull/228) | P1 走查清單（AC2 查詢句） | 已派修，結果 UNKNOWN |

### Claude 對 Codex PR 的複核（留言內）

| PR | 結論 | 連結 |
| --- | --- | --- |
| #262 | PASS_WITH_NOTES | [留言](https://github.com/Polalalabear/amidst/pull/262#issuecomment-6424259724) |
| #260 | PASS_WITH_NOTES（Opus） | [留言](https://github.com/Polalalabear/amidst/pull/260#issuecomment-6434365452) |
| #257 | PASS_WITH_NOTES | [留言](https://github.com/Polalalabear/amidst/pull/257#issuecomment-6434385433) |
| #242 | PASS_WITH_NOTES | [留言](https://github.com/Polalalabear/amidst/pull/242#issuecomment-6434385821) |
| #259 | **FAIL**（F1：`portable_pack.py` 的 private locator 掃描會讓真實包建不起來；擋合併） | [留言](https://github.com/Polalalabear/amidst/pull/259#issuecomment-6434386262) |
| #256 | 數字全部重算一致，「不能判可行」成立；D92 採選項 1 | [留言](https://github.com/Polalalabear/amidst/pull/256#issuecomment-6434381673) |
| #238 | 通過 | [留言](https://github.com/Polalalabear/amidst/pull/238#issuecomment-6434381956) |

Codex 對 Claude PR 的審查：#243 NEEDS_CHANGES（見上）；[#83](https://github.com/Polalalabear/amidst/pull/83) 決策索引 NEEDS_CHANGES（[留言](https://github.com/Polalalabear/amidst/pull/83#issuecomment-6423867393)：決策窗／D78 狀態與 D79–D90 的取代關係過期）。

### 文件整理（D91，#263）

S1 封存索引與檔頭（已開 [#264](https://github.com/Polalalabear/amidst/pull/264)）、S3 進度與過期文件、S4 新規格（進行中）依 #263 拆分（[#263](https://github.com/Polalalabear/amidst/issues/263)）。本交接屬 S2。

## 4. Claude 的待辦

| 何時 | 工作 | 模型 |
| --- | --- | --- |
| 現在 | 回報 #263 S1／S3／S4 的進度；S3 要等 #253、#252、#228、#240 合併後再開 | Sonnet |
| Codex 回修後 | 複核 #259（F1）、#243、#254、#255 的回修 | Sonnet（程式）；Opus（圖、契約、資料） |
| #257 合併後 | 確認 Codex 照 #242 重錄；跑 #127／AC7 | Sonnet |
| E1、E2 交件後 | 核定 #258；做 L2-1 v2 評分器 | Opus（設計）；Sonnet（實作） |
| Codex 完成 #256 改寫（I1）後 | 依 D92-1 更新 #253 情境卡與 #254 計畫檔；A4-c2 取決於靜態投影 | Opus（情境卡）；Sonnet（計畫檔） |
| staging 併入 mainline 前 | 審 G2 的合併 PR；批次補進度列（#220、#221、#222、#224、#226、#230、#232 加今天的） | Sonnet／Haiku |
| 本文整理合併後 | 把 1026 交接標為歷史（#263 分類） | Haiku |

## 5. 等 Codex

- 第二批 E1–E3、F1–F2、G1–G4 的交件；#257 合併後的 G1 重錄。
- #260 依 D92 修訂（I2）與回應 v2 實作（I3）：D92-2、-3、-4 已定案，修訂後要 Claude 複核再改契約。
- G4 的 M1 兩個選項仍未決。

## 6. 使用者待辦

- 依序按 merge commit：#257（已合）→ #242 → #238 → #259 → #262 → #260（Claude 複核後）。
- G4 決定（含 M1）；staging → mainline 合併 PR 由使用者決定時機。
- 之後：168 條遠端分支 demo 後再整理。

## 7. 組員（yyin）

- 10-26 狀態：正在看 r004 的三個澄清問題；下一份 Q1／Q3 包的設計稿是 [#240](https://github.com/Polalalabear/amidst/pull/240)（Draft），目錄凍結後出包。今天的更新：UNKNOWN。

## 8. 協調者慣例（使用者規定）

沿用 [10/26 的慣例](COORDINATOR_HANDOFF_20261026.md#9-協調者慣例使用者規定)（含 [10/25 的慣例](COORDINATOR_HANDOFF_20261025.md#8-協調者慣例使用者規定)），加上今天新增的：

- **畫面不做手機版**：workbench 與 demo 畫面只做桌面，不測也不修 375 px。
- **168 條遠端分支 demo 後再整理**：現在不刪、不歸檔。
- **D91**：文件封存方式 A；進度導覽的列由協調者批次補，不在 staging 的 PR 逐筆補（AGENTS.md「Progress guide」已改）。
- **寫入 session 上限 3**（D87）：檔案不重疊、第 3 個開始前可用磁碟 ≥ 9 GiB、Claude 端不渲染、低於 8 GiB 停止。
- **磁碟維持現狀**（D90-3）：三個 `.local-worktrees` 不動。
- 只用 merge commit、不 rebase、不 force、不刪分支、`main` 不動。
