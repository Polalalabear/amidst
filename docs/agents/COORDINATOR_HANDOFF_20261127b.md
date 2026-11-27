# 協調者交接（2026-11-27 第二次）

快照時間 2026-11-27 約 10:30（+08:00）。main = `71633fb8`；8785 pin = `5727fc9a`（未變）；下一個決策號 **D404**。之後的狀態以 [#93](https://github.com/Polalalabear/amidst/issues/93)、[#674](https://github.com/Polalalabear/amidst/issues/674) 為準。新的協調對話**全程用繁體中文**（D255）。前一份：`COORDINATOR_HANDOFF_20261127.md`。

## 0. 先讀

1. 本文件。
2. #93 的 D399–D403 留言（本段新增的決策）。
3. #674 最新幾則。
4. 規則：`CLAUDE.md`、`AGENTS.md`、`CLAUDE.local.md`，以及 D389、D391、D395、D396、D397、D402。

## 1. 規則（本段新增或重申）

- **D402**：使用者事前同意 E6「一次跑完、含費用」。預登要求的批 3 人工審查改成機械閘門 `e6_select_arm.py verify-freeze`，不再中途停下等人。這是明示的預登偏離，執行紀錄要照實寫。結果出來前，Opus 另外做一次事後核對，只看閘門紀錄，不看分數。
- **D397**：累計 ≤ USD 90 直接用。每次付費前先 ApiGuard dry-run 並記帳。
- **context 80% 交接**：context 接近 80% 時，協調對話自己準備交接（文件＋PR → `start_session` 開新的 Opus 對話，effort 相同、fresh → `detach_session` → 叫進行中的 session 改報給新對話 → 叫醒排程改指向新對話 → 在 #674 記一則）。
- **派工方式**：只讀、幾分鐘就完成的審查，用 Agent 子代理（Sonnet）比較省；寫檔或長時間的工作開子 session；已有 context 的工作送回原 session（SendMessage）。
- **額度**：五小時額度到 90% 時，用 scheduled task 在 `resetsAt` 後約 5 分鐘叫醒協調對話。醒來後繼續做事，不只是審查。

## 2. #732 主線（E6）現況

| 項目 | 狀態 |
|---|---|
| 預登 | `docs/evaluation/E6_PREREGISTRATION_DRAFT.md`（#726 `017dd61a`） |
| G1＋G2 新 12 段路線與錄製 | #745 合併 `a1fb2fcb`。D399 設計定案（DC1 起點修正、DC3 S11 改宣告 FULL_BLIND、DC7 ≤2.1 m/s、DC9 關卡）。D401 錄製凍結：LOCAL `local/evidence/e6-formal-20261127/` MANIFEST `e9297132…44efc`（118 MB、14 901 檔）；凍結規格 `configs/evaluation/e6_scenarios_frozen_v1.json` `5bab2766…1b338`；48 點（VISIBLE 43、FULL_BLIND 5、TRUE_DEPARTURE 0）；S12 tail_s 1.0 |
| G3 三組＋付費路徑 | #743 合併 `7dbb4ede` |
| K=1 診斷（付費） | 完成：297 次呼叫全 OK，格式退回 0、provider 錯誤 0，USD 3.2797，累計 **41.45**。LOCAL `local/evidence/e6-arms-k1-20261127/` MANIFEST `0cc89c0d…8d9f`。分數還沒有人看過 |
| G6 正式 K=3 路徑＋`verdict_e6`＋消融 | #746 合併 `037477d3`。Sonnet＋Opus 審過。新舊版在 `ablation=none` 時 18 個請求逐位元組相同，K=1 的選組可以套用到正式組 |
| G4 一次跑完 | #741 合併 `71633fb8`：選組（D400 平手解讀）、verify-freeze、正式偵測（沿用 E3 `index.py`，LOCAL `local/evidence/e6-formal-det-20261127/`）、R-N 擴充、控制流程修正（17＋ 項測試）、Linux／macOS 可攜複製 |
| **正式執行** | **進行中**：G4 session（`local_85cdc9e8-dfa6-4c1d-9053-3a9217b6c95f`）從 main `71633fb8` 的乾淨 clone 背景跑 `run_all.sh --execute --e6-phase=all`。每個 Stage 回報一行；2d 之前不看分數 |
| D403 消融 | NO_IMAGE → NO_SPATIAL，只對 SELECTED_AGENT、12 段、K=3；累計＋上界 > 90 就記 BUDGET_SKIPPED；探索性，不進 Holm |

### 正式跑完後要做的事

1. 核對結果：STATUS、VERIFY_FREEZE.json、verdict_e6.json、花費，以及每個輸出的 MANIFEST。先做 D402 要求的事後核對（只看閘門紀錄），再看分數。
2. 開結果 PR（`claude/feat-exp-run` 新分支，或再開一支）：在 `docs/operations/EXP_RUN_732_20261127.md` 和 `docs/evaluation/E6_EXECUTION_RECORD_V1.md` 寫實際產出與偏離列表（DC1、DC3、DC7、S12 tail、D402 機械閘門、TRUE_DEPARTURE n=0）。
3. 回填 #741（已合併，留言）、#732、#721、#742、#674、#93 的 FEAT-EXP-RUN 列。
4. 接著做：#734 報告的 E6 數字（Neon 或 Claude 另開 PR）、#675 Agent 預設設定（依 E6 最佳組）、E7 等使用者在 Colab 跑完再分析。

## 3. 其他工作（沒有變動）

- 8785 pin `5727fc9a` 正在跑（gate r5）。#735 剩 #675（等 #732）、#566／#574（blocked，等 R2 #589）。
- #733：剩 #728 雲端位置補登與定稿。#740（Neon）盤點工具的引用盲點。
- #734：骨架已合併 `c741c95d`，數字等 #732。
- **使用者要做的**：把 `local/evidence/e7-colab-pack-20261127/` 上傳私人雲端硬碟，在 Colab 跑 E7。

## 4. Session

- G4／G5：`local_85cdc9e8-dfa6-4c1d-9053-3a9217b6c95f`，執行中。
- G3：`local_1d45dee9-095e-4ecc-98c4-4cf350c52e1e`，已收尾。
- G1＋G2：`local_7b1915af-6532-483a-92bc-33210b59f514`，已收尾。
- 排程 `amidst-coordinator-resume-0955` 已觸發（一次性）。新對話要排下一次叫醒時，另外建立。

## 5. 本段教訓

- CI 跑在 Linux：macOS 專用的指令（`cp -c`）要有替代路徑，否則 CI 失敗，也違反產出 ②「Linux 可重現」。
- 背景「等 CI 就合併」的指令要比對 head SHA。等 CI 期間 head 前進過一次，比對擋下了，沒有合併到錯的版本。
- 付費、一次跑完的腳本，控制流程本身也要測（軟步驟、exit code、續跑完成的判定）。這次由 Sonnet 實測抓到三個問題。
