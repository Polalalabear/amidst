> 已封存（2026-10-27，D91），見 [封存索引](../../archive/ARCHIVE_20261027.md)。

# DEMO_V1_HANDOFF.md：歷史交接公開整理

> 原文件日期：2026-10-23；公開整理日期：2026-10-26。
> 以下是當日交接紀錄，內文「目前／最新／仍需」、PR 狀態、效能與磁碟數字均屬歷史快照。
> 本文件沒有重新確認現行 G4、圖／參數凍結、正式產製、正式 baseline 或 Windows 狀態；其現況為 UNKNOWN。
> 本次只公開文字與來源 metadata，不構成 CX-4 整合產品、P1／P2／G4 驗收或 Windows 可執行包。

LOCAL 原檔：`q1q5-qwen3-contention-20261023/documentation-hardware-20261023/DEMO_V1_HANDOFF.md`；11,138 bytes；1 檔；SHA-256 `d6241ce385bc1a48a4e1affe09942be43ee33f8ef1b5d96a52fa26f307649fac`。這是原檔 hash，公開整理後的檔案 bytes 不同。

完整來源收據與驗證口徑見 [LOCAL_ARTIFACTS.json](LOCAL_ARTIFACTS.json)；公開入口與重現限制見 [README.md](README.md)。

## 原歷史內容（已移除私人路徑及個人審查者姓名）

# Demo v1基準與Windows交接要求

狀態：交接要求，非已可在Windows執行的程式包。沒有新模型測試／原始素材複製／對外傳送。


## Demo v1基準優先與跨機交接（2026-10-23，取代先比較／先優化的排序）

### 第一版的明確交付

使用者確定四原則：限制範圍；物件存在與框必須來自RGB模型，GT只在獨立評估；先用既有RT-DETR及成熟模組；Demo v1後才按量測瓶頸比較YOLO-World、進階ReID、新按需排程與Qwen。OpenAI仍延後。本次是規格／交接要求補充，沒有下載8B、跑新推論、改採樣／模型／正式期限，或宣告兩模式已完成。

最小展示範圍提案：每次只選一個凍結run、預設固定起訖時間、兩台已核定連通的攝影機、一次一個追查目標；查找可列同條件的多個觀測與鏡頭。資料產製仍沿既定A4/B4規格，不改原始資產或把未處理的鏡頭算入已覆蓋範圍。新選定子集須明示camera/time scope，兩台是否可用仍由獨立圖／ROI檢查決定，不能猜。

- **一次查找**：預設表單→來源綁定RT-DETR索引→列出全部相符鏡頭／框／來源時間→結束；未評估與缺圖分開。用既有支援類別，未啟用新開放詞彙。不把類別永久當成靜止物件。
- **持續追查**：由使用者選起始觀測→同鏡頭連接→既有RULE_ONLY依核定空間關係查候選→有影像證據才硬切→暫失／重新接回／搜尋結束如實記錄；身分UNCONFIRMED，缺口不補框或位置。保持現行核准參數；新LOST期限不得由LLM臨時覆寫。
- 固定一次入口與完整source／model／run／clock／index／graph／parameter pins；保存逐格detections、request/response、decision/link journals、replay、實際執行命令與環境收據。人工題目／答案及GT留給獨立評估端。

**目前證據仍不足以交兩模式正式數據**：engineering-qa-v4可重現實際kernels／HTTP／UI／replay，但bindings是SYNTHETIC、RGB MISSING；RT實測只讀8張真RGB preview，不含完整影片／UI。既有五個雙模式案例是在比後端事件與Agent trace，不是一次查找／持續追查的真RGB成效比較。不能改名當成v1已完成。

先處理#117靜態圖／8台出口獨立檢查與事件前凍結，再依已有D70授權續#115 RGB、必要設定核定及#118索引；解決#145／原kit差異後整合既有Q1／Controller／HTTP／UI Draft。#117最新仍只有交付通知，正式RGB/index仍NONE。縮小v1不自動解除G4或新HSV核定；某設定非v1必需可在新明確scope提案中停用，不能暗中跳過。此處沒有以Codex子代理讀檔冒稱Claude獨立檢查或使用者核准。

### 先交兩種模式的實測數據，再討論優化

| 項目 | 交付數據及口徑 |
| --- | --- |
| 索引建置 | 來源格數／覆蓋、模型呼叫數、總牆鐘耗時、單worker推論fps、模型與設定hash |
| 一次查找 | 冷／暖查詢的首筆及全部結果等待；逐查詢命中／誤報鏡頭與分母N（需獨立答案）；不把建索引耗時藏掉 |
| 持續追查 | 逐事件來源時間、實際無觀測間隔、接回／未接回／接錯、無證據切鏡、切換時刻；分清離線處理、來源時間與播放時間，不冒稱即時攝影機追蹤 |
| 系統 | 端到端處理耗時、UI實際fps／掉格與推論fps分列、RSS峰／swap活動、硬體與軟體版本 |
| 重現 | 相同凍結錄製在無模型環境重播的hash；另做新推論的行為／數值差異檢查，不預設CPU/CUDA浮點逐byte相同 |

先報逐次數值、N、中位與最大等待；樣本不足不湊P95或宣稱可靠率。成功／失敗及未覆蓋都保留。效能門檻需先寫定才算驗收，本節沒有捏造「快速」的毫秒標準或人工答案。

### LLM能否決定多久才追丟

可以輸出數字，但該數字最多是**搜尋預算提案**，不是可靠接回上限。文字模型收到「紅衣服的人」無法觀測速度；即便VL收到多格影像，公尺／秒仍需要時間戳、可用校正及對應的不確定性。速度估計宜由可重現程式處理，不能靠模型常識猜。

以距離／觀測速度估到達時間只會形成假設窗：人可能停、轉向，鏡頭可能漏檢，另一人可能衣色相同；低速度／零速度也不能推成無限等待。v1先沿固定且可審的規則，量測不同實際間隔的接回與接錯。0.6秒同鏡頭暫失、6秒候選搜尋窗仍不是經驗證可靠上限。將來若試LLM政策，必須限在核定範圍、記模型／輸入證據／建議值，最後由controller驗證；不能因LLM延長期限就說目標仍可靠可辨。

### 後續8B比較：能力與記憶體估算，非本機量測

若只做文字解析與結構化工具決策，先以Qwen3-8B作較直接的候選；Qwen3-VL-8B-Instruct可作文字模型，也能在日後測受限RGB畫面／裁切的視覺判斷，但不能預設VL較準、較快或能直接提供可信速度。純文字比較與含RGB的視覺比較需分組，避免增加輸入資訊後冒稱模型本身勝出。

官方Ollama所列下載量：[Qwen3-8B Q4_K_M](https://ollama.com/library/qwen3:8b-q4_K_M)約5.2GB；[Qwen3-8B F16](https://ollama.com/library/qwen3:8b-fp16)約16GB；明確版本[Qwen3-VL-8B-Instruct Q4_K_M](https://ollama.com/library/qwen3-vl:8b-instruct-q4_K_M)約6.2GB、含視覺projector。不能把舊latest的6.1GB與這個明確tag混成同一包。4-bit通常指權重，不代表KV／視覺運算全部4-bit。

以下為**起測預留估算，非官方最低／本專案實測或硬上限**。固定單模型／單請求、總context4096、輸出至多256tokens；VL至多一張不超過960×540的來源影像，processor resize／visual token數另記並算進總context。估算含模型runtime，不含整台OS／瀏覽器／RT常駐。

| profile | 模型工作記憶體預留 | Windows獨立GPU起測規格（非保證fit／速度） |
| --- | --- | --- |
| Qwen3-8B Q4_K_M | 約6–8GiB | 8GiB VRAM短context起測，12GiB更有餘裕 |
| Qwen3-VL-8B-Instruct Q4_K_M | 約8–12GiB | 12GiB起測，16GiB更有餘裕；多圖／高解析另算 |
| Qwen3-8B F16 | 約18–22GiB | 24GiB起測；CPU offload須另算RAM及延遲 |

若要同機RT、UI與這些後續比較，整機RAM以32GiB作工程預留較合適；本機16GiB不預設能承受VL併行且無swap。CPU可運行／offload不等於延遲符合需求，以上都要實測校正，現階段不採購或下載。

兩個官方8B文字骨幹config皆36層、8個KV heads、head_dim128；以FP16 KV估 `2×36×8×128×tokens×2bytes`，4096 tokens約0.5625GiB，32768約4.5GiB。這只是KV部分，還有權重、運算buffer、VL視覺編碼等；更多context、影像或平行請求會增加，**未固定工作量就沒有通用最高記憶體值**。來源：[Qwen3 config](https://huggingface.co/Qwen/Qwen3-8B/blob/main/config.json)、[VL config](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct/blob/main/config.json)。

### 外包Windows：可行範圍與交接清單

可交由另一台機器執行相同測試，**目前未做Windows啟動／推論／瀏覽器驗證，沒有已驗證的整包即跑承諾**。先區分：A錄製重播／UI驗證；B重新跑RGB模型＋兩模式端到端。A不需Qwen或RT權重，但要顯示真畫面仍需safe RGB；B才需RT推論環境和權重。v1不需要Qwen／VL、YOLO-World或Blender安裝。

| 必交內容 | 具體要求 |
| --- | --- |
| source | 完整經審source snapshot、frontend、單一整合SHA或COMPOSITION逐檔hash；單一Draft PR／canonical checkout不是目前完整工程 |
| environment | Python／uv、實際torch／torchvision／Pillow／PyYAML等版本及Windows CPU/CUDA profile；需JS測試時含Node版本。不要搬Mac .venv當Windows環境 |
| model | 官方RT-DETR exact source、81,001,853bytes weights的官方locator／SHA，preprocess640×640／FP32／threads／seed／threshold pins；可由受控下載核對，不需另一份Blender來源 |
| RGB | 授權run的安全RGB、frame/run/camera ID、來源時間戳／尺寸與逐檔hash；不讀Blender物件名、actor ID、路線或GT當答案 |
| space/time | 已核定calibration、連通圖／出口、clock mapping、參數與唯一source registry；只用於縮候選，不提供目標答案 |
| tests | 固定camera/time scope、兩種模式的結構化請求與入口、focused/schema/replay檢查及回收欄位；人工題目與答案不由Codex補造 |
| outputs | 已凍結baseline responses/journals及可信hash只供replay核對；新推論結果先凍結，再由分離的評估端讀答案／GT |
| relocation | portable root mapping及新配置file pins，保留原content hashes與遷移收據；不就地篡改舊原始manifest |
| return | hardware/OS/driver/runtime、完整命令／return code、逐查詢／事件結果、timings、RSS/VRAM/swap或pagefile、logs、screenshots與output hashes |

Windows差異已有具體位置：舊start_local_demo.py依賴fcntl／Homebrew／macOS 暫存目錄／lsof；.command使用Bash和.venv/bin/python；量測程式使用resource、df、vm_stat、sysctl、memory_pressure；連engineering-qa-v4的serve122.py也呼叫df。現有pyproject／uv.lock沒有完整重建本次RT環境所需的torch／torchvision／PyYAML，因此不能只給git clone＋uv sync就稱可重現。這不是所有依賴都不支援Windows；需獨立portable launcher／監測adapter與環境profile。WSL2是候選執行環境，未驗證且不能解決macOS專屬監測命令本身。

GT／人工答案／評估劇本放獨立evaluation包／權限，推論包不含；也不搬原.blend、原始資料庫、Mac環境、憑證或舊state。若正式入口仍依賴舊PG，須在交接前明確處理，不能把舊PG/state直接複製成新Q線來源。本次沒有複製、傳送或上傳原始RGB／模型／GT；只產交接要求與待補狀態。


### Windows交接補充：硬體說明與審查順序

先做圖／出口ROI／必要設定的前置審查，再產正式RGB／索引與兩模式baseline；第一版輸出凍結後即可交組員T/F及做baseline評估，不等LLM／進階追蹤模型比較。後續比較依v1結果排程，新增行為另驗證／審查。

每台測試機需填：Windows版本/build與原生/WSL2；CPU完整型號、實體／邏輯核心與本次threads；RAM總量及執行前可用量；GPU型號、獨立VRAM總量／可用量、驅動、CUDA/torch版本與實際device；磁碟總量／可用量／輸出位置；電源模式與同時運行的模型／背景負載。沒有GPU要明填NONE，查不到的欄位填UNKNOWN，不從共享記憶體或錯誤的32-bit AdapterRAM猜VRAM。

baseline先保持既有RT-DETR CPU/FP32/2threads/640×640的可比profile，不要求Qwen或獨立GPU；這不是Windows最低硬體或fps保證。CUDA另列profile。後續8B沿上表受限context的RAM/VRAM估算，不在v1偷換模型；整機RAM與GPU VRAM分開記，不能把兩者相加當可用VRAM。交接前與產製前後記磁碟可用量，低於原8GiB門檻停止。
