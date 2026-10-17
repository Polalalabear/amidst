# RQ1 凍結區間失誤診斷 — 2026-10-18

以估計器負責人的判斷，最可能的共同原因是：**被家具截斷的可見 RGB 元件底部，仍沿用成地板 contact anchor；品質 heuristic 未標 CONTACT_OCCLUDED，因而走進 ±2 px 腳點帶。低入射角放大了這個 anchor 偏差。** 這是有影像與程式支持的機制假說，尚未由獨立、逐像素接觸標註證實。不能把 LOW_INCIDENCE-only 當作「腳已確認可見」。

本報告只讀既有凍結預測、Claude #61 的評估結果與 15 張指定原始 RGB。未重跑 perception、投影、估計、檢索或 GT 評估；未讀原始 GT／renderer 軌跡／depth／visibility。#61 的結果是事後評估資料，未回流估計器或任何推論輸入。

## 凍結來源與範圍

- C4a 預測：`docs/engineering/C4A_PERSON_FOOT_BAND_PREDICTIONS_20261017.json`，SHA-256 `c1dfc1bd3baacca514f2066adcfc10036cbcfaf657e5636d8482b837d6dd4616`。33 筆：29 FOOT_RAY_PIXEL_BAND、4 HEAD_RAY_HEIGHT_PRIOR；原始觀測仍 33 MISSING/null。
- 評估：[Draft #61](https://github.com/Polalalabear/amidst/pull/61) @ `5672feee7c96c490cc238dcec5a96681263be63b`，`RQ1_GROUND_INTERVAL_RESULTS_20261018.json` SHA-256 `981ccacad576773a6355fb64fc6ac5a4accea3a713798debde2eef615f0d991c`。數字沿用 Claude 的評估，沒有重新計算涵蓋率或更改容差。
- RGB locator 僅來自 person bundle 的 `safe_inputs.json`，SHA-256 `e9aff43f08955222348407a3435baff05c8a38f6638226a1bd43dc544836c998`；15 張原始 PNG 的 hash 均與 safe-input 記錄一致。含 10 張失誤、4 張頭頂射線、FRONT 0.6 s 對照。逐筆 frame/observation refs、hash、anchor、basis、距離與品質標籤見[診斷收據](RQ1_ESTIMATOR_DIAGNOSIS_20261018.json)。沒有複製或改圖、沒有 GT overlay。
- LOCAL 圖片位置：`data/pilot/office_person_20261016_v1/rendered/frames/<camera_id>/frame_NNN.png`，本 repo 外不新增媒體副本。

## 逐組證據

| 群組 | Claude 已凍結的評估 | 本次 RGB／預測檢視 | 判斷 |
| --- | --- | --- | --- |
| FRONT 0.8/1.0/1.2/1.4 s | 4 筆距離 1.176/1.562/1.797/2.040 m；線段參數皆 clamp 0（最近點為 near） | 橘色目標下緣與前景椅背相接／被截斷；anchor v 由 0.6 s 的 136 跳至 126，再 124/123/122。四筆全部只有 LOW_INCIDENCE，沒有 CONTACT_OCCLUDED。 | **較強支持遮擋／元件底部失配假說**。這個 10 px 的既有 anchor 跳變超過預先固定的 ±2 px 擾動，不能用腳點帶保證涵蓋。不能僅從 RGB 判定真實腳點位置。 |
| REAR 8.4/8.6/8.8/9.0/9.2/9.8 s | 6 筆皆未涵蓋，距離 1.991–3.120 m；最近點均 near | 橘色目標靠柱體與椅背，呈窄可見條帶，下部被椅背截斷；anchor 約 (287–301, 99–102)，仍全部只有 LOW_INCIDENCE。 | **較強支持同一失配機制**；不是零均值像素雜訊的典型形態。部分水平遮擋也可能讓元件底列中位 x 偏離軸心；此項未量化。 |
| FRONT 1.6；REAR 8.2/9.4/9.6 s | 頭頂射線 4/4 在 0.25 m 容差內，區間長 2.268–2.572 m | 同樣是底部受遮擋的畫面；這四筆有 CONTACT_OCCLUDED，因此 basis 切到 HEAD_RAY_HEIGHT_PRIOR。 | 頭高先驗不是上面 10 筆失誤的直接來源（10 筆根本沒使用它）；4/4 也不是精確頭點／接地證明。區間寬、bbox 頂列／中點與圓柱頂緣的差異仍有偏差風險。 |

## 程式機制：能確認與不能確認的部分

**VERIFIED：** `src/amidst/engineering/perception_v2.py::measure_component` 把元件最底列的 median x 與 max y 定為 `contact_pixel`，而非獨立確認的腳點。CONTACT_OCCLUDED 來自固定身高預測頂點與元件 top_pixel 的殘差是否超過 `height_tolerance_px + radius_px`；它是 heuristic，不是來源遮擋檢查。沒有該旗標不等於沒有遮擋。本次未重建元件、重跑 residual 或推導一個新的 threshold，不能宣稱已找出每筆漏標的數值邊界。

**VERIFIED：** `hybrid_contact.py::_foot_segment` 固定 u，只把 v 擾動 ±2 px，並僅在 far 端加 0.25 m 半徑；不對家具遮擋、水平 anchor 偏差、校正偏差或整體系統誤差建模。失誤的最近點均是 near，單純加長 far 端也無法處理這組評估形態。既有 `pixel_sensitivity_m` 在 FRONT 四筆約 0.176–0.189 m，REAR 六筆約 0.241–0.257 m；這只是局部像素敏感度，不能當總誤差界或信賴區間。

**VERIFIED：** 這些失誤並未被標 TOUCHES_IMAGE_EDGE，anchor 也不在 960×540 畫面的外框；影像外框截斷不是目前支持的主因。家具／柱體的內部邊緣遮擋與畫面外框是不同問題。沒有 AMBIGUOUS_MERGE 旗標，但也不能據此證明元件語意正確。

**VERIFIED：** `_height_segment` 使用預先宣告的頭高範圍；head anchor 取 bbox 的水平中點及 ymin。圓柱頂部輪廓、透視斜率、部分側遮擋或頭頂截斷均可能使此像素不同於軸心頭點。本次 4 筆只支持該寬區間在此 run 的事後涵蓋結果，不支持將先驗當量測值。

**UNKNOWN：** 每筆真實可見腳點、遮擋比例、造成漏標的 residual/容差數值、相機校正偏差的貢獻。Claude 已核對時間為 EXACT、尺度與地板高度殘差約 1.2 mm，可降低時鐘／單位錯配的優先度，但不能單靠高度一致證明完整外參正確。沒有進行校正擬合、來源 raycast、足部可見性或 GT 反投影。

**限制：** ±2 px 是預先宣告的局部擾動，不是經校準的 GT 涵蓋界。凍結中的 READY / K1 eligibility 只代表現行契約與 gate 通過，不是這 33 筆已獲準作真實人物位置或物理端點。原始 MISSING、不確定性與 identity UNCONFIRMED 均保留。

## 只提案，待使用者決定

可考慮另開事先註冊的 estimator revision：先定義 RGB-only 的「足部未獲確認」狀態／保守 UNKNOWN gate，再於新的獨立資料與凍結評估規程驗證。若需要來源幾何的 camera-specific foot-hidden masks，必須沿用 C7 介面與 authority，不能拿 renderer visibility 或這次 GT 替代。頭頂射線應維持先驗區間及其限制。

本報告**不建議據這 10 筆加大 band、放寬高度殘差、偏移 near endpoint 或針對 REAR 補常數**。所有修改都需使用者另行決定；沒有實作、調參、新測試資料回灌或重新凍結。這些案例已看過評估結果，後續若用於開發應標為診斷／開發資料，不能重新當作未見的驗收集。

## 重現唯讀診斷

從固定 SHA 讀取評估 JSON 與本 repo 的預測，按 observation_ref join；僅挑 `covered_body_radius_d5 == false`、四筆 HEAD basis 與 FRONT 0.6 s。以 camera_id / timestamp_s 在 safe_inputs.frames 解決 RGB 路徑並驗 SHA，再檢視原圖。只讀這些已凍結欄位，不呼叫 produce_contact_v2、estimate_contact 或評估工具。source blobs 可用 `git show a6ce40c:<path>` 讀取；#61 的評估以 `git show 5672fee:docs/engineering/RQ1_GROUND_INTERVAL_RESULTS_20261018.json` 讀取。診斷收據保存完整 refs、frame hashes 與 guard hashes。

## 實際產出 / Actual output
- Model / effort: UNKNOWN
- PR / commits: 純文件 #54；對照 #46 的固定預測與 #61 @ `5672feee7c96c490cc238dcec5a96681263be63b`。launcher 實作在讀 #61 前已提交為 `ba1ffe1`，且沒有 estimator 變動。
- Files changed: 只有本 Markdown 與診斷 JSON 收據。
- Commands run and results: `git show` 讀兩份 #61 結果；既有 prediction/evaluation JSON join；15 張指定 PNG SHA-256 與 safe-input 一致、原圖人工檢視；比對 estimator/config/prediction guard hashes；`git diff --check` PASS。
- Artifacts: 本文件與 JSON；PNG、GT 沒有複製／發布；LOCAL hash guard 記錄 `/private/tmp/rq1-diagnostic-frozen-guards.json`。
- Verified: 10 筆失誤的 basis/flag/anchor 與 nearest-near 形態；15 張 RGB；元件底點與 heuristic gate 的既有程式路徑；原預測 SHA 與估計器／設定 bytes 不變。
- Not verified: 失誤原因的獨立因果證明、每像素腳點／遮擋、校正殘差分解、修改估計器的改善幅度。沒有跑測試／推論／GT 評估；本任務只寫報告。
- Deviations, UNKNOWN items and follow-ups: 目前最強假說是部分遮擋未標記導致腳點帶用錯 anchor；未知項明列。任何 estimator revision 都等使用者決定；沒有重凍結或追求改寫既有 RQ1 分數。
