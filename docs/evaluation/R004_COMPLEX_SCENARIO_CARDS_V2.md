# r004 複雜情境卡 v2（L2-2，#245）

日期：2026-10-27｜起草：Claude（評估端，D75／D87／D90）｜Model / effort：Claude Opus 5.5 / high

## 狀態

**PROPOSED，待使用者核定。**本文件是第二版情境卡（劇本的設計規格），**不是劇本、不是 Ground Truth、不授權渲染**。依 D90 第 3 項，L2-6（#249）渲染延後；本文件只寫規格。

- **Line 1 不變**：圖 v3、G4、D89 的 A4-1／B4-1、D79 範圍聲明、#222 評分器、`q5-evaluation-script.v1` 都不改。本文件的卡都是**新的 run**，不延長、不取代 A4-1／B4-1。#256 對 A4-1／B4-1 的衝突由 Line 1 自行處理，本文件不處理；本文件只沿用 #256 的距離下界來排第二版的時刻。
- 所有時刻都是**計畫值**（來源時間，從 run 的 sample 0 起算，單位秒），沒有任何一個來自渲染、renderer 軌跡、visibility 或 depth。
- 評分規則 v2 還在設計（#244，設計稿 `docs/evaluation/Q5_SWITCH_EVAL_V2_DESIGN.md` @ `origin/claude/l2-1-scorer-design` `0a87c30`，**PROPOSED，未核定**）。本文件的類別名稱（`STANDARD`／`LONG_GAP`／`LONG_LOSS`／`LOST_TAIL`、`BLIND`／`OVERLAP` 進入窗）與公式都取自該版設計稿，只用來算**參考窗**。設計稿改了，參考窗就要重算；核定前，凡是只有 v2 規則才能評的部分一律標「依賴 #244（未定）」。
- 沒有讀任何 RGB、GT、軌跡、visibility、depth、`.blend`。

## 0. 摘要

### 0.1 第一批情境卡（D90 第 4 項，不需新場景，只用圖 v3 鏡頭）

| 卡 | D90 類別 | 鏡頭組 | 長度 | 場次 | 事件 | 依賴 #244 的部分 | 圖 | RGB（估） |
| --- | --- | --- | ---: | ---: | --- | --- | --- | ---: |
| V2-RR | 一窗多次 RETURN | A4（4 台） | 30 s | 1 | RETURN ×4（兩組反覆暫失） | 多次 RETURN；RR-b 的合併規則 UNKNOWN | v3 | 0.244 GiB |
| V2-LG | 長時間 LOST（SWITCH） | A4 | 24 s | 1 | `LONG_GAP` ×1（g 7.0 s） | LOST 分類、多次 RETURN | v3 | 0.195 GiB |
| V2-LL | 長時間 LOST（RETURN） | A4 | 24 s | 1 | `LONG_LOSS` ×1（d 3.0 s） | LOST 分類、多次 RETURN | v3 | 0.195 GiB |
| V2-LT（預設不做） | 長時間 LOST（尾段） | A4 | 20 s | 1 | `LOST_TAIL` ×1 | LOST 分類＋`ENDED_BY_LIMIT` 選項（E2／E3） | v3 | 0.163 GiB |
| V2-PE1 | 依鏡頭進入窗 | B4（5 台） | 22 s | 1 | SWITCH ×1（{W1, W2}，兩台 `t_N` 差 1.1 s） | 依鏡頭進入窗 | v3（v4 時加 P-OV3 檢查） | 0.224 GiB |
| V2-PE2 | 依鏡頭進入窗＋長 LOST | A4 | 24 s | 1 | `LONG_GAP` ×1（{EXT_CLEAR 3.5 s, EXT_CAR 7.0 s}） | 依鏡頭進入窗、LOST 分類 | v3 | 0.195 GiB |
| V2-OV1 | 重疊接手 | A4 | 26 s | 1 | SWITCH（OVERLAP）×2：EXT_CAR→EXT_CLEAR→EXT_CAR | 重疊接手進入窗 | **v4** | 0.212 GiB |
| V2-OV2 | 重疊接手 | B4 | 16 s | 1 | SWITCH（OVERLAP）×1：BRANCH→WIDE | 重疊接手進入窗 | **v4** | 0.163 GiB |
| V2-OV3 | 重疊接手 | B4 | 16 s | 1 | SWITCH（OVERLAP）×1：W1→W2 | 重疊接手進入窗；**G4 的 M1** | **v4＋M1** | 0.163 GiB |
| V2-A4-2 | 較長行走（由 v1 §2.2 搬入） | A4 | 77 s | 3 | 7（含 `LONG_GAP` ×2） | 全部四項＋跨場次彙總 | v3（v4 時另有風險） | 0.626 GiB |
| V2-B4-2 | 較長行走（由 v1 §3.2 搬入） | B4 | 80 s | 2 | 8（含依鏡頭 SWITCH ×1） | 依鏡頭進入窗＋跨場次彙總 | v3（v4 時另有風險） | 0.814 GiB |

RGB 係數沿用 v1（#132 舊 A 素材 63,976 KiB／150 格；forward 1.108 s／格），新場景壓縮率 UNKNOWN（§3）。

### 0.2 建議（細節見 §6）

**先做「甲」：V2-RR＋V2-LG＋V2-PE1＋V2-OV1**（四類各一張、2,150 格、RGB 約 0.87 GiB、forward 約 40 min）。四張都是短 run、單一場次，每張只測一個新規則部分，失敗時好歸因。較長行走（V2-A4-2、V2-B4-2）放最後：它們同時依賴四個規則部分與跨場次彙總，要等 #244 核定、甲的結果出來再定。

---

## 1. 共同規則

### 1.1 參數與記號（全部沿用）

| 符號 | 值（5 fps、D67） | 來源 |
| --- | ---: | --- |
| `Δ` 索引格距 | 0.2 s | D65、D68 |
| `L` `link_max_gap_us` | 0.6 s | D65；契約 §8.2 |
| `W` `search_window_us` | 6.0 s | D67 |
| `R` `research_interval_us` | 1.0 s | D67 |
| `N_max` `session_max_research_rounds` | 6 | D67 |
| `G1` 第一版 SWITCH 空檔上界 `W + Δ − R` | 5.2 s | D79；D90 第 1 項 |
| `D1` 第一版 RETURN 暫失上界 `Δ + L + R`（開區間） | 1.8 s | D79；D90 第 1 項 |

時刻記號沿用 v1 §1.3／#244 設計稿：`t_X`（離開原鏡頭出口 footprint）、`t_N`（進入目的鏡頭入口 footprint；RETURN 類是重新進入原鏡頭可見區）、`t_N(c)`（依鏡頭）、`g = t_N − t_X`（SWITCH 空檔）、`d = t_N − t_X`（RETURN 暫失）、`t_N* = t_X + Δ + L`（重疊接手的等效進入時刻，#244 §2.4）。

### 1.2 計畫步速與時刻來源

- **計畫步速 1.2 m/s**（本文件的選擇；v1 §6 Q2 的可接受範圍 0.8–1.5 m/s 之內）。
- 盲區時間＝ #256 的**直線距離下界** ÷ 1.2 m/s，往上取到 0.1 s，再視情況加餘裕。#256 的距離是樂觀下界（障礙物只會讓路更長），所以本文件的空檔可能**偏短**，交 Codex 用計畫路線複核（§5）。

| 用途 | #256 下界 | ÷ 1.2 m/s | 本文件計畫值 |
| --- | ---: | ---: | --- |
| EXT_CAR SOUTH → W1 | 8.3634 m | 6.97 s | **g = 7.0 s**（V2-LG、V2-A4-2 c1） |
| EXT_CAR NORTH → W1 | 10.5416 m | 8.78 s | 9.0 s（只作變體，§2.2） |
| EXT_CLEAR ↔ W1 | 3.7661 m | 3.14 s | **3.5 s**（V2-PE2、V2-A4-2 e／c2；反方向距離假設相同，UNKNOWN） |
| EXT_CAR ↔ EXT_CLEAR 入口距離（SOUTH） | 4.2300 m | 3.53 s | EXT_CAR 入口晚於 EXT_CLEAR **3.5 s**（V2-PE2、V2-A4-2 e） |
| W2 → BRANCH／WIDE | 3.6087／4.1076 m | 3.01／3.42 s | **g = 3.5 s**（V2-B4-2 b／b2；v1 是 3.0 s，WIDE 不夠） |
| W1／W2 入口間距（B4-d） | 1.2816 m | 1.07 s | 兩台 `t_N` 差 **1.1 s**（V2-PE1、V2-B4-2 d） |

### 1.3 沿用 v1 的間距與場次規則

v1 §1.4 的 S1–S6 照用（S1 硬下限 `0.2 s + δ`，δ＝允許提早失聯 1.2 s；S2 錨點間距 ≥ 7.0 s；S4 NO_SWITCH 前 ≥ 2 s、後 ≥ 9 s；S5 NO_SWITCH 不放場次最後；S6 第一個 `t_X` ≥ 查詢起點＋3 s、查詢終點 ≥ 最後窗終點＋2 s、run 終點 ≥ 查詢終點）。以下是第二版的改變：

| 項目 | v1 | 第二版（本文件） | 來源 |
| --- | --- | --- | --- |
| 每場次計畫 SEARCHING 上限 | ≤ 3 | **≤ 4**（`N_max − 2`）；`LONG_GAP` 計 `n_s(g)`、`LONG_LOSS` 計 `n_ret_max(d)` | #244 設計稿 §2.5、U-D10（未核定；若改回 ≤ 3，V2-A4-2 S1 要拆） |
| `session_max_research_rounds` 計法 | U5 UNKNOWN | 第一次 SEARCHING 算第 1 輪；第 6 輪可做完，第 7 輪前結束 | #256 Q7（原始碼判讀，未跑 runtime） |
| 長空檔 SWITCH 的 RETURN 次數 | 不允許 | `n_r_max(g)`：g 在 6.8–7.8 s 為 2 次（SEARCHING 3 次） | #244 §1.1 |
| 長暫失 RETURN 的 RETURN 次數 | 1 | `n_ret_max(d) = ⌊(d − Δ − L)/R⌋ + 1`：d = 3.0 s 為 3 次 | #244 §1.2 |
| 允許兩台時的入口時刻差 | ≤ 0.8 s | 取消，每台一窗（`BLIND`） | #244 §2.3 |
| 重疊對的 `t_V ≥ t_N − L` | 必須成立 | 改用 P-OV1–P-OV4 | #244 §2.4 |
| 分場次 | 只在豐富方案 | 允許；每場次一份劇本，重疊段不放事件 | #244 §2.5；#256 Q7（中途 seed＋窄 query 介面存在） |

### 1.4 參考窗公式（#244 設計稿，未核定）

| 類別 | 決策窗 | 進入窗 |
| --- | --- | --- |
| `STANDARD` SWITCH／RETURN | `[max(t_prev_end, t_N − W), t_N + R)`（D79） | `BLIND`：`[t_N(c) − L, t_N(c) + R)`（D79） |
| `STANDARD` NO_SWITCH | `[max(t_prev_end, t_X − W), min(t_X + W, 下一事件未截斷起點, 查詢終點))`（D79；D89 第 3 項讓位） | — |
| `LONG_GAP` | `[max(t_prev_end, min(t_N_min, t_X + G1) − W), t_N_max + R)` | 每台 `BLIND` |
| `LONG_LOSS` | 同 D79 RETURN 窗 | — |
| 重疊接手（`OVERLAP`） | `[max(t_prev_end, t_N* − W), t_N* + R)` ＝ `[t_X − 5.2, t_X + 1.8)` | `[t_X + Δ, t_X + Δ + L + R)` ＝ `[t_X + 0.2, t_X + 1.8)` |
| `LOST_TAIL`（E3，待決） | `[max(t_prev_end, t_X − W), 查詢終點)` | — |

### 1.5 GT 隔離（同 v1 §1.8）

情境卡與劇本只在評估端使用。`t_X`、`t_N` 只由計畫算出；`t_L`／`t_V` 與 P-OV 檢查只用計畫路線投影到靜態校正，只回報通過／不通過，不進分數（#244 U-D3 的 O2／O3 會改變這點，未核定）。人物身分一律 UNCONFIRMED。

---

## 2. 第一批情境卡

每張卡的格式：路線、事件（參考窗）、不計分、G4／圖 v4 需要的邊、渲染量、主要風險、依賴的 v2 規則。

### 2.1 V2-RR：反覆暫失（一窗多次 RETURN）

**目的。**D90 的「一窗多次 RETURN」。#244 把多 RETURN 定為 `LONG_GAP`／`LONG_LOSS` 的計分樣式（那兩類見 V2-LG／V2-LL）；本卡測的是另一種來源：**同一處短時間內反覆暫失**。RR-a 是對照組（兩次暫失間隔夠長，`STANDARD` 規則可評），RR-b 是壓力組（間隔短到第二個 RETURN 可能掉進前一窗）。

鏡頭組 A4：CAM_EXT_CAR、CAM_EXT_CLEAR、CAM_ENTRY（只供 Q1）、CAM_W1。A4 沒渲染 R101_IN、W2，所以 W1：E_PORTAL_R101 **沒有候選**，第一次搜尋就 RETURN（#256 Q7：空候選寫 accepted `RETURN_TO_ORIGIN`）。

**路線**（seed：W1 顯式觀測，約 0.0 s）

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–6.0 | CORR_W | W1 | 走向 R101 門口 |
| 1 | 6.0–7.2 | R101 門檻內側 | —（W1 看不到） | 跨進門檻 1.2 s |
| 2 | 7.2–9.2 | CORR_W 門口 | W1 | 退回走廊，可見 2.0 s |
| 3 | 9.2–10.4 | 門檻內側 | — | 再跨進 1.2 s |
| 4 | 10.4–17.0 | CORR_W | W1 | 沿走廊走開再走回門口 |
| 5 | 17.0–18.2 | 門檻內側 | — | 跨進 1.2 s |
| 6 | 18.2–18.6 | 門口 | W1 | 只露出 0.4 s（2 格） |
| 7 | 18.6–19.8 | 門檻內側 | — | 再跨進 1.2 s |
| 8 | 19.8–30.0 | CORR_W | W1 | 走回走廊中段，停在可見處直到結束 |

查詢 `[0.0, 28.0)`；run 30 s。

**事件**

| 事件 | 類型／類別 | `t_X` | `t_N` | d | 決策窗（參考） | 計畫 SEARCHING | 依賴 |
| --- | --- | ---: | ---: | --- | --- | ---: | --- |
| RR-a1 | RETURN／`STANDARD` | 6.0 | 7.2 | 1.2 s | [1.2, 8.2) | 1 | 無（v1 規則可評） |
| RR-a2 | RETURN／`STANDARD` | 9.2 | 10.4 | 1.2 s | [8.2, 11.4)（截斷） | 1 | 無 |
| RR-b1 | RETURN／UNKNOWN | 17.0 | 18.2 | 1.2 s | [12.2, 19.2) | 1 | **#244（未定）** |
| RR-b2 | RETURN／UNKNOWN | 18.6 | 19.8 | 1.2 s | [19.2, 20.8)（截斷） | 1 | **#244（未定）** |

- RR-a：`t_X(a2) − t_N(a1)` ＝ 2.0 s ≥ S1 的 1.4 s，兩個 RETURN 名目時刻（約 6.8、10.0 s）各落在自己的窗，`STANDARD` 可評。
- RR-b：間隔 0.4 s < 1.4 s。名目第二個 RETURN 約 19.4 s，只比 RR-b2 窗起點晚 0.2 s；提早失聯 δ ≥ 0.2 s 時就落進 RR-b1 的窗，`STANDARD` 判 miss。**#244 設計稿沒有定義這種情況**（§2.1 只讓 `LONG_*` 類有多 RETURN 樣式）。兩個可能：(i) 計畫時就合併成一個 `LONG_LOSS`（`t_X` 17.0、`t_N` 19.8、d 2.8 s、`n_ret_max` 3）；(ii) 維持兩個 `STANDARD`，接受 δ 造成的 miss。列 U-V2-1，交 #244。
- 合計 SEARCHING 4（RR-b 若合併為 `LONG_LOSS` 也是 1＋1＋3 ＝ 5，**超過預算 4**，那時要把 RR-a 拿掉或拆場次）。

**不計分**：段 2／段 6 之間 W1 看到的門口停留不另設 NO_SWITCH（A4 沒有可切候選，NO_SWITCH 無意義）。

- **G4／圖 v4：**不需要任何轉移邊。需要 R101 門檻走得到（#256 Q1 UNKNOWN）。
- **渲染量：**4 × 30 × 5 ＝ 600 格；RGB 約 **0.244 GiB**；forward 約 11.1 min。只算 Q5 的話可以只渲染 W1（150 格、約 0.061 GiB），但候選集合與 A4 不同，要另註冊 run（U-V2-8）。
- **主要風險：**
  1. W1 看得到門檻內側（#256 Q4 UNKNOWN）→ 沒有暫失。
  2. 段 6 只露 2 格：linker 能否在 RETURN 後用這 2 格重新接上（#256 Q7(c)：「當前格恰有 1 個符合的真實觀測時開新片段」，未跑 runtime）。接不上時 RR-b 實際上是一次 d ≈ 2.8 s 的暫失。
  3. 門口來回走動時的漏檢（#247 診斷待出）。

### 2.2 V2-LG：長空檔 SWITCH（`LONG_GAP`）

**目的。**計畫空檔 `g > G1`（5.2 s）的 SWITCH，預期 `RETURN* → SWITCH`。這條路線在 r004 是**自然存在**的：#256 量到 EXT_CAR SOUTH → W1 直線下界 8.3634 m，1.5 m/s 也要 5.58 s。

鏡頭組 A4。**路線**（seed：EXT_CAR 顯式觀測）

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–5.0 | OUT_W（只在 EXT_CAR 視野） | EXT_CAR | 從車旁走向入口，從 SOUTH_APPROACH 離開 |
| 1 | 5.0–12.0 | VEST_W | （追蹤盲區） | 以 1.2 m/s 直走穿過門廳，不停留 |
| 2 | 12.0–24.0 | CORR_W | W1 | 進走廊，停在可見處直到結束 |

查詢 `[0.0, 22.0)`；run 24 s。

**事件**

| 事件 | 類型／類別 | `t_X` | `t_N` | g | 允許鏡頭 | 決策窗（參考） | 進入窗（參考） | 計畫 SEARCHING |
| --- | --- | ---: | ---: | --- | --- | --- | --- | ---: |
| LG-1 | SWITCH／`LONG_GAP` | 5.0 | 12.0 | 7.0 s | {CAM_W1} | [4.2, 13.0) | W1 `BLIND` [11.4, 13.0) | 3（RETURN 上界 2） |

- 決策窗起點 `t_X + G1 − W` ＝ 4.2 s（#244 §2.2，U-D9）；若改回 D79 起點 `t_N − W` ＝ 6.0 s，第一個 RETURN（約 5.8 s）變成窗外動作。
- S3：W1：E_VEST_CORR 以外沒有候選，EXT_CAR 的 RETURN 候選只有 W1 ✔。
- **變體（不建議）：**NORTH 出口 g ＝ 9.0 s → `n_s` ＝ 5 > 預算 4，adapter 會拒絕（#244 §2.5）。

**不計分**：EXT → ENTRY、ENTRY → W1（D74，ENTRY 只供 Q1）。

- **G4／圖 v4：**E_OUT_VEST、E_VEST_CORR；T_CAM_EXT_CAR__CAM_W1。
- **渲染量：**4 × 24 × 5 ＝ 480 格；RGB 約 **0.195 GiB**；forward 約 8.9 min。
- **主要風險：**
  1. EXT_CAR 的涵蓋區含 VEST_W（v1 §2.1 風險 2）→ 實際失聯晚於 5.0 s，空檔變短；若 `t_L` 晚到使 g ≤ 5.2 s，類別與計畫不符（#244：類別由計畫決定，不事後改）。
  2. 實際路徑比直線長 → g > 7.8 s 時 RETURN 上界變 3、SEARCHING 4，剛好用完預算。
  3. 依賴 #248 C2（決策相位）與 C3（每次重搜是否都寫 accepted RETURN）；C3 若否，窗內只會看到 1 個 RETURN。

**依賴 #244：**LOST 分類（`LONG_GAP`）、多次 RETURN 樣式（U-D1 M1）、`LONG_GAP` 窗起點（U-D9）、場次預算（U-D10）。

### 2.3 V2-LL：長暫失 RETURN（`LONG_LOSS`）

**目的。**暫失 `d ≥ D1`（1.8 s）的 RETURN，預期窗內全是 RETURN、沒有 SWITCH。

鏡頭組 A4（理由同 V2-RR：W1：E_PORTAL_R101 沒有候選）。**路線**（seed：W1）

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–6.0 | CORR_W | W1 | 走向 R101 門口 |
| 1 | 6.0–9.0 | R101 門檻內側 | — | 跨進門檻停 3.0 s |
| 2 | 9.0–24.0 | CORR_W | W1 | 退回走廊，停在可見處直到結束 |

查詢 `[0.0, 22.0)`；run 24 s。

| 事件 | 類型／類別 | `t_X` | `t_N` | d | 決策窗（參考） | 計畫 SEARCHING |
| --- | --- | ---: | ---: | --- | --- | ---: |
| LL-1 | RETURN／`LONG_LOSS` | 6.0 | 9.0 | 3.0 s | [3.0, 10.0) | 3（`n_ret_max` 3；名目搜尋約 6.8、7.8、8.8 s） |

- d 選 3.0 s：比 `D1` 多 1.2 s；`n_ret_max` 3 在預算內。d ≥ 3.8 s 時 `n_ret_max` ≥ 4，再多一次漏檢就碰上限。

**不計分**：無其他事件。

- **G4／圖 v4：**不需要轉移邊；需要門檻走得到。
- **渲染量：**480 格；RGB 約 **0.195 GiB**；forward 約 8.9 min。
- **主要風險：**
  1. W1 看得到門檻內側（同 V2-RR）。
  2. 長暫失後能否直接接回（#248 C4；#256 Q7(c) 只確認「當前格恰有 1 個真實觀測」時可以開新片段，暫失 3 s 是否仍適用 D78 的位移條件 UNKNOWN）。
  3. 可以和 V2-RR 放同一個 run 的不同場次（兩者鏡頭組相同），但 V2-RR 已用滿預算，只能分場次（U-V2-8）。

**依賴 #244：**LOST 分類（`LONG_LOSS`）、多次 RETURN 樣式、U-D2（RETURN 次數不影響 match）。

### 2.4 V2-LT：永久離開（`LOST_TAIL`，預設不做）

**目的。**原 A4-d：目標離開所有渲染鏡頭、不再出現。預期只有 RETURN，直到 `ENDED_BY_LIMIT` 或查詢終點。

鏡頭組 A4。路線：段 0（0.0–8.0）W1 seed，走向 R101；段 1（8.0–20.0）走進 R101 深處不再出來（A4 沒渲染 R101_IN）。查詢 `[0.0, 20.0)`；run 20 s。

| 事件 | 類型／類別 | `t_X` | 決策窗（E3 參考） | 計畫 SEARCHING |
| --- | --- | ---: | --- | ---: |
| LT-1 | NO_SWITCH／`LOST_TAIL` | 8.0 | [2.0, 20.0) | 6（約 8.8–13.8 s 每 1 s 一次，之後 `ENDED_BY_LIMIT`；#256 Q7） |

- 這張卡**必然**觸發 `ENDED_BY_LIMIT`。現行 #222 與 #244 E1 都整場不評分；只有使用者選 E2＋E3（#244 §2.6、U-D4）才能評。
- **G4／圖 v4：**無轉移邊；需要 R101 用途核准（#132 註明尚未成立）。
- **渲染量：**4 × 20 × 5 ＝ 400 格；RGB 約 **0.163 GiB**；forward 約 7.4 min。
- **主要風險：**ENDED_BY_LIMIT 的回應是否帶完整 timeline（#248 C6）；超過計畫預算 4（這張卡本來就是要用完）。

**依賴 #244：**LOST 分類（`LOST_TAIL`）、U-D4（E2／E3）。未核定前不做。

### 2.5 V2-PE1：轉角回走廊（依鏡頭進入窗，`STANDARD`）

**目的。**允許兩台目的鏡頭、兩台入口時刻不同的 SWITCH。#256 量到 B4-d 的 W1／W2 入口相距至少 1.2816 m，超過 v1 的 0.8 s 條件；v2 每台各給一窗。

鏡頭組 B4：CAM_W1、CAM_W2、CAM_BRANCH、CAM_R101_IN、CAM_WIDE。**路線**（seed：BRANCH 顯式觀測；固定為 BRANCH，避免 WIDE 的出口在 11–12 m 處造成另一個 `t_X`）

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–6.0 | CORNER（BRANCH∩WIDE） | BRANCH | 停留、轉身 |
| 1 | 6.0–10.1 | CORNER → CORR_W | （盲區） | 走回走廊，依序經過兩台的入口 footprint |
| 2 | 10.1–22.0 | CORR_W | W1 或 W2 | 走向 R101 門口方向，停在可見處直到結束（不進門） |

查詢 `[0.0, 20.0)`；run 22 s。

| 事件 | 類型／類別 | `t_X` | `t_N(c)` | g | 允許鏡頭 | 決策窗（參考） | 進入窗（參考） | 計畫 SEARCHING |
| --- | --- | ---: | --- | --- | --- | --- | --- | ---: |
| PE1-d | SWITCH／`STANDARD` | 6.0 | 先到的一台 9.0；後到的一台 10.1 | 3.0／4.1 s | {CAM_W1, CAM_W2} | [3.0, 11.1) | 先到 `BLIND` [8.4, 10.0)；後到 `BLIND` [9.5, 11.1) | 1 |

- 哪一台先到 UNKNOWN（#256 只給兩入口距離），交 Codex（§5 Q3）；劇本要寫成 `t_N_by_camera` 的具體鍵。
- 兩台 g 都 ≤ 5.2 s，所以是 `STANDARD`；不需要多 RETURN 樣式。

**不計分**：B4-c BRANCH↔WIDE（圖 v3 沒有邊；圖 v4 時由 V2-OV2 測）。

- **G4／圖 v4：**E_W_CORNER；T_CAM_BRANCH__CAM_W1、T_CAM_BRANCH__CAM_W2。圖 v4 下 BRANCH 的出口另有 WIDE（OVERLAP）候選：**P-OV3** 要求 `[6.2, 13.2)` 內 WIDE 看不到目標，否則漏檢時可能切到 WIDE → miss。
- **渲染量：**5 × 22 × 5 ＝ 550 格；RGB 約 **0.224 GiB**；forward 約 10.2 min。
- **主要風險：**
  1. W1 端距離約 16 m、框約 65 px（v1 §3 收據），選到 W1 時可能漏檢或 MATCH_WEAK。
  2. BRANCH∩WIDE 的 footprint 交集只有 1.62 m²（#256 Q5），seed 停留 6 s 時可能走出 BRANCH 視野 → 提早失聯。
  3. 實際路徑比直線長，入口時刻差可能 > 1.1 s；不影響可評性（每台各自一窗），但要用實際值。

**依賴 #244：**依鏡頭進入窗（§2.3、`entry_windows_us`）；圖 v4 時另依賴重疊轉移的候選排序（#248 C5b）。

### 2.6 V2-PE2：出門到室外（依鏡頭進入窗＋`LONG_GAP`）

**目的。**A4-e 的反向問題：#256 量到 EXT_CAR 與 EXT_CLEAR 的入口至少差 2.82 s（1.5 m/s）。v2 每台一窗；因為 EXT_CAR 那台 g > 5.2 s，整個事件歸 `LONG_GAP`（#244 §2.3：任一台 BLIND g_c > G1 → `LONG_GAP`）。

鏡頭組 A4。**路線**（seed：W1）

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–6.0 | CORR_W | W1 | 走向門廳端，從 E_VEST_CORR 離開 |
| 1 | 6.0–9.5 | VEST_W | （盲區） | 穿過門廳，9.5 s 進 EXT_CLEAR 入口 |
| 2 | 9.5–13.0 | OUT_W | EXT_CLEAR | 繼續往 EXT_CAR SOUTH_APPROACH 走，13.0 s 進 EXT_CAR 入口 |
| 3 | 13.0–24.0 | OUT_W（共視區） | EXT_CLEAR 或 EXT_CAR | 停留直到結束 |

查詢 `[0.0, 22.0)`；run 24 s。

| 事件 | 類型／類別 | `t_X` | `t_N(c)` | g | 允許鏡頭 | 決策窗（參考） | 進入窗（參考） | 計畫 SEARCHING |
| --- | --- | ---: | --- | --- | --- | --- | --- | ---: |
| PE2-e | SWITCH／`LONG_GAP` | 6.0 | EXT_CLEAR 9.5；EXT_CAR 13.0 | 3.5／7.0 s | {CAM_EXT_CAR, CAM_EXT_CLEAR} | [3.5, 14.0) | EXT_CLEAR [8.9, 10.5)；EXT_CAR [12.4, 14.0) | 3（`n_s(7.0)`） |

- 名目上第一次搜尋（約 6.8 s，候選窗 [6.2, 12.2)）就看得到 EXT_CLEAR 的進入，0 個 RETURN 直接 SWITCH，仍符合 `RETURN* → SWITCH`。預算照 `max g_c` 算 3。

- **G4／圖 v4：**E_VEST_CORR、E_OUT_VEST；T_CAM_W1__CAM_EXT_CAR、T_CAM_W1__CAM_EXT_CLEAR。圖 v4 下，段 3 的共視停留若漏檢，可能觸發 EXT_CAR↔EXT_CLEAR 重疊切換；落在窗外，只列窗外動作。
- **渲染量：**480 格；RGB 約 **0.195 GiB**；forward 約 8.9 min。
- **主要風險：**
  1. 早可見盲區：EXT_CAR 看得到 VEST_W → `t_V(EXT_CAR)` 早於 `t_N − L`，#244 U-D6 建議 adapter 拒絕這種計畫。這時本卡要把 EXT_CAR 從允許集合拿掉，事件變成只允許 EXT_CLEAR 的 `STANDARD`（就不再測依鏡頭進入窗）。
  2. 反方向距離假設與 #256 相同（UNKNOWN）。

**依賴 #244：**依鏡頭進入窗、LOST 分類（`LONG_GAP` 的混合情形）、U-D6。

### 2.7 V2-OV1：室外重疊接手（EXT_CAR → EXT_CLEAR → EXT_CAR）

**目的。**D90 第 2 項：圖 v4 加 EXT_CAR↔EXT_CLEAR；原鏡頭失聯、進 SEARCHING 後才切。每個重疊事件用**場次 seed 固定原鏡頭**，避免「事先不知道系統在追哪一台」。

鏡頭組 A4。**路線**（seed：EXT_CAR 顯式觀測，目標在 EXT_CAR∩EXT_CLEAR 共視區）

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–6.0 | OUT_W 共視區 | EXT_CAR | 停留（P-OV4：不離開 EXT_CAR 視野） |
| 1 | 6.0–12.8 | 只有 EXT_CLEAR 看得到的區域（存在與否 UNKNOWN） | EXT_CLEAR | 6.0 s 走出 EXT_CAR 視野邊緣，之後停在 EXT_CLEAR 視野 |
| 2 | 12.8–16.0 | 回到共視區 | EXT_CLEAR | 走回共視區（不離開 EXT_CLEAR 視野） |
| 3 | 16.0–26.0 | 車旁（只有 EXT_CAR 看得到） | EXT_CAR | 16.0 s 走出 EXT_CLEAR 視野，停在車旁直到結束 |

查詢 `[0.0, 24.0)`；run 26 s。

| 事件 | 類型／類別 | `t_X` | 允許鏡頭（kind） | 決策窗（參考） | 進入窗（參考） | 計畫 SEARCHING |
| --- | --- | ---: | --- | --- | --- | ---: |
| OV1-a | SWITCH／`STANDARD` | 6.0 | {CAM_EXT_CLEAR}（`OVERLAP`） | [0.8, 7.8) | [6.2, 7.8) | 1 |
| OV1-b | SWITCH／`STANDARD` | 16.0 | {CAM_EXT_CAR}（`OVERLAP`） | [10.8, 17.8) | [16.2, 17.8) | 1 |

- P-OV1：EXT_CLEAR 在 6.0 − 0.6 ＝ 5.4 s 之前就看得到目標，並持續到 `t_N* + R + 5` ＝ 12.8 s；OV1-b 對 EXT_CAR 同理（到 22.8 s）。
- P-OV2：EXT_CAR／EXT_CLEAR 的最後可見時刻要落在 `[t_X − 0.2, t_X]`，需要圖 v4 把重疊轉移的出口區畫在可見範圍邊緣（#248 C5a）。
- P-OV3：OV1-b 從 EXT_CLEAR 失聯時候選還有 W1（BLIND）；`[16.2, 23.2)` W1 看不到室外 ✔（預期，UNKNOWN）。

- **G4／圖 v4：**新邊 EXT_CAR→EXT_CLEAR、EXT_CLEAR→EXT_CAR（transition ID 依 v4 命名，UNKNOWN）；不需要 E_OUT_VEST／E_VEST_CORR。
- **渲染量：**4 × 26 × 5 ＝ 520 格；RGB 約 **0.212 GiB**；forward 約 9.6 min。
- **主要風險：**
  1. 「只有 EXT_CLEAR 看得到」的區域是否存在、在共視區旁邊（UNKNOWN；v1 只有共視面積估計約 40.9 m²，#256 Q6 說不能證明）。
  2. 提早失聯 > 0.4 s（2 格）就進入早於進入窗（#244 O1 的已知缺點）。
  3. 共視停留時的漏檢會提早觸發重疊切換。

**依賴 #244：**重疊接手進入窗（§2.4、U-D3）；圖 v4。

### 2.8 V2-OV2：轉角重疊接手（BRANCH → WIDE）

鏡頭組 B4。**路線**（seed：BRANCH，目標在 BRANCH∩WIDE）

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–6.0 | CORNER 共視區 | BRANCH | 停留 |
| 1 | 6.0–16.0 | 只有 WIDE 看得到的區域（UNKNOWN） | WIDE | 6.0 s 走出 BRANCH 視野，停在 WIDE 視野直到結束；不走進 CORR_N 北段（E_CORNER_N 沒有轉移） |

查詢 `[0.0, 14.0)`；run 16 s。

| 事件 | 類型／類別 | `t_X` | 允許鏡頭（kind） | 決策窗（參考） | 進入窗（參考） | 計畫 SEARCHING |
| --- | --- | ---: | --- | --- | --- | ---: |
| OV2-a | SWITCH／`STANDARD` | 6.0 | {CAM_WIDE}（`OVERLAP`） | [0.8, 7.8) | [6.2, 7.8) | 1 |

- P-OV3：BRANCH 失聯時候選還有 W1、W2（BLIND）；`[6.2, 13.2)` 兩台都不能看到目標。
- **G4／圖 v4：**新邊 BRANCH→WIDE。
- **渲染量：**5 × 16 × 5 ＝ 400 格；RGB 約 **0.163 GiB**；forward 約 7.4 min。
- **主要風險：**共視 footprint 交集只有 1.62 m²（#256 Q5，不是全身共視面積）；WIDE 單獨可見區是否存在、是否在 CORR_N 北段裡（走進去就沒有轉移）都 UNKNOWN。

**依賴 #244：**重疊接手進入窗；圖 v4。

### 2.9 V2-OV3：走廊重疊接手（W1 → W2，依賴 M1）

鏡頭組 B4。**路線**（seed：W1，目標在走廊中段，W1、W2 都看得到）

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–6.0 | CORR_W 中段 → 門廳端 | W1 | 往門廳端走，6.0 s 從 W1 畫面下方離開（還在 CORR_W，不進 VEST_W） |
| 1 | 6.0–16.0 | CORR_W 門廳端 | W2（約 15 m 處） | 停在 W2 視野直到結束 |

查詢 `[0.0, 14.0)`；run 16 s。

| 事件 | 類型／類別 | `t_X` | 允許鏡頭（kind） | 決策窗（參考） | 進入窗（參考） | 計畫 SEARCHING |
| --- | --- | ---: | --- | --- | --- | ---: |
| OV3-a | SWITCH／`STANDARD` | 6.0 | {CAM_W2}（`OVERLAP`） | [0.8, 7.8) | [6.2, 7.8) | 1 |

- 走向門廳端而不是轉角：W1：E_VEST_CORR 的其他候選（EXT_CAR、EXT_CLEAR）不在 B4 run，P-OV3 自動成立；走向轉角的話 BRANCH／WIDE 是候選，P-OV3 很難保證。
- **G4／圖 v4：**新邊 W1→W2；**必須**使用者在 G4 核准 M1（D90 第 2 項不預先決定）。M1 不核准，這張卡不做。
- **渲染量：**400 格；RGB 約 **0.163 GiB**；forward 約 7.4 min。
- **主要風險：**W2 端距離約 15 m（v1 §1.5 收據），框小，可能漏檢；W1 正下方是否還在 CORR_W、是否已進 VEST_W（UNKNOWN）。

**依賴 #244：**重疊接手進入窗；圖 v4；G4 M1。

### 2.10 V2-A4-2：較長行走 A4（由 v1 §2.2 搬入，依 D90 重新歸類）

**重新歸類**（v1 原值 → 第二版）：

| v1 事件 | v1 設計 | 問題（來源） | 第二版 |
| --- | --- | --- | --- |
| A4-c1 EXT_CAR → W1 | g 3.0 s | #256：SOUTH 至少 5.58 s（1.5 m/s） | `LONG_GAP`，g 7.0 s |
| A4-n1 | NO_SWITCH | — | 不變（`STANDARD`） |
| A4-r1 門檻 | RETURN d 1.2 s | — | 不變（`STANDARD`） |
| A4-e W1 → EXT_* | g 3.0 s，兩台差 ≤ 0.8 s | #256：兩台入口至少差 2.82 s | 依鏡頭進入窗＋`LONG_GAP`（同 V2-PE2） |
| A4-n2 室外經過入口 | NO_SWITCH | 圖 v4 時共視區漏檢可能觸發重疊切換 | 不變；改由獨立場次 S3 seed 在 EXT_CLEAR |
| A4-c2 EXT_* → W1 | g 3.0 s | 追 EXT_CAR 時 g ≥ 5.58 s；追哪一台事先不知道，類別無法由計畫決定 | 改由 S3 的 EXT_CLEAR seed 固定原鏡頭；g 3.5 s，`STANDARD` |

**路線**（時間全部重排）

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–12.0 | OUT_W | EXT_CAR（S1 seed） | 繞車走一段，從 SOUTH_APPROACH 離開 |
| 1 | 12.0–19.0 | VEST_W | — | 直走穿過門廳 |
| 2 | 19.0–36.0 | CORR_W | W1 | 24.0 經過 R101 門口不進門；走遠再折返到門口 |
| 3 | 36.0–37.2 | 門檻內側 | — | 跨進 1.2 s 後退回 |
| 4 | 37.2–44.0 | CORR_W | W1（S2 seed 約 39.0） | 走回門廳端 |
| 5 | 44.0–47.5 | VEST_W | — | 出門，47.5 進 EXT_CLEAR 入口 |
| 6 | 47.5–63.5 | OUT_W 共視區 | EXT_CLEAR（S3 seed 約 53.0） | 51.0 進 EXT_CAR 入口（UNKNOWN）；56.5 沿入口外側走過入口不進門 |
| 7 | 63.5–67.0 | VEST_W | — | 從 E_OUT_VEST 再進門 |
| 8 | 67.0–77.0 | CORR_W | W1 | 停在可見處直到結束 |

場次：**S1 `[0.0, 41.0)`**（seed EXT_CAR）、**S2 `[39.0, 55.0)`**（seed W1）、**S3 `[53.0, 75.0)`**（seed EXT_CLEAR）。run 77 s。

| 場次 | 事件 | 類型／類別 | `t_X` | `t_N` | g／d | 允許鏡頭 | 決策窗（參考） | 進入窗（參考） | SEARCHING |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | ---: |
| S1 | c1 | SWITCH／`LONG_GAP` | 12.0 | 19.0 | 7.0 s | {CAM_W1} | [11.2, 20.0) | W1 [18.4, 20.0) | 3 |
| S1 | n1 | NO_SWITCH／`STANDARD` | 24.0 | — | — | — | [20.0, 30.0) | — | 0 |
| S1 | r1 | RETURN／`STANDARD` | 36.0 | 37.2 | 1.2 s | — | [31.2, 38.2) | — | 1 |
| S2 | e | SWITCH／`LONG_GAP` | 44.0 | EXT_CLEAR 47.5；EXT_CAR 51.0 | 3.5／7.0 s | {CAM_EXT_CAR, CAM_EXT_CLEAR} | [41.5, 52.0) | EXT_CLEAR [46.9, 48.5)；EXT_CAR [50.4, 52.0) | 3 |
| S3 | n2 | NO_SWITCH／`STANDARD` | 56.5 | — | — | — | [53.0, 61.0) | — | 0 |
| S3 | c2 | SWITCH／`STANDARD` | 63.5 | 67.0 | 3.5 s | {CAM_W1} | [61.0, 68.0) | W1 [66.4, 68.0) | 1 |

- 每場次 SEARCHING：S1 4（＝預算上限）、S2 3、S3 1。#244 U-D10 若改回 ≤ 3，S1 要把 r1 移到另一場次。
- 間距：c1→n1 停留 5.0 s；n1→r1 `t_N(r1) − t_X(n1)` ＝ 13.2 s；n2→c2 10.5 s。n1 由 r1 的搜尋（約 36.8 s）覆蓋；n2 由 c2 的搜尋（約 64.3 s）覆蓋（S5）。
- 場次重疊段 [39.0, 41.0)、[53.0, 55.0) 不放事件的錨點；n2 窗起點 53.0 與 S2 尾段重疊，事件只在 S3 的劇本。

**不計分**：同 v1 A4-1（A4-a、A4-b）；另外 S2 共視停留與 S3 之間的重疊切換（圖 v4 時）。

- **G4／圖 v4：**E_OUT_VEST、E_VEST_CORR；T_CAM_EXT_CAR__CAM_W1、T_CAM_EXT_CLEAR__CAM_W1、T_CAM_W1__CAM_EXT_CAR、T_CAM_W1__CAM_EXT_CLEAR。圖 v4 時另有 EXT_CAR↔EXT_CLEAR。
- **渲染量：**4 × 77 × 5 ＝ 1,540 格；RGB 約 **0.626 GiB**；forward 約 28.5 min。
- **主要風險：**V2-LG、V2-PE2、V2-RR 的風險全部；三場次 seed 的 adapter 工作；圖 v4 下 n2 可能被重疊切換破壞。

**依賴 #244：**LOST 分類、多次 RETURN、依鏡頭進入窗、場次預算、跨場次彙總（§2.5）；圖 v4 時另依賴重疊接手。

### 2.11 V2-B4-2：較長行走 B4（由 v1 §3.2 搬入，依 D90 重新歸類）

**重新歸類**：

| v1 事件 | v1 設計 | 問題（來源） | 第二版 |
| --- | --- | --- | --- |
| B4-n1 | NO_SWITCH | — | 不變 |
| B4-b W2 → 轉角 | g 3.0 s | #256：WIDE 下界 4.1076 m（1.2 m/s 需 3.42 s） | g 3.5 s，`STANDARD` |
| B4-d 轉角 → 走廊 | 兩台差 ≤ 0.8 s | #256：W1／W2 入口至少差 0.8544 s（1.5 m/s） | 依鏡頭進入窗（同 V2-PE1），`STANDARD` |
| B4-e 穿門 | g 2.0 s | 門口盲區 UNKNOWN（#256 Q4） | 不變 |
| B4-r1 室內 | RETURN d 1.2 s | 視野外區域 UNKNOWN | 不變（`STANDARD`） |
| B4-f 出門 | g 1.5 s | 兩台入口時刻 UNKNOWN | 先寫單一 `t_N`；Codex 給兩台時刻後若不同，改依鏡頭 |
| B4-n2 | NO_SWITCH | — | 不變 |
| B4-b2 | g 3.0 s | 同 B4-b | g 3.5 s |

**路線**

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–11.0 | CORR_W | W2（S1 seed） | 4.0 經過 R101 門口不進門；走到轉角接近區，從 W2 下方離開 |
| 1 | 11.0–14.5 | → CORNER | — | 轉進轉角 |
| 2 | 14.5–21.5 | CORNER 共視區 | BRANCH 或 WIDE | 停留、轉身 |
| 3 | 21.5–25.6 | → CORR_W | — | 走回走廊，依序經過兩台入口 |
| 4 | 25.6–31.0 | CORR_W | W1 或 W2 | 走到 R101 門口 |
| 5 | 31.0–33.0 | 門檻 | — | 穿門 |
| 6 | 33.0–41.0 | R101 | R101_IN（S2 seed 約 37.0） | 室內走動 |
| 7 | 41.0–42.2 | R101 視野外一角（UNKNOWN） | — | 1.2 s 後走回 |
| 8 | 42.2–49.0 | R101 | R101_IN | 走回門口 |
| 9 | 49.0–50.5 | 門檻 | — | 出門 |
| 10 | 50.5–67.0 | CORR_W | W1 或 W2 | 57.0 走進轉角接近區後退回約 2 m，全程可見；再走向轉角 |
| 11 | 67.0–70.5 | → CORNER | — | 轉進轉角 |
| 12 | 70.5–80.0 | CORNER 共視區 | BRANCH 或 WIDE | 停留直到結束 |

場次：**S1 `[0.0, 39.0)`**（seed W2）、**S2 `[37.0, 78.0)`**（seed R101_IN）。run 80 s。

| 場次 | 事件 | 類型／類別 | `t_X` | `t_N` | g／d | 允許鏡頭 | 決策窗（參考） | 進入窗（參考） | SEARCHING |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | ---: |
| S1 | n1 | NO_SWITCH | 4.0 | — | — | — | [0.0, 8.5) | — | 0 |
| S1 | b | SWITCH | 11.0 | 14.5 | 3.5 s | {CAM_BRANCH, CAM_WIDE} | [8.5, 15.5) | 兩台 [13.9, 15.5)（若兩台 `t_N` 不同改依鏡頭） | 1 |
| S1 | d | SWITCH（依鏡頭） | 21.5 | 先到 24.5；後到 25.6 | 3.0／4.1 s | {CAM_W1, CAM_W2} | [18.5, 26.6) | 先到 [23.9, 25.5)；後到 [25.0, 26.6) | 1 |
| S1 | e | SWITCH | 31.0 | 33.0 | 2.0 s | {CAM_R101_IN} | [27.0, 34.0) | [32.4, 34.0) | 1 |
| S2 | r1 | RETURN | 41.0 | 42.2 | 1.2 s | — | [37.0, 43.2) | — | 1 |
| S2 | f | SWITCH | 49.0 | 50.5 | 1.5 s | {CAM_W1, CAM_W2} | [44.5, 51.5) | [49.9, 51.5) | 1 |
| S2 | n2 | NO_SWITCH | 57.0 | — | — | — | [51.5, 63.0) | — | 0 |
| S2 | b2 | SWITCH | 67.0 | 70.5 | 3.5 s | {CAM_BRANCH, CAM_WIDE} | [64.5, 71.5) | [69.9, 71.5) | 1 |

- 全部 `STANDARD`；每場次 SEARCHING 3。
- 間距：d→e `t_N(e) − t_N(d 後到)` ＝ 7.4 s（≥ 7.0，但比 v1 的 8.0 s 餘裕少 0.6 s）；其他同 v1 或更寬。

**不計分**：同 v1 B4-1（B4-a W1↔W2、B4-c BRANCH↔WIDE、CORR_N／R102）。

- **G4／圖 v4：**同 v1 B4-2（E_W_CORNER、E_PORTAL_R101 與 R101 用途核准）。**圖 v4＋M1 核准時：**段 0「從 W2 下方離開」時 W1 仍看得到目標，W2：E_W_CORNER 的候選會多出 W1（OVERLAP），系統可能切到 W1 → b 判 miss。所以本卡在圖 v4 下要改走位或把 b 改成 W1 起點，列 U-V2-6。
- **渲染量：**5 × 80 × 5 ＝ 2,000 格；RGB 約 **0.814 GiB**；forward 約 37.0 min。
- **主要風險：**v1 B4-2 的全部；R101 視野外區域不存在時 r1 刪除。

**依賴 #244：**依鏡頭進入窗、跨場次彙總；圖 v4 時另依賴重疊接手。

### 2.12 卡與 #244 規則部分的對照

| 卡 | 多次 RETURN（§2.1） | LOST 分類（§2.2） | 依鏡頭進入窗（§2.3） | 重疊接手進入窗（§2.4） | 較長行走／分場次（§2.5） | ENDED_BY_LIMIT（§2.6） |
| --- | --- | --- | --- | --- | --- | --- |
| V2-RR | ✔（RR-b：UNKNOWN，U-V2-1） | — | — | — | — | — |
| V2-LG | ✔ | ✔ `LONG_GAP` | — | — | 預算 | — |
| V2-LL | ✔ | ✔ `LONG_LOSS` | — | — | 預算 | — |
| V2-LT | ✔ | ✔ `LOST_TAIL` | — | — | — | ✔（E2＋E3） |
| V2-PE1 | — | — | ✔ | 圖 v4 時（P-OV3） | — | — |
| V2-PE2 | ✔ | ✔ `LONG_GAP` | ✔ | — | 預算 | — |
| V2-OV1／OV2 | — | — | — | ✔ | — | — |
| V2-OV3 | — | — | — | ✔（＋M1） | — | — |
| V2-A4-2 | ✔ | ✔ | ✔ | 圖 v4 時 | ✔（3 場次） | — |
| V2-B4-2 | — | — | ✔ | 圖 v4 時 | ✔（2 場次） | — |

---

## 3. 渲染量

係數沿用 v1：RGB 63,976 KiB／150 格（#132 舊 A 素材，`docs/engineering/R004_SCENE_CHANGE_PROPOSAL.md` §5），forward 1.108406209 s／格。**不是新場景的量測值**；r004 每格大小、渲染時間、`.blend`／索引／暫存大小 UNKNOWN（#256 Q8）。

| 組合 | 卡 | 格數 | RGB（估） | forward（估） |
| --- | --- | ---: | ---: | ---: |
| **甲（建議）** | V2-RR、V2-LG、V2-PE1、V2-OV1 | 2,150 | 0.87 GiB | 39.7 min |
| 乙 | 第一批全部短卡（不含 V2-LT） | 3,910 | 1.59 GiB | 72.2 min |
| 較長行走 | V2-A4-2、V2-B4-2 | 3,540 | 1.44 GiB | 65.4 min |
| 丙 | 乙＋較長行走 | 7,450 | 3.03 GiB | 137.6 min |

磁碟：本 session `df -h /System/Volumes/Data` 可用 13 GiB（2026-10-27 快照；#256 記錄約 12.87 GiB）；停止線 8 GiB。D90 第 3 項：磁碟維持現狀、L2-6 渲染延後，等 D2 用量拆分後定案。所以以上只是估計，**不是渲染申請**。

---

## 4. 第二批（只列清單，不展開）

D90 第 4 項：需要新場景版本、磁碟與渲染授權。最終名單等 #247（漏檢診斷）與 #253／#256（可行性）。

| 項目 | 內容 | 前置 |
| --- | --- | --- |
| B2-1 門廳補盲鏡頭 | 在 VEST_W 加追蹤鏡頭，把 EXT↔W1 的長盲區拆成兩段短盲區（與 V2-LG 對照） | 新場景版本（名稱 UNKNOWN）；新鏡頭校正與 catalog；圖 v5（或 v4 擴充）；G4 逐邊；渲染授權 |
| B2-2 CORR_N 北段／R102 路線 | 目前 E_CORNER_N、E_PORTAL_R102 沒有轉移（v1 §1.1） | 新轉移與鏡頭涵蓋；R102 進路線要推翻 #132 的排除；G4 |
| B2-3 短暫遮擋型 NO_SWITCH（原 B4-d ①） | 目標在同一鏡頭內被遮擋 ≤ 0.4 s 後出現 | 場景要有遮擋物（r004 走廊有沒有：UNKNOWN）；#247 漏檢率；新場景版本 |
| B2-4 超過 `G_max` 的長空檔 | g > 10.8 s 的 SWITCH 只能靠 E2 部分評分或補盲鏡頭 | U-D4；或 B2-1 |
| B2-5 多人干擾 | 藍衣干擾者在非目的候選鏡頭（v1 Q9，#256 說暫不排定） | 路線座標；G4；新場景版本 |

共同前置：(1) 新場景版本與其 catalog／校正凍結；(2) 磁碟：D2 用量拆分完成、可用空間在停止線以上並有渲染＋索引＋暫存的實測係數；(3) 使用者的渲染授權（L2-6）；(4) 遮擋物或新鏡頭的 Blender 可行性檢查（不渲染）。

---

## 5. 給 Codex 的可行性問題（可直接貼上；不渲染）

```text
@Codex：r004 複雜情境卡 v2（docs/evaluation/R004_COMPLEX_SCENARIO_CARDS_V2.md，#245）的靜態可行性檢查。
等使用者核定情境卡 v2 之後才開始。只讀靜態 r004 場景、靜態校正與凍結的 ROI／footprint（同 #256 的證據邊界）；
不渲染、不存 .blend、不讀 renderer 軌跡／visibility／depth，不寫 #115 劇本，不改 Line 1（圖 v3、G4、D89、#222）。
controller 行為問題已在 #248（#244 設計稿 §5 C1–C10），這裡不重複。每題回「可行／不可行／UNKNOWN」並附數字。
計畫步速 1.2 m/s；時刻都是計畫值，可在 ±0.5 s 內調整並回報。

V1 門檻（V2-RR、V2-LL、V2-LT、V2-A4-2 r1）：W1 看不看得到 R101 門檻內側約 1 m 的站位？A4 的 R101 深處（V2-LT）走得到嗎？
V2 長盲區（V2-LG、V2-A4-2 c1）：EXT_CAR SOUTH_APPROACH → W1 入口的計畫路徑長度（不只直線下界）；
   EXT_CAR 對 VEST_W 的可見範圍會讓最後可見時刻 t_L 晚於 t_X 多少？以 1.2 m/s 計，g 是否落在 5.2 < g ≤ 7.8 s？
V3 依鏡頭進入（V2-PE1、V2-B4-2 d）：BRANCH E_W_CORNER 回走廊時，W1、W2 入口 footprint 哪一台先到、兩台 t_N 各是多少？
   B4-f（R101 → 走廊）兩台入口時刻是否不同？
V4 出門（V2-PE2、V2-A4-2 e）：W1 E_VEST_CORR → EXT_CLEAR 入口、→ EXT_CAR SOUTH 入口的計畫路徑長度
   （#256 只給了入站方向的下界）；EXT_CAR 是否在入口 footprint 之前就看得到（早可見盲區，#244 U-D6）？
V5 重疊對的單獨可見區（V2-OV1、OV2、OV3）：
   (a) 是否有「只有 EXT_CLEAR 看得到」、緊鄰 EXT_CAR∩EXT_CLEAR 的站位？「只有 EXT_CAR 看得到」的車旁站位？
   (b) 是否有「只有 WIDE 看得到」、緊鄰 BRANCH∩WIDE、又不在 CORR_N 北段的站位？共視區能否容納 6 s 停留？
   (c) W1 正下方離開畫面的位置是否還在 CORR_W；該處 W2 是否看得到（約 15 m）？
   (d) 圖 v4 的重疊轉移出口區能否畫在原鏡頭可見範圍邊緣（#244 P-OV2，與 #248 C5a 同一題，回一次即可）。
V6 未來窗不汙染（#244 P-OV3）：V2-OV1-b 失聯後 [16.2, 23.2) W1 看不到目標；V2-OV2 失聯後 [6.2, 13.2) W1／W2 看不到轉角內目標；
   V2-PE1 在圖 v4 下，BRANCH 失聯後 [6.2, 13.2) WIDE 看不到目標。
V7 R101 視野外（V2-B4-2 r1）：同 #253 §6 Q1，R101 是否有 R101_IN 看不到、又走得到的一角？
V8 分場次 seed（V2-A4-2 S2／S3、V2-B4-2 S2）：#256 Q7 說中途 seed＋窄 query 介面存在；請確認 seed 可以落在共視區
   並指定鏡頭（V2-A4-2 S3 指定 EXT_CLEAR），以及各場次的搜尋輪數各自計算、不跨場次累計。
V9 渲染量（只估算）：各卡格數見 §3；r004 每格大小、渲染時間、索引與暫存峰值；目前可用約 13 GiB、8 GiB 停止。
V10 圖 v4：是否以圖 v3 為底、只加 EXT_CAR↔EXT_CLEAR、BRANCH↔WIDE（與 M1 核准時的 W1↔W2）？transition ID 命名？
   v3 的 22 條轉移是否完全不變（V2-PE1、V2-B4-2 依賴）？
回覆請附「實際產出 / Actual output」。
```

---

## 6. 建議與優缺點

**建議：甲（V2-RR＋V2-LG＋V2-PE1＋V2-OV1）先核定為第一批的第一輪。**

| 方案 | 內容 | 優點 | 缺點 |
| --- | --- | --- | --- |
| **甲（建議）** | 四類各一張短卡 | 每張只測一個新規則部分，失敗好歸因；都是單一場次；RGB 約 0.87 GiB，最小；V2-RR 的 RR-a 與 V2-PE1 本身就能先用 `STANDARD` 規則驗 adapter | V2-OV1 依賴圖 v4 與「EXT_CLEAR 單獨可見區」（UNKNOWN）；沒有覆蓋 `LONG_LOSS` 與分場次 |
| 乙 | 第一批全部短卡（9 張扣掉 V2-LT） | 每個規則部分有兩張以上的卡；含 `LONG_LOSS`、PE2 的混合情形、三個重疊對 | RGB 約 1.59 GiB；V2-OV3 要等 G4 的 M1；卡多，Codex 可行性檢查工作量加倍 |
| 丙 | 乙＋較長行走 | 最接近展示用的長時間軸（#246）；測跨場次彙總 | RGB 約 3.03 GiB；依賴全部規則部分；V2-A4-2 S1 剛好用滿預算；圖 v4 下 V2-B4-2 的 b 要改（U-V2-6） |

- 較長行走建議等甲的結果與 #244 核定後再做，順序 V2-B4-2（全 `STANDARD`、只多依鏡頭進入窗）先於 V2-A4-2。
- V2-LT 預設不做，等使用者選 #244 U-D4。
- 合併 run：同鏡頭組的短卡（A4：RR、LG、LL、PE2、OV1；B4：PE1、OV2、OV3）可以合成一個 run 的多個場次，減少 run 註冊與時鐘，但格數不變，而且一張卡出問題會拖到整個 run。建議先分開（U-V2-8）。

---

## 7. UNKNOWN 與待決

| # | 項目 | 誰 | 影響 |
| --- | --- | --- | --- |
| U-V2-1 | RR-b（兩次暫失間只露 2 格）要合併成一個 `LONG_LOSS` 還是兩個 `STANDARD` | #244（使用者核定） | V2-RR 的計分與預算 |
| U-V2-2 | #244 設計稿各項（U-D1–U-D10）未核定；本文件的參考窗都依 `0a87c30` 版 | 使用者 | 全部參考窗、類別、預算 |
| U-V2-3 | 實際路徑長與時刻（本文件只用直線下界 ÷ 1.2 m/s） | Codex（§5 V2–V4） | 全部 g；LONG_GAP 的 RETURN 上界 |
| U-V2-4 | 各重疊對的單獨可見區、v4 出口區畫法 | Codex（V5、V10；#248 C5） | V2-OV1–OV3 能否成立 |
| U-V2-5 | 門檻／R101 視野外區域 | Codex（V1、V7） | V2-RR、V2-LL、V2-LT、r1 |
| U-V2-6 | 圖 v4＋M1 時 V2-B4-2 的 b 起點 | 使用者（G4 M1）＋Claude 改卡 | V2-B4-2 |
| U-V2-7 | 長暫失後能否直接接回、每次重搜是否都寫 RETURN | Codex（#248 C3、C4） | V2-LL、V2-LG 的 RETURN 計數 |
| U-V2-8 | 一卡一 run 還是同鏡頭組合併；只渲染 W1 的最小 run 是否可註冊 | 使用者；Codex（run 註冊） | 渲染量、run 數 |
| U-V2-9 | r004 每格 RGB 大小、渲染與索引時間 | Codex（V9） | §3 |
| U-V2-10 | #247 漏檢診斷結果 | Codex（D1） | 預算 4 的餘裕夠不夠；最終名單（D90 第 4 項） |
| D79 U2 | `t_X`／`t_N` 只由計畫算出；`t_L`／`t_V` 只由計畫路線＋靜態校正 | Codex 說明；使用者決定 | GT 隔離（同 v1） |

---

## 8. 來源

**決定（GitHub 留言）**
- D90：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423575212 （LOST 由評估端分類、5.2 s／1.8 s 邊界；失聯後接手、v4 加重疊轉移；第一批／第二批）
- D89：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423194857 （A4-1＋B4-1；A4-2／B4-2 移入 Line 2；NO_SWITCH 讓位）
- D87：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6421557959 （第二條線）
- D79、D67、D65、D73、D74、D77：見 D79 文件與 v1 §1.2。

**檔案（路徑＋commit＋bytes SHA-256）**
- 情境卡 v1：`docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md` @ `origin/claude/r004-a4b4-scenario-cards` `7554dc60267f51cceda1d9a4abb61d115a586574`，`77372a1e38ae266dcfe505f00975f6da66564f96d449c0f7460f1f5f4b5d60d3`（§1.3–§1.8、§2.2、§3.2、§6）
- 評分規則 v2 設計稿：`docs/evaluation/Q5_SWITCH_EVAL_V2_DESIGN.md` @ `origin/claude/l2-1-scorer-design` `0a87c3045923378f25c464e2bc43629612235233`，`3b7991cfe223d24f61340495cea8212e60a5fe0d6d753c2d290f7b31616b1ace`（PROPOSED；§1、§2.1–§2.6、U-D1–U-D10）
- 可行性檢查 #256：`docs/engineering/R004_D89_FEASIBILITY_20261027.md` @ `origin/codex/r004-d89-feasibility` `dd0e69bb7775789eaa94436ead1726dfb2d13823`，`82719479cc33e9d2b825ed37ccf7b4df1999a8aaa2dbba1ed6111183f444e192`（Q2、Q3、Q5 的距離下界；Q7 controller 原始碼判讀；Q8 磁碟）
- D79 文件：`docs/evaluation/Q5_DECISION_WINDOW_D79.md` @ `origin/mainline/q1q5` `2675c215d27424afcc77018cbcc6fe1afd3d7a42`，`7010ca5560b2ca71f35b1f86f87cc0d0b671a6af176065da04fbafeb4a9a6f43`
- 圖 v3、契約、評分器 #222、容量係數：同 v1 §8（`camera_graph_v3.json` `9896be11…`；契約 `b700bf86…` @ `680ca35`；`q5_switch_eval.py` `0fd1ef68…`；`R004_SCENE_CHANGE_PROPOSAL.md` §5）。
- 磁碟：本 session `df -h /System/Volumes/Data` 可用 13 GiB（2026-10-27）。

**議題**：#245（本文件）、#244（評分規則 v2）、#248（controller 契約）、#246（長時間軸）、#247（漏檢診斷）、#249（工程小場景，渲染延後）、#251（第二條線總覽）、#253（情境卡 v1）、#256（v1 可行性）。

**沒有用到、也沒有讀的來源：**GT、renderer 軌跡／visibility／depth、任何 RGB、`.blend`、#211 private producer。
