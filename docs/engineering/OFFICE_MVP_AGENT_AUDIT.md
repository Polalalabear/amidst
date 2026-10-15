# Agent / deterministic fallback audit — 2026-10-15

唯讀稽核 tree: `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization`，parent 指定 baseline `c6661dd`。未修改 source / ignored runtime / frontend / frozen data，未呼叫真實模型或付費 API。僅建立 `/private/tmp` 收據/測試 ledger。

## 實際配置與健康

- `data/engineering/local_run/phase2_abc/agent_provider.json` exists；SHA256 `9d1ef0f5848e606946f1b8a91ba7a0e60c2f4fa615fcc347d580181ba75c51a6`。
- endpoint `http://127.0.0.1:11437`，model `qwen2.5:7b-instruct`，digest `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`，base timeout `120s`。provider 無 context_tokens 欄位，constructor default `8192` (`src/amidst/local_agent/provider.py:37-38`)。
- `data/engineering/local_run/phase2_repair_0511/agent_transport_profile.json` exists；SHA256 `9ab32a9130431ea93023625445e51a2a669e8e5e1398ba935d9f85fe022c87cb`，schema `phase2.agent.transport.v1`，綁定上述 base SHA，effective per-HTTP timeout `180s`，automatic retries `False` (`workbench/agent_transport.py:12-48`)。
- 實測唯讀 `GET /api/tags` HTTP 200，7B digest 與 pin 相同；另有 3B digest `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`，不是現行 provider。沒有 completion。命令：`curl --fail http://127.0.0.1:11437/api/tags`；本輪用 Python `http.client` 等價 GET。
- OpenAI API: `rg -n 'OpenAI|openai' src pyproject.toml` 無 provider/SDK 接線。既有文件空章節不可算已配置；實際 provider 固定 `OLLAMA_LOOPBACK`、loopback-only。

## Agent source of truth / bounds

| 項目 | 實際值 / 行為 | source |
| --- | --- | --- |
| calls | model 12 (max24), tool8 (max16), actual attempts charged | `local_agent/contracts.py:49-57`; `manager.py:495-500,733-739` |
| budget | total actual tokens24000, elapsed300s, prompt24000 chars, result6000 chars, output768 tokens, window120s | 同上 |
| generation | temperature0, seed0, context8192, output limit | `local_agent/provider.py:93-125` |
| HTTP timeout | per request180s effective; `identity()` calls before and after chat, not one hard180s whole-call deadline | `provider.py:60-125` |
| overall elapsed | before/after operation checks; in-flight blocking HTTP/tool not forcibly killed at300s | `manager.py:495-533,568-571,770-789` |
| retries | zero automatic transport retries | `agent_transport.py:47`; `provider.py:60-81` |
| unavailable / timeout | transport `OSError`/TimeoutError → `AGENT_MODEL_UNAVAILABLE`; case `FAILED`; no automatic deterministic fallback | `provider.py:76-79`; `manager.py:666-669,831-855` |
| evidence | original receipt payload hashes, exact literal rows, citations; model cannot rerank algorithm results | `contracts.py:75-145`; `manager.py:147-174,550-560,810-824` |
| persistence | SQLite ledger; stop/resume generation guard, old execution versions readonly | `local_agent/store.py`; `manager.py:147-174,188-200,428-435` |
| Replay | get_replay consumes existing event metadata; saved answers do not invoke a completion; not an Office Agent replay provider | `local_agent/tools.py:28-50`; `integration/replay.py`; `docs/engineering/DEMO_V1.md:45-47` |

Allowed typed tool catalogue (`local_agent/tools.py:28-50`): `resolve_place`, `list_cameras`, `query_observations`, `query_events`, `get_event_summary`, `get_event_detail`, `get_media`, `get_replay`, `get_observation_detail`, `query_reachable_cameras`, `propose_feasible_trajectories`, `search_person_appearance`, `get_stitch_hypotheses`. Actual binding intersects source tools and excludes `get_media` (`workbench/phase2_suite.py:221-245`). Camera/time/resource refs constrained to server-issued scope; top_k≤8, page≤12 (`local_agent/tools.py:69-132,170-213`). Agent has no shell, raw geometry, pathfinding or arbitrary filesystem tools.

## Office is independent of Agent

`workbench/service.py:1241-1262` only loads product bridges for `local-camera` and `local-camera-accuracy-v2`；Office does not have one. Agent requires a verified product bridge + PostgreSQL (`workbench/phase2_suite.py:203-245,299-304`)。因此即使7B健康，Office source demo 原生 Agent status 仍應表達不可用，不能把 E1 Agent 結果冒充 Office。

Office MVP 應直接呼叫既有 `BlenderSceneAdapter.cross_camera_reconstruction()` / `.physical_cross_camera_reconstruction()` (`workbench/blender_scene.py:658-714`)。Agent unavailable/timeout/refusal/budget event 應以獨立 trace 回到此 deterministic baseline；不要等待 Agent 才讓使用者取得來源與候選。Recorded Replay 應保存確實執行的 request、payload SHA、candidate refs、decision ledger、trace；新重跑比對相同 canonical digest。不可生成假的 Agent decisions。

## Deterministic modules / limits / exact deficiency

- Office `BaselineMotionIndex`: `workbench/blender_motion.py:24-29` **MAX_WINDOW_S=10.0** (不是 Agent 的120s), max cameras4, points400, tracks32, interpolation gap≤1s, speed≤8m/s。0–9.8s source window符合此限制。
- Office `BaselineAssociationIndex`: `workbench/blender_association.py:24-31,53-143,145-210,256-290,490-572`：64 nodes、256 edges、beam256、K≤5、time/speed/overlap filters、canonical candidate ordering；long gap MISSING，無外插；RGB-derived floor-only projected local tracks，identity UNCONFIRMED。
- Office physical layer `workbench/blender_physical.py:128-155,750-839,841-925`：pool256、beam256、每path checks1000、reject curves≤5；UNKNOWN retained，exact known collision才reject；query-time physical checks0。每source cameras subset 預計算 deterministic beam。Office 現有docs明示全 UNKNOWN/0 hard exclusions，不得聲稱人體可通行或完整 obstacle constraints PASS。
- 既有 Office search 有有限 combinatorial bounds，但沒有 wall-clock deadline/獨立 candidate evaluation budget/camera subset count cap。MVP 可對固定2camera fixture 用 process deadline及明列候選評估上界，不需改演算法或新建另一套 reconstruction。
- 正式 `SpatiotemporalGraphEngine` (`graph/engine.py:220-262,427-632`) already has bounded Camera Graph route expansion, speed/time reachability, deadline: K3, nodes10000, path1000m, search1s, branch32, detour2 (`domain/search.py:19-27`)，NO_FEASIBLE_PATH/SEARCH_TIMEOUT/MAX_SEARCH_NODES etc。**不要直接接到 Office 假裝 geometry 已被授權**。
- `BlindGapReconstructor` (`reconstruction/blind_gap.py:126-275`) only time-parametrizes supplied routes, validates endpoints/time/length, exposes constant-speed vs dwell uncertainty；沒有自行找路或ReID。

## 實際 focused verification

工作目錄：上述 engineering tree。無 source writes：`PYTHONDONTWRITEBYTECODE=1`，`-B`，pytest cache disabled，basetemp `/private/tmp`。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -m pytest -o addopts='' -q -p no:cacheprovider tests/local_agent/test_tools_provider.py tests/local_agent/test_manager.py tests/workbench/test_workbench_agent_transport.py tests/unit/test_graph_engine.py tests/unit/test_reconstruction.py -k 'not test_ollama_wire_contract_pins_digest_schema_options_and_real_counts' --basetemp=/private/tmp/amidst-agent-audit-summary-20261015
```

實際：`289 passed, 1 deselected in 4.47s`。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -m pytest -o addopts='' -q -p no:cacheprovider tests/local_agent/test_tools_provider.py::test_ollama_wire_contract_pins_digest_schema_options_and_real_counts --basetemp=/private/tmp/amidst-agent-wire-audit-20261015
```

實際：`1 passed in 0.79s`。首次整組run該test被sandbox local bind拒絕；以核准的本機fake HTTP server重跑通過，未呼叫真實7B。合計290 focused tests通過。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B /private/tmp/amidst-agent-failure-probe.py
```

實際：scripted transport timeout → `AGENT_MODEL_UNAVAILABLE`；scripted manager unavailable → `FAILED`, attempts1, unknown usage1, tools0, real model calls0, automatic deterministic fallback false。首次probe錯把TimeoutError注入HTTPConnection constructor（在try之外），已改為模擬真實 `.request()` timeout並通過；不把首次probe當產品網路缺陷。

限制：沒有真實模型品質驗收、沒有真實180s timeout等待；不能把SCRIPTED故障注入或歷史模型品質當最新版LLM成功證據。Office independent fallback/replay adapter與deadline/trace acceptance需parent實作並驗證。
