# C5 可見範圍驗收補充（2026-10-16）

狀態：**驗收要求已記錄；C5 index／API 尚未實作或驗收**。來源是使用者對
[PR #34](https://github.com/Polalalabear/amidst/pull/34) 的 C6 渲染前篩選第 10 項；
工作追蹤 [C5 #18](https://github.com/Polalalabear/amidst/issues/18)。

C5 的「可見地板」應表示「以該地板 XY 為底點的代理目標，至少一個探針可被來源鏡頭看見」，
與 C6 完全一致：腳點、軀幹中點、頭頂中，**任一探針 VISIBLE 就不算盲區**。
不能只用地板射線被擋就把頭頂仍可見的位置當成盲區。

- 高度、半徑、地板平面、離地量逐 run 綁定；新代理高 1.70 m、半徑 0.25 m。
  C6 探針的地板上方偏移為 0.002／0.852／1.702 m；C5 不得默默忽略離地量或改用舊
  Office 的 2.9393 m 先驗。索引須綁定實際探針設定與來源／calibration／floor／config hash。
- 每個探針先檢查來源攝影機 clip／FOV，只有在視錐內才測來源靜態實體網格遮擋。
  FRUSTUM_ONLY 不等於來源網格視線，不可用於負證據。
- 對單一鏡頭，三探針任一可見即屬該鏡頭的可見 XY 集合；對 C6 的全局盲區，必須所有
  已聲明鏡頭的三探針皆不可見。未評估鏡頭／射線或資料缺失保持 UNKNOWN，不當成不可見。
- 「腳點可見且 incidence ≥0.25」是 C6 的**端點接地資格**，不是可見性定義。
  頭頂可見、腳點不合格的採樣仍非盲區，但不能因此宣稱端點接地可用。
- 可見不保證 RGB 檢測成功：元件像素閾值、透明材質、偵測器漏失仍須渲染後 RGB 檢查。
  負證據須另具相同 run／clock 的合法 NO_DETECTION 與已評估狀態；C6 規劃產物不直接
  成為推論負證據，也不包含已排除出口或已確認身分。

可重用的純函式位於 [c6_prescreen.py](../../scripts/c6_prescreen.py)：
`probe_visibility(..., raycast)` 與 `is_visible(camera_probes)`。
[專用測試](../../tests/unit/test_c6_feasibility.py) 包含 FOV 內被擋、OUTSIDE_FOV、CLIPPED、
clear ray、只見軀幹／頭仍非盲區。這些是 C6 的當次測試，不代表 C5 已接線或通過。

C5 實作時需在其 Actual output 紀錄明列：相同探針設定與 union 定義、UNKNOWN 處理、
靜態網格與材質政策、逐 run hash 綁定，以及用 C6 採樣核對盲／非盲分類的結果。
