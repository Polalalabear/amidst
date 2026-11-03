# r004 CX-7 A4-1 / B4-1 渲染收據

日期：2026-11-03（Asia/Taipei）；FEAT-1 #376／CX-7 #115，交件 PR #394。

## 範圍與 gate

此收據記錄已產生的 LOCAL RGB 與去中繼資料的 safe staging。下方渲染紀錄保留當時狀態；
2026-11-03 D119 production 機械投影結果另見本文末段及同名 JSON，不能改寫成產品或研究核准。
不宣稱偵測索引、Q1–Q5 執行、P2、AC7、身分或物理可通行已成立。

| D98-2 條件 | 結果 | 可核對依據 |
| --- | --- | --- |
| (a) G4 | PASS | [D115](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6579052576)、#281 本文；#348@`0502225bb16f117014fd875fc7a9281220ede484`；decisions_sha256 `9d99f87ea007e1988797e50fa28e70f67e6973578bc15ef3f440ba4f4d8bc76c` |
| (b) 劇本凍結 | PASS | D105-1／#354@`48133c1`；freeze `ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb`，原 bytes 及13個參照未改 |
| (c) 磁碟 | PASS | 起始可用14,247,852 KiB，兩段後及每個 camera 段前後已量；見下表。現行 [D118](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6580320736) 暫停門檻8 GiB；既有 producer 採較早9 GiB門檻且未觸發，不改寫歷史 driver／LOCK |

G4 只滿足渲染條件。`allowed_purposes=[]`，產品端跨鏡頭仍等 CQ-21 #304；P1 live scope `e2ca308b…` 仍 PROPOSED。#348 未合入整合分支；未改採 #351 B1。

## 來源與凍結綁定

來源標示用 LOCAL 代號，不公開使用者名稱或絕對來源 locator。

| 項目 | SHA-256 |
| --- | --- |
| `<LOCAL r004 derived blend>` | `466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b` |
| `<LOCAL r004 safe_static>` cameras.json | `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f` |
| `docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json` | `ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb` |
| A4-1 producer script | `d304d0fcc17932e11dd54120fc06f88c96e28dbb07713c75e388e7664a4824a9` |
| B4-1 producer script | `c1e7dcd1461f646c532fdd85d6f59c81ae9155cc14bcaf3c3b0a5ba2865c8345` |
| A4-1 clock | `a6d6df46110b5b8bc7874792c9bc0b469dd099eb7fc24f2806b7933d7e08079a` |
| B4-1 clock | `3a39443753120c102acaf23ed7c166048157f4ae805d92ff12f36e45a31c35d4` |
| LOCAL immutable producer `gt_private/render_cx7.py` | `60ca817001a374ef32eaece41f1beadade412a80a5a18b97755ea7ca32a4687b` |

來源衍生 blend 僅讀，render 前後 hash 相同，未 save／copy；原始 Blender、影片、GT 資產未修改。
保留來源既有紅衣 P1 模型、材質、frame-1 pose；只於記憶體依凍結控制點線性平移，未新增 gait／人體。
未選定藍衣干擾路線不啟用；不以此推定遮擋／可見性／身份。相機校正、解析度及凍結劇本 bytes 不變。

Blender 5.2.1 LTS（build `9e2066aef7ef`，2026-08-25），BLENDER_EEVEE，960×540 RGB PNG，5 fps，16 samples（來源64，依加速要求只調取樣）。

## 已產生的 run / clock / RGB

| 項目 | A4-1 | B4-1 |
| --- | --- | --- |
| run_id | `ctrl-lcorr-s1-a4-5fps-v1-r004` | `ctrl-lcorr-s1-b4-5fps-v1-r004` |
| clock_id | `clock:r004:a4:declared-demo:v1` | `clock:r004:b4:declared-demo:v1` |
| clock 類型 | DECLARED_DEMO_CLOCK | DECLARED_DEMO_CLOCK |
| wall_origin（Asia/Taipei） | 2026-11-01T14:00:00+08:00 | 2026-11-01T14:10:00+08:00 |
| t0_us / rate | 0 / 1 | 0 / 1 |
| duration / source samples | 50 s／0…49.8 s，200000 µs 間隔 | 42 s／0…41.8 s，200000 µs 間隔 |
| cameras | CAM_EXT_CAR、CAM_EXT_CLEAR、CAM_ENTRY、CAM_W1 | CAM_W1、CAM_W2、CAM_BRANCH、CAM_R101_IN、CAM_WIDE |
| frames | 4×250＝1000 | 5×210＝1050 |
| raw PNG bytes（PRIVATE） | 538357066 | 566772435 |
| sanitized RGB bytes（staging） | 538013316 | 566413125 |
| 段後可用（df -k） | 13172420 KiB | 12181860 KiB |
| 全段最低可用 | 13488558080 bytes（12.562 GiB） | 12474224640 bytes（11.618 GiB） |
| render completion | PASS（1000/1000） | PASS（1050/1050） |

clock 是宣告式 demo 時鐘，非渲染 wall time 或實測同步。兩段為獨立 run／clock，不混用。
磁碟受其他 session 影響，不把全機磁碟差額視為本 run 用量。

## LOCAL 證據與隔離

LOCAL output 代號：`<LOCAL r004-cx7-d115-20261102-01a199f8>`。
以下路徑均相對此根目錄；本 repo 只提交這份 curated 收據，不提交影像、GT、driver 或整包資料。

- `A4-1/safe/media/<camera>/<index>.png`、`B4-1/safe/media/<camera>/<index>.png`：只有 sanitized RGB，尚未作 production manifest。
- 每段 `gt_private/`：原 render PNG、LOCK、frame journal（含路線位置）、completion、df 紀錄、逐檔 raw/safe hashes 與 integrity summary。這些 private 證據不作推論輸入。
- safe PNG 移除 tEXt／iTXt／zTXt／eXIf；逐張 CRC、960×540、IDAT chunks 與 raw 原封相同。完整 camera/index grid、微秒取樣、檔案 hashes 全部核對，沒有缺檔／重複／額外檔或 symlink。
- PRIVATE audit 另核對路線取樣與凍結控制點；該路線、GT、visibility、depth 均不匯入 safe、推論、排序或重建。
- `completion.json` 是 run 結束證據；歷史 `progress.json` 的 RENDERING 字串不代表仍有渲染程序。

| LOCAL 證據 | SHA-256 |
| --- | --- |
| `A4-1/gt_private/LOCK.json` | `937d2b454c9a79e66b109241c7de57748bb5a2b7474e90afc1f92487e44b91d4` |
| `A4-1/gt_private/completion.json` | `02d73673e1fa2fe51d1eeefa3ce86fb4a07f6529f694cd369562b8494b041065` |
| `A4-1/gt_private/frame_integrity_summary.json` | `f00c2754c0956d245775895fd6fe543c92f465c8b49d50c8d85d1e1ea9b848c3` |
| `A4-1/gt_private/safe_frame_inventory.json` | `907615d4645507182590fbbc9c6d3e9213deef60c28fb07c9b5514773b60b939` |
| `B4-1/gt_private/LOCK.json` | `eacda514324316b5e59767e2e5f943492fbe24a04a2c64bb3f50ddecbcf81fa7` |
| `B4-1/gt_private/completion.json` | `67f6646cf695213151906d37314a1f3e41396adb3c441deb198583b862a8e40a` |
| `B4-1/gt_private/frame_integrity_summary.json` | `361d86f5fcc4f77de136648a1a31288764827fe82c277280f14c28f8d9cd38b1` |
| `B4-1/gt_private/safe_frame_inventory.json` | `2b797d69ac6c400f58bffac74496066f455c9b47173350e29498530d9bfb4173` |
| LOCAL independent audit `check_cx7_integrity.py` | `8a02cefb6c69749c967b4bab06e7dd2bf6fbcbd9a3b687ca302a7614fa659c17` |
| `gt_private/render_integrity_summary.json` | `f99585cacb5e6c81b04c02b26591b4c1fec2fec1f81c2f19349a64f8af0afe41` |

## 驗收界限與後續

- 2050 張實際 LOCAL 影像完整性／像素保真／GT 隔離檢查：PASS。此檢查不是 production bundle checker。
- 原渲染 checkpoint 的 production safe bundle checker 為 **NOT_RUN／CONTRACT_UNSELECTED**，當時 #353 只認明確的 TEST-ONLY `SYNTHETIC_EVENT_BUNDLE_V1`。其後 [D119](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6593904034) 已定案白名單投影，實跑結果見下方增量；原 staging 不回寫。
- D119 只選定工程機械投影；未選任何產品 contract 或提升 G4 authority。提案原9 GiB條件依 D118／D119 使用8 GiB。
- #118 正式索引／CX-8／P2：本次仍 NOT_RUN，D119 只解除 safe wire 這一項；其餘前置未在本任務驗證，未啟動模型。
- 可見性、偵測效果、切鏡效果、碰撞與身分：UNKNOWN；render 成功不代表這些驗收通過。
- LOCAL driver 與全量 logs 留在 GT 隔離區供獨立複核；單憑此 Markdown 不能完整重建媒體。

## D119 production wire 增量（2026-11-03）

`--profile r004-a4b4` 明確選擇固定的 D119 工程投影。不給 profile／options 仍為
`CONTRACT_UNSELECTED`；explicit contract options 仍只走原 SYNTHETIC -T 路徑。
本次真資料結果為 **PASS／ENGINEERING／D119**，不是 SYNTHETIC；
`human_approval_verified=false`、`allowed_purposes=[]`，產品 contract 仍為 `UNSELECTED`。

safe 只含 `manifest.json`、兩份 run descriptor、原 bytes 的兩 clock／catalog，以及
2050 張 RGB。manifest、run、sampling、frame 各層 exact keys 和完整檔案／父目錄集合均核對；
未知檔、空目錄、symlink、私有或其他多餘欄位皆 FAIL。frame hashes 同時對照外部兩份已 pin
producer safe inventory，不能靠重封 manifest／收據把替代像素說成原產物。PNG 另核 CRC、
RGB8 960×540、完整壓縮資料與 scanlines，拒絕文字／EXIF 及未知 chunks。

| 本輪機械驗證 | 結果 |
| --- | --- |
| A4-1 | PASS，250×4＝1000 張，50 s，5 fps，原 clock bytes |
| B4-1 | PASS，210×5＝1050 張，42 s，5 fps，原 clock bytes |
| 投影前／後可用磁碟 | 13438853120／13436141568 bytes |
| 投影每 camera 前後最低可用 | 13436141568 bytes（12.513381958 GiB），門檻8 GiB |
| checker 當下可用磁碟 | 13488967680 bytes |
| 既有渲染各段最低 | A4 13488558080／B4 12474224640 bytes；引用原渲染收據，沒有重測歷史磁碟 |

LOCAL 新輸出 `/private/tmp/amidst-cx7-wire-01a19f68-output/` 與原 staging 分開。
RGB 以 APFS clonefile 建獨立 inode，2050 張來源前／後及新副本 SHA 相符；不是共享可寫 hardlink。
只讀指定 sanitized inventories，沒有讀 frame journal／route／raw GT；原 safe、catalog、clock 不回寫。
外部 `receipt.json` 和其 `evidence/` sidecars 一起保留；inventory refs 相對該收據定位。
同名 repo JSON 是 curated 結果記錄，不能冒充 LOCAL checker input 或完整可重建媒體包。

| LOCAL 產物（相對新輸出根） | SHA-256 |
| --- | --- |
| `bundle/safe_bundle/manifest.json` | `60f2b5f8cdddf5096ffa9a25053260568570c40d8ea2737d6663f0ae3e3c2c82` |
| `receipt.json` | `9ab0c8ddcac82aac1f12001ac164068405adbad5d942f496099b75641f048f4a` |
| `checker.json` | `f5ef34938c2d6ce259aa3b0e89e8404bf6fb0907f8b8933744344a7373d2456c` |
| `materialization.json` | `db542f91dccc67557e3cf7ae290873b9a53c0ae60940c124a1112d1b6b02125a` |

LOCAL helper `/private/tmp/amidst-cx7-wire-01a19f68-project.py` SHA
`8640717587e2b75b93fc8e9ed652f7e0bb88efc6436ffaa6b6dec8201b28b5be`；
原 inventories SHA 仍為上方 `907615…b939`／`2b797d…4173`，沒有上傳 inventories／影像。

### 實際產出 / Actual output

- Model / effort: GPT-6（Codex；子代理同模型）／effort UNKNOWN。
- PR / commits: `codex/cx7-production-wire`，由 #394@`ed6a8dc8c62e833166beeb350f9a91e8c7db34ee` 開始；此收據與程式一併提交，精確交件 head 以 #279 回報為準。新 PR 等批次合完 #394 後才對 `mainline/q1q5` 開立，並加 `needs-claude-review`。
- Files changed: `scripts/check_event_run_bundle.py`、`tests/q1q5/test_check_event_run_bundle.py`、本 MD 與同名 JSON，僅四檔。
- Commands run and results: 下列命令只以 `<LOCAL existing Python>` 遮住既有 Python locator；未建立環境或安裝依賴。共用前綴 `PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/private/tmp/amidst-cx7-wire-01a19f68-cache`；測試另加 `AMIDST_REQUIRE_IMPL=1 PYTHONPATH=src`。
  - `uv run --no-project --offline --no-cache --python <LOCAL existing Python> python -m pytest -o addopts= -q tests/q1q5/test_check_event_run_bundle.py`：**176 passed，165.96 s**，含原83項及新增93項人工 production shape 測試。
  - 同一 uv 前綴後 `python -m pytest -o addopts= -q tests/evaluation/test_r004_script_freeze.py tests/unit/test_q5_script_adapter.py tests/q1q5/test_check_baseline_freeze.py tests/evaluation/test_p2_baseline_report.py tests/unit/test_architecture_guard.py`：**211 passed，12.89 s**；合計 **387 passed**。
  - 同一 uv 前綴後 `python /private/tmp/amidst-cx7-wire-01a19f68-project.py`：exit0，2050 張 MATERIALIZED；只有新 LOCAL 輸出。
  - 同一 uv 前綴後 `python scripts/check_event_run_bundle.py --profile r004-a4b4 --bundle /private/tmp/amidst-cx7-wire-01a19f68-output/bundle --receipt /private/tmp/amidst-cx7-wire-01a19f68-output/receipt.json > /private/tmp/amidst-cx7-wire-01a19f68-output/checker.json`：exit0，兩 run／2050 張 PASS；真資料未標 SYNTHETIC。
  - 同一 uv 前綴後 `python scripts/check_r004_script_freeze.py --freeze docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json --expected-freeze-sha256 ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb --report /private/tmp/amidst-cx7-wire-01a19f68-freeze.json`：exit0，candidate consistency PASS，13參照保持原 bytes。報告 SHA `d2e012288ef56b6044fdd65fd12db12c188f039743ad68aea901887f60b8797c`。
  - `python3 scripts/check_architecture_guard.py --base origin/codex/q1q5-staging --report /private/tmp/amidst-cx7-wire-01a19f68-guard-final-precommit.json`：不帶 `--allow`，exit0，authority／inference／schemas PASS，0 findings。提交後同指令另留 exact-head 報告於 LOCAL，hash 隨 #279 交件。
  - `git diff --check`：exit0。`git merge-base --is-ancestor 0502225bb16f117014fd875fc7a9281220ede484 HEAD`：exit1（預期，#348 未合）。額外僅 `python3 -m py_compile scripts/check_event_run_bundle.py`：exit0。
- Artifacts: 如上 LOCAL hashes 與同名 curated JSON。沒有媒體／GT／Blender／inventory 內容上 GitHub。
- Verified: D119-1～4 白名單與固定 source／freeze／G4 refs、原 clocks／catalog bytes、兩套 camera/index grids、PNG／hash／8 GiB，以及原 SYNTHETIC 行為。PASS 只表示 bundle 與外部收據機械一致。
- Not verified: 本次不重新讀取 Blender 來源 hash；render 前後 source pins 來自既有收據。本次未做推論、正式索引、CX-8、P2、AC7、物理／身分驗收，未重渲染或跑全套測試，未更動權威 schema、#348 或 `allowed_purposes`。
- Deviations, UNKNOWN items and follow-ups: uv 在 sandbox 的 macOS system-configuration 發生 NULL-object panic（exit101，測試未執行）；同一離線命令經擴權後使用既有 Python 完成。子代理初步 checker run 未取得最終 summary，列 UNKNOWN，不計入上述387項；上述176項為主代理最後完整重跑。[D121](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6594412627) 的 r004 run-bound 參數、Q3 timeout／attempts 核准未在本任務完成，故 A4/B4 推論仍 NOT_RUN；探索組上限不採用。凍結 `codex/feat-1-baseline` 不推新 head，審查 chat／clone 沒有介入。

## mainline PR 交件重驗（2026-11-03）

上節與同名 JSON 的 387 passed／staging guard 是 `49fac7121d9e52e2293c517f271fb3172d93ed65` 的歷史結果。本次在同一任務自有 clone，以普通 merge `8b9635fb3d66a544c55b89bf53abe65aee966ae0` 接上 `origin/mainline/q1q5@97030cd0b37240d78e832296bd6e89b5c95c018f`。wire 原四檔 bytes 當時與49fac71完全相同；本節及 [#118 產製前計畫](R004_INDEX_RECEIPT.md) 是後續文件增量，同名 JSON 與產品程式不回寫。

### 實際產出 / Actual output

- Model / effort: GPT-6（Codex）／effort UNKNOWN；兩個子代理只讀核對來源、限制與 #118 前置。
- PR / commits: `codex/cx7-production-wire` 對 `mainline/q1q5` 開 Draft PR，精確交件 head 與 PR URL 記在 PR 描述和 #115／#279。只 merge mainline，沒有 rebase、force 或遠端合併。
- Files changed: wire 原四檔；本輪只新增 mainline merge、此段重驗記錄與 `R004_INDEX_RECEIPT.md` 計畫。沒有手改 wire code／tests。
- Commands run and results:
  - `git merge --no-ff --no-stat -m 'Merge mainline/q1q5 into cx7 production wire after baseline batch' origin/mainline/q1q5`：無衝突，merge-base精確97030cd。
  - focused 實際使用既有 Python，外層 LOCAL supervisor 每秒讀 available bytes，低於8589934592 bytes即終止本測試 process group。其 pytest 子命令等同下列離線入口；未建立環境或下載依賴：

    ```sh
    PYTHONDONTWRITEBYTECODE=1 AMIDST_REQUIRE_IMPL=1 PYTHONPATH=src \
    uv run --no-project --offline --no-cache \
      --python /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/.venv/bin/python \
      python -m pytest -o addopts= -q -p no:cacheprovider \
      tests/q1q5/test_check_event_run_bundle.py \
      tests/evaluation/test_r004_script_freeze.py tests/unit/test_q5_script_adapter.py \
      tests/q1q5/test_check_baseline_freeze.py tests/evaluation/test_p2_baseline_report.py \
      tests/unit/test_architecture_guard.py
    ```

  - 結果：**383 passed／8 failed，209.06 s**。D119測試均通過；8項全部位於 `test_p2_baseline_report.py`，被 `Schema/validator differs from fixed kit 994d34c…` 拒絕。未把整組記為全綠。
  - 在本任務 clone 暫時 checkout exact mainline97030cd，用同一前綴只跑 `tests/evaluation/test_p2_baseline_report.py`：**13 passed／相同8 failed，0.82 s**，之後回到 wire branch。證明這8項是基底已有缺口，不是本wire新增回歸。
  - `scripts/check_p2_report.py` 仍直接以repo schema root載入固定994d34c bytes，且 `V1_SHA256` 仍為舊 `0fd1ef68…85d9f2`；#393合入後現行scorer為 `97564e40…b6d3dc`。這個下游P2整合缺口須由其擁有者處理；本次不放寬pin、不重產golden來掩蓋失敗。`Q1Q5_KIT_ROOT` 不會改掉該硬編碼root。
  - `python3 scripts/check_architecture_guard.py --base origin/mainline/q1q5 --report <NEW LOCAL report.json>`：無allow，authority／inference／schemas全PASS，0findings；交件commit另留exact-head報告，hash附PR與#279。
  - `git diff --check origin/mainline/q1q5 HEAD`：exit0。`git diff --exit-code origin/mainline/q1q5 HEAD -- configs/q1q5 docs/contracts src/amidst/contracts`：exit0。`git merge-base --is-ancestor 0502225bb16f117014fd875fc7a9281220ede484 HEAD`：exit1（預期，#348未合）。
- Artifacts: 本次LOCAL focused log／disk report／mainline P2重現及exact-head guard，SHA-256隨PR與#279登錄。既有真資料bundle／receipt／2050張結果僅引用上節歷史hash，本次沒有重開媒體或重跑真bundle checker。
- Verified: focused監測可用磁碟開始12438757376、最低11160547328、結束11352961024 bytes，全程高於8GiB，未觸發停止；凍結JSON及13參照原bytes保留，#348未合、`allowed_purposes=[]`保留；mainline guard採實際合併目標。
- Not verified: P2基底8項未修，整組focused不是PASS；全套、browser、正式index、推論／模型、原始來源／真bundle重驗、CX-8、P2正式驗收與AC7未執行。沒有重新渲染。
- Deviations, UNKNOWN items and follow-ups: #118僅交PLAN／NOT_RUN，依D121先完成run-bound核定與safe-only adapter／production index receipt decoder；不改凍結輸入、#348或用途。原dirty共用checkout與其他chat clone保持原狀，暫存不清理。
