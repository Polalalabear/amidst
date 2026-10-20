# Q1／Q2 第一版 Demo：Claude 審查後工作計畫修訂稿

日期：2026-10-20（Asia/Taipei）。狀態：**DISCUSSION DRAFT；D63 方向已決，修訂稿與提案參數仍待使用者核准，未開始產品實作。**

依據：使用者本次轉交的 Claude 審查回覆與更新 D63；遠端 [#65](https://github.com/Polalalabear/amidst/pull/65)、[#81](https://github.com/Polalalabear/amidst/pull/81)、[K7 #82](https://github.com/Polalalabear/amidst/pull/82) 的唯讀查核。**本次使用者訊息優先於遠端較早 D63(c)「只做語意解析」及「未授權下載」文字**；本輪未改寫遠端紀錄。

本稿取代前稿（LOCAL 未提交 `docs/engineering/SCENE_Q1_Q2_PLAN_20261020.md`）的待定方向；前稿原地改 r003、追蹤模型、PG 與 Codex 承包 UI 等提議不再有效。初次修訂只改文件，以及已特別授權的 RT-DETR 下載與既有 A／B1 小批推論接線測試。模型辨識、顏色輔助、候選關聯都不確認身分；`identity: UNCONFIRMED`，物理通行／碰撞仍為 `UNKNOWN`。

**D64 與發布補充：**本稿原提交 `60fa8ef` 的文件變更移植到獨立 `codex/q1q2-first-demo-plan`，base 為 `mainline/q1q5`，原 SHA 保留、不 rebase；不把 #80 產品程式帶進文件 PR。Q1–Q5 的 Agent 例外由 Claude 另開 DEVELOPMENT_RULES PR，**使用者核准合併後**才生效；Q4 第一版只用 RT-DETR＋HSV，VLM 第二版。修訂稿與 #86 核准前不建 r004、不渲染、不改產品程式。完整 [#86 的 19 題確認、差異與離線索引／MPS／取樣率評估](Q1_Q5_CONTRACT_REVIEW_20261020.md) 另列；本輪發布只做文件評估，不跑新推論。

## 1. Q1–Q5 目標與第一版定位

使用者首要目標原話：**「目前首要目標完成 Q1~Q5 問題，其餘先擺著」。**

| 問題 | 目標 | 第一版承接方式 |
| --- | --- | --- |
| Q1 | 幫我調某個條件的相機 | 查詢真實 RGB 的模型偵測索引，呈現相機／時間／代表畫面 |
| Q2 | 幫我找畫面中某個人 | 選起始人物框，按兩層圖與時間窗查合法候選，展示暫失、排除與切鏡 |
| Q3 | 盡可能理解使用者語意 | Qwen 將自然語言轉為結構化查詢；不支援或含糊條件明示，失敗退規則 |
| Q4 | 模型以自己的辨識判斷任意攝像頭 2D 畫面是否包含目標物 | RT-DETR 實際推論授權 run 中各鏡頭 RGB；按實際權重類別支援，不用物件清單或 GT 代答 |
| Q5 | 模型以現有資訊判斷目標物離鏡時是否切鏡 | 決定性候選生成／排序後，Agent（Qwen）依序取得 top-k 證據並判斷是否切鏡；輪數／時間超限由規則兜底 |

Q1／Q2 是整合 Q3–Q5 的第一版操作流程；「任意攝像頭」是同一授權 run／clock 的可用 RGB，不承諾所有物件類別或每格皆能檢出。固定機位切鏡以《惡靈古堡 1》為展示參考；盲區保留缺口，不畫出人物真實位置。

## 2. D63 決定、沿用與暫停

| 項目 | 本次有效方向 |
| --- | --- |
| 主線 | Q1／Q2 第一版，承接 Q1–Q5；其他工作暫緩 |
| 保留底座 | 沿用 #80（2a）的真實 RGB 後端與 `frontend/workbench-v2/` 外框，擴充既有流程，不另做啟動器、播放器或新入口 |
| 2D→3D 線 | #81 的 2b–2d、CS-C／CS-D、#84、#85 **暫停保留，不關 issue／PR、不刪分支或成果** |
| 場景 | 未來另存 `controlled_scene_v1_s001_r004.blend`；r003 原檔、D53／D59 的 source／run pins 不變 |
| 舊素材 | A／B1 保持 D42；紅衣／藍衣只用於 r004 新 run，不能把舊素材改標為新事件 |
| 模型 | RT-DETR 偵測＋人物框上半身最小 HSV 顏色統計；不導入 ByteTrack／OSNet／ReID |
| Agent | 兩層圖＋D28 決定候選與順序；Qwen 查證及判斷切鏡，不改排名；超限決定性兜底；D64 例外 PR 經使用者核准合併後才能在 Demo 啟用 |
| Storage | 第一版不用 PG；版本化 JSON 圖／相機、每 run JSONL 或 SQLite 偵測索引、單一 store 介面 |
| 分工 | Claude：workbench-v2 全部 UI、獨立契約草稿、browser acceptance；Codex：場景、感知、圖資料與後端 |

修訂稿與 #86 經使用者核准前：**不建 r004、不渲染、不開始查詢／Agent／圖／store／UI 產品實作。** D63(f) 特別授權的權重下載與舊 A／B1 小批接線已完成；#75 R1 及 #80 必要 merge 同步另有本次明確發布授權，不在本文件 PR 夾帶產品程式。這些授權不擴成新場景驗收、主線合併、GT 讀取或外部模型 API 授權。

## 3. 偵測、顏色與 Agent 邊界

### 3.1 RT-DETR 與最小 HSV

RT-DETR 輸出類別、人物框及分數；「紅衣」不是其原生類別。Q1 先用車輛作室外例子，室內類別與完整 class map 以**實際所下載權重、配套設定與輸出維度**為準，不能用通用 COCO 清單冒充另一份權重。樹木不以 `potted plant` 代替。

D63(d) 允許在 RT-DETR 人物框**上半身裁切**做最小 HSV 統計，輸出 `STRONG／WEAK／NONE／UNKNOWN`、有效像素量、方法版本、設定與方法 hash、來源 frame／bbox refs。裁切比例、HSV 色帶、飽和度／亮度與強弱門檻由新契約明列並核定；目前 `OPEN`，不冒稱已量測。背景混入、陰影、遠距小框或裁切無效時允許 `UNKNOWN`；`NONE` 與未計算分開。

顏色是查詢輔助訊號，不是 ReID 或身分置信度。第一版**不完成同色干擾**，不安排同色干擾人物，也不把同色多候選辨別列入 §11；多個條件相符框仍須保留歧義，不借 actor ID 解歧義。

### 3.2 Qwen 的解析、查證與決定性兜底

[Qwen2.5-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) 是文字模型。Q3 輸入自然語言、輸出受 schema 約束的查詢；Q5 只讀合法候選的結構化偵測／顏色／時間／可用性證據，輸出切鏡、繼續查證或維持暫失及引用理由。結果說明只能引用已提供證據，不直接以文字模型看 RGB。

1. Controller 先依核准兩層圖與 D28 固定完整候選序列。D28 排序鍵沿用 `relation_tier → overlap_area_m2_desc → camera_id`；Camera Graph 限定合法交接邊，不以人物偵測數、顏色或 LLM 改排名。關係／面積缺件保持 `UNKNOWN`，新契約須定義其穩定排序與截斷標記，不用事件答案補值。
2. Agent 僅能**依序**向序列的 top-k 取候選時窗證據；要求集合外相機、跳序、改時間窗或虛構 ref 一律拒絕。每次工具要求、重試與無效回覆都計入預算，拒絕也不能無限重問。
3. Qwen 可根據取得的偵測與顏色證據判斷是否切鏡；Controller 核對合法 refs、時間與最低證據 guard 後執行。合法候選只代表可查，沒有支持觀測不能切鏡。
4. 超過輪數／總時間上限、provider 不可用、逾時或格式錯誤時，決定性規則接手：依原候選順序，選候選時窗內有合格人物偵測且查詢顏色為 `STRONG` 的第一個候選；`WEAK／UNKNOWN` 不自動切換、保留候選；明確藍衣等條件不符者記排除理由。有歧義／無支持時維持搜尋／暫失，同一來源時間軸可回原鏡頭，不倒轉時鐘。強弱閾值未核定前不能宣告 guard 可用。
5. 回應記 `agent_used`、是否曾呼叫／嘗試 Agent、最終 `decision_source`、`fallback_used`／原因、輪詢次數、候選 refs／證據 refs、prompt 模板版本／hash、實際 prompt 與輸入／輸出 refs／hash、模型 tag／digest／版本及耗時。只用 LLM 解析時另標 `llm_parse_used`，不能因此把切鏡 `agent_used` 設 true；Agent 有有效查證後才兜底時保留 `agent_used: true` 與 fallback 狀態，不掩蓋歷程。精確欄位語意由 Claude 契約定稿。
6. UI 顯示解析所用方式、Agent／規則決策與**「規則回退」及原因**。模型說明不得修改控制結果。

top-k 是本次查證額度，不代表完整候選集合；未取證候選保留 `NOT_EVALUATED` 及完整性／截斷欄位。兜底可用的證據範圍、額外查取額度與耗時由新契約明列，不讓 Agent 逾時後變成無界掃描，也不能因 top-k 無支持就宣告所有鏡頭查無結果。

提案值（全部 **PROPOSED／待使用者核定**）：`top_k = 3`、每次暫失搜尋最多 **3 輪** Agent 工具／判斷往返、總預算 **5,000 ms**（含證據查取與模型等待，不能每次重試重置）、單次 provider timeout **2,000 ms**。Q3 解析另設 **2,000 ms** timeout，失敗走規則解析並明示；含糊且規則也不能解析時要求補充，不替使用者猜條件。超限可用原因碼提案 `ROUND_LIMIT／TIME_BUDGET／PROVIDER_UNAVAILABLE／INVALID_RESPONSE／ILLEGAL_CANDIDATE`；這些尚非既有 API。

### 3.3 同鏡頭最小連接器與「目標暫失」

同鏡頭內以決定性程式連接相鄰人物框，**不是模型或跨鏡頭身分追蹤器**。只在同一 source／run／clock／camera 的預期取樣 grid 上使用 RGB 偵測結果，不讀 actor、路線或 GT。

提案值（全部 **PROPOSED／待使用者核定**）：容許兩次匹配之間最多 **2 個缺格**；新框與最後匹配框的 **IoU ≥ 0.30** 且中心距離 **≤ 最後框對角線的 0.50 倍**才可連接。以穩定的一對一匹配及 bbox ref 作可重現處理；多個合格框無唯一匹配時回 `UNKNOWN`，不強配。中心點不能代替世界位置。

第一個缺格開始顯示「觀測缺失」；連續第 **3** 格無合格匹配時進入「目標暫失／搜尋」。在 5 fps 下 2 個缺格是 0.4 s，第 3 個是 0.6 s；其他 fps 必須在契約記錄對應時長，不沿用隱藏秒數。RGB 缺件、未推論、推論無人物與連接歧義分別記錄；缺格不插值、不填框、不跨 run／鏡頭接續 local ID，超過缺口後重見為新局部候選。

無偵測可能是漏檢、小框、遮擋或出視野，沒有觀測支持時不斷言原因；退出 ROI 只提供可查的出口候選。

## 4. 兩層圖與靜態標記依賴

### 4.1 Region Connectivity Graph

以 **O10 使用者核准後、用途與 hash 綁定的 `scene_static`（walkable／portals）**建立。O10 仍未核准；K7 #82 的建議不是批准，現有用途 `NOT_EVALUATED` 不升格。r004 有修改的幾何／相機需新 source hash 與受影響用途審查，不能從 r003 複製核准字樣。未涵蓋的室外新區域也須補靜態資料與核准。

`PORTAL_R102` 依 K7 #82 **只當拓撲連通，不能放進任何人物路線、可行路徑、路線距離或物理可通行證明**；圖可保留此拓撲邊並附用途限制，route builder 必須排除。R101 路線亦須等對應用途核准。walkable 的地板佔用區與人體中心可達區不同，不能因圖連通就宣告人體通過／無碰撞。

### 4.2 Camera Transition Graph 與出口 ROI

只用**靜態校正、D1 靜態可見範圍與不含人物的靜態畫面**建立／畫 ROI，記 source／calibration／static-image／ROI／graph 的版本與 hash、用途核准引用及作者。靜態畫面如需新 render，必須等後續渲染授權；本輪不產生。

**不得在事件 RGB 上標出口／入口 ROI，也不得讀路線、事件腳本、GT、renderer 逐幀人物 visibility／depth 來建立或調整圖。** 本輪的 A／B1 小批事件影格只供偵測接線，不供圖標註。圖定稿應先於事件證據檢查；若後續修圖，另版記理由並重新驗證，不能偷按答案改圖。

方向邊記 from／to camera、可用出口／入口／region refs、重疊或盲區關係；不能以相機距離最近就相連，畫面左側也不等於世界左側。出口不唯一時保留多個合法候選。靜態地板可見不等於人體全身可見，圖不存角色下一站或到達時間。

## 5. r004 具體修改提案（未建檔）

基底只讀保留 `data/pilot/controlled_scene_v1/assets/controlled_scene_v1_s001_r003.blend`，既有 source pin 為 `6e7de38dc069d330e0ffbb6c0051cdab304566fdbb7e3e8dfb429af863ae6d8e`。未來目標為同目錄 `controlled_scene_v1_s001_r004.blend`；本輪未開 Blender、未複製／另存資產。r004 hash／相機姿態為 `UNKNOWN`，核准後才產製；新 run、manifest、校正、graph／index hashes 獨立登錄。

以下相機 ID、HFOV、解析度與 K 均為**設計提案，不是已存在校正**。提議 preview 用 960×540、square pixels、pinhole、主點 `(cx,cy)=(480,270)`，`fx=fy=960/(2*tan(HFOV/2))`，`K=[[fx,0,480],[0,fy,270],[0,0,1]]`，以像素為單位；最終須用 Blender 實際設定／匯出重算並驗證座標與 image-center 慣例。此預算不自動把舊 5 fps／解析度變成新 run 定案值。

| 修改項目 | r004 預定修改／候選 ID | HFOV／焦距提案（px） | 後續 preview 與驗收 |
| --- | --- | --- | --- |
| 室外與車輛區 | 補一個室外車輛區及靜態通道；`CAM_EXT_CAR` 看停車，`CAM_EXT_CLEAR` 看無車區 | 各 70°；fx=fy≈685.51 | 至少一台有車、一台無車；以模型結果及 RGB 人工核對，不能從 scene 物件清單填索引 |
| 入口交接鏡頭 | `CAM_ENTRY` 覆蓋室外至室內門口，配對靜態入口／出口 ROI | 75°；fx=fy≈625.55 | 安裝點、視線無穿牆；與室外／走廊有可解釋的交接，出口不靠事件畫面標 |
| 走廊與轉角分岔候選 | 檢查／調整 r004 的 `CAM_W1`、`CAM_W2`；補 `CAM_BRANCH` 作另一合法候選，畫面放藍衣人物 | 各 75°；fx=fy≈625.55 | 真正轉角暫失、合法候選查取、藍衣被判條件不符；不能把鏡頭 ID 寫死為負例 |
| R101 門內 | 新 `CAM_R101_IN` 覆蓋 R101 門內落點與短走道；路線只經核准 `PORTAL_R101` | 70°；fx=fy≈685.51 | 由門外到門內交接；門內人物有足夠像素，不能借 `PORTAL_R102` 繞路 |
| 廣角鏡頭 | `CAM_WIDE` 在合理牆角／高度作 Wide pinhole；魚眼與 PTZ 延後 | 先比 90°（480.00）與 100°（402.77），K 主點同上 | **先小批 preview 量人物 bbox 像素高度分布**、邊緣／遠處辨識與出口可見性，再由使用者定案，不只標 Wide |
| 人物／事件 | 一個紅衣目標＋一個候選鏡頭中的藍衣人物；有身體材質及基本行走動畫；不做同色干擾 | 不適用 | 顏色方法只讀框上半身 RGB；人物 ID／路線腳本不進查詢與選鏡 |

兩個產製案例提議：A4「室外 → 入口 → 走廊直行」、B4「走廊 → 轉角暫失 → R101 門內」，與舊 A／B1 明確分開。兩者均不得經 `PORTAL_R102`，實際路線座標／長度／時窗待 O10 與 r004 靜態檢查後定案；私有產製腳本不能進 runtime 圖與排序。

後續廣角 preview 提案為每個 HFOV、每台相關鏡頭 5 張，記 min／P25／median／P75／max bbox 高度、檢出率的觀測範圍、推論耗時及邊緣案例；未檢出的格不能當高度 0 混入已檢出分布。人物像素高度的通過門檻 `OPEN`，待小批量測後核定。本輪既有 A／B1 接線測試不是這次 r004 preview。

## 6. 使用流程與牆鐘契約需求

Q1：`來源 RGB → RT-DETR → camera/time/class 索引 → Qwen／規則解析查詢 → workbench-v2 結果牆及播放`。顯示 camera、來源時間、實際偵測與 frame refs；沒有取樣／未推論的區段不可假定內容不變。至少展示有車鏡頭、無車鏡頭及一個**支援類別但索引範圍內查無結果**的查詢；不支援類別另回 unsupported，不能冒充零命中。

Q2：選起始觀測 → 同鏡頭連接與暫失 → 靜態出口／兩層圖產生 D28 有序候選 → Agent 依序取 top-k 時窗偵測／顏色 → 合法性 guard → 有支持才切鏡，或規則兜底／繼續暫失。藍衣排除須有實際偵測與輔助顏色證據；空畫面、未推論、條件不符、媒體錯誤分開。沒有後續觀測時可回原鏡頭，但時間不倒轉，最後觀測縮圖另標時間。

「13:00–13:30」是**新契約必備需求**：需日期、IANA 時區（示例 `Asia/Taipei`）、帶 offset 的牆鐘起點、`source_clock_id`、相對時間起點 `t0_us`、來源日期／時間的設定出處、有效／取樣範圍與映射版本／hash。映射提案為 `wall_time = wall_clock_origin + (t_us - t0_us)`；日期／時區／起點缺失時不能猜成今天下午。查詢區間用半開區間並明示未覆蓋部分，短片不能宣稱查完完整半小時。不按事件到達答案回推時鐘。

## 7. 獨立契約與 storage

由 **Claude 起草獨立 `Q1_Q2_FIRST_DEMO_V1`**（預定 `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md`；尚未建立），Codex 確認後，且使用者核准修訂稿／必要參數後，才開始並行實作。**不塞入 `OFFICE_CONTROLLED_SCENE_V1` v1.2**；既有 #75／#80 複審與新契約各自保留。

| 資料／I/O | 新契約需定義 |
| --- | --- |
| source／run／clock／model | 不可變 refs、pins、來源與取樣範圍、model／config／class-map／index hashes |
| 相機與兩層圖 | 版本化 JSON、K／pose／media bindings、O10 用途核准、拓撲限定邊、D1／ROI 靜態出處與 hash |
| 偵測索引 | 每 run 一份 JSONL 或 SQLite、frame／camera／time、class／bbox／score、HSV 輔助狀態、方法版本／hash、完整性與未推論範圍 |
| 同鏡頭連接 | 連接門檻／缺格、局部 ID、匹配歧義、暫失觸發；不跨鏡頭確認身分 |
| Agent I/O／兜底 | D28 有序候選、top-k／截斷、可取證據工具、guard、輪數與時間預算、prompt／model refs、agent_used／fallback 精確語意及原因 |
| 切鏡狀態 | 播放、缺觀測、暫失、搜尋、條件排除、有支持切鏡、無支持／錯誤；原鏡頭返回與共同時間軸 |
| 時間對應 | 日期／時區／來源時鐘起點、整數微秒／半開區間、映射 provenance、媒體與索引覆蓋範圍 |

第一版**不用 PG**。相機與兩層圖用版本化 JSON；偵測索引每 run 一份 JSONL（優先提案）或 SQLite，保存檔案 hash，放在單一 store 介面後面。媒體保持原檔引用，`.blend`／權重不進 DB 或 Git。配置以明確權重路徑及 hash 指向 repo 外既有位置，不搬移既有 Qwen 或其他權重。

新查詢路徑經薄 provider 直接呼叫現有 Ollama；**不經舊 Agent 初始化、不連 PG**。Q3 parser、Q5 受限輪詢 Controller／provider、store 可分離，但仍接 #80 與 workbench-v2 同一入口。既有 Agent／PG 與歷史資料保存原位；不用它們不等於可刪。外部付費 API 接線仍 `UNKNOWN／DEFERRED`，本輪不呼叫 Ollama 或外部模型 API。

## 8. 已授權 RT-DETR 下載與 A／B1 接線測試

候選採官方 PyTorch RT-DETR-R18 COCO 權重；來源為[官方 model zoo](https://github.com/lyuwenyu/RT-DETR/blob/df2a96c8c3a098567a1149bf0248da6efe6d495d/rtdetr_pytorch/README.md)，不是 Ultralytics 權重。授權下載依使用者 D63(f)，不再等待下載批准。

| 登錄項 | 本輪內容 |
| --- | --- |
| 檔名 | `rtdetr_r18vd_dec3_6x_coco_from_paddle.pth` |
| 來源 URL | [官方 release asset](https://github.com/lyuwenyu/storage/releases/download/v0.1/rtdetr_r18vd_dec3_6x_coco_from_paddle.pth) |
| 大小 | 官方 release API 與下載實測均為 **81,001,853 bytes** |
| 授權條款 | 官方 repo [Apache-2.0 LICENSE](https://github.com/lyuwenyu/RT-DETR/blob/df2a96c8c3a098567a1149bf0248da6efe6d495d/LICENSE)；release asset 未另列條款，不能以其他封裝授權代替 |
| 儲存 | LOCAL `/Users/polalabear/Models/amidst/rtdetr/`，repo 外、不進 Git；保留來源／授權／hash 收據 |
| SHA-256 | 實測 `3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0`；官方 API 的 `digest: null`，未有上游 digest 可比對 |
| 程式版本 | 官方 `df2a96c8c3a098567a1149bf0248da6efe6d495d`；僅 /private/tmp 接線 harness，不改產品程式 |

只讀 #80 登錄的舊 A／B1 safe manifest、`run_bindings`、RGB index 與所選 RGB，先核對 pins／逐張 hash；不開 private／evaluation、路線、事件腳本或 GT。每個 run 的每台已綁定相機 **5 張等距 sample index**，不挑人物答案；A 三台、B1 四台，合計 **35 張**。只取這批影格做 CPU／batch=1 接線，記模型 class map、實際檢出類別、人物框像素高度分布與冷啟／逐格推論時間，含零人物的組別；不把空分布填成 0。

既有環境沒有 Torch／torchvision；測試所需套件僅裝 `/private/tmp/amidst-q1q2-d63-20261020/deps`，重用既有 Python 3.12.12，不新建 venv、不修改共享環境或 `pyproject.toml`／`uv.lock`。原始影像不複製、不改 bytes；結果只證明舊素材上的接線及此取樣結果，**不等於 r004、車輛／紅藍衣、廣角、Q1–Q5 或新 Demo 功能通過**。

本輪**接線執行完成（exit 0）**：strict state dict 載入成功、權重分類 head 與實際輸出均為 80 維，配套 COCO class map 80 類；35／35 張 RGB hash 核對通過。A sample indices 為 `[0,12,24,36,49]`，B1 為 `[0,24,49,74,99]`。CPU arm64、Torch 2.6.0／torchvision 0.21.0、2 threads、batch=1、輸入 640×640（由原 960×540 resize）、未暖機。報表分數門檻 **0.30 僅為此次 smoke reporting 設定，非產品核准閾值**；沿官方 top-300 後處理，不另加 NMS。

實際 class map（依配套映射順序，並核對權重／輸出維度；不是全部在本批被檢出）：

`person, bicycle, car, motorcycle, airplane, bus, train, truck, boat, traffic light, fire hydrant, stop sign, parking meter, bench, bird, cat, dog, horse, sheep, cow, elephant, bear, zebra, giraffe, backpack, umbrella, handbag, tie, suitcase, frisbee, skis, snowboard, sports ball, kite, baseball bat, baseball glove, skateboard, surfboard, tennis racket, bottle, wine glass, cup, fork, knife, spoon, bowl, banana, apple, sandwich, orange, broccoli, carrot, hot dog, pizza, donut, cake, chair, couch, potted plant, bed, dining table, toilet, tv, laptop, mouse, remote, keyboard, cell phone, microwave, oven, toaster, sink, refrigerator, book, clock, vase, scissors, teddy bear, hair drier, toothbrush`。

本批實際輸出框數：`person:12`、`parking meter:8`、`toilet:6`、`sink:6`、`toothbrush:3`、`refrigerator:3`、`fire hydrant:1`。這些是模型輸出，**非人工確認物件真值**；沒有逐框人工精度驗收，不以非人物類別輸出證明場景真有該物件。未檢出的車輛不能用本批舊素材驗收 Q1 新車輛場景。

| 舊 run／鏡頭（各 5 張） | 有 person 框的格數 | person 框高度 min／P25／median／P75／max（px） | forward median（ms／格） |
| --- | ---: | --- | ---: |
| A／CAM_R102_CTRL | 0 | EMPTY，非 0 px | 1252.44 |
| A／CAM_W1 | 3 | 118.27／134.63／150.99／179.55／208.10 | 923.71 |
| A／CAM_W2 | 3 | 122.67／139.89／157.11／187.93／218.75 | 1223.54 |
| B1／CAM_N1 | 1 | 109.22／109.22／109.22／109.22／109.22 | 1017.17 |
| B1／CAM_R102_CTRL | 0 | EMPTY，非 0 px | 1119.96 |
| B1／CAM_W1 | 2 | 150.99／156.74／162.49／168.24／173.98 | 955.64 |
| B1／CAM_W2 | 3 | 122.67／156.02／189.38／204.06／218.75 | 1070.64 |

合計 12 個 person 框，高度 min／P25／median／P75／max = **109.22／122.67／154.05／194.06／218.75 px**（原圖座標未裁邊 bbox 的 y2−y1；逐框另記 clipped height）。未檢出格不納入高度分布；「有 person 框的格數」不是 recall，沒有真值分母。

模型建立／載入／deploy 為 **395.24 ms**（不含 Python／套件 import）；首格 forward **1318.06 ms**，全部 35 格 forward median **1108.41 ms**、P95 **1379.69 ms**、範圍 **585.14–1689.04 ms**。去掉首格後 34 格 median **1100.63 ms**。解碼／resize／forward／後處理合計 median **1136.85 ms**（不含 RGB 檔案讀取、hash 與程序啟動）。此 CPU 設定未達 5 fps 即時推論，後續索引預產製與播放的延遲須分開量測，不由本輪承諾即時效能。

可重跑命令（僅在上述 LOCAL 套件／官方來源／harness 仍存在時；harness 拒絕覆寫輸出，重跑須另定輸出位置）：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/amidst-q1q2-d63-20261020/deps uv --no-cache run --no-project --python /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/.venv/bin/python python /private/tmp/amidst-q1q2-d63-20261020/smoke_rtdetr.py
```

官方套件頂層初始化包含舊 training transforms（`torchvision.datapoints`）；harness 只用官方 inference leaf modules，明確建立 r18 backbone／encoder／decoder，`pretrained=False` 防止另下 backbone，`torch.load(weights_only=True)`，不修改官方來源或產品程式。實際套件裝載命令：`uv --no-cache pip install --python .local-worktrees/phase1-finalization/.venv/bin/python --target /private/tmp/amidst-q1q2-d63-20261020/deps torch==2.6.0 torchvision==0.21.0 scipy PyYAML pycocotools`；共 16 套件，473,944 KiB 配置用量，沒有新 venv。完整依賴及來源摘要見 LOCAL 收據。

| LOCAL artifact（不進 Git） | SHA-256 |
| --- | --- |
| `/private/tmp/amidst-q1q2-d63-20261020/summary.json` | `cbb95224bb1001e98517e77edb7fcd9c5e320b70c2f5218f1a8b2555569c8685` |
| `/private/tmp/amidst-q1q2-d63-20261020/detections.jsonl` | `390f685ac111d0cb79d425be5c5c311a311c11f6c6052ce7d1729942a457356c` |
| `/private/tmp/amidst-q1q2-d63-20261020/smoke_rtdetr.py` | `e68f1935c7b3d2b51951dceeff7d1a9ad68dd695b7fd218f1e29c2a49064d18e` |
| `/private/tmp/amidst-q1q2-d63-20261020/environment.json`（16 套件版本、upstream zip hash） | `b9b5fb2e14ca176552338d10b2a3f48f93ab094935220809d429b93f866f8f65` |
| `/Users/polalabear/Models/amidst/rtdetr/rtdetr_r18vd_dec3_6x_coco_from_paddle.pth.receipt.json` | `f704a2c71d5f09ce9e0e40905c910ba957bfa2bc84f8bb752260a80cd3a54c11` |

LOCAL /private/tmp 不承諾永久保存；本文件保留這次取樣、class map、量測與 hashes，不把本機 harness 當成已發布的推論模組。

## 9. Codex 範圍處置表與文件入口

依使用者要求加入「完全不能作為 Q1–Q5 參考、建議刪除」欄。**只能有證據時才填是；本輪只列不刪、不啟停服務、不搬資料或改 refs。** 不把「新熱路徑不用」等同「完全無參考價值」。Claude 另列其範圍，最後再合併名單；跨 owner／未盤點項保持 `UNKNOWN`。

下表路徑相對 canonical `/Users/polalabear/Developer/amidst`，外部路徑另寫。配置用量採本輪 `du -sk`（KiB），各樹可能硬連結／APFS 共享，**不可相加當回收量**。DB logical size 也不可與 cluster 相加。分支共用 Git objects，單分支大小 `N/A`。

| Codex 模組／分支／實體 | 路徑／ref、大小 | 第一版處置與理由 | 完全不能作為 Q1–Q5 參考、建議刪除 |
| --- | --- | --- | --- |
| 真實 RGB 2a／safe loader | `codex/controlled-scene-real-v2-2a` @ `2078183`；`codex/controlled-scene-real-v2-2a-review` @ `5d474c8`；大小 N/A | 沿用 #80，等 Claude 複審；後者 checkout 為 `/Users/polalabear/.codex/worktrees/mvp-backend-integration/amidst`，不改別人 checkout | 否，Q1／Q2 播放底座與複審證據 |
| controlled 骨架／screening | `codex/controlled-scene-backend` @ `8aff562`、`codex/controlled-scene-d47-screening` @ `5f7c906`；N/A | 保存 source／hash／error boundaries 的參考；2b–2d 與 #84／#85 依 D63 暫停 | 否，暫停保留有明確指示 |
| 舊 Office／感知／retrieval | `src/amidst/engineering/perception*.py`、`codex/c4a-*`、`codex/c4b-person-hypothesis`、`codex/c5-*`、`codex/c6-multicamera-feasibility`、`codex/c7-source-map`、`codex/k5-frame-wall-fixtures`、`codex/k8a-c4b-presync`、`codex/office-person-preset`；N/A | 保留 provenance、API／像素處理參考，不能把舊 floor／GT／研究指標帶入新路徑；實際重用需有界審查 | 否，仍有工程／歷史參考；不為第一版重做身高或精細軌跡 |
| integration／preset／handoff refs | `codex/mvp-backend-integration`、`codex/c3b-preset-isolation`、`codex/c3b-review-followup`、`codex/docs-agent-handoff`、`codex/office-demo-*`、`codex/rehearsal-*`；N/A | 只保留歷史，不全量 merge 或清理；本機 ref 存在已查，遠端可刪性未查 | UNKNOWN，不能由名稱判無參考 |
| 研究 refs | `codex/dataset-infrastructure`、`codex/deterministic-downstream-scenarios`、`codex/phase1-case23-formal`、`codex/phase1-preview-workspace`、`codex/simulation-engineering`、`phase1/*`、`phase2/*`；N/A | 第一版不重啟研究，但 formal／frozen／重現證據須保留 | 否，Q1–Q5 非依賴不解除研究保存義務 |
| finalization worktree | `.local-worktrees/phase1-finalization`，6,506,460 KiB | 仍含環境、Qwen、PG 與舊 Office consumers；只提出解除耦合，不刪整樹 | 否；未提交內容與必要依賴，見既有退役評估 |
| formal／clean worktrees | `.local-worktrees/phase1-case23-formal` 919,464 KiB；`.local-worktrees/phase1-case23-clean` 389,804 KiB | 保留 formal／clean release 與凍結重現；不改它們 | 否，歷史可重現性仍有用途 |
| Python／vendor 環境 | finalization `.venv` 793,456 KiB；`frontend/workbench/node_modules/three` 約 22.25 MiB（13:15 歷史值 REPORTED） | Python 本輪唯讀重用；新推論 deps 在 /private/tmp；舊 Office vendor consumer 未解除 | 否，仍有 consumer；環境搬移不可只改目錄 |
| Qwen 權重 | finalization `data/engineering/local_run/phase2_abc/ollama_models` 4,573,352 KiB | 沿用 provider 的既有位置，不搬移／刪除，薄 provider 接線另排 | 否，Q3／Q5 必要模型 |
| PG cluster／舊 Agent | finalization `data/engineering/local_run/phase2_abc/postgres` 324,968 KiB；`src/amidst/local_agent/` | 新路徑不初始化／連 PG；保留舊資料與研究 consumer，非本輪重構 | 否，不能由新版不用 PG 推論全部可刪 |
| PG restore 測試 DB | 同 cluster，12 個確切 DB 名稱與 bytes 見下表 | 僅列後續清理候選；row／備份／consumer 等價性未查 | UNKNOWN；用途疑似測試，尚不能斷言完全無參考，待使用者與 owner 確認 |
| PG 測試 schemas | `amidst_abc` 內 `schema_name LIKE '%test%'` 本輪 90 個；逐 schema bytes UNKNOWN | 先保留；歷史「96 測試 schemas」與本輪 filter 範圍不同，不冒稱 6 個已刪 | UNKNOWN，需精確 schema／owner 清單才能建議刪除 |
| A／B1 舊 RGB | `data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-a-5fps-v1-r001` 63,976 KiB；B1 sibling 170,156 KiB | #80 現行 pinned 播放輸入與本輪接線測試資料，保持 D42 | 否，不能刪／改 pin |
| 歷史舊資料 | `data/engineering/` 中 E0／E1、accuracy-v2、local_run、凍結 evidence；逐項大小 UNKNOWN | 13:15 退役評估（LOCAL 未提交 `docs/history/WORKTREE_RETIREMENT_ASSESSMENT_20261020.md`）列為有依賴／未知；不擴成全 repo 遞迴盤點 | UNKNOWN，不能當測試垃圾；後續逐項確認 |
| 舊清理收據 | `docs/history/storage_cleanup_20261014/` 13,580 KiB | 原位保留；不能再以已刪 locator 計回收量 | 否，清理與復原邊界證據 |

PG restore DB logical sizes（本輪唯讀 metadata；位於上述 cluster，共用實體檔，以下不是資料夾刪除指令）：

| DB 名稱 | bytes |
| --- | ---: |
| `amidst_restore_01cbc6f797f348b3` | 8,959,679 |
| `amidst_restore_02595d7bd4f647a0` | 8,959,679 |
| `amidst_restore_0a4a8923213847d6` | 8,959,679 |
| `amidst_restore_3dd3fd0973eb4ae5` | 8,959,679 |
| `amidst_restore_511e5827c8ac47c3` | 8,959,679 |
| `amidst_restore_7b7d5c37a53347df` | 8,959,679 |
| `amidst_restore_8892295cda634566` | 8,959,679 |
| `amidst_restore_cede76b7d1744250` | 8,959,679 |
| `amidst_restore_f52b746498384b72` | 8,787,647 |
| `amidst_restore_integration_244b5e5642524759` | 16,537,279 |
| `amidst_restore_integration_baf7cbd755c94baf` | 16,537,279 |
| `amidst_restore_integration_f12de37426304a3a` | 16,537,279 |

本輪可斷言「完全不能作為 Q1–Q5 參考、建議刪除」的實體：**NONE**。這是查證結論，不是刪除清單已完備。未盤點範圍列 UNKNOWN，之後合併 Claude 清單，使用者確認精確目標、owner、consumer、dirty／refs／保存狀態後才可刪。

文件入口依 AGENTS.md 使用 **[docs/DEVELOPMENT_RULES.md](../DEVELOPMENT_RULES.md)**；本輪確認它是指向 `specs/DEVELOPMENT_RULES.md` 的 symlink，兩者為同一份現行規則，不能誤稱 specs 版過期。現行本地規則仍有舊 workbench／Agent 邊界文字，D35 與本次 D63 的特定指示優先；後續由文件 owner 按實際新契約更新，**本輪不修改規則或 AGENTS.md**。

定案後才安排更新：計畫／MVP／TASKS、工作台 handoff／重現說明、單一 `docs/README.md` 索引、獨立 Q1_Q2 契約與必要架構差異。前稿、退役評估與 2a 紀錄保留歷史日期，不把舊 PASS 改成新功能驗收。不建 worktree、不切他人 checkout、不自行 push／PR／issue／merge／關閉或刪除分支。

## 10. 分工與實作順序（尚未開工）

責任重心估計改為 **Codex 約 60–65%、Claude 約 35–40%**，僅供協作規劃，非工期／成本量測。每個 file set 一個 owner，契約先行，不讓 Codex 同時承接 UI。

| 階段 | Codex | Claude | 門檻／交付 |
| --- | --- | --- | --- |
| 現在 | 本稿修訂、權重登錄、舊 A／B1 小批接線與結果記錄 | #75／#80 複審 | 不啟動其他產品程式 |
| 定案／契約 | 確認 r004 表、資源、backend I/O／provider／store；確認 Claude 契約 | 起草 `Q1_Q2_FIRST_DEMO_V1`、UI／狀態與 focused acceptance 計畫 | 使用者核准修訂稿／提案參數，Codex 確認契約；O10 及資產／渲染授權另守門 |
| 場景與資料 | r004、RT-DETR／HSV、偵測索引、靜態兩層圖資料與 hashes | 獨立檢查圖依據、preview 與資料契約 | 先靜態圖／ROI，後事件；廣角先小批量測再定案 |
| Q1 | 索引查詢、store、自然語言薄 provider、#80 adapter | `frontend/workbench-v2/` 結果牆／播放／查無結果 | 不另做入口；舊 `frontend/workbench/` 不動（D35） |
| Q2／Q5 | 連接器、查找、Agent 合法 top-k 輪詢與決定性兜底、切鏡後端 | workbench-v2 切鏡播放、時間軸、暫失／排除／規則回退 UI | 共同 run／clock 與 evidence refs，身分不升格 |
| 收斂 | focused backend checks、延遲與 provenance／hash 收據 | browser acceptance、獨立驗證、Demo 操作與說明 | 各自結果記錄；未經 checkpoint 核准不合併 |

## 11. 第一版完成條件與暫緩

- Q1 有至少一台有車與一台無車的鏡頭，展示有支持的查詢及一個支援類別的零命中查詢；結果附模型、frame／camera／時間證據與取樣範圍。
- Q3 可把示例自然語言轉為有效結構查詢，解析失敗明示規則回退或需補充；Q4 為各授權鏡頭實際 RGB 的 RT-DETR 判斷，不用 Blender 清單／GT 代答。
- Q2／Q5 的兩個 r004 案例展示觀測、同鏡頭暫失、D28＋兩層圖合法候選、Agent 依序取證、藍衣條件不符排除、有支持切鏡、無支持／回原鏡頭，以及超限規則兜底；排序不由 Agent 改寫。
- Agent／LLM parser／fallback 的標示、原因、prompt 與模型版本可查；非法候選會被拒絕且仍計預算，不無限輪詢。
- 圖、ROI、O10 用途與來源 hash 可核對，`PORTAL_R102` 不在任何路線；衣服、廣角及遠距小框有實測，不以渲染完成代替辨識通過。
- 舊 r003、A／B1、D53／D59 pins 保持；新 run 與牆鐘映射明確。workbench-v2 沿用 #80；舊 workbench 保留。延遲報實測，性能通過門檻待核定。

暫緩：**同色干擾完成／驗收條件**、2D→3D 的 2b–2d／CS-C／CS-D／#84／#85、GT 建立／讀取、tracking／ReID 模型、身高／腳點／精細 3D 軌跡、物理通行認證、魚眼／PTZ、大規模長影片、研究級評估、PG 重構／整批歷史搬遷清理。暫停項保留，不關、不刪。

## 12. 待核定與後續交接

1. 使用者核定 §3.2 的 top-k、Agent 輪數／總時間／provider timeout 與 §3.3 的缺格／IoU／中心距離提案；未核定值維持 PROPOSED。
2. Claude 起草獨立契約並補定 HSV 參數、未知 rank 行為、Agent I/O／錯誤碼及時間映射；Codex 確認後才並行。
3. O10 的核准與 r004 變更作用範圍仍是靜態圖依賴，K7 報告不代替使用者批准；r004／preview／渲染仍待另行明確授權。
4. r004 鏡頭實際 pose／內參及人物像素高度門檻待小批 preview 後定案；本輪 A／B1 接線不補此證據。
5. Codex／Claude 處置清單合併後交使用者確認；本輪無刪除、搬遷或服務切換。

## 13. 實際產出 / Actual output

以下保留 `60fa8ef` 初次修訂／下載／smoke 階段的歷史結果；發布階段的 D64、#86 確認與新增評估，見同目錄 `Q1_Q5_CONTRACT_REVIEW_20261020.md` §6 及 PR 的實際產出紀錄。初次階段的「未 push／發文」不是目前發布狀態。

- Model / effort: Codex（GPT-6）；精確模型變體／effort 未由 session 提供，UNKNOWN。
- PR / commits: 本輪 local commit SHA 於提交後回報；未 push／建 PR／發 GitHub 留言／merge。既有 #75／#80 保持 Claude 複審。
- Files changed: 僅本討論稿；本輪測試收據／harness 另於 LOCAL /private/tmp，權重位於 repo 外，不 stage。
- Commands run and results: `git status --short`、`git branch --show-current`、`git worktree list`、`git for-each-ref` 唯讀；`gh issue view 65 --repo Polalalabear/amidst --json number,title,state,body,comments`（81、82 各同樣查詢）；`du -sk` 指定依賴；PG 唯讀 SQL 見下方。官方 release metadata、下載／SHA-256、§8 精確接線命令 → exit 0、35 張／7 組、35／35 RGB hash PASS；相對連結 3／3、尾空白 0、HFOV 算術、`git diff --check` 與 `git diff --cached --check` 通過。文件核對命令：`uv --no-cache run --no-project --python /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/.venv/bin/python python /private/tmp/amidst-q1q2-d63-20261020/check_document.py` → PASS。未執行程式 unit tests／全 suite。
- Artifacts: 本文件；LOCAL repo 外權重、收據、35 張接線輸出／harness 的完整 paths／SHA-256 見 §8。文件本身 hash 於對話回報，不自我引用；權重與 media 沒有進 Git。
- Verified: D63 最新指示已逐項落稿；規則 symlink、D28 排序、#82 的 R102 限定、指定依賴大小與 PG metadata 已讀；實際權重 size／hash、80 類設定與分類 head／輸出維度、strict state load、35 張既有 RGB 接線／高度／耗時；r003 source hash 仍為原 pin。只確認此範圍。
- Not verified: r004／新事件／紅藍衣／廣角／全 Demo、HSV 品質、Agent／Ollama 互動、provider／store／新 API、browser acceptance、O10 批准、全量影像 hash、GT／研究指標、完整刪除安全性及可回收量；未跑產品 unit tests／全 suite。
- Deviations, UNKNOWN items and follow-ups: 遠端 D63(c)／下載權限仍是舊文字，本次訊息優先且本輪不發文更改；提案門檻、獨立契約、O10 與新場景產製仍待定。uv sandbox 發生 cache 權限錯誤及 macOS `system-configuration` panic，改以 `--no-cache` 在允許的執行環境完成，沒有改權限／共享環境。PG 預設 OS role 不存在，改用現有 settings 的 `amidst_local` 完成唯讀 metadata 查詢。前稿／退役評估與 `docs/README.md` 仍為原有未提交內容，連結只查本機，未隨此 commit 發布。保留原分支與所有既有修改／資產。

本輪 PG 實際命令（只讀 metadata，與新查詢路徑無關）：

```sh
psql -X -h /private/tmp/amidst-pg-abc -p 55432 -U amidst_local -d amidst_abc -At -c "BEGIN READ ONLY; SELECT datname, pg_database_size(datname) FROM pg_database WHERE datname LIKE '%restore%' OR datname LIKE '%test%' ORDER BY datname; SELECT 'test_schemas', count(*) FROM information_schema.schemata WHERE schema_name LIKE '%test%'; COMMIT;"
```
