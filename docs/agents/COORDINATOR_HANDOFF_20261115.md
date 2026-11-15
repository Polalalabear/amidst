# 協調者交接 2026-11-15

前一位協調者是 Claude Opus 5.5，從 `HANDOFF_COORDINATOR_20261110_B.md` 接手。下一個決策編號是 **D220**，要同步到 [#93](https://github.com/Polalalabear/amidst/issues/93)。

## 1. 現況與 SHA

| 項目 | 值 |
|---|---|
| 主線 | `main` @ `fe7b9d55`（GitHub 預設分支，D214）；`mainline/q1q5` 凍結在 `8c741451` |
| 本機 `~/amidst` | 分支 `main`、HEAD `74b84463`、工作樹乾淨，也就是 8785 demo pin（`local/demo-pin.json`） |
| 8785 | 仍鎖在 `74b84463`。更新到 `fe7b9d55` 被 core-e2e 擋住（見 §4-2） |
| 磁碟 | 約 11 GiB 可用。session 剩 5 GiB 就停，程式內建保護在 8 GiB |
| 遠端分支 | 40 條（11-15）。清理狀況見 §5 |
| Codex | 工作區已改為 `/Users/polalabear/amidst`（11-15 Codex 確認：實體目錄、`main`、`74b84463`、乾淨）；只在 scratchpad clone 寫檔 |

## 2. 先讀

1. `CLAUDE.md`、`AGENTS.md`、`CLAUDE.local.md`（本機規則：協調者只派工，不在 `~/amidst` 改檔）
2. 本文件
3. [#93](https://github.com/Polalalabear/amidst/issues/93) 的 D200–D219（主線 main、單分支一功能 D216、D210 新方向）
4. `docs/operations/LOCAL_FOLDER_FINALIZE_20261115.md`（本機資料夾定案）
5. 需要時再讀：`docs/contracts/DP4_ATTENTION_RANKING_V1.md`、`docs/contracts/NL_QUERY_PARSE_V1.md`、`docs/contracts/R004_V2_4ACTOR_PRODUCTION_GATES_V1.md`

## 3. 流程

- 每個任務都開新 session；模型照 `CLAUDE.md` 的表：雜務 Haiku low；程式、前端、審查、量測 Sonnet medium（難的用 high）；設計、文件、決策 Opus。
- 寫檔：`git clone --shared --no-checkout ~/amidst <scratch>/clone`，origin 設 GitHub，用完刪。同時最多 3 個寫檔 session，檔案不重疊。純審查用 `gh pr diff`，不 clone。
- 一條功能線一個 `claude/feat-<線>` 分支、一個 PR（D216），後續修正都 commit 在同一條。
- PR base 一律是 `main`，CI `checks` 要綠，只用 merge commit。**合併、刪分支、刪檔、kill 都由使用者在終端執行**（auto 模式會擋轉述的授權）；給指令要帶 `--repo Polalalabear/amidst`。
- Codex 和 Argon（Antigravity 的工具）的 PR：審查，有問題就直接修。Codex 的成果先給使用者看畫面再採用。
- 付費 API 一律經過 `ApiGuard`（#537）；先 dry-run，使用者核准金額才實跑。不讀 API key。
- 被 session 事件喚醒的回合不能開 session，改用提案卡。
- 決策寫到 #93，清理寫到 #486，報告素材寫到 #479。

## 4. 未完成工作（依優先序）

1. **待合併**（使用者執行）：
   - [#537](https://github.com/Polalalabear/amidst/pull/537) API 預算護欄：審查通過。殘留 P2 #5：`OpenAIProvider` 繞過護欄，DP4 和 WP5 實跑前要接上護欄。
   - [#538](https://github.com/Polalalabear/amidst/pull/538) WP5 比較 harness、Colab L4、dry-run：CI 綠，**尚未正式審查**（已有提案卡 rv-538-wp5，Sonnet medium）。
2. **8785 更新準備**（未完成）：在 `fe7b9d55` 上，unit（2574 passed）、dependency、HTTP 200 都通過；core-e2e **失敗**，check 91「D139 multi view: active tile keeps a loaded image while playing」和 check 84 失敗，原因未查。real-e2e 900/1300 未跑，截圖和 `UPDATE_PLAN.md` 也未做。A4-1-8CAM 和 B4-1-8CAM 兩個 run 沒出現在 run 清單裡。另有 `scripts/local/env_templates.sh build` 的 relocate `grep` 無匹配時 exit 1 的 bug。紀錄：LOCAL `local/evidence/demo-update-prep-20261115/gate-out-rerun/`，以及 [#486 留言](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6890067952)。**下一步**：Sonnet medium 查修 core-e2e，在 `claude/feat-workbench-8cam` 這條線上，PR 開新的，因為舊 PR 已合併。pin 要使用者核准。
3. **即時模式 spike**（部分完成）：分支 `claude/feat-live-mode` @ `0fe62c29`，未開 PR。含 three.js 操作端和系統端兩個視窗（`frontend/live-mode/`）及後端 `src/amidst/live_mode/`。偵測：膠囊人形在 320×180 下只有 16.7%。MPS 延遲矩陣已跑完，5 組設定，檔案在 LOCAL `local/evidence/live-mode-spike-20261115/lat/*.latency.json`，**尚未解讀**。初步看 3 鏡頭在 5 fps 下跟不上（顯示 95–114 tick，丟 140–156 tick）。**還要做**：讀 p50/p95、first-lock、switch，跑 CPU 對照，截並排圖，寫報告，開 Draft PR。外觀要等 Codex N6。
4. **Codex N6**：[#539](https://github.com/Polalalabear/amidst/pull/539) Draft，含人物骨架、走/跑/待機動畫、烘焙光照的場景，CI 通過。要審查，給使用者看外觀，然後整合進即時模式。
5. **Argon N3**（[#532](https://github.com/Polalalabear/amidst/issues/532)）：DP4 的 API／Agent 版本，要經過 #537 護欄（用法已貼在 #532）。等 Argon 開 PR 後審查，20 個 xfail 閘門在 `tests/q1q5/test_dp4_attention_gates.py`。
6. **模型分析**：#537 和 #538 合併後重新打包 Windows/Colab 資料包，跑本機模型（L4，D175）；OpenAI pilot 要使用者核准金額（USD 100 分階段，D165/D166）。
7. 之後：Spotlight「追蹤」接 DP4 和即時模式；ENTRY 鏡頭加進 graph；第 5 章補 WP5 數字和 Argon 全名（`docs/report/CH5_CONCLUSION_DRAFT.md`）；研究計畫更新延後。

## 5. 專案整理狀態（[#486](https://github.com/Polalalabear/amidst/issues/486)）

- 本機：home 只剩 `~/amidst`。11-15 刪了 6 個過時媒體資料夾，約 2.1 GiB（[#486 留言](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6889929146)）。B 組保留：`evidence/r004-cx7-d115-*` 2.1 GiB，舊 event-viewer 用；`q1q5-dynamic-baseline`；`p1-clean-room` 等。
- `~/Developer` 三個舊 symlink（`amidst` → office-canonical、`amidst-claude`、`amidst-q1q5`）：Codex 已換資料夾，可以刪了，指令在 `LOCAL_FOLDER_FINALIZE_20261115.md` (c)。
- 已合併、可刪的遠端分支（11-15 盤點，全部是 main 的祖先）：`argon/511-agent-wp3`、`argon/515-eval-toolchain`、`claude/445-demo-integration`、`claude/d211-gate-516-8cam`、`claude/d212-wb-8cam-grid`、`claude/d214-dp4-contract`、`claude/d214-wb-8cam-data`、`claude/feat-nl-search`、`claude/feat-ops-cleanup`、`claude/feat-workbench-8cam`、`claude/ui-redesign-v1`、`codex/486-vendor-deps`、`codex/516-eight-camera-completion`、`codex/d139-class-counts`、`codex/d147-d149-backend`。
- 保留：`archive/*`；關閉未合併的證據分支（argon/424、425、426、429，codex/445-independent-previews、467、516-four-actor-delivery、516-natural-walk-sample）；開著的 PR 分支；`claude/feat-live-mode`。
- [#445](https://github.com/Polalalabear/amidst/issues/445) 已於 11-15 關閉（Demo A 已驗收）。

## 6. 第一個任務

1. 確認使用者已執行 §5 的刪除，然後在 #486 結案或留下剩餘項目。
2. 開 Sonnet medium session 查修 8785 core-e2e（§4-2），同時讓使用者決定 #537 和 #538 的合併。
