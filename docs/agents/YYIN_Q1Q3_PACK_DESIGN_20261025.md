# yyin Q1／Q3 出題包設計（驗收計畫 T-2）— 設計稿

> 來源日期：2026-10-25（設計稿原檔為 LOCAL 副本，本文件為其內容的文件化版本）。
> 打包前置條件（2026-10-27 依 D84／D89 更新）：camera catalog 已由 D84 原樣凍結（SHA-256 `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`，收據 `docs/history/R004_CAMERA_CATALOG_FREEZE_D84_20261027.json`，收據檔 SHA-256 `3ade8183442781066b062d62f22e7af2335923fe73ead76b0fa5df5f9e0a81f5`；8 台 `static_validity: NOT_EVALUATED`，不等 G4）；剩下的硬前提是 #238 的 A4 run 註冊與 50 s clock 宣告（已於 `codex/q1q5-staging` 合併，merge `001cbcf`），打包引用該合併 SHA。依據：[D84](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6416451756)、[D89](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423194857)。
> 審查 [#240 留言](https://github.com/Polalalabear/amidst/pull/240#issuecomment-6434757822) 的 M1–M12、G1–G2 及再審 P2-1～P2-4、P3-1～P3-6 已於本版逐項更新；下文被取代的舊敘述已就地改寫。
> D83（P1 回交表人工讀取）不適用於本包。
> 2026-10-28 依 #240 增量複審更新 P2-A／B／C 與 P3-a～e；車輛題依 D97 第 7 點計入 Q1，逐鏡頭可見車輛清單由 CQ-26 #316 確認。


- 日期：2026-10-25（Asia/Taipei）｜設計：Claude Code（Opus 5.5 / effort 由協調者指定，本 session 實際 UNKNOWN）
- 範圍：只設計，不打包、不寫 GitHub、不 commit、不改 checkout、不開 clone。
- 依據（全部唯讀核對過）：
  - staging `codex/q1q5-staging` @ `4c9614046cfb860857a24b96b4663a2578823797`：已含 #221（merge `e52ace3`，指南 head `ff28f07`）、#224（merge `08d4793`，head `a2233cd`）、#226（merge `4c96140`，head `c326e4e`）。staging 上的 importer／builder 和 #226 head 相同（`git diff` 無差異）。
  - 指南 `docs/evaluation/Q1Q3_QUESTION_AUTHORING_GUIDE.md`（本設計稿寫作時依 staging `4c96140` 的 #221 版；**打包改用含 #269 的版本**，#269 合併後以其合併 SHA 為準，合併前不得打包；#269 head `e014be3` 僅供對照）。依 D97 先交件的主包框架可引用未合併的精確 head，但發包與合併仍須使用者同意，不把 head 當成合併 SHA。
  - `scripts/build_team_review_pack.py`（`TEXT_COLUMNS`、`csv_bytes`、`canonical`）、`scripts/import_team_review_pack.py`、`src/amidst/evaluation/q1_query_eval.py`、`src/amidst/evaluation/q3_parse_eval.py`、kit `994d34c` 的 schema。
  - 決定：D73（issuecomment-6395972547）、D75（6396184028）、D76（6396442549）；驗收計畫 `docs/agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md`（`mainline/q1q5`：T-2、CL-5、CL-7、CX-9）。
  - 包格式範例：LOCAL `r004-prereview-team-v2_20261024/`、`team-handoff-yyin-20261025/`（只讀文字檔）。

---

## 0. 設計前先講清楚的幾個事實（影響整份設計）

下列幾點是讀程式後確認的，有的比原本列的缺口更大，設計都已處理：

| # | 事實 | 證據 | 影響 |
|---|---|---|---|
| F1 | importer 要求 MANIFEST 是 `team-review-pack.v1`，`editable_files` 必須**剛好**是 `A_文字情境/情境.csv` 與 `B_畫面審查/審查表.csv` 兩個 | importer 第 36–38 行 | 只有 Q1／Q3 的包仍要放一份「只有表頭」的 `審查表.csv` 與其範本；`samples: []`。builder 不能產這種包（`n<1` 會拒絕，第 93–94 行），所以 MANIFEST 要由 Claude 打包時自建、但格式與 importer 完全相容（見 §7、決定 D-6） |
| F2 | importer 第 99–101 行：第 3 欄 ∈ {人,車,相機}、第 8 欄 ∈ {是,否}、第 9 欄 ∈ 五個值，否則整列 `TEXT_FIELDS_MISSING_OR_INVALID`；這個檢查在讀 Claude 精確標註**之前** | importer 第 97–103 行 | 缺口 1 屬實；而且不只 PARTIAL／UNKNOWN／TIME_EXPRESSION_INVALID／PARSE_FAILED：**任何「解析成功但組員不知道找不找得到」的人物題（Q3 PARSED／FIND_PERSON）在時段內時也填不出合法值**，目前只能出「超出時間」版本 |
| F3 | importer 建 `cases_v1` 時只保留 `{id, description, index_ref, request, expected_response_core, notes}`（第 121 行），會丟掉 annotation 裡任何 `query_binding`；評分器又要求 `cases_v1` 每題有 `query_binding`（`q1_query_eval.py` 第 181–184 行），而 receipt 釘住 `cases_v1.jsonl` 的 SHA-256（`dataset_eligibility` 第 121–123 行） | 同左 | 缺口 2 不能靠「Claude 事後在 cases 補欄位」解決：一補就和 receipt pin 不符、整份資料不被接受。只能由 importer 帶過去（需 Codex 改程式） |
| F4 | Q1 `expected_response_core` 要逐鏡頭的 `matched_segments`（`range_us`、`matched_frames`、`evaluated_frames`）與 `coverage`；評分器逐項精確比對 | `q1_query_eval.py` 第 140–162、204–215 行 | 一句話＋「找得到」做不出精確答案。人物及會移動的車需要逐格看正式 RGB；目前沒有影片可給組員。第9–12列只判斷靜態家具；A格車題依 D97 例外計入 Q1，但只能對 #316 清單確認空場景看得到車的鏡頭出題，不以空場景推定正式影片的逐格答案。精確標註仍由 Claude 獨立完成（D98-4） |
| F5 | Q3 評分器對 PARSED 題要該 run 的 clock mapping（`project()` 第 24–45 行，單 run） | `q3_parse_eval.py` | A4 已在 #238 宣告：`run_id` `ctrl-lcorr-s1-a4-5fps-v1-r004`、起點 2026-11-01 14:00 Asia/Taipei、`source_duration_us` 50,000,000（merge `001cbcf`）；B4 的宣告 UNKNOWN，本包不用。camera catalog hash 已凍結（D84），不再 UNKNOWN；中文別名是否正式仍 UNKNOWN。包要給組員「影片的展示時間範圍」才能判斷超出時間／時間部分相交，這是**打包的硬前提** |
| F6 | 契約 §3.2（staging 第 231 行）：使用者沒說日期時，日期與時區取「目前選定 run」的 clock mapping；指南 §6 卻寫「缺日期 → 反問」 | 契約／指南 | 兩者在「工作台已選一個 run」的情境下互相矛盾。包必須固定情境（見 D-5） |
| F7 | r004 正式 region 目錄 UNKNOWN：v2 包裡的 `region_graph.json` 是 `approval_status: DRAFT`、`approval_ref: null`（`rgraph:r004:static:9452968c1b2db3e5`）；#116 OPEN | v2 包 provenance | 區域詞不能用在「應直接查」的題目，只能用在反問題 |
| F8 | `AMIDST_ARTIFACTS` 在目前 shell 沒有設定 | `echo $AMIDST_ARTIFACTS` 空白 | 打包一律用 `LOCAL:預設 artifacts 目錄`；importer CLI 也硬性要求輸出在 `LOCAL:預設 artifacts 目錄` 底下 |

---

## 1. 包結構

包名：`q1q3-authoring-yyin-v1_<YYYYMMDD>`，放 LOCAL `LOCAL:預設 artifacts 目錄/`。組員不用 Git、Python、JSON。

```
q1q3-authoring-yyin-v1_YYYYMMDD/
  README.txt                    給組員：工作內容／要提交項目／操作／不要改（§2 全文）
  START_HERE.html               離線表單入口（雙擊開；不連網）
  app.js                        表單邏輯（§3）
  style.css                     版面
  data.js                       window.PACK_DATA = <DATA.json 同內容>（file:// 讀不到 JSON，所以包一層）
  DATA.json                     表單資料：欄名、下拉值、關鍵字、編號、配額、鏡頭目錄、時間範圍、提示文字
  A_文字情境/
    情境.csv                    importer 指定的可編輯檔；只有編號 Q0001–Q0014，其他欄空白（表單不直接改它）
    範例.csv                    填法示意（不含任何題目或答案；內容依 D-3）
  B_畫面審查/
    審查表.csv                  只有表頭（importer 結構需要；本包不做畫面審查）
  templates/
    情境.csv                    與 A_文字情境/情境.csv 位元組相同（importer 第 46 行核對）
    審查表.csv                  與 B_畫面審查/審查表.csv 位元組相同
  catalog/
    鏡頭目錄.csv                camera_id、中文說法（標「提案」或「正式」）、對應圖檔
    時間範圍.csv                值來源＝#238 合併版（`001cbcf`）的 A4 宣告整段 `[t0, t0+50 s)`，即 14:00:00–14:00:50（結束不含）；附來源 clock_mapping SHA-256。**不得**使用 D87 前的 30 s，也不得放情境卡 Q2 手動範圍 `[0,48)` 或任何事件時刻
    詞表.csv                    類別與顏色可用說法（標 PROVISIONAL 或正式 hash）
  images/cameras/CAM_*.png      r004 八台空場景靜態畫面（只在 D-3 選 (a) 時放；複製自 v2 包並核對 SHA-256）
  maintainers/
    （指南原檔不放進組員包，見 G1；PACK_NOTES.md 只記 #269 合併 SHA 與指南檔案 SHA-256，不寫指南路徑／檔名）
    PACK_NOTES.md               給 Claude 轉換者：配額、備註格式、轉換規則版本、已知限制
    build_q1q3_pack.py          打包腳本（可重建；組員不用）
  RETURN/
    README.txt                  只放回交檔：情境_yyin_YYYY-MM-DD.csv（未完成會是 _INCOMPLETE）
  tools/
    verify_pack.py              收件者核對 MANIFEST 與回交 CSV（只檢查格式，不判斷對錯）
  MANIFEST.json                 team-review-pack.v1 相容（§7 第 9 步）
```

檔案用途補充：

- **回交檔**：`RETURN/情境_yyin_YYYY-MM-DD.csv`；有必填未完成或配額未滿時，檔名自動加 `_INCOMPLETE`。和 builder README 的 `情境_<姓名>_YYYY-MM-DD.csv` 同一種命名。importer 收件時用 `--text-csv` 指這個檔。
- **為什麼 14 列**：Q0001–Q0008 是 Q3 基本題組（D76 的 8 題），Q0009–Q0012 是 Q1 加題，Q0013–Q0014 選填。importer 不准刪列（第 69 行），所以空著的選填列會以 `TEXT_FIELDS_MISSING_OR_INVALID` 出現在 invalid 清單，這是預期結果，PACK_NOTES 要寫明。
- **不放的東西**：影片、事件 RGB、系統輸出、#199 候選題、劇本、人物設定、GT、region_graph（DRAFT）、任何絕對路徑；情境卡 `docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md`（#253）、D89 可行性報告（#256）、D92 的路線調整（A4 路線改 EXT_CLEAR、計分事件 8→6）、事件時刻（`t_X`／`t_N`）、Q2 手動範圍（`[0,48)`）、指南原檔（G1）。`時間範圍.csv` 只放 A4 宣告整段。

---

## 2. README.txt 全文草稿（給組員的白話文）

> 角括號 〈…〉 是打包時才填的值；打包時找不到就停，不要用 A／B1 示例值代填。

```
這份工作內容（出題者：yyin，〈打包日期〉）
請你自己想 12 句「使用者可能對監視系統說的話」，最多可以寫到 14 句，並替每句填上「系統應該怎麼回應」。
這些句子會拿來測兩件事：系統能不能聽懂中文查詢，以及系統查「哪些鏡頭拍到某樣東西」時查得對不對。
用瀏覽器離線填寫，不用 Git、Python 或程式。預估〈打包者自測後填入的分鐘數〉。

- 第 1–8 列是必做的基本題組。頁面右邊有一張「題型進度表」，列出這 8 句需要涵蓋的回應種類（例如系統應該直接查、系統應該反問、系統不支援這種東西）。句子內容完全由你決定，每列要算哪一種也由你決定。
- 第 9–12 列是加題：問「哪些鏡頭拍得到椅子或桌子」這一類的話。請看包裡附的 8 台鏡頭空場景畫面，逐台勾選看得到或看不到。
- 第 13–14 列可以不填，空著也沒關係。
- 情境：請假設使用者正在看工作台上已經選好的那一段事件影片。那段影片的展示時間是〈YYYY-MM-DD HH:MM:SS〉到〈HH:MM:SS〉（台北時間，結束那一秒不算；打包時由 #238 合併版的 A4 宣告整段填入，預期為 2026-11-01 14:00:00 到 14:00:50，填入值必須與宣告逐字核對）。這是展示用的時間，不是真的拍攝日期。
- 你寫的句子和判斷就是標準答案的來源。之後由 Claude 照你的意思轉成程式要的格式，不會改你的句子。看不出來就照實寫「不確定」或 UNKNOWN，不要猜。
- 請自己一個人想，不要參考系統畫面、系統結果、其他人寫的題目、任何文件裡的例句、劇本或人物設定。

要提交項目
1. 填好的 RETURN/情境_yyin_YYYY-MM-DD.csv。頁面會自動命名；還沒做完時檔名會變成 _INCOMPLETE。14 列都要保留，不要刪列。
2. 完整資料夾或 ZIP（CSV 已放進 RETURN/），其他檔案保持原樣。
3. 交件訊息：有沒有沒做完的列、題型進度表哪一格湊不滿和原因。

操作
1. 完整解壓 → 雙擊 START_HERE.html。
2. 填日期。每一列照順序填：先寫「使用者會說的話」，再填其他欄。欄位旁邊的「?」有說明。
   - 想找什麼：第 3 欄填的是「目標類別」。人、車、椅子桌子分別填「人」「車」「相機」（椅子、桌子也填相機）。選「人」時頁面會再問一層：「要系統追這個人」或「只問哪些鏡頭有人」，照句子的意思選。
   - 顏色：句子裡有講衣服顏色才填，照句子的說法填。只有人可以用顏色。
   - 開始時間、結束時間：照句子的意思寫成文字，例如 時:分:秒。句子沒講就空著，並在說明寫「句子沒講時間」。句子完全沒講時間時，系統預設查整段影片（〈YYYY-MM-DD HH:MM:SS〉到〈HH:MM:SS〉，與上方展示時間相同）；這不算要反問。這類句子的預期結果照整段範圍判斷，另記為「整段預設（實作前不計分）」。只寫一半或寫錯的時間仍照原樣填。故意寫錯的時間也照原樣填，頁面只提醒、不會擋。
   - 鏡頭或區域：照句子寫。要系統直接查的題目，鏡頭請用目錄裡的代號（例如目錄裡的 CAM_ 開頭名稱）或目錄寫明「正式」的中文說法；口語、說不清楚是哪一台的說法，適合拿來出「系統應該反問」的題目。房間、走廊這類區域名稱目前沒有正式目錄，只能用在反問題。
   - 系統該反問嗎、預期結果：從下拉選。選了之後頁面會再問一個「原因」，照你的判斷選。
   - 加題（第 9–12 列）：預期結果選「找得到」或「找不到」時，頁面會列出鏡頭，逐台看附圖勾「看得到／看不到／看不清」。只看椅子、桌子這類不會動的東西。
3. 填完按「匯出回覆 CSV」，把下載的檔案放進 RETURN/，整包交回。
- 不會自動儲存，關頁前先匯出。要接著填，按「匯入 CSV 接續填寫」，選你上次匯出的檔。
- 請不要用 Excel 或 Numbers 開 CSV 再存檔，日期和時間可能會被改掉。
- （給收件者核對用）python3 tools/verify_pack.py --manifest-sha256 <MANIFEST.json 的 SHA-256> [--returned-csv RETURN/情境_yyin_YYYY-MM-DD.csv]

不要改
不要改編號、templates、DATA.json、data.js、catalog、圖片、maintainers、tools 或 MANIFEST.json。
不要去找劇本、人物設定、系統輸出或其他人的題目。
看不到的東西就寫看不到或不確定，不要推測人物去了哪裡、是不是同一個人、能不能走過去。
本包不會自動核准任何東西；你的判斷會由 Claude 轉換格式，並由另一個 session 逐列複核。
```

註：D76 規定說明檔要有「工作內容／要提交項目／操作／不要改」四段，所以比原指示的三段多一段「不要改」。

---

## 3. 表單規格（START_HERE.html＋app.js）

### 3.1 匯出格式（必須與 importer 完全一致）

- 欄名與順序：逐字等於 `build_team_review_pack.TEXT_COLUMNS`（staging 4c96140）：
  `編號,使用者會說的話,想找什麼(人/車/相機),顏色,開始時間,結束時間,鏡頭或區域,系統該反問嗎(是/否),預期結果(找得到/找不到/不支援/超出時間/反問),備註`
  打包腳本從 builder 匯入 `TEXT_COLUMNS` 寫進 DATA.json，表單從 DATA.json 讀，不手打。
- 編碼：UTF-8 加 BOM（importer 用 `utf-8-sig` 解碼；builder 也寫 BOM）。
- 換行：CRLF（r004 v2 表單同做法；importer 的 `csv` 模組 LF／CRLF 都接受，自測要實際驗證）。
- 引號：RFC 4180（含逗號、雙引號、換行的值加雙引號、內部雙引號重複）。
- 列：固定 14 列、依編號排序、一列都不能少（importer 第 57、69 行會整包拒收）。
- 不做任何改寫：不轉全形半形、不做 Unicode 正規化、不自動補日期；只去掉每格頭尾空白。因為 D75 要求 annotation 的 `text` 與 CSV 原文**逐字相同**（importer 第 102 行），匯出的 CSV 就是原文來源。
- **不要**用 v2 表單的「前面加 ' 中和公式」做法：那會讓 CSV 原文多一個 `'`，和使用者原話不同。改成直接擋（見 3.3）。

### 3.2 十欄的輸入控制

| 欄 | 控制 | 規則 |
|---|---|---|
| 1 編號 | 預填 Q0001–Q0014，唯讀顯示 | importer 鎖定欄（`LOCKED`＝第 1 欄） |
| 2 使用者會說的話 | 單行文字框（textarea 但擋換行），上限 200 字 | 第 1–12 列必填；不能有換行；提示「不要寫真實姓名、電話等個資」 |
| 3 想找什麼(人/車/相機) | 下拉：人／車／相機；選人後第二層「追這個人／只問哪些鏡頭有人」 | 必填；第二層寫入備註 `目標=追人`／`目標=只問鏡頭`；非人記 `目標=不適用`；第 9–12 列只能選「相機」（加題限定） |
| 4 顏色 | 文字框（不是下拉，因為要照句子原話） | 選填；第 3 欄不是「人」卻填了顏色時跳提醒：「顏色只用在人；這題應該是『不支援／條件不支援』」，不擋 |
| 5 開始時間、6 結束時間 | `<input type="text">`，**禁止** date／time picker | 不做合法性檢查（時間無效題是刻意的）；只提醒：純數字像試算表日期序號（例如 5 位數帶小數）、空白但說明沒寫原因 |
| 7 鏡頭或區域 | 文字框＋`datalist` 建議（目錄的 camera_id 與中文說法） | 選填；不強迫對應目錄（含糊說法是反問題的素材） |
| 8 系統該反問嗎(是/否) | 下拉：是／否 | 必填 |
| 9 預期結果 | 下拉＋第二層「原因」下拉（見 3.4） | 必填；選定後自動寫入備註的關鍵字 |
| 10 備註 | 由表單組字：`關鍵字=…｜目標=…｜鏡頭=…｜說明=…`；組員只編「說明」 | 格式見 3.5 |

填寫順序：第 2 欄沒填之前，第 3–10 欄鎖住（先寫句子再判斷，降低先選答案再湊句子的偏誤）。

### 3.3 防呆與提示

- 擋（不能匯出，顯示紅字）：任何可填格開頭是 `= + - @`、Tab、CR；第 2 欄含換行；第 1–12 列必填缺漏時只能匯出成 `_INCOMPLETE`。
- 一致性（擋）：預期結果＝反問 但 系統該反問＝否（指南 §6：需要澄清時「系統該反問填是」）。
- 一致性（提醒、可留說明後放行）：系統該反問＝是 但預期結果不是反問；第 3 欄＝人 且預期結果＝找得到／找不到（人物題沒有畫面可依據，見 D-3）；第 9–12 列鏡頭勾選有「看不清」（這列會變成待補）；必填說明沒寫。
- 說明必填的情況：時間欄空白、預期結果是不支援／反問／留空類、任何「看不清」、組員勾「我不確定」。
- 「我不確定」核取方塊：勾了之後說明開頭自動加 `UNKNOWN：`，提示這列不會當正式答案。
- 題型進度表（右側）：即時統計第 1–8 列的「預期結果＋原因」落在 §4 配額的哪一格、第 1–12 列 Q1 題的分布（排除 class=person 與整段預設題）；A 格人物句另列「A（人物，只計 Q3）」，不補 A 格相機／車的2題配額，PACK_NOTES 記錄此限制。完全沒寫時間的 PARSED 題不計 A／B 名額，另列「整段預設（實作前不計分）」；未滿的格子顯示灰色，但**不**規定哪一列要寫哪一型。
- 欄位「?」說明：每欄一句白話，摘自指南 §1、§3–§6（不放例句）。
- 匯入接續：讀先前匯出的 CSV，核對表頭逐字相同、編號 Q0001–Q0014 一個不少，否則拒絕並說明；依 q1q3-note-format.v2 解析備註並回填目標第二層及其他控制項；缺目標或與第 3 欄矛盾則拒絕／列 _INCOMPLETE，不從句子猜回。
- `beforeunload` 提醒「尚未匯出」。不依賴 localStorage（若做草稿暫存，所有讀寫包 try/catch，失效時照常運作）。
- 匯出檔名：`情境_yyin_<日期>.csv`；有缺漏或配額未滿 → `情境_yyin_<日期>_INCOMPLETE.csv`。

### 3.4 「預期結果」兩層下拉（依指南 §6；最終清單依 D-1）

| 第一層（寫入第 9 欄） | 第二層原因（寫入備註「關鍵字」） | 對照（給維護者，不顯示給組員） |
|---|---|---|
| 找得到 | 完整找到 | Q1 READY |
| 找不到 | 完整未找到 | Q1 NO_MATCH |
| 不支援 | 類別不支援／條件不支援／身分不支援／需私有真值／跨run身分 | Q3 UNSUPPORTED_CLASS／UNSUPPORTED_CONDITION；後三者的 Q3 status 對照 UNKNOWN（指南沒寫，見 §5 卡點） |
| 超出時間 | 完全超時 | Q1 OUT_OF_RANGE |
| 反問 | 需要澄清／單run範圍 | Q3 NEEDS_CLARIFICATION |
| （留空） | 部分涵蓋（時間部分相交）／時間無效／解析失敗／只測解析（只在 D-1 選 (a) 時出現） | Q1 PARTIAL／Q3 TIME_EXPRESSION_INVALID／Q3 PARSE_FAILED／Q3 PARSED 但不判斷 Q1／Q2 結果 |

- 不給組員「資料不足」與「缺格、尚未推論」類的「部分涵蓋」：組員不知道索引涵蓋範圍（審查 note 3）。這兩種由維護者另標，不在本包。
- 第一層選「（留空）」時第 9 欄匯出空字串。依目前 importer，這列會是 INVALID；D-1 修好後才會進正式資料。表單在選項旁標「目前會列待補」。

### 3.5 備註的固定格式（給 Claude 機械解析）

```
關鍵字=<第二層原因>｜目標=<追人|只問鏡頭|不適用>｜鏡頭=<CAM_ID>:看得到,<CAM_ID>:看不到,<CAM_ID>:看不清｜說明=<自由文字>
```

- 格式升為 `q1q3-note-format.v2`。目標欄必填：人只能選追人／只問鏡頭，非人固定不適用。分隔用全形「｜」；`說明=` 永遠放最後，只解析它之前的固定段，所以說明裡出現「｜」不影響。值中的半形 `|` 在上方表示三選一，不是匯出分隔符。
- `鏡頭=` 只在第 3 欄＝相機或車、且預期結果＝找得到／找不到時出現；列出的鏡頭＝句子指定的鏡頭，沒指定就是目錄全部 8 台。
- 沒有鏡頭段時省略整段，例如 `關鍵字=需要澄清｜目標=不適用｜說明=…`。
- PACK_NOTES.md 寫同一份格式與版本號 `q1q3-note-format.v2`。

---

## 4. 題組要求

### 4.1 Q3 基本題組（Q0001–Q0008，8 題）的覆蓋配額（建議＝D-4 (a)）

| 格 | 題數 | 組員看到的說法 | 對應 Q3 status／intent | 說明 |
|---|---|---|---|---|
| A | 2 | 系統應該直接查：問哪些鏡頭拍到某樣東西 | PARSED／FIND_CAMERAS（Q1 request） | 完全沒寫時間的 PARSED 題不計此格名額。至少 2 題 class=相機或車且有明寫時間，才同時計 Q1；class=person 的句子只計 Q3，不能取代這 2 題，不計 Q1 |
| B | 2 | 系統應該直接查：找一個人（句子要有追蹤的意思） | PARSED／FIND_PERSON（Q2 request） | 至少 1 題帶顏色；完全沒寫時間的 PARSED 題不計此格名額，因此本格 2 題須有明寫時間。依 D92-A：第 3 欄＝人**不等於** FIND_PERSON；只有「紅色的人」「那個人」而沒有追蹤意思的句子，依查找規則判 Q1（FIND_CAMERAS，class＝person），進度表另列「A（人物，只計 Q3）」；不補 A 格相機／車配額，也不計 Q1。這類句子沒有畫面依據，只做 Q3 解析（關鍵字＝只測解析）。 |
| C | 2 | 系統應該反問 | NEEDS_CLARIFICATION | 2 題原因不同（例如指代不明、鏡頭說法含糊、範圍跨好幾段影片）。不能拿「沒講日期」或「完全沒講時間」當原因（D-5：日期取目前影片、完全沒講時間取 A4 整段，D86-2）；可用的原因：指代不明、鏡頭說法含糊、要求跨 run、沒有選定影片／沒有時鐘 |
| D | 1 | 系統不支援這種東西 | UNSUPPORTED_CLASS | 類別不在詞表 |
| E | 1 | 系統不支援這種條件 | UNSUPPORTED_CONDITION | 例如顏色用在人以外的東西 |

全體附加條件：計入 A、B 的 4 題 PARSED 都須有明寫時間；整段預設題另列「整段預設（實作前不計分）」，不占 A／B 名額，也不補 Q1 名額。至少 1 題寫了完整日期與時區；至少 1 題寫了鏡頭條件（用目錄代號）。這些是比例條件，不指定哪一列。

B 格（人物題）怎麼填「預期結果」：
- D-1 選 (a)：時段在影片內的人物題，填「（留空）＋只測解析」。
- D-1 未修好：只能寫成時段完全落在影片外，填「超出時間＋完全超時」；否則會變成 INVALID。設計上接受這個偏誤（時間解析的難度不變），PACK_NOTES 要記錄。

理由：
1. 8 題太少，不能六種 status 都放；先放 importer **現在**就能收的四種 status（PARSED、NEEDS_CLARIFICATION、UNSUPPORTED_CLASS、UNSUPPORTED_CONDITION），回收當天就能變成正式資料，不必等 Codex。
2. PARSED 放 4 題（佔一半），因為 Q3 欄位正確率（intent、class、color、time_us、camera、region）只在 PARSED 題計算（`q3_parse_eval.py` 第 82 行）；Q1、Q2 各 2 題，兩種 intent 都有分母。
3. 拒答 4 題（C、D、E），拒答的精確率與召回率才有分母；C 給 2 題，因為「反問」是 D73 第一版最常見的保守行為（缺時鐘、多 run）。
4. TIME_EXPRESSION_INVALID、PARSE_FAILED 目前結構上進不了正式資料（F2），放進 8 題只會讓 8 題裡有 2 題作廢；改放到選填的 Q0013–Q0014 先收集，importer 修好後同一份 CSV 重新匯入即可，不必再找組員。
5. 每格的句子都由組員寫，配額只規定結果的種類；表單用進度表顯示，不鎖定哪列要寫哪型，降低誘導。

### 4.2 Q1 題（至少 6 題＝A 格至少 2 題相機／車＋Q0009–Q0012 加題 4 題）

class=person 的 A 格句子只計 Q3，不計 Q1；完全沒寫時間的 PARSED 題另列整段預設，不計本節正式題數。固定14列不增列；配額不夠就 _INCOMPLETE，不以未計分列補足。

**D97 第7點：A格車題也計入Q1。** 可出題鏡頭僅限 CQ-26 #316 已確認空場景看得到車的清單；看不到車的鏡頭不出車輛題。#316 尚未交件時清單為 UNKNOWN，交件時引用其 PR／head／清單 pin，留待 CQ-27 #317 打包前補齊；不得由鏡頭名稱、catalog 或人物設定猜車輛可見性。這不把空場景判斷升為正式影片的逐格精確答案。

| 預期結果 | 至少 | 依據 |
|---|---|---|
| 找得到（完整找到） | 2 | 空場景畫面上看得到椅子或桌子的鏡頭 |
| 找不到（完整未找到） | 1 | 指定的鏡頭裡都看不到 |
| 超出時間（完全超時） | 1 | 時段完全落在影片外 |
| （留空）部分涵蓋（時間部分相交） | 1 | 時段一半在影片內、一半在外。D-1 修好前是待補 |

- 加題第 3 欄限「相機」，物件限椅子、桌子（D-3 (a)）。
- 題數理由：Q1 的正式主題庫是 #138 的 SYNTHETIC 題（至少 40 題），這 6 題是真實 r004 上的小規模核對，數量和驗收 AC2「至少 3 句不同查詢」相符；四種結果各至少 1 題，加總後還有 1 題由組員自由分配。

### 4.3 防偏誤規則（寫進 README 與 PACK_NOTES）

1. 獨立出題：組員一人完成；不參考 #199 候選、#89／#138 issue 例句、指南表格措辭、其他人的題目。
2. 不看系統：不開 workbench、不看 baseline 輸出、Q3 parser 或 LLM 結果。打包者也不得把任何系統輸出放進包。
3. 不看 GT／劇本：不提供、不提示人物設定、路線、到達時間；指南 §7 的「紅衣與藍衣」這類設計資訊不放進組員看得到的檔案。指南原檔含候選顏色詞與 D80 題目設計資訊，**不放進組員包**（G1）：PACK_NOTES 只記 #269 合併 SHA 與指南檔案 SHA-256，不記路徑或檔名（P2-4 採方案 ii，保持全包禁止指南檔名的掃描不變）；若維護者一定要附，只能附刪去 §5、§7 與題目設計資訊的刪節版，並在 PACK_NOTES 記刪節規則與 SHA-256。
4. 先寫句子再判斷（表單鎖定順序）。
5. 判斷只依包內材料（目錄、時間範圍、空場景圖）；看不清就填看不清或「我不確定」，那一列變待補，不由 Claude 補。
6. Claude 轉換時：只依組員填的欄位與備註；不跑 parser、不看 baseline 結果；轉換後由另一個 session 逐列複核（8–14 列，全數複核）。
7. 配額湊不滿就照實交 `_INCOMPLETE` 並說明，不硬寫不自然的句子。

---

## 5. Claude 端轉換流程（D75）與目前卡點

| 步驟 | 做什麼 | 產物（LOCAL） | 目前卡點 |
|---|---|---|---|
| 1 收件 | 收 ZIP，以標準庫 `zipfile` 解到新的 `${AMIDST_ARTIFACTS}/q1q3-authoring-yyin-v1_.../`；無 UTF-8 bit 11 的回交 ZIP 可用 cp950 試解檔名，再對照 MANIFEST，仍不一致就停。記錄回交 CSV SHA-256，跑 `python3 tools/verify_pack.py --manifest-sha256 … --returned-csv RETURN/情境_yyin_….csv`。只有 template 缺件時可為 VALID_WITH_WARNINGS／exit0；匯入前依原包 MANIFEST hash 補回並記錄，再驗至 VERIFIED；其他錯誤 INVALID／exit1。D98-1既有yyin補件仍依#347等指定補交，不由本設計改寫歷史INVALID或自動補件 | 回交 CSV、verify 輸出、缺件／補件 hash 紀錄 | 無 |
| 2 結構試匯入 | 不帶 annotations 跑 importer（輸出到 `LOCAL:預設 artifacts 目錄/<新目錄>`、registry 用 LOCAL 暫存檔）；預期已填列全是 `PRECISE_HUMAN_ANNOTATION_REQUIRED`，空列是 `TEXT_FIELDS_MISSING_OR_INVALID`，**不得**出現 `CSV_COLUMNS_INVALID`／`LOCKED_FIELD_CHANGED` | 試匯入目錄（看完刪除） | 無 |
| 3 轉換 | Claude 依 `q1q3-conversion-rules.v1` 寫 `annotations_v1.jsonl`：每列 `{id, text, q3?, q1?}`；另寫 `conversion_receipt.json`（來源 CSV SHA-256、MANIFEST SHA-256、規則版本、各凍結輸入的 hash、model／effort） | annotations、conversion receipt | 見 5.1 |
| 4 正式匯入 | `import_team_review_pack.py --annotations annotations_v1.jsonl --text-csv RETURN/…` | `queries_v1.jsonl`、`cases_v1.jsonl`、`invalid_rows.jsonl`、`receipt.json`；registry 一列 | 留空列全數 INVALID（缺口 1／D-1）；`query_binding` 被丟掉（F3／D-2） |
| 5 複核 | 另一個 session（Opus high）逐列核對：`text` 逐字相同、`expected_llm_output` 9 鍵與 schema（kit 994d34c 的 `PinnedSchemas`）、status 與 CSV 第 9 欄＋關鍵字的對照、詞語欄都是原文片段、request 通過 schema | 複核紀錄 | 無 |
| 6 評分 | Q3：`scripts/eval_q3_parse.py --queries queries_v1.jsonl --clocks <r004 clock catalog> --dataset-receipt receipt.json …`；Q1：`scripts/eval_q1_query.py --cases cases_v1.jsonl --dataset-receipt receipt.json …` | 評分報告 | 要等 CX-8 正式 baseline 輸出（預測檔）；r004 clock catalog（#238 `001cbcf`，已發布）；Q1 每題都會因缺 `query_binding` 判 INVALID（D-2） |
| 7 紀錄 | 結果紀錄（AGENTS 模板）、registry、進度表 | — | 無 |

### 5.1 轉換規則要點與各欄卡點

Q3（每個已填列都做；`q3.category` 由 Claude 依列號填 `Q3_MIN`／`Q1_EXTRA`／`OPTIONAL`）：

| 欄位 | 來源 | 卡點 |
|---|---|---|
| `text` | CSV 第 2 欄原字串（含頭尾空白狀態與 CSV 一致） | 無 |
| `expected_llm_output.schema_version` | 固定 `q-demo.q3-llm-output.v1` | `q-demo.q3-llm-output.v1` 是否也隨 D92 補升版：**UNKNOWN**，打包前查契約定案版本 |
| `intent` | 第 3 欄是目標類別，不是意圖（D92-A，[D92-2](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434464633)）：句子有追蹤動詞（例如「去了哪裡」「跟著」）→FIND_PERSON；人但無追蹤動詞→FIND_CAMERAS（class＝person）；車／相機→FIND_CAMERAS；不支援類→UNSUPPORTED。表單第二層選項「要系統追這個人／只問哪些鏡頭有人」作為判斷依據 | 身分不支援／需私有真值／跨run身分 的 intent 雖可定為 UNSUPPORTED，但最終 `expected_status` 該用哪個值 **UNKNOWN**（指南只寫「不支援」）。在 Codex 或使用者補規則前，這類列標待補 |
| `class_term`、`color_term`、`camera_terms`、`region_terms` | 原句片段；第 4、7 欄只當核對 | 第 4 欄的顏色若不是原句片段，列為矛盾、待補 |
| `time_literal` | 原句裡的時間片段，`{start, end, date}`；第 5、6 欄核對意思 | 無 |
| `time_literal`（D86-2 補充） | 句子完全沒寫時間且已選 A4 → `time_literal` 為 null，`expected_structured_query.time` 取 A4 整段宣告範圍 `[t0, t0+50 s)`，標「整段 run 預設」，annotation／conversion receipt 記 `d86_2_default_range: true`。這類題與舊規則題分開計（#269：新增預設範圍題與舊題分開、正式評分題須明寫時間）。D86 parser／wire 尚未實作：這類題在實作前只收集、不計正式分數 | 實作前不計分 |
| `needs_clarification`、`clarification_question` | 第 8 欄；問句由 Claude 依說明寫一句中性反問 | `clarification_question` 是自由文字，評分器不比對 literal 以外的欄（`LITERALS` 不含它），影響小 |
| `expected_status` | 第 9 欄＋關鍵字，依 3.4 對照 | 留空類（時間無效、解析失敗、只測解析）被 importer 擋（D-1） |
| `expected_structured_query`（PARSED 才有） | Q1 request（`q-demo.q1-request.v1`，11 個必填鍵）或 Q2 request（`q-demo.q2-request.v1`：`schema_version, session_ref, scene_id, run_ids, time, seed, switch_mode, parameter_set_id`） | `class_label` 要正式 alias 表（#109，OPEN）；顏色要正式 color_vocabulary（#114／#118）；`time` 取 #238 `001cbcf` 已發布的 r004 clock mapping；`camera_ids` 取 D84 凍結 catalog；`region_ids` 要 #116（目前一律不做 PARSED）；`scene_id`、`run_ids`、`session_ref`、`page_size`、`query_min_score`、`parameter_set_id` 要正式評估 context（#118 的 parameter_set）；Q2 的 `seed`、`switch_mode` 由組員句子推不出，**UNKNOWN**，需契約說明「評估用 Q2 request 的 seed 怎麼由 Q3 PARSED 決定」 |

Q1（第 3 欄＝車／相機、Q3 為 PARSED 的列）：

| 欄位 | 來源 | 卡點 |
|---|---|---|
| `request` | 同上的 Q1 request | 同上 |
| `index_ref` | 正式 r004 索引 ID（#118） | #118 OPEN |
| `expected_response_core` 形狀 | 依 [D92 補](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434474506)（#260-B）：Q1／Q2／Q3 回應升 v2，`resolved_scope` 加必填 `time_range_source`；轉換時 expected core 帶 v2 形狀（明寫時間 vs 整段預設）。D80 query preimage 不改，D-2／`query_binding` 不受影響 | v2 schema 檔實際欄位打包前核對 |
| `expected_response_core.status` | 找得到→READY、找不到→NO_MATCH、超出時間→OUT_OF_RANGE、留空＋部分涵蓋→PARTIAL | PARTIAL 被 importer 擋（D-1） |
| `results`／`no_match_cameras` | 備註 `鏡頭=` 段：看得到→results；看不到→no_match_cameras；任一「看不清」→整列待補 | READY 的 `matched_segments`：依「空場景看得到的靜態家具整段可見」規則，由 Claude 把查詢時段對到正式索引的取樣格線，得出單一片段、`matched_frames = evaluated_frames = 時段內取樣格數`。這是**轉換假設**，沒有考慮人物遮擋；所以 Q1 的 `segments` 指標只當參考，主要看鏡頭層 TP／FP／FN。取樣格線來自 #118 parameter_set／index manifest 的 `index_interval_us` |
| `coverage`、`not_evaluated_cameras` | 正式索引 manifest 的推論範圍（系統中繼資料，不是預測結果） | 是否允許用索引中繼資料寫 expected coverage：**需要決定**（併在 D-2 的 Codex 指派第 4 點請 Codex 回覆契約意見；Claude 預設為可以，因為它不含偵測結果） |
| OUT_OF_RANGE 的 core 形狀 | 契約 §6.3 | `no_match_cameras`／`not_evaluated_cameras` 該不該列鏡頭：**UNKNOWN**（評分器只要求不帶 results）。請 Codex 指明（指派第 4 點） |
| `query_binding` | D-2 | importer 不帶過去；評分器全部 `QUERY_BINDING_CONTEXT_MISSING` |

---

## 6. 給使用者的決定（AskUserQuestion 用）

每題第一個選項是建議。

### D-1 「預期結果」留空會被判 INVALID（缺口 1）

> **D80 已決定：採 (a)**（[D80](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6399200757)）。以下選項保留為決策紀錄。

- **(a) 建議：importer 改成「留空要配固定關鍵字，以 Claude 精確標註為準」。** 第 9 欄留空時，備註開頭必須是封閉清單關鍵字之一（部分涵蓋、時間無效、解析失敗、只測解析、資料不足），而且要有精確標註才收；importer 再核對 CSV 第 9 欄／關鍵字和標註 status 是否相符，不符就 INVALID。欄名不變，指南 §6 補「時間部分相交」與「只測解析」。
  - 優點：欄名與已發的範本不變；四種 status 都能成為正式答案；人物題可以出時段內的版本；同一份回交 CSV 修好後可直接重匯。
  - 缺點：要 Codex 改 importer、補測試；關鍵字比對要嚴格（表單已保證格式）。
- **(b) 第 9 欄加第六個值（例如「其他（見備註）」）。**
  - 優點：語意最直白。
  - 缺點：欄名本身含五個值，要改 `TEXT_COLUMNS`，舊範本與 v0-pilot 包全部不相容；指南也要改。
- **(c) 先不改，本輪不收這四種 status。**
  - 優點：不用等 Codex。
  - 缺點：Q1 PARTIAL、Q3 TIME_EXPRESSION_INVALID／PARSE_FAILED 第一版沒有分母；人物題只能寫成超出時間，題目分布偏。
- 需要 Codex：(a)、(b) 都要。

### D-2 `query_binding` 的可信來源（缺口 2）

> **D80 已決定：採 (a)**（[D80](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6399200757)）。以下選項保留為決策紀錄。

- **(a) 建議：由評估端（Claude）在轉換時凍結，importer 原樣帶進 `cases_v1`。** `request_sha256` 由 Claude 依評分器定義算（request 去掉 origin 後的 canonical SHA-256）；`query_sha256` 由 Claude 依契約 §2.2 的 query_id preimage 自行計算，不呼叫受評的 Q1 模組。Codex 改 importer：驗證並保留 `q1.query_binding`（`request_sha256` 重算相符、兩值皆 64 位小寫十六進位），並在契約寫明 preimage 的精確欄位。
  - 優點：和預測完全獨立，評分器的「預測對帳」才有意義；receipt pin 不會壞。
  - 缺點：要 Codex 改 importer，還要把 preimage 寫到可獨立重算的程度（目前只寫「由正規化請求的 content_sha256 導出」，牽涉 clock mapping 等 pin，精確欄位 UNKNOWN）。
- **(b) 用 Q1 模組的「只正規化、不查詢」dry-run 結果凍結。**
  - 優點：Claude 不用重寫正規化邏輯。
  - 缺點：和受評系統同一來源，正規化有錯時兩邊一起錯，對帳失去意義（#224 審查已提醒）；仍要 importer 帶欄位。
- **(c) 評分器把 `query_sha256` 改成選填，只比 `request_sha256` 與 `normalized_condition`／`run_ids`。**
  - 優點：改動最小。
  - 缺點：少一層完整性檢查；仍要 importer 帶 `request_sha256`，或由評分器自己重算。
- 需要 Codex：三案都要（importer 和／或評分器）。

### D-3 組員沒有影片時，「預期結果」憑什麼填；範例.csv 怎麼做（缺口 3）

> **D80 已決定：採 (a)**（[D80](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6399200757)）。以下選項保留為決策紀錄。

- **(a) 建議：分層。Q3 不需要畫面；Q1 的找得到／找不到只出靜態家具（椅子、桌子），依包內附的 r004 八台空場景圖判斷；人物、車的 Q1 題等 r004 正式渲染（CX-7）後另出第二包。範例.csv 改成「填法示意」：每欄用 〈…〉 描述要填什麼（例如〈一句問某物件在哪些鏡頭的話〉），下拉欄放真實可選值，不放任何真句子。**
  - 優點：現在就能出包；空場景圖組員在 v2 包已看過，不含人物、事件或 GT；一列也不用猜；範例.csv 補上 #147 第 5 點又不違反 D70。
  - 缺點：Q1 第一版沒有人物、車；靜態圖是 preview 渲染，打包前要核對 v2 包 catalog SHA＝D84 凍結值（`3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`）；人物遮擋沒有建模，segments 指標只當參考。
- **(b) 等 CX-7 正式渲染後才出整包，附各鏡頭影片或關鍵格。**
  - 優點：人、車、家具都能出，答案最完整。
  - 缺點：卡在關鍵路徑最後段；影片是大檔，組員工作量大；8 題 Q3 也被拖延。
- **(c) 組員只出題，不判斷找得到／找不到；Q1 標準答案改由使用者或另一位組員看畫面標。**
  - 優點：組員負擔最小。
  - 缺點：違反「答案由出題者獨立判斷」的單一來源；需要第二輪人力；第 9 欄仍要填值（受 D-1 影響）。
- (a) r004 camera catalog 已由 D84 凍結，run／clock mapping 已由 #238 `001cbcf` 發布；打包時核對 pins，不再請 Codex 發布。(b) 仍要 CX-7。

### D-4 Q3 最小 8 題的覆蓋配額；Q1 題數（缺口 4）

> **D80 已決定：採 (a)**（[D80](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6399200757)）。以下選項保留為決策紀錄。

- **(a) 建議：PARSED 4（FIND_CAMERAS 2、FIND_PERSON 2）、NEEDS_CLARIFICATION 2、UNSUPPORTED_CLASS 1、UNSUPPORTED_CONDITION 1；時間無效、解析失敗放 2 列選填；Q1 共 6 題（找得到≥2、找不到≥1、超出時間≥1、時間部分相交≥1）。**
  - 優點：四種 status 回收當天就能進正式資料；兩種 intent 都有分母；拒答有分母；選填列等 importer 修好可直接重匯。
  - 缺點：第一版 Q3 沒有 TIME_EXPRESSION_INVALID／PARSE_FAILED 的必做題。
- **(b) 等 importer 修好後，8 題六種 status 各至少 1（PARSED 2：Q1、Q2 各 1，其他各 1，自由 1）。**
  - 優點：status 全覆蓋。
  - 缺點：要等 D-1 的 Codex 修正；PARSED 只有 2 題，欄位正確率的分母太小。
- **(c) 不訂配額，只要求 Q1、Q2 至少各 1 題。**
  - 優點：組員最自由。
  - 缺點：可能 8 題全是 PARSED，拒答召回率沒有分母，無法比較 parser。
- 需要 Codex：(a) 不需要（D-1 只影響選填列）；(b) 依賴 D-1。

### D-5（附加，設計時發現）Q3 題目的情境 run 與「沒講日期」的規則

> **已由 D80-5 決定（日期，採 (a)）＋[D86-2](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6417558930) 擴充（完全沒講時間 → 整段已選 run）**；指南 §6 由 #269 修訂（head `e014be3` 僅供對照，合併前 OPEN；正式打包引用時必須回填 #269 合併 SHA，D97 主包框架先引用交件 head 的規則見 §0）。以下選項保留為決策紀錄，不再待決。

- **(a) 建議：固定情境為「工作台已選定 A4」（`context.run_ids=[A4]`），沒講日期時照契約 §3.2 取該 run 的展示日期（算 PARSED）；指南 §6「缺日期 → 反問」限縮成「沒有選定 run 或沒有 clock mapping 時」。**
  - 優點：和契約一致；組員有明確情境；時間題能成為 PARSED。
  - 缺點：要改指南一句（Codex）；只測一個 run 的情境。
- **(b) 不設情境，所有沒講日期的題都算反問。**
  - 優點：照指南現行文字。
  - 缺點：和契約 §3.2 衝突；大部分口語時間題會變成反問，PARSED 很難湊滿。
- 需要 Codex：(a) 改指南；(b) 不需要。A4 的 `run_id`／`clock_mapping` 已由 #238 發布（merge `001cbcf`）。

### D-6（附加，低風險）包的 MANIFEST 由誰產

> **D80 已決定：採 (a)**（[D80](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6399200757)）。以下選項保留為決策紀錄。

- **(a) 建議：Claude 打包時自建 `team-review-pack.v1` 相容 MANIFEST（`samples: []`、表頭-only 審查表），用 importer 實測接受。**
  - 優點：不用等 Codex；CL-7 本來就是 Claude 的工作。
  - 缺點：MANIFEST 不是 builder 產的，要靠自測證明相容。
- **(b) 請 Codex 給 builder 加 `--text-only` 模式。**
  - 優點：產包程式單一來源。
  - 缺點：多一個 Codex 依賴與複核輪次。

### 6.1 Codex 指派草稿（D-1 (a)、D-2 (a)、D-5 (a) 都採建議時；可直接貼上，同步貼 GitHub #147）

```
@Codex Q1／Q3 組員出題包（驗收計畫 T-2）需要下列修正。依據：staging 4c96140（含 #221、#224、#226）、D73、D75、D76，以及使用者對 D-1／D-2／D-5 的選擇（〈填入 AskUserQuestion 結果的留言連結〉）。
每項從 codex/q1q5-staging 開分支，一個修正 PR（base codex/q1q5-staging，Draft），只用 merge commit，不 rebase、不 force。Claude 複核後才合。PR 說明與 #147 留言用「實際產出 / Actual output」模板。

1. importer：「預期結果」留空的處理（scripts/import_team_review_pack.py 約第 99–101 行）
   - 第 9 欄可以是五個值，或空字串；空字串只在「備註開頭是 `關鍵字=<X>`（後面接全形「｜」或直接結束）、X ∈ {部分涵蓋, 時間無效, 解析失敗, 只測解析, 資料不足}」而且有精確標註時才收。其他空白維持 TEXT_FIELDS_MISSING_OR_INVALID。
   - 新增 CSV↔標註一致性檢查（封閉對照表）：找得到→q1 READY；找不到→q1 NO_MATCH；超出時間→q1 OUT_OF_RANGE；反問→q3 NEEDS_CLARIFICATION；不支援→q3 UNSUPPORTED_CLASS 或 UNSUPPORTED_CONDITION；留空＋部分涵蓋→q1 PARTIAL；留空＋資料不足→q1 UNKNOWN；留空＋時間無效→q3 TIME_EXPRESSION_INVALID；留空＋解析失敗→q3 PARSE_FAILED；留空＋只測解析→q3 PARSED 且不得有 q1；class=person（含 A 格 FIND_CAMERAS）只計 Q3，不計 Q1，進度表排除；整段預設 PARSED 不計 A／B 配額與 Q1 正式題數。不符時 INVALID，reason `CSV_ANNOTATION_STATUS_MISMATCH`。
   - 備註格式依 q1q3-note-format.v2：`關鍵字=…｜目標=…｜鏡頭=…｜說明=…`（全形「｜」，說明在最後）。
   - 測試：每個關鍵字各一個成功案例、一個矛盾案例；無關鍵字的空白仍 INVALID；舊的五值行為不變。
2. importer：保留 q1.query_binding
   - annotation 的 q1 若有 `query_binding: {request_sha256, query_sha256}`，兩值必須是 64 位小寫十六進位，且 request_sha256 == sha256(canonical(request 去掉 origin))（與 q1_query_eval.py 第 181–184 行同定義），才原樣寫進 cases_v1；缺或不符時該列 INVALID `QUERY_BINDING_INVALID`。importer 不得自己產生 query_sha256。
   - receipt 增記 `query_binding_source: EVALUATION_OWNER_PER_D-2`。測試涵蓋成功、缺、request 不符、格式錯。
3. 契約：query_sha256 的精確 preimage
   - 在 Q1_Q2_FIRST_DEMO_V1.md §2.2 寫明 Q1 query_id／query_sha256 preimage 的完整欄位（含哪些 pin：clock_mapping_sha256、index、parameter_set 等），讓評估端不呼叫 Q1 模組也能獨立重算。只寫規則，不改既有核准值；若 preimage 依賴執行時才知道的值，請列出並在 §14 加待決項。
4. 契約／評分說明：兩個轉換時要用的形狀
   - OUT_OF_RANGE、UNSUPPORTED_* 的 expected_response_core 中，no_match_cameras／not_evaluated_cameras 應為空或列哪些鏡頭（§6.3）。
   - expected coverage／not_evaluated_cameras 可否取自正式索引 manifest 的推論範圍（中繼資料，不含偵測結果）。
   - 「身分不支援／需私有真值／跨run身分」對應的 Q3 expected_status。
   - 評估用 Q2 request 的 seed／switch_mode 如何由 Q3 PARSED 決定。
   用留言回覆即可；需要改契約的另開 PR。
5. 指南（docs/evaluation/Q1Q3_QUESTION_AUTHORING_GUIDE.md）跟進 #221 複核 note 1–4：
   §1 加「依當次包的 README 與 RETURN/ 指定檔名交回」；§6「部分涵蓋」列明寫「時間部分相交」；§6 加「只測解析」一列（留空＋只測解析＝Q3 PARSED，不判斷 Q1／Q2 結果）；寫明「組員依自己看到的畫面填找得到／找不到，涵蓋不足（資料不足、缺格）由維護者另標」；（§6「缺日期 → 反問」限縮與「完全沒講時間→整段 run」已由 #269 處理，不再列入本指派）；§8 待補列一筆本次 importer 後續。
6. 資料核對（不是程式；run／clock／catalog 已發布，不再請 Codex 發布）：核對 #238 合併 SHA（`001cbcf`）的 A4 run 註冊、clock 宣告（`source_duration_us` 50,000,000）與 D84 凍結收據 SHA-256 `3ade8183442781066b062d62f22e7af2335923fe73ead76b0fa5df5f9e0a81f5`。不得用 A／B1 示例值代填。

Model / effort 請照實填。
```

D-1 選 (b) 時把第 1 點換成「改 TEXT_COLUMNS 第 9 欄名稱與允許值，並同步 builder、指南、測試」；D-2 選 (b)／(c) 時改寫第 2–3 點。

---

## 7. 打包步驟清單（給 Sonnet；逐步可驗證）

建議由 Sonnet / medium 執行（CLAUDE.md 表：「Frontend implementation with a clear spec」）。全部 LOCAL；GitHub 寫入只在協調者明確授權後做。

**前置（任一不成立就停，回報協調者）**
0. 讀 D80、D84、D86、D89、D92（D-1～D-6 已由 D80 決定採 (a)）；確認以下都存在並記下 SHA-256：
   - r004 情境 run（A4）的 `run_id` 與 `clock_mapping`：取 #238 合併 SHA（`001cbcf`）的宣告並核對 50,000,000 us；#238 未合併則停。
   - D84 凍結的 r004 camera catalog（SHA-256 `3eba8572…899f`，收據 SHA-256 `3ade8183…81f5`；八台 camera_id；中文說法是否正式 UNKNOWN，否則標「提案」）。
   - D-3 (a)：v2 包八張空場景圖的 SHA-256 與 v2 MANIFEST 相符（見本檔 §0 依據；預期值已列在 v2 MANIFEST `images/static/CAM_*.png`），而且 camera catalog 和產生這些圖的相機姿態一致；不一致就停。
   - 詞表（類別、顏色）：有正式 hash 就用；沒有就標 PROVISIONAL，照指南 §3 的暫定表。
   - 磁碟剩餘 ≥ 8 GiB（`df -k`；importer／builder 都有這條）。
1. 用 `git -C LOCAL:工作副本目錄 fetch origin codex/q1q5-staging` 後 `git show <staging SHA>:<path>` 讀 builder、importer；指南改取 #269 合併後版本（M12），記錄 staging SHA 與指南合併 SHA。不建 worktree、不 clone（只有之後要 commit 時，才依 CLAUDE.md 用 scratchpad 精簡 clone，用完刪除）。

**建包**
2. `PACK=LOCAL:預設 artifacts 目錄/q1q3-authoring-yyin-v1_<YYYYMMDD>`；已存在就停，不覆寫。
3. 寫 `maintainers/build_q1q3_pack.py`（先在 scratchpad 寫、測，再複製進包）：從 staging 版 builder 匯入 `TEXT_COLUMNS`、`REVIEW_COLUMNS`、`csv_bytes`、`canonical`、`sha`（用 `importlib` 從 `git show` 匯出的暫存副本載入，或把三者逐字複製並寫明來源 SHA）。腳本負責寫第 4–10 步的所有檔案與 MANIFEST。
4. `A_文字情境/情境.csv` 與 `templates/情境.csv`：`csv_bytes(TEXT_COLUMNS, [{'編號': f'Q{i:04d}'} for i in 1..14])`，兩檔位元組相同。`B_畫面審查/審查表.csv` 與 `templates/審查表.csv`：`csv_bytes(REVIEW_COLUMNS, [])`。
5. `A_文字情境/範例.csv`：依 D-3。(a) 為 3 列「填法示意」，編號欄用 `示意1`–`示意3`（不是 Q 編號），文字欄用 〈…〉 描述，備註寫「填法示意，不匯入評估」。
6. `catalog/鏡頭目錄.csv`、`catalog/時間範圍.csv`、`catalog/詞表.csv`（UTF-8 BOM）；D-3 (a) 時複製八張圖到 `images/cameras/` 並逐張核對 SHA-256。
7. `DATA.json`（canonical JSON，`ensure_ascii=False` 可讀版亦可，但 MANIFEST 要記實際 bytes 的 hash）：`columns`、`row_ids`、`row_groups`（Q3_MIN 1–8／Q1_EXTRA 9–12／OPTIONAL 13–14）、`dropdowns`、`keywords`（依 D-1）、`note_format: q1q3-note-format.v2`、`quotas`（依 D-4）、`cameras`、`time_window`、`help_texts`。`data.js` = `window.PACK_DATA = ` + 同內容 + `;`。
8. `START_HERE.html`、`app.js`、`style.css`：依 §3 實作（可參考 r004 v2 表單的 `toCSV`／匯入／下載寫法，但**不要**沿用加 `'` 的公式中和）。`README.txt`（§2 全文，代入〈…〉）、`RETURN/README.txt`、`maintainers/PACK_NOTES.md`（配額、備註格式、轉換規則 `q1q3-conversion-rules.v1` 摘要、#269 合併 SHA 與指南檔案 SHA-256（G1；不記路徑／檔名，P2-4 ii）、已知偏誤：`詞表.csv` 列出紅／藍候選色本身暗示場景人物衣色（Q3 支援邊界必要資訊，可接受）、README 兩種回交檔名（正式與 `_INCOMPLETE`）都由 `verify_pack.py` 與 PACK_NOTES 接受、已知限制：靜態家具假設、人物題的超出時間偏誤（若 D-1 未修）、空列會是 INVALID）、（指南原檔不進包，見 G1）。
9. `tools/verify_pack.py`（只用標準庫）：
   - `--manifest-sha256` 必填；核對 MANIFEST 本身與 `files` 每一檔（拒絕 symlink）。三種結果：VERIFIED（無錯無警告，exit0）、VALID_WITH_WARNINGS（唯一問題是缺 `templates/情境.csv` 或 `templates/審查表.csv`，exit0，`warnings` 逐項列 `TEMPLATE_MISSING:<path>`）、INVALID（其餘問題，exit1）。缺件白名單之外任何檔缺失、已存在檔 hash 不符、symlink、可編輯原表或鎖定欄變動、回交 CSV 不合格，都不能降為警告；原本允許的 RETURN 回交內容依下項驗證。
   - `--returned-csv`（選填）：UTF-8（可有 BOM）、表頭逐字等於 TEXT_COLUMNS、14 列且編號順序完全相同、第 3／8／9 欄允許值（第 9 欄留空只在備註有合法關鍵字時接受）、開頭公式字元、換行、備註 q1q3-note-format.v2 的目標段及類別一致性（人＝追人／只問鏡頭，非人＝不適用）；匯入／匯出往返不得遺失第二層；class=person 排除 Q1，整段預設 PARSED 排除 A／B，另列「整段預設（實作前不計分）」；輸出各配額格的計數與 `_INCOMPLETE` 原因。不判斷答案對錯。
   - 結果 JSON 一行，包含 status、warnings 與錯誤；只缺 template 的收件須在正式匯入前從原包依 MANIFEST hash 補回，寫入缺件／補件紀錄並重驗至 VERIFIED。新建包與解壓自測不能接受 VALID_WITH_WARNINGS。這是待實作規格，不是本設計稿已完成工具驗證。
10. `MANIFEST.json`（用 builder 的 `canonical()` 寫，結尾 `\n`）：
    - importer 需要的鍵：`schema_version: "team-review-pack.v1"`、`version: "v1"`、`evaluation_eligible: true`、`files`（除 MANIFEST 外每個檔的 SHA-256；排除 `.DS_Store`、`__pycache__`）、`editable_files`（`A_文字情境/情境.csv` → `{template_ref: "templates/情境.csv", locked_columns: ["編號"]}`；`B_畫面審查/審查表.csv` → `{template_ref: "templates/審查表.csv", locked_columns: REVIEW_COLUMNS[:3]}`）、`samples: []`。
    - 附加鍵（importer 會忽略）：`pack_kind: "q1q3-authoring"`、`reviewer: "yyin"`、`return_file: "RETURN/情境_yyin_YYYY-MM-DD.csv"`、`guide_sha256`、`staging_sha`、`source_pins`（camera catalog、clock mapping、詞表、八張圖）、`quotas`、`note_format`、`decisions`（D-1～D-6 選項與留言連結）。
    - 注意：v1 包會被評分器視為 FORMAL（`dataset_kind_from_receipt`）。只有前置第 0 步全部是正式來源時才用 `v1`；有 PROVISIONAL 項目時，在 PACK_NOTES 寫明，並請協調者決定要不要改用 `v0-pilot`（evaluation_eligible false）。

**自測（結果全部寫進打包紀錄）**
11. `python3 -I $PACK/tools/verify_pack.py --manifest-sha256 <sha>` → `VERIFIED`。
12. 在 scratchpad 新空目錄做一份**測試用**回交 CSV（內容標「自測用，非題目」，絕不放進包），涵蓋：全空、部分填寫、每種下拉值、留空＋各關鍵字、含逗號／雙引號的句子、開頭 `=` 的錯誤列。跑 `verify_pack.py --returned-csv`，確認錯誤列被擋、其他通過；另以合成副本覆蓋只缺兩種template（VALID_WITH_WARNINGS／exit0／TEMPLATE_MISSING）、缺其他檔、hash錯、symlink、鎖定欄錯及CSV不合格（均INVALID／exit1），補回template後須VERIFIED。
13. 用 staging 版 importer 實跑（輸出目錄放 `LOCAL:預設 artifacts 目錄/_selftest_q1q3_<時間>`，`--registry` 指 scratchpad 暫存檔，不碰 repo 的 registry）：
    - 不帶 annotations：已填列全是 `PRECISE_HUMAN_ANNOTATION_REQUIRED`、空列與留空列是 `TEXT_FIELDS_MISSING_OR_INVALID`；**沒有** `CSV_COLUMNS_INVALID`、`LOCKED_FIELD_CHANGED`、`PackError`。
    - 帶一列合成 annotation（明標 SYNTHETIC 自測）：確認 `queries_v1.jsonl` 有 1 列、`text` 逐字相同。
    - 看完刪除自測輸出目錄與 df 檔。
14. 瀏覽器實測（Claude Browser；用 `preview_start` 開本機靜態伺服器，或直接 file://）：填 2 列 → 用 `javascript_tool` 取匯出函式產生的 CSV 字串 → 存到 scratchpad → 跑 `verify_pack.py --returned-csv` 和第 13 步的 importer 試匯入；再測「匯入 CSV 接續填寫」回填正確；確認時間欄沒有 date picker、公式字元被擋、反問＋否被擋。Windows／Excel 實機與真下載流程沒驗到的話，照實寫「未驗證」。
15. 內容檢查：`grep -r` 包內不得有 `/Users/`、`private`、`gt`／`GT` 路徑、劇本或人物設定字樣、`R004_A4B4_SCENARIO_CARDS`、`FEASIBILITY`（D89 報告）、路線調整內容標記 `E_OUT_VEST`／`路線改`／`計分事件`／`seed`、`t_X`、`t_N`、`[0,48)`／`0–48`、指南檔名 `Q1Q3_QUESTION_AUTHORING_GUIDE`、系統輸出檔、任何真句子示範；README 的〈…〉全部已代入，兩處展示時間必須與同一 #238 宣告逐字一致。P2-C採(i)：擋路線調整資訊，不禁合法鏡頭代號CAM_EXT_CLEAR，因D84凍結catalog及其衍生目錄／圖檔本來就包含該ID。PACK_NOTES 不寫指南檔名，所以該項全包掃描不設例外。

**封裝**
16. 重算 `files` 確認 MANIFEST 未過期（第11步須再得VERIFIED）；用標準庫 Python `zipfile` 封裝（在 `build_q1q3_pack.py` 子命令或獨立腳本實作，不使用Info-ZIP）。檔案依相對POSIX路徑排序，排除`.DS_Store`與`__pycache__`、拒絕symlink；每個`ZipInfo.date_time`固定為`(1980,1,1,0,0,0)`，`create_system=3`、`external_attr=(0o100644 << 16)`、壓縮方法／等級固定，中文檔名由zipfile設定UTF-8 bit11。同一輸入與封裝環境連做兩次，ZIP SHA-256必須相同，並核對所有非ASCII檔名都有bit11；記錄Python／壓縮環境、ZIP與MANIFEST SHA-256、檔案數、大小。不宣稱未驗證的跨環境壓縮bytes必相同。
17. 用`zipfile`把ZIP解到scratchpad新空目錄；去除唯一包根目錄前綴後，解出來的**regular-file相對檔名集合必須剛好等於MANIFEST.files鍵集合加MANIFEST.json**，缺檔／多檔／中文亂碼都失敗。再用`python3 -I`跑解出來的`tools/verify_pack.py`，新建包必須VERIFIED（不能接受VALID_WITH_WARNINGS）；看完依核准清理範圍處理該目錄。

**GitHub 說明文件（AGENTS.md「Handoff documents go on GitHub」；推送與開 PR 要協調者先取得使用者授權）**
18. 從 `mainline/q1q5` 開 `claude/yyin-q1q3-pack-v1`（scratchpad 精簡 clone，用完刪），Draft PR base `mainline/q1q5`，只用 merge commit。base 選擇若協調者要改 staging，以協調者為準（UNKNOWN）。提交：
    - `docs/operations/YYIN_Q1Q3_AUTHORING_PACK_V1.md`：包用途、決定 D-1～D-6 的結果與連結、包結構、配額、備註格式、轉換流程與卡點（§5）、LOCAL 產物清單（`$AMIDST_ARTIFACTS` 相對路徑、大小、檔案數、MANIFEST SHA-256、ZIP SHA-256、可否重建與怎麼重建）、自測結果、未驗證項。
    - `docs/operations/yyin_q1q3_pack_v1/README.txt`：與包內 README 位元組相同（文件裡寫兩者 SHA-256 相同）。
    - 建議一併提交可重建的來源：`docs/operations/yyin_q1q3_pack_v1/` 下的 `build_q1q3_pack.py`、`verify_pack.py`、`START_HERE.html`、`app.js`、`style.css`、`DATA.json`（都不含答案或回交資料；是否提交由協調者決定）。
    - 不改 `docs/operations/Q1Q5_PROGRESS.md`；由協調者在mainline批次補列（D91-4／#276），一般打包PR不自行更新導覽。
    - 不提交：RETURN 回交 CSV、空場景 PNG、ZIP、自測輸出。
19. 結果紀錄（AGENTS 模板，含 Model / effort）貼在 PR 說明，並留言到 #89 與 #138（T-2 沒有專屬 issue，掛在哪個 issue 由協調者決定：UNKNOWN）。

---

## 8. UNKNOWN 清單

- B4 的 run_id、clock_mapping（本包不用）。A4 已由 #238 宣告（merge `001cbcf`）。
- r004 camera catalog 中文別名是否正式（hash 已由 D84 凍結）；正式 region 目錄（#116）；`q-demo.q3-llm-output` 是否升版。
- 正式類別別名與顏色詞表 hash（#109、#114／#118）；正式索引 ID 與 parameter_set（#118）。
- Q1 query_sha256 的精確 preimage；OUT_OF_RANGE／UNSUPPORTED core 的鏡頭清單形狀；expected coverage 可否取自索引中繼資料。
- 身分不支援／需私有真值／跨run身分的 Q3 expected_status；評估用 Q2 request 的 seed／switch_mode。
- 文件 PR 的 base（mainline 或 staging）與 T-2 掛哪個 issue。
- 本 session 的 effort 設定。
- CQ-26 #316 的逐鏡頭可見車輛清單：尚未交件時為UNKNOWN，CQ-27 #317打包前回填交件PR／head與清單pin；看不到車的鏡頭不出車題。
