# 工作台單一合成 run 與操作員評測準備

> 目前操作入口： [demo 指南](DEMO_V1.md)與[全部工作／依賴交接](../operations/CURRENT_WORK_REPRODUCTION.md)。本頁固定埠號與日期化測試屬原 checkpoint；當次 URL 使用 `DEMO_URL`，不沿用歷史服務位址。獨立受限 Phase1 驗收見[最新正式報告](../research/PHASE1_FINAL_REPORT.md)，不擴大本頁來源／幾何權限。

2026-10-13 核准範圍為04單一既有合成流程、06評測準備，入口為
`frontend/workbench`／8016 的研究角色「執行與評測」。實際驗證與當次來源 hash
保存在[本輪收據](../../data/engineering/workbench_0406_20261013/validation.json)；
01–03與其他歷史測試不沿用為本輪 PASS。

## 04：既有 E0 RGB 流程的新結果

僅 `synthetic-lab` 的既有 `simulation_v2` 註冊來源可用。流程為
`既有102張RGB → 原perception → 原association → 獨立新run結果`，不產生新影像。
每次捕捉已發布 annotation version、六項有限數值參數、來源／原freeze／producer hash。
Worker只能執行固定模組；瀏覽器不能提供路徑、命令、模型或輸入 records。

| 操作 | 結果與限制 |
| --- | --- |
| 新增／重試 | 每次新請求有獨立 job/run identity；相同 idempotency key 重試回同一工作。最多一件活動工作。 |
| Overlay | 僅同平面的 WALKABLE／REGION 軸對齊矩形、CAMERA `ground_to_pixel` affine校正與顯示label。其他改動明確拒絕，不假裝已套用。 |
| 進度／停止 | SQLite持久化phase與處理量；狀態包括COMPLETED／CANCELLED／FAILED／INTERRUPTED。停止不回報成功結果，重啟不自動延續未確認工作。 |
| 檢視／比較 | 原基線與新結果並列數量、原來源照片、投影路徑及全部已產生候選／替代。新輸出只供檢視，不取代原catalog或凍結基線。 |
| 認證 | 結果／receipt／四份輸出 artifact hash、來源與producer在讀取時核對。同輸入結果的決定性hash不含新run identity。 |

參數為 appearance distance、速度、sample gap、association gap、同期分離距離與投影不確定度，
各有 server-owned 上下限。影像／量測／片段／事件／gap／候選數量的差異不是精度提升證據。
原來源 RGB、凍結結果及 producer不回寫；GT／evaluator sidecars不進入新run輸入。
新結果仍為 `SYNTHETIC_ENGINEERING_ONLY`，不證明人物身分、行為意圖或校園formal authority。

本機輸出位於ignored `data/engineering/local_run/workbench_jobs_v1/<state-hash>/<job-ref>/`；
不同工作台state使用不同ledger。來源或producer变更拒絕讀取，缺少此流程的其他場景明示不可用。

## 06：固定來源任務與排演紀錄

此階段為 `PREPARATION_REHEARSAL`，不是第15項實際操作員招募／驗收。
固定任務只核對原來源影格的timestamp、presence、count、order四種註冊事實；
參考答案留在server，reference kind為 `CANONICAL_SOURCE_REFERENCE`，沒有人物／行為真值。
Manual使用指定鏡頭與時間範圍內的原照片；assisted額外提供有限註冊timestamp evidence。

每次任務獨立保存模式、順序、答案、正確／錯誤／UNKNOWN、protocol污染與停止狀態。
計時為server monotonic活動片段；重啟間隔另外列為excluded wall-clock approximation。
鏡頭／影格次數是 **server接受的來源查看請求**，不表示人確實看過照片；
correction／evidence只接受已發出的references，不接受caller捏造觀看或時間。

Manual活動期間，其他調查、run比較、展示／媒體及舊study報告均拒絕並記錄protocol污染；
本次任務自己的已授權原照片仍可查看。這是單一workbench session的隔離，
不量測或控制使用者在其他session／外部工具的活動。

報告保留完成／有效完成／錯誤／UNKNOWN／排除／停止與重複嘗試分母。
配對時間比較要求同task、binding及恢復後的同owner分組，兩模式各只有一次正確、有效完成
且至少發出一次來源查看；重複嘗試不挑選最佳時間，順序與學習效應未受控制。
`actual_operator_acceptance=false`、`efficiency_gain_claim=false`固定保留。

owner由工作台session決定；第一次啟動才發出恢復token。新session必須明確輸入task紀錄ref與token，
才可接手未結束任務，或唯讀恢復已結束報告與先前已授權影格。
token不進入公開報告／匯出；瀏覽器離開頁面不偷偷停止任務，需明確停止、提交或恢復。

## 暫緩範圍

05／07／08／09／10全部擴展／11／12／13／14／15均需使用者再次確認才能開始。
下一階段大範圍推進是規劃方向，未授權自動實作；Phase1 formal blockers及原frozen Phase2不變。
