> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# 圓柱底部可見驗證與 perception v2（2026-10-16）

已在 `codex/mvp-backend-integration` 實作獨立版本，並依使用者明確授權完成原 FRONT/REAR、960×540、5 Hz、10 秒、每鏡頭 50 張、合計 100 張 PNG 渲染。只新增驗證資產；沒有儲存原 `.blend`、修改 Office baseline、fixture、原 perception、原 track_ref，或變更 `office_demo_backend.py` 的 31 個觀測斷言。沒有 push、PR 或 merge。

## 結果與範圍

新 run：`blender-contact-control-auditorium-v1`，角色 `FULLY_OBSERVED_CONTROL`。

| 比較範圍 | v1 筆數 | v1 平均／最大誤差 m | v2 筆數 | v2 平均／最大誤差 m |
| --- | ---: | --- | ---: | --- |
| 各版所有有效投影 | 100 | 0.149278 / 0.356445 | 62 | 0.097278 / 0.132631 |
| 完全相同的 62 個 camera/time | 62 | 0.155460 / 0.356445 | 62 | 0.097278 / 0.132631 |

誤差是對規劃 foot position 的三維歐氏距離，按既有核准研究模型尺度 0.0247 m/BU 換算。兩版同一組影格的對照才適合比較精度。這是單一合成驗證 run 的結果，沒有證明真實人員接地精度或正式研究驗收；兩版輸出的仍是可見輪廓的投影 proxy，圓柱可見底緣與中心 foot 也可能存在半徑造成的偏差。±1 px 敏感度不是總誤差界或信賴區間。

底部可見的相鄰影格沒有新版 `SPEED_CAP` 跳點。新版有位置的時刻為 47/50；0.0、0.2、9.8 秒兩台皆未保留位置，原因是合格 incidence 的鏡頭碰到畫面邊緣，另一鏡頭 incidence 太低。沒有內插、外推或用 GT 補觀測。38 個拒絕元件共記錄 LOW_INCIDENCE 35 次、TOUCHES_IMAGE_EDGE 3 次、CONTACT_OCCLUDED 1 次（原因可重疊）；最後一項出現在 0 秒 REAR 的裁切輪廓，是高度模型不一致的保守判定，不能當作已知靜態物件遮擋的證明。

## 選路與來源

`--contact-control` 使用既有 FULLY_OBSERVED_CONTROL 角色，從當前 source 建立 20 BU 網格，再沿用來源 evaluated physical triangles、triangulated WALKABLE、完整連續 marker sweep 與每時刻五點 floor support 檢查。既有快取 hints 不存在，因此本次沒有依賴歷史可見性答案。Office 在此網格沒有候選；不是全域不可行的證明。

- 選中 `WALK_1F_AUDITORIUM`，來源攝影機 pose/lens 不變。
- 0 秒起點 BU `(1780, 1660, 20.12885093688965)`；10 秒設定終點 `(1780, 2240, 20.12885093688965)`。
- 對應公尺起訖 `(43.966, 41.002, 0.4971826181411743)` → `(43.966, 55.328, 0.4971826181411743)`。
- 實際最後採樣為 9.8 秒，終點不包含在 `[0,10)` 的 50 幀內。
- 原中段 probe 55 BU，新增底部 probe 為 foot +0.5 BU。每個時刻至少一台同時通過中段可見、底部可見與 incidence ≥0.25；15 個時刻兩台同時通過。兩台的底部 probe 皆可見，但部分 incidence 不合格。
- 原 make_target：半徑 6 BU、高度 119 BU（身體加頭部），沒有修改來源或目標形狀。這是合成設定，不是人體模型。
- `.blend` SHA-256：`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`；renderer 前後 hash、大小及 mtime 完全相同。
- dataset SHA-256：`d70159cfe7fc5b9762b57d9b988b1af0f1fd78b6c5a774ca778b29f23f88f1d4`。
- safe inputs SHA-256：`c99f19bc7f79796dbd6baa8a24940ab5b2e80ec9d53d810c9b6969e1d24c310f`。

新 bundle 沿用獨立核准的 floor/scale 證據與來源 calibration，只有 camera/time/RGB locator/hash 進入 safe inputs。來源模型展示仍是 PARTIAL，不增補 walkability、碰撞或身分 authority。原 renderer 路線與可見性只留在 plan／評估區。source/scale、producer、calibration、floor、dataset、config 與逐張 RGB hash 綁定見 [機器收據](CONTACT_CONTROL_VALIDATION_20261016.json) 與本機 predictions。

## 新版本與舊結果

`perception_v2.py` 使用相同 temporal median、RGB max-channel difference >30、最少 28 px，但元件改為 8-連通；接點取遮罩最低列 x 中位數。接點、可見頂點、已配置高度／半徑與合法 calibration/floor 做一致性檢查；高度殘差超出容差時設 MISSING / CONTACT_OCCLUDED。這是合成目標假設下的拒絕 heuristic，單一 RGB 不能保證已辨識所有靜態遮擋物。

已配置高度 2.9393 m、半徑 0.1482 m 來自事先宣告的 119/6 BU 目標設定，不讀渲染 GT。畫面邊緣、incidence <0.25、寬度不相容或投影失敗均不輸出地板位置。寬度檢查包含透視造成的直立目標傾斜。8-連通會合併對角相接的不同物體；寬度檢查能拒絕部分合併，不能保證分開重疊目標，identity 保持 UNKNOWN。

有效點標為 OBSERVED / PROJECTED_OBSERVATION；拒絕點為 MISSING 且位置 null；identity/無法確認的遮擋保留 UNKNOWN。可選的高度反推位置、顏色篩選與 INFERRED 位置未啟用。每點保存四軸與四對角 ±1 px 的公尺位移敏感度；沒有沿用舊版的經驗 uncertainty 分數。

v2 的獨立執行入口是 `scripts/run_contact_validation.py predict`，不覆寫 canonical index／API／原 track。新 run 仍可由既有 `load_blender_scene` 載入，但必須明確傳入 `ValidationRunPin`；預設 loader 仍只接受原三個 baseline pins。新 pin 不可冒用 baseline run_id；測試包含錯 pin 拒絕。

## Office 回歸

原 index snapshot 前後相同，原投影總數仍為 31；新版為 30 個 8-連通元件，全部因低 incidence 拒絕輸出地板位置。這是防止無根據投影的保守結果，沒有把全拒絕稱為精度改善。

| 時刻 | 舊結果 | 新結果 |
| --- | --- | --- |
| 0.4→0.6 s | 8.513936 m/s，超過 8 m/s | MISSING，LOW_INCIDENCE；部分另有 AMBIGUOUS_MERGE |
| 1.8→2.0 s | 10.031685 m/s，超過 8 m/s | MISSING，LOW_INCIDENCE；部分另有 AMBIGUOUS_MERGE |
| 4.4 s FRONT | 兩個元件，地板交點相距約 4.395 m | 一個 8-連通元件，MISSING；LOW_INCIDENCE / AMBIGUOUS_MERGE / CONTACT_OCCLUDED |

## 本機產物與重現

所有以下 locator 相對於 canonical Amidst 資產 checkout；raw RGB、GT、dataset 與帶有本機 locator 的 safe bundle 留在本機，不作為待發布程式文件。

| 產物 | 相對路徑 |
| --- | --- |
| 新 dataset、100 張 PNG、plan、獨立 ground_truth | `data/pilot/contact_control_20261016_v1/auditorium/` |
| safe inputs、manifest、validation pin | `data/engineering/contact_control_20261016_v1/auditorium/` |
| 新 run 兩版完整像素／位置／拒絕狀態 | 同上 `predictions.json`，及上一層 `auditorium-comparison.csv` |
| 每台每幀中段／底部可見與 incidence 表 | 同上 `visibility.csv` |
| 逐幀誤差、均值、最大值、SPEED_CAP 檢查 | 同上 `evaluation.json`、`errors.csv` |
| Office 100 camera/time 的新舊對照 | 上一層 `office-regression.json`、`office-comparison.csv` |
| 完整 hash 與來源收據 | 上一層 `receipt.json` |

在指定 backend checkout、既有 uv 環境執行。`CANONICAL` 指向持有 immutable `.blend` 和新產物的既有資產 checkout；`TEMPLATE` 指向既有 Auditorium baseline bundle。每次重現使用新目的地與 run_id，不覆寫本次輸出。重新渲染須再次取得對應範圍授權。

```sh
blender --background "$CANONICAL/blender/school_v3.blend" \
  --python scripts/plan_blender_pilot_sites.py -- \
  --contact-control --min-incidence 0.25 --bottom-probe-height 0.5 \
  --site office --site auditorium --output-root "$NEW_PLAN_ROOT"

# 只在獲得該次渲染授權後執行；本次已完成 100 張。
blender --background "$CANONICAL/blender/school_v3.blend" \
  --python scripts/export_blender_pilot.py -- \
  --plan "$PLAN" --output "$NEW_RENDER_ROOT" --width 960 --height 540 --limit 50

PYTHONPATH=src uv run --offline --no-project --python "$EXISTING_PYTHON" \
  scripts/materialize_contact_control.py --template "$TEMPLATE" \
  --dataset "$NEW_RENDER_ROOT/dataset.json" --output "$NEW_BUNDLE" \
  --run-id "$NEW_RUN_ID"

PYTHONPATH=src uv run --offline --no-project --python "$EXISTING_PYTHON" \
  scripts/run_contact_validation.py predict --safe-inputs "$NEW_BUNDLE/safe_inputs.json" \
  --config configs/office_contact_v2.json --output "$PREDICTIONS"

# 另一個程序只在 predictions 寫出後讀 GT，不能回流調整本次結果。
PYTHONPATH=src uv run --offline --no-project --python "$EXISTING_PYTHON" \
  scripts/run_contact_validation.py evaluate --predictions "$PREDICTIONS" \
  --dataset "$NEW_RENDER_ROOT/dataset.json" --plan "$PLAN" --output "$EVALUATION"
```

## 驗證

只執行相關測試：`tests/engineering/test_perception_v2.py`、`tests/engineering/test_perception.py`、`tests/workbench/test_blender_scene.py`、`tests/unit/test_blender_pilot_sites.py`、`tests/unit/test_contact_control.py`，以及 `git diff --check`。未跑完整測試套件。合成遮罩測試涵蓋完整／底部截斷、邊緣、4/8 連通與合併風險、公尺敏感度；另驗證 GT 污染不影響 v2、損毀 RGB 拒絕、獨立 pin 與 paired 評估。

現有 backend loader 載入通過；100 張 raw／served hash 驗證通過。抽查兩鏡頭首尾 PNG 可見底部，首尾部分鏡頭輪廓被畫面裁切，保留上述拒絕。未新增影片、前端或跨鏡頭身分合併；未變更正式研究與 frozen 結果。
