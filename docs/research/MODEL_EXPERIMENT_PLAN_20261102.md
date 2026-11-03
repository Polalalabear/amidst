# 模組上的模型實驗分析企劃（事先登錄版）

- 日期：2026-11-02（第 2 版：依使用者補充，改成「先 Baseline、再比較」，並加上指標公式、數字表、實驗環境揭露與跨平台外包執行包。第 3 版：加上環境檢查與自動安裝腳本規格、GitHub Actions 跨平台 smoke、硬體基準與候選模型，對應 #93 D116-2。第 4 版：記錄決定 D 的定案；PostgreSQL 依賴與包大小維持 `UNKNOWN`，並寫明量法。第 5 版：加上 §P 核心價值、研究定位與現實落差，以及表 B-4 吞吐與儲存。第 6 版：加上 §D 資料集設計與其影響，依 CX-7 渲染的實際檔案大小更新。第 7 版：寫入使用者 2026-11-03 的決定 D121（A、B、C、E、F、G），補 §3.12 逾時判定規則與放寬逾時探索組、§5.10 查詢用字變因、§D.7 監視器取樣 fps 調查、§7.12 Colab 評估，並附 yyin 題集包 `docs/research/handoff/yyin_q1q3_wording_v1/`）
- 狀態：**PLANNED／NOT_RUN**。本文件只是企劃：沒有呼叫任何模型、沒有渲染、沒有推論。demo（11-04）之後、資料到位才執行，不進 11-03 批次。
- 作者：Claude Opus 5.5 / high。依 AGENTS.md：評估工具、統計和圖表歸 Claude；模型呼叫和 Agent orchestration 歸 Codex。
- base：`codex/q1q5-staging`＠`434e57922a24d2422226871c0bb672dc7bc3584b`
- 引用格式：`路徑＠commit`，後面附 SHA-256。LOCAL 表示檔案只在本機，不在 repo。
- **數字規則**：本文件不寫任何預期值。表格裡沒有實測數字的格子一律寫 `NOT_RUN`；資料缺的寫 `UNKNOWN`；不計分的寫該類別的標籤（例如 `NOT_SCORED_PENDING_DECISION`）。

## 目錄

- **前導：核心價值、研究定位與現實落差**（§P）
- **前導：資料集設計與其影響**（§D）
- 第 0 部分：目標與共用規則（§0～§1）
- **第一部分：Baseline 結果（RULE_ONLY）**（§2）
- **第二部分：建立在 Baseline 之上的比較**（§3 M1 Agent vs RULE、§4 M2 Q5 評分器 v1 vs v2、§5 M3 Q1／Q3）
- 第三部分：實驗環境揭露、硬體基準與候選模型（§6；含 M4 模型比較）
- 第四部分：跨平台外包執行包、環境腳本與 GitHub Actions smoke（§7）
- 開跑檢查表（§8）、使用者決定紀錄（§9，D121）、引用（§10）

## P. 核心價值、研究定位與現實落差

本節先說清楚本系統要證明什麼、不宣稱什麼，以及它和實際落地之間差多遠。後面所有實驗都在這個定位之內解讀。

### P.1 核心價值：本研究要證明什麼

1. **跨鏡頭盲區下、以證據為界的追蹤與檢索**：Q1～Q5 的每個答案都要能追溯到來源觀測（source／run／clock／hash），並且明確區分 observed（看到的）、inferred（推論的）、`MISSING`（該有卻沒有的）和 `UNKNOWN`（不知道的）。目標盲區內找不到時，系統顯示「搜尋中」或「回原鏡頭」，不假裝找到（AC4、AC8）。
2. **GT 隔離、可重現的評估方法**：決策和評分完全分開（§1.2）；凍結錄製重播後輸出 hash 相同（AC7）；假設、指標、門檻在看資料前登錄（§1.1）。即使結果不好，這套方法本身也是研究產出。
3. **Agent 在不確定性仲裁上相對規則的增益**：在候選集合由決定性模組產生的前提下（D64），讓 Agent 決定是否切鏡，**量測**它相對規則的增益。這裡要證明的是「量得出來、量法可信」，不是預設 Agent 一定贏；結果可能是增益、沒有差異，或是規則比較好（§1.6）。

**研究定位**：這是一個在 Blender 合成場景上的工程 demo，加上一套方法研究。它不是 benchmark，也不是正式研究驗收（AGENTS.md）。結論只對已測的場景和硬體成立。

### P.2 本研究明確「不」宣稱的事

| 不宣稱 | 原因 |
| --- | --- |
| 身分確認 | 只用 RT-DETR 偵測加 HSV 顏色證據（`docs/specs/DEVELOPMENT_RULES.md`＠`994b700` 第 64 行：第一版不用 VLM，也不接外部模型 API）；沒有經授權的身分證據，身分一律 unconfirmed |
| 物理可通行、碰撞 | Agent 不做幾何、路徑規劃或碰撞檢查；沒有授權證據時，物理通行一律 unknown |
| 即時、大規模部署 | 目前只有離線和預錄；真實攝影機串流在規則裡是 FUTURE |
| 真實監控影片上的效能 | 沒有任何真實影片評估 |
| 符合隱私或法規要求 | 沒有做過法規審查 |
| Agent 一定優於規則 | 這是待檢驗的假設（H1） |

### P.3 現實落差清單

「目前狀態」裡的數字，都是 2026-11-02 對 LOCAL 的 P1 包做結構量測得到的：只看檔案大小、張數和 PNG 檔頭，沒有讀 GT。「現實量級」是使用者給的落地情境，不是實測值。

| 面向 | 目前狀態（實際數字） | 現實場景的量級 | 落差 | 本研究的處理 |
| --- | --- | --- | --- | --- |
| 相機數與時長 | P1：2 台 × 8 s × 20 fps＝320 張 PNG，960×540。r004（CX-7 已渲染，§D）：A4-1 4 台 × 50 s × 5 fps＝1,000 張；B4-1 5 台 × 42 s × 5 fps＝1,050 張，都是 960×540 | 數十到數百台，24 小時連續 | P1 總共 16 相機秒，A4-1 200 相機秒，B4-1 210 相機秒；1 台相機 1 天是 86,400 相機秒，約是 B4-1 的 411 倍 | **量測＋外推**（P.4、表 B-4）；外推值標 `EXTRAPOLATED` |
| 運算吞吐 | RT-DETR 每幀耗時：`NOT_RUN`；Qwen3 每次決策延遲：`NOT_RUN`（P1 的 AGENT 錄製只有 1 次呼叫，而且逾時）；索引建置時間：`NOT_RUN` | 每台 20 fps 的即時預算是每幀 50 ms | `UNKNOWN` | **量測**（表 B-4），再外推需要的運算量 |
| 儲存 | P1 的 320 張 PNG 共 148,010,357 B（平均每幀 462,532 B）；偵測索引 `detection_index.records.jsonl` 共 424,666 B（320 筆，平均每幀 1,327.1 B）；整個 P1 包約 143 MiB | 數十到數百台 × 24 小時 | 見 P.4 的外推表 | **外推**；PNG 只是本管線的逐幀格式，真實系統存的是壓縮影片，所以 PNG 外推值是這種格式的量，不是真實儲存需求 |
| 資料域 | 只有 Blender 合成畫面（`source_kind=SYNTHETIC`，或 r004 渲染） | 真實監控：光線變化、壓縮失真、遮擋、人群密度、鏡頭品質不一 | 完全沒有真實影片評估 | **列為限制**；真實影片試點列為未來工作，而且要先取得隱私授權 |
| 身分與 ReID | 只用 RT-DETR 加 HSV 顏色；沒有 ReID 模型 | 穿著相似的人、人群、換裝 | 無法確認身分 | **列為限制**；ReID 列為未來工作，而且要另做評估；即使加入 ReID，沒有授權證據仍不宣稱身分確認 |
| 相機標定與圖核准 | r004 的圖已經 G4 核准（D115-1，`9d99f87e…bc76c`），但產品端跨鏡頭要等 CQ-21（#304）實作和重核，`allowed_purposes` 仍是 `[]`；P1 的 live 追蹤範圍仍是 PROPOSED，所以 live 停在 A（D113） | 每個新場址都要做標定、量拓撲、核准圖 | 新場址的上線流程還沒定義 | **列為限制**；在路線圖裡把「每個場址需要哪些核准步驟」列成清單 |
| 即時性 | 離線、預錄；demo 的 B-05b 是預錄，live 是 fail-closed（D113） | 即時串流 | 沒有串流管線 | **量測**即時倍率 `RTF`（表 B-4）；串流本身列為未來工作 |
| 隱私與法規 | 沒有真實人物資料；GT 是合成的 | 真實人物影像受所在地個資法規限制 | 沒有做法規審查 | **列為限制**與未來工作；本研究不做法律判斷 |
| 硬體 | Apple Silicon arm64、本機 Ollama（§6.1）；記憶體與 GPU：`UNKNOWN`（量法見 §6.3）；CI runner 沒有 GPU（§7.10） | 邊緣裝置或 GPU 伺服器 | 沒有在目標硬體上量過 | 每個數字都附硬體 manifest；**不跨硬體外推**，除非在該硬體上實測過 |

### P.4 吞吐與儲存的量測與外推

**量測**（屬於 Baseline，記在表 B-4；每列附 `env_manifest_sha256`）：

| 代號 | 指標 | 公式 | 單位 |
| --- | --- | --- | --- |
| `T_det` | RT-DETR 每幀耗時 | 偵測階段牆鐘時間 ÷ 處理影格數；報中位數和 P90 | ms／幀 |
| `T_llm` | Qwen3 每次決策延遲 | 每次模型呼叫從送出到收到的牆鐘時間；報中位數和 P90；逾時的呼叫另外計數，不併進中位數 | ms／次 |
| `T_index` | 索引建置時間 | 建索引牆鐘時間 ÷ 影片長度（相機分鐘） | s／相機分鐘 |
| `S_frame` | 每幀儲存 | 逐幀檔案位元組 ÷ 影格數 | B／幀 |
| `S_index` | 每幀索引儲存 | 索引檔位元組 ÷ 影格數 | B／幀 |
| `RTF` | 即時倍率 | 整條流程處理時間 ÷ 影片時長；<1 才可能即時 | 倍 |

表 B-4 的欄位：`run_id`、`source_class`、影格數、相機數、`T_det`、`T_llm`、`T_index`、`S_frame`、`S_index`、`RTF`、`env_manifest_sha256`。r004 的數字：**`NOT_RUN`**。

**外推公式**（線性假設；每次都寫出用到的實測值 hash 和硬體）：

- 每天要處理的影格數：`F＝N × T × 3600 × fps`（N 台、T 小時）
- 運算時間：`F × T_det ÷ 3.6×10⁶`（裝置小時）
- 即時處理需要的並行裝置數：`N × fps × T_det ÷ 1000`
- 儲存：`F × S_frame` 和 `F × S_index`

**目前能算的外推**（輸入是三個資料集實測的每幀 PNG 大小，見 §D.1；24 小時；標 `EXTRAPOLATED`，不是實測）：

| 每幀大小來源 | fps | 1 台（GiB／天） | 10 台 | 100 台 |
| --- | --- | --- | --- | --- |
| P1（462,532 B／幀） | 20 | 744.4 | 7,443.7 | 74,436.5 |
| A4-1（538,013 B／幀） | 5 | 216.5 | 2,164.6 | 21,646.0 |
| A4-1（538,013 B／幀） | 20 | 865.8 | 8,658.4 | 86,583.8 |
| B4-1（539,441 B／幀） | 5 | 217.0 | 2,170.3 | 21,703.4 |
| B4-1（539,441 B／幀） | 20 | 868.1 | 8,681.4 | 86,813.6 |

偵測索引只有 P1 量過（`detection_index.records.jsonl` 424,666 B／320 筆＝每幀 1,327.1 B）。外推到 20 fps 是 1／10／100 台每天 2.14／21.36／213.57 GiB；r004 的索引大小：`NOT_RUN`。

限制：三個資料集都是 960×540 的合成畫面；真實系統的解析度、壓縮方式、畫面裡的人數都不同，索引大小也會跟偵測數量一起變。同一個 fps 下，r004 每幀比 P1 大約 16%，而且同一場景裡不同鏡頭差到 1.5 倍（§D.1），所以單一資料集的每幀大小不能代表所有鏡頭。運算相關的外推見 §D.4，目前只有歷史實測可以參考，r004 的 `T_det`、`T_llm` 是 `NOT_RUN`。

### P.5 結論：離實際落地還差的步驟（路線圖，不承諾日期）

1. 在 r004 正式場景上產出 Baseline 數字（第一部分），包括表 B-4 的吞吐與儲存。
2. 完成 Agent vs RULE、評分器、Q1／Q3 的比較（第二部分），以及跨平台重現（第四部分）。
3. 用實測吞吐外推「N 台 × T 小時」需要的運算與儲存，找出瓶頸。
4. 擴大合成場景：長卡（A4-2／B4-2）、複雜情境「甲」凍結、更多相機。
5. 產品端跨鏡頭的核准（CQ-21）；定義新場址的標定與圖核准流程。
6. 在取得隱私授權之後，用真實影片做小規模試點，量資料域落差。
7. 加入 ReID 或身分模組，並做獨立評估；沒有授權證據時仍然不宣稱身分確認。
8. 串流與即時管線；在邊緣裝置或 GPU 伺服器上重量吞吐。
9. 隱私與法規審查，之後才談部署。

## D. 資料集設計與其影響

### D.1 資料集表

大小是用檔案系統讀出的位元組數（`stat`）實算的，沒有開影像內容；解析度只讀 PNG 檔頭；計數只數檔名。r004 的數字取自 CX-7 的 safe 目錄（LOCAL，GitHub 上寫 `<LOCAL r004 CX-7 render>`），沒有打開或讀取 `gt_private`。量測日：2026-11-03。

| 項目 | P1 | A4-1 | B4-1 |
| --- | --- | --- | --- |
| 來源類別 | `SYNTHETIC`（`ENGINEERING_DYNAMIC_SCENE`） | `FORMAL`（r004，G4 生效後渲染，D115） | `FORMAL`（同左） |
| 鏡頭 | A、B（2 台） | CAM_ENTRY、CAM_EXT_CAR、CAM_EXT_CLEAR、CAM_W1（4 台） | CAM_BRANCH、CAM_R101_IN、CAM_W1、CAM_W2、CAM_WIDE（5 台） |
| 片長 | 8 s | 50 s | 42 s |
| fps | 20 | 5 | 5 |
| 每台張數 | 160 | 250 | 210 |
| 總張數 | 320 | 1,000 | 1,050 |
| 解析度 | 960×540 | 960×540 | 960×540 |
| PNG 總位元組 | 148,010,357 B（141.2 MiB） | 538,013,316 B（0.50 GiB） | 566,413,125 B（0.53 GiB） |
| 每幀平均 | 462,532 B | 538,013 B | 539,441 B |
| 每台每幀平均（最小～最大） | `UNKNOWN`（沒有分台統計） | 446,433（CAM_EXT_CLEAR）～667,584（CAM_W1） | 466,192（CAM_WIDE）～663,436（CAM_W1） |
| 計分事件（劇本凍結 #354） | 沒有凍結劇本；兩份 Q2 預錄各 n＝1 | 計分：A4-c1、A4-n1；不計分：A4-e、A4-c2 | 計分：B4-n1、B4-b；不計分：B4-d、B4-e |
| 計畫 SEARCHING | — | 3 | 3 |
| 用途 | demo（B-05b 預錄）、管線冒煙測試 | Baseline、第二部分的比較實驗 | Baseline、第二部分的比較實驗 |
| hash | MANIFEST `6e9a0a4c…1f1d7` | safe 目錄裡只有 PNG，沒有 MANIFEST；safe bundle 收據等 #115／FEAT-1 交件：`UNKNOWN` | 同左 |

附註：

- 協調者回報 A4-1 約 1.0 GiB、B4-1 約 1.1 GiB，那是整個場景目錄的磁碟佔用（`du`：A4-1 1,056,256 KiB、B4-1 1,111,996 KiB）。其中 safe 只佔約一半（527,504 KiB、555,356 KiB），其餘是 `gt_private`。`gt_private` 只量了總佔用，沒有列檔或讀取。
- r004 正式 run 的偵測索引大小、`T_det`、`T_index`：`NOT_RUN`。

### D.2 5 fps 的出處

| 來源 | 內容 |
| --- | --- |
| #93 G6 列 | 「§11 參數組定為第一版初值，**前提 5 fps**」（2026-10-20 成立）。決策參數本來就是以 5 fps 設計的 |
| #93 D68-3（2026-10-20，使用者決定，#132 r004 提案） | A4 用 4 台、B4 用 5 台，「5 fps、stride 1」 |
| #115 前提檢查留言（[連結](https://github.com/Polalalabear/amidst/issues/115#issuecomment-6334859555)） | 「D70 已明確授權 A4 4台、B4 5台、各30s、5fps、960×540」 |
| #354（劇本凍結候選，D105-1 核准） | A4 producer／plan：「50 s，5 fps」；B4：「42 s，5 fps」 |
| #93 D79-2 | 計分範圍「SWITCH 計畫空檔 ≤5.2 s、RETURN 暫失 ≤1.8 s」，註明是「5 fps、D67 參數下的值；其他格率或參數由評估端用同一公式重算」 |

結論：5 fps 來自 D68-3 的 r004 提案核定，再由 D70 授權渲染；決策參數組（G6）也是以 5 fps 為前提。片長則從 D68 的「各 30 s」改成 #354 的 50 s／42 s。**仍待 Codex 確認**的只有兩件：D70 原文的確切位置（本次只看到 #115 的轉述），以及 P1 用 20 fps 時，參數組是否另外換算過（`UNKNOWN`）。

### D.3 時間解析度對指標的影響

影格間隔 `Δt＝1／fps`：5 fps 是 200 ms，20 fps 是 50 ms。

| 受影響的量 | 影響 | 對策 |
| --- | --- | --- |
| 切鏡延遲 `L_sw` | 決策只能落在影格上，所以延遲是 Δt 的整數倍。若真實事件時刻在兩幀之間均勻分布，量化誤差的標準差是 Δt／√12：5 fps 時 57.7 ms，20 fps 時 14.4 ms | 報告延遲時一律附「解析度 200 ms」；小於 Δt 的差異不解讀 |
| 配對延遲檢定 | 兩組用同一份影格，量化誤差共用，所以差值也只能是 200 ms 的整數倍，打平會很多。Wilcoxon 檢定只用非零差值，檢定力會下降 | 照實報告打平數；`L_sw` 本來就是次要指標，不影響 H1 的主要判定 |
| 事件正確率 `C_evt` | 進入時間要落在 `entry_window_us` 內。若窗口比 200 ms 短，可能一幀都沒有，變成結構性 miss | 評分前先檢查每個計分事件的窗口至少含 1 幀；不含的列為 `UNKNOWN`，不算任何一組錯 |
| 盲區長度 | 以影格計：5 fps 時，5.2 s 空檔是 26 幀，1.8 s 暫失是 9 幀。小於 200 ms 的短暫遮擋可能剛好落在兩幀之間，在 5 fps 下看不到 | `M_honest`、`FS` 只能代表 5 fps 看得到的事件；報告寫明「短於 1 幀的遮擋未被取樣」 |
| 偵測成本 | 偵測次數和索引大小都跟 fps 成正比：20 fps 是 5 fps 的 4 倍 | 表 B-4 的 `T_det` 以「每幀」為單位，換算時乘上 fps |
| 樣本數與檢定力 | 計分單位是劇本事件，不隨 fps 改變。目前合計只有 4 個計分候選，遠低於 §1.5 的 20 | 第二部分依 §3.8 用 D114-1 增加 request；做不到就判 `INSUFFICIENT`。fps 不能用來增加樣本 |

### D.4 運算成本：現有歷史實測

這些數字是早期在其他 staging commit 上量的，不是 r004 Baseline 的數字，只當作規劃參考，標 `HISTORICAL`：

| 量測 | 數值 | 來源 |
| --- | --- | --- |
| RT-DETR 單獨跑（Qwen3 完全卸載） | 3.129 fps（CPU 2 threads、單 worker） | [#93 留言](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6362295156)，staging `a958dd4` |
| RT-DETR，Qwen 常駐但不生成 | 3.114 fps，300.7 ms／幀 | 同上 |
| RT-DETR，與 Qwen 生成並行 | 0.554 fps，1854.1 ms／幀（吞吐降 82.2%） | 同上；該留言自己寫明「不支持宣稱 9 台各 5 fps 可即時」 |
| 峰值記憶體 | RT-DETR RSS 694 MiB；Qwen runner 2,076 MiB | 同上 |
| 歷史 CPU forward | 2.684 fps | [#93 留言](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6410099936) |
| Qwen3 呼叫 | rc3 重錄的兩個真 runtime 包：18 次呼叫、18 次逾時、LLM_used＝0；Q3／Q5 階段 p95 約 2.0～2.4 s | [#93 留言](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6417324746) |

依這些歷史數字做的示意外推（`EXTRAPOLATED`，僅供規劃）：A4-1＋B4-1 的 9 台、每台 5 fps，即時處理需要每秒 45 幀。依 3.129 fps 換算，大約要 14.4 個同等 worker；如果與 Qwen 生成並行（0.554 fps），大約要 81 個。r004 Baseline 會在 §6 的硬體 manifest 下重量（表 B-4），屆時以新數字為準。

### D.5 取樣率是 Baseline 的已知變因；敏感度分析（OPTIONAL）

取樣率列為 Baseline 的**已知變因**：表 B-1 加一欄 `fps`，所有結論只對 5 fps 成立。有兩種敏感度分析：

| 做法 | 內容 | 成本 | 需要什麼 |
| --- | --- | --- | --- |
| S1 降採樣（建議先做） | 從現有 5 fps 影格每隔一幀取一張，得到 2.5 fps，在同一劇本上重跑 RULE_ONLY | 不需要渲染；磁碟只多索引和錄製，大小 `NOT_RUN`（依 P1 的每幀 1.3 KB 估計遠小於 1 GiB） | 參數組是以 5 fps 為前提（G6），2.5 fps 要依 D79 的公式重算計分範圍；結果標 `EXPLORATORY` |
| S2 重渲染 20 fps（**OPTIONAL**） | 同一段重渲染成 20 fps，比較 5 fps 與 20 fps 的 `C_evt`、`L_sw`、`M_honest` | 依實測每幀大小估計：A4-1 全段 4,000 張約 2.0 GiB，B4-1 全段 4,200 張約 2.1 GiB，合計約 4.1 GiB；只做一個計分事件前後 10 s：A4-1 800 張約 0.40 GiB、B4-1 1,000 張約 0.50 GiB。渲染時間：`UNKNOWN`（看 CX-7 收據上的實際耗時再推） | **要使用者授權渲染**（D98-2 的條件）、磁碟可用 ≥9 GiB 才能開始；參數組要另外核定 20 fps 的版本 |

**已定（D121-G，使用者 2026-11-03 選選項 1）**：只做 S1 降採樣（5→2.5 fps），不重新渲染。S2 不做；之後若要做，要另外取得渲染授權並重新登錄。

### D.7 2026 年監視攝影機實際的錄影 fps（調查）

查詢日期一律是 2026-11-03。只收廠商規格或說明頁、政府或機關規範、產業研究；零售商和部落格只拿來交叉核對，不當主要依據。查不到可靠數字的寫 `UNKNOWN`。

| 類別 | 常見錄影 fps | 依據（標題、網址、查詢日） | 可信度 |
| --- | --- | --- | --- |
| 消費級（家用、小型店面） | 主串流最高 20～30 fps，預設多為 25 或 30；子串流 4～15 fps，預設約 10 | Reolink〈Reolink Stream Settings Guide: Resolution, Frame Rate, Bitrate & More〉，<https://support.reolink.com/articles/360006937654-Reolink-Stream-Settings-Guide-Resolution-Frame-Rate-Bitrate-More/>，2026-11-03（只看到搜尋摘要，各型號的確切數字要看各自的規格書） | 中：單一廠商；型號之間不同 |
| 企業雲端攝影機 | 24 fps；CM61 是 20 fps | Verkada Help Center 的錄影 FAQ（搜尋摘要；原網址 <https://help.verkada.com/product-faqs/where-is-recorded-video-stored> 在 2026-11-03 已回 404，無法直接核對） | 低～中：原頁已移，數字只來自搜尋摘要，標 `UNVERIFIED` |
| 企業 NVR（50 Hz／60 Hz 地區） | 主串流在 50 Hz 地區最高 25 fps、60 Hz 地區最高 30 fps；4K 常降到 20 fps | Hikvision 同系列型號規格書的格式（搜尋摘要；DS-2CD2387G2 的官方規格表沒有查到） | 低：沒有拿到官方規格書原文，確切型號標 `UNKNOWN` |
| 產業實際設定（整合商） | 平均約 15 fps；2016 年調查約 10 fps（從早年的約 7 fps 上升），只有約 10% 的整合商平均 ≥15 fps；2011 年調查約 70% 錄 ≤10 fps | IPVM〈Frame Rate Guide for Video Surveillance〉，<https://ipvm.com/reports/frame-rate-surveillance-guide>；IPVM〈Average Frame Rate Video Surveillance 2016〉，<https://ipvm.com/reports/avg-frame-rate-2016>；兩者 2026-11-03（付費內容，只看到摘要） | 中：產業研究，但樣本是美國為主的整合商，2026 年的新調查 `UNKNOWN` |
| 公部門與警方規範（英國） | 依地方規範不同：最低 6.25 fps、建議 25 fps；或最低 12 fps；或不低於 25 fps | 英國 Home Office〈UK Police Requirements for CCTV v3.0〉，<https://assets.publishing.service.gov.uk/media/65f4b481811225001a579f80/UK_Police_Requirements_for_CCTV_v3.0.pdf>（PDF 內文無法用工具抽出，本身的 fps 數字 `UNKNOWN`）；數字來自引用 Home Office 手冊的地方規範：Aberdeen City〈Approved CCTV guidance〉<https://committees.aberdeencity.gov.uk/documents/s14249/Approved%20CCTV%20guidance.pdf>、East Devon〈Appendix C – CCTV standards policy〉<https://eastdevon.gov.uk/licensing/sex-establishments/sex-establishment-licensing-policy-document/sex-establishment-licensing-policy/appendix-c-cctv-standards-policy>，2026-11-03（搜尋摘要） | 中：是官方文件，但各地不同，不是全國統一標準 |
| 智慧城市／交通（美國州交通部） | 可調 5～30 fps，預設 30 fps | Georgia DOT〈936 Closed Circuit Television (CCTV)〉合格產品規格，<https://www.dot.ga.gov/PartnerSmart/Materials/Documents/qplproducts/936_ClosedCircuitTelevision_CCTV.pdf>，2026-11-03（搜尋摘要）。NTCIP 1205／1208 只規範攝影機控制和切換，沒看到 fps 的規定（<https://www.standards.its.dot.gov/ApplicationArea/9>） | 中：單一州的規範；其他國家、城市的數字 `UNKNOWN` |
| 為省頻寬和儲存而降 fps | 錄影改成 10～15 fps；只看周界的鏡頭 5～10 fps；平常 5 fps、有移動時升到 25～30 fps；子串流 4～15 fps | Reolink 規格（同上）；Reolink〈Security Camera Frame Rate〉<https://reolink.com/blog/security-camera-frame-rate/>（廠商部落格）；IPVM（同上），2026-11-03 | 中：方向一致，但具體數字多來自廠商部落格 |

限制：這是桌面調查，沒有實測任何攝影機；多數來源只看到搜尋摘要，標了「搜尋摘要」的列都還要回原文核對。各國、各產業的部署比例：`UNKNOWN`。

**本研究的 5 fps 和 2.5 fps 落在哪裡**

- 5 fps 落在實務的**低端**：等於「只看周界」或「平常低 fps、有事件才升格」那一類設定，也略低於英國部分地方規範的最低 6.25 fps；比整合商平均（約 10～15 fps）和廠商預設（20～30 fps）低很多。
- 2.5 fps 低於上表所有來源的下限，屬於極端的省儲存設定。

**對外推的影響**

1. **時間解析度**：真實系統常用的 15～30 fps，影格間隔是 33～67 ms，比 5 fps 的 200 ms 細很多。本研究在 5 fps 下量到的 `L_sw` 量化誤差（§D.3）和「短於 1 幀的遮擋看不到」，在真實系統上會變小。所以 5 fps 的盲區判斷結果，**不能直接說成真實系統的表現**，只能說「在低 fps 部署下」。
2. **方向不確定**：fps 較高時，看得到更多短暫出現的畫面，可能讓 SEARCHING／RETURN 判斷更準；但決策參數組是以 5 fps 設計的（G6），換 fps 要重算參數，不能假設結果只會變好。S1（5→2.5 fps）只能看「fps 降低」這一側的敏感度，**不能**外推到 15～30 fps。
3. **成本**：偵測次數和索引大小跟 fps 成正比。把 §P.4、§D.4 的數字從 5 fps 換到 15 fps 要乘 3，換到 30 fps 要乘 6；這是 `EXTRAPOLATED`，不是實測。
4. 報告時，所有結論都寫「在 5 fps（及 2.5 fps 探索組）下」，並附上這一節的實務區間對照。

### D.6 跨資料集比較的限制

- A4-1 和 B4-1 只共用 **CAM_W1** 一台，其他鏡頭都不同。P1 的 A、B 兩台來自另一個工程場景，跟 r004 沒有共用鏡頭。
- 鏡頭會影響每幀內容（同一場景內每幀大小最多差 1.5 倍，最大的都是 CAM_W1），也可能影響偵測難度。所以兩個場景的指標差異，不能歸因於「情境不同」，因為鏡頭組成也不同。
- 報告規則：
  1. 指標依場景分列；合計只用依 run 分群的 bootstrap（§1.5），而且要附各場景的值；
  2. CAM_W1 可以單獨做跨場景對照，但只有 1 台，只能描述，不能檢定；
  3. P1（20 fps、SYNTHETIC）和 r004（5 fps、FORMAL）的數字永遠不合併，也不並排比較準確率，只並列每幀大小、吞吐這類工程量；
  4. 每台相機的結果（每台的事件數、偵測數）放在附錄。

## 0. 目標

研究目標是檢驗「Agent／LLM 的能力大於 RULE」。這是**待檢驗的假設**，不是預設結論。執行順序固定如下：

1. **先做 Baseline**：在 r004 正式場景上，用 `RULE_ONLY` 跑完 Q1／Q2／Q3／Q5 的正式鏈，產出第 2 節的數字表。這是主線，也是第二部分所有比較的對照數字。
2. **再做比較**：Agent vs RULE（M1）、評分器 v1 vs v2（M2）、LLM vs 規則解析（M3）。這三項都依賴 Baseline 的數字與錄製。Baseline 沒完成，第二部分一律 `NOT_RUN`。

假設、對照組、主要指標、門檻、樣本數和檢定都在看到資料前寫死。結果不論是 Agent 贏、打平、輸，或資料不足，都照第 1.6 節的判定標籤原樣報告。

## 1. 共用規則

### 1.1 事先登錄與修訂

1. **凍結點**：本文件推上 PR 的 commit 就是事先登錄版本。分析腳本（Claude）先用 SYNTHETIC fixture 寫完、測完，把腳本的 SHA-256 記在結果紀錄裡，之後才讀真實資料。
2. **修訂**：看到資料前可以修訂，但要另開 commit 寫明理由。看到資料後才加的分析一律標 `EXPLORATORY`，不能改判主要假設。
3. 每個假設只有**一個主要指標**。次要指標顯著，不能補主要指標的不顯著。

### 1.2 GT 隔離

- 決策端（Q2／Q3／Q5 控制器、Agent、Q3 parser、Q1 檢索）只讀錄製、凍結索引和 request。GT、渲染軌跡、visibility、depth 一律不進入（`docs/specs/DEVELOPMENT_RULES.md`＠`994b700` 第 57、64 行）。
- 正確答案只在評分端讀：Q5 讀外部撰寫並凍結的劇本，Q1／Q3 讀人工標註的答案。三個評分器都是 evaluation-only（`q5_switch_eval.py`、`q3_parse_eval.py`、`q1_query_eval.py` 開頭都寫明不 import 推論、模型、parser 或檢索實作）。
- 執行分兩段：**先**由執行端產生並凍結決策錄製（記 SHA-256），**後**由 Claude 的評分端讀劇本／答案計分。評分端不回寫錄製。外包機（§7）只做第一段。
- 每次執行附隔離檢查：決策錄製的輸入清單不得出現 GT 路徑（沿用 #307 守門和 #127 kit 的 GT 掃描）。

### 1.3 資料來源類別

每個數字都要標來源類別，結論不跨類別推論：

| 類別 | 例子 | 可以支持什麼 |
| --- | --- | --- |
| `FORMAL` | r004 A4-1／B4-1 渲染後的正式 run、`evaluation_eligible=true` 的題目包 | 正式結論 |
| `ENGINEERING` | P1 工程場景、team-eval v0-pilot（`source_class=ENGINEERING`） | 只有「工程場景上成立」 |
| `SYNTHETIC` | 合成 fixture、P1 包內錄製（`source_kind=SYNTHETIC`） | 只有「管線能跑」 |
| `PILOT` | `evaluation_eligible=false` 的題目包 | 試跑、估變異；不是證據 |

### 1.4 哪些結果不能拿來支持 H1

下列結果**不得**算成 Agent／LLM 能力的證據，報告時要單獨列出數量：

1. **`RULE_FALLBACK` 接手的步驟**。它在整組比較（ITT）裡算進 Agent 組，因為那是 Agent 系統的實際表現，但不能說成是 Agent 判斷對的。Q3 同理：`parsed_by=RULE` 的題目不算 LLM 的成績。
2. **SYNTHETIC／ENGINEERING 場景**的結果，不能推論到 r004 正式場景。
3. **`evaluation_eligible=false` 的題目包**。`q1_query_eval.py` 在 `evaluation_eligible=false` 時本來就把正式指標寫成 0／0，只在 SYNTHETIC 時另出 `synthetic_metrics`。
4. **不計分的事件**：`NOT_SCORED_PENDING_DECISION`（LONG_GAP、LONG_LOSS）、`OVERLAP_AUTHORITY_UNSELECTED`、OV1（D105-2：只展示不計分）、`ENDED_BY_LIMIT`。也不能另做一套評分把它們算進來。
5. **`OVERLAP_P_OV2_UNVERIFIED`**：依 D93 單列，不併入主比率。
6. **事後換評分器、門檻或子集**得到的結果。
7. **對照不公平的比較**（§3.2 任一項不同）。
8. **評分端沒有正確答案的單位**（劇本 `UNKNOWN`／`MISSING`、seed 選不到而 `NOT_RUN`）：記成缺值，不能補成 RULE 錯或 Agent 對。
9. **n＝1 的錄製**，例如 P1 包的兩份預錄。
10. **外包機上跑出、但環境 manifest 不完整或輸出 hash 驗不過的 run**（§7.5）。
11. **從多個候選模型裡挑表現最好的那一個當 H1 的證據**。H1 的模型事先固定為 `qwen3:1.7b-q4_K_M`（§6.5）；其他候選模型的結果只屬於 M4，標 `EXPLORATORY`。
12. **GitHub Actions 的 smoke test 結果**（§7.10）。它只用 SYNTHETIC fixture 或 mock，只能證明環境與管線能跑。

### 1.5 統計方法

- **分析單位**：Q2／Q5 是「計分事件」，也就是劇本裡一個 SWITCH 或 RETURN 決策窗；Q1／Q3 是「一道題」。
- **95% 信賴區間**：比例用 bootstrap，**依 run 分群重抽**，因為同一個 run 的事件不獨立。重抽 10,000 次，亂數種子 `20261102`。單一 run 的比例改用 Wilson 區間。延遲的中位數和 P90 也用同一套 bootstrap。
- **比較檢定**（只用在第二部分）：每對單位的差值 d＝比較組分數 − Baseline 分數。對 d≠0 的單位做**單尾精確符號檢定**，α＝0.05。四個 H1（H1-Q2、H1-Q3、H1-Q1、H1-QW；H1-QW 見 §5.10，D121-C 新增）用 Holm 校正。
- **樣本數**：單尾符號檢定，假設在不一致的單位裡比較組贏的比例是 0.75。

  | 不一致單位數 | 顯著所需贏數 | 檢定力 |
  | --- | --- | --- |
  | 10 | 9 | 0.24 |
  | 20 | 15 | 0.62 |
  | 30 | 20 | 0.89 |
  | 40 | 26 | 0.95 |

  不一致單位 ≥30 才算檢定力足夠；10～29 時，顯著仍可判 SUPPORTED，不顯著只能判 `INCONCLUSIVE_UNDERPOWERED`；<10 一律判 `INSUFFICIENT`。

### 1.6 判定標籤（第二部分每個 H1 只會得到一個）

| 標籤 | 條件 |
| --- | --- |
| `SUPPORTED` | Holm 校正後 p<0.05；正確率差的點估計 ≥ +5 個百分點；資料是 `FORMAL`；該模組的閘門成立；不一致單位 ≥10 |
| `SUPPORTED_ENGINEERING_ONLY` | 同上，但資料只有 `ENGINEERING`。報告要寫「不推論到正式場景」 |
| `NO_DIFFERENCE` | 不一致單位 ≥30，而且差的 95% CI 落在 ±5 個百分點內 |
| `INCONCLUSIVE_UNDERPOWERED` | 不顯著，且不一致單位 10～29；或閘門沒過 |
| `REVERSED` | 反方向（RULE 較好）的單尾檢定在 Holm 校正後 p<0.05。**照實報告為 RULE 優於 Agent／LLM** |
| `INSUFFICIENT` | 不一致單位 <10，或計分單位 <20 |
| `NOT_RUN`／`UNKNOWN` | 前置依賴沒到位，或資料缺 |

### 1.7 指標的精確定義（全文共用）

時間都用 source clock。錄製內部的單位是 µs，報告時換成 ms（÷1000，保留 1 位小數）。

| 代號 | 指標 | 公式 | 單位 | 計算來源 |
| --- | --- | --- | --- | --- |
| `C_evt` | 事件正確率 | 判為 match 的計分事件數 ÷ 計分事件數 × 100。v1 的 match 定義：決策窗 `[w0, w1)` 內**恰好一次** SWITCH，相機屬於 `allowed_camera_ids`，進入時間落在 `entry_window_us` 內（`q5_switch_eval.py` 第 146～151 行）。RETURN 事件依 v1 對應規則 | % | v1 評分器輸出 |
| `L_sw` | 切鏡延遲 | 對每個判為 match 的事件：`decision_time_us − w0`，÷1000。報告中位數和 P90 | ms | 錄製的 `decision_time_us` 加上劇本的決策窗 |
| `FS` | 誤切率 | 不落在任何計分決策窗內的 SWITCH 數 ÷ 計分範圍的總長（分鐘） | 次／分鐘 | 錄製加劇本 |
| `M_honest` | 缺值誠實率 | 劇本或評分端判為「應該找不到」的步驟中，輸出 `SEARCHING`／`TEMP_LOST`／`MISSING`／`UNKNOWN`、沒有硬給相機的比例 | % | 錄製加 v1 評分器（AC8） |
| `R_hash` | 重播一致率 | 同一 session 以 recorded replay 重播後輸出 hash 相同的次數 ÷ 重播次數 × 100 | % | AC7、#127 kit |
| `T_step` | 每步處理時間 | 每個決策步的牆鐘時間。報告中位數和 P90 | ms | 錄製時間戳或 runner log |
| `TO` | 逾時率 | `PROVIDER_TIMEOUT` 次數 ÷ 模型呼叫次數 × 100（分母是呼叫，不是步驟） | % | `agent_trace.events[].error_code` |
| `SI` | schema 失敗率 | `SCHEMA_INVALID` 次數 ÷ 模型呼叫次數 × 100 | % | 同上 |
| `FB` | fallback 比例 | `decision_source=RULE_FALLBACK` 的決策步數 ÷ Agent 組決策步數 × 100 | % | 錄製 `decision_source` |
| `K_call` | 呼叫成本 | 模型呼叫次數 ÷ 決策步數；另報每次呼叫的牆鐘 ms，以及 prompt／回應 token 數（錄製沒記就寫 `UNKNOWN`，不估） | 次／步、ms、token | `agent_trace`、`q3_provider_audit` |
| `E_q3` | Q3 整題正確率 | 六個欄位（intent、class、color、time_us、camera、region）全對，或正確拒答的題數 ÷ 計分題數 × 100 | % | `q3_parse_eval.py`（`q3-parse-eval-v1`） |
| `F_q3[f]` | Q3 各欄位正確率 | 欄位 f 正確的題數 ÷ 計分題數 × 100 | % | 同上 |
| `P_cam`、`R_cam` | Q1 相機 micro precision／recall | `TP/(TP+FP)`、`TP/(TP+FN)`，按相機累加 | % | `q1_query_eval.py` 的 `camera_micro_precision`／`camera_micro_recall`（第 242～243 行） |
| `LLM_share` | LLM 實際解析比例 | `parsed_by=LLM` 題數 ÷ LLM 組題數 × 100 | % | Q3 回應的 `parsed_by` |

## 第一部分：Baseline 結果（RULE_ONLY）

## 2. Baseline

### 2.1 定義

**Baseline**＝r004 正式場景（A4-1 50 s、B4-1 42 s；D89），在 G4 生效的圖上（D115-1，`decisions_sha256=9d99f87ea007e1988797e50fa28e70f67e6973578bc15ef3f440ba4f4d8bc76c`），用 FEAT-1 #376 的 Baseline 正式鏈，以 `switch_mode=RULE_ONLY`、`parser_mode=RULE_ONLY` 跑出的 Q1／Q2／Q3／Q5 結果。

這一部分沒有比較組，也沒有假設檢定，只產出帶 95% CI 的數字。第二部分的所有比較都拿這些數字和錄製當對照組。

### 2.2 輸入與 hash

| 輸入 | 來源 | SHA-256／狀態 |
| --- | --- | --- |
| Baseline 正式鏈程式 | FEAT-1 #394，head `18d1a287f1ddc6eed442eebc3fe8667b225344e1`（Claude 複審 APPROVE） | 合入後的 staging commit：`NOT_RUN` |
| 劇本凍結 | `docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json`＠#354 `48133c1a` | `ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb`（D105-1） |
| 情境卡 v1 | `docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md`＠mainline `0d78599` | `015201556f550ab67dbbebead35916db426a3b6a05066ffc94c928696900ddbd` |
| 圖（G4） | #348＠`0502225bb16f117014fd875fc7a9281220ede484` | `decisions_sha256` 如上 |
| 渲染 safe bundle（A4-1、B4-1） | CX-7 #115（D115-2，進行中），LOCAL | `NOT_RUN` |
| 偵測索引 | #118 | `NOT_RUN` |
| seed 選取索引 | #329，seed 依 D114-1 規則選取 | `NOT_RUN` |
| 參數集 | 正式鏈的 `parameter_set_sha256` | `NOT_RUN` |
| Q5 評分器 v1 | `src/amidst/evaluation/q5_switch_eval.py`＠#305 `f22e9da` | `97564e401cb7d70a7cc22113a008477b447974536ae207aabc230868e8b6d3dc`（#306 A15 例外） |
| Q1／Q3 評分器 | `q1_query_eval.py`、`q3_parse_eval.py`＠`434e579` | `eb403f968d3263cb5151219c9e46dddc8922d0f7ba9f21b7c07a276f44f973b9`、`4660edea0b204dfdead99cd1e2ebc5b8ce13ccffbd9d78c157ba285abda298c4` |
| Q1／Q3 Baseline 題目與答案 | 正式題目包（`evaluation_eligible=true`）目前不存在。依 D121-C：pilot 用 s2／team-eval；正式題由 yyin 依三種事件出題（`docs/research/handoff/yyin_q1q3_wording_v1/`，`v1`，核准前 `evaluation_eligible=false`），見 §5.4、§5.10 | `NOT_RUN` |
| team-eval 包（Baseline-only） | FEAT-3 #370／#293（D112-1），`v0-pilot`／`evaluation_eligible=false`／`ENGINEERING` | MANIFEST SHA-256：`NOT_RUN`（發包要 U12） |
| 執行環境 | §6 的環境 manifest | `NOT_RUN` |

### 2.3 表 B-1：每個 run 的 Q2／Q5 Baseline 數字（主表）

每列是一個 run 加一個 request（同一個 run 可以有多個 request，依 D114-1 規則選 seed）。最後兩列是依 run 分群的合計。

| 欄位 | 內容 |
| --- | --- |
| `run_id` | 正式 run ID |
| `scene` | A4-1／B4-1 |
| `request_sha256` | request 的 hash |
| `source_class` | `FORMAL` |
| `n_events_scored` | 計分事件數（SWITCH＋RETURN） |
| `n_events_not_scored` | 不計分事件數，並附各類標籤的計數 |
| `C_evt` ％ [95% CI] | §1.7 |
| `L_sw` 中位數 ms [95% CI]／P90 ms | §1.7 |
| `FS` 次／分鐘 | §1.7 |
| `M_honest` ％ [95% CI] | §1.7 |
| `T_step` 中位數／P90 ms | §1.7 |
| `R_hash` ％ | 重播 3 次 |
| `recording_sha256` | 決策錄製 |
| `scorer_output_sha256` | v1 評分輸出 |
| `env_manifest_sha256` | §6 |

**現況：每一格都是 `NOT_RUN`。**

### 2.4 表 B-2：Q1／Q3 Baseline 數字

| 欄位 | 內容 |
| --- | --- |
| `question_pack` | 題目包 ID 與 MANIFEST SHA-256 |
| `eligibility` | `evaluation_eligible` 的值；`false` 時這一列整列標 `PILOT` |
| `n_questions_scored` | 計分題數 |
| `E_q3` ％ [95% CI] | §1.7 |
| `F_q3[intent／class／color／time_us／camera／region]` ％ | 六欄 |
| 拒答正確率 ％ | `NEEDS_CLARIFICATION`、`UNSUPPORTED_CLASS` 等狀態判對的比例 |
| `P_cam`／`R_cam` ％ [95% CI] | §1.7 |
| `T_query` 中位數 ms | 從文字到 Q1 結果的牆鐘時間 |
| `scorer_output_sha256`、`env_manifest_sha256` | |

**現況：`NOT_RUN`**。正式題目包不存在；team-eval 和 s2 只能填 `PILOT` 列。

### 2.5 表 B-3：team-eval Baseline-only RETURN

FEAT-3 的 team-eval 包會重播我方凍結的 Baseline 輸出（D96-2），組員端不跑模型。所以它驗的是「別的機器能不能重現同一份 Baseline 輸出」，不是新的準確率數字。依 D112-1 的 RETURN 形狀（`projection=TEAM_EVAL_BASELINE_V0_PILOT`，`team-eval-return.v1` 仍是 PROPOSED）：

| 欄位 | 內容 |
| --- | --- |
| `return_file` | `RETURN/評測結果_姓名_YYYY-MM-DD.json`（報告用代號，不寫真名） |
| `pack_manifest_sha256` | 必須等於發出去的包 |
| `environment.python_version`／`isolated`／`platform` | RETURN 原欄位 |
| `halves` | 必須正好是 `["baseline"]`；出現 complex 鍵就 INVALID（`HALF_NOT_IN_PACK`） |
| `output_sha256.baseline` | 與我方參考輸出比對：`MATCH`／`MISMATCH` |
| `verify` | `VALID`／`VALID_WITH_WARNINGS`／`INVALID` |
| `complex` | 一律 `NOT_INCLUDED`（不計分、不算 0、不進分母） |

統計：`MATCH` 比例（％，附 Wilson 95% CI 與 n）。**這一表只能說明可重現性，不能當 Q1／Q3 的正確率證據**，因為它是 `v0-pilot`／`ENGINEERING`。

**現況：`NOT_RUN`**（要等 U12 發包和組員回件）。

### 2.6 Baseline 圖表規格

| 圖 | x 軸 | y 軸 | 標示 |
| --- | --- | --- | --- |
| G-B1 事件正確率長條 | run（A4-1、B4-1、合計） | `C_evt`（%，0～100） | 誤差線是 95% CI；長條上方寫 `n=計分事件數`；不計分事件數用灰字寫在下方 |
| G-B2 切鏡延遲 | run | `L_sw`（ms） | 盒鬚圖加上每個事件的點；寫 n |
| G-B3 計分覆蓋瀑布 | 類別 | 事件數 | 全部 → 各類不計分剔除 → 實際計分；每段寫標籤 |
| G-B4 Q3 欄位正確率 | 六欄加整題 | %（0～100） | 95% CI；寫 n；`PILOT` 列的標題加「PILOT_ONLY，非正式證據」 |
| G-B5 team-eval 重現 | 回件 | MATCH／MISMATCH | 寫 n 和 Wilson CI |

所有圖的標題列都寫來源類別和 `env_manifest_sha256` 的前 8 碼。`NOT_RUN` 的格子畫成斜線空格，不省略。

### 2.7 Baseline 完成的條件

全部成立才算 Baseline 完成，第二部分才能開跑：

1. CX-7 #115 渲染完成，safe bundle 與收據經 Claude 審過（D115-2）。
2. #118 偵測索引、#329 索引交件；seed 依 D114-1 選定，選不到的 request 標 `NOT_RUN`。
3. FEAT-1 #394 合入，正式鏈在 staging 上用 `RULE_ONLY` 跑完 A4-1、B4-1。
4. 表 B-1 每個 run 都有數字，計分事件合計 ≥20。不到 20 的話 Baseline 仍算完成，但標 `INSUFFICIENT_FOR_COMPARISON`，第二部分的 M1 直接判 `INSUFFICIENT`。
5. 重播一致率 `R_hash`＝100%（AC7），#127 kit 對這些錄製 0 FAIL，或逐項寫 NOT_APPLICABLE 的原因。
6. 每個 run 都有環境 manifest（§6）。
7. Q1／Q3：有正式題目包時填表 B-2；沒有時，表 B-2 標 `NOT_RUN`，Baseline 的 Q2／Q5 部分仍然可以算完成。

### 2.8 Baseline 的依賴與 owner

| 項目 | owner | 等待 |
| --- | --- | --- |
| 渲染、索引、正式鏈執行、錄製 | Codex | D115 渲染進行中，完成日 `UNKNOWN` |
| seed 選取 | Claude | #329 |
| 評分、表 B-1～B-3、圖 G-B1～G-B5 | Claude | 錄製 |
| 正式題目包核准、U12 | 使用者 | §9 決定 C |

預估工時（估計）：錄製到位後評分與出表 1 天；分析腳本可以在 demo 後先用 fixture 寫好（0.5 天）。

### 2.9 Baseline 可能失敗的情況

| 情況 | 對策 |
| --- | --- |
| 渲染延誤 | 表 B-1 全部寫 `NOT_RUN`；報告不改用 P1 數字頂替（P1 是 SYNTHETIC） |
| 重播 hash 不一致 | 停下來，不出 Baseline 數字；先查非決定性來源 |
| 劇本有 `UNKNOWN` 欄位 | 該事件不計分，計入 `n_events_not_scored` |
| 計分事件 <20 | 照 §2.7 第 4 項處理 |

## 第二部分：建立在 Baseline 之上的比較

三個比較都依賴第一部分。共同前提：比較組要用與 Baseline **同一份**輸入、索引、劇本和參數集，只有 mode 欄位不同；Baseline 的錄製直接當 RULE 組，不重新跑。

## 3. M1：Q2 追蹤決策，RULE_ONLY（Baseline）vs AGENT_SEQUENTIAL

### 3.1 研究問題與假設

- **RQ-Q2**：在相同的候選集合和時間預算下，Agent 依序查詢候選證據後決定是否切鏡，是否比決定性規則更常做出正確的切鏡決策？
- **H1-Q2（主要）**：在 r004 正式場景的計分事件上，`AGENT_SEQUENTIAL` 的 `C_evt` 高於 Baseline（ITT：fallback 接手的步驟照原樣算進 Agent 組）。
- **H2-Q2（次要）**：只看 Agent 實際做決定的步驟，與同一步的 Baseline 決定配對比較。這是條件子集，可能有選擇偏差，因為容易的步驟比較不會逾時。
- **分析方式已定（D121-A，使用者 2026-11-03 選選項 1）**：H1-Q2 用整組比較（ITT）判定；H2-Q2 的子集只當次要結果，不能用來改判 H1-Q2。
- **H0**：沒有差異，或 RULE 較好。

### 3.2 對照組公平條件

任何一項不同，該次比較就判 `INVALID_COMPARISON`，不計入。

| 項目 | 要求 |
| --- | --- |
| 輸入 | `request_sha256`、凍結索引、`candidate_snapshot_sha256` 都相同。候選集合和排序由決定性模組產生，Agent 不排序、不增刪（D64） |
| 參數 | 同一個 `parameter_set_sha256`，只差 `switch_mode` |
| 時間預算 | 每步決策期限相同；**正式組** Agent 的輪數與逾時用已核定的上限（§3.12：`agent_call_timeout_ms`＝2000、`agent_total_budget_ms`＝5000、`agent_max_rounds`＝3），實驗中不放寬。放寬逾時另成一組探索組（D121-B，§3.12），不算 H1 的正式比較 |
| 環境 | 同一台機器、同一份環境 manifest（§6）；量延遲時兩組交錯執行 |
| 重複 | RULE 是決定性的，用 Baseline 的錄製，另外重跑 2 次確認 hash 相同；Agent 每個 request 跑 K＝5 次，記錄每次的 seed 和溫度。每個單位的 Agent 分數取 K 次的平均 |

### 3.3 主要指標與閘門

- 主要：`C_evt`（§1.7），用 v1 評分器計算。
- 閘門：Agent 組的 `FB` >20% 時，H1-Q2 最多判 `INCONCLUSIVE_UNDERPOWERED`，報告寫「Agent 大多沒有實際做決定」。
- 次要：`L_sw`（只算兩組都判 match 的事件，配對 Wilcoxon 符號秩檢定）、`FS`、`M_honest`、`TO`、`SI`、`K_call`、`T_step`。

### 3.4 表 M1-1：每個 run 的比較數字

| 欄位 | 內容 |
| --- | --- |
| `run_id`、`scene`、`request_sha256` | 與表 B-1 同一列對應 |
| `arm` | `RULE_ONLY(Baseline)`／`AGENT_SEQUENTIAL` |
| `K` | 重複次數（RULE＝1） |
| `C_evt` ％ [95% CI] | |
| `L_sw` 中位數 ms [95% CI] | |
| `FS` 次／分鐘 | |
| `TO` ％ [95% CI] | 只有 Agent 組 |
| `SI` ％ [95% CI] | 只有 Agent 組 |
| `FB` ％ [95% CI] | 只有 Agent 組 |
| `K_call` 次／步；每次呼叫 ms 中位數；token | 只有 Agent 組；token 沒記就寫 `UNKNOWN` |
| `T_step` 中位數／P90 ms | |
| `recording_sha256`（K 份都列）、`env_manifest_sha256` | |

### 3.5 表 M1-2：假設檢定結果

| 欄位 | 內容 |
| --- | --- |
| `n_pairs` | 配對單位數 |
| `n_tie`、`n_agent_better`、`n_rule_better` | |
| `diff_C_evt` 百分點 [95% CI] | |
| `p_one_sided`、`p_holm` | |
| `p_reverse_holm` | 反方向（RULE 較好） |
| `gate_FB` | PASS／FAIL |
| `verdict` | §1.6 的標籤 |
| `excluded_counts` | §1.4 每一類被排除的數量 |

**現況：兩表都是 `NOT_RUN`。**

### 3.6 資料來源與 hash

| 來源 | 內容 | 用途 |
| --- | --- | --- |
| P1 包（LOCAL）`/Users/Shared/amidst-p1-clean-room-20261026/Amidst P1 最終測試/`，`MANIFEST.json` SHA-256 `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7` | `data/recordings/2777741d96ac9aff5bffb2f61a4d2938.json`（`ffe5e693a80031e707cddb531925cb97bc6d8295b69777ad3afa1d885bd5a55a`，`decision_source=RULE_ONLY`）；`d4b67fd71caef6fb80fc9d92af544959.json`（`26a1854efb08fe0a809b957692e3f05f92f1f516972e383e1b752f9be0eb02db`，`decision_source=RULE_FALLBACK`，`fallback_reason=PROVIDER_TIMEOUT`；`agent_trace` 只有 1 個模型呼叫事件，錯誤碼 `PROVIDER_TIMEOUT`，結構欄位中另有 1 次 `SCHEMA_INVALID`）。兩份都是 `source_kind=SYNTHETIC`。本企劃只讀了 hash 和結構欄位，沒讀 GT 的值 | 只做管線冒煙測試。每組 n＝1，Agent 實際上沒做出任何決定，**不能支持也不能否定 H1-Q2**。D113-1 的旁白照舊 |
| Baseline 錄製（第一部分） | 表 B-1 的 `recording_sha256` | RULE 組 |
| 同一組正式 run 的 Agent 錄製 | Codex 產生，K＝5 | Agent 組（主要資料） |
| FEAT-6 的 176 份凍結錄製（#300／#393＠`943a72f`，LOCAL） | #127 kit rc5 重錄，給 AC7 契約一致性用；#300 記載其中有 18 次模型逾時 | **待盤點**。只有同時滿足三項才用於次要指標（`TO`、`SI`、`FB`）：有 `switch_mode`／`decision_source` 結構欄位；同一 request 在兩組都有錄製；`source_kind` 明確。**不用於主要指標**，因為沒有對應的凍結劇本，而且是工程場景 |

### 3.7 評分與 GT 隔離

評分器是 v1（§2.2）。v2 只當穩健性檢查（§4）。GT 隔離見 §1.2。

### 3.8 樣本數

依劇本凍結（#354），A4-1、B4-1 合計只有 **4 個計分候選**（A4-c1、A4-n1、B4-n1、B4-b；§D.1）。事先登錄的擴充方式只有一種：在同一組 run 上，依 D114-1 的規則產生多個 request（不同起點和時間窗），每個 request 分別計分；CI 依 run 分群。合計仍 <20 時判 `INSUFFICIENT`，不再另找資料湊數。

### 3.9 前置依賴、owner、時程

- 依賴：Baseline 完成（§2.7）；Agent 輪數／逾時的核定值寫進參數集；v1 bytes＝`97564e40…`（FEAT-6 帶 #305 進 staging）。
- owner：Codex 負責 Agent 執行和錄製；Claude 負責評分、統計、圖表；使用者決定 §9 的 A、B。
- 時程（估計）：Baseline 完成後，Agent 錄製 1 天（K＝5），評分與出表 1 天。

### 3.10 圖表規格

| 圖 | x 軸 | y 軸 | 標示 |
| --- | --- | --- | --- |
| G-M1a 配對點圖 | 組別（RULE、Agent） | 每個單位的正確率（0～1） | 每個單位一條連線，顏色分 Agent 贏／輸／平；標題寫 n、打平數、不一致數 |
| G-M1b 決策來源堆疊長條 | run | 決策步數的比例（%） | 分 `AGENT`／`RULE_FALLBACK`；超過 20% 的欄加註 |
| G-M1c 森林圖 | `diff_C_evt`（百分點） | 分析列（ITT、Agent 子集、v2 穩健性） | 95% CI；0 線與 ±5 pp 帶；每列寫 n |
| G-M1d 延遲 ECDF | `L_sw`（ms） | 累積比例（0～1） | 兩組兩條線；圖例寫 n |
| G-M1e 失敗率長條 | `TO`、`SI`、`FB` | % | 95% CI，寫呼叫數或步數當分母 |

### 3.11 可能失敗的情況

| 情況 | 對策 |
| --- | --- |
| `FB` >20% | 依閘門降級；報告逾時分布。正式組不放寬逾時；放寬逾時只在 §3.12 的探索組裡做，結果標 `EXPLORATORY` |
| schema 失敗 | 照原樣計入 `SI`；不改 prompt 後拿同一批資料重跑來換結果。改 prompt 就是新版本，要重新登錄 |
| 計分事件 <20 | `INSUFFICIENT` |
| 兩組輸入 hash 不同 | `INVALID_COMPARISON`，整對重跑 |
| 渲染延誤到報告截止 | M1 寫 `NOT_RUN`；P1 冒煙結果照實寫「n＝1，不能判定」 |

### 3.12 逾時判定規則與放寬逾時探索組（D121-B）

**已核定的上限（正式組）**。協調者在 `mainline/q1q5`＠`0d78599` 的 `src`／`configs` 沒找到寫死的值；本次再查一次，`mainline/q1q5` 的確沒有，但 `codex/q1q5-staging`＠`434e579` 的參數集有。注意參數名是 `agent_call_timeout_ms`，不是 `agent_timeout_ms`：

| 參數 | 值 | 參數本身的狀態 | 來源 |
| --- | --- | --- | --- |
| `agent_call_timeout_ms` | 2000 ms | `APPROVED` | `configs/q1q5/parameter_set_v1.json`＠staging `434e579`（檔案 SHA-256 `960d823c17c181c6b0b128a3cc7f39fb0d5f7af19828073b884d74aa8336ee6e`）；提案在 [#88 留言](https://github.com/Polalalabear/amidst/issues/88#issuecomment-6291477432) |
| `agent_total_budget_ms` | 5000 ms | `APPROVED` | 同上 |
| `agent_max_rounds` | 3 次 | `APPROVED` | 同上 |
| `session_max_agent_rounds` | 12 次 | `APPROVED` | 同上；提案在 [#93 留言](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6292484288) |
| `q3_llm_timeout_ms` | 2000 ms | **`PROPOSED`** | 同上 |
| `q3_max_llm_attempts` | `null` | **`PROPOSED`** | 同上 |

同一份值也出現在 `configs/q1q5/baseline_v1_protocol.json`＠`434e579` 的 `budgets.inherited_values`。但有兩件事還沒定，**開跑前必須補上**：

1. 參數集整份的 `approval.status` 仍是 `PROPOSED`，`applies_to.run_ids` 是空的；protocol 的 `budgets.run_bound_approval` 是 `UNRESOLVED`。也就是說，「2000／5000／3」這組值已核定，但還沒綁到 r004 的正式 run：`UNKNOWN`。
2. M3 用的 `q3_llm_timeout_ms`、`q3_max_llm_attempts` 還是 `PROPOSED`，`q3_max_llm_attempts` 甚至沒有值：`UNKNOWN`。

這三項列在 §8 的開跑檢查表。補上之前，M1、M3 的正式組不開跑。

**逾時怎麼判（白話）**

- 每一次模型呼叫，從送出到收到完整回應，超過 `agent_call_timeout_ms` 就算逾時。這次呼叫記一筆 `PROVIDER_TIMEOUT`，遲到的回應丟掉，不採用。
- 逾時的那一個決策步，改由規則接手：錄製寫 `decision_source=RULE_FALLBACK`、`fallback_reason=PROVIDER_TIMEOUT`。用完 `agent_max_rounds` 或 `agent_total_budget_ms` 還沒決定時也一樣由規則接手，原因分別記 `ROUND_LIMIT`、`TIME_BUDGET`（`src/amidst/evaluation/q1q5_conformance.py`＠`434e579` 的 `_decision_budget` 檢查這兩個代碼）。
- **TO（逾時率）**＝`PROVIDER_TIMEOUT` 次數 ÷ 模型呼叫次數。分母是「呼叫」：一個決策步最多可以有 3 次呼叫。
- **FB（fallback 比例）**＝由規則接手的決策步 ÷ Agent 組全部決策步。分母是「決策步」。TO 高不一定 FB 高（同一步裡第一次逾時、第二次成功），所以兩個都報。
- **FB 大於 20% 就降級**：H1-Q2 最多只能判 `INCONCLUSIVE_UNDERPOWERED`，報告寫「Agent 大多沒有實際做決定」（§3.3 閘門）。這條在看資料前就固定。
- 規則接手的步驟在 ITT 裡照樣算進 Agent 組，但不能說成是 Agent 判斷對（§1.4 第 1 項）。

**歷史數據**（`HISTORICAL`，都在 2000 ms 上限下）：

| 來源 | 結果 |
| --- | --- |
| rc3 重錄的兩個真 runtime 包 | 18 次呼叫、18 次逾時（TO＝100%），LLM_used＝0（[#93 留言](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6417324746)） |
| P1 包的 AGENT 錄製 | 1 次呼叫、1 次逾時（TO＝100%），決策步由 `RULE_FALLBACK` 接手（§3.6） |
| CX-6 不截斷診斷（`docs/engineering/QWEN3_UNTRUNCATED_DIAGNOSTIC_20261025.md`＠staging `434e579`） | 把同一批 8 秒工程 baseline 的 18 次呼叫拿掉逾時重跑：Q3 12 次 5.366～10.427 s（中位 5.777 s），Q5 6 次 7.804～10.430 s（中位 7.992 s），18/18 完整生成。單線重跑，併發條件和原輪不同。這 18 次與 rc3 的 18 次是否逐筆同批：`UNKNOWN`（沒有逐筆比對 hash） |

依這些數字，正式組在 2000 ms 下很可能大部分逾時，H1-Q2 很可能判 `INCONCLUSIVE_UNDERPOWERED`。這是事先寫下的預期風險，不是結果。

**放寬逾時探索組（arm `AGENT_SEQUENTIAL_RELAXED`，標 `EXPLORATORY`）**

- 目的：把「模型本身會不會判斷」和「在現行時間預算內能不能判斷」分開回答。放寬組和 RULE 的時間預算不同，所以**不進 H1-Q2 的判定**，只放在表 M1-1 的另一列和 G-M1c 森林圖的「放寬逾時」列。
- 除了下面三個值，其他設定都和正式組一樣（同一份輸入、候選、提示、K＝5、temperature、seed）。
- **提出的數值（PROPOSED，待使用者核定）**：

| 參數 | 正式組 | 放寬組（PROPOSED） | 怎麼算 |
| --- | --- | --- | --- |
| `agent_call_timeout_ms` | 2000 | **11000** | 實測完整延遲的 P99，無條件進位到 1000 ms。CX-6 的 18 次裡最大是 10.430 s；n＝18 時 nearest-rank 的 P99 就是最大值，所以 P99＝10.430 s → 11000 ms |
| `agent_total_budget_ms` | 5000 | **33000** | 3 輪 × 11000 ms |
| `agent_max_rounds` | 3 | 3（不變） | 只放寬時間，不放寬輪數，變因只有一個 |

- **這個數值的限制**：n＝18 太少，P99 等於最大值，不能代表穩定的尾端延遲；而且是工程場景、不是 r004。所以開跑前要先做一次**校準量測**：在 r004 的 pilot request（不是正式計分 request）上，用診斷腳本的上限 30000 ms（`scripts/benchmark_q1q5_local_models.py` 允許的最大值）量至少 100 次呼叫的完整延遲，取 P99 進位到 1000 ms。校準值高於 11000 時用校準值；超過 30000 時以 30000 為上限，並把超過的呼叫數照實報。校準值也要使用者核定後才生效。
- 放寬組同樣報 TO、FB，也同樣套用 FB >20% 的降級規則。

## 4. M2：Q5 切鏡評分器 v1 vs v2

### 4.1 兩個問題要分開

| 問題 | 比什麼 | 是不是 H1 |
| --- | --- | --- |
| M2-a 評分器一致性 | 同一批凍結決策，分別用 v1 和 v2 計分 | 不是。這是在檢驗量尺本身 |
| M2-b 用評分器比較 Agent 和 RULE | 就是 M1 的 H1-Q2 | 是，但主要量尺固定用 v1 |

**事先登錄**：H1-Q2 的主要結論只用 v1。v2 只當穩健性檢查。兩版方向一致，才寫「結論對評分器版本穩健」；方向不一致，就照實寫「結論依賴評分器版本」，**不能**改用對 Agent 有利的那一版。

### 4.2 假設（M2-a）

- **H-S1**：在 v1 和 v2 都計分的 STANDARD 事件上，判定一致率 ≥99%，而且每一個不一致都能指到 v2 設計稿裡寫明的規則差異。
- **H-S2**：U6 列為不計分的類別（LONG_GAP、LONG_LOSS、ENDED_BY_LIMIT、真實 OVERLAP），v2 全部輸出不計分標籤，沒有任何一筆算進主比率。
- **H-S3**：重算兩次 hash 相同；`RECOMPUTE_AND_REJECT`（U-D5）對竄改過的輸入確實拒絕。

### 4.3 指標定義

| 代號 | 公式 | 單位 | 門檻 |
| --- | --- | --- | --- |
| `A_std` | v1 與 v2 判定相同的 STANDARD 事件數 ÷ 兩版都計分的 STANDARD 事件數 × 100 | % | ≥99 |
| `L_ns` | v2 對不計分類別輸出正確標籤的事件數 ÷ 不計分類別事件數 × 100 | % | ＝100 |
| `R_v2` | 重算 hash 相同的次數 ÷ 重算次數 × 100 | % | ＝100 |

### 4.4 版本與設定

| 項目 | 來源 |
| --- | --- |
| v1 | `src/amidst/evaluation/q5_switch_eval.py`＠#305 `f22e9da`（`97564e40…b6d3dc`）；A15：v1 一個 byte 都不改 |
| v2 設計稿 | `docs/evaluation/Q5_SWITCH_EVAL_V2_DESIGN.md`＠#258 `0b6e800`（`0a4e579b0664ab663e44809ebc0d2670b434c17161d7c24f237b1be4d051cc4c`，D114-4；**PROPOSED**） |
| v2 實作 | `q5_switch_eval_v2.py`（U-D8＝NEW_V2_MODULE），在 FEAT-4 #396，head `1ff272ffea2fa595a153106829ebf2cef3e29c8c`。D114-3：延到 demo 後，接在 FEAT-6 合入後的 staging 交件。正式 hash：`NOT_RUN` |
| U6 定案設定 | `configs/evaluation/q5_v2_decisions_u6_20261101.json`，`0daa1508e2a67607cdc6bac54684b1b5449d3a651325e5af23dfe0afb1bd3b7e`（D105-4）。預設檔 `q5_v2_decisions.json` 維持全 PENDING |
| U8（CQ-21a） | #351＠`03b369a519c8a81ffe9e5a3136d6a6ab0eb56bd3` 整批照推薦核定（D105-3） |
| 複雜情境卡 | `docs/evaluation/R004_COMPLEX_SCENARIO_CARDS_V2.md`＠#261 `b5302a0`（`02d98c06ac93b5b1eec019d65415eada7b751b4c6e76d3982a28aa36d9efd88b`；合進 mainline 時重釘，D114-3） |
| seed | D114-1：甲的 seed 只綁選取規則（例如 S_b＝CAM_W1、`[14.0, 17.0)`）；#329 索引出來後由 Claude 只看索引、照規則選 ID；選不到就 `NOT_RUN`，卡片退回 U7。formal 路徑拒絕 `UNKNOWN`／`MISSING` 的 seed |

### 4.5 常見與複雜情境的計分範圍（D105-2、D105-4）

| 情境 | 卡 | 計分 | 能不能進 H1-Q2 |
| --- | --- | --- | --- |
| 常見 | A4-1、B4-1（卡 v1） | STANDARD SWITCH／RETURN 計分 | 可以（主要） |
| 複雜「甲」 | RR-a1、RR-a2、PE1-d | 計分 | 可以，但和常見情境**分開報告**，不合成一個數字 |
| 複雜「甲」 | RR-b、LG-1 | `NOT_SCORED_PENDING_DECISION`（U-D1／U-D2 未決） | 不行 |
| 複雜「甲」 | OV1-a、OV1-b | 只展示、不計分；正式範圍是 `OVERLAP_AUTHORITY_UNSELECTED` | 不行 |
| 長卡 | A4-2、B4-2 | 暫緩（#323 選項 3） | 不行（`NOT_RUN`） |

甲目前是 UNFROZEN、走 fallback（D114-2）。甲凍結前，複雜情境的列全部寫 `NOT_RUN`。

### 4.6 表 M2-1

| 欄位 | 內容 |
| --- | --- |
| `recording_sha256` | Baseline 與 M1 的凍結決策錄製 |
| `scenario_class` | 常見／複雜甲 |
| `n_std_both_scored` | |
| `A_std` ％ | |
| `n_disagree` 與規則條目編號 | |
| `L_ns` ％ | |
| `R_v2` ％ | |
| `v1_output_sha256`、`v2_output_sha256` | |
| `C_evt_v1`、`C_evt_v2` ％（Baseline 與 Agent 各一列） | 給 M1 的穩健性列使用 |

**現況：`NOT_RUN`。**

### 4.7 依賴、owner、時程

- 依賴：Baseline 完成；FEAT-6 合入 staging；FEAT-4 #396 在其上合入；M1 的錄製（M2-a 本身不需要 Agent 錄製，只用 Baseline 錄製也能先跑）；甲凍結才跑複雜列。
- owner：Claude 負責比對腳本、混淆矩陣和報告；Codex（FEAT-4 擁有者）負責 v2 實作的交件與修正；使用者決定 U-D1／U-D2／U-D4（決定前 LONG_GAP／LONG_LOSS 一律不計分）。
- 時程（估計）：FEAT-4 合入後 0.5～1 天；FEAT-4 交件日 `UNKNOWN`。

### 4.8 圖表規格

| 圖 | 規格 |
| --- | --- |
| G-M2a v1×v2 混淆矩陣 | 行：v1 判定；列：v2 判定；格內是事件數；不一致格附規則條目編號；標題寫 n |
| G-M2b 計分覆蓋瀑布 | 同 G-B3，分 v1、v2 兩欄 |
| G-M2c 穩健性列 | 加在 G-M1c 森林圖裡的「v2」那一列 |

### 4.9 可能失敗的情況

| 情況 | 對策 |
| --- | --- |
| `A_std` <99% | H-S1 FAIL；逐筆列出不一致，回 FEAT-4 修；報告不挑版本 |
| v2 交件晚於報告 | M2 寫 `NOT_RUN`；報告寫「未做評分器穩健性檢查」 |
| v2 的方向與 v1 相反 | 照實寫「結論依賴評分器版本」；H1-Q2 的判定不改 |
| v1 bytes 不是 `97564e40…` | 停下來，不計分，回報 pin 偏移 |

## 5. M3：檢索 Q1／Q3

### 5.1 研究問題與假設

- **H1-Q3（主要）**：在正式題目上，`parser_mode=LLM_WITH_RULE_FALLBACK` 的 `E_q3` 高於 Baseline（`RULE_ONLY`）。
- **H1-Q1（主要）**：從同一道文字題出發，經各自的 Q3 解析再進 Q1 檢索，LLM 組的 `R_cam` 高於 Baseline。Q1 檢索本身是決定性的（`src/amidst/q1q5/q1_search.py`），兩組的差異只來自 Q3 的輸出。
- **H2-Q3（次要）**：只看 `parsed_by=LLM` 的題目，與同一題的 Baseline 結果配對。
- **H1-QW（主要，D121-C 新增，§5.10）**：同一個目標事件換不同說法時，LLM 組的正確率落差（精確地點詞 − 模糊空間詞）小於 Baseline 的落差。也就是 LLM 對查詢用字比較不敏感。
- **安全面（次要，不是 H1）**：LLM 捏造非字面詞而被拒絕的比例（`q3_parse.py` 會拒絕「LLM invented nonliteral term」）；錯誤接受率（該拒答卻給出查詢）。

### 5.2 對照組

| 組 | 設定 |
| --- | --- |
| Baseline | `parser_mode=RULE_ONLY`；字面文法 `src/amidst/q1q5/q3_rules.py`＠`434e579`（`659a148224fc08b0a71a31c09a831a7a1ceb81004335a4c535a61ef02b6f5d5d`，`q3-rules.v1`） |
| LLM | `parser_mode=LLM_WITH_RULE_FALLBACK`；`src/amidst/q1q5/q3_parse.py`＠`434e579`（`ab3e80aba29f66c58654b52392c88c33266347c41d063817b6bc0eb2f42c228d`）；`q3_max_llm_attempts`、`q3_llm_timeout_ms` 用已核定值；兩組用同一個 `parameter_set_sha256` |

LLM 模式本身含規則兜底，所以 LLM 組裡有一部分題目其實是規則解析的。H1-Q3 是整組比較；H2-Q3 只看 `parsed_by=LLM`。

### 5.3 閘門

`LLM_share` <50% 時，H1-Q3 最多判 `INCONCLUSIVE_UNDERPOWERED`，報告寫「大多數題目由規則解析」。

### 5.4 題目來源，以及能不能當正式證據

| 來源 | 狀態 | 可以做什麼 | 不能做什麼 |
| --- | --- | --- | --- |
| yyin 出題包 s2（FEAT-2 #317／#369），`v0-pilot`、`evaluation_eligible=false`（D100-6） | 尚未交回 | `PILOT`：試跑、估計題目間變異。**D121-C：M3 先用這份預設題（和 team-eval）當 pilot** | 不能當 H1-Q3／H1-Q1 的正式證據。`q1_query_eval.py` 在這種情況下本來就不出正式指標 |
| FEAT-3 team-eval（#293，D112-1），`v0-pilot`、`evaluation_eligible=false`、`ENGINEERING`、`halves=["baseline"]` | builder 進行中；發包要 U12 | 重現性（表 B-3） | 它重播凍結輸出，組員端不跑模型，所以不會產生新的 LLM 對照資料 |
| 正式題目包（`v1`、`evaluation_eligible=true`） | 不存在。D121-C：由 yyin 依「三種事件」各出一組，每題準備多種說法；發包包在 `docs/research/handoff/yyin_q1q3_wording_v1/`（`v1`，使用者核准前 `evaluation_eligible=false`）。「三種事件」指哪三種：`UNKNOWN`，待使用者確認（§5.10） | 正式證據；H1-QW 的唯一資料 | 要有正式來源，且由使用者另外核准（D105 B-8、#293 定案表）；答案由 yyin 依影像標註，再經 U13 |

**事先登錄**：pilot 題和正式題不能重疊（用題目文字的 SHA-256 比對）。在 pilot 上看過結果後才改的 prompt，只能拿去跑正式題，而且要重新登錄。

### 5.5 表 M3-1

| 欄位 | 內容 |
| --- | --- |
| `question_pack`、`eligibility`、`source_class` | |
| `arm` | `RULE_ONLY(Baseline)`／`LLM_WITH_RULE_FALLBACK` |
| `n_questions_scored` | |
| `E_q3` ％ [95% CI] | |
| `F_q3[6 欄]` ％ | |
| 拒答正確率 ％ | |
| `P_cam`／`R_cam` ％ [95% CI] | |
| `LLM_share` ％ | 只有 LLM 組 |
| `TO`、`SI` ％ | 只有 LLM 組 |
| 捏造詞被拒的比例 ％ | 只有 LLM 組 |
| `K_call`、每次呼叫 ms、token | 只有 LLM 組 |
| `scorer_output_sha256`、`env_manifest_sha256` | |

另有表 M3-2（假設檢定），欄位同表 M1-2，分 H1-Q3、H1-Q1、H1-QW 三列，加一欄 `gate_LLM_share`。用字變因的明細另見表 M3-3（§5.10）。**現況：`NOT_RUN`。**

### 5.6 樣本數

依 §1.5：不一致的題目要 ≥30。以 `LLM_share`＝50%、其中一半與規則結果不同來估算，正式題至少要 **120 題**；少於 40 題時，預期不一致題數 <10，直接判 `INSUFFICIENT`，只做描述。

### 5.7 依賴、owner、時程

- 依賴：Baseline 的表 B-2 有數字（也就是有正式題目包和答案）；#118 正式索引；Codex 產生 LLM 組的 Q3 錄製（含 `q3_provider_audit`）。
- owner：Codex 負責 LLM 呼叫和錄製；Claude 負責題目去重、評分、統計、圖表；yyin 和組員負責出題與作答；使用者負責正式包核准、U12、U13。
- 時程（估計）：pilot 在 s2 交回後 1 天；正式比較在題目包和答案到位後 2 天，日期 `UNKNOWN`。

### 5.8 圖表規格

| 圖 | x 軸 | y 軸 | 標示 |
| --- | --- | --- | --- |
| G-M3a 欄位正確率分組長條 | 六欄加整題 | %（0～100） | 兩組並列，95% CI，寫 n |
| G-M3b `parsed_by` 分布 | LLM 組 | % | 分 LLM／RULE |
| G-M3c 2×2 配對矩陣 | Baseline 對／錯 | LLM 對／錯 | 格內是題數，符號檢定直接從這裡讀 |
| G-M3d Q1 森林圖 | `R_cam` 差（百分點） | ITT、`parsed_by=LLM` 子集 | 95% CI，寫 n |

pilot 的圖一律在標題加「PILOT_ONLY，非正式證據」。

### 5.9 可能失敗的情況

| 情況 | 對策 |
| --- | --- |
| 沒有正式題目包 | H1-Q3、H1-Q1 判 `NOT_RUN`；pilot 結果照實標 `PILOT_ONLY` |
| `LLM_share` <50% | 依閘門降級，並寫原因（逾時、規則先命中等） |
| LLM 捏造詞被拒的比例高 | 照實報告；這是 LLM 組的失敗，不從分母剔除 |
| 人工答案有爭議 | 該題記 `UNKNOWN`，兩組都不計，列出爭議題數 |

### 5.10 查詢用字是主要變因（D121-C）

使用者 2026-11-03 的原話：「目前題目先用預設的，快速發包給 yyin 讓他做三種事件的問題集，我認為差別關鍵在找事件時的用字，如：經過某轉角、經過外面」。據此事先登錄：

**設計**

- 一個「題族」＝同一個目標事件（同一場景、同一段時間窗、同一個要找的人或物）加上幾種不同說法。題族之內只改用字，不改要找的東西。
- 每個題族至少要有下面前三種說法各一句，第四種選填：

| 代號 | 說法類型 | 例子（只示範句型，不是正式題） |
| --- | --- | --- |
| `P` | 精確地點詞：講出具體的轉角、門口、走廊或鏡頭位置 | 「有人經過某轉角的時候」 |
| `V` | 模糊空間詞：只講大概的方位 | 「有人經過外面的時候」 |
| `T` | 時間詞：用時刻或相對時間指出事件 | 「開始後大約 20 秒有人經過」 |
| `C` | 組合（選填）：地點詞加時間詞 | 「開始後 20 秒左右，有人經過某轉角」 |

- 模糊說法的正確答案，可能本來就是「系統該反問」（`NEEDS_CLARIFICATION`）。這由 yyin 依影像和詞表判斷，寫進答案欄；評分照答案算，不因為是模糊說法就自動算成反問或自動算錯。
- 地點詞要能對到凍結的 camera／region 目錄。r004 的正式 region 目錄是否已凍結：`UNKNOWN`（#118／#113 的收據為準）。沒凍結前，`P` 類的正確 `region` 欄先標 `UNKNOWN`，該欄不計分，整題的其他欄照算。

**「三種事件」指哪三種：`UNKNOWN`，要請使用者確認。** 依 §D.1 和 §4.5 可以有三種讀法，本文件不自己選：

| 讀法 | 三組是 | 可行性 |
| --- | --- | --- |
| 甲：依資料集 | P1、A4-1、B4-1 | 三份都已渲染；P1 是 `SYNTHETIC`／`ENGINEERING`，它那一組只能判 `SUPPORTED_ENGINEERING_ONLY`，不能和 r004 合併（§D.6） |
| 乙：依情境類別 | 常見（A4-1、B4-1）、複雜甲、長卡（A4-2／B4-2） | 複雜甲還沒凍結（D114-2），長卡暫緩（#323），現在只有「常見」出得了題 |
| 丙：依事件類型 | 切鏡（SWITCH）、暫失回原鏡（RETURN）、盲區搜尋（SEARCHING） | 只用 A4-1、B4-1 就能出；但要讓 yyin 知道事件類型和大略時段，需要確認這樣算不算給了劇本答案（§1.2） |

題集包先做成三個空的事件組 `E1`、`E2`、`E3`，等使用者指定讀法後，由使用者轉交時一起告訴 yyin。

**假設與指標**

- 每個題族、每一組（Baseline／LLM）、每種說法 x，算整題正確率 `E_q3(x)`，和 Q1 的 `R_cam(x)`。
- **用字落差** `G_PV`＝`E_q3(P)` − `E_q3(V)`（百分點）；`G_PT`＝`E_q3(P)` − `E_q3(T)`。
- **用字敏感度** `S_w`＝同一題族內，各說法的結果（對／錯）不全相同的題族數 ÷ 題族數 × 100（%）。
- **H1-QW（主要）**：LLM 組的 `G_PV` 小於 Baseline 的 `G_PV`。分析單位是題族；每個題族的差值 d＝`G_PV`(Baseline) − `G_PV`(LLM)，對 d≠0 的題族做單尾精確符號檢定，和其他 H1 一起做 Holm 校正（§1.5）。判定標籤照 §1.6；不一致題族 <10 就判 `INSUFFICIENT`。
- 次要：`G_PT`、`S_w`、`R_cam` 的同樣比較；各事件組分開報告，不合併成一個數字。
- 閘門照 §5.3：`LLM_share` <50% 時，H1-QW 最多判 `INCONCLUSIVE_UNDERPOWERED`。
- 樣本數：每個事件組至少 10 個題族，三組合計至少 30 個題族（約 90～120 句）。

**表 M3-3：用字變因明細**

| 欄位 | 內容 |
| --- | --- |
| `event_group` | `E1`／`E2`／`E3`（實際指哪三種見上，`UNKNOWN`） |
| `family_id` | 題族編號 |
| `variant` | `P`／`V`／`T`／`C` |
| `arm` | `RULE_ONLY(Baseline)`／`LLM_WITH_RULE_FALLBACK` |
| `n_questions` | 句數 |
| `E_q3` ％ [95% CI] | 依題族分群 bootstrap |
| `F_q3[region]`、`F_q3[time_us]` ％ | 用字最直接影響的兩欄 |
| `R_cam` ％ [95% CI] | |
| 反問比例 ％ | 輸出 `NEEDS_CLARIFICATION` 的比例，另列「答案本來就是反問」的比例 |
| `parsed_by=LLM` ％ | 只有 LLM 組 |

加一張圖 **G-M3e**：x 軸是說法類型（P、V、T、C），y 軸是 `E_q3`（%），兩組各一條線，95% CI，分三個事件組畫小圖，每點寫 n。

**現況：`NOT_RUN`**。pilot（s2／team-eval）只能看出說法類型的分布和流程，不能判 H1-QW。

## 第三部分：實驗環境揭露

## 6. 環境 manifest

每一個 run（Baseline、M1 的每次 Agent 重複、M3、外包機的每次執行）都要附一份環境 manifest，報告逐一點名使用到的設備、套件和模型。manifest 本身的 SHA-256 寫進對應表格的 `env_manifest_sha256` 欄。

### 6.1 現有基準

`configs/q1q5/linked_baseline_environment.json`＠staging `434e579`（SHA-256 `2e75735c8d3b1e5c803f03e50b3eaffe8ade8166a949c9b96a731d85e72b592b`）記錄的值：

| 項目 | 值 |
| --- | --- |
| Python | 3.12.12 |
| machine | arm64 |
| 套件 | pydantic 2.13.5、numpy 2.5.4、Pillow 13.0.0、torch 2.6.0、torchvision 0.21.0、PyYAML 6.0.3、networkx 3.7、shapely 2.1.2、psycopg 3.3.6 |
| Ollama | 0.35.0 |
| 模型 | `qwen3:1.7b-q4_K_M`，digest `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7` |
| RT-DETR 權重 | SHA-256 `3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0`；source commit `df2a96c8c3a098567a1149bf0248da6efe6d495d` |
| 依賴權威 | `pyproject.toml`、`uv.lock`（`uv.lock`＠`434e579` SHA-256 `18c66a46f799efcfb4da36a15246245d2c959e42768a67b01f667eb73d284a17`） |

這份檔案沒有硬體、OS、隨機種子和逾時的欄位，所以需要擴充成下面的 manifest。

### 6.2 manifest 欄位（建議 schema 名 `amidst.experiment-env.v1`，PROPOSED）

| 群組 | 欄位 | 取得方式 |
| --- | --- | --- |
| 硬體 | `cpu_model`、`cpu_cores`、`gpu_model`（沒有就寫 `NONE`）、`gpu_driver`、`ram_gib`、`accelerator`（`mps`／`cuda`／`cpu`） | 標準函式庫加上平台指令；取不到的欄位寫 `UNKNOWN`，不猜 |
| OS | `os_name`、`os_version`、`kernel`、`arch` | `platform` 模組 |
| Python | `python_version`、`python_implementation`、`isolated_mode` | `sys` |
| 套件 | `uv_lock_sha256`、`pyproject_sha256`，以及實際安裝版本的清單 | 以 `uv.lock` 為權威；實際安裝版本和 lock 不一樣時列出差異 |
| 模型 | `llm_name`、`llm_digest`、`ollama_version`、`detector_name`、`detector_weights_sha256`、`detector_source_commit` | Ollama API 加上權重檔的 hash |
| 執行設定 | `switch_mode`、`parser_mode`、`parameter_set_sha256`、`agent_max_rounds`、`agent_call_timeout_ms`、`agent_total_budget_ms`、`q3_max_llm_attempts`、`q3_llm_timeout_ms`、`llm_temperature`、`llm_seed`、`torch_deterministic`、`random_seed` | runner 的參數集 |
| 程式 | `git_commit`（外包包則用包的 MANIFEST SHA-256） | |
| 時間 | `started_at_utc`、`finished_at_utc`、`wall_clock_s` | runner |

報告的附錄是一張「環境總表」：每個 `env_manifest_sha256` 一列，列出上面的所有欄位。所有表格都用這個 hash 對回去。

### 6.3 硬體基準（待補）與量測方式

本專案預設的執行架構是 Apple Silicon（arm64）加上本機 Ollama（§6.1）。記憶體大小、GPU 核心數、晶片型號目前都是 **`UNKNOWN`**，沒有寫進任何已提交的檔案。選模型和解讀延遲之前要先量，量法如下（只讀，不改系統設定）：

| 項目 | 量法（macOS） | 寫進 manifest 的欄位 |
| --- | --- | --- |
| 晶片型號 | `sysctl -n machdep.cpu.brand_string` | `cpu_model` |
| CPU 核心數（效能核／節能核） | `sysctl -n hw.perflevel0.physicalcpu hw.perflevel1.physicalcpu` | `cpu_cores` |
| 統一記憶體 | `sysctl -n hw.memsize`（bytes，換成 GiB） | `ram_gib` |
| GPU 核心數 | `system_profiler SPDisplaysDataType` 的 Total Number of Cores | `gpu_model` |
| macOS 版本 | `sw_vers -productVersion` | `os_version` |
| 模型實際佔用記憶體、跑在 GPU 還是 CPU | 模型載入後執行 `ollama ps`，看 SIZE 和 PROCESSOR 欄 | 新增 `llm_loaded_size_gib`、`llm_processor` |
| 整條流程的峰值記憶體 | `/usr/bin/time -l python -I run.py …` 的 maximum resident set size（外加 `ollama ps` 的模型大小） | 新增 `peak_rss_gib` |

**注意**：Ollama 頁面列的檔案大小是下載大小，不是執行時的記憶體。實際佔用還要加上 KV cache 和 RT-DETR，所以候選模型能不能用，以量到的 `llm_loaded_size_gib` 為準。

### 6.4 候選模型

**收錄規則**（看到任何實驗資料之前就固定）：

1. 有官方模型卡或技術報告，**而且** Ollama 官方 library 有對應的 tag。沒有可靠來源的不列。
2. Ollama 頁面標了 `tools` 能力。Agent 和 Q3 都需要結構化輸出；Ollama 的 structured outputs 是用 `format` 參數傳 JSON schema（[Ollama 部落格](https://ollama.com/blog/structured-outputs)）。
3. 授權允許本專案在本機做研究使用。
4. 在 §6.3 量到的記憶體下，`llm_loaded_size_gib`＋RT-DETR＋系統保留 ≤ 統一記憶體的 70%。沒量到之前，這一欄寫 `UNKNOWN`，不先排除也不先納入。

| 候選 | Ollama tag（下載大小） | 參數量／脈絡長度 | 授權 | 依據 | 選它的理由 |
| --- | --- | --- | --- | --- | --- |
| **現行對照** Qwen3 1.7B | `qwen3:1.7b-q4_K_M`（1.4 GB），digest `8f68893c…30e7`（§6.1） | 1.7B（非 embedding 1.4B）／32,768（Ollama 頁標 40K） | Apache 2.0 | [模型卡](https://huggingface.co/Qwen/Qwen3-1.7B)、[Qwen3 技術報告 arXiv:2505.09388](https://arxiv.org/abs/2505.09388)、[Ollama tags](https://ollama.com/library/qwen3/tags) | 現行設定；H1 的唯一模型 |
| Qwen3 0.6B | `qwen3:0.6b-q4_K_M`（523 MB） | 0.6B／40K | Apache 2.0 | 同上 | 同家族較小一級：看能力隨大小怎麼變，也是 CI 上唯一下載得動的真模型（§7.10） |
| Qwen3 4B | `qwen3:4b-q4_K_M`（2.6 GB） | 4B／40K | Apache 2.0 | 同上 | 同家族較大一級：檢查逾時是不是因為模型太小或太慢 |
| Qwen3 8B | `qwen3:8b-q4_K_M`（5.2 GB） | 8B／40K | Apache 2.0 | 同上 | 上限參考；記憶體不夠就依規則 4 排除 |
| Llama 3.2 3B | `llama3.2:3b`（2.0 GB） | 3B／128K | Llama 3.2 Community License | [官方模型卡](https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/MODEL_CARD.md)（BFCL V2 0-shot：3B 為 67.0，1B 為 25.7）、[Ollama 頁](https://ollama.com/library/llama3.2) | 不同家族、大小相近，官方有工具呼叫基準 |
| Phi-4-mini 3.8B | `phi4-mini:3.8b`（2.5 GB） | 3.8B／128K | MIT | [官方模型卡](https://huggingface.co/microsoft/Phi-4-mini-instruct)、[技術報告 arXiv:2503.01743](https://arxiv.org/abs/2503.01743)、[Ollama 頁](https://ollama.com/library/phi4-mini) | 不同家族、大小相近，官方支援 function calling。模型卡沒有公布工具呼叫分數，也提到它有時會捏造函式名稱，這一點要在 `SI` 裡觀察 |

**評估過但不列入**：

- Gemma 3 4B（[技術報告 arXiv:2503.19786](https://arxiv.org/abs/2503.19786)、[Ollama 頁](https://ollama.com/library/gemma3)）：Ollama 頁只標 `vision`，沒有標 `tools`，不符規則 2。
- Llama 3.2 1B：官方 BFCL V2 只有 25.7，而且同家族已有 3B。
- 第三方整理的 BFCL 分數（例如二手網站、未經查證的 arXiv 預印本）：不當作收錄依據。BFCL 本身的方法見 [Patil et al., ICML 2025](https://proceedings.mlr.press/v267/patil25a.html)，只用來說明工具呼叫能力有公開的評測方法，不拿它的排名替代本專案的實測。

Qwen3 有思考模式和非思考模式（模型卡：`enable_thinking`，或在提示裡加 `/think`、`/no_think`）。思考模式會大幅增加延遲，所以實驗**固定用非思考模式**，取樣參數照模型卡的非思考建議值（temperature 0.7、top_p 0.8、top_k 20），並記錄 `llm_seed`。其他家族的模型用各自模型卡的建議值；模型卡沒寫就用 temperature 0。這些設定都寫進參數集。

### 6.5 M4：候選模型比較（探索性）

- **H1 只用現行模型** `qwen3:1.7b-q4_K_M`，這是事先固定的，不會因為別的模型表現較好就替換。
- **M4** 用同一套輸入、提示、時間預算和評分，把 §6.4 的候選模型都跑一次，看能力與成本怎麼取捨。結果全部標 `EXPLORATORY`。
- 每個模型、每個模組（Q2 Agent、Q3）都產出表 M4-1：

| 欄位 | 內容 |
| --- | --- |
| `model`、`llm_digest`、`quant` | |
| `llm_loaded_size_gib`、`peak_rss_gib`、`llm_processor` | §6.3 |
| `C_evt` ％ [95% CI]（Q2）／`E_q3` ％ [95% CI]（Q3） | 與 Baseline 的差（百分點）一併列出 |
| `TO`、`SI`、`FB`（或 `LLM_share`）％ | |
| 每次呼叫 ms 中位數／P90 | |
| `n` | 計分單位數 |

- 圖 G-M4：x 軸是每次呼叫 ms 中位數（對數軸），y 軸是 `C_evt` 或 `E_q3`（%），每個模型一個點，點的大小代表 `llm_loaded_size_gib`，誤差線是 95% CI，Baseline 畫成水平虛線，每個點標 n。
- 如果之後想把別的模型換成主線，要另寫一份新的事先登錄，用新資料重新檢驗，不能沿用 M4 的資料。
- **範圍已定（D121-E，使用者 2026-11-03 選選項 1）**：Qwen3 0.6B／1.7B／4B／8B，加上 Llama 3.2 3B、Phi-4-mini 3.8B，共 6 個（§6.4 表）。8B 仍依規則 4，記憶體不夠就排除並寫明理由。
- 依賴：Baseline 完成；§6.3 硬體量完。owner：Codex 執行，Claude 評分與作圖。時程（估計）：每個模型每個模組 0.5 天。

## 第四部分：跨平台外包執行包

## 7. 跨平台外包執行包

### 7.1 目的與順序

1. demo 結束後，先在本機（Mac）把完整系統錄一次影片紀錄。影片是 LOCAL，committed 文件只列路徑、大小和 SHA-256。這段影片只是展示紀錄，不是實驗數據。
2. 再把「模型對系統的測試」外包到其他作業系統：整包帶過去跑，回傳原始輸出和環境 manifest，**評分在我們這邊做**。
3. 順序：先用 GitHub Actions 跑環境腳本和不含 GT 的小型 smoke test（§7.10），通過後才把真正的數據 run 交給外包機：**先 Linux，再 Windows**。本機沒有 Docker、雙系統或虛擬機，所以不在本機做跨平台驗證。
4. 這個包和 FEAT-3 team-eval 不同：team-eval 重播凍結輸出、不跑模型（D96-2）；外包包要在外包機上**實際跑** RT-DETR 和 Qwen3。

### 7.2 包的內容（照 r004 v2 組員包格式）

| 放 | 內容 |
| --- | --- |
| `README` | 三節：**工作內容**、**要提交的項目**、**操作步驟**，外加「不要改」 |
| `RETURN/README.txt` 與指定的 RETURN 檔名 | `RETURN/外包結果_<代號>_<OS>_YYYY-MM-DD.zip`（內含輸出、manifest、log） |
| `MANIFEST.json` | 逐檔 SHA-256，分成不可變 payload 和 RETURN／STATE 兩類 |
| `tools/verify_pack.py` | 驗 MANIFEST；回收時也用它判定 VALID／INVALID |
| `run.py` | 跨平台的 Python 入口（不用 `.command`，也不用 `.bat` 當主要入口） |
| `scripts/ensure_env.py` | 環境檢查與自動安裝（規格見 §7.9）；產出 §6 的環境 manifest |
| 凍結輸入 | 正式 run 的 safe bundle（RGB 或來源綁定的安全欄位）、凍結索引、request、參數集。**不含 GT、劇本、渲染軌跡、visibility、depth** |
| runner 程式 | 對應 staging commit 的必要模組，以 `uv.lock` 鎖版本 |

**不放**：GT、評分器的正確答案、劇本、任何答案檔。禁止內容掃描沿用 #318（`scripts/check_handoff_pack.py` 的 `scan()`）。**模型權重和 Ollama 模型檔也不放**（決定 D 已定案，§9）：由 `scripts/ensure_env.py` 依 digest／SHA-256 下載並驗證，不符就停下。包裡只放一份權重清單（名稱、來源 URL、SHA-256 或 Ollama digest）。

### 7.3 跨平台要求

- 入口：`python run.py --task <baseline|agent|q3>`，Python ≥3.12，用 `-I` 執行。
- 路徑：一律用 `pathlib`，包內路徑以包根目錄為基準的相對路徑；不寫死 `/`，不假設大小寫敏感；檔名只用 ASCII（中文檔名在 Windows ZIP 解壓有編碼風險，RETURN 檔名的「外包結果」需要實測，失敗就改用 ASCII 名）。
- 文字檔一律用 UTF-8 讀寫，換行固定 `\n`，避免 Windows 的 `\r\n` 改到輸出 hash。
- 加速器：依序偵測 `cuda`、`mps`、`cpu`，寫進 manifest；不允許靜默改變 batch size 或精度。
- 時間：只用 source clock 和單調時鐘；不使用本機時區。

### 7.4 RETURN 內容

| 項目 | 說明 |
| --- | --- |
| `env_manifest.json` | §6 的全部欄位 |
| `outputs/` | 決策錄製、Q3 解析回應、Q1 結果（原始輸出，不含分數） |
| `output_sha256.json` | 每個輸出檔的 SHA-256 |
| `timing.json` | 每個 task 的牆鐘時間、每步 `T_step`、每次模型呼叫的 ms |
| `logs/` | runner log（不含私人路徑） |
| `pack_manifest_sha256` | 必須等於發出去的包 |

### 7.5 回收與評分（在我們這邊）

1. `verify_pack.py` 驗 RETURN：VALID／INVALID。INVALID 就整份不計（§1.4 第 10 項）。
2. 驗 `output_sha256`，並檢查 `env_manifest` 是否完整。
3. Claude 的評分端讀劇本／答案計分，產出與表 B-1、M1-1、M3-1 同格式的表，`source_class` 不變，另加 `os` 欄。
4. 跨 OS 比較表 X-1：

| 欄位 | 內容 |
| --- | --- |
| `os`、`env_manifest_sha256` | |
| `task`、`arm` | |
| `output_hash_equal_to_mac` | 是／否（逐檔） |
| `decision_diff_count` | 與 Mac 對照 run 決策不同的步數 |
| `C_evt`／`E_q3`／`R_cam` ％ [95% CI] | |
| `TO`、`SI`、`FB` ％ | |
| `T_step` 中位數／P90 ms | |
| `wall_clock_s` | |

**現況：`NOT_RUN`。**

### 7.6 已知變因與 Mac 對照 run

| 變因 | 影響 | 處理方式 |
| --- | --- | --- |
| 浮點運算差異（CPU／CUDA／MPS 的 kernel 不同） | RT-DETR 偵測分數的末位不同，可能跨過門檻，改變偵測或決策 | 記錄 `accelerator`；比較偵測輸出的差異分布；決策不同的步驟逐一列出 |
| 模型非決定性（Ollama 的取樣、執行緒排程） | Agent 和 Q3 LLM 的回應不同 | 固定 `llm_temperature`、`llm_seed`；Agent 每個 request 跑 K＝5 次，比較的是分布，不是單次 |
| 速度差異 | 逾時率不同，連帶 fallback 比例不同 | `TO`、`FB` 依 OS 分列；不用 Mac 的逾時率去推其他 OS |
| 套件版本 | 實際安裝和 `uv.lock` 不一樣 | `ensure_env.py` 不符合就停下；manifest 列出差異 |

**Mac 對照 run**：同一份包（同一個 MANIFEST SHA-256），在 Mac 上用 `run.py` 跑一次完整流程，產出 Mac 的 RETURN。跨 OS 的差異一律以這份 Mac RETURN 為對照，而不是拿 repo 裡的正式鏈錄製來比，避免把「包」和「平台」兩種差異混在一起。

RULE_ONLY 的決策只依賴偵測輸出，偵測一樣時決策 hash 應該相同，可以用來分辨差異是來自偵測還是 Agent。

### 7.7 可行性風險與預估工時（估計）

| 風險 | Linux | Windows | 對策 |
| --- | --- | --- | --- |
| torch 2.6.0／torchvision 0.21.0 的平台 wheel 與 CUDA 版本 | 中 | 中高 | `uv.lock` 要包含對應平台的 wheel；沒有 GPU 時走 CPU，manifest 標明 |
| Ollama 0.35.0 安裝與指定 digest 的模型 | 低 | 中 | README 寫安裝步驟；`ensure_env.py` 驗 digest，不符就停下 |
| 模型權重的授權與大小 | 低 | 低 | 決定 D 定案：包內不放權重，外包機自行下載後驗 hash，所以不涉及再散布 |
| 路徑、編碼、換行 | 低 | 高 | §7.3；先在 Linux 驗證 hash 穩定，再做 Windows |
| PostgreSQL（psycopg）依賴 | `UNKNOWN` | `UNKNOWN` | 見 §7.11 量法 1；需要資料庫的話改用包內的凍結檔 |
| 包的大小（RGB 與凍結輸入；權重不放） | `UNKNOWN` | `UNKNOWN` | 見 §7.11 量法 2；只放 A4-1／B4-1 需要的影格 |
| 外包機無法上網 | `UNKNOWN` | `UNKNOWN` | 決定 D 已定為「不放權重、線上下載」，所以外包機必須能連到權重來源和 Ollama registry。發包前要先問外包者；不能上網的機器不收，不在包裡改放權重（要改就得重新決定 D） |

| 工作 | owner | 估計工時 |
| --- | --- | --- |
| 本機完整影片紀錄 | 使用者或 Codex | 0.5 天 |
| `run.py`、跨平台路徑、`ensure_env.py`、manifest | Codex | 1.5～2 天 |
| 包的 builder、MANIFEST、verify、README、禁止內容掃描 | Codex（沿用 #318、FEAT-3 的做法） | 1 天 |
| Mac 對照 run | Codex | 0.5 天 |
| Linux 實測與修正 | 外包者＋Codex | 1～2 天 |
| Windows 實測與修正 | 外包者＋Codex | 2～3 天 |
| 回收評分、跨 OS 表 X-1 與圖 | Claude | 1 天 |

### 7.8 圖表規格

| 圖 | 規格 |
| --- | --- |
| G-X1 跨 OS 指標點圖 | x：OS（Mac 對照、Linux、Windows）；y：`C_evt`／`E_q3`（%）；95% CI；寫 n |
| G-X2 決策差異 | x：OS；y：與 Mac 決策不同的步數；依來源（偵測差異／Agent 回應差異）堆疊 |
| G-X3 速度與逾時 | x：`T_step`（ms，對數軸）；每個 OS 一條 ECDF；圖例寫 `TO` ％ 與 n |

### 7.9 環境檢查與自動安裝腳本 `scripts/ensure_env.py`（規格；實作歸 Codex，demo 後做）

依 AGENTS.md，launcher 和執行環境歸 Codex。本節只定規格和驗收條件。

**原則**

- 只裝到專案本地環境（包目錄裡的 `.venv`，加上 Ollama 自己的模型目錄）。不改系統設定、不改 PATH、不要求系統管理員權限、不裝系統層級的套件。
- 每一步（檢查、安裝、結果、耗時）都寫進環境 manifest 的 `ensure_env_steps` 陣列。
- 裝不起來就停下，給一個明確的錯誤碼和手動步驟，不靜默降級（例如不可以悄悄改用別的模型或別的 torch 版本）。
- 入口：`python -I scripts/ensure_env.py [--check-only] [--models <tag,…>] [--offline]`。`--check-only` 只檢查，不安裝。

**檢查與安裝步驟**

| 順序 | 檢查 | 缺的時候怎麼裝 | 裝不了時的錯誤碼 |
| --- | --- | --- | --- |
| 1 | Python ≥3.12（基準 3.12.12） | 不自動裝，只給下載指示 | `ENV_PYTHON_VERSION` |
| 2 | 磁碟可用空間 ≥（套件＋模型＋輸出的估計量；數字在包建好後量出並寫進 README） | 不裝；列出需要多少、還差多少 | `ENV_DISK_LOW` |
| 3 | `uv` 存在 | 用 uv 官方的獨立安裝方式裝到使用者目錄；不能自動裝時給手動步驟 | `ENV_UV_MISSING` |
| 4 | 套件和 `uv.lock` 一致 | `uv sync --frozen`（裝到專案的 `.venv`） | `ENV_LOCK_SYNC_FAILED` |
| 5 | Ollama 存在，版本＝0.35.0（或核定的範圍） | 不自動裝 Ollama 本體（要系統安裝程式），給各 OS 的安裝連結 | `ENV_OLLAMA_MISSING`／`ENV_OLLAMA_VERSION` |
| 6 | Ollama 服務可連線 | 提示啟動方式 | `ENV_OLLAMA_UNREACHABLE` |
| 7 | 指定模型的 digest 正確 | `ollama pull <tag>`，pull 完再驗 digest | `ENV_MODEL_DIGEST_MISMATCH`／`ENV_MODEL_PULL_FAILED` |
| 8 | RT-DETR 權重 SHA-256＝`3ba8b5c9…66f0` | 依權重清單的來源下載到專案本地目錄，下載完驗 SHA-256（決定 D 定案：包內不放權重） | `ENV_DETECTOR_WEIGHTS_MISMATCH`／`ENV_DETECTOR_DOWNLOAD_FAILED` |
| 9 | 加速器偵測（cuda／mps／cpu） | 不裝驅動；記錄結果 | 不算錯誤，只記錄 |
| 10 | 寫出環境 manifest 並算 SHA-256 | — | `ENV_MANIFEST_WRITE_FAILED` |

**結束碼**：全部通過回 0；任一步失敗回非 0，並把錯誤碼印在最後一行（方便 CI 和外包者回報）。

**驗收條件**

1. `--check-only` 在已備妥的 Mac 上回 0，產生的 manifest 欄位與 §6.2 一一對應，沒有 `UNKNOWN` 以外的空值。
2. 在乾淨環境（GitHub Actions 的 ubuntu-latest、windows-latest）上：步驟 3、4 會自動完成；步驟 5～8 依 §7.10 的 smoke 設定通過，或回傳預期的錯誤碼。
3. 每一個錯誤碼都有一個 focused 測試，用假環境觸發，斷言錯誤碼和手動步驟文字。
4. 用 grep 檢查原始碼，沒有任何 `sudo`、修改系統 PATH、寫入家目錄設定檔的指令。
5. 跑兩次結果相同（冪等）：第二次執行不重裝任何東西，manifest 除了時間欄位以外 hash 相同。
6. 不讀、不送任何 GT、劇本或答案路徑（#307 守門）。

**Colab 分支（只寫規劃，不寫實作；用途見 §7.12）**

| 步驟 | Colab 上的差異 | 規劃 |
| --- | --- | --- |
| 偵測 | 環境變數 `COLAB_RELEASE_TAG` 或可 import `google.colab` | manifest 加 `platform_kind=COLAB`、`colab_runtime_version`（Runtime > Change runtime type 裡選的版本）、`colab_tier`（FREE／PAYG／PRO／PRO_PLUS；由使用者填，腳本不猜） |
| 1 Python | 2026.10 版 runtime 是 Python 3.13；基準是 3.12.12 | 不改系統 Python；用 uv 在 `.venv` 裝 3.12.12（`uv python install`），或選 Python 3.12 的 pinned runtime（2026.07 是 3.12.13）。兩者都記進 manifest |
| 4 套件 | Colab 預裝 torch 2.11 | 不用預裝版；`uv sync --frozen` 裝 `uv.lock` 的 torch 2.6.0／torchvision 0.21.0 到 `.venv`。`uv.lock` 有沒有 Linux x86_64 的 CUDA wheel：`UNKNOWN`（與 §7.7 同一個風險），沒有就停在 `ENV_LOCK_SYNC_FAILED` |
| 5～7 Ollama | 沒有 systemd | 用 Ollama 官方 Linux 安裝指令裝到 VM，再在背景跑 `ollama serve`；VM 是一次性的，所以這一步不算「改系統設定」。pull 後照常驗 digest |
| 9 加速器 | T4 等 NVIDIA GPU | 記 `nvidia-smi` 的 GPU 型號、driver 版本、CUDA 版本；拿不到就寫 `UNKNOWN` |
| 2 磁碟 | 本機磁碟大小官方沒公布 | 開跑時量 `df`，寫進 manifest；不足就 `ENV_DISK_LOW` |
| 新增 | session 會斷 | 每個 task 結束就把輸出和 manifest 寫成一份 RETURN 子包；斷線後重跑時，已完成且 hash 驗過的 task 不重跑 |

### 7.10 跨平台驗證：GitHub Actions smoke（需要使用者授權）

本機沒有 Docker、雙系統或虛擬機可以測，所以跨平台驗證分成兩層：

| 層 | 在哪裡跑 | 跑什麼 | 證明什麼 |
| --- | --- | --- | --- |
| smoke | GitHub Actions 矩陣：`ubuntu-latest`、`windows-latest`，必要時加 `macos-14` | `ensure_env.py`；用 repo 內已提交的 SYNTHETIC fixture 跑 RULE_ONLY 重播；Agent／Q3 路徑用 mock provider，或極小的真模型 `qwen3:0.6b-q4_K_M` | 環境腳本、路徑、編碼、換行和管線在各 OS 都能跑；RULE_ONLY 重播的輸出 hash 跨 OS 一致 |
| 數據 run | 外包機（先 Linux、再 Windows） | §7.2 的整包，跑正式凍結輸入 | 第一部分與第二部分的數字 |

**smoke 的內容限制**

- 只用 repo 裡已經提交的 SYNTHETIC fixture。P1 包和正式 run 的 safe bundle 都是 LOCAL，不上傳到 Actions。
- 不放任何 GT、劇本、答案；不使用任何 secret（包括 `OPENAI_API_KEY`）。
- smoke 的結果不進任何數字表（§1.4 第 12 項）。

**Actions 的限制**（依 GitHub 官方文件，2026-11-02 查閱）

| 項目 | 內容 | 來源 |
| --- | --- | --- |
| 硬體 | public repo 的 `ubuntu-latest`、`windows-latest`：4 CPU、16 GB RAM、14 GB SSD、x64；`macos-14`：3 核 M1、7 GB RAM、14 GB SSD、arm64；標準 runner 沒有 GPU | [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) |
| 時間 | 每個 job 最多 6 小時；Free 方案同時最多 20 個 job，其中 macOS 最多 5 個 | [Actions limits](https://docs.github.com/en/actions/reference/limits) |
| 費用 | `Polalalabear/amidst` 是 public repo；public repo 使用標準 runner 免費 | [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) |
| 模型下載 | 14 GB SSD 要放套件（torch 本身就很大）和模型。smoke 只用 `qwen3:0.6b-q4_K_M`（523 MB）或 mock；不在 CI 上跑 1.7B 以上的模型 | §6.4 |
| 速度 | 沒有 GPU，又是 CPU 推論，延遲和逾時率**不能**代表實機，smoke 不報延遲 | — |
| Ollama 安裝 | runner 上要先裝 Ollama 本體，Windows runner 的安裝方式要實測 | 風險，見下 |

**授權**：repo 目前沒有任何 workflow（`gh api repos/Polalalabear/amidst/actions/workflows` 回傳 `total_count=0`）。**已授權（D121-F，使用者 2026-11-03 選選項 1）**：新增一個只能手動觸發（`workflow_dispatch`）的 workflow，矩陣是 `ubuntu-latest`、`windows-latest`；不在 push 或 PR 時自動執行，也不加 `macos-14`（要加要另外授權）。workflow 檔由 Codex 寫、Claude 審，demo 後做；本文件只記授權，不新增 `.github/workflows/` 檔案。

**驗收條件**

1. 矩陣中每個 OS 的 `ensure_env.py --check-only` 與安裝流程都依 §7.9 的驗收條件 2 通過。
2. RULE_ONLY 重播在三個 OS 上的輸出 SHA-256 相同；不同時列出差異檔案並追查（路徑、換行、浮點）。
3. mock 或 0.6B 的 Agent／Q3 路徑能跑完，錄製通過 #127 kit 的 schema 檢查。
4. 每個 job 上傳環境 manifest 當 artifact（保留天數依 repo 預設），不上傳任何 LOCAL 資料。

| 工作 | owner | 估計工時 |
| --- | --- | --- |
| `ensure_env.py` 與錯誤碼測試 | Codex | 1～1.5 天 |
| workflow 檔（授權後）與 smoke fixture 接線 | Codex 寫，Claude 審 | 0.5～1 天 |
| Windows runner 的 Ollama 安裝與路徑修正 | Codex | 0.5～1 天 |

### 7.11 仍是 `UNKNOWN` 的兩項與量法

**1. PostgreSQL（psycopg）依賴**：`psycopg 3.3.6` 在基準環境的套件清單裡（§6.1），但外包流程的 runner 實際上需不需要資料庫，目前不知道。量法（Codex，在建包之前做）：

1. 從 `run.py` 的每個 task 入口追 import，列出會 import `psycopg` 的模組（用 `python -I -X importtime` 或在 import 時記錄的測試）。
2. 在本機先停掉 PostgreSQL 服務，用 `--task baseline`、`--task agent`、`--task q3` 各跑一次極小的 SYNTHETIC 輸入，記錄有沒有連線錯誤。
3. 結果寫成一行：`postgres_required=true|false`，並附需要的資料表清單。`true` 時，改成包內的凍結檔，或在 README 寫明安裝步驟。這個決定要回報協調者。

**2. 包的大小**：決定 D 後包裡不放權重，大小只剩凍結輸入、程式和 `uv.lock`；外包機需要的總空間則要另外加上下載的套件與模型。量法：

| 項目 | 怎麼量 | 寫到哪裡 |
| --- | --- | --- |
| 包本身（ZIP 與解壓後） | builder 產包後執行 `du -sh` 並記錄 ZIP 的位元組數；MANIFEST 逐檔大小加總 | README、包收據 |
| 凍結輸入（A4-1／B4-1 影格、索引） | 依 MANIFEST 分類加總 | 包收據 |
| 外包機需下載的套件 | 在 GitHub Actions 的乾淨 runner 上跑 `uv sync --frozen` 前後，比較 `.venv` 大小 | `ensure_env.py` 的 `ENV_DISK_LOW` 門檻 |
| 外包機需下載的模型 | 依 §6.4 的 Ollama 下載大小加總要跑的模型；pull 後再用 `ollama list` 核對 | 同上 |
| 輸出（RETURN） | Mac 對照 run 的 RETURN ZIP 大小 | README |

量出來之前，這些格子一律寫 `UNKNOWN`，不估計。

### 7.12 Google Colab 作為外包執行平台（評估）

使用者 2026-11-03 問「能在 Colab 上運行嗎」。以下依 Colab 官方文件（查詢日 2026-11-03）；官方沒寫的寫 `UNKNOWN`，第三方說法標「非官方」。

| 面向 | 官方文件怎麼說 | 對本企劃的意思 |
| --- | --- | --- |
| 作業系統 | Colab 的託管 runtime 是 Linux VM（Ollama 官方 Linux 安裝方式可用，見下） | 可以當「Linux 外包機」的一種，但不是一台固定的機器 |
| GPU | 免費版「GPU 等昂貴資源的使用受到嚴格限制」；GPU／TPU 的型號「會隨時間改變」；付費方案可以「視供應情況」用到較高階的 GPU；資源「不保證、也不是無限」，用量上限不公布 | 免費版拿到 T4 是常見的第三方說法（非官方），官方沒有保證型號。每次 run 的 GPU 型號都要記進 manifest |
| 單次時長 | 免費版 notebook 最多跑 12 小時，視供應和使用情況而定；Colab Pro+ 在運算單元足夠時可連續執行最多 24 小時 | 一個 task 要在一個 session 內跑完，或能斷點續跑（§7.9 Colab 分支） |
| 閒置斷線 | 「閒置時 runtime 會逾時」；VM 閒置一段時間後會被刪除；確切分鐘數官方不公布 | 閒置時間：`UNKNOWN`（第三方常見說法約 90 分鐘，非官方）。長時間的 Agent K＝5 重複要拆成多個 task |
| 禁止事項 | 免費版且沒有運算單元餘額時，不能用 SSH 之類的遠端控制，也不能跑分散式運算 worker | 只能在 notebook 裡直接執行 `run.py`，不能把 Colab 當遠端 worker 接回本機 |
| 磁碟 | 官方 FAQ 沒寫大小；只說「多買 Google Drive 空間不會增加 Colab VM 的磁碟」 | 磁碟大小：`UNKNOWN`，開跑時用 `df` 量；VM 結束後本機磁碟會清掉 |
| Python／torch | 2026.10 runtime：Python 3.13.18、PyTorch 2.11.0；2026.07：Python 3.12.13、PyTorch 2.11.0；舊版 runtime 發布後保留 1 年，可在 Runtime > Change runtime type 選 | 基準是 Python 3.12.12、torch 2.6.0／torchvision 0.21.0。Colab 預裝的 torch 不能直接用，要在 `.venv` 照 `uv.lock` 裝；RT-DETR 在 torch 2.6.0 的 Linux CUDA wheel 上能不能跑：`UNKNOWN`，要先在 smoke 上驗。T4 的 CUDA 支援由 torch 的 CUDA wheel 決定，driver 版本官方 runtime 文件沒寫：`UNKNOWN` |
| Ollama／Qwen3 | Ollama 官方 Linux 安裝：`curl -fsSL https://ollama.com/install.sh \| sh`；沒有 systemd 時手動 `ollama serve`；NVIDIA GPU 要有 driver，可用 `nvidia-smi` 檢查 | 技術上可以裝 Ollama 0.35.0 並 pull `qwen3:*`，但版本鎖定要另外驗（安裝腳本預設裝最新版）。Colab 官方文件沒有提 Ollama：是否違反 Colab 使用規定，官方沒有直接說明，`UNKNOWN`；目前看到的禁止事項不包含本機推論 |
| 資料上傳 | — | **只能上傳 safe 包**（§7.2 的凍結輸入，RGB 或安全欄位、索引、request、參數集），上傳前跑禁止內容掃描（#318）。GT、劇本、渲染軌跡、visibility、depth、人工答案**一律不上雲**，也不放 Google Drive。評分仍在本機（§1.2） |
| 可重現性 | runtime 版本可選，但 GPU 型號和 driver 不固定 | manifest 必填：`colab_runtime_version`、GPU 型號、driver 版本、CUDA 版本、`nvidia-smi` 原文的 SHA-256。同一個 MANIFEST 的包在不同 session 拿到不同 GPU 時，要分開報，不合併延遲數字 |

**和其他執行平台比較**

| 平台 | 作業系統 | GPU | 費用 | 能產出什麼 | 主要限制 |
| --- | --- | --- | --- | --- | --- |
| GitHub Actions（D121-F 已授權，手動觸發） | ubuntu-latest、windows-latest | 沒有 | public repo 免費 | 只能證明環境和管線能跑（smoke），**不能產出任何數字** | 14 GB SSD、CPU 推論；smoke 結果不進數字表（§1.4 第 12 項） |
| Windows／Linux 外包機（§7.1～§7.8） | 固定一台 | 看機器 | 看外包者 | 正式的跨 OS 數字（表 X-1） | 要找人、要能上網、來回時間長 |
| Google Colab | Linux（一次性 VM） | 免費版有機會拿到，但型號和供應不保證 | 免費，或付費方案 | M4 的延遲、`TO`、`FB` 數據（GPU 條件下） | 12 小時上限、閒置斷線、GPU 不固定、不能上傳 GT |
| 本機 Mac | macOS arm64 | Apple Silicon（Metal） | 0 | Baseline 和 H1 的主數據 | 只有一個平台 |

**建議定位**

1. Colab 是這幾個選項裡**唯一免費又有 GPU** 的平台，適合拿來產出 **M4 候選模型在 GPU 上的延遲、`TO`、`FB` 數據**，和放寬逾時探索組（§3.12）的校準量測參考。
2. Colab **不能當正式主數據的唯一來源**：GPU 型號和供應不保證，同一份包兩次可能跑在不同硬體上，跨 session 的可重現性比固定外包機差。H1 的主數據仍以本機 Mac（和固定的外包機）為準。Colab 的結果標 `EXPLORATORY`，`source_class` 不變，另加 `platform_kind=COLAB`。
3. 順序：先過 GitHub Actions 的 smoke → 再上 Colab（Linux＋GPU）→ 再交固定的 Windows／Linux 外包機。
4. 要不要用付費方案（Pay As You Go、Pro、Pro+）是費用決定，由使用者決定；本企劃預設只用免費版。

依據（官方，2026-11-03 查詢）：

- 〈Colaboratory – Frequently Asked Questions〉，<https://research.google.com/colaboratory/faq.html>
- 〈Frequently Asked Questions – Past Runtime Versions〉，<https://research.google.com/colaboratory/runtime-version-faq.html>
- Ollama〈Linux〉，<https://docs.ollama.com/linux>

## 8. 資料到位就能開跑：檢查表

每一項都要附證據（命令輸出、SHA-256、留言連結）。任何一項沒勾，該段不開跑。

### 共用

- [ ] 本文件的事先登錄 commit SHA 已記在結果紀錄。
- [ ] 分析腳本已在 SYNTHETIC fixture 上通過，SHA-256 已記錄，之後不再修改。
- [ ] 磁碟可用 ≥9 GiB（`df -g /`）。
- [ ] 每個 run 的環境 manifest（§6）都已產出，`env_manifest_sha256` 已記錄。
- [ ] GT 隔離檢查（#307 守門、#127 kit GT 掃描）對決策錄製 PASS。

### 第一部分 Baseline

- [ ] CX-7 #115 的 safe bundle 與收據已交、已審；run／clock 的 SHA-256 已填。
- [ ] #118、#329 索引已交，SHA-256 已填；seed 依 D114-1 選定。
- [ ] 劇本凍結 `ab45a832…` 未變；G4 `9d99f87e…bc76c` 仍生效。
- [ ] FEAT-1 已合入，正式鏈用 `RULE_ONLY` 跑完 A4-1、B4-1。
- [ ] v1 評分器 bytes＝`97564e40…b6d3dc`。
- [ ] `R_hash`＝100%，#127 kit 0 FAIL（或逐項寫 NOT_APPLICABLE 的原因）。
- [ ] 表 B-1 已加 `fps` 欄；每個計分事件的進入窗口都至少含 1 幀（§D.3），不含的已標 `UNKNOWN`。
- [ ] D70 原文位置，以及 P1 20 fps 的參數換算，已由 Codex 確認（§D.2）。
- [ ] 表 B-4（吞吐與儲存，§P.4）每列都有實測值與 `env_manifest_sha256`；外推值都標 `EXTRAPOLATED`。
- [ ] 表 B-1 每列都有數字；計分事件合計已數出（≥20 或標 `INSUFFICIENT_FOR_COMPARISON`）。
- [ ] Q1／Q3：正式題目包已核准，或表 B-2 標 `NOT_RUN`。
- [ ] team-eval：U12 已同意、包已發、回件已收，或表 B-3 標 `NOT_RUN`。

### 第二部分

- [ ] Baseline 完成（§2.7）。
- [x] 已核定的 Agent 上限已查到（§3.12）：`agent_call_timeout_ms`＝2000、`agent_total_budget_ms`＝5000、`agent_max_rounds`＝3，`parameter_set_v1.json`＠staging `434e579`。
- [ ] 參數集整份核准（`approval.status` 現在是 `PROPOSED`），並綁到 r004 正式 run（`applies_to.run_ids` 現在是空的；`run_bound_approval` 現在是 `UNRESOLVED`）。
- [ ] `q3_llm_timeout_ms`（`PROPOSED` 2000）和 `q3_max_llm_attempts`（`PROPOSED`，值 `null`）已核定。
- [ ] 放寬逾時探索組的上限（PROPOSED 11000／33000 ms）已做 r004 pilot 校準（≥100 次呼叫的 P99），並由使用者核定（§3.12）。
- [ ] M1：兩組的 `parameter_set_sha256` 只差 mode 欄位（附 diff）。
- [ ] M2：FEAT-6、FEAT-4 已合入，v2 SHA-256 已填；U6 設定檔＝`0daa1508…bd3b7e`；甲是否凍結已確認。
- [ ] M3：正式題數 ≥40（≥120 才有足夠檢定力）；pilot 和正式題不重疊。
- [ ] M3：「三種事件」指哪三種已由使用者確認（§5.10，現在 `UNKNOWN`）；yyin 題集包已回件，每個事件組 ≥10 個題族，每個題族都有 P、V、T 三種說法；`evaluation_eligible` 已由使用者核准改成 true。
- [ ] M3：r004 的 region 目錄是否凍結已確認（沒凍結時 `P` 類的 region 欄不計分）。

### 第三部分 硬體與候選模型

- [ ] §6.3 的硬體欄位都量到了（`ram_gib`、`gpu_model` 等不再是 `UNKNOWN`）。
- [ ] 每個候選模型的 `llm_loaded_size_gib` 已量，依 §6.4 規則 4 決定納入或排除，並寫下理由。
- [x] 決定 E 已定（D121-E）：6 個候選模型。

### 第四部分 外包

- [ ] 本機影片紀錄的 LOCAL 路徑、大小、SHA-256 已記錄。
- [ ] `ensure_env.py` 已交件，§7.9 的驗收條件全部通過。
- [x] 決定 F 已授權（D121-F）：只能手動觸發的 `workflow_dispatch`，ubuntu-latest、windows-latest。
- [ ] workflow 檔已由 Codex 寫好、Claude 審過；GitHub Actions smoke 依 §7.10 的驗收條件通過。
- [ ] 用 Colab 時（§7.12）：上傳的只有 safe 包，禁止內容掃描 PASS；manifest 有 `colab_runtime_version`、GPU 型號、driver 版本。
- [ ] 包的 MANIFEST SHA-256 已記錄；禁止內容掃描 PASS（沒有 GT、劇本、答案）。
- [ ] Mac 對照 run 已完成。
- [x] 決定 D 已定案（協調者，D104 低階，2026-11-02）：包內不放權重。
- [ ] 權重清單（名稱、來源 URL、SHA-256／digest）已寫進包，`ensure_env.py` 依清單下載並驗證。
- [ ] §7.11 的 PostgreSQL 依賴和包大小都已量出，不再是 `UNKNOWN`。

## 9. 使用者決定紀錄（D121，2026-11-03）

使用者 2026-11-03 對本節 A～G 做了決定，記為 #93 的 **D121**。D 在 11-02 已定案，不變。下面每一項先寫定案，再保留原本的選項供追溯。

| 決定 | 定案 | 改到的正文 |
| --- | --- | --- |
| A | 選項 1：ITT 為主，Agent 實際決策的子集為次 | §3.1 |
| B | 選項 2：正式組沿用已核定上限；另加放寬逾時探索組，上限 PROPOSED 11000／33000 ms，待使用者核定 | §3.2、§3.11、§3.12、§8 |
| C | 先用預設題（s2／team-eval）當 pilot；正式題由 yyin 依「三種事件」各出一組；查詢用字列為主要變因（H1-QW）。「三種事件」指哪三種：`UNKNOWN`，待使用者確認 | §1.5、§2.2、§5.1、§5.4、§5.5、§5.10、§8；題集包 `docs/research/handoff/yyin_q1q3_wording_v1/` |
| D | 已定案（11-02），不變 | §7.2 |
| E | 選項 1：Qwen3 0.6B／1.7B／4B／8B，加 Llama 3.2 3B、Phi-4-mini 3.8B | §6.5、§8 |
| F | 選項 1：只能手動觸發的 `workflow_dispatch`，矩陣 ubuntu-latest、windows-latest；另評估 Colab | §7.9、§7.10、§7.12、§8 |
| G | 選項 1：只做 S1 降採樣（5→2.5 fps），不重新渲染 | §D.5、§D.7 |

### 決定 A：H1 的主要分析方式

**定案（D121-A）**：選項 1。

1. **（推薦）整組比較（ITT）為主，Agent 實際決策的子集為次。**優點：反映系統的真實表現，fallback 藏不住，也不會因為只挑 Agent 沒逾時的步驟而高估。缺點：逾時多時，Agent 的表現會被規則稀釋，較難得到 SUPPORTED。
2. **只看 Agent 實際做決定的步驟。**優點：比較接近模型本身的判斷力。缺點：有選擇偏差；fallback 比例高時樣本很少；容易被質疑是在挑資料。

### 決定 B：Agent 的逾時上限

**定案（D121-B）**：選項 2。正式組沿用已核定上限（2000／5000 ms、3 輪）；放寬組上限由 Claude 依實測 P99 提出（PROPOSED 11000／33000 ms），使用者核定前不開跑。細節見 §3.12。

1. **（推薦）沿用已核定的上限，不放寬，逾時照實計入。**優點：比的就是實際會用的系統，公平性最清楚。缺點：P1 那份就是 1 次呼叫、1 次逾時；正式 run 也大量逾時的話，H1 很可能判 INCONCLUSIVE。
2. **另加一組放寬逾時的 Agent。**優點：可以把「模型能力」和「在時間預算內的能力」分開回答。缺點：放寬組和 RULE 的時間預算不同，只能當探索性結果；執行時間加倍；新的上限要使用者核定。

### 決定 C：M3 的正式題目從哪裡來

**定案（D121-C）**：使用者原話「目前題目先用預設的，快速發包給 yyin 讓他做三種事件的問題集，我認為差別關鍵在找事件時的用字，如：經過某轉角、經過外面」。等於選項 1 的變形：s2／team-eval 當 pilot；正式題由 yyin 依三種事件各出一組，並把查詢用字列為主要變因（§5.10）。「三種事件」指哪三種：`UNKNOWN`。

1. **（推薦）s2／team-eval 只做 pilot，另請 yyin 出一份不重疊的正式題（`v1`、`evaluation_eligible=true`），經使用者核准。**優點：pilot 和正式題分開，符合 D105 B-8。缺點：要多一輪出題和標註，正式結果最快也在 demo 後一週以上。
2. **把 s2 升成 `evaluation_eligible=true`。**優點：最快。缺點：s2 本來是 pilot 設計；看過結果後再升級，就不是乾淨的事先登錄樣本。
3. **M3 只做 pilot。**優點：不增加工作。缺點：Q3／Q1 沒有正式結論。

### 決定 D：外包包裡的模型權重（**已定案**）

**定案**：選項 1。2026-11-02 協調者依 D104 的低階事項規則定案，照本企劃的推薦：包裡不放權重，由 `scripts/ensure_env.py` 依 digest 和 SHA-256 下載並驗證，不符就停下。下面保留原本的兩個選項，供追溯。

1. **（推薦）包裡不放權重；`ensure_env.py` 依 digest 和 SHA-256 引導外包者自行下載，驗不過就停下。**優點：包小，避開權重再散布的授權問題，hash 仍然可以核對。缺點：外包機要能上網；下載步驟在 Windows 上可能出錯。
2. **權重和 Ollama 模型檔離線放進包裡。**優點：外包機不需要上網，最容易重現。缺點：包會變大，大小 `UNKNOWN`，要先量；要先確認 RT-DETR 權重和 Qwen3 的授權允許轉交。

### 決定 E：M4 候選模型的範圍

**定案（D121-E）**：選項 1。

1. **（推薦）Qwen3 四個大小（0.6B／1.7B／4B／8B），加上 Llama 3.2 3B 和 Phi-4-mini 3.8B。**優點：同時看得到「同家族大小的影響」和「同大小不同家族的差異」，每個都有官方文件。缺點：執行時間大約是只跑現行模型的 6 倍；8B 可能因記憶體不足而依規則 4 排除。
2. **只跑 Qwen3 的四個大小。**優點：變因最少，最容易解釋。缺點：看不出差異是 Qwen 家族特有的，還是所有小模型都一樣。
3. **只跑現行的 `qwen3:1.7b-q4_K_M`，不做 M4。**優點：最省時間。缺點：如果 Agent 輸給 RULE，無法分辨是模型太小，還是方法本身的問題。

### 決定 F：要不要啟用 GitHub Actions 跨平台 smoke

**定案（D121-F）**：選項 1，矩陣只有 ubuntu-latest、windows-latest。使用者另問能不能用 Colab，評估見 §7.12。

1. **（推薦）授權新增一個只能手動觸發（`workflow_dispatch`）的 workflow，矩陣是 ubuntu-latest／windows-latest，必要時加 macos-14。**優點：public repo 免費；不會在每次 push 時自動執行；在交給外包機之前，先抓出路徑、編碼和安裝問題。缺點：沒有 GPU，只能驗環境和管線，不能產出任何數據；要多寫一個 workflow 並審查。
2. **授權在 PR 上自動觸發。**優點：每次改動都會自動檢查。缺點：會跑很多次，也會跑到與本實驗無關的 PR；第三方 PR 觸發時要另外考慮安全設定。
3. **不啟用，直接交給外包機。**優點：不需要授權 workflow。缺點：環境問題要等外包者回報才知道，來回時間長，Windows 尤其容易卡住。

### 決定 G：要不要做取樣率敏感度分析

**定案（D121-G）**：選項 1。

1. **（推薦）只做 S1 降採樣（5→2.5 fps），不重渲染。**優點：不需要渲染授權，磁碟成本小，能看出結果對 fps 的敏感程度。缺點：只能往低的方向看，無法回答「20 fps 會不會更好」；2.5 fps 要重算計分範圍，結果只能是探索性的。
2. **S1 之後，若敏感再做 S2（重渲染 20 fps 的單一事件片段，約 0.4～0.5 GiB）。**優點：直接回答高取樣率的影響。缺點：需要渲染授權和新的參數組核定；渲染期間佔用磁碟和機器。
3. **都不做，只把取樣率列為限制。**優點：零成本。缺點：無法說明 5 fps 對延遲和盲區判定的影響有多大。

## 10. 引用

| 文件 | ref | SHA-256 |
| --- | --- | --- |
| `docs/specs/DEVELOPMENT_RULES.md` | `origin/claude/rules-d108`＠`994b700` | `b01c60b7a8430de8ff45f6c8b911d5669dd2bdf5791dde9ad7487300387419a5` |
| `docs/agents/Q1Q5_DEMO_SCRIPT.md`（B-05a／B-05b） | #384＠`cf325aa9addeb801bb75da86a533bc42cb9b3f77` | `e1c543645ec8b659aa733ae1a9589893a84bc09d3f5a5a41c3f2a870293d30ea` |
| `src/amidst/evaluation/q5_switch_eval.py` | staging＠`434e579`／#305＠`f22e9da`（A15 例外） | `0fd1ef68c4c83443e8311723224b76f103c142dd018275e7c1596f917e85d9f2`／`97564e401cb7d70a7cc22113a008477b447974536ae207aabc230868e8b6d3dc` |
| `docs/evaluation/Q5_SWITCH_EVAL_V1.md` | staging＠`434e579` | `8457b2849b926b8534b1e43f71c98729f92ccd0320c2c73a89a78fe7ba6008cf` |
| `docs/evaluation/Q5_SWITCH_EVAL_V2_DESIGN.md` | #258＠`0b6e800` | `0a4e579b0664ab663e44809ebc0d2670b434c17161d7c24f237b1be4d051cc4c` |
| `src/amidst/evaluation/q3_parse_eval.py` | staging＠`434e579` | `4660edea0b204dfdead99cd1e2ebc5b8ce13ccffbd9d78c157ba285abda298c4` |
| `src/amidst/evaluation/q1_query_eval.py` | staging＠`434e579` | `eb403f968d3263cb5151219c9e46dddc8922d0f7ba9f21b7c07a276f44f973b9` |
| `src/amidst/q1q5/q3_rules.py` | staging＠`434e579` | `659a148224fc08b0a71a31c09a831a7a1ceb81004335a4c535a61ef02b6f5d5d` |
| `src/amidst/q1q5/q3_parse.py` | staging＠`434e579` | `ab3e80aba29f66c58654b52392c88c33266347c41d063817b6bc0eb2f42c228d` |
| `src/amidst/q1q5/q5_controller.py` | staging＠`434e579` | `1dcd0a53cf73bb2483c200be50f52f11ca35607ceaa5432c598343879c1719c7` |
| `configs/q1q5/linked_baseline_environment.json` | staging＠`434e579` | `2e75735c8d3b1e5c803f03e50b3eaffe8ade8166a949c9b96a731d85e72b592b` |
| `uv.lock` | staging＠`434e579` | `18c66a46f799efcfb4da36a15246245d2c959e42768a67b01f667eb73d284a17` |
| `docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md` | mainline＠`0d78599` | `015201556f550ab67dbbebead35916db426a3b6a05066ffc94c928696900ddbd` |
| `docs/evaluation/R004_COMPLEX_SCENARIO_CARDS_V2.md` | #261＠`b5302a0` | `02d98c06ac93b5b1eec019d65415eada7b751b4c6e76d3982a28aa36d9efd88b` |
| `docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json` | #354＠`48133c1a` | `ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb` |
| `configs/evaluation/q5_v2_decisions_u6_20261101.json` | FEAT-4 #396＠`1ff272f` | `0daa1508e2a67607cdc6bac54684b1b5449d3a651325e5af23dfe0afb1bd3b7e` |
| P1 包 `MANIFEST.json`（LOCAL） | — | `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7` |

決策：#93 的 D105-1～D105-4、D112-1、D113、D114-1～D114-4、D115；架構基準 #306（A15、P1）；FEAT-1 #376、FEAT-3 #370／#293、FEAT-4 #371、FEAT-6 #373、CQ-19 #300；驗收標準 AC1～AC8（`docs/agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md`＠mainline `0d78599`）。

### 外部來源（2026-11-02 查閱）

- Qwen3：[Qwen3 Technical Report, arXiv:2505.09388](https://arxiv.org/abs/2505.09388)；[Qwen3-1.7B 模型卡](https://huggingface.co/Qwen/Qwen3-1.7B)；[Ollama qwen3 tags](https://ollama.com/library/qwen3/tags)
- Llama 3.2：[官方 MODEL_CARD.md](https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/MODEL_CARD.md)；[Ollama llama3.2](https://ollama.com/library/llama3.2)
- Phi-4-mini：[模型卡](https://huggingface.co/microsoft/Phi-4-mini-instruct)；[Phi-4-Mini Technical Report, arXiv:2503.01743](https://arxiv.org/abs/2503.01743)；[Ollama phi4-mini](https://ollama.com/library/phi4-mini)
- Gemma 3（不列入）：[Gemma 3 Technical Report, arXiv:2503.19786](https://arxiv.org/abs/2503.19786)；[Ollama gemma3](https://ollama.com/library/gemma3)
- 工具呼叫評測：[Patil et al., The Berkeley Function Calling Leaderboard, ICML 2025](https://proceedings.mlr.press/v267/patil25a.html)
- Ollama 結構化輸出：[Structured outputs](https://ollama.com/blog/structured-outputs)
- Google Colab（2026-11-03 查閱）：[Colaboratory FAQ](https://research.google.com/colaboratory/faq.html)；[Past Runtime Versions](https://research.google.com/colaboratory/runtime-version-faq.html)；Ollama [Linux 安裝](https://docs.ollama.com/linux)
- 監視器 fps 調查（2026-11-03 查閱）：見 §D.7 表內各列
- GitHub Actions：[GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)；[Actions limits](https://docs.github.com/en/actions/reference/limits)；[Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
