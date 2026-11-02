# FEAT-1 程式與文件整合段

依 [#376 歸併](https://github.com/Polalalabear/amidst/issues/376#issuecomment-6556603824) 依序 no-ff 合入 #294、#256、#275、#295、#254、#354、#353、#355、#356、#357，再接上已交付的 #391 守門。逐項 head、merge commit、原始內容 hash、驗收及未跑 gate 在同名 JSON 收據。

## 凍結與 gate

[D105-1](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6556609083) 已核准 U4，精確綁 #354@48133c1 的凍結 JSON `ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb`。本樹未修改它或它列出的 13 個參照；#295 producer JSON 也保留原 bytes。候選檔的 `PENDING_USER`／`production_ready=false` 是被核准的歷史格式，不原地改成 APPROVED；當前人類核准記錄在 D105-1。

#348 選定副本留在原 PR，不合進本分支。固定 head hash 覆核 PASS 不代表 G4 已生效，仍需使用者 checkpoint 引用與 #93 D 決策（D101-2 第 4～5 步）。本次不渲染、不做正式索引、不重錄或啟動模型；資料段依賴與 NOT_RUN 在收據逐項列明。U18 分段批次接受仍待協調者處理。

## D105 B-12

`check_event_run_bundle.py` 在 case-fold 前先拆 camelCase、縮寫與英數交界，再用非英數字元切 token（含底線）。private 詞在 token 開頭即拒絕，另處理 `trajectories`／`visibilities` 複數、獨立 `gt` 與相鄰的 `ground truth`。因此 `actorId`／`depthMap`／`gt3d`、`depthmap.png`／`scripts.json` 仍拒絕；`description`／`factory` 內嵌的 substring 不誤殺，良性 token 也不會豁免後續 private token（如 `factoryDepth`）。其他 private 路徑、hash、symlink、SYNTHETIC-only fail-closed 與核准邊界不變。

此為 [#394 P1 回修](https://github.com/Polalalabear/amidst/pull/394#issuecomment-6574836115)：新增 19 個整包測試案例，修改前 17 個 private 反例失敗、2 個良性正例通過；修改後 strict focused 282 passed，另固定 kit QT-25 52 passed。原 263／52 結果保留在 JSON 歷史欄位，本次結果另列 `review_p1_verification`。未修改被凍結 bytes 或權威契約。

## 可重跑命令

使用 repo 既有 Python 3.12 環境，不安裝依賴。先在全新 LOCAL 目錄匯出固定 kit 的程式與合約檔；下列輸出皆非正式資料包：

```bash
# KIT_EXPORT 必須是新目錄；在此整合樹根目錄執行。
mkdir "$KIT_EXPORT"
git archive e1415f32a778f497bdd048d992440718bf0a9310 \
  src/amidst/__init__.py src/amidst/contracts \
  src/amidst/evaluation/q1q5_conformance.py \
  src/amidst/evaluation/response_versions.py | tar -x -C "$KIT_EXPORT"
# reader 採目前整合樹，只有合約與 conformance 相依來自固定 kit。
ln -s "$PWD/src/amidst/q1q5" "$KIT_EXPORT/src/amidst/q1q5"
AMIDST_REQUIRE_IMPL=1 AMIDST_INDEX_KIT_ROOT="$KIT_EXPORT" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$KIT_EXPORT/src:$PWD/src" \
  uv run --no-sync --offline python -m pytest -q \
  tests/q1q5/test_check_detection_index_receipt.py
```

QT-25 的 52 項要單獨執行。`checked_kit` 仍逐一驗七檔 pin，並核對實際 import 的來源。只有設定 KIT_ROOT 但仍從目前樹 import q_demo 會被拒絕；只在母程序改 package path 也不足，因 CLI 子程序需要相同的 PYTHONPATH。沒有修改 checker／測試／pin 去繞過這項保護。

其餘 strict focused：

```bash
AMIDST_REQUIRE_IMPL=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  uv run --no-sync --offline python -m pytest -q \
  tests/evaluation/test_r004_script_freeze.py tests/unit/test_q5_script_adapter.py \
  tests/q1q5/test_check_event_run_bundle.py tests/q1q5/test_check_baseline_freeze.py \
  tests/evaluation/test_p2_baseline_report.py tests/unit/test_architecture_guard.py
uv run --no-sync --offline python scripts/check_r004_script_freeze.py \
  --freeze docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json \
  --expected-freeze-sha256 ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb
python3 scripts/check_architecture_guard.py --base origin/codex/q1q5-staging \
  --allow configs/q1q5/graphs/r004/camera_graph_v3_1.json \
  --allow configs/q1q5/graphs/r004/region_graph_v3_1.json \
  --allow src/amidst/evaluation/q5_script_adapter.py --report /tmp/feat1-guard.json
git diff --check 434e57922a24d2422226871c0bb672dc7bc3584b HEAD
```

三個 `--allow` 只對應歸併指定 #294／#254 的精確 bytes；仍逐檔驗 #306 pin，不核准 graph authority。五個新 schema literal 的登記都指向原交付 head，只是 inventory，不採納 PROPOSED schema。

`check_p2_report.py` 的 v1 scorer pin 先保持 `0fd1ef68…`，依 D105 由 FEAT-6 在 #305 接入後更新 pin 與 golden，本分支不改。
