# Q4 正式 T／F 組員標註包說明（`q4-tf-pack-v1`）

- **任務編號**：Issue `#426`（W-A8 Q4 正式 T／F 評估工具：組員標註包＋計分）
- **合成測試包狀態（`--synthetic`）**：`READY`（僅供工具鏈、欄位校驗與計分流程驗證，不代表真實模型成績）
- **正式 W-C5 資料包狀態（`--safe-pack-dir`）**：`UNKNOWN`（等待 `#416` W-C5 safe data pack 產出後始可生成正式組員標註包）
- **真值隔離邊界**：`gt_read = false`；標註包內嚴禁包含任何 `gt_private/`、`ground_truth`、`visibility`、`depth` 或 `renderer` 軌跡資料。

---

## 工作內容

本標註包用於 **Q4（單格畫面目標出現判定）** 的人工 True／False（T／F）獨立標註與跨標註者一致性（Inter-Annotator Agreement）評估：

1. 組員根據標註包內的單格相機畫面（`frames/*.png`）與對應題目敘述（`target_query`／`statement`），獨立判斷該格畫面中是否出現指定目標。
2. 標註選項僅限三種：
   - `"T"`：畫面中**明確可見**題目所指目標（對應 `PRESENT`）。
   - `"F"`：畫面中**未出現**題目所指目標（對應 `ABSENT`）。
   - `"UNKNOWN"`：畫面模糊、嚴重遮擋、光線不足或證據不充分，**無法確定**目標是否出現（棄權／不確定）。
3. 本工作僅評估單格影像之可見證據，**不判斷**跨鏡頭是否為同一真實身分、**不推斷**盲區移動路線或物理碰撞／通行安全性。
4. 標註包內**不揭露**系統模型之預測結果（`PRESENT`／`ABSENT`／`UNKNOWN`），以確保人工標註完全獨立。

---

## 要提交項目

完成標註後，請在 `RETURN/` 資料夾內提交填寫完畢的 JSON 回件檔：

- **提交路徑與檔名格式**：`RETURN/q4_tf_answers_<組員代號>.json`（例如 `RETURN/q4_tf_answers_alice.json`）
- **必填頂層欄位**：
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
2. **複製空白作答模板**：
   - 將 `RETURN/q4_tf_answers_template.json` 複製為 `RETURN/q4_tf_answers_<組員代號>.json`。
   - **請勿直接覆寫** `RETURN/q4_tf_answers_template.json` 原始模板檔。
3. **逐題檢視影像並填寫判斷**：
   - 依序開啟 `answers` 陣列中每筆樣本的 `frame_file`（例如 `frames/Q4_S0001.png`）。
   - 對照 `target_query` 與 `statement`，在 `human_judgment` 欄填入 `"T"`、`"F"` 或 `"UNKNOWN"`。
   - **禁止修改**任何鎖定欄位（`sample_id`、`run_id`、`clock_id`、`camera_id`、`frame_index`、`timestamp_us`、`frame_file`、`frame_sha256`、`target_query`、`statement`）以及頂層校驗碼（`pack_id`、`sample_set_sha256`、`pack_manifest_sha256`）。
4. **儲存並檢查 UTF-8 JSON 格式**：
   - 確認所有樣本的 `human_judgment` 均已填寫（無空字串 `""`），且檔案為合法 UTF-8 JSON。

---

## RETURN/ 繳交規範

1. **檔案位置**：所有完成之回件必須放置於標註包內的 `RETURN/` 目錄下，檔名符合 `q4_tf_answers_<組員代號>.json`。
2. **不可竄改原包檔案**：
   - `MANIFEST.json`、`README.md`、`RETURN/q4_tf_answers_template.json`、`frames/*.png` 與 `claims/q4_system_judgments.json` 均受 SHA-256 校驗保護。
   - 計分器 `scripts/score_q4_tf_returns.py` 執行時會嚴格比對 `MANIFEST.json` 與所有鎖定欄位；任何未授權修改、缺漏樣本、未知題號或無效判定值皆會觸發 **Fail-Closed** 拒收。
3. **多人獨立標註**：
   - 若有多位組員標註同一包，可將各自的 `RETURN/q4_tf_answers_<組員代號>.json` 放入同一個 `RETURN/` 目錄，計分器將自動計算各標註者成績與跨標註者一致性（Exact Match Rate、Pairwise Agreement、Cohen's Kappa）。

---

## 產生與計分指令（維護者／評估端）

### 1. 產生合成測試標註包（`--synthetic`）

```bash
python scripts/build_q4_tf_annotation_pack.py --synthetic --output-dir <pack_dir>
```

### 2. 產生正式 W-C5 標註包（`--safe-pack-dir`）

> 目前 `#416` W-C5 safe data pack 尚未就緒，當指定路徑不存在或尚未包含完整安全資料時，工具會回報 `real_pack_status: "UNKNOWN"` 並拒絕偽造正式資料。

```bash
python scripts/build_q4_tf_annotation_pack.py --safe-pack-dir <w_c5_safe_pack_dir> --output-dir <pack_dir>
```

### 3. 驗證回件並執行 Q4 計分

```bash
python scripts/score_q4_tf_returns.py --pack-dir <pack_dir> --output <score_report.json>
```
