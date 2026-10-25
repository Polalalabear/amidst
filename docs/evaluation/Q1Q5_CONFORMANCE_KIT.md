# Q1–Q5 合約符合性測試包（Conformance Kit）

狀態：**v0.3.0-rc1，綁定 staging 契約檔**（`codex/q1q5-staging` @ `a958dd4`）：D65 核准的 `3873ff2`，加上 #135 釐清與 D69／D71（#148 寫入）。同一檔案 §14 第 9–25 項是 PROPOSED 選項，**本測試包不實作**，相關檢查維持 `3873ff2` 的讀法並列在 §7。契約定版前這是 release candidate；本測試包跟著契約改版，不是契約的一部分。

| 綁定項目 | 值 |
| --- | --- |
| 契約 | `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md`，分支 `codex/q1q5-staging` |
| 契約 commit | `a958dd4043ebcd5ef2d9fdb362d15f8c4ce3941f`（staging 綁定時的 head；檔案最後一次修改是 `09ae8e06a03c691cb23139305c10925cbf70d1a1`） |
| 契約檔 SHA-256（bytes） | `89b02cef9e957859c18f365d78a616ada8090ab310c8e3bd48dc9f950a4c1972` |
| 已核准的基底 | `3873ff2dbe97c88b3de2cfcdfc7df393fdff23d2`（D65；檔案 SHA-256 `924c4365…8078`，v0.2.x 綁這一版） |
| 測試包版本 | `0.3.0-rc1`（`amidst.evaluation.q1q5_conformance.KIT_VERSION`）；每份報告都記錄這兩項 |

契約改版後，測試包要同步改版並更新上表與常數 `CONTRACT`；舊報告的契約 commit 不同就不能當新契約的證據。v0.1.0 → v0.2.0 見 §11，v0.2.1 → v0.3.0-rc1 見 §12。

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
| `supported_classes.json` | 本測試包自己的輸入：`class_map` 的標籤、別名表、顏色詞彙（契約沒給可讀的清單，U02） |

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
| `Q1_RESULT_ORDER` | §6.3 | `q1_response` | Results ordered by first match time then camera_id, ranks consecutive, segments ordered and half-open, counts consistent; a last page ends at rank results_total (#156) |
| `Q1_NONE_CATEGORIES_DISJOINT` | §6.3 | `q1_response` | A camera appears in only one of results / no_match_cameras / not_evaluated_cameras |
| `Q3_LLM_OUTPUT_STRICT` | §7.1 | `q3_llm_output` | LLM output has no extra field and a consistent clarification flag |
| `Q3_LLM_TERMS_LITERAL` | §7.1 | `q3_llm_output` | class/colour/time/camera/region terms are fragments of the user's original text |
| `Q3_RESPONSE_RULES` | §7.2–§7.4 | `q3_response` | structured_query only when PARSED; clarification and failure statuses never execute; LLM call recorded when LLM was used |
| `Q3_STRUCTURED_QUERY_SCHEMA` | §7.2 step 4 | `q3_response` | The assembled structured_query validates against the Q1 or Q2 request schema |
| `Q3_FALLBACK_CONSISTENCY` | §7.3 | `q3_response` | A rule parse after an LLM attempt (LLM_WITH_RULE_FALLBACK) records fallback_used with a provider reason |
| `Q3_ATTEMPTS_WITHIN_PARAM` | §7.2, §11 | `q3_response` | llm_call.attempts <= q3_max_llm_attempts |
| `EXPLANATION_CITED_REFS` | §7.5 | `explanation` | Every cited ref appears in the explained response; text claims no identity; at least one ref is cited (explanation wrapper is provisional)（啟發式） |
| `CANDIDATE_ORDER_D28` | §5.4, v1.1 §6.1 | `candidate_snapshot` | Candidates sorted by relation_tier (§5.4 decision order 4,3,1,2), overlap_area_m2 desc (null last), camera_id; ranks consecutive; one entry per camera; ranking_basis has exactly the three D28 keys and no detection/colour keys |
| `CANDIDATE_TOPOLOGICAL_EXCLUDED` | §5.2–§5.4 | `candidate_snapshot` | TOPOLOGICAL_ONLY paths never appear as candidates; excluded ones carry TOPOLOGICAL_ONLY_EDGE; agrees with the camera graph when supplied |
| `CANDIDATE_SNAPSHOT_HASH` | §2.2, §5.4 | `candidate_snapshot` | candidate_snapshot_sha256 equals the canonical hash of the snapshot without itself, stats and every candidate_ref (candidates identified by rank) |
| `CANDIDATE_RANKING_AREA` | §5.3, §5.4 | `candidate_snapshot` | ranking_basis.overlap_area_m2 equals the camera graph transition's ranking_area_m2 (null stays null) |
| `CANDIDATE_REFS_AND_LIMITS` | §5.4, §8.4, §11 | `candidate_snapshot` | candidate_ref embeds the snapshot hash prefix and rank; candidate count <= top_k |
| `CANDIDATE_WINDOW_TRUNCATION` | §8.6 (#135 C4), §8.3 | `candidate_snapshot` | window_truncated_us is a list of half-open ranges, sorted, non-overlapping and inside the candidate's uncut window_us ([] when nothing is cut, never null) |
| `DECISION_FIELD_CONSISTENCY` | §8.4, §8.6, §8.7 | `decision_record` | accepted/rejection_code, decided_by, switch_mode, fallback_reason, executed action and state_after agree |
| `DECISION_CANDIDATE_LEGALITY` | §5.4, §8.4 | `decision_record` | The candidate switched to is in the legal snapshot (never a TOPOLOGICAL_ONLY / excluded / invented one) and its camera is a candidate camera |
| `DECISION_SEQUENTIAL_ORDER` | §8.4, §8.6 | `decision_record` | Candidates are taken in rank order without skipping; evidence is fetched before a switch/next; a switch is the last step and follows NEXT_CANDIDATEs |
| `DECISION_SWITCH_GUARD` | §8.4, §8.6, §11 | `decision_record` | An accepted SWITCH only targets a candidate whose target_presence reaches switch_min_presence; a rule decision does not skip a guard-reaching candidate that has an entry observation, and records NO_ALIGNABLE_OBSERVATION when it has none |
| `DECISION_REJECTION_CORRECTNESS` | §8.4 | `decision_record` | A submission that violates the controller rules (unknown ref, stale snapshot, no evidence, no citation) was not accepted |
| `DECISION_BUDGET_LIMITS` | §8.6, §11 | `decision_record` | rounds_used / budget_used_ms respect agent_max_rounds / agent_total_budget_ms unless the matching fallback is recorded |
| `SESSION_STATE_MACHINE` | §8.6 | `decision_record` | Each record is a legal §8.6 transition; step_index strictly increases and source time never goes backwards within a session |
| `DECISION_SESSION_COUNTERS` | §8.6, §8.7 (D69) | `decision_record` | searching_index is 0 before the first SEARCHING, the same within one snapshot and larger for a new one; session_agent_rounds_used never decreases and counts at least every recorded LLM call so far |
| `Q2_RESPONSE_VS_DECISIONS` | §2.3, §8.6, §8.7 | `q2_response` | agent_used / agent_attempted / fallback_used / first fallback_reason / decision_source equal what the session's decision records imply |
| `Q2_SWITCH_CAMERA_LEGAL` | §5.4, §8.6 | `q2_response` | Every SWITCH segment cites an accepted SWITCH decision whose snapshot candidate is exactly that camera, and starts at the evidence's entry_timestamp_us with the decision's entry_observation_id |
| `Q2_LINKS_FILE_HASH` | §8.2, §8.7 (D69) | `q2_response` | links_sha256 is the SHA-256 of the exact bytes of the session's link journal and every record in it belongs to the response's session |
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
| `DECISION_EVIDENCE_AND_ENTRY` | §8.3, §8.6, §8.7 | `decision_record` | decision_time_us <= source_time_us; an accepted SWITCH has an entry_observation_id that matches the candidate's evidence; considered candidates match their evidence summary |
| `LINK_RECORD_GAP_RULES` | §8.2 | `link_records` | elapsed_us is a positive multiple of the camera's index_interval_us; gap_samples = elapsed_us / index_interval_us (the current mismatching cell counts) and one less for LINKED |
| `LINK_RECORD_FIELDS` | §8.2 (D69, #135 C3) | `link_records` | One session per link journal, link_index 0..n-1 in file order; next_observation_id / iou set exactly for LINKED; ambiguous_candidates a non-empty list exactly for AMBIGUOUS_LINK, else null |
| `SEARCHING_TRIGGER_TIME` | §8.2, §8.3, §8.6, §11 | `decision_record` | decision_time_us is the time of the first unlinked index cell with gap_samples > link_max_gap_samples (elapsed_us >= link_max_gap_us, N derived as link_max_gap_us / index_interval_us - 1) |
| `Q2_FAIL_CLOSED_ON_GRID_MISMATCH` | §8.2, §11 | `q2_request` | If the parameter set and the index grid do not match (index_interval_us, link_max_gap_us a positive multiple of it, listed link_max_gap_samples = derived), the paired Q2 reply is status UNKNOWN, reason PARAMETER_GRID_MISMATCH, empty timeline (D69); otherwise it never says PARAMETER_GRID_MISMATCH |
| `PARAMS_APPROVAL_GATES_STATUS` | §11 | `q1_response`、`q2_response` | A response built on a parameter set whose approval.status is not APPROVED is not READY/COMPLETE and says PARAMETERS_NOT_APPROVED |

## 7. 契約中標 `UNKNOWN` 的檢查（契約修訂建議）

契約沒寫清楚、所以測試包**沒有猜**（或只能用暫定形狀）的地方。「影響的檢查」欄說明測試包目前怎麼處理。Codex 確認契約時請逐項回覆；契約修訂後，測試包會跟著改版。

| # | 契約章節 | 不清楚的地方 | 建議的修訂 | 影響的檢查 |
| --- | --- | --- | --- | --- |
| U01 | §4.3 | Per-frame records have no schema_version; the records file name, location and format (JSONL vs array) are not defined. | Add schema_version `q-demo.detection-record.v1` and state the file format. | SCHEMA_VALID, RECORDS_* |
| U02 | §4.2 | The manifest's class_map has only version and hash; the label list that Q1 support depends on is stored nowhere, and class_alias.json has no schema. Staging §14 item 10 lists options (PROPOSED, not decided). | Define class_map.labels (or a class_map file schema) and a q-demo.class-alias.v1 schema. | Q1_SUPPORTED_SET_CONSISTENCY (kit uses its own supported-classes input) |
| U03 | §2.3, §3.2, §6.3 | CLOCK_MAPPING_MISSING and TIME_EXPRESSION_INVALID are named as returns, but Q1/Q2 `status` lists do not contain them, and error responses (FORBIDDEN_INFERENCE_INPUT 422 etc.) have no body schema. Staging §14 item 9 lists options (PROPOSED, not decided); the three reason codes of §2.3 are no longer error codes (#135 C6). | Say whether these are statuses or error codes and define the error-response body. | COMMON_STATUS_REASON, ERROR_RESPONSE_RULES |
| U04 | §1–§8 | No HTTP endpoints or paths are defined for Q1, Q3 parse, Q2 or the Agent tools. Staging §14 item 22 lists options (PROPOSED, not decided). | Add an endpoint table (method, path, request and response schema_version). | --base-url mode needs an --endpoint-map supplied by Codex |
| U05 | §5.4, §8.4 | transition_candidates output has no wrapper schema: wrapper fields, the name of the truncated-count field, the schema_version and the endpoint are not defined. (The hash rule is defined in §2.2; window_truncated_us is a sorted, non-overlapping list of half-open ranges inside window_us, [] when nothing is cut, #135 C4.) | Define q-demo.candidate-snapshot.v1 (wrapper, truncated count). | CANDIDATE_* (kit uses a PROVISIONAL wrapper schema; CANDIDATE_WINDOW_TRUNCATION follows C4) |
| U06 | §5.4 step 4 | Relationship between candidate_set_complete, truncated and a top_k cut is not stated (v1.1 §6.1 defines truncated as budget-only). | State whether a top_k cut sets truncated or candidate_set_complete=false. | CANDIDATE_REFS_AND_LIMITS (only count <= top_k is checked) |
| U08 | §5.2 | BIDIRECTIONAL / ADJACENT boundary-ref field names are not given. (relation UNKNOWN = tier 4 and the two-value traversability list are settled by #135 C1 / C2.) | Name the ADJACENT boundary ref field. | GRAPH_STRUCTURE |
| U09 | §7.1, §7.3 | `parsed_by` values other than LLM, the `parser_mode` enum, the clarification/options shape, and where the rule parser's version and hash live in provenance are not defined. Staging §14 item 9 lists options (PROPOSED, not decided). | Define parsed_by (LLM\|RULE), parser_mode enum and provenance.rule_parser {version, sha256}. | Q3_RESPONSE_RULES, Q3_FALLBACK_CONSISTENCY |
| U10 | §7.5 | The LLM explanation has no output schema, endpoint or schema_version; how its `content_sha256` is computed is not stated. | Define q-demo.explanation.v1 {explains_output_sha256, text, cited_refs, fallback_reason, content_sha256}. | EXPLANATION_CITED_REFS (PROVISIONAL schema) |
| U12 | §8.7 | `budget_used_ms` sits inside the hashed body of decision-record, but §8.7 requires RULE_ONLY replays to have identical content_sha256; a measured value would break that. Staging §14 item 17 lists options (PROPOSED, not decided). | Move budget_used_ms under stats, or fix it to 0 for RULE_ONLY. | CONTENT_HASH_RECOMPUTE (kit hashes it as written) |
| U13 | §2.3, §8.7 | decisions_sha256 (Q2 response) has no definition (file hash or content hash, ordering); decision-record `rounds_used` does not say whether it is per decision or per SEARCHING episode; 'last switching decision' for decision_source does not say whether RETURN_TO_ORIGIN counts. (agent_used is defined since 1d1e061: an accepted AGENT step.) Staging §14 item 17 lists options for decisions_sha256 (PROPOSED, not decided). | State each rule; the kit treats SWITCH and RETURN_TO_ORIGIN as switching decisions and does not recompute decisions_sha256. | Q2_RESPONSE_VS_DECISIONS, DECISION_BUDGET_LIMITS |
| U14 | §8.6, §2.3 | With MODE_NOT_AUTHORIZED the response is RULE_ONLY but fallback_used is true; it is not stated whether decision_source is RULE_ONLY or RULE_FALLBACK. (The ILLEGAL_CANDIDATE counter is per SEARCHING since 1d1e061.) Not answered by D69 / D71; staging §14 item 21 covers the related Agent-NEXT exhaustion case (PROPOSED). | State decision_source for MODE_NOT_AUTHORIZED. | COMMON_AGENT_FIELDS, Q2_RESPONSE_VS_DECISIONS (kit accepts RULE_ONLY with fallback_used) |
| U15 | §8.5, §8.7 | APPEARANCE seeds with several candidates need a user choice, but no response status or payload exists for 'awaiting seed selection'; NO_SEED does not say whether it may be returned when time coverage is partial. Staging §14 item 22 proposes a separate seed-candidates endpoint (PROPOSED, not decided). | Add a status (e.g. SEED_SELECTION_REQUIRED) and say whether NO_SEED needs coverage_complete. | Q2_TIMELINE_STRUCTURE (NO_SEED is not forced to coverage_complete) |
| U16 | §6.3 | segment_merge_gap_us: whether the gap is measured between sample times or range ends, and strict vs inclusive, is not defined. | Define the gap operator. | no segment-merge check exists |
| U17 | §2.2, §6.3 | query_id / query_sha256 / decision_id derivation from 'the normalised request' has no normalisation rule, so they cannot be recomputed. | Specify the normalised-request canonical form. | no query_id check exists |
| U18 | §11 | parameter-set.v1 is defined (§11) but several §11 parameters have no machine name (crop ratio, HSV bands, exit rule, ...), the unit vocabulary is open, and the values of approval.status other than PROPOSED / APPROVED are not listed. | Name every parameter and list the approval.status values. | kit reads parameters[] by name; approval.status is kept a free string |
| U19 | §4.3 | unknown_reason is one field per detection but verdicts are per colour; whether all verdicts must be UNKNOWN when it is set is not stated. | State the relation. | RECORDS_COLOR_RULES (only 'UNKNOWN => reason set' is enforced) |
| U20 | §3.1 | Multi-run queries carry a single `clock_mapping_sha256` in resolved_scope although each run has its own mapping (§3.1 says each run uses its own mapping and no person may be chained across runs). Staging §14 item 11 lists options (PROPOSED, not decided). | Make it a map run_id -> sha256 or a hash over the set. | SCOPE_HASH_LINKS, TIME_COVERAGE_RECOMPUTE (match by run_id) |
| U23 | §8.6, §8.7 | step_index counts steps, but only decisions are in the decisions file (link / TEMP_LOST steps are not), so records are not state-contiguous and step_index is not guaranteed consecutive. | State whether the decisions file includes every step; the kit checks only that step_index increases and time never goes backwards. | SESSION_STATE_MACHINE |
| U29 | §8.7, §7.6 | llm_calls[].model_digest is a string in §8.7, but a provider call that fails before the model reports its digest (timeout, unavailable) has no observed digest (#170). | Staging §14 item 20 (a) allows null only for a failed call with its failure code (PROPOSED, not decided). | SCHEMA_VALID (decision-record keeps model_digest a string until decided) |
| U30 | §2.3, §8.4, §8.6 | When an Agent's accepted NEXT_CANDIDATEs exhaust the top-k, the Controller returns to origin; whether that RETURN is RULE_ONLY (agent_used stays true) or an Agent result is not stated (#170). | Staging §14 item 21 lists options (PROPOSED, not decided). | COMMON_AGENT_FIELDS, Q2_RESPONSE_VS_DECISIONS (kit keeps the 3873ff2 reading) |
| U31 | §2.3, §5.1, §11 | When several reasons hold at once (time coverage, graph, parameters, evidence, missing exits) the priority of the single `reason` is not approved. | Staging §14 item 12 lists options (PROPOSED, not decided). | GRAPH_APPROVAL_GATES_STATUS, PARAMS_APPROVAL_GATES_STATUS (kit keeps the 3873ff2 reading) |
| U32 | §8.4 | An Agent cannot cite anything for NEXT_CANDIDATE on a fetched candidate whose evidence has no observation (NO_PERSON_DETECTED, empty best_observations), so it cannot move on legally (#183). | Add a §14 decision (evidence-hash citation for NEXT, or a recorded RULE_FALLBACK reason). | AGENT_DECISION_FORMAT, DECISION_REJECTION_CORRECTNESS (kit keeps the 3873ff2 reading) |

**契約已回答、先前版本曾標 `UNKNOWN` 的項目**（`3873ff2` §2.2、#135 釐清、D69／D71；測試包現在依條文計算，不再暫定）：

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

**刻意沒改、等 §14 決定的地方**（U29–U32，§7）：失敗呼叫的 `model_digest: null`（§14 第 20 項）、Agent 全部 NEXT 後的 return 來源與 `agent_used`（第 21 項）、多原因優先序（第 12 項）、空證據候選的 NEXT 引用（#183）、`decisions_sha256` 的 preimage（第 17 項）、Q3 wire 與詞表（第 9、10 項）、多 run scope（第 11 項）。
