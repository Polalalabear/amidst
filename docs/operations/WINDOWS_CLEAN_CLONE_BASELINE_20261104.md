# Windows 乾淨 Clone 基準報告（W-A1 Baseline Report）

- **任務編號**：Issue [#419](https://github.com/Polalalabear/amidst/issues/419)（`W-A1 Windows 乾淨 clone 基準報告`）／Draft PR [#440](https://github.com/Polalalabear/amidst/pull/440)
- **整合基準**：`origin/mainline/q1q5`（`796cc176cd40bedbfe701b95192d3c8679755aa9`）
- **受測程式碼 Commit SHA（Source-bound HEAD）**：`def9e1dc4fabf89f86546da4663523728b1d76e9`
- **結構化收據**：`docs/operations/WINDOWS_CLEAN_CLONE_BASELINE_20261104.json`
- **收據雜湊（SHA-256）**：`223ac914b42da8ecb48d5840560a01d353684d10f4e84f348a955e0b355e764b`（33,843 bytes）
- **全體驗證結果**：**PASS**（乾淨工作區檢查、環境相依、diff、架構防護與核心測試門檻全數通過）

---

## 1. 執行機器環境基準（Machine Baseline）

| 項目 | 規格 / 偵測值 | 探針來源與說明 |
| --- | --- | --- |
| **作業系統 (OS)** | Windows 11 Pro 64-bit (`10.0.26200-SP0`, `AMD64`) | `platform.platform()`, `platform.uname()` |
| **中央處理器 (CPU)** | 12th Gen Intel(R) Core(TM) i7-12700 | `winreg` (`HARDWARE\DESCRIPTION\System\CentralProcessor\0`) |
| **實體 / 邏輯核心數** | 12 Physical Cores / 20 Logical Cores | `ctypes` (`GetLogicalProcessorInformationEx`) / `os.cpu_count()` |
| **主記憶體 (RAM)** | 31.75 GiB (34.09 GB / 34,088,603,648 bytes) | `ctypes` (`GlobalMemoryStatusEx`)，可用記憶體約 16.92 GiB |
| **圖形處理器 (GPU)** | NVIDIA GeForce RTX 3060 | `nvidia-smi` 原生探針（PowerShell CIM / winreg 雙重備援） |
| **顯示記憶體 (VRAM)** | 12.0 GiB (12,288 MiB) | `nvidia-smi --query-gpu=memory.total` |
| **GPU 驅動程式版本** | 610.88 | `nvidia-smi --query-gpu=driver_version` |
| **可用磁碟空間 (Disk)** | 130.45 GiB 可用（總量 401.16 GiB） | `shutil.disk_usage(".")`，通過 >= 8.0 GiB 門檻 (D118) |

### 1.1 核心工具鏈版本清單

| 工具名稱 | 探測版本 | 狀態 | 判定標準 |
| --- | --- | --- | --- |
| **Python** | 3.12.0 (`CPython`) | PASS | 要求 >= 3.12（符合 pyproject.toml） |
| **Node.js** | v24.14.1 | PASS | 可執行且版本正常 |
| **Git** | git version 2.53.0.windows.2 | PASS | 可執行且支援 rev-parse |
| **uv** | uv 0.10.0 (0ba432459 2026-02-05) | PASS | 輔助工具存在 |
| **pytest** | 9.1.1 | PASS | 可執行 Q1-Q5 測試套件 |

### 1.2 Python 模組相依清單（對齊 pyproject.toml 最小門檻）

| 套件名稱 | 安裝版本 | pyproject 門檻 | 狀態 | 說明 |
| --- | --- | --- | --- | --- |
| `numpy` | 2.5.4 | >= 2.5.3 | PASS | 滿足核心數值計算需求 |
| `pydantic` | 2.14.2 | >= 2.13.5 | PASS | 滿足資料結構驗證需求 |
| `networkx` | 3.7 | >= 3.7 | PASS | 滿足相機/區域圖演算法需求 |
| `shapely` | 2.2.0 | >= 2.1.2, < 3 | PASS | 必要相依，非 optional |
| `PIL` (Pillow) | 12.2.0 | - | PASS | 滿足影像處理需求 |
| `pytest` | 9.1.1 | >= 9.1.1 | PASS | 滿足測試套件需求 |
| `psycopg` | 3.3.6 | == 3.3.6 | PASS | 滿足執行期資料庫驅動需求 |
| `rerun-sdk` | 0.42.0 | >= 0.38.1 | PASS | 滿足 3D/日誌視覺化相依需求 |
| `mypy` | 2.4.1 | >= 2.3.1 | PASS | 滿足開發靜態檢查相依 |
| `ruff` | 0.17.3 | >= 0.16.9 | PASS | 滿足開發 linter 相依 |
| `types-shapely` | 2.1.0.20261030 | >= 2.1, < 3 | PASS | 滿足型別註解相依 |

---

## 2. 測試與驗證門檻結果（Verification Pass/Fail Summary）

收據產自完全隔離、未受本機其他開發任務污染之乾淨 Clone 目錄（`scratch/clean419`），執行指令：
`python scripts/verify_clean_clone.py --repo . --base origin/mainline/q1q5 --json-out docs/operations/WINDOWS_CLEAN_CLONE_BASELINE_20261104.json`

| 檢查項目 | 驗證方法 / 指令 | 狀態 | 數據與詳細輸出說明 |
| --- | --- | --- | --- |
| **1. HEAD & Base SHA 解析** | `git rev-parse HEAD / base` | **PASS** | HEAD=`def9e1dc4fabf89f86546da4663523728b1d76e9`, Base=`796cc176cd40bedbfe701b95192d3c8679755aa9` |
| **2. 工作區乾淨度檢查** | `git status --porcelain=v1` | **PASS** | 乾淨 clone 無任何 staged / unstaged / untracked 異動（0 changes） |
| **3. 環境與硬體自檢** | `python scripts/ensure_env.py` | **PASS** | 目錄、磁碟、Python (>=3.12)、Node、Git、必要套件皆符合 pyproject.toml 規範 |
| **4. Git Diff 格式檢查** | `git diff --check` | **PASS** | 0 findings（無 trailing whitespace、無 EOF newline 違規、returncode=0） |
| **5. 架構防護守門** | `python scripts/check_architecture_guard.py --repo . --base origin/mainline/q1q5` | **PASS** | 0 findings（無 `--allow`，authority、inference、schemas 全數通過，returncode=0） |
| **6. POSIX / Windows 相容性審計** | 靜態相容性探查與能力審計 | **PASS** | 審計記錄既有 Windows 相容性發現，探測能力如實記錄 |
| **7. Q1-Q5 核心 Python 測試** | `python -m pytest -o pythonpath=src ...`（10 個核心測試模組） | **PASS** | **340 passed, 0 failed, 0 skipped**，耗時 1.95 秒（嚴格摘要解析，非猜測數值） |
| **8. Workbench-v2 Node 測試** | `node --test frontend/workbench-v2/store.test.mjs` | **PASS** | **24 passed, 0 failed, 0 skipped**，耗時 0.09 秒（嚴格 stdout 解析） |
| **9. 乾淨 Clone 基準測試套件** | `python -m pytest tests/q1q5/test_clean_clone_baseline.py` | **PASS** | **24 passed, 0 failed**（包含全部 6 項 Codex REVISE 必修反例與新增 fail-closed / optional parser 回歸守門） |

---

## 3. Codex 審查意見與程式修正演進

依據 Codex 於 Issue [#419](https://github.com/Polalalabear/amidst/issues/419)／Draft PR [#440](https://github.com/Polalalabear/amidst/pull/440) 提出之審查意見與交件指示：
- Codex 新增 commits `e8bb12b`（make clean clone gates fail closed）與 `def9e1d`（keep environment checker parser optional），將受測程式碼 head推進至 `def9e1dc4fabf89f86546da4663523728b1d76e9`。
- 本次 Windows 乾淨 Clone 於該 head 實跑，完整通過所有門檻，並以獨立 receipt commit 保存實測 JSON 與本說明文件。

| 項目 | 審查意見與要求 | 修復動作與程式碼位置 | 驗證與回歸測試 |
| --- | --- | --- | --- |
| **P1** | **原始守門 FAIL 不得改成 PASS**：不得刪除 untracked/非 scripts finding，不得抹除 returncode，原始 status/returncode 原樣保留。 | 於 `scripts/verify_clean_clone.py` 移除所有 finding 過濾與 returncode 覆寫邏輯，原樣保留 `check_architecture_guard.py` 的 status、returncode 與完整 findings。 | `test_guard_failure_not_masked_or_filtered`：模擬 guard 失敗反例，確認 wrapper 如實回報 FAIL。 |
| **P2-1** | **其他檔案 whitespace 失敗不得丟棄**：保留整個 `git diff --check` 結果與 exitcode，不可事後改結果。 | 於 `scripts/verify_clean_clone.py` 移除檔案路徑白名單過濾，保留完整 diff findings 與 returncode（exitcode != 0 即為 FAIL）。 | `test_whitespace_diff_failure_preserved`：模擬非腳本檔案空白違規反例，確認 wrapper 如實回報 FAIL。 |
| **P2-2** | **加入乾淨 checkout 與嚴格 base 檢查**：新增 `git status --porcelain` 守門；base rev-parse 失敗不得 PASS。 | 於 `scripts/verify_clean_clone.py` 新增 `check_clean_checkout`（執行 `git status --porcelain=v1`，非空即 FAIL）與 `check_git_rev_parse`（HEAD 與 base 皆須成功解析 40-char SHA，否則 FAIL）。 | `test_unclean_checkout_fails` 與 `test_missing_base_fails_rev_parse`。 |
| **P2-3** | **缺測試/跳測試不可整體 PASS，不得猜測數字**：移除 test 缺檔 fallback 與 Node 缺檔 SKIPPED 認定；Node 與 Python 測試計數嚴格解析，不可解析回報 FAIL / None；`--skip-tests` 與 `--quick` 分別回報 `CHECKS_ONLY` 與 `SMOKE_ONLY`。 | 移除 HSV fallback 與 Node SKIPPED；移除 Node 猜測 24 邏輯；移除 wrapper 中的額外 `-q` 旗標；實作嚴格解析：若未包含 `N passed` 摘要行，則 `passed_count` 設為 `None` 且 `status` 設為 `FAIL`；依執行參數嚴格設定 `CHECKS_ONLY` / `SMOKE_ONLY`。 | 6 項測試：`test_missing_python_test_fails_without_guess`、`test_missing_node_test_fails_without_guess`、`test_node_unparseable_output_fails_without_guessing_24`、`test_python_unparseable_output_fails_without_guessing`、`test_skip_tests_reports_checks_only`、`test_quick_mode_reports_smoke_only`。 |
| **P2-4** | **環境門檻對齊 pyproject.toml**：Python 須 >= 3.12，不得接受 3.11；`shapely` 維持必要相依，不得自行改為 optional；相依套件版本對齊 pyproject minima。 | 於 `scripts/ensure_env.py` 將 Python 最低版本門檻調升為 `>=3.12`；將 `shapely` 復原為必要相依（`REQUIRED_PACKAGES`）；本地環境升級至 numpy 2.5.4、networkx 3.7、pydantic 2.14.2、shapely 2.2.0。 | `test_python_version_gate_312`。 |
| **P2-5** | **收據 source binding 與精確 SHA-256**：收據必須綁定真實測試程式碼 commit SHA，不得在未 commit 狀態下以 mainline SHA 頂替；精確回填實際 bytes 之 SHA-256。 | 綁定新 code commit `def9e1dc4fabf89f86546da4663523728b1d76e9`；在獨立乾淨 clone 中實跑產生收據；以獨立收據提交記錄 JSON 與本文件，精確核算 committed bytes 之 SHA-256（`223ac914b42da8ecb48d5840560a01d353684d10f4e84f348a955e0b355e764b`）。 | 收據 JSON SHA-256 驗證吻合。 |
| **Codex 新增** | **Fail-closed 檢查與可選版本解析器處理** | commit `e8bb12b` 確保未預期異常一律 fail-closed；commit `def9e1d` 保持 packaging / packaging.requirements 為可選匯入，缺 parser 時回傳 UNKNOWN 而非 crash。 | 24 項 focused tests 全數通過。 |

---

## 4. 歷史既有 Windows 測試相容性問題審計（Known Pre-existing Windows Findings）

依任務規範，以下歷史程式碼中的平台相容性問題列為**審計發現（Findings）**，**不直接修改該歷史檔案**，以維護第一版交付契約與範圍隔離：

| 編號 | 發現類別代碼 | 涉及檔案路徑 | 現象描述與根因分析 |
| --- | --- | --- | --- |
| **1** | `POSIX_FCNTL_IMPORT` | `src/amidst/workbench/run_jobs.py` | 頂層無條件執行 `import fcntl`。Windows CRT 無 `fcntl` 模組，導致直接匯入 `run_jobs.py` 或由其他模組連帶匯入時拋出 `ModuleNotFoundError: No module named 'fcntl'`。 |
| **2** | `POSIX_OS_OPEN_FLAGS` | `src/amidst/q1q5/api.py`, `src/amidst/q1q5/store.py` | 檔案寫入與儲存邏輯使用了 POSIX 專屬旗標 `os.O_NOFOLLOW` 與 `os.O_DIRECTORY`。Windows 的 `os` 模組未定義此二旗標，在 Windows 上呼叫會拋出 `AttributeError: module 'os' has no attribute 'O_NOFOLLOW'`。 |
| **3** | `WIN_SYMLINK_PRIVILEGE` | `tests/q1q5/test_api.py` | 測試中包含建立符號連結之斷言。Windows 預設需要系統管理員權限或開啟「開發人員模式 (Developer Mode)」才具備 `SeCreateSymbolicLinkPrivilege`，一般權限執行測試時會失敗並拋出 `[WinError 1314] 缺少用戶端所需要的權限`。 |
| **4** | `SANDBOX_LOOPBACK_HTTP` | `tests/q1q5/test_review_ui_unavailable.py` | 測試啟動本機 HTTP 伺服器並以 `urllib` 探測 `127.0.0.1`。在標準沙盒隔離環境（Sandbox Mode）下，未具備網路權限的環境會阻擋 socket 綁定與本機 loopback 通訊，拋出 `[WinError 10013] 嘗試存取通訊端被拒絕，因存取權限不足`。 |

---

## 5. 交付檔案與產物雜湊（Artifacts & Provenance）

### 5.1 受測程式碼檔案（固定於 commit `def9e1dc4fabf89f86546da4663523728b1d76e9`）

| 檔案路徑 | SHA-256 | 位元組大小 | 說明 |
| --- | --- | --- | --- |
| `scripts/ensure_env.py` | `8b775c6fc758c44478c55a6fedf4dd324410b36647a17c43b25ae6d53d5542df` | 31,210 bytes | 跨平台環境與硬體自檢 CLI（Windows 原生探針、相對路徑防洩漏、pyproject 對齊、可選 parser） |
| `scripts/verify_clean_clone.py` | `42ef014da30491e74e6b36d026c2fcac3ae5c4fdb9c94a44f5068aa91016d8a8` | 22,612 bytes | 跨平台乾淨 Clone 驗證 CLI（嚴格守門、乾淨度檢查、無 filter、嚴格計數解析、fail-closed） |
| `tests/q1q5/test_clean_clone_baseline.py` | `a74d0870a88bbc30e7a759cbc46774c15fc7c160cd9d0742592251b27fda39cb` | 22,687 bytes | 24 項自動化單元測試與行為回歸守門 |

### 5.2 驗證收據與文件產物（Receipt-only Commit）

| 檔案路徑 | SHA-256 | 位元組大小 | 說明 |
| --- | --- | --- | --- |
| `docs/operations/WINDOWS_CLEAN_CLONE_BASELINE_20261104.json` | `223ac914b42da8ecb48d5840560a01d353684d10f4e84f348a955e0b355e764b` | 33,843 bytes | 結構化驗證收據（完全無使用者個人主目錄路徑、無 API key、status PASS） |
| `docs/operations/WINDOWS_CLEAN_CLONE_BASELINE_20261104.md` | 本文件 | - | 基準報告摘要、硬體與工具清單、P1/P2 修復對照表、歷史已知問題審計 |

---

## 6. 未驗證項目說明（Not Verified）

1. **歷史既有相容性問題模組之就地修改**：未修復 `src/amidst/workbench/run_jobs.py` 中的 `fcntl` 匯入與 `src/amidst/q1q5/api.py` 中的 `os.O_NOFOLLOW`，依任務規範維持不修改歷史程式碼，僅記錄於審計發現。
2. **非 Windows 作業系統之本地重跑**：本報告係於 Windows 11 本地環境實跑驗證完成；macOS/Linux 已由 Codex 審查及主線 CI 獨立驗證。
3. **完整系統端到端物理推論/渲染**：本任務聚焦 Windows 乾淨 clone 與環境驗證門檻，未涵蓋完整 3D 渲染與推論系統驗收。
