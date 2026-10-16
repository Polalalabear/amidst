# Office 綠球（地板估計標記）診斷 — 2026-10-16

> 範圍：Office run `blender-pilot-office-baseline-v1`（dataset `2367ecc3…`）與 Codex 底部可見驗證 run `blender-contact-control-auditorium-v1`。唯讀診斷：未修改程式、fixture、`.blend`、RGB 或 GT，未渲染。程式符號依 [管線地圖](OFFICE_PIPELINE_MAP.md)（釘選 `a551a8b`）。
> 影格位於本機資產 checkout `data/pilot/school_v3_multisite_20261005/office/frames/` 與 `data/pilot/contact_control_20261016_v1/auditorium/frames/`，不在本 repository；本文不附影像，可依 §6 重現。

## 1. 結論

| 現象 | 確認原因 | 不是 |
| --- | --- | --- |
| 綠球在 0.4→0.6 s、1.8→2.0 s 亂跳 | FRONT 圓柱**底部被前排椅背遮住**，`contact_pixel`（bbox 底邊中點）取到遮擋線；視線入射角僅 0.158–0.188，1 px 約 0.12–0.24 m | 不是分軌（全部同一 track）、不是 <28 px 被丟、不是投影失敗 |
| 綠球只在 2.2–4.4 s 顯示 | 兩個跳點超過 `MAX_SPEED_M_S=8.0`，曲線切成 [0.0–0.4]、[0.6–1.8]、[2.0–4.4]；選定候選只連到最後一段 | — |
| 4.4 s 出現兩個位置 | 4-連通把輪廓切成兩元件，地板交點相距 4.395 m | — |
| REAR 在 FRONT 可見時沒有偵測 | REAR 0.0–8.2 s 的 42 張影格**解碼後逐像素相同**（hash 不同僅因 PNG metadata）；8.4 s 首次變化、8.6 s 出現目標 | 不是偵測器漏抓、不是背景吸收、不是對比不足 |
| 單位疑慮 | 後端已轉公尺：地板 z = 0.496 m = 20.08 BU × 0.0247 | 前端不需再換算 |

圓柱本身在 Blender 為**直線等速**移動（`plan_blender_pilot_sites.py` `main`：`t = frame_id/5`，10 s 線性）。REAR 前段看不到是路線規劃刻意的「可見→盲區→可見」（`candidates` 分數優先有缺口者），不是渲染錯誤。

## 2. FRONT 逐幀證據（選定 track `track:a7807f56197f0e8655944fed`）

- 0.0–4.4 s 共 23 個偵測全部屬同一 local track，無缺幀；相鄰接地像素最大位移 11–13 px，在 28 px 門檻內。
- 23 個 bbox 中 19 個為 `MERGED_OR_PARTIAL`；bbox 上緣皆在 y = 11–12。
- bbox 底邊 y：136 → 125（0.6–1.8 s）→ 135（2.0 s）→ 141–147（2.2–4.4 s）；x 每幀約 +3 px 平穩移動。

| 區間 | 地板跳距 | 推算速度 | 接地 y |
| --- | --- | --- | --- |
| 0.4 → 0.6 s | 1.703 m | 8.51 m/s | 135 → 124 |
| 1.8 → 2.0 s | 2.006 m | 10.03 m/s | 121 → 134 |

段內步距 0.04–0.24 m（2.0→2.2 s 為 0.79 m，仍低於上限）。REAR 8.6–9.8 s 全部屬 track `009a7986…`，步距 0.07–0.25 m，無斷點。

## 3. REAR 遮罩診斷

對 REAR 0.0–4.4 s 的 23 幀，以放寬門檻（差值 >15、8-連通、≥5 px）分別用正式背景（50 幀中位數）與 5.0–8.4 s 中位數背景計算：兩種背景完全相同、所有幀差值皆為 0。以圓柱在 REAR 9.0 s（RGB 80,33,7）與 FRONT 2.2 s（RGB 105,46,10）的顏色比對，0–8.2 s 無任何像素落在各通道 ±25 內。

## 4. 頭頂映射可行性分析

問題：以頭頂為節點、沿射線映射到固定高度平面，能否避開低矮遮擋？以 FRONT 攝影機（離地約 3.29 m）、目標水平距離約 17.8 m 估算；每像素角度以約 60° 水平視角推估（焦距未查，地板一列與 QA 實測 0.123–0.241 m 吻合）。

| 映射平面 | 攝影機高出平面 | 入射角 | 每 1 px 位置誤差 | 高度假設差 10 cm 的誤差 |
| --- | --- | --- | --- | --- |
| 地板（腳點） | 3.29 m | 0.185 | 約 0.12 m | 不需假設 |
| 頭頂（1.7 m 人） | 1.59 m | 0.089 | 約 0.24 m | 約 1.1 m |
| 頭頂（2.94 m 合成圓柱） | 0.35 m | 0.02 | 約 1.1 m | 3 cm 即約 1.5 m |

結論：本配置為近水平遠拍，頭頂平面更貼近射線，誤差放大並引入身高未知；只用頭頂不可行。頭頂法僅在攝影機明顯高於頭頂（俯拍）或目標很近時較佳。採用「腳點優先、腳點被擋時頭頂射線＋身高範圍輸出區間，再以遮擋物幾何與可走區域裁剪」的混合法，見 [計畫 §3](../agents/OFFICE_DEMO_PLAN_20261101.md#3-方法觀測--假設--檢索--驗證)。

## 5. perception v2 驗證結果獨立重算

依 Codex 輸出的 `data/engineering/contact_control_20261016_v1/` CSV 重算（Claude，2026-10-16）：

| 項目 | v1 | v2 |
| --- | --- | --- |
| 配對 62 點平均誤差 | 0.155 m | 0.097 m |
| 配對 62 點最大誤差 | 0.356 m | 0.133 m |
| 有位置的時刻 | — | 47/50 |
| v2 拒絕原因 | — | `LOW_INCIDENCE` 35、`TOUCHES_IMAGE_EDGE` 3、`CONTACT_OCCLUDED` 1 |
| Office 原 run 位置數 | FRONT 24＋REAR 7 = 31 | **0**（FRONT 23 次 `LOW_INCIDENCE`、1 次 `CONTACT_OCCLUDED`；REAR 7 次 `LOW_INCIDENCE`） |

觀察：底部可見時 v1 誤差已僅約 0.1–0.2 m，證實 Office 的 1.7–2 m 跳動來自遮擋。v2 的 `CONTACT_OCCLUDED` 沒有抓到 Office 0.4–2.0 s 的椅背遮擋（這些幀是因 `min_incidence = 0.25` 被拒）；在驗證 run 中，該門檻也拒絕了部分底部清楚、v1 誤差僅 0.13–0.19 m 的點。結果僅代表合成驗證。

## 6. 重現

- 逐幀表與 REAR 遮罩診斷：以 `scripts/office_demo_backend.py` `load_scene` 在程序內載入 Office bundle（safe inputs hash 需相符），讀取 observations／projections；遮罩重算沿用 `perception.py` 的背景與差值定義，只改門檻。
- 對照圖：以 PIL 讀原影格，疊上 `auditorium-comparison.csv` 的 `old_pixels`（v1）與 `new_pixels`（v2，保留／拒絕分色），輸出到暫存目錄，不寫回資產。
- v2 數字：讀 `auditorium/errors.csv` 的 `v1_errors_m`、`v2_errors_m`，只在兩者皆非 null 時配對。
