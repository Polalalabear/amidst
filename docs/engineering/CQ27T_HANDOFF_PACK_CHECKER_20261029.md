# CQ-27-T 交接包機械檢查

`scripts/check_handoff_pack.py`（`cq27t-synthetic-v1`）是可獨立使用的標準庫
唯讀工具。使用既有 `team-review-pack.v1`、原有 TEXT／REVIEW 欄名與
editable_files，不修改 builder／importer／權威文件。`VALID` 只代表指定
範圍的機械檢查通過，不核定來源、人類回件、評測資格或發包。

預設 extended profile 為 UNSELECTED，未提供外部 profile 選項 bytes pin
及 MANIFEST bytes pin 時拒絕。任何結果都固定回傳
`human_approval_verified=false`、`evaluation_eligible_verified=false`、
`release_authorized=false`、`production_profile=UNSELECTED`。

## 依賴到位後怎麼跑

#318 的逐字命令如下。Python 實際操作用 `uv run python`。正式 extended
profile 尚未選定時，前兩個命令預設 fail closed。

```sh
python scripts/check_handoff_pack.py --pack <LOCAL 主包 ZIP> --profile yyin-main
python scripts/check_handoff_pack.py --pack <LOCAL 評測包 ZIP> --profile team-eval
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/q1q5/test_yyin_main_pack.py tests/q1q5/test_check_handoff_pack.py
```

明示機械範圍的用法：

```sh
uv run python scripts/check_handoff_pack.py --pack <資料夾或ZIP> --profile yyin-main --manifest-sha256 <MANIFEST完整bytes SHA> --profile-options <外部選項JSON> --profile-sha256 <選項完整bytes SHA>
```

選項是 TEST-ONLY `SYNTHETIC_HANDOFF_PROFILE_V1` 投影，包含 profile、
readme、text_ids、zip_timestamp、return_names 與合成 s1 CSV 的 filename／
template_ref／columns／row_ids。欄位名稱及 s1 synthetic headers 只作檢查
介面，不採用為正式主包或評測包 wire。`team-eval` 尚未驗完整執行／回收
流程，不能用合成投影冒充該流程已核定。

明示 `phase=S2_FRAMEWORK_ONLY` 時，只驗既有 manifest／s2／README／禁止
內容與封裝機械條件，return_names 僅需 s2；回傳 validated_scope 同名。
它不要求捏造尚未加入的 s0／s1。完整 s1＋s2 合成 case 用
`phase=S1_S2_SYNTHETIC`（預設）；s1 CSV 欄名仍由明示測試選項提供。
所有範圍的 s0_status 固定 UNSELECTED。D98-1 的 s0 另由 #347 處理，
本工具沒有把未完的主包標成可發包。

## 檢查內容

- 資料夾與 ZIP 都拒絕 symlink、非正規路徑、非 NFC 名稱、重複／大小寫
  衝突、額外檔案及漏檔；每檔最多 4 MiB、共 32 MiB／2000 entries。
  `.DS_Store`／`__pycache__` 不得出現在包內。ZIP 不解壓或執行其中程式，
  同時核對 non-ASCII 名稱的 central／local UTF-8 bit 0x800、實際 UTF-8
  名稱與明示固定時間戳。合成測試另在新暫存目錄解壓，核對完整名稱集合，
  以及固定輸入兩次 ZIP bytes 相同；不保證跨封裝環境 bytes 一定相同。
- MANIFEST 本身用外部 pin 核對，其餘每個 immutable 檔案逐 bytes SHA。
  只有缺 `templates/情境.csv`／`templates/審查表.csv` 可回
  VALID_WITH_WARNINGS，逐項列 TEMPLATE_MISSING。缺其他模板、改 hash、
  多檔、symlink、CSV 表頭或編號不符均 INVALID。新建包不能將 warning
  當作交付通過；正式匯入前須從可信原包補齊模板。
- 固定表與 templates 保留既有 TEXT／REVIEW headers，review 只有表頭、
  `samples: []`。s2 row IDs 由明示 options 釘住，不能從變更後 CSV 反推。
  `--returned-csv` 可另外驗回交 CSV header／IDs，不修改原包，不產答案。
  未列出的 RETURN payload 仍會拒絕；完整回收／可變檔案擴充交 #321／#293。
- README 檢查工作內容、要提交項目、操作、不要改、s1／s2、確切回交名與
  _INCOMPLETE。S2 framework 範圍不假造 s1 回交完成狀態。
- 包內所有可解碼文字均掃描內部事件 token、評分窗欄名、內部檔名與私人
  locator 樣式。JSON／JSONL 另掃 decoded 巢狀 key／string，避免 Unicode
  escapes 藏住被禁止的資料。掃描不排除 maintainer 或 tools；工具的 token
  常數分段組裝，讓獨立副本也可接受同一全包掃描。二進位 bytes 沒有做
  OCR、metadata 完整解析或隱寫分析，不宣稱完整資訊洩漏證明。
- 合成 `tools/verify_pack.py` 是本工具的獨立副本，測試以 Python -I 跑
  VALID／VALID_WITH_WARNINGS／INVALID。主 checker 不執行外來包的 verifier。
  既有 importer 以合成 s2 CSV＋一列明標 SYNTHETIC 精確 annotation 實跑：
  header-only review 模板相容，沒有讀原影像或推導答案。

## builder 驗收與尚未完成項

`test_check_handoff_pack.py` 是 checker 自測；`test_yyin_main_pack.py` 是
#317 的獨立驗收。後者呼叫
`build_pack(output, inputs=..., synthetic_only=True)`；只有明示
`AMIDST_YYIN_BUILDER_INPUTS=<LOCAL SYNTHETIC config>` 才執行。
缺實作正常 importorskip，AMIDST_REQUIRE_IMPL=1 改為 fail；缺明示合成
inputs 也不自行發明。測試檢查既有 wire、S2_FRAMEWORK_ONLY、release=false、
兩次 ZIP bytes 與 UTF-8/NFC 名稱，不替 #317 寫 production builder。

clean staging 未含 #317，應保留缺實作紅燈；另可在 TEST-ONLY paired tree
接入其 exact head／本機已記 SHA 的候選再驗證，兩組結果必須分開報告。
不執行原資產、模型、render、完整 suite、#127 kit 或發包。#307 尚因
authority pin 衝突 blocked-user，架構守門 NOT_RUN。
