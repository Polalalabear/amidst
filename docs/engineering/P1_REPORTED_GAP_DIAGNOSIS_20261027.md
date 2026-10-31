# P1 人工回報漏檢／漏接逐格診斷（2026-10-27）

D1，回覆 #218／#247；來源是[#228使用者肉眼走查](https://github.com/Polalalabear/amidst/pull/228#issuecomment-6416863116)指定P1最終包、recording `2777741d96ac9aff5bffb2f61a4d2938`。**只讀既有輸出；未渲染、未跑detector／controller、未改D65或產品。**逐格表見[frames.csv](../history/p1_gap_diagnosis_20261027/frames.csv)，完整閾值、幾何數字與原檔pins見[summary.json](../history/p1_gap_diagnosis_20261027/summary.json)。

## 結論與證據等級

28格均已推論（INFERRED），在指定錄製上均為GAP／NO_CANDIDATE：

| 現有輸出的直接原因 | A | B | 合計 |
| --- | ---: | ---: | ---: |
| 沒有存下person ≥ index floor 0.3 | 8 | 7 | **15** |
| 有person，但分數全低於link_min_score 0.4 | 2 | 8 | **10** |
| 有person ≥0.4，但最後真框／D78平移參照的IoU均<0.3 | 1 | 2 | **3** |

門檻來源：0.3 的 index_score_floor、0.4 的 link_min_score（以及 0.5 的 query_min_score）是此凍結 run／bundle 的實際值；在來源 commit `c26d7cdd` 的 `configs/q1q5/parameter_set_v1.json` 仍為 value=null、status=PROPOSED，**不是已核定的全域參數值**。IoU=0.3、中心距離比例=0.5、link_max_gap_us 則按原設定各自的 APPROVED 狀態區分，不能混為同一個核定門檻。

這是**使用者選定失敗格的原因分布，不是recall、誤接率或全run準確率**。全體可見人物／正確框的獨立人工分母MISSING，不能從15/28推成模型漏檢率。index含320格；本報告只診斷指定28格。

可見性原始依據是使用者回報（REPORTED）。本次另逐張看了四張原始、hash綁定RGB：A50／2.50s與B123／6.15s完整人物在畫面，A58／2.90s與B156／7.80s人物部分被右邊界截斷仍可見（本次VERIFIED視覺抽樣）。其餘24格未重新做獨立視覺標註；CSV的selected_for_manual_visual_review只是抽樣清單，腳本不會自動宣稱人物可見。未讀GT、producer路線、renderer visibility/depth；身分始終UNCONFIRMED。

## 每格結果

2.5–3.0按50ms格點含3.00解讀；7.7–8.0採run半開終點，最後是7.95，8.00沒有影格（不是漏檢）。

| 鏡頭／frame | 秒 | person最高score | 分類 |
| --- | ---: | ---: | --- |
| A / 50 | 2.50 | NONE | 無已存person |
| A / 51 | 2.55 | NONE | 無已存person |
| A / 52 | 2.60 | NONE | 無已存person |
| A / 53 | 2.65 | NONE | 無已存person |
| A / 54 | 2.70 | NONE | 無已存person |
| A / 55 | 2.75 | NONE | 無已存person |
| A / 56 | 2.80 | NONE | 無已存person |
| A / 57 | 2.85 | NONE | 無已存person |
| A / 58 | 2.90 | 0.490363 | IoU<0.3 |
| A / 59 | 2.95 | 0.359096 | 分數<0.4 |
| A / 60 | 3.00 | 0.323097 | 分數<0.4 |
| B / 123 | 6.15 | 0.384504 | 分數<0.4 |
| B / 125 | 6.25 | NONE | 無已存person |
| B / 130 | 6.50 | 0.347267 | 分數<0.4 |
| B / 132 | 6.60 | NONE | 無已存person |
| B / 133 | 6.65 | 0.375727 | 分數<0.4 |
| B / 136 | 6.80 | 0.329530 | 分數<0.4 |
| B / 138 | 6.90 | 0.314424 | 分數<0.4 |
| B / 143 | 7.15 | NONE | 無已存person |
| B / 144 | 7.20 | NONE | 無已存person |
| B / 150 | 7.50 | NONE | 無已存person |
| B / 151 | 7.55 | 0.326645 | 分數<0.4 |
| B / 154 | 7.70 | 0.335783 | 分數<0.4 |
| B / 155 | 7.75 | 0.398019 | 分數<0.4 |
| B / 156 | 7.80 | 0.523503 | IoU<0.3 |
| B / 157 | 7.85 | NONE | 無已存person |
| B / 158 | 7.90 | 0.410716 | IoU<0.3 |
| B / 159 | 7.95 | NONE | 無已存person |

## 原因分類的實際含義

1. **15格無已存person：**只能確認在0.3儲存floor以上沒有person。部分格有refrigerator、sports ball、teddy bear、toothbrush等其他類別，顯示可能的合成外觀／姿態類別混淆；沒有逐框人工對應，不能說所有非person框都是同一個目標。具名P1包沒有floor以下raw logits/top-300，無法區分「person低於0.3」和「模型完全沒提出person」；原始分數MISSING，不填0。
2. **10格低於link分數：**例如B123有0.384504與0.362789兩個person框，低於0.4；B155為0.398019。它們不是MISSING影格或沒有跑推論。query_min_score=0.5只管seed／Q4等查詢門檻，這些已追蹤格實際用link_min_score=0.4；只改Q1／query門檻無法直接修復本組缺口。此錄製的request是person、color=null，因此紅色WEAK不構成本次link拒收原因。
3. **3格幾何拒收：**

| 格 | 真實prev/next IoU | 平移參照IoU | 真實／參照中心距離（框對角比例） |
| --- | ---: | ---: | --- |
| A58 / 2.90s | 0.137099939 | 0.225350853 | 0.223566／0.198117 |
| B156 / 7.80s | 0.299007110 | 0.299007110 | 0.163789／0.131091 |
| B158 / 7.90s | 0.249997614 | 0.239006360 | 0.239774／0.228513 |

中心距離均≤0.5，失敗的直接gate是IoU<0.3。B156與門檻只差0.000992890，仍須按原精度拒絕，不能把0.299四捨五入成0.30當PASS。邊界截斷使person框寬／高度變化，是可能的幾何失配原因；這是根據bbox和兩張右邊界RGB的診斷推論，不是已驗證因果或新增身份證據。

D78的移動參照已存在於這份歷史產品，A58參照IoU有改善仍不足；它不能補造15格不存在的person，也不能越過score/IoU門檻。#218早期A29在1.45s接回的歷史結果與這次2.50s後問題分開；不把本次視為新的D78前後重跑。本P1凍結來源的link schema仍是歷史v1＋audit，忠實保留，沒有為B2新v2要求重寫舊journal。

## 改善建議（未執行，先交使用者核定）

- **先處理detector輸出缺口。** 用同一份RGB、固定模型／前處理／code/weights pins建立可見性與bbox人工評估小集；若既有raw輸出找不到，明列缺資料。下一輪經授權才記完整低分候選、比較另一個核定detector或輸入方案。合成角色外觀／姿態domain差異與圖像邊界截斷是待檢驗假說，不能直接宣稱換模型必然改善。
- **分數方案另立參數版。** 10格目前直接被0.4擋下；如果要比較更低門檻，先核定獨立parameter_set與相同輸入對照，檢查false positives、重複框／歧義與誤接，不能只數多接回幾格。B123已有兩個person候選，降門檻可能引入歧義。15個無person格不會因單改link門檻必然恢復，3個IoU失敗也不會因此自動通過。
- **邊界／形狀變化另提契約選項。** 可比較裁切感知或有限形狀變化的匹配參照，仍須真觀測、同鏡頭、既有時間上界、歧義拒收與完整audit；這超出本次已核定D78保持最後框尺寸的語意，需新契約提案／核定後才實作。本次不放鬆IoU、中心距離或600ms。
- **將品質與誠實顯示分開。** 保留GAP／UNKNOWN，不能為消除畫面閃爍而畫假框或延後TEMP_LOST。未來比較報告分開detector缺口、分數拒收、幾何拒收、RETURN重接及真正盲區；主線正式參數／已凍結人工題不動。

## 重現與實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: 新Draft `codex/p1-reported-gap-diagnosis`；來源產品commit `c26d7cdd07deb43c9991a4f46403ea0236277fb1`，新head見PR。
- Files changed: 本報告、唯讀診斷script、curated summary.json／frames.csv；沒有產品改動。
- Commands run and results: 既有離線uv/Python執行 `scripts/diagnose_p1_detection_gaps.py --bundle <LOCAL_P1_BUNDLE> --output <NEW_LOCAL_OUTPUT>` 兩次，28格全部frame/journal/GAP互相綁定；36份輸入前後bytes／mtime未變（以JSON實際input_pins數為準）；summary/CSV逐bytes相同；`ruff check --select F,UP,B`與`git diff --check` PASS。四張RGB用view_image讀原檔，未改圖。
- Artifacts: MANIFEST SHA `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`；records SHA `816c261d4a3c4d243a6ce2a718a00690585763b68e928c8c0b3534182875ed2b`。summary SHA `495a6e6012c82b3edf45cd0846529449d394b1a653772b6b9b9d3de262884f4a`；CSV SHA `ca5a274527521f2e243d761829798db2ea8fedfb8d54ad49fbf57fd0563f95bf`。原包／RGB／完整錄製LOCAL，不上傳。
- Verified: 28格儲存／link直接拒收原因、3組IoU／中心距離、無色條件、source/run/frame/hash綁定，四張可見性抽樣。
- Not verified: 其餘24格獨立可見性標註、floor下raw分數、模型原因因果、誤接率／recall、改善效果、全run辨識品質。未跑render／推論／新產品／新錄製。
- Deviations, UNKNOWN items and follow-ups: 只讀既有輸出；改善方案待核定，不能把本報告當P1／AC7／正式研究驗收。
