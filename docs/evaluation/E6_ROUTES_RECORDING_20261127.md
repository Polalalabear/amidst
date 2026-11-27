# E6 正式 12 段錄製紀錄（#742，D399；錄製前設計偏離與關卡結果）

Opus 設計審查 APPROVE（D399，[PR #745 留言](https://github.com/Polalalabear/amidst/pull/745#issuecomment-7206630872)）後錄製。LIVE WebGL 無頭 Chrome、自己的 loopback port，沒有偵測器、模型或 API；付費 0。身分 `UNCONFIRMED`。**錄製在任何組別輸出之前完成；本檔記錄的是輸入資料與關卡，沒有評分。**

## 凍結與產出
- 路線凍結：`configs/evaluation/e6_routes_v1.json` `status: FROZEN_ROUTES_V1`，SHA-256 `22bee772c79c470a3e3558f76a038828050a6ed037f7733a205d7ea321146983`（含偵測器定義、`dp_kinds`、`detector_source` 釘住 `e6_design_check.mjs` 的 SHA；測試強制）。
- 錄製後的凍結規格副本：`configs/evaluation/e6_scenarios_frozen_v1.json`（SHA-256 `5bab27666bddcf4c4e089f8e442d19d263540e3ff158ca17ad8565c6e601b338`；原規格 `e6_scenarios_spec_v1.json` 不動，副本只填 `actual_*`、路徑與 SHA；`start_xy` 仍是規格值，實際錄製起點在 `start_xy_recorded`）。
- LOCAL `local/evidence/e6-formal-20261127/`：118 MB、14901 檔（12 段 case.json／3 次重播 A-log 與 wire／gt-boxes／pixels 每段約 1250 張）；`MANIFEST.sha256` 的 SHA-256 **`e929713224851394bca1adaea0008eb0076169f9b8265528a79131c3eda44efc`**。可重建：`generate_e6.mjs`、`record.mjs`（`E3_SCENARIO_JSON=<OUT>/e6-scenario.json`）、`finalize_e6.mjs`；不可入 repo。
- 12 段 × 3 次瀏覽器重播的邏輯雜湊各段內一致。

| 段 | 長度 s | 決策點 | case SHA | GT SHA |
| --- | --- | --- | --- | --- |
| E6-S01 | 30 | 4 | `eef43f1db17f…` | `5954c60276fb…` |
| E6-S02 | 32 | 4 | `61974e46049a…` | `450e4aea1fa0…` |
| E6-S03 | 30 | 4 | `710ec6985f8a…` | `a9576a443591…` |
| E6-S04 | 31 | 4 | `839e0de67b5f…` | `46dc73133fad…` |
| E6-S05 | 32 | 4 | `2a89f7bef5aa…` | `ce73b4ca9103…` |
| E6-S06 | 30 | 4 | `969fd325cb14…` | `59144a7bb042…` |
| E6-S07 | 30 | 4 | `7fd2557dbd70…` | `91abcdab1c81…` |
| E6-S08 | 30 | 4 | `51f8223522f3…` | `e5a434c7f31c…` |
| E6-S09 | 31 | 4 | `4fb54e47a12a…` | `d99944174cf0…` |
| E6-S10 | 30 | 4 | `876b5f600bb8…` | `9c6bb62a22b0…` |
| E6-S11 | 30 | 4 | `7c5bf960e715…` | `c84b6df6afed…` |
| E6-S12 | 31 | 4 | `37659cb77042…` | `e76d8d0a313d…` |

## 決策點（錄製後由 GT 放置，偵測器隨 JSON 凍結）
48 個，全部找到事件；GT 狀態 `VISIBLE` 43、`FULL_BLIND` 5、`TRUE_DEPARTURE` **0**。同段決策點的 3.0 s 視窗（15 tick）不重疊（最小間距 15 tick，S07）。

## 關卡結果
- **DC9**（`dc9-gate.json`）：12 段 `forced_overlap`、`pause_player_i`、`script_stall`、`crowd_error`、`spawn_adjusted` 全為 0；設計檢查 12/12；不需重錄（S12 的重錄見下，不是 DC9）。
- `check_e6_data_separation.py --spec configs/evaluation/e6_scenarios_frozen_v1.json --mode formal --artifact-root local/evidence/e6-formal-20261127`：`PASS: E6 data separation verified (mode=formal, old_e3=16, diag=3, formal=12, unique_dps=48, effective_units=12, similar=6/6)`；`--mode draft`（原規格）也 PASS。
- `node --test frontend/live-mode/test/*.test.mjs`：159 項、157 通過、0 失敗、2 略過。

## 錄製前的設計偏離（逐項）
**DC1　起點修正（7/12 段；規格欄位不改）**

| 段 | 規格 → 錄製起點 | 原因 |
| --- | --- | --- |
| E6-S01 | [-13.2, -1.2] → [-11.0, -2.0] | spec start sees only ENTRY+W2 (not the planned CAM_EXT_CAR); nearest cell 1.9 m away seen by CAM_EXT_CAR+ENTRY |
| E6-S02 | [-12.5, 4.2] → [-11.1, 4.2] | spec start is blind to every camera (seed must be visible at t=0); nearest cell 1.4 m away seen by CAM_EXT_CLEAR |
| E6-S03 | [2.2, -3.2] → [7.0, -2.2] | spec start is outside every floor (WALK_R101 spans x 5..11); moved into R101 to a cell seen by CAM_R101_IN |
| E6-S04 | [-3.0, 1.4] → [-1.1, 0.5] | spec start is inside a wall clearance (x -3.0 beside the west wall); moved 2.1 m into the corridor, seen by CAM_W1+CAM_W2 |
| E6-S05 | [12.2, 1.2] → [14.3, 0.45] | spec start is seen only by CAM_W2; nearest cell 2.2 m east seen by CAM_BRANCH |
| E6-S10 | [0.8, -4.6] → [9.5, -2.2] | spec start is outside every floor and R101_IN does not see it; moved into R101 to a cell seen by CAM_R101_IN |
| E6-S11 | [14.2, 1.8] → [14.5, 1.17] | spec start is blind to every camera; nearest cell 0.7 m away seen by CAM_BRANCH |

**DC3　`TRUE_DEPARTURE`：** 引擎中玩家 T 不會離場。S11-DP3、DP4 規格為 `TRUE_DEPARTURE`，正式宣告為 GT 推導的 `FULL_BLIND`（T 走到走廊 N 北端所有鏡頭外，17.6 s 起盲到結束；類型名 `TRUE_DEPARTURE_ABSTAIN`／`POST_DEPARTURE_ABSTAIN` 不變，凍結副本的 `spec_gt_regime` 保留規格值）。`TRUE_DEPARTURE` 分層 n=0，報告列為已知限制。

**S12 `tail_s` 1.0（D401，協調者核准）：** 錄製參數調整，在任何組別輸出之前。S12-DP4（接回，GT 事件 27.2 s＝tick 136）在 30 s 錄製中，`check_e6_data_separation.py` 要求 `tick + 15 <= max_ticks`（150）而失敗。路線與人群軌跡不動，只把 S12 的 `tail_s` 設為 1.0（錄製 31.0 s、156 tick），並重錄 S12；其餘 11 段不變。**注意：** routes JSON 的 `frozen_by` 文字寫「frozen before any recording」，實際上 S12 的 `tail_s` 是在第一次錄製之後調整的（D401），路線與軌跡未變；JSON 的 `tail_note` 也說明了。為避免重算 SHA，不再改 JSON。

**其他：** 干擾者最大速度 2.05 m/s（上限 2.1，DC7）；報告需寫為限制（快步、腳步動畫不同步）。決策點 ±3.0 s 只用於設計檢查（DC2）。

**下游讀起點：** 12 段的實際錄製起點用凍結規格副本裡的 `formal_cases[].start_xy_recorded`（routes JSON 的 `start_xy`）；凍結規格的 `start_xy` 與 routes JSON 的 `spec_start_xy` 是**規格原值**（為了 `check_e6_data_separation.py` 的檢查保留），下游不要拿它們當起點。

## formal 錄製目錄格式（`local/evidence/e6-formal-20261127/`，下稱 `$ARTIFACT_ROOT`；#741 的 G4 依此接 B1／R-N／AO_ORIG）
每段 `E6-Sxx`（xx = 01…12）：
- `E6-Sxx.case.json`：輸入錄製（schema_version、case_id、run_id、actor_id = T、bindings、config、`inputs` = 每 0.05 s 的按鍵、`expected` = 逐 tick 的解析器狀態、actions）。含 `expected`，SHA 在凍結規格的 `case_sha256`。`E6-Sxx.input.case.json` = 去掉 `expected` 的輸入版（餵 LIVE 頁用）。
- `pixels/E6-Sxx/<tick:05d>-<CAM_ID>.jpg`：**唯一的 RGB**。320×180 JPEG（quality 0.85）、5 Hz、8 鏡頭（CAM_BRANCH、CAM_ENTRY、CAM_EXT_CAR、CAM_EXT_CLEAR、CAM_R101_IN、CAM_W1、CAM_W2、CAM_WIDE）；`t_capture_ms = tick × 200`；每段 N+1 個 tick（長度 30 s → 151、31 s → 156、32 s → 161；S12 含尾段為 156）。取自第 1 次重播。
- `E6-Sxx.replay{1,2,3}.wire.json`：送進推論端的封包索引，`[{tick, t_capture_ms, available_cameras, frames: [{cam, bytes, sha256, path}]}]`；`path` 指向上面的 pixels，`sha256` 是該 JPEG 的 SHA-256。**B1／R-N／AO 讀這個加 pixels，不讀其他檔。** 三次重播邏輯一致（`browser-replay.json`），G4 用 replay1。
- `E6-Sxx.replay{1,2,3}.a-log.json`：**A 側私有紀錄，含 GT，推論端不得讀**。`ticks[i]` = {tick, t_capture, t_sim, actors: [{id, present, xy, gt_visible: [CAM…]}], pause_*_i, forced_pairs, …}；另有 forced_overlap、block_wait、pass_end、crowd_error、spawn_adjusted、config。
- `gt-boxes/E6-Sxx.a-log.json`：**評分用 GT**（`EVALUATION_ONLY`）。schema `live-ab.a-log.v1`；`ticks[i].actors[j]` = {id（T／A／C）, present, xy, gt_visible, gt_boxes: {CAM: 代理框 0.5×0.5×1.75 m，不是像素遮罩}}；`provenance` 註明可見性不含演員互相遮擋、身分 `UNCONFIRMED`。凍結規格的 `gt_path`／`gt_sha256` 指它。
- `E6-Sxx.operator.png`：操作視窗截圖，只供目視。

全域檔：`e6-scenario.json`（錄製時餵頁面的 run 定義，含干擾者腳本，推論端不得讀）、`input-replay.json`（逐段產生回條）、`browser-replay.json`（三次重播的邏輯雜湊與擷取數）、`dc9-gate.json`（關卡結果）、`e6_scenarios_frozen_v1.json`（凍結規格副本）、`MANIFEST.sha256`（每檔一行 `<sha256>  <相對路徑>`，MANIFEST 本身不在內）。

**沒有的東西：** 偵測結果、indexes、RT-DETR 輸出、B1 snapshot、任何組別輸出。G4 要從 pixels 自己產生（偵測、色彩判定、B1 的凍結偵測）。決策點在凍結規格 `formal_cases[].actual_decision_points`（dp_id、type、tick、t_actual_s、gt_regime、spec_gt_regime），`tick` 就是上面的 tick 索引。

**推論端可見：** wire 加 pixels，以及 8 鏡頭標定（`local/data/live-assets-20261115/cameras.three.json`）。**不可見：** a-log、gt-boxes、`e6-scenario.json`、case.json 的 `expected`、凍結規格的決策點 `gt_regime`／`spec_gt_regime`。
