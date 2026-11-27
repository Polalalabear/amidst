# E6 去錨定三組：請求建構與 ApiGuard dry-run（#721／#732 G3，D396）

狀態：Draft。**沒有呼叫模型、沒有付費、沒有開帳本；不外傳影格。** 付費要等協調者審過並由使用者在對話同意（D242）。

## 實作

- `src/amidst/live_mode/aopen/arms.py`：`ArmDecider(arm, …)` 繼承 `AOpenDecider`，只換請求建構；套用、中性追蹤器、解析沿用原程式。`decider.py`、`neutral.py` 未修改（測試鎖 SHA-256 與原 AO 請求黃金值）。
- 設定：`configs/evaluation/e6_arms_v1.json`（`e6.arm-config.v1`）；log 格式 `e6.arm-log.v1`（`scripts/evaluation/e6_arms_run.py`）；兩者在 `configs/architecture/schema_registry_v1.json` 登記為 `PROPOSED_LITERAL_ONLY_NOT_ADOPTION`。
- 三組（一次只疊一個因素）：
  - `DEANCHOR`：請求沒有目前追蹤框、規則顯示、規則答案、規則閘門結果、`AO_STATE`；鏡頭按擷取順序固定，不受上次排序影響；每次附原始種子參考截圖。`E5_EXTRA` 去掉指向 `AO_STATE`／rule_state 的那一行（`E5_BASE`），再接 E6 去錨定說明。
  - `DEANCHOR_HIST`：加 `HISTORY=`，最多 8 筆，由腳本維護。每筆 `{id, SYSTEM_OBSERVED{提問／生效 tick、時間、鏡頭、是否套用、fallback、追蹤秒數}, SELF_ANSWER_UNVERIFIED{answer、camera、detection_id、box、confidence、ranking}}`。「之後追蹤到多久」是中性追蹤器 IoU 連續 FOLLOWING 的 tick 數，是系統觀察，不是身分確認。
  - `DEANCHOR_HIST_SUM`：回答可附 `summary`（≤3 句，每句 `{text, sources:[H#…]}`）。每句都要有來源且來源必須是該次請求顯示過的 history id，否則**整段丟棄**，下次不傳；通過者以 `PRIOR_NOTES`（標 `SELF_ANSWER_UNVERIFIED`）回傳。摘要由原回答附帶，不額外呼叫模型。
- GT 隔離：序列化器遞迴拒絕 GT／可見性／深度／軌跡等鍵名（`ValueError`）；摘要文字含 GT 字樣則丟棄；AST 測試確認兩個檔案不 import `amidst.evaluation`／評分器、也沒有相關識別字；方法簽章只收觀察資料。B1 sidecar 只用來取種子參考截圖時刻（同 AO）。
- 已知取捨：`STILL_HERE_OCCLUDED` 仍可回答，但請求不告知有無目標；沒有目標時被忽略（`OCCLUDED_NO_TARGET`）。顏色標籤（HSV）保留為偵測觀察，規則閘門結果移除。

## 測試

`uv run python -B -m pytest tests/live_mode/test_e6_arms.py tests/live_mode/test_aopen_decider.py tests/live_mode/test_aopen_neutral.py tests/unit/test_architecture_guard.py -q` → 全過；`git diff --check` 乾淨。

## ApiGuard dry-run（估算，不呼叫）

指令（`--dry-run`：用本機假 transport 建出真的請求，量文字長度＋每張圖 1100 tokens，與 `guarded_responses_transport` 同一估法，再用 `estimate_run`）：

```
uv run python -B scripts/evaluation/e6_arms_run.py --root local/evidence/e3-652-20261122 \
  --cameras local/data/live-assets-20261115/cameras.catalog.json --cases E3-A1 E3-B1 E3-C1 --k 3 --dry-run
```

**案例是替身**：本機 E3 根目錄只有 9 段索引（A1 A2 A3 B1 B2 C1 C2 D1 D2），三段診斷（相似人物且開頭不同／無相似人物／長盲區）的實際挑選與劇本分類屬評分端、未在本 PR 決定（UNKNOWN）；費用只與段長與組別有關，故用 A1、B1、C1 估。模型 `gpt-6.1-terra`，K=3，呼叫數取每段上限 ⌈秒數÷2×1.5⌉（上界：每次都提問）。

| 組 | 呼叫數 | 平均 prompt tokens | 輸出 tokens | 每次 USD | 合計 USD（上界） |
|---|---|---|---|---|---|
| DEANCHOR | 381 | 18,159 | 300 | 0.019659 | 7.49 |
| DEANCHOR_HIST | 381 | 19,252 | 300 | 0.020752 | 7.91 |
| DEANCHOR_HIST_SUM | 381 | 19,349 | 450 | 0.021599 | 8.23 |
| 三組合計 | 1,143 | | | | **23.63** |

注意：
- 這個估法每張 320×180 圖算 1,100 tokens、8 台鏡頭，平均 18k tokens；E5 dry-run 用 8,800 平均。若實際接近 E5，上界約減半（三組合計約 USD 11–12）。實際單價與圖片 token 未核對（UNKNOWN）。
- #721 第 3 點的診斷上限是 USD 10；上界 23.63 超過，三組跑滿 K=3 放不進。可選：只跑 K=1、降低呼叫上限係數、或分批（先 DEANCHOR）。待協調者決定，再另跑 ApiGuard dry-run 並取得使用者同意。
- 累計花費基準 USD 38.17（D375）＋新列；本次新列 = 0。
