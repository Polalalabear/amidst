# E6 新 12 段：路線與干擾者時序設計（#742，D396；待 Opus 審查）

**狀態：設計草案，尚未錄正式資料。** Issue：[#742](https://github.com/Polalalabear/amidst/issues/742)（#732 的前提 G1＋G2）。分支 `claude/feat-e6-routes`。付費 0，沒有呼叫任何模型或 API。身分 `UNCONFIRMED`。
機器可讀版本：`configs/evaluation/e6_routes_v1.json`（釘住規格 `e6_scenarios_spec_v1.json` 的 SHA-256 `5eff6cb4…b074a83`，本設計**沒有改規格**）。設計檢查輸出：`docs/evaluation/E6_ROUTES_DESIGN_CHECK_20261127.json`。

## 1. 做法

- **引擎與錄製**：沿用 E3 的錄製管線（LIVE WebGL，`scene.glb`、`character.glb`、8 鏡頭、5 Hz、320×180）。路線用 `script_operator` 的 `walk`／`run`／`hold`／`hold_until` 步驟（行走 1.2 m/s、跑 2.5 m/s）驅動 A 側玩家 T；干擾者是場景 run 內的腳本演員（waypoint 線性內插）。E3 路徑的行為不變：`generate.mjs` 只多一行（路線自帶 `run` 時用它），`record.mjs` 只多一個環境變數 `E3_SCENARIO_JSON`（沒設就和原來一樣）。
- **新增檔案**：`e6_routes.mjs`（讀 JSON、編譯成路線與 run）、`generate_e6.mjs`（產輸入錄製）、`e6_design_check.mjs`（設計檢查）、`e6_visibility_map.mjs`（可見性 ASCII 地圖，設計輔助）。
- **設計檢查是什麼**：用正式的人群模擬（`createCrowd`）加上既有的 GT 可見性函式 `groundTruthVisible`（和 LIVE 頁寫進 A-log 的同一個函式，三個身體點射線＋靜態牆），每 0.2 s 取樣。它只用來檢查「路線在這個場景裡是否照設計發生」，**輸出是設計檢查，不是任何推論、排名或評分的輸入**。可見性不含演員互相遮擋（和 E3 相同）。
- **規格裡的決策點時間只是計畫**（規格 `actual_gt_status: PENDING_RECORDING`）；正式的決策點在錄製後由 GT 規則定稿（`check_e6_data_separation.py --mode formal` 驗）。設計檢查的標準：每個計畫決策點在 ±3.0 s 內有對應的 GT 事件，且該事件後 3 s 視窗的 GT 狀態等於計畫狀態。

## 2. 場景可走區域與盲區（來自 GT 可見性地圖，0.5 m 格）

| 區域 | 範圍（Blender 公尺） | 用法 |
| --- | --- | --- |
| 室外 | x −15.2…−3.2，y −6…8；西門 (−3.2, 0)，門框 y ±0.7 | 3 台鏡頭（ENTRY、EXT_CAR、EXT_CLEAR）大多重疊；**西南盲區** (−12.5, −4)；西北 (−14.5, 6)、(−12, 7) |
| 前廳＋走廊 W | x −3.2…15，y 0…2.4；SCREEN_W 在 x 10.4–10.55、y 0–0.8（行經 x≈10.4 須 y ≥ 1.2） | W1、W2 幾乎全覆蓋；**前廳南袋** (2, −1.35)（盲）；走廊東端盲區 (13–14, 0.5–2.0)（SCREEN_CORNER_N 後） |
| R101 | x 5…11，y −5…0；門 (8, 0) 寬 1.2 | R101_IN 看 y > −3；**深處** (8, −4) 盲 |
| 轉角＋走廊 N | x 15…17.4，y 0…12 | BRANCH 看轉角；WIDE 看 y 5–11.5；**SCREEN_N 後** (15.4, 4.9) 盲；**北端** y > 12 盲 |

W2→BRANCH 之間在走廊東端一定經過約 1 m 的盲區，所以「轉角分支交接」都帶約 1 s 的短暫消失。

## 3. 每段設計（完整 waypoint 見 JSON；表內為設計檢查結果）

「計畫 → 實現」是計畫決策點時間與設計檢查找到的 GT 事件時間（秒）；括號內狀態變更表示規格的 `gt_regime` 與實現不同（見設計選擇 DC3）。盲區欄是 T 對 8 台鏡頭都不可見的區間（長度）。最近距離是 T 與干擾者同鏡頭可見時的最近 m。最大速度是干擾者最大線段速度（m/s）。

| 段 | 開場鏡頭 | 規格起點 → 採用起點 | 干擾者 | T 盲區 s（長度） | 最近距離 | 干擾者最大速度 | 決策點 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E6-S01 | EXT_CAR | [-13.2, -1.2] → [-11.0, -2.0] | 紅衣 A「VEST_CROSS」 | 3.2–6.6（3.4） | 1 | 1.45 | DP1 BLIND_REAPPEAR：計畫 6 → 6.6<br>DP2 SIMILAR_CROSSING：計畫 13 → 13.8<br>DP3 POST_SPLIT_REACQUIRE：計畫 20 → 20<br>DP4 CAMERA_HANDOFF：計畫 25.5 → 25.6 |
| E6-S02 | EXT_CLEAR | [-12.5, 4.2] → [-11.1, 4.2] | 紅衣 A「CORR_W_MEET_PARALLEL」 | 17.4–23.4（6.0） | 1.51 | 2.05 | DP1 CAMERA_HANDOFF：計畫 7.5 → 7<br>DP2 SIMILAR_PARALLEL_SPLIT：計畫 14 → 16.4<br>DP3 BLIND_REAPPEAR：計畫 21.5 → 23.4<br>DP4 DISTRACTOR_STILL_VISIBLE_KEEP_T：計畫 27 → 27 |
| E6-S03 | R101_IN | [2.2, -3.2] → [7.0, -2.2] | 紅衣 A「PORTAL_SWAP_STAY_CORR_W」 | 3.4–10.6（7.2）, 24.0–25.0（1.0） | 0.87 | 1.54 | DP1 PORTAL_EXIT_BLIND：計畫 6.5 → 6.5<br>DP2 BLIND_REAPPEAR_WITH_SIMILAR：計畫 12 → 10.6<br>DP3 SIMILAR_CROSSING：計畫 19 → 19<br>DP4 CORNER_BRANCH_HANDOFF：計畫 25 → 25 |
| E6-S04 | W1 | [-3.0, 1.4] → [-1.1, 0.5] | 紅衣 A「COUNTERFLOW」 | 11.4–16.8（5.4） | 1 | 1.8 | DP1 SIMILAR_CROSSING：計畫 6 → 6.6<br>DP2 BLIND_ABSTAIN_DISTRACTOR_PRESENT：計畫 13 → 13<br>DP3 BLIND_REAPPEAR：計畫 19.5 → 16.8<br>DP4 POST_REAPPEAR_STABILITY：計畫 26 → 26 |
| E6-S05 | BRANCH | [12.2, 1.2] → [14.3, 0.45] | 紅衣 A「SCREEN_LOOP」 | 6.4–11.8（5.4） | 0.8 | 1.33 | DP1 OCCLUSION_BLIND_WITH_SIMILAR：計畫 7 → 7<br>DP2 BRANCH_REAPPEAR：計畫 13.5 → 11.8<br>DP3 SIMILAR_CROSSING：計畫 20.5 → 19.4<br>DP4 POST_SPLIT_REACQUIRE：計畫 26.5 → 26.5 |
| E6-S06 | WIDE | [16.4, 9.2] → [16.4, 9.2] | 紅衣 A「NORTH_EXIT」 | 7.4–12.4（5.0）, 18.2–19.4（1.2） | 0.98 | 1.37 | DP1 SIMILAR_CROSSING：計畫 5.5 → 4.6<br>DP2 BLIND_REAPPEAR：計畫 12.5 → 12.4<br>DP3 CAMERA_HANDOFF：計畫 19 → 17.6<br>DP4 TRUE_DEPARTURE_OR_KEEP_T：計畫 25 → 25 |
| E6-S07 | ENTRY | [-7.2, 0.2] → [-7.2, 0.2] | 藍衣 C（非紅） | 2.4–9.4（7.0） | 1.02 | 1.64 | DP1 BLIND_REAPPEAR：計畫 8 → 9.4<br>DP2 CAMERA_HANDOFF：計畫 14.5 → 14<br>DP3 NON_SIMILAR_CROSSING：計畫 20.5 → 22.6<br>DP4 PORTAL_REACQUIRE：計畫 25.5 → 25.5 |
| E6-S08 | W2 | [8.4, 0.6] → [8.4, 0.6] | 無 | 2.0–7.6（5.6）, 15.8–21.0（5.2） | — | 0 | DP1 BLIND_REAPPEAR：計畫 7 → 7.6<br>DP2 CAMERA_HANDOFF：計畫 13.5 → 12.2<br>DP3 SCREEN_OCCLUSION_RETURN：計畫 20 → 21<br>DP4 POST_RETURN_STABILITY：計畫 25.5 → 25.5 |
| E6-S09 | WIDE | [16.2, 4.8] → [16.2, 4.8] | 無 | 2.6–7.4（4.8）, 13.6–21.4（7.8） | — | 0 | DP1 SCREEN_OCCLUSION_RETURN：計畫 7.5 → 7.4<br>DP2 BRANCH_HANDOFF：計畫 14 → 13<br>DP3 BLIND_REAPPEAR：計畫 20.5 → 21.4<br>DP4 POST_RETURN_STABILITY：計畫 26 → 26 |
| E6-S10 | R101_IN | [0.8, -4.6] → [9.5, -2.2] | 無 | 12.2–19.8（7.6） | — | 0 | DP1 PORTAL_HANDOFF：計畫 6.5 → 8.4<br>DP2 CAMERA_HANDOFF：計畫 13 → 12<br>DP3 BLIND_REAPPEAR：計畫 19.5 → 19.8<br>DP4 OUTDOOR_REACQUIRE：計畫 25.5 → 25.5 |
| E6-S11 | BRANCH | [14.2, 1.8] → [14.5, 1.17] | 無 | 2.2–7.6（5.4）, 17.6–30.2（12.6） | — | 0 | DP1 BLIND_REAPPEAR：計畫 7.5 → 7.6<br>DP2 CAMERA_HANDOFF：計畫 14 → 12.2<br>DP3 TRUE_DEPARTURE_ABSTAIN：計畫 20 → 20（TRUE_DEPARTURE→FULL_BLIND）<br>DP4 POST_DEPARTURE_ABSTAIN：計畫 25 → 25（TRUE_DEPARTURE→FULL_BLIND） |
| E6-S12 | W1 | [0.5, 0.9] → [0.5, 0.9] | 無 | 3.6–7.2（3.6）, 14.8–18.2（3.4）, 22.0–27.2（5.2） | — | 0 | DP1 BLIND_REAPPEAR：計畫 6.5 → 7.2<br>DP2 PORTAL_HANDOFF：計畫 13 → 11<br>DP3 BLIND_REAPPEAR：計畫 19.5 → 18.2<br>DP4 BRANCH_REACQUIRE：計畫 25.5 → 27.2 |

全部 12 段：路線走完、無卡住（`script_stall` 0）、起點 2 s 內只有 T 被看到、T 前 2 s 一直可見、開場鏡頭在 t=0 看得到 T、**48 個計畫決策點全部找到對應 GT 事件**（≥ 40 的門檻有餘裕；同段內決策點 tick 不重複）。

## 4. 干擾者 6 種時序（S01–S06；「新紅衣」＝演員 A）

「新紅衣」＝ D124 的 `A` 外觀：和 T **同一紅上衣材質**、淺灰長褲、沒有背包與胸前徽章（不用橘紅的 B，不改成像素相同的 T）。出生都在 t ≥ 2.5 s、藏在盲區裡，所以 t=0 的種子判定（只能有一個有色人物）不受影響；腳本演員在 run 長度內不循環（run 長度 = 計畫長度 + 8 s）。

| 段 | 種類 | 出現（可見）時間 | 路線 | 和目標的相對位置 |
| --- | --- | --- | --- | --- |
| S01 | `NEW_ACTOR_RED_VEST_CROSS` | 2.5 s 出生在前廳南袋，10.2 s 起可見 | 南袋→走廊北線 y 1.8 西行→出西門 | T 東行走廊南線 y 0.8；13.8 s 錯身（最近 1.0 m，W1／W2 同見）；之後 A 往西出去 |
| S02 | `NEW_ACTOR_RED_CORR_W_MEET` | 2.5 s 在南袋，11 s 起可見 | 南袋→走廊南線 y 0.6 與 T 並行→約 x 5–8 轉進 R101 | 並行 ≈ 1.0–1.5 m 約 4 s；16.4 s 拉開 > 3.5 m；之後 A 留在 R101（R101_IN 看得到）＝「干擾者仍可見」 |
| S03 | `NEW_ACTOR_RED_PORTAL_SWAP` | 2.5 s 在走廊東端盲區，7.8 s 起可見 | 東端→走廊 (12, 2.0) **站定到結束** | T 從 R101 出門東行 y 1.2，19 s 經過 A（最近 0.87 m）；A 一直在走廊可見（T 在 R101 盲區時，相似人物在走廊） |
| S04 | `NEW_ACTOR_RED_COUNTERFLOW` | 2.2 s 東端盲區，3 s 起可見 | 東端→走廊北線 y 1.8 **西行 1.7 m/s**→出西門 | T 東行 y 0.8；6.6 s 迎面錯身（最近 1.0 m）；T 進 R101 盲區（11.4–16.8 s）時 A 仍在走廊／室外可見＝「盲區且干擾者在場」 |
| S05 | `NEW_ACTOR_RED_SCREEN_LOOP` | 2.5 s 在走廊 N 北端盲區，4.6 s 起可見 | 北端→走廊 N 南行（6–9 s 經過 WIDE）→轉角 (16.8, 1.0)→再北行 | T 在 SCREEN_CORNER_N 後盲區（6.4–11.8 s）時 A 經過 WIDE；19.4 s T 南行、A 北行迎面錯身（最近 0.8 m，WIDE 同見） |
| S06 | `NEW_ACTOR_RED_NORTH_EXIT` | 2.5 s 在轉角盲區，2.6 s 起可見 | 轉角→走廊 N 北行→北端盲區（14 s 起不可見） | T 南行 x 16.0 與 A 在 4.6 s 錯身（最近 0.98 m，BRANCH／WIDE 同見）；之後 A 北去離開 |

S07 用**藍衣 C**（非紅，路線：走廊東端→北線西行→出西門，T 與 C 在 22.6 s 錯身，最近 1.02 m）；S08–S12 沒有其他人（規格：一半沒有相似人物，6/6）。

## 5. 設計選擇（請 Opus 判斷；每條寫了我採用的做法）

- **DC1　起點修正（7/12 段）。** 規格的 `start_xy` 有 7 個和引擎不相容：S03、S10 在所有地板之外（R101 的 x 範圍是 5–11，規格寫 x 2.2、0.8）；S04 在牆的淨空內；S01、S05 看不到規格寫的開場鏡頭；S02、S11 對 8 台鏡頭都是盲區（種子需要 t=0 可見）。我**保留規格欄位不動**（`spec_start_xy`），另在 JSON 用 `start_xy` 放採用的起點，原因逐段寫在 `start_adjustment`：移到離規格點最近、地板上、離牆 ≥ 0.35 m、開場鏡頭看得到的格子（距離 0.7–3.3 m；S10 為手選 R101 內的格子）。其餘 5 段（S06–S09、S12）不動。`check_e6_data_separation.py` 看規格欄位，起點仍和 E3 的 (−10, −0.4)、(4, 1) 不同；採用的起點離所有 E3／hardset 起點 ≥ 0.5 m（測試強制）。
- **DC2　計畫時間是軟的，容差 ±3.0 s。** 路線是真人速度走出來的，無法讓規格每個 t_plan 剛好對上；設計檢查用事件偵測器（`reappear`：盲區 3–10 s 後回來；`handoff`：看了 ≥ 2 s 的鏡頭不再看到 T 而別台仍看到，或 ≤ 1.5 s 短消失後回到不相交的鏡頭集合；`cross`：同鏡頭可見且 ≤ 2.0 m 的距離局部最小；`split`：近距離 ≥ 2 s 後 > 3.5 m；`blind`：3 s 視窗全盲；`visible`：視窗內可見），每個規格決策點對應一種（表在 JSON 的 `dp_kinds`）。偵測器只用於設計檢查；正式決策點仍由錄製後的 GT 規則定稿。**請判斷 ±3 s 與偵測器定義是否可接受**；預登若要求更嚴，我調整路線。
- **DC3　`TRUE_DEPARTURE` 在現有引擎做不出來。** 玩家 T 在人群模擬裡不會消失（`present` 恆為真），所以規格的 S11-DP3、DP4（`gt_regime: TRUE_DEPARTURE`）只能是「T 走到所有鏡頭外」＝GT 衍生的 `FULL_BLIND`：S11 的 T 走到走廊 N 北端 y 12.8（17.6 s 起盲，到結束 12.6 s）。`check_e6_data_separation.py` 會拿 GT 衍生的狀態比對宣告的狀態，所以這兩點正式要宣告成 `FULL_BLIND`（類型名 `TRUE_DEPARTURE_ABSTAIN`／`POST_DEPARTURE_ABSTAIN` 不變）。替代方案：在人群模擬加「T 消失」功能（要改 crowd 與錄製重播的驗證，影響 E3 以外的路徑，我不建議）。**請決定接受 FULL_BLIND 或要求引擎改動。**
- **DC4　「新紅衣」用既有的 A 外觀，不新增角色資產。** 和 T 同一紅上衣，靠灰長褲與沒有背包區分；A、B、C 以外的新外觀會需要改 `character.glb`（資產，不改）。S01–S06 只放 1 個紅衣干擾者（不放橘紅 B）；S07 用藍衣 C 當「非紅行人」。這讓干擾者在 HSV 色彩閘門上和 T 不可分（設計目的）。
- **DC5　規格文字的「盲區」對應到實際盲格。** 規格寫「VEST_W blind」等，實際盲區是 §2 列的那幾格（前廳南袋、走廊東端、R101 深處、SCREEN_N 後、北端、室外西南）。每段的盲區位置由路線決定；表中 T 的主要盲區是 3.4–7.8 s（規格寫 3.5–6.0 s；S11 尾段 12.6 s 是 DC3 的長離開），另有 S03 的 1.0 s、S06 的 1.2 s 短消失，是走廊東端的轉角交接。盲區 3–10 s 的才算 E3 的接回事件（`min_blind_s 3、max_blind_s 10`）。
- **DC6　開場可見至少 2 s。** B1 的種子在第一次 ACQUIRE 的 tick；為了不讓種子失敗，5 段原本一開場就進盲區的路線（S01、S03、S09、S11、S12）都先站定 2 s。
- **DC7　干擾者速度。** 為了讓相遇時間貼近計畫，A 的最大線段速度到 1.3–2.05 m/s（S02 的 A 轉進 R101 那段 2.05 m/s，S04 迎面 1.80 m/s），高於 N6 行走片段的 1.2 m/s；腳本演員用線性內插，不受片段速度限制，但看起來會是快步走。若要求自然速度，需把相遇點移後、整段拉長，會超過規格的 30–32 s。**請判斷是否接受。**
- **DC8　時長。** 沿用規格 30–32 s；最後一步是 `hold_until(計畫時長)`，`tail_s = 0`，錄製長度 = 計畫長度（5 Hz，150–160 tick）。`run` 的長度多 8 s，避免腳本演員在錄製內循環。
- **DC9　人群解析器的相互讓步。** T（玩家）與干擾者同走廊時，人群模擬會讓位或等待（`pause_*`）；所有 12 段設計檢查中 `script_stall` 為 0，錄製後仍要查 A-log 的 `forced_overlap`／`pause_player_i`，有就要改路線再錄（本診斷 S04 沒有）。
- **DC10　一段一個「獨立情境」。** 12 段各是一個劇本家族（E6-F01…F12），開場區域與鏡頭各不相同（室外西、室外北、R101、走廊、轉角、走廊 N、前廳外、走廊東、走廊 N 中、R101 深、轉角東、走廊中），干擾者時序六種互不相同。同家族合併的有效獨立單位 = 12 ≥ 8。

## 6. 開發資料與正式資料的分離

- 診斷 3 段是舊 E3 的 E3-A1、E3-B1、E3-C1（規格 `diagnostic_cases`，只用於選組，不入正式判定）；正式 12 段的 case_id、family_id、起點、路線、干擾者時序都是新的。
- 跑 `python3 scripts/evaluation/check_e6_data_separation.py --mode draft`：`PASS: E6 data separation verified (mode=draft, old_e3=16, diag=3, formal=12, unique_dps=48, effective_units=12, similar=6/6)`。錄製後的 `--mode formal --artifact-root <dir>` 會逐檔驗 SHA、GT tick 與 GT 衍生狀態；**那是正式錄製後的關卡，本 PR 沒跑**（沒有正式資料）。
- 本設計不讀任何 E3 結果、B1／AO／R-N 輸出或模型輸出；設計檢查只用場景幾何、鏡頭與 GT 可見性（評分用資料）。路線在看到任何新資料的結果前固定；JSON 的 `status` 在 Opus 審過前是 `DRAFT_DESIGN_PENDING_OPUS_REVIEW`，審過後才錄正式資料並凍結 SHA。

## 7. 和 E3 路線不重疊的證明（測試 `frontend/live-mode/test/e6_routes.test.mjs` 強制）

1. 12 個起點都不在任何 E3（含 `E3_ROUTES`、`REAPPEARANCE_ROUTES`）或 hardset 路線起點 0.5 m 內。
2. 對 31 條 E3／重現／hardset 路線，逐一算「連續相同 waypoint 序列的最長長度」：E6 與任一條的最大值 = **1**（只共用單一地點，例如門口座標），測試要求 ≤ 2。
3. 干擾者時序是新寫的 waypoint，不使用 A4-1／B4-1 的 A、B、C 腳本。

## 8. 驗證結果

- `node --test frontend/live-mode/test/*.test.mjs`：158 項，156 通過、0 失敗、2 略過（原有的略過）；其中新測試 5 項全過（含需要 LOCAL 資產的設計檢查）。
- 設計檢查：12/12 `all_ok`（見 §3）。重現：`node scripts/evaluation/e3_cases/e6_design_check.mjs OUT.json <live-assets-dir>`。
- **1 段診斷錄製（E6-S04，無頭 Chrome，自己的 loopback port，沒有偵測器、模型或 API）**：LOCAL `local/evidence/e6-routes-dryrun-20261127/`；三次瀏覽器重播的邏輯雜湊相同（`a7751024…c644b`），156 次擷取 × 8 鏡頭 = 1248 張影格；頁面寫的 A-log 與設計檢查一致（T 盲區 11.4–16.8 s、A 3.0 s 起可見、最近距離 1.00 m）。目視確認 CAM_W1 第 33 tick（6.6 s）同框兩個紅衣人（T 有背包，A 灰長褲）錯身，CAM_R101_IN 第 70 tick（14 s）房內無人（T 在盲區）。
- 重現指令：

```bash
A=local/data/live-assets-20261115; OUT=local/evidence/e6-routes-dryrun-20261127
node scripts/evaluation/e3_cases/generate_e6.mjs $OUT $A E6-S04
E3_SCENARIO_JSON=$OUT/e6-scenario.json node scripts/evaluation/e3_cases/record.mjs $OUT $A E6-S04
```

## 9. LOCAL 產出

`local/evidence/e6-routes-dryrun-20261127/`（1 段診斷，約 10 MB、含 pixels 1248 張）；可用上列指令重建，不可入 repo。SHA-256：`E6-S04.case.json` `839e0de6…a346`、`e6-scenario.json` `844c9aa7…31d4`、`browser-replay.json` `52a43bc8…2225`、`input-replay.json` `7fd9f829…ed70`。

## 10. 審過之後

1. Opus 對 DC1–DC10 逐條決定；若改路線，我重跑設計檢查（`all_ok` 必須維持）。
2. 審過：JSON `status` 改 `FROZEN_ROUTES_V1`、記錄 JSON 的 SHA-256；用 `generate_e6.mjs` 產 12 段輸入錄製、`record.mjs` 錄正式資料，再跑 `check_e6_data_separation.py --mode formal`（需使用者同意錄製與外傳；錄製本身零費用）。
