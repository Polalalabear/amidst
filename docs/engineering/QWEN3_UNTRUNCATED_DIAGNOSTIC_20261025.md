# CX-6：Qwen3 不截斷診斷量測

工作依據：[#93 D76](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6396442549)。認領時間 2026-10-25；量測日期 2026-10-26（Asia/Taipei）。本文件及機器收據在同一 PR；完整 prompt、模型原始回應及既有錄製維持 LOCAL。

## 範圍與輸入

沿用 8 秒工程 baseline 已錄製的 18 次 provider 呼叫：12 次 Q3（2 題各 6 次）、6 次 Q5（同一個候選搜尋輸入）。原題組包含 3 種相異 wire request。每個來源檔先核對 bytes SHA-256，按原始呼叫編號重跑，同 messages、同 schema、同模型 digest、同 sampling。

正式人工八題仍由組員自行提供。本輪沒有讀人工答案、GT、RGB、劇本或 renderer 資料；只重送先前合法 runtime 的文字／結構輸入。Q5 工具或決策輸出只做離線合法性檢查，沒有呼叫 controller、執行工具或切鏡。

原生產輪的 18 次呼叫皆在 2000 ms deadline 逾時，沒有完整輸出或 token 數。這不能證明它們用完 256 token。診斷僅把 HTTP generation timeout 設成 None，並將原 options.num_predict=256 改成 -1；其餘 wire payload 不變。D65 生產預算及產品 provider 不變，formal denominator eligibility=false。

Ollama 的 num_predict=-1 表示不設生成 token 上限；完成與否仍檢查 done/done_reason，不把 length 視為完整成功。[官方參數說明](https://docs.ollama.com/modelfile)。prompt_eval_count、eval_count 及 server duration 依 [Ollama API 定義](https://docs.ollama.com/api/usage) 記錄；server duration 單位原為 ns，另換算 ms。客戶端 wall latency 與 server total_duration 分開保存，未把差值稱為實測 queue time。

## 實測結果

| 階段 | 呼叫數 | 延遲 min／median／p95／max（秒） | 輸入 tokens | 輸出 tokens | schema／字面來源 |
| --- | ---: | --- | --- | --- | --- |
| Q3 | 12 | 5.366／5.777／10.427／10.427 | 660 或 665 | 117 或 133 | schema 12/12；字面 12/12 |
| Q5 | 6 | 7.804／7.992／10.430／10.430 | 1269 | 166 | schema 6/6；Controller acceptance UNKNOWN |

18/18 完整生成，done_reason 全為 stop；逐次完整延遲與 token 數見[機器收據](../history/QWEN3_UNTRUNCATED_DIAGNOSTIC_20261025.json)。p95 使用 nearest-rank：Q3 n=12 時 ceil(0.95×12)=12，Q5 n=6 時 ceil(0.95×6)=6，所以本輪兩組 p95 都等於 max，資訊與最大值重複，不能據此推論穩定的母體尾端延遲。

載入與離群值分開看：呼叫1（首次 Q3）牆鐘10.427秒，server load_duration 約3.103秒；呼叫4（首次 Q5）牆鐘10.430秒，load_duration 僅1.757毫秒，**Q5 這個10.4秒離群值不能歸因於模型載入**。該次 prompt_eval_duration 約2.716秒、eval_duration 約7.667秒，是已記錄的分段時間；同組其餘5次 Q5 的 prompt_eval_duration 為0.022–0.029秒，這只是本輪時間觀察，不作因果判定。首次該 prompt 的額外成本根因未驗，不自行判成快取、排隊或冷啟動。每筆 server 原值獨立保存，不以 ps 空清單宣稱測得完整冷啟動。

本輪單線依原呼叫編號重跑，原輪有併發與 deadline。併發、載入及快取條件不同，因此這組數字不能把差異全歸因於「取消 timeout」。沒有 warm-up、沒有額外生成重試，也沒有重跑正式 baseline。

24 focused tests PASS；只檢查新 CLI／測試的 Ruff F/I/UP/B PASS；所有122個manifest payload重新核對hash，18份來源錄製重新hash，18個送出request都核對只有num_predict改成-1，metadata timeout=None。原始碼實測版[07d81f5](https://github.com/Polalalabear/amidst/blob/07d81f574b5dba12ec87cc5581542ea1c2437aa3/scripts/diagnose_qwen3_untruncated.py) 已保存；其後只作lint調整，沒有重跑模型。CLI對非2xx錯誤會停止，但不保存HTTP錯誤body；本次全部18個回應正常。

LOCAL 產物位於 `$AMIDST_ARTIFACTS/q1q5-qwen3-untruncated_20261026_01a1735f`，共123檔、188838 bytes（含manifest）。MANIFEST SHA-256：`72e77c0ddd9b00af541d15de7d298a1234682959e21289f8640bc17bd26c99f2`。本次新增的這份LOCAL量測包大小即188838 bytes；scratch／Git bytes沒有併入此數，亦不以df變化推算本task用量。輸入與舊素材不修改。

## 重跑

先把 `AMIDST_ARTIFACTS` 設為自己的既有artifact根目錄，`AMIDST_PYTHON` 設為既有Python 3.12以上的解譯器。以下是實測命令的可攜路徑版本；腳本只用stdlib，不需下載套件。輸出路徑必須不存在。

```sh
uv run --no-project --offline --no-cache --python "$AMIDST_PYTHON" python scripts/diagnose_qwen3_untruncated.py \
  --inputs "$AMIDST_ARTIFACTS/q1q5-review-closeout-v1_20261025/timeout-inputs.json" \
  --inputs-sha256 7e075317bc564fda7e76f181e721f5769c7ad7fe5541dc507080027f98eab3ab \
  --baseline-result "$AMIDST_ARTIFACTS/q1q5-review-closeout-v1_20261025/timeout-audit/RESULT.json" \
  --baseline-result-sha256 8a6dee884b99f1eddc1c110b190c17462362ef24a5bdcf11249dc2801748233f \
  --artifacts-root "$AMIDST_ARTIFACTS" \
  --output "$AMIDST_ARTIFACTS/q1q5-qwen3-untruncated_NEW_RUN" \
  --base-url http://127.0.0.1:11437
```

歷史 inputs JSON 自身含原機locator。移機時不得直接修改已pin的原檔；需在本地另外產生locator映射或用來源原根目錄。此版重現命令以持有原錄製的來源機為對象，未驗證跨機執行。公開receipt的locator均相對 `$AMIDST_ARTIFACTS`。

Focused 檢查（以既有測試環境執行）：

```sh
uv run python -m pytest -q -o addopts= -p no:cacheprovider tests/unit/test_qwen3_untruncated_diagnostic.py
uv run python -m ruff check --select F,I,UP,B scripts/diagnose_qwen3_untruncated.py tests/unit/test_qwen3_untruncated_diagnostic.py
git diff --check
```

只連明確指定的 loopback Ollama listener，拒絕 proxy／redirect；前後驗模型 digest，每次呼叫前檢查可用空間至少 8 GiB。不同執行環境的延遲、模型載入／快取狀態不同，重跑不承諾相同延遲。

## 合法性與限制

JSON 格式、wire schema 及 Q3 字面來源限制分開紀錄。格式通過不等於人工答案正確或產品已採用。Q5 schema 中的固定候選引用可檢查，但沒有執行 controller 的狀態、授權、時序及證據 guard，因此 controller acceptance 保持 UNKNOWN。正式 Qwen／RT-DETR 成效、P1／P2 驗收與 #127 完整符合性均不是本輪的驗證對象。

## 檔案歸屬盤點

本輪只新增獨立診斷 CLI、測試、本文及日期化收據；不修改 checkout、index 或既有分支。既有「完成第一版 baseline 規格」對話保留以下範圍（10/26 讀取快照；即時狀態以 #93 為準）：

| 工作 | 分支／PR | 檔案範圍 |
| --- | --- | --- |
| CX-1 | codex/q1q5-contract-d73／#219 | docs/contracts/Q1_Q2_FIRST_DEMO_V1.md |
| CX-2／#142 | codex/q1q5-fallback-observation-fix／#220 | docs/engineering/Q1Q5_PARAMETER_PROPOSAL.md |
| CX-2／#149 | codex/q1q3-guide-review-fixes／#221 | docs/evaluation/Q1Q3_QUESTION_AUTHORING_GUIDE.md |
| CX-2／#160 | codex/q1q5-q5-eval-review-fixes／#222 | Q5_SWITCH_EVAL_V1.md、eval_q5_switch.py、q5_switch_eval.py 及其測試 |
| CX-2／#164 | codex/q1q5-q1-eval-review-fixes／#224 | eval_q1_query.py、q1_query_eval.py 及其測試 |
| CX-2／#147 #151 | codex/q1q5-team-pilot-review-fixes／#226 | TEAM_REVIEW_PACK_REGISTRY.md、build/import_team_review_pack.py 及其測試 |
| CX-3 | codex/r004-graph-v3／#227 | configs/q1q5/graphs/r004、R004_GRAPH_*、r004 review generator／UI／測試 |
| CX-4／5／10 | codex/q1q5-baseline-integration 及後續窄分支 | 既有 runtime／controller／API／workbench／replay／launcher、portable builder／測試及操作文件 |

本對話另獲保留 sanitized LOCAL 交接文件的獨立 docs/operations 目錄，待 CX-6 交 Draft 後另外認領。契約既有分支不由本輪接管。CX-7／8 仍受 G4 約束；OpenAI API 不在本輪範圍。
