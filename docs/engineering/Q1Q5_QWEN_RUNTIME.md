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

範本來源是 `configs/q1q5/prompts/q3_parse_v1.txt` 和 `q5_agent_v1.txt`。來源 pins 在建立 provider 前驗證；啟動／bootstrap 不呼叫模型、不 discovery/pull、不重啟 Ollama。既有 Q3 次數／timeout 與 Q5 round／call／total/session 預算保持不變。Q5 scheduler 使用該 run 的 `research_interval_us`，同一 SEARCHING episode 的呼叫至少相隔這個時間，等待時間計入既有總預算；它不是新增的 RT-DETR 背景掃描服務。

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

## 還沒完成的界線

這次驗證的是實際 transport／pin／timeout／整段兜底／offline replay。沒有成功的模型解析或 Agent 決策，不能聲稱 Qwen 的正確率、速度或優於 RULE_ONLY；沒有量到正式 RGB／RT-DETR 系統效能。也尚未區分冷啟動、warm 模型或 prompt 長度各自造成多少延遲。若要 warm-up、改 sampling／prompt 或延長既有預算，需另列明確實驗與核准值，不暗改本次輸出。

Q3 的真 LLM→Q1/Q2 `llm_parse_used`／origin／hash 相容性仍為 #144 §14-23；本 probe 不執行該下游查詢。#183 無人物證據時 NEXT_CANDIDATE 的契約限制仍待 §14-26 決定；正式 LOST 時限仍待 §14-27。runtime 接線不改上述語意，不新增任意候選順序。正式 r004、#117 graph／exit ROI freeze、#158 G6／HSV 審核、#115／#118、正式人審題目／答案及 Claude 瀏覽器驗收仍分別未完成。本 PR 等級 B 並維持 Draft，原 #127 未通過，不合 staging；不變更 main／mainline、#135。
