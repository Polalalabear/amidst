# ApiGuard cached input accounting (#699)

狀態：Codex 已完成，待 Claude 審查。**E5／AO-L 結束前不合併**。

## 計費與相容性

`ApiGuard.run` 仍接受 `(value, prompt_tokens, completion_tokens)`。
若 value 保留 response usage，guard 讀取 Responses 的
`usage.input_tokens_details.cached_tokens`、Chat 的
`usage.prompt_tokens_details.cached_tokens`，或共用 Responses parser 的
`usage.cached_tokens`；value 可是 mapping 或原始 JSON bytes/string。
只檢查 usage，帳本不保存 body／prompt／key。
已剝除 usage 的 adapter 可選擇回傳第四欄 `cached_tokens`；不必修改既有呼叫端。
完全丟棄 usage 的舊 adapter 仍按未快取計費，本次不修改預錄模式、E5 或其結果。

每個新 ledger row 增加 `cached_tokens`（非負整數或 null）。必須不超過
`prompt_tokens`，bool、float、字串、負值與越界值都視為未知。
`prompt_tokens` 仍包含快取輸入。價格表新增可選欄位：

```json
{"models":{"gpt-6.1-terra":{"input_usd_per_mtok":1.0,"cached_input_usd_per_mtok":0.05,"output_usd_per_mtok":5.0}}}
```

terra 的快取／未快取輸入價為本次使用者提供，輸出價沿用 LIVE 設定。
這是可供 `AMIDST_API_PRICES_FILE` 使用的格式，**本次未更動執行中的價格表、帳本或環境**。
價格若缺失、無效、負值、非有限值或高於原輸入價，保留未快取算法。

`USD = ((prompt_tokens - cached_tokens) * input_price + cached_tokens * cached_input_price + completion_tokens * output_price) / 1e6`。
未知 token 或 provider 例外仍按事前最壞估價記帳。
Dry-run、每次呼叫前的限制與 pending reservation 一律按全部未快取估價。
舊 JSONL 列不改寫／不重算，重啟後仍以該列既有 `est_cost_usd` 計入總額與每日上限。
不從帳單差額或約 70% 命中率推造歷史 cached token。

## 重現

在 feature branch 根目錄，以既有 Python 環境執行：

```sh
PYTHONPATH=src uv run --offline --no-project --python <existing-env>/bin/python python -B -m pytest tests/q1q5/test_api_budget.py -o addopts='' -q
git diff --check
```

本次：53 passed。覆蓋 Responses／Chat／parsed usage、原始 JSON、0／全量快取、
錯誤／缺失價格與 token、dry-run 保守拒絕、混合新舊帳本重啟、未知使用量與 provider 例外。
sandbox 中 uv 的 macOS configuration lookup panic；同一離線命令在受控升權後通過。

Artifacts：NONE；測試只用合成 response 與隔離臨時帳本，無真實帳本改寫或付費呼叫。
未驗證：實際模型費用／帳單一致性、預錄模式與 E5 的 adapter 接線、部署與全套測試。
