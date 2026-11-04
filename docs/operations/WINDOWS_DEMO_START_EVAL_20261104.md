# Windows 一鍵啟動 demo 實測報告（Issue #429 / W-A11）

日期：2026-11-04（Asia/Taipei）
執行者：Argon
分支：`argon/429-windows-demo-start-eval`（base: `origin/mainline/q1q5`）
依據：#411 `start_all_demo.ps1`、#416 資料前置交件通知、`docs/operations/DEMO_RUNBOOK_20261104.md`

---

## 1. 摘要與測試目標

本任務實測並完善 `start_all_demo.ps1` 在原生 Windows PowerShell 5.1 / 7+ 環境下的端到端啟動流程，主要覆蓋：
1. **Safe 資料驗證**：在 Windows 本機以 Python 3.12 stdlib 獨立驗證 #416 提供之三包安全資料（`p1-v4-stripped`、`cx7-d119`、`cx7-d124`）。
2. **前置資源檢查與路徑自動偵測**：修復 `start_all_demo.ps1` 在 Windows 下對 safe data 目錄、manifest pin 與相依環境之自動偵測與路徑解析。
3. **相容性與門禁測試**：實作專屬單元測試套件 `tests/q1q5/test_windows_demo_start.py`，全數通過。
4. **端到端啟動實測與失敗點分析**：記錄 Windows 下全服務啟動之相容性瓶頸與後續修正方向。

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

## 3. `start_all_demo.ps1` 修正與增強內容

針對 Windows 環境與 #416 safe packs 交付結構，在 `start_all_demo.ps1` 進行以下修正：

1. **Safe Data 本機路徑自動偵測**：
   - `$P1Bundle` 優先偵測 `$env:P1_BUNDLE`，若無則自動尋找工作目錄下的 `.\p1-v4-stripped` 或 `$env:AMIDST_SAFE_PACKS\p1-v4-stripped`，免除手動指定長路徑。
   - `$CX7Root` 優先偵測 `$env:CX7_ROOT`，若無則自動尋找工作目錄下的 `.\cx7-d119` 或 `$env:AMIDST_SAFE_PACKS\cx7-d119`。
2. **P1 Runtime Manifest Pin 雙向相容**：
   - 支援原版 v4 Pin（`6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`）以及新版 stripped runtime Pin（`13ab3c559fd63dd6f5d44ac7f6dabe1192274b368bfd1307f3a3bbd6682e5805`）。
   - 新增 `-ManifestSha` 參數與 `$env:MANIFEST_SHA`，供使用者或測試指定特定 pin；非核定 pin 自動 fail-closed。
3. **PowerShell 跨版本語法與路徑安全性**：
   - 保持 `-LiteralPath` 與 NTFS ReparsePoint（symlink / junction）防禦檢查。
   - 透過 Node.js 讀取 `frontend/event-viewer/runs.mjs` 解析 declared safe camera directory catalog，在 `-CheckOnly` 階段完成所有鏡頭資料夾存在性校驗。

---

## 4. 實測結果與失敗點分析（Test Gate & Diagnostic）

### 4.1 Pre-flight `-CheckOnly` 實測

執行命令：
```powershell
powershell -ExecutionPolicy Bypass -File start_all_demo.ps1 -CheckOnly
```

輸出結果：
```text
Running demo pre-flight checks...
  Free disk space: 132.45 GiB
Pre-flight checks passed successfully (directory and pin checks only; PNG validation and service launch not run).
```
Exit code：`0`（PASS）。

### 4.2 啟動失敗點定位（End-to-End Service Launch Bottleneck）

在進行完整三進程啟動（Segment A, B, C）時，定位到以下 Windows 平臺專屬相容性問題：

1. **POSIX File Open Flag 在 Windows 上不可用**：
   - **觸發位置**：`src/amidst/q1q5/production_preflight.py` L32 及 `src/amidst/q1q5/p1_workbench.py` L58：
     ```python
     fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
     ```
   - **錯誤現象**：
     ```text
     AttributeError: module 'os' has no attribute 'O_NOFOLLOW'
     ```
   - **原因分析**：`os.O_NOFOLLOW` 與 `os.O_NONBLOCK` 為 POSIX 專屬常數，在 Windows 原生 Python（如 Python 3.12 官方 Windows build）並未提供。
   - **建議解法（跨平臺適配）**：在開啟檔案時應使用 `getattr(os, "O_NOFOLLOW", 0)` 與 `getattr(os, "O_NONBLOCK", 0)`，並在 Windows 上使用 `path.is_symlink()` / `os.path.islink()` 作為替代防禦。
2. **P1 剝除版 Media Reader 轉接器尚未併入 mainline**：
   - `p1-v4-stripped` 依賴 PR #449（`codex/416-safe-packs`）中引入的 `bundle_media_reader`，目前 `mainline/q1q5` 尚未包含此 adapter。

---

## 5. 驗證套件與門禁檢查

1. **專屬單元測試**：
   ```powershell
   pytest tests/q1q5/test_windows_demo_start.py -v
   ```
   **8 passed in 4.70s**。涵蓋腳本存在性、自動偵測、目錄遺失防禦、Pin 驗證相容性、Pin 不符 fail-closed、重複 port 拒絕、特權 port 拒絕。
2. **架構守門（Architecture Guard）**：
   ```powershell
   python scripts/check_architecture_guard.py --repo . --base origin/mainline/q1q5
   ```
   **0 findings, PASS**。
3. **Git Diff 格式規範**：
   ```powershell
   git diff --check
   ```
   無任何空白或編碼違規，通過。
