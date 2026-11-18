# 預錄模式（8785）OpenAI Agent 操作（#601，D306）

預設關。要用時開**兩個**程序，缺一個就是規則模式（Agent 選項反灰並寫原因）。

1. **gateway**（自己的終端機；只有它有網路與 key，每次呼叫都過 ApiGuard）：
   ```bash
   export OPENAI_API_KEY=...   # 只放在這個程序的環境
   export AMIDST_API_ENABLED=1 AMIDST_API_MAX_USD_TOTAL=1
   ./start_agent_gateway.command
   ```
2. **demo（8785）**，照平常方式啟動，另外設 `AMIDST_RECORDED_AGENT=openai`。稽核掛鉤（D269）不變：8785 程序不開 socket，只在 owned 的 `state/agent-gateway/` 讀寫檔案。

## 預算與逾時
- 預設用已核准參數：每輪 2000 ms、總 5000 ms、最多 3 輪。**實測 gpt-6.1-terra 每輪約 2.3–3.5 s，所以預設值下一定逾時、退回規則（`PROVIDER_TIMEOUT`）。**
- 要讓 Agent 實際可用，demo 程序另設（操作者明示，寫進參數集並讓 hash 改變）：`AMIDST_RECORDED_AGENT_CALL_TIMEOUT_MS=8000`、`AMIDST_RECORDED_AGENT_TOTAL_BUDGET_MS=24000`（上限 120000）。預錄回放不是即時，等較久只影響操作體感。是否改成預設值，等協調者決定（#601）。

## 顯示與退回
- 不可用原因（bootstrap `agent_unavailable_reason`）：`GATEWAY_OFFLINE`、`GUARD_NOT_APPROVED`、`NO_API_KEY`、`MODEL_NOT_ENABLED`。
- 執行中逾時／ApiGuard 拒絕／回應不合法：該次決策退回規則，`fallback_reason` 為 `PROVIDER_TIMEOUT`／`MODE_NOT_AUTHORIZED`／`INVALID_RESPONSE`。
- 沒有 key 的呼叫在 ApiGuard 之前就被擋，不計費。

## 實測（2026-11-18，合成 Q5 fixture，真實 gpt-6.1-terra）
見 PR 與 #601 的「實際產出」。
