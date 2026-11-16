> 已由 [COORDINATOR_HANDOFF_20261116.md](COORDINATOR_HANDOFF_20261116.md) 取代。

# 協調者交接 2026-11-15

前一位協調者是 Claude Opus 5.5，從 `HANDOFF_COORDINATOR_20261110_B.md` 接手。下一個決策編號是 **D220**，要同步到 [#93](https://github.com/Polalalabear/amidst/issues/93)。

## 2026-11-16 更新

以這一節為準。§1–§6 是 2026-11-15 交接時的原文，保留作為紀錄。問題和解法的完整清單在 `docs/operations/ISSUES_AND_FIXES_20261115.md`。

| 項目 | 值 |
|---|---|
| 主線 | `main` @ `8b023775`（#545 的 merge） |
| 8785 | pin `b24d6a26`（tree `ca6d0687`）。使用者 11-15 照 #545 的步驟更新，閘門全過（D234、D235）。舊 pin 備份在 LOCAL `local/demo-pin.74b84463.bak.json` |
| 下一個決策編號 | **D239**（D220–D238 在 [#93](https://github.com/Polalalabear/amidst/issues/93)） |

**已合併**（都由使用者執行，merge commit）：

| PR | 內容 | merge |
|---|---|---|
| [#537](https://github.com/Polalalabear/amidst/pull/537) | API 預算護欄 `ApiGuard` | `57dd761b` |
| [#538](https://github.com/Polalalabear/amidst/pull/538) | WP5 比較 harness，修好 OpenAI 繞過護欄的問題 | `18715e69` |
| [#539](https://github.com/Polalalabear/amidst/pull/539) | Codex N6 人物和烘焙場景 | `1aea09cd` |
| [#540](https://github.com/Polalalabear/amidst/pull/540) | 本交接文件 | `52b3ab2b` |
| [#541](https://github.com/Polalalabear/amidst/pull/541) | Argon N3：DP4 API／Agent 排序器（#532 已關閉） | `80f36220` |
| [#542](https://github.com/Polalalabear/amidst/pull/542) | core-e2e check 91 修正、`env_templates.sh` grep | `b24d6a26` |
| [#543](https://github.com/Polalalabear/amidst/pull/543) | WP5 Colab L4 和 Windows 資料包 | `4972f0f9` |
| [#545](https://github.com/Polalalabear/amidst/pull/545) | 8785 更新計畫，launcher 加 `--root-8cam` | `8b023775` |

**開著的 PR**：

- [#544](https://github.com/Polalalabear/amidst/pull/544)（Draft，`claude/feat-live-mode`）：即時模式 spike 報告和 N6 整合。可用設定是 3 鏡頭×2 fps（p50 約 240 ms）或 2 鏡頭×3 fps（p50 約 160 ms）；N6×烘焙場景的偵測率 69.1%。
- [#546](https://github.com/Polalalabear/amidst/pull/546)（`claude/feat-wp5`）：WP5 Colab DP1/DP3 修正（Colab v2 已驗證），加上 OpenAI 試跑校準 `f1ebdded`（實際花費 USD 0.1025）。D238：可以合併。session `wp5-calib-finish` 還在這條分支上收尾。
- [#547](https://github.com/Polalalabear/amidst/pull/547)（Draft，`claude/feat-live-llm-decision`）：即時模式的 LLM 決策設計 v1，使用者自己開的。

**§4 未完成工作（現況，依優先序）**：

1. **WP5 收尾**（進行中，session `wp5-calib-finish`）：降低 Colab v2 的 `INVALID_RESPONSE`（qwen 17–21%、llama 63–71%），修 `ollama ps` 的抓取時機（GPU 還沒證實）和 NL rule_agree 0/24 的指標，重產一鍵筆記本 v3；補完 OpenAI 校準報告。完成後由使用者合併 #546。
2. **待使用者決定**：OpenAI 正式額度（A USD 4／B USD 12／C USD 46）和 formal 2 s 逾時要不要放寬；真人模型對照實驗（D236）；8785 新 UI 要不要加 8CAM run（D234）；#547 的設計方向。
3. **即時模式**：#544 還是 Draft。CAM_ENTRY（19%）、R101_IN（47%）偵測率偏低。Codex 的偵測器加速和偵測改進，等真人模型的決定之後再寫指派（D230、D236）。
4. **延後**：N6 天花板亮度和接縫（D227）；`start_all_demo.ps1` 同步 `--root-8cam` 和 `.command` 的啟動時間註解（D234）；下次更新 8785 pin 時帶上 #543、#545。
5. **WP5 DP4 實跑**：runner 的 DP4 即時呼叫還是預留掛點（`DP4_LIVE_NOT_WIRED`，用 `--skip-types DP4`）。#541 的排序器已經合併，接上 runner 的工作還沒派。
6. 之後：Spotlight「追蹤」接 DP4 和即時模式；ENTRY 鏡頭加進 graph；第 5 章補 WP5 數字（`docs/report/CH5_CONCLUSION_DRAFT.md`）。
7. **流程教訓**（第 15、16 條）：長任務要分段 commit、分段 push；demo 和延遲量測期間不同時跑閘門，量測要記錄 load1。

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

> 這是 2026-11-15 的原文。現況見最上面的〈2026-11-16 更新〉。

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
