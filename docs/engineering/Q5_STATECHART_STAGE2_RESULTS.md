# Q5 Statechart／Journal Invariants：第二階段 A、B、C 實際結果

日期：2026-10-24（Asia/Taipei）。**A、B、C 的文件／獨立驗證與測試工作完成；四項產品缺口未修復。**
本輪停在第二階段，不開始 TLA+、CI、正式切鏡策略或第三階段資料驗證。

後續發布：依使用者新增授權，以 staging 為 parent 建立獨立 Draft PR；原 checkout／index／dirty 檔保持。
GitHub 可讀的精簡證據見 [公開驗收收據](Q5_STATECHART_STAGE2_EVIDENCE.json)。下文測試數字仍是第二階段實際執行結果。

## 範圍、版本與保護檢查

- 使用者核准的是 As-Is 文件、獨立 Journal Invariants 及自動化測試，沒有核准修改產品核心或契約。
- checkout 保持 `codex/controlled-scene-real-v2-2a`，HEAD
  `60fa8ef64988435530b09fb258d79130e83977af`；沒有 checkout、worktree、commit、push、PR／issue 寫入或 merge。
- 重新查 GitHub：#169 `798f73711e302a2e49fd495e96958ed254720e6f`、
  #172 `1bb4135965fb53643e9fbbaf8e41fd77e8ffb9c8`、
  #174 `d9125b68bdea82769a6c3b20317083d701fb2f1a` 仍為 OPEN／Draft。
- 前置審查 #187 已進至 `b3427e0d3d3da92729c7f3b010e2dd4fb66a93ef`，其 v2 包仍待獨立用途核准；
  這是外部工作進度，不是本任務的產出，也不據此解除 G4／新 HSV G6。
- 本輪開始前既有 **1,236 個程式／測試／設定／文件逐檔 SHA-256，結束時全部相同**。
  包括原先 dirty 的 docs/README.md 與未追蹤 q1q5 基礎模組；它們沒有被 stage 或覆寫。
- 固定測試組合中的 **342 個既有來源檔與第一階段逐 byte 相同**。
  Q5 Draft 不存在目前 checkout 的部分，用 test-only helper 從固定 Git objects 寫入新暫存目錄；
  不是合併 Draft、不是產品安裝、不建立新 venv，不複製原 Blender／RGB／GT／Baseline 資產。

證據：LOCAL GUARDS.json（LOCAL `/private/tmp/amidst-q5-stage2-20261024/GUARDS.json`；未上傳）、
來源組合（LOCAL `/private/tmp/amidst-q5-stage2-20261024/regression-snapshot/AUDIT_COMPOSITION.json`；未上傳）。
這是有界程式／文件與既有回歸的驗證；沒有重新讀取／雜湊所有大型原始資產。

## 實際新增檔案

| 檔案 | 用途 |
|---|---|
| [Q5_STATECHART.md](Q5_STATECHART.md) | As-Is 圖、12 組轉移／Guard／副作用、固定 source 行號、契約／缺口分離 |
| [q5_audit_source.py](../../tests/q1q5/q5_audit_source.py) | test-only 固定來源組合、隔離子行程、保留合成情境 evidence；不 fetch／切 branch |
| [q5_invariant_helpers.py](../../tests/q1q5/q5_invariant_helpers.py) | 不被產品 import 的離線 journal checker |
| [test_q5_invariants.py](../../tests/q1q5/test_q5_invariants.py) | 合法／違規／缺 context／準備失敗及 NEXT 引用等測試 |
| [test_q5_state_sequences.py](../../tests/q1q5/test_q5_state_sequences.py) | 有限序列、重複／衝突／預算邊界、已知缺口機械重現與 strict xfail |
| 本文件 | A／B／C 子階段、最後回歸、限制與後續依賴的實際紀錄 |

沒有修改既有 controller、Agent、API、schema、參數、前置審查資料或測試期待值。
沒有新增依賴；沿用既有 Python 3.12／uv／pytest／標準函式庫、既有合成 fixture 的依賴及 Node test runner。

## A：Statechart 的驗收

**完成。** 文件分開列出：

1. 現有 PLAYING／TEMP_LOST／SEARCHING／RETURNED_TO_ORIGIN／ENDED 的實際轉移。
2. 契約 §8.6 的 SWITCHING、使用者停止等預期。
3. 尚未實作、實作／契約不一致及 #183 的功能缺口。

SWITCHING 沒有被加入實際圖或偽造到 journal：現有 C `_commit_selection` L435
直接輸出 SEARCHING→PLAYING／SWITCH；契約預期仍是待解的差異。
ACTIVE 只用於文件分組，不宣稱產品已有階層式 statechart engine。
Guard／副作用對照列了 16 個既有測試符號，全部能在固定來源中找到。

驗證：既有 linker **28 PASS／0 FAIL／0 ERROR／0 SKIP，0.055 s**；
文件 source／測試符號檢查通過，沒有 whitespace 診斷。
`git diff --no-index --check /dev/null <new-file>` 的 exit 1 表示新檔與空檔有差異，
不將它誤報為 whitespace 失敗；原始 A-check.json 保留。

範圍判斷：只有新增文件；無 runtime／schema／hash 行為改變，可以進 B。

## B：獨立 Journal Invariants 的驗收

**完成。** checker 只在 tests/q1q5，無產品 import。輸入由測試提供 response、decision／link
JSONL、candidate snapshots、evidence、index context 與外部可信 scope。

檢查包含：檔案／content hashes、session／step 順序、As-Is 轉移、初始與終止紀錄、來源時間與
query 範圍、session／episode counters 不倒退、拒絕提案不得執行、fallback 後不再用模型、
candidate rank 順序、SWITCH entry／timeline／snapshot／取證／引用／index 的一致性、NEXT
引用與 decision slot、coverage 與負證據語意、GAP 不造位置、link 不造 attachment。

回報不只是一個布林值：

| 狀態 | 意義 |
|---|---|
| PASS | 本檢查器宣告的項目均通過，且沒有缺 context 或已知差異 |
| FAIL | 至少一項具體違例，附 code／path |
| INCOMPLETE | 缺少必要可信 scope／entry index／snapshot／evidence context，不能視為通過 |
| KNOWN_GAPS | As-Is 內部檢查通過，但有明列的未核准契約差異 |

As-Is profile 對現有壓縮 SWITCH 回報 `SWITCHING_NOT_RECORDED`／KNOWN_GAPS；
CONTRACT profile 對同一筆資料回報 FAIL。**沒有將現有錯誤改成正式合法規格。**

checker 的範圍是 supplied journal/context 一致性；它不簽發可信 pins、不驗證核准者真實性，
不重新做 RGB 推論、IoU／色彩政策或幾何計算，不是 #127 的替代品，不證明 GT 隔離或身份。
`gt_read=false` 只是被檢查的宣告之一。

B 子階段檢查當時：**51 PASS，既有 Q5 回歸 265 PASS，Ruff／diff PASS**。
C 驗收時補了 query／初始紀錄／NEXT 正反例，最終 B 模組為 **60 PASS**。

初版 B 曾有 **41 PASS／2 FAIL**：checker 在 hash 檢查前解析附空行的 JSONL，
只回 MALFORMED_JOURNAL，漏了更精確的 byte-hash 原因。只調整新 checker 的檢查順序，
同一測試期待值未變，重跑 43 PASS；原 B.xml 保留。沒有修改產品來通測試。

## C：序列、衝突與已知缺口的驗收

**測試交付完成，產品缺口仍未通過。** 最終 C 模組 **19 PASS／4 XFAIL，0 XPASS**。

- 四種 local 事件（接上、空偵測、MISSING、歧義），長度 0–6，共 **5,461 條序列**。
  與以事件類型／來源格時間建立的獨立 gap oracle 比對；已結束的 local linker 不得復活。
  這是 7 個參數化 pytest 案例中的有限枚舉，不能把 5,461 再當額外 pytest PASS 數相加。
- 重複 frame、倒退 frame、錯 timestamp／camera、歧義 attachment；拒錯後狀態不變。
- manual override 與晚到 evidence／provider 結果衝突；不允許舊自動 SWITCH，session 累計不退還。
- Agent session 額度 1／2 的邊界；用盡後由規則繼續，不能重啟 Agent 或提早終止規則 session。
- 順序重送相同請求只執行一次；並行保存時段另外保留反例。
- 同一機械 RULE 輸入改變牆鐘 latency，output hash、decisions bytes、links bytes 均相同；
  原始 stats 仍保留不同值，不藉刪掉 timing evidence 宣稱重播一致。

### 四項待修復狀態

| 項目 | 本次實際證據 | 期望測試／修正前提 |
|---|---|---|
| SWITCHING | 有實際 SWITCH，但沒有 SWITCHING journal | strict xfail；先核定 microstep／journal 抽象及 consumer 版本，不私增紀錄 |
| #183 空 evidence NEXT | NO_PERSON_DETECTED、空 observation 引用被 UNCITED_OR_FOREIGN_REF 拒絕；cursor=0；RULE 可前進至 E | strict xfail；先核定合法空證據前進／明確轉規則協議，SWITCH guard 不放寬 |
| 同步 publication race | barrier 控制於 _active 清除後、save 前；相同 session 執行 **2 次**、回 **2 份**相同 domain output | strict xfail；需獨立核准執行／保存原子性修正。現行 HTTP 部署可否觸發 UNKNOWN |
| user stop | 活躍背景工作無 stop/cancel 控制；假想 stop action 被 FORBIDDEN_DATA_SCOPE 拒絕，放行後原 job 正常 COMPLETE | strict xfail；只驗能力缺失，沒有替未核准 endpoint 發明成功協議。取消優先序與晚到結果仍待定 |

xfail 使用 `strict=True, raises=AssertionError`。另外的 PASS 測試記錄重現前提與實際結果；
隔離子行程／barrier／fixture 出錯會成為非預期錯誤，不被預期失敗掩蓋。沒有默認 skip；
JUnit 將 xfail 存為 skipped 節點，收據另以 `pytest.xfail` 計數，四項都不是產品已通過。

驗收補強時曾有 **78 PASS／1 FAIL／4 XFAIL**：正常 NEXT 測試誤用了 E 沒有觀測的預設 fixture，
實際引發空證據問題及規則 SWITCH，所以 checker 正確回 KNOWN_GAPS，與該測試的正常流程前提不符。
保留 final-new-v2.xml 與原情境 JSON；另明確建立 B、E 都有 STRONG 合成觀測的正常 NEXT fixture，
加上「確實有 Agent 決定且未用 fallback」前提。PASS 期待沒有改，#183 的原反例／xfail 保留。

## 最後完整有界回歸

| 集合 | 最後實際結果 | 證據 |
|---|---|---|
| 新增 checker／序列測試 | **79 PASS／4 XFAIL／0 非預期 FAIL／0 ERROR／0 XPASS，8.990 s** | final-new-v3.xml；B=60 PASS，C=19 PASS＋4 XFAIL |
| 目前 checkout 整個 tests/q1q5 共同收集／執行 | **280 PASS／4 XFAIL／0 非預期 FAIL／0 ERROR／0 XPASS，10.107 s** | final-checkout.xml；包含上一列新增案例，不可再相加 |
| 第一階段相同 Q5 focused 集合 | **265 PASS／0 FAIL／0 ERROR／0 SKIP，3.680 s** | final-q5.xml |
| 目前 checkout Demo 合成 association／motion／target | **85 PASS／0 FAIL／0 ERROR／0 SKIP，1.145 s** | final-demo.xml；明確排除真來源 HTTP fixtures |
| workbench cross-camera／observation selection | **39 PASS／0 FAIL／0 SKIP，216.186 ms** | final-node.tap；不是瀏覽器驗收 |
| 新增 Python 檔 Ruff／diff | **PASS** | 只 lint 四個新增 .py；既有程式與 user diff 不修改 |

不累加 A、B、C 及重跑同一案例的歷史數量；正式 #127 對齊、真模型、Windows、完整 repo suite、
真 RGB、GT／劇本評分、正式 Demo v1／Baseline 及瀏覽器驗收 **NOT_RUN**。
因此「未影響 Demo／Baseline」的證據限於既有來源未變與以上合成回歸，不能宣稱正式 Baseline 重驗通過。

## 精確重現指令

以下在 macOS 使用既有環境，沒有安裝依賴。Windows 未執行；路徑與 shell 語法不冒稱可直接照抄。
共同前綴：

```sh
PYTHONDONTWRITEBYTECODE=1 uv --no-cache run --no-project --offline \
  --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python python
```

下列 `python` 均指上述完整前綴。cwd 為 `/Users/polalabear/Developer/amidst`：

```sh
# A
python -m pytest tests/q1q5/test_linker.py -q -p no:cacheprovider \
  --basetemp=/private/tmp/amidst-q5-stage2-20261024/a-temp \
  --junitxml=/private/tmp/amidst-q5-stage2-20261024/A.xml
# B 子階段當時版本：51 PASS；最後新增邊界後以整組命令重跑
python -m pytest tests/q1q5/test_q5_invariants.py -q -p no:cacheprovider \
  --basetemp=/private/tmp/amidst-q5-stage2-20261024/b-final-temp \
  --junitxml=/private/tmp/amidst-q5-stage2-20261024/B-final.xml
# 最終新增集合（記錄 evidence 時另設 Q5_AUDIT_EVIDENCE_DIR 為已存在的 repo 外目錄）
python -m pytest tests/q1q5/test_q5_invariants.py tests/q1q5/test_q5_state_sequences.py \
  -q -rxX -p no:cacheprovider \
  --basetemp=/private/tmp/amidst-q5-stage2-20261024/final-new-v3-temp \
  --junitxml=/private/tmp/amidst-q5-stage2-20261024/final-new-v3.xml
# 全 q1q5 共同收集（PYTHONPATH=/Users/polalabear/Developer/amidst/src）
python -m pytest tests/q1q5 -q -rxX -p no:cacheprovider \
  --basetemp=/private/tmp/amidst-q5-stage2-20261024/final-checkout-temp \
  --junitxml=/private/tmp/amidst-q5-stage2-20261024/final-checkout.xml
```

以上已使用的 pytest temp 路徑不可在要保留原證據時重用；重現請另取新的 temp／XML 檔名。
Git object 組合指令（目的目錄必須不存在且位於 repo 外）：

```sh
python tests/q1q5/q5_audit_source.py /private/tmp/amidst-q5-stage2-20261024/regression-snapshot
```

Q5 回歸 cwd 為該 regression-snapshot，另設 `PYTHONPATH=<snapshot>/src`：

```sh
python -m pytest tests/q1q5/test_linker.py tests/q1q5/test_q5_controller.py \
  tests/q1q5/test_q5_agent.py tests/q1q5/test_agent_tools.py \
  tests/q1q5/test_q4_evidence.py tests/q1q5/test_candidates.py \
  tests/q1q5/test_api.py tests/q1q5/test_event_modes.py tests/unit/test_q5_switch_eval.py \
  -q -p no:cacheprovider --basetemp=/private/tmp/amidst-q5-stage2-20261024/final-q5-temp \
  --junitxml=/private/tmp/amidst-q5-stage2-20261024/final-q5.xml
```

Demo 回歸 cwd 為原 repo，`PYTHONPATH=/Users/polalabear/Developer/amidst/src`：

```sh
python -m pytest tests/workbench/test_blender_association.py tests/workbench/test_blender_motion.py \
  tests/workbench/test_target_reconstruction.py -k 'not real_source_http and not real_http' \
  -q -p no:cacheprovider --basetemp=/private/tmp/amidst-q5-stage2-20261024/final-demo-temp \
  --junitxml=/private/tmp/amidst-q5-stage2-20261024/final-demo.xml
node --test frontend/workbench/cross-camera.test.mjs frontend/workbench/observation-selection.test.mjs
python -m ruff check tests/q1q5/q5_audit_source.py tests/q1q5/q5_invariant_helpers.py \
  tests/q1q5/test_q5_invariants.py tests/q1q5/test_q5_state_sequences.py
git diff --check
```

未追蹤新檔另做 whitespace／路徑檢查，不能只靠 git diff --check 宣稱已檢查新檔。

## 已知限制、修復優先順序與下一階段條件

這是**固定 Draft commits 的審查測試**。更新產品整合版本後必須重新核對來源 pins、契約、
測試與預期失敗；它不會自動轉為未來 integration HEAD 的 CI 守門。
限定 snapshot／context 的檢查不是無界形式證明，也不取代 Claude 的獨立 conformance kit 或人工核准。

建議後續順序（本輪不執行）：

1. 先審查執行／保存原子性，以及 user stop／晚到結果／資源取消的生命週期方案；需使用者核准產品變更。
2. 決定 #183 空證據前進協議及 SWITCHING journal 表示，同步處理 #145／#170 的契約／kit 對齊；
   不為通過測試而放寬 SWITCH、刪歷史或改 expected failure。
3. 依既定工作完成 metadata 用途核准、正式 RGB／index、參數核定與凍結 RULE_ONLY Baseline，
   再做獨立人工答案／劇本／必要 GT adapter 的正式品質評估。
4. 控制協議與優先序穩定後，才另行審查是否值得加入 TLA+／refinement mapping／CI。

**具備提交下一輪修復方案審查的條件；不具備宣告正式 Q5／真模型／Baseline 已驗收或直接開始第三階段的條件。**
第二階段完成時六個新增檔未提交；其後 GitHub 發布依使用者另行授權，沒有進入第三階段。既有分支與 Draft 狀態保留。

## 實際產出紀錄

- Model／effort：UNKNOWN（未取得可核實的完整 model／effort 識別）。
- PR／commits：第二階段完成時 NONE；後續發布的 exact head 見本次 Draft PR，scope 為六個檔加第一階段報告與公開收據。
- Artifacts：LOCAL `/private/tmp/amidst-q5-stage2-20261024/`，原始 XML、情境 JSON、來源組合、
  before／GUARDS／TEST_RESULTS／FINAL_RECEIPT。新增檔 hashes 與磁碟用量見 FINAL_RECEIPT。
- Verified：上述固定來源、純合成測試、四個反例與既有檔案保護。
- Not verified：真模型／Windows／瀏覽器／正式資料與 Baseline、完整 #127 對齊、TLA+／CI。
- Deviations：為保留 checkout，用 test-only pinned composition；C 驗收時補強 B 邊界檢查；
  所有歷史失敗保留，沒有改產品、契約或原有測試。

完整機械結果：TEST_RESULTS.json（LOCAL `/private/tmp/amidst-q5-stage2-20261024/TEST_RESULTS.json`；未上傳）。
