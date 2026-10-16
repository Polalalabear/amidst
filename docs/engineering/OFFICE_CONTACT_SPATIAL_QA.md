# Office RGB 接地診斷 PoC（2026-10-16）

Application baseline：PR #7 `78b99e623f72f0e9f8df24ec54ce57815c1a9cf5`，包含 [Task B / PR #4](https://github.com/Polalalabear/amidst/pull/4)、[Task C / PR #6](https://github.com/Polalalabear/amidst/pull/6) 與 [PR #7](https://github.com/Polalalabear/amidst/pull/7)。本次沒有修改 perception、frame baseline、API、frontend、camera calibration、原 `.blend`、GT 或 frozen 結果。

## 結論與實作範圍

真實接地精度改善為 **UNKNOWN**。交付 `scripts/diagnose_office_contact.py` 的獨立診斷 PoC，保留 raw observations、來源 frame/image hash、calibration/floor/producer/baseline hash，另列 8-connected bbox proxy、最低可見 mask 像素中位數 proxy 及 ±1 px 投影敏感度。所有 proxy 都不是已驗證腳點；`proposed_person_world_position=null`、`position_use=WITHHOLD_AS_PERSON_GROUND_POSITION`、`canonical_replacement=false`。此閘門只在 PoC 報告生效，**尚未整合或變更 Workbench 的 canonical 位置輸出**；不能宣稱綠球的空間精度已修正。

完整數值與逐筆 provenance：[機器可讀收據](OFFICE_CONTACT_QA_20261016.json)。收據僅含安全輸入衍生欄位，沒有本機 locator、session token、RGB、GT 或原始資產副本。`accuracy_improvement=UNKNOWN`；沒有用 reprojection self-consistency 當作獨立精度驗證。

## 已核對的資料流

1. `engineering/perception.py::produce_perception` 核對 RGB SHA-256，以每鏡頭 50 張影格的 temporal median 作背景，max-channel difference `>30`，4-connected BFS，少於 28 px 的元件捨棄。
2. 元件 bbox 的 `(xmin+xmax-1)/2, ymax-1` 成為 `contact_pixel`；不是 mask 最低列的實際像素，也不是已量測腳點。`DETECTED` / `MERGED_OR_PARTIAL` 只用 width >32 或 height <20 分類；0.25/0.6 為 heuristic，不是公尺誤差或機率。
3. 以 contact pixel 距離及時間差建立 local pixel track，0.2 秒時容許 28 px。這能保留同一 local track，但不保證同一人或真實空間連續性。
4. `workbench/frame_baseline.py::_project` 經 `geometry/inverse_projection.py::InverseProjectionService`，用原 camera 校正及 approved source-bound floor plane 求射線交點。`projection_quality` 是 incidence，不是準確率。
5. `blender_motion` 由原投影形成曲線，超過 SPEED_CAP 時斷線；association/physical candidates 保留原投影與缺口，API 將 scoped 結果供 Workbench 使用。
6. PR #7 `cross-camera.mjs` 的統一 cursor、精確 frame_ref 綁定 bbox，以及 `scene.mjs` 的 candidate/path/camera captions 保留；診斷 PoC 不接入此管線。

來源 RGB 裁圖顯示 0.4/0.6、1.8/2.0 秒的橙色替代目標下部受座椅遮住；4.4 秒只剩狹窄可見輪廓。這是可見影像診斷，不將 display-only Auditorium 升為遮擋、碰撞或通行 authority。

## 指定時間點的原投影與替代 proxy

以下 XYZ 單位 m，三位小數僅供閱讀；完整 double precision、camera、frame、observation、track 與 image hashes 見 JSON。替代列使用各原元件最低可見列的 x 中位數，仍沿用相同 y、原校正及 floor。它有可見 mask 支持，但沒有真實接地證據。

| 時間 s / camera | 原始 XYZ | mask-bottom median 替代 XYZ（未採用） | 原量測狀態 | 人員接地位置 |
| --- | --- | --- | --- | --- |
| 0.4 FRONT | (34.285,48.184,0.496) | (34.589,47.971,0.496) | MERGED_OR_PARTIAL | UNKNOWN |
| 0.6 FRONT | (32.783,47.383,0.496) | (33.112,47.151,0.496) | DETECTED | UNKNOWN |
| 1.8 FRONT | (31.911,47.432,0.496) | (32.016,47.359,0.496) | MERGED_OR_PARTIAL | UNKNOWN |
| 2.0 FRONT | (33.608,48.503,0.496) | (33.755,48.400,0.496) | MERGED_OR_PARTIAL | UNKNOWN |
| 2.2 FRONT | (34.260,48.952,0.496) | (34.442,48.825,0.496) | MERGED_OR_PARTIAL | UNKNOWN |
| 4.4 FRONT 元件 1 | (34.580,49.563,0.496) | (34.628,49.529,0.496) | DETECTED | UNKNOWN |
| 4.4 FRONT 元件 2 | (30.556,47.794,0.496) | (30.795,47.627,0.496) | DETECTED | UNKNOWN |
| 5.0 雙鏡頭 | 無量測 | 無位置 | NO_MEASUREMENT | MISSING |
| 8.6 REAR | (31.544,53.649,0.496) | (31.699,53.756,0.496) | DETECTED | UNKNOWN |

相反鏡頭在這些 anchor 沒有量測時，JSON 同樣保留空陣列，沒有補值。

| 配對 | 原始跳距 / 表觀速度 | mask-bottom median 跳距（未採用） |
| --- | --- | --- |
| 0.4→0.6 s | 1.702787 m / 8.513936 m/s | 1.688745 m |
| 1.8→2.0 s | 2.006337 m / 10.031685 m/s | 2.027100 m |
| 2.0→2.2 s | 0.792095 m / 3.960475 m/s | 0.807637 m |

0.4→0.6 的 bbox bottom y 從 135→124，1.8→2.0 從 121→134。兩組仍為相同 local pixel track；影像位移通過 association threshold，floor projection 將 y 的變化放大，SPEED_CAP 之後才斷線。這不是已確認的人體瞬間移動。

4.4 秒兩個 4-connected 元件的地板交點相距 **4.395073 m**。保持同一 `>30` mask、只加 diagonal adjacency 的 8-connected PoC 得到一個輪廓，bbox proxy 為 **(34.376098,49.706557,0.495948)**；`>=30` 的 4-connected threshold 對照也變成一個元件。這支持拓樸／threshold 敏感性，不能證明新 proxy 是腳點。PoC 沒有合併原 observations、重建 local tracks 或改寫 fixture 選取的 observation_ref。

指定有量測的元件，bbox 中心到最低列最近 mask pixel 的水平距離為 **2.5–13.5 px**；四方向 ±1 px 的最大地板投影變化約 **0.123–0.241 m**。兩者都是幾何／像素診斷，沒有被包裝成信賴區間或人體位置誤差界。

## 候選方案評估

| 方法 | 必要資料及預期改善 | 本次證據 | 失敗情形／GT 需求 | 資料契約及決定 |
| --- | --- | --- | --- | --- |
| Occlusion-aware gating | RGB、可見接觸證據與遮擋狀態；阻止不支持的腳點主張 | 實際座椅遮住下部；DETECTED 仍可能遮擋 | 單一 RGB 無法認證隱藏接地點；不能由 incidence 推定遮擋。無 GT 需求 | PoC 明示 UNKNOWN 並不輸出人員接地位置；canonical 未變 |
| Mask／components | 同一安全 RGB、背景差分；修復 4.4 分裂並將取點放回可見 mask | 8C 或 >=30 都使 2→1；最低列實際 x 與 bbox center 不同 | 8C 也可能合併不同目標；threshold 可能引入背景；最低像素仍不是腳。無 GT 需求 | 另列替代 proxy，不改原 observations／refs／tracks |
| Camera-specific image-ground geometry | 既有校正與 approved plane；量化投影敏感度 | 低 incidence 放大 y 的變化，±1 px 達 0.12–0.24 m | 自我回投影誤差接近零仍無法驗證隱藏腳點；不可為對齊畫面修改校正 | 原校正／floor 不變；診斷附加敏感度，無 GT |
| Multi-frame constraints | 已支持的同鏡頭時間關係與明確速度／人體假設；可能降低跳點 | 像素 track 可跨過兩個大跳，現有 SPEED_CAP 已保留斷線 | Smoothing 可把錯誤變平順；未知身分或長缺口不能接線。需獨立驗證，不能用 GT 調參 | 未新增 temporal inference 或 identity link；整合前需核准科學假設 |
| Uncertainty／feasible regions | 有根據的像素／高度／遮擋 bounds，才可建立區域 | 只有數值敏感度，沒有隱藏腳點 bounds | ±1 px 不是遮擋量或誤差分布；不能據此認證 feasible region。無推論 GT | 輸出 UNKNOWN；沒有虛構區域或概率 |
| Existing scene geometry | purpose/authority 核准的 source-bound 支撐／遮擋幾何 | floor 可作射線平面；Auditorium companion 為 PARTIAL display context | 顯示座椅不等於 certified collider，不能據此硬推接地或導航；缺全身假設 | 只沿用原 approved floor；未將 display geometry 接入推論 |

## 重現及驗證

使用既有環境，從 checkout root 執行；環境變數應指向既有依賴，不建立新環境：

```sh
export OFFICE_EVIDENCE_REPO="$(cd ../amidst/.local-worktrees/phase1-finalization && pwd -P)"
PYTHONPATH=src uv run --offline --no-project --python "$OFFICE_EVIDENCE_REPO/.venv/bin/python" \
  python scripts/diagnose_office_contact.py \
  --safe-inputs "$OFFICE_EVIDENCE_REPO/data/engineering/local_run/blender_camera_v1/office/safe_inputs.json" \
  --output /private/tmp/office-contact-qa-new.json
```

Output 採 exclusive create，若檔案存在便拒絕覆寫。safe inputs SHA-256 為 `1ea62def6c843b3bae1c5e25584fa489915f08e678b28b6220dc88cc17b43163`；程式自身 hash 存於 JSON。輸入污染測試證明額外 GT/trajectory 欄位不改變報告；hash 不符的 RGB 拒絕處理；空 mask 不補位置；對角元件不跨空白合併；診斷前後 canonical index snapshot 完全相同。

實際瀏覽器逐點測試 0.4、0.6、1.8、2.0、2.2、4.4、5.0、8.6 s：來源影格時鐘與圖框同步，4.4 保留兩個原觀測，5.0 無當前圖框或 cursor，8.6 REAR 重啟。3D 的整段靜態候選線／sample dots 及 path labels 保留，不能把這些歷史資料當作當前 cursor。候選 1/2/3/未關聯基線切換成功；16 椅與講台保持。沒有整合 PoC，所以這是既有視覺行為回歸驗證。

## 最小追加實驗與未完成項目

要比較真實 3D 精度，至少需要不供調參的獨立接地參考。可另行授權在獨立設定中，對 0.4/0.6/1.8/2.0 s 產出少量同步、腳點可見且校正已知的驗證視角，保留原 `.blend`／GT／原影格不變；人工只標可見腳點，其餘 UNKNOWN。這些新影像及三角化參考只用於 held-out evaluation，不進入原方法或候選排名。沒有此獨立證據前，不將 mask 中位數、8C 或 smoothing 整合成 canonical 人員位置。

PHASE_2: PARTIAL。已完成診斷、候選比較、受限 PoC、數值與視覺回歸；真實人員接地精度仍 UNKNOWN。完整 8 分鐘 Demo 不能以 HTTP soak 或 9.8 秒來源 flipbook 自動視為驗收通過；還原影片尚未物化，本任務沒有生成影片。
