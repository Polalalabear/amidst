# C6 渲染前篩選（2026-10-16）

Model / effort：**gpt-6.1-sol / high**，本次 session 實際值。分支 `codex/c6-multicamera-feasibility`；
[PR #34](https://github.com/Polalalabear/amidst/pull/34)，CP1 #25 未核准，不合併。

**結論：尚不能選出要求的 10–15 條基準。** 0.5 m 與 0.25 m 兩次搜尋保持相同速度／篩選門檻；
0.25 m 搜尋 257 條路線，45 條通過單路線接地／長度／窗長門檻，但全為同鏡頭再出現
（C02→C02 44 條、C03→C03 1 條）。跨鏡頭比例不足，選定 benchmark 數為 **0**，
狀態 `NOT_READY_INSUFFICIENT_QUALIFIED_ROUTES`。未用降級樣本補成 10 條，也未渲染候選或對照。
這是有界搜尋結果，**不是全場域不可行的證明**；新鏡頭或擴大語意區域尚未授權／驗證。

Office 原路線的人形尺寸獨立重渲染已完成，見[新 run 報告](OFFICE_PERSON_RERENDER_20261016.md)。
基準篩選與這份同路線診斷 run 的速度設定分開：Office 保留原 10 s／原足點，不改動它來迎合基準門檻。

## 固定規則與兩次搜尋

- [v2 設定](../../configs/c6_prescreen_v2.json)：0.5 m 空間格點。
- [v3 設定](../../configs/c6_prescreen_v3.json)：只改為 0.25 m 格點；同一份已固定的速度與驗收規則。
- 速度帶 `[1.0, 2.0]` m/s、名目 1.5 m/s、`CONFIGURED_NOT_GT`。在搜尋／評估前固定，未依 GT 或結果調速度。
- `MAX_WINDOW_S = 10.0`，與現有 `blender_motion.py`、`frame_baseline.py` 一致；
  每條路線長 ≤10 m，所以連速度下緣 1.0 m/s 也不超窗，不需提高速度上限。
- 每側可見段至少 `2 s × 1.0 m/s = 2.0 m`。緊鄰盲區每側連續腳點合格段至少
  `1 s × 2.0 m/s = 2.0 m`，即在速度上緣仍滿 1 s。逐點要求 v2 bottom list 非空、
  腳點 VISIBLE、incidence ≥0.25；另外核對 45 條兩側採樣的鏡頭集合有非空交集。
  這是幾何接地資格，不等於 RGB contact_quality PASS，也未實作 D7 觀測替代。
- 盲區採樣首尾距離 ≥2.5 m；跨鏡頭候選須佔 ≥60%；同鏡頭長盲區最多 1 條、每對鏡頭最多 4 條，
  並限制路線採樣重疊 ≤80%。目前跨鏡頭候選為 0，故整批不放行。
- 四鄰圖與來源網格 body-box／支撐規則不變；0.25 m 搜尋 31,577 格點、12,161 合格節點、22,901 邊。
  88 個接地合格盲區入口；原始 257 路線中 45 條具有一個足夠長的盲區，45 條單路線篩選通過。
  搜尋仍是有界 BFS／格點搜尋，不保證完整；沒有使用 renderer GT、既有 trajectory 或逐幀 visibility。

## 舊 12 條逐一核對

以下讀取原已提交 JSON（hash 維持 `87d8633da543d36d8013743b00a02cf9659cc573a3400a802d3751fbf21f5fbf`）。
按實際 `v2_bottom_eligible_cameras` 欄位，**0/12 兩端合格**；review 所稱 01、05 兩條兩端合格未能重現：
01 終端 list 為空，05 起端 list 為空。下表與機器證據保留實際結果。全部剔除。

| 原 gap ID | 起端接地 | 終端接地 | 兩端合格 | 新盲區內轉彎 | 狀態 |
| --- | --- | --- | --- | ---: | --- |
| 01 | 是 | 否 | 否 | 2 | 剔除 |
| 02 | 否 | 是 | 否 | 0 | 剔除 |
| 03 | 否 | 否 | 否 | 0 | 剔除 |
| 04 | 否 | 否 | 否 | 2 | 剔除 |
| 05 | 否 | 是 | 否 | 2 | 剔除 |
| 07 | 否 | 是 | 否 | 1 | 剔除 |
| 10 | 是 | 否 | 否 | 1 | 剔除 |
| 11 | 是 | 否 | 否 | 3 | 剔除 |
| 12 | 是 | 否 | 否 | 2 | 剔除 |
| 13 | 否 | 是 | 否 | 2 | 剔除 |
| 14 | 是 | 否 | 否 | 2 | 剔除 |
| 15 | 否 | 否 | 否 | 2 | 剔除 |

原「均含轉彎」的結論已撤回。新計算先以 RDP（0.4 m 容差）合併共線／格點階梯，再只數
盲區內、方向改變 **>30°** 的角點。`turns_in_blind`、角度、原採樣 index 都寫入 JSON。
原 02、03 的盲區內轉彎為 0；其餘 1–3。45 條未入選診斷路線為 31 條 1 轉、14 條 2 轉。
化簡僅供量測，不把未驗證的 chord 當成移動路線，不改原足點或連續掃掠檢查。

## 相鄰可見區、材質與窄口

每條新診斷候選均有 `adjacent_visible_regions_and_potential_exits`：盲區連通分量旁的可見邊界簇、
鏡頭 index、XY bbox 與 stable exit ref。這些不是語意門口，也沒有實際排除任何出口；
只有未來 C5 合法索引與同 run／clock、已評估的 NO_DETECTION 才可能作負證據，K1 尚未驗證。

原 12 與新候選的遮擋物均列 `transparent_occluders` 與 `rgb_material_spotcheck_required`。
[材質原值](C6_MATERIAL_PROPERTIES_20261016.json) 覆蓋 29 個來源物件；其中 9 個物件的 slots 有明確 alpha：
`instance_26.003/.004/.005/.007/.008/.009`、`instance_27.007/.008/.009`；
`__Ivory_` alpha 約 0.098039、`__Glass_Sky_Reflection_` alpha 0。舊 gap 02、07 的遮擋物清單包含它們。
其他 `HASHED`／`DITHERED` 設定但 alpha=1 的材料只標潛在風險，不能宣稱實際透明；
物件有材質 slot 也不代表該射線命中的 face 一定用該材質。沒有修改材質、渲染或儲存來源。
既有 Office 重渲染採 `pilot_workbench_opaque_studio_v1`，OBJECT 灰色不透明 snapshot；
它不模擬來源透明材質。將來改用來源材質或選定基準後，仍須逐路線 RGB 抽查。

窄口幾何抽查 90 筆（26 條不同邊）：每筆 9 個邊上位置 × 8 個身體半徑環點，共 72 支撐射線，
加連續掃掠盒，全部通過。鄰近來源物件包含 `group_0`、`group_0.003`、`instance_127/128`。
**是否真為門口／座椅之間仍 UNKNOWN**，未用名稱升權；C7（10/22）須核對語意與推導地圖。
每條候選有 `c7_map_recheck: PENDING_C7`，不得宣稱已完成 C7／可走性認證。
`edge_rejections` 為空有可解釋原因：同高、軸向邊且步距 ≤2r 時，連線掃掠盒等於兩個端點盒的聯集；
端點已通過同三角形相交檢查，邊不會額外拒絕同一障礙。密集支撐抽查仍不等於完整連續地板證明。

## 編號、證據與測試

選取器會給入選路線連續 `c6-benchmark-001...`，並保留 raw gap ID／舊 gap ID 的重疊來源對照。
目前選定數為 0，所以 `benchmark_id_mapping` 是空表；沒有替未入選路線捏造 benchmark ID。
45 條診斷資料保留 raw search gap IDs／舊 gap 對照，明示不是獨立統計樣本，也不得拿去渲染。

- [完整篩選 JSON](C6_PRESCREEN_20261016.json)（5.2 MB 規劃證據，不含 RGB 或 GT）。
- [純函式](../../scripts/c6_prescreen.py)：可注入射線的 visibility、三探針 union、化簡／盲區轉彎、接地／速度門檻、搜尋與選取。
- [C5 驗收紀錄](C5_VISIBILITY_ACCEPTANCE_20261016.md)：任一探針可見即不盲；C5 尚未實作。
- [專用測試](../../tests/unit/test_c6_feasibility.py)：19 passed；含 FOV 內被擋、OUTSIDE_FOV、CLIPPED／clear、
  任一探針可見、接地鄰接段不足、窗長、格點階梯化簡、只計盲區轉彎、跨鏡頭比例與連續編號。
- 加 Office renderer／per-run config／既有 Office frozen regression／launcher，共 43 passed。
  舊 Office 31 觀測與七組移除品質欄位後的 canonical hashes 仍通過。未跑全套測試。

實際執行（輸出拒絕覆寫；需現有來源與既有環境）：

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --disable-autoexec \
  --python-exit-code 1 blender/school_v3.blend \
  --python scripts/plan_office_demo_feasibility.py -- \
  --config configs/c6_prescreen_v3.json --output docs/engineering/C6_PRESCREEN_20261016.json
/Applications/Blender.app/Contents/MacOS/Blender --background --disable-autoexec \
  --python-exit-code 1 blender/school_v3.blend --python scripts/inspect_c6_materials.py -- \
  --input docs/engineering/C6_PRESCREEN_20261016.json \
  --output docs/engineering/C6_MATERIAL_PROPERTIES_20261016.json
```

剩餘缺口是「10–15 條且跨鏡頭佔多數」；在此五鏡頭、搜尋窗與固定門檻下未達標。
本次不放寬速度、接地或比例，不加虛擬鏡頭，不宣稱 READY；需要下一輪路線／鏡頭方案審查。
