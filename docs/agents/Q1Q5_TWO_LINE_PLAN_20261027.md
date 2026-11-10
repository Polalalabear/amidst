# Q1–Q5 兩條線工作分配（D87）

日期：2026-10-27。決策來源：[D87](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6421557959)。即時狀態以[任務板 #93](https://github.com/Polalalabear/amidst/issues/93)為準。

## 1. 兩條線的定義與關係（D87）

| 線 | 內容 | 範圍 |
| --- | --- | --- |
| Line 1 | 第一版 r004 baseline | 範圍不變。A4／B4 劇本用情境卡加料，限於 graph v3 與 D79 的限制內 |
| Line 2 | 複雜場景 | 現行評分器與規則處理不了的情況：一窗多次 RETURN、長時間 LOST、D77 重疊接手、新鏡頭與新路線、較長多鏡頭行走 |

- Line 2 傘狀 issue：[#251](https://github.com/Polalalabear/amidst/issues/251)。
- Line 1 不另開 issue，追蹤在 #93 與既有 PR。
- Line 2 不得改 Line 1 已核定範圍。
- Codex 完成目前審查回覆後，兩條線並行。

## 2. Line 1 工作分配

### Codex（現在：審查回覆）

| 項目 | 負責 | 狀態 | 前置 | 預計完成項目 |
| --- | --- | --- | --- | --- |
| [#238](https://github.com/Polalalabear/amidst/pull/238) catalog 凍結收據與 A4／B4 run 註冊檔（D84） | Codex | 審查回覆中 | 時鐘長度待情境卡 | 收據與註冊檔更新 |
| [#235](https://github.com/Polalalabear/amidst/pull/235) L1／L2 與 M1 兩方案 | Codex | 審查回覆中 | 無 | 兩方案定稿 |
| [#236](https://github.com/Polalalabear/amidst/pull/236) 小修 | Codex | 審查回覆中 | 無 | 小修完成 |
| [#234](https://github.com/Polalalabear/amidst/pull/234) README D83 與 notes 3–5 | Codex | 審查回覆中 | 無 | README 與 notes 更新 |
| 契約小修、G4 收據格式、U37 | Codex | 審查回覆中 | 無 | 契約與格式更新 |
| Q1／Q3 回應補 `resolved_scope.tracking_scope_sha256`；Q2 讀 scope pin；工程場景補 tracking scope 檔 | Codex | 審查回覆中 | #127 rc4 結果 | 三項補齊 |
| D86 Q3 追蹤語法與缺時間預設整段 run 的契約提案 | Codex | 待做 | D86 | 契約提案 |
| 審 [#243](https://github.com/Polalalabear/amidst/pull/243)、[#83](https://github.com/Polalalabear/amidst/pull/83) | Codex | 待做 | 無 | 審查意見 |
| 關閉被 [#231](https://github.com/Polalalabear/amidst/pull/231) 涵蓋的舊 PR | Codex | 待做 | 無 | 舊 PR 關閉並留註 |
| P1 漏檢逐格診斷 | Codex | 待做 | [#218](https://github.com/Polalalabear/amidst/issues/218) | 診斷報告 |
| 重錄三包 | Codex | 待做 | 上列項目完成 | 三包重錄 |

### Codex（之後）

| 項目 | 負責 | 狀態 | 前置 | 預計完成項目 |
| --- | --- | --- | --- | --- |
| Blender 可行性、[#115](https://github.com/Polalalabear/amidst/issues/115) 劇本、重發時鐘 | Codex | 未開始 | 使用者核定情境卡 | 可行性結論、劇本、新時鐘 |
| G4 後渲染（CX-7） | Codex | 未開始 | G4、磁碟、渲染授權 | 渲染結果 |
| 索引 [#118](https://github.com/Polalalabear/amidst/issues/118) | Codex | 未開始 | CX-7 | 索引 |
| 正式 baseline（CX-8） | Codex | 未開始 | CX-7、索引 | baseline |

### Claude

| 項目 | 負責 | 狀態 | 前置 | 預計完成項目 |
| --- | --- | --- | --- | --- |
| 複核 Codex 上列全部 | Claude | 隨 Codex 交付 | Codex 回覆 | 複核記錄 |
| #127 rc4 對重錄包重跑（AC7） | Claude | 未開始 | 重錄三包 | AC7 結果 |
| [#228](https://github.com/Polalalabear/amidst/pull/228) 對齊 AC2 後合併 | Claude | 待做 | AC2 | 合併 |
| [#240](https://github.com/Polalalabear/amidst/pull/240) 合併 | Claude | 待做 | 審查通過 | 合併 |
| 打包 yyin Q1／Q3 包 | Claude | 未開始 | #238 合併 | 可轉交的包 |
| r004 A4／B4 情境卡 v1 與事件表 adapter | Claude | 進行中（PR 待開） | 無 | 情境卡 v1、adapter |
| G4 收據（含 M1 與逐邊核准） | Claude | 未開始 | yyin 三題回來 | G4 收據 |
| P2 評估 | Claude | 未開始 | 正式 baseline | 評估結果 |
| Demo 腳本 [#124](https://github.com/Polalalabear/amidst/issues/124) | Claude | 未開始 | P2 | 腳本 |
| staging→mainline 分批合併；進度導覽補列 | Claude | 持續 | 各 PR 通過 | 分批合併 |

### 使用者

| 項目 | 負責 | 狀態 | 前置 | 預計完成項目 |
| --- | --- | --- | --- | --- |
| 核定情境卡 | 使用者 | 待情境卡 v1 | Claude 情境卡 v1 | 核定 |
| G4 | 使用者 | 待 yyin 三題 | G4 收據 | 核准 |
| 磁碟空間 | 使用者 | 待處理 | 無 | 可用空間 ≥ 9 GiB |
| P2 驗收 | 使用者 | 未開始 | P2 評估 | 驗收 |
| 轉交 yyin 包 | 使用者 | 未開始 | Claude 打包 | 已轉交 |
| D64 外部 API 例外 | 使用者 | 之後 | 無 | 決定 |

### yyin

| 項目 | 負責 | 狀態 | 前置 | 預計完成項目 |
| --- | --- | --- | --- | --- |
| r004 三題澄清 | yyin | 進行中 | 無 | 回交 |
| Q1／Q3 出題包（靜態家具 Q1＋Q3 8 題） | yyin | 未開始 | 使用者轉交 | 回交 |
| Q4 盲測 | yyin | 之後 | Q1／Q3 包 | 回交 |
| 第二包（人與車 Q1） | yyin | 之後 | 正式渲染後 | 回交 |

## 3. Line 2 工作分配

| 議題 | 項目 | 負責 | 模型（Claude 端） | 前置 |
| --- | --- | --- | --- | --- |
| [#251](https://github.com/Polalalabear/amidst/issues/251) L2-0 | 傘狀 issue | 協調者 | 不適用 | 無 |
| [#244](https://github.com/Polalalabear/amidst/issues/244) L2-1 | Q5 評分器擴充：一窗多次 RETURN、長時間 LOST、重疊接手 | Claude | Opus 設計 → Sonnet 實作 | L2-7 的 LOST 期限與重疊時機 |
| [#245](https://github.com/Polalalabear/amidst/issues/245) L2-2 | 複雜情境卡 v2（只寫規格，不渲染） | Claude | Opus | Line 1 情境卡 v1；L2-7 |
| [#246](https://github.com/Polalalabear/amidst/issues/246) L2-3 | workbench 長時間軸、8 台鏡頭監看牆、長片段 Q1 並排 | Claude | Sonnet | #243 |
| [#247](https://github.com/Polalalabear/amidst/issues/247) L2-4 | 漏檢診斷與偵測改善（[P1 回報](https://github.com/Polalalabear/amidst/pull/228#issuecomment-6416863116)、#218） | Codex | 複核 Sonnet | P1 逐格診斷 |
| [#248](https://github.com/Polalalabear/amidst/issues/248) L2-5 | linker／Q5 controller 契約提案（依 D73，第一版不設期限） | Codex | 複核 Opus | L2-7、L2-1 |
| [#249](https://github.com/Polalalabear/amidst/issues/249) L2-6 | 工程小場景（2–3 台、約 30 秒、一個轉角） | Codex | 複核 Sonnet | 磁碟 ≥ 8 GiB、渲染授權 |
| [#250](https://github.com/Polalalabear/amidst/issues/250) L2-7 | 決策清單：LOST 期限、重疊接手時機（D77）、磁碟或外接儲存、第二版範圍 | 使用者 | 不適用 | 無 |

## 4. 並行規則

- Codex 完成審查回覆後，兩條線並行。
- 同時寫入的 session 上限 3（D87）。
- 各 session 寫的檔案不得重疊。
- 磁碟可用空間 ≥ 9 GiB 才開第 3 個寫入 session。
- Claude 不渲染。
- Line 2 不得改 Line 1 已核定範圍。
- 一項工作一個新 session，不送回舊 session。
- 只用 merge commit，不 rebase、不 force。

## 5. 里程碑順序

日期一律 `UNKNOWN`，待使用者核定。

### Line 1

| 順序 | 里程碑 | 日期 |
| --- | --- | --- |
| 1 | Codex 完成審查回覆 | UNKNOWN |
| 2 | #238、#240、#228 合併；yyin 包打包 | UNKNOWN |
| 3 | 使用者核定情境卡；Codex 重發時鐘、重錄三包 | UNKNOWN |
| 4 | yyin 三題回來；G4 收據；使用者 G4 | UNKNOWN |
| 5 | CX-7 渲染；索引；CX-8 正式 baseline | UNKNOWN |
| 6 | P2 評估與驗收；Demo 腳本 | UNKNOWN |

### Line 2

| 順序 | 里程碑 | 日期 |
| --- | --- | --- |
| 1 | L2-7 使用者決策 | UNKNOWN |
| 2 | L2-1 評分規則草案；L2-2 情境卡 v2 規格；L2-4 診斷 | UNKNOWN |
| 3 | L2-5 契約提案；L2-3 長時間軸 | UNKNOWN |
| 4 | L2-6 工程小場景（需磁碟與授權）驗證 L2-4／L2-5 | UNKNOWN |
| 5 | 使用者決定哪些情境進第二版 | UNKNOWN |

## 6. 本機檔案冗餘控制

- 協調者正在評估可移除的本機檔案候選。
- 未經使用者核准，不刪除任何檔案。
- 原始 Blender、影片、資料集、校正與 Ground Truth 資產維持不動。
