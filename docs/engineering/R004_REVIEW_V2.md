# r004 完整靜態審查包 v2（2026-10-24）

狀態：**工程補件供審完成／REVIEW_REQUIRED／B**。資料夾、圖與建議均未授予G4／新HSV G6，不是正式baseline或辨識驗收。

## 本次補齊的實際資料

| 項目 | v2實際產出 |
| --- | --- |
| 入口／出口 | 8台均有入口；共12個有邊引用的出口支持區。每塊0.8×0.8m標示面完整覆蓋於來源矩形floor cells聯集，保留缺口，未用AABB補面 |
| 靜態射線 | 20塊標示×9個足平面見證點＝180；校正投影均在原圖範圍內，並對4,120個有效靜態三角面作segment測試 |
| 門洞 | 西入口1.40×2.40m；R101與R102各1.20×2.40m。附WALL_JOINED_SHELL原面索引、mesh hash、世界座標開口四角及立面圖 |
| 有效幾何 | 43個白名單物件逐項檢查：15個render-enabled、6個WALK支撐標記、22個隱藏聯集輸入；隱藏輸入不當遮擋體 |
| 方向 | 22個非空邊路徑、全部有目標入口引用且成對；包含W1／W2→R101與反向。6個未核定完整重疊的同區方向另列排除，不藉空邊標籤取得權限 |
| 范圍提案 | 第一版持續追查先W2／R101、單目標、固定run／時間範圍；R102不進追蹤。原A4／B4產製規格不改 |
| 審查材料 | 132列空白人工判斷、43張原始export PNG、12張SVG、yyin預填頁面、README／具體提交要求、BASELINE_READINESS.md |

舊v1資料夾及全部RETURN檔保留；新包不是覆寫v1。舊CSV固定材料已不同，不直接匯入v2，也不替組員沿用已改項目的T。

## 來源與方法

- 只讀衍生r004 `.blend` SHA-256 `466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b`；前後hash一致。
- Blender **5.2.1 LTS**，`--background --factory-startup --disable-autoexec`；按已pin safe_static的43個物件名逐項取metadata，不查人物、動畫、事件、GT或renderer visibility/depth，不save或render。
- 原static file SHA `bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a`；calibration catalog `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`；membership bytes `e71f6ad16868ab450bcd093eb50f6fd7ca4a393c73689055235e9505f9e48ca7`。
- membership確認22個負Z／原點牆體屬`WALL_UNION_INPUTS_SOURCE_ONLY`且hide_render=true；不是新改場景或猜測transform bug。WALK標記雖hide_render，獨立保留為待核定支撐annotation，不當可見牆體。
- 開口尺寸由實際牆殼平面face cells的低部缺口求得，附精確來源面；不是靠門名、AABB、人物框或事件路線猜。
- 入口／出口由來源floor cells、PINHOLE校正及名義靜態遮擋面產生。0.25m定位grid、0.40m半寬是**離線標示方法**，不是新增runtime追蹤門檻。
- 原圖維持v1清理後的IHDR／IDAT；SVG以同一PNG的data URI作底，不改RGB像素。舊私有文字／EXIF已剝除；原始PNG未修改。
- 原static／calibration／mesh／HSV／membership資料保留原檔bytes；新增portal／patch文件以實際分發bytes記hash。Graph inputs逐一交叉驗證；PNG refs保留原始source hash，另以media_exports記匯出hash及pixel encoding。
- 場景物件名僅供幾何核對；目標存在、類別與框仍由RGB模型產生，不以車體mesh名或Blender資料回答查找。

## 範圍與不確定性

入口／出口是**地面接近／接回支持區**，不是精確門檻、首次可見邊界或人物必經路線。9點靜態射線不能證明整個人體可見、全場完整覆蓋、重疊比例、可靠接回時限或物理安全。

所有6個region edge維持TOPOLOGICAL_ONLY；22個camera path亦同，graphs仍DRAFT、approval_ref=null。R102尺寸雖可量測，限制沒有解除。沒有自動把測量或組員T換成APPROVED。

## 驗證結果

- 新幾何／SVG **15 tests PASS**；舊checker **25 PASS**；pack **21 PASS**（另43 subtests）；原#127 kit **223 PASS**。來源為固定工程source composition，非全repo suite。
- 實際production graph loader讀新版分發資料PASS；8台以明示SYNTHETIC bbox做fail-closed probe，均0 candidates；不把probe當人物觀測或真RGB baseline。
- 原#127固定`994d34c8340855dbf0e28d0273851049df5e6c7d`，對新版兩圖＋8 probe snapshots＋既有params：**82 PASS／0 FAIL／0 SKIP**。這是本包靜態資料檢查，不能聲稱#145產品端所有既有差異解除。
- 分發app的CSV utility **21 PASS**，JS syntax PASS；新4個Python檔Ruff PASS；commit範圍diff whitespace檢查另記。
- **80 locked files**／132列固定欄及全部image refs核對；DATA/data.js一致；原圖base64底圖逐byte一致；所有12 SVG parse／Sharp渲染PASS，並視覺檢查關鍵W2、R101、EXT_CAR、門洞、總圖。
- 空白回收INCOMPLETE132／INVALID0；另在包外以SYNTHETIC傳輸probe驗VALID且approval=false，沒有分發合成作答。
- 真瀏覽器／Windows **NOT_VERIFIED**。保留既有工具file-protocol限制，未以替代server／browser繞過；原生SVG渲染不當瀏覽器驗收。

## 新交付包與核對錨點

LOCAL `/Users/polalabear/amidst-artifacts/r004-prereview-team-v2_20261024/`，MANIFEST SHA-256 **`531a6539cb6db379630e4d3b62d2b9df83baf0ee136f27af70ad1b841089c8c4`**；共83檔、10,733,351 bytes。先看README，開START_HERE.html；人工姓名yyin、日期與判斷待填。CSV放RETURN，整包及交件說明回收。

原始config locator不分發。資料夾可離線使用，不需repo／模型／Git／Python；工具驗hash需Python標準庫：

```sh
PYTHONDONTWRITEBYTECODE=1 python tools/verify_bundle.py --manifest-sha256 531a6539cb6db379630e4d3b62d2b9df83baf0ee136f27af70ad1b841089c8c4
```

重建使用`scripts/build_r004_review_v2.py`與`--config/--config-sha256/--membership/--membership-sha256/--prior-pack/--prior-manifest-sha256/--output`；輸出必須全新，原config SHA `2ebcaa8cbc63a534196c4c1394492c6c59c6f6bf5764c8544004460fa456209f`，v1 manifest `34d863036e44effc7f425c211c9190f28c5d16d77c53fcfbcb15ac36fb346d54`。本包與scratch release重建manifest位元組一致。

產製前／後`df -k`可用 16,142,668→16,147,996KiB（+5,328KiB）。資料夾實際bytes與系統差額分列；全程高於8GiB，沒有清理／刪來源。

## yyin審查期間可同步完成

1. 固定source composition，整合RULE_ONLY／Q1/Q4/Q2／HTTP／UI；以測試資料與既有recorded replay驗失敗路徑。
2. 產品端既有違規由Codex修；#145／#127由Claude對齊，Codex提供最小重現，不改獨立測試包或#135。
3. 正式render／index配置、source/hash/scope/disk預檢；圖與必要參數凍結前不產正式事件RGB。
4. 完成兩模式測量入口、紀錄格式與報告：冷暖查找、處理／顯示fps分列、RSS、逐次接回／切鏡與offline replay。

以上不得回改正在審的包。獨立檢查／G4／新HSV核定及程式整合通過後，依既有D70授權產正式A4/B4→索引→兩模式baseline→輸出凍結→人工T/F與評分。Windows可執行包、Qwen／YOLO-World／ReID比較後排。
