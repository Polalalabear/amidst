# Amidst

**在 Blender 合成環境中，以來源證據與物理限制重建跨攝影機盲區的多條軌跡候選。**

**Source-grounded, physically constrained blind-gap trajectory reconstruction in a synthetic Blender environment.**

[繁體中文](#繁體中文) | [English](#english)

> 文件進度快照：**2026-10-14**。`main` 的程式基底是已驗證 R1 demo `439c866`；
> 後續工程與 Phase 1 scoped release 保留在各自分支。下方跨分支文件連結固定到已發布版本，
> 文件中的功能與驗證結果須依該版本範圍解讀。
>
> Documentation snapshot: **2026-10-14**. The code baseline on `main` is the validated R1 demo
> at `439c866`. Later engineering work and the scoped Phase 1 release remain on separate branches;
> their linked documents describe those exact published versions.

## 繁體中文

### 專案定位

Amidst 是合成研究原型。給定來源場景、校正攝影機及部分 2D 觀測，系統以幾何、
導航拓撲與時空限制產生有界 Top-K 軌跡候選，保留替代解、缺失與 `UNKNOWN`。
它不把候選分數當作機率，也不由展示介面確認人物身分、真實路線或整校通行能力。

Ground Truth 僅供模擬匯出、凍結後評估與除錯展示，不能進入 inference、候選搜尋或排名。
來源 RGB、投影位置、推斷橋接與未觀測區段分別保留來源標示。來源 `.blend` 保持唯讀；
局部幾何核准與人審筆記不自動授予門洞、碰撞、人體淨空或全校幾何權限。

### 目前進度與版本入口

| 範圍 | 目前結果 | 文件入口 |
| --- | --- | --- |
| `main` 穩定基底 | R1 demo 與必要 A＋B＋C 依賴已整合；保留原驗證收據，沒有整批併入後續工程與研究分支 | [main 整合範圍](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/engineering/PHASE2_LOCAL_REPAIR_0511.md#main整合判斷) |
| `codex/simulation-engineering` | 最新工作台、Blender 顯示與 Agent R3 工程；Phase 2 功能工作量仍估約 **50%** | [工程進度與負結果](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/engineering/PHASE2_LOCAL_REPAIR_0511.md)、[重現與依賴](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/operations/CURRENT_WORK_REPRODUCTION.md) |
| Phase 1 scoped release | Case 1–3 工作流程 **18/18 Exit gates PASS**，clean checkout 重現完成；Case 3 ADE 改善 **0%**，未達原 ≥30% 研究目標 | [限定驗收](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/PHASE1_CASE23_ACCEPTANCE.md)、[完整報告](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/PHASE1_CASE23_FINAL_REPORT.md) |
| 正式範圍 | 全局幾何仍為 `PARTIAL_APPROVED`，整校 `NOT_CERTIFIED`，Case 4 `DEFERRED`；限定工作流程通過不代表全部研究目標達成 | [Phase 1 重現](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/PHASE1_CASE23_REPRODUCTION.md) |

Agent R2 已完成全部 48 題：常規 **12/40**，中文 7/20、英文 5/20；417 個接受的 literal 欄位
核對錯誤 0，但有 **4 個 DETAIL 完整性誤報**。安全邊界 8/8、乾淨拒絕品質 2/8、澄清完成 0/8，
品質門檻未過。R3 的原工程測試通過，但首次真實模型 demo 失敗；後續 private candidate 未採用，
新 48 題回放尚未開始。工程測試與模型品質分別報告。

凍結研究入口為 `phase2-integration-hardening-frozen-20261006`（`5b51d2c`）；
目前 Phase 1 成果以 `phase1-scoped-case123-20261014`（`043bed2`）保存。
歷史階段另有 `checkpoint/*` tags；tag 只保存 Git 內容，不能恢復未追蹤的 Blender、影片、權重或資料庫。

### 第一版 demo：先在原本機器操作

目前沿用既有工作樹、來源資產與保存狀態。主展示依序為：Office 的來源 RGB／2D–3D 同步、
三個候選與未關聯基線、曲線及既有影片、Classroom 的無投影／缺失、E1 調查與案例保存重開／HTML 報告。
五段核心流程 **5/5** 已完成操作排演；若包含 Saved Agent 加映則為 **5/6**，新 origin 尚未恢復舊 Agent。
此比例描述 demo 操作就緒程度，與 Phase 2 完成度及研究準確率分開。

操作以當次核對的 `DEMO_URL` 為準。歷史 8016 代表工作台角色，最新入口使用動態 port；
不要以舊 URL 或 PID 啟停服務。Saved Agent 需原恢復憑證、PostgreSQL 與本機模型服務；
讀取已保存答案不會新增模型推論，但新 origin 不會自動繼承舊 token。

Office／Classroom 已保存 35 份人審差異，**38 個有效物理 checks 仍為 `UNKNOWN`**；
Auditorium 尚未人審。90 秒展示影片與完整可攜套件尚未交付。
精確操作、既有服務核對與依賴見[第一版 demo 指南](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/engineering/DEMO_V1.md)。

### 六層架構

1. **觀測來源：**Blender 場景、校正攝影機與合成 RGB／2D evidence，保留時鐘與來源。
2. **感知與時間理解：**pixel tracks、暫定關聯及時間範圍，保留漏偵、替代與不確定性。
3. **空間與事件理解：**明確平面投影、核准局部幾何、導航拓撲與有界多候選重建。
4. **狀態與儲存：**版本化輸出、調查、案例、人審及來源收據；目前保存流程具有 SQLite／PostgreSQL 依賴。
5. **檢索與推理：**限定來源與時間的確定性檢索、typed tools 和本機 Agent；事實引用與完成度獨立核對。
6. **應用：**共用工作台的來源展示、調查、回放、人審及報告；product 保留為部分遷移的工程來源。

跨層評估分開記錄 Ground Truth metrics、工程守門、模型品質與失敗原因；某一層 PASS 不提升其他層的核准範圍。

### 安裝與資料邊界

基本環境為 Python ≥3.12 與 `uv`，依 repository lock 安裝：

```sh
git clone https://github.com/Polalalabear/amidst.git
cd amidst
uv sync --frozen
```

此操作取得 Git 追蹤的程式、設定與文件。只 clone 加下載 `.blend` 仍不足以重現目前 demo：
還需要對應版本的 RGB／MP4、checkpoints、SQLite／PostgreSQL 保存狀態及 Agent 權重／設定。
目前優先使用原本機器，不移動上述檔案；跨機器重現須依[依賴盤點](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/operations/CURRENT_WORK_REPRODUCTION.md#3-依賴圖與檔案位置)核對並重新綁定。

Blender-backed 工作需要 Blender CLI 與對應來源資產，可用 `BLENDER_BIN` 指定可執行檔。
目前收據來自 macOS；Windows／Linux 尚無同等完整 demo 與 formal 流程的驗證紀錄。
本 README 更新僅核對文件及引用，未重新執行程式測試、模型或研究流程。

### 文件導覽

- [最新工程文件索引](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/README.md)、[目前交接](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/operations/CODEX_HANDOFF.md)
- [Phase 1 scoped 文件索引](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/README.md)、[Phase 1 交接](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/CODEX_HANDOFF.md)
- main 基底的[產品需求](docs/specs/PRD.md)、[系統設計](docs/specs/SYSTEM_DESIGN.md)、[資料契約](docs/specs/DATA_SCHEMA.md)
- [最新資料盤點](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/data/README.md)

## English

### Purpose and evidence boundaries

Amidst is a synthetic research prototype. Given source geometry, calibrated cameras and partial 2D observations,
it generates bounded Top-K trajectory candidates using geometry, navigation and spatiotemporal constraints.
Alternative hypotheses, missing evidence and `UNKNOWN` remain visible. Candidate scores do not establish probabilities,
identity, a true route or whole-school walkability.

Ground Truth is restricted to simulation/export, evaluation after inference freezes, and debug visualization.
It cannot enter inference, candidate search or ranking. Source RGB, projected positions and inferred bridges retain
separate provenance. The original `.blend` stays immutable; local geometry approval and review notes do not grant
portal, collision, body-clearance or whole-school authority.

### Current progress

| Scope | Published result | Documents |
| --- | --- | --- |
| Stable `main` | Validated R1 demo and required A＋B＋C dependencies, code baseline `439c866`; later engineering and formal research remain separate | [Integration scope](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/engineering/PHASE2_LOCAL_REPAIR_0511.md#main整合判斷) |
| `codex/simulation-engineering` | Latest workbench, Blender presentation and Agent R3 engineering; Phase 2 functional effort remains estimated at **50%** | [Engineering progress](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/engineering/PHASE2_LOCAL_REPAIR_0511.md), [dependencies and reproduction](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/operations/CURRENT_WORK_REPRODUCTION.md) |
| Scoped Phase 1 | Case 1–3 workflow: **18/18 Exit gates PASS**, clean reproduction completed. Case 3 ADE gain is **0%**, below the original ≥30% research target | [Acceptance](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/PHASE1_CASE23_ACCEPTANCE.md), [final report](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/PHASE1_CASE23_FINAL_REPORT.md) |
| Formal boundary | Global geometry is `PARTIAL_APPROVED`, the whole school is `NOT_CERTIFIED`, and Case 4 is `DEFERRED`; workflow acceptance does not mean all research targets passed | [Phase 1 reproduction](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/PHASE1_CASE23_REPRODUCTION.md) |

The full Agent R2 evaluation finished: **12/40** regular tasks (Chinese 7/20, English 5/20), zero literal errors across
417 accepted fields, and **4 DETAIL completeness false claims**. Safety boundaries passed 8/8; clean refusal quality
was 2/8 and clarification completion 0/8. The quality gate was not met. R3 engineering checks passed, but its first
real-model demo failed. The later private candidate has not been applied, and a new 48-task replay has not started.
Engineering checks and model quality remain separate results.

The frozen Phase 2 entry is `phase2-integration-hardening-frozen-20261006` (`5b51d2c`);
the current Phase 1 release is `phase1-scoped-case123-20261014` (`043bed2`). Historical stages have `checkpoint/*` tags.
Tags preserve Git content; untracked Blender assets, videos, model weights and databases need separate retention.

### Demo on the existing local machine

Keep the existing worktrees, source assets and saved state in place. The five core segments cover Office source RGB
and synchronized 2D/3D views; three candidates and an unassociated baseline; curves and existing videos; Classroom
missing projections; and E1 investigation, case save/reopen and HTML reports. All **5/5** core segments were rehearsed.
Including the Saved Agent extra gives **5/6**: the new origin has not recovered the previous Agent state.
This is operational readiness, separate from Phase 2 completion and research accuracy.

Use the verified **`DEMO_URL`** for the current process. Historical 8016 identifies the workbench role; the latest entry
uses a dynamic port. Saved Agent depends on the original recovery credentials, PostgreSQL and the local model service.
Reading a saved answer adds no inference call, but a new origin does not inherit the old token.

Office and Classroom retain 35 review deltas; **38 effective physical checks remain `UNKNOWN`**, and Auditorium has not
been reviewed. The 90-second recording and a complete portable package are still undelivered.
Follow the version-specific [demo guide](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/engineering/DEMO_V1.md) for operations and service checks.

### Six layers

1. **Observation sources:** Blender scenes, calibrated cameras and synthetic RGB/2D evidence with source clocks.
2. **Perception and temporal understanding:** pixel tracks, provisional associations, missed observations and alternatives.
3. **Spatial and event understanding:** explicit-plane projection, approved local geometry, navigation and bounded candidates.
4. **State and storage:** versioned outputs, investigations, cases, reviews and receipts; saved workflows currently depend on SQLite/PostgreSQL.
5. **Retrieval and reasoning:** scoped deterministic retrieval, typed tools and a local Agent, with independent fact and completeness checks.
6. **Application:** a shared workbench for presentation, investigation, playback, review and reports; product remains a partial migration source.

Cross-layer evaluation records Ground Truth metrics, engineering gates, model quality and failure causes separately.
A passing result in one layer does not expand another layer's approval scope.

### Installation and assets

The basic environment requires Python ≥3.12 and `uv`:

```sh
git clone https://github.com/Polalalabear/amidst.git
cd amidst
uv sync --frozen
```

A clone contains tracked code, configuration and documents. A clone plus a `.blend` download is insufficient for the
current demo: matching RGB/MP4, checkpoints, SQLite/PostgreSQL state, model weights and settings are also required.
The current route uses the existing local machine without moving assets. Migration requires the version-specific
[dependency inventory](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/operations/CURRENT_WORK_REPRODUCTION.md#3-依賴圖與檔案位置) and explicit rebinding.

Blender-backed workflows require Blender CLI and matching source assets; use `BLENDER_BIN` to select the executable.
Current receipts come from macOS. Equivalent full demo and formal-workflow validation on Windows/Linux is not yet recorded.
This README refresh checked documents and references only; it did not rerun code tests, models or research workflows.

### Documentation

- [Current engineering index](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/README.md) and [handoff](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/operations/CODEX_HANDOFF.md)
- [Scoped Phase 1 index](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/README.md) and [handoff](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/CODEX_HANDOFF.md)
- main baseline: [PRD](docs/specs/PRD.md), [system design](docs/specs/SYSTEM_DESIGN.md), [data schema](docs/specs/DATA_SCHEMA.md)
- [Current data inventory](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/data/README.md)
