# Q1／Q3 組員出題依據

日期：2026-10-21（Asia/Taipei）。Refs #146、#89、#138、#147。依契約 #86 @ `3873ff2`、D65–D71；#144 的補完提案在 PR #148，新增 wire 格式仍是 PROPOSED。這份文件不包含題目、標準答案或逐時段「誰在哪台」。出題、預期結果與畫面 T／F 由組員獨立填寫；Codex 只做格式轉換與評分程式。

## 1. 組員實際要交什麼

依 #147，組員不用 Git、JSON 或 repo 權限。使用者把 LOCAL 審查資料夾交給組員，組員填 `A_文字情境/情境.csv` 與 `B_畫面審查/審查表.csv`，再交回使用者。文字建議至少 60 句；具體句子與答案都由組員寫。CSV 用 UTF-8，以試算表編輯時保留欄位名稱、編號和時間文字；不要把時間欄自動轉成試算表日期序號。

`情境.csv` 欄位：

| 欄位 | 組員怎麼填 |
| --- | --- |
| 編號 | 保留發包編號；一列一個、不可重複 |
| 使用者會說的話 | 寫完整自然語句，不含真實個資 |
| 想找什麼(人/車/相機) | 寫希望系統完成的工作，不靠程式猜意圖 |
| 顏色 | 無條件時留空；只用在人，不指人物身分 |
| 開始時間、結束時間 | 原文時間；已知日期與時區時一併填。未知就留空並在備註說明，不自行補現在時間 |
| 鏡頭或區域 | 用本包目錄可用的名稱；指代含糊時照實標反問，不把口語名稱當正式 ID |
| 系統該反問嗎(是/否) | 組員判斷，不由匯入器推定 |
| 預期結果(找得到/找不到/不支援/超出時間/反問) | 組員獨立填；需要缺件／部分涵蓋等細節時寫備註，不能硬塞成「找不到」 |
| 備註 | 依據、歧義與無法確定的地方；沒有依據就明記 UNKNOWN |

畫面審查只填 `答案(T/F/不確定)` 與備註：判斷「系統說法」與同編號圖是否相符，不判斷追蹤品質、身分或盲區路線。`PILOT` A／B1 不進正式評估分母。

## 2. 內部 JSONL 對照（給匯入器／評分器維護者）

`queries_v1.jsonl`（#89）一行的欄位如下。這是空白格式示意，沒有題目或答案，不能當作合法完成資料：

```json
{"id":"<組員編號>","text":"<組員原文>","category":"<組員分類>","expected_llm_output":null,"expected_status":null,"expected_structured_query":null,"notes":"<組員備註>"}
```

| 欄位 | 來源／約束 |
| --- | --- |
| id、text、category、notes | 組員內容或發包編號；原文不改寫 |
| expected_llm_output | 組員標註；依 §7.1 `q-demo.q3-llm-output.v1`。intent、class_term、color_term、time_literal、camera_terms、region_terms、needs_clarification、clarification_question 都不可漏 |
| expected_status | 組員判定；只能填 §7.4 的六個值（見下節） |
| expected_structured_query | 組員已明示的條件與語意經機械式換算；PARSED 才能有可執行 Q1／Q2 request。缺少對應資訊就 INVALID，不能靠 parser 或 Q1 的預測反推標準答案 |
| scene/run/clock、索引與 parameter_set ID/hash | 發包時凍結的 MANIFEST／評估 context 自動帶入；組員不用寫 hash。缺正式綁定時標 UNKNOWN，不能用別的 run 代填 |

Q3 LLM 中間輸出的 `intent` 封閉清單是 `FIND_CAMERAS`、`FIND_PERSON`、`EXPLAIN`、`UNSUPPORTED`；`UNSUPPORTED` 不是 Q1／Q3 最終 response status。詞語欄只能是使用者原文的片段；正式類別／顏色／鏡頭／區域的對應由凍結詞表查出，不由 LLM 擴充。

`cases_v1.jsonl`（#138）原訂 `{id, description, index_ref, request, expected_response_core, notes}`。request 依 §6.1，核心欄位為 schema_version、scene_id、run_ids、time、condition、camera_ids、region_ids、origin；精確 required keys 以凍結 schema 為準。`expected_response_core` 含組員提供的 status、reason、results 的鏡頭／排序／片段／coverage，以及 no_match_cameras、not_evaluated_cameras。自然語句與粗略「找得到」不足以自動建立這些精確答案：回收時保留原文，列為缺少標註，不猜鏡頭、時間、數量或排序。#138 第一階段仍是 SYNTHETIC 索引，與真實 RGB／PILOT 分開。

## 3. 可填的詞與支援邊界

正式可用值由**該包 MANIFEST 綁定的 class_map／alias／color_vocabulary／camera／region 目錄**決定。#109 尚未交付正式 alias，本表是 #89 暫定表的有限整理，標 `PROVISIONAL`，不能冒充正式 runtime 詞表。

| 中文說法（暫定） | class_label | 限制 |
| --- | --- | --- |
| 人、人物、行人 | person | 不代表可辨識身分 |
| 車、汽車、轎車 | car | 不涵蓋所有車種，bus/truck 不能偷偷改成 car |
| 椅子 | chair | 是否偵測到由 RGB 模型輸出決定 |
| 桌子、餐桌 | dining table | 不把所有平台、櫃子視為餐桌 |

RT-DETR 的完整 class_map 與這份中文 alias 表是不同資料；正式支援不得只按場景物件清單決定。樹不能換成 potted plant；戴眼鏡、人物真名、特定身分、誰是同一人等超出本版條件。dog 等其他 COCO label 是否有中文 alias，要看正式表，不能因暫定表沒列就斷言模型不支援。

| 顏色說法 | 候選 label | 現況 |
| --- | --- | --- |
| 紅、紅色、紅衣 | red | r004 目標色；正式 HSV 方法／詞表 hash 待 #114／#118 |
| 藍、藍色、藍衣 | blue | r004 候選色；正式綁定同上 |
| 橙、黃、綠、紫、黑、白、灰 | 尚未凍結 | #89 曾列為暫定顏色；不是已驗證或核定支援清單。尤其黑／白／灰不能直接套有色 HSV hue bands |

顏色只用在 person；color 條件用在車或椅子時屬 `UNSUPPORTED_CONDITION`。沒有色彩條件與色彩 `UNKNOWN` 是不同狀態。`STRONG`／`WEAK` 是啟發式色彩證據，不是機率、身分或辨識正確保證。

## 4. 鏡頭與區域

r004 八台是 D68 核定的**設計名稱**；2026-10-21 尚未由 #113 產生正式校正與 catalog/hash，以下中文說法僅供填表辨識、不是正式 parser alias。不要按鏡頭用途猜內容或答案。

| 設計 camera_id | 中文說法（提案） |
| --- | --- |
| CAM_EXT_CAR | 室外一號 |
| CAM_EXT_CLEAR | 室外二號 |
| CAM_ENTRY | 入口 |
| CAM_W1 | 西走廊一號 |
| CAM_W2 | 西走廊二號 |
| CAM_BRANCH | 分岔 |
| CAM_R101_IN | R101 門內 |
| CAM_WIDE | 廣角 |

r004 正式 `region_id` 清單與中文 alias **UNKNOWN**，等 #113／#116 的靜態 catalog 與 hash；不能把設計房間名自動當 region_id。缺映射的區域題可先保留原文與「待目錄」註記，不能納入正式解析正確率。

A／B1 PILOT 已交付的 cameras.json 有四台 `CAM_W1`、`CAM_W2`、`CAM_N1`、`CAM_R102_CTRL`。A 的實際 media bindings 是 W1、W2、R102_CTRL；B1 綁定全部四台。同名 camera 跨 run 仍須帶 run／clock 來源，不能混接。safe scene_static **沒有 regions 陣列**；`WALK_VEST_W`、`WALK_CORR_W`、`WALK_CORNER`、`WALK_CORR_N`、`WALK_R101`、`WALK_R102` 是 walkable ID，`PORTAL_R101`／`PORTAL_R102` 是 portal ID，均不可直接填成已核定 region_id。R102 拓撲與用途限制仍保留。

## 5. 時間範圍與台北展示時鐘

來源時間以整數微秒比較，範圍半開 `[start, end)`；結束時刻不包含在查詢內。正式 clock mapping 必須帶 run／clock／hash；沒有 mapping 不猜日期、今天或事件時間。

| 資料 | 來源範圍 | 台北展示時間 |
| --- | --- | --- |
| A PILOT `ctrl-lcorr-s1-a-5fps-v1-r001` | [0, 10000000) us，5 fps | 若採 #89 的示例 mapping：2026-11-01 13:00:00 至 13:00:10（+08:00，結束不含） |
| B1 PILOT `ctrl-lcorr-s1-b1-5fps-v1-r001` | [0, 20000000) us，5 fps | 同示例：2026-11-01 13:00:00 至 13:00:20（+08:00，結束不含） |
| r004 A4 | D68 核定時長 30 s；正式 run_id／clock_id／source hash UNKNOWN | 正式 wall_origin／起訖 UNKNOWN，不能用 A／B1 示例回填 |
| r004 B4 | 同上，30 s | 同上 |

#89 提供的是**示例** `timezone=Asia/Taipei`、`wall_origin=2026-11-01T13:00:00+08:00`、`t0_us=0`，不是影像的拍攝日期，也不是已發布的 r004 clock_mapping。兩個 run 展示時間相同不代表同一事件或可以跨 run 追人。

## 6. 找得到、找不到與不能回答

| 狀況 | Q1 status／行為 | 組員填寫時注意 |
| --- | --- | --- |
| 支援條件、完整推論範圍有支持 | READY（未核准圖／參數會降級） | 題目答案須由組員依凍結證據寫，不以場景設計代答 |
| 支援條件、完整推論範圍沒有相符 | NO_MATCH | 只代表「已推論影格沒有找到」，不代表世界中不存在 |
| 缺格、尚未推論、只有部分時段涵蓋 | PARTIAL | 不填成找不到；NOT_SAMPLED 與取樣策略另記，不能偽造完整覆蓋 |
| 類別不在凍結支援表 | UNSUPPORTED_CLASS | 不是 NO_MATCH |
| 顏色用在非 person 等不支援組合 | UNSUPPORTED_CONDITION | 不偷偷丟掉顏色再執行 |
| 查詢時間完全無交集 | OUT_OF_RANGE | 不把請求搬到最近的 run |
| 索引／圖／必要參數缺失 | UNKNOWN | 不用 fixture 補資料；D69 grid 不符同樣 UNKNOWN／不執行 |
| 時間部分相交 | PARTIAL，列 uncovered 範圍 | 不能宣告全段沒找到 |

Q3 最終 status 封閉清單：`PARSED`、`NEEDS_CLARIFICATION`、`UNSUPPORTED_CLASS`、`UNSUPPORTED_CONDITION`、`PARSE_FAILED`、`TIME_EXPRESSION_INVALID`。`PARSED` 才能自動執行。代名詞指代不明、缺日期／clock mapping、鏡頭或區域詞有多個解釋，需反問；無法解析時不能亂選一台。Q3 `PARSED` 只表示查詢可解析，**不表示 Q1 找得到**。Q3 缺時鐘與 clarification wire 的細節仍待 #144／#148 決定。

框太小、半身、被擋、截斷、低光或低飽和度會影響 RT-DETR／HSV。色彩裁切像素不足、截斷過多、低亮度／飽和度時可以 UNKNOWN；沒有偵測不證明沒有物件。組員看不清就選「不確定」，不要由檔名、相鄰劇情、人物設定或系統判斷反推答案。

## 7. r004 種類層級與評估獨立性

設計範圍包含人物（紅衣與藍衣）與室外車輛；車輛實際種類 label **UNKNOWN**，待 r004 的 RGB 與正式 detector class_map。不得把資產名當成 car／bus／truck 標註。此處不列數量、逐時段位置、路線或到達時間。A／B1 白色人形只能用來試用流程，不核定 r004 紅／藍 HSV。

題目、精確標準答案與 T／F 由組員獨立判斷。匯入器只能做可追溯的機械式轉換：缺欄、矛盾、無映射、未填答案或不足以構成精確標準答案的列，一律標 INVALID／待補，不自動補答案。正式資料、SYNTHETIC 與 PILOT 分開；PILOT 不進任何評估分母、索引、參數、圖、排序或 prompt。所有回收結果只供評估端使用，推論端不得讀它們或劇本。

## 8. 固定來源與待補

- 契約 #86 @ `3873ff2dbe97c88b3de2cfcdfc7df393fdff23d2`；#144 補完 PR #148。
- #89／#138 原有 JSONL 格式與暫定詞表；#147 取代組員 Git／JSON 交付流程，本文件不假裝自然語句 CSV 已包含全部精確 JSON 答案。
- D68 的八台用途、r004 30 s／5 fps／960×540 設計，以及 D71 的評估分工。
- 本次只讀既有 safe 側四個文字 JSON，未讀 RGB／GT／劇本；本機已交付副本的 bytes SHA-256：A cameras `6599defea9b53592e8300973d3d4c3f4de0f84ea8a6846ca461873b63ce4e063`；B1 cameras `b374a737c9ed39178bfd4d32b17cb05ccfbdfc74e4c7ceafef46482a122fa1ad`；兩份 scene_static `a0b3a72c3e1967847b206a501ad64a70bfcb2544951e293db5eb064b71e49482`。只核對本機副本內容與 hash，未證明 Drive 已交給組員。
- 待補：正式 #109 詞表、#113 run/clock/calibration、#114 顏色方法、#116 region 目錄、#118 索引、組員精確標註。每版包必須保存以上實際版本／hash，不能沿用本表的 UNKNOWN 當正式值。
