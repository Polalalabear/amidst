# 受控場景契約 v1.1 草案（`OFFICE_CONTROLLED_SCENE_V1`）

狀態：
- **v1 已核准：**使用者以 D32（[#66](https://github.com/Polalalabear/amidst/issues/66)）核准 #65 @ `264377112d1859c5472a9a47dcb56c9b4b38e19e`。v1 中標「CS-A 待核准的介面設計」的項目，已隨 D32 一併核准；為保留可追溯性，原標示不逐一改寫。
- **v1.1 是草案：**本版加入 D44「接地區間的組成條件」，並在 §0.2 記錄 D32、D36–D42、D44。新增內容標 **v1.1 草案**，等 Codex 確認；確認前不得當成已核准契約實作。
- **B 包授權：**B 包的 `.blend` 與 preview 渲染，仍要等使用者在 [#68](https://github.com/Polalalabear/amidst/issues/68) 另行授權。
- **估計器：**v1.1 只定介面與行為，估計器的實作屬於 Codex（C4a 新版）。

- 本文標示規則：
  - 「待約定」：數值門檻，本文不定。
  - 「CS-A 待核准的介面設計」：Codex 已提出、等使用者核准的設計。
  - `UNKNOWN`：沒有依據。
- 本文所有新增欄位與端點**都還沒有實作**。

| 版本 | Commit | 內容 |
| --- | --- | --- |
| 1 | `6cb2183` | 初稿 |
| 2 | `9848d5e` | 使用者決定（5 fps）、§2.1 內插規則、對齊 Codex 準備文件 |
| 3 | `11820c0` | 依 Codex CS-A 審查修訂；記錄 D26–D28 |
| 4 | `2643771` | **已由 D32 核准（CS-A）**。依 Codex 對 `11820c0` 的複核（[留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6246035412)）R3：§6.1 範例改為 `PARTIAL`，新增整體 readiness 狀態的定義。R1、R2 只改回覆與 UX 草圖 |
| v1.1 草案 | `36b7781` | D47 影像驗收改成模型先篩（§0.2、§7、§8.1）；D45 不確定度標示（§2.4、§6.3、§6.4、§8）；D46 不做 GT 對照圖層（§7）；§0.2 記錄 D43、D45、D46。D44 接地區間的組成條件：§3.12 新增軌跡身高、§6.3 新增 `composed_ground`、§7 列出三種條件可讀的資料、§9 新增 CS-Q15；§0.2 記錄 D32、D36–D42、D44 |
| v1.1 草案（續） | `9b9b5a7` | 依 CS-B 複核，把殘留的「逐格／逐 sample 人工核對」寫法統一成 D47 的 §8.1 流程（§0.2 D26 列、§5.1、§5.2、§7、§8.1）；未經人工檢查的格標 `MODEL_SCREENED_NOT_HUMAN_REVIEWED`；§0.2 記錄 D48、D49 |
| v1.1 草案（續 2） | `0e51c53` | 依 #75 審查 L4，區分「已 pin 的影格檔案不存在」（完整性錯誤）與「列在 `rgb_index.missing[]` 的預期缺格」（`MISSING`）；修改 §2.2、§2.3、§3.11、§5.2、§6.2、§8 |
| v1.1 草案（續 3） | 本版 | 依門檻提案 #76 @ `6f862e6` §2.3 的 C1–C5 同步已定案的決定：同步容差（D41）、B1 錯開（D37）、`BLIND_CORNER` 西界 13.7、鏡頭與磁碟條文標「已由設計稿 #54 @ `f2afa3f` 取代」、投影比較基準（D54 A2）；§8.1 寫入 D54 A1–A4；§0.2 記錄 D50–D54 |

## 0. 依據與使用者決定

### 0.1 依據（固定版本）

| 來源 | 版本 |
| --- | --- |
| Codex 提案 | `docs/agents/CONTROLLED_SCENE_2D_TO_3D_PROPOSAL_20261018.md` @ `59b8f5d91fe35812dfe0046c67709a519b46ed1e`（分支 `codex/office-demo-rehearsal-docs`），SHA-256 `80013790cda63af6cfd14c395989a2e137a7b50b3d7675bda7a702025744b88f` |
| Codex 準備文件 | `docs/engineering/CONTROLLED_DEMO_PREPARATION_20261018.md` @ `14a3ffbd1ed6fbef5952b3402fe46daf14be22fb` |
| Codex CS-A 審查 | [#65 留言](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6245504825)（審查對象 #65 @ `9848d5e`）。以留言全文為準；Codex 本機的 commit `f50fc37` 沒有推送，本文不引用 |
| 使用者決定 | D25（[#26](https://github.com/Polalalabear/amidst/issues/26)）、D26–D28（§0.2） |
| Claude 文件 | [回覆](../agents/CONTROLLED_SCENE_CLAUDE_REPLY_20261018.md)、[UX 草圖](../agents/CONTROLLED_SCENE_UX_SKETCH_20261018.md) |
| 規則 | [DEVELOPMENT_RULES](../DEVELOPMENT_RULES.md)；本契約不放寬 GT 隔離，D1 照舊 |

**沿用的既有契約（固定版本）：**

| 契約 | 版本 | 沿用的部分 |
| --- | --- | --- |
| [區間觀測 v1](OFFICE_INTERVAL_OBSERVATION_V1.md) | 整合分支 @ `dcb89f4` | `ground_estimate` 物件、§2.1 共用 provenance 區塊 |
| [盲區假設 v1](OFFICE_BLIND_HYPOTHESIS_V1.md) | 整合分支 @ `dcb89f4` | — |
| [畫面檢索 v1](OFFICE_FRAME_RETRIEVAL_V1.md) | 整合分支 @ `dcb89f4` | — |
| 契約 v1.1（[#45](https://github.com/Polalalabear/amidst/pull/45)） | @ `9e1234cc0e626abf49669f6ab0624c42f6e8bacf` | `FOOT_RAY_PIXEL_BAND`（R1／D17）、D21 strict／suggestion 規則 |

**新場景不沿用**的舊 Office 條文：
- `floor_z_m = 0.4959…` 與其他 Office 常數；
- D18 的固定端點與 `D18_INTERVAL_CONTAINS_OBSERVATION` guard（保留給舊 run）；
- annotation authority 與 proxy 排除規則；
- D15 禁止區、D16 座椅規則；
- `MAX_CAMERAS` 等 Office wrapper 的寫死值（見 CS-Q7、CS-Q14）。

名稱保留 `OFFICE_` 前綴，只是為了和既有契約並列；新場景本身不叫 Office。

### 0.2 使用者決定（2026-10-18，由協調者轉達，引號內是使用者選的選項原文）

| 決定 | 使用者選項 | 內容 | 落在本文 |
| --- | --- | --- | --- |
| **D26** GT 時機 | 「RGB 人工驗收」 | CS-B 只用 RGB 逐格人工核對覆蓋與 B1 錯開，加上靜態標記、校正核對與產製完整性。GT／mask 的數值評估延到輸出凍結後。D1 不放寬。**「逐格人工核對」已由 D47 改成 §8.1 的流程**；不讀 GT 的部分不變 | §7、§8 |
| **D27** CS-Q3 | 「雙鏡全身＋接地」 | 事件 A 雙鏡重疊的目標區域內，兩台鏡頭都要拍到全身（頭頂到腳），RGB 裡看得到接地。不能用 bbox 底邊推定腳 | §5.2 |
| **D28** CS-Q4 | 「不列入排序」 | v1 排序是 `relation_tier → overlap_area_m2_desc → camera_id`；偵測數只當附帶證據欄位，並標明評估範圍與數量是否完整 | §6.1 |

D25 的內容（960×540／5 fps／PNG、B1／B2、固定 2 人、轉角無鏡頭、D3 反轉、D8 改為 B2 驗收前）照舊適用。

**D32（[#66](https://github.com/Polalalabear/amidst/issues/66)）：**「核准 CS-A（建議）」。核准對象是 #65 @ `2643771`。這項核准不授權 B 包建 `.blend` 或渲染；CS-Q9、CS-Q11 仍然 OPEN。

**D36–D42（[#68](https://github.com/Polalalabear/amidst/issues/68)，B 包設計門檻；以下是摘要，以 #68 全文為準）：**

| 決定 | 使用者選項 | 摘要 |
| --- | --- | --- |
| D36 B-Q1 | 「修正 W2 pose」 | 修正 W2 pose，讓事件 A 的 i48–i49 看得到人，並重算相關餘量；所有可走地板統一在 z = 0，不分層 |
| D37 B-Q2 | 「固定 11.0 s，盲窗只驗下限」 | P2 固定 11.0 s 進場；同一台鏡頭兩人至少錯開 1.0 s，而且中間有 4 個以上空 sample；盲窗 RGB 驗收只強制 ≥3.2 s（4.0 s 是設計目標）；西界 13.7；兩人中心距 ≥8 m 是產製約束，不列入 RGB 驗收 |
| D38 B-Q3 | 「投影＋偵測器＋人工」 | 全身＋接地、距畫面四邊 ≥16 px、人高 ≥112 px；偵測器只讀 RGB、只當輔助量測，和人工不一致時以人工為準並記錄差異。**「人工逐格」已由 D47 修訂** |
| D39 B-Q4 | 「接受 partial」 | 只有 D27 的目標窗要求全身；列出接地端點候選 W2 7.2 s → N1 14.8 s；不承諾盲窗邊緣就是合格端點；partial 段不能稱為盲區 |
| D40 B-Q5 | 「10 m geodesic」 | 理由寫成公開 prior（1.3 m/s × 約 7.7 s），不寫成 N1 的位置 |
| D41 B-Q6 | 「1 ms＋把副本計入額度」 | `clock_error` 容差 1 ms，`sample_age` 獨立計算；峰值額度 1.5 GiB，起跑保護 12 GiB、停止保護 8 GiB；`.blend1` 與審查副本計入額度 |
| D42 人形設定 | 「照 Claude 建議」 | 判斷看得到用名義人體 1.70 m／r 0.25，判斷看不到用包絡 1.80 m／r 0.30；人形身高 1.65–1.75 m、肩寬 ≤0.5 m；P1、P2 用相同的中性外觀 |

**D44（v1.1 草案的依據）：**「三種都寫進去」。人物接地估計的規格要納入三種條件，契約條文在 §3.12、§6.3、§7。
- **遮擋邊界：**只用 `scene_static` 已核准的靜態幾何。
- **軌跡身高：**只在同一台鏡頭、連續的 local track 內估計；不跨鏡頭，也不當關聯或身份證據。
- **速度界：**用公開的速度上限劃出範圍，和線段取交集。

輸出的 evidence state 一律是推論。每一格都要記錄用到的條件與其來源；所有條件都失效時回 `UNKNOWN`。

**D43（[#72](https://github.com/Polalalabear/amidst/pull/72)）：**v2 工作台設計的 Q1、Q4–Q10 全部照建議。細節以 #72 為準，本契約只記這一行摘要。

**D45：**「估計誤差要明確標出（文件內和demo時都要說）」。契約條文在 §2.4、§6.3、§6.4、§8。
- 每一個推論的人物位置、區間、曲線，都要附機器可讀的不確定度。
- UI 必須顯示不確定度。
- Demo 每一步都要說明當下顯示的是觀測還是推論，以及誤差的來源與大小。
- 文件引用的估計結果都要附誤差，沒有就寫 `UNKNOWN`。

**D46：**3D 人物只顯示從 2D 重現的結果，鏡頭看得到的區段也一樣。工作台永遠不讀 GT，也不做 GT 對照圖層（§7）。

**D47：**「模型先篩，後續會接 openai api 進行實際測試」。CS-B 的影像驗收改成模型先篩、人工看重點格，流程在 §8.1。
- 取代 D38 原本的「人工逐格」，也修訂 D26 的「逐格人工核對」。
- D26 的其他部分不變：CS-B 不讀 GT，GT／mask 的數值評估仍延到輸出凍結後。
- 外部 API 的邊界見 §7。

**D48（[#68](https://github.com/Polalalabear/amidst/issues/68)）：**「R1＋加深 SCREEN_N（建議）」。內容以 #68 全文為準，不改契約條文：
- W2 位置改為 x = 14.4（(14.4, 2.1, 1.8)，角度不變）；
- `OBSTACLE_SCREEN_N` 加深到 y = [5.25, 5.6]。

**D49（[#68](https://github.com/Polalalabear/amidst/issues/68)）：**「條件式授權（建議）」。條件全部成立時，才可以建 `.blend`（正本與 D33 審查副本）並渲染四張 preview；完成後停下，等使用者人工審查（D33）。這不授權渲染整段序列、凍結或讀 GT。條件與範圍以 #68 全文為準。

**D50–D54（[#68](https://github.com/Polalalabear/amidst/issues/68)，全文以 #68 為準）：**
- **D50：**W2 yaw 改為 205°（Blender Euler (80, 0, 115)），位置 (14.4, 2.1, 1.8)、俯角 10° 不變；取代 D48「角度不變」的文字。
- **D51：**收窄人形，讓整個步態側向半徑 ≤0.30 m；建新 revision r002，不覆寫 r001。
- **D52：**D33 審查結果是修牆面黑縫後通過；建 r003，不改牆面位置、遮屏、路線、鏡頭與門檻。
- **D53：**「r003 確認，D33 通過」。r003 是整段序列渲染的基準 `.blend`；**整段渲染（550 張）要另外授權**。
- **D54：**生成前門檻 A1–A4，全部照建議：A1 保守多標、A2 路線投影＋20%、A3 雜湊排序抽樣、A4 各 2 格＋切換處。條文在 §7、§8.1；這些門檻不得在看過 RGB 或 GT 後調整。

## 1. 目的與權限

- 本契約描述一個新的、獨立的受控測試場景：靜態標記、攝影機、事件情境，以及工作台讀取的 API。
- 人物的位置、方向與跨鏡頭關聯，**只能從 RGB 影像證據推得**。靜態背景可以使用核准用途的模型與校正（§3.3 `allowed_purposes`）。
- 事件腳本只在隔離的產製端用來生成影像。GT、遮罩等評估資料只能在**輸出凍結且 hash 驗證後**讀取（D26）。
- 正式服務不得開啟 private 檔案，也不得以事件標籤決定排序或配對。
- 身分一律 `UNCONFIRMED`。實體通行性與碰撞，在已核准範圍以外一律 `UNKNOWN`。

## 2. 共通慣例

| 項目 | 規定 |
| --- | --- |
| 長度 | 公尺（m）。匯出檔寫 `"length_unit": "m"`，其他值 fail closed |
| 時間 | 秒（s），以 run 的來源時鐘為準 |
| 世界座標 | Blender 世界座標，右手系，Z 軸向上 |
| 地板 | 由 `floors[]` 宣告支撐面（§3.1）。讀取端不得寫死 0 或舊 Office 高度 |
| 取樣索引 | `frame_index` 是公開的、從 0 起算的 sample index，`timestamp_s = frame_index / fps`。Blender 的 `frame_start`、`frame_step`、`fps`、`fps_base` 對應只存在產製端的 private manifest |
| 時間區間 | run 用半開區間 `[0, duration_s)`，`duration_s × fps` 必須是整數。`duration_s` 與 `last_timestamp_s` 分成兩欄；不能把最後一張的時間當成結束時間 |
| 證據狀態 | `PROJECTED_OBSERVATION`、`INFERRED_INTERPOLATION`、`INFERRED_HYPOTHESIS`、`MISSING`、`UNKNOWN` 分開。sibling estimate 不回填原觀測的 `world_position` |
| 同步容差 | `abs(clock_error_s) ≤ 0.001 s`（D41）；`sample_age_s` 另外計算，不算同步誤差 |

### 2.1 Hash 規則

- 檔案位元組的 hash 叫 `file_sha256`；canonical JSON 內容的 hash 叫 `content_sha256`。兩者不得混用同一個欄位名。
- canonical JSON 的序列化設定固定為 `sort_keys=True, separators=(',', ':'), allow_nan=False, ensure_ascii=True`，編碼 UTF-8。這與既有 `registry.content_hash` 的實作一致。
- 其他規則：
  - hash 不包含欄位自身，也不包含明列的計時欄位（例如 `stats.latency_ms`）。
  - 拒絕 NaN 與 Infinity。
  - 每個欄位要宣告數值型別。
  - 陣列的排序規則在各 schema 中寫明。
- 幾何 hash 另外由 `geometry_encoding_version` 固定以下規則：世界座標公尺、面索引、modifier 是否已評估、頂點與面的排序。

### 2.2 影格之間的時間內插

- 5 fps 時影格間隔 0.2 s。**只有 sample 時間點上的資料是觀測。**
- **2D：**依預期的 sample grid 選格（`LATEST_AT_OR_BEFORE`），即 `timestamp_s ≤ t` 的最後一個 sample。
  - 那個 sample 列在 `rgb_index.missing[]` 時，該格是 `MISSING`，**不得跳過它去找更早的可用影像**。已 pin 的 sample 檔案不存在，是完整性錯誤（§2.3）。
  - 影格本身是觀測，但它的時間是 `timestamp_s`，不是 `t`。
- **3D 內插的條件：**
  - 只能在**同一條 RGB 推得的局部軌跡**內做，而且兩端都有效時才做，範圍有界。
  - 不得跨過 `MISSING`、`UNKNOWN` 或未關聯的缺口。
  - 是不是缺口，由 RGB 記錄判斷，**不讀** private 的 `designed_blind_intervals`。
- **狀態標示：**
  - 單純移動播放頭只是時間控制，不產生證據狀態。
  - 只有內插算出來的空間幾何（位置、區間、刻度位置）標 `INFERRED_INTERPOLATION`，而且不得用觀測色。
  - 盲區中的 K1 假設切片維持 `INFERRED_HYPOTHESIS`，不得改標成內插。
- 把 5 fps 包成較高幀率播放，不會增加觀測。

### 2.3 缺影格與完整性錯誤

| 情況 | 處理 |
| --- | --- |
| sample 列在 `rgb_index.missing[]`（產製時就記錄為沒有這張影格） | 該格 `MISSING`（`reason` 照 `missing[]` 記錄的原因，例如 `RGB_RECORD_ABSENT`）。不補位，不用鄰近影格或其他 run |
| sample 列在 `rgb_index.records[]`、已 pin `file_sha256`，但檔案不存在 | **完整性錯誤**：`DataIntegrityError`（`reason: PINNED_RGB_RECORD_MISSING`）。整個 run fail closed，**不得降格為 `MISSING`** |
| expected grid 中的 sample，既不在 `records[]` 也不在 `missing[]` | **完整性錯誤**：`DataIntegrityError`（`reason: RGB_INDEX_INCOMPLETE`）。index 本身不完整，整個 run fail closed |
| 超出 run 的時間範圍 | `OUT_OF_RANGE` |
| hash、source 或 pin 不符 | **完整性錯誤**：`DataIntegrityError`，沿用既有原因碼（例如 `RGB_RECORD_HASH_MISMATCH`）。整個 run fail closed，不發 media token，**不得降格為 `MISSING`** |

### 2.4 不確定度標示（v1.1 草案，D45）

**payload 規則：**每一個 `READY` 的推論項目都必須帶一個 `uncertainty` 物件。範圍包括：
- §6.3 的 `composed_ground`；
- §6.3 推論的 `heading`；
- §6.4 的 `INFERRED_CONNECTOR`、`BLIND_HYPOTHESIS`，以及之後的 `PREDICTION`。

```json
{
  "uncertainty": {
    "extent_kind": "LENGTH_M",
    "extent_value": 0.49,
    "constraints_used": ["track_height", "occlusion_near", "lowest_visible_far", "speed"],
    "quality_grade": "MEDIUM",
    "quality_rule_ref": "quality-grade-rule-v1",
    "quality_rule_sha256": "…"
  }
}
```

| 欄位 | 規則 |
| --- | --- |
| `extent_kind` | `LENGTH_M`（區間長度，公尺）、`AREA_M2`（polygon 或範圍帶面積，平方公尺）、`ANGLE_DEG`（方向的角度範圍） |
| `extent_value` | 數值，單位依 `extent_kind`。範圍帶隨時間變化時填該段的最大值，並以 `per_sample_ref` 指向逐時刻的值（例如 K1 的 `reachable_regions[].area_m2`） |
| `constraints_used` | 用到的條件。位置與區間使用 D44 的五種：`prior`、`track_height`、`occlusion_near`、`lowest_visible_far`、`speed`。曲線另外可用 `endpoint_estimates`（兩端估計）與 `k1_reachability`（K1 的地圖與速度設定）。各條件的 ref 與 hash 照 §6.3.1 記錄 |
| `quality_grade` | `HIGH`、`MEDIUM`、`LOW`、`UNKNOWN`。這是**依公開規則分出的品質等級，不是機率**，也不是身份或事件發生的信心。分級門檻待約定（CS-Q15），規則以 `quality_rule_ref` 與 hash 綁定 |

- **缺欄位就是完整性錯誤：**`READY` 的推論項目缺少 `uncertainty` 或其中任一欄位時，是完整性錯誤（`DataIntegrityError`，`reason: UNCERTAINTY_FIELDS_MISSING`），整個回應 fail closed，**不得默默省略**。
- **`UNKNOWN` 項目：**`status: UNKNOWN` 的項目照原規定回 `geometry: null`。它的 `uncertainty` 是 `{extent_value: null, quality_grade: "UNKNOWN"}`，並列出原因。
- **觀測項目：**觀測（`PROJECTED_OBSERVATION`）照區間觀測 v1，帶 `pixel_sensitivity_m` 等欄位，不受這條規則限制。

**UI 規則：**
- 畫面必須顯示不確定度：選取項目的讀數（例如「區間 0.49 m」「範圍帶 7.2 m²」），以及常駐圖例。
- 推論不得畫得像觀測一樣確定，也不得省略讀數只畫幾何。

**文件與 Demo 規則：**
- 文件引用的估計結果都要附誤差或不確定度；沒有就寫 `UNKNOWN`。
- Demo 每一步都要說明當下顯示的是觀測還是推論，以及誤差的來源與大小。
- 輸出凍結前，誤差大小只能說「設計估計」或系統自身的不確定度（上面的 `extent_value`）。輸出凍結、並用 GT 評估之後，才能說與真值比較的誤差數字（D26）。兩者不得混稱。

## 3. Scene schema

### 3.0 檔案分成兩側

| 側別 | 檔案 | 讀取者 |
| --- | --- | --- |
| **safe** `runs/<run_id>/safe_bundle/` | `manifest.json`、`scene_static.json`、`cameras.json`、`event_A.query.json`／`event_B1.query.json`、`rgb_index.json`、`runtime_profile.json`、`outputs/`（日後凍結的 RGB 推得輸出） | 正式服務；只透過 safe manifest 的 allowlist 開啟 |
| **private** `private_evaluation/<run_id>/` | `production_manifest.json`、`event_A.validation.json`／`event_B1.validation.json`、`persons.sim.json`、`gt/` | 產製端；評估端只在輸出凍結後讀 |

- safe manifest 不得含事件腳本、私有 locator、generator script 或 config 的內容。它可以持有不透明的 source hash，但不得解析 private 內容。
- `event_*.validation.json` 不得出現在正式 loader 會遞迴開啟的檔案集合中。

### 3.1 座標、尺度與樓層（`scene_static.json`）

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `schema_version` | string | 是 | `controlled-scene.static.v1` |
| `scene_id` | string | 是 | `controlled-l-corridor`（不含版本號） |
| `scene_version` | integer | 是 | 初版 `1`；幾何改變就遞增 |
| `frame_id` | string | 是 | 世界座標系 ID |
| `length_unit`、`time_unit` | `"m"`、`"s"` | 是 | |
| `world_axes` | `"BLENDER_Z_UP_RIGHT_HANDED"` | 是 | |
| `floors[]` | array | 是 | `{floor_id, support_plane: {point_m, normal}, support_surface_ids[], source_static_sha256, approved_scope_ref}`。首版只有一層、一個平面；超出核准範圍一律 `UNKNOWN` |
| `source_static_sha256` | string | 是 | 靜態來源的 hash |

### 3.2 穩定 ID 規則

- 格式 `^[A-Z][A-Z0-9_]{2,63}$`。類別前綴：

  | 前綴 | 類別 |
  | --- | --- |
  | `WALK_` | 可走區域 |
  | `OBSTACLE_` | 障礙物 |
  | `WALL_` | 牆 |
  | `PORTAL_` | 門、開口 |
  | `STAIR_` | 樓梯 |
  | `ROOM_` | 房間 |
  | `CORR_` | 走廊 |
  | `AREA_` | 查詢用的目標區域 |
  | `CAM_` | 攝影機 |
  | `FLOOR_` | 樓層 |

- ID 存在 Blender 物件的 custom property `amidst_id`，不靠顯示名稱。
- 幾何修改不換 ID，只遞增 `geometry_version`。刪除的 ID 不得重用。
- 重複 ID 讓整份匯出無效。跨檔案的 ID 引用必須存在，類型也必須相符。

### 3.3 靜態物件（`objects[]`）與用途核准

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `id`、`class` | string、enum | 是 | `class`：`WALKABLE`、`WALL`、`OBSTACLE`、`PORTAL`、`STAIR`、`ROOM`、`CORRIDOR`、`AREA`、`DISPLAY_ONLY` |
| `source_mesh` | string | 是 | Blender 物件名稱，只作追溯 |
| `source_object_id` | string | 是 | 來源物件的穩定 ID |
| `geometry_ref`、`geometry_sha256` | string | 是 | 指向實際幾何檔與其 hash |
| `geometry_version`、`geometry_encoding_version` | integer、string | 是 | |
| `transform_applied` | `"WORLD_METRES"` | 是 | |
| `bounds_m` | `[[xmin,ymin,zmin],[xmax,ymax,zmax]]` | 是 | 只是外框；**hash 與外框都不能當碰撞或 raycast 幾何** |
| `source_method` | enum | 是 | `ANNOTATED_AT_CREATION` 或 `UNKNOWN`。這只描述來源方法，不代表用途已核准 |
| `allowed_purposes` | array | 是 | 從 `WALKABILITY`、`OCCLUSION`、`COLLISION`、`VISIBILITY_INDEX`、`DISPLAY` 中選 |
| `approval_status` | enum | 是 | `APPROVED`、`NOT_EVALUATED`、`REJECTED` |
| `scope_ref`、`approval_ref`、`approval_sha256` | string\|null | 是 | 核准範圍與核准紀錄 |
| `display_only` | boolean | 是 | `true` 時優先拒絕 walkability、occlusion、collision 用途 |

### 3.4 Walkable（`walkable[]`）：新場景唯一的推論用地圖

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `id`、`floor_id`、`support_surface_id` | string | 是 | |
| `polygon_m`、`holes_m` | polygon、array | 是 | 逆時針、不自交 |
| `geometry_ref`、`geometry_sha256` | string | 是 | |
| `status` | enum | 是 | `WALKABLE`、`BLOCKED`、`UNKNOWN`。未標的地面一律 `UNKNOWN` |
| `connections[]` | array | 是 | `{to_walk_id, via_portal_id or null}`，雙向各寫一次，必須對稱。`via_portal_id: null` 只用於已核准的連續地板接界，不代表可以穿牆 |
| `approval` | object | 是 | 見下 |

- 轉角這類重疊地板要有一致的聯集與歸屬規則：面積不得重複計算，也不得建立互相矛盾的連通。
- `approval`：
  - 還沒跑驗證時：`{status: "NOT_EVALUATED", verified_by: [], verification_sha256: null}`。
  - 跑過驗證後：填 verifier 名稱與版本、輸入 hash、報告 hash。
  - 不得預先寫成 C7、K7 都已驗證。
- K7 的 private 路線報告只留在 private 端。推論端能讀的收據，只含不洩漏路線的靜態核對結果。
- 驗證器（C7、K7）不自動改檔，只輸出 fail 或 `UNKNOWN` 報告。consumer 在不一致的範圍內 fail closed。人工修訂要產生新的 map 版本與 hash，舊檔不變。

### 3.5 牆與障礙物

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `id`、`floor_id` | string | 是 | |
| `footprint_m`、`base_z_m`、`height_m` | polygon、number、number | 是 | |
| `geometry_ref`、`geometry_sha256` | string | 是 | |
| `role` | enum | 是 | `PHYSICAL` 或 `DISPLAY`。`DISPLAY` 不進任何物理判斷 |
| `collision_scope` | enum | 是 | `EXACT_MESH` 必須能解析到實際 mesh；`FOOTPRINT_EXTRUDED` 只證明這個近似範圍內的碰撞，不能宣稱精確遮擋；`UNKNOWN` |
| `body_policy_ref`、`body_policy_sha256` | string | 是 | 淨空檢查依據的人體政策設定檔 |
| `allowed_purposes` | array | 是 | 同 §3.3 |

### 3.6 門與樓梯

**門（`portals[]`）：**

| 欄位 | 型別 | 必填 | 說明 |
| --- | --- | --- | --- |
| `id`、`floor_id` | string | 是 | |
| `opening_m` | `{a:[x,y], b:[x,y], width_m, sill_z_m, height_m}` | 是 | 開口的兩端與底高 |
| `geometry_ref`、`geometry_sha256`、`geometry_version` | | 是 | |
| `connects` | `[walk_id, walk_id]` | 是 | 缺一側就是 `UNKNOWN` |
| `state` | enum | 是 | 首版固定 `OPEN`，是公開的靜態狀態；首版沒有動態門 |
| `allowed_purposes` | array | 是 | |

**樓梯（`stairs[]`）：**獨立分型，需要多層端點、支撐面與幾何，不套用門的 2D schema。首版 `stairs: []`。若預留了實體，標 `used_in_first_round: false, acceptance: NOT_ACCEPTED`，不進首版路徑。

### 3.7 攝影機：光學校正與 run 綁定分開

**光學校正（`cameras.json` 的 `cameras[]`，A、B1 共用）：**

| 新欄位 | 對應既有 safe camera 輸入（Codex 審查 §3） |
| --- | --- |
| `schema_version`、`camera_id` | `calibration.camera_id`；外層另有 `camera_ref`、`authority` |
| `camera_to_world` | 4×4，列優先，世界公尺；不轉置、不再縮放 |
| `convention: "BLENDER_NEG_Z_UP_Y"` | 沿用既有名稱：−Z 向前、+Y 向上；匯出時要核對旋轉矩陣與行列式 |
| `fx`、`fy`、`cx`、`cy`、`pixel_origin: "TOP_LEFT_CONTINUOUS"` | 不另加 0.5 pixel |
| `width`、`height`、`pixel_aspect_xy`、`render_resolution_percentage` | K 必須對應實際的 PNG |
| `shift_x`、`shift_y`、`sensor_fit`、`sensor_width_mm`、`sensor_height_mm`、`focal_length_mm` | 產製追溯；正式定位以核對後的 K 為準 |
| `clip_start`、`clip_end` | 公尺；不沿用 Office 的 24.7 m |
| `distortion: null`、`camera_model: "PINHOLE"` | |
| `floor_id`、`zone_id`、`meters_per_unit: 1.0` | 地板平面的 point、normal 與 source hash 另外綁定 |
| `static_validity` | 靜態 pose 的有效範圍 |
| `calibration_sha256` | canonical 光學內容的 hash。**不含 clock** |

新 JSON 不能直接送進舊的 strict schema，要透過明確的 adapter。

**run 綁定（`cameras.json` 的 `run_bindings[]`，每個 run 一份）：**`{run_id, camera_id, clock_id, valid_time_range_s, visibility_index_ref, binding_sha256}`。A 和 B1 不共用 clock。

### 3.8 事件情境

**`event_<A|B1>.query.json`（safe）：**

| 欄位 | 說明 |
| --- | --- |
| `schema_version`、`event_id`、`run_id` | `event_id` 只是 UI 選項，用來定位這個 run。source、run、clock 由 server 從 catalog 解析 |
| `duration_s`、`camera_ids`、`sampling_version` | 公開的技術資訊 |
| `suggested_queries[]` | `{target_region_ref, query_intent, time_range_s}`，只用來預填 UI，不參與配對或排序 |

safe 檔不得含人物數、路線、覆蓋時間窗或盲區答案。

**`event_<A|B1>.validation.json`（private）：**

| 欄位 | 說明 |
| --- | --- |
| `schema_version`、`source/run/clock` 的 ref 與 hash | |
| `target_area_id`、`entry_exit_portals[]` | |
| `observation_windows[]` | `{segment_id, time_range_s, region_m, required_cameras[], visible_part: FULL_BODY / FOOT / PARTIAL}` |
| `overlap_requirements[]` | `{cameras, region_m, time_range_s, visible_part}` |
| `designed_blind_intervals[]` | `{blind_id, region_polygon_m, expected_time_range_s, cameras_expected_blind: [這個 run 的鏡頭 ID]}` |
| `separation_requirements[]` | B1：`{rule: "MAX_ONE_PERSON_PER_CAMERA_FRAME", min_gap_s: 1.0, min_empty_samples: 4}`（D37：同一台鏡頭兩人至少錯開 1.0 s，中間至少 4 個空 sample） |

時間、間隔、像素門檻都待約定。這個檔案**不進 runtime readiness**。

### 3.9 人物產製設定（private）

- `persons.sim.json` 的內容：`{person_sim_id, height_m, body_radius_m, gait, speed_mps, route_waypoints_m[], start_s, end_behavior, seed}`。
- 只供隔離的產製端，以及凍結後的評估。
- 固定 2 人是情境設定，不能拿來限制偵測數、替人物命名或挑選 prior。
- seed 不是正式推論的輸入。

### 3.10 Manifest

| safe `manifest.json` | private `production_manifest.json` |
| --- | --- |
| `schema_version`、`scene_id`、`scene_version`、`run_id`、`clock_id` | `blend_file_sha256`、`blender_version` |
| `sampling`：`{fps, image_size_px, format: "PNG_RGB8", sampling_version, duration_s, sample_count_per_camera, last_timestamp_s}` | Blender 影格對應（`frame_start`、`frame_step`、`fps`、`fps_base`） |
| allowlist：`scene_static`、`cameras`、`event query`、`rgb_index`、`runtime_profile` 的檔名與 `file_sha256` | generator script 與 config 的 hash、`random_seed` |
| 公共 config 的 hash（人體 prior、偵測器設定） | validation、`persons.sim`、GT 檔案清單與 hash |
| 不透明的 `source_sha256` | 作者路線、產製設定、完整相機與牆的細節 |

### 3.11 `rgb_index.json` 與 `runtime_profile.json`（safe）

- `rgb_index.json`：
  - `records[]`：`{camera_id, frame_index, timestamp_s, rgb_ref, file_sha256}`；
  - `missing[]`：`{camera_id, frame_index, timestamp_s, reason}`，是產製時就確定沒有的 sample；
  - expected grid：每個 sample 必須正好出現在 `records[]` 或 `missing[]` 其中一處（§2.3）。
  - `rgb_ref` 是相對路徑，指向 canonical 檔；不用 symlink，也不複製。
- `runtime_profile.json`：技術準備度的期望值，只含 grid、hash、API 可用性。**不含**人物的預期位置、盲窗或配對。

### 3.12 RGB 推得的輸出（CS-A 待核准的介面設計，CS-Q10）

**局部軌跡（Codex 主責）：**
- 內容：`{source/run/clock/camera, local_track_ref, ordered observation_refs 與 frame_refs, sample_indices, timestamps, gap_reasons, termination_reason, ambiguity_reason, producer, config_sha256, output_sha256}`。
- 局部軌跡只在單一鏡頭內有效，不跨鏡頭升級成身份。

**軌跡身高 `track_height_estimate`（v1.1 草案，D44；局部軌跡的欄位，Codex 主責）：**

```json
{
  "track_height_estimate": {
    "status": "READY",
    "reason": null,
    "scope": {"camera_id": "CAM_W2", "local_track_ref": "lt-…", "run_id": "…", "clock_id": "…"},
    "usage_restriction": "WITHIN_TRACK_GROUND_COMPOSITION_ONLY",
    "height_m": 1.71,
    "uncertainty": {"method": "待約定（CS-Q15）", "lower_m": 1.68, "upper_m": 1.74},
    "temporal_scope": "WHOLE_TRACK",
    "support_frame_refs": ["fr-…-CAM_W2-000030", "fr-…-CAM_W2-000031"],
    "support_observation_refs": ["obs-…-000030-c0", "obs-…-000031-c0"],
    "n_support_frames": 2,
    "selection_rule_ref": "track-height-rule-v1",
    "selection_rule_sha256": "…",
    "calibration_sha256": "…",
    "producer": "…",
    "config_sha256": "…",
    "output_sha256": "…"
  }
}
```

- **只用哪些影格：**同一條局部軌跡內，頭和腳都看得到、而且是高信心的影格。「高信心」的條件與最少格數待約定（CS-Q15）。
  - 腳點必須通過 §6.3 的遮擋檢查，不能是被靜態障礙物遮住的候選。
  - 頭與腳都不得貼近畫面邊緣。
- **狀態：**
  - `READY`：估計成功。
  - `INSUFFICIENT_FRAMES`：符合條件的影格不夠。
  - `UNKNOWN`：無法估計。
  - 不是 `READY` 時，`height_m` 與 `uncertainty` 都是 `null`。
- **時間範圍 `temporal_scope`：**`WHOLE_TRACK`（整條已封存軌跡）或 `CAUSAL`（只用當格以前的影格），必須宣告。本草案建議 `WHOLE_TRACK`，待 Codex 確認（CS-Q15）。
- **不跨 track：**
  - 身高只屬於這一條局部軌跡。
  - track 一斷（缺口、終止、歧義）就結束；下一條 track 重新估計，在估到之前退回公開先驗。
  - 不得跨鏡頭、跨 track 或跨 run 沿用。
- **生物特徵限制：**身高屬於生物特徵。
  - 不得當作跨鏡頭關聯、身份、候選排序、K8c 篩選或任何配對的證據，也不得出現在跨鏡頭候選的 payload 裡。
  - 前端不把它顯示成人物屬性或標籤；只在 §6.3 `composed_ground.constraints_used` 的來源紀錄中出現。
- **不讀 GT：**不讀 GT、`persons.sim.json` 的 `height_m`，也不讀 D42 的產製設定逐人數值；評估要等輸出凍結後（§7）。

**跨鏡頭候選（Claude 主責純介面與演算法，Codex 整合）：**
- 內容：`{candidate_ref, endpoint local_track_ref 與 observation_ref, eligibility, alternatives, unassociated_baseline, evidence_refs, scope, config_sha256, output_sha256}`。

**共同規則：**
- 讀不到資料時填 `null` 或 `UNKNOWN`。
- 不得填 actor ID，也不得使用事件答案。
- 沒有局部軌跡時，方向是 `UNKNOWN`，曲線不連接。

## 4. 檔案與存放

依 Codex 審查 §5，屬於 CS-A 待核准的介面設計。

- 資料根是 `data/pilot/controlled_scene_v1`，位於資產 checkout 中被 Git 忽略的 data 範圍內。
  - 服務以相對於 checkout 的路徑解析，不把本機絕對路徑寫進公開 payload。
  - 「不放共用 checkout」的意思是「不追蹤 Git」。

```text
data/pilot/controlled_scene_v1/
  assets/controlled_scene_v1.blend
  runs/<run_id>/
    rgb/<CAM_ID>/frame_<frame_index:06d>.png
    safe_bundle/manifest.json
    safe_bundle/scene_static.json
    safe_bundle/cameras.json
    safe_bundle/event_<A|B1>.query.json
    safe_bundle/rgb_index.json
    safe_bundle/runtime_profile.json
    safe_bundle/outputs/
  private_evaluation/<run_id>/
    production_manifest.json
    event_<A|B1>.validation.json
    persons.sim.json
    gt/
  derived/<run_id>/
```

- **run ID：**格式是 `ctrl-lcorr-s<scene_version>-<a|b1|b2>-<sampling_version>-r<revision:03d>`。第一版預定為 `ctrl-lcorr-s1-a-5fps-v1-r001`、`ctrl-lcorr-s1-b1-5fps-v1-r001`。這兩個是預定的 ID，run 還不存在。
- **版本：**
  - 10 Hz 用 `…-10hz-v2-r001`。
  - 影像、相機、產製設定或 source 改變時，產生新的 revision（必要時連 scene version 一起升），不得就地覆寫已封存的檔案。
  - `.blend` 封存後不覆寫；重新設計要用新檔名。
- **clock ID 與檔名：**
  - clock ID 是 `clock:<run_id>`；同一 run 的鏡頭共用一個 sample grid。
  - 事件 A 每台的 index 是 0–49，B1 是 0–99，檔名例如 `frame_000049.png`。
- **讀取範圍：**
  - server 只解析已註冊 run 的 safe manifest。
  - media allowlist 逐項解析 `rgb/<CAM_ID>/frame_*.png`，拒絕 symlink、越界路徑、`private_evaluation`、`derived` 與 hash 不符的檔案。
  - 不把整個資料根當成靜態目錄提供。
- **磁碟：**A＋B1 共 550 張 PNG，估 0.133–0.398 GiB（外推，不是新場景實測）。資料加 staging 的峰值額度是 1.5 GiB，不含 OS swap。起跑保護 12 GiB、停止保護 8 GiB 已由 D41 定案；`.blend1` 與審查副本也計入額度。授權整段渲染前要重查可用空間（CS-Q11）。
- **B 包第一步：**另開一個隔離的 preview run `ctrl-lcorr-s1-preview-5fps-v1-r001`，四台各渲染一張。
  - manifest 標 `purpose: CALIBRATION_PREVIEW, complete: false`。
  - 這四張只能檢查外觀、校正、輸出與每張大小，**不算整段場景驗收**，也不能用來凍結預測。
  - 選哪一個 sample 只記在 private 端。

## 5. 事件情境規格

### 5.0 取樣（D25）

| 版本 | 解析度 | 幀率 | 格式 | 事件 A | 事件 B1 | 合計 | 狀態 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `5fps-v1` | 960×540 | 5 fps | PNG，8-bit RGB | 3 台 × 50 張 = 150 | 4 台 × 100 張 = 400 | 550 | **第一版** |
| `10hz-v2` | 960×540 | 10 Hz | PNG，8-bit RGB | 3 台 × 100 = 300 | 4 台 × 200 = 800 | 1,100 | **後續版本**：5 fps 穩定後才做；新的 run ID、pin、hash；不覆寫 `5fps-v1`，也不自動產生 |

### 5.1 場景配置（起始候選幾何，未驗證）

以下尺寸是起始候選，**不標 VERIFIED**。B 包要補上：
- 牆厚與牆高；
- 門的開口；
- 正式支撐面；
- 幾何檔。

| ID | 範圍（m） | 說明 |
| --- | --- | --- |
| `CORR_W`／`WALK_CORR_W` | x 0–17.4，y 0–2.4 | 西走廊 |
| `CORR_N`／`WALK_CORR_N` | x 15–17.4，y 0–12 | 北走廊；轉角 x 15–17.4、y 0–2.4 與西走廊重疊，依 §3.4 的規則歸屬一次 |
| `ROOM_R101`／`WALK_R101` | x 5–11，y −5–0 | 目標房間，無鏡頭 |
| `PORTAL_R101` | y = 0，x 7.4–8.6 | R101 門 |
| `ROOM_R102`／`WALK_R102` | x 17.4–22.4，y 7–11 | 對照房間 |
| `PORTAL_R102` | x = 17.4，y 8.4–9.6 | R102 門 |
| `AREA_R101_FRONT` | x 6.5–9.5，y 0–2.4 | 目標區域 |

**鏡頭的起始位置已由設計稿 #54 @ `f2afa3f`／D36、D48、D50 取代**，以設計稿為準。下表只是為了方便閱讀，抄自設計稿 §2；兩者若有出入，以設計稿為準：

| 鏡頭 | 位置 (m) | yaw／俯角 (°) |
| --- | --- | --- |
| `CAM_W1` | (−2.6, −1.4, 2.0) | 15／16 |
| `CAM_W2` | (14.4, 2.1, 1.8) | 205／10（D50） |
| `CAM_N1` | (13.0, 13.5, 2.4) | −65／20 |
| `CAM_R102_CTRL` | (21.8, 10.5, 2.8) | 225／25 |

- 原本的起始候選（W1 (0.3, 1.2, 2.8)、W2 (15.0, 1.2, 2.8)、N1 (16.2, 11.8, 2.8)）與它們的名義地面視野，已經不適用。
- 設計稿另外新增了西側前廳、北側觀測凹室與五道遮屏。上面的區域表只是起始候選，同樣以設計稿為準。
- 設計稿提供的 pose、K、FOV、clip 都是設計估計，**所有實際覆蓋仍是 `UNKNOWN`**，依 §8.1 核對。
- 靜態地面足跡只用來建議候選鏡頭。**地面看不到，不能證明整個人看不到**：頭部或軀幹仍可能出現在畫面裡。
- 轉角不加鏡頭（D25）。

**設計盲區 `BLIND_CORNER`：**L 形 polygon，沿可走區域，不跨牆。西界是 13.7（D37；原候選 14.5）：

```text
[[13.7, 0.0], [17.4, 0.0], [17.4, 3.5], [15.0, 3.5], [15.0, 2.4], [13.7, 2.4]]
```

- 這是 private 的預期值，不供推論使用。
- 驗收依 §8.1 的流程核對頭、軀幹、腳都看不到（盲窗前後的邊界格一律人工看），不能只看 C5 的地面足跡。

### 5.2 事件 A：單人直線經過

| 項目 | 規格 |
| --- | --- |
| 人數 | 1 |
| 路線 | (1.0, 1.2) → (14.0, 1.2)，名義速度 1.3 m/s |
| 時間 | `[0, 10)` s；sample 0–49；最後一個 sample 在 9.8 s（x ≈ 13.74）；x = 14 是半開區間的終點，沒有對應的 PNG |
| 渲染鏡頭 | `CAM_W1`、`CAM_W2`、`CAM_R102_CTRL`；不呼叫 C4b，不含 `CAM_N1` |
| 目標區域 | `AREA_R101_FRONT`；名義經過時間約 4.23–6.54 s |
| 全程覆蓋 | 每個 sample 至少一台的 RGB 看得到人；依 §8.1 核對（模型先篩所有影格，人工看被標出的格與抽查格） |
| **雙鏡重疊（D27）** | 人在目標區域內時，`CAM_W1` 和 `CAM_W2` **都要拍到全身（頭頂到腳），RGB 裡看得到接地**。不能用 bbox 底邊推定腳。依 §8.1，目標窗的全部格一律人工看 |
| 近端出框風險 | 起點距 `CAM_W1` 水平只有 0.7 m，近端人物可能出框。這要在 B 包用 pose、FOV 或靜態結構解決，**不加第五台、不縮短盲窗**。設計稿 #54 @ `f2afa3f` 把 W1 移到西側前廳（設計估計）。調整後的實際覆蓋仍是 `UNKNOWN`，要在 CS-B 依 §8.1 核對 |
| 設計盲區 | 無；列在 `rgb_index.missing[]` 的缺格記 `MISSING`，已 pin 卻不存在的檔案是完整性錯誤（§2.3） |
| 對照鏡頭 | `CAM_R102_CTRL` 全程看不到人 |

### 5.3 事件 B1：兩人錯開、跨轉角

| 項目 | 規格（名義值） |
| --- | --- |
| 人數 | 2（固定；只是情境設定） |
| P1 | t = 0 從 (1.0, 1.2) 往東 → (16.2, 1.2) 轉北 → (16.2, 11.5)；25.5 m，約 19.6 s 抵達；之後停留或出場的方式寫在 private 設定 |
| P2 | **t = 11.0 s 進場（D37）**，從 (1.0, 1.2) 往東 → (8.0, 1.2)（約 16.38 s）→ 往南，約 17.31 s 穿過 `PORTAL_R101` → (8.0, −2.5)（約 19.23 s）後停留。時間是設計稿 #54 @ `f2afa3f` 的設計估計 |
| 時間 | `[0, 20)` s；sample 0–99 |
| 渲染鏡頭 | `CAM_W1`、`CAM_W2`、`CAM_N1`、`CAM_R102_CTRL` |
| 盲窗 | 驗收下限是 ≥3.2 s（D37）；4.0 s 是設計目標。設計稿 #54 @ `f2afa3f` 的設計估計是包絡盲窗 [10.2, 13.6) s（3.4 s）。這是 sample bin 的算術，**不是**人物已經看不到的證明，也不是指定的 sample 全部都盲；依 §8.1 核對 |
| 錯開（D37） | 同一台鏡頭兩人至少錯開 1.0 s，中間至少 4 個空 sample。設計稿 #54 @ `f2afa3f` 的設計估計是 W2 剛好 1.0 s／4 個空 sample（P1 最後一格 i50 → P2 第一格 i55），餘量 0。實際值依 §8.1 核對 |
| **北端 y 11–11.5** | 設計稿 #54 @ `f2afa3f` 選擇移動 `CAM_N1` 來涵蓋北端（設計估計），不列為預期離開視野。實際覆蓋仍是 `UNKNOWN`，依 §8.1 核對；不能默認唯一的缺口在轉角 |
| P2 進房後 | R101 內沒有鏡頭，但這不代表門外的鏡頭看不到門內。P2 是否可見，要由 RGB 判斷 |
| 驗收（D26、D47） | 全身不可見、任一鏡頭任一影格最多 1 人，依 §8.1 的流程核對（模型先篩所有影格，人工看被標出的格、邊界格與抽查格） |
| 負證據限制 | P2 出現的影格，對整張畫面是 `DETECTION_PRESENT`。沒偵測到特定的人，不等於整張影格 `NO_DETECTION`。D21 strict／suggestion 與可偵測性的區別照舊 |
| 關聯 | 不能用腳本把 `CAM_N1` 再出現的人認成 P1，也不能把 P2 接到 P1。沒有唯一的 RGB 證據時，保留多個候選或未關聯 |

### 5.4 事件 B2

- B2 另寫規格、另行驗收。
- B2 通過前，`AMBIGUOUS_MERGE` 不得當可用端點或位置（D8 修訂）。
- B1 不宣稱具備處理交會的能力。

## 6. Consumer API

端點（CS-Q5，**CS-A 待核准的介面設計**，都還沒實作）：
- `POST /api/candidate_cameras`
- `POST /api/synced_frames`
- `POST /api/person_layer`
- `POST /api/curve_layer`
- `POST /api/evidence_lookup`

這些端點都沿用 session／scene／run guard，不把新 payload 塞進舊的 D18 `target_reconstruction` 或舊 timeline；後端內部可以委派給舊核心。

**共通回應欄位：**
- `schema_version`；
- server 解析出的 `resolved_scope`（source、run、clock、sampling、scope、hash）；
- 完整 `provenance`（含 `gt_read: false`）、`output_sha256`；
- `identity_verdict: "UNCONFIRMED"`、`agent_used: false`。

回應不得含 session secret 或私有 locator。以下範例省略了部分欄位，標為 `NON_EXECUTABLE_EXCERPT`，不能當成可驗證的正式 payload。**數字都是示意。**

### 6.1 候選鏡頭查詢

請求（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "controlled-scene.candidate-cameras-request.v1",
  "session_ref": "sess-…",
  "scene_id": "controlled-l-corridor",
  "run_id": "ctrl-lcorr-s1-b1-5fps-v1-r001",
  "target_region_ref": "AREA_R101_FRONT",
  "target_polygon": null,
  "time_range_s": [8.0, 20.0],
  "query_intent": "ENTER_EXIT",
  "surrounding_policy_ref": "surround-policy-v1",
  "camera_ids": null,
  "page_size": 4,
  "cursor": null,
  "layout_capacity": 4
}
```

**請求規則：**
- `target_region_ref` 和 `target_polygon` 二選一。`target_polygon` 是 `{floor_id, frame_id, length_unit: "m", polygon_m}`；頂點數上限待約定。
- 時間用半開區間。`query_intent` 只有 `PASS_THROUGH`、`ENTER_EXIT`。
- 輸入的 `run_id` 只能選已註冊的 run，不能自訂 source pin。
- cursor 綁定 query、index、sampling 與 pin。
- 不接收：GT actor ID、renderer 路徑、已知的跨鏡頭身份、私有媒體路徑、事件答案。

回應（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "controlled-scene.candidate-cameras.v1",
  "status": "PARTIAL",
  "reason": "VISIBILITY_INDEX_UNAVAILABLE",
  "query_id": "cq-<由 query_sha256 導出>",
  "query_sha256": "…",
  "candidate_snapshot_sha256": "…",
  "resolved_scope": {
    "scene_id": "controlled-l-corridor", "scene_version": 1,
    "run_id": "ctrl-lcorr-s1-b1-5fps-v1-r001", "clock_id": "clock:ctrl-lcorr-s1-b1-5fps-v1-r001",
    "sampling_version": "5fps-v1", "time_range_s": [8.0, 20.0],
    "target_region_ref": "AREA_R101_FRONT", "floor_id": "FLOOR_1F", "length_unit": "m",
    "surrounding_policy_ref": "surround-policy-v1",
    "access_paths": [{"portal_id": "PORTAL_R101", "walk_ids": ["WALK_CORR_W", "WALK_R101"]}],
    "scene_static_sha256": "…", "camera_catalog_sha256": "…", "visibility_index_sha256": "…",
    "rgb_index_sha256": "…", "perception_version": null
  },
  "candidates": [
    {
      "camera_id": "CAM_W2",
      "rank": 1,
      "relation": "TARGET_FOOTPRINT_INTERSECT",
      "reason_codes": ["TARGET_FOOTPRINT_INTERSECT", "OVERLAP_AREA"],
      "related_region_refs": ["AREA_R101_FRONT", "PORTAL_R101"],
      "suggested_time_windows_s": [[8.0, 20.0]],
      "geometry_basis": {"footprint_method": "SOURCE_MESH_RAYCAST", "visibility_ref": "vis-…", "footprint_sha256": "…", "overlap_area_m2": 7.2, "detectability": "PASS"},
      "image_evidence": {"perception_status": "NOT_EVALUATED", "evaluated_frames": 0, "frame_records_read": 0, "frames_with_detection": null, "count_complete": false, "sample_frame_refs": []},
      "availability": "AVAILABLE",
      "unavailable_reason": null
    },
    {"camera_id": "CAM_W1", "rank": 2, "relation": "TARGET_FOOTPRINT_INTERSECT"},
    {"camera_id": "CAM_N1", "rank": 3, "relation": "NO_INTERSECTION"},
    {"camera_id": "CAM_R102_CTRL", "rank": 4, "relation": "UNKNOWN", "reason_codes": ["VISIBILITY_INDEX_UNAVAILABLE"], "availability": "PARTIAL"}
  ],
  "candidates_total": 4,
  "returned_count": 4,
  "next_cursor": null,
  "candidate_set_complete": false,
  "truncated": false,
  "unknown_camera_ids": ["CAM_R102_CTRL"],
  "recommended_camera_ids": ["CAM_W2", "CAM_W1", "CAM_N1", "CAM_R102_CTRL"],
  "ranking_basis": ["relation_tier", "overlap_area_m2_desc", "camera_id"],
  "stats": {"catalog_records_read": 4, "index_records_read": 3, "frame_records_read": 0, "latency_ms": {"total": 0}},
  "identity_verdict": "UNCONFIRMED",
  "agent_used": false,
  "provenance": {"producer": "candidate-cameras", "gt_read": false},
  "output_sha256": "…"
}
```

- **`relation`** 有四種：`TARGET_FOOTPRINT_INTERSECT`、`ACCESS_PATH_INTERSECT`、`NO_INTERSECTION`、`UNKNOWN`。
  - metadata 缺失時填 `UNKNOWN`，不能判成 `NO_INTERSECTION`。
  - 已知不相交的鏡頭也要保留在清單裡。
- **排序（D28）：**`relation_tier`（1 相交、2 通路、3 不相交、4 未知）→ `overlap_area_m2` 由大到小 → `camera_id`。
  - **偵測數不列入排序**，只是 `image_evidence` 中的附帶證據。
  - `perception_status` 與 `count_complete` 標明評估範圍與數量是否完整。
  - 沒有感知結果時，`frames_with_detection` 是 `null`，不是 0。
- **候選數量與完整性：**
  - `candidates_total` 是套用鏡頭目錄與篩選之後的集合大小；`returned_count` 是本頁筆數；還有下一頁時才有 `next_cursor`。
  - `candidate_set_complete` 表示整個集合都已經檢視過；分頁中的回應也可以是 complete。
  - `truncated` 只表示因為預算不足、無法完整求值。
  - metadata 未知的鏡頭列在 `unknown_camera_ids`，不省略。
- **其他：**
  - **整體狀態 `status`**（`READY`、`PARTIAL`、`UNKNOWN`）：
    - `READY`：在宣告的 scope 與 snapshot 下，候選所需的 metadata 與幾何都已完整求值。正常分頁本身不讓結果變成 `PARTIAL`；可選的感知未執行，也不會單獨讓結果變成 `PARTIAL`。
    - `PARTIAL`：部分必要的 metadata 或幾何缺失，或預算不足使部分結果無法求值。保留可用的候選，並附上 `unknown_camera_ids`、`truncated` 與 `reason`。上面的範例因為 `CAM_R102_CTRL` 的可見範圍索引缺失，所以是 `PARTIAL`。
    - `UNKNOWN`：無法提供有意義的候選結果。
    - **必要輸入缺失時，不得回 `READY`。**各狀態都不得把未知當成不相交，也不得把空結果解讀成「沒有人經過」。
  - 足跡或 suggestion 相交只是候選理由，不自動成為負證據。
  - 查詢在**沒有任何接地估計或局部追蹤**時也必須能回答（CS-Q12）。
  - `stats.latency_ms` 不計入 hash。

### 6.2 同步影格

請求：`{schema_version, session_ref, scene_id, run_id, t_s: 12.47, camera_ids: [最多 8 台]}`。單一 run、單一 clock、單一時間點。

回應（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "controlled-scene.synced-frames.v1",
  "t_s": 12.47,
  "clock_id": "clock:ctrl-lcorr-s1-b1-5fps-v1-r001",
  "sampling_version": "5fps-v1",
  "frame_rule": "LATEST_AT_OR_BEFORE_EXPECTED_GRID",
  "expected_frame_index": 62,
  "expected_timestamp_s": 12.4,
  "sample_age_s": 0.07,
  "tiles": [
    {"camera_id": "CAM_W2", "status": "READY", "frame_ref": "fr-…-CAM_W2-000062", "timestamp_s": 12.4, "clock_error_s": 0.0, "file_sha256": "…"},
    {"camera_id": "CAM_W1", "status": "READY", "frame_ref": "fr-…-CAM_W1-000062", "timestamp_s": 12.4, "clock_error_s": 0.0, "file_sha256": "…"},
    {"camera_id": "CAM_N1", "status": "MISSING", "frame_ref": null, "reason": "RGB_RECORD_ABSENT"},
    {"camera_id": "CAM_R102_CTRL", "status": "UNKNOWN", "frame_ref": null, "reason": "RUN_BINDING_UNAVAILABLE"}
  ]
}
```

- **選格規則：**依 sampling 的有理數 grid 算出預期的 index。該 sample 列在 `rgb_index.missing[]` 就回 `MISSING`，不回退到較早的可用影格；已 pin 卻不存在的檔案是完整性錯誤（§2.3）。
- **時間欄位：**`sample_age_s = t − timestamp_s` 不是同步誤差；同步誤差另外記在 `clock_error_s`，容差是 `abs(clock_error_s) ≤ 0.001 s`（D41）。邊界與容差寫在設定檔，不偷偷加 epsilon。
- **tile 狀態：**`READY`、`MISSING`、`OUT_OF_RANGE`、`UNKNOWN`。hash、source 或 pin 不符時是完整性錯誤，整個請求 fail closed（§2.3），不會出現在 tile 裡。
- **與 C5 的關係：**這不是 C5 `frame_retrieval`；C5 最多 64 張的建議影格，不能當同步影片的完整影格。
- **鏡頭數上限：**每次最多 8 台；超過 8 台時用候選目錄分頁（CS-Q13）。

### 6.3 3D 人物與區間圖層

回應（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "controlled-scene.person-layer.v1",
  "time_range_s": [12.0, 13.0],
  "estimates": [
    {
      "estimate_ref": "pe-…",
      "observation_ref": "obs-…-CAM_W1-000062-c0",
      "camera_id": "CAM_W1",
      "frame_ref": "fr-…-CAM_W1-000062",
      "rgb_file_sha256": "…",
      "calibration_sha256": "…",
      "floor_id": "FLOOR_1F",
      "timestamp_s": 12.4,
      "local_track_ref": null,
      "ground_estimate": {
        "status": "READY",
        "estimate_kind": "SEGMENT",
        "basis": "FOOT_RAY_PIXEL_BAND",
        "segment": {"near_m": [6.1, 1.0, 0.0], "far_m": [6.9, 1.3, 0.0], "raw_near_m": [6.0, 1.0, 0.0], "raw_far_m": [7.0, 1.3, 0.0], "length_m": 0.85},
        "constraints_applied": [],
        "contact_quality": {"status": "PASS"},
        "evidence_state": "PROJECTED_OBSERVATION",
        "output_sha256": "…"
      },
      "bbox_height_px": 214,
      "heading": {"state": "UNKNOWN", "reason": "LOCAL_TRACK_UNAVAILABLE", "direction_xy": null},
      "display": {"humanoid_range_allowed": true, "display_config_sha256": "…"},
      "identity_verdict": "UNCONFIRMED",
      "physical_verdict": "UNKNOWN"
    }
  ]
}
```

- **區間格式：**POINT 和 SEGMENT 都使用[區間觀測 v1 §3](OFFICE_INTERVAL_OBSERVATION_V1.md) 的完整 schema。
  - SEGMENT 的欄位是 `near_m`、`far_m`、`raw_near_m`、`raw_far_m`，加上 `height_prior` 等。
  - 原始觀測的 `MISSING` 或 `null` 不因 sibling estimate 是 READY 而被改寫。
- **方向：**沒有局部軌跡，或方向有歧義時，`heading` 是 `UNKNOWN`。有方向時是推論，必須帶 §2.4 的 `uncertainty`（`extent_kind: ANGLE_DEG`）。不得拿區間的中點差分來假裝有方向。
- **display：**
  - display 是 UI 設定，有自己的 config hash，不從 `persons.sim.json` 取尺寸或姿態。
  - 人體 prior 要在評估前針對每個 run 宣告，套用到所有 RGB 元件，不依 actor 選。
  - D5 的常數不是新場景已通過的門檻。
  - 長區間不在中點放人形。

#### 6.3.1 接地區間的組成條件 `composed_ground`（v1.1 草案，D44）

每一筆估計除了原本的 `ground_estimate`，再加一個 `composed_ground`。
- **`ground_estimate`：**C4a 的單格投影，`PROJECTED_OBSERVATION`，照區間觀測 v1，內容不變，保留作追溯。
- **`composed_ground`：**把下列條件組合後得到的地板範圍，**`evidence_state` 一律是推論**。

本草案用 `INFERRED_CONSTRAINED` 這個新值；名稱待 Codex 確認（CS-Q15）。現有的 `INFERRED_INTERPOLATION`（影格間）、`INFERRED_HYPOTHESIS`（盲區）語意不同，所以不沿用。

範例（`NON_EXECUTABLE_EXCERPT`；腳被已知障礙物遮住的一格）：

```json
{
  "composed_ground": {
    "schema_version": "controlled-scene.composed-ground.v1",
    "status": "READY",
    "reason": null,
    "evidence_state": "INFERRED_CONSTRAINED",
    "foot_status": "OCCLUDED_BY_STATIC",
    "geometry": {
      "kind": "SEGMENT",
      "floor_id": "FLOOR_1F",
      "near_m": [10.62, 0.95, 0.0],
      "far_m": [11.10, 0.88, 0.0],
      "length_m": 0.49,
      "polygon_m": null,
      "view_ray_ref": "obs-…-c0#head_ray"
    },
    "constraints_used": [
      {"kind": "track_height", "source_ref": "lt-…#track_height_estimate", "source_sha256": "…", "values": {"lower_m": 1.68, "upper_m": 1.74}},
      {"kind": "occlusion_near", "source_ref": "OBSTACLE_SCREEN_W", "source_sha256": "<geometry_sha256>", "values": {"bound_m": [10.62, 0.95, 0.0]}},
      {"kind": "lowest_visible_far", "source_ref": "obs-…-c0", "source_sha256": "<rgb file_sha256>", "values": {"pixel_uv": [512, 401], "bound_m": [11.40, 0.84, 0.0]}},
      {"kind": "speed", "source_ref": "obs-…-000047-c0", "source_sha256": "…", "values": {"anchor_timestamp_s": 9.4, "dt_s": 0.2, "v_max_mps": "CS-Q15", "speed_config_sha256": "…"}}
    ],
    "constraints_unavailable": [
      {"kind": "prior", "reason": "SUPERSEDED_BY_TRACK_HEIGHT"}
    ],
    "uncertainty": {"extent_kind": "LENGTH_M", "extent_value": 0.49, "constraints_used": ["track_height", "occlusion_near", "lowest_visible_far", "speed"], "quality_grade": "MEDIUM", "quality_rule_ref": "quality-grade-rule-v1", "quality_rule_sha256": "…"},
    "output_sha256": "…"
  }
}
```

**五種條件 `kind`：**名稱固定為 `prior`、`track_height`、`occlusion_near`、`lowest_visible_far`、`speed`。

| `kind` | 何時使用 | 給出什麼 | 來源 ref 與 hash |
| --- | --- | --- | --- |
| `prior` | 沒有可用的 `track_height` 時 | 頭部射線上的身高範圍：用公開人體先驗，D42 的 1.65–1.75 m | 人體 prior 設定檔的 ref 與 `content_sha256`（per-run 預先宣告，所有人共用） |
| `track_height` | 腳被遮住、而且同一條 track 有 `READY` 的身高估計時（§3.12） | 頭部射線上的身高範圍改用 `[lower_m, upper_m]`，取代先驗 | `local_track_ref` 與 `track_height_estimate.output_sha256` |
| `occlusion_near` | 腳點候選的視線穿過已核准的靜態障礙物時 | 近端界：腳不可能在障礙物前面或裡面 | 障礙物 ID 與 `geometry_sha256`、`calibration_sha256` |
| `lowest_visible_far` | 有任何看得到的身體像素時 | 遠端界：最低可見身體點的射線落到地板的位置。身體點在地板以上，所以人的接地位置不會比這一點更遠 | `observation_ref` 與 RGB `file_sha256`（若用偵測器遮罩，記錄偵測器版本與 config hash） |
| `speed` | 同一條 track 有更早的高信心位置時 | 以那個位置為中心、半徑 `v_max × Δt`（加上錨點自身的不確定度）的範圍，與線段取交集 | 錨點 `observation_ref` 與其 `composed_ground.output_sha256`、`speed_config_sha256` |

**遮擋邊界的行為：**
1. 對每個腳點候選，從相機中心到該地板點連一條視線，檢查是否穿過 `scene_static` 中 `allowed_purposes` 含 `OCCLUSION`、而且 `approval_status: APPROVED` 的幾何。
   - 有穿過：`foot_status: OCCLUDED_BY_STATIC`，這個候選**不能當腳點用**。
   - 用途未核准或幾何 `UNKNOWN` 的物件，不能拿來判定遮擋，也不能給近端界；該處記為 `UNKNOWN`。
2. 腳被已知障礙物遮住時，由障礙物給出近端界 `occlusion_near`。
3. 看得到的最低身體點，給出遠端界 `lowest_visible_far`。
4. 判斷腳是否可見時，可以再加上只讀 RGB 的姿態模型給出的腳踝信心值。
   - 記錄模型的版本與 config hash；門檻待約定（CS-Q15）。
   - 靜態遮擋檢查一律要做：檢查結果是被遮住時，即使模型說腳踝可見，也不得當腳點用。
   - 模型只能讓判斷更保守，不能推翻靜態遮擋檢查。
5. 不讀 GT、renderer 深度、visibility 或遮罩（§7）。

**組合規則：**
- **計算順序：**頭部射線的身高範圍（`track_height` 或 `prior`）先給出一段沿視線方向的地板線段；`occlusion_near`、`lowest_visible_far` 再分別收緊近端與遠端；最後與 `speed` 範圍取交集。
- **輸出：**沿視線方向的地板區間（`SEGMENT`），或在納入像素敏感度時成為窄帶（`POLYGON`）。
  - 不收成中點。
  - 不改寫原 `ground_estimate`。
- **`speed` 的錨點：**
  - 只取**同一條局部軌跡**內、時間在前的高信心位置；不得取其他 track 或其他鏡頭的位置，那等於先做了關聯。
  - 錨點的最大時間差與「高信心」的條件待約定（CS-Q15）。
  - 速度上限是公開設定，不讀 `persons.sim.json` 的 `speed_mps`。
- **交集為空：**`status: UNKNOWN`、`reason: CONSTRAINTS_INCONSISTENT`，並列出互相矛盾的條件。不得悄悄拿掉某個條件，讓結果變成非空。
- **所有條件都失效：**例如看不到頭，也沒有任何可見身體點，無法形成沿視線的範圍。此時 `status: UNKNOWN`、`reason: ALL_CONSTRAINTS_UNAVAILABLE`、`geometry: null`。
- **紀錄完整：**每一格都要在 `constraints_used` 列出實際用到的條件，並在 `constraints_unavailable` 列出沒用到的條件與原因（例如 `TRACK_BROKEN`、`NO_ANCHOR`、`SUPERSEDED_BY_TRACK_HEIGHT`、`FOOT_VISIBLE`）。
- **腳看得到時：**腳點候選通過遮擋檢查、而且 `contact_quality` 是 `PASS` 時，`foot_status: VISIBLE`。範圍來自腳點的像素帶，`prior` 與 `track_height` 列為未使用（`FOOT_VISIBLE`）。`speed` 仍可收緊；這時的輸出也是推論。
- **身高的用途：**身高只用在這一格的接地組合，不輸出成人物屬性（§3.12）。
- **前端：**`composed_ground` 依推論樣式畫；原 `ground_estimate` 保留為可切換的追溯圖層。這和 UX 草圖 §5.1「區間用觀測色實線」不同，前端畫法待 Codex 確認 v1.1 後一併修訂（CS-Q15）。

### 6.4 曲線圖層

回應（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "controlled-scene.curve-layer.v1",
  "curves": [
    {
      "curve_ref": "cv-…",
      "candidate_ref": null,
      "local_track_refs": ["lt-…"],
      "segments": [
        {"kind": "OBSERVED", "evidence_state": "PROJECTED_OBSERVATION", "sample_timestamps_s": [9.8, 10.0, 10.2], "support_refs": ["obs-…-000049-c0", "obs-…-000050-c0", "obs-…-000051-c0"], "geometry": {"type": "INTERVAL_SERIES"}},
        {"kind": "INFERRED_CONNECTOR", "evidence_state": "INFERRED_INTERPOLATION", "t_s": [10.0, 10.2], "support_refs": ["obs-…-000050-c0", "obs-…-000051-c0"], "local_track_ref": "lt-…", "geometry": {"type": "RIBBON"},
         "uncertainty": {"extent_kind": "AREA_M2", "extent_value": 0.11, "constraints_used": ["endpoint_estimates"], "quality_grade": "MEDIUM", "quality_rule_ref": "quality-grade-rule-v1", "quality_rule_sha256": "…"}},
        {"kind": "BLIND_HYPOTHESIS", "evidence_state": "INFERRED_HYPOTHESIS", "t_s": [10.4, 13.6], "hypothesis_response_sha256": "…", "hypothesis_refs": ["hyp-1"], "unassociated_baseline": true, "region_band": true,
         "uncertainty": {"extent_kind": "AREA_M2", "extent_value": 18.5, "per_sample_ref": "<K1 reachable_regions[].area_m2>", "constraints_used": ["endpoint_estimates", "k1_reachability", "speed"], "quality_grade": "LOW", "quality_rule_ref": "quality-grade-rule-v1", "quality_rule_sha256": "…"}},
        {"kind": "MISSING_GAP", "evidence_state": "MISSING", "t_s": [15.2, 15.4], "reason": "RGB_RECORD_ABSENT", "geometry": null}
      ],
      "result_sha256": "…",
      "map_sha256": "…",
      "policy_pins": {"body_policy_sha256": "…", "speed_config_sha256": "…"},
      "association": {"state": "INFERRED_HYPOTHESIS", "identity_verdict": "UNCONFIRMED"}
    }
  ],
  "time_highlight": {"t_s": 12.47, "window_s": 1.0},
  "kinds_reserved": ["PREDICTION"]
}
```

- **OBSERVED：**只存離散時間點上的區間序列。任何跨越 sample 的幾何都屬於 `INFERRED_CONNECTOR`。
- **連接：**只有同一條合法局部軌跡的兩端才能連接；連接一律畫虛線。單筆的橫向區間可以畫實線。
- **BLIND_HYPOTHESIS：**保留 K1 的多解與未關聯基線，不指定 actor。純時間高亮不會把假設切片改成內插。
- **MISSING_GAP：**原因不會是 hash 不符，因為完整性錯誤會中止載入。
- **B1：**不能把兩個人連成已確認身份。
- **不確定度（D45）：**`INFERRED_CONNECTOR`、`BLIND_HYPOTHESIS`、`PREDICTION` 都必須帶 §2.4 的 `uncertainty`，缺少時是完整性錯誤。`OBSERVED` 與 `MISSING_GAP` 不帶。
- **PREDICTION：**留給 D 包。

### 6.5 點擊回溯證據

請求：`{schema_version, session_ref, pick: {layer: "curve", ref: "cv-…", result_sha256: "…", segment_index: 0, t_click_s: 10.27}}`

回應（`NON_EXECUTABLE_EXCERPT`）：

```json
{
  "schema_version": "controlled-scene.evidence-lookup.v1",
  "status": "READY",
  "nearest_support": {
    "observation_ref": "obs-…-CAM_W2-000051-c0",
    "camera_id": "CAM_W2",
    "frame_ref": "fr-…-CAM_W2-000051",
    "timestamp_s": 10.2,
    "support_offset_s": -0.07,
    "bbox_px": [412, 188, 470, 402]
  },
  "other_supports": ["obs-…-000050-c0", "obs-…-000052-c0"],
  "relation": "SUPPORTS_OBSERVED_SEGMENT",
  "jump": {"t_s": 10.2, "camera_ids": ["CAM_W2"]}
}
```

- server 會核對每個 ref 的 scene、run、clock 與 `result_sha256`；`segment_index` 指向的是那個版本的結果。
- `support_offset_s = timestamp_s − t_click_s`，和播放器的 `sample_age_s` 是不同的欄位。
- 距離相等時，依序以 `timestamp_s`、`camera_id`、`observation_ref` 決定，確保結果穩定。

| 點到的東西 | `relation` | 跳轉 |
| --- | --- | --- |
| 觀測區間或點 | `IS_OBSERVATION` | 跳到該觀測自己的影格 |
| `OBSERVED` 段 | `SUPPORTS_OBSERVED_SEGMENT` | 跳到時間最近的支持觀測自己的時間 |
| `INFERRED_CONNECTOR` | `ENDPOINTS_OF_CONNECTOR` | 跳到較近的一端；另一端列在 `other_supports` |
| `BLIND_HYPOTHESIS` | `HYPOTHESIS_ENDPOINTS_AND_NEGATIVE_EVIDENCE` | 不自動跳轉；列出兩端觀測與負證據影格 |
| `MISSING_GAP` | `NO_SUPPORT` | 不跳轉 |

不會自動補上 GT 或鄰近 run 的資料。

## 7. GT 隔離邊界

依 D26。

| 資料 | 正式系統（檢索、排序、關聯、定位、預測、播放、runtime readiness） | CS-B 場景驗收 | 凍結後評估 |
| --- | --- | --- | --- |
| safe RGB（經 hash 驗證） | 可讀 | 可讀（模型先篩、人工看重點格，§8.1） | 可讀 |
| 已核准用途的靜態幾何、校正、只用靜態資料建的索引（D1） | 可讀 | 可讀 | 可讀 |
| `event_*.query.json` | 只用來預填 UI | 可讀 | 可讀 |
| `runtime_profile.json` | 可讀（只有技術期望值） | 可讀 | 可讀 |
| `event_*.validation.json`（覆蓋、盲窗、錯開） | **禁止** | 可讀，作為 §8.1 交叉比對與人工核對的清單 | 可讀 |
| `production_manifest.json`、generator 設定、seed | **禁止** | 可讀（核對產製完整性） | 可讀 |
| `persons.sim.json`、actor、路線 | **禁止** | 可讀：產製路線＋名義身高 1.70 m 只用作 §8.1 的投影比較基準（D54 A2） | 可讀 |
| GT 軌跡、mask、visibility、depth | **禁止** | **禁止**（D26） | 輸出凍結且 hash 驗證後才可讀 |

- **CS-B 的做法（D26，D47 修訂）：**用 RGB 核對覆蓋與 B1 錯開，加上靜態標記、校正核對與產製完整性。影像核對依 §8.1：模型先篩，人工看重點格。
  - 產製端可以依腳本生成 RGB，但腳本與 GT 不能當正式系統的輸入。
  - GT 與 mask 的數值評估延到輸出凍結後。若要提前讀 GT，需要使用者另外改訂邊界。
- **外部模型 API（D47，v1.1 草案）：**之後會改用 OpenAI API 的視覺模型做實際測試。
  - **只能送 safe RGB：**safe bundle 中 hash 驗證過的 PNG，以及不含 private 內容的 prompt。
  - **禁止送出：**GT、mask、depth、visibility、`private_evaluation/` 的任何檔案、`persons.sim.json`、`event_*.validation.json`、作者路線、事件腳本、本機路徑。prompt 也不得寫入這些內容，例如「這一格應該有幾個人」。
  - **API key：**由使用者自行設定；Agent 不經手、不讀取、不寫入檔案或紀錄。
  - **每次呼叫都要記錄：**模型名稱、版本、完整 prompt、送出影像的 `file_sha256`、回應內容與 hash、費用、時間。紀錄不含 API key。
  - **模型輸出的地位：**只是輔助證據，不能單獨判定合格（§8.1）。
  - **授權：**實際接上 API 之前，要使用者另外授權。[DEVELOPMENT_RULES](../DEVELOPMENT_RULES.md) 目前寫「不串接外部模型 API」，接上前要由規則的負責人修訂或列出例外，本契約不改規則。
- **投影比較基準（D54 A2）：**
  - CS-B 驗收端可以讀產製路線，加上名義身高 1.70 m，算出每格的預期投影，和 RGB 模型結果比較。
  - **推論與正式服務都不能讀產製路線**，也不能讀這個比較的結果。
  - 比較的結果只用來標出要人工看的格，不回填任何推論輸出，也不進排序、關聯或定位。
- **靜態索引：**靜態 raycast 只讀不含人物的靜態場景。
- **接地組成條件可讀的資料（v1.1 草案，D44）：**

  | 條件 | 可讀 | 禁止 |
  | --- | --- | --- |
  | `occlusion_near` | `scene_static` 中 `allowed_purposes` 含 `OCCLUSION`、`approval_status: APPROVED` 的靜態幾何；光學校正 | GT、renderer 深度、visibility、mask；含人物的場景；未核准用途或 `UNKNOWN` 的幾何 |
  | `lowest_visible_far` | safe RGB；只讀 RGB 的偵測器輸出（含它的遮罩）；校正與地板 | renderer mask、GT |
  | `track_height` | 同一條局部軌跡內的 RGB 觀測（頭與腳像素）、校正、地板 | `persons.sim.json` 的 `height_m`、D42 的逐人產製數值、GT；其他 track 或其他鏡頭的資料 |
  | `prior` | 預先宣告、所有人共用的公開人體先驗設定檔（D42 範圍 1.65–1.75 m） | 依 actor 選的先驗 |
  | `speed` | 公開速度設定；同一條局部軌跡中更早的 `composed_ground` | `persons.sim.json` 的 `speed_mps`、路線、事件腳本；其他 track 的位置 |

- **路徑防護：**
  - 採用遞迴 allowlist 與 realpath containment，拒絕 symlink 和路徑穿越；不只靠敏感欄位黑名單或目錄名稱。
  - 先做 schema 與路徑檢查，再做 IO，不能在開啟 GT 之後才回錯。
  - 錯誤訊息不得回顯私有路徑。
- **錯誤碼（CS-Q6，CS-A 待核准的介面設計）：**

  | 錯誤碼 | 狀況 |
  | --- | --- |
  | `FORBIDDEN_INFERENCE_INPUT`（HTTP 422） | 請求帶了禁用欄位或額外欄位 |
  | `FORBIDDEN_DATA_SCOPE`（HTTP 403） | server 拒絕 private 或 GT locator |
  | `DataIntegrityError`（附具體原因） | sealed 檔案、source 或 hash 錯誤；該 run 不可用 |

- **預填與手動查詢的比較：**在同一個正規化 query、snapshot、page、layout 與 session scope 下，比較 canonical 語意 payload 與 `output_sha256`。
  - latency 等計時欄位不比較。
  - `query_id` 由 hash 導出，不隨機產生。
  - 不得因為查詢來自預填或手動而產生不同的排序。
- **不做 GT 圖層（D46）：**
  - 正式播放沒有 GT fallback；工作台也不做 GT 對照圖層或 GT 回放面板。
  - 3D 人物只顯示從 2D 重現的結果，鏡頭看得到的區段也一樣。
  - GT 只用在輸出凍結後的離線評估工具，結果以報告與圖表呈現。
  - v1 原本允許的「凍結後 `EVALUATION` 面板」由 D46 取消。

## 8. 驗收表

三欄分開驗收，不能互相代替。
- 已定案的數值（D37、D38、D41、D47、D54）照決定；其餘數值門檻待約定（CS-Q9）。全部寫進版本化設定檔。
- 還沒執行的項目一律標 `NOT_EVALUATED`。
- validator 的 schema 零錯誤，不等於幾何或品質通過。

| 項目 | CS-B 場景符合條件（依 §8.1 的影像驗收＋靜態／校正／產製完整性；不讀 GT） | 影像估計正確（正式系統，不讀 GT） | 凍結後評估（可讀 GT／mask） |
| --- | --- | --- | --- |
| 座標與尺度 | 單位 m；支撐面與相機 pose 互相一致 | 接地估計使用同一支撐面與尺度 | — |
| 標記 | §3 必填欄位齊全；ID 唯一；跨檔引用有效；用途核准狀態明確 | — | — |
| Walkable | C7 mesh 檢查與 K7 靜態檢查的報告已產生；不一致的範圍 fail closed | K1 只讀已核准的 walkable | 路線不違反地圖 |
| 攝影機 | 完整校正（§3.7）；K 對應 PNG；run binding 與 clock 完整 | 同步：`abs(clock_error_s) ≤ 0.001 s`（D41） | — |
| 覆蓋與重疊（D27） | 依 §8.1 核對（D27 目標窗一律人工看）：事件 A 全程至少一台可見；目標區域內 W1、W2 都拍到全身與接地 | 候選查詢可重現；分頁不漏不重；無靜默截斷；沒有定位也能查 | 候選召回（待約定） |
| 設計盲區 | 依 §8.1 核對（盲窗前後的邊界格一律人工看）：`BLIND_CORNER` 時段頭、軀幹、腳都看不到；北端 y 11–11.5 照 §5.3 處理 | 盲區不畫位置 | K1 範圍帶涵蓋率（待約定） |
| B1 錯開 | 依 §8.1 核對任一鏡頭任一影格最多 1 人 | 兩人沒被連成同一條曲線；同一鏡頭只有一人不代表身份已關聯 | 關聯正確率（待約定） |
| 人物 | 產製端確認接地動畫與淨空設定已套用；body policy 是預先宣告的設定 | — | 接地區間涵蓋率與長度（待約定）；淨空實際通過另外證明，未使用的範圍為 `UNKNOWN` |
| 缺影格與完整性 | 列出所有非設計的缺檔，並寫入 `rgb_index.missing[]`；expected grid 的每個 sample 都在 `records[]` 或 `missing[]` 其中一處 | `missing[]` 中的 sample 顯示 `MISSING`；已 pin 卻不存在的檔案，以及 index 不完整，都是 fatal 的完整性錯誤 | — |
| 內插 | — | 只有內插算出的幾何標 `INFERRED_INTERPOLATION`；假設切片維持 `INFERRED_HYPOTHESIS` | — |
| 不確定度（v1.1 草案，D45） | — | 每個 `READY` 的推論項目都帶完整的 `uncertainty`，缺少時 fail closed；UI 顯示讀數與圖例 | 凍結後才報與 GT 比較的誤差；凍結前只報設計估計或 `extent_value` |
| GT 圖層（D46） | — | 工作台沒有 GT 對照圖層或回放面板 | — |
| 接地組成（v1.1 草案） | 已核准 `OCCLUSION` 用途的靜態幾何清單齊全 | 每格 `composed_ground` 都記錄用到與未用到的條件及其 ref 與 hash；條件交集為空或全部失效時回 `UNKNOWN`；身高不跨 track，也不出現在跨鏡頭候選的 payload | 接地區間涵蓋率與長度（待約定），分別統計各條件組合 |
| 點擊回溯 | — | 每個可點元素都回到支持證據或 `NO_SUPPORT`；距離相等時結果穩定 | — |
| GT 隔離 | — | 注入禁用目錄或欄位時拒絕；預填與手動語意相同；`gt_read: false` | GT 只在凍結並驗證 hash 後載入 |
| 取樣版本 | 5 fps 與 10 Hz 是不同的 run 與 hash；5 fps 封存後不變 | 回應帶 `sampling_version` | — |
| CS-B 影像驗收（D47、D54） | 依 §8.1：模型先篩所有影格（A1 標記條件）；以產製路線＋1.70 m 的投影交叉比對（A2，容差 20%、中心偏移 0.25 倍人高）；人工看被標出的格、D27 目標窗、邊界格（A4：盲窗前後各 2 格，另加偵測結果切換處前後各 1 格）與雜湊排序抽樣（A3，每台 `ceil(10%)`）；未看的格標 `MODEL_SCREENED_NOT_HUMAN_REVIEWED` | — | — |
| 原資產 | 舊校園、Office 的 `.blend`、RGB、GT 都不變 | — | — |
| 綠球 | — | 不出現綠球或球狀替身 | — |

### 8.1 CS-B 影像驗收流程（D47，v1.1 草案）

1. **模型先篩（D54 A1）：**
   - 只讀 RGB 的偵測器先跑完所有影格（A＋B1 共 550 張）。
   - 使用 D47 專用的偵測設定，不沿用舊 `perception.py` 為小目標設的常數（#76 §2.3 C8）。設定在渲染前封存並記錄 hash。
   - 以下任一情況就標給人工（保守多標）：
     - D27 目標窗缺人；
     - 同一格 ≥2 人；
     - 人高 <112 px；
     - 邊距 <16 px；
     - 觸邊；
     - 應該有人卻沒有人（全程覆蓋）；
     - 盲窗內有人；
     - B1 同一格 ≥2 人；
     - `merged` 或歧義；
     - 與投影不一致（第 2 步）。
2. **交叉比對（D54 A2）：**
   - 比對基準是產製路線＋名義身高 1.70 m 的投影，只供 CS-B 驗收，不進推論（§7）。
   - 以下任一情況就標出：
     - 存在性不同；
     - 人高差 >20%；
     - 中心偏移 >0.25 倍人高。
   - 靜態遮擋檢查（§6.3.1）說腳被遮住、模型卻說腳看得到的格，也一律標出。
3. **人工只看三類：**
   - 第 1、2 步標出的格。
   - **D27 目標窗的全部格，以及邊界格（D54 A4）：**
     - 盲窗前後各 2 格，四台共 16 格；
     - 偵測結果切換處前後各 1 格。
   - **抽樣（D54 A3）：**每台鏡頭中沒被標出的格，依 `SHA-256(seed, run_id, camera_id, index)` 排序，取前 `ceil(10%)` 格。seed 要在渲染前寫進 repo；抽中的清單要記錄。
4. **以人工為準：**模型和人工不一致時，以人工判定為準，並記錄差異。
5. **紀錄：**
   - 每格記錄：模型版本與 config hash、模型結果、是否被標出及原因、是否由人工檢查、人工結果、差異。
   - 沒有經過人工檢查的格，標 `MODEL_SCREENED_NOT_HUMAN_REVIEWED`；不得寫成人工已確認。
6. **之後換成外部視覺模型：**照 §7 的外部 API 邊界辦理。模型輸出仍只是輔助證據，不能單獨判定合格。

這個流程不讀 GT（D26）。各項數值依據如下，都不得在看過 RGB 或 GT 後調整（CS-Q9）：
- 10% 抽查：D47；
- 112 px、16 px：D38；
- 標記條件、20% 容差、雜湊抽樣、邊界格：D54。

## 9. 待決問題

v1 共 14 題（CS-Q1–CS-Q14）；v1.1 草案新增 CS-Q15。

| 編號 | 問題 | 狀態 |
| --- | --- | --- |
| CS-Q1 | 校正格式 | **CS-A 待核准的介面設計**：投影核心沿用；新 JSON 透過明確 adapter 轉換；光學校正與 run clock 分開（§3.7） |
| CS-Q2 | 資料根 | **CS-A 待核准的介面設計**：`data/pilot/controlled_scene_v1`，被 Git 忽略；只存一份 RGB；新的 allowlist 與 loader adapter 之後實作（§4） |
| CS-Q3 | 事件 A 重疊的可見部位 | **已關閉（D27）**：雙鏡全身＋接地 |
| CS-Q4 | 偵測數是否列入排序 | **已關閉（D28）**：不列入；只當附帶證據 |
| CS-Q5 | 端點 | **CS-A 待核准的介面設計**：五個新端點（§6） |
| CS-Q6 | GT 誤入的錯誤碼 | **CS-A 待核准的介面設計**：`FORBIDDEN_INFERENCE_INPUT`、`FORBIDDEN_DATA_SCOPE`、`DataIntegrityError`（§7） |
| CS-Q7 | C5 上限 | **CS-A 待核准的介面設計**：舊限制（4 鏡頭、20 s、64 張建議、512 筆、5 s）保留，不為新 Demo 全域放大。5 fps 的 B1 400 筆在 512 內，但 64 張建議不等於 400 張都能回傳。10 Hz 的 800 筆要用綁定穩定 snapshot 的半開時間分窗或鏡頭分批，跨窗去除重複的 frame key 並彙總完整性；整體預算待約定，不能用無限分頁繞過上限。同步播放走 §6.2，不占用 C5 的建議上限 |
| CS-Q8 | 多組端點 | **CS-A 待核准的介面設計**：新 adapter，舊 D18 guard 原樣保留給舊 run。事件 A 不呼叫。B1 由 RGB 局部軌跡的結束與開始產生候選端點組，附兩端 ref、hash、clock、eligibility、`candidate_ref`、未關聯基線、多解與整條路徑的時間與速度檢查。別人的觀測不再全域阻擋；同一候選若有中間支持就分段。配對不讀 actor 或盲窗；沒有合法端點就回 `UNKNOWN`。Claude 起草純候選介面，Codex 接 adapter |
| CS-Q9 | 所有數值門檻 | **OPEN**（已定案的部分：同步容差 1 ms 為 D41；B1 錯開為 D37；D47 的標記、投影容差、抽樣與邊界格為 D54；其餘仍 OPEN）：同步誤差（與 sample age 分開）、人形區間門檻、通路距離、B1 間隔、召回與涵蓋率、polygon 頂點數、tracking 的缺口、速度與方向條件、批次預算。在生成或凍結前約定；會影響鏡頭或場景設計的門檻，要在生成前定。不看新 GT 之後倒推調整 |
| CS-Q10 | 局部軌跡與關聯的分工 | **CS-A 待核准的介面設計**：Codex 主責 RGB-only 局部追蹤與感知 wrapper；Claude 主責可分離的純關聯候選介面與演算法，Codex 整合（§3.12） |
| CS-Q11 | 磁碟 | 起跑保護 12 GiB、停止保護 8 GiB、峰值額度 1.5 GiB 已由 D41 定案，取代原本「12 GiB 只是既有建議」的寫法。每次授權渲染前要重查可用空間 |
| CS-Q12 | 沒有定位時的候選查詢 | **CS-A 待核准的介面設計**：`TimeFrameIndex` 本身只需要 metadata；依賴 `_ground_estimates` 的是 `FrameRetrievalIndex` 的初始化與 provenance 抽取。新的候選 loader 從 safe catalog 與 run config 取 provenance，感知與定位只是可選的補充，不為了湊 provenance 造假估計 |
| CS-Q13 | 8 格 | **CS-A 待核准的介面設計**：8 格與超過 8 台先用 UI fixture 驗收，真實場景只有 3 或 4 台。`synced_frames` 每次最多 8 台；超過 8 台用目錄分頁並保留全集合。不並行呼叫兩次舊 timeline 再假裝是同一個 snapshot |
| CS-Q14 | wrapper 寫死值 | **CS-A 待核准的介面設計**：preset、launcher、rehearsal-check 改讀 safe manifest 的 `sampling`、`duration`、`camera_ids`、`rgb_index`，以及 `runtime_profile` 的技術期望值。**不讀** private 的情境驗收表 |
| CS-Q15 | 接地組成條件的數值與命名（v1.1 草案，D44） | **OPEN**，在生成或凍結前約定，不看新 GT 之後倒推調整：<br>（1）速度上限 `v_max`，建議 2 m/s；<br>（2）軌跡身高需要的最少高信心格數，以及「高信心」的條件（接地品質、邊距、人高像素）；<br>（3）身高不確定度的計算方法；<br>（4）`temporal_scope` 用 `WHOLE_TRACK` 或 `CAUSAL`；<br>（5）`speed` 錨點的最大時間差與錨點條件；<br>（6）`INFERRED_CONSTRAINED` 的命名；<br>（7）`SEGMENT` 與 `POLYGON` 的選用規則；<br>（8）前端畫法；<br>（9）`quality_grade` 的分級門檻（D45）；<br>（10）姿態模型腳踝信心值的門檻與模型版本；<br>（11）曲線用的 `constraints_used` 新種類（`endpoint_estimates`、`k1_reachability`）的命名。<br>其中（6）–（8）、（11）屬介面設計，需要 Codex 確認 |

## 10. 對照紀錄

### 10.1 Codex CS-A 審查「修改」項目的處置

| Codex 審查條目 | 本版處置 |
| --- | --- |
| 標頭：依據改固定 SHA；舊 Office 條文不隨引用移入 | §0.1 |
| §1 模擬／評估資料 | §1、§7 |
| §2 影格對應：零起算 sample index、private Blender 對應、`duration_s` 與 `last_timestamp_s` 分開 | §2 |
| §2 Hash：`file` 與 `content` 分名、序列化設定、幾何 hash 規則 | §2.1 |
| §2.1 內插：同一軌跡、RGB 判斷缺口、假設切片不改標 | §2.2 |
| §3 檔案分成 safe 與 private manifest | §3.0、§3.10 |
| §3.1 scene ID 與版本分開、`frame_id`、支撐面 point 與 normal、核准範圍 | §3.1 |
| §3.3 幾何 ref、encoding、用途核准 | §3.3 |
| §3.4 approval 未評估時不預填；驗證器不改檔、fail closed | §3.4 |
| §3.5 牆的幾何、body policy、EXACT_MESH 規則 | §3.5 |
| §3.6 門的底高與幾何；樓梯獨立分型 | §3.6 |
| §3.7 完整校正映射；clock 不進光學 hash | §3.7 |
| §3.8 validation 檔全部 private，不進 runtime readiness | §3.8 |
| §3.10 safe 與 production manifest 分開 | §3.10、§3.11 |
| §5.1 起始幾何不標 VERIFIED；地面看不到不證明人物看不到；L 形盲區 | §5.1 |
| §5.2 雙鏡可見部位 | §5.2（D27） |
| §5.3 逐 sample RGB；房內可能可見；北端 y 11–11.5 | §5.3（D47 之後，核對方式改依 §8.1） |
| §6 共通回應、`NON_EXECUTABLE_EXCERPT` | §6 |
| §6.1 query hash、snapshot hash、`relation: UNKNOWN`、排序、`image_evidence`、完整性語意 | §6.1（D28） |
| §6.2 依 grid 選格、不回退、`sample_age_s` 與 `clock_error_s`、完整性錯誤不降格 | §6.2、§2.3 |
| §6.3 完整區間 schema、RGB ref、heading、display hash、人體 prior | §6.3 |
| §6.4 OBSERVED 與 CONNECTOR 的界線、軌跡 ref、pin、假設切片 | §6.4 |
| §6.5 ref 核對、`support_offset_s`、穩定排序 | §6.5 |
| §7 可讀邊界、allowlist、預填等價的定義 | §7（D26） |
| §8 RGB 驗收與 GT 指標分欄；新增注入、分頁、截斷、錯連、原資產檢查 | §8 |
| §9 共 14 題 | §9 |
| §10.2 Q14 不讀 private | CS-Q14 |

### 10.2 與 Codex 準備文件（`14a3ffb`）的對照

第 2 版已對齊的項目（半開區間、事件 A 3 台、550 張、一份 RGB、候選欄位、未物化的局部軌跡、多人負證據、同步與建議影格分開），第 3 版都保留。原本列為差異的項目，現在的狀態都併入 §9。
