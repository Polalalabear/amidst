# CQ-29-T：合成主包回件測試

此目錄說明 #321 的 runtime fixtures；實際 bytes 由 `tests/q1q5/test_yyin_main_pack_return.py` 在 pytest 暫存目錄產生。沒有實際 yyin 回件、影像、GT、formal／clean bytes、私人路徑或正式題庫。

## 現在可重跑

```sh
uv run python -m pytest -q tests/q1q5/test_yyin_main_pack_return.py
```

沒有主包 orchestration driver 時：13 個既有 importer 檢查 pass；27 個完整主包測試 skip。這些 skip 不是主包驗收通過。

## 依賴到位後怎麼跑

主任務指定的嚴格命令逐字如下：

```sh
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/q1q5/test_yyin_main_pack_return.py
```

目前主包 orchestration 尚未存在，因此該命令會有 27 個明確的 MISSING failures；13 個現有 importer 檢查仍 pass。不得用 dummy driver 把缺失變綠，也不能用正常模式的 skip 宣稱 #320 驗收。

#320 實作後，測試擁有者可以提供只供驗收的 adapter 模組，然後設定：

```sh
AMIDST_YYIN_RETURN_TEST_DRIVER=<test_adapter_module> AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/q1q5/test_yyin_main_pack_return.py
```

adapter 必須宣告 `TEST_ONLY = "SYNTHETIC"`；`probe_return(**kwargs)` 接收測試產生的 `pack`、`manifest_sha256`、`s2_csv`、`s1_csv`、`s0_csv`、`expected_s0_sha256`、`output`，呼叫真正的驗證／匯入流程，再投影出測試斷言視圖。這些 Python 參數與視圖 keys **不是新的 production receipt／schema／authority**。沒有自動探測、未核格式 fallback 或正式輸入 decoder；未提供 adapter 就按 test-first 規則 skip／fail。

視圖中的 `raw_verify_status` 保留實際驗證器原值；`receipt_status` 是 #321 要求的結果層。#240 草案說完整驗證器輸出 VERIFIED，#321 完整收件寫 VALID，測試分別要求兩者，不把字串默默視為同義。兩層正式 receipt 格式與映射仍 UNKNOWN，須由 #320 真實實作／核定後在 adapter 明示；本檔不採用新 mapping。

## 案例與已驗證界線

- 既有 staging importer 的 13 個 probes：有／無 BOM 與 LF／CRLF 的原文保留、MANIFEST／CSV raw SHA、沒有精確標註時 14 列明確 PRECISE_HUMAN_ANNOTATION_REQUIRED、所有輸出不含 importer 自產 query_sha256、六種公式前綴不被加 apostrophe 改寫、缺列／重複 ID／固定檔被改拒收。公式前綴的 decoder 保留測試不代表阻擋已實作。
- 待實作的 27 個 probes：完整（s1 五個合法選項）、_INCOMPLETE、各只缺一種 template、固定檔改動／多檔、BOM、六種公式前綴阻擋與記錄、缺列／列順序改動、非法 s1 單列（其餘照收）、s0 hash 相符／不符／缺件。未完整 s2 不進正式分母；缺 template 只列 warning／待決，未依來源 pin 補回並重驗前不得當完整匯入。
- fixture 沿用既有 `team-review-pack.v1` 與原 TEXT_COLUMNS／REVIEW_COLUMNS，版本刻意是 v0-pilot、evaluation_eligible=false；不產生正式答案。主包 s1 真正 CSV 尚未定版，fixture 的三欄只作 test-driver 視圖，不是新增正式 CSV 欄位。14 列只承載明示 SYNTHETIC 流程文字及型別，不是給組員的例句或已核精確標註；基本型別安排涵蓋 A／B／C／D／E 與 Q1 附加結果，實際配額驗證仍待 driver。
- D98-1／#347 的真實 `RETURN/s0_templates_審查表.csv` 必須比對原 pin `d9bc71e32e4659d3678857202d1e45b512300cc8f0b67bb922a767b18b4babf7`。測試只用自己產生的 SYNTHETIC s0 bytes／對應 test pin，**沒有讀取或宣稱補回 10-25 原模板**；缺件／不符不得自動接受。

直接被測 code 固定於 staging `434e57922a24d2422226871c0bb672dc7bc3584b` 的 `scripts/import_team_review_pack.py` 與 `scripts/build_team_review_pack.py`，沒有修改。格式規則參考 #240 修正 head `2938bbb4ba875de0723004bd7a248ebc32bec536` 的 §3.1、§3.3、§5、§7（已交件、未經 Claude 複審），不把 PROPOSED 文件升成已核 authority。

沒有新增 `scripts/check_*.py` 或偽造 production implementation。#307 未交付，架構守門 NOT_RUN；沒有新增實際 recorded 輸出，#127 kit NOT_RUN。真實回件、發包、精確標註／query_binding、s1 答案升權或改圖都不在本 -T 範圍。
