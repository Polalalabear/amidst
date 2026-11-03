# 複雜事件多鏡頭播放（唯讀）

CX-7 的 A4-1（4 鏡頭）與 B4-1（5 鏡頭）safe RGB 同步播放頁。ENGINEERING：只有影像，無推論、無身分，不含事件、路線或時間窗資訊。獨立於 `frontend/workbench-v2/`，不修改 FEAT-9。

## Demo 當日啟動（一行）

```bash
node frontend/event-viewer/server.mjs --root "$HOME/amidst-artifacts/r004-cx7-d115-20261102-01a199f8" --port 8765
```

再開 <http://127.0.0.1:8765/>。`--root` 是 LOCAL 的 CX-7 輸出根目錄；server 只讀 `<run>/safe/media/<camera>/<index>.png`，其餘路徑（含 `gt_private/`）、`..`、symlink 一律 404，且只綁 127.0.0.1。

## 啟動驗證（fail-closed）

safe 區沒有 manifest／clock，預期結構取自 `runs.mjs`（來自 `docs/engineering/R004_EVENT_RUNS_RECEIPT.md`，#394）。

- **路徑**：在任何 `readdir`／`readFile` 之前，先逐段 `lstat` root 以下的 `<run>/safe/media/<camera>`，任一段是 symlink 或非目錄即 UNAVAILABLE；`realpath` 必須等於以 root 串出的路徑。`--root` 本身是 symlink 亦然。
- **全量驗證（啟動時一次，結果快取）**：camera 集合與連續檔名正確；**每一張**影格都檢查 PNG：簽章；IHDR 在最前、唯一、長度 13，且為 960×540、8-bit RGB、非交錯；其後只允許各至多一次、長度與值依規格驗證的 sRGB(1)／gAMA(4)／cHRM(32)／pHYs(9)／oFFs(9)（數值欄位另設上限，塞不進文字）；IDAT 連續，且必須恰好解壓成 540×(1+960×3) bytes（zlib 串流後無多餘資料、過濾位元組 0–4）；IEND 長度必須為 0 且之後不得有任何 bytes；每個區塊 CRC 正確。PLTE／tRNS／sBIT／bKGD、tEXt／iTXt／zTXt／eXIf／iCCP／sPLT／tIME 與未知區塊皆拒絕。同時記下每張的 SHA-256。
- **送出時**：每次重新讀檔，SHA-256 須等於啟動時記下的值且仍通過 PNG 檢查，才送出「同一份 bytes」；否則 404。
- **錯誤**：`/api/runs` 只列 `runs.mjs` 宣告的 run，失敗只回固定碼 `UNAVAILABLE`（結構／symlink／無法讀取）或 `INTEGRITY_FAIL`（內容不符），不含任何檔案系統路徑或目錄名稱；頁面只顯示該碼。
- safe 區沒有逐檔 SHA 清單（在 `gt_private/`，依規定不讀），故 SHA 以啟動時自行計算的值作為「驗證後不得改變」的基準，不是對外部清單的比對。

## 測試

```bash
node --test frontend/event-viewer/viewer.test.mjs
```
