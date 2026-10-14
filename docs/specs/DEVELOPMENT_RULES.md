# Development rules / 開發與文件維護規則

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

本文件整理既有工作規則，不新增研究需求或改變架構。需求依 [PRD](PRD.md)，模組責任依 [SYSTEM_DESIGN](SYSTEM_DESIGN.md)，已採用解法依 [ISSUES_AND_DECISIONS](ISSUES_AND_DECISIONS.md)；發現重大衝突先詢問，不自行改寫規格。

### 文件分工

| 文件 | 存放內容 | 不放入 |
| --- | --- | --- |
| `PRD.md` | 研究需求、成功條件、Phase 邊界 | 開發紀錄、一般 TODO |
| `SYSTEM_DESIGN.md` | 架構、模組責任、資料流 | 每次 commit 或測試結果 |
| `ISSUES_AND_DECISIONS.md` | 核心問題 → 已採用解法 | 開發日誌、小 bug、測試紀錄、未採用方案冒充決策 |
| `DEVELOPMENT_RULES.md` | 持續適用的工程與文件維護規則 | 當次工作進度、歷史驗證結果 |
| `WORK_LOG.md` | 日期／checkpoint 綁定的已完成工作與驗證證據 | 即時待辦清單、未完成工作冒充完成 |
| `CODEX_HANDOFF.md` | 當前狀態、有效待修項目、續作入口及階段性暫緩項目 | 已完成細節、已解問題、過期環境問題、完整歷史與重複規則 |
| `DATA_SCHEMA.md` / `INTERFACES.md` | 實際資料契約與模組介面 | 測試成功日誌 |
| `../../data/README.md` | 已物化資料的日期化盤點與發布邊界 | 尚未產生的 dataset 被當成既有資料 |

工作完成並驗證後，把結果記入工作紀錄；已解決或已失效的 handoff 項目移除，不留「已完成 TODO」。有效未解問題不能只因整理文件而消失；若被暫緩，標明暫緩，不標為解決。歷史紀錄使用當時日期／commit／證據，不能改寫成今天重新驗證的結果。

文件正文放在 specs／engineering／research／operations／history；只由 `docs/README.md` 提供總索引，不另建每分類 README 或逐檔轉址文件。根目錄例外只保留實際 hash／runtime 綁定的檔案或必要路徑別名；新增文件直接使用分類路徑。

### 開發與 Git

- 開始先確認實際工作目錄、`git status` 與 `git branch`；保留使用者及其他工作的未提交修改。
- 優先重用既有 checkout／environment 與單一 immutable 資產來源；branch 可在同一 checkout 切換。不要為每個 milestone 建 worktree、clone、venv 或 raw 副本。必要的隔離仍保留，但刪除／archive 既有 checkout 和資產須有對應授權。
- 2026-10-14 已授權不再使用的 worktree／封存／試跑實體清理：僅保留文件、manifest／hash及精簡收據，不再製作或移存大型 raw 封存。先核對是否仍供現行服務、共享工作、demo或復原使用；原始來源、現行資料與未提交變更仍保留。刪除舊產物後同步標明歷史 locator 退役，不承諾只靠文件可完整復原。
- Python 全部使用 uv；主要依賴來源為 `pyproject.toml`、`uv.lock`，不以 requirements.txt 取代。
- 實作以 milestone 為邊界：可執行功能 → unit／major-flow integration validation → 確認既有階段未破壞 → 獨立 commit → 下一階段。
- 只 stage 本任務檔案；不 `reset --hard`、force push、rewrite history 或 rebase 使用者 commit。Push／PR／merge 需要對應明確授權。
- 遇到重大場景語意、walkability、camera convention、公開介面、指標或 GT isolation 問題，先停止該不確定部分並詢問；可依既有規格解決的小問題不必擴張設計。

程式實作的驗證指令：

```sh
uv run pytest
uv run ruff check .
uv run mypy
git diff --check
```

純文件整理只做相稱的 diff、連結與內容一致性檢查；若沒有重跑程式測試，引用既有結果時標明歷史 checkpoint，不宣稱本次執行。

### 共用網頁工作台

- Amidst 網頁以 `frontend/workbench/` 的[共用工作台](../engineering/SHARED_WORKBENCH.md)為主入口；既有及後續需要頁面展示的功能均接入它的導覽、元件及流程。
- 新場景使用 catalog／adapter，新增展示、調查、測試或人審功能擴充共用工作台。研究／管理權限由後端限制，工作模式及產品的輸入模式／凍結階段不改變權限。
- 遷移既有頁面時重用資料與後端服務，保留原介面、來源綁定及歷史驗證；以局部查詢與獨立 milestone 驗證遷移。未遷入的功能在 handoff 明列，不把主入口決策或舊頁面的 PASS 當作遷移完成。

### 研究有效性與資產

- 原始 `.blend` 保持不變；研究副本與生成資料依既有隔離決策處理。Audit／export 不儲存來源；清理、刪除、修改來源資產或 render 必須另外明確授權。
- GT 僅供 simulation/export、evaluation、debug visualization；不得進入 inference、graph、candidate ranking、semantic reasoning 或 path score。Domain 只放 schema／interface；Agent 不做 geometry、pathfinding 或 collision checking。
- 依 PRD 保留物理硬限制、多解 Top-K 與 provenance；Phase 2 僅保留 schema／interface，Semantic Ranking 在 deterministic closed loop 完成後才考慮。
- 研究配置與合成 fixture 不等於核准的 school walkability、正式資料集或 benchmark。驗證點可見性、技術 render 成功、影像可用性與正式研究驗收是不同證據，不互相代替。
- 規則與永久決策不要複製到每次 handoff。當前授權範圍／暫緩狀態留在 handoff，完成與驗證紀錄留在 work log；不因文件整理擴大實作或發布權限。
- 工程可先以 synthetic/mock 調用、查找與 replay 並行推進，不以正式 Phase 1 全 Exit 作工程前置；工程通過不改寫正式研究狀態。Agent 的操作资源與輸出契約見 [工程邊界](../engineering/AGENT_RETRIEVAL_BOUNDARY.md)。不串接外部模型 API。2026-10-11 已授權圖形/label 前處理、明確 Agent I/O、階段性模擬資料庫併發與差異文件；此 token 兜底原型不代表已量測 token 減量。
- 真實攝影機串流保留 FUTURE；正式帳號與部署保留 DEFERRED。專案媒體為 Blender camera 來源影像與依原 `.blend`／預設平滑展示材質的模型；替代 procedural RGB 必須另標來源，材質不改 scene 或 authority。
- Blender 基底畫面檢索只使用來源綁定的安全 camera/time/media 欄位、實際 RGB pixels及獨立合法校正／floor plane；不讀 renderer 的 GT、trajectory、visibility、depth或預先給定 observation 答案。基底演算法模式不經 Agent 決策；像素元件／local tracks與使用者行為意圖不得改稱人物或行為已確認。
- source model 的 subset/crop 與平滑材質維持 PARTIAL display context，不擴大整場幾何、可行走、遮擋或碰撞authority。校正、plane與clip distances必須使用同一明確尺度；不能只改單位標頭或拿landmark plane代替接地面。
- 分層資料流明列ACTUAL_BLENDER、SUBSTITUTE、DEFERRED及各自source/model/run/clock/hash；替代Graph／重建與歷史測試只用獨立fixture，不回填實際Blender run。未物化的物理曲線／影片保持未完成。公開PNG可剝除文字metadata但須保留像素chunks、核對原始／served hashes，不能修改原影像或洩漏private locator。
- 新歷史版本保存修改部分及 source/base/parent/result hashes；以 baseline 還原。發布只包含可核對的差異文件、code/docs/tests/curated receipts，不直接複製 `.blend` 或上傳 raw DB／GT／影像。既有歷史與已授權隔離實驗保留。
- 工作台以穩定 3D 為主，按需標示登錄節點／邊；事件 ID 只在專用 log 顯示，內部 references 保留。Agent 不得全量掃描，未知 label 明示需要補充輸入。
- Blender物理曲線區分RGB觀測、地板投影、短缺口插值與有限差分速度；缺失／無效投影／超過設定限制保持斷線，不外推或跨鏡頭合併身分。設定速度上限與像素heuristic uncertainty不得冒稱人體模型、機率或誤差界。窄範圍曲線與完整預先物化影片分別標明鏡頭／時間；GET只驗證／讀取，不產制。影片缺失或過期不阻斷有效曲線，且不得改用其他source/run補缺。
- 跨鏡頭工程可在同site/run/clock內產生受限關聯假設，不等於合併已確認身分。保留多解與未關聯基線、同期原投影、原局部硬缺口、未知幾何權限及搜尋截斷。重疊須有同步位置支持，整條候選路徑須檢查時間／速度一致性。完整來源排名與窄窗曲線切片各自標明；事件reference不因切窗重編，影片素材K／鏡頭／時間與本次查詢及rank各自標示。
- 來源物理篩選只用hash綁定且purpose／authority核准的支撐面、人體政策與精確碰撞元件。部分碰撞scope可拒絕已知名義路徑矛盾，不能證明無碰撞。門洞、走廊連接與未分類mesh的未知部分保持UNKNOWN；名稱、annotation box或display crop不升權。長缺口示意線不能當實際動線硬判穿牆，partial支撐缺連接不能當完整不可達證明。每解保留PASS／REJECT／UNKNOWN理由與範圍，物理工程重排不改寫正式幾何／身分／行為核准。

## English

These are existing engineering and documentation rules, not new requirements. [PRD](PRD.md) owns research scope, [SYSTEM_DESIGN](SYSTEM_DESIGN.md) owns architecture, and [ISSUES_AND_DECISIONS](ISSUES_AND_DECISIONS.md) contains only core problems and adopted solutions. Ask before resolving major conflicts through design changes.

Keep durable rules here, dated completed work/evidence in [WORK_LOG](../history/WORK_LOG.md), current unresolved/actionable state in [CODEX_HANDOFF](../operations/CODEX_HANDOFF.md), contracts in DATA_SCHEMA/INTERFACES, and materialized-data inventory in [data/README](../../data/README.md). Move verified completion into the log and remove resolved/stale handoff items. Deferred is not resolved. Preserve genuine open issues and bind historical checks to their original date/checkpoint.

Store maintained text in the five category folders and use only `docs/README.md` as the index. Do not add category READMEs or per-document redirect pages. Root exceptions must serve an actual hash/runtime binding or required path alias; new documents use category paths directly.

Verify workspace, Git status and branch before work; preserve unrelated changes. Use uv, pyproject.toml and uv.lock. Implement, validate and independently commit each milestone before the next. Stage narrowly; do not reset, force-push or rewrite user history. Publication requires explicit authorization. Code checks are listed above; documentation-only changes use proportionate diff/link/consistency checks and must not claim an old test run as new.

Prefer reusing one checkout/environment and shared immutable assets rather than accumulating worktrees, clones or raw copies per milestone. Branches can share the same checkout. Necessary isolation remains available; existing assets/checkouts are not deleted or archived without authorization.

Use `frontend/workbench/` as the primary Amidst web entry for existing and future presentation,
investigation, testing and human review. Extend its shared navigation, components and scene
catalog/adapters. Enforce Research/Management access on the server; work modes and product
input/frozen stages do not grant permissions. Reuse existing backend/data contracts during
migration, preserve source-bound history, validate each bounded migration milestone and keep
unmigrated capabilities explicit in the handoff.

Local synthetic/mock engineering proceeds alongside formal Phase 1 research without making
engineering passes formal acceptance. Follow the [Agent retrieval boundary](../engineering/AGENT_RETRIEVAL_BOUNDARY.md).
No external model API is connected. The 2026-10-11 instruction authorizes bounded graph/label
preprocessing with explicit Agent I/O, phased simulated SQLite concurrency and delta documents;
this does not establish measured token savings. Real camera streaming is FUTURE; accounts and
deployment are DEFERRED. Blender camera images and source-bound smooth model presentation keep
their simulation provenance. New history stores changed parts and binding hashes, with no raw
DB/GT/media/`.blend` publication. Stable 3D is primary; event IDs appear only in dedicated logs.

Blender baseline frame retrieval reads only sanitized source-bound camera/time/media inputs,
actual RGB pixels and independently legal calibration/floor geometry. It does not read renderer
truth, trajectories, visibility/depth or precomputed observation answers, and does not use an Agent
to decide. Pixel components/local tracks and behavior intent do not confirm people or behavior.
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

Preserve source Blender assets and isolated research copies. No cleanup, source modification or rendering without explicit authorization. Keep Ground Truth out of inference, search, ranking and path scores. Domain contains contracts only; deterministic modules handle physics, Top-K and provenance, not an Agent. Phase 2 implementation and semantic ranking remain gated by the research scope. Synthetic/configured routes and technical checks are not school navigation certification, a formal dataset or a successful benchmark. A documentation update does not expand implementation or publishing authority.
