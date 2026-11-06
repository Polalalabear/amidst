# 從頭建置與重現（BUILD_FROM_SCRATCH）

返回 [README](README.md)。架構見 [SYSTEM_ARCH.md](SYSTEM_ARCH.md)，規格見 [SPEC.md](SPEC.md)。

本文件寫「從 Blender 建檔到工作台啟動」的完整流程，目標是讓另一個人照著做就能重現。**每一步都只寫 repo 裡實際存在的腳本、設定與收據**；repo 裡找不到的步驟標 **UNKNOWN**，並寫出缺什麼。除非另外註明，repo 檔案都在 `mainline/q1q5`@`796cc17` 讀取。

## 0. 先講結論：目前能重現到哪裡

| 步驟 | 能否只靠 repo 重現 | 缺什麼 / 備註 |
| --- | --- | --- |
| 環境（Python 套件） | 部分 | `pyproject.toml`／`uv.lock` 沒有 torch、torchvision、Pillow、PyYAML；版本記在 `configs/q1q5/linked_baseline_environment.json` |
| r004 場景建檔（`.blend`） | **不能** | 父檔 r003 `.blend` 與 r004 建檔腳本（`build_static_v2.py` 等）都是 LOCAL，不在 repo |
| P1 工程場景（B-05 用） | 可以（腳本在 repo） | 腳本會自己建幾何；但 demo 用的 P1 v4 包是否就是這份設定產生的：**UNKNOWN** |
| 路線與事件時刻 | 可以（規劃 JSON 與凍結檔在 repo） | — |
| r004 渲染（A4-1／B4-1） | **不能** | producer `render_cx7.py` 在 LOCAL 的 `gt_private/`，不在 repo |
| safe bundle 檢查 | 可以（checker 在 repo） | 需要已渲染的 LOCAL run 目錄 |
| 兩層圖標記 | 部分 | 建圖腳本在 repo；需要 LOCAL 靜態 provenance（`r004-prereview-team-v2_20261024/provenance`） |
| 宣告時鐘 | 可以 | — |
| RT-DETR 偵測索引（r004） | **不能**（尚未產製） | #118 只有計畫；r004 adapter、production decoder、核定參數都 **UNKNOWN**／未完成 |
| 擴充 Office 場景（多間教室＋COCO 物件） | **不能**（尚未建） | D126-2 已指派 Codex，repo 裡沒有腳本或設定 |
| Windows 啟動工作台 | **待驗（由 #429 負責）** | W-A1（#419 / PR [#440](https://github.com/Polalalabear/amidst/pull/440)）已完成乾淨 clone 測試基準驗證（code head `def9e1dc4fabf89f86546da4663523728b1d76e9`、receipt commit `2372767`、JSON SHA-256 `223ac914b42da8ecb48d5840560a01d353684d10f4e84f348a955e0b355e764b`，340 core Python + 24 Node + 24 clean clone focused tests PASS）；PR [#443](https://github.com/Polalalabear/amidst/pull/443) 提供 `start_all_demo.ps1` 原生啟動腳本，而完整 Windows 服務啟動與實際運行評估由 Issue [#429](https://github.com/Polalalabear/amidst/issues/429)（W-A11）專門執行驗證，W-A10 不代驗 |

## 1. 環境

### 1.1 版本

| 項目 | 版本 | 出處 |
| --- | --- | --- |
| Blender | 5.2.1 LTS（build `9e2066aef7ef`，2026-08-25），引擎 `BLENDER_EEVEE` | `docs/engineering/R004_EVENT_RUNS_RECEIPT.md`、`docs/engineering/R004_BUILD_RECEIPT.md` §2 |
| Python | `>=3.12`；Windows 乾淨基準實測 3.12.0；基準環境實際 3.12.12 | `pyproject.toml`；`WINDOWS_CLEAN_CLONE_BASELINE_20261104.json` |
| 專案依賴 | matplotlib≥3.10、networkx≥3.7、numpy≥2.5.3、pydantic≥2.13.5、psycopg[binary]==3.3.6、rerun-sdk≥0.38.1、shapely≥2.1.2,<3；dev：pytest≥9.1.1、ruff、mypy | `pyproject.toml`、`uv.lock` |
| 偵測額外依賴 | torch 2.6.0、torchvision 0.21.0、Pillow 13.0.0、PyYAML 6.0.3 | `configs/q1q5/linked_baseline_environment.json`（`extra_existing_runtime_dependencies`） |
| RT-DETR | 官方 R18；source commit `df2a96c8c3a098567a1149bf0248da6efe6d495d`；source zip SHA-256 `e6014ae32d2d…6564`；權重 SHA-256 `3ba8b5c909c9…66f0`（81,001,853 bytes） | `linked_baseline_environment.json`；`R004_BUILD_RECEIPT.md` §3 |
| Node | 前端測試與 event-viewer 需要；Windows 基準實測 **v24.14.1** | `WINDOWS_CLEAN_CLONE_BASELINE_20261104.json` |
| uv | 專案用 `uv run`；Windows 基準實測 **0.10.0** | 同上 |
| Git | 專案版本控制；Windows 基準實測 **2.53.0.windows.1** | 同上 |
| Ollama／Qwen | `qwen3:1.7b-q4_K_M`，只有 AGENT_SEQUENTIAL 需要；兩個核心的 demo 不需要 | `linked_baseline_environment.json` |

### 1.2 Windows 安裝與實測指引

依據 W-A1（#419 / PR [#440](https://github.com/Polalalabear/amidst/pull/440)）之 Windows 11 乾淨 clone 實測驗證收據（受測代碼 head `def9e1dc4fabf89f86546da4663523728b1d76e9`、收據 commit `2372767`、結構化 JSON SHA-256 `223ac914b42da8ecb48d5840560a01d353684d10f4e84f348a955e0b355e764b`，驗證結果：340 core Python + 24 Node + 24 clean clone focused tests PASS），安裝與環境要求分為三組：

| 用途 | 需要 |
| --- | --- |
| A. 只看錄製重播與 UI | Python 3.12＋專案依賴、Node v24、Git for Windows、safe RGB；**不需要** Blender、RT 權重、Qwen |
| B. 重跑模型推論 | A 再加 torch 2.6.0／torchvision 0.21.0／Pillow／PyYAML、RT-DETR 官方 source 與權重（核對上表 SHA） |
| C. 從頭渲染 | B 再加 Blender 5.2.1 LTS（blender.org 官方版） |

**Windows 安裝與驗證流程**：

W-A1（#419 / PR [#440](https://github.com/Polalalabear/amidst/pull/440)）正式驗證的端到端標準流程為乾淨 clone 驗證器（`scripts/verify_clean_clone.py`）；下方條列手動步驟中，核心驗證指令（第 3、6 步）為實測通過指令，手動 venv/pip 指令（第 4、5 步）為備援參考範例：

1. 安裝 Python 3.12（官方 64-bit）、Node v24、Git for Windows 與 uv。
2. 設定環境變數 `PYTHONUTF8=1`，確保 Windows 控制台與 Python 子行程預設使用 UTF-8 編碼，防止繁體中文 `cp950` 代碼頁錯誤。
3. **環境檢查（已實測 PASS）**：在乾淨 clone 目錄執行原生探針：
   ```powershell
   python scripts/ensure_env.py --json-out env_report.json
   ```
   腳本具備原生 WinAPI 探針（`GlobalMemoryStatusEx`、`GetLogicalProcessorInformationEx` + `winreg`、`nvidia-smi` + CIM / `winreg` 備援），路徑嚴格正規化防止個資洩漏。
4. **依賴套件安裝（標準與手動備援範例）**：
   標準推薦指令（由 `uv` 管理）：
   ```powershell
   uv sync
   ```
   手動 venv 備援參考範例（未列入正式 CI 回條）：
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e .
   ```
5. **推論依賴加裝（手動備援參考範例）**：B 組推論在既有環境手動加裝：
   ```powershell
   pip install torch==2.6.0 torchvision==0.21.0 Pillow>=10.0.0 PyYAML>=6.0.0
   ```
6. **乾淨基準全套守門與回歸驗證（W-A1 正式實測已驗證，PASS）**：
   ```powershell
   python scripts/verify_clean_clone.py --repo . --base origin/mainline/q1q5 --json-out clean_clone_report.json
   ```
   此命令實跑乾淨 checkout 檢查、`check_architecture_guard.py`（0 findings，無 `--allow`）、340 項核心 Python 測試、24 項 Node 測試與 24 項 clean clone focused tests，均全數通過。

## 2. 場景建檔

### 2.1 r004 場景

- r004 的 geometry、材質、燈光、鏡頭放置都在 Blender 檔案裡，**repo 內沒有** `.blend` 原檔。
- 只有收據 `docs/engineering/R004_BUILD_RECEIPT.md` 記錄建檔資訊。鏡頭參數見其 §2：7 台追蹤鏡頭＋1 台 CAM_ENTRY，水平視角 55.4°～83.0°。
- 建檔腳本與世界座標清單（`cameras.json`）在 LOCAL 目錄，不在 repo。

### 2.2 P1 工程場景

- 幾何與鏡頭由腳本建立：`scripts/render_q1q5_dynamic_rgb.py` 讀取 `configs/q1q5/dynamic_engineering_v1.json`。
- 產生 2 台鏡頭（CAM_A、CAM_B），各 160 格，20 fps，長度 8 s。

### 2.3 擴充 Office 場景（D126-2）

- 目標：多間標註教室（例如 R101～R104），每間有室內鏡頭，場景內放置 COCO 可辨識物件。
- 目前狀態：**尚未產出**。

## 3. 路線與事件時刻

- A4-1：50 s、5 fps、250 格。凍結設定 `configs/q1q5/a4_freeze_v1.json`。
- B4-1：42 s、5 fps、210 格。凍結設定 `configs/q1q5/b4_freeze_v1.json`。
- 劇本與關鍵影格屬於 GT，**不進入推論端**。

## 4. 渲染

- r004 渲染由 LOCAL producer 執行，輸出分成 `safe/` 和 `gt_private/`。
- 渲染磁碟安全門檻：可用空間低於 8 GiB 時全面停止寫檔（D118）。
- safe bundle 結構檢查：
  ```powershell
  python scripts/check_event_run_bundle.py --bundle-dir <RUN_DIR>
  ```

## 5. 標記與索引

### 5.1 兩層圖

- Region graph：`configs/q1q5/graphs/r004/region_graph_v3_1.json`
- Camera graph：`configs/q1q5/graphs/r004/camera_graph_v3_1.json`
- Tracking scope：`configs/q1q5/graphs/r004/tracking_scope_v3_1.json`

### 5.2 宣告時鐘

- A4-1：`configs/q1q5/clocks/r004_a4_v1.json`（wall_origin: `2026-11-01T14:00:00+08:00`）
- B4-1：`configs/q1q5/clocks/r004_b4_v1.json`（wall_origin: `2026-11-01T14:10:00+08:00`）

### 5.3 RT-DETR 偵測索引

- 離線跑 `src/amidst/q1q5/detection_index.py` 產生 JSONL 索引；查詢端只讀索引，不補推論。

## 6. 每步驗證指令

每項驗證在 Windows PowerShell 上均可直接執行：

| 驗證項目 | 命令 | 預期結果 |
| --- | --- | --- |
| 環境檢查 | `python scripts/ensure_env.py` | 全 PASS，顯示 OS、CPU、RAM、GPU、Python、Node、uv 版本 |
| 乾淨 clone 驗證 | `python scripts/verify_clean_clone.py --repo . --base origin/mainline/q1q5` | 全 PASS，340 Python + 24 Node 核心測試全過 |
| 核心契約驗收測試（Python） | `python -m pytest -o pythonpath=src -q tests/q1q5/test_core_search_track_t.py` | 契約驗收測試通過（在 #443 下 0 fail） |
| 核心契約驗收測試（Node） | `node --test frontend/workbench-v2/core-search-track.test.mjs` | 24 tests passed |
| 跨平台腳本回歸測試 | `python -m pytest -o pythonpath=src -q tests/q1q5/test_clean_clone_baseline.py` | 17 passed |
| 架構守門（無 allow） | `python scripts/check_architecture_guard.py --repo . --base origin/mainline/q1q5` | authority／inference／schemas 各 0 findings，status PASS |
| 程式碼排版與換行 | `git diff --check origin/mainline/q1q5...HEAD` | 0 findings（無輸出） |

## 7. 在 Windows 上跑起工作台

在 Windows 環境中，啟動 demo 推薦使用原生 PowerShell 腳本 `start_all_demo.ps1`（PR [#443](https://github.com/Polalalabear/amidst/pull/443)）。

### 7.1 一鍵啟動（PowerShell 原生）

在單一 PowerShell 視窗中：

```powershell
# 1. 唯讀資源與埠號預檢（不啟動行程）
.\start_all_demo.ps1 -CheckOnly

# 2. 正式啟動全部三段（背景作業管理，自動監控）
.\start_all_demo.ps1
```

腳本會自動檢查 8766、8765、8780 埠號，建立專屬 state 目錄，以 background jobs 啟動三段服務，並在按下 Ctrl+C 時自動乾淨停止所有子行程。

### 7.2 替代手動啟動步驟（三終端機）

若需手動逐步啟動，開三個 PowerShell 視窗：

**準備環境變數與目錄**：
```powershell
$P1_BUNDLE = "C:\path\to\p1_v4_bundle"   # 需含 MANIFEST.json，SHA-256 6e9a0a4c…f1d7
$CX7_ROOT = "$HOME\amidst-artifacts\r004-cx7-d115-20261102-01a199f8"
$STATE_PARENT = "$HOME\amidst-demo-state"
New-Item -ItemType Directory -Force -Path $STATE_PARENT
```

**段 A：錄製伺服器（埠 8766）**：
```powershell
python scripts/start_q1q5_p1.py --bundle $P1_BUNDLE --manifest-sha256 6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7 --state-root "$STATE_PARENT\rec-$([guid]::NewGuid().ToString().Substring(0,8))" --current-ui --no-open --port 8766
```

**段 B：live 追蹤（埠 8765）**：
```powershell
python scripts/start_q1q5_p1.py --bundle $P1_BUNDLE --manifest-sha256 6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7 --state-root "$STATE_PARENT\live-$([guid]::NewGuid().ToString().Substring(0,8))" --tracking-scope configs/q1q5/p1_live_tracking_scope.json --tracking-scope-sha256 e2ca308b13181346707660a1ae4edcd7b8cc594709a3e009c2db0a9fea3374b8 --current-ui --no-open --port 8765
```

**段 C：複雜事件播放（埠 8780）**：
```powershell
node frontend/event-viewer/server.mjs --root $CX7_ROOT --port 8780
```

**開瀏覽器**：
- 監控牆：`http://127.0.0.1:8766/workbench-v2/`
- 預錄切鏡（B-05b）：`http://127.0.0.1:8766/workbench-v2/?recording=2777741d96ac9aff5bffb2f61a4d2938`
- 即時追蹤（B-05a）：`http://127.0.0.1:8765/workbench-v2/`
- 複雜事件：`http://127.0.0.1:8780/`

### 7.3 Windows 跨平台注意事項（源自 W-A1 基準審計）

| 項目 | 說明與處置方案 |
| --- | --- |
| **字元編碼** | 繁體中文 Windows 預設 `cp950` 代碼頁。所有 Python 子行程、檔案讀寫必須顯式指定 `encoding="utf-8"`，或設定環境變數 `PYTHONUTF8=1`，防止 Unicode 解碼崩潰 |
| **磁碟檢查** | Windows 使用 PowerShell `Get-PSDrive` 或 `psutil` 取得磁碟剩餘空間，門檻嚴格維持 ≥ 9 GiB 才啟動、< 8 GiB 拒絕寫入 |
| **埠檢查** | Windows 使用 `netstat -ano` 或 PowerShell `Get-NetTCPConnection` 檢查 8765／8766／8780 是否已被占用 |
| **POSIX `fcntl`** | Windows 不支援 POSIX `fcntl` 模組；歷史檔案鎖相關模組列管審計，不得在新模組中使用 |
| **`os.O_NOFOLLOW`／`os.O_DIRECTORY`** | Windows 原生無此旗標；檔案路徑解析全面採用跨平台 `pathlib.Path.resolve()` 與 `is_relative_to` 進行邊界判定 |
| **NTFS 符號連結** | Windows 非管理者權限建立 symlink 會拋出 `WinError 1314`；測試與建置流程全面採用複製或相對路徑參照，禁止依賴特權 symlink |
| **網路沙盒 Loopback** | Windows 本機沙盒環境下 server 不可跨行程連線；測試須在同一命令鏈中 probe 或在授權環境下執行 |

## 8. UNKNOWN 與要補的東西

| # | 缺什麼 | 影響的步驟 | 狀態 |
| --- | --- | --- | --- |
| 1 | r003 `.blend`、r004 v2 建檔腳本（`build_static_v2.py` 等） | §2.1 建檔 | 待補充 |
| 2 | 鏡頭世界座標、朝向、焦距（mm）、sensor 寬度（LOCAL `cameras.json`） | §2.1 | 待補充 |
| 3 | P1 v4 包與 `dynamic_engineering_v1.json` 的對應 | §2.2 | 待補充 |
| 4 | 擴充 Office 場景的建檔腳本、區域、鏡頭、COCO 物件清單 | §2.3 | Codex 進行中 |
| 5 | D124 重渲染（轉身、正反面）的做法 | §2.1、§4.1 | Codex 進行中 |
| 6 | r004 producer `render_cx7.py` 與渲染指令 | §4.1 | 待補充 |
| 7 | D119 safe bundle 投影 helper | §4.3 | 待補充 |
| 8 | 建圖用的 LOCAL 靜態 provenance | §5.1 | 待補充 |
| 9 | r004 索引 adapter、核定參數集、production decoder | §5.3 | 待補充 |
| 10 | Windows 版依賴檢查與啟動腳本 | §1.2、§7 | **已完成**（`scripts/ensure_env.py` + `start_all_demo.ps1`，W-A1 #419 / PR #440 基準收據 commit `2372767` + PR #443） |
| 11 | Node、uv 的版本；torch CPU／CUDA 選擇 | §1.1 | **Node/uv 已確定**（Node v24.14.1, uv 0.10.0；torch 待核定） |
