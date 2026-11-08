# Epic D 路徑 (b)：錄製 Qwen3 1.7B 的自然語言解析（給 Codex）

Refs [#489](https://github.com/Polalalabear/amidst/issues/489)、設計稿 [`docs/specs/EPIC_D_AGENTIC_V1.md`](../specs/EPIC_D_AGENTIC_V1.md) §5.2、決策 D134。

## 這份錄製是什麼

- `scripts/record_nl_options.py` 用本機 Ollama 的 `qwen3:1.7b-q4_K_M`，把 `configs/epicd/nl_sentences_v1.json` 的固定句子逐句送出，輸出 `q-core.agent-recording.v1`（`data_origin: QWEN3_RECORDED`）。
- 畫面和 API 讀這個檔重播，不再連 Ollama；同一個錄製檔加同一句話，輸出 byte 完全相同。
- repo 內建的 `configs/epicd/nl_recording_synthetic_fixture_v1.json` 是 `SYNTHETIC_FIXTURE`（由規則解析器算出，不是模型輸出），只用來讓畫面和測試能跑。**真正的 Qwen 錄製檔不要覆蓋它，另存新檔。**
- 只連 `127.0.0.1:11434`。不需要任何 API key，不執行 OpenAI。腳本不 render、不看媒體、不讀 GT。

## 步驟（在 Codex 的本機執行）

1. 確認 Ollama 在跑，且已有模型（沒有就 `ollama pull qwen3:1.7b-q4_K_M`）：

```bash
curl -s http://127.0.0.1:11434/api/tags | head -c 400
```

2. 啟動要錄的那個後端（真實資料的 run），存下它的 bootstrap（句子用的目錄必須和伺服器一致，重播才對得上 prompt）：

```bash
curl -s http://127.0.0.1:<PORT>/api/q_bootstrap > /tmp/epicd_bootstrap.json
```

3. 錄製（`<RUN_ID>` 取自 bootstrap 的 `runs[].run_id`；`--timeout-ms` 刻意放寬，Qwen3 1.7B 不設上限時中位數約 5.8 秒）：

```bash
python scripts/record_nl_options.py --bootstrap /tmp/epicd_bootstrap.json --run-id <RUN_ID> --out configs/epicd/nl_recording_qwen3_1p7b_v1.json
```

4. 輸出會列出每句的耗時、錄製狀態（OK／PROVIDER_TIMEOUT／INVALID_RESPONSE）、離線重播後的 `decided_by/fallback_reason/status`，最後一行是 `recording_sha256` 和 `model_digest`。把整段輸出貼回 #489。
5. 檢查錄製檔對得上這個後端的目錄（離線，不連模型；不一致時畫面會顯示「退回規則：錄製檔沒有這句話」）：

```bash
python scripts/check_nl_recording.py --recording configs/epicd/nl_recording_qwen3_1p7b_v1.json --bootstrap /tmp/epicd_bootstrap.json --run-id <RUN_ID>
```

   最後一行是 `RESULT MATCH` 才算對上；`MISMATCH` 會列出哪幾句沒對上、目錄是否一致。

5b. 驗證重播（不連 Ollama）：

```bash
AMIDST_NL_PROVIDER=RECORDED AMIDST_NL_RECORDING=configs/epicd/nl_recording_qwen3_1p7b_v1.json python -m pytest tests/q1q5/test_nl_options.py -q
```

6. 用這個錄製檔跑 API：啟動後端前設 `AMIDST_NL_PROVIDER=RECORDED AMIDST_NL_RECORDING=<錄製檔路徑>`（預設就是 RECORDED；沒設路徑時用 SYNTHETIC_FIXTURE，真實目錄對不上，會顯示「退回規則：錄製檔沒有這句話」）。

## 要回報什麼

- 錄製檔路徑與 SHA-256、`model_digest`、耗時表（每句 `latency_ms`，單位毫秒）。
- 各句錄製狀態與重播結果，特別是 `INVALID_RESPONSE`／`PROVIDER_TIMEOUT` 的句子（這是 Qwen3 1.7B 在這個 schema 下的合法率證據，不要重錄到全部通過）。
- 不要提交錄製檔，除非使用者指示；要提交時用 `Model / effort` 與 SHA-256 照 AGENTS.md 範本寫實際產出。

## 其他 provider（不在這次錄製範圍）

- `AMIDST_NL_PROVIDER=OLLAMA`：現場跑本機 Qwen（單步，要等數秒）。
- `AMIDST_NL_PROVIDER=OPENAI` 且 `AMIDST_NL_OPENAI_ENABLED=1` 與 `AMIDST_NL_OPENAI_MODEL`：金鑰只從環境變數 `OPENAI_API_KEY` 讀，不印、不寫入紀錄；第一輪驗收之後才開（C-3）。
- `AMIDST_NL_PROVIDER=NONE`：只用規則。
