# LIVE 難題集「規則 vs LLM 覆核」比較工具與評分器 v1（#597 準備部分）

狀態：準備部分已完成（不付費、不依賴 Codex）；**實跑等 #588／#608 合併與使用者核准付費金額**。沒有呼叫任何付費 API。難題集定義見 `docs/evaluation/LIVE_HARDSET_V1.md`，預錄版同類分析見 `docs/evaluation/RECORDED_RULE_VS_LLM_D325_20261118.md`（#597 留言）。

## 1. LIVE B 的決策注入點（不用新介面）

main 已有：`src/amidst/live_mode/advisor.py` 的 `LiveDecider`＋`Advisor`（provider 可換），由 `POST /config {advisor, advisor_model}` 建立或拿掉（`server.py: set_llm_mode`，`llm_switch.py` 決定實際模式）。

| 項目 | 現況 |
| --- | --- |
| 預設 | `advisor=off`：沒有 decider，後端輸出等於只用規則 |
| 模式 | `review`（規則照常，答案在人物仍被追蹤時接手）；`lead` 本比較不用 |
| 模型 | `terra6.1`（`gpt-6.1-terra`）、`sol6.1`（`gpt-6.1-sol`） |
| provider | 伺服器旗標 `--advisor-provider openai｜fake`（fake 不連網、不花錢、永遠答 1）；付費只有伺服器端 ApiGuard 核准時有效 |
| 決策點 | `LiveDecider.step`：`SILENT_PICK`（跟著時畫面上 ≥ 2 個紅衣人在 `gate_m` 內）、`LOST_WITH_CANDIDATES`（失聯且 ≥ 2 個候選）；B log 的 `tracking.events` 有 `ADJUDICATE_ASK`（`kind`、`candidates`）和 `ADJUDICATED`（`choice`、`applied`、`cleared`、`source`、`latency_ms`） |

所以「注入 decider」就是比較前對 `/config` 設定模式；本 PR 沒改後端（#608 範圍）。請求只含兩張 JPEG 和候選數，沒有座標、演員代號或腳本位置（`advisor.py` 的 docstring；GT 不進推論）。

## 2. 比較 runner

`frontend/live-mode/measure/hardset_compare.mjs`（新檔，沒碰 `hardset_smoke.mjs`；純函式在 `hardset_compare_lib.mjs`）：

```bash
LIVE_BASE=http://127.0.0.1:<port> OUT=<dir> node measure/hardset_compare.mjs H5-1,H1-1 --modes rule,terra,sol --k 3
```

- 每個 case × mode × rep：`POST /config` 設模式 → `GET /config` 確認真的生效（不生效就中止，附後台原因）→ 無頭 Chrome 開 B（`?role=system`）與 A（`?script=<case>`）→ B 按紅衣「開始追蹤」→ 等路線跑完再多等 6 s（答案在途）→ 存 `<case>.<mode>.<rep>.{a-log,b-log,meta}.json` → 把後台設回 off。
- **付費閘**：真實 provider 的 LLM 模式需要環境變數 `HARDSET_PAID_APPROVED_USD`（只有使用者在對話裡核准金額後才設）；規則模式與 fake provider 不需要。伺服器端 ApiGuard 的上限照常生效。`HARDSET_LEDGER=<usage.jsonl>` 可選，用來記每次執行的花費。
- 用 `?script=` 的固定步長腳本，所以三種模式的演員位置是 `t_sim` 的函數；擷取 tick 仍由牆鐘觸發，所以評分以 `t_sim` 對齊（不是 tick 編號）。逐 tick 完全相同的重播要等 #608／#617。

## 3. 評分器

`scripts/live_hardset_compare.py`（只讀 A／B log，不碰後端）：

```bash
python scripts/live_hardset_compare.py --dir <dir> [--cases H5-1,...] --out <outdir>   # report.md、score.json、decisions.csv
```

- **與 D325 的分母差別（兩份數字不可直接並排）**：本工具跟對率＝ON_TARGET 秒 ÷ 目標 GT 可見秒，偵測漏掉的時間算失聯／錯人（端到端，與 `live_ab_score.py` 一致）；D325 是 ÷「偵測得到（score≥0.3）」的 tick，本工具的數字通常較低。同一案內三組共用同一份 GT 重播，所以規則 vs LLM 的比較是公平的。以「偵測得到」為分母的次要指標要等 B log 有偵測收據（#608），目前 UNKNOWN，不補值。
- **未採用的裁決**：`choice≥1` 但 `applied=False`（例如該時刻目標已移動而被拒）記「未採用」、對錯 `—`，因為當時的系統輸出是規則的；`applied=True` 的 LLM 答案以採用後同一 tick 的追蹤位置代表（候選名單不在 B log，#608 收據契約前是替代量）；`choice` 不是 ≥ 0 的整數記 `UNKNOWN`。報告逐案表列「採用／未採用／都不是／退回」件數。
- **「之後 10 s 跟對」**：規則、terra、sol 三欄都從問的時刻起算（LLM 的等待時間算在它的成本裡）；未採用列反映的是規則。
- **切鏡點與較好／較差**：切鏡點只由規則組第 1 次重播定義；規則從頭沒跟上的案例沒有切鏡點，LLM 的改善只會反映在跟對率。某個切鏡點算「變好」或「變差」時，規則與 LLM 兩邊都取 K 次的嚴格多數（多數「接對」＝好），平手＝不確定，不算改善也不算退步。報告同時列跟對率的 K 次範圍，讓讀者看出 0.05 門檻是否在雜訊內。
- 目標＝腳本玩家 T。逐 tick 類別沿用 `scripts/live_ab_score.py` 的 `classify()`（1.5 m 判定），**差別**：`NEEDS_CONFIRM` 算失聯（RELOCK §2.1；`live_ab_score` 目前記 UNKNOWN）。比率以秒加權。
- 看不到期間另列：宣告失聯（正確）／追蹤在別人身上（`wrong_unseen_s`，H5 重點）／UNMATCHED。
- 跟對率、失聯秒、錯人秒、身分交換（連續 ≥ 2 tick 的錯人區段）、重新找回秒數（從目標重新可見起算，未找回另計件數）。
- 切鏡點：由**規則組**的 GT 定義（系統跟對時目標離開 active_cam，到目標再出現的 `t_N`），三組共用；`W = 2／5／10 s` 逐點判 接對／接錯／沒接上＋延遲（指引 §3.4）。
- 裁決點表：每個 LLM 裁決點一列（terra、sol 同一時刻合併），欄位：tick、t、失聯秒數、名單人數、目標可見（GT）、規則／terra／sol 的答案（對應成 T／A／B／C／都不是／失聯／退回規則）、正確答案、對錯、之後 10 s 跟對（規則／terra／sol）；只在某一組出現的裁決點標註。
- 逐類型：較好／相同／較差，定義照指引 §4（跟對率差 ≥ 0.05，或至少一個切鏡點變成接對且沒有另一個變差）；定義寫在程式碼前面，先於結果。
- **重播一致性**：以 `t_sim` 內插比對各組演員位置，最大差距 > 0.05 m（`--replay-tol-m`）或 `session_id` 不一致 → 該案 `NOT_COMPARED`（REPLAY_MISMATCH），不比較。

**UNKNOWN（沒有補值）**：B log 沒有候選名單（`cand_id`、`est_xy`、規則選擇）——#596 Q6／#608 的收據契約；所以「目標在名單？」只能寫「目標可見（GT）」，「T 可見但不在名單」的情形無法分辨。裁決點表的規則欄是規則組同一 `t_sim` 的追蹤輸出，不是規則在該次問題的選擇。

## 4. 估價（ApiGuard dry-run，沒有 API 呼叫）

```bash
python scripts/live_hardset_dryrun.py --cases nine --k 3        # H1×3、H4×3、H5×3；不帶 --cases = 全部 15 段
```

裁決點數上限＝段長 ÷ 3.5 s（等答案的時間）；實際會更少，規則組重播後用 `--rule-counts` 換成真實數。每次呼叫：最壞＝守衛計價 1100 輸入＋400 輸出 token；典型＝實測 807 輸入＋120 輸出（對應 D297 每次約 USD 0.0028）。單價用 `configs/agent_eval/wp5_price_table_v1.json`（D237）。

| 範圍 | 呼叫數（每模型，K=3） | terra 最壞／典型 | sol 最壞／典型 | 合計最壞／典型 |
| --- | ---: | ---: | ---: | ---: |
| 9 段（H1、H4、H5） | 312 | USD 0.967／0.439 | USD 1.934／0.878 | **USD 2.90／1.32** |
| 15 段（H1–H5 全部） | 513 | USD 1.590／0.722 | USD 3.181／1.444 | **USD 4.77／2.17** |

- 都低於 D306 的告知線 USD 10。**但**伺服器 ApiGuard 的預設日上限是 200 次／USD 5：每個模型 312（9 段）或 513（15 段）次會碰到 `DAILY_CALL_CAP`，實跑前要由使用者核准並設定較高的日呼叫上限，或分天、分批跑（這是 dry-run 的 `would_exceed` 輸出）。
- 付費實跑需要使用者在對話裡核准金額；核准只用於 #597（D242）。

## 5. 驗證與沒驗證

- 驗證：`tests/evaluation/test_live_hardset_compare.py`（17 個，合成 A／B log：秒加權類別、切鏡點、裁決點表含「都不是」、退回規則、未採用、規則 K 次不一致、K 平手、目標離開所有鏡頭的切鏡點、`NEEDS_CONFIRM`、找回秒、REPLAY_MISMATCH、SESSION_MISMATCH、較好／較差定義、CLI 輸出、dry-run 估價）；`frontend/live-mode/test/hardset_compare.test.mjs`（5 個：模式請求、生效檢查、付費閘 fail-closed、執行計畫、帳本差額）；評分器另用本機真實規則組 log（`hardset-597-20261118-ab2` 的 H1-3、H2-1、H5-3）跑過，能出表。
- **沒驗證**：runner 的瀏覽器流程沒有端到端跑（需要 LOCAL 模型的後台與長時間；也沒有 terra／sol 的真實 B log）；A／B 用同一個 browser context 的兩個 page（同 #617 的做法）能否在無頭下穩定收到畫面，要實跑時確認。
