# E6 執行紀錄規格 v1（#717；#721 的實作輸入）

本檔只定義紀錄，未啟動 blocked 的 #721。每次執行獨立 run_id；身份
`UNCONFIRMED`，所有推論端欄位不得含 GT、renderer 軌跡、visibility、depth 或劇本答案。

共用來源 envelope：schema_version、run_id、case_id、arm、k、mode、tick_us、size、
source/index/records/RGB descriptor/calibration/config/code/protocol SHA-256。
推論紀錄與 GT 評分紀錄分檔；以 run_id、capture tick、camera_id 關聯。

| 階段 | 必填欄位與意義 |
|---|---|
| REQUEST | request_id、ask_tick、FIRST/POLL/LOST_EARLY、原始請求 SHA、reference SHA、每鏡頭影格 SHA、完整候選清單（camera_id、該次 detection_id、框、score、color evidence、gate reasons）、提問前 own_tracking、neutral_status、last_known_position/tick 或明列 MISSING、獨立 rule_state（若有） |
| RESPONSE | request_id、原始回答或其 LOCAL 路徑與 SHA、模型 digest、answer、selected_camera/detection/box、ranking、confidence、provider latency、usage；provider error/timeout/guard denial 仍須留一筆 |
| VALIDATION | request_id、accepted boolean、reason、validated answer/selected box、是否仍在 pending、call cap 狀態；接受不等於採用 |
| APPLICATION | request_id、ask_tick、apply_tick 或 MISSING、requested box、actual adopted box、source、applied boolean、fallback reason、expired reason、套用前後 own_tracking；UNCERTAIN 是合法不改動，applied=false；pending_at_end 不得冒充已套用 |
| TRACK | 每 tick：own_tracking（含框與估計位置）、neutral_status、tracker_action（FOLLOWING/COASTING/LOST/OCCLUDED_HOLD/ADOPT/CLEAR/NO_CHANGE）、作用中的 request_id、events、last observed tick；中性追蹤與新回答接管分開 |
| SCORE（獨立評分檔） | run_id/request_id、ask_tick 的 GT-side answer judgement、apply_tick 的分類、直到下一次實際接管的每 tick 分類、visible/blind 分母與裁切規則；GT provenance 和主準則/Iou 準則分開 |

「回答當下」以 ask_tick 的候選框評分；「套用後」以實際 run.rows 評分。
本次 AO 描述切片到下一筆已釋放回答，UNCERTAIN 也切片，故是回答時序描述，
不是因果歸因；正式記錄應另保留 active_request_id，跨 UNCERTAIN 連接實際接管。
舊 A2 沒有完整 candidate_list，**MISSING**，不能拿新結果或 GT 補成原請求。
舊 AO 有候選清單、ask/applied tick 與 rows，可派生描述欄位，但缺完整逐階段
原始事件時不得宣稱舊紀錄已符合本規格。

正式 12 段的錄製前設計偏離（起點修正、`TRUE_DEPARTURE`→`FULL_BLIND`、S12 尾段）與關卡結果見 [E6_ROUTES_RECORDING_20261127.md](E6_ROUTES_RECORDING_20261127.md)。

---

# 第二部：E6 正式執行紀錄（#732，2026-11-27）

> 狀態：**骨架**（D407）。結果數字一律 `UNKNOWN（待 2d）`，由 E6 協調對話在 `verdict_e6`（Stage 2d）完成、並做完 D402 事後閘門核對後回填。本骨架撰寫時未讀任何分數、verdict 或 `local/evidence/` 下的 E6 輸出。R 編號對應預登 [`E6_PREREGISTRATION_DRAFT.md`](E6_PREREGISTRATION_DRAFT.md)（#726 `017dd61a`）的章節號；預登 §4（統計）併入 R1，§6（劇本）併入 R0。執行經過見 [`EXP_RUN_732_20261127.md`](../operations/EXP_RUN_732_20261127.md) §5。

**報告語言（預登 §1.1、§4.4–§4.5）**：判定只有 `SUPPORTED`（成立）／`NOT_SUPPORTED`（不成立）／`INCONCLUSIVE`（無法判斷）／`EXPLORATORY`。**「無法判斷」不等於「無差異」**；$M=12$ 的檢定力有限，落入無法判斷時要照實寫檢定力限制。P2 若為不成立或無法判斷，必須寫明「改良後仍未證實優於現有規則」。S3（R-N 對照）的結論只能寫「在中性追蹤器底座上」。身分一律 `UNCONFIRMED`。

## R0. 凍結輸入與執行環境

| 項目 | 值 |
| --- | --- |
| 預登 | `docs/evaluation/E6_PREREGISTRATION_DRAFT.md`（#726 `017dd61a`），本身未改 |
| 凍結規格 | `configs/evaluation/e6_scenarios_frozen_v1.json` `5bab2766…1b338`（D401） |
| 路線 | routes JSON `22bee772…1146983`（D401） |
| 正式錄製 | LOCAL `local/evidence/e6-formal-20261127/`，MANIFEST `e9297132…44efc`（118 MB、14 901 檔；不重建，重錄屬偏離） |
| 決策點 | 48 個（VISIBLE 43、FULL_BLIND 5、TRUE_DEPARTURE 0），錄製後由 GT 規則放置（D399 DC2、D401） |
| 正式偵測 | LOCAL `local/evidence/e6-formal-det-20261127/`（沿用 E3 `e3_cases/index.py` 與 RT-DETR 參數，`DETECTION_RECEIPT.json`）；SHA：`UNKNOWN（待 2d）` |
| K=1 診斷 | LOCAL `local/evidence/e6-arms-k1-20261127/`，MANIFEST `0cc89c0d…8d9f`；297 次呼叫全 OK，USD 3.2797 |
| 批 3 凍結收據（現行） | `BATCH3_FREEZE.json` `2ecdeb61…95db`；`VERIFY_FREEZE.json` `feb8a19f…a1bf`（main `a25a2124`） |
| SELECTED_AGENT | `DEANCHOR_HIST_SUM`（三次凍結皆同；選組是確定性的） |
| 正式輸出根目錄 | LOCAL `local/evidence/e6-formal-run-20261127/{b1,rn,ao_orig,arms}/<case>/`；verdict 在 `…/verdict/` |
| 帳本 | 新空帳本 LOCAL `local/evidence/e6-run-ledger-20261127/`（見偏離 X9） |
| 執行指令 | `bash scripts/experiments/run_all.sh --execute --e6-phase=all`（G4 session，main 乾淨 clone） |
| 完整 SHA-256 與 MANIFEST | `UNKNOWN（待 2d）`：上表截短值以 #93 D401／D404／D405 為準，完整值由 E6 協調對話回填 |

## R1. 假設判定

### R1.1 主要假設（Holm，預登 §1.1、§4.4）

| 假設 | 比較 | C1 ΔWP（s） | C2 ΔFollow | C3 ΔDP | C4 ΔBlindFL（s） | $p$（正向） | $p^{neg}$ | 判定 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| P1 | DEANCHOR − AO_ORIG | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） |
| P2 | DEANCHOR_HIST_SUM − B1 | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） |

- 樣本：$M$＝`UNKNOWN（待 2d）`（預期 12）、$N_{\text{dp}}$＝`UNKNOWN（待 2d）`（預期 48）；`EXPLORATORY` 觸發條件（$N_{\text{dp}}<40$ 或 $M<8$）：`UNKNOWN（待 2d）`。
- 校正區間（97.5%／95.0%）與 `would_be`：`UNKNOWN（待 2d）`。
- 敏感度（D406，S12 AO.k2 用原 DNS 失敗檔）：P1 判定 `UNKNOWN（待 2d）`。

### R1.2 次要／探索性（不進 Holm，預登 §1.2）

| 編號 | 比較 | 結果 | 備註 |
| --- | --- | --- | --- |
| S1 | DEANCHOR_HIST vs DEANCHOR | UNKNOWN（待 2d） | DEANCHOR_HIST 未進正式 12 段（未選中）；只能用 K=1 診斷描述或記「未執行」 |
| S2 | DEANCHOR_HIST_SUM vs DEANCHOR_HIST | UNKNOWN（待 2d） | 同上 |
| S3 | Agent 各組 vs R-N | UNKNOWN（待 2d） | 只能寫「在中性追蹤器底座上」 |
| S4 | DEANCHOR vs AO_ORIG 機制 | UNKNOWN（待 2d） | `same_wrong_persistence_rate`、失聯秒、重新出現 top-1／top-3 |
| S5 | P1、P2 較嚴盲區準則 | UNKNOWN（待 2d） | |
| S6a | NO_IMAGE vs SELECTED_AGENT | UNKNOWN（待 2d）（或 `BUDGET_SKIPPED`） | D403：探索性，未校正符號翻轉 $p$ |
| S6b | NO_SPATIAL vs SELECTED_AGENT | UNKNOWN（待 2d）（或 `BUDGET_SKIPPED`） | 同上 |
| S6c | SIMLIVE_K1 | 未執行 | D403 決定不做 |

## R2. 選組（預登 §2.2，D400）

- 收據：見 R0。逐層軌跡（錯人秒 → 盲區誤鎖秒 → 平均跟對率 → 簡單優先）在 `BATCH3_FREEZE.json`；本骨架不抄數字，回填時只引收據 SHA 與停在哪一層：`UNKNOWN（待 2d）`。
- 批 3 由機械閘門取代人工審查（偏離 X6）；Opus 事後閘門核對結果：`UNKNOWN（待 2d）`。

## R3. 指標（預登 §3，每組 12 段合計；Agent 組 K=3）

| 組別 | 跟對率 | 錯人秒 | 失聯秒 | 盲區誤鎖秒 | `full_track_dp_acc` | `single_dp_acc` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B1 | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） |
| R-N | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） |
| AO_ORIG | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） |
| DEANCHOR | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） |
| DEANCHOR_HIST_SUM | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） | UNKNOWN（待 2d） |

- IoU 保守準則（IoU ≥ 0.3）穩健性：`UNKNOWN（待 2d）`。
- 依 `gt_regime` 分層（VISIBLE／FULL_BLIND；TRUE_DEPARTURE n=0，偏離 X2）：`UNKNOWN（待 2d）`。
- 格式退回率、provider 錯誤率、`CALL_BUDGET_EXHAUSTED`（預登 §7.2 第 3–4 點）：`UNKNOWN（待 2d）`。

## R5. 資料分離與 GT 隔離

- `check_e6_data_separation.py --mode formal`：錄製凍結時 PASS（D401）；批 3 閘門內再跑一次 PASS（D404／D405 的 VERIFY_FREEZE 各項 PASS）。正式組執行後：`UNKNOWN（待 2d）`。
- GT 隔離違規（預登 §7.2 第 2 點）：`UNKNOWN（待 2d）`。

## R7. 預算

| 項目 | USD |
| --- | ---: |
| D375 基準 | 38.17 |
| K=1 診斷（2a） | 3.2797（累計 41.45） |
| 正式組 dry-run 上界（AO_ORIG＋DEANCHOR＋DEANCHOR_HIST_SUM） | 43.7424（8.6829＋16.1064＋18.9532；上限 45，偏離 X7） |
| AO_ORIG 實際（停在 S12 k2 時的帳本估計） | 約 6.48（618 列；累計約 47.93，D406） |
| S12 AO k2／k3 重跑 | UNKNOWN（待 2d） |
| DEANCHOR、DEANCHOR_HIST_SUM 實際 | UNKNOWN（待 2d） |
| 消融 NO_IMAGE、NO_SPATIAL | UNKNOWN（待 2d）（或 `BUDGET_SKIPPED`） |
| 最終累計（≤ 90） | UNKNOWN（待 2d） |

## R8. 偏離列表（全部在任何組別分數產生前定案）

| # | 偏離 | 預登條文 | 決策 | 處理與對結論的影響 |
| --- | --- | --- | --- | --- |
| X1 | **DC1 起點修正**：7/12 段規格起點與引擎不相容，改用修正起點錄製 | §6 劇本規格 | D399 | 規格欄位不改；修正起點逐段列在 [`E6_ROUTES_RECORDING_20261127.md`](E6_ROUTES_RECORDING_20261127.md)。錄製前定案 |
| X2 | **DC3 S11-DP3／DP4 宣告 `FULL_BLIND`**：引擎中目標不會離場，`TRUE_DEPARTURE` 分層 n=0 | §6、§3.1 `gt_regime` | D399、D401 | 不改引擎；`TRUE_DEPARTURE` 分層不報數字，列為已知限制 |
| X3 | **DC7 干擾者最高 2.1 m/s** | §6 | D399 | 列為限制（干擾者速度範圍窄於規格意圖） |
| X4 | **S12 tail_s 1.0**：S12-DP4（tick 136）的 3.0 s 窗超出 30 s，錄製延長 1.0 s（156 tick） | §6（約 30 s） | D401 | 路線與軌跡不變；routes JSON `frozen_by` 文字不精確，以錄製文件為準，凍結檔不重算 |
| X5 | **選組平手解讀**：三組時每層保留與最佳者差 ≤ 容許值的全部組別；平均跟對率＝3 段各自跟對率的算術平均 | §2.2 | D400 | 釐清非改規則；兩組時與原文等價。在任何診斷輸出前定案 |
| X6 | **批 3 改機械閘門＋使用者事前同意**：`e6_select_arm.py verify-freeze`（重算選組逐欄比對、prompt／參數 SHA、`code_commit_sha`＝HEAD、資料分離、上限、累計）取代人工審查 | §0「批 3 審查通過並經使用者同意」 | D402 | 使用者原話「先設計好一次跑完，可以接受含費用的」；Opus 在結果前另做閘門紀錄核對（R2） |
| X7 | **正式上限 USD 32 → 45** | §7.1、§7.2 第 5 點 | D404 | 只改 `FORMAL_CAP_USD`／`MAX_FORMAL_USD`（#748 `a9418fdf`）；累計上限 90、選組、評分不變。因 `code_commit_sha` 檢查，在新 commit 重新凍結（見 R8.1） |
| X8 | **S04／S07 B1 無 ACQUIRE → 所有組無種子**：R-N 輸出 `seed: null`、`seed_status: NO_B1_ACQUIRE`；Agent 組共用同一種子規則，兩段都不啟動、不呼叫 API | §2.1（R-N 同種子 tick） | D405 | #750 `a25a2124`；不換替代種子、不重錄。兩段**所有組配對差依構造為 0**，仍留在分母（不剔除），會把效果量往 0 拉，列為已知限制 |
| X9 | **新空帳本** `local/evidence/e6-run-ledger-20261127/`，不用舊 `local/evidence/api-usage`（est 合計 22.40、最後一列 2026-11-20，已含在 D375 基準 38.17 內，續用會重複計） | §7.1 累計基準 | 協調者接受（記於 EXP_RUN §4） | 累計＝38.17＋新帳本列（K=1 診斷帳本由 `e6_refresh_ledgers` 納入） |
| X10 | **S12 AO_ORIG k2 DNS 失敗只重跑 k2／k3**：24 次呼叫中 18 次 `URLError [Errno 8]`（請求未離開本機）、1 次 timeout、5 次 OK；k3 未跑 | §7.2 第 4 點（provider 錯誤記缺漏、不重跑） | D406 | 用戶端網路故障不算 provider 錯誤；原檔改名保留在 `local/evidence/e6-formal-run-20261127/ao_orig-aside-infra/E6-S12/`。**主分析用重跑的 k2／k3，敏感度分析用原 k2 另算一次 verdict**，兩者都報（R1.1）。不整組重跑 |
| X11 | **D403 消融為探索性**：NO_IMAGE → NO_SPATIAL，只對 SELECTED_AGENT、12 段、K=3；SIMLIVE_K1 不做 | §1.2 S6、§7.1 條件項 | D403 | 不進 P1／P2 Holm，只報與 SELECTED_AGENT 的配對差與未校正 $p$；累計＋上界 > 90 記 `BUDGET_SKIPPED` |

### R8.1 批 3 收據沿革

| 凍結 | main commit | `BATCH3_FREEZE.json` | `VERIFY_FREEZE.json` | 結果 | 狀態 |
| --- | --- | --- | --- | --- | --- |
| 1 | `71633fb8`（#741） | `313441a7…1fa3` | `af1d73a2…37c3` | 9 項 PASS；`FORMAL_OVER_CAP 43.74 > 32` → exit 6，正式付費 0 | superseded（資料夾 `e6-batch3-freeze-20261127-superseded-71633fb8`） |
| 2 | `a9418fdf`（#748） | `8806e8f6…5643` | `b3f64f6a…a71e` | 10 項 PASS；之後 R-N 在 S04／S07 StopIteration（X8），正式付費 0 | superseded（`…-superseded-a9418fdf`） |
| 3 | `a25a2124`（#750） | `2ecdeb61…95db` | `feb8a19f…a1bf` | 現行 | 現行 |

三次的 `SELECTED_AGENT` 都是 `DEANCHOR_HIST_SUM`。舊收據改名保留、不刪。

## R9. 已知限制（報告必寫）

1. `TRUE_DEPARTURE` 分層 n=0（X2）；干擾者 ≤ 2.1 m/s（X3）。
2. S04／S07 所有組無種子，配對差依構造為 0（X8）。
3. $M=12$ 檢定力有限（預登 §4.5）：「無法判斷」不得寫成「無差異」。
4. S12 AO_ORIG 主分析與敏感度分析並列（X10）。
5. 批 3 為機械閘門而非人工審查（X6）；正式上限 45 而非 32（X7）。
