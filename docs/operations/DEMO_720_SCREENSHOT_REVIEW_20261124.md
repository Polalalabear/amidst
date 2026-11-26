# #714 截圖 README 與 #720 零付費界線

Codex 於 2026-11-24 逐張檢視既有 12 張原 PNG，沒有改圖或重拍。
來源 LOCAL `local/evidence/screenshots-714-20261124/`；MANIFEST.sha256 的 SHA-256
`24a38dfcdec6893f7bba6b4efa87c67e8bb91d302166e4bef2c2ce4e15b61560`，12/12 逐檔核對相符。
來源沒有 console error log；無法由截圖推論 console error=0。

| 檔名 | 親自觀察到的內容 | 證據界線 |
|---|---|---|
| a-home.png | Amidst 首頁與進入系統 | 單張首頁 |
| b1-a4-3d-click.png | A4 49.8 s；2D 被選取，顯示「3D 資產不存在」 | 不能當 3D PASS |
| b2-scene3d-direct.png | JSON `FORBIDDEN_DATA_SCOPE` | 圖內沒有 HTTP status/console，不當本次 HTTP 重跑 |
| c1-a4-mid-unknown.png | A4 25 s，UNKNOWN／ESTIMATE_IN_FUTURE，沒有估計點 | 圖內可見 |
| c2-a4-end-estimate.png | A4 49.8 s，INFERRED、0.4 m 範圍文字與藍點 | 非身分確認或精度驗證 |
| d1-b4-mid.png | B4 20 s，UNKNOWN／ESTIMATE_IN_FUTURE，無估計點 | 圖內可見 |
| d2-b4-end-estimate.png | B4 41.8 s，INFERRED 藍點，R101_IN 作用中 | 圖內可見 |
| f-b05-before-track.png | B-05 查詢窗、Agent 不可用／規則 | 額外截圖，非主要 A4/B4 |
| f-b05-panel-hidden.png | B-05 播放；右側無樓層俯視圖面板 | 只證明此時面板隱藏 |
| tmp1.png | 三個工作模式選單 | 不計交付驗收 |
| tmp2.png | B-05 查詢窗 | 不計交付驗收 |
| tmp3.png | A4 10 s UNKNOWN；2D/3D 按鈕 | 不計交付驗收 |

9 張非 tmp 圖（含 B-05 額外2張），不冒稱全部需求通過。
逐檔路徑／大小／SHA 與 console 缺漏記在本次 LOCAL `screenshots-review.json`；
console 記錄為 `{captured:false,errors:null,status:UNKNOWN}`，不是空錯誤清單。

**正式 launcher、正式 `/scene3d/` HTTP、WebGL 與方向動態驗收：未驗證。**
現行 launcher 在 owned root 產生 state；本次使用者要求 pinned 目錄不改檔，
而 scratch clone 對外部資產受既有 io guard 限制。沒有複製 3D 資產、改 guard、
擴大白名單或用無 guard 服務取代正式驗收。本次 Q1–Q3 的直接 API harness 不啟服務、
不讀 3D 資產，也不當作正式 launcher 通過。

#720 第3點：pin 未變（`c988ed607cb2941bde2b84688f9675213efd2a98`），
換 pin 後 AC1–AC8 **未執行／未驗證**。8785／8791／8795／8796 未重啟或修改。
第2點 r3b 需要新模型呼叫，依使用者指示不做，等待 gate 標準。
不修改原 gate 的 FAIL／NOT_READY。

本文件亦以 README 複本留在本次 scratch LOCAL，原 pinned 截圖目錄未寫入。
