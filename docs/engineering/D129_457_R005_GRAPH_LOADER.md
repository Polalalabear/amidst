# D129 / #457：依場景選取的 graph 骨架入口

此交件是 **PROPOSED** 純程式／小型 JSON 入口。`office_expanded_r005` 的覆蓋全部保持 `NOT_EVALUATED`，不是 MANUAL、runtime 推論接線、人工圖覆蓋核准或正式研究驗收。人工覆蓋後續由 #464 確認；本次不消除 r004 的既有 coverage skip。

## 來源與可重用範圍

- #447 exact head：`39b9c4323288cae8c52532277cdd6dc75b63a965`，未合併。
- 只逐檔承接 `configs/q1q5/graphs/office_expanded_r005/preview_v2/region_graph.json`（raw SHA-256 `c61b1ce126d1fcae34f517f0d500d614990aa66ca4770c09e73d797d991ddf50`）及 `camera_graph.json`（`0ed4b6ca74917459d25935915fdfe2c20e274924d89845b08e89db858286d0f9`）的小型安全靜態 topology／calibration／ROI／frame hash 欄位。
- 原方案核定：[留言6634899000](https://github.com/Polalalabear/amidst/issues/418#issuecomment-6634899000)；v2 核定：[留言6636456072](https://github.com/Polalalabear/amidst/issues/418#issuecomment-6636456072)。核定不包含人工圖覆蓋核准。
- #447 已交 4 ROOM、6 camera、5 edge、10 directed transition；本次沿用，沒有另造近似場景。保留其原目錄，僅新增 `search_skeleton/`，避免覆寫未合 PR 已交的 v1/v2 證據。
- 將兩份輸入的 `static-review:` pin 移除；每筆 coverage 改成 `basis: NOT_EVALUATED`、`visibility_ref: null`、`visible_area_m2: null`；獨立 PROPOSED schema literal 與 canonical content pins 重算。其他來源 pin 保留。沒有把 AI 視檢的 MANUAL 當成人類核定。
- `source_pins.json` 固定來源 commit／raw pins／轉換，檔案自身 SHA-256 `01fe6b8a55d04cfafc1178aee1facc4340c7370703b9bb3fe942dcc72cf7ec7e` 固定在 loader。這是對指定來源 bytes 的綁定，沒有重驗 LOCAL blend／PNG。

## 可呼叫入口與邊界

```python
from amidst.q1q5.scene_graphs import load_scene_graphs, location_coverage, room_coverage_pending

graphs = load_scene_graphs('office_expanded_r005', run_scene_id='office_expanded_r005')
result = location_coverage(graphs, ['R101'], run_camera_ids=['CAM_R101_IN'])
assert result == {'hits': {}, 'not_evaluated': [
    {'camera_id': 'CAM_R101_IN', 'reason': 'COVERAGE_BASIS_UNSUPPORTED'}]}
assert room_coverage_pending(graphs) == 'SCENE_ROOM_COVERAGE_PENDING'
```

場景可用 canonical ID 或 `r004`／`r005` 別名；`run_scene_id` 若提供，須使用 canonical ID。未知場景與跨 run scene 明確拒絕。r004 讀原 v3_1 三份固定 raw bytes，仍交原 `load_graphs` 驗證與原 tracking scope；未修改 r004 檔、既有 assertion、skip 或 `graphs.py`。r005 直接驗獨立 skeleton schema，不清空覆蓋／重封後送舊 validator，不回 `GraphBundle`。

r005 載入前驗 manifest pin、逐 graph raw pin、canonical content pin、scene/revision、IDs、edge/path/zone references，以及 DRAFT、UNKNOWN、TOPOLOGICAL_ONLY、空 ranking/physical authority。缺檔、pin 不符、symlink 均 fail closed；不讀 graph ref 指向的路徑。`SceneGraphs` 屬性回 copy。

`location_coverage` 使用 #410 的 `{hits, not_evaluated}` 語意；只有 MANUAL 且存在 run catalog 的覆蓋可命中。r005 所有地點結果都未評估。`visibility_ref` 是既有契約的靜態人工 provenance 鍵，不是 renderer visibility 輸入；guard 僅登錄新檔四個精確 literal occurrence，pattern／scanner 不改。兩個新 schema literal 只登錄 `PROPOSED_LITERAL_ONLY_NOT_ADOPTION`。

#410 exact head `b1a619d0128450f03ace0002d7d1a5347355d02f` 的 core HTTP 實作不在本次 base，沒有接 bootstrap／HTTP／frontend；此處是供其後接用的純程式場景選擇入口。本次沒有 object search、時鐘解析、target observation、推論、影片、Blender、GT、raw dataset 或秘密讀取。

## 重現與實際驗證

使用現有共享 Python environment，勿建立 venv；將 `AMIDST_SHARED_PYTHON` 設為現有環境 executable：

```sh
uv --no-cache run --offline --no-project --python "$AMIDST_SHARED_PYTHON" python -m pytest -o pythonpath=src -o addopts= -q -ra tests/q1q5/test_scene_graphs.py tests/q1q5/test_graphs.py
uv --no-cache run --offline --no-project --python "$AMIDST_SHARED_PYTHON" python scripts/check_architecture_guard.py --base origin/mainline/q1q5
git diff --check
```

本次 focused 結果：**67 passed、1 skipped、0 failed**。唯一 skip 為 `SCENE_ROOM_COVERAGE_PENDING`（r005 等 #464 人工覆蓋），不 skip 缺證據／篡改反例。counterexamples 包含缺 manifest／graph／pin、raw 篡改、symlink、未知 scene、run scene mismatch、重算 content pin 後非法 MANUAL／unknown basis／非空 ref／錯 region、camera、edge／升權／多餘欄位。無 allow guard：authority／inference／schemas 各 **0 findings**。未跑全套、Blender、媒體檢視、Windows、API/runtime、人工／Claude接受或正式研究驗收。
