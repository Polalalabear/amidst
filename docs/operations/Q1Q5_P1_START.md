# P1 工程預驗收：啟動與操作

這是8秒／20fps工程動態RGB與真RT-DETR凍結索引，D78接回版；不是正式r004成績。可攜包含同一整合commit的程式、兩種模式錄製及相對路徑設定，不含torch/Ollama權重或producer/GT。需Python3.12+，不會安裝套件。

## 一行啟動

在交付資料夾執行 `./start.command`。也可 `python3 -S app/scripts/start_q1q5_p1.py --bundle .`；啟動會逐檔驗證MANIFEST、選未占用的loopback埠、開啟review工作台。網址與owner PID寫入STATE/run-*/SERVER.json；Ctrl-C只停止這次terminal服務，不會關閉舊63408。

預設載入RULE_ONLY錄製。點「播放」看A→B在5.15秒切鏡；1.25–1.45秒及2.50–5.15秒的GAP會保留RGB背景，沒有目標框，不補假觀測。切為多鏡頭時看目前鏡頭標示。點錄製選單的AGENT_SEQUENTIAL後開啟，可見真Qwen3在D65預算timeout後RULE_FALLBACK接手；不是LLM成功。

## 查找與改選

輸入三句工程查詢：`哪些鏡頭拍到人13:00:00到13:00:08`、`哪些鏡頭拍到車13:00:00到13:00:08`、`紅色哪些鏡頭拍到人13:00:00到13:00:08`。RULE_ONLY解析後列相機與區間；零結果／UNKNOWN也照實顯示。點「播放片段」只看片段，或「設為Q2起點」執行同一索引的追查。不要把類別或顏色當身分。

可攜包預設不連模型；AGENT錄製可看，但重新執行AGENT需操作者另外提供已核定runtime與sha256。原工程機可加 `--runtime <pinned.json> --runtime-sha256 <sha>`，維持D65預算；不會下載模型。

「暫停」只控制播放；「停止追查」取消目前後端工作。模型是否停止計算UNKNOWN。進行中的人工改選需選原條件內、不得早於目前cursor的真觀測，預設不重啟Agent；明勾「這次改選後重啟Agent」才重啟，累計次數保留。

## 審核與可重現

`?mode=review`可看決策來源、候選、證據與兜底原因，demo網址移除mode參數。播放量測面板記錄實際畫面frame samples／swaps／buffering／RAF與cache峰值；物理螢幕fps仍null。輸出hash在審核面板對照錄製；兩種錄製replay均保留原output/links/decisions hash。

AC1–AC8工程走查與截圖／量測另以收據提供。AC7的#127全符合性仍待Claude rc2；不能把可播放、focused tests或record/replay hash相同當作全符合性PASS。G4、正式RGB/索引與獨立人工評分仍未完成。
