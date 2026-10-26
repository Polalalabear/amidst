# r004 A4／B4 情境卡 v1（D87）

日期：2026-10-27｜起草：Claude（評估端，D75／D87）｜Model / effort：Claude Opus 5.5 / high

## 狀態

**PROPOSED，待使用者核定。**本文件是情境卡（劇本的設計規格），**不是劇本、不是 Ground Truth、不授權渲染**。依 [D87](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6421557959)：使用者核定情境卡之後，Codex 才做 Blender 可行性檢查（不渲染）；檢查通過、劇本固定 hash 之後，才進 #115。

- 所有時刻都是**計畫目標值**（來源時間，從 run 的 sample 0 起算，單位秒），沒有任何一個來自渲染、renderer 軌跡、visibility 或 depth。Codex 做可行性檢查時，可以在不違反 §1 規則的前提下把時刻移動 ±0.5 s，並回報移動後的值。
- 表中的決策窗與進入窗是依 D79 公式算出的**參考值**；正式值由評估端 adapter 依固定 hash 的劇本重算（D79 第 1 項）。
- 本文件只用到圖 v3、D79 文件、契約、#222 評分器與 #238 的文字與 JSON，沒有讀任何 RGB、GT、軌跡、visibility、depth。

## 0. 摘要

| 方案 | 長度 | 渲染鏡頭 | Q2 場次 | 計分事件 | 預計 SEARCHING | 估計 RGB | 評分器 |
| --- | ---: | --- | ---: | --- | ---: | ---: | --- |
| 目前（D68／#238） | A4 30 s、B4 30 s | 4＋5 | 各 1 | A4 約 1、B4 約 3（D79 表） | — | 0.55 GiB（兩案合計） | — |
| **A4-1（建議）** | 50 s | 4 台（不變） | 1 | 4（SWITCH 3、NO_SWITCH 1） | 3 | 0.41 GiB | 不改 |
| A4-2 | 72 s | 4 台（不變） | 2 | 6（SWITCH 3、RETURN 1、NO_SWITCH 2） | 2＋2 | 0.59 GiB | 不改；adapter 要分場次 |
| **B4-1（建議）** | 42 s | 5 台（不變） | 1 | 4（SWITCH 3、NO_SWITCH 1） | 3 | 0.43 GiB | 不改 |
| B4-2 | 78 s | 5 台（不變） | 2 | 8（SWITCH 5、RETURN 1、NO_SWITCH 2） | 3＋3 | 0.79 GiB | 不改；adapter 要分場次 |

建議 **A4-1＋B4-1**：計分事件由約 4 個增加到 8 個，每個 run 只開一個 Q2 場次，評分器與 D79 都不用改，RGB 合計約 0.83 GiB，在目前磁碟（9.3 GiB 可用、8 GiB 停止線）的餘裕內。兩個豐富方案合計約 1.38 GiB，超過約 1.3 GiB 的餘裕，要先清出空間才能做（§4）。

---

## 1. 限制

### 1.1 只用圖 v3 的鏡頭與轉移

依據：圖 v3 #235 head `f1a0910`（`camera_graph_v3.json` SHA-256 `9896be11…`，`tracking_scope_v3.json` `ed5b6899…`）。56 個有向對中有 22 條轉移、34 個排除。CAM_ENTRY 只用於查找（D74），追蹤鏡頭有 7 台。

**每個 run 實際能用的轉移。**候選只取「run 的鏡頭 ∩ tracking scope」（契約 §5.4 第 0 步，D81-2），所以 A4 沒渲染的 W2、R101_IN、BRANCH、WIDE，B4 沒渲染的 EXT_CAR、EXT_CLEAR，都不會成為候選。

| 出口（from 鏡頭：出口區） | 圖 v3 目的鏡頭（字母序） | A4 實際候選 | B4 實際候選 |
| --- | --- | --- | --- |
| EXT_CAR：NORTH／SOUTH_APPROACH、EXT_CLEAR：E_OUT_VEST | W1、W2 | **W1** | （不在 run） |
| W1：E_VEST_CORR | EXT_CAR、EXT_CLEAR、W2 | **EXT_CAR、EXT_CLEAR** | W2（只在 M1 核准時才有） |
| W1：E_PORTAL_R101 | R101_IN、W2 | 無 | **R101_IN**、W2（M1） |
| W1：E_W_CORNER | BRANCH、W2、WIDE | 無 | **BRANCH、WIDE**、W2（M1） |
| W2：E_W_CORNER | BRANCH、W1、WIDE | — | **BRANCH、WIDE**、W1（M1） |
| W2：E_PORTAL_R101 | R101_IN、W1 | — | **R101_IN**、W1（M1） |
| W2：E_OUT_VEST | EXT_CAR、EXT_CLEAR | — | 無 |
| BRANCH：E_W_CORNER、WIDE：E_W_CORNER | W1、W2 | — | **W1、W2** |
| BRANCH：E_CORNER_N、WIDE：E_PORTAL_R102 | （沒有轉移） | — | 無 |
| R101_IN：E_PORTAL_R101 | W1、W2 | — | **W1、W2** |

- G4 之後 relation 全是 UNKNOWN，候選一律在 tier 4，依 camera_id 字母序（D81-3），`top_k` = 3。出口命中零個或多個時，取該鏡頭全部出口的聯集（§5.4 第 1 步）。
- 「無」表示出口沒有任何可用候選：系統會在第一次搜尋時直接 RETURN，之後每 1 s 再搜一次。路線若從這裡**永久離開**，搜尋次數很快就會用完（§1.7）。
- 本卡不新增鏡頭、不改鏡頭位置／朝向／FOV、不新增轉移、不改 tracking scope。

### 1.2 決定帶來的限制

| 決定 | 對情境卡的限制 |
| --- | --- |
| D74 | CAM_ENTRY 照常渲染（A4，供 Q1），不當起點或候選。EXT → ENTRY、ENTRY → W1 不設計分事件；從追蹤器的角度，VEST_W 是盲區。 |
| D77 | EXT_CAR↔EXT_CLEAR、BRANCH↔WIDE 不建轉移。追蹤中的鏡頭若在重疊區看丟目標，系統切不到另一台，會一直 RETURN。所以 SWITCH 若允許兩台目的鏡頭（{EXT_CAR, EXT_CLEAR}、{BRANCH, WIDE}），進場後的路線要**留在兩台的共視區**，直到下一次離開。 |
| D79 | SWITCH 計畫空檔 `t_N − t_X` ≤ 5.2 s；RETURN 暫失 < 1.8 s；每窗恰好一個已執行動作；NO_SWITCH 要有完成的回應覆蓋到窗終點（否則 `COVERAGE_MISSING`）；窗依序、不重疊。報告必須寫明「本版只評空檔 ≤ 5.2 s、暫失 ≤ 1.8 s 的事件，超出範圍的情況依目前評分器會因多次 RETURN 判 miss，未納入」。 |
| D67 | `search_window_us` W = 6 s、`research_interval_us` R = 1 s、`session_max_research_rounds` = 6；`link_max_gap_us` L = 0.6 s（D65）；Δ = 0.2 s（5 fps）。 |
| D73 §14-27 | 第一版沒有 LOST 期限。LOST 不是評分器的動作類型，本卡不設 LOST 計分事件。 |
| D81 M1 | W1↔W2 的空路徑在 loader 中算成 APPROVED_WALKABLE。本卡**沒有任何計分事件需要 W1↔W2**（§1.5）。 |
| D87 | 圖 v3、G4 範圍、yyin 第一包不重做；#238 的 `source_duration_us` 依核定長度重發。 |

### 1.3 事件設計值（含餘裕）

| 事件類型 | D79 上限 | 本卡設計值 | 餘裕 | 理由 |
| --- | --- | --- | --- | --- |
| SWITCH 空檔 `g = t_N − t_X` | ≤ 5.2 s | **1.0–4.0 s**（一般 3.0 s；穿門 1.5–2.0 s） | 上限 ≥ 1.2 s（6 格） | 1.2 s 用來吸收「目標還在畫面中就先漏檢」的提早失聯 δ（P1、#218）。只要 `g + δ ≤ 5.2 s`，未來窗仍涵蓋入口，只會有一個動作。下限 1.0 s 見下一點。 |
| SWITCH 空檔下限 | 隱含 > −0.2 s | ≥ 1.0 s | — | 決策時刻約在 `t_X + 0.8 s`，切鏡只能進到不早於決策時刻的觀測。若 `g < 0.8 s`，進入觀測最早就是決策時刻，必須在 `t_N + 1 s` 前被偵測到，可用的格數很少。`g ≥ 1.0 s` 時進入窗有完整 8 格。 |
| RETURN 暫失 `t_N − t_X` | < 1.8 s（D79 建議 ≤ 1.6 s） | **1.2 s** | 上限 0.6 s（3 格）；下限 0.4 s（2 格） | 暫失要長到能觸發搜尋（約 `t_X + 0.6–0.8 s`，視格點相位而定，契約 §8.2 與 D79 推導差一格），又要短到第二次重搜（約 `t_X + 1.8 s`）之前就回到畫面。 |
| NO_SWITCH | 窗內無 SWITCH（允許 RETURN） | **經過出口但不離開**，目標全程可見 | — | 不設計短暫遮擋（≤ 0.4 s）型：r004 走廊有沒有遮擋物 UNKNOWN，而且多漏一格就會進搜尋。 |

另外兩個條件（適用所有 SWITCH，交 Codex 用計畫路線＋靜態校正檢查，§6）：
- **原鏡頭最後可見時刻 `t_L` ≤ `t_N − 1.0 s`。**D79 推導假設在 `t_X` 失聯。若原鏡頭在走出出口區之後仍看得到目標，實際空檔會變短；`t_L ≥ t_N + 0.2 s` 時，進入觀測一定晚於進入窗，判 miss。
- **目的鏡頭第一次可見時刻 `t_V` ≥ `t_N − 0.6 s`。**進入窗的早側只有 L = 0.6 s。若目的鏡頭在目標踏進入口區之前就看得到它（例如 EXT_CAR 的涵蓋區含 VEST_W），進入觀測可能早於進入窗。允許兩台目的鏡頭時，兩台的進入時刻相差要 ≤ 0.8 s；`t_N` 取較早的那台。

### 1.4 事件間距（由 D79 公式與 `t_prev_end` 推導）

記號：事件 k 的錨點為 `t_N(k)`（SWITCH／RETURN）或 `t_X(k)`（NO_SWITCH），窗終點 `e_k`。

- SWITCH／RETURN 窗：`[max(t_prev_end, t_N − W), t_N + R)`，所以 `e_k = t_N(k) + 1 s`。
- NO_SWITCH 窗：`[max(t_prev_end, t_X − W), min(t_X + W, 下一窗起點, 查詢終點))`。本卡的 adapter 慣例（待核）：「下一窗起點」取下一事件**未截斷**的起點 `t_N(k+1) − W`，也就是 NO_SWITCH 讓位。
- 第一個事件的 `t_prev_end` 取查詢起點。

| 規則 | 條件 | 由來 | 本卡採用 |
| --- | --- | --- | --- |
| S1 硬下限（窗截斷也不衝突） | `t_X(k+1) − t_N(k) ≥ R − Δ − L + δ` ＝ **0.2 s＋δ** | 下一事件的正確動作最早在 `t_X(k+1) − δ + 0.8 s`，必須 ≥ `e_k` | 停留時間 `t_X(k+1) − t_N(k)` ≥ **5 s**（新鏡頭至少接上約 25 格） |
| S2 窗不截斷 | `t_N(k+1) − t_N(k) ≥ W + R` ＝ **7.0 s** | `t_N(k+1) − W ≥ e_k` | 連續 SWITCH／RETURN 錨點間距 ≥ **8.0 s**（多 1 s 餘裕） |
| S3 未來窗不汙染 | 每次離開後 `W + Δ` ＋ 1 s ＝ **7.2 s** 內，目標不出現在該出口任何一台「非允許」候選鏡頭（RETURN 事件則是所有候選） | 第一次搜尋的候選窗是 `[t_X + Δ, t_X + Δ + W)`，會「看到未來」 | 每個事件逐條檢查（各方案表格的「S3」欄） |
| S4 NO_SWITCH 有效寬度 | 窗至少涵蓋 `[t_X − 1 s, t_X + 3 s)`：`t_X(NS) − t_N(前) ≥ 2 s`，`t_N(後) − t_X(NS) ≥ 9 s` | 誤觸發的搜尋最晚約在 `t_X + 0.8 s`；留 2 s 以上看錯切 | 本卡最窄的是 `[t_X − 4, t_X + 4)` |
| S5 NO_SWITCH 覆蓋 | 同一場次中，NO_SWITCH 之後一定還有計畫內的搜尋 | 評分器要求有決策紀錄的 `source_time_us` ≥ 窗終點（U7 未知，不靠終止紀錄） | NO_SWITCH 不放在場次最後 |
| S6 場次頭尾 | 第一個 `t_X` ≥ 查詢起點＋3 s；查詢終點 ≥ 最後窗終點＋2 s，且到查詢終點之前目標都在最後一台鏡頭可見；run 終點 ≥ 查詢終點 | seed 要先接穩；最後不能留下 LOST 尾巴 | 各方案都照此設定 |

**最小錨點間距的結論：**連續兩個 SWITCH／RETURN 事件，`t_N` 間距硬下限是 `t_N(k+1) − t_N(k) ≥ g(k+1) + 0.2 s + δ`，窗不截斷的下限是 **7.0 s**；本卡一律 ≥ 8.0 s，停留 ≥ 5 s。NO_SWITCH 前後分別 ≥ 2 s 與 ≥ 9 s。

### 1.5 不做重疊接手；W1↔W2 不計分

- 依收據的靜態深度，W1 從門廳端看向轉角（E_VEST_CORR 約 4 m、E_PORTAL_R101 約 10.5 m、E_W_CORNER 約 16 m），W2 從轉角端看向門廳（E_W_CORNER 約 3.7 m、E_PORTAL_R101 約 7 m、E_OUT_VEST 約 15 m）。兩台幾乎**共視整段 CORR_W**，所以 W1↔W2 實質上是重疊對，不是盲區，不符合 D79 的盲區搜尋模型。這是由收據的靜態深度推得，實際共視範圍 UNKNOWN（交 Codex 確認）。
- 所以本卡**不設 W1↔W2 計分事件**。B4 的路線也不在 W1 追蹤時走向門廳（W1：E_VEST_CORR 在 B4 的唯一候選是 W2）。
- **M1 對本卡的影響（G4 時由使用者決定）：**
  - 若 W1↔W2 核准為合法切鏡：走廊中漏檢造成的失聯可能切到 W2（或 W1）。這次 SWITCH 若落在 NO_SWITCH 或 SWITCH 窗內，該事件判 miss。
  - 若不核准（保守值）：同樣的失聯會變成 RETURN 後重新接上。RETURN 在 NO_SWITCH 窗內是允許的，但會消耗搜尋次數。
  - **建議 v1 不核准**，與 #235 複核 M1 的保守選項一致。A4 不受影響（W2 不在 A4 run）。
- 允許兩台目的鏡頭的事件（EXT_CAR／EXT_CLEAR、BRANCH／WIDE、W1／W2）屬於「盲區後切到其中一台」，不是兩台之間的接手，可以計分。進場後依 D77 留在共視區。

### 1.6 B4-d 固定為一種情況

**B4-d 固定為 ③：「轉角暫失後回到走廊」的 SWITCH**，BRANCH／WIDE → {W1, W2}。
- ①（≤ 600 ms 同鏡頭重新出現）會改用 1.3 節「經過出口不離開」型的 NO_SWITCH 代替，因為短暫遮擋需要場景遮擋物（UNKNOWN），而且一格漏檢就會進搜尋。
- ②（RETURN）不放在轉角：轉角由 BRANCH 與 WIDE 共視，系統追的是哪一台事先不知道，同一段走位不能保證兩台都看丟。B4-2 的 RETURN 改放在 R101 室內（只有 R101_IN 一台）。

### 1.7 每個 Q2 場次的搜尋次數上限

`session_max_research_rounds` = 6（D67）。達到上限時 `ENDED_BY_LIMIT`，status 不是 COMPLETE，**整個場次不評分**（#222 在讀劇本前就拒絕）。第一次 SEARCHING 算不算一輪、第 6 次是開始時就結束還是做完才結束，仍是 U5（UNKNOWN）。
- 本卡規則：**每個場次計畫內的 SEARCHING ≤ 3 次**（SWITCH 與 RETURN 各 1 次，NO_SWITCH 0 次），保留 ≥ 2 次給漏檢造成的計畫外搜尋（P1 已觀察到目標可見時大量漏檢）。
- 計分事件要超過 3 個 SEARCHING，只能把 run 分成兩個 Q2 場次（豐富方案）。不改 D67 參數。
- 不設計「離開所有渲染鏡頭後不再出現」的 LOST 尾巴（原 A4-d）：每 1 s 一次重搜，約 5 s 就會用完次數。

### 1.8 GT 隔離

- 情境卡與之後的劇本只在評估端使用，runtime、索引、圖、prompt、參數都不讀（#222 凍結順序：先凍結輸出、驗 hash，才開劇本）。
- `t_X`、`t_N` 只能由劇本**計畫**（路點＋時刻＋凍結的 entry／exit footprint）算出。若只有 Blender keyframe 或 renderer 匯出能提供時刻，就屬於 GT，交使用者決定（D79 U2）。
- §1.3 的 `t_L`／`t_V` 檢查只用計畫路線投影到**靜態校正**，結果只回報「通過／不通過」，用來決定路線能不能用；不進評分、不進 runtime。
- 藍衣干擾者的時刻只用來安排場景，不寫進評分事件（§6 Q9）。
- 人物身分一律 UNCONFIRMED。相機與進入時刻都符合，也不代表是同一個人。

---

## 2. A4（室外 → 入口 → 走廊）

渲染鏡頭不變：CAM_EXT_CAR、CAM_EXT_CLEAR、CAM_ENTRY（只供 Q1）、CAM_W1，共 4 台。

### 2.1 方案 A4-1（中等，50 s，1 個場次）

**路線**

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–8.0 | OUT_W 車旁 → 西入口前 | EXT_CAR（顯式觀測 seed） | 從車旁走向入口，全程留在 EXT_CAR 視野，從 NORTH 或 SOUTH_APPROACH 出口區離開 |
| 1 | 8.0–11.0 | VEST_W | （追蹤盲區；ENTRY 看得到但只供查找） | 穿過門廳 |
| 2 | 11.0–26.0 | CORR_W | W1 | 進走廊；16.0 經過 R101 門口不進門；走過門口約 2 m 後折返，回到門廳端 |
| 3 | 26.0–29.0 | VEST_W | — | 走出門廳 |
| 4 | 29.0–36.0 | OUT_W（EXT_CAR∩EXT_CLEAR 共視區） | EXT_CAR 或 EXT_CLEAR | 在入口外的共視區停留（例：講電話），不走到只有一台看得到的地方 |
| 5 | 36.0–39.0 | VEST_W | — | 再次進門 |
| 6 | 39.0–50.0 | CORR_W | W1 | 進走廊，停在可見處直到 run 結束 |

查詢範圍 `[0.0, 48.0)` s；run 長 50 s（`source_duration_us` 50,000,000）。

**事件**

| 事件 | 類型 | 起 → 訖 | `t_X` | `t_N` | 空檔（餘裕） | `allowed_camera_ids` | 決策窗（參考） | 進入窗（參考） | S3 |
| --- | --- | --- | ---: | ---: | --- | --- | --- | --- | --- |
| A4-c1 | SWITCH | EXT_CAR → W1（經 VEST_W） | 8.0 | 11.0 | 3.0 s（2.2 s） | {CAM_W1} | [5.0, 12.0) | [10.4, 12.0) | 候選只有 W1 ✔ |
| A4-n1 | NO_SWITCH | W1 經過 E_PORTAL_R101 不進門 | 16.0 | — | — | — | [12.0, 22.0) | — | A4 中 R101_IN、W2 都不在 run，沒有可切候選 ✔ |
| A4-e | SWITCH | W1 → EXT（往外） | 26.0 | 29.0 | 3.0 s（2.2 s） | {CAM_EXT_CAR, CAM_EXT_CLEAR} | [23.0, 30.0) | [28.4, 30.0) | 候選＝兩台允許鏡頭 ✔ |
| A4-c2 | SWITCH | EXT_* → W1 | 36.0 | 39.0 | 3.0 s（2.2 s） | {CAM_W1} | [33.0, 40.0) | [38.4, 40.0) | 候選只有 W1 ✔ |

- 間距：c1→n1 停留 5 s；n1→e 的 `t_N(e) − t_X(n1)` ＝ 13 s；e→c2 停留 7 s、錨點間距 10 s。全部符合 S1–S4。
- 計畫 SEARCHING 3 次（約 8.8、26.8、36.8 s）。n1 由 26.8 s 的決策覆蓋（S5 ✔）。
- A4-c2 的 `t_X` 依實際追蹤的是 EXT_CAR 還是 EXT_CLEAR 而不同，兩者的空檔都要 ≤ 4.0 s（§6 Q3）。

**不計分（明列）**

| 情況 | 理由 |
| --- | --- |
| A4-a EXT_CAR↔EXT_CLEAR 接手 | D77；段 0、4 留在 seed 鏡頭或共視區，避免發生 |
| A4-b EXT → ENTRY、ENTRY → W1 | D74；ENTRY 只供 Q1 |
| A4-d 離開 W1 後不再出現（LOST） | 本方案沒有；run 結束時目標在 W1 可見（S6） |

- **G4 逐邊核准（需要）：**E_OUT_VEST、E_VEST_CORR（traversability 與 state），用於 T_CAM_EXT_CAR__CAM_W1、T_CAM_EXT_CLEAR__CAM_W1、T_CAM_W1__CAM_EXT_CAR、T_CAM_W1__CAM_EXT_CLEAR。**不需要：**M1（W2 不在 A4）、E_W_CORNER、E_PORTAL_R101、E_CORNER_N、E_PORTAL_R102。
- **渲染量：**4 台 × 50 s × 5 fps ＝ 1,000 格；RGB 約 **0.41 GiB**（沿用 #132 的舊 A 係數 63,976 KiB／150 格，新場景壓縮率 UNKNOWN）。CPU forward 約 18.5 min（舊係數 1.108 s／格）。`.blend`、索引、暫存大小 UNKNOWN。
- **主要風險：**
  1. W1 或 EXT 漏檢造成計畫外搜尋。落在窗內就多一個動作而判 miss；累積到上限則整場不評分（§1.7）。
  2. A4-e 允許兩台，但 EXT_CAR 的涵蓋區含 VEST_W：它可能在目標走到入口區之前就看到人，使進入觀測早於進入窗（§1.3 的 `t_V` 條件）。兩台入口區的進入時刻差也可能 > 0.8 s。
  3. 段 4 若被 EXT_CLEAR 接手，而目標走到只有 EXT_CAR 看得到的車旁，就會一直 RETURN（D77）。

### 2.2 方案 A4-2（豐富，72 s，2 個場次）

**路線**

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–12.0 | OUT_W | EXT_CAR（seed） | 繞車走一段較長的路線再走向入口，全程在 EXT_CAR 視野 |
| 1 | 12.0–15.0 | VEST_W | — | 穿過門廳 |
| 2 | 15.0–32.0 | CORR_W | W1 | 20.0 經過 R101 門口不進門；走到走廊較遠處折返；回到門口 |
| 3 | 32.0–33.2 | R101 門檻內側 | （W1 看不到；A4 沒渲染 R101_IN） | 跨進門檻約 1 m，停 1.2 s 後退回走廊 |
| 4 | 33.2–40.0 | CORR_W | W1 | 走回門廳端 |
| 5 | 40.0–43.0 | VEST_W | — | 走出門廳 |
| 6 | 43.0–59.0 | OUT_W 共視區 | EXT_CAR 或 EXT_CLEAR | 在共視區停留；50.0 沿入口外側走過入口但不進門，全程可見 |
| 7 | 59.0–62.0 | VEST_W | — | 再次進門 |
| 8 | 62.0–72.0 | CORR_W | W1 | 走廊內停在可見處，直到 run 結束 |

場次：**S1 `[0.0, 37.0)`**（seed：EXT_CAR 顯式觀測）、**S2 `[35.0, 70.0)`**（seed：約 35.0 s 的 W1 顯式觀測）。run 長 72 s（`source_duration_us` 72,000,000）。

**事件**

| 場次 | 事件 | 類型 | 起 → 訖 | `t_X` | `t_N` | 空檔／暫失（餘裕） | `allowed_camera_ids` | 決策窗（參考） | 進入窗（參考） | S3 |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- | --- |
| S1 | A4-c1 | SWITCH | EXT_CAR → W1 | 12.0 | 15.0 | 3.0 s（2.2 s） | {CAM_W1} | [9.0, 16.0) | [14.4, 16.0) | ✔ |
| S1 | A4-n1 | NO_SWITCH | W1 經過門口 | 20.0 | — | — | — | [16.0, 26.0) | — | ✔ |
| S1 | A4-r1 | RETURN_TO_ORIGIN | W1 → 門檻 → W1 | 32.0 | 33.2 | 1.2 s（0.6 s） | — | [27.2, 34.2) | — | 出口不明時候選是 EXT_*：目標要在 39.2 s 之後才出現在 EXT 畫面；`t_N(e)` ＝ 43.0 ✔ |
| S2 | A4-e | SWITCH | W1 → EXT | 40.0 | 43.0 | 3.0 s（2.2 s） | {CAM_EXT_CAR, CAM_EXT_CLEAR} | [37.0, 44.0) | [42.4, 44.0) | ✔ |
| S2 | A4-n2 | NO_SWITCH | EXT 經過入口不進門 | 50.0 | — | — | — | [44.0, 56.0) | — | 誤觸發時候選只有 W1，目標不在 W1 ✔ |
| S2 | A4-c2 | SWITCH | EXT_* → W1 | 59.0 | 62.0 | 3.0 s（2.2 s） | {CAM_W1} | [56.0, 63.0) | [61.4, 63.0) | ✔ |

- 間距：r1→e 停留 6.8 s、錨點間距 9.8 s；其他都 ≥ 16 s。n1 由 r1 的搜尋（約 32.8 s）覆蓋；n2 由 c2 的搜尋（約 59.8 s）覆蓋。
- 計畫 SEARCHING：S1 2 次、S2 2 次。若 Q2 不支援 run 中途的顯式 seed（§6 Q7），可以退回單一場次 `[0.0, 70.0)`，計畫 SEARCHING 4 次，只剩 1 次餘裕。
- A4-r1 依賴三件 UNKNOWN：W1 看不到門檻內側；出口候選為空時，系統在第一次搜尋就寫一筆 accepted 的 RETURN_TO_ORIGIN；目標回到畫面後，能用唯一的真實候選開新片段（契約 §8.2「回原探針」）。

**不計分**：同 A4-1，另外 S1／S2 重疊的 `[35.0, 37.0)` 不放事件，兩份評估劇本的事件不重複。

- **G4 逐邊核准：**同 A4-1（E_OUT_VEST、E_VEST_CORR）。A4-r1 不用任何邊。
- **渲染量：**4 × 72 × 5 ＝ 1,440 格；RGB 約 **0.59 GiB**；forward 約 26.6 min。另需 #238 重發 72 s 時鐘；長度超過 D68 的「改提各 60 s」，要使用者另外核定長度。
- **主要風險：**A4-1 的三項，再加：
  1. RETURN 的暫失只能在約 1.0–1.6 s 之間：回到畫面那幾格若漏檢，就會出現第二次 RETURN 而判 miss（K1）。
  2. 分場次要 Q2 支援 run 中途的顯式 seed，adapter 也要分開產生兩份劇本（§5）。

---

## 3. B4（走廊 → 轉角 → R101）

渲染鏡頭不變：CAM_W1、CAM_W2、CAM_BRANCH、CAM_R101_IN、CAM_WIDE，共 5 台。

**seed 固定在 W2（顯式觀測）。**目標從門廳端往轉角走時，離 W2 越來越近（框約 100 px 到 300 px）。若改由 W1 追蹤，到轉角時距離約 16 m、框約 65 px（收據），漏檢風險較高。

### 3.1 方案 B4-1（中等，42 s，1 個場次）

**路線**

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–11.0 | CORR_W | W2（seed） | 從 R101 門口前約 4 m 起走向轉角；4.0 經過門口不進門；走進 W2 的轉角接近區，再從 W2 下方離開畫面 |
| 1 | 11.0–14.0 | CORR_W → CORNER | （盲區，約 4 m） | 轉進轉角 |
| 2 | 14.0–21.0 | CORNER（BRANCH∩WIDE 共視區） | BRANCH 或 WIDE | 停留、轉身（例：看指示牌），不走出共視區 |
| 3 | 21.0–24.0 | CORNER → CORR_W | （盲區） | 走回走廊 |
| 4 | 24.0–30.0 | CORR_W | W1 或 W2 | 走回 R101 門口 |
| 5 | 30.0–32.0 | PORTAL_R101 門檻 | （盲區） | 穿門 |
| 6 | 32.0–42.0 | R101 | R101_IN | 在 R101_IN 視野內走動、停留，直到 run 結束 |

查詢範圍 `[0.0, 40.0)`；run 長 42 s（`source_duration_us` 42,000,000）。

**事件**

| 事件 | 類型 | 起 → 訖 | `t_X` | `t_N` | 空檔（餘裕） | `allowed_camera_ids` | 決策窗（參考） | 進入窗（參考） | S3 |
| --- | --- | --- | ---: | ---: | --- | --- | --- | --- | --- |
| B4-n1 | NO_SWITCH | W2 經過 E_PORTAL_R101 不進門 | 4.0 | — | — | — | [0.0, 8.0) | — | 誤觸發時候選是 R101_IN（和 M1 下的 W1）：R101_IN 不能從門內看到走廊（§6 Q4） |
| B4-b | SWITCH | W2 → CORNER | 11.0 | 14.0 | 3.0 s（2.2 s） | {CAM_BRANCH, CAM_WIDE} | [8.0, 15.0) | [13.4, 15.0) | M1 核准時，W1 在 [11.2, 18.2) 不能看到轉角內的目標 |
| B4-d（③） | SWITCH | BRANCH／WIDE → 走廊 | 21.0 | 24.0 | 3.0 s（2.2 s） | {CAM_W1, CAM_W2} | [18.0, 25.0) | [23.4, 25.0) | 候選＝兩台允許鏡頭 ✔ |
| B4-e | SWITCH | W1／W2 → R101_IN（經 PORTAL_R101） | 30.0 | 32.0 | 2.0 s（3.2 s） | {CAM_R101_IN} | [26.0, 33.0) | [31.4, 33.0) | M1 核准時，目標在 37.2 s 前不能回走廊；本方案留在室內到結束 ✔ |

- 間距：n1→b 的 `t_N(b) − t_X(n1)` ＝ 10 s；b→d 停留 7 s、錨點間距 10 s；d→e 停留 6 s、錨點間距 8 s。
- 計畫 SEARCHING 3 次（約 11.8、21.8、30.8 s）。n1 由 11.8 s 的搜尋覆蓋。
- B4-d 的 `t_X` 依追蹤的是 BRANCH 還是 WIDE 而不同（WIDE 的 E_W_CORNER 在約 11–12 m 處），兩者的空檔都要 ≤ 4.0 s。B4-b 進入時 BRANCH 與 WIDE 的入口時刻差、B4-d 進入時 W1 與 W2 的入口時刻差，都要 ≤ 0.8 s（§6 Q3）。

**不計分**

| 情況 | 理由 |
| --- | --- |
| B4-a W1↔W2 | 共視同一條走廊，屬重疊接手；M1 未定（§1.5） |
| B4-c BRANCH↔WIDE | D77；段 2 留在共視區 |
| B4-d ①、② | §1.6 固定為 ③ |
| 走進 CORR_N 北段或 R102 | 沒有轉移（E_CORNER_N、E_PORTAL_R102），會一直 RETURN；R102 依 #132 不進路線 |

- **G4 逐邊核准（需要）：**
  - E_W_CORNER：用於 T_CAM_W2__CAM_BRANCH、T_CAM_W2__CAM_WIDE、T_CAM_BRANCH__CAM_W1、T_CAM_BRANCH__CAM_W2、T_CAM_WIDE__CAM_W1、T_CAM_WIDE__CAM_W2。
  - E_PORTAL_R101：用於 T_CAM_W1__CAM_R101_IN、T_CAM_W2__CAM_R101_IN，另需 R101 用途核准（#132 註明尚未成立）。
  - **不需要：**M1（建議不核准）、E_OUT_VEST、E_VEST_CORR、E_CORNER_N、E_PORTAL_R102。
- **渲染量：**5 × 42 × 5 ＝ 1,050 格；RGB 約 **0.43 GiB**；forward 約 19.4 min。
- **主要風險：**
  1. 走廊漏檢造成計畫外搜尋（W1／W2 共視，M1 決定這時會切鏡還是 RETURN）。
  2. 穿門的實際盲區可能 < 1.0 s：R101_IN 可能從門內看到走廊，W1／W2 也可能看到門檻內側。
  3. 轉角停留時若走出 BRANCH∩WIDE 共視區，會一直 RETURN（D77）。
  4. B4-d 若選到 W1，目標在約 16 m 處，框小，可能漏檢或判成 MATCH_WEAK；這時會改選 W2，也在允許集合內。

### 3.2 方案 B4-2（豐富，78 s，2 個場次）

S1 與 B4-1 **完全相同**（同一路線、同一組 4 個事件、查詢 `[0.0, 40.0)`），之後接續：

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 6' | 32.0–40.0 | R101 | R101_IN | 走進室內 |
| 7 | 40.0–41.2 | R101 中 R101_IN 看不到的一角（存在與否 UNKNOWN） | — | 走出 R101_IN 視野 1.2 s 後走回 |
| 8 | 41.2–48.0 | R101 | R101_IN | 走回門口 |
| 9 | 48.0–49.5 | PORTAL_R101 門檻 | （盲區） | 出門 |
| 10 | 49.5–66.0 | CORR_W | W1 或 W2 | 走向轉角；56.0 走進轉角接近區後停下、退回約 2 m，全程可見；稍後再走向轉角 |
| 11 | 66.0–69.0 | CORR_W → CORNER | （盲區） | 轉進轉角 |
| 12 | 69.0–78.0 | CORNER 共視區 | BRANCH 或 WIDE | 停留，直到 run 結束 |

場次：**S1 `[0.0, 40.0)`**（seed：W2）、**S2 `[36.0, 76.0)`**（seed：約 36.0 s 的 R101_IN 顯式觀測）。run 長 78 s（`source_duration_us` 78,000,000）。

| 場次 | 事件 | 類型 | 起 → 訖 | `t_X` | `t_N` | 空檔／暫失（餘裕） | `allowed_camera_ids` | 決策窗（參考） | 進入窗（參考） | S3 |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- | --- |
| S1 | B4-n1、B4-b、B4-d、B4-e | 同 B4-1 | | | | | | | | |
| S2 | B4-r1 | RETURN_TO_ORIGIN | R101_IN → 視野外 → R101_IN | 40.0 | 41.2 | 1.2 s（0.6 s） | — | [36.0, 42.2) | — | 候選 W1／W2：目標要在 47.2 s 之後才出現在走廊；`t_N(f)` ＝ 49.5 ✔ |
| S2 | B4-f | SWITCH | R101_IN → 走廊 | 48.0 | 49.5 | 1.5 s（3.7 s） | {CAM_W1, CAM_W2} | [43.5, 50.5) | [48.9, 50.5) | ✔ |
| S2 | B4-n2 | NO_SWITCH | W1／W2 走進轉角接近區後退回 | 56.0 | — | — | — | [50.5, 62.0) | — | 誤觸發時候選含 BRANCH／WIDE：目標不能讓轉角鏡頭看到（§6 Q5） |
| S2 | B4-b2 | SWITCH | W1／W2 → CORNER | 66.0 | 69.0 | 3.0 s（2.2 s） | {CAM_BRANCH, CAM_WIDE} | [63.0, 70.0) | [68.4, 70.0) | ✔ |

- 間距：r1→f 停留 6.8 s、錨點間距 8.3 s；f→n2 為 6.5 s（≥ 2 s）；n2→b2 為 13 s（≥ 9 s）。
- 計畫 SEARCHING：S1 3 次、S2 3 次。n2 由 b2 的搜尋（約 66.8 s）覆蓋。
- B4-b2 的起點若是 W1，出口是 W1：E_W_CORNER（約 16 m，框約 65 px），比 B4-b 更容易提早失聯。設計空檔 3.0 s 可容許 δ ≤ 2.2 s。

**不計分**：同 B4-1。

- **G4 逐邊核准：**同 B4-1，另加 T_CAM_R101_IN__CAM_W1、T_CAM_R101_IN__CAM_W2（E_PORTAL_R101），以及 W1 起點往轉角的 T_CAM_W1__CAM_BRANCH、T_CAM_W1__CAM_WIDE（E_W_CORNER）。
- **渲染量：**5 × 78 × 5 ＝ 1,950 格；RGB 約 **0.79 GiB**；forward 約 36.0 min。長度超過 60 s，要使用者另外核定。
- **主要風險：**B4-1 的四項，再加：
  1. R101 裡是否有 R101_IN 看不到、又走得到的區域：UNKNOWN。沒有的話，B4-r1 要刪掉。
  2. B4-n2 的轉角接近區可能被 BRANCH／WIDE 看到；漏檢觸發搜尋時就會切過去，判 miss。
  3. RETURN 的暫失只能在約 1.0–1.6 s 之間。
  4. 分場次的依賴同 A4-2。

---

## 4. 建議與優缺點

**建議：A4-1＋B4-1。**兩案合計 RGB 約 0.83 GiB、forward 約 37.9 min，共 8 個計分事件、每個 run 1 個場次。

| 方案 | 優點 | 缺點 |
| --- | --- | --- |
| **A4-1（建議）** | 計分事件由 1 個（A4-c）增為 4 個，含往返兩個方向的入口盲區；每個轉移在 A4 都只有允許的候選，S3 自動成立；單一場次，評分流程與 #222 現行一致；50 s 在 D68「改提各 60 s」的範圍內 | 沒有 RETURN 事件；A4-e 的兩台允許鏡頭有入口時刻差的風險（EXT_CAR 看得到 VEST_W） |
| A4-2 | 6 個事件，含 RETURN 與兩個 NO_SWITCH；路線較長、兩次進出 | RETURN 依賴三件 UNKNOWN 的 controller 行為；要分場次；72 s 超過 D68 的 60 s；兩個豐富方案加起來超過磁碟餘裕 |
| **B4-1（建議）** | 原計畫（#132）的「轉角暫失 → R101」完整走一遍，3 個盲區 SWITCH（轉角去、轉角回、穿門）加 1 個 NO_SWITCH；B4-d 固定為 ③；不需要 M1；單一場次 | 穿門盲區短；R101_IN／W1／W2 在門口互相看得到的程度 UNKNOWN |
| B4-2 | 8 個事件，S1 與 B4-1 完全相同，可以先依 S1 評分；加入出門、第二次轉角、室內 RETURN | 需要「R101 室內有視野外區域」（UNKNOWN）；要分場次；78 s；兩個豐富方案合計約 1.38 GiB，超過目前約 1.3 GiB 的餘裕（9.3 GiB 可用 − 8 GiB 停止線），要先清空間 |

- 次佳組合：A4-1＋B4-2，約 1.20 GiB，貼近餘裕上限，且 `.blend`、索引、暫存大小 UNKNOWN，不建議在目前磁碟狀態下做。
- 若先渲染 B4-1，之後要做 B4-2 就得重新產生一個 run（B4-2 不是已渲染 run 的延長），時鐘與 run 註冊也要再發一次。

---

## 5. 評分器是否要改

**結論：評分器（#222 @ `362a87c`，`q5_switch_eval.py` SHA-256 `0fd1ef68…`）與 D79 規則都不用改。**四個方案的每個計分事件，都能用現有的 `compare_script` 原樣評分：
- SWITCH 與 RETURN_TO_ORIGIN 都是「窗內恰好一個已執行動作」。SWITCH 另比對 `allowed_camera_ids` 與進入窗；允許兩台目的鏡頭時，在 `allowed_camera_ids` 明列即可。
- NO_SWITCH 是「窗內沒有 SWITCH、允許 RETURN」，而且要有決策紀錄的 `source_time_us` ≥ 窗終點。本卡以 S5 保證由後續的計畫內搜尋覆蓋。
- 事件數不限；窗依序、不重疊、都在查詢範圍內（§1.4 的計算已滿足）。
- 一份評估只吃一個 session 的 response 與一份劇本。

**一定要有（不是改評分器，是評估端 adapter；任何正式劇本本來就需要）：**
1. **劇本計畫 → `q5-evaluation-script.v1` 產生器**（評估端，D75）。依固定 hash 的劇本計畫，用 D79 公式把 `t_X`／`t_N` 換成整數微秒的 `decision_window_us`、`entry_window_us`；處理截斷與 §1.4 的 NO_SWITCH 讓位慣例；帶 `run_id`、`clock_id`、`allowed_camera_ids`、`approval_ref`（U11：指向使用者核定留言＋內容 hash）。
2. **事前檢查**（adapter 拒絕不合格的計畫，不交給評分器）：SWITCH 空檔 ≤ 5.2 s（本卡設計 ≤ 4.0 s）、RETURN 暫失 < 1.8 s、S1–S6、每場次計畫 SEARCHING ≤ 3、事件不跨場次。報告寫入 D79 第 2 項規定的範圍聲明。

**豐富方案才需要：**
3. **分場次**：adapter 依場次查詢範圍把事件分成兩份劇本，各自固定 hash，各自交 `compare_script`；兩份事件集合不得重疊。
4. **跨場次彙總**：兩份報告的分子分母相加，另寫一份彙總，並列出各場次的 `uncovered_executed_actions`。不改單份報告的 schema。
5. Q2 支援 run 中途的顯式 seed（Codex，§6 Q7）。這是產品端前提，不是評分器的改動。

**有條件才需要（預設不做）：**
6. 允許兩台目的鏡頭、但兩台的入口時刻差 > 0.8 s 時，現有 schema 只有一個 `entry_window_us`，評不了。本卡的處理是改路線讓時刻差 ≤ 0.8 s；做不到時，該事件改列不計分。「依鏡頭分別給進入窗」要新的劇本 schema 版本，列入第二條線。

**延後到第二條線（D87 第 1 項）：**
- 一個窗內多次 RETURN（空檔 > 5.2 s、暫失 ≥ 1.8 s），或依鏡頭分別給進入窗。
- 長時間 LOST、離開所有渲染鏡頭的尾段（原 A4-d），以及 `ENDED_BY_LIMIT` 的部分評分。
- D77 重疊接手（EXT_CAR↔EXT_CLEAR、BRANCH↔WIDE）與 W1↔W2 共視接手（M1）。
- 短暫遮擋型 NO_SWITCH（B4-d ①）、新鏡頭（例如 VEST_W 補盲）、新路徑（CORR_N 北段、R102）。

---

## 6. Codex 可行性問題（可直接貼上；不渲染）

```text
@Codex：r004 A4／B4 情境卡 v1（docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md）的 Blender 可行性檢查。
等使用者核定情境卡之後才開始。只讀靜態 r004 場景、靜態校正與凍結的 ROI／footprint；不渲染、不存 .blend、
不讀 renderer 軌跡／visibility／depth，也不寫 #115 劇本。對每一題回覆「可行／不可行／UNKNOWN」並附數字。
方案：A4-1、A4-2、B4-1、B4-2（核定版以使用者選的為準）。

Q1 走得通：各方案每一段路線在靜態導航網格／地板上是否走得通（含門廳、R101 門檻、轉角）？
   A4-2 段 3 能否跨進 R101 門檻約 1 m 再退回？B4-2 段 7，R101 是否有 R101_IN 看不到、又走得到的區域？
Q2 長度與步速：各段的計畫路徑長度（m）與換算步速，是否落在 0.8–1.5 m/s？若不行，請提出最小的時刻調整（±0.5 s 內）。
Q3 盲區時刻（只用計畫路線＋靜態校正投影）：每個 SWITCH 請給 t_X（離開出口 footprint）、t_L（原鏡頭最後可見）、
   每台允許目的鏡頭的 t_V（第一次可見）與 t_N（進入入口 footprint）。檢查 t_L ≤ t_N − 1.0 s、t_V ≥ t_N − 0.6 s、
   1.0 ≤ t_N − t_X ≤ 4.0 s；允許兩台時，兩台的 t_N 差 ≤ 0.8 s。
   需要特別看：A4-e（EXT_CAR 涵蓋 VEST_W）、B4-b／B4-b2（BRANCH 與 WIDE）、B4-d（W1 遠端與 W2 近端）、B4-f。
Q4 門口：PORTAL_R101 能不能有 ≥ 1.0 s 的盲區？R101_IN 從門內看得到走廊嗎？W1／W2 看得到門檻內側嗎（A4-r1 需要 W1 看不到）？
Q5 轉角：W2 轉角 patch 到 BRANCH／WIDE 入口的距離與時間；BRANCH∩WIDE 共視區能不能容納 6–7 s 的停留與轉身；
   B4-n2 的轉角接近區會不會被 BRANCH／WIDE 看到；M1 核准時，W1 看不看得到轉角內的停留點？
Q6 室外：EXT_CAR∩EXT_CLEAR 共視區（約 40.9 m²）能不能容納 A4 段 4／段 6 的停留與「沿入口外側走過」？
   A4 段 0 能否全程只在 EXT_CAR 視野？
Q7 Controller（#110）：(a) U5：第一次 SEARCHING 算不算一輪？第 6 次是開始時就結束，還是做完才結束？
   (b) 出口候選為空時（例：A4 的 W1：E_PORTAL_R101），第一次搜尋是否就寫一筆 accepted 的 RETURN_TO_ORIGIN？
   (c) RETURN 後目標回到原鏡頭，能否以唯一的真實候選開新片段回到 PLAYING？
   (d) U7：查詢範圍結束時有沒有一筆 source_time_us = 查詢終點的紀錄？
   (e) Q2 能否用 run 中途的顯式 observation 當 seed，並限定查詢範圍（A4-2、B4-2 的 S2）？
   (f) 不在 run 的鏡頭（A4 的 W2／R101_IN，B4 的 EXT_*）是否在 top_k 截斷之前就排除？
Q8 渲染長度與磁碟（只估算）：各方案的格數、r004 材質下每格大小、渲染時間、索引時間與暫存；
   目前可用 9.3 GiB，低於 8 GiB 停止。兩個豐富方案合計估 1.38 GiB RGB，請說明是否可行、要清什麼。
Q9 藍衣干擾者：請提出出現時段，條件是不在任何事件的進入窗內出現在目的鏡頭，也不和目標同時在同一台鏡頭的 2 m 內；
   建議讓它在一個 SWITCH 窗內出現在非目的的候選鏡頭（測 CONDITION_MISMATCH）。時刻只在場景與劇本中使用，不進評分事件。
Q10 時鐘：情境卡核定後，#238 的 source_duration_us 依核定長度重發（A4-1 50 s、B4-1 42 s；豐富方案 72／78 s）。
回覆請附「實際產出 / Actual output」。
```

---

## 7. UNKNOWN 與待決

| # | 項目 | 誰 | 影響 |
| --- | --- | --- | --- |
| U-C1 | 各段路徑長度、步速、門檻與轉角穿越時間（圖 v3 的 `nominal_path_length_m` 全是 null） | Codex（Q1、Q2） | 全部計畫時刻 |
| U-C2 | W1／W2 實際共視範圍；R101_IN 透過門看得到的範圍；EXT_CAR 對 VEST_W 的可見範圍 | Codex（Q3–Q5） | §1.3 的 `t_L`／`t_V` 條件、M1 的影響 |
| U-C3 | R101 是否有 R101_IN 視野外、走得到的區域 | Codex（Q1） | B4-r1 |
| U-C4 | BRANCH∩WIDE、EXT_CAR∩EXT_CLEAR 共視區的形狀是否容納停留 | Codex（Q5、Q6） | B4 段 2、A4 段 4／6 |
| U-C5 | U5、U7、空候選時的 RETURN、RETURN 後重新接上、run 中途 seed、非 run 鏡頭在 top-k 前排除 | Codex（Q7） | §1.7、A4-r1、B4-r1、分場次 |
| U-C6 | 新場景每格大小、渲染時間、`.blend`／索引／暫存大小 | Codex（Q8） | 磁碟 |
| U-C7 | NO_SWITCH「下一窗起點」取下一事件未截斷起點的慣例 | 使用者（隨情境卡核定） | NO_SWITCH 窗終點 |
| U-C8 | M1：W1↔W2 是否核准為合法切鏡（本卡建議不核准） | 使用者（G4） | §1.5 |
| U-C9 | 豐富方案超過 60 s 的長度核定 | 使用者 | #238 時鐘 |
| D79 U2 | `t_X`／`t_N` 能否只由劇本計畫算出 | Codex 說明；使用者決定 | GT 隔離 |
| D79 U6 | Agent 模式下 `decision_time_us` 是否一律等於 SEARCHING 開始時刻；Qwen 一律逾時、由規則接手（D73 X2 不自動重啟）時，結果照 `by_decided_by` 分列 | Codex | 不影響本卡的時刻設計 |

---

## 8. 來源

- D87：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6421557959 ；D73–D86 同在 #93。
- D79 文件：`docs/evaluation/Q5_DECISION_WINDOW_D79.md` @ `origin/mainline/q1q5` `2675c21`（最後修改 commit `7ef9f25`），SHA-256 `7010ca5560b2ca71f35b1f86f87cc0d0b671a6af176065da04fbafeb4a9a6f43`。
- 圖 v3 #235 head `f1a0910cb7ecbdff28f8411d834d3d9d95d7b925`：`camera_graph_v3.json` `9896be113bf6e2b5f2d9344f1227484674fda2c2bb983d32a70d8ffcc4adfc7e`、`tracking_scope_v3.json` `ed5b68995094b060b21a9dba6a05e26a21aa0af15c0f8dcb7fd0bd56424af80a`、`region_graph_v3.json` `717772600caaa51d88b55f62d118bbef2d3f10514ebffeabd41081e801a45ae0`、`docs/engineering/R004_GRAPH_RECEIPT.md` `42c511588c97b94ac6ec2b42b2ddb4d4280df5f313778608ccce0a33687e9c70`。複核（M1）：https://github.com/Polalalabear/amidst/pull/235#issuecomment-6416451188
- 契約：`docs/contracts/Q1_Q2_FIRST_DEMO_V1.md` @ `origin/codex/q1q5-staging` `680ca35`，SHA-256 `b700bf86041f4853ae37dd54bbc9d93199a07be3d5d3c87bc8c2f6455570df04`（§5.4、§8.2、§8.6、§11）。
- 評分器 #222 @ `362a87c`：`src/amidst/evaluation/q5_switch_eval.py` `0fd1ef68c4c83443e8311723224b76f103c142dd018275e7c1596f917e85d9f2`、`docs/evaluation/Q5_SWITCH_EVAL_V1.md`。
- 時鐘 #238 head `07571b6`（A4 14:00、B4 14:10 Asia/Taipei，各 30 s）；複核 https://github.com/Polalalabear/amidst/pull/238#issuecomment-6416423209
- 容量係數：`docs/engineering/R004_SCENE_CHANGE_PROPOSAL.md` §5（63,976 KiB／150 格、1.108406209 s／格，舊 A 素材，不是新場景上界）。
- P1 漏檢：https://github.com/Polalalabear/amidst/pull/228#issuecomment-6416863116 ；#218。
- 磁碟：本 session 開始時 `df -h /` 可用 9.3 GiB（2026-10-27）。

**沒有用到、也沒有讀的來源：**GT、renderer 軌跡／visibility／depth、任何 RGB、`.blend`、#211 private producer。
