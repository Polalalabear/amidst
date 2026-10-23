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

Q1–Q5 的契約、計畫、規則例外與時鐘對應已合併進主線 `mainline/q1q5`。Codex 已把儲存層、偵測索引與 HSV 證據、同鏡頭 IoU 串接、
靜態圖與 D28 候選、Q3 規則解析，以及 Q1、Q3、Q4、Q5 的評估器合併進 `codex/q1q5-staging`，等待審查後分批進主線。
工作台 T1–T4、依序查證的 Agent、Qwen3 執行環境、Q5 `RULE_ONLY` 控制器、Q1 索引搜尋與 Q4 證據彙整仍是 Draft PR；
其中多項卡在一致性檢查包的修正、空候選的契約缺口，以及 Qwen3 工具流程尚未通過。正式 RGB 與正式索引還在等授權，
真實 RGB 端到端數字目前只有預覽。

跨攝影機盲區的 3D 軌跡重建線暫停但保留，在分支 `archive/3d-line`。

全部 PR 與 issue 依五大問題與「已完成／進行中／未完成／待確認」的分類，見 **[Q1–Q5 進度導覽](docs/operations/Q1Q5_PROGRESS.md)**；
即時狀態看[任務板 #93](https://github.com/Polalalabear/amidst/issues/93)。

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

The Q1–Q5 contract, plan, rule exception and clock mapping are merged into `mainline/q1q5`. Codex has merged the store,
the detection index with HSV evidence, same-camera IoU linking, the static graph with D28 candidates, the rule-based Q3
parser, and the Q1, Q3, Q4 and Q5 evaluators into `codex/q1q5-staging`; they move to mainline in reviewed batches.
Workbench T1–T4, the sequential Agent, the Qwen3 runtime, the Q5 `RULE_ONLY` controller, Q1 index search and Q4 evidence
are still Draft PRs. Several are blocked on conformance-kit fixes, a contract gap for empty candidate sets, and a Qwen3
tool flow that does not pass yet. Formal RGB and the formal index await authorization, and end-to-end numbers on real RGB
are preview only.

The cross-camera blind-interval 3D reconstruction line is paused but kept on the branch `archive/3d-line`.

Every PR and issue, classified by the five questions and by done / in progress / not done / to confirm, is in the
**[Q1–Q5 progress guide](docs/operations/Q1Q5_PROGRESS.md)** (Traditional Chinese). Live status is on
[task board #93](https://github.com/Polalalabear/amidst/issues/93).

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
