# #516 八鏡頭 v2.3 修正紀錄

來源：#527 `1e55272fb08dc15ff69251e3b06113c3cf12e3ba`，v2.2；使用者 2026-11-14 授權八鏡頭 preflight 失敗直接修。v2.2 原檔不覆蓋，T 的兩段完整 actor JSON 逐項相同；自然步態模組與 Person adapter 不變。

| 修正 | 原值 → 新值 | 原因與數字 | 修正後 |
| --- | --- | --- | --- |
| 鏡頭集合 | A4 4 台／B4 5 台 → 各 8 台原 catalog 相機 | 使用者要求補齊；不改姿態、內參與鏡頭圖 | checker 兩段 exit 0；96 個 mesh endpoint × camera 測試 PASS |
| A4 B 出生與初段 | 2.0–5.6s `(16,1)` → 2.0–5.0s `(13.75,0.5)`；6.21s 重新接上 `(15.2,1.1)`，後續路點不變 | 原出生 CAM_BRANCH 可見像素 `(437.544,143.852)`，CAM_WIDE `(462.205,221.392)`；實際 posed mesh witness | 新出生 8/8 mesh 遮擋／frustum PASS；全片 probe 零相交；checker PASS |
| A4 C 出生與初段 | 4.0–17.5s `(9,-3)` → 4.0–15.5s `(9.75,-4.5)`，17.5s 接回 `(9,-3)` | 原出生 CAM_R101_IN 可見像素 `(369.972,358.972)`；實際 posed mesh witness | 新出生 8/8 mesh PASS；全片 probe 零相交；checker PASS |
| A4 C 尾段 | 27.7–50s `(16.8,0.7)` → 27.7s 原點、28.6s `(16.7,1.8)`、38–50s `(16.7,13.7)` | D207 允許停留到錄影結束；但 #520 G1 要求所有 last 點也在鏡頭外。原末點 CAM_BRANCH／CAM_WIDE 可見，為滿足較強 G1 採北側既有通路離場 | 末點 8/8 mesh PASS；牆距 ≥0.45m；速度≤1.6m/s；T 不變 |

完整結果：兩段各 7/7 checker PASS；人物中心最小距 A4 0.8m、B4 0.6764m；最小牆線淨距 ≥0.45m（門檻 0.35m）；全 460 個時間樣本 posed mesh 零相交；歧義規劃估算合計 ≥5 段（數字見報告，屬假設 coverage／perfect detection，不是觀測）。實際 articulated surface 連續淨距及完整物理導航仍 UNKNOWN。

A4 改動會影響原有相機的人物姿態／路線，因此八台全部重產 2,000 幀；B4 actor JSON 完全相同，驗證原 #527 影格、gait bytes、Person AST、渲染設定後沿用五台共 1,050 幀，新增三台 630 幀。不得混入 #523 舊 RGB 或 records。所有索引將在八台完成後僅重建一次。

## 改自我檢查：標記計數→函式計數

沿用使用者在 #523 期間的逐項明確授權，只修 `test_selftest_gate_markers_are_strict_and_cover_every_gate`。#528 main 仍帶舊規則（永遠要求 8 個 @G1、4 個 @G2，與完成後移除標記矛盾）；新規則依函式名保留完整 8/4 關卡，每組標記只能全部保留或全部移除，存在的定義必須 `xfail(strict=True)`。其餘 G1/G2 validator、測試函式與自我測試均保持 #528 的 AST 不變；待交付時只移除整組標記。
