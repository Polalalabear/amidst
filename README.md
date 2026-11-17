# Amidst

**多攝影機畫面的調查輔助工具：用條件「查找」畫面，選定目標後跨鏡頭「追蹤」，目標進入盲區時標出推測路線。每個答案都能追溯到來源證據。**

**An investigation aid for multi-camera footage: *search* frames by a condition, *track* a chosen target across cameras, and mark the inferred route when the target enters a blind interval. Every answer traces back to source evidence.**

[繁體中文](#繁體中文) | [English](#english)

> **狀態（2026-11-08）：**研究原型，全部資料來自 Blender 合成的受控場景，不是部署系統。目前在做**大問題 A：Demo 驗收**（新 UI 加真實資料，[#445](https://github.com/Polalalabear/amidst/issues/445)），即時進度和決策紀錄看[決策板 #93](https://github.com/Polalalabear/amidst/issues/93)。
>
> **Status (2026-11-08):** research prototype. All data comes from a synthetic, controlled Blender scene; this is not a deployed system. Current work is **epic A: demo acceptance** (new UI on real data, [#445](https://github.com/Polalalabear/amidst/issues/445)). Live progress and decisions are on [decision board #93](https://github.com/Polalalabear/amidst/issues/93).

## 繁體中文

### 這個專案在做什麼

建築內的攝影機很多，調查人員常常要逐支影片回看。Amidst 只做兩件核心的事（D126）：

| 核心 | 使用者做什麼 | 系統回什麼 |
| --- | --- | --- |
| **查找** | 輸入時段，再選地點或特徵（例如「人物」，可加衣服顏色） | 符合條件的鏡頭和畫面，排成結果牆，可放大逐張看 |
| **追蹤** | 選特徵和開始時間，系統自動選取追蹤起點 | 目標在各鏡頭出現的片段、自動切鏡、播放列和追蹤紀錄；目標離開所有鏡頭時，在俯視圖畫出盲區的推測路線 |

系統是**輔助**，目的是讓使用者快速知道目標大概在哪，不追求精確：

- 身分一律是 `UNCONFIRMED`：串起來的片段是「條件相符的候選」，不代表同一個人。
- 證據不足時回 `UNKNOWN`，不用猜測補上。
- 盲區路線是推測（`INFERRED`），不代表目標實際走得通。

### 畫面

新 UI 在 `frontend/workbench-v2/`，從封面進入，有三個前台畫面和一個後台：

| 畫面 | 內容 |
| --- | --- |
| case 1 查找 | 查詢窗、進度、結果牆、放大檢視 |
| case 2 追蹤 | 單畫面和多畫面播放、自動切鏡、速度選擇、俯視圖的盲區路線、追蹤紀錄 |
| case 3 查看 | 依事件同時看所有鏡頭 |
| 後台（`admin.html`） | 概況、鏡頭播放、紀錄、設定（例如預設入口） |

前台預設是展示模式：只顯示事件名稱和白話狀態，技術標籤收進 ⓘ。後台完整顯示所有欄位。加上 `?ui=legacy` 會回到舊工作台。

### 方法

```text
來源 RGB 畫面 ─▶ RT-DETR 物件偵測 ─▶ 人物上半身 HSV 顏色訊號
                         │
                         ▼
                偵測索引（綁定來源、時鐘與 hash）
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
     查找                               追蹤
  地點：場景設定的涵蓋區域          同鏡頭以 IoU 串成片段
  特徵：索引中的偵測與顏色          兩層圖（鏡頭拓撲）決定切鏡
                                          │
                                          ▼
                              盲區：依可走區域與時間
                              推算可能路線（INFERRED）
```

- 地點命中是場景設定（人工在靜態畫面標的涵蓋範圍），不是看到目標，所以這類結果會標成「目標未觀測」。
- 區域、鏡頭、類別、顏色都從 pinned 設定檔讀，程式不寫死特定教室或鏡頭。
- Agent 和自然語言查詢（大問題 D）目前是把自然語言轉成查詢選項，使用者確認後才執行。自主行為仍是規則式，不是學習出來的。

### 核心原則

| 原則 | 說明 |
| --- | --- |
| 證據狀態分開 | `OBSERVED`、`INFERRED`、`MISSING`、`UNKNOWN` 分開保存。前台改成白話顯示，但資料層不合併 |
| 身分不自動確認 | 顏色相符只代表證據強弱，不代表同一人；身分維持 `UNCONFIRMED` |
| Ground Truth 隔離 | GT、渲染軌跡、visibility、depth、劇本關鍵影格不進推論、測試輸入或畫面；請求帶這些鍵會被拒絕（422） |
| 來源追溯與 fail-closed | 每筆資料綁定來源、run、時鐘與 hash；不符就拒絕，缺資料只關閉該功能 |
| 依賴自有 | 依賴、鎖定檔、啟動腳本、資料和模型的 manifest 都在 repo 裡，不借用舊環境（D133） |

### 目前進度（2026-11-08）

工作整合成四個大問題（D132）：

| 大問題 | 內容 | 狀態 |
| --- | --- | --- |
| A [#445](https://github.com/Polalalabear/amidst/issues/445) | Demo 驗收：新 UI 加真實資料 | 新 UI（[#487](https://github.com/Polalalabear/amidst/pull/487)）在真實資料上的瀏覽器測試已通過；前台展示調整 D139（[#493](https://github.com/Polalalabear/amidst/pull/493)）審查中；之後做量測 B、走查，再由使用者驗收 |
| B [#479](https://github.com/Polalalabear/amidst/issues/479) | 實驗紀錄與研究報告 | 實驗紀錄 v2 已出（[#488](https://github.com/Polalalabear/amidst/pull/488)）；v3 等新截圖和量測 B |
| C [#486](https://github.com/Polalalabear/amidst/issues/486) | 大掃除與可攜性 | Python 3.12 鎖定和依賴收編已完成（[#491](https://github.com/Polalalabear/amidst/pull/491)）；Windows／Linux、CI、分支整理在驗收後 |
| D [#489](https://github.com/Polalalabear/amidst/issues/489) | 讓 Agentic 成立 | 路徑 (b) 自然語言轉選項已完成（[#490](https://github.com/Polalalabear/amidst/pull/490)）；路徑 (a)、現場 Qwen／OpenAI 在驗收後 |

上面的 PR 都還沒合併進 `mainline/q1q5`，合併要使用者授權。跨攝影機 3D 軌跡重建線暫停但保留，在分支 `archive/3d-line`。

### 開發環境

需要 [`uv`](https://docs.astral.sh/uv/) 和 Node.js。Python 固定為 3.12（`.python-version`），Node 版本在 `.node-version`，依賴由 `uv.lock` 和各 `package-lock.json` 鎖定：

```sh
git clone https://github.com/Polalalabear/amidst.git
cd amidst
scripts/setup_env.sh        # 建立 .venv（Python 3.12），照鎖定檔安裝 Python 和 node 依賴
.venv/bin/pytest tests/q1q5
AMIDST_REQUIRE_IMPL=1 node --test frontend/workbench-v2/*.test.mjs frontend/event-viewer/*.test.mjs
```

### 執行真實資料 Demo

Clone 只取得程式、設定和文件。渲染畫面、模型權重、偵測索引這些資料放在本機的自有資料夾（預設 `local/data/demo-owned-v1`，在 repo 根目錄之下、已被 `.gitignore`；可用 `AMIDST_DEMO_HOME` 改位置；找不到時報 `OWNED_ROOT_NOT_FOUND`），不在 repository 裡，所以光靠 clone 不能重現 Demo。資料夾備妥後：

```sh
export AMIDST_DEMO_HOME="${AMIDST_DEMO_HOME:-$PWD/local/data/demo-owned-v1}"
PYTHONPATH=src uv run --offline --no-project \
  --python "$AMIDST_DEMO_HOME/runtime/python/bin/python3.12" \
  python -B scripts/setup_owned_demo.py        # 第一次，或鎖定檔變了之後才需要
./start_445_demo.command --port 8785
```

然後開 `http://localhost:8785/workbench-v2/`。細節和移機方式見[依賴收編說明](docs/operations/DEMO_OWNED_DEPENDENCIES_20261108.md)；展示和驗收步驟見 [Demo 腳本兼驗收清單](docs/operations/DEMO_SCRIPT_ACCEPTANCE_V1.md)。目前只驗證過 Mac（darwin-arm64）。

### 分支與協作

- `mainline/q1q5`：預設與整合分支，只接受 merge commit。
- `claude/445-demo-integration`（[#485](https://github.com/Polalalabear/amidst/pull/485)）：大問題 A 的整合分支，驗收後合進主線。
- `claude/ui-redesign-v1`（[#487](https://github.com/Polalalabear/amidst/pull/487)）：新 UI，合進 #485。
- `main`：Q1–Q5 轉向前的歷史版本，目前不更新。
- Codex 和 Claude Code 依檔案和資料契約分工，規則見 [AGENTS.md](AGENTS.md)。只用 merge commit，不 rebase、不 force。

### 文件導覽

- [核心功能契約：查找與追蹤](docs/contracts/Q_CORE_SEARCH_TRACK_V1.md)（`Q_CORE_SEARCH_TRACK_V1`）、[Demo UI 支援契約](docs/contracts/DEMO_UI_SUPPORT_V1.md)、[Q1–Q5 第一版契約](docs/contracts/Q1_Q2_FIRST_DEMO_V1.md)（時鐘、偵測索引、兩層圖的定義沿用這份）
- [Demo 腳本兼驗收清單](docs/operations/DEMO_SCRIPT_ACCEPTANCE_V1.md)、[依賴收編說明](docs/operations/DEMO_OWNED_DEPENDENCIES_20261108.md)、[Python 3.12 鎖定同步](docs/operations/DEMO_PY312_LOCK_SYNC_20261108.md)
- [開發規則](docs/specs/DEVELOPMENT_RULES.md)（架構、資產、GT 隔離、不確定性）、[Q1–Q5 產品規格](docs/specs/Q1Q5_PRODUCT_SPEC.md)
- [文件索引](docs/README.md)、[封存索引](docs/archive/ARCHIVE_20261027.md)
- 舊的 issue 編號已經併入四個大問題，對照表在 [#93](https://github.com/Polalalabear/amidst/issues/93)。`docs/operations/Q1Q5_PROGRESS.md` 停在 2026-10-27，以 #93 為準。
- **給 AI agent：**依 [AGENTS.md](AGENTS.md) 工作；本 README 不重複其規則。

## English

### What it does

Buildings have many cameras, and investigators often review every video by hand. Amidst does two core things (D126):

| Core | The user | The system returns |
| --- | --- | --- |
| **Search** | Enters a time range, then picks a location or a feature (e.g. "person", optionally with a clothing color) | Matching cameras and frames as a result wall, each frame viewable full size |
| **Track** | Picks a feature and a start time; the system chooses the starting detection | Segments where the target appears on each camera, automatic camera switching, a playback bar and a track log; when the target leaves every camera, the top view draws an inferred route through the blind interval |

The system is an **aid**: it tells the user roughly where the target is, not exactly.

- Identity is always `UNCONFIRMED`: linked segments are candidates that match the condition, not proof of the same person.
- Missing evidence yields `UNKNOWN` rather than a guess.
- The blind-interval route is an inference (`INFERRED`), not proof that the path is walkable.

### Screens

The new UI lives in `frontend/workbench-v2/`. A cover page leads to three front-end screens and an admin page:

| Screen | Contents |
| --- | --- |
| Case 1 Search | Query panel, progress, result wall, full-size viewer |
| Case 2 Track | Single and multi-view playback, automatic switching, speed selector, blind-interval route on the top view, track log |
| Case 3 View | All cameras of one event side by side |
| Admin (`admin.html`) | Overview, camera playback, logs, settings (e.g. the default entry screen) |

The front end defaults to presentation mode: it shows the event name and plain-language status, with technical labels behind ⓘ. The admin page shows every field. Adding `?ui=legacy` returns to the old workbench.

### Method

```text
Source RGB frames ─▶ RT-DETR object detection ─▶ upper-body HSV color signal for persons
                              │
                              ▼
               Detection index (bound to source, clock and hash)
                              │
          ┌───────────────────┴───────────────────┐
          ▼                                       ▼
       Search                                   Track
  Location: configured coverage areas     Same-camera segments linked by IoU
  Feature: detections and colors          Two-layer camera graph decides switching
                                                  │
                                                  ▼
                                   Blind interval: possible routes from
                                   walkable area and time (INFERRED)
```

- A location hit is scene configuration (coverage hand-marked on a still frame), not a sighting, so such results are marked "target not observed".
- Regions, cameras, classes and colors are read from pinned configuration; no classroom or camera is hard-coded.
- The agent and natural-language query (epic D) currently turn a sentence into query options that run only after the user confirms. Autonomous behavior is still rule-based, not learned.

### Principles

| Principle | Meaning |
| --- | --- |
| Separate evidence states | `OBSERVED`, `INFERRED`, `MISSING` and `UNKNOWN` are stored separately. The front end words them plainly; the data layer never merges them |
| No automatic identity | A color match is evidence strength, not identity; identity stays `UNCONFIRMED` |
| Ground Truth isolation | GT, render trajectories, visibility, depth and script keyframes never enter inference, test inputs or the screen; requests carrying them are rejected (422) |
| Provenance and fail-closed | Every record is bound to source, run, clock and hash. Mismatches are rejected; missing data disables only that feature |
| Owned dependencies | Dependencies, lock files, launch scripts and data/model manifests live in the repository; no old environments are reused (D133) |

### Progress (2026-11-08)

Work is organized into four epics (D132):

| Epic | Scope | Status |
| --- | --- | --- |
| A [#445](https://github.com/Polalalabear/amidst/issues/445) | Demo acceptance: new UI on real data | The new UI ([#487](https://github.com/Polalalabear/amidst/pull/487)) passes its browser tests on real data; presentation changes D139 ([#493](https://github.com/Polalalabear/amidst/pull/493)) are in review; measurement B, a walkthrough and the user's acceptance follow |
| B [#479](https://github.com/Polalalabear/amidst/issues/479) | Experiment record and research report | Record v2 is out ([#488](https://github.com/Polalalabear/amidst/pull/488)); v3 waits for new screenshots and measurement B |
| C [#486](https://github.com/Polalalabear/amidst/issues/486) | Cleanup and portability | Python 3.12 pin and owned dependencies are done ([#491](https://github.com/Polalalabear/amidst/pull/491)); Windows/Linux, CI and branch cleanup come after acceptance |
| D [#489](https://github.com/Polalalabear/amidst/issues/489) | Making the agentic claim hold | Path (b), natural language to query options, is done ([#490](https://github.com/Polalalabear/amidst/pull/490)); path (a) and live Qwen/OpenAI come after acceptance |

None of these PRs is merged into `mainline/q1q5` yet; merging needs the user's authorization. The cross-camera 3D reconstruction line is paused but kept on the branch `archive/3d-line`.

### Development setup

Requires [`uv`](https://docs.astral.sh/uv/) and Node.js. Python is pinned to 3.12 (`.python-version`), Node to `.node-version`, and dependencies are locked by `uv.lock` and each `package-lock.json`:

```sh
git clone https://github.com/Polalalabear/amidst.git
cd amidst
scripts/setup_env.sh        # creates .venv (Python 3.12) and installs locked Python and node dependencies
.venv/bin/pytest tests/q1q5
AMIDST_REQUIRE_IMPL=1 node --test frontend/workbench-v2/*.test.mjs frontend/event-viewer/*.test.mjs
```

### Running the real-data demo

A clone contains code, configuration and documents only. Rendered frames, model weights and the detection index live in a local owned folder (default `~/amidst-artifacts/demo-owned-v1`, overridable with `AMIDST_DEMO_HOME`) and are not in the repository, so a clone alone cannot reproduce the demo. With that folder in place:

```sh
export AMIDST_DEMO_HOME="${AMIDST_DEMO_HOME:-$PWD/local/data/demo-owned-v1}"
PYTHONPATH=src uv run --offline --no-project \
  --python "$AMIDST_DEMO_HOME/runtime/python/bin/python3.12" \
  python -B scripts/setup_owned_demo.py        # first run, or after the locks change
./start_445_demo.command --port 8785
```

Then open `http://localhost:8785/workbench-v2/`. Details and moving to another machine are in the [owned-dependency notes](docs/operations/DEMO_OWNED_DEPENDENCIES_20261108.md); the demo and acceptance steps are in the [demo script and acceptance checklist](docs/operations/DEMO_SCRIPT_ACCEPTANCE_V1.md) (both in Traditional Chinese). Only macOS (darwin-arm64) has been verified so far.

### Branches and collaboration

- `mainline/q1q5`: default and integration branch; merge commits only.
- `claude/445-demo-integration` ([#485](https://github.com/Polalalabear/amidst/pull/485)): epic A integration branch, merged into mainline after acceptance.
- `claude/ui-redesign-v1` ([#487](https://github.com/Polalalabear/amidst/pull/487)): the new UI, merged into #485.
- `main`: the pre-Q1–Q5 history; not currently updated.
- Codex and Claude Code split work by file sets and data contracts; see [AGENTS.md](AGENTS.md). Merge commits only; no rebase or force-push.

### Documents

- [Core contract: search and track](docs/contracts/Q_CORE_SEARCH_TRACK_V1.md) (`Q_CORE_SEARCH_TRACK_V1`), [demo UI support contract](docs/contracts/DEMO_UI_SUPPORT_V1.md), [Q1–Q5 first-demo contract](docs/contracts/Q1_Q2_FIRST_DEMO_V1.md) (still the source for clocks, the detection index and the two-layer graph)
- [Demo script and acceptance checklist](docs/operations/DEMO_SCRIPT_ACCEPTANCE_V1.md), [owned-dependency notes](docs/operations/DEMO_OWNED_DEPENDENCIES_20261108.md), [Python 3.12 lock sync](docs/operations/DEMO_PY312_LOCK_SYNC_20261108.md)
- [Development rules](docs/specs/DEVELOPMENT_RULES.md) (architecture, assets, GT isolation, uncertainty), [Q1–Q5 product specification](docs/specs/Q1Q5_PRODUCT_SPEC.md)
- [Document index](docs/README.md), [archive index](docs/archive/ARCHIVE_20261027.md)
- Old issue numbers were folded into the four epics; the mapping is on [#93](https://github.com/Polalalabear/amidst/issues/93). `docs/operations/Q1Q5_PROGRESS.md` stops at 2026-10-27; #93 is authoritative.
- **For AI agents:** work by [AGENTS.md](AGENTS.md); this README does not repeat its rules.
