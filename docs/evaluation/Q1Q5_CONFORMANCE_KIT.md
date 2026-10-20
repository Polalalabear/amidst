# Q1–Q5 合約符合性測試包（Conformance Kit）

狀態：**v0.1.0，綁定契約草案**。契約本身還是 DRAFT（待 Codex 確認、使用者核准）；本測試包跟著契約改版，不是契約的一部分。

| 綁定項目 | 值 |
| --- | --- |
| 契約 | `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md`，PR [Polalalabear/amidst#86](https://github.com/Polalalabear/amidst/pull/86)，分支 `claude/q1q2-contract-v1` |
| 契約 commit | `258c7e2cf24b37ab69a5c4578fe23cc5f000d724`（本包開工時 PR #86 的 head） |
| 契約檔 SHA-256 | `5336f6c3e2a1e0ca590f768adeed1849be764a6886eda609cc9327c62034c95f` |
| 測試包版本 | `0.1.0`（`amidst.evaluation.q1q5_conformance.KIT_VERSION`）；每份報告都記錄這兩項 |

契約改版後，測試包要同步改版並更新上表與常數 `CONTRACT`；舊報告的契約 commit 不同就不能當新契約的證據。

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
| `parameter_set.json` | 參數組（§4） |
| `supported_classes.json` | 本測試包自己的輸入：`class_map` 的標籤、別名表、顏色詞彙（契約沒給可讀的清單，U02） |

缺少某個上下文時，依賴它的檢查報告 `SKIPPED_NO_CONTEXT`，不算通過，但也不擋整體結果；要擋就把檔案放進目錄。

## 4. 參數組（契約 §11）

門檻數字一律由參數組讀入，**測試包沒有任何預設值**。`parameter_set.json` 是平的 JSON 物件（或把值放在 `values` 底下，U18），鍵名用 §11 的名稱：

- 目前會讀的：`index_score_floor`、`top_k`、`switch_min_presence`、`agent_max_rounds`、`agent_total_budget_ms`、`q3_max_llm_attempts`。
- 沒有鍵、值是 `null`、`""`、`"待約定"`、`"TBD"`，或型別不對（數字參數給了布林或字串），都算未設定，依賴它的檢查回報 `SKIPPED_PARAM_UNSET`。
- `index_score_floor` 缺時，會退而讀索引 manifest 的 `detector.index_score_floor`（它是資料，不是測試包的預設）。
- 參數組的 `content_sha256` 要能重算，回應 `resolved_scope.parameter_set_*` 要對得上。
- 參數值**由使用者核定**（契約 §11）。`tests/fixtures/` 內的值是 SYNTHETIC 的任意數字，不是提案值，不要抄進真正的參數組。

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
| `CONTENT_HASH_RECOMPUTE` | §2.1, §2.3, §3.1, §4.2, §5.2–§5.3, §8.7 | `detection_index`、`region_graph`、`camera_graph`、`clock_mapping`、`decision_record` | content_sha256 equals the canonical hash of the document without itself, stats and (index/graph) its self-derived id |
| `OUTPUT_HASH_RECOMPUTE` | §2.1, §2.3, §7.5 | `q1_response`、`q3_response`、`q2_response` | output_sha256 recomputes without output_sha256 and stats; hashed body has no timing fields or explanation text |
| `ID_DERIVED_FROM_HASH` | §2.2 | `detection_index`、`region_graph`、`camera_graph` | index_id / graph_id use scene_revision and the first 16 hex chars of content_sha256 |
| `PARAMSET_INTEGRITY` | §11 | `parameter_set` | Parameter set has parameter_set_id and a recomputable content_sha256 |
| `ERROR_RESPONSE_RULES` | §2.3, v1.1 §7 | `error_response` | Error responses use a known error code with the matching HTTP status (shape is provisional) |
| `COMMON_GT_READ_FALSE` | §2.3, §9 | `q1_response`、`q3_response`、`q2_response`、`detection_index` | provenance.gt_read is exactly false |
| `COMMON_IDENTITY_UNCONFIRMED` | §2.3, §7.5, §8.7 | `q1_response`、`q3_response`、`q2_response` | identity_verdict is UNCONFIRMED and no text claims 'the same person'（啟發式） |
| `COMMON_AGENT_FIELDS` | §2.3, §7.3, §8.6 | `q1_response`、`q3_response`、`q2_response` | agent_used / agent_attempted / llm_parse_used / decision_source / fallback_used / fallback_reason are mutually consistent |
| `COMMON_STATUS_REASON` | §2.3, §3.3, §5.1, §6.3, §7.4, §8.7 | `q1_response`、`q3_response`、`q2_response` | status is in the endpoint's closed list; READY has no reason; PARTIAL has one |
| `TIME_COVERAGE_INTERNAL` | §3.3, §4.4, §6.3, §8.7 | `q1_response`、`q2_response` | Partial wall-clock coverage is never READY/COMPLETE/NO_MATCH; uncovered ranges listed; OUT_OF_RANGE queries nothing |
| `TIME_COVERAGE_RECOMPUTE` | §3.1, §3.3 | `q1_response`、`q2_response` | Resolved source ranges, coverage_complete and uncovered_wall_ranges equal the values computed from the clock_mapping (wall requests only) |
| `SCOPE_HASH_LINKS` | §2.3, §4.2, §5, §11 | `q1_response`、`q3_response`、`q2_response` | resolved_scope hashes / ids point at the supplied index, graphs, clock mapping and parameter set |
| `GRAPH_APPROVAL_GATES_STATUS` | §5.1 | `q1_response`、`q2_response` | A response built on a DRAFT graph is not READY/COMPLETE and says GRAPH_NOT_APPROVED |
| `Q1_MIN_SCORE_FLOOR` | §6.1, §4.2 | `q1_request`、`q1_response` | query_min_score is never below index_score_floor; a request below it is answered with FORBIDDEN_INFERENCE_INPUT |
| `Q1_UNSUPPORTED_HANDLING` | §6.1, §6.3 | `q1_response` | UNSUPPORTED_* statuses return no results; a colour condition on a non-person class is UNSUPPORTED_* |
| `Q1_SUPPORTED_SET_CONSISTENCY` | §6.1, §6.2 | `q1_response`、`q1_request` | Class / colour support decision agrees with the supplied class map, alias table and colour vocabulary |
| `Q1_STATUS_VS_COVERAGE` | §3.3, §4.4, §6.3 | `q1_response` | READY needs a full inference pass and a result; NO_MATCH never hides un-inferred, missing or uncovered time; PARTIAL when anything is missing |
| `Q1_RESULT_ORDER` | §6.3 | `q1_response` | Results ordered by first match time then camera_id, ranks consecutive, segments ordered and half-open, counts consistent |
| `Q1_NONE_CATEGORIES_DISJOINT` | §6.3 | `q1_response` | A camera appears in only one of results / no_match_cameras / not_evaluated_cameras |
| `Q3_LLM_OUTPUT_STRICT` | §7.1 | `q3_llm_output` | LLM output has no extra field and a consistent clarification flag |
| `Q3_LLM_TERMS_LITERAL` | §7.1 | `q3_llm_output` | class/colour/time/camera/region terms are fragments of the user's original text |
| `Q3_RESPONSE_RULES` | §7.2–§7.4 | `q3_response` | structured_query only when PARSED; clarification and failure statuses never execute; LLM call recorded when LLM was used |
| `Q3_STRUCTURED_QUERY_SCHEMA` | §7.2 step 4 | `q3_response` | The assembled structured_query validates against the Q1 or Q2 request schema |
| `Q3_FALLBACK_CONSISTENCY` | §7.3 | `q3_response` | A rule parse after an LLM attempt (LLM_WITH_RULE_FALLBACK) records fallback_used with a provider reason |
| `Q3_ATTEMPTS_WITHIN_PARAM` | §7.2, §11 | `q3_response` | llm_call.attempts <= q3_max_llm_attempts |
| `EXPLANATION_CITED_REFS` | §7.5 | `explanation` | Every cited ref appears in the explained response; text claims no identity; at least one ref is cited (explanation wrapper is provisional)（啟發式） |
| `CANDIDATE_ORDER_D28` | §5.4, v1.1 §6.1 | `candidate_snapshot` | Candidates sorted by relation_tier, overlap_area_m2 desc (null last), camera_id; ranks consecutive; one entry per camera; ranking_basis has no detection/colour keys |
| `CANDIDATE_TOPOLOGICAL_EXCLUDED` | §5.2–§5.4 | `candidate_snapshot` | TOPOLOGICAL_ONLY paths never appear as candidates; excluded ones carry TOPOLOGICAL_ONLY_EDGE; agrees with the camera graph when supplied |
| `CANDIDATE_REFS_AND_LIMITS` | §5.4, §8.4, §11 | `candidate_snapshot` | candidate_ref embeds the snapshot hash prefix and rank; candidate count <= top_k |
| `DECISION_FIELD_CONSISTENCY` | §8.4, §8.6, §8.7 | `decision_record` | accepted/rejection_code, decided_by, switch_mode, fallback_reason, executed action and state_after agree |
| `DECISION_CANDIDATE_LEGALITY` | §5.4, §8.4 | `decision_record` | The candidate switched to is in the legal snapshot (never a TOPOLOGICAL_ONLY / excluded / invented one) and its camera is a candidate camera |
| `DECISION_SEQUENTIAL_ORDER` | §8.4, §8.6 | `decision_record` | Candidates are taken in rank order without skipping; evidence is fetched before a switch/next; a switch is the last step and follows NEXT_CANDIDATEs |
| `DECISION_SWITCH_GUARD` | §8.4, §8.6, §11 | `decision_record` | An accepted SWITCH only targets a candidate whose target_presence reaches switch_min_presence |
| `DECISION_REJECTION_CORRECTNESS` | §8.4 | `decision_record` | A submission that violates the controller rules (unknown ref, stale snapshot, no evidence, no citation) was not accepted |
| `DECISION_BUDGET_LIMITS` | §8.6, §11 | `decision_record` | rounds_used / budget_used_ms respect agent_max_rounds / agent_total_budget_ms unless the matching fallback is recorded |
| `SESSION_STATE_MACHINE` | §8.6 | `decision_record` | Each record is a legal §8.6 transition; step_index strictly increases and source time never goes backwards within a session |
| `Q2_RESPONSE_VS_DECISIONS` | §2.3, §8.6, §8.7 | `q2_response` | agent_used / agent_attempted / fallback_used / first fallback_reason / decision_source equal what the session's decision records imply |
| `Q2_SWITCH_CAMERA_LEGAL` | §5.4, §8.6 | `q2_response` | Every SWITCH segment cites an accepted SWITCH decision whose snapshot candidate is exactly that camera |
| `Q2_TIMELINE_STRUCTURE` | §8.7 | `q2_response` | Timeline ordered, contiguous, half-open; GAP segments never carry a position; observation-driven ON_CAMERA segments; status matches the timeline |
| `AGENT_DECISION_FORMAT` | §8.4 | `agent_decision` | Submission has a well-formed candidate_ref bound to its snapshot, citations for SWITCH, and a rationale for NEXT_CANDIDATE |
| `GRAPH_STRUCTURE` | §5.1–§5.3 | `region_graph`、`camera_graph` | Graph ids unique, references resolve inside the graph, closed lists respected, approval fields coherent |
| `GRAPH_CROSS_REFERENCES` | §5.2, §5.3 | `camera_graph` | Camera graph agrees with its region graph: hash link, paths follow edges, traversability is the weakest edge, unknown state propagates |
| `CLOCK_MAPPING_RULES` | §3.1 | `clock_mapping` | wall_origin's UTC offset matches the declared IANA timezone on that date; declared (not observed) clock |
| `INDEX_MANIFEST_RULES` | §4.2, §4.4 | `detection_index` | Per-camera sampled / inferred ranges are half-open, ordered, inferred within sampled, not_inferred disjoint from inferred |
| `INDEX_RECORDS_FILE_HASH` | §4.2 | `detection_index` | records_file_sha256 equals the SHA-256 of the supplied records file |
| `RECORDS_FRAME_STATE` | §4.3, §6.3 | `detection_records` | frame_state is closed; only INFERRED has a detections array (empty = no detection); NOT_INFERRED has a reason; records sorted and unique |
| `RECORDS_OBSERVATION_IDS` | §2.2, §4.3 | `detection_records` | observation_id follows obs:<hash16>:<camera>:<frame>:<ordinal> with one hash segment per file; ordinals 0..n-1 by score desc then bbox; boxes valid |
| `RECORDS_COLOR_RULES` | §4.3 | `detection_records` | Colour only on applies_to_classes; verdicts cover the whole vocabulary; UNKNOWN verdicts carry unknown_reason; score range |
| `RECORDS_MATCH_MANIFEST` | §4.3, §4.4 | `detection_records` | INFERRED frames lie inside inferred_ranges_us of their camera; every camera is declared in the manifest |
| `RECORDS_SCORE_FLOOR` | §4.2, §11 | `detection_records` | No stored detection scores below index_score_floor |
| `PROBE_FORBIDDEN_FIELD_REJECTED` | §6.1, §9, v1.1 §7 | 全部 | (base-url mode) A request carrying a forbidden extra field is rejected with HTTP 422 FORBIDDEN_INFERENCE_INPUT |

## 7. 契約中標 `UNKNOWN` 的檢查（契約修訂建議）

契約沒寫清楚、所以測試包**沒有猜**（或只能用暫定形狀）的地方。「影響的檢查」欄說明測試包目前怎麼處理。Codex 確認契約時請逐項回覆；契約修訂後，測試包會跟著改版。

| # | 契約章節 | 不清楚的地方 | 建議的修訂 | 影響的檢查 |
| --- | --- | --- | --- | --- |
| U01 | §4.3 | Per-frame records have no schema_version; the records file name, location and format (JSONL vs array) are not defined. | Add schema_version `q-demo.detection-record.v1` and state the file format. | SCHEMA_VALID, RECORDS_* |
| U02 | §4.2 | The manifest's class_map has only version and hash; the label list that Q1 support depends on is stored nowhere, and class_alias.json has no schema. | Define class_map.labels (or a class_map file schema) and a q-demo.class-alias.v1 schema. | Q1_SUPPORTED_SET_CONSISTENCY (kit uses its own supported-classes input) |
| U03 | §2.3, §3.2, §6.3 | CLOCK_MAPPING_MISSING and TIME_EXPRESSION_INVALID are named as returns, but Q1/Q2 `status` lists do not contain them, and error responses (FORBIDDEN_INFERENCE_INPUT 422 etc.) have no body schema. | Say whether these are statuses or error codes and define the error-response body. | COMMON_STATUS_REASON, ERROR_RESPONSE_RULES |
| U04 | §1–§8 | No HTTP endpoints or paths are defined for Q1, Q3 parse, Q2 or the Agent tools. | Add an endpoint table (method, path, request and response schema_version). | --base-url mode needs an --endpoint-map supplied by Codex |
| U05 | §5.4, §8.4 | transition_candidates output has no schema: wrapper fields, ranking_basis shape, the name of the truncated-count field and the schema_version are not defined; candidate_snapshot_sha256 has no hash rule. | Define q-demo.candidate-snapshot.v1 and how candidate_snapshot_sha256 is computed. | CANDIDATE_* (kit uses a PROVISIONAL schema) |
| U06 | §5.4 step 4 | Relationship between candidate_set_complete, truncated and a top_k cut is not stated (v1.1 §6.1 defines truncated as budget-only). | State whether a top_k cut sets truncated or candidate_set_complete=false. | CANDIDATE_REFS_AND_LIMITS (only count <= top_k is checked) |
| U07 | §5.4 | The numeric suffix of candidate_ref (`cand:<hash16>:2`) is not defined (rank? zero-based index?). | State that it is the 1-based rank. | CANDIDATE_REFS_AND_LIMITS assumes suffix == rank |
| U08 | §5.2 | traversability lists two values but §1 says unapproved passability is UNKNOWN; relation lists OVERLAP/BLIND_GAP but tier 4 means 'UNKNOWN'; BIDIRECTIONAL/ADJACENT boundary-ref field names are not given. | Add UNKNOWN to both closed lists (kit accepts it) and name the ADJACENT boundary ref field. | GRAPH_STRUCTURE |
| U09 | §7.1, §7.3 | `parsed_by` values other than LLM, the `parser_mode` enum, the clarification/options shape, and where the rule parser's version and hash live in provenance are not defined. | Define parsed_by (LLM|RULE), parser_mode enum and provenance.rule_parser {version, sha256}. | Q3_RESPONSE_RULES, Q3_FALLBACK_CONSISTENCY |
| U10 | §7.5 | The LLM explanation has no output schema, endpoint or schema_version; how its `content_sha256` is computed is not stated. | Define q-demo.explanation.v1 {explains_output_sha256, text, cited_refs, fallback_reason, content_sha256}. | EXPLANATION_CITED_REFS (PROVISIONAL schema) |
| U11 | §8.2 | Link records ({prev_observation_id, next_observation_id, iou, decision}) have no schema_version or file location, so link rules (iou >= link_iou_min, gap tolerance) cannot be checked. | Define q-demo.link-record.v1 and where it is stored. | no link check exists |
| U12 | §8.7 | `budget_used_ms` sits inside the hashed body of decision-record, but §8.7 requires RULE_ONLY replays to have identical content_sha256; a measured value would break that. | Move budget_used_ms under stats, or fix it to 0 for RULE_ONLY. | CONTENT_HASH_RECOMPUTE (kit hashes it as written) |
| U13 | §2.3, §8.7 | decisions_sha256 (Q2 response) has no definition (file hash or content hash, ordering); decision-record `rounds_used` does not say whether it is per decision or per SEARCHING episode; 'last switching decision' for decision_source does not say whether RETURN_TO_ORIGIN counts. | State each rule; the kit treats SWITCH and RETURN_TO_ORIGIN as switching decisions and does not recompute decisions_sha256. | Q2_RESPONSE_VS_DECISIONS, DECISION_BUDGET_LIMITS |
| U14 | §8.6, §2.3 | With MODE_NOT_AUTHORIZED the response is RULE_ONLY but fallback_used is true; it is not stated whether decision_source is RULE_ONLY or RULE_FALLBACK. Also not stated: whether the ILLEGAL_CANDIDATE counter spans one SEARCHING episode or the session. | State both explicitly. | COMMON_AGENT_FIELDS, Q2_RESPONSE_VS_DECISIONS (kit accepts RULE_ONLY with fallback_used) |
| U15 | §8.5, §8.7 | APPEARANCE seeds with several candidates need a user choice, but no response status or payload exists for 'awaiting seed selection'; NO_SEED does not say whether it may be returned when time coverage is partial. | Add a status (e.g. SEED_SELECTION_REQUIRED) and say whether NO_SEED needs coverage_complete. | Q2_TIMELINE_STRUCTURE (NO_SEED is not forced to coverage_complete) |
| U16 | §6.3 | segment_merge_gap_us: whether the gap is measured between sample times or range ends, and strict vs inclusive, is not defined. | Define the gap operator. | no segment-merge check exists |
| U17 | §2.2, §6.3 | query_id / query_sha256 / decision_id derivation from 'the normalised request' has no normalisation rule, so they cannot be recomputed. | Specify the normalised-request canonical form. | no query_id check exists |
| U18 | §11 | parameter_set.json shape is undefined (flat keys vs `values`), and several §11 parameters have no machine name (crop ratio, HSV bands, exit rule). | Define parameter_set.v1 with every parameter name. | kit reads flat keys or a `values` object |
| U19 | §4.3 | unknown_reason is one field per detection but verdicts are per colour; whether all verdicts must be UNKNOWN when it is set is not stated. | State the relation. | RECORDS_COLOR_RULES (only 'UNKNOWN => reason set' is enforced) |
| U20 | §3.1 | Multi-run queries carry a single `clock_mapping_sha256` in resolved_scope although each run has its own mapping. | Make it a map run_id -> sha256 or a hash over the set. | SCOPE_HASH_LINKS, TIME_COVERAGE_RECOMPUTE (match by run_id) |
| U21 | §2.2, §4.2 | Circular dependency: observation_id embeds the index hash segment (= content_sha256[:16]), but the manifest's content_sha256 covers records_file_sha256, which covers the records that contain those observation ids. | Derive the hash segment from the manifest without records_file_sha256 (or from detector+sampling only) and say so. | RECORDS_OBSERVATION_IDS (kit only requires one consistent segment per file) |
| U22 | §5.4, §8.4 | Same circularity for candidates: candidate_ref embeds candidate_snapshot_sha256[:16] while the snapshot hash would cover the candidate_ref values. | Define the snapshot hash over the snapshot without candidate_ref fields. | CANDIDATE_REFS_AND_LIMITS (hash not recomputed) |
| U23 | §8.6, §8.7 | step_index counts steps, but only decisions are in the decisions file (link / TEMP_LOST steps are not), so records are not state-contiguous and step_index is not guaranteed consecutive. | State whether the decisions file includes every step; the kit checks only that step_index increases and time never goes backwards. | SESSION_STATE_MACHINE |
| U24 | §2.2, §2.1 | index_id / graph_id embed content_sha256[:16] but are fields of the same document, so content_sha256 cannot include them. | State that content_sha256 excludes index_id / graph_id (and stats). | CONTENT_HASH_RECOMPUTE (kit excludes them) |

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
- 沒有檢查的條文（因為 UNKNOWN 或需要看畫面）見 §7 與 §8。
