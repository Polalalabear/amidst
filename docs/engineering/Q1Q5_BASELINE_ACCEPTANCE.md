# Baseline 前置：一次驗收入口

2026-10-24，Refs #200。工程交付可依下表一次驗收；正式 baseline 仍受明列的人審/契約/資料凍結阻塞。各項完成即發布 Draft，沒有合併 staging/main/mainline。

| 原工作項 | 交付入口 | 實際結果與限制 |
|---|---|---|
| 最小規格/JSON | PR #193、Q1Q5_BASELINE_V1_PROTOCOL.md、baseline_v1_protocol.json | 已固定格式/變因/指標；正式pins不猜填 |
| 執行/對照/timeout/replay | PR #195、run_q1q5_baseline.py；本項 source/registry exporter | 原240合成樣本/480重播為歷史#195證據；本項最終真Qwen原預算12樣本/24 stage replay一致，Q3 6/6 timeout、Q5 3/3 timeout，LLM採用0。RULE接手不能算模型成功 |
| 延遲/記憶體/呼叫/事件 | 每筆telemetry、raw audits、journals、flags | 首回/暖呼叫、Q3/Q5、wall/CPU/caller lifetime peak RSS分列；未量fps/模型RSS/VRAM/accuracy保留null。真RT smoke兩張新合成PNG，模型載入/完整index build分列，不稱純inference fps |
| API/工作台/產品契約 | PR #195歷史7流程；本項Q2 publication race修正 | 固定source上83 focused PASS；修正後publication/API/runtime70 PASS（重疊不相加）。#189原證據/4 strict XFAIL不回改；新source另有barrier測試證明只執行一次。其他契約見決策表 |
| 正式產製預檢 | PR #197、r004_production_v1.json、新pinned index入口 | 27 focused PASS；14個正式欄位未凍結，prepare為BLOCKED/exit2。未產正式RGB/index，不改原審查包 |
| 最小Q3前置 | PR #199、Q3_MINIMUM_V1_REVIEW.md/CSV | 8題/8類候選bytes已固定；AI草稿、formal_rows=0。空白獨立expected表供本次一次審核，未讓受測Qwen答題/出答案 |

公開精簡數字與檔案pins見 `docs/history/Q1Q5_BASELINE_PREPARATION_RECEIPT_20261024.json`。LOCAL持久交付為 `~/amidst-artifacts/q1q5-baseline-acceptance-v1_20261024/`，先讀根README；原#195包及正在審的yyin包保持原版。raw audit/完整測試錄製/新合成PNG不公開到GitHub。

## 重建與重跑

`configs/q1q5/baseline_v1_sources.json` 是504檔的完整code composition：每檔commit/SHA-256，以及四份append-only CSS的輸入/結果hash。刻意排除manifest本身與最後驗收文件以避免自我引用；它們由本PR提交及公開收據固定。缺Git object就失敗，需先正常fetch所列提交；工具不fetch、不切checkout、不建worktree、不讀原資產。

在現有repo指定 `Q1Q5_REPO`、新的repo外 `Q1Q5_SOURCE`，以及現有 `Q1Q5_PYTHON`。先重算manifest的file SHA-256（固定值見公開收據），執行：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$Q1Q5_REPO/src" \
uv --no-cache run --no-project --offline --python "$Q1Q5_PYTHON" \
python "$Q1Q5_REPO/scripts/prepare_q1q5_baseline_source.py" \
  --repo "$Q1Q5_REPO" \
  --composition "$Q1Q5_REPO/configs/q1q5/baseline_v1_sources.json" \
  --composition-sha256 "$Q1Q5_COMPOSITION_SHA256" --output "$Q1Q5_SOURCE"
```

沒有Ollama也能依 `Q1Q5_BASELINE_RUNNER.md` 的 `--fixture scripted|timeout|invalid|unavailable` 跑完整控制與錄製kernel replay。要測既有本機服務，先用唯讀/api/version、/api/tags、/api/ps核對版本/digest/服務負載，禁止自動下載、預載、卸載、重啟或調寬預算：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$Q1Q5_SOURCE/src:$Q1Q5_SOURCE/tests/q1q5" \
uv --no-cache run --no-project --offline --python "$Q1Q5_PYTHON" \
python "$Q1Q5_SOURCE/scripts/prepare_q1q5_synthetic_registry.py" \
  --output "$Q1Q5_NEW_INPUT" --base-url "$Q1Q5_BASE_URL" \
  --model-digest "$Q1Q5_OBSERVED_DIGEST"
```

此generator只產兩個既有機械控制字串、假RT觀測和真runtime metadata，零HTTP；不讀#199八題或expected。再用原baseline CLI指定新輸出的registry/runtime/cases及各file pins、`--synthetic --allow-local-model-calls --worker-timeout-ms 60000 --lost-after-us 600000`，輸出另一個新目錄。完整本輪argv在LOCAL `RUNTIME_COMMAND_RELEASE.json`；歷史TMP路徑只作當時記錄，搬移後重跑要新建registry並重算file pins，不能默用舊locator。

60000ms是外層worker防掛死，600000us是synthetic事件控制，均不更改Q5 call2000/total5000或正式LOST期限。首回不是保證冷模型，暖重複也不是已證明模型常駐；client timeout不保證server立即停止。真Qwen原預算未成功是本次限制，沒有長診斷冒充baseline通過。真RT兩張PNG smoke與Qwen機械索引smoke分開，尚未做正式RGB的完整模型組合成效。

## 原版符合性與正式啟用

原#127 @994d34c的工具/schema bytes已核對未改。最終實機smoke的8份FIRST_CALL兩stage錄製全套、無--only，604 PASS/27 FAIL/11缺context，overall FAIL；不是24次重播的分母，也不與#195的160份/505FAIL合計。完整FAIL交#145，由獨立owner處理，不刪D69欄位、補假journal或偽造digest。

正式啟用前，依 [決策與核定清單](Q1Q5_BASELINE_DECISIONS.md) 一次核對程式交付、契約選項、Q3獨立expected與圖/ROI/必要HSV收據。yyin回收需要CSV、問題/不確定/未完成清單及完整folder/ZIP；yyin審完不能代替Claude或必要HSV核定。核定/程式前置→凍結→正式A4/B4 RGB→index→查找/持續追查baseline→輸出凍結→人工評分。沒有提前產正式資料或修改原資產，accuracy=null。
