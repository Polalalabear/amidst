# 人審資料回收與正式輸入接線

Refs #204；尚未收到正式核定，正式執行仍 BLOCKED。

原 baseline 的 `--synthetic` 行為保留。正式輸入改用互斥的 `--reviewed-formal`，
同時提供 `--authority`、SHA-256 與 `--permit-reviewed-run`。authority schema 為
`q-demo.baseline-freeze-authority.v1`：scope 含 source_kind=FORMAL_R004、
protocol/cases/composition/registry/runtime 五個 input_pins，以及 public_questions
檔案 path/file_sha256；receipts 是十三份 path/file_sha256。包括 #145 符合性解除等 #192 的全部 gates。每份 gate/decision/
scope_sha256/reviewer/reviewed_at/review_kind/predictions_seen 必須完整、APPROVED、
同一 scope hash、具時區、INDEPENDENT_HUMAN、未看預測。正式 protocol 須另版
FROZEN/allowed=true；案例、registry source_kind 與八題公共文字必須相符。
pins 連至既有 registry 的完整 index/graph/clock/parameter/catalog metadata。
工具核對收據完整性與作用範圍，不能認證簽名者或人審是否真實；使用者仍須核對
實際核定紀錄。不能自行產收據、把工程 synthetic APPROVED 當正式核定。

`import_q3_minimum_review.py` 接獨立填好的 CSV、原候選 JSONL/freeze、review scope
及 #127 固定 schema kit。scope schema `q-demo.q3-review-scope.v1`，含 scope_id、
context_sha256 與 clocks（既有 q-demo.eval-clock-catalog.v1）。CSV 的 scope_sha256
必須是整份 scope 的檔案 hash；正式 clock/context 先固定，不能拿預測回填。

新版本名不可沿用候選版本；KEEP/REVISE 精確保留／另版文字，EXCLUDE 會要求補足
該類最小題組。空白或無效 expected、缺 reviewer/scope、缺類別均 BLOCKED/exit2。
答案由既有 q3_parse_eval 驗證 schema 與 clock，不呼叫 parser/provider 生成答案。
通過只輸出 `public.json` 的 id/text 與 evaluation-only `expected.jsonl`，IMPORT.json
記錄各檔 hash、來源與修訂選擇；formal_rows=0、formal_run_allowed=false，必須再經
獨立 freeze gate。推論只拿 public；expected、category、notes 不能傳給模型。

評分沿既有 `amidst.evaluation.q3_parse_eval.evaluate`，先固定實際輸出，再由獨立
authority 決定 evaluation_eligible。沒有獨立答案或預測時正式 accuracy 保持 null。
本次測試答案及收據皆為 SYNTHETIC 控制，不是八題正式答案。沒有變更 #127/#135。

## 獨立評分入口與本次結果

同一 CLI 可另給 --predictions/--predictions-sha256、--evaluation-authority/
--evaluation-authority-sha256、--permit-evaluation；只在回收驗證通過後呼叫原
q3_parse_eval.evaluate。評估收據 schema q-demo.q3-evaluation-authority.v1，完整欄位
為 review_import_sha256（IMPORT 的 content hash）、predictions_file_sha256、
scope_file_sha256、decision=APPROVED、reviewer、expected_independent=true、
predictions_frozen=true、dataset_kind=SYNTHETIC 或 FORMAL_R004。
SYNTHETIC 一律不進正式分母；收據完整性不代替人審真實性核對。

2026-10-24：本段 113 focused PASS，另 3 個同源回歸 PASS（不與前段重複相加）；
七個 scoped Python 檔 Ruff PASS。原八題空白 CSV 實際 CLI 回收 BLOCKED/exit2，
8 項 pending、0 formal rows、沒有 public/expected 輸出。正式資料未執行、accuracy=null。
