> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# Phase 1 demo / 展示與驗收邊界

更新：2026-10-14。目前共用工作台約九分鐘的操作、啟動與測試範圍見
[第一版 demo 指南](../engineering/DEMO_V1.md)。來源影像、多解路線與 E1
保存調查已完成其限定操作排演；Saved Agent 加映及最新模型品質仍有未完成項，
以該指南與當輪收據為準。

獨立正式分支 `phase1/finalization-sprint` 的已發布 commit
`043bed2d6dac34698260bd37faefc31b9009d3ca`，及標籤
`phase1-scoped-case123-20261014`，已完成受限 Case 1–3 的實際執行、
乾淨 checkout 重現與 **18 項 Exit gates PASS**，狀態為
**PHASE1_EXIT_GATES_PASSED**。精確範圍與原失敗紀錄見
[該版本正式報告](https://github.com/Polalalabear/amidst/blob/043bed2d6dac34698260bd37faefc31b9009d3ca/docs/PHASE1_CASE23_FINAL_REPORT.md)
與 [Exit gate 收據](https://github.com/Polalalabear/amidst/blob/043bed2d6dac34698260bd37faefc31b9009d3ca/data/finalization/reviewed_run_case123_formal_v2_20261014/acceptance_verification.json)。
Case 3 primary ADE 改善 **0%**，仍未達初始 **30%** 研究目標；整校物理權限仍為
**PARTIAL_APPROVED**，沒有整校可行走／導航認證。這份受限正式結果不改寫工作台
Office 候選的 UNKNOWN，也不代表 Phase 2 品質通過。

以下是 **2026-10-06 歷史 DIAGNOSTIC** 展示，不是上述新正式 Case 1–3 recordings。
當時的 formal NOT_RUN 狀態已由新報告更新；歷史診斷產物本身沒有升格。
本次只核對既有位置，未重跑 producer、render 或模型。

三站 `office`、`auditorium`、`corridor` 的既有 RRD、PNG 與 presentation JSON
目前位於 canonical repository 的 ignored 目錄：

```text
data/pilot/phase1_finalization_20261006/local_run/diagnostics/<stream>/demo/
data/pilot/phase1_finalization_20261006/fresh_run/diagnostics/<stream>/demo/
```

本次核對時，以上六個目錄均已有 `diagnostic.rrd`、`preview.png`、`presentation.json`；
它們是本機 ignored 產物，不隨 GitHub clone 提供，也不保證後續清理後仍存在。
舊 `data/finalization/local_run/diagnostics/<stream>/demo/` 目前沒有這三種檔案，
不可再當作現行 replay／preview 入口。使用 canonical 目錄中實際存在的 RRD：

```sh
uv run rerun /absolute/path/to/diagnostic.rrd
```

查看 scene context、校準 cameras、OBSERVED/GAP、projection method/confidence、
configured Top-K/timing（若 legacy Graph contract 可執行）。GT debug 在獨立 entity
layer，初始不顯示；可由 Rerun entity visibility 控制。未取得 authority 的 collider
pruning、floor/scope certification 與 surface-constrained school inference 應顯示
N/A，不得由 annotation box 或空 collider 集合視覺上宣稱 PASS。

The historical PNG and presentation JSON remain diagnostic previews; their reader
checks belong to the original checkpoint. A replayable diagnostic recording does
not certify school geometry. The published scoped formal result above is separate
from these previews and from the current workbench / Phase 2 quality gates.
