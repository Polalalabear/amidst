# RQ1 單鏡頭接地區間評估結果（2026-10-18）

Model / effort: Sonnet 5.5 / 預設（未指定）。評估對象：C4a v1.1 `FOOT_RAY_PIXEL_BAND` 凍結預測（#46 @ a6ce40c）對人形 run `blender-contact-control-office-person-20261016-v1`。這是工程 demo 的診斷，不是身分、物理安全或正式研究驗收。

## 結論（先看這裡）

- 33 筆區間中，**23 筆（70%）在 0.25 m（D5 半徑）容差內涵蓋 GT 接觸點；0 容差下 0/33**（GT 是一個點、區間是一條線，0 容差幾乎不可能命中，僅作下界參考）。
- 結果**高度依賴鏡頭與時段**：FRONT 腳點帶 19/23 涵蓋；**REAR 腳點帶 0/6 涵蓋**，GT 距離線段 2.0–3.1 m，且 GT 一律落在 near 端之外（位置參數 clamp 在 0）。頭頂射線 4/4 涵蓋，但區間長 2.3–2.6 m，資訊量低。
- FRONT 在 t=0.8–1.4 s 也有 4 筆未涵蓋（1.2–2.0 m，逐筆遞增）。REAR 的失誤是系統性偏移，不像隨機雜訊。**原因未診斷**（UNKNOWN）：可能在接觸點偵測、標定或可見性，需要另行調查，本文件不下結論。
- 區間長度與已知值一致：腳點帶 0.732–1.185 m、頭頂射線 2.268–2.572 m（REAR 8.2 s 為 2.49 m）。

## 數字（逐觀測計算後彙總；單位 m）

| 群組 | n | 涵蓋 0.25 m | 涵蓋 0 容差 | 距離中位數 | 距離範圍 | 區間長度 中位數（範圍） | 線段上位置中位數 | 參考：中點誤差中位數* |
|---|---|---|---|---|---|---|---|---|
| 全部 | 33 | 23/33 (70%) | 0/33 | 0.146 | 0.002–3.120 | 0.793 (0.732–2.572) | 0.40 | 0.189 |
| 腳點像素帶（全部） | 29 | 19/29 (66%) | 0/29 | 0.156 | 0.002–3.120 | 0.780 (0.732–1.185) | 0.40 | 0.180 |
| 腳點像素帶 · FRONT | 23 | 19/23 (83%) | 0/23 | 0.106 | 0.002–2.040 | 0.760 (0.732–0.924) | 0.43 | 0.112 |
| 腳點像素帶 · REAR | 6 | 0/6 (0%) | 0/6 | 2.615 | 1.991–3.120 | 1.157 (1.129–1.185) | 0.00 | 3.193 |
| 頭頂射線（全部） | 4 | 4/4 (100%) | 0/4 | 0.113 | 0.057–0.249 | 2.532 (2.268–2.572) | 0.34 | 0.409 |

\* 中點誤差是**參考，非系統輸出**（預測本質上是區間，不是點）。位置參數：0 = near 端，1 = far 端。
完整逐觀測列與其餘彙總（含 camera 單獨彙總）：`RQ1_GROUND_INTERVAL_RESULTS_20261018.json`。

圖：`figures/rq1_distance_and_length.png`（距離與區間長度隨時間）、`figures/rq1_plan_view.png`（平面圖：GT 路徑與預測區間）。

## 方法

- **輸入凍結**：預測 `docs/engineering/C4A_PERSON_FOOT_BAND_PREDICTIONS_20261017.json`，SHA-256 `c1dfc1bd3baacca514f2066adcfc10036cbcfaf657e5636d8482b837d6dd4616`（取自 `origin/codex/c4a-foot-ray-band@a6ce40c`，`git show a6ce40c:<path>`；不複製入本 repo）。評估程式先驗證此 SHA，通過後才取得可載入 GT 的授權物件；否則 `load_ground_truth` 拒絕（有測試）。預測自述 `gt_read=false`。
- **GT**：`/Users/polalabear/Developer/amidst/data/pilot/office_person_20261016_v1/rendered/ground_truth.json`（LOCAL，唯讀，SHA-256 `e12c34f566e69b5d51fb0c9022dc69f1401c56f18fee078ca10a0ee2f42b72a9`）。檔內 `source_asset_sha256` 與預測的 `source_sha256`（`cd46fa03…6e84e`）相同，`trajectory_id=OFFICE_PERSON_SAME_ROUTE_20261016_V1`，50 筆、0–9.8 s、5 Hz。選用此檔的理由：run 的 `manifest.json` 指向同一 `rendered/` 目錄，且 C4a 報告與 `trajectory_plan.json` 的 `run_id` 一致。
- **接觸點定義**：GT `foot_position`（人形圓柱軸心在地面的接觸點，z＝地板＋0.05 場景單位間隙）；不用 `position`（`SYNTHETIC_TARGET_BODY_CENTER`，身體中心高度）。比較在水平面（XY）進行；預測線段位於固定地板高度，GT 高度殘差最大 1.24 mm，僅作一致性檢查（上限 5 mm），不計入距離。
- **單位**：GT 為場景單位，乘以 `0.0247 m/單位`（`trajectory_plan.json` 的 `run_configuration.source_scale_m_per_bu`；plan SHA-256 `fbdadb31d49cf54f6ee0ea458f22c438f97c7191875252e05067ce2443453aa6`，LOCAL）。交叉檢查：GT 地板高度換算後與預測平面高度 0.496 m 相符。
- **時間對齊**：預測與 GT 同為 5 Hz；若時間戳在 1e-6 s 內則取該 GT 樣本，否則在相鄰兩樣本間線性內插；超出 GT 時間範圍則報錯，不外推、不取最近點。本次 33 筆全為 `EXACT`，沒有內插。
- **指標**：距離＝GT 點到線段（near→far）的最短距離；位置參數 t∈[0,1]（clamp）；涵蓋＝距離 ≤ 容差。容差 0.25 m（D5 人形半徑，預先於設定檔宣告）與 0。注意預測 far 端已含半徑裕度（C4a），所以 0.25 m 容差對 far 端方向可能略為寬鬆；本文沒有調整容差去改善數字。
- 輸出確定性：報告腳本連跑兩次，JSON 與兩張 PNG 的 SHA-256 完全相同。

## 限制與 UNKNOWN

- **單一 run、單一路徑、33 筆觀測**（4 m 直線，人形圓柱，合成場景），觀測之間高度相關；百分比不是統計推論，也不可外推到真實人物或其他場景。
- GT 是 renderer 軌跡，僅供事後評估；結果沒有回流到任何預測、排序或重建。
- 失誤原因（REAR 系統偏移、FRONT 0.8–1.4 s）：UNKNOWN，未檢視影像或接觸點偵測。
- 頭頂射線基底只有 4 筆，且區間長度 2.3–2.6 m，高涵蓋率主要來自區間寬。
- 未評估：C4b／C5、物理可行性（new_body_clearance 為 UNKNOWN_PENDING_C7）、身分。
- 預測檔在 Codex 分支，本分支不含該檔；重現需先取出：`git show a6ce40c2956a8f15b1ad77c9310bce1b203b7e7b:docs/engineering/C4A_PERSON_FOOT_BAND_PREDICTIONS_20261017.json > /tmp/pred.json`。

## 重現

```bash
PYTHONPATH=src python scripts/rq1_ground_interval_report.py --predictions /tmp/pred.json \
  --out-json docs/engineering/RQ1_GROUND_INTERVAL_RESULTS_20261018.json --fig-dir docs/engineering/figures
```

設定：`configs/rq1_ground_interval_v1.json`；程式：`src/amidst/evaluation/rq1_ground_interval.py`；測試：`tests/evaluation/test_rq1_ground_interval.py`。
