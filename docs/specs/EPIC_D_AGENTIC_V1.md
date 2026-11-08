# Epic D 設計稿 v1：讓「Agentic 驅動」可被客觀驗證（`EPIC_D_AGENTIC_V1`）

- 狀態：**PROPOSED 設計稿**，只含設計與驗收測試規格，無實作。Refs [#489](https://github.com/Polalalabear/amidst/issues/489)。
- 基準：`origin/claude/445-demo-integration@1fdc1a4`（下文「@1fdc1a4」皆指此）；新 UI 結構取自 PR #487 `claude/ui-redesign-v1@b49fb6e`。
- 優先序：大問題 A（#445）優先；本文件不阻擋 A，也不改 `Q_CORE_SEARCH_TRACK_V1` 的 wire。
- 規則：每個數字附來源；無資料寫 UNKNOWN。GT 不進 LLM 輸入（DEVELOPMENT_RULES、契約 §0.4）。

## 1. 現況盤點

### 1.1 自主但屬於規則的行為

| 行為 | 實作 | 來源 |
| --- | --- | --- |
| case2 單畫面切鏡（起點、續看、換鏡、GAP、LOST） | 純函式，固定排序規則 | `docs/contracts/Q_CORE_SEARCH_TRACK_V1.md` §3.5；`src/amidst/q1q5/core_query.py@1fdc1a4` `single_view_sequence` |
| case1 命中與排序 | 地點 `covered_regions` ∩ 偵測索引，固定排序 | 契約 §2.2 |
| 盲區預測 | 物理預測（直線／節點圖），信心一律 LOW | 契約 §3.6、§4.3 |
| Q5 舊追蹤的 RULE_ONLY／RULE_FALLBACK 切鏡 | `RuleController` | `src/amidst/q1q5/q5_agent.py@1fdc1a4` `_decider()`、`_fallback()` |
| Q3 規則解析 | `parsed_by='RULE'` | `src/amidst/q1q5/q3_parse.py@1fdc1a4` L122 |

### 1.2 有 LLM 但實際沒有生效的地方

| 位置 | 現況 | 來源 |
| --- | --- | --- |
| Q5 `AgentController`（`AGENT_SEQUENTIAL`） | 已有工具迴圈（`get_search_context`、`get_candidate_evidence`、`get_observation_summary`、`submit_decision`）、預算、退回、`RecordedProvider` 重播。只有設 `AMIDST_Q1Q5_OLLAMA_RUNTIME`＋SHA 時才綁定；預設不綁 | `q5_agent.py@1fdc1a4` L73–285；`src/amidst/q1q5/ollama_runtime.py@1fdc1a4` L113–131 |
| Q5 預算 | `agent_call_timeout_ms` 2000、`agent_total_budget_ms` 5000、`agent_max_rounds` 3、`agent_max_illegal_submissions` 2、`session_max_agent_rounds` 12（APPROVED） | `configs/q1q5/parameter_set_v1.json@1fdc1a4` |
| Qwen3 1.7B 在該預算下 | 18/18 次在 2000 ms deadline 逾時；不設上限重跑 Q3 中位數 5.777 s、Q5 中位數 7.992 s | `docs/engineering/QWEN3_UNTRUNCATED_DIAGNOSTIC_20261025.md@1fdc1a4`；#479 內文第 3 點 |
| 前端 fixture 唯一的 Agent 例子 | `decided_by: AGENT` 兩次都被拒（`ILLEGAL_ORDER`），最後 `RULE_FALLBACK`／`ILLEGAL_CANDIDATE` | `frontend/workbench-v2/fixtures/q2-agent.json@1fdc1a4` |
| Q3 LLM 解析 | `parser_mode: LLM_WITH_RULE_FALLBACK` 存在；無 provider 時 `fallback='PROVIDER_UNAVAILABLE'`。輸出是舊 Q1/Q2 結構，不是 `q-core` 請求 | `q3_parse.py@1fdc1a4` L107、L140–173 |
| OpenAI | `OpenAIPredictionAdapter` 預設 `enabled=False`；只回「下一台鏡頭」猜測，`used_for: DISPLAY_ONLY`，不進決策；只接受 Q2 response。repo 內沒有任何啟動腳本傳入 `openai_prediction_adapter=`，demo 中一律 `DISABLED` | `src/amidst/q1q5/openai_prediction.py@1fdc1a4` L1–5、L304–340；`src/amidst/q1q5/api.py@1fdc1a4` L173、L654–675 |
| 核心查找／追蹤 | `q_core_search`／`q_core_track` 完全不呼叫 LLM | `api.py@1fdc1a4` L641–652 |

結論：目前沒有任何一條 demo 路徑由 LLM 實際做決定。

## 2. 「Agentic」的可驗證定義

一條路徑稱為 Agentic，必須**同時**滿足 A1–A6，且每一條都有自動測試（§9）：

| # | 條件 | 怎麼驗 |
| --- | --- | --- |
| A1 | **LLM 選工具**：下一步呼叫哪個工具、帶什麼參數由 LLM 輸出決定，不是固定順序 | 換一份錄製回應，工具序列跟著變（T-U3） |
| A2 | **看結果再決定**：第 n+1 步的輸入包含第 n 步工具結果 | 步驟紀錄 `input_refs` 含前一步 `result_sha256`（T-U4） |
| A3 | **步驟留紀錄**：每步記 decided_by、工具、參數、結果 hash、耗時 | schema 驗證（T-U1） |
| A4 | **逾時退回規則**：超過預算或輸出不合法時，交給現有規則，並標 `RULE_FALLBACK` 與原因 | 注入逾時／壞輸出（T-U5、T-U6） |
| A5 | **畫面看得到**：UI 顯示每一步，分得出 LLM／規則／退回 | E2E（T-E1–T-E3） |
| A6 | **可重播**：同一份錄製檔不連 LLM 也產生 byte 相同的步驟與結果 | T-U7 |

另外必須遵守：LLM 只能呼叫 §4 的工具；不讀 GT；最終輸出仍是 `identity_verdict: UNCONFIRMED`、結果標 `EXPLORATORY`（D128）。

## 3. 第一版路徑

**推薦：(a) 追蹤跟丟時由 LLM 規劃找回，加上 (b) 自然語言轉選單（使用者確認後才執行）。(c) 延後。**

| 候選 | 為什麼 |
| --- | --- |
| **(a) 跟丟找回** | 唯一真正「看結果再決定下一步」的路徑（A1、A2）；可直接重用 Q5 已有的工具迴圈、預算、`RecordedProvider` 設計；觸發點明確（`single_view` 最後一段是 `LOST`，契約 §3.5 規則 6）；跟丟後是離線重播，延遲可接受（§6）。 |
| **(b) 自然語言轉選單** | 單次呼叫、使用者確認才執行，風險最低；對應 RQ3 與 #480；現有 Q3 解析器與錄製重播（`RecordedParseProvider`）可沿用。單獨不足以稱 Agentic（沒有多步），所以和 (a) 搭配。 |
| (c) 俯視圖點教室 | 依賴 #481 與多教室顯示座標（契約 O4，尚未提供）；點教室後只是一次 `q_core_search`，LLM 規劃價值低。待 O4 完成後當 v2。 |

## 4. 工具介面（LLM 唯一可用的能力）

全部只包裝現有 API：`q_core_search`、`q_core_track`（契約 §2、§3）與 camera graph（`q_camera_map`，`docs/contracts/DEMO_UI_SUPPORT_V1.md` §2.4）。伺服器端執行，LLM 不得傳 session、路徑、score、門檻、GT 鍵；這些由伺服器從目前 session 補上。所有工具輸出只含白名單欄位（沿用 `openai_prediction.FORBIDDEN_KEYS` 檢查）。

| 工具 | 輸入 schema | 輸出 schema | 包裝 |
| --- | --- | --- | --- |
| `get_camera_neighbors` | `{camera_id: string∈graph}` | `{camera_id, neighbors:[{camera_id, region_id}], covered_regions:[region_id]}` | camera graph |
| `search_window` | `{camera_ids: string[1..4]∈graph, range_us:[int,int]（必須在 [lost_at_us, as_of_us) 內，長度 ≤ 60 000 000）}` | `{status, hits:[{camera_id, source_range_us, target_observed, evidence_state}], not_evaluated:[{camera_id, reason}]}` | `q_core_search`（`feature` 固定為原追蹤特徵，`time` 由 `range_us` 換算） |
| `resume_track` | `{camera_id, from_us:int}` | `{status, single_view_tail:[段], as_of_us}` | `q_core_track`（`region_ids` 取該鏡頭涵蓋區域） |
| `get_blind_estimate` | `{}` | 契約 §4.4 `estimate` 的 `candidates`、`confidence` | `q_core_track.blind` |
| `finish` | `{outcome: "REACQUIRED"\|"GIVE_UP", camera_id?: string, reason: string≤200}` | — | 結束；`REACQUIRED` 的 `camera_id` 必須出現在某次 `search_window` 的 `target_observed:true` 命中 |

路徑 (b) 只有一個工具：`propose_query` 輸出 `{kind:"search"|"track", form:{start,end,regionIds,classLabel,colorLabel}}`，由前端既有 `buildCoreSearchRequest`／`buildCoreTrackRequest`（契約 §5）驗證；不合法就顯示規則解析結果。使用者按「確認」後才送出。

驗證規則：每次 LLM 輸出必須是 `{tool, arguments}`，工具名在白名單、參數過 schema；否則記 `INVALID_RESPONSE` 並計一次違規（沿用 Q5 `agent_max_illegal_submissions` 的作法）。

## 5. 步驟紀錄與重播

### 5.1 紀錄格式 `q-core.agent-trace.v1`

```json
{
  "schema_version": "q-core.agent-trace.v1",
  "trace_id": "agt-…", "path": "LOST_RECOVERY",
  "trigger": {"track_output_sha256": "…", "lost_at_us": 30000000, "as_of_us": 42000000},
  "provider": {"kind": "OLLAMA|OPENAI|RECORDED|NONE", "model": "qwen3:1.7b", "model_digest": "…或 null",
               "template_sha256": "…", "options": {"temperature": 0, "seed": 7}},
  "budget": {"call_timeout_ms": 0, "total_budget_ms": 0, "max_steps": 0},
  "steps": [
    {"step": 0, "decided_by": "LLM|RULE|RULE_FALLBACK|USER", "tool": "search_window",
     "arguments": {"…": "…"}, "input_refs": ["前一步 result_sha256"],
     "llm_call": {"request_sha256": "…", "raw_output_sha256": "…", "latency_ms": 0, "validation": "OK|TIMEOUT|INVALID_RESPONSE|ILLEGAL_TOOL"},
     "result_sha256": "…", "result_summary": "2 台命中", "fallback_reason": null}
  ],
  "outcome": {"status": "REACQUIRED|GIVE_UP|RULE_FALLBACK", "camera_id": "…或 null", "decided_by": "LLM|RULE_FALLBACK"},
  "labels": {"evidence": "EXPLORATORY", "identity_verdict": "UNCONFIRMED", "gt_read": false},
  "content_sha256": "…"
}
```

- `content_sha256 = canonical_hash(trace, exclude=('content_sha256',))`（沿用 `store.canonical_hash`）。
- 紀錄**不得**含 API key、Authorization header、完整 prompt 以外的環境變數；prompt 與原始輸出只存 hash，原文放 LOCAL 錄製檔。

### 5.2 錄製與重播

- 錄製檔 `q-core.agent-recording.v1`：`[{request_sha256, request, raw_output, latency_ms, error_code}]`，比照 `RecordedProvider`（`q5_agent.py@1fdc1a4` L51–70）：輸入不符就 `ReplayMismatch`，不修補；用完要 `assert_consumed`。
- 重播時 `provider.kind = RECORDED`，UI 顯示「錄製重播」；`latency_ms` 顯示錄製值並註明。
- Demo 預設走重播（D126「離線索引加重播」）。

## 6. 延遲預算與逾時退回

| 量測 | 值 | 來源 |
| --- | --- | --- |
| Qwen3 1.7B，2000 ms deadline | 18/18 逾時 | QWEN3 診斷文件 |
| Qwen3 1.7B 不設上限，Q3 | min 5.366／中位數 5.777／max 10.427 s（n=12） | 同上 |
| Qwen3 1.7B 不設上限，Q5 | min 7.804／中位數 7.992／max 10.430 s（n=6） | 同上 |
| Qwen 生成時拖慢偵測 | 3.114 → 0.554 fps（−82.2%） | #479 內文第 3 點 |
| Qwen3 0.6B／4B 延遲 | UNKNOWN（未量） | — |
| OpenAI 延遲 | UNKNOWN（未量）；adapter 上限 5.0 s | `openai_prediction.py@1fdc1a4` L323 |
| 每條路徑實際步數 | UNKNOWN | — |

**規則**

1. 預算參數新增為 PROPOSED（不改既有 APPROVED 的 Q5 值）：`epicd_call_timeout_ms`、`epicd_total_budget_ms`、`epicd_max_steps`。數值待 Codex 量測後填（§10 C-2）；量到之前一律 UNKNOWN，設計上允許「探索組」放寬（#482）。
2. 任一呼叫逾時、輸出不合法、違規達上限、或總預算用完 → 立即退回規則：路徑 (a) 退回「維持 `LOST`，顯示物理預測」（契約 §3.6，不另造規則搜尋）；路徑 (b) 退回規則解析／手動選單。`outcome.decided_by = RULE_FALLBACK`，`fallback_reason ∈ {TIMEOUT, TIME_BUDGET, INVALID_RESPONSE, ILLEGAL_TOOL, PROVIDER_UNAVAILABLE, DISABLED}`。
3. 依現有數字，Qwen3 1.7B 單次呼叫中位數 5.8–8.0 s，多步路徑 (a) **不能即時跑，只能離線錄製後重播**；(b) 單次呼叫，現場等候 UNKNOWN 秒級（中位數 5.777 s 是 Q3 舊 prompt 的值），列為「可即時但需提示等候」，demo 仍以重播為預設。
4. 即時模式下 LLM 不得與偵測同時跑（避免 −82.2% 吞吐，#479）；demo 現場本來就不跑偵測，此條只影響本機錄製。

## 7. 模型選項

| 選項 | 用途 | 規則 |
| --- | --- | --- |
| `RECORDED` | demo 預設 | 不連網、不連 Ollama |
| `OLLAMA` Qwen3 0.6B／1.7B／4B | 本機錄製、探索組 | 沿用 `OllamaProvider`＋pinned digest（`llm_provider.py`、`ollama_runtime.py`）；只連 loopback |
| `OPENAI` | opt-in | 預設關；後台開關＋`enabled=true` 才讀 `OPENAI_API_KEY`（只從環境變數）；key 不印、不進紀錄、不進錄製檔、`__repr__` 不含 key（沿用 adapter L335、L369 的做法）；只送工具結果摘要，不送影格、GT、劇本（D128） |
| `NONE` | 關閉 | 全走規則 |

模型與 provider 寫進 `trace.provider`；UI 顯示模型名。

## 8. 前端呈現（新 UI，PR #487）

依 `ui-shell.mjs@b49fb6e` 結構：

- **路徑 (a)**：case2 `#ui-case2` 的右側 `aside.ui-track-aside` 目前有 `#ui-floorplan` 與 `#ui-journal`（追蹤紀錄）。在 `#ui-journal` 之下新增卡片 `#ui-agent-steps`（「找回步驟」），只在 `status: LOST` 且有 trace 時出現。每列：時間、工具中文名、結果摘要、來源 chip。
- **路徑 (b)**：查詢窗 `#ui-q-search`／`#ui-q-track` 卡片頂端新增一行文字輸入與「解析」按鈕；解析後把選單填好並顯示來源 chip，使用者按既有「開始查找／開始追蹤」才送出。
- **來源 chip**（三種，不得同色）：`LLM 決定`、`規則`、`退回規則：<原因>`；另加 provider chip `錄製重播`／`Qwen3 1.7B`／`OpenAI`。
- 樓層圖：LLM 查過的鏡頭在 `#ui-floorplan` 加淡色外框；推論仍用虛線（契約 §4.4），LLM 不得產生曲線。
- 不改 `ui-shell.mjs` 既有元素 id；新卡片用新模組 `agent-steps-view.mjs`＋純模型 `agent-steps-model.mjs`。

## 9. 驗收測試規格

全部可用 fixture／錄製回應跑，不連 LLM。比照契約 §7：模組未實作時 skip，`AMIDST_REQUIRE_IMPL=1` 時 fail；skip 代碼 `EPICD_AGENT_MODULE_MISSING`、`EPICD_FRONTEND_MODEL_MISSING`。

| ID | 類型 | 情境 | 通過條件 |
| --- | --- | --- | --- |
| T-U1 | Python | 合成 LOST fixture＋錄製回應跑完 | trace 過 `q-core.agent-trace.v1` schema；`content_sha256` 正確 |
| T-U2 | Python | 工具輸入含 GT 鍵、`session_ref`、score、未知鏡頭 | 拒絕，記 `ILLEGAL_TOOL`，不呼叫底層 API |
| T-U3 | Python | 同一 fixture、兩份不同錄製回應 | 工具序列不同（A1） |
| T-U4 | Python | 任一 LLM 步 | `input_refs` 含前一步 `result_sha256`（A2） |
| T-U5 | Python | 錄製第 2 步 `error_code: TIMEOUT` | `outcome.decided_by = RULE_FALLBACK`、`fallback_reason = TIMEOUT`；追蹤回應仍 200 且等於無 Agent 時的結果 |
| T-U6 | Python | 錄製輸出非 JSON／工具名不在白名單／`finish` 指向未命中的鏡頭 | `INVALID_RESPONSE`／`ILLEGAL_TOOL`；達上限後退回 |
| T-U7 | Python | 同一錄製重播兩次 | 兩份 trace byte 相同；錄製被改一個字元 → `ReplayMismatch` |
| T-U8 | Python | OpenAI provider `enabled=false`；或 env 有 key 但 mode=RECORDED | 不讀 key；trace／錄製／log／`repr` 都不含 key 字串（以假 key `sk-test-DO-NOT-LOG` 檢查） |
| T-U9 | Python | 所有 trace | `labels.gt_read=false`、`identity_verdict=UNCONFIRMED`、`evidence=EXPLORATORY`；遞迴無 `FORBIDDEN_KEYS` |
| T-U10 | Python | 路徑 (b) 錄製回應 → `propose_query` | 結果過 `buildCoreSearchRequest` 等價的伺服器驗證；不合法時退回規則解析並標退回 |
| T-N1 | node | `agent-steps-model` 吃 trace | 每步產生 `{text, source:'LLM'|'RULE'|'FALLBACK', reason}`；三種來源 class 不同 |
| T-N2 | node | (b) 解析結果 | 只填表，不送出；送出必須經使用者點擊 |
| T-E1 | E2E（新 UI） | 錄製 LOST 情境 | `#ui-agent-steps` 出現，列數等於 trace 步數，至少一列 `LLM 決定` |
| T-E2 | E2E | 錄製 TIMEOUT 情境 | 出現 `退回規則：TIMEOUT` chip；樓層圖仍是物理預測虛線 |
| T-E3 | E2E | (b) 輸入一句話 → 解析 → 確認 | 選單被填好；未按確認前沒有 `q_core_*` 請求；按下後恰一次 |
| T-E4 | E2E | provider `NONE` | 不出現 Agent 卡片；既有 case1／case2 E2E 不變 |

## 10. 風險與不做的事

**風險**
- Qwen3 小模型多步工具呼叫的合法率 UNKNOWN（唯一 fixture 例子兩次 `ILLEGAL_ORDER`）。緩解：工具少、schema 嚴、違規即退回。
- 重播被質疑「不是真的 LLM」：trace 記 model digest、錄製檔 hash，並保留一次本機現場跑的紀錄。
- 延遲：多步 (a) 現場跑不了，demo 只能重播（§6）。

**不做**
- 不讓 LLM 改切鏡規則（契約 §3.5）、排序、門檻、物理預測曲線。
- 不送影格給任何模型；不做身分判定。
- 不把結果算進 H1 或研究評估（D128 EXPLORATORY）。
- (c) 俯視圖點教室、非人物追蹤（#422）不在 v1。

## 11. 工作拆分與勾選清單

| 項目 | 誰 | 理由 |
| --- | --- | --- |
| C-1 錄製 (a)(b) 回應：Qwen3 0.6B／1.7B／4B 各跑合成＋真實 LOST 情境，產生錄製檔與延遲表 | Codex（本機 Ollama、真實資料） | 需要模型與本機資料 |
| C-2 依 C-1 填 `epicd_*` 預算 PROPOSED 值 | Codex 量，Claude 寫入 | 數字要來自量測 |
| C-3 OpenAI 實際連線一次（使用者設 key） | Codex＋使用者 | 外部資源 |
| K-1 `src/amidst/q1q5/agent_recovery.py`：工具、迴圈、預算、退回、trace、重播 | Claude | 純模組，fixture 可測 |
| K-2 schema `q-core.agent-trace.v1`／`agent-recording.v1` | Claude | 契約 |
| K-3 Python 測試 T-U1–T-U10 | Claude | |
| K-4 前端 `agent-steps-model/view.mjs`、查詢窗文字輸入，T-N1–T-N2 | Claude | |
| K-5 E2E T-E1–T-E4（錄製 fixture） | Claude | |
| K-6 API route `q_agent_recovery`（重播優先）＋後台開關 | Claude 寫，Codex 在真實資料上驗 | |

建議貼到 #489 的勾選清單：

```markdown
### Epic D v1（EPIC_D_AGENTIC_V1）
- [ ] 使用者決定第一版路徑（推薦 (a)+(b)）與 demo 模式（推薦錄製重播）
- [ ] K-2 trace／recording schema
- [ ] K-1 agent_recovery 模組（工具、預算、退回、重播）
- [ ] K-3 Python 驗收 T-U1–T-U10
- [ ] K-4 前端步驟卡與自然語言輸入，T-N1–T-N2
- [ ] K-6 API route 與後台開關
- [ ] C-1 Codex 本機錄製 Qwen3 0.6B／1.7B／4B 回應與延遲
- [ ] C-2 預算 PROPOSED 值（依 C-1）
- [ ] K-5 E2E T-E1–T-E4
- [ ] C-3 OpenAI opt-in 實連一次（使用者設 key）
```

## 12. 需要使用者決定

1. 第一版路徑：**(a)+(b)（推薦）**／只做 (b)／(a)+(b)+(c)。
2. demo 模式：**錄製重播（推薦）**／現場跑 Qwen（(b) 單步）／現場跑 OpenAI。
3. 錄製用模型：**Qwen3 1.7B（推薦，有歷史數字）**／4B（品質可能較好，延遲 UNKNOWN）／0.6B。
