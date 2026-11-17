# 即時模式「LLM 決策」開關使用說明（A6，D242）

分支 `claude/feat-workbench-llm-toggle`。設計依據：`docs/design/LIVE_MODE_LLM_DECISION_V1.md` §3.3、§6 A6。

## 放在哪裡（D265、D267）

兩處，讀寫同一份後端狀態（live 伺服器的 `State`）：

1. 即時模式 B 畫面（`/?role=system`）右側「設定」區，同源打 live 伺服器 `/config`。
2. **新工作台 `frontend/workbench-v2/`**（8785 demo 實際使用的，由 `scripts/serve_demo_integration.py` 提供）：後台頁 `admin.html` →「設定」→「即時模式 · LIVE」群組的「即時 LLM 決策」開關（`admin-ui.mjs`，邏輯在 `live-llm-model.mjs`）。狀態不存瀏覽器、不屬於「儲存」，每次操作立即送出，畫面一律用 live 伺服器回報的狀態。舊的 `frontend/workbench/`、`src/amidst/workbench/service.py` 這一輪沒有任何改動（D265 的版本已移除）。

**連線方式：瀏覽器直連 live 伺服器，live 伺服器對指定本機來源開 CORS，不用代理。** 原因：`serve_demo_integration.py` 啟動時安裝的稽核掛鉤（`scripts/demo_dependency_config.py` 的 `install_owned_io_guard`）禁止這個行程做任何 `socket.connect`（含本機），所以後端代理在 8785 的行程裡永遠連不上 live 伺服器；要改掛鉤是安全決定，我沒有動。

- live 位址預設 `http://127.0.0.1:8791`；工作台頁網址加 `?live_port=<埠>` 可改（只接受 1024–65535，不含 8785 和本頁自己的埠）。
- live 伺服器新參數 `--workbench-ports`（預設 `8785`，逗號分隔）：只有 `http://127.0.0.1:<埠>`、`http://localhost:<埠>` 這些來源會得到 CORS 標頭（只在 `/config`，絕不用 `*`）；`OPTIONS /config` 對其他來源回 403；`POST /config` 帶了不在名單、也不是 live 頁自己的 Origin 就回 403（沒有 Origin 的 curl／腳本不受影響）。
- 瀏覽器端只送 `advisor`（off／review／lead）和選填 `advisor_model`，回應縮成固定狀態欄位。

live 伺服器連不上、被擋或版本不支援開關時，面板顯示「LLM 決策：不可用」加原因，開關停用且不開。

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

## 啟動時

live 伺服器用預設埠 8791、工作台是 8785：什麼都不用設。其他埠：live 伺服器加 `--workbench-ports <工作台埠>`，工作台頁網址加 `?live_port=<live 埠>`。

## 本機驗證

```bash
cd frontend/live-mode && node --test test/llm_switch.test.mjs test/hud.test.mjs test/protocol.test.mjs
cd frontend/workbench-v2 && node --test *.test.mjs
PYTHONPATH=src:<runtime-deps> python -m pytest tests/live_mode -q
```

截圖（LOCAL，`local/evidence/workbench-llm-toggle-20261117/`，埠 8797／8798，不是 8785／8791）：B 畫面的 `1-`～`3-`，工作台 v2（真的 `serve_demo_integration.py` 後端在 8797、live 在 8798）的 `v2-1-`～`v2-3-`；SHA-256 見 PR 描述。
