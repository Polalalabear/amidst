# FEAT-6 v2／rc5 整合與唯讀重跑

此分支依 [#373 歸併](https://github.com/Polalalabear/amidst/issues/373#issuecomment-6556605282) 依序以 merge commit 合入 #260 → #278 → #305 → #127 → #277。完整 heads 與 merge commits 在 `FEAT6_RESPONSE_V2_COMPOSITION_20261102.json`；base 是 staging@`434e57922a24d2422226871c0bb672dc7bc3584b`。

**尚未完成整個 FEAT-6。** 前序已通過 feature 的合入、下游 pins 與 golden reports、store 衝突與其重驗、#267 批次合併準備，以及合併後的 AC7 仍依原 gate。此文件不授權合併，不把 conformance 當辨識率或正式接受。

## 來源與衝突解法

- 產品 v2 schema 來源：`src/amidst/contracts/q_demo/schemas/{common,q1-response,q2-response,q3-parse-response}.v2.schema.json@82798fbd100cdad230ca8eb8469dc51a0b91f842`。
- Q1／Q3 計分端的 v1 schema／validator 仍用 `src/amidst/contracts/q_demo@994d34c8340855dbf0e28d0273851049df5e6c7d` 的唯讀來源；不能指到已更新 schema 的 rc5 checkout。v2 schemas 另驗 #278 的原始 bytes pins。這是既有消費端契約，不更改固定 pins。
- kit 的三個衝突檔 `src/amidst/evaluation/q1q5_conformance.py`、`tests/unit/test_q1q5_conformance.py`、`docs/evaluation/Q1Q5_CONFORMANCE_KIT.md` 保留 `e1415f32a778f497bdd048d992440718bf0a9310` 的**精確 bytes**。rc5 已包含 #305 的全部 v2 schema dispatch、time origin 與 report 註記；#305 的 33 個測試函式都已包含在 rc5 的 60 個函式集合。沿用 rc5 的 tracking-scope 斷言與版本，不退回舊 kit。
- #277 的 merge `3c5bf6661b5305e5fc91d6e5808182bc6831ff8a` 另有兩個手動組合檔：`scripts/rerecord_q1q5_rc3.py` 的 `validate_recording()` 合併 q1／q3-parse／q2 的 v1、v2 schema dispatch，未知 schema 以 `FRESH_RESPONSE_SCHEMA_REQUIRED` 拒絕；`tests/q1q5/test_rc3_rerecord.py` 保留兩版 query／session 的 scope-pin 正反例。這兩檔不是任一子 PR 的精確 bytes 副本；沒有新增 schema 或改 scope-pin 語意，已隨原分段測試通過。
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

**批次 gate 必須保留上述 `Q1Q5_KIT_ROOT="$FROZEN_KIT_ROOT"`**，其中來源精確為994d34c匯出；未設變數會找不到來源，指到rc5會因固定pin不符被拒，兩者都不是可忽略的setup error。

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
3. #307 已以 #391@`1f0a710f12b90f37e74e10e8faa744ff167314a5` 交付，D112 A14 gate已處理；用固定腳本／policy對當前head重跑。#260/#278/#305/#127 指定變更的七個authority路徑可依 #373 歸併明列 `--allow`，仍必須通過bytes pin，不沿用前一head的PASS。
4. #286／#267 等批次前置與使用者合併授權。#267 的 head 是 staging；本輪不推送 mainline 或 staging，也不自行執行該整合合併。
5. CQ-15／CQ-23 實際合入 staging 後，再依 #300 開獨立回件／重錄與 AC7 驗收；不能由本次 176 份既有 v1 conformance 重跑改判 AC7。


## D114-3：CQ-16 註記確認（2026-11-03）

#260@d560f22 在舊 kit 末尾的「CQ-16 零邊候選排除與原kit相容」說明未出現在 rc5，是依 D105 B-20 **刻意保留 #127@e1415f3 三檔精確 bytes 的整檔衝突解法**，不是撤回零邊規則；本文件「來源與衝突解法」原已揭露這項取捨。kit 文件 SHA 仍為 `9645b26e6c04f8245c05a632f584242ff79cc48ae98c287c19ff230cab7e42c0`，沒有為補註改動 A14。

該註記的有效內容仍在 #260 的契約與程式：有未核准 scope 先回 `GRAPH_NOT_APPROVED`；零邊原宣告 `TOPOLOGICAL_ONLY` 回 `TOPOLOGICAL_ONLY_EDGE`，其餘零邊回 `SAME_REGION_TRANSITION_NOT_APPROVED`；非零拓撲路徑仍為 `TOPOLOGICAL_ONLY_EDGE`。`GraphBundle.transition_authorities` 不改 frozen graph，零邊一律 effective UNKNOWN，不進候選。對應原測試為 `tests/q1q5/test_empty_path_authority.py`，本輪重跑，並非移除規則或擴大 G4 authority。這份確認保留在交付文件，固定 kit 原檔不重寫。

## 11-03 乾跑衝突修復

依 [Claude 乾跑](https://github.com/Polalalabear/amidst/issues/279#issuecomment-6584023284)，在本分支以 no-ff 接 #392 固定 head `1ffabe603c5197515c9825f7e40e9ba5a08b1b35`。唯一衝突是 `frontend/workbench-v2/store.test.mjs` 末尾 add/add：完整保留單畫面 auto-switch 預設案例及 v1/v2 Q1/Q2/Q3 store 與拒絕異類 action 的全部斷言。`store.mjs` 自動合併同時保留 single 預設及 `responseKind` 的 v1/v2 dispatch。kit 三檔無衝突、精確 rc5 bytes 不變；沒有手改 FEAT-9 檔案。

FEAT-9 UI-10 固定交付與交叉審查、#388→#392 的交接／是否進批次仍由各擁有者與協調者處理，不能用本次 store 衝突修復代替。D114-3 已把 FEAT-4 移到 demo 後，FEAT-6 的 11-03 前置不再包含 FEAT-4。


### 此輪驗證與守門交接

- 四份原指定 Node 檔：73 passed，保留 single 預設與完整 v1/v2 拒絕斷言。
- 原指定 Python 四份：453 passed（21.20s，固定 994d34c code/fixture export）；初次受限 sandbox 是450 passed／3個loopback bind PermissionError，再以允許本機loopback環境全數通過，沒有改測試。
- 原零邊focused：23 passed（0.23s）；rc5 SYNTHETIC conformance：711 PASS／0 FAIL。三份kit檔逐bytes與e1415f3相同。
- 對 FEAT-9 UI-10固定head d141b1d87f9d231b9cd5bb06554d89fa124bd1a4 跑 `git merge-tree --write-tree --name-only` 無衝突；這是靜態合併檢查，未合FEAT-9、未取代其D104交叉審查。
- 固定 FEAT-7@bac7451（D114-4 P1已重釘）的外部guard，沿#373原指定七個 `--allow` 路徑為三項PASS、0findings；pin逐一全驗。依[協調者乾跑修正分工](https://github.com/Polalalabear/amidst/issues/279#issuecomment-6584089278)，七路徑需由FEAT-7擁有者登錄精確已授權變更，組合樹不帶CLI allow的守門仍待整批重跑；不能將此命令當整批無條件PASS。

七路徑與原固定授權來源：#260@d560f22的 `docs/contracts/Q1Q5_D86_G4_RECEIPT_PROPOSAL_20261027.md`、`docs/contracts/Q1_Q2_FIRST_DEMO_V1.md`；#278@82798fb的 `docs/contracts/Q1Q5_RESPONSE_V2_D92_20261027.md`；#127@e1415f3的 `docs/evaluation/Q1Q5_CONFORMANCE_KIT.md`、`src/amidst/evaluation/q1q5_conformance.py`；#305@f22e9da的 `src/amidst/evaluation/q5_switch_eval.py`、`tests/unit/test_q5_switch_eval.py`（#306 D100-2／D105 B-22）。本次未更動這七檔bytes，也未在非擁有者分支擴守門policy。


## 最後接入 FEAT-5 凍結 head

FEAT-5 的必修 UI-F 已交並凍結於 `3f81637b1e9fb15f08c26cd10c3faec8d815ab0c`。本分支在凍結前以 no-ff `ba06759546e6565756bc9111c3b2f2e747f4b4cb` 接上；`api.py`／`q-api.mjs` 都由ort乾淨合併，保留v2 dispatch及scope/session preimage，沒有新增手動解法。

以原固定994d34c code/fixtures、明確選定原P1包、既有Python3.12與 `AMIDST_REQUIRE_IMPL=1` 同程序跑原四份unit plus `test_demo_live_tracking_t.py`／`test_api.py`／`test_p1_live_tracking.py`：530 passed（25.57s），0skip。四份Node原命令73 passed；rc5 SYNTHETIC kit711 PASS／0FAIL。固定F7@f637596＋原七allow，三項0 findings PASS；七變更的無allow精確登錄仍由F7擁有者完成，組合樹需Claude再乾跑，不將局部命令當整批放行。

對UI-10 #385@d141的merge-tree仍CLEAN（tree `a9cfabcc4649e2d23ccbac5fc80e0025c59c0455`）。此檢查不取代#385未接#384最新D113腳本的NEEDS_CHANGES；該項已另交Claude，Codex不手改FEAT-9檔。

一般凍結後不再推；只有使用者已允許的必要衝突修復例外。完整前序／U18／使用者批次merge與AC7仍依各gate，不開新實驗或正式錄製。
