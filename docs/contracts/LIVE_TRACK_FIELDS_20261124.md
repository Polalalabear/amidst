# LIVE tracking fields — 2026-11-24

給 Claude 的 B1 前端接線契約；Refs #675、#676、#677、#690。
後端基底：#690 `4d60514e5b05575bf7c01d6d2d51b063e472abc7`。
本文件與離線 fixture 位於 `codex/feat-live-agent`，依賴 #690；不修改前端。
**E5／AO-L 結束前不合併**，不代表已部署 8791。

## 位置、型別與單位

| JSON path | 型別／單位 | 來源與語意 |
| --- | --- | --- |
| `/config.gate_m` | number，m | rule Tracker 基礎距離 gate |
| `/config.gate_growth_m_s` | number，m/s | 距最後看到後的 gate 成長速度；0 為固定 gate |
| `/config.max_gate_m` | number，m | 成長啟用時的上限 |
| `/infer.tracking.gate_m_effective` | number 或 null，m | 該 tick 更新前實際使用的 rule gate；不是事後下一個 tick 的值 |
| `/infer.dets.<camera>[i].reject_reason` | string 或 null，無單位 | 規則診斷原因；完整值域與優先序如下 |
| `/infer.dets.<camera>[i].cand_id` | opaque string，無單位 | 既有 session／epoch／tick 簽章候選群 handle；不是人名、actor id 或身分 |
| `/track/candidates.candidates[i].cand_id` | 同上 | 明確選人的同一種候選 handle |

`gate_m_effective = gate_m`，若 growth 非 0 且已有 `t_seen`，則
`min(max_gate_m, gate_m + gate_growth_m_s * max(0, t_capture_s - t_seen_s))`。
時間來自該請求 `t_capture_ms / 1000`；不可用 UI wall time 回算替代。
成功接回當 tick 會更新 `t_seen`，回傳 gate 仍是更新前使用的值。
growth=0 時不額外套 max_gate，遵循原 Tracker 公式。

`bbox` 是來源影格的 `[x0,y0,x1,y1]` pixels；`est_xy` 是校正地平面投影的
world `[x,y]` metres，可為 null，不是真值。`score` 是偵測器分數，不是身分機率。
`tick` 是 capture 序號，不是秒；例如測試的 0.5 s/tick 不保證所有 LIVE session 都相同。

## reject_reason 完整值域與優先序

第一個成立者勝出：

| 值 | 條件 | 建議顯示 |
| --- | --- | --- |
| `CAM_NOT_SCHEDULED` | 該鏡頭不在本次實際處理的 schedule | 鏡頭未排程 |
| `COLOR_MISMATCH` | 已選 red／blue，該偵測的 color 不符 | 顏色不符 |
| `OUT_OF_GATE` | last estimate、該偵測投影與 gate 皆存在，而且距離嚴格 `> gate` | 超出距離 gate |
| `null` | 以上沒有一條可判定成立 | 未記錄拒絕；不可顯示「已確認目標」 |

同色偵測距離恰好等於 gate 不被此條拒絕。
缺投影時無法判斷距離，`null` 不是投影有效、接回成功或身分通過。
這些是 rule 診斷 metadata，不是 Agent 的硬閘門；Agent 可以選被 rule 拒絕的偵測。
`reject_reason` 不改寫追蹤或排序；也不涵蓋所有失聯可能原因。
本版沒有 `UNKNOWN` 這個後端 reject enum。前端遇到缺欄位／未來不識別值，
顯示 `UNKNOWN`，保留原值供診斷，不猜成 null 或成功。

fresh `/infer` 不推論未排程鏡頭，因此通常不會產出 `CAM_NOT_SCHEDULED`；
未排程鏡頭在 dets 中省略，**省略不是偵測數 0**。fixture 此例只示範離線診斷函式輸入，
不能把它當已接收該鏡頭新影格的證據。

## 缺欄位與 UNKNOWN

- 舊 backend／歷史 response 可能完全沒有 gate、reject_reason 或 cand_id。前端須容忍，不可補成 0、固定 4 m 或已接回。
- `/detect` 回 `tracking: null`；不追蹤時沒有 effective gate。無法取得 gate 時也可能為 null；顯示 `UNKNOWN`。
- 新 `/infer` 的每筆實際偵測有 reject_reason（可為 null）；dets key 缺少與空陣列意義不同。
- cand_id 只在 `lost_ticks > 0`（含尚未進入 LOST 的短缺口）或 `state == LOST` 時，
  對選定同色且有有限投影、能連到當前 selection 候選群的偵測附上。
  正常追蹤、預覽、異色、投影未知、無群代表等情況省略，不回傳字串 `UNKNOWN`。
- 同色框按投影距離 `< 1.5 m` 連通分群，跨鏡頭的多框可共享代表 cand_id。
  cand_id 不能當長期人員 key；前端不要解析其內部格式、不要自行製造或延用到別的 session。
- pick 仍須帶 session_id，且 selection mode 必須 NEEDS_PICK。
  TRACKING／LOST 不因拿到 cand_id 就能直接 pick；先走既有明確 reselect 流程並重取候選。
  epoch 改變、reset、切色或 latest.tick−candidate.tick > 6 會讓 handle 失效。
  `CANDIDATE_UNKNOWN`／`CANDIDATE_STALE`／`TRACK_MODE_CONFLICT` 應重新取 state／候選，不能重試舊 handle。

`identity_verdict` 即使 Agent 採用也只會是 `UNCONFIRMED`；此工程關聯不證明真實身分或物理可通行。

## 範例與核對

fixture：[`tests/fixtures/live/track_fields_example.json`](../../tests/fixtures/live/track_fields_example.json)。
全為合成，不是原 23.5 秒事件；範例 cand_id 只示範型別，簽章不能送到真實服務使用。
`expected_display` 是前端呈現預期，含 `UNKNOWN`，不是服務 payload 的新 enum。
例子涵蓋固定 gate、所有 reject 值、null、缺欄位、缺投影、缺 handle、未追蹤與未知 gate。

既有 focused endpoint tests：`tests/live_mode/test_track_endpoints.py`，
涵蓋 gate 增長／飽和／接回 tick、reason 優先序、缺投影、同群 handle 與 pick guard。
前端整合與真實 LIVE 模型回應待 E5／D359 閘門解除後另驗，本次不改 frontend/workbench-v2 或 LIVE UI。
