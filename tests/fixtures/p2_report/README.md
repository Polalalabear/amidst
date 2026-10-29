# CQ-25-T SYNTHETIC P2 probes

此目錄只服務 #315。`SYNTHETIC/receipt.json` 與 aggregate report 的欄位是 **TEST_ONLY** 測試封套，沒有新增正式凍結收據／P2 報告 wire contract，也不取代 #313。checker 預設拒絕正式輸入；只有明示 `--synthetic-only` 才能核對這份合成正例。

## 依賴到位後怎麼跑

主任務 #314 的指定命令保留如下；正式 decoder 尚未核定時會 fail closed，不能用合成旗標解除正式門檻：

```sh
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/evaluation/test_p2_baseline_report.py
python scripts/check_p2_report.py --report docs/evaluation/R004_BASELINE_P2_REPORT_<日期>.json --inputs <凍結收據>
```

本任務可立即重跑的合成自測：

```sh
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/evaluation/test_p2_baseline_report.py
uv run python scripts/check_p2_report.py --report tests/fixtures/p2_report/SYNTHETIC/report.json --inputs tests/fixtures/p2_report/SYNTHETIC/receipt.json --synthetic-only
```

checker 只讀，不改寫報告或輸入；report.md 必須與重導出的數字表完全相同。每個數字以 JSON pointer 對應 paired JSON 與來源 bytes SHA；未提供的 latency 是 null，只沿用 response 中已有的 synthetic stats，沒有預估或填補。

## 固定來源與手算 oracle

source 為 staging `434e57922a24d2422226871c0bb672dc7bc3584b` 的既有 `tests/fixtures/q1q5_conformance/SYNTHETIC/valid/`，無原始媒體、GT、formal／clean 包或私人路徑。兩模式 response／decision examples、Q1／Q3 response、request 與 clock 均來自該合成集；新增精確合成標註與以下刻意反例。不是實際 baseline 錄製，不是 #127 kit 實測。

- Q5：RULE_ONLY 的唯一可計分 SWITCH 命中；AGENT_SEQUENTIAL 的 entry camera 刻意改成 CAM_E，未命中。第二個 NO_SWITCH 沒有到達窗尾的 decision，依原 v1 是 COVERAGE_MISSING，兩場分母均只剩一個。另一個 SYNTHETIC-NONSCORING 明列於 annotations，未進 script.events 或分母。t_X／t_N 只在評分端合成 annotations，沒有傳入產品。
- Q1：兩個同樣精確標註的案例，第一個完整命中兩台相機；第二個刻意移除結果並改 PARTIAL。synthetic status 為 1/2，camera recall 為 2/4；正式分母保持零。
- Q3：第一個案例逐欄相符，第二個刻意把 class 改成 car。原 scorer 的 details 分別是全部正確、class=False。固定 staging scorer 沒有 Q3 synthetic aggregate 支援，因此保留 formal_case_count=0、status_accuracy=0/0、value=null，另標 MISSING_IN_PINNED_SCORER；**不是準確率 0%**。不把 evaluation_eligible 設成 true，也不另定一套 Q3 公式。

三個 evaluator 直接沿用原模組與 pinned schemas，不改公式或分母。Q5 v1 bytes SHA 維持 `0fd1ef68c4c83443e8311723224b76f103c142dd018275e7c1596f917e85d9f2`，script 一律 PROPOSED／approval_ref=null。

時間排序驗的是合成封套的明示 offset timestamps 與輸出先驗 hash 的讀取順序；沒有替這些 timestamps 建立正式時間 authority。Q4 在此 probe 是 NOT_EVALUATED_IN_TEST_PROBE，沒有改 D98-5 的正式 P2 範圍。

正式 #314 仍需要使用者劇本凍結、實際 CX-8 輸出與 #313 收據、Claude 獨立精確標註／query_binding、已核 response 版本與正式 aggregate decoder。這些沒有因 #315 的 focused PASS 成立。#307 架構守門尚未交付，記 NOT_RUN；本任務不新增實際 recorded 輸出，#127 kit 記 NOT_RUN。
