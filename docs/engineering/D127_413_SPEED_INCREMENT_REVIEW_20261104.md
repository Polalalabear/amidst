# D127 / #413：#408 倍速顯示增量審查

日期：2026-11-04（Asia/Taipei）。僅審 [#413](https://github.com/Polalalabear/amidst/issues/413) 指定的 `6de481da50aabb0f8acebf4c21b6066f679cb826..eb10d4c62ce09a765488cdd0548cfdd3abfd5109`，不重做 #408 全功能驗收。

## 判定與範圍

**ADOPT 此十檔增量，P1=0、P2=0、P3=2。** 兩個 P3 為量測文字的可理解性，不阻斷此限定採用；不是整包 #408 或正式研究驗收的 APPROVE，也沒有合併授權。

十檔為 `frontend/event-viewer/{app.mjs,index.html,style.css,sync.mjs,viewer.test.mjs}`、`frontend/workbench-v2/{app.mjs,event-menu.css,index.html,speed-meter.mjs,speed.test.mjs}`。

增量把來源時間的前進量除以牆鐘時間，只新增播放列文字／量測器／對應測試。它沒有改動來源時鐘轉換、`q-playback.mjs` 的 decode-ready 等待／每次來源採樣上限、`planTick` 的逐格規則、後端路由、D113 決策或錄製內容。`performance.now()` 只量測實際倍速，不成為來源時間或推論證據。

| 級別 | 原 head 位置 | 重現與建議 |
| --- | --- | --- |
| P3 | `frontend/workbench-v2/speed-meter.mjs:27-29` | 2秒內來源前進20000µs，實際0.01×仍被四捨五入顯示「實際0×」。這不能單靠文字判定真的完全停住。建議小正值顯示 `<0.1×` 或標「約」，並保留緩衝提示。 |
| P3 | `frontend/event-viewer/sync.mjs:117-129` | 最後一格後超過2秒，window沒有任何live samples，actual回null，文字只剩「設定2×」；長停滯時反而失去實際速度。建議保留0或明示量測不足，避免把null與設定值混讀。 |

手寫純函式重現：workbench以 `record(i*200,i*20)`、i=0..100，`actual(2000)=0.01`，格式化為「設定2× · 實際0×」。event-viewer依序 `record(0,5,0)`、`record(1,5,200)`、`record(2,5,400)`，最後一格後1.5秒為0.210526×，2.5秒為null，只顯示設定。沒有修改原碼或新增鏡頭證據。

## B-05b 親眼驗證

只讀 LOCAL P1 v4 包，manifest SHA-256 `6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`；manifest列397檔、149437452 bytes，先核對檔名無GT/private資產路徑，再交原launcher逐檔驗證。不啟動模型、推論、Blender或渲染，不讀真key或 `gt_private/`。

LOCAL state `/private/tmp/d127-413-b05b-01a1a4ff-1`，隨機loopback埠49844；IAB預設viewport，前景。以原 #408 head 的 current UI、錄製 `2777741d96ac9aff5bffb2f61a4d2938` 操作，設定2×，觀察到「實際1.9×」及「實際2×」和前進中的來源時間。本輪132.671秒瀏覽器播放紀錄含5249個main samples，最大相鄰main sample間隔166.9ms；包含循環，不等於一段132秒來源影片，也不代表物理螢幕fps量測。

手動來源時間核對：

| 來源時刻 | 目前鏡頭／影格標籤 | 決策／虛擬時間 |
| --- | --- | --- |
| 5.10 s | A，影像標籤A·5.10s | 2026-11-01 13:00:05.10（UTC+8），尚未進#18 |
| 5.15 s | B，影像標籤B·5.15s | #18 SWITCHING→PLAYING「畫面換成B」，2026-11-01 13:00:05.15（UTC+8） |

**D113時點未漂移。** RAF自動播放可能在5.16秒附近才取樣到切鏡，不能把RAF取樣時刻改稱決策時刻；精確slider核對仍是5.15秒。

另讀原交付截圖 `31-speed-note-set2x-actual-b05b-system.jpg`，實際SHA-256與其SHA256SUMS一致：`782a43179cc16a8164be41a8f49b7ace65551b5437b2ddca634bf019a14e51c2`。原圖在來源2.40秒、影格2.35秒，確實顯示「緩衝中 · 前一來源影格」與「實際0×」。因此它記錄當時等待下一張影像，不能說成已維持2×；單張截圖也不能證明永久停止。加上P3的四捨五入，同樣的0×文字也可能是很慢的正速度。本輪沒有重現持續0×或永久停住，歷史停滯長度／根因仍UNKNOWN。

新LOCAL截圖（不提交圖片）：`/private/tmp/d127-413-b05b-510.jpg` SHA-256 `9eeecb2740d0fe5562842fc84127b07a9b98f148ff54da43acb62555427d2243`；`/private/tmp/d127-413-b05b-515.jpg` `14195584d1430077aefdee07885b1f574277da95c1efd300159564d9b4a2af31`。瀏覽器摘要收據 `/private/tmp/d127-413-browser.json` `254f07e28db0d462e5ac2d15a91a9a06e3fc781f8076502b60669061180b0edd`。服務以本次SERVER.json的PID／state／port核對後SIGINT停止，exit0；不影響其他服務。

## Focused gate

在乾淨的精確 head `eb10d4c62ce09a765488cdd0548cfdd3abfd5109`：

```sh
node --test frontend/workbench-v2/*.test.mjs frontend/event-viewer/*.test.mjs
uv run --no-project --offline --python /Users/polalabear/.local/bin/python3.12 python scripts/check_architecture_guard.py --repo . --base origin/mainline/q1q5 --report /private/tmp/d127-413-guard.json
git diff --check
git diff origin/mainline/q1q5...HEAD --check
```

Node **410 passed／0 failed／0 skipped，2.883s**；guard **PASS、authority/inference/schemas各0 findings，沒有 --allow**；兩個diff check PASS。初跑有5個sandbox loopback EPERM與1個sparse未取`.gitignore`造成的失敗；補取該文字檔並允許本機HTTP測試後，原碼／原測試未改即全過。

本審查PR從 `mainline/q1q5@796cc176cd40bedbfe701b95192d3c8679755aa9` 起，只提交本紀錄與結構化收據，不移入 #408 其餘未合功能，也未改Claude擁有的UI程式。兩個P3回原 #408 供Claude review；沒有另做全套Python測試、event-viewer真實複雜事件播放、物理螢幕fps、長期穩定性或正式驗收。
