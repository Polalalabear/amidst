# Team review pack registry

回收結果只供評估端；推論、索引、排序、圖、參數與 prompt 不讀回收結果。PILOT 不進正式評估分母。題目、精確標準答案與 T／F 由組員填，程式不補猜。

## 發包紀錄

| 版本 | LOCAL 資料夾 | MANIFEST bytes SHA-256 | 實際內容 |
| --- | --- | --- | --- |
| v0-pilot（2026-10-21） | `/Users/polalabear/amidst-artifacts/team_review_pack_v0-pilot_20261021/` | `c0ee42c1275d13551734634052814206f06bca4797fa04a08761c2f73d84096a` | A／B1 原 RGB 24 格：系統說「有」12／「沒有」12；60 列空白文字情境；沒有組員答案 |

| v0-pilot 審查修正 r2（2026-10-25） | `/Users/polalabear/.codex/visualizations/2026/10/24/01a16c37-bf25-7220-a407-4dd7e74bd30a/team-pilot-review-fixes-20261025/` | `4b5ff905a7ff4394a552c6d93c0be2b7b72569cc1e07d5e5ead8eb54142233d4` | 原24格ID／RGB hash不變，12正／12負；四段組員說明、RETURN檔名、maintainers指南；仍PILOT、空答案 |

原定 200 格是數量提案。本 PILOT 重用既有 35 格凍結 smoke 輸出（SHA-256 `390f685ac111d0cb79d425be5c5c311a311c11f6c6052ce7d1729942a457356c`），其中 12 格有 person 判定；為避免重複與填造，正負各取 12 格，共 24 格，差額 176。不是 200 格正式標註集，也不冒稱紅／藍衣或車輛評估。舊 smoke 的 0.30 僅是歷史報表設定，不是正式核准閾值。正式 r004 v1 等 #115／#118。

文字說明沿 #146／PR #149。三列「範例.csv」只示意格式，沒有實際題目或答案，不匯入評估。組員的精確 Q1／Q3 標註不足時，匯入器只保留原文並標 INVALID；D75 已決：由 Claude 將組員 CSV 轉為精確 annotation JSONL，保留來源 CSV hash；Codex 不預填或轉答案。可另外提供這份由評估端準備的精確 annotation JSONL，程式不能用受測系統輸出回填答案。annotation 的結構檢查不代替評估器的完整契約 schema 驗證。

## 完整性與回收

使用者已於 2026-10-21 同意：MANIFEST 驗原始範本、圖片與不可改欄位；回收 CSV 另記新 hash。發包時的 `templates/情境.csv`、`templates/審查表.csv` 是不可改的原始範本；組員只改一般位置的兩個 CSV。MANIFEST 由使用者保管其 bytes SHA-256，匯入時必填 `--manifest-sha256`，不可相信回收包自己提供的新 MANIFEST。

```sh
uv run python scripts/import_team_review_pack.py \
  --pack /Users/polalabear/amidst-artifacts/team_review_pack_v0-pilot_20261021 \
  --manifest-sha256 c0ee42c1275d13551734634052814206f06bca4797fa04a08761c2f73d84096a \
  --text-csv '<組員交回的情境.csv>' --review-csv '<組員交回的審查表.csv>' \
  --output '<新的 ~/amidst-artifacts/ 回收目錄>' \
  --registry docs/evaluation/TEAM_REVIEW_PACK_REGISTRY.md
```

命令中的回收檔／新目錄是 placeholders，尚未執行真實回收。`--annotations` 可提供依 D75 由 Claude 準備的精確 JSONL；沒有就不輸出 Q1／Q3 標準答案。圖片／範本／MANIFEST pin 不符仍整包拒收；固定欄位誤改只把該列標 LOCKED_FIELD_CHANGED／INVALID，其他列繼續。未知／重複／刪除ID仍拒收。非UTF-8以CSV_UTF8_REQUIRED提示另存CSV UTF-8；缺欄／空答／F或不確定沒理由的列INVALID，不補值。輸出 JSONL、回收 CSV 的新 hash 與 receipt.output_sha256 可重跑核對；同一輸入不重複登錄。輸出只到 repo 外，registry 只留 hash。

## 回收登錄

本registry尚未登錄v0-pilot的真實回收；r004 yyin回收屬另一份包，不以本紀錄否定其已完成狀態。單元測試使用假資料，不當成組員成果。

| output_sha256 | version | MANIFEST SHA-256 | returned CSV SHA-256 |
| --- | --- | --- | --- |


## 審查修正 r2 驗證（2026-10-25）

原包32個固定檔與原MANIFEST全保留；新包24個sample_id／RGB hash逐一相同，新MANIFEST只反映說明／目錄補件。所有queries／cases／q4／invalid輸出列都帶pilot與evaluation_eligible；receipt仍另驗來源pin。沒有真實回收或人寫答案，本輪沒有用預測製作答案；重建是組員版格式補件，不要求重交已交付工作。

F3責任依D75：組員出題與寫答案，Claude轉JSONL並附來源CSV hash，Codex只維護程式。新版Q1評分#224要求評估端另外凍結query_binding；舊importer不會替缺少的binding猜值，缺件由評估端補context。這不是從預測反推答案的入口。
