> 2026-10-27 D92 更新：下方 rc3／rc4 準備段落為歷史；目前已完成 rc5 原生重錄 176 份，見本文末與新收據。#242 已由使用者合併，本次工具／結果另開 follow-up PR。

> D96／CQ-19：本次只補 rc5 追溯收尾，新增錄製 **0**。D92 v2 的 AC7 另待 CQ-15＋CQ-23 **實際合入 staging** 後，以獨立 PR 補 context、重錄與驗收；目前 **AC7=NOT_ACCEPTED**。

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

## G1 執行清單（2026-10-27，尚未重錄）

本節在 #257 合併前準備。#257 於本次核對仍 OPEN；不能自行合併解除 gate。Claude 已指出目前固定 rc4 不識別 tracking_scope.json，會額外產生 DOCUMENT_LOADABLE FAIL；不能移走 scope、使用 --only 或刪失敗檔假裝 AC7 通過。若 Claude／使用者後續採 rc5，先複核相容性、以新 commit 更新 KIT_COMMIT 與 gate、重產／pin plan；本次不更改固定 kit SHA，也不擅核新版本。

1. 核對 live #257 state=MERGED，base=codex/q1q5-staging，取得 mergeCommit.oid；其 head 若增加 commit，先同步 B1 常數並複核。保持 merge commit，不 squash/rebase/force。
2. 重讀本次工具 commit，核對契約／D85／B1 祖先、原案與模型 digest；kit head 必須符合工具 pin。確認本次 owner、既有模型服務與 df -k，free≥8GiB；不啟停其他服務。
3. 執行前述 plan 命令；應得到 expected_recordings=176，dynamic=8、linked=8、runner=160；記 plan 原始 bytes SHA-256 與全部 immutable_files pins。
4. 執行前述 run 命令，使用全新 canonical NEW_LOCAL_OUTPUT 與 exact MERGED_PRODUCT_SHA；一次 FIRST_CALL＋兩次 warm repeat，單 worker，原 60s worker 上限／D65。完整錄製留 LOCAL。
5. 預期新產物：各包全量 case.response.json、原生 links.jsonl（link-record.v2＋matching_audit）、decisions.jsonl（若 Q2 產生）、tracking_scope.json 與新 registry／scope migration receipts、原檔前後 pins／context delta、各包 delivery manifest／ZIP、總 RESULT 收據。工具根目錄明確產物為 PLAN.json、GATE.json、COMPOSITION.json、COMMANDS.json、STATUS.json、MANIFEST.json、df-before.json／df-after.json；各包 HANDOFF.json、claude-recordings.zip、recordings/{id}/；dynamic／linked 另有 MODEL_READY.json、SCOPE_MIGRATION.json、RUNTIME_MIGRATION.json、runtime.json。未產生前不能填 hash。
6. 驗證 Q1/Q3 resolved_scope.tracking_scope_sha256 鍵存在且值為 null；Q2 為 scope bytes SHA，所有 decision input_pins 相同；reasons[]、link v2 audit、8/8/160 份數、原 index／records／RGB／參數未改、原始檔 bytes/mtime 前後相同。失敗保留收據，不修補 response/journal。
7. 交 Claude 對三包全量 conformance，不加 --only，分包記 PASS／FAIL／SKIP；缺 context=INCOMPLETE，scope kind 問題未解就如實 FAIL。AC7 在完整當前產品驗證前保持 NOT_ACCEPTED。
8. 最後記本次新增 logical/allocated bytes 與 df free 差分（共享變動不能全歸因本次），每包 manifest／主要錄製／link journal 的 SHA-256 公開為 curated receipt，私人路徑／原錄製／模型 trace 不上傳。

### 本次實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: 延續 #242，精確 follow-up SHA 見 PR 留言。
- Files changed: 本文件、原 tool、原 focused test；Q1/Q3 null 檢查補嚴。
- Commands run and results: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src <EXISTING_PYTHON> -m pytest -q -p no:cacheprovider tests/q1q5/test_rc3_rerecord.py`：27 PASS；`git diff --check` PASS。
- Artifacts: 尚無新錄製、links journal 或新結果收據；fresh_recordings=0。
- Verified: G1 指令／預期產物／檢查表已具體化；Q1/Q3 非 null scope pin 會遭拒。
- Not verified: #257 合併後三包重錄、真模型、scope-kind 新 kit、AC7。
- Deviations, UNKNOWN items and follow-ups: #257 未合併與 rc4 scope kind 缺口均明列；不得因本清單已交就宣稱 G1 已完成。


## D92／rc5 同步（2026-10-27）

#257 已用 merge commit `c1d9cbda51872de839a9c61a5b3b70ae8ff4e0f1` 合入；
`B1=b761a336c75879870a1e5e748fa032461f4d35d2` 已確認仍為祖先，無須改值。
本工具的 `KIT_COMMIT` 更新為 rc5 `4e3edfcf3fb984f590ce5d2af2e6b44a9cd7500c`；
後續 head 有任何變動仍以 `KIT_HEAD_CHANGED_REVIEW_REQUIRED` 停止，沒有移除 exact-head gate。
契約 pin `b700bf86…df04`、176 份 FIRST_CALL、D65、單 worker 與兩次 warm repeat 不變。
本次重錄固定使用上述 #257 merge 的 v1 response 產品，與尚未合併的 D92 response v2 實作分開；
不能把 rc5 的單一合成夾具 PASS 176 說成三包 176 份錄製已通過。

rc5 檢查 tracking_scope 原始 bytes pin、兩圖 input pin 與 Q2 response pin。
三包執行後在本 PR 附新 LOCAL artifact／manifest／ZIP SHA、完整命令與三包檢查數；
Claude 獨立完整複核前 AC7 仍為 NOT_ACCEPTED。


## I4 實際重錄與 rc5 全量自檢結果（2026-10-27）

產品固定 #257 merge `c1d9cbda51872de839a9c61a5b3b70ae8ff4e0f1`；kit rc5 `4e3edfcf3fb984f590ce5d2af2e6b44a9cd7500c`。
未混用尚未合併的 D92 v2 response。全部 1,669 份舊輸入／錄製 bytes＋mtime 在結束再次核對一致。

| 包 | 新 FIRST_CALL 錄製 | kit recording overall | check PASS | SKIPPED_NO_CONTEXT | FAIL | link-record.v2 rows |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| dynamic | 8 | 8 PASS | 1684 | 4 | 0 | 194 |
| linked | 8 | 8 PASS | 745 | 4 | 0 | 16 |
| runner | 160 | 160 PASS | 14751 | 80 | 0 | 200 |

88 個 SKIPPED_NO_CONTEXT 都是 Q1_SUPPORTED_SET_CONSISTENCY 缺 supported-classes context；
固定產品 export 未提供該檔，未補造，這部分保持 **INCOMPLETE**。kit 的 recording overall PASS 不等於 context 完整或 AC7 核准。
真本機模型 Q3 12 次、Q5 6 次呼叫全 timeout，used=0；fallback 不算 LLM 成功。runner 四個 fault modes 仍為 test doubles，分開列示。

完整錄製、manifest、原 metadata／argv、rc5 每份報告與 ZIP 均 LOCAL：
`<LOCAL_ARTIFACTS>/q1q5-rc5-rerecord-20261027-d92` 與同名 `-validation`。
公開收據：`docs/history/Q1Q5_RC5_RERECORD_RESULTS_20261027.json`，包含三 ZIP、manifest 與 validation summary SHA-256。
獨立 Claude 全量複核仍 PENDING；**AC7=NOT_ACCEPTED、accuracy=null、formal_acceptance=false**。

### CQ-19：逐份 run／clock 的追溯入口

逐份資料在 **LOCAL manifest**，公開收據 `packs.<pack>.run_clock_traceability` 列出入口與核對結果。
根 `MANIFEST.json` 的原始 bytes SHA-256 為 `7497ecde3556c3e1edea4e73c91c4e159f5d4d863fc04885b86ab9fb920c544c`；
`<pack>/HANDOFF.json#/recordings` 將每個 id 對到 `<pack>/recordings/<id>/`，
其中 `clock_mapping.json` 提供 run_id／clock_id／content_sha256，`case.response.json` 提供
resolved_scope.run_ids／clock_ids／clock_mapping_sha256，兩檔的原始 bytes pin 同時列在 HANDOFF 與根 manifest。

本次唯讀核對 176 份、355 個 metadata 檔（3 個 HANDOFF、176 個 clock、176 個 response），
每份 raw-file pin 與 response↔clock 綁定皆一致，讀取前後 bytes 未變：

| 包 | 份數 | run_id | clock_id |
| --- | ---: | --- | --- |
| dynamic | 8 | ENGINEERING_DYNAMIC_RUN_20261025 | ENGINEERING_DYNAMIC_CLOCK |
| linked | 8 | SYNTHETIC_RUN | SYNTHETIC_CLOCK |
| runner | 160 | SYNTHETIC_RUN | SYNTHETIC_CLOCK |

這是 provenance 核對，未重跑 kit／模型或重錄，不能補掉 88 個 SKIPPED_NO_CONTEXT，也不構成 AC7。
新工具的 `tracking_scope_rc5` 與 `PR257_MERGED_EXACT_PRODUCT_AND_KIT_RC5_HEAD_REQUIRED` 是新產製用的名稱；
歷史 plan、registry、錄製與其 `tracking_scope_rc4` reference／manifest bytes 一律保留。

AC7 後續須依 #300：CQ-15 與 CQ-23 實際合入 staging 後，另開 PR 補 supported_classes.json context、
以 v2 產品重錄、解決 timeout 或明定 LLM 測試範圍，再由 #127 做獨立 AC7。
在此之前，舊 176 份仍是固定 c1d9cbd v1 產品的歷史工程證據，context=INCOMPLETE、LLM_used=0、accuracy=null。

## 實際產出 / Actual output（本次 rc5）

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: #242 已合併 `d6a9e21`；本次另開 rc5 follow-up，精確 head 見 PR。
- Files changed: rerecord tool、focused test 的 kit gate error、本文、新 rc5 結果收據；舊 rc3／rc4 JSON 不改。
- Commands run and results: 同上固定 plan/run flags；27 focused PASS；6 個產品 run 命令 returncode=0；176 份完整 rc5 checks（無 --only），逐包數字如上；git diff／lint 見 PR。
- Artifacts: 三 ZIP／原始錄製與完整 reports LOCAL，SHA-256 見新收據；原資料／模型服務不改、不渲染、不跑 detector。
- Verified: exact merge／祖先／contract／kit gates、scope raw bytes pins、link-v2、原輸入 pin／mtime、全部新錄製與完整 rc5。
- Not verified: Claude 獨立複核、AC7、正式研究／真實身份／物理通行／HTTP-browser；D92 v2 不是本批錄製產品。
- Deviations, UNKNOWN items and follow-ups: supported-classes context 缺口 INCOMPLETE；18 次 timeout、LLM_used=0；不把 kit PASS 或 fallback 升格。
