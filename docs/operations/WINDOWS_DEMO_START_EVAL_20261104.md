# Windows 一鍵啟動 demo 實測報告（Issue #429 / W-A11）

日期：2026-11-05（Asia/Taipei，更新實測收據）
執行者：Argon
分支：`argon/429-windows-demo-start-eval`（base: `origin/mainline/q1q5`）
依據：#411 `start_all_demo.ps1`、#416 資料前置交件通知、Codex Review on PR #455、`docs/operations/DEMO_RUNBOOK_20261104.md`

## 2026-11-06 Codex 有界修正與狀態更正

本文件以下 2026-11-05 內容保留 Argon 當時的歷史收據；其中「端到端」僅有三個 HTTP 200 probe，不能代表 P1 `q_bootstrap`、recorded response、`q_frames`／media grant、live rule-only、跨服務組合畫面或關閉後 PID／port 均已驗證。原先 `is_symlink()` 後用 `os.open()` 的 Windows fallback 亦不能阻止檢查與開啟之間的 junction／symlink 替換。

本次在 #455 後續修正加入 source／served 雙 pin reader（對應 #449 `69a102bb042297b8fcf813bd73e7f25b4d25b5ef` 的純 adapter）、公開 PNG `eXIf` 剝除、Windows handle 檢查與原有 `q_physical_prediction` error-only 503。Windows reader 以 `CreateFileW` 開啟並持有每層目錄 handle，只允許 `FILE_SHARE_READ`，檢查 reparse／一般檔／handle final path 後才讀 bytes；無法驗證時拒絕。這些變更只經 macOS synthetic／mock focused tests；**Windows/NTFS 實機、PowerShell、原 stripped pack runtime media、完整瀏覽器驗收均 NOT_RUN**，不將本次修正視為 #429 完整 gate。啟動腳本在下一次 Windows 執行時會輸出精確 probe URL、child PID 與清理後 PID／port 狀態；本文尚無該次實測收據。

---

## 1. 摘要與測試目標

本任務實測並完善 `start_all_demo.ps1` 在原生 Windows PowerShell 5.1 / 7+ 環境下的端到端啟動流程，主要覆蓋：
1. **Safe 資料驗證**：在 Windows 本機以 Python 3.12 stdlib 獨立驗證 #416 提供之三包安全資料（`p1-v4-stripped`、`cx7-d119`、`cx7-d124`）。
2. **前置資源檢查與路徑自動偵測**：修復 `start_all_demo.ps1` 在 Windows 下對 safe data 目錄、manifest pin 與相依環境之自動偵測與路徑解析。
3. **相容性與門禁測試**：實作專屬單元測試套件 `tests/q1q5/test_windows_demo_start.py`，全數 8 項測試通過。
4. **端到端三進程啟動實測**：完成 Segment A（8766，review）、Segment B（8765，live tracking）、Segment C（8780，events）全部三進程成功啟動與 HTTP 200 就緒驗收。

---

## 2. 安全資料包本機驗證結果

使用 `verify_safe_pack.py`（Python 3.12 stdlib，不使用外部套件／網路／模型／Blender）在 Windows NTFS 檔案系統上對三包資料進行逐檔 SHA-256 及結構驗證，結果全數通過：

| 資料包 ID | 檔案總數 | Payload 位元組 | 傳輸 Manifest SHA-256 | 驗證狀態 |
| :--- | :--- | :--- | :--- | :--- |
| `p1-v4-stripped` | 402 | 149,689,383 | `c7f32857948468e54cdafa8d8eaaefce730c6660378191b2b2ecfe3f80dcf7fd` | **VERIFIED** |
| `cx7-d119` | 4,107 | 2,209,639,931 | `5d7bde92462cd3b72604b612f676565c487edfa469af5c6a46f03a6cbe8fd115` | **VERIFIED** |
| `cx7-d124` | 2,057 | 1,105,936,480 | `6a0d90d00580a1c6bace411316fc909e09a209a0ac282841328ef4e209ba762f` | **VERIFIED** |

- `p1-v4-stripped` 內 runtime `MANIFEST.json` SHA-256 為 `13ab3c559fd63dd6f5d44ac7f6dabe1192274b368bfd1307f3a3bbd6682e5805`。
- `cx7-d119` 完整保留 A4-1 與 B4-1 兩個 safe run 之 `safe/media/<camera>` 目錄結構，與前端 `event-viewer` runs 目錄完全吻合。

---

## 3. `start_all_demo.ps1` 與平臺相容性修正內容

針對 Windows 環境與 #416 safe packs 交付結構，完成以下跨平臺相容性修復：

1. **Safe Data 本機路徑自動偵測**：
   - `$P1Bundle` 優先偵測 `$env:P1_BUNDLE`，若無則自動尋找工作目錄下的 `.\p1-v4-stripped` 或 `$env:AMIDST_SAFE_PACKS\p1-v4-stripped`，免除手動指定長路徑。
   - `$CX7Root` 優先偵測 `$env:CX7_ROOT`，若無則自動尋找工作目錄下的 `.\cx7-d119` 或 `$env:AMIDST_SAFE_PACKS\cx7-d119`。
2. **P1 Runtime Manifest Pin 雙向相容**：
   - 支援原版 v4 Pin（`6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`）以及新版 stripped runtime Pin（`13ab3c559fd63dd6f5d44ac7f6dabe1192274b368bfd1307f3a3bbd6682e5805`）。
   - 新增 `-ManifestSha` 參數與 `$env:MANIFEST_SHA`，供使用者或測試指定特定 pin；非核定 pin 自動 fail-closed。
3. **磁碟剩餘空間檢查安全性（`Get-FreeDiskGiB`）**：
   - 使用 `[System.IO.Path]::GetPathRoot` 與 `[System.IO.DriveInfo]` 直接取得目標磁碟空間，避免在沙箱／受限目錄下遞迴探測目錄層級造成權限拒絕。
4. **PowerShell `Start-Process` 參數傳遞優化**：
   - 移除 `ArgumentList` 中多餘的反引號轉義雙引號，避免 Node.js 與 Python 子行程解析到非預期的引號字元。
5. **後端 POSIX Open Flag 與 Symlink 防禦跨平臺調適**：
   - `src/amidst/q1q5/store.py`：針對 Windows（無 `dir_fd`、`O_NOFOLLOW`、`O_DIRECTORY`）實作安全組件遍歷，強制檢查各級路徑與葉節點之 `is_symlink()`，fail-closed 拒絕 symlink。
   - `src/amidst/q1q5/api.py`、`production_preflight.py`、`p1_workbench.py`、`ollama_runtime.py`、`linked_runtime.py`、`team_eval_pack.py`、`baseline_runner.py`：使用 `getattr(os, "O_NOFOLLOW", 0)`、`getattr(os, "O_NONBLOCK", 0)` 與 `getattr(os, "O_BINARY", 0)`，搭配 `path.is_symlink()` 確保 Windows 上二進位讀寫與符號連結防禦一致。
6. **Windows 下 Python `zoneinfo` / `tzdata` 調適**：
   - `scripts/start_q1q5_p1.py` 在 Windows 下若遇到 `-S` 導致 site-packages 未載入時，自動補全 `site` 尋找 `tzdata`，使 `Asia/Taipei` 等 IANA 時區正確載入。

---

## 4. 實測結果（Test Gate & Verification）

### 4.1 Pre-flight `-CheckOnly` 實測

執行命令：
```powershell
powershell -ExecutionPolicy Bypass -File start_all_demo.ps1 -CheckOnly
```

輸出結果：
```text
Running demo pre-flight checks...
  Free disk space: 129.39 GiB
Pre-flight checks passed successfully (directory and pin checks only; PNG validation and service launch not run).
```
Exit code：`0`（PASS）。

### 4.2 端到端全服務實測（End-to-End Service Launch）

執行命令：
```powershell
powershell -ExecutionPolicy Bypass -File start_all_demo.ps1 -NoOpen
```

輸出結果：
```text
Running demo pre-flight checks...
  Free disk space: 129.39 GiB
Starting Segment A (rec) on port 8766, Segment B (live) on port 8765, Segment C (events) on port 8780...
Waiting for services to become ready (max 180s)...
  ✔ Segment A ready (port 8766)
  ✔ Segment B ready (port 8765)
  ✔ Segment C ready (port 8780)

All services ready. Workbench URL: http://127.0.0.1:8766/workbench-v2/?ev=wall&ev_live=8765&ev_cx=8780
```

- **Segment A (8766)**：P1 Review 工作台服務就緒，回傳 HTTP 200。
- **Segment B (8765)**：P1 Live Tracking 工作台服務就緒，回傳 HTTP 200。
- **Segment C (8780)**：CX-7 多鏡頭事件播放服務於 11.6 秒內完成 4,107 張 PNG 區塊 CRC/SHA-256 全量驗證，A4-1 與 B4-1 均為 OK，回傳 HTTP 200。

---

## 5. 驗證套件與門禁檢查

1. **專屬單元測試**：
   ```powershell
   pytest tests/q1q5/test_windows_demo_start.py -v
   ```
   **8 passed in 4.71s**。涵蓋腳本存在性、自動偵測、目錄遺失防禦、Pin 驗證相容性、Pin 不符 fail-closed、重複 port 拒絕、特權 port 拒絕。
2. **Store 單元測試相容性**：
   ```powershell
   pytest tests/q1q5/test_store.py -v
   ```
   **26 passed, 2 skipped**（在非開發者模式 Windows 上優雅跳過 symlink 建立步驟，無任何失敗）。
3. **架構守門（Architecture Guard）**：
   ```powershell
   python scripts/check_architecture_guard.py --base origin/mainline/q1q5
   ```
   **0 findings, PASS**（authority: PASS, inference: PASS, schemas: PASS）。
4. **Git Diff 格式規範**：
   ```powershell
   git diff --check
   ```
   無任何空白或編碼違規，通過。
