# Amidst

**多攝影機畫面的調查輔助工具：用條件「查找」畫面，選定目標後跨鏡頭「追蹤」，目標進入盲區時標出推測路線。每個答案都能追溯到來源證據。**

**An investigation aid for multi-camera footage: *search* frames by a condition, *track* a chosen target across cameras, and mark the inferred route when the target enters a blind interval. Every answer traces back to source evidence.**

[繁體中文](#繁體中文) | [English](#english)

> **狀態（2026-11-20）：**研究原型，全部資料來自 Blender 合成的受控場景，不是部署系統。目前在驗證研究假設 H1–H6：能看圖、又知道場景空間資訊的 Agent，在複雜情況下的切鏡決策和辨識是否比規則與 RT-DETR 好（D340、D341）。工作清單和決策紀錄在[任務板 #93](https://github.com/Polalalabear/amidst/issues/93)。
>
> **Status (2026-11-20):** research prototype. All data comes from a synthetic, controlled Blender scene; this is not a deployed system. Current work tests research hypotheses H1–H6: whether an Agent that sees frames and knows the scene layout makes better camera-switching and recognition decisions than the rules and RT-DETR in hard cases (D340, D341). The work list and decision log are on [task board #93](https://github.com/Polalalabear/amidst/issues/93).

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

前台預設是展示模式：只顯示事件名稱和白話狀態，技術標籤收進 ⓘ。後台完整顯示所有欄位。加上 `?ui=legacy` 會切到 v2 的引擎版面（不是舊工作台，舊工作台已於 D268 下線）。

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
- 追蹤方式可以在「規則」和「Agent」之間切換（D340）。**規則是預設和退路**；Agent 模式預設關，開啟時可以看渲染畫面、從所有偵測中選人、回答「仍在這台」「不在」或「下一台看哪台」，每個請求都附場景上下文（區域連通、鏡頭圖與核定等級、鏡頭位置／朝向／FOV／覆蓋範圍），只取已提交的設定與標定。付費呼叫一律經 `ApiGuard`；Agent 失敗時退回規則。程式在 `src/amidst/q1q5/agent_service.py`、`scene_context.py`、`camera_projection.py`，介面見[產品規格 §4.3](docs/specs/Q1Q5_PRODUCT_SPEC.md)。
- 自然語言查詢把句子轉成查詢選項，使用者確認後才執行。

### 核心原則

| 原則 | 說明 |
| --- | --- |
| 證據狀態分開 | `OBSERVED`、`INFERRED`、`MISSING`、`UNKNOWN` 分開保存。前台改成白話顯示，但資料層不合併 |
| 身分不自動確認 | 顏色相符只代表證據強弱，不代表同一人；身分維持 `UNCONFIRMED` |
| Ground Truth 隔離 | GT、渲染軌跡、visibility、depth、劇本關鍵影格不進推論、測試輸入或畫面；請求帶這些鍵會被拒絕（422） |
| 來源追溯與 fail-closed | 每筆資料綁定來源、run、時鐘與 hash；不符就拒絕，缺資料只關閉該功能 |
| 依賴自有 | 依賴、鎖定檔、啟動腳本、資料和模型的 manifest 都在 repo 裡，不借用舊環境（D133） |

### 目前進度（2026-11-20）

研究假設與目前證據（[假設計畫 §0](docs/evaluation/AGENT_VS_RULE_HYPOTHESES_20261120.md)；條件：渲染合成、預錄、A4-1／B4-1 兩事件、單一目標、DRAFT 鏡頭圖）：

| 假設 | 內容 | 目前狀態 |
| --- | --- | --- |
| H5 辨識 | Agent 看圖判斷「這格有沒有目標」比 RT-DETR＋規則準 | 有條件成立：F1 0.52 → 0.96，增益集中在遮擋、遠小、沒有人物框的格子（[W1](docs/evaluation/W1_FRAME_EVAL_20261120.md)） |
| H2 機制 | 優勢來自看圖 | 有條件成立（部分）：不給圖就沒有優勢，但「不在」的判斷略差 |
| H1 切換決策 | 複雜情況下 Agent 切鏡比規則好 | 尚無數據：兩個簡單事件只驗證可行（[W2](docs/evaluation/W2_ACTIVE_AGENT_20261120.md)） |
| 即時 | 模擬即時下的增益 | 0：單次延遲約 4.3 s，比失聯段長 |
| H3、H4 | 閘門改資訊、依空間資訊主動找下一台 | H3 無害也無可見好處；H4 只有描述性訊號，不支持 |
| H6 | 每個模式都能切規則／Agent | 部分完成：統一介面已有；8785 開關、LIVE Agent（W3）、查找待做 |

下一步：W3 LIVE 難題集（前置已合併：LIVE 重新取得 R1 #608 `cfbfe4e9`，門檻 UNKNOWN、預設關閉；錄製重播 #617 `1742ed06`）、E3 劇本（#652）、W4 複雜場景。G7 已修正：所有付費呼叫經 ApiGuard（4f665d55）。

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

Clone 只取得程式、設定和文件。渲染畫面、模型權重、偵測索引這些資料放在本機的自有資料夾（預設 `local/data/demo-owned-v1`，在 repo 根目錄之下、已被 `.gitignore`；整個資料夾沒有單一 SHA-256（不適用），各檔的 manifest 見依賴收編說明；可用 `AMIDST_DEMO_HOME` 改位置；找不到時報 `OWNED_ROOT_NOT_FOUND`），不在 repository 裡，所以光靠 clone 不能重現 Demo。資料夾備妥後：

```sh
export AMIDST_DEMO_HOME="${AMIDST_DEMO_HOME:-$PWD/local/data/demo-owned-v1}"
PYTHONPATH=src uv run --offline --no-project \
  --python "$AMIDST_DEMO_HOME/runtime/python/bin/python3.12" \
  python -B scripts/setup_owned_demo.py        # 第一次，或鎖定檔變了之後才需要
./start_445_demo.command --port 8785
```

然後開 `http://localhost:8785/workbench-v2/`。細節和移機方式見[依賴收編說明](docs/operations/DEMO_OWNED_DEPENDENCIES_20261108.md)；展示和驗收步驟見 [Demo 腳本兼驗收清單](docs/operations/DEMO_SCRIPT_ACCEPTANCE_V1.md)。目前只驗證過 Mac（darwin-arm64）。

### 分支與協作

- `main`：整合分支（D200；GitHub 預設分支），PR 的 base 一律是 `main`，CI `checks` 要綠，只用 merge commit，不 rebase、不 force。`mainline/q1q5` 凍結在 `8c741451`，只是歷史。
- 功能分支：一個大功能一條分支，Claude 用 `claude/feat-<line>`、Codex 用 `codex/feat-<line>`；小修正進既有分支（D216、D248）。
- Codex 和 Claude Code 依檔案和資料契約分工，規則見 [AGENTS.md](AGENTS.md)。

### 文件導覽

- [核心功能契約：查找與追蹤](docs/contracts/Q_CORE_SEARCH_TRACK_V1.md)（`Q_CORE_SEARCH_TRACK_V1`）、[Demo UI 支援契約](docs/contracts/DEMO_UI_SUPPORT_V1.md)、[Q1–Q5 第一版契約](docs/contracts/Q1_Q2_FIRST_DEMO_V1.md)（時鐘、偵測索引、兩層圖的定義沿用這份）
- [Demo 腳本兼驗收清單](docs/operations/DEMO_SCRIPT_ACCEPTANCE_V1.md)、[依賴收編說明](docs/operations/DEMO_OWNED_DEPENDENCIES_20261108.md)、[Python 3.12 鎖定同步](docs/operations/DEMO_PY312_LOCK_SYNC_20261108.md)
- [開發規則](docs/specs/DEVELOPMENT_RULES.md)（架構、資產、GT 隔離、不確定性、D340 Agent 模式）、[Q1–Q5 產品規格](docs/specs/Q1Q5_PRODUCT_SPEC.md)（§2 資料流、§4 介面）
- [Agent vs 規則假設計畫 H1–H6](docs/evaluation/AGENT_VS_RULE_HYPOTHESES_20261120.md)、[W1 逐格評估](docs/evaluation/W1_FRAME_EVAL_20261120.md)、[W2 主動 Agent](docs/evaluation/W2_ACTIVE_AGENT_20261120.md)、[Agent 接線與 ApiGuard 檢查](docs/engineering/AGENT_API_WIRING_AUDIT_20261120.md)
- [程式碼 ↔ 文件對應表](docs/index/CODE_DOC_MAP.md)、[文件索引](docs/README.md)、[封存索引](docs/archive/ARCHIVE_20261027.md)
- 工作清單在 [#93](https://github.com/Polalalabear/amidst/issues/93) 本文（D281）；[進度導覽](docs/operations/Q1Q5_PROGRESS.md) 列出每個 PR 與 issue（批次補列到 #650）。
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

The front end defaults to presentation mode: it shows the event name and plain-language status, with technical labels behind ⓘ. The admin page shows every field. Adding `?ui=legacy` switches to the v2 engine layout (not the old workbench, which was retired in D268).

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
- Tracking can switch between "rules" and "Agent" (D340). **Rules are the default and the fallback.** Agent mode is off by default; when on, the Agent may look at rendered frames, choose among all detections, and answer "still on this camera", "not visible" or "check camera X next". Every request carries the scene context (region connectivity, the camera graph with approval levels, camera position/heading/FOV/coverage), taken only from committed configuration and calibration. Paid calls always go through `ApiGuard`; on failure the rule answer stands. Code: `src/amidst/q1q5/agent_service.py`, `scene_context.py`, `camera_projection.py`; interface in [product spec §4.3](docs/specs/Q1Q5_PRODUCT_SPEC.md).
- Natural-language queries turn a sentence into query options that run only after the user confirms.

### Principles

| Principle | Meaning |
| --- | --- |
| Separate evidence states | `OBSERVED`, `INFERRED`, `MISSING` and `UNKNOWN` are stored separately. The front end words them plainly; the data layer never merges them |
| No automatic identity | A color match is evidence strength, not identity; identity stays `UNCONFIRMED` |
| Ground Truth isolation | GT, render trajectories, visibility, depth and script keyframes never enter inference, test inputs or the screen; requests carrying them are rejected (422) |
| Provenance and fail-closed | Every record is bound to source, run, clock and hash. Mismatches are rejected; missing data disables only that feature |
| Owned dependencies | Dependencies, lock files, launch scripts and data/model manifests live in the repository; no old environments are reused (D133) |

### Progress (2026-11-20)

Research hypotheses and current evidence ([hypothesis plan §0](docs/evaluation/AGENT_VS_RULE_HYPOTHESES_20261120.md); conditions: synthetic rendering, recorded footage, two events A4-1/B4-1, one target, DRAFT camera graph):

| Hypothesis | Claim | Current status |
| --- | --- | --- |
| H5 recognition | Looking at the frame, the Agent judges "is the target here" better than RT-DETR plus rules | Holds with conditions: F1 0.52 → 0.96, gains concentrated in occluded, small/distant and no-person-box frames ([W1](docs/evaluation/W1_FRAME_EVAL_20261120.md)) |
| H2 mechanism | The gain comes from seeing the image | Partly holds: without images there is no gain, but "not visible" answers are slightly worse |
| H1 switching | In hard cases the Agent switches cameras better than the rules | No data yet: two simple events only show feasibility ([W2](docs/evaluation/W2_ACTIVE_AGENT_20261120.md)) |
| Real time | Gain under simulated real time | Zero: one call takes about 4.3 s, longer than the lost spans |
| H3, H4 | Gates as information; spatial reasoning to pick the next camera | H3 no harm and no visible benefit; H4 only a descriptive signal, not supported |
| H6 | Every mode can switch rules/Agent | Partly done: the shared interface exists; 8785 switch, LIVE Agent (W3) and search remain |

Next: W3 on the LIVE hard set (prerequisites merged: LIVE relock R1 #608 `cfbfe4e9`, thresholds UNKNOWN and off by default; recording/replay #617 `1742ed06`), E3 scripts (#652) and W4 complex scenes. G7 is fixed: every paid call goes through `ApiGuard` (`4f665d55`).

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

A clone contains code, configuration and documents only. Rendered frames, model weights and the detection index live in a local owned folder (default `local/data/demo-owned-v1` under the repository root, git-ignored; a whole-folder SHA-256 is not applicable, per-file manifests are in the owned-dependency notes; overridable with `AMIDST_DEMO_HOME`; `OWNED_ROOT_NOT_FOUND` if missing) and are not in the repository, so a clone alone cannot reproduce the demo. With that folder in place:

```sh
export AMIDST_DEMO_HOME="${AMIDST_DEMO_HOME:-$PWD/local/data/demo-owned-v1}"
PYTHONPATH=src uv run --offline --no-project \
  --python "$AMIDST_DEMO_HOME/runtime/python/bin/python3.12" \
  python -B scripts/setup_owned_demo.py        # first run, or after the locks change
./start_445_demo.command --port 8785
```

Then open `http://localhost:8785/workbench-v2/`. Details and moving to another machine are in the [owned-dependency notes](docs/operations/DEMO_OWNED_DEPENDENCIES_20261108.md); the demo and acceptance steps are in the [demo script and acceptance checklist](docs/operations/DEMO_SCRIPT_ACCEPTANCE_V1.md) (both in Traditional Chinese). Only macOS (darwin-arm64) has been verified so far.

### Branches and collaboration

- `main`: the integration branch (D200; GitHub default). Every PR targets `main`, needs the CI check `checks` green and merges with a merge commit only; no rebase or force-push. `mainline/q1q5` is frozen at `8c741451` and is history only.
- Feature branches: one branch per large feature, `claude/feat-<line>` for Claude and `codex/feat-<line>` for Codex; small fixes go to the existing branch (D216, D248).
- Codex and Claude Code split work by file sets and data contracts; see [AGENTS.md](AGENTS.md).

### Documents

- [Core contract: search and track](docs/contracts/Q_CORE_SEARCH_TRACK_V1.md) (`Q_CORE_SEARCH_TRACK_V1`), [demo UI support contract](docs/contracts/DEMO_UI_SUPPORT_V1.md), [Q1–Q5 first-demo contract](docs/contracts/Q1_Q2_FIRST_DEMO_V1.md) (still the source for clocks, the detection index and the two-layer graph)
- [Demo script and acceptance checklist](docs/operations/DEMO_SCRIPT_ACCEPTANCE_V1.md), [owned-dependency notes](docs/operations/DEMO_OWNED_DEPENDENCIES_20261108.md), [Python 3.12 lock sync](docs/operations/DEMO_PY312_LOCK_SYNC_20261108.md)
- [Development rules](docs/specs/DEVELOPMENT_RULES.md) (architecture, assets, GT isolation, uncertainty, D340 Agent mode), [Q1–Q5 product specification](docs/specs/Q1Q5_PRODUCT_SPEC.md) (§2 data flow, §4 interfaces)
- [Agent vs rule hypotheses H1–H6](docs/evaluation/AGENT_VS_RULE_HYPOTHESES_20261120.md), [W1 frame evaluation](docs/evaluation/W1_FRAME_EVAL_20261120.md), [W2 active Agent](docs/evaluation/W2_ACTIVE_AGENT_20261120.md), [Agent wiring and ApiGuard audit](docs/engineering/AGENT_API_WIRING_AUDIT_20261120.md) (all in Traditional Chinese)
- [Code ↔ document map](docs/index/CODE_DOC_MAP.md), [document index](docs/README.md), [archive index](docs/archive/ARCHIVE_20261027.md)
- The work list is the body of [#93](https://github.com/Polalalabear/amidst/issues/93) (D281); the [progress guide](docs/operations/Q1Q5_PROGRESS.md) lists every PR and issue (batch-updated to #650).
- **For AI agents:** work by [AGENTS.md](AGENTS.md); this README does not repeat its rules.
