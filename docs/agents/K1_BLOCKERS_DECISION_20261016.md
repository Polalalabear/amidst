# K1 Office 4.4 → 8.6 s 阻擋：決策草稿（2026-10-16）

> 使用者已於 2026-10-16 核准本文建議，紀錄見 [#25](https://github.com/Polalalabear/amidst/issues/25) D4–D13；第 3、6、9 項依 D5、D6、D4 調整。

> 狀態：**草稿，未追蹤、未 commit**。只做分析，沒有改程式、契約或 issue。
> 讀取來源（皆以 `git show <ref>:<path>` 讀取，未切換 checkout）：
> - K1：`origin/claude/k1-hypothesis` @ `28e6be5`（PR #33）
> - K0 契約草稿：`origin/claude/k0-data-contracts` @ `7e2589c`（PR #10，未核准）
> - 計畫與診斷：`origin/claude/office-demo-visualization` @ `dc10d57`
> - issue #15、#19、#25、#29、#30
>
> 數字只取自已提交的 JSON：
> - `data/scene_audit/school_v3_approved_scale_20261006/geometry.json`（`a1423622…`）
> - `data/engineering/blender_workbench_20261011/frame_queries.json`（`8b64beaf…`）
> - `docs/engineering/OFFICE_PRESETS_20261016.json`
> - `configs/office_contact_v2.json`
> - `configs/office_demo_fixture_v1.json`
>
> 以上檔案都從 K1 分支讀取。另外引用 #25 中 K2 結果紀錄的數字。沒有讀 GT、渲染器軌跡、可見性或深度，也沒有渲染、推論或打開影像。幾何距離由本草稿用 shapely 從上述 JSON 重算，標為「重算」。

## 0. 摘要

| 阻擋 | 主要根本原因 | 建議 | 負責 |
| --- | --- | --- | --- |
| 1. 4.4 s 端點不可用 | **資料＋契約**：v1 把同一輪廓切成兩塊，v2 又把它們合回一塊，因此觸發 `AMBIGUOUS_MERGE`。契約 §4.1 遇到這個旗標一律判 UNKNOWN。 | **1A**：4.4 s 維持 UNKNOWN。由呼叫端依明文規則，改用同一 track 最近一個 READY 的觀測當盲區起點（預期 4.2 s），並在畫面與 trace 標明。 | Claude K0 文字；Codex C4a 估計、C4b 選端點 |
| 2. 8.6 s 端點落在障礙物 | **標註**：`OBSTACLE_1F_OFFICE_01` 是一整塊 7.90 × 4.64 m 的矩形，蓋住房間北半部。估計器結果也還沒產生。 | **2A**：等 C7 從網格推導逐張座椅的地圖、K7 核對後，再以 C4a 的 8.6 s 區間觀測加上推導地圖裁剪。**2C** 是事先約定的備案。 | Codex C7、C4a；Claude K7、K1 |
| 3. 門口缺口 | **標註**：threshold 面與 walkable 面沒有相接，K1 的嚴格鄰接規則又不橋接。 | **3A**：不處理。在速度上限 2.0 m/s 下，這兩處缺口不影響本案例（重算如下），交給 C7／K7。 | Codex C7、Claude K7 |

**Demo 主軸：** 「4.4 → 盲區 → 8.6」要誠實呈現，必須同時有 C4a 的估計結果和 C7 的推導地圖，兩者都在關鍵路徑上，最晚 **10/24（CP2）** 判定。建議同時準備 C6 的人形代理路線，作為 P0 的備援；這需要使用者在 CP1 授權渲染。

## 1. 已查證的共同事實

| 項目 | 數值 | 來源 |
| --- | --- | --- |
| 4.4 s FRONT 選定觀測 | `observation:add9f687…`；bbox `[826, 119, 832, 147]`（高 28 px、寬 6 px）；`measurement_count: 2`；`world_position` (34.580, 49.563)；`projection_quality` 0.1876 | `frame_queries.json` `office.response.items[0]` |
| 4.4 s 旗標 | 兩個觀測都是 `[LOW_INCIDENCE, CONTACT_OCCLUDED, AMBIGUOUS_MERGE]` | `OFFICE_PRESETS_20261016.json` `required_flag_reasons["4.4"]`；`OFFICE_PRESETS_20261016.md:16` |
| 4.4 s 兩個元件 | v1 4-連通把輪廓切成兩個元件，兩者的地板交點相距 4.395 m | `OFFICE_MARKER_DIAGNOSIS_20261016.md:12` |
| FRONT bbox 上緣 | 其他幀的 bbox 上緣都在 y = 11–12；只有 4.4 s 的選定觀測上緣是 y = 119，也就是下半塊碎片 | 診斷 `:22`；`frame_queries.json` |
| 8.6 s REAR 觀測 | `observation:99716654…`；bbox `[274, 9, 287, 99]`；(31.544, 53.649)；`projection_quality` 0.1383 | `frame_queries.json` `items[1]` |
| 8.6 s REAR 旗標 | 已提交的 receipt **沒有列出逐點原因**，記為 UNKNOWN。K2 統計顯示 REAR 7 點在 v2 下全部被拒，原因都是 `LOW_INCIDENCE`。 | `OFFICE_PRESETS_20261016.json`（只列 0.4／0.6／1.8／2.0／4.4）；#25 K2 紀錄 |
| `OBSTACLE_1F_OFFICE_01` | 4 個頂點的矩形，x 28.87–36.77、y 52.44–57.08，面積 36.64 m²；`support: FOOTPRINT`；z = 25 BU | `geometry.json`（重算） |
| `WALK_1F_OFFICE` | 6 個矩形，共 37.93 m²。障礙物 01 的西側只剩 0.59 m 寬（x 28.28–28.87），東側只剩 0.16 m 寬（x 36.77–36.93） | `geometry.json`（重算） |
| 8.6 s／8.8 s 點 | 兩點都在障礙物 01 內，離可走區分別為 2.67 m 和 2.58 m。最近的可走點是西側窄帶 (28.87, 53.65) | 重算；K1 `tests/unit/test_blind_hypothesis_office.py:196-206` |
| 4.4 → 8.6 直線距離 | 5.09 m，平均 1.21 m/s。上限可達距離為 2.0 × 4.2 = 8.4 m | 重算；`configs/blind_hypothesis_v1.json` |
| 樓層高度 | `geometry.json` 的 1F 平面為 25 BU = 0.6175 m（`PROPOSED_FLOOR_1F`，`approval_id: null`）；後端投影平面為 0.4959 m，差 0.1216 m | `geometry.json` `floors[0]`；IO 契約 `:47` |
| 舊圓柱尺寸 | 高 `assumed_target_height_m` 2.9393、半徑 0.1482，標為 `PREDECLARED_SYNTHETIC_TARGET_SETTING_NOT_GT` | `configs/office_contact_v2.json` |

## 2. 阻擋 1：4.4 s FRONT 端點不可用

### 2.1 根本原因

- **資料。** 選定觀測只是目標的下半塊（bbox 高 28 px，上緣 y = 119）。同一幀還有另一個 v1 元件（`measurement_count: 2`），兩者地板交點相距 4.395 m。v2 用 8-連通把兩塊合回同一個元件，任務 3 的對應規則因此標上 `AMBIGUOUS_MERGE`（計畫 `OFFICE_DEMO_PLAN_20261101.md:118`）。所以這裡的旗標其實來自 **v1 把一個目標切成兩塊**，不是兩個目標被合併。不過旗標本身無法區分這兩種情況。
- **契約。** IO §4.1（`OFFICE_INTERVAL_OBSERVATION_V1.md:139`）規定，只要帶 `AMBIGUOUS_MERGE` 就判 `HEAD_ANCHOR_UNRELIABLE`，連頭頂射線區間都不嘗試。若依 IO-Q1 草案用 **v1 bbox 上緣**當頭頂，這個觀測的上緣 y = 119 是切開的位置，不是頭頂，因此對這個觀測來說，判定不可靠是正確的。BH §3.1（`OFFICE_BLIND_HYPOTHESIS_V1.md:75-77`）再規定模組不得自行改用鄰近觀測。K1 照契約實作（`engine.py:243`，得到 `GROUND_ESTIMATE_UNKNOWN:HEAD_ANCHOR_UNRELIABLE`）。
- **估計器。** C4a（#15）還沒有產出。就算旗標問題解決，舊圓柱的頭頂射線幾乎是水平的。依診斷 §4（`OFFICE_MARKER_DIAGNOSIS_20261016.md:39-45`，FRONT 離地約 3.29 m、水平距離約 17.8 m），頭頂平面的入射角約 0.02，1 px 約 1.1 m。以先驗 2.9393 ± 0.05 m 粗估區間長約 5 m；± 0.10 m 則約 10 m，會超過 `MAX_SEGMENT_LENGTH_M = 8.0`，觸發 `SEGMENT_TOO_LONG`。這是本草稿的估算，FRONT 實際位置與焦距沒有查證。
- **標註。** 椅背遮擋物在標註中只有平面足跡，沒有高度，所以 `OCCLUDER_BEHIND` 裁剪會是 `NOT_AVAILABLE`。需要 C7 從網格取得椅背高度後才能用。

### 2.2 選項

| 選項 | 改什麼 | 負責 | 時程影響 | GT／CP1 | Demo 誠實度 |
| --- | --- | --- | --- | --- | --- |
| **1A 呼叫端改用同 track 最近的 READY 端點** | BH 契約新增端點選擇規則：使用 `candidate_ref` 時，若盲區邊緣的觀測不是 READY，C4b 沿同一 `track_ref` 往盲區外側找第一個 READY 的觀測，最多回溯 N 秒（建議 1.0 s）。trace 記錄 `ENDPOINT_SELECTED_EARLIER_SAME_TRACK` 與被略過的 ref；模組本身仍不替換端點。4.4 s 在畫面上標「已觀測、接地不可用」。 | Claude 擬契約文字（K0）；Codex C4a 產出 3.6–4.4 s 的估計；C4b 實作選擇規則 | 小。契約一句話；C4a 本來就要跑 FRONT 全段 | 不讀 GT；符合 CP1 | 好。FLAGGED 點維持 UNKNOWN，替換有明確標示。代價是盲區變成 4.2 → 8.6 s，demo 台詞要調整 |
| 1B 條件放寬 `AMBIGUOUS_MERGE` | IO §4.1 改為：若 v2 只有一個元件，且被合併的 v1 元件屬同一 track、上下堆疊，就允許做 SEGMENT，頭頂改用 v2 遮罩最高點（等於決定 IO-Q1、IO-Q3）。 | Codex C4a（需要 v1→v2 元件幾何）；Claude 改 K0 | 中。C4a 要多寫一條規則和測試，佔 10/19–10/23 的時間 | 不讀 GT；符合 CP1 | 中。「同 track、上下堆疊」是啟發式規則，可能把真正的雙目標合併當成單一目標；必須保留 FLAGGED 並在 `constraints_applied` 記錄。依 2.1，算出來仍可能是 `SEGMENT_TOO_LONG` |
| 1C 把 FLAGGED 的 v1 點當 POINT，加大圓盤半徑 | 違反 IO §4.1「FLAGGED 不得升格」，以及 K1 `engine.py:264-265` | — | — | 不涉 GT，但違反契約 | **差**。等於把一個已知會跳 1.7–2.0 m 的點當成可靠端點。**不建議** |
| 1D 不用 Office 4.4 s 當主軸 | 見 §5 | — | — | — | — |

### 2.3 建議

採 **1A**。理由：
1. 契約唯一要補的是呼叫端的選擇規則；IO 和 BH 原有的 fail-closed 條款都不用改。
2. 4.2 s 在 v1 只有一個元件。依診斷，FRONT 23 幀有 24 個觀測，只有 4.4 s 有兩個，所以 4.2 s **不可能**帶 `AMBIGUOUS_MERGE`，它的 bbox 上緣也在 y = 11–12，頭頂錨點正常。4.2 s 的逐點原因仍是 UNKNOWN，所以 1A 的前提要等 C4a 產出後才能確認。
3. 1B 留到 11/01 之後，作為 IO-Q1／IO-Q3 的正式答案。

風險：舊圓柱的頭頂射線區間可能過長，4.2 s 也可能得到 `SEGMENT_TOO_LONG`。如果回溯 1.0 s 內都找不到 READY，起點就誠實維持 UNKNOWN，此時改走 §5 的備援。

附帶的 K1 後續：如果先驗範圍為 0（`min_m == max_m`），SEGMENT 會退化成一個點，而 K1 目前**不會**為 SEGMENT 加上 `pixel_sensitivity_m` 的寬度（`engine.py:273-282`）。K0 應規定先驗範圍必須大於 0，或規定 SEGMENT 也要加寬。

### 2.4 需要使用者決定

- 是否核准 1A：端點不可用時，呼叫端可沿同一 track 改用最近的 READY 觀測，最多回溯 1.0 s，並明確標示。
- `AMBIGUOUS_MERGE` 是否在 11/01 前一律維持 UNKNOWN（建議：是，1B 延後）。
- 舊圓柱的頭頂先驗是否可用預先宣告的 2.9393 m，容差取多少（例如 ± 0.10 m），並接受很長的區間或 `SEGMENT_TOO_LONG`。

## 3. 阻擋 2：8.6 s REAR 端點落在障礙物內

### 3.1 根本原因

- **標註（主因）。** `OBSTACLE_1F_OFFICE_01` 是一個軸對齊矩形，7.90 × 4.64 m，面積 36.64 m²，`support: FOOTPRINT`。它從 y 52.44 一直延伸到北牆（walkable 的北界是 57.06），東西兩側只留 0.16 m 和 0.59 m 的窄帶。換句話說，標註認為**房間北半部任何位置都不可走**。fixture 寫到「RGB shows seating context」，可見這塊矩形是把整片座椅區當成一個障礙物，沒有畫出座椅之間的走道。8.6 s 和 8.8 s 兩個點都在這塊裡面（離可走區 2.67 m、2.58 m）。C7（#29）本來就計畫把已抽出的 16 張椅子和講台升級成推論用地圖。
- **估計器。** C4a 還沒產出 8.6 s 的估計，K1 測試因此判 `GROUND_ESTIMATE_NOT_PRODUCED`（`test_blind_hypothesis_office.py:175-179`）。逐點的 `contact_quality` 原因沒有提交，記為 UNKNOWN。若依 K2 統計只有 `LOW_INCIDENCE`，IO §4.1 會嘗試算 SEGMENT。
- **契約。** 規則本身是對的。但在現有標註下，就算 C4a 算出 SEGMENT，`WALKABLE_AREA` 裁剪後很可能變空，得到 `SEGMENT_EMPTY_AFTER_CONSTRAINTS`（IO §4.3）。若是 POINT，則會在 K1 `engine.py:750-761` 得到 `ENDPOINT_OUTSIDE_WALKABLE`。所以**只等估計器並不能解除這個阻擋**。
- **資料（待查，UNKNOWN）。** 標註和 `geometry.json` 的 1F 平面高 0.6175 m，後端投影用的是 0.4959 m，差 0.1216 m。如果這個房間的真實地板在 0.6175 m，以入射角約 0.138（管線地圖 §6：`projection_quality` 等於入射角）估算，投影點會往遠離攝影機的方向偏約 0.88 m。這可以解釋一部分落差，但不足以解釋 2.67 m。原因待 C7 從網格量測確認。

### 3.2 選項

| 選項 | 改什麼 | 負責 | 時程影響 | GT／CP1 | Demo 誠實度 |
| --- | --- | --- | --- | --- | --- |
| **2A C7 推導地圖＋C4a 區間觀測** | C7 範圍明確包含 Office 房間：逐張座椅足跡、講台、地板支撐面的 z。K7 核對後，K1 改接推導地圖（只換 `FloorMap` builder，演算法不改）。C4a 的 8.6 s SEGMENT／POINT 再用推導地圖裁剪。 | Codex C7、C4a；Claude K7、K1 | **關鍵路徑**。C7 最晚 10/22 交付，K7 才能在 10/24 前完成，K1 在 10/25 切換。C7 不在原 §7 時程內，需確認 Codex 的排程 | 符合 D3。注意：K7 的 GT 路線檢查只能當**離線驗證**；若因 GT 違規去改地圖，就等於 GT 洩漏到推論輸入，該路線必須從 RQ2 排除 | 好。如果推導地圖顯示座椅之間有可走空間，端點合法；如果仍在障礙物內，就誠實維持 UNKNOWN |
| 2B 端點吸附到最近的可走點 | K1 放寬 `ENDPOINT_OUTSIDE_WALKABLE`，把端點平移 2.67 m 到西側窄帶 | — | 小 | 違反 BH §3.1「不替換」與 IO §5 | **差**。等於捏造端點位置。**不建議** |
| 2C 座椅區標 `UNKNOWN`，不從可走區扣除 | BH 契約允許 `checks.walkable` 為 `UNKNOWN`（比照 §5.1 `unseen` 的 UNKNOWN）：C7 tier 為 `UNKNOWN` 的區域可以進入格點，但經過的路徑標 `walkable: UNKNOWN`，畫面以不同樣式顯示。地圖仍來自 C7，只是座椅區暫標 UNKNOWN。 | Claude 改 K0、K1；Codex C7（只需粗分 tier）、C4b | 中。K1 要改格點和檢查，約 1 天 | 符合 D3；不讀 GT | 中偏好。路徑穿過座椅區會被明確標示為「可走性未知」，不會被畫成已驗證。前端（K4）必須清楚區分樣式 |
| 2D 換 REAR 的其他時刻 | 改用 9.0 s 之後的 REAR 點 | Codex | 小 | — | 8.8 s 同樣在障礙物內；其他時刻沒有提交的座標（UNKNOWN）。價值低 |

### 3.3 建議

以 **2A** 為主。若 C7／K7 在 **10/22** 前明顯趕不上，啟用 **2C** 作為事先約定的備案，並在 CP2 由使用者確認。**拒絕 2B。**

另外建議把「Office 房間地板支撐面的 z 與 0.4959 m 是否一致」列入 C7 的驗收項目，因為它會同時影響所有 Office 投影點和 walkable 的高度。

### 3.4 需要使用者決定

- C7 是否把 Office 房間（逐張座椅、講台、地板 z）列為 10/22 前必交的關鍵路徑。
- K7 的 GT 路線檢查發現違規時，是禁止據此修改地圖，還是允許修改但把該路線排除於 RQ2 評估。
- C7 膨脹可走區時用哪個身體半徑：舊圓柱 0.1482 m 或人形 0.25 m，或依場景分開設定。
- 若 C7／K7 在 10/22 前趕不上，是否接受 2C（座椅區以 `walkable: UNKNOWN` 進入假設），還是讓 Office 維持 UNKNOWN。

## 4. 阻擋 3：門口缺口

### 4.1 根本原因

- **標註。** 兩處 threshold 面與相鄰的 walkable 面之間有縫：
  - `WALK_1F_AUDITORIUM_OFFICE_THRESHOLD` 的 x 上界是 37.42，`WALK_1F_AUDITORIUM` 的 x 下界是 37.54，縫寬 0.1235 m；
  - `WALK_1F_CORRIDOR_03` ↔ `WALK_1F_AUDITORIUM_THRESHOLD` 縫寬 0.1696 m。

  `PORTAL_1F_AUDITORIUM_OFFICE` 的足跡與 threshold 面完全相同（x 36.93–37.42），所以沒有蓋住這道縫（K1 `test_blind_hypothesis_office.py:216-229`）。
- **契約。** BH §4.1 規定，相鄰只限同一多邊形內，或跨越 portal。K1 照做，沒有容差。

### 4.2 對本案例的影響（重算）

- 起點 (34.58, 49.56) 到 `WALK_1F_AUDITORIUM` 2.96 m，終點到它 6.00 m。任何繞進 auditorium 的路徑**至少** 8.96 m，超過上限可達的 8.4 m（2.0 m/s × 4.2 s）。
- `PORTAL_1F_OFFICE`／走廊離起點 7.13 m、離終點 11.6 m，同樣到不了。
- **結論：只要凍結的速度上限低於 8.96 / 4.2 = 2.13 m/s，這兩處缺口不會改變 4.4 → 8.6 s 的任何結果。** 上限一旦 ≥ 2.14 m/s，auditorium 變成可達，缺口就會讓帶狀區**比應有的窄**，也就是過度自信。

### 4.3 選項

| 選項 | 改什麼 | 負責 | 時程影響 | GT／CP1 | Demo 誠實度 |
| --- | --- | --- | --- | --- | --- |
| **3A 不處理，由 C7／K7 解決** | 無。K7 把缺口列為標註缺陷；C7 的連通性由網格推導（D3） | Codex C7、Claude K7 | 無 | 符合 D3 | 好。本案例不受影響 |
| 3B K1 builder 加容差橋接 | 縫寬 ≤ 0.2 m 且相鄰有 PORTAL 時就連接 | Claude K1 | 小 | 不涉 GT。但 D3 規定標註只作核對，這是一次性工作 | 中。新增一條未經驗證的連通規則 |
| 3C 補 PORTAL 標註或修改 `geometry.json` | 修改已核准的資產 | Codex | 小 | 需要資產修改授權；與 D3 方向相反 | 中 |

### 4.4 建議

採 **3A**。在 K1 的 Office fixture 補一個斷言：「繞經 auditorium 的下界 8.96 m > 8.4 m」，讓這個前提可以重算；這是 K1 的後續小事，本草稿不改。

### 4.5 需要使用者決定

- D2 凍結速度上限時，請注意 ≥ 2.14 m/s 會讓這兩處缺口開始影響 Office 結果（建議上限維持 2.0 m/s）。

## 5. Demo 主軸的整體建議

### 5.1 最小誠實路徑（Office，10/29 前）

| 日期 | 步驟 | 負責 |
| --- | --- | --- |
| 10/18（CP1） | 核准 1A 的端點選擇規則、K1 的 SEGMENT 最小寬度、2C 備案條款，寫入 K0 草稿 | Claude 擬稿、Codex 確認、使用者核准 |
| 10/19–10/21 | C4a 產出 FRONT 3.6–4.4 s 與 REAR 8.6–9.0 s 的區間觀測，記錄每點的 READY 或 UNKNOWN 原因 | Codex C4a |
| 10/22 | C7 交付 Office 房間的推導地圖：座椅、講台、地板 z | Codex C7 |
| 10/22–10/24 | K7 核對（IoU、portal、離線 GT 路線）；K1 改接推導地圖並重跑 Office fixture | Claude K7、K1 |
| **10/24（CP2）判定** | Office 回應若為 READY，就作為現場 Demo；若為 UNKNOWN，則把「系統拒絕推測及原因」當成工程主張①的現場畫面，P0 假設路徑束改用 §5.2 的備援 | 使用者 |
| 10/24–10/27 | C4b 接 API、K4 假設路徑束 | Codex、Claude |

**呈現方式：**
- 4.4 s 標「已觀測、接地不可用（FLAGGED）」，假設路徑束從 4.2 s 的區間觀測開始。
- 8.6 s 以區間觀測（線段）顯示，不畫成點。
- 若採用 2C，穿過座椅區的路徑使用「可走性未知」的樣式。

計畫 §9 固定的跳轉時間點（0.0、4.4、6.0、8.6 s）不用改。

### 5.2 做不到時的替代方案

| 替代 | 可行性 | 誠實度 | §7 刪減順序 |
| --- | --- | --- | --- |
| **C6 基準路線（人形代理）** | 需要使用者在 CP1 授權渲染；依 §7，10/24–10/27 渲染，時程緊。路線規劃時可以讓盲區兩端腳點可見，端點就是 PASS 的 POINT，K1 可直接 READY。這是規劃，不是拿 GT 當推論輸入。路線集合須在看到結果前固定，比照 D2 | 好 | §7「必保」包含「多攝影機或多路線資料」與「P0 盲區假設」，因此 C6 的一條路線屬於必保範圍。可刪的是 P2 的批次量化（10–15 條），不是第一條 |
| Office 換時間區間 | 實質上就是 1A。8.6 s 端端點仍受阻擋 2 限制 | 好 | 不刪任何項目 |
| 控制場景 `blender-contact-control` | v2 下 union 47/50 個時刻有位置，只缺 3 個時刻，沒有有意義的盲區；motion／association 層也不可用（`OFFICE_PRESETS_20261016.md:8,18`） | — | **不適合 RQ2**，只適合 RQ1 |
| 預製圖：K1 合成地圖結果 | 已有：兩房間加門口、障礙物繞行（K1 合成測試 40 項） | 好，但必須標明是合成地圖、不是 Office | 依 §9「未完成者用預製圖」，可放在研究段 |

**建議：** 兩條線並行。Office 走 1A + 2A（2C 備案）；同時請使用者在 CP1 授權 C6 至少渲染**一條**單房間、兩端腳點可見、速度落在 D2 範圍內的路線，作為 P0 備援。10/24 再決定哪條當現場主軸。即使 Office 最後是 UNKNOWN，也應在 Demo 中保留這一段，作為 fail-closed 的實例，不要藏起來。

## 6. 需要使用者決定的事項（彙總）

1. 是否核准 1A：端點不可用時，呼叫端沿同一 track 改用最近的 READY 觀測，最多回溯 1.0 s，並明確標示。
2. `AMBIGUOUS_MERGE` 是否在 11/01 前一律維持 UNKNOWN（1B 延後）。
3. 舊圓柱的頭頂先驗是否可用預先宣告的 2.9393 m，容差取多少。
4. C7 是否把 Office 房間（逐張座椅、講台、地板 z）列為 10/22 前必交的關鍵路徑。
5. K7 的 GT 路線檢查發現違規時，禁止據此改地圖，還是允許修改但把該路線排除於 RQ2。
6. C7 膨脹可走區用的身體半徑：0.1482 m、0.25 m，或依場景分開。
7. C7／K7 在 10/22 前趕不上時，是否接受 2C（`walkable: UNKNOWN`），還是讓 Office 維持 UNKNOWN。
8. D2 凍結速度上限時是否維持 ≤ 2.0 m/s（≥ 2.14 m/s 會讓門口缺口開始影響結果）。
9. 是否在 CP1 授權 C6 至少渲染一條人形代理路線，作為 P0 備援。
10. 10/24（CP2）由使用者選定現場 Demo 主軸：Office 或 C6。

## 7. 未查證與 UNKNOWN

- 4.2 s 與 8.6 s 的逐點 `contact_quality` 原因：已提交的 receipt 沒有列出，記為 UNKNOWN。
- §2.1 頭頂射線區間長度：依診斷 §4 的近似值（FRONT 高 3.29 m、距離 17.8 m）粗估，沒有用實際校正計算。REAR 攝影機高度 UNKNOWN。
- 地板 z 差 0.1216 m 的原因、0.88 m 偏移的估算，以及 `projection_quality` 的單位（管線地圖寫「等於入射角」，未確認是否為弧度）：UNKNOWN。
- 座椅之間是否有足以讓 0.1482 m 或 0.25 m 半徑通過的走道：要等 C7，UNKNOWN。
- C7 的實際排程：issue #29 沒有日期，UNKNOWN。
- 本草稿沒有執行任何測試、渲染或推論；幾何數字由已提交的 JSON 重算。
