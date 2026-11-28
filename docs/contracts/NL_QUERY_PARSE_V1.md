# NL_QUERY_PARSE_V1: one-sentence query → tag panel (N1 Spotlight)

Status: draft for N1 (D210), branch `claude/feat-nl-search`. Implementation: `src/amidst/q1q5/nl_query_parse.py`;
route `POST /api/nl_query_parse` (`QAPI.call('nl_query_parse', …)`). The parser **only fills the existing tag panel**;
the Q1/Q2 request builders and the whole query flow below it are unchanged. It never executes a query.

## 1. Request

```json
{"session_ref": "…", "context": {"scene_id": "…", "run_ids": ["…"]}, "text": "追蹤紅衣的人 從西入口 0:10 到 0:30", "mode": "RULES"}
```

* `text`: non-empty after trimming, ≤ 200 characters. Anything else → `FORBIDDEN_INFERENCE_INPUT`.
* `mode`: `API` | `LOCAL` | `RULES` (default `RULES`). Same scope check as `q3_parse` (`session_ref`, scene, run).

## 2. Response (fixed shape)

```json
{"schema_version": "q-demo.nl-query-parse.v1",
 "action": "追蹤", "location": ["R1"], "target": ["person", "red"], "time": {"start": 10, "end": 30}, "unrecognized": [],
 "parser": "RULES", "latency_ms": 0.4, "cost_usd": 0.0,
 "fallback_trail": [{"parser": "RULES", "outcome": "OK", "latency_ms": 0.4}]}
```

| field | type | rule |
| --- | --- | --- |
| `action` | `"查找"` \| `"追蹤"` \| `null` | `null` when the sentence has no action cue. The UI then keeps the current mode; nothing is guessed. |
| `location` | `string[]` | canonical `region_ids` of the run, no duplicates |
| `target` | `string[]` | canonical class labels **or** colour labels of the run (`["person","red"]` = red clothing, person). No duplicates |
| `time` | `{start,end}` \| `null` | seconds of **elapsed source time** (numbers, `0 ≤ start < end`). `null` when no complete range was given. A single time is not a range: it goes to `unrecognized` |
| `unrecognized` | `string[]` | pieces of the sentence that matched nothing (≤ 16 items, each ≤ 64 chars). The UI marks them 「未辨識」. Never mapped to a nearest value |

Exactly these five keys; extra or missing keys fail validation. Metadata (`schema_version`, `parser`, `latency_ms`, `cost_usd`,
`fallback_trail`) is added by the server after validation.

## 3. Vocabulary source (not copied)

The closed vocabulary is the run's server catalog (`QRun.catalog`: `class_labels`, `color_labels`, `region_ids` and the
`*_aliases` tables), the same catalog the Q3 parser and the tag panel menus are built from. A value outside it is invalid for
every layer. Aliases (e.g. `西入口 → R1`, `紅 → red`, `人 → person`) are matched by the rules parser and are shown to the models in the
prompt; the models still must answer with canonical ids.

## 4. Parsers and fallback order

`mode=API`: API → LOCAL → RULES. `mode=LOCAL`: LOCAL → RULES. `mode=RULES`: RULES only (default; needs no key, no network).

* **API**: OpenAI chat completions with strict structured output (`json_schema`, vocabulary as `enum`s). Models `astra6`, `sol6.1`,
  `terra6.1` (`AMIDST_NL_OPENAI_MODEL`, default `astra6`). The key is read from `OPENAI_API_KEY` **on the server only**, at call time; it never
  appears in a response, a recording, a log or the front end. Uses the #526 transport/extraction helpers (`agent_providers`).
* **LOCAL**: Ollama on loopback (`AMIDST_NL_OLLAMA_MODEL`, `AMIDST_NL_OLLAMA_ENDPOINT`, default `http://127.0.0.1:11434`), JSON-schema `format`.
* **RULES in Spotlight** interprets two fixed-width `HH:MM:SS` boundaries on the selected run’s declared date and timezone, then returns elapsed source seconds. `M:SS`, single-digit-hour `H:MM:SS` and duration units keep their elapsed meaning. A wall-clock range needs one declared clock. Mixed formats and midnight rollover are rejected. A wholly uncovered range reports `OUT_OF_RANGE`. A range beginning before source zero and ending inside or after the recording reports `TIME_SCOPE_PARTIAL` and can be entered in the wall-time form. The nonnegative elapsed format cannot represent its requested start. Standalone callers such as LIVE and the WP5 pack use elapsed parsing.

A layer is skipped to the next one when: it is not configured (`NOT_CONFIGURED`), exceeds the timeout (`TIMEOUT`, default 2500 ms per
remote layer), fails (`UNAVAILABLE`), or returns something that does not pass §2 validation (`SCHEMA_REJECTED`). Validation is
applied to every model answer before it is returned; RULES output is validated too. `fallback_trail` lists every layer tried with its outcome.

## 5. Recorded fields

`parser` (`API`|`LOCAL`|`RULES`, the layer that produced the answer), `latency_ms` (wall time of the whole call, all layers),
`cost_usd` (sum over attempted layers: RULES and LOCAL = `0.0`; API = tokens × the pinned price table, or `null` when
no price table is pinned. Never estimated). Optional `recorder` receives one row per remote call (request hash, parsed answer, model, usage, wall_ms); recording
failures never break a parse. Tests use fake clients or recordings; no real API is called in CI.

## 6. Front end

The Spotlight bar (⌘K / magnifier, centered, blurred backdrop, Esc closes) shows the parsed fields as chips while typing (debounced, RULES
locally via the same endpoint) and 「未辨識」 chips for `unrecognized`. Enter fills the existing query window (action → 查找/追蹤 window, location, class,
colour, start/end) and submits the selected query. A rejected wall-clock range shows its error in Spotlight and prevents submission. Settings key `nlParser`: `RULES` (default) | `API` | `LOCAL`.

## Paid-API guard (shared spend guard)

`mode=API` is only a request. The paid layer runs only when the server opts in (`AMIDST_API_ENABLED=1`) **and** sets `AMIDST_API_MAX_USD_TOTAL` above 0 (default 0). Otherwise the layer reports `API_DISABLED` (or a cap reason: `PRICE_UNKNOWN`, `PER_CALL_TOKEN_CAP`, `PER_CALL_COST_CAP`, `RATE_LIMIT`, `DAILY_CALL_CAP`, `DAILY_COST_CAP`, `TOTAL_BUDGET`) as its `fallback_trail` outcome and the chain falls back to LOCAL, then RULES. Implementation and ledger (`local/evidence/api-usage/usage.jsonl`, LOCAL): `src/amidst/q1q5/api_budget.py`. Dry-run estimate: `scripts/api_budget_estimate.py`.
