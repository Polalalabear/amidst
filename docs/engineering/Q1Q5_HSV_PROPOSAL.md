# Q1–Q5 上半身 HSV 參數提案

狀態：**PROPOSED，G6 未核定**。Refs #114、#113/PR #155、#144/PR #148。只用新 r004 calibration preview RGB 及模型人物框；沒有讀事件腳本、actor/material ID、GT、A／B1白色人形。沒有出題、填標準答案或 T/F。這份設定不能當成核准的 parameter-set，正式索引仍須等待 Claude 獨立檢查及使用者核定。

## 明確候選設定

完整機器格式在 `configs/q1q5/hsv_color_v1.json` 的 `hsv_config`，可在核定後原樣放入 `hsv_config` parameter；外層 proposal 不是 parameter-set。版本 `upper-hsv-r004-v1-PROPOSED`，設定 canonical SHA-256 `c35606ee7bc2770bb52645a1a63635fbdf26c1d56d748c9fdea271c5c11a12a6`。任何值更動都須產新版本與 hash，不回填舊索引。

| 項目 | PROPOSED 值 | 單位／定義 |
|---|---:|---|
| crop_ratio | 0.50 | 偵測框上半部高度占比；不從 renderer 取軀幹位置 |
| min_pixels | 64 | 裁切面積及通過 S/V 的有效像素都須達標 |
| truncation_max_ratio | 0.20 | 上半身框超出影像而被裁掉的面積占比上限 |
| saturation_min | 0.20 | colorsys S，範圍 [0,1] |
| value_min | 0.15 | colorsys V，範圍 [0,1] |
| red bands | [0.95,0.05] | normalized H，跨 1→0，端點包含 |
| blue bands | [0.55,0.75] | normalized H，端點包含 |
| strong_ratio | 0.35 | 該色像素／S/V有效像素 ≥ 此值為STRONG |
| weak_ratio | 0.10 | 未達STRONG且 ≥ 此值為WEAK；其餘NONE |
| histogram_bins | 36 | 等寬 hue bins |

這是一組可審的工程起點，並非以答案最佳化的門檻。紅色色相跨零，藍色色帶涵蓋此批RGB的候選色域；S/V過濾低飽和與暗像素。當前最小有效像素335，64不會在這批已取到的框觸發，但未證明小框／遮影情境可靠。0.35／0.10只是待審分界，未估準確率，沒有以低光或遮擋真值挑最優點。

## 實際量測與樣本界線

LOCAL artifact：`/Users/polalabear/amidst-artifacts/hsv-proposal-20261021/`。`analyze114.py`、`report.json`、35張人物框上半部裁切、前後 `df-k` 皆保存。讀45張960×540 preview，逐張驗 RGB SHA；既有 RT-DETR 原始輸出中只取 person score≥0.30 的35框。0.30仍是 **PROPOSED_REPORTING_ONLY**，不是正式 index floor。重複視角／框可能含同一人，35不是35位獨立受試者，也沒有召回分母。

輸入 detections SHA-256：`5228d20c4d79ffb2495a427ed46177caa2eccc013c037267f94ddfaf736193f1`。
量測 report SHA-256：`1e6430c2a1c91bc1fbbd1af501ebfbefb5d8d3528ba9a3d788ac53b8e6e85e5b`。

| 像素統計（35框） | min | P25 | median | P75 | max |
|---|---:|---:|---:|---:|---:|
| 裁切總像素 | 714 | 1967 | 2812 | 4513.5 | 7874 |
| S/V有效像素 | 335 | 732 | 1419 | 2388.5 | 4676 |

| 色彩判定 | STRONG | WEAK | NONE | UNKNOWN | STRONG框有效像素 min／median／max |
|---|---:|---:|---:|---:|---|
| red | 15 | 6 | 14 | 0 | 335／1419／4676 |
| blue | 25 | 2 | 8 | 0 | 458／1067／3495 |

這是各色 **候選證據數**。人工紅／藍樣本數均 `UNKNOWN`，35框全待組員審核，不能把此表當標準答案。5框同時 red/blue STRONG，因每色獨立、框可含背景或另一人，不強行指定唯一衣色。沒有做像素人物分割、遮擋辨識或身分識別。

## UNKNOWN 與未涵蓋情況

沿用既有 `hsv_color.py`：裁切太小→`CROP_TOO_SMALL`；超出影像的裁切比例過高→`CROP_TRUNCATED`；通過 S/V 的像素不足→`LOW_LIGHT_OR_SATURATION`；這些分支讓各色為UNKNOWN，不是NONE。此次實際裁切都未觸發UNKNOWN，所以不能聲稱已驗證真實低光、遮影或截斷。

影像內部遮擋不一定造成 bbox 超界；暗背景與遮影也不能僅靠 HSV 完整判斷。此限制不能偽裝成已有遮影偵測器。若獨立審查要求「雙色STRONG／遮擋也要轉UNKNOWN」的新語意，須先列入契約 §14 待決並核定，再改程式；本提案不私自改既有判定。

## 凍結／再驗證順序

1. Claude 檢查RGB裁切、色彩污染、HSV定義與上述界線；組員只補審核標註，不改推論輸出。
2. 使用者在 G6 核定實際值與方法版本；目前 `approval_ref=null`。
3. 核定後建立 scope-bound parameter-set，凍結 method/config/content hashes；#118 正式索引從該組核准參數讀取。
4. 以凍結輸出做T/F抽樣，包含系統說有與沒有；評估端才能讀人類答案，不回灌調這次輸出。

驗證：反序列化至 `HSVConfig`、canonical hash與35個實際RGB框量測通過；`git diff --check`。此任務指定focused是diff檢查，沒有另建測試檔；#127產品查詢schema對純提案設定N/A。正式r004事件、準確率、G6、Controller/HTTP/browser未驗證。
