# CX-L1 偵測診斷（#552，2026-11-17）

這份是修正前的診斷，不是驗收通過紀錄。基準程式為 `main@31a69177`，人物、場景、相機保持 N6 原始素材；沒有修改 Blender、場景燈光或相機擺位。模型為既有本機 RT-DETR R18；沒有外部模型呼叫或 API key 讀取。GT 只在錄製／評分／診斷圖使用，不傳入偵測器。

## 固定樣本與觀察

歷史評分輸入：`local/evidence/live-mode-n6-20261115/glb_n6scene_320x180_r1.rows.json`。合格條件保持原 sweep：射線可見、投影框在畫面內比例（四捨五入到兩位）≥0.6、框高（四捨五入到一位）≥16 px；命中為 IoU≥0.3。共 1,328 個合格樣本。門檻比較是同批既有偵測，不是重新推論。

| 鏡頭 | n | ≥0.35 命中率 | ≥0.05 命中率 | 框高範圍 px | 框內亮度中位數 /255 | ≥0.05 誤檢/影格 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CAM_ENTRY | 236 | 19.1% | 72.5% | 31.6–117.2 | 119.8 | 0.636 |
| CAM_R101_IN | 68 | 47.1% | 98.5% | 58.5–117.7 | 137.2 | 0.676 |
| CAM_EXT_CAR | 300 | 67.3% | 97.0% | 27.8–98.1 | 147.3 | 0.283 |

亮度為新錄製 RGB 的投影框內像素 `0.2126R+0.7152G+0.0722B` 中位數，再對樣本取中位數，包含背景，不能當人體照度。圖中分數來自歷史 sweep，相機／位置／朝向逐筆對應；新錄製會另行推論，不能以歷史分數冒稱新 RGB 的結果。

![三台鏡頭的代表影格](live_detection_20261117/diagnosis_frames.jpg)

圖欄依序為低分／門檻造成的漏檢／原門檻可見；`lowest scored` 表示沒有分數低於 0.05 的對應樣本。黃色是評分用投影框，不是偵測框。逐張索引、位置、朝向、分數、亮度在 `live_detection_20261117/diagnosis_frame_stats.json`。

## 原因分解

- **門檻：已量出主要損失。** CAM_ENTRY 同一偵測結果從 0.35 放寬到 0.05 增加 53.4 個百分點；R101_IN +51.5、EXT_CAR +29.7。但誤檢由三台均為 0 增加到表中數字，不能只報召回率。
- **人物大小：不是三台共同主因。** R101_IN 全部框高≥58 px 仍漏掉過半。EXT_CAR 高16–32 px 的40個樣本在0.35命中95%，高80–180 px的32個樣本僅15.6%；CAM_ENTRY 高32–48 px的124個樣本命中9.7%，高48–80 px的60個樣本40.0%。距離／角度／背景混雜，未證明尺寸本身造成差異。
- **太暗／逆光：尚無獨立因果證據。** 三台投影框亮度中位數不低，樣本圖也有明亮背景下的低分。烘焙背景、人物姿態與朝向可能影響模型；亮度1.5倍的固定RGB對照才能進一步判定。不能以框亮度證明沒有局部陰影或逆光。
- **遮擋：部分可見性仍 UNKNOWN。** 歷史 sweep 的射線可見不等於人體每個部位都可見，投影框也不是人體遮罩。圖中 R101_IN 在門框附近，EXT_CAR 有車體與牆邊；尚未量化像素級遮擋比例，不能宣稱已隔離其效應。
- **解析度／形變：待固定RGB比較。** 來源320×180目前直接拉伸到640×640，改來源640×360仍會拉伸；正在比較原輸入、保長寬比letterbox與較高來源解析度。先前延遲報告已說明模型forward尺寸固定，提高來源解析度不代表提高模型尺寸。

## 重現與 LOCAL

腳本 `scripts/live_mode/record_detection_bench.mjs` 從不變的 N6 素材錄製同一格點／朝向，RGB 單獨保存，標籤寫入 `evaluation_labels.json`。`scripts/live_mode/detection_bench.py` 僅讀 RGB 做推論，全部完成後才開標籤計分。`scripts/live_mode/detection_diagnosis.py` 產生以上精簡診斷圖與亮度代理量。

輸出用 `$AMIDST_ARTIFACTS/cx552-20261117/`；本次為獨立 clone 的 `local/evidence/cx552-20261117/`。原始 RGB 不提交 GitHub。完整 SHA、檔數與大小在後續驗收紀錄補齊；尚未完成的項目為 UNKNOWN。

```bash
# SHARED_LOCAL 指向現有唯讀的 local；使用現有 Python / Node 依賴。
PYTHONPATH=src:$SHARED_LOCAL/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps uv run --no-project --python "$PYTHON" python -m amidst.live_mode.server --port 8797 --device mps --models "$SHARED_LOCAL/data/demo-owned-v1/models/rtdetr" --assets "$SHARED_LOCAL/data/live-assets-20261115" --cameras "$SHARED_LOCAL/data/r004-build-v2-20261021/safe_static/cameras.json"
LIVE_BASE=http://127.0.0.1:8797 node scripts/live_mode/record_detection_bench.mjs "$AMIDST_ARTIFACTS/cx552-20261117/recording"
PYTHONPATH=src:$SHARED_LOCAL/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps uv run --no-project --python "$PYTHON" python scripts/live_mode/detection_bench.py --recording "$AMIDST_ARTIFACTS/cx552-20261117/recording" --out "$AMIDST_ARTIFACTS/cx552-20261117/diagnosis" --models "$SHARED_LOCAL/data/demo-owned-v1/models/rtdetr" --variant stretch
```

同批新錄製比較、逐台前後對照、延遲、gate4_off 重播及指定 tests/live_mode 尚未完成；這些不以本診斷替代。
