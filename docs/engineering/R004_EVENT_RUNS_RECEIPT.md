# r004 CX-7 A4-1 / B4-1 渲染收據

日期：2026-11-03（Asia/Taipei）；FEAT-1 #376／CX-7 #115，交件 PR #394。

## 範圍與 gate

此收據記錄已產生的 LOCAL RGB 與去中繼資料的 safe staging；production safe bundle 尚未驗收。
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
- production safe bundle checker：**NOT_RUN／CONTRACT_UNSELECTED**。#353 現有 checker 只認明確的 TEST-ONLY `SYNTHETIC_EVENT_BUNDLE_V1`；真資料不偽標 SYNTHETIC。
- production manifest／receipt 機械投影：[A/B 定案請求](https://github.com/Polalalabear/amidst/issues/376#issuecomment-6579455945) 等 Claude（D104-3）。提案原9 GiB條件受 D118 的8 GiB特例取代。未採納前保持 staging，不宣稱 safe bundle 正式驗收通過。
- #118 正式索引／CX-8／P2：NOT_RUN，先等上述 safe wire 與各自前置；未啟動模型。
- 可見性、偵測效果、切鏡效果、碰撞與身分：UNKNOWN；render 成功不代表這些驗收通過。
- LOCAL driver 與全量 logs 留在 GT 隔離區供獨立複核；單憑此 Markdown 不能完整重建媒體。
