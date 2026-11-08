# D139：`q-demo.api-bootstrap.v1` run 的偵測類別統計（#445／#493）

每個 bootstrap `runs[]` 新增 `detected_class_counts`：

```json
[{"class_label":"person","detection_count":123},{"class_label":"laptop","detection_count":12}]
```

統計來源只限該 run 已固定的 `run.bindings.index.records[].detections[]`，每個 detection 計一次，不去重人物、不依查詢分數或畫面時間窗篩選，不重新推論。`detections: null`／空清單算零；只列正整數計數，先依 `detection_count` 遞減，同數依 `class_label` 字典序。空索引回 `[]`。類別必須存在於同 run 的 `supported_classes.class_labels`；不符表示索引／類別表損壞，fail closed `DataIntegrityError`，不能把任意未知字串傳到前台。

同一 run 已有的 `detection_index_sha256` 綁定統計來源。這是 run 層的衍生展示統計，不放入 `supported_classes`、index manifest、records 或任何 `content_sha256` 的輸入；所有既有 content／index／class-map／alias pins 保持原值。Bootstrap 本身沒有新增 hash。消費者可用 `(scene_id, run_id, detection_index_sha256)` 識別／快取本欄位，不能跨索引混用。

只讀 `detections[].class_label`，不讀／回傳 GT、`gt_private`、劇本、visibility 或 depth。數值是偵測筆數，不是人數、身分、行為或正式研究 ground truth。`fixtures/q-bootstrap.json` 的 7／2 是明確的合成示例，不是真實 run 統計。
