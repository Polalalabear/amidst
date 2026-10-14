# Current handoff / 目前工作交接

日期：2026-10-14。Phase1 Case1–3 workflow 已完成正式範圍內驗收；目前沒有剩餘的 Case2／Case3 工程 blocker。
有效判定是 [acceptance receipt](../data/finalization/reviewed_run_case123_formal_v2_20261014/acceptance_verification.json)：
**PHASE1_EXIT_GATES_PASSED、18/18 gates PASS、freeze_allowed=true**。
原 assembly 與原 reproduction 的失敗 receipt 保留原 bytes；它們的歷史狀態不覆蓋新增的最終判定。

實作與結果 worktree：`/Users/polalabear/Developer/amidst/.local-worktrees/phase1-case23-formal`，
branch `codex/phase1-case23-formal`。已驗證 producer milestone `c4a8a0acfd3de2a8e266cf8463c9982610e5fe1d`；
master SHA `55337cc70ac1c28ecaa4f9b0e586cb8679ef6a1b9c4b9c631ba98ac69f826fe8`。
已發布 curated release 為 `043bed2d6dac34698260bd37faefc31b9009d3ca`，遠端 `phase1/finalization-sprint`；
annotated tag `phase1-scoped-case123-20261014` peel 到相同 SHA。當前文件 PR 在獨立
`codex/docs-phase1-scoped-progress`，不移動formal／main／frozen refs。總入口：[文件索引](README.md)。
發布核對另存同一 release 目錄的 local `publication_receipt.json`，不把未發布的 SHA 當成遠端狀態。

完整標準與第一版 demo 的差异見 [驗收標準](PHASE1_CASE23_ACCEPTANCE.md)；
結果、限制與負面研究結果見 [正式報告](PHASE1_CASE23_FINAL_REPORT.md)，
重建入口見 [reproduction guide](PHASE1_CASE23_REPRODUCTION.md)。
原 HR01–04 與 exact six-cell union 核准沿用；Case2 已有使用者直接核准的
[union interior branch addendum](../configs/finalization/case2_interior_branch_addendum_v1.json)。
這項定義只使用既有 union 內、同來源鏡頭的可見 anchors；真正穿越門孔仍需原 PORTAL gate。

保留的重要限制：

- Case3 主 gap 的 C 相對 A ADE 改善 **0%**，原初始研究目標 30% **TARGET_MISSED**；
  workflow 可驗收有效負面結果，不代表研究優勢已證明。沒有 overall metric PASS 或未核准的跨案例加權。
- 原 raw visibility graph 的 MAX_BRANCH_FACTOR 終止保留；完整性僅限已定義且凍結的 source class grammar，
  不宣稱任意連續路徑／整棟建築 search 完整。
- Overall physical authority **PARTIAL_APPROVED**；school surface **NOT_CERTIFIED**；Case4 **DEFERRED**。
- Main 第一版 demo、canonical source 與 Phase2 工作保持隔離。現行 Phase2 使用
  `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization`、`codex/simulation-engineering`，
  正由另一項工作推進；不要把歷史 `5b51d2c` frozen checkpoint 當成現在的工作狀態，勿修改其檔案、index、refs 或 services。
- 此工作尚未進行 shared-runtime cleanup；保留目前 worktrees、raw deliveries 與 source，直到確認共享任務完成。

English: The bounded Case1–3 workflow passes all 18 formal Exit gates. The final acceptance
receipt is authoritative; original failed assembly/comparison receipts remain intact. The
frozen producer milestone is c4a8a0ac and publication must be checked against the dated tag
and remote sprint branch. Case3's initial 30% ADE improvement target was missed (0% measured);
no overall research-target PASS is claimed. Authority remains partial, school geometry is
not certified and Case4 is deferred. Active Phase2 work is isolated in its own checkout and
must not be modified. Use the linked standards, final report and reproduction guide.
