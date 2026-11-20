# Workbench-v2 的 A4-1／B4-1-8CAM（#594）

D302 選用 #529 safe bundle 的 A4-1-8CAM，50 秒、5 fps、八台鏡頭各 250 格。
D326 再接入同包 B4-1-8CAM，42 秒、5 fps、八台鏡頭各 210 格。
兩個 run 與 B-05、A4-1、B4-1、r005 共用既有 bootstrap、監控牆與來源選單。
名稱表分別標示「A4-1-8CAM · 4 人／8 鏡頭」及「B4-1-8CAM · 4 人／8 鏡頭」。
核准 safe bundle 的 runs 目錄只有 A4-1.json、B4-1.json；B-05-8CAM、r005-8CAM
在 bootstrap.eightcam_runs 明列 UNKNOWN，reason 為 NO_PINNED_EIGHTCAM_SOURCE_IN_APPROVED_BUNDLE。
沒有以其他 run 替代，也沒有重新渲染。

`start_445_demo.command` 在 checkout 的標準 safe bundle 目錄存在時，透過 `--auto-root-8cam` 載入。
自動找到的 bundle 如果缺檔、路徑不合法、pin 不符、或未通過索引和場景綁定，
bootstrap 的 `eightcam.status` 為 `UNKNOWN` 並附原因，四個既有 run 仍可載入。
明確的 `--root-8cam` 優先採用指定目錄。指定來源驗證若遇內容 pin 或綁定錯誤會報錯，
且 dependency smoke 要求指定來源成功註冊兩個新增 run，總計六個。
資料來源為 `local/data/r004-4actor-natural-walk-eightcam-20261114/bundle/safe`，SHA-256 `0900d151e4e3360741f51d47f3d1a532db31e69818d1c8b1a325495a48bd413d`（原 SAFE_MANIFEST.json）。
兩個 run 的 3,680 個 PNG 與 12 個 metadata／index 檔以 #529 已提交的
`docs/operations/R004_V2_4ACTOR_BUNDLE_MANIFEST.json` 為來源。程式在載入時綁定每格的 PNG、
時鐘和 detector index。每個被請求的 PNG 會再驗 byte SHA，既有媒體供應路徑會清除 PNG 文字 metadata。
I/O guard 只增列這 3,692 個檔案的讀取權限。兩個 descriptor 和索引都通過後才一起註冊；
任一失敗時，自動載入仍保有四個原始 run，顯式載入保持嚴格拒絕。
以既有 v3.1 graph 呈現七個已知 graph 節點。
CAM_ENTRY 有校正與影像，跨鏡頭轉移仍為 UNKNOWN。另案才可核定跨鏡頭追蹤 scope。

以下為 D302 歷史 checkpoint，保留當時的單一 A4-1-8CAM 結果。

- Python 20 pass（8CAM、D147 既有資料、launcher），Node 17 pass（來源命名與 monitor room）。
- Dependency smoke 帶 `--root-8cam` 時 PASS，5 個 run、12 個首格，包含新 run 的全部 8 台。
  省略參數時 PASS，4 個既有 run、4 個首格，8CAM 明示 `ROOT_NOT_CONFIGURED`。
- 以獨立 loopback 埠及真實資料驗證 1440×900 與 1440×1300 的工作台。每個 viewport 5 assertions，
  包含選單切到正確 run、8 張解碼影格與拖曳到 1.0 秒後的八張解碼影格。0 頁面錯誤、0 失敗 API。
- `bash -n start_445_demo.command` 與 `git diff --check` 通過。

LOCAL `local/evidence/cx594-20261118/MANIFEST.json`，SHA-256 `3736c0e385c113521d8d25e24974aae00a4d023ba65d7617868fbb2b1ae90fd9`，8 檔／1,015,324 bytes。
包含兩份 dependency 驗證、focused 測試、兩種高度截圖及瀏覽器收據。使用同一份資料、下列驗證命令
可重現，截圖的頁面時鐘與 token 會變動。

#576 的完整 D269 gate 使用合併後的 candidate checkout、獨立 port 與新的證據目錄。以下命令中
`EIGHTCAM_ROOT` 指向既有 safe bundle，`OUT` 指向新 LOCAL 證據，`PYTHONPATH=src` 並使用
checkout 自有且以 owned runtime 建立的 `.venv`。Gate 由 Claude 執行，pin 由使用者核准。

```bash
.venv/bin/python -B scripts/check_demo_dependencies.py --smoke --root-8cam "$EIGHTCAM_ROOT" --output "$OUT/dependencies.json"
AMIDST_ROOT_8CAM="$EIGHTCAM_ROOT" .venv/bin/python -B -m pytest tests/q1q5/test_demo_eightcam.py tests/q1q5/test_d147_acceptance.py tests/q1q5/test_demo_launcher.py -q
node --test frontend/workbench-v2/event-names.test.mjs frontend/workbench-v2/monitor-room-model.test.mjs
# 以驗證 checkout 啟動獨立 QA 埠
AMIDST_DEMO_ALLOW_UNPINNED=1 ./start_445_demo.command --port 8799 --root-8cam "$EIGHTCAM_ROOT"
# 由另一個終端執行。1300 高度改 UI_QA_HEIGHT 和輸出目錄。
UI_QA_BASE_URL=http://127.0.0.1:8799 UI_QA_REQUIRE_8CAM=1 UI_QA_HEIGHT=900 UI_QA_OUTPUT="$OUT/real-900" node tests/browser/ui-redesign/real-e2e.mjs
```

正式 real-e2e 會跑原 D269 內容與新增的 8CAM 監控牆測試。
`UI_QA_REQUIRE_8CAM=1` 使缺失的 8CAM 在 #576 中直接指出原因並失敗。

## D326：B4-1-8CAM 與預錄估計的聯合驗證

以下結果在獨立 checkout 執行，沒有改動 8785 pin。以既有 owned demo 設定
AMIDST_DEMO_HOME，EIGHTCAM_ROOT 為上述 safe bundle，OUT 為新的 LOCAL evidence 目錄。
本次直接使用既有 uv 環境的 .venv/bin/python，沒有安裝新 Python 依賴。

```bash
AMIDST_ROOT_8CAM="$EIGHTCAM_ROOT" AMIDST_TEST_EVIDENCE="$OUT" .venv/bin/python -B -m pytest tests/q1q5/test_demo_eightcam.py tests/q1q5/test_demo_estimate.py tests/q1q5/test_d147_acceptance.py tests/q1q5/test_demo_launcher.py tests/q1q5/test_api.py -o addopts= -q -p no:cacheprovider
node --test frontend/workbench-v2/event-names.test.mjs frontend/workbench-v2/monitor-room-model.test.mjs frontend/workbench-v2/scene3d-model.test.mjs frontend/workbench-v2/core-screens.test.mjs
.venv/bin/python -B scripts/check_demo_dependencies.py --smoke --root-8cam "$EIGHTCAM_ROOT"
AMIDST_ROOT_8CAM="$EIGHTCAM_ROOT" AMIDST_TEST_EVIDENCE="$OUT" PYTHONPATH=src:scripts node tests/browser/ui-redesign/eightcam-smoke.mjs
.venv/bin/python -B scripts/check_architecture_guard.py --repo . --base origin/main
git diff --check
```

- Python 76 pass、0 skip；Node 53 pass。正常 Demo 入口的四個既有 run 估計測試另確認 4 pass。
- Dependency smoke PASS：六個 run、20 張首格，兩個新增 run 各檢查八台鏡頭。
- Focused browser smoke PASS：1440×900、1440×1300 各檢查 A4-1、B4-1；
  共 20 個獨立斷言，四張截圖，全部八格解碼並可 seek 到 1.0 秒。
  0 page errors、0 failed APIs。伺服器 log 有頁面關閉時已取消請求的 BrokenPipeError，
  runner 與 owned fixture 均正常結束，exit 0。
- 新 runner 使用同一個預設無頭 browser，finally 關閉並以 stdin EOF 結束 fixture。
  只有明確 --headful 或 AMIDST_HEADFUL=1 才開視窗；需要目視時才使用並在交件註明。
- Architecture guard、LOCAL refs strict 與 git diff --check 通過。

LOCAL `local/evidence/cx594-d326-20261118/MANIFEST.json`，SHA-256 `95b30841b20777f92cf1d55b057c2e6846a3cd823673e5e777aa9b4c96c01db0`，14 檔／2,308,983 bytes。包含 focused 測試、六 run smoke、投影重播、來源範圍、四張截圖和 browser 收據，可用上述命令重建；頁面時鐘與 token 可變動。
完整 #576／8785 gate 與 pin 核准不在本次 focused 驗證內。B-05-8CAM、r005-8CAM
的來源仍為 UNKNOWN，需有核准且帶 pin 的資料才能再接入。

## #603 審查 P2 回歸

使用上述 focused Python 與 Node 指令重跑，分別為 22 和 17 個測試通過。
測試用臨時目錄中的 descriptor 觸發 `BYTE_PIN_MISMATCH`。自動載入以 UNKNOWN
回報並保有原 4 個 run，顯式載入會拒絕同一輸入。
LOCAL `local/evidence/cx594-d308-p2-20261118/MANIFEST.json`，SHA-256 `034dc5d3a3ebe5c0997edb849df27ed1bef49013e1416eddcaf1ef5c2dbe625a`，3 檔／1,693 bytes。

## D315 複審 P3

只有 bootstrap 驗證期間或 8CAM 狀態為 READY 時，I/O guard 才接受 receipt
列出的檔案。自動來源降級到 UNKNOWN 後，該批讀取權立即停用，原有 run 的讀取仍可用。
顯式 smoke 保留原嚴格驗證。#604 已含 #603 的 8CAM bootstrap 並合併；
本修正和最新 main `b98fac2a` 的 Git 合併預覽無衝突。
預覽的 8CAM／launcher／D147 共 22 個 Python 測試全部通過。
LOCAL `local/evidence/cx610-d315-final-20261118/MANIFEST.json` SHA-256 `ac1d2b2dda7b3fb4c55258dfa141c5db7b74db55da971758c2ecd032a4a28aff`，16 檔／838,750 bytes。可用本文件的 focused 測試指令重跑。
