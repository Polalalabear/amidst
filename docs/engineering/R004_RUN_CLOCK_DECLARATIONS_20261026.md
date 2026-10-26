# r004 A4／B4 獨立展示時鐘宣告（D84／D89 更新）

D89核定 A4-1 50 s／B4-1 42 s，query分別[0,48)／[0,40) s。起點沿用使用者原先選的2026-11-01 14:00／14:10（Asia/Taipei）；`DECLARED_DEMO_CLOCK`不是拍攝時間。D89留言時間只作宣告紀錄，不拿系統時間回填展示起點。

| run | source_duration_us | query_source_range_us | wall_origin |
| --- | ---: | --- | --- |
| A4 | 50000000 | [0, 48000000] | 2026-11-01T14:00:00+08:00 |
| B4 | 42000000 | [0, 40000000] | 2026-11-01T14:10:00+08:00 |

`t0_us=0`、`rate=1`；run_id／clock_id各自獨立且保留原值，沒有重用A／B1。mapping_version改為`r004-declared-demo-v1-d89`，全部content/file hash已重發。

## D84 catalog 凍結

依[D84](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6416451756)，原catalog byte SHA-256 `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`原樣凍結，與G4脫鉤。8台static_validity全部維持NOT_EVALUATED；原run_bindings仍為[]，catalog bytes未改、未複製。凍結只核定catalog bytes，不代表通行、碰撞或辨識品質核准。

[凍結收據](../history/R004_CAMERA_CATALOG_FREEZE_D84_20261027.json)包含全長hash、approval_ref與八台清單。兩份獨立run註冊宣告各自引用凍結catalog和時鐘，不改catalog本身；這是發包用metadata，不是假造已產製RGB／index的runtime registry。

## 檔案與 pins

- [configs/q1q5/clocks/r004_a4_v1.json](../../configs/q1q5/clocks/r004_a4_v1.json)，bytes SHA-256 `a6d6df46110b5b8bc7874792c9bc0b469dd099eb7fc24f2806b7933d7e08079a`。
- [configs/q1q5/runs/r004_a4_v1.json](../../configs/q1q5/runs/r004_a4_v1.json)，bytes SHA-256 `2f9c77fac097098787a1b23602cc59868677d655a1c4f92c0831c21f9dd0a0b9`。
- [configs/q1q5/clocks/r004_b4_v1.json](../../configs/q1q5/clocks/r004_b4_v1.json)，bytes SHA-256 `3a39443753120c102acaf23ed7c166048157f4ae805d92ff12f36e45a31c35d4`。
- [configs/q1q5/runs/r004_b4_v1.json](../../configs/q1q5/runs/r004_b4_v1.json)，bytes SHA-256 `bec1b2829ef2eabcdac74ea9123725ee7e9b486364c27c360b45e70eb707b598`。

[formal context](../../configs/q1q5/r004_formal_context_v1.json)記錄查詢範圍、clock/registration/freeze pins與真正待辦：Claude更新內容複核及#238合併後SHA。`question_pack_ready=false`，不以未合Draft直接發包；Q1 query_binding的index／aliases／parameters正式pins仍INCOMPLETE（不把出題前metadata當正式query_binding）。G4仍false，但不再列為catalog／Q1/Q3題包的前置。

## A1 與生產界線

[A1 #256](https://github.com/Polalalabear/amidst/pull/256)已回報現有footprint與卡片時刻的步速／雙入口衝突，不能宣稱完整可行。此處仍依D89固定50/42 s，不擅改事件時刻、長度、ROI、圖、原審查包或Blender。正式劇本、RGB、index、G4及人審均未完成。

## 重現驗證

在repo根目錄讀context，每份clock以`ClockMapping.from_document`傳入run/clock/content pin；分別以`resolve_source_range(mapping,0,source_duration_us)`與query終點驗READY／coverage_complete；核對registration content/hash及freeze原始bytes pin。原catalog來源需以LOCAL locator掛載，核對上述SHA；公開Git不含校正資產。

## 實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: 延續Draft #238，前head `07571b6a02713159a8b51d0ad9e1c65420711442`；新head見PR，不合併。
- Files changed: 原5檔更新；新增2份run註冊與D84凍結收據（共8檔）。
- Commands run and results: LOCAL `verify_a2.py`透過既有離線uv/Python執行；2份clock、4個完整／query半開範圍、2份run註冊、所有content/file/catalog pins PASS；JSON解析與`git diff --check` PASS。
- Artifacts: 精確每檔SHA-256見PR實際產出；原catalog／geometry／RGB LOCAL且未複製。
- Verified: D84原樣凍結與NOT_EVALUATED、D89長度／範圍、既有wall origins、獨立IDs、G4脫鉤。
- Not verified: Claude更新內容複核／合併、正式index／RGB／G4／人物正確性。
- Deviations, UNKNOWN items and follow-ups: A1幾何衝突保持未解；不影響metadata依核定長度交件。
