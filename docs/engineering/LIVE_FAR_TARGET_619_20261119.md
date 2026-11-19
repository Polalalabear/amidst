# LIVE 室外遠端目標：偵測與追蹤失敗的量測與修正（#619，CX-L8）

日期 2026-11-19。Claude 接手（使用者同意；Codex 額度用完至 11-20 22:29）。範圍：用 #615 的腳本（`?script=<case_id>`）重現 H1、H4、H5，量測室外遠端的偵測與鎖定，找原因。GT 只用於量測評分（`measure/far_target_score.mjs`），不進推論。不動 #608／#617 的檔案和 tracker 的重新取得、門檻邏輯。

## 結論

1. **不是偵測解析度、偵測門檻、排程或投影。** graph 鏡頭看得到 T 且被排程時，LIVE（320×180、門檻 0.15）的偵測率：H1 100%、H5 95%。全 yard 掃描（graph 鏡頭、4 個朝向）88%。
2. **覆蓋缺口。** H1-1、H1-2、H5-1 約一半的 tick（22/42、27/58、27/53）沒有任何 graph 鏡頭看得到 T：x < −13 只有 CAM_ENTRY（不在追蹤圖），y > 5.7 沒有鏡頭。這是場景與鏡頭配置，不是偵測問題；H1 本來就要求 ≥15 s 看不到。
3. **偵測到卻被判成非紅。** `color.py` 的 weak = 0.3：EXT_CAR 6.4 m 的 red_ratio 0.24–0.29 連續 14 tick 被標 `none`；EXT_CLEAR 4 m 為 0.20–0.28；W2 24–27 m 的 13–15 px 小框常為 0。追蹤器只收 `red` 標籤，所以這些幀等於沒看到。
4. **標籤失敗後無法重新取得。** 追蹤器的 4 m gate 以最後估計為中心：H1-1 的 est 離 T 7.2 m，T 在 EXT_CLEAR（4 m）被偵測且標紅 12 tick 仍 LOST。這屬 #608（重新取得），本 PR 不動。
5. **H4-3 不是室外遠端。** 跟丟發生在室內 R101_IN（3.5 m，T 靜止，score 0.25 → 0）。#615 審查把 H4-3 歸為室外遠端不準確。
6. 640×360 擷取＋`--det-width 640`：遠處（14 m 以上）偵測 85% → 98%，但近處（0–6 m）90% → 62%，紅標籤總量不升；不採用。

## 修正

`--color-weak`（新參數，live 預設 **0.2**；離線 `color.CFG["weak"]`＝D131 的 0.3 不變）。`judge(rgb, bbox, weak=None)`。

受控掃描（yard、graph 鏡頭、同姿勢，`measure/detect_sweep.mjs`）：紅標籤 77.4% → 86.7%；14 m 以上 56% → 77%；偵測率不變。其他人物色：藍 C 0% → 0%（不誤標）；橘 B（色相本來就在紅色色帶）83% → 93%；A 98% → 98%。代價：B 更常被標紅，區分 T 與 B 本來就不靠這個標籤。

## 前後對照（9 案單次＋4 案複測；`local/evidence/far-target-619-20261119/compare.json`（SHA-256 見該目錄 SHA256SUMS））

幀＝T 被 GT 判為某 graph 鏡頭可見（框內 ≥ 60%）的鏡頭幀；偵測＝IoU ≥ 0.3 且 score ≥ 0.15；紅＝偵測且標籤 red。

| 距離組 | 修改前 n／偵測／紅 | 修改後 n／偵測／紅 |
| --- | --- | --- |
| 0–6 m | 191 / 79.6% / 71.7% | 176 / 91.5% / 90.3% |
| 6–10 m | 158 / 93.0% / 56.3% | 166 / 80.1% / 80.1% |
| 10–14 m | 232 / 94.4% / 91.8% | 197 / 97.5% / 97.0% |
| 14 m 以上 | 200 / 99.5% / 42.0% | 206 / 98.5% / 50.5% |
| 全部 | 781 / 91.8% / 67.0% | 745 / 92.5% / 78.8% |

T 可見 tick 中追蹤器在目標上（TRACKING、離 T ≤ 1.5 m）：184/465（39.6%）→ 203/454（44.7%）。

**難題點前 3 s 跟對（`hardset_check.mjs`，graph 讀法）：沒有改善。** 單次 9 案：修改前只有 H4-1 PASS，修改後只有 H4-3 PASS；複測：修改前 0/4，修改後 1/3（H1-2）。每次跑的模擬以延遲配速，ticks 數與姿勢不同，不是成對比較；只有「受控掃描」是成對的。

## 沒做到、原因與後續

- 難題點前跟對沒有因標籤修正而穩定：失敗還來自起始鎖錯人（A 同紅衣，H4-2 後測起始就鎖到 A）、4 m gate 不重新取得（#608），以及覆蓋缺口。建議 #608 合併後再用 `far_target_smoke.mjs`／`far_target_score.mjs` 重量。
- 覆蓋缺口要靠路線（讓 H1 的看不到段從覆蓋好的位置開始）或鏡頭配置，不在本 PR。
- 後測複測的 H5-1 逾時（10 分鐘）未完成；後測只有 3 案複測。
- 沒量 LLM 模式。

## 重現

```bash
# 伺服器（任一空埠，不要 8785／8791／8798）
PYTHONPATH=src python -B -m amidst.live_mode.server --port 8796 --device mps --advisor off --color-weak 0.2 ...
cd frontend/live-mode
LIVE_BASE=http://127.0.0.1:8796 OUT=out node measure/far_target_smoke.mjs H1-1
LIVE_BASE=http://127.0.0.1:8796 node measure/far_target_score.mjs out H1-1
REGION='[-15.2,-3.2,-6,8]' LIVE_BASE=http://127.0.0.1:8796 OUT=out node measure/detect_sweep.mjs yard glb 320 180 1.0 0,90,180,270 n6 T
```

LOCAL 證據：`local/evidence/far-target-619-20261119/`（README 與 SHA256SUMS 在該目錄；可由上述指令重建，結果因延遲配速不逐位相同）。
