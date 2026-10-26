# B2 rc4 重錄：B1 合併門檻與原生 scope 輸出

2026-10-27。本次只更新工程重錄工具；**B1 [#257](https://github.com/Polalalabear/amidst/pull/257) 尚未合入，fresh_recordings=0，AC7=NOT_ACCEPTED**。2026-10-26的兩份history JSON保留歷史量測／artifact hashes，僅把private locators改為公開佔位符，不能把舊176份結果算成這次已重錄。

## 固定範圍與 gate

三包dynamic 8、linked 8、runner 160，共176份FIRST_CALL；同題組、profile、一次FIRST_CALL＋兩次warm repeat、單worker、60秒worker上限與原D65。runner scripted/timeout/invalid/unavailable四fixture獨立標示，不算真LLM成效。不render、不跑detector，不改RGB／原index／clock／params或舊錄製。

`run`即時要求#257已MERGED、base=`codex/q1q5-staging`、指定product SHA等於該merge commit，且包含B1、D85與#237祖先。契約bytes SHA固定`b700bf86041f4853ae37dd54bbc9d93199a07be3d5d3c87bc8c2f6455570df04`；kit固定#127 rc4 `c4e96979ad559d73cbd6a265e905100a1cf7f4f9`，head變動則停下核對。不得自行合併以解除門檻。

新產品helper另產engineering scope檔與新registry，更新兩圖scope inputs與pins，逐項列context差異；原index／records bytes維持原pin。runtime只更新合併產品的prompt模板。完整source export綁單一merge commit，沒有混用未合overlay。scope原始檔隨每份domain export交付；不能補寫response或journal。

機械檢查要求：Q1/Q3 nullable `resolved_scope.tracking_scope_sha256`鍵；Q2非null且等於scope原始檔bytes hash、每筆decision的input_pins一致；全部reasons[]；link-record.v2及matching_audit鍵。這些不代替完整rc4／AC7。

## 操作（所有locators均LOCAL）

操作者明確設定`EXISTING_PYTHON`、`LOCAL_ARTIFACTS`、`REPO`、`LOCAL_PLAN`、`TOOL_SOURCE`、`NEW_LOCAL_OUTPUT`為既有／新canonical路徑，不建環境。先產plan並記完整SHA：

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-project --offline --no-cache \
  --python "$EXISTING_PYTHON" python "$TOOL_SOURCE/scripts/rerecord_q1q5_rc3.py" plan \
  --artifacts "$LOCAL_ARTIFACTS" --output "$LOCAL_PLAN"
shasum -a 256 "$LOCAL_PLAN"
```

待B1實際merge後，再設定`MERGED_PRODUCT_SHA`與`PLAN_SHA256`：

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-project --offline --no-cache \
  --python "$EXISTING_PYTHON" python "$TOOL_SOURCE/scripts/rerecord_q1q5_rc3.py" run \
  --repo "$REPO" --plan "$LOCAL_PLAN" --plan-sha256 "$PLAN_SHA256" \
  --product-commit "$MERGED_PRODUCT_SHA" --python "$EXISTING_PYTHON" \
  --allow-local-model-calls --output "$NEW_LOCAL_OUTPUT"
```

只用既有loopback `127.0.0.1:11437`與原model/digest/options，不下載、啟停服務。執行前核對owner與disk；各run／ZIP前及結束記df，<8GiB停止。新output不存在才可產製，舊檔bytes／mtime pins前後核對，失敗證據保留。新資料夾logical bytes與全碟free差分分開報告；共享負載未控制，不能全歸因本任務。

完整錄製、原始metadata與argv留LOCAL。GitHub只交code/docs/tests／curated receipt／hash；公開history的placeholder不改LOCAL檔或其artifact hash。Claude以固定rc4對全部176份重跑，不加--only、不改kit／錄製，缺context仍INCOMPLETE。三包分別報PASS/FAIL/SKIP與剩餘問題；未量測正確性保持null，G4／身分／通行不升權。

## 實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: 延續Draft #242；精確新head見PR。
- Files changed: 原tool、focused tests、本文、兩份歷史JSON locator遮蔽；新增B2準備收據。
- Commands run and results: 離線uv/Python `pytest -q -p no:cacheprovider tests/q1q5/test_rc3_rerecord.py`：25 PASS；變更tool/tests `ruff check --select F,UP,B` PASS；`plan`盤點176份舊錄製；公開docs `rg`無私人絕對路徑；`git diff --check` PASS。
- Artifacts: 新LOCAL plan（pin／原檔數見準備收據）；沒有新錄製。歷史量測留在標示日期的rc3 RESULTS收據。
- Verified: 未合gate先停、exact merge/ancestor/contract/kit檢查；scope migration保留原index/records、舊檔pins；Q1/Q3缺key及Q2 null/wrong pin遭拒；原生link-v2檢查保持。
- Not verified: B1合併後真模型三包重錄、實際migration全流程、Claude完整rc4／AC7、HTTP/browser／G4／正式r004。
- Deviations, UNKNOWN items and follow-ups: 本次B2尚未完成，依使用者明定「B1合入後」守住依賴；不能用未合產品或舊176份冒充重錄完成。
