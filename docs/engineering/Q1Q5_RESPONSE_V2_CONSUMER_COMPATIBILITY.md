# Q1／Q2／Q3 response v1／v2 消費端相容

CQ-23（#303），2026-10-28。#278 的新產品與本項必須成套合入 staging；本文件不核准合併或 AC7。

前端以封閉的 schema_version 對照辨識 Q1／Q2／Q3，支援各自的 v1／v2，未知版本直接拒絕。
v2 額外檢查 time_range_source、requested_time 的 SOURCE／WALL／null 對應、tracking_scope pin 欄與 reasons。
Q1 fixture artifact、錄製重播及 app task dispatch 共用同一對照，Q1／Q2 v2 不再落到 Q3。

Q1／Q3 scorer 保留 #127 `994d34c8340855dbf0e28d0273851049df5e6c7d` 的唯讀 v1 schemas／validator pins；
v2 的四份 JSON schemas 另依 #278 `82798fbd100cdad230ca8eb8469dc51a0b91f842` 的原始 bytes SHA 載入。
mini_schema 的 bytes 相同，refs 仍限制在記憶體 allowlist。缺檔、symlink、SHA 不同或未知版本均拒絕，
沒有把 v2 改名成 v1 再略過新欄位。

正式／synthetic 計分以 `DEFAULT_SELECTED_RUN` 標記排除整段預設；明示整段 SOURCE／WALL 仍可計分。
v1 沒有時間來源欄，不能靠區間剛好等於整段 run 就推定為預設。
Q1／Q3 的排除列保留在 details 與 unscored_default_run_ids，但不進正式、分類、拒絕、literal 或 synthetic 分母。
評估端可在凍結的 case 另附 `expected_time_range_source`；這能讓缺失／無效的預設題預測同樣保持不計分，
也能拒絕預測用 DEFAULT 逃避已標成 EXPLICIT 的題目。此欄屬評估 annotation，不進產品 request／hash。
Q5 保留觀測與腳本核對資訊，預設整段的 event match 為 null，狀態為 NOT_SCORED_DEFAULT_SELECTED_RUN。
conformance 的 PASS 只代表契約檢查，輸入旁另列 scoring_exclusion_reason，不能拿 PASS 當模型分數或 AC7。

staging 原有 conformance 與外部 #127 rc5 是不同版本：CQ-23 分別修兩份，保留各自原有檢查；
staging 的舊 kit 測試不能代替 rc5 測試。#127 的修正以普通 commit 直接追加原分支，v1 schemas／fixtures 不改，
只新增與 #278 同 bytes 的四份 v2 schemas／registry entries。套件必須包含 evaluation/response_versions.py。

## 指定測試與 schema 來源

Q1／Q3 測試的 Q1Q5_KIT_ROOT 是凍結的 994d34c 來源，不能誤指到已改過 schemas 的任意 kit head：

```sh
task_kit_root="$(mktemp -d /private/tmp/q1q5-frozen-schema.XXXXXX)"
git archive 994d34c8340855dbf0e28d0273851049df5e6c7d \
  src/amidst/contracts/q_demo tests/fixtures/q1q5_conformance | tar -x -C "$task_kit_root"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src Q1Q5_KIT_ROOT="$task_kit_root" \
  uv run --no-project --offline --no-cache --python "$EXISTING_PYTHON" python \
  -m pytest -o addopts='' -q -p no:cacheprovider \
  tests/unit/test_q1_query_eval.py tests/unit/test_q3_parse_eval.py \
  tests/unit/test_q5_switch_eval.py tests/unit/test_q1q5_conformance.py
node --test frontend/workbench-v2/q-validate.test.mjs frontend/workbench-v2/q-api.test.mjs
```

合併前驗證須在暫存 code export 先疊入配對 #278 的 contracts/q_demo/__init__.py 與四份 v2 schema；
這是 TEST-ONLY source overlay，不是 Git merge，也不提交覆蓋的檔案。#127 rc5 分支已含自己的完整 registry 與新 v2 檔，
另在該分支來源跑 tests/unit/test_q1q5_conformance.py。兩者結果分開記錄於 PR 的 Actual output。

#127 的新 head 會使固定舊 kit SHA 的重錄工具停在 exact-head gate；必須經複核後在 #300 後續更新 pin。
CQ-15／CQ-23 實際合入 staging 前，不以 v2 重建評測包或重錄 AC7。舊 v1 錄製、manifest 及 scope 原始 bytes 保留。
