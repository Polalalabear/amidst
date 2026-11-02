# 組員離線評測包：FEAT-3／#293

依 [D112-1 定案](https://github.com/Polalalabear/amidst/issues/293#issuecomment-6569026437)。目前 native builder、standalone verifier／replay、RETURN 及 TEST-ONLY driver 已實作；真實 P1 包仍等下方 scan gate 與 FEAT-2 的共用 production profile。此文件不表示 U12 發包核准。

## 程式與模式

- `scripts/build_team_eval_pack.py`：標準庫 CLI；只讀明確提供的凍結 JSON 與 SHA，不啟動模型、網路或 repo 服務。
- `src/amidst/q1q5/team_eval_pack.py`：native builder／verify／RETURN 驗證及逐 bytes replay。相同程式以 standalone source 放入包內 tools，執行不需 repo 或 site-packages。
- `CQ14_TEST_RETURN_V1`：只給明示的兩半 SYNTHETIC 輸入與 -T；不能當成真實 P1 包。
- `TEAM_EVAL_BASELINE_V0_PILOT`：D112 的 Baseline-only 工程投影；`v0-pilot`、`evaluation_eligible=false`、`halves=["baseline"]`、`editable_files={}`。`team-eval-return.v1` 仍 PROPOSED。沒有選 profile 時 fail closed。
- 多個 Baseline 凍結 JSON 只以外層 JSON 陣列收集；每個來源的原 bytes 原樣保留，source_pins 逐一綁定。沒有改 response、產品 output hash、clock、決定或身份。
- D112 Baseline-only RETURN 的 `halves` 是以 baseline 為唯一鍵的映射，與 output_sha256／return_files 鍵集合相同；MANIFEST 的 halves 仍為清單。SYNTHETIC -T 的表示法保留。
- #293 的[精確例外定案](https://github.com/Polalalabear/amidst/issues/293#issuecomment-6574714049)只適用兩個固定來源的 false provenance 旗標。先核原文件 bytes；collection 逐切片核原始 bytes，再只為掃描建立移除該旗標的記憶體副本。payload、RETURN與既有output hash不改；其他路徑、型別、額外禁止內容與其他profile仍拒絕。

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

## 真實 P1 的來源與 C-09

來源 <LOCAL P1 v4 ENGINEERING> 的MANIFEST固定 `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`，source commit `c26d7cdd07deb43c9991a4f46403ea0236277fb1`。兩個來源name/pins列在native與共用常數及舊inventory收據；舊收據的pending文字只屬當時狀態，已由#293精確例外定案與本輪C-09收據接續。

真P1包只收集兩個既有frozen JSON，沒有複製整個來源包。逐文件bytes原樣放進collection，來源response／產品output hash不改；collection自己的檔案SHA另列。兩次建包byte-identical：ZIP 64,585bytes，SHA `01a52e216a1d8d6f1c4f247e525c529d12d4d641e0d8efee1d1a379b464eb08c`；MANIFEST `afda8065a0aa85390278636c194c618d4fc024ac7cad087cea07197737dd61d2`。

C-09 LOCAL乾淨scratchpad：對production checker已VALID的ZIP解壓，cwd為另一空目錄。相同Python3.12.12以`-I -S`直接執行包內verify／replay；audit阻擋socket、子程序、repo與原artifacts／來源包的讀取，0次禁止存取。verify VALID → replay VALID → RETURN → 我方native validate_return與共享checker --returned-json VALID。共享checker明列不檢實際RETURN bytes；native另外核實payload／RETURN逐bytes相同與output_sha256。沒有讀劇本計分。

持久收據 `TEAM_EVAL_P1_C09_20261102.json` 記錄步驟、原來源前後pins、輸出與code hashes、df-k前後、隔離旗標。完整ZIP／原生報告保留LOCAL，沒有提交原始資料。這個結果是Baseline-only ENGINEERING的重播與讀入；complex NOT_INCLUDED。另一實機／Windows NOT_RUN，組員Y5與正式計分C-10仍NOT_RUN；發包仍等U12與Claude審查，release_authorized=false。

重現時先重新核來源MANIFEST與兩個原文件pins，再用build CLI明傳每個baseline檔、SHA及source-name，指定全新output／zip／receipt。checker用`--profile team-eval --manifest-sha256 <PIN>`；包內程式用Python3.12 `-I`照README執行；我方讀回使用native validate_return，另可對原ZIP傳checker `--returned-json <RETURN>`。不要對已含可變RETURN的解壓目錄套用原ZIP的不可變fileset檢查。U12前不交給組員。
