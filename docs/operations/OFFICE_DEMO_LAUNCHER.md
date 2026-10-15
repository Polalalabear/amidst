# Office Demo 一鍵啟動

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
