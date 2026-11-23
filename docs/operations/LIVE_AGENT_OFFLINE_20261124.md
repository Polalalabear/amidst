# LIVE Agent offline follow-up (#675; A3/B1)

狀態：Codex 已完成，待 Claude 審查。
分支 `codex/feat-live-agent` 從 #690 的最新核准 head
`4d60514e5b05575bf7c01d6d2d51b063e472abc7` 開出，Draft PR base main，**依賴 #690**。
不再推 `codex/feat-live-fixes`。**E5／AO-L 結束前不合併**：本 PR 含 server.py，
合併會改 B1 快照的來源 SHA。未修改 E5 程式或文件，也未修改 scheduler.py。

## 程式結果

- CLI 啟動與 `/config` 切換使用同一個 provider／ApiGuard／key availability gate；
  未核准或 key 缺失回規則並回報原因，不再啟動後直接宣告 available=true。
  切換時檢查實際既有 guard config，環境變數變更不能讓關閉的 guard 被宣告可用。
- Agent 請求建構前放入 session 的目標色；紅／藍目標的 reference layer 不再空白。
- 已超過決策 deadline 的完成回應仍走 TIME_BUDGET fallback，不採用延遲 SELECT。
- Responses transport 在每筆 ApiGuard.run 前做公開 estimate_run（保守未快取價格）；
  key 只在 guard callback 中讀取。沒有新增直連付費入口。
- decision record 加 canonical request SHA-256，保留 model id、scene_context SHA、usage、
  決策來源及 fallback 原因；不記錄 request body／影格。Agent identity_verdict 固定 UNCONFIRMED。
- backend 預設模型改 terra6.1，advisor 仍預設 off。既有候選／排程／rule門檻不改。

現有 LIVE Agent 的 SELECT 以 PeopleTracker 觀測 handle 做延遲串接；未採用、逾時、
provider／guard 失敗仍有原規則退路。這不是 E5 A-open／AO-L，也不宣稱所有回答類型或
未投影／低於原偵測門檻的框都已支援接管。這些既有能力邊界不作本次研究變更。

## B1 前端交接

契約：`docs/contracts/LIVE_TRACK_FIELDS_20261124.md`。
Fixture：`tests/fixtures/live/track_fields_example.json`。
明列 gate_m_effective 的更新前時刻、單位與公式；reject_reason 的三個字串與 null、
優先序／缺投影；cand_id 的 opaque string、分群、缺失與 epoch／session／6 tick 過期。
缺欄位／不可判定的 UI 使用 UNKNOWN，不新增後端 reject enum。
不修改 LIVE 前端或 workbench-v2；Claude 可按此契約接 #695 後續。

## 離線重現

```sh
PYTHONPATH=src uv run --offline --no-project --python <existing-env>/bin/python python -B -m pytest tests/live_mode/test_service_decider.py tests/live_mode/test_llm_switch.py tests/live_mode/test_track_endpoints.py tests/live_mode/test_session_target_color.py tests/live_mode/test_live_agent_launch.py -o addopts='' -q
python3 -m json.tool tests/fixtures/live/track_fields_example.json > /dev/null
git diff --check
```

僅使用合成 JPEG、stub detector／transport、隔離測試帳本與隨機 loopback port。
75 focused tests PASS。紅／藍兩種顏色皆經實際 HTTP `/config` → `/track/start` → `/infer`，
驗證 reference 色、scene_context、Agent SELECT 採用，以及超出 3 m gate 的單候選接回。
另驗未核准啟動／既有guard關閉、無效回應、provider錯誤、逾時已完成回應與 request hash。
舊 endpoint／session 色／launcher focused tests 同時通過。fixture JSON parse 與 diff-check PASS。
Artifacts：NONE；沒有原始來源資產或實際服務收據產生。

## 未驗證與下一個閘門

沒有啟動／重啟／停止 8791，沒有改 8785 pin，沒有模型呼叫／資料外傳／帳本花費。
原 `start_live_agent_8791.py` 仍只允許 runtime `c988ed60`；本 PR 不修改 runtime pin。
真實模型回應、前後端整合與費用仍待 E5 結束後，取得 D359 所需的具體資料外傳與執行核准，
在指定 runtime／沿用核准帳本先 dry-run，再做有界驗證。
全套測試、實際 detector／模型效果、原 23.5 秒事件與實體導航均未驗證。
