# CQ-39-T（#336）：評分端；與推論隔離

只有六份合成回件控制：complete、wrong_manifest、tampered、missing、incomplete、environment_drift。原始的兩份輸出由 #364 的 SYNTHETIC 小資料構成，沒有真實組員資料、模型執行、原始資產或正式凍結收據。

每份目錄內有 test-only MANIFEST、原始凍結bytes、回件bytes、回件hash投影、case索引及private_script合成控制。`CQ39_TEST_PACK_V1`、`CQ39_TEST_RETURN_V1`、`CQ39_TEST_SCORING_INPUT_V1` 都不是正式schema／authority；不登記到架構守門。private_script只給合成expected hash，無真實GT。#335實作glue可將這些控制轉成已採用的原生評分輸入，但不能自行放寬正式規則。

## 反例差異

- wrong_manifest：回件指向f×64，與實際合成manifest SHA不符；必須拒收。
- tampered：complex輸出改為PARTIAL，回件仍保留原hash；屬完整性破壞，INVALID、不計分。
- missing：回件列complex檔案與hash，但實際檔案不存在；INVALID、不計分。
- incomplete：檔名有_INCOMPLETE，其他hash完整；照收並封存，不進正式分母。
- environment_drift：complex輸出同樣改為PARTIAL，但回件hash同步正確；與原始凍結bytes不同，必須ENVIRONMENT_DRIFT並列兩份結果。不能把漂移當成篡改，也不能覆寫我方凍結檔。
- complete：回件bytes完全相同；native回件計分須等於直接對我方凍結輸出計分的native結果。測試不自行編造一個「通過分數」。

## TEST-ONLY binding

設定 `AMIDST_TEAM_RETURN_MODULE` 為真實收件/計分模組（預設提議名 `amidst.evaluation.team_eval_return_scoring`），`AMIDST_TEAM_RETURN_DRIVER` 為測試glue，提供 `exercise(operation, *, implementation, **kwargs)`。這些名稱不是產品API。缺實作一般importorskip，AMIDST_REQUIRE_IMPL=1時CQ39_IMPLEMENTATION_MISSING fail；缺driver是CQ39_TEST_DRIVER_UNBOUND。strict不接受glue skip/xfail，壞import不吞成skip。

每次結果必有 `implementation_file_sha256` 與 `human_approval_verified=false`；test trace必須觀察到真正implementation檔的函式執行。glue只能映射原生欄名/呼叫介面，不能代做驗證、產生分數、回傳常數成功或自己造封存收據。

- `receive_and_score`：收到 `root`、`case`、`freeze_output`、`freeze_verified` callback與明示`test_profile`。它須呼叫真verify、真freeze，再接實作的Baseline v1／complex v2計分流程。完整/漂移須在封存後實際讀script；invalid不得讀。回status/score，INCOMPLETE回accepted=true與included_in_formal_denominator=false；漂移回frozen_score/returned_score及兩組output hashes。
- `score_direct_frozen`：直接經真scorer計算original資料，回非空score dict。不得轉用receive_and_score的cached分數。
- `score_without_freeze`：直接請真計分入口處理尚無回件封存的資料；須在開script前回INVALID／RETURN_NOT_FROZEN。

## 檔案順序觀測

測試audit hook鎖住給定private_script（含symlink別名）；封存前任何open都會失敗，並記錄premature計數。正常實作必須自行拒絕未封存的讀取，不靠測試丟例外偽裝產品拒絕。

真freeze完成後，glue把其收據/檔案欄位映射給 `freeze_verified(ref)`：receipt_path、receipt_sha256、files（原回件相對檔名→{path,sha256}）。這是測試觀測，不是新freeze契約。所有真封存檔案及receipt必須先實際存在於指定freeze-output內，不能是symlink；檔案bytes必須與測試先取得的回件快照相同。驗過後才允許讀script。callback不建立收據、不寫authority；不許glue以假的檔案代替原生freeze。

測試也在前後比較original凍結bytes，防止環境漂移路徑覆寫原輸出。Audit hook在finally停用，避免影響其他pytest案例。這是功能驗收觀測，不是針對惡意native程式的安全sandbox。

## 依賴到位後怎麼跑

先接真實glue，再照議題原命令：

```bash
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/evaluation/test_team_eval_return_scoring.py
```

## 實際結果

Model / effort：GPT-6（Codex） / UNKNOWN。六份fixture hash/缺檔/漂移差異及封存前讀script負控制共2個測試通過；7個native驗收因實作缺失一般skip／strict fail。**沒有任何組員回件已被正式接受或計分**。架構守門NOT_RUN（#307未交付）；#127 kit NOT_APPLICABLE（純test-first）。正式回件wire、freeze receipt、v1/v2 scorer整合與真實組員資料尚未驗證。
