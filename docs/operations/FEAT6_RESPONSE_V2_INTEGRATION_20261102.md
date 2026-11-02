# FEAT-6 v2／rc5 整合與唯讀重跑

此分支依 [#373 歸併](https://github.com/Polalalabear/amidst/issues/373#issuecomment-6556605282) 依序以 merge commit 合入 #260 → #278 → #305 → #127 → #277。完整 heads 與 merge commits 在 `FEAT6_RESPONSE_V2_COMPOSITION_20261102.json`；base 是 staging@`434e57922a24d2422226871c0bb672dc7bc3584b`。

**尚未完成整個 FEAT-6。** 前序已通過 feature 的合入、下游 pins 與 golden reports、store 衝突與其重驗、#267 批次合併準備，以及合併後的 AC7 仍依原 gate。此文件不授權合併，不把 conformance 當辨識率或正式接受。

## 來源與衝突解法

- 產品 v2 schema 來源：`src/amidst/contracts/q_demo/schemas/{common,q1-response,q2-response,q3-parse-response}.v2.schema.json@82798fbd100cdad230ca8eb8469dc51a0b91f842`。
- Q1／Q3 計分端的 v1 schema／validator 仍用 `src/amidst/contracts/q_demo@994d34c8340855dbf0e28d0273851049df5e6c7d` 的唯讀來源；不能指到已更新 schema 的 rc5 checkout。v2 schemas 另驗 #278 的原始 bytes pins。這是既有消費端契約，不更改固定 pins。
- kit 的三個衝突檔 `src/amidst/evaluation/q1q5_conformance.py`、`tests/unit/test_q1q5_conformance.py`、`docs/evaluation/Q1Q5_CONFORMANCE_KIT.md` 保留 `e1415f32a778f497bdd048d992440718bf0a9310` 的**精確 bytes**。rc5 已包含 #305 的全部 v2 schema dispatch、time origin 與 report 註記；#305 的 33 個測試函式都已包含在 rc5 的 60 個函式集合。沿用 rc5 的 tracking-scope 斷言與版本，不退回舊 kit。
- #260 的零邊決定語意仍以 `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md@d560f224be0f93cf62076f5ae2fa78b0ae957d15` 及同 ref 的 G4 proposal 為準；沒有修改其圖或 candidate 行為。#260 對舊 kit 文件末尾的補充說明未寫回已釘住的 rc5 文件。
- A15 scorer／test 必須分別為 `97564e401cb7d70a7cc22113a008477b447974536ae207aabc230868e8b6d3dc`／`9b64798bb62f323e1dcf9516ec439419a526e148b59befcde235b87e5c3d0df0`，依 #306 D100(b)／D105 B-22。

## 消費端與合成驗收

先在自己的新暫存目錄匯出**只有 code 與 SYNTHETIC fixtures** 的 994d34c 來源：

```bash
mkdir "$FROZEN_KIT_ROOT"
git archive 994d34c8340855dbf0e28d0273851049df5e6c7d src/amidst/contracts/q_demo tests/fixtures/q1q5_conformance | tar -x -C "$FROZEN_KIT_ROOT"
Q1Q5_KIT_ROOT="$FROZEN_KIT_ROOT" PYTHONPATH=src AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/unit/test_q1_query_eval.py tests/unit/test_q3_parse_eval.py tests/unit/test_q5_switch_eval.py tests/unit/test_q1q5_conformance.py
node --test frontend/workbench-v2/q-validate.test.mjs frontend/workbench-v2/q-api.test.mjs frontend/workbench-v2/store.test.mjs frontend/workbench-v2/review/review-model.test.mjs
PYTHONPATH=src uv run python scripts/check_q1q5_conformance.py --recorded tests/fixtures/q1q5_conformance/SYNTHETIC/valid --params tests/fixtures/q1q5_conformance/SYNTHETIC/valid/parameter_set.json --output "$NEW_REPORT"
```

使用既有 Python 環境，不另建 venv。較早 schema 來源是計分器的固定 code 依賴，不是退回舊 kit 執行 conformance；conformance 使用本分支 rc5。

## 既有凍結錄製的重跑

LOCAL 來源相對 `$AMIDST_ARTIFACTS`：`q1q5-rc5-rerecord-20261027-d92/`。根 MANIFEST bytes SHA-256：`7497ecde3556c3e1edea4e73c91c4e159f5d4d863fc04885b86ab9fb920c544c`。
只讀 `dynamic/recordings/{0..7}`、`linked/recordings/{0..7}`、`runner/recordings/{0..159}`，不讀模型 prompt、private trace、原影片或其他 run。

每份先核對根 MANIFEST 與 HANDOFF 的逐檔 SHA，再執行原生完整命令（沒有 `--only` 或補造 context）：

```bash
PYTHONPATH=src uv run python scripts/check_q1q5_conformance.py --recorded "$RECORDING_DIR" --params "$RECORDING_DIR/parameter_set.json" --output "$NEW_REPORT"
```

其中 `RECORDING_DIR` 是上述單一錄製目錄，`NEW_REPORT` 在自己的全新輸出目錄。結束後重核全部 source pins；確認 report inputs 都綁到 HANDOFF、scope 沒有未列檔案。kit 對 JSONL decisions 的 `filename#N` 是逐列文件表示法，`file_sha256` 仍為原整檔 hash。

GitHub 只存 `docs/history/FEAT6_RC5_CONFORMANCE_REPLAY_20261102.json` 的 curated 摘要：每個原生 report 的 bytes／output hash、exit code、各包計數、HANDOFF pin、1,804 個輸入的 hash-map 摘要與前後不變結果。完整 176 份 checker reports 留 LOCAL。`input_files_sha256` 是相對來源根目錄的 path→SHA map，`json.dumps(sort_keys=True, separators=(",", ":"))` UTF-8 bytes 的 SHA-256，可由固定 HANDOFF／MANIFEST 重建。

這些錄製仍為既有 v1 工程／合成輸出，沒有重錄 v2、跑模型或新增錄製。rc5 report 的 CONTRACT binding 仍指向原先固定的契約 bytes，沒有改為對合入後所有提案的正式認證。supported-classes context 的缺口繼續明列，**AC7=NOT_ACCEPTED**。

## 接續 gates

1. 前序 feature（包含 D109 的 FEAT-9）通過並有固定 heads 後，依指定批次順序以 merge 接上；才刷新 #356／#360／#366／#357 的 pins、golden reports 與相關驗收。
2. #305 與 #243／#255 的 store 測試衝突保留雙方案例，重跑 FEAT-5／FEAT-6 node 命令。
3. #307 尚未完成交付；架構守門不得將 NOT_RUN 或候選腳本的 FAIL 填成 PASS。#374 的 A14 pin gate 由協調者處理。
4. #286／#267 等批次前置與使用者合併授權。#267 的 head 是 staging；本輪不推送 mainline 或 staging，也不自行執行該整合合併。
5. CQ-15／CQ-23 實際合入 staging 後，再依 #300 開獨立回件／重錄與 AC7 驗收；不能由本次 176 份既有 v1 conformance 重跑改判 AC7。
