# r004 複雜情境卡 v2（L2-2，#245）

日期：2026-10-27｜起草：Claude（評估端，D75／D87／D90）｜Model / effort：Claude Opus 5.5 / high

回修：2026-10-30，CQ-31（#323）｜Model / effort：GPT-6（Codex） / UNKNOWN。只改本文件，不核定 U7。

## 狀態

**PROPOSED，U7 尚未核定。**本文件是第二版情境卡的工程候選，不是劇本、不是 Ground Truth、不構成渲染開工。D99 已預先授權 r004 v2 卡「甲」的資料來源；仍須 U7 核定、v2 劇本凍結與磁碟≥9 GiB 三條件全成立。G4／M1與未核評分選項不由本文件代選。

- **Line 1 不變**：圖v3、G4、D89 A4-1／B4-1、D79、#222與v1 schema原bytes不改。全部卡是新run，不延長或取代Line1；本次採#271的明示計畫折線，取代直線下界作完整路線的假設。
- 所有時刻都是**計畫值**（來源時間，從 run 的 sample 0 起算，單位秒），沒有任何一個來自渲染、renderer 軌跡、visibility 或 depth。
- 公式固定#258 CQ-30 head `f19fbcfd2ff64c483fedb00bd9be2e72e97a2af3`（PROPOSED）；其已定部分只沿用D93／D94，其他U-D／UK-8方法仍待核。以下都是參考窗，不是已產生的script／實際觀測；來源#271 head `c5aa674ce772b7f49e813c89ab6fa415064e22ca`未經Claude複審。
- 全卡時序仍有未決：A4-2 S3/n2的重疊段解釋衝突、B4-2 f的逐鏡頭時刻未選，相關窗／搜尋總數保持UNKNOWN，不聲稱兩張長卡已排通或通過驗收。
- 沒有讀任何 RGB、GT、軌跡、visibility、depth、`.blend`。

## 0. 摘要

### 0.1 第一批情境卡（D90 第 4 項，不需新場景，只用圖 v3 鏡頭）

| 卡 | D90 類別 | 鏡頭組 | 長度 | 場次 | 事件 | 依賴 #244 的部分 | 圖 | RGB（估） |
| --- | --- | --- | ---: | ---: | --- | --- | --- | ---: |
| V2-RR | 一窗多次 RETURN | A4（4 台） | 30 s | 1 | RETURN ×4（兩組反覆暫失） | 多次 RETURN；RR-b 的合併規則 UNKNOWN | v3 | 0.244 GiB |
| V2-LG | 長時間 LOST（SWITCH） | A4 | 24 s | 1 | `LONG_GAP` ×1（計畫g 7.4 s，真失聯UNKNOWN） | LOST 分類、多次 RETURN | v3 | 0.195 GiB |
| V2-LL | 長時間 LOST（RETURN） | A4 | 24 s | 1 | `LONG_LOSS` ×1（d 3.0 s） | LOST 分類、多次 RETURN | v3 | 0.195 GiB |
| V2-LT（預設不做） | 長時間 LOST（尾段） | A4 | 20 s | 1 | `LOST_TAIL` ×1 | LOST 分類＋`ENDED_BY_LIMIT` 選項（E2／E3） | v3 | 0.163 GiB |
| V2-PE1 | 依鏡頭進入窗 | B4（5 台） | 22 s | 1 | W1=9.0、W2=10.4，計畫差1.4 s | 依鏡頭進入窗 | v3（v4競爭候選P-OV3未驗） | 0.224 GiB |
| V2-PE2 | 依鏡頭進入窗＋長LOST | A4 | 24 s | 1 | CLEAR=9.4、CAR=13.4（g3.4／7.4 s） | 依鏡頭進入窗、LOST分類 | v3 | 0.195 GiB |
| V2-OV1 | 重疊接手 | A4 | 26 s | 1 | SWITCH（OVERLAP）×2：EXT_CAR→EXT_CLEAR→EXT_CAR | 重疊接手進入窗 | **v4** | 0.212 GiB |
| V2-OV2 **BLOCKED_GEOMETRY** | 重疊接手 | B4 | 16 s（歷史佔位） | — | 無FOV-only獨有區，不列可執行候選 | 需遮擋證據或改卡／場景 | v4出口MISSING | 0.163 GiB（佔位估算） |
| V2-OV3 | 重疊接手 | B4 | 16 s | 1 | SWITCH（OVERLAP）×1：W1→W2 | 重疊接手進入窗；**G4 的 M1** | **v4＋M1** | 0.163 GiB |
| V2-A4-2 | 較長行走候選 | A4 | 77 s（未核） | 3 | 表列6個事件位置；S3/n2政策UNKNOWN | 全部四項＋彙總，非整卡VALID | v3（v4另有競爭候選） | 0.626 GiB（佔位估算） |
| V2-B4-2 | 較長行走候選 | B4 | 80 s（未核） | 3個新request候選 | 8個事件位置；f未定，非整卡VALID | 依鏡頭窗、reseed、彙總 | v3亦有W2→W1競爭候選 | 0.814 GiB（佔位估算） |

RGB 係數沿用 v1（#132 舊 A 素材 63,976 KiB／150 格；forward 1.108 s／格），新場景壓縮率 UNKNOWN（§3）。

### 0.2 建議（細節見 §6）

**推薦甲，但U7未選：RR＋LG＋PE1＋OV1。**新時刻仍放得進原30／24／22／26 s run，所以重算仍為600+480+550+520=2,150格、歷史RGB係數估0.874509 GiB、forward39.717889 min。OV2 BLOCKED_GEOMETRY不在任何可執行第一批；OV3另等M1。甲中的RR-b合併規則、BLIND真失聯與OV1 P-OV仍未核，不能以推薦等同ready。長卡仍有§2.10／§2.11未決，排在短卡之後。

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

D94只限Line2：STANDARD RETURN計畫d≤1.6 s，1.6<d<1.8 s事前拒絕，d≥1.8仍歸LONG_LOSS；不回寫v1分類或接受範圍。

時刻記號沿用v1／#258：t_X、t_N是計畫footprint錨點，g=t_N−t_X、d=t_N−t_X；它們不等於真實最後／首次觀測。理想最後成功觀測在t_X時首次相位為t_fm+L−Δ=t_X+L；D93的重疊等效錨點t_N*=t_X+L，不再加Δ。真正t_fm／entry仍取合法觀測，不能從計畫代填。

### 1.2 計畫步速與時刻來源

- **計畫步速 1.2 m/s**（本文件的選擇；v1 §6 Q2 的可接受範圍 0.8–1.5 m/s 之內）。
- 本次選用#271 `route_audits`的下列計畫折線；座標逐值保留，不重算／改寫該JSON。長度÷1.2只給連續計畫通過時間，不是盲區、t_L／t_V或detector入框證據。表內採用的是明列的0.2 s參考時刻；連續路線控制點不四捨五入，非格點錨點仍不能當實際sample。

| #271 route_id（本次選作計畫候選） | 明示points_world_m，單位m | 已交連續時間s | 本稿參考錨點s |
| --- | --- | --- | --- |
| SOUTH_VIA_WEST_PORTAL_TO_W1 | (-6.2,-4.1,-.06)→(-3.2,0,-.06)→(-3.2,0,0)→(.35,1.1,0) | 7.380726254318201 | LG 5→12.4；A4 c1 12→19.4 |
| NORTH_VIA_WEST_PORTAL_TO_W1（僅變體） | (-10,-.9,-.06)→(-3.2,0,-.06)→(-3.2,0,0)→(.35,1.1,0) | 8.863181202238861 | g9.0，SEARCHING5，超過建議預算4 |
| CLEAR_VIA_WEST_PORTAL_TO_W1 | (-3.35,.4,-.06)→(-3.2,0,-.06)→(-3.2,0,0)→(.35,1.1,0) | 3.503097811746253 | A4 c2 63.5→67.2；63.5是連續計畫錨點，非index格承諾 |
| W1_VIA_WEST_PORTAL_TO_SOUTH | (.35,1.1,0)→(-3.2,0,0)→(-3.2,0,-.06)→(-6.2,-4.1,-.06) | CLEAR3.358779085622698／CAR7.380726254318201 | PE2 6→9.4／13.4；A4 e44→47.4／51.4 |
| BRANCH_TO_W1_THEN_W2_DETOUR | (15,1.4,0)→(13.9,.2,0)→(12.85,1.6,0)→(12.6,1.85,0)→(11.4,1.15,0) | W1 2.8149017163416423／W2 4.267233207623521 | PE1 6→9.0／10.4；B4 d21.5→24.4／25.8 |
| W2_TO_BRANCH_THEN_WIDE | (11.4,1.15,0)→(15,1.4,0)→(15.5,1.4,0) | BRANCH3.007225095961022／WIDE3.4238917626276884 | b11→14.2／14.6；b2 67→70.2／70.6 |
| R101_TO_W2_THEN_W1（只引用、不採為f最終時序） | (8,-.1,0)→(8,.1,0)→(7.9,.6,0) | W2 .16666666666666666／W1 .5915849594660654 | f兩台t_N=UNKNOWN；不以短線覆寫50.5歷史佔位 |

RR選擇淺進≤0.72m、零停留（§2.1 F3）；LL／LT／室內r1僅引用#271的支撐候選，沒有把門牆遮擋或物理可達性核過。#271每條continuous points保持原bytes，以上省略的末位0只屬數字顯示、不移動座標。

### 1.3 沿用 v1 的間距與場次規則

v1 §1.4 的 S1–S6 照用（S1 硬下限 `0.2 s + δ`，δ＝允許提早失聯 1.2 s；S2 錨點間距 ≥ 7.0 s；S4 NO_SWITCH 前 ≥ 2 s、後 ≥ 9 s；S5 NO_SWITCH 不放場次最後；S6 第一個 `t_X` ≥ 查詢起點＋3 s、查詢終點 ≥ 最後窗終點＋2 s、run 終點 ≥ 查詢終點）。以下是第二版的改變：

| 項目 | v1 | 第二版（本文件） | 來源 |
| --- | --- | --- | --- |
| 每場次計畫 SEARCHING 上限 | ≤ 3 | **≤ 4**（`N_max − 2`）；`LONG_GAP` 計 `n_s(g)`、`LONG_LOSS` 計 `n_ret_max(d)` | #244 設計稿 §2.5、U-D10（未核定；若改回 ≤ 3，V2-A4-2 S1 要拆） |
| session輪數 | 歷史U5 | 首次算1，第6次照常決策／可繼續追蹤，企圖第7次才停 | #266 C1／#258 CQ-30，非本次runtime測試 |
| 長空檔RETURN上界 | v1不採多RETURN | g>G1時n_r_max=max(1,ceil((g−(W+L))/R)+1)，n_s=n_r_max+1；(6.6,7.6]s為2次RETURN／3次SEARCHING | #258 §1.1；G_max=10.6 s含端點 |
| 長暫失RETURN上界 | v1不改 | n_ret_max=max(0,ceil((d−L)/R))；同格先probe恢復再判重搜，d3.0為3次 | #258 §1.2；D_max=6.6 s含端點 |
| 允許兩台時的入口時刻差 | ≤ 0.8 s | 取消，每台一窗（`BLIND`） | #244 §2.3 |
| 重疊對 | v1不改 | D93只評EXT pair、O1相位，另列OVERLAP_P_OV2_UNVERIFIED，不併主／STANDARD分母；P-OV未驗 | #258 §2.4；W1↔W2等M1，OV2不評 |
| 分場次 | 只在豐富方案 | 允許；每場次一份劇本，重疊段不放事件 | #244 §2.5；#256 Q7（中途 seed＋窄 query 介面存在） |

### 1.4 參考窗公式（#244 設計稿，未核定）

每場次獨立計算，第一個t_prev_end取該query左端；以下所有max都包含此範圍下限。NO_SWITCH的「下一起點」是下一事件未截斷起點，右端半開。遇到UNKNOWN參數不填猜測數字，相關窗／全卡驗收fail closed。

| 類別 | 決策窗 | 進入窗 |
| --- | --- | --- |
| `STANDARD` SWITCH／RETURN | `[max(t_prev_end, t_N − W), t_N + R)`（D79） | `BLIND`：`[t_N(c) − L, t_N(c) + R)`（D79） |
| `STANDARD` NO_SWITCH | `[max(t_prev_end, t_X − W), min(t_X + W, 下一事件未截斷起點, 查詢終點))`（D79；D89 第 3 項讓位） | — |
| `LONG_GAP` | `[max(t_prev_end, min(t_N_min, t_X + G1) − W), t_N_max + R)` | 每台 `BLIND` |
| `LONG_LOSS` | 同 D79 RETURN 窗 | — |
| 重疊接手（OVERLAP） | `[max(t_prev_end,t_X+L−W),t_X+L+R)`；未截斷時`[t_X−5.4,t_X+1.6)` | `[t_X,t_X+L+R)`＝`[t_X,t_X+1.6)` |
| `LOST_TAIL`（E3，待決） | `[max(t_prev_end, t_X − W), 查詢終點)` | — |

### 1.5 GT 隔離（同 v1 §1.8）

情境卡與劇本只在評估端使用。t_X／t_N是計畫，真正t_L／t_V／遮擋／全身可見性仍UNKNOWN；靜態frustum或支撐不能代替它們。UK-8（D79 U2）方法未核，P-OV無證據不PASS；D93不等於P-OV2已驗。推論不得讀GT、軌跡、visibility、depth或這些錨點。身分UNCONFIRMED、物理UNKNOWN。

---

## 2. 第一批情境卡

每張卡的格式：路線、事件（參考窗）、不計分、G4／圖 v4 需要的邊、渲染量、主要風險、依賴的 v2 規則。

### 2.1 V2-RR：反覆暫失（一窗多次 RETURN）

**目的。**D90 的「一窗多次 RETURN」。#244 把多 RETURN 定為 `LONG_GAP`／`LONG_LOSS` 的計分樣式（那兩類見 V2-LG／V2-LL）；本卡測的是另一種來源：**同一處短時間內反覆暫失**。RR-a 是對照組（兩次暫失間隔夠長，`STANDARD` 規則可評），RR-b 是壓力組（間隔短到第二個 RETURN 可能掉進前一窗）。

鏡頭組 A4：CAM_EXT_CAR、CAM_EXT_CLEAR、CAM_ENTRY（只供 Q1）、CAM_W1。A4 沒渲染 R101_IN、W2，所以 W1：E_PORTAL_R101 **沒有候選**，第一次搜尋就 RETURN（#256 Q7：空候選寫 accepted `RETURN_TO_ORIGIN`）。

**路線／F3 已修：選淺進≤0.72m、零停留。**保留每次進退1.2 s，因2×0.72/1.2=1.2 s；不再同時要求深入1m。深度是計畫上限，不保證如此就會離開W1可見區；若沒有合法失聯證據，卡仍不可凍結。seed候選W1@0.0 s，實際observation_id=MISSING。

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–6.0 | CORR_W | W1 | 走向 R101 門口 |
| 1 | 6.0–7.2 | R101門檻淺進≤0.72m | 失聯待驗 | 進退共1.2 s、零停留，不假定W1看不到 |
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

- RR-a：間隔2.0 s≥S1 1.4 s；理想首次RETURN約6.6／9.8 s，各在自己的半開窗。兩個d=1.2 s都在D94 STANDARD准入內；不是已驗遮擋或detector成功。
- RR-b：間隔.4 s<1.4 s；理想第二RETURN=18.6+.6=19.2 s，剛好在b2左端、被b1右端排除。只要提早一格至19.0 s就會落入b1，不能沿用舊「晚.2 s餘裕」。#258未核定這種短重現合併：可提(i)合併LONG_LOSS（17→19.8、d2.8、n_ret_max3）或(ii)兩個STANDARD壓力測試，U-V2-1未選。不能依實際漏檢後事後改類別。
- 合計 SEARCHING 4（RR-b 若合併為 `LONG_LOSS` 也是 1＋1＋3 ＝ 5，**超過預算 4**，那時要把 RR-a 拿掉或拆場次）。

**不計分**：段 2／段 6 之間 W1 看到的門口停留不另設 NO_SWITCH（A4 沒有可切候選，NO_SWITCH 無意義）。

- **G4／圖 v4：**不需要任何轉移邊。需要 R101 門檻走得到（#256 Q1 UNKNOWN）。
- **渲染量：**4 × 30 × 5 ＝ 600 格；RGB 約 **0.244 GiB**；forward 約 11.1 min。只算 Q5 的話可以只渲染 W1（150 格、約 0.061 GiB），但候選集合與 A4 不同，要另註冊 run（U-V2-8）。
- **主要風險：**
  1. W1 看得到門檻內側（#256 Q4 UNKNOWN）→ 沒有暫失。
  2. 段 6 只露 2 格：linker 能否在 RETURN 後用這 2 格重新接上（#256 Q7(c)：「當前格恰有 1 個符合的真實觀測時開新片段」，未跑 runtime）。接不上時 RR-b 實際上是一次 d ≈ 2.8 s 的暫失。
  3. 門口來回走動時的漏檢（#247 診斷待出）。

### 2.2 V2-LG：長空檔 SWITCH（`LONG_GAP`）

**目的。**採SOUTH明示折線的footprint gap7.4 s測LONG_GAP提案；不是以直線下界證明真實長盲區。#271已算支撐折線，但整段EXT_CAR垂直軸仍在frustum，真正t_L／失聯尚未成立。

鏡頭組 A4。**路線**（seed：EXT_CAR 顯式觀測）

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–5.0 | OUT_W（只在 EXT_CAR 視野） | EXT_CAR | 從車旁走向入口，從 SOUTH_APPROACH 離開 |
| 1 | 5.0–12.4 | 經西門→VEST_W | 實際失聯UNKNOWN | 採§1.2 SOUTH折線；連續通過7.380726 s，參考錨點12.4 |
| 2 | 12.4–24.0 | CORR_W | W1候選 | footprint進入後的實際可見／detector仍待驗 |

查詢 `[0.0, 22.0)`；run 24 s。

**事件**

| 事件 | 類型／類別 | `t_X` | `t_N` | g | 允許鏡頭 | 決策窗（參考） | 進入窗（參考） | 計畫 SEARCHING |
| --- | --- | ---: | ---: | --- | --- | --- | --- | ---: |
| LG-1 | SWITCH／LONG_GAP提案 | 5.0 | 12.4 | 7.4 s | {CAM_W1} | [4.2,13.4) | W1 BLIND [11.8,13.4) | 3（RETURN上界2） |

- 起點5+5.2−6=4.2、終點12.4+1=13.4；若U-D9改回D79，起點6.4，首RETURN名目5.6 s落窗外。n_r_max=ceil((7.4−6.6)/1)+1=2；不是實際已觀察RETURN。
- S3／P-OV3未驗：v4若把SOUTH_APPROACH列入EXT_CAR→EXT_CLEAR的via_exit，CLEAR會是競爭候選；不能寫「只有W1」為PASS。
- **變體（不建議）：**NORTH 出口 g ＝ 9.0 s → `n_s` ＝ 5 > 預算 4，adapter 會拒絕（#244 §2.5）。

**不計分**：EXT → ENTRY、ENTRY → W1（D74，ENTRY 只供 Q1）。

- **G4／圖 v4：**E_OUT_VEST、E_VEST_CORR；T_CAM_EXT_CAR__CAM_W1。
- **渲染量：**4 × 24 × 5 ＝ 480 格；RGB 約 **0.195 GiB**；forward 約 8.9 min。
- **主要風險：**
  1. EXT_CAR 的涵蓋區含 VEST_W（v1 §2.1 風險 2）→ 實際失聯晚於 5.0 s，空檔變短；若 `t_L` 晚到使 g ≤ 5.2 s，類別與計畫不符（#244：類別由計畫決定，不事後改）。
  2. g>7.6 s時理想RETURN上界至少3、SEARCHING至少4；路線若改要重算，不從下界延用原表。
  3. C2相位／C3逐次accepted RETURN已由#266確認；額外漏檢、合法guard與實際計數沒有在本次執行。

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
| LL-1 | RETURN／LONG_LOSS提案 | 6.0 | 9.0 | 3.0 s | [3.0,10.0) | 3（ceil((3−.6)/1)=3；名目6.6／7.6／8.6 s） |

- d3.0可容納1m進退約1.667 s加約1.333 s停留，但遮擋／恢復未驗。d>3.6 s時n_ret_max≥4，預算4仍未核，不能據此宣稱LL已可執行。

**不計分**：無其他事件。

- **G4／圖 v4：**不需要轉移邊；需要門檻走得到。
- **渲染量：**480 格；RGB 約 **0.195 GiB**；forward 約 8.9 min。
- **主要風險：**
  1. W1 看得到門檻內側（同 V2-RR）。
  2. C4已確認每格先probe唯一合法目前觀測可開新segment，D78平移只在L內、不外推3s；本卡是否有合法觀測仍UNKNOWN，不確認同一人。
  3. 可以和 V2-RR 放同一個 run 的不同場次（兩者鏡頭組相同），但 V2-RR 已用滿預算，只能分場次（U-V2-8）。

**依賴 #244：**LOST 分類（`LONG_LOSS`）、多次 RETURN 樣式、U-D2（RETURN 次數不影響 match）。

### 2.4 V2-LT：永久離開（`LOST_TAIL`，預設不做）

**目的。**原 A4-d：目標離開所有渲染鏡頭、不再出現。預期只有 RETURN，直到 `ENDED_BY_LIMIT` 或查詢終點。

鏡頭組 A4。路線：段 0（0.0–8.0）W1 seed，走向 R101；段 1（8.0–20.0）走進 R101 深處不再出來（A4 沒渲染 R101_IN）。查詢 `[0.0, 20.0)`；run 20 s。

| 事件 | 類型／類別 | `t_X` | 決策窗（E3 參考） | 計畫 SEARCHING |
| --- | --- | ---: | --- | ---: |
| LT-1 | NO_SWITCH／LOST_TAIL未核 | 8.0 | 計畫[2.0,20.0)；LIMIT後綴不算覆蓋 | 6（理想8.6–13.6 s；企圖14.6 s第7次才ENDED） |

- 只有如計畫完全離開且不再有合法恢復／SWITCH時才推得上述LIMIT；真正可見性未知。若終止在14.6，補到20的GAP不是執行證據，[14.6,20)必須COVERAGE_MISSING。E2／E3未選，現行v1拒收；不得把全窗0SWITCH寫成正確。
- **G4／圖 v4：**無轉移邊；需要 R101 用途核准（#132 註明尚未成立）。
- **渲染量：**4 × 20 × 5 ＝ 400 格；RGB 約 **0.163 GiB**；forward 約 7.4 min。
- **主要風險：**LIMIT結構與已產hashes由C6確認，但cutoff只取同session已驗ENDED.source_time；圖／scope／prefix完整性仍要另驗。超過建議預算4的例外未核，LT仍預設不做。

**依賴 #244：**LOST 分類（`LOST_TAIL`）、U-D4（E2／E3）。未核定前不做。

### 2.5 V2-PE1：轉角回走廊（依鏡頭進入窗，`STANDARD`）

**目的。**允許兩台目的鏡頭、兩台入口時刻不同的 SWITCH。#256 量到 B4-d 的 W1／W2 入口相距至少 1.2816 m，超過 v1 的 0.8 s 條件；v2 每台各給一窗。

鏡頭組 B4：CAM_W1、CAM_W2、CAM_BRANCH、CAM_R101_IN、CAM_WIDE。**路線**（seed：BRANCH 顯式觀測；固定為 BRANCH，避免 WIDE 的出口在 11–12 m 處造成另一個 `t_X`）

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–6.0 | CORNER（BRANCH∩WIDE） | BRANCH | 停留、轉身 |
| 1 | 6.0–10.4 | CORNER→南側折返點→CORR_W | 實際失聯UNKNOWN | 採BRANCH_TO_W1_THEN_W2_DETOUR；W1先到 |
| 2 | 10.4–22.0 | CORR_W | W1或W2候選 | 實際可見／合法entry待驗，不進R101門 |

查詢 `[0.0, 20.0)`；run 22 s。

| 事件 | 類型／類別 | `t_X` | `t_N(c)` | g | 允許鏡頭 | 決策窗（參考） | 進入窗（參考） | 計畫 SEARCHING |
| --- | --- | ---: | --- | --- | --- | --- | --- | ---: |
| PE1-d | SWITCH／STANDARD計畫 | 6.0 | CAM_W1=9.0；CAM_W2=10.4 | 3.0／4.4 s | {CAM_W1,CAM_W2} | [3.0,11.4) | W1 [8.4,10.0)；W2 [9.8,11.4) | 1 |

- 本卡已選#271明示折返線，故W1先到，不再寫「哪台先到UNKNOWN」；這不是全場景唯一先後。連續差1.4523314912818787 s，參考錨點差1.4 s；W1 footprint通過約.295 s，仍可能沒有合法觀測。
- 兩台 g 都 ≤ 5.2 s，所以是 `STANDARD`；不需要多 RETURN 樣式。

**不計分**：B4-c BRANCH↔WIDE（圖 v3 沒有邊；圖 v4 時由 V2-OV2 測）。

- **G4／圖 v4：**E_W_CORNER；T_CAM_BRANCH__CAM_W1、T_CAM_BRANCH__CAM_W2。圖 v4 下 BRANCH 的出口另有 WIDE（OVERLAP）候選：**P-OV3** 要求 `[6.2, 13.2)` 內 WIDE 看不到目標，否則漏檢時可能切到 WIDE → miss。
- **渲染量：**5 × 22 × 5 ＝ 550 格；RGB 約 **0.224 GiB**；forward 約 10.2 min。
- **主要風險：**
  1. W1 端距離約 16 m、框約 65 px（v1 §3 收據），選到 W1 時可能漏檢或 MATCH_WEAK。
  2. BRANCH∩WIDE 的 footprint 交集只有 1.62 m²（#256 Q5），seed 停留 6 s 時可能走出 BRANCH 視野 → 提早失聯。
  3. 本次只採上述折線；若改路線，逐鏡頭時刻需重算。不是每台有一窗就保證BLIND可見性條件已通過。

**依賴 #244：**依鏡頭進入窗（§2.3、`entry_windows_us`）；圖 v4 時另依賴重疊轉移的候選排序（#248 C5b）。

### 2.6 V2-PE2：出門到室外（依鏡頭進入窗＋`LONG_GAP`）

**目的。**A4-e 的反向問題：#256 量到 EXT_CAR 與 EXT_CLEAR 的入口至少差 2.82 s（1.5 m/s）。v2 每台一窗；因為 EXT_CAR 那台 g > 5.2 s，整個事件歸 `LONG_GAP`（#244 §2.3：任一台 BLIND g_c > G1 → `LONG_GAP`）。

鏡頭組 A4。**路線**（seed：W1）

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–6.0 | CORR_W | W1 | 走向門廳端，從 E_VEST_CORR 離開 |
| 1 | 6.0–9.4 | W1→西門 | 失聯UNKNOWN | 採W1_VIA_WEST_PORTAL_TO_SOUTH，CLEAR連續首進+3.358779 s |
| 2 | 9.4–13.4 | OUT_W | CLEAR候選 | 沿同一反向折線到CAR，連續首進+7.380726 s |
| 3 | 13.4–24.0 | OUT_W | CLEAR／CAR候選 | 完整人體／遮擋與共視停留仍未驗 |

查詢 `[0.0, 22.0)`；run 24 s。

| 事件 | 類型／類別 | `t_X` | `t_N(c)` | g | 允許鏡頭 | 決策窗（參考） | 進入窗（參考） | 計畫 SEARCHING |
| --- | --- | ---: | --- | --- | --- | --- | --- | ---: |
| PE2-e | SWITCH／LONG_GAP提案 | 6.0 | CLEAR9.4；CAR13.4 | 3.4／7.4 s | {CAM_EXT_CAR,CAM_EXT_CLEAR} | [3.4,14.4) | CLEAR[8.8,10.4)；CAR[12.8,14.4) | 3（n_s(7.4)） |

- 理想首次相位6.6 s，首次候選窗仍[6.2,12.2)；若CLEAR確有合法guard，可直接SWITCH，RETURN*允許0次。預算依max g=7.4算3，不能用這個假設宣稱detector已看見。

- **G4／圖 v4：**E_VEST_CORR、E_OUT_VEST；T_CAM_W1__CAM_EXT_CAR、T_CAM_W1__CAM_EXT_CLEAR。圖 v4 下，段 3 的共視停留若漏檢，可能觸發 EXT_CAR↔EXT_CLEAR 重疊切換；落在窗外，只列窗外動作。
- **渲染量：**480 格；RGB 約 **0.195 GiB**；forward 約 8.9 min。
- **主要風險：**
  1. CAR與CLEAR兩向都只有in-frustum證據，真正t_V、早可見與BLIND條件UNKNOWN。U-D6預設fail closed；本次不擅自刪CAR或改分類使它通過。
  2. 反向折線已明示，不再以入站直線距離假設出站；連續入口差4.021947168695503 s，不是舊3.5 s。換線需重算。

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
| OV1-a | SWITCH／STANDARD | 6.0 | {CAM_EXT_CLEAR}（OVERLAP） | [0.6,7.6) | [6.0,7.6) | 1 |
| OV1-b | SWITCH／STANDARD | 16.0 | {CAM_EXT_CAR}（OVERLAP） | [10.6,17.6) | [16.0,17.6) | 1 |

- P-OV1待驗條件：CLEAR要在5.4 s以前有合格支持並持續至12.6 s；反向CAR同理至22.6 s。原路段表6–12.8 s較長停留仍保留，不把靜態frustum當真實全程可見。
- P-OV2：EXT_CAR／EXT_CLEAR 的最後可見時刻要落在 `[t_X − 0.2, t_X]`，需要圖 v4 把重疊轉移的出口區畫在可見範圍邊緣（#248 C5a）。
- P-OV3：OV1-b從CLEAR失聯時可能還有W1（BLIND）競爭候選；首次候選／餘裕窗仍為[16.2,23.2)，此處Δ不刪。#271只給部分frustum外候選點，整段是否排除W1仍UNKNOWN，不打PASS勾號。

- **G4／圖 v4：**新邊 EXT_CAR→EXT_CLEAR、EXT_CLEAR→EXT_CAR（transition ID 依 v4 命名，UNKNOWN）；不需要 E_OUT_VEST／E_VEST_CORR。
- **渲染量：**4 × 26 × 5 ＝ 520 格；RGB 約 **0.212 GiB**；forward 約 9.6 min。
- **主要風險：**
  1. #271已給CLEAR／CAR獨有frustum候選點與共視點，但不是已驗全身／遮擋／6秒連續可見區，也沒有凍結相連整段路線，仍不可宣稱P-OV2／3成立。
  2. O1接受entry區間從t_X起，是否命中只看真正最早合法guard的entry_time；不把舊.4 s換成新的已驗提早失聯容忍。
  3. 共視停留時的漏檢會提早觸發重疊切換。

**D93隔離：**本卡只列OVERLAP_P_OV2_UNVERIFIED獨立分母，不進主比率／STANDARD主分母；O1已由D93定案，不等於P-OV2、G4或U7已核。#271有共視／獨有frustum站位，但整段連續路線與合法觀測未凍結。

### 2.8 V2-OV2：BLOCKED_GEOMETRY（BRANCH→WIDE）

**F2 已修。**CORNER整塊支撐矩形15–17.4×0–2.4 m均在BRANCH／WIDE凸frustum內，FOV-only沒有獨有區。這不是「尚未找到座標」；只有另有合法遮擋證據或改卡／場景才可能成立，並非證明任何遮擋原因都不可能。此卡不列可執行第一批，v4兩方向出口仍polygon=null／MISSING。

鏡頭組 B4。**路線**（seed：BRANCH，目標在 BRANCH∩WIDE）

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–6.0 | CORNER 共視區 | BRANCH | 停留 |
| 1 | 6.0–16.0（歷史佔位） | BLOCKED_GEOMETRY，沒有FOV-only獨有區 | 不承諾可執行 | 需合法遮擋證據或改卡／場景，不能沿既有E_W_CORNER冒充畫面邊緣出口 |

查詢 `[0.0, 14.0)`；run 16 s。

| 事件 | 類型／類別 | `t_X` | 允許鏡頭（kind） | 決策窗（參考） | 進入窗（參考） | 計畫 SEARCHING |
| --- | --- | ---: | --- | --- | --- | ---: |
| OV2-a（不啟用） | BLOCKED_GEOMETRY | 6.0（佔位） | {CAM_WIDE}（歷史） | O1代數[0.6,7.6)，非可評窗 | [6.0,7.6)，非可評窗 | 不宣告預算通過 |

- P-OV3：BRANCH 失聯時候選還有 W1、W2（BLIND）；`[6.2, 13.2)` 兩台都不能看到目標。
- **G4／圖 v4：**新邊 BRANCH→WIDE。
- **歷史佔位用量：**5×16×5=400格、RGB估.163GiB、forward估7.4min；BLOCKED_GEOMETRY，未納可執行第一批或開工量。
- **狀態：BLOCKED_GEOMETRY。**不能列「可執行卡」；遮擋／全身仍UNKNOWN，D93已排除本輪BRANCH/WIDE評分，不因代數窗可寫就升權。

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
| OV3-a（待M1） | SWITCH／STANDARD候選 | 6.0 | {CAM_W2}（OVERLAP） | [0.6,7.6) | [6.0,7.6) | 1（條件式） |

- 走向門廳端而不是轉角：W1：E_VEST_CORR 的其他候選（EXT_CAR、EXT_CLEAR）不在 B4 run，P-OV3 自動成立；走向轉角的話 BRANCH／WIDE 是候選，P-OV3 很難保證。
- **G4／圖v4：**沿用v3既有W1→W2／W2→W1 IDs，僅提overlap語意／出口補充，PENDING_G4／M1；不能重複新增兩條ID。M1未核，本卡不啟用；即使後續開放，D93的獨立報告限制不可自行解除。
- **渲染量：**400 格；RGB 約 **0.163 GiB**；forward 約 7.4 min。
- **主要風險：**W2 端距離約 15 m（v1 §1.5 收據），框小，可能漏檢；W1 正下方是否還在 CORR_W、是否已進 VEST_W（UNKNOWN）。

**依賴 #244：**重疊接手進入窗；圖 v4；G4 M1。

### 2.10 V2-A4-2：較長行走 A4（由 v1 §2.2 搬入，依 D90 重新歸類）

**重新歸類**（v1 原值 → 第二版）：

| v1 事件 | v1 設計 | 問題（來源） | 第二版 |
| --- | --- | --- | --- |
| A4-c1 EXT_CAR→W1 | g3.0 s歷史 | 採SOUTH明示折線7.380726 s | LONG_GAP計畫g7.4 s，真失聯UNKNOWN |
| A4-n1 | NO_SWITCH | — | 不變（`STANDARD`） |
| A4-r1 門檻 | RETURN d 1.2 s | — | 不變（`STANDARD`） |
| A4-e W1 → EXT_* | g 3.0 s，兩台差 ≤ 0.8 s | #256：兩台入口至少差 2.82 s | 依鏡頭進入窗＋`LONG_GAP`（同 V2-PE2） |
| A4-n2 室外經過入口 | NO_SWITCH | 圖 v4 時共視區漏檢可能觸發重疊切換 | 不變；改由獨立場次 S3 seed 在 EXT_CLEAR |
| A4-c2 EXT_*→W1 | g3.0 s歷史 | CLEAR折線連續3.503098 s | S3以CLEAR新seed候選固定原鏡頭，63.5→67.2、g3.7 s；S3重疊政策未核 |

**路線**（時間全部重排）

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–12.0 | OUT_W | EXT_CAR（S1 seed） | 繞車走一段，從 SOUTH_APPROACH 離開 |
| 1 | 12.0–19.4 | 經西門→VEST_W | 實際失聯UNKNOWN | 採SOUTH同一points，19.4為參考W1 footprint錨點 |
| 2 | 19.4–36.0 | CORR_W | W1候選 | 24.0經過門口不進門；完整銜接路線未驗 |
| 3 | 36.0–37.2 | 門檻淺進≤.72m | 失聯待驗 | 同RR的1.2s零停留候選，不要求深入1m |
| 4 | 37.2–44.0 | CORR_W | W1（S2 seed 約 39.0） | 走回門廳端 |
| 5 | 44.0–47.4 | W1→西門 | 失聯UNKNOWN | 採反向SOUTH折線，CLEAR footprint47.4 |
| 6 | 47.4–63.5 | OUT_W計畫段 | S3 CLEAR seed@53.0候選 | CAR footprint51.4；n2計畫56.5；S3/n2政策衝突未核 |
| 7 | 63.5–67.2 | 西門→W1 | 失聯UNKNOWN | 採CLEAR折線；連續到達約67.003098，參考錨點67.2 |
| 8 | 67.2–77.0 | CORR_W | W1候選 | 完整人體／實際停留可見性仍待驗 |

場次：**S1 `[0.0, 41.0)`**（seed EXT_CAR）、**S2 `[39.0, 55.0)`**（seed W1）、**S3 `[53.0, 75.0)`**（seed EXT_CLEAR）。run 77 s。

| 場次 | 事件 | 類型／類別 | `t_X` | `t_N` | g／d | 允許鏡頭 | 決策窗（參考） | 進入窗（參考） | SEARCHING |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | ---: |
| S1 | c1 | SWITCH／LONG_GAP計畫 | 12.0 | 19.4 | 7.4 s | {CAM_W1} | [11.2,20.4) | W1[18.8,20.4) | 3 |
| S1 | n1 | NO_SWITCH／STANDARD | 24.0 | — | — | — | [20.4,30.0) | — | 0 |
| S1 | r1 | RETURN／`STANDARD` | 36.0 | 37.2 | 1.2 s | — | [31.2, 38.2) | — | 1 |
| S2 | e | SWITCH／LONG_GAP計畫 | 44.0 | CLEAR47.4；CAR51.4 | 3.4／7.4 s | {CAM_EXT_CAR,CAM_EXT_CLEAR} | [41.4,52.4) | CLEAR[46.8,48.4)；CAR[50.8,52.4) | 3 |
| S3（未核） | n2 | NO_SWITCH／PROPOSED_UNKNOWN | 56.5 | — | — | — | 代數[53.0,61.2)，政策待決 | — | 0（不能據此核准S3） |
| S3（未核） | c2 | SWITCH／STANDARD計畫 | 63.5 | 67.2 | 3.7 s | {CAM_W1} | [61.2,68.2) | W1[66.6,68.2) | 1（條件式） |

- 每場次 SEARCHING：S1 4（＝預算上限）、S2 3、S3 1。#244 U-D10 若改回 ≤ 3，S1 要把 r1 移到另一場次。
- 更新間距：c1→n1為4.6 s≥S4的2；n1→r1為13.2 s≥9；n2→c2為10.7 s≥9。名目r1搜尋36.6、c2搜尋64.1（63.5是連續計畫錨點、實際grid相位UNKNOWN）可在計畫上到達NO_SWITCH窗尾；不是已產生coverage。
- 查詢／seed候選保留S1[0,41)、S2[39,55)、S3[53,75)，seed鏡頭CAR@0、W1@39、CLEAR@53，全部真實observation_id=MISSING。S1末窗38.2+2≤41；S2末窗52.4+2≤55；S3末窗68.2+2≤75。各seed都須新controller request，不在同session換seed假重設輪數。
- **S3/n2保持PROPOSED／UNKNOWN：**原本一處寫「兩場次查詢可以重疊，但重疊段不放事件」，另一處原文則是「[39,41)、[53,55)不放事件的錨點；n2窗起點53與S2尾段重疊，事件只在S3」。這兩句不能在本次偷偷改成同義；若「事件」含完整決策窗，n2的[53,61.2)仍占[53,55)，現配置不通過；若只指不重複錨點／事件集合，需U6／U7明示採此解釋。本次不選、不宣稱全卡通過。可另提重排query／seed／n2時刻使整窗避開重疊，重算後再核。

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
| B4-b W2→轉角 | g3.0 s歷史 | 採W2_TO_BRANCH_THEN_WIDE | BRANCH14.2／WIDE14.6，g3.2／3.6 s |
| B4-d 轉角 → 走廊 | 兩台差 ≤ 0.8 s | #256：W1／W2 入口至少差 0.8544 s（1.5 m/s） | 依鏡頭進入窗（同 V2-PE1），`STANDARD` |
| B4-e 穿門 | g 2.0 s | 門口盲區 UNKNOWN（#256 Q4） | 不變 |
| B4-r1 室內 | RETURN d 1.2 s | 視野外區域 UNKNOWN | 不變（`STANDARD`） |
| B4-f出門 | 單一50.5 s是歷史佔位 | #271短線W2先到.166667／W1 .591585，不能把兩者當相同t_N | 兩台最終t_N=UNKNOWN，不擅填50.5以外的新值，不宣告STANDARD／預算通過 |
| B4-n2 | NO_SWITCH | — | 不變 |
| B4-b2 | g3.0 s歷史 | 同b的W2折線 | BRANCH70.2／WIDE70.6；需另確認當時原鏡頭確為W2 |

**路線**

| 段 | 時間 (s) | 區域 | 預期追蹤鏡頭 | 走位 |
| --- | --- | --- | --- | --- |
| 0 | 0.0–11.0 | CORR_W | W2（S1 seed） | 4.0 經過 R101 門口不進門；走到轉角接近區，從 W2 下方離開 |
| 1 | 11.0–14.6 | →CORNER | 失聯UNKNOWN | b採W2折線，BRANCH14.2／WIDE14.6 |
| 2 | 14.6–21.5 | CORNER | b可落BRANCH或WIDE | d之前另提BRANCH@18.0的新request seed，不假設b一定選BRANCH |
| 3 | 21.5–25.8 | →CORR_W | 實際entryUNKNOWN | d採BRANCH折返線，W1 24.4／W2 25.8 |
| 4 | 25.8–31.0 | CORR_W | W1或W2候選 | 與R101門檻之銜接／停留未驗 |
| 5 | 31.0–33.0 | 門檻 | — | 穿門 |
| 6 | 33.0–41.0 | R101 | R101_IN（S2 seed 約 37.0） | 室內走動 |
| 7 | 41.0–42.2 | R101 視野外一角（UNKNOWN） | — | 1.2 s 後走回 |
| 8 | 42.2–49.0 | R101 | R101_IN | 走回門口 |
| 9 | 49.0→UNKNOWN | R101→走廊 | UNKNOWN | 50.5保留歷史佔位，兩台footprint最終時刻與門檻停留未選，不將短線時間代入 |
| 10 | UNKNOWN–67.0 | CORR_W | 原鏡頭UNKNOWN | n2計畫57.0，但其窗左端與b2前W2來源須等f決定，不能聲稱全程可見 |
| 11 | 67.0–70.6（條件式） | →CORNER | 若原鏡頭W2 | 同b折線，BRANCH70.2／WIDE70.6；source不符則需新seed／改卡 |
| 12 | 70.6–80.0（未核） | CORNER | BRANCH或WIDE候選 | 全身／停留／全卡80s可行性未驗 |

**未核三request工程候選（不重設同一session）：**S1a `[0,18)` W2 seed@0含n1／b；S1b `[18,36)` BRANCH seed@18含d／e；S2 `[37,78)` R101_IN seed@37含r1／f／n2／b2。三個真實seed IDs全部MISSING。這解決d採BRANCH折線卻由b任選原鏡頭的歧義，但不替f或b2後段source作決定。run80 s只是保留的未核配置，不是整卡時序PASS。

| 場次 | 事件 | 類型／類別 | `t_X` | `t_N` | g／d | 允許鏡頭 | 決策窗（參考） | 進入窗（參考） | SEARCHING |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | ---: |
| S1a | n1 | NO_SWITCH | 4.0 | — | — | — | [0,8.2) | — | 0 |
| S1a | b | SWITCH／STANDARD計畫 | 11.0 | BRANCH14.2／WIDE14.6 | 3.2／3.6 s | {CAM_BRANCH,CAM_WIDE} | [8.2,15.6) | BRANCH[13.6,15.2)；WIDE[14.0,15.6) | 1 |
| S1b（新seed候選） | d | SWITCH／STANDARD計畫 | 21.5 | W1 24.4／W2 25.8 | 2.9／4.3 s | {CAM_W1,CAM_W2} | [18.4,26.8) | W1[23.8,25.4)；W2[25.2,26.8) | 1 |
| S1b | e | SWITCH／門檻待驗 | 31.0 | 33.0（歷史計畫） | 2.0 s | {CAM_R101_IN} | [27.0,34.0) | [32.4,34.0) | 1（僅計畫） |
| S2 | r1 | RETURN | 41.0 | 42.2 | 1.2 s | — | [37.0, 43.2) | — | 1 |
| S2 | f | SWITCH／UNKNOWN | 49.0 | W1=UNKNOWN；W2=UNKNOWN；50.5僅歷史 | UNKNOWN | {CAM_W1,CAM_W2}待核 | `[max(43.2,min_c t_N(c)−6),max_c t_N(c)+1)`＝UNKNOWN | 每台`[t_N(c)−.6,t_N(c)+1)`＝UNKNOWN | UNKNOWN |
| S2 | n2 | NO_SWITCH／UNKNOWN | 57.0 | — | — | — | `[max(end_f,51.0),63.0)`；左端UNKNOWN，不能假定非空 | — | 0（coverage未驗） |
| S2 | b2 | 若W2原鏡頭的STANDARD計畫 | 67.0 | BRANCH70.2／WIDE70.6 | 3.2／3.6 s | {CAM_BRANCH,CAM_WIDE} | [64.2,71.6)（source條件式） | BRANCH[69.6,71.2)；WIDE[70.0,71.6) | 1（source未確認） |

- S1a計畫SEARCHING1、S1b計畫2；S2只有r1／條件式b2的2個佔位，f輪數／總數UNKNOWN，不再宣告「全部STANDARD、每場3次」。f未定或b2 source不符時整個S2不交正式adapter。
- 間距重算：d後到25.8→e33.0為7.2 s≥S2 7.0；d的21.5離S1b query left18為3.5 s；S1a末窗15.6+2≤18、S1b末窗34+2=36、S2條件式末窗71.6+2≤78。查詢無重疊事件，但S2中間未知窗不可因此算PASS。
- B4 f需要誰決定什麼：U7核卡時選較長出門動線／門檻停留或逐鏡頭時刻；本次不選50.5以外的值。若f可選W1，b2的W2來源也不保證，需另明示W2新request／seed或修改卡片；不從任選候選自造source。r1的1.2 s亦未證有可見區外短動線，不能把#271長5.131277m的支撐候選塞進1.2 s。

**不計分**：同 v1 B4-1（B4-a W1↔W2、B4-c BRANCH↔WIDE、CORR_N／R102）。

- **圖／scope風險：**W2→W1經E_W_CORNER的競爭路徑在v3已存在，不是等v4＋M1才冒出；若該scope准入，b／b2不能只憑預期目的集合假定P-OV3通過。v4語意／M1另待G4，原圖ID不重複新增。
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
| V2-OV1 | — | — | — | D93另列、不入主比率 | — | — |
| V2-OV2 | — | — | — | BLOCKED_GEOMETRY，不啟用 | — | — |
| V2-OV3 | — | — | — | ✔（＋M1） | — | — |
| V2-A4-2 | ✔ | ✔ | ✔ | 圖 v4 時 | ✔（3 場次） | — |
| V2-B4-2 | — | — | f／source仍UNKNOWN | v3亦須查競爭候選 | 3request工程候選，未核 | — |

---

## 3. 渲染量

係數沿用 v1：RGB 63,976 KiB／150 格（#132 舊 A 素材，`docs/engineering/R004_SCENE_CHANGE_PROPOSAL.md` §5），forward 1.108406209 s／格。**不是新場景的量測值**；r004 每格大小、渲染時間、`.blend`／索引／暫存大小 UNKNOWN（#256 Q8）。

| 組合 | 卡 | 格數 | RGB（估） | forward（估） |
| --- | --- | ---: | ---: | ---: |
| 甲（推薦，未核） | RR＋LG＋PE1＋OV1 | 2,150 | 0.874509 GiB | 39.717889 min |
| 甲＋LL（未核） | 甲另加LONG_LOSS | 2,630 | 1.069748 GiB | 48.585139 min |
| RR＋LG（未核） | 不含重疊接手 | 1,080 | 0.439288 GiB | 19.951312 min |
| 其餘短卡工程合計 | RR／LG／LL／PE1／PE2／OV1；排除LT、OV2、OV3 | 3,110 | 1.264988 GiB | 57.452388 min |
| 加待M1的OV3 | 上列再加OV3，仍非已核候選 | 3,510 | 1.427687 GiB | 64.841763 min |
| 長卡佔位估算 | A4-2 77 s＋B4-2 80 s；未證全卡時序可行 | 3,540 | 1.439890 GiB | 65.395966 min |

以上只是歷史係數乘camera×seconds×5fps，未含index／暫存峰值；新r004實測MISSING。舊13GiB df只屬2026-10-27歷史，不能當目前門檻。D99預先授權仍須U7、v2劇本凍結與開始時即時df≥9GiB；低於8GiB全部停。改卡／增卡是否涵蓋原授權須另確認，不能從估算或這份文件自行開工。

---

## 4. 第二批（只列清單，不展開）

D90 第 4 項：需要新場景版本、磁碟與渲染授權。最終名單等 #247（漏檢診斷）與 #253／#256（可行性）。

| 項目 | 內容 | 前置 |
| --- | --- | --- |
| B2-1 門廳補盲鏡頭 | 在 VEST_W 加追蹤鏡頭，把 EXT↔W1 的長盲區拆成兩段短盲區（與 V2-LG 對照） | 新場景版本（名稱 UNKNOWN）；新鏡頭校正與 catalog；圖 v5（或 v4 擴充）；G4 逐邊；渲染授權 |
| B2-2 CORR_N 北段／R102 路線 | 目前 E_CORNER_N、E_PORTAL_R102 沒有轉移（v1 §1.1） | 新轉移與鏡頭涵蓋；R102 進路線要推翻 #132 的排除；G4 |
| B2-3 短暫遮擋型 NO_SWITCH（原 B4-d ①） | 目標在同一鏡頭內被遮擋 ≤ 0.4 s 後出現 | 場景要有遮擋物（r004 走廊有沒有：UNKNOWN）；#247 漏檢率；新場景版本 |
| B2-4 超過G_max長空檔 | g>10.6 s超過理想單一事件搜尋上限；E2未核，不是已有可評保證 | U-D4或補盲候選，不改v1 |
| B2-5 多人干擾 | 藍衣干擾者在非目的候選鏡頭（v1 Q9，#256 說暫不排定） | 路線座標；G4；新場景版本 |

共同前置：(1) 新場景版本與其 catalog／校正凍結；(2) 磁碟：D2 用量拆分完成、可用空間在停止線以上並有渲染＋索引＋暫存的實測係數；(3) 使用者的渲染授權（L2-6）；(4) 遮擋物或新鏡頭的 Blender 可行性檢查（不渲染）。

---

## 5. V1–V10 已交答覆與本次處置（#271）

以下只引用#271@c5aa674的已交靜態結果，不重跑static/grid、renderer或detector；其JSON仍是原ecf1ce46 bytes。本次僅選作計畫候選與重算參考窗，沒有把frustum／支撐升成實際可見性。

| 題 | 本次採用／更新 | 仍未驗證 |
| --- | --- | --- |
| V1 門檻 | RR已選淺進≤.72m零停留；LL3s可容納1m往返＋約1.33s停留；LT僅引R101_PORTAL_TO_DEEP支撐候選 | 門牆遮擋、用途、全身、物理可達性與真失聯UNKNOWN |
| V2 SOUTH長空檔 | 採§1.2固定points；LG t_N12.4、A4 c1 19.4，g7.4 | 整段CAR垂直軸in-frustum，真正t_L／BLIND未成立；v4 CLEAR競爭候選P-OV3未驗 |
| V3 分鏡頭進入 | 採BRANCH折返線，W1先到；PE1 9.0／10.4，B4 d24.4／25.8 | 非唯一場景先後；W1 footprint只有約.295s觀測餘裕，沒有有效detection保證 |
| V3 出門f | 只記R101短線W2 .166667／W1 .591585的已知差異 | 最終t_N都UNKNOWN；50.5為歷史佔位；需U7選較長動線／停留或改逐鏡頭時刻 |
| V4 反向出門 | 採反向SOUTH points；PE2 9.4／13.4，A4 e47.4／51.4 | CAR/CLEAR雙向都只有frustum，真正t_V、早可見與BLIND條件UNKNOWN |
| V5 重疊獨有區 | EXT／W1-W2有靜態frustum站位；OV2的CORNER全共視，BLOCKED_GEOMETRY | OV1整段路線／P-OV2／3未凍結；OV3另等M1；遮擋仍可能改變結果，不宣稱任何原因都不可能 |
| V6 P-OV3 | 不再用勾號假PASS；v4 SOUTH→CLEAR與PE1→WIDE競爭候選逐案列出 | 逐方向出口、全段合法可見性與排除時窗未驗 |
| V7 室內角落 | #271有(5.2,-4.8,0)的frustum外支撐點與5.131277m候選線 | 往返至少約8.55s，不能拿來證B4 r1的1.2s；碰撞／全身／用途UNKNOWN |
| V8 seed／run | 先一卡一run；每場新request、顯式鏡頭observation seed；B4為d另提BRANCH新seed | 所有真實observation IDs MISSING；不在同session換seed歸零；長卡政策／source仍未核 |
| V9 用量 | 新時刻未超原短run長度，§3按camera×seconds×5重算 | r004實測RGB／forward／index／暫存峰值MISSING，舊df不能開工 |
| V10 圖v4 | v3既有W1↔W2兩ID保留；EXT/BRANCH新增4個ID後26個唯一ID，draft envelope非runtime authority | G4／M1、BRANCH/WIDE出口仍MISSING；W2→W1經E_W_CORNER競爭路徑在v3就存在 |

---

## 6. 可直接提請使用者的U7選項（尚未核定）

**要使用者決定：第一批卡片範圍是否採甲，或以下替代範圍？**D99只給資料來源／有條件預授權，不代替本題U7與劇本凍結。選項的計畫窗與未驗條件都須照實保留；沒有本文件自選的結果。

| 選項 | 內容與重算用量 | 優點 | 限制／缺點 |
| --- | --- | --- | --- |
| **甲（推薦，未核）** | RR＋LG＋PE1＋OV1；2150格／RGB估.874509GiB／forward估39.717889min | 四類短卡，無需長卡跨場次整合；保留已修F1／F3候選 | RR-b合併未定、LG／PE1實際BLIND未驗、OV1 P-OV2／3未驗；OV1只獨立分母，不進主比率 |
| 甲＋LL（未核） | 再加LL；2630格／估1.069748GiB／48.585139min | 多涵蓋LONG_LOSS | 多480格；LL遮擋與合法接回未驗；是否擴及D99原授權需明示，不能自動渲染 |
| 只RR＋LG（未核） | 1080格／估.439288GiB／19.951312min | 規模較小，避開重疊接手部分 | 不含依鏡頭窗與重疊類；RR-b／LG真正失聯仍待驗，不能因卡少就稱已可行 |

V2-OV2在摘要、§2.8與本候選清單一致為**BLOCKED_GEOMETRY，不列可執行選項**；V2-OV3等M1，LT預設不做。A4-2／B4-2不是甲的一部分；它們的S3政策／f時刻／source未解前不交正式adapter。

先一卡一run；同鏡頭組合併仍須固定唯一run／clock／scope與新hash、各場新request，不減camera×seconds×fps，還可能增加銜接段。本次沒有核准合併，也不把W1-only最小run提案當成既有A4。

---

## 7. UNKNOWN 與待決

| # | 項目 | 誰 | 影響 |
| --- | --- | --- | --- |
| U-V2-1 | RR-b（兩次暫失間只露 2 格）要合併成一個 `LONG_LOSS` 還是兩個 `STANDARD` | #244（使用者核定） | V2-RR 的計分與預算 |
| U-V2-2 | 公式已對齊#258 f19fbcf；D93／D94已定，其他U-D與UK-8方法仍待核 | 使用者U6／U7 | 參考窗不等於已核script；14名稱不增刪 |
| U-V2-3 | 本稿已選#271明示points並更新footprint時刻；完整銜接／可達／真實t_L／t_V仍UNKNOWN | 後續計畫與合法觀測 | 不能把計畫g稱為已驗盲區 |
| U-V2-4 | 各重疊對的單獨可見區、v4 出口區畫法 | Codex（V5、V10；#248 C5） | V2-OV1–OV3 能否成立 |
| U-V2-5 | 門檻／R101 視野外區域 | Codex（V1、V7） | V2-RR、V2-LL、V2-LT、r1 |
| U-V2-6 | B4 b／b2的W2 source與競爭候選；v3已有W2→W1路徑，不只v4＋M1 | U7卡片／G4逐scope | source不符需reseed或改卡，不能任選W1後還套W2路線 |
| U-V2-7 | C3逐次RETURN／C4每格先probe的產品行為已確認；本卡實際guard／遮擋仍UNKNOWN | #266現行回覆；後續合法觀測 | 不再寫產品接回介面未知，也不宣稱本場已成功 |
| U-V2-8 | 一卡一 run 還是同鏡頭組合併；只渲染 W1 的最小 run 是否可註冊 | 使用者；Codex（run 註冊） | 渲染量、run 數 |
| U-V2-9 | r004 每格 RGB 大小、渲染與索引時間 | Codex（V9） | §3 |
| U-V2-10 | #247 漏檢診斷結果 | Codex（D1） | 預算 4 的餘裕夠不夠；最終名單（D90 第 4 項） |
| UK-8／D79 U2 | t_L／t_V能否只由計畫路線＋靜態校正得到；D98-6只確認名稱，方法未核 | 使用者U6 | 真正可見性仍UNKNOWN；不進推論、不自行作評分時刻 |

| 既有事件／配置 | 仍須誰決定什麼 | 本稿處置 |
| --- | --- | --- |
| A4 S3/n2 | U6／U7確認「重疊段不放事件」是完整窗，或僅不重複錨點／事件集合；不是新增第15項已採規則 | 兩句原文衝突保留，S3/n2 PROPOSED／UNKNOWN，整卡NOT_ACCEPTED |
| B4 f／後段source | U7選較長出門路線／停留、各camera t_N及b2前原鏡頭；50.5以外不擅填 | f各窗與S2預算UNKNOWN；三request只解d原鏡頭，未核／seed IDs MISSING |

### 7.1 回修定位與偏離提案（不自行採用）

| 複核項 | 回修狀態 | 尚未接受的界線 |
| --- | --- | --- |
| F1 | **已修計畫候選**：§1.2選points、LG／PE1／PE2與長卡逐鏡頭時刻／窗／計數／seed表更新 | 全卡時序未驗，A4重疊政策及B4 f／source未解，不能宣稱全卡通過 |
| F2 | **已修**：摘要、§2.8路線／風險與§6清單一致BLOCKED_GEOMETRY | 不過度推成所有遮擋原因都不可能 |
| F3 | **已修**：RR選淺進≤.72m、零停留，保留1.2s往返；A4 r1同樣約束 | 深度／時間算術相容不等於W1真的看不到或物理可達 |

**偏離提案：A4長卡場次重疊語意。**現配置S2=[39,55)、S3=[53,75)，n2窗[53,61.2)；原稿同時有「重疊段不放事件」與「只不放錨點、n2窗可在S3」。若採完整窗限制，現配置不能同時滿足；本文件不把後一句默默升成放寬規則。

1. **推薦：先不納長卡，按完整窗避重疊重新提query／seed／n2時刻。**只改未核工程候選，重算後交U7核；優點是不用放寬評估邊界，缺點是不能保留現S3時刻直接凍結。
2. 維持現配置，請使用者明示允許只排除錨點／重複事件集合、完整窗可占query重疊段。優點是少改時序；缺點是評估語意需核定，U6／U7未明示前仍fail closed。
3. 暫緩A4-2／B4-2，第一輪只核§6短卡選項。優點是甲不依賴這個跨場次歧義；缺點是不涵蓋較長行走／彙總；B4 f與source也仍待後續卡片決定。

以上是提請決定的候選，不是本稿的選擇；未解前不產正式adapter／script或進入render。卡片文稿可供審查，長卡驗收維持NOT_ACCEPTED。

---

## 8. 來源

**決定（GitHub 留言）**
- D93：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434812845 （EXT pair／O1、獨立分母；BRANCH/WIDE不評）
- D94：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6434821818 （Line2 STANDARD RETURN≤1.6，拒絕1.6<d<1.8；D90分類不改）
- D98-6：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6461263003 （14名稱含UK-8，方法未核）
- D99：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6461277019 （資料來源／有條件預授權，U7仍未定）
- D90：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423575212 （LOST 由評估端分類、5.2 s／1.8 s 邊界；失聯後接手、v4 加重疊轉移；第一批／第二批）
- D89：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423194857 （A4-1＋B4-1；A4-2／B4-2 移入 Line 2；NO_SWITCH 讓位）
- D87：https://github.com/Polalalabear/amidst/issues/93#issuecomment-6421557959 （第二條線）
- D79、D67、D65、D73、D74、D77：見 D79 文件與 v1 §1.2。

**檔案（路徑＋commit＋bytes SHA-256）**
- 情境卡v1（#306 A11）：`docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md` @ mainline `0d785992a57f1f5db142957bdafa65dfadf1f1a2`，`015201556f550ab67dbbebead35916db426a3b6a05066ffc94c928696900ddbd`；只引用，不改Line1核定範圍。
- 評分規則v2：`docs/evaluation/Q5_SWITCH_EVAL_V2_DESIGN.md` @ #258 `f19fbcfd2ff64c483fedb00bd9be2e72e97a2af3`，`b07c26a0489256737bf536a07895bcb5de41616241de5b761b33fdab4960e846`（PROPOSED；只D93／D94限定已定，U6其他待決不代選）。
- 明示折線／靜態回覆：`docs/engineering/R004_L2_STATIC_FEASIBILITY_20261027.md` @ #271 `c5aa674ce772b7f49e813c89ab6fa415064e22ca`，`2f615fd7db6c66bbe622c1d1cfb58612c260a9803439dae7b9510a86757d45e6`；同名JSON bytes `ecf1ce4615da7faf6a908e1a98ec329ac62814b9f162af60b6085f945f1baeab`。其原static執行結果只作已交引用，本次沒有重跑。
- 可行性檢查 #256：`docs/engineering/R004_D89_FEASIBILITY_20261027.md` @ `origin/codex/r004-d89-feasibility` `dd0e69bb7775789eaa94436ead1726dfb2d13823`，`82719479cc33e9d2b825ed37ccf7b4df1999a8aaa2dbba1ed6111183f444e192`（Q2、Q3、Q5 的距離下界；Q7 controller 原始碼判讀；Q8 磁碟）
- D79文件（#306 A12）：`docs/evaluation/Q5_DECISION_WINDOW_D79.md` @ mainline `0d785992a57f1f5db142957bdafa65dfadf1f1a2`，`20b5df9d6948ce4845ebb2e12be7ddae1aa6f6adac087f4d41e3df2489745d1e`。
- 圖 v3、契約、評分器 #222、容量係數：同 v1 §8（`camera_graph_v3.json` `9896be11…`；契約 `b700bf86…` @ `680ca35`；`q5_switch_eval.py` `0fd1ef68…`；`R004_SCENE_CHANGE_PROPOSAL.md` §5）。
- 磁碟：本 session `df -h /System/Volumes/Data` 可用 13 GiB（2026-10-27）。

**議題**：#245（本文件）、#244（評分規則 v2）、#248（controller 契約）、#246（長時間軸）、#247（漏檢診斷）、#249（工程小場景，渲染延後）、#251（第二條線總覽）、#253（情境卡 v1）、#256（v1 可行性）。

**沒有用到、也沒有讀的來源：**GT、renderer 軌跡／visibility／depth、任何 RGB、`.blend`、#211 private producer。
