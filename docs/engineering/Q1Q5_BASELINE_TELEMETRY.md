# 一次查找／持續追查的共用量測入口

本入口已可執行 **SYNTHETIC、RULE_ONLY** 的直接 kernel 工程驗證。
正式 r004 RGB／索引、HTTP／工作台整合與人工審查仍依原本前置條件完成；
此文件及工程通過不授予 G4、新 HSV G6 或正式成效驗收。

## 使用與輸出

在固定 source composition 中，用既有 Python environment 執行：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$Q1Q5_SOURCE/src" \
uv --no-cache run --no-project --offline --python "$Q1Q5_PYTHON" \
python "$Q1Q5_SOURCE/scripts/measure_q1q5_baseline.py" \
  --synthetic --lost-after-us 600000 --warm-repeats 2 \
  --output "$Q1Q5_NEW_OUTPUT"
```

`Q1Q5_SOURCE` 是組合來源資料夾，`Q1Q5_PYTHON` 是已安裝依賴的 Python；
`Q1Q5_NEW_OUTPUT` 必須為全新、絕對且無 symlink 的路徑，parent 已存在。
每次產製前後保存 `df -k`，可用空間低於 8 GiB 即停止；不下載模型、不渲染、不清快取。
Windows 尚未實機驗證，缺 `resource` 的平台將 RSS 記為 UNKNOWN，不填假值。

`lost_after_us` 必填；600000 只是兩秒合成控制情境的工程值，
不是正式追丟期限，也不改 link gap 或任何已核准參數。

五情境是：有支持的候選、所有候選空、暫失後原鏡頭恢復、候選畫面缺失、沒有選定起點。
這是程式控制案例，沒有組員題目、標準答案或正式 T/F。
每個情境各跑 ONCE_SEARCH／CONTINUOUS_PURSUIT，使用不同子程序；
每程序第一回一次、暖呼叫兩次，共 10 個 worker／30 次呼叫。
兩次暖呼叫也做離線重播核對，共 20 次：Q1 的 output hash、Q2 的 output hash／兩份 journal bytes 應一致。
第一回只做自身完整性檢查，不冒稱多做一次重播。

交付資料包括：

- `REPORT.json`：整體狀態、環境、磁碟、全部逐次數值及錯誤。
- `<case>/<workflow>/telemetry.json`：該程序 setup 與逐次量測、SOURCE flags／決策。
- `<case>/<workflow>/recorded/`：原 domain request／response、圖／參數／clock／index pins、原始紀錄。
- `MANIFEST.json`：該次產製檔案的 bytes SHA-256。若額外封裝來源／測試證據，另用交付 manifest。
- `worker.stderr.txt`：執行錯誤供本機診斷，含私有 locator 時不可直接公開。

任一 worker 失敗、超時、缺少報告或 domain 重播改變，整體即 ERROR，不能只計成功案例。
沒有起點回 NO_SEED；缺影像維持 PARTIAL／未評估，不能當作「不存在」或已追丟。
kernel 先凍結原輸出，flags 只轉換它；沒有額外授權切鏡。

## 數值定義與範圍

| 欄位 | 定義／限制 |
| --- | --- |
| setup.wall_ms | 匯入 fixture helper、建立機械索引／圖／參數及綁定，不是模型載入時間；不含 Python 啟動及先前 module imports |
| samples.wall_ms | 直接 Q1 查索引，或建立新 RULE_ONLY Controller 並執行 Q2；用 perf_counter_ns；不含報告、磁碟、hash比對或flags轉換 |
| process_cpu_ms | 同一次 operation 的 process_time_ns 差；與 wall 分開，不能當使用者端延遲 |
| FIRST_CALL | 全新程序在 fixture setup 後的第一個 kernel call；不是冷模型／清空 OS cache |
| WARM_REPEAT | 同程序、同 pins、重新呼叫 kernel；不聲稱暖模型 |
| process_peak_rss_before/after_bytes | 程序啟動以來 peak RSS，macOS 原值 bytes、Linux KiB 轉 bytes；不是當前RSS、單次配置、系統RAM或GPU記憶體，不能相減當作本次配置量 |
| provider_calls | 本版兩模式都驗 agent_attempted／agent_used=false，再記0；沒有把機械索引當真RT-DETR推論 |
| flags／decisions | 每次 FOUND／LOST、來源時間、切鏡、候選／觀測ref；LOST只表示支持未恢復，absence UNKNOWN |
| model_inference_fps | 本版 null。未呼叫 RGB 模型，不能拿索引回放速度或來源5fps代替 |
| display_fps | 本版 null。未執行 UI 播放或測量 presented frames |
| accuracy | 本版 null。沒有人工答案或正式評分 |

Q1 為一次索引查詢，不啟動持續監看；Q2 為逐 SOURCE tick 的同鏡頭連接、圖約束候選、
實際 Q4 evidence port 與 RULE_ONLY 決策。沒有 Qwen、Ollama、GT、event script、actor metadata 或新 RGB。
相機／圖／參數均為既有機械 fixture 的 SYNTHETIC pins，不使用或回改正在審查的 r004 v2 包。

`measure_call` 可供後續真實 detector／HTTP 呼叫使用，但接入這些路徑仍須另做工程整合；
只有實際完成的推論／顯示 frames 才可用 `frame_rate` 計算各自 fps。
目前沒有現場 HTTP、端到端輸入至畫面完成時間、真模型載入或真實找回率資料。

## 契約與後續

本次只新增 runtime sidecar、CLI、focused tests 與本說明；不改原 domain schema、hash、
排序／guard／圖語意、#127、#135 或任何核准數值。
原 #127 仍以固定 `994d34c8340855dbf0e28d0273851049df5e6c7d` 對 `recorded/` 全套執行；
telemetry 是新的工程紀錄，另以 focused tests 驗證，不冒稱由舊 kit 認證。
既有 D69／link 分類與空 journal 差異仍交 #145；未通過時 PR 維持 B／Draft。

人工審查期間可繼續產品接線與必要設定預檢。正式流程仍是必要審查核定／程式前置完成 →
凍結 → A4/B4 正式 RGB → 正式索引 → 一次查找／持續追查 baseline 實測 →
輸出凍結 → 人工 T/F 與評分。LLM／YOLO-World／進階 ReID 比較後排。

## 2026-10-24 本機工程結果

LOCAL `~/amidst-artifacts/q1q5-baseline-telemetry-v2_20261024/`，Darwin arm64／Python 3.12.12。
5情境×2流程；每流程1次首回＋2次暖呼叫，共30次，20次重播核對一致。
未控制其他系統負載；每流程各有獨立程序，RSS仍是該程序生命週期peak。
下表僅機械fixture和直接kernel，不能當作正式r004、RT-DETR、Qwen、HTTP或畫面端效能。

| 流程 | 首回wall範圍 ms，5筆 | 暖呼叫wall中位數 ms，10筆 | 程序peak RSS範圍 MiB |
| --- | --- | --- | --- |
| ONCE_SEARCH | 0.528–0.833 | 0.509 | 41.30–41.64 |
| CONTINUOUS_PURSUIT | 2.371–8.247 | 4.992 | 41.39–41.67 |

正式正確率／模型推論fps／畫面fps均為null。
REPORT content hash `8cebf3167f0ff92a8b2ec3d7d76bba46cfc9076f1e90bcda75c76283b33ced9c`。
MISSING fixture 的 RGB hash 已清空並重綁索引；該產製錯誤已修正，沒有放寬kit。
測試與原kit完整報告在資料夾evidence；既有上游FAIL依各自來源歸檔，不宣稱整包符合性通過。
