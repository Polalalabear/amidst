# Office Demo 一鍵啟動

## 彩排用：合成副本或另一個 clone（2026-10-17）

現行 launcher 以自己的 checkout 作為 UI／程式來源；資產根目錄預設由 `git rev-parse --git-common-dir` 的父目錄取得。另一個 clone 或彩排合成 checkout 的 Git common dir 會指向自己，未必有原資產，因此必須把 `OFFICE_ASSETS_REPO` 設為**既有資產 checkout 的絕對路徑**。這只是指定讀取位置，不搬移或複製來源。副本仍須有可用 Git 資訊及啟動器要求的 application baseline；只設定資產路徑不能讓沒有 Git provenance 的目錄通過 preflight。

先把下列路徑換成既有位置，再於彩排 checkout 執行：

```sh
cd "/absolute/path/to/rehearsal-checkout"
export OFFICE_ASSETS_REPO="/absolute/path/to/existing-assets-checkout"
export OFFICE_EVIDENCE_REPO="$OFFICE_ASSETS_REPO/.local-worktrees/phase1-finalization"
export OFFICE_PYTHON="$OFFICE_EVIDENCE_REPO/.venv/bin/python"
./start-office-demo.command start --no-open
```

- `OFFICE_ASSETS_REPO` 供 assets-root presets（含 `blender-office-person`）尋找 bundle；不能只設 `OFFICE_BUNDLE`，後者只覆寫舊 `blender-office` bundle。
- `OFFICE_EVIDENCE_REPO` 預設為上述 assets root 下的 `.local-worktrees/phase1-finalization`，提供舊 Office bundle、既有媒體與 Three.js。若現有位置不同，直接設成該既有 evidence checkout 的絕對路徑。manifest 內的 source／dataset／RGB locators 仍須有效且符合原 hash，不改寫 locator、不建立替代資產。
- `OFFICE_PYTHON` 指向**既有、可執行**的 Python interpreter；預設是 evidence checkout 的 `.venv/bin/python`。例如 `export OFFICE_PYTHON="/absolute/path/to/existing-env/bin/python"`。啟動器透過 `uv run --offline --no-project --python "$OFFICE_PYTHON"` 使用它；不建立環境、不安裝缺失依賴。只有 Python 路徑正確，不能補足缺少的 bundle／Three.js。
- preflight 遇到任何 **tracked 修改**（含已 stage 的修改）就拒絕啟動；先檢閱、在自己的分支提交預期變更，再啟動。未追蹤檔案會保留並警告，不代表它們已納入來源驗證。不要藉由丟棄修改或繞過檢查讓彩排啟動。

同一個 Terminal 保留這組 exports，之後使用：

```sh
./start-office-demo.command status
./start-office-demo.command stop
./start-office-demo.command restart --no-open
```

使用 launcher 當次印出的動態 URL；不要照抄其他 checkout 的 PID／port。`WORKBENCH_READY` 與 `PERSON_DEMO_READINESS` 分開判讀，HTTP readiness 不等於瀏覽器或完整 Demo 驗收。

下方固定 `amidst-claude` 路徑、branch／commit 與早期 evidence 預設均為歷史紀錄，不是現行彩排的固定配置。本段依 `start-office-demo.command`、`scripts/start_office_demo.py` 與 preset 路徑解析核對；本次只改文件，未新建副本／clone、環境或啟停服務。

## 歷史初版與驗證紀錄

在 Finder 雙擊根目錄 `start-office-demo.command`，或在任意 Terminal 工作目錄執行：

```sh
/Users/polalabear/Developer/amidst-claude/start-office-demo.command
/Users/polalabear/Developer/amidst-claude/start-office-demo.command --no-open
/Users/polalabear/Developer/amidst-claude/start-office-demo.command --status
/Users/polalabear/Developer/amidst-claude/start-office-demo.command --stop
```

預設／唯一支援模式為 `--mode lite`。啟動器印出實際 `OFFICE_DEMO_URL`、frontend commit、來源 checkout、PID、可用磁碟空間與 PostgreSQL/Ollama 程序狀態。離線使用既有 uv 與 Python 環境，不安裝依賴。`--no-open` 不開瀏覽器。服務在 Terminal 關閉後繼續運行；`--stop` 僅向 runtime record 中、啟動時間與命令列均核對成功的 launcher-owned Workbench 送出 SIGTERM。不停止其他服務，不使用 killall。

## 來源與依賴

- 固定 frontend checkout：`/Users/polalabear/Developer/amidst-claude`。
- 固定 branch：`claude/office-demo-visualization`。HEAD 必須包含 Task 1 commit `3181cff84ac2c712f66da0e24a3387dee672df03`；有 tracked 修改時拒絕啟動。新 launcher 文件未提交不影響此檢查。`FRONTEND_COMMIT` 記錄最後修改 `frontend/workbench` 的提交，因此單獨提交 launcher 不會被誤判為前端變更；本次前端為 `d2e38778f963578df4f7efeb07e7ed12d4fe1966`。
- 使用既有 `scripts/office_demo_backend.py` 的 `load_scene` 與 `application` factories。既有 `serve` 命令所支援的 bundle/UI/evidence 分離路徑可直接重用原始 Office 素材，無需一般 Workbench catalog 的跨 checkout 設定。
- 預設 evidence/environment checkout：`/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization`。
- Office bundle：該處 `data/engineering/local_run/blender_camera_v1/office`；manifest 的原始來源、dataset 與 RGB 絕對路徑保持原樣。
- Three.js：唯讀使用該處 `frontend/workbench/node_modules/three` 的三條既有 vendor routes。其他前端及 API 皆由 Claude checkout 提供，沒有 proxy 到舊 Workbench。
- 可顯式指定既有依賴位置：`OFFICE_EVIDENCE_REPO`、`OFFICE_BUNDLE`、`OFFICE_PYTHON`。不尋找替代資料、不下載、不複製、不使用 symlink；已缺失時明確停止。

Lite 提供 Office 的 deterministic API、既有 source frames，以及存在時的既有 motion/association/physical artifacts。它使用獨立暫存 review state，不開啟原有 SQLite，也不連線 PostgreSQL 或 Ollama。Backend/Agent 模式明確回錯，不會暗中啟動資料庫或模型。現有全功能 `start_local_demo.py` 位於工程 checkout，會要求 PG 與 Ollama 且服務舊 UI，因此不直接用作 Lite 啟動器。Office Agent 尚未接入；不自動載入 7B 或重建 3B。

## 驗證與生命週期

系統分配 `127.0.0.1` 動態埠；以 PID 的實際 listener 與 HTTP 再核對。以每使用者／checkout 的 file lock 防止同時重複啟動。重開會比對 PID 啟動身分、最後修改 frontend/workbench 的 commit、來源 fingerprint、HTTP frontend hash、`cameraViewerHTML`／`sourcePlaybackStep`、bootstrap、雙鏡頭 timeline，以及 0.0/0.2/0.4 秒六張 PNG。舊原始庫服務即使健康也不會被接受為此 launcher 的新版 Workbench。來源改變時拒絕重用，使用 `--stop` 後再啟動。

Runtime record、小型 startup log 與獨立 state 位於 `/private/tmp/amidst-office-demo-<uid>-<checkout hash>/`，權限 700。啟動日誌每次新啟動截斷，不記錄 HTTP session token，也不記錄逐幀請求。既有 QuietHandler 不產生持續 request log。正常停止清除此次 temporary state；SIGKILL 或系統異常可能留小型暫存檔。最低剩餘空間 256 MiB。

## 人工視覺驗收

開啟啟動器印出的 URL，選「研究」→ Office → 工作區（若頁面尚未自動選取）。確認主來源相機 viewer 與同步鏡頭影格直接可見且不需展開 details；切換相機時核對相機標籤與來源畫面。拖曳時間軸，再按播放，確認每 0.2 秒的來源影格、時間標籤與 timeline 一致；在 4.4–8.6 秒缺觀測區間保留 MISSING/UNKNOWN。這是既有來源截圖的 flipbook，非即時攝影機或新生成影片。

HTTP readiness 不代表人工視覺驗收通過；身份、完整物理安全與正式研究驗收仍維持原有範圍。此啟動器不實作 Task 2。

## 2026-10-15 啟動驗證

Frontend commit `d2e38778f963578df4f7efeb07e7ed12d4fe1966`、預期分支與乾淨 tracked tree 已核對。開始時僅有本 launcher 的三個預期 untracked 檔案。Shell／Python syntax PASS；Lite 首次啟動及第二次啟動皆通過來源 hash、`cameraViewerHTML`／`sourcePlaybackStep`、三個 vendor assets、Office bootstrap、雙鏡頭 0.0/0.2/0.4 秒 timeline 與六張 PNG 的 HTTP 檢查；第二次重用相同 PID／URL。

瀏覽器已實際載入 3D 與主相機 PNG；完整播放、相機切換與同步的人工驗收仍 PENDING。未執行全套研究測試、模型推論、依賴安裝或 shutdown 測試。現有 57597 Workbench 保留；Lite 不啟動 PostgreSQL 或 Ollama，Ollama 的唯讀 `/api/ps` 於啟動前後皆無已載入模型。動態 URL／PID 只保留於本機 runtime record 與當次回報。

## 2026-10-16 PR #7 launcher 修復

以 PR #7 `78b99e623f72f0e9f8df24ec54ce57815c1a9cf5` 為最低 application baseline，取代上述歷史分支白名單。現在 root 由 launcher 所在位置取得；evidence 預設相對於 root 的 `../amidst/.local-worktrees/phase1-finalization`，仍可透過 `OFFICE_EVIDENCE_REPO` 指定既有位置。Python 預設取該 evidence 的 `.venv/bin/python`，沿用 `uv --offline --no-project`，不建立環境或安裝依賴。相對 evidence 路徑由 shell 驗證存在並正規化；原始素材 locator 保留在既有 manifest，未搬移。

在 repository root 使用：

```sh
./start-office-demo.command start --no-open
./start-office-demo.command status
./start-office-demo.command stop
./start-office-demo.command restart --no-open
```

預設 `OFFICE_PORT=0`，交給系統配置 loopback 埠。可明確指定 `OFFICE_PORT`；佔用時初始化失敗，不終止佔用者。網址只在 PID/start identity/cwd/listener、HTTP metadata、四個 frontend resources 的 SHA-256、vendor、Office catalog、timeline 及 PNG 驗證後印出。`status` 也完整核對來源；改動 tracked 程式時必須先檢閱並提交，再 `restart`。`--status`、`--stop` 維持相容。

程序盤點列出 executable、PID、start identity、cwd、listener。可核對目前 runtime record 者為 `CURRENT_ACTIVE`；未能證明 managed ownership/session release 的既有服務為 `OWNERSHIP_UNKNOWN`，一律保留。流量低或沒有請求不能證明閒置，目前沒有可獨立證明的 `OLD_IDLE_VERIFIED`，所以不自動清除舊服務。若取得明確其他 session 使用證據，須視為 `IN_USE_BY_OTHER_SESSION` 並保留，不能僅由程序 cwd 推定 session 身分。

`stop` / `restart` 是使用者對本 launcher managed service 的明確操作，只在 PID/start identity/cwd 符合 runtime record 時送 SIGTERM，最多等 5 秒，不升級 SIGKILL。Restart 在 preflight 失敗時保留原服務；初始化失敗時終止本次 child、保留錯誤日誌，未驗證通過不印 READY。服務有獨立 session、runtime record、日誌及 stop 指令；關閉 Terminal 後仍可透過 status/stop 管理。

啟動資訊另含 branch/HEAD、tracked/untracked 狀態、Python/environment、剩餘容量、HTTP stage、PID/port 與操作指令。低於 12 GiB 提醒；低於 256 MiB 拒絕啟動。不把 HTTP readiness 當完整 8 分鐘 Demo、空間精度或正式研究驗收。

聚焦測試：`tests/workbench/test_office_launcher.py` 涵蓋 PID reuse、cwd 不符、SIGTERM bounded timeout、較新 runtime record 保護、來源不符拒用、唯一 loopback listener、restart preflight 失敗保留舊服務、child initialization 失敗不回報 READY。實際啟動與瀏覽器驗收結果另記工作收據。

## 八分鐘 Office 工程展示腳本（精度驗收仍未通過）

先以 `start` 印出的本次實際網址進入「研究」；若 `status` 失敗，先看日誌，不改用舊服務網址。以下是可重複的操作順序，不能把八分鐘講解時間當成八分鐘影片或正式精度驗收。

| 時間 | 操作與可說明的證據 |
| --- | --- |
| 0:00–1:00 | Terminal 核對 branch/HEAD、PID/port、HTTP/FRONTEND_MATCH；研究→Office。 |
| 1:00–2:00 | 2D 雙鏡頭，查看 0.4/0.6 s；橙色是替代目標，座椅遮住下部。 |
| 2:00–3:00 | 切 3D，看來源局部模型、16 椅及講台；display-only，物理權威 UNKNOWN。 |
| 3:00–4:00 | 「跨鏡頭多解還原」，比較 0.4/0.6 與 1.8/2.0 s 的分段起點、caption、原 bbox。不要把大跳說成人員瞬移。 |
| 4:00–5:00 | 4.4 s 保留兩個原始觀測；5.0 s 無當前 cursor；8.6 s 是 REAR 新觀測。 |
| 5:00–6:00 | 候選 1→2→3→未關聯基線；分數非機率，身分未確認，缺失不補值。 |
| 6:00–7:00 | 完整回放 0.0–9.8 s，切 2D/3D；現有 source flipbook，尚無還原影片。 |
| 7:00–8:00 | 展示 [空間診斷收據](../engineering/OFFICE_CONTACT_SPATIAL_QA.md)，說明 raw/proxy/UNKNOWN；以 `status` 結束。 |

完整 demo 的位置精度與完整影片仍未驗收，因此 `FULL_8_MIN_DEMO=NOT_READY`；這份腳本不宣稱它們已完成。本次不填寫任何人工支持或矛盾判定，也不假造已確認身份／物理通行結果。
