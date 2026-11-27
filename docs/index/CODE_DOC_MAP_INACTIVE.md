# 程式碼 ↔ 文件對應表（非現行）

- 2026-11-27（D408）從 [`CODE_DOC_MAP.md`](CODE_DOC_MAP.md) 原樣搬出 §3、§4，內容未改；現行對應（§1 主規格章節、§2 LIVE 模組）留在原檔。章節編號沿用原檔。
- 規則同原檔：只記區段，不記行號；這是索引，不是規範。

## 3. 其他套件（摘自 SWEEP §1；細節與 UNKNOWN 見該紀錄）

| 程式 | 文件 | 狀態 |
| --- | --- | --- |
| `src/amidst/workbench/`（Python，與退役 UI 無關） | `docs/engineering/SHARED_WORKBENCH.md`、`BLENDER_*.md` | 模組層級無文件 |
| `src/amidst/agent_eval/`、`agent_eval_scoring/` | `docs/contracts/AGENT_EVAL_TOOLCHAIN_GATES_V1.md` | |
| `src/amidst/local_agent/` | `docs/engineering/AGENT_RETRIEVAL_BOUNDARY.md`（契約 pin，不可改） | `manager.py` 只在 Office 稽核文件出現 |
| `src/amidst/finalization/` | `docs/engineering/FINALIZATION_DECOUPLING_PLAN_20261020.md` | 重複與否 `UNKNOWN` |
| 頂層 `physical_*.py`、`obstacle_volume_authority.py` | `docs/engineering/BLENDER_PHYSICAL_CANDIDATE_FILTER.md` | |
| `src/amidst/geometry/`、`geometry_authority.py`、`scene_geometry.py` | `docs/specs/GEOMETRY_AUTHORITY.md`、`SCENE_VALIDATION.md` | |
| `scene_validation.py`、`scene_validation_blender.py` | `docs/specs/SCENE_VALIDATION.md` | 有來源 pin |
| `src/amidst/benchmark/`、`benchmark_report.py` | `docs/research/PHASE1_BENCHMARK_PROTOCOL.md` | |
| `src/amidst/evaluation/` | `docs/engineering/Q1Q5_BASELINE_V1_PROTOCOL.md` | |
| `src/amidst/engineering/` | `docs/engineering/` 多份回執 | `api.py`、`research_scene.py`、`synthetic.py` 無文件 |
| `src/amidst/product/` | `docs/engineering/DEMO_V1.md` | |
| `src/amidst/integration/` | `docs/engineering/PHASE2_INTEGRATION.md` | 主規格未提及 |
| `src/amidst/research_accuracy/` | `docs/research/` | |
| `src/amidst/simulation/`、`visualization/` | `docs/engineering/SIMULATION_ENGINEERING.md` | |
| `src/amidst/phase2_research/` | `docs/engineering/PHASE2_LOCAL_REPAIR_0511.md` | |
| 頂層 `pipeline.py` | 無文件（主規格 U-11） | 動態匯入 `UNKNOWN` |
| `datasets/`、`domain/`、`storage/` 等 | `docs/specs/DATA_SCHEMA.md`、`INTERFACES.md`（已封存） | |

## 4. D319 第一輪檢索項目的處理結果（D338）

| SWEEP 項目 | 處理 |
| --- | --- |
| §1.1 規格無 LIVE、§4.2 無 operator／system、§4.3 無預錄 Agent 開關、難題集無敘述 | 規格新增 §4.4 LIVE，§4.2、§4.3 補 Agent 開關與 3D 視圖；「難題集」正式名稱為 #597「LIVE 難題集」 |
| §1.1 §1.3／P-5／U-14 的 3D 敘述 | 規格 §1.3 改寫（3D 重建暫停，3D 顯示已存在）；U-14 部分釐清，對應標籤仍 `UNKNOWN` |
| §1.1 §5.1 vs `UI_REDESIGN_V1.md` 的 8／7 台 | 查設定檔：catalog／查找 8 台，追蹤圖 7 台（CAM_ENTRY 只供查找，D74）；規格 §5.1 與 `UI_REDESIGN_V1.md` 都加註 |
| §1.1 §6 決策索引只到 D92 | 規格新增 §6.1（D107–D338 選錄，原文依 #93） |
| §1.1、§4.2 頂部 staging 敘述 | 規格頂部改為 `main`（D200）；契約版本依 pin 表說明；`Q1Q5_PROGRESS.md`「分類方式」加註（authority pin 另登記） |
| §1.1 U-13 | 關閉：DEVELOPMENT_RULES 已寫 workbench-v2 為主入口（D268） |
| （另）U-1 | 關閉：`main` 的契約已寫 v2 schema 名稱 |
| §2.2 `CURRENT_WORK_REPRODUCTION.md` §7.3 | 已封存，檔頭加註現行指令 |
| §2.2 `OFFICE_DEMO_TASKS.md` | 已封存，檔頭標「放棄」 |
| §2.2 `OFFICE_DEMO_MVP.md`、`OFFICE_DEMO_SCRIPT.md`、`SYSTEM_DESIGN.md`、`ISSUES_AND_DECISIONS.md` | 已封存，檔頭加 D268 註記 |
| §2.2 `OFFICE_DEMO_LAUNCHER.md` | 檔頭原本已有 D268 下線註記，不動 |
| §2.2 `WORKBENCH_V2_Q1Q5_DESIGN.md` §2.1 | 表格列加註來源檔已移除 |
| §2.3 LIVE 樣式（本次補記） | 對應工作 1（#633／PR #634），不在本 PR 改程式 |
| §4.1 `docs/engineering/LIVE_MODE_SPIKE_20261115.md` | 檔頭標「已被取代」；歸檔仍待使用者決定 |
| §4.1 `R004_A4B4_SCENARIO_CARDS_V1.md` | 有 authority pin 且仍被引用，**不動**，仍為歸檔候選 |
| §4.1 `N6_LIVE_ASSETS_20261115.md`、`LIVE_MODE_HANDOFF_20261116.md` | 仍 `UNKNOWN`（未逐份比對），本次不動 |
| §4.2 `DEMO_RUNBOOK_20261104.md` 埠號 | 檔頭加過時說明與現行 8785／8791 |
| §4.3 索引缺口（LIVE 文件） | 本表 §1、§2 已收錄 LIVE 相關文件 |
| §3.1、§2.1 可刪候選（5 支 `*_r004_*` 腳本、`core-screens-demo.html`） | **只標記，不刪**；刪除需使用者授權 |
| §2.1、§5 冗餘與可模組化 | 屬程式整併，不在本 PR；之後另開工作 |
