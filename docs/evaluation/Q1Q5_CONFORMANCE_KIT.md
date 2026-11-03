# Q1–Q5 合約符合性測試包（Conformance Kit）

狀態：**v0.3.0-rc5，綁定已合併的 staging 契約檔**（#237 merge commit `83da40f`，檔案內含 D65／D69／D71／D73／D78–D82）。rc5 再加上 `tracking_scope` 文件的 kind 與 scope 原始 bytes pin 檢查（見 §16）；綁定不變。rc4 沿用 rc3 的綁定（staging `680ca357` 的契約檔 bytes 相同），只把測試包對齊同一份檔案的 §2.3／§5.1（D81）scope pin、§8.6（D78）SWITCHING 兩段 journal 與 §7.6＋D73 §14-20 的 Q3 digest（見 §15）。rc2 綁的是 `a958dd4` 加 D73 決定文字，已由 rc3 取代（見 §14）。契約仍待 Claude 複核與 Codex 確認新 SHA；本測試包跟著契約改版，不是契約的一部分，也不宣告任何產品已通過。

| 綁定項目 | 值 |
| --- | --- |
| 契約 | `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md`，分支 `codex/q1q5-staging` |
| 契約 commit | `83da40f075e7981b02b4b2150ccf0cf9128e4008`（PR #237 的 merge commit；PR head `b50764114063a03c240acd63f5c7cedc528635cf`）。staging 之後又前進，但契約檔 bytes 沒變（rc4 在 `680ca357a31b664bed3feb6a5284dcd7c5c0d94d` 重新核對，記在報告的 `contract.rechecked`）。上一版綁定 `a958dd4` 記在報告的 `contract.previous_binding` |
| 契約檔 SHA-256（bytes） | `b700bf86041f4853ae37dd54bbc9d93199a07be3d5d3c87bc8c2f6455570df04`（報告的 `contract.file_sha256`，`final_file_sha256` 與它相同） |
| 已核准的基底 | `3873ff2dbe97c88b3de2cfcdfc7df393fdff23d2`（D65；檔案 SHA-256 `924c4365…8078`，v0.2.x 綁這一版） |
| 決定（§14） | D65、D69、D71、D73、D78–D82 已寫進契約條文；決定紀錄在 [`Polalalabear/amidst#93`](https://github.com/Polalalabear/amidst/issues/93)（報告的 `contract.decisions`） |
| 含 D73 的契約檔 SHA-256 | 已填：同上（rc2 的「待填」到此解除） |
| 測試包版本 | `0.3.0-rc5`（`amidst.evaluation.q1q5_conformance.KIT_VERSION`）；每份報告都記錄這幾項 |

契約改版後，測試包要同步改版並更新上表與常數 `CONTRACT`；舊報告的契約 commit 不同就不能當新契約的證據。v0.1.0 → v0.2.0 見 §11，v0.2.1 → v0.3.0-rc1 見 §12，v0.3.0-rc1 → rc2（D73）見 §13，rc2 → rc3（綁已合併的契約檔）見 §14，rc3 → rc4（D78 SWITCHING、D81 scope pin）見 §15，rc4 → rc5（`tracking_scope` 文件、原始 bytes pin）見 §16。

## 1. 這套東西做什麼

Codex 實作 Q1–Q5 後端時，可以自己跑這套測試，確認輸出**符合契約的形狀與不變量**，不必經過協調者。它只測**契約層**：

- JSON Schema：欄位、型別、封閉清單、不得有額外欄位。
- 共通回應欄位：`provenance.gt_read`、`identity_verdict`、`agent_used` 等欄位彼此一致。
- 不變量：候選排序、`TOPOLOGICAL_ONLY` 邊不進候選、部分涵蓋不得 `READY`、hash 可重算、不含本機路徑等。

測試包本身**不含任何 GT、產製路線或事件腳本**，也不含「某人應該出現在哪台鏡頭或哪個時間」這類劇情答案（見 §8）。

## 2. 怎麼跑

只用標準函式庫與 repo 內的 `amidst` 套件，不需要額外安裝 `jsonschema`。

```bash
# 讀錄好的回應（目錄內放 request / response / 上下文檔，見 §3）
uv run python scripts/check_q1q5_conformance.py --recorded <dir> --params <parameter_set.json> --output report.json

# 直接打本機後端（只允許 127.0.0.1 / localhost；契約沒定端點，必須自備 endpoint map）
uv run python scripts/check_q1q5_conformance.py --base-url http://127.0.0.1:8000 \
  --requests <request 與上下文檔目錄> --endpoint-map endpoints.json --probe-forbidden \
  --params <parameter_set.json> --output report.json

# 列出所有檢查
uv run python scripts/check_q1q5_conformance.py --list-checks

# 這套測試包自己的測試
uv run pytest tests/unit/test_q1q5_conformance.py
```

`endpoints.json` 的格式是 `{"q-demo.q1-request.v1": "/路徑", "q-demo.q3-parse-request.v1": "/路徑", "q-demo.q2-request.v1": "/路徑"}`。契約沒有定義端點（U04），所以這份對應由 Codex 提供，測試包不猜。`--probe-forbidden` 會把每個請求再加上一個禁用欄位（`actor_id`）送一次，預期收到 HTTP 422 `FORBIDDEN_INFERENCE_INPUT`（契約 §6.1、v1.1 §7）。base-url 模式只涵蓋 Q1、Q3 解析、Q2 這三種「請求 → 回應」；偵測索引、兩層圖、決策紀錄、候選快照、說明文字契約都沒有端點，只能放進上下文目錄用 `--recorded` 風格檢查。

## 3. 輸入目錄慣例

目錄內每個 `*.json` / `*.jsonl` 依 `schema_version` 分類；不認得的檔案會讓 `DOCUMENT_LOADABLE` 失敗。檔名慣例（**這是測試包的慣例，不是契約**）：

| 檔名 | 內容 |
| --- | --- |
| `<名稱>.request.json` / `<名稱>.response.json` | 同名（stem 相同）的請求與回應，用來做成對檢查。Q1 請求被拒時，`.response.json` 可以是 `{"error_code": ..., "http_status": ...}` |
| `<名稱>.llm_output.json`、`<名稱>.explanation.json` | Q3 的 LLM 原始輸出；LLM 說明文字（外層包裝是暫定的，U10） |
| `<名稱>.decisions.jsonl`、`<名稱>.snapshot.json`、`<名稱>.agent_decision.json` | Q2 的逐步紀錄（每行一筆 `q-demo.decision-record.v1`）、候選快照（暫定，U05）、Agent 提交 |
| `clock_mapping.json`、`detection_index.json`、`detection_index.records.jsonl`、`region_graph.json`、`camera_graph.json` | 上下文；有它們，才能跑跨文件檢查（hash 連結、牆鐘換算、圖與候選一致） |
| `<名稱>.evidence_<n>.json`、任意檔名的 `q-demo.candidate-evidence.v1` | Q4 的候選證據摘要（契約 §8.3 只給欄位，`schema_version` 與檔名是本包暫定，U26）；決策紀錄用 `evidence_sha256` 連到它 |
| `<session>.links.jsonl` | 同鏡頭連接器的 link journal（D69：每個 session 一份 append-only JSONL，每行 `q-demo.link-record.v1`）。依每行的 `session_id` 連到決策與 Q2 回應；Q2 回應的 `links_sha256` 是這個檔案的 bytes hash |
| 0 byte 的 `<session>.decisions.jsonl`／`<session>.links.jsonl` | 還沒有任何決策或 link 的 session（例如 `NO_SEED`）的空 journal；依檔名 stem 綁到 `session_id`。其他名稱的空檔仍是不認得的文件 |
| `parameter_set.json` | 參數組，`q-demo.parameter-set.v1`（§4） |
| `supported_classes.json` | 本測試包自己的輸入：`class_map` 的標籤、別名表、顏色詞彙（契約沒給可讀的清單，U02；D73 §14-10 決定單一 `q-demo.supported-classes.v1`，欄位名等契約條文，目前兩個 `schema_version` 都收） |

缺少某個上下文時，依賴它的檢查報告 `SKIPPED_NO_CONTEXT`，不算通過，但也不擋整體結果；要擋就把檔案放進目錄。

## 4. 參數組（契約 §11）

門檻數字一律由參數組讀入，**測試包沒有任何預設值**。`parameter_set.json` 是契約 §11 的 `q-demo.parameter-set.v1`：`parameters[]` 每筆有 `name`、`value`、`unit`、`status`（`PROPOSED`／`APPROVED`）、`proposed_by`、`proposal_ref`，另有 `applies_to`（`scene_revision`、`run_ids`、`detection_index_ids`、`index_interval_us`）與 `approval`。v0.1.0 讀的「平的 JSON 物件」不再支援（缺 `schema_version` 會讓 `SCHEMA_VALID` 失敗）。

- 目前會讀的：`index_score_floor`、`top_k`、`switch_min_presence`、`agent_max_rounds`、`agent_total_budget_ms`、`q3_max_llm_attempts`、`link_max_gap_us`；`link_max_gap_samples` 若列出只當導出值的核對欄（§8.2），不是另一個核定值。
- 沒有該名稱、值是 `null`、`""`、`"待約定"`、`"TBD"`，或型別不對（數字參數給了布林或字串），都算未設定，依賴它的檢查回報 `SKIPPED_PARAM_UNSET`。
- `index_score_floor` 缺時，會退而讀索引 manifest 的 `detector.index_score_floor`（它是資料，不是測試包的預設）。
- `parameter_set_id` 是 `pset:q-demo:<content_sha256 前 16 碼>`，`content_sha256` 的 preimage 不含 `content_sha256` 與 `parameter_set_id` 本身（契約 §2.2）；回應 `resolved_scope.parameter_set_*` 要對得上。
- `approval.status` 不是 `APPROVED` 時，回應不得是 `READY`／`COMPLETE`，`PARTIAL` 要填 `PARAMETERS_NOT_APPROVED`（`PARAMS_APPROVAL_GATES_STATUS`）。多個原因同時成立時取哪一個還沒核准（§14 第 12 項，U31），本版維持 `3873ff2` 的讀法。
- `applies_to.index_interval_us` 必須等於所用鏡頭（回應的 `resolved_scope.camera_ids`，#135 C5）的 `index_interval_us`，`link_max_gap_us` 必須是它的正整數倍；否則 Q2 回應必須是 `status: UNKNOWN`、`reason: PARAMETER_GRID_MISMATCH`、`timeline: []`（D69；`Q2_FAIL_CLOSED_ON_GRID_MISMATCH`）。`PARAMETER_GRID_MISMATCH` 是原因碼，不是錯誤碼（#135 C6）。
- 參數值**由使用者核定**（契約 §11）。`tests/fixtures/` 內的值是 SYNTHETIC 的任意數字（`proposed_by: SYNTHETIC-NOT-A-PROPOSAL`），不是提案值，不要抄進真正的參數組。

## 5. 結果與結束碼

報告（JSON）內容：每項檢查對每份文件的 `PASS` / `FAIL` / `SKIPPED_PARAM_UNSET` / `SKIPPED_NO_CONTEXT` 與理由、輸入檔 SHA-256、契約 commit 與檔案 hash、測試包版本、參數組 id 與 hash、契約不清楚處清單，以及 `output_sha256`（報告去掉自身後的 canonical hash；報告不含時間戳與本機路徑，同樣輸入會得到位元組相同的報告）。

| `summary.overall` | 意思 | 結束碼 |
| --- | --- | --- |
| `PASS` | 沒有 FAIL，也沒有因參數未設而略過的檢查 | 0 |
| `INCOMPLETE` | 沒有 FAIL，但有檢查因參數未設而略過（**不算通過**） | 1；`--allow-incomplete` 時為 0 |
| `FAIL` | 至少一項違反契約 | 1 |
| `ERROR` | 沒有文件可檢查，或參數／檔案無法讀取 | 1 |

`SKIPPED_NO_CONTEXT` 不影響 `overall`，但會出現在報告中，請檢查是否漏放上下文檔。

## 6. 檢查清單與契約章節

「啟發式」表示用關鍵字或正規式判斷，可能有誤報；誤報請回報（§9）。每項檢查都有至少一個違規 fixture 證明它抓得到（`test_every_check_is_proven_to_detect_something`）。

| 檢查 ID | 契約章節 | 套用文件 | 檢查內容 |
| --- | --- | --- | --- |
| `DOCUMENT_LOADABLE` | §2.1 | 全部 | File parses as JSON (no NaN/Infinity), has a known schema_version, no symlink or path escape |
| `SCHEMA_VALID` | §2–§8 (per kind) | 全部 | Document validates against its JSON Schema (closed lists, required keys, no extra keys) |
| `NO_FORBIDDEN_CONTENT` | §2.3, §9, v1.1 §7 | 全部 | No local absolute path, GT / private / event-script field or token anywhere in the document |
| `CONTENT_HASH_RECOMPUTE` | §2.1, §2.3, §3.1, §4.2, §5.2–§5.3, §8.3, §8.7 | `detection_index`、`region_graph`、`camera_graph`、`clock_mapping`、`decision_record`、`parameter_set`、`candidate_evidence` | content_sha256 (evidence_sha256 for an evidence summary) equals the canonical hash of the document without itself, stats and its self-derived id (index_id / graph_id / parameter_set_id), §2.2 preimage |
| `OUTPUT_HASH_RECOMPUTE` | §2.1, §2.3, §7.5 | `q1_response`、`q3_response`、`q2_response` | output_sha256 recomputes without output_sha256 and stats; hashed body has no timing fields or explanation text |
| `ID_DERIVED_FROM_HASH` | §2.2 | `detection_index`、`region_graph`、`camera_graph` | graph_id uses the first 16 hex chars of content_sha256; index_id (and the observation_id segment) uses the first 16 of the index key (manifest without index_id, content_sha256, records_ref, records_file_sha256), §2.2 |
| `PARAMSET_INTEGRITY` | §2.2, §11 | `parameter_set` | parameter_set_id is pset:q-demo:<first 16 chars of content_sha256> (content_sha256 itself is checked by CONTENT_HASH_RECOMPUTE) |
| `ERROR_RESPONSE_RULES` | §2.3, v1.1 §7 | `error_response` | Error responses use a known error code with the matching HTTP status (shape is provisional) |
| `COMMON_GT_READ_FALSE` | §2.3, §9 | `q1_response`、`q3_response`、`q2_response`、`detection_index` | provenance.gt_read is exactly false |
| `COMMON_IDENTITY_UNCONFIRMED` | §2.3, §7.5, §8.7 | `q1_response`、`q3_response`、`q2_response` | identity_verdict is UNCONFIRMED and no text claims 'the same person'（啟發式） |
| `COMMON_AGENT_FIELDS` | §2.3, §7.3, §8.6 | `q1_response`、`q3_response`、`q2_response` | agent_used / agent_attempted / llm_parse_used / decision_source / fallback_used / fallback_reason are mutually consistent (RULE_ONLY with agent_used is allowed after an exhausted Agent, D73 §14-21; the journal decides) |
| `COMMON_STATUS_REASON` | §2.3, §3.3, §5.1, §6.3, §7.4, §8.7 | `q1_response`、`q3_response`、`q2_response` | status is in the endpoint's closed list; READY has no reason; PARTIAL has one |
| `COMMON_REASONS_LIST` | §2.3 (§14-12 a) | `q1_response`、`q3_response`、`q2_response` | reasons[] lists every reason that holds without duplicates, reasons[0] equals reason ([] when reason is null), and all codes keep the §14-12 total order (head list, other codes in ASCII order, degradation tail); the list is hashed with the response |
| `TIME_COVERAGE_INTERNAL` | §3.3, §4.4, §6.3, §8.7 | `q1_response`、`q2_response` | Partial wall-clock coverage is never READY/COMPLETE/NO_MATCH; uncovered ranges listed; OUT_OF_RANGE queries nothing |
| `TIME_COVERAGE_RECOMPUTE` | §3.1, §3.3 | `q1_response`、`q2_response` | Resolved source ranges, coverage_complete and uncovered_wall_ranges equal the values computed from the clock_mapping (wall requests only) |
| `SCOPE_HASH_LINKS` | §2.3, §4.2, §5, §11 | `q1_response`、`q3_response`、`q2_response` | resolved_scope hashes / ids point at the supplied index, graphs, clock mapping and parameter set |
| `TRACKING_SCOPE_STRUCTURE` | §5.1 (D81), §5.4 step 0 | `tracking_scope` | The scope file has exactly the v3 keys, a known status, a camera partition (query = tracking + query-only, disjoint) and a complete directed-pair matrix over the query cameras (TRANSITION pairs name a transition, EXCLUDED pairs name a reason); with a camera graph supplied, the tracking cameras are the graph's cameras and the TRANSITION pairs are exactly the graph's transitions |
| `TRACKING_SCOPE_BYTES_PIN` | §5.1 (D81) | `tracking_scope` | The SHA-256 of the scope file's raw bytes equals the single tracking-scope input pin of each supplied region / camera graph (the file is not re-serialised before hashing) |
| `RESPONSE_SCOPE_PIN_IS_FILE_BYTES` | §2.3, §5.1 (D81) | `q1_response`, `q3_response`, `q2_response` | A non-null resolved_scope.tracking_scope_sha256 equals the SHA-256 of the raw bytes of a supplied tracking_scope file (Q2 and its decision records share that pin, see Q2_RESPONSE_VS_DECISIONS); null is allowed, Q1 / Q3 use it when they ran without the scope |
| `GRAPH_APPROVAL_GATES_STATUS` | §5.1 | `q1_response`、`q2_response` | A response built on a DRAFT graph is not READY/COMPLETE and says GRAPH_NOT_APPROVED |
| `Q1_MIN_SCORE_FLOOR` | §6.1, §4.2 | `q1_request`、`q1_response` | query_min_score is never below index_score_floor; a request below it is answered with FORBIDDEN_INFERENCE_INPUT |
| `Q1_UNSUPPORTED_HANDLING` | §6.1, §6.3 | `q1_response` | UNSUPPORTED_* statuses return no results; a colour condition on a non-person class is UNSUPPORTED_* |
| `Q1_SUPPORTED_SET_CONSISTENCY` | §6.1, §6.2 | `q1_response`、`q1_request` | Class / colour support decision agrees with the supplied class map, alias table and colour vocabulary |
| `Q1_STATUS_VS_COVERAGE` | §3.3, §4.4, §6.3 | `q1_response` | READY needs a full inference pass and a result; NO_MATCH never hides un-inferred, missing or uncovered time; PARTIAL when anything is missing |
| `Q1_RESULT_ORDER` | §6.3 | `q1_response` | Results ordered by first match time then camera_id, ranks consecutive, segments ordered and half-open, counts consistent; a last page ends at rank results_total (#156) |
| `Q1_NONE_CATEGORIES_DISJOINT` | §6.3 | `q1_response` | A camera appears in only one of results / no_match_cameras / not_evaluated_cameras |
| `Q3_LLM_OUTPUT_STRICT` | §7.1 | `q3_llm_output` | LLM output has no extra field and a consistent clarification flag |
| `Q3_LLM_TERMS_LITERAL` | §7.1 | `q3_llm_output` | class/colour/time/camera/region terms are fragments of the user's original text |
| `Q3_RESPONSE_RULES` | §7.2–§7.4, §7.6 (D73 §14-20) | `q3_response` | structured_query only when PARSED; clarification and failure statuses never execute; LLM call recorded when LLM was used; a null observed model_digest only on a provider-level failure (no raw output, fallback_reason PROVIDER_UNAVAILABLE / PROVIDER_TIMEOUT, parse not used) |
| `Q3_STRUCTURED_QUERY_SCHEMA` | §7.2 step 4 | `q3_response` | The assembled structured_query validates against the Q1 or Q2 request schema |
| `Q3_FALLBACK_CONSISTENCY` | §7.3 | `q3_response` | A rule parse after an LLM attempt (LLM_WITH_RULE_FALLBACK) records fallback_used with a provider reason |
| `Q3_ATTEMPTS_WITHIN_PARAM` | §7.2, §11 | `q3_response` | llm_call.attempts <= q3_max_llm_attempts |
| `Q3_MISSING_CLOCK_CLARIFIES` | §7.2 (D73 §14-9) | `q3_response` | A Q3 request whose context has no clock_mapping_sha256 is answered NEEDS_CLARIFICATION (rule parser and LLM alike): never PARSED into a wall-clock query and never an error code |
| `Q1_Q3_SINGLE_RUN_ONLY` | §3.1, §6.1, §7.2 (D73 §14-11) | `q1_request`、`q1_response`、`q3_response` | The first version queries one run: a Q1 request with several run_ids is answered UNKNOWN without results, a Q3 request that spans several runs is answered NEEDS_CLARIFICATION, and no Q1 answer or Q3 query spans runs |
| `EXPLANATION_CITED_REFS` | §7.5 | `explanation` | Every cited ref appears in the explained response; text claims no identity; at least one ref is cited (explanation wrapper is provisional)（啟發式） |
| `CANDIDATE_ORDER_D28` | §5.4, v1.1 §6.1 | `candidate_snapshot` | Candidates sorted by relation_tier (§5.4 decision order 4,3,1,2), overlap_area_m2 desc (null last), camera_id; ranks consecutive; one entry per camera; ranking_basis has exactly the three D28 keys and no detection/colour keys |
| `CANDIDATE_TOPOLOGICAL_EXCLUDED` | §5.2–§5.4 | `candidate_snapshot` | TOPOLOGICAL_ONLY paths never appear as candidates; excluded ones carry TOPOLOGICAL_ONLY_EDGE; agrees with the camera graph when supplied |
| `CANDIDATE_SNAPSHOT_HASH` | §2.2, §5.4 | `candidate_snapshot` | candidate_snapshot_sha256 equals the canonical hash of the snapshot without itself, stats and every candidate_ref (candidates identified by rank) |
| `CANDIDATE_RANKING_AREA` | §5.3, §5.4 | `candidate_snapshot` | ranking_basis.overlap_area_m2 equals the camera graph transition's ranking_area_m2 (null stays null) |
| `CANDIDATE_REFS_AND_LIMITS` | §5.4, §8.4, §11 | `candidate_snapshot` | candidate_ref embeds the snapshot hash prefix and rank; candidate count <= top_k |
| `CANDIDATE_WINDOW_TRUNCATION` | §8.6 (#135 C4), §8.3 | `candidate_snapshot` | window_truncated_us is a list of half-open ranges, sorted, non-overlapping and inside the candidate's uncut window_us ([] when nothing is cut, never null) |
| `DECISION_FIELD_CONSISTENCY` | §8.4, §8.6 (D78), §8.7 | `decision_record` | accepted/rejection_code, decided_by, switch_mode, fallback_reason, executed action and state_after agree (an accepted SWITCH ends in SWITCHING; the SWITCHING -> PLAYING record adds no LLM call, D78) |
| `DECISION_CANDIDATE_LEGALITY` | §5.4, §8.4 | `decision_record` | The candidate switched to is in the legal snapshot (never a TOPOLOGICAL_ONLY / excluded / invented one) and its camera is a candidate camera |
| `DECISION_SEQUENTIAL_ORDER` | §8.4, §8.6 | `decision_record` | Candidates are taken in rank order without skipping; evidence is fetched before a switch/next; a switch is the last step and follows NEXT_CANDIDATEs |
| `DECISION_SWITCH_GUARD` | §8.4, §8.6, §11 | `decision_record` | An accepted SWITCH only targets a candidate whose target_presence reaches switch_min_presence; a rule decision does not skip a guard-reaching candidate that has an entry observation, and records NO_ALIGNABLE_OBSERVATION when it has none |
| `DECISION_REJECTION_CORRECTNESS` | §8.4 | `decision_record` | A submission that violates the controller rules (unknown ref, stale snapshot, no evidence, no citation) was not accepted |
| `DECISION_BUDGET_LIMITS` | §8.6, §11 | `decision_record` | rounds_used / budget_used_ms respect agent_max_rounds / agent_total_budget_ms, and session_agent_rounds_used respects session_max_agent_rounds (ROUND_LIMIT covers both, D73 X3), unless the matching fallback is recorded |
| `SESSION_STATE_MACHINE` | §8.6 (D78) | `decision_record` | Each record is a legal §8.6 transition (an accepted SWITCH goes SEARCHING -> SWITCHING, then SWITCHING -> PLAYING); the SWITCHING -> PLAYING record names the accepted SWITCH in cause_decision_id and keeps its snapshot, entry, candidate, decision time and model-round count (D78); step_index strictly increases and source time never goes backwards within a session |
| `DECISION_SESSION_COUNTERS` | §8.6, §8.7 (D69) | `decision_record` | searching_index is 0 before the first SEARCHING, the same within one snapshot and larger for a new one; session_agent_rounds_used never decreases and counts at least every recorded LLM call so far |
| `DECISION_LLM_CALL_RULES` | §7.6, §8.7 (D73 §14-20) | `decision_record` | A null model_digest only on a call that failed before the model reported one (PROVIDER_UNAVAILABLE / PROVIDER_TIMEOUT, no raw output); a PASS call has a string digest and a raw output hash |
| `DECISION_NO_WALL_CLOCK` | §8.7 (D73 §14-17) | `decision_record` | A RULE_ONLY record carries no wall-clock time (budget_used_ms 0, no latency / duration field): wall-clock time lives in response stats and diagnostics, so a replay has the same journal bytes |
| `DECISION_AGENT_EXHAUSTED_RETURN` | §8.4, §8.6 (D73 §14-21) | `decision_record` | In an AGENT_SEQUENTIAL session a Controller RETURN_TO_ORIGIN decided by RULE_ONLY follows accepted Agent NEXT_CANDIDATEs over every candidate of the snapshot and records no fallback_reason |
| `DECISION_NO_AUTO_AGENT_RESTART` | §8.6 (D73 X2) | `decision_record` | After a fallback_reason the rules decide the rest of the session: the Agent is called again only after a USER decision (the user restarts it on the front-end), never automatically |
| `Q2_RESPONSE_VS_DECISIONS` | §2.3, §5.1 (D81), §5.4 step 0, §8.6, §8.7 | `q2_response` | agent_used / agent_attempted / fallback_used / first fallback_reason / decision_source equal what the session's decision records imply (an accepted Agent NEXT_CANDIDATE counts for agent_used, and a Controller return after them is RULE_ONLY, D73 §14-21); every record's input_pins.tracking_scope_sha256 equals resolved_scope.tracking_scope_sha256, and a null scope pin only goes with an UNKNOWN that opened no session (§5.4 step 0, D81) |
| `Q2_SWITCH_CAMERA_LEGAL` | §5.4, §8.6 | `q2_response` | Every SWITCH segment cites an accepted SWITCH decision whose snapshot candidate is exactly that camera, and starts at the evidence's entry_timestamp_us with the decision's entry_observation_id |
| `Q2_LINKS_FILE_HASH` | §8.2, §8.7 (D69) | `q2_response` | links_sha256 is the SHA-256 of the exact bytes of the session's link journal and every record in it belongs to the response's session |
| `Q2_DECISIONS_FILE_HASH` | §2.3, §8.7 (D73 §14-17) | `q2_response` | decisions_sha256 is the SHA-256 of the exact bytes of the session's decisions journal (UTF-8 JSONL, newlines included) |
| `Q2_TIMELINE_STRUCTURE` | §8.7 | `q2_response` | Timeline ordered, contiguous, half-open; GAP segments never carry a position; observation-driven ON_CAMERA segments; status matches the timeline |
| `AGENT_DECISION_FORMAT` | §8.4 | `agent_decision` | Submission has a well-formed candidate_ref bound to its snapshot, citations for SWITCH, and a rationale for NEXT_CANDIDATE |
| `GRAPH_STRUCTURE` | §5.1–§5.3 | `region_graph`、`camera_graph` | Graph ids unique, references resolve inside the graph, closed lists respected, approval fields coherent |
| `GRAPH_CROSS_REFERENCES` | §5.2, §5.3 | `camera_graph` | Camera graph agrees with its region graph: hash link, paths follow edges, traversability is the weakest edge, unknown state propagates |
| `CLOCK_MAPPING_RULES` | §3.1 | `clock_mapping` | wall_origin's UTC offset matches the declared IANA timezone on that date; declared (not observed) clock |
| `INDEX_MANIFEST_RULES` | §4.2, §4.4 | `detection_index` | Per-camera sampled / inferred ranges are half-open, ordered, inferred within sampled, not_inferred disjoint from inferred; per-camera stride_samples = top-level (D69); index_interval_us = stride_samples x source_frame_interval_us; detector class_map / nms / load rules; one content_sha256 per index_id |
| `INDEX_RECORDS_FILE_HASH` | §4.2 | `detection_index` | records_file_sha256 equals the SHA-256 of the supplied records file |
| `RECORDS_FRAME_STATE` | §4.3, §6.3 | `detection_records` | frame_state is closed; only INFERRED has a detections array (empty = no detection); NOT_INFERRED has a reason; records sorted and unique |
| `RECORDS_OBSERVATION_IDS` | §2.2, §4.3 | `detection_records` | observation_id follows obs:<hash16>:<camera>:<frame>:<ordinal> where <hash16> is the hash segment of the manifest's index_id; ordinals 0..n-1 by score desc then bbox; boxes valid |
| `RECORDS_INDEX_GRID` | §4.4 | `detection_records` | Frames on the index grid (index_grid_origin_frame + n x stride_samples) are never NOT_SAMPLED; frames off the grid are NOT_SAMPLED |
| `RECORDS_COLOR_RULES` | §4.3 | `detection_records` | Colour only on applies_to_classes; verdicts cover the whole vocabulary; UNKNOWN verdicts carry unknown_reason; score range |
| `RECORDS_MATCH_MANIFEST` | §4.3, §4.4 | `detection_records` | INFERRED frames lie inside inferred_ranges_us of their camera; every camera is declared in the manifest |
| `RECORDS_SCORE_FLOOR` | §4.2, §11 | `detection_records` | No stored detection scores below index_score_floor |
| `PROBE_FORBIDDEN_FIELD_REJECTED` | §6.1, §9, v1.1 §7 | 全部 | (base-url mode) A request carrying a forbidden extra field is rejected with HTTP 422 FORBIDDEN_INFERENCE_INPUT |
| `EVIDENCE_PRESENCE_RULES` | §8.3 | `candidate_evidence` | frames / coverage_complete / target_presence follow the §8.3 judging order (NOT_EVALUATED first, empty window never covered, NONE+UNKNOWN is not a colour mismatch, partial coverage never negative; without a colour condition only four values and null verdicts, #135 C8); entry observation not before decision_time_us |
| `DECISION_EVIDENCE_AND_ENTRY` | §8.3, §8.6, §8.7 | `decision_record` | decision_time_us <= source_time_us; an accepted SWITCH has an entry_observation_id that matches the candidate's evidence; considered candidates match their evidence summary and the evidence is bound to this snapshot (a NEXT_CANDIDATE may cite an observation-free evidence hash, D73 §14-26) |
| `LINK_RECORD_GAP_RULES` | §8.2 | `link_records` | elapsed_us is a positive multiple of the camera's index_interval_us; gap_samples = elapsed_us / index_interval_us (the current mismatching cell counts) and one less for LINKED |
| `LINK_RECORD_FIELDS` | §8.2 (D69, #135 C3) | `link_records` | One session per link journal, link_index 0..n-1 in file order; next_observation_id / iou set exactly for LINKED; ambiguous_candidates a non-empty list exactly for AMBIGUOUS_LINK, else null |
| `LINK_RECORD_MATCHING_AUDIT` | §8.2 (D78 F1, link-record.v2) | `link_records` | link-record.v2: matching_audit is an object or null (key never omitted); it is an object once earlier cells were left unlinked; actual_pair_iou is the main iou, reference_iou is set only for LINKED, event REACQUIRED / LINKED only for a LINKED cell and NO_MATCH otherwise, CENTER_TRANSLATION_V1 uses two real source observations in time order, elapsed_us equals the main field; v1 records (historical replay) are not judged |
| `SEARCHING_TRIGGER_TIME` | §8.2, §8.3, §8.6, §11 | `decision_record` | decision_time_us is the time of the first unlinked index cell with gap_samples > link_max_gap_samples (elapsed_us >= link_max_gap_us, N derived as link_max_gap_us / index_interval_us - 1); after a return the rules' re-search starts its window at the tick that entered it, at least research_interval_us after the return (D73 §14-18); a manual reselect is not applicable |
| `Q2_FAIL_CLOSED_ON_GRID_MISMATCH` | §8.2, §11 | `q2_request` | If the parameter set and the index grid do not match (index_interval_us, link_max_gap_us a positive multiple of it, listed link_max_gap_samples = derived), the paired Q2 reply is status UNKNOWN, reason PARAMETER_GRID_MISMATCH, empty timeline (D69); otherwise it never says PARAMETER_GRID_MISMATCH |
| `Q2_EXIT_ZONES_PRECHECK` | §8.2, §8.6 (D73 X1) | `q2_response` | Exit zones are checked once, before the seed is looked for: a camera of resolved_scope.camera_ids without exit_zones makes the whole answer UNKNOWN / EXIT_ZONES_MISSING with an empty timeline and no session step; the reason is never used otherwise |
| `Q2_REASON_STATUS` | §2.3, §5.4, §8.2, §8.7 (D69, D81, D82) | `q2_response` | A blocking reason (grid, exit zones, tracking scope, seed camera not tracked, ...) answers status UNKNOWN with an empty timeline; USER_STOPPED answers PARTIAL (D82) and never UNKNOWN or COMPLETE; reason is reasons[0] |
| `PARAMS_APPROVAL_GATES_STATUS` | §11 | `q1_response`、`q2_response` | A response built on a parameter set whose approval.status is not APPROVED is not READY/COMPLETE and says PARAMETERS_NOT_APPROVED |

## 7. 契約中標 `UNKNOWN` 的檢查（契約修訂建議）

契約沒寫清楚、所以測試包**沒有猜**（或只能用暫定形狀）的地方。「影響的檢查」欄說明測試包目前怎麼處理。Codex 確認契約時請逐項回覆；契約修訂後，測試包會跟著改版。

| # | 契約章節 | 不清楚的地方 | 建議的修訂 | 影響的檢查 |
| --- | --- | --- | --- | --- |
| U01 | §4.3 | Per-frame records have no schema_version; the records file name, location and format (JSONL vs array) are not defined. | Add schema_version `q-demo.detection-record.v1` and state the file format. | SCHEMA_VALID, RECORDS_* |
| U02 | §4.2, §6.1 (D73 §14-10) | D73 §14-10 (a) decides one q-demo.supported-classes.v1 (classes, aliases, colour vocabulary, each with a hash) for Q1 and Q3. Its field names, hash fields and where the label list of the class map is stored are in the contract text that is not merged yet. | Name the fields and the hash preimage; until then the kit reads class_labels / aliases / color_labels from a supported_classes.json in the recording and accepts both schema_version values. | Q1_SUPPORTED_SET_CONSISTENCY (SKIPPED_NO_CONTEXT without that file) |
| U03 | §2.3, §3.2, §6.3 | TIME_EXPRESSION_INVALID is named as a return but Q1/Q2 `status` lists do not contain it, and error responses (FORBIDDEN_INFERENCE_INPUT 422 etc.) have no body schema. (A Q3 request without a clock is NEEDS_CLARIFICATION, D73 §14-9; the three reason codes of §2.3 are reasons, #135 C6.) | Say whether TIME_EXPRESSION_INVALID is a status or an error code and define the error-response body. | COMMON_STATUS_REASON, ERROR_RESPONSE_RULES |
| U04 | §1–§8 | No HTTP endpoints or paths are defined for Q1, Q3 parse, Q2 or the Agent tools. D73 §14-15/-22 (a) decides stable media_ref + short-lived grant + start / poll envelope (about nine endpoints); the endpoint table is in the contract text that is not merged yet. | Add an endpoint table (method, path, request and response schema_version). | --base-url mode needs an --endpoint-map supplied by Codex |
| U05 | §5.4, §8.4 | transition_candidates output has no wrapper schema: wrapper fields, the name of the truncated-count field, the schema_version and the endpoint are not defined. (The hash rule is defined in §2.2; window_truncated_us is a sorted, non-overlapping list of half-open ranges inside window_us, [] when nothing is cut, #135 C4.) | Define q-demo.candidate-snapshot.v1 (wrapper, truncated count). | CANDIDATE_* (kit uses a PROVISIONAL wrapper schema; CANDIDATE_WINDOW_TRUNCATION follows C4) |
| U06 | §5.4 step 4 | Relationship between candidate_set_complete, truncated and a top_k cut is not stated (v1.1 §6.1 defines truncated as budget-only). | State whether a top_k cut sets truncated or candidate_set_complete=false. | CANDIDATE_REFS_AND_LIMITS (only count <= top_k is checked) |
| U08 | §5.2 | BIDIRECTIONAL / ADJACENT boundary-ref field names are not given. (relation UNKNOWN = tier 4 and the two-value traversability list are settled by #135 C1 / C2.) | Name the ADJACENT boundary ref field. | GRAPH_STRUCTURE |
| U09 | §7.1, §7.3 (D73 §14-9) | D73 §14-9 (a): the rule parser and the LLM both use q-demo.q3-llm-output.v1 and a missing clock is NEEDS_CLARIFICATION. Still open: the `parser_mode` enum, where the rule parser's version and hash live in provenance, and the reason code for the clock case (the #144 review proposes CLOCK_MAPPING_MISSING; the kit does not enforce it). | Define parser_mode, provenance.rule_parser {version, sha256} and the reason code. | Q3_RESPONSE_RULES, Q3_FALLBACK_CONSISTENCY, Q3_MISSING_CLOCK_CLARIFIES |
| U10 | §7.5 | The LLM explanation has no output schema, endpoint or schema_version; how its `content_sha256` is computed is not stated. | Define q-demo.explanation.v1 {explains_output_sha256, text, cited_refs, fallback_reason, content_sha256}. | EXPLANATION_CITED_REFS (PROVISIONAL schema) |
| U12 | §8.7 (D73 §14-17) | D73 §14-17 keeps wall-clock time out of the journal (it lives in response stats and diagnostics) and the kit checks that for RULE_ONLY records. `budget_used_ms` of an AGENT_SEQUENTIAL record is still measured inside the hashed record; D73 does not say whether it moves out too. | State whether budget_used_ms of an Agent session moves under stats / diagnostics. | CONTENT_HASH_RECOMPUTE, DECISION_NO_WALL_CLOCK (RULE_ONLY only), DECISION_BUDGET_LIMITS |
| U13 | §8.7 | decision-record `rounds_used` does not say whether it is per decision or per SEARCHING episode. (decisions_sha256 is the hash of the journal's exact bytes and a RULE_ONLY return after the Agent's NEXT steps is the last switching decision, D73 §14-17 / §14-21; agent_used is defined since 1d1e061.) | State the unit of rounds_used. | DECISION_BUDGET_LIMITS |
| U14 | §8.6, §2.3 | With MODE_NOT_AUTHORIZED the response is RULE_ONLY but fallback_used is true; it is not stated whether decision_source is RULE_ONLY or RULE_FALLBACK. (The ILLEGAL_CANDIDATE counter is per SEARCHING since 1d1e061.) Not answered by D69 / D71 / D73. | State decision_source for MODE_NOT_AUTHORIZED. | COMMON_AGENT_FIELDS, Q2_RESPONSE_VS_DECISIONS (kit accepts RULE_ONLY with fallback_used) |
| U15 | §8.5, §8.7 | APPEARANCE seeds with several candidates need a user choice, but no response status or payload exists for 'awaiting seed selection'; NO_SEED does not say whether it may be returned when time coverage is partial. D73 §14-22 (a) adds endpoints but the seed-candidates payload is not named. | Add a status (e.g. SEED_SELECTION_REQUIRED) and say whether NO_SEED needs coverage_complete. | Q2_TIMELINE_STRUCTURE (NO_SEED is not forced to coverage_complete) |
| U16 | §6.3 | segment_merge_gap_us: whether the gap is measured between sample times or range ends, and strict vs inclusive, is not defined. | Define the gap operator. | no segment-merge check exists |
| U17 | §2.2, §6.3 | query_id / query_sha256 / decision_id derivation from 'the normalised request' has no normalisation rule, so they cannot be recomputed. | Specify the normalised-request canonical form. | no query_id check exists |
| U18 | §11 | parameter-set.v1 is defined (§11) but several §11 parameters have no machine name (crop ratio, HSV bands, exit rule, ...), the unit vocabulary is open, and the values of approval.status other than PROPOSED / APPROVED are not listed. | Name every parameter and list the approval.status values. | kit reads parameters[] by name; approval.status is kept a free string |
| U19 | §4.3 | unknown_reason is one field per detection but verdicts are per colour; whether all verdicts must be UNKNOWN when it is set is not stated. | State the relation. | RECORDS_COLOR_RULES (only 'UNKNOWN => reason set' is enforced) |
| U20 | §3.1 (D73 §14-11) | D73 §14-11: the first version queries one run (Q1 over several runs is UNKNOWN, Q3 asks). The reason code of that UNKNOWN is not named, and the multi-run shape of resolved_scope (a single clock_mapping_sha256 for several runs) is left for a later version. | Name the reason code for a multi-run Q1 request. | Q1_Q3_SINGLE_RUN_ONLY (status UNKNOWN, no results; the reason is not enforced), SCOPE_HASH_LINKS |
| U23 | §8.6, §8.7 | step_index counts steps, but only decisions are in the decisions file (link / TEMP_LOST steps are not), so records are not state-contiguous and step_index is not guaranteed consecutive. | State whether the decisions file includes every step; the kit checks only that step_index increases and time never goes backwards. | SESSION_STATE_MACHINE |
| U34 | §6.3, §14-15 / -22 (D73) | D73 decides stable media_ref + short-lived grant + start / poll envelope. The field names (media_ref in place of media_token), the grant and the envelope are not in a contract text yet, and Q1 hashes still cover media_token. | Name the fields and the endpoints. | SCHEMA_VALID (kit keeps the current Q1 media field), U04 |
| U35 | §8.6 (D73 §14-18) | D73 §14-18 (a) accepts that a re-search after a return starts its window at the current tick (kit: decision_time_us equals the source time of the entering record and is at least research_interval_us after the return) and a manual reselect goes through a server port. exit_rule {method, boundary_inclusive} and the manual-port decision_time_us anchor are not written; D73 says the boundary_inclusive value is decided separately. | Write exit_rule, the manual-port anchor and the boundary_inclusive value. | SEARCHING_TRIGGER_TIME (a manual reselect stays not applicable) |
| U37 | §5.1 (D81), §8.6 (D78), §8.7 | The merged contract requires the Q2 journal to carry its input pins (§5.1) and the two SWITCHING records to bind one decision (§8.6 D78), but its text names neither wire key: `input_pins` is the product's spelling of 'journal 的輸入 pins' and `cause_decision_id` is named only in the D78 decision comment. The §8.7 decision-record example still shows the atomic SEARCHING -> PLAYING (option (b), not adopted) and has neither key. | Write input_pins {tracking_scope_sha256} and cause_decision_id into the §8.7 decision-record example and update its state_after to SWITCHING. | SCHEMA_VALID (kit admits exactly these two keys), SESSION_STATE_MACHINE, Q2_RESPONSE_VS_DECISIONS |

**契約已回答、先前版本曾標 `UNKNOWN` 的項目**（`3873ff2` §2.2、#135 釐清、D69／D71、D73；測試包現在依條文或決定計算，不再暫定）：

| # | 原本不清楚的地方 | 契約現在怎麼說 | 檢查 |
| --- | --- | --- | --- |
| U07 | numeric suffix of candidate_ref | §2.2: cand:<snapshot_hash16>:<rank> | CANDIDATE_REFS_AND_LIMITS |
| U08 | relation UNKNOWN / tier 4 marker and traversability UNKNOWN | #135 C1, C2: relation UNKNOWN is tier 4; traversability has only APPROVED_WALKABLE / TOPOLOGICAL_ONLY; the remaining BLIND_GAP combination does not exist | SCHEMA_VALID, GRAPH_STRUCTURE, CANDIDATE_ORDER_D28 |
| U11 | link record schema_version, file, session binding and null values | D69 (§8.2): q-demo.link-record.v1, one append-only JSONL per session, links_ref / links_sha256 (exact bytes) in the Q2 response; #135 C3: next_observation_id / iou only for LINKED | SCHEMA_VALID, LINK_RECORD_FIELDS, LINK_RECORD_GAP_RULES, SEARCHING_TRIGGER_TIME, Q2_LINKS_FILE_HASH |
| U21 | observation_id hash segment vs records_file_sha256 cycle | §2.2 detection index: index_id / observation_id use the index key (manifest without index_id, content_sha256, records_ref, records_file_sha256); content_sha256 keeps records_file_sha256 | ID_DERIVED_FROM_HASH, RECORDS_OBSERVATION_IDS, CONTENT_HASH_RECOMPUTE, INDEX_MANIFEST_RULES |
| U22 | candidate_ref vs candidate_snapshot_sha256 cycle | §2.2 candidate snapshot: preimage without candidate_snapshot_sha256 and every candidate_ref | CANDIDATE_SNAPSHOT_HASH, CANDIDATE_REFS_AND_LIMITS |
| U24 | index_id / graph_id inside content_sha256 | §2.2 general documents: preimage without content_sha256 and the document's own id field (graph_id, parameter_set_id) | CONTENT_HASH_RECOMPUTE, ID_DERIVED_FROM_HASH, PARAMSET_INTEGRITY |
| U25 | how PARAMETER_GRID_MISMATCH / PARAMETERS_NOT_APPROVED are returned | #135 C6 + D69 (§2.3): reason codes, not error codes; grid mismatch is status UNKNOWN with empty results / timeline; unapproved parameters turn READY / COMPLETE into PARTIAL | Q2_FAIL_CLOSED_ON_GRID_MISMATCH, PARAMS_APPROVAL_GATES_STATUS, ERROR_RESPONSE_RULES |
| U26 | evidence summary schema_version, evidence_sha256 preimage, colour-less verdict, window_us | #135 C8 (§8.3): q-demo.candidate-evidence.v1; evidence_sha256 = canonical hash without itself and stats; color_verdict null without a colour condition; window_us is uncut (endpoint still U04) | CONTENT_HASH_RECOMPUTE, EVIDENCE_PRESENCE_RULES |
| U27 | session counters and fallback wall-clock use | D69 / D71 (§8.6, §8.7): searching_index and session_agent_rounds_used in every decision record (hashed); fallback wall time only in stats, never a cut-off | SCHEMA_VALID, DECISION_SESSION_COUNTERS |
| U28 | top-level vs per-camera stride_samples | D69 (§4.4): every per-camera stride_samples equals sampling.stride_samples | INDEX_MANIFEST_RULES |
| U29 | model_digest of a call that fails before the model reports one | D73 §14-20: the observed digest is null only for a provider-level failure (PROVIDER_UNAVAILABLE / PROVIDER_TIMEOUT) that keeps its failure code; offline replay does not call the model | SCHEMA_VALID, DECISION_LLM_CALL_RULES |
| U30 | decision_source / agent_used after the Agent takes NEXT_CANDIDATE on every candidate | D73 §14-21: the Controller returns to origin, the step is RULE_ONLY with no invented fallback_reason, accepted NEXTs still make agent_used true | COMMON_AGENT_FIELDS, DECISION_AGENT_EXHAUSTED_RETURN, Q2_RESPONSE_VS_DECISIONS |
| U31 | priority of the single reason when several hold | D73 §14-12: reason stays and reasons[] lists all, in a fixed priority, inside the output hash (the table itself: U33) | COMMON_REASONS_LIST, OUTPUT_HASH_RECOMPUTE |
| U36 | SWITCHING journal and stop / cancel wire of Q5 (#189) | D78 / §14-29 (a), §8.6: an accepted SWITCH is recorded SEARCHING -> SWITCHING, then SWITCHING -> PLAYING bound to the same decision / snapshot / entry / candidate without another model choice (kit 0.3.0-rc4) | SESSION_STATE_MACHINE, DECISION_FIELD_CONSISTENCY |
| U33 | fixed priority of reasons[] and the undefined INCOMPLETE_EVIDENCE | §14-12 (a) in the merged contract (#237): total order, other codes in ASCII order, degradation tail | `COMMON_REASONS_LIST`, `Q2_REASON_STATUS` |
| U32 | NEXT_CANDIDATE on a fetched candidate whose evidence has no observation | D73 §14-26: NEXT may cite an evidence hash bound to exactly that candidate and snapshot; SWITCH keeps its guard and needs a real entry observation; NO_PERSON_DETECTED never means 'certainly absent' | DECISION_SEQUENTIAL_ORDER, DECISION_EVIDENCE_AND_ENTRY, DECISION_SWITCH_GUARD, AGENT_DECISION_FORMAT |

## 8. 這套測試**不能**證明什麼

通過只代表「輸出符合契約的形狀與不變量」。它**不能**證明：

- 辨識品質：RT-DETR 有沒有偵測到人、框準不準、HSV 顏色判得對不對、漏檢率。
- 劇情正確：目標有沒有被接到正確的鏡頭、切鏡時間對不對、盲區假設合不合理、有沒有誤切到干擾對象。這些都要由**人工審核頁**看畫面判斷。
- 資料真實性：fixture 與測試只用 SYNTHETIC 資料；真實 safe RGB、真實索引的品質沒有被測。
- GT 隔離的實際行為：`provenance.gt_read == false` 只是回應自己的宣告；服務真的沒讀 GT，要靠程式審查與 `PROBE_FORBIDDEN_FIELD_REJECTED` 這類行為探測，不能靠這份報告擔保。
- 身分：全部結果都是「條件相符的候選」，沒有人能從這份報告推得「同一個人」。
- 效能與延遲（契約 §11 未訂門檻）。
- Agent 決策的好壞：只檢查它有沒有違反 Controller 規則，不評價它選得對不對。

測試包刻意不含劇情答案（誰在哪台鏡頭、什麼時間出現）。把任何 GT、產製路線或事件腳本放進這裡都是錯的；`test_kit_files_contain_no_gt_route_or_local_path` 會掃描 fixture 與 schema。

## 9. 測試有錯時怎麼回報

**Codex 不要直接改測試包**（`src/amidst/contracts/q_demo/`、`src/amidst/evaluation/q1q5_conformance.py`、`scripts/check_q1q5_conformance.py`、`tests/fixtures/q1q5_conformance/`、`tests/unit/test_q1q5_conformance.py`、本文件）。這些檔案由 Claude Code 維護。

1. 先判斷是後端錯還是測試錯：對照 §6 的契約章節與 `findings[].message`。
2. 若認為測試錯（誤報、檢查過嚴、檢查與契約條文不符），在 GitHub 開 issue，附：報告 JSON（含 `output_sha256`）、失敗的檢查 ID 與文件、被檢查的 JSON（或最小重現）、你認為正確的契約條文與章節。
3. 若是契約本身不清楚，列在 §7 的 U 編號下（或新增 U 編號）。
4. Claude 修改測試包並重跑 `tests/unit/test_q1q5_conformance.py`，在 issue 回覆新版本號。修改時 fixture 與違規案例一起更新；不改成「讓某個後端剛好通過」。

## 10. 維護備註

- Fixture 由 `tests/fixtures/q1q5_conformance/build_fixtures.py` 產生（`SYNTHETIC/valid/` 與 `SYNTHETIC/violations.json`）；測試會檢查已提交檔案與產生結果一致。
- 每個違規案例是一組套在合法 fixture 上的修補（`ops`）與預期失敗的檢查集合（`expect_fail`，必須完全相同，以免一個違規連鎖污染其他檢查）。`stage: "post"` 表示修補在重算 hash 之後套用，用來測 hash 本身錯誤的情況。
- Schema 檔在 `src/amidst/contracts/q_demo/schemas/`，`x-contract-status` 欄位標示「契約沒定義、本包暫定」的 schema（候選快照、說明文字、supported-classes、逐格紀錄的 `schema_version`）。驗證器 `mini_schema.py` 只實作這些 schema 用到的 JSON Schema 子集；用到不支援的關鍵字會直接報錯，不會靜默略過。
- 沒有檢查的條文（因為 UNKNOWN 或需要看畫面）見 §7、§8 與 §11。
- 修補操作除了 `set`／`del`／`append`／`swap`／`add_file`／`copy_file`／`rehash_decisions`，v0.2.0 多了 `rehash_manifest`（重算複製出來的索引 manifest 的 `content_sha256`）。`finalize()` 依契約 §2.2 的順序產生：索引鍵 → `index_id` 與 `observation_id` → 逐格紀錄 → `records_file_sha256` → manifest `content_sha256` → 參數組（含 `detection_index_ids`）→ 候選快照 hash 與 `candidate_ref`。
- fixture 的取樣格是 stride 2、`index_interval_us` 400000、`link_max_gap_us` 1200000（所以導出的 `link_max_gap_samples` 是 2）；這些數字是 SYNTHETIC，只為了讓「閾值剛好落在索引格上」「`gap_samples` 含失配格」「等於閾值的那一格仍可接上」三種情況都有例子。

## 11. v0.1.0 → v0.2.0：對齊契約 `258c7e2` → `3873ff2`

契約在這段期間經過 `b0a49f0`、`1d1e061`、`3873ff2` 三次提交（v0.1.0 綁的 `258c7e2` 在它們之前）。下表只列影響 schema、檢查器、fixture 或違規案例的條文；「正例」「違規例」指 `SYNTHETIC/valid/` 與 `violations.json`（`positive` 為 `expect_fail: []` 的案例）。

| 契約條文 | 測試包的處理 | 正例／違規例 |
| --- | --- | --- |
| §2.2 一般文件的 hash preimage（`graph_id`、`parameter_set_id`；U24） | `content_sha256` 的 preimage 去掉 `content_sha256`、文件自己的 id 欄位與 `stats`；id 的 `<hash16>` 是 `content_sha256` 前 16 碼。`parameter_set` 也受 `CONTENT_HASH_RECOMPUTE` 與 `PARAMSET_INTEGRITY` 檢查 | 單元測試 `test_graph_and_parameter_set_ids_exclude_their_own_id_from_the_hash`；違規 `paramset_id_not_from_hash`、`params_hash_bad`、`graph_id_not_from_hash` |
| §2.2 偵測索引（U21） | `index_id` 與 `observation_id` 的 hash 段取「索引鍵」（manifest 去掉 `index_id`、`content_sha256`、`records_ref`、`records_file_sha256`、`stats` 的 canonical hash 前 16 碼）；`content_sha256` 的 preimage 去掉 `content_sha256`、`index_id`，**含** `records_file_sha256`。同一個 `index_id` 出現兩個 `content_sha256` 是 `DataIntegrityError` | 單元測試 `test_index_key_is_independent_of_the_records_file`（改逐格紀錄：`content_sha256` 變、`index_id` 不變）；正例 `records_change_keeps_index_id`；違規 `index_id_from_content_hash`、`obs_segment_not_index_key`、`index_id_two_contents` |
| §2.2 候選快照（U22；U07 一併回答：`cand:<snapshot_hash16>:<rank>`） | `candidate_snapshot_sha256` 的 preimage 去掉它自己、`stats` 與每個候選的 `candidate_ref`；新檢查 `CANDIDATE_SNAPSHOT_HASH` | 單元測試 `test_snapshot_hash_excludes_candidate_refs_but_binds_the_rest`、`test_circular_snapshot_hash_is_rejected`；違規 `snapshot_hash_wrong`、`cand_order_swapped` |
| §4.2 manifest 的 detector 紀錄（權重檔、大小、授權、`load`、`class_map.num_classes`／`source_file_sha256`、`postprocess`、`nms`） | schema 補欄位（`load.strict` 只能是 `true`）；`INDEX_MANIFEST_RULES` 檢查來源檔 hash 不得代替 `class_map.content_sha256`、`load.num_classes == class_map.num_classes`、`nms.applied: false` 時 `iou` 為 `null` | 違規 `index_load_not_strict`、`index_class_map_source_hash`、`index_num_classes_differ`、`index_nms_iou_without_nms` |
| §4.4 來源格與索引格 | `sampling.per_camera[]` 多四個必填欄位；`index_interval_us == stride_samples × source_frame_interval_us`；新檢查 `RECORDS_INDEX_GRID`：索引格不得是 `NOT_SAMPLED`，不在索引格上的格只能是 `NOT_SAMPLED` | fixture 為 stride 2；違規 `index_interval_not_stride_product`、`records_not_sampled_on_grid`、`records_inferred_off_grid` |
| §5.3 `ranking_area_m2`／`ranking_area_refs` | camera graph 的 transition 多兩個必填欄位；非 `null` 的面積要附 refs；新檢查 `CANDIDATE_RANKING_AREA`：候選 `ranking_basis.overlap_area_m2` 等於 graph 的 `ranking_area_m2` | 違規 `graph_area_without_refs`、`cand_area_differs_from_graph` |
| §5.4 `relation_tier` 判定順序（4 → 3 → 1 → 2）、Q-03 不加次要鍵 | `_tier` 照順序判定（`OVERLAP` 含 `UNKNOWN` 邊是 3）；`ranking_basis` 只能有 `relation_tier`、`overlap_area_m2`、`camera_id` | 單元測試 `test_relation_tier_decision_order`；違規 `cand_overlap_with_unknown_edge_tier1`、`cand_secondary_key`、`cand_tier_wrong` |
| §8.2 `link_max_gap_us`、導出的 `link_max_gap_samples`、link 紀錄 `elapsed_us`／`gap_samples`、缺格判定 | 新檢查 `LINK_RECORD_GAP_RULES`（`elapsed_us` 是索引格間隔的倍數；`gap_samples = elapsed_us ÷ 間隔`，`LINKED` 再減 1；失配格要算進去）與 `SEARCHING_TRIGGER_TIME`（`decision_time_us` 是第一個 `gap_samples > link_max_gap_samples`、即 `elapsed_us ≥ link_max_gap_us` 的失配格的時間） | 正例：fixture 內等於門檻仍 `LINKED` 的紀錄；單元測試 `test_threshold_is_inclusive_on_the_linked_cell_and_exclusive_on_failing_cells`；違規 `link_gap_not_counting_failed_cell`、`link_gap_counting_linked_cell`、`link_elapsed_off_grid`、`searching_one_cell_early`、`searching_one_cell_late` |
| §8.2／§11 grid 檢查（`PARAMETER_GRID_MISMATCH`，fail closed） | 新檢查 `Q2_FAIL_CLOSED_ON_GRID_MISMATCH`：參數組與索引不合（`applies_to.index_interval_us` 與鏡頭不同、`link_max_gap_us` 不是間隔的正整數倍或小於一格、列出的 `link_max_gap_samples` 不等於導出值）時，配對的回應要是 `error_code: PARAMETER_GRID_MISMATCH`；合的時候不得回這個錯誤。不四捨五入 | 單元測試 `test_grid_check_derives_link_max_gap_samples`；正例 `grid_mismatch_fails_closed`；違規 `grid_applies_to_interval_differs`、`grid_gap_not_a_multiple`、`grid_gap_below_interval`、`grid_listed_samples_not_derived`、`grid_camera_interval_differs`、`grid_ok_but_rejected` |
| §8.3 覆蓋計數與判定順序、空窗、`PARTIAL_EVIDENCE` 要 `0 < evaluated < N` | 新檢查 `EVIDENCE_PRESENCE_RULES`（`N = evaluated + not_inferred + missing`，`not_sampled` 不算；空窗不是覆蓋完整；`NOT_EVALUATED` 先判；`NONE` 加 `UNKNOWN` 是 `PERSON_COLOR_UNKNOWN`；否定結果只在覆蓋完整時成立） | 正例：fixture 內每個分支各一份證據摘要；違規 `ev_unknown_mixed_as_no_color_match`、`ev_partial_with_nothing_evaluated`、`ev_empty_window_is_covered`、`ev_negative_over_gaps`、`ev_all_evaluated_not_evaluated`、`ev_not_sampled_counted_in_n`、`ev_strong_without_strong_box` |
| §8.3／§8.6 進入觀測（`entry_observation_id`、`entry_timestamp_us`、`decision_time_us`）、`NO_ALIGNABLE_OBSERVATION` | 證據摘要檢查進入觀測不早於 `decision_time_us`、在窗內；新檢查 `DECISION_EVIDENCE_AND_ENTRY`（SWITCH 必有進入觀測且等於證據的、`source_time_us ≥ decision_time_us`）；`DECISION_SWITCH_GUARD` 加入「規則不得跳過達到 guard 且有進入觀測的候選，沒有進入觀測就記 `NO_ALIGNABLE_OBSERVATION`」；`Q2_SWITCH_CAMERA_LEGAL` 加入「SWITCH 段從 `entry_timestamp_us` 起」 | 正例 `rule_no_alignable_observation`；違規 `ev_entry_before_decision_time`、`dec_switch_without_entry`、`dec_source_time_before_decision_time`、`q2_switch_before_entry`、`rule_skips_candidate_with_entry` |
| §2.3／§8.6 `agent_used`（N6） | `Q2_RESPONSE_VS_DECISIONS` 本來就以「至少一步 `decided_by: AGENT` 且 `accepted: true`」計算；補上只取證／只被拒時的案例 | 正例 `n6_tool_use_only_is_not_agent_used`；違規 `n6_agent_used_after_rejections_only` |
| §11 `parameter-set.v1`、`PARAMETERS_NOT_APPROVED` | 新 schema；新檢查 `PARAMS_APPROVAL_GATES_STATUS` | 違規 `params_not_approved_ready` |

**契約改了、但測試包沒有檢查的條文**（原因見 §7、§8）：

- §3.1／Q-11 同一事件共用一個 run 與 clock、不得跨 run 串接人物：沒有跨 run 的資料可比對（U20）。
- §5.4 出口判定（底邊中點落在 ROI 內，邊界另提）：提案值未核定，也需要影像座標與 ROI（`UNKNOWN`）。
- §8.4 `get_search_context`、`get_observation_summary` 等工具的回應：契約沒有 schema，也沒有端點（U04）。
- §8.6 `session_max_research_rounds`、`session_max_agent_rounds`、`fallback_budget_ms`、`research_interval_us`、Q-18 手動改選不重置 session 上限：記錄裡沒有可驗的計數（U27）。
- §8.6「兜底只在快照前 `top_k` 個候選內取證」：用 `DECISION_CANDIDATE_LEGALITY`（候選必須在快照內，快照不超過 `top_k`）間接涵蓋；不另外檢查「剩下的候選記 `NOT_EVALUATED`」。
- §8.6 `search_window_us` 與 `window_truncated_us` 的長度關係：窗長參數沒有值，`window_truncated_us` 的形狀未定（U05），schema 只收為選填欄位。
- §9／§11 Q-19 HSV 參數的資料來源：流程規定，不是輸出形狀。
- §10 儲存（不用 PG）：實作選擇，不是輸出形狀。

## 12. v0.2.1 → v0.3.0-rc1：對齊 staging 契約（#135 釐清、D69、D71）

依 #145，把 Codex 三份交接包（動態 8 份、linked 8 份、baseline runner 160 份 FIRST_CALL 錄製）裡的 FAIL／缺 context 逐項對照 staging 契約分類，**只修測試包本身違反已核准語意、#135 釐清、D69 或 D71 的地方**。§14 第 9–25 項的 PROPOSED 選項一律不實作（相關檢查維持 `3873ff2` 讀法，列為 U29–U32 等）。「方向」欄：**嚴**＝新增或收緊判定，**寬**＝原本判 FAIL／SKIP 的情況改為 PASS／不適用，**同**＝只是改形狀，判定強度不變。

| 契約條文 | 測試包的修正 | 方向 | 正例／違規例 |
| --- | --- | --- | --- |
| D69（§8.7）`searching_index`、`session_agent_rounds_used` | decision-record schema 加兩個必填整數欄位；新檢查 `DECISION_SESSION_COUNTERS`：SEARCHING 前是 0、同一快照同值、新快照變大；session 累計不減少、不少於已記錄的 LLM 呼叫數 | 嚴（原本這兩欄被當成額外欄位 FAIL，現在接受並驗它們的值） | 違規 `dec_missing_d69_counters`、`dec_searching_index_not_counted`、`dec_searching_index_changes_within_snapshot`、`dec_agent_rounds_below_calls`、`dec_agent_rounds_reset` |
| D69（§8.2、§8.7）`links_ref`／`links_sha256` | q2-response schema 加兩個必填欄位；新檢查 `Q2_LINKS_FILE_HASH`：`links_sha256` 等於該 session link journal 的精確 bytes SHA-256 | 嚴 | 違規 `q2_links_hash_wrong`、`q2_links_ref_missing`；單元測試 `test_links_sha256_is_the_exact_file_bytes` |
| D69（§8.2）`q-demo.link-record.v1`；#135 C3 | link-record schema 改成 v1（`schema_version`、`session_id`、`link_index`、`run_id`、`camera_id`、`frame_ref`、`local_segment_id`、`ambiguous_candidates`）；分類先認 link 再認逐格紀錄（v0.2.1 因 `frame_ref` 把 link journal 誤判為 `detection_records`，連帶 6 個 RECORDS 檢查 KeyError，#170）；link journal 依 `session_id` 綁定；新檢查 `LINK_RECORD_FIELDS`（一檔一 session、`link_index` 連號、`next_observation_id`／`iou` 只在 `LINKED` 有值、`ambiguous_candidates` 只在 `AMBIGUOUS_LINK`） | 嚴（link 規則原本根本沒執行） | 單元測試 `test_d69_link_records_with_frame_ref_are_not_detection_records`；違規 `link_without_schema_version`、`link_index_gap`、`link_unlinked_with_next`、`link_ambiguous_without_candidates`、`link_candidates_on_linked_cell`、`link_two_sessions_in_one_journal` |
| D69（每個 session 一份 append-only JSONL）；#178 | 0 byte 的 `<session>.decisions.jsonl`／`.links.jsonl` 認成空 journal（不是不明 schema）；`Q2_RESPONSE_VS_DECISIONS`、`Q2_SWITCH_CAMERA_LEGAL` 對空 journal 以「0 筆決策」判定，不再缺 context；`MODE_NOT_AUTHORIZED` 推論不套用在 0 筆決策上 | 寬（只限檔名是 session journal 的空檔；其他空檔照樣 FAIL） | 正例：valid 內的 `q2_noseed`（`NO_SEED`、兩個空 journal）；違規 `empty_journal_but_agent_attempted`、`empty_file_without_journal_name`；單元測試 `test_empty_journal_is_recognised_only_for_session_journals` |
| §8.3「起始條件沒有顏色時」（已核准）、§6.1；#211 | q2-request 的 `APPEARANCE` seed `color` 可為 `null`（鍵仍必填） | 寬 | 正例 `q3_q2_query_without_colour`、valid 的 `q2_noseed`；單元測試 `test_q2_appearance_seed_colour_may_be_null` |
| §8.3 無色只有四種值（已核准）；#135 C8 `color_verdict: null`；#153 | `EVIDENCE_PRESENCE_RULES` 依 Q2 請求（同 stem 或唯一的 Q2 請求）判斷有無顏色條件：無色時 `MATCH_STRONG` 只要有人物框、`color_verdict` 必須是 `null`、只允許四種值、`PARTIAL_EVIDENCE` 沒有人物框；有色時 `color_verdict` 不得是 `null` | 寬（無色 `MATCH_STRONG` 不再要求 `STRONG`）＋嚴（無色混入顏色判定、有色缺判定都 FAIL） | 正例：valid 的 `evidence_case_nocolor_strong`、`evidence_case_nocolor_partial`；違規 `ev_nocolor_verdict_strong`、`ev_nocolor_weak`、`ev_colour_query_null_verdict`、`ev_colour_verdicts_for_colourless_seed` |
| #135 C8 `evidence_sha256` preimage | `CONTENT_HASH_RECOMPUTE` 也重算證據摘要：去掉 `evidence_sha256` 與 `stats` 的 canonical hash | 嚴 | 違規 `ev_hash_wrong`；單元測試 `test_evidence_hash_preimage_excludes_itself_and_stats` |
| D69（§2.3、§14 第 5 項）；#135 C6 | `Q2_FAIL_CLOSED_ON_GRID_MISMATCH`：grid 不符時 Q2 回應必須是 `status: UNKNOWN`、`reason: PARAMETER_GRID_MISMATCH`、`timeline: []`；回成錯誤回應或照常執行都 FAIL；`PARAMETER_GRID_MISMATCH` 從錯誤碼清單移除 | 同（仍 fail closed，只改成 D69 的形狀） | 正例 `grid_mismatch_fails_closed`；違規 `grid_ok_but_rejected`、`grid_mismatch_as_error_code`、`grid_mismatch_still_executed` |
| D69（§4.4、U28） | `INDEX_MANIFEST_RULES`：逐台 `stride_samples` 必須等於頂層 `sampling.stride_samples` | 嚴 | 違規 `index_per_camera_stride_override`（原 `grid_camera_interval_differs` 改用不同來源影格間隔） |
| D71（§5.3）每台鏡頭都要有出口 | camera-graph schema：`exit_zones` 至少一筆 | 嚴 | 違規 `graph_camera_without_exit` |
| #135 C2（§5.2）`traversability` 只有兩個值 | region graph `traversability` 與 `path_traversability` 拿掉 v0.2.1 自行接受的 `UNKNOWN` | 嚴 | 違規 `graph_traversability_unknown` |
| #135 C4（§8.6）`window_truncated_us` | 候選必填；新檢查 `CANDIDATE_WINDOW_TRUNCATION`：半開區間、排序、不重疊、在未裁切的 `window_us` 內 | 嚴 | 違規 `cand_truncation_outside_window`、`cand_truncation_overlapping`、`cand_truncation_missing` |
| §8.6 轉移表（`RETURNED_TO_ORIGIN` → `SEARCHING` 經 `research_interval_us`）、§8.3 `decision_time_us` 是「這次 SEARCHING 開始的來源時間」 | `SEARCHING_TRIGGER_TIME` 只套用在 §8.2 link 觸發（`TEMP_LOST` → `SEARCHING`）的那次 SEARCHING；再次搜尋與手動改選不適用（再次搜尋的窗口錨點是 §14 第 18 項，PROPOSED） | 寬（link journal 修好後，再次搜尋的 `decision_time_us` 原本會被誤判成 link 觸發時間） | 單元測試 `test_searching_trigger_applies_only_to_the_link_trigger` |
| §6.1／§6.3 分頁（`page_size`、`cursor`、`results_total`）；#156 | `Q1_RESULT_ORDER`：取消「`next_cursor` 為 null ⇒ `results_total == returned_count`」；改為最後一頁的最後名次等於 `results_total`、第一頁（請求 `cursor` 為 null）從名次 1 起 | 寬（多頁的最後一頁）＋嚴（第一頁名次） | 正例 `q1_last_page_of_two`；違規 `q1_last_page_total_mismatch`、`q1_first_page_not_rank_1` |
| §2.3 `resolved_scope` 是實際用到的範圍 | `GRAPH_APPROVAL_GATES_STATUS`：回應的兩個 graph hash 都是 `null`（沒用圖，例如沒有 `region_ids` 的 Q1）時不適用，不再報缺 context | 同（原本是不影響結果的 SKIP） | 交接包 44 筆 Q1 回應 |

**rc1 刻意沒改、等 §14 決定的地方**（rc2 已依 D73 處理，見 §13）：失敗呼叫的 `model_digest: null`（§14 第 20 項）、Agent 全部 NEXT 後的 return 來源與 `agent_used`（第 21 項）、多原因優先序（第 12 項）、空證據候選的 NEXT 引用（#183）、`decisions_sha256` 的 preimage（第 17 項）、Q3 wire 與詞表（第 9、10 項）、多 run scope（第 11 項）。

## 13. v0.3.0-rc1 → v0.3.0-rc2：依 D73 對齊 §14 的決定

D73（2026-10-25，[#93 留言](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6395972547)）決定了 §14 各項。下表只列**影響檢查**的條目；其餘條目測試包不涉及，見本節末。「方向」：**嚴**＝新增或收緊判定，**寬**＝原本判 FAIL／不適用的情況改為 PASS／可判定。新增的 wire 欄位（`reasons[]`）在 D73 以前錄製的回應上**不存在**，所以相關檢查會 FAIL；這是「產品還沒做 D73」，不是回歸，要用 D73 之後的錄製重跑。

| D73 條目 | 測試包的處理 | 方向 | 正例／違規例 |
| --- | --- | --- | --- |
| §14-20 取得 digest 前就失敗：觀察 digest 可為 null 並保留失敗碼 | decision-record 的 `llm_calls[].model_digest` 可為 `null`；新檢查 `DECISION_LLM_CALL_RULES`：null 只在 `PROVIDER_UNAVAILABLE`／`PROVIDER_TIMEOUT` 且沒有 raw output；`PASS` 呼叫要有字串 digest 與 raw output hash（U29 已回答） | 寬（runner 的 6 個 `model_digest: null` FAIL）＋嚴（null 不能配 `PASS`／`SCHEMA_INVALID`） | 正例 `failed_call_has_no_digest`；違規 `llm_digest_null_on_pass`、`llm_digest_null_with_raw_output`、`llm_digest_null_on_schema_invalid` |
| §14-21 Agent 全選 NEXT 後回原鏡頭記為 `RULE_ONLY`，已接受的 NEXT 仍算 `agent_used` | `COMMON_AGENT_FIELDS` 不再因 `RULE_ONLY` ＋ `agent_used` true 無兜底而 FAIL；`Q2_RESPONSE_VS_DECISIONS` 的 `agent_used` 也計入「已接受的 Agent `NEXT_CANDIDATE`」；新檢查 `DECISION_AGENT_EXHAUSTED_RETURN`：AGENT_SEQUENTIAL 下由 `RULE_ONLY` 做的 `RETURN_TO_ORIGIN` 不得有 `fallback_reason`、只含 Agent 的 `NEXT_CANDIDATE`，且快照每個候選都被 Agent 走過（U30 已回答） | 寬（旗標組合）＋嚴（回原鏡頭前候選要走完） | 正例：valid 的 `q2_exhaust`；違規 `exhausted_return_with_fallback_reason`、`exhausted_return_with_candidate_left`、`exhausted_return_after_rule_next`、`exhausted_return_response_not_used` |
| §14-17 `decisions_sha256`／`links_sha256` 是 JSONL 原始 bytes 的 SHA-256；牆鐘耗時只在 `stats` 與 diagnostics | 新檢查 `Q2_DECISIONS_FILE_HASH`（與既有 `Q2_LINKS_FILE_HASH` 同法）；新檢查 `DECISION_NO_WALL_CLOCK`：RULE_ONLY 紀錄 `budget_used_ms` 為 0 且沒有 `latency_ms` 等欄位。AGENT_SEQUENTIAL 的 `budget_used_ms` 仍在被 hash 的紀錄內（D73 沒說要搬，U12 縮小後保留） | 嚴 | 單元測試 `test_decisions_sha256_is_the_exact_file_bytes`；違規 `decisions_hash_is_record_hashes`、`wall_clock_budget_in_rule_journal`、`wall_clock_latency_in_rule_journal` |
| §14-12 `reason` 加 `reasons[]`，固定優先序並進 hash | 三種回應 schema 加選填 `reasons`；新檢查 `COMMON_REASONS_LIST`：必須存在、無重複、`reasons[0] == reason`（`reason` 為 null 時是 `[]`）、已列名的代碼依優先序（缺必要資料〔grid、出口、時鐘〕＞ `TIME_SCOPE_PARTIAL` ＞ `GRAPH_NOT_APPROVED` ＞ `PARAMETERS_NOT_APPROVED`）。優先序取自 #144 審查 (a)，條文未合併（U33）；未列名的代碼（錄製裡的 `INCOMPLETE_EVIDENCE`）不排序。`OUTPUT_HASH_RECOMPUTE` 本來就把 `reasons` 算進 hash（U31 已回答） | 嚴 | 違規 `reasons_missing`、`reasons_first_is_not_reason`、`reasons_not_empty_without_reason`、`reasons_duplicate`、`reasons_wrong_priority`；單元測試 `test_reason_priority_ranks_only_the_listed_codes` |
| §14-9 規則與 LLM 解析同用 `q3-llm-output.v1`；缺時鐘回 `NEEDS_CLARIFICATION` | 規則解析的中間結果就是 `q3_llm_output`，同一份 schema 與 `Q3_LLM_*` 檢查；新檢查 `Q3_MISSING_CLOCK_CLARIFIES`：請求的 `context` 沒有 `clock_mapping_sha256` 時，不得 `PARSED` 成牆鐘查詢、也不得用 `CLOCK_MAPPING_MISSING` 當失敗碼（要 `NEEDS_CLARIFICATION`）。回應的 reason 代碼與 `parser_mode` 列舉仍開放（U09），測試包不強制 | 嚴 | 正例：valid 的 `q3_noclock`（規則解析、`llm_output` 同形）；違規 `q3_missing_clock_parsed_to_wall_query`、`q3_missing_clock_error_reason` |
| §14-11 第一版 Q1 只限單 run | 新檢查 `Q1_Q3_SINGLE_RUN_ONLY`：多 run 的 Q1 請求回 `UNKNOWN` 且沒有結果；Q1 回應範圍不得跨 run；Q3 請求跨 run 回 `NEEDS_CLARIFICATION`、不得解析出跨 run 的查詢。UNKNOWN 的 reason 代碼未訂，不強制（U20 縮小） | 嚴 | 違規 `q1_two_runs_ready`、`q1_response_spans_two_runs`、`q3_parsed_over_two_runs` |
| §14-26 NEXT 可引用綁定該候選與快照的 evidence hash | `DECISION_EVIDENCE_AND_ENTRY` 加：引用的證據必須屬於本紀錄的快照（`candidate_ref` 前綴）。無觀測的候選（`NO_PERSON_DETECTED`、`NOT_EVALUATED`）可以被 `NEXT_CANDIDATE`；SWITCH 仍要真實入口觀測與原 guard，檢查未放寬（U32 已回答） | 寬（NEXT 引用空證據）＋嚴（證據跨快照） | 正例：valid 的 `q2_exhaust`（三筆 NEXT 的證據有兩筆 `NOT_EVALUATED`、一筆 `NO_PERSON_DETECTED`）；單元測試 `test_evidence_must_belong_to_the_snapshot_of_the_record` |
| X1 Q2 找起點前檢查出口，缺漏回 `UNKNOWN`／`EXIT_ZONES_MISSING` | 新檢查 `Q2_EXIT_ZONES_PRECHECK`：`resolved_scope.camera_ids` 內有鏡頭沒有 `exit_zones` 時，整個回應 `UNKNOWN`、`reasons` 含 `EXIT_ZONES_MISSING`、`timeline` 為 `[]`，且該 session 沒有任何決策；沒有缺漏時不得用這個原因 | 嚴 | 違規 `graph_camera_without_exit`（schema 與此檢查一起 FAIL）、`exit_zones_missing_without_cause`；單元測試 `test_exit_zone_precheck_accepts_the_closed_answer` |
| X3 `ROUND_LIMIT` 涵蓋 `session_max_agent_rounds` | `DECISION_BUDGET_LIMITS`：`session_agent_rounds_used` 超過 `session_max_agent_rounds` 要記 `ROUND_LIMIT`；達到 session 上限時記 `ROUND_LIMIT` 也合法（參數組沒有該參數時維持舊判定） | 嚴＋寬 | 正例 `round_limit_from_session_cap`；違規 `session_round_cap_without_round_limit` |
| X2 Agent 故障後不自動重啟；使用者手動改選才可重啟 | 新檢查 `DECISION_NO_AUTO_AGENT_RESTART`：有 `fallback_reason` 的紀錄之後，Agent 步驟（`AGENT` 決定或 LLM 呼叫）之前必須有 `USER` 決定。前端提示畫面不在測試包範圍 | 嚴 | 正例 `agent_restarted_by_user`；違規 `agent_restarted_after_fallback` |
| §14-18 (a) 再次搜尋的新窗從當次 tick 起；§14-13 (a) 再次搜尋用 `research_interval_us` | `SEARCHING_TRIGGER_TIME`：`RETURNED_TO_ORIGIN` → `SEARCHING`（規則進入）的 `decision_time_us` 等於進入那一筆的 `source_time_us`，且不早於上次 return 的來源時間加 `research_interval_us`（下限，不要求剛好相等）。手動改選（USER）仍不適用：手動 port 的錨點沒寫（U35）；`exit_rule`／`boundary_inclusive` 仍待核 | 寬（原本不適用的再次搜尋現在判定） | 單元測試 `test_searching_trigger_after_a_return_starts_at_the_entering_tick`；參數組 fixture 加 `session_max_agent_rounds`、`research_interval_us` |
| §14-10 (a) 單一詞表 | `supported_classes.json` 也收 `schema_version: q-demo.supported-classes.v1`（欄位沿用 `class_labels`／`aliases`／`color_labels`，欄位名與 hash 欄位等契約條文，U02）。**錄製裡沒有這個檔時，`Q1_SUPPORTED_SET_CONSISTENCY` 仍是 `SKIPPED_NO_CONTEXT`** | 同 | 單元測試 `test_supported_classes_file_accepts_the_d73_schema_version` |

**D73 決定了、但不影響檢查或測試包不涉及的條目**：§14-23（保留已核准 §2.3，`llm_parse_used` 留在 output hash，所以測試包不用改）；§14-1–3（照 D65 條文，沒有變動）；§14-16（維持現行）；§14-19 (a)（`candidates_considered` 只記實際查取的前綴，`DECISION_SEQUENTIAL_ORDER` 本來就如此）；§14-27（不設 LOST 期限，沒有檢查）；§14-14（逐事件決策窗，窗寬另行核定，屬評分器不是契約層）；§14-15＋22（`media_ref`＋短效 grant＋start／poll：欄位與端點沒寫，U34，測試包仍讀現行 Q1 欄位）；§14-24、25（審核紀錄與預期清單，不在 Q1–Q5 輸出）；BL-SW（#189，Codex 尚未補 §14 選項，U36）；§14-4、新-C、Qwen3 預算（流程或量測決定，不是輸出形狀）。

**對三份交接包的預期**（重跑數字見 #127 說明與 #145）：`model_digest: null` 的 6 個 FAIL 消失；原本不適用的 88 筆再次搜尋改成判定；`COMMON_REASONS_LIST` 對每份 D73 以前錄製的回應 FAIL（錄製裡沒有 `reasons[]`）；`Q3_MISSING_CLOCK_CLARIFIES`、`Q1_Q3_SINGLE_RUN_ONLY`（多 run 分支）、`Q2_EXIT_ZONES_PRECHECK`（缺出口分支）、`DECISION_AGENT_EXHAUSTED_RETURN` 在三包內沒有觸發的資料，所以它們靠 fixture 證明抓得到，不能代表產品已通過。

## 14. v0.3.0-rc2 → v0.3.0-rc3：綁定已合併的契約檔（#237、D78–D82）

契約檔由 PR #237 合併進 `codex/q1q5-staging`（merge commit `83da40f`；檔案 SHA-256 `b700bf86…df04`）。測試包本來就只在報告與文件記錄契約 commit 與檔案 SHA-256、不依賴契約檔在 repo 內，所以只更新綁定常數，不另做 merge commit 把契約檔放進本分支。

| 契約條文 | 測試包的處理 | 方向 | 正例／違規例 |
| --- | --- | --- | --- |
| §14-12 (a) reasons 全序：`MULTI_RUN_SCOPE_UNRESOLVED → INDEX_NOT_AVAILABLE → CLOCK_MAPPING_MISSING → TRACKING_SCOPE_MISSING → GRAPH_NOT_AVAILABLE → PARAMETER_GRID_MISMATCH → EXIT_ZONES_MISSING → SEED_CAMERA_NOT_TRACKED → EMPTY_CAMERA_SCOPE → USER_STOPPED`，其後其他既有原因碼按 ASCII，最後 `TIME_SCOPE_PARTIAL → GRAPH_NOT_APPROVED → PARAMETERS_NOT_APPROVED → INCOMPLETE_EVIDENCE` | `COMMON_REASONS_LIST` 改為對**所有**代碼檢查全序（rc2 只排六個代碼）；`INCOMPLETE_EVIDENCE` 現在是契約定義的尾列碼；U33 轉為已解決 | 嚴 | 正例 `q2_noscope`；違規 `reasons_new_codes_wrong_order`、`reasons_tail_before_other_code`（既有 `reasons_wrong_priority` 保留）；單元測試 `test_reason_total_order_of_the_merged_contract` |
| §5.4／§2.3 新原因碼 `TRACKING_SCOPE_MISSING`、`SEED_CAMERA_NOT_TRACKED`（及 grid／出口／時鐘等阻擋碼）回 `UNKNOWN`，`timeline` 為空 | 新檢查 `Q2_REASON_STATUS` | 嚴 | 違規 `q2_scope_missing_not_unknown`；`grid_mismatch_still_executed` 現在同時觸發它 |
| D82／§8.7 使用者 stop：Q2 回 `PARTIAL`＋`USER_STOPPED`，不新增 STOPPED status | `Q2_REASON_STATUS`：`USER_STOPPED` 必須是 `PARTIAL`；`status` 清單不加 `STOPPED`（外層 job 的 STOPPED 不在測試包範圍） | 嚴 | 違規 `q2_user_stopped_complete`；單元測試 `test_q2_user_stopped_is_partial_and_blocking_reasons_are_unknown`。沒有 USER_STOPPED 的完整錄製（含 journal）fixture：UNKNOWN |
| D78 `q-demo.link-record.v2`：`matching_audit` 必填（物件或 null）；v1 只用於重播舊錄製 | 新 schema `link-record.v2`；v1 仍可讀（`LINK_RECORD_MATCHING_AUDIT` 對 v1 不適用）；fixture 的 link journal 改為 v2；新檢查判 audit 與主欄位的一致性 | 嚴 | 違規 `link_matching_audit_missing`、`link_matching_audit_null_after_gap`、`link_audit_pair_iou_differs`、`link_audit_event_on_unlinked`；單元測試 `test_link_record_v1_is_historical_and_v2_audit_is_judged` |
| §6.1 `str.casefold()` 比對 `class_label` 與 alias 鍵 | `Q1_SUPPORTED_SET_CONSISTENCY` 以 casefold 比對 alias；Q1 preimage（D80 的 `query_sha256`）**沒有**重算：需要凍結 bindings 的 hash，錄製沒帶；U17 改寫為待後續版本 | 嚴／UNKNOWN | 單元測試 `test_q1_class_label_is_matched_with_casefold` |

**刻意沒做**：`reference_iou ≥ link_iou_min` 的 guard 檢查（fixture 與三包的參數組沒有 `link_iou_min`，加了會讓報告變 `INCOMPLETE`）；supported-classes 欄位名換成契約的 `version`／`class_map_sha256`／`color_vocabulary`；endpoint、`agent-decision.v2`、`tracking_scope` pin 的檢查。這些列為後續版本，不宣稱已涵蓋。

**對既有錄製的預期**：舊錄製沒有 `reasons[]`（D73 之前），`COMMON_REASONS_LIST` 仍對每份回應 FAIL；它們的 link journal 是 v1，`LINK_RECORD_MATCHING_AUDIT` 不適用。要等產品依 D73／D78 補欄位後重錄才會轉綠。

## 15. v0.3.0-rc3 → v0.3.0-rc4：對齊 D78 SWITCHING 兩段 journal 與 D81 scope pin

綁定不變（契約檔 SHA-256 `b700bf86…df04`，在 staging `680ca357` 重新核對相同）。rc3 對 #242 的 176 份新錄製重跑時有 64 份 FAIL；逐項對照契約條文後，下表只改條文有寫的部分。條文沒寫的欄位不放行，列為產品偏差（見 PR #127 的 rc4 結果紀錄）。

| 契約條文 | 測試包的處理 | 方向 | 正例／違規例 |
| --- | --- | --- | --- |
| §8.6 轉移表「`SEARCHING` → 決定 `SWITCH` 被接受 → `SWITCHING` → `PLAYING`」、§8.6 D78 條「接受 SWITCH 時記 SEARCHING→SWITCHING，再記 SWITCHING→PLAYING，綁同一 decision／snapshot／entry；不虛增一次模型選擇」、§14-29 (a)（(b) 原子 journal 歷史未採用） | `SESSION_STATE_MACHINE`：`SEARCHING` 可到 `SWITCHING`，不再有 `SEARCHING → PLAYING`（USER 手動改選仍可）。`SWITCHING → PLAYING` 那筆必須緊接在被接受的 `SEARCHING → SWITCHING` SWITCH 之後，`cause_decision_id` 等於該筆 `decision_id`，`candidate_snapshot_sha256`、`entry_observation_id`、`executed_candidate_ref`、`decision_time_us`、`session_agent_rounds_used` 相同；其他紀錄不得帶 `cause_decision_id`。`DECISION_FIELD_CONSISTENCY`：被接受的 SWITCH 結束於 `SWITCHING`；離開 `SWITCHING` 的那筆沿用 SWITCH 的 `decided_by`、不得有自己的 LLM 呼叫，所以「Agent 決策要記 LLM 呼叫」不套用在它身上。U36 轉為已解決，新增 U37 | 寬（新狀態）＋嚴（綁定、禁止原子切換） | fixture `q2_rule`、`q2_agent` 改為兩段 journal；單元測試 `test_d78_switch_goes_through_switching`、`test_d78_switching_to_playing_binds_the_accepted_switch`、`test_d78_switching_record_adds_no_llm_call` |
| `cause_decision_id` 這個鍵名：契約條文只寫「綁同一 decision」，鍵名出自 D78 決定留言（#93 issuecomment-6398428243「用cause_decision_id及同snapshot/entry/candidate綁定」） | `decision-record.v1` schema 加選填 `cause_decision_id`（字串）。D78 收據另提的 `control_reason`、`provider_cancelled` 不在契約條文，**不放行** | 寬 | 同上；`test_d81_journal_input_pins_only_carry_the_scope_pin` 也確認 `control_reason` 仍被拒 |
| §2.3 共通 `resolved_scope` 列出 `tracking_scope_sha256`，「沒用到的填 null，不省略鍵」；§5.1 D81「`resolved_scope.tracking_scope_sha256`、Q2 session／journal 的輸入 pins 及 output hash 必須帶入（未使用時明確 null）」 | `common.schema.json` 的 `resolved_scope` 加**必填**的 `tracking_scope_sha256`（sha256 或 null），Q1／Q2／Q3 三種回應都適用 | 寬（新欄位）＋嚴（必填） | fixture 全部回應帶此鍵（Q1／Q3 為 null）；單元測試 `test_d81_resolved_scope_names_the_tracking_scope_pin` |
| §5.1 D81「journal 的輸入 pins」 | `decision-record.v1` 加**必填** `input_pins`，內容恰為 `{tracking_scope_sha256}`（sha256 或 null），其他鍵不放行。鍵名 `input_pins` 是產品對「輸入 pins」的寫法，契約沒寫鍵名（U37） | 寬＋嚴 | fixture 每筆決策都帶 `input_pins`；單元測試 `test_d81_journal_input_pins_only_carry_the_scope_pin` |
| §5.1 D81「scope 與兩圖共同成為來源 binding」；§5.4 第 0 步「Q2 在找起點之前先讀已驗 pin 的 `tracking_scope`」「缺 `tracking_scope` 回 `UNKNOWN`／`TRACKING_SCOPE_MISSING`……不找 seed、不開 session」 | `Q2_RESPONSE_VS_DECISIONS`：每筆決策的 `input_pins.tracking_scope_sha256` 等於回應的 `resolved_scope.tracking_scope_sha256`；scope pin 是 null 時只允許「沒開 session、在讀 scope 之前就停下」的 `UNKNOWN`；其他 status（包括 `NO_SEED`，因為它找過起點）、有決策紀錄或 timeline 非空都判 FAIL | 嚴 | fixture `q2_*` 帶 SYNTHETIC scope pin、`q2_noscope` 為 null；單元測試 `test_d81_q2_scope_pin_matches_the_journal_and_is_set_for_a_session` |
| §7.6「每次 LLM 呼叫（Q3、說明、Q5）都記錄……Ollama 回報的 digest」；D73 §14-20「在tags前已失敗時，觀察digest允許null並保留failure code，不能拿預期digest冒稱實測」 | `q3-parse-response.v1` 的 `llm_call.model_digest` 可為 null；`Q3_RESPONSE_RULES`：null 只允許在解析沒被採用（`llm_parse_used: false`）、沒有原始輸出、而且 `fallback_reason` 是 `PROVIDER_UNAVAILABLE`／`PROVIDER_TIMEOUT` 時 | 寬（有條件） | 單元測試 `test_q3_null_digest_only_on_a_provider_failure` |

**fixture 建構**：`build_fixtures.py` 以 `switch_done()` 從 SWITCH 紀錄導出 `SWITCHING → PLAYING` 紀錄；違規例改到 SWITCH 紀錄時，`finalize()` 會重新導出那一筆，讓違規只打到原本要測的檢查。綁定本身的違規在單元測試裡判。

**刻意沒做**：測試包沒有 tracking-scope 文件的 kind，所以不重算 `tracking_scope_sha256` 與 scope 原始檔 bytes 是否相符（錄製也沒帶 scope 檔）；`control_reason`、`provider_cancelled`、外層 `session-job.v1` 的 STOPPED 不在契約條文，不放行也不檢查。

## 16. v0.3.0-rc4 → v0.3.0-rc5：`tracking_scope` 文件與原始 bytes pin

綁定不變（契約檔 SHA-256 `b700bf86…df04`）。起因：Codex 的 #257 讓 Q2 錄製目錄多一個 `tracking_scope.json`，rc4 不認得它，`DOCUMENT_LOADABLE` 判 FAIL（unclassified，no recognised schema_version；見 PR #257 的複核留言 N1）。rc5 補上這個 kind，並把 §15 列為「刻意沒做」的 pin 檢查做完。

| 條文 | 測試包的處理 | 方向 | 正例／違規例 |
| --- | --- | --- | --- |
| §5.1 D81：scope 是獨立文件，pin 是原始檔 bytes | 新 kind `tracking_scope`，`schema_version` 為 `q-demo.r004-tracking-scope.v3`。G4 的 scope 與 #257 工程用合成 scope 使用同一個 `schema_version`，以 `status`／`G4_approved`／`north_floor_y_gt_12`／`overlap_pairs_deferred` 的值區分；`north_floor_y_gt_12` 與 `overlap_pairs_deferred` 只要求鍵存在，值不限（真 scope 與合成 scope 的值不同）。契約沒有這份文件的 JSON Schema，`SCHEMA_VALID` 對它不適用（記為略過），改由 `TRACKING_SCOPE_STRUCTURE` 判 | 寬（新 kind） | 正例 `tracking_scope.json`；違規例 `tracking_scope_schema_unknown`（未知版本，仍判 `DOCUMENT_LOADABLE` FAIL）、`tracking_scope_key_missing` |
| §5.1 D81：結構（鍵集、status、鏡頭分割、有向鏡頭對矩陣） | `TRACKING_SCOPE_STRUCTURE`：鍵集恰為 v3 的 9 個；status ∈ PROPOSED／FROZEN／APPROVED；`G4_approved` 為布林；query = tracking ∪ query-only 且 tracking 與 query-only 不相交；`directed_pairs` 涵蓋 query 鏡頭的每個有序對，TRANSITION 對有 `transition_id` 且無 `reason`，EXCLUDED 對有 `reason` 且無 `transition_id`；有 camera graph 時，tracking 鏡頭等於 graph 的鏡頭、TRANSITION 對恰為 graph 的 transitions | 嚴 | `tracking_scope_pair_missing`、`tracking_scope_transition_unknown` |
| §5.1 D81：pin 是原始檔 bytes，兩圖各帶一把相同的 pin | `TRACKING_SCOPE_BYTES_PIN`：scope 檔原始 bytes 的 SHA-256 等於每份 region／camera graph `inputs` 中唯一的 `tracking-scope:` pin。不重新序列化再算 hash（縮排或換行不同就是不同的檔） | 嚴 | `tracking_scope_bytes_changed`、`tracking_scope_graph_pin_differs`；單元測試 `test_rc5_reserialised_scope_no_longer_matches_the_pin` |
| §2.3／§5.1 D81：`resolved_scope.tracking_scope_sha256`，沒用到填 null | `RESPONSE_SCOPE_PIN_IS_FILE_BYTES`：非 null 的 pin 必須等於某份已提供 scope 檔的原始 bytes SHA-256；null 不適用（Q1／Q3 沒用 scope 時為 null，合法）；有非 null pin 卻沒帶 scope 檔 → `SKIPPED_NO_CONTEXT`，不判 FAIL。journal 的 `input_pins` 與回應 pin 的一致性仍由 `Q2_RESPONSE_VS_DECISIONS` 判，所以 journal 也間接綁到檔案 bytes | 嚴 | `tracking_scope_response_pin_differs`；單元測試 `test_rc5_null_scope_pin_in_q1_q3_is_allowed_without_a_scope_file` |

**fixture 建構**：`build_fixtures.py` 現在產出 `tracking_scope.json`（與 #257 `bind_engineering_scope` 同樣的位元組慣例：排序鍵、緊湊分隔、ASCII、無結尾換行；`serialise()` 對這個檔名特別處理），`TS_SHA` 由這些 bytes 算出，兩份圖的 `inputs` 加上同一把 pin。因此 SYNTHETIC 圖的 `content_sha256` 與全部帶 pin 的回應、journal 的 hash 都跟著變；舊 fixture 的 pin 是憑空編的 `H("SYNTHETIC-tracking-scope")`，沒有對應檔案。

**對 #257 輸出的結果**（用 #257 的 `fixture_api()` 產生 Q2 錄製，分支 `codex/q1q5-scope-pins-rc4` 的 `b761a33`，`export_domain` 輸出 13 個檔）：rc4 為 PASS 171／FAIL 1（`DOCUMENT_LOADABLE`，就是 N1）；rc5 為 **PASS 176／SKIP 0／FAIL 0**。`tracking_scope.json` 原始 bytes 的 SHA-256 與 Q2 `resolved_scope`、每筆 decision 的 `input_pins`、兩圖的 `tracking-scope:` input 全部一致。這是單一合成 Q2 錄製的數字，不是 #242 的三包正式錄製。任務預期的 PASS 210／SKIP 2／FAIL 0 沒有重現：用 #257 的 `fixture_api()` 只得到上面這一份 Q2 錄製，210／2 這組數字對應的錄製組成 UNKNOWN，不宣稱重現。

**刻意沒做**：不驗證 scope 內容是否為 r004 的 G4 核可（`G4_approved`／`status` 只檢查型別與已知值，不判核可與否；合成 scope 的 `G4_approved: true` 是工程語意，不代表 r004 核可）；`north_floor_y_gt_12`／`overlap_pairs_deferred` 的值不檢查；沒有 scope 檔時不判舊錄製失敗。

### 給 #242 的同步說明

`scripts/rerecord_q1q5_rc3.py` 把 kit 綁在固定 commit，kit 一改版就會被它擋下，這是設計行為。

1. **新的 kit commit SHA**：`claude/q1q5-conformance-kit` push 之後的 head，也就是 PR #127 的 `headRefOid`。文件無法寫入自己的 commit SHA；實際值在 #127 的結果紀錄與 #242 的留言中。舊值 `c4e96979ad559d73cbd6a265e905100a1cf7f4f9` 是 rc4 head。
2. **`KIT_COMMIT`**（`scripts/rerecord_q1q5_rc3.py` 第 22 行）改成上面的新 SHA（完整 40 碼）。它同時用在計畫檔的 `kit_commit`、`headRefOid` 比對與結果紀錄，三處由同一個常數帶，改一處即可。
3. **`RC4_HEAD_CHANGED_REVIEW_REQUIRED`**：這是第 162 行 `require(kit["headRefOid"] == KIT_COMMIT, ...)` 的錯誤碼。`KIT_COMMIT` 改好後它就不會再觸發；錯誤碼字串本身可以保留，也可以改名為 `KIT_HEAD_CHANGED_REVIEW_REQUIRED`（含 rc5 後的意義）。改名的話，同檔與測試中對這個字串的引用要一起改。不要為了讓比對通過而拿掉那個 `require`，它的用途是讓 kit 的任何後續變動都要經人複核。
4. `expected_recordings: 176` 與契約檔 SHA（`b700bf86…df04`）不用改；rc5 沒有改契約綁定。
5. 用新 kit 重跑的三包錄製，Q2 目錄裡的 `tracking_scope.json` 會被 `TRACKING_SCOPE_*` 與 `RESPONSE_SCOPE_PIN_IS_FILE_BYTES` 三項檢查涵蓋，報告的 `by_check` 多這三項；檢查總數會比 rc4 多，不能直接拿 rc4 的 PASS 數量當期望值。
