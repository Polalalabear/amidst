# WP5 dry-run 預估（2026-11-15）

- Model / effort：Sonnet 5.5 / medium。範圍：D210、D218 之後的 WP5（主要結果是延遲和費用；準確度只記錄）。
- **沒有任何真的呼叫**：這份數字來自 `python -m amidst.agent_eval.wp5_runner --set <set>`（預設 DRY_RUN，0 次呼叫）和 `--fake`（用假 client 跑完整流程，不連網、不讀 key、不讀 GT）。
- **價目表尚未釘死**：`configs/agent_eval/wp5_price_table_v1.json` 的 `status` 是 `UNPINNED_PLACEHOLDER`，三個模型都暫用**偏高的上限**（輸入 5.00／輸出 15.00 USD 每百萬 token）來估規模，**不是真實價格**。使用者提供真實價目（附日期和來源）後，把 `status` 改 `PINNED`、重跑下面的指令，金額會跟著更新，下面兩個核准金額也要重新確認。LIVE 在 `status` 不是 `PINNED` 時拒絕開跑。

## 1. 題組與呼叫數

每題一次「步驟」；OpenAI 與本機模型每個步驟至少一次模型呼叫（DP1／DP3 最多 3 輪，DP4 Agent 最多 5 步，NL 最多 2 次含重試）。Rule 不呼叫模型、不花錢。

| 組 | 題數（DP1／DP3／DP4／NL） | 重複 | 每個模型的步驟 | OpenAI 呼叫（3 模型，名義） | OpenAI 呼叫（最壞情況） | 逾時 |
| --- | --- | --- | ---: | ---: | ---: | --- |
| pilot（D166） | 4／4／4／4 = 16 | pilot 1 + 一致性 5 = 6 | 96 | **288**（與 D166 允許的 288 相同） | 936 | formal 2000／5000／3 |
| formal | 30／30／40／40 = 140（**提議值**，S1+S2 最終題數 UNKNOWN） | 3 | 420 | 1260 | 4140 | formal 2000／5000／3 |
| relaxed_exploration（選用） | 同 formal | 1 | 140 | 420 | 1380 | 10000／30000／3，另外報告，不與 formal 混合 |

pilot 的 16 題 = 每種題型 4 題，所以總數仍是 D166 的 16×(1+5)×3 = 288。本機模型（兩個，q4_K_M）和 Rule 各跑同樣的步驟數（pilot 每個 96），費用 0。

## 2. Token 與費用預估（依暫用上限價目表）

每次呼叫的 token 估計值在設定檔 `task_types`：DP1 1500＋300、DP3 1000＋300、DP4 2500＋300、NL 700＋150（輸入＋輸出上限）。這些是**預估值**，pilot 會量到真實 token 再修正。

| 組 | 每個 OpenAI 模型：輸入 token／輸出 token（名義） | 每個 OpenAI 模型：名義 USD | 3 個 OpenAI 模型：名義 USD | 3 個 OpenAI 模型：最壞情況 USD |
| --- | ---: | ---: | ---: | ---: |
| pilot | 136,800／25,200 | 1.062 | **3.19** | 11.59 |
| formal | 609,000／108,000 | 4.665 | **14.00** | 52.16 |
| relaxed_exploration（選用） | 203,000／36,000 | 1.555 | 4.67 | 17.39 |

假 client 跑完 pilot 的整個流程（`--fake`）驗證了計數：576 個步驟列（6 個模型 × 96）、OpenAI 288 次、輸入 410,400 token，輸出 37,800 token（假 client 只用上限的一半），依暫用價目是 2.62 USD，落在名義估計 3.19 USD 之下，沒有超出。

## 3. 使用者要核准的兩個金額

暫定（依上面的暫用上限價目；價目釘死後要重新確認）。核准金額＝護欄的上限，用最壞情況（每題用滿重試與輪數）進位，所以實際花費預期接近「名義」那一欄，不會超過核准金額：

| 核准 | 金額（USD） | 內容 |
| --- | ---: | --- |
| **① pilot** | **12** | 288 次名義呼叫（最壞 936 次）；名義約 3.2，最壞約 11.6 |
| **② formal** | **55** | 1260 次名義呼叫（最壞 4140 次）；名義約 14.0，最壞約 52.2 |

合計 67，在 D166 的 USD 100 以內；選用的放寬探索組另需約 18（最壞 17.4）才會變成 85，**不含在這兩個金額內**，要的話再單獨核准。護欄先用 `LocalCapGuard`（行程內上限，不是共用護欄）；共用護欄 PR 合併後，換掉 `wp5.Guard` 的實作即可。

## 4. 重跑指令

```bash
python -m amidst.agent_eval.wp5_runner --set pilot --out /tmp/wp5_est_pilot            # 只估算，0 次呼叫
python -m amidst.agent_eval.wp5_runner --set formal --out /tmp/wp5_est_formal
python -m amidst.agent_eval.wp5_runner --set pilot --fake --out /tmp/wp5_fake_pilot    # 假 client 完整流程
```

使用者同意後（例如 pilot 核准 12 USD、價目已釘死）：

```bash
python -m amidst.agent_eval.wp5_runner --set pilot --arm mac --questions <題目檔> \
  --price-table <已釘死價目表> --approved-usd 12 --skip-types DP4 --live --out <輸出資料夾>
```

## 5. 沒驗證和未決事項

- 真實價目、真實 token 數：UNKNOWN（pilot 才量得到）。真實延遲：沒有量；假 client 的延遲是雜湊產生的假數字，不能引用。
- DP4 的即時呼叫（API／Agent）還沒接：等 #532（`attention_api.ApiRanker`）合併，runner 留了 `Context.dp4_ranker` 掛點，LIVE 在沒接上時要用 `--skip-types DP4`（Rule 的 DP4 仍可跑）。接上前 pilot 只有 12 題，名義呼叫數是 216 而不是 288。
- 本機模型的名稱和 digest（`qwen2.5:7b-instruct-q4_K_M`、`llama3.1:8b-instruct-q4_K_M`）沿用 #525 的筆記本；實際 digest 和 Ollama 版本在跑的當天釘死，目前是 UNKNOWN。
- 題目檔（真實的 DP1／DP3／DP4／NL 題）還沒產生；這次 dry-run 用合成題。
