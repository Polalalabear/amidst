# WP5 延遲組：Colab L4 本機模型操作說明

- 對應決定：D175（本機模型在 Colab Pro 的 NVIDIA L4 24GB 上跑，Ollama 版本與模型 digest 固定，q4_K_M；延遲一次只跑一個模型；評分和 GT 只在 Mac）、D218（主要結果是延遲和費用）。
- 筆記本：[`notebooks/agent_decision/wp5_colab_l4.ipynb`](../../notebooks/agent_decision/wp5_colab_l4.ipynb)。題組設定：[`configs/agent_eval/wp5_v1.json`](../../configs/agent_eval/wp5_v1.json)。runner：`python -m amidst.agent_eval.wp5_runner`。
- 這個流程**不需要任何 API key，不呼叫 OpenAI，不花錢**。OpenAI 與 Rule 的部分從 Mac 跑（`--arm mac`），不在 Colab。

## 工作內容

1. 在 Mac 用 `python scripts/agent_decision/build_wp5_packs.py --out local/data/wp5-packs-<日期>` 打包（Colab L4 包與 Windows 包；只含程式、設定、合成題；沒有 GT、影像、key）。交付說明與 SHA-256 見 [`WP5_PACKS_20261115.md`](WP5_PACKS_20261115.md)。題目檔 `data/wp5_questions.jsonl` 目前是合成題（真題庫 UNKNOWN）；真題的每列是 DP1／DP3 請求、DP4 請求或 NL `{text, vocab}`，檔案本身不得含 `gt_`、`truth*`、`trajectory` 等鍵（runner 在呼叫前就會整批拒絕）。
2. 在 Colab 選 **L4** 執行環境，上傳 `wp5-pack_colab_l4_<日期>.zip`，解開後在包根目錄開 `notebooks/agent_decision/wp5_colab_l4.ipynb`。
3. 依序執行各步驟：確認 L4（不是 L4 就停）→ 設定 `SET`、**釘死 `OLLAMA_VERSION`** → 安裝並讓 Ollama 一次只載入一個模型 → 拉模型、寫 `models.txt`（`名稱@digest`）並驗證 q4_K_M 與 digest → dry-run（0 次呼叫）→ 逐一模型（暖機一次、跑題組、卸載）→ 打包。
4. 下載 `RETURN/wp5_<set>_colab_l4.zip`，放進 Mac 的 `local/evidence/wp5/<set>/`，記下 SHA-256。

## 要帶回來的東西

| 檔案 | 內容 |
| --- | --- |
| `<模型>/calls.jsonl` | 每次呼叫一列：`latency_ms`、token、`cost_usd`（本機一律 0.0）、`timed_out_fallback`、`fallback_reason`、答案；`accuracy_correct` 為 null |
| `<模型>/summary.json`、`summary.md` | 每個模型、每種題型的延遲中位數／p95、費用、逾時率；準確度欄位排最後，只記錄 |
| `<模型>/MANIFEST.json` | 模式、組別、模型、設定檔 SHA-256、`calls.jsonl` SHA-256 |
| `ENV.json` | GPU 名稱、Ollama 版本、`models.txt`、digest |

## 規則

- 非 L4 的 GPU：不報延遲（`detect_colab_gpu` 判斷）。
- 延遲一次只跑一個模型（`OLLAMA_MAX_LOADED_MODELS=1`、`OLLAMA_NUM_PARALLEL=1`、模型之間 `ollama stop`）；準確度可以另外並行，但不混進延遲結果。
- 逾時：formal 組 2000 ms／5000 ms／3 輪；放寬組（`relaxed_exploration`，10000／30000／3）另外報告，不與 formal 混合。
- DP4：即時呼叫要等 #532（`ApiRanker`）接上，暫時用 `--skip-types DP4`（筆記本預設）；Rule 的 DP4 不受影響。
- 評分不在這裡：GT 只在 Mac，由 `amidst.agent_eval_scoring` 之後的任務併入。
- 回傳的原始檔留在本機（LOCAL，不進 git）；要進 PR 的只有彙總數字，並附 SHA-256 和路徑（相對 `$AMIDST_ARTIFACTS`）。
