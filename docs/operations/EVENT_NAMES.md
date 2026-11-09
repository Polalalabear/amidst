# 事件短名稱對照（展示模式）

展示模式開啟時（D139，前台預設開、後台「前台展示模式」開關），前台與後台只顯示短名稱；關閉時照舊顯示 bootstrap 的完整標題。對照表在 `frontend/workbench-v2/event-names.mjs`，**用 run_id（錄製用 recording_id）對**，不比對標題字串；bootstrap 的 `title` 不改（`tests/browser/core-preview/real-e2e.mjs` 用 `title.startsWith(label+' ')` 找 run）。查不到的 id 顯示「事件 N」（N＝清單順序），不顯示原始 id 或標題。

## 短名稱

| 短名稱 | 顯示 | run_id / recording_id | 描述出處 |
| --- | --- | --- | --- |
| B-05 | B-05 · 8 秒工程場景 | `ENGINEERING_DYNAMIC_RUN_20261025`（P1 v4 包，LOCAL：`/Users/Shared/amidst-p1-clean-room-20261026/Amidst P1 最終測試/data/registry/catalog.json`） | 同包 `README.txt`：「8秒／20fps工程場景」；標題 `scripts/serve_demo_integration.py:149` |
| A4-1 | A4-1 · 室外→入口→走廊 | `ctrl-lcorr-s1-a4-5fps-v1-r004-d124-v1` | `docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md` §2「A4（室外 → 入口 → 走廊）」；run_id 見 `tests/q1q5/test_d149_scene_annotation.py:22`、`docs/engineering/R004_D124_RERENDER_RECEIPT.md` |
| B4-1 | B4-1 · 走廊→轉角→R101 | `ctrl-lcorr-s1-b4-5fps-v1-r004-d124-v1` | 同上 §3「B4（走廊 → 轉角 → R101）」；run_id 見 `frontend/workbench-v2/ui-d147.test.mjs` 與 `R004_D124_RERENDER_RECEIPT.md` |
| r005 | r005 · 六張靜態圖 | `r005-static-reviewed-v2` | `scripts/serve_demo_integration.py:196,231`（標題「六張靜態圖」） |
| B-05（預錄切鏡） | B-05 · 預錄切鏡 | recording `2777741d96ac9aff5bffb2f61a4d2938` | `frontend/workbench-v2/event-menu.mjs`（`B05B_RECORDING_ID`、B-05b「預錄切鏡」） |
| B-05 / A4-1 / B4-1（測試替身） | 只有短名稱 | `SYNTHETIC_B05` / `SYNTHETIC_A4_1` / `SYNTHETIC_B4_1` | `tests/browser/core-preview/preview-server.mjs:37`（合成預覽伺服器，非真實事件） |

## 編號每一段的意思

- **B-05**：`B-` 是 demo 步驟編號（B-01 開啟監控牆、B-02 檢索彈窗、B-03 查找、B-05 追蹤；a＝live、b＝預錄），見 `docs/agents/Q1Q5_DEMO_SCRIPT.md` 的「步驟與 #346 編號對照」。把它當作 P1 v4 事件的名稱是 repo／GitHub 慣用說法（`docs/specs/UI_REDESIGN_V1.md:31`「事件或場景選擇（B-05、A4-1、B4-1、r005）」）。`05` 的事件對應關係（為何 P1 run 叫 B-05）：除上述慣用說法外 **UNKNOWN**（沒有文件明說）。
- **A4-1 / B4-1**：`A4`、`B4` 是情境卡編號（A4＝室外→入口→走廊；B4＝走廊→轉角→R101）；`-1` 是方案 1（A4-1 50 s、B4-1 42 s；D89 核定、D92 調整）。出處 `docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md` §0、§2、§3。
- **r004**（出現在 run_id）：場景 revision 欄位 `scene_revision`／graph `r004`（`scripts/serve_demo_integration.py:91`）；數字 004 的由來 **UNKNOWN**。
- **r005**：`office_expanded_r005`，獨立程序建模的 Office 示範場景（四間教室 R101～R104），`docs/engineering/D127_418_OFFICE_EXPANSION_PARAMETERS.md:7`；`r005` 為 scene revision。

## 展示模式下隱藏的完整標題各段

完整標題例：`A4-1 · D124 · ACTUAL_BLENDER · 自動種子`（`scripts/serve_demo_integration.py:174`）。

- `D124`：重新渲染的 run 家族（`scripts/check_event_run_bundle.py:55`、`docs/engineering/R004_D124_RERENDER_RECEIPT.md`）。
- `ACTUAL_BLENDER`：`source_kind`（Blender 實際渲染來源，`qrun(..., source_kind)`）。
- `自動種子`：追蹤起點由系統自動選取（`frontend/workbench-v2/core-search-track-model.mjs:751` `AUTO_SEED_LABEL`；`docs/operations/DEMO_SCRIPT_ACCEPTANCE_V1.md` D137）。
- `SYNTHETIC`、`P1 v4`：資料來源與素材包版本（`docs/operations/DEMO_RUNBOOK_20261104.md`）。

## 顯示位置

前台：case3 事件按鈕、事件說明列、標頭來源下拉；後台：播放頁與紀錄頁的項目欄、「目前」選定事件。其他位置若新增事件名稱，請用 `eventDisplayName(run, {present, index})`。
