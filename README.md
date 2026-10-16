# Amidst

**跨攝影機盲區的證據工作台：選定一個目標，跟著來源證據穿過攝影機看不到的區段，並誠實標示哪些是觀測、哪些是推論、哪些仍然未知。**

**An evidence workbench for camera blind spots: follow a selected target's source evidence through the intervals no camera sees, and keep what was observed, inferred and still unknown visibly distinct.**

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

### 這個專案在做什麼

建築內的攝影機視野通常不重疊。目標離開一台攝影機、過一段時間才出現在另一台時，中間發生了什麼沒有任何畫面可以證明。
一般系統會直接給出一條看似確定的路線；Amidst 則把「看到的」「推測的」「缺失的」「未知的」分開保留，
並給出物理上可能的情境與其不確定程度，讓調查者知道該相信什麼、還該去看哪些畫面。

目前在 Blender 合成的校園場景（`school_v3`）中開發與驗證，屬於研究原型，不是部署系統。

### 實用情境（目標）

- 調查人員不必逐支影片人工回看：系統依可能路徑指出「哪台攝影機、哪個時段」值得檢視。
- 對結果的可信程度有明確標示：缺少證據的區段不會被畫成確定路線，身分不會被系統自動確認。

### 核心概念

| 概念 | 說明 |
| --- | --- |
| 四種證據狀態 | `PROJECTED_OBSERVATION`（由影像像素投影）、`INFERRED_*`（推論）、`MISSING`（缺失，不補值）、`UNKNOWN`（證據不足）。工作台以不同樣式呈現，不混用。 |
| 可信的不確定性 | 盲區內不輸出單一路線，而是一組物理上可能的路徑與每個時刻的可能範圍；排序代表合理程度，不是機率。 |
| 身分與物理邊界 | 身分維持 `UNCONFIRMED`；通行性、碰撞與人體淨空維持 `UNKNOWN`，除非有經授權的證據。 |
| Ground Truth 隔離 | GT 只用於模擬匯出、預測凍結後的評估與除錯展示，不進入推論、候選搜尋或排序。 |
| 來源追溯與 fail-closed | 每筆資料綁定來源、run、時鐘與 hash；不符即拒絕，缺資料只關閉該功能，不以替代資料補上。 |

### 方法與架構

```text
觀測 ──▶ 假設 ──▶ 檢索 ──▶ 驗證
 │        │        │        │
 │        │        │        └─ 檢索畫面中沒有目標 → 成為負證據，刪除不可能的假設
 │        │        └─ 以假設路徑 × 攝影機可見範圍，找出可能拍到目標的畫面
 │        └─ 盲區內的物理推測曲線：可走區域、速度範圍、不可被看見的約束
 └─ 單一攝影機：偵測 → 接地點 → 投影到地板（公尺）
```

**實作狀態：** 觀測（單鏡頭定位）、有界跨鏡頭候選與工作台已實作；盲區推測曲線、假設驅動檢索與負證據閉環為目標 2026-11-01 的開發中項目，進度見[專案狀態](docs/history/STATUS.md)。

系統分為六層：觀測來源（Blender 場景、校正攝影機、合成 RGB）→ 感知與時間理解（像素軌跡、暫定關聯）→
空間與事件理解（平面投影、局部幾何、導航拓撲、有界多候選）→ 狀態與儲存（版本化輸出、案例、人審、收據）→
檢索與推理（確定性檢索、typed tools、Agent 編排）→ 應用（共用工作台：來源展示、2D／3D 同步、調查、回放、審查）。
各層的評估分開記錄，某一層通過不擴大其他層的核准範圍。

### 研究問題

| 編號 | 問題 | 量化指標 |
| --- | --- | --- |
| RQ1 | 單一攝影機的地板定位有多準？遮擋與斜視角如何影響？ | 平均／最大誤差（m）、覆蓋率、跳點數、每像素敏感度 |
| RQ2 | 盲區推測能否涵蓋真實路徑，同時保持精準？ | 涵蓋率、帶寬、最佳假設距離與排名 |
| RQ3 | 跨攝影機關聯能否把正確延續排在前面？ | Top-1／Top-3 命中率、MRR、錯誤關聯率 |
| RQ4 | 依假設檢索畫面能省下多少人工檢視？ | 召回率、需檢視畫面比例、查詢延遲 |

最新結果與進度見[專案狀態](docs/history/STATUS.md)。

### 工程特性

- **可重現：** 版本化輸出、來源收據與確定性重播；同一請求的回應 hash 可核對。
- **有界檢索：** 以索引取代逐張掃描影像，每次查詢有讀取上限。
- **Agent 編排與確定性備援：** Agent 只呼叫有界、可稽核的工具；沒有 Agent 時系統照常運作，結果不依賴模型。
- **分工明確的多 agent 開發：** Codex 與 Claude Code 依檔案與資料契約分工，規則見 [AGENTS.md](https://github.com/Polalalabear/amidst/blob/7e1c208b85ffcd2ff12160ed16551e994470e1bc/AGENTS.md)。

### 限制

- 全部結果來自合成場景；目前目標為合成圓柱，尚未以真人或真實影像驗證。
- 全局幾何為 `PARTIAL_APPROVED`，整校通行性 `NOT_CERTIFIED`。
- 原始 `.blend` 保持唯讀；局部幾何核准與人審筆記不自動授予門洞、碰撞或人體淨空權限。

### 開始使用

需要 Python ≥3.12 與 `uv`：

```sh
git clone https://github.com/Polalalabear/amidst.git
cd amidst
uv sync --frozen
```

Clone 只取得程式、設定與文件。完整 Demo 另需對應版本的 Blender 來源資產、渲染影格、保存狀態等本機資產，
Blender 相關流程需 Blender CLI（可用 `BLENDER_BIN` 指定）。目前的 Demo 操作與依賴見[專案狀態](docs/history/STATUS.md)。

### 文件導覽

- [專案狀態與進度](docs/history/STATUS.md)
- [開發規則](docs/DEVELOPMENT_RULES.md)（架構、資產、GT 隔離、攝影機慣例、不確定性）
- [產品需求](docs/specs/PRD.md)、[系統設計](docs/specs/SYSTEM_DESIGN.md)、[資料契約](docs/specs/DATA_SCHEMA.md)
- Office Demo：[計畫](https://github.com/Polalalabear/amidst/blob/7e1c208b85ffcd2ff12160ed16551e994470e1bc/docs/agents/OFFICE_DEMO_PLAN_20261101.md)、[管線地圖](https://github.com/Polalalabear/amidst/blob/7e1c208b85ffcd2ff12160ed16551e994470e1bc/docs/engineering/OFFICE_PIPELINE_MAP.md)、[綠球診斷](https://github.com/Polalalabear/amidst/blob/7e1c208b85ffcd2ff12160ed16551e994470e1bc/docs/engineering/OFFICE_MARKER_DIAGNOSIS_20261016.md)
- **給 AI agent：** 請依 [AGENTS.md](https://github.com/Polalalabear/amidst/blob/7e1c208b85ffcd2ff12160ed16551e994470e1bc/AGENTS.md) 工作；本 README 不重複其規則。

## English

### What it does

Cameras inside a building rarely overlap. When a target leaves one camera and appears in another later, nothing on video
proves what happened in between. Typical systems draw one confident route. Amidst keeps observed, inferred, missing
and unknown evidence apart, and offers physically plausible scenarios with their uncertainty, so an investigator knows
what to trust and which footage to check next.

It is developed and validated in a synthetic Blender campus scene (`school_v3`). It is a research prototype, not a
deployed system.

### Intended use

- Investigators avoid reviewing every video by hand: the system points to the cameras and time windows worth checking.
- Confidence is explicit: intervals without evidence are never drawn as a certain route, and identity is never
  confirmed automatically.

### Core concepts

| Concept | Meaning |
| --- | --- |
| Four evidence states | `PROJECTED_OBSERVATION` (projected from image pixels), `INFERRED_*`, `MISSING` (never filled) and `UNKNOWN`. The workbench draws them differently and never mixes them. |
| Trustworthy uncertainty | A blind interval yields a set of physically plausible paths and per-time possible regions, not one route. Ranking reflects plausibility, not probability. |
| Identity and physical limits | Identity stays `UNCONFIRMED`; walkability, collision and body clearance stay `UNKNOWN` unless authorized evidence says otherwise. |
| Ground Truth isolation | GT is used only for simulation export, evaluation after predictions freeze, and debug views; never for inference, candidate search or ranking. |
| Provenance and fail-closed | Every record is bound to source, run, clock and hash. Mismatches are rejected; missing data disables only that feature and is never substituted. |

### Method and architecture

```text
Observe ──▶ Hypothesize ──▶ Retrieve ──▶ Verify
   │            │              │           │
   │            │              │           └─ no target in retrieved frames → negative evidence prunes hypotheses
   │            │              └─ hypothesis paths × camera visibility → frames that may show the target
   │            └─ physically constrained blind-interval curves: walkable area, speed range, must stay unseen
   └─ per camera: detection → contact point → floor projection (metres)
```

**Implementation status:** observation (single-camera localization), bounded cross-camera candidates and the workbench are implemented. Blind-interval curves, hypothesis-driven retrieval and the negative-evidence loop are in development for 2026-11-01; see [project status](docs/history/STATUS.md).

Six layers: observation sources (Blender scene, calibrated cameras, synthetic RGB) → perception and temporal
understanding (pixel tracks, provisional associations) → spatial and event understanding (plane projection, local
geometry, navigation, bounded candidates) → state and storage (versioned outputs, cases, reviews, receipts) →
retrieval and reasoning (deterministic retrieval, typed tools, Agent orchestration) → application (shared workbench:
source views, synchronized 2D/3D, investigation, replay, review). Each layer is evaluated separately; a pass in one
layer does not widen another layer's approval.

### Research questions

| ID | Question | Metrics |
| --- | --- | --- |
| RQ1 | How accurate is single-camera floor localization, and how do occlusion and grazing views affect it? | Mean/max error (m), coverage, jump count, per-pixel sensitivity |
| RQ2 | Do blind-interval hypotheses cover the true path while staying tight? | Coverage, band width, best-hypothesis distance and rank |
| RQ3 | Does cross-camera association rank the correct continuation first? | Top-1/Top-3 hit rate, MRR, false association rate |
| RQ4 | How much manual review does hypothesis-driven frame retrieval save? | Recall, share of frames to review, query latency |

See [project status](docs/history/STATUS.md) for current results and progress.

### Engineering

- **Reproducible:** versioned outputs, source receipts and deterministic replay with verifiable response hashes.
- **Bounded retrieval:** index lookups instead of scanning images, with a read limit per query.
- **Agent orchestration with deterministic fallback:** the Agent calls only bounded, auditable tools; the system works
  without it, and results do not depend on a model.
- **Multi-agent development:** Codex and Claude Code split work by files and data contracts; see
  [AGENTS.md](https://github.com/Polalalabear/amidst/blob/7e1c208b85ffcd2ff12160ed16551e994470e1bc/AGENTS.md).

### Limits

- All results come from a synthetic scene; the current target is a synthetic cylinder, not yet validated on people or
  real footage.
- Global geometry is `PARTIAL_APPROVED`; whole-school walkability is `NOT_CERTIFIED`.
- The original `.blend` stays read-only; local geometry approval and review notes do not grant portal, collision or
  body-clearance authority.

### Getting started

Requires Python ≥3.12 and `uv`:

```sh
git clone https://github.com/Polalalabear/amidst.git
cd amidst
uv sync --frozen
```

A clone contains code, configuration and documents only. The full demo also needs matching Blender source assets,
rendered frames and saved state on the local machine; Blender workflows need the Blender CLI (`BLENDER_BIN` selects it).
Current demo operations and dependencies are in [project status](docs/history/STATUS.md).

### Documentation

- [Project status and progress](docs/history/STATUS.md)
- [Development rules](docs/DEVELOPMENT_RULES.md) (architecture, assets, GT isolation, camera conventions, uncertainty)
- [PRD](docs/specs/PRD.md), [system design](docs/specs/SYSTEM_DESIGN.md), [data schema](docs/specs/DATA_SCHEMA.md)
- Office demo: [plan](https://github.com/Polalalabear/amidst/blob/7e1c208b85ffcd2ff12160ed16551e994470e1bc/docs/agents/OFFICE_DEMO_PLAN_20261101.md), [pipeline map](https://github.com/Polalalabear/amidst/blob/7e1c208b85ffcd2ff12160ed16551e994470e1bc/docs/engineering/OFFICE_PIPELINE_MAP.md), [marker diagnosis](https://github.com/Polalalabear/amidst/blob/7e1c208b85ffcd2ff12160ed16551e994470e1bc/docs/engineering/OFFICE_MARKER_DIAGNOSIS_20261016.md)
- **For AI agents:** follow [AGENTS.md](https://github.com/Polalalabear/amidst/blob/7e1c208b85ffcd2ff12160ed16551e994470e1bc/AGENTS.md); this README does not repeat its rules.
