# Agent vs 規則：研究假設與驗證計畫 v2（精簡版，2026-11-20）

- Issue [#641](https://github.com/Polalalabear/amidst/issues/641)；報告素材 [#479](https://github.com/Polalalabear/amidst/issues/479)；相關 [#597](https://github.com/Polalalabear/amidst/issues/597)、[#639](https://github.com/Polalalabear/amidst/issues/639)、[#637](https://github.com/Polalalabear/amidst/pull/637)。
- Model / effort：Claude Opus 5.5 / high。計畫文件；沒有新量測、沒有付費。
- v2 依使用者補充改寫：「先根據假設再去實作，不要過度拘泥在工程細節」，並加 §4「現況不合理處與修正」。v1（commit `2bae1dbc`）的完整版本留在 git 歷史。
- 身分永遠**未確認**；可行走連通是圖上的宣告，實體可通行是 **UNKNOWN**。GT 只在評分端。

## 1. 要證明的事

> **能看圖、又知道空間資訊（鏡頭關聯、可行走連通）的 Agent，在複雜情況下的切換決策和辨識，比規則演算法和 RT-DETR 好。**

複雜情況＝相似候選、遮擋或偵測失敗、長時間失聯、目標不在規則的候選名單、重疊鏡頭交接。核心是 H1、H2、H5；H3、H4、H6 是支撐條件。

### H5 辨識：Agent 看圖判斷「這格有沒有目標、是哪個框」比 RT-DETR＋規則準

- **要證明**：在遮擋、距離遠、偵測分數低的格子，Agent 看圖的 recall 比 RT-DETR＋HSV 規則高，precision 沒有明顯下降。
- **最小實驗（E1）**：
  - 場景：r004 A4-1、B4-1（GT、偵測索引、RGB 畫面都已存在）。先數格子夠不夠，困難格不夠時再加入 LIVE 錄製或 Line 2 場景。
  - 樣本：抽 600–1000 格，間隔 ≥ 1 s。按三個變數分層：遮擋（0／< 50%／≥ 50%）、距離（三段）、RT-DETR 對目標的最高分數（沒有框／< 0.3／≥ 0.3）。
  - 比較（同一批格子，成對）：
    - **規則**：Q4 判法，即分數門檻＋HSV（`q4_evidence.py`）。
    - **Agent 看圖**：輸入參考裁切圖＋當格畫面，可以選框、答「不在」，或答「在但沒有框」並給位置。
    - **Agent 只給文字特徵**：這組同時是 H2 的消融。
  - 指標：逐格 precision、recall、選框正確率、「在但沒框」的發現率，全部分層報。
- **成立**：三個困難層中至少兩層 recall 的成對差 95% 區間 > 0，且 precision 下降 ≤ 0.05。
- **推翻**：三個困難層的 recall 差區間都包含 0；或 recall 上升但 precision 降 > 0.05。某一層在場格 < 50 時，該層判「無法判斷」。

### H2 機制：優勢來自看圖分辨「被遮擋／偵測漏掉」和「真的離開」

- **要證明**：在目標還在畫面裡、但被遮擋或沒有被偵測到的時刻，看圖的 Agent 判斷「仍在此鏡頭」比不看圖的組準；在目標真的離開的時刻，也能正確判「已離開」。
- **最小實驗**：E1 的格子（看圖 vs 只給文字，在「遮擋／沒框」層的正確率），加上 E2 的四組消融（圖 有／無 × 空間資訊 有／無）在決策點上的結果。
- **成立**：看圖 vs 不看圖在遮擋或沒框時刻的成對差 95% 區間 > 0，而且「已離開」的正確率沒有變差。
- **推翻**：差的區間包含 0。另一種情況：H1 成立，但「不看圖＋有空間」接近完整組，表示優勢來自空間推理而不是看圖，H2 改寫。

### H1 切換決策：複雜情況下 Agent 切換比規則好

- **要證明**：在複雜決策點上，Agent 錯人秒較少、跟對率不低於規則。
  - 錯人秒是主要指標：自信地指錯人比誠實失聯更有害。
  - 跟對率一起看：防止 Agent 靠一直說「不在」來壓低錯人秒。
- **最小實驗（E2）**：
  - Agent 的輸入和權限：
    - 看圖：參考裁切、候選鏡頭當下畫面、低分框的裁切。
    - 空間資訊：鏡頭邊、重疊、出口區，以及每條邊的核定等級（附上，不擋）。
    - 可以選任何偵測到的人，包括顏色不符或分數低的人。
    - 也可以答「目標仍在此鏡頭（被遮擋）」或「不在畫面，下一台可能是 X」。
  - 比較組：規則、Agent 完整組、不看圖、沒有空間資訊，四組吃同一份輸入。
  - E2a 試跑：r004 A4-1／B4-1 的失聯段與決策點，只驗證可行，不下結論。
  - E2b 正式：LIVE 難題集 HS1（長失聯）、HS2（相似人物交錯）、HS4（跳過相鄰鏡頭）、HS5（目標不在候選）。用同一個 `?script=` 劇本、以 `t_sim` 對齊成對比較；之後再加 Line 2 預錄場景。
  - 延遲分兩種報：離線（等呼叫時模擬時間暫停）和即時（等待時間算進延遲）。
  - 每個 Agent 組跑 K = 3。
- **成立**：同時滿足三點：
  - 錯人秒成對差的 95% 區間 < 0；
  - 跟對率沒有下降超過 0.05；
  - 決策點正確率的 McNemar 檢定顯示 Agent 較好。
- **推翻**：上面任一條朝反方向，或區間包含 0。離線和即時分開判。
- **樣本**：複雜決策點 ≥ 40（建議 ≥ 60），且 ≥ 8 段。不足時只寫逐案表，不寫「支持」或「推翻」。

### 支撐條件

- **H3 閘門改成資訊**：Agent 模式下，規則閘門的結果附給 Agent，不硬擋。GT 隔離、付費護欄、身分未確認、格式驗證仍硬擋。在 E2 加一組「閘門照擋」比較即可，不另做實驗。
- **H4 主動搜尋**：Agent 依空間資訊預測下一台鏡頭並主動去看，看接回延遲。併在 E2，記錄前 1／前 3 預測命中率和接回延遲。
- **H6 全模式可切換**：前提，不是假設。現在沒有任何模式同時做到四件事：真的呼叫模型、看圖、有空間資訊、閘門只當資訊。缺口見 §4。

## 2. 現有證據

| 假設 | 證據 | 不能證明什麼 | 強度 |
| --- | --- | --- | --- |
| H5 | LIVE 看圖選人 0.81–0.92；兩候選題 38 題全對（`LIVE_MODE_ADJUDICATION_20261116.md`、`LIVE_MODE_ADVISOR_20261116.md` §0.4） | 只是從規則給的 2–3 個紅衣框中選，不是逐格判斷「有沒有」；沒有「沒有框」的格子；沒有分層 | 部分 |
| H2 | 看圖 0.81–0.92 vs 只給文字 0.58–0.69；A4 有 15 次目標不在候選，其中 11 次模型正確答「都不是」 | 比的是「看圖 vs 文字選人」，不是「遮擋 vs 離開」；沒有空間資訊組 | 弱 |
| H1 | D325：A4-1／B4-1 規則和 LLM 相同（0.970／0.906）；LIVE 覆核時跟對率沒變好（重播時就算模型一定答對，B4 也只從 0.52 到 0.53） | 都是覆核架構：沒有送圖（D325），或只在規則允許時、從規則篩過的紅衣候選中選（LIVE）。D325 的場景沒有任何要在兩個不同的人之間選的決策點 | 無（主動架構） |
| H3／H4 | #629：134 筆轉移全被 `GRAPH_NOT_APPROVED` 擋掉；#637 的理論上限：失聯 A4-1 2.6→0.8 s、B4-1 4.2→0.2 s | 沒有「閘門當資訊」的對照組；上限沒有實測 | 無 |

**D325 與 A4-1／B4-1 不能檢驗 H1–H5**：場景簡單、沒有送圖、8785 的 Agent 被閘門擋下。

## 3. 實驗順序

1. **E1（立刻可做）**：H5＋H2 逐格評估，用 r004 現有的 GT、索引和畫面。估計 USD 3–6，先跑 ApiGuard dry-run。不依賴 Codex。
2. **E2a（修完 §4 C1–C3 後）**：主動 Agent 在 r004 上試跑，確認請求、回應和評分都能跑通。估計 USD 2–4。
3. **E2b（#608／#617 合併、LIVE 端完成 §4 C7 後）**：在 LIVE 難題集上正式驗 H1／H2／H3／H4。估計 USD 6–12。
4. **E3（Codex 完成 Line 2 場景後）**：補足決策點數量。需求見 §5 W4。

總計約 USD 15–25，每一步先跑 dry-run。依 D242，每次核准只用於該實驗。

## 4. 現況不合理處與修正

以下每一項都用 grep 和讀碼確認過（基準 `main` `bc28f33b`），依影響假設驗證的程度排序。

### 4.0 需要使用者決策（擋住 H1／H2／H5 的規則本身）

| # | 位置 | 為什麼不合理 | 怎麼改 | 改的人 |
| --- | --- | --- | --- | --- |
| R1 | `docs/DEVELOPMENT_RULES.md` L63（D64 條）：「Agent 不排序、不增刪候選，也不做 geometry、pathfinding…Agent 依序向候選取偵測與顏色證據…**第一版只用 RT-DETR＋HSV，不用看圖**」 | 規則**明文禁止**本計畫要驗證的 Agent：不准看圖（H1／H2／H5），不准加入規則沒給的候選（H3），不准用空間做推理（H4）。現在所有 Agent 程式都照這條寫成覆核者，這是根本原因 | 新 D 號：**Agent 模式（預設關、研究與 demo 皆可）**可以看渲染畫面、可以從所有偵測（含低分、顏色不符）中選、可以回答「仍在／不在／下一台看 X」、可以讀圖的邊與核定等級。決定性規則仍是預設與兜底；GT 隔離、ApiGuard、身分未確認不變 | 使用者決定；Claude 起草條文 |
| R2 | `docs/specs/Q1Q5_PRODUCT_SPEC.md` §4.3 L143（「Agent 只在合法 top-k 內依序取偵測與顏色證據」）、§3 表 L82（「Agent 不排序、不增刪」）、§1.2 L42 的 D128（「不送原始影格」） | 同 R1，規格把 Agent 定義成覆核者。D128 不送原始影格，和 LIVE 已經送圖（使用者核准過）不一致 | R1 決定後，同步改這三處，並把 D128 改成：送渲染合成畫面可以，真實人物影像仍然不送 | Claude |

### 4.1 Claude 可以立刻改（`src/amidst/q1q5/`，沒有 Codex 的 PR 在動；需 R1 先決定）

| # | 位置 | 為什麼不合理 | 怎麼改 |
| --- | --- | --- | --- |
| C1 | `src/amidst/q1q5/agent_decision.py` L93–101：請求是封閉 schema，只有 `TRACK_KEYS`、`CANDIDATE_KEYS`、`TOPOLOGY_KEYS = {graph_status, edges}`；`agent_wiring.py` L38–45 只送軌跡摘要（顏色、分數統計） | **Agent 沒有圖**（H1／H2）；空間資訊只有邊清單，沒有重疊、出口區、可行走連通與各邊核定等級（H1／H4） | schema v3：加 `frames`（參考裁切＋候選鏡頭當下畫面＋候選裁切，JPEG 的 SHA-256 與內容）；`topology` 加 `overlaps`、`exit_regions`、每條邊的 `authority`（APPROVED／DRAFT／TOPOLOGICAL_ONLY／UNKNOWN）。`FORBIDDEN_KEYS` 不變 |
| C2 | `agent_decision.py` L337：`if not match or not match[0]['rule_eligible']: raise ILLEGAL_CANDIDATE`；`cross_camera_demo.py` L195–196 也只接受 `eligible` 中的選擇 | Agent 看得到顏色不符的候選，卻**不准選**。顏色篩選仍是硬閘門（H3） | Agent 模式下可選任何 `considered` 候選；選了 `rule_eligible=false` 的人時，在稽核中記 `RULE_OVERRIDE:<原因>` |
| C3 | `cross_camera_demo.py` L186：`if decider is not None and current is not None and eligible:` | 只有規則**至少有一個合格候選**時才問 Agent。全部顏色不符、目標失聯、零候選時 Agent 完全不被問，而這正是複雜情況 c3／c4（H1／H4） | 有 `considered` 候選、或失聯超過 N 個樣本時也呼叫 decider；新增回答 `STILL_HERE_OCCLUDED`、`NOT_VISIBLE`（附 `next_camera_hint`），由規則決定怎麼顯示 |
| C4 | `cross_camera_demo.py` L170–172：`gap < 0` → `CURRENT_CAMERA_STILL_OBSERVED`，不進 `considered` | 重疊鏡頭交接（c5）時，另一台鏡頭的候選 Agent 根本看不到（H1） | 放進 `considered`，標 `overlap=true` |
| C5 | `cross_camera_demo.py` L32–33（`min_score = 0.4` 連結門檻、`local_track_min_score = 0.3`）、L126 | 低於 0.3／0.4 的框在 Agent 看到前就被刪了；遮擋或遠距離的目標分數通常偏低（H5／H3） | Agent 模式另送「低信心框」（索引 floor 到 0.3）的裁切；規則照舊用門檻 |
| C6 | `agent_decision.py` L49 `MAX_REASON_CODES = 4` | 格式問題讓約 12% 的「圖上沒有邊」決策退回規則（D325 §5）；這不是決策閘門 | 驗證前截斷到 4 個，或在提示裡寫明上限 |
| C8a | `src/amidst/q1q5/q4_evidence.py` L123、L131–134：`score < query_min_score` 直接跳過，`presence` 只由 HSV 判定（`MATCH_STRONG`／`WEAK`…）；`q1_search.py` 是 index-only | **RT-DETR 分數門檻加 HSV 是 Q4「有沒有目標」的最終答案**，沒有任何看圖確認（H5／H6） | 先做 E1 的離線評估器（不改 API）；E1 成立後，把 Agent 看圖確認加成 Q4 的可選路徑（見 X3） |

### 4.2 要等 Codex（同檔有 Codex 的 PR，或屬 Codex 範圍）

| # | 位置 | 為什麼不合理 | 怎麼改 | 改的人 | `waiting:codex` |
| --- | --- | --- | --- | --- | --- |
| C7 | `src/amidst/live_mode/advisor.py` L224（只收 `color == "red"` 的人）、L284（`SILENT_PICK` 要 ≥ 2 人在 `gate_m = 3.0` m 內）、L286–287＋L196（`LOST_WITH_CANDIDATES` 要 ≥ `lost_min_candidates = 2`）、L91–95（請求只有兩張圖和 k） | LIVE 只有在規則已把目標放進候選、而且候選 ≥ 2 時才問 Agent；A4 21 次中 15 次目標不在候選。單一候選、零候選、非紅衣都不問。請求也沒有空間資訊（H1／H3／H4） | 候選改成所有人（顏色只當特徵）；單一候選、零候選、失聯時也可以問，回答可以是「不在，看鏡頭 X」；請求附鄰接鏡頭與多鏡頭畫面 | Claude | 是（#608 也改 `advisor.py`） |
| X1 | `src/amidst/q1q5/candidates.py` L63–71：`scope_unapproved` → 所有轉移記 `GRAPH_NOT_APPROVED` 並排除 | 8785 Q5 controller 的 Agent 候選是 0，從來沒有呼叫 API（H3／H6） | Agent 模式下把未核定的轉移連同核定狀態一起交給 Agent；規則模式維持 fail-closed | Codex（Q5 controller） | 是 |
| X2 | #639：8785 Agent 開關改接 `associate()` | 方向對，但如果只改接、不先做 C1–C3，8785 的 Agent 仍然是不看圖的覆核者，結果會和 D325 一樣 | 順序改成 C1–C3 → #639 | Claude | 是（#623 動 `serve_demo_integration.py`） |
| X3 | Q1／Q2 查找、Q4 證據的 API（`q1_search.py`、`q4_evidence.py` 的 route） | Agent／規則在查找模式不能切換，只有 Q3 解析可以走 LLM（H6） | E1 成立後加入 Agent 看圖確認的可選路徑，回應附 `decision_source` | Codex（API 契約）；Claude 起草契約 | 是 |
| X4 | 資料：複雜預錄場景不存在；LIVE 難題集還沒正式錄製 | H1 沒有足夠的複雜決策點 | Line 2 場景（§5 W4）；#608／#617 合併後錄製難題集 | Codex | 是 |

**和假設無關、不用優先處理**：#633（LIVE 改 workbench-v2 風格）。

## 5. 工作拆解（依優先順序）

| # | 工作 | 驗證 | 負責 | 依賴 | 建議模型／effort |
| --- | --- | --- | --- | --- | --- |
| W1 | **E1 逐格評估器並實跑**：從 r004 抽格並分層；三組比較：Q4 規則、Agent 看圖、Agent 只給文字 | H5、H2 | Claude | 無（付費金額需使用者核准；送渲染畫面已在 LIVE 做過，但預錄送圖是否要等 R1，由協調者決定） | Sonnet / high |
| W2 | **主動 Agent 決策器**：完成 C1–C6（schema v3：送圖、空間資訊、閘門當資訊、可以不選人），在 r004 跑 E2a 試跑；併入看圖 Agent 實驗 session 的成果 | H1、H2、H3、H4 | Claude | R1 | Sonnet / high |
| W3 | **LIVE 端主動 Agent**：做 C7，在難題集跑 E2b，含四組消融與「閘門照擋」組 | H1、H2、H3、H4 | Claude | #608／#617 合併 | Sonnet / high |
| W4 | **複雜場景**：Line 2 預錄 L2-S1–S6（相似人物交錯、遮擋、長失聯＋多出口、目標不在候選、重疊交接、離開路線圖），每類 ≥ 3 次；GT 只放 `gt_private/`；偵測用相同的 RT-DETR R18 | H1（樣本數） | Codex | 無 | — |
| W5 | **判讀**：每次實驗前提交指標與推翻條件，實驗後寫結論 | 全部 | Claude | W1–W3 | Opus / high |

## 6. 判讀規則

- 樣本不足（H1 < 40 個複雜決策點或 < 8 段；H5 某層 < 50 格）：只寫逐案數字，不寫「支持」「優於」。
- 區間跨 0：寫「沒有觀察到差異（區間 [x, y]）」，不寫「兩者相同」或「Agent 沒用」。
- 只在離線成立：寫「可以等待時 Agent 判斷較好；以目前 4–5 s 的延遲，即時模式沒有顯示優勢」。
- 覆核架構的結果（D325、#597 現行版、#639）一律標明「覆核架構」，不和主動架構混寫。
- **停損**：E1 在困難層推翻 H5 時，先回報，H2 的基礎就不成立，E2 降為次要；E2a 試跑後格式退回超過 20% 時，先修，不付費重跑。

## 附錄：來源

`RECORDED_RULE_VS_LLM_D325_20261118.md`、`LIVE_MODE_ADJUDICATION_20261116.md`、`LIVE_MODE_ADVISOR_20261116.md`、`AGENT_ZERO_CANDIDATES_629.md`、`LIVE_HARDSET_V1.md`、`LIVE_HARDSET_COMPARE_V1.md`、PR #637（head `6c318377`）；程式行號以 `main` `bc28f33b` 為準。
