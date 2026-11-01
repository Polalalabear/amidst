# CQ-32-T 合成驗收

**評分端；與推論隔離。**只有人工指定的合成數字、JSON 與 journal，沒有
原始 RGB、GT、renderer 軌跡、visibility、depth、正式劇本、模型或人類回件。
任何 APPROVED／decision selection 都只在 SYNTHETIC 控制例中成立，不能
解除 G4、U6、UK-8、劇本凍結、render、AC7 或評測／發包 gate。

參考 #325 與 PROPOSED 設計
[#258@f19fbcfd2ff64c483fedb00bd9be2e72e97a2af3](https://github.com/Polalalabear/amidst/pull/258)。
該設計未經 Claude 複審、未由使用者採用。只使用 D93／D94 的已定規則；
其餘選項不因測試存在就成為決定。

## 檔案及重建

`build_fixtures.py` 僅產生小合成資料。`MANIFEST.SYNTHETIC.json` pin 每份
生成 JSON／JSONL；測試在另一個暫存根重建並比較 bytes。

```sh
uv run python tests/fixtures/q5_v2/SYNTHETIC/build_fixtures.py
uv run python -m pytest -q tests/evaluation/test_q5_switch_eval_v2.py tests/unit/test_q5_switch_eval.py
```

phase 正例是 #325 指定的 Δ=0.2、L=0.6、R=1、W=6 秒，RETURN@0.6／1.6、
SWITCH@2.6、entry@7.6；第二搜尋窗右端 7.6 不含該 entry。LONG_GAP 的
g=6.8 > G1=5.2，計畫需3輪，不能用舊相位推成第2輪切換。

limit trace 有完整6輪 start／RETURN，已綁定 ENDED source_time=6.8 秒；
timeline GAP 卻補到12秒，後綴沒有執行證據。searching trace 包含 index0、
窗前開始而窗內完成的第1輪、USER SEARCHING→SEARCHING 的第3輪；只按
真實開啟 start 取 distinct，不能在窗內全部紀錄上直接 distinct 或只用
state_before != SEARCHING 篩選。

`parameter_set.SYNTHETIC.json` 是合成既有 parameter 形狀控制例；不是
正式已核參數。`plan.SYNTHETIC.json` 明示沒有 production plan schema，
只提供數字來源控制例。`q5-evaluation-script.v2` 樣本依 PROPOSED 欄位
製作，不把 schema 草案當採用。實作選定 wire 若不同，須明示綁定，不可
靜默重寫原 fixture、生成 authority 或跳過缺少的有效資料。

## 尚未核定的選項

`decisions.PENDING.SYNTHETIC.json` 中全部10個可設定鍵都為 PENDING_USER；
U-D3 不在設定鍵內，D93 O1 固定，不能改成 O2／O3。
每份 `decisions.<group>.SYNTHETIC.json` 只改一個鍵，其他仍 PENDING。
M1／E2 是設計已列的選項 ID；`TEST_ONLY:` 字串只是本驗收的**語意標記**，
不是 production 設定 enum，也不是使用者核定。UK-8 的控制標記尤其
不是選擇真實 t_V／t_L 來源方法；runtime 正例仍保留 UK-8=PENDING_USER，
只用明示合成時刻，不從幾何或 renderer 推導。

這些標記涵蓋報告超額 RETURN、重算窗、保守拒絕早可見 BLIND、分開主群／
standard／class 比率、新 v2 module、LONG_GAP 夾住起點、N_max−2預算。
測試覆蓋這些分支不代表推薦已採用。真實採用只由 U6／UK-8 的使用者決定。

## TEST-ONLY driver seam

#324 尚未實作，公開 Python API、完整 report 及計畫／決定 wire 未定。
測試先載入真正的 `amidst.evaluation.q5_switch_eval_v2`；缺實作正常
`pytest.importorskip`，`AMIDST_REQUIRE_IMPL=1` 改為
CQ32_IMPLEMENTATION_MISSING。沒有本地 replacement scorer 或 stub。

之後以 `AMIDST_Q5_V2_DRIVER=<TEST-ONLY Python module>` 明示薄 adapter，
提供 `exercise_case(name, *, inputs, implementation)`。這是**測試介面**，
不是新 production API。driver 必須實際呼叫傳入的實作、讀取其原報告／
錯誤；不得自行套公式、產生預期分數、將 fixture 的 expected 當觀察或
用 mock scorer 取代實作。需新的已核 wire／完整合成 binding 時，明示
提供所選 bytes／pins；未知處保持未綁定，不能只信 APPROVED boolean。
driver 內的 skip／xfail 在 strict 模式也轉 fail。

輸入有 response／records／script／parameters／plan／decisions，以及
reseal 後的 raw bytes／pins；overlap 的 binding_context 是 TEST-ONLY
scope 控制例，不是圖、G4 或新 wire。外部 binding 載入器若有必要，
須使用完整合成 pinned 資料和真正 verifier，不能自行宣稱 real_authority。

回傳的 TEST-ONLY envelope：

- implementation_invoked=true、implementation_file_sha256=實際 module bytes
  SHA、human_approval_verified=false。
- native_report：實作的原報告，拒絕時為 null；rejected：是否真被實作拒絕。
- observations：只從實際報告／錯誤抽出的 status、events、main_ratio、
  standard_event_match_ratio、partial_ratio、overlap_ratio、cutoff_us 或
  searching_count。event 欄位是 event_id、event_class、match、reason、
  return_count、searching_count、entry_window_us。這些是測試投影，
  不決定 production report schema。
- 拒絕的 error_category 為測試語意分類：OUTPUT_INTEGRITY、
  D94_FORBIDDEN_INTERVAL、SCRIPT_PLAN_MISMATCH、DECISION_CONFIG_INVALID、
  PLANNED_SEARCH_BUDGET；不能改寫實作結果以湊成分類。
- dispatch_v1 回傳原生 v1 報告，或真實 error_type／error_message。
  原 v1 測試函式及 parameterize 案例被讀取後，每次 compare_script 都
  對比 v1／v2 原報告 canonical bytes 或同一錯誤；原 v1 CLI／freeze
  用例保留原路徑另驗，沒有竄改 v1 檔案。

freeze_file_order 須在同個 process 呼叫實際檔案入口，尊重給定 paths／
pins，不能預讀 script。測試攔截 builtins／io／os open，壞輸出 pin 時
script 必須未被讀；同一正例必須真的讀 script 並成功，避免 reject-all。

## 依賴到位後怎麼跑

#325 指定原命令：

```sh
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/evaluation/test_q5_switch_eval_v2.py tests/unit/test_q5_switch_eval.py
```

實作及其所選 wire 到位後，另外明示 AMIDST_Q5_V2_DRIVER 再跑。未綁定
driver 正常 skip、strict fail；不可把 strict 紅燈寫成 scorer 已完成。
自測只證明 fixture／驗收框架可重建，不能當 v2 runtime 正確性證據。
