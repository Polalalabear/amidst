# 研究實驗包（Claude 負責的部分）

依據：研究企劃 #397（`docs/research/MODEL_EXPERIMENT_PLAN_20261102.md`，在 `claude/model-experiment-plan`）、#93 的 D121～D123。
這個目錄只有**讀結果檔、產表與圖**的工具；沒有任何實驗被執行，所有範例輸入都是 SYNTHETIC，不是證據。

指令一律用專案 venv 的 Python；腳本只讀自己的輸入檔，不讀 GT、錄製或影像。

```bash
PY=/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/.venv/bin/python
```

## 腳本

| 腳本 | 做什麼 | 要等 Codex 的真實 run 嗎 |
| --- | --- | --- |
| `experiment_env.py` | 驗證 `amidst.experiment-env.v1` 並印出 `env_manifest_sha256`（正規化 JSON 的 SHA-256） | 不用；schema 與驗證現在就能用。**Codex 的 runner 要產出 manifest** |
| `build_baseline_table.py` | CX-8 RULE_ONLY 結果 → 表 B-1（CSV＋Markdown）、圖 G-B1／G-B2／G-B3 | 要。真實輸入要等 CX-8；腳本已用合成 fixture 測過 |
| `analyze_experiments.py m1` | 表 M1-1、M1-2；圖 G-M1a／b／d／e | 要（Agent 錄製、K＝5） |
| `analyze_experiments.py m2` | 表 M2-1；圖 G-M2a | 要（v2 評分器 FEAT-4 #396 與 Baseline 錄製） |
| `analyze_experiments.py m3` | 表 M3-1、M3-2；圖 G-M3a、G-M3e。**只讀 `evaluation_eligible=true` 的題** | 要（LLM 組 Q3 錄製；題集要先核定） |
| `analyze_experiments.py m4` | 表 M4-1；圖 G-M4（Q2、Q3 各一張） | 要（六個候選模型的錄製） |

```bash
# 環境 manifest
$PY scripts/research/experiment_env.py docs/contracts/examples/amidst.experiment-env.v1.example.json

# Baseline 表（SYNTHETIC 範例）
$PY scripts/research/build_baseline_table.py tests/fixtures/research/SYNTHETIC_baseline_results.json --out /tmp/out_b

# M1～M4（SYNTHETIC 範例；--bootstrap-b 可調小加速，正式分析用預設 10000）
$PY scripts/research/analyze_experiments.py m1 tests/fixtures/research/SYNTHETIC_m1_results.json --out /tmp/out_m1
$PY scripts/research/analyze_experiments.py m2 tests/fixtures/research/SYNTHETIC_m2_results.json --out /tmp/out_m2
$PY scripts/research/analyze_experiments.py m3 tests/fixtures/research/SYNTHETIC_m3_results.json \
    --queries tests/fixtures/research/SYNTHETIC_m3_queries_eligible.csv --out /tmp/out_m3
$PY scripts/research/analyze_experiments.py m4 tests/fixtures/research/SYNTHETIC_m4_results.json --out /tmp/out_m4
```

圖有 `--theme light|dark`；每張圖輸出 PNG 與 SVG，圖尾標來源類別和 `env_manifest_sha256` 前 8 碼。
同一輸入重跑，CSV／Markdown／SVG 逐位元組相同（種子 `20261102`）。

## 共用規則（腳本怎麼處理缺值）

- `UNKNOWN`、`MISSING`、`NOT_RUN`、空值、`null`：表裡寫 `UNKNOWN`，**不補值**，同時從分子和分母拿掉並另外計數（企劃 §1.4 第 8 項）。分母為 0 的指標整格 `UNKNOWN`。
- 95% CI：單一 run 用 Wilson；≥2 個 run 用依 run 分群的百分位 bootstrap（10,000 次，種子 `20261102`）。中位數只有一個 run 時 CI 是 `UNKNOWN`。企劃沒有指定 bootstrap 區間種類，這裡用百分位法，是實作選擇，不是企劃條文。P90 用 nearest-rank。
- 假設檢定：腳本只輸出配對計數與單尾精確符號檢定的原始 p。**`p_holm`、`verdict` 一律寫 `UNKNOWN`**：Holm 要跨整個 H1 家族，判定標籤（§1.6）還要別的模組的閘門與資料來源，不在單一腳本內決定。M1 的 FB 閘門（>20%）與 M3 的 `LLM_share` 閘門（<50%）會輸出 PASS／FAIL。
- M1 公平性（§3.2）：同一個 `run_id`＋`request_sha256`，兩組的 `parameter_set_sha256`、`candidate_snapshot_sha256`、`env_manifest_sha256` 必須相同且已知，否則整個配對標 `INVALID_COMPARISON` 並排除（會在表尾列名）。
- `AGENT_SEQUENTIAL_RELAXED`（放寬逾時組）用 `--agent-arm AGENT_SEQUENTIAL_RELAXED` 另跑；輸出檔名加 `_relaxed`，verdict 固定為 `EXPLORATORY_NOT_IN_H1`。
- M3：題集 CSV 沒有 `evaluation_eligible` 欄、或沒有任何一列是 `true`，輸出就是空表加「評測集未核定」提示（沒有圖、不讀結果）。**#397 的 `m3_queries_v1_draft.csv` 目前沒有 `evaluation_eligible` 欄**（標記只寫在 `.md`），照上述規則一律視為未核定。使用者核准後由 Claude 產生的 `m3_queries_v1.csv` 要有這一欄。
- 沒做的圖：G-M1c 森林圖與 G-M3c／G-M3d。原因：Agent 子集的配對方式、v2 穩健性列的輸入、Q1 的 ITT／子集配對在企劃裡沒有精確定義，標 `UNKNOWN`，等企劃補齊再加。G-B4（Q3 Baseline 欄位）與 G-B5（team-eval 重現）也未做，等表 B-2／B-3 的輸入格式定案。

## 輸入契約（草案 `amidst.research-results.v0-draft`）

格式還沒和 Codex 定案，**這是 Claude 提的草案**；Codex 的 runner 與評分器輸出若不同，改輸入端的轉換，或改這份契約（要 Codex 確認）。每個結果檔是一個 JSON 物件：

通用欄位：`contract`（固定 `amidst.research-results.v0-draft`）、`experiment`（`BASELINE`／`M1`／`M2`／`M3`／`M4`）、`source_class`（`FORMAL`／`ENGINEERING`／`SYNTHETIC`／`PILOT`）、`env_manifest_sha256`（64 位十六進位或 `UNKNOWN`）、選填 `scorer: {name, version, output_sha256}`。

**BASELINE／M1**（列都有 `run_id`、`request_sha256`、`arm`、`repeat`；`arm`＝`RULE_ONLY`／`AGENT_SEQUENTIAL`／`AGENT_SEQUENTIAL_RELAXED`）

| 陣列 | 欄位 |
| --- | --- |
| `runs`（每個 run×request×arm 一列） | `scene`、`fps`、`scoped_minutes`、`false_switch_count`、`replay_n`、`replay_hash_same_n`、`recording_sha256`、`parameter_set_sha256`、`candidate_snapshot_sha256`、`env_manifest_sha256` |
| `events` | `event_id`、`scored`（bool）、`not_scored_label`、`match`（true／false／`UNKNOWN`）、`decision_source`（`RULE_ONLY`／`AGENT`／`RULE_FALLBACK`）、`latency_ms` |
| `steps` | `step_id`、`decision_source`、`step_ms` |
| `calls`（Agent） | `step_id`、`error_code`（`PROVIDER_TIMEOUT`／`SCHEMA_INVALID`／null）、`duration_ms`、`prompt_tokens`、`completion_tokens`（沒記就 `UNKNOWN`） |
| `honesty_steps`（BASELINE） | `step_id`、`expected_missing`、`output_missing_marker` |

**M2**：`events[]`：`event_id`、`scenario_class`、`category`（`STANDARD` 或不計分類別）、`v1_label`、`v2_label`（`MATCH`／`MISMATCH`／`NOT_SCORED_*`／`UNKNOWN`）、選填 `v2_expected_label`、`rule_ref`；`recompute: {n, same_n}`。

**M3**：`questions[]`：`query_id`、`arm`（`RULE_ONLY`／`LLM_WITH_RULE_FALLBACK`）、`parsed_by`、`correct`（E_q3）、`field_correct`（intent、class、color、time_us、camera、region 各 bool）、`camera_tp`／`camera_fp`／`camera_fn`。另用 `--queries` 指定題集 CSV（欄位同 #397 草稿：`query_id`、`family_id`、`event_class`、`wording_type` 等，加 `evaluation_eligible`）。

**M4**：`models[]`（`model`、`llm_digest`、`quant`、`llm_loaded_size_gib`、`peak_rss_gib`、`llm_processor`）、`events[]`（`model`、`run_id`、`event_id`、`match`）、`questions[]`（`model`、`run_id`、`query_id`、`correct`）、`calls[]`（`model`、`run_id`、`error_code`、`duration_ms`）、`baseline: {Q2, Q3}`（百分比或 `UNKNOWN`）。

## 解讀上的 UNKNOWN（企劃沒定義，腳本沒有自己發明）

- 表 B-1「最後兩列依 run 分群的合計」指哪兩列：本實作輸出每個場景一列 `TOTAL:<scene>` 與全部一列 `TOTAL:ALL`。
- 「三種事件」（E1／E2／E3）的讀法未經使用者確認；M3 不依 `event_class` 拆開報告。
- M1 的 `C_evt` 對 Agent 組是 K 次重複的單位平均；單一 run 的 Wilson CI 把平均當計數，只是近似。
- token 數、`T_step`、`R_hash` 的實際來源欄位名稱以 Codex 的 runner 為準：UNKNOWN。

## 測試

```bash
$PY -m pytest tests/unit/research -q
```

fixture 在 `tests/fixtures/research/`，檔名都以 `SYNTHETIC_` 開頭，內容的 `source_class` 都是 `SYNTHETIC`，全部合計約 120 KB。

## 實驗環境 manifest schema

`docs/contracts/schemas/amidst.experiment-env.v1.schema.json`（PROPOSED；範例在 `docs/contracts/examples/`）。
已登錄於 `configs/architecture/schema_registry_v1.json`（登錄不等於核准）。必填：git SHA、run id、參數集 id／狀態（`PROPOSED`／`APPROVED`）／SHA-256、`source_class`、資料來源與 hash、模型與版本、硬體、OS、Python／node 版本、隨機種子、起訖時間、GT 隔離宣告（`inference_read_gt` 只能是 `false`）。
取不到的值寫 `UNKNOWN`；資料來源 locator 不可是絕對路徑、`..` 或含 `gt_private`。額外規則：`APPROVED` 要有 `approval_ref` 與已知 hash；`FORMAL` 要有已知 commit 與參數集 hash，且 `gt_path_scan=PASS`；`gt_path_scan=FAIL` 一律不合格。
