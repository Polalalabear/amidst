# Windows 乾淨 Clone 基準報告（W-A1 Baseline Report）

- **任務編號**：Issue [#419](https://github.com/Polalalabear/amidst/issues/419)（`W-A1 Windows 乾淨 clone 基準報告`）
- **整合基準**：`origin/mainline/q1q5`（`796cc176cd40bedbfe701b95192d3c8679755aa9`）
- **當前 HEAD SHA**：`796cc176cd40bedbfe701b95192d3c8679755aa9`
- **結構化收據**：`docs/operations/WINDOWS_CLEAN_CLONE_BASELINE_20261104.json`
- **收據雜湊（SHA-256）**：`8170a5c20670d7379a111f0bed6771bfb3cbf0719fefd8db782ca180ee7a3373`
- **全體驗證結果**：**PASS**（所有核心自檢與核心測試門檻全數通過）

---

## 1. 執行機器環境基準（Machine Baseline）

| 項目 | 規格 / 偵測值 | 探針來源與說明 |
| --- | --- | --- |
| **作業系統 (OS)** | Windows 11 Pro 64-bit (`10.0.26200-SP0`, `AMD64`) | `platform.platform()`, `platform.uname()` |
| **中央處理器 (CPU)** | 12th Gen Intel(R) Core(TM) i7-12700 | `winreg` (`HARDWARE\DESCRIPTION\System\CentralProcessor\0`) |
| **實體 / 邏輯核心數** | 12 Physical Cores / 20 Logical Cores | `ctypes` (`GetLogicalProcessorInformationEx`) / `os.cpu_count()` |
| **主記憶體 (RAM)** | 31.75 GiB (34.09 GB / 34,088,603,648 bytes) | `ctypes` (`GlobalMemoryStatusEx`)，可用記憶體約 15.3 GiB |
| **圖形處理器 (GPU)** | NVIDIA GeForce RTX 3060 | `nvidia-smi` 原生探針（PowerShell CIM / winreg 雙重備援） |
| **顯示記憶體 (VRAM)** | 12.0 GiB (12,288 MiB) | `nvidia-smi --query-gpu=memory.total` |
| **GPU 驅動程式版本** | 610.88 | `nvidia-smi --query-gpu=driver_version` |
| **可用磁碟空間 (Disk)** | 133.3+ GiB 可用（總量 401.16 GiB） | `shutil.disk_usage(".")`，通過 >= 8.0 GiB 門檻 (D118) |

### 1.1 核心工具鏈版本清單

| 工具名稱 | 探測版本 | 狀態 | 判定標準 |
| --- | --- | --- | --- |
| **Python** | 3.12.0 (`CPython`) | PASS | 要求 >= 3.11 |
| **Node.js** | v24.14.1 | PASS | 可執行且版本正常 |
| **Git** | git version 2.53.0.windows.2 | PASS | 可執行且支援 rev-parse |
| **uv** | uv 0.10.0 (0ba432459 2026-02-05) | PASS | 輔助工具存在 |
| **pytest** | 9.1.1 | PASS | 可執行 Q1-Q5 測試套件 |

### 1.2 Python 模組相依清單

- **必要套件 (Required)**：
  - `numpy`: `2.3.5`（已安裝，PASS）
  - `pydantic`: `2.13.4`（已安裝，PASS）
  - `networkx`: `3.6.1`（已安裝，PASS）
  - `PIL` (Pillow): `12.2.0`（已安裝，PASS）
  - `pytest`: `9.1.1`（已安裝，PASS）
- **選用套件 (Optional)**：
  - `shapely`: 未安裝（PASS，已移出必要套件清單，屬已封存 3D 線選用套件）

---

## 2. 測試與驗證門檻結果（Verification Pass/Fail Summary）

| 檢查項目 | 執行指令 / 驗證方法 | 通過狀態 | 數據與輸出說明 |
| --- | --- | --- | --- |
| **1. Git SHA 對齊** | `git rev-parse HEAD` vs `origin/mainline/q1q5` | **PASS** | 雙方皆為 `796cc176cd40bedbfe701b95192d3c8679755aa9`，完全一致 |
| **2. 環境與硬體自檢** | `python scripts/ensure_env.py --json` | **PASS** | 目錄、磁碟、Python、Node、Git、必要套件皆符合規範 |
| **3. 架構防護檢查** | `python scripts/check_architecture_guard.py --repo . --base origin/mainline/q1q5` | **PASS** | 0 findings（authority、inference、schemas 全數通過） |
| **4. Git Diff Check** | `git diff --check`（檢查本任務異動檔案） | **PASS** | 0 whitespace / EOF newline 違規 |
| **5. Q1-Q5 核心 Python 測試** | `python -m pytest -o pythonpath=src -q ...`（10 個核心模組） | **PASS** | **340 passed, 0 failed**，耗時 2.33 秒 |
| **6. Workbench-v2 Node 測試** | `node --test frontend/workbench-v2/store.test.mjs` | **PASS** | **24 passed, 0 failed**，耗時 0.14 秒 |
| **7. 乾淨 Clone 基準測試** | `python -m pytest -o pythonpath=src -q tests/q1q5/test_clean_clone_baseline.py` | **PASS** | **5 passed, 0 failed**（驗證硬體結構、工具丟失 UNKNOWN、無金鑰洩漏、無絕對主目錄） |
| **8. 跨平台驗證 CLI** | `python scripts/verify_clean_clone.py --json-out docs/operations/WINDOWS_CLEAN_CLONE_BASELINE_20261104.json` | **PASS** | 成功生成結構化 JSON 收據 |

---

## 3. W-A1 針對 Windows 平台實施的相容性修正（Fixes Applied in W-A1）

1. **W-A1-FIX-1：子程序 UTF-8 明確解碼以防止 `cp950` 解碼錯誤**
   - **目標檔案**：`scripts/ensure_env.py`、`scripts/verify_clean_clone.py`
   - **問題**：Windows 繁體中文環境預設終端代碼頁為 `cp950`（Big5 擴展），當 `node --test` 或 `pytest` 輸出包含 UTF-8 符號（如 `✔`、`ℹ`、箭頭）時，若未設定 `encoding="utf-8", errors="replace"`，會直接引發 `UnicodeDecodeError: 'cp950' codec can't decode byte` 中斷程序。
   - **修正**：所有 `subprocess.run` 呼叫統一明確指定 `encoding="utf-8"`, `errors="replace"`，確保輸出解析平順且不因語系代碼頁崩潰。

2. **W-A1-FIX-2：解耦已封存 3D 線選用套件 `shapely`**
   - **目標檔案**：`scripts/ensure_env.py`
   - **問題**：舊版 `ensure_env.py` 將 `shapely` 列入 `REQUIRED_PACKAGES`。但在乾淨的 Q1-Q5 執行環境中，無 C++ GEOS 預編譯函式庫時 Windows 安裝 shapely 易引發建置失敗，且 Q1-Q5 主線第一版 Demo 已不依賴 shapely。
   - **修正**：將 `shapely` 移至 `OPTIONAL_PACKAGES`，未安裝時標記 `installed: false, passed: true, required: false`，不阻擋乾淨環境檢驗。

3. **W-A1-FIX-3：實作 Windows 原生硬體與系統探針（Hardware & OS Probes）**
   - **目標檔案**：`scripts/ensure_env.py`
   - **問題**：macOS/Linux 專屬的 `sysctl`、`/proc/cpuinfo`、`/proc/meminfo` 在 Windows 不可用。
   - **修正**：新增純標準函式庫的 Windows 原生探針：
     - **RAM**：利用 `ctypes.windll.kernel32.GlobalMemoryStatusEx` 讀取 `MEMORYSTATUSEX.ullTotalPhys` 與 `ullAvailPhys`。
     - **CPU 型號**：利用 `winreg` 查詢 `HARDWARE\DESCRIPTION\System\CentralProcessor\0\ProcessorNameString`。
     - **CPU 核心數**：利用 `ctypes.windll.kernel32.GetLogicalProcessorInformationEx`（`RelationProcessorCore`）解析精確實體核心數（12），並以 `os.cpu_count()` 取得邏輯緒數（20）。
     - **GPU / VRAM**：優先以 `nvidia-smi` 查詢；備援支援 PowerShell CIM (`Win32_VideoController`) 與 `winreg` Display Class GUID 註冊表掃描；若皆不可用則優雅回傳 `UNKNOWN`。

4. **W-A1-FIX-4：絕對主目錄與金鑰隔離保護（Zero Path Leakage & Zero Secret Ingestion）**
   - **目標檔案**：`scripts/ensure_env.py`、`scripts/verify_clean_clone.py`
   - **問題**：原先報告直接記錄 `sys.executable` 與 `Path.cwd()` 的絕對路徑（如 `C:\Users\a\...`），違反了「不得含有使用者絕對主目錄（須採相對路徑）、絕不印出金鑰」之安全規範。
   - **修正**：報告中一律正規化為倉庫相對路徑（`repo: "."`, `disk.path: "."`, `python.executable: "python.exe"`, `command: "python -m pytest ..."`），並於自動化測試中注入多種 Canary Token（`AMIDST_API_KEY`, `GITHUB_TOKEN`, `AWS_SECRET_ACCESS_KEY`），確認收據零外洩。

---

## 4. 歷史既有 Windows 測試相容性問題審計（Known Pre-existing Windows Findings）

依任務規定，以下歷史程式碼中的平台相容性問題列為**審計發現（Findings）**，**不直接修改該歷史檔案**，以維護第一版交付契約與範圍隔離：

| 編號 | 發現類別代碼 | 涉及檔案路徑 | 現象描述與根因分析 |
| --- | --- | --- | --- |
| **1** | `POSIX_FCNTL_IMPORT` | `src/amidst/workbench/run_jobs.py` | 頂層無條件執行 `import fcntl`。Windows CRT 無 `fcntl` 模組，導致直接匯入 `run_jobs.py` 或由其他模組連帶匯入時拋出 `ModuleNotFoundError: No module named 'fcntl'`。 |
| **2** | `POSIX_OS_OPEN_FLAGS` | `src/amidst/q1q5/api.py`, `src/amidst/q1q5/store.py` | 檔案寫入與儲存邏輯使用了 POSIX 專屬旗標 `os.O_NOFOLLOW` 與 `os.O_DIRECTORY`。Windows 的 `os` 模組未定義此二旗標，在 Windows 上呼叫會拋出 `AttributeError: module 'os' has no attribute 'O_NOFOLLOW'`。 |
| **3** | `WIN_SYMLINK_PRIVILEGE` | `tests/q1q5/test_api.py` | 測試中包含建立符號連結之斷言。Windows 預設需要系統管理員權限或開啟「開發人員模式 (Developer Mode)」才具備 `SeCreateSymbolicLinkPrivilege`，一般權限執行測試時會失敗並拋出 `[WinError 1314] 缺少用戶端所需要的權限`。 |
| **4** | `SANDBOX_LOOPBACK_HTTP` | `tests/q1q5/test_review_ui_unavailable.py` | 測試啟動本機 HTTP 伺服器並以 `urllib` 探測 `127.0.0.1`。在標準沙盒隔離環境（Sandbox Mode）下，未具備網路權限的環境會阻擋 socket 綁定與本機 loopback 通訊，拋出 `[WinError 10013] 嘗試存取通訊端被拒絕，因存取權限不足`。 |

---

## 5. 交付檔案與產物雜湊（Artifacts & Provenance）

| 檔案路徑 | 類型 | 說明 |
| --- | --- | --- |
| `scripts/ensure_env.py` | 核心指令稿 | 跨平台環境與硬體自檢 CLI（支援 Windows 原生硬體探測、相對路徑防洩漏） |
| `scripts/verify_clean_clone.py` | 核心指令稿 | 跨平台乾淨 Clone 驗證 CLI（整合 SHA、環境、diff、架構防護、核心測試、相容性審計） |
| `docs/operations/WINDOWS_CLEAN_CLONE_BASELINE_20261104.json` | 結構化收據 | 完整 JSON 驗證收據（SHA-256: `8170a5c20670d7379a111f0bed6771bfb3cbf0719fefd8db782ca180ee7a3373`） |
| `docs/operations/WINDOWS_CLEAN_CLONE_BASELINE_20261104.md` | 本文件 | 基準報告摘要、硬體與工具清單、相容性修復、歷史已知問題審計 |
| `tests/q1q5/test_clean_clone_baseline.py` | 單元測試 | 5 項自動化測試，驗證硬體鍵、優雅 UNKNOWN、收據結構、零金鑰與零主目錄洩漏 |

---

## 6. 未驗證項目說明（Not Verified）

1. **歷史既有相容性問題模組之修復**：未修復 `src/amidst/workbench/run_jobs.py` 中的 `fcntl` 匯入與 `src/amidst/q1q5/api.py` 中的 `os.O_NOFOLLOW`，依任務規範維持不修改，僅記錄於審計發現。
2. **非 Windows 作業系統之本次迴歸**：本報告係於 Windows 11 本地環境實跑驗證完成，macOS / Linux 探針邏輯已保持分支相容但未於本機切換 OS 重跑。
