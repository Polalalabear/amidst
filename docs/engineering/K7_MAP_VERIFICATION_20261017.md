# K7 地圖獨立驗證 — 2026-10-17

Issue [#30](https://github.com/Polalalabear/amidst/issues/30)（CP2 #26，**未核准，不可 merge**）。Model / effort：Sonnet 5.5 / high。機器可讀結果：[K7_MAP_VERIFICATION_20261017.json](K7_MAP_VERIFICATION_20261017.json)；疊圖：[figures/k7/](figures/k7/)（15 張，每張 < 110 KB）。

驗證對象：C7（PR #40，分支 `codex/c7-source-map`，commit `7214ef7`）輸出的 `C7_OFFICE_SOURCE_MAP_20261017.json` 與 `C7_DEMO_SOURCE_MAP_20261017.json`。工具獨立於 C7：只用 shapely 讀地圖 JSON，沒有 import `source_floor_map.py`，也沒有重用 `verify_demo_source_map.py`。路線 GT 只用於離線評估；本報告與 JSON 只含違規摘要（時刻、距離、區域），不含路線座標，也沒有任何結果回流到地圖（D10）。

## 1. 結論

- **沒有任何 GT 路線違規**：6 條已渲染 run 的 50 個取樣點全部落在對應半徑的推導可走區內（0 違規）。最緊的是禮堂 control run（舊 r=0.1482 m），最小餘裕只有 **0.019 m**。
- **Office 區（`WALK_1F_OFFICE`）判 `UNKNOWN`**：Office 辦公區內的標註 `OBSTACLE_1F_OFFICE_01/02` 與來源網格不一致。來源網格在這兩塊標註障礙物多邊形內有 **64.4 m²** 的人形身體中心可走區（`OFFICE_01` 30.3 m²、`OFFICE_02` 34.3 m²；含被薄牆隔出的內室），標註則整塊視為障礙物；以同一半徑侵蝕基準計算的推導獨有面積為 66.4 m²。只比 `WALK_*` 多邊形本身時 IoU 是 0.877，把這兩塊障礙物納入比較範圍後降為 0.253（見 §4、§7）。
- **禮堂（`WALK_1F_AUDITORIUM`）判 `SOURCE_DERIVED_VERIFIED`，但座椅區必須另列 `UNKNOWN`（D11）**：C7 的兩份地圖都沒有任何 `UNKNOWN` 區；16 張椅子的座椅外包絡（31.4 m²）內有 **9.36 m²**（人形）／**11.98 m²**（舊半徑）標成 `walkable: TRUE`（排與排之間的走道）。
- **舊半徑 r=0.1482 m 的有效緩衝只有 0.1484 m，小於 K1 契約 §12.4 的 0.15 m 門檻**；人形 r=0.25 m（緩衝 0.2503 m）不受影響。因此舊半徑地圖不適合給 K1 當輸入。
- **比一格還窄的特徵**：人形地圖在 Office 範圍有 4 個窄於 0.25 m 的可走片段（最長 0.40 m，寬 0.16–0.18 m，皆非通道）；Demo 範圍 20 個，其中 10 個長於 0.5 m（最長 2.17 m、寬 0.12 m）。「比一格薄的牆」在身體中心地圖裡不存在（牆為零厚度線，已被膨脹成 ≈ 0.50 m），但原始障礙物有 65 處（Demo）比一格薄。
- **K1 實際 0.25 m 格點下，Office 人形地圖的兩個窄頸沒有把地圖切斷**（1 個連通塊，詳見 §4.4）。
- 其他區域見 §6 等級表：17 個 1F `WALK_*` 區域中 6 個 `SOURCE_DERIVED_VERIFIED`、7 個 `UNKNOWN`、4 個 `ANNOTATION_ONLY`。

## 2. 判定規則（判定前固定）

規則寫在 `src/amidst/evaluation/map_verification.py::GRADING_RULES`，並原樣寫入 JSON 的 `grading_rules`。

| 項目 | 規則 |
|---|---|
| 比較基準 | 以身體半徑 r 侵蝕標註再比：`A = (所有 WALK_* 聯集 − r) − (OBSTACLE_* 膨脹 r)`；推導地圖已是身體中心可走區，不再侵蝕。兩邊都裁到 `ROI − r`，避免 ROI 切邊假差異 |
| 比較範圍 | `WALK_*` 區域加上與之相接的 `OBSTACLE_*`（見 §7 偏離說明） |
| IoU | 人形（r=0.25 m）地圖逐區域，門檻 **≥ 0.80**；舊半徑 IoU、侵蝕前（來源支撐面 − 障礙物 vs 標註）IoU 另列參考，不入判定 |
| 涵蓋率 | 區域被地圖 ROI 涵蓋的面積比例 < **0.50** → `ANNOTATION_ONLY` |
| 門口 | 區域相鄰（0.6 m 內）的每個 `PORTAL_*` 必須配到一個寬度 ≥ 2×r（人形 0.50 m）的推導開口，開口軸向一致、與標註寬度重疊 ≥ 0.50 m、垂直位置在 0.6 m 內，且穿越線兩側 0.5 m 皆在可走區內。標註近似方形（長寬比 < 1.5）時兩個軸向都試。完全位於 ROI 內才評估 |
| 路線 | 區域內 GT 取樣點（身體中心）離推導可走區 > 1e-4 m 即違規；0 違規才過 |
| 等級 | 涵蓋率 < 0.50 → `ANNOTATION_ONLY`；否則 IoU ≥ 0.80 **且** 門口全配對 **且** 0 路線違規 → `SOURCE_DERIVED_VERIFIED`；其餘 → `UNKNOWN` |
| 不影響等級 | 比一格窄的特徵、推導但未標註的開口、無路線（`route check: N/A`）都只列出 |
| D11 | 座椅外包絡內有 `walkable: TRUE` → 該外包絡另列 `UNKNOWN`，並從所屬區域的 IoU 兩側扣除 |
| 比一格窄 | 格距 0.25 m（`configs/blind_hypothesis_v1.json::grid_step_m`）；可走區以 0.125 m 開運算後消失的部分、不可走區以 0.125 m 閉運算填平的部分、原始障礙物以 0.125 m 開運算後消失的部分，面積 ≥ 0.005 m² 才列出；長 ≥ 0.5 m 另標為細長特徵 |

## 3. 輸入與可重現性

| 輸入 | SHA-256 | 備註 |
|---|---|---|
| `C7_OFFICE_SOURCE_MAP_20261017.json` | `53c3771327ad71e26f0a5f1f4db580eaafb7bc7d028b9c250c9f401495bbcd61` | C7 `7214ef7`（`git show` 取出，存於 scratchpad） |
| `C7_DEMO_SOURCE_MAP_20261017.json` | `79da9ba747c38c62731c50c91c76d936a97042cba5551451b85047690cf6ca37` | 同上 |
| `geometry.json`（school_v3 approved scale） | `a1423622d23f9267ba345922e96e91e3852e1e16dc7d33ecf5b33405ca131e89` | LOCAL；單位 0.0247 m/BU |
| 6 條離線路線（`trajectory_plan.json`） | 見 JSON `inputs` | LOCAL、GT、僅離線評估 |

- 兩份地圖的 `source_sha256` 皆為 `cd46fa03…6e84e`（`school_v3.blend`）。標註與 renderer 路線的座標單位是 Blender 單位，轉換 ×0.0247 後與地圖同座標系（目視疊圖確認）。
- 標註 `geometry.json` **沒有 `AREA_*`**（`area_objects_present: false`），任務所說的 `AREA_*` 比對沒有輸入，標 UNKNOWN；D11 的座椅區改由 C7 的 `furniture` 清單（16 張 `CHAIR`）推得。
- 每個區域取涵蓋率最高的地圖評估（並列取 Office 地圖）；禮堂與 Office 用 Office 地圖，其餘用 Demo 地圖。

```sh
PYTHONPATH=src python scripts/verify_source_map_k7.py \
  --map office=<C7_OFFICE_SOURCE_MAP_20261017.json> --map demo=<C7_DEMO_SOURCE_MAP_20261017.json> \
  --annotation <geometry.json> --route NAME=<trajectory_plan.json> ... \
  --c7-commit 7214ef7 --output docs/engineering/K7_MAP_VERIFICATION_20261017.json \
  --figures-dir docs/engineering/figures/k7
```

所有路徑都是參數；輸出路徑若在任一輸入檔或其所在目錄內會拒絕寫入。實跑約 2.3 分鐘（Demo 地圖的細特徵運算佔多數）。

## 4. 驗證項目

### 4.1 IoU（逐區域）

「身體半徑侵蝕後」為主要比較；「侵蝕前」是來源支撐面扣掉原始障礙物，對標註 `WALK − OBSTACLE`。另列只比 `WALK_*` 多邊形（不含相接障礙物）的 IoU，與舊半徑 IoU。標註獨有／推導獨有區塊只計面積 > 0.25 m² 的區塊（先以 0.05 m 開運算去除細線），完整座標在 JSON 的 `annotation_only_blocks`／`derived_only_blocks`。

| 區域 | 地圖 | 涵蓋率 | IoU 人形 | IoU 僅多邊形 | IoU 侵蝕前 | IoU 舊半徑 | 標註獨有 區塊數／m² | 推導獨有 區塊數／m² |
|---|---|---:|---:|---:|---:|---:|---|---|
| AUDITORIUM（扣除座椅外包絡） | office | 1.00 | 0.942 | 0.942 | 0.997 | 0.959 | 8 / 7.03 | 1 / 2.81 |
| OFFICE | office | 1.00 | **0.253** | 0.877 | 0.276 | 0.243 | 0 / 0 | 2 / **66.37** |
| CLASS101 | demo | 1.00 | 0.844 | 0.844 | 0.944 | 0.885 | 4 / 7.53 | 0 / 0 |
| CLASS102 | demo | 1.00 | 0.852 | 0.852 | 0.945 | 0.889 | 3 / 6.85 | 0 / 0 |
| CLASS103 | demo | 0.010 | — | — | — | — | — | — |
| CORRIDOR_01 | demo | 1.00 | 0.929 | 0.929 | 0.997 | 0.948 | 2 / 2.18 | 6 / 6.17 |
| CORRIDOR_02 | demo | 0.928 | 0.903 | 0.903 | 1.000 | 0.924 | 0 / 0 | 7 / 6.38 |
| CORRIDOR_03 | demo | **0.502** | 0.945 | 0.945 | 1.000 | 0.959 | 0 / 0 | 1 / 0.37 |
| CORRIDOR_04 | demo | 0.362 | 0.883 | 0.883 | 1.000 | 0.923 | 0 / 0 | 2 / 3.83 |
| MAIN_ENTRANCE | demo | 1.00 | **0.576** | 0.662 | 0.609 | 0.514 | 4 / 4.07 | 3 / 3.11 |
| MEETINGROOM | demo | 0.835 | **0.760** | 0.760 | 0.949 | 0.811 | 4 / 12.23 | 1 / 1.16 |
| RESTAURANT_A | demo | 1.00 | 0.803 | 0.825 | 0.880 | 0.836 | 1 / 0.45 | 7 / 3.51 |
| RESTAURANT_B | demo | 1.00 | 0.960 | 0.960 | 0.998 | 0.963 | 0 / 0 | 1 / 0.46 |
| SIDE_ENTRANCE | demo | 1.00 | **0.753** | 0.753 | 0.987 | 0.764 | 3 / 1.39 | 2 / 1.02 |
| STORAGE | demo | 1.00 | **0.707** | 0.707 | 0.929 | 0.784 | 1 / 0.30 | 6 / 4.47 |

BATHROOM、CLASS104 與全部 2F 區域不在 C7 範圍（涵蓋率 0），不比較。

補充：

- **獨立重建**：以標稱半徑 r 對來源支撐面與障礙物各做一次侵蝕／膨脹重建身體中心域，與 C7 地圖的 IoU 為 0.9997–0.9998（面積差 0.08–0.24 m²，來自 C7 以 0.2503 m 保守圓弧緩衝）。表示半徑只套用了一次，沒有雙重侵蝕。
- 標註獨有的區塊多半是座椅（禮堂）、講台（禮堂 `N1 Hamburg` 約 2 m²）與教室桌椅：來源網格有、標註沒有的障礙物。這些在疊圖中是橘色區塊。
- 推導獨有而不在任何 `WALK_*` 內的身體中心可走區：Office 範圍 6 塊共 65.29 m²（絕大部分是上述 OFFICE 障礙物內側），Demo 範圍 15 塊共 166.98 m²。

### 4.2 門口

人形（需寬度 ≥ 0.50 m）：

| 範圍 | 評估的標註門 | 已配對 | 未配對（標註→推導） | 推導未配對（推導→標註） |
|---|---:|---:|---|---:|
| Office 地圖 | 4 | 4（`AUDITORIUM`、`AUDITORIUM_OFFICE`、`OFFICE` 寬 1.750 m；`SIDE_ENTRANCE` 寬 1.556 m） | 無 | 7 |
| Demo 地圖 | 12 | 9 | `MAIN_ENTRANCE`（找到寬 1.750 m 開口，但穿越線一側不在可走區）、`MEETINGROOM_01`、`MEETINGROOM_02`（無開口） | 15 |

- 配對者的推導寬度對標註寬度：1.750 vs 1.778、1.750 vs 1.729、1.750 vs 1.729、1.556 vs 1.482 m 等，彼此一致。
- 推導未配對的開口包括同一道門兩面牆各一個的重複候選、寬 0.78–0.88 m 的窄開口，以及沒有標註的開口（Office 範圍座標與寬度見 JSON `unmatched_derived`）。C7 已說明這些只是幾何開口、不是門標籤。
- 舊半徑地圖的 `SIDE_ENTRANCE`（Office、Demo 兩份）找不到開口，Demo 的 `MAIN_ENTRANCE` 也找不到；人形地圖找得到。舊半徑 run 的身體高度為 2.9393 m，推測門頭等高處幾何被納入障礙切片而吃掉開口，這是推測，未另外驗證。
- 1F 另有 4 個 `PORTAL_*`（`CLASS103`、`CLASS104`、`LADYSROOM`、`MENSROOM`）完全在 Demo ROI 之外，不評估；沒有只部分落在 ROI 內的門。

### 4.3 離線路線（GT，只用於評估）

每個 run 以其實際身體半徑選對應變體（舊 0.1482 m → `legacy_office`、人形 0.25 m → `person`）。

| Run | 地圖／變體 | 取樣點 | 違規 | 最小餘裕（到可走區邊界）m | 區域 |
|---|---|---:|---:|---:|---|
| `office_legacy_20261005`（舊 Office） | office／舊 | 50 | 0 | 0.217 | OFFICE |
| `office_person_20261016`（人形 Office 同路線） | office／人形 | 50 | 0 | 0.115 | OFFICE |
| `auditorium_legacy_20261005`（舊禮堂） | office／舊 | 50 | 0 | 0.255 | AUDITORIUM |
| `auditorium_control_20261016`（禮堂 control） | office／舊 | 50 | 0 | **0.019** | AUDITORIUM |
| `classroom101_legacy_20261005` | demo／舊 | 50 | 0 | 0.111 | CLASS101 |
| `corridor_occlusion_20261005` | demo／舊 | 50 | 0 | 0.102 | CORRIDOR_01 |
| `office_wall_marked_20261005` | — | — | — | — | `EXCLUDED_DIFFERENT_SOURCE_SHA256`（用 `school_v3_wall_marked.blend`，來源不同；路線與舊 Office 相同） |

**0 違規，沒有要回報的違規；D10 沒有觸發，不建議修改地圖。** 禮堂 control 路線貼著椅子外側，離舊半徑可走區邊界只有 1.9 cm，若半徑再多 2 cm 就會違規，意味這條路線對半徑設定很敏感。C6 的 15 條候選路線（未渲染）不在本次範圍，C7 已自行檢查；K7 沒有獨立重算。

### 4.4 比一格（0.25 m）還窄

| 地圖／變體 | 窄於一格的可走片段（≥0.005 m²）個數／細長（≥0.5 m）個數 | 薄於一格的不可走障礙（閉運算填平） | 原始障礙物薄於一格 個數／細長個數 | 零厚度牆線 | 有效緩衝 m／是否 < 0.15 m |
|---|---|---|---|---|---|
| office／人形 | 4 / 0 | 0 | 2 / 2 | 536 條，240.4 m | 0.2503 / 否 |
| office／舊 | 24 / 6 | 0 | 1 / 1 | 468 條，233.8 m | 0.1484 / **是** |
| demo／人形 | 20 / 10 | 0 | 65 / 26 | 1981 條，598.5 m | 0.2503 / 否 |
| demo／舊 | 67 / 26 | 0 | 70 / 29 | 1880 條，589.5 m | 0.1484 / **是** |

- 窄通道（人形、Office 範圍）：兩處寬 0.16–0.18 m、長 0.31–0.40 m（約 (30.3, 51.5) 與 (31.6, 51.5)，兩道內牆之間）；兩處寬 0.056 m 的角落殘片。細長者（Demo）最長 2.17 m、寬 0.119 m（約 (43.2, 14.7)），另有多處寬 0.12–0.14 m、長 0.9–1.4 m。這些通道依 K1 §12.4「窄於一格的通道不保證連通，會偏向 `ENDPOINTS_UNREACHABLE`（UNKNOWN）」，不會造成假 READY。
- 零厚度牆線在身體中心地圖中被膨脹成約 2×0.2503 = 0.50 m 的屏障（> 2 格），所以「牆薄於一格」不會讓 K1 的格點穿牆；但**舊半徑變體的屏障寬 0.2968 m、有效緩衝 0.1484 m < 0.15 m**，落在 §12.4 薄牆尖端的已知限制範圍內。
- 原始障礙物薄於一格的例子：Office 西側兩片厚 0.089 m、長 0.88–0.99 m 的薄牆（約 x = 28.54）；Demo 範圍 65 處，位置見 JSON `raw_obstacle_thinner_than_cell`。
- 每區域計數見 JSON `zones.*.thin_features_in_zone`。

**窄頸與 K1 實際格點的連通性（來自 C7 審查的補充要求）。** 人形 Office 地圖的可走區以 −0.125 m／+0.125 m 緩衝後切成 3 塊：主塊 326.9 m²，另有 2.06 m² 與 0.55 m²；兩處窄頸約在 (31.6, 51.5) 與 (30.3, 51.5)（寬 0.16–0.18 m）。用 `scripts/k7_lattice_connectivity.py` 建構 K1（`origin/claude/k1-hypothesis` @ `7c01522`）的**實際** `_Lattice`（K1 自己的 0.25 m 格點、`edge()` 邊有效性與引擎的 16 種原始移動，不產生假設），結果見 [K7_LATTICE_CONNECTIVITY_20261017.json](K7_LATTICE_CONNECTIVITY_20261017.json)：

| 項目 | 結果 |
|---|---|
| 格點數／原始移動數 | 5213 格（0.25 m）／16 |
| 格點連通塊數 | **1**（5213 格全連通） |
| 主塊（326.9 m²） | 含在唯一連通塊內 |
| 2.06 m² 小塊 | 38 格，與主塊**連通** |
| 0.55 m² 小塊 | 10 格，與主塊**連通** |

結論：兩個窄頸在這份地圖與這組格點對位下**沒有**切斷 K1 格點；窄頸是靠兩格長度的原始移動（線段仍完全落在連續多邊形內）跨過去的。限制：(a) 連通性取決於格點相對窄頸的對位，K1 的格點原點固定在 0.25 m 整數倍，這裡測的就是那個對位，窄頸若平移 0.1 m 結論可能不同；(b) 只測 Office 地圖人形變體，未測 Demo 範圍的 10 個細長窄道與舊半徑變體；(c) 這只是連通性，不等於 K1 假設保守性（K1 §12.4 的限制仍適用）。

### 4.5 D11（座椅區）

| 項目 | 結果 |
|---|---|
| `unknown_regions` 數量 | Office、Demo 兩份地圖、兩個變體皆為 **0**；「座椅區 `walkable: UNKNOWN`」目前**沒有被實作** |
| 被標成 TRUE 的座椅區 | 禮堂 16 張椅子單一群集（單鏈距離 ≤ 1.5 m）的凸包 31.42 m²，包絡 [39.924, 46.96, 43.798, 55.087]；其中 `walkable: TRUE` 面積人形 **9.36 m²**、舊半徑 **11.98 m²**（椅子本身與膨脹區是障礙，排間走道是 TRUE） |
| 建議 | 該凸包另列 `UNKNOWN`（本報告把它從 AUDITORIUM 的 IoU 兩側扣除，凸包座標在 JSON `zones.WALK_1F_AUDITORIUM.seating_hulls`）；Codex 或 K1 在使用前把凸包內設為 `walkable: UNKNOWN` |
| 座椅被當實心障礙 | C7 的座椅（`Theatre Chair` 16 組）與講台（`N1 Hamburg`）是**實心障礙物**，直接從可走區扣掉，而不是 `UNKNOWN`；`unknown_regions` 在兩份地圖、所有變體都是空的。這是照實記錄，**地圖沒有改**，如何處理由使用者決定 |
| 受影響區域與面積（Office 地圖） | 椅子 16 組：原始腳印 13.24 m²，依半徑膨脹後從（侵蝕後的）支撐面扣掉 **26.23 m²**（人形）／21.54 m²（舊半徑）；講台：腳印 0.68 m²，扣掉 **1.68 m²**（人形）／1.23 m²（舊）。全部位於 `WALK_1F_AUDITORIUM`（椅子 x 39.92–43.80、y 46.96–55.09；講台 x 46.92–48.05、y 54.05–55.15）。椅子外包絡 31.42 m² 內：被扣掉（不可走）22.06 m²（人形）、TRUE 9.36 m² |
| 教室、餐廳 | C7 的 `furniture` 只有禮堂 16 張椅子與講台，教室桌椅與餐廳座位只在障礙物清單裡、沒有語義標籤（也沒有 `AREA_*`），**無法判定座椅區 → UNKNOWN**。需要 C7 補標籤，或由人決定 |

## 5. 疊圖

每個有地圖涵蓋的區域一張（`WALK_1F_*.png`，15 張）：灰＝來源支撐面；綠＝推導身體中心可走區；虛線藍＝`WALK_*`；紅斜線＝`OBSTACLE_*` 標註；橘／粉＝標註獨有／推導獨有區塊（> 0.25 m²）；黃＝窄於一格的特徵；紫點線＝座椅外包絡；青＝`PORTAL_*` 標註框；黑線＝推導開口穿越線；藍點劃線＝路線，紅 ✕＝違規點（本次沒有）。

[AUDITORIUM](figures/k7/WALK_1F_AUDITORIUM.png)、[OFFICE](figures/k7/WALK_1F_OFFICE.png)、[CLASS101](figures/k7/WALK_1F_CLASS101.png)、[CLASS102](figures/k7/WALK_1F_CLASS102.png)、[CLASS103](figures/k7/WALK_1F_CLASS103.png)、[CORRIDOR_01](figures/k7/WALK_1F_CORRIDOR_01.png)、[CORRIDOR_02](figures/k7/WALK_1F_CORRIDOR_02.png)、[CORRIDOR_03](figures/k7/WALK_1F_CORRIDOR_03.png)、[CORRIDOR_04](figures/k7/WALK_1F_CORRIDOR_04.png)、[MAIN_ENTRANCE](figures/k7/WALK_1F_MAIN_ENTRANCE.png)、[MEETINGROOM](figures/k7/WALK_1F_MEETINGROOM.png)、[RESTAURANT_A](figures/k7/WALK_1F_RESTAURANT_A.png)、[RESTAURANT_B](figures/k7/WALK_1F_RESTAURANT_B.png)、[SIDE_ENTRANCE](figures/k7/WALK_1F_SIDE_ENTRANCE.png)、[STORAGE](figures/k7/WALK_1F_STORAGE.png)。BATHROOM、CLASS104 與 2F 區域沒有地圖資料，無圖。

## 6. 各區域等級建議

| 區域 | 等級 | 判定理由 |
|---|---|---|
| AUDITORIUM | `SOURCE_DERIVED_VERIFIED` | IoU 0.942；2/2 門口配對；2 條路線 0 違規。**座椅外包絡 31.4 m² 另列 `UNKNOWN`（D11）** |
| OFFICE | `UNKNOWN` | IoU 0.253（< 0.80）：標註 `OBSTACLE_1F_OFFICE_01/02` 範圍內來源網格有 64.4 m² 可走區；門口 2/2 配對、2 條路線 0 違規。窄頸經 K1 實際格點驗證為連通，**不是**降級理由；等級只取決於標註與來源在障礙物範圍上的分歧（§7 第 1 點） |
| CLASS101 | `SOURCE_DERIVED_VERIFIED` | IoU 0.844；1/1 門口；1 條路線 0 違規 |
| CLASS102 | `SOURCE_DERIVED_VERIFIED` | IoU 0.852；1/1 門口；無路線（`route check: N/A`） |
| CORRIDOR_03 | `SOURCE_DERIVED_VERIFIED` | IoU 0.945；2/2 門口；無路線。**涵蓋率只有 0.502，剛過門檻**，只評估被涵蓋的一半 |
| RESTAURANT_A | `SOURCE_DERIVED_VERIFIED` | IoU 0.803（剛過門檻）；2/2 門口；無路線 |
| RESTAURANT_B | `SOURCE_DERIVED_VERIFIED` | IoU 0.960；1/1 門口；無路線 |
| CORRIDOR_01 | `UNKNOWN` | IoU 0.929 過；但相鄰的 `MAIN_ENTRANCE`（穿越線一側不可走）、`MEETINGROOM_01`（無開口）未配對；路線 0 違規 |
| CORRIDOR_02 | `UNKNOWN` | IoU 0.903 過；`MEETINGROOM_01` 無開口 |
| MAIN_ENTRANCE | `UNKNOWN` | IoU 0.576（< 0.80）；門口未配對 |
| MEETINGROOM | `UNKNOWN` | IoU 0.760（< 0.80）；`MEETINGROOM_01/02` 皆無開口 |
| SIDE_ENTRANCE | `UNKNOWN` | IoU 0.753（< 0.80）；門口 1/1 配對 |
| STORAGE | `UNKNOWN` | IoU 0.707（< 0.80）；門口 1/1 配對 |
| CLASS103 | `ANNOTATION_ONLY` | 涵蓋率 0.010 |
| CORRIDOR_04 | `ANNOTATION_ONLY` | 涵蓋率 0.362（被涵蓋部分 IoU 0.883，但不足一半） |
| BATHROOM、CLASS104 | `ANNOTATION_ONLY` | 不在 C7 範圍 |
| 2F 全部（BATHROOM、CLASS201–204、CORRIDOR_01–04、GALLERY、MEETINGROOM、OFFICE） | `ANNOTATION_ONLY`（未逐項評估） | C7 只涵蓋 1F |

等級只回答「來源推導地圖與人工標註、離線路線是否互相支持」，不是真實建築通行性認證（`physical_navigation` 維持 `NOT_CERTIFIED`）。

## 7. 偏離、限制與 UNKNOWN

1. **比較範圍在第一次部分執行後調整（偏離「判定前固定」）。** 第一次只在 Office 地圖上試跑時，比較範圍只含 `WALK_*` 多邊形，OFFICE 的 IoU 是 0.877（會判 VERIFIED）。看到「推導但不在任何 `WALK_*` 內的可走區」有 65 m² 之後，我把範圍改為「`WALK_*` 加上相接的 `OBSTACLE_*`」，因為 `WALK_*` 多邊形本身已挖掉障礙物，只比多邊形會藏起一個關於整個房間的分歧。門檻（0.80、0.50、0.5 m 等）沒有改，兩個 IoU 都留在 JSON（`iou_eroded` 與 `iou_eroded_zone_polygon_only`）。這個調整影響 OFFICE（0.877→0.253）、MAIN_ENTRANCE（0.662→0.576）、RESTAURANT_A（0.825→0.803），其餘區域不變。若人決定「障礙物標註只是粗略示意、不算比較對象」，OFFICE 會是 0.877，其他條件都過，等級會變成 `SOURCE_DERIVED_VERIFIED`。**這一點需要人在 CP2 判斷。**
2. OFFICE 的分歧是「標註 vs 來源」，K7 不判斷誰對：疊圖顯示標註障礙物內側有薄牆圍成的內室，來源網格在內室內沒有身體高度的障礙物，所以可走區延伸進去。這些內室是否真的可進入、與外部是否連通，K7 沒有驗證。K7 另行驗算：人形可走區與 `OBSTACLE_1F_OFFICE_01` 多邊形重疊 30.27 m²，與 C7 報告的 30.274 m² 一致；`OBSTACLE_1F_OFFICE_02` 另有 34.29 m²，兩塊合計 64.37 m²。
3. 門口比對只能判斷「幾何開口與標註框一致」，不驗證語義上的門；C7 的門口產生器只認軸向對齊的低牆缺口，非軸向的門不會被找到（這可能是 `MEETINGROOM_01/02` 無開口的原因，未驗證）。
4. 標註 `geometry.json` 無 `AREA_*`，所以區域名稱用 `WALK_*`；`THRESHOLD` 條帶（11 個）不單獨評分，併入相鄰區域的 IoU 範圍。
5. 路線只檢查取樣點（50 個，間距 ≈ 8–12 cm），沒有檢查點與點之間的連線。
6. 無路線的區域（CLASS102、CORRIDOR_03、RESTAURANT_A/B 等）路線檢查是 N/A，不阻擋 VERIFIED，但表示沒有 GT 路線佐證。
7. 區域涵蓋率以 ROI（相機鄰域）計；ROI 邊界不是牆，所以 IoU 兩側都裁掉 ROI 內縮 r 的邊帶。
8. 來源路線的 `office_wall_marked_20261005` 因 `.blend` 不同而排除；C6 的 15 條候選路線未重算。
9. 本工具沒有跑 Blender、沒有渲染、沒有推論；GT 數值沒有進入 repo。

## 8. 檔案

- `src/amidst/evaluation/map_verification.py`：純函式（載入、IoU、區塊、門口配對、路線、細特徵、座椅、等級、輸出路徑防護）。
- `scripts/verify_source_map_k7.py`：CLI 與疊圖。
- `scripts/k7_lattice_connectivity.py`：用 K1 實際 `_Lattice` 測格點連通性（需 `--k1-src` 指向 K1 匯出）；輸出 `K7_LATTICE_CONNECTIVITY_20261017.json`。
- `tests/unit/test_map_verification.py`：合成地圖與合成標註，12 項測試。
- `docs/engineering/K7_MAP_VERIFICATION_20261017.{md,json}`、`docs/engineering/figures/k7/*.png`。

## 9. 使用者決定（CP2，2026-10-17）

以下是使用者在 CP2 對本報告發現所做的決定。§1–§8 的原結論、數字與 §7 的偏離說明維持不變，這一節只追加；原本的等級保留在 JSON 的 `grade` 欄位，決定後的等級另記在 `grade_after_user_decision`。

- **D15（Office 禁止區）**：Office 西側 `OBSTACLE_1F_OFFICE_01/02` 範圍（人形可走區 64.4 m²）經使用者確認是**禁止區域**，標註正確。問題在於目前的標註把「禁止區」和「實體障礙物」混在同一類。禁止區改為獨立的**政策圖層**：K1 允許路徑經過，但要標示「進入禁止區」。Office 的實體幾何改以只比 `WALK_*` 多邊形的結果判定（IoU 0.877），西側另加禁止區政策圖層。使用者接受 §7 第 1 點揭露的比較範圍偏離。
- **D16（修訂 D11）**：來源網格能解析的座椅與講台是**實體障礙物**，走道可走；只有**無法解析**的座位區才標 `UNKNOWN`。

### 更新後的等級

| 區域 | 原等級 | 決定後 | 說明 |
|---|---|---|---|
| OFFICE | `UNKNOWN` | **`SOURCE_DERIVED_VERIFIED`（實體幾何）＋ 西側禁止區政策圖層** | IoU 0.877（僅 `WALK_*` 多邊形）；門口 2/2、2 條路線 0 違規；禁止區 `OBSTACLE_1F_OFFICE_01/02` 不再算實體障礙物分歧，改由政策圖層表達 |

其餘區域的等級不變。

### 對本報告其他段落的影響（K7 依決定推得，未改動地圖）

- 禮堂的 16 張椅子與講台是來源網格已解析的實體障礙物，依 D16 走道可走，所以 §4.5 與 §6 把座椅外包絡 31.4 m² 另列 `UNKNOWN` 的建議**不再需要**；`WALK_1F_AUDITORIUM` 維持 `SOURCE_DERIVED_VERIFIED`，不附 `UNKNOWN` 子區。§4.5 的面積記錄（椅子扣掉 26.23 m²、講台 1.68 m²）仍是事實紀錄。
- 教室與餐廳的座位 C7 沒有語義標籤（§4.5），K7 無法判斷它們是否屬於「能解析的實體障礙」；依 D16 這些座位區是否標 `UNKNOWN` 尚未定案，仍列為未決。
- 禁止區政策圖層本身（格式、K1 如何標示「進入禁止區」）不在 K7 範圍；K7 沒有修改任何地圖，也沒有重算 IoU 或重畫疊圖。
