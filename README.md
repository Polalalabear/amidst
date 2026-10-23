# Amidst

**多攝影機畫面的調查工作台：依條件找鏡頭、在畫面中找人、理解使用者的問題、判斷畫面是否含目標，並在目標離開鏡頭時決定要不要切鏡。每個答案都能追溯到來源證據。**

**An investigation workbench for multi-camera footage: find cameras by a condition, find a person in the footage, understand the user's question, judge whether a frame contains the target, and decide when to switch cameras as the target leaves. Every answer traces back to source evidence.**

[繁體中文](#繁體中文) | [English](#english)

> **狀態（2026-10-24）：**研究原型，全部資料來自 Blender 合成的受控場景，不是部署系統。主線目標是 **Q1–Q5 第一版 Demo**；即時進度看[任務看板 #93](https://github.com/Polalalabear/amidst/issues/93)。
>
> **Status (2026-10-24):** research prototype. All data comes from a synthetic, controlled Blender scene; this is not a deployed system. The current goal is the **Q1–Q5 first demo**; live progress is on [task board #93](https://github.com/Polalalabear/amidst/issues/93).

## 繁體中文

### 這個專案在做什麼

建築內的攝影機很多，調查人員常常要逐支影片回看。Amidst 讓使用者用一句話提問，系統從偵測索引中找出相關鏡頭與畫面，
並在目標離開某台鏡頭時判斷下一台該看哪裡。系統只回答證據支持的內容：身分一律 `UNCONFIRMED`，證據不足時回 `UNKNOWN`，不以猜測補上。

| 編號 | 能力 | 說明 |
| --- | --- | --- |
| Q1 | 依條件找鏡頭 | 例如「哪些鏡頭在這段時間拍到穿紅衣的人」，回傳鏡頭與時段 |
| Q2 | 在畫面中找人 | 在時間軸與主畫面上標出人物框，同一鏡頭內以 IoU 串接成片段 |
| Q3 | 理解使用者語意 | 把自然語言問題解析成結構化查詢；解析失敗時有可稽核的規則備援 |
| Q4 | 判斷畫面是否含目標 | 由模型自己的偵測與顏色證據判斷任一鏡頭的 2D 畫面是否有目標 |
| Q5 | 決定是否切鏡 | 目標離開鏡頭時，從合法的候選鏡頭中判斷下一個要看的鏡頭，以維持追蹤 |

### 方法

```text
來源 RGB 畫面 ─▶ RT-DETR 人物偵測 ─▶ 上半身 HSV 顏色訊號（STRONG／WEAK／NONE／UNKNOWN）
                                         │
                                         ▼
                                    偵測索引（綁定來源、時鐘與 hash）
                                         │
         ┌───────────────────────────────┼───────────────────────────────┐
         ▼                               ▼                               ▼
   Q3 語意解析                    兩層圖：鏡頭拓撲                  Q1／Q2／Q4 查詢
  （本機 LLM＋規則備援）           ＋同鏡頭 IoU 串接                與證據彙整
                                         │
                                         ▼
                        Q5：決定性排序產生 top-k 候選鏡頭（D28）
                        Agent 依序查證候選；超過輪數或時間上限
                        改由決定性規則（RULE_ONLY）完整接手
```

- 候選集合與順序由決定性服務產生，Agent 只在合法候選內查證與判斷，不負責排序。
- 第一版不使用追蹤器或 ReID，也不放同色干擾人物；LLM 在本機執行（Ollama），不呼叫外部 API。
- 每個回應都標示是否用到 Agent、是否觸發備援及原因，並保留 prompt 紀錄以便重播。

### 核心原則

| 原則 | 說明 |
| --- | --- |
| 證據狀態分開 | 觀測、推論、`MISSING`、`UNKNOWN` 分開保存與顯示，不混用 |
| 身分不自動確認 | 顏色相符只是證據強弱，不代表同一人；身分維持 `UNCONFIRMED` |
| Ground Truth 隔離 | GT 只用於模擬匯出、預測凍結後的評估與除錯，不進入偵測、索引、排序或 Agent |
| 來源追溯與 fail-closed | 每筆資料綁定來源、run、時鐘與 hash；不符就拒絕，缺資料只關閉該功能 |
| 決定性備援 | 沒有 Agent 或 Agent 失敗時，`RULE_ONLY` 能完整回答，結果不依賴模型 |

### 目前進度（2026-10-24）

**已合併進主線 `mainline/q1q5`：**
- 契約與計畫：[Q1–Q5 第一版契約 #86](https://github.com/Polalalabear/amidst/pull/86)、[計畫 #92](https://github.com/Polalalabear/amidst/pull/92)（D65 於 [checkpoint #88](https://github.com/Polalalabear/amidst/issues/88) 核准）
- 規則：[Q1–Q5 Agent 例外 #125](https://github.com/Polalalabear/amidst/pull/125)
- 時鐘對應與有界時間覆蓋：[#134](https://github.com/Polalalabear/amidst/pull/134)
- 工作台 v2 外框與 API（[#74](https://github.com/Polalalabear/amidst/pull/74)、[#79](https://github.com/Polalalabear/amidst/pull/79)）、多鏡頭播放格（[#71](https://github.com/Polalalabear/amidst/pull/71)）、真實 RGB 與限定範圍媒體存取（[#80](https://github.com/Polalalabear/amidst/pull/80)）、受控場景安全載入（[#75](https://github.com/Polalalabear/amidst/pull/75)）

**在 Codex 整合分支 `codex/q1q5-staging`（10-21～10-22 合併 27 個 PR，尚未進主線，等 Claude 分批審查）：**
- 儲存層、離線偵測索引與 HSV 證據、同鏡頭 IoU 串接、靜態圖驗證與 D28 候選、參數組綁定
- 本機 Ollama 介面、Q3 規則解析與備援
- Q1、Q3、Q4、Q5 評估器，以及題目撰寫指南與人工標註匯入
- r004 場景靜態匯出與 90 度廣角鏡頭選定、Demo 腳本草稿

**進行中（Draft PR）：**工作台 T1–T4（[#175](https://github.com/Polalalabear/amidst/pull/175)、[#176](https://github.com/Polalalabear/amidst/pull/176)、[#177](https://github.com/Polalalabear/amidst/pull/177)、[#180](https://github.com/Polalalabear/amidst/pull/180)）、
依序查證的 Agent 與重播（[#172](https://github.com/Polalalabear/amidst/pull/172)）、固定版本 Qwen3 執行環境（[#174](https://github.com/Polalalabear/amidst/pull/174)）、
Q5 `RULE_ONLY` 控制器（[#169](https://github.com/Polalalabear/amidst/pull/169)）、Q1 索引搜尋（[#157](https://github.com/Polalalabear/amidst/pull/157)）、Q4 候選證據（[#154](https://github.com/Polalalabear/amidst/pull/154)）、
r004 預審包 v2（[#187](https://github.com/Polalalabear/amidst/pull/187)）、一致性檢查工具（[#127](https://github.com/Polalalabear/amidst/pull/127)）。

**尚未解決：**
- Qwen3 的 schema／工具呼叫流程還沒通過（[#186](https://github.com/Polalalabear/amidst/issues/186)）；候選為空時的契約缺口（[#183](https://github.com/Polalalabear/amidst/issues/183)）；檢查工具與產品輸出對齊（[#145](https://github.com/Polalalabear/amidst/issues/145)）。
- 真實 RGB 端到端數字目前只有預覽；工程 UI、HTTP 與重播仍使用合成資料。
- 接下來的順序：靜態圖檢查（[#117](https://github.com/Polalalabear/amidst/issues/117)）→ 正式 RGB（[#115](https://github.com/Polalalabear/amidst/issues/115)）→ 核准後建正式索引（[#118](https://github.com/Polalalabear/amidst/issues/118)）→ 整合上列 Draft PR。

**暫停但保留：**跨攝影機盲區的 3D 軌跡重建線，保存在分支 `archive/3d-line`。
舊 Office Demo 整合分支已封存為 tag `archive/office-demo-visualization`。

### 開始使用

需要 Python ≥3.12 與 [`uv`](https://docs.astral.sh/uv/)：

```sh
git clone https://github.com/Polalalabear/amidst.git
cd amidst
uv sync --frozen
```

Clone 只取得程式、設定與文件。Blender 場景、渲染畫面、模型權重、偵測索引與資料庫都只存在本機，不在 repository 裡，
所以 clone 下來不能直接重現 Demo。

### 分支與協作

- `mainline/q1q5`：預設與整合分支，只接受 merge commit。
- `codex/q1q5-staging`：Codex 的整合分支，審查後分批合併進主線。
- `main`：Q1–Q5 轉向前的歷史版本，目前不更新。
- Codex 與 Claude Code 依檔案與資料契約分工；檢查點以 `checkpoint` 標籤的 issue 管理。規則見 [AGENTS.md](AGENTS.md)。

### 文件導覽

- [Q1–Q5 第一版契約](docs/contracts/Q1_Q2_FIRST_DEMO_V1.md)、[Codex 討論稿與計畫](docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md)、[契約審查](docs/engineering/Q1_Q5_CONTRACT_REVIEW_20261020.md)
- [開發規則](docs/specs/DEVELOPMENT_RULES.md)（架構、資產、GT 隔離、不確定性）
- [文件索引](docs/README.md)
- [任務看板 #93](https://github.com/Polalalabear/amidst/issues/93)、[Checkpoint #88](https://github.com/Polalalabear/amidst/issues/88)
- **給 AI agent：**依 [AGENTS.md](AGENTS.md) 工作；本 README 不重複其規則。

## English

### What it does

Buildings have many cameras, and investigators often review every video by hand. Amidst lets a user ask a question in
plain language; the system finds the relevant cameras and frames in a detection index and, when the target leaves a
camera, decides which camera to watch next. It answers only what the evidence supports: identity is always
`UNCONFIRMED`, and missing evidence yields `UNKNOWN` rather than a guess.

| ID | Capability | Description |
| --- | --- | --- |
| Q1 | Find cameras by a condition | e.g. "which cameras saw a person in red during this period"; returns cameras and time ranges |
| Q2 | Find a person in footage | Person boxes on the timeline and main view, linked into same-camera segments by IoU |
| Q3 | Understand the question | Parses natural language into a structured query, with an auditable rule-based fallback |
| Q4 | Judge whether a frame has the target | Uses the model's own detection and color evidence on any camera's 2D frame |
| Q5 | Decide whether to switch cameras | When the target leaves, picks the next camera from legal candidates to keep tracking |

### Method

```text
Source RGB frames ─▶ RT-DETR person detection ─▶ upper-body HSV color signal (STRONG / WEAK / NONE / UNKNOWN)
                                                    │
                                                    ▼
                                    Detection index (bound to source, clock and hash)
                                                    │
         ┌──────────────────────────────────────────┼──────────────────────────────┐
         ▼                                          ▼                              ▼
   Q3 query parsing                   Two-layer graph: camera topology       Q1 / Q2 / Q4 queries
  (local LLM + rule fallback)         + same-camera IoU linking              and evidence summaries
                                                    │
                                                    ▼
                        Q5: deterministic ordering yields top-k candidate cameras (D28)
                        The Agent checks candidates in order; past a round or time limit
                        the deterministic RULE_ONLY path takes over completely
```

- A deterministic service produces the candidate set and order. The Agent only checks and judges legal candidates; it never ranks.
- The first version uses no tracker or ReID and no same-color distractor. The LLM runs locally (Ollama); no external API is called.
- Every response records whether the Agent was used, whether the fallback fired and why, and keeps the prompts for replay.

### Principles

| Principle | Meaning |
| --- | --- |
| Separate evidence states | Observed, inferred, `MISSING` and `UNKNOWN` are stored and shown separately, never mixed |
| No automatic identity | A color match is evidence strength, not identity; identity stays `UNCONFIRMED` |
| Ground Truth isolation | GT is used only for simulation export, evaluation after predictions freeze, and debugging; never for detection, indexing, ranking or the Agent |
| Provenance and fail-closed | Every record is bound to source, run, clock and hash. Mismatches are rejected; missing data disables only that feature |
| Deterministic fallback | Without the Agent, or when it fails, `RULE_ONLY` answers fully; results do not depend on a model |

### Progress (2026-10-24)

**Merged into `mainline/q1q5`:**
- Contract and plan: [Q1–Q5 first-demo contract #86](https://github.com/Polalalabear/amidst/pull/86), [plan #92](https://github.com/Polalalabear/amidst/pull/92) (approved as D65 on [checkpoint #88](https://github.com/Polalalabear/amidst/issues/88))
- Rules: [Q1–Q5 Agent exception #125](https://github.com/Polalalabear/amidst/pull/125)
- Clock mapping and bounded time coverage: [#134](https://github.com/Polalalabear/amidst/pull/134)
- Workbench v2 shell and API ([#74](https://github.com/Polalalabear/amidst/pull/74), [#79](https://github.com/Polalalabear/amidst/pull/79)), multi-camera player grid ([#71](https://github.com/Polalalabear/amidst/pull/71)), real RGB with scoped media access ([#80](https://github.com/Polalalabear/amidst/pull/80)), controlled-scene safe loaders ([#75](https://github.com/Polalalabear/amidst/pull/75))

**On Codex's integration branch `codex/q1q5-staging` (27 PRs merged 10-21 to 10-22; not yet in mainline, awaiting Claude's batched review):**
- Store, offline detection index with HSV evidence, same-camera IoU linking, static graph validation with D28 candidates, parameter-set binding
- Local Ollama provider, rule-based Q3 parser with fallback
- Q1, Q3, Q4 and Q5 evaluators, a question-authoring guide and a human-annotation importer
- r004 static scene export with the selected 90° wide camera, and a draft demo script

**In progress (Draft PRs):** workbench T1–T4 ([#175](https://github.com/Polalalabear/amidst/pull/175), [#176](https://github.com/Polalalabear/amidst/pull/176), [#177](https://github.com/Polalalabear/amidst/pull/177), [#180](https://github.com/Polalalabear/amidst/pull/180)),
the sequential Agent with replay ([#172](https://github.com/Polalalabear/amidst/pull/172)), a pinned Qwen3 runtime ([#174](https://github.com/Polalalabear/amidst/pull/174)),
the Q5 `RULE_ONLY` controller ([#169](https://github.com/Polalalabear/amidst/pull/169)), Q1 index search ([#157](https://github.com/Polalalabear/amidst/pull/157)), Q4 candidate evidence ([#154](https://github.com/Polalalabear/amidst/pull/154)),
the r004 pre-review package v2 ([#187](https://github.com/Polalalabear/amidst/pull/187)) and the conformance kit ([#127](https://github.com/Polalalabear/amidst/pull/127)).

**Open problems:**
- The Qwen3 schema and tool-call flow does not pass yet ([#186](https://github.com/Polalalabear/amidst/issues/186)); the contract has a gap for empty candidate sets ([#183](https://github.com/Polalalabear/amidst/issues/183)); the conformance kit and product output still need aligning ([#145](https://github.com/Polalalabear/amidst/issues/145)).
- End-to-end numbers on real RGB are preview only; the engineering UI, HTTP and replay still use synthetic data.
- Next, in order: static graph check ([#117](https://github.com/Polalalabear/amidst/issues/117)) → formal RGB ([#115](https://github.com/Polalalabear/amidst/issues/115)) → formal index after approval ([#118](https://github.com/Polalalabear/amidst/issues/118)) → integrate the Draft PRs above.

**Paused but kept:** the cross-camera blind-interval 3D reconstruction line, kept on the branch `archive/3d-line`.
The old Office Demo integration branch is archived as the tag `archive/office-demo-visualization`.

### Getting started

Requires Python ≥3.12 and [`uv`](https://docs.astral.sh/uv/):

```sh
git clone https://github.com/Polalalabear/amidst.git
cd amidst
uv sync --frozen
```

A clone contains code, configuration and documents only. Blender scenes, rendered frames, model weights, the detection
index and databases live on a local machine and are not in the repository, so a clone cannot reproduce the demo on its own.

### Branches and collaboration

- `mainline/q1q5`: default and integration branch; merge commits only.
- `codex/q1q5-staging`: Codex's integration branch, merged into mainline in reviewed batches.
- `main`: the pre-Q1–Q5 history; not currently updated.
- Codex and Claude Code split work by file sets and data contracts; checkpoints are issues labeled `checkpoint`. See [AGENTS.md](AGENTS.md).

### Documents

- [Q1–Q5 first-demo contract](docs/contracts/Q1_Q2_FIRST_DEMO_V1.md), [Codex discussion and plan](docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md), [contract review](docs/engineering/Q1_Q5_CONTRACT_REVIEW_20261020.md)
- [Development rules](docs/specs/DEVELOPMENT_RULES.md) (architecture, assets, GT isolation, uncertainty)
- [Document index](docs/README.md)
- [Task board #93](https://github.com/Polalalabear/amidst/issues/93), [checkpoint #88](https://github.com/Polalalabear/amidst/issues/88)
- **For AI agents:** work by [AGENTS.md](AGENTS.md); this README does not repeat its rules.
