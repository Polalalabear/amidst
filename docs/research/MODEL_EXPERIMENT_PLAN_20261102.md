# 模組上的模型實驗分析企劃（事先登錄版）

- 日期：2026-11-02（第 2 版：依使用者補充，改成「先 Baseline、再比較」，並加上指標公式、數字表、實驗環境揭露與跨平台外包執行包）
- 狀態：**PLANNED／NOT_RUN**。本文件只是企劃：沒有呼叫任何模型、沒有渲染、沒有推論。demo（11-04）之後、資料到位才執行，不進 11-03 批次。
- 作者：Claude Opus 5.5 / high。依 AGENTS.md：評估工具、統計和圖表歸 Claude；模型呼叫和 Agent orchestration 歸 Codex。
- base：`codex/q1q5-staging`＠`434e57922a24d2422226871c0bb672dc7bc3584b`
- 引用格式：`路徑＠commit`，後面附 SHA-256。LOCAL 表示檔案只在本機，不在 repo。
- **數字規則**：本文件不寫任何預期值。表格裡沒有實測數字的格子一律寫 `NOT_RUN`；資料缺的寫 `UNKNOWN`；不計分的寫該類別的標籤（例如 `NOT_SCORED_PENDING_DECISION`）。

## 目錄

- 第 0 部分：目標與共用規則（§0～§1）
- **第一部分：Baseline 結果（RULE_ONLY）**（§2）
- **第二部分：建立在 Baseline 之上的比較**（§3 M1 Agent vs RULE、§4 M2 Q5 評分器 v1 vs v2、§5 M3 Q1／Q3）
- 第三部分：實驗環境揭露（§6）
- 第四部分：跨平台外包執行包（§7）
- 開跑檢查表（§8）、待使用者決定（§9）、引用（§10）

## 0. 目標

研究目標是檢驗「Agent／LLM 的能力大於 RULE」。這是**待檢驗的假設**，不是預設結論。執行順序固定如下：

1. **先做 Baseline**：在 r004 正式場景上，用 `RULE_ONLY` 跑完 Q1／Q2／Q3／Q5 的正式鏈，產出第 2 節的數字表。這是主線，也是第二部分所有比較的對照數字。
2. **再做比較**：Agent vs RULE（M1）、評分器 v1 vs v2（M2）、LLM vs 規則解析（M3）。這三項都依賴 Baseline 的數字與錄製。Baseline 沒完成，第二部分一律 `NOT_RUN`。

假設、對照組、主要指標、門檻、樣本數和檢定都在看到資料前寫死。結果不論是 Agent 贏、打平、輸，或資料不足，都照第 1.6 節的判定標籤原樣報告。

## 1. 共用規則

### 1.1 事先登錄與修訂

1. **凍結點**：本文件推上 PR 的 commit 就是事先登錄版本。分析腳本（Claude）先用 SYNTHETIC fixture 寫完、測完，把腳本的 SHA-256 記在結果紀錄裡，之後才讀真實資料。
2. **修訂**：看到資料前可以修訂，但要另開 commit 寫明理由。看到資料後才加的分析一律標 `EXPLORATORY`，不能改判主要假設。
3. 每個假設只有**一個主要指標**。次要指標顯著，不能補主要指標的不顯著。

### 1.2 GT 隔離

- 決策端（Q2／Q3／Q5 控制器、Agent、Q3 parser、Q1 檢索）只讀錄製、凍結索引和 request。GT、渲染軌跡、visibility、depth 一律不進入（`docs/specs/DEVELOPMENT_RULES.md`＠`994b700` 第 57、64 行）。
- 正確答案只在評分端讀：Q5 讀外部撰寫並凍結的劇本，Q1／Q3 讀人工標註的答案。三個評分器都是 evaluation-only（`q5_switch_eval.py`、`q3_parse_eval.py`、`q1_query_eval.py` 開頭都寫明不 import 推論、模型、parser 或檢索實作）。
- 執行分兩段：**先**由執行端產生並凍結決策錄製（記 SHA-256），**後**由 Claude 的評分端讀劇本／答案計分。評分端不回寫錄製。外包機（§7）只做第一段。
- 每次執行附隔離檢查：決策錄製的輸入清單不得出現 GT 路徑（沿用 #307 守門和 #127 kit 的 GT 掃描）。

### 1.3 資料來源類別

每個數字都要標來源類別，結論不跨類別推論：

| 類別 | 例子 | 可以支持什麼 |
| --- | --- | --- |
| `FORMAL` | r004 A4-1／B4-1 渲染後的正式 run、`evaluation_eligible=true` 的題目包 | 正式結論 |
| `ENGINEERING` | P1 工程場景、team-eval v0-pilot（`source_class=ENGINEERING`） | 只有「工程場景上成立」 |
| `SYNTHETIC` | 合成 fixture、P1 包內錄製（`source_kind=SYNTHETIC`） | 只有「管線能跑」 |
| `PILOT` | `evaluation_eligible=false` 的題目包 | 試跑、估變異；不是證據 |

### 1.4 哪些結果不能拿來支持 H1

下列結果**不得**算成 Agent／LLM 能力的證據，報告時要單獨列出數量：

1. **`RULE_FALLBACK` 接手的步驟**。它在整組比較（ITT）裡算進 Agent 組，因為那是 Agent 系統的實際表現，但不能說成是 Agent 判斷對的。Q3 同理：`parsed_by=RULE` 的題目不算 LLM 的成績。
2. **SYNTHETIC／ENGINEERING 場景**的結果，不能推論到 r004 正式場景。
3. **`evaluation_eligible=false` 的題目包**。`q1_query_eval.py` 在 `evaluation_eligible=false` 時本來就把正式指標寫成 0／0，只在 SYNTHETIC 時另出 `synthetic_metrics`。
4. **不計分的事件**：`NOT_SCORED_PENDING_DECISION`（LONG_GAP、LONG_LOSS）、`OVERLAP_AUTHORITY_UNSELECTED`、OV1（D105-2：只展示不計分）、`ENDED_BY_LIMIT`。也不能另做一套評分把它們算進來。
5. **`OVERLAP_P_OV2_UNVERIFIED`**：依 D93 單列，不併入主比率。
6. **事後換評分器、門檻或子集**得到的結果。
7. **對照不公平的比較**（§3.2 任一項不同）。
8. **評分端沒有正確答案的單位**（劇本 `UNKNOWN`／`MISSING`、seed 選不到而 `NOT_RUN`）：記成缺值，不能補成 RULE 錯或 Agent 對。
9. **n＝1 的錄製**，例如 P1 包的兩份預錄。
10. **外包機上跑出、但環境 manifest 不完整或輸出 hash 驗不過的 run**（§7.5）。

### 1.5 統計方法

- **分析單位**：Q2／Q5 是「計分事件」，也就是劇本裡一個 SWITCH 或 RETURN 決策窗；Q1／Q3 是「一道題」。
- **95% 信賴區間**：比例用 bootstrap，**依 run 分群重抽**，因為同一個 run 的事件不獨立。重抽 10,000 次，亂數種子 `20261102`。單一 run 的比例改用 Wilson 區間。延遲的中位數和 P90 也用同一套 bootstrap。
- **比較檢定**（只用在第二部分）：每對單位的差值 d＝比較組分數 − Baseline 分數。對 d≠0 的單位做**單尾精確符號檢定**，α＝0.05。三個 H1 用 Holm 校正。
- **樣本數**：單尾符號檢定，假設在不一致的單位裡比較組贏的比例是 0.75。

  | 不一致單位數 | 顯著所需贏數 | 檢定力 |
  | --- | --- | --- |
  | 10 | 9 | 0.24 |
  | 20 | 15 | 0.62 |
  | 30 | 20 | 0.89 |
  | 40 | 26 | 0.95 |

  不一致單位 ≥30 才算檢定力足夠；10～29 時，顯著仍可判 SUPPORTED，不顯著只能判 `INCONCLUSIVE_UNDERPOWERED`；<10 一律判 `INSUFFICIENT`。

### 1.6 判定標籤（第二部分每個 H1 只會得到一個）

| 標籤 | 條件 |
| --- | --- |
| `SUPPORTED` | Holm 校正後 p<0.05；正確率差的點估計 ≥ +5 個百分點；資料是 `FORMAL`；該模組的閘門成立；不一致單位 ≥10 |
| `SUPPORTED_ENGINEERING_ONLY` | 同上，但資料只有 `ENGINEERING`。報告要寫「不推論到正式場景」 |
| `NO_DIFFERENCE` | 不一致單位 ≥30，而且差的 95% CI 落在 ±5 個百分點內 |
| `INCONCLUSIVE_UNDERPOWERED` | 不顯著，且不一致單位 10～29；或閘門沒過 |
| `REVERSED` | 反方向（RULE 較好）的單尾檢定在 Holm 校正後 p<0.05。**照實報告為 RULE 優於 Agent／LLM** |
| `INSUFFICIENT` | 不一致單位 <10，或計分單位 <20 |
| `NOT_RUN`／`UNKNOWN` | 前置依賴沒到位，或資料缺 |

### 1.7 指標的精確定義（全文共用）

時間都用 source clock。錄製內部的單位是 µs，報告時換成 ms（÷1000，保留 1 位小數）。

| 代號 | 指標 | 公式 | 單位 | 計算來源 |
| --- | --- | --- | --- | --- |
| `C_evt` | 事件正確率 | 判為 match 的計分事件數 ÷ 計分事件數 × 100。v1 的 match 定義：決策窗 `[w0, w1)` 內**恰好一次** SWITCH，相機屬於 `allowed_camera_ids`，進入時間落在 `entry_window_us` 內（`q5_switch_eval.py` 第 146～151 行）。RETURN 事件依 v1 對應規則 | % | v1 評分器輸出 |
| `L_sw` | 切鏡延遲 | 對每個判為 match 的事件：`decision_time_us − w0`，÷1000。報告中位數和 P90 | ms | 錄製的 `decision_time_us` 加上劇本的決策窗 |
| `FS` | 誤切率 | 不落在任何計分決策窗內的 SWITCH 數 ÷ 計分範圍的總長（分鐘） | 次／分鐘 | 錄製加劇本 |
| `M_honest` | 缺值誠實率 | 劇本或評分端判為「應該找不到」的步驟中，輸出 `SEARCHING`／`TEMP_LOST`／`MISSING`／`UNKNOWN`、沒有硬給相機的比例 | % | 錄製加 v1 評分器（AC8） |
| `R_hash` | 重播一致率 | 同一 session 以 recorded replay 重播後輸出 hash 相同的次數 ÷ 重播次數 × 100 | % | AC7、#127 kit |
| `T_step` | 每步處理時間 | 每個決策步的牆鐘時間。報告中位數和 P90 | ms | 錄製時間戳或 runner log |
| `TO` | 逾時率 | `PROVIDER_TIMEOUT` 次數 ÷ 模型呼叫次數 × 100（分母是呼叫，不是步驟） | % | `agent_trace.events[].error_code` |
| `SI` | schema 失敗率 | `SCHEMA_INVALID` 次數 ÷ 模型呼叫次數 × 100 | % | 同上 |
| `FB` | fallback 比例 | `decision_source=RULE_FALLBACK` 的決策步數 ÷ Agent 組決策步數 × 100 | % | 錄製 `decision_source` |
| `K_call` | 呼叫成本 | 模型呼叫次數 ÷ 決策步數；另報每次呼叫的牆鐘 ms，以及 prompt／回應 token 數（錄製沒記就寫 `UNKNOWN`，不估） | 次／步、ms、token | `agent_trace`、`q3_provider_audit` |
| `E_q3` | Q3 整題正確率 | 六個欄位（intent、class、color、time_us、camera、region）全對，或正確拒答的題數 ÷ 計分題數 × 100 | % | `q3_parse_eval.py`（`q3-parse-eval-v1`） |
| `F_q3[f]` | Q3 各欄位正確率 | 欄位 f 正確的題數 ÷ 計分題數 × 100 | % | 同上 |
| `P_cam`、`R_cam` | Q1 相機 micro precision／recall | `TP/(TP+FP)`、`TP/(TP+FN)`，按相機累加 | % | `q1_query_eval.py` 的 `camera_micro_precision`／`camera_micro_recall`（第 242～243 行） |
| `LLM_share` | LLM 實際解析比例 | `parsed_by=LLM` 題數 ÷ LLM 組題數 × 100 | % | Q3 回應的 `parsed_by` |

## 第一部分：Baseline 結果（RULE_ONLY）

## 2. Baseline

### 2.1 定義

**Baseline**＝r004 正式場景（A4-1 50 s、B4-1 42 s；D89），在 G4 生效的圖上（D115-1，`decisions_sha256=9d99f87ea007e1988797e50fa28e70f67e6973578bc15ef3f440ba4f4d8bc76c`），用 FEAT-1 #376 的 Baseline 正式鏈，以 `switch_mode=RULE_ONLY`、`parser_mode=RULE_ONLY` 跑出的 Q1／Q2／Q3／Q5 結果。

這一部分沒有比較組，也沒有假設檢定，只產出帶 95% CI 的數字。第二部分的所有比較都拿這些數字和錄製當對照組。

### 2.2 輸入與 hash

| 輸入 | 來源 | SHA-256／狀態 |
| --- | --- | --- |
| Baseline 正式鏈程式 | FEAT-1 #394，head `18d1a287f1ddc6eed442eebc3fe8667b225344e1`（Claude 複審 APPROVE） | 合入後的 staging commit：`NOT_RUN` |
| 劇本凍結 | `docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json`＠#354 `48133c1a` | `ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb`（D105-1） |
| 情境卡 v1 | `docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md`＠mainline `0d78599` | `015201556f550ab67dbbebead35916db426a3b6a05066ffc94c928696900ddbd` |
| 圖（G4） | #348＠`0502225bb16f117014fd875fc7a9281220ede484` | `decisions_sha256` 如上 |
| 渲染 safe bundle（A4-1、B4-1） | CX-7 #115（D115-2，進行中），LOCAL | `NOT_RUN` |
| 偵測索引 | #118 | `NOT_RUN` |
| seed 選取索引 | #329，seed 依 D114-1 規則選取 | `NOT_RUN` |
| 參數集 | 正式鏈的 `parameter_set_sha256` | `NOT_RUN` |
| Q5 評分器 v1 | `src/amidst/evaluation/q5_switch_eval.py`＠#305 `f22e9da` | `97564e401cb7d70a7cc22113a008477b447974536ae207aabc230868e8b6d3dc`（#306 A15 例外） |
| Q1／Q3 評分器 | `q1_query_eval.py`、`q3_parse_eval.py`＠`434e579` | `eb403f968d3263cb5151219c9e46dddc8922d0f7ba9f21b7c07a276f44f973b9`、`4660edea0b204dfdead99cd1e2ebc5b8ce13ccffbd9d78c157ba285abda298c4` |
| Q1／Q3 Baseline 題目與答案 | 正式題目包（`evaluation_eligible=true`）目前不存在，見 §9 決定 C | `NOT_RUN` |
| team-eval 包（Baseline-only） | FEAT-3 #370／#293（D112-1），`v0-pilot`／`evaluation_eligible=false`／`ENGINEERING` | MANIFEST SHA-256：`NOT_RUN`（發包要 U12） |
| 執行環境 | §6 的環境 manifest | `NOT_RUN` |

### 2.3 表 B-1：每個 run 的 Q2／Q5 Baseline 數字（主表）

每列是一個 run 加一個 request（同一個 run 可以有多個 request，依 D114-1 規則選 seed）。最後兩列是依 run 分群的合計。

| 欄位 | 內容 |
| --- | --- |
| `run_id` | 正式 run ID |
| `scene` | A4-1／B4-1 |
| `request_sha256` | request 的 hash |
| `source_class` | `FORMAL` |
| `n_events_scored` | 計分事件數（SWITCH＋RETURN） |
| `n_events_not_scored` | 不計分事件數，並附各類標籤的計數 |
| `C_evt` ％ [95% CI] | §1.7 |
| `L_sw` 中位數 ms [95% CI]／P90 ms | §1.7 |
| `FS` 次／分鐘 | §1.7 |
| `M_honest` ％ [95% CI] | §1.7 |
| `T_step` 中位數／P90 ms | §1.7 |
| `R_hash` ％ | 重播 3 次 |
| `recording_sha256` | 決策錄製 |
| `scorer_output_sha256` | v1 評分輸出 |
| `env_manifest_sha256` | §6 |

**現況：每一格都是 `NOT_RUN`。**

### 2.4 表 B-2：Q1／Q3 Baseline 數字

| 欄位 | 內容 |
| --- | --- |
| `question_pack` | 題目包 ID 與 MANIFEST SHA-256 |
| `eligibility` | `evaluation_eligible` 的值；`false` 時這一列整列標 `PILOT` |
| `n_questions_scored` | 計分題數 |
| `E_q3` ％ [95% CI] | §1.7 |
| `F_q3[intent／class／color／time_us／camera／region]` ％ | 六欄 |
| 拒答正確率 ％ | `NEEDS_CLARIFICATION`、`UNSUPPORTED_CLASS` 等狀態判對的比例 |
| `P_cam`／`R_cam` ％ [95% CI] | §1.7 |
| `T_query` 中位數 ms | 從文字到 Q1 結果的牆鐘時間 |
| `scorer_output_sha256`、`env_manifest_sha256` | |

**現況：`NOT_RUN`**。正式題目包不存在；team-eval 和 s2 只能填 `PILOT` 列。

### 2.5 表 B-3：team-eval Baseline-only RETURN

FEAT-3 的 team-eval 包會重播我方凍結的 Baseline 輸出（D96-2），組員端不跑模型。所以它驗的是「別的機器能不能重現同一份 Baseline 輸出」，不是新的準確率數字。依 D112-1 的 RETURN 形狀（`projection=TEAM_EVAL_BASELINE_V0_PILOT`，`team-eval-return.v1` 仍是 PROPOSED）：

| 欄位 | 內容 |
| --- | --- |
| `return_file` | `RETURN/評測結果_姓名_YYYY-MM-DD.json`（報告用代號，不寫真名） |
| `pack_manifest_sha256` | 必須等於發出去的包 |
| `environment.python_version`／`isolated`／`platform` | RETURN 原欄位 |
| `halves` | 必須正好是 `["baseline"]`；出現 complex 鍵就 INVALID（`HALF_NOT_IN_PACK`） |
| `output_sha256.baseline` | 與我方參考輸出比對：`MATCH`／`MISMATCH` |
| `verify` | `VALID`／`VALID_WITH_WARNINGS`／`INVALID` |
| `complex` | 一律 `NOT_INCLUDED`（不計分、不算 0、不進分母） |

統計：`MATCH` 比例（％，附 Wilson 95% CI 與 n）。**這一表只能說明可重現性，不能當 Q1／Q3 的正確率證據**，因為它是 `v0-pilot`／`ENGINEERING`。

**現況：`NOT_RUN`**（要等 U12 發包和組員回件）。

### 2.6 Baseline 圖表規格

| 圖 | x 軸 | y 軸 | 標示 |
| --- | --- | --- | --- |
| G-B1 事件正確率長條 | run（A4-1、B4-1、合計） | `C_evt`（%，0～100） | 誤差線是 95% CI；長條上方寫 `n=計分事件數`；不計分事件數用灰字寫在下方 |
| G-B2 切鏡延遲 | run | `L_sw`（ms） | 盒鬚圖加上每個事件的點；寫 n |
| G-B3 計分覆蓋瀑布 | 類別 | 事件數 | 全部 → 各類不計分剔除 → 實際計分；每段寫標籤 |
| G-B4 Q3 欄位正確率 | 六欄加整題 | %（0～100） | 95% CI；寫 n；`PILOT` 列的標題加「PILOT_ONLY，非正式證據」 |
| G-B5 team-eval 重現 | 回件 | MATCH／MISMATCH | 寫 n 和 Wilson CI |

所有圖的標題列都寫來源類別和 `env_manifest_sha256` 的前 8 碼。`NOT_RUN` 的格子畫成斜線空格，不省略。

### 2.7 Baseline 完成的條件

全部成立才算 Baseline 完成，第二部分才能開跑：

1. CX-7 #115 渲染完成，safe bundle 與收據經 Claude 審過（D115-2）。
2. #118 偵測索引、#329 索引交件；seed 依 D114-1 選定，選不到的 request 標 `NOT_RUN`。
3. FEAT-1 #394 合入，正式鏈在 staging 上用 `RULE_ONLY` 跑完 A4-1、B4-1。
4. 表 B-1 每個 run 都有數字，計分事件合計 ≥20。不到 20 的話 Baseline 仍算完成，但標 `INSUFFICIENT_FOR_COMPARISON`，第二部分的 M1 直接判 `INSUFFICIENT`。
5. 重播一致率 `R_hash`＝100%（AC7），#127 kit 對這些錄製 0 FAIL，或逐項寫 NOT_APPLICABLE 的原因。
6. 每個 run 都有環境 manifest（§6）。
7. Q1／Q3：有正式題目包時填表 B-2；沒有時，表 B-2 標 `NOT_RUN`，Baseline 的 Q2／Q5 部分仍然可以算完成。

### 2.8 Baseline 的依賴與 owner

| 項目 | owner | 等待 |
| --- | --- | --- |
| 渲染、索引、正式鏈執行、錄製 | Codex | D115 渲染進行中，完成日 `UNKNOWN` |
| seed 選取 | Claude | #329 |
| 評分、表 B-1～B-3、圖 G-B1～G-B5 | Claude | 錄製 |
| 正式題目包核准、U12 | 使用者 | §9 決定 C |

預估工時（估計）：錄製到位後評分與出表 1 天；分析腳本可以在 demo 後先用 fixture 寫好（0.5 天）。

### 2.9 Baseline 可能失敗的情況

| 情況 | 對策 |
| --- | --- |
| 渲染延誤 | 表 B-1 全部寫 `NOT_RUN`；報告不改用 P1 數字頂替（P1 是 SYNTHETIC） |
| 重播 hash 不一致 | 停下來，不出 Baseline 數字；先查非決定性來源 |
| 劇本有 `UNKNOWN` 欄位 | 該事件不計分，計入 `n_events_not_scored` |
| 計分事件 <20 | 照 §2.7 第 4 項處理 |

## 第二部分：建立在 Baseline 之上的比較

三個比較都依賴第一部分。共同前提：比較組要用與 Baseline **同一份**輸入、索引、劇本和參數集，只有 mode 欄位不同；Baseline 的錄製直接當 RULE 組，不重新跑。

## 3. M1：Q2 追蹤決策，RULE_ONLY（Baseline）vs AGENT_SEQUENTIAL

### 3.1 研究問題與假設

- **RQ-Q2**：在相同的候選集合和時間預算下，Agent 依序查詢候選證據後決定是否切鏡，是否比決定性規則更常做出正確的切鏡決策？
- **H1-Q2（主要）**：在 r004 正式場景的計分事件上，`AGENT_SEQUENTIAL` 的 `C_evt` 高於 Baseline（ITT：fallback 接手的步驟照原樣算進 Agent 組）。
- **H2-Q2（次要）**：只看 Agent 實際做決定的步驟，與同一步的 Baseline 決定配對比較。這是條件子集，可能有選擇偏差，因為容易的步驟比較不會逾時。
- **H0**：沒有差異，或 RULE 較好。

### 3.2 對照組公平條件

任何一項不同，該次比較就判 `INVALID_COMPARISON`，不計入。

| 項目 | 要求 |
| --- | --- |
| 輸入 | `request_sha256`、凍結索引、`candidate_snapshot_sha256` 都相同。候選集合和排序由決定性模組產生，Agent 不排序、不增刪（D64） |
| 參數 | 同一個 `parameter_set_sha256`，只差 `switch_mode` |
| 時間預算 | 每步決策期限相同；Agent 的輪數與逾時用已核定的上限，實驗中不放寬（§9 決定 B） |
| 環境 | 同一台機器、同一份環境 manifest（§6）；量延遲時兩組交錯執行 |
| 重複 | RULE 是決定性的，用 Baseline 的錄製，另外重跑 2 次確認 hash 相同；Agent 每個 request 跑 K＝5 次，記錄每次的 seed 和溫度。每個單位的 Agent 分數取 K 次的平均 |

### 3.3 主要指標與閘門

- 主要：`C_evt`（§1.7），用 v1 評分器計算。
- 閘門：Agent 組的 `FB` >20% 時，H1-Q2 最多判 `INCONCLUSIVE_UNDERPOWERED`，報告寫「Agent 大多沒有實際做決定」。
- 次要：`L_sw`（只算兩組都判 match 的事件，配對 Wilcoxon 符號秩檢定）、`FS`、`M_honest`、`TO`、`SI`、`K_call`、`T_step`。

### 3.4 表 M1-1：每個 run 的比較數字

| 欄位 | 內容 |
| --- | --- |
| `run_id`、`scene`、`request_sha256` | 與表 B-1 同一列對應 |
| `arm` | `RULE_ONLY(Baseline)`／`AGENT_SEQUENTIAL` |
| `K` | 重複次數（RULE＝1） |
| `C_evt` ％ [95% CI] | |
| `L_sw` 中位數 ms [95% CI] | |
| `FS` 次／分鐘 | |
| `TO` ％ [95% CI] | 只有 Agent 組 |
| `SI` ％ [95% CI] | 只有 Agent 組 |
| `FB` ％ [95% CI] | 只有 Agent 組 |
| `K_call` 次／步；每次呼叫 ms 中位數；token | 只有 Agent 組；token 沒記就寫 `UNKNOWN` |
| `T_step` 中位數／P90 ms | |
| `recording_sha256`（K 份都列）、`env_manifest_sha256` | |

### 3.5 表 M1-2：假設檢定結果

| 欄位 | 內容 |
| --- | --- |
| `n_pairs` | 配對單位數 |
| `n_tie`、`n_agent_better`、`n_rule_better` | |
| `diff_C_evt` 百分點 [95% CI] | |
| `p_one_sided`、`p_holm` | |
| `p_reverse_holm` | 反方向（RULE 較好） |
| `gate_FB` | PASS／FAIL |
| `verdict` | §1.6 的標籤 |
| `excluded_counts` | §1.4 每一類被排除的數量 |

**現況：兩表都是 `NOT_RUN`。**

### 3.6 資料來源與 hash

| 來源 | 內容 | 用途 |
| --- | --- | --- |
| P1 包（LOCAL）`/Users/Shared/amidst-p1-clean-room-20261026/Amidst P1 最終測試/`，`MANIFEST.json` SHA-256 `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7` | `data/recordings/2777741d96ac9aff5bffb2f61a4d2938.json`（`ffe5e693a80031e707cddb531925cb97bc6d8295b69777ad3afa1d885bd5a55a`，`decision_source=RULE_ONLY`）；`d4b67fd71caef6fb80fc9d92af544959.json`（`26a1854efb08fe0a809b957692e3f05f92f1f516972e383e1b752f9be0eb02db`，`decision_source=RULE_FALLBACK`，`fallback_reason=PROVIDER_TIMEOUT`；`agent_trace` 只有 1 個模型呼叫事件，錯誤碼 `PROVIDER_TIMEOUT`，結構欄位中另有 1 次 `SCHEMA_INVALID`）。兩份都是 `source_kind=SYNTHETIC`。本企劃只讀了 hash 和結構欄位，沒讀 GT 的值 | 只做管線冒煙測試。每組 n＝1，Agent 實際上沒做出任何決定，**不能支持也不能否定 H1-Q2**。D113-1 的旁白照舊 |
| Baseline 錄製（第一部分） | 表 B-1 的 `recording_sha256` | RULE 組 |
| 同一組正式 run 的 Agent 錄製 | Codex 產生，K＝5 | Agent 組（主要資料） |
| FEAT-6 的 176 份凍結錄製（#300／#393＠`943a72f`，LOCAL） | #127 kit rc5 重錄，給 AC7 契約一致性用；#300 記載其中有 18 次模型逾時 | **待盤點**。只有同時滿足三項才用於次要指標（`TO`、`SI`、`FB`）：有 `switch_mode`／`decision_source` 結構欄位；同一 request 在兩組都有錄製；`source_kind` 明確。**不用於主要指標**，因為沒有對應的凍結劇本，而且是工程場景 |

### 3.7 評分與 GT 隔離

評分器是 v1（§2.2）。v2 只當穩健性檢查（§4）。GT 隔離見 §1.2。

### 3.8 樣本數

A4-1、B4-1 各只有少數幾個 SWITCH／RETURN 事件。事先登錄的擴充方式只有一種：在同一組 run 上，依 D114-1 的規則產生多個 request（不同起點和時間窗），每個 request 分別計分；CI 依 run 分群。合計仍 <20 時判 `INSUFFICIENT`，不再另找資料湊數。

### 3.9 前置依賴、owner、時程

- 依賴：Baseline 完成（§2.7）；Agent 輪數／逾時的核定值寫進參數集；v1 bytes＝`97564e40…`（FEAT-6 帶 #305 進 staging）。
- owner：Codex 負責 Agent 執行和錄製；Claude 負責評分、統計、圖表；使用者決定 §9 的 A、B。
- 時程（估計）：Baseline 完成後，Agent 錄製 1 天（K＝5），評分與出表 1 天。

### 3.10 圖表規格

| 圖 | x 軸 | y 軸 | 標示 |
| --- | --- | --- | --- |
| G-M1a 配對點圖 | 組別（RULE、Agent） | 每個單位的正確率（0～1） | 每個單位一條連線，顏色分 Agent 贏／輸／平；標題寫 n、打平數、不一致數 |
| G-M1b 決策來源堆疊長條 | run | 決策步數的比例（%） | 分 `AGENT`／`RULE_FALLBACK`；超過 20% 的欄加註 |
| G-M1c 森林圖 | `diff_C_evt`（百分點） | 分析列（ITT、Agent 子集、v2 穩健性） | 95% CI；0 線與 ±5 pp 帶；每列寫 n |
| G-M1d 延遲 ECDF | `L_sw`（ms） | 累積比例（0～1） | 兩組兩條線；圖例寫 n |
| G-M1e 失敗率長條 | `TO`、`SI`、`FB` | % | 95% CI，寫呼叫數或步數當分母 |

### 3.11 可能失敗的情況

| 情況 | 對策 |
| --- | --- |
| `FB` >20% | 依閘門降級；報告逾時分布。同一次實驗不放寬逾時，要放寬就照決定 B 另開一組並重新登錄 |
| schema 失敗 | 照原樣計入 `SI`；不改 prompt 後拿同一批資料重跑來換結果。改 prompt 就是新版本，要重新登錄 |
| 計分事件 <20 | `INSUFFICIENT` |
| 兩組輸入 hash 不同 | `INVALID_COMPARISON`，整對重跑 |
| 渲染延誤到報告截止 | M1 寫 `NOT_RUN`；P1 冒煙結果照實寫「n＝1，不能判定」 |

## 4. M2：Q5 切鏡評分器 v1 vs v2

### 4.1 兩個問題要分開

| 問題 | 比什麼 | 是不是 H1 |
| --- | --- | --- |
| M2-a 評分器一致性 | 同一批凍結決策，分別用 v1 和 v2 計分 | 不是。這是在檢驗量尺本身 |
| M2-b 用評分器比較 Agent 和 RULE | 就是 M1 的 H1-Q2 | 是，但主要量尺固定用 v1 |

**事先登錄**：H1-Q2 的主要結論只用 v1。v2 只當穩健性檢查。兩版方向一致，才寫「結論對評分器版本穩健」；方向不一致，就照實寫「結論依賴評分器版本」，**不能**改用對 Agent 有利的那一版。

### 4.2 假設（M2-a）

- **H-S1**：在 v1 和 v2 都計分的 STANDARD 事件上，判定一致率 ≥99%，而且每一個不一致都能指到 v2 設計稿裡寫明的規則差異。
- **H-S2**：U6 列為不計分的類別（LONG_GAP、LONG_LOSS、ENDED_BY_LIMIT、真實 OVERLAP），v2 全部輸出不計分標籤，沒有任何一筆算進主比率。
- **H-S3**：重算兩次 hash 相同；`RECOMPUTE_AND_REJECT`（U-D5）對竄改過的輸入確實拒絕。

### 4.3 指標定義

| 代號 | 公式 | 單位 | 門檻 |
| --- | --- | --- | --- |
| `A_std` | v1 與 v2 判定相同的 STANDARD 事件數 ÷ 兩版都計分的 STANDARD 事件數 × 100 | % | ≥99 |
| `L_ns` | v2 對不計分類別輸出正確標籤的事件數 ÷ 不計分類別事件數 × 100 | % | ＝100 |
| `R_v2` | 重算 hash 相同的次數 ÷ 重算次數 × 100 | % | ＝100 |

### 4.4 版本與設定

| 項目 | 來源 |
| --- | --- |
| v1 | `src/amidst/evaluation/q5_switch_eval.py`＠#305 `f22e9da`（`97564e40…b6d3dc`）；A15：v1 一個 byte 都不改 |
| v2 設計稿 | `docs/evaluation/Q5_SWITCH_EVAL_V2_DESIGN.md`＠#258 `0b6e800`（`0a4e579b0664ab663e44809ebc0d2670b434c17161d7c24f237b1be4d051cc4c`，D114-4；**PROPOSED**） |
| v2 實作 | `q5_switch_eval_v2.py`（U-D8＝NEW_V2_MODULE），在 FEAT-4 #396，head `1ff272ffea2fa595a153106829ebf2cef3e29c8c`。D114-3：延到 demo 後，接在 FEAT-6 合入後的 staging 交件。正式 hash：`NOT_RUN` |
| U6 定案設定 | `configs/evaluation/q5_v2_decisions_u6_20261101.json`，`0daa1508e2a67607cdc6bac54684b1b5449d3a651325e5af23dfe0afb1bd3b7e`（D105-4）。預設檔 `q5_v2_decisions.json` 維持全 PENDING |
| U8（CQ-21a） | #351＠`03b369a519c8a81ffe9e5a3136d6a6ab0eb56bd3` 整批照推薦核定（D105-3） |
| 複雜情境卡 | `docs/evaluation/R004_COMPLEX_SCENARIO_CARDS_V2.md`＠#261 `b5302a0`（`02d98c06ac93b5b1eec019d65415eada7b751b4c6e76d3982a28aa36d9efd88b`；合進 mainline 時重釘，D114-3） |
| seed | D114-1：甲的 seed 只綁選取規則（例如 S_b＝CAM_W1、`[14.0, 17.0)`）；#329 索引出來後由 Claude 只看索引、照規則選 ID；選不到就 `NOT_RUN`，卡片退回 U7。formal 路徑拒絕 `UNKNOWN`／`MISSING` 的 seed |

### 4.5 常見與複雜情境的計分範圍（D105-2、D105-4）

| 情境 | 卡 | 計分 | 能不能進 H1-Q2 |
| --- | --- | --- | --- |
| 常見 | A4-1、B4-1（卡 v1） | STANDARD SWITCH／RETURN 計分 | 可以（主要） |
| 複雜「甲」 | RR-a1、RR-a2、PE1-d | 計分 | 可以，但和常見情境**分開報告**，不合成一個數字 |
| 複雜「甲」 | RR-b、LG-1 | `NOT_SCORED_PENDING_DECISION`（U-D1／U-D2 未決） | 不行 |
| 複雜「甲」 | OV1-a、OV1-b | 只展示、不計分；正式範圍是 `OVERLAP_AUTHORITY_UNSELECTED` | 不行 |
| 長卡 | A4-2、B4-2 | 暫緩（#323 選項 3） | 不行（`NOT_RUN`） |

甲目前是 UNFROZEN、走 fallback（D114-2）。甲凍結前，複雜情境的列全部寫 `NOT_RUN`。

### 4.6 表 M2-1

| 欄位 | 內容 |
| --- | --- |
| `recording_sha256` | Baseline 與 M1 的凍結決策錄製 |
| `scenario_class` | 常見／複雜甲 |
| `n_std_both_scored` | |
| `A_std` ％ | |
| `n_disagree` 與規則條目編號 | |
| `L_ns` ％ | |
| `R_v2` ％ | |
| `v1_output_sha256`、`v2_output_sha256` | |
| `C_evt_v1`、`C_evt_v2` ％（Baseline 與 Agent 各一列） | 給 M1 的穩健性列使用 |

**現況：`NOT_RUN`。**

### 4.7 依賴、owner、時程

- 依賴：Baseline 完成；FEAT-6 合入 staging；FEAT-4 #396 在其上合入；M1 的錄製（M2-a 本身不需要 Agent 錄製，只用 Baseline 錄製也能先跑）；甲凍結才跑複雜列。
- owner：Claude 負責比對腳本、混淆矩陣和報告；Codex（FEAT-4 擁有者）負責 v2 實作的交件與修正；使用者決定 U-D1／U-D2／U-D4（決定前 LONG_GAP／LONG_LOSS 一律不計分）。
- 時程（估計）：FEAT-4 合入後 0.5～1 天；FEAT-4 交件日 `UNKNOWN`。

### 4.8 圖表規格

| 圖 | 規格 |
| --- | --- |
| G-M2a v1×v2 混淆矩陣 | 行：v1 判定；列：v2 判定；格內是事件數；不一致格附規則條目編號；標題寫 n |
| G-M2b 計分覆蓋瀑布 | 同 G-B3，分 v1、v2 兩欄 |
| G-M2c 穩健性列 | 加在 G-M1c 森林圖裡的「v2」那一列 |

### 4.9 可能失敗的情況

| 情況 | 對策 |
| --- | --- |
| `A_std` <99% | H-S1 FAIL；逐筆列出不一致，回 FEAT-4 修；報告不挑版本 |
| v2 交件晚於報告 | M2 寫 `NOT_RUN`；報告寫「未做評分器穩健性檢查」 |
| v2 的方向與 v1 相反 | 照實寫「結論依賴評分器版本」；H1-Q2 的判定不改 |
| v1 bytes 不是 `97564e40…` | 停下來，不計分，回報 pin 偏移 |

## 5. M3：檢索 Q1／Q3

### 5.1 研究問題與假設

- **H1-Q3（主要）**：在正式題目上，`parser_mode=LLM_WITH_RULE_FALLBACK` 的 `E_q3` 高於 Baseline（`RULE_ONLY`）。
- **H1-Q1（主要）**：從同一道文字題出發，經各自的 Q3 解析再進 Q1 檢索，LLM 組的 `R_cam` 高於 Baseline。Q1 檢索本身是決定性的（`src/amidst/q1q5/q1_search.py`），兩組的差異只來自 Q3 的輸出。
- **H2-Q3（次要）**：只看 `parsed_by=LLM` 的題目，與同一題的 Baseline 結果配對。
- **安全面（次要，不是 H1）**：LLM 捏造非字面詞而被拒絕的比例（`q3_parse.py` 會拒絕「LLM invented nonliteral term」）；錯誤接受率（該拒答卻給出查詢）。

### 5.2 對照組

| 組 | 設定 |
| --- | --- |
| Baseline | `parser_mode=RULE_ONLY`；字面文法 `src/amidst/q1q5/q3_rules.py`＠`434e579`（`659a148224fc08b0a71a31c09a831a7a1ceb81004335a4c535a61ef02b6f5d5d`，`q3-rules.v1`） |
| LLM | `parser_mode=LLM_WITH_RULE_FALLBACK`；`src/amidst/q1q5/q3_parse.py`＠`434e579`（`ab3e80aba29f66c58654b52392c88c33266347c41d063817b6bc0eb2f42c228d`）；`q3_max_llm_attempts`、`q3_llm_timeout_ms` 用已核定值；兩組用同一個 `parameter_set_sha256` |

LLM 模式本身含規則兜底，所以 LLM 組裡有一部分題目其實是規則解析的。H1-Q3 是整組比較；H2-Q3 只看 `parsed_by=LLM`。

### 5.3 閘門

`LLM_share` <50% 時，H1-Q3 最多判 `INCONCLUSIVE_UNDERPOWERED`，報告寫「大多數題目由規則解析」。

### 5.4 題目來源，以及能不能當正式證據

| 來源 | 狀態 | 可以做什麼 | 不能做什麼 |
| --- | --- | --- | --- |
| yyin 出題包 s2（FEAT-2 #317／#369），`v0-pilot`、`evaluation_eligible=false`（D100-6） | 尚未交回 | `PILOT`：試跑、估計題目間變異 | 不能當 H1-Q3／H1-Q1 的正式證據。`q1_query_eval.py` 在這種情況下本來就不出正式指標 |
| FEAT-3 team-eval（#293，D112-1），`v0-pilot`、`evaluation_eligible=false`、`ENGINEERING`、`halves=["baseline"]` | builder 進行中；發包要 U12 | 重現性（表 B-3） | 它重播凍結輸出，組員端不跑模型，所以不會產生新的 LLM 對照資料 |
| 正式題目包（`v1`、`evaluation_eligible=true`） | 不存在 | 正式證據 | 要有正式來源，且由使用者另外核准（D105 B-8、#293 定案表）；答案要經 U13 標註 |

**事先登錄**：pilot 題和正式題不能重疊（用題目文字的 SHA-256 比對）。在 pilot 上看過結果後才改的 prompt，只能拿去跑正式題，而且要重新登錄。

### 5.5 表 M3-1

| 欄位 | 內容 |
| --- | --- |
| `question_pack`、`eligibility`、`source_class` | |
| `arm` | `RULE_ONLY(Baseline)`／`LLM_WITH_RULE_FALLBACK` |
| `n_questions_scored` | |
| `E_q3` ％ [95% CI] | |
| `F_q3[6 欄]` ％ | |
| 拒答正確率 ％ | |
| `P_cam`／`R_cam` ％ [95% CI] | |
| `LLM_share` ％ | 只有 LLM 組 |
| `TO`、`SI` ％ | 只有 LLM 組 |
| 捏造詞被拒的比例 ％ | 只有 LLM 組 |
| `K_call`、每次呼叫 ms、token | 只有 LLM 組 |
| `scorer_output_sha256`、`env_manifest_sha256` | |

另有表 M3-2（假設檢定），欄位同表 M1-2，分 H1-Q3、H1-Q1 兩列，加一欄 `gate_LLM_share`。**現況：`NOT_RUN`。**

### 5.6 樣本數

依 §1.5：不一致的題目要 ≥30。以 `LLM_share`＝50%、其中一半與規則結果不同來估算，正式題至少要 **120 題**；少於 40 題時，預期不一致題數 <10，直接判 `INSUFFICIENT`，只做描述。

### 5.7 依賴、owner、時程

- 依賴：Baseline 的表 B-2 有數字（也就是有正式題目包和答案）；#118 正式索引；Codex 產生 LLM 組的 Q3 錄製（含 `q3_provider_audit`）。
- owner：Codex 負責 LLM 呼叫和錄製；Claude 負責題目去重、評分、統計、圖表；yyin 和組員負責出題與作答；使用者負責正式包核准、U12、U13。
- 時程（估計）：pilot 在 s2 交回後 1 天；正式比較在題目包和答案到位後 2 天，日期 `UNKNOWN`。

### 5.8 圖表規格

| 圖 | x 軸 | y 軸 | 標示 |
| --- | --- | --- | --- |
| G-M3a 欄位正確率分組長條 | 六欄加整題 | %（0～100） | 兩組並列，95% CI，寫 n |
| G-M3b `parsed_by` 分布 | LLM 組 | % | 分 LLM／RULE |
| G-M3c 2×2 配對矩陣 | Baseline 對／錯 | LLM 對／錯 | 格內是題數，符號檢定直接從這裡讀 |
| G-M3d Q1 森林圖 | `R_cam` 差（百分點） | ITT、`parsed_by=LLM` 子集 | 95% CI，寫 n |

pilot 的圖一律在標題加「PILOT_ONLY，非正式證據」。

### 5.9 可能失敗的情況

| 情況 | 對策 |
| --- | --- |
| 沒有正式題目包 | H1-Q3、H1-Q1 判 `NOT_RUN`；pilot 結果照實標 `PILOT_ONLY` |
| `LLM_share` <50% | 依閘門降級，並寫原因（逾時、規則先命中等） |
| LLM 捏造詞被拒的比例高 | 照實報告；這是 LLM 組的失敗，不從分母剔除 |
| 人工答案有爭議 | 該題記 `UNKNOWN`，兩組都不計，列出爭議題數 |

## 第三部分：實驗環境揭露

## 6. 環境 manifest

每一個 run（Baseline、M1 的每次 Agent 重複、M3、外包機的每次執行）都要附一份環境 manifest，報告逐一點名使用到的設備、套件和模型。manifest 本身的 SHA-256 寫進對應表格的 `env_manifest_sha256` 欄。

### 6.1 現有基準

`configs/q1q5/linked_baseline_environment.json`＠staging `434e579`（SHA-256 `2e75735c8d3b1e5c803f03e50b3eaffe8ade8166a949c9b96a731d85e72b592b`）記錄的值：

| 項目 | 值 |
| --- | --- |
| Python | 3.12.12 |
| machine | arm64 |
| 套件 | pydantic 2.13.5、numpy 2.5.4、Pillow 13.0.0、torch 2.6.0、torchvision 0.21.0、PyYAML 6.0.3、networkx 3.7、shapely 2.1.2、psycopg 3.3.6 |
| Ollama | 0.35.0 |
| 模型 | `qwen3:1.7b-q4_K_M`，digest `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7` |
| RT-DETR 權重 | SHA-256 `3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0`；source commit `df2a96c8c3a098567a1149bf0248da6efe6d495d` |
| 依賴權威 | `pyproject.toml`、`uv.lock`（`uv.lock`＠`434e579` SHA-256 `18c66a46f799efcfb4da36a15246245d2c959e42768a67b01f667eb73d284a17`） |

這份檔案沒有硬體、OS、隨機種子和逾時的欄位，所以需要擴充成下面的 manifest。

### 6.2 manifest 欄位（建議 schema 名 `amidst.experiment-env.v1`，PROPOSED）

| 群組 | 欄位 | 取得方式 |
| --- | --- | --- |
| 硬體 | `cpu_model`、`cpu_cores`、`gpu_model`（沒有就寫 `NONE`）、`gpu_driver`、`ram_gib`、`accelerator`（`mps`／`cuda`／`cpu`） | 標準函式庫加上平台指令；取不到的欄位寫 `UNKNOWN`，不猜 |
| OS | `os_name`、`os_version`、`kernel`、`arch` | `platform` 模組 |
| Python | `python_version`、`python_implementation`、`isolated_mode` | `sys` |
| 套件 | `uv_lock_sha256`、`pyproject_sha256`，以及實際安裝版本的清單 | 以 `uv.lock` 為權威；實際安裝版本和 lock 不一樣時列出差異 |
| 模型 | `llm_name`、`llm_digest`、`ollama_version`、`detector_name`、`detector_weights_sha256`、`detector_source_commit` | Ollama API 加上權重檔的 hash |
| 執行設定 | `switch_mode`、`parser_mode`、`parameter_set_sha256`、`agent_max_rounds`、`agent_timeout_ms`、`q3_max_llm_attempts`、`q3_llm_timeout_ms`、`llm_temperature`、`llm_seed`、`torch_deterministic`、`random_seed` | runner 的參數集 |
| 程式 | `git_commit`（外包包則用包的 MANIFEST SHA-256） | |
| 時間 | `started_at_utc`、`finished_at_utc`、`wall_clock_s` | runner |

報告的附錄是一張「環境總表」：每個 `env_manifest_sha256` 一列，列出上面的所有欄位。所有表格都用這個 hash 對回去。

## 第四部分：跨平台外包執行包

## 7. 跨平台外包執行包

### 7.1 目的與順序

1. demo 結束後，先在本機（Mac）把完整系統錄一次影片紀錄。影片是 LOCAL，committed 文件只列路徑、大小和 SHA-256。這段影片只是展示紀錄，不是實驗數據。
2. 再把「模型對系統的測試」外包到其他作業系統：整包帶過去跑，回傳原始輸出和環境 manifest，**評分在我們這邊做**。
3. 順序：**先 Linux，再 Windows**。
4. 這個包和 FEAT-3 team-eval 不同：team-eval 重播凍結輸出、不跑模型（D96-2）；外包包要在外包機上**實際跑** RT-DETR 和 Qwen3。

### 7.2 包的內容（照 r004 v2 組員包格式）

| 放 | 內容 |
| --- | --- |
| `README` | 三節：**工作內容**、**要提交的項目**、**操作步驟**，外加「不要改」 |
| `RETURN/README.txt` 與指定的 RETURN 檔名 | `RETURN/外包結果_<代號>_<OS>_YYYY-MM-DD.zip`（內含輸出、manifest、log） |
| `MANIFEST.json` | 逐檔 SHA-256，分成不可變 payload 和 RETURN／STATE 兩類 |
| `tools/verify_pack.py` | 驗 MANIFEST；回收時也用它判定 VALID／INVALID |
| `run.py` | 跨平台的 Python 入口（不用 `.command`，也不用 `.bat` 當主要入口） |
| `tools/check_env.py` | 產出 §6 的環境 manifest，並檢查 Python、套件、Ollama、模型 digest、權重 hash；不符合就停下並寫明哪一項 |
| 凍結輸入 | 正式 run 的 safe bundle（RGB 或來源綁定的安全欄位）、凍結索引、request、參數集。**不含 GT、劇本、渲染軌跡、visibility、depth** |
| runner 程式 | 對應 staging commit 的必要模組，以 `uv.lock` 鎖版本 |

**不放**：GT、評分器的正確答案、劇本、任何答案檔。禁止內容掃描沿用 #318（`scripts/check_handoff_pack.py` 的 `scan()`）。模型權重要不要放進包裡，見 §9 決定 D。

### 7.3 跨平台要求

- 入口：`python run.py --task <baseline|agent|q3>`，Python ≥3.12，用 `-I` 執行。
- 路徑：一律用 `pathlib`，包內路徑以包根目錄為基準的相對路徑；不寫死 `/`，不假設大小寫敏感；檔名只用 ASCII（中文檔名在 Windows ZIP 解壓有編碼風險，RETURN 檔名的「外包結果」需要實測，失敗就改用 ASCII 名）。
- 文字檔一律用 UTF-8 讀寫，換行固定 `\n`，避免 Windows 的 `\r\n` 改到輸出 hash。
- 加速器：依序偵測 `cuda`、`mps`、`cpu`，寫進 manifest；不允許靜默改變 batch size 或精度。
- 時間：只用 source clock 和單調時鐘；不使用本機時區。

### 7.4 RETURN 內容

| 項目 | 說明 |
| --- | --- |
| `env_manifest.json` | §6 的全部欄位 |
| `outputs/` | 決策錄製、Q3 解析回應、Q1 結果（原始輸出，不含分數） |
| `output_sha256.json` | 每個輸出檔的 SHA-256 |
| `timing.json` | 每個 task 的牆鐘時間、每步 `T_step`、每次模型呼叫的 ms |
| `logs/` | runner log（不含私人路徑） |
| `pack_manifest_sha256` | 必須等於發出去的包 |

### 7.5 回收與評分（在我們這邊）

1. `verify_pack.py` 驗 RETURN：VALID／INVALID。INVALID 就整份不計（§1.4 第 10 項）。
2. 驗 `output_sha256`，並檢查 `env_manifest` 是否完整。
3. Claude 的評分端讀劇本／答案計分，產出與表 B-1、M1-1、M3-1 同格式的表，`source_class` 不變，另加 `os` 欄。
4. 跨 OS 比較表 X-1：

| 欄位 | 內容 |
| --- | --- |
| `os`、`env_manifest_sha256` | |
| `task`、`arm` | |
| `output_hash_equal_to_mac` | 是／否（逐檔） |
| `decision_diff_count` | 與 Mac 對照 run 決策不同的步數 |
| `C_evt`／`E_q3`／`R_cam` ％ [95% CI] | |
| `TO`、`SI`、`FB` ％ | |
| `T_step` 中位數／P90 ms | |
| `wall_clock_s` | |

**現況：`NOT_RUN`。**

### 7.6 已知變因與 Mac 對照 run

| 變因 | 影響 | 處理方式 |
| --- | --- | --- |
| 浮點運算差異（CPU／CUDA／MPS 的 kernel 不同） | RT-DETR 偵測分數的末位不同，可能跨過門檻，改變偵測或決策 | 記錄 `accelerator`；比較偵測輸出的差異分布；決策不同的步驟逐一列出 |
| 模型非決定性（Ollama 的取樣、執行緒排程） | Agent 和 Q3 LLM 的回應不同 | 固定 `llm_temperature`、`llm_seed`；Agent 每個 request 跑 K＝5 次，比較的是分布，不是單次 |
| 速度差異 | 逾時率不同，連帶 fallback 比例不同 | `TO`、`FB` 依 OS 分列；不用 Mac 的逾時率去推其他 OS |
| 套件版本 | 實際安裝和 `uv.lock` 不一樣 | `check_env.py` 不符合就停下；manifest 列出差異 |

**Mac 對照 run**：同一份包（同一個 MANIFEST SHA-256），在 Mac 上用 `run.py` 跑一次完整流程，產出 Mac 的 RETURN。跨 OS 的差異一律以這份 Mac RETURN 為對照，而不是拿 repo 裡的正式鏈錄製來比，避免把「包」和「平台」兩種差異混在一起。

RULE_ONLY 的決策只依賴偵測輸出，偵測一樣時決策 hash 應該相同，可以用來分辨差異是來自偵測還是 Agent。

### 7.7 可行性風險與預估工時（估計）

| 風險 | Linux | Windows | 對策 |
| --- | --- | --- | --- |
| torch 2.6.0／torchvision 0.21.0 的平台 wheel 與 CUDA 版本 | 中 | 中高 | `uv.lock` 要包含對應平台的 wheel；沒有 GPU 時走 CPU，manifest 標明 |
| Ollama 0.35.0 安裝與指定 digest 的模型 | 低 | 中 | README 寫安裝步驟；`check_env.py` 驗 digest，不符就停下 |
| 模型權重的授權與大小 | 中 | 中 | §9 決定 D |
| 路徑、編碼、換行 | 低 | 高 | §7.3；先在 Linux 驗證 hash 穩定，再做 Windows |
| PostgreSQL（psycopg）依賴 | `UNKNOWN` | `UNKNOWN` | 先確認外包流程是否需要資料庫；需要的話改用包內的凍結檔 |
| 包的大小（RGB 與權重） | 中 | 中 | 只放 A4-1／B4-1 需要的影格；量出大小後寫進 README |
| 外包機無法上網 | `UNKNOWN` | `UNKNOWN` | 權重和模型改成離線放入（決定 D） |

| 工作 | owner | 估計工時 |
| --- | --- | --- |
| 本機完整影片紀錄 | 使用者或 Codex | 0.5 天 |
| `run.py`、跨平台路徑、`check_env.py`、manifest | Codex | 1.5～2 天 |
| 包的 builder、MANIFEST、verify、README、禁止內容掃描 | Codex（沿用 #318、FEAT-3 的做法） | 1 天 |
| Mac 對照 run | Codex | 0.5 天 |
| Linux 實測與修正 | 外包者＋Codex | 1～2 天 |
| Windows 實測與修正 | 外包者＋Codex | 2～3 天 |
| 回收評分、跨 OS 表 X-1 與圖 | Claude | 1 天 |

### 7.8 圖表規格

| 圖 | 規格 |
| --- | --- |
| G-X1 跨 OS 指標點圖 | x：OS（Mac 對照、Linux、Windows）；y：`C_evt`／`E_q3`（%）；95% CI；寫 n |
| G-X2 決策差異 | x：OS；y：與 Mac 決策不同的步數；依來源（偵測差異／Agent 回應差異）堆疊 |
| G-X3 速度與逾時 | x：`T_step`（ms，對數軸）；每個 OS 一條 ECDF；圖例寫 `TO` ％ 與 n |

## 8. 資料到位就能開跑：檢查表

每一項都要附證據（命令輸出、SHA-256、留言連結）。任何一項沒勾，該段不開跑。

### 共用

- [ ] 本文件的事先登錄 commit SHA 已記在結果紀錄。
- [ ] 分析腳本已在 SYNTHETIC fixture 上通過，SHA-256 已記錄，之後不再修改。
- [ ] 磁碟可用 ≥9 GiB（`df -g /`）。
- [ ] 每個 run 的環境 manifest（§6）都已產出，`env_manifest_sha256` 已記錄。
- [ ] GT 隔離檢查（#307 守門、#127 kit GT 掃描）對決策錄製 PASS。

### 第一部分 Baseline

- [ ] CX-7 #115 的 safe bundle 與收據已交、已審；run／clock 的 SHA-256 已填。
- [ ] #118、#329 索引已交，SHA-256 已填；seed 依 D114-1 選定。
- [ ] 劇本凍結 `ab45a832…` 未變；G4 `9d99f87e…bc76c` 仍生效。
- [ ] FEAT-1 已合入，正式鏈用 `RULE_ONLY` 跑完 A4-1、B4-1。
- [ ] v1 評分器 bytes＝`97564e40…b6d3dc`。
- [ ] `R_hash`＝100%，#127 kit 0 FAIL（或逐項寫 NOT_APPLICABLE 的原因）。
- [ ] 表 B-1 每列都有數字；計分事件合計已數出（≥20 或標 `INSUFFICIENT_FOR_COMPARISON`）。
- [ ] Q1／Q3：正式題目包已核准，或表 B-2 標 `NOT_RUN`。
- [ ] team-eval：U12 已同意、包已發、回件已收，或表 B-3 標 `NOT_RUN`。

### 第二部分

- [ ] Baseline 完成（§2.7）。
- [ ] M1：Agent 輪數／逾時核定值已寫進參數集；兩組的 `parameter_set_sha256` 只差 mode 欄位（附 diff）。
- [ ] M2：FEAT-6、FEAT-4 已合入，v2 SHA-256 已填；U6 設定檔＝`0daa1508…bd3b7e`；甲是否凍結已確認。
- [ ] M3：正式題數 ≥40（≥120 才有足夠檢定力）；pilot 和正式題不重疊。

### 第四部分 外包

- [ ] 本機影片紀錄的 LOCAL 路徑、大小、SHA-256 已記錄。
- [ ] 包的 MANIFEST SHA-256 已記錄；禁止內容掃描 PASS（沒有 GT、劇本、答案）。
- [ ] Mac 對照 run 已完成。
- [ ] 決定 D 已定。

## 9. 需要使用者決定的事項

### 決定 A：H1 的主要分析方式

1. **（推薦）整組比較（ITT）為主，Agent 實際決策的子集為次。**優點：反映系統的真實表現，fallback 藏不住，也不會因為只挑 Agent 沒逾時的步驟而高估。缺點：逾時多時，Agent 的表現會被規則稀釋，較難得到 SUPPORTED。
2. **只看 Agent 實際做決定的步驟。**優點：比較接近模型本身的判斷力。缺點：有選擇偏差；fallback 比例高時樣本很少；容易被質疑是在挑資料。

### 決定 B：Agent 的逾時上限

1. **（推薦）沿用已核定的上限，不放寬，逾時照實計入。**優點：比的就是實際會用的系統，公平性最清楚。缺點：P1 那份就是 1 次呼叫、1 次逾時；正式 run 也大量逾時的話，H1 很可能判 INCONCLUSIVE。
2. **另加一組放寬逾時的 Agent。**優點：可以把「模型能力」和「在時間預算內的能力」分開回答。缺點：放寬組和 RULE 的時間預算不同，只能當探索性結果；執行時間加倍；新的上限要使用者核定。

### 決定 C：M3 的正式題目從哪裡來

1. **（推薦）s2／team-eval 只做 pilot，另請 yyin 出一份不重疊的正式題（`v1`、`evaluation_eligible=true`），經使用者核准。**優點：pilot 和正式題分開，符合 D105 B-8。缺點：要多一輪出題和標註，正式結果最快也在 demo 後一週以上。
2. **把 s2 升成 `evaluation_eligible=true`。**優點：最快。缺點：s2 本來是 pilot 設計；看過結果後再升級，就不是乾淨的事先登錄樣本。
3. **M3 只做 pilot。**優點：不增加工作。缺點：Q3／Q1 沒有正式結論。

### 決定 D：外包包裡的模型權重

1. **（推薦）包裡不放權重；`check_env.py` 依 digest 和 SHA-256 引導外包者自行下載，驗不過就停下。**優點：包小，避開權重再散布的授權問題，hash 仍然可以核對。缺點：外包機要能上網；下載步驟在 Windows 上可能出錯。
2. **權重和 Ollama 模型檔離線放進包裡。**優點：外包機不需要上網，最容易重現。缺點：包會變大，大小 `UNKNOWN`，要先量；要先確認 RT-DETR 權重和 Qwen3 的授權允許轉交。

## 10. 引用

| 文件 | ref | SHA-256 |
| --- | --- | --- |
| `docs/specs/DEVELOPMENT_RULES.md` | `origin/claude/rules-d108`＠`994b700` | `b01c60b7a8430de8ff45f6c8b911d5669dd2bdf5791dde9ad7487300387419a5` |
| `docs/agents/Q1Q5_DEMO_SCRIPT.md`（B-05a／B-05b） | #384＠`cf325aa9addeb801bb75da86a533bc42cb9b3f77` | `e1c543645ec8b659aa733ae1a9589893a84bc09d3f5a5a41c3f2a870293d30ea` |
| `src/amidst/evaluation/q5_switch_eval.py` | staging＠`434e579`／#305＠`f22e9da`（A15 例外） | `0fd1ef68c4c83443e8311723224b76f103c142dd018275e7c1596f917e85d9f2`／`97564e401cb7d70a7cc22113a008477b447974536ae207aabc230868e8b6d3dc` |
| `docs/evaluation/Q5_SWITCH_EVAL_V1.md` | staging＠`434e579` | `8457b2849b926b8534b1e43f71c98729f92ccd0320c2c73a89a78fe7ba6008cf` |
| `docs/evaluation/Q5_SWITCH_EVAL_V2_DESIGN.md` | #258＠`0b6e800` | `0a4e579b0664ab663e44809ebc0d2670b434c17161d7c24f237b1be4d051cc4c` |
| `src/amidst/evaluation/q3_parse_eval.py` | staging＠`434e579` | `4660edea0b204dfdead99cd1e2ebc5b8ce13ccffbd9d78c157ba285abda298c4` |
| `src/amidst/evaluation/q1_query_eval.py` | staging＠`434e579` | `eb403f968d3263cb5151219c9e46dddc8922d0f7ba9f21b7c07a276f44f973b9` |
| `src/amidst/q1q5/q3_rules.py` | staging＠`434e579` | `659a148224fc08b0a71a31c09a831a7a1ceb81004335a4c535a61ef02b6f5d5d` |
| `src/amidst/q1q5/q3_parse.py` | staging＠`434e579` | `ab3e80aba29f66c58654b52392c88c33266347c41d063817b6bc0eb2f42c228d` |
| `src/amidst/q1q5/q5_controller.py` | staging＠`434e579` | `1dcd0a53cf73bb2483c200be50f52f11ca35607ceaa5432c598343879c1719c7` |
| `configs/q1q5/linked_baseline_environment.json` | staging＠`434e579` | `2e75735c8d3b1e5c803f03e50b3eaffe8ade8166a949c9b96a731d85e72b592b` |
| `uv.lock` | staging＠`434e579` | `18c66a46f799efcfb4da36a15246245d2c959e42768a67b01f667eb73d284a17` |
| `docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md` | mainline＠`0d78599` | `015201556f550ab67dbbebead35916db426a3b6a05066ffc94c928696900ddbd` |
| `docs/evaluation/R004_COMPLEX_SCENARIO_CARDS_V2.md` | #261＠`b5302a0` | `02d98c06ac93b5b1eec019d65415eada7b751b4c6e76d3982a28aa36d9efd88b` |
| `docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json` | #354＠`48133c1a` | `ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb` |
| `configs/evaluation/q5_v2_decisions_u6_20261101.json` | FEAT-4 #396＠`1ff272f` | `0daa1508e2a67607cdc6bac54684b1b5449d3a651325e5af23dfe0afb1bd3b7e` |
| P1 包 `MANIFEST.json`（LOCAL） | — | `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7` |

決策：#93 的 D105-1～D105-4、D112-1、D113、D114-1～D114-4、D115；架構基準 #306（A15、P1）；FEAT-1 #376、FEAT-3 #370／#293、FEAT-4 #371、FEAT-6 #373、CQ-19 #300；驗收標準 AC1～AC8（`docs/agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md`＠mainline `0d78599`）。
