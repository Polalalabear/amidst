# 核心追蹤非人物類別擴充提案 v1（契約 O3：`Q_CORE_NON_PERSON_TRACK_O3_PROPOSAL_V1`）

- 狀態：**PROPOSED**（2026-11-04；對應 [#422](https://github.com/Polalalabear/amidst/issues/422) 與 `Q_CORE_SEARCH_TRACK_V1` §8 待決項目 O3）。本文件為契約增量提案，不宣告任何真實 run 門檻、圖或 G4 核准，亦不宣稱跨鏡身分確認或正式驗收通過。
- 依據：
  - `docs/contracts/Q_CORE_SEARCH_TRACK_V1.md`（§2.1、§2.3、§3.1、§3.2、§3.3、§3.4、§8 O3）
  - `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md`（§4 偵測索引、§8.2 同鏡頭 IoU 連接器）
  - `configs/q1q5/class_alias_v1.json`（COCO 80 類與別名映射）
  - `src/amidst/q1q5/linker.py`（同鏡頭局部連接器與類別無關擴充）
- 測試閘門：[`tests/q1q5/test_non_person_linker_o3.py`](../../tests/q1q5/test_non_person_linker_o3.py) 及既有 [`tests/q1q5/test_linker.py`](../../tests/q1q5/test_linker.py)。

---

## 1. 背景與目標

在 `Q_CORE_SEARCH_TRACK_V1` §3.2 與 §8 O3 中，第一版核心追蹤（`q_core_track`）建立於單一鏡頭 IoU 連接器（`linker.py`）之上，原先僅開放 `person` 類別，其餘 COCO 類別一律回傳 HTTP 200 `status: "UNSUPPORTED"`、`reasons: ["CLASS_NOT_SUPPORTED_BY_LINKER"]`。

本提案（契約 O3）定義 **Class-Agnostic 同鏡頭 IoU 連接器擴充規則**，在不引入任何跨鏡 Re-ID 模型、不讀取私有／真值欄位、不改變既有 `person` 追蹤行為與雜湊的前提下：

1. 明確劃分 COCO 80 類別中的**可追蹤剛體／移動物件類別（`TRACKABLE_CLASSES_V1`）**與**不支援追蹤之靜態／背景類別**。
2. 定義同鏡頭跨影格 IoU 連接規則（類別相等檢查、`iou_threshold`、`max_gap_frames`、`min_track_len`）。
3. 維持非人物類別對顏色過濾的拒絕規則（422 `UNSUPPORTED_CONDITION`），以及對不支援追蹤類別的明確回應（200 `UNSUPPORTED` + `CLASS_NOT_SUPPORTED_BY_LINKER`）。

---

## 2. 類別分級與支援矩陣（`TRACKABLE_CLASSES_V1`）

來源詞彙表沿用 `configs/q1q5/class_alias_v1.json` 的 COCO 80 類（含正規化別名，例如「車／汽車／轎車」→ `car`、「人／人物／行人」→ `person`、「椅子」→ `chair`、「桌子／餐桌」→ `dining table`）。

### 2.1 可追蹤類別（`TRACKABLE_CLASSES_V1` / `TRACKABLE_OBJECT_CLASSES`）

連接器支援以下 **9 個**具備單鏡頭短時距位移連續性之 COCO 類別：

| 分類 | `class_label` 清單 | 顏色條件（`color_label`） | 連接依據 |
| --- | --- | --- | --- |
| 人物 | `person` | 支援（`null` 或 `color_vocabulary.labels`，依 HSV 規則判定） | 同鏡頭類別相等 + 分數門檻 + HSV 顏色判定 + IoU／中心距離 |
| 剛體車輛與隨身移動物件 | `car`, `bicycle`, `motorcycle`, `bus`, `truck`, `backpack`, `handbag`, `suitcase` | **不支援**（只允許 `color_label: null`；非 `null` 時依 §2.1／§3.1 回 422 `UNSUPPORTED_CONDITION`） | 同鏡頭類別相等 + 分數門檻 + IoU（與可選中心距離比） |

程式碼常數定義於 `src/amidst/q1q5/linker.py`：

```python
TRACKABLE_OBJECT_CLASSES: frozenset[str] = frozenset({
    "person",
    "car",
    "bicycle",
    "motorcycle",
    "bus",
    "truck",
    "backpack",
    "handbag",
    "suitcase",
})
TRACKABLE_CLASSES_V1: frozenset[str] = TRACKABLE_OBJECT_CLASSES
```

並提供純函式判定入口：

```python
def is_trackable_class(class_label: str, *, allow_non_person: bool = True) -> bool:
    ...
```

- 當 `allow_non_person=True`（O3 預設）時，`class_label in TRACKABLE_OBJECT_CLASSES` 回 `True`。
- 當 `allow_non_person=False`（退回 v1 僅人物模式）時，僅 `class_label == "person"` 回 `True`。

### 2.2 不支援追蹤之 COCO 類別（Static / Non-Trackable COCO Classes）

在 `configs/q1q5/class_alias_v1.json` 內、但不在 `TRACKABLE_CLASSES_V1` 中的其餘 71 個 COCO 類別（例如靜態家具、家電、餐具與裝飾物：`chair`, `couch`, `dining table`, `tv`, `laptop`, `bed`, `potted plant`, `cup`, `bottle`, `book`, `clock` 等）：

- 在 `q_core_search`（case1 查找）：仍可依偵測索引做單格存在性查找。
- 在 `q_core_track`（case2 追蹤）與 `link_class_detections`：因為場景中多為大量靜態重複擺設或缺乏合理位移語意，連接器不為其串接軌跡，必須回傳 **HTTP 200**：
  - `status`: `"UNSUPPORTED"`
  - `reasons`: `["CLASS_NOT_SUPPORTED_BY_LINKER"]`
  - `sightings`: `[]`
  - `multi_view`: `[]`
  - `single_view`: `[]`
  - `blind`: `null`
- 若請求帶入不在 `class_alias_v1.json` 內的未知類別（如 `"unicorn"`），維持 §2.3／§3.3 回傳 **HTTP 422** `UNSUPPORTED_CLASS`。
- 若非人物類別（不論是否在 `TRACKABLE_CLASSES_V1` 中，例如 `car` 或 `chair`）搭配非 `null` 的 `color_label`，維持 §2.3／§3.3 回傳 **HTTP 422** `UNSUPPORTED_CONDITION`。

---

## 3. 同鏡頭類別無關 IoU 連接規則（Same-Camera Class-Agnostic IoU Linker）

### 3.1 嚴格類別隔離與觀測分數門檻（Class Equality & Score Gate）

連接器在任何候選配對前，必須先執行嚴格類別相等與信心分數檢查：

```text
det.class_label == target_class and det.score is not None and det.score >= min_score
```

- **非目標類別嚴格排外**：不同類別的偵測框（例如同一畫面中 100% 重疊的 `person` 與 `car`，或 `car` 與 `chair`）**絕對不得互相連接或合併**。
- **無分數或低分觀測嚴格排除**：觀測必須具備明確且有效之信心分數（`score`），無分數（`score is None`）或低於 `min_score` 者嚴格排除，絕不預設為 1.0；在 `strict=True` 模式下缺漏分數直接回絕（`INVALID_SCORE`）。
- **Observation ID 必須來自輸入**：可用觀測缺少非空 `observation_id` 時回絕 `INVALID_OBSERVATION_ID`；不得合成 `obs:syn:*` 來冒充來源引用。
- **歧義時保留未連接假設**：候選 IoU 差小於既有 `LinkParameters.ambiguity_margin` 時不延續 track；多個 active tracks 對同一候選也依相同 margin 拒絕強配。`parameters=None` 時沒有選定 margin，若延續匹配有多個合格候選則保守拒絕延續；不新增閾值或輸出狀態。
- `LocalLinker` 與 `link_class_detections` 的預設 `target_class` 均為 `"person"`，確保所有既有呼叫端與測試零退步。

### 3.2 單一時鐘與來源範圍鎖定（Single Run / Clock Scope Lock）

- 連接器與單一追蹤請求嚴格綁定在同一 `(run_id, clock_id, camera_id)` 內，禁止跨鐘或跨 run 串接。
- 若批次觀測包含相異 `run_id` 或 `clock_id`，立即拋出 `LinkError("Cross run/clock input", "CROSS_RUN_OR_CLOCK")`。
- 每個 track 的 `track_ref` 前置圖像納入 `[run_id, clock_id, camera_id, ...]`，確保證據出處鎖定單一鏡頭時鐘軸。

### 3.3 連接器參數與規則

| 參數 | 型別與範圍 | 預設／說明 |
| --- | --- | --- |
| `target_class` | `str` | 預設 `"person"`。必須屬於 `TRACKABLE_OBJECT_CLASSES`，否則回 `UNSUPPORTED`（`CLASS_NOT_SUPPORTED_BY_LINKER`）或於嚴格種子模式拋出 `LinkError(..., "CLASS_NOT_SUPPORTED_BY_LINKER")` |
| `iou_threshold` / `iou_min` | `float` $\in [0, 1]$ | 同鏡頭前後觀測框（或線性中心平移參考框）的最小 IoU 門檻（合成測試常用 `0.3`） |
| `max_gap_frames` / `max_gap_samples` | `int` $\ge 0$ | 允許中間連續缺漏的取樣格數上限；gap 內再次出現且 IoU 達標時接續為同一局部片段，超過上限則結束該段（不跨長缺口復活舊段） |
| `min_track_len` | `int` $\ge 1$ | 構成有效追蹤片段（track / sighting）所需的最少觀測格數；低於此長度的零星單格雜訊予以過濾 |
| `min_score` | `float` $\in [0, 1]$ | 偵測框信心分數下限，無分數或低分觀測嚴格排除 |
| `as_of_us` | `int \| None` | 時間上限（不看未來原則：僅使用 `timestamp_us < as_of_us` 的已推論觀測）。未指定時基準線延伸至輸入影格上限，確保跟丟狀態不遺失 |

### 3.4 GAP 切片與時間網格嚴格對齊（Grid-Aligned Gap & Lost Slicing）

- 時間間隔判定嚴格依據 `interval_us` 與 `max_gap_frames`（或 `max_gap_samples`），輸入觀測時間戳記若偏離 index grid 必須拒絕（`PARAMETER_GRID_MISMATCH`）。
- `single_view` 切片：`ON_CAMERA`、`GAP`、`LOST` 之時間區間 `[start_us, end_us]` 嚴格對齊網格整數倍，不得任意縮放。
- 當觀測影格在最後一次 sighting 後仍有後續影格且未再出現時，若未指定 `as_of_us`，視窗邊界延伸至輸入影格結尾 `max_record_end_us`，並正確補上 `LOST` 切片，狀態標記為 `LOST`，絕不縮小視窗遺失狀態或誤判為 `TRACKING`。
- Track 可保留跨短 gap 的同鏡頭局部關聯假設；`sightings[]` 與 `single_view` 的 `OBSERVED` 區間只涵蓋連續實際觀測格。明確 `MISSING`、未推論或缺觀測格不納入 `OBSERVED`；其間以 `GAP`/`UNKNOWN` 保留不確定性。
- 同鏡頭重疊／相接 sighting 先合併；`single_view` 只在目前鏡頭沒有後續實際覆蓋時才切到另一鏡頭，重疊期間不提前切鏡。

### 3.5 輸出結構與證據邊界（Provenance & Uncertainty）

每一筆由連接器產出的同鏡頭片段（`tracks[]` 與 `sightings[]`）必須遵守：

1. `evidence_state`: 固定為 `"OBSERVED"`（僅包含 `frame_state == "INFERRED"` 中實際偵測到的 `observation_ids`）。
2. `identity_verdict`: 固定為 `"UNCONFIRMED"`（代表「同鏡頭、時間相近且位置重疊的同類別候選框」，不宣稱物理世界同一物件或跨鏡同身分）。
3. `range_us`: 半開區間 `[start_us, end_us]`，若指定 `as_of_us` 則 `end_us <= as_of_us`。
   `tracks[].range_us` 僅為首末觀測的局部關聯假設包絡，不代表中間 gap 有觀測；實際 `OBSERVED` 時間以 `frame_indices`、`observation_ids` 與分段 `sightings[]` 為準。
4. 禁止任何真值、渲染私有欄位或未來影格進入連接計算。

---

## 4. 相容性與驗收條件

1. **向後相容**：`LocalLinker` 保留既有簽章，新增具預設值的關鍵字參數 `target_class="person"` 與 `allow_non_person=True`。當 `target_class="person"` 時，`segment_id` 雜湊計算、狀態轉移（`PLAYING` / `TEMP_LOST` / `SEARCHING`）與 `LinkStep` 欄位與既有行為完全一致。
2. **多類別與混合場景驗收**：
   - `car`, `bicycle`, `truck`, `backpack` 等類別在同鏡頭跨影格移動與短暫遮擋（`gap <= max_gap_frames`）下可正確連接，超過 `max_gap_frames` 時自動切分為獨立片段。
   - 混合場景（`car` + `person` + `chair` 同框且重疊）下，追蹤 `car` 僅串接 `car` 觀測，絕不混入 `person` 或 `chair`。
   - 非可追蹤類別（`chair`, `dining table`, `cup`）回傳 `status: "UNSUPPORTED"` 與 `reasons: ["CLASS_NOT_SUPPORTED_BY_LINKER"]`。
   - 非人物類別帶 `color_label` 時拋出 `LinkError(..., "UNSUPPORTED_CONDITION")`。
3. **REVISE 守門驗收**：
   - 跨 run / 跨 clock 串接嚴格禁止，違者拋出 `LinkError`（`CROSS_RUN_OR_CLOCK`）。
   - 無分數或低分觀測嚴格依照 `min_score` 篩選，絕不預設為 1.0；在 `strict=True` 模式下缺漏分數直接回絕（`INVALID_SCORE`）。
   - GAP / LOST 切片邊界嚴格對齊 `interval_us`，觀測尾端丟失目標時正確輸出 `LOST` 狀態與區間。
