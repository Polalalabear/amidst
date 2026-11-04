# 研究報告用的分析與圖表腳本說明與合成預覽 v1

Refs: Issue #427 (`W-A9 研究報告用的分析與圖表腳本`), PR #397, PR #407, Issue #416 (`W-C5`), Issue #425 (`W-A7`).

> **資料來源與證據邊界聲明**：
> - 本文件展示之數值與圖表雜湊均由 `--synthetic` 合成 fixture 輸入產生（`data_origin: "SYNTHETIC"`），僅供驗證表格計算邏輯、缺值處理與決定性圖表重現性，**非正式實驗證據**。
> - **真實實驗數字目前為 `待補 / UNKNOWN`（`PENDING_REAL_DATA`）**，需待 `#416`（W-C5 複雜場景收斂與評分）與 `#425`（W-A7 M1～M4 真實跑批與資料收集）完成後，以 `--input-dir` 傳入凍結實驗輸出重算。
> - 腳本絕不讀取 Ground Truth、原始錄影或 RGB 影像；任何未量測或缺漏欄位一律標示為 `PENDING_REAL_DATA` 或 `UNKNOWN`，絕不補值或捏造數字。

---

## 1. CLI 用法與重算方式

### 1.1 合成資料驗證模式（`--synthetic`）

```bash
python scripts/research/generate_report_tables_and_figures.py \
  --synthetic \
  --out /tmp/report_synthetic_preview
```

### 1.2 真實實驗輸出目錄模式（`--input-dir`）

當 `#416`（W-C5）與 `#425`（W-A7）產出真實實驗結果後，將結果目錄傳入 `--input-dir`：

```bash
python scripts/research/generate_report_tables_and_figures.py \
  --input-dir /path/to/frozen_experiment_outputs \
  --out /path/to/report_artifacts
```

`--input-dir` 讀取以下三個選填結果檔（若任一檔案或組別尚未產出，對應列自動標為 `data_status = PENDING_REAL_DATA`、數值欄填 `UNKNOWN`，且 `manifest.json` 標記 `data_origin: "PENDING_REAL_DATA"`）：
- `m0_m4_events.json`：`{"events": [...]}`（包含 `RULE_ONLY`、`M1`、`M2`、`M3`、`M4` 各組事件紀錄）
- `q4_presence.json`：`{"samples": [...]}`（包含 `A4-1`、`B4-1`、`COMPLEX` 各層人工 T/F 審核紀錄）
- `q5_switch_windows.json`：`{"windows": [...]}`（包含 `KEEP`、`HANDOFF`、`LOST`、`ABSTAIN` 決策窗對齊紀錄）

**真實資料契約與邊界防禦規則**：
1. **來源與資格鎖定**：每個輸入檔計算 SHA-256 並記錄於 `manifest.json` 的 `source_pins` 與 `input_files`。若輸入檔頂層標記 `data_origin: "SYNTHETIC"`，或 `evaluation_eligible: false`，或 `pilot: true`，腳本完整保留其來源與資格狀態，**絕不升格為 `REAL_DATA`**；僅當檔案具備 `data_origin: "REAL_DATA"`、`evaluation_eligible: true` 且非 pilot 時，方納入真實安全包（Safe Pack）統計。
2. **缺欄位不補值（Fail-Closed）**：未量測或缺欄位（例如僅有 `{"arm_id": "M1"}`）絕不當成 False 或 0%。必填欄位缺漏時計數與比率一律標示為 `UNKNOWN`，行狀態標記為 `PENDING_REAL_DATA`。
3. **F1 分數指標邊界**：使用精確公式 $F_1 = 2\text{TP} / (2\text{TP} + \text{FP} + \text{FN})$。當分母 $2\text{TP} + \text{FP} + \text{FN} > 0$ 且 $\text{TP} = 0$ 時，F1 精確傳回 `0.00%`（分開處理零 F1 與未定義分母）；僅當分母為 0（完全無正例且無預測正例）時，F1 方傳回 `UNKNOWN`。
4. **純靜態決定性繪圖**：所有圖表均使用純 Python 標準庫（`zlib` + `struct`）自幹 5x7 點陣與幾何光柵化器，零網路相依、零字型引擎變異，確保不同平台逐位元組（byte-for-byte）結果完全相同。

---

## 2. 輸出表格 Schema 與圖表規格

### 2.1 表 1 與圖 1：Baseline (`RULE_ONLY`) vs `M1`～`M4` 比較
- **檔案**：`table_m0_m4_comparison.csv`、`table_m0_m4_comparison.md`、`fig_m0_m4_comparison.png`
- **欄位定義**：
  - `arm_id`：實驗組別（`RULE_ONLY`、`M1`、`M2`、`M3`、`M4`）
  - `model_combination`：模型與規則組合說明
  - `data_status`：`SYNTHETIC`、`REAL_DATA` 或 `PENDING_REAL_DATA`
  - `n_events_total`：該組總事件數
  - `n_events_scored`：進入計分分母之有效事件數（排除 `abstained=true` 與 `match=UNKNOWN`）
  - `n_events_abstained`：棄權（`ABSTAIN`）事件數
  - `action_match_rate_pct`：動作吻合率（`100 * matched / n_events_scored`）
  - `switch_latency_median_ms`：成功切鏡事件延遲中位數（ms）
  - `switch_latency_p90_ms`：成功切鏡事件延遲 Nearest-Rank P90（ms）
  - `false_handoff_rate_pct`：誤切鏡率（`100 * false_handoffs / handoff_opportunities`）
  - `abstention_rate_pct`：棄權率（`100 * n_events_abstained / n_events_total`）
- **圖表說明（`fig_m0_m4_comparison.png`）**：以純 Python 決定性光柵器（`zlib` + `struct`）繪製 `RULE_ONLY` 與 `M1`～`M4` 的三項核心百分比指標（Action Match Rate、False Handoff Rate、Abstention Rate）分組長條圖；缺值組別以斜線空心框標示 `UNK`。

### 2.2 表 2 與圖 2：Q4 T/F Presence 準確率分析
- **檔案**：`table_q4_presence_accuracy.csv`、`table_q4_presence_accuracy.md`、`fig_q4_presence_accuracy.png`
- **欄位定義**（對齊 `docs/evaluation/Q4_PRESENCE_EVAL_V1.md`）：
  - `stratum`：評估分層（`A4-1`、`B4-1`、`COMPLEX`、`ALL`）
  - `data_status`：`SYNTHETIC`、`REAL_DATA` 或 `PENDING_REAL_DATA`
  - `n_total`：抽樣總數
  - `n_decided`：人工已判定 T/F 的有效分母（`tp + fp + tn + fn`）
  - `tp`、`fp`、`tn`、`fn`：四格混淆計數
  - `n_unknown`：人工填 `UNKNOWN` 或缺審之樣本數（排除於 `n_decided` 分母外，絕不當成 TN 或 FP）
  - `accuracy_pct`：`100 * (tp + tn) / n_decided`
  - `precision_pct`：`100 * tp / (tp + fp)`
  - `recall_pct`：`100 * tp / (tp + fn)`
  - `f1_pct`：`2 * precision * recall / (precision + recall)`
  - `unknown_rate_pct`：`100 * n_unknown / n_total`
- **圖表說明（`fig_q4_presence_accuracy.png`）**：繪製各分層與總計（`ALL`）之 Accuracy、Precision、Recall 與 UNKNOWN Rate 分組長條圖。

### 2.3 表 3 與圖 3：Q5 切鏡決策窗一致性分析
- **檔案**：`table_q5_switch_consistency.csv`、`table_q5_switch_consistency.md`、`fig_q5_switch_consistency.png`
- **欄位定義**（對齊 `docs/evaluation/Q5_SWITCH_EVAL_V1.md`）：
  - `decision_category`：決策窗類別（`KEEP`、`HANDOFF`、`LOST`、`ABSTAIN`、`ALL`）
  - `data_status`：`SYNTHETIC`、`REAL_DATA` 或 `PENDING_REAL_DATA`
  - `n_windows_total`：決策窗總數
  - `n_windows_evaluated`：有效評分決策窗數（`n_agreed + n_disagreed`）
  - `n_agreed`、`n_disagreed`：與核定劇本決策窗一致／不一致之窗數
  - `n_unknown`：觀測結果為 `UNKNOWN` 之決策窗數（不計入 `n_windows_evaluated`）
  - `agreement_rate_pct`：決策窗一致率（`100 * n_agreed / n_windows_evaluated`）
  - `median_window_latency_ms`：一致決策窗之延遲中位數（ms）
- **圖表說明（`fig_q5_switch_consistency.png`）**：繪製 `KEEP`、`HANDOFF`、`LOST`、`ABSTAIN` 與 `ALL` 之決策窗一致率（`AGREE%`）長條圖。

---

## 3. 合成輸入預覽（`--synthetic` 驗證輸出，非正式實驗結果）

> **注意**：下表所有數據均標註 `data_status = SYNTHETIC`，真實數據待 `#416`（W-C5）與 `#425`（W-A7）完成後重算（目前真實數據狀態：`待補 / UNKNOWN`）。

### 3.1 `table_m0_m4_comparison`（合成預覽）

| arm_id | model_combination | data_status | n_events_total | n_events_scored | n_events_abstained | action_match_rate_pct | switch_latency_median_ms | switch_latency_p90_ms | false_handoff_rate_pct | abstention_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RULE_ONLY | Baseline rule-only controller (M0) | SYNTHETIC | 20 | 18 | 2 | 66.67 | 525.00 | 810.00 | 16.67 | 10.00 |
| M1 | Sequential agent with rule fallback (M1) | SYNTHETIC | 20 | 17 | 3 | 82.35 | 605.00 | 910.00 | 11.76 | 15.00 |
| M2 | Scorer v2 guarded complex-scene evaluation (M2) | SYNTHETIC | 20 | 16 | 4 | 87.50 | 560.00 | 790.00 | 6.25 | 20.00 |
| M3 | LLM Q3 query parser with rule fallback (M3) | SYNTHETIC | 20 | 18 | 2 | 83.33 | 600.00 | 900.00 | 11.11 | 10.00 |
| M4 | Candidate LLM model sweep best-balanced arm (M4) | SYNTHETIC | 20 | 18 | 2 | 88.89 | 547.50 | 790.00 | 5.56 | 10.00 |

### 3.2 `table_q4_presence_accuracy`（合成預覽）

| stratum | data_status | n_total | n_decided | tp | fp | tn | fn | n_unknown | accuracy_pct | precision_pct | recall_pct | f1_pct | unknown_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A4-1 | SYNTHETIC | 32 | 30 | 14 | 2 | 13 | 1 | 2 | 90.00 | 87.50 | 93.33 | 90.32 | 6.25 |
| B4-1 | SYNTHETIC | 30 | 28 | 12 | 3 | 11 | 2 | 2 | 82.14 | 80.00 | 85.71 | 82.76 | 6.67 |
| COMPLEX | SYNTHETIC | 30 | 25 | 10 | 3 | 9 | 3 | 5 | 76.00 | 76.92 | 76.92 | 76.92 | 16.67 |
| ALL | SYNTHETIC | 92 | 83 | 36 | 8 | 33 | 6 | 9 | 83.13 | 81.82 | 85.71 | 83.72 | 9.78 |

### 3.3 `table_q5_switch_consistency`（合成預覽）

| decision_category | data_status | n_windows_total | n_windows_evaluated | n_agreed | n_disagreed | n_unknown | agreement_rate_pct | median_window_latency_ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KEEP | SYNTHETIC | 21 | 20 | 18 | 2 | 1 | 90.00 | 205.00 |
| HANDOFF | SYNTHETIC | 18 | 17 | 14 | 3 | 1 | 82.35 | 615.00 |
| LOST | SYNTHETIC | 14 | 12 | 10 | 2 | 2 | 83.33 | 445.00 |
| ABSTAIN | SYNTHETIC | 10 | 9 | 8 | 1 | 1 | 88.89 | 260.00 |
| ALL | SYNTHETIC | 63 | 58 | 50 | 8 | 5 | 86.21 | 310.00 |

---

## 4. 決定性輸出 SHA-256 雜湊清單（`--synthetic` 模式）

在同一組 `--synthetic` 輸入下重複執行腳本，產出之 CSV、Markdown 與 PNG 檔案逐位元組（byte-for-byte）完全一致，`manifest.json` 記錄之固定 SHA-256 如下：

| 檔案名稱 | 類型 | 大小 (bytes) | SHA-256 |
| --- | --- | --- | --- |
| `table_m0_m4_comparison.csv` | `csv` | 686 | `549986576a09ac78e0716b521008592cd31d02624b74e7d6929767758f4bf562` |
| `table_m0_m4_comparison.md` | `markdown` | 1225 | `b7febc97691d349c559593c371d60ca8b7f133042f2e03273bec2ecd47c55329` |
| `fig_m0_m4_comparison.png` | `png` | 6144 | `8261f387eaaebb13c18ee0bc3eba6e09f5cd15cd81a1bdd3c07f3abc4d8a2d68` |
| `table_q4_presence_accuracy.csv` | `csv` | 372 | `9452f53ce84ee539ad674a28b47b354c37bbe343f743d8865691b3afe6b35e7d` |
| `table_q4_presence_accuracy.md` | `markdown` | 954 | `5309c64e6ce4c931dd21d7b38c62c19700dd9874cd6c65ec839c22df2a14abad` |
| `fig_q4_presence_accuracy.png` | `png` | 6511 | `622492e241a83f2c5f2706cbb642388c7254650c5aaf33072e24274e11fb8d11` |
| `table_q5_switch_consistency.csv` | `csv` | 349 | `6b301002dfd16daebf106f2d899d2f1fdd8916b92b31db07fcff2c1769453887` |
| `table_q5_switch_consistency.md` | `markdown` | 861 | `45b61067624be0709ba65e4c2d8fc388df44cb933a338e95db9b46ae9c359a93` |
| `fig_q5_switch_consistency.png` | `png` | 5932 | `e501e288528edac61405164cf085e57199372e252715139339a7466267943ff6` |

---

## 5. 聚焦測試指令

```bash
python -m pytest -o pythonpath=src -q tests/q1q5/test_research_report_figures.py
```
