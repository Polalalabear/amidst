# 預錄三事件：規則 vs LLM 覆核（D325，2026-11-18）

> **更正說明（2026-11-20，issue [#649](https://github.com/Polalalabear/amidst/issues/649)）**：本文的數字與表格不變，以下結論的適用範圍與一處計數已修正。
>
> 1. **結論只適用於「LLM 覆核、不看圖」的架構。** 本分析的 LLM 只拿到不透明代號與軌跡摘要，沒有收到任何影格，只能在規則已判合格的候選中選或 ABSTAIN；而且 A4-1、B4-1 是簡單場景（各 1 個目標、目標在所有鏡頭都看不到的最長時間 1.0／0.4 s）。§1 第 1 條「LLM 沒有帶來可量到的好處」與第 2 條「原因是題目，不是模型」**不能推論為「LLM 無效」**：差異同時來自「沒有送圖、只覆核」與「題目簡單」。見 PR [#637](https://github.com/Polalalabear/amidst/pull/637)（`docs/evaluation/RULE_VS_LLM_RECORDED_AND_LIVE_20261120.md` §1.3，分支 head `6c318377`）。
> 2. **「34 個決策點規則都只有 0 或 1 個合格候選」應為 32 個。** B4-1 24.8 s、25.0 s 的兩個 DP1 各有 2 個合格候選（CAM_W1、CAM_W2），但兩者是同一個紅衣人在重疊鏡頭的影像，選哪個都對；「沒有任何決策點需要在兩個不同的人之間選擇」的判斷不變。見 PR #637 §1.2b。
> 3. **看圖的結果見 PR [#647](https://github.com/Polalalabear/amidst/pull/647)**（`docs/evaluation/VISION_AGENT_RECORDED_20261120.md`，分支 head `b6e99c9d`）：同樣兩個事件，離線可等待時看圖 Agent 把失聯秒由 2.6／4.2 s 降到 0.8／1.2 s，不給圖的對照組與本文一致沒有改善；模擬即時則因呼叫延遲沒有增益。該實驗 n＝2 事件、K=3，只談機制可行性。
> 4. 失聯秒的成因分解（覆核架構最多只能救回 B4-1 的 0.4 s）見 PR #637 §1.2c；8785 Agent 開關實際上走不到模型，見 `docs/evaluation/AGENT_ZERO_CANDIDATES_629.md`（PR #635）與 PR [#648](https://github.com/Polalalabear/amidst/pull/648)。

授權：D325（使用者核准的 OpenAI 分析，上限 USD 10）。分析執行 session：`eval-recorded-llm`。本文件是研究紀錄，數字全部抄自 LOCAL 報告 `local/evidence/eval-recorded-llm-20261118/REPORT.md`（SHA-256 `2f6bd7c61c16aa158515e612c03b06c2eb98c38c6c16a6ef91c520c9e6013b31`）與 `tables.md`（SHA-256 `9da1910487f28fbb6a22f037a805dacfd41b4b76ab57a621e06a41b1dd0eab1c`），沒有重算。相關 issue：[#597](https://github.com/Polalalabear/amidst/issues/597)（難題集，CL-B11）、[#620](https://github.com/Polalalabear/amidst/issues/620)（CL-B16，8785 Q2 Agent 開關）、報告素材 [#479](https://github.com/Polalalabear/amidst/issues/479)。

- Model / effort（本文件撰寫）：Claude Opus 5.5；effort UNKNOWN（session 看不到自己的設定）。分析本身的 model / effort：UNKNOWN（報告沒有記錄）。
- 這是工程量測，不是辨識、身分或實體安全的正式驗收。「跟對」只表示顯示的框落在 GT 目標位置；身分仍然未確認。
- 沒有統計顯著性：2 個可評分事件、每事件 17 個決策點、K=3。只寫逐案比較。

## 1. 結論

1. **在這三個預錄事件裡，LLM 沒有帶來可量到的好處。** A4-1、B4-1 上 terra6.1、sol6.1 各跑 3 次，跟對率、失聯秒、錯人秒都和規則相同（A4-1 0.970／2.6 s／0 s；B4-1 0.906／4.2 s／0 s）。唯一的差別是 sol6.1 在 B4-1 第 2 次於 25.2 s 把 DP1 改成 ABSTAIN，0.2 s 由「對」變「失聯」，跟對率 0.906→0.901，**略差**。
2. **原因是題目，不是模型。** 34 個決策點（每事件 DP1×8＋DP3×9）規則都只有 0 或 1 個合格候選（A1 或 ABSTAIN、ACCEPT_SEGMENT）。規則的錯人秒本來就是 0，沒有「規則追丟、LLM 接回」或「規則錯人、LLM 糾正」的空間。採用的 LLM 決策中，與規則不同的只有上面那 1 次。
3. **要證明 LLM 的價值，需要 #597 的難題集**（多候選、相似人物、長時間失聯）。
4. **LLM 的代價是真的**：單次呼叫 p50 約 4.3–5.5 s、p95 約 6.7–7.4 s；整段事件重放 80–116 s（規則 0.0 s）；本次花費 USD 0.4115。
5. **B-05 不適用**：沒有 decider 注入點，而且沒有 GT 檔（見 §6）。

## 2. 資料與版本

| 項目 | 值 |
| --- | --- |
| 程式版本 | `main` `b98fac2a`（`~/amidst` 唯讀，沒有改任何 repo 檔案） |
| 服務 | 8810 QA 埠 |
| 事件 | r004 A4-1、B4-1（可評分）；B-05（合成 P1 事件，只跑規則） |
| 模型 | OpenAI terra6.1（gpt-6.1-terra）、sol6.1（gpt-6.1-sol），各 K=3 |
| 逾時 | D313：每輪 8000 ms、一步 24000 ms、最多 3 輪（不是 formal 的 5000／5000） |
| 付費護欄 | 每次呼叫都經 `ApiGuard`（caller=`d325_eval`）；dry-run 最壞估計約 USD 2.8，上限 USD 10 |
| 種子 | 沿用 8785 的自動種子（最早的局部種子），沒有人工挑選 |

## 3. 方法

- **比較的是什麼**：#604 的 8785 Agent 開關綁的是 Q5 `AgentController`（Q2 工作階段），在這三個真實事件上回 `TRACKING_SCOPE_MISSING`（8810 實測），不能用。因此本分析改走離線 Agent 決策：`agent_wiring.AgentDecider` 注入 `cross_camera_demo.associate()` 的 DP1（選候選／ABSTAIN）與 DP3（接受片段），也就是 8785 `q_core_track` 規則所在的位置；provider 是 `OpenAIProvider`。所以這是「`associate()` 規則 vs 加 LLM 覆核」，**不是 8785 畫面上的 Agent 開關**。
- **規則組**：同一個 `associate()`，不注入 decider。
- **退回**：LLM 回答不合法或逾時時，`AgentDecider` 退回規則答案（`RULE_FALLBACK:<原因>`）。
- **GT 只用於評分**：GT 是 r004 `gt_private/frame_journal.jsonl` 的目標 T 腳點世界座標（每 0.2 s 一個 tick），用相機標定投影成身體框；「目標被偵測」是索引中有框（score≥0.3）的中心落在投影框內。GT 沒有進入推論、排序或提示詞；請求由 `agent_wiring` 建立，只含不透明代號與局部軌跡摘要。
- **指標**（逐 tick 對 GT）：
  - 跟對率＝顯示的鏡頭／框在目標上的 tick ÷ 目標在某台鏡頭被偵測到的 tick；
  - 失聯秒＝目標可被偵測卻顯示 GAP；
  - 錯人秒＝顯示的框不在 GT 目標位置；
  - 盲區誤鎖秒＝目標在所有鏡頭都沒被偵測卻顯示 ON_CAMERA。
- 載入用精簡版唯讀 loader（沒用 `Demo` 類別，因為它的 8 GiB 磁碟護欄在當時 6.6 GiB 可用空間下會擋，而分析不需要它的寫入）。

## 4. 總表

數字是 K 次平均，方括號是 [最小–最大]。

| 事件 | 模型 | K | 跟對率 | 失聯秒 | 錯人秒 | 盲區誤鎖秒 | 決策點×K | LLM 採用 | 退回規則 | LLM≠規則 | 單次呼叫 p50／p95 ms | 花費 USD（K 次合計） | 一次整段牆鐘 s |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| A4-1 | 規則 | 1 | 0.970 | 2.6 | 0.0 | 0.0 | — | — | — | — | — | — | 0.0 |
| A4-1 | terra6.1 | 3 | 0.970 | 2.6 | 0.0 | 0.0 | 51 | 45 | 6 | 0 | 5341／7360 | 0.0726 | 104 |
| A4-1 | sol6.1 | 3 | 0.970 | 2.6 | 0.0 | 0.0 | 51 | 45 | 6 | 0 | 5527／6936 | 0.1528 | 116 |
| B4-1 | 規則 | 1 | 0.906 | 4.2 | 0.0 | 0.0 | — | — | — | — | — | — | 0.0 |
| B4-1 | terra6.1 | 3 | 0.906 | 4.2 | 0.0 | 0.0 | 51 | 51 | 0 | 0 | 5545／7409 | 0.0649 | 97 |
| B4-1 | sol6.1 | 3 | 0.905 [0.901–0.906] | 4.3 [4.2–4.4] | 0.0 | 0.0 | 51 | 49 | 2 | 1 | 4264／6661 | 0.1211 | 82 |

與規則的差異：A4-1 兩個模型 6 次都沒有任何顯示差異（0 段、0.0 s）。B4-1 只有 sol6.1 第 2 次有 1 段：25.2–25.4 s 規則顯示 CAM_W2（CORRECT），LLM 顯示 GAP（MISSED）。逐決策點與逐切鏡點的完整表見 LOCAL `tables.md` §3、§4。

## 5. 退回規則的原因

| 事件 | 模型 | 決策點×K | 呼叫次數 | OK | PROVIDER_TIMEOUT | INVALID_RESPONSE | 退回原因分布 |
|---|---|---:|---:|---:|---:|---:|---|
| A4-1 | terra6.1 | 51 | 54 | 45 | 3 | 6 | INVALID_RESPONSE 6 |
| A4-1 | sol6.1 | 51 | 59 | 45 | 8 | 6 | INVALID_RESPONSE 6 |
| B4-1 | terra6.1 | 51 | 51 | 51 | 0 | 0 | 無 |
| B4-1 | sol6.1 | 51 | 53 | 49 | 2 | 2 | INVALID_RESPONSE 2 |

- **逾時（PROVIDER_TIMEOUT）重試後都成功，沒有造成退回。** 原本的 2 s／5 s 逾時在這個延遲下必逾時，要靠 D313 的 8 s 才行。
- **A4-1 的 INVALID_RESPONSE 集中在 9.2 s、37.2 s 兩個 DP1**：terra6.1 與 sol6.1 各 3 次都一致退回（規則答案 A1）。B4-1 sol6.1 在 21.0 s 的 DP1 偶發 2 次。
- **事後診斷（附錄 A，同樣兩個請求再打 terra6.1 各 1 次，約 USD 0.006，經 ApiGuard）**：
  - 37.4 s 的請求：**確認是回應的 `reason_codes` 有 5 個，超過上限 4 個**（`MAX_REASON_CODES`），驗證器回 `INVALID_RESPONSE:reason_codes`。模型的決定本身是 ABSTAIN，內容合理，但格式不合法。
  - 9.4 s 的請求：這次回應合法（SELECT A1，4 個理由碼），沒有重現。分析當時 6 次都退回，推測同樣是理由碼超過 4 個，但當時原始回應沒保存，**無法確認（UNKNOWN）**。
  - 共通情境：候選 A1 的 `graph_edge=False`（圖上沒有 EXT_CLEAR→EXT_CAR 邊）、間隔 0.2 s、分數低，模型傾向多列理由（含 NO_GRAPH_EDGE、LOW_SCORE）。
  - 診斷請求時間（9.4 s、37.4 s）和決策點時間（9.2 s、37.2 s）的 0.2 s 差異在報告中沒有說明（UNKNOWN）。
- 影響：退回時答案等於規則答案，對分數沒有影響；但 LLM 在「圖上無邊」的邊界情況約有 12% 退回。可行修法（未做，需決定）：提示明寫「最多 4 個 reason_codes」，或在驗證前截斷為前 4 個。目前沒有開 issue。

## 6. B-05 不適用

- B-05 是合成 P1 事件，走 `q_core_track` 而不是 `associate()`，**沒有 decider 注入點**，所以 LLM 組不適用。8785 的 Q2 Agent 開關（#604）在三個事件上都回 `TRACKING_SCOPE_MISSING`，修正追蹤在 [#620](https://github.com/Polalalabear/amidst/issues/620)。
- GT 評分 **UNKNOWN**：沒有找到 B-05 的 GT 檔。
- 規則輸出：LOCAL `raw/RULE_B-05_q_core_track.json`（狀態 LOST，A／B 兩台 20 段）。

## 7. 代價

| 項目 | 值 |
| --- | --- |
| 單次呼叫延遲 | p50 約 4.3–5.5 s，p95 約 6.7–7.4 s（見 §4 逐列） |
| 整段事件重放牆鐘 | 80–116 s（規則 0.0 s） |
| 花費（每模型每事件 K=3） | terra6.1 約 USD 0.065–0.073；sol6.1 約 USD 0.12–0.15 |
| 本次總花費 | **USD 0.4115**（ApiGuard 帳本 `local/evidence/api-usage/usage.jsonl`，caller=`d325_eval`；帳本持續追加，SHA-256 不適用）；逾時呼叫沒有 usage，帳本按估價計，是上界 |
| 事後診斷 | 約 USD 0.006（另計） |

## 8. 限制

- 只涵蓋兩個單人目標的基線事件；B-05 沒有 LLM 組也沒有 GT。
- 跟對率的分母是「偵測得到」的 tick，偵測漏掉的 tick 不算「目標可見」，所以是「偵測得到時有沒有顯示對」，不是影片真實可見率。
- GT 不含其他人物，所以「錯人」只表示顯示的框不在 T 的位置。
- 比較的是 `associate()` 的 DP1／DP3 覆核，不是 8785 畫面上的 Agent 開關，也不是 LIVE 模式的規則 vs LLM（那是 #597 CL-B11 本體）。
- 逾時用 D313 設定，不是 formal 的 5000／5000 ms。
- 沒有統計顯著性（K=3）。

## 9. 後續

1. #597 難題集（PR [#622](https://github.com/Polalalabear/amidst/pull/622)）就緒後，跑 LIVE 的規則 vs LLM 重播比較（CL-B11 本體），付費先 ApiGuard dry-run。
2. `reason_codes` 超過 4 個的提示／截斷修正：未開 issue，待協調者決定。
3. #620：讓 8785 Q2 Agent 開關在 A4-1、B4-1 可用，B-05 顯示「不適用」。

## 10. LOCAL 產出

目錄：`local/evidence/eval-recorded-llm-20261118/`（LOCAL，不進版控；`SHA256SUMS` 的 SHA-256 `49c2d7903b24278f066b07d9d354f475b328840c98ab6283f0b344da818f1252`）。共 29 檔、約 2.3 MB（`raw/` 約 2.3 MB、`scripts/` 約 32 KB）。`SHA256SUMS` 列出其餘 28 檔，撰寫本文件時 `shasum -a 256 -c SHA256SUMS` 全部 OK。

| 路徑（相對上列目錄） | 內容 | SHA-256 |
| --- | --- | --- |
| `SHA256SUMS` | 其餘 28 檔的雜湊清單 | `49c2d7903b24278f066b07d9d354f475b328840c98ab6283f0b344da818f1252` |
| `REPORT.md` | 完整報告（含附錄 A 診斷） | `2f6bd7c61c16aa158515e612c03b06c2eb98c38c6c16a6ef91c520c9e6013b31` |
| `tables.md` | 總表、退回、逐決策點、逐切鏡點 | `9da1910487f28fbb6a22f037a805dacfd41b4b76ab57a621e06a41b1dd0eab1c` |
| `raw/`（17 檔） | 每個（模型、事件、重複）的完整回應、tick 判定、決策紀錄、請求、帳本列；規則組 3 檔；診斷 2 檔 | 見 `SHA256SUMS` |
| `scripts/`（6 檔） | `aggregate.py`、`count.py`、`harness.py`、`load.py`、`run_eval.py`、`score.py` | 見 `SHA256SUMS` |
| `run_live.log`、`qa_8810.log`、`gateway.log` | 執行紀錄 | 見 `SHA256SUMS` |

可否重建：規則組應可用 `scripts/` 在 `main` `b98fac2a` 上重跑（是否逐位元組相同未驗證，UNKNOWN）；LLM 組需要再付費呼叫 OpenAI，模型回答不保證逐字相同，**不能逐位元組重建**。
