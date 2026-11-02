# CQ-36-T（#331）評分端；與推論隔離

這些都是 **SYNTHETIC_ONLY** controls，不是凍結批准、正式收據、已採用的報告 wire 或正式分數。沒有 Blender、影片、GT、formal／clean 包 bytes。#330 的工程核心現由真實 v2 scorer 驗證；正式凍結輸入與 production report wire 仍未選定。

## 兩層驗證

1. `scripts/check_l2_report.py` 的 `CQ36_SYNTHETIC_PROJECTION_V1` 只重算已釘住的合成 scored rows 的分類與彙總。必須明示 `--synthetic-profile CQ36_SYNTHETIC_PROJECTION_V1`；省略時在讀檔前 `PRODUCTION_PROFILE_UNSELECTED`。它不呼叫v2 scorer，輸出明列 `native_scorer_executed=false`、`formal_acceptance=NOT_EVALUATED`。
2. required-implementation 測試透過 `l2_complex_test_driver` 呼叫真實 `l2_complex_report.score_sessions`，再逐場呼叫 v2 scorer。driver 只做 path／pin／欄名綁定，不解析 scored rows 或 golden report 作為分數。缺實作時 strict 仍 fail。

## 輸入與手算

`inputs.SYNTHETIC.json` 是測試收據投影，逐檔綁定 synthetic script/response/journal/scored rows 與 `native_inputs.SYNTHETIC.json`；後者再綁8組獨立session的 v2 script、v1 response、decision-record journal、參數、計畫fixture。native fixtures 由 #360@685a5a69949566ca4b00db9033ebb556c95df64b 的合成控制改作，重新計算每列 content hash、journal SHA、response output hash。參數的 APPROVED 字樣仍只屬 SYNTHETIC_CONTROL_ONLY；沒有真實核准。

native plan 是明示 test-only 計畫表示，不是自行新增正式 schema。各 script 的 plan_ref SHA 與 parameter_binding 已綁定。projection 的 session_group 只是 COMPLETE／LIMIT 類別分組；8份原生 response 使用不同 SYNTHETIC_SESSION_1～8，不冒充同一場次。

| 事件 | 合成輸入控制 | fixture期待 |
| --- | --- | --- |
| E1 | STANDARD SWITCH、正確目的鏡頭/窗 | match |
| E2 | 同E1，但執行RETURN而非SWITCH | miss |
| E3 | LONG_GAP、0.6/1.6 RETURN、2.6決策SWITCH、7.6 entry | match |
| E4 | LONG_LOSS d3.0、0.6/1.6/2.6 RETURN | match |
| E5 | O1 OVERLAP窗，entry camera錯誤 | miss，單列OVERLAP |
| E6 | LIMIT在6.8；STANDARD前綴[0,1.8)只有0.6 RETURN（d=0.8>L；次個RETURN為1.8） | prefix match |
| E7 | LIMIT同6.8；LONG_GAP g5.4，完整前綴窗[0,6.4)沒有SWITCH | prefix miss |
| E8 | LIMIT同6.8；OVERLAP前綴[0,2.6)只有1.6 SWITCH，正確EXT_CLEAR | prefix match，單列OVERLAP |

依 D105 E5 裁定，全 PENDING 或 SETTLED 時：主群 E1/E2 的 STANDARD=1/2；E5 依固定 D93 計分 0/1、單列 OVERLAP；其餘5列 NOT_SCORED_PENDING_DECISION。U-D3 不是設定鍵，不能覆寫固定 D93；OVERLAP 不回流主比率。

全照建議是**合成測試選項**：COMPLETE主比率(E1–4)=3/4，STANDARD=1/2，LONG_GAP=1/1，LONG_LOSS=1/1；COMPLETE OVERLAP(E5)=0/1另列。E2前綴設定下LIMIT(E6/E7)=1/2，LIMIT OVERLAP(E8)=1/1另列。兩個狀態不合併分母。這些結果由 native scorer 實際重算；正式 LIMIT／OVERLAP 在證據介面未接上前仍 fail closed，合成控制不授權正式資料。

PENDING／RECOMMENDED／SETTLED 三個 SYNTHETIC 決策投影統一為 #366 的10鍵與 `PENDING_USER`，沒有 U-D3／E1／E2／E3 額外鍵。SETTLED 只映射 D105-4 的選值，不是假核准回條；正式定案檔是 `configs/evaluation/q5_v2_decisions_u6_20261101.json`（SHA `0daa1508e2a67607cdc6bac54684b1b5449d3a651325e5af23dfe0afb1bd3b7e`）。預設全 PENDING 檔不變。

每個計數/比率共享 exact receipt SHA、decisions bytes SHA及各輸入file SHA，數字所在row重複同一provenance；pending count由同一收據下的event rows重算。即使設定只多一個空白，bytes SHA改變也使舊報告失效。反例 `report.TAMPERED.SYNTHETIC.json` 把3改4並重封自身hash，checker仍拒絕，不能只驗報告自己的hash。額外反例覆蓋symlink、path escape、輸入pin、未知欄位、duplicate JSON key與禁止宣稱。

## 真實報告 TEST-ONLY glue

`AMIDST_L2_REPORT_MODULE` 指向實作模組（預設提議名 `amidst.evaluation.l2_complex_report`）；`AMIDST_L2_REPORT_DRIVER` 指向glue，提供 `exercise_case(*, implementation, inputs_path, decisions_path)`。這不是產品介面。glue須讀native_inputs釘住的原生資料，透過真scorer/report API執行，**不得把scored_events或golden report直接當評分結果**。投影scored rows只供checker重算與oracle；不能回傳假報告。

回傳原樣 `native_report`、真實實作檔 `implementation_file_sha256`、`native_scorer_executed=true`、`human_approval_verified=false`。另提供 `observations`，只把native report欄名映射為本fixture測試投影（events/metrics/provenance/pending_event_count），不得代算分數或補不存在的原生provenance。測試trace必須看到實作模組函式呼叫；測試不傳golden report，strict不許glue skip/xfail。若正式wire改名，更新glue；不能為通過測試偷改權威規則。

## 依賴到位後怎麼跑

接好上述glue後執行議題原命令：

```bash
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/evaluation/test_l2_complex_report.py
python scripts/check_l2_report.py --report docs/evaluation/L2_COMPLEX_REPORT_<日期>.json --inputs <凍結收據> --decisions configs/evaluation/q5_v2_decisions_u6_20261101.json
```

第二條正式wire目前刻意FAIL；#330交件後須以已定介面接正式重算，不可偷偷讓synthetic profile接受formal資料。

目前可直接自測：

```bash
python scripts/check_l2_report.py --report tests/fixtures/l2_report/SYNTHETIC/report.RECOMMENDED.SYNTHETIC.json --inputs tests/fixtures/l2_report/SYNTHETIC/inputs.SYNTHETIC.json --decisions tests/fixtures/l2_report/SYNTHETIC/decisions.RECOMMENDED.SYNTHETIC.json --synthetic-profile CQ36_SYNTHETIC_PROJECTION_V1
```

## 實際結果

Model / effort：GPT-6（Codex） / UNKNOWN。focused正常18passed/3skipped，strict18passed/3failed/0skipped/0errors；3 fail都是CQ36_IMPLEMENTATION_MISSING。checker CLI正例VALID_SYNTHETIC_PROJECTION，重封的反例FAIL REPORT_RECOMPUTE_MISMATCH。`python scripts/check_architecture_guard.py` NOT_RUN（#307尚未交付）；#127 kit NOT_APPLICABLE（沒有產品recording）。未做render、推論、U6/U7核定或正式驗收。

本輪原生驗收：`AMIDST_REQUIRE_IMPL=1 AMIDST_L2_REPORT_DRIVER=l2_complex_test_driver PYTHONPATH=src:tests/evaluation uv run --no-sync --offline python -m pytest -q tests/evaluation/test_l2_complex_report.py`。formal 資料與未採納 report wire 仍 NOT_RUN，不以這23項合成 PASS 代替正式驗收。
