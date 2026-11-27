# E6 去錨定三組：請求建構與 ApiGuard dry-run（#721／#732 G3，D396）

狀態：Draft。**沒有呼叫模型、沒有付費、沒有開帳本；不外傳影格。** 付費要等協調者審過並由使用者在對話同意（D242）。

## 實作（D398 修改後）

- `src/amidst/live_mode/aopen/arms.py`：`ArmDecider(arm, …)` 繼承 `AOpenDecider`，只換請求建構；套用、中性追蹤器、解析沿用原程式。`decider.py`、`neutral.py` 未修改（測試鎖 SHA-256 與原 AO 請求黃金值）。
- 設定：`configs/evaluation/e6_arms_v1.json`（`e6.arm-config.v1`）；log 格式 `e6.arm-log.v1`（`scripts/evaluation/e6_arms_run.py`）；兩者在 `configs/architecture/schema_registry_v1.json` 登記為 `PROPOSED_LITERAL_ONLY_NOT_ADOPTION`。
- **E6 專用中性靜態前綴**（`E6_SYSTEM_TEXT`＋scene context＋`E6_BASE`＋組別說明）：不再使用 `agent_service.SYSTEM_TEXT` 與 `E5_EXTRA`（AO 路徑照舊用）。沒有「Rule gates」「previous display」「current target is unchanged」「AO_STATE」「neutral tracker」等字樣；`UNCERTAIN`／`NOT_VISIBLE`／`STILL_HERE_OCCLUDED` 只用中性定義。參考截圖文字改為查詢條件：`TARGET REFERENCE (crop taken when the user's query "a person wearing red" was first matched)`，不再寫 `Tracker colour labels`。
- 三組（一次只疊一個因素；預登 §2.1）：
  - `DEANCHOR`：請求沒有目前追蹤框、規則顯示、規則答案、規則閘門結果、`AO_STATE`；鏡頭按擷取順序固定；每次附原始種子參考截圖。**只附前一次答案**：`PREVIOUS_ANSWER={SELF_ANSWER_UNVERIFIED:{…}}`（沒有答案前為 `null`），**不含任何 SYSTEM_OBSERVED 欄位**（時間、是否套用、追蹤秒數都沒有）。DEANCHOR 前綴只說明 `PREVIOUS_ANSWER`／`SELF_ANSWER_UNVERIFIED`，不提 `HISTORY`／`SYSTEM_OBSERVED`；HIST／SUM 才附 `HISTORY` 的說明。
  - `DEANCHOR_HIST`：以 `HISTORY=`（最多 8 筆）取代 `PREVIOUS_ANSWER`。每筆 `{id, SYSTEM_OBSERVED{提問／生效 tick、時間、鏡頭、是否套用、fallback、followed_s}, SELF_ANSWER_UNVERIFIED{answer、camera、detection_id、box、confidence、ranking}}`。
    - `followed_s`＝中性追蹤器在「已套用的 SELECT／OWN_BOX」之後連續 FOLLOWING 的 tick 數，計到追蹤器 LOST／遮擋保留、或被後一個**已套用**的選擇（或已套用的 NOT_VISIBLE／OCCLUDED）取代為止；`UNCERTAIN`、未套用、EXPIRED 不截斷；COASTING 不計也不結束。這是系統觀察，不是身分確認。
  - `DEANCHOR_HIST_SUM`：回答可附 `summary`（≤3 句，每句 `{text, sources:[H#…]}`）。每句都要有來源且來源必須是該次請求顯示過的 history id，否則**整段丟棄**，下次不傳；通過者以 `PRIOR_NOTES`（標 `SELF_ANSWER_UNVERIFIED`）回傳。失敗的呼叫（有 fallback）不清掉舊 notes。摘要由原回答附帶，不額外呼叫模型。
- GT 隔離：序列化器遞迴拒絕 GT／可見性／深度／軌跡等鍵名（`ValueError`）；摘要文字含 GT 字樣則丟棄；AST 測試確認兩個檔案不 import `amidst.evaluation`／評分器、也沒有相關識別字；方法簽章只收觀察資料。B1 sidecar 只用來取種子參考截圖時刻（同 AO）。
- 已知取捨：`STILL_HERE_OCCLUDED` 仍可回答，沒有目標時由原解析忽略（`OCCLUDED_NO_TARGET`）；請求不告知。候選框的 HSV 顏色標籤（`colours red|blue`）保留為偵測觀察，規則閘門結果移除。

## 測試

`uv run python -B -m pytest tests/live_mode/test_e6_arms.py tests/live_mode/test_aopen_decider.py tests/live_mode/test_aopen_neutral.py tests/unit/test_architecture_guard.py -q` → 全過；`git diff --check` 乾淨。

## ApiGuard dry-run（估算，不呼叫）

診斷 **K=1**（預登 §2.1／§5，D398；#721 本文原寫 K=3 已更正）。案例 `E3-A1`、`E3-B1`、`E3-C1`（預登 §5 預設）。指令（`--dry-run`：用本機假 transport 建出真的請求，量文字長度＋每張圖 1100 tokens，與 `guarded_responses_transport` 同一估法，再用 `estimate_run`；不開帳本、不讀金鑰）：

```
uv run python -B scripts/evaluation/e6_arms_run.py --root local/evidence/e3-652-20261122 \
  --cameras local/data/live-assets-20261115/cameras.catalog.json --cases E3-A1 E3-B1 E3-C1 --k 1 --dry-run
```

估法（D398 後改為較保守的上界）：
- **呼叫數**：每段取上限 ⌈秒數÷2×1.5⌉（每次都提問）。
- **prompt tokens**：本機假答案（全部 `UNCERTAIN`）重播量到的平均值（文字 chars÷3＋每張圖 1,100 tokens）**再加最大歷史區塊的 padding**：HIST／SUM 以「每次呼叫都有新回答、歷史長到上限 8 筆、各欄位取長值」估；SUM 另加 3 句×200 字的摘要與來源；DEANCHOR 加一筆前一次答案。padding 為 DEANCHOR 87、HIST 1,465、SUM 1,740 tokens。
- **輸出 tokens**：典型值 300／300／450，**不是** `max_output_tokens`（1,500）；輸出不是上界，總額另由 ApiGuard 的 `--max-usd` 硬擋。

| 組 | 呼叫數 | 平均 prompt tokens（含 padding） | 輸出 tokens | 每次 USD | 合計 USD |
|---|---|---|---|---|---|
| DEANCHOR | 127 | 17,728 | 300 | 0.019228 | 2.44 |
| DEANCHOR_HIST | 127 | 20,077 | 300 | 0.021577 | 2.74 |
| DEANCHOR_HIST_SUM | 127 | 20,449 | 450 | 0.022699 | 2.88 |
| 三組合計 | 381 | | | | **8.07** |

每張 320×180 圖算 1,100 tokens、9 張圖，不計快取；實際單價與圖片 token 未核對（UNKNOWN）。上限 USD 10 內。累計花費基準 USD 38.17（D375）＋新列；本次新列 = 0。

## 付費路徑（已接，**未執行**）

`scripts/evaluation/e6_arms_run.py`；沒有 `--paid` 一律拒絕（`PAID_RUN_NOT_AUTHORIZED`）。需協調者核准後才執行：

```
uv run python -B scripts/evaluation/e6_arms_run.py --root local/evidence/e3-652-20261122 \
  --cameras local/data/live-assets-20261115/cameras.catalog.json --cases E3-A1 E3-B1 E3-C1 --k 1 \
  --paid --max-usd 10 --baseline-json local/evidence/api-usage/RECONCILIATION_20261124.json \
  --out <絕對路徑>/local/evidence/e6-arms-k1-20261127
```

- 只允許 K=1 與 `E3-A1`／`E3-B1`／`E3-C1`（不得重複）；`--max-usd` 必須在 (0, 10]。其他組合拒絕。
- 執行順序：先 dry-run 估算（上界）→ 估算必須 ≤ `--max-usd` → D375 累計檢查：`actual_total_usd`（38.17）＋ baseline `effective_at` 之後的新帳本列（本次 `<out>/ledger`，另可用 `--extra-ledger` 加其他帳本）＋估算 ≤ `cap_usd`（90），否則 `CUMULATIVE_OVER_CAP` 停止；通過後才建立 transport。
- 每次呼叫都走 `ApiGuard`（caller `e6arms`、model `gpt-6.1-terra`、單次上限 USD 0.2／40000 tokens、總額上限＝`--max-usd`），帳本寫在 `<out>/ledger/usage.jsonl`；帳本只有 ts／caller／model／outcome／reason／tokens／est_cost_usd，不含金鑰、提示或回應。金鑰只在 guard 內讀 `OPENAI_API_KEY`。
- 輸出（LOCAL，不進 git；**原子寫入**：先序列化成字串，寫同目錄暫存檔再 `os.replace`，最終檔名不會是半寫檔，殘留 `.tmp` 不算已存在、開跑前清掉）：`<out>/PRECHECK.json`（估算與累計檢查）、`<out>/STATUS.json`（`COMPLETE`／`STOPPED`／`INCOMPLETE`＋原因；任何例外或停止路徑都會寫，並寫 MANIFEST）、`<out>/<case>/<ARM>.k1.json`（回答、請求雜湊 `body_sha256`／影像 SHA、歷史、逐 tick 結果）、`<out>/ledger/usage.jsonl`、`<out>/MANIFEST.sha256`。輸出前遞迴檢查鍵名，出現 GT／可見性／深度／軌跡類鍵名即中止且不寫檔。已存在的輸出跳過，不覆蓋。
- 停止條件：guard 拒絕（`CALL_BUDGET_EXHAUSTED`）時該組重播**立即停止**（`stopped_early={tick, reason}` 記在該組輸出），整個執行停止、不跑後續組別，STATUS 記 `STOPPED`；provider 錯誤率 > 10% 同樣停止並保留輸出。
- 離線測試（`tests/live_mode/test_e6_arms_run.py`，假 transport／假 opener）：沒旗標拒絕、錯誤組合與超額 `--max-usd` 拒絕、估算超限與累計超 90 拒絕（含剛好 90 允許、舊帳本列不計）、帳本列格式與不留金鑰／提示、guard 拒絕與缺金鑰、輸出清單／MANIFEST／無評分端鍵名、已存在不覆蓋、序列化失敗不留半寫檔且 STATUS＝INCOMPLETE、殘留暫存檔不被當成已存在、非預期例外仍寫 STATUS／MANIFEST、guard 拒絕立即停止（重播層與執行層）、估算 padding 排序。
