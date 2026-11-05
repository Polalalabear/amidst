# Q4 正式 T／F 組員盲測標註包說明（`q4-tf-pack-v1`）

- **任務編號**：Issue `#426`（W-A8 Q4 正式 T／F 評估工具：組員標註包＋計分）
- **合成測試包狀態（`--synthetic`）**：`READY`（僅供工具鏈、欄位校驗與計分流程驗證，不代表真實模型成績）
- **正式 W-C5 資料包狀態（`--safe-pack-dir`）**：`UNKNOWN`（等待 `#416` W-C5 safe data pack 產出後始可生成正式組員標註包）
- **真值隔離與盲測邊界**：`gt_read = false`；標註包內嚴禁包含任何真實標籤（GT）、`gt_private/`、`ground_truth`、`visibility`、`depth` 或 `renderer` 軌跡資料。
- **評估端答案分離（Codex REVISE #436）**：標註包中不得包含系統預測答案或 `claims/` 目錄。評估端標準答案獨立產製為 `<pack_id>.eval_claims.json`，透過 `pack_manifest_sha256` 與 `sample_set_sha256` 進行雙向密碼學綁定，確保組員在完全盲測（Double-Blind）狀態下標註。
- **標註語意綁定與契約相容（Codex REVISE #436 P2）**：標註包生成工具嚴格限制為 `TARGET_PRESENCE` 語意（與作答指引「T=目標明確可見、F=未出現」保持 100% 一致）。回件必須明確繼承並鎖定該語意；評估端計分器提供嚴格驗證來源語意與 frozen 欄位的契約 adapter（`normalize_return_document`、`export_return_to_q4_tf_reviews`、`import_q4_tf_reviews_to_return`）以完全相容 `#123/#147`（`q4-tf-review.v1` 與 `q4-presence-eval-report.v1`）。

---

## 工作內容

本標註包用於 **Q4（單格畫面目標出現判定）** 的人工 True／False（T／F）獨立盲測標註與跨標註者一致性（Inter-Annotator Agreement）評估：

1. 組員根據標註包內的單格相機畫面（`frames/*.png`）與對應題目敘述（`target_query`／`statement`），獨立判斷該格畫面中是否出現指定目標。
2. 標註選項僅限三種：
   - `"T"`：畫面中**明確可見**題目所指目標（在 `TARGET_PRESENCE` 語意下對應 `PRESENT`）。
   - `"F"`：畫面中**未出現**題目所指目標（在 `TARGET_PRESENCE` 語意下對應 `ABSENT`）。
   - `"UNKNOWN"`：畫面模糊、嚴重遮擋、光線不足或證據不充分，**無法確定**目標是否出現（棄權／不確定）。
3. 本工作僅評估單格影像之可見證據，**不判斷**跨鏡頭是否為同一真實身分、**不推斷**盲區移動路線或物理碰撞／通行安全性。
4. 標註包內**絕對不揭露**系統模型之預測結果（`PRESENT`／`ABSENT`／`UNKNOWN`），以確保人工標註完全獨立客觀。

---

## 要提交項目

完成標註後，請在 `RETURN/` 資料夾內提交填寫完畢的 JSON 回件檔：

- **提交路徑與檔名格式**：`RETURN/q4_tf_answers_<組員代號>.json`（例如 `RETURN/q4_tf_answers_alice.json`）
- **必填頂層欄位**：
  - `schema_version`：固定為 `"team-review-pack.v1"`
  - `template_kind`：固定為 `"q4-tf-answers-v1"`
  - `annotation_semantics`：固定為 `"TARGET_PRESENCE"`（需與標註包及模板一致）
  - `annotator_id`：組員代號（非空字串，需與檔名一致）
  - `completed_at`：完成時間（ISO-8601 字串，例如 `"2026-11-04T12:00:00+08:00"`）
  - `answers`：與 `RETURN/q4_tf_answers_template.json` 樣本順序及數量完全一致的作答陣列
- **每筆樣本必填欄位**：
  - `human_judgment`：必填 `"T"`、`"F"` 或 `"UNKNOWN"`（不可留空）
  - `notes`：選填備註字串（當填寫 `"F"` 或 `"UNKNOWN"` 時，建議填寫簡短原因，如 `"目標被柱子遮擋"` 或 `"畫面無人物"`）

---

## 操作步驟

1. **確認壓縮包與目錄結構**：
   - 解壓縮或開啟標註包目錄，確認包含 `README.md`、`MANIFEST.json`、`frames/` 及 `RETURN/q4_tf_answers_template.json`。
   - 確認目錄內無 `claims/` 子目錄（盲測保護）。
2. **複製空白作答模板**：
   - 將 `RETURN/q4_tf_answers_template.json` 複製為 `RETURN/q4_tf_answers_<組員代號>.json`。
   - **請勿直接覆寫** `RETURN/q4_tf_answers_template.json` 原始模板檔。
3. **逐題檢視影像並填寫判斷**：
   - 依序開啟 `answers` 陣列中每筆樣本的 `frame_file`（例如 `frames/Q4_S0001.png`）。
   - 對照 `target_query` 與 `statement`，在 `human_judgment` 欄填入 `"T"`、`"F"` 或 `"UNKNOWN"`。
   - **禁止修改**任何鎖定欄位（`sample_id`、`run_id`、`clock_id`、`camera_id`、`frame_index`、`timestamp_us`、`frame_file`、`frame_sha256`、`target_query`、`statement`）以及頂層校驗碼（`pack_id`、`sample_set_sha256`、`pack_manifest_sha256`、`annotation_semantics`）。
4. **儲存並檢查 UTF-8 JSON 格式**：
   - 確認所有樣本的 `human_judgment` 均已填寫（無空字串 `""`），且檔案為合法 UTF-8 JSON。

---

## RETURN/ 繳交規範

1. **檔案位置**：所有完成之回件必須放置於標註包內的 `RETURN/` 目錄下，檔名符合 `q4_tf_answers_<組員代號>.json`。
2. **不可竄改原包檔案**：
   - `MANIFEST.json`、`README.md`、`RETURN/q4_tf_answers_template.json` 與 `frames/*.png` 均受 SHA-256 校驗保護。
   - 影像檔均經過 PNG 結構、CRC 與解碼校驗，防止無效圖檔或隱藏 metadata。
   - 計分器 `scripts/score_q4_tf_returns.py` 執行時會嚴格比對回件中每個樣本的欄位數值與 `MANIFEST.json` 是否完全吻合；若有任何篡改，評估將被拒絕（Fail-Closed）。

---

## 語意契約與 #123/#147 相容性適配說明

1. **語意差異說明**：
   - `TARGET_PRESENCE`（W-A8 預設盲測語意）：組員判斷目標人物是否出現在單格畫面中。
     - `"T"` -> `PRESENT`
     - `"F"` -> `ABSENT`
     - 若系統宣稱 `ABSENT`，組員填 `"T"`，則評定為 `FN`（系統宣稱無，組員確認有）。
   - `CLAIM_VERACITY`（#123/#147 語意）：組員判斷系統陳述是否屬實。
     - 若系統陳述為 `ABSENT`，組員填 `"T"`，代表陳述屬實（目標確屬 `ABSENT`），評定為 `TN`。
2. **契約適配器（Adapter）**：
   - `scripts/score_q4_tf_returns.py` 內建 `export_return_to_q4_tf_reviews` 與 `import_q4_tf_reviews_to_return`：
     - 能將 `team-review-pack.v1` / `q4-tf-answers-v1` 回件無失真轉換為 `#147` 的 `q4-tf-review.v1` 行記錄。
     - 轉換時依據語意自動映射 `system_positive` 與 `answer`（`T`／`F`／`不確定`），使 `#123/#147` 的 `score_reviews` 與本計分器產出的混淆矩陣與指標完全一致。
