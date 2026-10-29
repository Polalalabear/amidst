# Q5 評分規則 v2 設計稿（L2-1，#244）

日期：2026-10-27｜起草：Claude（評估端，D75／D87／D90）｜Model / effort：Claude Opus 5.5 / high

回修：2026-10-29，CQ-30（#322）｜Model / effort：GPT-6（Codex） / UNKNOWN。僅修本設計文件，未改程式或代選待決項。

## 狀態

**PROPOSED，待使用者核定。**本文件只寫規則，不含程式。依 D97，#324 可先做待決值可設定、預設 fail closed 的實作；任何建議值都不是使用者核准。已定案的例外僅採 D93／D94，D98-6 只確認待決清單的對應（§6.3）。

- 只作用在第二版（D90 第 4 項第一批）。**Line 1 已核定範圍不變**：圖 v3、G4、D89 的 A4-1／B4-1、D79 的範圍聲明、#222 評分器（`q5_switch_eval.py`，`q5-switch-eval-v1.1`）、`q5-evaluation-script.v1`。
- 所有窗都由 D79 的四個參數 `W`、`R`、`L`、`Δ` 導出，不新增數字。下文的「5 fps、D67 代入值」只是參考；正式值由評估端依固定 hash 的劇本與綁定的 parameter_set 算出。
- 沒有讀 GT、renderer 軌跡、visibility、depth、RGB 或 `.blend`。本次依 J2、#266 C1–C10 與決定原文逐步驗算 §1.4，不把舊相位的歷史模擬結果當成本次驗證；沒有執行 controller 或模型。

### 參數（全部沿用，D79 §1.1）

| 符號 | 意思 | 5 fps、D67 值 | 來源 |
| --- | --- | ---: | --- |
| `Δ` | 索引格距 `index_interval_us` | 0.2 s | D65、D68 |
| `L` | `link_max_gap_us`（`elapsed_us ≥ L` 進 SEARCHING） | 0.6 s | D65；契約 §8.2、§11；D78 |
| `W` | `search_window_us`（候選窗固定長度，Q-05） | 6.0 s | D67；契約 §8.6 |
| `R` | `research_interval_us`（回原鏡頭後每隔 R 重搜） | 1.0 s | D67；契約 §14-13(a) |
| `N_max` | `session_max_research_rounds`（第 N 次照常決策，企圖第 N+1 次才 `ENDED_BY_LIMIT`） | 6 | D67；#266 C1、C10 |

時刻符號沿用 D79 §1.2：`t_X`（依計畫離開原鏡頭出口 footprint）、`t_N`（依計畫第一次進入目的鏡頭入口 footprint；RETURN 類是重新進入原鏡頭可見區）、`t_prev_end`（前一事件決策窗終點）。本稿另用：

| 符號 | 定義 | 來源 |
| --- | --- | --- |
| `g` | SWITCH 計畫空檔 `t_N − t_X`（依鏡頭時寫 `g_c = t_N(c) − t_X`） | 劇本計畫 |
| `d` | RETURN 計畫暫失 `t_N − t_X` | 劇本計畫 |
| `t_N(c)` | 允許目的鏡頭 c 的入口 footprint 進入時刻（§2.3） | 劇本計畫 |
| `t_N*` | 重疊接手的「等效進入時刻」`t_X + L`（§2.4） | D93 的 O1；由 `t_X` 與參數導出 |
| `G1` | 第一版 SWITCH 空檔上界 `W + Δ − R` ＝ 5.2 s | D79「K1 門檻推導」 |
| `D1` | 第一版 RETURN 暫失上界 `Δ + L + R` ＝ 1.8 s（開區間） | D79；D90 第 1 項 |

D90 的分類邊界仍是 G1=5.2 s、D1=1.8 s。Line 2 原生計畫另依 D94：STANDARD RETURN 只收 `d ≤ L+R`（1.6 s），`L+R < d < D1` 事前拒絕；不修改 Line 1 或 v1 輸入的既有範圍。

---

## 0. 摘要

| # | 情境（D90 第一批） | 事件類別 `event_class` | 預期動作 | 窗（相對 v1 的改變） | 計分重點 |
| --- | --- | --- | --- | --- | --- |
| 1 | 一窗多次 RETURN | `LONG_GAP`、`LONG_LOSS` 共用的計分樣式 | — | — | 窗內允許「機械性 RETURN」；SWITCH 窗的樣式是 `RETURN* → SWITCH` |
| 2 | 長時間 LOST | `LONG_GAP`（SWITCH，`g > G1`）、`LONG_LOSS`（RETURN，`d ≥ D1`）；`LOST_TAIL` 待決 | SWITCH／RETURN／NO_SWITCH | `LONG_GAP` 決策窗起點改為夾住的公式；其他沿用 D79 | 依計畫數字分類；超過搜尋次數上限的事件不評分 |
| 3 | 依鏡頭分別給進入窗 | 任何 SWITCH | SWITCH | `entry_windows_us` 每台一窗 | 相機在 map 的鍵中，進入時刻在該台的窗內 |
| 4 | D77／D90 重疊接手 | `OVERLAP` 進入窗（掛在 SWITCH 事件的單台鏡頭上） | SWITCH | D93：用 `t_N* = t_X + L` 代入 D79 公式 | 只評已有出口條帶的 EXT_CAR↔EXT_CLEAR；另列 `OVERLAP_P_OV2_UNVERIFIED`，不併主比率 |
| 5 | 較長行走（A4-2／B4-2 類） | 不新增類別 | — | 每場次一份劇本 | 跨場次彙總報告；每場次計畫 SEARCHING 次數上限 |

分類由劇本計畫的數字決定；是否由評分器重算並驗證仍是 U-D5 待決。建議的 `STANDARD` 動作比對與 BLIND 窗沿用 v1；Line 2 計畫准入須加 D94 的 RETURN 限制。這不會重寫 v1 的窗公式或既有接受範圍。

---

## 1. 系統行為推導（評分規則的依據）

以下沿用 D79 的理想失聯假設：最後成功觀測在 `t_X`，第一個沒接上的索引格 `t_fm = t_X + Δ`。依 #266 C2，第一次 SEARCHING 的決策時刻固定為 `t_s0 = t_fm + L − Δ = t_X + L`（5 fps、D67：`t_X + 0.6 s`），不是尚待選擇的產品相位。只有理想可用觀測／合法 guard 的計畫假設成立時，下面的次數推導才適用；不等於實際 detector 品質保證。

- 第 0 次搜尋的候選窗：`[t_X + Δ, t_X + Δ + W)`（契約 §8.6、§14-18(a)）。修正決策相位不會把這個窗口的 Δ 刪掉。
- 第 k 次（k ≥ 1）重搜在 `t_k = t_s0 + k·R`，候選窗 `[t_k, t_k + W)`（D79 §1.1）。
- 首次 SEARCHING 算第 1 輪；第 N_max 次照常產快照／決策，可以 SWITCH 並繼續追蹤。只有企圖開始第 N_max+1 次才 `ENDED_BY_LIMIT`，不產該次快照；終止紀錄沿用 N_max。恢復／切換／人工選擇不退還已消耗輪數（#266 C1、C9、C10）。

### 1.1 長空檔 SWITCH 的 RETURN 次數

最差情況下進入觀測落在進入窗最後一格 `t_N + R − Δ`（D79 推導同一假設）。第 k 次搜尋能看到這一格的條件：
- k = 0：`t_N + R − Δ ≤ t_X + W`，即 `g ≤ W + Δ − R = G1`（D79）。
- k ≥ 1：`t_N + R − Δ ≤ t_k + W − Δ`，代入 `t_k=t_X+L+kR` 得 `g ≤ W + L + (k − 1)·R`。

所以 SWITCH 前的 RETURN 次數上界：

```
n_r_max(g) = 0                                         若 g ≤ G1
           = max(1, ⌈(g − (W + L)) / R⌉ + 1)            若 g > G1
```

SEARCHING 次數 `n_s(g) = n_r_max(g) + 1`。D67 代入：

| g (s) | ≤ 5.2 | (5.2,6.6] | (6.6,7.6] | (7.6,8.6] | (8.6,9.6] | (9.6,10.6] | > 10.6 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RETURN 上界 | 0 | 1 | 2 | 3 | 4 | 5 | ≥ 6 |
| SEARCHING | 1 | 2 | 3 | 4 | 5 | 6 | ≥ 7（超過 `N_max`） |

`n_s(g) ≤ N_max` 的最大空檔 `G_max = W + L + (N_max − 2)·R` ＝ **10.6 s，含端點**（整個 session 只有這一個事件時；有其他事件時更短，§2.5）。在端點第 6 次成功決策仍可切換；超過才需要第 7 次。

### 1.2 長暫失 RETURN 的 RETURN 次數

在理想、唯一合法目前候選可於 t_N 當格恢復的假設下，目標回到原鏡頭之前，每個 tick `t_s0 + k·R < t_N` 都會 SEARCHING → RETURN。回原狀態每個 index tick **先 probe 原鏡頭，再判是否重搜**；若恢復與重搜同格，先恢復，不再新增該次 SEARCHING（#266 C4）。

```
n_ret(d) = n_ret_max(d) = max(0, ⌈(d − L) / R⌉)
```

例如 d=1.6 s 時只在 0.6 s RETURN，1.6 s 當格 probe 先恢復；d=1.8 s 時已有 0.6、1.6 s 兩次 RETURN，所以 D94 拒絕兩者中間的 `(1.6,1.8)` s 計畫，而 D90 的 1.8 s 分類線不動。`n_ret_max(d) ≤ N_max` 的條件是 `d ≤ L + N_max·R` ＝ **6.6 s，含端點**（`D_max`）。d=6.6 s 時 0.6–5.6 s 六次 RETURN，6.6 s 先恢復，不企圖第 7 次；d=6.8 s 則在 6.6 s 企圖第 7 次而終止。這是理想 guard 假設下的計畫上界，不保證漏檢時也成功恢復。

### 1.3 重疊接手的進入時刻

D90 第 2 項：重疊對也要原鏡頭失聯、進 SEARCHING 後才可切；進入觀測取目的鏡頭 `timestamp_us ≥ decision_time_us` 的**最早合法 guard 觀測**，還要滿足窗口、可用範圍、person／score／color 條件（#266 C5）。不能取任意第一格；SWITCHING 不額外配置延遲，entry 較晚時保留 GAP。理想情況在決策時刻已經有合法觀測，所以：

- O1 名目錨點是 `t_X + L`（＝ `t_N*`，D93）；實際 entry 仍由最早合法 guard 決定，不能由此計畫錨點代填觀測。
- 計畫的 `t_N`（進入目的鏡頭入口 footprint）與目的鏡頭第一次可見 `t_V` 都**早於** `t_X`。v1 情境卡 §1.3 的條件 `t_V ≥ t_N − L` 與 D79 進入窗 `[t_N − L, t_N + R)` 對重疊對必然不成立：進入觀測取決於原鏡頭何時失聯，而不是目標何時走進目的鏡頭。
- 只要候選窗內目的鏡頭看得到目標，第 0 次搜尋就 SWITCH，只預期 1 個動作，沒有 K1 問題。

### 1.4 J2 反例與端點逐步驗算（F1 已修）

固定 Δ=0.2 s、L=0.6 s、R=1 s、W=6 s、t_X=0、g=6.8 s，最晚合法 entry=`t_N+R−Δ=7.6 s`：

| 搜尋（session index） | 決策時刻 | 候選窗（半開） | entry 7.6 s 是否在窗內 | 動作 |
| --- | ---: | --- | --- | --- |
| 首次（1；k=0） | 0.6 s | [0.2,6.2) s | 否 | RETURN@0.6 |
| 重搜（2；k=1） | 1.6 s | [1.6,7.6) s | 否，右端不含 | RETURN@1.6 |
| 重搜（3；k=2） | 2.6 s | [2.6,8.6) s | 是 | SWITCH@2.6，entry@7.6 |

公式給 `n_r_max=max(1,ceil((6.8−6.6)/1)+1)=2`，`n_s=3`，符合上述序列。g=6.6 s 時最晚 entry=7.4 s，第二窗可收，只有一次 RETURN；g=10.6 s 時第五次重搜（session index 6）可收，之後不必開始第 7 輪。RETURN 的 d=6.6／6.8 s 端點則見 §1.2。這是依已交件行為條文與 J2 trace 的手算，沒有重跑 controller、模擬器或模型。

---

## 2. 五類情境的規則

共通規則（全部沿用 v1／D79，不重述細節）：
- 時間一律來源微秒、半開區間；決策窗依序、不重疊、在 `resolved_source_ranges_us` 內；與相鄰窗重疊時截斷，NO_SWITCH 讓位（D89 第 3 項：「下一窗起點」取下一事件未截斷的起點）。
- 只看已執行動作（accepted SWITCH、accepted RETURN_TO_ORIGIN），以 decision_id 綁 timeline；窗外動作列 `uncovered_executed_actions`。
- 相機正確不代表同一人（UNCONFIRMED）；Agent／fallback 只轉錄。

### 2.1 一窗多次 RETURN（計分樣式）

**事件定義。**`LONG_GAP`（SWITCH）與 `LONG_LOSS`（RETURN）兩類事件的決策窗內，會依凍結的搜尋機制出現多個 RETURN（§1.1、§1.2）。這些 RETURN 是 Q-05 固定窗與 R 節奏的機械結果，不是錯誤。

**計分（建議 M1，§6.1 U-D1）：**

| 事件類別 | 正確（match = true） | miss（match = false） | 不評分（match = null） |
| --- | --- | --- | --- |
| `LONG_GAP`（SWITCH） | 窗內已執行動作依時間排序為 `RETURN_TO_ORIGIN* → SWITCH`：恰一個 SWITCH、它是窗內最後一個動作、相機與進入時刻符合 §2.3／§2.4 | 窗內 0 個 SWITCH；≥ 2 個 SWITCH；SWITCH 之後還有動作；相機或進入時刻不符 | 依 §2.6 的 `ENDED_BY_LIMIT` 決定 |
| `LONG_LOSS`（RETURN） | 窗內至少 1 個動作，而且全部是 `RETURN_TO_ORIGIN`（0 個 SWITCH） | 窗內有任何 SWITCH；窗內 0 個動作 | 同上 |
| `STANDARD`（v1） | SWITCH／RETURN沿用v1恰一個動作；NO_SWITCH另按v1的無SWITCH與覆蓋檢查 | v1 規則原樣 | v1 規則原樣（NO_SWITCH 的 `COVERAGE_MISSING`） |

- 「≥ 2 個 SWITCH 判 miss」沿用 v1「多次 SWITCH 不被第一個正確動作掩蓋」。
- **建議（U-D2未核）**：RETURN 次數不影響 match，逐事件報 return_count／return_count_max（n_r_max或n_ret_max）及 return_count_exceeds_max。超過理想上界另列重新接上失敗／額外漏檢，不在本類扣分；是否採用仍由§6.1 U-D2選擇。
- `searching_count`（F2 已修）：先在同 session 完整已驗證 journal 中，識別每個**正整數 searching_index 首次真正開啟該輪 SEARCHING 的 start 紀錄**，再依該 start 的 source_time 是否在事件半開窗內取 distinct。不能對窗內所有紀錄直接 distinct；idx=0、同輪 completion／RETURN／ENDED 沿用的 index 都不加次。USER manual override 可能是 SEARCHING→SEARCHING 的新一輪，不可用 `state_before != SEARCHING` 一律排除；USER starts／actions 另列來源（#266 C10）。

**邊界。**
- 只有 LONG_GAP／LONG_LOSS 類提議套用多RETURN樣式；STANDARD SWITCH／RETURN窗內兩個RETURN仍判miss。NO_SWITCH維持原v1的無SWITCH與覆蓋規則，不被此處改寫。
- 類別由計畫數字決定，不由觀察到的動作數決定：不能因為系統多 RETURN 了，就把 STANDARD 事件事後改成 LONG 類。

### 2.2 長時間 LOST（分類與窗）

**事件定義（D90 第 1 項）。**評估端分類，產品端不加狀態、不加 `lost_after_us`、不加 enum（D73 §14-27 不變）。

| 類別 | 條件（計畫數字） | 預期動作 | 可評上界 |
| --- | --- | --- | --- |
| `STANDARD` SWITCH | 所有 BLIND 鏡頭 `g_c ≤ G1`（5.2 s） | SWITCH | — |
| `LONG_GAP` | 至少一台 BLIND 鏡頭 `g_c > G1`，且 `n_s(max_c g_c) ≤ 本場次可用輪數`（§2.5） | SWITCH | `g ≤ G_max`（單一事件時 10.6 s，含端點） |
| `STANDARD` RETURN | Line 2 計畫 `d ≤ L+R`（1.6 s，含端點；D94） | RETURN | `(L+R,D1)` 事前拒絕；不改 v1 |
| `LONG_LOSS` | `d ≥ D1`，且 `n_ret_max(d) ≤ 本場次可用輪數` | RETURN | `d ≤ D_max`（單一事件時 6.6 s，含端點） |
| 超出上界 | `n_s` 或 `n_ret_max` 超過本場次可用輪數 | — | **adapter 拒絕放進劇本**（預期 `ENDED_BY_LIMIT`，整場不評分） |
| `LOST_TAIL` | 目標離開所有渲染鏡頭、查詢範圍內不再出現（原 A4-d） | NO_SWITCH | **待決**，見 §2.6 選項 E3 |

邊界依 D90：`g = 5.2 s` 屬 `STANDARD`；`d = 1.8 s` 屬 `LONG_LOSS`。

**窗公式。**

- `LONG_LOSS` 決策窗：**沿用 D79 RETURN 窗** `[max(t_prev_end, t_N − W), t_N + R)`。`d ≤ D_max` 時 `t_N−W ≤ t_X+L`，第一個 RETURN（名目 `t_X+0.6 s`）在未被前窗截掉的本窗內；等於左端也計入。若相鄰窗截斷會排掉它，adapter 仍須拒絕該計畫，不能宣稱所有 RETURN 都已歸本事件。
- `LONG_GAP` 決策窗（新）：

  ```
  start = max(t_prev_end, min(t_N_min, t_X + G1) − W)
  end   = t_N_max + R
  ```

  `t_N_min`／`t_N_max` 是所有允許鏡頭進入時刻的最小／最大值（§2.3；OVERLAP 鏡頭用 `t_N*`）。`g ≤ G1` 時 `start = t_N − W`，與 D79 完全相同；`g > G1` 時起點固定在 `t_X + G1 − W = t_X + Δ − R`（D67：`t_X − 0.8 s`），把這個事件自己的第一個 RETURN（`t_X + L`）收進窗內。此處 G1 仍含 Δ，公式在 `g = G1` 處連續；新起點是否採用仍是 U-D9。
- `LONG_GAP` 進入窗：D79 原式，每台各自（§2.3）。

**為什麼建議 `LONG_GAP` 不直接用 D79 起點 `t_N − W`：**`5.2 < g ≤ 6.6 s` 時第一個 RETURN 在 D79 窗內；`g > 6.6 s` 時它開始落在窗外。新起點讓同一事件的 RETURN 歸這個事件；採用與否仍由 U-D9 決定，不是產品端規則變更。

**邊界與相鄰事件。**
- 起點早於 D79 窗，所以相鄰間距規則要重算：前一事件窗終點 `e_{k−1}` ≤ `t_X(k) + Δ − R` 才不截斷（取代情境卡 §1.4 S2 對 LONG_GAP 的寫法）；截斷時仍要 `e_{k−1}` ≤ `t_X(k) + L − δ`（情境卡 S1，δ 為允許的提早失聯，卡內 1.2 s），否則本事件的第一個 RETURN 會落進上一窗。
- 若前一窗是 NO_SWITCH，依 D89 第 3 項讓位：NO_SWITCH 終點取本事件未截斷的起點。
- 報告的範圍聲明（v2 提議）：「本版計畫上界 `g ≤ G_max`、`d ≤ D_max`，且不得超過本場次可用搜尋次數；D94 的 STANDARD RETURN 只收 d≤1.6 s、拒絕 1.6<d<1.8 s。STANDARD 的動作比對／BLIND 窗沿用 v1，LONG 類多 RETURN 樣式仍待核定。D93 的 OVERLAP 結果另列、不併主比率。」代入值須隨凍結參數列出；Line 1 範圍聲明不變。

### 2.3 依鏡頭分別給進入窗

**事件定義。**一個 SWITCH 事件允許多台目的鏡頭時（例：{EXT_CAR, EXT_CLEAR}、{BRANCH, WIDE}、{W1, W2}），各台的入口 footprint 進入時刻 `t_N(c)` 可能不同。v1 只有一個 `entry_window_us`，情境卡 §1.3 因此要求兩台 `t_N` 差 ≤ 0.8 s、取較早者。v2 改為每台一窗。

**窗公式。**

| 進入窗種類 `kind` | 用於 | 公式 |
| --- | --- | --- |
| `BLIND` | 盲區後進入（v1 的唯一種類） | `[t_N(c) − L, t_N(c) + R)`（D79 原式，各台用自己的 `t_N(c)`） |
| `OVERLAP` | D93 限定重疊接手（§2.4） | `[t_N* − L, t_N* + R)` ＝ `[t_X, t_X + L + R)` |

決策窗終點取 `max_c` 的進入窗終點，起點用 §2.2 的公式（`STANDARD` 時等於 `max(t_prev_end, min_c t_N(c) − W)`）。

**計分。**
- 正確：（依類別的動作樣式成立，且）SWITCH 的 `camera_id` 是 `entry_windows_us` 的鍵之一，`entry_time_us` 落在**該台**的窗內。
- miss：相機不在鍵中；或相機在鍵中但進入時刻不在該台的窗（即使落在另一台的窗內）。
- 不評分：同 v1／§2.6。

**邊界與檢查（adapter 事前拒絕）。**
- `STANDARD` 類要求每台 BLIND 鏡頭 `g_c ≤ G1`；任一台超過，整個事件歸 `LONG_GAP`。
- BLIND 鏡頭仍要通過情境卡 §1.3 的 `t_V(c) ≥ t_N(c) − L` 與 `t_L ≤ t_N(c) − 1.0 s`（只當通過／不通過，不進分數；情境卡 §1.8）。「兩台 `t_N` 差 ≤ 0.8 s」的限制在 v2 取消。
- 「早可見盲區」（`t_L < t_V(c) < t_N(c) − L`，目的鏡頭在入口區之前就看到人，但原鏡頭已看不到）不是重疊、也不符 BLIND 窗：v2 預設**仍拒絕這種計畫**（§6.1 U-D6）。
- 同一台鏡頭不得同時有 BLIND 與 OVERLAP 兩種窗。

### 2.4 重疊對的失聯後接手

**事件定義（D90 第 2 項；D93 限定）。**BRANCH／WIDE 出口仍 MISSING 期間，Line 2 只評已有出口條帶的 EXT_CAR↔EXT_CLEAR；W1↔W2 等 G4 的 M1，不能從圖中有轉移就自行納入。原鏡頭失聯、進 SEARCHING 後才接手；進入取決策時刻之後的最早合法 guard 觀測，不是任意第一格。

- `t_X`：依計畫離開**原鏡頭在這條重疊轉移上的出口 footprint**的時刻。v4 必須把重疊轉移的出口區放在原鏡頭可見範圍的邊緣，使 `t_X` 等於「原鏡頭最後可見」的計畫時刻（容許一格，P-OV2）。v4 出口區怎麼畫屬 Codex（§5 C5）。
- 不用 `t_N`、`t_V` 當錨（兩者都早於 `t_X`，§1.3）。

**窗公式（O1 已由 D93 定案：把 `t_N* = t_X + L` 代入 D79，U-D3 不再待選）：**

| 窗 | 公式 | D67 代入 |
| --- | --- | --- |
| 決策窗 | `[max(t_prev_end, t_N* − W), t_N* + R)` | 未截斷時 `[t_X − 5.4, t_X + 1.6)`，寬 7.0 s |
| 進入窗（OVERLAP） | `[t_N* − L, t_N* + R)` ＝ `[t_X, t_X + L + R)` | `[t_X, t_X + 1.6)`，寬 1.6 s、8 格 |

- 早側接受區間從 `t_X` 起；是否 match 依實際最早合法 guard 的 entry_time，不能只由計畫 δ 推定。P-OV2 的 `t_L∈[t_X−Δ,t_X]` 仍未驗，不宣稱額外提早失聯容忍已實測。
- 晚側 `+ R`：目的鏡頭偵測晚到，沿用 D79 的晚側容忍 R。
- 窗寬與 D79 BLIND 窗相同（`L + R`），只是錨點換成 `t_N*`。

**計分。**
- 正確：窗內恰一個已執行動作（`STANDARD`），它是 SWITCH，`camera_id` 是 OVERLAP 鍵，進入時刻在 OVERLAP 窗內。
- miss：切到別台、entry_time `<t_X` 或 `≥t_X+L+R`、窗內有 RETURN 或第二個動作。
- 不評分：同 v1／§2.6。

**D93 報告隔離。**本類結果標 `OVERLAP_P_OV2_UNVERIFIED`，分子／分母單獨列出，**不併入主比率，也不併入與 Line 1 並列的 standard_event_match_ratio**；事件寫 STANDARD 不會解除這項排除。這不是 P-OV2 已通過、不是 G4 核准，也不把 footprint 邊緣升成實際 detector 的最後可見格。

**取代 `t_V ≥ t_N − L` 的計畫檢查（設計條件，未驗則UNKNOWN／fail closed；UK-8未核，不把靜態估計宣稱實際detector證據）：**

| 檢查 | 條件 | 理由 |
| --- | --- | --- |
| P-OV1 共視 | 目的鏡頭 `t_V ≤ t_X − L`，而且目標從 `t_V` 到 `t_N* + R + 5 s` 都在目的鏡頭可見範圍內 | 失聯時目的鏡頭必須已看到人；進入後至少停留 5 s（情境卡 S1） |
| P-OV2 出口對齊 | 原鏡頭最後可見 `t_L ∈ [t_X − Δ, t_X]` | 失聯時刻由 `t_X` 決定；若出口區畫在可見範圍內側，實際失聯更晚，進入會晚於窗 |
| P-OV3 未來窗不汙染 | `[t_X + Δ, t_X + Δ + W + 1 s)` 內，目標不出現在這個出口的任何非允許候選鏡頭 | 情境卡 S3 |
| P-OV4 共視停留 | 進入 `t_X` 之前的共視停留，目標不得離開原鏡頭可見範圍 | 否則在 `t_X` 之前就失聯（D77 的「留在共視區」改為「離開時只往目的鏡頭單獨可見區走」） |

**邊界。**
- schema 可以表達混合 BLIND／OVERLAP，但 D93 未允許的 BRANCH／WIDE 不能據此進入本輪可評集合；含 OVERLAP 的事件先歸 D93 單獨報告，不回流主分母。每台各用自己的窗；非允許候選仍受 P-OV3 約束。
- 第二版 W1↔W2 是否核准仍由 G4 的 M1 決定（D90 不預先決定）；本規則只在轉移存在時適用。
- 長時間在共視區內「看丟又接上」（反覆暫失）不是本類事件：若漏檢觸發 SEARCHING 並切到另一台，那一次 SWITCH 落在任何 NO_SWITCH 或其他事件窗內時，依該事件規則判 miss；落在窗外則列窗外動作。

### 2.5 較長行走（A4-2／B4-2 類）

**事件定義。**同一 run 內串較長路線、更多事件。不新增事件類別；新增的是場次切分與搜尋次數預算。

**規則。**
1. **每個 Q2 場次一份劇本**（v1 本來就是一份 response 對一份劇本）。劇本帶 `session_query_range_us`；事件窗必須完整落在該場次的查詢範圍內，不跨場次。兩場次查詢範圍可以重疊，但重疊段不放事件（情境卡 A4-2）。
2. **每場次搜尋次數預算（提議，U-D10 未核）**：`Σ 計畫 SEARCHING ≤ N_max−2`（D67：≤4）；STANDARD SWITCH／RETURN 各計1、NO_SWITCH 計0、LONG_GAP 計 n_s(g)、LONG_LOSS 計 n_ret_max(d)。只放單一 LONG_GAP 時，預算4可到 g≤8.6 s，預算3可到 g≤7.6 s；g=6.8 s 自己耗3輪，所以預算4還可放一個 STANDARD，預算3則沒有這一輪餘裕。這是兩個待選預算的成本比較，不是放寬已核定。
3. **跨場次彙總（schema 仍為提議）**：`q5-switch-eval-aggregate.v1` 輸入各場次報告 bytes SHA；同群的分子分母才相加。D93 `OVERLAP_P_OV2_UNVERIFIED` 單獨一群，不進主比率或 STANDARD 主分母；E2／E3 若獲核定，其 LIMIT prefix 也與 COMPLETE 分列。event_id 跨場次不得重複，同一 run／clock，列各場次 uncovered_executed_actions。
4. NO_SWITCH 不放在場次最後（保留情境卡S5）；COMPLETE有query-right ENDED的U7資料前提已由C6確認，但不據此自動放寬規劃約束。場次頭尾仍同S6。
5. 前提：Q2 支援 run 中途的顯式 seed 與限定查詢範圍（情境卡 Q7e；§5 C8）。

**計分。**各事件依自己的類別計分；彙總不加權（每事件 1 票）。

### 2.6 `ENDED_BY_LIMIT` 的部分評分（D90 未定，待使用者決定）

現行 v1：`freeze_output` 只接受 `COMPLETE`，`ENDED_BY_LIMIT`／`PARTIAL`／`NO_SEED`／`UNKNOWN` 在讀劇本之前就拒絕。

| 選項 | 內容 | 優點 | 缺點 |
| --- | --- | --- | --- |
| **E1 維持不評分** | v2 同 v1；adapter 用 §2.5 的預算避免 `ENDED_BY_LIMIT` | 最簡單；完全相容；不需要新契約 | 長 LOST 與 `LOST_TAIL` 都評不了；一次計畫外漏檢累積到上限，整場 0 資料 |
| **E2 前綴評分（建議，未核）** | 在讀劇本前先驗 response／完整已產 journal 的 raw hashes、session／run／clock／scope。cutoff 只能取**同 session、已驗綁定的 ENDED 紀錄 source_time**，不是任意末筆或 timeline 尾端。事件窗完整位於 `[query_left,cutoff)` 才照常評；跨 cutoff 或在其後者記 COVERAGE_MISSING。LIMIT 報告另標 MEASURED_PARTIAL_ENDED_BY_LIMIT，與 COMPLETE 分列、不併主比率 | 用到已產生的決策，不改產品端；C6 已確認會保留 journal | 有存活偏差；新增 decoder／prefix 報告仍待核定，缺 ENDED 或綁定不符必須拒絕 |
| E3 預期上限事件（未核） | LOST_TAIL 的「直到」同 E2：COMPLETE 可到已驗 ENDED 的 query right；LIMIT 只能到實際 cutoff。原計畫窗仍是 `[max(t_prev_end,t_X−W),query_right)`，但 cutoff 後綴一律 COVERAGE_MISSING；不得因補出的 GAP 沒 SWITCH 就判整個計畫窗正確。若核定 E3 的 prefix 比對，也只能報實際 prefix 的「只有 RETURN、沒有 SWITCH」，與 COMPLETE／主比率分列，不能宣稱未執行後綴已觀察 | 能在實際執行前綴檢查「人走後不亂切」 | 只能放場次最後；需明示 partial coverage，E2／E3 如何並用仍由使用者決定 |

建議 **E2**；E3 可在 E2 核定後另外加。PARTIAL（含 USER_STOPPED）、NO_SEED、UNKNOWN 在三個選項下都維持不評分。

**F3 已修／C6 已確認的事實：**LIMIT trace 可在 source_time=6.8 s 終止，timeline 卻補到 query right=12 s；`[6.8,12)` 沒有繼續執行證據。正常 COMPLETE 有 query right 的 ENDED 紀錄，該右端不是觀測。現行 v1 不變；U-D4 未核前，v2 的 LIMIT 解碼／評分入口預設 fail closed，不從 status、reason 或 padding GAP 自推核准。

若E2／E3後續獲核，仍須另驗圖／tracking scope核准、有效時間涵蓋及prefix內沒有MISSING／NOT_INFERRED／缺row；少reason碼不等於這些條件通過。缺ENDED、pins不符或prefix證據不完整時拒絕，不把它補成NO_SWITCH證據。

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
      "event_id": "SYNTHETIC-BLIND-1",
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
      "event_id": "SYNTHETIC-OV-1",
      "action": "SWITCH",
      "event_class": "STANDARD",
      "plan_anchor_us": {"t_X": 40000000, "t_N_by_camera": {}},
      "decision_window_us": [34600000, 41600000],
      "entry_windows_us": {"CAM_EXT_CLEAR": {"kind": "OVERLAP", "range_us": [40000000, 41600000]}}
    },
    {
      "event_id": "SYNTHETIC-R-1",
      "action": "RETURN_TO_ORIGIN",
      "event_class": "LONG_LOSS",
      "plan_anchor_us": {"t_X": 44000000, "t_N": 46500000},
      "decision_window_us": [41600000, 47500000],
      "return_count_max": 2
    }
  ]
}
```

（F4 已修：數字只示範公式，不是正式劇本。BLIND 的兩個進入時刻是假設值；OVERLAP 假設方向 EXT_CAR→EXT_CLEAR 且仍 PROPOSED，未核 G4。三個決策窗依序不重疊、全部在 session [0,48) s 內；R-1 的起點=max(41.6,46.5−6)=41.6 s、終點47.5 s，RETURN 上界=ceil((2.5−0.6)/1)=2。不更動 D89 的正式 run 時鐘宣告。）

**欄位規則。**

| 欄位 | v1 | v2 |
| --- | --- | --- |
| `allowed_camera_ids` + `entry_window_us` | 必填 | **移除**，改 `entry_windows_us`（鍵＝允許鏡頭） |
| `event_class` | 無（隱含 STANDARD） | 必填：`STANDARD`／`LONG_GAP`／`LONG_LOSS`（`LOST_TAIL` 待 §2.6） |
| `plan_anchor_us` | 無 | 必填。SWITCH：`t_X` 與 `t_N_by_camera`（只列 BLIND 鏡頭）；RETURN：`t_X`、`t_N`；NO_SWITCH：`t_X` |
| `parameter_binding` | 無 | 草案必填；U-D5 核定後才決定重算策略。須另讀凍結參數文件、重算 canonical content hash 與 response resolved_scope 比對；不是只信此處數字或把參數 hash 當原檔 bytes SHA（C7） |
| `session_query_range_us` | 無 | 必填；必須等於 response 的 `resolved_source_ranges_us` 之一 |
| `approval_content_sha256` | 無 | `APPROVED` 時必填（D79 U11：核定留言 URL＋固定內容 hash） |
| `return_count_max` | 無 | `LONG_*` 類必填，等於 §1 的公式值；評分器重算比對 |
| `plan_ref` | 無 | 劇本計畫檔的路徑＋hash（評估端專用，不給推論端） |

**評分器驗證（提議採U-D5重算選項時，未核不自動啟用）：**從獨立凍結參數驗證後，依parameter_binding／plan_anchor_us重算類別、decision_window_us、entry_windows_us與return_count_max；不符就EvaluationError，不當miss。超出計畫上界／核定場次預算、同台兩種kind都拒絕；其他待決值未設定／未核仍fail closed。

**實作方式（建議，§6.1 U-D8）。**
- 新模組 `src/amidst/evaluation/q5_switch_eval_v2.py`，`VERSION = 'q5-switch-eval-v2.0'`，報告 `q5-switch-eval-report.v2`。重用 v1 的 `freeze_output`（E2 時另加接受 ENDED_BY_LIMIT 的包裝，不改 v1 函式）。
- **`q5_switch_eval.py` 一個 byte 都不改。**v2 的入口收到 `q5-evaluation-script.v1` 時，直接呼叫 v1 的 `compare_script` 並原樣回傳。
- CLI 另開 `scripts/eval_q5_switch_v2.py`，旗標同 v1；彙總另開 `scripts/aggregate_q5_switch.py`。
- v2 報告欄位仍是提議：by_event_class、standard_event_match_ratio、逐事件 event_class／return_count／return_count_max／return_count_exceeds_max／searching_count／matched_camera_kind 及範圍聲明。D93 已定的 OVERLAP_P_OV2_UNVERIFIED 必須單列；即使 event_class=STANDARD，主比率及 standard_event_match_ratio 都排除。U-D7 只決定其餘主群如何呈現，不得覆寫這項排除。

---

## 4. 相容性（#244：v1 劇本與既有案例結果不變）

### 4.1 要保證的三件事

1. **v1 劇本經 v2 入口，報告與 v1 逐 byte 相同**（含 `output_sha256`、`scorer_version = q5-switch-eval-v1.1`）：v2 入口對 v1 schema 只做分派。
2. **v1 劇本「提升」成 v2 後，逐事件結果相同**：提升規則是 `event_class = STANDARD`、每台 `allowed_camera_ids` 對應同一個 `entry_window_us`、`kind = BLIND`。逐事件 `match`、`reason`、`observed`，以及 `event_match_ratio`、`by_expected_action`、`by_decided_by`、`uncovered_executed_actions` 都相等（報告 schema 不同，所以整份 hash 不同，但這些欄位相等）。提升後的劇本不帶 `plan_anchor_us` 時，不做 §3 的重算驗證（只有 v1 來源的提升劇本可以這樣，標 `lifted_from_v1_sha256`）。
3. **D79 公式在 STANDARD 範圍內不變**：§2.2 的 `LONG_GAP` 起點公式在 `g ≤ G1` 時等於 `t_N − W`；`LONG_LOSS` 窗就是 D79 RETURN 窗；BLIND 進入窗就是 D79 進入窗。

上述相容性不把D94倒灌到v1：原生v2計畫須通過Line2的1.6／1.8 s准入規則；v1輸入走原v1入口與原bytes，不能為新公式重寫既有v1結果。提升版只為比對原v1事件欄位，不拿來繞過原生v2計畫檢查或核定。

### 4.2 既有案例清單

| 案例 | 位置 | v2 預期 |
| --- | --- | --- |
| #222 單元測試 17 個測試函式（`test_q5_switch_eval.py`，部分參數化） | `origin/codex/q1q5-staging` @ `680ca35` | 原檔不改、照跑全過 |
| 同一批測試的 v1 劇本與凍結輸出 | 測試內建的最小布林／整數時間資料 | v2 入口回傳的報告 `output_sha256` 與 v1 相同；提升版逐事件欄位相同 |
| D79 表 P1-E1 推算（#211 工程參數 W 1.2 s、R 0.4 s） | D79 文件 §2 | 只是推算、沒有實跑輸出；用合成資料重建同一序列（RETURN 1.8–3.8 s、SWITCH 決策 4.2 s、進入 5.15 s，`t_N` 5.15）時，STANDARD 下 match、6 個 RETURN 列窗外，與 D79 文字一致 |
| D89 A4-1／B4-1 的 8 個事件（參考窗） | 情境卡 §2.1、§3.1 | 全部 `g` = 2.0–3.0 s，屬 STANDARD；v2 重算的決策窗與進入窗與卡上的參考值相同（A4-e 若兩台 `t_N` 相同，兩台的窗相同） |

正式 A4-1／B4-1 的凍結輸出與劇本目前不存在（#115 NONE），等它們存在後，再加一次「同一凍結輸出 × v1 劇本 × 提升版 v2 劇本」的比對。

### 4.3 驗證方式（給 v2 實作者的後續驗收；本次未執行）

```bash
git diff --exit-code origin/codex/q1q5-staging -- src/amidst/evaluation/q5_switch_eval.py tests/unit/test_q5_switch_eval.py scripts/eval_q5_switch.py
PYTHONPATH=src uv run --no-sync pytest tests/unit/test_q5_switch_eval.py
PYTHONPATH=src uv run --no-sync pytest tests/unit/test_q5_switch_eval_v2.py
git diff --check
```

新測試 `test_q5_switch_eval_v2.py` 至少包含：
- **相容 1**：對 v1 測試的每一組（凍結輸出, v1 劇本），v2 入口與 v1 `compare_script` 的報告逐 byte 相等。
- **相容 2**：同組資料的提升版 v2 劇本，逐事件欄位與比率相等。
- **公式**：§1 的 n_r_max／n_ret_max 與閉界 G_max=10.6 s／D_max=6.6 s；J2 的 0.6 RETURN→1.6 RETURN→2.6 SWITCH、entry7.6；LONG_GAP 起點在 G1 連續；OVERLAP 窗 `[t_X,t_X+L+R)`；D94 的 d=1.6／1.8端點與中間拒絕區間。
- **計數／覆蓋／彙總**：真正 SEARCHING start 在窗前、completion／ENDED 在窗內時不誤計，idx0排除；USER 的 SEARCHING→SEARCHING 新 index 仍算真 start 並分列。LIMIT 同 session ENDED cutoff=6.8、timeline padding到12時後綴COVERAGE_MISSING；D93 OVERLAP 不回流主／STANDARD分母。
- **計分**：`RETURN → RETURN → SWITCH` 在 LONG_GAP 判 match、在 STANDARD 判 miss；`SWITCH → RETURN` 與 `SWITCH → SWITCH` 在 LONG_GAP 判 miss；LONG_LOSS 窗內 3 個 RETURN 判 match、有 SWITCH 判 miss、超過上界時 `return_count_exceeds_max = true` 但 match 不變；依鏡頭進入窗「進入時刻落在另一台的窗」判 miss。
- **驗證**：類別與計畫數字矛盾、窗與重算值不符、超出場次預算、同台兩種 kind → `EvaluationError`；凍結驗證失敗時絕不開劇本（同 v1）。
- runtime 不 import v2 模組（同 v1 最後一個測試）。

---

## 5. C1–C10 回覆處置（#266；不改產品）

固定來源為 #266@38118c40d76f23606a11aecd30a7137c4005afc1 的 §2；其原始碼行號綁定 staging 680ca357，並非本次重跑結果。只解除已回覆的現行行為 UNKNOWN，不把契約 PROPOSED 條文或本文件建議升成核定。

| 題 | 已確認的行為／仍未知部分 | 本稿處置 |
| --- | --- | --- |
| C1／U5 | 首次算1、第N次正常決策／可繼續追蹤、企圖N+1才終止且不產新快照 | U5解除；§1／LOST_TAIL 不再以第6次何時終止為未知 |
| C2／UK-1 | D0=t_last+L=t_fm+L−Δ；無恢復／控制介入時 Dk=D0+kR，R須為Δ整數倍；首次候選窗仍從 first missing 起 | UK-1解除；F1重算，保留G1中的Δ及Line1 D79 |
| C3／UK-2 | 每次無合法SWITCH的搜尋都記 accepted RETURN，另有 action=null 的SEARCHING start；LIMIT／stop／USER override不補假RETURN | UK-2解除；產品資料前提確定，M1／扣分方式仍待U-D1／U-D2 |
| C4／UK-3 | RETURNED每格先probe唯一合法目前真實觀測，恢復時開新local segment，UNCONFIRMED；中心平移只在L內，不能復活舊segment | UK-3解除；先probe同格順序已確認，§1.2採嚴格小於t_N的重搜計數；seed／score資格仍須合法，不能僅以「唯一」推通過 |
| C5／UK-4 | scope gate先於排序；無unknown的OVERLAP tier1、BLIND_GAP tier2、unknown path tier3、relation UNKNOWN tier4；同tier area非null優先、大到小、再camera_id。entry取最早合法guard；不另設SWITCHING延遲 | 排序／entry部分解除；出口對齊與實際detector最後格仍UNKNOWN，P-OV2未驗。D93只准EXT pair另列，M1不預決 |
| C6／UK-5 | COMPLETE／LIMIT同q2-response.v1且有完整已產journal raw hashes；LIMIT填GAP至query right，但停止時間在同session ENDED.source_time；COMPLETE也有query-right ENDED | UK-5現行資料前提解除；F3改cutoff。LIMIT缺少某reason不能推出圖／scope已核、時間完整或沒有MISSING；prefix仍須另驗完整性 |
| C7／UK-6 | resolved_scope已有parameter_set_id／parameter_set_sha256，後者是排除ID／content_sha256／stats的canonical content hash，不是原檔bytes SHA | UK-6解除；另載凍結參數、重算並驗ID／scope／grid才取參數；null拒絕，不新增產品wire欄位 |
| C8／UK-7 | 顯式observation seed＋單run半開子範圍可用；各場次各request／resolved range，輸入與seed導出session_id，同輸入replay同ID；session_ref是授權上下文 | UK-7解除；不把actor ID或劇本時刻當seed，不把兩個範圍塞進同份v1 Q2 |
| C9 | 未達L的反覆短暫失不消耗SEARCHING；成功接回清first_missing。已用session輪數不因恢復／切換／人工選擇退還 | 不累加短暫失秒數、不新增產品LOST期限或enum |
| C10 | 每次真正開新SEARCHING遞增；同輪start／RETURN／SWITCH／completion沿用index；idx0未搜尋、LIMIT終止沿用N | F2只數窗內真正start的正整數index；USER新輪與actions另列，不能把completion當新搜尋 |

只有 C5a 的實際出口／P-OV2 與後續幾何資料仍未知；C1–C10 回覆沒有代選 LONG 計分、LIMIT E1／E2／E3 或 UK-8。

---

## 6. UNKNOWN 與待使用者決定

### 6.1 使用者選項（建議不是核准；U-D3 已由 D93 定案）

| # | 項目 | 選項 | 優點 | 缺點 |
| --- | --- | --- | --- | --- |
| U-D1 | LONG 類的多 RETURN 計分樣式（§2.1） | **M1 `RETURN* → SWITCH`**（恰一個 SWITCH、在最後） | 機械性 RETURN 不扣分；錯切、多切仍抓得到 | 是 D79 未採用的 (c) 的嚴格版，要新決定才能用（只用在 v2 LONG 類） |
| | | M2 M1＋RETURN 次數 ≤ `return_count_max` 才算正確 | 更嚴，抓到重新接上失敗 | 依賴 C2 的相位；相位差一格就誤判 |
| | | M3 只看窗內最後一個動作 | 最簡單 | 前面的錯切被掩蓋，違反 v1「多次 SWITCH 不被掩蓋」 |
| U-D2 | LONG_LOSS 的 RETURN 次數上限（待決） | **不影響 match，只報告 `return_count_exceeds_max`** | C2／C3現行行為已確認，仍可把額外漏檢與match分開呈現 | 重新接上失敗的情況仍算正確 RETURN，要讀報告細項才知道 |
| | | 超過上限判 miss | 一個數字就看得出 | 依賴 C2、C3；相位誤差會誤判 |
| U-D3 | 重疊對進入窗：**已定案（D93）** | **O1 `t_N*=t_X+L` 代入D79**；本輪只評有出口條帶的EXT pair，另列OVERLAP_P_OV2_UNVERIFIED、不併主比率 | 不新增數字，窗寬與BLIND相同；不改Line1 | P-OV2仍未驗、M1未核；不宣稱額外早側容忍已實測 |
| | O2 歷史替代方案（本輪未採用） | 進入窗起點放寬到目的鏡頭t_V | 可表達較早entry | 校正投影進分數，需另核UK-8；本次不得啟用 |
| | O3 歷史替代方案（本輪未採用） | 錨點改原鏡頭最後可見t_L | 不依賴出口區畫法 | 同O2；不能因D93已採O1就推定UK-8獲准 |
| U-D4 | `ENDED_BY_LIMIT` 部分評分（§2.6） | **E2 前綴評分、分開列** | 用到已有資料；不改產品端 | 需要 C6；存活偏差 |
| | | E1 維持不評分 | 最簡單、相容 | 長 LOST 與 LOST_TAIL 評不了 |
| | | E3 預期上限事件（能否與E2並用仍待選） | 只驗實際prefix內「人走了不亂切」 | U5已解除，但只能放場次最後，未執行後綴COVERAGE_MISSING |
| U-D5 | 評分器是否重算窗與分類 | **重算並比對，不符就拒絕** | adapter 錯誤不會變成分數；窗來源可追溯 | 評分器與 adapter 共用公式，改公式要兩邊一起升版 |
| | | 只信劇本給的窗（同 v1） | 評分器簡單 | 分類錯的事件會被當 miss 或錯誤地當 match |
| U-D6 | 早可見盲區（§2.3） | **adapter 拒絕這種計畫**（同情境卡 v1） | 不新增規則；保持 BLIND 窗單純 | 某些路線（EXT_CAR 看得到 VEST_W）不能用 |
| | | BLIND 窗錨點改用 `min(t_N(c), t_V(c) + L)` | 路線較自由 | 校正投影時刻進分數（同 O2 缺點） |
| U-D7 | 主比率怎麼報（待決；D93排除不可覆寫） | **主群總比率＋standard_event_match_ratio＋各類分列** | 主群可與Line1並列；OVERLAP獨立分母不稀釋主群 | 報告欄位多 |
| | | 只報總比率 | 簡單 | 與 Line 1 不可比 |
| U-D8 | 實作位置 | **新模組 `q5_switch_eval_v2.py`，v1 不動** | 相容性可以用 `git diff --exit-code` 證明 | 兩份程式，共用部分要 import v1 |
| | | 擴充 v1 模組（歷史選項） | 一份程式 | 與#306 A15「v1一byte不改」衝突；未經明示修訂架構基準，不得實作此選項 |
| U-D9 | LONG_GAP 決策窗起點（§2.2） | **夾住公式 `min(t_N_min, t_X + G1) − W`** | 事件自己的 RETURN 全歸自己；`g ≤ G1` 時等於 D79 | 新公式（仍只用既有參數） |
| | | 沿用 D79 `t_N − W` | 不新增公式 | g>6.6 s時首RETURN落窗外；5.2<g≤6.6 s時在窗內，是否由M1吸收仍待核 |
| U-D10 | 每場次計畫SEARCHING預算（待決） | **≤N_max−2（4）** | 單一LONG_GAP可到g≤8.6 s；g=6.8 s耗3輪，還有1輪可放STANDARD | 計畫外漏檢餘裕由3輪降為2輪 |
| | | ≤3（同情境卡v1） | 餘裕較大；單一LONG_GAP仍可到g≤7.6 s | g=6.8 s已用完3輪，不能再加STANDARD；不是完全不容LONG |

### 6.2 UNKNOWN 與已解除的產品事實

| # | 目前狀態 | 依據／仍待事項 |
| --- | --- | --- |
| U5 | 已解除現行行為UNKNOWN | C1：首次算1、第N次正常、企圖N+1才停；不等於E3已核 |
| UK-1 | 已解除 | C2：t_fm+L−Δ；無介入的重搜D0+kR且對齊grid |
| UK-2 | 已解除 | C3：每次無合法SWITCH都accepted RETURN，另有start journal |
| UK-3 | 已解除產品可行性 | C4：每格先probe唯一合法真實候選，新segment、UNCONFIRMED；特定幾何／detector成功仍未知 |
| UK-4 | 部分解除 | C5排序與earliest legal guard已確認；出口對齊、P-OV2、M1仍UNKNOWN／待G4 |
| UK-5 | 已解除資料前提 | C6：同schema、已產hashes與ENDED cutoff；E2／E3仍待使用者選，不從padding或reasons推完整 |
| UK-6 | 已解除 | C7：既有ID／content hash；須另載凍結參數重算，null不猜 |
| UK-7 | 已解除 | C8：顯式observation seed、單run半開子範圍、各request／session綁定 |
| UK-8 | **仍待使用者決定（D79 U2）** | t_V／t_L可否只由計畫路線＋靜態校正得到；D98-6只確認它是第14項，沒有選方法或准它進分數 |
| UK-9 | UNKNOWN／等卡片核定與可行性 | 新場景是否真有g>5.2／d≥1.8的合法路線，不能由本公式推定 |
| UK-10 | UNKNOWN／等#247診斷 | 額外漏檢搜尋頻率；U-D10餘裕足不足尚未實測 |

### 6.3 待決清單對照（D98-6：14個名稱，不增刪項目）

使用者明確定義的14個名稱是 **U-D1–U-D10＋E1–E3（U-D4值域）＋UK-8**。E1–E3不是額外三個互不相干的產品開關；此表保留母項與值域層級，避免把「14項」誤讀為14個已選值。

| 序 | 名稱 | 內容／層級 | 目前狀態 |
| --- | --- | --- | --- |
| 1 | U-D1 | LONG多RETURN計分樣式 | 待決，M1只是建議 |
| 2 | U-D2 | RETURN超限是否影響match | 待決 |
| 3 | U-D3 | 重疊窗／O1 | **已定案（D93）**，僅限定EXT pair另列、不併主比率；M1／P-OV2未因此核准 |
| 4 | U-D4 | LIMIT評分母項，值域E1／E2／E3 | 待決 |
| 5 | U-D5 | 重算窗與分類 | 待決 |
| 6 | U-D6 | 早可見盲區處理 | 待決，預設拒絕 |
| 7 | U-D7 | 主群比率呈現 | 待決，必須保留D93排除 |
| 8 | U-D8 | v2實作位置 | 待決；#306 A15 v1原bytes不可改 |
| 9 | U-D9 | LONG_GAP起點 | 待決 |
| 10 | U-D10 | 場次計畫SEARCHING預算 | 待決 |
| 11 | E1 | U-D4：維持不評分 | 值域選項，未選；現行拒絕行為不等於本次核定E1 |
| 12 | E2 | U-D4：prefix分列 | 值域選項，未選；建議不是核准 |
| 13 | E3 | U-D4：LOST_TAIL／實際prefix | 值域選項，未選；未執行後綴仍COVERAGE_MISSING |
| 14 | UK-8（D79 U2） | 計畫＋靜態校正能否給t_V／t_L | **待決**；第14項的身份已由D98-6確認，選項未核 |

UK-8 的選項仍供使用者選：①只作計畫通過／不通過檢查、不進分數（#279 U6-10推薦）；②准作評分時刻（將改GT邊界，須明示核定）。本稿未選其一；GT、renderer軌跡、visibility、depth仍不進推論。D94是另項已定的Line2計畫准入限制，不新增成第15個待決名稱。

### 6.4 CQ-30 回修定位

| J2項 | 狀態 | 本文件定位 |
| --- | --- | --- |
| F1 | 已修 | §1首次相位、§1.1／§1.2閉界公式、§1.4逐步反例、§2.2／§2.4／§2.5及schema數字 |
| F2 | 已修 | §2.1 searching_count真正start定義、§5 C10與§4.3驗收例 |
| F3 | 已修 | §2.6 E2／E3同session ENDED cutoff與未執行後綴 |
| F4 | 已修 | §3三事件窗口全落session [0,48) s內且依序不重疊 |

---

## 7. 來源

**決定（GitHub 留言）**
- D93：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434812845 （O1相位、限定EXT pair、OVERLAP_P_OV2_UNVERIFIED另列且不併主比率）
- D94：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434821818 （Line2拒絕1.6<d<1.8，STANDARD RETURN只收d≤1.6，D90分類不動）
- D98-6：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6461263003 （14名稱對照，UK-8身份確認但未核方法）
- D97／架構基準：https://github.com/Polalalabear/amidst/issues/306 （權威pins、v1一byte不改、未定預設fail closed）
- J2 F1–F4：https://github.com/Polalalabear/amidst/pull/258#issuecomment-6434786468 （本次必修與反例；其14項UNKNOWN由D98-6後續確認）
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
- D79 文件（#306 A12）：`docs/evaluation/Q5_DECISION_WINDOW_D79.md` @ mainline `0d785992a57f1f5db142957bdafa65dfadf1f1a2`，`20b5df9d6948ce4845ebb2e12be7ddae1aa6f6adac087f4d41e3df2489745d1e`
- 情境卡 v1（#306 A11）：`docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md` @ 同mainline，`015201556f550ab67dbbebead35916db426a3b6a05066ffc94c928696900ddbd`（只引用，不更動正式D89／D92／D96範圍）
- C1–C10（#306 A9）：`docs/contracts/L2_LINKER_Q5_CONTRACT_PROPOSAL_20261027.md` @ #266 `38118c40d76f23606a11aecd30a7137c4005afc1`，`9a0acd73f4672ccdc9213d6e76dfd7efd7a30bc902aeaa791bba1fd965bb936e`（PROPOSED；只取其固定code的現行行為回覆；第14項的舊UNKNOWN由D98-6後續決定覆蓋）
- 契約：`docs/contracts/Q1_Q2_FIRST_DEMO_V1.md` @ `680ca35`，`b700bf86041f4853ae37dd54bbc9d93199a07be3d5d3c87bc8c2f6455570df04`（§8.6 狀態機、決策時刻、兜底規則；§8.7 status 清單、`searching_index`）

**議題**：#244（本稿）、#248（L2-5 契約）、#251（第二條線總覽）、#245（情境卡 v2）、#247（漏檢診斷）。

**沒有用到、也沒有讀的來源：**GT、renderer 軌跡／visibility／depth、任何 RGB、`.blend`、#211 private producer。
