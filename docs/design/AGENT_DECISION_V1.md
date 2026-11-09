# Agent 決策設計稿 v1（DRAFT）

- 狀態：**DRAFT，設計稿**。依 D152，實作等大掃除後才開始；本文不改任何程式行為。
- 基準：`mainline/q1q5`＠`2616661`（Merge #485）。
- 作者／Model / effort：Claude Code，Opus 5.5 / medium。
- 附件：
  - schema 草案 [`docs/contracts/schemas/q-core.agent-decision.v1.draft.schema.json`](../contracts/schemas/q-core.agent-decision.v1.draft.schema.json)（DRAFT）
  - 決策點計數腳本 [`scripts/design/count_agent_decision_points.py`](../../scripts/design/count_agent_decision_points.py)（設計證據，不是正式評估）
- 規則：事實附出處；查不到的寫 `UNKNOWN`；需要大掃除後才能確認的路徑寫「大掃除後確認」。GT 只用來評分。程式不寫入、不輸出 API key。

---

## 0. 一句話

v1 只把**有限選項的決策**交給 LLM：
- **DP1**：切鏡時要選哪一個候選人，或不切；
- **DP3**：是否接受一段低信心的延續框。

LLM 只看推論可以用的摘要，輸出先用 schema 驗證，不合法、逾時或超出預算就退回規則，每次退回都記下原因。對照組是純規則演算法。

---

## 1. 決策點

### 1.1 現況（有出處的事實）

| 事實 | 出處 |
| --- | --- |
| 跨鏡頭關聯是 `associate()`，純規則，只用輸入的值物件，不做檔案或網路 I/O | `src/amidst/q1q5/cross_camera_demo.py:1-5,92` |
| 現在的鏡頭還看得到人時，黏在現在的鏡頭，不換（記 `CURRENT_CAMERA_STILL_OBSERVED`） | 同檔 `:121-127` |
| 跟丟後，每個有索引的時間點都**重掃所有鏡頭**的 local track | 同檔 `:128-161`，docstring `:93` |
| 候選人只看兩條規則：(1) 顏色和目前的 track 有交集；(2) 時間差不能是負的。有拓樸邊、而且時間差 ≤ `handoff_max_gap_us`（預設 6 s）時標為 `CROSS_CAMERA_HANDOFF`，否則標 `CROSS_CAMERA_REACQUISITION` | 同檔 `:144-150`、`Parameters` `:29-34` |
| 有兩個以上合格候選人時，每個都記 `AMBIGUOUS_HANDOFF`，**這一格不切鏡**（`continue`） | 同檔 `:160-167` |
| 只有一個合格候選人時就切過去，記 `DEMO_ASSOCIATION_HYPOTHESIS` | 同檔 `:168-173` |
| 延續框（`BOX_CONTINUATION`）跟著被選中的鏡頭序列一起輸出，顏色記 `NOT_EVALUATED`；算顏色時跳過延續框 | 同檔 `:117-119,180-185` |
| 身分一律 `UNCONFIRMED`，物理導航 `UNKNOWN` | 同檔 `:154,252` |
| 協定的 fallback profile `RULE_ONLY_RTDETR_V1` 中切鏡和解析都是 `RULE_ONLY`；demo 實際跑的也是規則路徑 | `configs/q1q5/baseline_v1_protocol.json:366-374` |
| 已有的決策紀錄 enum：`decision_source` ∈ {AGENT, RULE_FALLBACK, RULE_ONLY, USER}；`fallback_reason` ∈ {ROUND_LIMIT, TIME_BUDGET, PROVIDER_UNAVAILABLE, PROVIDER_TIMEOUT, INVALID_RESPONSE, ILLEGAL_CANDIDATE, EXPLANATION_INVALID, MODE_NOT_AUTHORIZED} | `src/amidst/contracts/q_demo/schemas/common.v2.schema.json` `$defs/decision_source`、`$defs/fallback_reason` |
| OpenAI 介接只用在顯示（外部推測線），支援 LIVE／REPLAY，逾時上限 5 s；模型名稱來自 `AMIDST_OPENAI_MODEL`，目前未選定 | `src/amidst/q1q5/openai_prediction.py:311-338`；`docs/contracts/DEMO_UI_SUPPORT_V1.md:178,311` |
| 本機 Qwen3 Agent 在 2000 ms 上限下 18 次呼叫全部逾時；拿掉逾時後 Q5 中位數是 7.992 s | #489 本文；PR #397 計畫 §3.12（分支 `claude/model-experiment-plan`＠`e6c6ad02`） |

### 1.2 候選決策點

| 代號 | 決策 | 輸入 | 輸出 | 現在的規則做法 | 交給 LLM 預期能改善什麼 |
| --- | --- | --- | --- | --- | --- |
| **DP1** | 切鏡裁決：選哪一個候選人，或不切 | 目前 track 的摘要（鏡頭、最後一次看到的時間、顏色、分數）、每個候選人的摘要（鏡頭、時間差、有沒有拓樸邊、link 種類、顏色、分數、延續框比例）、拓樸邊 | `SELECT <candidate_id>` 或 `ABSTAIN` | 0 個合格候選人：不切；1 個：直接切；≥2 個：記 `AMBIGUOUS_HANDOFF`，不切 | (a) 歧義時能綜合時間差、拓樸和分數做選擇，不必一律放棄，可以提高跨鏡頭召回；(b) 只有一個候選人時能否決明顯不合理的切換（例如沒有拓樸邊、時間差很長、幾乎全是延續框），可以減少誤切 |
| DP2 | 跟丟後先找哪一支鏡頭 | 最後位置、拓樸、各鏡頭最近的觀測 | 鏡頭的排序 | 每個時間點都重掃全部鏡頭，沒有順序（`:128-161`） | 只有在搜尋有預算（即時、每步只能查 k 支鏡頭）時才有差。用凍結索引重播時，全部鏡頭都會掃到，**排序不會改變結果**，所以現在量不到效益 |
| **DP3** | 是否接受一段低信心的延續框 | 這一段的時間、幀數、框分數摘要，前後的偵測摘要，所屬 track 的顏色 | `ACCEPT_SEGMENT`／`REJECT_SEGMENT` | 被選中的 track 上，延續框全部接受（`:180-185`） | 拒絕不可靠的延續段可以提高每鏡頭的精確度，也會影響單畫面在那段時間停在哪支鏡頭 |
| DP4 | 查找結果的排序和解說 | Q1 命中列表與分數 | 排序後的列表加上解說 | 依分數排序（`src/amidst/q1q5/q1_search.py`；細節不在本文範圍） | 解說比較好讀。但 D152 已暫停自然語言轉選單；解說沒有可以用 GT 評分的標準答案 |

### 1.3 v1 挑 DP1（主要）和 DP3（次要）

1. **選項有限、可以驗證**：DP1 的答案只能是請求裡列出的候選 id 或 `ABSTAIN`；DP3 只有兩個選項。schema 加上「id 必須在請求裡」就能完全擋住幻覺。
2. **有可以用 GT 評分的標準答案**：「候選 track 是不是目標人物」以及「這段延續框裡是不是目標人物」，都可以由只用來評分的模組從 GT 算出來（§4.4），不需要人主觀判斷。
3. **直接影響核心指標**：DP1 影響跨鏡頭召回和切鏡比例；DP3 影響每鏡頭的精確度和召回（D126 的核心是追蹤和查找）。
4. **呼叫次數少**：現有兩個 run 跑完整重播，DP1 有 16 次、DP3 有 30 次（§4.1），本機模型就算一次要 8 s，也能在可以接受的時間內跑完。
5. **為什麼不挑 DP2、DP4**：DP2 在重播時量不到差異；DP4 已被 D152 暫停，而且解說沒有標準答案。這兩個留到 v2。

DP1 是主要假設（對應 #397 的 M1／H1-Q2）。DP3 是次要，只報點估計和 CI，不做主要檢定。

---

## 2. 輸入與安全邊界

### 2.1 LLM 看得到什麼

一律只給**當下時間以前**（`timestamp_us < as_of_us`，與 `associate()` 的因果規則相同，`:103`）的推論摘要：

| 欄位 | 來源 |
| --- | --- |
| 鏡頭 id、首次／最後看到的時間、時間差 `gap_us` | local track 的觀測（`Observation.timestamp_us`） |
| 顏色（WEAK／STRONG 的顏色名稱） | 偵測的 `color.verdicts`（`scripts/run_cross_camera_demo.py` `load_run`） |
| 分數摘要（n、min、median、max） | `Observation.score` |
| 延續框比例 | `evidence_kind == 'BOX_CONTINUATION'` 的比例 |
| 拓樸邊、圖的核准狀態 | 靜態 camera graph（`metadata/graphs/camera_graph_v3_1.json`），狀態 `GRAPH_NOT_APPROVED` |
| 規則的答案 | 同一個請求下 `associate()` 的結果（讓 LLM 知道 baseline；§3.4 有拿掉這個欄位的消融組） |

**不給**：GT、`gt_private/`、劇本、visibility、depth、renderer 軌跡、`actor_id`、檔案路徑、原始 `track_ref`、影像像素。

- 候選 id 由請求產生器**重新編號**成不透明的 `A1`、`B2`……（schema 的 `opaque_id`），避免 track 名稱洩漏任何資訊。對照表只存在請求產生器的記憶體和錄製檔裡，不會進 prompt。
- 請求產生器沿用 `run_cross_camera_demo.reject_protected` 的禁用鍵清單（`FORBIDDEN`，`scripts/run_cross_camera_demo.py:22-23`），並加上 schema 的 `additionalProperties:false`／`unevaluatedProperties:false` 雙重保護。
- v1 只送文字摘要，不送影像。送到 OpenAI 的內容只有上表的數值和 id。

### 2.2 輸出驗證

- 模型的回應必須符合 schema 的 `$defs/response`：`action`、`candidate_id`（只在 SELECT 時給）、1–4 個 `reason_codes`（封閉 enum）、`rationale`（≤240 字）。
- 額外檢查：
  - `SELECT` 的 `candidate_id` 必須在請求裡出現；
  - DP1 不能回 `*_SEGMENT`，DP3 不能回 `SELECT`／`ABSTAIN`；
  - 任何身分相關的欄位（例如 `identity`）都會被 schema 拒絕。
- 不合法時：`decision_source=RULE_FALLBACK`，`fallback_reason` 記 `INVALID_RESPONSE`（格式錯）或 `ILLEGAL_CANDIDATE`（id 不在清單）。
- OpenAI 用 structured output（`response_format` 的 JSON schema 模式）；Ollama 用 `format=<schema>`（`src/amidst/local_agent/provider.py:99-100` 已有同樣的做法）。即使 provider 端有約束，我們這邊仍然重新驗證一次。

### 2.3 逾時、預算與退回

沿用已核定的值（#397 §3.12；`configs/q1q5/parameter_set_v1.json`＠staging `434e579`）：`agent_call_timeout_ms`＝2000、`agent_total_budget_ms`＝5000、`agent_max_rounds`＝3、`session_max_agent_rounds`＝12。**這些值還沒綁到 r004 的 run（`run_bound_approval`＝UNRESOLVED）**，列為未決問題 Q2。

| 情況 | 結果 | `fallback_reason` |
| --- | --- | --- |
| 模式不是 AGENT（預設） | 用規則答案 | 不記（`decision_source=RULE_ONLY`） |
| 模式未授權（例如 LIVE 但沒有設定模型） | 用規則答案 | `MODE_NOT_AUTHORIZED` |
| 單次呼叫超過 2000 ms | 丟掉遲到的回應，同一步可以重試 | `PROVIDER_TIMEOUT`（記在 attempt） |
| 一步用完 3 次 | 用規則答案 | `ROUND_LIMIT` |
| 一步超過 5000 ms | 用規則答案 | `TIME_BUDGET` |
| 整個 session 呼叫次數用完 | 之後全部用規則答案 | **新增** `CALL_BUDGET_EXHAUSTED` |
| 連不到 provider | 用規則答案 | `PROVIDER_UNAVAILABLE` |
| REPLAY 時找不到對應的錄製 | 用規則答案 | **新增** `REPLAY_MISS`（`openai_prediction.py:433` 已在用） |

- 新增的兩個 enum 值要經 Codex 確認後才能寫進 `common.v2`；在這之前只出現在 DRAFT schema。
- 評估的探索組可以放寬逾時（#397 D121-B），但要另外成組，不能和正式組混在一起報。

### 2.4 身分

- 請求和紀錄裡的 `identity_verdict` 是常數 `UNCONFIRMED`。
- LLM 選了某個候選人，只代表「選擇了這個關聯假設」，在 sightings 裡標 `association_state=SELECTED_HYPOTHESIS`（與現有欄位一致，`:229`），不會寫成同一個人。

### 2.5 接進 `associate()` 的方式（給 WP2）

- 新增可以注入的 `decider`；預設是 `RuleDecider`，行為和現在逐 byte 相同。
- DP1 在 `:160` 之前呼叫：把合格的候選人，加上規則判為顏色不相容但時間差合法的列（只當資訊，標 `rule_eligible=false`，不能被選）都交給 decider。
- `SELECT` 時 `row['reason']='AGENT_ASSOCIATION_HYPOTHESIS'`；`ABSTAIN` 而規則原本會切時，記 `AGENT_REJECTED_HANDOFF`。
- DP3 在建 sightings 的迴圈（`:174-196`）裡，以「連續的延續框段」為單位決定，不是逐格決定。

---

## 3. 模型對比設計

### 3.1 比較的系統

| 組別 | 內容 | 出處／狀態 |
| --- | --- | --- |
| **R0** 規則 baseline | 現在的 `associate()`：歧義時 ABSTAIN，單一候選人時接受，延續框全部接受 | `cross_camera_demo.py` |
| **R1** 加強版規則 | R0 加上決定性的平手規則：時間差最小 → 有拓樸邊 → 分數中位數最高 → id。DP3：延續框比例超過門檻就拒絕 | **新增**。用來回答「LLM 是否只是贏過『放棄』」；門檻要在看資料以前固定 |
| **O-small／O-large** | OpenAI 的兩個等級。確切的模型名稱**待使用者選定**（`AMIDST_OPENAI_MODEL` 目前未選，`DEMO_UI_SUPPORT_V1.md:311`）。條件：支援 JSON schema structured output，可以設定 seed 和 temperature。跑的當天把 API 回應裡的 `model` 欄位逐筆錄下來 | UNKNOWN（待選） |
| **Q-0.6／Q-1.7／Q-4／Q-8** | 本機 Ollama 的 Qwen3：0.6B、1.7B（`qwen3:1.7b-q4_K_M`，現行模型，`llm_provider.py:125`）、4B、8B | M4 的範圍（D121-E，#397 §6.5） |
| **L-3B／P-3.8B** | Llama 3.2 3B、Phi-4-mini 3.8B | 同上，M4 範圍，標 `EXPLORATORY` |

**M1–M4 的定義**（出處：PR #397 `docs/research/MODEL_EXPERIMENT_PLAN_20261102.md`＠`e6c6ad02` §3–§6.5；#425 本文只寫「依 #397 跑」；PR #397 狀態是 CLOSED、沒有合併；`argon/425-research-m1-m4-baseline`＠`15ac140` 的報告開頭已更正為合成治具，數字是 UNVERIFIED／NOT_RUN）：

| 代號 | #397 的定義 | 在本設計的對應 |
| --- | --- | --- |
| M0 | Baseline `RULE_ONLY` | R0 |
| M1 | Q2 追蹤決策：`RULE_ONLY` 對 `AGENT_SEQUENTIAL`，H1 用固定模型 `qwen3:1.7b-q4_K_M`，ITT，FB>20% 時降級 | **DP1 主要比較**：R0 對 Q-1.7（正式組，預算 2000／5000／3） |
| M2 | Q5 切鏡評分器 v1 對 v2 | 不是決策系統，是評分器。這裡當成**評分敏感度分析**：同一批決策用 v1、v2 各算一次 |
| M3 | Q3 LLM 查詢解析對規則解析 | **不在 v1 範圍**（D152 暫停自然語言） |
| M4 | 候選模型比較（Qwen3 0.6B／1.7B／4B／8B、Llama 3.2 3B、Phi-4-mini 3.8B），探索性 | Q-*、L-3B、P-3.8B 這幾組 |

「M1–M4 組合」在本設計解讀為：M1 的流程 × M4 的模型清單，加上 M2 的評分敏感度。#425 的分支只有合成治具，沒有可以沿用的實測數字。

### 3.2 指標

計分單位是「決策點題目」（§4）。下表盡量沿用 #397 §1.7 的代號。

| 指標 | 定義 | 單位 |
| --- | --- | --- |
| `Acc_dp`（決策正確率） | final_answer 等於標準答案的題數 ÷ 計分題數。DP1 的答案空間是 {候選 id, ABSTAIN}；如果標準答案裡沒有任何候選人是目標，ABSTAIN 才算對 | % |
| 每鏡頭召回 `R_cam` | 用決策後的 sightings，每支鏡頭「目標實際在場的時間」中被輸出覆蓋的比例，再對各鏡頭平均（macro）並另報 micro | % |
| 切鏡比例 | 沿用 D150 的單畫面切鏡比例定義（現有指標），另外報誤切率 `FS`（次／分鐘，#397 §1.7） | %、次／分鐘 |
| 延遲 P50／P90 | 每次呼叫的牆鐘時間和每個決策步的牆鐘時間，兩者分開報 | ms |
| 每題成本 | OpenAI：從回應的 `usage` 取 token 數，乘上**跑的當天由使用者提供、附日期和來源的價目表**；沒有價目表就寫 UNKNOWN，不估。本機：每題的 GPU 或 CPU 秒數 | USD／題、s／題 |
| 重跑一致性 `Cons_K` | 同一題 LIVE 跑 K＝5 次，5 次答案都相同的題數比例；另報 Fleiss κ | %、κ |
| 重播一致率 `R_hash` | REPLAY 重跑後，決策紀錄的 `content_sha256` 相同的比例。**閘門：必須是 100%** | % |
| 退回比例 `FB` | `decision_source=RULE_FALLBACK` 的步數 ÷ Agent 組的步數，依 `fallback_reason` 分開列 | % |
| `TO`、`SI` | 逾時率、schema 失敗率（分母是呼叫次數，#397 §1.7） | % |

### 3.3 錄製與重播

- 每個請求做 canonical JSON（`sort_keys`、`separators=(",",":")`、`ensure_ascii`，與 `openai_prediction.py`、`run_cross_camera_demo.canonical` 相同），取 `request_sha256`。
- LIVE 時把 {`request_sha256`, request, 原始回應, provider, model, model_digest, seed, temperature, candidate_order_seed, wall_ms, usage} 寫進 JSONL 錄製檔。
- REPLAY 只依 `request_sha256` 取回應，不做任何網路呼叫；找不到就是 `REPLAY_MISS` → 退回規則。
- **同一題重跑比對**：K 次 LIVE 用不同的 `candidate_order_seed`（候選人的順序隨機排列，並記下 seed），用來抵消位置偏誤；但 request 的雜湊要排除順序（以候選人集合計算），這樣 K 次可以對應到同一題。
- 每次評估輸出一份 manifest：輸入的 byte pin、程式 commit、參數集的 SHA、環境 manifest（沿用 `amidst.experiment-env.v1`，`docs/contracts/schemas/amidst.experiment-env.v1.schema.json`）、錄製檔的 SHA。

### 3.4 對照的公平條件與消融

- 所有組別使用相同的請求檔案（同一份 `request_sha256` 清單）、參數集和預算；延遲要在同一台機器上交錯量測（#397 §3.2）。
- 消融：A1 拿掉請求裡的 `rule_answer`（看 LLM 是否只是照抄規則）；A2 打亂候選人順序（看位置偏誤）。
- 統計方法沿用 #397 §1.5：配對的單尾精確符號檢定、bootstrap 依 run 分群、Holm 校正；判定標籤用 §1.6。

---

## 4. 評估題庫

### 4.1 現有事件的決策點（實際數出來的）

**方法**：用 `scripts/design/count_agent_decision_points.py`（SHA-256 `40d8fed3…69d1`）。這個腳本透過 `run_cross_camera_demo.load_run` 讀 demo job 釘住的輸入（job 檔 SHA-256 `651906f9…d49e`，與 `configs/demo_integration_local.json:7` 一致），以現在的 `associate()`、`DEMO_DEFAULT` 參數跑到每個 run 的結尾，統計稽核紀錄。過程不讀 GT、影像、模型或網路。輸出檔 SHA-256 `c5243951…d6ad`（LOCAL）。

| 事件 | 鏡頭數（有 track 的） | 跨鏡頭事件（`DEMO_ASSOCIATION_HYPOTHESIS`，單一候選人） | `AMBIGUOUS_HANDOFF` 時間點（每點候選數） | `AMBIGUOUS_FIRST_SEED` | 延續框觀測／連續段 | 單畫面 GAP 段數 |
| --- | --- | --- | --- | --- | --- | --- |
| A4-1（`ctrl-lcorr-s1-a4-5fps-v1-r004-d124-v1`，50 s） | 3 | 8 | 0 | 0 | 105／11 | 6 |
| B4-1（`ctrl-lcorr-s1-b4-5fps-v1-r004-d124-v1`，42 s） | 5 | 6 | 2（2、2） | 0 | 132／19 | 3 |
| B-05（P1 工程場景） | 2 | 不經過 `associate()`；P1 路徑的預錄是 1 次 SWITCH（`docs/agents/Q1Q5_DEMO_SCRIPT.md:36`） | — | — | — | — |

**DP1 題目數**：A4-1 有 8 題（單一候選人），B4-1 有 6＋2＝8 題，合計 **16 題，其中只有 2 題是歧義題**。**DP3 題目數**：11＋19＝**30 段**。DP2 如果之後要做，候選題數就是 GAP 段數，共 9 段。

> 注意：較舊的 fixture `tests/q1q5/fixtures/d139-index-diagnostics.engineering.json`（D145，`base_head` `5d6afd2`）記的是 A4-1 有 1 個歧義時間點、B4-1 沒有，與現在的數字不同。這表示決策點的數量會隨演算法版本改變，題庫一定要綁定 commit 和參數集。

### 4.2 需要多少題

**假設**：主要檢定是 Agent 組對規則組的配對單尾精確符號檢定，α＝0.05；在答案不一致的題目裡，Agent 贏的比例是 0.75（與 #397 §1.5 相同）。

1. **檢定力**（#397 §1.5 的表）：不一致的題數要 ≥30，檢定力才有 0.89；10–29 題只能判 `INCONCLUSIVE_UNDERPOWERED`；<10 題判 `INSUFFICIENT`。
2. **換算成總題數**：總題數 n ≈ 不一致題數 ÷ 不一致率 d。
   - 對 R0：只有歧義題才會不一致（R0 的 ABSTAIN 對上 LLM 的 SELECT），加上 LLM 否決單一候選人的題目。如果 d≈0.3，n≈100；d≈0.2，n≈150。
   - 對 R1：預期 d 比較低（例如 0.15），n≈200。
3. **估計精度**：要讓 `Acc_dp` 的 95% CI 半寬 ≤10 個百分點，n ≥ 1.96²×0.25÷0.1² ≈ **96**（p＝0.5 時最保守）。
4. **群集效應**：同一個 run 裡的題目彼此不獨立，所以用依 run 分群的 bootstrap。只有 2 個 run 的時候，群集 CI 沒有意義，**至少要 10 個 run**。設計效應 DEFF＝1＋(m−1)ρ；假設每個 run 有 m≈12 題、ρ≈0.1，DEFF≈2.1，有效樣本數會少一半左右。
5. **目標**：DP1 **≥200 題、≥10 個 run，其中歧義題 ≥60**；最低門檻是計分題 ≥20（低於這個數一律 `INSUFFICIENT`，#397 §1.6）。DP3 ≥150 段。

**結論**：現有的 16 題（2 題歧義）遠遠不夠。現在的場景大多只有一個人，所以很少出現歧義；要補題目，關鍵是**多人而且顏色相近**的場景。

### 4.3 怎麼補題目，以及對 GT 隔離的影響

| 方法 | 做法 | 增加的題數（估計） | GT 隔離的影響 |
| --- | --- | --- | --- |
| S1 整理現有的渲染 | 把 `cx7-d119`、`cx7-d124`、r005（`d127-418-office-expanded-r005`）等 safe bundle 裡其他 run 建成索引和 local track，再跑計數腳本 | UNKNOWN（各 bundle 有多少 run、多少人，**大掃除後確認**） | 不變。這些 bundle 本來就是 safe bundle（`gt_read=false`），只要繼續用 `reject_protected` 擋就好 |
| S2 track 層級的合成干擾 | 從其他 run 拿 local track，平移時間、改鏡頭，插進來當干擾候選人；也可以改顏色標籤製造顏色相近的情況。產生器只讀 safe 索引 | 可以控制，例如每個真實決策點加 1–3 個干擾 | 「哪個是插進來的」是**由構造得知的標籤**，不是 GT，但等同答案，必須和 GT 一樣隔離：寫進只給評分用的檔案（例如 `scoring_private/`），決策程式和 prompt 都讀不到。合成題要另外標 `SYNTHETIC_PERTURBATION`，報告分開列，不能和真實題混在一起當主要結果 |
| S3 新的多人渲染 | 在 Blender 做 2–4 人交錯、顏色相近、同時進出盲區的場景 | 每個 run 預估 10–20 題（UNKNOWN，要先試做） | 渲染和 GT 產生是 Codex 的範圍，要另外授權。GT 照舊放在 `gt_private/` |
| S4 真實影片 | 現有的真實影片（如果有授權的話） | UNKNOWN | 沒有 GT，只能用人工參考答案 |

建議順序：S1（成本最低）→ S2（快速補到統計門檻，但只算次要結果）→ S3（主要結果的正式來源，需要授權）。

### 4.4 標準答案從哪來

- **主要：只用於評分的 GT 對應**。獨立的評分模組（在單獨的程序裡執行，不被決策程式 import）讀 `gt_private/`，對每個 local track 的每個觀測，用框和 GT 投影的 IoU 對應到 actor，多數決得到 track→actor 對照。DP1 的答案是「候選人中對應到目標 actor 的那一個；沒有就是 ABSTAIN」；DP3 的答案是「這段延續框中對應到目標 actor 的幀數 ≥50% 就 ACCEPT」。
- **IoU 的門檻、多數決的門檻**要在看結果以前固定，寫進評分參數集。
- **對應不清楚的題目**（例如 IoU 介於 0.3 和 0.5 之間，或多數決不到 60%）改用**人工參考答案**：兩個人各自標註，報告 Cohen's κ，意見不一致時由第三人裁決。這類題目要另外標記。
- 真實影片（S4）只有人工參考答案。
- 評分模組的輸出只有 `{request_sha256, correct: bool}` 和匯總指標，不回寫任何 actor 資訊到決策端。

---

## 5. 為什麼不能用 LLM 當評判標準

1. **它沒有比受測系統更多的資訊**：如果評判只看到同樣的推論摘要，它只是另一個受測系統，量到的是「兩個模型一致的程度」，不是正確率。
2. **給它 GT 就違反隔離**：要讓評判判得準就得給它 GT，但 GT 一旦進了 prompt，就可能被 provider 端快取或記錄（OpenAI），也可能被誤用到推論路徑，違反「GT 只用在評分」（`docs/DEVELOPMENT_RULES.md`）。
3. **偏誤**：同一家族的模型會偏好自己的答案（自我偏好）；評判也有位置偏誤、偏好長答案的問題。
4. **不可重現**：評判本身不決定性，換版本分數就跟著變，評分標準不能是一個會漂移的東西。
5. **循環論證**：用 LLM 去證明「LLM 決策比較好」，結論不成立。

**LLM 在評估裡可以扮演的角色**（都不進入正確率的計算）：

- **標註草稿**：在人工參考答案的流程裡，先由 LLM 產生草稿（記 `label_source=LLM_DRAFT`），由人逐題確認或修改。報告要寫出修改率；草稿不能讓評分者看到是哪一組產生的。
- **標出分歧題**：各組答案不一致、K 次重跑不穩定（`Cons_K` 低）、或理由碼和答案矛盾的題目，自動列成清單，優先給人工檢查。
- **解說品質的初篩**：DP4 之後如果要評解說，可以由 LLM 依規則先篩一輪，最後由人判定。
- **錯誤歸類**：把錯誤的題目依理由碼分群，幫忙寫錯誤分析（敘述性的，不是指標）。

---

## 6. 執行環境與檔案清單

### 6.1 誰在哪裡跑

| 環境 | 跑什麼 | 說明 |
| --- | --- | --- |
| **Mac（本機）** | R0、R1、OpenAI LIVE 錄製、全部 REPLAY、評分（讀 GT 的評分模組只在這裡跑）、圖表 | API 金鑰由使用者自己設在環境變數 `OPENAI_API_KEY`；轉接器只在送出請求時從環境變數取值放進 header（`openai_prediction.py:336`），程式不把金鑰寫進檔案、log 或錄製，也不輸出。Claude 和 Codex 都不讀、不印這個值 |
| **Windows（外包機）** | 本機模型（Ollama）：Q-0.6、Q-1.7、Q-4，以及記憶體夠的話 L-3B、P-3.8B | #425 分支報告寫的 Windows 環境是 20 核、31.75 GiB RAM、**沒有 GPU**（該報告標 UNVERIFIED）。CPU 跑 4B 以上會很慢，要先做小量試跑 |
| **Colab（GPU）** | Q-4、Q-8，以及 Windows 跑不動的模型 | GPU 型號和配額 UNKNOWN，跑的當天記到環境 manifest |

外包機**只產生錄製檔**（請求→回應），不帶 GT，也不評分；評分統一在 Mac 做（#397 §7.1）。

### 6.2 各環境要準備的檔案

v1 的決策只需要凍結的索引和 local track，**不需要影像，也不需要 RT-DETR**（偵測已經在索引裡）。

| 檔案 | 路徑（`$OWNED`＝`~/amidst-artifacts/demo-owned-v1`） | 大小（bytes） | SHA-256 | 取得方式 | Mac | Win | Colab |
| --- | --- | --- | --- | --- | --- | --- | --- |
| camera graph | `$OWNED/metadata/graphs/camera_graph_v3_1.json` | 25,262 | `e250413a…8409`（job 檔釘住） | 複製 | ✓ | — | — |
| A4-1 index | `$OWNED/data/indexes/A4-1/detection_index.json` | 3,220 | `b6f708fb…cf67` | 複製 | ✓ | — | — |
| A4-1 records | `…/A4-1/detection_index.records.jsonl` | 601,214 | `46238842…09f0` | 複製 | ✓ | — | — |
| A4-1 local tracks | `…/A4-1/cx8_rule_only.json` | 22,021 | `6fe9c482…4ce8` | 複製 | ✓ | — | — |
| A4-1 receipt | `…/A4-1/demo_default_receipt.json` | 14,901 | `3ecbe7a0…33a7` | 複製 | ✓ | — | — |
| A4-1 config | `$OWNED/metadata/config/A4-1-config.json` | 14,131 | `37bbd88b…166c` | 複製 | ✓ | — | — |
| A4-1 clock | `$OWNED/data/artifacts/r004-cx7r-20261104-01a19f8b/bundle/safe_bundle/clocks/r004_a4_d124_v1.json` | 722 | `0f69b149…db26` | 複製 | ✓ | — | — |
| B4-1 index | `…/B4-1/detection_index.json` | 3,436 | `f92e22f1…0379` | 複製 | ✓ | — | — |
| B4-1 records | `…/B4-1/detection_index.records.jsonl` | 837,465 | `c2b8bfa0…524f` | 複製 | ✓ | — | — |
| B4-1 local tracks | `…/B4-1/cx8_rule_only.json` | 48,849 | `4ba6ed7c…03d6` | 複製 | ✓ | — | — |
| B4-1 receipt | `…/B4-1/demo_default_receipt.json` | 16,025 | `59f4ddf3…4ada` | 複製 | ✓ | — | — |
| B4-1 config | `$OWNED/metadata/config/B4-1-config.json` | 15,293 | `f8578fc2…1494` | 複製 | ✓ | — | — |
| B4-1 clock | `…/clocks/r004_b4_d124_v1.json` | 722 | `91bd3fe3…29d2` | 複製 | ✓ | — | — |
| **請求檔**（題庫，由 WP4 產生；已經是去識別化的摘要） | 大掃除後確認（建議 `$ARTIFACTS/agent-decision/requests_v1.jsonl`） | UNKNOWN | 產生時寫進 MANIFEST | WP4 產生 | ✓ | ✓ | ✓ |
| 評分參數集、對應表 | `scoring_private/`（只在 Mac） | UNKNOWN | 產生時記錄 | WP4 | ✓ | **不帶** | **不帶** |
| GT | `gt_private/`（路徑大掃除後確認） | — | — | 現有 | 只給評分模組 | **不帶** | **不帶** |
| 決策參數集 | 大掃除後確認（建議 `configs/q1q5/agent_decision_params_v1.json`） | UNKNOWN | git blob | WP1 | ✓ | ✓ | ✓ |
| Qwen3 1.7B（Ollama） | `$OWNED/models/ollama/blobs/sha256-3d0b7905…6ab6`，manifest `…/manifests/registry.ollama.ai/library/qwen3/1.7b-q4_K_M` | 1,359,279,776；manifest 859 | blob `3d0b7905…6ab6`；manifest `8f68893c…30e7`（`$OWNED/copy-manifest.json`） | `ollama pull qwen3:1.7b-q4_K_M` 後比對 digest，或複製 | — | ✓ | ✓ |
| Qwen3 0.6B／4B／8B、Llama 3.2 3B、Phi-4-mini 3.8B | 外包機的 Ollama 模型目錄 | UNKNOWN | 以 `ollama pull` 後 `/api/tags` 回報的 digest 為準，記進環境 manifest | `ollama pull` | — | ✓ | ✓ |
| Ollama 執行檔 | 系統安裝 | — | 記錄版本 | 官方安裝程式 | — | ✓ | ✓ |
| Python 執行環境 | repo 的 `uv.lock`；Python 3.12（`configs/demo_integration_local.json` 記 3.12.12） | — | `uv.lock` 的 git blob | `uv sync` | ✓ | ✓ | ✓ |
| 執行腳本 | WP3／WP6 產生（建議 `scripts/agent_decision/run_provider.py`、包裡的 `run.py`） | — | 包 MANIFEST | WP6 | ✓ | ✓ | ✓ |

> 表中的 SHA-256 為縮寫（前 8 碼…後 4 碼）；完整 64 碼以 `$OWNED/metadata/cross-camera-job.json`（SHA-256 `651906f9ca18a02d8efd300eb9cef57877ad8da758d9a323b590f82feb86d49e`）裡的 pin 為準，大小是 2026-11-09 在本機量的 `os.path.getsize`。

外包機只拿**請求檔**，不需要上面的索引和 local track。請求檔由 Mac 產生，已經只剩 §2.1 列出的欄位，所以外包包不含任何原始索引。

### 6.3 Colab／Windows 包的結構（依 D136）

```
agent-decision-pack_<OS>_<YYYYMMDD>/
├── README.md                 # 中文；三節：工作內容／要上傳的檔案／操作步驟（另加「不要改」）
├── MANIFEST.json             # 每個檔案的 SHA-256；分成不可變 payload 和 RETURN 兩類
├── 01_requests_v1.jsonl      # 上傳清單第 1 項：題庫請求（去識別化摘要）
├── 02_agent_decision_params_v1.json   # 第 2 項：參數集（預算、溫度、K）
├── 03_models.txt             # 第 3 項：要 pull 的模型 tag 和預期 digest
├── 04_agent_decision.ipynb   # Colab 版；每一格開頭都有中文註解說明在做什麼
├── run.py                    # Windows 版的跨平台入口
├── tools/
│   └── verify_pack.py        # 驗 MANIFEST；回收時也用它判斷 VALID／INVALID
└── RETURN/
    └── README.txt            # 指定回傳檔名：agent-decision_<OS>_<YYYYMMDD>.zip
                              #   內含 recordings/*.jsonl、env_manifest.json、run.log
```

- README 的「要上傳的檔案」依上表的 01→04 編號，每一項附 SHA-256。
- 包裡**不含** GT、劇本、`gt_private/`、`scoring_private/`、影像或原始索引。`verify_pack.py` 要掃檔名和 JSON 的鍵，有禁用鍵就判 INVALID（沿用 `FORBIDDEN` 清單）。
- 依「團隊交接包格式」記憶：一定要有 README 的三節，以及指定的 RETURN 檔。

---

## 7. 實作工作包

依 D126 的分工：Claude 寫契約和測試，Codex／Argon 實作；只用 merge commit；每個 PR 以測試當閘門。

| WP | 範圍 | 驗收測試 | 建議模型分級 | 依賴 |
| --- | --- | --- | --- | --- |
| **WP1 契約與驗證器** | 把 DRAFT schema 定稿（請 Codex 確認新的 enum 值）；純函式的 `validate_request`、`validate_response`、`RuleDecider`；fallback 狀態機（§2.3 的表） | schema 的正例和反例向量（GT 鍵、`actor_id`、身分欄位、id 不在清單、超過字數都要擋）；§2.3 每一列各一個測試；身分永遠 `UNCONFIRMED` | 契約定稿：Opus medium；程式：Sonnet medium | 無（大掃除後第一個） |
| **WP2 接進 `associate()`** | 注入 decider；DP1、DP3 的請求產生器（不透明 id、只取 `as_of` 以前的資料）；新的稽核 reason | **回歸**：預設 `RuleDecider` 下，A4-1、B4-1 的 `response()` 輸出逐 byte 和現在相同（輸出 SHA 寫進測試）；請求裡找不到任何 `FORBIDDEN` 鍵；用假的 decider 強制選擇，檢查 chain 和稽核紀錄 | Sonnet medium（Codex 實作） | WP1 |
| **WP3 Provider、錄製和重播** | OpenAI（structured output）和 Ollama 轉接器；預算和逾時；JSONL 錄製器和重播器；`CALL_BUDGET_EXHAUSTED`、`REPLAY_MISS` | 用假的 transport：逾時、格式錯、id 不合法、預算用完都會退回並記錄原因；同一份錄製重播 3 次，`R_hash`＝100%；log 和錄製檔裡找不到 `OPENAI_API_KEY` 的值（用假金鑰測） | Sonnet medium | WP1（可以和 WP2 平行） |
| **WP4 題庫和評分模組** | 擴充計數腳本成題庫產生器（輸出請求 JSONL＋MANIFEST）；S1／S2 補題；獨立程序的 GT 評分模組和人工標註表 | 決策端的程式不能 import 評分模組（靜態檢查）；題庫的每一題都能通過 request schema；評分模組在一個小的人工 fixture 上算出預期的答案 | 設計：Opus medium；程式：Sonnet medium | WP1、WP2 |
| **WP5 評估執行與報告** | 跑所有組別（Mac 部分）；指標、bootstrap、符號檢定、圖表；分歧題清單 | 指標在固定的小 fixture 上算出手算的值；報告裡每個數字都能追到錄製檔的 SHA；`R_hash`＝100% 才放行 | Sonnet medium（量測）；結果解讀和判定：Opus medium | WP3、WP4 |
| **WP6 Windows／Colab 包** | 依 §6.3 打包；`verify_pack.py`；回收流程 | 包裡的禁用鍵掃描是 0；在 Mac 上用 Q-0.6 試跑 notebook 的前 5 題成功；回收的 zip 能通過 `verify_pack.py` | Sonnet medium；打包的機械工作：Haiku low | WP3、WP4 |

**順序**：WP1 → (WP2 ∥ WP3) → WP4 → (WP5 ∥ WP6)。同時寫檔的 session 最多 2–3 個（依現行規則），而且不能碰同一組檔案。

---

## 8. 風險與未決問題

### 8.1 風險

| 風險 | 影響 | 緩解 |
| --- | --- | --- |
| 題目太少，尤其是歧義題（現在 2 題） | 主要假設只能判 `INSUFFICIENT` | §4.3 的 S1→S2→S3；合成題分開報 |
| 本機 Qwen 在 2000 ms 內跑不完（歷史上 18/18 逾時） | `FB` 接近 100%，正式組變成規則組 | 照實報告（FB>20% 降級，#397 §3.3）；探索組放寬逾時另外報；用 Colab GPU 量真正的能力 |
| OpenAI 模型版本漂移、seed 不保證決定性 | 重跑結果不同 | 逐筆記 `model`；用 REPLAY 保證報告可以重現；`Cons_K` 照實報 |
| 資料送到外部 | 隱私 | v1 只送數值摘要和不透明 id，不送影像；使用者在 LIVE 之前要確認 |
| GT 從旁門漏進來（track 名稱、檔名、評分模組被 import） | 結果無效 | 重新編號 id；`FORBIDDEN` 掃描；靜態檢查 import；GT 只在 Mac 的評分程序裡 |
| LLM 只是照抄 `rule_answer` | 高估或低估 Agent | 消融 A1 |
| 候選人的位置偏誤 | 答案受順序影響 | 隨機順序並記 seed；消融 A2 |
| 決策點數量隨演算法版本改變（§4.1 注意） | 題庫和程式對不上 | 題庫綁 commit 和參數集的 SHA |
| Windows 沒有 GPU | 4B 以上跑不完 | 大模型放 Colab；先小量試跑 |

### 8.2 未決問題（需要決定的人）

| # | 問題 | 誰決定 |
| --- | --- | --- |
| Q1 | OpenAI 要比哪兩個模型（O-small／O-large）、總預算上限 | 使用者 |
| Q2 | 2000／5000／3 的預算綁到 r004 的 run（`run_bound_approval`＝UNRESOLVED） | 使用者 |
| Q3 | 新增 `CALL_BUDGET_EXHAUSTED`、`REPLAY_MISS` 到 `common.v2` 的 enum | Codex 確認 |
| Q4 | 是否授權 S3（多人新渲染） | 使用者授權，Codex 執行 |
| Q5 | 人工參考答案由誰標註（兩人＋裁決） | 使用者 |
| Q6 | R1 的平手規則和 DP3 的門檻（要在看資料以前固定） | Claude 提案，使用者確認 |
| Q7 | 各 safe bundle 裡可以用來補題的 run 數 | 大掃除後確認 |
| Q8 | OpenAI 價目表的來源與日期（算每題成本用） | 使用者在跑的當天提供 |
