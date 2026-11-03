# FEAT-5：11-03 凍結前 UI-F 整合

依[協調者乾跑分工](https://github.com/Polalalabear/amidst/issues/279#issuecomment-6584089278)，#388 必須隨 FEAT-5 批次第4步進入。以 no-ff `a1482f57cdb2b167af292481ccacadca268a4651` 接 #388@`0051d237f9a96b34a0c2b91742f0bd2621f67a63`，第一parent為原#392@`1ffabe603c5197515c9825f7e40e9ba5a08b1b35`。

唯一衝突是 `src/amidst/q1q5/p1_workbench.py` constructor：#388已包含launcher所需 `ui_root` 與canonical驗證，另有tracking_scope／pin／pins=()與live overlay。保留該完整constructor；合後此檔逐bytes等於#388，不丟replay指定UI root，不另選新scope或參數。沒有手改FEAT-9檔案。

## 驗證

既有Python3.12環境，`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src AMIDST_REQUIRE_IMPL=1`，uv `--no-sync --offline`；不建venv、不重建原包。

- `node --test frontend/workbench-v2/demo-mode-model.test.mjs frontend/workbench-v2/q1-wall-model.test.mjs frontend/workbench-v2/q3-bar-model.test.mjs frontend/workbench-v2/store.test.mjs frontend/workbench-v2/q-api.test.mjs`：65 passed。
- `python -m pytest -o addopts= -q tests/q1q5/test_demo_launcher.py tests/q1q5/test_portable_pack.py tests/q1q5/test_check_demo_rehearsal.py tests/q1q5/test_demo_live_tracking_t.py tests/q1q5/test_api.py tests/q1q5/test_p1_workbench.py tests/q1q5/test_p1_live_tracking.py`：153 passed／4 LOCAL項因未指定包先skip（5.20s）。沿原交付的Shared clean-room定位精確匹配的原包後，明確 `AMIDST_P1_BUNDLE=<LOCAL P1 v4 final clean-room>` 單跑 `test_p1_live_tracking.py`：4 passed（3.61s）。合計157項PASS，未把先前skip寫PASS。
- 原P1 MANIFEST `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`；397 payload／149437452bytes 逐檔SHA與size吻合。測試STATE在repo／包外；不改原clean包。hash-map SHA `2f115b693f76c5d634f20568e68c8507b0c46a0cb36f4e896959cd462a4334b9`。
- 外部守門 #391@`bac745153abcd81a6973ec0a2db9062bc430f69c`，對本head、base `434e57922a24d2422226871c0bb672dc7bc3584b`、無allow：authority／inference／schemas PASS、0findings。
- `git diff --check 434e57922a24d2422226871c0bb672dc7bc3584b HEAD` PASS；P1 adapter逐bytes等於#388。

D113的live A/GAP fail-closed維持；預錄B切鏡另起不帶scope的來源。此整合不等於全部UI／彩排通過。`check_demo_script.py`／完整checklist、`check_demo_rehearsal.py`／#339／U16／U17仍NOT_RUN，等FEAT-9最新文件及實際彩排來源；未以合成案例補正式結果。一般凍結後不再推，僅使用者允許的必要衝突回修例外。
