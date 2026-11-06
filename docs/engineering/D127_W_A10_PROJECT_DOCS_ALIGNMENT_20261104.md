# D127 W-A10 專案文件包與契約核對對齊收據（2026-11-04）

- **任務來源**：Issue [#428](https://github.com/Polalalabear/amidst/issues/428)（W-A10 文件對齊：#409 專案文件包 ↔ #410 契約 ↔ 實作）
- **依據**：PR [#409](https://github.com/Polalalabear/amidst/pull/409)（D126 專案文件包）、PR [#410](https://github.com/Polalalabear/amidst/pull/410)（核心契約與驗收測試）、PR [#440](https://github.com/Polalalabear/amidst/pull/440) / Issue [#419](https://github.com/Polalalabear/amidst/issues/419)（W-A1 Windows 乾淨 clone 基準報告：code head `def9e1dc4fabf89f86546da4663523728b1d76e9`、receipt commit `2372767`、JSON SHA-256 `223ac914b42da8ecb48d5840560a01d353684d10f4e84f348a955e0b355e764b`，340 core Python + 24 Node + 24 clean clone focused tests PASS）、PR [#443](https://github.com/Polalalabear/amidst/pull/443)（W-C1 核心接線與修復）
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

依據 W-A1（#419 / PR [#440](https://github.com/Polalalabear/amidst/pull/440)）之最新 Windows 11 乾淨 clone 基準收據（code head `def9e1dc4fabf89f86546da4663523728b1d76e9`、receipt commit `2372767`、JSON SHA-256 `223ac914b42da8ecb48d5840560a01d353684d10f4e84f348a955e0b355e764b`；驗證 340 core Python + 24 Node + 24 clean clone focused tests 全數 PASS），以及 PR [#443](https://github.com/Polalalabear/amidst/pull/443) 之 `start_all_demo.ps1`，補齊以下內容：

| 項目 | 原 BUILD_FROM_SCRATCH 狀態 | 對齊後更新內容 | 參照收據 |
| --- | --- | --- | --- |
| **Windows 啟動腳本** | 「repo 裡沒有 Windows 版啟動腳本」 | 補充 `start_all_demo.ps1`（原生 PowerShell 5.1/7+ 支援，含 `-CheckOnly` 唯讀預檢、三段背景作業管理與 Ctrl+C 乾淨關閉） | `start_all_demo.ps1`（PR #443） |
| **Windows 硬體與環境探針** | 「repo 沒有 Windows 實測紀錄」 | 補充 `scripts/ensure_env.py` 的 WinAPI 探針（`GlobalMemoryStatusEx`、`GetLogicalProcessorInformationEx`、`winreg`、`nvidia-smi` + CIM） | `WINDOWS_CLEAN_CLONE_BASELINE_20261104.md` |
| **工具版本實測值** | Node / uv 版本標註 UNKNOWN | 補全 Windows 乾淨 clone 實測值：Python 3.12.0、Node v24.14.1、Git 2.53.0、uv 0.10.0 | 同上 |
| **字元編碼相容** | 未提及 | 寫明繁體中文 Windows 預設 `cp950` 代碼頁問題，規定顯式指定 `encoding="utf-8"` 或環境變數 `PYTHONUTF8=1` | 同上 §3.2 |
| **POSIX 相容性問題** | 未列管 | 建立 `fcntl`、`os.O_NOFOLLOW`/`os.O_DIRECTORY`、NTFS symlink (`WinError 1314`) 與網路沙盒 loopback 邊界指引 | 同上 §3.1 |
| **Windows 驗證指令與啟動邊界** | 僅抄錄 Mac 指令且啟動邊界未界定 | 提供 PowerShell 原生執行指令；明確以 `verify_clean_clone.py`（W-A1）為唯一實測基準通過流程，手動 venv/pip 列為備援參考範例；明確完整 Windows 展示服務啟動由 Issue #429 負責，W-A10 不代驗 | `BUILD_FROM_SCRATCH.md §1.2, §6` |

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
   - `docs/project/` 內 8 份文件間之相對連結（[README](../project/README.md)、[PRD.md](../project/PRD.md) 等）全部解析存在。
   - 所有外部 GitHub PR 與 Issue 參照均使用完整 URL 格式。
4. **Mermaid 實際渲染 Gate 實測驗證（PASS，全 3 圖實際渲染完成）**：
   - 執行環境：Windows 11、Node v24.14.1、`@mermaid-js/mermaid-cli` v12.2.0（以 `npx --offline @mermaid-js/mermaid-cli` 離線執行）、Chromium headless（透過 `docs/project/diagrams/puppeteer-config.json` 指定 `--no-sandbox` 參數）。
   - 驗證方法：提取 `SYSTEM_ARCH.md`（2 張）與 `ROADMAP.md`（1 張）共 3 張 Mermaid 圖表源碼為 `.mmd` 檔案，逐一執行實際渲染輸出向量 `.svg` 與點陣 `.png`，驗證無語法錯誤、進程結束碼全為 0。
   - 渲染執行命令與產出明細：
     1. 圖 1（系統架構總覽，取自 `SYSTEM_ARCH.md`）：
        - 源碼：`docs/project/diagrams/system_arch_overview.mmd`（1,679 bytes，SHA-256 `5aea526858a8699e5f6b5f589b54c2092e3d863ecabd64a1f749be9d6cf0baba`）
        - SVG 渲染命令：`npx --offline @mermaid-js/mermaid-cli -p docs/project/diagrams/puppeteer-config.json -i docs/project/diagrams/system_arch_overview.mmd -o docs/project/diagrams/system_arch_overview.svg`（225,350 bytes，SHA-256 `4af4f4d455025b6944d16105d03c7f0f0d27a64a388148f4f1d6cc70e52493fe`）
        - PNG 渲染命令：`npx --offline @mermaid-js/mermaid-cli -p docs/project/diagrams/puppeteer-config.json -i docs/project/diagrams/system_arch_overview.mmd -o docs/project/diagrams/system_arch_overview.png`（34,323 bytes，SHA-256 `ee92bd2397975afdabd2294d4ed517cd016c661db12a136905b5ebeecb0cceea`）
     2. 圖 2（地點查找兩層圖，取自 `SYSTEM_ARCH.md`）：
        - 源碼：`docs/project/diagrams/system_arch_twolayer_graph.mmd`（758 bytes，SHA-256 `142e6dc87b5a06f4b89a641a3fbaa0dbfdbfa22b570e67d9325db6b6a9a12d7f`）
        - SVG 渲染命令：`npx --offline @mermaid-js/mermaid-cli -p docs/project/diagrams/puppeteer-config.json -i docs/project/diagrams/system_arch_twolayer_graph.mmd -o docs/project/diagrams/system_arch_twolayer_graph.svg`（209,022 bytes，SHA-256 `d03efc9d306db441067b5b8cf0682cdc109316234fbb6aba73d83761c317ee38`）
        - PNG 渲染命令：`npx --offline @mermaid-js/mermaid-cli -p docs/project/diagrams/puppeteer-config.json -i docs/project/diagrams/system_arch_twolayer_graph.mmd -o docs/project/diagrams/system_arch_twolayer_graph.png`（50,936 bytes，SHA-256 `4b9896f9b3cb351e20d8ada294e7a6c72b03f07254dca5b3c38c8385eba62a8f`）
     3. 圖 3（任務流程圖，取自 `ROADMAP.md`）：
        - 源碼：`docs/project/diagrams/roadmap_workflow.mmd`（412 bytes，SHA-256 `8ec7cbab9cdec3816b26e08e926b0b9720feba994b5647e566d61aebc0404366`）
        - SVG 渲染命令：`npx --offline @mermaid-js/mermaid-cli -p docs/project/diagrams/puppeteer-config.json -i docs/project/diagrams/roadmap_workflow.mmd -o docs/project/diagrams/roadmap_workflow.svg`（204,842 bytes，SHA-256 `b81dd11c5b14d50e5b0bcea3f4d41bd1481af155d3ef6f946ddb96c8c4d9041e`）
        - PNG 渲染命令：`npx --offline @mermaid-js/mermaid-cli -p docs/project/diagrams/puppeteer-config.json -i docs/project/diagrams/roadmap_workflow.mmd -o docs/project/diagrams/roadmap_workflow.png`（34,633 bytes，SHA-256 `73ce55e9fcded63e2c6e1cf8804f2bd7e6e550319713e47e82f83001dbd7eba2`）
     4. 渲染配置：`docs/project/diagrams/puppeteer-config.json`（54 bytes，SHA-256 `636310579e058f27124a62f021ad0816305d24d812f3a72712a1be52d2e6040d`）
   - 判定：Mermaid render gate 通過，所有 3 張圖表具備確定性渲染驗證結果與完整檔案歸檔。
5. **安全與 GT 隔離維護**：
   - 零 GT、零 `gt_private/` 存取、零渲染軌跡依賴。
   - 零 API Key、零外部模型依賴。
