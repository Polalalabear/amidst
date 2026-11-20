# LIVE 室外覆蓋缺口：量測與方案比較（#630）

日期 2026-11-20。Claude（Sonnet 5.5 / high）。範圍：只做量測與方案文件，不改場景、鏡頭、graph，不渲染、不付費。GT（`gt_visible`、`hardset_check` 的失聯點）只用在事後評分，沒有進任何推論路徑。

## 結論（先讀）

1. **缺口是真的，但位置與成因和 #630 開頭的描述不完全一樣。** 9 段難題（H1／H4／H5，after 組）共 545 個 T 可見 tick，**151 個（27.7%）沒有任何 graph 鏡頭看得到 T**（before 組 28.8%）。其中 **82 個在室外院子，69 個在室內**（H5 的門廳停留點、H4-3／H5-3 的走廊 (13–14, 1.1)）。#630 寫的「y > 5.7 沒有鏡頭」不精確：y > 5.7 只有 x < −10 的西北角是盲區，x > −10 有 EXT_CLEAR。H5 的缺口根本不在室外。
2. **大部分「看不到」是難題集故意要的。** H1 要求躲 ≥ 15 s（H1.a），H5 要求目標躲起來。路線的躲藏點 P1（室外西側鏡頭背後）就在盲區裡。所以「約一半 tick 沒鏡頭」不是 bug，只有 hard point（失聯開始）那一刻附近的覆蓋才影響評分。
3. **真正受覆蓋影響的是 H1-1 與 H1-3 的 hard point 前 3 s。** 這兩段 T 走 (−10, −0.4) → (−13, −1)，在 x < −11 只剩 **CAM_W2（27.6 m，框 13–15 px）** 看得到（EXT_CAR 的視野是朝東，x = −13 這條線在它側面）。after 組這 3 s 窗口：H1-1 0/1、H1-3 0/7 tick 跟對（都是 `WRONG_PERSON`）；H1-2 路線反過來走，hard point 在 EXT_CLEAR 3.4–4.0 m，5 tick 中 4 tick `ON_TARGET`。9 段共 35 個窗口 tick，14 m 內沒有任何 graph 鏡頭的只有 **8 個，全部屬於 H1-1／H1-3**。
4. **其餘 7 段的前 3 s 失敗不是覆蓋造成的。** H4-2、H5-1、H5-2、H5-3 窗口內 T 在 2–6 m 有 graph 鏡頭看得到，仍是 `WRONG_PERSON`；這是起始鎖錯人與 #608 的重新取得（#619 結論第 4 點），改覆蓋不會修好。所以「難題點前 3 s 跟對沒改善 → 覆蓋缺口」只對 2/9 段成立。
5. **推薦：先改路線（方案 b），不動鏡頭與 graph。** 方案 b 屬 Claude、不需要場景改動。要不要把 CAM_ENTRY 納入追蹤（方案 a，要推翻 D74／D81）、要不要動鏡頭（方案 c）是使用者的決定；本文給數字，不建議現在做。

## 方法（幾何模型，不渲染）

- 鏡頭：`docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json` 的 8 台內外參（Blender `camera_to_world`、fx／fy、960×540）。
- 可見判定：沿用 `groundTruthVisible`（`frontend/live-mode/src/world.mjs:96`）：地面點 z = 0.15／0.9／1.6 m 三點，至少 2 點投影在畫面內且在鏡頭前方；2D 視線不穿過 `occluders_full_height` 的任一線段。
- **模型驗證**：把 9 段 after 組每個 T tick 的模型結果和 A log 記錄的 `gt_visible`（只看「有沒有 graph 鏡頭」）逐 tick 比對，**545/545 一致**（`cases.*.model_gt_agree_no_cam`）。
- 院子＝`R004_EXTERIOR_FLOOR`：x −15.2…−3.2、y −6…8（168 m²），格點 0.25 m。「近」＝graph 鏡頭水平距離 ≤ 14 m（#619：14 m 以上的框很小、紅標籤率低）。graph 鏡頭＝`camera_graph_v3.json` 的 7 台（不含 CAM_ENTRY）。
- 反事實：新增／重新對準的鏡頭都用同一個模型算；T 位置用 A log 的 `xy`（評分用）。

## 缺口數字

### 每台鏡頭的院子覆蓋（不計遮擋以外因素）

| 鏡頭 | 在 graph | 院子可見面積 m² |
| --- | --- | --- |
| CAM_EXT_CAR（−13, −6，朝東偏北） | 是 | 91.2 |
| CAM_EXT_CLEAR（−13, +7，朝東偏南） | 是 | 69.9 |
| CAM_W2（14.4, 2.1，隔門看西） | 是 | 22.1 |
| CAM_ENTRY（−2.5, 0.4，門內看西） | **否** | 89.2 |
| BRANCH、R101_IN、W1、WIDE | 是 | 0 |

兩台室外鏡頭都在 x = −13 朝東，所以 **x < −13 的條帶與它們背後沒有近鏡頭**。

### 未覆蓋區域（graph v3 七台）

- 院子 168 m² 中 **54.1 m²（32.2%）** 沒有任何 graph 鏡頭；位置：西北 x −15.2…−9.8、y 0.5…8（36.2 m²），西南 x −15.2…−10.3、y −6…0.5（17.9 m²）；另有 y −2…0.5、x < −10.7 的 W2 單獨條帶（只有 27 m 外的 W2，算有鏡頭但不是「近」，不在上述面積內）。
- 加上 CAM_ENTRY 後剩 **17.4 m²（10.4%）**，剩下的是西北角 y > 4.8。

0.5 m 一格，north 在上，`#`＝沒有鏡頭，數字＝看得到的 graph 鏡頭數（x 由 −15.2 往東，每字元 0.5 m；每列 y 為列中心）：

```
y=  7.8 ###########1111112222222
y=  5.8 #########111111222222222
y=  3.8 #########111122222222222
y=  1.8 ###########1222222222222
y=  0.2 ##########22223333333333
y= -0.8 111111111222222233333322
y= -1.8 111111112111111111222222
y= -2.8 #######11111111111122222
y= -4.8 #########111111111111122
```

（每隔一列取樣；完整地圖見腳本輸出 `ascii_graph`。）

### 難題集 9 段：T 在缺口的 tick（after 組，graph 讀法）

| 案 | tick | 無 graph 鏡頭 | 只有 ENTRY 看得到 | 缺口（t 起點／長度／位置） | 缺口在 |
| --- | --- | --- | --- | --- | --- |
| H1-1 | 58 | 26 | 3 | 8.5 s／18.6 s／(−13, 0.1)→(−10.3, 7.8) | 室外西北 |
| H1-2 | 61 | 18 | 4 | 19.1 s／15.4 s／(−10.4, 7.8)→(−13, 0.7) | 室外西北 |
| H1-3 | 68 | 24 | 8 | 26.8 s／16.0 s／(−13, 0.3)→(−10, 7.8) | 室外西北 |
| H4-1 | 54 | 4 | 4 | 18.1 s／3.0 s／(−10.5, 1.3)→(−10.9, 2.7) | 室外 |
| H4-2 | 53 | 10 | 8 | 27.1 s／4.2 s／(−10.7, 3.7)→(−10.5, 1.3) | 室外 |
| H4-3 | 70 | 1 | 0 | 35.4 s／1 tick／(14.3, 1.1) | 室內走廊 |
| H5-1 | 54 | 26 | 0 | 15.5 s／16.0 s／(2.6, −0.5)→(2.1, −1.2) | 室內門廳 |
| H5-2 | 61 | 22 | 0 | 15.7 s／16.4 s／(2.5, −0.7) | 室內門廳 |
| H5-3 | 66 | 20 | 0 | 28.5 s／12.2 s／(13.6, 1.1) | 室內走廊 |
| 合計 | 545 | **151（27.7%）** | 27 | | 室外 82／室內 69 |

跨四組（before、after、before_rep、after_rep）的比例：28.8%、27.7%、45.6%（n = 136，只有 4 案）、28.6%（n = 84，只有 3 案）。#630 引用的 22/42、27/58、27/53 是 **before 組**的 H1-1、H1-2、H5-1；after 組是 26/58、18/61、26/54，兩組都是 H1／H5 約一半以下，H1-2 只有 30%。

### CAM_ENTRY 不在追蹤圖的影響

- 27/151（18%）缺口 tick 只有 ENTRY 看得到；全在 H1／H4（H5 為 0，門廳 ENTRY 也看不到）。
- 排程：ENTRY 不在 graph，`scheduler.plan` 只有 `INITIAL_SEARCH`／`LOST_ALL`（`available` 全選）會掃它；H1-1 after 組 58 次排程中 ENTRY 只有 2 次。
- 加入 ENTRY（模擬）：院子未覆蓋 54.1 → 17.4 m²（−68%）、無鏡頭 tick 151 → 122（−19%）、hard point 前 3 s 14 m 內無鏡頭 8 → 0。
- 偵測品質未知：N6 量測的 ENTRY 偵測率 19%（`docs/design/LIVE_MODE_GAME_DESIGN_V2.md` §6.3，非 LIVE 設定）；`detector.py` 對 ENTRY 用 min score 0.05（雜訊風險）。本次沒有量 LIVE 在 ENTRY 上的偵測率。

### hard point 前 3 s 的覆蓋與結果（after 組，graph 讀法）

| 案 | hard point（t, 最後可見位置／鏡頭） | 窗口 tick | 最近 graph 鏡頭 m | 跟對（ON_TARGET） |
| --- | --- | --- | --- | --- |
| H1-1 | 8.5 s，(−13, −1)／W2 | 1 | 27.6 | 0／1 |
| H1-2 | 19.1 s，(−9.7, 7.8)／EXT_CLEAR | 5 | 3.4–4.0 | 4／5 |
| H1-3 | 26.8 s，(−13, −0.2)／W2 | 7 | 27.5 | 0／7 |
| H4-1 | 18.1 s，(−10.1, 1.0)／EXT_CAR | 6 | 7.2–7.6 | 6／7 |
| H4-2 | 27.1 s，(−10.7, 4.4)／EXT_CLEAR | 5 | 3.4–3.5 | 0／5 |
| H4-3 | 35.4 s，(12.4, 1.2)／W2 | 3 | 2.2–3.1 | 1／1 |
| H5-1 | 15.5 s，(3.2, 0.3)／W1+W2 | 3 | 4.7–6.0 | 0／3 |
| H5-2 | 15.7 s，(3.1, 0.1)／W1+W2 | 3 | 4.9–5.9 | 1／3 |
| H5-3 | 28.5 s，(12.4, 1.2)／W2 | 2 | 2.2–3.1 | 0／3 |

（跟對欄取自 `hardset_check.json` 的 `common_pre.statuses`；窗口 tick 與其第 4 欄取自本腳本的模型，H5-3 兩者的窗口 tick 數不同〔2 vs 3〕是 hard point 邊界取捨，不影響結論。）

結論：覆蓋最差（只有 27 m 外的 W2）的 H1-1／H1-3 全部失敗；覆蓋好的案有成功也有失敗，失敗原因另有來源。樣本小（單次、不成對），只能當方向，不是統計證據。

## 方案比較

所有「改善」都是同一個幾何模型的反事實，不是實測；基準＝graph v3 七台。欄位＝院子未覆蓋面積／545 個 tick 中無鏡頭／其中 14 m 內無鏡頭／hard point 前 3 s 的 35 個 tick 中 14 m 內無鏡頭。

| 方案 | 院子未覆蓋 m² | 無鏡頭 tick | 14 m 內無鏡頭 tick | 前 3 s 14 m 內無 | 改哪些檔案 | 誰 | 風險 | 要使用者決定 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 基準 graph v3 | 53.0 | 151 | 174 | 8 | — | — | — | — |
| **b. 改 H1-1／H1-3 路線**（先走北段、讓 hard point 落在 EXT_CLEAR 3–4 m；同 H1-2 型態） | 53.0（不變） | 151（不變） | 不變 | **8 → 0**（H1-1／H1-3 的 hard point 改到近覆蓋；以 H1-2 路線輪廓為準，未重跑） | `configs/evaluation/live_hardset_v1.json`、`frontend/live-mode/src/hardset_routes.mjs`、`docs/evaluation/LIVE_HARDSET_V1.md`、重算答案表 | Claude（評估） | H1-1／H1-3 與 H1-2 路線變得相似，變化減少；要重確認 H1.a（躲 ≥ 15 s）與 H1.b（跳 ≥ 8 m）；還沒有正式錄製，成本低 | 否（難題集 v1 尚未錄製；若要改 D330 的路線決定則要） |
| a. CAM_ENTRY 納入追蹤圖（或只在排程補掃，不改 graph） | 17.4 | 122 | 123 | **0** | 納入 graph：`configs/q1q5/graphs/r004/camera_graph_v3*.json`（SHA 釘住）、`tracking_scope_v3*.json`、`authority_pins_v1.json`、`scheduler.py`、graph 轉移（ENTRY 轉移現為 `UNKNOWN`）；只補掃：`src/amidst/live_mode/scheduler.py` | 納入 graph：契約／使用者；補掃：Claude | 推翻 D74／D81；ENTRY 偵測率 19%、min score 0.05 雜訊；追蹤器若切到 ENTRY，`active` 不在 adj → `GRAPH_SCOPE_UNKNOWN` 全鏡頭掃描；hardset 的「graph 讀法」定義要重寫 | **要**（D74／D81） |
| c3. 重新對準 CAM_EXT_CAR（yaw 約 75°、pitch 20°，位置不動） | 31.8 | 69 | 82 | 0 | N6 `cameras.three.json`（LOCAL 資產）、camera catalog（D84 凍結，`calibration_sha256`）、場景 preset | Codex（鏡頭幾何） | 改掉 A4-1／B4-1 基準場景裡 EXT_CAR 的畫面（基準 AC 與已渲染素材用舊朝向）；H4 路線原本靠 EXT_CAR；live 與 catalog 不一致 | **要**（動凍結的鏡頭） |
| c2. 新增室外鏡頭（南邊界約 (−8.2, −6, 3 m)，朝 135°，面向西北；本模型的面積最佳點，不是可行安裝點） | 3.8 | 72（其中 69 為室內） | 73 | 0 | camera catalog（要新增第 9 台）、`cameras.three.json`、graph 新增節點與轉移、tracking scope、scenario、偵測門檻 | Codex（場景／鏡頭）＋契約 | 動到多個凍結檔（catalog、graph、scope）；安裝點在場景裡是否可行 `UNKNOWN`；渲染素材要重做 | **要**（場景改動） |
| a + c2 | 0.5 | 72 | 73 | 0 | 兩者合計 | | | **要** |

補充：
- c1「按 tick 最佳」的新鏡頭是 (−15.2, 5, 3 m) 朝東：無鏡頭 tick 151 → 54，但 14 m 內仍 120、前 3 s 仍 8（它離 H1 hard point 太遠），表示「拉近 tick 數」與「修好 hard point」不是同一件事，不建議。
- 69 個室內缺口 tick（H5 門廳、H4-3／H5-3 走廊）不受任何室外方案影響，也是難題集故意的（H5 要躲起來）。
- 隔門看穿的視線已算進模型（門洞不是遮擋），例如院子鏡頭 c1 能隔門看到門廳但距離 > 18 m。

## 推薦與要決定的點

1. **先做方案 b（Claude，無需決定）**：H1-1／H1-3 改成和 H1-2 同型的路線（hard point 落在近覆蓋），或維持路線但在報表標註「hard point 前只有 W2 27 m」，不把這兩段列入「難題點前 3 s 跟對」的比較（該指標本來就是依模式標註、不再是重錄條件）。再 #608 合併後用 `far_target_smoke`／`far_target_score` 配對重量。
2. **#608（重新取得）才是另外 7 段的主因**，不是覆蓋；不要因本文去動鏡頭。
3. **需要使用者決定的只有一件**：要不要把 CAM_ENTRY 當成可追蹤的鏡頭（方案 a）。本文數字：院子缺口 −68%、hard point 前 3 s 14 m 內盲點 8 → 0，但 ENTRY 偵測率與雜訊未量，且推翻 D74／D81。我的建議是**暫不推翻**；若要試，先做「排程補掃、不改 graph」並實測 LIVE 的 ENTRY 偵測率，再決定。
4. **方案 c（動鏡頭）不建議現在做**：除非方案 b 與 #608 完成後 H1 仍然不穩，且需要 Codex 與使用者同意（動凍結的 catalog）。

## 沒做到、未驗證

- 所有方案效果都是幾何模型反事實，沒有重跑 LIVE 煙霧測試，也沒量追蹤器在新路線／新鏡頭下的行為。
- 方案 b 的 H1.a／H1.b（躲 ≥ 15 s、跳 ≥ 8 m）只以 H1-2 的路線輪廓推論，沒有為新路線重跑 `hardset_check`；注意從 W2 單獨條帶（y −2…0.5、x < −10.7）穿過會把「看不到」打斷（graph 讀法 W2 算看得到）。
- 前 3 s 跟對的樣本是單次、不成對、n 很小，不能做統計結論。
- 偵測／紅標籤品質沒有進模型（只有幾何可見性與 ≤ 14 m 門檻）；新鏡頭的安裝可行性、遮擋（樹、車）未建模，車輛視為不遮擋（只用牆與屏風線段）。
- LIVE 使用的 N6 `cameras.three.json`（LOCAL，SHA-256 `6deb31b032f4a7ce2e1734db07b666d118e1b0de17e8e37be7008814ba0f4f41`，路徑 `data/live-assets-20261115/cameras.three.json`）與 repo geometry 的 8 台鏡頭位置逐一一致（差 < 1e-3 m）；朝向與內參沒有逐項比對（模型與 `gt_visible` 545/545 一致，間接支持）。

## 重現

```bash
# 在 repo 根目錄；需要 LOCAL 證據（只讀）
PYTHONPATH=src python -B -m amidst.evaluation.live_coverage_gap \
  --evidence local/evidence/far-target-619-20261119 --set after --out /path/to/gap.json
PYTHONPATH=src python -B -m pytest tests/evaluation/test_live_coverage_gap.py -q
```

輸出 JSON 欄位：`per_camera_yard_area_m2`、`yard_uncovered_graph(_plus_entry)`、`ascii_graph`、`cases.*`（含缺口段）、`pre_window_3s`、`option_table`、`uncovered_ticks_by_region`、`route_profiles`、`reaim`、`no_graph_cam_ticks_by_set`。

LOCAL 證據（只讀，未修改）：

| 路徑（相對 `local/`） | SHA-256 |
| --- | --- |
| `evidence/far-target-619-20261119/SHA256SUMS`（全部檔案清單） | `212849ec34d9db5796003d34a1968a238170695db2ead27adffa50f38a207a6a` |
| `evidence/far-target-619-20261119/after/H1-1.a-log.json` | `d287aeddb081045669d7e6185776780226ceb0e240291b3959cd9955b6d481c3` |
| `evidence/far-target-619-20261119/after/hardset_check.json` | `69e1b8c04ccf67025c70e6236301d06d6a554d0fd1e9ea410912d0024b8d924d` |

其他 8 段的 a-log 與 before／rep 各組檔案雜湊都在上述 `SHA256SUMS`。Repo 內輸入：`docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json`（SHA-256 `73e263819c38da1acd5ccc347bc07f788544fc7a95813e1aa25a0ecbe4c18ae3`）、`configs/q1q5/graphs/r004/camera_graph_v3.json`（content SHA-256 `57f70c94…`）。
