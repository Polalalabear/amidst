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

> 狀態：**已回填**（D407 骨架 → 2026-11-27 回填）。Stage 2 `COMPLETE`（`local/evidence/e6-formal-run-20261127/STATUS.json`，2026-11-27T11:21:32Z），D402 事後閘門核對通過（E6 協調對話）。數字只取自 `local/evidence/` 下的唯讀輸出（`verdict*/verdict_e6.json`、`VERDICT_E6.md`、`STATUS.json`、各 `MANIFEST.sha256`、`e6-batch3-freeze-20261127*/`、各 `ledger/usage.jsonl`）；回填時未重跑、零費用。R 編號對應預登 [`E6_PREREGISTRATION_DRAFT.md`](E6_PREREGISTRATION_DRAFT.md)（#726 `017dd61a`）的章節號；預登 §4（統計）併入 R1，§6（劇本）併入 R0。執行經過見 [`EXP_RUN_732_20261127.md`](../operations/EXP_RUN_732_20261127.md) §5。

**報告語言（預登 §1.1、§4.4–§4.5）**：判定只有 `SUPPORTED`（成立）／`NOT_SUPPORTED`（不成立）／`INCONCLUSIVE`（無法判斷）／`EXPLORATORY`。**「無法判斷」不等於「無差異」**；$M=12$ 的檢定力有限。P2 不成立：**改良後仍未證實優於現有規則**（`verdict_e6.json` `must_report`）。S3（R-N 對照）的結論只能寫「在中性追蹤器底座上」。消融（S6）為探索性、不進 Holm。身分一律 `UNCONFIRMED`。

## R0. 凍結輸入與執行環境

| 項目 | 值 |
| --- | --- |
| 預登 | `docs/evaluation/E6_PREREGISTRATION_DRAFT.md`（#726 `017dd61a`），本身未改；檔案 SHA-256 `309e8f3c1c14076b943df7894b338777275d84eeafcc91fe62c733a36b5685fa`（收據 `prompt_and_config_sha256`） |
| 凍結規格 | `configs/evaluation/e6_scenarios_frozen_v1.json` `5bab27666bddcf4c4e089f8e442d19d263540e3ff158ca17ad8565c6e601b338`（D401；`verdict_e6.json` `frozen_spec_sha256`） |
| 路線 | routes JSON `22bee772…1146983`（D401） |
| 正式錄製 | LOCAL `local/evidence/e6-formal-20261127/`，MANIFEST SHA-256 `e929713224851394bca1adaea0008eb0076169f9b8265528a79131c3eda44efc`（118 MB、14 901 檔；不重建，重錄屬偏離） |
| 決策點 | 48 個（VISIBLE 43、FULL_BLIND 5、TRUE_DEPARTURE 0），錄製後由 GT 規則放置（D399 DC2、D401） |
| 正式偵測 | LOCAL `local/evidence/e6-formal-det-20261127/`（29 530 檔，無 MANIFEST；沿用 E3 `e3_cases/index.py` 與 RT-DETR 參數）；`DETECTION_RECEIPT.json` SHA-256 `36e4a6422b42c8b9f594917d1d367985665101f76b48000c9bd754f09445cd15` |
| K=1 診斷 | LOCAL `local/evidence/e6-arms-k1-20261127/`，MANIFEST SHA-256 `0cc89c0df325b28d94f00d31e73e392aaa8e06ca23e87a0e6546e97fa03c8d9f`；297 次呼叫全 OK，USD 3.2797 |
| 批 3 凍結收據（現行） | 見 R8.1（main `a25a212424c268c96a31efe8bb59f08a32cff729`） |
| SELECTED_AGENT | `DEANCHOR_HIST_SUM`（三次凍結皆同；選組是確定性的） |
| 模型 | `gpt-6.1-terra`（收據 `params.model`） |
| 評分器 | `scorer_sha256` `acacce396f27e0d7c8bf03d527b22272f2622376ed4a43ae6db0842353f87d08`（收據與 verdict 相同） |
| 正式輸出根目錄 | LOCAL `local/evidence/e6-formal-run-20261127/`（下表） |
| 帳本 | 新空帳本 LOCAL `local/evidence/e6-run-ledger-20261127/`（0 列；見偏離 X9）＋各步驟自己的 `ledger/usage.jsonl`（R7） |
| 執行指令 | `bash scripts/experiments/run_all.sh --execute --e6-phase=all`（G4 session，main 乾淨 clone） |

### R0.1 正式輸出的雜湊（LOCAL，皆不可重建：付費組重跑會得到不同回答）

| 輸出（`local/evidence/e6-formal-run-20261127/…`） | 檔數 | 雜湊種類 | SHA-256 |
| --- | ---: | --- | --- |
| `b1/` | 13 | 樹雜湊（無 MANIFEST） | `909206065630c27124331e9739e30eacd6dd40e5636274e5a7e716616cb7e5cc` |
| `rn/` | 25 | 樹雜湊（無 MANIFEST） | `e4da4b6dcff1f2b62d6b87de893af838c39a69e4eecb776bf607fef3243dab00` |
| `ao_orig/`（主分析：S12 k2／k3 為重跑檔） | 37 | 樹雜湊（無 MANIFEST） | `f4eb72b4e4db2a6b4004793f457506146a6b4592c57a5f23d3c5163be5a2b68c` |
| `ao_orig-aside-infra/`（S12 原 DNS 失敗 k2） | 1 | 樹雜湊（無 MANIFEST） | `aecc13d86d7a2bb4271fe06bfa33c32c05e63f901fb9e4654e0ba7344bfaffc0` |
| `ao_orig-sensitivity-dns/`（敏感度輸入） | 36 | 樹雜湊（無 MANIFEST） | `e144f52e7b858c5d0759a596871c08bf0489a58e639d7136f749afee735eccb3` |
| `arms/`（DEANCHOR、DEANCHOR_HIST_SUM） | — | `MANIFEST.sha256` 的 SHA-256 | `a68f3b41ddc903724463ab4ce188aeac6020c48846c663feab78afc7177e2772` |
| `verdict/`（主分析） | — | `MANIFEST.sha256` 的 SHA-256 | `f99d5de0c4e68c93c3056185bbd197d588fdeec1169fe2c8e99e98cf6acc8028` |
| `verdict-exploratory/`（含消融） | — | `MANIFEST.sha256` 的 SHA-256 | `14c5cfca8e6b6368f4b6fb6657cb9bc2d34a17f25b25c9adb10c3dc4a152359b` |
| `verdict-sensitivity-dns-original-k2/`（D406） | — | `MANIFEST.sha256` 的 SHA-256 | `61a1e220123ff7d5c7e3411978aeb695d275fd76fc756de7aba7d67b5d05d926` |
| `ablation-NO_IMAGE/` | — | `MANIFEST.sha256` 的 SHA-256 | `e7d00a56394fab50cb09ef29b3202600d22385fa7be2223cd88ba927653fba47` |
| `ablation-NO_SPATIAL/` | — | `MANIFEST.sha256` 的 SHA-256 | `e0a1e4c04bb7ef3e39ef5b7f3670fc521c085383f570b7b7eebb5da2694a0fc6` |

**樹雜湊算法**（2026-11-27 執行完成後事後計算，非事前登記）：在該目錄內執行
`find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256`，
即對每個檔案（相對路徑 `./…`、C locale 排序，含 `STATUS.json`）列出 `<sha256>  <path>`，再對整份清單取 SHA-256。格式與 `MANIFEST.sha256` 的逐行格式相同，但路徑帶 `./` 前綴，所以數值不能和 MANIFEST 的 SHA 直接比較。

## R1. 假設判定

### R1.1 主要假設（Holm 0.0125／0.025，單尾；預登 §1.1、§4.4）

`status: FORMAL`：$M=12$、$N_{\text{dp}}=48$（門檻 $N_{\text{dp}}\ge 40$、$M\ge 8$），未觸發 `EXPLORATORY`。`SKEW_SENSITIVITY_FLAG: False`。

| 假設 | 比較 | C1 ΔWP（s） | C2 ΔFollow | C3 ΔDP | C4 ΔBlindFL（s） | $p_h$（IUT max） | $p^{neg}$ | 判定 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| P1 | DEANCHOR − AO_ORIG | −3.600 | −0.013 | −0.021 | −0.400 | 0.75 | 1.0 | **INCONCLUSIVE**（無法判斷） |
| P2 | DEANCHOR_HIST_SUM − B1 | 4.067 | −0.131 | −0.333 | 22.867 | 0.9990234375 | 0.009765625 | **NOT_SUPPORTED**（不成立；負向 Holm 通過） |

各元件的符號翻轉 $p$ 與校正區間（`verdict/VERDICT_E6.md`）：

| 元件 | P1 $p_{flip}$ | P1 97.5% CI | P2 $p_{flip}$ | P2 97.5% CI |
| --- | ---: | --- | ---: | --- |
| C1 | 0.46094 | [−17.868, 3.400] | 0.67578 | [−17.868, 19.867] |
| C2 | 0.06201 | [−0.061, 0.034] | 0.94897 | [−0.239, −0.037] |
| C3 | 0.75000 | [−0.146, 0.083] | 0.99902 | [−0.479, −0.146] |
| C4 | 0.00024 | [−1.333, 0.400] | 0.99780 | [11.800, 35.134] |

- `verdict_if_formal` 與判定相同（P1 INCONCLUSIVE、P2 NOT_SUPPORTED）。
- P1 為無法判斷：不得寫成「去錨定與原版無差異」。P2：B1 在跟對率、決策點正確率、盲區誤鎖秒都明顯較好；**改良後仍未證實優於現有規則**。
- bootstrap 區間是百分位近似；符號翻轉的精確性需要對稱虛無假設（預登 §4.3，verdict notes）。

**敏感度分析（D406，偏離 X10）**：S12 AO_ORIG k2 改用原 DNS 失敗檔，其餘輸入相同。

| 假設 | 主分析判定（$p_h$／$p^{neg}$） | 敏感度判定（$p_h$／$p^{neg}$） | 有變的元件 |
| --- | --- | --- | --- |
| P1 | INCONCLUSIVE（0.75／1.0） | INCONCLUSIVE（0.75／1.0） | C1 −3.600 → −2.933；C2 −0.013 → −0.000（$p_{flip}$ 0.06201 → 0.00171）；C4 −0.400 → 1.333（$p_{flip}$ 0.00024 → 0.03687）；C3 不變 |
| P2 | NOT_SUPPORTED（0.9990234375／0.009765625） | NOT_SUPPORTED（同左） | 無（P2 不含 AO_ORIG） |

證據的性質照實寫：這兩次分析**沒有事前雜湊**，所以這裡不是「同一份輸入的前後 diff」。證據有三項：
- 兩個 verdict 目錄各自的 MANIFEST 已在事後驗證。
- 輸入逐檔比對只有 S12 AO.k2 不同：敏感度用的是原 DNS 檔 `6d71fbba…`，主樹用的是重跑檔 `bae7db77…`。
- 檔案 mtime。

### R1.2 次要／探索性（不進 Holm，預登 §1.2）

| 編號 | 比較 | 結果 | 備註 |
| --- | --- | --- | --- |
| S1 | DEANCHOR_HIST vs DEANCHOR | **正式 12 段未執行** | DEANCHOR_HIST 沒有被選中，未進正式組。只有**診斷 K=1、非正式組**的數字（E3-A1／B1／C1 三段合計，`BATCH3_FREEZE.json` `metrics`）：錯人秒 DEANCHOR 20.0、DEANCHOR_HIST 15.2；盲區誤鎖秒 10.0、10.0；跟對率 0.7977、0.782。這是選組用的診斷值，不能當成 S1 的正式結果 |
| S2 | DEANCHOR_HIST_SUM vs DEANCHOR_HIST | **正式 12 段未執行** | 同上。**診斷 K=1、非正式組**：錯人秒 DEANCHOR_HIST_SUM 11.6、DEANCHOR_HIST 15.2；盲區誤鎖秒 9.6、10.0；跟對率 0.8238、0.782 |
| S3 | Agent 各組 vs R-N | **未計算（X13）** | R-N 的 24 個輸出已產出，但沒有接進 verdict |
| S4 | DEANCHOR vs AO_ORIG 機制 | **未計算（X13）**；只有失聯秒可描述 | `same_wrong_persistence_rate` 與重新出現點 top-1／top-3 不依賴 R-N，但 `verdict_e6`／`e6_verdict_run.py` 沒有實作。失聯秒來自 R3 的群組指標：AO_ORIG 73.1、DEANCHOR 78.7（描述性，非 S4 正式量） |
| S5 | P1、P2 較嚴盲區準則 | P1、P2 皆**不成立** | `S5_blind_ci_upper_lt_0`：97.5% 與 95% 都是 False |
| S6a | NO_IMAGE − SELECTED_AGENT | 探索性 | 錯人秒 +4.133（$p$=0.750）、跟對率 −0.020（0.469）、`full_track_dp_acc` +0.062（0.500）、盲區誤鎖秒 −8.067（0.070）；$p$ 為雙尾、未校正的符號翻轉 |
| S6b | NO_SPATIAL − SELECTED_AGENT | 探索性 | 錯人秒 +1.867（$p$=0.375）、跟對率 −0.010（0.375）、`full_track_dp_acc` −0.021（1.000）、盲區誤鎖秒 −0.800（0.875）；同上 |
| S6c | SIMLIVE_K1 | 未執行 | D403 決定不做 |

消融沒有 `BUDGET_SKIPPED`（`ablations_skipped` 為空；兩項 `budget-check` 皆 `fits: true`）。

## R2. 選組（預登 §2.2，D400）

- 現行收據 `BATCH3_FREEZE.json` 的 SHA-256 為 `2ecdeb61f45793ac6eaea18111a3bcd707077d71837b62c9dd0908c2fd9795db`。選組在第 1 層（錯人秒，容許差 1.0 s）就結束：最低值 11.6，只有 DEANCHOR_HIST_SUM 留下。三組都符合資格，`ineligible` 為空。
- 批 3 由機械閘門取代人工審查（偏離 X6）。`VERIFY_FREEZE.json`（`feb8a19f…a1bf`）的 10 項檢查全部 PASS，其中包括：
  - 選組重算結果與收據相同；
  - `code_commit_sha` 等於 HEAD，且工作樹乾淨；
  - `formal_separation` PASS；
  - 正式組上界 43.742427 ≤ 45，累計上界 85.192127 ≤ 90。
- Opus 的事後閘門核對（D402）：通過（E6 協調對話）。

## R3. 指標（預登 §3，每組 12 段家族彙總；Agent 組 K=3）

來源：`verdict/verdict_e6.json` 的 `groups` 欄位。

| 組別 | 跟對率 | 錯人秒 | 失聯秒 | 盲區誤鎖秒 | `full_track_dp_acc`（n） | `single_dp_acc` |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| B1 | 0.737 | 16.2 | 53.4 | 7.8 | 0.7083（48） | 未執行（X12） |
| R-N | UNKNOWN：未評分（X13） | 同左 | 同左 | 同左 | 同左 | 未執行（X12） |
| AO_ORIG | 0.629 | 25.1 | 73.1 | 33.2 | 0.375（48） | 未執行（X12） |
| DEANCHOR | 0.621 | 21.5 | 78.7 | 32.8 | 0.3542（48） | 未執行（X12） |
| DEANCHOR_HIST_SUM | 0.619 | 20.3 | 80.5 | 30.7 | 0.375（48） | 未執行（X12） |
| ＋NO_IMAGE（探索性） | 0.591 | 24.4 | 83.7 | 22.6 | 0.438（48） | — |
| ＋NO_SPATIAL（探索性） | 0.607 | 22.1 | 81.9 | 29.9 | 0.354（48） | — |
| AO_ORIG（敏感度，D406） | 0.618 | 24.4 | 76.6 | 31.5 | 0.375（48） | — |

- 依 `gt_regime` 分層的 `full_track_dp_acc`：

  | 組別 | VISIBLE（n=43） | FULL_BLIND（n=5） |
  | --- | ---: | ---: |
  | B1 | 0.698 | 0.800 |
  | AO_ORIG | 0.349 | 0.600 |
  | DEANCHOR | 0.326 | 0.600 |
  | DEANCHOR_HIST_SUM | 0.349 | 0.600 |

  `TRUE_DEPARTURE` 為 n=0（偏離 X2），沒有數字可報。
- IoU 保守準則（IoU ≥ 0.3）的穩健性：verdict 沒有輸出，UNKNOWN。
- provider 錯誤率（`data_quality`，錯誤數／呼叫數）：

  | 組別 | 錯誤／呼叫 | 錯誤率 |
  | --- | ---: | ---: |
  | AO_ORIG | 6／642 | 0.0093 |
  | DEANCHOR | 0／653 | 0 |
  | DEANCHOR_HIST_SUM | 1／655 | 0.0015 |
  | NO_IMAGE | 0／645 | 0 |
  | NO_SPATIAL | 8／657 | 0.0122 |
  | AO_ORIG（敏感度） | 25／642 | 0.0389 |

  所有組 timeout 0、`budget_denied` 0；失敗呼叫照預登 §7.2 算錯，不排除。
- 格式退回率：正式組的 verdict 沒有輸出，UNKNOWN。診斷 K=1 三組都是 0。

## R5. 資料分離與 GT 隔離

- `check_e6_data_separation.py --mode formal`：錄製凍結時 PASS（D401）。現行批 3 閘門內再跑一次也 PASS：`old_e3=16, diag=3, formal=12, unique_dps=48, effective_units=12, similar=6/6`。正式組執行**後**沒有再跑一次，UNKNOWN。
- GT 隔離違規（預登 §7.2 第 2 點）：診斷 K=1 三組的 `gt_violation_count` 都是 0。正式組的 verdict 沒有輸出這個計數，UNKNOWN。推論端只讀推論根目錄，GT 只在評分端讀（`--gt-root`）。

## R7. 預算

| 項目 | USD | 來源 |
| --- | ---: | --- |
| D375 基準 | 38.17 | |
| K=1 診斷（2a） | 3.2797 | `local/evidence/e6-arms-k1-20261127/ledger/usage.jsonl`（297 列） |
| 正式組 dry-run 上界（AO_ORIG＋DEANCHOR＋DEANCHOR_HIST_SUM） | 43.7424 | 8.6829＋16.1064＋18.9532；上限 45（偏離 X7） |
| AO_ORIG 實際（含 S12 k2／k3 重跑） | 6.9510 | `e6-formal-run-20261127/ledger-ao_orig/usage.jsonl`（666 列）；停在 S12 k2 時約 6.48（618 列），重跑約 0.47 |
| DEANCHOR＋DEANCHOR_HIST_SUM 實際 | 13.5154 | `arms/ledger/usage.jsonl`（1 308 列；兩組共用一份帳本，沒有拆分） |
| 消融 NO_IMAGE | 6.5238 | `ablation-NO_IMAGE/ledger/usage.jsonl`（645 列；dry-run 上界 10.5257） |
| 消融 NO_SPATIAL | 2.3011 | `ablation-NO_SPATIAL/ledger/usage.jsonl`（657 列；dry-run 上界 13.434） |
| **新增合計（ApiGuard 估計）** | **32.571** | 上面五列相加 |
| **累計（ApiGuard 估計）** | **70.741** | 38.17＋32.571；≤ 90 |

平台對帳由使用者在 2026-11-27 讀取 OpenAI 平台（D413）：
- 累計 48.22，取代上面的估計值，剩餘 41.78。
- 調整檔是 LOCAL `local/evidence/api-usage/RECONCILIATION_20261127.json`，SHA-256 `3035e4bea6fbe01b241ad57c527d845cf7300c0b3bdce0d4adb8a3a2c30a8759`。
- 平台讀數無法拆出 E6 單獨的費用，UNKNOWN。
- 差額推測來自兩點：快取折扣沒有計價、帳本採用上界估計。這個推測沒有核對過。

## R8. 偏離列表

X1–X11 在任何組別分數產生前定案；X12、X13 是執行後發現的分析缺漏，不改判定。

| # | 偏離 | 預登條文 | 決策 | 處理與對結論的影響 |
| --- | --- | --- | --- | --- |
| X1 | **DC1 起點修正**：7/12 段規格起點與引擎不相容，改用修正起點錄製 | §6 劇本規格 | D399 | 規格欄位不改；修正起點逐段列在 [`E6_ROUTES_RECORDING_20261127.md`](E6_ROUTES_RECORDING_20261127.md)。錄製前定案 |
| X2 | **DC3 S11-DP3／DP4 宣告 `FULL_BLIND`**：引擎中目標不會離場，`TRUE_DEPARTURE` 分層 n=0 | §6、§3.1 `gt_regime` | D399、D401 | 不改引擎；`TRUE_DEPARTURE` 分層不報數字，列為已知限制 |
| X3 | **DC7 干擾者最高 2.1 m/s** | §6 | D399 | 列為限制（干擾者速度範圍窄於規格意圖） |
| X4 | **S12 tail_s 1.0**：S12-DP4（tick 136）的 3.0 s 窗超出 30 s，錄製延長 1.0 s（156 tick） | §6（約 30 s） | D401 | 路線與軌跡不變；routes JSON `frozen_by` 文字不精確，以錄製文件為準，凍結檔不重算 |
| X5 | **選組平手解讀**：三組時每層保留與最佳者差 ≤ 容許值的全部組別；平均跟對率＝3 段各自跟對率的算術平均 | §2.2 | D400 | 釐清非改規則；兩組時與原文等價。在任何診斷輸出前定案 |
| X6 | **批 3 改機械閘門＋使用者事前同意**：`e6_select_arm.py verify-freeze`（重算選組逐欄比對、prompt／參數 SHA、`code_commit_sha`＝HEAD、資料分離、上限、累計）取代人工審查 | §0「批 3 審查通過並經使用者同意」 | D402 | 使用者原話「先設計好一次跑完，可以接受含費用的」；Opus 事後閘門核對通過（R2） |
| X7 | **正式上限 USD 32 → 45** | §7.1、§7.2 第 5 點 | D404 | 只改 `FORMAL_CAP_USD`／`MAX_FORMAL_USD`（#748 `a9418fdf`）；累計上限 90、選組、評分不變。因 `code_commit_sha` 檢查，在新 commit 重新凍結（見 R8.1） |
| X8 | **S04／S07 B1 無 ACQUIRE → 所有組無種子**：R-N 輸出 `seed: null`、`seed_status: NO_B1_ACQUIRE`；Agent 組共用同一種子規則，兩段都不啟動、不呼叫 API | §2.1（R-N 同種子 tick） | D405 | #750 `a25a2124`；不換替代種子、不重錄。兩段**所有組配對差依構造為 0**，仍留在分母（不剔除），會把效果量往 0 拉，列為已知限制 |
| X9 | **新空帳本** `local/evidence/e6-run-ledger-20261127/`，不用舊 `local/evidence/api-usage`（est 合計 22.40、最後一列 2026-11-20，已含在 D375 基準 38.17 內，續用會重複計） | §7.1 累計基準 | 協調者接受（記於 EXP_RUN §4） | 累計＝38.17＋各步驟帳本（R7）；平台對帳見 R7（D413） |
| X10 | **S12 AO_ORIG k2 DNS 失敗只重跑 k2／k3**：24 次呼叫中 18 次 `URLError [Errno 8]`（請求未離開本機）、1 次 timeout、5 次 OK；k3 未跑 | §7.2 第 4 點（provider 錯誤記缺漏、不重跑） | D406 | 用戶端網路故障不算 provider 錯誤；原檔改名保留在 `local/evidence/e6-formal-run-20261127/ao_orig-aside-infra/E6-S12/`。主分析用重跑的 k2／k3，敏感度分析用原 k2 另算一次 verdict，兩者並列（R1.1）：**P1、P2 判定都沒變**。兩次分析沒有事前雜湊，證據是事後 MANIFEST 驗證、輸入逐檔比對和 mtime |
| X11 | **D403 消融為探索性**：NO_IMAGE → NO_SPATIAL，只對 SELECTED_AGENT、12 段、K=3；SIMLIVE_K1 不做 | §1.2 S6、§7.1 條件項 | D403 | 不進 P1／P2 Holm，只報與 SELECTED_AGENT 的配對差與未校正 $p$（R1.2）；兩項都在預算內執行 |
| X12 | **預登 §3.2 單次配對未執行**：`single_dp_acc` 與 McNemar 沒有計算 | §3.2（單次配對、共用先驗快照） | D412 | `scripts/evaluation/e6_verdict_run.py`:12（docstring）與 :103 把 `single_correct` 寫死成 `None`，因為 Stage 2c 沒有產出所需的 K=1 配對快照。`verdict_e6.json` 中各組 `n = 0`、McNemar `n_paired = 0`、`p_two_sided = 1.0` 是**未執行**，**不是結果，不得報告**。C3 的唯一主終點是 `full_track_dp_acc`，P1／P2 判定不受影響。補跑在 [#765](https://github.com/Polalalabear/amidst/issues/765) |
| X13 | **預登 S3、S4 未計算**：verdict 沒有接 R-N 輸出，也沒有實作 S4 的機制量 | §1.2 S3、S4；§2 表 R-N「正式 12 段（機制對照）」 | 協調對話（2026-11-27） | S3：`e6_verdict_run.py --runs` 只給了 `b1`、`ao_orig`、`arms`。R-N 已產出（`rn/`，24 個輸出＋`STATUS.json`，樹雜湊 `e4da4b6dcff1f2b62d6b87de893af838c39a69e4eecb776bf607fef3243dab00`），但沒有評分。S4：不依賴 R-N；`same_wrong_persistence_rate` 與重新出現點 top-1／top-3 在 `verdict_e6`／`e6_verdict_run.py` 都沒有實作（程式中找不到這兩個量），只有失聯秒可從群組指標描述。兩者都是次要／探索性，不影響 P1／P2 判定。零費用的事後評分併入 [#765](https://github.com/Polalalabear/amidst/issues/765) 一起處理 |

### R8.1 批 3 收據沿革（LOCAL，完整 SHA-256）

| 凍結 | main commit | 資料夾（`local/evidence/…`） | `BATCH3_FREEZE.json` | `VERIFY_FREEZE.json` | `MANIFEST.sha256` 的 SHA-256 | 結果 | 狀態 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `71633fb866d71a2961e8d1b384d18932f3faa50e`（#741） | `e6-batch3-freeze-20261127-superseded-71633fb8/` | `313441a73aa0e14f69409775285a0b67c20d1a472b594a1e8741ca2070ba1fa3` | `af1d73a2ae7d48512011c121b6478b555ce75d1a42236f32d0b7ae5e699737c3` | `dc01e1242b16bcfad9ca8c3fd6593d42e0a0b1b4d4763cd7ba650030d7265800` | 9 項 PASS；`FORMAL_OVER_CAP 43.74 > 32` → exit 6，正式付費 0 | superseded |
| 2 | `a9418fdfb9a4bf8bec6031be1201da33c02fcff3`（#748） | `e6-batch3-freeze-20261127-superseded-a9418fdf/` | `8806e8f6dde788567aa18e60d5f11b20b0a1448ecd1b1190bcd7c760de985643` | `b3f64f6af8eb3ea4faa86c4e6e72049849c1f53c19a526c4c96d72eae93fa71e` | `5228d708818a12b961faff120104120ba48edf1f796846f456b3785503255171` | 10 項 PASS；之後 R-N 在 S04／S07 StopIteration（X8），正式付費 0 | superseded |
| 3 | `a25a212424c268c96a31efe8bb59f08a32cff729`（#750） | `e6-batch3-freeze-20261127/` | `2ecdeb61f45793ac6eaea18111a3bcd707077d71837b62c9dd0908c2fd9795db` | `feb8a19fe889c3fc41dfd723dd3edb22bb83a82837ac803d748c391e0e06a1bf` | `92ee86225dabe873e11501d80cb6d2505004bf011031a4172d736c62c3c387bd` | 10 項 PASS → 正式組執行 | **現行** |

三次的 `SELECTED_AGENT` 都是 `DEANCHOR_HIST_SUM`。舊收據改名保留、不刪。

## R9. 已知限制（報告必寫）

1. `TRUE_DEPARTURE` 分層 n=0（X2）；干擾者 ≤ 2.1 m/s（X3）。
2. S04／S07 所有組無種子，配對差依構造為 0，仍留在分母，會把效果量往 0 拉（X8，D405）。
3. $M=12$ 的檢定力有限（預登 §4.5）。P1 是「無法判斷」，不得寫成「無差異」。
4. S12 AO_ORIG 的主分析與敏感度分析並列，判定都沒變；兩者沒有事前雜湊（X10）。
5. 批 3 為機械閘門而非人工審查（X6）；正式上限是 45 而非 32（X7）。
6. 單次配對 `single_dp_acc`／McNemar 未執行（X12）；S3、S4 未計算（X13）。補跑在 #765 之前，這些欄位不報告。
7. S07 紅色偵測偏多，原因 UNKNOWN（未調查）。
8. 正式組的格式退回率、GT 隔離違規計數，以及執行後的資料分離檢查，verdict 都沒有輸出，UNKNOWN（R3、R5）。
9. 花費的 ApiGuard 估計（累計 70.741）已由平台對帳（48.22，D413）取代；E6 單獨的平台費用 UNKNOWN（R7）。
10. 結論：**改良後未證實優於現有規則**（P2 不成立）；去錨定相對原版 Agent 無法判斷（P1）；消融僅為探索性。身分 `UNCONFIRMED`。
