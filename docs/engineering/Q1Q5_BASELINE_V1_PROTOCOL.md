# Demo v1 最小 baseline 協定

日期：2026-10-24（Asia/Taipei）。任務 [#192](https://github.com/Polalalabear/amidst/issues/192)，base staging `a958dd4043ebcd5ef2d9fdb362d15f8c4ce3941f`。配套 [JSON 工程配置](../../configs/q1q5/baseline_v1_protocol.json) 是本文件的欄位與來源清單，狀態 **PROPOSED／不可正式執行**；現有 CLI 尚不讀取此配置。這兩檔不改產品 API、domain schema、核准參數或測量器。

本版先固定「找到拍攝目標的鏡頭」與「依影像及空間關係持續追查」的可重現操作及紀錄。正式 baseline 尚未完成；歷史 SYNTHETIC 通過不等於真模型、正式 RGB、人工正確性或 Demo 驗收。規則依 [DEVELOPMENT_RULES](../DEVELOPMENT_RULES.md)。

## 1. 狀態、來源與正式執行前置

`VERIFIED` 只用於本次已核對的 Git 檔案 bytes／SHA-256；`PROPOSED` 是待審的工程選擇；`UNRESOLVED` 表示缺值、缺 pin 或缺核定。JSON 中未知數值是 `null` 加原因，不以字串冒充數值。`REPORTED` 歷史量測不能升格成本次實測。

JSON 的 `formal_run.allowed=false` 是交付狀態聲明，**不是已接入產品的 runtime guard**。後續入口必須先驗其 `required_gates` 及所有正式 bindings；本輪不能改旗標便啟動。每項 gate 需核對實際 scope、版本／hash、核定者與收據；檔案存在、有人回覆或 manifest 相符不等於核定。

正式執行至少還缺：選定 run／相機／時間範圍及安全來源、正式 RGB／索引、run-bound clock／graph／parameter／catalog、最小 Q3 題組與獨立答案、硬體／環境收據、模型設定／預算核定、yyin 回收、Claude 獨立圖／ROI 與必要 HSV 核定、產品接線及 #145 符合性前置。這些缺件保持 `UNRESOLVED`；不以 A／B1、preview、機械 fixture 或其他 run 代填。

## 2. 有界案例與輸入

一次執行只選一個凍結 run；追查一次只有一個由使用者選定的來源觀測。查找可列多個相符鏡頭／觀測，不能替使用者暗選一個人。最小展示子集的相機數及時間窗由合法凍結收據決定，本協定不猜兩台名稱或事件時間。A4／B4 原產製規格不因展示縮小而被改寫。

`case_catalog` 是獨立 UTF-8 JSONL，逐列欄位見 JSON 的 `case_catalog.row_template`／`field_rules`：

- `case_id` 唯一且穩定；`task` 是 `ONCE_SEARCH` 或 `CONTINUOUS_PURSUIT`；`data_kind` 明填 `SYNTHETIC`、`PILOT` 或 `FORMAL_R004`。三者分開報告，前兩者不進正式分母。
- `binding_id` 連到凍結 bindings；`run_id`、`camera_ids` 及整數微秒半開窗 `[start_us,end_us)` 必須在同一 run／clock 及授權範圍內，不能裁掉越界部分假裝完整涵蓋。
- `query.kind=TEXT` 時帶 `question_id`、組員原文 `text` 及 context pin；`PRESET` 時帶既有 Q1／Q2 request 的 ref／file hash，Q3 記 `SKIPPED_PRESET`。兩種輸入互斥，不把表單再轉成文字請模型猜。
- 目標條件只用凍結支援 catalog 及 request 表達；Qwen3 讀文字／安全結構化證據，RT-DETR 讀 RGB。GT、劇本、actor、renderer 路線／visibility／depth 和人工 expected 不得出現在推論輸入。
- 追查的 `selected_seed` 綁 observation／frame／run／camera／timestamp 與來源 response hash，且在可用窗內；查找為 null。工程 NO_SEED 反例可故意不選，但不能算成功追查。

每個 binding 保存來源 manifest、RGB manifest、索引 manifest／records bytes、clock mapping、兩層圖、parameters、catalog／aliases／HSV、tracker 設定、case catalog、Q3 公開輸入、source composition 與 environment receipt 的 file hashes；domain 有 content hash 者另存，兩種 hash 不混用。composition 必須逐檔記 commit 與 SHA-256，不能只寫「用了幾個 Draft」。不複製或變動原始素材。

## 3. 模型角色、profile 與比較控制

| 工程 profile ID | Q3 文字解析 | Q5 持續追查 | RGB／索引 |
| --- | --- | --- | --- |
| `QWEN3_RTDETR_V1` | `LLM_WITH_RULE_FALLBACK` | `AGENT_SEQUENTIAL` | 同一份 RT-DETR 索引 |
| `RULE_ONLY_RTDETR_V1` | `RULE_ONLY` | `RULE_ONLY` | 同一份 RT-DETR 索引 |

profile ID 只是工程紀錄，不是新增 API enum。Q1 不啟用 Q5；PRESET 案例不呼叫 Q3。Qwen 各階段是否配置啟用、實際 attempted／used、呼叫數／timeout／fallback 必須分開記。`llm_parse_used` 或 `agent_used` 表示輸出經 guard 採用，不是人工判定正確；合法 RETURN 不是切鏡或追蹤成功。timeout 後的 RULE 結果可成為系統結果，但該次 LLM 仍失敗，不併入獨立 RULE_ONLY 對照程序。

第一組採現有 Qwen3 `qwen3:1.7b-q4_K_M` 與官方 RT-DETR R18。JSON 引用現有 tag／歷史 digest、v2 prompt bytes、generation framing、R18 code commit／預期 weights hash／RGB resize／CPU FP32／threads；這次只核對程式／文件，沒有查模型服務、載入權重或重測。實跑前須驗實際 digest、官方 source 逐檔 hashes、weights／class map／環境 pins，不能把歷史數值當已驗安裝。

Q5 call `2000 ms`、total `5000 ms` 沿已核准參數；`fallback_budget_ms=1000` 只記錄、不截斷整段 RULE 接手。Q3 `2000 ms` 仍是 **PROPOSED**，max attempts 與正式 generation 設定未定；正式 run 不能使用 fixture 的 APPROVED 背書。較長診斷預算不進 baseline。正式 `lost_after_us` 未定，與 `link_max_gap_us` 是不同參數；`600000 us` 只可沿既有 SYNTHETIC 工程命令，不是正式追丟期限。

兩個完整 profile 同時改 Q3 與 Q5，結果是系統對照，不能單獨歸因 Q3 或 Q5。後續 LLM 比較只換 LLM，固定題組、RGB／觀測、RT-DETR／tracker、閾值、prompt、generation／資源預算及硬體。若要隔離 Q3，只換解析器、Q5 固定 RULE；隔離 Q5 時兩邊共用同一份已凍結 structured query 及 selected seed，Q3 不重跑。這些是比較規則，本任務不另建執行平台。

case 難度／缺失／盲區條件兩邊相同；順序、case IDs、重複數及背景負載先凍結，保留失敗，不看輸出挑題。換題組、場景、硬體或輸入資訊，另開 experiment version 並重跑 baseline。一次查找和持續追查各自報告，不能用兩者耗時直接判斷演算法優劣。

## 4. 最小 Q3 題組與正確性

若該輪啟用 Qwen 語意解析，**先有最小固定 Q3 題組，再跑該輪**。本版提案至少 8 個不同 ID，沿 #89 八類各至少一題：Q1 找鏡頭、Q2 人／色／時間、時間變化、鏡頭／區域詞、不支援、需澄清、口語／混用、越界／注入。這只是最小工程子集提案，不取代 #89 的完整 60 題，也不聲稱具統計代表性；未經人審及凍結不得使用。

題目先抽樣再凍結，記選樣規則／ID 順序、公開文字及 catalog／clock hashes；模糊或答案缺件在執行前補正並保留修訂紀錄。本 issue **不生成題目／答案**，也不要求目前做影像標記的組員寫 Q3 程式。若日後獲指示採 AI 草稿，須由人核對；受測模型不能產生自己的正式 expected 或替自己評分。

推論端只拿公開 `{id,text}` 及 context；分類、`expected_llm_output`、`expected_status`、`expected_structured_query`、notes、GT／評估劇本留獨立 evaluation 端，沿 [既有出題格式](https://github.com/Polalalabear/amidst/blob/a958dd4043ebcd5ef2d9fdb362d15f8c4ce3941f/docs/evaluation/Q1Q3_QUESTION_AUTHORING_GUIDE.md) 與既有評分器。Q3 精確欄位／status／source 微秒比較規則先固定；缺人工精確答案、clock 或 mappings 是 INVALID／待補，不能由模型結果反推。

execution record 的 `evaluation.status=UNREVIEWED`、accuracy／接錯率等均 null。正式輸出與 journals／manifest 凍結後，獨立人工才讀影像與評估端資料做 T/F／評分，另產 pinned evaluation report，不能回寫凍結 execution。Q1 按鏡頭／觀測答案及未評估覆蓋分列；Q5 區分支持恢復、未接回、接錯及無證據切鏡。身份持續 UNCONFIRMED；物理導航／碰撞保持 UNKNOWN。

## 5. 逐次紀錄與量測定義

JSON 的 `record_contract` 定義工程 sidecar，保留原 domain request／response／journals；不把 wall time、RSS 或評分放入既有 domain hash。每筆至少有 experiment／protocol／case／profile／task、資料種類、iteration／phase、bindings／request／response／journals pins、執行 status、錯誤 stage／code、Q3 與 Q5 各自的實際呼叫及兜底、事件引用、replay 核對。下列欄位均先列於 `sample_template`，未儀器化保持 null 並在 `unmeasured_reasons` 說明；只有已驗未呼叫／未發生才填 0 或 false。

| 欄位群組 | 定義 |
| --- | --- |
| stages | setup、model_load、index_build、q3、detector、index_search、q5、http 各自 wall／CPU ms 與 measure_call 的程序 peak RSS；未包到的 stage 為 null，不拆估 |
| first／all result | 自接受該 case 請求到首個可用結果／全部結果完成的同一 monotonic clock 差；無結果時 first 為 null，另記 completion／status，不能把空回應當首筆命中 |
| end_to_end_ms | 使用者提交到對應結果／切鏡影格實際 presented 的 elapsed；需 browser acknowledgement 與同時鐘或已校正時計，server 回應時間不能代填 |
| 首回／暖呼叫 | 每個 case×task×profile 獨立 worker，setup 後 1 次 FIRST_CALL＋2 次 WARM_REPEAT；這是功能 baseline 提案，僅報逐次值、N、中位、最大，不宣稱穩定 P95 |
| 模型冷／暖 | FIRST_CALL 不叫冷模型。另記載入前後 inventory、load 測量、preload／warmup 次數及是否計時；未觀察載入就 UNKNOWN，不清 cache／卸載他人模型來造冷啟動 |
| 建置成本 | 首版沿離線 RT-DETR 索引，model_load／index_build 分列一次性成本及 scope，不重算成每次查詢；setup／index build 不在 kernel wall 內時明示 excluded，使用者總等待仍另記 |
| 記憶體 | measure_call 的 before／after peak 是程序生命週期高水位，不能相減當本次配置量。Ollama runner／detector／server／browser 各自 sampled RSS 與採樣間距另記；系統 available／compressor／swap、VRAM／API size_vram 分列，不能相加冒稱物理需求 |
| fps | detector_completed_frames×1000／detector_elapsed_ms；display_presented_frames×1000／display_elapsed_ms，必須同 scope／正時間／去除重複影格並記 dropped frames。索引查詢／replay 速度、source 5 fps 均不是模型或顯示 fps |
| Q3／Q5 | 配置啟用與實際 attempted／used 分開；各記 provider_calls、timeouts、fallback、原始 status／原因、prompt／raw output／audit pins；provider envelope 合法不等於 task／人工正確 |
| 事件 | 引用既有 event_flags 與 decision/link 原始 journal，記 SOURCE us、run／camera、observation、previous camera、output pin；FOUND／LOST、真切鏡與 LOST 後同／異鏡頭支持恢復分列，不把初次 FOUND 算接回 |
| 利用率 | provider accepted calls／attempted calls、fallback cases／eligible cases、CPU seconds／wall seconds等都記 numerator、denominator、unit、scope；無合法分母為 null。多核心 CPU ratio 可大於 1，不冒充單核百分比；硬體 GPU utilization 需實測，不能由 API residency 推估 |

SOURCE 時間、處理 wall 時間與播放時間分開。LOST 僅表示原範圍未恢復觀測支持，期限當刻恢復不另發 LOST；不宣稱人不存在。MISSING／NOT_INFERRED／NOT_SAMPLED 及 PARTIAL coverage 保留；事件分類未獲正式語意核定時只保存原 flags／journals，正式接回率為 null。

所有預定 worker／case／profile／重複須在 run manifest 列出，失敗／timeout／缺 worker／缺報告／replay 不一致均保留，整體不能報 COMPLETE。`COMPLETE` 只代表工程計畫執行完且重播核對，另記 conformance／evaluation／formal readiness，不能用它代替產品或人審通過。

## 6. 重用入口、資源與 replay

沿 [#185 code head 93042da](https://github.com/Polalalabear/amidst/tree/93042da095e88942380aa2b83d27528da4726c2c) 的 `measure_call`、`frame_rate`、`verify_replay` 與既有 kernel／API，不重寫測量器。JSON `source_references` 固定各檔 commit／file hash；正式 composition 仍未凍結。這不是「checkout 單一 Draft 即完整啟動」的承諾。

現有可跑命令只涵蓋 SYNTHETIC／RULE_ONLY。先指定既有量測包的 source root、已安裝 Python 及**全新、canonical、無 symlink、parent 已存在**的 LOCAL 輸出目錄，再從該 composition 執行：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$Q1Q5_SOURCE/src" \
uv --no-cache run --no-project --offline --python "$Q1Q5_PYTHON" \
python "$Q1Q5_SOURCE/scripts/measure_q1q5_baseline.py" \
  --synthetic --lost-after-us 600000 --warm-repeats 2 \
  --output "$Q1Q5_NEW_OUTPUT"
```

此命令不吃本 JSON、不跑 Qwen／真 RT-DETR；五情境×兩任務×三次＝30 次 kernel、20 次暖呼叫重播，是歷史工程設計，不是本輪新測試。真模型／HTTP／UI／case catalog 整合另認領，不提供尚不存在的 `--protocol` 開關。

執行前保存完整命令／exit code、OS／CPU／RAM／GPU／drivers、Python／uv／torch／Ollama／JS／依賴鎖與實際環境差異、device／precision／threads、模型 inventory／共享服務所有權及背景負載。JSON 的 worker concurrency=1 是本協定提案；模型服務是否仍在 timeout 後運算須如實記錄，不私自 kill／restart／卸載。host、worker timeout、memory cap 未凍結者仍 UNRESOLVED，不借用歷史機器當當前硬體。

每次產製／推論前後保存 `df -k`，失敗也記 after；可用空間低於 `8388608 KiB`（8 GiB）停止。不為本任務清理資產或快取。程序 peak、產物 bytes 與檔案系統 free delta 分列，不互相代替。

回收 run manifest、逐次 telemetry、原 request／response、detection／clock／graph／parameter pins、decision/link journals、私有 model audit／trace、replay 結果、環境／命令／錯誤與逐檔 bytes manifest。含 prompt／raw／私人 locator 的紀錄限 LOCAL 私有權限，不由靜態 server 或公開 repo 提供。

離線 replay 用錄製 provider／ticks／既有 replay scheduler，Q3 response、Q5 output hash 與兩份 journal bytes 一致；模型／網路呼叫都為 0。與原 domain canonical hash 分開核對 bytes hashes，replay latency 不算模型效能。缺 trace／pin、竄改或重播差異直接 ERROR；不拿重新推論代替錄製重播，也不保證不同硬體新推論逐 byte 相同。

## 7. 人審期間交付與後續

本 issue 只交這份 MD 與 JSON，B／需要 Claude 審；不更動 #127／#135、Q5 statechart／strict XFAIL、產品或人審原包。yyin 回收需填好的 CSV、問題／不確定／未完成清單，以及完整資料夾或 ZIP；保留原包，按回覆另做補件。

後續另逐項認領模型／API／工作台／replay 接線、產品契約差異、正式產製預檢。yyin 審完不等於 G4 或新 HSV 核定完成；已有 D70 渲染授權不重問，但不能跳過獨立凍結收據。順序為：必要獨立審查／設定及程式前置通過 → 凍結 → 正式 A4／B4 RGB → 正式索引 → 查找／持續追查 baseline → 輸出凍結 → 人工 T/F／評分。其他 LLM、YOLO-World、進階 ReID 後排。

本輪驗收只核對 JSON parse、必要欄位／交叉欄位、Git source bytes/hash references、兩檔一致性與 `git diff --check`；不執行模型、render、browser、正式評分或全套測試。#185 的 976 PASS／62 FAIL／36 缺 context 是原 checkpoint，#145 尚未解除，不能計為本次通過。JSON 是明確可審的規格配置，尚無正式 run／Q3 題組／人工答案或新 runtime 成效。
