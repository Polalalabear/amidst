# r004 graph v3 — CX-3 / D74 / D77

PROPOSED／DRAFT，G4 未核，legal_auto_switch_paths=0。只用 #187 的 safe 靜態幾何／calibration／membership 與靜態圖片；事件／GT／renderer visibility/depth 未讀，未渲染／保存 .blend 或移動相機。父版本 #187 @ 9402c91588205bccc972a8efad0b1a9512e3c823，PR base staging。

## 十項處置

1. W1 各邊補新版入口：R101 指 E_PORTAL_R101，EXT 指 E_VEST_CORR，BRANCH/WIDE 指 E_W_CORNER。
2. W2 E_VEST_CORR 改到九點可見的 VEST_W 並加入 covered_regions；R101、EXT、BRANCH/WIDE 分別指 portal、vestibule、corner approach。W2 corner patch 是鏡頭前方可見接近區，距實際轉角約4m，不能聲稱人已到轉角或可見首次出現。
3. EXT_CAR 南北各一塊地面入口與出口，都 leads_to E_OUT_VEST，每塊九點靜態見證。這是車側接近區，距門洞數公尺，不等同實體門檻或已知行走路線。
4. BRANCH E1/X1 推入 CORNER 並加寬至完整2.4m，另補 E_CORNER_N 出口；covered_regions 增 CORNER。新增出口不解除 D77 的 BRANCH↔WIDE 排除。
5. WIDE E1/X1 加寬至1.8m並增 CORNER；全寬會有3/9足點被 screen 遮擋，故不冒充全寬。加 E_PORTAL_R102 出口，edge 維持 TOPOLOGICAL_ONLY、零合法候選；y>12 明列 OUT_OF_GRAPH。90° PINHOLE 未動。
6. 56有向對全列：20轉移、36附理由的排除；D77排除 BRANCH↔WIDE、EXT_CAR↔EXT_CLEAR，W1↔W2不在本版盲區搜尋。其餘排除只表示未涵蓋，不宣稱幾何不可能。
7. CAM_ENTRY 依 D74 只供Q1，查找8台、追蹤7台；不虛造ROI、不移鏡頭。Q2/index需綁定顯式tracking scope，不能默默容忍不一致。
8. 每塊ROI像素外框、九點相機深度與1.7m假定人物像素高如下。指定小ROI可在 LOCAL 靜態 SVG／瀏覽器使用100–400%放大，僅改善顯示；辨識仍 UNVALIDATED，證據不足回 AMBIGUOUS/UNKNOWN，不新增 runtime 門檻。
9. 可選 relation/ranking_area_m2 維持 UNKNOWN/null，沒有新增共同可見面積排名。
10. 固定ID見下表、JSON及完整pins；所有圖hash/derived ID重算，原包80鎖定檔驗證未改。

## X 標號與固定 ID

| camera | 舊X標號 | 新版後綴 |
|---|---|---|
| W1 / W2 | X1 / X2 / X3 | E_PORTAL_R101 / E_VEST_CORR / E_W_CORNER |
| EXT_CAR | 南／北接近區 | SOUTH_APPROACH / NORTH_APPROACH |
| BRANCH | X1／新增北側 | E_W_CORNER / E_CORNER_N |
| WIDE | X1／新增R102 | E_W_CORNER / E_PORTAL_R102 |
| EXT_CLEAR / R101_IN | X1 | E_OUT_VEST / E_PORTAL_R101 |

ID=`CAM_*:ENTRY_V3:<後綴>` 或 `CAM_*:EXIT_V3:<後綴>`。BRANCH北側與WIDE R102只有EXIT；完整表以 static_patches_v3.json 為準。

## 像素與深度（九點 min–max）

| ROI ID | bbox xyxy px | depth m | 1.7m height px |
|---|---|---|---|
| CAM_BRANCH:ENTRY_V3:E_W_CORNER | 280.4, 306.8, 587.1, 386.3 | 4.62–5.91 | 182.8–229.3 |
| CAM_BRANCH:EXIT_V3:E_CORNER_N | 385.7, 383.8, 523.6, 468.6 | 3.77–4.65 | 227.9–275.1 |
| CAM_BRANCH:EXIT_V3:E_W_CORNER | 280.4, 306.8, 587.1, 386.3 | 4.62–5.91 | 182.8–229.3 |
| CAM_EXT_CAR:ENTRY_V3:NORTH_APPROACH | 57.5, 410.2, 213.7, 490.2 | 4.87–5.91 | 191.4–227.1 |
| CAM_EXT_CAR:ENTRY_V3:SOUTH_APPROACH | 627.3, 333.2, 728.7, 381.7 | 6.39–7.43 | 155.1–178.1 |
| CAM_EXT_CAR:EXIT_V3:NORTH_APPROACH | 57.5, 410.2, 213.7, 490.2 | 4.87–5.91 | 191.4–227.1 |
| CAM_EXT_CAR:EXIT_V3:SOUTH_APPROACH | 627.3, 333.2, 728.7, 381.7 | 6.39–7.43 | 155.1–178.1 |
| CAM_EXT_CLEAR:ENTRY_V3:E_OUT_VEST | 669.0, 238.4, 739.3, 254.7 | 10.92–11.88 | 99.2–107.5 |
| CAM_EXT_CLEAR:EXIT_V3:E_OUT_VEST | 669.0, 238.4, 739.3, 254.7 | 10.92–11.88 | 99.2–107.5 |
| CAM_R101_IN:ENTRY_V3:E_PORTAL_R101 | 420.2, 356.1, 564.7, 426.3 | 4.69–5.74 | 203.7–245.9 |
| CAM_R101_IN:EXIT_V3:E_PORTAL_R101 | 420.2, 356.1, 564.7, 426.3 | 4.69–5.74 | 203.7–245.9 |
| CAM_W1:ENTRY_V3:E_PORTAL_R101 | 487.7, 314.7, 545.2, 325.9 | 10.02–11.02 | 96.8–106.4 |
| CAM_W1:ENTRY_V3:E_VEST_CORR | 117.4, 466.1, 298.5, 536.4 | 3.75–4.74 | 224.2–282.9 |
| CAM_W1:ENTRY_V3:E_W_CORNER | 510.2, 276.5, 547.5, 281.4 | 15.54–16.54 | 64.6–68.7 |
| CAM_W1:EXIT_V3:E_PORTAL_R101 | 487.7, 314.7, 545.2, 325.9 | 10.02–11.02 | 96.8–106.4 |
| CAM_W1:EXIT_V3:E_VEST_CORR | 117.4, 466.1, 298.5, 536.4 | 3.75–4.74 | 224.2–282.9 |
| CAM_W1:EXIT_V3:E_W_CORNER | 510.2, 276.5, 547.5, 281.4 | 15.54–16.54 | 64.6–68.7 |
| CAM_W2:ENTRY_V3:E_PORTAL_R101 | 375.4, 345.4, 462.3, 366.3 | 6.53–7.43 | 144.1–163.8 |
| CAM_W2:ENTRY_V3:E_VEST_CORR | 514.3, 264.9, 549.1, 269.3 | 14.78–15.68 | 68.3–72.4 |
| CAM_W2:ENTRY_V3:E_W_CORNER | 238.8, 462.9, 417.0, 536.3 | 3.30–4.20 | 254.5–323.4 |
| CAM_W2:EXIT_V3:E_PORTAL_R101 | 375.4, 345.4, 462.3, 366.3 | 6.53–7.43 | 144.1–163.8 |
| CAM_W2:EXIT_V3:E_VEST_CORR | 514.3, 264.9, 549.1, 269.3 | 14.78–15.68 | 68.3–72.4 |
| CAM_W2:EXIT_V3:E_W_CORNER | 238.8, 462.9, 417.0, 536.3 | 3.30–4.20 | 254.5–323.4 |
| CAM_WIDE:ENTRY_V3:E_W_CORNER | 412.4, 280.5, 487.5, 290.5 | 11.40–12.48 | 65.6–71.7 |
| CAM_WIDE:EXIT_V3:E_PORTAL_R102 | 407.3, 412.4, 576.7, 475.0 | 4.40–5.56 | 144.1–180.0 |
| CAM_WIDE:EXIT_V3:E_W_CORNER | 412.4, 280.5, 487.5, 290.5 | 11.40–12.48 | 65.6–71.7 |

## 驗證與重現

- 指定 `pytest tests/unit/test_r004_review_v2.py -q`：27 PASS，含 production loader 與8次缺出口探針。第8次刻意把D74排除的CAM_ENTRY插回並留空出口，得到 EXIT_ZONES_MISSING；正常追蹤仍7台。
- 未修改 #127 @994d34c8340855dbf0e28d0273851049df5e6c7d 的檢查器和schemas，對v3兩圖完整適用項13 PASS／0 FAIL／0 SKIP，見 conformance_v3.json；不是錄製/runtime全符合性通過。
- Ruff `--select F,I,UP,B`、`git diff --check` PASS。原.blend前後SHA-256均466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b。
- 26ROI=12入口+14出口，234足點靜態見證；另2塊covered_region證據各9點。精確floor-cell union阻止跨洞；15 active/6 support/22 hidden templates。
- 既有 `build_r004_review_v2.py --graph-v3`，沿用 --config/--config-sha256/--membership/--membership-sha256/--prior-pack/--prior-manifest-sha256/--output。config是build_plan_v3.json；完整source pins在source_pins_v3.json。輸出必須新目錄，含8GiB停止檢查。原絕對路徑只作本機source locator，不上傳原資產；他人可用同hash的本地來源製作新plan並重算plan pin。
- 未驗證：Claude獨立入口／像素／轉移／covered_regions複核、G4、正式HSV／A4/B4／索引／baseline；identity與物理可通行性UNKNOWN。

## Byte SHA-256

- `build_plan_v3.json`: `155eb60db64098af4e336c1d27b731681ca4e0fa58a8cd7a70c1fb2d690aed9f`
- `camera_graph_v3.json`: `03e14e79676872cf7c6a4938fb47d194a46c4b9c2f9af148b1c4716e2bd9c382`
- `conformance_v3.json`: `0ae04b3b4bc640f8ca1c97d23c7638bd3bde45763b774f7af0353bd291ab564d`
- `region_graph_v3.json`: `a774c5b753caa7da85d0bdf3388eeb2a7b3278bd3134d9840c6d6578272b1b6e`
- `roi_report_v3.json`: `74ee69659d4829844018eb866cafb2b3a93b6a7aef67151f1074b4aa047abc0d`
- `source_pins_v3.json`: `714c3f5bcf73e646c4ff2798c8223cbd4db1b59953a8182e02afd6796c7446ca`
- `static_patches_v3.json`: `2f306b1e4d20524d44c2f80bd1e146d5ee63a018b860c86965da22e004f80f09`
- `tracking_scope_v3.json`: `01771904fffeeae1676bdfe22d87a38d17182fe7260269f42764df061aa56cfd`
