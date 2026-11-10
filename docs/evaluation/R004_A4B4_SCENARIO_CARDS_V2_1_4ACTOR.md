# r004 A4／B4 情境卡 v2.1（4 人版，D207 修訂）

日期：2026-11-10｜起草：Claude（評估端）｜Model / effort：Claude Opus 5.5 / high

## 狀態

**PROPOSED，不授權渲染。**本版取代 [v2 卡](R004_A4B4_SCENARIO_CARDS_V2_4ACTOR.md)（#519，merge `d7391d83`）的路線、門洞和顏色假設；v2 卡的外觀設計、計分事件、DP1 方法和 S2 搭配（v2 §2、§6）不變，本文只寫改了什麼和為什麼。起因是 Codex 在 [#516](https://github.com/Polalalabear/amidst/issues/516#issuecomment-6761965932) 的不渲染可行性檢查 FAIL；修訂規則照 D207：

- 干擾者停留到錄影結束，算離場；片中消失時，必須已經不在任何渲染鏡頭內；
- 出生點必須在所有渲染鏡頭外，或在 t=0 就已在場並寫明；
- T 的路線可以為了淨距微調，但要保持 v1 的事件序列（鏡頭交接順序、LOST／RETURN 時刻）。

交付的檔案：

| 檔案 | 內容 |
| --- | --- |
| [`R004_SCENE_GEOMETRY_2D_V1.json`](R004_SCENE_GEOMETRY_2D_V1.json) | r004 實測 2D 幾何：260 條淨距線段、62 段全高遮擋牆、門洞、地板高度、8 台相機的矩陣與內參 |
| [`scripts/design/build_r004_scene_geometry_2d.py`](../../scripts/design/build_r004_scene_geometry_2d.py) | 從 Codex 的 LOCAL 匯出重建上面那份 JSON |
| [`R004_A4B4_SCENARIO_V2_1_4ACTOR_DRAFT.json`](R004_A4B4_SCENARIO_V2_1_4ACTOR_DRAFT.json) | v2.1 劇本草稿（run ID 不變：`A4-1-v2-4actor`、`B4-1-v2-4actor`） |
| [`R004_A4B4_SCENARIO_V2_1_4ACTOR_CLEARANCE_REPORT.json`](R004_A4B4_SCENARIO_V2_1_4ACTOR_CLEARANCE_REPORT.json) | 檢查器報告（PASS） |
| [`R004_A4B4_SCENARIO_V2_1_4ACTOR_DP1_ESTIMATE.json`](R004_A4B4_SCENARIO_V2_1_4ACTOR_DP1_ESTIMATE.json) | 歧義段數估計 |
| [`scripts/design/check_actor_clearance.py`](../../scripts/design/check_actor_clearance.py)、[`tests/evaluation/test_actor_clearance.py`](../../tests/evaluation/test_actor_clearance.py) | 檢查器（解析牆距＋出入點可見性）與 28 個測試 |

v2 的草稿和報告保留不動（walls 仍是 null，檢查器仍判 UNKNOWN），因為 [#520](https://github.com/Polalalabear/amidst/pull/520) 的關卡測試目前指向 v2 草稿。

## 0. 摘要

| 項目 | A4-1 v2.1 | B4-1 v2.1 |
| --- | --- | --- |
| 檢查器結論 | **PASS**（7 項全部 PASS） | **PASS**（7 項全部 PASS） |
| 最小牆／障礙淨距 | **0.450 m**（四人都 ≥ 0.45；v2 是 T 0.30、A 0、B 0） | **0.4507 m**（T，經過轉角屏風；v2 是 T 0.197、A 0、B 0.199） |
| 出入點 | 3 個出生點、1 個片中消失點全部在所有 A4 鏡頭外；其餘停留到 50 s | 3 個出生點全部在所有 B4 鏡頭外；全部停留到 42 s |
| 最近的一對 | T–A、T–B、A–B 0.85 m | T–A 0.676 m（16.54 s，A 經過站在轉角的 T） |
| 歧義情境段（B 在紅色內，D204） | 3 段（與 v2 相同） | 2 段（與 v2 相同） |
| 合計 | **5 段 ≥ 5**；B 出帶的敏感度情況 3 段 | |

## 1. Codex #516 的發現和本版的處理

| Codex 的發現 | 本版處理 |
| --- | --- |
| 西入口實寬 1.40 m（jamb y = ±0.70），T 在 y = −0.4 穿越，淨距 0.30 m | T 的門口路點改成 y = −0.25（時刻不變），淨距 0.45 m；門洞寬改 1.4 m |
| R101 門中心在 (8.00, 0)，不是 7.75 | 門的中心改 x = 8.0；T（B4）和 C 都從 x = 8.0 穿越，離門框 0.60 m |
| A4 的 A／B、B4 的 A／B 碰到角落屏風（x 14.50–14.65、y 1.60–2.40） | 北道（y = 1.95）在 x ≈ 13 降到 y = 1.1 再經過屏風，離屏風 ≥ 0.45 m。B 不再在屏風上出生 |
| B4 的 T 碰到西側屏風 OBSTACLE_SCREEN_W（x 10.40–10.55、y 0–0.80），0.197 m | T 在 x 8–11.4 走 y 1.25–1.30，回程加一個路點 (10.0, 1.3) @25.0 s；轉角一段改走 y = 1.1。淨距 ≥ 0.45 m |
| C 剛好 0.35 m（R101 門框） | 改從門中心 x = 8.0 穿越，A4 0.45 m（北道）、B4 0.60 m |
| 多個出生點／離場點在鏡頭內；A4 的 B 在 30 s 消失時還在畫面裡 | 出生點全部移到鏡頭外（§3）；A4 的 B 改成走到 CAM_EXT_CLEAR 後方 (−13.6, 6.4) 才在 32.2 s 消失 |
| 實際 HSV 是 `D131-DEMO-HSV-v1`（crop 0.50、V ≥ 0.20、red [0.95, 0.05]、blue [0.50, 0.72]） | 草稿加上 `hsv_config`，全部說明改用實際參數；B 的色相改 0.012（§4） |
| 檢查器的牆距只做 20 ms 採樣 | 改成每段路線對每條線段的解析最短距離（§2） |

## 2. 幾何資料和檢查器的修改

**幾何 JSON（`R004_SCENE_GEOMETRY_2D_V1.json`）。**全部取自 Codex 的 LOCAL 證據，已從 `/tmp/codex-516-feasibility/` 複製到 `local/evidence/codex-516-feasibility-20261110/`（gitignore），用 `ARTIFACT_MANIFEST.json`（SHA-256 `fcf478fe…0b46`）核對 28/28 個檔案。provenance：

- `.blend` SHA-256 `466e6fbe…809b`（未開啟、未讀取；hash 取自 Codex 的匯出）
- 相機 catalog `safe_static/cameras.json` SHA-256 `3eba8572…899f`
- Codex `scene_export.json` `c4788666…45ac`、`geometry_2d.json` `fb4e0103…9dc0`

| 欄位 | 內容 |
| --- | --- |
| `clearance_segments` | Codex 的 260 條 XY 截面線段（WALL_JOINED_SHELL 152、5 個屏風 20、車體／車窗／車輪 88），人體高度帶 0–1.7 m，原樣收錄 |
| `occluders_full_height` | 62 段在 z = 0.25、1.45、2.65、3.05 m（牆殼每個拓樸區間各一個高度）都實心的 XY 牆段。所有相機都在 z ≤ 3.0 m、人體頂端 1.85 m，所以 2D 視線穿過其中一段，3D 視線就一定被擋。門洞、門楣、x = 15 的矮牆（0.5 m 以上是窗）和車都不算遮擋物 |
| `cameras` | 8 台相機的 `camera_to_world`、fx／fy／cx／cy、解析度、clip（catalog 原值） |
| `render_camera_sets` | A4：EXT_CAR、EXT_CLEAR、ENTRY、W1；B4：W1、W2、BRANCH、R101_IN、WIDE。ENTRY 雖然只供查找，仍會渲染，所以算進出入點檢查 |

**檢查器（`check_actor_clearance.py`）新增與修改：**

1. **牆距改成解析計算。**人在兩個路點之間是等速直線，所以每段路線對每條線段算精確的「線段對線段」最短距離，並回報發生的時刻和位置。`walls: "FROM_GEOMETRY"` 會讀幾何 JSON 的 260 條線段。用 v2 原路線重算，結果和 Codex 的解析補查逐項相同（T 0.30、A 0、B 0、C 0.35；B4 T 0.1971、A 0、B 0.199、C 0.35），已寫成測試。
2. **新增 `spawn_exit`（D207）。**每個人的第一個和最後一個在場點，加上在場那一側最近的渲染格（5 fps），對該 run 的每台渲染鏡頭判斷。人體用半徑 0.35 m、高 1.85 m 的八角柱，腳底高度取地板（室外 −0.06 m）：
   - `OUT_OF_FRUSTUM`：一個視錐平面就把整個柱體排除在外；
   - `WALL_OCCLUDED`：一段全高遮擋牆在 XY 上把相機和整個腳印隔開；
   - `IN_VIEW`（FAIL）：有一個角點在視錐內，且視線上沒有任何全高遮擋牆；
   - 其他情況 `UNKNOWN`。
   其他演員和矮的物體（車、門楣）都不當遮擋物，所以這個檢查只會偏向 FAIL／UNKNOWN，不會誤判 PASS。t = 0 就在場的人要有 `present_at_t0_note`（只有 T）；最後一點等於 `duration_us` 算「停留到錄影結束」。
   - **與任務說明的差異：**任務說「不算遮擋」。純視錐（不算任何遮擋）時，A4／B4 幾乎所有室內位置都在某台鏡頭的視錐內，例如 W1 的視錐穿過牆看進 R101，沒有一個出生點能 PASS。所以加了上面這種只用全高靜態牆、只會更保守的 2D 遮擋；仍然不用任何網格射線或演員遮擋。
3. 文件可在頂層寫 `geometry_ref`（相對 repo 根目錄）；`check_document(doc, geometry=None, base_dir=None)` 也可以直接傳幾何。沒有幾何或沒有寫 `render_camera_ids` 時，`spawn_exit` 是 UNKNOWN；明確寫空清單（不渲染）時是 PASS。

## 3. v2.1 路線

座標見草稿 JSON。走廊分道不變：T 走 y ≈ 1.1，反向或超越的人走北道 y = 1.95（離北牆 0.45 m）。北道在 x ≈ 13 降到 y = 1.1，經過角落屏風後再進 CORNER。

### 3.1 A4-1（50 s）

| 人 | v2.1 路線 | 出入點判斷 |
| --- | --- | --- |
| T | v1 路線；只有西入口的路點 1–3、8–13 由 y = −0.4 改 y = −0.25，時刻全部不變 | t = 0 在場（seed，已寫明）；停留到 50 s |
| A（同色） | 2.0 s 在 CAM_EXT_CLEAR 後方 (−12.75, 6.0) 出現，斜穿室外進入 EXT 畫面，10.65 s 在 y = 0.15 過西入口（T 之後 2.5 s），13.5 s 進 W1；17–18 s 換北道，22.9 s 起降到 y = 1.1 經過屏風，25.4–32.6 s 在 CORNER (15.8, 1.5) 等；35.0–43.5 s 沿北道往西走過 W1（c2 時在畫面裡），47.4 s 出西入口，50 s 時在室外 (−6.2, 2.1) | 出生：EXT_CAR／EXT_CLEAR／W1 在視錐外，ENTRY 被西牆擋。停留到 50 s |
| B（相近色） | 2.0 s 在 CORNER (16.0, 1.0) 出現，等到 5.6 s，經過屏風後 8.1–16.9 s 沿北道往西走過 W1；約 14.24 s 與往東的 T 錯身（橫向 0.85 m）；20.5 s 出西入口，24.0–26.8 s 在 (−7, 3) 講電話，之後走到 CAM_EXT_CLEAR 後方，**32.2 s 在 (−13.6, 6.4) 消失** | 出生：EXT_CAR／EXT_CLEAR／W1 被牆擋，ENTRY 在視錐外。消失：32.2 s 和 32.2 s 那一格都在所有 A4 鏡頭外 |
| C（對照） | 4.0 s 在 R101 (9, −3) 出現並等到 17.5 s，19.95 s 從 R101 門中心 (x 8.0) 出來，22.0–24.2 s 沿北道往東，27.7 s 起站在 CORNER (16.8, 0.7) 到結束 | 出生：被牆擋或在視錐外。停留到 50 s |

**西入口順序（實寬 1.4 m，仍維持一次一人）：**T 8.16 → A 10.65 → B 20.53 → T 28.84／36.16 → A 47.43 s，任兩次相差 ≥ 2.49 s。**R101 門：**C 19.95 s。

### 3.2 B4-1（42 s）

| 人 | v2.1 路線 | 出入點判斷 |
| --- | --- | --- |
| T | v1 路線，時刻不變；淨距微調：(8, 1)→(8, 1.25)、(11.4, 1.15)→(11.4, 1.3)、(15.5, 1.4)→(15.5, 1.1)、(15, 1.4)→(15, 1.1)、門口 x 7.75→8.0；回程在 25.0 s 加一個路點 (10.0, 1.3)。最大位移 0.30 m | t = 0 在場（seed，已寫明）；停留到 42 s |
| A（同色） | 2.0 s 在門廳東南角、OBSTACLE_SCREEN_W_HOOD 後方 (2.0, −1.35) 出現，5.6 s 進北道，13.9 s 到 (13, 1.95)，經過屏風後 15.8 s 進 CORNER（T 的 t_N = 14 s 之後約 1.8 s），離站著的 T ≥ 0.676 m；19.6 s 起停在 CORR_N (16.4, 6.0) 的公告屏風旁到結束 | 出生：W1 被 W_HOOD 屏風擋，W2／R101_IN／WIDE 被牆擋，BRANCH 在視錐外。停留到 42 s |
| B（相近色） | 18.0 s 在同一個門廳角落出現，沿北道往東；約 25.9 s 與往西的 T 錯身，錯身點 T 已回到 y < 1.0（橫向 0.888 m）；經過屏風後 31.6 s 起站在 CORNER (16.4, 0.8) 到結束 | 出生：同 A。停留到 42 s |
| C（對照） | 3.0 s 在 R101 西南角 (6.0, −4.3) 出現，6.4 s 從 R101 門中心出來（T 在 4 s 前後經過門口，沒有進門），沿南道 y = 1.0 往西，7.75 s 與北道的 A 錯身（0.95 m），14.5 s 起在門廳邊 (−0.75, 0.4) 等到結束 | 出生：R101_IN 在視錐外（在相機後方），其他被牆擋。停留到 42 s |

**R101 門順序：**C 6.40 → T 31.90 s。

B 的出生時刻由 16.0 s 改 18.0 s，讓它和 T 的錯身點落在 T 已回到 y < 1.0 的地方（T 在西側屏風旁走 y = 1.3，和北道只差 0.65 m，會違反 0.8 m 錯身規則）。

## 4. 顏色：改用實際的 D131-DEMO-HSV-v1

| 參數 | v2 卡的假設 | 實際（`D131-DEMO-HSV-v1`，canonical content SHA-256 `2af90afc…0368`） |
| --- | --- | --- |
| 紅色帶 | [0.95, 0.05] | [0.95, 0.05]（跨 0） |
| 藍色帶 | [0.50, 0.75] | **[0.50, 0.72]** |
| 上方裁切 `crop_ratio` | 0.30 | **0.50** |
| `saturation_min`／`value_min` | 0.2／0.15 | 0.2／**0.20** |
| 其他 | — | min_pixels 64、STRONG ≥ 0.60、WEAK ≥ 0.30、18 bins、truncation ≤ 0.20 |

這組設定是 `DEMO_DEFAULT`（`formal_parameters=false`、`human_approval_verified=false`），不是正式研究核准的參數。

- **A：**同一個紅色材質；裁切改成上方 50% 後，淺灰褲子仍在裁切外。T 的深色背包在背面視角可能進到上方 50%，會降低 T 的紅色比例（Codex 實測既有 T 觀測大多 STRONG，少數 WEAK／UNKNOWN）。
- **B：材質色相由 0.02 改 0.012**（S 0.75、V 0.65，線性 RGB 0.65／0.1976／0.1625）。Codex 對色相 0.02 的 proxy 是 0.0158–0.0291（離上界 0.05 只剩 0.0209）。把同一個 proxy 偏移套到 0.012，得到 0.0078–0.0211，離上界 **0.029**；改用既有 T 紅衣「材質到像素中位數」的最大偏移 +0.0152 估計，得到 0.0272，離上界 **0.0228**。兩種估計都 ≥ 0.02，離下界（0.95）都 > 0.06。**這只是估計**：proxy 沒有 AgX、BRDF、間接光、陰影、裁切和多人遮擋，B 在各鏡頭的實際色相和 ≥ 0.02 的餘裕，要在渲染後由 G2 逐鏡頭實測確認；Codex 重跑可行性時也請用 0.012 直接重算 proxy。色相 0.012 和 T 渲染後的 0.011–0.017 很接近，B 會比 v2 更難靠顏色區分，這符合「相近色干擾」的用意。
- **C：**色相 0.62（線性 RGB 0.1625／0.299／0.65），離藍色帶兩邊 0.10／0.12。

## 5. 檢查器報告

指令：`python3 scripts/design/check_actor_clearance.py docs/evaluation/R004_A4B4_SCENARIO_V2_1_4ACTOR_DRAFT.json --out docs/evaluation/R004_A4B4_SCENARIO_V2_1_4ACTOR_CLEARANCE_REPORT.json`，exit 0（PASS）。

| 檢查 | A4-1 v2.1 | B4-1 v2.1 |
| --- | --- | --- |
| 兩兩距離（≥ 0.6 m） | PASS。T–A 0.85 @19.214 s、T–B 0.85 @14.237 s、A–B 0.85 @15.545 s、A–C 0.80 @26.95 s、T–C 1.271、B–C 4.95 m | PASS。T–A **0.676** @16.539 s、A–C 0.95 @7.754 s、T–B 0.983 @25.901 s、T–C 2.601、B–C 3.260、A–B 5.129 m |
| 走廊錯身（≥ 0.8 m） | PASS。T–A、T–B、A–B 0.85 m | PASS。T–B 0.888、A–C 0.95 m |
| 門口（一次一人、錯開 ≥ 1.5 s） | PASS（§3.1） | PASS（§3.2） |
| 牆／障礙（≥ 0.35 m，解析） | PASS。T 0.450（西入口門框）、A 0.450、B 0.450、C 0.450 m（北道） | PASS。T **0.4507**（角落屏風）、A 0.450、B 0.450、C 0.600 m |
| 出入點（D207） | PASS（3 個出生、1 個片中消失；T t = 0 已寫明） | PASS（3 個出生） |
| seed 互斥（其他人 ≥ 2.0 s） | PASS | PASS |
| 速度（≤ 1.6 m/s） | PASS（最大 1.546 m/s，A 走向西入口） | PASS（最大 1.50 m/s） |
| **結論** | **PASS** | **PASS** |

物理導航和人體網格碰撞仍然 **UNKNOWN**；檢查的是中心線對截面線段的距離。

## 6. 歧義段數

指令：`python scripts/design/estimate_plan_decision_points.py . docs/evaluation/R004_A4B4_SCENARIO_V2_1_4ACTOR_DRAFT.json --variant in_band|out_of_band`。`estimate_model` 的地板框沒改（是規劃假設，不是可見性；出入點可見性改由檢查器的 `spawn_exit` 判斷）。

| run | B 在紅色內（D204） | B 出帶（敏感度） |
| --- | --- | --- |
| A4-1 | 3 段：8.0–10.4 s（A、B）、17.8–25.8 s（A、B、T）、29.0–36.0 s（A、T）；DP1 94 個時間點 | 1 段 |
| B4-1 | 2 段：11.2–12.6 s（A、T）、14.4–41.8 s（A、B、T）；DP1 147 個時間點 | 2 段 |
| **合計** | **5 段 ≥ 5**，全部含干擾者 | 3 段 |

和 v2 一樣剛好 5 段，沒有餘裕；B 在某支鏡頭出帶時會掉到 3 段。

## 7. 未驗證和待辦

- **沒有渲染、沒有開 Blender**（Claude 端不渲染）。出入點的可見性是純幾何：沒有網格射線、沒有演員互相遮擋。A 和 B（B4）的出生點靠 W_HOOD 屏風（寬 0.77 m、厚 5 cm）擋住 W1，餘裕不大，請 Codex 用網格 BVH 確認。
- B 的色相餘裕是估計（§4），要 G2 實測。
- 門洞 `portal-openings:r004:v2` 的獨立 JSON 仍然 UNKNOWN；門洞資料取自 Codex 的實際牆殼截面。
- [#520](https://github.com/Polalalabear/amidst/pull/520) 的關卡目前指向 v2 草稿，契約裡寫 `crop_ratio` = 0.3、A4 渲染鏡頭沒有列 CAM_ENTRY；要改成指向 v2.1 草稿、crop 0.5、並決定 ENTRY 是否算渲染鏡頭。這是 #520 那邊的檔案，本 PR 沒動。
- 渲染、索引、打包需要使用者另外授權；Codex 估計渲染 22–45 分鐘、1.1–1.7 GiB，磁碟門檻要先滿足。
