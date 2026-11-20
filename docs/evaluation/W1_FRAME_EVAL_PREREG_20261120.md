# W1 逐格評估：預先登記（實驗前提交，W5）

Issue [#644](https://github.com/Polalalabear/amidst/issues/644)；日期 2026-11-20；Model / effort：Claude Sonnet 5.5 / high。此檔在付費呼叫**之前**提交，結果文件是 `W1_FRAME_EVAL_20261120.md`。

## 單位與標籤

- 評估單位 = 一個（事件、鏡頭、tick）影格；事件 A4-1、B4-1（r004 只有這兩個有 GT 的事件）。
- GT 只用在分層和評分。目標 T「可見」= GT 身體框落在畫面內 ≥ 50%，**且**身體框內有紅衣像素 ≥ 15（偵測器之外的像素證據；只幾何不夠，因為牆後的 T 也會投影進畫面）。
- 分層：`easy_visible`、`partial_occluded`（紅衣像素佔身體框 < 4.5%）、`partial_edge`（身體框被畫面邊緣切掉）、`far_small`（身體框高度在可見格的下三分位）、`lowscore_person`（T 上的人物框分數 0.3–0.5）、`nonperson_class`（T 上只有其他 COCO 類別的框）、`visible_nobox`（可見但 ≥ 0.3 沒有框）、負樣本 `neg_absent`（T 在畫面外）、`neg_occluded`（T 在視錐內但在牆後）、`neg_with_similar`。
- 無法做：索引分數下限是 0.3，沒有 0.05–0.3 的框，該層不測；索引裡幾乎沒有「相似人物同框」（只有 3 格負樣本、0 格正樣本），該層只報數字。

## 四組

(a) 規則（Q4 判法：person、score ≥ 0.3、HSV 紅色 STRONG／WEAK，選 `(verdict, -score)` 最佳框；另報不看顏色版）；(b) Agent 看圖（參考裁切＋當格，可選框 id 或自畫框或「不在」）；(c) Agent 不給圖（同文字：所有偵測的 id、類別、框、分數、顏色）；(d) Agent 看圖但只能選既有偵測 id 或「不在」。模型 terra，K=3；sol 只跑 (b)，K=1。每格逐格獨立呼叫。

## 指標與判讀（實驗前定死）

- 每格結果：TP（框在 GT 身體框內或 IoU ≥ 0.3）、FP_wrong_box（有人但框錯＝錯人）、FP_absent（T 不可見卻答「在」）、FN、TN。recall = TP／T 可見格；precision = TP／答「在」的格；F1；框 IoU；「不在」答對率 = 負樣本 TN 率。
- 每個正樣本層的 precision／F1 以該層加上**全部抽到的負樣本**計算；層內 recall 對比不受影響。整體數字是**分層樣本**的數字，不是母體比例。
- 成對差（同一格 b−a、c−a、b−c、b−d）用 5 秒區塊（事件×鏡頭×t//5 s）的 cluster bootstrap，2000 次，95% 百分位區間。K 次先對同一格取多數票（≥ 2/3 答「在」且 box 取第一個答「在」的次數），區間另報不取多數的平均版本。
- **H5 成立**：至少兩個困難層（`partial_occluded`、`far_small`、`lowscore_person`、`nonperson_class`、`visible_nobox`中任選，在場格 ≥ 50）b 對 a 的 recall 成對差區間 > 0，且該層加負樣本後整體 precision 下降 ≤ 0.05（b 對 a）。**推翻**：這些層的區間都含 0，或 precision 下降 > 0.05。在場格 < 50 的層「無法判斷」。
- **H2 成立**：b 對 c 在 `partial_occluded`／`visible_nobox`／`nonperson_class` 的 recall 差區間 > 0，**而且** `neg_absent`／`neg_occluded` 的 TN 率 b 不低於 c（差 ≥ −0.05）。**推翻**：差區間含 0。若 c 的 recall 與 b 接近，H2 改寫（優勢來自文字特徵而不是圖）。b 對 d 只是拆「自畫框」和「重新判斷既有框」的貢獻，不是成立條件。
- 限制先寫明：預錄、渲染合成場景、兩個事件、單一目標（紅衣）、層內格相關（用區塊 bootstrap 部分處理）、遮擋標籤是像素代理而非場景幾何。
