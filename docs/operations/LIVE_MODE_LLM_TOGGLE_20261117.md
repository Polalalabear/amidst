# 即時模式「LLM 決策」開關使用說明（A6，D242）

分支 `claude/feat-workbench-llm-toggle`。設計依據：`docs/design/LIVE_MODE_LLM_DECISION_V1.md` §3.3、§6 A6。

## 放在哪裡（設計稿標 UNKNOWN 的部分）

`frontend/workbench/` 沒有連到 live 後台（8785 demo 和 8791 live 是不同伺服器，工作台也沒有設定面板），所以開關放在即時模式 B 畫面（`/?role=system`）右側的「設定」區，和 HUD 同一頁、同源，直接打後台 `/config`。**這是和任務原文「工作台設定」的出入**，要不要另外接進 `frontend/workbench/` 由協調者決定（需要先決定 CORS 或代理）。

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

不接任何付費 provider、沒有發出任何 API 呼叫、沒有讀 API key；provider 由後台啟動參數決定（`--advisor-provider`），UI 不提供選擇；工作台 8785 沒改。

## 本機驗證

```bash
cd frontend/live-mode && node --test test/llm_switch.test.mjs test/hud.test.mjs test/protocol.test.mjs
PYTHONPATH=src:<runtime-deps> python -m pytest tests/live_mode -q
```

截圖（LOCAL，`local/evidence/workbench-llm-toggle-20261117/`，埠 8797／8798，不是 8785／8791）：見 PR 描述的 SHA-256。
