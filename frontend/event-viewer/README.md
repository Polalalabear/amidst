# 複雜事件多鏡頭播放（唯讀）

CX-7 的 A4-1（4 鏡頭）與 B4-1（5 鏡頭）safe RGB 同步播放頁。ENGINEERING：只有影像，無推論、無身分，不含事件、路線或時間窗資訊。獨立於 `frontend/workbench-v2/`，不修改 FEAT-9。

## Demo 當日啟動（一行）

```bash
node frontend/event-viewer/server.mjs --root "$HOME/amidst-artifacts/r004-cx7-d115-20261102-01a199f8" --port 8765
```

再開 <http://127.0.0.1:8765/>。`--root` 是 LOCAL 的 CX-7 輸出根目錄；server 只讀 `<run>/safe/media/<camera>/<index>.png`，其餘路徑（含 `gt_private/`）、`..`、symlink 一律 404，且只綁 127.0.0.1。

## 啟動驗證（fail-closed）

safe 區沒有 manifest／clock，預期結構取自 `runs.mjs`（來自 `docs/engineering/R004_EVENT_RUNS_RECEIPT.md`，#394）。啟動時逐 run 檢查：camera 目錄集合、每台恰為連續編號的 `000000.png`…、全為一般檔；每台抽驗首／中／末三張的 PNG 簽章、960×540、無 tEXt／iTXt／zTXt／eXIf。任一不符則該 run 在頁面顯示 UNAVAILABLE 且不提供影像。逐檔 SHA-256 在 `gt_private/` 內，本頁不讀取，故不做 SHA 驗證。

## 測試

```bash
node --test frontend/event-viewer/viewer.test.mjs
```
