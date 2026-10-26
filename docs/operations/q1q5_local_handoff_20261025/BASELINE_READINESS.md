# BASELINE_READINESS.md：歷史交接公開整理

> 原文件日期：2026-10-24；公開整理日期：2026-10-26。
> 以下是當日交接紀錄，內文「目前／最新／仍需」、PR 狀態、效能與磁碟數字均屬歷史快照。
> 本文件沒有重新確認現行 G4、圖／參數凍結、正式產製、正式 baseline 或 Windows 狀態；其現況為 UNKNOWN。
> 本次只公開文字與來源 metadata，不構成 CX-4 整合產品、P1／P2／G4 驗收或 Windows 可執行包。

LOCAL 原檔：`r004-prereview-team-v2_20261024/BASELINE_READINESS.md`；1,555 bytes；1 檔；SHA-256 `ffa1b5f0e56bef79ba3c7e211ce84fadb735c3850896cd55f3fbdcf6454cc58b`。這是原檔 hash，公開整理後的檔案 bytes 不同。

完整來源收據與驗證口徑見 [LOCAL_ARTIFACTS.json](LOCAL_ARTIFACTS.json)；公開入口與重現限制見 [README.md](README.md)。

## 原歷史內容（已移除私人路徑及個人審查者姓名）

# baseline啟動條件與審查期間可做事項

工程補件已包含：8台入口、每台出口、3門洞尺寸及來源面、22個隱藏聯集輸入的排除證據、R101入向與反向轉移、baseline範圍提案。
這是完整靜態材料供審，不是執行核准或正式成效。
幾何物件名稱只用於靜態遮擋與來源核對；目標存在、類別與框一律由RGB模型產生，不以場景物件名查找目標。

仍需：獨立審查意見回收、Claude獨立檢查與使用者G4／新HSV核定；產品Draft與#145獨立契約測試對齊；之後凍結正式圖／參數，依已有授權產A4/B4 RGB／safe bundles，再建正式索引與跑兩模式。

審查期間可同步做（不得改這包或先看事件回改圖）：
1. 固定source composition，整合RULE_ONLY、Q1/Q4/Q2、HTTP與UI；用synthetic fixtures和既有錄製驗失敗路徑，不聲稱正式成效。
2. Codex提供#145最小重現、修產品端違規；Claude對齊#127。Codex不改測試包或#135。
3. 完成渲染／索引配置與磁碟、來源hash、run/camera/time scope預檢；未凍結前不產正式事件影像。
4. 準備一次查找／持續追查共用測量入口：模型呼叫、冷暖耗時、推論與顯示fps分列、RSS、逐次接回／切鏡、無模型replay與失敗紀錄。

審查核定後：凍結 → 正式RGB與safe bundle → 正式索引 → 一次查找／持續追查baseline → 輸出凍結 → 人工T/F與評分。
Windows可執行包、Qwen／YOLO-World／進階ReID比較後排，不作本版前置。
