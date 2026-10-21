# r004 建檔、靜態校正與 45 格 preview 收據

日期：2026-10-21（Asia/Taipei）。Refs #113、#132、#114。**實際狀態：PREVIEW_MATERIALIZED／HFOV_SELECTED_90／STATIC_DRAFT；不是正式 run 或 Demo 驗收。** D70 已授權本批產製；D71 中性環境色／每台出口要求保持。G4、#117 圖／ROI 獨立檢查仍未完成，沒有渲染 A4／B4 事件。

## 1. 實際 LOCAL 產物與來源鏈

| 產物 | LOCAL locator | bytes SHA-256 |
| --- | --- | --- |
| 原 r003（未改） | repo 的 `data/pilot/controlled_scene_v1/assets/controlled_scene_v1_s001_r003.blend` | `6e7de38dc069d330e0ffbb6c0051cdab304566fdbb7e3e8dfb429af863ae6d8e` |
| r004 v1（失敗證據保留） | `/Users/polalabear/amidst-artifacts/r004-build-20261021/controlled_scene_v1_s001_r004.blend` | `f079c8b055c0030445b088d50fa4e7866a7ed4553fefc4cf8af8dd4ab899aea8` |
| r004 v2（本次候選） | `/Users/polalabear/amidst-artifacts/r004-build-v2-20261021/controlled_scene_v1_s001_r004.blend` | `466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b` |
| v2 靜態相機（8 台，無 run bindings） | `/Users/polalabear/amidst-artifacts/r004-build-v2-20261021/safe_static/cameras.json` | `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f` |
| v2 靜態幾何提案 | `/Users/polalabear/amidst-artifacts/r004-build-v2-20261021/safe_static/static_geometry.PROPOSED.json` | `bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a` |
| v2 靜態匯出收據 | `/Users/polalabear/amidst-artifacts/r004-build-v2-20261021/static-export-receipt.json` | `32f72b328d773a895ebdcda5505d91b1d95a14f98459bd8c1a6bab632993c628` |
| v2 preview RGB 索引（45 格） | `/Users/polalabear/amidst-artifacts/r004-build-v2-20261021/preview45/rgb_index.json` | `44c969cb108c39794d4ed60a56d278b116a2540076738f0d63dd5c24bb914eb1` |
| v2 preview 變體相機（含 WIDE 100°） | `/Users/polalabear/amidst-artifacts/r004-build-v2-20261021/preview45/cameras.json` | `fa471d54348c3556b49172a2888c9e34b888b535611778a5590dac4aca2cf016` |
| v2 實際 RT-DETR 原始候選輸出 | `/Users/polalabear/amidst-artifacts/r004-build-v2-20261021/preview45/perception/detections.jsonl` | `5228d20c4d79ffb2495a427ed46177caa2eccc013c037267f94ddfaf736193f1` |
| v2 量測報告 | `/Users/polalabear/amidst-artifacts/r004-build-v2-20261021/preview45/perception/report.json` | `7513d0bd93083d4bf6f5ec0488483ec73ea173eeb72e048f7d5c0f8c810aa857` |

完整逐檔 hash 在同目錄 `ARTIFACT_HASHES.json`。產製腳本與 private preview poses 留在 LOCAL；它們不是 runtime／索引／圖／參數輸入。靜態匯出排除所有 `PRODUCTION_` 人物物件，不輸出 actor IDs／路線／逐幀 visibility／depth。幾何是 `q-demo.static-geometry-proposal.v1`、`DRAFT`、`allowed_purposes: []`；尚未宣稱可直接作核准 `controlled-scene.static.v1` safe bundle 使用。

v1 的入口鏡頭視線被牆擋住，完整保留；v2 只修入口鏡頭位置／方向、加強非全白中性牆地色與室外補光。原 r003 不改，A／B1 不改。r004 的新增西側入口、室外地面、靜態車輛幾何、鏡頭與材質都是新 source 的設計，沒有通行／碰撞核准。

## 2. 校正與靜態畫面

實際 Blender 5.2.1 LTS，來源單位 `scale_length=1.0`；8 台 pinhole、960×540、square pixels、sensor fit HORIZONTAL、lens shift 0、主點 (480,270)。`camera_to_world` 用 `BLENDER_NEG_Z_UP_Y`，像素 `TOP_LEFT_CONTINUOUS`。K 由實際 lens/sensor 算出，並核對旋轉矩陣正交性；不是像素重投影誤差或鏡頭安裝可用性驗收。

| camera_id | fx px | fy px | cx,cy px | calibration_sha256 |
| --- | ---: | ---: | --- | --- |
| CAM_BRANCH | 625.548197 | 625.548197 | 480.0, 270.0 | `605ca41caec1f6dfbf8bcd831248d54196140b0200d990289606f56e6f0e7c53` |
| CAM_ENTRY | 625.548197 | 625.548197 | 480.0, 270.0 | `e5cc2f5a2408c4513d3edc3e081db9f10a7ded8e73d0fd74442ec25fe1170ec3` |
| CAM_EXT_CAR | 685.511068 | 685.511068 | 480.0, 270.0 | `63efc5c148a499108a4999b8fa1233c2ec30db21610757dd7dc2ab23e0ac6319` |
| CAM_EXT_CLEAR | 685.511068 | 685.511068 | 480.0, 270.0 | `a4f32c45e5913b2a489d1c68ac280842568b56d313a976a90dac631e9558e057` |
| CAM_R101_IN | 685.511068 | 685.511068 | 480.0, 270.0 | `950deeeae2adb18f1d62b8a79095a4efc702b256894fca997d4068f7601e45d1` |
| CAM_W1 | 625.548197 | 625.548197 | 480.0, 270.0 | `72a75795c183e0204ead20e6a63e54a73661ce0e1f610b924d485fa2fc89fe47` |
| CAM_W2 | 625.548197 | 625.548197 | 480.0, 270.0 | `3d505ab7fc81732ca4c21c1f8703410cec444bff286f570c3a4ac59f46924010` |
| CAM_WIDE | 480.000000 | 480.000000 | 480.0, 270.0 | `302614556073b2a4bf3cde6270f5ac8c78ca806f583884a7b4656bd39fa225b4` |

v2 的 8 張無人物靜態畫面位於 `safe_static/frames/<camera_id>.png`。WIDE 的 source 已存90°，100°保留獨立preview calibration。**使用者已於本chat明確選90°（保留較大人物框）**。再次核對v2 source/cameras檔SHA與CAM_WIDE calibration pin一致，width=960、fx=480推得HFOV90°，不必改source或重渲染。選擇收據 LOCAL `/Users/polalabear/amidst-artifacts/r004-hfov-selection-20261021/receipt.json`；該選擇只定HFOV，不核准G4/G6或辨識品質。 Camera graph／每台出口 ROI 尚未由 #116 產製與 #117 檢查，正式事件不得先跑。

## 3. 實際 preview 與模型量測

八台各 5 格，WIDE 100° 另加 5，共 45 格；每組為獨立 calibration preview，不是 A4／B4 事件、不是到達時間或追蹤答案。所有 PNG 的 hash／格式／960×540 已逐張核對。v1 靜態用 Cycles，v1/v2 calibration preview 與 v2 靜態使用 Eevee；實際 renderer／產製設定留在 LOCAL，沒有混稱現實相機影像。

RT-DETR 使用既有官方 R18，zip pin `e6014ae32d2d384799e353a7a6a511aaef1dad77763492738dfef70e714d6564`，逐一核對 `src/*.py` 與該 zip；權重 SHA-256 `3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0`，strict load、80 類、CPU 2 threads、seed 7、無 NMS／無下載。報表門檻 0.30 是 **PROPOSED_REPORTING_ONLY**，不是正式 index_score_floor 或使用者核准閾值；原始 top-300 候選另存。

| preview variant | 有 person 判定格／輸入格 | person 框數 | 高度 min / P25 / median / P75 / max（px） | forward median（ms/格） |
| --- | ---: | ---: | --- | ---: |
| CAM_BRANCH_hfov75 | 0/5 | 0 | None / None / None / None / None | 242.514 |
| CAM_ENTRY_hfov75 | 0/5 | 0 | None / None / None / None / None | 243.546 |
| CAM_EXT_CAR_hfov70 | 0/5 | 0 | None / None / None / None / None | 253.134 |
| CAM_EXT_CLEAR_hfov70 | 5/5 | 10 | 156.16665649414062 / 162.4509620666504 / 169.79776763916016 / 177.26848602294922 / 194.89895629882812 | 242.393 |
| CAM_R101_IN_hfov70 | 5/5 | 6 | 231.29959106445312 / 233.38714599609375 / 240.94955444335938 / 249.76124572753906 / 254.25682067871094 | 242.545 |
| CAM_W1_hfov75 | 4/5 | 6 | 132.8378448486328 / 138.88894271850586 / 143.96295166015625 / 147.89185333251953 / 152.12747192382812 | 241.917 |
| CAM_W2_hfov75 | 0/5 | 0 | None / None / None / None / None | 241.708 |
| CAM_WIDE_hfov100 | 5/5 | 6 | 83.54730224609375 / 98.95671081542969 / 101.88948822021484 / 106.01679992675781 / 107.1636962890625 | 242.107 |
| CAM_WIDE_hfov90 | 5/5 | 7 | 101.10337829589844 / 115.22827911376953 / 122.42355346679688 / 124.4842529296875 / 127.02423095703125 | 241.591 |

未檢出組的高度為 `null`，沒有填 0。這些是模型輸出；沒有 GT 或人工標註分母，**不是 recall／accuracy**。ENTRY／EXT_CAR／BRANCH／W2 此設定均為 0/5，實際 RGB 中可見人物的情況仍可能漏檢；不能宣稱人物／車輛品質已可用。WIDE 90° 的框較大，僅作HFOV選擇的量測依據；使用者已選90°，並非品質驗收。

## 4. 磁碟與重現

每次建檔、靜態渲染、preview 與推論前後都有 `df -k` 收據，render／inference 逐格檢查 available ≥8 GiB；本次記錄的最低 available `12213872` KiB。沒有刪任何快取、權重、venv、PG 或資料。兩個自有目錄目前 allocated usage：`27052` KiB（v1）／`29144` KiB（v2），合計約 `54.88` MiB。磁碟為共享，df 差值不全歸因本任務。

重現只對**新的 output 目錄**執行，不能覆蓋這些 source／收據：LOCAL `build_preview.py`／`build_static_v2.py`、`render_previews.py`、`measure_preview.py` 記錄實際參數。Blender 背景執行讀指定 parent source，再另存新 LOCAL；Python 用既有 3.12 interpreter 與既有離線 torch dependencies，不新建 venv 或 worktree。可重現輸入要核對上列 source、官方 zip/code/weights pins；若依賴目錄遺失，不承諾只靠此文件即可完整復原。

## 5. 實際驗證與剩餘工作

Verified：原 r003 hash、兩版 source hash、45 PNG pins/尺寸、8 台校正 K／pose 數學一致性、靜態匯出不含人物、來源／calibration／preview／detector refs、df 記錄；文件 `git diff --check`。

Not verified／待辦：#116 每台出口／靜態兩層圖與凍結；#117 獨立檢查／G4；HSV／正式參數核准；正式 A4／B4／safe bundle／index／Controller／HTTP／browser。未讀評估劇本或 GT，未產事件、未發布媒體或 `.blend` 到 Git。
