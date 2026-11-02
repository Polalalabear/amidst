# r004 圖 v4 草案收據（E3；CQ-08 回修 2026-10-29）

**DRAFT_NOT_RUNTIME_LOADABLE；runtime=false；G4=false；M1=PENDING_G4；NOT_FROZEN。**
僅回修 #272 的兩份 JSON 與本收據。不改 loader、candidate、controller、Line 1 或原始資產；沒有渲染、凍結或核准。
本文件取代本檔舊的 E3／J3 當前狀態敘述；歷史 bytes 與結果保留在 #272 的 `d3a5cae`／`6f06105`，不把舊結果當成本輪重驗。

## 1. 依賴、繼承與 pins

依 D97，從 #294 `0c34287b0b0c21c672f863fd281934f37e8aa24b` 的 **v3_1** 重新繼承。
依賴未經 Claude 複審：#294@0c34287b0b0c21c672f863fd281934f37e8aa24b。
#272 feature 分支用兩 parent merge commit 接上該前置，PR base 設為 `codex/cq01-r004-v3-yyin-exits`；不是合併 PR 或改 staging。
`inherited_transitions` 逐欄等於前置的22條轉移，`inherited_camera_definitions` 逐欄等於 v3_1 的 cameras。
舊 v3 與已交 v3_1 bytes 不變；此處只是 v4 草稿繼承來源換版。

| source key | v3 舊 bytes SHA-256 | v3_1 新 bytes SHA-256 |
| --- | --- | --- |
| camera_graph | `9896be113bf6e2b5f2d9344f1227484674fda2c2bb983d32a70d8ffcc4adfc7e` | `e250413a0d0a2aeb61bd98bb1763236b1e39127f919cee1ee3ca3bd906b78409` |
| region_graph | `717772600caaa51d88b55f62d118bbef2d3f10514ebffeabd41081e801a45ae0` | `a2f737805cf5446c6ba01fa4bebfddd2186d040cbd94314cf573c082191b24e1` |
| static_patches | `17dbae08de96a65b8cc9710b5a8cb4a945d466362f17d41a7e6a0b3108285151` | `fb4141b5e50267982f0e566268e565a584b1bd9fe80a6bacbe895a45b8498547` |
| tracking_scope | `ed5b68995094b060b21a9dba6a05e26a21aa0af15c0f8dcb7fd0bd56424af80a` | 同左（bytes不變） |

graph 的 `source_pins`、exit JSON 的 `base_v3_file_sha256` 交叉相等；後者保留既有 draft key 名，值明確指上述 v3_1，沒有改成新的 runtime schema。
source `.blend` pin `466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b` 只沿用既有來源收據，沒有開啟 `.blend`。
只讀取並驗證四份 LOCAL 靜態 provenance（讀取前後 SHA 相同）：

| 靜態檔 | bytes SHA-256 |
| --- | --- |
| camera_catalog.json | `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f` |
| source_static_geometry.json | `bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a` |
| static_membership.json | `e71f6ad16868ab450bcd093eb50f6fd7ca4a393c73689055235e9505f9e48ca7` |
| region_meshes.json | `4dd2861ded335a9b31454672d3ed1591405f5c53644ccc9df64736cfccdb8a8c` |

| 產物 | 本次 bytes SHA-256 |
| --- | --- |
| camera_graph_v4_draft.json | `a67bd7468fff8a870ca4109636d73f67f23f8be78c4311cf5b31c760c15e3ddf` |
| exit_zones_v4_draft.json | `c2dff7bddcf249cbabe3518a45f4a45817c165993a172b6c10926d1436784958` |

兩份草稿仍使用既有 `q-demo.r004-camera-graph-v4-DRAFT.v1`／`q-demo.r004-exit-zones-v4-DRAFT.v1` envelope；不是現行 production graph schema，也未註冊為 runtime 輸入。

## 2. 轉移與 D93 分組

**22條繼承轉移＋4個新提案ID＝26個唯一ID**，另有6筆 overlap annotations。W1↔W2 已在繼承的22條內，沒有重複新增ID。
新條目各自有 status 與 runtime_enabled=false；所有用途、walkability、scope、G4 與凍結仍須獨立授權。

| 對 | 操作／幾何狀態 | D93 評分 |
| --- | --- | --- |
| EXT_CAR→EXT_CLEAR | 新提案；舊條帶保留，PROPOSED | OVERLAP_P_OV2_UNVERIFIED |
| EXT_CLEAR→EXT_CAR | 新提案；舊條帶保留，PROPOSED | OVERLAP_P_OV2_UNVERIFIED |
| BRANCH→WIDE | 新提案；有 CORR_N 腳點條帶，但未有已接受／凍結出口，MISSING_EXIT | EXCLUDED_NO_EXIT_STRIP |
| WIDE→BRANCH | 新提案；polygon／ROI=null，MISSING_EXIT | EXCLUDED_NO_EXIT_STRIP |
| W1→W2 | 僅註記繼承ID；M1=PENDING_G4 | PENDING_G4_M1 |
| W2→W1 | 僅註記繼承ID；M1=PENDING_G4 | PENDING_G4_M1 |

此處「重疊提案」指：原鏡頭腳點平面位於其畫面邊緣、接手鏡頭視錐仍含該腳點；遮擋、完整人體與真實最後偵測格保持 UNKNOWN（P-OV2）。
BRANCH 單方向新增提案 polygon 不自動解除 D93 對 BRANCH／WIDE 的排除；`EXCLUDED_NO_EXIT_STRIP` 在這裡表示尚無經獨立接受／凍結的合格出口對，不能因 polygon 非 null 改列可評。
D93 的 O1 相位與另列、不得併入主比率規則不變；沒有修改 adapter、評分器或評分規則。

四個新提案均保留 `relation=OVERLAP`、`path_has_unknown_state=true`、`ranking_area_m2=null`。
依 D28／#266 C5b，若未來獲准進入候選且維持這些宣告，排名為 **tier 3**，在無 unknown 的 BLIND_GAP tier 2 後面，不是 tier 1。
因此 #258 §2.4 的混合事件不能假定 OVERLAP 先被選；新增轉移還會改變候選集合，評估端仍須做 P-OV3，不能由本草稿讓 overlap 永遠優先。

所有 overlap 註記仍要求原鏡頭失聯、elapsed_us ≥ link_max_gap_us、進 SEARCHING 後接手。
目的觀測為 timestamp ≥ decision_time 的最早合法 guard observation，不回取歷史首次進入；保留 SWITCHING／PLAYING 兩段時間。
接手 ROI 是同一靜態條帶的投影參考，不是首次可見地點，也不新增「決策時必須仍在這條窄帶」的匹配條件。現行 candidates 不使用 entry ROI 作該匹配；本次沒有改 runtime。

## 3. BRANCH→WIDE 的 CORR_N 靜態提案

v3_1 的 BRANCH E_CORNER_N 已加寬／加深，但繼承22條中仍沒有任何轉移用到該出口；只改 portal ROI 不會達成及時切鏡。
本次另求 **BRANCH 畫面下緣**，不拿 E_W_CORNER 或 E_CORNER_N portal footprint 冒充失聯邊界。

錨點取 frozen WALK_CORR_N 的精確 x 中線 `16.199999809265137` m，x 座標跨度 ±0.2 m；地面 z=0。
先解 v=540 邊界，再沿 world y 軸向鏡頭內側移0.15 m。0.4 m 是 x 座標跨度，不宣稱是斜邊的弧長；0.15 m 也是座標位移。
四個頂點的 bounding rectangle 通過既有 exact floor-cell union 支撐檢查，不是以 mesh bbox 取代支撐面：

| world x,y,z m | BRANCH u,v px | WIDE u,v px |
| --- | --- | --- |
| 15.999999809, 4.111803877, 0 | 533.388736, 540.000000 | 474.909665, 309.680961 |
| 16.399999809, 4.025317409, 0 | 454.576211, 540.000000 | 455.026253, 309.153097 |
| 16.399999809, 3.875317409, 0 | 449.741122, 519.144284 | 454.548493, 307.182039 |
| 15.999999809, 3.961803877, 0 | 525.379718, 519.144284 | 474.137534, 307.694515 |

兩個邊界端點再沿 y 往外移0.15 m，BRANCH 腳點投影在畫面外，WIDE 仍在畫面內。這只證明這個受限腳點 FOV 提案；不是 renderer visibility、實際人物失聯或接回成功。
完整精度的頂點、before／after 投影、支撐 pin 與接手側靜態足點射線結果放在 exit JSON 的 `J3_static_recheck.corr_n_boundary_recheck`。
BRANCH→WIDE 提案轉移改用既有 `region_path=[CORNER,CORR_N]`、`edge_path=[E_CORNER_N]`、region_hops=1；未新增或核准 region graph edge。
新 strip 的 `region_id=CORR_N`；這與 route 起於 CORNER、經 E_CORNER_N 進 CORR_N 的順序相符。
status 仍 MISSING_EXIT，geometry_status 僅為 FRUSTUM_FOOT_EDGE_STRIP_PROPOSED：尚欠獨立複核、接受／凍結、P-OV2／P-OV3及用途／G4授權。

舊四個 EXT／W1／W2 條帶的 polygon 與雙鏡頭投影保持原 bytes 所示數值。
其可重算座標錨點：EXT_CAR 使用明列的提案 x=−9.2±0.2 m；EXT_CLEAR 使用提案 y=1.0±0.2 m；W1／W2 使用 WALK_CORR_W 中線 y=1.2±0.2 m。
前兩者是本草稿公開固定的幾何選取，不假稱從資料得出人物路線或知道舊 helper 作者意圖。JSON 的 boundary_basis 寫明錨點與座標跨度限制。

## 4. WIDE→BRANCH 與 WIDE 下緣仍缺什麼

在 CORNER、CORR_N、CORR_W 各用41×41格點，先以實際支撐面排除不支撐點，保留1681／1653／1653個地面點。
三組中「BRANCH 視錐內而 WIDE 視錐外」均為0點。這是有限格點結果，不是連續空間不可能性證明，也未排除靜態遮擋可導出不同結果。
WIDE→BRANCH 保持 polygon／ROI=null、MISSING_EXIT；若依遮擋補出口，仍需來源綁定的合法 occluder、全身支撐政策及獨立接受／凍結。

WIDE 自身北側下緣另以同一 CORR_N 中線 ±0.2 m、向內 y−0.15 m 查四個支撐頂點：

| 鏡頭 | 純 FOV 內頂點 /4 | 已分類靜態幾何的足點射線見證 /4 |
| --- | ---: | ---: |
| BRANCH | 0 | 0 |
| EXT_CAR | 4 | 0 |
| EXT_CLEAR | 4 | 0 |
| W1 | 4 | 0 |
| ENTRY／R101_IN／W2 | 各0 | 各0 |
| WIDE（原鏡頭） | 4 | 2 |

射線見證沿既有 `static_witness` 的2px內縮界線與分類幾何判斷；位於 v=540 的原鏡頭端點不滿足2px內縮，故 WIDE 的2/4不是人體可見率。
純視錐會忽略牆面，不能將 EXT／W1 的4/4當接手支持。**下一 region／camera 仍 UNKNOWN**，未新增非重疊轉移或將其寫成 BRANCH 重疊出口。
yyin 漏標的門仍 UNKNOWN，交 CQ-22 用 v3_1 疊圖確認；不改門或新增 portal。

## 5. W1↔EXT_CAR 的短暫失聯意見與補視角

新增明確非重疊註記：yyin 10-27 認為兩方向可能短暫消失。兩個繼承 transition 仍 relation=UNKNOWN，經 VEST_W；未改成 OVERLAP，亦未核定 BLIND_GAP。
VEST_W 的41×41格點經 exact support 過濾後有1131個腳點；其中同時在 W1、EXT_CAR 視錐外的點為0。
因此這個 FOV-only 格點查核沒有建立可用的「雙鏡頭都失聯」區，不能拿空集合的覆蓋比率宣稱能補完整空檔。

| 鏡頭 | 1131點的 FOV 內點數 | 同批點的靜態足點射線見證 |
| --- | ---: | ---: |
| W1 | 378 | 86 |
| EXT_CAR | 1131 | 79 |
| EXT_CLEAR | 1131 | 179 |
| W2 | 1131 | 681 |

這些只表示既有提案幾何與腳點的受限檢查；不是特定路線、時間、全身可見性、完整遮擋模型或漏檢驗證。
EXT_CLEAR／W2 有部分靜態見證，實際能否補住短失聯仍 **UNKNOWN**。W2 不在 A4 run 鏡頭範圍，不能以此加到 A4 候選或替換錄製輸入。

## 6. W1↔W2 合併規則：兩案都未選

當前 `overlap_transition_annotations` 的新 exit ref 不在繼承 W1↔W2 的 `via_exit_zone_ids` 內；annotation 沒有接上 runtime，也不能靠 metadata 升權。
兩個方向分別等待 G4／M1，不能因圖標頭或原始空 edge_path 的歷史 APPROVED_WALKABLE 自動核准。

| 方案 | 要改什麼 | 優點 | 代價／待決 |
| --- | --- | --- | --- |
| A：新圖版本修訂沿用 transition | 經核定後，在原ID的出口／入口引用及 relation 語意納入新條帶 | 不增加目的鏡頭的route ID | 不再是22條逐欄相等；整條ID改為OVERLAP會連帶影響舊portal出口，混合出口如何分群須先明定；不能自行增加每出口relation schema |
| B：另設 overlap transition ID | 保留原22條，另以核定的新ID連接新條帶 | 舊BLIND／UNKNOWN用途與新OVERLAP可分開綁定、審查 | ID與schema／candidate合併及替代route紀錄須核定，唯一轉移數會改變；多出口命中仍按契約取聯集 |

**沒有推薦其中一案為已採用，沒有實作任一案。** 精確ID、方向／出口／入口、CORR_W用途、排名與多出口重疊規則交 G4／M1 及契約 owner 決定。
既有審查指出 W1／W2 條帶可能和 portal ROI 重疊；本稿不以新heuristic裁掉出口或強制偏好OVERLAP。

## 7. 重算與驗證邊界

投影沿既有公式：`q=Rᵀ(p−t)`、`d=−q_z`、`u=cx+fx*q_x/d`、`v=cy−fy*q_y/d`。
下緣的世界平面式為 `fy*q_y+(cy−height)*q_z=0`，固定 x,z 後解 y。`uv_depth` 是此靜態校正算出的正 optical-axis 距離，**不是 renderer depth pass**。
支撐查核使用 #294 的 `rectangle_supported`／`on_support`；靜態射線使用其 `membership`、`triangles_for`、`static_witness`，只有已分類靜態檔。
J3 重新檢查 BRANCH／WIDE 共6個 v3_1 patches，包含 BRANCH E_CORNER_N 與 WIDE R102：24頂點、48個雙鏡頭投影，完整數字嵌入 JSON。
來源 pins 逐 byte 驗證；圖／scope／ROI bytes 並未改寫。JSON 可解析與幾何重算不是 runtime 或 schema conformance 通過。

核對程式的重點（repo根目錄，使用uv既有環境）：

```python
import hashlib, json
from pathlib import Path
root = Path('configs/q1q5/graphs')
g = json.loads((root/'r004_v4_draft/camera_graph_v4_draft.json').read_bytes())
e_raw = (root/'r004_v4_draft/exit_zones_v4_draft.json').read_bytes()
e = json.loads(e_raw)
assert hashlib.sha256(e_raw).hexdigest() == g['exit_zones_file_sha256']
base = json.loads((root/'r004/camera_graph_v3_1.json').read_bytes())
assert g['inherited_transitions'] == base['transitions']
assert g['inherited_camera_definitions'] == base['cameras']
ids = [t['transition_id'] for t in g['inherited_transitions']+g['proposed_added_transitions']]
assert len(ids) == len(set(ids)) == 26
assert g['runtime_enabled'] is False and g['G4_approved'] is False
assert e['runtime_enabled'] is False and e['G4_approved'] is False
assert g['freeze_status'] == 'NOT_FROZEN'
```

本次沒有議題另列 pytest 路徑，因此只做指定 JSON／繼承／cross-pin／靜態查核及 diff --check；沒有新增測試或執行全套。
架構守門 **NOT_RUN（#307 尚未交付）**；#127 kit **NOT_RUN（草稿 envelope 不供現行 runtime／recorded kit，本次沒有新錄製）**。
身份保持 UNCONFIRMED，物理通行與碰撞保持 UNKNOWN。未讀原 `.blend`、RGB大素材、GT、軌跡、renderer visibility／depth或劇本事件時刻。
凍結與渲染均須使用者授權；D98-2／D99的其他條件全部保留，本草稿不啟動資料產製。
