> 已封存（2026-10-27，D91），見 [封存索引](../../archive/ARCHIVE_20261027.md)。

# 公開交接入口與歷史 CURRENT

公開整理日期：2026-10-26。這一組文件公開原 LOCAL 交接文字與來源 metadata，便於 GitHub 複核；它不是當前產品狀態或可執行包。

| 文件 | 用途 |
| --- | --- |
| [README.md](README.md) | 範圍、日期、重現條件與 hash 核對方式 |
| [DEMO_V1_HANDOFF.md](DEMO_V1_HANDOFF.md) | 2026-10-23 Demo／Windows 歷史交接要求 |
| [HANDOFF_REQUIREMENTS.json](HANDOFF_REQUIREMENTS.json) | 相同日期的結構化歷史要求與來源收據 |
| [BASELINE_READINESS.md](BASELINE_READINESS.md) | 2026-10-24 靜態審查前置條件歷史紀錄 |
| [DELIVERY_COMPOSITION.json](DELIVERY_COMPOSITION.json) | 2026-10-25 工程組成 533 檔；保留 commit／SHA 並補 git blob 大小 |
| [LOCAL_ARTIFACTS.json](LOCAL_ARTIFACTS.json) | 五份原文件與七份包 manifest 的相對路徑、大小、檔數及 SHA |

現行 G4、圖／參數凍結、正式 RGB／索引／baseline、Claude 複核及 PR merge 狀態，本次文件工作均未連線重查，記為 **UNKNOWN**。本次沒有授予核准或更改 D65 預算。CX-4 整合產品與 CX-10 可攜包須另行交付及實測。

以下原 CURRENT 屬 2026-10-23，內文「最新／目前」、PR heads、效能與磁碟數字全部保留為歷史紀錄，不能當今天的結論。

# CURRENT.md：歷史交接公開整理

> 原文件日期：2026-10-23；公開整理日期：2026-10-26。
> 以下是當日交接紀錄，內文「目前／最新／仍需」、PR 狀態、效能與磁碟數字均屬歷史快照。
> 本文件沒有重新確認現行 G4、圖／參數凍結、正式產製、正式 baseline 或 Windows 狀態；其現況為 UNKNOWN。
> 本次只公開文字與來源 metadata，不構成 CX-4 整合產品、P1／P2／G4 驗收或 Windows 可執行包。

LOCAL 原檔：`q1q5-qwen3-contention-20261023/CURRENT.md`；4,076 bytes；1 檔；SHA-256 `c5bd24c345c2d931939d51dae4cddd73e8b0c0dae4264a0394bf760f7ed6ae14`。這是原檔 hash，公開整理後的檔案 bytes 不同。

完整來源收據與驗證口徑見 [LOCAL_ARTIFACTS.json](LOCAL_ARTIFACTS.json)；公開入口與重現限制見 [README.md](README.md)。

## 原歷史內容（已移除私人路徑及個人審查者姓名）

## 最新Windows硬體與審查順序補充

#174 `d9125b68bdea82769a6c3b20317083d701fb2f1a`，B/Draft、未merge。最新交接檔 documentation-hardware-20261023/DEMO_V1_HANDOFF.md 與 HANDOFF_REQUIREMENTS.json；最新同份報告在同目錄docs/engineering/。補CPU/RAM/GPU/VRAM/driver/device/disk/power欄位；先前置審查、兩模式baseline、凍結後T/F及v1驗收，再後續模型比較。未新增推論或Windows執行驗證。

## 最新：Demo v1基準優先（2026-10-23）

#174文件head `238a6e34986bf826e1fe363d7592dd510484f542`，B／Draft，未merge。使用者新指示：先既有RT-DETR／RULE_ONLY兩模式真RGB基準，模型／ReID／新排程／Qwen比較延後。最新同份報告：documentation-baseline-v1-20261023/docs/engineering/Q1Q5_QWEN_CONTENTION_MIGRATION.md；跨機要求：documentation-baseline-v1-20261023/DEMO_V1_HANDOFF.md及HANDOFF_REQUIREMENTS.json。這是已核對的測試規格／交接要求，非已可執行Windows包或已完成真RGB兩模式數據；沒有新模型下載／推論／原素材複製／外傳。原408檔hash保持，新補充另有MANIFEST。

## 最新資料定義與工作盤點（2026-10-23）

#174文件head `5753dcaefcf23b710734fd286bff37bc7fd1b54f`，B／Draft，未merge。最新同份報告：documentation-dataflow-20261023/docs/engineering/Q1Q5_QWEN_CONTENTION_MIGRATION.md；完整現況資料定義：documentation-dataflow-20261023/DATA_DEFINITIONS.json。包含Q3/Q5 input/output與動態schema、實際生成prefill/decode分時、磁碟／idle RSS與20項剩餘交付。只讀GET核對模型當下未載入，無新推論／程式測試。既有401檔與前一補充包3檔hash不變；新補充另有MANIFEST.json。

## 同份報告問答補充（2026-10-23）

#174文件head `a90e857e4be5769f262f2ce772ab72149fb87d86`，base staging，B／Draft，未merge。最新版同一路徑報告：documentation-followup-20261023/docs/engineering/Q1Q5_QWEN_CONTENTION_MIGRATION.md。補充既有2.5／3延遲索引、常駐／生成／並行定義、按需偵測與播放分流評估；新調度／採樣政策未實作。

原MANIFEST所列401檔全部逐一hash驗證保持，原source-delta仍代表當時程式checkpoint；新版文件另以documentation-followup-20261023/MANIFEST.json凍結。原270／56測試屬歷史結果，本次只有文件diff／數字／連結／hash檢查，0新推論、0程式測試。

# RT-DETR/Qwen3並行實測與遷移評估

#172 `1bb4135965fb53643e9fbbaf8e41fd77e8ffb9c8`；#174 `67c25158a35877cfb3885c82d044443ef9a4fc67`。共同工程組成，B／Draft，未merge staging。

- MANIFEST.json SHA-256 `47e7ee608da9cc27110eb35fd9f188915719df82b0b3d6c705374c59eadbea99`，401檔／3,657,797bytes（不含manifest／本入口）；凍結前配置量5,328KiB，無模型／媒體副本。
- source-delta/COMPOSITION_DELTA.json SHA-256 `451f82d8429c8d0c9b3dae714e4f3c5b3d2f6f57c86bedf0c47130074518dbd5`，17檔分別對應#172四檔／#174十三檔，沿前次source組成還原。
- MEASUREMENTS.json／逐phase resources.jsonl：基線、初版負面schema、最終guided、卸載Qwen單跑；RSS/VRAM不相加。
- Qwen卸載RT約3.13fps；Qwen常駐無生成約3.11fps；生成時約0.55–0.62fps，並行swap新增與swapin/out均0。
- 長診斷Q3 3/3採用，Q5 3/3合法返回但0 Agent切鏡；原2秒probe仍timeout。不能當正式accuracy／追蹤驗收。
- focused-published-heads.xml：270 PASS；focused172.xml：56 PASS（重疊，不相加）。CONFORMANCE-FINAL：長Q3 56/0，長Q5 148/15/4；原預算Q3 56/0，Q5 133/14/3。
- REPLAY_FINAL_SOURCE.json：6筆新長診斷＋2筆退役2.5錄製replay一致，0模型呼叫；WIRE_FINAL_SOURCE：12個最終實測payload相同。
- MIGRATION_AUDIT五個舊checkout檔案hash未改；未查改DB、未啟新產品server。
- 最後可用13,135,364KiB；新權重0bytes，未清cache。

完整分析與重現：source-delta/docs/engineering/Q1Q5_QWEN_CONTENTION_MIGRATION.md。舊等待與失敗紀錄保持；初期缺deps／未配對export／schema負面結果均保留。
