# Office Demo 綠球管線地圖

> 狀態：釘選 commit `a551a8b`（只讀該 commit 內容，非工作樹）。目的：加速查找「綠球／綠色標記」從 Blender 路線到前端畫面的來源與斷點。
> 規則：引用以檔案＋符號名稱為準，不使用行號；程式變動後請更新本表。
> 註：程式內「綠色」實為 teal（`0x66dfd0`）；橘色（orange）是 Blender 內的合成目標，琥珀（amber `0xffc266`）是推論狀態。

## 1. 流程總覽

```text
[規劃] plan_blender_pilot_sites.py        直線、等速、50 點、角色 VGV / CONTROL
   -> [渲染] export_blender_pilot.py       每時間點移動橘色膠囊，各鏡頭 write_still（無 keyframe）
   -> [打包] blender_scene.py              safe_inputs.json（校正、100 張 RGB 指標、floor plane、5 Hz clock）
   -> [感知] perception.py                 時序中位數背景差分 -> 元件 -> contact_pixel -> 單鏡頭 local track
   -> [投影] frame_baseline.py + inverse_projection.py   contact_pixel -> source floor 平面交點（公尺）
   -> [曲線] blender_motion.py             PROJECTED_OBSERVATION / INFERRED_INTERPOLATION / MISSING 與 gaps
   -> [關聯] blender_association.py        跨鏡頭節點／邊／候選（INFERRED_CROSS_CAMERA）
   -> [審查] blender_physical_review.py    synchronized_evidence（samples + missing_intervals）
   -> [後端] office_demo_backend.py / BlenderSceneAdapter   載入、驗證、HTTP 回應
   -> [前端] physical-review.mjs -> scene.mjs               依時間取 evidence frame，畫 teal／amber 標記
```

## 2. 階段表

| 階段 | 檔案 | 主要符號 | 輸入 → 輸出 | 權限／狀態 |
| --- | --- | --- | --- | --- |
| 路線規劃 | `scripts/plan_blender_pilot_sites.py` | `SITES`, `candidates`, `main` | 來源 .blend 的可見性提示＋即時 raycast → 路線 plan（起訖、角色、50 samples） | 使用來源幾何與可見性做規劃（Ground Truth 側）；不進推論 |
| 渲染 | `scripts/export_blender_pilot.py` | `make_target`, `configure_render`, `main` | plan → `frames/<camera>/frame_NNN.png`、`dataset.json` | 合成目標；dataset 內含 ground_truth 僅供評估；`LABEL` 為 PILOT / SYNTHETIC SAMPLE |
| 打包 | `src/amidst/workbench/blender_scene.py` | `materialize_blender_workbench`, `_calibration`, `_safe_input_contract` | `dataset.json`＋pinned floor/scale 證據 → `safe_inputs.json`、`manifest.json` | 只抽取校正、RGB 指標、floor plane、模型；`_safe_input_contract` 限定欄位白名單 |
| 載入 | 同上 | `BlenderSceneAdapter`, `load_blender_scene`, `_verify` | bundle → `BaselineFrameIndex` / `BaselineMotionIndex` / `BaselineAssociationIndex` | 啟動時驗證 hash，查詢不開圖 |
| 感知 | `src/amidst/engineering/perception.py` | `produce_perception`, `_components`, `Measurement`, `LocalTrack` | RGB 影格 → measurements、local tracks、frame statuses | 只讀 RGB；`image_measurement=True`；身分 UNCONFIRMED |
| 投影 | `src/amidst/workbench/frame_baseline.py` | `BaselineFrameIndex.__init__`, `_project`, `_measurement_key` | 每個 measurement 的 `contact_pixel` → `world_position`、`projection_quality` | `geometry_authority=SOURCE_BOUND_FLOOR_INTERSECTION_ONLY` |
| 反投影 | `src/amidst/geometry/inverse_projection.py` | `InverseProjectionService.project_frame`, `InverseProjectionFailure` | 像素＋camera＋Plane → `ProjectedPoint` 或失敗原因 | 無 GT；失敗即 fail-closed |
| 曲線 | `src/amidst/workbench/blender_motion.py` | `BaselineMotionIndex`, `_build_track`, `reconstruct` | local track＋投影 → samples／velocities／gaps／events | 只在同一 track 的首末之間插值；不外推；不跨 track 接線 |
| 關聯 | `src/amidst/workbench/blender_association.py` | `BaselineAssociationIndex`, `_edge`, `_route_samples`, `reconstruct` | 各鏡頭 motion 節點 -> 邊（時間差／速度／重疊距離）-> Top-K 候選路徑 | 分數是 `CONFIGURED_COMPATIBILITY_NOT_PROBABILITY`；身分 UNCONFIRMED |
| 審查 | `src/amidst/workbench/blender_physical_review.py` | `BlenderPhysicalReviewIndex._motion_evidence`, `snapshot`, `_STATES` | 物理基線候選的 path samples/gaps -> `synchronized_evidence` | `position_filled=False`、`identity_confirmed=False`；樣本上限 `MAX_SAMPLES` |
| 後端入口 | `src/amidst/workbench/blender_scene.py` | `BlenderSceneAdapter.physical_review_index`, `physical_review`, `bind_physical` | 已綁定 physical source -> review 回應 | 未綁定則 `PHYSICAL_REVIEW_UNAVAILABLE` |
| 後端驗證 | `scripts/office_demo_backend.py` | `load_scene`, `reproduce` | fixture＋bundle -> 收據 | 見第 3 節固定值檢查 |
| 前端資料 | `frontend/workbench/physical-review.mjs` | `physicalReviewScenePlan`, `physicalReviewEvidenceFrame`, `physicalReviewEvidenceAt` | review 回應 + 時間 -> 當下可顯示 samples | 顯示用；`physical_certification:false` |
| 前端 3D | `frontend/workbench/scene.mjs` | `reviewEvidenceMarker`, `setPhysicalReviewTime`, `updateCrossCamera`, `makeBody`, `updateBodies` | evidence frame -> teal／amber 標記、cursor、人形 | 純呈現；不補點、不外推 |
| 前端跨鏡頭 | `frontend/workbench/cross-camera.mjs` | `crossCameraCursor`, `crossCameraSegments`, `crossCameraScenePlan`, `groundContactBasis`, `candidateEvidenceOverlays` | candidate path -> cursor／線段／2D bbox | 同一 cursor 規則供 3D、面板、2D 使用 |

## 3. 常數與門檻

| 常數 | 值 | 檔案＋符號 | 影響（綠球何時斷或偏） |
| --- | --- | --- | --- |
| 目標半徑／高度／probe 高／離地裕度 | 6.0 / 119.0 / 55.0 / 0.05（Blender 單位） | `plan_blender_pilot_sites.py` `main`（`radius, height, probe_height, margin`） | 目標約 0.148 m 半徑；`make_target` 要求 `height == 2*probe + 1.5*radius`，否則報錯 |
| 取樣 | 50 點，`t = frame_id / 5`，10 s 線性等速 | `plan_blender_pilot_sites.py` `main` | 時間戳 0.0–9.8 s、5 Hz；速度恆定，非行走步態 |
| 路線分數 | `(bool(gap_count), active, min(gap_count,10), length)` | `plan_blender_pilot_sites.py` `candidates` | 先選「有缺口」者，故 VISIBLE_GAP_VISIBLE 優先於 FULLY_OBSERVED_CONTROL |
| 角色篩選 | VGV 缺口必須連續且首尾可見；CONTROL 不得有缺口 | `plan_blender_pilot_sites.py` `main` | 拒絕原因如 `LIVE_VISIBILITY_NOT_CONTIGUOUS_VGV` |
| 尺度 | `METRES_PER_BU = 0.0247` | `blender_scene.py` 引用自 `source_presentation`（本次僅查到定義值） | 校正平移與 clip 乘此值；`safe_inputs` 的 `metres_per_bu` 不符即拒絕 |
| 時鐘 | `BLENDER_PILOT_CONFIGURED_SECONDS_5HZ`，`sampling_hz: 5`，影格 960x540 | `blender_scene.py` `materialize_blender_workbench`, `BlenderSceneAdapter` | 0.2 s 一格，frontend 容差由此推得 |
| 背景 | 每鏡頭全部有效影格的逐像素中位數 | `perception.py` `produce_perception` | 目標長時間停留會被吸進背景而漏偵測（本資料是否發生：UNKNOWN） |
| 前景閾值 | `max-channel |diff| > 30` | `perception.py` `produce_perception` | 門檻附近的目標邊緣會碎裂 |
| 連通性／最小面積 | 4-connected BFS；< 28 px 丟棄 | `perception.py` `_components` | 窄遮擋輪廓被拆成兩元件或丟棄 |
| contact pixel | `((xmin+xmax-1)/2, ymax-1)` bbox 底部中央 | `perception.py` `produce_perception` | 下半身被遮擋時，接地點上移，地板交點偏遠 |
| MERGED_OR_PARTIAL | `bbox 寬 > 32` 或 `bbox 高 < 20` | `perception.py` `produce_perception` | 只是 heuristic 標記，仍然產生 measurement 並被投影 |
| uncertainty | `min(1, 0.25 + 0.35*merged + 0.15*(alternatives>1))` | `perception.py` `produce_perception` | 不是公尺誤差也不是機率 |
| local track | `0 < dt <= 0.61 s`，距離 `<= 28 px * max(1, dt/0.2)`，貪婪最近鄰 | `perception.py` `produce_perception` | 一個 frame 的所有元件都成為 measurement，會併入或開新 track |
| 每幀代表 | 最低 `uncertainty`，再比 status、alternatives、id | `frame_baseline.py` `_measurement_key`, `BaselineFrameIndex.__init__` | 只影響 frame 記錄／Top-K；motion 用的是 local track 的全部 observation |
| 影格上限 | `MAX_FRAMES_PER_CAMERA = 128`, `MAX_INPUT_FRAMES = 400`, `MAX_CAMERAS = 4` | `frame_baseline.py` | 超量即拒絕載入 |
| 反投影品質 | `projection_quality = min(1, incidence)`；僅 `incidence <= 1e-12` 判平行 | `inverse_projection.py` `project_frame` | 沒有 grazing 門檻，低入射角仍標為 PROJECTED |
| 曲線上限 | `MAX_CAMERAS=4`, `MAX_WINDOW_S=10.0`, `MAX_POINTS=400`, `MAX_TRACKS=32` | `blender_motion.py` | 查詢範圍限制 |
| 插值缺口 | `MAX_INTERPOLATION_GAP_S = 1.0` | `blender_motion.py` `_build_track` | 超過即 `LONG_GAP`，該段不插值（Office 的 4.4 到 8.6 s 為 4.2 s） |
| 速度上限 | `MAX_SPEED_M_S = 8.0` | `blender_motion.py` `_build_track` | 超過即 `SPEED_CAP` 斷線；單一錯誤投影會切斷綠色曲線 |
| 關聯 | `MAX_OVERLAP_DISTANCE_M=0.75`, `_BRIDGE_STEP_S=0.2`, `MAX_GRAPH_NODES=64`, `MAX_GRAPH_EDGES=256`, `BEAM_WIDTH=256` | `blender_association.py` | 時間差上限用 `MAX_WINDOW_S`；速度同用 `MAX_SPEED_M_S` |
| 後端固定值 | 100 張 RGB、時間 `i/5`、`len(errors) == 31` | `office_demo_backend.py` `reproduce` | 31 為 `world_position` 非 null 的 observation 數；改感知／投影會直接破壞此斷言 |
| 前端容差 | `tolerance = min(.100001, 最小步長/2 + 1e-6)`；cursor 預設 `.100001` | `physical-review.mjs` `physicalReviewEvidenceFrame`；`cross-camera.mjs` `crossCameraCursor` | 超過半格無證據即不顯示 |
| 前端標記上限 | `REVIEW_MARKER_LIMIT = 24` | `physical-review.mjs` | 同時刻只畫前 24 筆，其餘記為 `omitted` |

## 4. 狀態詞彙

| 狀態 | 設定位置 | 前端顏色／行為 |
| --- | --- | --- |
| `PROJECTED_OBSERVATION` | `blender_motion.py` `_build_track`（`projection_status == "PROJECTED"` 且有 `world_position`） | teal `0x66dfd0`（review marker）；cross-camera cursor 用 path 顏色；顯示 nominal body 圓柱線框（`userData.nominalBody`）；`makeBody` 的實線人形為 `0x63dfdd` |
| `INFERRED_INTERPOLATION` | `blender_motion.py` `_build_track`（相鄰兩個可用端點、`dt <= 1.0 s`、`speed <= 8 m/s`） | amber `0xffc266`；隱藏 nominal body 線框 |
| `INFERRED_CROSS_CAMERA` | `blender_association.py` `_edge`, `_route_samples`, `_path`（跨節點線性橋接，步長 0.2 s） | amber `0xffc266`；連線標示為跨鏡頭關聯假設 |
| `MISSING` | `blender_motion.py`：無像素測量、`INVALID_PROJECTION`、gaps（`LONG_GAP`, `SPEED_CAP`, `NUMERICAL_FAILURE`）；`blender_association.py`：`CROSS_CAMERA_LONG_GAP` | 無位置；`USABLE_EVIDENCE` 排除，故不畫點；`world_position` 為 `null` |
| `UNKNOWN` | `identity_verdict` 預設 `UNCONFIRMED`、`behavior_verdict` 為 `UNKNOWN`；physical review 的 `status`／`default_decision` 與 `groundContactBasis` 的 `ground_contact` | 不畫位置；面板顯示未知；fixture 的 `physical_verdict` 為 `UNKNOWN` |

另有 `INFERRED_FINITE_DIFFERENCE`（速度區間，非位置），與 `INFERRED_GAP`（`scene.mjs` `updateBodies` 以 `marker.evidence_state==='INFERRED_GAP'` 選擇 amber 半透明人形；其來源端未在本次範圍確認）。`blender_physical_review.py` `_STATES` 只允許前四種位置狀態，其他狀態會丟 `PHYSICAL_REVIEW_SAMPLE_STATE_DENIED`。

前端顯示規則（`physicalReviewEvidenceFrame`、`crossCameraCursor`）：取容差內最近的可用 tick；`connect_from_previous !== true` 的段起點不會早於自身時間出現；線段終點不向後延續；落在 `missing_intervals` 內不補點、不 hold。段起點在 `scene.mjs` 以白色 ring 標示。

## 5. 已知限制（不宣稱已修復）

- 接地點：`contact_pixel` 是可見元件 bbox 的底部中央，不是量測腳點；座椅等遮擋會抬高底邊，使 floor 交點偏離。`groundContactBasis` 在前端明確把 `ground_contact` 標為 `UNKNOWN`。
- 掠射角：`projection_quality` 只是 incidence，沒有門檻；QA 文件記錄 ±1 px 在低入射角下地板位移約 0.123–0.241 m（本表不採用「0.15 m / px」這個單一值）。
- 4-connected 切分：窄輪廓可被切成兩個元件，QA 記錄 4.4 s 兩元件的地板交點相距 4.395073 m；每個元件各自成為 measurement。
- 速度斷線：單點錯誤投影造成的跳距（QA 例：0.4 到 0.6 s 約 8.5 m/s、1.8 到 2.0 s 約 10.0 m/s）超過 `MAX_SPEED_M_S`，曲線在 `SPEED_CAP` 處被切成多段。
- 選定目標（已確認）：Office fixture（`configs/office_demo_fixture_v1.json`）：`track_ref` 為 `track:a7807f56197f0e8655944fed`，`selected_timestamp` 4.4 s，`next_observed_timestamp` 8.6 s；`time_range` [0.0, 9.8]。
- 缺口性質：fixture 的 4.6–8.4 s 無偵測是「measurement gap」，不是已驗證的遮擋；缺口內位置維持 `MISSING`。
- 合成目標：橘色膠囊為 `SYNTHETIC_CAPSULE_MARKER_NOT_PHYSICALLY_CALIBRATED_PERSON`；site 為 office 別名（沿用 auditorium 兩鏡頭），房間語意未認證。
- 詳見 [OFFICE_CONTACT_SPATIAL_QA.md](OFFICE_CONTACT_SPATIAL_QA.md)（節標題：結論與實作範圍／已核對的資料流／指定時間點的原投影與替代 proxy／候選方案評估／重現及驗證／最小追加實驗與未完成項目）。

## 6. 範圍外／UNKNOWN

- HTTP 路由名稱與 handler（`QuietHandler` 所在的 service 模組）：UNKNOWN，不在本次範圍；僅確認 `office_demo_backend.py` 會呼叫 `target_reconstruction`、`cross_camera_reconstruction`、`query`、`scene`、`timeline`。
- 前端對 `physical_review` 的實際請求端點與 `bootstrap` 欄位：UNKNOWN。
- `blender_physical_source.py`、`blender_physical.py` 的 body policy 數值（nominal body 的 `radius_m`／`height_m`）：UNKNOWN；前端只驗證 `0 < radius <= 2`、`0 < height <= 4`。
- `source_presentation.py`、`service.py`、`app.mjs` 等未列入範圍的檔案：UNKNOWN。
- 實際 Blender 渲染影像、`dataset.json` 內容與 ground_truth 欄位：未開啟。
- 本表所有數值皆來自釘選 commit 的原始碼；沒有重跑 pipeline，也未驗證實際輸出。
