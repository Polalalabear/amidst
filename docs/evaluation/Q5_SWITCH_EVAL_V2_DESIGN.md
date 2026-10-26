# Q5 評分規則 v2 設計稿（L2-1，#244）

日期：2026-10-27｜起草：Claude（評估端，D75／D87／D90）｜Model / effort：Claude Opus 5.5 / high

## 狀態

**PROPOSED，待使用者核定。**本文件只寫規則，不含程式。核定後由 Sonnet 依本稿實作（新模組，見 §3）。

- 只作用在第二版（D90 第 4 項第一批）。**Line 1 已核定範圍不變**：圖 v3、G4、D89 的 A4-1／B4-1、D79 的範圍聲明、#222 評分器（`q5_switch_eval.py`，`q5-switch-eval-v1.1`）、`q5-evaluation-script.v1`。
- 所有窗都由 D79 的四個參數 `W`、`R`、`L`、`Δ` 導出，不新增數字。下文的「5 fps、D67 代入值」只是參考；正式值由評估端依固定 hash 的劇本與綁定的 parameter_set 算出。
- 沒有讀 GT、renderer 軌跡、visibility、depth、RGB 或 `.blend`。§1 的公式檢查用一個 20 行的理想 controller 模擬（只用 W／R／L／Δ 與整數毫秒，不讀任何資料），結果見 §1.4。

### 參數（全部沿用，D79 §1.1）

| 符號 | 意思 | 5 fps、D67 值 | 來源 |
| --- | --- | ---: | --- |
| `Δ` | 索引格距 `index_interval_us` | 0.2 s | D65、D68 |
| `L` | `link_max_gap_us`（`elapsed_us ≥ L` 進 SEARCHING） | 0.6 s | D65；契約 §8.2、§11；D78 |
| `W` | `search_window_us`（候選窗固定長度，Q-05） | 6.0 s | D67；契約 §8.6 |
| `R` | `research_interval_us`（回原鏡頭後每隔 R 重搜） | 1.0 s | D67；契約 §14-13(a) |
| `N_max` | `session_max_research_rounds`（達到則 `ENDED_BY_LIMIT`） | 6 | D67；契約 §8.6、§8.7 |

時刻符號沿用 D79 §1.2：`t_X`（依計畫離開原鏡頭出口 footprint）、`t_N`（依計畫第一次進入目的鏡頭入口 footprint；RETURN 類是重新進入原鏡頭可見區）、`t_prev_end`（前一事件決策窗終點）。本稿另用：

| 符號 | 定義 | 來源 |
| --- | --- | --- |
| `g` | SWITCH 計畫空檔 `t_N − t_X`（依鏡頭時寫 `g_c = t_N(c) − t_X`） | 劇本計畫 |
| `d` | RETURN 計畫暫失 `t_N − t_X` | 劇本計畫 |
| `t_N(c)` | 允許目的鏡頭 c 的入口 footprint 進入時刻（§2.3） | 劇本計畫 |
| `t_N*` | 重疊接手的「等效進入時刻」`t_X + Δ + L`（§2.4） | 由 `t_X` 與參數導出 |
| `G1` | 第一版 SWITCH 空檔上界 `W + Δ − R` ＝ 5.2 s | D79「K1 門檻推導」 |
| `D1` | 第一版 RETURN 暫失上界 `Δ + L + R` ＝ 1.8 s（開區間） | D79；D90 第 1 項 |

---

## 0. 摘要

| # | 情境（D90 第一批） | 事件類別 `event_class` | 預期動作 | 窗（相對 v1 的改變） | 計分重點 |
| --- | --- | --- | --- | --- | --- |
| 1 | 一窗多次 RETURN | `LONG_GAP`、`LONG_LOSS` 共用的計分樣式 | — | — | 窗內允許「機械性 RETURN」；SWITCH 窗的樣式是 `RETURN* → SWITCH` |
| 2 | 長時間 LOST | `LONG_GAP`（SWITCH，`g > G1`）、`LONG_LOSS`（RETURN，`d ≥ D1`）；`LOST_TAIL` 待決 | SWITCH／RETURN／NO_SWITCH | `LONG_GAP` 決策窗起點改為夾住的公式；其他沿用 D79 | 依計畫數字分類；超過搜尋次數上限的事件不評分 |
| 3 | 依鏡頭分別給進入窗 | 任何 SWITCH | SWITCH | `entry_windows_us` 每台一窗 | 相機在 map 的鍵中，進入時刻在該台的窗內 |
| 4 | D77／D90 重疊接手 | `OVERLAP` 進入窗（掛在 SWITCH 事件的單台鏡頭上） | SWITCH | 用 `t_N* = t_X + Δ + L` 代入 D79 公式 | 取代 `t_V ≥ t_N − L`（重疊對必然違反） |
| 5 | 較長行走（A4-2／B4-2 類） | 不新增類別 | — | 每場次一份劇本 | 跨場次彙總報告；每場次計畫 SEARCHING 次數上限 |

分類由劇本計畫的數字決定，評分器依同一參數重算並驗證（§2.2、§4 U-D5）。`STANDARD` 類（v1 的 SWITCH／RETURN／NO_SWITCH，`g ≤ G1`、`d < D1`、只有 BLIND 進入窗）的規則與 v1 **逐字相同**。

---

## 1. 系統行為推導（評分規則的依據）

以下沿用 D79 的理想失聯假設：目標在 `t_X` 離開原鏡頭，第一個沒接上的索引格 `t_fm = t_X + Δ`，第一次 SEARCHING 的決策時刻 `t_s0 = t_fm + L = t_X + Δ + L`（5 fps、D67：`t_X + 0.8 s`；情境卡 §1.3 記錄格點相位可能使它早一格，屬 UNKNOWN，§5 C2）。

- 第 0 次搜尋的候選窗：`[t_X + Δ, t_X + Δ + W)`（契約 §8.6、§14-18(a)）。
- 第 k 次（k ≥ 1）重搜在 `t_k = t_s0 + k·R`，候選窗 `[t_k, t_k + W)`（D79 §1.1）。
- 每次 SEARCHING 消耗 1 輪；session 累計達 `N_max` 即 `ENDED_BY_LIMIT`（第一次算不算一輪、第 6 次是開始時還是做完才結束：U5，§5 C1）。

### 1.1 長空檔 SWITCH 的 RETURN 次數

最差情況下進入觀測落在進入窗最後一格 `t_N + R − Δ`（D79 推導同一假設）。第 k 次搜尋能看到這一格的條件：
- k = 0：`t_N + R − Δ ≤ t_X + W`，即 `g ≤ W + Δ − R = G1`（D79）。
- k ≥ 1：`t_N + R − Δ ≤ t_k + W − Δ`，即 `g ≤ W + L + Δ + (k − 1)·R`。

所以 SWITCH 前的 RETURN 次數上界：

```
n_r_max(g) = 0                                         若 g ≤ G1
           = max(1, ⌈(g − (W + L + Δ)) / R⌉ + 1)        若 g > G1
```

SEARCHING 次數 `n_s(g) = n_r_max(g) + 1`。D67 代入：

| g (s) | ≤ 5.2 | 5.2–6.8 | 6.8–7.8 | 7.8–8.8 | 8.8–9.8 | 9.8–10.8 | > 10.8 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RETURN 上界 | 0 | 1 | 2 | 3 | 4 | 5 | ≥ 6 |
| SEARCHING | 1 | 2 | 3 | 4 | 5 | 6 | ≥ 7（超過 `N_max`） |

`n_s(g) ≤ N_max` 的最大空檔 `G_max = W + L + Δ + (N_max − 2)·R` ＝ **10.8 s**（整個 session 只有這一個事件時；有其他事件時更短，§2.5）。

### 1.2 長暫失 RETURN 的 RETURN 次數

目標回到原鏡頭之前，每個 tick `t_s0 + k·R < t_N` 都會 SEARCHING → RETURN（候選窗裡沒有目標）。

```
n_ret(d) = ⌈(d − Δ − L) / R⌉          （名目值，d > Δ + L）
n_ret_max(d) = ⌊(d − Δ − L) / R⌋ + 1   （上界：tick 與重新出現同一格時，先處理哪個是 U5／D79 的 UNKNOWN）
```

`d < D1` 時 `n_ret_max = 1`，與 D79 一致。`n_ret_max(d) ≤ N_max` 的條件 `d < Δ + L + N_max·R` ＝ **6.8 s**（`D_max`）。

### 1.3 重疊接手的進入時刻

D90 第 2 項：重疊對也要原鏡頭失聯、進 SEARCHING 後才可切；進入觀測是目的鏡頭 `timestamp_us ≥ decision_time_us` 的觀測（契約 §8.6）。目標在決策時刻**已經**在目的鏡頭可見，所以：

- 進入時刻 ≈ 決策時刻之後的第一格：名目 `t_X + Δ + L`（＝ `t_N*`），格點相位早一格時 `t_X + L`。
- 計畫的 `t_N`（進入目的鏡頭入口 footprint）與目的鏡頭第一次可見 `t_V` 都**早於** `t_X`。v1 情境卡 §1.3 的條件 `t_V ≥ t_N − L` 與 D79 進入窗 `[t_N − L, t_N + R)` 對重疊對必然不成立：進入觀測取決於原鏡頭何時失聯，而不是目標何時走進目的鏡頭。
- 只要候選窗內目的鏡頭看得到目標，第 0 次搜尋就 SWITCH，只預期 1 個動作，沒有 K1 問題。

### 1.4 模擬檢查

在 `scratchpad`（不進 repo）用整數毫秒模擬 §1 的理想 controller：g 從 1.0 到 12.0 s（每 0.2 s）、進入觀測延遲 0–0.8 s（每格），實際 RETURN 次數都不超過 `n_r_max(g)`；`g ≤ 5.2 s` 一律 0 次。d 從 0.8 到 6.8 s，實際次數等於 `⌈(d − Δ − L)/R⌉`，在 tick 與重新出現同一格時比 `⌊…⌋ + 1` 少 1（即 U5 的邊界）。這是公式自洽檢查，不是 controller 實測。

---

## 2. 五類情境的規則

共通規則（全部沿用 v1／D79，不重述細節）：
- 時間一律來源微秒、半開區間；決策窗依序、不重疊、在 `resolved_source_ranges_us` 內；與相鄰窗重疊時截斷，NO_SWITCH 讓位（D89 第 3 項：「下一窗起點」取下一事件未截斷的起點）。
- 只看已執行動作（accepted SWITCH、accepted RETURN_TO_ORIGIN），以 decision_id 綁 timeline；窗外動作列 `uncovered_executed_actions`。
- 相機正確不代表同一人（UNCONFIRMED）；Agent／fallback 只轉錄。

### 2.1 一窗多次 RETURN（計分樣式）

**事件定義。**`LONG_GAP`（SWITCH）與 `LONG_LOSS`（RETURN）兩類事件的決策窗內，會依凍結的搜尋機制出現多個 RETURN（§1.1、§1.2）。這些 RETURN 是 Q-05 固定窗與 R 節奏的機械結果，不是錯誤。

**計分（建議 M1，§4 U-D1）：**

| 事件類別 | 正確（match = true） | miss（match = false） | 不評分（match = null） |
| --- | --- | --- | --- |
| `LONG_GAP`（SWITCH） | 窗內已執行動作依時間排序為 `RETURN_TO_ORIGIN* → SWITCH`：恰一個 SWITCH、它是窗內最後一個動作、相機與進入時刻符合 §2.3／§2.4 | 窗內 0 個 SWITCH；≥ 2 個 SWITCH；SWITCH 之後還有動作；相機或進入時刻不符 | 依 §2.6 的 `ENDED_BY_LIMIT` 決定 |
| `LONG_LOSS`（RETURN） | 窗內至少 1 個動作，而且全部是 `RETURN_TO_ORIGIN`（0 個 SWITCH） | 窗內有任何 SWITCH；窗內 0 個動作 | 同上 |
| `STANDARD`（v1） | v1 規則原樣：窗內恰一個動作 | v1 規則原樣 | v1 規則原樣（NO_SWITCH 的 `COVERAGE_MISSING`） |

- 「≥ 2 個 SWITCH 判 miss」沿用 v1「多次 SWITCH 不被第一個正確動作掩蓋」。
- RETURN 次數**不影響 match**，但逐事件報告 `return_count`、`return_count_max`（`n_r_max(g)` 或 `n_ret_max(d)`）與 `return_count_exceeds_max`（布林）。超過上界代表重新接上失敗或額外漏檢，另列，不在本類扣分（§4 U-D2）。
- `searching_count`：窗內決策紀錄 `searching_index` 的相異值個數（契約 §8.7 D69／U27），一併報告。

**邊界。**
- 只有 `LONG_GAP`／`LONG_LOSS` 類套用多 RETURN 樣式；`STANDARD` 類窗內 2 個 RETURN 仍判 miss（v1 不變）。
- 類別由計畫數字決定，不由觀察到的動作數決定：不能因為系統多 RETURN 了，就把 STANDARD 事件事後改成 LONG 類。

### 2.2 長時間 LOST（分類與窗）

**事件定義（D90 第 1 項）。**評估端分類，產品端不加狀態、不加 `lost_after_us`、不加 enum（D73 §14-27 不變）。

| 類別 | 條件（計畫數字） | 預期動作 | 可評上界 |
| --- | --- | --- | --- |
| `STANDARD` SWITCH | 所有 BLIND 鏡頭 `g_c ≤ G1`（5.2 s） | SWITCH | — |
| `LONG_GAP` | 至少一台 BLIND 鏡頭 `g_c > G1`，且 `n_s(max_c g_c) ≤ 本場次可用輪數`（§2.5） | SWITCH | `g ≤ G_max`（單一事件時 10.8 s） |
| `STANDARD` RETURN | `d < D1`（1.8 s，開區間） | RETURN | — |
| `LONG_LOSS` | `d ≥ D1`，且 `n_ret_max(d) ≤ 本場次可用輪數` | RETURN | `d < D_max`（單一事件時 6.8 s） |
| 超出上界 | `n_s` 或 `n_ret_max` 超過本場次可用輪數 | — | **adapter 拒絕放進劇本**（預期 `ENDED_BY_LIMIT`，整場不評分） |
| `LOST_TAIL` | 目標離開所有渲染鏡頭、查詢範圍內不再出現（原 A4-d） | NO_SWITCH | **待決**，見 §2.6 選項 E3 |

邊界依 D90：`g = 5.2 s` 屬 `STANDARD`；`d = 1.8 s` 屬 `LONG_LOSS`。

**窗公式。**

- `LONG_LOSS` 決策窗：**沿用 D79 RETURN 窗** `[max(t_prev_end, t_N − W), t_N + R)`。`d < D_max` 時 `t_N − W < t_X + Δ + L`，所以第一個 RETURN（名目 `t_X + 0.8 s`）一定在窗內，所有機械性 RETURN 都歸這個事件。
- `LONG_GAP` 決策窗（新）：

  ```
  start = max(t_prev_end, min(t_N_min, t_X + G1) − W)
  end   = t_N_max + R
  ```

  `t_N_min`／`t_N_max` 是所有允許鏡頭進入時刻的最小／最大值（§2.3；OVERLAP 鏡頭用 `t_N*`）。`g ≤ G1` 時 `start = t_N − W`，與 D79 完全相同；`g > G1` 時起點固定在 `t_X + G1 − W = t_X + Δ − R`（D67：`t_X − 0.8 s`），把這個事件自己的第一個 RETURN（`t_X + Δ + L`）收進窗內。公式在 `g = G1` 處連續。
- `LONG_GAP` 進入窗：D79 原式，每台各自（§2.3）。

**為什麼 `LONG_GAP` 不直接用 D79 起點 `t_N − W`：**`g` 在 5.2–6.8 s 時，第一個 RETURN 剛好落在 D79 窗內（判 miss 的 K1 來源）；`g > 6.8 s` 時前幾個 RETURN 落在窗外，變成窗外動作，報告看起來像系統亂動。新起點讓同一事件的 RETURN 全部歸這個事件（另列 §4 U-D9，可選回 D79 起點）。

**邊界與相鄰事件。**
- 起點早於 D79 窗，所以相鄰間距規則要重算：前一事件窗終點 `e_{k−1}` ≤ `t_X(k) + Δ − R` 才不截斷（取代情境卡 §1.4 S2 對 LONG_GAP 的寫法）；截斷時仍要 `e_{k−1}` ≤ `t_X(k) + L − δ`（情境卡 S1，δ 為允許的提早失聯，卡內 1.2 s），否則本事件的第一個 RETURN 會落進上一窗。
- 若前一窗是 NO_SWITCH，依 D89 第 3 項讓位：NO_SWITCH 終點取本事件未截斷的起點。
- 報告的範圍聲明（D79 第 2 項）在 v2 改寫為：「本版評 `g ≤ G_max`、`d < D_max` 且在本場次可用搜尋次數內的事件；`STANDARD` 類規則與 v1 相同；`LONG_*` 類允許機械性 RETURN」，並列出實際代入的秒數。

### 2.3 依鏡頭分別給進入窗

**事件定義。**一個 SWITCH 事件允許多台目的鏡頭時（例：{EXT_CAR, EXT_CLEAR}、{BRANCH, WIDE}、{W1, W2}），各台的入口 footprint 進入時刻 `t_N(c)` 可能不同。v1 只有一個 `entry_window_us`，情境卡 §1.3 因此要求兩台 `t_N` 差 ≤ 0.8 s、取較早者。v2 改為每台一窗。

**窗公式。**

| 進入窗種類 `kind` | 用於 | 公式 |
| --- | --- | --- |
| `BLIND` | 盲區後進入（v1 的唯一種類） | `[t_N(c) − L, t_N(c) + R)`（D79 原式，各台用自己的 `t_N(c)`） |
| `OVERLAP` | 重疊接手（§2.4） | `[t_N* − L, t_N* + R)` ＝ `[t_X + Δ, t_X + Δ + L + R)` |

決策窗終點取 `max_c` 的進入窗終點，起點用 §2.2 的公式（`STANDARD` 時等於 `max(t_prev_end, min_c t_N(c) − W)`）。

**計分。**
- 正確：（依類別的動作樣式成立，且）SWITCH 的 `camera_id` 是 `entry_windows_us` 的鍵之一，`entry_time_us` 落在**該台**的窗內。
- miss：相機不在鍵中；或相機在鍵中但進入時刻不在該台的窗（即使落在另一台的窗內）。
- 不評分：同 v1／§2.6。

**邊界與檢查（adapter 事前拒絕）。**
- `STANDARD` 類要求每台 BLIND 鏡頭 `g_c ≤ G1`；任一台超過，整個事件歸 `LONG_GAP`。
- BLIND 鏡頭仍要通過情境卡 §1.3 的 `t_V(c) ≥ t_N(c) − L` 與 `t_L ≤ t_N(c) − 1.0 s`（只當通過／不通過，不進分數；情境卡 §1.8）。「兩台 `t_N` 差 ≤ 0.8 s」的限制在 v2 取消。
- 「早可見盲區」（`t_L < t_V(c) < t_N(c) − L`，目的鏡頭在入口區之前就看到人，但原鏡頭已看不到）不是重疊、也不符 BLIND 窗：v2 預設**仍拒絕這種計畫**（§4 U-D6）。
- 同一台鏡頭不得同時有 BLIND 與 OVERLAP 兩種窗。

### 2.4 重疊對的失聯後接手

**事件定義（D90 第 2 項）。**圖 v4 新增 EXT_CAR↔EXT_CLEAR、BRANCH↔WIDE（第二版另有 W1↔W2）的轉移。目標從兩台的共視區走到只有目的鏡頭看得到的區域：原鏡頭失聯、進 SEARCHING 後，系統切到目的鏡頭，進入觀測是決策時刻之後的第一筆目的鏡頭觀測。

- `t_X`：依計畫離開**原鏡頭在這條重疊轉移上的出口 footprint**的時刻。v4 必須把重疊轉移的出口區放在原鏡頭可見範圍的邊緣，使 `t_X` 等於「原鏡頭最後可見」的計畫時刻（容許一格，P-OV2）。v4 出口區怎麼畫屬 Codex（§5 C5）。
- 不用 `t_N`、`t_V` 當錨（兩者都早於 `t_X`，§1.3）。

**窗公式（建議 O1：把 `t_N* = t_X + Δ + L` 代入 D79 公式，§4 U-D3）：**

| 窗 | 公式 | D67 代入 |
| --- | --- | --- |
| 決策窗 | `[max(t_prev_end, t_N* − W), t_N* + R)` | `[t_X − 5.2, t_X + 1.8)`，寬 7.0 s |
| 進入窗（OVERLAP） | `[t_N* − L, t_N* + R)` ＝ `[t_X + Δ, t_X + Δ + L + R)` | `[t_X + 0.2, t_X + 1.8)`，寬 1.6 s、8 格 |

- 早側 `t_X + Δ`：名目進入 `t_X + 0.8`，格點相位早一格時 `t_X + 0.6`，都在窗內；容許提早失聯 `δ ≤ L − Δ`（0.4 s、2 格）。
- 晚側 `+ R`：目的鏡頭偵測晚到，沿用 D79 的晚側容忍 R。
- 窗寬與 D79 BLIND 窗相同（`L + R`），只是錨點換成 `t_N*`。

**計分。**
- 正確：窗內恰一個已執行動作（`STANDARD`），它是 SWITCH，`camera_id` 是 OVERLAP 鍵，進入時刻在 OVERLAP 窗內。
- miss：切到別台、進入時刻在窗外（例如提早失聯 > 0.4 s，進入早於 `t_X + Δ`）、窗內有 RETURN 或第二個動作。
- 不評分：同 v1／§2.6。

**取代 `t_V ≥ t_N − L` 的計畫檢查（adapter 事前拒絕；只用計畫路線＋靜態校正，只當通過／不通過）：**

| 檢查 | 條件 | 理由 |
| --- | --- | --- |
| P-OV1 共視 | 目的鏡頭 `t_V ≤ t_X − L`，而且目標從 `t_V` 到 `t_N* + R + 5 s` 都在目的鏡頭可見範圍內 | 失聯時目的鏡頭必須已看到人；進入後至少停留 5 s（情境卡 S1） |
| P-OV2 出口對齊 | 原鏡頭最後可見 `t_L ∈ [t_X − Δ, t_X]` | 失聯時刻由 `t_X` 決定；若出口區畫在可見範圍內側，實際失聯更晚，進入會晚於窗 |
| P-OV3 未來窗不汙染 | `[t_X + Δ, t_X + Δ + W + 1 s)` 內，目標不出現在這個出口的任何非允許候選鏡頭 | 情境卡 S3 |
| P-OV4 共視停留 | 進入 `t_X` 之前的共視停留，目標不得離開原鏡頭可見範圍 | 否則在 `t_X` 之前就失聯（D77 的「留在共視區」改為「離開時只往目的鏡頭單獨可見區走」） |

**邊界。**
- 同一事件可以混合 BLIND 與 OVERLAP 鏡頭（例：圖 v4 下從 BRANCH 失聯，候選有 W1、W2〔BLIND〕與 WIDE〔OVERLAP〕）。每台各用自己的窗；不在允許集合的重疊鏡頭仍受 P-OV3 約束。
- 第二版 W1↔W2 是否核准仍由 G4 的 M1 決定（D90 不預先決定）；本規則只在轉移存在時適用。
- 長時間在共視區內「看丟又接上」（反覆暫失）不是本類事件：若漏檢觸發 SEARCHING 並切到另一台，那一次 SWITCH 落在任何 NO_SWITCH 或其他事件窗內時，依該事件規則判 miss；落在窗外則列窗外動作。

### 2.5 較長行走（A4-2／B4-2 類）

**事件定義。**同一 run 內串較長路線、更多事件。不新增事件類別；新增的是場次切分與搜尋次數預算。

**規則。**
1. **每個 Q2 場次一份劇本**（v1 本來就是一份 response 對一份劇本）。劇本帶 `session_query_range_us`；事件窗必須完整落在該場次的查詢範圍內，不跨場次。兩場次查詢範圍可以重疊，但重疊段不放事件（情境卡 A4-2）。
2. **每場次的搜尋次數預算**：`Σ 計畫 SEARCHING ≤ N_max − 2`（D67：≤ 4）。STANDARD SWITCH／RETURN 各計 1、NO_SWITCH 計 0、`LONG_GAP` 計 `n_s(g)`、`LONG_LOSS` 計 `n_ret_max(d)`。保留 2 輪給漏檢造成的計畫外搜尋。v1 情境卡用 ≤ 3（餘裕 3）；v2 放寬 1 輪，是為了讓一場次能容納一個 `g` ≤ 6.8 s 的 `LONG_GAP`（另列 §4 U-D10）。
3. **跨場次彙總**：新報告 `q5-switch-eval-aggregate.v1`，輸入是各場次報告的檔案 SHA-256；分子分母逐類相加，`event_id` 跨場次不得重複，同一 run／clock，列出每場次的 `uncovered_executed_actions`。不改單份報告的 schema。
4. NO_SWITCH 不放在場次最後（情境卡 S5，U7 未決）；場次頭尾規則同情境卡 S6。
5. 前提：Q2 支援 run 中途的顯式 seed 與限定查詢範圍（情境卡 Q7e；§5 C8）。

**計分。**各事件依自己的類別計分；彙總不加權（每事件 1 票）。

### 2.6 `ENDED_BY_LIMIT` 的部分評分（D90 未定，待使用者決定）

現行 v1：`freeze_output` 只接受 `COMPLETE`，`ENDED_BY_LIMIT`／`PARTIAL`／`NO_SEED`／`UNKNOWN` 在讀劇本之前就拒絕。

| 選項 | 內容 | 優點 | 缺點 |
| --- | --- | --- | --- |
| **E1 維持不評分** | v2 同 v1；adapter 用 §2.5 的預算避免 `ENDED_BY_LIMIT` | 最簡單；完全相容；不需要新契約 | 長 LOST 與 `LOST_TAIL` 都評不了；一次計畫外漏檢累積到上限，整場 0 資料 |
| **E2 前綴評分（建議）** | `freeze_output` 另接受 `status = ENDED_BY_LIMIT`（凍結順序不變，仍在讀劇本前驗 hash）。窗終點 ≤ 最後一筆決策 `source_time_us` 的事件照常評；之後的事件記 `COVERAGE_MISSING`。報告狀態另標 `MEASURED_PARTIAL_ENDED_BY_LIMIT`，比率與 COMPLETE 場次**分開列**，不併入主比率 | 用到已產生的決策；長 LOST 失敗時仍看得到前段結果；不改產品端 | 需要契約保證 ENDED_BY_LIMIT 的 response 帶完整 timeline／decisions（§5 C6）；有存活偏差（提早結束的場次跳過後段難事件）；報告多一個分母 |
| E3 預期上限事件 | 新事件類別 `LOST_TAIL`：目標永久離開後，預期結果是「只有 RETURN、沒有 SWITCH，直到 `ENDED_BY_LIMIT` 或查詢終點」。窗 `[max(t_prev_end, t_X − W), 查詢終點)`；`status ∈ {COMPLETE, ENDED_BY_LIMIT}` 且窗內 0 個 SWITCH 為正確 | 能測「人走了，系統不亂切」，這正是原 A4-d 的目的 | 依賴 U5（第 6 次何時結束）；只能放在場次最後，等於該場次後面不能有其他事件；與 E2 一起才有意義 |

建議 **E2**；E3 可在 E2 核定後另外加。PARTIAL（含 USER_STOPPED）、NO_SEED、UNKNOWN 在三個選項下都維持不評分。

---

## 3. 劇本 schema 草案 `q5-evaluation-script.v2`

```json
{
  "schema_version": "q5-evaluation-script.v2",
  "status": "PROPOSED",
  "approval_ref": null,
  "approval_content_sha256": null,
  "run_id": "…",
  "clock_id": "…",
  "session_query_range_us": [0, 48000000],
  "parameter_binding": {
    "parameter_set_id": "…",
    "parameter_set_sha256": "…",
    "index_interval_us": 200000,
    "link_max_gap_us": 600000,
    "search_window_us": 6000000,
    "research_interval_us": 1000000,
    "session_max_research_rounds": 6
  },
  "plan_ref": {"path": "…", "sha256": "…"},
  "events": [
    {
      "event_id": "A4-e",
      "action": "SWITCH",
      "event_class": "STANDARD",
      "plan_anchor_us": {"t_X": 26000000, "t_N_by_camera": {"CAM_EXT_CAR": 29000000, "CAM_EXT_CLEAR": 29400000}},
      "decision_window_us": [23000000, 30400000],
      "entry_windows_us": {
        "CAM_EXT_CAR":   {"kind": "BLIND", "range_us": [28400000, 30000000]},
        "CAM_EXT_CLEAR": {"kind": "BLIND", "range_us": [28800000, 30400000]}
      }
    },
    {
      "event_id": "OV-1",
      "action": "SWITCH",
      "event_class": "STANDARD",
      "plan_anchor_us": {"t_X": 40000000, "t_N_by_camera": {}},
      "decision_window_us": [34800000, 41800000],
      "entry_windows_us": {"CAM_WIDE": {"kind": "OVERLAP", "range_us": [40200000, 41800000]}}
    },
    {
      "event_id": "R-1",
      "action": "RETURN_TO_ORIGIN",
      "event_class": "LONG_LOSS",
      "plan_anchor_us": {"t_X": 50000000, "t_N": 52500000},
      "decision_window_us": [46500000, 53500000],
      "return_count_max": 2
    }
  ]
}
```

（數字只示範公式，不是劇本。A4-e 的 EXT_CLEAR 時刻是假設值。）

**欄位規則。**

| 欄位 | v1 | v2 |
| --- | --- | --- |
| `allowed_camera_ids` + `entry_window_us` | 必填 | **移除**，改 `entry_windows_us`（鍵＝允許鏡頭） |
| `event_class` | 無（隱含 STANDARD） | 必填：`STANDARD`／`LONG_GAP`／`LONG_LOSS`（`LOST_TAIL` 待 §2.6） |
| `plan_anchor_us` | 無 | 必填。SWITCH：`t_X` 與 `t_N_by_camera`（只列 BLIND 鏡頭）；RETURN：`t_X`、`t_N`；NO_SWITCH：`t_X` |
| `parameter_binding` | 無 | 必填；評分器用它重算窗與分類（§4 U-D5）。`parameter_set_sha256` 要與 response 綁定的參數組相同（§5 C7） |
| `session_query_range_us` | 無 | 必填；必須等於 response 的 `resolved_source_ranges_us` 之一 |
| `approval_content_sha256` | 無 | `APPROVED` 時必填（D79 U11：核定留言 URL＋固定內容 hash） |
| `return_count_max` | 無 | `LONG_*` 類必填，等於 §1 的公式值；評分器重算比對 |
| `plan_ref` | 無 | 劇本計畫檔的路徑＋hash（評估端專用，不給推論端） |

**評分器對 v2 劇本的驗證（失敗 → `EvaluationError`，不當 miss）：**依 `parameter_binding` 與 `plan_anchor_us` 重算每個事件的類別、`decision_window_us`、`entry_windows_us`、`return_count_max`，與劇本逐值相等；類別與計畫數字矛盾、超出 `G_max`／`D_max` 或場次預算、同一台鏡頭兩種 kind，都拒絕。

**實作方式（建議，§4 U-D8）。**
- 新模組 `src/amidst/evaluation/q5_switch_eval_v2.py`，`VERSION = 'q5-switch-eval-v2.0'`，報告 `q5-switch-eval-report.v2`。重用 v1 的 `freeze_output`（E2 時另加接受 ENDED_BY_LIMIT 的包裝，不改 v1 函式）。
- **`q5_switch_eval.py` 一個 byte 都不改。**v2 的入口收到 `q5-evaluation-script.v1` 時，直接呼叫 v1 的 `compare_script` 並原樣回傳。
- CLI 另開 `scripts/eval_q5_switch_v2.py`，旗標同 v1；彙總另開 `scripts/aggregate_q5_switch.py`。
- v2 報告在 v1 欄位之外加：`by_event_class`（各類 count／matched／ratio）、`standard_event_match_ratio`（只算 STANDARD 類，可與 Line 1 數字並列）、逐事件 `event_class`、`return_count`、`return_count_max`、`return_count_exceeds_max`、`searching_count`、`matched_camera_kind`，以及 §2.2 的範圍聲明。

---

## 4. 相容性（#244：v1 劇本與既有案例結果不變）

### 4.1 要保證的三件事

1. **v1 劇本經 v2 入口，報告與 v1 逐 byte 相同**（含 `output_sha256`、`scorer_version = q5-switch-eval-v1.1`）：v2 入口對 v1 schema 只做分派。
2. **v1 劇本「提升」成 v2 後，逐事件結果相同**：提升規則是 `event_class = STANDARD`、每台 `allowed_camera_ids` 對應同一個 `entry_window_us`、`kind = BLIND`。逐事件 `match`、`reason`、`observed`，以及 `event_match_ratio`、`by_expected_action`、`by_decided_by`、`uncovered_executed_actions` 都相等（報告 schema 不同，所以整份 hash 不同，但這些欄位相等）。提升後的劇本不帶 `plan_anchor_us` 時，不做 §3 的重算驗證（只有 v1 來源的提升劇本可以這樣，標 `lifted_from_v1_sha256`）。
3. **D79 公式在 STANDARD 範圍內不變**：§2.2 的 `LONG_GAP` 起點公式在 `g ≤ G1` 時等於 `t_N − W`；`LONG_LOSS` 窗就是 D79 RETURN 窗；BLIND 進入窗就是 D79 進入窗。

### 4.2 既有案例清單

| 案例 | 位置 | v2 預期 |
| --- | --- | --- |
| #222 單元測試 17 個測試函式（`test_q5_switch_eval.py`，部分參數化） | `origin/codex/q1q5-staging` @ `680ca35` | 原檔不改、照跑全過 |
| 同一批測試的 v1 劇本與凍結輸出 | 測試內建的最小布林／整數時間資料 | v2 入口回傳的報告 `output_sha256` 與 v1 相同；提升版逐事件欄位相同 |
| D79 表 P1-E1 推算（#211 工程參數 W 1.2 s、R 0.4 s） | D79 文件 §2 | 只是推算、沒有實跑輸出；用合成資料重建同一序列（RETURN 1.8–3.8 s、SWITCH 決策 4.2 s、進入 5.15 s，`t_N` 5.15）時，STANDARD 下 match、6 個 RETURN 列窗外，與 D79 文字一致 |
| D89 A4-1／B4-1 的 8 個事件（參考窗） | 情境卡 §2.1、§3.1 | 全部 `g` = 2.0–3.0 s，屬 STANDARD；v2 重算的決策窗與進入窗與卡上的參考值相同（A4-e 若兩台 `t_N` 相同，兩台的窗相同） |

正式 A4-1／B4-1 的凍結輸出與劇本目前不存在（#115 NONE），等它們存在後，再加一次「同一凍結輸出 × v1 劇本 × 提升版 v2 劇本」的比對。

### 4.3 驗證方式（給 Sonnet 的實作驗收）

```bash
git diff --exit-code origin/codex/q1q5-staging -- src/amidst/evaluation/q5_switch_eval.py tests/unit/test_q5_switch_eval.py scripts/eval_q5_switch.py
PYTHONPATH=src uv run --no-sync pytest tests/unit/test_q5_switch_eval.py
PYTHONPATH=src uv run --no-sync pytest tests/unit/test_q5_switch_eval_v2.py
git diff --check
```

新測試 `test_q5_switch_eval_v2.py` 至少包含：
- **相容 1**：對 v1 測試的每一組（凍結輸出, v1 劇本），v2 入口與 v1 `compare_script` 的報告逐 byte 相等。
- **相容 2**：同組資料的提升版 v2 劇本，逐事件欄位與比率相等。
- **公式**：§1 的 `n_r_max`、`n_ret_max`、`G_max`、`D_max` 表格值；`LONG_GAP` 起點在 `g = G1` 處連續；OVERLAP 窗 `[t_X + Δ, t_X + Δ + L + R)`。
- **計分**：`RETURN → RETURN → SWITCH` 在 LONG_GAP 判 match、在 STANDARD 判 miss；`SWITCH → RETURN` 與 `SWITCH → SWITCH` 在 LONG_GAP 判 miss；LONG_LOSS 窗內 3 個 RETURN 判 match、有 SWITCH 判 miss、超過上界時 `return_count_exceeds_max = true` 但 match 不變；依鏡頭進入窗「進入時刻落在另一台的窗」判 miss。
- **驗證**：類別與計畫數字矛盾、窗與重算值不符、超出場次預算、同台兩種 kind → `EvaluationError`；凍結驗證失敗時絕不開劇本（同 v1）。
- runtime 不 import v2 模組（同 v1 最後一個測試）。

---

## 5. 給 Codex 的契約問題（#248 L2-5 用，可直接貼上）

```text
@Codex：#248 L2-5（linker／Q5 controller：反覆暫失與 LOST 期限契約提案）需要回答的問題，來自 L2-1 評分規則設計稿
docs/evaluation/Q5_SWITCH_EVAL_V2_DESIGN.md（#244）。只回覆現行 controller／契約的行為與 v2 提案，不改 Line 1
（圖 v3、G4、D89、D79 範圍、#222）。D90 已定：產品端不加 LOST 狀態、不加 lost_after_us、不加 enum，D73 §14-27 不變。
每題回「現行行為＋條文／程式位置」或「UNKNOWN」，需要新條文的另列提案。

C1（U5）session_max_research_rounds：第一次 SEARCHING 算不算一輪？第 6 次 SEARCHING 是開始時就 ENDED_BY_LIMIT，
   還是做完（含決策紀錄、可能的 SWITCH）才結束？第 6 次若 SWITCH 成功，session 是否繼續？
C2 決策時刻相位：第一次 SEARCHING 的 decision_time_us 是 t_fm + link_max_gap_us，還是 t_fm + link_max_gap_us − Δ
   （情境卡 §1.3 記錄契約 §8.2 與 D79 推導差一格）？之後每次重搜是否恰好在 decision_time_us + k·research_interval_us，
   是否對齊索引格？
C3 每次重搜的紀錄：RETURNED_TO_ORIGIN 狀態下，每次重搜（候選窗沒有目標）是否都寫一筆 executed_action = RETURN_TO_ORIGIN、
   accepted = true 的決策紀錄？還是只在第一次寫 RETURN、之後的重搜寫別的 executed_action（例如 null 或 CONTINUE_SEARCH）？
   v2 的「一窗多次 RETURN」計數依賴這一題。
C4 長暫失後重新接上：目標在原鏡頭消失超過 link_max_gap_us 很久（例如 3 s）後回到畫面，linker 能否在 RETURNED_TO_ORIGIN
   直接接回（契約 §8.2「回原探針」、D78 的 600 ms 框中心平移是否仍適用）？若不能，是否必須等下一次重搜把原鏡頭當候選？
C5 圖 v4 的重疊轉移（EXT_CAR↔EXT_CLEAR、BRANCH↔WIDE，第二版 W1↔W2）：
   (a) 出口區怎麼畫？v2 規則需要原鏡頭在這條轉移的出口區邊緣 ≈ 原鏡頭可見範圍邊緣（P-OV2：最後可見時刻在 t_X 前一格內）。
   (b) 候選排序：重疊鏡頭與盲區鏡頭同一出口時的 tier 與順序？
   (c) 確認進入觀測是目的鏡頭第一筆 timestamp_us ≥ decision_time_us 的觀測，SWITCHING 等待不另加延遲。
C6 ENDED_BY_LIMIT 的回應：是否帶完整 timeline（涵蓋到結束時刻）、decisions、output_sha256 與 decisions_sha256，
   與 COMPLETE 同一 schema？結束那一刻是否寫一筆終止紀錄（source_time_us = 結束時刻）？COMPLETE 時是否有
   source_time_us = 查詢終點的紀錄（U7）？
C7 參數綁定：response 或 resolved_scope 是否帶 parameter_set_id／parameter_set_sha256，讓評估劇本 v2 的 parameter_binding
   能比對？若沒有，請提出欄位位置。
C8 分場次（情境卡 Q7e）：Q2 能否用 run 中途的顯式 observation 當 seed，並限定查詢範圍？兩個場次的 session_id、
   resolved_source_ranges_us 如何表示？
C9 反覆暫失：同一鏡頭內 PLAYING ↔ TEMP_LOST 反覆（每次 < link_max_gap_us）時，是否有任何計數或狀態累積？
   重新接上後 session_max_research_rounds 的累計是否一律不重置（確認）？
C10 searching_index：同一次 SEARCHING 的所有決策紀錄是否同值、跨 SEARCHING 嚴格遞增、RETURN 紀錄也帶此值？
   v2 報告用窗內 searching_index 的相異值數當 searching_count。
回覆請附「實際產出 / Actual output」。
```

---

## 6. UNKNOWN 與待使用者決定

### 6.1 待使用者決定（每項附選項；第一個是建議）

| # | 項目 | 選項 | 優點 | 缺點 |
| --- | --- | --- | --- | --- |
| U-D1 | LONG 類的多 RETURN 計分樣式（§2.1） | **M1 `RETURN* → SWITCH`**（恰一個 SWITCH、在最後） | 機械性 RETURN 不扣分；錯切、多切仍抓得到 | 是 D79 未採用的 (c) 的嚴格版，要新決定才能用（只用在 v2 LONG 類） |
| | | M2 M1＋RETURN 次數 ≤ `return_count_max` 才算正確 | 更嚴，抓到重新接上失敗 | 依賴 C2 的相位；相位差一格就誤判 |
| | | M3 只看窗內最後一個動作 | 最簡單 | 前面的錯切被掩蓋，違反 v1「多次 SWITCH 不被掩蓋」 |
| U-D2 | LONG_LOSS 的 RETURN 次數上限 | **不影響 match，只報告 `return_count_exceeds_max`** | 不依賴 C2／C3 未定的行為 | 重新接上失敗的情況仍算正確 RETURN，要讀報告細項才知道 |
| | | 超過上限判 miss | 一個數字就看得出 | 依賴 C2、C3；相位誤差會誤判 |
| U-D3 | 重疊對的進入窗（§2.4） | **O1 `t_N* = t_X + Δ + L` 代入 D79** | 不新增數字、窗寬與 BLIND 相同；只用計畫的 `t_X` | 提早失聯只容許 0.4 s；需要 v4 出口區對齊可見邊緣（C5a） |
| | | O2 進入窗起點放寬到目的鏡頭 `t_V` | 任何提早失聯都不扣 Q5 | 窗可能很寬；`t_V` 來自靜態校正投影，第一次把它放進分數（情境卡 §1.8 目前只當通過／不通過） |
| | | O3 錨點改用原鏡頭最後可見 `t_L` | 不依賴出口區畫法 | 同 O2：校正投影時刻進分數；GT 邊界要再確認（D79 U2） |
| U-D4 | `ENDED_BY_LIMIT` 部分評分（§2.6） | **E2 前綴評分、分開列** | 用到已有資料；不改產品端 | 需要 C6；存活偏差 |
| | | E1 維持不評分 | 最簡單、相容 | 長 LOST 與 LOST_TAIL 評不了 |
| | | E3 預期上限事件（可與 E2 並用） | 能測「人走了不亂切」 | 依賴 U5（C1）；只能放場次最後 |
| U-D5 | 評分器是否重算窗與分類 | **重算並比對，不符就拒絕** | adapter 錯誤不會變成分數；窗來源可追溯 | 評分器與 adapter 共用公式，改公式要兩邊一起升版 |
| | | 只信劇本給的窗（同 v1） | 評分器簡單 | 分類錯的事件會被當 miss 或錯誤地當 match |
| U-D6 | 早可見盲區（§2.3） | **adapter 拒絕這種計畫**（同情境卡 v1） | 不新增規則；保持 BLIND 窗單純 | 某些路線（EXT_CAR 看得到 VEST_W）不能用 |
| | | BLIND 窗錨點改用 `min(t_N(c), t_V(c) + L)` | 路線較自由 | 校正投影時刻進分數（同 O2 缺點） |
| U-D7 | 主比率怎麼報 | **總比率＋`standard_event_match_ratio`＋各類分列** | 可與 Line 1 數字直接比；新類別不稀釋 | 報告欄位多 |
| | | 只報總比率 | 簡單 | 與 Line 1 不可比 |
| U-D8 | 實作位置 | **新模組 `q5_switch_eval_v2.py`，v1 不動** | 相容性可以用 `git diff --exit-code` 證明 | 兩份程式，共用部分要 import v1 |
| | | 擴充 v1 模組 | 一份程式 | v1 檔 hash 改變，Line 1 引用的 SHA 失效 |
| U-D9 | LONG_GAP 決策窗起點（§2.2） | **夾住公式 `min(t_N_min, t_X + G1) − W`** | 事件自己的 RETURN 全歸自己；`g ≤ G1` 時等於 D79 | 新公式（仍只用既有參數） |
| | | 沿用 D79 `t_N − W` | 不新增公式 | `g > 6.8 s` 時前幾個 RETURN 變窗外動作；`g` 在 5.2–6.8 s 時第一個 RETURN 在窗內，要靠 M1 吸收 |
| U-D10 | 每場次計畫 SEARCHING 預算（§2.5） | **≤ `N_max − 2`（4）** | 一場次能放一個 `g` ≤ 6.8 s 的 LONG_GAP | 計畫外漏檢的餘裕由 3 輪降為 2 輪 |
| | | ≤ 3（同情境卡 v1） | 餘裕較大 | LONG_GAP 幾乎都要獨占一場次 |

### 6.2 UNKNOWN（等 Codex 或資料）

| # | 項目 | 誰 | 影響 |
| --- | --- | --- | --- |
| U5 | 第一次 SEARCHING 是否算一輪、第 6 次何時結束 | Codex（C1） | `G_max`、`D_max`、E3 |
| UK-1 | 決策時刻相位（`t_fm + L` 或早一格）、重搜是否對齊格點 | Codex（C2） | `n_r_max`、`n_ret_max` 的 ±1；OVERLAP 窗早側 |
| UK-2 | 每次重搜是否都寫一筆 accepted RETURN | Codex（C3） | 多 RETURN 樣式的計數；若不寫，LONG_LOSS 只會看到 1 個 RETURN，規則仍成立但 `return_count` 意義改變 |
| UK-3 | 長暫失後能否直接接回原鏡頭 | Codex（C4） | LONG_LOSS 是否可行 |
| UK-4 | 圖 v4 重疊轉移的出口區畫法與候選順序 | Codex（C5） | P-OV2、O1 是否可用 |
| UK-5 | ENDED_BY_LIMIT 回應內容、終止紀錄（含 U7） | Codex（C6） | E2、E3、NO_SWITCH 覆蓋 |
| UK-6 | response 是否帶參數組 hash | Codex（C7） | U-D5 的重算驗證 |
| UK-7 | run 中途 seed、分場次表示 | Codex（C8） | §2.5 |
| UK-8 | `t_V`、`t_L` 能否只由計畫路線＋靜態校正得到（不用 renderer visibility） | Codex 說明；使用者決定（D79 U2） | P-OV1、P-OV2；O2／O3 |
| UK-9 | 新場景（#245 情境卡 v2）是否真的有 `g` > 5.2 s、`d` ≥ 1.8 s 的路線 | Claude（#245）＋Codex 可行性 | LONG 類是否有實際事件可評 |
| UK-10 | #247 漏檢診斷的結果 | Codex（D1） | 計畫外搜尋的頻率，決定 U-D10 的餘裕夠不夠 |

---

## 7. 來源

**決定（GitHub 留言）**
- D90：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423575212 （LOST 評估端分類、5.2 s／1.8 s 邊界；失聯後接手、v4 加重疊轉移；第一批範圍）
- D89：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423194857 （A4-1＋B4-1；NO_SWITCH 讓位）
- D87：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6421557959 （第二條線）
- D79：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6398981572 （方案一公式、K1 範圍聲明）
- D67、D65、D73、D77、D78：見 D79 文件 §5 的連結。

**檔案（路徑＋commit＋bytes SHA-256）**
- 評分器：`src/amidst/evaluation/q5_switch_eval.py` @ `origin/codex/q1q5-staging` `680ca357a31b664bed3feb6a5284dcd7c5c0d94d`（最後修改 `362a87c`），`0fd1ef68c4c83443e8311723224b76f103c142dd018275e7c1596f917e85d9f2`
- 評分器文件：`docs/evaluation/Q5_SWITCH_EVAL_V1.md` 同 commit，`8457b2849b926b8534b1e43f71c98729f92ccd0320c2c73a89a78fe7ba6008cf`
- 測試：`tests/unit/test_q5_switch_eval.py` 同 commit，`786059034fe870c093d04d87d502422cc12b8ba4313768d29b20620c8a504e24`
- CLI：`scripts/eval_q5_switch.py` 同 commit，`c8e1c37438f89cbdf558454107f6dd2d99874ec6b1a1425871fb4b6cb622304f`
- D79 文件：`docs/evaluation/Q5_DECISION_WINDOW_D79.md` @ `origin/mainline/q1q5` `2675c215d27424afcc77018cbcc6fe1afd3d7a42`，`7010ca5560b2ca71f35b1f86f87cc0d0b671a6af176065da04fbafeb4a9a6f43`
- 情境卡 v1：`docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md` @ `origin/claude/r004-a4b4-scenario-cards` `7554dc60267f51cceda1d9a4abb61d115a586574`，`77372a1e38ae266dcfe505f00975f6da66564f96d449c0f7460f1f5f4b5d60d3`（§1.3 `t_L`／`t_V`、§1.4 S1–S6、§1.7、§5）
- 契約：`docs/contracts/Q1_Q2_FIRST_DEMO_V1.md` @ `680ca35`，`b700bf86041f4853ae37dd54bbc9d93199a07be3d5d3c87bc8c2f6455570df04`（§8.6 狀態機、決策時刻、兜底規則；§8.7 status 清單、`searching_index`）

**議題**：#244（本稿）、#248（L2-5 契約）、#251（第二條線總覽）、#245（情境卡 v2）、#247（漏檢診斷）。

**沒有用到、也沒有讀的來源：**GT、renderer 軌跡／visibility／depth、任何 RGB、`.blend`、#211 private producer。
