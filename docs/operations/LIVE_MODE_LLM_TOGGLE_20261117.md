# 即時模式「LLM 決策」開關使用說明（A6，D242）

分支 `claude/feat-workbench-llm-toggle`。設計依據：`docs/design/LIVE_MODE_LLM_DECISION_V1.md` §3.3、§6 A6。

## 放在哪裡（D265）

兩處，讀寫同一份後端狀態（live 伺服器的 `State`）：

1. 即時模式 B 畫面（`/?role=system`）右側「設定」區，直接打 live 伺服器 `/config`。
2. 工作台（`frontend/workbench/`）左下角的固定小面板「即時 LLM」，在所有頁面都看得到，不受 `render()` 影響。工作台只和自己的後端說話：`GET／POST /api/live_llm`（`src/amidst/workbench/live_llm_proxy.py`，在 `service.py` 的 `_dispatch` 接一個路由），後端再轉到 live 伺服器的 `/config`。

**連線方式選同源代理，不用 CORS**：工作台有自己的 WSGI 後端，代理不需要放寬任何跨來源設定，live 伺服器（`server.py`）這一輪完全沒動。代理規則：live 位址用環境變數 `AMIDST_LIVE_URL`（預設 `http://127.0.0.1:8791`），只接受 `localhost`／`127.0.0.1`、1024–65535 的埠，拒絕 8785 和工作台自己的埠；POST 要同源 Origin、`application/json`，body 重建成只剩 `advisor`（off／review／lead）和選填 `advisor_model`；回應縮成固定的狀態欄位（沒有 key、裝置、GT）。

live 伺服器沒啟動、連不上或版本不支援開關時，面板顯示「LLM 決策：不可用」加原因（例如 `live 伺服器沒有啟動或連不上（127.0.0.1:8791）`），勾選框停用且不勾，不會看起來是開的。

## 行為

| 狀態 | 畫面文字 | 後台 |
| --- | --- | --- |
| 關閉（預設） | `LLM 決策：關閉` | `decider = None`，不建護欄、不送請求，追蹤輸出和原本相同 |
| 開啟，provider 可用 | `LLM 決策：開啟（LLM 覆核／LLM 主導）` | 建立 `LiveDecider`；`fake` provider 顯示「假模型（不連網、不花錢）」 |
| 開啟，但不可用 | `LLM 決策：開啟（不可用，使用規則）` + 原因 | 有效模式留在 `off`（規則），`/config` 的 `llm_switch.reason_text` 說明原因，HUD「模式・模型」格同步顯示 |

不可用的原因（`src/amidst/live_mode/llm_switch.py`）：花費護欄沒核准（`AMIDST_API_ENABLED` 沒開或 `AMIDST_API_MAX_USD_TOTAL` 為 0）、沒有 `OPENAI_API_KEY`（只檢查有沒有設，不讀值、不印）。付費 provider 仍受 `ApiGuard` 限制（D166）。

預設與重新整理：前端不存「已開啟」。畫面一律讀後台 `/config`，後台預設 off、重啟回到 off；所以只有使用者明確打開才會是開，重新整理保持使用者剛才的選擇。

生效時機：切換後建立新的 decider；參考圖在下一次 `ACQUIRE`（重新鎖定目標）才會取得，之前不會發問。

## 介面

- `GET /config`：多了 `llm_switch {requested, effective, available, reason, reason_code, reason_text, provider, model, models}`；`advisor` 仍是有效模式。
- `POST /config` `{"advisor": "off|review|lead", "advisor_model": 選填}`：其他欄位一律忽略；`advisor` 缺少或不合法回 400。
- B 畫面的訊息白名單（`frontend/live-mode/src/protocol.mjs`）沒有改；開關資訊只走 `/config`，不進影格訊息。

## 沒有做

不接任何付費 provider、沒有發出任何 API 呼叫、沒有讀 API key；provider 由後台啟動參數決定（`--advisor-provider`），UI 不提供選擇；8785 demo 沒有重啟或修改。

## 啟動工作台時

用 live 伺服器預設埠 8791 就不用設定；其他埠：`AMIDST_LIVE_URL=http://127.0.0.1:<埠>` 後再啟動工作台。`live-llm.mjs` 已加進 `scripts/start_office_demo.py` 的證據複本清單，並用動態 `import()` 載入：缺這個檔時工作台照常，只是沒有面板。

## 本機驗證

```bash
cd frontend/live-mode && node --test test/llm_switch.test.mjs test/hud.test.mjs test/protocol.test.mjs
cd frontend/workbench && node --test live-llm.test.mjs app.test.mjs static-assets.test.mjs
PYTHONPATH=src:<runtime-deps> python -m pytest tests/workbench/test_live_llm_proxy.py tests/workbench/test_office_launcher.py -q
PYTHONPATH=src:<runtime-deps> python -m pytest tests/live_mode -q
```

截圖（LOCAL，`local/evidence/workbench-llm-toggle-20261117/`，埠 8797／8798，不是 8785／8791）：見 PR 描述的 SHA-256。
