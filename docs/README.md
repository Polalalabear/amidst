# Phase 1 scoped 文件導覽 / Scoped Phase 1 documentation

更新：2026-10-14。正式版本 `043bed2d6dac34698260bd37faefc31b9009d3ca`，annotated tag `phase1-scoped-case123-20261014`。
此分支保留 flat `docs/` 路徑，不將正式producer、protocol、核准及收據搬入工程樹。

| 目的 | 入口 |
| --- | --- |
| 當前驗收、結果與負面目標 | [驗收](PHASE1_CASE23_ACCEPTANCE.md)、[完整報告](PHASE1_CASE23_FINAL_REPORT.md)、[實驗紀錄](PHASE1_CASE23_EXPERIMENT_LOG.md) |
| 接手／重建 | [目前交接](CODEX_HANDOFF.md)、[當前prompt](PHASE1_NEXT_CHAT_PROMPT.md)、[正式重建](PHASE1_CASE23_REPRODUCTION.md)、[資料盤點](../data/README.md) |
| 原規格與核准 | [PRD](PRD.md)、[benchmark protocol](PHASE1_BENCHMARK_PROTOCOL.md)、[exact corridor review](PHASE1_CORRIDOR_SCOPE_REVIEW.md)、[post-approval gates](PHASE1_POST_APPROVAL_HANDOFF.md)、[physical materialization](PHYSICAL_EVIDENCE_MATERIALIZATION.md) |
| 設計與持續規則 | [系統設計](SYSTEM_DESIGN.md)、[資料契約](DATA_SCHEMA.md)、[interfaces](INTERFACES.md)、[開發規則](DEVELOPMENT_RULES.md)、[authority](GEOMETRY_AUTHORITY.md)、[provider](GEOMETRY_PROVIDER.md)、[場景](SCENE_VALIDATION.md)、[尺度](SCHOOL_V3_SCALE_REVIEW.md)、[決策](ISSUES_AND_DECISIONS.md) |
| 歷史office與checkpoint | [報告路由](PHASE1_FINAL_REPORT.md)、[旧benchmark](PHASE1_BENCHMARK.md)、[reviewed結果](PHASE1_REVIEWED_BENCHMARK.md)、[旧恢復](PHASE1_RESTORED_RUNTIME.md)、[工作紀錄](WORK_LOG.md)、[實驗紀錄](EXPERIMENT_LOG.md) |
| 保存與清理 | [清理條件](PHASE1_ARTIFACT_CLEANUP.md)、[歷史883204a tag](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/finalization-sprint-883204a)；原始資料與shared runtime繼續保留 |
| 最新工程demo與Phase2 | [工程demo](https://github.com/Polalalabear/amidst/blob/c6661dd53507805deb4613f30afb31798987bfd5/docs/engineering/DEMO_V1.md)、[工程進度](https://github.com/Polalalabear/amidst/blob/c6661dd53507805deb4613f30afb31798987bfd5/docs/engineering/PHASE2_LOCAL_REPAIR_0511.md)、[整體重現快照](https://github.com/Polalalabear/amidst/blob/c6661dd53507805deb4613f30afb31798987bfd5/docs/operations/CURRENT_WORK_REPRODUCTION.md) |

原locked review的8次離線引用與aliases見[引用可用性](REFERENCE_AVAILABILITY.md)。

當前限定Case1–3的18/18 Exit gates PASS、clean reproduction完成；Case3 ADE改善0%未達原≥30%目標，
`all_research_targets_met=false`、`overall_metric_pass=null`。局部geometry仍PARTIAL_APPROVED，整校NOT_CERTIFIED、Case4 DEFERRED。
原BLOCKED／failed assembly與comparison records保留原bytes及日期；它們不覆蓋新增的final acceptance。
本輪只更新導覽與引用，未重新跑native export、inference、evaluation、模型或程式測試。

English: Release043bed2 and tag `phase1-scoped-case123-20261014` preserve the bounded Case1–3 workflow:
18/18 Exit gates passed with clean reproduction. Case3's0% ADE gain missed the initial≥30% target;
no overall metric pass or whole-school certification is claimed. Historical failed/blocked records remain intact.
Use the current acceptance, report and reproduction links above; legacy prompts are historical.
Engineering/main work remains separate. This update changes documentation only and retires no assets or worktrees.
