# CQ-14-T 合成評測包輸入（#334）

本目錄只包含兩份很小的 SYNTHETIC 凍結輸出及一份 test-only RETURN 範例；不是正式Baseline／Line2資料或可發送的評測包。沒有原始資產、GT、劇本、評分窗或私人絕對路徑。D96-2只授權重播我方凍結輸出，不在組員端下載權重或執行模型。

`inputs.SYNTHETIC.json` 的兩個輸出各附精確 bytes SHA。完整包的重播結果必須逐bytes相同，不能只比較JSON解析結果。RETURN範例 `pack_manifest_sha256=000…000` 是明確假控制；不是任何真包的pin。

## 尚未核定的介面

`team-eval-return.v1` 在 #334 明列「提議」，#307 registry又尚未交付。本任務沒有新增正式schema/registry。`CQ14_TEST_RETURN_V1` 與範例欄位只是驗收投影；`test_profile=None` 必須CONTRACT_UNSELECTED，不能憑schema字串升權。待正式契約採納時，#293需接回既有架構守門；本測試不替人決定欄位名稱。

## TEST-ONLY glue（#293實作到位後）

`AMIDST_TEAM_EVAL_MODULE` 是真實builder/verify模組（預設提議名 `amidst.q1q5.team_eval_pack`）；可設成實作採用的模組路徑。`AMIDST_TEAM_EVAL_DRIVER` 指向glue，提供 `exercise(operation, *, implementation, **kwargs)`。名字不是產品API；glue只作資料/欄名轉接，不得實作假builder、回傳常數VALID或代做重播。

每次操作結果都有 `implementation_file_sha256`、`human_approval_verified=false`；trace須觀察到真實implementation模組的函式呼叫。缺實作一般importorskip、strict fail；未綁driver則TEST_DRIVER_UNBOUND；strict不許glue skip/xfail。glue壞import不能吞成缺實作。

- `build`：以 `output`、`inputs`、明示 `test_profile` 呼叫真builder。回 `root`、`manifest_sha256`、`release_authorized=false`、`entrypoint`、`entry_args`、`return_path`、`replayed_files`（BASELINE/COMPLEX各一）、`optional_template`、`immutable_probe_file`、`readme`。所有路徑除root外是包內相對路徑，不能含..／symlink。entry_args是執行入口的實際CLI參數。
- `validate_return`：用包的真驗證器核對return及manifest，回status與observations（pack_manifest_sha256/environment/output_sha256）。observations只映射原生欄名，不補實作沒有的欄位。
- `return_missing_field`：將範例轉成所選測試wire，再逐一刪掉對應原生pack manifest/environment/output hashes欄位，交真驗證器；必須INVALID。
- `validate_unselected_return`：不選test profile，真驗證器須拒絕未核契約（reason_category=CONTRACT_UNSELECTED）。
- `verify`：真verify結果映射VALID、VALID_WITH_WARNINGS、INVALID；missing template須附TEMPLATE_MISSING原因。測試自己刪template／改immutable payload，不由driver代造情境。

## Python與離線測試

優先尋找python3.12；當pytest本身已是3.12時，可使用它的實際executable。若兩者都無，一般skip/PYTHON_3_12_NOT_FOUND，strict fail。真正包的入口必須在空cwd以 `python3.12 -I -c <audit bootstrap> <包入口> <參數>` 執行；bootstrap只加audit hook再runpy真入口，並斷言sys.flags.isolated=1。它不替包補repo import路徑；PYTHONPATH故意指向repo也應被-I忽略。

socket.*和child process啟動被hook阻止，禁止用子程序繞過網路封鎖。這是可攜包功能測試的封鎖，不宣稱對惡意原生程式的完整安全sandbox。已跑negative control，socket建立即被拒絕，沒有真的連外。完整包測試目前缺實作，**尚未證明正式包可離線跑完**。

README檢查工作內容／要提交／操作，start.command必須存在；start.bat保持UNKNOWN，等#344/yyin Y0。資料/檔名檢查GT/計畫錨/評分資訊、私人路徑、原始Blender與模型權重；實作主任務仍另跑#318通用掃描，不以本小測試取代完整檢查。

## 依賴到位後怎麼跑

先接真glue，然後使用議題原命令：

```bash
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/q1q5/test_team_eval_pack.py
python scripts/check_handoff_pack.py --pack <LOCAL 評測包 ZIP> --profile team-eval
```

#318目前正式profile未選定，第二條預設fail closed；待#293接正式契約後驗收，不能用test-only projection當正式包。

## 實際結果

Model / effort：GPT-6（Codex） / UNKNOWN。Python3.12.12、isolated=1，兩個fixture/網路封鎖自測PASS。正常2passed/9skipped；strict2passed/9failed/0skipped/0errors，九個都是CQ14_IMPLEMENTATION_MISSING。沒有建可發送包、沒有fake entrypoint冒充產品通過。架構守門NOT_RUN（#307未交付）；#127 kit NOT_APPLICABLE（純test-first、無產品recording）。正式RETURN契約、跨機器驗收、發包U12與Windows皆未驗。
