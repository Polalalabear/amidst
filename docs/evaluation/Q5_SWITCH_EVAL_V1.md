# Q5 凍結輸出對劇本評分程式 v1

依 D71（#129、#93）由 Codex 寫程式，組員審結果；只在評估端讀劇本。**正式評分 NOT_RUN**：#110 Controller、#115 A4/B4與正式劇本尚未產出。未寫事件答案、人物路線或情境題庫。本版測試只有最小布林／整數時間的機械算式。

## 凍結邊界

1. Controller先完成輸出，保存response與append-only decisions JSONL，記錄各自檔案SHA；不得先把劇本傳給Controller。
2. 評估CLI先讀這兩個凍結檔、驗可信file pins，重算response.output_sha256與各decision.content_sha256，驗response.decisions_sha256指向傳入的確切JSONL bytes；session／decision／step／source時間拒錯。
3. **上述驗證成功後**CLI才開script檔，驗另一份可信SHA與run/clock。失敗不讀script、不輸出假準確率。
4. 相同凍結輸出可以各自對不同核定劇本版本評估；評估結果不能回填索引、圖、參數、prompt或這次輸出。

程式只在 `amidst.evaluation.q5_switch_eval`，runtime/controller不依賴它；不讀RGB、不呼叫Ollama、不接網路。此凍結是內容hash與可信輸入pin的工程保證，不是證明人在先前從未看過劇本的遠端公證。scope/index/graph的完整契約符合性仍交#127獨立驗證。

## 劇本評估adapter（PROPOSED）

程式只接受明確的 `q5-evaluation-script.v1`，不猜renderer原始腳本的欄位或以actor ID選切鏡目標。正式#115劇本若是不同格式，須由評估端另外固定轉換與hash，**不讓推論端讀原始劇本**。

必要頂層：schema_version、status（PROPOSED/APPROVED）、approval_ref（APPROVED必填引用）、run_id、clock_id、events[]。每個event由劇本作者／核定方提供event_id、action、decision_window_us。所有時間均來源微秒、半開區間；決策窗須依序不重疊且完整落於該次查詢resolved_source_ranges_us，不能把query沒涵蓋的事件算成模型錯誤。

| action | 必要附加欄位 | 比較算式（提案） |
|---|---|---|
| SWITCH | allowed_camera_ids[]、entry_window_us | 決策窗內恰一個已執行動作且為SWITCH；timeline相機在允許集合、entry時刻在明確窗內 |
| RETURN_TO_ORIGIN | 無 | 決策窗內恰一個已執行動作且為RETURN_TO_ORIGIN |
| NO_SWITCH | 無 | 決策窗內沒有SWITCH；允許return，以免把「不追」綁成未約定的單一UI動作 |

entry_window_us也必須在查詢範圍內。時間窗由劇本明示，**不內建容忍秒數**。可接受多個目的相機時在allowed_camera_ids明列，不能讓評分器猜。多次SWITCH不被第一個正確動作掩蓋。窗外的SWITCH／RETURN另列uncovered_executed_actions，不能只看event_match_ratio而忽略額外動作。

這些是比較定義提案，尚非核定的「正確切鏡」標準：劇本若PROPOSED，報告MEASURED_PROPOSED_SCRIPT；只有帶approval_ref的APPROVED劇本才標MEASURED_APPROVED_SCRIPT，仍不宣告通過Demo。新script/wire格式及NO_SWITCH如何解釋待使用者核定；需更多動作或連續追蹤指標時另版，不能默默變更分母。

## 決策與畫面對齊

讀executed_action，不能把submitted、被拒決定或Agent文字當已切鏡。SWITCH需accepted=true、executed_candidate_ref與entry_observation_id；再以decision_id綁timeline中entered_by=SWITCH的ON_CAMERA段。entry觀測第一筆須相同，開始時間不得早於decision_time_us。孤立、重複、缺失timeline綁定是資料錯誤，不當錯誤模型決策。timeline區間不得重疊或超出query，GAP位置必須null，不以劇本補盲區位置。

這個比對**不證明同一人**，也不重新驗IoU、D28排序、guard、候選證據hash或Agent工具合法性。那些是#127與各產品模組的責任；agent_used_reported/fallback_used_reported僅轉錄，不冒稱此評分器獨立重建了Agent行為。

## 操作與報告

```bash
PYTHONPATH=src python scripts/eval_q5_switch.py \
  --response <frozen-response.json> --response-sha256 <trusted-file-sha256> \
  --decisions <frozen-decisions.jsonl> --decisions-sha256 <trusted-file-sha256> \
  --script <evaluation-script.json> --script-sha256 <trusted-script-sha256> \
  --output <new-report.json>
```

輸出只可新建、不覆寫。報告記三個輸入file hashes、scorer版本、script核定狀態、event總數／match數及比率、各action計數、逐event觀察、窗外動作；不帶本機路徑、實時計時或通過門檻。canonical output_sha256排除自身與stats，同輸入重跑相同。

指定focused `pytest tests/unit/test_q5_switch_eval.py`；`git diff --check`。測試包含hash／scope錯誤、錯相機／時窗、NO_SWITCH、return、孤立／回溯entry、重複event、未核定script及「輸出驗證失敗時絕不開script」。#127沒有此離線報告schema，產品輸入完整schema驗證須在正式評分之前另跑。無正式劇本／Controller輸出時不產正式評分數字，不由程式輸出倒造標準答案。
