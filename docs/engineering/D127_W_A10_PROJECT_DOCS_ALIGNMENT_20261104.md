# D127 W-A10 專案文件包與契約核對對齊收據（2026-11-04）

- **任務來源**：Issue [#428](https://github.com/Polalalabear/amidst/issues/428)（W-A10 文件對齊：#409 專案文件包 ↔ #410 契約 ↔ 實作）
- **依據**：PR [#409](https://github.com/Polalalabear/amidst/pull/409)（D126 專案文件包）、PR [#410](https://github.com/Polalalabear/amidst/pull/410)（核心契約與驗收測試）、PR [#440](https://github.com/Polalalabear/amidst/pull/440)（W-A1 Windows 乾淨 clone 基準報告）、PR [#443](https://github.com/Polalalabear/amidst/pull/443)（W-C1 核心接線與修復）
- **工作分支**：`argon/428-project-docs-alignment`，base：`origin/mainline/q1q5`（`796cc17`）

---

## 1. 差異逐項處理矩陣（#409 ↔ #410 ↔ 實作）

| # | 差異項目 | #409 原文（SPEC / PRD） | #410 契約與實作（#443） | W-A10 對齊處理方案 | 對齊檔案 |
| --- | --- | --- | --- | --- | --- |
| 1 | V1 時間必填 | 前端擋下；錯誤碼 UNKNOWN | 前端擋下；伺服器驗證回 422 `TIME_REQUIRED` | SPEC §1.2 消除 UNKNOWN，補齊 422 代碼與前後端雙重防護說明 | `docs/project/SPEC.md` |
| 2 | V2 地點與特徵至少填一個 | 前端擋下；錯誤碼 UNKNOWN | 前端擋下；伺服器驗證回 422 `LOCATION_OR_FEATURE_REQUIRED` | SPEC §1.2 消除 UNKNOWN，補齊 422 代碼 | `docs/project/SPEC.md` |
| 3 | V3 時間順序與跨午夜 | `TIME_EXPRESSION_INVALID` | 細分為 `TIME_ORDER`、`TIME_CROSSES_MIDNIGHT`、`TIME_INVALID`、`TIME_ZONE_MISMATCH`（HTTP 422） | SPEC §1.2 更新四個細分錯誤代碼，對齊核心查詢純模組 | `docs/project/SPEC.md` |
| 4 | V4 沒有時鐘 | `CLOCK_MAPPING_MISSING` | 一致：`status: UNKNOWN`，reasons 帶 `CLOCK_MAPPING_MISSING`，不猜測日期 | 保持一致，明確標註 status 與 reasons | `docs/project/SPEC.md` |
| 5 | V5 部分涵蓋或超出範圍 | `PARTIAL`／`OUT_OF_RANGE` | 一致：部分無資料回 `PARTIAL`，完全無交集回 `OUT_OF_RANGE` | 保持一致 | `docs/project/SPEC.md` |
| 6 | V6 類別或條件不支援 | 回應狀態 `UNSUPPORTED_CLASS`／`UNSUPPORTED_CONDITION` | 選單驗證失敗回 HTTP 422；另加 `COLOR_UNKNOWN`、`REGION_UNKNOWN` | SPEC §1.2 更新為 HTTP 422 及新增的兩個防護代碼 | `docs/project/SPEC.md` |
| 7 | 只給地點查找 | 回傳涵蓋該區域的鏡頭畫面 | 只算 `covered_regions` 且 basis 為 `MANUAL_ON_STATIC_FRAME` 的鏡頭（且鏡頭存在於 run 目錄），結果標 `target_observed: false` | SPEC §1.3 與 PRD §4.1 更新：明確 basis 要求、run 目錄限制與 `target_observed: false` 標籤 | `docs/project/SPEC.md`、`PRD.md` |
| 8 | 預錄資料的「現在」 | 空著代表現在；待補（看核心契約） | 前端回放時鐘之 `playback_now_us`（非負安全整數）；視窗為 `[now − track_lookback_us, now)`，預設 60 s | SPEC §2.1 與 PRD §4.2 消除待補，明確記載回放時鐘微秒定義與 60 秒視窗 | `docs/project/SPEC.md`、`PRD.md` |
| 9 | 「完全跟丟」條件 | 待補（是否沿用 W/R 輪數 UNKNOWN） | 最後一段觀測結束到 `as_of_us` 為止沒有鏡頭再看到目標，即判定為 `LOST`；不依賴輪數 | SPEC §2.2 消除待補，記錄無鏡頭看見之 `LOST` 語意 | `docs/project/SPEC.md` |
| 10 | 單畫面切鏡依據 | 兩層圖＋D28 候選（Q2 狀態機） | 由連接器觀測到的 sightings 經純函式排出（#410 §3.5、`core_query.single_view_sequence`），不靠圖決定切鏡；圖未核准帶 `GRAPH_NOT_APPROVED` | SPEC §2.3 更新切鏡演算法依據，明確與圖狀態解耦 | `docs/project/SPEC.md` |
| 11 | 盲區信心 | 標 `INFERRED` | 標 `INFERRED`，對外標籤信心一律 `LOW`（或 `UNKNOWN`）；底層數值保留在 `model_confidence` | SPEC §2.4 與 PRD §4.2 補充信心階層定義 | `docs/project/SPEC.md`、`PRD.md` |
| 12 | 核心契約地位與實作狀態 | 標註 UNKNOWN，GitHub 找不到分支 | PR #410 正式提出 PROPOSED 契約，PR #443 完成純模組與 API 接線 | README、PRD、SPEC §8、ROADMAP、GLOSSARY 全面更新狀態與連結 | 全套 8 份文件 |

---

## 2. 跨平台與 Windows 實測指引對齊（源自 #419 / PR #440 與 #443）

依據 W-A1（#419 / PR [#440](https://github.com/Polalalabear/amidst/pull/440)）之 Windows 11 乾淨 clone 實測驗證，以及 PR [#443](https://github.com/Polalalabear/amidst/pull/443) 之 `start_all_demo.ps1`，補齊以下內容：

| 項目 | 原 BUILD_FROM_SCRATCH 狀態 | 對齊後更新內容 | 參照收據 |
| --- | --- | --- | --- |
| **Windows 啟動腳本** | 「repo 裡沒有 Windows 版啟動腳本」 | 補充 `start_all_demo.ps1`（原生 PowerShell 5.1/7+ 支援，含 `-CheckOnly` 唯讀預檢、三段背景作業管理與 Ctrl+C 乾淨關閉） | `start_all_demo.ps1`（PR #443） |
| **Windows 硬體與環境探針** | 「repo 沒有 Windows 實測紀錄」 | 補充 `scripts/ensure_env.py` 的 WinAPI 探針（`GlobalMemoryStatusEx`、`GetLogicalProcessorInformationEx`、`winreg`、`nvidia-smi` + CIM） | `WINDOWS_CLEAN_CLONE_BASELINE_20261104.md` |
| **工具版本實測值** | Node / uv 版本標註 UNKNOWN | 補全 Windows 乾淨 clone 實測值：Python 3.12.0、Node v24.14.1、Git 2.53.0、uv 0.10.0 | 同上 |
| **字元編碼相容** | 未提及 | 寫明繁體中文 Windows 預設 `cp950` 代碼頁問題，規定顯式指定 `encoding="utf-8"` 或環境變數 `PYTHONUTF8=1` | 同上 §3.2 |
| **POSIX 相容性問題** | 未列管 | 建立 `fcntl`、`os.O_NOFOLLOW`/`os.O_DIRECTORY`、NTFS symlink (`WinError 1314`) 與網路沙盒 loopback 邊界指引 | 同上 §3.1 |
| **Windows 驗證指令** | 僅抄錄 Mac 指令 | 提供 PowerShell 原生執行之完整測試指令（含 `verify_clean_clone.py`、`test_clean_clone_baseline.py`、核心契約測試） | `BUILD_FROM_SCRATCH.md §6` |

---

## 3. 架構守門與驗證結果

1. **架構守門（Architecture Guard）**：
   - 執行命令：`python scripts/check_architecture_guard.py --repo . --base origin/mainline/q1q5`（**無** `--allow`）
   - 結果：`status: PASS`
   - Authority: 0 findings (checked 23 files)
   - Inference: 0 findings (scanned 141 files)
   - Schemas: 0 findings (literal occurrences verified)
2. **排版與 whitespace 守門**：
   - 執行命令：`git diff --check origin/mainline/q1q5...HEAD`
   - 結果：0 findings（無輸出，通過）
3. **相對連結與文件交叉參照**：
   - `docs/project/` 內 8 份文件間之相對連結（`[README](README.md)`、`[PRD.md](PRD.md)` 等）全部解析存在。
   - 所有外部 GitHub PR 與 Issue 參照均使用完整 URL 格式。
4. **Mermaid 語法驗證**：
   - `SYSTEM_ARCH.md`（flowchart LR 架構圖、flowchart TB 兩層圖）
   - `ROADMAP.md`（flowchart LR 任務流）
   - 全部語法經標準 Mermaid 節點與引號檢查，無標籤語法錯誤。
5. **安全與 GT 隔離維護**：
   - 零 GT、零 `gt_private/` 存取、零渲染軌跡依賴。
   - 零 API Key、零外部模型依賴。
