# 真動態工程 baseline（#210 / Draft #211）

公開 locator 約定：`$AMIDST_ARTIFACTS` 代表審查者自行指定、canonical 絕對路徑的 LOCAL 證據根目錄，`$AMIDST_SOURCE`／`$SOURCE` 代表按 composition 還原的工程，`$AMIDST_PYTHON`／`$AMIDST_PYTHON_ENV` 代表既有 Python executable／環境。這些是去識別化 locator，不宣稱其他機器已存在對應資料；先取得相同 hash 的 LOCAL 檔案並設定環境變數。GitHub 只有公開程式與精簡收據，完整 RGB、錄製、模型 wire 與原始命令紀錄仍為 PRIVATE／LOCAL。文中的歷史數據未因路徑去識別化而重跑。

原播放素材為兩張靜態圖延展。本版以全新獨立Blender場景產生8秒、20fps、雙鏡頭各160張960×540 RGB，人物有位移與步態；真RT-DETR逐格建索引，沿原Q3/Q5 API跑Qwen3與RULE_ONLY、錄製/replay，接回原63408工作台。新場景是替代工程來源，正式r004未產製，身分與物理可行性未確認。

## 實際驗收結果

- 最終正常完整播放5次（單畫面3、雙鏡頭2）：2402 RAF取樣、主畫面缺圖0、BUFFERING1。每次實際呈現160/160來源格，每鏡頭向前最大1格；全部媒體decode-to-swap p95 2ms/max5ms。decoded pixels峰值66355200bytes（63.28MiB），非瀏覽器整體RSS。
- 原63408部署後再播一次8秒：482 RAF、主畫面缺圖0。350ms/張注入慢載：8秒來源約14.417秒播完、160格全呈現、主畫面缺圖0；來源clock等媒體，不跳格。缺圖B5.6秒起：144個預期空圖RAF取樣，明示MISSING並移除舊圖/OBS；拖回起點可恢復播放。Q1查得A/B及兩段實際播放，61 RAF、缺圖0。
- 兩次真320-frame RT-DETR重建，index/records等9份query輸入JSON逐bytes相同；每次59筆person>=0.5，forward119217.78ms / 2.684fps，完整index129987.91ms，caller sampled RSS peak795148288bytes。source20fps與模型推論fps分列，不宣稱即時推論。另保留18+4+18次pilot/debug與第一版人偶失敗證據。
- 兩輪24樣本、48stage replay全部PASS。Q3/Q5共18次Qwen呼叫全部timeout，LLM_used=0；兜底不算LLM成功，2秒/5秒預算不改。12個對應輸出10同bytes，另2因fallback latency與依賴hash不同；所有timeline/event counts一致。FIRST_CALL不是可證明冷模型，背景負載未控制。
- 獨立CLI `scripts/replay_q1q5_dynamic_evidence.py` 再重播48份，程序硬拒所有socket連線、連線嘗試0；錯pin與覆寫兩負例拒絕，3案例PASS。重用既有recording/kernel，不接live模型。
- focused Python78 PASS、Node76 PASS。額外舊shell套件4 FAIL（仍期待舊HTML/stub），保留原紀錄，未宣稱全suite通過。原#127 kit81檔逐bytes核對994d34c，8份新錄製全項1334 PASS / 91 FAIL / 35缺context，#145仍FAIL。

## 程式與來源界線

新增dynamic RGB schema綁定scene/run/clock/static/RGB pins，拒絕actor欄位、重複/錯格、跨來源、錯hash。公開PNG剝除文字metadata並分列source/served hash，像素不改。Qwen/RT只讀安全RGB/合法靜態資料；producer motion/actor設定僅供產製，私有producer產物留LOCAL，不進推論、候選排序或LLM prompt。新producer從factory-startup建立，不讀原Blender。原r004只重新hash，SHA466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b相符，未開啟/渲染/改動。

快取採frame LRU與像素/消費者租約，上限64MiB decoded pixels、96 frame entries、最多300ms/6格前瞻。交換先解碼；控制列等可見畫面commit，缺圖不留下來源timestamp或OBS。狀態/鏡頭轉換沿原controller，沒有crossfade、插值影格或偽造observation。

模型固定COMPOSITION 533檔、head f1d13cebc7c9437fb27ebf8450b5c43d01d7d77b；最終UI固定DELIVERY_COMPOSITION 533檔、head01c6ef19c6d52df864a9ccee15be6882ae6b5606。中間UI來源/失敗原始量測保留，兩context不混稱同版。離線CLI為本PR另列工具，有獨立file hash。

新工程固定兩題「哪幾台拍到人13:00:00到13:00:08」「人13:00:00到13:00:08」，兩profile同題，起點選實際A鏡頭1秒觀測；HSV原值不變，color多為WEAK，不把person偵測當紅衣正確。color=null是現有runtime行為，原kit拒絕，契約是否核准仍待#144/#145，未改schema或宣稱核准。不將新場景/題組與舊靜態/紅衣題組作單因子模型比較。

## 審查前五項收尾

1. 最小規格/JSON、資料/版本、控制變因、預算、case/input/output/量測與null語意已沿#192交付，正式8題candidate bytes保持原樣，獨立expected仍0。
2. 真RGB/RT-DETR/Qwen/RULE/timeout/API/錄製/離線入口完成工程接線；Qwen成功率實測為0，不標成模型成功。
3. latency/RSS/推論fps/顯示來源格/RAF/calls/切鏡追丟接回/錯誤均留逐次數據；correctness、物理螢幕fps與VRAM峰值未測保持null。
4. API/工作台/故障/拖曳/重播focused通過；產品/契約FAIL完整測試包已交#145，不改#127/#135/#189，不解除gate。
5. A4/B4配置、來源hash/相機校正pins/範圍/磁碟/凍結收據的正式產製預檢完成，47檢查回報BLOCKED，未猜run/camera/clock核定或產正式資料。

原工程驗收快照當時 RETURN132列但0列有效（INCOMPLETE）。**2026-10-25 回收更新：yyin 的新 CSV 已驗證132/132 VALID（123 T、7 F、2不確定）；不再等待交件。** 回收包79/80固定檔相符、缺空白模板；意見處置、Claude獨立圖/ROI、必要HSV與設定核定/凍結、正式Q3獨立答案及#144/#183/#145前置仍待完成。詳見[最新回收與baseline啟動狀態](Q1Q5_R004_REVIEW_RETURN_STATUS.md)及其來源hash收據。原 RESULTS.json／LOCAL驗收紀錄保留歷史bytes，不回寫成新回收結果；既有D70授權不重問。

## 驗收與重現

LOCAL `$AMIDST_ARTIFACTS/q1q5-dynamic-baseline-v1_20261025/README.md` 是一次驗收入口，含完整ACCEPTANCE、source/context pins、原始逐次數據、已實跑重現命令與拒網路replay。程式與curated JSON上GitHub，完整RGB/私有producer/錄製/人工資料保持LOCAL。`Q1Q5_DYNAMIC_BASELINE_RESULTS.json` 是機器可讀實際結果。

既有checkout/index/原502項dirty逐hash/mtime保留；不建worktree、不換canonical分支、不改main/mainline、不merge。七個本任務暫用測試服務已按receipt/PID/UID/命令/唯一listener核對後停止；63408交付服務與共享Ollama97769保持運行。已知新目錄約972MiB（另套件快取未歸因），df剩約11.17GiB，高於8GiB門檻。
