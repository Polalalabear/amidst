# LIVE session 顏色與接回定位（#676，D357）

狀態：Codex 已完成定位與修正，待 Claude 審查。分支 `codex/feat-live-fixes`；E5 #684 結束前不合併、不部署到 8791。原「失聯23.5秒」事件未取得其錄製檔，原因保持 UNKNOWN，以下是合成觀測的可重跑工程定位。

## 定位與修正

- `Tracker` 已使用 target_color。固定 gate 4 m／growth 0 的預設下，最後估計 [0,0]、23.5 s 後同色觀測 [5,0] 仍被拒（距離5 m）；異色距1 m也拒，同色距1 m可接回。人工 reselect/pick 可把5 m目標作為新種子，再持續追蹤。紅色和藍色相同。沒有把這個fixture冒稱原事件。
- scheduler 的近期候選記憶只收 red。現在只記 session 選定顏色，切色即清空記憶。記憶仍只是補充掃鏡提示；失聯兩輪後本來就全掃，因此它不能單獨解釋原23.5秒長失聯。
- 舊 review／lead `LiveDecider` 只收 red，server 因而跳過藍色。現在 factory 傳入 session 顏色，候選按該色選取，並宣告支援選定顏色，使既有 server 能呼叫藍色 advisor。預設仍 red；agent_service 模式原已支援全色，不改其行為。
- `tracker.py`、people、E3 執行／評分、scene_context 與評分器不改。R1 的 runtime 閾值仍 UNKNOWN／預設 disabled，離線 GT-derived appearance 參數不進 runtime。>4 m 自動接回需要 #589/R2 後續核定，本交付不擅自放寬 gate 或宣稱原事件已修。

## 聚焦驗證與重製

從 scratch clone 執行；`PYTHON` 指向既有唯讀 demo Python，不複製環境或資產。

```sh
UV_CACHE_DIR=local/uv-cache PYTHONPATH=src uv run --offline --no-project --python "$PYTHON" python -B -m pytest -o addopts='' -q tests/live_mode/test_session_target_color.py tests/live_mode/test_scheduler.py tests/live_mode/test_advisor.py tests/live_mode/test_track_endpoints.py tests/live_mode/test_tracker_color.py
UV_CACHE_DIR=local/uv-cache PYTHONPATH=src uv run --offline --no-project --python "$PYTHON" python -B scripts/verification/live_color_gate_diagnose.py --out local/evidence/cx-live-fixes-20261123/after.json
node scripts/verification/live_blue_recording.mjs > local/evidence/cx-live-fixes-20261123/recording-fixture-after.json
git diff --check
```

72 passed；diff-check PASS。測試涵蓋雙色近距離失聯返回、遠距／異色拒絕、記憶切色清空、舊advisor候選與factory、既有紅色回歸。合成觀測 before／after 的完整紅色 cases 相同；藍色近期候選鏡頭由遺漏變成保留，Tracker gate 的接受／拒絕不變。

Node 收據使用 #617 的真實 `createInputRecording`／`createPlayback` 模組各重播2次，並驗證 start→reselect→candidates→pick 的 public requests 不帶 actor/scenario/GT 欄位。這是合成fixture，模擬端依既有情境建立錄製；不是原錄製，也不是影像／偵測推論驗證。修前後 Node 收據位元組相同。

## LOCAL 證據

全部新產物在本分支 scratch clone 的 `local/evidence/cx-live-fixes-20261123/`；不轉存 pinned checkout。4份列入收據的 JSON（before、after、recording-fixture、recording-fixture-after）合計392,578 bytes。MANIFEST SHA-256 `09a385fc35485472089fc13720a7426c2798db473b68488fbe32b07646ea56cb`，逐檔 SHA/bytes 在 MANIFEST。before 由分支 base `aeb9b915` 的原程式生成；其餘按上列命令再生。原檔／設定與媒體均未更動。

未驗證原事件根因、實體場域、身分、模型效果或遠距自動接回；無付費API、Blender render、影片或原始資料修改。這是有邊界的定位與顏色傳遞修正提案，等待 Claude 審查。
