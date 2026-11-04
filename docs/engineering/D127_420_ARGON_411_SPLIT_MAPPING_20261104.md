# D127 / #420：依 W-C1 判定修 #411 並拆成 Feature PR 映射與交付紀錄

- **任務編號**：[Issue #420](https://github.com/Polalalabear/amidst/issues/420)（W-A2 依 W-C1 判定修 #411 並拆成 feature PR）
- **前置依據**：Codex 在 #412（PR #443，commit `20ea00fbfc0aa927a1fbc73b048d81641ccdd413`）之決策表與修正
- **工作分支**：`argon/420-repair-411-split-pr`（base: `origin/mainline/q1q5`）
- **交付目標**：提供核心搜尋/追蹤（D126 Core Search & Track）之獨立 Feature PR，徹底解決 #411 混包問題，建立 63 檔案逐項拆分映射表，並確保在 `AMIDST_REQUIRE_IMPL=1` 下通過 #410 契約測試（僅允許保留 `SCENE_ROOM_COVERAGE_PENDING`）。

---

## 1. 原 #411 檔案拆分映射總表（63 檔案）

依據 Codex 於 #412 判定之 11 ADOPT、24 REVISE、28 REJECT，將原 #411 涵蓋之 63 個檔案拆分映射至專屬 PR／議題：

| 目標歸屬 / PR | 檔案數 | 處理原則 | 檔案清單摘要 |
| --- | --- | --- | --- |
| **Feature PR #420**（核心搜尋與追蹤） | 21 | ADOPT / REVISE | `configs/architecture/schema_registry_v1.json`, `docs/contracts/Q_CORE_SEARCH_TRACK_V1.md`, `docs/contracts/schemas/q-core.search-track.v1.schema.json`, `frontend/workbench-v2/core-search-track-model.mjs`, `frontend/workbench-v2/core-search-track.test.mjs`, `frontend/workbench-v2/core-search-track-regressions.test.mjs`, `scripts/build_office_synthetic_fixture.py`, `scripts/build_q1q5_detection_index.py`, `scripts/run_cx8_rule_tracking.py`, `src/amidst/q1q5/api.py`, `src/amidst/q1q5/camera_map.py`, `src/amidst/q1q5/candidate_view.py`, `src/amidst/q1q5/core_query.py`, `src/amidst/q1q5/demo_launcher.py`, `src/amidst/q1q5/openai_prediction.py`, `tests/q1q5/fixtures/core_multi_room.synthetic.json`, `tests/q1q5/fixtures/core_single_view_vectors.synthetic.json`, `tests/q1q5/test_core_query_regressions.py`, `tests/q1q5/test_core_search_track_t.py`, `tests/q1q5/test_cx8_tracking_adapter.py`, `tests/q1q5/test_demo_adapter_regressions.py` |
| **PR #440 / #419**（環境檢測與乾淨 Clone 基準） | 4 | 移出 #411，由 #419 / PR #440 獨立收斂 | `scripts/ensure_env.py`, `scripts/verify_clean_clone.py`, `start_all_demo.ps1`, `tests/q1q5/test_cross_platform_scripts.py`（#420 暫留相容實作，正式基準由 #419 交付） |
| **PR #423**（工作台核心畫面接線） | 6 | 移出 #411，由 #423 獨立實作 | `frontend/workbench-v2/search-dialog-model.mjs`, `frontend/workbench-v2/search-dialog-view.mjs`, `frontend/workbench-v2/search-dialog.test.mjs`, `frontend/workbench-v2/search-dialog-model.test.mjs`, `frontend/workbench-v2/search-dialog-view.test.mjs`, `frontend/workbench-v2/tracking-source.mjs` |
| **PR #428**（專案文件全面對齊） | 8 | 移出 #411，由 #428 獨立對齊 | `docs/project/BUILD_FROM_SCRATCH.md`, `docs/project/DECISIONS.md`, `docs/project/GLOSSARY.md`, `docs/project/PRD.md`, `docs/project/README.md`, `docs/project/ROADMAP.md`, `docs/project/SPEC.md`, `docs/project/SYSTEM_ARCH.md` |
| **PR #408 / #413**（事件檢視器與既有 UI） | 22 | REJECT 混入，保留於原 #408 分支由 #413 審查 | `frontend/event-viewer/*` (7 檔), `frontend/workbench-v2/admin.html`, `app.mjs`, `cam-stamp.*`, `clock.mjs`, `event-menu.*`, `index.html`, `monitor-room-model.mjs`, `q-time.*`, `simple-view.*`, `speed-meter.mjs`, `speed.test.mjs`, `style.css`, `start_all_demo.command`, `docs/operations/DEMO_RUNBOOK_20261104.md` |
| **W-C7 #418**（真實場景擴充） | 1 | REJECT 作為真實建檔工具 | `scripts/build_office_expanded_scene.py`（由獨立合成測試資料生成腳本 `scripts/build_office_synthetic_fixture.py` 取代） |
| **交付收據更新** | 1 | 本文件取代 | `docs/engineering/D126_CORE_DELIVERY_RECEIPT_20261104.md`（由本紀錄與拆分映射取代） |

完整機器可讀映射資料見 [`docs/engineering/d127_420_split_mapping_20261104.json`](d127_420_split_mapping_20261104.json)。

---

## 2. 跨平台（Windows）修復細節

在採納 Codex #412 修復成果之基礎上，針對 Windows 平台執行環境補齊必要跨平台防護：
1. **`src/amidst/q1q5/api.py`**：
   - 修正 line 87 與 line 126 中之 `os.O_NOFOLLOW`。Windows 原生未定義此常數，改以 `getattr(os, 'O_NOFOLLOW', 0)` 安全相容。
2. **`tests/q1q5/test_cx8_tracking_adapter.py` 與 `tests/q1q5/test_cross_platform_scripts.py`**：
   - Windows 一般非管理員權限下建立符號連結會拋出 `OSError: [WinError 1314]`，加入 `try...except (NotImplementedError, OSError)` 並在無權限時自動 `pytest.skip`，避免測試在 Windows 平台非預期中斷。

---

## 3. 測試與架構守門驗證結果

### 3.1 Python 核心測試（`AMIDST_REQUIRE_IMPL=1`）
執行指令：
```powershell
$env:AMIDST_REQUIRE_IMPL="1"
python -m pytest -o pythonpath=src -o addopts= -q -ra `
  tests/q1q5/test_core_search_track_t.py `
  tests/q1q5/test_demo_camera_map_t.py `
  tests/q1q5/test_demo_recording_title_t.py `
  tests/q1q5/test_demo_candidate_view_t.py `
  tests/q1q5/test_openai_prediction_t.py `
  tests/q1q5/test_cx8_tracking_adapter.py `
  tests/q1q5/test_cross_platform_scripts.py `
  tests/q1q5/test_core_query_regressions.py `
  tests/q1q5/test_demo_adapter_regressions.py
```
- 結果：**237 passed, 1 failed, 2 skipped in 15.51s**
- 唯一允許失敗項目：`tests/q1q5/test_core_search_track_t.py::test_r004_scene_rooms_have_an_indoor_manual_camera`（`Failed: SCENE_ROOM_COVERAGE_PENDING`，符合契約規定未擴充場景之保留狀態）。
- 略過項目：Windows 符號連結權限略過 2 項。

### 3.2 Node 核心模型與回歸測試
執行指令：
```powershell
node --test frontend/workbench-v2/core-search-track.test.mjs frontend/workbench-v2/core-search-track-regressions.test.mjs
```
- 結果：**28 passed, 0 failed, duration 102.4ms**

### 3.3 架構守門（Architecture Guard）
執行指令：
```powershell
python scripts/check_architecture_guard.py --repo . --base origin/mainline/q1q5
```
- 結果：**PASS（0 findings across authority, inference, and schemas；無 `--allow` 豁免）**

### 3.4 Git 差異格式檢查
執行指令：
```powershell
git diff --check
```
- 結果：**PASS（0 whitespace/formatting errors）**
