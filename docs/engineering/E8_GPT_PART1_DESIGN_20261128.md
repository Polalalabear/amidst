# E8 GPT 組設計（#781）

狀態：Codex 已完成，待 Claude 審查（設計階段）。實作與執行等 #785 合併及 Claude 在 #781 確認。

## 模型與配對

使用 `gpt-6.1-terra`，與 E6 已提交的模型識別及計價表一致。第一部分沿用 #785 的 B1 凍結決策點，每個 `level × perm` 有 116 筆（E3 68、E6 48）。只跑 L0、L1、L2、L3、L4，各有 `p0`、`p1`、`p2`，每筆最多一次 Responses 請求，共 15 組、1,740 筆。L0c 與 L3F 保留在 Colab 資料內。第二部分和 #765 的 R-N 快照、E6 verdict 依 [#780 裁定](https://github.com/Polalalabear/amidst/issues/780#issuecomment-7225302386) 維持原範圍。

## 渲染與執行

1. Mac 讀取同一個凍結包的 `requests/e8_part1.jsonl`（`e8_level_request_v1`）。沿用 `e8_colab_run.load_pack`，驗證 manifest、請求雜湊、各組的 116 個唯一 `base_id`、`request_id` 與候選順序，並記錄最終合併後的渲染及評分來源 SHA。
2. 新增獨立的 E8 Mac adapter，透過 `e8_requests.answer_with_vlm` 呼叫 `render_vlm` 與各級既有 parser。L0 用 E7 AO 原提示與 AO parser，L1–L4 用 E8 VLM system/text 與 `parse_e8_answer`。L4 依渲染器順序傳 target reference、各攝影機影格與標籤。從 manifest 涵蓋的包路徑讀取 JPEG，保持原始位元組。沿用候選排列、視覺欄位遮蔽與 `KEEP` 對應。Responses 輸出上限沿用渲染器的 L0 256 tokens、L1–L4 48 tokens，格式錯誤和截斷原樣計入，維持一次回覆。
3. 沿用 `e6_arms_run.guarded_transport` 與 `cumulative_check` 的 guard、台帳及 D375 累計門檻。E8 新增組合與狀態檔。E6 的 `ArmDecider` 是閉迴路，有自己的 prompt、候選過濾及歷史。E8 使用其共用來源的唯讀 import，並把 E8 渲染結果交給 transport。`aopen/arms.py`、`aopen/decider.py`、`e6_arms_v1.json`、`e6_rule_neutral.py` 受凍結收據保護，保持位元組一致。API key 只在 Mac 的 guard callback 中讀取。
4. 組別起跑前驗證指紋及本組估算。以 `request_id` 原子記錄已完成的嘗試，再用 `e8_requests.make_record` 與 Colab `run_group` 的 `e7_colab_runtime` checkpoint 格式輸出 `checkpoints/gpt-6.1-terra__<level>_<perm>.json`。保留 `model`、`level`、`perm`、`n`、`records`、`latency_p50_s`、`format_invalid` 及逐筆欄位。若程序在送出後中斷且結果未落盤，標為未結算並停住，避免把同一筆付費請求重送。另用 `PRECHECK.json`、`STATUS.json`、`MANIFEST.sha256` 與 ApiGuard 台帳記錄執行。

## 離線 ApiGuard dry-run

在 #785 `2b3be2b2e04add010a2e20dbf2bd44f1ac188dda` 上，對正式包逐筆呼叫 `render_vlm` 並用 `guarded_responses_transport` 的 `last_estimate` 取得 ApiGuard 結果。估法為 `max(500, 文字字元數 // 3 + 1100 × 圖片數)`、渲染器輸出上限、Repo 價格 USD 1／百萬輸入 tokens、USD 5／百萬輸出 tokens。以空環境、拒絕任何網路請求的 opener 和不執行 callback 的替身 guard 量測。使用影格路徑存在性與 manifest 索引估算，影像內容未讀取。以下金額為估算 USD，每欄的組別皆為 116 筆。

| 級別 | p0 | p1 | p2 | 三組合計 |
| --- | ---: | ---: | ---: | ---: |
| L0 | 0.214614 | 0.214614 | 0.214614 | 0.643842 |
| L1 | 0.087578 | 0.087578 | 0.087578 | 0.262734 |
| L2 | 0.090077 | 0.090077 | 0.090077 | 0.270231 |
| L3 | 0.098284 | 0.098284 | 0.098284 | 0.294852 |
| L4 | 1.245906 | 1.245906 | 1.245906 | 3.737718 |
| 合計 | 1.736459 | 1.736459 | 1.736459 | **5.209377** |

L4 每個順序計入 1,036 個圖像輸入。D413 台帳基準為已用 USD 48.22、上限 USD 90、餘額 USD 41.78。只扣本估算後餘 USD 36.570623。正式執行前重新以最終 head 與確定的 Responses 請求逐組 dry-run，計入基準後所有台帳支出，再檢查 USD 90 累計門檻。若本輪估算超過 USD 10，先取得使用者核准。Dry-run 寫估算紀錄，實際請求逐筆由 ApiGuard 寫帳。

## Mac 評分

模型端只讀請求及 L4 的影像。Mac 評分端透過修正後的 `e8_score_run.py` 讀 Colab 格式 checkpoint，使用同一個 `scoring_only/answer_table.json` 和 `mac_index.json`。報同一組逐點正確率、多數決、三種順序的一致率、位置偏好與格式失敗數，E3／E6 分開列出。GPT 是第一部分的補充比較，沿用 E8 已預登的主要模型及閉迴路選擇。

目前 `own_box_hits` 以 `request_id` 索引，而各模型共用 ID。待 #785 合併後核對評分端，若仍共用這個索引，先將 GPT checkpoints 單獨用同一評分器評分，再按 `base_id`／`perm` 配對 Colab 結果，避免 L0 的 `OWN_BOX` 跨模型覆寫。實作審查時用假 transport 驗證兩種 parser、計數、checkpoint 與同一張標籤表的相容性，才進正式 dry-run。

## 估算的 LOCAL 依據

下列路徑均相對 `local/evidence/`，依 #785 的 `docs/operations/E8_REPRO_20261128.md` §3 可重建。

| 路徑 | 大小／檔數 | SHA-256 |
| --- | ---: | --- |
| `e8-pack-20261128/pack/MANIFEST.sha256` | 記錄 2,873 個檔 | `e55638ad11b84d0e38d05939539a43a13884405e567efa678b922b3793b983be` |
| `e8-pack-20261128/pack/requests/e8_part1.jsonl` | 3,974,673 bytes／1 | `356197a5f0938e0169c7edfe63cc43653f86ea0f7ba2377be62bf2b37a795f45` |
| `e8-pack-20261128/pack/scoring_only/answer_table.json` | 32,505 bytes／1 | `8d96f6434b0aee251df559357e440cf0079fdd08040a35eedbec598737e70004` |
| `e8-pack-20261128/mac_index.json` | 42,470 bytes／1 | `403718ac45cb4f3b804cae79aa6cbd0eb195c1ad5e69a679b0f05d4178548e7a` |
