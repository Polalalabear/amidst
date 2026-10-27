> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

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

---

# Office 視覺化前端稽核 — Claude Code Opus，2026-10-15

範圍：`/Users/polalabear/Developer/amidst-claude`，branch `claude/office-demo-visualization`，HEAD `400f42fc22e411cbe833392c5f9bcfddd303c61a`（以 `git cherry-pick --ff` 套用 Codex `7033096..400f42f` 四個 commit，與 parent `c6661dd` 線性，無衝突）。純靜態程式碼稽核：**未啟動 workbench、未做瀏覽器重現、未執行測試、未讀大型媒體或 bundle**。檢視檔案（共 8 個，局部範圍）：`frontend/workbench/{app.mjs,scene.mjs,cross-camera.mjs,blender-motion.mjs,index.html}`、`src/amidst/workbench/source_presentation.py:300-420`、`src/amidst/workbench/service.py`（僅 grep dispatch）、`configs/office_demo_fixture_v1.json`。

證據等級：**CONFIRMED** = 程式碼直接證實（行為仍未在瀏覽器重現）；**SUSPECTED** = 程式碼支持的推定原因，需重現；**UNKNOWN** = 證據不足。

## 使用者回報缺陷分類

| ID | 回報 | 判定 | 分類 | 證據 |
| --- | --- | --- | --- | --- |
| D1 | 8 個 2D 面板靜止 | **CONFIRMED（設計使然）** | frontend | 畫面牆是 temporal mosaic：`validateFrameWallResponse` 要求 `temporal_mosaic===true`、`data_kind==='ACTUAL_SOURCE_RGB_TIME_SAMPLES'`（`app.mjs:383-397`）；8 格是所選時間段內固定取樣（`frameWallSelection` `app.mjs:374-382`，預設 `wallSlotCount:8` `app.mjs:74`）。時間軸拖曳/回放只呼叫 `updateFrameWallCursor`（`app.mjs:435-438`），僅切換 `.nearest-source-time` class（框線）。面板內容不隨時間改變。 |
| D2 | 切換鏡頭主要只改框線 | **CONFIRMED** | frontend | 鏡頭 chip 只切 `selected` class（`app.mjs:340-342`）；handler 更新 `state.cameraIds`（multi-select，`.slice(-4)`）並重抓 frames/畫面牆（`app.mjs:1125-1130`）。預設 `visualMode:'3d'`（`app.mjs:74`），同步來源影格只在**預設收合**的 `<details class="source-evidence">`「輔助核對」內（`app.mjs:348-349`），畫面牆在 3D 模式 hidden。`SceneView` 無任何切換至 calibrated camera 視角的方法（`scene.mjs:36-432` 方法列表；`addCalibratedCameras` `scene.mjs:307` 僅畫 frustum）。 |
| D3 | 動畫不是實際模擬影像 | **CONFIRMED** | frontend + asset(UNKNOWN) | 沒有來源 RGB `<video>`。來源回放 `togglePlayback`（`app.mjs:1000-1014`）每 400 ms 前進 **0.4 s** 並以 `timeline` API 取靜態影格；但 Office 取樣為 5 Hz/0.2 s（fixture `sampling_hz: 5`；時間軸 `step=.2` `app.mjs:331`）→ 回放跳過每隔一張來源影格。頁面上唯一的 `<video>` 是**預先物化的還原影片**，caption 自述「素材沒有依本次鏡頭或窄範圍重新產生」（`blender-motion.mjs:120-126`；`cross-camera.mjs:160,300`）。是否存在來源 RGB 影片檔：UNKNOWN（MVP 不需要，可用 0.2 s 靜態影格 flipbook）。 |
| D4 | 3D marker 不可預期漂移 | **SUSPECTED** | frontend（組合）+ backend-contract/data | 同一畫面有多個彼此獨立的位置來源與時間規則：(a) 人形 body 取自 `snapshot.presentation.frames`，最近 ±0.1 s（`scene.mjs:357-383`），該 frames 由**凍結的歷史 motion artifact** 組成（`source_presentation.py:304-320`；`model_revision: historical-office-diagnostic-v1`、`clock: HISTORICAL_CONFIGURED_SYNTHETIC_SECONDS` `:364-366`），與目前選取的 cross-camera/target 結果無關；(b) cross-camera cursor 球取所選候選 samples ±0.1 s（`scene.mjs:185-190`；`crossCameraCursor` `cross-camera.mjs:101-107`）；(c) projected `timeMarker` 最近 ±0.6 s（`scene.mjs:384-393`）；(d) `activeReconstructionTime`（`app.mjs:834-836`）在 source/association/physical/motion 四個時鐘間切換，影片 `play`/`seeking` 會搶時鐘（`app.mjs:862-870`）；(e) body 朝向由「上一次渲染位置」計算（`scene.mjs:373-375`），忽略後端 `yaw_radians`，seek 時會跳轉；步態擺動 `sin(timestamp*7)`（`scene.mjs:377`）忽略 `walk_phase_radians`。 |
| D5 | 物理曲線未反映預期移動 | **SUSPECTED** | frontend（顯示尺度） | `cross-camera.mjs` `chart()` 把 X/Y/Z 畫在**同一 y 軸尺度**（`cross-camera.mjs:131-133` lo/hi 取三軸全部值）；地面投影 Z 近乎常數、X/Y 偏移量不同時，單軸移動被壓扁。缺口處理本身正確：只有 `connect_from_previous===true` 才連線（`cross-camera.mjs:82`）。`blender-motion.mjs` `chart()`（`:80-101`）的尺度未逐行驗證：UNKNOWN。物化曲線圖為全範圍預先產生（同 D3）。 |
| D6 | （MVP 必要功能缺失） | **CONFIRMED** | frontend + backend dependency | 前端沒有任何 `target_reconstruction` 呼叫（`frontend/workbench/*.mjs` grep 無結果；`observation_ref` 只出現在 `motion/investigation/run-study`，非 Office Blender 流程）。來源影格卡片只有 `<img>` + 放大 dialog（`frameHTML` `app.mjs:285-289`；`frameWallItemsHTML` `app.mjs:423-429`），沒有 2D observation overlay，因此「在來源影格選人」無 UI。後端 dispatch 已存在但未執行（`service.py:368,605`）。 |

## 科學有效性風險（立即回報）

- **SUSPECTED / 呈現風險，非 GT 洩漏**：3D 人形在 4.6–8.4 s 量測缺口內仍有位置並移動——presentation frames 的 `INFERRED_GAP` 列帶有 `world_position`（`source_presentation.py:304-316`，以半透明 body 呈現 `scene.mjs:368`）。這違反 MVP「missing 區段不移動」與 contract「long gaps MISSING / null positions」。該檔宣告 `gt_used: False`（`:358`）；缺口位置 `body_base_bu` 的上游來源（pinned `_MOTION` artifact）未檢視：**UNKNOWN**。觀眾可能誤以為缺口路徑已知。

## 缺少的依賴

- **Backend（Codex）**：(1) `POST /api/target_reconstruction` 未執行、無 receipt、無可供前端測試的已驗證 response fixture；(2) Office 每張來源影格的公開 2D observation（`observation_ref` + 像素 bbox/點）是否有既有 endpoint 提供：**UNKNOWN**——沒有它就無法做 contract 要求的「從來源影格選取」；(3) 選取 observation 的來源鏡頭：**UNKNOWN**（fixture 只有 ref 與 4.4 s）；(4) 3D body 應改由 target 候選 samples 驅動，或將歷史 presentation 明確降級——需 contract 決定。
- **Asset**：Office safe-input bundle 路徑 **UNKNOWN**（runner 需 `--bundle`）。Claude checkout 有 `data/engineering/blender_{association,motion,physical,physical_review}_2026101x/` 目錄（僅 `ls`，內容與 hash 未驗證）。
- **Runtime**：workbench 未啟動，瀏覽器重現 **BLOCKED（本 session 未授權執行）**。

## 結論

D1–D3 是**前端呈現設計**與 MVP 期望不符，可在不改後端的情況下以既有 `timeline` API（REPORTED 可用）修復，因此列為第一個實作任務。D4 需要 Codex 的 contract 決定才能完全修正；D5 是小型獨立前端修正；D6 依賴 Codex 的 target receipt 與 2D observation 資料。MVP 範圍與任務順序見 [`OFFICE_DEMO_MVP.md`](../agents/OFFICE_DEMO_MVP.md)、[`OFFICE_DEMO_TASKS.md`](../agents/OFFICE_DEMO_TASKS.md)。
