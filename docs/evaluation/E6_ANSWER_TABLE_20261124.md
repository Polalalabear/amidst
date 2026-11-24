# E6 答案表與錯誤拆解：獨立重算（#717）

狀態：Codex 已完成，待 Argon 互審、Claude 第 1 批審查。全部為舊 16 段的事後描述；
不改 E3/E5 判定，不作固定決策點公平配對，不宣稱身分確認。模型呼叫 0、費用 USD 0。
計畫：#722 head `c03b6b37aa784c6f11ace3a0b6d0776b19e72f3d`；D377。

## 獨立重算與定義

先自行撰寫 `scripts/evaluation/e6_independent_diagnostics.py`，只 import 凍結評分器
`e3_scoring.py`（SHA-256 `acacce396f27e0d7c8bf03d527b22272f2622376ed4a43ae6db0842353f87d08`），
重現 B1 **114.0 s**、A2 **243.8 s**、AO **243.0667 s**，之後才讀 Claude 的 CSV／文字成品。
未讀其 `build.py`、`anchor.py`、`lib.py`、`base.py` 或 a3–a8 分析腳本；
既有 runner／tracker 只作輸入契約與 R-N 語意核對，未 import runner。
每段 Agent K=3 先平均；B1、R-N 各 K=1。166 個已消費來源列在 results.json，
corpus manifest、case／input case／GT、F4/AO run 都核對既有 manifest SHA。

答案表只在 LOCAL：`planned` 是原 input case 的操作者指令分段、actions 與來源；
`recorded_gt` 是錄製 GT 可見集合／盲區；`catalog_points` 是另列的 GT-derived 評分事件，
不冒稱原始劇本意圖。GT 原檔各多一個 endpoint guard tick，依來源的
半開 `[0,duration)` 範圍排除，不算失聯或重現；未改原檔。

| 組 | 錯人秒 s | 盲區誤鎖 s | 可見時 LOST s | 跟對率 |
|---|---:|---:|---:|---:|
| B1 | 114.0000 | 109.4000 | 85.0000 | 0.758721 |
| A2 | 243.8000 | 167.6000 | 32.8000 | 0.664971 |
| AO | 243.0667 | 174.8667 | 44.6667 | 0.651486 |
| R-N 主要 UNCERTAIN | 133.2000 | 94.0000 | 186.0000 | 0.613372 |
| R-N 敏感度 NOT_VISIBLE | 79.0000 | 41.4000 | 389.4000 | 0.432655 |

錯人秒＝WRONG_PERSON＋WRONG_CAMERA；盲區誤鎖不混入。可見分母 825.6 s，
全段 1044.6 s。43 個原始盲區含一個 0.4 s 閃爍；排除該閃爍後 42 個，
其中 41 個有重現，1 個右設限。事件表的誤鎖因此是 B1 109.0、A2 167.2、AO 174.6 s。

| 組 | 在下一盲區前接回 | 3 s 內接回 | 完成接回延遲中位 s | 開頭至首次盲區錯人 s |
|---|---:|---:|---:|---:|
| B1 | 0.609756 | 0.536585 | 0.2 | 40.6000 |
| A2 | 0.910569 | 0.788618 | 1.0 | 164.7333 |
| AO | 0.813008 | 0.715447 | 1.2 | 131.2000 |
| R-N UNCERTAIN | 0.512195 | 0.439024 | 0.6 | — |
| R-N NOT_VISIBLE | 0.292683 | 0.219512 | 0.6 | — |

接回後持續、接回前錯人／LOST、
接回後錯人與完整 2 s 持續條件都逐事件、逐 K 保留，不只列成功案例。

## 與 Claude 初版的差異

`e6_compare_outputs.py` 比較 58 列（42 盲區＋16 開頭）、**1,137 個數值欄**：
1,135 一致、2 不同、0 缺資料，按原 CSV 顯示精度比。

| 欄位 | 初版 | 本次 | 原因 |
|---|---:|---:|---|
| E3-C3 BLIND4 A2 持續2s跟對率 | 0.67 | 0 | K2/K3 接回後距下一盲區只有 1.0 s，不能證明完整 2 s |
| E3-C6 BLIND4 A2 持續2s跟對率 | 1.00 | 0 | 三次都只剩 0.6 s 可見，不能證明完整 2 s |

本次要求完整觀察 2 s；初版數值與「只檢查剩餘可見窗」相符，未讀腳本確認。
這是事後診斷定義差異，沒有修改凍結 scorer 或原研究判定。

原先 6 個 UNKNOWN 事件全部找到既有出處：

- E3-D2 38.2 s 至段末：CORPUS 的 `diagnostic_events.TRUE_CAMERA_EXIT` tick191、
  `metrics.true_exit_tick=191`，不是漏列的 RETURN。
- E3-C5 的 44.4–50.4、56.2–61.2、69.2–73.4、78.8–84.0 s：
  `excluded_duplicate_returns`，因 `DUPLICATE_GT_WINDOW_1CM` 排除，沒有消失。
- E3-C6 的 61.4–66.6 s：同欄的排除重複事件（duplicate_of E3-C3-RETURN-00328）。

七個 B4 共同開頭（A2/C2/D2/C3/C4/C5/C6）各扣 22 s，獨立重現
A2−B1 **+10.4 s**、AO−B1 **+54.3333 s**。本次 clip cluster bootstrap
seed660／2000 次：95% CI **[−38.0,47.0667]**、**[1.7333,99.6]**。
初版文字為 [−37.4,45.9]、[3.7,99.1]，其種子／取樣細節在讀取成品中未註明，
因此區間差異原因 **UNKNOWN**；點估計一致。clip 並非獨立劇本家族，這些區間不作 E6 判定。

## AO：回答當下與套用後分開

1848 次回答：SELECT 1633、OWN_BOX 132（**7.1429%**）、NOT_VISIBLE 74、UNCERTAIN 9。
1839 個可依當下 GT 評分，1110 正確（含 74 個正確 NOT_VISIBLE）；
只看 SELECT/OWN_BOX：**1036/1765** 框在目標上。1848 個合法接受，1834 有實際套用；
其餘為合法 UNCERTAIN 或段末 pending。逐回答保留完整候選、所選框、ask 狀態、
套用狀態／tick、其後 neutral_status 與分類。這是 AO 自己狀態觸發時點的描述，非公平配對。

| 最近回答時狀態 | 之後錯人 s | 之後盲區誤鎖 s |
|---|---:|---:|
| 當下目標可見、回答框正確 | 35.4667 | 9.7333 |
| 當下目標可見、回答框錯誤 | 182.5333 | 10.4000 |
| 當下目標不可見 | 25.0667 | 154.7333 |

切片到下一筆釋放回答，是時間關聯，不證明回答造成後續錯誤。
自我延續的原標籤算法重現 **254/304**（可見時先前顯示錯人）、**173/178**（不可見）。
但 254 中有 **21 次 OTHER→OTHER**，不代表確認同一個人；只在可解析身體框的
錯人子集，為 **241/265**，與較寬標籤算法分開列出。身分始終 UNCONFIRMED。
舊 A2 缺完整候選清單，不能補造公平逐候選配對；新紀錄規格見
[`E6_EXECUTION_RECORD_V1.md`](E6_EXECUTION_RECORD_V1.md)，未實作 #721。

## R-N 的執行與限制

規格先在 commit `81f3aacd` 提交，見 [`E6_RN_FROZEN_20261124.md`](E6_RN_FROZEN_20261124.md)。
`e6_rule_neutral.py` 獨立載入偵測、RGB 做原 HSV 與安全校正，只取 B1 seed tick／位置；
之後使用自己的 NeutralTracker 與最後有效位置，不讀 B1 後續決策或 GT。
FIRST／LOST_EARLY／POLL、ceil(duration/2*1.5) cap、下一 tick 套用提問時框皆保留。
32 個 run 共 1439 次零模型規則決策。與 AO 共同 ask tick 的 **1559 份候選集合**
（含 camera/box/score/red）0 差異；格式整理前後的 rows／calls 亦 0 差異。
8 個 focused tests 包含與真正 AOpenDecider 時機對照、cap、下一 tick、兩種無候選策略、
自己的 LOST／最後位置、距離與顏色門檻、GT/model import 隔離。

R-N 沒有 OWN_BOX，也沒有 AO 請求帶入的 B1 rule_state；R-N 額外保留最後位置。
比較只能說「**在中性追蹤器底座上**」。NOT_VISIBLE 版本的錯人較少伴隨 LOST 大增，
不能據此判優於 B1，也不改任何原研究結論。

## GT／影像抽樣

198 列標記中，每類依固定排序等距選 6 列，共 12 列。逐張檢視原 RGB，未改原圖、
未外傳；只看 GT 最大未裁切高度的鏡頭，保留原 SHA 與投影框。
**可見9／不可見0／無法判斷3**；三個 UNKNOWN 是同色人物重疊，單格無法分辨目標輪廓。
局部可見算可見；不確認身份。這不是隨機樣本，不推論全部198列或改寫 GT。
詳細方法與逐樣本結果留 LOCAL `image-review.json`。

## 重製、成品與驗證

所有原始來源唯讀；本次交付在 scratch clone 的 LOCAL
`local/evidence/cx-e6-717-20261124/`，**39 檔／28,089,295 bytes**（不含 MANIFEST），
MANIFEST SHA-256 `c584905a14b9f1c9684d0068e0f8d068ce984a92113648377409a0b7eba4926f`。
curated manifest 不含保留的探索中間檔；沒有刪檔。逐檔大小與 SHA 全在 MANIFEST：

| LOCAL 相對路徑 | SHA-256 |
|---|---|
| `results.json` | `fc23615a980ad43c9762138e30ee3edc207b88b39925703c06ba2d18e10c9a37` |
| `image-review.json` | `7c025e47a72fe42734091bb1e01dd5b6a3e3aadb343c236af21a0b6b993506d1` |
| `rn-final/`、baseline／summary／comparison／integrity | 逐檔見以上 MANIFEST；可由凍結輸入重製，圖像人工判讀不可保證逐位元重製 |

重製於寫入 clone，`EVIDENCE_ROOT` 指向來源 evidence、`E6_CAMERAS` 指向既有
safe_static 校正（SHA-256 `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f`），
`E6_PYTHON` 是既有唯讀環境；OUT 要用尚不存在的新輸出位置。

```sh
UV_CACHE_DIR=local/uv-cache uv run --offline --no-project --python "$E6_PYTHON" python -B scripts/evaluation/e6_rule_neutral.py --evidence "$EVIDENCE_ROOT" --cameras "$E6_CAMERAS" --out "$OUT/rn-final"
UV_CACHE_DIR=local/uv-cache uv run --offline --no-project --python "$E6_PYTHON" python -B scripts/evaluation/e6_independent_diagnostics.py --evidence "$EVIDENCE_ROOT" --rn "$OUT/rn-final" --out "$OUT/results.json"
UV_CACHE_DIR=local/uv-cache uv run --offline --no-project --python "$E6_PYTHON" python -B scripts/evaluation/e6_compare_outputs.py --diagnostics "$OUT/results.json" --reference "$EVIDENCE_ROOT/e3-answer-table-20261124/events.csv" --out "$OUT/final-comparison.json"
UV_CACHE_DIR=local/uv-cache uv run --offline --no-project --python "$E6_PYTHON" python -B -m pytest tests/evaluation/test_e6_independent.py -q -o addopts=''
```

focused pytest：8 passed；三個腳本與測試 ruff PASS；`git diff --check` PASS。
uv 在 sandbox panic 後改由核准的既有離線環境執行。未跑全套、本次模型、E6 新資料、
LIVE、gate、pin 或導航驗證。CI 與 PR head 以 PR 的實際產出紀錄為準。
