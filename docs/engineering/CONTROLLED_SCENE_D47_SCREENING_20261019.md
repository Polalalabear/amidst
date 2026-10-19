# D47 模型先篩：2026-10-19 實際產出

## 實際產出 / Actual output
- Model / effort: Codex；精確 model／effort UNKNOWN。RGB producer 是下列 deterministic 元件模型，不是 LLM／語意 person detector。
- PR / commits: 新本機分支 `codex/controlled-scene-d47-screening`，base `812817f29c74b8589f6cdf613966eba5d936755f`；設定在讀 RGB 前 commit `a830873`、`e3a0776`，工具 `c83b0d8f4a54f2afa057ac9459fcd2fd11b34ab2`。本輪未 push／開 PR；未改 #54、整合分支或 main，無 merge／rebase／force-push。
- Files changed: `configs/controlled_scene_d47_detector_v1.json`；`scripts/acceptance/screen_controlled_scene_d47.py`；`scripts/acceptance/test_screen_controlled_scene_d47.py`；`scripts/acceptance/verify_controlled_scene_d47.py`；本文件。LOCAL ignored 產物只有兩份 `acceptance/d47_screening.json`；原 RGB、rgb_index、safe_bundle、seed、Blender 資產未改。
- Commands run and results: 下列 8 項 focused tests 通過；獨立驗證 **550/550** 格完整 schema、grid、逐檔 RGB SHA、索引 SHA、固定 seed 抽樣、review 原因計數；`git diff --check` 通過。全部依賴重用既有 bundled NumPy 2.3.5／Pillow 12.3.0，未安裝、未建 venv。
- Artifacts: 兩份 LOCAL 輸出與 SHA 見下；設定 SHA `3b83a74d236753a9596f56266f80a2585f06d1e5201474c49179c16d17336bff`；seed 檔 SHA `584c458b788348f8e7b6f47f69888e2420f5f01590e1d923001d5c94a0a2a3d0`，維持渲染前版本。
- Verified: 所有 550 格都有要求欄位，右／下 exclusive bbox；兩個獨立 run、source/run/clock/grid/hash 綁定；acceptance 在 safe_bundle 外並 ignored；偵測函式只收 RGB，投影於偵測後獨立比較、不選元件或回填 bbox；抽樣每鏡頭 ceil(10% 剩餘集合) 可重算。正式服務／loader 未改、未接此檔。
- Not verified: **未做人工 RGB 驗收、未確認人物數或接地、未確認全盲、未凍結、未讀 GT／mask／depth、未渲染、未接外部模型 API。**未驗證新場景的正式 runtime readiness。投影使用已 pin 設計校正參數；正式 safe 校正匯出尚未物化，未宣稱已驗證匯出校正。沒有把模型旗標當失敗或通過。
- Deviations, UNKNOWN items and follow-ups: 下列規則差異／限制未自行放寬；模型和人工不一致以人工為準，原模型值保留。本輪只交人工佇列，不結案 CS-B。`frames`／`records` 差異另在 #65 v1.1 提出，不修改本輪索引。

### 執行指令

```sh
UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline --python /Users/polalabear/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 python scripts/acceptance/test_screen_controlled_scene_d47.py
UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline --python /Users/polalabear/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 python scripts/acceptance/screen_controlled_scene_d47.py --root /Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1
UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline --python /Users/polalabear/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 python scripts/acceptance/verify_controlled_scene_d47.py
git diff --check
```

工具只接受這兩個已 pin 的 run；hash/source/clock/grid 錯誤停止，不降格 MISSING，不覆寫既有結果。重跑會拒絕覆寫。驗證器唯讀，不再跑偵測。8 項 focused tests 用 synthetic pixels 測 4 連通／bbox、橋接 union、純 RGB 偵測、嚴格閾值、雜湊抽樣、A4／D27、hash fail-closed，以及設計投影／P2 起點。

### D47 專用設定和舊常數的差異

名稱 `csb-screen-rgb-temporal-components`，版本 `csb-screen-v1`，設定 `configs/controlled_scene_d47_detector_v1.json`。設定在本輪讀 RGB 前固定；看過結果後沒有調參或放寬門檻。

| 項目 | 舊 perception.py（C8） | D47 專用版 |
| --- | --- | --- |
| 每 run／camera 背景 | 全影格 temporal median | 相同 RGB 原理，30-row tile 計算，控制 median 記憶體峰值 |
| RGB 最大通道差 | >30 | >24，較保守保留弱差分；獨立設定 |
| 4-connected 元件面積 | ≥28 px | ≥64 px；限制微小噪點，不是「人物像素」最低數 |
| merged／歧義 | 寬 >32px 或高 <20px | 寬／高 >0.8 標歧義；多元件另標，不靠絕對寬32px判定；可能漏合併，不能確認人數 |
| 追蹤 | dt≤.61s，位移≤28px／.2s | 停用；不產生 local identity，不用投影或 actor ID 配對 |
| bbox 高／邊距 | 沒有 D47 政策 | 高<112px、任一邊距<16px、觸邊均標；partial 也保守標 |
| score | 沒有這個輸出 score | 元件 area／bbox area 的填充比，**不是語意信心或機率**；`score_kind` 明示 |

這仍是 class-agnostic 差分元件；陰影、碎裂、合併及 median 吃掉停留者都可能發生。`MULTIPLE_COMPONENTS_POSSIBLE_PEOPLE`／`B1_POSSIBLE_TWO_PEOPLE` 是送人工的疑點，不能描述為已量到兩人。沒有以 bbox 底邊推腳，沒有偷偷接 C4a。

### 人工佇列（原因可重疊，不能相加當總數）

| run | 全部格 | review_required 聯集 | FLAGGED | D27_TARGET | BLIND_BOUNDARY | SWITCH_BOUNDARY | RANDOM_SAMPLE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ctrl-lcorr-s1-a-5fps-v1-r001 | 150 | **95** | 79 | 22 | 0 | 62 | 8 |
| ctrl-lcorr-s1-b1-5fps-v1-r001 | 400 | **212** | 158 | 0 | 16 | 139 | 23 |

總計 **307/550** 格需要人工；其餘243格維持 `MODEL_SCREENED_NOT_HUMAN_REVIEWED`，**全部550格目前都還沒有人工作結論**。`review_required=false` 不等於人工通過。

| run／camera | review_required／全部 | 抽樣候選數 | RANDOM_SAMPLE index |
| --- | --- | --- | --- |
| A / CAM_W1 | 41/50 | 11 | 13, 46 |
| A / CAM_W2 | 49/50 | 2 | 6 |
| A / CAM_R102_CTRL | 5/50 | 50 | 5, 6, 11, 33, 43 |
| B1 / CAM_W1 | 75/100 | 28 | 29, 96, 97 |
| B1 / CAM_W2 | 86/100 | 16 | 82, 96 |
| B1 / CAM_N1 | 37/100 | 71 | 29, 31, 41, 45, 54, 56, 60, 67 |
| B1 / CAM_R102_CTRL | 14/100 | 96 | 8, 33, 43, 63, 77, 82, 87, 97, 98, 99 |

### Flags 分布（每格每旗標計一次；不等於人數或確定錯誤）

| flag | A | B1 |
| --- | --- | --- |
| A_ALL_CAMERAS_NO_COMPONENT | 0 | 0 |
| B1_POSSIBLE_TWO_PEOPLE | 0 | 90 |
| COMPONENT_IN_DESIGN_BLIND_WINDOW | 0 | 26 |
| D27_TARGET_PERSON_MISSING | 0 | 0 |
| EXPECTED_PERSON_MISSING | 2 | 5 |
| FRAME_EDGE_TOUCH | 12 | 12 |
| HEIGHT_BELOW_112_PX | 58 | 118 |
| MARGIN_BELOW_16_PX | 13 | 13 |
| MERGED_OR_AMBIGUOUS | 37 | 70 |
| MULTIPLE_COMPONENTS_POSSIBLE_PEOPLE | 46 | 90 |
| PARTIAL_EXPECTED | 22 | 32 |
| PROJECTION_CENTER_MISMATCH | 4 | 5 |
| PROJECTION_COMPARISON_AMBIGUOUS | 46 | 90 |
| PROJECTION_HEIGHT_MISMATCH | 23 | 42 |
| PROJECTION_INCONSISTENT | 25 | 47 |
| PROJECTION_MULTIPLE_EXPECTED_UNKNOWN_MATCH | 0 | 0 |
| PROJECTION_PRESENCE_MISMATCH | 2 | 5 |

期望有人但沒元件：A W1 i43、44；B1 W1 i43、44、85，W2 i50，N1 i69。這是模型／設計投影不一致清單，未人工確認漏人。D27 無元件格為0；A 沒有「三鏡頭同格全無元件」，不能反推全程人物可辨。

### 產物與耗時

- LOCAL `/Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-a-5fps-v1-r001/acceptance/d47_screening.json`；SHA-256 **`4cb59e57c3e3311222e595a19c7600404fc50f528c434cb70af23611f935f494`**；216,417 bytes；150 筆。
- LOCAL `/Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-b1-5fps-v1-r001/acceptance/d47_screening.json`；SHA-256 **`972dc2df64bdf05037eeaeb698559aa24021b8cb1c9fe96f60a01dc7e8305052`**；508,767 bytes；400 筆。

兩檔合計 725,184 bytes（約 0.692 MiB），不在 safe_bundle。偵測計時含 median／差分／元件，不含 RGB 讀檔／投影／輸出：A **3.060s**、B1 **7.838s**，合計 **10.898s**。兩 run 內部處理階段計時分別 5.050s／11.570s（不含其後重核 hash 與寫檔）；不冒稱整個開發耗時。開始時 df available 20,577,832 KiB≈19.625GiB；完成期間讀到20,579,436KiB，未觸8GiB停止線。

### 比較／抽樣的明確定義及尚有問題的規則

1. **A2**：產製設計 route＋名義 H1.70m／r.25m、已 pin 的理想相機與不透明 AABB 聯集；32方位×9高度＋頭腳中心=290 probes。僅為 **設計估計，不是覆蓋證據**；有限探針／真實人形／光照誤差 UNKNOWN。存在性由名義探針是否入框且未被設計遮擋判定；比較框是完整圓柱投影，未依 RGB 裁切或挑元件，partial 因而容易標記。多元件不硬配對，標 `PROJECTION_COMPARISON_AMBIGUOUS`。投影不進正式推論。
2. **中心偏移文字差異**：#76 A2 原提案寫「水平偏差」，D54 決策摘要／本次指示寫「中心偏移」。本次保守用 xy 歐氏距離，0.25倍投影高不變，設定／收據明列；未悄悄採用較寬鬆的水平-only，也未宣稱兩種定義相同。
3. **尺寸／邊距 scope 差異**：#76 選項表把112／16集中於D27，後續D54摘要與本次指示列為任一條件。本次按後者全格保守標，partial另標 `PARTIAL_EXPECTED`，不是強迫所有 partial 達成D27。人工可接受partial而不改模型輸出。
4. **盲窗／P2**：A4使用已核准包絡窗 i51–67，半開 [10.2,13.6)s；四台各 i49、50、68、69，共16筆。這是先進場者的設計盲窗，但P2在i55進場；依A1「任一鏡頭有元件就標」會包含P2，共26格。沒有用actor ID扣掉P2或要求偵測器辨識身份；需人工解釋，不能直接宣布盲窗失敗。
5. **any-pixel 限制**：RGB 差分＋64px面積門檻不能證明「任何人物像素都沒有」。噪點、靜止人物、碎裂、陰影都可能誤判；26是元件旗標數，不是26格確定看到先進場者。沒有以模型無元件取代人工全盲證據，沒有把64px門檻偷改為盲窗的可見性標準。
6. **A3**：嚴格使用渲染前 commit `812817f` 的 compact JSON array 雜湊序列化（不是#76早期提案的pipe串接），seed不變。抽樣候選排除FLAGGED、D27及A4，per run/camera取ceil10%。輸出記候選集合hash、候選數與選中index。
7. **切換處**：首次component count或ambiguity state改變的sample為k，列k−1、k、k＋1（grid內）。不把bbox每個像素變動當切換；也不推定身份。這個約定已在讀RGB前寫進設定。
8. **新增欄位**：保留要求的所有欄位名與`schema_version: d47_screening_v1`；另加 detection的`component_area_px`、detector的`score_kind`、projection的`expected_count/full_body_expected/basis/model_error`、逐格`projection_comparison`（可比較時）／`human_review_status`，頂層`acceptance_only/not_for_runtime_or_safe_bundle/formal_acceptance/gt_read/projection_provenance/producer/summary`，sampling下`receipts`。均為CS-B輔助／稽核資料；前端可忽略新增欄位，不能當正式API輸入。

**D47 篩選完成，待人工審查；不凍結、不讀 GT、不合併，不宣告 CS-B 通過。**
