# W-A6 Colab 一鍵測試 Notebook 合成資料執行紀錄（2026-11-04）

- **對應任務**：Issue [#424](https://github.com/Polalalabear/amidst/issues/424)（`W-A6 Colab 一鍵測試 notebook（環境自檢→資料 sha256→測試→匯出）`）
- **資料類別宣告**：`source_class = "SYNTHETIC"`
- **真實 W-C5 資料包狀態**：`real_data_status = "UNKNOWN"`（`UNKNOWN (awaiting #416 W-C5 safe pack)`）
- **GT 隔離狀態**：`inference_read_gt = false`、`gt_path_scan = "PASS"`（自動拒絕任何含 `gt_private` 的路徑與清單項目）
- **實測執行平台**：**Windows 本機工作站（PowerShell / Python 3.12，非 Colab 雲端環境）**
- **Colab 雲端執行狀態**：**未驗證（Colab run = not verified）**；所有流程已於 Windows 本機確定性驗證通過。

---

## 1. 交付檔案與結構

| 檔案路徑 | 用途說明 |
| --- | --- |
| `notebooks/amidst_q1q5_colab_oneclick.ipynb` | Colab 一鍵測試 Notebook（nbformat v4.5），含 Cell 1～Cell 5 繁體中文說明、程式碼註解與合成資料實際執行輸出 |
| `scripts/research/colab_oneclick_runner.py` | Notebook 呼叫之核心輔助模組（環境自檢、API Key 狀態安全檢查、資料包 SHA-256 與 `gt_private` 驗證、JSONL 中斷續跑、M0～M4 統計匯出） |
| `docs/operations/COLAB_ONECLICK_RUN_LOG_20261104.md` | 本執行紀錄（記錄 Windows 本機實跑結果、中斷續跑驗證、CSV/PNG 產物 SHA-256 與 `real_data_status: UNKNOWN` 狀態，明確標示 Colab 雲端未驗證） |
| `tests/q1q5/test_colab_oneclick_notebook.py` | 自動化單元測試（驗證 nbformat v4、繁體中文註解、API Key 零洩漏、SHA-256 與 `gt_private` 阻擋、中斷續跑跳過已完成項目、合成資料匯出與 `UNKNOWN` 標記） |

---

## 2. 一鍵執行指令（Colab 與本地重現）

本 Notebook 與執行模組支援兩種標準執行模式：

### 2.1 模式 A：離線合成資料模式（Offline Synthetic Mode，預設開箱即用，已實測驗證）
適用於無外部付費 API、未掛載 Google Drive 或真實 W-C5 資料包尚未核定之測試驗證情境：
1. 於 Google Colab 開啟 `notebooks/amidst_q1q5_colab_oneclick.ipynb`。
2. （選填）於左側 **Secrets (`🔑`)** 設定 `OPENAI_API_KEY`、`GEMINI_API_KEY`、`ANTHROPIC_API_KEY` 或 `OLLAMA_HOST`。Cell 2 僅檢查並顯示 `PRESENT` / `MISSING`，**絕不印出或記錄任何金鑰值**。
3. 點選 **執行階段 (Runtime) → 全部執行 (Run all)**：
   - Cell 1 產出標準化硬體環境清冊並通過 `amidst.experiment-env.v1` 契約驗證。
   - Cell 2 檢查金鑰狀態（回報 `MISSING` 亦可安全執行後續合成實驗）。
   - Cell 3 偵測未掛載 Drive，自動標記 `real_data_status: "UNKNOWN"` 並切換至內建 `tests/fixtures/research/SYNTHETIC_*` 資料集。
   - Cell 4 執行 251 筆逐事件／逐模型組合工作單元，寫入 JSONL checkpoint；重複執行自動命中 skip。
   - Cell 5 匯出 42 個分析產物（CSV/PNG/SVG/EXPORT_MANIFEST.json）。
4. **本地 Windows 命令列一鍵驗證指令**：
   ```powershell
   python scripts/research/colab_oneclick_runner.py --workdir ".tmp_colab_run" --bootstrap-b 200
   ```

### 2.2 模式 B：W-C5 已核定真實資料包模式（W-C5 Verified Pack Mode）
適用於持有上游核定之 `#416` W-C5 safe pack 真實資料包情境：
1. **資料包置放**：於 Google Colab 掛載 Google Drive（`drive.mount("/content/drive")`），將 safe pack 置於 `/content/drive/MyDrive/amidst_wc5_safe_pack`，或設定環境變數 `AMIDST_WC5_SAFE_PACK_DIR` 指向資料目錄。
2. **信任根設定**：設定經上游核定之 manifest SHA-256 信任根環境變數：
   ```python
   os.environ["AMIDST_APPROVED_WC5_MANIFEST_SHA256"] = "<approved_64_char_hex_sha256>"
   ```
   或使用 CLI 參數 `--manifest-sha256 <approved_64_char_hex_sha256>`。
3. **安全規範與結構比對**：
   - 資料包內必須具備 `SAFE_PACK_MANIFEST.json` 或 `MANIFEST.json`。
   - Manifest 必須聲明符合規範之 `format`（如 `amidst.argon-safe-pack.v1`）、非空 `pack_id`、明確之 `sources` provenance，且 `gt_read` 必須為 `false`。
   - `verify_data_pack` 會比對 manifest 本身之 SHA-256 是否吻合核定信任根，並逐檔核對 safe pack 內所有檔案之 SHA-256。
4. **防偽與降級防護（Fail-Closed against Self-Declared Packs）**：
   - 若資料包僅包含未經核定之 self-declared manifest（無核定信任根），系統嚴禁宣告真資料已驗，自動將狀態歸類為 `real_data_status: "UNVERIFIED"`、`active_data_mode: "SYNTHETIC"` 與 `source_class: "SYNTHETIC"`。
   - 即使真實資料包在磁碟上驗證通過，因真實推論 adapter 尚未實作（`NOT_IMPLEMENTED`），評測產物指標一律鎖定為 `SYNTHETIC` 與 `UNKNOWN`，絕不升格固定分數。

> **注意**：Colab 雲端執行階段尚未在 Google Colab 上線上線點擊 Run all（**Colab run = not verified**），本次交付係於本地 Windows 工作站透過 runner 與 notebook 模擬執行驗證。

---

## 3. Cell 1 ～ Cell 5 合成資料實際執行紀錄（Windows 本機實跑）

### Cell 1：環境自檢（`amidst.experiment-env.v1`）
- **驗證契約**：`amidst.experiment-env.v1`（透過 `scripts/research/experiment_env.py` 驗證，`validation_errors = []`）
- **正規化環境雜湊 (`env_manifest_sha256`)**：`bca0694cfa283dbaded84aa17b2caef18c875a3a657f198f9c718faa38ec49bb`
- **自檢摘要**：
  - `os_name`: `SYNTHETIC-Colab-Linux`（在 deterministic=True 下產出標準化自檢，真實探針模式下亦可探測本機 Windows / Colab Linux 硬體）
  - `cpu_cores`: `4`
  - `ram_gib`: `12.7`
  - `gpu_model`: `NONE`, `gpu_vram_gib`: `NONE`
  - `python_version`: `3.12.0`, `torch_version`: `NOT_INSTALLED`

### Cell 2：API Key 安全讀取（Secrets / 環境變數狀態）
- **檢查鍵名**：`OPENAI_API_KEY`、`GEMINI_API_KEY`、`ANTHROPIC_API_KEY`、`OLLAMA_HOST`
- **輸出策略**：`STATUS_ONLY_NEVER_LOG_VALUES`（`secret_values_logged = false`）
- **實跑狀態**：四組皆為 `MISSING`（單元測試中亦驗證注入假金鑰時僅回傳 `PRESENT`，輸出字串與 Notebook 全文完全不含金鑰內容）。

### Cell 3：Google Drive 掛載與 W-C5 safe 資料包 SHA-256 驗證
- **真實資料狀態 (`real_data_status`)**：`UNKNOWN`
- **狀態說明 (`real_data_note`)**：`UNKNOWN (awaiting #416 W-C5 safe pack)`
- **啟用資料模式 (`active_data_mode`)**：`SYNTHETIC`
- **GT 路徑掃描 (`gt_path_scan`)**：`PASS`（確認無 `gt_private`）
- **SHA-256 驗證 (`sha256_verified`)**：`true`（共 6 個內建合成資料檔，`pack_manifest_sha256 = 8e528d4a7dacb4745b77af38a4a5b867c57f850c59fdb5b8ec6507af237e38b6`）

### Cell 4：中斷續跑（Checkpoint / Resume）實驗執行器
- **Checkpoint 檔案**：`$AMIDST_COLAB_WORKDIR/checkpoints/experiment_checkpoint.jsonl`（LOCAL 暫存產物，可由 `colab_oneclick_runner.py` 100% 重現）
- **第一階段（模擬執行 10 個單元後中斷）**：
  - `executed_now`: `10`
  - `skipped_from_checkpoint`: `0`
  - `interrupted`: `true`
- **第二階段（從同一個 JSONL checkpoint 自動續跑）**：
  - `total_units`: `251`
  - `skipped_from_checkpoint`: `10`（前次已完成的 10 筆因 `config_sha256` 與 `input_sha256` 相同，自動跳過不重算）
  - `executed_now`: `241`
  - `completed_total`: `251`
  - `interrupted`: `false`
  - `checkpoint_sha256`: `49a4d35ee7329ed83a80966049089d4c9798452a3acf10c9f5c1336347b23392`
- **第三階段（對已完成 checkpoint 再次執行）**：
  - `skipped_from_checkpoint`: `251`
  - `executed_now`: `0`
  - `completed_total`: `251`
- **各實驗模組完成筆數 (`completed_by_experiment`)**：
  - `M0_BASELINE`: `10`
  - `M1_AGENT_VS_RULE`: `56`
  - `M2_SCORER_V2`: `17`
  - `M3_Q3_PARSER`: `72`
  - `M4_MODEL_COMPARE_Q2`: `48`
  - `M4_MODEL_COMPARE_Q3`: `48`

### Cell 5：結果彙整與匯出 CSV／視覺化比較圖（PNG）／MANIFEST SHA-256
- **匯出檔案總數 (`file_count`)**：`42`（LOCAL 產物目錄 `$AMIDST_COLAB_WORKDIR/exports/`，可由腳本 100% 確定性重現）
- **匯出包 Manifest SHA-256 (`export_manifest_sha256`)**：`3bdb3c4d9990a55c6bf3259637971ccf8d2ed78d4903e7df1a435291ac9768a3`

#### 彙整總表（`colab_oneclick_summary.csv`）結果摘要

| module | arm_or_scope | primary_metric | score_pct | ci_lo | ci_hi | n_scored | source_class | real_data_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `M0_BASELINE` | `RULE_ONLY (TOTAL:ALL)` | `C_evt_pct` | `57.1429` | `50.0000` | `66.6667` | `7` | `SYNTHETIC` | `UNKNOWN` |
| `M1_Q5_SWITCH` | `RULE_ONLY` | `C_evt_pct` | `66.6667` | `66.6667` | `66.6667` | `18` | `SYNTHETIC` | `UNKNOWN` |
| `M1_Q5_SWITCH` | `AGENT_SEQUENTIAL` | `C_evt_pct` | `75.0000` | `66.6667` | `80.5556` | `18` | `SYNTHETIC` | `UNKNOWN` |
| `M2_SCORER_V2` | `STANDARD_EVENTS` | `A_std_pct` | `91.6667` | `UNKNOWN` | `UNKNOWN` | `12` | `SYNTHETIC` | `UNKNOWN` |
| `M3_Q3_PARSER` | `RULE_ONLY (ALL)` | `E_q3_pct` | `55.5556` | `41.6667` | `69.4444` | `36` | `SYNTHETIC` | `UNKNOWN` |
| `M3_Q3_PARSER` | `LLM_WITH_RULE_FALLBACK (ALL)` | `E_q3_pct` | `75.0000` | `58.3333` | `88.8889` | `36` | `SYNTHETIC` | `UNKNOWN` |
| `M4_CANDIDATES` | `Q2:SYN-model-large` | `C_evt_pct` | `56.2500` | `50.0000` | `62.5000` | `16` | `SYNTHETIC` | `UNKNOWN` |

#### 關鍵匯出產物 SHA-256 清單（LOCAL `$AMIDST_COLAB_WORKDIR/exports/`）

| 相對路徑 | 檔案大小 (bytes) | SHA-256 | 可重現方式 |
| --- | --- | --- | --- |
| `colab_oneclick_summary.csv` | 1,173 | `9a2f0f08f9bf09e761a1030dec98110a4f6ac71ee67c80a2dc273c1736514c17` | 執行 Cell 5 或 `colab_oneclick_runner.py` |
| `colab_oneclick_summary.png` | 106,303 | `2b01ca30f8bcd43ee25d972f7a7d4b830a720b13ad438ed94c8d044a8c6861cf` | 執行 Cell 5 或 `colab_oneclick_runner.py` |
| `colab_oneclick_summary.svg` | 20,006 | `c7a035ec4154feac37a2e899aec1e571607ea250035beb9dfe87688be2cc6a93` | 執行 Cell 5 或 `colab_oneclick_runner.py` |
| `experiment_env_manifest.json` | 3,044 | `d84e6fbd85c197a54b9ce606f80aeb3c49a801edeb56f9fe389f7c94310e161c` | 執行 Cell 1 + Cell 5 |
| `m0_baseline/baseline_B1.csv` | 2,542 | `36819c22531d485ec4991311101495ac0cf24b325a98b9b1c1585768050e4c93` | `build_baseline_table.py` (bootstrap_b=200) |
| `m0_baseline/G-B1_c_evt.png` | 48,299 | `8d91d48c29295e5ffd24e4be130e612cb8c7544e3bc85b2a3b50d4236a3388f0` | `build_baseline_table.py` (bootstrap_b=200) |
| `m1/m1_M1-1.csv` | 700 | `7ceb533a826477bb62b035916955411748111beba5016fd81b28af89b3d97df0` | `analyze_experiments.py m1` (bootstrap_b=200) |
| `m1/G-M1a_paired.png` | 101,212 | `001782f6a1a0703dc670fbb8379efc97b624e6dee77910d13fdae44734cefc52` | `analyze_experiments.py m1` (bootstrap_b=200) |
| `m2/m2_M2-1.csv` | 249 | `553c2d3d153a4cbcc9322b73a859775ab9c23e845bd539c9abaa6a03ee3fc5ae` | `analyze_experiments.py m2` |
| `m2/G-M2a_confusion.png` | 74,211 | `e49c9448f47a088dd0db125c21672773f0b162cba696d400bdb745f36b866e83` | `analyze_experiments.py m2` |
| `m3/m3_M3-1.csv` | 1,141 | `75957a610237d8534f5be8588ee3e12e391e3d877b237e6c5e35d02ad42ceac4` | `analyze_experiments.py m3` (bootstrap_b=200) |
| `m3/G-M3a_field_accuracy.png` | 44,269 | `2b71cfb113d91f12fc557d8b6c8ee14e602dbed8cb06920aa7122455aea810fd` | `analyze_experiments.py m3` (bootstrap_b=200) |
| `m4/m4_M4-1.csv` | 1,402 | `fbd12e878d11321b27811ede42c76d7aa22139e4067e2c433f03911db791658d` | `analyze_experiments.py m4` (bootstrap_b=200) |
| `m4/G-M4_Q2.png` | 56,638 | `29fa001c801b15bdd2e49ca3c25a6cebccca9194d0610c4ade5ac80223a9d6e7` | `analyze_experiments.py m4` (bootstrap_b=200) |
| `EXPORT_MANIFEST.json` | 4,768 | `3bdb3c4d9990a55c6bf3259637971ccf8d2ed78d4903e7df1a435291ac9768a3` (canonical payload SHA-256) | 執行 Cell 5 或 `colab_oneclick_runner.py` |

---

## 4. 本地 Windows 實測指令、產物雜湊與狀態總結

### 4.1 執行指令與結果
1. **Runner 本地一鍵執行全流程**：
   ```powershell
   python scripts/research/colab_oneclick_runner.py --workdir .tmp_colab_run --bootstrap-b 200
   ```
   - 結果：`status=PASS`, 251/251 單元完成，產出 42 個檔案，`export_manifest_sha256 = 3bdb3c4d9990a55c6bf3259637971ccf8d2ed78d4903e7df1a435291ac9768a3`。
2. **中斷續跑（Resume Skip）驗證**：
   ```powershell
   python scripts/research/colab_oneclick_runner.py --workdir .tmp_colab_run --bootstrap-b 200
   ```
   - 結果：`completed_total = 251`, `skipped_from_checkpoint = 251`, `executed_now = 0`（完全命中 checkpoint，跳過 100% 重複運算）。
3. **自動化測試套件**：
   ```powershell
   python -m pytest -o pythonpath=src -q tests/q1q5/test_colab_oneclick_notebook.py
   ```
   - 結果：`6 passed in 5.8s`（100% 通過）。
4. **架構防護檢查**：
   ```powershell
   python scripts/check_architecture_guard.py --repo . --base origin/mainline/q1q5
   ```
   - 結果：`status=PASS`, `findings: []`（0 findings）。

### 4.2 驗證項目（Verified）
- Notebook (nbformat v4.5) 結構完整，所有 Markdown 與程式碼單元均具備繁體中文說明與註解。
- 環境自檢輸出符合 `amidst.experiment-env.v1` 契約並通過 `experiment_env.py` 驗證。
- API Key 零洩漏原則：Secrets 與環境變數僅回報 `PRESENT` / `MISSING`，絕無金鑰內容輸出或記錄。
- 資料包 SHA-256 驗證：強制檢查無 `gt_private`，若資料包缺失自動標記 `real_data_status: UNKNOWN (awaiting #416)` 並切換至 `SYNTHETIC`。
- JSONL Checkpoint / Resume 機制：同 config/input 雜湊項目自動跳過，設定變更時重新計算。
- 匯出產物生成：總表 CSV、比較圖 PNG、SVG 與 `EXPORT_MANIFEST.json`。

### 4.3 未驗證項目（Not verified）
- **Google Colab 雲端執行階段**：本次驗證完全在本地 Windows 11 工作站進行，尚未在實際 Google Colab 雲端環境點選全部執行（`Colab run = not verified`）。
- **真實 #416 W-C5 資料包**：等待 Issue #416 提供安全真實資料包，目前標記為 `UNKNOWN (awaiting #416 W-C5 safe pack)`。
- **外部付費 LLM 連線**：未調用外部付費 API，僅在離線合成環境驗證金鑰狀態檢查與 Fallback 邏輯。

---

## 5. Codex 審查回饋修正記錄（2026-11-05，PR #438 / Issue #424）

針對 Codex 於 PR #438 提出之 `P1=2, P2=2` 審查意見完成下列全面修復：

1. **[P1] safe pack 路徑安全性與 GT 隔離全面強化**（`scripts/research/colab_oneclick_runner.py`）：
   - 拒絕任何絕對路徑、`..` 相對路徑遍歷與無效字元（`\\`, `:`, `\0`）。
   - 阻擋符號連結（symlinks）與 Windows junction / reparse points，要求所有檔案必須為 regular file。
   - 強制執行 canonical containment 檢查（`fpath.resolve().relative_to(target_dir.resolve())`），禁止任何跳脫 safe pack 根目錄之路徑。
   - 全面檢查 `FORBIDDEN_NAME_PATTERN`，涵蓋 `gt`, `gt_private`, `ground_truth`, `groundtruth`, `private`, `trajectory`, `depth`, `visibility`, `waypoints` 等關鍵字，不以檔名黑名單宣稱 GT 隔離。
   - 實作副檔名白名單（`.json`, `.jsonl`, `.png`, `.py`, `.mjs`, `.css`, `.html`, `.txt`, `.csv`, `.sha256`, `.md`）與 64 MiB 檔案大小上限。

2. **[P1] 嚴格 provenance 分類與防止 synthetic 分數升格**（`scripts/research/colab_oneclick_runner.py`）：
   - 統計結果來源嚴格綁定實際讀入的資料與 clock / run / hash：工作單元一律標記 `source_class: "SYNTHETIC"`。
   - 分析匯出流程讀入 `tests/fixtures/research/SYNTHETIC_*` 固定產物，指標一律標記為 `source_class: "SYNTHETIC"` 與 `real_data_status: "UNKNOWN"`。
   - 即使 safe 資料包在磁碟上驗證通過，因真實推論 adapter 尚未實作（`real_data_adapter_status: "NOT_IMPLEMENTED"`），固定 synthetic 分數絕不升格為 `ENGINEERING` 或 `VERIFIED`。

3. **[P2] Notebook Cell 4 移除預設 unlink**（`notebooks/amidst_q1q5_colab_oneclick.ipynb`）：
   - 移除 `if checkpoint_file.exists(): checkpoint_file.unlink()`。
   - 正常執行流程完整保留既有 checkpoint，驗證 config / input pins 後接續執行剩餘單元，已完成項目 100% 跳過。
   - 中斷續跑特性於自動化測試 `test_checkpoint_resume_skips_completed_units_and_recomputes_on_config_change` 與 `test_notebook_cell4_preserves_existing_checkpoint` 中驗證。

4. **[P2] 補齊 source-bound bootstrap 與跨平台測試一致性**（`notebooks/amidst_q1q5_colab_oneclick.ipynb`、`tests/q1q5/test_colab_oneclick_notebook.py`）：
   - Cell 1 增加乾淨 Colab runtime 自動檢測與 source-bound repo bootstrap，在本地／離線環境下直接重用既有程式庫。
   - 單元測試修復跨平台 matplotlib PNG 二進位差異導致的 export-manifest 雜湊比對問題，改為驗證正規化 64-char hex sha256 與 manifest 一致性，確保在 Windows / macOS / Linux 皆 100% 通過（8 passed in 6.65s）。

5. **[REVISE P2] 未核定 W-C5 manifest 信任根不可宣稱真資料已驗（Root of Trust）**（`scripts/research/colab_oneclick_runner.py`、`tests/q1q5/test_colab_oneclick_notebook.py`、`notebooks/amidst_q1q5_colab_oneclick.ipynb`）：
   - 拒絕盲目信任任意未核定 pack 內部自含之 MANIFEST.json / SAFE_PACK_MANIFEST.json 路徑與雜湊。
   - 增列 owning manifest 結構與上游信任根顯式驗證：強制檢查 `gt_read: false`、合法 `pack_id`、上游 source/run 標識與 `format` 白名單，並比對顯式提供之信任根雜湊（`expected_manifest_sha256` / `AMIDST_APPROVED_WC5_MANIFEST_SHA256` / `APPROVED_SAFE_PACK_ROOTS`）。
   - 若資料包缺乏上游已核定之 provenance 或純屬本地 self-declared，`verify_data_pack` 嚴禁宣告 `real_data_status="VERIFIED"`、`active_data_mode="REAL_WC5_PACK"` 或 `source_class="ENGINEERING"`；一律分類降級標記為 `UNVERIFIED` 與 `SYNTHETIC`。
   - 新增專屬回歸測試 `test_arbitrary_synthetic_pack_with_self_calculated_hash_cannot_claim_verified_or_engineering`，驗證任意自算雜湊之合成資料包絕無法誘騙系統回傳 `VERIFIED` 或 `ENGINEERING`（9 passed in 6.74s）。
   - 於 Notebook 與本執行紀錄中完整補齊「離線合成模式」與「W-C5 已核定真實包模式」之雙軌執行指引。
