# 工作台播放修正與 6 秒工程事件驗收

Issue #208 / Draft PR #209。工程驗收資料已備齊，等待使用者驗收；未合併、未解除正式資料與 #145 的核定。實作 head 為 `228bf448f5e40fc1c45ef5a1700de00fa5dc037a`，後續文件 commit 不改模型或播放器。

使用原網址 `http://127.0.0.1:63408/workbench-v2/?mode=review`，開頁會明示載入唯一的 SYNTHETIC 錄製事件。按播放可看完整 A → GAP → B；可切多鏡頭、拖曳、重播。右側／下方審查資訊不再把 RGB 擠成小縮圖。側欄「播放量測與素材說明」提供原始 JSON。

## 實際修正

- 未載入事件／Q1 片段時停用播放，避免只有時鐘運作。
- RGB 先經來源 hash 核對及解碼，最多 96 個時間格與 64 MiB 解碼像素緩衝；一秒前讀、相同像素共用解碼。前讀只供顯示，不供推論或排名。
- 時間格更新保留 DOM；狀態／鏡頭切換的新容器先準備影像，再整組替換。等待時標示「緩衝中 · 前一來源影格」，移除舊 OBS 框；缺圖明示 MISSING，不以舊觀測冒充。
- 半開來源時間窗終點顯示最後合法的 5.8 秒影格。播放到結尾標示結束，重播回到來源 0 秒；不請求第 30 格。
- 時間軸先讀取拖曳值，再發送 PAUSE，避免暫停重繪覆蓋新時間。實際拖至 2.5 秒顯示 SEARCHING、A 的 2.4 秒來源格，OBS 框為 0。
- 新版工程設定為 6 秒、5 fps、兩鏡頭共 60 個來源時間樣本。A 觀測 [0,2)、GAP [2,3)、B 觀測 [3,6)。原 2 秒預設、原包與人審材料保留。

## 瀏覽器實測

以下為真實定時播放的 DOM／解碼狀態 RAF 取樣，不是物理螢幕呈現 fps 或黑色像素分類器。

| 檢查 | 實際結果 |
|---|---|
| 正常完整播放 | 5／5；單畫面 3 次、多鏡頭 2 次 |
| 正常 RAF 取樣 | 1,801 次，沒有已解碼主畫面的取樣 0 次 |
| 正常播放牆鐘 | 6,000.7–6,017.3 ms |
| 正常 RAF 頻率 | 59.978–59.994 Hz；最大 RAF 間隔 17.8 ms |
| 解碼至替換 DOM | 224 次；p95 3.5 ms，最大 3.9 ms |
| 緩衝 | 1 次 RAF 取樣保留明示的前次畫面，沒有清空；最終 head 那次完整播放為 0 次 |
| A→B | 來源約 3 秒；瀏覽器取樣看見 B 的牆鐘為 3,015.8–3,018.5 ms；不把啟播時前次緩衝視圖算成額外 domain 切鏡 |
| Q1 片段 | A [0,2) 與 B [3,6) 都完整播放；300 次 RAF、無已解碼影像 0 次 |
| 慢載 | 每次媒體注入 350 ms 延遲；實際下載／hash／解碼 365.4–378.1 ms；361 次 RAF、無已解碼主畫面 0 次 |
| 缺圖 | 注入 B 5.6 秒後兩格 MISSING；24 次無已解碼主畫面是預期缺圖，UI 明示 MISSING，舊圖與 OBS 框都為 0；不併入正常播放成功率 |

前四次正常播放與慢載／缺圖／Q1 測試在 `0c21e422fff445361baf253b1a39a2789ccb17d6`；時間軸修正後在 `228bf448f5e40fc1c45ef5a1700de00fa5dc037a` 重新完成一次完整播放與實際拖曳。兩版差異只有時間軸 handler 與對應測試。原始 JSON 和截圖逐版留存。較早 `654f18f` 的多鏡頭測試曾出現一次空白，未通過；原始失敗數據保留，未納入上表。

## 真模型、replay 與重現

RT-DETR 重新讀這批 RGB 執行 60 次；25 筆 person 候選。首次模型載入 2,498.014 ms，forward 共 18,881.333 ms（3.178 fps），索引建立 21,152.529 ms。呼叫者 RSS 取樣峰值 801,308,672 bytes；這是離線索引量測，不能宣稱即時 5 fps 推論。

首次與從交付命令完整重跑各有 12 個樣本、24 次階段 replay，兩輪皆 COMPLETE。每輪 Q3 6 次、Q5 3 次，全數 timeout；兩輪 LLM used 都為 0。RULE_ONLY／兜底不能列為 Qwen 成功。

兩輪 RGB manifest、完整索引與 records、clock、parameter、cases、runtime 七組檔案皆 byte-identical。12 筆中 9 筆 domain output hash 相同。其餘三筆 Qwen 追查只在實測 `budget_used_ms`、stats 及衍生 hash 不同；12 筆回應移除 stats 與衍生 hash 後相同，六組追查 journal 移除實測 budget 與其 hash 後相同，畫面時間線及事件計數一致。這不是所有 live audit 位元組完全一致的宣稱；每輪自己的離線 replay 仍逐階段核對。

61 項 focused Node 測試、18 項 focused Python 測試通過；四個變更 Python 檔的 ruff、窄 diff check 通過。完整命令、pins、未量測欄位見 `docs/history/Q1Q5_PLAYBACK_ACCEPTANCE_20261024.json`。沒有執行 full suite、Blender render、正式評分或更換模型預算。

## 驗收與重現入口

LOCAL：`/Users/polalabear/amidst-artifacts/q1q5-playback-continuity-v2_20261024/README.md`。

- `open-workbench.command`：啟動新的 dynamic loopback server，載入固定錄製與既有 RGB/index；不呼叫模型。已實際啟動並核對 bootstrap 與四個實際提供檔案的 SHA-256，完成後只停止該測試 server。
- `run-baseline.command <新的絕對輸出路徑>`：重新產工程 RGB、RT-DETR 索引、Qwen/RULE 樣本與 replay。已真實執行於 `reproductions/verified-repeat-01`。使用原既有 uv 環境、既有 model/deps 路徑，不安裝、不下載、不操作共享 Ollama 的 lifecycle。
- `RUNTIME_COMPOSITION.json` 固定模型執行時的 527 檔 source；`DELIVERY_WORKBENCH_COMPOSITION.json` 固定提供 UI 的 527 檔。對應來源為 `source/` 與 `workbench-source-delivery/`；中間版本為稽核證據，不是另一個驗收入口。
- 原始 PNG、錄製、模型 audit、瀏覽器數值與截圖維持 LOCAL；GitHub 只上傳程式、設定、source pins 與精簡收據。

## 驗收界線

這次素材是兩張靜態合成 person RGB 加一張中性 RGB 的時間延展；只驗證播放器的時間、切鏡、緩衝與失敗處理，尚未驗證人物連續動作。正確率、物理顯示 fps、可靠 Qwen runner RSS／VRAM 峰值維持 null／UNKNOWN。

沒有改原 Blender／影像／GT、人審原包、#127／#135／#189、main／mainline；checkout、index 與原有 dirty 檔保留。正式 A4/B4、獨立人工正確性、必要圖／HSV 核定與 #145 前置仍未解除。本 PR 為 Draft，等待使用者驗收，不自行合併。
