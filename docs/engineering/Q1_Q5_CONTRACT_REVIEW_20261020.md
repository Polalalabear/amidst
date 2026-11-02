> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# Q1–Q5：D64、契約 #86 確認與離線索引預算

日期：2026-10-20（Asia/Taipei）。**文件審查與預算評估；非契約核准、實作授權或 r004 驗收。**

依據：[討論稿](Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md)，原提交 `60fa8ef64988435530b09fb258d79130e83977af`；[契約 #86](https://github.com/Polalalabear/amidst/pull/86) @ `258c7e2cf24b37ab69a5c4578fe23cc5f000d724`，文件 bytes SHA-256 `5336f6c3e2a1e0ca590f768adeed1849be764a6886eda609cc9327c62034c95f`；本次使用者 D64 原文。審查不直接編輯 Claude owner 的契約。

## 1. D64 與生效順序

- Q1–Q5 主線可列 DEVELOPMENT_RULES 的有界例外：Agent 可在決定性產生的合法 top-k 內依序取證、判斷切鏡並用於 Demo，必須有輪數／時間上限、決定性兜底與全程紀錄。**例外條文由 Claude 另開 PR；使用者核准合併後才生效。** D64 的方向確認不等於例外 PR 已合併。
- Q4 第一版只用 **RT-DETR＋HSV**，VLM 留第二版。Qwen 只讀結構化偵測／顏色證據，另做語意解析與說明。
- 修訂稿與 #86 都經使用者核准前，**不建 r004、不渲染、不改產品程式**。#86 §0.3 的「可先實作 Agent schema」不能跨過這個關卡。核准後，Agent Demo 啟用仍須等例外 PR 核准合併及參數核定；r004／渲染另守資產授權與 O10 gate。
- `mainline/q1q5` 已存在，本輪讀到 `f481fe0e300198235bd9599ff0091fd33d0381a5`。新 Q1–Q5 PR 以它為 base；停用的 3D 線／舊 PR 由既有流程封存 tag，不在本輪關閉、刪分支或改 tag。討論稿 §9 維持只列不刪，之後與 Claude 清單合併交使用者決定。

## 2. #86 §13：Q-01–Q-19 逐題確認

以下「同意」為 Codex 的供應方確認／提案，不替代使用者核准。所有數值維持 PROPOSED／待約定。

| 題號 | Codex 回覆 |
| --- | --- |
| Q-01 | **由 D64 解決方向，生效仍有 gate。** Claude 另開規則例外 PR，使用者核准合併後才可在 Demo 啟用有界 `AGENT_SEQUENTIAL`；先修 #86 §0.3／§8.1，不把「提出例外」當已生效。修訂稿／#86 尚未核准時連 `RULE_ONLY` 產品程式也不先改。 |
| Q-02 | 本次直接使用者訊息已確認更新 D63：Q1–Q5、Agent 依序查合法 top-k／規則兜底、不做同色干擾、允許 RT-DETR 權重下載與舊 A／B1 小批接線；不是較早 `agent_used: false` 的全面限制。請用本次直接授權與 D64 更新 §0.1／§0.2。下載／接線已實際完成，見本表 Q-14；這不授權 r004 或渲染。 |
| Q-03 | 同意 **D28 三個原鍵**與四層轉移提案，不加出口命中層級／區域跳數。需補精確定義：缺可見範圍／出口資料先為 tier 4；已知路徑含未知門狀態為 tier 3，不能因 `OVERLAP` 又升為 tier 1。`BLIND_GAP` 的面積應是「目標入口區域 ∩ 目標鏡頭核准靜態可見範圍」的 m²，附幾何／校正 refs；不是整台鏡頭可見面積、像素 ROI 面積或事件框面積。缺值 null 同層排後；每候選列實際 ranking keys。 |
| Q-04 | 同意 UNKNOWN 邊保留且明示，不證明人體可通過；`TOPOLOGICAL_ONLY` 不進 route／candidate，列 excluded。第一版 `PORTAL_R102` 依使用者指示保持此限制；r004 需重新驗證，不代表驗證後可自行撤銷該限制。解除需使用者另行明確決定。 |
| Q-05 | 第一版採固定 `search_window_us`，值待約定；不啟用依長度／速度縮窗，避免新增幾何依賴。候選窗限定同一 run／clock、媒體／索引可用範圍；裁切範圍與未涵蓋部分明示，不讀事件速度。 |
| Q-06 | 提案第一版用 **bbox 底邊中點落入 ROI**；它只是 2D 框代理點，不是腳點、世界座標或人體接地。ROI 優先人工標在不含人物的靜態畫面，附校正／靜態影像／方法版本／hash；允許經核准的純靜態校正投影方法。邊界／多出口／零命中保留歧義、展開合法出口聯集，不從事件 RGB 反推。精確邊界規則與必要門檻仍待契約明定／使用者核定。 |
| Q-07 | **同意一律離線索引，查詢不補推論。** `NOT_INFERRED`、`NOT_SAMPLED`、`MISSING` 與無偵測分開。重新產索引是另一次有版本、hash 與授權的離線工作，不能藏在 GET／查詢中。 |
| Q-08 | **D64 已決：RT-DETR＋HSV；VLM 第二版。** Qwen 不接 RGB 作看圖判斷。 |
| Q-09 | 同意 schema／時間／別名驗證成功後直接執行並顯示結構化查詢，允許使用者修改重查；含糊、缺時鐘或不支援條件先回明確狀態，不猜、不執行。 |
| Q-10 | 同意 Agent 與規則用同一 guard。維持 Codex `MATCH_STRONG` 提案；`WEAK／UNKNOWN` 不自動切，Agent 不能降低 guard。這是待使用者核定的提案，不把 STRONG 的 HSV 閾值當已核准。 |
| Q-11 | 同意**同一事件所有鏡頭共用一個 run／clock**。A4、B4 是兩個獨立 run／clock，不因展示牆鐘重疊而跨 run 串人；每 run 各有日期、時區、wall_origin、t0_us、hash。可聯合顯示查詢結果，不能把兩事件假裝同一條時間／身分鏈。 |
| Q-12 | 第一版不新增讀產製路線的驗收需求，以 safe RGB、靜態依據與操作紀錄做工程驗收。若未來要讀路線，另立隔離驗收授權；不得回填圖、ROI、排序、索引、Agent 或參數答案。 |
| Q-13 | **不用 PG**；版本化 JSON 圖／相機／參數，每 run JSONL＋manifest／hash（優先）或 SQLite，單一 store。新 Q3／Q5 以薄 provider 直接接 Ollama，不啟動舊 Agent 初始化，不碰 PG；權重設定指向既有位置、不搬移。這是架構確認，store schema 仍由 #86 定義。 |
| Q-14 | 已下載官方 `rtdetr_r18vd_dec3_6x_coco_from_paddle.pth`，81,001,853 bytes，SHA-256 **`3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0`**。官方 Apache-2.0 repo／release 來源、完整 80 類與實測在討論稿 §8。官方程式固定 `df2a96c8c3a098567a1149bf0248da6efe6d495d`；strict state load，分類 head／輸出均 80 維。配套 class-map **來源檔 bytes hash** `4d5b85566bbf29bf245e74fdca34e44b4c3a36d144f6679ba81ca2803bb15431`，它不是尚待契約定義的 canonical class_map hash。Smoke 用 PIL bilinear resize 640×640、RGB／255、FP32、CPU batch=1、top-300，**不額外 NMS**；請改 §4.2 範例的 `nms.applied: true` 為 false／iou null。正式 `detector_config` 尚未產製，不能拿 smoke reporting 分數 0.30 當正式閾值。 |
| Q-15 | 同意 Codex 產生、Claude 獨立檢查、使用者核准。r004 幾何／鏡頭固定後對受影響靜態範圍重新做 K7 類型檢查，保留方法／source／calibration／static-frame／graph hash；O10 未核准不能產可用 authority。不把 r003 收據直接貼到 r004。 |
| Q-16 | 同意歧義計入暫失，保留所有框；第一個缺格為 TEMP_LOST，超過核定缺格／時間才 SEARCHING，不因穩定 tie-break 強配。使用者可明確手動改選，記 USER，不能由程式冒充手動決定。 |
| Q-17 | 同意沿用 #76 的**提案→使用者核定→版本／hash 綁定**流程。唯讀核對 #76 @ `6f862e6` 是 552 行門檻提案文件，沒有已定的 Q1–Q5 JSON parameter schema；因此不能宣告檔案格式已相容。#86 應自行明定 parameter_set_id、值／單位、適用 run／取樣、核准來源／狀態與 hash，不能複製舊研究門檻或改舊 parameter set。 |
| Q-18 | 同意明確手動改選可以開新一次有界 SEARCHING 預算；先終結並保留舊決策，使用新 decision_id／seed／快照與 USER 紀錄。**不重置 session 累計上限／查詢期限**，無效提交或 Agent 重試不能偽裝手動改選；來源時間不倒退，跨 run／回看另開查詢。 |
| Q-19 | Codex 提案，Claude 獨立檢查，使用者核定。只用授權後 r004 小批 preview 的 RGB 人物裁切與可見色彩檢查，不讀 actor／材質 ID／腳本／GT；記裁切、色帶、S／V、像素量、遮影／截斷的 UNKNOWN 分支。以獨立 preview 選參數並凍結方法版本／hash，再產 Demo 索引，不能看 Demo 答案調整。現有白色人形 A／B1 不能決定紅藍衣品質或 HSV 閾值；本輪不先填數字。 |

## 3. 對齊、差異與需修文件的項目

已對齊：workbench-v2／#80 單入口、Claude UI／Codex 後端、r004 新 run 與 r003 pins 保留、兩層圖靜態輸入、D28 不按偵測／顏色排序、Agent 依序取證與記錄、Q3 和 Q5 flags 分離、STRONG 切鏡 guard 提案、時鐘對應、無 PG、缺證據／未知／無偵測區分、身分 UNCONFIRMED、禁止 GT／private 入推論。

供應方結論：**CONFIRMED_WITH_REQUIRED_DOC_FIXES**，未宣告 #86 全案可實作。請 Claude 在下一版處理：

1. **D64 gate／版本依據：**§0.1 改用已提交討論稿（本文件來源 `60fa8ef` 的 docs-only 移植版），而非未提交 `33a11dab…` 中間態；加入 D64 與例外 PR 核准合併 gate。移除先寫產品 schema 的暗示。§0.2 的舊「不准下載」保留歷史並明示已被新授權取代。
2. **候選排序／R102：**按 Q-03／Q-04 補 tier 優先順序、入口交集面積與 UNKNOWN；不能藉 r004 驗證自動解除 R102 的拓撲限制。所有面積來自核准靜態幾何，不從 event RGB 調圖。
3. **有界兜底：**§8.6 目前寫「從游標逐一取到結束」，須明訂只能在既有合法 top-k 快照／已核定窗口內，另有兜底候選數／時間與 session 累計上限；不讓 Agent 5 s 超限後變成無界掃描。未取證候選與 truncated 部分保持未評估，不能宣告全鏡頭無結果。
4. **取樣與連接器：**§8.2 跳過 NOT_SAMPLED 但 §11 按 run fps 換缺格秒數，降低索引率後會不一致。須同時列來源 grid、有效索引 grid、stride 與實際 elapsed_us，定義缺格與最大時間跨度；不能用 stride 把舊 0.6 s 暫失不知不覺拉長成 3 s。不得跨未觀測間隔補框。第一版取樣率未核定前不先改。
5. **Q4 聚合需覆蓋混合情況：**§8.3 的「全 NONE」「全 UNKNOWN」未涵蓋 NONE＋UNKNOWN。請定明優先順序：有 STRONG／WEAK 可記正向支持並另報 coverage；沒有相符且只要仍有未知顏色，不能當全條件不符。未推論／缺媒體造成的 PARTIAL 與完整取樣內的 NO_PERSON_DETECTED 分開；不以未取樣秒段證明目標不存在。
6. **切鏡時鐘／觀測選擇：**§8.3 的 best_observations 先按分數排序，不能無條件取第一筆就把目前播放時間倒退。Controller 須引用同 run／clock、在候選窗且切換來源時刻可對齊的觀測；未來觀測要明示來源時間與前方缺口，不能把舊觀測當現在畫面。返回原鏡頭也不倒轉。
7. **模型 metadata：**按 Q-14 填真實 weight／class-map 來源、strict-load 結果；NMS 範例修正。正式 class-map canonical schema／detector config hash 仍待建立，不混用 source-file hash。下列硬體評估不更換裝置或數值設定。

以上是待 Claude 修改契約的確認意見，不直接修改其檔案；待新版固定 SHA 再逐項確認，仍須使用者批准。

## 4. r004 離線索引時間：算術預算，不是新量測

本輪**沒有新推論／渲染／裝置切換**。沿用討論稿 §8 的舊 A／B1 smoke：35 張、CPU 2 threads、batch=1、640×640，forward 中位數 **1.108406209 s／格**（約 1108 ms），decode／resize／forward／postprocess 中位數 **1.136849167 s／格**；首格 forward 1.318 s，模型載入／deploy 0.395 s（不含 import）。這些不是 r004 的速度保證。

目前 r004 最終時長、fps、每事件實際鏡頭數與取樣率都是 **OPEN**。討論稿 §5 列出的工作鏡頭聯集為 8 台：EXT_CAR、EXT_CLEAR、ENTRY、W1、W2、BRANCH、R101_IN、WIDE（皆提案；舊 N1／R102_CTRL 若另保留並索引，須加計）。為給使用者可比較的預算，提出以下**規劃情境**，不把它寫成已核准 run 配置：

- A4 先按 4 台估（EXT_CAR、EXT_CLEAR、ENTRY、W1）；B4 按 5 台估（W1、W2、BRANCH、R101_IN、WIDE），共同相機在不同 run 各計一次。
- 每事件先比較 30 s 與 60 s；來源 5 fps 僅為預算假設。設第 i 個 camera-run 有 n_i 個來源格、索引 stride 為 s_i，`N = Σ ceil(n_i / s_i)`（從 sample 0 起、區間半開）；`T_forward ≈ N × 1.108406209 s`。

| 情境（A4／B4 各自時長） | 索引率／stride（來源假設 5 fps） | 預計索引影格 N | CPU forward 投影（min） | 加已量測 decode／resize／postprocess 的投影（min） |
| --- | --- | ---: | ---: | ---: |
| 4＋5 台；各 30 s | 5 fps／1 | 1,350 | 24.94 | 25.58 |
| 同上 | 2.5 fps／2 | 675 | 12.47 | 12.79 |
| 同上 | 1 fps／5 | 270 | 4.99 | 5.12 |
| 4＋5 台；各 60 s | 5 fps／1 | 2,700 | 49.88 | 51.16 |
| 同上 | 2.5 fps／2 | 1,350 | 24.94 | 25.58 |
| 同上 | 1 fps／5 | 540 | 9.98 | 10.23 |
| 每事件都索引全部 8 台；各 30 s | 5 fps／1 | 2,400 | 44.34 | 45.47 |
| 每事件都索引全部 8 台；各 60 s | 5 fps／1 | 4,800 | 88.67 | 90.95 |

這是每格中位數乘 N 的**線性估算**，不是整批實際中位數／P95 或上下界；不含 RGB 檔案讀取／hash、HSV、JSONL／SQLite 寫入、程序 import、重試／失敗恢復與同機負載。應另記 `T_total = T_import/load + T_read/hash + T_forward + T_HSV + T_store + T_retry`，未量測項不填數字。即使使用 smoke mean 會得到較小值，本稿採使用者指定的 forward median，不以此承諾完成時間。每事件超過上述時長或相機數增加時，依公式重算。

D41 與空間預算見[討論稿 §5](Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md)：低於 12 GiB 不得開始任何渲染／preview，低於 8 GiB 停止產製；本輪渲染 gate 快照約 11.54 GiB。1,350 格粗估約 0.55 GiB，不含 `.blend`；若每個 run 實際渲染的鏡頭多於 4＋5 台，必須索引每台或明示 NOT_INFERRED，不能沿用較窄估算宣稱全 run 完整。這些容量／耗時值不取代 #88、資產授權或 preview 後實測。

廣角 preview 若後續獲准，按 8 台每台 5 張＝40 張估，若 WIDE 的第二個 HFOV 再加 5 張則 45 張，CPU forward 投影約 44.34／49.88 s；**只算推論，不含渲染**。最終人物像素高度及 HFOV 必須從新 preview 量測，不用舊 A／B1 數字代填。

## 5. Apple MPS 與較低索引率選項（只評估）

| 選項 | 預期作用 | 風險／後續需要的證據 |
| --- | --- | --- |
| CPU、batch=1、保留 5 fps 離線索引 | 用已有實測作預算，Q2 保留較密的觀測支持；播放讀索引，不在查詢現跑模型 | 上表只是投影；真實完整 index throughput、讀圖／hash／HSV／寫入成本未量測。5 fps 來源不表示 5 fps 即時模型推論 |
| Apple MPS、保留原取樣率 | 可以評估把模型與 tensor 放到 MPS GPU，目標是縮短離線建索引時間、保留事件取樣密度 | **本機可用性、完整 RT-DETR 算子支援、輸出差異、實際加速倍數 UNKNOWN**；未跑 MPS。先核對 PyTorch／macOS／device，再在授權的固定 RGB 小批比較，記同步後耗時／記憶體／不支援算子，不能直接報 2×／4×或宣稱可即時 |
| 2.5 fps（stride 2）／1 fps（stride 5） | 理想上索引格數為 1/2／1/5；上表約成比例減少 CPU forward 成本，來源 RGB／播放 fps 不變 | 0.4／1.0 s 取樣間隔可能漏掉短暫可見或出口證據，切鏡時間更粗；Q2 IoU／中心距離跨格變大，更容易暫失。必須獨立版本、sampling coverage 與連接器時間上限，不把 NOT_SAMPLED 當無人或補框 |
| Q1 粗索引、Q2 保留較密範圍 | 可用較少代表格建立 Q1 快速目錄，把 Q2 所需鏡頭／時段另行離線物化 | 仍不允許查詢觸發補推論；不同 index 的 refs、hash 與覆蓋範圍明示，不得用粗索引承諾 Q2 完整性。只在使用者核准此分層策略後安排 |

PyTorch 2.6 官方文件說明 MPS 的裝置檢查與 model／tensor 移轉；它不能證明本 RT-DETR 在本機的算子支援或速度。[MPS backend](https://docs.pytorch.org/docs/2.6/notes/mps.html)

未來比較 MPS 時，計時需等 GPU 工作完成，並記 GPU tensor／driver memory；官方提供 `torch.mps.synchronize()` 與記憶體查詢介面。若出現 CPU fallback，需明列落回的算子與其耗時，不能把混合執行標成純 MPS 加速。本輪沒有開啟 fallback、改 dtype、改 batch／取樣率或跑 benchmark。[torch.mps](https://docs.pytorch.org/docs/2.6/mps.html)

建議待核准後先以有限 preview 固定實際 N，優先保留 Q2 證據密度並量測 MPS 可行性；若仍不符使用者可接受的離線等待時間，再比較 2.5／1 fps 的漏檢與切鏡代價。這不是現在開始實作或測試的授權。

## 6. 實際產出 / Actual output

- Model / effort: Codex（GPT-6）；精確模型變體／effort UNKNOWN。
- PR / commits: 計畫從 `mainline/q1q5` 的讀取版本 `f481fe0` 建立 `codex/q1q2-first-demo-plan`，只移植 `60fa8ef` 的文件變更（新 parent 會產生新 SHA，原提交不改寫），再納入本次 D64／契約審查／算術預算。實際 branch／commit／Draft PR 於發布交付回報；沒有 rebase／force 或合併主線。
- Files changed: `docs/engineering/Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md`、本文件；不直接改 #86 契約、DEVELOPMENT_RULES、前端或產品程式。
- Commands run and results: `gh pr view 75/80/86/76 --json ...`、`git ls-remote`／`git fetch` 核對 refs，固定 SHA 的 `git show` 讀契約；離線算術與 Markdown 連結／內容／diff 檢查，不執行新推論。35 張 smoke／1108 ms 是同日早一輪已執行收據，不是這次重測。
- Artifacts: 兩份工程文件；模型、原圖、逐框 JSONL 與 /private/tmp 套件不進 Git。舊 smoke 收據 hash／取樣及完整類別表保留在討論稿 §8。
- Verified: #86 固定版本的 19 題逐項回覆、必要文件修正清單、D64 gate、8 台提案聯集與 4＋5 台／時長情境算術。#76 只有門檻提案，不宣告與尚未定義的新 parameter JSON 已相容。
- Not verified: r004／render／HSV 閾值／完整索引與端到端延遲、MPS 可用性／效能／數值一致性、降低取樣率對漏檢與切鏡的實測影響、Agent／provider／store、browser acceptance、O10／規則例外 PR 是否獲使用者核准合併；未做新的模型測試或研究評估。
- Deviations, UNKNOWN items and follow-ups: #86 仍需 §3 所列文件修改與新版確認；所有新增情境都是預算假設，最終 run／clock／fps／duration／camera scope 未核定。前稿與退役評估為原有 LOCAL 未提交文件，討論稿移除不可在此 Draft PR 解析的相對連結，沒有順帶發布它們或原有 dirty README。清理清單只列不刪。

## 7. #92 X2／X3 修訂與指定 worktree 清理（2026-10-20）

本節是 #92 @ `80f5ca2` 後的增量結果；§6 與討論稿 §13 保留先前階段的歷史紀錄。

| 指定 worktree | 本輪判定／結果 |
| --- | --- |
| `demo-v1-main/amidst` | HEAD `f9b563f` 在最新 `origin/main` 等 refs 中，未推送 commits=0；tracked／untracked／ignored 清單空，未見開啟檔案或使用中 consumer。執行一般 `git worktree remove` 成功，未 force；本機 `main` 分支保持 `f9b563f`。移除前配置用量 104,956 KiB，不將它當實際回收量。 |
| `mvp-backend-integration/amidst` | HEAD `5d474c8` 已可由遠端 #80 branch 到達，未推送 commits=0；但存在 ignored 的 `data/engineering/local_run/office_mvp_v1/` audit／receipt 產物（3,764 KiB）與工具 caches，原位保存／可再生性未確認。**跳過移除**，不 force、不刪資料；本機 review 分支保留。沒有為了清理而讀其 observation／GT／人工標註內容。 |

兩個目標位於 `/Users/polalabear/.codex/worktrees/`；只處理使用者指定目標，未動 finalization、其他 worktree、權重、PG 或 §9 清理候選。沒有新增 worktree、clone、來源快照或環境。

### 實際產出 / Actual output

- Model / effort: Codex（GPT-6）；精確模型變體／effort UNKNOWN。
- PR / commits: #92 本輪限定兩份文件的增量提交，完整 SHA 於 PR 留言回報；一般 push，不 merge／rebase／force。
- Files changed: 討論稿 X2 的 D64 優先順序；§5 補 D41、容量快照與約 0.55 GiB 的 r004 情境估算；本文件同步補 gate 與本紀錄。不改契約或產品程式。
- Commands run and results: `df -h .`、`df -k .`；指定兩樹的 `git status --porcelain=v1 --untracked-files=all`／`git ls-files --others --ignored --exclude-standard`、fresh fetch 後的 `git rev-list --count HEAD --not --remotes=origin` 均為 0 未推送 commits；`lsof`／`ps` 未見實際使用中目標 consumer；只有 demo-v1-main 執行一般 `git worktree remove`。文件只做連結、算術、內容與 `git diff --check`，不跑模型／渲染／產品測試。
- Artifacts: LOCAL `/Users/polalabear/amidst-artifacts/q1q2-plan-x2-x3-20261020/` 存小型檢查／容量收據，沒有新 inference／index／preview 產物。原有 README 單檔臨時 stash 供主 checkout 切分支，結束回原分支並核對 bytes，其他 untracked 不動。
- 本次新增的磁碟用量: 提交正文淨增 **5832 bytes**；沒有新權重、RGB、索引或套件。外部報告目錄的實測配置用量於 PR 實際產出回報；Git metadata 開銷未獨立計量。全磁碟起點 12,855,612 KiB、指定移除後 12,105,204 KiB（淨變 −750,408 KiB），可能有其他同機寫入，不能把這個差額歸因於本任務。
- Verified: X2 與 D64 生效 gate 一致；D41 的 12／8 GiB 分層限制；1350／2400／4800 格容量粗估算術；已移除的 worktree 與保留 branch refs；另一樹的未保存風險保持原位。
- Not verified: mvp ignored 產物的備份等價性、可刪性或回收量；#86 新版與尚未交付固定入口的合約符合性測試包；本次沒有實作 API，未宣稱通過該測試包。r004／render／新索引／MPS／完整 Demo 仍未驗。
- Deviations, UNKNOWN items and follow-ups: 使用者回報約 7.6 GiB，而本輪起點為 12.26 GiB、移除後約 11.54 GiB；容量以 fresh df 為準，不沿用舊快照。第二個 worktree 因檢查未通過而保留，待確認其 ignored 成果保存。後續程式 PR 送出前須先跑 Claude 的固定版本合約符合性測試包。未開始下一項產品實作。
