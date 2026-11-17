# 即時模式工作交接（2026-11-16）

給接手即時模式（D210）的新對話。這份文件整理到 2026-11-16 為止做了什麼、使用者決定了什麼、還有哪些問題、下一步從哪裡開始。

- Model / effort：Fable 5.2；effort 沒有記錄（這個 session 看不到自己的 effort 設定）。前段（遊戲化設計 v1 的盤點和第一張 mockup）是 Opus 5.5 做的。
- 這是工程 demo，不是辨識、身分或實體安全的正式驗收。身分一律是未確認。

## 1. 現在的狀態（一段話）

即時模式有一個可以跑的原型：操作端用 WASD 控制人物，後台只看 8 個虛擬攝影機的像素，偵測、追蹤、切鏡。人物和場景已經換成 N6 的素材。影像裁決（出現兩個以上候選人時把鏡頭畫面丟給 OpenAI 的模型判斷）已經接進後台，預設關閉。模型看圖的判斷是準的，但**接上去之後還沒有讓追蹤變好**；目前最有效的改動是把演算法的關聯範圍從 3 m 放寬到 4 m。遊戲化的操作和畫面（越肩鏡頭、HUD、小地圖、B 畫面）只有設計稿，還沒有實作。兩個 PR 都是 Draft，沒有合併。

## 2. 位置和版本

| 項目 | 位置 | 版本 |
| --- | --- | --- |
| 程式、量測、報告 | PR [#544](https://github.com/Polalalabear/amidst/pull/544)，分支 `claude/feat-live-mode`，base `main` | `832c8f69`（再加上這份交接文件的 commit） |
| 設計稿（LLM 決策） | PR [#547](https://github.com/Polalalabear/amidst/pull/547)，分支 `claude/feat-live-llm-decision`，base `main` | 以分支最新的 commit 為準 |
| main | | `1fe6e716`（2026-11-16 查的） |
| WP5（離線模型比較，另一條線） | PR #546，分支 `claude/feat-wp5` | `297e03e2`，不是這條線的工作 |
| 8785 demo 的鎖定資料夾 | `~/amidst` | `b24d6a26`，工作樹乾淨。**不要在這裡改檔** |
| 決策紀錄 | issue [#93](https://github.com/Polalalabear/amidst/issues/93) | 這條線的決定貼在三則留言，還沒有 D 編號（§5） |

`claude/feat-live-mode` 上不只有這個 session 的 commit：N6 整合（`971b9763`）是另一個 session 做的。推送前先 `git fetch` 看有沒有新的 commit，有的話用 merge，不要 rebase 或 force push。

## 3. 先讀這些（照順序）

1. 這份文件。
2. `AGENTS.md`、`CLAUDE.md`、`docs/DEVELOPMENT_RULES.md`（Ground Truth 隔離、原始資產、PR 的規則）。
3. `docs/design/LIVE_MODE_LLM_DECISION_V1.md`（在 #547 的分支）：先讀 §0A–§0E。§0C 是問題和決定的紀錄。§1 之後是較早寫的內容，和 §0A–§0E 有出入時以前面為準。
4. `docs/evaluation/LIVE_MODE_TRACKER_20261116.md`：最新的量測，演算法改進和重播測試。
5. `docs/evaluation/LIVE_MODE_ADVISOR_20261116.md`：影像裁決接上後的兩輪實跑。**先讀 §0**，它更正了後面第一輪的結論。
6. `docs/evaluation/LIVE_MODE_ADJUDICATION_20261116.md`：單題測試，OpenAI 三個模型和 Colab 的本機視覺模型。
7. `docs/evaluation/LIVE_MODE_T1_20261115.md`：只用演算法時的基準。
8. `docs/evaluation/LIVE_MODE_SPIKE_20261115.md`：spike 的延遲和偵測率，§10 是 N6 整合後的量測。
9. `docs/design/LIVE_MODE_GAME_DESIGN_V2.md` 和 `LIVE_MODE_GAME_DESIGN_V1.md`：遊戲化的操作和畫面設計。v2 開頭有一段更新說明：B 畫面要保留。
10. `docs/design/AGENT_DECISION_V1.md`（在 main）：專案原有的 LLM 決策設計。即時模式的裁決沿用它的 `decision_source` 和退回規則，但輸入改成影像。

## 4. 做了什麼

依時間排列。每一項的細節在括號裡的文件。

| 項目 | 結果 | 文件 |
| --- | --- | --- |
| 遊戲化設計 v1、v2 | 越肩鏡頭、按鍵、HUD 四項（失聯計時、目前延遲、判斷來源、FPS）、小地圖方案 A、寫實化評估、後台紀錄格式。mockup 是 three.js 實際載入 N6 素材的渲染。**都還沒實作** | `LIVE_MODE_GAME_DESIGN_V1.md`、`V2.md` |
| T1：只用演算法的基準 | 目標看得到的時間裡 24–61% 沒跟對。推論頻率影響最大 | `LIVE_MODE_T1_20261115.md` |
| 盤點現有的 LLM 設計和 WP5 測試 | LLM 決策設計已經存在。WP5 回答的是離線的問題，列了 8 個缺口 | 設計稿 §1、§2 |
| 單題的影像裁決測試 | 36 題。OpenAI 看圖：sol6.1 和 astra6 33 題對，terra6.1 29 題。只看文字特徵 21–25 題。Colab L4 的 Qwen 視覺模型 20–21 題。llama3.2-vision 載入失敗 | `LIVE_MODE_ADJUDICATION_20261116.md` |
| Colab 測試包 | 使用者已經在 L4 上跑完 | `docs/operations/ADJUDICATION_COLAB_PACK_20261116.md` |
| 影像裁決接進後台 | `advisor.py`、`people.py`，預設關閉。單元測試通過 | `LIVE_MODE_ADVISOR_20261116.md` |
| 兩輪用 sol6.1 的實跑 | 模型在兩個候選人的題目上 38 題全對。只有一個候選人時容易選錯（已改成不問）。**接上後追蹤沒有變好**；第一輪「覆核有幫助」的結論已經更正 | 同上，§0 |
| 重播測試工具 | 把錄下來的偵測結果重新餵給演算法，不花錢，和實際紀錄逐輪相同 | `LIVE_MODE_TRACKER_20261116.md` §2 |
| 演算法改進 | 關聯範圍 3 m → 4 m：重播跟對 0.51 → 0.63，實跑 0.47 → 0.65。後台預設改成 4 m | 同上 |

## 5. 使用者的決定

| 日期 | 決定 |
| --- | --- |
| 2026-11-15 | 即時模式要像設計遊戲一樣呈現：越肩第三人稱、小地圖、腳步動畫、系統反應要快 |
| 2026-11-15 | HUD 只留 4 項：失聯計時、目前延遲、判斷來源（LLM 或演算法）、FPS。其他數字進後台紀錄 |
| 2026-11-15 | 小地圖用「自己永遠在正中央」的方案（設計稿 v2 的方案 A） |
| 2026-11-15 | 畫面要更寫實：用 N6 的烘焙場景和骨架人物 |
| 2026-11-15 | 目標：A 畫面 WASD 即時移動；B 畫面是單一跟隨視角，由 LLM 判斷並切鏡。即時模式只做追蹤，不做查找 |
| 2026-11-15 | 本機的 LLM 延遲可以接受。對評審的說法：目前硬體有限，之後上雲；Colab 上有固定硬體下的分析 |
| 2026-11-15 | 即時模式以「本機 demo 加 OpenAI」為準。之後可以上雲，要能在其他設備測不同模型 |
| 2026-11-16 | 只在需要裁決時把鏡頭畫面丟給 LLM；三個 OpenAI 模型都測 |
| 2026-11-16 | 即時模式切鏡裁決的預設模型是 sol6.1（`gpt-6.1-sol`）。在即時模式的範圍內取代 D237 的 terra6.1；WP5 的預設不變 |
| 2026-11-16 | B 畫面的 demo 預設用「LLM 覆核」；「LLM 主導」做成可以切換的展示方式 |
| 2026-11-16 | 先改演算法（這一輪的工作） |

核准過的付費額度，都已經用完該用的部分，**不能沿用到之後的工作**：

| 用途 | 核准上限 | 實際花費 |
| --- | ---: | ---: |
| 單題影像裁決測試 | USD 4 | 0.88 |
| 第一輪實跑 | USD 1 | 0.12 |
| 第二輪實跑 | USD 0.5 | 0.07 |
| 合計 | | 1.07 |

花費是回應的 token 數乘上 D237 的價目算的，不是 OpenAI 帳單上的數字。

還沒有 D 編號的決定貼在 #93 的三則留言：[6909798873](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6909798873)、[6910613701](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6910613701)、[6911702981](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6911702981)（第三則更正第二則）。「只在裁決時丟圖」放寬了 `AGENT_DECISION_V1.md` §2.1「不送影像」，範圍只限即時模式的裁決。

這個 session 自己做的低層決定（不需要使用者核准的那種），接手後可以依量測結果改：

- 後台的關聯範圍預設 4 m。這是使用者 2026-11-17 的決定（D244），預設值不改。已知限制：只在 A4/B4 兩條劇本路線調過（68 段重播高度相關、20 次實跑）；場景有同色（紅）干擾者，範圍越大越容易接到旁邊的紅衣者（`tracker.py` 取最近者，沒有速度或外觀檢查）；換路線、換人數或由人操作時沒量過（§12）。
- 至少兩個候選人才發問。
- 採用答案的方式預設是「只修正一次」（`reseed`）。
- 交錯檢查的門檻 0.7 m。
- 裁決每題上限 5 秒。

## 6. 還沒解決的問題

依重要程度排列。

1. **4 m 範圍下，加上裁決反而讓 A4 路線變差，就算回答一定正確。** 重播：A4 路線鏡頭的跟對 0.41 → 0.32，回答越快越差。正確的答案不該讓結果變差，接法裡還有問題。這是建議的第一件事（§8）。
2. **影像裁決還沒有證明能讓追蹤變好。** 3 m 範圍下，一定答對的回答能把跟對從 0.51 提到 0.63；但只把範圍放寬到 4 m 就有同樣的效果，兩者疊在一起沒有更好。所以「LLM 判斷追蹤」目前的價值主要是展示（畫面上看得到它的判斷和理由），不是準確度。
3. **A4 路線的偵測。** 目標在室外鏡頭有十幾輪實際看得到卻沒被偵測到。N6 人物在烘焙場景的偵測率是 69.1%，CAM_ENTRY 只有 19%。協調者那一線有一個「真人模型對照實驗」等使用者決定（D236）。
4. **推論頻率。** 8 個鏡頭全推論時每秒不到 1 輪。「只推論作用中鏡頭和鄰居」的排程還沒做（設計稿 §0A.5 第 1 項）。重播測試量不到它的效果，要實跑。
5. **只有兩條劇本路線。** 所有參數都是在 A4 和 B4 上調的，有「剛好適合這兩條路線」的風險。沒有用人實際操作的資料量過。
6. **追蹤編號仍然會對調**：每 100 次觀測約 1.3 次，目標平均被切成 4 段編號。
7. **只有一個候選人的時候不發問**，所以「目標獨自重新出現、但演算法接不上」的情況，裁決幫不上忙。模型對單一候選人的判斷不可靠（18 題對 8 題）。
8. **遊戲化的部分都還沒實作**：越肩鏡頭、角色控制和動畫混合、HUD、小地圖、B 畫面跟隨視角、後台紀錄。設計在 `LIVE_MODE_GAME_DESIGN_V1.md` §8 和 `V2.md` §8。現在操作端的鏡頭是高處俯視。
9. **（已修）後台從不該用於推論的幾何檔讀攝影機參數。** 原本 `server.py` 的投影器讀 `R004_SCENE_GEOMETRY_2D_V1.json`（`must_not_enter: RUNTIME_INFERENCE`）。現在改讀 `local/data/r004-build-v2-20261021/safe_static/cameras.json`（`controlled-scene.cameras.v1`，`--cameras` 可指定；`replay_advisor.py` 同）；8 台攝影機的 `camera_to_world`、`fx/fy/cx/cy`、解析度與舊檔逐項相同，重播 gate4_off 數字前後一致（ALL 0.64/0.21/0.14 n38）。操作端畫面仍用 `/data/geometry.json` 顯示，不進推論。
10. **這些程式還沒有經過正式審查。** `tracker.py`、`people.py`、`advisor.py` 改了追蹤的行為，照 `CLAUDE.md` 屬於複雜程式碼。#547 有一份 Opus 審查（NEEDS_CHANGES），已經回覆並修改，沒有複審。
11. **Colab 的本機視覺模型**：Qwen 兩個模型偏向回答 1 號；`llama3.2-vision` 在 Ollama 0.40.16 上載入失敗，下次換成 `gemma3:12b-it-q4_K_M`。OpenAI 是兩張圖分開送，Colab 是合成一張，兩邊不能完全對等比較。

## 7. 這個 session 犯過的錯（接手時留意）

- **只看彙總表就下結論。** 把 terra 的 2.7 秒當成回答時間，那些其實是格式不合法的回應。之後要看逐筆紀錄。
- **每組只跑 3 次就說有幫助。** 第一輪說「覆核在 B4 把跟對從 0.54 提高到 0.81」，那是湊巧。只用演算法時同一設定的 3 次可以是 0.36、0.90、0.36。之後比較兩種設定，先用重播在同一批偵測結果上比，再用實跑確認。
- **加了保護卻沒量它擋掉多少。**「兩人靠近過就不採用」設成 1.2 m，走廊才 2.4 m 寬，結果擋掉幾乎所有答案。
- **`git diff --cached --check` 後面用分號接 commit**，檢查沒過還是提交了一次（多了一個空行，已修）。檢查和提交之間要用 `&&`。
- 機器負載沒有控制。其他 session 在跑的時候 load1 到過 24，實跑的數字會被影響。

## 8. 建議的下一步

**第一件事：查清楚「4 m 範圍下加上正確的裁決反而變差」。** 不花錢，全部用重播。

1. 在 #544 的分支建 scratchpad clone（§9）。
2. 重跑重播確認現象：
   ```bash
   PYTHONPATH=src:<runtime-deps> python scripts/live_mode/replay_bench.py --work <暫存資料夾> --src sol2=local/evidence/live-mode-advisor-20261116/sol2 --src gate=local/evidence/live-mode-tracker-20261116/gate --config "gate4_off=--mode off --gate-m 4" --config "gate4_review=--mode review --gate-m 4"
   ```
3. 挑一段 A4 路線鏡頭、差距最大的紀錄，逐輪印出兩種設定的狀態，找出第一個「關閉時跟對、覆核時沒跟對」的時刻，看那一輪發生了什麼。`LIVE_MODE_ADVISOR_20261116.md` §0.2 的編號對調就是這樣找到的。
4. 可能的方向在 `LIVE_MODE_TRACKER_20261116.md` §6 第 1 點。
5. 修好之後的驗收：重播裡「4 m 加覆核」在每一組都不比「4 m 關閉」差。

之後的工作，順序由使用者決定：

- 推論排程（只推論作用中鏡頭和鄰居）。要實跑才量得到。
- B 畫面的跟隨視角和 HUD。現在只有後台，畫面上看不到裁決的狀態和理由。
- 遊戲化的操作（越肩鏡頭、動畫混合）。
- 請協調者安排正式審查。

要花錢的事（用真的模型實跑）每次都要使用者在對話裡給一個金額。

## 9. 工作方式

這些是這個專案的規則，細節在 `CLAUDE.md` 和使用者的本機設定。

- **不要在 `~/amidst` 改檔、切分支或 commit。** 那是 8785 demo 的鎖定資料夾。寫檔在 scratchpad 做：
  ```bash
  git clone --shared --no-checkout ~/amidst <scratchpad>/clone
  ```
  然後把 origin 設成 `https://github.com/Polalalabear/amidst.git`，fetch 並 checkout 要的分支。用完刪除。
- 開工前跑 `df`。剩 5 GiB 就停下來回報。2026-11-16 查的時候剩 13 GiB。
- PR 的 base 是 `main`，只用 merge commit。合併由使用者執行。不刪分支。
- 不要碰 8785 和 8791 埠。量測用的後台開在 8796，用完關掉。
- Ground Truth 隔離：後台和模型拿不到操作者的座標、角色代號、劇本位置。用劇本位置的程式只能用於評估，放在 `measure/` 或 `scripts/`，不能被後台 import。
- 付費 API 一律經過 `ApiGuard`，用伺服器端的環境變數開啟，每次量測用獨立的帳本資料夾。
- 每個 PR 的說明用 `AGENTS.md` 的「實際產出」模板；LOCAL 的檔案要列相對路徑、大小、檔案數、SHA-256。
- 回覆和文件用繁體中文。
- 決定要同步到 #93。D 編號由協調者編。

### 啟動和量測的指令

`<runtime-deps>` 是 `local/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps`（裡面有 torch 和 Pillow）；Python 用 `~/amidst/.venv/bin/python`；`AMIDST_ARTIFACTS` 指向 `~/amidst/local`（N6 素材在裡面）。前端的 `node_modules`（three、puppeteer-core）要在 clone 的 `frontend/live-mode/` 裡 `npm install`；這個 session 是借用另一個 session 留下的資料夾，那個資料夾不保證還在。

後台（只用演算法）：

```bash
AMIDST_ARTIFACTS=<local 資料夾> PYTHONPATH=src:<runtime-deps> python -m amidst.live_mode.server --port 8796 --device mps --threads 4 --models <local 資料夾>/data/demo-owned-v1/models/rtdetr
```

主要參數：`--gate-m`（預設 4）、`--advisor off|review|lead`（預設 off）、`--advisor-model`（預設 sol6.1）、`--advisor-provider fake`（不連網、不花錢的假模型，用來測流程）、`--advisor-apply reseed|lock`、`--advisor-lost-min-candidates`。

用真的模型時，加上這些伺服器端的環境變數（金額照使用者核准的數字）：

```bash
AMIDST_API_ENABLED=1 AMIDST_API_MAX_USD_TOTAL=<核准金額> AMIDST_API_MAX_USD_PER_DAY=<核准金額> AMIDST_API_MAX_CALLS_PER_MIN=30 AMIDST_API_USAGE_DIR=<這次量測的帳本資料夾>
```

錄一次自動路線（在 `frontend/live-mode/`）：

```bash
LIVE_BASE=http://127.0.0.1:8796 OUT=<輸出資料夾> node measure/t1_record.mjs b4_off_r1 "auto=B4&run=B4-1-v2-4actor&cams=CAM_W1,CAM_W2,CAM_R101_IN&model=glb&fps=2&w=960&h=540" 41
```

A4 路線把查詢換成 `auto=A4&run=A4-1-v2-4actor&cams=CAM_EXT_CAR,CAM_EXT_CLEAR,CAM_ENTRY,CAM_W1`，秒數 49。算跟對、跟錯、失聯：

```bash
node measure/t1_analyze.mjs <輸出資料夾> ../../docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json
```

測試：

```bash
PYTHONPATH=src:<runtime-deps> python -m pytest tests/live_mode -q
```

```bash
cd frontend/live-mode && node --test test/*.test.mjs
```

2026-11-16 的結果：pytest 29 項通過；node 的測試 13 項通過（沒有 N6 素材時部分會跳過）。

## 10. 程式地圖

| 檔案 | 做什麼 |
| --- | --- |
| `frontend/live-mode/src/operator.mjs` | 操作端：WASD、渲染、擷取虛擬攝影機、送後台 |
| `frontend/live-mode/src/system.mjs`、`hud.mjs` | 系統端 B 畫面：單一跟隨視角＋HUD（§13）。`hud.mjs` 是不碰 DOM 的純函式，有 node 測試 |
| `frontend/live-mode/src/system_grid.mjs` | 舊的系統端除錯頁（8 個鏡頭、偵測框、地圖），`?role=system&view=grid` |
| `frontend/live-mode/src/protocol.mjs` | 可以離開操作端的欄位白名單。新增欄位要改這裡和它的測試 |
| `frontend/live-mode/src/n6.mjs` | 載入 N6 素材（另一個 session 寫的） |
| `src/amidst/live_mode/server.py` | 後台。偵測、顏色、追蹤、裁決 |
| `src/amidst/live_mode/tracker.py` | 演算法追蹤器：跟最近的紅色偵測，關聯範圍可調 |
| `src/amidst/live_mode/people.py` | 給每個紅衣人跨輪的追蹤編號 |
| `src/amidst/live_mode/advisor.py` | 影像裁決：組圖、呼叫 OpenAI、覆核和主導兩種方式、退回規則 |
| `frontend/live-mode/measure/t1_record.mjs`、`t1_analyze.mjs` | 錄一次執行；算跟對、跟錯、失聯（用劇本位置，只用於評估） |
| `frontend/live-mode/measure/adv_analyze.mjs` | 逐題分析裁決的對錯（只用於評估） |
| `frontend/live-mode/measure/adj_record.mjs`、`adj_build.mjs` | 錄裁決時刻的高解析度畫面；產生單題測試的題目 |
| `scripts/live_mode/adjudication_probe.py`、`adjudication_score.py` | 單題測試：呼叫 OpenAI；評分 |
| `scripts/live_mode/replay_advisor.py`、`replay_bench.py` | 重播測試（只用於評估） |
| `scripts/live_mode/build_adjudication_colab_pack.py`、`colab_pack/` | Colab 測試包 |
| `tests/live_mode/` | 後台的單元測試 |

## 11. LOCAL 的資料（不進 Git）

路徑相對於 `local/`。SHA-256 在各報告的「證據」一節，或資料夾裡的 `SHA256SUMS.txt`。

| 資料夾 | 內容 | 檔案數 | 大小 | 能不能重新產生 |
| --- | --- | ---: | ---: | --- |
| `evidence/live-mode-spike-20261115/` | spike 的延遲量測 | 5 | 48 KiB | 可以重跑，數字不會相同 |
| `evidence/live-mode-t1-20261115/` | T1 的 12 次紀錄 | 14 | 1.3 MiB | 同上 |
| `evidence/live-mode-adjudication-20261116/` | 單題測試：題目、標準答案、OpenAI 和 Colab 的回答 | 304 | 7.9 MiB | 題目可以重新產生；OpenAI 的回答要再花錢，Colab 要再跑一次 |
| `evidence/live-mode-advisor-20261116/` | 裁決接上後的兩輪實跑、護欄帳本、重播彙總 | 56 | 6.7 MiB | 實跑要再花錢；重播可以重跑 |
| `evidence/live-mode-tracker-20261116/` | 3 m 對 4 m 的 20 次實跑、最後的重播彙總 | 25 | 1.5 MiB | 實跑可以重跑，數字不會相同；重播可以完全重現 |
| `evidence/live-mode-design-v2-20261115/` | 設計稿 v2 的 mockup 圖 | 8 | 2.3 MiB | 可以 |
| `data/adjudication-colab-pack-20261116/` | Colab 測試包 | 45 | 3.4 MiB | 可以，zip 是決定性的 |
| `data/live-assets-20261115/` | N6 的人物和場景（Codex #539） | 39 | 71 MiB | 不能由這條線重建 |

`evidence/live-mode-adjudication-20261116/questions/answers_private.jsonl` 和 `evidence/live-mode-advisor-20261116/sol/adv_questions.json` 裡有每個候選人對應的劇本角色，只能用於評分。

## 12. 沒有驗證的事

- 4 m 的關聯範圍在這兩條路線以外是不是仍然比較好。
- 用真的模型、4 m 範圍、新的編號追蹤一起跑的結果。最後一次用真的模型實跑是在修正編號對調之前。
- 遊戲化設計裡的延遲預算、GPU 記憶體、寫實化對偵測率的影響。
- 交接時 #544 的 CI 還在跑最新的 commit；前一個 commit 的 CI 是通過的。
- `frontend/live-mode/` 的 `npm install` 這個 session 沒有自己跑過。

## 13. B 畫面（系統端）怎麼開、HUD 各欄位的意思（PR #551，2026-11-17）

B 畫面是單一跟隨視角：主區域只顯示後台目前判定的作用中鏡頭（`active_cam`），目標有橘框和「目標」字樣，其他紅衣人紅框、藍衣人藍框。

**怎麼開。** 後台照 §9 的指令啟動（例如開在 8797）。同一個瀏覽器開兩個分頁，兩頁要同一個來源（BroadcastChannel 只在同源的頁面之間傳）：

- 操作端：`http://127.0.0.1:8797/?auto=B4&run=B4-1-v2-4actor&cams=CAM_W1,CAM_W2,CAM_R101_IN&model=glb&fps=2&w=960&h=540`（不加 `auto` 就是 WASD 手動）
- B 畫面：`http://127.0.0.1:8797/?role=system`
- 舊的 8 鏡頭格狀版：`?role=system&view=grid`

只看桌面版面（建議 1600×900 以上）。B 畫面只認後台經 `protocol.mjs` 白名單送出的訊息和 `/config`；白名單只加了 `advisor.last.cleared` 一個鍵（後台輸出，回答「都不是」時為真，和 `applied` 同性質；原本漏掉，HUD 會把選 0 顯示成「未採用」），GT、操作端座標、`gt_visible`、演員代號進不來（`test/hud.test.mjs` 有測試釘住：B 畫面的原始碼不 import 操作端的程式、不出現這些字，後台回送這些鍵會被剝掉並被驗證器標出）。

**畫面上的東西。**

| 位置 | 內容 |
| --- | --- |
| 左上角 | 作用中鏡頭名稱 |
| 上方中央（橘色，2.5 秒） | 切鏡提示：`切鏡 W2 → W1（規則）`；括號是誰切的，`LLM` 表示這次切鏡是採用 LLM 答案時發生的。切鏡時畫面有 150 ms 淡入 |
| 畫面邊框和上方中央的黑底提示 | 失聯：邊框橘色（短暫失聯）或紅色（失聯 3 秒以上或後台狀態 `LOST`），提示寫失聯秒數和最後鎖定的鏡頭，**畫面仍是該鏡頭的即時影像**，不標目標框。尚未鎖定時顯示「尚未鎖定目標」。LLM 主導且等回答時顯示「LLM 判斷中 x.x 秒，畫面停在原鏡頭」 |
| 下方一條 | 狀態列：`LLM 判斷中 1.4 秒（2 位候選人）`、`LLM 選了第 1 號（由左至右）：理由`、`演算法暫代：原因`、或 `規則追蹤中（LLM 沒開）` |
| 右側 | 小地圖（後台的位置估計）和事件清單 |

**HUD 四格（畫面最上方，左到右）。**

| 欄位 | 內容 | 資料來源（都是後台輸出） |
| --- | --- | --- |
| 目前鏡頭・追蹤 | `W2・跟蹤中`／`W1・失聯 2.4 秒`／`LLM 判斷中 0.3 秒`／`尚未鎖定目標`。失聯秒數從「目標離開視野」那一輪的前一輪擷取時間算起，在兩則訊息之間每 100 ms 更新 | `tracking.state`、`active_cam`、`lost_ticks`、擷取時鐘 `t_capture_ms` |
| 決策來源 | `規則`／`LLM 覆核`／`LLM 主導`／`LLM 判斷中`／`演算法暫代`＋原因。原因：逾時（`PROVIDER_TIMEOUT`）、逾時或答案太晚（`TIME_BUDGET`）、回應不合法（`INVALID_RESPONSE`）、額度用完（`CALL_BUDGET_EXHAUSTED`）、沒開（`MODE_NOT_AUTHORIZED`）、服務無法使用（`PROVIDER_UNAVAILABLE`）。advisor off 時一律是「規則」 | `decision_source`、`fallback_reason`、`/config` 的 `advisor` |
| 最近一次裁決 | `2 人 → 第 1 號（由左至右）`、一行「理由」（上限 40 字）、延遲 ms、結果：`已採用`／`已採用（不跟隨任何人）`（回答都不是）／`太晚，已丟棄`／`未採用：原因`。尚無裁決時寫「尚無裁決」 | `tracking.advisor.last`；候選人數取自同一鏡頭前一則 `ADJUDICATE_ASK` 事件，沒看到那則事件（頁面中途才開）就顯示 `?` |
| 模式・模型 | `規則（advisor off）`／`LLM 覆核 · gpt-6.1-sol (sol6.1)`／`LLM 主導 · …`。用假模型時寫「假模型（測試，不連網）」 | `/config` 的 `advisor`、`advisor_model`、`advisor_provider`；`last.model` |

**取捨（保守版本）。**

- 覆核模式採用 LLM 答案後，後台只修正一次（`reseed`），下一輪 `decision_source` 就退回 `RULE_ONLY`。為了讓畫面看得到，HUD 在答案被採用後 8 秒內仍把決策來源標成「LLM 覆核」（只在 `applied` 為真時）。
- 「選了誰」只有「第 N 號」：後台沒有給候選人其他描述，編號是問題圖裡由左至右的黃色框，不一定是目前畫面裡的鏡頭。
- 候選人數沒有放進 `last`（避免動 `advisor.py`，另有寫手在改）；HUD 用事件配對。要改成後台直接給，是 `advisor.py` 的小改動，留待那條線合併後。
- 短暫失聯（少於 3 秒、後台狀態仍是 `TRACKING`）用橘色，不等後台的 `LOST`（15 輪）。

**截圖（LOCAL，不進 Git）。** `local/evidence/live-mode-bscreen-20261117/`，SHA-256 見該資料夾的 `SHA256SUMS.txt`。後台用 8797（advisor off）、8798（review，假模型延遲 1.5 秒）、8799（review，假模型延遲 2.5 秒、逾時 1 秒）、8800（lead，假模型延遲 2.5 秒）；假模型固定回答 1，不連網、不讀 API key、沒有任何付費呼叫。產生截圖的指令：`LIVE_BASE=http://127.0.0.1:<埠> OUT=<資料夾> node measure/bscreen_shots.mjs "<操作端 query>" <秒數> <條件> <前綴>`，條件是 `tracking,switch,lost,judging,applied,fallback`。

| 檔名 | 狀態 | SHA-256 |
| --- | --- | --- |
| `01_off_b4_tracking.png` | advisor off，跟蹤中 | c5a7a0168bf8866acd0c2dec37e48e001e1389dff37bf6fd1f4469de16b1dd24 |
| `01_off_b4_switch.png` | advisor off，切鏡提示 | d7a260548bfdf824e8955557dc5897c8c27c4346a6871c0703a59c2644ed37c6 |
| `02_off_a4_lost.png` | advisor off，失聯（A4 室外鏡頭偵測率低） | ef33393bd614ffbf3b1e31a5957aa2fc595a670ebd33ec46bfd4a6c6320de285 |
| `03_review_judging.png`、`03_review_applied.png` | 覆核：規則繼續、LLM 判斷中；採用 LLM 答案 | a49beb7207282bd4888b6f3a719e46306c6f3d3c7ea41c961613928dafd0cbcc<br>9ca275de47583f8e8dc52706cc3f1c2d0c1bb0f74c2e74a398930ff191ff568c |
| `04_fallback_fallback.png` | 覆核，LLM 逾時，演算法暫代 | 88cc1a6d5f886f7aed661dd0bbac04d4cd4437777dd6c65884bd1aef3d223a3d |
| `05_lead_judging.png`、`05_lead_applied.png` | 主導：畫面停住等回答；採用答案 | f143dbeb4e2674dbeca3c992479c0bc7399ea99a9b96b2c0ae467898814bf387<br>40a2fc10b663d8bb0bfa6654dc236b2aac576c1554060161f714ad8f6d66618e |
| `06_review_none_none.png` | 覆核，LLM 回答「都不是」（假模型固定回答 0；啟動器在 scratchpad，不進 repo）：結果顯示「已採用（不跟隨任何人）」 | 3fa8f645e450e02e51473634cfbdb2da1e87d12e60ea50bfc49e82fbb2835b3f |
