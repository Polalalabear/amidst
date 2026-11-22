# Agent vs 規則：研究假設與驗證計畫 v2（精簡版，2026-11-20）

- Issue [#641](https://github.com/Polalalabear/amidst/issues/641)；報告素材 [#479](https://github.com/Polalalabear/amidst/issues/479)；相關 [#597](https://github.com/Polalalabear/amidst/issues/597)、[#639](https://github.com/Polalalabear/amidst/issues/639)、[#637](https://github.com/Polalalabear/amidst/pull/637)。
- Model / effort：Claude Opus 5.5 / high。計畫文件；沒有新量測、沒有付費。
- v2 依使用者補充改寫：「先根據假設再去實作，不要過度拘泥在工程細節」，並加 §4「現況不合理處與修正」。v1（commit `2bae1dbc`）的完整版本留在 git 歷史。
- 身分永遠**未確認**；可行走連通是圖上的宣告，實體可通行是 **UNKNOWN**。GT 只在評分端。
- **2026-11-20 更新（D342）**：新增 §0「目前證據狀態」（W1 #647、W2 #648 之後）。§2 是實驗前的證據，保留作對照。
- 2026-11-22：新增 §0.1 H1–H6 總表（導讀，不改判定）。
- 2026-11-22：新增 §0.2 LIVE 追其他目標（後續工作，#672）。

## 0. 目前證據狀態（2026-11-20，W1／W2 之後；D342）

措辭以 [`W1_FRAME_EVAL_20261120.md`](W1_FRAME_EVAL_20261120.md)、[`W2_ACTIVE_AGENT_20261120.md`](W2_ACTIVE_AGENT_20261120.md)、[`VISION_AGENT_RECORDED_20261120.md`](VISION_AGENT_RECORDED_20261120.md) 與 #647、#648 的 Opus 裁決為準。所有結果的共同條件：**渲染合成、預錄、只有 A4-1／B4-1 兩個事件、單一紅衣目標、RT-DETR R18、鏡頭圖仍是 DRAFT**；不能外推到真實影像或複雜場景。身分一律未確認。

| 假設 | 目前狀態 | 依據（數字） | 還缺什麼 |
| --- | --- | --- | --- |
| **H5 辨識** | **有條件成立**（限規則失效的層） | W1（#644，PR #647；terra K=3 **多數決**為主結果，422 格分層樣本）：整體 F1 規則 0.523 → 看圖 0.957，差 +0.433 [0.324, 0.566]；precision 差 −0.019 [−0.042, 0.009]（區間含 0）；recall 差 `partial_occluded` +0.738 [0.585, 0.854]、`far_small` +0.574 [0.369, 0.719]（這兩層不依賴規則失敗定義，單獨即滿足預先登記條件）。`lowscore_person` 無優勢（−0.018）；`easy_visible`（23）、`partial_edge`（36）不足 50 格，**無法判斷** | 複雜場景、真實影像、其他服裝；Q4 API 仍只有規則路徑（X3） |
| **H2 機制** | **有條件成立（部分）**：看圖是必要條件，但「不在」的判斷有代價 | W1：不給圖的 (c) 組整體 F1 只有 0.27，(b)−(c) F1 +0.685 [0.545, 0.827]；但 `neg_absent`「不在」答對率 (b) 比 (c) 低 0.111 [−0.200, −0.030]，未達預先登記條件（7 個誤報都在身體 12–50% 在畫面內的邊界格）。W2 E2a：不給圖的 B 組 offline 跟對率 A4-1 0.646、B4-1 0.547（規則 0.970／0.906），給圖的組沒有這個問題 | 「遮擋 vs 真的離開」在複雜場景的決策點（E2b） |
| **H1 切換決策** | **尚無數據** | W2 E2a 只驗證可行，不下結論。F1 統一評分（[`E3_SCORER_RECOMPUTE_20261122.md`](E3_SCORER_RECOMPUTE_20261122.md)）：B4-1 規則 0.889（IoU 準則 0.647）→ W2 A 離線 0.981（IoU 準則 0.824），錯人 0.2 秒、定位不準 6.5 秒；A4-1 規則 0.904 → 0.960；規則正確的 tick 沒有被改壞。舊尺（#648：0.906 → 0.916、IoU 0.761／錯人 6.3 秒）見 E3_SCORER_RECOMPUTE §4。兩個事件規則本來幾乎沒有錯人，沒有可勝出的決策點 | E2b：複雜決策點 ≥ 40（建議 ≥ 60）、≥ 8 段（W3 #646、W4 Line 2 場景） |
| **即時（realtime）** | **增益 0** | W2：所有 Agent 組在模擬即時下都等於規則；單次延遲 p50 約 4.3 s、p95 約 6.2 s，比失聯段（2.6／4.2 s）長。先導 #640 同（p50 約 3.2–4.0 s） | 更快的模型或非同步預取；依 §6，只能寫「可以等待時較好，即時沒有顯示優勢」 |
| **H3 閘門改資訊** | 這兩個事件上**沒有害處，也沒有可見好處** | W2：Agent 多次選 `rule_eligible=false` 的偵測（記 `RULE_OVERRIDE`），中心點準則下錯人 0 秒；「選中的框落在目標上的機率是否與規則相同」沒有計算 | 規則真的錯的場景（E2b 的「閘門照擋」組） |
| **H4 主動搜尋** | **只有描述性訊號，不支持 H4** | W2 兩階段挑鏡頭：B4-1 前 3 名命中 有場景 37／40 vs 無場景 9／40，但差異**全部來自第 3 順位**；前 1、前 2 名只有 8／40，低於隨機期望（10、19），等於繼續看最後一台；A4-1 無區分力；只看前 2 名的第二階段沒有改善失聯。tick 高度自相關，B4-1 只有 3 段失聯 | 更多失聯段；覆蓋多邊形不建模遮擋（CAM_WIDE 恆排第 2，未驗證） |
| **H6 全模式可切換** | 前提，**部分完成** | `src/amidst/q1q5/agent_service.py` 提供 `RULE`／`AGENT` 統一介面（RULE 不呼叫模型）；8785 開關改接是 #645 第二步（等 Codex #623）；LIVE 是 W3（#646；前置 #608、#617 已於 2026-11-22 合併）；Q1／Q2 查找與 Q4 的 Agent 路徑（X3）未做。G7 已修正：所有付費呼叫經 ApiGuard（4f665d55） | #645 第二步、#646、X3 |

**LIVE 前置（2026-11-22）**：#608 重新取得 R1 已合併（`cfbfe4e9`）：`RelockConfig` 門檻全部預設 `None`（預設關閉，未設定時走原固定 gate），`t_short_s`、`tau_app`、`margin_app` 量測依據不足，值為 `UNKNOWN`；#617 LIVE 錄製重播已合併（`1742ed06`）：輸入側確定性成立，完整 E3 corpus 為 0，輸出側（偵測器、Agent 回應、延遲）確定性未驗。E3 劇本前提見 #652。

**先導 #640（PR #647，n = 2 事件、K = 3 平均）只作描述性引用**：失聯秒 A4-1 規則 2.6 → 看圖 0.8 s、B4-1 4.2 → 1.2 s，錯接 0 次；不給圖零改善；不作推論統計。

**花費**（ApiGuard 帳本）：W1 `frame_eval` USD 6.414、先導 `vision_agent` USD 6.611、W2 `w2_agent` USD 8.904；帳本合計 USD 22.40（額度 USD 50，D339）。

## 0.1 H1–H6 核心問題與解法總表（2026-11-22）

判定門檻以 [`E3_PREREGISTRATION_20261122.md`](E3_PREREGISTRATION_20261122.md) §6 為準（#667，merge `744f9d7f`）；本表只是導讀。

| 假設 | 核心問題 | 解法（做了什麼／怎麼驗） | 目前狀態 |
|---|---|---|---|
| **H1** 切換決策 | 困難情況下，Agent 決定換鏡頭時，錯人秒是否比規則少？ | E3 困難劇本：A2 vs B1（離線），A3 vs B1（模擬即時）；指標錯人秒、跟對率，決策點 McNemar | 尚無數據：W2 兩事件規則幾乎沒錯，沒有可勝出的點；E3 執行中 |
| **H2** 機制 | 如果 Agent 較好，好處是否來自看圖（分辨被遮住／偵測漏掉 vs 真的離開）？ | 同一批決策點比 A1 vs B1、A2 vs B2；D 類決策點另查「已離開」正確率 | 部分成立：W1 不給圖 F1 只有 0.27，看圖是必要條件；但 Agent 判「不在」有誤報；複雜情境待 E3 |
| **H3** 閘門改成資訊 | 不讓規則硬擋、讓 Agent 自己選之後，會不會選錯人？ | D340：規則閘門只附資訊；GT 隔離、ApiGuard、身分未確認、格式驗證仍硬擋；Agent 推翻規則記 `RULE_OVERRIDE` | W2 看不出害處也看不出好處；E3 沒有「閘門照擋」組，目前只能描述性報告（`RULE_OVERRIDE` 次數與被選框的 GT 對錯，標探索性） |
| **H4** 空間資訊 | 給 Agent 鏡頭圖、可行走連通、FOV、門洞後，猜「下一台在哪出現」是否更準、接回更快？ | A2（有空間資訊）vs A1（沒有）的 top-1 命中與接回延遲；B2 vs B1 另報；空間資訊不含牆面裁切（D348） | 先前不支持：B4-1 top-1 8／40，低於隨機 10／40；E3 加入 #665 的 30 個重現點（D349）再驗 |
| **H5** 逐格辨識 | 「這格有沒有目標、是哪個框」，看圖 Agent 是否勝過 RT-DETR＋HSV？ | 同一批格子逐格比，5 個困難層（相似衣著、遮擋、遠小、沒有人物框、非人物框） | 有條件成立（規則失效的層）：遮擋 recall +0.738、遠小 +0.574，precision 沒變差；E3 再驗複雜場景 |
| **H6** 全模式可切換 | 每個模式都能在 Agent 和規則之間切換嗎？ | 前提，不做統計；統一介面 `agent_service.py`；8785 主畫面 #666；LIVE W3（#646）；Q1／Q2 查找與 Q4 是 X3 | 部分完成：8785 只限 D124 run，8CAM／B-05 未接，X3 未做（列後續工作） |

關係：核心是 H1、H2、H5；H3 是前提（規則不放寬，Agent 沒機會贏），H4 讓 Agent 知道去哪找，H6 讓結果能在 demo 實際切換。

## 0.2 後續：LIVE 追其他目標（2026-11-22，探索性，非預先登記）

Issue [#672](https://github.com/Polalalabear/amidst/issues/672)。狀態：blocked，E3 凍結後才開始。

**現況（以 main 為準，2026-11-22 核對）**
- main 已有 LIVE 選目標功能（commit `df006515`「Add session-scoped LIVE target selection endpoints」）：`server.py` 的 `/track/start` 收 `color`（red／blue 色票）、`sentence`（句子解析）、`reselect`；`/track/candidates` 列候選；使用者可點選候選（`USER_PICK`）或單一候選自動種子（`AUTO_SINGLE`）。`tracker.py:65` 的 `LiveTracker` 有 `target_color` 參數（只接受 `COLORS`，即 red／blue），`tracker.py:130` 依 `self.target_color` 篩偵測；`hud.mjs:124` 顯示「目標：紅衣／藍衣」。
- 仍寫死紅色：`advisor.py:229`（Agent 候選只收 `color == "red"`）、`scheduler.py:94`；`live_mode/color.py` 仍只分 red／blue／none。
- LIVE 劇本固定為 `docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json`（A4-1、B4-1，各 4 人）：T 紅上衣＋背包＋胸章（目標）、A 與 T 同款紅上衣無背包、B 橘紅上衣（H 0.012，可能也被判 red）、C 藍上衣。
- 所以：LIVE 已可選紅或藍為目標顏色，並可點選特定候選作為種子（追 C 在追蹤器路徑已可行）；但 (a) 追蹤器重新取得時只靠顏色＋位置連續，無法區分同為紅色的 T／A／B；(b) Agent 路徑（`advisor.py:229`）與排程（`scheduler.py:94`）仍只認紅色，Agent 模式下追藍衣不會問 Agent；(c) E3 主實驗只以 T 為目標。
- 評分端 `src/amidst/evaluation/e3_scoring.py` 已收 `target` 參數，評分端有每個人物 GT，評分不用改。

**設計（baseline／對誰做／用誰判斷）**

| 目標 | 對誰做 | Baseline | 被比較 | 判斷 | 回答什麼 |
|---|---|---|---|---|---|
| T（現行） | 紅衣＋背包＋胸章 | B1 規則（RT-DETR＋HSV＋閘門，追紅） | A1／A2／A3（T 的參考裁切） | `e3_scoring` target='T'，預先登記 §6 | E3 主實驗 H1／H2／H4／H5 |
| C | 唯一藍衣 | B1 改追藍 | 同組，C 的參考裁切 | target='C' | 簡單對照：規則應夠好 |
| A | 與 T 同款紅衣 | B1 追紅（規則本來分不出 A／T） | Agent 用背包、胸章、褲色分辨 | target='A'，另報「跟成 T」錯人秒 | 最直接測 H2 |
| B | 橘紅 | B1 追紅 | 同上 | target='B' | 顏色接近的干擾 |

GT 只在評分端；身分 UNCONFIRMED；非預先登記，結果只標探索性。

**要做的事**
1. 把 `advisor.py`、`scheduler.py` 的紅色常數改成 session 選定的 `target_color`／種子描述；Agent 請求的參考裁切改用使用者選定的種子；同色目標（A、B）需要外觀描述（背包、褲色）才能區分，顏色門檻做不到。
2. B1 顏色跟著目標；目標 A／B 時寫明規則本來分不出。
3. Agent 請求的參考裁切換成選定目標。
4. 規則組用現有錄製重播（#617 輸入側確定），零成本；Agent 組要付費，每目標 K=3，走 ApiGuard。

**順序與限制**
- blocked：E3 評分與判定進 main（凍結）之前不動，避免改到 E3 正在用的推論路徑。
- 第一步：零成本規則組重播，target=C、A 評分；看規則在 A 上錯多少，再決定是否付費跑 Agent 組。
- 論文寫法：「目前只驗證單一目標 T；其他目標列後續工作」。


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

## 2. 實驗前的證據（2026-11-20 W1／W2 之前；目前狀態見 §0）

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
3. **E2b（#608／#617 已於 2026-11-22 合併；等 LIVE 端完成 §4 C7）**：在 LIVE 難題集上正式驗 H1／H2／H3／H4。估計 USD 6–12。
4. **E3（Codex 完成 Line 2 場景後）**：補足決策點數量。需求見 §5 W4。

總計約 USD 15–25，每一步先跑 dry-run。依 D242，每次核准只用於該實驗。

## 4. 現況不合理處與修正

以下每一項都用 grep 和讀碼確認過（基準 `main` `bc28f33b`），依影響假設驗證的程度排序。

### 4.0 需要使用者決策（擋住 H1／H2／H5 的規則本身）

**狀態（2026-11-20）**：R1、R2 已由使用者核准為 **D340**（[#93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-7016410023)），在本 PR 改寫 `docs/specs/DEVELOPMENT_RULES.md` 與產品規格。W1、W2 等本 PR 合併後才開始。

| # | 位置 | 為什麼不合理 | 怎麼改 | 改的人 |
| --- | --- | --- | --- | --- |
| R1 | `docs/DEVELOPMENT_RULES.md` L63（D64 條）：「Agent 不排序、不增刪候選，也不做 geometry、pathfinding…Agent 依序向候選取偵測與顏色證據…**第一版只用 RT-DETR＋HSV，不用看圖**」 | 規則**明文禁止**本計畫要驗證的 Agent：不准看圖（H1／H2／H5），不准加入規則沒給的候選（H3），不准用空間做推理（H4）。現在所有 Agent 程式都照這條寫成覆核者，這是根本原因 | 新 D 號：**Agent 模式（預設關、研究與 demo 皆可）**可以看渲染畫面、可以從所有偵測（含低分、顏色不符）中選、可以回答「仍在／不在／下一台看 X」、可以讀圖的邊與核定等級。決定性規則仍是預設與兜底；GT 隔離、ApiGuard、身分未確認不變 | 使用者決定；Claude 起草條文 |
| R2 | `docs/specs/Q1Q5_PRODUCT_SPEC.md` §4.3 L143（「Agent 只在合法 top-k 內依序取偵測與顏色證據」）、§3 表 L82（「Agent 不排序、不增刪」）、§1.2 L42 的 D128（「不送原始影格」） | 同 R1，規格把 Agent 定義成覆核者。D128 不送原始影格，和 LIVE 已經送圖（使用者核准過）不一致 | R1 決定後，同步改這三處，並把 D128 改成：送渲染合成畫面可以，真實人物影像仍然不送 | Claude |

### 4.1 Claude 可以立刻改（`src/amidst/q1q5/`，沒有 Codex 的 PR 在動；需 R1 先決定）

| # | 位置 | 為什麼不合理 | 怎麼改 |
| --- | --- | --- | --- |
| C1 | `src/amidst/q1q5/agent_decision.py` L93–101：請求是封閉 schema，只有 `TRACK_KEYS`、`CANDIDATE_KEYS`、`TOPOLOGY_KEYS = {graph_status, edges}`；`agent_wiring.py` L38–45 只送軌跡摘要（顏色、分數統計） | **Agent 沒有圖**（H1／H2）；空間資訊只有邊清單，沒有重疊、出口區、可行走連通與各邊核定等級（H1／H4） | schema v3：加 `frames`（參考裁切＋候選鏡頭當下畫面＋候選裁切，JPEG 的 SHA-256 與內容）；把 `topology` 換成必填的 **`scene_context`**（D340 補充，W2 實作）：(a) 區域圖的區域、出口區、相連關係；(b) 鏡頭邊與各邊核定等級；(c) 每台鏡頭的地面覆蓋多邊形、安裝位置、朝向、FOV、重疊鏡頭；(d) 設定裡其他鏡頭屬性（`covered_regions`、`entry_zones`、`exit_zones`）。來源只限 `camera_graph_v3_1`、`region_graph_v3_1`、鏡頭內外參、由標定與場景幾何投影的覆蓋多邊形（`live_coverage_gap.py` 的投影部分，不含 GT 評分），每項附來源 SHA-256；草稿圖照給並標核定等級；缺項標 `SCENE_CONTEXT_INCOMPLETE`。`scene_context` 每個場景算一次並快取，請求帶它的 SHA-256 與內容。`FORBIDDEN_KEYS` 不變，另加測試確認 `scene_context` 不含 GT、visibility、depth 欄位。請求分三層、靠前綴快取，見 §4.3 |
| C2 | `agent_decision.py` L337：`if not match or not match[0]['rule_eligible']: raise ILLEGAL_CANDIDATE`；`cross_camera_demo.py` L195–196 也只接受 `eligible` 中的選擇 | Agent 看得到顏色不符的候選，卻**不准選**。顏色篩選仍是硬閘門（H3） | Agent 模式下可選任何 `considered` 候選；選了 `rule_eligible=false` 的人時，在稽核中記 `RULE_OVERRIDE:<原因>` |
| C3 | `cross_camera_demo.py` L186：`if decider is not None and current is not None and eligible:` | 只有規則**至少有一個合格候選**時才問 Agent。全部顏色不符、目標失聯、零候選時 Agent 完全不被問，而這正是複雜情況 c3／c4（H1／H4） | 有 `considered` 候選、或失聯超過 N 個樣本時也呼叫 decider；新增回答 `STILL_HERE_OCCLUDED`、`NOT_VISIBLE`（附 `next_camera_hint`），由規則決定怎麼顯示 |
| C4 | `cross_camera_demo.py` L170–172：`gap < 0` → `CURRENT_CAMERA_STILL_OBSERVED`，不進 `considered` | 重疊鏡頭交接（c5）時，另一台鏡頭的候選 Agent 根本看不到（H1） | 放進 `considered`，標 `overlap=true` |
| C5 | `cross_camera_demo.py` L32–33（`min_score = 0.4` 連結門檻、`local_track_min_score = 0.3`）、L126 | 低於 0.3／0.4 的框在 Agent 看到前就被刪了；遮擋或遠距離的目標分數通常偏低（H5／H3） | Agent 模式另送「低信心框」（索引 floor 到 0.3）的裁切；規則照舊用門檻 |
| C6 | `agent_decision.py` L49 `MAX_REASON_CODES = 4` | 格式問題讓約 12% 的「圖上沒有邊」決策退回規則（D325 §5）；這不是決策閘門 | 驗證前截斷到 4 個，或在提示裡寫明上限 |
| C8a | `src/amidst/q1q5/q4_evidence.py` L123、L131–134：`score < query_min_score` 直接跳過，`presence` 只由 HSV 判定（`MATCH_STRONG`／`WEAK`…）；`q1_search.py` 是 index-only | **RT-DETR 分數門檻加 HSV 是 Q4「有沒有目標」的最終答案**，沒有任何看圖確認（H5／H6） | 先做 E1 的離線評估器（不改 API）；E1 成立後，把 Agent 看圖確認加成 Q4 的可選路徑（見 X3） |

**現況對照（2026-11-20，W2 #645 第一步，PR #648 merge `8290f190`；程式 `src/amidst/q1q5/agent_service.py`、`scene_context.py`，不改 `cross_camera_demo.py`／`agent_decision.py`）**

| # | 狀態 | 做法與備註 |
| --- | --- | --- |
| C1 | 已完成（新介面） | 三層請求；必填 `scene_context`（含各來源 SHA-256、`incomplete` 缺項）；測試確認無 GT／visibility／depth。舊 `agent_decision.py` 的 schema 未動，契約新版本仍待另開 |
| C2 | 已完成（新介面） | 可選任何偵測；`rule_eligible=false` 記 `RULE_OVERRIDE` |
| C3 | 已完成（新介面） | 每個決策點都問；新回答 `STILL_HERE_OCCLUDED`、`NOT_VISIBLE`＋`next_camera_hint`。`cross_camera_demo.py` L186 未改 |
| C4 | 已完成（新介面） | 所有鏡頭的偵測都進請求，重疊鏡頭標記；`cross_camera_demo.py` L170 未改 |
| C5 | 已完成（新介面） | 索引下限 0.3 的所有類別偵測都送，分數與顏色是 `gate` 資訊 |
| C6 | 已完成（新介面） | `reason_codes` 截斷到 4，不退回 |
| X1／X2 | 未做 | `candidates.py`、8785 開關是 `waiting:codex`；#645 第二步 |
| C8a | E1 已完成；API 未改 | W1 逐格評估（#644，PR #647 merge `afddfe74`）：H5 有條件成立（§0）。Q4 仍只有規則路徑，Agent 看圖確認的可選路徑是 X3，未做 |
| G7 | 已修正 | 已修正：所有付費呼叫經 ApiGuard（4f665d55）：#655（issue #651）讓 `scripts/agent_decision/run_provider.py` 的 OPENAI 每次嘗試、`OpenAIPredictionAdapter` 的每次傳輸嘗試都先經 `ApiGuard.run`，DENIED 時不呼叫 provider，重試重新檢查；兩者仍預設關閉，adapter 仍未接到 8785。見 [`PAID_API_G7_20261120.md`](../operations/PAID_API_G7_20261120.md) |

### 4.2 要等 Codex（同檔有 Codex 的 PR，或屬 Codex 範圍）

| # | 位置 | 為什麼不合理 | 怎麼改 | 改的人 | `waiting:codex` |
| --- | --- | --- | --- | --- | --- |
| C7 | `src/amidst/live_mode/advisor.py` L224（只收 `color == "red"` 的人）、L284（`SILENT_PICK` 要 ≥ 2 人在 `gate_m = 3.0` m 內）、L286–287＋L196（`LOST_WITH_CANDIDATES` 要 ≥ `lost_min_candidates = 2`）、L91–95（請求只有兩張圖和 k） | LIVE 只有在規則已把目標放進候選、而且候選 ≥ 2 時才問 Agent；A4 21 次中 15 次目標不在候選。單一候選、零候選、非紅衣都不問。請求也沒有空間資訊（H1／H3／H4） | 候選改成所有人（顏色只當特徵）；單一候選、零候選、失聯時也可以問，回答可以是「不在，看鏡頭 X」；請求附鄰接鏡頭與多鏡頭畫面 | Claude | 是（#608 也改 `advisor.py`） |
| X1 | `src/amidst/q1q5/candidates.py` L63–71：`scope_unapproved` → 所有轉移記 `GRAPH_NOT_APPROVED` 並排除 | 8785 Q5 controller 的 Agent 候選是 0，從來沒有呼叫 API（H3／H6） | Agent 模式下把未核定的轉移連同核定狀態一起交給 Agent；規則模式維持 fail-closed | Codex（Q5 controller） | 是 |
| X2 | #639：8785 Agent 開關改接 `associate()` | 方向對，但如果只改接、不先做 C1–C3，8785 的 Agent 仍然是不看圖的覆核者，結果會和 D325 一樣 | 順序改成 C1–C3 → #639 | Claude | 是（#623 動 `serve_demo_integration.py`） |
| X3 | Q1／Q2 查找、Q4 證據的 API（`q1_search.py`、`q4_evidence.py` 的 route） | Agent／規則在查找模式不能切換，只有 Q3 解析可以走 LLM（H6） | E1 成立後加入 Agent 看圖確認的可選路徑，回應附 `decision_source` | Codex（API 契約）；Claude 起草契約 | 是 |
| X4 | 資料：複雜預錄場景不存在；LIVE 難題集還沒正式錄製 | H1 沒有足夠的複雜決策點 | Line 2 場景（§5 W4）；#608／#617 已合併（2026-11-22），E3 劇本待 #652後錄製難題集 | Codex | 是 |

**和假設無關、不用優先處理**：#633（LIVE 改 workbench-v2 風格）。

### 4.3 W2 實作要求與完成定義

**請求三層結構（場景上下文做成固定前綴，靠快取減少重複傳送）**

1. **固定前綴**：system 指示、角色、規則、輸出格式，加上整份 `scene_context`（連通性、鏡頭圖與核定等級、每台鏡頭的位置、朝向、FOV、覆蓋多邊形、重疊）。
   - 每個場景版本只產生一次。
   - 用穩定的序列化：鍵排序、固定數值格式、固定換行。
   - 附場景版本雜湊（`scene_context_sha256`）。
2. **每次追蹤固定**：目標參考裁切圖和外觀描述。
3. **每次變動**：當下影格或裁切圖、候選、時間、規則給出的資訊（閘門結果、規則答案）。

規則：

- 每次請求只用鏡頭 ID 指向前綴裡的資料，不重送鏡頭屬性。
- 使用 OpenAI 的前綴提示快取：前綴要逐字相同，放在請求最前面。若 API 支援 `prompt_cache_key`，就用場景雜湊當 key。
- 參數名稱、最短可快取長度、折扣和保留時間，以實作當時的 OpenAI 官方文件為準，不憑記憶；實驗紀錄要寫出查閱的文件網址與日期。
- 每次呼叫都記錄總輸入 token 和 `cached_tokens`（或官方對應欄位），透過 `ApiGuard` 帳本保存。

**快取策略正式比較（使用者要求記錄這個比較）**

- 用同一批決策點、同樣的請求內容，比較三組：
  - (a) 每次完整重送，不快取；
  - (b) 固定前綴＋提示快取；
  - (c) 對話狀態接續（例如沿用前一輪回應的對話狀態；做法以官方文件為準），小樣本即可。
- 每組記錄：
  - 輸入 token、`cached_tokens`、命中率；
  - 單次延遲 p50／p95；
  - 每個決策點的花費（USD）；
  - 決策結果是否和 (a) 相同。快取不應改變答案；不同的決策點要逐一列出，並在 K 次重複中區分模型本身的隨機性。
- 結果寫在兩個地方：W2 的實驗紀錄，以及一份簡短的成本與延遲紀錄（`docs/evaluation/` 下），收錄到 [#479](https://github.com/Polalalabear/amidst/issues/479) 的「報告素材」。
- 付費照 `ApiGuard` dry-run 與使用者核准；這個比較的金額在 W2 的核准裡另列。

**完成定義（不能只交程式）**

W2 的 PR 要同時包含：

1. 程式與測試：C1–C6、三層請求、`scene_context` 與 GT 欄位檢查、快取欄位記錄。
2. 快取策略比較的實驗紀錄，以及成本與延遲紀錄。
3. 產品規格 `docs/specs/Q1Q5_PRODUCT_SPEC.md` 中 Agent 輸入與請求結構的章節：三層結構、`scene_context` 欄位。
4. `docs/index/CODE_DOC_MAP.md`：新增的程式↔文件對應。
5. `docs/index/README.md`：追加一筆。
6. 本文件 §4 的現況對照：C1–C6 改成「已完成」並附 PR。
7. 有 authority pin 的文件照前例登記新 pin，並跑 `scripts/check_architecture_guard.py`。

## 5. 工作拆解（依優先順序）

| # | 工作 | 驗證 | 負責 | 依賴 | 建議模型／effort |
| --- | --- | --- | --- | --- | --- |
| W1 | **E1 逐格評估器並實跑**：從 r004 抽格並分層；三組比較：Q4 規則、Agent 看圖、Agent 只給文字 | H5、H2 | Claude | 無（付費金額需使用者核准；送渲染畫面已在 LIVE 做過，但預錄送圖是否要等 R1，由協調者決定） | Sonnet / high |
| W2 | **主動 Agent 決策器**（實作要求與完成定義見 §4.3）：完成 C1–C6（schema v3：送圖、空間資訊、閘門當資訊、可以不選人），在 r004 跑 E2a 試跑；併入看圖 Agent 實驗 session 的成果 | H1、H2、H3、H4 | Claude | R1 | Sonnet / high |
| W3 | **LIVE 端主動 Agent**：做 C7，在難題集跑 E2b，含四組消融與「閘門照擋」組 | H1、H2、H3、H4 | Claude | C7（#608／#617 已合併；E3 劇本 #652） | Sonnet / high |
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
