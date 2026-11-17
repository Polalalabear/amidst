# 協調者交接 2026-11-17（晚間快照）

**快照時間：2026-11-17 晚間（UTC 約 15:55，#93 最後一則是 D277，15:51 UTC）。** 這份文件改寫了同日早上的版本（#562 合併的 `306dc2fa` 版，保留在 git 歷史）。早上版本之後的決策是 #93 的 D257–D277；本文整理到 D277 為止（第一版晚間快照到 D273，見本 PR 的 `c6e03889`）。

**新的協調者對話全程用繁體中文回覆**（D255、`CLAUDE.md`「Handoff」）。下一個決策編號是 **D278**，同步到 [#93](https://github.com/Polalalabear/amidst/issues/93)。

- Model / effort：Opus 5.5 / medium（交接文件 session `handoff-1117pm`）。
- 核對方式：PR、issue、分支、CI 狀態都在快照時用 `gh pr view`、`gh issue view`、`gh issue list`、`gh api repos/Polalalabear/amidst/branches` 重新查過；`~/amidst` 只讀了 HEAD、`git status --porcelain` 和 `local/demo-pin.json`。查不到的寫 `UNKNOWN`。

## 1. 現況與 SHA

| 項目 | 值 |
|---|---|
| 主線 | `main` @ `0606b164`（[#563](https://github.com/Polalalabear/amidst/pull/563) 的 merge，2026-11-17 晚間）。`mainline/q1q5` 凍結在 `8c741451` |
| 本機 `~/amidst` | 8785 demo 的資料夾，分支 `main`、HEAD `e9db4fdf`、工作樹乾淨（0 行）。**不改檔、不切分支、不 commit、不 fetch** |
| 8785 pin | `local/demo-pin.json`：commit `e9db4fdf`、2026-11-17、gate `local/evidence/demo-update-prep-20261117/gate-20261117/RESULT.txt`（D270）。**比 main 舊一個 merge（缺 #563）**，等 #559 合併後一起更新 |
| 8785 執行方式 | **在終端面板分頁「8785 demo」前景執行**：`start_445_demo.command --port 8785 \| tee -a local/logs/demo-8785-20261117.log`（D277 第 4 點）。原因：用 `nohup`＋`&` 背景啟動兩次，都收到結束訊號停止（log 無錯誤，同 D269）。**關掉這個分頁 8785 就會停** |
| 8791 | `local/runtime/live-main` @ `e9db4fdf`，由 `local/runtime/start_live_8791.sh` 啟動（D264、D269；pid 24417 是 D269 當時的值，現在 `UNKNOWN`） |
| 磁碟 | 快照時約 12 GiB 可用（`df -h`）。早上曾掉到 7.6 GiB（D257），B3、B1 刪除後回升。第三個寫手要 9 GiB 以上，剩 5 GiB 就停 |
| 下一個決策編號 | **D278** |

**今天（11-17）合併的 PR**（都由使用者執行，merge commit）：

| PR | 內容 | merge |
|---|---|---|
| [#556](https://github.com/Polalalabear/amidst/pull/556) | 即時模式 `people.py` 併人修正 | `547a9e61` |
| [#546](https://github.com/Polalalabear/amidst/pull/546) | WP5 修正、OpenAI 校準、Colab v3.1 | `febc1707` |
| [#547](https://github.com/Polalalabear/amidst/pull/547) | 即時模式 LLM 決策設計稿 v1.9.1 | `da0dfe60` |
| [#557](https://github.com/Polalalabear/amidst/pull/557) | AGENTS／CLAUDE 規則、進度導覽 | `31a69177` |
| [#551](https://github.com/Polalalabear/amidst/pull/551) | 即時模式 B 畫面跟隨視角＋HUD | `21aacc8e` |
| [#562](https://github.com/Polalalabear/amidst/pull/562) | 交接規則（D255）＋早上的交接文件 | `444d15f3` |
| [#560](https://github.com/Polalalabear/amidst/pull/560) | WP5 DP4 實跑接線（Codex，#554） | `4142e26c` |
| [#561](https://github.com/Polalalabear/amidst/pull/561) | 即時模式推論排程（Codex，#553） | `e9db4fdf` |
| [#563](https://github.com/Polalalabear/amidst/pull/563) | LLM 開關（workbench-v2 設定 → 即時模式，預設關；P2 Host 檢查已補，head `6737accf`） | `0606b164` |

**開著的 PR：**

| PR | 分支 @ head | 狀態 |
|---|---|---|
| [#558](https://github.com/Polalalabear/amidst/pull/558) | `claude/experiment-record-latex` @ `b3246e00` | 非 Draft；`rv-558` 審查 NEEDS_CHANGES（[留言 6952193830](https://github.com/Polalalabear/amidst/pull/558#issuecomment-6952193830)），原 session `record-live-vs-offline` 修正中（D274 第 2 點） |
| [#559](https://github.com/Polalalabear/amidst/pull/559) | `codex/feat-live-detection` @ `2e654b26` | Draft，CI 綠；修改 C 聯合驗證 NOT_PASSED，Codex 做第三份指示中 |
| [#564](https://github.com/Polalalabear/amidst/pull/564) | `claude/feat-workbench-v2-ux` @ `b01f9ddc` | Draft，CI 綠；五點已完成，**待正式審查**，尚未在真的 8785 驗證（D274 第 3 點） |
| [#567](https://github.com/Polalalabear/amidst/pull/567) | `claude/feat-live-ab` @ `b8359bfb` | LIVE A/B 雙畫面規格與介面契約 `docs/specs/LIVE_MODE_AB_V1.md`（D275–D277）；§11 有 7 個待使用者決定的點（都有預設） |
| 本 PR | `claude/feat-ops-docs` | 交接文件、AGENTS.md 主要 UI、進度導覽 |

**還在的分支**（`gh api .../branches`）：`main`、`mainline/q1q5`、上表五條（含本 PR 的 `claude/feat-ops-docs`）、`claude/epic-d-agentic`（等使用者刪）、`argon/424-colab-oneclick-notebook`、`argon/425-research-m1-m4-baseline`、`argon/426-q4-tf-eval-tool`、`argon/429-windows-demo-start-eval`、`codex/467-r005-person-clip-proposal`（五條待判斷）、`archive/*` 9 條。今天合併的 `codex/feat-wp5-dp4`、`codex/feat-live-schedule`、`claude/feat-workbench-llm-toggle` 已刪。刪除建議見過時項目總清單（[#486 留言 6953090327](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6953090327) §1）。

## 2. 先讀

1. `CLAUDE.md`、`AGENTS.md`、`CLAUDE.local.md`（本機規則：協調者只派工，不在 `~/amidst` 改檔）
2. 本文件
3. [#93](https://github.com/Polalalabear/amidst/issues/93) 的 D257–D277（`gh issue view 93 --repo Polalalabear/amidst --comments`，從 D257 開始逐則讀）
4. 即時模式：`docs/operations/LIVE_MODE_HANDOFF_20261116.md`、`docs/design/LIVE_MODE_LLM_DECISION_V1.md` §0F
5. #559 的聯合驗證報告（[`docs/evaluation/LIVE_DETECTION_SCHEDULE_JOINT_20261117.md` @ `2e654b26`](https://github.com/Polalalabear/amidst/blob/2e654b268624d023ac2d16f9e90c6fdaf4778198/docs/evaluation/LIVE_DETECTION_SCHEDULE_JOINT_20261117.md)）和第三份指示（[#559 留言 6952347393](https://github.com/Polalalabear/amidst/pull/559#issuecomment-6952347393)）
6. WP5：formal 結果（[#93 留言 6941051090](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6941051090)）、逾時分析（[#93 留言 6950053674](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6950053674)）
7. 舊工作台下線計畫（[#486 留言 6950051568](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6950051568)）與 Opus 決定（[#486 留言 6952944724](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6952944724)）
8. 過時項目總清單（[#486 留言 6953090327](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6953090327)）
9. LIVE A/B 規格：[#567](https://github.com/Polalalabear/amidst/pull/567) 的 `docs/specs/LIVE_MODE_AB_V1.md`（§11 待決定）與 Codex issue [#566](https://github.com/Polalalabear/amidst/issues/566)

## 3. 流程（今天新增或再確認的）

沿用早上版本 §3 與 `CLAUDE.md`、`AGENTS.md`。今天的補充：

- **主要 UI 是 `frontend/workbench-v2/`**（8785 由 `scripts/serve_demo_integration.py` 提供）。舊的 `frontend/workbench/` 下線中（D268）。今天 #563 的 brief 寫成舊工作台而做錯一次（D267），寫 brief 時要寫 workbench-v2。
- **8785 的更新流程**（D269、D270）：在 clone 跑 gate（node、focused pytest、`check_demo_dependencies.py --smoke`、real-e2e）→ 寫 `RESULT.txt` → 使用者在終端快轉 `~/amidst`、`scripts/demo_pin.py approve`、`start_445_demo.command --port 8785`。gate 24 小時內有效。
- **8785 在終端面板分頁「8785 demo」前景執行**（D277 第 4 點）：背景啟動（`nohup`＋`&`）兩次都收到結束訊號停止，改前景後正常。之後重啟 8785 也照這個方式，不要關那個分頁。
- **8791 從 `local/runtime/live-main` 跑 main**（`local/runtime/start_live_8791.sh`），不再用舊 scratchpad clone（C1）。
- **Sonnet 每週額度曾用完**（D272，原本 11/22 09:00 重置）；使用者已重置（D273）。額度再用完時改用 Opus medium 派同樣的工作，並在 #93 記一筆。
- **中斷或失敗的 session 不會自己回報**：用 `gh` 查產出（PR head、留言），再對原 session 發訊息續做。

## 4. 所有工作，依類型分類

### 4.1 8785 demo

| 工作 | 預計產出 | 目前進度 | 卡住的部分（卡在誰、等什麼） |
|---|---|---|---|
| 8785 更新到 main | 8785 跑 main 最新版 | **已完成**（D270）：`~/amidst` 快轉到 `e9db4fdf`，`scripts/demo_pin.py approve` 通過（gate `local/evidence/demo-update-prep-20261117/gate-20261117/RESULT.txt`），`start_445_demo.command --port 8785` 啟動；`/workbench-v2/` 回 200，四個 run（B-05、A4-1、B4-1、r005）載入 | 無 |
| 8791 改從 main | 即時模式跑 main | **已完成**（D264、D269）：`local/runtime/live-main` @ `e9db4fdf`，`start_live_8791.sh`；改用 N6 正式資產 `local/data/live-assets-20261115` | 無 |
| 8785／8791 下午停止原因 | 查明 | **已查**（D269 第 1 點）：兩者都收到結束訊號後正常退出（8785 14:15:17、8791 14:58:03），不是系統殺、不是崩潰或重開機；送訊號者查不到 | 無（原因 `UNKNOWN`，再發生時再查） |
| 8785 晚間又停止 | 8785 持續可用 | 晚間又收到結束訊號停止（log 無錯誤）。協調者改在終端面板分頁「8785 demo」前景執行，`/workbench-v2/` 回 200（D277 第 4 點） | 無；關掉分頁就會停。送結束訊號的來源仍 `UNKNOWN` |
| 合併後再更新一次 | 8785、8791 含 #559、#563（和 #564） | 未開始。#563 已合併（`0606b164`），但兩個介面仍在 `e9db4fdf` | 等 #559 合併（一起含 #563）；之後照 §3 的流程跑 gate，pin 和啟動交使用者（8785 照前景方式） |
| N6 天花板亮度和接縫 | — | 未決（D227） | **等使用者決定** |
| 新 UI 要不要加 8CAM run | — | 未決（D234） | **等使用者決定** |

### 4.2 即時模式

| 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|
| 推論排程 #553／#561（Codex） | 只推論作用中鏡頭和鄰居 | **已合併** `e9db4fdf`；#553 已關閉 | 無 |
| 偵測率＋demo 啟動入口 #552、#555／[#559](https://github.com/Polalalabear/amidst/pull/559)（Codex） | A4 室外鏡頭偵測率提高；即時模式啟動入口 | 修改 A 完成（`efb2f498`，ENTRY 0.05 保留，D266）；修改 C（merge main、聯合驗證）**NOT_PASSED**（[Codex 留言 6941946203](https://github.com/Polalalabear/amidst/pull/559#issuecomment-6941946203)）：固定 RGB A4 跟對 0.705→0.695（tick 56 adaptive 漏看）、新實跑 B4 跟對 0.451→0.333、失聯 0.235→0.303、ENTRY 重新鎖定兩模式皆 censored；adaptive 每秒輪數 +20–30%。**使用者決定：先修排程與重新鎖定再合併**，不改回 `--schedule all`（D273） | **卡在 Codex**：做第三份指示（[#559 留言 6952347393](https://github.com/Polalalabear/amidst/pull/559#issuecomment-6952347393)：漏看修正、B4 原因、ENTRY 可量測定義；通過條件不變）。交回後派審查（複雜程式），通過再請使用者合併 |
| LLM 開關 [#563](https://github.com/Polalalabear/amidst/pull/563) | workbench-v2「設定 → 即時模式」切換 LLM 覆核／主導，預設關、不接付費 provider | **已合併** `0606b164`（D276 第 3 點）：瀏覽器直連 live `/config`，live 端只對本機工作台來源開 CORS；差異重審的 P2（`Host` 檢查）已補（head `6737accf`） | 無。8785／8791 還沒含它（等 #559 一起更新）；P3（`advisor_model` 非字串、IPv6）未處理 |
| workbench-v2 五點易用性 [#564](https://github.com/Polalalabear/amidst/pull/564) | (1) 搜尋 Enter 直接進入；(2) 追蹤分頁搜尋＋`FORBIDDEN_DATA_SCOPE` 原因；(3) 概況卡片排版；(4) 易讀地點／鏡頭名稱；(5) live 模式入口（D271） | 五點完成，head `b01f9ddc`，CI 綠（D274 第 3 點）。`FORBIDDEN_DATA_SCOPE` 不是 GT 隔離，而是伺服器重啟後 session 失效（改自動續期）與拒絕原因碼被遮掉（改具體說明）；3 個鏡頭名稱標 UNKNOWN | **待正式審查**（Sonnet medium）；尚未在真的 8785 驗證；3 個 UNKNOWN 名稱等使用者確認；之後使用者看截圖、合併 |
| LIVE A/B 雙畫面 規格 [#567](https://github.com/Polalalabear/amidst/pull/567)／實作 [#566](https://github.com/Polalalabear/amidst/issues/566)（CX-L5） | A（操作端）WASD、開始前選角色（中途不可換）；B（系統端）和 8785 追蹤模式一樣選要追蹤的人，只用鏡頭畫面（GT 隔離）；沒被選的人物照腳本移動；人物不碰撞（半徑預設 0.30 m）；目的只是展示即時追蹤（D275、D276） | 規格與介面契約已起草（`live-ab-spec`，`docs/specs/LIVE_MODE_AB_V1.md`）；Codex issue #566 標 `blocked` | **規格 §11 的 7 點等使用者決定**（都有預設）；#566 等 #559 合併與 Codex 確認契約，可先做 `crowd.mjs`＋`sim.mjs`＋A 選單與 `scripts/live_ab_score.py`（D277 第 1 點）。實作交 Codex，Claude 寫規格與審查 |
| 失聯後重新取得 | 分段門檻：短失聯自動接回；超過門檻放寬搜尋 | 協調者建議（D254 第 3 點） | **等使用者決定**（D254-3 分段門檻） |
| 真模型在「目標不在名單」時怎麼答 | 驗證模型會答「都不是」 | 未驗證（`LIVE_MODE_LLM_DECISION_V1.md` §0F.4 第 2 項：sol6.1 約 USD 0.2、三模型約 USD 1，或不測） | **等使用者決定**花費（不能用 WP5 的 USD 46） |
| 不花錢的備援方案與 T2 | 失聯主動接回、候選名單改用速度預測，用重播驗收 | §0F.4 第 1 項建議先做 | **等使用者決定** |

### 4.3 WP5 與 Agent 決策

| 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|
| 方案 C pilot | terra／sol／astra 各 72 步 | **完成**（D256 與補充）：格式錯誤 0；逾時退回（模型合計）terra 11%、sol 19%、astra 60%；實測約 USD 0.51（帳本估計 1.73） | 無 |
| 方案 C formal | terra、sol 的 5 s 正式組＋NL 10 s 放寬組（astra 不跑、DP4 跳過） | **完成**（D260 另開帳本、上限 USD 6；結果 [留言 6941051090](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6941051090)）：格式錯誤 0、無 DENIED；逾時退回 terra 10.7%、sol 20.0%（sol DP3 35.6%）；NL 放寬到 10 s 後兩模型 0／40。**實測 USD 0.854**（帳本估計 1.233）。執行時以環境變數把每日／每分鐘呼叫次數上限調高（金額上限不變） | 無 |
| 逾時原因分析 | 為什麼逾時、怎麼改 | **完成**（[留言 6950053674](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6950053674)，0 次付費呼叫）：5 s 上限落在模型延遲分布中間；自由文字 `rationale` 讓輸出過長；pilot 樣本小且模型依序跑；astra 固定開銷約 2.2 s，5 s 不可行。建議：逾時分題型（NL／DP3 用 10 s）、縮短輸出、加大 pilot 並讓合成題有分歧 | **等使用者決定**要不要採用改善建議（要改程式和再花錢） |
| DP4 實跑接線 #554／#560（Codex） | runner 真的呼叫 DP4 | **已合併** `4142e26c`（D266）；#554 issue 還開著（工作已完成，可關） | 真實 provider 的 DP4 smoke **等使用者核准金額**（不擋合併，D261） |
| 預算 | — | 專案 OpenAI 累計實測約 **USD 1.36**（pilot 0.51＋formal 0.854；不含 11-16 以前的約 1.18，含的話約 2.54）；帳本估計約 2.96（兩本帳分開）。方案 C 總上限 USD 46 不變，只給 WP5 | 額度不跨用途（D242） |

> 註：D266 寫「專案 OpenAI 累計實測約 1.36」，口徑是方案 C 的 pilot＋formal；早上版本的「約 1.69」含 11-16 以前的 1.18。兩個數字口徑不同，引用時寫清楚。

### 4.4 研究紀錄與報告

| 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|
| 實驗紀錄 v4 [#558](https://github.com/Polalalabear/amidst/pull/558) | 新章：預錄與 live 的差異、參數依據、LLM 介入 | `rv-558` 審查 **NEEDS_CHANGES**：P1「formal 未跑」已過時；P2 `decision_source` 在預設 `reseed` 下不會出現 `AGENT`、4 m 候選名單只適用 `SILENT_PICK`；P3 三項。原 session `record-live-vs-offline` 修正並重編 PDF 中（D274 第 2 點），head 已到 `b3246e00` | 等寫手交回 → 複審 → 使用者合併 |
| 報告素材 #479 | 持續追加「報告素材」留言 | 進行中（owner:argon epic，實際由 Claude 追加） | 今天的 WP5 formal、逾時分析、#559 聯合驗證都還沒追加到 #479（`UNKNOWN`，快照時沒逐則查） |
| 第 5 章 WP5 數字 | `docs/report/CH5_CONCLUSION_DRAFT.md` 5.3、5.4 補數字 | 未做；pilot 與 formal 數字都有了 | 可派（Opus medium），建議等 #558 修正後一起對齊口徑 |

### 4.5 流程與整理

| 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|
| 冗餘檔案清理（#486） | 刪重複的 LOCAL 檔 | 盤點（`inv-redundant`）→ Opus 決定（[#486 留言 6940461147](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6940461147)）。**B3（143 MB）、B1（488 MB）已刪**；**C1**（舊 scratchpad clone 223 MB）原因是 8791 用它當 cwd，8791 已改從 `local/runtime/live-main` 跑，可以刪 | C1、舊 pid、`/private/tmp/claude-501/glb` 的刪除指令已交使用者（D264、D268）；使用者是否已執行 `UNKNOWN`，下次要確認 |
| ledger 小修（R3） | `CO-claude` 改 `deletable`；`LOC-shared-cleanroom` 更新檔數／SHA／大小、註明刪除日期（D262 第 2 點） | 未做；已併入過時清單的 R3 | #565 合併後，在 `claude/feat-ops-docs` 做 |
| 舊工作台 `frontend/workbench/` 下線（R1） | 刪 `frontend/workbench/` 62 檔（33,410 行），改 15 檔；`/`（8016）302 轉到 `/workbench-v2/`；不打 tag，以 `0606b164` 留存 | **Opus 決定完成**（`opus-retire-old-wb`，[#486 留言 6952944724](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6952944724)）：盤點更正 4 處，`office_demo_backend.py`、`core-legacy-e2e.mjs` 保留；過時清單另補列 Office 舊 demo 8 檔（併入 commit 3）。實作分支 `claude/feat-retire-old-workbench`，4 個 commit。本 PR 已把 AGENTS.md 主要 UI 改成 workbench-v2 | **等使用者確認 Office 舊啟動器 3 檔下線**（建議是）；建議 #565 先合再派實作；`office_display` 被 `configs/q1q5/*_sources.json` 列出，實作前要先確認（UNKNOWN） |
| 過時項目總清單 | 分支、文件、程式碼、issue、LOCAL 的過時項目與終端指令、依賴順序 | **完成**（Opus high，[#486 留言 6953090327](https://github.com/Polalalabear/amidst/issues/486#issuecomment-6953090327)）。可立即執行：刪 5 條分支（`claude/epic-d-agentic`＋4 條有同 SHA tag 的 `archive/local/phase1/*`）、關 #554、刪 C1（222 MB）、搬 tmp 雜項。約 30 份文件封存（留原位加頭＋索引，不刪）。需改 repo 的 R1（舊工作台下線＋Office 補列 8 檔）、R2（文件封存）、R3（ledger）、R4（`frontend/live-mode/measure/smoke.mjs` 不寫 `/private/tmp`） | 可立即執行的刪除／關閉交使用者在終端執行；argon/424、425、426、429、codex/467 **等使用者確認**；R1 走 `claude/feat-retire-old-workbench`，R2–R4 進 `claude/feat-ops-docs`，都等 #565 合併後派 |
| 進度導覽 | 補到 #564 | 本 PR 做 | 等合併 |
| 舊分支 | `argon/424`、`425`、`426`、`429`、`codex/467` 去留；`claude/epic-d-agentic` 刪除 | 過時清單建議：`claude/epic-d-agentic` 可立即刪；五條舊分支建議刪（commit 都留在 `refs/pull/<n>/head`） | 五條**等使用者確認**；刪除由使用者在終端執行 |
| `archive/*` 9 條 | — | 過時清單：4 條 `archive/local/phase1/*` 有同 SHA tag，可立即刪；另 5 條（被 main 引用或沒有其他副本）保留 | 刪除由使用者在終端執行 |
| 磁碟 | 維持 9 GiB 以上 | 快照時約 12 GiB | 系統 swap、Chrome 更新暫存、Claude `vm_bundles` 11 GiB 等 repo 外大項（D257）由使用者決定 |

### 4.6 Codex 與 Argon

| 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|
| Codex：#559 第三份指示 | 修漏看、查 B4、定義 ENTRY 可量測；通過聯合驗證 | 進行中（D273；同分支、保持 Draft） | 等 Codex 交回。#552、#555 都併在 #559 |
| Codex：#566 CX-L5 LIVE A/B 實作 | 照 #567 規格實作 A 選角色、B 選目標、人物不碰撞 | 已開 issue，`blocked` | 等 #559 合併與 Codex 確認契約；可先做不和 #559 重疊的部分（D277 第 1 點） |
| Codex：#554 | 關 issue | 工作已由 #560 合併；過時清單列為可立即關閉 | 協調者或 Haiku 留言關閉 |
| Argon | — | 沒有派工。`owner:argon` 開著的只有 epic [#479](https://github.com/Polalalabear/amidst/issues/479)；Argon／Codex 拉取佇列 [#434](https://github.com/Polalalabear/amidst/issues/434) 已在 2026-11-08 關閉（D132 改到 #93） | 需要時再派 |

## 5. 等使用者決定

1. **LIVE A/B 規格 §11 的 7 點**（#567，都有預設）。
2. **舊工作台下線時 Office 舊啟動器 3 檔是否一起下線**（建議是；#486 留言 6952944724）。
3. **過時清單**：可立即執行的項目（刪 5 條分支、關 #554、刪 C1、搬 tmp 雜項）交使用者執行；`argon/424`、`425`、`426`、`429`、`codex/467` 去留。
4. **#565**（本 PR）合併——R1–R4 和舊工作台下線實作都排在它後面。
5. **#559**：Codex 第三份指示交回後的審查結果與合併（D273）。
6. **#564**：審查後看截圖、確認 3 個 UNKNOWN 鏡頭名稱、合併。
7. **#558**：修正後合併。
8. **失聯後重新取得的分段門檻**（D254 第 3 點）。
9. **LLM 不花錢的備援與 T2**（§0F.4 第 1 項）；**真模型驗證花費**（§0F.4 第 2 項：sol6.1 約 USD 0.2、三模型約 USD 1，或不測）。
10. **WP5 改善建議**（逾時分題型、縮短輸出、加大 pilot）要不要做，以及 DP4 smoke 的金額。
11. **N6 天花板亮度和接縫**（D227）；新 UI 要不要加 8CAM run（D234）。

## 6. 給新協調者的第一件事（依 D277 的順序）

開始前先用 `gh pr view 558 559 564 565 567` 和 `gh issue view 93 --comments`（D277 之後）確認快照後有沒有新進度。

1. **LIVE A/B**（D277 第 1 點）：把 #567 規格 §11 的 7 點問使用者（AskUserQuestion，附預設），決定後更新規格、合併 #567；把可先做的部分（`crowd.mjs`＋`sim.mjs`＋A 選單、`scripts/live_ab_score.py`）告訴 Codex（給可直接貼上的文字）。#566 在 #559 合併、Codex 確認契約後改 `ready`。
2. **舊工作台下線**（D277 第 2 點）：問使用者 Office 舊啟動器 3 檔是否下線；#565 合併後派實作（分支 `claude/feat-retire-old-workbench`，照 #486 留言 6952944724 的 4 個 commit，含過時清單補列的 Office 8 檔；先確認 `office_display` 的來源 pin）。
3. **過時項目**（D277 第 3 點）：可立即執行的刪除／關閉指令（#486 留言 6953090327）交使用者在終端執行；問五條舊分支去留；#565 合併後派 R2–R4（進 `claude/feat-ops-docs`）。
4. **8785**（D277 第 4 點）：維持終端面板分頁「8785 demo」前景執行，不要關。#559 合併後照 §3 的流程把 8785、8791 更新到 main（含 #563），8785 照前景方式重啟。
5. **開著的 PR**（D277 第 5 點）：#558 修正交回後複審；#559 等 Codex，交回後 Sonnet 審查＋Opus 判定；#564 派正式審查（Sonnet medium）；#565 請使用者合併；#567 見第 1 點。

## 7. Session 清單（快照時）

`list_sessions {"linked": true}` 列得到時以它為準。快照時與前一位協調者連結的 session：

| 名稱 | session id | 狀態 | 內容 |
|---|---|---|---|
| `wb2-ux-opus` | `local_a9d969c1-ec18-433c-a79c-2bdb2771696e` | 快照時 `UNKNOWN` | #564 workbench-v2 五點（已完成五點） |
| `live-ab-spec` | `UNKNOWN` | `UNKNOWN` | #567 LIVE A/B 規格、#566 |
| `opus-retire-old-wb` | `UNKNOWN` | 完成 | 舊工作台下線決定（#486 留言 6952944724） |
| 過時清單（Opus high） | `UNKNOWN` | 完成 | #486 留言 6953090327 |
| `rv-563-v2` | `local_87e00904-c5b9-4d65-aede-7b0600b4513f` | 完成 | #563 差異重審 APPROVE |
| `rv-558` | `local_ebe77247-9a07-4b56-b782-46c5c360156c` | 完成 | #558 審查 NEEDS_CHANGES |
| `llm-toggle` | `local_0c115a14-faa9-4091-a055-70d6c0ea5f53` | 完成 | #563 寫手（P2 已補、已合併） |
| `563-llm` | `local_111a94ce-cce7-4eff-9cc7-6ef6e147007a` | 完成 | #563 |
| `wp5-c-formal` | `local_d877f162-0e11-42db-83f0-e0d43516e6f5` | 閒置 | WP5 formal 執行 |
| `wp5-api-analysis` | `local_396faf85-524a-407c-a03f-a867132c0c76` | 閒置 | WP5 逾時分析 |
| `live-8791-main` | `local_6f39c05e-fb5c-45df-9938-dbc0483b3681` | 閒置 | 8791 改從 main |
| `demo-ports-main` | `local_bc7f709c-1848-4b09-816d-af72fdf25297` | 閒置 | 8785／8791 停止原因與 8785 gate |
| `retire-old-wb-plan` | `local_c841eca7-cd71-402e-9075-bcbd424afa5c` | 閒置 | 舊工作台下線計畫 |
| `inv-redundant` | `local_8c9d9584-3c47-47c1-a1fb-c18221a0949f` | 閒置 | 冗餘檔案盤點 |
| `sonnet-486` | `local_ffa8eab6-d802-41f7-9ad2-da46d163a878` | 閒置 | 清理候選核對 |
| `opus-486-b3-c1-b1` | `local_cddff288-6b2f-46a6-a865-e494bb562eca` | 閒置 | 清理刪除決定 |
| `opus-559-560-561` | `local_266aae80-db7d-4be5-b60f-b99b306bf92a` | 完成 | Codex 三個 PR 的 Opus 判定 |
| `rv-559`、`rv-560`、`rv-561` | `local_9e90289a-…`、`local_d6eacff2-…`、`local_f92543b6-…` | 完成 | Codex 三個 PR 的 Sonnet 審查 |
| `handoff-1117pm` | （本 session） | — | 本文件 |

`record-live-vs-offline`（#558 寫手，D274 已請它修正）、`live-ab-spec`、`opus-retire-old-wb` 不在本 session 看得到的連結清單內，id `UNKNOWN`；用 `list_sessions {"linked": true}` 找，找不到就開新 session。
