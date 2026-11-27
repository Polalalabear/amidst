# 文件與整理線交接（2026-11-27）

快照時間：2026-11-27 晚上（+08:00），main = 本 PR 合併後的 commit（見 #674 最新一則）。8785 pin = `5727fc9a`。下一個決策號：查 #93 最新留言（本文寫成時是 **D410**）。

- 交接方：D407 文件整理對話（Claude Opus 5.5），它和 E6 協調對話（`local_2a4a26d2-946e-4a1f-90fd-eb1cba1c5103`）同一層，**只負責文件與整理**。E6 的執行、結果數字與回填由 E6 協調對話做。
- 新對話**全程用繁體中文**（D255）。

## 0. 先讀

1. 本文件。
2. **[`docs/index/CLEANUP_LEDGER.md`](../index/CLEANUP_LEDGER.md)**：整理總帳（D409）。做過什麼、東西搬到哪、還有什麼要做，都在這一份，不要重新翻。
3. #93 的 D407–D409 留言。
4. `CLAUDE.md`、`AGENTS.md`、`CLAUDE.local.md`；現行協調交接是 `docs/agents/COORDINATOR_HANDOFF_20261127b.md`。

## 1. 規則（本線特有）

- **整理總帳是唯一紀錄（D409）**：每做一件整理（盤點、刪除、搬移、更新、新增），就在總帳 §2 加一列；搬移或刪除了路徑，同時更新 §1 對照表；盤點結果寫進 §3。不另開 SWEEP 檔或盤點檔。
- **先設計再動手**：先寫出要改哪些檔、結構、會影響哪些引用。搬移和刪除的計畫要先經使用者核准（用選項卡，推薦的放第一個）；刪除另需使用者明確同意，並由使用者在自己的終端機執行。
- `~/amidst` 是 8785 釘住的資料夾：不改檔、不切分支、不 commit、不 fetch。寫檔一律在 scratchpad 的 `git clone --shared --no-checkout ~/amidst` 裡做，用完就刪。
- E6 執行中的檔案不動：`scripts/experiments/run_all.sh`、`scripts/evaluation/e6_*`、`configs/evaluation/e6_*`、`src/amidst/evaluation/e6_verdict.py`、`src/amidst/live_mode/aopen/`、`docs/evaluation/E6_*`、`docs/operations/EXP_RUN_732_20261127.md`。E7 的 notebook 與 `src/amidst/evaluation/e7_*` 也不動（使用者正在 Colab 用固定 pin）。
- 改到 `AGENTS.md`、`CLAUDE.md`、`Q1Q5_PROGRESS.md` 或其他有 pin 的檔時，要在 `configs/architecture/authority_pins_v1.json` 登記 pin 和 `authorized_changes`（照 `D407-DOCS-*` 的做法），並確認 `check_architecture_guard.py` 是 PASS。
- 每個 PR：CI 綠燈＋Sonnet 子代理審查通過，就用 `--match-head-commit` 和 `--merge --delete-branch` 合併（D305）。每個節點都追加到 #674。

## 2. 工作清單（依類型）

| 類型 | 工作 | 預計產出 | 目前進度 | 卡在哪 |
| --- | --- | --- | --- | --- |
| 研究紀錄 | E6 結果紀錄骨架 | `E6_EXECUTION_RECORD_V1.md` 第二部、`EXP_RUN_732_20261127.md` §5 | [#754](https://github.com/Polalalabear/amidst/pull/754) Draft，偏離 X1–X11 已寫，數字欄位是 `UNKNOWN（待 2d）` | 等 E6 跑完；**由 E6 協調對話回填、合併**，本線不填數字 |
| 研究紀錄 | E6 結果出來後的文件同步 | PROGRESS、#93 列、CODE_DOC_MAP（如有新檔） | 未開始 | 等 #754 合併 |
| 研究紀錄 | E7 分析設計 | 要看的指標、和 E6 的對照方式（先給使用者看設計） | 未開始 | 等使用者在 Colab 跑完 E7（#727） |
| 報告 | #734 的數字核對、引用與來源檢查 | 核對紀錄（主要寫作由 Neon 負責） | 未開始 | 等 E6 數字 |
| 流程與整理 | **全專案大整理** | 照總帳 §3.6：GitHub issue 與標籤 → 分支 → `local/` → 文件分批搬移 → 收尾 | 盤點已完成（總帳 §3，D409） | **等大工作完成**（E6 結果、E7、報告；D408 第 6 點） |
| 流程與整理 | D394 後續、`c37a0cc4` | 見總帳 §4 | 未開始 | 併進大整理處理 |
| 8785 demo | — | — | pin `5727fc9a`，沒有待辦 | — |
| 即時模式／Agent 決策 | #675（LIVE Agent 預設設定） | 依 E6 最佳組設定 | 未開始 | 等 E6 選組；屬主線，由 E6 協調對話決定誰做 |
| 重現包 | #733、#728、#740 | — | D407 延後 | — |

## 3. 本段已完成（細節在總帳 §2）

- #755 `84dbbc44`：交接指向、PROGRESS 補到 #755、CODE_DOC_MAP 加 E6／E7。
- #757 `ba7f74f6`（D408）：舊交接合併後刪除、Office 文件與截圖搬移、索引拆成現行和非現行兩份。
- #93 本文同步；`real-e2e.mjs` 列關閉。
- 已關閉 issue 上的狀態標籤清乾淨（共 89 個）。
- 本 PR（D409）：總帳 `CLEANUP_LEDGER.md`、本交接文件、AGENTS.md 加總帳連結。

## 4. Session

- 子 session `d408-folder-cleanup`（`local_09ee954c-01fc-47f9-8df7-e0329feaf78f`）：已完成（#757），可以封存。
- E6 協調對話：`local_2a4a26d2-946e-4a1f-90fd-eb1cba1c5103`（同一層；它跑完會在 #754 回填）。
