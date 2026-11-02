# CX-8-T baseline 凍結檢查器

狀態：合成機械檢查工具；正式收據 contract **UNSELECTED**。這份文件與
`SYNTHETIC_BASELINE_FREEZE_V1` 都不是 production schema，不核定 #278
合併、不解除 G4／劇本凍結、AC7 或正式 baseline gate。

`scripts/check_baseline_freeze.py`（`cx8t-synthetic-v1`）預設唯讀。未給明示
TEST-ONLY 選項檔與其完整 bytes SHA-256，回 `CONTRACT_UNSELECTED`、exit 1。
即使合成檢查通過也僅回 `SYNTHETIC_VALID`、exit 0，固定：

```json
{"human_approval_verified":false,"formal_run_allowed":false,"production_contract":"UNSELECTED","independent_kit_execution":false,"historical_producer_no_overwrite":"UNKNOWN"}
```

## 依賴到位後怎麼跑

#313 的逐字命令：

```sh
python scripts/check_baseline_freeze.py --receipt <凍結收據 JSON> --recordings <LOCAL 錄製目錄>
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/q1q5/test_check_baseline_freeze.py
```

Python 實際操作用 `uv run python`。正式收據與使用者決定格式未選定時，
第一個命令維持 fail closed。此機器既有離線環境可跑：

```sh
AMIDST_REQUIRE_IMPL=1 uv run --no-project --offline --no-cache --python /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/.venv/bin/python python -m pytest -q -o addopts= tests/q1q5/test_check_baseline_freeze.py
```

此為 LOCAL 工具環境，不是 fixture 來源。測試只產生標 `SYNTHETIC` 的
JSON／JSONL，沒有模型、原影像、GT、formal／clean bytes 或人類回件。

## 測試輸入與八項檢查

pytest 暫存根包含 `recordings/`、`receipt.json`、`contract.json` 與外部
合成 parameter／registry／kit report／merge decision／scoring read 觀察。
`--contract-options <contract.json> --contract-sha256 <完整bytes SHA>` 顯式
選擇 TEST-ONLY projection；每個外部文件與凍結收據都有獨立 bytes pin。
未選、未知 projection 或非 SYNTHETIC role 一律拒絕。正式 decoder 必須
等契約核定後另行接入，不能把 fixture 的欄位拿來替代核定。

1. 外部選項列出的每個 synthetic run 都須有 RULE_ONLY 與
   AGENT_SEQUENTIAL；不能只把整個未完成 run 從收據省略。
2. 直接合成既有 `q-demo.api-recording.v1` 格式的小錄製，交給現有
   `RecordingStore.load`／`QAPI`（僅 recordings，沒有 live runs）執行
   `q_recorded_response` 與 `q2_artifact`。response 由既有 `raw_json`
   序列化，decision／link journal 取原始 UTF-8 bytes，與凍結檔逐 byte
   比較。重新 pin 多餘換行仍會失敗。這是**錄製 API playback**，沒有
   重新跑 RuleController／AgentController kernel，也沒有 RecordedProvider
   kernel 重演或模型呼叫。v2 case 只驗選定版本的錄製 bytes，不宣稱
   完整 v2 schema、推論 consumer 或 #278／#305 整合已驗收。
3. 預算值從 staging434e 的 `configs/q1q5/parameter_set_v1.json` 讀取，
   先驗其 bytes pin
   `960d823c17c181c6b0b128a3cc7f39fb0d5f7af19828073b884d74aa8336ee6e`，
   比對有效 parameter 與 registry 的同名 ms 參數，並驗錄製 response 的
   parameter content pin。沒有在程式寫死新的 2000／5000 預設值；其他
   PROPOSED 參數不因本檢查升為核定。
4. Q5 timeout_calls 由 trace 的 PROVIDER_TIMEOUT 計數；
   rule_fallback_decisions 由 decision journal 的 RULE_FALLBACK 動作計數；
   llm_success_decisions 只計 accepted AGENT decision，且不可多於有效
   非 timeout provider calls。trace audit hash、timeout error 一致性及
   receipt 宣告計數都核對；RULE 接手不能當 LLM 成功。此 projection
   只含 Q2/Q5 控制案例，沒有把未提供的 Q3 指標算成零或成功。
5. 收據對錄製根的**每個**輸出列 bytes SHA，並比對實際完整 inventory。
   錄製時間須不晚於 freeze；freeze 須嚴格早於每個已 pin 的合成評分
   script-first-read 觀察，觀察另綁同一 outputs hash。缺觀察保持 UNKNOWN
   而拒絕，不用空集合假 PASS。只讀時間觀察，從不讀評分劇本／答案。
   這證明宣告的順序一致，不認證歷史程序或觀察來源的真偽。
6. 讀取已 pin 的 `q1q5-conformance.report.v1` 形狀合成報告，核對明示
   適用 domain inputs 的凍結 bytes pin、完整 required check 列表與計數。
   任何 FAIL 拒絕；SKIPPED_NO_CONTEXT／SKIPPED_PARAM_UNSET 每項都須有
   receipt 的 NOT_APPLICABLE 原因。summary 不能藏 FAIL。synthetic
   `SYNTHETIC_CHECK` 是報告結構控制例，不是 #127 真正檢查結果。
   不執行、不修改 #127 kit，也不以這些假報告聲稱獨立 conformance PASS。
7. 每份 Q2 response 的 v1／v2 必須明列，並與外部已 pin 的**合成**
   merge decision 一致；UNSELECTED 或矛盾決定拒絕。這個 seam 不替
   使用者選擇是否合併 #278，真實決定仍需正式來源與已核格式。
8. 錄製目錄必須在 repo 外，拒絕 symlink 與跳出根的 ref；檢查器不改
   輸入。選用 `--output <新目錄>` 寫檢查報告時，也須 repo 外、無
   symlink、目錄不存在，以 exclusive mkdir／O_EXCL 寫 `check.json`。
   已存在目錄／檔案不覆寫。這不能倒推歷史 producer 從未覆寫；該項
   固定 UNKNOWN，正式 freeze producer 仍需其自身建立與發布證據。

只接受靜態離線輸入；檢查期間不可修改檔案。每檔最多 16 MiB，JSON
重複 key／非有限數值拒絕，檔案 open 不跟隨 leaf symlink。不是跨多檔
原子快照或完整事件／效能／科學驗收。#307 未交，架構守門 NOT_RUN。
