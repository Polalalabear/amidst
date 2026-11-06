# #467 r005 人物短片參數提案（PROPOSED，未授權渲染）

本文件只供 [#467](https://github.com/Polalalabear/amidst/issues/467) 逐項核定。建議先做 **A：R101 ↔ 西走廊、8 秒、兩鏡頭** 的受限工程片段。B 是較大範圍的備選。兩者都沒有動畫、影格、模型推論或完整追蹤 Demo 成果；核定本文件也不等於授權渲染。後續渲染須另開任務，確認全部參數、來源及磁碟 gate。

## 綁定與權限

- 靜態基底為 [#447@`39b9c432`](https://github.com/Polalalabear/amidst/pull/447) 的 `office_expanded_r005` v2；[交件紀錄](https://github.com/Polalalabear/amidst/blob/39b9c4323288cae8c52532277cdd6dc75b63a965/docs/engineering/D127_418_STATIC_PREVIEW_V2_20261105.md)記載 `scene.blend` SHA-256 `79d142bac6a1853f6cde0066b72efd7d439d2fe329195df0fadfbfd32cfebf2e`、build receipt SHA-256 `0f6b279e4d535959aad7bff769022f6fcf0a2257e2aca922f6f9fa0fac1ea3bd`、修正參數 SHA-256 `e07218a16875a79aac474a0f5ab1ae714248571414a2d775f1ab2f2c8295aa74`。這是靜態 source pin；動態衍生品的 source/run/clock/hash 均 `UNKNOWN`，不能沿用靜態圖的 run 身分。
- [v2 region graph](https://github.com/Polalalabear/amidst/blob/39b9c4323288cae8c52532277cdd6dc75b63a965/configs/q1q5/graphs/office_expanded_r005/preview_v2/region_graph.json) 有 `R101—CORR_W`、`CORR_W—CORR_E`、`CORR_E—R102` 等拓撲邊，但均為 `TOPOLOGICAL_ONLY`／`UNKNOWN`；[camera graph](https://github.com/Polalalabear/amidst/blob/39b9c4323288cae8c52532277cdd6dc75b63a965/configs/q1q5/graphs/office_expanded_r005/preview_v2/camera_graph.json) 只有靜態 frame 的人工部分覆蓋與 portal ROI。不能由此推得門洞淨空、可走、遮擋、人物可見時間或 camera handoff 成功。
- [#418 v2 授權紀錄](https://github.com/Polalalabear/amidst/blob/39b9c4323288cae8c52532277cdd6dc75b63a965/docs/engineering/d127_418_preview_v2_authorization.json)只涵蓋六張靜態 camera RGB 與一張人用俯視圖，明列 `actors_authorized=false`、`animation_authorized=false`、`video_authorized=false`。俯視圖不作推論輸入。
- [#442 D124 producer 參數](https://github.com/Polalalabear/amidst/blob/62a8979632d800e9ac6d23fc29789e56a11550bc/configs/q1q5/producers/r004_d124_v1.json) 與 [D124 收據](https://github.com/Polalalabear/amidst/blob/62a8979632d800e9ac6d23fc29789e56a11550bc/docs/engineering/R004_D124_RERENDER_RECEIPT.md) 是**另一 r004 source 的已批准先例**：非零 XY 移動切線朝向、停留保留上次朝向、無轉向平滑、正面臉部／胸前特徵與背包區分正反面。其 source 軸、人物物件尺寸、路線、時鐘、資產授權與結果均不能移植為 r005 已核定事實；r005 人物模型、局部正面軸、材質與姿態都 `UNKNOWN`。

## 兩個待選分鏡

時間採每段 `[start,end)` 秒、片段源時鐘從 0 秒起算；秒數是**提案分鏡**，不是測得的速度或可見性。所有鏡頭於選定片段全程同步取樣，即使人物不在視野也保留來源影格；不以推論結果事後裁剪或挑幀。畫面為 960×540、RGB8 PNG、EEVEE 64 samples、已核定 v2 靜態曝光 -4 EV 與走廊補光設定；人物加入後的亮度、噪點、曝光可用性均 `UNKNOWN`。5 fps 僅沿用 D124 的工程節奏作提案，並非 #418 已核准動畫 fps。

| 參數 | A：建議的最小受限片段 | B：跨兩室擴充片段 |
| --- | --- | --- |
| 路線（只指拓撲） | `R101 → CORR_W → R101`；往返一次，西走廊折返 | `R101 → CORR_W → CORR_E → R102`；單向跨兩段走廊 |
| 分鏡秒數 | 0–2 室內出發；2–4 門口／進西走廊；4–5 西走廊停留並轉身；5–8 返回 R101 | 0–2 R101 出發；2–4 到西走廊；4–7 通過西走廊及接合；7–10 到東走廊；10–12 嘗試進 R102 |
| 同步鏡頭 | `CAM_R101_IN`、`CAM_CORR_W`；不含人用俯視 | `CAM_R101_IN`、`CAM_CORR_W`、`CAM_CORR_E`、`CAM_R102_IN`；不含人用俯視 |
| 時長、fps、輸出影格 | 8 s × 5 fps = 40 時點／鏡頭，2 鏡頭共 80 PNG | 12 s × 5 fps = 60 時點／鏡頭，4 鏡頭共 240 PNG |
| 正反面與轉身 | 出門及返回各有相反移動方向；4–5 秒停留時提案做一次可見轉身。以正面／背包識別外觀朝向，來源前軸及具體動畫 `UNKNOWN` | 只靠單向行進未必能在任一相機同時看清正反面；另提議 7–8 秒在走廊停留轉身，會改變 7–10 秒的移動節奏，需另核定細分 timing。具體呈現 `UNKNOWN` |
| 工程用途 | 檢查兩台靜態相機的同期 RGB、出入與折返的可檢視性 | 檢查四台相機、兩段走廊與跨室資料量；風險與成本較高 |

**推薦 A**：先確認人物外觀、門口出入與轉身是否能在兩鏡頭中被人看清。A 的回程可能讓片段具有正反面對照，但相機實際視角與遮擋仍待合規檢查；它不提供「有意義 blind interval 已達成」或跨空間身分成立的證明。B 需要先確認 A 的結果、接合邊與 R102 門口的合法通行範圍。若目標必須是「兩間教室之間」而非「教室與走廊之間」，請選 B 並重新核對時間與安全邊界。

## 座標、人物與來源待核定項

- 本提案**不填具體 XY 路點、門口通過軌跡、速度、身高、gait、骨架、朝向角或接地高度**。它們沒有經 r005 合法來源、淨空與動畫可行性核對，全部 `UNKNOWN`。拓撲上的箭頭不授權直線穿牆或碰撞判定。
- 參照 D124 的原則只作**待核定設計**：非零移動方向決定朝向、停留時保留最後朝向；正面可見臉部／胸前標記，背面可見背包。需先讀取合法 r005 人物來源並核實前軸、尺寸、材質、相機遮擋，再定義轉身時間與視角；不得把 D124 的 r004 私有設定當 r005 推論或展示資料。
- 動態 scene 的 parent/source hash、producer、clock origin、run ID、camera-to-world/K 綁定、逐幀採樣表、原始與 served RGB hashes、獨立輸出根目錄均需在另一次核定與產製中固定。本提案不建檔、不複製或覆蓋 v1/v2/source，也不變更任何 graph、config、Blender 或媒體。

## 磁碟規劃值與硬 gate

v2 靜態交件的**整包**為 11 檔、3,611,228 logical bytes（含 7 PNG 與 metadata），可供 `約 0.5 MiB／PNG` 的**名義規劃**，不是動態帶人物畫面的實測大小。A：80 × 0.5 MiB ≈ 40 MiB；B：240 × 0.5 MiB ≈ 120 MiB。時序場景複雜度、壓縮雜訊、逐影格大小、Blender 暫存、影片封裝與峰值占用都 `UNKNOWN`；不得將 40／120 MiB 當容量上限或承諾輸出。若後續另編影片，須另估算並核定，不在這兩個 PNG 數中。

預留 **1 GiB 新支出預算**（含衍生 scene、PNG、暫存與核驗開銷），且另保留 **8 GiB 可用空間硬底線**：開始每個建檔／render 階段前用目標磁碟 `df -k` 實測，須同時滿足可用 ≥9 GiB 與獨立目的目錄／預算；階段中與階段後若可用 <8 GiB、預算將超限或輸出大小超過事先設定的逐檔上限，停止並回報，**不自動刪除舊成果**。1 GiB 是保守規劃 reserve，非實測峰值；新作業若量到更高需求，先修方案。舊 df 快照不能代替開工檢查。本次未讀磁碟容量，current free=`UNKNOWN`。

## 請使用者在 #467 核定的具體項目

1. 選 A（建議）或 B；路線與各段時長是否同意。B 的 7–8 秒轉身與東走廊節奏必須另定。
2. 相機列表、960×540 RGB8 PNG、5 fps、EEVEE 64 samples、v2 靜態曝光／補光沿用範圍；是否要求另外的正反面示範影格。
3. r005 人物來源、正面軸、外觀修改方式與轉身姿態；合法路點、門口淨空、碰撞／通行與相機可見性未查前均保持 `UNKNOWN`。
4. 只在後續獨立任務授權時才建立動態衍生 scene、run、clock 與輸出；確認新目錄、原版保留、1 GiB 支出預算、≥9 GiB 開始與 ≥8 GiB 全程硬底線。核定參數與渲染授權需分開記錄。

本次文件未執行 Blender、RGB／原媒體讀取、模型、renderer trajectory／visibility／depth、GT、API、演算法測試或產品 UI。工程片段不代表人物身分、物理可通行、完整追蹤或正式研究接受。
