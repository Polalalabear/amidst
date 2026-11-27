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

## 正式 12 段 K=3 付費路徑與 verdict（D401，#721 剩餘兩件；**未執行**）

- `e6_arms_run.py` 的第二個付費模式 **FORMAL**：只接受 `--k 3` 與 `E6-S01`…`E6-S12` 全部 12 段（缺、多、重複都拒絕）、`--max-usd` ∈ (0, 32]。介面對齊 `run_all.sh` 2c：`--root <formal root> --cameras … --cases … --arms … --k 3 --paid --max-usd … --baseline-json … --out … --extra-ledger <ledger dirs…>`。
- 閘門（D402：批 3 改機械閘門、使用者事前同意，**不再用 `E6_BATCH3_APPROVED` 環境變數**；完整比對由 `e6_select_arm.py verify-freeze` 負責，本腳本只做下列檢查，任一不過即 SystemExit，不建 transport）：批 3 凍結收據存在且有全部必要鍵（`SELECTED_AGENT`、`code_commit_sha`、`prompt_and_config_sha256`、`params`、`formal_dry_run_estimate`、`scorer_sha256`），路徑為 `--receipt`，否則 `$E6_FREEZE_DIR/BATCH3_FREEZE.json`，否則 `<evidence root>/e6-batch3-freeze-20261127/BATCH3_FREEZE.json`；`SELECTED_AGENT` 合法；收據 `prompt_and_config_sha256`（`{路徑: sha256}`）中每個檔案的 SHA-256 都要等於目前 checkout 的檔案，否則 `FORMAL_PROMPT_SHA_MISMATCH`；`--arms` 必須恰好是 `DEANCHOR` ＋ 收據的 `SELECTED_AGENT`（AO_ORIG 由 `e5_run.py` 跑，不在此）。之後同診斷：估算 ≤ `--max-usd`、累計（38.17＋`<out>/ledger` 與 `--extra-ledger` 之新列＋估算）≤ 90，通過才付費。
- 輸出 `<out>/<case>/<ARM>.k1.json`…`k3.json`，其餘（原子寫入、PRECHECK／STATUS／MANIFEST、guard 拒絕立即停）同診斷；PRECHECK 記 mode 與收據 SHA-256。
- G6：`src/amidst/evaluation/e6_verdict.py` 的 `verdict_e6(segments, decision_points, selected_agent=…)`，只用標準庫，`e3_scoring.py` 未動（測試鎖 SHA-256）。
  - 輸入為評分端產出的逐段數字（`wrong_person_s`、`blind_false_lock_s`＝e3 `false_lock_s`、`lost_s`、`follow_rate`、`visible_ticks`）與逐決策點判分（`gt_regime`、`full_track_correct`、`single_correct`）；K 次重複可傳 list（秒數與跟對率取平均、決策點 K 多數決＝嚴格過半）。真值表輔助函式：`full_track_dp_correct`（§3.2 三情境）、`single_dp_correct`。
  - 以家族為單位彙整（秒數加總、跟對率按可見 tick 加權、決策點按點數）；N_dp ≥ 40 且 M ≥ 8，否則 `EXPLORATORY`（附 `verdict_if_formal`）。
  - P1＝DEANCHOR vs AO_ORIG，P2＝SELECTED_AGENT vs B1；C1–C4 IUT；元件 p＝家族層級符號翻轉（M ≤ 12 枚舉 2^M，否則 `random.Random(20261124)` 10000 次），p_h＝四者最大；伴隨 skew、配對 t（自寫不完全 beta，標準庫）、精確符號檢定與 `SKEW_SENSITIVITY_FLAG`（|skew| > 1 且 t 與翻轉在該假設的 Holm 門檻下結論不一致）；家族群集 bootstrap B=10000、seed 20261124，97.5%／95.0% 百分位區間；Holm 0.0125→0.025 正向（含 CI 邊界條件）與反向（四元件 Bonferroni）；否則 `INCONCLUSIVE`；P2 非 `SUPPORTED` 時 `must_report` 帶「改良後仍未證實優於現有規則」。另報分層（VISIBLE／FULL_BLIND＋TRUE_DEPARTURE）、`single_dp_acc` 與精確 McNemar（不併入 C3）、S5 較嚴盲區準則。
  - 測試（`tests/evaluation/test_e6_verdict.py`）涵蓋三情境真值表每個分支、多數決、符號翻轉精確值與 Monte Carlo、t 分布臨界值（2.593／11 df→0.0125、2.201→0.025）、Holm 閘門各分支、SUPPORTED／P2 INCONCLUSIVE／C4 與跟對率擋下／兩者 NOT_SUPPORTED／INCONCLUSIVE／EXPLORATORY（M<8、N_dp<40、邊界 M=8、N_dp=40）／偏態旗標／同家族合併／K 重複／輸入錯誤。

### verdict CLI（`scripts/evaluation/e6_verdict_run.py`；D402，未執行於真實資料）

`e6_verdict.py` 維持只用標準庫的純判定函式；讀 GT 與呼叫凍結評分器的部分放在評分端腳本（可以 import `e3_f4_score`／`e3_scoring`）：

```
uv run python -B scripts/evaluation/e6_verdict_run.py --frozen-spec configs/evaluation/e6_scenarios_frozen_v1.json \
  --gt-root <錄製根> --runs <B1 輸出根> <AO_ORIG 輸出根> <arms 輸出根> \
  (--selected-agent <組別> | --receipt BATCH3_FREEZE.json) --out <dir>
```

- `--runs` 接受任意個輸出根，每個根的 `<case>/*.json` 依 log 的 `arm` 分組（`AO`→`AO_ORIG`）；缺任何 case／組別即 `RUNS_MISSING` 停止；GT 檔以凍結規格的 `gt_sha256` 驗證（`GT_PIN_MISMATCH`），規格必須是 FROZEN；評分器為 SHA-256 `acacce39…` 的 `e3_scoring.py`（預設 `src/amidst/evaluation/e3_scoring.py`）。輸出目錄已有 `verdict_e6.json` 就拒絕。
- 每段取 `e3_f4_score.run_scores` 的 primary 指標（錯人秒、`false_lock_s`＝盲區誤鎖秒、`lost_s`、跟對率、可見 tick）；固定決策點以凍結規格的 `gt_regime` 與決策 tick 起 15 tick（3.0 s）窗，依 §3.2 真值表判 `full_track_dp_acc`（K 次逐點多數決）。`single_dp_acc` 需要另外的 K=1 共用先驗快照執行，2c 不產生，故不計（`single_correct=None`，UNKNOWN）。
- 輸出：`verdict_e6.json`（含 `data_quality`：各組呼叫數、provider 錯誤率）、`VERDICT_E6.md`、`scored_inputs.json`、`MANIFEST.sha256`。
- 驗證：離線測試用假逐 run 評分（`tests/evaluation/test_e6_verdict_run.py`）；另以真實評分器與本機 12 段凍結 GT 檔做過管線冒煙（各組全 LOST 的合成 log → 跑通、INCONCLUSIVE，未提交）。

## D403 消融（`--ablation none|NO_IMAGE|NO_SPATIAL`；**未執行**）

- 只作用在凍結收據的 `SELECTED_AGENT`，正式 12 段、K=3；付費時 `--arms` 必須恰為該組（診斷模式、K≠3、其他組合一律 `PAID_COMBINATION_REFUSED`／`FORMAL_ARMS_REFUSED`）。輸出檔名 `<case>/<ARM>+<ABLATION>.k<n>.json`，log 記 `ablation`。
- `NO_IMAGE`：請求不含任何影像（含種子參考截圖與每鏡頭畫面，`input_image` 與 `[frame …]` 標籤都沒有），變數文字、候選框、scene context、模型參數與 SELECTED 逐位元相同；靜態提示中提到影像的句子改寫或移除（`reference crop`、`TARGET REFERENCE`、`request frames`、`shown frames` 等），只留查詢條件 `a person wearing red`。
- `NO_SPATIAL`：保留影像（逐位元相同）、鏡頭 id、畫面內框座標；scene context 只剩 `{schema, identity, cameras:[{camera_id}]}`（拿掉區域／邊／鏡頭轉移與排除對／鏡頭位置 yaw FOV 足跡／重疊／來源／靜態幾何），提示中描述這些欄位的句子與 `Camera properties are in the scene context.`、`Scene edges do not certify…` 一併移除。現行 E6 請求本來就沒有平面座標或 `last_known_xy`（測試確認不含 `est_xy`／`last_known`／`ground`）。
- 預算：付費前重讀帳本（`<out>/ledger` 與 `--extra-ledger`），累計＋該消融上界 > 90（或上界 > `--max-usd`）→ 寫 `STATUS=BUDGET_SKIPPED`（附 PRECHECK、MANIFEST）並結束，**不縮 K、不縮段數**；非消融的 FORMAL 仍然 SystemExit。
- dry-run 分開估價：`--dry-run --ablation NO_IMAGE`／`NO_SPATIAL` 各自輸出（輸出含 `ablation` 欄位）；NO_IMAGE 因沒有圖片，估價（1,100 tokens／張）明顯較低。
- `e6_verdict_run.py --ablation-runs <root…>`：group 名 `<SELECTED>+<ABLATION>`；對 SELECTED 報家族層級配對差（消融−SELECTED：錯人秒與盲區誤鎖秒為加總、跟對率與決策點正確率為平均）與**未校正**雙側符號翻轉 p（M≤12 枚舉），一律標 `EXPLORATORY`、`in_holm=false`，不影響 P1／P2 判定（測試確認 hypotheses 逐欄相同）；`BUDGET_SKIPPED` 的根目錄列在 `ablations_skipped`；消融組別的基底不是 SELECTED 即 `ABLATION_NOT_ON_SELECTED`。
- **注意（凍結順序）**：`arms.py` 在 #741 的 `PROMPT_FILES` 裡，本 PR 修改了它（`ablation='none'` 的請求位元組不變，測試鎖定 prefix／variable-text 的 SHA），所以批 3 凍結收據必須在本 PR 合併之後產生，否則 `FORMAL_PROMPT_SHA_MISMATCH`。

### D403 補充核對

1. **`ablation=none` 位元組不變的證明**（K=1 診斷用 main `7dbb4ede` 跑，選組結果能套到正式組的依據）：把 `git show 7dbb4ede:src/amidst/live_mode/aopen/arms.py` 放到暫存檔，以 `amidst.live_mode.aopen.arms_old` 載入，與目前的 `arms.py` 在同一個行程、同一組假回答（含摘要）、`SCENE` 與含空間欄位的 `RICH_SCENE` 兩種 scene、三組各 3 次呼叫實算：
   - 完整請求 body（`json.dumps(sort_keys=True)`，含 base64 影像）逐呼叫**相同**（3 組 × 2 scene × 3 呼叫＝18 個 body 全相同），`prefix_sha256`、variable_text SHA、`body_sha256` 全相同；
   - 舊版輸出的 prefix／variable-text SHA 與測試黃金值一致：DEANCHOR `49b5bed0…`／`a4a012b3…`、DEANCHOR_HIST `abe31838…`／`e2381b84…`、DEANCHOR_HIST_SUM `f5c6e589…`／`e2381b84…`。結論 `ALL_IDENTICAL True`。
2. **`E6_EXTRA_NO_IMAGE` 與其他 NO_IMAGE 靜態文字改寫了哪些句子**（原文 → 改寫）：
   - `E6_EXTRA`：`Decide from the frames alone: compare every listed person with the TARGET REFERENCE crop (the original first-match crop) as if you saw this situation for the first time.` → `Decide from the listed detections alone, as if you saw this situation for the first time.`（其餘三句——不要因為自己或別人選過就當成目標、鏡頭固定順序、不確定就答 UNCERTAIN／NOT_VISIBLE——不變）。
   - `E6_SYSTEM_TEXT`：`…which detected person looks most like the same person as the reference crop.` → `…which detected person most likely is the person the user asks for.`
   - `E6_BASE`：`All request frames are 320x180 pixels.` → `Box coordinates are in a 320x180 pixel frame.`；`UNCERTAIN: you cannot judge from these frames.` → `…from these inputs.`；`NOT_VISIBLE: the person you look for is in none of the shown frames` → `…is none of the listed detections`。
   - 參考層文字：`TARGET REFERENCE (crop taken when the user's query "a person wearing red" was first matched). The reference crop follows.` → `TARGET: the user's query is "a person wearing red".`（查詢條件保留）。
   - 變數文字（偵測框、候選、`CAMERAS THIS CALL`）完全不變。
3. verdict 的消融比較除了家族集合，也比對**決策點 id 集合**與 SELECTED 相同（`DECISION_POINT_MISMATCH_ABLATION:<group>`）。
4. **與 #741 head `4ae04066` 的 run_all.sh 2c／2d／2e 對照**：2c `--cases … --arms "${AGENT_ARMS[@]}" --k 3 --paid --max-usd "${ARMS_BUDGET}" --baseline-json --receipt --out --extra-ledger …`、2d `--frozen-spec --gt-root --runs b1 ao_orig arms --receipt --out`、2e dry-run `--arms SELECTED --k 3 --ablation X --dry-run` 與 paid `--ablation X --paid --max-usd <budget-check max_usd> --receipt --out --extra-ledger`、探索性比較 `--ablation-runs <完成的根> … --out verdict-exploratory`，旗標名稱與參數個數都與本 PR 兩支 CLI 相容（`budget-check` 的 `max_usd` ＝ 估價上界進位到分，≥ 本腳本重算的上界，不會誤判 BUDGET_SKIPPED）。唯一建議：2e 的 `ABL_RUNS` 目前只收 STATUS＝COMPLETE 的根；若本腳本自己寫了 `STATUS=BUDGET_SKIPPED`（重讀帳本後超額），那個根不會傳給 `--ablation-runs`，`ablations_skipped` 就不會列出——不影響判定，只是報告少一行；要列出的話把 STATUS 為 BUDGET_SKIPPED 的根也加進 `--ablation-runs`（CLI 已支援）。
