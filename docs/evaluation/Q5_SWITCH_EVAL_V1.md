# Q5 凍結輸出對劇本評分程式 v1

依 D71／D73（#129、#93）由 Codex 寫程式，組員審結果；只在評估端讀劇本。**正式評分 NOT_RUN**：#110 Controller、#115 A4/B4與正式劇本尚未產出。未寫事件答案、人物路線或情境題庫。本版測試只有最小布林／整數時間的機械算式。

## 凍結邊界

1. Controller先完成輸出，保存response與append-only decisions JSONL，記錄各自檔案SHA；不得先把劇本傳給Controller。
2. 評估CLI先讀這兩個凍結檔、驗可信file pins，重算response.output_sha256與各decision.content_sha256，驗response.decisions_sha256指向傳入的確切JSONL bytes；session／decision／step／source時間拒錯。
3. **上述驗證成功後**CLI才開script檔，驗另一份可信SHA與run/clock。失敗不讀script、不輸出假準確率。
4. 相同凍結輸出可以各自對不同核定劇本版本評估；評估結果不能回填索引、圖、參數、prompt或這次輸出。

程式只在 `amidst.evaluation.q5_switch_eval`，runtime/controller不依賴它；不讀RGB、不呼叫Ollama、不接網路。此凍結是內容hash與可信輸入pin的工程保證，不是證明人在先前從未看過劇本的遠端公證。scope/index/graph的完整契約符合性仍交#127獨立驗證。

## 劇本評估 adapter（D73 採逐事件決策窗；窗寬另核）

程式只接受明確的 `q5-evaluation-script.v1`，不猜renderer原始腳本的欄位或以actor ID選切鏡目標。正式#115劇本若是不同格式，須由評估端另外固定轉換與hash，**不讓推論端讀原始劇本**。

必要頂層：schema_version、status（PROPOSED/APPROVED）、approval_ref（APPROVED必填引用）、run_id、clock_id、events[]。每個event由劇本作者／核定方提供event_id、action、decision_window_us。所有時間均來源微秒、半開區間；決策窗須依序不重疊且完整落於該次查詢resolved_source_ranges_us，不能把query沒涵蓋的事件算成模型錯誤。

| action | 必要附加欄位 | 比較算式（提案） |
|---|---|---|
| SWITCH | allowed_camera_ids[]、entry_window_us | 決策窗內恰一個已執行動作且為SWITCH；timeline相機在允許集合、entry時刻在明確窗內 |
| RETURN_TO_ORIGIN | 無 | 決策窗內恰一個已執行動作且為RETURN_TO_ORIGIN |
| NO_SWITCH | 無 | COMPLETE成功終態，且至少一筆決策 source_time_us ≥ 窗終點；窗內無SWITCH，允許已接受return。空session或未覆蓋窗的中斷輸出記match=null／COVERAGE_MISSING，不進分母 |

entry_window_us也必須在查詢範圍內。時間窗由劇本明示，**不內建容忍秒數**。可接受多個目的相機時在allowed_camera_ids明列，不能讓評分器猜。多次SWITCH不被第一個正確動作掩蓋。窗外的SWITCH／RETURN另列uncovered_executed_actions，不能只看event_match_ratio而忽略額外動作。

D73已選逐事件決策窗，D75要求窗寬由Claude依劇本提案並在輸出凍結前交使用者核定，程式不自選窗寬。劇本本身仍須獨立核准：劇本若PROPOSED，報告MEASURED_PROPOSED_SCRIPT；只有帶approval_ref的APPROVED劇本才標MEASURED_APPROVED_SCRIPT，仍不宣告通過Demo。這不核准任意劇本的答案或窗寬；需更多動作或連續追蹤指標時另版，不能默默變更分母。

## 決策與畫面對齊

freeze階段只接受response.status=COMPLETE，UNKNOWN／PARTIAL／NO_SEED／ENDED_BY_LIMIT等不評分，在讀script前拒絕。讀executed_action，不能把submitted、被拒決定或Agent文字當已切鏡。RETURN_TO_ORIGIN亦需accepted is True；被拒return不得當已執行。SWITCH需accepted=true、executed_candidate_ref與entry_observation_id；再以decision_id綁timeline中entered_by=SWITCH的ON_CAMERA段。entry觀測第一筆須相同，開始時間不得早於decision_time_us。孤立、重複、缺失timeline綁定是資料錯誤，不當錯誤模型決策。timeline區間不得重疊或超出query，GAP位置必須null，不以劇本補盲區位置。

這個比對**不證明同一人**，也不重新驗IoU、D28排序、guard、候選證據hash或Agent工具合法性。那些是#127與各產品模組的責任；agent_used_reported/fallback_used_reported僅轉錄，不冒稱此評分器獨立重建了Agent行為。

## 操作與報告

```bash
PYTHONPATH=src uv run --no-sync python scripts/eval_q5_switch.py \
  --response <frozen-response.json> --response-sha256 <trusted-file-sha256> \
  --decisions <frozen-decisions.jsonl> --decisions-sha256 <trusted-file-sha256> \
  --script <evaluation-script.json> --script-sha256 <trusted-script-sha256> \
  --output <new-report.json>
```

輸出只可新建、不覆寫。報告記三個輸入file hashes、scorer版本、script核定狀態、event總數／match數及比率、各action計數、逐event觀察、窗外動作；不帶本機路徑、實時計時或通過門檻。canonical output_sha256排除自身與stats，同輸入重跑相同。

指定focused `pytest tests/unit/test_q5_switch_eval.py`；`git diff --check`。測試包含hash／scope錯誤、錯相機／時窗、NO_SWITCH、return、孤立／回溯entry、重複event、未核定script及「輸出驗證失敗時絕不開script」。#127沒有此離線報告schema，產品輸入完整schema驗證須在正式評分之前另跑。無正式劇本／Controller輸出時不產正式評分數字，不由程式輸出倒造標準答案。


## CX-2 審查修正的報告欄位

`decision_count`、`last_source_time_us` 顯示完整決策數與最後來源時間；`coverage_missing_event_ids` 列未評事件。總 `event_match_ratio.denominator` 只含 match 非 null 的事件，沒有可評事件時 value=null。

每筆 observed 保留原 `decided_by`，報告 `by_decided_by` 分 RULE_ONLY／AGENT／FALLBACK／OTHER；RULE_FALLBACK 與舊 FALLBACK 只在統計分組正規化，原字串不改。每組各報 decision_count 與事件比率，混合或無已執行動作的事件列 OTHER，不從 session 旗標猜來源。`fallback_only_event_match_ratio` 只含觀察動作全部為兜底的事件；`non_fallback_event_match_ratio` 只含全部非兜底的事件；兩者都排除沒有執行動作的事件，避免把無動作的NO_SWITCH硬分到某個模式。

`approval_ref` 現階段只驗非空字串；正式劇本須由評估端指向使用者核定留言URL與其固定內容hash，字串本身不是核准證明。本PR不包含#129第一階段的完整「正確切鏡」定義文件或SYNTHETIC情境集，不產正式答案。
