# Q1–Q5 第一版：搜尋、非法提交與兜底上限提案

日期：2026-10-20（Asia/Taipei）。**PROPOSED，供使用者核定；不是預設值、效能實測或已核准契約。**

依據：[#92 審查 N2](https://github.com/Polalalabear/amidst/pull/92#issuecomment-6286061631)、[#86 契約 §8／§11](https://github.com/Polalalabear/amidst/blob/258c7e2cf24b37ab69a5c4578fe23cc5f000d724/docs/contracts/Q1_Q2_FIRST_DEMO_V1.md)，以及使用者本次允許先做獨立提案。#86 正由 Claude 修訂；名稱／schema 如有變化，以固定新版確認後同步，不直接編輯其 owner 檔案。

## 1. 待核定的第一版初值

沿用 #92 已有提案：`top_k=3`、`agent_max_rounds=3`、`agent_total_budget_ms=5000`、`agent_call_timeout_ms=2000`。本文件補齊 N2；所有值都是 **PROPOSED**。

| 參數 | 提案值／單位 | 計數或計時範圍、理由 |
| --- | --- | --- |
| `agent_max_illegal_submissions` | **2 次** | 每次 SEARCHING 中被 Controller 拒絕的提交累計；第 2 次立即轉兜底。拒絕同時計入既有 Agent 輪數與5秒總預算，不另給重試額度。保留一次修正 schema／ref 的機會，避免反覆空轉。 |
| `search_window_us` | **6,000,000 µs（來源6秒）** | 固定來源窗口，從該次 TEMP_LOST 第一個缺格的來源 timestamp 起，裁切到同 run／clock 的 query／run 結束；不讀路線、事件速度或 GT，不以這6秒當人體通過預測。窗內的有效切鏡觀測仍不得讓播放頭倒退。 |
| `research_interval_us` | **1,000,000 µs（來源1秒）** | RETURNED_TO_ORIGIN 後原鏡頭仍無有效連接，至少前進1秒來源時間才可開新快照；避免同一段來源時間重複輪詢。來源時間暫停時，不因牆鐘走了1秒就重查。 |
| `session_max_research_rounds` | **6 次 SEARCHING** | 同一 Q2 session 內累計，包含重搜與手動改選開出的新搜尋。開到第6次後不能再開第7次；目前搜尋仍受其自身與 session 時間預算限制。選6僅是短 Demo 的有限工作量提案，不是路線覆蓋保證。 |
| `fallback_max_candidates`（新增提案名） | **最多3個，且不超過該快照剩餘 top-k** | 從既有游標開始，不回頭重查 Agent 已接受 NEXT_CANDIDATE 的項目、不翻下一頁或擴張集合；既有取證可重用。3與top_k初值對齊，但不是候選集合完整性聲明。 |
| `fallback_total_budget_ms`（新增提案名） | **1,000 ms（monotonic 執行時間）** | 每次兜底的總工作時間，含 store 查取／guard／紀錄；每個操作只能用剩餘時間，重試不重置。逾時停止取證，保留缺口與未評估候選，不能把沒查到當無人。未量測，不承諾實際1秒內完成全部候選。 |
| `session_total_search_budget_ms`（新增提案名） | **30,000 ms（累計搜尋工作時間）** | 累計所有 SEARCHING／兜底的執行時間，含等待 provider／store；不計正常播放與使用者閱讀畫面的時間。不可由手動改選、快照更新、retry 或局部預算重置清零。用於約束6次搜尋的總成本，哪個上限先到就先停止。 |

新提案名需由 Claude 寫入 #86 下一版後確認，不暗稱已存在 wire。Store／provider 需有可取消或有界的剩餘時間 timeout；超過 deadline 的實際耗時須記錄，不能只截斷回報計時而假裝沒有超限。

## 2. 邊界、用完預算與紀錄

- **兩種時間分開：**`search_window_us`／`research_interval_us` 是來源時間；Agent、provider、fallback 與 session 搜尋預算是 monotonic 執行時間。6秒來源窗不能拿來延長5秒 Agent 預算，亦不代表推論要在查詢時現跑；第一版仍只查離線索引。
- 每次 SEARCHING 的 Agent 部分最多3輪／5000 ms，單次 provider 最多2000 ms；第2次非法提交可更早觸發兜底。工具要求／重試／格式錯誤都照 #86 規則計入輪數。**3輪不保證取完3個候選**，尤其工具往返本身會耗輪數；不得為完成top-k而偷偷追加呼叫。
- Agent 轉兜底後只可使用同一合法快照與窗口；兜底最多3候選／1000 ms。局部 Agent＋兜底提案額度至多5000＋1000＝6000 ms；這不是量測結果，亦不把 provider 或阻塞 I/O 超時藏掉。
- 6次局部額度合計可到36,000 ms，但 **session 的30,000 ms累計上限優先**，所以不保證能跑滿6次。RULE_ONLY 不呼叫 Agent，但仍受每次兜底1000 ms、6次搜尋及session累計上限約束。
- 用完候選或局部時間後回原鏡頭的目前來源時間並保留暫失；未取證、NOT_INFERRED、NOT_SAMPLED、MISSING、UNKNOWN 及截斷範圍各自明示。達到session次數／時間上限時應結束並有可區分原因；新增 reason-code 名稱由 #86 定稿，不在此私設已實作 enum。
- 手動改選可終結舊決策並開新有界 SEARCHING，但要記 `decided_by: USER`、新 seed／decision／snapshot，**不可重置 session 累計次數與時間**；不是 Agent 自動重試。`agent_used`／`agent_attempted`／`fallback_reason`、prompt／模型 digest／工具證據與每層預算用量須保留。
- 所有模式同用合法候選、D28順序與核定的切鏡guard；本提案不放寬 MATCH_STRONG、不啟用 Agent Demo、不更改 IoU／HSV、索引率或圖。D64 的規則例外仍需使用者核准合併後才生效。

## 3. 尚待證據與核准

6秒來源窗、1秒重搜與6次session不是依事件腳本、人體速度或實際路線推算；目前沒有量測能證明覆蓋完整。使用者可核定為第一版初值，再以**授權的 RGB preview**與操作耗時做獨立新版本調整，保留舊結果／參數 hash；不看 GT／人工標註來選答案。

Qwen 呼叫速度、store讀取與紀錄開銷尚未量測，因此5000／2000／1000 ms可能提早走兜底；應如實標示「規則回退」與原因，不因此增大上限。正式 parameter_set 的值／單位／run／clock／取樣／批准來源／hash 都需由新版 #86 明訂。本次沒有輸出可執行參數檔或改任何產品預設值。

D41 仍適用：任何推論／下載／渲染前先記 `df -h`；可用量低於12 GiB不得開始渲染／preview、低於8 GiB停止產製。此任務起點 available 11,488,144 KiB（約10.96 GiB）；不做推論、下載或渲染，不動 r004、finalization／權重／PG，不執行 §9 清理。

## 4. 實際產出 / Actual output

- Model / effort: Codex（GPT-6）；精確模型變體／effort UNKNOWN。
- PR / commits: `codex/q1q5-search-budget-proposal`，base `mainline/q1q5` @ `f481fe0`；限定本文件的 Draft PR，實際 SHA／PR 於發布回報；不合併／rebase／force。
- Files changed: 僅本文件，新增缺少的上限提案與計數／時間語意；未改 #86 owner 檔案或產品程式。
- Commands run and results: `df -h .`／`df -k .`；固定版本 #86 與 #92 N2 唯讀核對；文件空白、連結、必填提案名稱／數字與預算算術檢查、`git diff --check`。沒有模型／Ollama呼叫、render、download 或產品測試。
- Artifacts: LOCAL `/Users/polalabear/amidst-artifacts/q1q5-search-budget-proposal-20261020/` 只存小型收據；所有工作在資產 repo 主 checkout，無新 worktree／source snapshot／環境。
- 本次新增的磁碟用量: 新增文件 UTF-8 正文 **8243 bytes**；外部驗證收據配置用量於 PR 描述回報，Git metadata 未獨立計量。無媒體、索引、權重或套件新增。
- Verified: 所有提案保持 PROPOSED；來源時間和執行時間分開；非法提交、重試、手動重選不繞過局部與session上限；36秒局部額度受30秒session累計限制。這是文件檢查，不是Controller執行驗證。
- Not verified: 參數尚未經使用者核定；#86 新版、合約符合性測試包固定入口尚未交付；本次沒有API實作，不宣稱該測試包已通過。未量測 Agent／store／fallback耗時、覆蓋率或切鏡品質。
- Deviations, UNKNOWN items and follow-ups: 新欄位／結束原因由 Claude 合入契約草案後再確認；後續程式PR送出前須跑其固定版本符合性測試包。保留原README與untracked，提案不代表產品可開啟Agent或場景可渲染。
