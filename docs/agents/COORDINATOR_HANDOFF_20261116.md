# 協調者交接 2026-11-16

> 已被 [`COORDINATOR_HANDOFF_20261117.md`](COORDINATOR_HANDOFF_20261117.md)（11-17 版）取代；本檔保留作為紀錄。

這份文件是新協調者對話的入口，取代 `COORDINATOR_HANDOFF_20261115.md`（舊檔保留作為紀錄）。前一位協調者是 Claude Opus 5.5。下一個決策編號是 **D242**，要同步到 [#93](https://github.com/Polalalabear/amidst/issues/93)。

- Model / effort：Opus 5.5 / medium（交接文件 session `ops-handoff-1116`）。
- 核對方式：下面每個 SHA 和狀態都在 2026-11-16 用 `gh pr view`、`gh issue view`、`gh api`、`git log` 逐條查過；查不到的寫 `UNKNOWN`。和協調者轉述不一致的地方在文中用「**核對**」標出。

## 1. 現況與 SHA

| 項目 | 值 |
|---|---|
| 主線 | `main` @ `1fe6e716`（[#549](https://github.com/Polalalabear/amidst/pull/549) 的 merge）。`mainline/q1q5` 凍結在 `8c741451` |
| 本機 `~/amidst` | 8785 demo 的資料夾。分支 `main`、HEAD `b24d6a26`，工作樹乾淨（`git status --porcelain` 0 行） |
| 8785 | `local/demo-pin.json` 鎖在 `b24d6a26`（2026-11-15，使用者核准；閘門 `local/evidence/demo-update-prep-20261115/gate-20261115-1829/RESULT.txt`；D234、D235）。**不要在 `~/amidst` 改檔、切分支或 commit** |
| 磁碟 | 約 13 GiB 可用（`df -h ~`，2026-11-16）。session 剩 5 GiB 就停，程式內建保護在 8 GiB |
| 下一個決策編號 | **D242**（D241 是即時模式線的現況紀錄，[#93 留言](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6916303608)） |
| Codex | 目前沒有派工 |

**11-15～16 合併的 PR**（都由使用者執行，merge commit）：

| PR | 內容 | merge |
|---|---|---|
| [#537](https://github.com/Polalalabear/amidst/pull/537) | 付費 API 預算護欄 `ApiGuard` | `57dd761b` |
| [#538](https://github.com/Polalalabear/amidst/pull/538) | WP5 比較 harness（DP1/DP3/DP4/NL）、Colab L4、dry-run | `18715e69` |
| [#539](https://github.com/Polalalabear/amidst/pull/539) | Codex N6 人物和烘焙場景（#516） | `1aea09cd` |
| [#540](https://github.com/Polalalabear/amidst/pull/540) | 協調者交接 2026-11-15 | `52b3ab2b` |
| [#541](https://github.com/Polalalabear/amidst/pull/541) | Argon N3：DP4 API／Agent 排序器（#532） | `80f36220` |
| [#542](https://github.com/Polalalabear/amidst/pull/542) | core-e2e check 91 修正、`env_templates.sh` grep（= 8785 pin） | `b24d6a26` |
| [#543](https://github.com/Polalalabear/amidst/pull/543) | WP5 Colab L4 和 Windows 本機模型包 | `4972f0f9` |
| [#545](https://github.com/Polalalabear/amidst/pull/545) | 8785 更新計畫、launcher 加 `--root-8cam` | `8b023775` |
| [#548](https://github.com/Polalalabear/amidst/pull/548) | 進度導覽補到 #548（D239） | `17a480a6` |
| [#549](https://github.com/Polalalabear/amidst/pull/549) | 問題與解法紀錄 11-15～16、11-15 交接的更新節 | `1fe6e716` |

**關閉的 issue**：[#486](https://github.com/Polalalabear/amidst/issues/486)（大掃除，11-15）、[#532](https://github.com/Polalalabear/amidst/issues/532)（N3 DP4，11-15）、[#516](https://github.com/Polalalabear/amidst/issues/516)（4 人場景產製，11-16）。

## 2. 先讀

1. `CLAUDE.md`、`AGENTS.md`、`CLAUDE.local.md`（本機規則：協調者只派工，不在 `~/amidst` 改檔）
2. 本文件
3. [#93](https://github.com/Polalalabear/amidst/issues/93) 的 D220–D241，以及 D241 前面三則還沒編號的即時模式留言（[6909798873](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6909798873)、[6910613701](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6910613701)、[6911702981](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6911702981)，第三則更正第二則）
4. `docs/operations/ISSUES_AND_FIXES_20261115.md`（11-15～16 的 16 個問題和解法）
5. 即時模式線：`docs/operations/LIVE_MODE_HANDOFF_20261116.md`（在 #544 分支 `claude/feat-live-mode` @ `ce948e59`，還沒進 main）
6. WP5：`docs/evaluation/WP5_OPENAI_CALIBRATION_20261115.md`（在 #546 分支 `claude/feat-wp5` @ `297e03e2`，還沒進 main）

## 3. 流程

沿用 11-15 版 §3：

- 每個任務都開新 session；模型照 `CLAUDE.md` 的表：雜務 Haiku low；程式、前端、審查、量測 Sonnet medium（難的用 high）；設計、文件、決策 Opus。
- 寫檔：`git clone --shared --no-checkout ~/amidst <scratch>/clone`，origin 設 `https://github.com/Polalalabear/amidst.git`，用完刪。同時最多 3 個寫檔 session，檔案不重疊。純審查用 `gh pr diff`，不 clone。
- 一條功能線一個 `claude/feat-<線>` 分支、一個 PR（D216），後續修正都 commit 在同一條。
- PR base 一律是 `main`，CI `checks` 要綠，只用 merge commit。**合併、刪分支、刪檔、kill 都由使用者在終端執行**（auto 模式會擋轉述的授權）；給指令要帶 `--repo Polalalabear/amidst`。
- Codex 和 Argon 的 PR：審查，有問題就直接修。Codex 的成果先給使用者看畫面再採用。
- 付費 API 一律經過 `ApiGuard`（#537）；先 dry-run，使用者核准金額才實跑。不讀 API key。
- 被 session 事件喚醒的回合不能開 session，改用提案卡。
- 決策寫到 #93，報告素材寫到 #479。（#486 已關閉。）

11-16 新增：

- **同一條分支同時只能有一個寫手。** 11-16 有兩個 session 先後推上 #546（`claude/feat-wp5`），審查過的 head 因此過時、要重審（D240）。派工前先查 `list_sessions {"linked": true}`，同分支有 session 在跑就等它結束。
- **長任務要分段 commit、分段 push。** 11-15 有兩個 session 用完 5 小時額度，進度沒推上去（`ISSUES_AND_FIXES_20261115.md`）。brief 裡寫明每完成一段就 commit 並 push。

## 4. 開著的 PR（CI `checks` 都綠，2026-11-16 查）

- **[#546](https://github.com/Polalalabear/amidst/pull/546)** `claude/feat-wp5` @ `297e03e2`（非 Draft）：WP5 Colab DP1/DP3 修正、OpenAI 校準、一鍵筆記本 v3。上次審查（APPROVE，head `fae92353`，D236）之後又加了 5 個 commit 和 1 個 merge：`f1ebdded`、`abcb18d0`、`e58ee033`、`4ec00d46`、`05a9e547`、merge `297e03e2`，要重新審查（D240 說提案卡 rv-546-v3 已放上；卡片現況這個 session 無法查，`UNKNOWN`）。使用者還要用 v3 在 Colab 重跑。兩邊都過才合併（D236、D240）。
- **[#544](https://github.com/Polalalabear/amidst/pull/544)** `claude/feat-live-mode` @ `ce948e59`（Draft）：即時模式的程式、量測、報告、Colab 包、交接文件。**還沒正式審查**；`tracker.py`、`people.py`、`advisor.py` 改了追蹤行為，照 `CLAUDE.md` 屬於複雜程式碼。
- **[#547](https://github.com/Polalalabear/amidst/pull/547)** `claude/feat-live-llm-decision` @ `77f64e6e`（Draft）：即時模式 LLM 決策設計稿 `docs/design/LIVE_MODE_LLM_DECISION_V1.md`，§0F 是問題和決定的總表。上一版 `34683b9c` 審查 NEEDS_CHANGES（P1 3、P2 7，[審查留言](https://github.com/Polalalabear/amidst/pull/547#issuecomment-6900140128)）。之後加了 6 個 commit（`ab47a9ba` … `77f64e6e`）；#544 的交接文件說「已經回覆並修改，沒有複審」，所以 P1/P2 是否都處理了要再審。

## 5. 即時模式線現況（D241，已用 #544 核對）

來源：#544 的 `docs/operations/LIVE_MODE_HANDOFF_20261116.md`、`docs/evaluation/LIVE_MODE_TRACKER_20261116.md`、`docs/evaluation/LIVE_MODE_SPIKE_20261115.md` §10；#547 §0F。

**已完成**：

- 操作端用 WASD 操作，後台只看 8 個虛擬鏡頭的像素做偵測與追蹤；人物和場景已換成 N6 素材。
- 影像裁決（兩個以上候選人時把畫面送 OpenAI 判斷）已接進後台，預設關閉，預設模型 sol6.1（`gpt-6.1-sol`；使用者 11-16 決定，只在即時模式範圍取代 D237 的 terra）。
- 關聯範圍預設 3 m → 4 m：20 次實跑跟對 0.47 → 0.65；重播 0.51 → 0.63。
- 實跑記錄、評分、重播測試工具都有了。
- Colab 測試包使用者已在 L4 跑完。
- 單元測試：pytest `tests/live_mode` 29 項通過，node 測試 13 項通過（2026-11-16，交接文件 §9）。

**只有設計稿**（`docs/design/LIVE_MODE_GAME_DESIGN_V1.md`、`V2.md` §8）：越肩鏡頭、動畫混合、HUD 四項、小地圖、B 畫面跟隨視角、後台紀錄。

**未解決**（依重要程度）：

1. **4 m 加上正確的裁決後，A4 路線反而變差**：重播 A4 路線鏡頭跟對 0.41 → 0.32，回答越快越差，原因不明。**這條線的第一件事**，不花錢，全用重播（交接文件 §8 有指令和驗收條件）。
2. 影像裁決沒有證明能讓追蹤變好：放寬到 4 m 就有同樣效果，兩者疊加沒有更好。
3. A4 室外鏡頭偵測率低：N6 × 烘焙場景整體 69.1%，CAM_ENTRY 19%、R101_IN 47%、EXT_CAR 67%（`LIVE_MODE_SPIKE_20261115.md` §10）。
4. 程式沒有經過正式審查。
5. 其他（交接文件 §6）：8 鏡頭全推論每秒不到 1 輪；參數只在 A4/B4 調過；追蹤編號每 100 次觀測約對調 1.3 次；後台從標明 `must_not_enter: RUNTIME_INFERENCE` 的 `R004_SCENE_GEOMETRY_2D_V1.json` 讀攝影機參數，要改讀攝影機 catalog。

**延遲**：可用設定是 3 鏡頭 × 2 fps（p50 約 240 ms）、2 鏡頭 × 3 fps（p50 約 160 ms）（`LIVE_MODE_SPIKE_20261115.md` §10）。

## 6. 預算

| 用途 | 核准上限 | 實際花費 | 出處 |
|---|---:|---:|---|
| WP5 OpenAI 試跑校準 | USD 3 | 0.113（帳本上界 0.1465） | `WP5_OPENAI_CALIBRATION_20261115.md`、D240 |
| 即時模式：單題影像裁決測試 | USD 4 | 0.88 | #544 交接文件 §5 |
| 即時模式：第一輪實跑 | USD 1 | 0.12 | 同上 |
| 即時模式：第二輪實跑 | USD 0.5 | 0.07 | 同上 |
| **合計** | | **約 1.18** | |

- **核對**：D241 寫「合計約 USD 1.07（WP5 校準 0.113＋即時模式線）」。#544 的帳本表顯示 **即時模式線自己就是 1.07**，加上 WP5 的 0.113，合計約 **USD 1.18**。新協調者要在 #93 用 D242 更正這個數字。花費是回應 token 數乘 D237 價目算的，不是 OpenAI 帳單。
- 先前核准的額度不能沿用；任何新的付費呼叫都要使用者在對話裡重新核准金額。
- 待使用者決定的額度：WP5 方案 **A terra USD 4（建議）**／B 混合 USD 12／C 三個模型 USD 46（D240）；#547 的 T2 約 USD 1.7（金額出自協調者轉述，在 #547 @ `77f64e6e` 找不到這個數字，`UNKNOWN`；另外 #547 §0F.4 說 T2 的單題延遲已經在 §0D 量過，即上表 USD 0.88 那一項，T2 還要不要另外花錢要先確認）。
- 預設模型 terra（D237）；即時模式的影像裁決用 sol6.1。要不要統一由使用者決定。

## 7. 等使用者決定

1. #546：重新審查和 Colab v3 都過之後合併。
2. OpenAI 額度（§6）。
3. formal 的 2 s 逾時要不要放寬（所有模型延遲中位數約 2.7–4.7 s，D240）。
4. #547 的決策點（D240 交給使用者的 4 個）：先不接進 demo 預設、預設用「LLM 覆核」、先做不花錢的備援方案、T2 另外核准。**核對**：#547 §0F.3 和 #544 交接文件 §5 都記錄使用者 2026-11-16 已決定「B 畫面的 demo 預設用 LLM 覆核，LLM 主導做成可切換」，所以實際還待決定的是其餘 3 點。
5. 真人模型對照實驗（D236）。
6. 8785 新 UI 要不要加 8CAM run（D234）。
7. N6 天花板亮度和接縫（D227）。

## 8. 之後要做

- 8785 下次更新時，一起帶上 #543、#545 的 launcher 修改，以及兩項 P2：`start_all_demo.ps1` 同步 `--root-8cam`、`.command` 的啟動時間註解（D234）。pin 要使用者核准。
- 第 5 章補 WP5 數字（`docs/report/CH5_CONCLUSION_DRAFT.md`）。
- 把 #93 上三則即時模式留言的使用者決定編成 D 號（交接文件 §5 請協調者編）。
- WP5 DP4 實跑：runner 的 DP4 呼叫還是預留掛點（`DP4_LIVE_NOT_WIRED`），接上的工作還沒派（11-15 交接更新節 §4-5）。
- Codex 目前沒有派工。

## 9. 第一個任務（建議）

1. 確認 #546 的重新審查（Sonnet medium）和使用者的 Colab v3 結果，兩邊都過就請使用者合併。
2. 派 Sonnet medium 正式審查 #544（diff、`tests/live_mode`、`git diff --check`、merge-tree）；複雜程式碼部分由 Opus 判定被標出的點。
3. 派 Sonnet high 查「4 m 加裁決後 A4 變差」（在 `claude/feat-live-mode` 上；和 #544 審查的修改不能同時寫同一條分支，見 §3）。
4. 讓使用者一次決定第 7 節的額度、逾時和 #547 的其餘 3 點；同時用 D242 更正花費合計。
