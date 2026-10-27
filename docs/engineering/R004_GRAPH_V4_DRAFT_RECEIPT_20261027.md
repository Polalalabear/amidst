# r004 圖 v4 草案收據（E3，2026-10-27）

**DRAFT_NOT_RUNTIME_LOADABLE；G4=false；M1=PENDING_G4。** 本次只交兩份 JSON 與此收據，不核定、不凍結、不改 loader／candidate/controller／Line 1，不渲染。狀態與座標是靜態提案，不能直接充當可執行圖。

## 1. 範圍與輸入

以 staging `680ca357a31b664bed3feb6a5284dcd7c5c0d94d` 圖 v3 為底。完整 source pin 與輸入檔 hashes 同 E2 收據：catalog `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`；static geometry `bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a`；patches `17dbae08de96a65b8cc9710b5a8cb4a945d466362f17d41a7e6a0b3108285151`；source `.blend` pin 只沿用靜態匯出內的 `466e6fbe…`，本次沒有讀 `.blend` bytes。兩份草案也各帶完整 pins。

| 產物 | SHA-256 |
| --- | --- |
| `configs/q1q5/graphs/r004_v4_draft/camera_graph_v4_draft.json` | `bfbdb6e6efbf680649ba19fa151e70df992acf68de5bdbcdadfd094427e3e9a2` |
| `configs/q1q5/graphs/r004_v4_draft/exit_zones_v4_draft.json` | `9f908ed92ce261cc765de8a049f57174c124bda11a5505436b31c32367c180de` |

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
