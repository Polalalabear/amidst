# 程式碼 ↔ 文件對應表

- 建立：2026-11-19（D338，issue [#631](https://github.com/Polalalabear/amidst/issues/631)）。來源：[`SWEEP_D319_PASS1_20261119.md`](SWEEP_D319_PASS1_20261119.md)（D319 第一輪檢索，`main` `b98fac2a` 核對）＋本次以 `main` `be4c4262` 的 `ls`／`git ls-files` 補 LIVE、workbench-v2 與 Agent 開關。
- 用途：寫論文、研究紀錄或更新規格時，從模組找到對應的規格／契約／文件章節，或反過來。
- 規則照本資料夾 [README](README.md)：只記區段（模組、檔案、文件章節），不記行號。「文件」欄有多份時，第一份是主要依據。查不到的寫 `無文件`；沒查證的寫 `UNKNOWN（原因）`。
- 這是索引，不是規範；與規格或契約不一致時以規格、契約為準。

## 1. 主規格章節 ↔ 程式

| 主規格 [`Q1Q5_PRODUCT_SPEC.md`](../specs/Q1Q5_PRODUCT_SPEC.md) | 契約／專屬規格 | 主要程式 |
| --- | --- | --- |
| §1.1 Q1 依條件找相機 | `Q1_Q2_FIRST_DEMO_V1.md` §6；`Q_CORE_SEARCH_TRACK_V1.md` | `src/amidst/q1q5/core_query.py`、`detection_index.py`；`frontend/workbench-v2/core-search-track-model.mjs`、`search-dialog-model.mjs` |
| §1.1 Q2 找人／追蹤、Q5 切鏡 | 契約 §8（§8.1–§8.7）；`Q5_DECISION_WINDOW_D79.md` | `src/amidst/q1q5/linker.py`、`q5_controller.py`、`q5_agent.py`；`frontend/workbench-v2/q-playback.mjs`、`track-map-model.mjs` |
| §1.1 Q3 語意解析 | 契約 §7；`NL_QUERY_PARSE_V1.md` | `src/amidst/q1q5/nl_query_parse.py`；`frontend/workbench-v2/nl-spotlight.css` 與 Spotlight 相關 `.mjs` |
| §1.1 Q4 畫面是否含目標 | 契約 §8.3 | `src/amidst/q1q5/detection_index.py`（RT-DETR＋HSV 索引） |
| §2 兩層圖、候選排序 | 契約 §5；`configs/q1q5/graphs/r004/*_v3*.json` | `src/amidst/q1q5/graphs.py`、`attention_ranking.py`（DP4，`DP4_ATTENTION_RANKING_V1.md`） |
| §3 schema | 契約 §2–§11；`configs/architecture/schema_registry_v1.json` | `src/amidst/q1q5/store.py` 等；`frontend/workbench-v2/q-validate.mjs` |
| §4.1 後端 API | `Q_DEMO_API_BOOTSTRAP_V1.md`；規格 U-12（action 介面文件 `UNKNOWN`） | `src/amidst/q1q5/api.py`、`p1_workbench.py`；`scripts/serve_demo_integration.py`；`start_445_demo.command` |
| §4.2 workbench-v2 | `UI_REDESIGN_V1.md`（§12 為準）、`WORKBENCH_V2_Q1Q5_DESIGN.md`、`DEMO_UI_SUPPORT_V1.md` | `frontend/workbench-v2/`（`app.mjs`、`ui-shell.mjs`、`ui-model.mjs`、`ui.css`、`monitor-room-model.mjs`、`live-entry.mjs`） |
| §4.2 8CAM run | `docs/operations/WORKBENCH_8CAM_D302_20261118.md`、`R004_EIGHT_CAMERA_DELIVERY_20261114.md` | `scripts/demo_eightcam.py`、`scripts/check_demo_dependencies.py` |
| §4.2 俯視圖 2D／3D | D316；#613 | `frontend/workbench-v2/topdown-model.mjs`、`scene3d-model.mjs`、`scene3d-view.mjs`；`est_xy` 來源 #612（PR #623，未合併） |
| §4.3 Agent 與 fallback | 契約 §8.4；`AGENT_DECISION_V1.md`；`EPIC_D_AGENTIC_V1.md` | `src/amidst/q1q5/agent_decision.py`、`agent_tools.py`、`agent_wiring.py`、`agent_providers.py`、`agent_recording.py` |
| §4.3 主動 Agent 決策器（W2 #645） | `docs/evaluation/W2_ACTIVE_AGENT_20261120.md`；`AGENT_VS_RULE_HYPOTHESES_20261120.md` §4.1、§4.3；`docs/engineering/AGENT_API_WIRING_AUDIT_20261120.md` §6 | `src/amidst/q1q5/agent_service.py`、`scene_context.py`、`camera_projection.py`（標定 → 地面覆蓋多邊形，#648 從 `evaluation/live_coverage_gap.py` 搬出，後者重新匯出）；`scripts/run_w2_agent.py`；`tests/q1q5/test_agent_service.py`（8785 開關改接為第二步，`waiting:codex`） |
| §4.3 付費護欄（`ApiGuard`）與接線 | `docs/engineering/AGENT_API_WIRING_AUDIT_20261120.md`；AGENTS.md（#537、D339）；規格 §4.3、U-18 | `src/amidst/q1q5/api_budget.py`（`ApiGuard`、帳本 `AMIDST_API_USAGE_DIR`）；G7 已修正：所有付費呼叫經 ApiGuard（4f665d55）：`scripts/agent_decision/run_provider.py`、`src/amidst/q1q5/openai_prediction.py`（`OpenAIPredictionAdapter`）每次嘗試都經 `ApiGuard.run`（#655；`docs/operations/PAID_API_G7_20261120.md`） |
| 假設 H1–H6 評估（W1、先導、W2） | `docs/evaluation/AGENT_VS_RULE_HYPOTHESES_20261120.md` §0；`W1_FRAME_EVAL_20261120.md`（預先登記 `W1_FRAME_EVAL_PREREG_20261120.md`）；`VISION_AGENT_RECORDED_20261120.md`；`W2_ACTIVE_AGENT_20261120.md` | `src/amidst/evaluation/frame_eval.py`、`vision_agent.py`、`gt_scoring_r004.py`（GT 只在評分端）；`scripts/run_frame_eval.py`、`frame_eval_score.py`、`run_vision_agent.py`、`vision_agent_report.py`、`run_w2_agent.py`、`capture_agent_payloads.py`；`tests/evaluation/test_frame_eval.py`、`test_vision_agent.py`、`tests/q1q5/test_capture_agent_payloads.py` |
| E3 統一評分器與預先登記（F1 #660） | `docs/evaluation/E3_PREREGISTRATION_20261122.md`；`E3_SCORER_RECOMPUTE_20261122.md`（凍結結果重算對照） | `src/amidst/evaluation/e3_scoring.py`（純函式；GT 由評分端傳入）；`scripts/e3_recompute_frozen.py`（不花 API，重算 D325／先導／W1／W2）；`tests/evaluation/test_e3_scoring.py`（含推論端不 import `amidst.evaluation`） |
| E3 劇本與重現點錄製（#652、#663、#665） | `docs/operations/E3_CASES_20261122.md`、`E3_REAPPEARANCES_20261122.md` | `scripts/evaluation/e3_cases/`；`tests/evaluation/test_e3_cases.py`、`test_e3_reappearances.py` |
| E3 各組執行、評分與獨立重算（F4 #658、#683） | `docs/operations/F4_E3_REPORT_658.md`；`docs/evaluation/F4_INDEPENDENT_RECOMPUTE_20261123.md` | `scripts/evaluation/e3_f4_run.py`、`e3_f4_score.py`、`e3_f4_rerun_select.py`、`e3_f4_gt_spotcheck.py`；`scripts/verification/f4_independent_recompute.py` |
| F2 牆面裁切鏡頭覆蓋（#656、#664） | `docs/operations/F2_LIVE_COVERAGE_20261122.md` | `src/amidst/q1q5/camera_projection.py`、`scripts/f2_validate_wall_projection.py`；`frontend/live-mode/src/coverage.mjs`（`coverage_map.mjs`、`coverage_overlay.mjs` 的對應文件 `UNKNOWN`） |
| F3 Agent 接管 8785／LIVE（#657、#666、#686） | `docs/operations/F3_AGENT_TAKEOVER_657.md`；`CX_H6_8CAM_20261123.md` | `src/amidst/q1q5/service_agent_q5.py`、`service_agent_track.py`、`service_core_track.py`；`src/amidst/live_mode/service_decider.py` |
| E5 完全開放 Agent（#684、#685、#694） | `docs/evaluation/E5_PREREGISTRATION_20261123.md`；契約 `docs/contracts/E5_AOPEN_INTERFACE_V1.md`；報告 `docs/operations/E5_REPORT_20261123.md`；`E5_NUMBERS_TABLE_20261124.md` | `src/amidst/live_mode/aopen/decider.py`、`neutral.py`；`scripts/evaluation/e5_run.py`、`e5_score.py`；`tests/live_mode/test_aopen_*.py`、`tests/evaluation/test_e5_*.py` |
| E6 去錨定、上下文、R-N（D377，**尚無程式**） | `docs/evaluation/E6_PLAN_20261124.md`、`DESIGN_QA_20261124.md`；預登由 #718 交 | 待 #717、#721 |
| ApiGuard 快取計價（#699、#701） | `docs/operations/APIGUARD_CACHE_20261124.md` | `src/amidst/q1q5/api_budget.py` |
| §4.3 預錄 Agent 開關（OpenAI） | `docs/operations/RECORDED_AGENT_OPENAI.md`；D306、D313 | `src/amidst/q1q5/openai_gateway.py`、`api_budget.py`、`scene_graphs.py`；`frontend/workbench-v2/shell-view.mjs`；`start_agent_gateway.command`（#625 修正 scope 與 B-05 不適用；候選 0 見 #629） |
| §4.3 規則 vs LLM（預錄） | `docs/evaluation/RECORDED_RULE_VS_LLM_D325_20261118.md` | 分析結果在 LOCAL（見該文件） |
| §4.4 LIVE 即時模式 | `LIVE_MODE_AB_V1.md`（v2.1）、`LIVE_MODE_GAME_DESIGN_V2.md`、`LIVE_MODE_LLM_DECISION_V1.md` | 前端 `frontend/live-mode/src/`；後端 `src/amidst/live_mode/`；`start_live_mode.command`（8791） |
| §4.4 重新取得 R1 | `LIVE_MODE_RELOCK_V1.md`；`docs/engineering/LIVE_MODE_RELOCK_R1_20261118.md` | `src/amidst/live_mode/relock.py`、`tracker.py`（R1 由 PR #608 合併 `cfbfe4e9`；`RelockConfig` 門檻預設 `None`＝關閉，`t_short_s`、`tau_app`、`margin_app` 為 `UNKNOWN`） |
| §4.4 錄製重播 | `docs/operations/LIVE_AB_RECORDING_20261118.md`、`LIVE_AB_HANDOFF_20261118.md` | `frontend/live-mode/src/recording.mjs`（PR #617 合併 `1742ed06`；固定步長 0.05 s，輸入側確定性） |
| §4.4 難題集 | `docs/evaluation/LIVE_HARDSET_V1.md`、`LIVE_HARDSET_COMPARE_V1.md`；`configs/evaluation/live_hardset_v1.json` | `frontend/live-mode/src/script_operator.mjs`、`hardset_routes.mjs`；`scripts/live_hardset_compare.py`、`live_hardset_dryrun.py`；`scripts/live_ab_score.py` |
| §5 Line 1／Line 2、評分 | `Q5_DECISION_WINDOW_D79.md`、`Q5_SWITCH_EVAL_V1.md`、`R004_A4B4_SCENARIO_CARDS_V1.md` | `src/amidst/evaluation/q5_switch_eval.py`、`q5_script_adapter.py`、`q1q5_conformance.py` |

## 2. LIVE 模組（2026-11-19 補）

| 程式 | 文件 | 備註 |
| --- | --- | --- |
| `frontend/live-mode/src/operator.mjs`、`sim.mjs`、`crowd.mjs`、`person.mjs`、`world.mjs`、`view.mjs`、`setup.mjs` | `LIVE_MODE_AB_V1.md` §1–§3（A 端、腳本人物、不碰撞） | `world.mjs` 的 `groundTruthVisible` 只供評估 |
| `frontend/live-mode/src/system.mjs`、`system_grid.mjs`、`hud.mjs` | `LIVE_MODE_AB_V1.md` §4–§5（B 端、A↔B 協定）；`LIVE_MODE_HANDOFF_20261116.md` §13（HUD） | 系統端不收操作者 ID／座標（D210） |
| `frontend/live-mode/src/protocol.mjs` | `LIVE_MODE_AB_V1.md` §5 | 白名單與禁止鍵 |
| `frontend/live-mode/src/llm_switch.mjs`；`src/amidst/live_mode/llm_switch.py`、`advisor.py` | `LIVE_MODE_LLM_DECISION_V1.md`；`docs/operations/LIVE_MODE_LLM_TOGGLE_20261117.md` | #563 |
| `frontend/live-mode/src/n6.mjs`、`n6-ceiling.mjs`、`exterior.mjs` | `docs/operations/N6_LIVE_ASSETS_20261115.md`、`N6_CEILING_D302_20261118.md` | N6 glTF 資產在 LOCAL |
| `frontend/live-mode/src/capture.mjs`、`capture-plan.mjs`、`sweep.mjs` | `docs/evaluation/LIVE_MODE_SPIKE_20261115.md`、`LIVE_DETECTION_20261117.md` | 偵測量測 |
| `frontend/live-mode/index.html`（內嵌 `<style>`） | `UI_REDESIGN_V1.md`（只涵蓋 workbench-v2） | 樣式 token 複製自 `workbench-v2/ui.css`（SWEEP §2.3），工作 1 處理（#633／PR #634） |
| `src/amidst/live_mode/server.py` | `LIVE_MODE_AB_V1.md` §5.3–§5.4（`/reset`、`session_id`、`reselect`） | 8791 |
| `src/amidst/live_mode/tracker.py`、`candidates.py`、`people.py`、`color.py` | `LIVE_MODE_RELOCK_V1.md`；`LIVE_MODE_TRACKER_20261116.md`、`LIVE_MODE_PEOPLE_GROUPING_20261117.md` | 關聯 4 m（D244） |
| `src/amidst/live_mode/detector.py`、`scheduler.py` | `LIVE_SCHEDULE_20261117.md`、`LIVE_DETECTION_SCHEDULE_D273_20261118.md` | |
| LIVE Agent 接線與重新取得 R2 證據（#675、#676、#703） | `docs/operations/LIVE_AGENT_675_20261123.md`、`LIVE_AGENT_OFFLINE_20261124.md`、`LIVE_COLOR_GATE_676_20261123.md`、`LIVE_COLOR_GATE_EVIDENCE_20261124.md`、`LIVE_RELOCK_R2_PLAN_20261124.md`；契約 `docs/contracts/LIVE_TRACK_FIELDS_20261124.md` | 8791 未部署 |
| LIVE 共用樣式（#633、#705） | `docs/operations/LIVE_SHARED_STYLE_633_20261124.md` | |
| `src/amidst/live_mode/track_sentence.py` | `NL_QUERY_PARSE_V1.md`（B 句子接 Q3，D279） | |
| `frontend/live-mode/test/`、`tests/operations/test_live_launcher.py`、`tests/evaluation/test_live_ab_score.py` | `LIVE_AB_HANDOFF_20261118.md`（測試指令） | |

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
