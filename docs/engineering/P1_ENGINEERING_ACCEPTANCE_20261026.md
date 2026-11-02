# P1 工程走查收據（CX-5，2026-10-26）

狀態：工程操作已走查，待Claude CL-4與使用者驗收。**AC7全符合性未通過；不是正式baseline。**

程式只取整合分支單一commit `c26d7cdd07deb43c9991a4f46403ea0236277fb1`。可攜包是LOCAL，原RGB／索引／完整錄製沒有上GitHub。新API透過既有QAPI、workbench-v2，不另做識別／GT重建。

| AC | 實際檢查 | 結果 |
|---|---|---|
| AC1 | Shared獨立根路徑（含中文/空白）執行 `./start.command --no-open`，Python -S；預設載入RULE錄製 | 工程通過；實際OS使用者未換，Windows未驗 |
| AC2 | 三句「哪些鏡頭拍到人／車／紅衣人13:00:00到13:00:08」 | READY 2台／NO_MATCH 0台／READY 2台 |
| AC3 | Q1紅衣人代表觀測設為Q2起點 | 跳A、0.100000s，真OBS框1個；原先跳0已修正重驗 |
| AC4 | 完整8秒單畫面與Agent錄製多鏡頭播放 | A→B切鏡；找不到保留GAP/UNKNOWN，沒有假框 |
| AC5 | 真Qwen3/D65雙模式固定索引執行與離線錄製 | RULE 146.953ms；AGENT 2184.192ms/1次模型呼叫逾時後兜底，agent_used=false |
| AC6 | review決策/候選/證據與demo模式對照 | demo的review/log不可見，保留身分未確認 |
| AC7 | 兩份record/replay response/links/decisions hash | replay相同；原#127比較479PASS/49FAIL/9缺context，**本項未通過** |
| AC8 | 缺觀測、零結果與未知身分 | 明列GAP、不代表目標不存在、UNCONFIRMED |

## 實際播放與資源

乾淨副本：完整8秒花8044.800ms；取樣到160個不同主畫面RGB，19.889 RGB frames/s；RAF約60.039Hz，物理螢幕fps仍null。整個影像區無已解碼主畫面的取樣次數0；buffering樣本3，維持上一張合法RGB到下一張解碼，不補觀測。換到B的來源clock為5150099us，實際RGB採樣5150000us。cache峰值66355200bytes（63.28125MiB，小於64MiB上限），RGB errors=0、missing_tiles=0。

另一完整Agent錄製多鏡頭輪：8012.700ms、RAF60.030Hz、缺解碼主畫面樣本0、buffering1。這是recorded playback，不在播放時計LLM成功。

同一固定索引的歷史RT-DETR CPU收據（2026-10-25）：320次forward，119217.784ms，2.684forward fps；索引總建置129987.910ms；caller sampled RSS峰值795148288bytes。此次沒有重跑RT-DETR；不能把離線播放20fps說成即時辨識20fps。各階段與來源檔pin在curated JSON，physical VRAM peak仍null。

## 重現／證據

- 操作：`docs/operations/Q1Q5_P1_START.md`。
- 精確數據與LOCAL證據hash：`docs/history/P1_ENGINEERING_ACCEPTANCE_20261026.json`。
- 包MANIFEST `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`；401檔／149501743bytes，320RGB＋2錄製，不含權重；CLI跨Python3.14/3.12重建401檔逐bytes相同。
- LOCAL畫面證據：`p1-browser-20261026/final-clean-b-observation.png`、`final-clean-rule-browser-metrics.json`、`final-q1-selected-seed.json`。截圖/完整錄製維持LOCAL。
- 11 adapter focused PASS、47相關frontend focused PASS；246 D73/D78 backend focused PASS；Ruff F/I/UP/B與diff --check。未跑完整suite／新渲染／正式推論。
- 限制：Claude獨立CL-4、#127 rc2、G4仍待完成；正確性/誤接回null。D80/D81後續r004與出題任務另開窄PR，不更動本凍結工程包。
