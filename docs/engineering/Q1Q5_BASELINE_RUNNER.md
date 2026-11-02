# Baseline v1 工程接線與產製預檢

2026-10-24（Asia/Taipei），[#194](https://github.com/Polalalabear/amidst/issues/194)。沿 [#192 協定](Q1Q5_BASELINE_V1_PROTOCOL.md)／[配置](../../configs/q1q5/baseline_v1_protocol.json) 提案，重用 #174 runtime、#185 `measure_call`／`verify_replay`、既有 Q API／RecordingStore／RecordedProvider。沒有改 #127／#135、核准預算、domain schema 或原審查包。

#192 原檔中的 `runtime_loader_implemented=false` 保留該次交付狀態；本輪新增的是工程消費者，未把原 `measure_q1q5_baseline.py` 或正式產品入口改成接受這份配置。

## 可執行範圍

`run_q1q5_baseline.py` 現可讀獨立 file-pin 的 protocol、case catalog 與 source composition，以每個 case×profile 一個獨立程序，依序跑 1 首回＋2 暖呼叫。每次用相同 bindings 與模型設定建立新的 QAPI，避免舊 session cache 令暖呼叫不執行模型。模型 provider 可在同一 worker 重用，但不把首回／暖呼叫稱為已量過冷／暖模型。

目前入口只接受明示 `--synthetic` 的 SYNTHETIC 工程案例；正式／PILOT 保持拒絕，不能改 JSON 的 `allowed` 便取得核定。這不是正式 baseline 或可直接執行 A4／B4 的承諾。正式啟用仍需獨立核定、凍結及產品契約前置後另行接續。

兩個 profile 分開執行：`QWEN3_RTDETR_V1` 使用 Q3 `LLM_WITH_RULE_FALLBACK`、Q5 `AGENT_SEQUENTIAL`；`RULE_ONLY_RTDETR_V1` 兩階段均 RULE_ONLY。Q1 不啟用 Q5；PRESET 不啟用 Q3。API 原 Q3／Q1／Q2 回應與 journals 不改寫；Q3 真的採用 LLM 時，下游 lineage 另記 `UNRESOLVED_SECTION_14_23`，不自行改寫原 response flags／hash。

預設沒有任何模型呼叫。`--fixture scripted|timeout|invalid|unavailable` 明確引用本包的合成測試 helper；透過選定 Qwen3 tag／假 digest、現有 v2 prompt 與 native wire/audit validator，重現合法採用及各種兜底。它是 **SCRIPTED transport，不是真 Qwen／RT-DETR 推論**；題目只是機械控制字串，沒有正式 Q3 expected 或模型品質分母。

也可明示 `--registry <file> --registry-sha256 <pin>` 載入既有 QAPI。選用既有本機 runtime 時另給 `--runtime <file> --runtime-sha256 <pin> --allow-local-model-calls`；沒有 explicit permission 就在 provider 呼叫前拒絕。仍要求註冊的來源與 case 均是 SYNTHETIC。既有模型／digest／prompt／時間預算及 loopback transport 由原 runtime 驗證，不下載、預載、重啟或卸載模型。正式 Q3 timeout／max attempts 核定沒有由機械 fixture 代填。

RT-DETR 沿既有「離線索引→同一索引供兩種 profile 使用」資料流；此查詢入口不載入／重新執行 detector，不把索引速度當 inference fps。真 RGB、正式 RT-DETR index、正式 Qwen 效果、模型載入／常駐／VRAM均未由這次合成接線驗證。

## 輸入、紀錄與失敗

case catalog 沿協定的十個欄位。TEXT 與 PRESET 互斥；`binding_id` 在本工程 adapter 精確等於該 run 的 index content SHA-256，context pin 必須等於 clock hash。選定 seed 的 observation／frame／camera／SOURCE us 均驗原索引，不自動挑多候選。TEXT 解析結果超出 case 相機或時間窗就拒絕，不偷偷縮窗、補條件或擴大查詢。Q2 尚不支援的窄相機 subset 不繞過原契約。

每個 sample 保存 private request、原 response、API recording receipt、原 domain 文件／index records／snapshots／evidence、decision/link journals、flags、逐階段 telemetry 與重播結果。`private/` 中 API 錄製含 raw model audit／trace，目錄0700、檔案0600，不交靜態 server／公開 repo。新輸出必須 canonical、非 symlink、repo 外、parent 已存在；所有檔案 exclusive create，不覆寫。

`stages.q3/index_search/q5` 用原 `measure_call` 包實際 QAPI 呼叫，記 wall／CPU ms 與 **呼叫者程序生命週期 peak RSS**。`wait_ms` 從該 sample 接受後到 batch API response 可用，用 monotonic clock；first_result 無匹配時為 null，completion 仍可量。完整結果尚有 next_cursor 時不能報全數完成。這是同步 batch 回應，並非串流首筆或瀏覽器 presented 時間；worker Python 啟動、fixture／registry setup 另記，record／freeze／replay 在 response-ready 計時之後執行。

Q3、Q5 分別記 attempted／used／provider_calls／timeouts／fallback／原 status。`used=true` 僅代表 guard 採用，不能當人工正確；TIMEOUT 後 RULE 接手不算 LLM 成功，也不是獨立 RULE_ONLY 對照的那筆執行。Q5 保持原 call2000ms／total5000ms，fallback budget只記錄、不截斷整段RULE。Q3 2000ms仍PROPOSED；本次無延長診斷預算。

模型載入／建索引／推論與顯示fps、模型／server／browser sampled RSS、系統memory／VRAM、使用者端到端、accuracy保持 null 與原因；不拿 source5fps、索引 replay 或 caller RSS冒充它們。FOUND／LOST／切鏡及LOST後同／異鏡頭支持恢復是明示 `lost_after_us` 的合成工程事件，正式時限仍未核定。MISSING／NOT_INFERRED／PARTIAL 不當不存在，identity=UNCONFIRMED、物理通行／碰撞 UNKNOWN。

worker timeout、缺worker／report、例外、pin差異或replay差異使整體 ERROR；保留所有樣本。worker timeout後不再發下一個worker，因為 client中止不代表Ollama server已停。`COMPLETE` 只表示本次工程計畫／錄製／重播完成，不代表LLM在預算內成功、符合性或人工驗收。每次前後df-k，低8GiB停止；沒有任何清理或原資產操作。

## 離線重播

API recording先經原 RecordingStore pin／domain hash檢查，再由只有recordings、沒有live runs的QAPI提供原response。另做真正的kernel重執行：Q3用RecordedParseProvider；Q5 Agent用RecordedProvider、原clock ticks與明示no-wait replay scheduler；RULE/Q1沿原kernel。逐stage檢查output hash；Q5兩份journal bytes也須完全一致，且錄製provider events全部消耗。replay不建立live transport，provider／network calls=0，重播耗時不算模型效能。

## 操作

需使用交付的 **完整 source composition**，單一 Draft checkout 仍不等於產品整合。`COMPOSITION.json` 記逐檔commit／bytes hash；本次source-only組合不含原Blender、RGB、GT或權重。T1–T4的CSS均為各自相對staging的append-only增量，組合時按T1→T4附加，manifest另記每個原輸入及結果hash，沒有修改owner PR。

在該source根目錄，先指定既有Python、各輸入**實際file hash**與全新LOCAL輸出，再執行：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$Q1Q5_SOURCE/src:$Q1Q5_SOURCE/tests/q1q5" \
uv --no-cache run --no-project --offline --python "$Q1Q5_PYTHON" \
python "$Q1Q5_SOURCE/scripts/run_q1q5_baseline.py" \
  --synthetic --fixture scripted \
  --protocol "$Q1Q5_PROTOCOL" --protocol-sha256 "$Q1Q5_PROTOCOL_SHA256" \
  --cases "$Q1Q5_CASES" --cases-sha256 "$Q1Q5_CASES_SHA256" \
  --composition "$Q1Q5_COMPOSITION" --composition-sha256 "$Q1Q5_COMPOSITION_SHA256" \
  --worker-timeout-ms 60000 --lost-after-us 600000 --output "$Q1Q5_NEW_OUTPUT"
```

60000ms只限本次工程worker外層防掛死，不修改模型call／total預算；600000us只限既有SYNTHETIC事件控制。五情境×兩任務×兩profile×三次＝60 samples；不是60個不同Q3題目。換成其他fixture故障模式要用另一個新輸出；原CASE catalog／pins不改。

## 正式產製唯讀預檢

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$Q1Q5_SOURCE/src" \
uv --no-cache run --no-project --offline --python "$Q1Q5_PYTHON" \
python "$Q1Q5_SOURCE/scripts/preflight_q1q5_production.py" \
  --protocol "$Q1Q5_PROTOCOL" --protocol-sha256 "$Q1Q5_PROTOCOL_SHA256" \
  --repo "$Q1Q5_REPOSITORY" \
  --review-manifest "$Q1Q5_REVIEW_MANIFEST" \
  --review-manifest-sha256 "$Q1Q5_REVIEW_MANIFEST_SHA256" \
  --output "$Q1Q5_NEW_PREFLIGHT_REPORT"
```

BLOCKED的exit code為2；這是缺核定／凍結的正確預檢結果，不是產製通過。只讀明列protocol、Git source refs及原審查manifest鎖定的五份安全metadata（build_sources、camera_catalog、兩層圖、HSV config），不掃描或讀editable RETURN、影像、原.blend、GT／劇本。摘要記來源／校正hash；不把存在或hash相符當人類核准，也不說本次重新hash過原.blend／weights。

沿#115最新紀錄，D70已有A4四台／B4五台、各30s／5fps／960×540授權；正式run ID、相機子集與clock/RGB/index pins未凍結就null。yyin回收CSV／問題清單／完整folder或ZIP、Claude獨立圖/ROI、必要HSV核定仍分離；原包不回改。既有index CLI目前仍固定r003／A-B1 registration，不能拿來產正式r004，後續#118需接正式registration與設定；本輪沒有執行該producer。

## 本輪驗證與仍待處理

指定Python focused是 `test_baseline_runner.py`、`test_production_preflight.py`、原 `test_api.py`；JS為 `q3-bar-view.test.mjs`、`q3-bar-model.test.mjs`、`q-api.test.mjs`、`q2-session-model.test.mjs`。只對本任務Python檔Ruff及diff檢查，不跑全suite。原版#127固定994d34c對本輪domain錄製完整跑；其FAIL／缺context照實保留，不能把工程sidecar稱為舊kit已認證。

工作台Q3現在可明選規則／Qwen3，未配置Q3 provider時LLM選項禁用；Q5模式仍是獨立選擇。PARSED→Q2複製request並套操作者選定的既有switch_mode，不改Q3原回應／hash；Q1與recorded replay不改。只驗合成資料與既有API接線，正式RGB、真模型效用及Claude獨立browser／Demo驗收仍未完成。

正式最小Q3題組／獨立expected仍未準備與凍結，本次控制案例排除正式分母。§14-23 lineage、#183空證據NEXT、正式LOST時限、Q5 stop／同步競態與其他strict XFAIL未由此接線修正；#145仍交Claude對齊原測試包。必要前置→凍結→正式RGB→正式index→兩任務baseline→輸出凍結→人工評分的順序不變。本交付B／Draft、不merge，main／mainline／staging不動。
