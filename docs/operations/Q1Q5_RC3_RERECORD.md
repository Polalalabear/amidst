# D85 合併後：176 份新產品錄製與 rc3 交接

此入口只處理工程錄製更新。D85 產品修正由 #231 的既有 owner 負責；本工具不修改 API、契約、kit 或其測試。#231 必須先經 Claude 複核並合併，才能開始執行 `run`。不得自行合併以解除門檻。

## 固定範圍

| 包 | 既有 LOCAL 來源（`/Users/polalabear/amidst-artifacts/` 下） | FIRST_CALL 錄製數 |
| --- | --- | ---: |
| dynamic | `q1q5-dynamic-baseline-v1_20261025` | 8 |
| linked | `q1q5-linked-baseline-v1_20261024` | 8 |
| runner | `q1q5-baseline-runner-v1_20261024` | 160 |

原始 protocol SHA-256：`db6e11d5483470b27bac3c88794d8dc5f79177ab948c7d416e87b89906bcf634`。保留同題組、profile、一次 FIRST_CALL＋兩次 warm repeat、單 worker、60 秒 worker 上限、600000 µs engineering LOST interval，以及 D65 參數。交付為所有 FIRST_CALL 的 Q3 與 downstream stage，共 176 份；warm 樣本留在完整 LOCAL run。runner 保留 scripted、timeout、invalid、unavailable 四種 fixture，絕不算成真 LLM 成效。

dynamic／linked 重用凍結 prepared registry／索引，不跑 detector 或 render。新 runtime 只將 Q3／Q5 prompt bytes 更新成合併產品內的模板，重算模板與 runtime hash；model、digest、options、scope 與預算保持原值。原始 runtime、錄製、manifest 與資料不修改。每份交接另列新舊參數、時鐘、graph、索引／records 的 bytes hash；若新版 fixture context 改變，明列 `controlled_context_changed`，不能稱為僅單一因素的效能比較。

## 版本與執行門檻

- D85 修正提交祖先：`3a87bc5216c186d7f32c77be7fbc3d29118b907a`。
- #237 契約 merge 祖先：`83da40f075e7981b02b4b2150ccf0cf9128e4008`。
- `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md` 原 bytes SHA-256：`b700bf86041f4853ae37dd54bbc9d93199a07be3d5d3c87bc8c2f6455570df04`。
- #127 rc3 head：`b995fe8c5c314099b2a9c6111888a3cae917353b`。head 變動時停止，先核對新的獨立審查版本。
- `run` 即時讀取 GitHub #231：必須 MERGED、base 為 `codex/q1q5-staging`，且操作者指定的完整產品 SHA 等於其 merge commit；再檢查上述祖先與契約檔雜湊。Git 物件缺失時先 `git fetch --no-write-fetch-head origin <精確 SHA>`；不改 checkout／共享 index。
- 產製前、各 run／ZIP 前與結束後保留 `df -k`；剩餘少於 8 GiB 即停止。失敗產物保留，不覆寫或清理舊包。
- 模型只接現有 `127.0.0.1:11437`，先核對 tags 的 model／digest；不下載、不啟停 Ollama。執行前人工核對服務 owner／佔用；`background_load_controlled=false`，不能宣稱排除其他負載。

## 操作順序

所有路徑必須 canonical，輸出為新的 LOCAL 位置，完整錄製不得上傳 GitHub。範例中的 `TOOL_SOURCE` 指此 Draft 的精確 source export 目錄，`MERGED_PRODUCT_SHA` 由 #231 實際 merge 記錄填入，不能用未合併 head 代替。沿用現有 Python，勿建環境或安裝套件。

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-project --offline --no-cache \
  --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python python \
  "$TOOL_SOURCE/scripts/rerecord_q1q5_rc3.py" plan \
  --artifacts /Users/polalabear/amidst-artifacts \
  --output /private/tmp/rc3-rerecord-plan.json
shasum -a 256 /private/tmp/rc3-rerecord-plan.json
```

`plan` 只盤點與凍結原檔，不呼叫產品、模型或 kit。執行階段須填入剛才的完整 plan hash、已合併產品 SHA 與新輸出目錄：

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-project --offline --no-cache \
  --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python python \
  "$TOOL_SOURCE/scripts/rerecord_q1q5_rc3.py" run \
  --repo /Users/polalabear/Developer/amidst \
  --plan /private/tmp/rc3-rerecord-plan.json --plan-sha256 "$PLAN_SHA256" \
  --product-commit "$MERGED_PRODUCT_SHA" \
  --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python \
  --allow-local-model-calls --output "$NEW_LOCAL_OUTPUT"
```

工具從該 merge commit 匯出 83 個左右的限定程式／測試／prompt blobs，透過產品原有 `run_q1q5_baseline.py` 重新執行六個 run。實際 blobs 數以新 `COMPOSITION.json` 為準；不是混用舊 overlay。原 runner 的 `scope=ENGINEERING_COMPOSITION_NOT_INTEGRATED_PRODUCT`／`integrated_product=false` 為既有 adapter 欄位，不能據此聲稱正式資料驗收；新增 `source_product_commit` 記明單一合併產品來源。

若產品執行失敗、缺預期錄製、response 缺 `reasons[]`、link 非 v2 或缺 `matching_audit` 鍵，工具立即停止並保留證據。它不補寫 response／journal。新 bytes 複製成每包 `recordings/<id>/`，保存新舊 locator、context 差異與逐檔 hash，產出 `HANDOFF.json` 與 `claude-recordings.zip`。

## Claude 獨立驗證與 AC7

交付完整新 LOCAL 目錄、三包 ZIP、`PLAN.json`、`GATE.json`、`COMPOSITION.json`、`COMMANDS.json`、磁碟收據和 `MANIFEST.json`。GitHub 只貼精簡結果與 hashes，不上傳完整錄製、RGB、GT 或人工回收檔。

Claude 固定使用 #127 `b995fe8` 的 rc3 對全部 176 份重跑，不加 `--only`，不修改 kit 或錄製。每份將新 `recordings/<id>` 傳給 `--recorded`，其 `parameter_set.json` 傳給 `--params`；輸出寫入新的審查目錄。由 Claude 補充凍結且可信的 context；缺資料仍記 `INCOMPLETE`／`SKIPPED_NO_CONTEXT`，不能用假 context 換 PASS。

工具僅檢查 reasons list／journal 版本與輸出完整性，不代替 rc3 的原因優先序、hash、guard、schema 與完整契約判斷。結果必須分別報告三包 PASS／FAIL／SKIP、COMMON_REASONS_LIST、link v2／matching_audit、實際 provider 使用／fallback／timeout、剩餘缺 context；未量測正確性保持 null。無觀測仍是 GAP／UNKNOWN，身分 UNCONFIRMED，實體通行 UNKNOWN。

只有 Claude 完成獨立 rc3、AC7 相關檢查與必要缺漏處置後，才可評估 #127 合併；準備完成、176 份機械檢查或舊包結果均不是 AC7 PASS。

## 本次 focused 驗證

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-project --offline --no-cache \
  --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python python \
  -m pytest -q -p no:cacheprovider "$TOOL_SOURCE/tests/q1q5/test_rc3_rerecord.py"
uv run --no-project --offline --no-cache \
  --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python python \
  -m ruff check --select F,I,UP,B \
  "$TOOL_SOURCE/scripts/rerecord_q1q5_rc3.py" "$TOOL_SOURCE/tests/q1q5/test_rc3_rerecord.py"
```

2026-10-26：21 focused PASS；實際三包 plan 盤點 176 份、1669 個原檔 pins。D85 head 的限定 source export 為 83 blobs，runner/runtime 匯入通過；未啟動產品或模型，未產新錄製，未跑 rc3。當時 #231 仍為 OPEN Draft，merge SHA 為 null。
