# r004 graph v3 — CX-3 / D74 / D77 / D81

PROPOSED／DRAFT，G4 未核，legal_auto_switch_paths=0。只用 #187 的 safe 靜態幾何／calibration／membership 與靜態圖片；事件／GT／renderer visibility/depth 未讀，未渲染／保存 .blend 或移動相機。父版本 #187 @ 9402c91588205bccc972a8efad0b1a9512e3c823，PR base staging。

## 十項處置

1. W1 各邊補新版入口：R101 指 E_PORTAL_R101，EXT 指 E_VEST_CORR，BRANCH/WIDE 指 E_W_CORNER。
2. D81／R1(a)：保留 W2 VEST_W 世界座標，兩 zone ID／edge 改為 E_OUT_VEST；W2↔EXT_CAR／EXT_CLEAR 四條路徑改 VEST_W↔OUT_W、單邊 E_OUT_VEST、region_hops=1。R101、BRANCH/WIDE 仍指 portal、corner approach。W2 corner patch 是鏡頭前方可見接近區，距實際轉角約4m，不能聲稱人已到轉角或可見首次出現。
3. EXT_CAR 南北各一塊地面入口與出口，都 leads_to E_OUT_VEST，每塊九點靜態見證。這是車側接近區，距門洞數公尺，不等同實體門檻或已知行走路線。
4. BRANCH E1/X1 推入 CORNER 並加寬至完整2.4m，另補 E_CORNER_N 出口；covered_regions 增 CORNER。新增出口不解除 D77 的 BRANCH↔WIDE 排除。
5. WIDE E1/X1 加寬至1.8m並增 CORNER；全寬會有3/9足點被 screen 遮擋，故不冒充全寬。加 E_PORTAL_R102 出口，edge 維持 TOPOLOGICAL_ONLY、零合法候選；y>12 明列 OUT_OF_GRAPH。90° PINHOLE 未動。
6. 56有向對全列：22轉移、34附理由的排除；D77仍排除 BRANCH↔WIDE、EXT_CAR↔EXT_CLEAR。D81新增 W1↔W2 同 CORR_W 的兩條零邊轉移，完整引用來源出口及目標入口；relation/ranking_area_m2 為 UNKNOWN/null。空 edge_path 的 path_traversability 依既有 loader／kit 慣例是 APPROVED_WALKABLE、path_has_unknown_state=false；這是零條邊的彙總值，沒有新增或核准實體可通行邊，整圖仍 DRAFT、G4=false、零合法自動切鏡路徑。其餘排除只表示未涵蓋，不宣稱幾何不可能。
7. CAM_ENTRY 依 D74 只供Q1，查找8台、追蹤7台；不虛造ROI、不移鏡頭。Q2/index需綁定顯式tracking scope，不能默默容忍不一致。
8. 每塊ROI像素外框、九點相機深度與1.7m假定人物像素高如下。指定小ROI可在 LOCAL 靜態 SVG／瀏覽器使用100–400%放大，僅改善顯示；辨識仍 UNVALIDATED，證據不足回 AMBIGUOUS/UNKNOWN，不新增 runtime 門檻。
9. 可選 relation/ranking_area_m2 維持 UNKNOWN/null，沒有新增共同可見面積排名。
10. 固定ID見下表、JSON及完整pins；所有圖hash/derived ID重算，原包80鎖定檔驗證未改。

## X 標號與固定 ID

| camera | 舊X標號 | 新版後綴 |
|---|---|---|
| W1 | X1 / X2 / X3 | E_PORTAL_R101 / E_VEST_CORR / E_W_CORNER |
| W2 | X1 / X2 / X3 | E_PORTAL_R101 / E_OUT_VEST / E_W_CORNER |
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
| CAM_W2:ENTRY_V3:E_OUT_VEST | 514.3, 264.9, 549.1, 269.3 | 14.78–15.68 | 68.3–72.4 |
| CAM_W2:ENTRY_V3:E_W_CORNER | 238.8, 462.9, 417.0, 536.3 | 3.30–4.20 | 254.5–323.4 |
| CAM_W2:EXIT_V3:E_PORTAL_R101 | 375.4, 345.4, 462.3, 366.3 | 6.53–7.43 | 144.1–163.8 |
| CAM_W2:EXIT_V3:E_OUT_VEST | 514.3, 264.9, 549.1, 269.3 | 14.78–15.68 | 68.3–72.4 |
| CAM_W2:EXIT_V3:E_W_CORNER | 238.8, 462.9, 417.0, 536.3 | 3.30–4.20 | 254.5–323.4 |
| CAM_WIDE:ENTRY_V3:E_W_CORNER | 412.4, 280.5, 487.5, 290.5 | 11.40–12.48 | 65.6–71.7 |
| CAM_WIDE:EXIT_V3:E_PORTAL_R102 | 407.3, 412.4, 576.7, 475.0 | 4.40–5.56 | 144.1–180.0 |
| CAM_WIDE:EXIT_V3:E_W_CORNER | 412.4, 280.5, 487.5, 290.5 | 11.40–12.48 | 65.6–71.7 |

## 驗證與重現

- 指定 `pytest tests/unit/test_r004_review_v2.py -q`：31 PASS，含 production loader 與8次缺出口探針。第8次刻意把D74排除的CAM_ENTRY插回並留空出口，得到 EXIT_ZONES_MISSING；正常追蹤仍7台。
- 未修改 #127 @994d34c8340855dbf0e28d0273851049df5e6c7d 的檢查器和schemas，對v3兩圖完整適用項13 PASS／0 FAIL／0 SKIP，見 conformance_v3.json；不是錄製/runtime全符合性通過。
- Ruff `--select F,I,UP,B`、`git diff --check` PASS。原.blend前後SHA-256均466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b。
- 26ROI=12入口+14出口，234足點靜態見證；另2塊covered_region證據各9點。精確floor-cell union阻止跨洞；15 active/6 support/22 hidden templates。
- 既有 `build_r004_review_v2.py --graph-v3`，沿用 --config/--config-sha256/--membership/--membership-sha256/--prior-pack/--prior-manifest-sha256/--output。config是build_plan_v3.json；完整source pins在source_pins_v3.json。輸出必須新目錄，含8GiB停止檢查。source_blend_path 使用相對 AMIDST_ARTIFACTS 的 locator（未設時使用 ~/amidst-artifacts）；拒絕 .. 與 symlink 逃逸，原資產不上傳。
- #227 的 Claude 獨立複核已指出 R1，本文修正待其重審。W2 VEST_W ROI 約35×4 px、深度14.78–15.68 m，預期 AMBIGUOUS／辨識未驗證；顯示放大不增加證據。
- D81：等 yyin 三題澄清交回並併入圖複核後才提交 G4；不渲染。逐邊 traversability/state 與 E_CORNER_N 核准留在 G4。G4 後 relation 仍 UNKNOWN，候選屬 tier 4、依 camera_id 字母序；目前 G4 未核，仍零合法候選。
- 未驗證：本修正的 Claude 重審、G4、正式HSV／A4/B4／索引／baseline；identity與物理可通行性UNKNOWN。

## Byte SHA-256

- `build_plan_v3.json`: `88c0ae6b001b3e6a90f04418aedd6638c4c634f060941cac882eef7bb6e4ec1f`
- `camera_graph_v3.json`: `9896be113bf6e2b5f2d9344f1227484674fda2c2bb983d32a70d8ffcc4adfc7e`
- `conformance_v3.json`: `2b52ac5b68a6bb99d45eb160d33880cd4880f12980f27cca818b6c23c9d0a20b`
- `region_graph_v3.json`: `717772600caaa51d88b55f62d118bbef2d3f10514ebffeabd41081e801a45ae0`
- `roi_report_v3.json`: `befe23a4f79026998beeabf60187b8f436b31c207347197f87319abbaf259f3b`
- `source_pins_v3.json`: `9e452ab00c8ca8036998413239875e87c25f3a009e2961b71f30df7760fc957e`
- `static_patches_v3.json`: `17dbae08de96a65b8cc9710b5a8cb4a945d466362f17d41a7e6a0b3108285151`
- `tracking_scope_v3.json`: `ed5b68995094b060b21a9dba6a05e26a21aa0af15c0f8dcb7fd0bd56424af80a`

## G4 M1：兩個待選選項（本次不選）

- **選項一：逐條核准。** 使用者在可信G4收據中明確核准 `T_CAM_W1__CAM_W2` 與 `T_CAM_W2__CAM_W1` 的同區域通行／state，並逐一列明允許的來源出口（特別是W1的E_VEST_CORR）與目標入口；只有明列的方向／出口可升權。不能把整圖approval自動解讀成CORR_W已可通行。
- **選項二：維持保守值。** 未有上述逐條核准時，同區域空edge_path不得因空真值自動成合法切鏡；以獨立已核准region/transition authority檢查，缺核准維持UNKNOWN／不可自動切換。這需要另案loader／candidate修正與新衍生hash，不能只改收據或假稱本PR已實作。

M1仍待使用者在G4選擇；不因本次文字修正、D89情境卡建議或Line2 D90而預先決定。圖仍DRAFT、G4=false。

L1完整補充（收據本身、generator、CLI、test四檔bytes SHA與兩圖content hash）見[hash sidecar](../history/R004_GRAPH_RECEIPT_HASHES_20261027.json)。收據不嵌入自己的hash，以免循環；sidecar綁本文件最終bytes。


## yyin 2026-10-27 澄清的落實（CQ-01；v3_1，PROPOSED_PARTIAL）

本節是新版本提案，舊節保留歷史語境。未核 G4、零合法自動切鏡；不是三題都已通過。
回件 CSV bytes SHA-256 `bee91e61004ac13b8e30a6550f77664975c207101788efe1c7f9da16c64df197` 已核對。
少模板檔依 D98-1／CQ-48 #347 處理：補交前為人工例外；補交後重跑 verify_pack。
本次未收到或匯入補件，不把人工例外記為完整包 VALID，也不代核 G4。

### 1. BRANCH：幾何已加深／加寬，及時切鏡目的未達成

先更正上文「舊 X1」對照：v2 `zone_svg()` 先排 ENTRY，再依 edge_id 排 EXIT；
`make_graphs()` 的 BRANCH 原 ENTRY 位於 CORR_N，唯一 EXIT 是 E_CORNER_N。
因此 E1 是 `CAM_BRANCH:ENTRY_V2`，X1 是 `CAM_BRANCH:EXIT_V2:E_CORNER_N`，兩者原共用
x=[15.85,16.65]、y=[2.6,3.4]。v3 的 E1 依角色改接 `ENTRY_V3:E_W_CORNER`，移至 CORNER；
這是角色對照，不是同一塊幾何，不能解讀成 v2 ENTRY 原地加寬。
原 X1 的 edge lineage 是 `EXIT_V3:E_CORNER_N`，另設 `EXIT_V3:E_W_CORNER`，不能把後者誤稱原 X1。
證據：staging `434e579` 的 `r004_review_v2.py` 中 make_graphs／zone_svg 與 pin 住的 v2 static_patches。

v3_1 保留 ROI ID／角色／edge，三塊均加寬至 frozen WALK_* 的全寬
x=[15,17.399999618530273]（約 2.4 m）：CORNER 的入口及出口 y=[1.4,2.4000000953674316]，
延伸至轉角交界；CORR_N 的原 X1 出口 y=[2.4000000953674316,3.4]，較舊區向交界加深約 0.2 m。
每塊來源四頂點、9 個足點與 support SHA 見 `static_patches_v3_1.json`；來源是 frozen floor-cell union，
沒有改場景、校正或 FOV。3/3 區各 9/9 靜態足點見證通過。
投影數值一致性 max=0 px（同校正重投影），不是獨立校正精度；後者 UNKNOWN/null。
不推論完整人體可見性、首現邊界、可行走或及時切鏡。

**功能缺口及副作用（#294 P2-1）：** v3 與 v3_1 都沒有任何 transition 的
`via_exit_zone_ids` 包含 `CAM_BRANCH:EXIT_V3:E_CORNER_N`；BRANCH 的四條轉移均經
`EXIT_V3:E_W_CORNER`。因此這次加寬沒有增加任何可切換路徑，yyin 所說的「及時切到下一台」
尚未達成。新增約 1.76 m²（2.4×1.0−0.8×0.8）還會改變出口解析：原本未命中任何出口時，
`candidates.transition_candidates` 使用全部出口（AMBIGUOUS）；若唯一命中沒有轉移的
E_CORNER_N，就只選這個出口，轉移數為 0。

以下以兩圖原 bytes 和同一 safe_static 校正重算，列的是 **gate 前的轉移選取**，不是合法候選：

| 地面腳點 x,y m | BRANCH 像素 u,v | v3 的解析／選取 | v3_1 的解析／選取 |
| --- | --- | --- | --- |
| 15.3, 3.0 | 583.4, 404.8 | AMBIGUOUS；W1、W2 | 唯一命中 E_CORNER_N；0 條 |
| 17.0, 2.5 | 335.8, 394.6 | AMBIGUOUS；W1、W2 | 唯一命中 E_CORNER_N；0 條 |
| 16.2, 3.6 | 475.5, 480.0 | AMBIGUOUS；W1、W2 | AMBIGUOUS；W1、W2 |

目前兩圖仍 DRAFT、scope 的 G4=false；上表六個探針的現行合法候選全為 0。
有選到轉移的探針均被 GRAPH_NOT_APPROVED 排除；死路出口則沒有轉移可送 gate。
即使未來 G4 核准，該出口無轉移的缺口仍存在，不能把「沒有改 transition bytes」當成候選行為不變。

往北離框前，ROI 上界 y=3.4 到影像下緣 y≈3.81（x≈17.4）／4.33（x=15）的區段仍未涵蓋
（邊界估計來自 #294 Claude 靜態複核）。未命中時仍取 W1／W2，不能說方向正確或已接手。
**後續責任：** CQ-22 #302 給 yyin A＝目前 y 2.4～3.4、B＝同方法延長至約 y 3.75、
C＝FOV 下緣條帶的疊圖確認；CQ-08 #287 評估 Line 2 v4 的 BRANCH→WIDE 條帶與轉移。
逐邊／方向核准仍由 G4 使用者決定；Line 1 的 D77 排除不因幾何或本收據解除。

### 2. WIDE：下緣提案幾何已知，連接 MISSING／門指認 UNKNOWN

(a) **更正 #294 P2-2：幾何可導出，只有連接 region／camera 維持 MISSING。**
先前 frozen CORR_N 候選 x=[15.6,17.2]、y=[11,12] 四個地面角點投影 v=597.9～847.3 px，
全在 540 px 高畫面下方；被 `rectangle_patch` 拒絕是必然，不能據此聲稱無法導出下緣幾何。

改用畫面內條帶：CORR_N x=[15,17.399999618530273]、y=[9.6,10.1]、z=0 m。
精確 x 上界來自 frozen WALK_CORR_N，不把顯示用 17.4 直接當輸入（會超出支撐面約 0.38 μm）。
沿用 `rectangle_patch`，exact floor-cell union 支撐與 9/9 靜態足點見證通過；
v=464.783371～523.089079 px。來源頂點與像素如下（像素顯示至六位小數）：

| world x,y,z m | WIDE u,v px |
| --- | --- |
| 15, 9.6, 0 | 641.319667, 464.783371 |
| 17.399999618530273, 9.6, 0 | 384.326371, 483.430971 |
| 17.399999618530273, 10.1, 0 | 379.432919, 523.089079 |
| 15, 10.1, 0 | 667.532611, 499.526523 |

其餘五個見證是四邊中點與中心（16.199999809265137, 9.85, 0）。支撐為 WALK_CORR_N，
canonical mesh SHA-256 `a7cdd20f4791d587eeafb7929a6db7ddfee9e9abeae6b0cc0c78b3cb0edae496`。
校正 pin `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`；
其餘靜態來源 pins 見 `build_plan_v3_1.json` 的 `static_source_pins`，重算前逐 byte 驗證。
這是 **PROPOSED 幾何，僅記在收據，不加入任何 `exit_zones`**。沒有可接的 edge，
也沒有下一 region／camera 的來源證據或 authority；y>12 仍 OUT_OF_GRAPH。
9 點靜態足點通過不等於完整人體可見、最後失聯邊界、可通行或無碰撞。

(b) 已看回件所指無人物 static_CAM_WIDE.png；左側門狀開口可見，但是否即 yyin 指的那扇門為 **UNKNOWN**。
v3 已有 `CAM_WIDE:EXIT_V3:E_PORTAL_R102`；不能僅憑外觀把「另外一扇」等同 R102 或新增 portal。
v2 審查包曾略過 E_PORTAL_R102，yyin 未看過這個標號；確認題交 CQ-22 #302 疊上
A＝PORTAL_R102、B＝右側大開口、C＝其他位置，並保留「都不是／看不出來」。
不能要求 yyin 直接比對未見過的 v3_1 標號。`EXIT_V3:E_PORTAL_R102` 也沒有任何轉移，
WIDE 沒有該門的 ENTRY，R102 沒有鏡頭；即使確認門指認，也不會自行增加切換。
缺人工指認與靜態門洞對照，未加新區／邊。上述候選只是確認題，不是門指認結論。

### 3. W1↔EXT_CAR：雙向拓撲已涵蓋，BLIND 核定仍 MISSING

兩個有向 transition 均存在，region／edge 路徑互反，來源出口和目標入口均保留。
雙向是短暫盲區為 yyin 的回覆，不把意見提升為 relation authority：兩方向現行 `relation=UNKNOWN`，
不是已核 BLIND_GAP；兩者含 TOPOLOGICAL_ONLY／UNKNOWN 邊，G4 未核，零合法候選。
因此「已是 BLIND 型」無法確認，保持 **MISSING（待 G4 的來源證據及逐項核定）**。
`candidates.transition_candidates` 依來源／目的／出口查找，沒有只允許其中一方向的常數；
`linker.LinkParameters` 的 link_max_gap_us 是局部 track 的共同參數，不是兩鏡頭 travel-time 上限。
不能用它補出跨鏡頭失聯時間。此次只做靜態原始碼核對，未跑 linker／Q5 或核定任何參數。
「其他相機可以補」保持審查意見，未新增任何 transition。

### 版本、pin 與重現

新增檔名 `_v3_1.json`，ROI ID 沿用 `_V3` 以保留語意對照；檔案 bytes hash 與 graph content hash 均重算。
舊八個 `_v3.json` bytes 全數保持 recipe 的 base_files pins。tracking scope bytes 不變；
region／camera 增列新版 patch input；圖仍 DRAFT，舊 approval、edge 與 transition 語意完全保留。
逐檔圖 SHA 見 `docs/history/R004_GRAPH_CQ01_HASHES_20261027.json`；本次文字回修與相同圖 bytes
由 `docs/history/R004_GRAPH_CQ01_HASHES_20261028.json` 綁定。兩份舊 hash sidecar 都保留歷史值。

P2-2 靜態條帶可從 repo 根目錄重算；只開啟四份白名單靜態檔，不讀 .blend／媒體／事件／GT：

```sh
uv run python - <<'PY'
import importlib.util
import json
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location('review', 'src/amidst/evaluation/r004_review_v2.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
root = Path('configs/q1q5/graphs/r004')
plan = json.loads((root / 'build_plan_v3_1.json').read_bytes())
prov = Path(os.environ.get('AMIDST_ARTIFACTS', Path.home() / 'amidst-artifacts')) / 'r004-prereview-team-v2_20261024/provenance'
names = ['source_static_geometry', 'static_membership', 'region_meshes', 'camera_catalog']
docs = {n: m.pinned(prov / (n + '.json'), plan['static_source_pins'][n + '.json']) for n in names}
triangles = m.triangles_for(m.membership(docs['source_static_geometry'], docs['static_membership'])['render_enabled_objects'])
cal = next(c for c in docs['camera_catalog']['cameras'] if c['camera_id'] == 'CAM_WIDE')
patch = m.rectangle_patch(cal, docs['region_meshes']['meshes']['CORR_N'],
                          [15, plan['branch_bounds']['CORR_N'][1], 9.6, 10.1], triangles)
print(json.dumps(patch, indent=2))
for version in ['v3', 'v3_1']:
    graph = json.loads((root / ('camera_graph_' + version + '.json')).read_bytes())
    assert not any('CAM_BRANCH:EXIT_V3:E_CORNER_N' in t['via_exit_zone_ids'] for t in graph['transitions'])
    assert not any('CAM_WIDE:EXIT_V3:E_PORTAL_R102' in t['via_exit_zone_ids'] for t in graph['transitions'])
PY
```

重現（新 output 目錄；LOCAL 靜態 provenance 只讀）：

```sh
uv run python scripts/build_r004_review_v2.py --graph-v3-1 \
  --config configs/q1q5/graphs/r004/build_plan_v3_1.json \
  --config-sha256 CONFIG_SHA256_FROM_SIDECAR \
  --base-graphs configs/q1q5/graphs/r004 \
  --static-provenance "$AMIDST_ARTIFACTS/r004-prereview-team-v2_20261024/provenance" \
  --output NEW_OUTPUT_DIRECTORY
```

後續須明確改 pin 的消費端：CQ-02/G4 圖引用、#127 kit／run 配置、tracking scope 內圖引用的實際消費端、
v4 #272（CQ-08）及後續錄製。此次沒有改這些消費端或舊包；未列出的實際 pin locator UNKNOWN。
當前 tracking_scope_v3_1 與舊 bytes 相同，不宣稱已更新任何 runtime consumer。
驗證：指定 `tests/unit/test_r004_review_v2.py` 33 PASS；新增 loader／舊 bytes pin／authority／transition 不變
與錯誤 recipe pin 拒絕檢查。第一次 32 PASS/1 FAIL 是測試錯誤訊息預期不符（已改正），不是幾何失敗。
未做 renderer、GT、runtime、模型、G4 或 formal 驗收。
