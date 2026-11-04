# #448 本機空間唯讀盤點與 #441 交叉審查

盤點開始：2026-11-04；交件：2026-11-05（Asia/Taipei）；free snapshot：2026-11-04T16:03:58Z。**刪除／搬移／停服務：全部 0。**

使用者優先條件：**不影響當前專案進行**。本表只是待選清單；A 級須使用者明確授權，B 級須 Claude 審查＋使用者授權。本輪不清 cache、不刪 clone／branch、不中斷 #416，也不執行 #447 的 Blender 工作。

## 空間估算與建議順序

- 當下可用 **8.4613 GiB**；#447 必須重新量得 ≥8.5 GiB 才開工，<8 GiB 停止。
- A 級可供選擇 **14 項，du 名目合計 2.0353 GiB**；不是已授權、已刪除或保證可回收。
- A 級 hardlink 去重後 regular-file blocks 2.0353 GiB；其中已知仍有選取範圍外 hardlink 的 blocks 0.0000 GiB，不能算成刪除即回收。APFS CoW extent 仍 UNKNOWN。
- B 級**目前建議可清 0 GiB**；B01–B03 是完成替代／移交、更新引用及雙重授權後的條件式候選，名目上限 2.0661 GiB，不能現在執行。
- 名目情境：只清選定全部 A → **10.4966 GiB**；若未來 B01–B03 也滿足條件 → **12.5627 GiB**。這是當下 free + du 上限算式，非容量保證；本次實際回收 **0 bytes**。
- 保留副本仍共用 APFS extents 時，刪重複副本可能只回收極少 metadata。實際 future free 無法由 du 證明；需每筆獲准刪除後量 df，達到 gate 後不繼續擴張清理。

## A 級：可重建快取／暫存 clone 候選

| ID | 絕對路徑 | 大小（du） | 理由／取代來源／引用 | 建議 |
| --- | --- | --- | --- | --- |
| A01 | `/Users/polalabear/.cache/puppeteer` | 0.4592 GiB | 目前無 open-file 命中；現在使用的瀏覽器 executable 在 ChatGPT/Codex app 及既有 Chrome，非此下載快取。保留 profiles/帳號資料。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN | 刪除候選：獲使用者明列授權後，再確認無 consumer；不跟隨 symlink |
| A02 | `/Users/polalabear/Library/Caches/pip` | 0.0118 GiB | 專案目前以 uv 與既有 venv 執行；無此路徑的 open-file 命中；不動 pip/uv 的安裝環境。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN | 刪除候選：獲授權後只清此 cache |
| A03 | `/private/tmp/amidst-01a199f8-feat2-profile` | 0.1376 GiB | HEAD `5f4ed678bfcbaa3c521c5d56f0c60cad656741d8`；7 個 local tips 已保存；95 PNG 如存在皆是 Git tracked 副本；ignored 僅 code cache。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN | 刪除 clone 候選：先確認 owner 不再使用；只限此副本 |
| A04 | `/private/tmp/amidst-01a199f8-feat3-v2` | 0.1353 GiB | HEAD `aaf660d76cc2e15315931fc73fac11945b4fe79c`；2 個 local tips 已保存；95 PNG 如存在皆是 Git tracked 副本；ignored 僅 code cache。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN | 刪除 clone 候選：先確認 owner 不再使用；只限此副本 |
| A05 | `/private/tmp/amidst-01a199f8-feat7-guard` | 0.1341 GiB | HEAD `b6f5a28b24e2850f83a781d7300bf3dce7566c81`；3 個 local tips 已保存；95 PNG 如存在皆是 Git tracked 副本；ignored 僅 code cache。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN | 刪除 clone 候選：先確認 owner 不再使用；只限此副本 |
| A06 | `/private/tmp/amidst-cx7-wire-01a19f68` | 0.1686 GiB | HEAD `9394b60216aeb676730cf580419c2e0caf3a72bc`；2 個 local tips 已保存；95 PNG 如存在皆是 Git tracked 副本；ignored 僅 code cache。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/R004_EVENT_RUNS_RECEIPT.md:120` | 刪除 clone 候選：先確認 owner 不再使用；只限此副本 |
| A10 | `/private/tmp/amidst-demo-launch-20261103-97030cd0` | 0.1652 GiB | HEAD `6d029ce9328ba922a252b851ae987314cbfd5b00`；2 個 local tips 已保存；95 PNG 如存在皆是 Git tracked 副本；ignored 僅 code cache。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN | 刪除 clone 候選：先確認 owner 不再使用；只限此副本 |
| A13 | `/private/tmp/amidst-review-403-TFA4kT` | 0.0190 GiB | HEAD `9a4701658a3a06ef95007263d0b58fc8017fdd6d`；1 個 local tips 已保存；95 PNG 如存在皆是 Git tracked 副本；ignored 僅 code cache。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN | 刪除 clone 候選：先確認 owner 不再使用；只限此副本 |
| A14 | `/private/tmp/amidst-root-01a199f8-feat1-render` | 0.1354 GiB | HEAD `ed6a8dc8c62e833166beeb350f9a91e8c7db34ee`；2 個 local tips 已保存；95 PNG 如存在皆是 Git tracked 副本；ignored 僅 code cache。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN | 刪除 clone 候選：先確認 owner 不再使用；只限此副本 |
| A15 | `/private/tmp/amidst-root-01a199f8-feat2-pins` | 0.1337 GiB | HEAD `46e4673f6d7bbc41d43e623882afe438db16893a`；3 個 local tips 已保存；95 PNG 如存在皆是 Git tracked 副本；ignored 僅 code cache。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN | 刪除 clone 候選：先確認 owner 不再使用；只限此副本 |
| A16 | `/private/tmp/amidst-root-01a199f8-feat5-registry` | 0.1336 GiB | HEAD `1ffabe603c5197515c9825f7e40e9ba5a08b1b35`；2 個 local tips 已保存；95 PNG 如存在皆是 Git tracked 副本；ignored 僅 code cache。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN | 刪除 clone 候選：先確認 owner 不再使用；只限此副本 |
| A17 | `/private/tmp/amidst-root-01a199f8-feat6-review` | 0.1337 GiB | HEAD `943a72f8a2c5ade5472d5ead00cc5a2f2bb4fdf4`；2 個 local tips 已保存；95 PNG 如存在皆是 Git tracked 副本；ignored 僅 code cache。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN | 刪除 clone 候選：先確認 owner 不再使用；只限此副本 |
| A18 | `/private/tmp/amidst-root-01a199f8-feat8` | 0.1329 GiB | HEAD `47da051700683dfdc8607cafe41ba1a64d64025e`；2 個 local tips 已保存；95 PNG 如存在皆是 Git tracked 副本；ignored 僅 code cache。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN | 刪除 clone 候選：先確認 owner 不再使用；只限此副本 |
| A19 | `/private/tmp/amidst-root-01a199f8-guard-scan-d114` | 0.1353 GiB | HEAD `72f911e156d648e953f4b71144c27b5600b26d1a`；1 個 local tips 已保存；95 PNG 如存在皆是 Git tracked 副本；ignored 僅 code cache。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/ARCHITECTURE_GUARD_D114_REPORTS_20261103.json:13` | 刪除 clone 候選：先確認 owner 不再使用；只限此副本 |

不刪原始 checkout；local `60fa8ef64988435530b09fb258d79130e83977af` 的保全依據是 `/Users/polalabear/Developer/amidst` 仍持有該 HEAD。部分 clone 的 95 張 PNG 是已追蹤的 Git 副本，未讀影像；並未把原始資料庫／渲染包列為 A。全部 branch-tip 明細與重建依據見 JSON；執行前要重新核對 owner、ignored/untracked、open files 與 source pin。

## A 級：本輪保留、不計可釋放

| ID | 絕對路徑 | 大小 | 保留原因／引用 |
| --- | --- | --- | --- |
| A07 | `/private/tmp/amidst-d1223-01a19f8b` | 0.1403 GiB | 目前 #448/#418、#416 或 #442 的工作／重現 clone；保留。 引用：`/private/tmp/amidst-d1223-01a19f8b/docs/engineering/R004_D124_RERENDER_RECEIPT.md:76` |
| A08 | `/private/tmp/amidst-d127-01a1a4ff` | 0.0517 GiB | 目前 #448/#418、#416 或 #442 的工作／重現 clone；保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| A09 | `/private/tmp/amidst-d127-415` | 0.0195 GiB | 目前 #448/#418、#416 或 #442 的工作／重現 clone；保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| A11 | `/private/tmp/amidst-pr407-rereview` | 0.0185 GiB | git status 有 2291 筆，不能當乾淨暫存；不復原、不 reset、不覆寫。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| A12 | `/private/tmp/amidst-pr407-review` | 0.0184 GiB | git status 有 2291 筆，不能當乾淨暫存；不復原、不 reset、不覆寫。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| A20 | `/private/tmp/amidst-root-01a199f8-u16-rehearsal` | 0.1348 GiB | 有尚未證明由 live GitHub 或保留的原 checkout 保存之 local commit，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| AK20 | `/Users/polalabear/.cache/uv` | 1.1960 GiB | 目前離線依賴／uv 工作流程仍使用；原路徑含環境與 symlink，先保留，不能只因可重建就清。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| AK21 | `/private/tmp/amidst-demo-launch-uv-cache` | 0.4159 GiB | Q1Q5_REVIEW_403_DIAGNOSIS_20261103.md:74 有明確執行引用；當前 launcher 相容性仍在處理，保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/Q1Q5_REVIEW_403_DIAGNOSIS_20261103.md:74` |
| AK22 | `/Users/polalabear/.npm/_npx` | 0.5066 GiB | 可重下載但尚未逐一證明工具 consumer；以不影響進行中專案為優先，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| AK23 | `/Users/polalabear/.cache/codex-runtimes` | 1.6140 GiB | 代理仍在工作，不以快取名推導可清；consumer 未完全確認。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| AK24 | `/Users/polalabear/Library/Caches/Codex` | 0.2308 GiB | 目前 Codex app 在使用，保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| AK25 | `/Users/polalabear/Library/Caches/Google/Chrome` | 1.1925 GiB | 有 3 個 open-file 命中；Chrome 在使用。Default/Cache 約 0.802 GiB、Code Cache 約 0.362 GiB 目前不列本輪可清。不得清 profile/Storage。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| AK26 | `/private/tmp/claude-501` | 0.0420 GiB | 別的工具／agent 擁有，無明確退休／保全證據，保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |

## B 級：有條件的舊 RGB／safe 投影候選（現在保留）

| ID | 絕對路徑 | 大小 | 理由／取代／引用 | 建議 |
| --- | --- | --- | --- | --- |
| B01 | `/private/tmp/amidst-cx7-wire-01a19f68-output/bundle` | 1.0334 GiB | 目前是必須保留的原 D119 投影。#416 已交件，散裝 transfer 副本依另一 chat 的授權清理退役，ZIP 又由使用者回報刪除；本機沒有已確認的 transfer 替代。須先確認外部交付／hash、更新引用、Claude 審查及使用者授權，才可另議外移。receipt/evidence 仍保留。 取代：`先前 #416 transfer 已退役；外部可用副本 UNKNOWN`；引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/R004_EVENT_RUNS_RECEIPT.md:146` | 目前保留；後續可外移／刪除的條件式候選 |
| B02 | `/Users/polalabear/amidst-artifacts/r004-cx7-d115-20261102-01a199f8/A4-1/safe` | 0.5031 GiB | DEMO_RUNBOOK 仍指向舊 safe media；#442 是新 run，不自動替代歷史研究證據。#416 散裝包已退役、交付 ZIP 已由使用者刪除，外部可用副本 UNKNOWN。先保留；禁止整包刪其父目錄及 gt_private。 取代：`新展示候選 #442 + 舊資料保留副本 #416；尚未證明所有 consumer 已切換`；引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/R004_EVENT_RUNS_RECEIPT.md:63` | 目前保留；新版完整切換後再審是否外移 |
| B03 | `/Users/polalabear/amidst-artifacts/r004-cx7-d115-20261102-01a199f8/B4-1/safe` | 0.5296 GiB | DEMO_RUNBOOK 仍指向舊 safe media；#442 是新 run，不自動替代歷史研究證據。#416 散裝包已退役、交付 ZIP 已由使用者刪除，外部可用副本 UNKNOWN。先保留；禁止整包刪其父目錄及 gt_private。 取代：`新展示候選 #442 + 舊資料保留副本 #416；尚未證明所有 consumer 已切換`；引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/R004_EVENT_RUNS_RECEIPT.md:63` | 目前保留；新版完整切換後再審是否外移 |

兩份舊／新 projection manifest 的實際 bytes SHA 分別為 `60f2b5f8cdddf5096ffa9a25053260568570c40d8ea2737d6663f0ae3e3c2c82` 與 `ad3c66f21ef6713a76b0bb6505a7e5eb3514fa346f9279c42d7b486479281f01`；各自與 #416 transfer 子包中的同一 manifest **逐 bytes hash 相同**（每份 2055 entries）。沒有因此宣稱所有 RGB 已由本輪重驗，也沒有把新 run 的不同 manifest 當成舊 run 已無用途。

## B 級：原始／證據／當前包保留

| ID | 絕對路徑 | 大小 | 保留原因／引用 |
| --- | --- | --- | --- | --- |
| BK01 | `/Users/polalabear/amidst-artifacts/q1q5-baseline-acceptance-v1_20261024` | 0.0120 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/Users/polalabear/Developer/amidst/docs/history/Q1Q5_BASELINE_PREPARATION_RECEIPT_20261024.json:7` |
| BK02 | `/Users/polalabear/amidst-artifacts/q1q5-review-closeout-v1_20261025` | 0.0325 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/QWEN3_UNTRUNCATED_DIAGNOSTIC_20261025.md:38` |
| BK03 | `/Users/polalabear/amidst-artifacts/hsv-proposal-20261021` | 0.0003 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK04 | `/Users/polalabear/amidst-artifacts/r004-graphs-proposed-20261021` | 0.0032 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK05 | `/Users/polalabear/amidst-artifacts/team_review_pack_v0-pilot_20261021` | 0.0097 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/evaluation/TEAM_REVIEW_PACK_REGISTRY.md:9` |
| BK06 | `/Users/polalabear/amidst-artifacts/q1q5-rc5-rerecord-20261027-d92` | 0.0777 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/operations/FEAT6_RESPONSE_V2_INTEGRATION_20261102.md:34` |
| BK07 | `/Users/polalabear/amidst-artifacts/demo-launcher_20261102_01a199f8` | 0.0001 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/operations/Q1Q5_DEMO_LAUNCH.md:33` |
| BK08 | `/Users/polalabear/amidst-artifacts/q1q5-qwen-diagnosis-20261023` | 0.0006 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/Q1Q5_QWEN_CONTENTION_MIGRATION.md:71` |
| BK09 | `/Users/polalabear/amidst-artifacts/coordinator-20261025` | 0.0001 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK10 | `/Users/polalabear/amidst-artifacts/q1q5-playback-continuity-v2_20261024` | 0.0608 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/Users/polalabear/Developer/amidst/docs/engineering/Q1Q5_PLAYBACK_CONTINUITY.md:47` |
| BK11 | `/Users/polalabear/amidst-artifacts/q1q5-baseline-telemetry-v1_20261024` | 0.0008 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK12 | `/Users/polalabear/amidst-artifacts/r004-build-v2-20261021` | 0.0278 GiB | 現有 r004 source SHA 466e6fbe…809b、camera/geometry pins 的來源，#442 仍依賴。 引用：`/private/tmp/amidst-d127-01a1a4ff/configs/q1q5/graphs/r004/build_plan_v3.json:59` |
| BK13 | `/Users/polalabear/amidst-artifacts/q1q5-dynamic-baseline-v1_20261025` | 0.7784 GiB | 既有 baseline/replay/rerecord 來源；存在 private producer；不因新 #442 而消失，不進清理範圍。 引用：`/Users/polalabear/Developer/amidst/docs/engineering/Q1Q5_DYNAMIC_BASELINE.md:15` |
| BK14 | `/Users/polalabear/amidst-artifacts/demo-all-events-shots-20261104` | 0.0010 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK15 | `/Users/polalabear/amidst-artifacts/q1q5-event-modes-20261022` | 0.0090 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK16 | `/Users/polalabear/amidst-artifacts/q1q5-contract-1d1e061` | 0.0002 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK17 | `/Users/polalabear/amidst-artifacts/q1q5-workbench-reopen_20261025T175011` | 0.0001 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK18 | `/Users/polalabear/amidst-artifacts/r004-prereview-team-v2_20261024` | 0.0102 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/R004_REVIEW_V2.md:51` |
| BK19 | `/Users/polalabear/amidst-artifacts/q1q5-qwen3-contention-20261023` | 0.0047 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/Q1Q5_QWEN_CONTENTION_MIGRATION.md:78` |
| BK20 | `/Users/polalabear/amidst-artifacts/q1q5-search-budget-proposal-20261020` | 0.0000 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK21 | `/Users/polalabear/amidst-artifacts/q1q5-staging-20261021` | 0.0426 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK22 | `/Users/polalabear/amidst-artifacts/q1q5_acceptance` | 0.0008 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/agents/Q1Q5_BROWSER_ACCEPTANCE.md:8` |
| BK23 | `/Users/polalabear/amidst-artifacts/q1q5-rc5-rerecord-20261027-d92-validation` | 0.0082 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/history/Q1Q5_RC5_RERECORD_RESULTS_20261027.json:187` |
| BK24 | `/Users/polalabear/amidst-artifacts/team-handoff-yyin-20261025` | 0.0034 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/agents/COORDINATOR_HANDOFF_20261025.md:93` |
| BK25 | `/Users/polalabear/amidst-artifacts/q1q5-model-compare-20261023` | 0.0035 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/Q1Q5_QWEN3_BOTTLENECKS.md:11` |
| BK26 | `/Users/polalabear/amidst-artifacts/q1q2-plan-x2-x3-20261020` | 0.0000 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/Q1_Q5_CONTRACT_REVIEW_20261020.md:127` |
| BK27 | `/Users/polalabear/amidst-artifacts/r004-cx7-d115-20261102-01a199f8` | 2.0681 GiB | 父根同時含 safe 與 GT；不得整包刪。B02/B03 已單列 safe，parent 不重複加總。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/R004_EVENT_RUNS_RECEIPT.md:63` |
| BK28 | `/Users/polalabear/amidst-artifacts/demo-ui-f_20261102_01a199f8` | 0.0001 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/operations/DEMO_UI_F_BROWSER_COMPOSITION_20261102.json:22` |
| BK29 | `/Users/polalabear/amidst-artifacts/demo-20261104` | 0.0005 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK30 | `/Users/polalabear/amidst-artifacts/q1q5-qwen-runtime-20261023` | 0.0072 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/Q1Q5_QWEN_RUNTIME.md:76` |
| BK31 | `/Users/polalabear/amidst-artifacts/q1q5-qwen3-untruncated_20261026_01a1735f` | 0.0004 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/QWEN3_UNTRUNCATED_DIAGNOSTIC_20261025.md:30` |
| BK32 | `/Users/polalabear/amidst-artifacts/r004-hfov-selection-20261021` | 0.0000 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/R004_BUILD_RECEIPT.md:39` |
| BK33 | `/Users/polalabear/amidst-artifacts/q1q5-baseline-runner-v1_20261024` | 0.0564 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/scripts/rerecord_q1q5_rc3.py:32` |
| BK34 | `/Users/polalabear/amidst-artifacts/q1q5-rc3-rerecord-v1_20261026` | 0.0764 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/history/Q1Q5_RC3_RERECORD_RESULTS_20261026.json:33` |
| BK35 | `/Users/polalabear/amidst-artifacts/argon-safe-packs-20261104-d127-416` | ABSENT（初測大小不再計） | 初次盤點時存在；最終重新檢查已不存在。#416 最新交付更新說明散裝生成副本已依另一 chat 授權清理；不歸因本輪，亦不再計入可回收。 引用：`/private/tmp/amidst-d127-415/docs/engineering/d127_416_delivery.json:45` |
| BK36 | `/Users/polalabear/amidst-artifacts/q1q3-authoring-yyin-v0-pilot_20261102_01a199f8` | 0.0037 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/operations/YYIN_S2_PILOT_RECEIPT_20261102.json:42` |
| BK37 | `/Users/polalabear/amidst-artifacts/r004-prereview-team-v1_20261023` | 0.0075 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/R004_GRAPH_CHECK.md:43` |
| BK38 | `/Users/polalabear/amidst-artifacts/q1q5-linked-baseline-v1_20261024` | 0.0249 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/Users/polalabear/Developer/amidst/docs/engineering/Q1Q5_LINKED_ACCEPTANCE.md:50` |
| BK39 | `/Users/polalabear/amidst-artifacts/r004-build-20261021` | 0.0258 GiB | v1 失敗／演進證據且為 #415 build_static_v2 parent f079c8b0…aea8；與 v2 不是相同 hash。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/R004_BUILD_RECEIPT.md:10` |
| BK40 | `/Users/polalabear/amidst-artifacts/r004-cx7r-20261104-01a19f8b` | 1.0360 GiB | #442 新 run 及 source-bound 機械證據，當前優先保留。 引用：`/private/tmp/amidst-d1223-01a19f8b/docs/engineering/R004_D124_RERENDER_RECEIPT.json:58` |
| BK41 | `/Users/polalabear/amidst-artifacts/q1q5-clock-mapping` | 0.0002 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK42 | `/Users/polalabear/amidst-artifacts/q4-eval-program-20261021` | 0.0000 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK43 | `/Users/polalabear/amidst-artifacts/q1q5-baseline-telemetry-20261024` | 0.0008 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK44 | `/Users/polalabear/amidst-artifacts/p1-v4-stripped-20261104-d127-416` | ABSENT（初測大小不再計） | 初次盤點時存在；最終重新檢查已不存在。#416 最新交付更新說明散裝生成副本已依另一 chat 授權清理；不歸因本輪，亦不再計入可回收。 引用：`/private/tmp/amidst-d127-415/docs/engineering/d127_416_delivery.json:10` |
| BK45 | `/Users/polalabear/amidst-artifacts/project-docs-20261104` | 0.0001 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK46 | `/Users/polalabear/amidst-artifacts/q1q5-baseline-telemetry-v2_20261024` | 0.0028 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/Users/polalabear/Developer/amidst/configs/q1q5/baseline_v1_protocol.json:198` |
| BK47 | `/Users/polalabear/amidst-artifacts/d67` | 0.0005 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK48 | `/Users/polalabear/amidst-artifacts/r004-scene-change-proposal` | 0.0002 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/Users/polalabear/Developer/amidst/docs/engineering/FINALIZATION_DECOUPLING_PLAN_20261020.md:7` |
| BK49 | `/Users/polalabear/amidst-artifacts/q1q5-qwen3-switch-20261023` | 0.0005 GiB | 未取得完整替代、引用遷移與保全證據；屬歷史 run/研究/交件資料，先保留。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/engineering/Q1Q5_QWEN3_BOTTLENECKS.md:61` |
| BK-P1 | `/Users/Shared/amidst-p1-clean-room-20261026` | 0.2800 GiB | 原始 MANIFEST 6e9a0a4c…f1d7 及 #413/#416 來源依據；不能拿新 stripped bytes 覆蓋原 hashes。 引用：`/private/tmp/amidst-d127-01a1a4ff/docs/operations/DEMO_RUNBOOK_20261104.md:24` |
| BK-TORCH | `/Users/polalabear/.cache/torch` | 0.0341 GiB | 可能為模型權重或固定實驗輸入；不等同一般 browser cache，未讀內容或改 weights。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK-PERF | `/private/tmp/b05-perf.IvaQQp` | 0.1133 GiB | 有約 0.113 GiB 資料，未證明是純可重建 cache；可能含媒體或量測證據，不能只按 tmp 位置清。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| BK-ZIP | `/private/tmp/amidst-01a199f8-yyin-s2-repro.zip` | 0.0036 GiB | 3.71 MiB 的重現 zip；未開內容，不把資料包列為 A 級。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |

以上父子目錄的「保留大小」可能重疊，**不加入可回收加總**。所有金額是 allocated blocks，不是 Windows 搬運 logical bytes。

## .blend／autosave／原始資產

| 絕對路徑 | 大小 | 引用與判定 |
| --- | --- | --- |
| `/Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1/assets/controlled_scene_v1_s001_r002.blend` | 0.0003 GiB | 原始／凍結來源，依 AGENTS.md 保留；大小、檔名或版本較舊不能證明可刪。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| `/Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1/assets/controlled_scene_v1_s001_r003.blend` | 0.0003 GiB | 原始／凍結來源，依 AGENTS.md 保留；大小、檔名或版本較舊不能證明可刪。 引用：`/Users/polalabear/Developer/amidst/docs/engineering/SCENE_Q1_Q2_PLAN_20261020.md:22` |
| `/Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1/assets/controlled_scene_v1_s001_r001.blend` | 0.0003 GiB | 原始／凍結來源，依 AGENTS.md 保留；大小、檔名或版本較舊不能證明可刪。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| `/Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1/review_only/ctrl-lcorr-s1-preview-5fps-v1-r003/controlled_scene_v1_s001_r003_REVIEW.blend` | 0.0003 GiB | 歷史 review 衍生場景，重現用途與來源不同；先保留，不因 REVIEW 字樣刪除。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| `/Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1/review_only/ctrl-lcorr-s1-preview-5fps-v1-r002/controlled_scene_v1_s001_r002_REVIEW.blend` | 0.0003 GiB | 歷史 review 衍生場景，重現用途與來源不同；先保留，不因 REVIEW 字樣刪除。 引用：本次 bounded 文本搜尋無命中；完整歷史引用 UNKNOWN |
| `/Users/polalabear/Developer/amidst/blender/school_v3.blend` | 0.4361 GiB | 原始／凍結來源，依 AGENTS.md 保留；大小、檔名或版本較舊不能證明可刪。 引用：`/Users/polalabear/Developer/amidst/configs/physical_policy_validation_school_v3.json:4` |
| `/Users/polalabear/Developer/amidst/blender/school_v2.blend` | 0.4343 GiB | 原始／凍結來源，依 AGENTS.md 保留；大小、檔名或版本較舊不能證明可刪。 引用：`/Users/polalabear/Developer/amidst/docs/engineering/SCENE_Q1_Q2_PLAN_20261020.md:20` |
| `/Users/polalabear/Developer/amidst/blender/working/phase1_wall_pilot_20261005/school_v3_wall_marked.blend` | 0.4369 GiB | 原始／凍結來源，依 AGENTS.md 保留；大小、檔名或版本較舊不能證明可刪。 引用：`/Users/polalabear/Developer/amidst/docs/engineering/K7_MAP_VERIFICATION_20261017.md:115` |
| `/Users/polalabear/amidst-artifacts/r004-build-v2-20261021/controlled_scene_v1_s001_r004.blend` | 0.0002 GiB | R004_BUILD_RECEIPT.md 有不同 parent/source SHA pins；v1/v2 同名但不是重複檔，保留。 引用：`/Users/polalabear/Developer/amidst/docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md:30` |
| `/Users/polalabear/amidst-artifacts/r004-build-20261021/controlled_scene_v1_s001_r004.blend` | 0.0002 GiB | R004_BUILD_RECEIPT.md 有不同 parent/source SHA pins；v1/v2 同名但不是重複檔，保留。 引用：`/Users/polalabear/Developer/amidst/docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md:30` |

原始 school v2/v3/wall-marked 三檔合計約 1.307 GiB，全部保留。r004 v1/v2 的同名 blend 也各有不同 published hash；本輪不開啟／重算原始 blend bytes。可讀掃描範圍內未找到 `.blend1`、`.blend2` 或 autosave blend；Blender user config 不等於 cache，不清。私有 producer 路徑不作個別資產候選。

## GT/private：只列 aggregate 大小，保留

| 絕對路徑 | 大小 | 判定 |
| --- | --- | --- |
| `/Users/polalabear/amidst-artifacts/r004-cx7-d115-20261102-01a199f8/gt_private` | 0.0004 GiB | 保留；只用 du/stat 取得路徑及 aggregate 大小，沒有列成員／讀內容 |
| `/Users/polalabear/amidst-artifacts/r004-cx7-d115-20261102-01a199f8/B4-1/gt_private` | 0.5309 GiB | 保留；只用 du/stat 取得路徑及 aggregate 大小，沒有列成員／讀內容 |
| `/Users/polalabear/amidst-artifacts/r004-cx7-d115-20261102-01a199f8/A4-1/gt_private` | 0.5042 GiB | 保留；只用 du/stat 取得路徑及 aggregate 大小，沒有列成員／讀內容 |
| `/Users/polalabear/amidst-artifacts/r004-cx7r-20261104-01a19f8b/gt_private` | 0.0004 GiB | 保留；只用 du/stat 取得路徑及 aggregate 大小，沒有列成員／讀內容 |
| `/Users/polalabear/amidst-artifacts/r004-cx7r-20261104-01a19f8b/B4-1/gt_private` | 0.0006 GiB | 保留；只用 du/stat 取得路徑及 aggregate 大小，沒有列成員／讀內容 |
| `/Users/polalabear/amidst-artifacts/r004-cx7r-20261104-01a19f8b/A4-1/gt_private` | 0.0006 GiB | 保留；只用 du/stat 取得路徑及 aggregate 大小，沒有列成員／讀內容 |

掃描共遇 279 個 private/GT 命名子目錄，多數為 pytest 暫存測試路徑；完整 path+size 在 JSON，未讀內容。所有此類目錄都排除可釋放合計。

## #441 交叉比對判定

| 判定 | #441 範圍 | #448 本機證據與必要修正 |
| --- | --- | --- |
| ADOPT | 保留證據／archive tags、只盤點不刪的方向 | 本輪同樣不刪分支／issue／文件；local runtime/data 要另有 owner/source 證據。 |
| REVISE P2 | 把 6 條仍 open 的 Argon feature branch 列 DELETE_CANDIDATE | #440/#439/#435/#438/#436/#437 都仍 open 且需修；不能據此刪其 clone 中未保存的 local work。clone 的可重建性與遠端 branch 是否能刪是兩件事。 |
| REVISE P2 | 把人工回件／試跑 issue 泛稱已由 FEAT 完全取代 | local source/manifest 與歷史研究 bundle 仍被 code/runbook 引用；工具完成不是人工 gate 完成。需逐 issue receipt/承接 owner。 |
| REVISE P2 | 以 #418 稱 Claude review gate；缺逐項替代證據 | #418 是本機場景工作；使用者已核定 #447，未授權清理。B 級需 Claude＋使用者，A 級依 #448 使用者最新明確範圍。 |
| REJECT（推論） | 合併／版本舊／位於 tmp／有新 #442 ⇒ 本機可刪 | 原始 .blend、舊 RGB 的 runtime consumer、CoW、dirty/local-only tips 反例均存在；不採這項安全推論。不是 REJECT 整份盤點。 |

本輪複審固定 #441 head `8cdd302e07250e12fce1696144f44afadfab6598`；focused `test_cleanup_inventory_w_a12.py` **7 passed, 0.12 s**；無 allow 架構守門各 0 findings、base-to-head diff check PASS。七個 shape/snapshot tests 不能取代逐資產安全審查。未做 merge／merge-tree。

## 掃描與驗證邊界

只做 file metadata／du、Git 狀態／refs、選定文字引用、四份 safe manifest JSON hash。讀取檔案 metadata 212,238 筆；權限／消失路徑 errors 42 筆（Library/Caches 另有 11 行權限拒絕）；不繞過 OS 拒絕，也不宣稱全磁碟完整盤點。
- roots：原 repo／兩個 Amidst checkout／amidst-artifacts／.codex/worktrees／private tmp 及 user TMP／Downloads/Desktop/Documents（只找 blend metadata）。.git、venv、node_modules、PostgreSQL cluster、Ollama models 於 blend 掃描中剪枝。沒有讀秘密、GT、原始媒體或 key。
- 主 checkout 保留 `60fa8ef…`、原 branch、`docs/README.md` dirty 與全部 untracked；5 個既有 worktree 不變。phase1-finalization 內 venv/PostgreSQL/Ollama 必須保留，不能按整個目錄大小清。
- `lsof` 是時間快照，0 open files 不是永久無 consumer 證明。另一個 active chat 的 `/private/tmp/amidst-d127-415` 與所有 #416 輸出明列保留；不改它的 checkout。
- 本輪無媒體 decode/hash 重跑、Blender、模型推論、資料搬移、cache clean、process kill 或刪除。LOCAL 原始診斷在 `/private/tmp/d127-448-*`；raw lsof 可能含無關個人路徑，只保留 LOCAL，不提交。
- 這份報告完成後等使用者選 A 編號；B 另等 Claude。未核准的候選不能執行。

## 交件前外部變更與重啟提醒

- 本輪中曾讀得 free 約 5.2239 GiB，已按 D118 停止本機寫檔；使用者回報刪除交付 ZIP 後，重新 df 約 8.46 GiB，恢復小型報告交件。沒有啟動 Blender。前後差異不記為本輪清理成果。
- [#416 交付更新](https://github.com/Polalalabear/amidst/issues/416#issuecomment-6635305099) 記錄散裝副本已由另一 chat 依授權退役。本輪重新檢查 argon-safe-packs 與 p1-v4-stripped 兩路徑、交付 ZIP 均不存在；仍在保留清單記下歷史路徑，bytes=0／ABSENT，不再列可回收。原 P1、D119 projection、D124 原始 run 保留。
- 使用者準備重啟；不要假設重啟會自動清空 /private/tmp。重啟後所有 PID／open-file／容量快照失效，需重新驗證 owner、Git dirty/refs、存在性與 free，再依明列授權執行。
- #447 方案 A 的核定與新 source-bound 測試入口已確認於 [#418 核定留言](https://github.com/Polalalabear/amidst/issues/418#issuecomment-6634899000)。本輪先交 #448；≥8.5 GiB 的開工 gate 不豁免，r004/v3_1 既有斷言及 skip 不動。
