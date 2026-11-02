# Q5 逐事件決策窗（D79 核定版）

日期：2026-10-25｜起草：Claude（評估端，D75）｜Model / effort：Sonnet 5.5 / medium

## 狀態

**已核定。**使用者於 2026-10-25 以 [D79（#93）](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6398981572) 核定本提案。D79 四項核定結果：

1. **決策窗公式：採方案一**（以進入時刻 `t_N` 為錨）。決策窗 `[t_N − search_window_us, t_N + research_interval_us)`（D67 下 7 s）；SWITCH 另加進入窗 `[t_N − link_max_gap_us, t_N + research_interval_us)`（1.6 s）；NO_SWITCH 窗以離開時刻 `t_X` 為中心前後各 `search_window_us`；與相鄰窗重疊時截斷。現在核定的是公式；`t_X`、`t_N` 由劇本計畫給出（不得取自 GT、renderer 軌跡或動畫），實際秒數在劇本固定 hash 後由評估端算出。`boundary_inclusive` 另案決定。方案二、三**未採用**。
2. **多次 RETURN（K1）：由劇本避開，並標注處理範圍。**第一版正式事件只涵蓋 SWITCH 計畫空檔 `t_N − t_X` ≤ **5.2 s**、RETURN 暫失 < **1.8 s**（5 fps、D67；D90-1 更正：第一版暫失是 < 1.8 s，≥ 1.8 s 歸 Line 2 的「長時間 LOST」，由 [L2-1（#244）](https://github.com/Polalalabear/amidst/issues/244)評分；上面 D79 留言中的「≤ 1.8 s」以此為準；其他格率或參數用同一公式重算）。評分報告必須寫明「本版只評空檔 ≤ 5.2 s、暫失 < 1.8 s 的事件，超出範圍的情況依目前評分器會因多次 RETURN 判 miss，未納入」。評分規則本身不改（D73 不變）。
3. **NO_SWITCH 收緊：同意。**NO_SWITCH 要有完成的回應覆蓋該窗；空 session 或中斷的 session 記為 `COVERAGE_MISSING` 並排除在分母外（與已合入的 #222 一致）。
4. **A4-c 列入正式評估。**A4-c（EXT_CAR／EXT_CLEAR 經盲區 VEST_W 進到 W1，`allowed_camera_ids` = {CAM_W1}）不經過 CAM_ENTRY，不屬於 D74 第 3 點排除的入口交接。

本文件把原提案全文上傳 GitHub（AGENTS.md「Handoff documents go on GitHub」）。與原提案的差異只有：標題與狀態、§3 K1 的公式更正（見下節）、方案二／三標為「未採用」、去掉本機絕對路徑。

## 後續決定（D79 之後；Line 1 範圍不變）

1. **D89-3（NO_SWITCH 結束點讓位，[D89](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423194857)）：**「下一窗起點」取下一事件**未截斷**的起點 `t_N(k+1) − W`；SWITCH／RETURN 的時段一律完整。只影響 B4-n1（[0.0, 8.0)）。
2. **D90-1（[D90](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423575212)）：**暫失 ≥ 1.8 s 的 RETURN 與計畫空檔 > 5.2 s 的 SWITCH 歸「長時間 LOST」，由 L2-1（#244）的新規則評分；controller 不加 `lost_after_us`，D73 §14-27 不變。
3. **D90-2：**重疊接手（EXT_CAR↔EXT_CLEAR、BRANCH↔WIDE，第二版再加 W1↔W2）的新進入窗規則交給 L2-1（#244）；仍須原鏡頭失聯、進入 SEARCHING 後才可切。不預先決定 G4 的 M1。只作用在 Line 2。
4. **D92-1（[D92](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434464633)，採 [#256 §4](https://github.com/Polalalabear/amidst/pull/256#issuecomment-6434381673) 選項 1）：**A4-e、B4-d **不計分**（路線與搜尋照舊，不進分母，也不影響本文 §2 其他事件的窗）；A4-c1 seed 改 EXT_CLEAR；A4-c2 保留但需 Codex 靜態投影確認 EXT_CAR 的 `t_L` 落在 `[t_N − 4.0, t_N − 1.0]`，否則改不計分。A4-1／B4-1 計分事件由 8 降為 6（A4-c2 不過則 5）；長度 50／42 s、#238 時鐘、評分器、本文公式都不動。細節見 [情境卡 v1](R004_A4B4_SCENARIO_CARDS_V1.md)。
5. **D93（[D93](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434812845)，只作用於 Line 2）：**BRANCH／WIDE 出口仍 MISSING 期間，重疊對接手只評有出口條帶的對，用新相位 O1，結果另列 `OVERLAP_P_OV2_UNVERIFIED`，不併入主比率。

6. **D94（[D94](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434821818)，只作用於 Line 2）：**1.8 s 邊界不動；adapter 事前拒絕 `L + R < d < Δ + L + R`（1.6 s < d < 1.8 s）的計畫，STANDARD RETURN 只收 d ≤ 1.6 s，範圍聲明同步補上；Line 1 不變（A4-1／B4-1 無 RETURN 事件）。

## K1 門檻推導

以下用 §1.1 的凍結行為（5 fps、D67：`Δ` = 0.2 s、`L` = 0.6 s、`W` = 6 s、`R` = 1 s）。設目標在 `t_X` 離開原鏡頭、之後理想失聯（最差情況下偵測不到任何延遲），第一個沒接上的索引格 `t_fm = t_X + Δ`。

**SWITCH（只預期 1 個動作）**
- 第一次搜尋的候選窗是 `[t_fm, t_fm + W) = [t_X + Δ, t_X + Δ + W)`，決策時刻 `t_s = t_fm + L`。
- 只要進入觀測落在這個窗內，系統在 `t_s` 就直接 SWITCH，沒有 RETURN，所以窗內只有 1 個動作。
- 進入觀測可以比計畫的 `t_N` 晚，但進入窗是半開區間 `[t_N − L, t_N + R)`，在 5 fps 格點上最晚的進入格是 `t_N + R − Δ`。要這一格仍在候選窗內：窗內最後一格是 `t_fm + W − Δ = t_X + W`，所以需要 `t_N + R − Δ ≤ t_X + W`。
- 整理：`t_N − t_X ≤ W + Δ − R` ＝ 6 + 0.2 − 1 ＝ **5.2 s**。

**提案原文寫 `W − Δ − R`，那是筆誤**：代入得 4.8 s，與 D79 的 5.2 s 不符。正確的符號是 **`W + Δ − R`**（`t_fm` 比 `t_X` 晚一格，候選窗因此多出 `Δ`）。提案其他處（§2 A4-c 的「`t_fm = t_X + Δ`，進入晚 1 s 也成立」）本來就是照 `W + Δ − R` 算的。D79 的數字 5.2 s 不變。

**RETURN（只預期 1 個動作）**
- 系統在 `t_s = t_X + Δ + L` ＝ `t_X + 0.8 s` 第一次搜尋；目標沒在窗內出現就回原鏡頭（1 次 RETURN）。
- 下一次重搜在 `t_s + R` ＝ `t_X + 1.8 s`。目標若在這之前回到原鏡頭，就不再失聯，也不會有第二次 RETURN。
- 條件 `t_N < t_s + R`：`t_N − t_X < Δ + L + R` ＝ 0.2 + 0.6 + 1.0 ＝ **1.8 s**。與提案及 D79 一致，數字不變。

**待 Codex 確認的邊界（不改 D79 數字）**
- 兩個界線是連續時間的上界。RETURN 的界線是開區間（`< 1.8 s`）：5 fps 格點上，若第二次重搜的 tick 與同一格的觀測同時發生，哪一個先處理屬於 controller 實作細節（對應 §4 U5），這裡標 UNKNOWN。劇本設計時建議留一格餘裕（暫失 ≤ 1.6 s）。
- 以上是「保證只有 1 個動作」的**充分條件**，不是「超過就必定 miss」的必要條件。例如 SWITCH 空檔超過界線時，第一個 RETURN 若早於 `t_N − W`，會落在決策窗之外，仍可能 match；只是這取決於各次重搜的時刻與 `session_max_research_rounds`（K2），所以第一版不納入。

---

依據：D73 §14-14 採「逐事件決策窗」，評分器不能自己選窗寬；D75 規定窗寬由 Claude 依劇本事件提案，在輸出凍結前交使用者核定。本文只提**公式與常數**。具體秒數要等 #115 的正式劇本固定 hash 之後，由評估端 adapter 依公式算出。

> **最重要的前提：r004 A4／B4 的正式劇本還不存在。** #115 的產出（run、RGB、clock、劇本）目前都是 NONE（[#115 留言](https://github.com/Polalalabear/amidst/issues/115#issuecomment-6334859555)）。#132 計畫只寫了兩個案例的路線描述，並明說「實際路線座標／長度／時窗待 O10 與 r004 靜態檢查後定案」，也「不先用本時長推人物速度」。圖 v3（Draft #227）的 20 條轉移 `nominal_path_length_m` 全部是 null，而且全部是 `TOPOLOGICAL_ONLY`（G4 未核，合法切鏡 0）。所以本文的逐事件表**沒有任何劇本秒數**。各事件的「預期空檔」一律 UNKNOWN，建議窗寫成公式。這是刻意的設計，不是遺漏：核定的對象是公式與常數，所以可以在劇本與輸出凍結之前就核定。

---

## 1. 前提與定義

### 1.1 已凍結、會直接影響窗寬的系統行為（全部是來源時間）

| 項目 | 值 | 來源 |
| --- | --- | --- |
| 索引格距（正式 r004） | 5 fps，`index_interval_us` 200,000 | D65、D68 |
| `link_max_gap_us` | 600,000：`elapsed_us ≥ 600000` 時進 `SEARCHING`。5 fps 容忍 2 格，第 3 個缺格觸發；20 fps 由同一公式導出 11 格 | D65；契約 §11；D78 |
| `search_window_us` | 6,000,000。候選窗**固定長度**，不依路徑或速度縮放（Q-05） | D67；契約 §8.6 |
| `research_interval_us` | 1,000,000。回原鏡頭後，每隔這麼久重搜一次；新窗從當次 tick 開始，長度仍是 `search_window_us` | D67；契約 §14-13(a)、§14-18(a) |
| `session_max_research_rounds` | 6。達到就 `ENDED_BY_LIMIT` | D67；契約 §8.6、§8.7 status 清單 |
| `decision_time_us` | **這次 `SEARCHING` 開始的來源時間**。切鏡只能進到 `timestamp_us ≥ decision_time_us` 的觀測 | 契約 §8.6 |
| 第一次搜尋的候選窗 | 從第一個沒接上的索引格 `t_fm` 起算，長 `search_window_us`；決策時刻是 `t_fm + 600 ms` | 契約 §8.6、§14-18(a) |
| D65 Agent 預算 | 3 輪、5,000 ms、單次 2,000 ms，全部是**牆鐘** | D65；D73 維持 |
| D78 | 600 ms 內用框中心平移做同鏡頭重新取得；成功只引用真實觀測 | D78 |

**推論一：D65 的牆鐘預算不會移動 `decision_time_us`。** 依契約 §8.6，`decision_time_us` 是 SEARCHING 開始的來源時刻，模型等待多久不影響它。#216 的 audit 裡，RULE_ONLY 的切鏡紀錄 `decision_time_us` 4,200,000 剛好等於 tick 時刻，`budget_used_ms` 是 0。所以窗寬**不為牆鐘延遲加寬**，這也和 D73 §14-17「牆鐘只在 stats」一致。Agent 模式在即時播放時來源游標會不會前進，仍列 UNKNOWN（§4 U6）。

**推論二：決策時刻由搜尋機制決定，不是由人進入目的鏡頭的時刻決定。** 系統用的是離線索引，候選窗可以看到「未來」：#216 的切鏡在 4.20 s 決定，進入觀測在 5.15 s；契約 §8.3 範例的決策是 12.6 s，進入是 13.4 s。設劇本計畫中目標重新出現的時刻為 `t_N`：
- 第一次搜尋的窗 `[t_fm, t_fm+6 s)` 已經涵蓋 `t_N` 時，系統在 `t_s = t_fm + 0.6 s` 就決定 SWITCH，比人實際出現早最多 5.4 s。
- 窗沒涵蓋 `t_N` 時，系統先在 `t_s` 回原鏡頭，之後每 1 s 重搜一次，在第一個滿足 `tick > t_N_actual − 6 s` 的 tick 決定 SWITCH。所以**正確的 SWITCH 決策一定落在 `(t_N_actual − 6 s, t_N_actual]`**。

### 1.2 時刻定義（評估端專用，來自劇本計畫，不來自 GT）

| 符號 | 定義 | 來源 |
| --- | --- | --- |
| `t_X` | 目標依劇本計畫路線離開「起訖鏡頭出口區」凍結 footprint 的時刻 | #115 劇本計畫（評估端專用、固定 hash） |
| `t_N` | 目標依劇本計畫路線**第一次進入目的鏡頭入口區**（圖 v3 的 `to_entry_zone_ids`）凍結 footprint 的時刻。RETURN 類事件則是重新進入原鏡頭可見區的時刻 | 同上 |
| `t_prev_end` | 前一個事件決策窗的終點；第一個事件用 seed 時刻或查詢起點 | 評估 adapter |
| `W`、`R`、`L` | `search_window_us`、`research_interval_us`、`link_max_gap_us` | 綁定的 parameter_set |
| `Δ` | 索引格距（5 fps 時 200,000） | run |

- **GT 隔離：**`t_X` 與 `t_N` 必須來自劇本**計畫**：路點、時刻、計畫路線與凍結的 entry／exit footprint 相交，在評估端算出。不得來自 renderer 軌跡、visibility、depth，也不得來自「人實際在畫面中可見」的渲染輸出。劇本若只有 Blender 動畫 keyframe 或 renderer 軌跡匯出能提供時刻，這個數字就屬於 GT，**交使用者決定是否允許**（§4 U2）。
- 公式只在評估端套用，不回灌 runtime（D71、契約 §14-14(a)）。

### 1.3 和評分器（Draft #222 @ `362a87c`）的對齊

我讀過 `compare_script` 的實際邏輯：
- **決策窗是半開區間** `[start, end)`：`window[0] <= decision_time_us < window[1]`。`entry_window_us` 也是半開：`entry_window[0] <= entry_time_us < entry_window[1]`。
- **SWITCH 事件**：窗內要**恰好一個**已執行動作，而且它是 SWITCH，相機在 `allowed_camera_ids` 內，進入時刻落在 `entry_window_us`。
- **RETURN_TO_ORIGIN 事件**：窗內恰好一個已執行動作，而且是 accepted 的 RETURN。
- **NO_SWITCH 事件**：response 必須是 COMPLETE，而且至少有一筆決策的 `source_time_us ≥ 窗終點`；窗內不能有 SWITCH，可以有 RETURN。沒覆蓋到就記 `match=null`／`COVERAGE_MISSING`，不進分母。
- 各窗要依序、不重疊，而且在 `resolved_source_ranges_us` 內。
- 窗外的動作列在 `uncovered_executed_actions`。
- response 不是 `COMPLETE`（包括 `ENDED_BY_LIMIT`、`PARTIAL`）時，整個 session 不評分。

### 1.4 與 `boundary_inclusive` 的關係（只指出依賴，不替使用者決定）

`exit_rule.boundary_inclusive`（D73 §14-18 仍待核）決定**出口 ROI 邊界上的足點算不算在出口內**，會影響 `exit_resolution` 與候選集合，因此可能改變系統選哪台鏡頭。它**不影響**本提案的窗寬公式：公式只用劇本時刻與 W／R／L；決策時刻由缺格門檻觸發，不由出口判定觸發。另外，評分窗的「半開區間」是評分器的時間區間慣例，和 ROI 幾何邊界是兩回事，不能拿來互相替代。兩者都要在輸出凍結前核定，但可以分開決定。

---

## 2. 逐事件表

說明：
- 「事件」是由 #132 的路線描述、圖 v3 的 tracking scope（20 條轉移、36 個排除）與 D74／D77 推得的**候選子事件**。正式事件 ID、順序、是否真的發生，都以 #115 劇本為準。
- 下表的建議窗都用方案一（§3）。D67 值代入後：

**SWITCH 決策窗** `[max(t_prev_end, t_N − 6.0 s), t_N + 1.0 s)`
- 寬 7.0 s；5 fps 為 35 格，20 fps 為 140 格。

**SWITCH 進入窗** `[t_N − 0.6 s, t_N + 1.0 s)`
- 寬 1.6 s；5 fps 為 8 格（`t_N` 之前 3 格、之後 5 格），20 fps 為 32 格（12＋20）。

**RETURN_TO_ORIGIN 決策窗** `[max(t_prev_end, t_N − 6.0 s), t_N + 1.0 s)`
- 這裡的 `t_N` 是重新進入原鏡頭的時刻；寬度同 SWITCH。

**NO_SWITCH 窗** `[max(t_prev_end, t_X − 6.0 s), min(t_X + 6.0 s, 下一窗起點, 查詢終點))`
- 最寬 12 s；5 fps 為 60 格，20 fps 為 240 格。

| 事件（暫定 ID） | 類型 | 起 → 訖鏡頭 | 劇本預期空檔 | 建議窗 | 理由 | 太窄的風險 | 太寬的風險 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **P1-E1**（#211 工程 8 s，只供 P1，不是正式計分） | 盲區後成功切鏡 | A → B | 劇本 UNKNOWN（producer 是 private，未讀）。偵測面代理值：A 最後一筆儲存 person 3.00 s，B 第一筆 5.15 s，兩鏡頭都沒有儲存 person 的區間是 [3.05, 5.15)（#216 審查；這是推論輸出，不是 GT） | 同方案一，但要代入**工程參數** W 1.2 s、R 0.4 s（#216 audit，不是 D67）：決策窗 `[t_N−1.2 s, t_N+0.4 s)`，進入窗 `[t_N−0.6 s, t_N+0.4 s)` | 工程輸出的實例：RETURN 發生在 1.8、2.2 … 3.8 s（6 次），SWITCH 決策在 4.2 s、進入 5.15 s。若 `t_N` 取代理值 5.15，窗是 [3.95, 5.55)：3.8 s 的 RETURN 在窗外，SWITCH 在窗內，進入點在 [4.55, 5.55) 內，所以 match；6 次 RETURN 列為窗外動作。 | 計畫的 `t_N` 只要 ≤ 5.00 s，3.8 s 的 RETURN 就會落進窗內，變成兩個動作而判 miss（R 0.4 s 太短，詳見 §3 的風險 K1）。 | 若窗往前延伸到 1.25 s，會把追蹤失敗造成的 RETURN 全部算進這個事件（#218）。 |
| **A4-a** | 重疊接手（D77 延後） | EXT_CAR ↔ EXT_CLEAR（共同可見約 40.9 m²） | UNKNOWN | **不設窗、不評分**。窗外動作照列 | D77：第一版不建這個轉移；tracking scope 標 `D77_OVERLAP_DEFERRED_UNTIL_Q5_STABLE` | — | — |
| **A4-b** | CAM_ENTRY 交接（D74 排除） | EXT_* → ENTRY、ENTRY → W1 | UNKNOWN | **不設窗、不評分** | D74：CAM_ENTRY 只用於 Q1，不進自動切鏡；7 個以 ENTRY 為起點的有向對都排除 | — | — |
| **A4-c** | 盲區後成功切鏡（ENTRY 不參與追蹤，所以從追蹤器的角度看，VEST_W 是盲區） | EXT_CAR 或 EXT_CLEAR → W1（經 VEST_W；`allowed_camera_ids` = {CAM_W1}，A4 沒有渲染 W2） | UNKNOWN（VEST_W 的長度／時間都沒有資料） | SWITCH 決策窗／進入窗用方案一 | 圖 v3 有 `T_CAM_EXT_CAR__CAM_W1`、`T_CAM_EXT_CLEAR__CAM_W1`。只要計畫空檔 `t_N − t_X ≤ 5.2 s`（理想失聯，`t_fm = t_X + Δ`，進入晚 1 s 也成立），就只預期 1 個動作 | 進入窗太窄：W1 的入口偵測若晚（框在畫面邊緣、類別混淆，見 #216 B frame 102 被判成 chair），會誤判 miss | 進入窗太寬：可能接受較晚出現的藍衣干擾者。相機正確不代表身分（UNCONFIRMED） |
| **A4-c 的連帶風險** | — | — | 如果目標先從 EXT_CAR 走到只有 EXT_CLEAR 看得到的區域（A4-a 被延後），從追蹤器失聯到 W1 出現的空檔＝EXT_CLEAR 內的停留時間＋VEST_W | 同上 | 空檔 > 5.2 s 時會出現 RETURN，可能汙染窗（K1）；也會消耗 research rounds（K2） | — | — |
| **A4-d** | 找不到（目標離開最後一台被追蹤的鏡頭，A4 沒有任何下一台渲染鏡頭） | W1 → 走廊遠端／CORNER（A4 只渲染 4 台） | UNKNOWN；也可能 run 結束前人沒有離開 W1，那就沒有這個事件 | NO_SWITCH 窗用方案一 | 從 W1 出發的候選（BRANCH、WIDE、R101_IN、EXT_*）中，只有 EXT_* 在 A4 有渲染，目標不在那裡。這時「不切」才是正確結果 | 窗終點太早：可能漏看後來對干擾者的錯切 | 窗終點太晚：沒有決策紀錄的 `source_time_us` 達到終點，就是 `COVERAGE_MISSING`；而且 6 次重搜用完會 `ENDED_BY_LIMIT`，**整個 session 都不能評**（K2） |
| **B4-a** | 同走廊接手（本版不建） | W1 → W2 | UNKNOWN | **不設窗、不評分**。路線若經過這裡，見風險 | 圖 v3 的收據寫「W1↔W2 不在本版盲區搜尋」；W1 的候選裡沒有 W2 | — | **路線風險**：目標從 W1 走進只有 W2 看得到的區域時，系統永遠切不到 W2，會一直 RETURN → 重搜，直到 `ENDED_BY_LIMIT`（K2）。請 Codex 確認 B4 的 seed 鏡頭與路線 |
| **B4-b** | 轉角盲區後成功切鏡 | W1 或 W2 → CORNER（`allowed_camera_ids` = {CAM_BRANCH, CAM_WIDE}） | UNKNOWN。唯一幾何線索：W2 的轉角 patch 是「鏡頭前方可見接近區，距實際轉角約 4 m」（收據第 2 項）；沒有步速，算不出時間 | SWITCH 決策窗／進入窗用方案一 | 圖 v3 有 W1／W2 → BRANCH／WIDE 四條轉移。兩台都看得到 CORNER；兩者之間的重疊接手依 D77 延後，所以兩台都列為允許 | 只列一台：系統選另一台合法鏡頭時會被誤判錯 | 列太多台：會掩蓋錯切。目前只列圖上兩台合法目的地 |
| **B4-c** | 重疊接手（D77 延後） | BRANCH ↔ WIDE（約 8.4 m²） | UNKNOWN | **不設窗、不評分** | D77 | — | — |
| **B4-d** | 「轉角暫失」：情況未定 | ① 暫失 ≤ 600 ms、同鏡頭重新出現：NO_SWITCH；② > 600 ms 後回到原鏡頭：RETURN_TO_ORIGIN；③ 離開轉角回到走廊：SWITCH BRANCH／WIDE → {W1, W2} | UNKNOWN | ①：NO_SWITCH 窗；②：RETURN 窗；③：SWITCH 窗（全部是方案一） | ①：D78 的 600 ms 重新取得應該不會觸發 SEARCHING；②：若在第二次 tick 前重新出現（`t_N − t_X < Δ + 0.6 + R` ＝ 1.8 s @5 fps），預期剛好 1 次 RETURN；③：圖有 BRANCH／WIDE → W1／W2 | ②：暫失超過約 1.8 s 會有多次 RETURN，違反「恰一個動作」而判 miss（K1） | ①：窗太寬可能吞掉相鄰事件，所以以前後窗截斷 |
| **B4-e** | 進門後成功切鏡 | W1 或 W2 → R101_IN（經 PORTAL_R101；`allowed_camera_ids` = {CAM_R101_IN}） | UNKNOWN（門洞 1.20 × 2.40 m，見 R004_REVIEW_V2；穿門時間沒有資料） | SWITCH 決策窗／進入窗用方案一 | 圖有 W1／W2 → R101_IN；BRANCH／WIDE → R101_IN **不在**範圍內。「R101 用途核准尚未成立」（#132），所以要等 G4 | 進門瞬間室內偵測可能較晚 | 同 A4-c |

所有事件共通的前提：圖 v3 目前 20 條轉移全部是 `TOPOLOGICAL_ONLY`，依契約 §5.4 不會進候選。G4 核准、路徑升成 `APPROVED_WALKABLE` 之前，**任何 SWITCH 事件都不可能 match**。這是 G4 的問題，不是窗寬的問題。

---

## 3. 整體方案（D79 選方案一）

### 方案一（D79 採用）：以劇本計畫的重新出現時刻為錨，用已核准參數導出餘裕

> **一句話：**每個 SWITCH／RETURN 事件以劇本計畫的「到達目的（或原）鏡頭入口區時刻 `t_N`」為錨：決策窗 `[t_N − search_window_us, t_N + research_interval_us)`（D67 下是 7 s），SWITCH 另加進入窗 `[t_N − link_max_gap_us, t_N + research_interval_us)`（1.6 s）；NO_SWITCH 以離開時刻 `t_X` 為中心 ±`search_window_us`；與相鄰窗重疊時截斷；不新增任何數字。

- **為什麼起點是 `t_N − W`：**依 §1.1 推論二，正確的 SWITCH 決策一定落在 `(t_N_actual − W, t_N_actual]`。比這更早的 SWITCH，候選窗涵蓋不到入口，不可能正確。比這更早的 RETURN，是固定窗長（Q-05 不縮窗）造成的機械性結果，列在窗外動作即可，不算這個事件錯。追蹤失敗造成的提早失聯（#218）只要不超過 `W − 空檔`，正確的切鏡仍會落在窗內。
  - 以 #211 為例：若 W 是 D67 的 6 s，第一次搜尋窗 [1.25, 7.25) 已經涵蓋 B 的 5.15 s，系統會在 1.80 s 只做一次 SWITCH，仍在窗 [−0.85→截到 seed, 6.15) 內。這只是推算，**沒有實跑**。
- **為什麼終點是 `t_N + R`：**評分器要求 `entry_time ≥ decision_time`，所以決策窗終點等於進入窗終點就足夠。R 是 D73 §14-13 綁定的來源時間單位節奏。
- **為什麼進入窗早側是 L：**框在畫面邊緣可能比計畫的 footprint 進入時刻略早被偵測到。早側容忍沿用系統本身的同鏡頭容忍 L，不另立新數字。
- **優點：**
  - 全部由已核准的 D65／D67 參數導出，參數組換版時公式自動跟著換。
  - 和凍結的搜尋機制一致，提早失聯不會被重複扣成 Q5 錯。
  - 可以在劇本與輸出凍結前核定。
- **缺點：**
  - 需要劇本提供 `t_N`（footprint 進入時刻）。
  - 空檔長（> 約 5.2 s）或暫失長（> 約 1.8 s）的事件有 RETURN 汙染風險（K1）。
  - 窗比直覺寬（7 s），要在報告中說清楚：「窗寬」不等於「允許的延遲」。

### 方案二（未採用）：以離開時刻為錨的統一寬度

> **一句話：**所有事件都從劇本計畫的離開時刻 `t_X` 起算同一個寬度 `[t_X, t_X + search_window_us + research_interval_us)`（7 s），SWITCH 的進入窗同方案一。

- **優點：**只需要一個錨點與一個寬度，最容易解釋；不需要知道空檔多長。
- **缺點：**
  - 提早失聯（#218 類，決策早於 `t_X`）的正確切鏡會落在窗外，被判 miss 又列成窗外動作，Q2 的錯會被重複扣在 Q5 上。
  - 空檔 > 6 s 時，正確切鏡（在 `t_N − 6 s` 之後）可能落在 `t_X + 7 s` 之後。
  - 空檔不同的事件用同一窗，鬆緊不一致。

### 方案三（未採用）：依距離／步速公式（目前不可行）

> **一句話：**決策窗＝`t_X` 起到 `t_X + 路徑長 ÷ 假設步速 + 固定餘裕`，進入窗依同一個預測到達時刻左右各加餘裕。

- **優點：**直覺上符合「走多遠、等多久」。
- **缺點：**
  - 圖 v3 的 `nominal_path_length_m` 全部是 null。
  - repo 裡沒有任何經過核准的步速來源。#132 明說不先用時長推速度。
  - 必須新增「步速」與「餘裕」兩個自由參數。
  - 和系統的固定窗機制（Q-05）脫鉤：預測到達時刻不等於決策時刻。
  - **現階段無法計算**，只能等劇本與路徑長度都有之後再議。

D79 決定：採**方案一**。

### 不論選哪個方案都存在的結構性風險（需使用者知悉，部分要另外決定）

- **K1：「恰一個動作」與多次 RETURN 衝突。** 評分器要求窗內恰好一個已執行動作（D73 §14-14(a)）。下面兩種情況，系統會依凍結的機制在 SWITCH／RETURN 之前或之間產生 RETURN，事件可能被判 miss：
  - SWITCH 事件的空檔大於約 `W + Δ − R` ＝ 5.2 s（5 fps、D67；提案原文誤寫成 `W − Δ − R`，推導見「K1 門檻推導」）；
  - RETURN 事件的暫失大於約 `Δ + L + R` ＝ 1.8 s。

  方案一已經把大部分機械性 RETURN 排在窗外；剩下的機率大約是「實際入口相對 `t_N` 的偏差 ÷ R」。處理方式有三種（D79 選 (a)，並要求報告寫明處理範圍）：
  - (a) 請 Codex 設計劇本時，讓 v1 正式事件的空檔維持在上述界線內，並在劇本中記錄；
  - (b) 接受風險，報告中分列；
  - (c) 另開新決定修改評分規則，例如「SWITCH 窗內只看最後一個動作，前面的 RETURN 另列」。這會改 D73 的條文，不在 D75 的授權範圍內。

  D79：採 (a)；(c) 不採用，D73 評分規則不變。
- **K2：`session_max_research_rounds` 6 可能讓整個 session 不能評。** 達到上限就 `ENDED_BY_LIMIT`，status 不是 COMPLETE，#222 會在讀劇本之前就拒絕。#211 的 SWITCH 是 `searching_index` 7（工程上限 8）；在 D67 的 6 之下，同樣的序列就會結束。風險來源：A4-d 的尾段 NO_SWITCH、B4-a 的 W1→W2、長空檔、長暫失。窗寬改不了這個問題；它屬於查詢範圍與劇本設計，請 Codex 估每個 run 的預期 SEARCHING 次數。
- **K3：窗只算劇本時刻，不保證身分。** 相機與進入時刻都符合，仍然是 UNCONFIRMED（#216 審查：MATCH_STRONG 的 `color_verdict` 是 null）。

---

## 4. UNKNOWN 與待確認

| # | 項目 | 誰提供 | 影響 |
| --- | --- | --- | --- |
| U1 | A4／B4 正式劇本的事件清單、順序、seed 鏡頭與時刻、查詢範圍，以及每個事件的 `t_X`、`t_N`（footprint 進入／離開的計畫時刻） | Codex（#115，評估端專用、固定 hash） | 全部窗的具體值；目前全表空檔 UNKNOWN |
| U2 | `t_X`／`t_N` 能否只從劇本**計畫**（路點＋時刻＋凍結 footprint）算出。若只能從 Blender 動畫或 renderer 軌跡得到，就屬於 GT | Codex 說明；**使用者決定是否允許** | GT 隔離 |
| U3 | A4-c（EXT → W1 經 VEST_W）是否就是 D74 所說「A4 的入口交接不列入評估」 | **使用者** | A4 是否還有任何正式 SWITCH 事件 |
| U4 | B4 路線是否經過 W1 → W2（本版沒有這個轉移）、「轉角暫失」屬於 B4-d 的 ①②③ 哪一種 | Codex（劇本） | B4-a 的風險、B4-d 的事件類型 |
| U5 | 第一次 SEARCHING 算不算一次 research round；`ENDED_BY_LIMIT` 是否在第 6 次 SEARCHING 當下觸發 | Codex（#110 controller） | K2；NO_SWITCH 能不能覆蓋到窗終點 |
| U6 | AGENT 模式下 `decision_time_us` 是否一律等於 SEARCHING 開始時刻；即時播放時，模型等待期間來源游標會不會前進 | Codex | 推論一；若會前進，D65 的 5 s 牆鐘預算可能把決策推出窗外 |
| U7 | 範圍走完時，是否會寫一筆 `source_time_us` ＝ 查詢終點的終止紀錄（NO_SWITCH 覆蓋判定需要） | Codex | NO_SWITCH 的 `COVERAGE_MISSING` |
| U8 | 各轉移的 `nominal_path_length_m`、VEST_W／轉角／門洞的穿越時間、步速 | 目前沒有來源（圖 v3 全部是 null） | 方案三不可行；K1 的空檔判斷 |
| U9 | 劇本裡藍衣干擾者出現在目的鏡頭的時刻 | Codex（劇本） | 進入窗是否需要收窄 |
| U10 | `boundary_inclusive` 的值 | **使用者**（另案） | 不影響窗寬公式，但影響候選與分數 |
| U11 | 窗寬核定後，寫進 `q5-evaluation-script.v1` 的 `approval_ref`，要指向使用者核定留言 URL＋固定內容 hash（#222 目前只驗非空字串） | Claude（評估端）／Codex（adapter） | APPROVED 劇本的可信度 |

---

## 5. 來源清單

**決定（GitHub 留言）**
- D65：https://github.com/Polalalabear/amidst/issues/88#issuecomment-6291477432 （600,000 µs、2 格、5 fps、Agent 預算 3／5000／2000）
- D67：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6292484288 （`search_window_us` 6,000,000、`research_interval_us` 1,000,000、`session_max_research_rounds` 6、`agent_max_illegal_submissions` 2、`session_max_agent_rounds` 12）
- D68：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6292617734 （A4 4 台、B4 5 台、各 30 s、5 fps）
- D73：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6395972547 （§14-14 逐事件決策窗；`boundary_inclusive` 另核）
- D74：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6396154980 （CAM_ENTRY 不進自動切鏡；「A4 的入口交接不列入評估」）
- D75：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6396184028 （窗寬由 Claude 提案、使用者核定）
- D76：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6396442549 （兩階段驗收、WIDE 90°）
- D77：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6397771396 （BRANCH↔WIDE 約 8.4 m²、EXT_CAR↔EXT_CLEAR 約 40.9 m² 延後）
- D78：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6398428243 （600 ms 重新取得；20 fps 為 11 格）

**檔案（路徑＋commit＋bytes SHA-256）**
- 契約 Draft #219：`docs/contracts/Q1_Q2_FIRST_DEMO_V1.md` @ `28eeb8ae07cc234ee73df847cef70fc2e953507f`，SHA-256 `1ae29741b72aaa11866e9a986b61102124ae1efe8e533eafc99d7e9e7d6191c3`。用到的條文：§8.2（L 與格數）、§8.6（`decision_time_us`、固定窗、狀態轉移）、§8.7 status 清單（`ENDED_BY_LIMIT`）、§11、§14-13、§14-14、§14-18、§14-30。
- 驗收計畫：`docs/agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md` @ `origin/mainline/q1q5` `549d8ac2a5de275ccbe5a47fcfffa91d739c8160`，SHA-256 `0b2cd266adc113e482639e0aedf37be110757dbf05107f79e039a0b784f2b3c3`（CL-5）。
- r004 計畫（#132，merge `e4bdde24d04b1d182e7f942123e1a281884c1983`）：`docs/engineering/R004_SCENE_CHANGE_PROPOSAL.md`，最後修改 commit `f4fc841626bf57fb73b70f5e30c5a58e500ca54d`，SHA-256 `c36c9e44a17a2aba2b43eb440fcbe93ae6163be79fdf9cd7fd42e8f67918537e`（§4 A4／B4；「路線長度／時窗待定、不推速度」）。
- Q5 評分程式 Draft #222 head `362a87c6b90a04f9e2720e304e28336b9e7bdd1a`：`src/amidst/evaluation/q5_switch_eval.py` SHA-256 `0fd1ef68c4c83443e8311723224b76f103c142dd018275e7c1596f917e85d9f2`；`docs/evaluation/Q5_SWITCH_EVAL_V1.md` SHA-256 `8457b2849b926b8534b1e43f71c98729f92ccd0320c2c73a89a78fe7ba6008cf`。
- 圖 v3 Draft #227 head `2fb4232af33d567e78f014d92c29df764c08b314`：`configs/q1q5/graphs/r004/camera_graph_v3.json` SHA-256 `03e14e79676872cf7c6a4938fb47d194a46c4b9c2f9af148b1c4716e2bd9c382`（20 條轉移，全部是 TOPOLOGICAL_ONLY，路徑長 null）；`tracking_scope_v3.json` SHA-256 `01771904fffeeae1676bdfe22d87a38d17182fe7260269f42764df061aa56cfd`；`docs/engineering/R004_GRAPH_RECEIPT.md` SHA-256 `8ae9a00978708c6de12c986191623983d5366fec0e0eef446b5b2b88e0e22cd9`（W2 patch 距轉角約 4 m；W1↔W2 不在本版）。
- #216 audit：`docs/history/q1q5_ab_gap_20261025/audit.json` @ `c52cb90dcaf05f123703fa0223461f0c694c6dad`，SHA-256 `80fe6aee4e8f778d22b18b4f1184600eda20abbf5691db83a761aaf5336408a4`（工程參數 W 1.2 s、R 0.4 s、rounds 8；決策序列 RETURN 1.8–3.8 s、SWITCH 決策 4.2 s、進入 5.15 s、`searching_index` 7）。

**其他留言**
- #115：https://github.com/Polalalabear/amidst/issues/115#issuecomment-6334859555 （A4／B4 run 與劇本 NONE）
- #218：https://github.com/Polalalabear/amidst/issues/218 ＋ Codex 分析 https://github.com/Polalalabear/amidst/issues/218#issuecomment-6398196567 （1.25 s 就 GAP，畫面約 3.3 s 才沒人）
- #216 Claude 審查：https://github.com/Polalalabear/amidst/pull/216#issuecomment-6397866809 （A 最後 3.00 s、B 第一筆 5.15 s、[3.05, 5.15)）

**沒有用到、也沒有讀的來源：**GT、renderer 軌跡／visibility／depth、#211 private producer、任何 RGB。
