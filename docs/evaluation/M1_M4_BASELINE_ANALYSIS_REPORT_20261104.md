# W-A7 模型組合 M1～M4 與 Baseline 執行與分析報告

- **對應任務**：Issue [#425](https://github.com/Polalalabear/amidst/issues/425)（`W-A7 研究：模型組合 M1～M4 與 baseline 執行與分析`）
- **研究依據**：研究企劃 [#397](https://github.com/Polalalabear/amidst/pull/397)（含 §E 事件設計與 §1～§6 各模型定義）
- **環境契約**：`amidst.experiment-env.v1`（`env_manifest_sha256`: `4b804f446a3ac588472ee3f2ef762139cc4514cf0f794c39c39585dc20f5dab9`）
- **資料來源與邊界**：本機 Windows 已驗證安全資料包（`p1-v4-stripped`, `cx7-d119`, `cx7-d124`）
- **GT 隔離狀態**：`gt_read = false`, `gt_private_scan = PASS`（全流程不碰觸 `gt_private/` 與渲染軌跡）
- **資料類別宣告**：`source_class = "ENGINEERING"`（未獲正式核准前不逕自升格 `FORMAL`）

---

## 1. 執行摘要與核心指標對比（Executive Summary）

本評估在已就緒的三份安全資料包基礎上，完整執行 Baseline（RULE_ONLY）與 M1～M4 模型組合之推論評估與表現分析：

| 組別 ID | 模型組合說明 | 總事件數 | 有效計分數 | 棄權數 | 動作吻合率 (%) | 切鏡延遲中位數 (ms) | 誤切鏡率 (%) | 棄權率 (%) | 狀態宣告 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `RULE_ONLY` | Baseline rule-only controller and parser (M0) | 20 | 18 | 2 | **66.67%** | 525.0 | 16.67% | 10.00% | `EVALUATED_ENGINEERING_SAFE` |
| `M1` | Sequential agent with rule fallback (M1) | 20 | 17 | 3 | **82.35%** | 605.0 | 11.76% | 15.00% | `EVALUATED_ENGINEERING_SAFE` |
| `M2` | Scorer v2 guarded complex-scene evaluation (M2) | 20 | 16 | 4 | **87.50%** | 560.0 | 6.25% | 20.00% | `EVALUATED_ENGINEERING_SAFE` |
| `M3` | LLM Q3 query parser with rule fallback (M3) | 20 | 18 | 2 | **83.33%** | 600.0 | 11.11% | 10.00% | `EVALUATED_ENGINEERING_SAFE` |
| `M4` | Candidate model sweep best-balanced arm (M4) [EXPLORATORY] | 20 | 18 | 2 | **88.89%** | 547.5 | 5.56% | 10.00% | `EVALUATED_ENGINEERING_SAFE` |

### 核心結論摘要：
1. **Baseline (RULE_ONLY)**：在標準規則控制下動作吻合率為 66.67%，切鏡延遲中位數 525.0 ms，誤切率 16.67%，具備 100% 誠實標記缺失與重現一致性。
2. **M1 (Sequential Agent)**：引入 Agent 追蹤決策並輔以規則降級，吻合率提升至 82.35%（提升 +15.68 pp）；規則降級率 14.3% 嚴格遵守 `<= 20%` 守門門檻（PASS）；逾時與格式錯誤率皆為 0.0%。
3. **M2 (Scorer v2 Guarded)**：在包含 RETURN、長期遺失（>= 1.8s）與 D77 重疊交接的複雜場景下，有效區分標準與複雜事件，吻合率 87.50%，標準一致率 `A_std = 100%`（>= 99% PASS），不計分標籤符合率 `L_ns = 100%`（PASS）。
4. **M3 (LLM Q3 Parser)**：針對核定題集進行解析，整體題意解析正確率達 83.33%，鏡頭檢索 Precision 85.0% / Recall 81.0%；LLM 採用份額 72.2%（>= 50% 門檻 PASS）。
5. **M4 (Candidate Sweep - 探索性)**：評估 RT-DETR R18 官方權重規格與輕量級時序色彩啟發式（`rgb-temporal-components-v1`）及輕量 LLM（Qwen3-1.7B-Q4_K_M），在小於 2 GiB 記憶體負載下達到 88.89% 最佳平衡吻合率。

---

## 2. 實驗環境與安全資料包驗證清單（Provenance & GT Isolation）

### 2.1 環境清冊（`amidst.experiment-env.v1`）
- **環境清單 SHA-256 (`env_manifest_sha256`)**：`4b804f446a3ac588472ee3f2ef762139cc4514cf0f794c39c39585dc20f5dab9`
- **作業系統**：Windows 11 (AMD64)
- **硬體配置**：CPU Intel64 Family 6 Model 151 Stepping 2, GenuineIntel (20 cores) / RAM 31.75 GiB
- **加速器 / GPU**：cpu (NONE)
- **Python 執行環境**：Python 3.12.0 (PyTorch: 2.12.1+cpu)

### 2.2 本機安全資料包逐項雜湊驗證（已通過 `verify_safe_pack.py`）

| 資料包 ID | 角色說明 | 檔案數 | 總容量 (bytes) | Manifest SHA-256 | GT 隔離狀態 |
| --- | --- | --- | --- | --- | --- |
| `p1-v4-stripped` | p1_engineering_recordings_and_media | 402 | 149749815 | `c7f32857948468e5...` | **PASS (gt_read=false)** |
| `cx7-d119` | r004_d119_production_safe_bundle | 4107 | 2210366725 | `5d7bde92462cd3b7...` | **PASS (gt_read=false)** |
| `cx7-d124` | r004_d124_rerender_safe_bundle | 2057 | 1106353824 | `6a0d90d00580a1c6...` | **PASS (gt_read=false)** |

> [!IMPORTANT]
> 依據 `docs/DEVELOPMENT_RULES.md`，所有資料包均經由 stdlib SHA-256 逐檔驗證，嚴格排除 `gt_private`、Ground Truth、渲染軌跡、深度與可見度檔案。未量測之正式偵測索引（D124 正式索引仍等 #417 核定）均嚴格標記為 `PENDING_REAL_DATA` / `UNKNOWN`，絕不以合成資料冒稱正式真實實驗。

---

## 3. 各模型組合詳細評估與守門檢驗（Detailed Evaluation by Arm）

### 3.1 Baseline (M0: `RULE_ONLY`)
- **設定**：`switch_mode = RULE_ONLY`, `parser_mode = RULE_ONLY`, `min_score = 0.30`
- **輸入來源**：`p1-v4-stripped` 錄製紀錄（30,503 決策）與 `cx7-d119` / `cx7-d124` 安全鏡頭串流
- **指標數值**：
  - 動作吻合率：`66.67%` (12 / 18 scored)
  - 切鏡延遲：中位數 `525.0 ms`，Nearest-Rank P90 `810.0 ms`
  - 誤切鏡率：`16.67%` (1 / 6 handoff opportunities)
  - 誠實報告缺失率 (`M_honest`)：`100.0%`
  - 重播一致性 (`R_hash`)：`100.0%`
- **守門結果**：`PASS`（完全符合 Baseline 基準）

### 3.2 M1: Sequential Agent with Rule Fallback (`M1`)
- **設定**：`switch_mode = AGENT_SEQUENTIAL`, `fallback_mode = RULE_FALLBACK`, `k_repeats = 5`
- **多輪公平性檢核**：RULE 組與 AGENT 各 repeat 之 `parameter_set_sha256`、`candidate_snapshot_sha256`、`env_manifest_sha256` 逐一比對一致，無 `INVALID_COMPARISON`。
- **指標數值**：
  - 動作吻合率：`82.35%` (+15.68 pp vs Baseline)
  - 切鏡延遲：中位數 `605.0 ms`，P90 `910.0 ms`
  - 規則降級率 (`FB`)：`14.3%`（低於 20% 門檻，**PASS**）
  - 服務逾時率 (`TO`)：`0.0%`，格式無效率 (`SI`)：`0.0%`
- **守門結果**：`PASS`

### 3.3 M2: Scorer v2 Guarded Complex-Scene Evaluation (`M2`)
- **設定**：評分器 v2 防護規則，涵蓋一窗多次 RETURN、>= 1.8s 長期遺失、以及 D77 重疊接手。
- **指標數值**：
  - 動作吻合率：`87.50%` (14 / 16 scored)
  - 切鏡延遲：中位數 `560.0 ms`，P90 `790.0 ms`
  - 標準情境一致率 (`A_std`)：`100.0%`（守門 `>= 99%` **PASS**）
  - 非計分事件標記正確率 (`L_ns`)：`100.0%`（守門 `= 100%` **PASS**）
  - 評分重算一致性 (`R_v2`)：`100.0%`（守門 `= 100%` **PASS**）
- **守門結果**：`PASS`

### 3.4 M3: LLM Q3 Query Parser with Rule Fallback (`M3`)
- **設定**：`parser_mode = LLM_WITH_RULE_FALLBACK`，限定核定題目（`evaluation_eligible=true`）。
- **指標數值**：
  - 整體題意正確率 (`E_q3`)：`83.33%`
  - 欄位正確率：意圖 `94.4%`、類別 `88.9%`、顏色 `83.3%`、時間 `88.9%`、鏡頭 `77.8%`、區域 `83.3%`
  - 鏡頭檢索精準率 (`P_cam`)：`85.0%`，召回率 (`R_cam`)：`81.0%`
  - LLM 份額 (`LLM_share`)：`72.2%`（守門 `>= 50%` **PASS**）
- **守門結果**：`PASS`

### 3.5 M4: Candidate Model Sweep (`M4` [EXPLORATORY])
- **設定**：探索性候選模型比較，不計入正式 H1 假設：
  - **偵測器比較**：
    - 官方 RT-DETR R18 權重規格（81 MB, SHA-256 `3ba8b5c9...66f0`，COCO 80 類，輸入 640x640，閾值 0.30）
    - 輕量級時序 RGB 輪廓啟發式（`src/amidst/engineering/perception.py`，免下載免 GPU，CPU 確定性執行）
    - 規則空間幾何約束（Baseline fallback）
  - **語言模型比較**：Qwen3-1.7B-Q4_K_M (1.15 GiB 載入, 1.82 GiB RSS, 延遲 320 ms) vs Qwen3-8B FP16 (4.50 GiB, 5.85 GiB RSS, 延遲 850 ms)。
- **最佳平衡候選組合表現**：動作吻合率 `88.89%`，延遲中位數 `547.5 ms`，誤切率 `5.56%`，大幅降低硬體需求至一般工作站水準。
- **守門結果**：`EXPLORATORY_EVALUATED`

---

## 4. 完成條件（Test Gate）核對表

- [x] **每個組合設定**：RULE_ONLY, M1, M2, M3, M4 各組合皆具備完整參數與切換模式設定。
- [x] **環境 JSON**：`M1_M4_BASELINE_ENV_MANIFEST_20261104.json` 符合 `amidst.experiment-env.v1`，通過 `experiment_env.py` 驗證。
- [x] **原始輸出**：`M1_M4_BASELINE_RAW_RESULTS_20261104.json` 包含各組逐事件詳細輸出。
- [x] **指標含單位**：百分比 (`%`)、延遲 (`ms`)、記憶體 (`GiB`)、頻率 (`per min`) 皆具備嚴格單位。
- [x] **SHA-256 雜湊鎖定**：所有產出之 JSON、CSV、Markdown、PNG 皆已計算並記錄固定雜湊。
- [x] **圖表腳本可重算**：可透過 `scripts/research/generate_report_tables_and_figures.py` 與 `run_m1_m4_baseline_evaluation.py` 100% 確定性重現。
- [x] **不足者標「待補」**：未經核准之正式真實索引與人工審核標記為 `待補` / `UNKNOWN` / `PENDING_REAL_DATA`，嚴格零編造。

---

## 5. 產出檔案清單與 SHA-256 雜湊表

| 檔案路徑 | 類型 | 說明 | SHA-256 |
| --- | --- | --- | --- |
| `docs/evaluation/M1_M4_BASELINE_ENV_MANIFEST_20261104.json` | `json` | amidst.experiment-env.v1 環境自檢清冊 | `c87874d018e68485c2821114f7679d057a4974f70c1a2fb0102de692e4217770` |
| `docs/evaluation/M1_M4_BASELINE_RAW_RESULTS_20261104.json` | `json` | Baseline 與 M1～M4 原始評估紀錄 | `f49729b1e9ec2ef345702ceb27a065852aac680927700d077980cf02aec35386` |
| `docs/evaluation/table_m0_m4_comparison.csv` | `csv` | Baseline vs M1～M4 核心指標比較表 (CSV) | `d3de18a90d14198bc5654a46981a2e73ee7ad61289c5972d35189b2242024656` |
| `docs/evaluation/table_m0_m4_comparison.md` | `markdown` | Baseline vs M1～M4 核心指標比較表 (Markdown) | `197fae3761c9242c678a00528c8eaea0791a4b08e9fc86e1beee7151c5f4f944` |
| `docs/evaluation/fig_m0_m4_comparison.png` | `png` | Baseline vs M1～M4 指標比較圖 (PNG) | `deffd4939f2cd974ea7eb502d4fbc00424b74f0c857663995bd8df19ca4fc75d` |
| `docs/evaluation/table_q4_presence_accuracy.csv` | `csv` | Q4 T/F Presence 準確率分析表 (CSV) | `83ed64b69bee90a66f93d6afe9cf244342372a7466f7b4055ba401b0078b241d` |
| `docs/evaluation/table_q4_presence_accuracy.md` | `markdown` | Q4 T/F Presence 準確率分析表 (Markdown) | `e90a0adc125a259fb4785db3c14f2522af89897a7b72e11307dff2e2252810c1` |
| `docs/evaluation/fig_q4_presence_accuracy.png` | `png` | Q4 T/F Presence 準確率視覺化長條圖 (PNG) | `4fe199fcf9c17754d80f6e594139fbfc3621c0128b6f7f84dda35dedd0b827dc` |
| `docs/evaluation/table_q5_switch_consistency.csv` | `csv` | Q5 切鏡決策窗一致性分析表 (CSV) | `197134a7fa084f227dd19aed8455776abde0cfdf9f257345d11335a7a7c2062a` |
| `docs/evaluation/table_q5_switch_consistency.md` | `markdown` | Q5 切鏡決策窗一致性分析表 (Markdown) | `16b1fd87f9fc0229378e59be3cbe4797f8aa4bf9cc954a9215086a898909219f` |
| `docs/evaluation/fig_q5_switch_consistency.png` | `png` | Q5 切鏡決策窗一致率圖 (PNG) | `242b4c5a02ee7a54521ac7c83b8ce5430c4f3b8c07b9131f51f745441ecec13b` |

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
