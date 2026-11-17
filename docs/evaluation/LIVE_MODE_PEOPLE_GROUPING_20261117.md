# 即時模式：`people.py` 併人規則修正（2026-11-17）

Model / effort：Sonnet 5.5 / high。全部用重播，沒有付費呼叫，沒有讀 API key，沒有 render；GT 只用在評分。
依據：[#544 的 Opus 判定](https://github.com/Polalalabear/amidst/pull/544#issuecomment-6924091618)第 1 點，和 `LIVE_MODE_A4_REGRESSION_20261116.md`。

## 改了什麼（`src/amidst/live_mode/people.py` 的 `group()`）

1. **同鏡頭 IoU 去重：** 同一台鏡頭裡，IoU ≥ 0.6（`DUP_IOU`）的框，只留分數高的。同鏡頭兩框 IoU 低於 0.6 仍算兩人（保留防止 pid 互換的原設計）。
2. **併人：**
   - `same_m` 預設 1.5 → **1.0 m**（`SAME_M`）。**1.0 m 是從 A4/B4 兩條路線挑的**：A4 旁人與目標相距 1.28–1.42 m，落在觀察到距離的 0.64–1.28 m 縫隙裡；換場景可能要重挑，沒有獨立資料驗證。
   - 逐筆貪婪併入改成：每個框先自成一人，重複挑「平均落地點距離最近、不共用鏡頭、< `same_m`」的一對合併，直到沒有為止。由距離決定誰併誰，不再由分數順序決定。
   - 一個人的 `xy` 改成成員落地點的平均；`dets` 仍依分數由高到低。
3. **計數器**（`PeopleTracker.stats`，重播輸出 `replay.people_stats`）：`dup_dropped`（同鏡頭去重掉的框）、`merges`（跨鏡頭併入次數）、`far_merges`（併入時兩組成員之間有兩框相距 > `same_m` 的次數）。
4. 影格間連結的門檻原本是 `same_m + vmax·dt`，為了不讓 `same_m` 改小順便縮小連結門檻，改成固定底數 `LINK_BASE_M = 1.5`（即舊值），只有併人規則變。

## 驗收

單元測試：`PYTHONPATH=src python -m pytest tests/live_mode -q` → 38 passed（原 29 個加新增 9 個；判定要求的 4 個情境各一，另加平均落地點／far_merges、依距離而非分數配對、`update()` 計數）。

重播（`replay_bench.py`，來源 `sol2`、`gate`，n=38，`gate4_review` 用 `--oracle-m 1.0`；修改前 = `main` `7d612aa7`，修改後 = 本分支）。跟對／跟錯／失聯，平均：

| 設定 | A4 八鏡頭 (n4) | A4 路線 (n15) | B4 八鏡頭 (n4) | B4 路線 (n15) | ALL (n38) |
| --- | --- | --- | --- | --- | --- |
| gate4_off（前） | 0.47/0.37/0.16 | 0.38/0.37/0.25 | 0.73/0.18/0.09 | 0.92/0.03/0.05 | 0.64/0.21/0.14 |
| gate4_off（後） | 0.47/0.37/0.16 | 0.38/0.37/0.25 | 0.73/0.18/0.09 | 0.92/0.03/0.05 | 0.64/0.21/0.14 |
| gate4_review（前） | 0.61/0.28/0.11 | 0.38/0.36/0.25 | 0.73/0.18/0.09 | 0.92/0.03/0.05 | 0.66/0.20/0.14 |
| gate4_review（後） | **0.74/0.22/0.04** | 0.38/0.37/0.25 | 0.73/0.18/0.09 | 0.92/0.03/0.05 | **0.67/0.20/0.13** |

| 判定條件 | 結果 |
| --- | --- |
| gate4_off 完全不變 | **通過**：38 段逐筆三值相同（off 不用 `group()`） |
| 4 m 覆核比 4 m 關閉差的紀錄 0/38 | **通過**：修改前 0/38、修改後 0/38 |
| A4 路線 ≥ 0.38、ALL ≥ 0.66 | **通過**：0.38、0.67 |
| 跨鏡頭相距 > 1.0 m 的併入 0 次 | **通過**：`far_merges` = 0（併入 1151 次） |
| 同鏡頭去重次數 | **49 個框**（38 段、107 次提問，提問數與修改前相同） |
| 每一段都不比修改前差 | **未通過，差一段**：見下 |

`gate4_review` 與修改前不同的只有 4 段（其餘 34 段三值完全相同），on_target 前→後：

| 紀錄 | 前 | 後 |
| --- | --- | --- |
| sol2 a4 lead r1 | 0.568/0.211/0.221 | **0.537**/0.242/0.221（−0.031，約 3 輪） |
| gate a4 8camg3 r1 | 0.239/0.478/0.283 | 0.717/0.283/0 |
| gate a4 8camg3 r2 | 0.681/0.170/0.149 | 0.702/0.191/0.106 |
| gate a4 8camg4 r2 | 0.718/0.256/0.026 | 0.744/0.205/0.051 |

退步那一段只有第 36–38 輪不同：修改前替身答 3 並採用；修改後同一個候選的 `xy` 變成多鏡頭平均，離替身看的真實位置超過 1.0 m，被判為「目標不在候選裡」而回 0（清除鎖定）。也就是說代價來自「成員平均落地點在鏡頭間有投影誤差」與替身 1.0 m 的組合，不是併錯人；該段仍沒有比 4 m 關閉差。這是否要接受，交給 Opus 判定。

第 27–34 輪（`sol2/a4_off_r2`，`trace_ticks.py`）：旁人 p2 (4.3, 1.9) 與目標 p5 (5.3, 1.1) 仍是兩個人（`trace_ticks_27_34_after.txt`）。

## 沒量到的

- 真模型在「目標不在候選裡」時的答法（需要花錢實跑）；`tracker.py:98` 初始鎖定的 1.5 m（Opus 建議另開一題）。
- 只有 A4/B4 兩條路線，1.0 m 與 0.6 IoU 沒有獨立資料驗證。
- 逐段標籤中的 `_off_`／`_review_` 在 `per_stream_review.json` 都換成 `X` 以便前後配對。

## 證據

`docs/evaluation/live_mode_people_grouping_20261117/`（`SHA256SUMS.txt`）：`bench_before.json`、`bench_after.json`、`per_stream_review.json`（38 段前後三值）、`trace_ticks_27_34_after.txt`。重播輸入是 LOCAL：`local/evidence/live-mode-advisor-20261116/sol2`、`local/evidence/live-mode-tracker-20261116/gate`（唯讀，未改）。

重現（`<runtime-deps>` = `local/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps`）：

```bash
PYTHONPATH=src:<runtime-deps> python scripts/live_mode/replay_bench.py --work <暫存> --src sol2=local/evidence/live-mode-advisor-20261116/sol2 --src gate=local/evidence/live-mode-tracker-20261116/gate --config "gate4_off=--mode off --gate-m 4" --config "gate4_review=--mode review --gate-m 4 --oracle-m 1.0"
```
