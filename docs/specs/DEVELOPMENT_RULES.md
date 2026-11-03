# Development rules / 開發與文件維護規則

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

本文件整理既有工作規則，不新增研究需求或改變架構。現行版本對齊 [#93](https://github.com/Polalalabear/amidst/issues/93) 的 D104～D108（2026-11-01）。需求與模組責任依 [Q1–Q5 產品規格](Q1Q5_PRODUCT_SPEC.md)，權威文件、模組邊界與不偏離規則依架構基準 [#306](https://github.com/Polalalabear/amidst/issues/306)，已採用的決策依 #93；`PRD.md`、`SYSTEM_DESIGN.md`、`ISSUES_AND_DECISIONS.md` 已歸為歷史（D91-2）。發現重大衝突先詢問，不自行改寫規格。過時的文件、PR、議題與分支列在 [廢棄／過時索引](../operations/DEPRECATION_INDEX_20261101.md)。

### 文件分工

| 文件 | 存放內容 | 不放入 |
| --- | --- | --- |
| `specs/Q1Q5_PRODUCT_SPEC.md` | Q1–Q5 需求、架構、模組責任、資料流 | 開發紀錄、每次 commit 或測試結果 |
| `contracts/*.md` | 實際資料契約與模組介面（現行版本與 ref 見 #306） | 測試成功日誌 |
| #93 決策紀錄 | 使用者決策與 Claude 低階定案（D104-3） | 開發日誌、未採用方案冒充決策 |
| `DEVELOPMENT_RULES.md`、`AGENTS.md`、`CLAUDE.md` | 持續適用的工程、流程與文件維護規則 | 當次工作進度、歷史驗證結果 |
| `operations/Q1Q5_PROGRESS.md` | 每個 PR 與議題的分類與狀態 | 即時待辦清單、未完成工作冒充完成 |
| `agents/COORDINATOR_HANDOFF_*.md` | 當前狀態、有效待修項目、續作入口及階段性暫緩項目 | 已完成細節、已解問題、完整歷史與重複規則 |
| `operations/DEPRECATION_INDEX_*.md`、`archive/ARCHIVE_*.md` | 已過時或封存的文件、PR、議題、分支 | 現行規則 |
| PR 說明的「實際產出 / Actual output」 | 該 PR 的實際命令、結果與證據（D104-5） | 計畫或預期結果 |
| `../../data/README.md` | 已物化資料的日期化盤點與發布邊界 | 尚未產生的 dataset 被當成既有資料 |

工作完成並驗證後，把結果記入該 PR 的 Actual output；已解決或已失效的 handoff 項目移除，不留「已完成 TODO」。有效未解問題不能只因整理文件而消失；若被暫緩，標明暫緩，不標為解決。歷史紀錄使用當時日期／commit／證據，不能改寫成今天重新驗證的結果。

文件正文放在 specs／engineering／research／operations／history；只由 `docs/README.md` 提供總索引，不另建每分類 README 或逐檔轉址文件。根目錄例外只保留實際 hash／runtime 綁定的檔案或必要路徑別名；新增文件直接使用分類路徑。

### 開發與 Git

- 開始先確認實際工作目錄、`git status` 與 `git branch`；保留使用者及其他工作的未提交修改。
- 本機 checkout（D108-4）：新 session 從乾淨的共用 checkout `~/Developer/amidst-q1q5`（`mainline/q1q5`）開始，不在其中切分支或改檔；寫入在另外的 clone 進行（Claude 用自己 scratchpad 的 `git clone --shared`，用完刪除）。舊的 `~/Developer/amidst`、`~/Developer/amidst-claude` 原封不動，只 fetch。不建 worktree、venv 或 raw 副本；單一 immutable 資產來源照舊。同時寫入的 session 每邊最多 3 個（含子代理），檔案不重疊；可用磁碟低於 9 GiB 不開第 3 個，低於 8 GiB 全部停止。刪除／archive 既有 checkout 和資產須有對應授權。
- 2026-10-14 已授權不再使用的 worktree／封存／試跑實體清理：僅保留文件、manifest／hash及精簡收據，不再製作或移存大型 raw 封存。先核對是否仍供現行服務、共享工作、demo或復原使用；原始來源、現行資料與未提交變更仍保留。刪除舊產物後同步標明歷史 locator 退役，不承諾只靠文件可完整復原。
- Python 全部使用 uv；主要依賴來源為 `pyproject.toml`、`uv.lock`，不以 requirements.txt 取代。
- 交付以 feature 為單位（D104-1、D105-7）：一個 feature 一個整合分支、一個 PR（base `codex/q1q5-staging`），子 PR 依該 feature 歸併留言的順序以 merge commit 合入；feature 內仍以可驗證的 milestone 獨立 commit。
- 只 stage 本任務檔案；不 `reset --hard`、force push、rewrite history 或 rebase 使用者 commit。Push／PR／merge 需要對應明確授權；合併只用 merge commit（不 squash、不 rebase），且只在使用者批准一批合併後由協調者執行（D104-4）。
- 遇到重大場景語意、walkability、camera convention、公開介面、指標或 GT isolation 問題，先停止該不確定部分並詢問；可依既有規格解決的小問題不必擴張設計。

程式實作的驗證以任務或 feature 議題列出的整合驗收為準（D104-2）：

```sh
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q <議題列出的 -T 測試>
uv run python -m pytest -q <議題列出的 focused 測試>
python scripts/check_architecture_guard.py --base origin/codex/q1q5-staging --report <報告路徑>
git diff --check <merge-base> HEAD
```

另含議題列出的 GT 隔離檢查與適用時的 #127 conformance kit。不跑 full suite，除非任務明寫。要等外部回件、使用者 gate 或 LOCAL 正式資料的命令寫 `NOT_RUN` 與 gate，不寫 PASS（D105-7-8）。純文件整理只做相稱的 diff、連結與內容一致性檢查；若沒有重跑程式測試，引用既有結果時標明歷史 checkpoint，不宣稱本次執行。

### 共用網頁工作台

- Amidst 網頁唯一的 UI 入口是 `frontend/workbench-v2/`（#306 §2）；既有及後續需要頁面展示的功能均接入它的導覽、元件及流程。它只經 HTTP API 或錄製回應取資料，不直接讀 GT 或劇本。`frontend/workbench/`（[共用工作台](../engineering/SHARED_WORKBENCH.md)）已是歷史。
- 新場景使用 catalog／adapter，新增展示、調查、測試或人審功能擴充共用工作台。研究／管理權限由後端限制，工作模式及產品的輸入模式／凍結階段不改變權限。
- 遷移既有頁面時重用資料與後端服務，保留原介面、來源綁定及歷史驗證；以局部查詢與獨立 milestone 驗證遷移。未遷入的功能在 handoff 明列，不把主入口決策或舊頁面的 PASS 當作遷移完成。

### 研究有效性與資產

- 原始 `.blend` 保持不變；研究副本與生成資料依既有隔離決策處理。Audit／export 不儲存來源；清理、刪除、修改來源資產或 render 必須另外明確授權。
- GT 僅供 simulation/export、evaluation、debug visualization；不得進入 inference、graph、candidate ranking、semantic reasoning 或 path score。Domain 只放 schema／interface；Agent 不做 geometry、pathfinding 或 collision checking。
- 依 PRD 保留物理硬限制、多解 Top-K 與 provenance；Phase 2 僅保留 schema／interface，Semantic Ranking 在 deterministic closed loop 完成後才考慮。Q1–Q5 主線的 Agent 切鏡例外見本節 D64 條，排序仍屬決定性模組。
- 研究配置與合成 fixture 不等於核准的 school walkability、正式資料集或 benchmark。驗證點可見性、技術 render 成功、影像可用性與正式研究驗收是不同證據，不互相代替。
- 規則與永久決策不要複製到每次 handoff。當前授權範圍／暫緩狀態留在 handoff，完成與驗證紀錄留在 work log；不因文件整理擴大實作或發布權限。
- 工程可先以 synthetic/mock 調用、查找與 replay 並行推進，不以正式 Phase 1 全 Exit 作工程前置；工程通過不改寫正式研究狀態。Agent 的操作资源與輸出契約見 [工程邊界](../engineering/AGENT_RETRIEVAL_BOUNDARY.md)。不串接外部模型 API；唯一例外是本節 D107 條（俯視圖示意）。2026-10-11 已授權圖形/label 前處理、明確 Agent I/O、階段性模擬資料庫併發與差異文件；此 token 兜底原型不代表已量測 token 減量。
- 真實攝影機串流保留 FUTURE；正式帳號與部署保留 DEFERRED。專案媒體為 Blender camera 來源影像與依原 `.blend`／預設平滑展示材質的模型；替代 procedural RGB 必須另標來源，材質不改 scene 或 authority。
- Blender 基底畫面檢索只使用來源綁定的安全 camera/time/media 欄位、實際 RGB pixels及獨立合法校正／floor plane；不讀 renderer 的 GT、trajectory、visibility、depth或預先給定 observation 答案。基底演算法模式不經 Agent 決策；像素元件／local tracks與使用者行為意圖不得改稱人物或行為已確認。
- Q1–Q5 主線例外（D64，2026-10-20）：僅 Q1–Q5 主線可由 Agent 在合法 top-k 候選內決定是否切鏡。候選集合與排序仍由決定性模組（兩層圖與 D28）產生，Agent 不排序、不增刪候選，也不做 geometry、pathfinding 或 collision checking。Agent 依序向候選取偵測與顏色證據；輪數與時間有上限（由 Codex 提案、使用者核定），超過上限或失敗時由決定性規則兜底。全程記錄 prompt、模型 digest、決策來源與 fallback 原因；GT 仍不得進入 Agent。第一版只用 RT-DETR＋HSV，不用看圖模型（VLM），不接外部模型 API。此例外不延伸到 Q1–Q5 主線以外的流程。
- 外部模型限定例外（D107，2026-11-01）：追蹤模式的俯視圖可在物理預測（主要、預設開、離線可重現）旁顯示 OpenAI 推測（輔助、預設關，標「外部模型推測（非系統判斷）」）。只用於俯視圖示意，不進評分、不進 Q1～Q5 判斷、不影響排序與 fallback。只送結構化資料白名單，不送影像、GT、劇本、渲染軌跡、visibility、depth；回放只送當下時刻以前的資料。每次檢索最多 1 次呼叫、失敗重試 1 次、相同輸入快取、逾時約 5 秒、每個 session 有呼叫上限，任何錯誤退回物理預測。demo 播放錄製的回應，不現場呼叫。key 只在使用者本機環境變數 `OPENAI_API_KEY`，程式只從環境讀；agent 不讀取、不印出、不寫入任何檔案、PR 或留言；自動測試一律用假回應。此例外不延伸到俯視圖以外。
- source model 的 subset/crop 與平滑材質維持 PARTIAL display context，不擴大整場幾何、可行走、遮擋或碰撞authority。校正、plane與clip distances必須使用同一明確尺度；不能只改單位標頭或拿landmark plane代替接地面。
- 分層資料流明列ACTUAL_BLENDER、SUBSTITUTE、DEFERRED及各自source/model/run/clock/hash；替代Graph／重建與歷史測試只用獨立fixture，不回填實際Blender run。未物化的物理曲線／影片保持未完成。公開PNG可剝除文字metadata但須保留像素chunks、核對原始／served hashes，不能修改原影像或洩漏private locator。
- 新歷史版本保存修改部分及 source/base/parent/result hashes；以 baseline 還原。發布只包含可核對的差異文件、code/docs/tests/curated receipts，不直接複製 `.blend` 或上傳 raw DB／GT／影像。既有歷史與已授權隔離實驗保留。
- 工作台以穩定 3D 為主，按需標示登錄節點／邊；事件 ID 只在專用 log 顯示，內部 references 保留。Agent 不得全量掃描，未知 label 明示需要補充輸入。
- Blender物理曲線區分RGB觀測、地板投影、短缺口插值與有限差分速度；缺失／無效投影／超過設定限制保持斷線，不外推或跨鏡頭合併身分。設定速度上限與像素heuristic uncertainty不得冒稱人體模型、機率或誤差界。窄範圍曲線與完整預先物化影片分別標明鏡頭／時間；GET只驗證／讀取，不產制。影片缺失或過期不阻斷有效曲線，且不得改用其他source/run補缺。
- 跨鏡頭工程可在同site/run/clock內產生受限關聯假設，不等於合併已確認身分。保留多解與未關聯基線、同期原投影、原局部硬缺口、未知幾何權限及搜尋截斷。重疊須有同步位置支持，整條候選路徑須檢查時間／速度一致性。完整來源排名與窄窗曲線切片各自標明；事件reference不因切窗重編，影片素材K／鏡頭／時間與本次查詢及rank各自標示。
- 來源物理篩選只用hash綁定且purpose／authority核准的支撐面、人體政策與精確碰撞元件。部分碰撞scope可拒絕已知名義路徑矛盾，不能證明無碰撞。門洞、走廊連接與未分類mesh的未知部分保持UNKNOWN；名稱、annotation box或display crop不升權。長缺口示意線不能當實際動線硬判穿牆，partial支撐缺連接不能當完整不可達證明。每解保留PASS／REJECT／UNKNOWN理由與範圍，物理工程重排不改寫正式幾何／身分／行為核准。

## English

These are existing engineering and documentation rules, not new requirements, aligned with decisions D104–D108 on [#93](https://github.com/Polalalabear/amidst/issues/93) (2026-11-01). The [Q1–Q5 product specification](Q1Q5_PRODUCT_SPEC.md) owns scope and architecture, the architecture baseline [#306](https://github.com/Polalalabear/amidst/issues/306) owns authoritative pins, module boundaries and no-deviation rules, and #93 holds adopted decisions; `PRD.md`, `SYSTEM_DESIGN.md` and `ISSUES_AND_DECISIONS.md` are historical (D91-2). Ask before resolving major conflicts through design changes. Superseded documents, PRs, issues and branches are listed in the [deprecation index](../operations/DEPRECATION_INDEX_20261101.md).

Keep durable rules here and in AGENTS.md/CLAUDE.md, each PR's completed work and evidence in its own Actual output (D104-5), current unresolved/actionable state in the newest coordinator handoff (`docs/agents/COORDINATOR_HANDOFF_*.md`), PR and issue status in `docs/operations/Q1Q5_PROGRESS.md`, contracts in `docs/contracts/` (current refs on #306), and materialized-data inventory in [data/README](../../data/README.md). `WORK_LOG.md` and `CODEX_HANDOFF.md` are historical. Move verified completion into the log and remove resolved/stale handoff items. Deferred is not resolved. Preserve genuine open issues and bind historical checks to their original date/checkpoint.

Store maintained text in the five category folders and use only `docs/README.md` as the index. Do not add category READMEs or per-document redirect pages. Root exceptions must serve an actual hash/runtime binding or required path alias; new documents use category paths directly.

Verify workspace, Git status and branch before work; preserve unrelated changes. Use uv, pyproject.toml and uv.lock. Deliver by feature: one integration branch and one PR per feature (base `codex/q1q5-staging`), with sub-PRs merged in by merge commit in the order of the feature's merge-plan comment; inside a feature, validate and commit each milestone separately. Stage narrowly; do not reset, force-push or rewrite user history. Publication requires explicit authorization; merges use merge commits only and happen after the user approves a batch (D104-4). Code checks are the integration acceptance listed above (`-T` with `AMIDST_REQUIRE_IMPL=1`, focused tests, the architecture guard, GT isolation, `git diff --check`; no full suite unless the task says so; gated commands are `NOT_RUN`, not PASS). Documentation-only changes use proportionate diff/link/consistency checks and must not claim an old test run as new.

Checkouts (D108-4): new sessions start from the clean shared checkout `~/Developer/amidst-q1q5` (`mainline/q1q5`) and do not switch branches or edit files there; writing happens in a separate clone (Claude: a scratchpad `git clone --shared`, deleted when done). The old `~/Developer/amidst` and `~/Developer/amidst-claude` stay untouched except for fetch. No worktrees, venvs or raw copies; keep one shared immutable asset source. At most three writing sessions per side (sub-agents included) with non-overlapping files; below 9 GiB free do not start a third, below 8 GiB all writing stops. Existing assets/checkouts are not deleted or archived without authorization.

Use `frontend/workbench-v2/` as the only Amidst web entry (#306) for existing and future presentation,
investigation, testing and human review; it reads data only through the HTTP API or recorded responses,
never Ground Truth or scripts. `frontend/workbench/` is historical. Extend its shared navigation, components and scene
catalog/adapters. Enforce Research/Management access on the server; work modes and product
input/frozen stages do not grant permissions. Reuse existing backend/data contracts during
migration, preserve source-bound history, validate each bounded migration milestone and keep
unmigrated capabilities explicit in the handoff.

Local synthetic/mock engineering proceeds alongside formal Phase 1 research without making
engineering passes formal acceptance. Follow the [Agent retrieval boundary](../engineering/AGENT_RETRIEVAL_BOUNDARY.md).
No external model API is connected, except the D107 top-view illustration described below. The 2026-10-11 instruction authorizes bounded graph/label
preprocessing with explicit Agent I/O, phased simulated SQLite concurrency and delta documents;
this does not establish measured token savings. Real camera streaming is FUTURE; accounts and
deployment are DEFERRED. Blender camera images and source-bound smooth model presentation keep
their simulation provenance. New history stores changed parts and binding hashes, with no raw
DB/GT/media/`.blend` publication. Stable 3D is primary; event IDs appear only in dedicated logs.

Blender baseline frame retrieval reads only sanitized source-bound camera/time/media inputs,
actual RGB pixels and independently legal calibration/floor geometry. It does not read renderer
truth, trajectories, visibility/depth or precomputed observation answers, and does not use an Agent
to decide. Pixel components/local tracks and behavior intent do not confirm people or behavior.
Q1–Q5 mainline exception (D64, 2026-10-20): only on the Q1–Q5 mainline may an Agent decide
whether to switch cameras, and only among legal top-k candidates. Deterministic modules (the
two-layer graph and D28) still generate the candidate set and its order; the Agent does not
rank, add or drop candidates, or do geometry, pathfinding or collision checking. The Agent
queries candidates in order for detection and color evidence under round and time limits
(proposed by Codex, approved by the user); past a limit or on failure, deterministic rules decide.
Record the prompt, model digest, decision source and fallback reason throughout; Ground Truth
never enters the Agent. The first version uses only RT-DETR plus HSV, with no vision-language
model and no external model API. The exception does not extend beyond the Q1–Q5 mainline.
External model exception (D107, 2026-11-01): the tracking top view may show an OpenAI estimate
(secondary, off by default, labeled as an external-model estimate, not a system judgment) next to
the physical prediction (primary, on by default, offline and reproducible). It is an illustration
only and never enters scoring, Q1–Q5 judgments, ranking or fallback. Only a whitelisted structured
payload is sent: no images, Ground Truth, scripts, renderer trajectories, visibility or depth, and in
playback only data up to the current time. At most one call per search with one retry, caching,
about 5 s timeout and a per-session cap; any error falls back to the physical prediction. The demo
replays recorded responses. The key lives only in the user's `OPENAI_API_KEY` environment
variable; agents never read, print or write it anywhere, and automated tests use fake responses.
Model crops and smooth materials remain PARTIAL display context, without whole-scene geometry,
walkability, occlusion or collision authority. Normalize camera, floor and clips consistently;
do not relabel units or substitute a landmark plane for ground contact.

Label actual Blender, substitute and deferred layers with independent source/model/run/clock/hash
bindings. Substitute Graph/reconstruction/history tests do not fill a Blender run's missing results;
unmaterialized physical curves/video remain unfinished. Public PNG text metadata may be removed
while preserving pixel chunks and validating original/served hashes. Keep original images intact
and private locators out of public media/JSON. See the
[Blender frame contract](../engineering/BLENDER_CAMERA_FRAME_RETRIEVAL.md).

Blender motion curves distinguish observed RGB, floor projections, bounded interpolation and
finite-difference speed. Keep invalid/missing/over-cap intervals disconnected, without
extrapolation or cross-camera identity merging. Configured caps and heuristic uncertainty are
not human physics, probabilities or error bounds. Label narrow curve scope separately from full
pre-materialized media scope; GET verifies/reads and does not encode. Missing/stale video must
not block valid curves or substitute another source/run. See the
[motion contract](../engineering/BLENDER_MOTION_RECONSTRUCTION.md).

Bounded cross-camera hypotheses are allowed within one site/run/clock; they do not confirm or
merge identities. Preserve alternatives, an unassociated baseline, original corroborating
projections, hard local gaps, unknown geometry authority and search truncation. Overlaps require
synchronized position support; validate time/speed consistency across the whole candidate path.
Label canonical full-time ranking separately from narrow displayed curves and fixed media K,
cameras/time versus query/selected rank. Window slicing must not regenerate event references.

Physical filtering uses hash-bound, purpose-approved support surfaces, the body policy and
exact known collider components. Partial scopes can reject known nominal-path contradictions;
absence of known contact does not prove collision freedom. Keep unresolved apertures, corridor
connectivity and unclassified meshes UNKNOWN. Names, boxes and display crops do not gain
authority. Missing-gap lines are association illustrations, and partial support disconnection
does not prove global unreachability. Preserve per-candidate PASS/REJECT/UNKNOWN reasons and
their scope without changing formal geometry, identity or behavior approvals.

Preserve source Blender assets and isolated research copies. No cleanup, source modification or rendering without explicit authorization. Keep Ground Truth out of inference, search, ranking and path scores. Domain contains contracts only; deterministic modules handle physics, Top-K and provenance, not an Agent (the D64 Q1–Q5 camera-switch exception leaves ranking deterministic). Phase 2 implementation and semantic ranking remain gated by the research scope. Synthetic/configured routes and technical checks are not school navigation certification, a formal dataset or a successful benchmark. A documentation update does not expand implementation or publishing authority.
