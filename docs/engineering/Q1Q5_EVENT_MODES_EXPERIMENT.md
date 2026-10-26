# Q1–Q5 Agent 職責與雙模式比較

依使用者在 #184 對應 chat 的新指示，兩種 Q5 方式均做工程試用；這不是核定正式追丟門檻或辨識品質。依 #144 提案，原 #127／#135 不動。

**目前模型順序（使用者已決定，2026-10-22）：先使用本機 Qwen2.5-7B-Instruct；OpenAI API 等系統完整後才接入測試。** 這是接續開發順序，並非宣稱本機真模型已完成接線或已量測效果。現有比較頁仍使用機械 FakeProvider；本次只補文件，不啟動模型或串接外部 API。

## Agent 在整個 Q1–Q5 系統做什麼

| 系統階段 | 執行者與責任 |
| --- | --- |
| Q3 理解自然語言 | 規則 parser，或可選 LLM 將文字轉結構化條件／提出釐清。解析模型與切鏡 Agent 是不同職責；不找影像、不產生答案。 |
| RT-DETR／HSV | 程式對已授權 RGB 離線產索引，偵測人物／類別及顏色線索；LLM 不逐格看圖。 |
| Q1 找相機 | 程式查安全索引，保留相符／不相符／未評估；不需要切鏡 Agent。 |
| Q2 同鏡頭追蹤／失聯觸發 | 後端按來源取樣時間做局部連接與狀態機，無支持進入搜尋；不由 Agent 持續監看。 |
| 候選圖與排序、Q4 證據 | 程式按凍結圖／參數產生有界 top-k，聚合觀測支持；Agent 不能自行擴大、重排、改門檻或讀 GT。 |
| Q5 AGENT_SEQUENTIAL | Agent 讀搜尋摘要、當前候選證據及已曝光觀測，提交 SWITCH／NEXT_CANDIDATE／RETURN_TO_ORIGIN。實際切鏡仍由後端重新驗 guard、pin、來源時間。 |
| Q5 BACKEND_FLAGS 實驗 | 使用現有 RULE_ONLY Controller 做選擇，事件 adapter 產 FOUND／LOST；切鏡／提示是決定性的事件處理，不呼叫 Q5 LLM。 |
| 故障兜底、UI、replay、評分 | 程式執行；Agent 壞掉時規則接手餘下 session。人工題目、答案、T/F 由組員提供；評分端才讀凍結答案／劇本。 |

正式 registry 尚未配置 live Q5 Agent factory；Q3 LLM→Q1/Q2 的 parse provenance 為 §14-23 未決。本工程試用不宣稱已接通正式模型。

## 兩種方式怎麼比較

- 相同 index／clock／圖／參數／query／selected seed，僅 switch_mode 不同。BACKEND_FLAGS 對應 RULE_ONLY；AGENT_DECISIONS 對應 AGENT_SEQUENTIAL，沒有私加 q2-request.v1 enum。
- kernel 完成並凍結原 response、decisions／links；事件 adapter 不改原 output hash，也不授權額外切鏡。UI 只重播已產生的 SOURCE timeline 和 flags。
- FOUND：觀測支持恢復或核准 kernel 已切到另一鏡頭；附入口觀測 ref，只帶入口那一筆，不把合併 segment 後面的未來觀測當成當時證據。原鏡頭恢復可以 FOUND，但 switch=false。
- LOST：選定起點後，連續無觀測支持超過操作者明給的 `lost_after_us`，保留失聯鏡頭、通知一次；恢復支持後才可開始下一段失聯計時。這不是「確定人不在」，所有候選未必都有完整證據。
- 期限用來源微秒；恰於期限恢復時不先閃 LOST。查詢右端是半開界，不在範圍外發通知。還沒選到起點不發 LOST。
- 沒有正式預設期限。工程範例 600000 us 僅為2秒機械fixture中的測試值，EXPERIMENT_ONLY_NOT_APPROVED；不替代 link_max_gap_us、不改已核准參數。
- 比較呼叫數、取證數、切鏡／LOST 次數、故障兜底及原 trace replay 一致性；沒有人工答案，不計準確率。機械 FakeProvider 的呼叫數不是實際 Ollama token／延遲／品質量測。

## 重現

在具名的多 PR source composition（含上游 #169/#172）中，使用既有 Python：

```sh
df -k "$Q1Q5_OUTPUT_PARENT"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$Q1Q5_SOURCE/src" \
uv --no-cache run --no-project --offline --python "$Q1Q5_PYTHON" \
python "$Q1Q5_SOURCE/scripts/compare_q1q5_event_modes.py" --synthetic \
  --lost-after-us 600000 --output "$Q1Q5_OUTPUT_PARENT/new-run"
```

output 要全新，既有檔不覆寫，產製前後 df-k，低8GiB停止。沒有 Blender、權重下載、模型連線或原始素材讀取。逐情境保留 Agent trace，並用 RecordedProvider 斷線重跑；domain hash、decisions、links 須完全相同。

瀏覽器試用是 `frontend/workbench-v2/event-modes.html`，同目錄提供 generated `comparison.json` 與既有 q-validate／q-time 模組。從 localhost 靜態server 開啟；只發布 web 檔，不把 private trace 根目錄當靜態站台。可以選後端、Agent或並排，切換5個機械情境，播放／重播／拖SOURCE時間。沒有真RGB，兩邊都明示 RGB MISSING。

工程情境：有支持的第一候選、第一候選空但後面有支持、所有候選空、暫失後原鏡頭恢復、provider故障。它們是程式控制測試，不是組員題目或標準答案。

## 未完成與限制

#183 原契約仍不允許空 observation 引用的 NEXT。此版本保留它：機械策略遇空證據合法 RETURN，不偷偷換成能跳過空證據的 Agent；因此可直接看出後端模式與目前 Agent 協議的差異。修法列 §14-26，未核定／實作。事件通知方式與期限列 §14-27。

這是一個可播放的工程比較包，非 live streaming 通知端點或正式 r004 Demo。正式RGB、Agent真模型與人工評分仍待既有#115/#118/#147／契約與模型設定。上游Draft與原kit FAIL未解除前，本任務維持Draft，不可拿SYNTHETIC對比當正式比較結論。

## 工程問答統整（2026-10-22）

本節整理使用者與 Codex 對系統分工的討論，供開發及審查引用；不是組員評估題目、標準答案或人工 T/F。

### Q1：什麼是「候選沒有人物觀測，Agent 無法合法下一候選」？

追蹤在 A 失去觀測支持後，後端提供排序候選 B、C。Agent 已查 B，但 B 的 evidence 是 NO_PERSON_DETECTED，best_observations=[]、entry_observation_id=null。現有契約 §8.4 要 NEXT_CANDIDATE 引用該候選內至少一筆 observation，所以空引用與引用原鏡頭 A 都會被拒絕，游標停在 B；直接查 C 也因 ILLEGAL_ORDER 被拒。此刻 C 尚未檢查，不能說全部候選都找不到。

這是契約功能缺口 [#183](https://github.com/Polalalabear/amidst/issues/183)，程式及既有測試目前正是照非空引用規則運作。RULE_ONLY 可跳過空候選；Agent 若依現有契約合法 RETURN，就可能錯失後面的可用候選。§14-26 列修法選項，尚未決定或實作；不得編造引用或放寬 SWITCH guard。

### Q2：長時間找不到時，畫面與提示應怎麼做？

使用者提出的方向是：在指定候選範圍持續找，長時間仍未恢復目標的觀測支持時，保留目前鏡頭、讓來源時間繼續前進，提示「追丟目標」，不切到沒有支持的畫面。候選暫時沒找到時先繼續搜尋，不立刻宣告 LOST。

本次實驗實作：LOST 每段連續失聯只通知一次，恢復後可重新計時；期限使用 SOURCE 微秒且操作者必填，沒有正式預設。合成示範0.6秒只是2秒控制素材的測試值。正式「多久算長時間」、期限當刻與查詢結束的行為仍列 §14-27 待核定。保留目前鏡頭是本次失聯所在鏡頭，不必回到整個 session 最初的 A。

LOST 的含義是「追蹤沒有恢復觀測支持」；不能升格為「所有鏡頭已證明沒有人」。MISSING、未推論、未查完與條件不符須保持區分。

### Q3：可否讓 RT-DETR 定期檢查所有指定畫面，Agent 不逐格處理？

可以採這種分工：程式處理固定鏡頭／時間範圍的影像與索引，只有需決策或通知時才使用 Agent。RT-DETR 偵測人物／類別，再由 HSV 等程式檢查條件；不是 Agent 每格看圖，也不能把偵測到人物當確認同一人。

目前離線影片 Demo 的方式是先離線建立指定範圍的偵測索引，播放時後端依來源取樣時間讀索引。查詢不臨時補推論、不擴大到未授權畫面。持續即時跑多鏡頭 RT-DETR 的吞吐量與採樣頻率尚未量測；現有比較包也不是該即時推論能力的證據。

### Q4：是不是 Agent 等待後端 FOUND／LOST flag，再切鏡或通知？

這是使用者提出並要求試用的 BACKEND_FLAGS 分工：後端已有選擇結果，FOUND 帶鏡頭、來源時間與證據；事件處理器執行切鏡，LOST 則保留鏡頭並提示。當前鏡頭仍有支持或搜尋未結束時，毋須反覆叫模型。若規則固定為 FOUND必切／LOST必提示，處理flag本身不需要再呼叫LLM。

AGENT_DECISIONS 則把後端限定的候選與證據交給模型，由模型選 SWITCH／NEXT_CANDIDATE／RETURN_TO_ORIGIN。實際切鏡權限仍在後端。兩種模式都已做出 frozen-output 的工程比較；live streaming flag端點尚未接入，不能把比較頁當成這部分已完成。

### Q5：具體的三鏡頭例子是什麼？

以下為分工示意，不是正式r004執行結果：起初在走廊 A 觀察到符合條件的人，主畫面看 A；失聯後後端檢查指定候選 B、C。若 B 有足夠支持，後端事件模式發 FOUND(B,t,refs)，後端驗證後硬切 B。之後 B 也失聯，持續指定時間未恢復支持，就在目前來源時間保留 B、提示追丟。

Agent模式在同一搜尋點讀候選證據後，可以提議切 B、繼續下一個或暫不追。RETURN只是結束這次候選搜尋、保留失聯鏡頭；它本身不是「已長時間查遍並證明追丟」的結論。後端仍可依明列的計時／重查規則繼續工作。

### Q6：Agent 在整個系統到底做哪些決策？

完整角色表見前面的「Agent 在整個 Q1–Q5 系統做什麼」。LLM 只有兩處可參與：

1. Q3：把文字轉成結構化條件、判定是否需要補充；這是解析模型的職責，不是 Q5 切鏡 Agent。
2. Q5：在後端給定的 top-k 與工具中，讀證據並提出 SWITCH／NEXT／RETURN；後端做最終 guard 與執行。

影像偵測、顏色線索、查索引、同鏡頭連接／失聯觸發、候選排序、參數／來源檢查、故障兜底、播放／提示、錄製／replay、評分都由程式處理。Agent不能重排候選、改門檻、擴搜尋範圍、讀GT、確認身分或判定物理安全。現有程式不是由一個模型管理所有模組。

### Q7：這樣算 agentic 嗎？看起來演算法就可以處理？

這個質疑成立。固定的 FOUND→切鏡、LOST→提示屬事件驅動自動化；已有明確規則的部分不必為了名稱加入LLM。Q5若模型能依工具回應選取證／下一步／停止，有工具使用與回饋迴圈，可定位為「受限Agent模組」，但不因此證明整個系統更快、更準或模型不可替代。

現有小範圍固定top-k、固定排序下，Agent未必能比RULE_ONLY少查詢；LLM往返還可能增加延遲。目前比較頁是機械策略，不能據此證明Qwen優於規則。實際收益須用相同資料、起點、規則、候選與預算，比較任務完成率、人工操作、時間、工具／模型呼叫與成本。

### Q8：哪些工作用 Agent 有機會加速？

| 工作 | 可能收益 | 目前狀態 |
| --- | --- | --- |
| 自然語言與釐清 | 減少人工填條件、處理不同說法，缺欄位時反問 | Q3 kernel已有，正式LLM→Q1/Q2 provenance接線尚未完成 |
| 多步驟任務編排 | 按結果串查詢、請人選起點、啟動追蹤、整理結果，減少操作與手寫分支 | 建議擴充，尚未實作；不是本次原工作清單已承諾完成的能力 |
| 選下一份要取得的證據 | 在核准範圍／預算內減少不必要查詢 | 可研究，現有候選順序／時間窗契約不可私改，收益尚未量測 |
| 追蹤紀錄摘要 | 將引用、缺口、理由與UNKNOWN整理給使用者 | 可擴充；不得生成評估標準答案或替代原證據 |

這裡的「加速」主要是節省人員操作／編排時間，不保證RT-DETR推論或固定切鏡更快。技術是否更agentic與工程效益是兩個要分別量測的問題。

### Q9：Qwen2.5-7B 與 OpenAI API 怎麼用？

使用者已明確決定：**目前先用本機Qwen2.5-7B-Instruct；系統完整後，再接OpenAI API測試。現在不新增外部模型連線。**

Qwen2.5-7B-Instruct可先測文字解析及少量受控工具的短回合決策；它是文字模型，讀偵測／證據摘要，不直接作RGB視覺模型。官方有[工具呼叫文件](https://qwen.readthedocs.io/en/v2.5/framework/function_call.html)與[模型卡](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)。現有loopback Ollama薄provider可作接線基礎，但正式registry的Q5工廠、模型digest／prompt／參數pins，以及Q3採用來源仍要補，不能將FakeProvider或provider單測寫成真模型整條鏈已通過。

OpenAI API是後續另一組模型測試的介面，不等於Agent本身。後續可以透過[function calling](https://developers.openai.com/api/docs/guides/function-calling)連同一組工具；格式約束不代替後端guard／引用驗證。這次只記錄延後接入的順序，未新增provider、key或外送資料設定，也不宣告既有本機限定契約已自動修改。

### Q10：現在比較頁能回答什麼、還不能回答什麼？

能回答：同一份凍結來源下兩種控制流程如何切換／保留畫面、何時發FOUND／LOST、取證與機械模型呼叫數、原始trace是否可斷線重播。#183的空候選限制刻意保留，機械策略遇空證據合法RETURN。

還不能回答：真Qwen的語意／決策品質、真RGB辨識效果、即時吞吐量、真模型延遲／token成本、人工評分、OpenAI與Qwen孰優。之後應先跑真Qwen，才能把工程流程比較升級成模型效果比較。

## 尚未完成的工作（2026-10-22 GitHub核對快照）

staging為 `a958dd4043ebcd5ef2d9fdb362d15f8c4ce3941f`；27個PR已merge commit合入，12個Draft保留。PR #185本次純文件更新也保持Draft。狀態要依具體交付與驗證判斷，OPEN／ready標記本身不代表未寫程式或已完工。

| 順序／工作 | 還差什麼 | 依賴／負責 |
| --- | --- | --- |
| 契約與原kit對齊 | #153無色evidence、#156末頁total、#170 D69/link／Agent失敗欄位、#178空journal；#145 owner對齊後須對實際輸出重驗 | Claude處理#145；Codex不改#127/#135；仍有程式／契約差異須逐項判定，不能先說全是測試錯 |
| #183空候選NEXT與通知語意 | §14-23 Q3 parse provenance、§14-26空evidence引用、§14-27雙模式／LOST期限等待決；正式門檻未核定 | 契約決策／審查；不放寬SWITCH guard |
| 真Qwen接線與比較 | 正式Q3／Q5模型設定、digest與prompt pins、Q5 factory／scheduler、實際工具回合、故障接手、真trace replay與模型效果測試 | Codex程式；當前只有kernel／provider測試及機械比較，live完整鏈未驗 |
| #117靜態圖與出口ROI | 已有8台PROPOSED圖，缺Claude獨立檢查及事件前凍結完成收據；G4／通行authority不自動成立 | Claude獨立檢查與既定核准流程 |
| #115正式A4／B4 | 正式RGB／安全bundle／run／clock未產出；待事件前圖／ROI前提成立 | Codex；D70的G5渲染授權已存在，不重複要求 |
| #114新HSV、#118正式索引 | 新HSV Q-19需檢查／核定，正式index依賴#115 RGB；既有§11 G6初值核准不替代新提案核定 | Claude檢查／使用者核定後Codex產製 |
| #112／#80端點與T1–T4整合 | 上游Draft、原kit尚FAIL；須接正式safe RGB與Qwen，驗真取圖grant、來源pins、Q3後續執行、雙模式／live通知 | Codex程式整合；Claude獨立審查 |
| #147正式組員包 | 現有A/B1 v0-pilot24圖／60空白文字列可試填，正式r004 v1仍等#115／#118 | Codex產包；組員出題／答案／T-F |
| 正式評估 | #123／#129／#138／#89程式已交；還需凍結正式系統輸出、組員獨立標註／劇本，再在評估端比對 | 程式與人工工作分開；PILOT／SYNTHETIC不進正式分母 |
| #83交接文件 | head bda073d仍待修改：無Git/JSON的CSV流程、D68–71現況、Q1/Q3出題與Q4審聲明的區分 | 原文件作者；Codex已留言needs changes |
| #124與週日交付 | 正式端到端browser acceptance、色覺模擬／灰階、Demo腳本改寫、Claude審B項與staging，再走主線整合 | Claude；Codex補工程阻塞，mainline/main仍不動 |
| OpenAI API | **延後：系統完整後才接入測試，不是目前應先開工的項目** | 使用者已決定順序；之後另補adapter／資料與provider契約 |

目前最先需要解除的外部依賴是 #145 的原kit對齊，以及 #117 的獨立圖／ROI完成收據；可獨立推進的程式方向是真Qwen接線，但須保留目前Draft與契約邊界。多步驟Agent編排／摘要屬建議擴充，是否納入後續工作另行排定，不把它們偷偷加入原清單的完工條件。

新HSV #158曾因G6／Q-19獨立檢查及核定未成立而被自動審批拒絕合併，仍保留Draft。這不是缺D70渲染授權，也不能以本次模型選擇或問答整理替代核定。
