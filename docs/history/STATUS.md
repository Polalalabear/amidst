# 專案狀態與進度快照 / Project status

[繁體中文](#繁體中文) | [English](#english)

此頁保存原 README 的進度內容（2026-10-14 快照，含 2026-10-16 追加），於 2026-10-16 自 README 移出，內容未改寫。README 改為專案說明；之後的進度更新寫在此頁。

The progress content previously in the README (2026-10-14 snapshot plus the 2026-10-16 addition) moved here unchanged on 2026-10-16. The README now describes the project; future progress updates go on this page.

> 文件進度快照：**2026-10-14**。`main` 的程式基底是已驗證 R1 demo `439c866`；
> 後續工程與 Phase 1 scoped release 保留在各自分支。下方跨分支文件連結固定到已發布版本，
> 文件中的功能與驗證結果須依該版本範圍解讀。
>
> 2026-10-16 追加：Office 可驗證 demo 的計畫、診斷與分工已發布於 `claude/office-demo-visualization`（`f5e49b3`），見下方「Office 可驗證 demo」。
>
> Documentation snapshot: **2026-10-14**. The code baseline on `main` is the validated R1 demo
> at `439c866`. Later engineering work and the scoped Phase 1 release remain on separate branches;
> their linked documents describe those exact published versions.
>
> 2026-10-16 addition: the Office verifiable-demo plan, diagnosis and task split are published on
> `claude/office-demo-visualization` (`f5e49b3`); see "Office verifiable demo" below.

## 繁體中文

### 目前進度與版本入口

| 範圍 | 目前結果 | 文件入口 |
| --- | --- | --- |
| `main` 穩定基底 | R1 demo 與必要 A＋B＋C 依賴已整合；保留原驗證收據，沒有整批併入後續工程與研究分支 | [main 整合範圍](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/engineering/PHASE2_LOCAL_REPAIR_0511.md#main整合判斷) |
| `codex/simulation-engineering` | 最新工作台、Blender 顯示與 Agent R3 工程；Phase 2 功能工作量仍估約 **50%** | [工程進度與負結果](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/engineering/PHASE2_LOCAL_REPAIR_0511.md)、[重現與依賴](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/operations/CURRENT_WORK_REPRODUCTION.md) |
| Phase 1 scoped release | Case 1–3 工作流程 **18/18 Exit gates PASS**，clean checkout 重現完成；Case 3 ADE 改善 **0%**，未達原 ≥30% 研究目標 | [限定驗收](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/PHASE1_CASE23_ACCEPTANCE.md)、[完整報告](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/PHASE1_CASE23_FINAL_REPORT.md) |
| `claude/office-demo-visualization`（Office 可驗證 demo） | 2026-10-16：綠球跳動原因確認為椅背遮擋＋斜視角；底部可見驗證 run 接地誤差平均 0.155→0.097 m（合成）；目標 2026-11-01 報告 | [計畫](https://github.com/Polalalabear/amidst/blob/f5e49b35da16e9e384dd46a24c53c975317308ae/docs/agents/OFFICE_DEMO_PLAN_20261101.md)、[診斷](https://github.com/Polalalabear/amidst/blob/f5e49b35da16e9e384dd46a24c53c975317308ae/docs/engineering/OFFICE_MARKER_DIAGNOSIS_20261016.md)、[管線地圖](https://github.com/Polalalabear/amidst/blob/f5e49b35da16e9e384dd46a24c53c975317308ae/docs/engineering/OFFICE_PIPELINE_MAP.md) |
| 正式範圍 | 全局幾何仍為 `PARTIAL_APPROVED`，整校 `NOT_CERTIFIED`，Case 4 `DEFERRED`；限定工作流程通過不代表全部研究目標達成 | [Phase 1 重現](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/PHASE1_CASE23_REPRODUCTION.md) |

Agent R2 已完成全部 48 題：常規 **12/40**，中文 7/20、英文 5/20；417 個接受的 literal 欄位
核對錯誤 0，但有 **4 個 DETAIL 完整性誤報**。安全邊界 8/8、乾淨拒絕品質 2/8、澄清完成 0/8，
品質門檻未過。R3 的原工程測試通過，但首次真實模型 demo 失敗；後續 private candidate 未採用，
新 48 題回放尚未開始。工程測試與模型品質分別報告。

凍結研究入口為 `phase2-integration-hardening-frozen-20261006`（`5b51d2c`）；
目前 Phase 1 成果以 `phase1-scoped-case123-20261014`（`043bed2`）保存。
歷史階段另有 `checkpoint/*` tags；tag 只保存 Git 內容，不能恢復未追蹤的 Blender、影片、權重或資料庫。

### Office 可驗證 demo（目標 2026-11-01）

目標：選定一筆觀測，跨兩台不同位置的攝影機穿過盲區，並在工作台清楚區分觀測、推論、缺失與未知。
研究題目為「多鏡頭、視野不重疊條件下，對選定目標的跨盲區位置推測與不確定性量化」；身分維持 `UNCONFIRMED`，目標目前是合成圓柱。

- **已確認：** Office 綠球在 0.4→0.6、1.8→2.0 秒的跳動來自圓柱底部被椅背遮住、視線入射角僅約 0.16–0.19；REAR 前段無偵測是路線刻意設計的盲區。
- **已量測（合成驗證）：** 底部可見路線上，perception v2 接地誤差平均 0.155→0.097 m、最大 0.356→0.133 m，0 個速度上限跳點；代價是 Office 原 31 點在 v2 下全部被拒絕。
- **下一步：** 混合接地估計器（腳點或頭頂射線區間）、盲區物理推測曲線、依假設檢索可能畫面與負證據收斂；以 RQ1–RQ4 量化（誤差、涵蓋率／帶寬、Top-K 命中率、檢索召回與延遲）。功能凍結 10/29。
- **分工：** Codex 負責 Blender、感知與估計器、後端整合、檢索索引與 Agent 編排；Claude Code 負責盲區假設演算法模組、評估工具、工作台視覺化與 Demo 模式、驗收與文件。

詳見[計畫](https://github.com/Polalalabear/amidst/blob/f5e49b35da16e9e384dd46a24c53c975317308ae/docs/agents/OFFICE_DEMO_PLAN_20261101.md)、[綠球診斷](https://github.com/Polalalabear/amidst/blob/f5e49b35da16e9e384dd46a24c53c975317308ae/docs/engineering/OFFICE_MARKER_DIAGNOSIS_20261016.md)、[管線地圖](https://github.com/Polalalabear/amidst/blob/f5e49b35da16e9e384dd46a24c53c975317308ae/docs/engineering/OFFICE_PIPELINE_MAP.md)與[分工規則](https://github.com/Polalalabear/amidst/blob/f5e49b35da16e9e384dd46a24c53c975317308ae/AGENTS.md)。此段僅整理文件與既有結果，未重新執行程式或研究流程。

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

## English

### Current progress

| Scope | Published result | Documents |
| --- | --- | --- |
| Stable `main` | Validated R1 demo and required A＋B＋C dependencies, code baseline `439c866`; later engineering and formal research remain separate | [Integration scope](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/engineering/PHASE2_LOCAL_REPAIR_0511.md#main整合判斷) |
| `codex/simulation-engineering` | Latest workbench, Blender presentation and Agent R3 engineering; Phase 2 functional effort remains estimated at **50%** | [Engineering progress](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/engineering/PHASE2_LOCAL_REPAIR_0511.md), [dependencies and reproduction](https://github.com/Polalalabear/amidst/blob/59ca2502575b5e284bab8037d768cac53cd3655c/docs/operations/CURRENT_WORK_REPRODUCTION.md) |
| Scoped Phase 1 | Case 1–3 workflow: **18/18 Exit gates PASS**, clean reproduction completed. Case 3 ADE gain is **0%**, below the original ≥30% research target | [Acceptance](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/PHASE1_CASE23_ACCEPTANCE.md), [final report](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/PHASE1_CASE23_FINAL_REPORT.md) |
| `claude/office-demo-visualization` (Office verifiable demo) | 2026-10-16: marker jumps traced to chair-back occlusion plus grazing view; on a bottom-visible control run the contact error fell from 0.155 to 0.097 m mean (synthetic); report due 2026-11-01 | [Plan](https://github.com/Polalalabear/amidst/blob/f5e49b35da16e9e384dd46a24c53c975317308ae/docs/agents/OFFICE_DEMO_PLAN_20261101.md), [diagnosis](https://github.com/Polalalabear/amidst/blob/f5e49b35da16e9e384dd46a24c53c975317308ae/docs/engineering/OFFICE_MARKER_DIAGNOSIS_20261016.md), [pipeline map](https://github.com/Polalalabear/amidst/blob/f5e49b35da16e9e384dd46a24c53c975317308ae/docs/engineering/OFFICE_PIPELINE_MAP.md) |
| Formal boundary | Global geometry is `PARTIAL_APPROVED`, the whole school is `NOT_CERTIFIED`, and Case 4 is `DEFERRED`; workflow acceptance does not mean all research targets passed | [Phase 1 reproduction](https://github.com/Polalalabear/amidst/blob/b55b57a3c323a7fa30a881fb5ab843f47c24fdb9/docs/PHASE1_CASE23_REPRODUCTION.md) |

The full Agent R2 evaluation finished: **12/40** regular tasks (Chinese 7/20, English 5/20), zero literal errors across
417 accepted fields, and **4 DETAIL completeness false claims**. Safety boundaries passed 8/8; clean refusal quality
was 2/8 and clarification completion 0/8. The quality gate was not met. R3 engineering checks passed, but its first
real-model demo failed. The later private candidate has not been applied, and a new 48-task replay has not started.
Engineering checks and model quality remain separate results.

The frozen Phase 2 entry is `phase2-integration-hardening-frozen-20261006` (`5b51d2c`);
the current Phase 1 release is `phase1-scoped-case123-20261014` (`043bed2`). Historical stages have `checkpoint/*` tags.
Tags preserve Git content; untracked Blender assets, videos, model weights and databases need separate retention.

### Office verifiable demo (target 2026-11-01)

Goal: select one observation, follow its evidence across two separated cameras through a blind interval, and keep
observed, inferred, missing and unknown states distinct in the workbench. The research question is cross-blind-interval
position inference and uncertainty quantification for a selected target with non-overlapping cameras. Identity stays
`UNCONFIRMED`, and the current target is a synthetic cylinder.

- **Confirmed:** the Office marker jumps at 0.4→0.6 s and 1.8→2.0 s come from chair backs hiding the cylinder's base at a
  grazing incidence of about 0.16–0.19. REAR's early silence is the route's intended blind interval.
- **Measured (synthetic):** on a bottom-visible route, perception v2 reduced contact error from 0.155 to 0.097 m mean and
  from 0.356 to 0.133 m max, with no speed-cap jumps. In exchange, all 31 original Office positions are rejected by v2.
- **Next:** a hybrid contact estimator (foot point or head-ray interval), physically constrained blind-interval hypotheses,
  retrieval of possibly relevant frames and negative-evidence pruning, measured by RQ1–RQ4 (error, coverage/band width,
  Top-K hit rate, retrieval recall and latency). Feature freeze is 10/29.
- **Task split:** Codex owns Blender, perception and estimators, backend integration, the retrieval index and Agent
  orchestration. Claude Code owns the hypothesis algorithm module, evaluation tooling, workbench visualization and demo
  mode, acceptance and documentation.

See the [plan](https://github.com/Polalalabear/amidst/blob/f5e49b35da16e9e384dd46a24c53c975317308ae/docs/agents/OFFICE_DEMO_PLAN_20261101.md), [marker diagnosis](https://github.com/Polalalabear/amidst/blob/f5e49b35da16e9e384dd46a24c53c975317308ae/docs/engineering/OFFICE_MARKER_DIAGNOSIS_20261016.md), [pipeline map](https://github.com/Polalalabear/amidst/blob/f5e49b35da16e9e384dd46a24c53c975317308ae/docs/engineering/OFFICE_PIPELINE_MAP.md) and [task rules](https://github.com/Polalalabear/amidst/blob/f5e49b35da16e9e384dd46a24c53c975317308ae/AGENTS.md). This section summarizes
documents and existing results only; no code or research workflow was rerun.

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
