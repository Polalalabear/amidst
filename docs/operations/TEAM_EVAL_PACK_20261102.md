# 組員離線評測包：FEAT-3／#293

依 [D112-1 定案](https://github.com/Polalalabear/amidst/issues/293#issuecomment-6569026437)。目前 native builder、standalone verifier／replay、RETURN 及 TEST-ONLY driver 已實作；真實 P1 包仍等下方 scan gate 與 FEAT-2 的共用 production profile。此文件不表示 U12 發包核准。

## 程式與模式

- `scripts/build_team_eval_pack.py`：標準庫 CLI；只讀明確提供的凍結 JSON 與 SHA，不啟動模型、網路或 repo 服務。
- `src/amidst/q1q5/team_eval_pack.py`：native builder／verify／RETURN 驗證及逐 bytes replay。相同程式以 standalone source 放入包內 tools，執行不需 repo 或 site-packages。
- `CQ14_TEST_RETURN_V1`：只給明示的兩半 SYNTHETIC 輸入與 -T；不能當成真實 P1 包。
- `TEAM_EVAL_BASELINE_V0_PILOT`：D112 的 Baseline-only 工程投影；`v0-pilot`、`evaluation_eligible=false`、`halves=["baseline"]`、`editable_files={}`。`team-eval-return.v1` 仍 PROPOSED。沒有選 profile 時 fail closed。
- 多個 Baseline 凍結 JSON 只以外層 JSON 陣列收集；每個來源的原 bytes 原樣保留，source_pins 逐一綁定。沒有改 response、產品 output hash、clock、決定或身份。

包內 MANIFEST 逐檔 pin 不可變 payload；RETURN 的輸出和結果可新增，其餘未列檔案拒絕。SYNTHETIC 的 optional template 缺失回 VALID_WITH_WARNINGS，其餘不可變缺失／篡改均 INVALID。
symlink、路徑逃逸、重複 JSON keys、非有限值、未選 profile／formal flags、錯誤 source pins、禁止內容和既有輸出覆寫皆拒絕。

## 原 -T 與新增 Baseline-only 驗收

#364 的 -T 不再修改。driver 只做原生函式／欄位映射；trace 與原生 source SHA 仍由 -T 驗證。

```bash
AMIDST_REQUIRE_IMPL=1 AMIDST_TEAM_EVAL_DRIVER=team_eval_pack_driver PYTHONPATH=src:tests/q1q5 uv run python -m pytest -q tests/q1q5/test_team_eval_pack.py tests/q1q5/test_team_eval_baseline.py tests/q1q5/test_portable_pack.py
git diff --check "$(git merge-base origin/codex/q1q5-staging HEAD)" HEAD
```

新增 focused tests 使用 SYNTHETIC 控制，不代表真實 P1 接受；涵蓋 Baseline-only replay／VALID、三個集合與 root 的 complex 拒絕、halves 不符、formal flags、必要 metadata、deterministic ZIP、多文件原 bytes 與 plain／escaped 禁止內容。原 -T 的空 cwd、Python 3.12 `-I`、socket／子程序封鎖、逐 bytes 比對與 missing-field／tamper 斷言均保留。

## SYNTHETIC CLI 自測

操作者選既有、可寫的新 LOCAL_OUT；包、ZIP、收據路徑須尚不存在：

```bash
PYTHONPATH=src uv run python scripts/build_team_eval_pack.py --synthetic-inputs tests/fixtures/team_eval_pack/SYNTHETIC/inputs.SYNTHETIC.json --profile CQ14_TEST_RETURN_V1 --output "$LOCAL_OUT/synthetic-a" --zip "$LOCAL_OUT/synthetic-a.zip" --receipt "$LOCAL_OUT/synthetic-a.receipt.json"
```

換三個新輸出名稱再跑一次，MANIFEST 與 ZIP 應完全相同。不要把已有結果覆寫掉。
在空 cwd 使用包內工具，MANIFEST pin 由發包者獨立提供（取 CLI 收據／GitHub 紀錄，不把自行重算未知包的值當成核准）：

```bash
python3.12 -I "$PACK/tools/verify_pack.py" --profile CQ14_TEST_RETURN_V1 --manifest-sha256 "$MANIFEST_PIN"
python3.12 -I "$PACK/tools/team_eval.py" --profile CQ14_TEST_RETURN_V1 --manifest-sha256 "$MANIFEST_PIN"
```

replay 只複製不可變 payload 到 `RETURN/outputs/{half}.json`，最後才產 `RETURN/評測結果_姓名_YYYY-MM-DD.json`。RETURN 含 pin、Python 3.12.x／isolated／platform、halves、output_sha256、return_files；實際 runtime 必須是 3.12 `-I`。重跑使用新的解壓目錄。
本 CLI 自測不是 C-09 的真實 P1 那一次，也不是組員 Y5 回件或正式計分。

## 真實 P1 的來源與剩餘 gate

候選清單：[`TEAM_EVAL_P1_INPUTS_20261102.json`](TEAM_EVAL_P1_INPUTS_20261102.json)。來源 locator 為 LOCAL 的 `P1_V4_BUNDLE`，以 MANIFEST bytes SHA `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7` 與 code commit `c26d7cdd07deb43c9991a4f46403ea0236277fb1` 確認；目錄名稱不作 authority。原 Shared 包保持唯讀，沒有整包複製。

Baseline 半部擬使用兩份既有錄製：RULE_ONLY 與 AGENT_SEQUENTIAL。確切兩筆 source_pins 在收據及 #370；FEAT-2 依 D112 釘為 TEAM_EVAL_SOURCE_PINS。
目前每份唯一禁止命中是 `/response/provenance/gt_read=false`。原樣 `scan()` 會拒絕它；原生 CLI 對真來源也保持 INVALID、不產包。沒有刪旗標、重算產品 output hash、編碼隱藏或假標 SYNTHETIC。
例外的精確範圍、型別及負例提案見 [#293](https://github.com/Polalalabear/amidst/issues/293#issuecomment-6572871164)。等 Claude 定案，再由 FEAT-2／FEAT-3 各自擁有者同步 scanner，不能先放寬。

定案後使用 D112 的共用分支（從 #359@aa3196163c9702274aa4fde36ff1016a8902ea07 開）只改 checker 與其測試，FEAT-2／FEAT-3 都 no-ff 合入。production profile VALID 與 C-09 真實 P1 的獨立重跑在此之前 NOT_RUN。
原 -T 兩半照常；真包不得放 complex payload／佔位檔／空目錄。#335 對未含的 complex 報 NOT_INCLUDED，真人計分仍等 U12、Y5。

## 交回與發布邊界

README 有工作內容／要提交項目／操作／不要改與 _INCOMPLETE 說明。MANIFEST 不含自己的 hash，外部收據提供 manifest pin，避免 circular hash。start.command 明傳所選 profile，並要求操作者提供 pin。
human_approval_verified 與 release_authorized 保持 false。工程／SYNTHETIC 的通過不核身份、通行、研究、AC7 或發包。真 P1 C-09、production checker、Claude 複審與使用者 U12 成立後才可交給組員。
