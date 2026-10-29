# Qwen3／RT-DETR 實測、改善與遷移評估（2026-10-23，依 #144 提案）

公開 locator 約定：`$AMIDST_ARTIFACTS` 代表審查者自行指定、canonical 絕對路徑的 LOCAL 證據根目錄，`$AMIDST_SOURCE`／`$SOURCE` 代表按 composition 還原的工程，`$AMIDST_PYTHON`／`$AMIDST_PYTHON_ENV` 代表既有 Python executable／環境。這些是去識別化 locator，不宣稱其他機器已存在對應資料；先取得相同 hash 的 LOCAL 檔案並設定環境變數。GitHub 只有公開程式與精簡收據，完整 RGB、錄製、模型 wire 與原始命令紀錄仍為 PRIVATE／LOCAL。文中的歷史數據未因路徑去識別化而重跑。

> **當前優先序（使用者2026-10-23新指示）**：Scope／Evidence／Baseline First。先以既有RT-DETR、成熟模組與RULE_ONLY完成「一次查找／持續追查」的有界真RGB端到端基準，再做模型、ReID、新按需排程及Qwen優化。下文既有量測保留歷史口徑；先前比較／優化建議不再排在Demo v1之前。詳見文末「Demo v1基準優先與跨機交接」。

本次完成：只讀遷移評估、三組實際資源對照、完全卸載Qwen的額外RT對照、v2 schema／工具進度實作、原預算與長診斷／replay驗證。**沒有正式遷移舊state／DB、沒有啟動產品server、沒有證明Agent已能有效追蹤。** 原始負面實驗保留，不把較長診斷當正式預算通過。

結論：生成期間RT-DETR吞吐顯著下降，單純常駐模型的影響在這輪很小；併發區間沒有新增swap或swapin/out。Q3的型別／原文問題可藉封閉詞表與schema改善，但輸出tokens增加、等待變長。Q5從重複工具變成合法返回，仍沒有Agent切鏡，追蹤效用未驗證。現有2秒呼叫／5秒總預算仍不滿足。

## 量測條件與界線

- Apple M3／16GiB；Ollama0.35.0，既有 `127.0.0.1:11437`，Qwen3 1.7B Q4_K_M manifest/API digest `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`。沒有下載任何權重，Qwen2.5已移除且沒有恢復。
- 官方RT-DETR R18，code `df2a96c8c3a098567a1149bf0248da6efe6d495d`，weights SHA-256 `3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0`，torch2.6.0／CPU／2threads／FP32，輸入640×640。重用既有deps；沒有安裝新套件或改官方source。
- 八個不同鏡頭各一張既有r004 preview RGB輪替（CAM_WIDE取已選90°），只讀RGB bytes；非正式A4/B4事件run。先解碼八張圖，計入每張resize／forward／postprocess，不計檔案讀取與預載；單一worker無sleep飽和跑，非九鏡頭即時流。
- 每組順序：Qwen常駐閒置→RT單跑（Qwen仍常駐但不生成）→Qwen單跑→並跑，穩態至少30秒；另外完全卸載Qwen再跑RT。RT預載與一張warmup在resource trace中另標，不進forward統計。
- Qwen只用固定SYNTHETIC Q3／Q5輸入，各重複3次，temperature0、seed7、context4096、cap256、think=false；不是三題／正式accuracy。資源對照每次provider允許30秒，僅診斷；未放寬產品Q5 D65 call2000ms／total5000ms，Q3 2000ms仍PROPOSED。
- 約每0.5–1秒採樣process RSS、vm_stat（實測page16384bytes）、swapusage、memory_pressure -Q、Ollama api/ps。RSS、API size_vram和系統壓縮頁是不同量，不相加冒稱實體RAM。
- 其他桌面程序不停止，phase順序未隨機化，也沒有GPU利用率／頻寬／溫度profile。因此可報觀測差異，不能精確歸因CPU排程、頻寬、thermal或宣稱一般硬體benchmark。P95僅N≥30，全部逐次值保留。

## RT-DETR實際容量

| 條件 | 張數N | 每張中位ms | phase吞吐fps | worker CPU秒/牆鐘秒 |
| --- | ---: | ---: | ---: | ---: |
| Qwen完全卸載 | 96 | 295.62 | 3.129 | 1.87 |
| 原模板：Qwen常駐、無生成 | 97 | 296.92 | 3.108 | 1.86 |
| 原模板：並行生成 | 19 | 1987.79 | 0.619 | 0.99 |
| 最終v2：Qwen常駐、無生成 | 95 | 300.75 | 3.114 | 1.88 |
| 最終v2：並行生成 | 32 | 1854.11 | 0.554 | 1.13 |

完全卸載與常駐無生成都約3.1fps；原模板生成期間降至0.619fps，最終v2生成期間0.554fps，後者相對同組無生成下降約82.2%。CPU秒／牆鐘秒由約1.88降至約1.13，支持生成時有明顯的共享資源競爭；未量測的底層機制仍UNKNOWN。

若需求是9台各5fps，總需45fps；此單worker本次離線容量約3.1fps，生成時約0.55fps，**不支持直接宣告可即時跑9台**。即使單台5fps也高於本次量測吞吐。這是容量對比，不是正式多鏡頭runtime驗收或偵測正確率。

## 記憶體與swap：實際數字

單位MiB；下表是穩態採樣峰值／差分，未把模型size_vram加入RSS。

| 條件 | RT RSS峰值 | Qwen runner RSS峰值 | 系統compressor峰值 | swap使用起→迄 | swapin/out新增 | pressure free最低% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen完全卸載 | 759.1 | 0.0 | 4004.7 | 2961.0→2961.0 | 0.06/0.00 | 60 |
| v2 RT單跑／Qwen常駐 | 653.4 | 1835.2 | 3917.1 | 2961.0→2961.0 | 0.00/0.00 | 49 |
| v2 Qwen單跑 | 0.0 | 2082.7 | 3769.7 | 2961.0→2961.0 | 0.00/0.00 | 49 |
| v2並行 | 693.6 | 2075.9 | 4236.9 | 2961.0→2961.0 | 0.00/0.00 | 46 |

`memory_pressure -Q`的free百分比是系統可回收／可用狀態指標，**不是空閒實體RAM百分比**。vm_stat真正Pages free最低曾僅約56MiB，不能單靠這一數字判定記憶體耗盡；同時要看壓縮、swap活動和pressure指標。Qwen API回報size_vram固定約1786.6MiB／context4096，與runner RSS有共享／映射關係，不能重複相加。

開始前已有約2.91GiB swap；測量期間多數穩態為2961MiB。兩個主要並行階段swap使用差、swapin與swapout均為0，故**這輪沒有證據把RT降速歸因於新swap I/O或swap擴張**。這不等於系統無記憶體成本，也不證明更長／更多模型負載仍安全。

## Qwen輸出改善與成本

| 固定單次輸出測試 | 原模板單跑中位s | 最終v2單跑中位s | 最終v2並跑中位s |
| --- | ---: | ---: | ---: |
| Q3一次解析 | 4.907 | 6.691 | 7.685 |
| Q5第一次模型輸出 | 3.893 | 10.454 | 11.428 |

Q5原模板是工具請求，v2是完整返回決策，輸出任務大小不同，不宣稱純模型速度比。Q3輸出token93→128；Q5首次輸出75→185。新schema／完整ID／固定audit欄位增加token成本，單靠禁止重複工具無法達到2秒。

初版schema實驗 `guided/` 只修正型別，仍漏class且把時間填date，Q5返回理由過長；其單跑中位Q3 6.947s／Q5 10.523s。這些負面數據和當時source保存在 `experimental-guidance-source/`，沒有抹掉再挑漂亮結果。

最終實際controller長診斷（call30s／total90s，複製SYNTHETIC bindings）三次：Q3 **3/3**通過原validator，session中位6.428s；Q5 **3/3**有合法Agent決策、每session兩次RETURN_TO_ORIGIN，中位20.790s，**0次Agent SWITCH**。不是正式accuracy、不是追蹤成功，不能以「合法返回」取代有效跟隨。

最終原預算probe：Q3與Q5都PROVIDER_TIMEOUT，規則接管；replay一致。因此v2是明確版本化、供review／對照的profile，沒有提升正式budget或證明即時Agent可用。預設Demo仍RULE_ONLY，既有v1設定檔沒有被就地改寫。

## 同一份紀錄的歷史對照索引

以下保留不同階段的口徑；不能把raw envelope、native controller、單次輸出與整段session混成純模型A/B。所有等待值均來自既存檔案，本次文件補充沒有重跑模型。

| 階段／輸入 | Q3等待 | Q5等待 | 結果與來源（LOCAL） |
| --- | --- | --- | --- |
| 最初Qwen2.5 raw診斷 | 單次14.726s；冷載入另6.645s | 單次至少15.003s，timeout | Q3 task INVALID；`q1q5-qwen-diagnosis-20261023/`，原始等待保留 |
| 相同native機械輸入，Qwen2.5 7B，N=3 | 觀測等待中位28.551s，含1次timeout | session中位60.906s，含1次timeout | Q3/Q5各0/3 task採用；`q1q5-model-compare-20261023/COMPARISON.json` |
| 同組native輸入，Qwen3 1.7B，N=3 | 中位4.380s | session中位10.136s | Q3/Q5各0/3 task採用；同一COMPARISON，非正式題庫 |
| Qwen3切換收據 | 明確管理載入2.584s；原2秒probe仍timeout | 原2秒probe仍timeout | `q1q5-qwen3-switch-20261023/`；2.5權重移除，等待／raw／replay保持 |
| 本報告最終v2資源對照，N=3 | 單次輸出單跑6.691s／並跑7.685s | 首次完整決策單跑10.454s／並跑11.428s | 本報告MEASUREMENTS；不是整段Q5 session |
| 本報告最終v2實際controller，N=3 | session中位6.428s，3/3採用 | session中位20.790s，3/3合法返回、0 SWITCH | call30s／total90s診斷；原預算仍timeout，非追蹤驗收 |

前四個資料夾都位於 `$AMIDST_ARTIFACTS/`；本報告完整原始根目錄為 `$AMIDST_ARTIFACTS/q1q5-qwen3-contention-20261023/`。歷史模型比較用seed7/8/9、temperature0.7，本次資源對照用同輸入seed7、temperature0；不得跨階段推導固定加速倍率。native比較的四個2秒probe皆timeout；16段session都可無模型精確replay。

## 問答補充：常駐、生成、同跑與瓶頸

- **模型存於磁碟**：權重存在，但不代表模型已載入或正在運算。刪除舊2.5權重主要釋放儲存空間；卸載Qwen3記憶體不會刪除它的權重。
- **Qwen常駐、無生成**：runner與模型已載入，等待請求；不是不斷讀取鏡頭。RT在這種狀態約3.114fps，完全卸載Qwen約3.129fps，這輪差距很小；但常駐runner RSS峰1835.2MiB仍有記憶體成本。
- **Qwen生成**：收到一次文字／結構化觀測請求，處理prompt並逐token產生JSON／工具／決策。這裡的Qwen3 1.7B文字模型不直接看RGB；RT-DETR才負責像素偵測。
- **與Qwen同時生成／同跑**：本量測專指RT worker做偵測的時間區間，與Qwen實際處理請求的區間重疊；不是只把兩個服務打開，也不是只測模型放在記憶體。RT雖用CPU，同一台M3仍有共享運算／記憶體資源；不能未經profile就斷言是某一條頻寬或GPU滿載。

具體已觀測瓶頸有兩個：RT單worker自身約3.1fps的容量，以及Qwen生成重疊時降到0.554fps的資源競爭。Qwen完整決策本身也需約10–11秒，與原2秒call預算不符；schema／長ID增加輸出token，是已觀測成本。兩個主要並行穩態沒有新增swapin/out，所以本輪不把瓶頸說成硬碟換頁。影片解碼、瀏覽器多畫面、傳輸、長時間佇列尚未納入本輪，這些仍UNKNOWN。

## 按需偵測與播放分流（使用者提案評估，尚未實作）

方向合理：**播放讀媒體；偵測只讀被排程取樣的RGB；審核讀凍結的觀測與決策紀錄**，三者以相同source/run/camera/clock/frame pins對齊，審核資料與GT不回流推論。以下以目前預錄／生成影像為主；即時串流僅說明未來差異，不把它加入本次交付。

| 狀態 | 顯示與後端工作（提案） | 限制 |
| --- | --- | --- |
| 未查找 | 多鏡頭播放；不因每次顯示frame而呼叫RT／Qwen | 同時解碼所有影片仍會占資源；可用低解析概覽與有限緩衝，實際節省未量測 |
| 開始查找 | 指令只解析一次；若有合法既有索引先查索引，選出結果才顯示該畫面；缺索引時按需掃描指定時間／鏡頭 | 尚未掃到結果不能宣稱已找到。顯示SEARCHING／保留當前畫面，Qwen不是RT的逐格觸發器 |
| 追查中 | 排程取樣當前與圖上合法候選鏡頭；背景產生帶證據的觀測事件，controller驗guard後才切畫面 | 快速例行動作可用RULE_ONLY；Agent mode的呼叫／切換政策仍須契約review，不因flag繞過guard |
| 審核 | 重播同一份已記錄畫面、觀測、缺口與決策 | 預設重用結果，不再啟第二套相同推論；權限與GT隔離維持 |

「開始查找就先調出追查到的畫面」需要既有索引、快取或使用者提供的起始觀測。若都沒有，系統仍需先掃RGB，第一筆結果有等待；不能預先知道目標在哪台。當前正式r004事件run／index仍待#115／#118，不能假裝正式索引已可用。

預錄影像適合在核准輸入到位後離線建一次索引，按frame hash＋模型／前處理版本pins重用，再讓播放／查詢讀索引；若只在查詢時建，會把掃描等待移到第一次查詢。即時來源若完全停掉查詢前的取樣，就沒有查詢前歷史；需要受限的壓縮媒體保留或另提稀疏索引，不能讓「沒有掃到」變成「目標不存在」。

容量要分成**送入量**與**實際處理能力**：按需取樣能降低平均工作量、佇列和舊frame等待，但不會自動把RT約3.1fps的服務能力變成45fps。以下只是容量算式，不是已核准採樣率或追蹤正確率：

- 9台各5fps＝45frames/s；9台各1fps＝9frames/s，都超過本次單worker約3.114fps。
- 9台各3秒一張＝3frames/s，已接近飽和，幾乎沒有Qwen／解碼／抖動餘裕。
- 9台各5秒一張＝1.8frames/s，約占無生成容量58%；會增加漏掉短事件的風險，不能以省資源為由直接採用。
- 若Qwen生成重疊，對照期容量只有約0.554fps，連1.8frames/s也會積壓。這是phase平均，不能當每一瞬間固定的服務率。

記憶體節省要看保留什麼。停止送RT frame會減少工作與暫存；若RT與Qwen仍載入，模型的固定成本仍在。本次RT worker RSS約653–759MiB，Qwen runner約1835–2083MiB；它們包含runtime／buffers，不能當純權重大小，也不能再加API的size_vram重複計算。

作為**容量估算而非實測**：960×540 RGB uint8一張1,555,200bytes（約1.48MiB）；若在RAM保存9台×5fps×30秒完整解碼畫面，單是像素約1.96GiB，尚未算物件、decoder、tensor與副本。同尺寸RGB float32像素需4倍空間。避免完整解碼歷史常駐、只保留有界待處理frame，比單純把UI分兩個頁面更能針對這類成本；本次八張預解碼測試沒有證明產品實際存在這種1.96GiB積壓。

## 建議優先序與下一輪量測（提案，未變更正式參數）

1. **目前預錄Demo先重用來源綁定索引**：等核准run與正式索引到位，查詢／播放不重複推論。同一frame的結果以來源／模型／前處理pins快取；索引缺失與時間覆蓋缺口明示，不能只快取命中畫面而把未覆蓋當negative。
2. **有界排程與frame生命週期**：一個RT worker、依合法鏡頭與時間取樣，限制解碼池／待處理佇列／tensor副本。即時待處理工作可每鏡頭保留最新frame、合併過期pending工作並記錄跳過／stale；離線完整建索引及正式評估不能套用靜默丟frame。播放可維持流暢FPS，偵測FPS另設，但仍須量測decoder競爭。
3. **減少Qwen生成次數與輸出體積**：每個新指令解析一次；同文快取須綁catalog／prompt／model pins。例行觀測處理保持決定性，語意或有歧義的決策才進模型。compact decision與預取證據的一次決策模式列§14選項，不能為了加速私自改契約／修補輸出；先維持單一LLM請求，不增加模型併發。
4. **以記憶體／首答等待取捨Qwen常駐**：活躍session可保留，長時間閒置可卸載模型；Ollama服務與權重保持。管理載入曾實測2.584秒，是另一輪載入值，不保證每次相同；每次用完即卸載會讓每次請求多付載入成本。Ollama支援keep_alive控制，平行請求還會增加context記憶體，見[官方FAQ](https://docs.ollama.com/faq)。本次沒有重啟共享server或修改其全域設定。
5. **生成／偵測調度先做對照再選**：減少重疊可能改善RT速度；完全串行卻可能讓約10秒的Qwen決策造成觀測空窗，必須有時間戳、stale／gap與回補政策，不能直接停偵測後仍稱持續監看。RT的MPS／其他後端及更小context另做相同輸入的正確性／效能對照，不能宣稱換裝置必然更快或更多worker必然增吞吐。

下一輪應固定來源與輸入範圍，比「持續全範圍推論／按需取樣／預建索引重用」：記錄各狀態Qwen生成占空比、實際解碼與推論張數、佇列長度與最老frame年齡、查詢首筆延遲、事件至切鏡延遲P50/P95、RSS／compressor／swapin-out／disk與時間覆蓋缺口。另以組員凍結標註評估短事件漏失；本次不產生答案，也不把容量估算當實測效益或新增正式採樣／LOST門檻。

以上問答是同一份量測紀錄的文件補充。舊401檔MANIFEST與原始source delta保持不變；新版文件存於獨立documentation-followup目錄並另有hash收據，由CURRENT指向。先前270／56項測試屬原程式head的歷史checkpoint；本次只驗文件diff、來源數字、連結與既有artifact hash，不宣稱重跑推論或程式測試。

## 實作內容及保留邊界

- 新 `q3_parse_v2.txt`／`q5_agent_v2.txt`，保留v1。Q3給完整JSON Schema；可填class/color/camera/region值只取已存在server aliases在USER_TEXT中出現的原文片段，時間／日期用既有versioned lexical patterns，不餵人類答案。原文大小寫保留。這是程式協助縮小輸出空間，不能宣稱模型獨立語意能力提高。
- Q5明列phase、已完成工具、當前candidate、合法下一步與citation refs；decode schema不再提供重查context／observation，仍允許返回。現有工具dispatch／guard、SWITCH強證據與entry、NEXT非空引用、候選順序、round／timeout完全不改。無觀測NEXT與LOST時限仍待§14決定。
- rationale使用固定動作標籤，**不是模型自由推理或新的證據**。模型選action；controller保留全部pins／guard並執行。這次沒有實作「compact decision由server擴展長IDs」或「一律先預取候選再問模型」的新mode。
- native v2記 `q-demo.ollama-native-chat.v2`＋完整wire schema／hash；v1/raw replay保持。Q3模板版本顯式傳遞，診斷按已驗file pin的原audit版本選模板，schema建構也計入單次deadline。
- Q5/shared helper更新在原[PR #172](https://github.com/Polalalabear/amidst/pull/172)，head `1bb4135965fb53643e9fbbaf8e41fd77e8ffb9c8`；runtime／Q3／量測在[PR #174](https://github.com/Polalalabear/amidst/pull/174)，依賴前者，沒有把整個Agent重複加入HTTP PR。兩者B／Draft，未merge。

## 遷移評估

只讀pin了舊phase1五檔（啟動command、start_local_demo、local_agent provider／contracts、agent_provider.json），保存在 `MIGRATION_AUDIT.json`，沒有查改DB、state或另一checkout。舊config仍指向已刪的2.5，啟動器找不到模型會拒絕。

| 項目 | 舊phase1 | 新Q線 | 遷移判斷 |
| --- | --- | --- | --- |
| Ollama服務／store | 既有11437與同一模型庫 | 同一loopback，可pin Qwen3 | 可沿用，核對owner／digest；不重啟／複製權重 |
| Agent輸出 | ModelAction kind=tool/clarification/answer/refusal | Q5 SWITCH/NEXT/RETURN＋typed tools | 不相容，不能只改model tag |
| 預算／context | timeout120秒、8192ctx、keepalive10m、未設think | Q5 call2秒／total5秒、4096ctx、think=false | 不複製舊值，不默默放寬新契約 |
| 啟動／state | PG＋舊state＋python -m amidst.workbench | Office Application＋唯一run registry／media pins／recording | 建新Q線入口；不把舊state當r004 inference來源 |
| 資料／UI | 舊資料與其流程 | primary frontend/workbench與Q API；其他Draft UI仍待整合 | UI路徑／授權／媒體驗收另做，不把靜態頁當runtime |

建議遷移順序：先凍結完整工程source與recorded replay入口，再接approved run/index/graph/parameter/clock/media registry，明填四個registry/runtime環境變數與獨立file pins；先驗bootstrap、同origin/session/scene、media grants與無模型replay，再做真模型及瀏覽器驗收。缺registry仍NOT_READY，不能用合成fixture補成正式Demo。此處未產生假的可啟動正式registry或宣告完成遷移。

實測顯示，即使遷移入口完成，RT容量與2秒Agent預算仍是獨立阻擋。近期可交付的仍是RULE_ONLY／recorded replay；即時Agent需先處理輸出體積與RT調度，並補量測。只以減少模型常駐記憶體作解方，與本輪數據不符。

## §14待決選項（未分配正式編號，未實作）

1. compact Agent輸出由server依當前已pin的context擴展完整IDs／hash，保留raw→expanded映射與guard；用來減少185-token決策成本。需契約review，不能當成已准schema或output repair。
2. 候選證據由controller先備妥，Agent只判一次action，與原sequential tools並列比較；不能繞過證據／citation或把候選先驗當觀測。
3. RT與LLM生成的調度／取樣策略及CPU/MPS相容性另做實測；本次未更改正式裝置、採樣率、Q5預算或未核定的LOST時限。

## 驗證與重現

工程組成focused **270 PASS**；#172原typed-tools／Agent focused另 **56 PASS**（有重疊，不相加）。全部長診斷6筆response/journals、歷史2.5 Q3/Q5都在最終source以0模型呼叫精確重播；12個最終實測wire payload與最終builder相同，包含大小寫／deadline修正後的驗證。

原#127 pin `994d34c8340855dbf0e28d0273851049df5e6c7d` 全包未改、沒有--only：長診斷Q3 56 PASS；Q5 148 PASS／15 FAIL／4缺context。原預算Q3 56 PASS；Q5 133 PASS／14 FAIL／3缺context。長診斷多一筆decision導致同類D69 counter schema多一FAIL；links/counters/classifier差異沿#145/#170，未隱藏。初次exporter未配對的report保留，後以新檔名配對而不改domain bytes；配對收據可核對。SEARCHING_TRIGGER_TIME缺context仍不是PASS。

LOCAL `$AMIDST_ARTIFACTS/q1q5-qwen3-contention-20261023/CURRENT.md` 是最終入口；包含MEASUREMENTS、每次wire／envelope／逐張timing／resource JSONL、來源pins、COMMANDS、CONFORMANCE-FINAL、REPLAY_FINAL_SOURCE、WIRE_FINAL_SOURCE、MIGRATION_AUDIT與source delta。模型／媒體沒有複製。每次產製前後df，量測監測8GiB門檻，結束釋放本次模型記憶體，既有服務不重啟。

重跑範例（`SOURCE`為按composition還原的完整工程；config必須新建／核對pin，output必須新目錄）：

```sh
: "${AMIDST_ARTIFACTS:?set the LOCAL artifact root first}"
: "${AMIDST_PYTHON:?set an existing Python executable}"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$SOURCE/src:$AMIDST_ARTIFACTS/local-work/amidst-q1q2-d63-20261020/deps" \
uv --no-cache run --no-project --offline \
  --python "${AMIDST_PYTHON:?set an existing Python executable}" \
  python "$SOURCE/scripts/measure_q1q5_contention.py" \
  --config "$AMIDST_ARTIFACTS/q1q5-qwen3-contention-20261023/measurement-grounded-config.json" \
  --config-sha256 e62471745a9376cd59796ed5f1e7aa09fd119944406182ea8d86abe47384e584 \
  --output "$NEW_OUTPUT" --profile guided
```

deps／upstream仍是LOCAL既有環境，沒有聲稱永遠存在；RT weights與preview輸入須按config pin核對。舊2.5推論需重新下載，歷史replay不需模型。正式r004／G4/G6、人工題目答案、正式準確率、真LLM下游provenance與Claude瀏覽器驗收仍分開未完成。


## 資料流、生成分時與未完成清單補充（2026-10-23）

本節只讀核對目前工程實作／原始錄製及GitHub狀態，沒有新推論。機械可讀的完整欄位、Q3 generic JSON Schema、Q5當次動態schema與既存SYNTHETIC輸出放在LOCAL `documentation-dataflow-20261023/DATA_DEFINITIONS.json`；這是程式現況說明，不是新契約、人工題目或標準答案。

### 實際生成包含什麼

一次請求會經模型載入（如有）、prompt evaluation／prefill、逐token decode、返回JSON。think=false僅關閉思考輸出；JSON欄位、長IDs、標點及空白仍須生成。讀prompt與生成tokens都會占運算資源。Ollama[API欄位](https://docs.ollama.com/api/chat)分別記load_duration、prompt_eval_duration及eval_duration。

| 已存在錄製（第一輪單跑，不是新的實驗） | 呼叫等待 | prompt evaluation | token generation | 輸出tokens |
| --- | ---: | ---: | ---: | ---: |
| guided-grounded/qwen-only/q3-0.json | 7.617s | 0.848s | 6.747s | 128 |
| guided-grounded/qwen-only/q5-0.json | 12.868s | 2.962s | 9.867s | 185 |

其餘時間含載入／傳輸／封裝；這不是拿各中位數相加。0.554fps是壓力對照的**整段concurrent phase平均**：RT飽和處理，同時按Q3→Q5順序連續重複三次呼叫；不代表使用者打一次字後，RT永久只有0.554fps，也沒有逐格隔離prefill和decode的個別因果。

Q3完成正常請求後即無新任務；權重可依目前wire keep_alive=60s留在記憶體。Q5 AGENT_SEQUENTIAL則可在SEARCHING期間再次呼叫模型：取候選證據→下一次模型讀工具結果→提交決策；下一次追查事件也可能重啟。RULE_ONLY不呼叫模型。provider只有HTTP timeout，沒有server端已停止生成的確認收據；不能把客戶端timeout當server立刻待機，取消完成時間仍待量測。

### 目前Qwen輸入與輸出

| 路徑 | 輸入／輸出現況 |
| --- | --- |
| UI文字預設 | `textRequest`／`buildQ3`預設parser_mode=RULE_ONLY，因此文字不必然進Qwen。只有明選LLM_WITH_RULE_FALLBACK才走Q3模型解析 |
| Q3公開請求 | schema_version、session_ref、text、locale=zh-TW、context={scene_id,run_ids,clock_mapping_sha256}、parser_mode；context由server核對單一註冊run |
| Q3送模型 | system=版本化prompt＋CLOSED_CATALOG（class/color/camera/region labels與aliases）；user=text。沒有RGB、偵測結果、GT、答案或完整使用者歷史 |
| Q3模型輸出 | schema_version=q-demo.q3-llm-output.v1；intent=FIND_CAMERAS/FIND_PERSON/EXPLAIN/UNSUPPORTED；class_term/color_term為原文字串或null；time_literal={start,end,date}為原文字串或null；camera_terms/region_terms為原文字串陣列；needs_clarification布林、clarification_question字串或null |
| Q3輸出後 | server驗schema、原文、封閉詞表、使用者條件與clock，再組q-demo.q1-request.v1或q-demo.q2-request.v1；只有PARSED才執行，不能讓模型直接執行查詢 |
| Q5送模型 | system=版本化Agent規則；user=JSON物件context、last_tool_result、remaining、v2 workflow。context含session/decision/snapshot hash、SEARCHING、最後觀測、出口解決狀態、有序候選、游標與剩餘round/time |
| Q5觀測 | observation_id、frame_ref、timestamp_us、camera_id、class_label、bbox_xyxy_px、score、color_verdict。frame_ref是引用，不是像素；score不是正確率 |
| Q5候選證據 | q-demo.candidate-evidence.v1，包含時間窗、target_presence、evaluated/not_sampled/not_inferred/missing計數、coverage_complete、entry觀測、best_observations、evidence hash等；未取回不能當不存在 |
| Q5模型輸出 | 工具envelope={tool,arguments}，或decision={schema_version,session_id,decision_id,candidate_snapshot_sha256,action,candidate_ref,cited_observation_ids,rationale}；action只有SWITCH/NEXT_CANDIDATE/RETURN_TO_ORIGIN |
| Q5工具與執行 | get_search_context/get_candidate_evidence/get_observation_summary/submit_decision。它們讀已pin索引，不呼叫RT、不直接切畫面；controller檢查引用、順序、snapshot與SWITCH強證據／entry後執行。v2每次動態限制合法分支；空證據NEXT缺口仍是#183 |

兩路Qwen3的wire都是/api/chat、stream=false、think=false、format=JSON/schema、context4096、輸出上限256tokens、keep_alive60s。每次只帶system與這次user資料；Q5進度來自server context／上次工具結果，並非模型自主在背景看所有鏡頭。正式產品尚缺run registry；本次CPU/LLM並行是獨立量測工具，不表示正式產品正在持續跑模型。

### 預設時間／地點與自由文字的對應

建議以結構化表單處理已知條件，不把選單重新轉成文字交Qwen猜。現有T2 Draft已有類別、顏色、來源起訖微秒的手動表單，直接組Q1/Q2；Q1 model helper已有camera_ids／region_ids，但目前view沒有地點選單，時間也還不是友善的預設時段。Q3→Q2 FIND_PERSON目前遇camera/region篩選會回Q2_SCOPE_FILTER_UNSUPPORTED；追查起點地點的語意／接線仍需定義，不能假稱已支援。

自由文字僅補支援範圍內的別名／語意。Qwen不能讓COCO detector憑文字辨識背包品牌、臉部身分或未支援屬性；超範圍保持UNSUPPORTED／澄清，不悄悄忽略。表單優先＋自由文字補物件的整體互動仍提案，不在本輪改UI／正式API。

### 磁碟、載入記憶體、顯示FPS與正確率

| 項目 | 具體數據與口徑 |
| --- | --- |
| Qwen3 1.7B Q4_K_M模型磁碟 | api/tags size=1,359,293,444bytes＝1.266GiB；模型tag如此命名，metadata parameter_size報2.0B，保留兩者，不自行更名 |
| RT-DETR R18 checkpoint磁碟 | stat=81,001,853bytes＝77.249MiB；未含共享Python／torch／Ollama依賴、快取或RGB |
| Qwen載入後閒置RSS | guided-grounded/idle-loaded 30.397s、53次採樣，峰1867.516MiB；不是全系統新增實體RAM，也不是兩模型都閒置的共同基線 |
| Qwen常駐＋RT運行 | RT RSS峰653.422MiB、Qwen runner峰1835.156MiB；吞吐3.114fps（95張），每張中位300.746ms |
| Qwen生成＋RT運行 | RT RSS峰693.578MiB、Qwen runner峰2075.938MiB；吞吐0.554fps（32張），每張中位1854.112ms |
| 尚缺的基本消耗 | 兩模型同時載入且都閒置的完整共同baseline、完整產品解碼／UI RSS尚未量測；不可把上述運行峰值冒稱純權重底耗 |
| 顯示FPS | 未量測正式多鏡頭瀏覽器顯示FPS、掉格率或端到端延遲。3.114／0.554是單worker總偵測吞吐，不是每鏡頭或UI FPS；正式事件規格5fps仍是#115預定來源採樣，不是已達成的顯示效能 |
| RT／HSV正確率 | UNKNOWN：無正式凍結人工標註分母，不能提供precision/recall/mAP或衣色準確率。35個preview框中5框同時紅藍STRONG是歧義證據，不是準確率 |
| Qwen正確率 | 正式語意／決策／追蹤準確率UNKNOWN。長診斷同一SYNTHETIC輸入重複Q3 3/3採用、Q5 3/3合法RETURN但0 SWITCH；原2秒probe仍timeout。不能報100%準確或把0 SWITCH當0%追蹤準確率 |

本輪只GET核對已安裝模型與api/ps，Qwen3 digest仍是原pin、api/ps models=[]：當下模型未載入；上表是歷史「載入後」量測。沒有為了核對而重新載入。API size_vram1786.64MiB不可再次加到RSS，峰值也不能相加冒稱兩程序同時峰值或實體記憶體總需求。

### 尚未完成（核對議題留言與PR狀態，不把OPEN等同沒寫程式）

1. #145對齊原#127：#133時鐘、#153無顏色、#156分頁、#170 D69 links／counters／flags等差異重驗；Codex不改獨立測試包。
2. #144／#183及§14決定：空證據NEXT、正式LOST語意／期限、Q3 lineage／failure provenance，以及compact decision／預取證據mode等提案；不能私改已准值。
3. #117對#116／#163的8台出口與靜態圖做獨立檢查、完成事件前凍結／G4；#116提案已交，不是還沒畫ROI。
4. #114／#158新HSV Q-19獨立檢查與核定；不否定已存在的舊§11初值G6。
5. #115正式A4 4台／B4 5台，各30s、5fps、960×540與safe bundles；已有D70授權，卡獨立圖檢查，輸出仍NONE。
6. #118以正式RGB及核准設定產製index、coverage／clock/hash／耗時收據；正式index仍NONE。
7. #108／#154、#109／#157、#110／#169、#111／#172程式已有Draft，待契約／原kit差異處理後重驗整合；不是四套程式都未寫。
8. #186改善／驗證真Qwen：原2秒預算、合法且有效的SWITCH、工具多回合與timeout後server停止時刻；已有schema改善與無模型replay，尚不能宣稱Agent跟隨可用。
9. 按需取樣、播放／審核分流、有界佇列、LLM生成占空比與解碼／UI完整量測；目前只有提案和獨立RT/LLM壓力對照。
10. #112／#174正式runtime／scheduler／source registry與#80真RGB接線；舊phase1 state／action／PG入口遷移未完成，不可只換model tag。
11. #119–#122／PR#175/#176/#177/#180接共用工作台、正式資料與模型／事件；四個T階段已有Draft，未完成正式整合／驗收。
12. #184／#185雙模式已有SYNTHETIC／replay原型；還缺真Qwen與相同正式RGB來源的端到端效果比較。
13. 表單預設時間與地點／文字物件的產品流程；已有基本手動表單，地點view與Q2範圍限制仍需處理。此為本次使用者方向，未假稱新增實作。
14. #147正式r004 v1包與回收；A/B1 v0-pilot已交24張／60列，不入正式分母。
15. 組員#89/#138文字情境及精確標準答案、#128人工T/F與Q5評估劇本；程式由Codex做，題目答案不代寫。
16. 正式輸出凍結後跑#123/#129/#138/#89評估與報告；四套評分器已合staging（#159/#160/#164/#165），仍缺正式輸出／人工資料，不是還要重寫評分器。
17. #83交接包head仍bda073d；上次Codex已審需修改，待owner更新無Git資料夾流程、D70/D71與評估者可見資料後複審。
18. #124正式瀏覽器／色覺模擬／灰階／人工驗收與#130/#137試跑；Demo腳本草稿已由#181/#182保存，待Claude改寫／獨立驗收。
19. 12個相關Draft（#154/#157/#158/#163/#169/#172/#174/#175/#176/#177/#180/#185）的對應驗證／B級審查與合入；通過既定條件才merge，主線由Claude既定週日流程處理。
20. 最後在#93發布staging總結：head、PR與等級、啟動、已知問題、§14待決、磁碟變化。現在仍有實作／gate／人工驗收缺口，不能當全部完成。OpenAI API照使用者順序延後到系統完整後，非本輪已接入能力。


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

Windows差異已有具體位置：舊start_local_demo.py依賴fcntl／Homebrew／macOS temporary-directory convention／lsof；.command使用Bash和.venv/bin/python；量測程式使用resource、df、vm_stat、sysctl、memory_pressure；連engineering-qa-v4的serve122.py也呼叫df。現有pyproject／uv.lock沒有完整重建本次RT環境所需的torch／torchvision／PyYAML，因此不能只給git clone＋uv sync就稱可重現。這不是所有依賴都不支援Windows；需獨立portable launcher／監測adapter與環境profile。WSL2是候選執行環境，未驗證且不能解決macOS專屬監測命令本身。

GT／人工答案／評估劇本放獨立evaluation包／權限，推論包不含；也不搬原.blend、原始資料庫、Mac環境、憑證或舊state。若正式入口仍依賴舊PG，須在交接前明確處理，不能把舊PG/state直接複製成新Q線來源。本次沒有複製、傳送或上傳原始RGB／模型／GT；只產交接要求與待補狀態。


### Windows交接補充：硬體說明與審查順序

先做圖／出口ROI／必要設定的前置審查，再產正式RGB／索引與兩模式baseline；第一版輸出凍結後即可交組員T/F及做baseline評估，不等LLM／進階追蹤模型比較。後續比較依v1結果排程，新增行為另驗證／審查。

每台測試機需填：Windows版本/build與原生/WSL2；CPU完整型號、實體／邏輯核心與本次threads；RAM總量及執行前可用量；GPU型號、獨立VRAM總量／可用量、驅動、CUDA/torch版本與實際device；磁碟總量／可用量／輸出位置；電源模式與同時運行的模型／背景負載。沒有GPU要明填NONE，查不到的欄位填UNKNOWN，不從共享記憶體或錯誤的32-bit AdapterRAM猜VRAM。

baseline先保持既有RT-DETR CPU/FP32/2threads/640×640的可比profile，不要求Qwen或獨立GPU；這不是Windows最低硬體或fps保證。CUDA另列profile。後續8B沿上表受限context的RAM/VRAM估算，不在v1偷換模型；整機RAM與GPU VRAM分開記，不能把兩者相加當可用VRAM。交接前與產製前後記磁碟可用量，低於原8GiB門檻停止。
