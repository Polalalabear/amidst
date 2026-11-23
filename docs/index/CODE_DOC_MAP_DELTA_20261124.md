# CODE_DOC_MAP 差異清單（2026-11-24）

Refs #704；Draft #702。這是唯讀增量清單，不修改 `CODE_DOC_MAP.md`、程式、E5或LIVE資料。

## 1. 範圍與來源

- 起點：`git log -1 -- docs/index/CODE_DOC_MAP.md` → `ea31b64396b555a49cc6b9b06ff11f0536c2aa06`，2026-11-22 13:27:26 +08:00。
- 終點：main `d52ce2f0`（完整SHA見下）；support-data只新增文件，沒有新增程式差異。
- 取 `git diff --name-status <起點>..<終點>` 中 `.py`、`.mjs`、`.js`、`.css`、`.html`、`.sh`、`.command` 的新增／修改檔，含測試／量測腳本。配置JSON、lock、workflow及文件不當成程式檔；本區間沒有刪除／改名程式檔。
- 不含未合併的 #623、#690 或其他分支。這不是所有分支的盤點。
- 對應只採現有文件的完整路徑或有詞界的檔名引用；同名檔可能混淆時標UNKNOWN。文件提到程式不代表其內容已涵蓋所有本次改動，也不代表功能驗收。原表只有模組對應時明列索引依據；找不到明確引用則UNKNOWN。
- 文件列只寫區段／檔案，不綁行號。E5／e3_cases／LIVE禁止範圍只取Git檔名及文件引用，未讀取或改寫其程式內容。

終點完整SHA：`d52ce2f0a1a6f774d830f7834f3ac9a598493233`。原表SHA-256：`9cad68b16f86e9db77c0fe18055202952d9aa401be6e0a986cd76b57256aa592`。

## 2. 逐檔差異

| Git | 程式檔 | 對應文件 | 查證方式／缺項 |
|---|---|---|---|
| A | `frontend/live-mode/measure/live_ui_shots.mjs` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| A | `frontend/live-mode/src/coverage.mjs` | [F2_LIVE_COVERAGE_20261122.md](../operations/F2_LIVE_COVERAGE_20261122.md) | 完整程式路徑引用 |
| A | `frontend/live-mode/src/coverage_map.mjs` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| A | `frontend/live-mode/src/coverage_overlay.mjs` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| M | `frontend/live-mode/src/hud.mjs` | [LIVE_MODE_AB_V1.md](../specs/LIVE_MODE_AB_V1.md) | 完整程式路徑引用 |
| M | `frontend/live-mode/src/live.css` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| M | `frontend/live-mode/src/llm_switch.mjs` | [CODE_DOC_MAP.md](../index/CODE_DOC_MAP.md) | 完整程式路徑引用（原表模組對應；未聲稱已涵蓋新變更） |
| M | `frontend/live-mode/src/operator.mjs` | [LIVE_MODE_AB_V1.md](../specs/LIVE_MODE_AB_V1.md) | 完整程式路徑引用 |
| M | `frontend/live-mode/src/system.mjs` | [LIVE_MODE_AB_V1.md](../specs/LIVE_MODE_AB_V1.md) | 完整程式路徑引用 |
| A | `frontend/live-mode/src/ui_state.mjs` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| M | `frontend/live-mode/test/ab_menu.test.mjs` | [BROWSER_HEADLESS_20261118.md](../operations/BROWSER_HEADLESS_20261118.md) | 完整程式路徑引用 |
| A | `frontend/live-mode/test/coverage.test.mjs` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| M | `frontend/live-mode/test/llm_switch.test.mjs` | [LIVE_MODE_LLM_TOGGLE_20261117.md](../operations/LIVE_MODE_LLM_TOGGLE_20261117.md) | 唯一檔名引用 |
| A | `frontend/live-mode/test/operator_view.test.mjs` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| A | `frontend/live-mode/test/ui_state.test.mjs` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| M | `frontend/workbench-v2/admin-ui.mjs` | [LIVE_MODE_LLM_TOGGLE_20261117.md](../operations/LIVE_MODE_LLM_TOGGLE_20261117.md) | 唯一檔名引用 |
| M | `frontend/workbench-v2/app.mjs` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| M | `frontend/workbench-v2/core-search-track-model.mjs` | [EVENT_NAMES.md](../operations/EVENT_NAMES.md) | 完整程式路徑引用 |
| M | `frontend/workbench-v2/live-llm-model.mjs` | [AGENT_API_WIRING_AUDIT_20261120.md](../engineering/AGENT_API_WIRING_AUDIT_20261120.md) | 唯一檔名引用 |
| M | `frontend/workbench-v2/live-llm-model.test.mjs` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| M | `frontend/workbench-v2/q-api.mjs` | [AGENT_API_WIRING_AUDIT_20261120.md](../engineering/AGENT_API_WIRING_AUDIT_20261120.md) | 唯一檔名引用 |
| M | `frontend/workbench-v2/ui-d139.test.mjs` | [D139_CLASS_COUNTS_AND_REVIEW_20261108.md](../operations/D139_CLASS_COUNTS_AND_REVIEW_20261108.md) | 完整程式路徑引用 |
| A | `frontend/workbench-v2/ui-f3.test.mjs` | [CX_H6_8CAM_20261123.md](../operations/CX_H6_8CAM_20261123.md) | 完整程式路徑引用 |
| M | `frontend/workbench-v2/ui-model.mjs` | [D139_CLASS_COUNTS_AND_REVIEW_20261108.md](../operations/D139_CLASS_COUNTS_AND_REVIEW_20261108.md) | 完整程式路徑引用 |
| M | `frontend/workbench-v2/ui-shell.mjs` | [D135_487_MAC_UI_ACCEPTANCE.md](../operations/D135_487_MAC_UI_ACCEPTANCE.md) | 完整程式路徑引用 |
| M | `scripts/design/build_r004_scene_geometry_2d.py` | [R004_A4B4_SCENARIO_CARDS_V2_1_4ACTOR.md](../evaluation/R004_A4B4_SCENARIO_CARDS_V2_1_4ACTOR.md) | 完整程式路徑引用 |
| M | `scripts/e3_recompute_frozen.py` | [E3_PREREGISTRATION_20261122.md](../evaluation/E3_PREREGISTRATION_20261122.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_cases/annotations.mjs` | [E3_CASES_20261122.md](../operations/E3_CASES_20261122.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_cases/baseline.py` | [E3_CASES_20261122.md](../operations/E3_CASES_20261122.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_cases/f1_probe.py` | [E3_CASES_20261122.md](../operations/E3_CASES_20261122.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_cases/finalize.py` | [E3_CASES_20261122.md](../operations/E3_CASES_20261122.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_cases/freeze_reappearances.mjs` | [E3_REAPPEARANCES_20261122.md](../operations/E3_REAPPEARANCES_20261122.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_cases/generate.mjs` | [E3_CASES_20261122.md](../operations/E3_CASES_20261122.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_cases/index.py` | [E3_CASES_20261122.md](../operations/E3_CASES_20261122.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_cases/manifest.py` | [E3_CASES_20261122.md](../operations/E3_CASES_20261122.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_cases/prepare_reappearances.mjs` | [E3_REAPPEARANCES_20261122.md](../operations/E3_REAPPEARANCES_20261122.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_cases/reappearance_events.mjs` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| A | `scripts/evaluation/e3_cases/reappearance_routes.mjs` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| A | `scripts/evaluation/e3_cases/record.mjs` | [E3_CASES_20261122.md](../operations/E3_CASES_20261122.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_cases/release_reappearances.py` | [E3_REAPPEARANCES_20261122.md](../operations/E3_REAPPEARANCES_20261122.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_cases/routes.mjs` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| A | `scripts/evaluation/e3_cases/verify.py` | [E3_CASES_20261122.md](../operations/E3_CASES_20261122.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_f4_gt_spotcheck.py` | [F4_E3_REPORT_658.md](../operations/F4_E3_REPORT_658.md) | 唯一檔名引用 |
| A | `scripts/evaluation/e3_f4_rerun_select.py` | [F4_E3_REPORT_658.md](../operations/F4_E3_REPORT_658.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_f4_run.py` | [F4_E3_REPORT_658.md](../operations/F4_E3_REPORT_658.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e3_f4_score.py` | [F4_E3_REPORT_658.md](../operations/F4_E3_REPORT_658.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e5_run.py` | [E5_AOPEN_INTERFACE_V1.md](../contracts/E5_AOPEN_INTERFACE_V1.md) | 完整程式路徑引用 |
| A | `scripts/evaluation/e5_score.py` | [E5_AOPEN_INTERFACE_V1.md](../contracts/E5_AOPEN_INTERFACE_V1.md) | 完整程式路徑引用 |
| A | `scripts/f2_validate_wall_projection.py` | [F2_LIVE_COVERAGE_20261122.md](../operations/F2_LIVE_COVERAGE_20261122.md) | 完整程式路徑引用 |
| A | `scripts/publication/e3_coverage.py` | [E3_FIGURES_20261123.md](../operations/E3_FIGURES_20261123.md) | 完整程式路徑引用 |
| A | `scripts/publication/e3_figures.py` | [E3_FIGURES_20261123.md](../operations/E3_FIGURES_20261123.md) | 完整程式路徑引用 |
| A | `scripts/publication/verify_e3_figures.py` | [E3_FIGURES_20261123.md](../operations/E3_FIGURES_20261123.md) | 完整程式路徑引用 |
| A | `scripts/qa/cx_h6_8cam_server.py` | [CX_H6_8CAM_20261123.md](../operations/CX_H6_8CAM_20261123.md) | 完整程式路徑引用 |
| M | `scripts/run_w2_agent.py` | [W2_ACTIVE_AGENT_20261120.md](../evaluation/W2_ACTIVE_AGENT_20261120.md) | 完整程式路徑引用 |
| M | `scripts/serve_demo_integration.py` | [AGENT_ZERO_CANDIDATES_629.md](../evaluation/AGENT_ZERO_CANDIDATES_629.md) | 完整程式路徑引用 |
| A | `scripts/verification/f4_independent_recompute.py` | [F4_INDEPENDENT_RECOMPUTE_20261123.md](../evaluation/F4_INDEPENDENT_RECOMPUTE_20261123.md) | 完整程式路徑引用 |
| M | `src/amidst/evaluation/e3_scoring.py` | [E3_PREREGISTRATION_20261122.md](../evaluation/E3_PREREGISTRATION_20261122.md) | 完整程式路徑引用 |
| A | `src/amidst/live_mode/aopen/decider.py` | [E5_AOPEN_INTERFACE_V1.md](../contracts/E5_AOPEN_INTERFACE_V1.md) | 完整程式路徑引用 |
| A | `src/amidst/live_mode/aopen/neutral.py` | [E5_AOPEN_INTERFACE_V1.md](../contracts/E5_AOPEN_INTERFACE_V1.md) | 完整程式路徑引用 |
| M | `src/amidst/live_mode/llm_switch.py` | [LIVE_MODE_LLM_TOGGLE_20261117.md](../operations/LIVE_MODE_LLM_TOGGLE_20261117.md) | 完整程式路徑引用 |
| M | `src/amidst/live_mode/server.py` | [CODE_DOC_MAP.md](../index/CODE_DOC_MAP.md) | 完整程式路徑引用（原表模組對應；未聲稱已涵蓋新變更） |
| A | `src/amidst/live_mode/service_decider.py` | [F3_AGENT_TAKEOVER_657.md](../operations/F3_AGENT_TAKEOVER_657.md) | 完整程式路徑引用 |
| M | `src/amidst/q1q5/camera_projection.py` | [F2_LIVE_COVERAGE_20261122.md](../operations/F2_LIVE_COVERAGE_20261122.md) | 完整程式路徑引用 |
| M | `src/amidst/q1q5/core_query.py` | [Q_CORE_SEARCH_TRACK_V1.md](../contracts/Q_CORE_SEARCH_TRACK_V1.md) | 完整程式路徑引用 |
| M | `src/amidst/q1q5/cross_camera_demo.py` | [AGENT_DECISION_V1.md](../design/AGENT_DECISION_V1.md) | 完整程式路徑引用 |
| M | `src/amidst/q1q5/linker.py` | [CODE_DOC_MAP.md](../index/CODE_DOC_MAP.md) | 完整程式路徑引用（原表模組對應；未聲稱已涵蓋新變更） |
| M | `src/amidst/q1q5/openai_gateway.py` | [CODE_DOC_MAP.md](../index/CODE_DOC_MAP.md) | 完整程式路徑引用（原表模組對應；未聲稱已涵蓋新變更） |
| M | `src/amidst/q1q5/scene_context.py` | [W2_ACTIVE_AGENT_20261120.md](../evaluation/W2_ACTIVE_AGENT_20261120.md) | 完整程式路徑引用 |
| A | `src/amidst/q1q5/service_agent_q5.py` | [F3_AGENT_TAKEOVER_657.md](../operations/F3_AGENT_TAKEOVER_657.md) | 完整程式路徑引用 |
| A | `src/amidst/q1q5/service_agent_track.py` | [F3_AGENT_TAKEOVER_657.md](../operations/F3_AGENT_TAKEOVER_657.md) | 唯一檔名引用 |
| A | `src/amidst/q1q5/service_core_track.py` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| A | `tests/browser/ui-redesign/cx-h6-screens.mjs` | [CX_H6_8CAM_20261123.md](../operations/CX_H6_8CAM_20261123.md) | 完整程式路徑引用 |
| A | `tests/browser/ui-redesign/f3-screens.mjs` | [F3_AGENT_TAKEOVER_657.md](../operations/F3_AGENT_TAKEOVER_657.md) | 完整程式路徑引用 |
| M | `tests/browser/ui-redesign/real-e2e.mjs` | [D135_487_MAC_UI_ACCEPTANCE.md](../operations/D135_487_MAC_UI_ACCEPTANCE.md) | 完整程式路徑引用 |
| A | `tests/evaluation/e3_reappearance_events.test.mjs` | [E3_REAPPEARANCES_20261122.md](../operations/E3_REAPPEARANCES_20261122.md) | 完整程式路徑引用 |
| A | `tests/evaluation/test_e3_cases.py` | [E3_CASES_20261122.md](../operations/E3_CASES_20261122.md) | 完整程式路徑引用 |
| A | `tests/evaluation/test_e3_f4_a3.py` | [F4_E3_REPORT_658.md](../operations/F4_E3_REPORT_658.md) | 完整程式路徑引用 |
| A | `tests/evaluation/test_e3_f4_score.py` | [F4_E3_REPORT_658.md](../operations/F4_E3_REPORT_658.md) | 完整程式路徑引用 |
| A | `tests/evaluation/test_e3_reappearances.py` | [E3_REAPPEARANCES_20261122.md](../operations/E3_REAPPEARANCES_20261122.md) | 完整程式路徑引用 |
| M | `tests/evaluation/test_e3_scoring.py` | [E3_PREREGISTRATION_20261122.md](../evaluation/E3_PREREGISTRATION_20261122.md) | 完整程式路徑引用 |
| A | `tests/evaluation/test_e5_run.py` | [E5_AOPEN_INTERFACE_V1.md](../contracts/E5_AOPEN_INTERFACE_V1.md) | 完整程式路徑引用 |
| A | `tests/evaluation/test_e5_score.py` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| A | `tests/evaluation/test_f4_independent_recompute.py` | [F4_INDEPENDENT_RECOMPUTE_20261123.md](../evaluation/F4_INDEPENDENT_RECOMPUTE_20261123.md) | 完整程式路徑引用 |
| A | `tests/live_mode/test_aopen_decider.py` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| A | `tests/live_mode/test_aopen_neutral.py` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| M | `tests/live_mode/test_llm_switch.py` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| A | `tests/live_mode/test_service_decider.py` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| A | `tests/q1q5/test_service_agent_q5.py` | UNKNOWN | UNKNOWN：未找到可唯一對應的現行文件引用 |
| A | `tests/q1q5/test_service_agent_track.py` | [Q_CORE_SEARCH_TRACK_V1.md](../contracts/Q_CORE_SEARCH_TRACK_V1.md) | 完整程式路徑引用 |
| A | `tests/q1q5/test_service_core_track.py` | [CX_H6_8CAM_20261123.md](../operations/CX_H6_8CAM_20261123.md) | 完整程式路徑引用 |
| A | `tests/q1q5/test_wall_coverage.py` | [F2_LIVE_COVERAGE_20261122.md](../operations/F2_LIVE_COVERAGE_20261122.md) | 完整程式路徑引用 |

## 3. 盤點收據

共91檔：A=59，M=32；UNKNOWN=20。此數字只計清單列數，不是測試或研究結果。

`git diff --name-status ea31b64396b555a49cc6b9b06ff11f0536c2aa06..d52ce2f0` 與清單逐項核對，缺漏0、重複0；所有已列文件連結存在。`git diff --check`通過。未執行程式測試，因為本項只新增文件，未變更任何程式。

LOCAL查證快照（各1檔，按同命令及文件字串搜尋可重建；來源與對應綁在上述Git區間）：

- `local/evidence/codex-w-20261124/c3/changed-paths.json`，8179 bytes，SHA-256 `3062db52b5953345e1027ac8b2c6b19d450f81df4853d74dbdb66513624aac31`。
- `local/evidence/codex-w-20261124/c3/mapping-final.json`，16192 bytes，SHA-256 `0c6a9111bb77220d39bad1cb8fded6c84a5f12fb4fc665cb27e8b604c63d7040`。
