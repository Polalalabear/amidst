# Agent 評估工具鏈驗收關卡 v1（D200）

- 狀態：**規範性（normative）**。對象：Argon ②（issue #515）。測試：[`tests/q1q5/test_argon2_gates.py`](../../tests/q1q5/test_argon2_gates.py)。
- 作者／Model / effort：Claude Code，Sonnet 5.5 / high。
- 依據：[`docs/design/AGENT_DECISION_V1.md`](../design/AGENT_DECISION_V1.md) §2–§4、§7；WP1 `src/amidst/q1q5/agent_decision.py`；WP2 掛點 `cross_camera_demo.associate(decider=…)`；#511（WP3，介面衝突時以 #511 為準）。

## 完成條件

`tests/q1q5/test_argon2_gates.py` 裡所有標 `xfail(strict=True, reason="awaiting Argon ② #515")` 的測試**全部轉為 PASS，並把 xfail 標記拿掉**。不要改斷言；覺得斷言或本契約有誤，在 #515 留言。
strict xfail 的意思是：測試一旦通過但標記還在，CI 就會失敗，所以通過時一定要同時移除標記。

## 共同規則

1. 只用標準函式庫＋WP1（`amidst.q1q5.agent_decision`）；不改 WP1、`agent_wiring.py`、`cross_camera_demo.py`。
2. 決策端（`src/amidst/q1q5/`、`src/amidst/agent_eval/`、`scripts/agent_decision/` 除 `score.py`）**不得 import** `amidst.agent_eval_scoring`；評分是獨立套件，只經子程序執行。
3. JSON 一律用 `agent_decision.canonical()` 寫（排序鍵、緊湊、ASCII、換行 `\n`）。
4. 決策端任何輸出（題目檔、MANIFEST、包內 JSON）的鍵不得命中 `agent_decision.FORBIDDEN_KEYS`，也不得以 `gt_` 開頭。**注意** `path`、`file`、`actor` 等都在清單裡，所以本契約的欄位名稱避開它們（例如用 `relative_path`）。
5. 測試只用合成資料；`FAKE_GT_FIXTURE` 在測試檔裡自己造。不讀真實 GT、`gt_private/`、真實 `scoring_private/`、影像。不連網路，不讀 `OPENAI_API_KEY`。

## 模組與介面

### 1. `amidst.agent_eval.question_bank`（關卡 1、2）

```python
build_questions(requests, *, source_run: str, commit: str, params_sha256: str,
                scene_sha256: str, candidate_order_seed: int = 0) -> list[dict]
write_question_bank(questions, out_dir) -> dict
```

`build_questions`：每個 request 先過 `validate_request()`（有 FORBIDDEN 鍵就**整批**丟 `AgentDecisionError`，不是跳過）。每題欄位：

| 欄位 | 內容 |
| --- | --- |
| `schema_version` | `"amidst.agent-eval-question.v1"` |
| `decision_point` | `DP1`／`DP3`，等於 `request['decision_point']` |
| `source_run`, `commit`, `params_sha256`, `scene_sha256` | 照傳入值 |
| `request_sha256` | `agent_decision.request_sha256(request)`（與候選人順序無關） |
| `candidate_order_seed` | 照傳入值 |
| `question_class` | 真實題 `"REAL"`；合成題 `"SYNTHETIC_PERTURBATION"` |
| `allowed_answers` | DP1：請求裡所有候選 id＋`"ABSTAIN"`；DP3：`["ACCEPT_SEGMENT","REJECT_SEGMENT"]` |
| `request` | WP1 request，原樣 |

`write_question_bank` 寫 `requests_v1.jsonl`（一行一題）和 `MANIFEST.json`，回傳 MANIFEST 內容（也要等於磁碟上的內容）。MANIFEST 至少有：`commit`、`params_sha256`、`scene_sha256`、`n_questions`、`requests_sha256`（= `requests_v1.jsonl` 位元組的 SHA-256）。**同樣輸入產生的兩個檔逐位元組相同。**

### 2. `amidst.agent_eval.synthetic_perturbation`（關卡 3）

```python
generate_synthetic(questions, *, safe_index_path, seed: int, per_point: int, out_dir) -> dict
# -> {"questions_path": str, "labels_path": str, "n_synthetic": int}
```

- 輸入 `questions` 是 DP1 真實題。`safe_index_path` 是 JSON：`{"schema_version": "safe-track-index-v1"（測試用的值，v1 不檢查）, "tracks": [{camera_id, first_seen_us, last_seen_us, colors, scores, continuation_fraction}, …]}`。索引含 FORBIDDEN 鍵就丟 `AgentDecisionError`。
- 每個真實決策點加 `per_point` 個（1–3）干擾候選人，id 重新編號成不透明 id，**位置要被打亂**（測試要求插入者的位置不固定）。新 request 要過 `validate_request()`，且 `rule_answer == RuleDecider().answer(request)`。
- 寫兩個東西：
  - `out_dir/requests_s2_v1.jsonl`：每行同 §1 的題目格式，`question_class="SYNTHETIC_PERTURBATION"`。**裡面不得出現標籤的鍵名、字串 `scoring_private`、`perturb`、`inserted`、`synthetic`（在 `request` 內）。**
  - `out_dir/scoring_private/synthetic_labels_v1.json`：`{request_sha256: {"inserted_candidate_ids": [...]}}`，長度等於 `per_point`。
- **只讀** `safe_index_path`（測試用 monkeypatch 開檔函式驗證；寫入不限）。同 seed 同位元組，不同 seed 不同。

### 3. `amidst.agent_eval.rule_r1`＋`configs/q1q5/agent_r1_params_v1.json`（關卡 5）

```python
load_params(path=None) -> dict          # 預設讀 configs/q1q5/agent_r1_params_v1.json
class R1Decider:
    def __init__(self, params=None): ...
    def answer(self, request) -> str    # 與 RuleDecider.answer 同介面
    def params_report(self) -> dict     # 與 load_params 同形
```

參數檔（每個值都帶 `status`，現在一律 `"PROPOSED"`；正式值要在看資料前由使用者確認，Q6）：

```json
{"dp1_tie_order": {"value": ["gap_us", "graph_edge", "score_median", "id"], "status": "PROPOSED"},
 "dp3_reject_continuation_fraction": {"value": 0.5, "status": "PROPOSED"}}
```

- DP1：只在 `rule_eligible` 的候選人中選；沒有 → `ABSTAIN`。依序比：`gap_us` 小者優先 → `graph_edge` 為真者優先 → `scores.median` 大者優先 → `id` 字串序。與請求裡候選人的排列順序無關，可重現。
- DP3：`current.continuation_fraction` **嚴格大於**門檻 → `REJECT_SEGMENT`，否則 `ACCEPT_SEGMENT`。

### 4. `amidst.agent_eval.runner`、`amidst.agent_eval.latency`（關卡 6）

```python
runner.main(argv: list[str], *, provider=None) -> int
```

旗標：`--questions FILE --params FILE --stage NAME --out DIR [--k N (預設 1)] [--live]`。`provider` 是符合 `call(request, *, timeout_ms, max_output_tokens) -> Attempt` 的 callable（測試注入假的）。

- **預設 DRY_RUN**：回傳 0；寫 `out/dry_run.json` = `{"mode": "DRY_RUN", "provider_calls": 0, "estimate": agent_decision.dry_run_estimate(params, questions=<題數>, k=k, stage=stage)}`；`provider` 呼叫 0 次。
- `--live` 且該 stage `approved=false`：回傳非 0，provider 呼叫 0 次。
- 不得連線（任何 socket 連線都會讓測試失敗），不得讀 `OPENAI_API_KEY`（DRY_RUN 和被拒絕的 LIVE 都一樣）。

```python
latency.GROUPS == ("tracking_formal", "search_relaxed")
latency.group_params() -> {group: {"timeout_ms", "budget_ms", "max_rounds"}}
latency.summarize(samples) -> {group: {kind: {"n", "p50", "p90", "p99"}}}
```

- `tracking_formal` 從正式組參數集讀（2000／5000／3），`search_relaxed` 從探索組參數集讀（`configs/q1q5/agent_decision_params_v1_exploratory.json`）；數值不寫死在程式裡。
- `samples` 的每列是 `{"group", "kind": "call"|"step", "wall_ms"}`；不同 group 永遠分開統計；未知 group 丟 `ValueError`。百分位用 nearest-rank：排序後取第 `ceil(p/100·n)` 個（1..10 → P50=5、P90=9、P99=10）。

### 5. `amidst.agent_eval_scoring`（獨立套件，關卡 4）

```python
mapping.iou(a, b) -> float                                  # 框 [x0, y0, x1, y1]
mapping.map_track_to_actor(observations, gt_source, *, iou_match, iou_manual_low, majority_fraction) -> dict
# -> {"actor": str | None, "needs_manual": bool, "majority_fraction": float}
```

- `observations`：`[{"camera_id", "timestamp_us", "box"}, …]`。`gt_source(camera_id, timestamp_us) -> {actor_name: box}`（GT 來源介面，任意多個 actor）。
- 每個觀測取 IoU 最高的 actor；IoU ≥ `iou_match`（含）才算命中。命中最多的 actor 的比例 ≥ `majority_fraction`（含）→ 對應到該 actor、`needs_manual=False`；否則 `actor=None`、`needs_manual=True`（涵蓋 IoU 介於 `iou_manual_low` 和 `iou_match` 之間、以及多數決不足的情形）。預設門檻 0.5／0.3／0.6，標 PROPOSED。

CLI（只經子程序執行）：

```
python -m amidst.agent_eval_scoring.cli --questions Q.jsonl --decisions D.jsonl \
    --candidate-observations O.json --gt-fixture G.json --params P.json --out DIR
```

- `D.jsonl`：`{"request_sha256", "answer"}`。`O.json`：`{request_sha256: {"candidates": {opaque_id: [observation, …]}, "segment": [observation, …]}}`（評分端檔案，不給決策端）。`G.json`（`FAKE_GT_FIXTURE` 格式）：`{"fixture", "target", "frames": [{"camera_id", "timestamp_us", "boxes": {actor: box}}]}`。`P.json`：`{"iou_match", "iou_manual_low", "majority_fraction", "status"}`。真實 GT 的轉接器之後另做，不在本關卡內。
- 輸出 `DIR/per_question.jsonl`：每行**只有** `{"request_sha256", "correct"}`（`correct` 為 true／false，需要人工的題目為 null）；`DIR/metrics.json` 至少有 `Acc_dp`（`{"DP1": …}`）和 `n_scored`。輸出裡不得出現任何 actor 名稱。
- DP1 標準答案：對應到 `target` 的候選人；沒有 → `ABSTAIN`。

### 6. `amidst.agent_eval.windows_pack`（關卡 7）

```python
build_pack(out_dir, *, files: Mapping[str, Path]) -> dict   # files: 包內相對路徑 -> 來源檔
```

寫出：`files` 裡的檔案（複製到 `out_dir/<相對路徑>`）、`MANIFEST.json`（也是回傳值）、`README.md`、`RETURN/README.txt`、`tools/verify_pack.py`。

- `MANIFEST.json` 有 `upload_list`：每列恰好 `{"relative_path", "sha256"}`，涵蓋 `files` 的每一個鍵；`sha256` 是包內該檔的 SHA-256；路徑是 `/` 分隔的相對路徑（不以 `/` 或 `\` 開頭、無 `:`、無 `\`、無 `..`）。
- `README.md` 含四節標題字樣：`工作內容`、`要上傳的檔案`、`操作步驟`、`不要改`，並列出 `upload_list` 的每個路徑。
- 包內所有 `.json` 的鍵不得命中 FORBIDDEN 清單。

## 對照表：關卡 → 測試

| 關卡 | 測試 |
| --- | --- |
| 1 題庫 | `test_g1_*`（3 個） |
| 2 FORBIDDEN 鍵 | `test_g2_*`（含 6 個植入鍵的參數化） |
| 3 S2 | `test_g3_*`（4 個） |
| 4 評分隔離 | `test_g4_*`（3 個） |
| 5 R1 | `test_g5_*`（3 個） |
| 6 runner／延遲 | `test_g6_*`（3 個） |
| 7 Windows 包 | `test_g7_*`（1 個） |
| 自我測試（不是 xfail） | `test_selftest_*`（4 個，驗 fixture 本身） |

## 已知限制

- 這些測試只固定「介面契約與核心隔離規則」，不取代 #515 自己的測試要求（抽取前後 `response()` SHA、Colab 非 L4 分支、`verify_pack.py` 對插入禁用鍵的包判 INVALID 等）。
- 參考實作驗證：關卡中不依賴檔案系統外部資源的 15 個測試，曾以一份丟棄式的參考實作跑過，確認斷言可以被滿足；該參考實作**沒有**放進任何 PR。其餘 9 個（S2、評分 CLI、runner、Windows 包、import 圖）未用參考實作驗證，若斷言有誤請在 #515 留言。
