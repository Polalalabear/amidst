# E5 數字總表（唯讀摘錄，2026-11-24）

Refs #684、#704；Draft #702。2026-11-24 增補 AO-L（§6）與 W1 F1 兩準則（§7），原 §1–§5 與 S1–S3 不改。只摘錄已存在的評分輸出與費用記錄，不重算、不四捨五入，不加入判定或結論。`UNKNOWN（來源未提供）`表示該來源沒有該欄位；不是0。`null`、原始陣列與布林值照抄。

## 1. 來源

| ID | 相對路徑 | SHA-256 | bytes |
|---|---|---|---|
| S1 | `local/evidence/e5-20261123/report.json` | `f000830e7023e5e8beb3338d230386967e3e700b3e54c93dd38ff012812c1bee` | 65229 |
| S2 | `local/evidence/e5-20261123/report-skeleton.md` | `47a9b0378b38b396345c856bb9c65a8b66ae88d41912e224560d6b424ac59b14` | 7892 |
| S3 | `docs/operations/E5_REPORT_20261123.md` | `1e00733fde385c72e4ee2261f0c7ff7672c30b17d085181fd8206d398fb6d7d6` | 9393 |

| S4 | `local/evidence/e5-aol-20261124/report.json` | `edf988df08ac48c421086fa1c37394b285a4c34335e2aa23c0091a0e5439f3ad` | 81901 |
| S5 | `local/evidence/e5-aol-20261124/report-skeleton.md` | `07ff4dd108df0415beff6d8005ef9e2280637073d5ab5ea5216e60188f40114b` | 9302 |
| S6 | `docs/operations/E5_REPORT_20261123.md`（main `6afb4f76` 現行版，含 #706 的 §9 AO-L） | `4833adb7f608973194f24da9e54ea20742f3b6be31c208cf8bec024c638828eb` | 14919 |

S3 是 #698 版（舊），S6 是 #706 之後的現行版，兩者為同一路徑的不同版本，各自保留。S4／S5 含 AO 與 AO-L；S4 的 AO 部分與 S1 相同（見 §6），因此 §2–§5 仍引用 S1／S2。費用帳本欄位引用 S6 §5、§9.3。

S1／S2 是 LOCAL 兩檔。S3 是 main `d52ce2f0` 中已合併 #698 的文件；不更改該文件。每個 S1／S2／S3 引用均對應上表的相對路徑與 SHA-256。原始 AO 執行需要付費才能重做；本表可從現有檔案只讀重建，不會呼叫模型或評分器。

## 2. 樣本數與組別表（原樣）

來源 S2「組別合計」；此區保留來源的顯示精度。段數、決策點分母與top-k分母都直接照抄。

| 組 | 段數 | 錯人秒 | 跟對率 | 失聯秒 | 盲區誤鎖秒 | 決策點對 | top-1 | top-3 | 有排名點 | 延遲 p50／p95 ms | 輸入／輸出 token |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 | 16 | 259.13 | 0.645 | 33.93 | 166.07 | 20/68 | 2/111 | 2/111 | 8 | 4335／9439 | 2285165／404378 |
| A2 | 16 | 243.80 | 0.665 | 32.80 | 167.60 | 25/68 | 3/111 | 3/111 | 9 | 4944／10669 | 14813760／477779 |
| A3 | 9 | 49.33 | 0.826 | 17.20 | 13.60 | 23/38 | 0/21 | 0/21 | 0 | 4875／11442 | 1374551／46291 |
| AO | 16 | 243.07 | 0.651 | 44.67 | 174.87 | 15/68 | 34/111 | 87/111 | 111 | 4557／11052 | 17410415／344414 |
| B1 | 16 | 114.00 | 0.759 | 85.00 | 109.40 | 28/68 | 11/37 | 25/37 | 36 | —／— | 0／0 |
| B2 | 16 | 114.00 | 0.759 | 85.00 | 109.40 | 28/68 | 13/37 | 27/37 | 37 | —／— | 0／0 |

S1 的各 `per_case` 原始 `k`、`dp_majority`、各 `comparisons` 的 `n_points`／`n_segments`／`x_points`／`y_points` 在下節逐欄照抄。未從陣列長度、true個數或token計算新樣本數。

## 3. S1 原始欄位、點估計、95% 信賴區間

JSON pointer 使用 JSON 原鍵名；`|` 以 HTML entity 顯示。`*_ci` 與相同前綴欄位放同一列，區間不重新生成。樣本欄只引用當前原物件明列的 n／k；沒有就寫 UNKNOWN，其他分母見§2及原欄位。非點估計的計數、p值、token、延遲、布林旗標也逐欄保留。

| JSON pointer（S1） | 點估計／原值 | 95% CI（原值） | 樣本數／K（原欄位） |
|---|---|---|---|
| `/per_arm/A1/segments` | `[E3-A1, E3-A2, E3-A3, E3-B1, E3-B2, E3-C1, E3-C2, E3-D1, E3-D2, E3-B3, E3-B4, E3-B5, E3-C3, E3-C4, E3-C5, E3-C6]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/wrong_person_s` | `259.133` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/follow_rate` | `0.6448` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/lost_s` | `33.933` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/false_lock_s` | `166.067` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/dp_correct` | `20` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/dp_total` | `68` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/top1` | `[2, 111]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/top3` | `[2, 111]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/random_top1` | `0.125` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/ranked_points` | `8` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/latency_ms_p50` | `4335` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/latency_ms_p95` | `9439` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/input_tokens` | `2285165` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/output_tokens` | `404378` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A1/cost_usd` | `UNKNOWN (not in the run log; read the ApiGuard ledger)` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/segments` | `[E3-A1, E3-A2, E3-A3, E3-B1, E3-B2, E3-C1, E3-C2, E3-D1, E3-D2, E3-B3, E3-B4, E3-B5, E3-C3, E3-C4, E3-C5, E3-C6]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/wrong_person_s` | `243.8` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/follow_rate` | `0.665` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/lost_s` | `32.8` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/false_lock_s` | `167.6` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/dp_correct` | `25` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/dp_total` | `68` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/top1` | `[3, 111]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/top3` | `[3, 111]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/random_top1` | `0.125` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/ranked_points` | `9` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/latency_ms_p50` | `4944` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/latency_ms_p95` | `10669` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/input_tokens` | `14813760` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/output_tokens` | `477779` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A2/cost_usd` | `UNKNOWN (not in the run log; read the ApiGuard ledger)` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/A3/segments` | `[E3-A1, E3-A2, E3-A3, E3-B1, E3-B2, E3-C1, E3-C2, E3-D1, E3-D2]` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/wrong_person_s` | `49.333` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/follow_rate` | `0.8255` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/lost_s` | `17.2` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/false_lock_s` | `13.6` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/dp_correct` | `23` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/dp_total` | `38` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/top1` | `[0, 21]` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/top3` | `[0, 21]` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/random_top1` | `0.125` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/ranked_points` | `0` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/latency_ms_p50` | `4875` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/latency_ms_p95` | `11442` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/input_tokens` | `1374551` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/output_tokens` | `46291` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/A3/cost_usd` | `UNKNOWN (not in the run log; read the ApiGuard ledger)` | `UNKNOWN（來源未提供）` | dp_total=38 |
| `/per_arm/AO/segments` | `[E3-A1, E3-A2, E3-A3, E3-B1, E3-B2, E3-C1, E3-C2, E3-D1, E3-D2, E3-B3, E3-B4, E3-B5, E3-C3, E3-C4, E3-C5, E3-C6]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/wrong_person_s` | `243.067` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/follow_rate` | `0.6515` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/lost_s` | `44.667` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/false_lock_s` | `174.867` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/dp_correct` | `15` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/dp_total` | `68` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/top1` | `[34, 111]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/top3` | `[87, 111]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/random_top1` | `0.125` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/ranked_points` | `111` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/latency_ms_p50` | `4557` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/latency_ms_p95` | `11052` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/input_tokens` | `17410415` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/output_tokens` | `344414` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/cost_usd` | `UNKNOWN (not in the run log; read the ApiGuard ledger)` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/calls` | `1848` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/provider_error` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/provider_errors` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/format_rejected` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/budget_denied` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/expired` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/applied` | `1834` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/valid_calls` | `1848` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/answer_counts/SELECT` | `1633` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/answer_counts/OWN_BOX` | `132` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/answer_counts/UNCERTAIN` | `9` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AO/e5_calls/answer_counts/NOT_VISIBLE` | `74` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/segments` | `[E3-A1, E3-A2, E3-A3, E3-B1, E3-B2, E3-C1, E3-C2, E3-D1, E3-D2, E3-B3, E3-B4, E3-B5, E3-C3, E3-C4, E3-C5, E3-C6]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/wrong_person_s` | `114.0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/follow_rate` | `0.7587` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/lost_s` | `85.0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/false_lock_s` | `109.4` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/dp_correct` | `28` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/dp_total` | `68` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/top1` | `[11, 37]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/top3` | `[25, 37]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/random_top1` | `0.125` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/ranked_points` | `36` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/latency_ms_p50` | `null` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/latency_ms_p95` | `null` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/input_tokens` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/output_tokens` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B1/cost_usd` | `UNKNOWN (not in the run log; read the ApiGuard ledger)` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/segments` | `[E3-A1, E3-A2, E3-A3, E3-B1, E3-B2, E3-C1, E3-C2, E3-D1, E3-D2, E3-B3, E3-B4, E3-B5, E3-C3, E3-C4, E3-C5, E3-C6]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/wrong_person_s` | `114.0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/follow_rate` | `0.7587` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/lost_s` | `85.0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/false_lock_s` | `109.4` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/dp_correct` | `28` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/dp_total` | `68` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/top1` | `[13, 37]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/top3` | `[27, 37]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/random_top1` | `0.125` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/ranked_points` | `37` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/latency_ms_p50` | `null` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/latency_ms_p95` | `null` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/input_tokens` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/output_tokens` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/B2/cost_usd` | `UNKNOWN (not in the run log; read the ApiGuard ledger)` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/comparisons/AO-B1/wp_diff` | `129.067` | `[55.2, 193.13333333333333]` | n_points=68; n_segments=16 |
| `/comparisons/AO-B1/false_lock_diff` | `65.467` | `[39.73333333333333, 91.26666666666667]` | n_points=68; n_segments=16 |
| `/comparisons/AO-B1/follow_diff` | `-0.1072` | `[-0.19993455295027052, -0.0032536185558561526]` | n_points=68; n_segments=16 |
| `/comparisons/AO-B1/mcnemar/agent_only` | `7` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/comparisons/AO-B1/mcnemar/baseline_only` | `20` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/comparisons/AO-B1/mcnemar/p` | `0.0191572904586792` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/comparisons/AO-B1/n_points` | `68` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/comparisons/AO-B1/n_segments` | `16` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/comparisons/AO-B1/segments` | `[E3-A1, E3-A2, E3-A3, E3-B1, E3-B2, E3-B3, E3-B4, E3-B5, E3-C1, E3-C2, E3-C3, E3-C4, E3-C5, E3-C6, E3-D1, E3-D2]` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/comparisons/AO-B1&#124;iou` | `null` | `UNKNOWN（來源未提供）` | UNKNOWN（來源未提供） |
| `/comparisons/AO-B1&#124;topk/top1_diff` | `0.009` | `[-0.15740740740740738, 0.1724137931034483]` | n_segments=13; x_points=111; y_points=37 |
| `/comparisons/AO-B1&#124;topk/x_top1` | `0.3063063063063063` | `UNKNOWN（來源未提供）` | n_segments=13; x_points=111; y_points=37 |
| `/comparisons/AO-B1&#124;topk/y_top1` | `0.2972972972972973` | `UNKNOWN（來源未提供）` | n_segments=13; x_points=111; y_points=37 |
| `/comparisons/AO-B1&#124;topk/x_top3` | `0.7837837837837838` | `UNKNOWN（來源未提供）` | n_segments=13; x_points=111; y_points=37 |
| `/comparisons/AO-B1&#124;topk/y_top3` | `0.6756756756756757` | `UNKNOWN（來源未提供）` | n_segments=13; x_points=111; y_points=37 |
| `/comparisons/AO-B1&#124;topk/x_points` | `111` | `UNKNOWN（來源未提供）` | n_segments=13; x_points=111; y_points=37 |
| `/comparisons/AO-B1&#124;topk/y_points` | `37` | `UNKNOWN（來源未提供）` | n_segments=13; x_points=111; y_points=37 |
| `/comparisons/AO-B1&#124;topk/x_random_top1` | `0.125` | `UNKNOWN（來源未提供）` | n_segments=13; x_points=111; y_points=37 |
| `/comparisons/AO-B1&#124;topk/n_segments` | `13` | `UNKNOWN（來源未提供）` | n_segments=13; x_points=111; y_points=37 |
| `/comparisons/AO-B1&#124;iou_conservative/follow_diff` | `-0.1033` | `[-0.194519427402863, -0.0016972165648336812]` | n_segments=16 |
| `/comparisons/AO-B1&#124;iou_conservative/wp_diff` | `132.467` | `[60.26666666666667, 195.4]` | n_segments=16 |
| `/comparisons/AO-B1&#124;iou_conservative/n_segments` | `16` | `UNKNOWN（來源未提供）` | n_segments=16 |
| `/comparisons/B2-B1/wp_diff` | `0.0` | `[0.0, 0.0]` | n_points=68; n_segments=16 |
| `/comparisons/B2-B1/false_lock_diff` | `0.0` | `[0.0, 0.0]` | n_points=68; n_segments=16 |
| `/comparisons/B2-B1/follow_diff` | `0.0` | `[0.0, 0.0]` | n_points=68; n_segments=16 |
| `/comparisons/B2-B1/mcnemar/agent_only` | `0` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/comparisons/B2-B1/mcnemar/baseline_only` | `0` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/comparisons/B2-B1/mcnemar/p` | `1.0` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/comparisons/B2-B1/mcnemar/favours` | `null` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/comparisons/B2-B1/n_points` | `68` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/comparisons/B2-B1/n_segments` | `16` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/comparisons/B2-B1/segments` | `[E3-A1, E3-A2, E3-A3, E3-B1, E3-B2, E3-B3, E3-B4, E3-B5, E3-C1, E3-C2, E3-C3, E3-C4, E3-C5, E3-C6, E3-D1, E3-D2]` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/per_case/E3-A1&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A1/primary/wp_s` | `9.4` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A1/primary/correct` | `204.99343333333331` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A1/primary/visible` | `271.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A1/primary/lost_s` | `3.7999999999999994` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A1/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A1/dp_majority` | `[false, false, false, false, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A2/primary/wp_s` | `8.066666666666666` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A2/primary/correct` | `218.00143333333335` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A2/primary/visible` | `271.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A2/primary/lost_s` | `2.533333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A2/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A2/dp_majority` | `[false, false, false, false, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A3/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A3/primary/wp_s` | `8.6` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A3/primary/correct` | `204.99343333333331` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A3/primary/visible` | `271.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A3/primary/lost_s` | `4.6` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A3/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A3/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A3/dp_majority` | `[false, false, false, true, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;A3/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/primary/wp_s` | `6.733333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/primary/correct` | `220.00683333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/primary/visible` | `271.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/primary/lost_s` | `3.466666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/dp_majority` | `[true, true, true, true, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/calls` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/applied` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/valid_calls` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/answer_counts/SELECT` | `28` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/answer_counts/OWN_BOX` | `2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/calls` | `31` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/applied` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/valid_calls` | `31` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/answer_counts/SELECT` | `28` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/answer_counts/UNCERTAIN` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/calls` | `33` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/applied` | `32` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/valid_calls` | `33` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/answer_counts/SELECT` | `29` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/answer_counts/UNCERTAIN` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A1&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B1/primary/wp_s` | `11.8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B1/primary/correct` | `171.001` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B1/primary/visible` | `271.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B1/primary/lost_s` | `8.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B1/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B1/dp_majority` | `[false, false, false, false, true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B2/primary/wp_s` | `11.8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B2/primary/correct` | `171.001` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B2/primary/visible` | `271.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B2/primary/lost_s` | `8.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B2/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B2/dp_majority` | `[false, false, false, false, true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A1/primary/wp_s` | `22.8` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A1/primary/correct` | `71.0066` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A1/primary/visible` | `201.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A1/primary/lost_s` | `3.2000000000000006` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A1/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A1/dp_majority` | `[false, false, false, false, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A2/primary/wp_s` | `22.333333333333332` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A2/primary/correct` | `73.33820000000001` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A2/primary/visible` | `201.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A2/primary/lost_s` | `3.2000000000000006` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A2/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A2/dp_majority` | `[false, false, false, false, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A3/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A3/primary/wp_s` | `0.20000000000000004` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A3/primary/correct` | `187.99530000000001` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A3/primary/visible` | `201.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A3/primary/lost_s` | `2.4` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A3/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A3/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A3/dp_majority` | `[true, true, false, true, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;A3/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/primary/wp_s` | `15.4` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/primary/correct` | `117.3304` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/primary/visible` | `201.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/primary/lost_s` | `1.3333333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/dp_majority` | `[false, false, false, false, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/calls` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/applied` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/valid_calls` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/answer_counts/SELECT` | `15` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/answer_counts/OWN_BOX` | `7` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/calls` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/applied` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/valid_calls` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/answer_counts/SELECT` | `15` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `7` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/calls` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/applied` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/valid_calls` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/answer_counts/SELECT` | `20` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A2&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B1/primary/wp_s` | `0.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B1/primary/correct` | `187.99530000000001` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B1/primary/visible` | `201.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B1/primary/lost_s` | `2.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B1/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B1/dp_majority` | `[true, true, false, true, true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B2/primary/wp_s` | `0.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B2/primary/correct` | `187.99530000000001` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B2/primary/visible` | `201.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B2/primary/lost_s` | `2.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B2/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B2/dp_majority` | `[true, true, false, true, true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A1/primary/wp_s` | `5.2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A1/primary/correct` | `104.00433333333335` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A1/primary/visible` | `130.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A1/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A1/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A1/dp_majority` | `[false, true, true, true, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A2/primary/wp_s` | `5.6000000000000005` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A2/primary/correct` | `102.00233333333334` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A2/primary/visible` | `130.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A2/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A2/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A2/dp_majority` | `[true, true, true, true, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A3/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A3/primary/wp_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A3/primary/correct` | `130.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A3/primary/visible` | `130.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A3/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A3/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A3/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A3/dp_majority` | `[true, true, true, true, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;A3/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/primary/wp_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/primary/correct` | `128.999` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/primary/visible` | `130.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/primary/lost_s` | `0.20000000000000004` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/dp_majority` | `[true, true, true, true, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/calls` | `13` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/applied` | `13` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/valid_calls` | `13` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/answer_counts/SELECT` | `12` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/answer_counts/OWN_BOX` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/calls` | `13` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/applied` | `13` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/valid_calls` | `13` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/answer_counts/SELECT` | `12` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/calls` | `13` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/applied` | `13` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/valid_calls` | `13` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/answer_counts/SELECT` | `12` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-A3&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B1/primary/wp_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B1/primary/correct` | `130.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B1/primary/visible` | `130.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B1/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B1/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B1/dp_majority` | `[true, true, true, true, true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B2/primary/wp_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B2/primary/correct` | `130.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B2/primary/visible` | `130.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B2/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B2/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B2/dp_majority` | `[true, true, true, true, true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A1/primary/wp_s` | `3.1999999999999997` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A1/primary/correct` | `196.99919999999997` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A1/primary/visible` | `216.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A1/primary/lost_s` | `0.4000000000000001` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A1/primary/false_lock_s` | `9.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A1/dp_majority` | `[false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A2/primary/wp_s` | `2.4` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A2/primary/correct` | `201.99599999999998` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A2/primary/visible` | `216.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A2/primary/lost_s` | `0.4000000000000001` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A2/primary/false_lock_s` | `9.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A2/dp_majority` | `[false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A3/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A3/primary/wp_s` | `3.2000000000000006` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A3/primary/correct` | `199.0008` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A3/primary/visible` | `216.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A3/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A3/primary/false_lock_s` | `4.8` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A3/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A3/dp_majority` | `[true, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;A3/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/primary/wp_s` | `6.933333333333334` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/primary/correct` | `168.66` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/primary/visible` | `216.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/primary/lost_s` | `2.533333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/primary/false_lock_s` | `7.933333333333334` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/dp_majority` | `[false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/calls` | `31` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/applied` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/valid_calls` | `31` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/answer_counts/SELECT` | `29` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/answer_counts/UNCERTAIN` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/answer_counts/NOT_VISIBLE` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/calls` | `31` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/applied` | `31` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/valid_calls` | `31` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/answer_counts/SELECT` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/answer_counts/NOT_VISIBLE` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/calls` | `31` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/applied` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/valid_calls` | `31` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/answer_counts/SELECT` | `29` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/answer_counts/UNCERTAIN` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B1&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B1/primary/wp_s` | `3.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B1/primary/correct` | `199.0008` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B1/primary/visible` | `216.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B1/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B1/primary/false_lock_s` | `4.8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B1/dp_majority` | `[true, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B2/primary/wp_s` | `3.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B2/primary/correct` | `199.0008` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B2/primary/visible` | `216.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B2/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B2/primary/false_lock_s` | `4.8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B2/dp_majority` | `[true, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A1/primary/wp_s` | `4.466666666666666` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A1/primary/correct` | `170.66346666666666` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A1/primary/visible` | `193.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A1/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A1/primary/false_lock_s` | `6.866666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A1/dp_majority` | `[false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A2/primary/wp_s` | `3.5999999999999996` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A2/primary/correct` | `174.9931` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A2/primary/visible` | `193.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A2/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A2/primary/false_lock_s` | `7.400000000000001` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A2/dp_majority` | `[false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A3/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A3/primary/wp_s` | `2.533333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A3/primary/correct` | `180.33276666666666` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A3/primary/visible` | `193.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A3/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A3/primary/false_lock_s` | `1.2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A3/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A3/dp_majority` | `[true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;A3/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/primary/wp_s` | `10.266666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/primary/correct` | `135.66613333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/primary/visible` | `193.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/primary/lost_s` | `1.2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/primary/false_lock_s` | `6.333333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/dp_majority` | `[false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/calls` | `27` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/applied` | `27` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/valid_calls` | `27` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/answer_counts/SELECT` | `24` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/answer_counts/OWN_BOX` | `2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/answer_counts/NOT_VISIBLE` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/calls` | `27` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/applied` | `27` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/valid_calls` | `27` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/answer_counts/SELECT` | `24` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/answer_counts/NOT_VISIBLE` | `2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/calls` | `28` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/applied` | `28` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/valid_calls` | `28` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/answer_counts/SELECT` | `25` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/answer_counts/NOT_VISIBLE` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B2&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B1/primary/wp_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B1/primary/correct` | `193.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B1/primary/visible` | `193.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B1/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B1/primary/false_lock_s` | `0.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B1/dp_majority` | `[true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B2/primary/wp_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B2/primary/correct` | `193.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B2/primary/visible` | `193.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B2/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B2/primary/false_lock_s` | `0.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B2/dp_majority` | `[true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A1/primary/wp_s` | `12.533333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A1/primary/correct` | `216.33333333333334` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A1/primary/visible` | `295.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A1/primary/lost_s` | `3.1999999999999997` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A1/primary/false_lock_s` | `0.6` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A1/dp_majority` | `[false, false, false, true, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A2/primary/wp_s` | `7.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A2/primary/correct` | `244.0043333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A2/primary/visible` | `295.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A2/primary/lost_s` | `3.2000000000000006` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A2/primary/false_lock_s` | `0.6` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A2/dp_majority` | `[false, false, false, true, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A3/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A3/primary/wp_s` | `22.2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A3/primary/correct` | `144.668` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A3/primary/visible` | `295.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A3/primary/lost_s` | `7.866666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A3/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A3/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A3/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;A3/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/primary/wp_s` | `10.533333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/primary/correct` | `230.01149999999998` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/primary/visible` | `295.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/primary/lost_s` | `2.466666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/primary/false_lock_s` | `1.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/calls` | `34` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/applied` | `34` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/valid_calls` | `34` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/answer_counts/SELECT` | `34` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/calls` | `34` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/applied` | `34` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/valid_calls` | `34` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/answer_counts/SELECT` | `33` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/calls` | `34` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/applied` | `34` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/valid_calls` | `34` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/answer_counts/SELECT` | `34` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C1&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B1/primary/wp_s` | `25.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B1/primary/correct` | `123.9885` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B1/primary/visible` | `295.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B1/primary/lost_s` | `9.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B1/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B1/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B2/primary/wp_s` | `25.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B2/primary/correct` | `123.9885` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B2/primary/visible` | `295.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B2/primary/lost_s` | `9.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B2/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B2/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A1/primary/wp_s` | `29.266666666666666` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A1/primary/correct` | `38.6657` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A1/primary/visible` | `199.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A1/primary/lost_s` | `2.7999999999999994` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A1/primary/false_lock_s` | `0.4000000000000001` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A1/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A2/primary/wp_s` | `22.933333333333334` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A2/primary/correct` | `77.00636666666666` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A2/primary/visible` | `199.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A2/primary/lost_s` | `1.4666666666666668` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A2/primary/false_lock_s` | `0.4000000000000001` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A2/dp_majority` | `[true, true, true, true, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A3/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A3/primary/wp_s` | `8.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A3/primary/correct` | `149.33623333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A3/primary/visible` | `199.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A3/primary/lost_s` | `1.9333333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A3/primary/false_lock_s` | `0.4000000000000001` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A3/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A3/dp_majority` | `[true, true, true, true, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;A3/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/primary/wp_s` | `11.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/primary/correct` | `135.66493333333332` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/primary/visible` | `199.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/primary/lost_s` | `1.6666666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/primary/false_lock_s` | `0.26666666666666666` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/dp_majority` | `[false, false, false, false, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/calls` | `24` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/applied` | `24` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/valid_calls` | `24` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/answer_counts/SELECT` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/answer_counts/OWN_BOX` | `2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/calls` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/applied` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/valid_calls` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/answer_counts/SELECT` | `19` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/calls` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/applied` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/valid_calls` | `22` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/answer_counts/SELECT` | `19` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C2&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B1/primary/wp_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B1/primary/correct` | `199.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B1/primary/visible` | `199.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B1/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B1/primary/false_lock_s` | `0.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B1/dp_majority` | `[true, true, true, true, true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B2/primary/wp_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B2/primary/correct` | `199.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B2/primary/visible` | `199.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B2/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B2/primary/false_lock_s` | `0.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B2/dp_majority` | `[true, true, true, true, true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A1/primary/wp_s` | `1.2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A1/primary/correct` | `230.99706666666665` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A1/primary/visible` | `242.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A1/primary/lost_s` | `1.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A1/primary/false_lock_s` | `1.9333333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A1/dp_majority` | `[true, false, true, true, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A2/primary/wp_s` | `3.866666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A2/primary/correct` | `218.00166666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A2/primary/visible` | `242.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A2/primary/lost_s` | `0.9333333333333332` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A2/primary/false_lock_s` | `2.2666666666666666` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A2/dp_majority` | `[true, false, true, true, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A3/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A3/primary/wp_s` | `1.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A3/primary/correct` | `235.00619999999995` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A3/primary/visible` | `242.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A3/primary/lost_s` | `0.4000000000000001` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A3/primary/false_lock_s` | `0.20000000000000004` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A3/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A3/dp_majority` | `[true, true, true, true, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;A3/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/primary/wp_s` | `7.8` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/primary/correct` | `186.99339999999998` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/primary/visible` | `242.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/primary/lost_s` | `3.2000000000000006` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/primary/false_lock_s` | `2.7999999999999994` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/calls` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/applied` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/valid_calls` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/answer_counts/SELECT` | `29` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/answer_counts/OWN_BOX` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/calls` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/applied` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/valid_calls` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/answer_counts/SELECT` | `29` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/calls` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/applied` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/valid_calls` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/answer_counts/SELECT` | `29` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D1&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B1/primary/wp_s` | `1.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B1/primary/correct` | `235.00619999999998` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B1/primary/visible` | `242.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B1/primary/lost_s` | `0.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B1/primary/false_lock_s` | `0.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B1/dp_majority` | `[true, true, true, true, true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B2/primary/wp_s` | `1.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B2/primary/correct` | `235.00619999999998` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B2/primary/visible` | `242.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B2/primary/lost_s` | `0.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B2/primary/false_lock_s` | `0.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B2/dp_majority` | `[true, true, true, true, true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A1/primary/wp_s` | `18.46666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A1/primary/correct` | `60.004999999999995` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A1/primary/visible` | `165.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A1/primary/lost_s` | `2.533333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A1/primary/false_lock_s` | `8.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A1/dp_majority` | `[true, true, true, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A2/primary/wp_s` | `16.133333333333336` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A2/primary/correct` | `72.336` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A2/primary/visible` | `165.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A2/primary/lost_s` | `2.4` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A2/primary/false_lock_s` | `8.266666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A2/dp_majority` | `[true, true, true, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A3/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A3/primary/wp_s` | `3.6` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A3/primary/correct` | `146.9985` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A3/primary/visible` | `165.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A3/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A3/primary/false_lock_s` | `7.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A3/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A3/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;A3/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/primary/wp_s` | `15.466666666666669` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/primary/correct` | `77.66550000000001` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/primary/visible` | `165.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/primary/lost_s` | `2.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/primary/false_lock_s` | `9.466666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/dp_majority` | `[false, false, false, false, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/calls` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/applied` | `29` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/valid_calls` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/answer_counts/SELECT` | `25` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/answer_counts/OWN_BOX` | `2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/answer_counts/NOT_VISIBLE` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/calls` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/applied` | `29` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/valid_calls` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/answer_counts/SELECT` | `23` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `4` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/answer_counts/NOT_VISIBLE` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/calls` | `31` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/applied` | `30` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/valid_calls` | `31` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/answer_counts/SELECT` | `25` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/answer_counts/NOT_VISIBLE` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-D2&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B1/primary/wp_s` | `3.6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B1/primary/correct` | `146.9985` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B1/primary/visible` | `165.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B1/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B1/primary/false_lock_s` | `7.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B1/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B2/primary/wp_s` | `3.6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B2/primary/correct` | `146.9985` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B2/primary/visible` | `165.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B2/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B2/primary/false_lock_s` | `7.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B2/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A1/primary/wp_s` | `7.3999999999999995` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A1/primary/correct` | `250.66896666666665` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A1/primary/visible` | `289.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A1/primary/lost_s` | `0.26666666666666666` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A1/primary/false_lock_s` | `19.599999999999998` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A1/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A2/primary/wp_s` | `6.066666666666666` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A2/primary/correct` | `257.6724` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A2/primary/visible` | `289.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A2/primary/lost_s` | `0.20000000000000004` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A2/primary/false_lock_s` | `19.933333333333334` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A2/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/primary/wp_s` | `13.466666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/primary/correct` | `200.3348` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/primary/visible` | `289.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/primary/lost_s` | `4.266666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/primary/false_lock_s` | `20.333333333333332` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/dp_majority` | `[false, true, false, false, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/calls` | `54` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/applied` | `54` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/valid_calls` | `54` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/answer_counts/SELECT` | `44` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/answer_counts/OWN_BOX` | `5` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/answer_counts/NOT_VISIBLE` | `5` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/calls` | `56` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/applied` | `55` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/valid_calls` | `56` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/answer_counts/SELECT` | `45` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `5` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/answer_counts/NOT_VISIBLE` | `5` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/answer_counts/UNCERTAIN` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/calls` | `55` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/applied` | `54` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/valid_calls` | `55` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/answer_counts/SELECT` | `45` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/answer_counts/NOT_VISIBLE` | `6` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/answer_counts/UNCERTAIN` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B3&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B1/primary/wp_s` | `6.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B1/primary/correct` | `230.9977` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B1/primary/visible` | `289.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B1/primary/lost_s` | `5.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B1/primary/false_lock_s` | `13.6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B1/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B2/primary/wp_s` | `6.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B2/primary/correct` | `230.9977` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B2/primary/visible` | `289.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B2/primary/lost_s` | `5.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B2/primary/false_lock_s` | `13.6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B2/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A1/primary/wp_s` | `17.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A1/primary/correct` | `258.00066666666663` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A1/primary/visible` | `346.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A1/primary/lost_s` | `0.6` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A1/primary/false_lock_s` | `21.400000000000002` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A1/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A2/primary/wp_s` | `15.133333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A2/primary/correct` | `267.3311333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A2/primary/visible` | `346.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A2/primary/lost_s` | `0.6` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A2/primary/false_lock_s` | `21.400000000000002` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A2/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/primary/wp_s` | `16.066666666666666` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/primary/correct` | `252.3378` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/primary/visible` | `346.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/primary/lost_s` | `2.6666666666666665` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/primary/false_lock_s` | `22.733333333333334` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/calls` | `58` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/applied` | `58` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/valid_calls` | `58` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/answer_counts/SELECT` | `47` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/answer_counts/OWN_BOX` | `6` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/answer_counts/NOT_VISIBLE` | `5` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/calls` | `59` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/applied` | `59` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/valid_calls` | `59` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/answer_counts/SELECT` | `49` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `5` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/answer_counts/NOT_VISIBLE` | `5` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/calls` | `58` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/applied` | `58` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/valid_calls` | `58` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/answer_counts/SELECT` | `47` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `5` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/answer_counts/NOT_VISIBLE` | `6` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B4&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B1/primary/wp_s` | `12.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B1/primary/correct` | `219.98680000000002` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B1/primary/visible` | `346.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B1/primary/lost_s` | `13.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B1/primary/false_lock_s` | `14.8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B1/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B2/primary/wp_s` | `12.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B2/primary/correct` | `219.98680000000002` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B2/primary/visible` | `346.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B2/primary/lost_s` | `13.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B2/primary/false_lock_s` | `14.8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B2/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A1/primary/wp_s` | `9.6` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A1/primary/correct` | `268.33216666666664` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A1/primary/visible` | `319.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A1/primary/lost_s` | `0.5333333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A1/primary/false_lock_s` | `19.599999999999998` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A1/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A2/primary/wp_s` | `9.333333333333334` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A2/primary/correct` | `272.3303` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A2/primary/visible` | `319.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A2/primary/lost_s` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A2/primary/false_lock_s` | `20.8` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A2/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/primary/wp_s` | `18.133333333333336` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/primary/correct` | `214.3467333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/primary/visible` | `319.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/primary/lost_s` | `2.8000000000000003` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/primary/false_lock_s` | `21.53333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/calls` | `56` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/applied` | `56` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/valid_calls` | `56` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/answer_counts/SELECT` | `48` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/answer_counts/NOT_VISIBLE` | `5` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/answer_counts/OWN_BOX` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/calls` | `56` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/applied` | `55` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/valid_calls` | `56` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/answer_counts/SELECT` | `48` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/answer_counts/NOT_VISIBLE` | `5` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/answer_counts/UNCERTAIN` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/calls` | `55` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/applied` | `55` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/valid_calls` | `55` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/answer_counts/SELECT` | `47` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/answer_counts/NOT_VISIBLE` | `5` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-B5&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B1/primary/wp_s` | `8.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B1/primary/correct` | `235.99620000000002` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B1/primary/visible` | `319.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B1/primary/lost_s` | `8.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B1/primary/false_lock_s` | `19.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B1/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B2/primary/wp_s` | `8.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B2/primary/correct` | `235.99620000000002` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B2/primary/visible` | `319.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B2/primary/lost_s` | `8.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B2/primary/false_lock_s` | `19.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B2/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A1/primary/wp_s` | `26.46666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A1/primary/correct` | `147.66716666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A1/primary/visible` | `295.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A1/primary/lost_s` | `3.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A1/primary/false_lock_s` | `20.466666666666665` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A1/dp_majority` | `[false, true, false, false, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A2/primary/wp_s` | `28.53333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A2/primary/correct` | `132.67133333333334` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A2/primary/visible` | `295.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A2/primary/lost_s` | `3.9333333333333336` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A2/primary/false_lock_s` | `19.8` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A2/dp_majority` | `[false, true, false, false, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/primary/wp_s` | `25.400000000000002` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/primary/correct` | `147.33283333333335` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/primary/visible` | `295.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/primary/lost_s` | `4.133333333333334` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/primary/false_lock_s` | `21.066666666666666` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/calls` | `49` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/applied` | `48` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/valid_calls` | `49` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/answer_counts/SELECT` | `44` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/answer_counts/OWN_BOX` | `5` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/calls` | `49` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/applied` | `49` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/valid_calls` | `49` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/answer_counts/SELECT` | `46` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/calls` | `48` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/applied` | `47` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/valid_calls` | `48` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/answer_counts/SELECT` | `45` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C3&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B1/primary/wp_s` | `11.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B1/primary/correct` | `202.98950000000002` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B1/primary/visible` | `295.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B1/primary/lost_s` | `7.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B1/primary/false_lock_s` | `13.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B1/dp_majority` | `[false, true, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B2/primary/wp_s` | `11.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B2/primary/correct` | `202.98950000000002` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B2/primary/visible` | `295.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B2/primary/lost_s` | `7.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B2/primary/false_lock_s` | `13.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B2/dp_majority` | `[false, true, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A1/primary/wp_s` | `31.599999999999998` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A1/primary/correct` | `166.00639999999999` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A1/primary/visible` | `336.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A1/primary/lost_s` | `2.4` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A1/primary/false_lock_s` | `19.6` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A1/dp_majority` | `[false, false, false, false, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A2/primary/wp_s` | `32.93333333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A2/primary/correct` | `155.3328` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A2/primary/visible` | `336.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A2/primary/lost_s` | `3.2000000000000006` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A2/primary/false_lock_s` | `19.733333333333334` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A2/dp_majority` | `[false, false, false, false, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/primary/wp_s` | `29.599999999999998` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/primary/correct` | `167.3392` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/primary/visible` | `336.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/primary/lost_s` | `4.133333333333334` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/primary/false_lock_s` | `20.333333333333332` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/calls` | `53` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/applied` | `53` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/valid_calls` | `53` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/answer_counts/SELECT` | `49` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/answer_counts/OWN_BOX` | `2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/answer_counts/NOT_VISIBLE` | `2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/calls` | `55` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/applied` | `55` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/valid_calls` | `55` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/answer_counts/SELECT` | `50` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `4` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/answer_counts/NOT_VISIBLE` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/calls` | `52` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/applied` | `52` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/valid_calls` | `52` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/answer_counts/SELECT` | `49` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/answer_counts/NOT_VISIBLE` | `2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C4&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B1/primary/wp_s` | `10.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B1/primary/correct` | `225.9936` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B1/primary/visible` | `336.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B1/primary/lost_s` | `12.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B1/primary/false_lock_s` | `12.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B1/dp_majority` | `[true, true, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B2/primary/wp_s` | `10.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B2/primary/correct` | `225.9936` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B2/primary/visible` | `336.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B2/primary/lost_s` | `12.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B2/primary/false_lock_s` | `12.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B2/dp_majority` | `[true, true, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A1/primary/wp_s` | `32.6` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A1/primary/correct` | `154.0143` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A1/primary/visible` | `331.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A1/primary/lost_s` | `2.8000000000000003` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A1/primary/false_lock_s` | `18.4` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A1/dp_majority` | `[false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A2/primary/wp_s` | `30.46666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A2/primary/correct` | `162.0024333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A2/primary/visible` | `331.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A2/primary/lost_s` | `3.3333333333333335` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A2/primary/false_lock_s` | `18.4` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A2/dp_majority` | `[false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/primary/wp_s` | `27.2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/primary/correct` | `171.66763333333333` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/primary/visible` | `331.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/primary/lost_s` | `4.666666666666667` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/primary/false_lock_s` | `20.933333333333334` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/dp_majority` | `[false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/calls` | `53` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/applied` | `53` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/valid_calls` | `53` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/answer_counts/SELECT` | `51` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/answer_counts/NOT_VISIBLE` | `2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/calls` | `57` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/applied` | `57` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/valid_calls` | `57` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/answer_counts/SELECT` | `52` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/answer_counts/NOT_VISIBLE` | `2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/calls` | `53` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/applied` | `52` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/valid_calls` | `53` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/answer_counts/SELECT` | `48` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/answer_counts/UNCERTAIN` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/answer_counts/NOT_VISIBLE` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C5&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B1/primary/wp_s` | `11.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B1/primary/correct` | `214.9845` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B1/primary/visible` | `331.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B1/primary/lost_s` | `12.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B1/primary/false_lock_s` | `11.8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B1/dp_majority` | `[true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B2/primary/wp_s` | `11.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B2/primary/correct` | `214.9845` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B2/primary/visible` | `331.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B2/primary/lost_s` | `12.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B2/primary/false_lock_s` | `11.8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B2/dp_majority` | `[true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;A1/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A1/primary/wp_s` | `27.933333333333334` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A1/primary/correct` | `123.33` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A1/primary/visible` | `300.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A1/primary/lost_s` | `7.400000000000001` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A1/primary/false_lock_s` | `20.2` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A1/dp_majority` | `[false, true, false, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A2/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A2/primary/wp_s` | `29.399999999999995` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A2/primary/correct` | `116.00999999999999` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A2/primary/visible` | `300.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A2/primary/lost_s` | `7.400000000000001` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A2/primary/false_lock_s` | `19.6` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A2/dp_majority` | `[false, true, false, true]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;A2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/k` | `3` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/primary/wp_s` | `29.066666666666666` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/primary/correct` | `135.01` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/primary/visible` | `300.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/primary/lost_s` | `3.9333333333333336` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/primary/false_lock_s` | `20.133333333333336` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/dp_majority` | `[false, false, false, false]` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/calls` | `48` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/applied` | `48` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/valid_calls` | `48` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/answer_counts/SELECT` | `43` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/answer_counts/OWN_BOX` | `4` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/answer_counts/NOT_VISIBLE` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/calls` | `50` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/applied` | `50` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/valid_calls` | `50` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/answer_counts/SELECT` | `43` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/answer_counts/OWN_BOX` | `7` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/1/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/calls` | `49` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/expired` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/applied` | `48` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/valid_calls` | `49` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/answer_counts/SELECT` | `40` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/answer_counts/OWN_BOX` | `7` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/answer_counts/NOT_VISIBLE` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/answer_counts/UNCERTAIN` | `1` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;AO/e5_calls/2/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=3 |
| `/per_case/E3-C6&#124;B1/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B1/primary/wp_s` | `10.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B1/primary/correct` | `215.01` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B1/primary/visible` | `300.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B1/primary/lost_s` | `7.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B1/primary/false_lock_s` | `12.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B1/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B1/dp_majority` | `[true, true, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B1/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B2/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B2/primary/wp_s` | `10.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B2/primary/correct` | `215.01` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B2/primary/visible` | `300.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B2/primary/lost_s` | `7.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B2/primary/false_lock_s` | `12.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B2/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B2/dp_majority` | `[true, true, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;B2/e5_calls` | `null` | `UNKNOWN（來源未提供）` | k=1 |
| `/verdicts/H8a/reasons/follow_lower` | `-0.19993455295027052` | `UNKNOWN（來源未提供）` | UNKNOWN（來源未提供） |
| `/verdicts/H8a/reasons/follow_upper` | `-0.0032536185558561526` | `UNKNOWN（來源未提供）` | UNKNOWN（來源未提供） |
| `/verdicts/H8a/reasons/mcnemar_p` | `0.0191572904586792` | `UNKNOWN（來源未提供）` | UNKNOWN（來源未提供） |
| `/verdicts/H8a/n_points` | `68` | `UNKNOWN（來源未提供）` | UNKNOWN（來源未提供） |
| `/verdicts/H8a/n_segments` | `16` | `UNKNOWN（來源未提供）` | UNKNOWN（來源未提供） |
| `/verdicts/H8b/reasons/ci` | `[39.73333333333333, 91.26666666666667]` | `UNKNOWN（來源未提供）` | UNKNOWN（來源未提供） |
| `/verdicts/H8c/reasons/top1_diff_ci` | `[-0.15740740740740738, 0.1724137931034483]` | `UNKNOWN（來源未提供）` | UNKNOWN（來源未提供） |
| `/verdicts/H8c/reasons/ao_top1` | `0.3063` | `UNKNOWN（來源未提供）` | UNKNOWN（來源未提供） |
| `/verdicts/H8c/reasons/random_top1` | `0.125` | `UNKNOWN（來源未提供）` | UNKNOWN（來源未提供） |
| `/verdicts/H8c/denominator/AO_points` | `111` | `UNKNOWN（來源未提供）` | UNKNOWN（來源未提供） |
| `/verdicts/H8c/denominator/B1_points` | `37` | `UNKNOWN（來源未提供）` | UNKNOWN（來源未提供） |

## 4. S2 逐段衍生指標（已存在的評分輸出，原樣）

S2「逐段」表已含每段跟對率與決策點對／總數；本次直接複製整個表，不用 S1 的 correct／visible 或 dp_majority 重新算。來源沒有逐段95% CI。

| 段 | 組 | K | 錯人秒 | 跟對率 | 失聯秒 | 盲區誤鎖秒 | 決策點對（多數決） | CALL_CAP_REACHED（各次合計） |
|---|---|---|---|---|---|---|---|---|
| E3-A1 | A1 | 3 | 9.40 | 0.756 | 3.80 | 0.00 | 1/5 | — |
| E3-A1 | A2 | 3 | 8.07 | 0.804 | 2.53 | 0.00 | 1/5 | — |
| E3-A1 | A3 | 3 | 8.60 | 0.756 | 4.60 | 0.00 | 2/5 | — |
| E3-A1 | AO | 3 | 6.73 | 0.812 | 3.47 | 0.00 | 5/5 | 0 |
| E3-A1 | B1 | 1 | 11.80 | 0.631 | 8.20 | 0.00 | 1/5 | — |
| E3-A1 | B2 | 1 | 11.80 | 0.631 | 8.20 | 0.00 | 1/5 | — |
| E3-A2 | A1 | 3 | 22.80 | 0.353 | 3.20 | 0.00 | 1/5 | — |
| E3-A2 | A2 | 3 | 22.33 | 0.365 | 3.20 | 0.00 | 1/5 | — |
| E3-A2 | A3 | 3 | 0.20 | 0.935 | 2.40 | 0.00 | 4/5 | — |
| E3-A2 | AO | 3 | 15.40 | 0.584 | 1.33 | 0.00 | 1/5 | 0 |
| E3-A2 | B1 | 1 | 0.20 | 0.935 | 2.40 | 0.00 | 4/5 | — |
| E3-A2 | B2 | 1 | 0.20 | 0.935 | 2.40 | 0.00 | 4/5 | — |
| E3-A3 | A1 | 3 | 5.20 | 0.800 | 0.00 | 0.00 | 4/5 | — |
| E3-A3 | A2 | 3 | 5.60 | 0.785 | 0.00 | 0.00 | 4/5 | — |
| E3-A3 | A3 | 3 | 0.00 | 1.000 | 0.00 | 0.00 | 5/5 | — |
| E3-A3 | AO | 3 | 0.00 | 0.992 | 0.20 | 0.00 | 5/5 | 0 |
| E3-A3 | B1 | 1 | 0.00 | 1.000 | 0.00 | 0.00 | 5/5 | — |
| E3-A3 | B2 | 1 | 0.00 | 1.000 | 0.00 | 0.00 | 5/5 | — |
| E3-B1 | A1 | 3 | 3.20 | 0.912 | 0.40 | 9.00 | 0/2 | — |
| E3-B1 | A2 | 3 | 2.40 | 0.935 | 0.40 | 9.00 | 0/2 | — |
| E3-B1 | A3 | 3 | 3.20 | 0.921 | 0.00 | 4.80 | 1/2 | — |
| E3-B1 | AO | 3 | 6.93 | 0.781 | 2.53 | 7.93 | 0/2 | 0 |
| E3-B1 | B1 | 1 | 3.20 | 0.921 | 0.00 | 4.80 | 1/2 | — |
| E3-B1 | B2 | 1 | 3.20 | 0.921 | 0.00 | 4.80 | 1/2 | — |
| E3-B2 | A1 | 3 | 4.47 | 0.884 | 0.00 | 6.87 | 0/1 | — |
| E3-B2 | A2 | 3 | 3.60 | 0.907 | 0.00 | 7.40 | 0/1 | — |
| E3-B2 | A3 | 3 | 2.53 | 0.934 | 0.00 | 1.20 | 1/1 | — |
| E3-B2 | AO | 3 | 10.27 | 0.703 | 1.20 | 6.33 | 0/1 | 0 |
| E3-B2 | B1 | 1 | 0.00 | 1.000 | 0.00 | 0.20 | 1/1 | — |
| E3-B2 | B2 | 1 | 0.00 | 1.000 | 0.00 | 0.20 | 1/1 | — |
| E3-C1 | A1 | 3 | 12.53 | 0.733 | 3.20 | 0.60 | 2/5 | — |
| E3-C1 | A2 | 3 | 7.00 | 0.827 | 3.20 | 0.60 | 2/5 | — |
| E3-C1 | A3 | 3 | 22.20 | 0.490 | 7.87 | 0.00 | 0/5 | — |
| E3-C1 | AO | 3 | 10.53 | 0.780 | 2.47 | 1.00 | 0/5 | 0 |
| E3-C1 | B1 | 1 | 25.20 | 0.420 | 9.00 | 0.00 | 0/5 | — |
| E3-C1 | B2 | 1 | 25.20 | 0.420 | 9.00 | 0.00 | 0/5 | — |
| E3-C2 | A1 | 3 | 29.27 | 0.194 | 2.80 | 0.40 | 0/5 | — |
| E3-C2 | A2 | 3 | 22.93 | 0.387 | 1.47 | 0.40 | 5/5 | — |
| E3-C2 | A3 | 3 | 8.00 | 0.750 | 1.93 | 0.40 | 5/5 | — |
| E3-C2 | AO | 3 | 11.00 | 0.682 | 1.67 | 0.27 | 1/5 | 0 |
| E3-C2 | B1 | 1 | 0.00 | 1.000 | 0.00 | 0.40 | 5/5 | — |
| E3-C2 | B2 | 1 | 0.00 | 1.000 | 0.00 | 0.40 | 5/5 | — |
| E3-D1 | A1 | 3 | 1.20 | 0.955 | 1.00 | 1.93 | 4/5 | — |
| E3-D1 | A2 | 3 | 3.87 | 0.901 | 0.93 | 2.27 | 4/5 | — |
| E3-D1 | A3 | 3 | 1.00 | 0.971 | 0.40 | 0.20 | 5/5 | — |
| E3-D1 | AO | 3 | 7.80 | 0.773 | 3.20 | 2.80 | 0/5 | 0 |
| E3-D1 | B1 | 1 | 1.00 | 0.971 | 0.40 | 0.20 | 5/5 | — |
| E3-D1 | B2 | 1 | 1.00 | 0.971 | 0.40 | 0.20 | 5/5 | — |
| E3-D2 | A1 | 3 | 18.47 | 0.364 | 2.53 | 8.00 | 3/5 | — |
| E3-D2 | A2 | 3 | 16.13 | 0.438 | 2.40 | 8.27 | 3/5 | — |
| E3-D2 | A3 | 3 | 3.60 | 0.891 | 0.00 | 7.00 | 0/5 | — |
| E3-D2 | AO | 3 | 15.47 | 0.471 | 2.00 | 9.47 | 1/5 | 0 |
| E3-D2 | B1 | 1 | 3.60 | 0.891 | 0.00 | 7.00 | 0/5 | — |
| E3-D2 | B2 | 1 | 3.60 | 0.891 | 0.00 | 7.00 | 0/5 | — |
| E3-B3 | A1 | 3 | 7.40 | 0.867 | 0.27 | 19.60 | 0/5 | — |
| E3-B3 | A2 | 3 | 6.07 | 0.892 | 0.20 | 19.93 | 0/5 | — |
| E3-B3 | AO | 3 | 13.47 | 0.693 | 4.27 | 20.33 | 2/5 | 0 |
| E3-B3 | B1 | 1 | 6.40 | 0.799 | 5.20 | 13.60 | 0/5 | — |
| E3-B3 | B2 | 1 | 6.40 | 0.799 | 5.20 | 13.60 | 0/5 | — |
| E3-B4 | A1 | 3 | 17.00 | 0.746 | 0.60 | 21.40 | 0/5 | — |
| E3-B4 | A2 | 3 | 15.13 | 0.773 | 0.60 | 21.40 | 0/5 | — |
| E3-B4 | AO | 3 | 16.07 | 0.729 | 2.67 | 22.73 | 0/5 | 0 |
| E3-B4 | B1 | 1 | 12.00 | 0.636 | 13.20 | 14.80 | 0/5 | — |
| E3-B4 | B2 | 1 | 12.00 | 0.636 | 13.20 | 14.80 | 0/5 | — |
| E3-B5 | A1 | 3 | 9.60 | 0.841 | 0.53 | 19.60 | 0/5 | — |
| E3-B5 | A2 | 3 | 9.33 | 0.854 | 0.00 | 20.80 | 0/5 | — |
| E3-B5 | AO | 3 | 18.13 | 0.672 | 2.80 | 21.53 | 0/5 | 0 |
| E3-B5 | B1 | 1 | 8.20 | 0.740 | 8.40 | 19.00 | 0/5 | — |
| E3-B5 | B2 | 1 | 8.20 | 0.740 | 8.40 | 19.00 | 0/5 | — |
| E3-C3 | A1 | 3 | 26.47 | 0.501 | 3.00 | 20.47 | 2/5 | — |
| E3-C3 | A2 | 3 | 28.53 | 0.450 | 3.93 | 19.80 | 2/5 | — |
| E3-C3 | AO | 3 | 25.40 | 0.499 | 4.13 | 21.07 | 0/5 | 0 |
| E3-C3 | B1 | 1 | 11.40 | 0.688 | 7.00 | 13.20 | 1/5 | — |
| E3-C3 | B2 | 1 | 11.40 | 0.688 | 7.00 | 13.20 | 1/5 | — |
| E3-C4 | A1 | 3 | 31.60 | 0.494 | 2.40 | 19.60 | 1/5 | — |
| E3-C4 | A2 | 3 | 32.93 | 0.462 | 3.20 | 19.73 | 1/5 | — |
| E3-C4 | AO | 3 | 29.60 | 0.498 | 4.13 | 20.33 | 0/5 | 0 |
| E3-C4 | B1 | 1 | 10.00 | 0.673 | 12.00 | 12.00 | 2/5 | — |
| E3-C4 | B2 | 1 | 10.00 | 0.673 | 12.00 | 12.00 | 2/5 | — |
| E3-C5 | A1 | 3 | 32.60 | 0.465 | 2.80 | 18.40 | 0/1 | — |
| E3-C5 | A2 | 3 | 30.47 | 0.489 | 3.33 | 18.40 | 0/1 | — |
| E3-C5 | AO | 3 | 27.20 | 0.519 | 4.67 | 20.93 | 0/1 | 0 |
| E3-C5 | B1 | 1 | 11.00 | 0.649 | 12.20 | 11.80 | 1/1 | — |
| E3-C5 | B2 | 1 | 11.00 | 0.649 | 12.20 | 11.80 | 1/1 | — |
| E3-C6 | A1 | 3 | 27.93 | 0.411 | 7.40 | 20.20 | 2/4 | — |
| E3-C6 | A2 | 3 | 29.40 | 0.387 | 7.40 | 19.60 | 2/4 | — |
| E3-C6 | AO | 3 | 29.07 | 0.450 | 3.93 | 20.13 | 0/4 | 0 |
| E3-C6 | B1 | 1 | 10.00 | 0.717 | 7.00 | 12.40 | 2/4 | — |
| E3-C6 | B2 | 1 | 10.00 | 0.717 | 7.00 | 12.40 | 2/4 | — |

## 5. 費用：帳本上界

來源 S3 §5；#698 的費用欄明示「帳本值（未計快取折扣的上界）」。以下直接照抄，實際估算約 USD 7.5；估算範圍不是95% CI。

| 項目 | 估算（dry-run） | 帳本值（ApiGuard `est_cost_usd`，未計快取折扣的上界） |
|---|---|---|
| 試跑 | 0.4223 | 0.312（30 次） |
| AO 正式，行程 p1（9 段：A1–A3、B1、B2、C1、C2、D1、D2；上限 10.2） | 9.887（9 段合計） | 7.522（725 次） |
| AO 正式，行程 p2（B3、B4、B5、C3；上限 8.6） | 14.555（7 段合計，含 p3） | 6.757（653 次） |
| AO 正式，行程 p3（C4、C5、C6；上限 6.2） | （含在上列） | 4.853（470 次） |
| 正式合計（上限 25） | 24.44 | **19.132**（帳本上界；1848 次，平均 0.01035／次） |


AO 的實際花費估算約 USD 7.5（範圍 2.6–19.1）：用 OpenAI 帳單 2026-11-08～11-23 的 USD 35.72 反推輸入快取命中約 70% 得到，無法由帳單單獨驗證。

S1 `cost_usd` 本身維持原始 UNKNOWN，不以S3費用回填。CI與逐段費用若未提供則UNKNOWN。

## 6. AO-L 補充（2026-11-24；新增來源 S4–S6，舊來源 S1–S3 不改）

AO-L ＝ 模擬即時，K=1，預登記 H8d。以下只摘錄 S4（新 `report.json`）、S5（新 `report-skeleton.md`）中 AO-L 的欄位與 S6 §9 的文字；不重算、不四捨五入。已逐欄比對：S4 的 `per_arm` A1／A2／A3／AO／B1／B2、這些組別的 `per_case`、`comparisons`（AO-B1 四個鍵、B2-B1）、`verdicts` H8a／H8b／H8c 與 `stop`，和 S1 完全相同。唯一不同：`/verdicts/H8d`（S1：`verdict`＝`UNKNOWN`、`reasons`＝`{reason: NOT_RUN}`、`note`＝`未執行`；S4 見 §6.5），以及 S4 新增的 `AOL` 組別、`E3-*|AOL` 的 16 個 `per_case` 鍵與 `AOL-B1` 的比較。

### 6.1 AO-L 組別合計（S5「組別合計」，原樣）

| 組 | 段數 | 錯人秒 | 跟對率 | 失聯秒 | 盲區誤鎖秒 | 決策點對 | top-1 | top-3 | 有排名點 | 延遲 p50／p95 ms | 輸入／輸出 token |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AOL | 16 | 110.20 | 0.248 | 510.60 | 31.80 | 6/68 | 6/37 | 18/37 | 36 | 4784／10524 | 1750652／37076 |
| B1 | 16 | 114.00 | 0.759 | 85.00 | 109.40 | 28/68 | 11/37 | 25/37 | 36 | —／— | 0／0 |

### 6.2 AO-L 呼叫分類（S5「呼叫分類（契約 §7）」，原樣）

| 組 | 呼叫 | 有效 | 套用 | provider 錯誤（逾時／其他） | 錯誤率 | 格式退回 | 退回率 | 預算拒絕 | EXPIRED | OCCLUDED_NO_TARGET | CALL_CAP_REACHED | 回答分佈 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AOL | 186 | 186 | 72 | 0（0／0） | 0.0000 | 0 | 0.0000 | 0 | 98 | 0 | 0 | {"SELECT": 176, "OWN_BOX": 4, "UNCERTAIN": 1, "NOT_VISIBLE": 5} |

### 6.3 AO-L 逐段（S5「逐段」中 AOL 與 B1 的列，原樣；來源沒有逐段 95% CI）

| 段 | 組 | K | 錯人秒 | 跟對率 | 失聯秒 | 盲區誤鎖秒 | 決策點對（多數決） | CALL_CAP_REACHED（各次合計） |
|---|---|---|---|---|---|---|---|---|
| E3-A1 | AOL | 1 | 0.20 | 0.435 | 30.40 | 0.00 | 1/5 | 0 |
| E3-A1 | B1 | 1 | 11.80 | 0.631 | 8.20 | 0.00 | 1/5 | — |
| E3-A2 | AOL | 1 | 0.20 | 0.144 | 34.20 | 0.00 | 0/5 | 0 |
| E3-A2 | B1 | 1 | 0.20 | 0.935 | 2.40 | 0.00 | 4/5 | — |
| E3-A3 | AOL | 1 | 0.00 | 0.800 | 5.20 | 0.00 | 5/5 | 0 |
| E3-A3 | B1 | 1 | 0.00 | 1.000 | 0.00 | 0.00 | 5/5 | — |
| E3-B1 | AOL | 1 | 0.20 | 0.426 | 24.60 | 0.00 | 0/2 | 0 |
| E3-B1 | B1 | 1 | 3.20 | 0.921 | 0.00 | 4.80 | 1/2 | — |
| E3-B2 | AOL | 1 | 0.20 | 0.466 | 20.40 | 0.00 | 0/1 | 0 |
| E3-B2 | B1 | 1 | 0.00 | 1.000 | 0.00 | 0.20 | 1/1 | — |
| E3-C1 | AOL | 1 | 4.60 | 0.048 | 51.60 | 0.00 | 0/5 | 0 |
| E3-C1 | B1 | 1 | 25.20 | 0.420 | 9.00 | 0.00 | 0/5 | — |
| E3-C2 | AOL | 1 | 0.00 | 0.000 | 39.80 | 0.00 | 0/5 | 0 |
| E3-C2 | B1 | 1 | 0.00 | 1.000 | 0.00 | 0.40 | 5/5 | — |
| E3-D1 | AOL | 1 | 0.20 | 0.380 | 29.80 | 0.00 | 0/5 | 0 |
| E3-D1 | B1 | 1 | 1.00 | 0.971 | 0.40 | 0.20 | 5/5 | — |
| E3-D2 | AOL | 1 | 15.60 | 0.042 | 16.00 | 0.00 | 0/5 | 0 |
| E3-D2 | B1 | 1 | 3.60 | 0.891 | 0.00 | 7.00 | 0/5 | — |
| E3-B3 | AOL | 1 | 0.20 | 0.329 | 38.60 | 0.00 | 0/5 | 0 |
| E3-B3 | B1 | 1 | 6.40 | 0.799 | 5.20 | 13.60 | 0/5 | — |
| E3-B4 | AOL | 1 | 7.20 | 0.355 | 37.40 | 0.80 | 0/5 | 0 |
| E3-B4 | B1 | 1 | 12.00 | 0.636 | 13.20 | 14.80 | 0/5 | — |
| E3-B5 | AOL | 1 | 3.60 | 0.382 | 35.80 | 1.80 | 0/5 | 0 |
| E3-B5 | B1 | 1 | 8.20 | 0.740 | 8.40 | 19.00 | 0/5 | — |
| E3-C3 | AOL | 1 | 27.60 | 0.010 | 30.80 | 8.60 | 0/5 | 0 |
| E3-C3 | B1 | 1 | 11.40 | 0.688 | 7.00 | 13.20 | 1/5 | — |
| E3-C4 | AOL | 1 | 19.40 | 0.196 | 34.60 | 11.00 | 0/5 | 0 |
| E3-C4 | B1 | 1 | 10.00 | 0.673 | 12.00 | 12.00 | 2/5 | — |
| E3-C5 | AOL | 1 | 10.00 | 0.199 | 43.00 | 5.40 | 0/1 | 0 |
| E3-C5 | B1 | 1 | 11.00 | 0.649 | 12.20 | 11.80 | 1/1 | — |
| E3-C6 | AOL | 1 | 21.00 | 0.010 | 38.40 | 4.20 | 0/4 | 0 |
| E3-C6 | B1 | 1 | 10.00 | 0.717 | 7.00 | 12.40 | 2/4 | — |

### 6.4 S4 `per_arm/AOL`、`per_case`（AOL）原始欄位

| JSON pointer（S4） | 點估計／原值 | 95% CI（原值） | 樣本數／K（原欄位） |
|---|---|---|---|
| `/per_arm/AOL/segments` | `[E3-A1, E3-A2, E3-A3, E3-B1, E3-B2, E3-C1, E3-C2, E3-D1, E3-D2, E3-B3, E3-B4, E3-B5, E3-C3, E3-C4, E3-C5, E3-C6]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/wrong_person_s` | `110.2` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/follow_rate` | `0.2481` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/lost_s` | `510.6` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/false_lock_s` | `31.8` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/dp_correct` | `6` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/dp_total` | `68` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/top1` | `[6, 37]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/top3` | `[18, 37]` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/random_top1` | `0.125` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/ranked_points` | `36` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/latency_ms_p50` | `4784` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/latency_ms_p95` | `10524` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/input_tokens` | `1750652` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/output_tokens` | `37076` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/cost_usd` | `UNKNOWN (not in the run log; read the ApiGuard ledger)` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/calls` | `186` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/provider_error` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/provider_errors` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/format_rejected` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/budget_denied` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/expired` | `98` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/applied` | `72` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/valid_calls` | `186` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/answer_counts/SELECT` | `176` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/answer_counts/OWN_BOX` | `4` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/answer_counts/UNCERTAIN` | `1` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_arm/AOL/e5_calls/answer_counts/NOT_VISIBLE` | `5` | `UNKNOWN（來源未提供）` | dp_total=68 |
| `/per_case/E3-A1&#124;AOL/family` | `A` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/primary/wp_s` | `0.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/primary/correct` | `117.99340000000001` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/primary/visible` | `271.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/primary/lost_s` | `30.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/dp_majority` | `[false, false, false, false, true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/calls` | `10` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/expired` | `3` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/applied` | `6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/valid_calls` | `10` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/answer_counts/SELECT` | `10` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A1&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/family` | `A` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/primary/wp_s` | `0.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/primary/correct` | `29.0043` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/primary/visible` | `201.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/primary/lost_s` | `34.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/calls` | `6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/expired` | `4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/applied` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/valid_calls` | `6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/answer_counts/SELECT` | `4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/answer_counts/OWN_BOX` | `2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A2&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/family` | `A` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/primary/wp_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/primary/correct` | `104.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/primary/visible` | `130.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/primary/lost_s` | `5.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/dp_majority` | `[true, true, true, true, true]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/calls` | `6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/expired` | `2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/applied` | `3` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/valid_calls` | `6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/answer_counts/SELECT` | `6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-A3&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/family` | `B` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/primary/wp_s` | `0.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/primary/correct` | `91.9944` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/primary/visible` | `216.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/primary/lost_s` | `24.6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/dp_majority` | `[false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/calls` | `8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/expired` | `2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/applied` | `5` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/valid_calls` | `8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/answer_counts/SELECT` | `7` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/answer_counts/UNCERTAIN` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B1&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/family` | `B` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/primary/wp_s` | `0.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/primary/correct` | `89.99589999999999` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/primary/visible` | `193.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/primary/lost_s` | `20.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/dp_majority` | `[false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/calls` | `8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/expired` | `2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/applied` | `5` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/valid_calls` | `8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/answer_counts/SELECT` | `8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B2&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/family` | `C` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/primary/wp_s` | `4.6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/primary/correct` | `14.0125` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/primary/visible` | `295.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/primary/lost_s` | `51.6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/calls` | `10` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/expired` | `7` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/applied` | `2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/valid_calls` | `10` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/answer_counts/SELECT` | `10` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C1&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/family` | `C` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/primary/wp_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/primary/correct` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/primary/visible` | `199.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/primary/lost_s` | `39.8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/calls` | `5` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/expired` | `4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/applied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/valid_calls` | `5` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/answer_counts/SELECT` | `5` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C2&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/family` | `D` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/primary/wp_s` | `0.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/primary/correct` | `92.0084` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/primary/visible` | `242.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/primary/lost_s` | `29.8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/calls` | `12` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/expired` | `5` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/applied` | `6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/valid_calls` | `12` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/answer_counts/SELECT` | `12` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D1&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/family` | `D` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/primary/wp_s` | `15.6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/primary/correct` | `6.996` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/primary/visible` | `165.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/primary/lost_s` | `16.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/calls` | `10` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/expired` | `6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/applied` | `3` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/valid_calls` | `10` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/answer_counts/SELECT` | `9` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/answer_counts/NOT_VISIBLE` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-D2&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/family` | `B` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/primary/wp_s` | `0.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/primary/correct` | `94.9943` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/primary/visible` | `289.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/primary/lost_s` | `38.6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/primary/false_lock_s` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/calls` | `17` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/expired` | `9` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/applied` | `7` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/valid_calls` | `17` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/answer_counts/SELECT` | `15` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/answer_counts/NOT_VISIBLE` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/answer_counts/OWN_BOX` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B3&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/family` | `B` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/primary/wp_s` | `7.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/primary/correct` | `123.003` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/primary/visible` | `346.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/primary/lost_s` | `37.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/primary/false_lock_s` | `0.8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/calls` | `19` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/expired` | `7` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/applied` | `11` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/valid_calls` | `19` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/answer_counts/SELECT` | `18` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/answer_counts/NOT_VISIBLE` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B4&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/family` | `B` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/primary/wp_s` | `3.6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/primary/correct` | `121.9856` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/primary/visible` | `319.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/primary/lost_s` | `35.8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/primary/false_lock_s` | `1.8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/calls` | `17` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/expired` | `6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/applied` | `10` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/valid_calls` | `17` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/answer_counts/SELECT` | `15` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/answer_counts/NOT_VISIBLE` | `2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-B5&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/family` | `C` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/primary/wp_s` | `27.6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/primary/correct` | `3.0090000000000003` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/primary/visible` | `295.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/primary/lost_s` | `30.8` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/primary/false_lock_s` | `8.6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/calls` | `14` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/expired` | `10` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/applied` | `3` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/valid_calls` | `14` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/answer_counts/SELECT` | `14` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C3&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/family` | `C` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/primary/wp_s` | `19.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/primary/correct` | `65.9904` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/primary/visible` | `336.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/primary/lost_s` | `34.6` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/primary/false_lock_s` | `11.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/dp_majority` | `[false, false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/calls` | `16` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/expired` | `11` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/applied` | `4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/valid_calls` | `16` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/answer_counts/SELECT` | `16` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C4&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/family` | `C` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/primary/wp_s` | `10.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/primary/correct` | `66.0014` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/primary/visible` | `331.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/primary/lost_s` | `43.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/primary/false_lock_s` | `5.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/dp_majority` | `[false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/calls` | `15` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/expired` | `9` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/applied` | `5` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/valid_calls` | `15` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/answer_counts/SELECT` | `15` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C5&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/family` | `C` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/k` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/primary/wp_s` | `21.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/primary/correct` | `3.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/primary/visible` | `300.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/primary/lost_s` | `38.4` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/primary/false_lock_s` | `4.2` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/primary/gt_unknown_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/dp_majority` | `[false, false, false, false]` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/calls` | `13` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/provider_timeout` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/provider_error` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/format_rejected` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/budget_denied` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/expired` | `11` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/occluded_no_target` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/applied` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/valid_calls` | `13` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/answer_counts/SELECT` | `12` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/answer_counts/OWN_BOX` | `1` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/provider_errors` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/call_cap_reached` | `0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/provider_error_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/format_return_rate` | `0.0` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/provider_error_stop` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/format_return_flag` | `false` | `UNKNOWN（來源未提供）` | k=1 |
| `/per_case/E3-C6&#124;AOL/e5_calls/0/rerun_needed_budget` | `false` | `UNKNOWN（來源未提供）` | k=1 |

### 6.5 AO-L vs B1：全部 comparisons（H8d）與敏感度

`|topk`＝top-k 附報；`|iou_conservative`＝IoU 保守準則敏感度；`|iou` 在來源為 null。

| JSON pointer（S4） | 點估計／原值 | 95% CI（原值） | 樣本數／K（原欄位） |
|---|---|---|---|
| `/comparisons/AOL-B1/wp_diff` | `-3.8` | `[-76.2, 68.4]` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1/false_lock_diff` | `-77.6` | `[-122.39999999999999, -36.4]` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1/follow_diff` | `-0.5106` | `[-0.6165477150880776, -0.4197736739130435]` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1/mcnemar/agent_only` | `0` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1/mcnemar/baseline_only` | `22` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1/mcnemar/p` | `4.76837158203125e-07` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1/mcnemar/favours` | `baseline` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1/n_points` | `68` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1/n_segments` | `16` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1/segments` | `[E3-A1, E3-A2, E3-A3, E3-B1, E3-B2, E3-B3, E3-B4, E3-B5, E3-C1, E3-C2, E3-C3, E3-C4, E3-C5, E3-C6, E3-D1, E3-D2]` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1&#124;topk/top1_diff` | `-0.1351` | `[-0.4, 0.1111111111111111]` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1&#124;topk/x_top1` | `0.16216216216216217` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1&#124;topk/y_top1` | `0.2972972972972973` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1&#124;topk/x_top3` | `0.4864864864864865` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1&#124;topk/y_top3` | `0.6756756756756757` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1&#124;topk/x_points` | `37` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1&#124;topk/y_points` | `37` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1&#124;topk/x_random_top1` | `0.125` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1&#124;topk/n_segments` | `13` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1&#124;iou` | `null` | `UNKNOWN（來源未提供）` | `UNKNOWN（來源未提供）` |
| `/comparisons/AOL-B1&#124;iou_conservative/follow_diff` | `-0.4952` | `[-0.601091540560655, -0.4065853658536585]` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1&#124;iou_conservative/wp_diff` | `-0.4` | `[-70.80000000000001, 71.6]` | 見該列欄位（n_points／n_segments／x_points／y_points） |
| `/comparisons/AOL-B1&#124;iou_conservative/n_segments` | `16` | `UNKNOWN（來源未提供）` | 見該列欄位（n_points／n_segments／x_points／y_points） |

### 6.6 S4 `/verdicts/H8d`

| JSON pointer（S4） | 點估計／原值 | 95% CI（原值） | 樣本數／K（原欄位） |
|---|---|---|---|
| `/verdicts/H8d/verdict` | `NOT_SUPPORTED` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/verdicts/H8d/verdict_zh` | `不成立` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/verdicts/H8d/reasons/wrong_person` | `zero` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/verdicts/H8d/reasons/follow_lower` | `-0.6165477150880776` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/verdicts/H8d/reasons/follow_upper` | `-0.4197736739130435` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/verdicts/H8d/reasons/mcnemar_p` | `4.76837158203125e-07` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/verdicts/H8d/reasons/mcnemar_favours` | `baseline` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/verdicts/H8d/robustness` | `DEPENDS_ON_BOX_CRITERION` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/verdicts/H8d/n_points` | `68` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/verdicts/H8d/n_segments` | `16` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |
| `/verdicts/H8d/note` | `K=1 (preregistration §5 H8d); judged apart from AO` | `UNKNOWN（來源未提供）` | n_points=68; n_segments=16 |

### 6.7 延遲、EXPIRED、決策點、token 與費用（S4 欄位與 S6 §9 原文）

| 項目 | 值 | 來源 |
|---|---|---|
| 模型延遲 p50／p95（ms） | 4784／10524 | S4 `/per_arm/AOL/latency_ms_p50`、`/latency_ms_p95`；S6 §9.2 |
| 呼叫／EXPIRED／套用 | 186／98／72 | S4 `/per_arm/AOL/e5_calls/calls`、`/expired`、`/applied`；S6 §9.2 寫「98 次（52.7%）答案過期、72 次被套用」（52.7% 是 S6 文字，S4 沒有此欄） |
| 回答種類 | SELECT 176、OWN_BOX 4、NOT_VISIBLE 5、UNCERTAIN 1（全部 OK） | S4 `/per_arm/AOL/e5_calls/answer_counts`；S6 §9.3 |
| provider 錯誤／逾時／格式退回／預算拒絕／達到呼叫上限 | 0／0／0／0／0（段數 0） | S4 `/per_arm/AOL/e5_calls`；S6 §9.3 |
| 決策點對 | 6/68（B1 28/68） | S4 `/per_arm/AOL/dp_correct`、`/dp_total` |
| token（輸入／輸出） | 1,750,652／37,076 | S4 `/per_arm/AOL/input_tokens`、`/output_tokens`；S6 §9.3 |
| 帳本花費（ApiGuard `est_cost_usd` 增量） | USD 1.931（兩本帳本逐列加總 1.936） | S6 §9.3；**未計快取折扣的上界**，輸入大多為快取命中，實際扣款更低 |
| dry-run 估價 | USD 8.147（791 次，以每段呼叫上限當分母） | S6 §9.3 |
| 帳本累計（執行前→後，同一掃描） | 78.25 → 80.18 | S6 §9.3、§5；上界；期間其他行程可能新增花費，不全是 E5 |
| OpenAI 帳單 | 35.72（2026-11-08～11-23）；S6 §9.3 寫「約 35.72 加本次」 | S6 §5、§9.3；原始截圖查不到，S4 無此欄 |
| 費用上限 | 預登記 USD 7 → 執行時 USD 8.5（使用者在協調者對話決定） | S6 §9.4 |

S4 `/per_arm/AOL/cost_usd` 維持原始 `UNKNOWN (not in the run log; read the ApiGuard ledger)`，不以 S6 費用回填。

## 7. W1 F1 兩個準則

W1 是 r004 兩事件的 422 格分層樣本；以下摘錄兩份既有文件，不重算。

| 準則 | 看圖 Agent（terra_vision_free，K=3 多數決） | 規則 | 差與 95% 區間 | 來源 |
|---|---|---|---|---|
| **主準則**（框中心在 GT 身體框內，或 IoU ≥ 0.3；K=3 多數決，主結果） | 0.957 | 0.523 | +0.433 [0.324, 0.566] | `docs/evaluation/W1_FRAME_EVAL_20261120.md` §3b（第 79、82 行；規則 0.523 見第 65 行）；`docs/evaluation/E3_SCORER_RECOMPUTE_20261122.md`「W1 整體（422 格）F1」表第 84、88 行 |
| IoU 準則（統一評分器，IoU ≥ 0.3） | 0.887 | 0.518 | UNKNOWN（來源未提供；沒有重算區間） | `docs/evaluation/E3_SCORER_RECOMPUTE_20261122.md` 第 84、88 行 |
