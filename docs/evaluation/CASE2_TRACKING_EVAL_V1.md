# Case2 追蹤評估 projection v1（PROPOSED）

Issue #461。這是可獨立 review 的工程評分提案與合成機械測試，不是正式
CX-8 decoder、研究指標核定或驗收。**真實數字：待補 #417；`real_data_status=NOT_RUN`。**
不引用 #454 的固定假實測數字，不執行模型、render、API 或原媒體讀取。

## Owning sources 與尚未解決的定義

- 基準 `mainline/q1q5`：`796cc176cd40bedbfe701b95192d3c8679755aa9`。
- #397 研究計畫 head `e6c6ad02805b4f0c2992245919df91c9771b9097`，
  `docs/research/MODEL_EXPERIMENT_PLAN_20261102.md` SHA-256
  `5a24882f553bbb45327fec4c4a1841e658d19fe4903fd635c8dd9e3c636a941b`。
  §1.7 定義 matched 事件的 `L_sw`，來源時間 µs 除以 1000 得 ms；§D.3
  要求保留取樣解析度限制。**該版未找到 issue 所稱 Eq.14 的切鏡一致性公式**。
  本工具固定 `eq14_status=UNRESOLVED`，不能宣稱符合 Eq.14。
- `docs/evaluation/Q5_SWITCH_EVAL_V1.md` 與
  `src/amidst/evaluation/q5_switch_eval.py` 擁有既有 SWITCH／entry 決策窗比對規則。
  本工具不修改或取代既有 scorer，也不讀其劇本檔案。
- `docs/engineering/CX8T_BASELINE_FREEZE_CHECKER_20261029.md` 的正式 production
  contract 是 `UNSELECTED`。本工具只接受下述明示 projection；CX-8 原生格式與
  時間／欄位 adapter 均 `NOT_RUN`，不得把 projection 欄位當正式契約。
- #437 head `06c65a26690e2ab456e999daa33523a799c1216f` 的
  `docs/evaluation/RESEARCH_REPORT_TABLES_AND_FIGURES_V1.md` SHA-256
  `23c0993a97f29f26036beda5be4303f1dea309bce8c6414ac4e96b31e14ee476`，
  `q5_switch_windows.json` 使用 `expected_category`、`observed_category`、`latency_ms`。
  該報表的 category agreement 不檢查相機；不能直接把本工具的 camera/action
  一致率改名為其 category 指標，亦不能把其結果當 Eq.14。本 PR 不接線到 #437。

## 指標與單位

所有算式固定 `definition_status=PROPOSED`，待 Claude 獨立 review 與使用者確認。
下列前三個新增定義不冒稱出自 #397；只有 `L_sw` 算式沿用 #397 §1.7。

| 輸出 | 定義與有效條件 | 單位／彙總 |
| --- | --- | --- |
| `switch_consistency` | **本 PR PROPOSED**：逐 sample 對齊後，action 相同且 prediction 的 `decision_time_us` 在 reference 的半開決策窗內；若兩者 action 為 SWITCH，另要求 camera 相同、entry 不早於 decision 且 entry 在 reference 半開 entry 窗內。action 僅 SWITCH／KEEP／LOST／ABSTAIN。已知 action 或 camera 不同是 false；缺對齊欄位保持 UNKNOWN | bool；`100*n_agreed/n_valid` %，零分母 UNKNOWN |
| `switch_latency_ms` | **#397 §1.7 `L_sw` 算式**：僅一致且為 SWITCH 的 sample，`(decision_time_us-decision_window_us[0])/1000`。這個工程 projection 不代表正式 v1 劇本已核准 | ms；有效 sample 的中位數，無值 UNKNOWN |
| `lost_onset_error_ms` | **本 PR PROPOSED**：同一 sample 的 prediction/reference `lost_onset_us` 絕對差除以 1000；兩者都必須是來源 clock 的非負整數時間 | ms；中位數，缺時點 UNKNOWN |
| `landing_error_m` | **本 PR PROPOSED**：同一 sample、同一來源時刻、同一合法 2D coordinate frame、同一 coordinate authority reference 且單位均為 m 時，兩個有限位置的 Euclidean L2 距離。只評獨立 reference 已提供的落點，沒有內插、時間容差或座標轉換 | m；中位數，無合法獨立 reference UNKNOWN |

四項各有自己的 `n_valid`／`n_unknown`；camera 錯誤不使獨立且合法的跟丟誤差
或落點誤差失效。`MISSING`、`UNKNOWN`、無配對、source/run/clock/sample-set 不一致
會使該列四項全部 UNKNOWN，逐項保留原因，不當成 0 或失敗事件。已知錯相機
可得到 0% 一致率；這和沒有可評樣本的 UNKNOWN 不同。空列表的觀測計數為 0，
其比率／中位數保持 UNKNOWN。所有 prediction-only／reference-only sample 都列出，
不默默略過。每個 sample 最多一筆 prediction/reference；重複 ID 拒絕，
不採第一筆，也不從多筆預測挑最佳結果。呼叫端必須在評分前固定 sample-set 與
匹配單位，工具不推斷 target identity。

時間解析度與取樣頻率不由工具猜測；本版測試不量測真實採樣誤差、不提供 CI／P90。
正式研究如需上述統計、失敗率或多次 SWITCH 判定，須先核定 sample 單位與 decoder，
不能把本 projection 的單列一致率直接升為正式研究結論。

## 明示輸入契約與 GT 隔離讀取清單

`amidst.evaluation.case2_tracking_eval.score` 只接受兩段已凍結 JSON **bytes**，
以及分別從可信收據取得的完整 `expected_prediction_sha256`、
`expected_reference_sha256`。先驗 bytes SHA 再 parse；不開檔、不追 locator、
不掃目錄、不 import runtime。每份上限 1 MiB；重複 JSON key、非標準 NaN/Infinity、
未知頂層／sample 欄位、非明示角色、重複 sample ID 都拒絕。

兩份頂層只允許以下欄位（全部必填）：

| 欄位 | 契約 |
| --- | --- |
| `format` | `case2-evaluation-projection.v1`，是本 PR 的 PROPOSED projection 名稱 |
| `role` | 各自為 `prediction`／`reference` |
| `data_origin` | prediction 只允許 SYNTHETIC；reference 允許 SYNTHETIC 或 INDEPENDENT_HUMAN。後者只表示宣告來源，不能把合成 prediction 變為真實結果 |
| `evaluation_eligible` | 必須 false；不接受正式資格宣告 |
| `authoring_ref` | 非空來源收據引用；兩份必須不同，不接受 UNKNOWN／MISSING |
| `source_id`、`run_id`、`clock_id` | 顯式非空來源綁定；不接受 UNKNOWN／MISSING。雙方不同時整列 UNKNOWN |
| `sample_set_sha256` | 評分前獨立固定的 sample-set 清單完整 SHA-256；雙方須相同才能評分，不由 predictions 產生 |
| `samples` | 顯式列表，允許空列表 |

每個 sample 必填唯一 `sample_id`、`status`（OBSERVED／MISSING／UNKNOWN）。
其他只允許：`action`、`camera_id`、`decision_time_us`、`entry_time_us`、
`decision_window_us`、`entry_window_us`、`lost_onset_us`、`landing`。
缺指標欄位只影響依賴它的指標，保持 UNKNOWN。決策窗／entry 窗是
reference 作者提供的來源 clock `[start_us,end_us)`，不得由 predictions 推回。
`landing` 只允許 `frame_id`、`unit`、`coordinate_authority_ref`、`position`（2D）、
`source_time_us`。coordinate authority 只是待 review 的合法來源宣告；本 scorer
不讀校正資產，也不驗證該引用實際已核定。

**評估端實際讀取**：上述兩份 projection 的 bytes 與 expected hashes；除此之外無
外部輸入。prediction 是待評輸出，reference 是獨立人工標註或完全獨立寫成的合成
fixture。測試的兩份 fixture 分別 authored，不從 prediction 複製 reference。
人工 reference 需有自身 source/run/clock/sample-set pins 與 authoring 收據；
不能用 predictions 自動生成標註、不能用 renderer positions 補落點、不能讀 GT、
`gt_private/`、劇本關鍵影格、軌跡、visibility、depth、原 RGB／影片、API key。
評分結果不能回填 inference、ranking、index、prompt 或此次 prediction。

Codex 已按此明示讀取清單確認 GT 隔離工程邊界。工具只能檢查宣告與 hash 一致，
不能遠端認證獨立標註的歷史、座標合法性或人類核准，故固定
`independence_verified=false`、`evaluation_eligible=false`。期待 hash 不能由不可信
producer 自己提供後就視為已認證。

## 呼叫與驗證

```python
from amidst.evaluation.case2_tracking_eval import score

report = score(
    frozen_prediction_bytes, independent_reference_bytes,
    expected_prediction_sha256=trusted_prediction_pin,
    expected_reference_sha256=trusted_reference_pin,
)
```

本 PR 沒有接 production CLI；呼叫者負責合規取得 bytes，不得擴成任意 asset loader。
report 保留兩份完整 bytes hashes、各自 bindings／origins、mismatch 欄位、逐 sample
數值／UNKNOWN 原因與各指標有效／未知計數；同樣 bytes 與 pins 產生相同報告。
固定 `production_adapter=NOT_RUN`、`real_data_status=NOT_RUN`，不輸出 ENGINEERING
或正式接受狀態。

```sh
uv --no-cache run --offline --no-project --python /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/.venv/bin/python python -m pytest -q -o addopts= -o pythonpath=src tests/unit/test_case2_tracking_eval.py
uv --no-cache run --offline --no-project --python /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/.venv/bin/python python scripts/check_architecture_guard.py --repo . --base origin/mainline/q1q5
git diff --check
```

LOCAL Python 路徑僅為既有工具環境，不是資料來源。測試只含獨立合成 inputs：perfect、
wrong camera/action、MISSING／UNKNOWN、source/run/clock/sample-set mismatch、
無 reference／prediction、零分母、coordinate/unit/time mismatch、缺欄位、半開窗、
hash 錯誤、重複 ID 與禁止資格升格。不代表真實 CX-8 數字或正式流程執行。

後續待補：Eq.14 owning source、Claude 獨立 review／指標定義確認、CX-8 正式 decoder、
獨立人工 reference 與座標 authority review、#417 核准參數與正式凍結輸出。
