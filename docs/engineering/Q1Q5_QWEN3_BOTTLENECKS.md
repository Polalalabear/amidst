# Qwen3 切換與瓶頸分析（2026-10-23，依 #144 提案）

依使用者指示，Q線新runtime已改用 `qwen3:1.7b-q4_K_M`。Qwen2.5 7B 模型權重已透過官方 Ollama rm 移除；舊等待紀錄、raw output、模型digest、manifest、採樣、輸入hash、離線重播全部保留。這次沒有更改任務prompt、guard、核准預算或宣告Agent品質通過。

結論：目前主要問題依序是 **輸出契約不穩定、工具流程未推進、輸出token成本超過2秒預算**。模型載入不是暖機後每次慢的主要原因。容量壓力存在，但尚無證據證明它是本次每個錯誤的原因。

## 先看觀察證據

資料來源為 LOCAL `/Users/polalabear/amidst-artifacts/q1q5-model-compare-20261023/`，原封不動的 `MANIFEST.json` SHA-256 `85b9f8808eccc5ca762a5f5dffcaadb9e6bad18ee70cfc3cae077569df3c811a`，205個檔案已逐一核對。方法與完整表見 [Q1Q5_LOCAL_MODEL_COMPARISON.md](Q1Q5_LOCAL_MODEL_COMPARISON.md)。這是同一機械輸入的3個seed，沒有組員題目／答案／GT；不能外推正式accuracy。

| 問題 | 實際觀察 | 判斷邊界 |
| --- | --- | --- |
| Q3回覆型別與原文錯誤 | 1.7B三次輸出相同：把車文字輸入回成person/red，invent A/R1，time_literal是字串而非start/end/date物件；0/3採用 | 原schema/literal guard正確拒絕。不能解讀成僅「模型太慢」 |
| Q5沒有決策 | 1.7B三次session各呼叫同一個get_observation_summary三次，耗盡3回合；沒有提交Agent決策 | 能產生合法工具JSON，不等於完成Agent工作 |
| 暖機後decode成本 | 1.7B Q3約93輸出tokens，decode4203.918–4304.285ms；後兩次prefill20.826/23.343ms，load3.310/4.457ms | 暖機後這兩次主要時間在decode；不是靠再預載一次就能達到2秒 |
| 多回合成本 | 1.7B Q5每次工具呼叫57輸出tokens，decode2599.729–2838.643ms；每session三次，總等待10.100–11.931s | 僅一次完整工具回覆就超過2秒，三次呼叫也超過Q5總5秒 |
| 7B吞吐與任務錯誤 | 已完成Q3 decode中位約5.53 tokens/s；有camera_terms/region_terms=null等型別錯誤；Q5重複抓同一candidate evidence後ILLEGAL_CANDIDATE | 較慢與任務錯誤同時存在，不能只延長timeout |
| 7B telemetry異常 | 有一筆prompt_eval_duration=329317.68ms，但client此次呼叫並未等待相應時間 | 這筆server phase數值與client wall不一致，原因UNKNOWN；保留raw，不加總成可信prefill結論 |

1.7B舊長診斷Q3中位等待4.380s、Q5 session10.136s；7B native是28.551s／60.906s，各含逾時樣本，不能當成功延遲或一般倍率。4次2秒probe皆逾時。這些數字與已刪除的舊權重無關，仍可用hash核對並離線重播。

## 原因分析：已確認與推測分開

### 1. JSON有效不代表符合任務schema（優先P0）

目前wire只送 `format: "json"`，沒有把完整typed schema交給解碼器；Q3原template雖列欄位與時間三鍵，但沒有完整列出所有陣列型別與缺值形狀。已確認的是「模型回傳JSON、task validator拒絕」。這支持schema引導不足是可驗證的改善方向，**還不能證明它是語意幻造的唯一原因**；小模型能力／prompt措辭的影響尚未做隔離實驗。

建議下一輪：把既有契約轉成JSON Schema，明示陣列、null、time_literal物件與禁止額外欄位，保持literal／closed-catalog驗證。仍要拒絕原文不存在的值；schema約束只能限制結構，不能證明語意正確。Ollama允許 `format` 接JSON schema，參見[官方structured outputs](https://docs.ollama.com/capabilities/structured-outputs)。本輪未實作或宣告改善。

### 2. 工具選擇缺少明確的流程進度（優先P0）

目前每輪用同一system template＋當前context／last_tool_result／remaining，沒有保留完整assistant/tool對話；`get_search_context` 已由controller先準備。模型仍可反覆選observation工具，且沒有將這種已讀工具從本輪選項拿掉。prompt的「不得重抓rank」主要描述candidate evidence，不能保證模型不重查observation。

已確認的是重複工具耗盡回合。推測是模型沒有從last_tool_result辨識「已查過、下一步應取候選證據或提交」，不是工具查不到資料。建議：顯式列已完成工具／目前phase／合法下一步，讓重複請求可見；對小模型比較「候選證據由程式備妥後只做一次決策」與「保留sequential tools」兩路。是否縮減Agent工具自由度、改回合語意需另列契約提案，本次不改，也不跳過SWITCH evidence guard。

### 3. 輸出token與多回合相乘超過預算（優先P1）

1.7B已完成呼叫的decode約21tokens/s，本次57-token工具回覆約2.7秒、93-token Q3回覆約4.3秒。以這個觀察量級，2秒還需支付prefill、metadata、網路與驗證，不足容納這些回覆；這是本次預算失敗的直接證據，不是一般硬體保證。

建議先減少重複工具／長ID反覆抄寫／可省的解說，使用精確schema及緊湊JSON，再看合法決策的端到端耗時；必要的source/hash/reference仍保留，不能改成不受驗證的候選索引。`think=false` 已在比較與新runtime中使用，不能把「再關一次thinking」當尚未做的加速。核准Q5 call2000ms／total5000ms保持；Q3的2000ms仍PROPOSED。

### 4. 冷啟動與共享資源（優先P2）

本次新runtime獨立管理預載2584.02ms；歷史7B冷載入約6.64秒，不能混在暖呼叫結果。16GiB機器同時有桌面程序，但沒有RT-DETR併發測量／記憶體壓力profile，不能宣告Metal、swap或RT-DETR是已證實主因。

建議有界模型常駐／背景預熱需明確的owner與lifecycle；推論與RT-DETR併發另做測量。單純清磁碟不等於增加推論吞吐，本輪不改服務啟動規則。

## 這次已落實的切換

- 新runtime只允許 `qwen3:1.7b-q4_K_M`，明填manifest/API pin `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`。產品未配置registry/run仍NOT_READY，沒有新建正式run或啟動產品server。
- Qwen3走native `/api/chat`、system/user分開、`think=false`、context4096、輸出cap256、keep_alive60s；完整wire hash／protocol進audit。原Qwen2.5 raw audit仍可驗證／replay，新Qwen2.5 runtime config則拒絕。原模板檔、Domain schema、SWITCH guard、Q5預算不變，Demo仍預設RULE_ONLY。
- 官方 `OLLAMA_HOST=http://127.0.0.1:11437 ollama rm qwen2.5:7b-instruct` 成功，移除舊模型獨占blobs共4,683,087,332 bytes（metadata），Qwen3 manifest SHA與所有blob大小／mtime保持（未重新雜湊大權重）。沒有移動／備份weights，沒有清cache、重啟Ollama或改其他chat服務。
- 刪除前／後df可用8,665,000→13,239,360KiB，當步增加4,574,360KiB（約4.36GiB）；這是當步df差，與模型bytes分列，不作絕對因果或永久可回收量保證。本次無新增模型下載。
- 2.5權重移除後，歷史真錄製Q3 response、Q5 output hash／decisions／links精確重播一致，0模型呼叫。歷史模型重新生成在本機已不可用，不能宣稱可不用下載重做7B推論。
- 本次177 focused PASS；新Qwen3原預算Q3／Q5 provider各約2001.98／2001.78ms逾時，規則接管且replay一致。原#127 Q3 56 PASS，Q5 133 PASS／14 FAIL／3缺context；不把兜底合法輸出當Agent成功，PR維持B／Draft。

程式接入與file pins見[目前runtime文件](Q1Q5_QWEN_RUNTIME.md)；[Ollama chat API](https://docs.ollama.com/api/chat)說明messages／format／think欄位。對既有typed schema／工具策略的改善只列為提案，不因本次換模型就放寬驗證或調整核准值。正式r004、人審、RT-DETR並行、瀏覽器驗收、§14-23／26／27仍未核定。

LOCAL證據：`/Users/polalabear/amidst-artifacts/q1q5-qwen3-switch-20261023/CURRENT.md`，包含MODEL_REMOVAL、retired-qwen2.5-replay、原預算runtime-probe/runtime.json、兩種replay、原包報告、focused XML與最終source composition。舊phase1啟動器設定屬另一checkout未改，仍pin已刪的2.5，因此不能拿來啟動新Q線runtime；現有靜態／RGB審查服務不受本次模型選擇控制。
