# 協調者交接 2026-11-18

**快照時間：2026-11-18（UTC 約 02:45，#93 最後一則是 D310，02:39 UTC）。** 前一份是 `docs/agents/COORDINATOR_HANDOFF_20261117.md`（11-17 晚間快照，整理到 D277）。本文整理 D278–D310（D283 是無編號留言索引，補編 D284–D301）。

**新的協調者對話全程用繁體中文回覆**（D255、`CLAUDE.md`「Handoff」）。下一個決策編號是 **D311**，同步到 [#93](https://github.com/Polalalabear/amidst/issues/93)。

**工作清單的唯一來源是 [#93](https://github.com/Polalalabear/amidst/issues/93) 本文**（D281）。本文 §4 是快照，和 #93 本文不一致時以 #93 本文為準。

- Model / effort：Opus 5.5 / medium（交接文件 session `handoff-1118`）。
- 核對方式：`gh issue view 93`（本文與留言）、`gh pr list --state open`、`gh pr list --state merged`、`gh pr checks`、`gh issue list --state open`、`gh api repos/Polalalabear/amidst/branches`、`git ls-remote`；`~/amidst` 只讀了 HEAD、`git status --porcelain` 和 `local/demo-pin.json`；session 用 `list_sessions {"linked": true}`。查不到的寫 `UNKNOWN`。

## 1. 現況與 SHA

| 項目 | 值 |
|---|---|
| 主線 | `main` @ `894bdd9e`（[#559](https://github.com/Polalalabear/amidst/pull/559) 的 merge，2026-11-18 02:34 UTC）。`mainline/q1q5` 凍結在 `8c741451` |
| 本機 `~/amidst` | 8785 demo 的資料夾，分支 `main`、HEAD `e9db4fdf`、工作樹乾淨（`git status --porcelain` 0 行）。**不改檔、不切分支、不 commit、不 fetch** |
| 8785 pin | `local/demo-pin.json`：commit `e9db4fdf`、2026-11-17、gate `local/evidence/demo-update-prep-20261117/gate-20261117/RESULT.txt`（SHA-256 `4d9d6930febf123daa9c19b8205ad0a311c4be08ae64b2ed87e3f85afa267887`）、approved_by 使用者（D270）。**比 main 舊**（缺 #563、#558、#567、#575、#586、#587、#590、#595、#559），等 [#576](https://github.com/Polalalabear/amidst/issues/576) 一起更新 |
| 8785 執行方式 | 在終端面板分頁「8785 demo」**前景執行**（D277 第 4 點）。背景啟動兩次都收到結束訊號停止。**關掉這個分頁 8785 就會停** |
| 8791 | 從 `local/runtime/live-main` @ `e9db4fdf` 跑（`local/runtime/start_live_8791.sh`，D264、D269）；pid `UNKNOWN` |
| 磁碟 | 快照時約 12 GiB 可用（`df -h ~`）。第三個寫手要 9 GiB 以上，剩 5 GiB 就停 |
| OpenAI | 專案實測至今不到 USD 3；**可用額度約 USD 50**（D306） |
| 下一個決策編號 | **D311** |

**11-17 晚間到 11-18 合併的 PR**（merge commit；11-18 起依 D305 由協調者直接合併）：

| PR | 內容 | merge |
|---|---|---|
| [#565](https://github.com/Polalalabear/amidst/pull/565) | 11-17 晚間交接文件、AGENTS 主要 UI 改 workbench-v2 | `3137a1ca` |
| [#558](https://github.com/Polalalabear/amidst/pull/558) | 實驗紀錄 v4.2（預錄與 live 的差異、參數依據、LLM 介入） | `edb96a31` |
| [#567](https://github.com/Polalalabear/amidst/pull/567) | LIVE A/B 雙畫面規格與介面契約 v2（D279） | `2f013cb8` |
| [#575](https://github.com/Polalalabear/amidst/pull/575) | 舊工作台 `frontend/workbench/` 與 Office 舊啟動器下線（R1） | `59782b1d` |
| [#586](https://github.com/Polalalabear/amidst/pull/586) | 報告第 5 章 WP5 數字（#581） | `bd1dc614` |
| [#587](https://github.com/Polalalabear/amidst/pull/587) | LIVE A/B v2.1（C-5 補定義）＋重新取得契約 v1（#585） | `590afb34` |
| [#590](https://github.com/Polalalabear/amidst/pull/590) | R2 文件封存、R3 ledger、進度導覽、工作清單指向 #93（#580） | `703ce625` |
| [#595](https://github.com/Polalalabear/amidst/pull/595) | Office 補列檔下線（#579） | `6bf287d7` |
| [#559](https://github.com/Polalalabear/amidst/pull/559) | 即時模式偵測率＋隔離 demo 啟動入口（Codex，#552、#555） | `894bdd9e` |

**開著的 PR：**

| PR | 分支 @ head | CI | 狀態 |
|---|---|---|---|
| [#564](https://github.com/Polalalabear/amidst/pull/564) | `claude/feat-workbench-v2-ux` @ `a2c80351` | 綠 | Draft；審查 APPROVE（D280）；D302 鏡頭改名已推；**等使用者看五點截圖**（`local/evidence/wb2-ux-564-20261118/`（SHA256SUMS.txt `4eb1e6dcd8617f14d5a072c884bc8d18902f8944bdf5a7d79f565d3f64b8de2e`）），OK 就合併 |
| [#584](https://github.com/Polalalabear/amidst/pull/584) | `codex/feat-live-ab` @ `96c73e0e` | 跑中（快照時） | Draft；Codex 交 #568–#570、#573，#568 C-5 已通過（D309）；預審 P2 兩點交 Codex（D308 第 5 點）；**`rv-584` 正式審查中** |
| [#599](https://github.com/Polalalabear/amidst/pull/599) | `codex/feat-n6-ceiling` @ `3c545fe5` | 綠 | Draft；N6 天花板（#593，CAM_WIDE 天花板平均亮度 137.72→121.25），**`rv-599-603` 正式審查中** |
| [#603](https://github.com/Polalalabear/amidst/pull/603) | `codex/feat-workbench-8cam` @ `7b170f52` | 綠 | Draft；8785 加 8CAM run（#594），獨立埠 smoke 通過；完整 gate 隨 #576；**`rv-599-603` 正式審查中** |
| [#604](https://github.com/Polalalabear/amidst/pull/604) | `claude/feat-recorded-openai-agent` @ `9d23883d` | **紅**（快照時） | Draft；#601 預錄 OpenAI Agent，`agent-openai-601` 還在做 |

**還在的分支**（`gh api .../branches`）：`main`、`mainline/q1q5`、上表五條、`archive/*` 5 條（`archive/amidst-claude-wip-20261109`、`archive/canonical-uncommitted-20261109`、`archive/finalization-uncommitted-20261109`、`archive/local/codex/controlled-scene-real-v2-2a`、`archive/local/phase1/physical-policy-approval`，被 main 引用或沒有其他副本，保留）。

**刪掉的分支**：D278 清理 10 條（`claude/epic-d-agentic`、`argon/424`、`425`、`426`、`429`、`codex/467`、4 條 `archive/local/phase1/*`）；合併後刪 `claude/experiment-record-latex`、`claude/feat-live-ab`（D280）、`claude/feat-retire-old-workbench`（D282）、`claude/feat-research-report`、`claude/feat-live-relock`、`claude/feat-ops-docs`（D305；本 PR 重新開同名分支）、`codex/feat-live-detection`、`claude/feat-retire-office-display`（D308）。

## 2. 先讀

1. `CLAUDE.md`、`AGENTS.md`、`CLAUDE.local.md`（本機規則：協調者只派工，不在 `~/amidst` 改檔）
2. 本文件
3. [#93](https://github.com/Polalalabear/amidst/issues/93) 本文（工作清單）和 D278–D310 的留言（D283 是無編號留言的索引）
4. LIVE A/B：`docs/specs/LIVE_MODE_AB_V1.md`（v2.1）、重新取得契約（#587 合併的檔，見 [#585](https://github.com/Polalalabear/amidst/issues/585)）、Codex 總項 [#566](https://github.com/Polalalabear/amidst/issues/566)
5. 評估方向 D304 與 [#597](https://github.com/Polalalabear/amidst/issues/597) 的錄製指引 v1（[留言 6967247222](https://github.com/Polalalabear/amidst/issues/597#issuecomment-6967247222)）
6. 即時模式背景：`docs/operations/LIVE_MODE_HANDOFF_20261116.md`、`docs/design/LIVE_MODE_LLM_DECISION_V1.md` §0F
7. 前一份交接 `docs/agents/COORDINATOR_HANDOFF_20261117.md` §3（8785 更新流程、前景執行）

## 3. 流程（今天新增的）

沿用前一份 §3 與 `CLAUDE.md`、`AGENTS.md`。今天的補充：

- **工作清單只在 #93 本文**（D281）：派工、取工、更新都在 issue 上做，每件可派的工作都有自己的 issue；brief 指向 issue 編號。狀態要標全：ready／in-progress／review／waiting（寫明等誰、等什麼）／blocked／deferred／done／abandoned（寫原因）／superseded（寫被誰取代）。**做完當下就更新**那一列，並在 issue 留言；完成或廢棄的移到「最近結束」。
- **合併不問使用者**（D305）：審查通過、CI 綠、可合併的 PR 由協調者直接合併（merge commit）並刪掉已合併分支。例外仍要問：使用者要先看截圖的 UI（#564）、8785 pin、付費、刪除原始資產。
- **OpenAI 額度**（D306）：可用約 USD 50，用於專案測試（#597、#601 smoke 等）。每次先 ApiGuard dry-run，在 issue 貼預估與實際花費；**單次預估超過 USD 10 先問使用者**。
- **研究文件分兩份**（D308）：研究紀錄（`docs/research/experiment_record/`，LaTeX）記使用者在專案中提出要記錄和分析的東西，隨進度追加；研究計畫（較嚴謹）最後才動，main 上目前沒有對應檔案（`UNKNOWN`），要做時另開 issue。
- **目前以專案實際運行為主**（D308）：優先 #576、#566、#588、#601、#602（D309 起只做 LIVE 外圍）；研究計畫和跨平台（#598，D304）延後。
- **評估方向**（D304）：LIVE 玩一次錄下玩家軌跡，同一劇本重播（只用規則／LLM 覆核），用 GT 逐 tick 評分（GT 只用於評分）。預錄三事件不再拿來證明 LLM。
- **`gh api -X DELETE` 前加 `PAGER=cat`**，不然 gh 會開分頁器卡住。
- **被 session 事件喚醒的回合不能開 session**，改用提案卡。

## 4. 所有工作，依類型分類

每項分成三組：**現在能做的**、**收尾中的**（等審查、等使用者看圖、等合併）、**還沒做的（含延後）**。

### 4.1 8785 demo

| 組 | 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|---|
| 現在能做 | 8785／8791 更新到 main [#576](https://github.com/Polalalabear/amidst/issues/576)（claude） | 兩介面含 #559、#563、#564、#594 | ready（#559 已合併，D308）。8785、8791 都還在 `e9db4fdf` | 建議等 #564 合併（和 #603 視審查結果）再一起跑 gate；**pin 要使用者核准**；8785 前景重啟 |
| 收尾中 | 預錄模式可切 OpenAI Agent [#601](https://github.com/Polalalabear/amidst/issues/601)／[#604](https://github.com/Polalalabear/amidst/pull/604)（claude） | 四個 run 可選 Agent，預設關、經 ApiGuard | in-progress；Draft #604，**CI 紅**（快照時） | `agent-openai-601` 還在做；交件後派審查；真 provider smoke 先 dry-run，>USD 10 才問 |
| 收尾中 | 8CAM run [#594](https://github.com/Polalalabear/amidst/issues/594)／[#603](https://github.com/Polalalabear/amidst/pull/603)（codex） | 8785 多一個 8 鏡頭 run | review；Draft，CI 綠，獨立埠 8CAM／dependency smoke 通過 | `rv-599-603` 正式審查中（D309）；完整 gate 隨 #576 |
| 還沒做 | 預錄俯視圖改成 LIVE 式 3D 場景視圖 [#605](https://github.com/Polalalabear/amidst/issues/605)（claude） | 只畫系統估計、不畫 GT；先出示意圖 | ready（D310） | 等寫檔名額（快照時三個寫手：#601、交接文件、#602） |

### 4.2 即時模式（LIVE）

| 組 | 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|---|
| 收尾中 | 場景外圍實作 [#602](https://github.com/Polalalabear/amidst/issues/602)（claude） | **只做 LIVE**（操作端與系統端鏡頭畫面）的外圍背景，可走範圍不變；預錄畫面是原始渲染影片，不重新渲染（D309）；前後截圖 | in-progress；示意通過（D307，LOCAL `local/evidence/live-exterior-mock-20261118/`（SHA256SUMS.txt `32b42386683a3372a6048ca4cb65f4edfe584e955293370c955e533fdb3b8727`）） | session `exterior-602` 執行中；和 #593（`codex/feat-n6-ceiling`）協調檔案 |
| 現在能做 | #563 的 P3＋#559 審查 P2-1 [#577](https://github.com/Polalalabear/amidst/issues/577)（claude） | `advisor_model` 非字串、IPv6、缺 `t_capture_ms` 時略過記憶 | ready | 無 |
| 現在能做 | 後台 `/track/*` 端點 [#571](https://github.com/Polalalabear/amidst/issues/571)（codex） | session、Q3 句子接線 | ready（#559 已合併） | 等 Codex 取工 |
| 現在能做 | 重新取得 R1 [#588](https://github.com/Polalalabear/amidst/issues/588)（codex） | tracker 分段門檻、速度預測、門檻量測，重播驗收 | ready | 等 Codex 取工 |
| 收尾中 | 人物不碰撞 [#568](https://github.com/Polalalabear/amidst/issues/568)（codex） | crowd＋sim，C-1～C-8 | review；C-5 通過（D309：無玩家基線 0、`player_phase_shift` 11 次另計、78.7 s 反例保留），在 Draft #584 | `rv-584` 正式審查中 |
| 收尾中 | A 場景＋角色選單＋滑鼠 [#569](https://github.com/Polalalabear/amidst/issues/569)、離線評分 [#570](https://github.com/Polalalabear/amidst/issues/570)、`smoke.mjs` 不寫 `/private/tmp` [#573](https://github.com/Polalalabear/amidst/issues/573)（codex） | — | review；都在 Draft #584 | #584 預審 P2 兩點（評分器在 ACQUIRING／NEEDS_PICK 誤判失聯；tick 層 `gt_visible` 被覆寫，[留言 6967155738](https://github.com/Polalalabear/amidst/pull/584#issuecomment-6967155738)）等 Codex 修 |
| 收尾中 | N6 天花板亮度與接縫 [#593](https://github.com/Polalalabear/amidst/issues/593)／[#599](https://github.com/Polalalabear/amidst/pull/599)（codex） | 材質調整＋截圖 | review；Draft，CI 綠，A4-1 同秒前後截圖已交 | `rv-599-603` 正式審查中（D309） |
| 收尾中 | workbench-v2 五點易用性 [#564](https://github.com/Polalalabear/amidst/pull/564)（claude） | 搜尋 Enter、追蹤分頁搜尋、概況排版、易讀名稱、live 入口 | waiting；審查 APPROVE；D302 改名（室外西側／轉角／轉角廣角）已推 `a2c80351` | **等使用者看截圖**（`local/evidence/wb2-ux-564-20261118/`（SHA256SUMS.txt `4eb1e6dcd8617f14d5a072c884bc8d18902f8944bdf5a7d79f565d3f64b8de2e`）） |
| 還沒做 | #564 的 3 個 P3 [#578](https://github.com/Polalalabear/amidst/issues/578)（claude） | — | blocked | 等 #564 合併 |
| 還沒做 | B 選目標流程 [#572](https://github.com/Polalalabear/amidst/issues/572)、整合驗收 [#574](https://github.com/Polalalabear/amidst/issues/574)（codex） | — | blocked | #572 等 #571；#574 等全部子項 |
| 還沒做 | 重新取得 R2 [#589](https://github.com/Polalalabear/amidst/issues/589)（codex） | 後台接線＋ENTRY 驗收；交件補 `accepted_by: D282` | blocked | 等 #588 |
| 還沒做 | LIVE 錄製與重播 [#596](https://github.com/Polalalabear/amidst/issues/596)（codex） | 玩家軌跡存成可重播劇本＋決定性測試 | blocked | 等 #568、#569、#574 |
| 總項 | LIVE A/B [#566](https://github.com/Polalalabear/amidst/issues/566)（codex） | 雙畫面展示即時追蹤 | in-progress | 看子項 |

### 4.3 預錄模式與 Agent

| 組 | 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|---|
| 收尾中 | #601 預錄 OpenAI Agent | 見 4.1 | 見 4.1 | 見 4.1 |
| 總項 | Agentic epic [#489](https://github.com/Polalalabear/amidst/issues/489)（claude） | 自然語言、數位孿生點選、Agent 實際決策、OpenAI | in-progress；子項勾到 #582 為止 | — |
| 已取代 | WP5 合成題重跑 #592、sol6.1 單獨驗證 #591 | — | superseded（D304，併入 #597；額度不沿用） | — |

### 4.4 評估（難題集）

| 組 | 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|---|
| 還沒做 | LIVE 難題集：規則 vs LLM 重播比較 [#597](https://github.com/Polalalabear/amidst/issues/597)（claude） | 逐案結果、報告素材、demo 並排重播；含「目標不在名單」 | blocked；錄製指引與評分定義 v1 已備（[留言 6967247222](https://github.com/Polalalabear/amidst/issues/597#issuecomment-6967247222)），付費粗估 sol 約 USD 1.6、terra 約 USD 0.8（未 dry-run） | 等 LIVE A/B（#566）、#588、#596 完成；使用者錄難題集；付費先 dry-run |

### 4.5 研究紀錄與報告

| 組 | 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|---|
| 現在能做 | 報告素材 epic [#479](https://github.com/Polalalabear/amidst/issues/479)（argon／claude） | 持續追加「報告素材」留言 | in-progress；第 5 章 WP5 數字已合併（#586） | 無 |
| 還沒做 | 研究紀錄追加 | 使用者提出要記錄的項目進 `docs/research/experiment_record/` | v4.2 已合併（#558）；之後隨使用者提出追加 | 等使用者提出 |
| 延後 | 研究計畫（嚴謹版） | — | 最後才動（D308）；檔案 `UNKNOWN` | 要做時另開 issue |

### 4.6 流程與整理

| 組 | 工作 | 預計產出 | 目前進度 | 卡住的部分 |
|---|---|---|---|---|
| 收尾中 | 本交接（handoff-1118） | 本文件、CLAUDE.md／AGENTS.md 連結 | 本 PR | 等 CI、協調者合併 |
| 已完成 | 舊工作台下線 R1、Office 補列檔、R2 封存、R3 ledger、#93 工作清單、D 號補編 | — | #575、#595、#590、D281、D283 | — |
| 延後 | 跨平台 [#598](https://github.com/Polalalabear/amidst/issues/598)（claude） | Windows／Linux 跑 demo | deferred（D304） | 使用者決定延後 |

### 4.7 Codex 與 Argon

| 組 | 工作 | 目前進度 | 卡住的部分 |
|---|---|---|---|
| 現在能做（Codex） | #571、#588（ready）；#584 預審 P2 兩點與正式審查的修正 | — | 等 Codex 取工 |
| 收尾中（Codex） | #584（#568–#570、#573）、#599（#593）、#603（#594） | Draft | 正式審查中：`rv-584`、`rv-599-603`（D309） |
| 還沒做（Codex） | #572、#574、#589、#596 | blocked | 見 4.2 |
| Argon | 沒有派工；`owner:argon` 只有 epic #479 | — | 需要時再派 |

## 5. 等使用者決定

> **已過時，見[晚間交接（D311–D330）](#9-晚間交接d311d330)。**以下保留原文。

1. **#564 五點截圖**（`local/evidence/wb2-ux-564-20261118/`（SHA256SUMS.txt `4eb1e6dcd8617f14d5a072c884bc8d18902f8944bdf5a7d79f565d3f64b8de2e`））：OK 就合併。
2. **#576 的 8785 pin**：gate 通過後由使用者在終端核准（`scripts/demo_pin.py approve`）並前景重啟 8785。
3. **#601 真 provider smoke 金額**：先 dry-run；預估 ≤ USD 10 可直接跑（D306），超過才問。
4. **#597 難題集**：使用者要親自錄 LIVE 難題集（LIVE A/B 和 #596 完成後）；付費同上。

快照時 #93 沒有其他 `needs-auth` 項目（#583 已在 D282、D302 全部決定）。

## 6. 給新協調者的第一件事（依優先順序）

> **已過時，見[晚間交接（D311–D330）](#9-晚間交接d311d330)。**以下保留原文。

開始前先用 `gh issue view 93 --repo Polalalabear/amidst --comments` 看 D310 之後有沒有新留言，`gh pr list --repo Polalalabear/amidst` 看 PR 有沒有新進度。

1. **#564**：問使用者看截圖（`local/evidence/wb2-ux-564-20261118/`（SHA256SUMS.txt `4eb1e6dcd8617f14d5a072c884bc8d18902f8944bdf5a7d79f565d3f64b8de2e`）），OK 就合併並刪分支，解除 #578。
2. **#576**：把 8785／8791 更新到 main。照 D269／D270 的 gate 流程（clone 跑 node、focused pytest、`check_demo_dependencies.py --smoke`、real-e2e → `RESULT.txt`），8785 用前景方式重啟（終端分頁「8785 demo」），**pin 要使用者核准**。
3. **#577**：派寫手（#563 的 P3＋#559 審查 P2-1）。
4. **#602**：追 `exterior-602`（只做 LIVE 外圍，D309）的進度，交件後派審查；寫手名額空出後派 #605 示意圖（D310）。
5. **#601**：追 `agent-openai-601` 的進度（#604 快照時 CI 紅），交件後派審查。
6. **Codex**：收 `rv-584`、`rv-599-603` 的審查結果（#568–#570、#573、#593、#594），通過就合併（D305）；#571、#588 和 #584 預審的 P2 兩點交 Codex；給 Codex 的指派寫成可直接貼上的文字。
7. **#597** 在 LIVE A/B（#566）和 #596 完成後才開始。

## 7. Session 清單（快照時）

`list_sessions {"linked": true}` 列得到時以它為準。快照時與前一位協調者（`local_98bbf379-97a0-48c7-9325-c3ae1ceaac25`）連結的 session：

| 名稱 | session id | 狀態 | 內容 |
|---|---|---|---|
| `exterior-602` | `local_ae2d568d-49a9-4cd0-8085-71af26586bf2` | **執行中** | #602 LIVE 場景外圍實作（D309） |
| `rv-584` | `local_5e481ed7-f22f-4762-a0f5-622decdfee18` | **執行中** | #584 LIVE A/B 正式審查 |
| `rv-599-603` | `local_f44c4a73-f4e0-4b26-b09b-5f697b031154` | **執行中** | #599 天花板＋#603 8CAM 正式審查 |
| `agent-openai-601` | `local_2e85950a-dd9b-4df3-8f98-596cff16e6dd` | 閒置（快照時，#604 CI 紅） | #601／#604 預錄 OpenAI Agent |
| `guide-597` | `local_89972c0e-905f-4fab-bc5b-630066ca20ad` | 閒置（完成） | #597 錄製指引與評分定義 v1 |
| `wb2-rename-564` | `local_6fd2a7b7-bed7-4886-9af1-c3692a8a9ae0` | 閒置（完成） | #564 鏡頭改名＋五點截圖 |
| `rv-584-pre` | `local_26295735-4c30-4034-8241-103f47572cf6` | 閒置（完成） | #584 預審（P2 兩點） |
| `rv-559` | `local_663121b7-c5af-40e6-b97e-6359474d0920` | 完成 | #559 正式審查 |
| `office-579-impl` | `local_b756478f-f4df-440a-99fb-2431ccfde1ac` | 完成 | #579／#595 實作 |
| `rv-595` | `local_b104fcbb-1e28-4832-9eb5-a26966092f70` | 完成 | #595 審查 |
| `live-exterior-mock` | `local_012c8dce-5a6d-45f3-a9b2-7cec414e82c1` | 閒置（完成） | #600 場景外圍示意圖 |
| `live-relock-spec` | `local_00a07361-4e84-4384-8ff7-72b3eb029346` | 完成 | #585／#587 |
| `ops-docs-580` | `local_6b6eeddd-8689-4dd0-bb5a-24af35ef6aea` | 完成 | #580／#590 |
| `report-581` | `local_824712e6-8f97-4a9f-b704-56b0858fe621` | 完成 | #581／#586 |
| `inv-582` | `local_8c94e830-ce34-4f41-add7-b50eca31575f` | 閒置（完成） | #582 盤點＋D283 |
| `opus-579` | `local_a25afa7d-960c-4694-8e7e-c92b967d65c2` | 閒置（完成） | #579 Office 8 檔判定 |
| `board-1118` | `local_ea82c502-6f7c-4f0b-8dee-62200bc36099` | 閒置（完成） | #93 改寫成工作清單（D281） |
| `live-ab-spec-v2` | `local_92110ef1-0828-4cb4-94a3-d85b23f7ec76` | 完成 | #567 規格 v2＋Codex 子 issue |
| `retire-old-wb-impl` | `local_d4b1aa96-d6f6-4493-94ff-9540f41d3145` | 完成 | #575 實作 |
| `rv-575` | `local_1d9b5267-0826-4346-b82c-082960c21e00` | 完成 | #575 審查 |
| `rv-564` | `local_4db853ad-4eb1-4074-b06a-a703b4551522` | 完成 | #564 正式審查 |
| `rv-558-v42` | `local_2463ae51-072a-48d0-82f8-2eff90336f86` | 完成 | #558 差異複審 |
| `handoff-1118` | `UNKNOWN`（本 session） | — | 本文件 |

已完成的 session 可在使用者同意後封存。

## 8. D311–D318 補記（2026-11-18，事實補記；前文不改）

> **已過時，見[晚間交接（D311–D330）](#9-晚間交接d311d330)。**以下保留原文。

快照：`main` 頭為 `b98fac2a`（#613 merge）。進度導覽已依 GitHub 逐項批次補列到 #613（見 [Q1Q5_PROGRESS.md](../operations/Q1Q5_PROGRESS.md)）。

| 決策 | 內容 | 結果 |
| --- | --- | --- |
| D311 | 收尾交接：#606、#599 合併；#584、#603 NEEDS_CHANGES；#564、#607、#604 等使用者 | #606 `b7ca80f2`、#599 `3c3e1267` 已合併 |
| D312 | 使用者同意合併 #564、#607 | #564 `eb06e9a0`、#607 `7f8e8443` 已合併（#602 關閉） |
| D313 | #604 逾時預設由使用者決定為每輪 8000 ms、總共 24000 ms | 已由 D317 指出 P1（LOCAL 參數檔仍 2000／5000），修後合併 |
| D314 | 新協調者派工：#604 修正、#577＋#578 P3、#584／#603 複審、#588 判定、#571 改走法 | #577＋#578 合併（D317）；#584、#603 合併（D315）；#604 合併（D318） |
| D315 | #584 `81ba829d`、#603 `3b5a987a` 合併；#571 改由 Codex 從最新 main 重開 `codex/feat-live-ab` 另開 Draft | #584、#603 已合併；Draft #610 為新開（待審） |
| D316 | Opus 判定 #588 有條件允許（gate 內唯一群可走 short_gate）；#605 照示意圖做 | #611 `4bf9b5ed` 已合併；#613 實作完成 |
| D317 | #609 `fb4b99b9`（#577、#578 P3）、#611 合併；#604 Opus NEEDS_CHANGES（P1） | #609、#611 已合併；#577、#578 關閉 |
| D318 | #604 `62da6464`、#613 `b98fac2a` 合併（#601、#605 關閉）；8785／8791 由 #576 更新到 `b98fac2a`，gate 後使用者核准 pin | #604、#613 已合併 |

目前等待（事實）：

- **使用者**：#576 的 8785／8791 pin 核准（gate 通過後）。
- **Codex**：#608（#588 relock R1，D316 驗收 B4 ≥58/60、錯接 0）、#610（D315 的 #571 端點 Draft）、#589、#596、#612（est_xy，#605 3D 視圖的估計位置）、#594（8CAM run，#603 已加入 A4-1-8CAM，是否關閉待確認）。
- **Claude**：#597（LIVE 難題集）、#576（8785／8791 更新，gate 後）。
- **未排程**：#598（跨平台，延後）、#566 母 issue（子項 #571、#572、#574 未完成）。

本補記不改 #93 的決策紀錄；D 編號下一個為 D319。

## 9. 晚間交接（D311–D330）

2026-11-18 晚間快照，取代 §5、§6 與 §8 的狀態。數字和 SHA 已在撰寫時用 `gh`、`git` 核對。**新的協調者對話全程用繁體中文回覆**（D255）。協調者的 D331（難題集全由腳本產生、#608／#617 NEEDS_CHANGES、磁碟盤點結果）已貼 #93；本交接記為 **D332**，新協調者從 **D333** 起。

### 9.1 現況

| 項目 | 值 |
| --- | --- |
| `main` | `7393bf62`（#615 merge） |
| 8785 pin | `b98fac2a`（`local/demo-pin.json`，gate `local/evidence/gate-576-20261118/RESULT.txt`（SHA-256 `60201b729e7c50eccfec1709e52803038a2425adf6c7f0fe14df15c165b8f927`），D324）；`~/amidst` 工作樹在 `b98fac2a`，終端分頁「8785 demo」前景執行 |
| 8791 | `50f2fd14`（#618 merge），`local/runtime/live-main`，用 `local/runtime/start_live_8791.sh` 啟動（D329） |
| 下一個決策編號 | D331（協調者）、D332（本交接）→ 新協調者用 **D333** |
| 磁碟 | 可用約 7–8 GiB（低於 9 GiB 不開第三個寫手，低於 5 GiB 停工）；盤點已完成：LOCAL `local/evidence/disk-inventory-20261118/INVENTORY.md`（SHA-256 `5afa743861e0c6d1f25fdee2e0f8840801e16bab5a65ff4c92ba20dafe6b7daa`，Haiku low，唯讀，未刪任何東西）。A 類約 1.77 GiB（npm／uv／torch／pip 快取＋2 個殘留 clone）等使用者授權（D331-3），殘留 clone 要等所有 session 結束才刪；B 類走 Sonnet 驗證 → Opus 決定 → 使用者授權 |
| OpenAI 額度 | D306 約 USD 50；今天花 USD 0.41（D325 預錄三事件分析）＋診斷約 USD 0.006 |

### 9.2 所有工作，依類型分類

#### 即時模式（LIVE）

| 項目 | 預計產出 | 目前進度 | 卡在哪裡／在等誰 |
| --- | --- | --- | --- |
| #588／#608 重新取得 R1 | relock R1 合併，R-6、R-5a 過，runtime 預設不變 | D326：R-5 拆成 R-5a（相對 main 不新增錯接，R1 閘門）與 R-5b（LLM 救回同衣色錯接，移到 #597）。Codex 回報驗證完成（head `533b4e99`）。**NEEDS_CHANGES，原因是和 main 衝突，等 Codex 合 main**（D331-2；Sonnet [#608 留言](https://github.com/Polalalabear/amidst/pull/608#issuecomment-6980353441)）：數字核對全過，但 P1-1 `src/amidst/live_mode/tracker.py` 與 main 有語意衝突（main 已加 `target_color`、`project_detections()`、`seed()`、`_result(seen)`），合併 main 後要重跑 `replay_relock.py`、`replay_advisor.py`、逐位元組比對與 `pytest tests/live_mode`；P2 兩點、P3 四點；另有三個給 Opus 的問題 | **Codex**（用 merge commit 合 main 後重驗重送）→ Claude 複審；審查留給 Opus 的三題要協調者分派（R-5a 的 main 基準是否改同程式重播、NEEDS_CONFIRM 與 #610／#611 的銜接、接受 5 筆已知錯接是否已有 D 編號——D326 已記錄使用者同意 R-5 改寫） |
| R-5a／R-5b 契約條文 | `docs/specs/LIVE_MODE_RELOCK_V1.md` 補 R-5a、R-5b | 未開始 | 派 Claude 文件寫手（可和 #610 Opus 三點的 v2.2 規格補丁同一個 PR，D323） |
| #589 重新取得 R2 | 後台接線＋ENTRY 排程驗收 | blocked | 等 #608 合併 |
| #566 A/B 雙畫面（母） | 選角色、B 選目標、不碰撞 | #610 已合併（`118c2035`，D323）；#571、#572 由 #610 完成，本交接已關閉 | 等 #617、#574 |
| #617 pass 規則＋#596 錄製重播 | D327 pass 規則（只結束從未進入 2r 的 pass）＋確定性錄製重播 | Draft，head `50164136`，CI 綠；Codex 自報 C-2／C-6 回綠。**NEEDS_CHANGES，原因是和 main 衝突，等 Codex 合 main**（D331-2；Sonnet [#617 留言](https://github.com/Polalalabear/amidst/pull/617#issuecomment-6980418787)：程式核對通過，交接文件也過期） | **Codex**（合 main 重送）→ Claude 複審，通過就合併（D305） |
| #574 整合驗收 | A/B 整合、瀏覽器驗收、handoff 文件 | blocked | 等 #617 |
| #619 室外遠端目標偵測失敗（CX-L8） | 室外遠處目標能偵測與追蹤（難題集前置條件，D330-c） | 新開，`ready` | **Codex** |
| LIVE A 選單工作台風格 | — | #618 已合併（`50f2fd14`，D329），8791 已更新 | 無；8785 的轉址修正等下一次 pin |

#### 難題集與 LLM 價值證明

| 項目 | 預計產出 | 目前進度 | 卡在哪裡／在等誰 |
| --- | --- | --- | --- |
| #597 LIVE 難題集（CL-B11） | 規則 vs LLM 重播比較，證明 LLM 價值 | 事件表、答案表、腳本操作者已合併（#615，`7393bf62`，D330）。D330 三個決定：(a) H1、H4 以不計 CAM_ENTRY 的讀法為正式判定，**要驗證 ENTRY 畫面沒有進入追蹤或 LLM 覆核輸入**，有就改回嚴格讀法；(b) 開場就通過的 3 段改路線，其餘標註前置條件；(c) 室外遠端 → #619。**D331-1：難題集全部改由 Claude 的腳本操作者產生**（使用者不親自玩），H2（相似人物交錯）、H3（不照路線）也寫成 `?script=` 路線；報告要聲明所有段落都是照規則弱點設計的腳本、沒有真人的不可預測性 | `hardset-597-plan` 正在 `claude/feat-live-hardset` 做 D330 (a)(b)＋D331-1 → 交件後派審查、合併；#596（在 #617）合併後接錄製；然後跑規則 vs LLM（付費先 ApiGuard dry-run，單次 > USD 10 要問） |
| 預錄三事件分析（D325、D328） | 規則 vs LLM 在 A4-1、B4-1、B-05 的差異 | 完成：LLM 與規則相同（A4-1 0.970、B4-1 0.906；sol 在 B4-1 一次 0.901），題目太簡單；B-05 沒有 decider 注入點。報告 LOCAL `local/evidence/eval-recorded-llm-20261118/REPORT.md`（SHA-256 `2f6bd7c61c16aa158515e612c03b06c2eb98c38c6c16a6ef91c520c9e6013b31`） | 後續：`INVALID_RESPONSE`（`reason_codes` 超過 4 個）的提示修正，未開 issue |
| #620 CL-B16 Q2 Agent 開關 | 8785 的 Agent 開關（#604）在 A4-1、B4-1 可用；B-05 顯示「不適用」 | 本交接開的 issue（引用 D328）：三個事件回 `TRACKING_SCOPE_MISSING` | 派 Claude 寫手（`claude/feat-recorded-openai-agent`） |

#### 8785 預錄 demo

| 項目 | 預計產出 | 目前進度 | 卡在哪裡／在等誰 |
| --- | --- | --- | --- |
| 已合併 | — | #604（OpenAI Agent，D313 逾時 8000／24000 ms，`62da6464`）、#613（3D 場景視圖，2D 為預設，`b98fac2a`）、#603（A4-1-8CAM，`3b5a987a`）、#609（`fb4b99b9`）、#616（`d3dd2d65`） | — |
| #612 est_xy（CX-8E） | 預錄模式提供系統估計位置給 3D 視圖 | Codex 進行中，還沒開 PR | **Codex** |
| #594 其餘 8CAM run（CX-8C） | workbench-v2 加其餘 8CAM run | Codex 進行中 | **Codex** |
| 下一次 8785 更新 | pin 更新到含 #618 轉址修正、#617、#612 的 main | 未開始 | 等 #617、#612 合併；照 D269／D270 gate 流程：gate 的 `RESULT.txt` **每行必須以 PASS 結尾**（D324 教訓），**使用者**在終端執行 `scripts/demo_pin.py approve`，8785 前景重啟 |

#### 流程與整理

| 項目 | 預計產出 | 目前進度 | 卡在哪裡／在等誰 |
| --- | --- | --- | --- |
| 合併規則 | — | D305：審查過＋CI 綠就直接合併並刪分支；UI 要使用者先看截圖；pin、付費、刪原始資產要問 | — |
| gate 檔格式 | — | D323：協調者替 gate 檔改格式被安全機制擋下；gate 檔只能由產出的 session 重寫 | — |
| 磁碟清理 | 釋出空間到 ≥ 9 GiB | Haiku 盤點完成（見 9.1） | A 類約 1.77 GiB 等**使用者**授權（殘留 clone 等 session 結束）；B 類 Sonnet 驗證 → Opus 讀原始證據決定 → **使用者**授權並在自己的終端刪除 |
| 冗餘程式盤點 | 沒被引用的模組／腳本清單 | 延後（D319） | 等 #608、#571（已由 #610 完成）、#612 合併 |
| #598 跨平台 | — | 延後 | — |
| 進度導覽 | — | 本交接 PR 批次補列到 #620 | 下一批補列本 PR 自己的列 |

#### Codex 與 Argon

- **Codex** 正在做：#608（合併 main 重驗）、#617（含 #596）、#612、#594、#619。
- **給 Codex 的待貼文字**（還沒貼，交使用者轉給 Codex）：

  > 使用者桌面在 live 測試時一直彈出 Chrome 視窗。請把 live 測試（node／瀏覽器驗收腳本）預設改成 headless，只有明確加旗標時才開有視窗的瀏覽器。改在你下一個 LIVE PR（#617 或 #608）裡，並在實際產出紀錄寫明。

- **Argon**：#479 研究紀錄（沒有變動，沒有派工）。

### 9.3 新協調者的第一件事（依優先順序）

開始前先 `gh api "repos/Polalalabear/amidst/issues/93/comments?per_page=30&page=15"`（`gh issue view 93 --comments` 在 444 則留言時會逾時）看 D332 之後有沒有新留言，`gh pr list --repo Polalalabear/amidst` 看 PR 進度。

1. **#608、#617**：兩者都是 NEEDS_CHANGES（和 main 衝突）。Codex 合 main 之後派 Sonnet 複審，通過就合併（D305）；#608 審查留給 Opus 的三題要派。
2. **難題集 PR**：`hardset-597-plan`（`claude/feat-live-hardset`，D330 (a)(b)＋D331-1 全腳本）交件後派審查、合併。
3. **磁碟**：A 類約 1.77 GiB 問使用者授權；B 類交 Sonnet 驗證、Opus 決定，使用者授權後由使用者刪除。
4. **#620 CL-B16**：派 Sonnet medium 寫手。
5. **下一次 8785 更新**：#617、#612 合併後照 gate 流程。

### 9.4 Session（快照時，與前一位協調者連結）

以 `list_sessions {"linked": true}` 為準。快照時仍在執行：`disk-inventory`（`local_0808ab32-1f79-4c8b-88e7-db04514ffcc5`，盤點已產出）、`rv-608-617`（`local_fe212872-521f-436b-8939-8220b24e2c41`，#608、#617 結論都已貼）、`hardset-597-plan`（難題集路線修正＋全腳本）。閒置：`opus-588-gate`、`mock-605-3d`、`board-d315`、`576-8785-8791-main-gate`、`eval-recorded-llm`。其餘已完成，使用者同意後可封存。
