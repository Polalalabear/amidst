# r004 場景修改與小批 preview 提案

日期：2026-10-20（Asia/Taipei）。任務 [QT-04／#97](https://github.com/Polalalabear/amidst/issues/97)。**D68 已核定六項設計；本輪只修文件，不執行建檔、渲染或用途升權。**

## 1. 固定依據與本次邊界

- 計畫：[#92 @ 86877b2](https://github.com/Polalalabear/amidst/blob/86877b20d1a6c5fd54a59ff6903efe9d175d8de0/docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md) §5；[離線索引預算](https://github.com/Polalalabear/amidst/blob/86877b20d1a6c5fd54a59ff6903efe9d175d8de0/docs/engineering/Q1_Q5_CONTRACT_REVIEW_20261020.md) §4。
- 契約：[#86 @ 3873ff2](https://github.com/Polalalabear/amidst/blob/3873ff2dbe97c88b3de2cfcdfc7df393fdff23d2/docs/contracts/Q1_Q2_FIRST_DEMO_V1.md)，bytes SHA-256 `924c4365ab3b3169eb9192296a26eede9d558d885410e7e80197d00a77978078`。本輪對 `1d1e061` 的[異議](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6291180958)已由新版修正，Codex [確認新版](https://github.com/Polalalabear/amidst/pull/86#issuecomment-6291339657)。D65 已核准 #86 @ `3873ff2` 與 #92 @ `86877b2`，merge commit 分別為 `f62ab72`、`b1a1b32`（G1 成立）。
- 保留 r003：`data/pilot/controlled_scene_v1/assets/controlled_scene_v1_s001_r003.blend`，既有計畫登錄 pin `6e7de38dc069d330e0ffbb6c0051cdab304566fdbb7e3e8dfb429af863ae6d8e`。本輪未讀／重算 `.blend`，此處是引用登錄值。r003、A／B1 與 D53／D59 pins 不變。
- 未來目標：同目錄另存 `controlled_scene_v1_s001_r004.blend`；本輪未建立。r004 source hash、相機 pose、實際 K、場景尺寸、路線座標與新 run IDs 均為 `UNKNOWN`。
- 本輪不開 Blender、不複製資產、不渲染、不推論、不讀 GT／人工標註、不接外部模型 API；只交付本文件。不合併 #75、#80 或其他 PR。

## 1.1 D70／D71 的後續授權與固定邊界（2026-10-21）

[D70](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6307788539) 已授權 #113 的 45 格廣角 preview、#115 A4／B4（4＋5 台、各 30 s、5 fps、960×540）與 #118 正式索引。開始時的 12 GiB 門檻由使用者判斷；每次產製前後記 `df -k`，輸出集中 `~/amidst-artifacts/<task>/`，available 低於 8 GiB 立刻停止。只清可重新產生的 uv／pip／Python／pytest／node 快取，不動權重、venv、PG、資料。下文 2026-10-20 的「未授權／12 GiB」只保留為歷史紀錄，執行以本節的新決定為準，不能混用日期。

[D71](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6308081801) 補充：r004 的牆壁與地板要有非全白的中性色差，避開紅／藍色相；只改新 r004，不改 r003 或 A／B1。環境顏色不是人物標籤，不把材質 ID、人物設定或劇本送進索引／HSV／圖／參數／prompt。每台鏡頭必須有出口區域，缺漏 fail closed；不以全畫面邊緣替代。兜底 budget 保留核定數值，但不作截止，僅 stats 觀察。

X1／X2 已在 `0e02f5ee32d72a7da9d3071700020726857f768b` 修正；本版重新核對且保留完整 graph 候選／未取證與選鏡偏差說明。G3 已由 #125 merge `f915fb0` 成立。G4 仍未核准；#116 可先標 PROPOSED／DRAFT 工程圖，不能升權。D68「事件渲染前固定圖／ROI 並經獨立檢查」沒有被本節取消，#117／G4 與 HFOV 最終定案各自保留。

## 2. 可單獨核准的修改表

全部相機 ID、HFOV 與場景修改是候選設計。最終安裝點、鏡頭方向、near／far、region／portal 引用，須等授權後由靜態場景及校正核對；不能用名稱推定已存在或已可通行。

| 項目 | 提案修改 | HFOV 提案 | 後續應留下的證據 |
| --- | --- | ---: | --- |
| 室外車輛區 | 新 `CAM_EXT_CAR` 與 `CAM_EXT_CLEAR`，分別覆蓋有車與無車的室外區域 | 各 70° | 新 source／calibration／static frame refs；車輛搜尋結果來自實際模型 RGB 偵測，不從 Blender 物件清單填答案 |
| 室外至室內入口 | 新 `CAM_ENTRY`；配置可解釋的入口交接及靜態出口／入口 ROI | 75° | 校正、靜態可見範圍與 ROI hashes；鏡頭不能裝在牆內或藉穿牆畫面成立 |
| 走廊／轉角 | 在 r004 檢查並調整 `CAM_W1`、`CAM_W2`；新 `CAM_BRANCH` 作另一合法候選 | 各 75° | 轉角盲區與分岔的靜態依據；不能用實際目標下一站建 graph 或改 D28 排名 |
| R101 門內 | 新 `CAM_R101_IN` 覆蓋門內落點與短走道 | 70° | 對應核准的 R101 portal／walk 用途、門內像素尺度與靜態校正；O10 未核准則維持 DRAFT |
| 廣角 | 新 `CAM_WIDE`，合理牆角／高度的 pinhole；比較兩個 HFOV | **先測 90°，再比較 100°** | 相同安裝點的靜態可見範圍、人物框高度與邊緣分布；最終 HFOV 待小批 preview 後核定 |
| 場景環境材質 | 新 r004 的牆壁／地板使用有明暗差的中性色，避免全白與紅／藍色相（D71） | 不適用 | 新 source／靜態畫面 hash；不能把材質或人物設定用作推論答案 |
| 人物／動畫 | r004 新事件有一個紅衣目標與一個藍衣候選人物，身體材質與基本行走動畫 | 不適用 | 私有產製設定獨立保存；偵測、顏色、圖、索引、查詢與 prompt 不讀人物 ID／材質 ID／腳本／路線 |

第一版不做同色干擾、魚眼、PTZ、ReID、身分確認或物理通行認證。藍衣所在鏡頭不是硬編碼負例；是否排除必須由該窗實際偵測／顏色證據決定。

## 3. HFOV 與 K 的算術提案

建議 preview 解析度 **960×540**、square pixels、pinhole、無 lens shift、水平視角控制；這不是已匯出的相機校正。採 `TOP_LEFT_CONTINUOUS` 像素慣例，提案主點 `(cx, cy) = (480, 270)`：

```text
fx = fy = width / (2 * tan(HFOV / 2))
K = [[fx, 0, 480], [0, fy, 270], [0, 0, 1]]
```

| HFOV | fx＝fy（px，四捨五入至 2 位） |
| --- | ---: |
| 70° | 685.51 |
| 75° | 625.55 |
| 90° | 480.00 |
| 100° | 402.77 |

此推導只在上述假設成立時有效。授權後須核對 Blender 的 sensor fit、pixel aspect、render percentage、shift 與匯出慣例，重算 K／pose、image-center、source／calibration hashes。不得將本表直接貼成已驗證 `cameras.json`；World／camera 座標沿用既有契約。

## 4. A4／B4 事件與鏡頭範圍

D68 已核定下列 **4＋5 個 camera-run**、各 30 s 作容量與索引預算；共同的 `CAM_W1` 在兩個 run 分別計算。聯集 8 台。實際 render scope 與 `run_bindings` 另待授權後固定。

| 事件 | 產製案例提案 | 預算鏡頭 |
| --- | --- | --- |
| A4 | 室外 → 入口 → 走廊直行 | `CAM_EXT_CAR`、`CAM_EXT_CLEAR`、`CAM_ENTRY`、`CAM_W1` |
| B4 | 走廊 → 轉角暫失 → R101 門內 | `CAM_W1`、`CAM_W2`、`CAM_BRANCH`、`CAM_R101_IN`、`CAM_WIDE` |

- 每個事件各一個獨立 run／clock；鏡頭在該 run 內同步。展示牆鐘重疊不代表兩個事件可跨 run 串接人物。
- 上表只供產製排程與預算，**不得轉成 runtime 候選圖、固定切鏡表、prompt 或評分答案**。沒有任何到達時間或人物路線座標。runtime 候選使用完整 camera graph；沒有影像的合法候選標 `NOT_EVALUATED`／未取證。展示不得把「只有這幾台有證據」當成推論結果。
- `PORTAL_R102` 維持 `TOPOLOGICAL_ONLY`，A4／B4 不經過它；不進 route、路徑長度或可切換候選。r004 重驗不自動解除此限制；R101 的用途核准亦尚未成立。
- 完整 camera catalog 與每個 run 的 media／inference coverage 要分開列。所有實際綁定鏡頭都必須索引，或明示 `NOT_INFERRED` 等缺口；沒有 media binding 的鏡頭明示不可取證，不能默默刪候選或宣稱全場完整。
- 若靜態圖顯示這個 scope 不足以查核必要候選，先擴大提案、重新計算容量並取得授權，不在展示中偷用未登錄畫面。
- 來源時長 D68 已核定 **各 30 s**；若靜態檢查後無法容納所需事件與盲區，改提各 60 s。實際路線長度／時窗待 O10 與靜態檢查，不先用本時長推人物速度。

## 5. 取樣、離線索引與容量選項

**D68 已核定來源 5 fps／索引 stride 1；D65 的 §11 值為第一版初值。** stride 2（2.5 fps）與 stride 5（1 fps）只作預算選項；索引率不改來源播放率。較稀索引可能漏掉短暫可見／出口訊號。依 `3873ff2`，`link_max_gap_us` 必須為索引間隔的正整數倍；D65 第一版初值 `link_max_gap_us = 600000 us`（5 fps／格距 200,000 us） 不相容於 400000／1000000 us，會回 `PARAMETER_GRID_MISMATCH`，需另提及核定新參數組。

來源暫以 5 fps、camera-run 從 sample 0 起、區間半開估算：

```text
N_source = sum(duration_s * 5 for each camera-run)
N_index = sum(ceil(source_frames / stride_samples) for each camera-run)
T_forward_minutes ≈ N_index * 1.108406209 / 60
T_total = T_import/load + T_read/hash + T_forward + T_HSV + T_store + T_retry
```

`1.108406209 s/frame` 是 #92 引用的舊 A／B1 35 格 CPU forward median，**不是本輪量測、完整 index throughput 或上界**。不含 RGB 讀取／hash、HSV、寫檔、載入、重試及同機負載。

| camera-run／每事件來源時長 | source frames | 5 fps／stride 1：N、forward min | 2.5 fps／stride 2：N、forward min | 1 fps／stride 5：N、forward min |
| --- | ---: | --- | --- | --- |
| **4＋5 台／各 30 s（建議先評估）** | 1,350 | 1,350；24.94 | 675；12.47 | 270；4.99 |
| 4＋5 台／各 60 s | 2,700 | 2,700；49.88 | 1,350；24.94 | 540；9.98 |
| 每事件全部 8 台（16 個 camera-run）／各 30 s | 2,400 | 2,400；44.34 | 1,200；22.17 | 480；8.87 |
| 每事件全部 8 台（16 個 camera-run）／各 60 s | 4,800 | 4,800；88.67 | 2,400；44.34 | 960；17.73 |

儲存沿用 #92 的舊 A 目錄粗估 `63976 KiB / 150 frames`，不是新場景上界：1,350 格約 **0.55 GiB**；2,700 格約 **1.10 GiB**；2,400／4,800 格約 **0.98／1.95 GiB**。此處只估 RGB，以來源格數計，降低索引率不會減少來源 RGB；不含 `.blend`、新靜態畫面、preview、模型、索引、暫存、RAM／swap。新室外／材質／廣角壓縮率未知，必須在授權 preview 後重估。

不在本輪跑 MPS benchmark、不下載權重或產新索引。Q1–Q5 查詢只讀已物化索引，不補推論。舊 A／B1 可於對應任務放行後作接線；白色人形不能用於核定 r004 紅／藍衣 HSV 品質或門檻。

## 6. 小批 preview 與通過條件草案

以下是 **未執行的產製／量測計畫**；其本身不授權渲染或推論。

1. G1 已成立；D67 僅授權 #132 經 Claude 複核通過並合併後建 r004 與靜態校正匯出。任何靜態畫面／preview 仍屬渲染，須 G5 渲染部分另授權且符合 D41。放行後固定 source 與相機候選。先用不含人物的靜態校正／可見範圍／畫面產生圖與出口 ROI；用途未核准只標 DRAFT。
2. D68 已核定契約 §14 的較早凍結選項：**事件渲染之前**，由 Claude 獨立檢查並固定圖／ROI hashes。不能看事件 RGB、人物路線或偵測結果再畫圖。相機或幾何變動要重出版本／檢查。
3. 人物 preview 與正式 Demo run 分開。建議八台各取 5 格（40 格），WIDE 的第二個 HFOV 另加 5 格，共 45 格；粗估 RGB 約 18.7 MiB、CPU forward 約 0.83 min（沿用 §5 舊係數，不含 I/O 等）；r004 `.blend` 大小 `UNKNOWN`。取樣規則在看結果前記錄，不挑「有檢出」的格。固定同一安裝點比較 HFOV，版本／source／run／clock／取樣與方法均留 hash。
4. 依鏡頭與 HFOV 報告輸入格數、人物偵測非空格比例、detected bbox 高度的 min／P25／median／P75／max、邊緣／遠距／截斷例、有效上半身像素量及逐格耗時。**未檢出格不填成高度 0**；零檢出組的高度統計為 null。沒有人工標註或 GT 分母，不把「非空格比例」稱 recall／accuracy。
5. HSV 參數由另項任務 #114 提案、Claude 檢查、使用者核定。只用已授權 preview RGB，不能用 actor／材質／路線答案；方法凍結後再產正式 Demo 索引。不讀人工標註。人工看 RGB 只能當驗收觀察，不能回填索引、參數或評估分母。

| 檢查 | 通過條件草案／狀態 |
| --- | --- |
| Provenance／完整性 | source、run、clock、calibration、static frame、RGB、graph／ROI／index hashes 可追溯；錯 pin／hash fail closed，不以 fixture 代替 |
| 靜態鏡頭／拓撲 | 安裝位置、視線、入口／出口對應有靜態依據；R102 排除；r004 受影響用途經獨立檢查與使用者核准，否則 DRAFT／UNKNOWN |
| 人物尺度／HFOV | 完成上述分組量測；像素高度／截斷／檢出品質的數值門檻 **OPEN**，preview 後核定；本輪不宣告 PASS |
| Q1 功能 | 授權正式 run 後展示有支持的車輛搜尋、已推論格無命中、不支援類別及 coverage 缺口；不從場景清單代答 |
| Q2／Q4／Q5 功能 | 有觀測支持才切換；暫失保留 GAP；藍衣排除須有顏色證據；缺格／未取證／未知分開；來源時鐘不倒退，身分 UNCONFIRMED |
| 模式／驗收 | 預設 RULE_ONLY；AGENT_SEQUENTIAL 在 #125 核准合併後才可於 Demo 啟用；產品測試、Claude browser acceptance 與使用者展示判定另有任務，非本提案 PASS |

## 7. D68 核定結果與仍待核定項目

D68 六項均採建議：八台鏡頭用途、4＋5 台各 30 s（1,350 格，約 0.55 GiB，不含 `.blend`）、5 fps／stride 1、90° 與 100° 都測後再定、事件渲染前凍結圖／ROI、960×540。設計核定不等於渲染授權或 G4 用途核准。下表保留替代方案的代價；preview 格數與品質門檻仍是提案。

| 決定 | 建議先選 | 其他選項與代價 |
| --- | --- | --- |
| 基本場景／鏡頭修改 | 核定 §2 的八台候選用途，pose／K 留待靜態核對 | 調整候選清單時，同步重算 graph、scope 與預算 |
| 解析度／鏡頭模型 | 960×540、square pixel pinhole | 更高解析度另估空間／推論；魚眼／PTZ 暫緩 |
| WIDE | 先比較 90° 與 100°，依量測定案 | 直接固定一個角度會少掉像素尺度比較證據 |
| camera-run 範圍／時長 | 4＋5 台、各 30 s 作初始預算，靜態檢查不足時重新提案 | 4＋5 台依已知路線挑選，有影像鏡頭與答案路徑高度重疊，可能讓 Q2／Q4 看起來較容易；各 60 s 或全部八台提高 coverage，影格與空間依 §5 增加 |
| 來源與索引密度 | 先評估來源 5 fps／stride 1 | stride 2／5 降低離線索引成本，但可能少觀測；需新 index／參數組，不隱藏缺口 |
| 圖與 ROI 凍結時點 | 事件渲染之前完成獨立檢查與 hash 凍結 | 在檢查事件證據前才凍結，稽核較難；D68 已選事件渲染前凍結 |
| preview 範圍 | 每台 5 格，WIDE 第二角度加 5，共 45 格 | 改格數先寫選樣規則與預算，不依結果挑格 |
| 人物尺度／HSV／切鏡等門檻 | §11 切鏡參數（D65）與 #126 搜尋／兜底預算（D67）已為第一版初值並須綁 parameter_set hash；人物尺度與 HSV 仍 OPEN／PROPOSED | 參數調整只能用授權的 r004 preview 另出新版核定；不拿舊 smoke 分數、白色人物或本表算術當預設值 |

## 8. 執行 gate 與實際產出

- G1 已成立，G7 已由 D66 核定；G3 須 #125 合併，G4（O10／K7）仍未成立。G5 依 D67 只授權 #132 複核通過並合併後的建檔與靜態校正匯出；G5 渲染部分未授權，仍受 D41 限制。此文件 PR 不替代任何 gate；檔案 pin 或 `.blend` 另存成功不等於場景／物理認證。
- 任意推論／下載先記 `df -h`；任何 render／preview 開始前同時查精確 available bytes，**至少 12 GiB**；低於 8 GiB 停止產製。`df -h` 顯示四捨五入的 12Gi 不能證明達標。預算小也不豁免。
- 本輪精確快照：`df -k` available **12,529,324 KiB**（約 **11.95 GiB**），`df -h` 顯示 12Gi；此快照未達 12 GiB，且沒有渲染授權。未開始任何產製。
- 輸出集中 `~/amidst-artifacts/<task>/`；PR 僅文件、hash／統計，不上傳媒體、權重、DB、人工標註或 GT。暫存用完刪除；不建立 worktree。
- Model / effort：Codex（GPT-6）；精確變體／effort UNKNOWN。
- Files changed：只有本文件。PR／commit 與實際命令／結果記在 PR 及 #97 留言，不把預計工作當已完成。
- 驗證範圍：HFOV／K 與預算算術、文件 diff／連結，以及 #127 舊契約 SYNTHETIC 自測。舊包通過不能當作 `3873ff2` 或新 RGB 後端通過；待 Claude 更新測試包後，產品 PR 再跑對應版本。
- Not verified：r004、相機姿態／實際校正、靜態用途／graph、preview／偵測／HSV 品質、任何推論／render／API／Agent／browser acceptance。本輪實際產出只有可審查提案。
