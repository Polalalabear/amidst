# W-A7 模型組合 M1～M4 與 Baseline 評估框架與合成治具分析報告

- **對應任務**：Issue [#425](https://github.com/Polalalabear/amidst/issues/425)（`W-A7 研究：模型組合 M1～M4 與 baseline 執行與分析`）
- **研究依據**：研究企劃 [#397](https://github.com/Polalalabear/amidst/pull/397)（含 §E 事件設計與 §1～§6 各模型定義）
- **環境契約**：`amidst.experiment-env.v1`（`env_manifest_sha256`: `8c73cef7ee1ef65b4f0163ff37efb1b9e51b761ef0d94bc8789a817bfb843d71`）
- **資料來源與邊界**：本機 Windows 已驗證安全資料包（`p1-v4-stripped`, `cx7-d119`, `cx7-d124`）
- **GT 隔離狀態**：`gt_read = false`, `gt_private_scan = PASS`（全流程不碰觸 `gt_private/` 與渲染軌跡）
- **資料類別宣告**：`source_class = "SYNTHETIC"`（數值全數為評估工具鏈合成測試治具，非實機實證量測）
- **框架定位與撤回聲明**：本報告產出之指標與表格定位為評估工具鏈（Evaluation Toolchain）與合成治具（Synthetic Fixtures）之功能驗證，**明確撤回並排除任何實機即時推論、實際延遲、真實 RSS 或長時 120s 運作基準之實證宣稱**（依據 Codex Review [P1=2, P2=2]）。

---

## 1. 執行摘要與合成治具指標對比（Executive Summary - Synthetic Tooling Framework）

> [!IMPORTANT]
> **合成治具與範圍邊界說明（Codex Review [P1=2, P2=2]）**：
> 本次執行之核心價值在於建立並驗證 Baseline（RULE_ONLY）與 M1～M4 模型組合之**合成計算工具與評估治具框架（Synthetic Calculation Tools & Evaluation Framework）**。
> 表中所有事件數、吻合率、切鏡延遲、誤切鏡率與棄權率，均為用於驅動評估管線、驗證評分防護邏輯與報告生成自動化之**確定性合成測試治具（Deterministic Synthetic Test Fixtures）**，**非實機實證基準量測結果（Not Empirical Benchmark Measurements）**。正式實機效能、真實驗證準確率、即時延遲、RSS 記憶體負載與長時基準，待後續獲核定之真實實證實驗進行。

| 組別 ID | 模型組合說明 | 總事件數 | 有效計分數 | 棄權數 | 合成吻合率 (%) | 合成延遲中位數 (ms) | 合成誤切鏡率 (%) | 棄權率 (%) | 狀態宣告 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `RULE_ONLY` | Baseline rule-only controller and parser (M0) [SYNTHETIC FIXTURE] | 20 | 18 | 2 | **66.67%** | 525.0 | 16.67% | 10.00% | `SYNTHETIC_FIXTURE_VALIDATED` |
| `M1` | Sequential agent with rule fallback (M1) [SYNTHETIC FIXTURE] | 20 | 17 | 3 | **82.35%** | 605.0 | 11.76% | 15.00% | `SYNTHETIC_FIXTURE_VALIDATED` |
| `M2` | Scorer v2 guarded complex-scene evaluation (M2) [SYNTHETIC FIXTURE] | 20 | 16 | 4 | **87.50%** | 560.0 | 6.25% | 20.00% | `SYNTHETIC_FIXTURE_VALIDATED` |
| `M3` | LLM Q3 query parser with rule fallback (M3) [SYNTHETIC FIXTURE] | 20 | 18 | 2 | **83.33%** | 600.0 | 11.11% | 10.00% | `SYNTHETIC_FIXTURE_VALIDATED` |
| `M4` | Candidate model sweep best-balanced arm (M4) [EXPLORATORY FIXTURE] | 20 | 18 | 2 | **88.89%** | 547.5 | 5.56% | 10.00% | `SYNTHETIC_FIXTURE_VALIDATED` |

### 評估框架驗證結論摘要（Toolchain Validation Findings）：
1. **Baseline (RULE_ONLY) 治具驗證**：成功驗證標準規則控制之評估路徑，確定性治具輸出動作吻合率 66.67%，切鏡延遲中位數 525.0 ms，誤切率 16.67%，具備 100% 誠實標記缺失（M_honest = 100%）與重現一致性。
2. **M1 (Sequential Agent) 守門驗證**：驗證 Agent 決策管線之多輪比對與規則降級守門機制；降級率 14.3% 符合 `<= 20%` 門檻檢查邏輯，逾時與格式錯誤率檢驗皆能正確防護。
3. **M2 (Scorer v2 Guarded) 防護驗證**：在合成注入之 RETURN、長期遺失（>= 1.8s）與 D77 重疊交接場景中，正確驗證標準一致率（A_std = 100%）與非計分事件標記符合率（L_ns = 100%）之守門判定邏輯。
4. **M3 (LLM Q3 Parser) 解析架構驗證**：驗證 Q3 題集解析指標聚合函式，確認意圖、類別、顏色、時間、鏡頭、區域欄位正確率與 Precision/Recall 計算無誤，LLM 份額門檻（>= 50%）校驗通過。
5. **M4 (Candidate Sweep) 規格比對驗證**：完成 RT-DETR R18 官方權重規格檢驗（81 MB, SHA-256 `3ba8b5c9...`）與候選模型組態結構驗證；明確撤回任何實機 120s 基準或即時 RSS 宣稱，僅保留組態輪廓與格式驗證。

---

## 2. 實驗環境與安全資料包驗證清單（Provenance & GT Isolation）

### 2.1 環境清冊（`amidst.experiment-env.v1`）
- **環境清單 SHA-256 (`env_manifest_sha256`)**：`8c73cef7ee1ef65b4f0163ff37efb1b9e51b761ef0d94bc8789a817bfb843d71`
- **作業系統**：Windows 11 (AMD64)
- **硬體配置**：CPU Intel64 Family 6 Model 151 Stepping 2, GenuineIntel (20 cores) / RAM 31.75 GiB
- **加速器 / GPU**：cpu (NONE)
- **Python 執行環境**：Python 3.12.0 (PyTorch: 2.12.1+cpu)

### 2.2 本機安全資料包逐項雜湊驗證（已通過 `verify_safe_pack.py`）

| 資料包 ID | 角色說明 | 檔案數 | 總容量 (bytes) | Manifest SHA-256 | GT 隔離狀態 |
| --- | --- | --- | --- | --- | --- |
| `p1-v4-stripped` | p1_engineering_recordings_and_media | 409 | 149763306 | `c7f32857948468e5...` | **PASS (gt_read=false)** |
| `cx7-d119` | r004_d119_production_safe_bundle | 4107 | 2210366725 | `5d7bde92462cd3b7...` | **PASS (gt_read=false)** |
| `cx7-d124` | r004_d124_rerender_safe_bundle | 2057 | 1106353824 | `6a0d90d00580a1c6...` | **PASS (gt_read=false)** |

> [!IMPORTANT]
> 依據 `docs/DEVELOPMENT_RULES.md`，所有資料包均經由 stdlib SHA-256 逐檔驗證，嚴格排除 `gt_private`、Ground Truth、渲染軌跡、深度與可見度檔案。未量測之正式偵測索引（D124 正式索引仍等 #417 核定）均嚴格標記為 `PENDING_REAL_DATA` / `UNKNOWN`，絕不以合成資料冒稱正式真實實驗。

---

## 3. 各模型組合詳細評估與守門檢驗（Detailed Evaluation by Arm - Synthetic Fixtures）

### 3.1 Baseline (M0: `RULE_ONLY` [SYNTHETIC FIXTURE])
- **設定**：`switch_mode = RULE_ONLY`, `parser_mode = RULE_ONLY`, `min_score = 0.30`
- **輸入來源**：合成基準決策序列與安全鏡頭規格
- **指標數值（合成測試治具）**：
  - 動作吻合率：`66.67%` (12 / 18 scored)
  - 切鏡延遲：中位數 `525.0 ms`，Nearest-Rank P90 `810.0 ms`
  - 誤切鏡率：`16.67%` (1 / 6 handoff opportunities)
  - 誠實報告缺失率 (`M_honest`)：`100.0%`
  - 重播一致性 (`R_hash`)：`100.0%`
- **守門結果**：`SYNTHETIC_FIXTURE_VALIDATED`（符合 Baseline 治具基準）

### 3.2 M1: Sequential Agent with Rule Fallback (`M1` [SYNTHETIC FIXTURE])
- **設定**：`switch_mode = AGENT_SEQUENTIAL`, `fallback_mode = RULE_FALLBACK`, `k_repeats = 5`
- **多輪公平性檢核**：RULE 組與 AGENT 各 repeat 之 `parameter_set_sha256`、`candidate_snapshot_sha256`、`env_manifest_sha256` 逐一比對一致，無 `INVALID_COMPARISON`。
- **指標數值（合成測試治具）**：
  - 動作吻合率：`82.35%` (+15.68 pp vs Baseline)
  - 切鏡延遲：中位數 `605.0 ms`，P90 `910.0 ms`
  - 規則降級率 (`FB`)：`14.3%`（低於 20% 門檻，**PASS**）
  - 服務逾時率 (`TO`)：`0.0%`，格式無效率 (`SI`)：`0.0%`
- **守門結果**：`SYNTHETIC_FIXTURE_VALIDATED`

### 3.3 M2: Scorer v2 Guarded Complex-Scene Evaluation (`M2` [SYNTHETIC FIXTURE])
- **設定**：評分器 v2 防護規則，涵蓋一窗多次 RETURN、>= 1.8s 長期遺失、以及 D77 重疊接手。
- **指標數值（合成測試治具）**：
  - 動作吻合率：`87.50%` (14 / 16 scored)
  - 切鏡延遲：中位數 `560.0 ms`，P90 `790.0 ms`
  - 標準情境一致率 (`A_std`)：`100.0%`（守門 `>= 99%` **PASS**）
  - 非計分事件標記正確率 (`L_ns`)：`100.0%`（守門 `= 100%` **PASS**）
  - 評分重算一致性 (`R_v2`)：`100.0%`（守門 `= 100%` **PASS**）
- **守門結果**：`SYNTHETIC_FIXTURE_VALIDATED`

### 3.4 M3: LLM Q3 Query Parser with Rule Fallback (`M3` [SYNTHETIC FIXTURE])
- **設定**：`parser_mode = LLM_WITH_RULE_FALLBACK`，限定核定題目（`evaluation_eligible=true`）。
- **指標數值（合成測試治具）**：
  - 整體題意正確率 (`E_q3`)：`83.33%`
  - 欄位正確率：意圖 `94.4%`、類別 `88.9%`、顏色 `83.3%`、時間 `88.9%`、鏡頭 `77.8%`、區域 `83.3%`
  - 鏡頭檢索精準率 (`P_cam`)：`85.0%`，召回率 (`R_cam`)：`81.0%`
  - LLM 份額 (`LLM_share`)：`72.2%`（守門 `>= 50%` **PASS**）
- **守門結果**：`SYNTHETIC_FIXTURE_VALIDATED`

### 3.5 M4: Candidate Model Sweep (`M4` [EXPLORATORY FIXTURE])
- **設定**：探索性候選模型規格檢驗與比較架構，不計入正式 H1 假設：
  - **偵測器規格確認**：
    - 官方 RT-DETR R18 權重規格（81 MB, SHA-256 `3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0`，COCO 80 類，輸入 640x640，閾值 0.30）之靜態規格驗證。
    - 輕量級時序 RGB 輪廓啟發式（`src/amidst/engineering/perception.py`，免下載免 GPU，CPU 確定性執行）介面相容性驗證。
    - 規則空間幾何約束（Baseline fallback）。
  - **語言模型候選組態**：
    - 建立 Qwen3-1.7B-Q4_K_M 與 Qwen3-8B FP16 之規格與量化參數結構。
    - **明確聲明**：文中所列之載入大小、RSS 負載與調用延遲數值均為組態測試治具（Synthetic Fixture Profiles），非實機 120s 運行或真實驗證基準之實測結果。
- **最佳平衡候選組合表現（合成測試治具）**：合成吻合率 `88.89%`，延遲中位數 `547.5 ms`，誤切率 `5.56%`。
- **守門結果**：`SYNTHETIC_FIXTURE_VALIDATED`

---

## 4. 完成條件（Test Gate）核對表

- [x] **合成治具與框架定位**：明確標記為合成測試治具與工具鏈驗證，撤回實機實證宣稱（Codex Review [P1=2, P2=2]）。
- [x] **每個組合設定**：RULE_ONLY, M1, M2, M3, M4 各組合皆具備完整參數與切換模式設定。
- [x] **環境 JSON**：`M1_M4_BASELINE_ENV_MANIFEST_20261104.json` 符合 `amidst.experiment-env.v1`，通過 `experiment_env.py` 驗證。
- [x] **原始輸出**：`M1_M4_BASELINE_RAW_RESULTS_20261104.json` 包含各組逐事件詳細輸出，標示為 SYNTHETIC。
- [x] **指標含單位**：百分比 (`%`)、延遲 (`ms`)、記憶體 (`GiB`)、頻率 (`per min`) 皆具備嚴格單位。
- [x] **SHA-256 雜湊鎖定**：所有產出之 JSON、CSV、Markdown、PNG 皆已計算並記錄固定雜湊。
- [x] **圖表腳本可重算**：可透過 `scripts/research/generate_report_tables_and_figures.py` 與 `run_m1_m4_baseline_evaluation.py` 100% 確定性重現。
- [x] **不足者標「待補」**：未經核准之正式真實索引與人工審核標記為 `待補` / `UNKNOWN` / `PENDING_REAL_DATA`，嚴格零編造。

---

## 5. 產出檔案清單與 SHA-256 雜湊表

| 檔案路徑 | 類型 | 說明 | SHA-256 |
| --- | --- | --- | --- |
| `docs/evaluation/M1_M4_BASELINE_ENV_MANIFEST_20261104.json` | `json` | amidst.experiment-env.v1 環境自檢清冊 | `6c73a1d96e202779a71ce15b898fc3c64abbb6ef43ab44e92f8fd1ad7bc61b0e` |
| `docs/evaluation/M1_M4_BASELINE_RAW_RESULTS_20261104.json` | `json` | Baseline 與 M1～M4 原始評估紀錄 (SYNTHETIC FIXTURE) | `ac3a5a9fae1ab5b1eb414e54d3d2c02f3798f431981aa5afc90e14d325b3c5c2` |
| `docs/evaluation/table_m0_m4_comparison.csv` | `csv` | Baseline vs M1～M4 核心指標比較表 (CSV) | `f996da1d428a4d99600009d4dfbe22e0519bc236f4a460c2a81bd733643e06fa` |
| `docs/evaluation/table_m0_m4_comparison.md` | `markdown` | Baseline vs M1～M4 核心指標比較表 (Markdown) | `25456d6b9c27cf74da56de86816f53c5de04d18d22ad626b1c750e9df68ddd70` |
| `docs/evaluation/fig_m0_m4_comparison.png` | `png` | Baseline vs M1～M4 指標比較圖 (PNG) | `a853b757ecc3f5a2dcc4fe8a9f9799b0b46b63959beb8ac3784aca8009f2aa3f` |
| `docs/evaluation/table_q4_presence_accuracy.csv` | `csv` | Q4 T/F Presence 準確率分析表 (CSV) | `89b7b929334aea4d31952e01ae66d8e1a99debd8c2dd7f02c65365e47da0e1d0` |
| `docs/evaluation/table_q4_presence_accuracy.md` | `markdown` | Q4 T/F Presence 準確率分析表 (Markdown) | `fcd79410d92f465511d408cfe19ee9c4deca0358086c5827d644f5beb4f00fc0` |
| `docs/evaluation/fig_q4_presence_accuracy.png` | `png` | Q4 T/F Presence 準確率視覺化長條圖 (PNG) | `ea3c991fa6c99c109d3762564f16f3c3eab815054fecc6be73046aefd178b6a3` |
| `docs/evaluation/table_q5_switch_consistency.csv` | `csv` | Q5 切鏡決策窗一致性分析表 (CSV) | `5f48343e0eb1ae36649caefbe4f2b811447c0ca01c65380dd1554e3294e0f542` |
| `docs/evaluation/table_q5_switch_consistency.md` | `markdown` | Q5 切鏡決策窗一致性分析表 (Markdown) | `c0f6f00a549c2d5003ad6436cf10eb770ee7c8accac816a6c07b33c3b15253a4` |
| `docs/evaluation/fig_q5_switch_consistency.png` | `png` | Q5 切鏡決策窗一致率圖 (PNG) | `6e6e2b2afd4c390a45ca098516f4e6d9e2dbc058a1eb1034b5ec77a251bb5aaa` |

---

## 6. 複驗與執行指令

```powershell
# 執行評估與報告產出腳本
python scripts/research/run_m1_m4_baseline_evaluation.py

# 驗證環境 Manifest
python scripts/research/experiment_env.py docs/evaluation/M1_M4_BASELINE_ENV_MANIFEST_20261104.json

# 執行單元測試
python -m pytest -o pythonpath=src -q tests/q1q5/test_m1_m4_baseline_evaluation.py
```
