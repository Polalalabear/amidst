# 協調者交接：Amidst（2026-10-18）

> 給下一個協調者 session。這份**取代** [COORDINATOR_HANDOFF_20261017.md](https://github.com/Polalalabear/amidst/blob/claude/docs-handoff-20261017/docs/agents/COORDINATOR_HANDOFF_20261017.md)（PR #52，未合併）。10/17 版的操作坑和 D1–D21 的內容仍然有效；本文件只摘要，並補上 10/17 晚到 10/18 的變化。
> 進度類內容是 10/18 的快照，即時狀態以 GitHub issue／PR 為準。決策全文在 CP1 [#25](https://github.com/Polalalabear/amidst/issues/25)、CP2 [#26](https://github.com/Polalalabear/amidst/issues/26) 的留言（D1–D25）。

## 0. 最重要的一件事：Demo 已經轉向（D25）

2026-10-18，使用者決定 **Codex 的「受控新場景與 2D → 3D 重現」提案直接作為新的 Demo**，不再在舊 Office 人形 run 上反覆修問題（使用者原話：「新提案目標是直接作為新 demo，不再反覆找問題」）。

- 舊分支和 PR **全部保留**：不刪、不關，作為證據和可重用模組。處置清單在 #65 回覆文件 Q8。
- 舊的 CP2（#26）、CP3（#27）**暫停**，不關閉；CP4（#28）改為新 Demo 的發布審查。
- 新檢查點：CS-A [#66](https://github.com/Polalalabear/amidst/issues/66)、CS-R [#67](https://github.com/Polalalabear/amidst/issues/67)、CS-B [#68](https://github.com/Polalalabear/amidst/issues/68)、CS-C [#69](https://github.com/Polalalabear/amidst/issues/69)。CS-D（曲線與預測）等 CS-C 完成後再建。
- 使用者說「先不要管日期」，不要再以 11/01 當錨點。
- 舊 Office 才需要的工作都不再續做：K5 畫面牆、K8d、K8e、3D 目標高亮、CP2／CP3 合併。除非使用者要求，否則不要重新啟動。

## 1. 角色與工作方式

- 你是「協調者」：分派任務、記錄決策、寫 brief、讀回報、核對數字。**不自己動手做任務**，開分支、寫程式、審查、留言、改文件，一律交給子 session（Claude）或 Codex。例外是很小的核對，例如比對 SHA、tree、blob，可以自己在協調者 session 裡做。
- 回覆一律用繁體中文。使用者寫「簡單回答／簡單回覆」時，只回答。
- **要使用者授權或決定時，直接用 AskUserQuestion 給 2–3 個選項**：第一個放建議，每個選項寫出風險與代價；不要先寫長篇說明再問。使用者點選就等於授權。只有超出既有規則的動作才需要問，例如合進整合分支或 main、刪除、force-push、改別人的分支；其餘照規則直接做。
- 模型分級照 `CLAUDE.md` 的表：設計判斷和複雜程式碼的複核用 Opus／high；一般審查和實作用 Sonnet；張貼留言用 Haiku。審查採兩段式：Sonnet 全面審查，有疑點才交 Opus。
- 後續修正送回已有前因後果的 session（`SendMessage`），不要另開新的。
- 給 Codex 的指派由使用者轉貼；協調者提供可以直接貼上的文字。**使用者 10/18 為 Codex 開了新對話，已給過一份完整的背景訊息**，內容包括角色、D25、要讀的文件、使用者已定的範圍、CS-A 任務和限制。
- 每個子 session 的回報都要核對測試數字、commit SHA；和預期不符時，讀 diff 或升一級模型。

## 2. 環境、分支、磁碟

- repo：`/Users/polalabear/Developer/amidst-claude`。它其實是資產 repo `/Users/polalabear/Developer/amidst` 的 git worktree（`.git` 是檔案），平常停在 `claude/k1-hypothesis`。
- 6 個不屬於我們的未追蹤檔永遠不要 stage、移動或刪除：`configs/dual_camera_straight_line_v1.json`、`docs/engineering/WORKBENCH_AUDITORIUM_GEOMETRY_AUDIT.md`、`scripts/audit_auditorium_geometry.py`、`scripts/audit_auditorium_source.py`、`scripts/render_dual_camera_validation.py`、`src/amidst/workbench/dual_camera_validation.py`。
- 資產 repo `/Users/polalabear/Developer/amidst` 是唯讀的，Codex 也在那裡工作，不要在裡面跑 git。`.local-worktrees/phase1-finalization`（6 GB）是 launcher 的 evidence 來源，**不能刪**。
- 整合分支 `claude/office-demo-visualization` 在 `dcb89f4`。main 在 `519e874`，只有使用者授權才能更新。合併一律用 merge commit，不 squash、不 rebase。
- **並行寫入（使用者 10/17 核准）**：同一時間最多 2 個寫入 session，各自在自己的 scratchpad 用 clone 工作，檔案集合不能重疊。共用 checkout 仍然只能有一個寫入者。兩個前端任務不要同時跑，它們都會改 `app.mjs`、`demo-steps`。
- **磁碟（10/18）**：可用約 17 GiB。clone 一律用精簡做法：`git clone --shared --no-checkout` 加上 `git sparse-checkout set --cone <需要的目錄>`；`node_modules` 用 symlink 並加進 `.git/info/exclude`；任務完成後立刻 `rm -rf` 刪除 clone。不要刪 clone 目錄以外的 LOCAL 產物（json、截圖），要刪先問使用者。
  - 已刪：舊 scratchpad clone 約 2.6 GB、`~/.cache/codex-runtimes/codex-runtime-install-*` 3.6 GB、Xcode `DocumentationCache` 2 GB。
  - 刪不掉：`/Library/Developer/CoreSimulator/Caches/dyld`（11 GB）。macOS 隱私保護擋住了，要先給終端機「完整磁碟取用權限」；使用者說刪不了就算了。
  - 保留：`amidst/blender/school_v2.blend`（445 MB，可刪，但沒有必要）、`school_v3.blend`、`~/.cache/uv`（launcher 用 `--offline`，刪了會無法離線啟動）、Ollama、PostgreSQL。
- **工作台服務**：協調者從 `<協調者 scratchpad>/wb`（彩排分支 `5a2c613` 的精簡 clone）啟動了一個服務，網址 `http://127.0.0.1:54384/`。停止方式：`<該目錄>/start-office-demo.command stop`，停掉後把 `wb` 刪除。協調者 scratchpad 是 `/private/tmp/claude-501/-Users-polalabear-Developer-amidst-claude/16f4d26c-fca8-4dc8-8776-e237a9e00656/scratchpad`。

## 3. 操作上的坑（新增的；10/17 版第 3 節仍有效）

- **由子 session 回報或自動事件觸發的那一輪，不能直接開 session**，只能用 `own_initiative` 做成卡片，等使用者按。`SendMessage` 給既有 session 可以。
- **用量上限**：10/18 凌晨，多個子 session 撞到「session limit · resets 3am」，中斷的有 K5 畫面牆、K8d、Codex 批次審查。重置後送一則「從中斷處繼續」的訊息就能續做；但這些現在都因 D25 不再需要。
- **堆疊 SHA 會變**：Codex 往上合併時，PR head 會換，但 tree 可能不變。核對方式是 `git rev-parse <sha>^{tree}`。brief 裡寫死的 SHA 和 fetch 結果不同時，子 session 應停下回報；協調者確認後再給新的 SHA。
- **合成時的重複 import**：測試會把 import 拿掉再執行，抓不到重複 import。每次合併都要對所有 `.mjs` 跑 `node --check`，並用瀏覽器實際打開確認。
- **文件提交**：用暫存 `GIT_INDEX_FILE` 加 plumbing（`read-tree` → `hash-object -w` → `update-index --cacheinfo` → `write-tree` → `commit-tree` → `git push origin <sha>:refs/heads/<branch>`），不碰工作樹。
- **瀏覽器驗收**：在 scratchpad 合成副本；啟動指令是 `OFFICE_ASSETS_REPO=/Users/polalabear/Developer/amidst OFFICE_PYTHON=/Users/polalabear/Developer/amidst-claude/.venv/bin/python ./start-office-demo.command --no-open`。工作樹要先提交乾淨，launcher 會自行把 PYTHONPATH 設成 `<副本>/src`。研究身份要先選，再切場景。
- **zsh**：`$VAR:path` 會被當成修飾詞，要寫成 `${VAR}:path`。

## 4. 決策摘要

- D1–D21：見 10/17 版第 4 節。重點是 GT 隔離（D1）、D15 禁止區是政策圖層、D19 收斂照實講、D21 負證據要腳加腰都可見且 ≥112 px。
- **D22**：移除舊 Demo 的原步驟 5（跨鏡頭候選），因為人形 v2 刻意停用了舊面板。
- **D23**：系統能力用 Office 地圖上的合成段（K8）展示。第二人形延到 11/01 之後（#55，現已關閉）。
- **D24**：舊 Demo 步驟排成 1–5 真實、6–8 SYNTHETIC、9 負例。
- **D25**：轉向受控新場景；新 Demo 的 11 項決定見第 5 節。

## 5. 新 Demo 現況

### 文件
| 文件 | 位置 |
| --- | --- |
| Codex 提案 | `docs/agents/CONTROLLED_SCENE_2D_TO_3D_PROPOSAL_20261018.md`（`codex/office-demo-rehearsal-docs`，blob 59b8f5d） |
| Codex 準備文件：磁碟預算、可重用後端、候選鏡頭 API 欄位 | `docs/engineering/CONTROLLED_DEMO_PREPARATION_20261018.md`（同一分支，blob 14a3ffb） |
| Claude A 包：回覆、契約、UX 草圖 | Draft [#65](https://github.com/Polalalabear/amidst/pull/65)（`claude/controlled-scene-a` @ 9848d5e），`docs/agents/CONTROLLED_SCENE_CLAUDE_REPLY_20261018.md`、`docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md`、`docs/agents/CONTROLLED_SCENE_UX_SKETCH_20261018.md`。契約 §9 有 11 題待 Codex 回答 |

### 使用者已定（A 包第 3 節全部照 Claude 建議，只改幀率）
1. 事件 B 拆成 B1（兩人錯開、不交會）和 B2（交會或分離）；先驗收 B1。
2. B1 的轉角不放鏡頭，作為設計好的盲區。暫定鏡頭 `CAM_W1`、`CAM_W2`、`CAM_N1`、`CAM_R102_CTRL`，兩個事件共用一個 `.blend` 和一份校正。
3. B1、B2 固定 2 人。
4. **960×540、先用 5 fps、PNG**；穩定後再另版升到 10 Hz，不覆寫 5 fps 的 run。存放位置由 Codex 確認，初步是資產 repo `data/pilot/<新 run>/`。前端在影格之間的時間內插，evidence state 一律是推論（INFERRED）。
5. 8 台以上的候選鏡頭用 UI fixture 測。
6. 可重用模組先核准合併（CS-R），不做深層堆疊。
7. 檢查點改為 CS-A～CS-D。
8. 新場景以標記為主，C7／K7 當驗證器（D3 反轉）；AMBIGUOUS_MERGE 在 B2 驗收前不可用（D8 修訂）。
9. 現行工作台先移除綠球（A 包核准後的小任務）。
10. 各項門檻在凍結前約定，不自己定數字。
11. #55 已關閉。

其他使用者需求：3D 物理曲線用虛線；2D 同步畫面可切 1／2／4／8 格；有查找模式（地面選區、時間範圍、查詢模板，不用 Agent）；**3D 人物只能由 2D 影像重現，不能讀 GT**；事件 A 是單人直線經過。5 fps 的跳動不等於「飛出去」：舊綠球跳動是因為估計誤差（RQ1），不是幀率。

### 檢查點順序
CS-A（A 包加 Codex 可行性；通過前不建 `.blend`、不渲染）→ CS-R（可重用模組併入整合分支）→ CS-B（事件 A、B1 場景驗收）→ CS-C（查找與重現）→ CS-D（曲線與預測；B2 另開）。

## 6. 舊工作的重點數字（之後寫報告會用到）

- **RQ1**（Draft [#61](https://github.com/Polalalabear/amidst/pull/61)）：C4a v1.1 的 33 筆接地區間，在 0.25 m 容差下涵蓋 23/33。FRONT 腳點帶 19/23、**REAR 腳點帶 0/6**（真值落在近端外 2.0–3.1 m，屬系統性偏移）、頭頂射線 4/4。Codex 的唯讀診斷（`04f02fb`）認為最可能是遮擋，讓估計器把被擋住處的底部誤當成腳點；沒有調參，也沒有重新凍結。GT 檔是 `amidst/data/pilot/office_person_20261016_v1/rendered/ground_truth.json`（SHA e12c34f5…），只供評估。
- **D19／D21**：舊 Office 人形 run 的 NONE＝BASELINE＝281.125 m²，收斂 0%（#53，已獨立核對）。
- **K8 合成**（#56–#60）：S1 產生 3 條假設；S2 判出可達、排除、無法判定各一；S3 的可達面積 649.0 → 611.438 → 574.5 m²。「只有 1 條假設」的原因是兩端點互相可直視，時間預算約 7.79 m，而繞行至少要約 13.1 m。
- **P1**：百萬筆 metadata 索引 p50／p95 約 0.497／0.505 ms，不含 HTTP。

## 7. 開啟中的 PR（10/18）

所有 PR 都未合併。新 Demo 會用到的模組要經 CS-R 決定。

| 類別 | PR（head） |
| --- | --- |
| 新 Demo | #65 A 包（9848d5e）；Codex 純文件 #54（`codex/office-demo-rehearsal-docs` @ 14a3ffb） |
| Claude 演算法 | #33 K1（7c01522）、#36 K5（726e390）、#48 K1 D15／D21（74c6ace）、#58 K8a（131869d）、#57 K8c（d2ee136，已補 negative_evidence 型別修正）、#60 K8b（1f53f0d）、#56 K8 設計（91d944a） |
| Claude 前端 | #31 K3（74af12f）、#42 K3 後半（d0f82b1）、#35 K4（7a7f93e）、#38 K6（e82f94b，含 A1／A3／A4／A5 與 D22／D24 步驟） |
| Claude 其他 | #41 K7（1ef9bc9）、#45 契約 v1.1／v1.2（9e1234c）、#61 RQ1（5672fee）、#39 問答、#52 舊交接 |
| Codex | #37、#43、#44（86b9b24）、#46、#47、#50、#53（4019a44）、#40 C7、#51、#62 畫面牆 fixture（710ae1f）、#63 K8a 預同步（28f050a）、#64 rehearsal-check（225f246）、#34 C6（不合併） |
| 彩排分支 | `claude/rehearsal-20261018` @ 5a2c613（無 PR）：#53＋K6＋K3 後半＋#54，舊 Demo 步驟 1–6 在瀏覽器全部通過，前端測試 359 項 |

Codex 的 CP2 合併準備報告（#54 @ d7b235d）和 CP3 報告（`b965c3d`）可以作為 CS-R 的起點。報告列出的衝突集中在 #40、#37、#43（文件與測試）和 #53／#35／#38。

### 分支整理（10/18 盤點，尚未執行）

- **已完全併入整合分支、沒有 PR**：`claude/k0-data-contracts`、`claude/k2-eval-rq1`、`docs/office-pipeline-map`、`codex/c3b-preset-isolation`、`codex/mvp-backend-integration`。刪掉遠端分支不會遺失任何 commit，但要使用者核准（AskUserQuestion）。`codex/*` 要先問 Codex；`codex/mvp-backend-integration` 是 AGENTS.md 指定的 Codex 後端分支，**不要刪**。
- **沒有 PR、也沒有併入**：`phase1/finalization-sprint`（launcher evidence，不能刪）、`phase2/integration-hardening`、`codex/phase1-case23-formal`、`codex/simulation-engineering`、`docs/auditorium-geometry-audit`、`docs/workbench-root-cause-audit`、`claude/rehearsal-20261018`。這些不刪；擁有者不明的先問 Codex。
- **有 open PR 的**：依 AGENTS.md 不靠刪分支關 PR。新 Demo 要用的模組走 CS-R 合併；只有舊 Office 才需要的維持 Draft 或暫停。

## 8. 待辦（依優先順序）

1. **等 Codex 的 CS-A 回覆**：逐條審契約、答 §9 的 11 題、評估鏡頭配置、確認存放位置與 run ID、估計 wrapper 修改量。收到後：
   - 契約修改送回 A 包 session `local_274da42e-c7e8-477b-be9e-9228325cacc7`（Opus），更新 #65；
   - 整理成 AskUserQuestion，請使用者在 #66 核准 CS-A。
2. **CS-R 計畫**：依 #65 回覆 Q7 的可重用模組清單，加上 Codex 的 CP2／CP3 報告，派 Sonnet 做唯讀的合併模擬：只合新 Demo 要用的模組，依合併順序逐一列出衝突與建議解法。之後由使用者在 #67 核准合併；合併時要用 AskUserQuestion，因為合進整合分支超出既有規則。
3. **CS-A 通過後可以立刻並行的 Claude 工作**（各自用精簡 clone，最多 2 個寫入）：
   - 現行工作台移除綠球：小任務，Sonnet／medium；
   - 用契約的 payload 做 fixture，先寫 `player-grid.mjs`（1／2／4／8 格同步播放）與 `search-mode.mjs`。這兩個不依賴 RGB；屬前端，兩者不要同時寫。
4. **CS-B 開始後**：
   - Claude 審核 Codex 的場景與每台鏡頭的單張渲染，抽查影像與標記完整性；
   - 標記範本與 validator（E 包）。
5. **舊工作收尾（低優先）**：
   - K8 issue #59：依 D25 留言說明暫停；
   - 中斷的 session（K5 畫面牆 `local_2eb143ae…`、K8d `local_6a3108fe…`、Codex 批次審查 `local_876fb449…`）不續做；
   - Codex 的 #62／#63／#64 若要在新 Demo 重用（例如 rehearsal-check），在 CS-R 一併審查。
6. **協調者自己的清理**：停掉 54384 的服務，刪除協調者 scratchpad 的 `wb` clone。

## 9. 子 session 參考（可用 SendMessage 續用）

| 用途 | session |
| --- | --- |
| 新 Demo A 包（Opus） | `local_274da42e-c7e8-477b-be9e-9228325cacc7` |
| K6 Demo 模式（Sonnet） | `local_874a317b-315b-48e2-a5cb-a7f973808be8` |
| K3 後半（Sonnet） | `local_db6c1cb4-6cdc-4371-89f8-1012654690b7` |
| K5／K1 演算法（Sonnet） | `local_bfdf4160-ec23-4171-818c-6a42c482fae3` |
| K8 設計（Opus） | `local_f6e6b1e6-e88d-4850-9ae7-caaa4c7ec3a7` |
| K8a 與契約 v1.2（Opus） | `local_8206a958-b820-4c79-a447-4f79103a195c` |
| 彩排分支（Sonnet） | `local_f0497bf6-be42-4b64-9097-60d12051c02e` |
| RQ1 評估（Sonnet） | `local_8e2004ee-e8ae-4508-ba82-1a411d4b02d5` |
| 張貼留言、開 issue（Haiku） | `local_cd0e8831-02f8-4424-ac03-6be7b4f4cc6a` |
| 上一個協調者（本次） | `local_ea2923ec-7641-4c86-8f29-7b682f899968` |
