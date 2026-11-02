# D78 工程對照（2026-10-26）

D78採 §14-30(a) 與 §14-29(a)，原查詢、同一A20起點、RGB與RT-DETR records pin不變。資料是8秒/20fps工程場景，不進正式分母；無獨立答案，誤接回與正確性維持null。

| 數據 | 原版 | D78 |
|---|---|---|
| 首次起點後GAP | 1.25 s | 1.25 s（未延後） |
| A24→A29 | 未接回，raw IoU 0.2879724436 | 1.45 s接回，平移參照IoU 0.5874798803 |
| 早期長GAP | [1.25,5.15) s | 分成有實際框的短段；後段長GAP為[2.50,5.15) s |
| TEMP_LOST→PLAYING次數 | 8 | 12（其中1次使用中心平移） |
| B切鏡entry | 5.15 s | 5.15 s |
| 該次decision時間 | 4.20 s | 4.25 s |
| 模型呼叫 | 0 | 0（使用原真RT-DETR索引） |

本次固定索引執行牆鐘147.495ms；不是RT-DETR推論耗時。完整區間與三種hash見 D78_ENGINEERING_20261026.json。原先0–1s為選定起點前的GAP，故另報first_gap_after_seed_us。新response/replay完全相同：c30ed8147603dbb33cf4a306485772ce70f4a817963fc858aff1ee4c431bda88。原輸出51da51df…是歷史對照，未覆寫。

## 實作與驗證

- CENTER_TRANSLATION_V1只在既有600ms門檻內使用最後兩個合法真框估計中心位移，尺寸固定；每筆matching_audit記實際prev/next IoU、參照IoU與bbox、兩筆真來源、elapsed、REACQUIRED。沒有真框仍立即TEMP_LOST/GAP。超時只能由當前唯一合法真實候選開新local segment，關聯UNCONFIRMED。
- SEARCHING→SWITCHING在決策時刻記接受SWITCH，entry處另記SWITCHING→PLAYING並以cause_decision_id綁前筆。snapshot/entry/candidate/decision_time一致，模型輪數不增加。
- q2_stop_session需要同session/scene授權；USER ENDED/control_reason=USER_STOPPED保留原journal/counters。generation阻止provider/發布晚到後寫成功結果；stop重試回同一receipt。provider_cancelled=null，沒有宣稱模型停止計算。prefix journal bytes與hash一併回傳為靜止收據。
- 前端Q2用start/poll，停止追查按鈕與播放暫停分開。手動改選可明選restart_agent，預設false，session累計不退回。
- D73 NEXT可引用已fetch當前candidate的evidence_sha256或精確snapshot hash；SWITCH仍需真實觀測。reasons排序、多run澄清與未知digest=null亦對齊。
- 246項相關Python focused PASS、47項前端focused PASS；另有原整合166項與圖v3的27項。停止測試涵蓋provider中與publication中兩種晚到，沒有成功response寫入。

## 重現與限制

scripts/verify_q1q5_d78.py明列request/registry pins、起點與新輸出目錄；可選runtime必須額外明選allow-local-model-calls。不在這次RULE量測呼叫模型；CX-6由其他對話量測。新的輸出先凍結，再開歷史reference作比較，reference不進推論。

完整錄製與原始區間LOCAL：d78-rule-measurement-v5-20261026（本對話artifact根目錄）；RESULT.json SHA-256：7a9cd8f564e9045640b3db4e53cdba2aa9fc021110a9232fd0f818a955ebae1f.

新增wire欄位：Q1/Q2/Q3 reasons[]；link.matching_audit；decision.cause_decision_id/control_reason；stop-receipt/session-job STOPPED。#127原分支／schemas未改，需Claude rc2獨立對齊，AC7全符合性尚未驗收。synthetic Agent與stop測試不是Qwen成功率。P1/portable與真Qwen現場測試另附後續收據；G4、正式RGB／索引／人工評分皆未解除。

原 pinned kit 對本次工程session比較：479 PASS／49 FAIL／9缺context（本輪資料集合，不能與舊正式包的976/62/36混算）。完整LOCAL報告pin見curated JSON；包含舊link分類/schema與新D73/D78欄位差異，AC7仍未通過。不得以focused tests取代符合性。
