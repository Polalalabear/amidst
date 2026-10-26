# Q1／Q3 組員出題依據

更新：2026-10-26（Asia/Taipei）。依 [D80](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6399200757) 更新，來源基準為 staging `4c9614046cfb860857a24b96b4663a2578823797`（含 #221、#224、#226）。第一版 Q1 單 run、缺 clock mapping 反問沿用 D73；契約後續條文以固定版本為準，不把此指南當成新契約。本文件只定格式、範圍與配額，不提供題目、標準答案或逐時段位置。組員獨立出題與判斷，Claude 依 D75／D80 轉成精確評估標註；Codex 的匯入器只驗證、保留與評分，不製造答案。

## 1. 組員實際要交什麼

組員不用 Git、JSON 或 repo 權限。先讀當次包的 `README.md`、`RETURN/README.txt`，以該包說明為準。現行流程開 `A_文字情境/情境.csv` 與 `B_畫面審查/審查表.csv` 填寫，再另存 **CSV UTF-8** 到 `RETURN/情境_<姓名>_YYYY-MM-DD.csv`、`RETURN/審查表_<姓名>_YYYY-MM-DD.csv`。保留原表、欄名、固定編號與鎖定欄；交回完整資料夾或 ZIP，不能只交螢幕截圖。若當次包只派文字題，依 README 交指定部分，不能把未派的畫面判斷當成缺件。

舊第一階段的 60 句建議已不是最低題數。D80 的 Q3 必做 8 題、Q1 共 6 題，配額與資料限制見 §7；#199 Codex 候選不作為題目來源。具體句子與答案由組員獨立寫。試算表存檔後重開核對中文字、欄名和時間，不把時間自動改成日期序號。

| 情境 CSV 欄位 | 組員怎麼填 |
| --- | --- |
| 編號 | 保留發包編號；一列一個、不可重複 |
| 使用者會說的話 | 完整自然語句，不含真實個資 |
| 想找什麼(人/車/相機) | 跟一個人物填「人」（Q2／FIND_PERSON）；查哪些鏡頭拍到某物填「相機」（Q1／FIND_CAMERAS），物件寫在原句。查車可填「車」，仍是 Q1；靜態家具填「相機」 |
| 顏色 | 無條件時留空；只用在人，不代表身分 |
| 開始時間、結束時間 | 照原話；已知日期、時區才另填，未知不補今天。已選 run 的日期規則見 §5 |
| 鏡頭或區域 | 只用本包目錄；含糊就註記，不能把口語名稱當正式 ID |
| 系統該反問嗎(是/否) | 由組員判斷，不由匯入器推定 |
| 預期結果(找得到/找不到/不支援/超出時間/反問) | 五種值之一；五種不適用時，依 §6 留空加固定關鍵字 |
| 備註 | 特殊狀況用 `關鍵字=…｜鏡頭=…｜說明=…`，說明放最後。鏡頭未知可留空，不自行補對應 |

有畫面依據時，組員標自己看見的「找得到／找不到」；索引 coverage 或必要資料不足由維護者核對並記錄，不能要求組員看出推論尚未執行。精確標註仍由評估端獨立整理，不能讀模型預測補答案。

畫面審查只改 `答案(T/F/不確定)` 與備註：判斷同編號圖片能否支持「系統說法」；F／不確定要寫原因。這不判斷跨鏡身分、追蹤品質、盲區路線或物理通行。PILOT A／B1 不進正式評估分母。

## 2. 內部 JSONL 對照（給匯入器／評分器維護者）

`queries_v1.jsonl` 保留組員 `id`、原文 `text`、`category`、`notes`，精確標註由評估端提供：

| 欄位 | 來源／約束 |
| --- | --- |
| expected_llm_output | 依 `q-demo.q3-llm-output.v1`；schema_version、intent、class_term、color_term、time_literal、camera_terms、region_terms、needs_clarification、clarification_question 都不可漏 |
| expected_status | §6 的 Q3 六個封閉狀態之一 |
| expected_structured_query | PARSED 才能有 Q1／Q2 request；條件與來源須來自人工標註及凍結 context，不能靠 parser 或搜尋結果反推 |
| scene/run/clock、index、parameter_set ID/hash | 從發包 MANIFEST／評估 context 綁定；缺件標 MISSING／UNKNOWN，不能用其他 run 代填 |

LLM 中間輸出的 intent 是 `FIND_CAMERAS`、`FIND_PERSON`、`EXPLAIN`、`UNSUPPORTED`；詞語欄只能取原句片段，正式 class／color／camera／region 對應查凍結詞表。

`cases_v1.jsonl` 保存 `id`、`description`、`index_ref`、`request`、`query_binding`、`expected_response_core`、`notes`。request 與 response core 的 required keys 依凍結契約；粗略「找得到」不能自動生成鏡頭、排序、時間片段、coverage、數量或框。

D80 的 `query_binding` 由評估端 Claude 獨立計算，至少含 `request_sha256`、`query_sha256`，均為 64 位小寫十六進位。匯入器檢查 `request_sha256 = SHA-256(canonical(request 去除 origin))` 後原樣帶入；**不生成 query_sha256**，其完整 preimage 以契約為準。缺少 binding、格式錯誤或 request hash 不符為 `QUERY_BINDING_INVALID`，不輸出該列 case。完整契約驗證仍由評估工具負責。

## 3. 可填的詞與支援邊界

只使用本包 MANIFEST 綁定的 class_map／alias／color_vocabulary／camera／region 目錄。RT-DETR 完整 class_map 與中文 alias 不同，不能按場景資產清單判定支援。下表仍是 PROVISIONAL，不代替正式詞表。

| 暫定中文說法 | class_label | 限制 |
| --- | --- | --- |
| 人、人物、行人 | person | 不代表身分 |
| 車、汽車、轎車 | car | 不涵蓋所有車種，不把 bus／truck 改成 car |
| 椅子 | chair | 有無依據由人工圖片判讀，偵測結果另行評估 |
| 桌子、餐桌 | dining table | 不把所有平台、櫃子視為餐桌 |

樹不能改成 potted plant；其他 COCO label 是否有中文 alias 要查正式表。人物真名、身分、是否同一人、跨 run 串接身分以及需要 GT／劇本才能回答的真實盲區路線、位置與到達時間都不支援。

紅／紅色／紅衣與藍／藍色／藍衣是 r004 候選詞；正式 HSV／詞表 hash 待 #114／#118。顏色只用 person，車或椅子的顏色條件屬 `UNSUPPORTED_CONDITION`。黑／白／灰不能直接套有色 hue bands。沒有顏色條件與顏色 UNKNOWN 不同；STRONG／WEAK 是啟發式證據，不是機率或辨識保證。

## 4. 鏡頭與區域

鏡頭名稱只是代號，不能依用途猜內容或下一站。r004 設計含 `CAM_EXT_CAR`、`CAM_EXT_CLEAR`、`CAM_ENTRY`、`CAM_W1`、`CAM_W2`、`CAM_BRANCH`、`CAM_R101_IN`、`CAM_WIDE`。中文名稱與正式 region alias 以當次凍結目錄為準；草案目錄不能冒充正式 parser alias。D74 的 CAM_ENTRY 只供 Q1，Q2 追蹤範圍與實際出口檢查依 D81／凍結圖。

A／B1 PILOT 的 cameras.json 有 W1、W2、N1、R102_CTRL；同名 camera 跨 run 仍需各自 run／clock 來源。safe scene_static 的 walkable／portal ID 不是核定 region_id，不能直接代填。r004 靜態 catalog 已有來源 pin，但「來源已 pin」不等於 D80 正式發包的 catalog 已凍結。

## 5. 時間範圍與台北展示時鐘

D80 固定情境是工作台已選 A4。原句沒講日期時取**已選 run 的日期**，不因省略日期就反問；如果沒有選定 run 或沒有 clock mapping，才回 `NEEDS_CLARIFICATION`，不能猜今天、最近影片或另一個 run。

來源時間用整數微秒，範圍半開 `[start, end)`。正式 `DECLARED_DEMO_CLOCK` 需綁 run／clock／hash，含 timezone、wall_origin、t0_us、duration_us。A4／B4 設計各 30 秒，但正式 run_id、clock_id、mapping 宣告與 hash 仍 MISSING，不能把設計時長或歷史示例當成正式映射。

A PILOT 的來源範圍為 [0,10000000) us，B1 為 [0,20000000) us，皆為 5 fps。#89 的 `Asia/Taipei`、`2026-11-01T13:00:00+08:00`、t0_us=0 是歷史示例，**不得回填 A4／B4**。兩個 run 展示時刻相同也不代表同一事件或可以跨 run 追人。

## 6. 找得到、找不到與不能回答

CSV 欄名不改，預期結果仍只有五種固定值或空白。空白時，備註必須以 `關鍵字=(部分涵蓋|時間無效|解析失敗|只測解析|資料不足)` 的其中一項開頭，後面接全形 `｜` 或字串結尾；仍須有 Claude 的精確標註。一般說明中提到關鍵字不算有效前綴。建議完整格式為 `關鍵字=…｜鏡頭=…｜說明=…`，說明欄放最後。

| 狀況 | 預期結果 | 空白時的固定關鍵字 | 精確標註必須對應 |
| --- | --- | --- | --- |
| 有相符支持 | 找得到 | — | Q1 READY |
| 沒有相符支持 | 找不到 | — | Q1 NO_MATCH；不證明現實不存在 |
| 查詢時間與 run 的時間範圍只有部分交集 | 留空 | 部分涵蓋 | Q1 PARTIAL；不是缺格、未推論或資料不足的通稱 |
| 類別不支援 | 不支援 | — | Q3 UNSUPPORTED_CLASS |
| 條件不支援 | 不支援 | — | Q3 UNSUPPORTED_CONDITION |
| 查詢時間與 run 完全無交集 | 超出時間 | — | Q1 OUT_OF_RANGE |
| 時間寫法不合法 | 留空 | 時間無效 | Q3 TIME_EXPRESSION_INVALID |
| 指代／鏡頭／區域含糊，或沒有選定 run／clock mapping | 反問 | — | Q3 NEEDS_CLARIFICATION |
| 必要索引／圖／資料缺失 | 留空 | 資料不足 | Q1 UNKNOWN；不當成 NO_MATCH |
| 無法解析原句 | 留空 | 解析失敗 | Q3 PARSE_FAILED |
| 只評解析、不執行 Q1 | 留空 | 只測解析 | Q3 PARSED，不能另有 Q1 case |

匯入器以人工精確標註核對上表；不一致為 `CSV_ANNOTATION_STATUS_MISMATCH`，該列不輸出有效 Q3／Q1 資料。空白沒有有效關鍵字、缺精確標註或其他必要欄位，保留原文並報 INVALID；不從 parser／模型輸出補答案。有效空白加關鍵字也不是預填答案，必須通過人工標註及格式驗證。

Q3 最終 status 為 `PARSED`、`NEEDS_CLARIFICATION`、`UNSUPPORTED_CLASS`、`UNSUPPORTED_CONDITION`、`PARSE_FAILED`、`TIME_EXPRESSION_INVALID`。PARSED 只表示語句可解析，不表示 Q1 命中。第一版 Q1 一次要求多 run 時，Q3 回 NEEDS_CLARIFICATION；直接 Q1 多 run 回 UNKNOWN，依 D73 處理。

框太小、遮擋、截斷、低光或低飽和度會影響 detector／HSV。組員看不清就記不確定，不能由檔名、人物設定、相鄰劇情或系統框反推答案；沒有偵測不證明畫面沒有物件。

## 7. D80 題數、資料限制與評估獨立性

| 工作 | 必做配額 | 依據 |
| --- | --- | --- |
| Q3 直接查詢 | 4 題：找相機 2、找人 2 | 不需要畫面 |
| Q3 系統該反問 | 2 題 | 依選定 run／clock 的真實 context 判斷 |
| Q3 不支援類別 | 1 題 | 凍結詞表 |
| Q3 不支援條件 | 1 題 | 契約支援邊界 |
| Q3 時間無效、解析失敗 | 選填列，另計 | 不替代上列必做 8 題 |
| Q1 | 6 題，只出椅子、桌子等靜態家具 | 依 8 台空場景圖獨立判斷 |

人物與車輛的 Q1 題等正式 RGB 渲染後另發第二包。出題範例 CSV 只解釋每欄填法，不放真實句子；不要以 Codex 候選題或模型輸出作標準答案。即使 Q3 不需要圖片，D80 整包仍需正式 A4 context，不能跳過發包硬前提。

正式、SYNTHETIC、PILOT 分開；PILOT 不進任何正式評估分母、索引、參數、圖、排序或 prompt。回收檔僅供評估端；推論不得讀人工答案、GT、劇本、人物設定或路線。辨識正確性仍需獨立人工資料，不以本指南或結構驗證代替。

## 8. 版本、匯入入口與尚缺資料

- D80／D81 決定見 #93；舊 #221／#224／#226 已包含於 staging `4c9614046cfb860857a24b96b4663a2578823797`。#219 的契約續修由其指定 owner 處理。
- 回收匯入入口為 [scripts/import_team_review_pack.py](../../scripts/import_team_review_pack.py)，用 `--text-csv`／`--review-csv` 指向 RETURN 的另存檔、`--annotations` 指向 Claude 精確標註；輸入 MANIFEST 固定 pin。保留 returned CSV hash、annotation hash、輸出 hash 與逐列 INVALID 原因。收據的 `query_binding_source` 為 `EVALUATION_OWNER_PER_D80`。
- Claude 依 D80 自建本次 MANIFEST，並用匯入器實測相容；不等 builder 新模式，亦不把現有 builder 的 PILOT 宣告套進正式包。
- **發包硬前提**：正式 A4 run_id、`DECLARED_DEMO_CLOCK` 宣告與 hash，以及凍結 camera catalog SHA-256。任何一項缺少就不打包，不得用 A／B1 或工程 A／B 代填。
- #113 已有 r004 static／HFOV90° 來源收據；來源 catalog SHA-256 `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f` 僅為 SOURCE_PINNED_NOT_FROZEN。正式 A4／B4 run／clock／source bindings、凍結 catalog、#109 詞表、#114 色彩方法、#116 圖與 #118 索引以其正式收據為準。
- D81 要等 yyin 的 3 題澄清併入圖 v3 複核，才提交 G4；G4／必要核定後凍結設定，再正式 RGB、索引與 baseline。D70 既有產製授權仍有效，但不取代這些前提。時程依賴審查回收，完成日期 UNKNOWN。
- 本次 metadata 缺項及來源證據見 [R004_FORMAL_METADATA_STATUS_20261026.json](../history/R004_FORMAL_METADATA_STATUS_20261026.json)；此檔是狀態收據，不是 runtime clock 或正式發包 MANIFEST。
