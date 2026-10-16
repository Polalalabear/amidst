# C6 渲染前篩選與來源視線修正（2026-10-17）

Model / effort：**gpt-6.1-sol / high**（實際 session 值）。[PR #34](https://github.com/Polalalabear/amidst/pull/34)，CP1 未核准，不合併。

**尚未選出要求的 10–15 條基準。** 最後一輪以固定名目速度 1.5 m/s／≤10 s 排程搜尋，
加入來源可見性與接地中點失敗的邊限制後，兩輪即穩定：244 條提出路線、45 條單路線合格，
但跨鏡頭合格數仍為 0，整批 selected=0／`NOT_READY_INSUFFICIENT_QUALIFIED_ROUTES`。
基準候選與控制均未渲染。這是有界、採樣網路的結果，**不是連續場域不可行證明**。

[Office 1.70 m／r0.25 m 同路線新 run](OFFICE_PERSON_RERENDER_20261016.md)已完成 100 PNG、
獨立 bundle／fixture／可選場景預設；v2 33 元件全因 LOW_INCIDENCE 保持 MISSING。

## 固定規則與時間範圍

| 項目 | 最新規則 |
| --- | --- |
| 速度帶 | 1.0–2.0 m/s，CONFIGURED_NOT_GT，未依 GT／結果調速度帶 |
| 實際規劃排程 | 固定 1.5 m/s；duration = length / 1.5，≤10 s；最大 15 m |
| 每側可見段 | ≥2 s × 速度帶下限 1.0 = 2.0 m |
| 盲區旁連續接地合格段 | 每側 ≥1 s × 上限 2.0 = 2.0 m，逐點 bottom eligible 且 incidence≥0.25 |
| 盲區長度 | ≥2.5 m |
| 跨鏡頭比例 | ≥60%；同鏡頭長盲區最多 1 條，不用降級樣本補數 |
| 轉彎 | RDP 0.4 m 化簡後，只計盲區內 >30°；不改動受檢路線 |
| 可見性 | 五台任一腳／軀幹／頭探針 VISIBLE 就非盲；候選每 0.125 m 複查 |
| 資料權限 | 僅來源規劃，inference_input_eligible=false；不讀 renderer GT／逐幀 visibility／depth |

[v5 設定](../../configs/c6_prescreen_v5.json)保持速度與接地／盲長門檻；[v4](../../configs/c6_prescreen_v4.json)
已將窗長與實際固定名目速度排程綁定。舊 [10/16 報告](C6_PRESCREEN_20261016.md)按速度下緣
也必須 ≤10 s 的較保守結果保留為歷史；最新規則不要求尚未採用的 1.0 m/s 也能完成同一條 15 m 路線。
若之後改 render speed，必須重新驗證窗長，不能依結果提高 D12 上限。

**待釐清驗收時域：**目前「單一盲區」要求加密空間採樣中沒有中間可見島；
實際 5 Hz 影格可能漏掉短於 0.2 s 的可見片段。是否只按實際影格判盲須由使用者明確決定，
本次維持連續空間的保守解讀。無論哪種解讀，C5 在某點只要任一探針可見就不能標為盲，
並須保留影格之間的可見／UNKNOWN 狀態，不抹去來源證據。

## 為何格點提出的跨鏡頭路線被剔除

0.25 m 格點的 512 條候選經來源射線每 0.125 m 複查：255 條兩端鏡頭不同的候選，
**全部**有中間可見島，原因 `NOT_SINGLE_INTERIOR_BLIND_INTERVAL`。其餘剔除原因包含
盲區太短（201 次）與鄰接接地段不足（2 次）；理由可同時出現，不能相加當路線總數。

例如 raw gap 006 的固定名目排程 7.0 s，盲段沿程為 `[2.125,3.5]`、`[3.75,8.375]` m，
3.625 m 的採樣重新可見，把原先以格點串接的一段分為兩段；兩側盲採樣距離差 0.25 m，
在名目 1.5 m/s 下對應不足 0.167 s 的局部可見片段。這不是速度超窗造成的剔除。

[邊診斷](C6_VISIBILITY_EDGE_AUDIT_20261017.json)重建 22,901 個 physical graph edges，核對 512 份
逐盲段剖面、935 條實測中點邊，找出 6 條「兩端格點全盲、實際中點可見」的邊。
這說明格點中心不能直接證明整條邊或整個 cell 不可見。

接著 [來源視線修正器](../../scripts/refine_c6_visibility.py)重讀同一 source hash／frame 220／
calibration，沿用原已驗證的 body／support graph；不重新賦予 walkability authority。
它將已測到的中點可見、visible 段中斷、腳點資格中斷作為搜尋邊限制，最多 4 輪。
這次第一輪再發現 4 條可見性／接地限制邊，第二輪無新增限制並穩定；未擴大場域或改門檻。

| 修正輪次 | 提出路線 | 單路線合格 | 跨鏡頭合格 | 入選 | 新限制邊 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 488 | 45 | 0 | 0 | 4 |
| 2 | 244 | 45 | 0 | 0 | 0 |

兩輪都沒有達到跨鏡頭多數，不把 45 條同鏡頭資料當成 RQ3 基準；
停止於有界結果，未嘗試虛擬攝影機。提出路線仍非完備搜尋，不能宣稱全場域無解。

## Review 項目與實際狀態

1. 原 12 條全部剔除；逐條起端／終端／兩端接地、可見長度、盲區轉彎與原因見
   [原 12 條核對](C6_PRESCREEN_20261016.md#舊-12-條逐一核對)。按已提交 JSON 為 0/12 兩端合格；
   review 所稱 01、05 兩條兩端合格未重現（01 終端 list 空、05 起端 list 空）。
2. 速度／時間／2 m 兩側段、≥2.5 m 盲區都已設門檻；新路線均逐候選量測。
3. 轉彎 `turns_in_blind`／原採樣 index／角度均輸出；原 02、03 為 0，舊「均含轉彎」解讀已撤回。
4. 單路線診斷資料有相鄰可見邊界／潛在出口摘要。這些不是語意 portal，也沒有實際排除任何出口；
   C5 索引與合法 NO_DETECTION、K1 驗證尚未完成。
5. [原材質屬性](C6_MATERIAL_PROPERTIES_20261017.json)涵蓋 21 個遮擋物。9 個物件有明確 alpha slots，
   包括 `instance_26.003/.004/.005/.007/.008/.009`、`instance_27.007/.008/.009`；
   `__Ivory_` alpha≈0.098039、`__Glass_Sky_Reflection_` alpha=0，舊 gap 02／07 受影響。
   HASHED/DITHERED 但 alpha=1 只標潛在設定風險；物件 slot 不等於 hit face 材質，渲染後仍需 RGB 抽查。
6. 原篩選已有 90 筆／26 條不同窄口邊的 72 點環支撐＋掃掠抽查，全部通過，證據見
   [歷史完整 JSON](C6_PRESCREEN_20261016.json)。門口／座椅語意仍 UNKNOWN；C7（10/22）到位後
   必須用推導地圖再核對，不能把本次 source-mesh box-clear 升權成通行認證。
7. 連續 benchmark ID 與 raw／舊 gap 對照機制已加入並測試；實際 selected=0，mapping 空，沒有編造入選 ID。
8. 純 visibility 可注入 raycast；FOV 內被擋、OUTSIDE_FOV、CLIPPED、clear、任一探針可見、
   中間可見島必須剔除都已有測試。
9. [C5 驗收紀錄](C5_VISIBILITY_ACCEPTANCE_20261016.md)與 #18 已補同一定義；C5 API 尚未實作。

## 產物與驗證

- [512 條完整剖面與篩選](C6_PRESCREEN_20261017.json)：包含全部被拒路線的各盲段距離。
- [來源邊剖面核對](C6_VISIBILITY_EDGE_AUDIT_20261017.json)。
- [來源視線回饋搜尋結果](C6_SELECTED_ROUTES_20261017.json)：兩輪、0 selected、5 條未渲染 controls。
- [固定規則與 waypoint 純函式](../../scripts/c6_prescreen.py)、[修正器](../../scripts/refine_c6_visibility.py)。
- [Office 新 run 收據](OFFICE_PERSON_RERENDER_20261016.json)。
- 47 個 focused 測試通過（含原 Office 31 觀測／七組 canonical hashes 回歸）；未跑全套測試。
- source hash／size／mtime 不變。未存 `.blend`，未渲染基準／控制、未改 K1／main，未啟停服務。
- 未驗證：10–15 條合格基準、RGB 接地品質／短可見片段是否形成偵測、完整連續 floor support、
  C7 地圖／新 Office 半徑 clearance、混合區間、K1 READY、瀏覽器／Demo 與正式研究指標。

實際指令與 hashes 以 PR／#19／CP1 的最新 Actual output 為準。輸出均拒絕覆寫；
重新產生需新輸出名稱，重新渲染則另需新 run_id，不能覆寫既有資料。
