> 2026-10-24：新版工程補件與交付見 [R004_REVIEW_V2.md](R004_REVIEW_V2.md)。本頁保留 v1 歷史，不代表 v2 仍缺入口或門洞資料。

# r004 工程前置審查與組員離線包（2026-10-23）

狀態：**REVIEW_REQUIRED / B，工程審查完成；獨立審查與人工作答未完成。** 本收據不核准 G4、新 HSV G6、物理通行、自動切鏡或正式評估。

## 實際輸入與範圍

- base staging `a958dd4043ebcd5ef2d9fdb362d15f8c4ce3941f`。
- 圖提案 [#163](https://github.com/Polalalabear/amidst/pull/163) head `4b2b8a78baaf0cf3f703935f4c5c79e1ec5b3161`；HSV 提案 [#158](https://github.com/Polalalabear/amidst/pull/158) head `71e0ef58b34da0cd3d3bc6c6e6cb9087caea8440`。
- 只讀已 pin 靜態 mesh、相機校正、8 張無人物靜態 PNG、8 張既有出口標示、35 張既有 HSV PREVIEW 裁切。
- 不渲染、不推論、不下載；不讀 GT、事件腳本、人物路線、visibility 或 depth。原始 Blender、r003、A/B1、來源圖檔、#127、#135 均未修改。
- 原 §11 初值 G6 與 D70 的 G5 授權保持原紀錄；尚待的是新 HSV 參數審查與 #117/O10/G4。不得把它們混成「所有初值／渲染都未授權」。

## 工程檢查結果

`R004_GRAPH_CHECK.json`：**221 項 PASS、0 FAIL、12 組待審缺口**。這是有限的 pin／結構／幾何檢查，並非完整 runtime、辨識正確率或核准收據。

- 7 區域 mesh 與來源頂點／面、6 邊、8 校正、8 出口、17 轉移核對；8 張原圖及8張標示圖可解壓，尺寸一致。
- 驗檔案及 canonical hashes、宣告 inputs／scene／graph IDs、右手正交 PINHOLE 校正、簡單非退化影像內出口、方向／邊狀態／路徑權限／出口引用。
- 嚴格限制本次 DRAFT proposal；拒絕升權輸入。`legal_auto_switch_paths=0` 是保守審查值，本工具不驗證外部核准收據。
- 地圖由來源 mesh 每片面之 XY 投影與鏡頭校正生成，沒有用 AABB 補地板或補洞；鏡頭箭頭只是光軸方向，不是可見範圍。
- ROI 的 z=0 射線交點僅為診斷，不證明遮擋、實際門檻、可行走範圍、重疊比例或接回時限。

## 必須保留的缺口

| 現況 | 審查所需處理 |
| --- | --- |
| 6 邊、17 轉移仍 TOPOLOGICAL_ONLY，來源用途未核准 | 不能只改 APPROVED 字串就當合法候選；需要獨立收據與指定用途核定 |
| 8 台入口區域全空，9 個轉移缺反向 | 依靜態證據補入口／方向範圍；不可看事件答案倒補 |
| `CAM_R101_IN` 入向轉移 0；ENTRY 僅連外景，W1/W2 同區轉移未列 | 現圖不支援追入 R101，也未證完整候選覆蓋 |
| 17 條 relation UNKNOWN、距離／面積 null | 無可靠重疊比例與追丟 timeout 的量測 |
| 3 個 portal semantic refs 未綁實際開口寬高 | 表示證據缺少，不表示場景沒有門 |
| safe_static 22 個 WALL 物件含負 Z 且無有效／隱藏／collection membership | 不把全部 WALL 當已核定遮擋體；未證明 transform bug |
| ENTRY 前景接近區、EXT_CAR 遮擋、W1 提早觸發、W2 長深度 | 組員並排看原圖及標示，填支持／反駁／不確定與理由 |
| R102 | 保留 TOPOLOGICAL_ONLY 限制，不在本次順便解除 |
| HSV 35 PREVIEW、5 框紅藍皆 STRONG，無獨立人工 truth | 只做參數工程意見；不能算正式 T/F 或準確率；WEAK 不等同確定有 |

完整逐項 refs 與逐台面積／HFOV／投影診斷見 JSON。CAM_WIDE 維持使用者選定的 90°。

## 交付給組員的一包

LOCAL：`~/amidst-artifacts/r004-prereview-team-v1_20261023/`。開 `START_HERE.html`，不需 repo、模型、Git 或 Python。

- 121 項：8 鏡頭對應、8 出口、6 區域邊、17 轉移、12 待決缺口、35×2 紅／藍 PREVIEW。人工答案與日期留白；頁面姓名預填 `yyin`，匯出 CSV 帶入此姓名。
- 51 PNG 加 1 SVG；全部相對路徑。原圖／標示並排，詳細 context、路徑及證據引用均可看見。
- 可篩選、逐項填答、匯出 UTF-8 BOM CSV、匯入續填。F／不確定必填原因；所有缺口項連 T 也必填原因。未分工／未填列回報 INCOMPLETE，不補答案。
- `templates/`、圖檔及 DATA 固定。瀏覽器下載 CSV 放到 `RETURN/`；整包和 CSV 一起交回。MANIFEST 驗原始範本／圖片／固定欄，另記回收 CSV 新 hash。
- 71 個不可改檔案；MANIFEST SHA-256：`34d863036e44effc7f425c211c9190f28c5d16d77c53fcfbcb15ac36fb346d54`。此獨立 hash 是驗證錨點，不以使用者可修改的 manifest 自我證明。
- 8 張靜態 PNG 的文字／EXIF 私有路徑只在新匯出副本移除，IHDR、IDAT 位元組完全保留；所有 51 張檢查 CRC、非交錯8bit模式、bounded zlib 與 scanline filters。來源檔案 hashes 未變。
- `OWNER_DECISIONS.csv` 是另交指定核定者的建議表，不是可執行核准；工具不修改 proposal 或 gate。

這包是**靜態前置審查＋HSV 參數 PREVIEW**。正式 A4/B4 RGB、正式偵測索引、預先固定抽樣與盲審 T/F 仍需後續完成，不能拿本包替代。

## 驗證與實際限制

- #127仍為外部OPEN測試包，固定head `994d34c8340855dbf0e28d0273851049df5e6c7d`，並非staging已合入檔案；本次3個程式／unit來源逐byte核對該head一致，沒有將它們納入本PR。
- unchanged #127 unit：**223 PASS**；checker：**25 PASS**；package：**21 PASS**（另含43個 unittest subtests）；UI utility：**21 PASS**；JS syntax、7個新增Python檔 Ruff、diff whitespace PASS。
- unchanged #127 kit 對凍結圖、8 組空候選 snapshot 與既有 parameter_set：**82 PASS、0 FAIL、0 SKIP，overall PASS**。未提供 params 的第一次為69 PASS/8 SKIPPED_PARAM_UNSET、INCOMPLETE；補入既有參數後重跑，沒有改測試包。
- 實包71個hash、121列固定欄／圖片引用／DATA與data.js一致性、51個來源與副本像素編碼核對通過。空白回收為 INCOMPLETE121／INVALID0；獨立合成傳輸測試為 VALID且approval=false，合成資料未放入交付包。
- 真瀏覽器及 Windows 離線操作 **NOT_VERIFIED**。Chrome 控制工具拒絕 `file://`（只允許 http/https），同時要求不得繞過；已停止該嘗試，未改用 server 或其他瀏覽器繞過。首次實機開啟仍須確認圖片、匯出與續填。
- 工程檢查／Codex 子任務互查不等於契約指定的 Claude 獨立檢查或使用者核准。本 PR 等級 B，不宣稱已完成 #117/G4。

## 重現

本機使用現有 Python 環境，`PYTHONPATH=src`，`PYTHONDONTWRITEBYTECODE=1`；不下載依賴。LOCAL 輸入 locator 不分發：

```sh
uv --no-cache run --no-project --offline --python /path/to/existing/python python scripts/check_q1q5_graphs.py \
  --config /path/to/inputs.json --config-sha256 2ebcaa8cbc63a534196c4c1394492c6c59c6f6bf5764c8544004460fa456209f \
  --output /new/path/GRAPH_CHECK.json
uv --no-cache run --no-project --offline --python /path/to/existing/python python scripts/build_r004_prereview_pack.py \
  --config /path/to/inputs.json --config-sha256 2ebcaa8cbc63a534196c4c1394492c6c59c6f6bf5764c8544004460fa456209f \
  --report /path/to/GRAPH_CHECK.json --report-sha256 8a07aeb754b1deee409ce556879821cbda02d078d0e85c18b65daf672e038f9a \
  --output /new/path/team-pack
PYTHONDONTWRITEBYTECODE=1 python team-pack/tools/verify_bundle.py \
  --manifest-sha256 34d863036e44effc7f425c211c9190f28c5d16d77c53fcfbcb15ac36fb346d54
PYTHONDONTWRITEBYTECODE=1 python team-pack/tools/verify_bundle.py \
  --manifest-sha256 34d863036e44effc7f425c211c9190f28c5d16d77c53fcfbcb15ac36fb346d54 \
  --returned-csv team-pack/RETURN/審查表_yyin_YYYY-MM-DD.csv
```

回收程式只驗固定內容、枚舉、完整度與新 hash，回傳 VALID／INCOMPLETE／INVALID；不授予任何 gate 或改寫原始資料。輸出資料夾必須不存在，磁碟低於8GiB立即停止。私有原始 locator、合成填答探針、測試環境／hostname 不進組員包。

## 磁碟實測

最終產製前／後 `df -k` 可用：13,659,752 → 13,651,764 KiB（變化 -7,988 KiB；系統同期差額不等於資料夾大小）。本包新增 7,916,475 bytes（7.550 MiB）。全程高於8GiB，無清理或刪除來源。原始df輸出保留在LOCAL任務收據。

## yyin 交件說明更新

依使用者要求，README與HTML最上方明列「這份工作內容」及「要提交項目」：121項審查、回收CSV、整包資料夾／ZIP、已審與未完成項目說明。頁面姓名預填`yyin`，匯出檔名為`審查表_yyin_YYYY-MM-DD.csv`（未完成加`_INCOMPLETE`）；匯入空白CSV仍保留預填姓名。既有RETURN檔逐byte保留，圖片與人工答案未改。

本次重跑package21項（另43subtests）、UI21項、JS syntax與Ruff通過；71個locked files驗證通過。最終包7,920,182 bytes。更新前／後df可用13,665,340→13,665,220KiB（-120KiB），高於8GiB。真瀏覽器／Windows仍未驗，不把文字及靜態檢查當瀏覽器驗收。
