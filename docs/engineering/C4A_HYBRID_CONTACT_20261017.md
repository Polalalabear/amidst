# C4a 混合接地估計器（2026-10-17）

Model / effort：**gpt-6.1-sol / high**。Refs [#15](https://github.com/Polalalabear/amidst/issues/15)，CP2 [#26](https://github.com/Polalalabear/amidst/issues/26)，未核准前不可合併。

已實作逐觀測 POINT／SEGMENT／UNKNOWN 估計，接上原工作台的品質註記邊界。
**依據未核准草稿（PR #10）**，釘選遠端契約 commit `586f1321cbfde24cfcdb73c500a24c1183c97c0d`。
不修改原 `world_position`、31 個觀測、track、曲線狀態或既有 `contact_quality`；不替換端點、不呼叫 K1。

## 首個 Office 驗收案例

| 原端點 | 本次公開估計 | 原始區間長度 | >8m／SEGMENT_TOO_LONG | 品質理由原樣保留 |
| --- | --- | --- | --- | --- |
| FRONT 4.4s，`observation:add9f687d311742321e80dff` | UNKNOWN／NONE，HEAD_ANCHOR_UNRELIABLE | 未計算，null | 未判定區間長度；不是超長拒絕 | LOW_INCIDENCE、CONTACT_OCCLUDED、AMBIGUOUS_MERGE |
| REAR 8.6s，`observation:997166541f223b4f923d8bff` | UNKNOWN／NONE，SEGMENT_TOO_LONG | **10.237160757m** | 是 | LOW_INCIDENCE |

既有31個Office觀測：29個 `SEGMENT_TOO_LONG`、2個 `HEAD_ANCHOR_UNRELIABLE`，0 READY／POINT／SEGMENT。
這是目前沒有C7裁切資料時的實際結果；未用較小容差湊出可用端點。
4.4s同幀另一個v1元件也帶AMBIGUOUS_MERGE，同樣拒絕頭錨，不自行改選4.2s。
D7替代屬C4b責任；本模組沒有端點替代或可用性選擇器。

[凍結預測](C4A_OFFICE_PREDICTIONS_20261017.json)保留每個觀測的完整輸出／output hash、
診斷用raw近遠端與長度。失敗時公開 `estimate_kind=NONE`、`segment=null`；診斷座標不得當合法端點使用。

## 8.6s與粗障礙標註的關係

[獨立端點診斷](C4A_OFFICE_ENDPOINTS_20261017.json)：**先寫完預測、固定SHA-256，才讀取**
`data/scene_audit/school_v3_approved_scale_20261006/geometry.json` 的 `OBSTACLE_1F_OFFICE_01`。
該標註只作比較，不是推論、遮擋裁切或walkable輸入，也不是C7來源地圖。

- 舊8.6s v1點位於粗標註內。
- 10.237160757m原始頭部區間與粗標註重疊 **1.789891237m**；區間不全在標註內。
- 標註XY bounds為 `[28.870657715,52.443997607,36.768585229,57.083111084]`m。
- 本次未以標註裁短區間、未snap到最近可走點、未改地圖。C7來源地圖到位後須重新計算裁切及8m門檻；目前不宣稱K1可產出路徑。

## 逐run先驗與建議容差

[版本化設定](../../configs/hybrid_contact_v1.json)在首次計算前固定，按run_id索引，不按影格或結果調整。

| run | 宣告高度／半徑m | 頭高先驗m | 狀態 |
| --- | --- | --- | --- |
| blender-pilot-office-baseline-v1 | 2.9393／0.1482 | 2.9393±0.10 | **合成圓柱，非人體尺寸**；±0.10是本次工程建議，尚未核准 |
| blender-contact-control-office-person-20261016-v1 | 1.70／0.25 | 1.70±0.10 | D5/D6；人形尺寸合成圓柱，仍非真人驗證 |

建議舊run也先用±0.10m作可重現的工程先驗，以同一設定檢查高度敏感度；它不是合成人物尺寸分布、
統計誤差界或GT估得容差。保留超長失敗，不為滿足8m而縮窄。既有2.9393m／0.1482m的由來仍UNKNOWN，留待C7。
原契約將舊run容差標UNKNOWN；本次明確提出且先固定建議值，在Deviations保留未核准狀態。

每個輸出帶run_ref、clock_id、source／safe-input／config SHA、宣告ref／hash、body radius、prior與gt_read=false。
未登錄run不借用另一run或預設身高，回報HEIGHT_PRIOR_UNAVAILABLE。
contact設定的height／radius與宣告不符時直接失敗 `CONTACT_TARGET_DECLARATION_MISMATCH`。
現有禮堂control沒有本次run宣告，因此新增ground欄位保持UNKNOWN，不影響原v2點。

## 投影與裁切

[純估計器](../../src/amidst/engineering/hybrid_contact.py)：

1. PASS且有可驗證v2接地點：重用相同v2 contact_pixel／校正／floor投影，輸出POINT，核對逐像素敏感度；不回寫原v1位置。
2. FLAGGED僅LOW_INCIDENCE／CONTACT_OCCLUDED：用唯一對應的同一v2元件bbox頂邊中心，套用逐run高低兩平面，得到地板區間。
3. AMBIGUOUS_MERGE／TOUCHES_IMAGE_EDGE或未評估旗標：UNKNOWN。status／reasons完整保留。
4. 頭射線須向下，鏡頭高於先驗上界，沿用InverseProjectionService的pixel／pose／clip規則。
5. 按HEIGHT_PRIOR→OCCLUDER_BEHIND→WALKABLE_AREA固定次序裁切。沒有資料即NOT_AVAILABLE，區間不變。
6. 只接受來源hash、floor z、body radius及幾何內容hash相符的SOURCE_DERIVED clip；拒絕ANNOTATION_ONLY。
   遮擋clip須明確是該鏡頭的「腳點隱藏區」mask，普通障礙物足跡不能充當遮擋後方區域。
7. WALKABLE UNKNOWN區保留並計算 `walkable_unknown_length_m`；空／多段／超8m分別UNKNOWN，不移動或延長區間。
8. POINT與SEGMENT逐觀測計算8方向±1px敏感度；SEGMENT對擾動後區間重做相同裁切。
   敏感度不可算則UNKNOWN，不是誤差界或機率。

**真實來源裁切接線尚待C7。** 本PR提供hash-bound `SourceClip`介面與合成幾何測試，
原Office實測兩個幾何步驟都是NOT_AVAILABLE；沒有把展示模型或粗標註升權。
接C7時須提供來源衍生的walkable與camera-specific foot-hidden masks；不能只塞家具足跡。

## 工作台接入與MISSING

[contact_scene.py](../../src/amidst/workbench/contact_scene.py)在現有query／frame query／重建／target／physical review
註記邊界附加 `ground_estimate`，同時保留凍結索引。別名scene_id只更新新欄位provenance及hash，不更動來源run。
單純GET只讀預先計算的估計，不在查詢時跑RGB或裁切。啟動指紋納入新設定檔。

新person run的33筆v2觀測原world_position都仍null、state仍MISSING，既有外層品質欄位行為也不變；
新增ground_estimate可帶來源v2品質旗標及合法頭部區間。這只增加旁欄，不能視為曲線位置已補齊。
新run的直接adapter驗證通過；該run的preset／fixture仍由未合併的C6 PR #34提供，C4a不複製它們。
後續整合須保留C6的逐run contact_config載入，舊全域contact設定無法載入人形run時會明確失敗。

POINT使用v2位置，若原v1位置不同，原位置仍不變。這是依使用者「用v2地板投影」的明確偏離：
草稿§4.1所稱existing projected point不被重寫，v2點只放在新欄位。
canonical hash採既有registry.content_hash（排序keys、緊湊JSON、allow_nan=false），不事後改小數精度；IO-Q7仍待核准。
額外diagnostics只供解釋拒絕，不能覆蓋公開status／kind／segment。

## 驗證與未驗證

- 新純函式26個測試：POINT／SEGMENT、旗標逐字保留、hash確定、缺／壞先驗、向上射線、非剛體姿態、
  遮擋與walkable順序、空／不連續區間、UNKNOWN區保留、錯source／floor／radius／hash／tier拒絕、超長與GT隔離。
- 同範圍工作台／v2／launcher聚焦回歸合計 **51 passed，0 failed／skipped**；原Office七組回應去除新增欄位後canonical hashes不變，仍31觀測。
- 人形run直接adapter測試確認MISSING不改、逐run1.70m先驗可產生SEGMENT，且拒絕錯用舊contact尺寸。
- 未跑全套測試、未渲染／修改原資產、未存blend、未啟停服務、未做瀏覽器驗收。
- 未驗證：C7真實source裁切、RQ1區間涵蓋率／GT評估、K1 READY、D7替代、完整新preset整合與正式研究指標。
  GT與renderer軌跡／visibility／depth不進入估計或裁切；本次沒有讀GT作評估。

## 重現

```sh
PYTHONPATH=src:scripts uv run python scripts/run_hybrid_contact.py \
  --bundle .local-worktrees/phase1-finalization/data/engineering/local_run/blender_camera_v1/office \
  --output /private/tmp/c4a-predictions-new.json \
  --diagnostic-geometry data/scene_audit/school_v3_approved_scale_20261006/geometry.json \
  --diagnostic-output /private/tmp/c4a-endpoints-new.json
```

需既有資產與環境；輸出檔須不存在，且不能寫入輸入bundle內。實際本次uv命令／artifact SHA以PR及#15 Actual output為準。
C7 Office（10/22）接續；C5索引/API仍未實作，依原順序留在C7與PR #32小修之後。
