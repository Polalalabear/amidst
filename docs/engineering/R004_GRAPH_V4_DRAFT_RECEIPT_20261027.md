# r004 圖 v4 草案收據（E3，2026-10-27）

**DRAFT_NOT_RUNTIME_LOADABLE；G4=false；M1=PENDING_G4。** 本次只交兩份 JSON 與此收據，不核定、不凍結、不改 loader／candidate/controller／Line 1，不渲染。狀態與座標是靜態提案，不能直接充當可執行圖。

## 1. 範圍與輸入

以 staging `680ca357a31b664bed3feb6a5284dcd7c5c0d94d` 圖 v3 為底。完整 source pin 與輸入檔 hashes 同 E2 收據：catalog `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`；static geometry `bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a`；patches `17dbae08de96a65b8cc9710b5a8cb4a945d466362f17d41a7e6a0b3108285151`；source `.blend` pin 只沿用靜態匯出內的 `466e6fbe…`，本次沒有讀 `.blend` bytes。兩份草案也各帶完整 pins。

| 產物 | SHA-256 |
| --- | --- |
| `configs/q1q5/graphs/r004_v4_draft/camera_graph_v4_draft.json` | `3b798ddf4859a7070f62652604bc330135e516484deb8e6234d6c2dde52bdd2f` |
| `configs/q1q5/graphs/r004_v4_draft/exit_zones_v4_draft.json` | `5bfff01f3acd2ddbfcabb35ca34b668cc178b8a7fdd631340222699345d62837` |

這是新的草案 envelope（`q-demo.r004-camera-graph-v4-DRAFT.v1`／`q-demo.r004-exit-zones-v4-DRAFT.v1`），不假冒現行 `q-demo.camera-transition-graph.v1`。現行 loader 不接受這兩個頂層 schema；未提供給 runtime registry，也沒有產 approved scope。

## 2. 轉移與 ID

| 對 | ID／操作 | 狀態 |
| --- | --- | --- |
| EXT_CAR→EXT_CLEAR | 新增 `T_CAM_EXT_CAR__CAM_EXT_CLEAR` | PROPOSED，runtime=false |
| EXT_CLEAR→EXT_CAR | 新增 `T_CAM_EXT_CLEAR__CAM_EXT_CAR` | PROPOSED，runtime=false |
| BRANCH→WIDE | 新增 `T_CAM_BRANCH__CAM_WIDE` | PROPOSED，出口幾何 MISSING，runtime=false |
| WIDE→BRANCH | 新增 `T_CAM_WIDE__CAM_BRANCH` | PROPOSED，出口幾何 MISSING，runtime=false |
| W1→W2 | 沿用既有 `T_CAM_W1__CAM_W2`，新增 overlap annotation | **PENDING_G4／M1**，runtime=false |
| W2→W1 | 沿用既有 `T_CAM_W2__CAM_W1`，新增 overlap annotation | **PENDING_G4／M1**，runtime=false |

v3 已經有 W1↔W2；所以不是 22+6=28，而是 **22 條逐欄保留 +4 新 ID =26 條唯一轉移**，另有6條 overlap annotation。`inherited_transitions` 與 v3 完整 JSON 比對相等，`inherited_camera_definitions` 也相等；原 region graph 不改。W1/W2 的舊 `APPROVED_WALKABLE` 只是精確保留的歷史欄位，不代表本草案核准；頂層警示、`runtime_enabled=false` 與 PENDING_G4 annotation 阻止將其誤解為 M1 決定。

新轉移都是 same-region proposal，`edge_path=[]` 並明確 `path_traversability=UNKNOWN`、`path_has_unknown_state=true`，不讓空 edge path 的空真值替新邊取得 walkability。圖 v4 不加新 region、物理邊、camera pose或FOV，不改CAM_ENTRY query-only。

所有 overlap annotation 都採 D90-2：原鏡頭失聯、`elapsed_us ≥ link_max_gap_us` 且進 SEARCHING 才能切；目的觀測沿現行 earliest legal guard，timestamp_us ≥ decision_time_us，不回取歷史首次進入；entry 若較晚，仍按 E1 C5c 保留 SWITCHING→PLAYING 的兩段時間。D90「決策時刻」文字與現行大於等於的界線交契約 owner 確認，本草案不暗加「僅能恰好當格」限制。這只是本次提案的守門文字，不是 controller 已修改或新評分規則已核定。

## 3. 出口條帶與缺口

出口坐標只由 source-bound pinhole calibration 求影像邊界直線，再向原鏡頭內側偏0.15 m、沿邊切0.4 m條帶；投影以連續像素界線 0/960/540 表示。ROI 邊界 inclusive 規則未在本草案核定。新 entry zone 是同一靜態條帶投影到接手鏡頭，供當格觀測匹配的提案，不表示第一次看見目標的地方。

| 出口 | 畫法 | 靜態界線 |
| --- | --- | --- |
| EXT_CAR→CLEAR | `CAM_EXT_CAR:EXIT_V4:OVERLAP_CLEAR` | 舊鏡頭左邊 u=0；外部支撐面 x約−9.4至−9.0、y約2.74至3.72 m |
| EXT_CLEAR→CAR | `CAM_EXT_CLEAR:EXIT_V4:OVERLAP_CAR` | 舊鏡頭右邊 u=960；x約−9.18至−8.71、y0.8至1.2 m |
| W1→W2 | `CAM_W1:EXIT_V4:OVERLAP_W2` | 舊鏡頭下邊 v=540；CORR_W x約0.217至0.488、y1.0至1.4 m；仍 PENDING_G4 |
| W2→W1 | `CAM_W2:EXIT_V4:OVERLAP_W1` | 舊鏡頭下邊 v=540；CORR_W x約11.251至11.457、y1.0至1.4 m；仍 PENDING_G4 |
| BRANCH→WIDE | `CAM_BRANCH:EXIT_V4:OVERLAP_WIDE` | **polygon／ROI=null，MISSING_FEASIBLE_BOUNDARY_IN_CORNER** |
| WIDE→BRANCH | `CAM_WIDE:EXIT_V4:OVERLAP_BRANCH` | **polygon／ROI=null，MISSING_FEASIBLE_BOUNDARY_IN_CORNER** |

四個條帶的16個頂點都落在對應exact support cells。這只驗支撐和腳點 frustum 邊緣；人體寬度／頭部先離框／車或牆遮擋可能讓 `t_L` 早於此邊界，P-OV2 仍 UNKNOWN。條帶未凍結，不可從這份草案直接產 run。

BRANCH/WIDE 的 CORNER 矩形四角在0／0.85／1.7 m高度全部落入兩個凸frustum內，因此整塊 CORNER 的垂直軸都在兩視錐。既有 BRANCH/WIDE E_W_CORNER footprint 不在所需的 FOV 離框邊界，不能直接拿來冒充新 overlap 出口。若遮擋讓實際獨有區成立，須提供完整且合法的靜態遮擋證據、重新定ROI；否則需由Claude調整卡片／場景提案。沒有假造可用 polygon。

## 4. 核定前必做

獨立靜態／ROI複核 → 使用者選定 M1與各轉移／用途 → 凍結新版本／exit polygons → 新run與clock/camera/scope登錄 → 另取得渲染授權。這份收據只提 static geometry/calibration/ROI 證據，不引用GT、renderer軌跡、visibility、depth或劇本的 t_X／t_N。Line1持續使用原圖v3與其既有核定流程；草案不放寬任何門檻。

## 實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: 主代理發布獨立Draft PR；沒有合併或G4核准。
- Files changed: 只新增上述兩份JSON與本收據。
- Commands run and results: 本機Python根據靜態calibration平面式產JSON；驗證原22條transition／camera definitions逐欄相等；26個ID唯一；6個overlap annotations，W1/W2兩筆皆PENDING_G4；4個條帶16頂點支撐PASS；2個CORNER出口保持MISSING；出口檔cross-pin PASS；JSON解析PASS。`git diff --check`由主代理提交前執行。
- Artifacts: 上表兩份JSON與SHA-256；LOCAL生成helper保留於本次暫存工作目錄，不含來源資產。
- Verified: 靜態投影計算、繼承不變、唯一ID、draft／runtime=false／G4=false、明確M1 pending、缺口不偽填。
- Not verified: 現行runtime載入（故意不支援此草案schema）、實際P-OV2／P-OV3／全身可見性、遮擋、detector、renderer、G4/M1、任何正式評分或通行。
- Deviations, UNKNOWN items and follow-ups: v3已含W1/W2，採annotation而不重複加ID；BRANCH/WIDE無已證明的CORNER離框出口，JSON明記MISSING，不把草案稱成可執行圖。

## J3 補查：BRANCH／WIDE 出口保持 MISSING

2026-10-27，只重讀 frozen catalog／ROI／footprint。沒有讀 static wall mesh、原 `.blend`、RGB、人物軌跡、visibility 或 depth。catalog／patch bytes SHA仍為§1原值，執行前後相同。具體數字已嵌入 exit JSON 的 `J3_static_recheck`，不用取得 LOCAL helper 才能查閱。

檢查四個 frozen E_W_CORNER patches（BRANCH與WIDE各ENTRY／EXIT，16頂點，交叉投影到兩鏡頭共32個點）。各多邊形在兩個凸視錐內，原owner像素ROI重投影最大差0px：

| frozen footprint | BRANCH投影 u／v（px） | BRANCH最近畫面邊距（px） | WIDE投影 u／v（px） | WIDE最近邊距（px） |
| --- | --- | ---: | --- | ---: |
| BRANCH ENTRY／EXIT E_W_CORNER | u280.3932–587.1136／v306.8136–386.2715 | 153.728500 | u408.1124–507.8848／v280.0085–290.6612 | 249.338773 |
| WIDE ENTRY／EXIT E_W_CORNER | u294.4181–527.9911／v311.6265–384.7293 | 155.270661 | u412.3657–487.4887／v280.4920–290.5446 | 249.455371 |

因此舊portal ROI不是所需的origin失聯邊界，不能直接改名當overlap出口。這不證明實際畫面一定共視：腳點在frustum內仍可能被遮擋，完整人體也未驗證。僅憑本次允許的calibration／frozen patches，**仍無法補出有證據的兩個出口polygon／ROI**，保留null、MISSING及runtime=false；原四個已提條帶和所有v3資料原樣保留。

缺的證據逐項列入兩個zone的`missing_evidence`：允許CORNER路線上具有來源pin的靜態失聯／遮擋邊界；從該邊界導出的frozen footprint與pixel ROI；若靠遮擋則需合法static occluder membership及核定的全身支撐政策。這些都不能由現有腳點ROI、相機代號或劇本時刻推得，也不能讀renderer visibility補答案。之後仍需獨立審查、G4增補與事件前凍結；本稿不代核。

重算公式：對world點p，先`q = Rᵀ(p−t)`、`d=−q_z`，再`u=cx+fx*q_x/d`、`v=cy−fy*q_y/d`；edge margin=`min(u,width−u,v,height−v)`。四角都滿足near≤d≤far及0≤u≤width／0≤v≤height；因frustum凸，整個平面footprint也在內。使用完整float精度，表格只為閱讀四捨五入。

### J3 實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: 延續#272，精確head見PR本次回覆。
- Files changed: 原兩JSON與本收據；只加靜態補查／缺資料說明及更新cross-pin。
- Commands run and results: 既有uv/Python離線執行LOCAL helper（僅catalog+patches）；4 patches／16頂點／32 projections、原ROI最大差0px、來源before/after pins相同；兩缺口null、原四條帶不變、v3的22條transition不變、26ID唯一、M1仍PENDING_G4；`git diff --check`由提交時記錄。
- Artifacts: 具體投影證據已放exit JSON；LOCAL helper bytes SHA-256 `fc64b74f31e1c23336851700a6afb116b04ff8b732f1572886dc08bbd7abd1e1`（可依上列公式獨立重算，不含來源素材）。最新三檔SHA見PR。
- Verified: 目前frozen portal footprint不能當FOV失聯邊界；現有允許輸入不足以畫新overlap出口。
- Not verified: 全身／遮擋／實際t_L、detector／renderer、G4或正式run；沒有啟動Blender、推論或讀GT。
- Deviations, UNKNOWN items and follow-ups: J3允許做不到時保留MISSING，本次沒有偽造可用ROI；需要上列新增合法靜態證據或卡片／場景調整後重審。
