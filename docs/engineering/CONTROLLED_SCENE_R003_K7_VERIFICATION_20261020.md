# r003 靜態幾何的 K7 地圖驗證（O10 核准依據，2026-10-20）

本文是 D62 O10 的 K7 證據：逐物件、逐用途檢查 r003 safe 靜態幾何，給使用者據以核准用途。**本文不做核准**，也不改 r003、safe_bundle 或任何資產；核准後由 Codex 產生新版 `scene_static`（契約 v1.1 §3.4「人工修訂要產生新的 map 版本與 hash，舊檔不變」）。

- 結果 JSON：[`CONTROLLED_SCENE_R003_K7_VERIFICATION_20261020.json`](CONTROLLED_SCENE_R003_K7_VERIFICATION_20261020.json)
- 疊圖：[`figures/k7_r003/r003_walkable_inset.png`](figures/k7_r003/r003_walkable_inset.png)、[`figures/k7_r003/r003_camera_floor_visibility.png`](figures/k7_r003/r003_camera_floor_visibility.png)
- 程式：`src/amidst/evaluation/k7_controlled_scene.py`、`scripts/verify_controlled_scene_k7.py`、`tests/unit/test_k7_controlled_scene.py`

## 0. 結論

| 用途 | 物件 | 建議 | 主要證據 |
| --- | --- | --- | --- |
| `OCCLUSION` | 22 牆＋5 遮屏 | **建議核准**（27/27） | 27 個 mesh 都是封閉的 8 頂點長方體，和 `footprint_m × [base_z, base_z+height]` 的最大差 0 m；牆元件聯集和 `WALL_JOINED_SHELL` 在 52,990 個取樣點 0 不一致；4 台鏡頭共 42,567 條地面射線，「元件長方體」與「shell＋遮屏三角面」兩種 raycast 0 不一致 |
| `VISIBILITY_INDEX` | 同上 27 個 | **建議核准**（27/27） | 同上；4 台鏡頭的靜態地面足跡合理（§3.6） |
| `COLLISION` | 同上 27 個 | **建議核准**（27/27） | walkable 被實體穿透的最大深度 1.9073×10⁻⁶ m ≤ 1×10⁻⁵（D58）；3 個（兩個門楣、窗楣）整個在 1.80 m 人體帶以上，不影響可走範圍 |
| `WALKABILITY` | 6 個 walk | **建議核准**（6/6），附語意條件 | `polygon_m` 與 mesh 完全相同；walkable ＝「地板 − 人體帶實體 footprint」在設計範圍內，IoU 0.9999999；沒有未宣告的鄰接。**walkable 是地板佔用區，不是人體中心可達區**：依 0.30 m 內縮後只剩 102.71 m²（IoU 0.751） |
| `WALKABILITY` | `PORTAL_R101` | **建議核准** | 開口淨寬 1.2000 m、兩側門框與門楣都在；人體中心可通過的最大半徑 0.600 m |
| `WALKABILITY` | `PORTAL_R102` | **建議不核准**（只能當拓撲連通） | 門後到遮屏 `OBSTACLE_SCREEN_R102` 只有 0.48 m：人體中心可通過的最大半徑 **0.2395 m**，小於包絡 0.30 m，也小於名義 0.25 m。內縮後 `WALK_R102` 的室內（12.71 m²）和走廊不連通 |
| `DISPLAY` | 42 個 | **建議核准**（42/42） | geometry hash 相符，mesh 外框和 `bounds_m` 一致 |
| 地板 `FLOOR_GROUND`（不在 O10 的 objects 內） | 1 | **建議一併核准支撐面範圍** | 680 個頂點全部 z = 0；地板 163.12 m² 完全涵蓋 walkable；`approved_scope_ref` 目前是 `null` |

沒有任何物件需要改幾何。「需修正」的是核准紀錄與消費端的用法，見 §5。

## 1. 依據與讀取範圍

| 輸入 | 版本／SHA-256 |
| --- | --- |
| r003 `.blend` | `6e7de38dc069d330e0ffbb6c0051cdab304566fdbb7e3e8dfb429af863ae6d8e`（只核對 `source_static_sha256`，未開檔） |
| `scene_static.json`（A、B1 相同） | `a0b3a72c3e1967847b206a501ad64a70bfcb2544951e293db5eb064b71e49482` |
| `cameras.json` A／B1 | `6599defea9b53592e8300973d3d4c3f4de0f84ea8a6846ca461873b63ce4e063`／`b374a737c9ed39178bfd4d32b17cb05ccfbdfc74e4c7ceafef46482a122fa1ad`（4 台的 `calibration_sha256` 相同；A 只綁 W1、W2、CTRL） |
| `geometry/*.json` | 52 個引用，44 個檔，兩 run 逐檔相同；逐檔 SHA-256 在 JSON `runs[].input_sha256` |
| 契約 | v1.1 草案 #65 @ `98451bd`（§3.0–§3.6、§6.3.1、§7） |
| validator | E 包 v2 #77 @ `7bc345f`（只讀規則表，避免重複） |
| 設計稿附錄 A | #54 @ `812817f` `docs/engineering/CONTROLLED_SCENE_B_DESIGN_20261018.md`，SHA-256 `da262df5…3d29`；**只用 `WALK_POLYGONS`（扣除前的 walk 多邊形）**指定歸屬，沒有讀 §3 路線或附錄中的路線函式 |
| 第二批規格 | #81 @ `3a5967f` §2、§3.2–§3.4、§6 |

**沒有讀：**RGB 內容、`rgb_index.json`、`body_policy.json` 內容、GT、`persons.sim.json`、人物路線、renderer visibility、depth、`private_evaluation/`。

## 2. 方法（執行前寫定）

### 2.1 各用途：2b–2d 要它做什麼、validator 已涵蓋什麼、K7 補什麼

| 用途 | 2b–2d 的需要（#81） | validator v2 已涵蓋 | K7 補的檢查 |
| --- | --- | --- | --- |
| `OCCLUSION` | 2b：腳點像素帶擴 2 px 的靜態遮擋檢查、`occlusion_near`（§6.3.1 第 1–2 步）；2c：raycast 的遮擋面 | `OBS-001`（footprint 和 bounds／base_z／height 一致）、`OBS-004`（和設計 AABB 一致）、`SCH-005`、`APR-*`、`HSH-001`（只驗 hash 格式）。**validator 不讀 geometry 檔**（#68 留言 6270258238） | K1 geometry 檔 hash；K2 mesh 是否為封閉長方體、是否等於 footprint 擠出（回答 #81 §6 的 UNKNOWN）；K3 牆元件與 `WALL_JOINED_SHELL` 的體積一致性；K4 元件之間的縫；K8 兩種 raycast 交叉比對 |
| `VISIBILITY_INDEX` | 2c：`SOURCE_MESH_RAYCAST` 地面足跡；2d：負證據 `visible_floor` | 同上，加上 `CAM-001`–`CAM-005`（pose、K、與設計一致、與外框間隙） | 同上，加上 K7 鏡頭視錐與遮擋的合理性（只用校正與靜態幾何） |
| `COLLISION` | 2d：K1 的人體中心可達區、淨空 | `OBS-001`–`OBS-004`（含 D58 穿透深度、D38 遮屏淨距） | K2；K5 推導 walkable、依 0.30 m 內縮的比較 |
| `WALKABILITY` | 2d：K1 `polygon_floor_map` 的 regions／portals；2c：O11 拓撲通路 | `FLR-001`、`WLK-001`–`WLK-006`、`PRT-001`、`PRT-002` | K5 推導比較；K6 portal 開口、門框、門楣、穿越、人體可通過寬度；連通拓撲與內縮後的分量 |
| `DISPLAY` | 前端 3D 顯示；不進推論 | `ID-*`、`APR-002`、`APR-003` | K1；mesh 外框和 `bounds_m` 一致 |

### 2.2 檢查項目與理由

- **K1 輸入完整性：**每個 `geometry_ref` 只能在 `geometry/` 底下，拒絕路徑穿越與 symlink；位元組 SHA-256 等於 `geometry_sha256`。不相符的檔不載入。
- **K2 實體 mesh：**頂點都在外框角上、恰好 8 個、每條邊恰好被兩個面共用（封閉），而且外框等於 `footprint_m × [base_z_m, base_z_m + height_m]`（容差 1×10⁻⁶ m）。理由：契約 §3.5 的 `EXACT_MESH` 必須能解析到實際 mesh；如果 mesh 就是 footprint 擠出，2b／2c 用哪一種表示都得到同樣的遮擋。
- **K3 shell 一致性：**`active_wall_geometry_ref` 是 render 實際用的牆外殼。在每個牆元件外擴 0.03 m 的範圍內各取 1,500 點，加上 shell 外框內 20,000 點（seed 20261020），排除離任何面 ≤1×10⁻⁵ m 的點，再比較「在元件聯集內」與「在 shell 內」（射線奇偶判定）。
- **K4 縫：**任兩個實體之間的正距離 ≤1 mm 就列出，記錄寬度、方向、射線能穿過的最大角度。
- **K5 walkable 推導：**地板（`FLOOR_GROUND` 面的 XY 聯集）扣掉人體帶（z 在 [0, 1.80] m，D42 包絡高度）內的實體 footprint，得到可站地面；再用設計稿 §1.1 的扣除前多邊形決定歸屬，逐 walk 和 `polygon_m` 比 IoU、差異區塊位置與面積。另把 walkable 聯集依 0.25 m（D42 名義）與 0.30 m（D42 包絡）內縮，得到人體中心可達區。
- **K6 portal 與連通：**開口在牆線上的淨寬、兩端是否有門框、門楣是否在 `sill_z + height` 之上、門標記 mesh 是否等於 `opening_m`、垂直穿越線兩端是否分別落在 `connects[]` 的兩個 walk。每一組宣告的連通算「人體中心可通過的最大半徑」：兩個 walk 聯集內縮後，連通兩邊的分量必須包含兩個 walk 各自內縮後面積的 ≥99%（門口小凹槽不算進入對面）；用二分法求到 1 mm。另檢查沒有未宣告的鄰接。
- **K7 鏡頭視錐：**以 0.05 m 格點取地面（扣掉 base_z = 0 的實體），用針孔模型投影，在畫面內、深度在 clip 範圍內，而且到鏡頭的線段不穿過任何實體，就算看得到。記錄每台鏡頭的位置所在區域、是否在實體內、各 walk／AREA 的可見面積，並核對設計稿 §1.2 寫明的意圖（CTRL 看不到走廊、N1 透過觀測窗看北走廊、W1／W2 看得到 `AREA_R101_FRONT`）。
- **K8 raycast 交叉比對：**0.10 m 格點，在畫面內的地面點，各用「27 個元件長方體（slab 法）」與「shell＋5 個遮屏 mesh 的三角面（Möller–Trumbore）」判斷是否被擋；長方體弦長 <1×10⁻⁴ m 的擦邊射線另計，不列入比較。

**刻意不做：**沒有讀路線，所以不做舊 K7 的路線違規檢查（D10 的路線檢查在新場景屬 private，§7）；不判斷人體是否看得到（只算地面，2a 交接 §5「地面看不到不證明全身看不到」）。

### 2.3 判定規則

固定在程式的 `DECISION_RULES`（JSON `decision_rules`）：

- `OCCLUSION`／`VISIBILITY_INDEX`：K1、K2 通過，`collision_scope` 是 `EXACT_MESH`，牆的 K3 通過，K4 的每條縫都 ≤1×10⁻⁵ m，K8 不一致為 0，才「建議核准」；否則「需修正」。
- `COLLISION`：同上的 mesh 條件；在人體帶內的物件另外要求 walkable 穿透深度 ≤1×10⁻⁵ m。整個在人體帶以上的物件也核准，但註明不影響可走範圍。
- `WALKABILITY`（walk）：`polygon_m` 等於 mesh（對稱差 ≤1×10⁻⁶ m²、Hausdorff ≤1×10⁻⁵ m）、在地板上、沒被實體穿透、和推導結果 IoU ≥0.9999、沒有未宣告的鄰接。
- `WALKABILITY`（portal）：開口、門框、門楣、標記 mesh、穿越都通過，而且在 0.30 m 包絡下可通過。只有「包絡下可通過」不成立時，判「建議不核准」（拓撲連通仍成立）；其他項不成立時判「需修正」。
- `DISPLAY`：hash 相符，mesh 外框和 `bounds_m` 差 ≤1×10⁻⁵ m。

### 2.4 對規則的修改（偏離「執行前固定」，在此揭露）

第一次對 r003 實跑後、在提出任何建議之前，改了兩處（規則版本 v1 → v1.1，JSON `rules_changelog`）：

1. **K4 縫：**v1 把所有 ≤1 mm 的縫都當成不通過，結果 27 個實體的三種用途全部「需修正」。實測的 7 條縫寬度是 2.3842×10⁻⁷ 到 4.7684×10⁻⁷ m，正好是 float32 在這些座標的 1 ULP，和 D58 處理過的同一類數值誤差。v1.1 改成：≤1×10⁻⁵ m（D58 容差）記 `INFO`，超過才不通過。每條縫的實測寬度都保留在 JSON。沒有改其他門檻。
2. **K6 可通過半徑（程式錯誤）：**v1 只要求內縮後的分量「碰到」對面的 walk，於是 `WALK_R102` 門口 0.6 m 寬的小凹槽被算成已進入房間，得到 0.599 m 的錯誤結果。v1.1 要求連通分量包含兩邊內縮面積的 ≥99%。修正後的 0.2395 m 和手算一致（門框牆面 x = 17.52 到遮屏 x = 18.0 是 0.48 m，半寬 0.24 m）。

## 3. 結果

兩個 run 的 `scene_static.json` 與全部 geometry 檔逐位元相同；除了 run 綁定之外，兩 run 的結果逐項相同（`runs_static_identical` 三項皆為 true）。以下數值取 B1。

### 3.1 輸入完整性（K1）

52 個 geometry 引用，0 個 hash 不符。`geometry_scope` 是 `STATIC_MARKED_SUBSET_NOT_APPROVED`；4 台鏡頭的 `static_validity` 都是 `NOT_EVALUATED`；所有 `visibility_index_ref` 都是 `null`。

### 3.2 實體 mesh（K2、K3）：回答 #81 §6 的 UNKNOWN

- 27 個實體（22 牆＋5 遮屏）的 geometry 檔都是**精確的封閉 mesh**：8 個頂點、6 個面，每條邊被兩個面共用；外框和 footprint 擠出的最大差 **0 m**。所以 safe 幾何足以做 `SOURCE_MESH_RAYCAST`，而且用 mesh 或 footprint＋高度做 raycast 結果相同。
- `WALL_JOINED_SHELL`：854 個頂點、840 個四邊形面，每條邊被兩個面共用；外框和 22 個牆元件的聯集外框差 0 m。52,990 個取樣點（排除 10 個貼近表面的點）中，元件聯集內 21,827 點、shell 內 21,827 點，**0 不一致**。
- shell 只含牆，不含 5 個遮屏；遮屏另有各自的 mesh。

### 3.3 walkable 推導（K5）

| 量 | 值 |
| --- | --- |
| 地板面積 | 163.1200 m²；頂點 z 全部是 0 |
| 地板 − 人體帶實體 | 159.2255 m² |
| walkable 聯集 | 136.8095 m²（與 #68 匯出報告的 136.80949624 m² 一致） |
| IoU（walkable，地板 − 實體） | 0.8592 |
| IoU（walkable，地板 − 實體，限設計範圍） | **0.9999999** |

設計範圍外的可站地面只有兩塊，都是設計稿 §1 寫明「沒有 walk polygon」的地方：

| 區塊 | XY 範圍（m） | 面積 |
| --- | --- | --- |
| N1 觀測凹室 `AREA_OBS_BAY_N` | [12.5, 15.0] × [7.0, 14.2] | 17.1360 m² |
| 北走廊北端延伸 | [15.0, 17.4] × [12.0, 14.2] | 5.2800 m² |

逐 walk：

| Walk | 面積 m² | `polygon_m` 對 mesh 的對稱差 | 實體穿透深度 m | 對推導結果的 IoU |
| --- | --- | --- | --- | --- |
| `WALK_VEST_W` | 23.8015 | 0 | 0 | 0.99999998 |
| `WALK_CORR_W` | 35.7600 | 0 | 2.3842×10⁻⁷ | 0.99999994 |
| `WALK_CORNER` | 5.7600 | 0 | 0 | 0.99999996 |
| `WALK_CORR_N` | 22.7600 | 0 | 4.7684×10⁻⁷ | 0.99999994 |
| `WALK_R101` | 29.4240 | 0 | 0 | 1.00000000 |
| `WALK_R102`（1 個洞） | 19.3040 | 0 | 1.9073×10⁻⁶ | 0.99999946 |

穿透深度是 K7 獨立重算，與契約 §3.5.1 的 r003 `OBS-002` `INFO` 同量級。沒有 ≥1×10⁻⁴ m² 的差異區塊。

**依包絡內縮（人體中心可達區）：**

| 半徑 | 內縮後面積 | IoU（walkable，內縮） | 少掉的面積 | 分量 |
| --- | --- | --- | --- | --- |
| 0.25 m（D42 名義） | 108.1755 m² | 0.7907 | 28.6340 m² | 2 |
| 0.30 m（D42 包絡） | 102.7092 m² | 0.7507 | 34.1003 m² | 2 |

所以 walkable 的語意是**地板佔用區**（地板扣掉實體 footprint），不是人體中心可達區。這符合設計稿 §1.1.1（「它不是人體半徑膨脹後的可達區」），但 K1 目前直接把 walk 多邊形當人體中心的格點範圍（K1 `engine.py` 只對負證據足跡做內縮），2d 必須先內縮再交給 K1（§5 第 2 點）。

### 3.4 連通（K6）

| 連通 | 經由 | 共用的無實體邊界 | 人體中心可通過的最大半徑 | r = 0.25 | r = 0.30 |
| --- | --- | --- | --- | --- | --- |
| `WALK_CORR_W`↔`WALK_VEST_W` | — | 7.28 m | 0.800 m | 可 | 可 |
| `WALK_CORNER`↔`WALK_CORR_W` | — | 2.40 m | 0.800 m | 可 | 可 |
| `WALK_CORNER`↔`WALK_CORR_N` | — | 2.40 m | 0.800 m | 可 | 可 |
| `WALK_CORR_W`↔`WALK_R101` | `PORTAL_R101` | 1.20 m | 0.600 m | 可 | 可 |
| `WALK_CORR_N`↔`WALK_R102` | `PORTAL_R102` | 1.20 m | **0.2395 m** | **不可** | **不可** |

- 0.800 m 是 walk 內部被遮屏收窄的寬度（遮屏與對面牆 1.6 m），不是連通處的寬度。
- 沒有未宣告的鄰接；宣告的連通與幾何鄰接一致（和 `WLK-004`／`WLK-005` 的結論相同，K7 是由幾何獨立推得）。
- 內縮 0.30 m 後的分量：{`WALK_VEST_W`、`WALK_CORR_W`、`WALK_CORNER`、`WALK_CORR_N`、`WALK_R101`} 90.00 m²，以及 `WALK_R102` 的室內 12.71 m²。0.25 m 時 `WALK_R102` 也出現在大分量裡，但只是門後的小凹槽；房間本身（13.55 m²）仍是獨立分量。
- O11 若採拓撲定義，`WALK_R102` 經 `PORTAL_R102` 算是 `WALK_CORR_N` 的通路，但人體實際走不過去。設計稿 §1.2 寫明 R102 這輪「不作人物通路」，所以 Demo 沒有受影響的查詢（`AREA_R101_FRONT`、`AREA_OBS_BAY_N` 都不經 R102）。

### 3.5 Portal（K6）

| 項目 | `PORTAL_R101` | `PORTAL_R102` |
| --- | --- | --- |
| 牆線上量到的淨寬（宣告 1.2 m） | 1.2000008 m | 1.1999998 m |
| 兩側門框 | 有 | 有 |
| 門楣在 2.4 m 以上 | 有（`WALL_R101_LINTEL`） | 有（`WALL_R102_LINTEL`） |
| 門標記 mesh 對 `opening_m` | 最大差 0 m | 最大差 0 m |
| 穿越線兩端 | `WALK_CORR_W`／`WALK_R101` | `WALK_CORR_N`／`WALK_R102` |
| 人體中心可通過 | 0.600 m ≥ 0.30 | **0.2395 m < 0.30** |
| `physical_geometry_authority` | `NOT_EVALUATED` | `NOT_EVALUATED` |

### 3.6 鏡頭視錐與遮擋（K7、K8）

| 鏡頭 | 位置所在 | 離實體最近 | 畫面內地面 | 看得到的地面 | 主要可見區（m²） |
| --- | --- | --- | --- | --- | --- |
| `CAM_W1` | `WALK_VEST_W` | 0.600 m | 137.07 m² | 27.62 m² | `WALK_CORR_W` 25.45、`AREA_R101_FRONT` 5.45、`WALK_VEST_W` 2.16 |
| `CAM_W2` | `WALK_CORR_W` | 0.100 m | 77.43 m² | 39.83 m² | `WALK_CORR_W` 25.10、`WALK_VEST_W` 14.53、`AREA_R101_FRONT` 6.81、`WALK_R101` 0.20 |
| `CAM_N1` | `AREA_OBS_BAY_N` | 0.500 m | 82.95 m² | 26.92 m² | `WALK_CORR_N` 15.15、`AREA_OBS_BAY_N` 10.26、`WALK_R102` 0.69、`WALK_CORNER` 0.31 |
| `CAM_R102_CTRL` | `WALK_R102` | 0.500 m | 128.27 m² | 6.96 m² | 只有 `WALK_R102` 6.96 |

- 沒有鏡頭在實體內。W2 到最近實體 0.100 m，和設計稿 §2、`CAM-005` 一致。
- 設計意圖都成立：CTRL 看不到 `WALK_CORR_N`（0 m²，`OBSTACLE_SCREEN_R102` 擋住門）；N1 透過窗台 0.5 m、窗楣 2.9 m 之間的觀測窗看到北走廊 15.15 m²；W1、W2 看得到 `AREA_R101_FRONT` 7.2 m² 中的 5.45、6.81 m²。
- K8：4 台共 42,567 條射線，長方體與三角面兩種 raycast 判為被擋的數目相同（10,936／3,769／5,563／12,139），**0 不一致**；只有 N1 有 1 條擦邊射線被排除。
- 這些是靜態地面可見度，不是人體可見度，也不是覆蓋證據。

### 3.7 縫（K4）

7 對實體之間有縫，全部 `INFO`：

| 實體 | 縫寬 m | 接觸方式 | 射線能穿過的最大角度 |
| --- | --- | --- | --- |
| `WALL_VEST_W`／`WALL_VEST_S` | 2.3842×10⁻⁷ | 只在邊或角 | — |
| `WALL_BAY_N_W`／`WALL_BAY_N_S` | 4.7684×10⁻⁷ | 只在邊或角 | — |
| `WALL_BAY_N_S`／`WALL_N_WINDOW_SILL` | 4.7684×10⁻⁷ | 只在邊或角 | — |
| `WALL_BAY_N_S`／`WALL_N_WINDOW_HEADER` | 4.7684×10⁻⁷ | 只在邊或角 | — |
| `WALL_W_S1`／`WALL_R101_LINTEL` | 4.7684×10⁻⁷ | 面 | 4.0×10⁻⁶ rad |
| `WALL_N_W`／`WALL_N_WINDOW_SILL` | 4.7684×10⁻⁷ | 面 | 4.0×10⁻⁶ rad |
| `WALL_N_W`／`WALL_N_WINDOW_HEADER` | 4.7684×10⁻⁷ | 面 | 4.0×10⁻⁶ rad |

shell 也保留同樣的座標（例如 y = 7.0 與 7.000000477 都在），所以 render 幾何有同樣的縫。射線要和縫面夾角小於 4×10⁻⁶ rad 才能穿過；K8 的 42,567 條射線沒有一條因此不一致。

## 4. 逐用途建議

完整的 131 列（物件 × 宣告用途）在 JSON `runs[].purposes`，每列有 `needed_by`、`validator_rules`、`k7_gates`、`notes`、`verdict`。

1. **`OCCLUSION`：建議核准** 22 個 `WALL_*`、5 個 `OBSTACLE_SCREEN_*`。證據：§3.2、§3.6 K8、§3.7。
2. **`VISIBILITY_INDEX`：建議核准** 同 27 個。證據同上，加上 §3.6 的視錐結果。鏡頭本身的 `static_validity` 與 `visibility_index_ref` 不在 O10 範圍，仍是 `NOT_EVALUATED`／`null`，要等 2c 建索引。
3. **`COLLISION`：建議核准** 同 27 個。`WALL_R101_LINTEL`、`WALL_R102_LINTEL`、`WALL_N_WINDOW_HEADER` 底高 ≥2.4 m，記為「在人體帶以上」；消費端判斷可走與淨空時要看 z 範圍，不能只看 footprint。
4. **`WALKABILITY`：**
   - **建議核准** 6 個 `WALK_*`，核准範圍寫明「地板佔用區；可達性用途要先依 body policy 的包絡半徑內縮」。
   - **建議核准** `PORTAL_R101`。
   - **建議不核准** `PORTAL_R102`。這樣 `WALK_CORR_N`↔`WALK_R102` 的連通會 fail closed，K1 把 R102 當獨立 walk，O11 不把 R102 算作通路。若使用者要保留拓撲通路，契約要先有「只限拓撲」的核准範圍（目前沒有這個欄位），見 §5 第 3 點。
5. **`DISPLAY`：建議核准** 42 個。
6. **地板 `FLOOR_GROUND`：**建議同時填 `floors[].approved_scope_ref`，範圍是 z = 0 支撐面上的 `FLOOR_GROUND` 面（163.12 m²）。依契約 §3.1「超出核准範圍一律 `UNKNOWN`」，`null` 會讓 2b 的接地投影沒有核准範圍可依；這點本文只標出，是否屬 O10 由使用者決定。

## 5. 需修正（誰修、修什麼）

幾何本身都不必改。

1. **Codex：產生新版 `scene_static`**（使用者核准後）。不改任何幾何與 geometry hash，只寫：
   - 核准的 objects：`approval_status: APPROVED`、`scope_ref`、`approval_ref`、`approval_sha256`；
   - `walkable[].approval`：`verified_by` 填 validator `controlled-scene-marker-validator.v2`（#77 @ `7bc345f`）與 K7 `k7-controlled-scene.v1`（規則 `k7-controlled-scene-rules.v1.1`），`verification_sha256` 填本報告 JSON 的檔案 SHA-256；
   - `PORTAL_R102` 不核准 `WALKABILITY`（`DISPLAY` 照核准）；
   - `floors[].approved_scope_ref`（若使用者同意 §4 第 6 點）；
   - `geometry_scope` 換成核准後的值；`scene_version` 依契約 §3.1 規則處理（幾何沒變，版本是否遞增要 Codex 依 §3.1／§3.4 決定）。
2. **2d adapter（Codex）與 K1（Claude）：**K1 的 `polygon_floor_map` 要收到內縮後的 walkable，不能直接用 `polygon_m`。內縮半徑由 Claude 在 K1 設定檔決定：建議 walkable 用 0.25 m（名義人體；內縮越少、可達範圍越大，對涵蓋率較保守），負證據維持 0.30 m 包絡（D42）。兩種半徑下 `PORTAL_R102` 都不通，不影響本文的建議。`WALK_R102` 的洞（#81 §3.4 第 5 點）：內縮 0.25 m 或 0.30 m 後，遮屏外擴的範圍和房間西界內縮線相接，結果的每一塊都沒有內部洞（實測），所以 K1 只收外環也不會漏掉遮屏，不需另列 `unknown_regions`。這只對 r003 成立；內縮前直接取外環會把遮屏 0.36 m² 算成可走。
3. **契約 v1.2（Claude 起草、Codex 確認）：**
   - §3.4 寫明 walkable 的語意是地板佔用區，可達性消費端要依 `body_policy` 內縮；
   - 考慮在 portal 或 connection 加上人體可通過寬度，或「只限拓撲」的核准範圍；
   - §3.5 補一句：實體之間 ≤1×10⁻⁵ m 的縫是 float32 誤差，raycast 端以閉合聯集或同等容差處理（和 D58 同一依據）；
   - `AREA_*` 只有 `DISPLAY` 用途，但 2c 把它當查詢多邊形；用途列舉沒有「查詢目標」，要確認這不需要核准。
4. **2c（Codex）：**可見範圍索引用元件長方體或 shell＋遮屏都可以（§3.2、§3.6 K8 等價），記錄用了哪一種；本文的地面足跡只是合理性檢查，不能當索引。

## 6. 沒有驗證或仍是 UNKNOWN

- **safe 幾何是否涵蓋 render 中所有遮擋物**（例如天花板、燈具、鏡頭支架）：`UNKNOWN`。只讀 safe 靜態檔無法回答，要靠 D47 的 RGB 人工收據或 `.blend` 盤點（後者要另外授權）。天花板（3.2 m）沒有匯出；鏡頭都在 3.2 m 以下往下看，對地面射線沒有影響。
- 幾何的實體精度：本文只證明數值一致（mesh、footprint、walkable、設計範圍之間），不證明和真實建模誤差的關係（設計稿標 `UNKNOWN`）。
- 鏡頭校正精度與 `static_validity`：只做視錐合理性，沒有評估校正誤差。
- 人體高度的可見度（頭、軀幹）：沒有算；只算地面。
- 路線相關檢查：依 §7 不讀路線，沒有做。
- mypy、全套測試：沒有跑。

## 7. 重現

```bash
PYTHONPATH=src .venv/bin/python scripts/verify_controlled_scene_k7.py \
  --safe-dir <資產 repo>/data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-a-5fps-v1-r001/safe_bundle \
  --safe-dir <資產 repo>/data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-b1-5fps-v1-r001/safe_bundle \
  --output docs/engineering/CONTROLLED_SCENE_R003_K7_VERIFICATION_20261020.json \
  --figures-dir docs/engineering/figures/k7_r003
```

約 30 秒。重跑得到相同的 canonical `output_sha256`：`ea1cb5e33fc1620c7f9fe5cf3375f62e41b434e2bd9a6c49c5f653efa74b5cf7`（JSON 內，不含自身；和檔案 SHA-256 是兩種 hash）。

## 8. 實際產出 / Actual output

見 PR 描述與 #68 留言（同一份範本）。
