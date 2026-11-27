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

**S12 尾段 1.0 s（凍結後、評分前的機械修正；Opus 設計審查時未列）：** S12-DP4（接回，GT 事件 27.2 s＝tick 136）在 30 s 錄製中，`check_e6_data_separation.py` 要求 `tick + 15 <= max_ticks`（150）而失敗。路線與人群軌跡不動，只把 S12 的 `tail_s` 設為 1.0（錄製 31.0 s、156 tick），並重錄 S12。僅此一段，`tail_note` 寫在 JSON；其餘 11 段不變。請審查者確認。

**其他：** 干擾者最大速度 2.05 m/s（上限 2.1，DC7）；報告需寫為限制（快步、腳步動畫不同步）。決策點 ±3.0 s 只用於設計檢查（DC2）。
