# 模組上的模型實驗分析企劃（事先登錄版）

- 日期：2026-11-02
- 狀態：**PLANNED／NOT_RUN**。本文件只是企劃，沒有呼叫任何模型、沒有渲染、沒有推論。demo（11-04）之後、資料到位才執行，不進 11-03 批次。
- 作者：Claude Opus 5.5 / high（Claude 負責評估工具、統計與圖表；模型呼叫與 Agent orchestration 歸 Codex）
- base：`codex/q1q5-staging`＠`434e57922a24d2422226871c0bb672dc7bc3584b`
- 引用格式：`路徑＠commit`，SHA-256 寫在後面。LOCAL 表示只在本機、不在 repo。

## 0. 這份企劃要回答什麼，以及不做什麼

研究目標是檢驗「Agent／LLM 的能力大於 RULE」。這是**待檢驗的假設**，不是預設結論。本企劃在看到任何實驗資料之前，就把假設、對照組、主要指標、門檻、樣本數和檢定寫死。結果不論是 Agent 贏、打平、輸，或資料不足，都照第 1.6 節的判定標籤原樣報告。

三個模組：

| 模組 | 比較 | 主要假設 |
| --- | --- | --- |
| M1 | Q2 追蹤決策：`RULE_ONLY` vs `AGENT_SEQUENTIAL`（Qwen3） | H1-Q2 |
| M2 | Q5 切鏡評分器 v1 vs v2 | H-S（評分器一致性），**不是 H1** |
| M3 | Q3 解析：`RULE_ONLY` vs `LLM_WITH_RULE_FALLBACK`；Q1 檢索命中率 | H1-Q3、H1-Q1 |

不做：改評分器、改門檻來配合結果、把工程場景（SYNTHETIC／ENGINEERING）的結果推論到正式場景、把 GT 送進任何決策路徑。

## 1. 三個模組共用的規則

### 1.1 事先登錄與修訂

1. **凍結點**：本文件推上 PR 的那個 commit 就是事先登錄版本。分析腳本（Claude）要先用 SYNTHETIC fixture 寫完、測完，把腳本的 SHA-256 記在結果紀錄裡，然後才讀真實資料。
2. **修訂**：看到資料前可以修訂，但要另開 commit，寫明理由。看到資料後的任何新分析一律標 `EXPLORATORY`，不能改判主要假設。
3. **主要指標只有一個**（每個假設一個），其餘都是次要或描述。次要指標顯著不能拿來補主要指標的不顯著。

### 1.2 對照組公平性

兩組必須在下面每一項都相同，任何一項不同，該次比較就判 `INVALID_COMPARISON`，不計入：

| 項目 | 要求 |
| --- | --- |
| 輸入 | 同一份 request（`request_sha256` 相同）、同一份凍結索引、同一個 `candidate_snapshot_sha256`。候選集合和排序由決定性模組產生，Agent 不排序、不增刪（`docs/specs/DEVELOPMENT_RULES.md`＠`994b700`，D64 例外條） |
| 參數 | 同一個 `parameter_set_sha256`，只有 `switch_mode`（或 Q3 的 `parser_mode`）不同 |
| 時間預算 | 每一步的決策期限相同。Agent 的輪數與逾時上限用使用者已核定的值，實驗中**不另外放寬**；放寬要當成另一組（見第 6 節決定 B） |
| 硬體與環境 | 同一台機器、同一個模型 digest、同一個 Ollama 版本；量延遲時兩組輪流交錯執行，避免溫機或背景負載偏向一組 |
| 重複 | `RULE_ONLY` 是決定性的，跑 1 次並用 2 次重跑確認 hash 相同；Agent 每個輸入跑 K＝5 次，每次的 seed 和溫度都記錄 |

### 1.3 GT 隔離

- 決策端（Q2／Q3／Q5 控制器、Agent、Q3 parser）只讀錄製、凍結索引和 request。GT、渲染軌跡、visibility、depth 一律不進入（`docs/specs/DEVELOPMENT_RULES.md`＠`994b700` 第 57、64 行）。
- 正確答案只在評分端讀：Q5 用外部撰寫並凍結的劇本，Q1／Q3 用人工標註的答案。評分器本身已經是 evaluation-only（`src/amidst/evaluation/q5_switch_eval.py` 開頭寫明不 import 推論、模型、RGB；`q3_parse_eval.py`、`q1_query_eval.py` 同樣）。
- 執行順序固定成兩段：**先**由 Codex 產生並凍結兩組的決策錄製（記 SHA-256），**後**由 Claude 的評分端讀劇本／答案計分。評分端不得回寫決策錄製。
- 每次執行附一份隔離檢查：決策錄製的 import 與輸入清單不得出現 GT 路徑（沿用 #307 守門和 #127 kit 的 GT 掃描）。

### 1.4 哪些結果不能拿來支持 H1

下列任何一種，都**不得**算成 Agent／LLM 能力的證據。報告時要單獨列出數量：

1. **`RULE_FALLBACK` 接手的步驟**：`decision_source=RULE_FALLBACK` 是規則做的決定。它在「整組比較」（ITT）裡算進 Agent 組的成績（因為那是 Agent 系統的真實表現），但**不能**說成 Agent 自己判斷對了。Q3 同理：`parsed_by=RULE` 的題目不算 LLM 的成績。
2. **SYNTHETIC／ENGINEERING 場景**：P1 工程場景（`source_kind=SYNTHETIC`）、合成 fixture、v0-pilot 包的結果，只能說明「管線能跑」或做描述，不能推論到 r004 正式場景。
3. **`evaluation_eligible=false` 的題目包**：只能當 pilot（試跑、估變異），不能當正式證據（見 M3）。
4. **不計分的事件**：`NOT_SCORED_PENDING_DECISION`（LONG_GAP、LONG_LOSS）、`OVERLAP_AUTHORITY_UNSELECTED`、OV1（D105-2 只展示不計分）、`ENDED_BY_LIMIT`。也不能自己補一套評分把它們算進來。
5. **`OVERLAP_P_OV2_UNVERIFIED`**：依 D93 單列，不併進主比率。
6. **用不同評分器、不同門檻、不同子集挑出來的結果**：主要結論只用第 1.5 節登錄的那一版評分器。
7. **對照不公平的比較**（第 1.2 節任一項不同）。
8. **評分端讀不到正確答案的單位**（劇本 `UNKNOWN`／`MISSING`、seed 選不到而 `NOT_RUN`）：記為缺值，不能補成 RULE 錯或 Agent 對。
9. **只有 n＝1 的錄製**：例如 P1 的兩份預錄。

### 1.5 統計方法（三個 H1 共用）

- **分析單位**：M1 是「計分事件」（劇本裡一個 SWITCH／RETURN 事件），M3 是「一道題」。同一個單位在兩組都有結果，才算一對（paired）。
- **Agent 的 K 次重複**：每個單位的 Agent 分數取 K 次的平均正確率；另外報告每個單位 K 次之間的不一致率。
- **主要檢定**：每對的差值 d＝Agent 分數 − RULE 分數。對 d≠0 的單位做**單尾精確符號檢定**（H1：Agent 較好），α＝0.05。d＝0（打平）的單位數量照實報告。
- **多重比較**：H1-Q2、H1-Q3、H1-Q1 三個主要假設用 Holm 校正。
- **信賴區間**：正確率差的 95% CI 用 bootstrap，**依 run 分群重抽**（同一個 run 的事件不獨立），10,000 次，亂數種子 `20261102`。
- **樣本數**（依單尾符號檢定估算，假設不一致的單位中 Agent 贏的比例是 0.75）：

  | 不一致單位數 | 臨界值（贏幾個才顯著） | 檢定力 |
  | --- | --- | --- |
  | 10 | 9 | 0.24 |
  | 20 | 15 | 0.62 |
  | 30 | 20 | 0.89 |
  | 40 | 26 | 0.95 |

  所以：不一致單位 **≥30** 才算「檢定力足夠」；**10～29** 時顯著仍然可以判 SUPPORTED，但不顯著只能判 `INCONCLUSIVE_UNDERPOWERED`，不能說「兩者一樣」；**<10** 一律 `INSUFFICIENT`。

### 1.6 判定標籤（每個 H1 只能得到其中一個）

| 標籤 | 條件 |
| --- | --- |
| `SUPPORTED` | Holm 校正後 p<0.05、正確率差的點估計 ≥ +5 個百分點、資料來源是正式場景、該模組的 fallback 門檻成立（各模組自訂）、不一致單位 ≥10 |
| `SUPPORTED_ENGINEERING_ONLY` | 同上，但資料只有 SYNTHETIC／ENGINEERING。報告裡要寫「不推論到正式場景」 |
| `NO_DIFFERENCE` | 不一致單位 ≥30，且 95% CI 落在 ±5 個百分點內 |
| `INCONCLUSIVE_UNDERPOWERED` | 不顯著，且不一致單位 10～29 |
| `REVERSED` | 反向單尾檢定（RULE 較好）在 Holm 校正後 p<0.05。**照實報告為 RULE 優於 Agent** |
| `INSUFFICIENT` | 不一致單位 <10，或計分單位 <20 |
| `NOT_RUN`／`UNKNOWN` | 前置依賴沒到位，或資料缺 |

### 1.7 成本與失敗的記法（M1、M3 共用）

- **逾時率**＝`PROVIDER_TIMEOUT` 次數／模型呼叫次數；**schema 失敗率**＝`SCHEMA_INVALID` 次數／模型呼叫次數。分母是呼叫，不是步驟。
- **fallback 比例**＝`decision_source=RULE_FALLBACK` 的決策數／Agent 組的決策數（Q3 用 `parsed_by` 不是 LLM 的題數／LLM 組題數）。
- **成本**：模型呼叫次數、每次呼叫的牆鐘時間（ms）、prompt／回應 token 數（錄製裡沒記就寫 `UNKNOWN`，不估）。Qwen3 在本機執行，沒有金錢費用；D107 的 OpenAI 例外不在本實驗範圍。

## 2. M1：Q2 追蹤決策，RULE_ONLY vs AGENT_SEQUENTIAL

### 2.1 研究問題與假設

- **RQ-Q2**：在相同的候選集合與時間預算下，Agent 依序查詢候選證據後決定是否切鏡，是否比決定性規則更常做出正確的切鏡決策？
- **H1-Q2（主要）**：在 r004 正式場景的計分事件上，`AGENT_SEQUENTIAL` 的事件正確率高於 `RULE_ONLY`（ITT：整組比較，fallback 接手的步驟照原樣算進 Agent 組）。
- **H2-Q2（次要）**：在 Agent 真的有做決定（`decision_source` 是 Agent）的步驟上，與同一步的 RULE_ONLY 決定比較，Agent 正確率較高。這是條件子集，可能有選擇偏差（容易的步驟比較不會逾時），只當次要結果。
- **H0**：兩組沒有差異，或 RULE 較好。

### 2.2 對照組

| 組 | 設定 |
| --- | --- |
| RULE_ONLY | `switch_mode=RULE_ONLY`（參數集的 `switch_mode` 封閉集合，見 `src/amidst/q1q5/q3_parse.py`＠`434e579` 第 40 行） |
| AGENT_SEQUENTIAL | `switch_mode=AGENT_SEQUENTIAL`，Qwen3（P1 錄製裡的 digest 是 `qwen3:1.7b-q4_K_M`；正式執行時以實際 digest 為準並記錄），輪數與逾時用已核定上限 |

控制器：`src/amidst/q1q5/q5_controller.py`＠`434e579`（SHA-256 `1dcd0a53cf73bb2483c200be50f52f11ca35607ceaa5432c598343879c1719c7`），依索引 tick 推進，不讀媒體、GT 和 PG。

### 2.3 指標與門檻

| 指標 | 定義 | 角色 |
| --- | --- | --- |
| **事件正確率** | v1 評分器判定 SWITCH／RETURN 事件正確的比例 | **主要** |
| 切鏡延遲 | 在評分端：劇本的事件時刻到決策紀錄出現 SWITCH 的時間差（source clock，ms）。只算兩組都正確的事件，配對 Wilcoxon 符號秩檢定 | 次要 |
| 逾時率、schema 失敗率 | 第 1.7 節 | 次要（描述） |
| fallback 比例 | 第 1.7 節 | **閘門**：>20% 時 H1-Q2 最多判 `INCONCLUSIVE_UNDERPOWERED`，報告寫「Agent 大多沒有實際做決定」 |
| 成本 | 呼叫次數、每步牆鐘時間 | 描述 |
| 誤切率 | 劇本沒有事件時卻切鏡的次數／決策步數 | 次要（安全面，Agent 較高要明寫） |

### 2.4 資料來源與 hash

| 來源 | 內容 | 可以拿來做什麼 |
| --- | --- | --- |
| P1 包（LOCAL）`/Users/Shared/amidst-p1-clean-room-20261026/Amidst P1 最終測試/`，`MANIFEST.json` SHA-256 `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7` | 兩份預錄：`data/recordings/2777741d96ac9aff5bffb2f61a4d2938.json`（`ffe5e693a80031e707cddb531925cb97bc6d8295b69777ad3afa1d885bd5a55a`，`decision_source=RULE_ONLY`）、`d4b67fd71caef6fb80fc9d92af544959.json`（`26a1854efb08fe0a809b957692e3f05f92f1f516972e383e1b752f9be0eb02db`，`decision_source=RULE_FALLBACK`，`fallback_reason=PROVIDER_TIMEOUT`，agent_trace 只有 1 個模型呼叫事件，錯誤碼 `PROVIDER_TIMEOUT`；結構欄位中另出現 1 次 `SCHEMA_INVALID`）。兩份都是 `source_kind=SYNTHETIC`。本企劃只讀了 hash 和結構欄位，沒讀 GT 的值 | **只做管線冒煙測試**。每組 n＝1，Agent 實際上沒做出任何決定，**不能支持也不能否定 H1-Q2**。D113-1 的旁白照舊 |
| r004 A4-1（50 s）、B4-1（42 s）渲染後的 run（CX-7 #115 → #118 索引 → 錄製） | 劇本凍結：`docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json`＠#354 `48133c1a`，SHA-256 `ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb`（D105-1）。圖：G4 `decisions_sha256=9d99f87ea007e1988797e50fa28e70f67e6973578bc15ef3f440ba4f4d8bc76c`（D115-1） | **主要資料**。渲染輸出的 safe bundle 與 run／clock 的 SHA-256 等交件後補（現在 `UNKNOWN`） |
| FEAT-6 的 176 份凍結錄製（#300／#393＠`943a72f`，LOCAL） | #127 kit rc5 重錄，給 AC7 契約一致性用。#300 記載其中有 18 次模型逾時 | **待盤點後決定**。只有同時滿足下面三項才可用於次要指標（逾時率、schema 失敗率、fallback 比例）：每份錄製有 `switch_mode`／`decision_source` 結構欄位；同一 request 在兩組都有錄製；`source_kind` 明確。**不可用於主要指標**，因為它們沒有對應的凍結劇本，而且來源是工程場景 |

樣本量的現實：A4-1、B4-1 各只有少數幾個 SWITCH／RETURN 事件。為了湊到第 1.5 節的單位數，**事先登錄**的擴充方式是：在同一組 run 上，依 D114-1 的 seed 選取規則（只綁規則，由 Claude 從 #329 索引照規則選 ID，選不到就 `NOT_RUN`）產生多個 request（不同起點與時間窗），每個 request 各自計分。這些單位之間不獨立，所以 CI 依 run 分群重抽。若事件總數仍 <20，H1-Q2 判 `INSUFFICIENT`，不再另找資料湊數。

### 2.5 評分來源與 GT 隔離

- 正確答案來源：上面的凍結劇本（外部撰寫，評分端讀）。
- 評分器：**v1**，`src/amidst/evaluation/q5_switch_eval.py`，以 #305＠`f22e9dafe495a560eea145a8f5cefcfc871dce0f` 的 bytes 為準（SHA-256 `97564e401cb7d70a7cc22113a008477b447974536ae207aabc230868e8b6d3dc`，#306 A15 例外）；規格 `docs/evaluation/Q5_SWITCH_EVAL_V1.md`＠`434e579`（`8457b2849b926b8534b1e43f71c98729f92ccd0320c2c73a89a78fe7ba6008cf`）。v2 的結果只當穩健性檢查（見 M2）。
- GT 隔離：第 1.3 節。控制器和 Agent 的輸入只有錄製的 detection／color 證據與候選快照。

### 2.6 前置依賴

1. CX-7 #115 渲染完成（D115-2），safe bundle 與收據交 Claude 審過。
2. #118 索引、#329 索引出來（seed 選取要用）。
3. FEAT-1 #394 的正式鏈合入（`baseline_runner` 正式資料段）。
4. Codex 在同一環境對兩組產生錄製；Agent 輪數／逾時上限的核定值寫進參數集。
5. A15 v1 評分器在受檢樹是 `97564e40…` 的 bytes（#305 隨 FEAT-6 進 staging）。
6. 分析腳本（Claude）先在 SYNTHETIC fixture 上測過並凍結 hash。

### 2.7 Owner

- Codex：執行兩組、模型呼叫、錄製與收據、Agent 參數集。
- Claude：seed 選取（照 D114-1 規則）、評分執行、統計腳本、圖表、報告。
- 使用者：核定 Agent 輪數／逾時上限（若要改）、第 6 節的決定。

### 2.8 預估時程（估計，以前置依賴實際到位為準）

| 步驟 | 估計 |
| --- | --- |
| 渲染與索引 | D115 進行中；完成日 `UNKNOWN` |
| 分析腳本與 fixture 測試（可先做） | 0.5 天，demo 後 11-05 起 |
| 兩組錄製（Codex，K＝5） | 渲染＋索引後 1 天 |
| 評分、統計、圖表 | 錄製到位後 1 天 |

### 2.9 結果圖表樣式

1. **配對點圖**：每個計分單位一列，左點 RULE、右點 Agent（K 次平均），中間連線；顏色標贏／輸／平。上方標 n、打平數、不一致數。
2. **決策來源堆疊長條**：Agent 組每步的 `AGENT`／`RULE_FALLBACK` 比例，依 run 分欄。fallback 比例超過 20% 的欄加註。
3. **正確率差的森林圖**：主要（ITT）、次要（Agent 實際決策子集）、v2 穩健性，各一列 95% CI，0 線與 ±5 pp 帶。
4. **切鏡延遲 ECDF**：兩條線。
5. 每張圖的標題列都寫資料來源類別（`SYNTHETIC`／`ENGINEERING`／`FORMAL`）。`NOT_RUN` 的格子畫斜線空格，不省略。

### 2.10 可能失敗的情況與對策

| 情況 | 對策 |
| --- | --- |
| 逾時多到 fallback >20% | H1-Q2 依閘門降級；報告逾時分布；**不**在同一次實驗中放寬逾時。要放寬就照第 6 節決定 B 開新組，重新登錄 |
| Agent 回應 schema 失敗 | 照原樣計入 schema 失敗率；不修 prompt 後重跑同一批資料來換結果。修 prompt 要開新版本、重新登錄 |
| 計分事件 <20 | 判 `INSUFFICIENT`，報告寫缺多少 |
| 劇本或 seed `UNKNOWN`／`MISSING` | 該單位記缺值，不補 |
| 兩組輸入 hash 不同 | 判 `INVALID_COMPARISON`，找出原因重跑整對 |
| 渲染延誤到報告截止 | M1 主要結果寫 `NOT_RUN`；P1 冒煙測試照實寫「n＝1，不能判定」 |

## 3. M2：Q5 切鏡評分器 v1 vs v2

### 3.1 先分清楚兩個問題

| 問題 | 比較的對象 | 是不是 H1 |
| --- | --- | --- |
| **M2-a 評分器一致性** | 同一批凍結決策，分別用 v1、v2 計分 | 否。這是在檢驗量尺本身 |
| **M2-b 用評分器比較 Agent 與 RULE** | 就是 M1 的 H1-Q2 | 是，但主要量尺固定是 v1 |

**事先登錄**：H1-Q2 的主要結論只用 v1。v2 只當穩健性檢查：兩版方向一致才寫「結論對評分器版本穩健」；方向不一致就照實寫「結論依賴評分器版本」，**不能**改用對 Agent 有利的那一版。

### 3.2 研究問題與假設（M2-a）

- **RQ-S**：v2 在 v1 已涵蓋的 STANDARD SWITCH／RETURN 事件上，是否給出與 v1 相同的判定；v2 新增的類別是否都正確標成計分或不計分？
- **H-S1**：在 v1 與 v2 都計分的 STANDARD 事件上，判定一致率 ≥99%，且每個不一致都能指到 v2 設計稿裡寫明的規則差異。
- **H-S2**：v2 對 U6 列為不計分的類別（LONG_GAP、LONG_LOSS、ENDED_BY_LIMIT、真實 OVERLAP）全部輸出不計分標籤，沒有一個被算進主比率。
- **H-S3**：重算（recompute）兩次 hash 相同，`RECOMPUTE_AND_REJECT`（U-D5）對竄改輸入確實拒絕。

### 3.3 版本與設定

| 項目 | 來源 |
| --- | --- |
| v1 | `src/amidst/evaluation/q5_switch_eval.py`＠#305 `f22e9da`（`97564e40…b6d3dc`），A15「v1 一個 byte 都不改」 |
| v2 設計稿 | `docs/evaluation/Q5_SWITCH_EVAL_V2_DESIGN.md`＠#258 `0b6e800`（`0a4e579b0664ab663e44809ebc0d2670b434c17161d7c24f237b1be4d051cc4c`，D114-4；**PROPOSED**） |
| v2 實作 | `q5_switch_eval_v2.py`（U-D8＝NEW_V2_MODULE），在 FEAT-4 #396，head `1ff272ffea2fa595a153106829ebf2cef3e29c8c`；D114-3 延到 demo 後，接在 FEAT-6 合入後的 staging。正式 hash 等交件後補 |
| U6 定案設定 | `configs/evaluation/q5_v2_decisions_u6_20261101.json`，SHA-256 `0daa1508e2a67607cdc6bac54684b1b5449d3a651325e5af23dfe0afb1bd3b7e`（D105-4）。預設檔 `q5_v2_decisions.json` 維持全 PENDING |
| U8（CQ-21a） | #351＠`03b369a519c8a81ffe9e5a3136d6a6ab0eb56bd3` 整批照推薦核定（D105-3） |
| 情境卡 | 常見：`docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md`＠mainline `0d78599`（`015201556f550ab67dbbebead35916db426a3b6a05066ffc94c928696900ddbd`）。複雜：`docs/evaluation/R004_COMPLEX_SCENARIO_CARDS_V2.md`＠#261 `b5302a0`（`02d98c06ac93b5b1eec019d65415eada7b751b4c6e76d3982a28aa36d9efd88b`，合 mainline 時重釘，D114-3） |
| seed | D114-1：甲的 seed 只綁選取規則（例如 S_b＝CAM_W1、`[14.0, 17.0)`），#329 索引出來後由 Claude 只看索引照規則選 ID；選不到就 `NOT_RUN`，卡片退回 U7。formal 路徑拒絕 `UNKNOWN`／`MISSING` 的 seed |

### 3.4 指標與門檻

| 指標 | 門檻／用途 |
| --- | --- |
| STANDARD 事件判定一致率（v1 vs v2） | **主要**，≥99% 才判 H-S1 PASS；附混淆矩陣 |
| 不計分類別的標籤正確率 | 100%，任一錯誤即 H-S2 FAIL |
| 重算 hash 一致 | 100% |
| 分類別計分覆蓋 | 依 U-D7 分列主比率、STANDARD 比率、各類比率；`OVERLAP_P_OV2_UNVERIFIED` 另列（D93） |

### 3.5 常見與複雜情境的計分範圍（依 D105-2、D105-4）

| 情境 | 卡 | 計分 | 可以進 H1-Q2 嗎 |
| --- | --- | --- | --- |
| 常見 | A4-1、B4-1（卡 v1） | STANDARD SWITCH／RETURN 計分 | 可以（主要） |
| 複雜「甲」 | RR-a1、RR-a2、PE1-d | 計分 | 可以，但與常見情境**分開報告**，不合併成一個數字 |
| 複雜「甲」 | RR-b、LG-1 | `NOT_SCORED_PENDING_DECISION`（U-D1／U-D2 未決） | 不行 |
| 複雜「甲」 | OV1-a、OV1-b | 只展示不計分；正式範圍是 `OVERLAP_AUTHORITY_UNSELECTED` | 不行 |
| 長卡 | A4-2、B4-2 | 暫緩（#323 選項 3） | 不行（`NOT_RUN`） |

甲目前仍是 UNFROZEN、走 fallback（D114-2）。甲沒有凍結前，複雜情境那幾列全寫 `NOT_RUN`。

### 3.6 資料來源

M2-a 不需要新的模型呼叫：拿 M1 已凍結的兩組決策錄製，加上 v2 的 SYNTHETIC fixture（FEAT-4 自帶的 SETTLED fixture 與 #363 E5 的 pending 5 列）即可。

### 3.7 GT 隔離

評分器只讀凍結決策和凍結劇本。v1、v2 都是 evaluation-only 模組；本實驗不改兩者任何 byte。

### 3.8 前置依賴

1. FEAT-6 #393 合入 staging（帶 #305，v1 bytes 變成 `97564e40…`）。
2. FEAT-4 #396 在 FEAT-6 之後的 staging 上交件、審過、合入（D114-3），v2 才有正式 hash。
3. M1 的決策錄製（M2-a 的真實資料段）。
4. 甲凍結（#326 v2 劇本核准、run／clock／參數集、seed）才跑複雜情境列；否則只跑常見情境。

### 3.9 Owner

- Claude：一致性比對腳本、混淆矩陣、報告（評估工具歸 Claude）。
- Codex：v2 實作的交件與修正（FEAT-4 擁有者）。
- 使用者：U-D1／U-D2／U-D4 若要決定（決定前 LONG_GAP／LONG_LOSS 一律不計分）。

### 3.10 預估時程

FEAT-4 合入後 0.5～1 天。FEAT-4 的交件日 `UNKNOWN`（demo 後）。

### 3.11 結果圖表樣式

1. **v1×v2 混淆矩陣**（每格事件數），不一致格附規則條目編號。
2. **計分覆蓋瀑布圖**：全部事件 → 各類不計分剔除 → 實際計分，每一段標原因標籤。
3. **H1-Q2 穩健性列**：在 M1 森林圖加一列「v2」。

### 3.12 可能失敗的情況與對策

| 情況 | 對策 |
| --- | --- |
| STANDARD 一致率 <99% | H-S1 FAIL；逐筆列出不一致，回 FEAT-4 修，不在報告裡挑一版用 |
| v2 交件晚於報告 | M2 寫 `NOT_RUN`；H1-Q2 只有 v1 結果，報告寫「未做評分器穩健性檢查」 |
| v2 對 Agent／RULE 的方向與 v1 相反 | 照實寫「結論依賴評分器版本」，H1-Q2 判定不改（主要量尺是 v1） |
| v1 bytes 不是 `97564e40…` | 停下，不計分；回報 pin 偏移 |

## 4. M3：檢索 Q1／Q3

### 4.1 研究問題與假設

- **RQ-Q3**：LLM 解析（失敗時由規則兜底）是否比只用字面規則的解析，更常把自然語言問題正確轉成結構化查詢？
- **H1-Q3（主要）**：在正式題目上，`LLM_WITH_RULE_FALLBACK` 的**整題完全正確率**（六個欄位 intent、class、color、time_us、camera、region 全對，或正確拒答）高於 `RULE_ONLY`。
- **H1-Q1（主要）**：從同一道文字題出發，經各自的 Q3 解析再進 Q1 檢索，LLM 組的**相機命中率**（人工答案中的相機有被找到的比例）高於 RULE 組。Q1 檢索本身是決定性的（`src/amidst/q1q5/q1_search.py`），兩組的差異只來自 Q3 輸出。
- **H2-Q3（次要）**：在 `parsed_by=LLM` 的題目上，與同一題的 RULE 結果配對比較。
- **安全面（次要，不是 H1）**：LLM 捏造非字面詞的比例（`q3_parse.py` 會拒絕「LLM invented nonliteral term」，記錄被拒次數），錯誤接受率（該拒答卻給了查詢）。

### 4.2 對照組

| 組 | 設定 |
| --- | --- |
| RULE_ONLY | `parser_mode=RULE_ONLY`，字面文法 `src/amidst/q1q5/q3_rules.py`＠`434e579`（`659a148224fc08b0a71a31c09a831a7a1ceb81004335a4c535a61ef02b6f5d5d`，`q3-rules.v1`） |
| LLM | `parser_mode=LLM_WITH_RULE_FALLBACK`，`src/amidst/q1q5/q3_parse.py`＠`434e579`（`ab3e80aba29f66c58654b52392c88c33266347c41d063817b6bc0eb2f42c228d`）；`q3_max_llm_attempts`、`q3_llm_timeout_ms` 用已核定值，兩組同一 `parameter_set_sha256` |

注意：`q3_parse.py` 的 LLM 模式含規則兜底，所以 LLM 組裡有一部分題目其實是規則解析的。H1-Q3 是整組比較（ITT），H2-Q3 只看 `parsed_by=LLM`。兩組在 `parsed_by=RULE` 的題目上如果結果完全相同，這些題就是打平，報告會顯示打平數。

### 4.3 指標與門檻

| 指標 | 定義 | 角色 |
| --- | --- | --- |
| **整題完全正確率** | `q3_parse_eval.py`（`q3-parse-eval-v1`）判定六欄全對，或狀態屬於正確拒答 | **H1-Q3 主要** |
| **相機命中率** | `q1_query_eval.py` 依人工答案計算 | **H1-Q1 主要** |
| 各欄位正確率 | 六欄分開 | 次要 |
| 拒答正確率 | `NEEDS_CLARIFICATION`、`UNSUPPORTED_CLASS` 等狀態是否正確 | 次要 |
| LLM 實際解析比例 | `parsed_by=LLM` 題數／LLM 組題數 | **閘門**：<50% 時 H1-Q3 最多判 `INCONCLUSIVE_UNDERPOWERED`，報告寫「大多由規則解析」 |
| 逾時率、schema 失敗率、成本 | 第 1.7 節 | 描述 |

### 4.4 題目來源與能不能當正式證據

| 來源 | 狀態 | 可以做什麼 | 不能做什麼 |
| --- | --- | --- | --- |
| yyin 出題包 s2（FEAT-2 #317／#369），`v0-pilot`、`evaluation_eligible=false`（D100-6） | 尚未交回 | pilot：試跑管線、估計題目間變異、檢查評分器能不能處理每一題 | **不能**當 H1-Q3／H1-Q1 的正式證據。用它算出的任何差異，報告標 `PILOT_ONLY` |
| FEAT-3 team-eval（#293，D112-1），`team-review-pack.v1`、`v0-pilot`、`evaluation_eligible=false`、`source_class=ENGINEERING`、`halves=["baseline"]` | builder 進行中；發包要 U12 | 同上；而且它重播凍結輸出（D96-2），組員端不跑模型，本身不會產生新的 LLM 對照資料 | 同上 |
| 正式題目包（`v1`、`evaluation_eligible=true`） | 不存在 | 正式證據 | 要有正式來源，且使用者另外核准（D105 B-8、#293 定案表）。人工答案要經 U13 標註流程 |

**事先登錄**：pilot 題與正式題必須不重疊（以題目文字 SHA-256 比對）。在 pilot 上看到的結果不能拿來改 prompt 後再在同一批題目上報告；改 prompt 就要在**正式題**上重新跑、重新登錄。

### 4.5 GT 隔離

- Q3 parser 的輸入只有使用者文字、locale、context（`q3_parse.py` 允許的欄位：`schema_version`、`session_ref`、`text`、`locale`、`context`、`parser_mode`）。
- 正確答案是人工標註，只在 `q3_parse_eval.py`／`q1_query_eval.py` 讀。兩個評分器都寫明不 import parser、provider 或檢索實作。
- 題目文字不得含 GT 衍生的資訊（例如渲染軌跡時間點）；出題包已有的禁止內容掃描（#318）照用。

### 4.6 樣本數

依第 1.5 節。H1-Q3 的不一致題目要 ≥30 才算檢定力足夠；以 LLM 實際解析比例 50%、其中一半與規則結果不同估算，正式題至少要 **120 題**。少於 40 題（預期不一致 <10）就直接判 `INSUFFICIENT`，只做描述。

### 4.7 前置依賴

1. 正式題目包（`evaluation_eligible=true`）與人工答案：目前不存在，需要使用者決定來源（第 6 節決定 C）。
2. yyin 交回 s2（pilot 用）；FEAT-3 team-eval 發包（U12）。
3. Q1 檢索的正式索引（#118），否則 H1-Q1 只能在 P1 工程索引上做 `SUPPORTED_ENGINEERING_ONLY` 以下的判定。
4. Codex 對兩組產生 Q3 解析錄製（含 `q3_provider_audit`）。

### 4.8 Owner

- Codex：LLM 呼叫、Q3 解析錄製、provider 設定。
- Claude：題目去重與分層、評分、統計、圖表。
- yyin／組員：出題與作答；使用者：正式包核准、U12、U13。

### 4.9 預估時程

- pilot：s2 交回後 1 天。
- 正式：正式題目包與答案到位後 2 天。現在兩者的日期都是 `UNKNOWN`。

### 4.10 結果圖表樣式

1. **欄位正確率分組長條**（六欄＋整題），兩組並列，95% CI。
2. **parsed_by 分布長條**：LLM 組裡 LLM／RULE 各占多少。
3. **配對結果矩陣**：RULE 對／錯 × LLM 對／錯 的 2×2 計數（符號檢定直接從這裡讀）。
4. **Q1 命中率森林圖**：ITT 與 `parsed_by=LLM` 子集。
5. pilot 的圖一律在標題加「PILOT_ONLY，非正式證據」。

### 4.11 可能失敗的情況與對策

| 情況 | 對策 |
| --- | --- |
| 沒有正式題目包 | H1-Q3、H1-Q1 判 `NOT_RUN`；pilot 結果照實報告為 `PILOT_ONLY` |
| LLM 實際解析比例 <50% | 依閘門降級，報告寫原因（逾時？規則先命中？） |
| LLM 捏造詞被拒的比例高 | 照實報告；這是 LLM 組的失敗，不從分母剔除 |
| 人工答案有爭議 | 該題記 `UNKNOWN`，不計入兩組；爭議題數照列 |
| 時間表達式需要 clock 對應卻缺 | `q3_parse_eval.py` 會拒絕；該題記缺值 |

## 5. 資料到位就能開跑：檢查表

每一項都要附證據（命令輸出、SHA-256、留言連結）。任一項沒打勾，該模組不開跑。

### 共用

- [ ] 本文件的事先登錄 commit SHA 已記在結果紀錄。
- [ ] 分析腳本已在 SYNTHETIC fixture 上通過，腳本 SHA-256 已記錄，之後不再改。
- [ ] 磁碟可用 ≥9 GiB（`df -g /`）。
- [ ] 模型 digest、Ollama 版本、機器型號已記錄。
- [ ] 兩組的 `parameter_set_sha256` 只差 mode 欄位（以 diff 證明）。
- [ ] GT 隔離檢查（#307 守門、#127 kit GT 掃描）對決策錄製 PASS。

### M1

- [ ] CX-7 #115 的 safe bundle 與收據已交、Claude 審過；run／clock SHA-256 已填。
- [ ] #118、#329 索引已交，SHA-256 已填。
- [ ] 劇本凍結 `ab45a832…` 在受檢樹中未變。
- [ ] G4 `9d99f87e…bc76c` 仍是生效值。
- [ ] seed 依 D114-1 規則選定，選不到的 request 已標 `NOT_RUN`。
- [ ] v1 評分器 bytes＝`97564e40…b6d3dc`。
- [ ] Agent 輪數／逾時上限的核定值已寫進參數集。
- [ ] 計分事件數 ≥20（否則預先知道會判 `INSUFFICIENT`，仍可跑，但報告標明）。

### M2

- [ ] FEAT-6 已合入 staging；FEAT-4 已在其上合入，v2 SHA-256 已填。
- [ ] U6 設定檔＝`0daa1508…bd3b7e`；預設檔仍全 PENDING。
- [ ] M1 的兩組決策錄製已凍結。
- [ ] 甲是否凍結：是 → 跑複雜列；否 → 複雜列寫 `NOT_RUN`。

### M3

- [ ] 正式題目包（`evaluation_eligible=true`）已由使用者核准，或確定只做 pilot。
- [ ] 人工答案已交，題目 SHA-256 清單已凍結；pilot 與正式題不重疊。
- [ ] 正式題數 ≥40（≥120 才有足夠檢定力）。
- [ ] 正式 Q1 索引已交，或確定只用 P1 工程索引（判定上限是 `SUPPORTED_ENGINEERING_ONLY`）。
- [ ] `q3_parse_eval.py`（`4660edea…98c4`）、`q1_query_eval.py`（`eb403f96…73b9`）bytes 未變，或新 bytes 已記錄。

## 6. 需要使用者決定的事項

### 決定 A：H1 的主要分析用哪一種比較

1. **（推薦）整組比較（ITT）為主，Agent 實際決策子集為次。**優點：反映系統真實表現，fallback 不會被藏起來；不會因為只挑 Agent 沒逾時的步驟而高估。缺點：逾時多時，Agent 的能力會被規則的表現稀釋，較難得到 SUPPORTED。
2. **只看 Agent 實際決策的步驟（與同一步的 RULE 配對）為主。**優點：比較貼近「模型本身的判斷力」。缺點：有選擇偏差（容易的步驟比較不會逾時）；fallback 比例高時樣本會很少；審查者容易質疑是在挑資料。

### 決定 B：Agent 的逾時上限

1. **（推薦）實驗沿用已核定的上限，不放寬；逾時照實計入。**優點：比的就是 demo 與產品實際會用的系統；公平性最清楚。缺點：P1 那份就是 1 次呼叫 1 次逾時；若正式 run 也大量逾時，H1 很可能判 `INCONCLUSIVE` 或閘門降級。
2. **另加一組「放寬逾時」的 Agent 組，與原上限組並列。**優點：能分開回答「模型能力」和「在時間預算內的能力」。缺點：放寬後兩組時間預算不同，不能拿來與 RULE 做公平比較，只能當探索；多一組要多一倍執行時間，且要使用者核定新上限。

### 決定 C：M3 的正式題目從哪裡來

1. **（推薦）先用 s2／team-eval 做 pilot，另外請 yyin 出一份不重疊的正式題（`v1`、`evaluation_eligible=true`），經使用者核准後才算正式證據。**優點：pilot 與正式分開，避免用同一批題目調 prompt 又報結果；符合 D105 B-8。缺點：要多一輪出題與標註，正式結果最快也在 demo 後一週以上。
2. **把 s2 升級成 `evaluation_eligible=true`。**優點：最快。缺點：s2 原本就是 pilot 設計，題數與答案品質沒有針對正式評估；若之前有人看過 s2 的結果，就不再是事先登錄的乾淨樣本。
3. **M3 只做 pilot，報告標 `PILOT_ONLY`，不做正式判定。**優點：不增加工作。缺點：H1-Q3、H1-Q1 只能是 `NOT_RUN`，研究成果裡沒有 Q3／Q1 的正式結論。

## 7. 引用

| 文件 | ref | SHA-256 |
| --- | --- | --- |
| `docs/specs/DEVELOPMENT_RULES.md` | `origin/claude/rules-d108`＠`994b700` | `b01c60b7a8430de8ff45f6c8b911d5669dd2bdf5791dde9ad7487300387419a5` |
| `docs/agents/Q1Q5_DEMO_SCRIPT.md`（B-05a／B-05b） | #384＠`cf325aa9addeb801bb75da86a533bc42cb9b3f77` | `e1c543645ec8b659aa733ae1a9589893a84bc09d3f5a5a41c3f2a870293d30ea` |
| `src/amidst/evaluation/q5_switch_eval.py` | staging＠`434e579`（現值）／#305＠`f22e9da`（A15 例外） | `0fd1ef68…85d9f2`／`97564e40…b6d3dc` |
| `docs/evaluation/Q5_SWITCH_EVAL_V1.md` | staging＠`434e579` | `8457b2849b926b8534b1e43f71c98729f92ccd0320c2c73a89a78fe7ba6008cf` |
| `docs/evaluation/Q5_SWITCH_EVAL_V2_DESIGN.md` | #258＠`0b6e800` | `0a4e579b0664ab663e44809ebc0d2670b434c17161d7c24f237b1be4d051cc4c` |
| `src/amidst/evaluation/q3_parse_eval.py` | staging＠`434e579` | `4660edea0b204dfdead99cd1e2ebc5b8ce13ccffbd9d78c157ba285abda298c4` |
| `src/amidst/evaluation/q1_query_eval.py` | staging＠`434e579` | `eb403f968d3263cb5151219c9e46dddc8922d0f7ba9f21b7c07a276f44f973b9` |
| `src/amidst/q1q5/q3_rules.py` | staging＠`434e579` | `659a148224fc08b0a71a31c09a831a7a1ceb81004335a4c535a61ef02b6f5d5d` |
| `src/amidst/q1q5/q3_parse.py` | staging＠`434e579` | `ab3e80aba29f66c58654b52392c88c33266347c41d063817b6bc0eb2f42c228d` |
| `src/amidst/q1q5/q5_controller.py` | staging＠`434e579` | `1dcd0a53cf73bb2483c200be50f52f11ca35607ceaa5432c598343879c1719c7` |
| `docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md` | mainline＠`0d78599` | `015201556f550ab67dbbebead35916db426a3b6a05066ffc94c928696900ddbd` |
| `docs/evaluation/R004_COMPLEX_SCENARIO_CARDS_V2.md` | #261＠`b5302a0` | `02d98c06ac93b5b1eec019d65415eada7b751b4c6e76d3982a28aa36d9efd88b` |
| `docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json` | #354＠`48133c1a` | `ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb` |
| `configs/evaluation/q5_v2_decisions_u6_20261101.json` | FEAT-4 #396＠`1ff272f` | `0daa1508e2a67607cdc6bac54684b1b5449d3a651325e5af23dfe0afb1bd3b7e` |
| P1 包 `MANIFEST.json`（LOCAL） | — | `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7` |

決策：#93 的 D105-1～D105-4、D112-1、D113、D114-1～D114-4、D115；架構基準 #306（A15、P1）；FEAT-4 #371、FEAT-6 #373、FEAT-1 #376、CQ-14 #293、CQ-19 #300。
