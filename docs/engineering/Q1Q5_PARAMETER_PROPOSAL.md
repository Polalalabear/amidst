# Q1–Q5 第一版參數組：已核定初值與未決項

日期：2026-10-20（Asia/Taipei）。[QT-05／#98](https://github.com/Polalalabear/amidst/issues/98)。機器檔為 [parameter_set_v1.json](../../configs/q1q5/parameter_set_v1.json)。

這份文件物化 D65／D67／D68 的初值，不另外提出一套數字。整組仍是 **PROPOSED、不可作核准 runtime 參數**：索引與 HSV 等必要值未決，r004 的實際 run／index 尚未產生。`run_ids: []`、`detection_index_ids: []` 表示沒有任何已綁定對象，絕不表示 wildcard／套用全部。身分 UNCONFIRMED；不提供物理通行／碰撞認證。

## 1. 固定依據與逐項核准

- 契約 [#86 @ 3873ff2](https://github.com/Polalalabear/amidst/blob/3873ff2dbe97c88b3de2cfcdfc7df393fdff23d2/docs/contracts/Q1_Q2_FIRST_DEMO_V1.md) §11／§2.2（bytes SHA-256 `924c4365ab3b3169eb9192296a26eede9d558d885410e7e80197d00a77978078`）。本檔只用該 schema，未把 #135 未核准修訂當成基準。
- [D65](https://github.com/Polalalabear/amidst/issues/88#issuecomment-6291477432) 明列核定值；[D67 第 2 項](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6292484288) 補核 #126 六個預算；[D68 第 3 項](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6292617734) 核定 5 fps／stride 1。

| 出處 | APPROVED 的項目與值 | 單位／適用條件 |
| --- | --- | --- |
| D65 | `top_k=3`、`agent_max_rounds=3` | count |
| D65 | `agent_total_budget_ms=5000`、`agent_call_timeout_ms=2000` | ms；單次與總預算不同 |
| D65 | `link_iou_min=0.30`、`link_center_dist_max_diag_ratio=0.50` | IoU／最後匹配框對角線比例 |
| D65 | `link_max_gap_us=600000`、導出 `link_max_gap_samples=2` | us／index_samples；5 fps、200000 us 間距 |
| D67 | `agent_max_illegal_submissions=2`、`session_max_research_rounds=6`、`session_max_agent_rounds=12` | count |
| D67 | `search_window_us=6000000`、`research_interval_us=1000000` | us |
| D67（數值）＋[D71 第 2 項](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6308081801)（語意） | `fallback_budget_ms=1000` | ms；只記錄的效能觀察值，實際用量放 `stats.latency_ms.fallback`；不截斷、不改輸出、不停止 session |
| D68 | `stride_samples=1` | source_samples；來源 5 fps |

`link_max_gap_samples` 只是 `600000 / 200000 - 1 = 2` 的核對欄，不是另一個獨立核定值。t＋0.2／0.4 s 失配仍 TEMP_LOST，t＋0.6 s 失配才 SEARCHING；若 t＋0.6 s 恰好接上，仍是同一段、gap_samples=2。stride 2 的 400000 us 與 stride 5 的 1000000 us 都不整除 600000，必須 `PARAMETER_GRID_MISMATCH`，不能四捨五入或拉長暫失。

## 2. 未決項與不能執行的原因

契約表格中有提案但 D65 沒有明列核准的 `switch_min_presence=MATCH_STRONG`、`q3_llm_timeout_ms=2000`、bbox 底邊中點出口方法，保留 **PROPOSED**。不能把「§11 初值」擴張成核准所有空白欄位；D65 的 2000 ms 明列在 Agent 呼叫項，不據此推定 Q3 所有設定均核准。

以下值保持 `null`／PROPOSED：`index_score_floor`、`query_min_score`、`segment_merge_gap_us`、`link_min_score`、`link_color_rule`、`link_ambiguity_margin`、出口邊界規則、`evidence_max_observations`、`q3_max_llm_attempts`、LLM temperature／seed。`nms.iou=null` 表示沒有另外做 NMS 的 IoU 門檻；detector 配置仍須依契約 §4.2 明示 `nms.applied=false`，不能因 null 改用預設 NMS。

HSV 在 [#114](https://github.com/Polalalabear/amidst/issues/114) 另行提案；本檔只留 `color_method_sha256: null` 作尚未綁定的引用，不複製或填造裁切／HSV 門檻。不使用 A／B1 白色人形、smoke 的 0.30、人物設定、事件腳本、路線、GT 或人工標註調參。

目前只有 `applies_to.scene_revision=r004` 與 200000 us 格距設計；實際 run IDs、detection index IDs、source／HSV hashes 仍 UNKNOWN。未來必須針對實際已物化且核准的輸入另出新版本，不能把本檔的空清單當全場授權。

## 3. Hash 與後續核定

`content_sha256` 是移除頂層 `content_sha256`、`parameter_set_id`（以及可選 `stats`）後，以 UTF-8、JSON `sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False` 計算 SHA-256。`parameter_set_id = pset:q-demo:<hash 前 16 碼>`。每項的值、單位、status、出處與整組 approval 都進 hash；任何值、範圍或核准狀態變更都要產生新 hash／ID，不覆寫舊研究 parameter set。

D65／D67 初值的後續調整只能用授權的 r004 preview（不使用 Demo 事件），另出新版、Claude 檢查、使用者核定。D71 已定：`fallback_budget_ms` 不截斷，所以 RULE_ONLY 重跑結果一致；語意以 #148 後的契約 §8.6 為準。值仍是 D67 的 1000，不以此修改 Agent 的單次／總預算。

## 4. 本次驗證範圍

只做 JSON schema、canonical hash／ID、逐項決策與 grid 算術檢查，以及 `git diff --check`。沒有產索引、取 RGB、調 HSV、呼叫 Ollama、渲染或讀取 GT。完整 runtime／效能／人物辨識品質均未驗證。精確 commit、機器檔 hash 與 #127 結果記於 PR／#98 的實際產出紀錄。
