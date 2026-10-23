# Q1–Q5 本機 Qwen runtime／離線重播

2026-10-23；依 #144 提案，接在 #112／PR #174 的既有 API。先使用本機 `qwen2.5:7b-instruct`；系統完整後才接 OpenAI API 測試。本文件沒有啟用外部模型服務。

Q3 可選 `LLM_WITH_RULE_FALLBACK`，只將文字拆成封閉詞表／原文片段；Q5 可選 `AGENT_SEQUENTIAL`，以既有工具與有界預算提交決策。RT-DETR、HSV、檢索、local tracking、候選產生、Q4 guard 與執行仍由程式處理。預設 `RULE_ONLY`；未配置 runtime 不自動載入模型。Qwen2.5-7B-Instruct 是文字模型，不持續讀取攝影機畫面。

## 接入方式

既有 registry 仍由 `AMIDST_Q1Q5_REGISTRY` 和獨立的 `AMIDST_Q1Q5_REGISTRY_SHA256` 載入。另給兩個 server 環境變數，再用既有 Application 啟動方式：

```sh
export AMIDST_Q1Q5_OLLAMA_RUNTIME=/absolute/private/runtime.json
export AMIDST_Q1Q5_OLLAMA_RUNTIME_SHA256=<runtime.json 的實際檔案 SHA-256>
```

兩者必須同時存在；path 須為 canonical 絕對路徑，拒絕 symlink、非 regular file、超過 2 MiB 或 file pin 不符。JSON 另有 canonical content hash；file hash 和 JSON 自雜湊不是同一個值。設定錯誤停止載入，不改用猜測值。沒有 registry 時原有 `NOT_READY` 行為保留，不建立合成 run。

`q-demo.ollama-runtime.v1` 固定欄位如下，不接受其他欄位：

| 欄位 | 要求 |
| --- | --- |
| `schema_version` | `q-demo.ollama-runtime.v1` |
| `applies_to` | `scene_id`、`scene_revision`、`run_id`、`detection_index_sha256`、`parameter_set_sha256`、`clock_mapping_sha256` 全部明填；必須精確匹配唯一已註冊 run |
| `base_url` | 明填 HTTP loopback，例如這次既存服務 `http://127.0.0.1:11437`；不是隱含預設 |
| `model` | `qwen2.5:7b-instruct` 或 `qwen2.5:7b` |
| `model_digest` | 必填 64 位小寫 hex，provider 呼叫驗證實際模型 digest |
| `options` | 明填現有 provider／AgentSettings 允許的選項；本次機械 probe 是 temperature=0、seed=7 |
| `q3_template` | `{text,sha256,version}`；版本 `q3-parse.v1`，text 與 SHA-256 一致 |
| `q5_template` | 同一結構，通過既有 AgentSettings 驗證；本次版本 `q5-agent-v1` |
| `agent_authorization_ref` | server 明填對應授權證據；probe 的 `SYNTHETIC_G3_TEST_ONLY` 不可用於正式 run |
| `enable_q3`、`enable_q5` | 各自明填 boolean；false 會移除該 run 舊 provider／factory |
| `content_sha256` | 依 store.canonical_hash 排除本欄計算 |

範本來源是 `configs/q1q5/prompts/q3_parse_v1.txt` 和 `q5_agent_v1.txt`。來源 pins 在建立 provider 前驗證；啟動／bootstrap 不呼叫模型、不 discovery/pull、不重啟 Ollama。既有 Q3 次數／timeout 與 Q5 round／call／total/session 預算保持不變。核准狀態須分開：D65 核准 Q5 call=2000ms／total=5000ms；Q3 的 2000ms 是 PROPOSED，fixture 的 APPROVED／SYNTHETIC 不能替正式 Q3 設定背書。Q5 scheduler 使用該 run 的 `research_interval_us`，同一 SEARCHING episode 的呼叫至少相隔這個時間，等待時間計入既有總預算；它不是新增的 RT-DETR 背景掃描服務。

## 可重現的真 provider 機械 probe

僅在包含上游 Draft 相依檔的工程 source 組合執行；單獨 checkout PR #174 尚不是完整系統。probe 明確匯入現有測試 fixture，來源為 **SYNTHETIC**，不讀正式題目／答案、影像、GT、劇本或 renderer 資料。以下從該組合根目錄執行，`--output` 必須尚不存在、父目錄已存在；使用已安裝環境，不下載模型：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" \
uv --no-cache run --no-project --offline \
  --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python \
  python scripts/probe_q1q5_ollama.py --synthetic \
  --base-url http://127.0.0.1:11437 \
  --model qwen2.5:7b-instruct \
  --model-digest 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e \
  --output /Users/polalabear/amidst-artifacts/q1q5-qwen-runtime-20261023/new-run
```

每次前後記 `df -k`，低於 8 GiB 停止；即使 probe 例外也記 after。完整 prompt／raw output／trace 存私有 LOCAL bundle（0600），不當成一般畫面或靜態檔提供。`runtime.json` 的 SYN scope 不能套到 r004。

真呼叫後，Q3 的 RecordedParseProvider 驗可信 audit hash、輸入／範本／model pin、timeout 和 raw output hash，再跑相同 parser；失敗記錄也重現同一 fallback。Q5 使用既有 RecordedProvider、錄製 clock ticks 與明確無等待 replay scheduler，逐一消耗 trace。probe 比對 Q3 response，以及 Q5 output hash／decisions／links。兩種重播皆不建立網路 transport。既有 API 的 `q_record_response`／`q_recorded_response` 也保留完整 Q3 audit；修正了 API 原本誤把 wrapper 當 provider record 驗 hash 的 409 錯誤，nested record 竄改仍拒絕。

## 2026-10-23 實際結果

LOCAL `/Users/polalabear/amidst-artifacts/q1q5-qwen-runtime-20261023/run-v2/`。使用既有 Ollama 0.35.0、Q4_K_M 模型；manifest／API digest 是上列 `845dbd…697e`。沒有下載、搬動或重新雜湊 4.68 GB 權重，沒有重啟既存服務。

| 實測項目 | 結果 |
| --- | --- |
| Q3 機械文字解析 | 1 次真 provider 呼叫，2000 ms 預算；2002.54 ms 回 `PROVIDER_TIMEOUT`；RULE 成功 PARSED；`llm_parse_used=false` |
| Q5 有界追蹤決策 | 1 次真 provider 呼叫，2000 ms 預算；2002.91 ms 回 `PROVIDER_TIMEOUT`；規則接手 session 並 COMPLETE；`agent_attempted=true`、`agent_used=false` |
| Q3／Q5 離線重播 | 兩者與該次原輸出一致；Q5 decisions／links 也一致 |
| focused | `test_api.py`＋`test_ollama_runtime.py`：62 PASS／0 FAIL |
| 原版 #127 自測 | @994d34c 完整必要原檔：223 PASS／0 FAIL |
| 原版 #127 對真呼叫的 Q3 兜底輸出 | 56 PASS／0 FAIL／0 SKIP |
| 原版 #127 對真呼叫的 Q5 兜底輸出 | 133 PASS／14 FAIL／3 SKIPPED_NO_CONTEXT，overall FAIL |

Q5 14 FAIL＝8 個 SCHEMA_VALID（response 的 links 欄位、6 筆 decision 的 D69 counters、link 檔誤判 detection records）＋6 個連帶 RECORDS 檢查。3 個缺 context 是 link 分類造成 SEARCHING_TRIGGER_TIME 未執行；不是 PASS。沿 #145／#170 追蹤，不刪 D69 欄位迎合舊包，也不修改 #127。最終套件輸入在 `paired-recorded/`：僅把 request／response 檔名改成共同 stem，原 bytes/hash 不變，沒有重跑模型或改回應。早期 scratch kit 缺文件的自測失敗已以完整原 SHA 匯出重跑修正，不當成產品失敗或 223 PASS 的同一執行。

run-v2 前後可用空間 13,179,920 → 13,179,800 KiB，差 120 KiB；這是檔案系統當時變化，不等於本次新增產物大小。實際 artifact 逐檔 SHA-256／大小見同目錄上層 MANIFEST。

## 2026-10-23 續作：載入、暖機與輸出分階段診斷

更正先前紀錄：**Q5 2000ms 是 D65 核准值；Q3 2000ms 仍是 PROPOSED**，見 `Q1Q5_PARAMETER_PROPOSAL.md` §1–2。前次把兩者統稱「已核准2秒」不精確，數字本身與舊 artifact 不重寫。本次延續原 fixture 的2秒比較，沒有將正式 Q3 參數改成 APPROVED。

LOCAL `/Users/polalabear/amidst-artifacts/q1q5-qwen-diagnosis-20261023/`：

| 階段 | 實際觀察 | 可以下的結論 |
| --- | --- | --- |
| 舊服務日誌 | 2秒 client 關閉時模型尚在 load；server 取消 load；續作前 `/api/ps` 為空 | 舊冷啟動失敗不能當 warm 推論成績 |
| 獨立空 prompt 預載 | 6,644.66ms，`done_reason=load`；後續 `/api/ps` 有相同 model digest | 該次已觀察到載入；不是題目解析／Agent成功 |
| 暖機後原 probe | Q3／Q5各2000ms，皆 PROVIDER_TIMEOUT；兩種 offline replay 保持一致 | 單靠先載入仍未解決本次2秒限制 |
| 同 prompt／採樣、15秒診斷：Q3 | 14,726.06ms才有完整provider envelope；server報86輸出token／14,537.835ms，約5.9 token/s；prefill 124.005ms／286 token，load 3.575ms | 該次主要時間在輸出生成，不是load或prefill；單筆資料不是一般硬體效能結論 |
| 同 prompt／採樣、15秒診斷：Q3 task | 使用者機械片段「車」卻回 `class_term=person`，`camera_terms`／`region_terms` 為null | provider envelope通過仍不等於任務通過；違反原文片段／array要求，不能採用為查詢 |
| 同 prompt／採樣、15秒診斷：Q5 | 15,003.02ms仍 PROVIDER_TIMEOUT，無完整envelope | 未取得合法Agent決策；不推估完整往返要多久 |
| 完成版 CLI 的顯式管理預載 | 另一次5,102.41ms、pins及loaded inventory一致，沒有task生成 | 只證明 CLI 的實際管理操作；沒有新的品質成績 |

30秒是本次**管理預載**的顯式上限，15秒是另外兩次**timing-only診斷**的顯式上限；都沒有寫進 parameter_set、產品 provider 或評分結果。原fixture結果只用2000ms那次輸出送原版#127：Q3 **56 PASS**；Q5 **133 PASS／14 FAIL／3缺context**，仍不合staging。87項focused通過，包含新增25項診斷測試；前次62項結果保留其checkpoint。

### 獨立工具與重現

`scripts/diagnose_q1q5_ollama.py` **不被產品啟動器或runtime呼叫**。預設只讀 metadata；只有顯式 `--preload` 才送空prompt載入，必填管理 timeout／keep-alive，工具上限30000ms／300秒。若其他模型佔用同一服務就拒絕；已載入同一digest只觀察，不重載或延長keep-alive；不提供pull／delete／unload操作。較長生成必須另外顯式給 `--measure-timeout-ms`；不能把keep-alive當推論預算。

較長診斷只接受獨立file-pin的SYNTHETIC既有Q3／Q5 probe bundle，先驗 API bundle、model digest、prompt input hash與模板hash。原來源檔不改。輸出固定 `diagnostic_only=true`、`production_or_evaluation_accepted=false`；保留原 `source_probe_timeout_ms`，另記診斷timeout與telemetry。Q3只檢查literal schema／片段，Q5不執行task guard；工具不產domain response／output_sha256，不當正式評分。完整provider audit與envelope均為private LOCAL 0600，每次前後記df、低於8GiB停。

從完整工程source根目錄，重現本次 CLI 管理操作（輸出須新目錄）：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" \
uv --no-cache run --no-project --offline \
  --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python \
  python scripts/diagnose_q1q5_ollama.py \
  --base-url http://127.0.0.1:11437 --model qwen2.5:7b-instruct \
  --model-digest 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e \
  --output /Users/polalabear/amidst-artifacts/q1q5-qwen-diagnosis-20261023/new-diagnostic \
  --preload --preload-timeout-ms 30000 --keep-alive-seconds 300 \
  --q3-bundle /Users/polalabear/amidst-artifacts/q1q5-qwen-diagnosis-20261023/warm-original-budgets/q3-bundle.json \
  --q3-bundle-sha256 b6a16b840a6e7a987565d85ba19a255b8e18ece2ea9bb5da5c67a72e84da069b \
  --q5-bundle /Users/polalabear/amidst-artifacts/q1q5-qwen-diagnosis-20261023/warm-original-budgets/q5-bundle.json \
  --q5-bundle-sha256 e6e5502e8dbd39848169c6adda6a085d8953835d1a2d1cd239b30b80a4b04f2f
```

上例不做task生成；若要明確量同一prompt，可另加 `--measure-timeout-ms 15000`，輸出仍是診斷。沒有自動採用較長timeout、預載、改prompt／sampling／模型或輸出schema。現在已知的阻擋是本機延遲與任務有效性；正式Qwen整段Agent成功仍未完成。

參考[Ollama官方API](https://docs.ollama.com/api/generate)及[官方load說明](https://github.com/ollama/ollama/blob/main/docs/api.md#load-a-model)。目前provider設定 `raw=true`，會略過server prompt templating；是否需另版完整chat framing，尚未做受控A/B，不據此斷言是本次語意錯誤原因。不能用新增ChatML、縮短schema或延長核准Q5預算冒稱只修transport。

## 還沒完成的界線

這次驗證的是實際 transport／pin／timeout／整段兜底／offline replay。沒有成功的模型解析或 Agent 決策，不能聲稱 Qwen 的正確率、速度或優於 RULE_ONLY；沒有量到正式 RGB／RT-DETR 系統效能。續作已拆出單次load／prefill／decode觀察，尚未建立多次量測分布或正式資料表現。較長診斷與顯式模型預載必須另記範圍，不能計為原預算通過；若改產品 sampling／prompt 或研究預算，仍須另走對應契約與參數核定，不暗改本次輸出。

Q3 的真 LLM→Q1/Q2 `llm_parse_used`／origin／hash 相容性仍為 #144 §14-23；本 probe 不執行該下游查詢。#183 無人物證據時 NEXT_CANDIDATE 的契約限制仍待 §14-26 決定；正式 LOST 時限仍待 §14-27。runtime 接線不改上述語意，不新增任意候選順序。正式 r004、#117 graph／exit ROI freeze、#158 G6／HSV 審核、#115／#118、正式人審題目／答案及 Claude 瀏覽器驗收仍分別未完成。本 PR 等級 B 並維持 Draft，原 #127 未通過，不合 staging；不變更 main／mainline、#135。
