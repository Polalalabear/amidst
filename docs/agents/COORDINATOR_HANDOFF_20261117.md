# 協調者交接 2026-11-17

這份文件是新協調者對話的入口，取代 `COORDINATOR_HANDOFF_20261116.md`（舊檔保留作為紀錄）。前一位協調者是 Claude Opus 5.5（2026-11-16～17）。**新的協調者對話全程用繁體中文回覆**（D255、`CLAUDE.md`「Handoff」）。下一個決策編號是 **D257**，要同步到 [#93](https://github.com/Polalalabear/amidst/issues/93)。

- Model / effort：Opus 5.5 / medium（交接文件 session `ops-handoff-1117`）。
- 核對方式：下面每個 SHA 和狀態都在 2026-11-17 用 `gh pr view`、`gh pr list`、`gh pr checks`、`gh issue view`、`gh issue list`、`gh api`（#93 留言、分支列表、refs）重新查過；本機只讀了 `~/amidst` 的 HEAD、`git status` 和 `local/demo-pin.json`。查不到的寫 `UNKNOWN`。和協調者轉述不一致的地方在文中用「**核對**」標出。

## 1. 現況與 SHA

| 項目 | 值 |
|---|---|
| 主線 | `main` @ `21aacc8e`（[#551](https://github.com/Polalalabear/amidst/pull/551) 的 merge，2026-11-17 09:23 +0800）。`mainline/q1q5` 凍結在 `8c741451` |
| 本機 `~/amidst` | 8785 demo 的資料夾。分支 `main`、HEAD `b24d6a26`，工作樹乾淨（`git status --porcelain` 0 行）。**比 GitHub 的 main 舊**，這是刻意的（pin 住），不要在裡面 fetch 或 pull |
| 8785 | `local/demo-pin.json` 鎖在 `b24d6a26`（2026-11-15，使用者核准；閘門 `local/evidence/demo-update-prep-20261115/gate-20261115-1829/RESULT.txt`；D234、D235）。11-16～17 沒動。**不要在 `~/amidst` 改檔、切分支、commit 或 fetch** |
| 磁碟 | 約 7.5–7.9 GiB 可用（`df -h ~`，2026-11-17 下午；早上開工時約 11 GiB，一天少了約 3–4 GiB，原因未查）。**已低於 8 GiB 的程式保護線和 9 GiB 的第三寫手門檻**，派寫檔 session 前要先查原因並請使用者清空間。session 剩 5 GiB 就停，程式內建保護在 8 GiB；第三個寫檔 session 要 9 GiB 以上 |
| 下一個決策編號 | **D257**。**核對**：派這份文件時的轉述說下一個是 D255，但 #93 上已經有 D255（[留言 6934833151](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6934833151)：交接規則、#551 複審 APPROVE、#558 開 PR、Codex 認領 #552、終端機指令只給一次）和 D256（[留言 6939983302](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6939983302)：WP5 方案 C pilot 結果），所以是 D257 |
| 開著的 PR | [#558](https://github.com/Polalalabear/amidst/pull/558)（非 Draft，`claude/experiment-record-latex`，v4 新章已推上，§4.3）；Codex 三個 Draft：[#559](https://github.com/Polalalabear/amidst/pull/559) `codex/feat-live-detection` @ `e1bce09e`（#552、#555）、[#560](https://github.com/Polalalabear/amidst/pull/560) `codex/feat-wp5-dp4` @ `92a4b0c7`（#554）、[#561](https://github.com/Polalalabear/amidst/pull/561) `codex/feat-live-schedule` @ `341f57d4`（#553），CI 都綠、**都還沒審查**（0 review、0 留言）；本 PR [#562](https://github.com/Polalalabear/amidst/pull/562) |

**11-16～17 合併的 PR**（都由使用者執行，merge commit）：

| PR | 內容 | merge |
|---|---|---|
| [#550](https://github.com/Polalalabear/amidst/pull/550) | 協調者交接 2026-11-16 | `ccbd9533` |
| [#544](https://github.com/Polalalabear/amidst/pull/544) | 即時模式（程式、量測、A4 調查、審查修正） | `7d612aa7` |
| [#546](https://github.com/Polalalabear/amidst/pull/546) | WP5 修正、OpenAI 校準、Colab 筆記本 v3.1、彙總表修正、正式組逾時 5000／5000 ms 不重試 | `febc1707` |
| [#556](https://github.com/Polalalabear/amidst/pull/556) | 即時模式 `people.py` 併人規則修正（#544 Opus 判定的後續） | `547a9e61` |
| [#547](https://github.com/Polalalabear/amidst/pull/547) | 即時模式 LLM 決策設計稿 v1.9.1 | `da0dfe60` |
| [#557](https://github.com/Polalalabear/amidst/pull/557) | AGENTS／CLAUDE 規則（D242–D250）、進度導覽、`EPIC_D_AGENTIC_V1.md` 搬進 main | `31a69177` |
| [#551](https://github.com/Polalalabear/amidst/pull/551) | 即時模式 B 畫面跟隨視角＋HUD（複審 APPROVE @ `85b37f2f`） | `21aacc8e` |

**已刪的分支**（使用者執行；D249、D250、D252）：`argon/n3-dp4-api-agent`、`claude/feat-8785-update`、`claude/feat-api-budget`、`claude/feat-live-mode`、`claude/feat-ops-handoff`、`claude/feat-ops-progress`、`claude/feat-workbench-8cam`、`codex/feat-n6-live-assets`、`codex/445-independent-previews`、`codex/516-four-actor-delivery`、`codex/516-natural-walk-sample`、`claude/feat-wp5`、`claude/feat-live-people`、`claude/feat-live-bscreen`。**核對**：協調者 11-17 轉述 `claude/feat-live-bscreen`「ahead 0、等使用者刪」，但 `gh api git/refs/heads/claude/feat-live-bscreen` 已回 404，分支已經刪了。另外 `argon/427-research-report-figures`、`codex/461-tracking-evaluation` 在 GitHub 上已經不存在（`gh api git/refs/heads/...` 回 404；PR #437、#472 都是 CLOSED，commit 留在 `refs/pull/<n>/head`）。**核對**：轉述說這兩條「未核對」，實際是分支已不在，沒有東西要刪。

**還在的分支**（`gh api repos/Polalalabear/amidst/branches`，下午再查：`claude/feat-live-bscreen` 已刪，多了 Codex 的三條）：

| 分支 | head | 狀態 |
|---|---|---|
| `main` | `21aacc8e` | 主線 |
| `mainline/q1q5` | `8c741451` | 凍結的歷史 |
| `claude/feat-ops-docs` | 本 PR | 文件功能線（沿用） |
| `claude/experiment-record-latex` | `36748dda` | #558 |
| `codex/feat-live-detection`、`codex/feat-wp5-dp4`、`codex/feat-live-schedule` | `e1bce09e`、`92a4b0c7`、`341f57d4` | #559、#560、#561（Codex，待審） |
| `claude/epic-d-agentic` | `bebfa8ad` | 設計稿已進 main（#557，D250），**等使用者刪** |
| `argon/424-colab-oneclick-notebook`、`argon/425-research-m1-m4-baseline`、`argon/426-q4-tf-eval-tool`、`argon/429-windows-demo-start-eval`、`codex/467-r005-person-clip-proposal` | `918cc5b6`、`15ac140b`、`0942ebf8`、`c79069c9`、`83b42720` | 待判斷（§4.5） |
| `archive/*` 9 條 | — | 5 條沒有對應 tag（§4.5） |

## 2. 先讀

1. `CLAUDE.md`、`AGENTS.md`、`CLAUDE.local.md`（本機規則：協調者只派工，不在 `~/amidst` 改檔）
2. 本文件
3. [#93](https://github.com/Polalalabear/amidst/issues/93) 的 D242 之後（`gh issue view 93 --repo Polalalabear/amidst --comments`），含 [分支核對留言 6924590269](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6924590269)
4. 即時模式：`docs/operations/LIVE_MODE_HANDOFF_20261116.md`（已在 main）
5. 即時模式 LLM 決策：`docs/design/LIVE_MODE_LLM_DECISION_V1.md` §0F（結果、問題、使用者決定、待決定總表）
6. WP5：`docs/evaluation/WP5_OPENAI_CALIBRATION_20261115.md`
7. WP5 方案 C 開跑計畫（dry-run）：[#546 留言 6924089568](https://github.com/Polalalabear/amidst/pull/546#issuecomment-6924089568)（§5 逾時、§7 停止條件）

## 3. 流程

沿用 11-16 版 §3：

- 每個任務都開新 session；模型照 `CLAUDE.md` 的表：雜務 Haiku low；程式、前端、審查、量測 Sonnet medium（難的用 high）；設計、文件、決策 Opus。
- 寫檔：`git clone --shared --no-checkout ~/amidst <scratch>/clone`，origin 設 `https://github.com/Polalalabear/amidst.git`，用完刪。同時最多 3 個寫檔 session，檔案不重疊。純審查用 `gh pr diff`，不 clone。
- PR base 一律是 `main`，CI `checks` 要綠，只用 merge commit。**合併、刪分支、刪檔、kill 都由使用者在終端執行**；給指令要帶 `--repo Polalalabear/amidst`。
- Codex 和 Argon 的 PR：審查，有問題就直接修。Codex 的成果先給使用者看畫面再採用。
- 付費 API 一律經過 `ApiGuard`；先 dry-run，使用者核准金額才實跑。不讀 API key。
- 被 session 事件喚醒的回合不能開 session，改用提案卡。
- 決策寫到 #93，報告素材寫到 #479。
- 同一條分支同時只能有一個寫手；長任務分段 commit、分段 push（11-16 新增）。

11-17 新增（原文在 #93 D245、D248、D249、D255 和 main 的 `AGENTS.md`「Git workflow」）：

- **分支只給大 feature 開**（D248）。小修正、審查修正、文件更新、後續補強都 commit 到既有的功能分支。能合的盡快合，合完的分支由使用者刪。
- **被取代的分支直接刪，不打 `archive/` tag**（D249）；關閉的 PR 仍保有 commit（`refs/pull/<n>/head`）。
- **和 GitHub 的互動一律用 `gh`**（D245）；不在 `~/amidst` 裡 `git fetch` 來讀其他分支，要讀檔用 `gh api .../contents/<path>?ref=<branch>`。
- **給使用者的終端機指令每條只給一次，不重貼**（D255 第 6 點）。11-17 有一條 `gh pr merge` 被重複貼出、使用者重複執行，卡在「Delete the branch locally?」提示。
- **同一個寫手不要連續追加任務**：一個任務做完就結束，下一件事開新 session（`CLAUDE.local.md`：每個任務都開新 session，不送回舊 session）。
- **5 小時額度會讓 session 中斷**：11-17 一天內撞到三次（01:10 前、06:10 重置前、09:27），每次好幾個 session 同時停（D242、D249）。**中斷的 session 不會自己回報**，協調者要主動用 `gh`（PR head、commit 時間、#93 留言）查產出，再對原 session 發訊息續做（用 `list_sessions {"linked": true}` 找 id），不要重開一個從頭來。
- **付費額度不跨用途**：每筆核准只給它寫明的用途（例如方案 C 的 USD 46 只給 WP5，不給即時模式或 #547 T2；D242 第 2 點）。

## 4. 所有工作，依類型分類

### 4.1 即時模式

| 工作 | 預計產出 | 進度 | 卡住的部分／等誰 |
|---|---|---|---|
| 即時模式本體 #544 | 操作端＋8 鏡頭後台、4 m 關聯範圍、影像裁決（預設關、sol6.1）、重播工具 | **已合併** `7d612aa7`（D247）；A4 變差查明是重播替身答題者的問題（D243 第 2 點） | 無 |
| `people.py` 併人修正 #556 | 同鏡頭 IoU 去重、`same_m` 1.0 m、一對一配對 | **已合併** `547a9e61`；Opus 判定 5 個 P3 不必合併前修 | 無（5 個 P3 留作之後的小修正） |
| B 畫面跟隨視角＋HUD #551 | 前端 B 畫面、HUD、交接文件 §13 | 審查 NEEDS_CHANGES → 修正 → 複審 APPROVE @ `85b37f2f` → **已合併** `21aacc8e`；分支已刪 | 無。注意：給使用者看的裁決截圖用的是假模型（LOCAL `local/evidence/live-mode-bscreen-20261117/`，8 張），真模型的畫面還沒看過 |
| 工作台設定的 LLM 切換 | 工作台設定裡可切換「LLM 覆核／LLM 主導」，預設不開 | 使用者決定要做（D242 第 3 點）；設計在 `LIVE_MODE_LLM_DECISION_V1.md` §6；**未派工** | **下一位協調者的第一個任務**（#551 已合併，前端檔案不再重疊）；派前先處理磁碟（§1） |
| 推論排程 #553（Codex） | 只推論作用中鏡頭和鄰居 | Codex 已交 [#561](https://github.com/Polalalabear/amidst/pull/561)（Draft，+865／−20、14 檔，CI 綠） | **等審查**；和 #559 合併後要聯合驗證 |
| A4 室外偵測率 #552（Codex） | CAM_ENTRY 19%、R101_IN 47%、EXT_CAR 67% 提高 | Codex 已交 [#559](https://github.com/Polalalabear/amidst/pull/559)（Draft，+2555／−14、27 檔，CI 綠；同時含 #555 的 demo 啟動入口）。**核對**：#552 的 `in-progress` 標籤已不在，現在是 `ready` | **等審查**（Sonnet medium；+2555 行且改偵測，屬複雜程式碼，被標出的點交 Opus）。和 #561 合併後要聯合驗證 |
| 失聯後重新取得 | 是否硬性限制追丟時間 | 協調者建議：不設硬性上限，分段門檻（短失聯自動接回；超過門檻放寬搜尋、接回要外觀確認或標待確認；門檻秒數用重播量）（D254 第 3 點） | **等使用者決定**；採用的話寫進 #553 範圍 |
| 真模型在「目標不在候選名單」時怎麼答 | 驗證模型會不會答「都不是」 | 未驗證（D243 第 2 點）；`LIVE_MODE_LLM_DECISION_V1.md` §0F.4 第 2 項：先免費挑題數，再選 sol6.1 上限約 USD 0.2 或三模型約 USD 1，或不測、寫成已知限制 | **等使用者決定**（要花錢；不能用 WP5 的 USD 46） |
| 不花錢的備援方案 | 推論排程、失聯主動接回、候選名單改用速度預測，用重播驗收 | §0F.4 第 1 項建議先做 | **等使用者決定**（D242 第 3 點未回覆） |
| 越肩鏡頭、動畫混合、小地圖 | 遊戲化畫面 | 只有設計稿（`LIVE_MODE_GAME_DESIGN_V1.md`、`V2.md` §8） | 未排 |

### 4.2 WP5 與 Agent 決策

| 工作 | 預計產出 | 進度 | 卡住的部分／等誰 |
|---|---|---|---|
| WP5 修正與 OpenAI 校準 #546 | DP1/DP3 修正、彙總表、Colab 筆記本 v3.1、正式組逾時 5000／5000 不重試 | **已合併** `febc1707`（D251） | 無 |
| Colab L4 v3.1 pilot | 本機模型 DP1／DP3／NL | **已完成**：qwen 24/24 有效；llama DP3 13/24（選了不允許的動作），`run_status: WARN`（[#546 留言 6924323692](https://github.com/Polalalabear/amidst/pull/546#issuecomment-6924323692)；LOCAL `local/evidence/wp5/pilot/colab_l4_v3_1_20261117/`） | 無 |
| OpenAI 方案 C：pilot 段 | terra6.1 → sol6.1 → astra6 各 72 步（DP1／DP3／NL，DP4 跳過），上限 USD 4（D253） | **已跑完**（D256；`wp5-c-pilot` 恢復後的報告 [6939993923](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6939993923) 數字一致；[D256 補充 6940005834](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6940005834)）。格式錯誤三個模型都是 0；**逾時是主要問題**（5 s 不重試）：terra NL 25%；sol DP3 21%、NL 38%；astra DP1 38%、DP3 58%、NL 83%。有回答的題目和規則 100% 一致（合成題）。花費約 USD 0.51（護欄帳本估計 1.728，逾時呼叫按估計記）。依模型合計的逾時退回率 terra 11%、sol 19%、astra 60%。D256 原寫的「偏離」已在補充更正：以模型合計，terra、sol 都沒超過 20%，跑 astra 不算偏離；開跑計畫沒寫明以題型或模型計，下次要先講清楚 | 無（這份文件引用 D256 的數字，沒有重算） |
| OpenAI 方案 C：formal 段 | 三模型正式組 | 未開始。協調者看法（D256）：5 s 下 astra 的 formal 大半會是規則退回，不值得花（formal 預估 USD 3.4）；terra／sol 的 DP1、DP3 可用，NL 要放寬逾時或另列放寬組 | **等使用者決定**：formal 跑不跑、跑哪些模型和題型、NL 要不要放寬組（D253：formal 不在 pilot 授權內） |
| DP4 實跑接線 #554（Codex） | 移除 `DP4_LIVE_NOT_WIRED`，runner 真的呼叫 DP4 | Codex 已交 [#560](https://github.com/Polalalabear/amidst/pull/560)（Draft，+1180／−18、13 檔，CI 綠） | **等審查**（改 Agent 決策輸入，屬複雜程式碼）；實跑 DP4 要花錢，另外核准 |
| 即時模式 LLM 決策設計稿 #547 | v1.9.1 設計稿 | **已合併** `da0dfe60` | 無 |
| T2 是否再花錢 | §0F.4 表的 b、c、d 項 | a 項可免費重算；舊的「約 USD 1.7」已作廢（§0F.4） | **等使用者決定**（和 4.1「目標不在名單」是同一題的 b 項） |

### 4.3 研究紀錄與報告

| 工作 | 預計產出 | 進度 | 卡住的部分／等誰 |
|---|---|---|---|
| 實驗紀錄 v4 #558 | 新增一章：預錄與 live 的差異、參數依據、LLM 介入、追丟時間討論；升 v4、重編 PDF | session `record-live-vs-offline`（Opus high，沿用 `claude/experiment-record-latex`，D254）中斷過，恢復後在 05:53–05:57（UTC）推上 3 個 commit：`06b3b226` v4 新章、`e4027f93` 流程圖與附錄、`36748dda` 重編 PDF（v4，42 頁）。**核對**：協調者 13:50 轉述「新章節還沒寫」，但 GitHub 上新章已在；PR 說明還是「進行中」、沒有「實際產出」，寫手是否收尾 `UNKNOWN` | 等寫手補「實際產出」→ 審查 → 使用者合併 |
| 報告素材 #479 | 持續追加「報告素材」留言 | 進行中 | 無 |
| 第 5 章 `docs/report/CH5_CONCLUSION_DRAFT.md` | 補 WP5 數字（5.3、5.4 第 5 點，標【待補】） | 未做。pilot 數字已有（D256），formal 未決 | 可先用 pilot 數字寫，formal 若跑再補 |
| #479／#489 子項盤點 | 勾選或註明已處理的子項 | 未做。**核對**：#479 未勾的 13 項（#425、#426、#427、#433、#460、#461、#462、#466、#468、#128、#138、#89、#123）裡，前 9 項的 issue 都已 CLOSED（多數標 `deferred`）；#489 未勾的 7 項裡 #480 已 CLOSED | 等協調者派一個 Haiku 盤點 |
| #489 第 1 項（#480 自然語言） | 勾選 | 實際已由 N1（`nl_query_parse.py`、Spotlight 輸入列）完成（D249 第 3 點），#480 已 CLOSED，但 #489 清單沒勾 | 併入上一項 |

### 4.4 8785 demo

| 工作 | 預計產出 | 進度 | 卡住的部分／等誰 |
|---|---|---|---|
| 8785 pin | — | 沒動，`b24d6a26`（2026-11-15） | 下次更新要使用者核准 |
| 更新準備 #555（Codex） | launcher 兩項 P2（`start_all_demo.ps1` 同步 `--root-8cam`、`.command` 啟動時間註解）＋即時模式啟動入口 | Codex 併在 [#559](https://github.com/Polalalabear/amidst/pull/559) 一起交（Codex 回報，D256 補充）；標籤仍是 `ready` | **等審查**；8785 pin 更新要使用者核准 |
| 新 UI 要不要加 8CAM run | — | 未決（D234） | **等使用者決定** |
| N6 天花板亮度和接縫 | — | 未決（D227） | **等使用者決定** |

### 4.5 流程與整理

| 工作 | 預計產出 | 進度 | 卡住的部分／等誰 |
|---|---|---|---|
| 規則寫進 AGENTS／CLAUDE #557 | D242–D250 規則 | **已合併** `31a69177` | 無 |
| 交接規則與本文件（本 PR） | `CLAUDE.md`「Handoff」節、本文件 | 開 PR 中 | 等使用者合併 |
| `claude/epic-d-agentic` | 刪除 | 設計稿已進 main（#557，D250） | **等使用者刪** |
| 舊分支 `argon/424`、`argon/425`、`argon/426`、`argon/429`、`codex/467` | 判斷刪或補進 main | 核對留言列為 D 類（需判斷）。其中 `argon/425`、`argon/426` 對應 #479 未勾子項，`argon/424`、`argon/429` 對應 #486（已關閉）未勾子項，`codex/467` 對應 #445 未勾子項；這些 issue 本身都已 CLOSED | **等使用者決定**（刪除前 Opus 看原始證據；D249 後被取代的直接刪不打 tag） |
| `archive/*` 9 條 | — | 4 條有同 commit 的 `checkpoint/phase1/*` tag；5 條沒有 tag（`archive/local/phase1/physical-policy-approval`、`archive/amidst-claude-wip-20261109`、`archive/canonical-uncommitted-20261109`、`archive/finalization-uncommitted-20261109`、`archive/local/codex/controlled-scene-real-v2-2a`） | **等使用者決定**要不要保留或刪（D249 的「不打 tag」是針對被取代的分支，這 9 條是留存用，要先問） |
| 進度導覽 `Q1Q5_PROGRESS.md` | 補 #558 之後的列；把 #546、#547、#551、#556、#557 的列移到正確狀態 | **核對**：#558 沒有列；#546 還寫「開著，未合併」、#547／#556 還寫 Draft 進行中、#557 還寫「本 PR；待審」 | 等協調者批次更新（D91-4） |
| #93 三則沒編號的即時模式留言 | 編 D 號 | 未做（[6909798873](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6909798873)、[6910613701](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6910613701)、[6911702981](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6911702981)；另 [6916169854](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6916169854) 也沒編號） | 等協調者 |

### 4.6 Codex 與 Argon

| 工作 | 預計產出 | 進度 | 卡住的部分／等誰 |
|---|---|---|---|
| Codex 佇列（D248、D251） | #552–#555 全部交付 | #559（#552、#555）、#560（#554）、#561（#553）都是 Draft、CI 綠；#552–#555 標籤都是 `ready`（沒有 `in-progress`） | **等 Claude 審查**。注意 Codex 的原始證據放在 `~/.codex/visualizations/…`，不在 `local/evidence`，審查要對照 AGENTS.md 的 LOCAL 規則（D256 補充） |
| Argon | — | 目前沒有派工。`owner:argon` 開著的只有 epic #479 本身，沒有 `ready` 子項 | 等協調者需要時派 |

## 5. 預算

| 用途 | 核准上限 | 實際花費 | 出處 |
|---|---:|---:|---|
| 11-16 以前合計（WP5 校準 0.113＋即時模式線 1.07） | — | 約 USD 1.18 | D242 第 1 點 |
| WP5 方案 C pilot 段 | USD 4（terra 1.5、sol 2.5、astra 4 累計） | 依實際 token 約 USD 0.51（terra 0.082、sol 0.119、astra 0.305）；護欄帳本估計約 1.73（逾時呼叫按估計記，佔用的是護欄額度） | D253、D256 |
| WP5 方案 C 總額（含 pilot、formal） | USD 46 | — | D242 第 2 點 |

- 合計：約 USD 1.18 ＋ 0.51 ＝ **約 USD 1.69**（D256）。方案 C 剩約 USD 45.5。花費是 token 數乘 D237 價目算的，不是 OpenAI 帳單。
- 方案 C 開跑計畫：DP4 未接上，扣掉後名義約 USD 8.15、預期約 5.43、最壞約 29.88（D245 第 3 點）。
- **額度不跨用途**：USD 46 只給 WP5；即時模式「目標不在名單」測試、#547 T2 都要另外核准。
- 預設模型 terra（D237）；即時模式的影像裁決用 sol6.1。

## 6. 等使用者決定

1. 磁碟：剩約 7.5 GiB，低於 8 GiB 保護線，要清空間才能再派寫檔 session。
2. WP5 方案 C formal 段：跑不跑、跑哪些模型和題型、NL 要不要放寬逾時組（D256）。
3. 不花錢的備援方案要不要先做（§0F.4 第 1 項；D242 第 3 點）。
4. 「目標不在名單」／T2 要不要花錢、花多少（§0F.4 第 2 項：sol6.1 約 USD 0.2、三模型約 USD 1，或不測）。
5. 失聯後重新取得：分段門檻、不設硬性上限（D254 第 3 點）。
6. `claude/epic-d-agentic` 刪除；`argon/424`、`425`、`426`、`429`、`codex/467` 的去留；`archive/*` 5 條沒有 tag 的處理。
7. 8785：新 UI 要不要加 8CAM run（D234）、N6 天花板亮度和接縫（D227）；下次更新的 pin 核准。
8. #558、本 PR、Codex 的 #559／#560／#561 審查通過後合併；#560 的 DP4 實跑花費另外核准。
9. 真人模型對照實驗（D236，11-16 版列過，之後沒有新的決定）。

## 7. 第一個任務（建議，給新協調者）

前一位協調者（本對話）收尾後不再開新工作，之後以新的協調者對話為主（使用者 2026-11-17）。

1. **先查磁碟**：剩約 7.5 GiB，一天少了約 3–4 GiB。派 Haiku low 唯讀查哪裡變大（`local/evidence`、scratchpad、`~/.codex` 等），請使用者清；回到 9 GiB 以上才同時派三個寫手。
2. **審查 Codex 的 #559／#560／#561**：各派 Sonnet medium 正式審查（`gh pr diff`、focused tests、`git diff --check`、merge-tree）；三個都屬複雜程式碼，被標出的點交 Opus。#559＋#561 合併後聯合驗證；檢查 Codex 證據放在 `~/.codex/...` 的 LOCAL 規則。
3. **問使用者 formal 要不要跑**（D256、補充）：跑哪些模型和題型、NL 要不要另列放寬逾時組；分段停止條件要先寫明以題型或模型計。
4. **#558**：寫手補完「實際產出」後派 Sonnet medium 審查（LaTeX 數字對照出處、PDF 重編），通過後請使用者合併。
5. **派「工作台設定的 LLM 切換」**（Sonnet medium，新功能分支，設計照 `LIVE_MODE_LLM_DECISION_V1.md` §6，預設不開；D242 第 3 點）。等磁碟恢復再派。
6. 之後派一個 Haiku low 批次處理：進度導覽補列（#558–#562）並更新 #546／#547／#551／#556／#557 的狀態、#479／#489 子項勾選、#93 沒編號的留言編 D 號。
