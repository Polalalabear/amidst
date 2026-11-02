# FEAT-4 整合進度：BLOCKED，未完整交件

依 [#371 歸併](https://github.com/Polalalabear/amidst/issues/371#issuecomment-6556604761) 合17個精確 head（#258 用協調者更新 0b6e800），再 no-ff 接已交 FEAT-1 #394 的共用檢查器／守門。各 head／merge commit 與實測結果見同名 JSON；#261 只在原分支回修，沒有合 mainline 進此樹。#274 沒有合入。

## 可驗部分

D105-4 定案檔精確重現 SHA `0daa1508e2a67607cdc6bac54684b1b5449d3a651325e5af23dfe0afb1bd3b7e`；預設全 PENDING 檔未改。CLI 以定案檔為預設，覆寫檔沒有相符 pin 就拒絕。U-D1／U-D2／U-D4 不代選。

v2 scorer 加 D93 逐事件與兩個 overlap ratio 標籤、不計分原因／相關 pending keys／計數；LONG 閘對齊類別，RETURN 加 d>L 與前窗檢查。沒有更改分母規則或 v1 bytes。SYNTHETIC LIMIT 正例改為合規 d=.8>L，前窗 [0,1.8)、次個 RETURN 恰在1.8右端外；原 cutoff6.8、prefix及拒絕斷言保留，沒有放寬測試去收 d=L。

#363 統一10鍵／PENDING_USER，E5依固定 D93 在合成範圍計分並單列；PENDING／SETTLED 都5列不計分。native 報告實際逐場呼叫 v2 scorer，跨場彙總主群／各類／OVERLAP／LIMIT，未計分逐群列出，不讀 oracle scored rows 作評分結果。工程彙總不採用新的正式 report wire。

#261 原分支 head `b5302a0ad9a1895d728946d824854b6001b6b66a` 的文件 hash `02d98c06ac93b5b1eec019d65415eada7b751b4c6e76d3982a28aa36d9efd88b` 已記錄 U7；四卡現為五份 private plans。RR 同一 run 的 S_a [0,14)、S_b [14,28) 各2／3次搜尋，S_b W1@14只作定位候選，真實 seed UNKNOWN／observation_id MISSING。舊卡片副本依 B-4 移除，plans只引原PR head/hash。

#351 文件記錄11條U8推薦案已選及 hash 影響表，不猜正式 schema／A4 grammar／C2 field names。#273 文件私人路徑改佔位變數，沒有重跑 U15 參數實驗。

## 尚未通過

- P1-5 真實 UK-8／P-OV3 與 P1-6 formal APPROVED 路徑未完成；缺採用的安全靜態 evidence／核准記錄表示，且正式 run／clock／參數／seed／新 script freeze 仍缺。保持拒絕，不把計畫或自填 hash 當核准。
- CQ-21 尚未實作。全 strict 實跑 **27 passed／21 failed（CQ21_IMPLEMENTATION_MISSING）**，不能稱全綠；正式 wire／schema、A4封閉核准表達與選項測試矩陣待協調者固定，見 [規格提案](https://github.com/Polalalabear/amidst/issues/371#issuecomment-6577282238)。舊五鍵合成checker PASS 不替代新格式 adapter。
- 架構守門 inference／schemas PASS，但 authority **FAIL**：#258指定新設計文件 pin 尚未重釘；#260夾帶的 kit 文件既非原staging也非rc5。沒有自行新增允許 bytes，[pin提案](https://github.com/Polalalabear/amidst/issues/371#issuecomment-6576987672)已交指定協調者。`--allow` 只處理指定合入的 changed paths，不能隱藏 AUTHORITY_DRIFT。

目前甲仍 UNFROZEN，依 D105 在批次卡明列 fallback／未完成P1。正式 #328→#329→#330 資料命令、G4新格式與U15比較均 NOT_RUN；沒有渲染、模型呼叫或原資產變更。

## 驗收命令

共同環境：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests/evaluation AMIDST_REQUIRE_IMPL=1`，既有 Python 3.12，不安裝依賴。

```bash
AMIDST_Q5_V2_DRIVER=q5_v2_test_driver AMIDST_Q5_ADAPTER_V2_DRIVER=q5_adapter_v2_test_driver \
AMIDST_L2_REPORT_DRIVER=l2_complex_test_driver uv run --no-sync --offline python -m pytest -q \
  tests/evaluation/test_q5_switch_eval_v2.py tests/unit/test_q5_switch_eval.py \
  tests/evaluation/test_feat4_settled_scoring.py tests/evaluation/test_q5_script_adapter_v2.py \
  tests/unit/test_q5_script_adapter.py tests/evaluation/test_feat4_plan_sources.py \
  tests/evaluation/test_l2_complex_report.py tests/q1q5/test_check_event_run_bundle.py \
  tests/q1q5/test_check_baseline_freeze.py tests/q1q5/test_l2_linker_replay.py \
  tests/q1q5/test_l2_detection_options.py tests/unit/test_architecture_guard.py
# 423 passed；QT-25依 FEAT1_BASELINE_INTEGRATION_20261102.md 的固定kit獨立程序另52 passed。
uv run --no-sync --offline python -m pytest -q tests/q1q5/test_g4_receipt_overlay.py
# exit1：27 passed／21 failed，缺CQ-21實作，不隱藏。
node --test frontend/workbench-v2/long-timeline-data.test.mjs \
  frontend/workbench-v2/timeline-model.test.mjs frontend/workbench-v2/monitor-wall-model.test.mjs
# 38 passed。
git diff --exit-code 434e57922a24d2422226871c0bb672dc7bc3584b -- \
  src/amidst/evaluation/q5_switch_eval.py docs/evaluation/Q5_SWITCH_EVAL_V1.md
git diff --check 434e57922a24d2422226871c0bb672dc7bc3584b HEAD
```

完整守門命令、允許路徑、FAIL findings 與報告 SHA 在 PR Actual output／JSON收據，不將 BLOCKED 草稿當完整交件或合併授權。
