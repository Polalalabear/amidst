# WP5 OpenAI 試跑校準（2026-11-15，D233／D237）

- Model / effort：Sonnet 5.5 / medium。使用者核准的上限是 **USD 3**，用來量每個模型、每種題型的 token、延遲和費用，再推算 pilot 與更大題組。
- **題目是合成題**（`wp5_fake.synthetic_rows`，真題庫未定），所以所有數字都是「**合成題基準**」。DP4 的即時呼叫在 runner 裡還沒接上，**這次沒有量 DP4**。
- 每次呼叫都經過 `ApiGuard`（`--approved-usd 3`，`AMIDST_API_USD_PER_DAY=3`，`AMIDST_API_MAX_CALLS_PER_DAY=60`，每分鐘照預設 10）。不讀、不存 API key；帳本已用 `grep sk-` 檢查沒有 key。
- 標示：**〔量測〕** 來自這次實跑；**〔推算〕** 用量測平均乘上題數；**〔UNKNOWN〕** 沒有量。

## 1. 價目（PINNED）

來源 <https://developers.openai.com/api/docs/pricing>，2026-11-15 直接讀原頁 HTML（不是摘要）。第一張表是 Standard、短上下文（輸入 ≤272K）；第二張表剛好是 Batch 半價，沒有使用。單位 USD／百萬 token。

| 設定 id | API model id（使用者確認，D237） | 輸入 | 輸出 | 快取輸入（未使用） |
| --- | --- | ---: | ---: | ---: |
| astra6 | gpt-6-astra | 10.00 | 50.00 | 1.00 |
| sol6.1 | gpt-6.1-sol | 2.00 | 10.00 | 0.10 |
| terra6.1（預設） | gpt-6.1-terra | 1.00 | 5.00 | 0.05 |

`configs/agent_eval/wp5_price_table_v1.json` 已改成 `PINNED`（date 2026-11-15、source 如上）。護欄與估算把所有輸入 token 都當成未快取價，是偏安全的上界。

## 2. 為了能實跑做的程式修改（同一個 PR #546）

1. `api_model_id` 填進 `configs/q1q5/agent_decision_params_v1*.json`；runner 的 `api_model_id()` 讀它，DP1/DP3（`OpenAIProvider`）和 NL（`OpenAINlClient` 新增 `api_model_id`）都送真實 id；沒對應的 id 直接拒絕（`API_MODEL_ID_UNMAPPED`）。**之前實跑會把 `astra6` 這種設定 id 直接送給 OpenAI。**
2. **預設模型 terra**：選設定檔（`wp5_v1.json` 的 `default_openai_model: "terra6.1"`）加 runner 規則：給 `--arm` 且沒給 `--models` 時，OpenAI 只跑預設模型；`--all-openai` 或 `--models` 可以改。dry-run 沒給 `--arm` 時三個模型都估。
3. **OpenAI 拒絕原本的回應 schema**（HTTP 400：`'if' is not permitted`，另有懸空 `$ref`）：第一次實跑 DP1/DP3 因此全部失敗（0 token，沒有計費）。`OpenAIProvider` 改送 #546 已有的 `ollama_format_schema`（內嵌 `$ref`、拿掉 if/then/else/uniqueItems，這些仍由 `validate_response` 在呼叫後檢查），`strict` 改 `false`（`candidate_id` 是選填）。
4. 測試：`tests/q1q5/test_wp5_openai_api_ids.py`（新，12 項：id 對應、DP 與 NL 送出的 model、預設 terra、PINNED 價目）；更新 `test_agent_decision_wp1.py`、`test_agent_providers_wp3.py` 兩處斷言。

## 3. 實跑設定與結果〔量測〕

- 逾時用 **relaxed（10 s／30 s，標 EXPLORATORY）**，不用 formal（見 §5：formal 的 2 s 對這些模型幾乎一定逾時，會讓每題重試而混淆 token 量測）。
- 取樣：terra 每種題型 6 題（DP1／DP3／NL，共 18），sol、astra 每種 2 題（各 6），共 30 步、**每步 1 次呼叫**；加上 2 次除錯探測（確認 400 的原因和 `candidate_id` 空字串）。DP4 跳過。
- 每分鐘上限 10：分段執行，每段之間等 66 秒，沒有調高。
- **實際花費：USD 0.1025（依帳本裡有 token 用量的 31 列，用 PINNED 價目計；這是量到的真實用量）。護欄帳本總估計 0.1360 USD 是上界**（多出的 0.034 是 11 筆被 HTTP 400 在模型執行前就拒絕的請求、1 筆錯誤，都用預估價記，OpenAI 實際沒有計費）。**遠低於 USD 3 上限。**
- 帳本 51 列：OK 且有用量 31、OK 但無用量（400 拒絕）11、DENIED 8（第一次實跑撞到每分鐘上限）、ERROR 1（terra 的一次 NL 呼叫，被規則退回）。token：輸入 15,230、輸出 3,900。實跑總呼叫（含被拒的 400）約 43 次，低於 60。

### 每個模型×題型（由 `scripts/agent_decision/wp5_calib_report.py` 算出）

| 模型 | 題型 | n | 輸入 token | 輸出 token 平均（標準差） | USD／次 | 延遲 p50 ms | 延遲 p95 ms | 有效答案 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| terra6.1 | DP1 | 6 | 594 | 116 (11) | 0.00117 | 2682 | 2975 | 0/6 |
| terra6.1 | DP3 | 6 | 454 | 171 (28) | 0.00131 | 3475 | 3852 | 1/6 |
| terra6.1 | NL | 6 | 396 | 115 (50) | 0.00097 | 2712 | 6733 | 5/6 |
| sol6.1 | DP1 | 2 | 594 | 82 (15) | 0.00201 | 4158 | 4400 | 2/2 |
| sol6.1 | DP3 | 2 | 454 | 108 (6) | 0.00199 | 4333 | 4483 | 2/2 |
| sol6.1 | NL | 2 | 396 | 115 (74) | 0.00194 | 3631 | 5060 | 2/2 |
| astra6 | DP1 | 2 | 594 | 105 (1) | 0.01119 | 4384 | 4442 | 2/2 |
| astra6 | DP3 | 2 | 454 | 135 (1) | 0.01129 | 4694 | 4810 | 2/2 |
| astra6 | NL | 2 | 396 | 158 (117) | 0.01186 | 5643 | 8937 | 2/2 |

註：sol／astra 每格只有 2 筆，p95 只是兩筆的內插，**不能當作穩定估計**。輸入 token 在合成題裡每種題型是固定值。延遲含網路來回，從這台 Mac 到 API，各呼叫序列執行。

### 發現（要使用者知道）

1. **延遲遠超 formal 的 2 s 單次上限**：所有模型 p50 約 2.7–4.7 s。formal 設定下這些呼叫幾乎都會 TIMEOUT 退回規則，並（最多 3 輪）重試；逾時的呼叫 OpenAI 仍會計費。formal 組的結果會變成「幾乎都是規則」，要不要放寬 formal 逾時是決策，不是這份文件能決定的。
2. **terra 的 DP1／DP3 多半被判 INVALID_RESPONSE**（DP1 0/6、DP3 1/6）：探測顯示它在不選候選時回 `"candidate_id": ""`，不符合 opaque id 規則；sol／astra 沒有這樣。這是非 strict 模式的副作用；建議的修法是在 provider 解析後，action 不是 SELECT 時丟掉空的 `candidate_id`。**這次沒有改**（它改變模型輸出的處理，應該另外決定），所以 terra 的 DP1／DP3 成本是量到了，但「有效率」偏低，不能引用為品質結論。準確度本來只記錄不排名。
3. 實際輸入 token（394–594）只有設定估計（700–1500）的約 40–60%；輸出 token 約 80–210，遠低於上限 300（含推理 token，API 的 completion 計數）。

## 4. 推算〔推算〕（合成題基準；不含 DP4）

每個模型 pilot（4 題×(1+5)＝DP1／DP3／NL 各 24 步）和 formal（提議題數 30／30／40×3 重複＝90／90／120 步；DP4 另外 120 步未含）。「合成」欄用量測的輸入 token；「設定估計」欄把輸入換成設定檔的估計（1500／1000／700），代表真題可能更長的上界。± 是 2 個標準誤（只算輸出 token 的抽樣誤差；輸入 token 的差異看右欄）。

| 組 | 模型 | 呼叫 | 合成 USD (±2 SE) | 設定估計 USD（上界） |
| --- | --- | ---: | ---: | ---: |
| pilot | terra6.1 | 72 | 0.083 ± 0.014 | 0.125 |
| pilot | sol6.1 | 72 | 0.142 ± 0.045 | 0.227 |
| pilot | astra6 | 72 | 0.824 ± 0.223 | 1.246 |
| formal | terra6.1 | 300 | 0.340 ± 0.064 | 0.507 |
| formal | sol6.1 | 300 | 0.593 ± 0.206 | 0.927 |
| formal | astra6 | 300 | 3.446 ± 1.032 | 5.118 |

**含 DP4 的上界**（DP4 沒量：輸入用設定估計 2500，輸出用該模型 DP3 平均）：pilot 每個模型 terra 0.21、sol 0.37、astra 2.01；formal 每個模型 terra 0.91、sol 1.66、astra 8.93（USD）。三個模型 pilot 全跑 ≈ **2.59**（上界），比原 dry-run 的 3.19（用 5／15 暫用價目）低。

**重試倍數**：formal 逾時會讓步驟最多重 3 輪（dry-run 最壞／名義 ≈ 3.25 倍）。核准額度要留這個倍數，實際花費預期接近名義值。

## 5. 建議額度（三個方案；帳戶約 USD 150）

額度＝護欄的 `--approved-usd` 總額上限。以含 DP4 的上界乘 3.25（最壞重試）再進位：

| 方案 | 內容 | 上界（名義） | 最壞（×3.25） | 建議核准額 | 用途 |
| --- | --- | ---: | ---: | ---: | --- |
| **A 便宜（預設 terra）** | terra：pilot＋formal（含 DP4） | 1.12 | 3.62 | **USD 4** | 預設 terra 的延遲／費用主結果，Rule 與本機模型對照 |
| **B 混合** | A＋sol 與 astra 各跑一次 pilot 當價格／延遲對照 | 3.50 | 11.36 | **USD 12** | 主結果之外，回答「貴的模型多花多少、延遲差多少」 |
| **C 全部最強** | 三個模型 pilot＋formal 全跑（含 DP4） | 14.08 | 45.76 | **USD 46**（astra 占約 78%） | 完整三模型比較；astra 單價最貴，必要性要使用者決定 |

建議先核准 **A（USD 4）**：花費最小、直接對應預設模型；等 DP4 即時呼叫接上、terra 的空 `candidate_id` 處理決定後再執行。B、C 沒有技術阻礙，但 C 的大部分花費來自 astra，而且 formal 的 2 s 逾時不調整的話，三個模型的 formal 結果大多是規則退回，額外花費的價值有限。

## 6. LOCAL 成品（`local/evidence/wp5-openai-calib-20261115/`，不進 git，無 key，用 `grep sk-` 檢查過）

| 路徑 | 大小 | SHA-256 | 可否重建 |
| --- | ---: | --- | --- |
| `guard-ledger/usage.jsonl` | 9,374 bytes（51 列） | `c4d88c313398fe0d71802c10b8247d0c007bb454c826d19471c7b26caba93ea6` | 不可重建（真實呼叫的帳本） |
| `SHA256SUMS`（`runs/`、`failed_v0_schema400/`、`guard-ledger/` 共 33 個檔案的逐檔雜湊） | 約 3 KB | `5a5b97cbc6356b96230b8c7adf1f7153554cb056333dc77b995ddcdb1644b620` | 不可重建 |
| `runs/{terra_DP1,terra_DP3,terra_NL,sol_all,astra_all}/`（`calls.jsonl`、`summary.*`、`MANIFEST.json`） | 資料夾合計 156 KB（含其他） | 見 `SHA256SUMS` | 不可重建（需再花錢重跑） |
| `failed_v0_schema400/`（第一次失敗的實跑，保留作證據） | 同上 | 見 `SHA256SUMS` | 不可重建 |
| `wp5_calib_config.json`、`questions.jsonl`、`run.sh`（實跑用的設定、合成題、分段指令） | 小 | `9287806e…`、`9d42ee5c…`、`8bba58c8…`（前 8 碼；完整值用 `shasum -a 256`） | 可由 `wp5_fake.synthetic_rows` 與本文重建 |

## 7. 重現

```bash
# 只估算，0 次呼叫
python -m amidst.agent_eval.wp5_runner --config <calib config> --set calib_terra --skip-types DP4 --out <out>
# 實跑（需 OPENAI_API_KEY 在環境；不要把 key 寫進指令）
AMIDST_API_USD_PER_DAY=3 AMIDST_API_MAX_CALLS_PER_DAY=60 AMIDST_API_USAGE_DIR=<ledger dir> \
python -m amidst.agent_eval.wp5_runner --config <calib config> --set calib_terra --models terra6.1 \
  --questions <questions.jsonl> --arm mac --skip-types DP4,DP3,NL --price-table configs/agent_eval/wp5_price_table_v1.json \
  --approved-usd 3 --live --out <out>
python scripts/agent_decision/wp5_calib_report.py <evidence dir>
```

## 8. 沒驗證和未決

- DP4 的即時呼叫（#541 的 API／Agent 版本）還沒接到 WP5 runner，DP4 的 token、延遲、費用 **UNKNOWN**，上面只有上界推算。
- 真題的 token 數 UNKNOWN（合成題基準）。sol／astra 每格 n=2，變異估計很粗。
- 延遲只有一台 Mac、單一時段、序列呼叫；不是 L4 數字，也沒有並行。
- terra 的 `candidate_id: ""` 問題（§3 發現 2）和 formal 逾時是否放寬，是待決策項目，這份 PR 沒改。
