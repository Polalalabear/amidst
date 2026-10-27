# Q1–Q5 Demo v1：baseline 驗收計畫與工作分配

- 日期：2026-10-25（Claude 協調者撰寫）；2026-10-27 更新到 D94（D93、D94 只作用於 Line 2）（見 §2、§3、§4、§5）
- 範圍：本文是 **Line 1（r004 A4-1／B4-1 baseline，D89）** 的驗收計畫。第二條線（複雜場景，D87）的分工見 [Q1Q5_TWO_LINE_PLAN_20261027.md](Q1Q5_TWO_LINE_PLAN_20261027.md)，不在本文範圍。
- 依據：D70–D94（D93、D94 只作用於 Line 2）（[任務板 #93](https://github.com/Polalalabear/amidst/issues/93)）、契約 `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md`（現行版在 staging，SHA `b700bf86…`；mainline 副本過期，不要手改）、[#192](https://github.com/Polalalabear/amidst/issues/192) baseline 規格
- 即時狀態以 [Q1Q5_PROGRESS.md](../operations/Q1Q5_PROGRESS.md) 和 #93 為準。本文只寫目標、驗收標準與分工。

## 1. 使用者要驗收的 Demo

使用者能**選取目標或查看目標**，畫面會**跟著切到目標所在的鏡頭**。

| 編號 | 驗收標準 | 怎麼看 |
| --- | --- | --- |
| AC1 | 用一行指令啟動 workbench；另有 recorded replay 模式，不連模型也能重播 | 啟動說明照做一次，不必另外查文件 |
| AC2 | 選取目標：輸入一句中文（Q3），Q1 結果牆列出符合條件的鏡頭與時段；點一筆結果，或直接點畫面上的偵測框，就選為目標 | 至少 3 句不同的查詢 |
| AC3 | 查看目標：主畫面跳到該鏡頭與時刻，顯示目標框與時間軸 | 目標框、鏡頭名稱與來源時間一致 |
| AC4 | 跟隨切鏡：播放時，同鏡頭內持續標出目標（Q2）；目標離開畫面後，單畫面模式自動硬切到 Q5 判定的下一台鏡頭，多鏡頭模式標出下一台。找不到時顯示「搜尋中」或「回原鏡頭」，不假裝找到 | 至少 1 次成功切鏡、1 次找不到 |
| AC5 | 模式：預設 RULE_ONLY，可以選 AGENT_SEQUENTIAL。Qwen 逾時時顯示兜底接手（D73） | 兩種模式各跑一次 |
| AC6 | 審核模式顯示每一步的決策來源、候選、證據與 fallback 原因；Demo 模式不顯示內部判斷（D71） | 切換 `?mode=review` 比對 |
| AC7 | 可重現：同一 session 用 recorded replay 重播，輸出 hash 相同；#127 測試包對該 session 的輸出全部通過 | 附 hash 與 kit 報告 |
| AC8 | 誠實標示：MISSING／UNKNOWN 照實顯示；不宣稱身分已確認 | 抽看缺格與找不到的情況 |

## 2. 兩階段驗收（D76）

| 階段 | 資料 | 用途 | 前置條件 |
| --- | --- | --- | --- |
| **P1 工程預驗收** | Codex 的工程動態場景（#211：8 秒、20 fps、真 RT-DETR 索引） | 先驗操作流程與畫面跟隨（AC1–AC8），早點找出 UI 問題。**不是正式成績** | CX-4 整合分支、CX-5 預驗收版、CL-4 Claude 預走查 |
| **P2 正式 baseline 驗收** | r004 A4-1（50 s）／B4-1（42 s）正式事件與正式索引（D89）；A4-1／B4-1 共 6 個計分事件（A4-c2 不過則 5，D92-1：A4-e、B4-d 不計分） | 正式 baseline 數據與 Demo | CX-3 圖 v3 → G4 → CX-7 渲染與索引 → CX-8 正式 baseline → CL-5 評估。目錄於 D84 凍結（`3eba8572…`），`static_validity` 為 `NOT_EVALUATED` |

## 3. 關鍵路徑

```
CX-1 契約修正 ─┐
CL-1 kit rc2 ──┴─> 契約定版、#127 合併 ─┐
CX-2 staging 修正 ─> CL-2 複核、分批合主線 ─┤
CX-4 baseline 整合分支（完成）─> CX-5 預驗收版（完成）─> CL-4 預走查（完成）─> 使用者 P1 驗收
CX-3 圖 v3 ─> CL-3 複核 ─> 使用者 G4 ─> CX-7 渲染＋索引 ─> CX-8 正式 baseline ─> CL-5 評估 ─> CL-6 走查 ─> 使用者 P2 驗收
```

CX-4、CX-5、CL-4 已完成（對應 PR 見 §4）；其餘節點的即時狀態以 [Q1Q5_PROGRESS.md](../operations/Q1Q5_PROGRESS.md) 為準。

D89 之後 P2 的前置路徑（A4-1／B4-1）：

```
D89（A4-1 50 s／B4-1 42 s）─> #256 靜態可行性（D92-1 調整）─> #238 時鐘宣告與 D84 目錄凍結 ─> #115 A4／B4 事件 run
```

## 4. 工作分配

兩條線的整體分工（含 Line 2 的 Claude／Codex／使用者工作）見 [兩條線計畫](Q1Q5_TWO_LINE_PLAN_20261027.md)；本節只列 Line 1。「PR」欄是 2026-10-27 依 `gh` 查到的對應項目，合併狀態以 [Q1Q5_PROGRESS.md](../operations/Q1Q5_PROGRESS.md) 為準。

### Codex

| 編號 | 工作 | 對應 | 完成條件 | PR／狀態 |
| --- | --- | --- | --- | --- |
| CX-1 | 契約修正：R1–R8、寫入 D73（含 X2：手動改選時由使用者在前端決定是否重啟 Agent）；為 BL-SW（#189）補 §14 選項 | #144 | Claude 複核通過、Codex 確認新 SHA，依 D71 合主線 | [#237](https://github.com/Polalalabear/amidst/pull/237)（契約 B，staging）；契約小修與 D86／G4 提案 [#260](https://github.com/Polalalabear/amidst/pull/260)（Draft） |
| CX-2 | staging 修正：#142、#149、#160、#164；v0-pilot 審查包與 importer（#147／#151） | #93 指派（10/25） | 每項一個修正 PR（base staging），Claude 複核後才合 | [#220](https://github.com/Polalalabear/amidst/pull/220)、[#221](https://github.com/Polalalabear/amidst/pull/221)、[#222](https://github.com/Polalalabear/amidst/pull/222)、[#224](https://github.com/Polalalabear/amidst/pull/224)、[#226](https://github.com/Polalalabear/amidst/pull/226)（皆已併入 staging） |
| CX-3 | r004 圖 v3 的 10 項；CAM_ENTRY 不進自動切鏡（D74） | #117 收據、D74 | Claude 複核通過，提交 G4 | [#227](https://github.com/Polalalabear/amidst/pull/227)、[#235](https://github.com/Polalalabear/amidst/pull/235)（已併入 staging）；G4 未核 |
| CX-4 | baseline 整合分支：把 #193–#214 收成 `codex/q1q5-baseline-integration`，關閉被取代的 PR（保留分支）；受 D73 影響的 Draft（#157、#169、#172、#174、#180 等）一併依 D73 修改 | D75 | 一個 PR（base staging），列出被併入的 PR 與 head SHA | [#231](https://github.com/Polalalabear/amidst/pull/231)（staging `680ca35`）；**完成** |
| CX-5 | P1 預驗收版：在工程動態場景上，用一行指令啟動，滿足 AC1–AC8；附給使用者的操作說明（怎麼啟動、點哪裡、預期看到什麼） | 本文 §1 | Claude 預走查通過 | [#233](https://github.com/Polalalabear/amidst/pull/233)（已併入 staging）；P1 一行啟動與 8 秒播放，AC7 另依 #127；**完成** |
| CX-6 | Qwen3 不截斷診斷量測：同一題組、不設逾時，記錄完整延遲、token 數與輸出是否合法。不改 D65 預算，不進正式分母 | D76 | 量測報告與原始紀錄 pins | [#230](https://github.com/Polalalabear/amidst/pull/230)（已併入 staging）；**完成** |
| CX-7 | G4 之後：凍結圖 → #115 A4／B4 渲染 → #118 正式索引（HSV 用 §11 初值，D75）。每次產製前後記 `df -k`，可用空間低於 8 GiB 就停 | #115、#118 | 產出 pins 與 GT 隔離收據 | 前置：[#256](https://github.com/Polalalabear/amidst/pull/256)（D89 靜態可行性，Draft）、[#238](https://github.com/Polalalabear/amidst/pull/238)（D89 時鐘與 D84 凍結，已併入 staging）；G4 後執行 |
| CX-8 | 正式 baseline：RULE_ONLY 與 AGENT_SEQUENTIAL（D65 預算），錄製、replay、輸出凍結；P2 正式資料的工作台 | #194、#202 | 凍結收據；#127 通過 | 未開始 |
| CX-9 | 之後交給組員的任何包，都要有說明檔與指定的 RETURN 檔案（格式參考 r004 前置審查包 v2） | D76 | — | [#234](https://github.com/Polalalabear/amidst/pull/234)（CX-10 可攜包 v4，已併入 staging）示範格式 |

其他 Line 1 的 Codex PR（2026-10-27）：[#242](https://github.com/Polalalabear/amidst/pull/242)（rc4 錄製重錄，已併入 staging）、[#257](https://github.com/Polalalabear/amidst/pull/257)（rc4 工程 tracking scope pin，已併入 staging `c1d9cbd`）、[#259](https://github.com/Polalalabear/amidst/pull/259)（#235／#236／#234 審查備註，已併入 staging）、[#262](https://github.com/Polalalabear/amidst/pull/262)（P1 回報的 28 筆偵測／連結缺口逐格診斷，已併入 staging）。

### Claude

| 編號 | 工作 | 對應 | 完成條件 | PR／狀態 |
| --- | --- | --- | --- | --- |
| CL-1 | 測試包 rc2 依 D73 對齊 → 綁定最終契約 SHA → 合併 #127 | #145 | kit 對錄製輸出 0 FAIL（不適用的項目要寫明原因） | [#127](https://github.com/Polalalabear/amidst/pull/127)（Draft；head rc5 `4e3edfc`，增量複核 PASS；AC7 仍未通過；重錄見 [#277](https://github.com/Polalalabear/amidst/pull/277)，待複核） |
| CL-2 | 複核 CX-1、CX-2、CX-4（程式由 Sonnet、契約與決策由 Opus）；staging 第 2 批之後分批合主線；合完後關閉 #135 | #93 | 合併前核對 head SHA | 審查與分批合併：[#213](https://github.com/Polalalabear/amidst/pull/213)（第 1 批）、[#267](https://github.com/Polalalabear/amidst/pull/267)（staging→mainline，Draft） |
| CL-3 | 複核圖 v3，出 G4 收據，交使用者核准 | #117 | G4 決定紀錄 | G4 收據待辦；v3 圖見 #227／#235 |
| CL-4 | P1 預走查：瀏覽器逐步截圖，對照 AC1–AC8，交使用者試用 | #124 | 走查報告 | [#228](https://github.com/Polalalabear/amidst/pull/228)（走查清單，已合併 `bd44ff2`）；**完成** |
| CL-5 | 評估端：輸出凍結前提出 Q5 決策窗寬（交使用者核定）；把組員 CSV 轉成精確標註（D75）；輸出凍結後跑評分 | #129、#89、#138、#128 | 評分報告 | [#254](https://github.com/Polalalabear/amidst/pull/254)（A4-1／B4-1 劇本 adapter，Draft）；窗寬已核定（D79） |
| CL-6 | 改寫 Demo 腳本 #124，做 P2 瀏覽器驗收 | #124 | 驗收報告 | 未開始（Demo 腳本 #124 仍開） |
| CL-7 | 組員包的整理（說明檔加 RETURN）與回收匯入 | D76 | — | [#240](https://github.com/Polalalabear/amidst/pull/240)（yyin Q1／Q3 包設計，Draft） |

Line 2 的 Claude 工作（[#258](https://github.com/Polalalabear/amidst/pull/258) L2-1 評分規則、[#261](https://github.com/Polalalabear/amidst/pull/261) L2-2 情境卡 v2、[#255](https://github.com/Polalalabear/amidst/pull/255) L2-3 長時間軸）見兩條線計畫，不在本表。

### 組員（yyin）

| 編號 | 工作 | 狀態 |
| --- | --- | --- |
| T-1 | r004 的 3 個澄清問題，以及 v0-pilot 畫面 T／F 試填 | 包已備好（LOCAL `team-handoff-yyin-20261025`） |
| T-2 | Q1／Q3 出題，包含 Q3 最小題組 8 題，由組員自己出（D76） | 等 #149 修好，Claude 另出包 |
| T-3 | Q4 正式 T／F | 等 CX-8 正式輸出 |

### 使用者

G4 核准、Q5 決策窗寬核定、`exit_rule` 的 `boundary_inclusive` 值、P1／P2 驗收，以及最後是否更新 `main`（D72）。

## 5. 不在這一版範圍

- **磁碟搬移（D90-3）：**三個 `.local-worktrees` 維持現狀，不動、不停服務、不搬移；之後 CX-7 或 L2-6 需要空間時再評估。8 GiB 停止線不變。
- **第二版範圍（D90-4，暫定）：**複雜場景分兩批（第一批不需新場景，第二批需新場景版本、磁碟與渲染授權），屬 Line 2，不影響本文的 Line 1 範圍。

- **OpenAI API**：依 10/22 的決定，排在 baseline 完成之後，當比較組。接之前需要使用者決定：D64 規則例外（第一版不用外部 API）、送外部畫面的隱私與授權範圍、預算與逾時。
- **CAM_WIDE 100°**：第一版維持 90°（D76）；100° 之後可以當新的場景版本另做比較。
- **新 HSV 提案（#158）**：之後當比較組，不擋 baseline（D75）。
