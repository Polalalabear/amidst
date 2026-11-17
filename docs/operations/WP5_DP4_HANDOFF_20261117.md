# CX-L3：WP5 DP4接線與零費用重現（#554）

分支`codex/feat-wp5-dp4`，base `main@21aacc8ea75b49fe9efd914a0d0198b789066a7a`（#546已合併）。不需要#559或其他未合併分支。本任務只有dry-run、fake client／transport，不執行任何真實模型或付費API、不讀真實API key；沒有改8785、原始場景或GT資產。

## 最終行為

WP5 runner的`--dp4-method API|AGENT`預設API：API使用既有`ApiRanker`單次呼叫，Agent使用`AgentRanker`的工具迴圈，最多沿config的5步。兩種方法都有OpenAI和loopback Ollama轉接，不再有`DP4_LIVE_NOT_WIRED`。工具只有契約內graph neighbors、recent detections、update hypothesis，GT與操作者欄位在呼叫前拒絕。既有DP4契約與gate斷言未改，沒有接進associate或即時追蹤。

真實OpenAI路徑必須通過既有`--live`／approved-usd／PINNED price／arm／questions閘門，且每一個Agent工具輪都經`ApiGuard.run`；沒有guard不能建paid ranker。預設dry-run零provider呼叫。Agent依profile剩餘整題時間縮短每輪timeout，耗盡後不再派發。美元由WP5核准總額與ApiGuard每次／每日上限管理，不沿用N3的PROPOSED 0.02美元軟上限；沒有更改已提交的正式參數或budget設定。

`calls.jsonl`保留每輪messages、prompt SHA、模型／provider metadata、usage、wall_ms、guard允許／拒絕原因與fallback；未知用量保持UNKNOWN。HTTP400等已知未執行的4xx才記0／0，429與逾時不冒稱免費。DP4也套用既有「100% PROVIDER_UNAVAILABLE不得當有效比較」守門；格式錯誤率沿#546彙總，仍保留原來warning／failure政策。

`--fake`會保留選定方法，但只是框架煙霧測試；實際API/Agent ranker與工具迴圈由下方`--live`介面注入fake provider的測試驗證。這些fixture的LIVE／synthetic approval flags不是真實核准或付費量測。

Colab／Windows pack檔案清單補入`attention_api.py`與`attention_agent.py`，解包後兩種ranker可構造。沒有覆寫既有LOCAL zip或一鍵notebook；舊包不能自動獲得新程式，需另建新包。舊wrapper可能預設skip DP4，直接runner要包含DP4就不傳skip，或明確使用空skip清單。沒有在L4／Windows原生執行，也沒有真的叫Ollama。

## 零費用指令

以下在自己的checkout與既有uv環境執行；輸出根`$AMIDST_ARTIFACTS/cx554-20261117`，本次用本clone的`local/evidence/cx554-20261117`。

```bash
# pilot/formal各做一次，method API/AGENT各一組；不帶--live。
PYTHONPATH=src uv run --offline --no-project --python .venv/bin/python python -m amidst.agent_eval.wp5_runner --set pilot --skip-types DP1,DP3,NL --dp4-method API --out "$AMIDST_ARTIFACTS/cx554-20261117/dry-api-pilot"
# 上式另以formal、AGENT執行，out分別dry-api-formal、dry-agent-pilot、dry-agent-formal。
PYTHONPATH=src uv run --offline --no-project --python .venv/bin/python python -m amidst.agent_eval.wp5_runner --set pilot --fake --skip-types DP1,DP3,NL --dp4-method API --out "$AMIDST_ARTIFACTS/cx554-20261117/fake-api"
# --fake --dp4-method AGENT另存fake-agent。
PYTHONPATH=src uv run --offline --no-project --python .venv/bin/python python scripts/agent_decision/wp5_dp4_dry_report.py --work "$AMIDST_ARTIFACTS/cx554-20261117" --out docs/evaluation/wp5_dp4_20261117/dry_run_report.json
```

dry-run的config呼叫數／美元完全沿`wp5_v1.json`：pilot DP4每模型24名義／120 config最壞，formal120／600。API實作每題1次，config共用係數5是保守計畫，不能把它當API實際重試次數。

新增估計欄位將首輪序列化粗估與config保留值分開：API859 token；Agent975–976；不是tokenizer或計費usage。輸入保留仍2500、輸出上限300、最壞5，未因粗估較低而改budget。Agent後續輸入、真題、實際延遲與用量UNKNOWN。更新方案表及定義見`docs/evaluation/WP5_OPENAI_CALIBRATION_20261115.md` §10；新表沒有授權任何支出。

## 指定focused驗證

```bash
PYTHONPATH=src uv run --offline --no-project --python .venv/bin/python python -m pytest tests/q1q5/test_wp5_dp4_live.py tests/q1q5/test_wp5_eval.py tests/q1q5/test_dp4_attention_gates.py tests/q1q5/test_wp5_openai_api_ids.py tests/q1q5/test_wp5_local_provider.py tests/q1q5/test_wp5_v3_fixes.py tests/q1q5/test_wp5_packs.py -q --basetemp="$AMIDST_ARTIFACTS/cx554-20261117/final-tmp"
git diff --check
```

最終 **140 passed**，沒有跑全套。test-first新測試最初8 failed（接線不存在），完成後通過。四組實際走runner `--live`介面、底層全fake：

| 模型fixture | 方法 | calls.jsonl列 | fake provider calls | summary | 格式錯率 |
| --- | --- | ---: | ---: | --- | ---: |
| terra6.1 | API | 24 | 24 | OK | 0 |
| qwen2.5:7b | API | 24 | 24 | OK | 0 |
| terra6.1 | Agent | 24 | 48 | OK | 0 |
| qwen2.5:7b | Agent | 24 | 48 | OK | 0 |

兩輪Agent fixture先取工具再FINAL；另測五步上限、整題時間、逐輪美元拒絕、GT拒絕、已知未計費4xx與未知429、錯誤格式率、全Unavailable失敗、pack隔離構造。真實provider品質／schema接受度／速度／token均未驗證，不能引用fake延遲或費用當量測。

## LOCAL／已提交收據

`docs/evaluation/wp5_dp4_20261117/dry_run_report.json`綁定config與價目SHA；`verification.json`列四組輸出和測試範圍。原始dry/fake/--live fixture輸出與log留LOCAL：`$AMIDST_ARTIFACTS/cx554-20261117/MANIFEST.json`，SHA-256 **1c42620f54c541a1d96985f837d4c53a8e72a60dd9101278584cccd96034af9c**，37檔808,417 bytes。它只列交付證據，不包含pytest的其他合成fixture和cache。

可依上述指令完整重建新的dry/fake輸出；時間／Python環境造成的log差異不保證同hash。收據重建：`scripts/agent_decision/wp5_dp4_receipt.py --work <LOCAL/cx554-20261117> --out docs/evaluation/wp5_dp4_20261117/verification.json`。沒有任何LOCAL-only啟動或交接文件。

## 實際產出 / Actual output
- Model / effort: GPT-6 / UNKNOWN
- PR / commits: 本feature Draft PR，base main；完整SHA見PR提交紀錄
- Files changed: src/amidst/agent_eval/{wp5.py,wp5_fake.py,wp5_runner.py,wp5_pack.py}；tests/q1q5/{test_wp5_dp4_live.py,test_wp5_eval.py,test_wp5_packs.py}；兩個dry/receipt工具、本交接與校準文件、wp5_dp4_20261117兩份精簡JSON
- Commands run and results: 上述140項focused tests與diff PASS；四組zero-call dry-run、兩組--fake、四組--live-with-fake-provider均產出calls/summary；test-first8 failed→PASS
- Artifacts: 上述LOCAL37檔808,417 bytes及manifest SHA；來源config／價目SHA在已提交dry_run_report.json
- Verified: API／Agent接線、兩種transport格式、guard逐輪且預設關閉、格式錯／不可用彙總、已知／未知usage、config一致估價與呼叫數、打包依賴、GT未進請求
- Not verified: 真實OpenAI／Ollama、付費、API key、L4／Windows原生、真題、模型效果／延遲／實際token、身分與安全
- Deviations, UNKNOWN items and follow-ups: 粗估不當成tokenizer／嚴格費用上界；舊5.93與新config計畫值分開；實跑與新增額度須使用者另行核准，不在本任務內
