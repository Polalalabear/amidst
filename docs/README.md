# 文件導覽 / Documentation

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

更新：2026-10-14。這是工程文件索引，基線 `c6661dd53507805deb4613f30afb31798987bfd5`；main 程式維持已驗證 R1 `439c866`。
最新 scoped Phase1 在独立 `043bed2d6dac34698260bd37faefc31b9009d3ca`，保留 flat 文件布局及 hash 綁定的原路徑。

### 先從這裡開始

| 目的 | 入口 |
| --- | --- |
| 了解目前進度與續作 | [目前交接](operations/CODEX_HANDOFF.md)、[當前 prompt](operations/PHASE1_NEXT_CHAT_PROMPT.md) |
| 展示第一版 demo | [唯一 demo 指南](engineering/DEMO_V1.md)：五段核心5/5、含Agent加映5/6；動態DEMO_URL及新origin限制 |
| 恢復既有本機狀態 | [工作樹／資產／PG／Ollama／SQLite重現快照](operations/CURRENT_WORK_REPRODUCTION.md)、[資料盤點](../data/README.md) |
| 核對Phase2品質與main範圍 | [05／11驗收與負結果](engineering/PHASE2_LOCAL_REPAIR_0511.md)：R2全48常規12/40，R3真實demo失敗；05 baseline，功能估約50% |
| 核對正式Phase1 | [043bed2驗收](https://github.com/Polalalabear/amidst/blob/043bed2d6dac34698260bd37faefc31b9009d3ca/docs/PHASE1_CASE23_ACCEPTANCE.md)、[正式報告](https://github.com/Polalalabear/amidst/blob/043bed2d6dac34698260bd37faefc31b9009d3ca/docs/PHASE1_CASE23_FINAL_REPORT.md)、[重建](https://github.com/Polalalabear/amidst/blob/043bed2d6dac34698260bd37faefc31b9009d3ca/docs/PHASE1_CASE23_REPRODUCTION.md) |
| 分支、PR與歷史恢復 | [發布與保留範圍](operations/BRANCH_PUBLICATION.md)、[清理條件](operations/PHASE1_ARTIFACT_CLEANUP.md)、[既往清理紀錄](history/LOCAL_STORAGE_CLEANUP_20261014.md) |

Phase1 Case1–3的18 Exit gates PASS及clean重現已完成，但Case3 ADE改善0%未達原30%目標；
幾何仍PARTIAL_APPROVED、整校NOT_CERTIFIED、Case4 DEFERRED。工程Office／Classroom35人審差異与38 UNKNOWN checks
屬另一範圍，不互相升權。原測試數字各自綁定日期／checkpoint，本次僅做文件與連結檢查。

### 功能與規格

| 主題 | 文件 |
| --- | --- |
| 工作台／展示庫／場景來源 | [共用工作台](engineering/SHARED_WORKBENCH.md)、[来源展示](engineering/SOURCE_PRESENTATION_WORKBENCH.md)、[人物調查／展示庫](engineering/WORKBENCH_INVESTIGATION_GALLERY.md)、[覆蓋表](engineering/WORKBENCH_EXPERIMENT_COVERAGE.md) |
| Blender來源／曲線／多解／人審 | [畫面檢索](engineering/BLENDER_CAMERA_FRAME_RETRIEVAL.md)、[曲線回放](engineering/BLENDER_MOTION_RECONSTRUCTION.md)、[跨鏡頭多解](engineering/BLENDER_CROSS_CAMERA_RECONSTRUCTION.md)、[物理篩選](engineering/BLENDER_PHYSICAL_CANDIDATE_FILTER.md)、[人審契約](engineering/BLENDER_PHYSICAL_HUMAN_REVIEW.md) |
| 感知與工程研究 | [模擬](engineering/SIMULATION_ENGINEERING.md)、[局部camera pilot](engineering/LOCAL_CAMERA_PILOT.md)、[accuracy-v2](research/LOCAL_CAMERA_ACCURACY_V2.md)、[研究protocol](research/LOCAL_CAMERA_EVENT_PROTOCOL.md) |
| 保存／Agent／PG | [本機產品](engineering/LOCAL_PHASE2_PRODUCT.md)、[Agent邊界](engineering/AGENT_RETRIEVAL_BOUNDARY.md)、[ABC整合](engineering/PHASE2_LOCAL_BATCH_ABC.md)、[run／操作員排演](engineering/WORKBENCH_RUN_STUDY.md)、[端口與label](engineering/SYSTEM_PORTS_AND_LABEL_GUIDANCE.md) |
| 原frozen整合 | [Phase2 frozen mock契約](engineering/PHASE2_INTEGRATION.md)、[歷史hardening](history/PHASE2_INTEGRATION_HARDENING.md) |
| 需求與資料設計 | [PRD](specs/PRD.md)、[系統設計](specs/SYSTEM_DESIGN.md)、[資料契約](specs/DATA_SCHEMA.md)、[interfaces](specs/INTERFACES.md) |
| 持續規則與authority | [開發規則](specs/DEVELOPMENT_RULES.md)、[幾何authority](specs/GEOMETRY_AUTHORITY.md)、[provider](specs/GEOMETRY_PROVIDER.md)、[場景核對](specs/SCENE_VALIDATION.md)、[尺度](specs/SCHOOL_V3_SCALE_REVIEW.md)、[決策](specs/ISSUES_AND_DECISIONS.md) |
| 歷史研究與收據 | [Phase1報告路由](research/PHASE1_FINAL_REPORT.md)、[舊benchmark](research/PHASE1_BENCHMARK.md)、[實驗紀錄](history/EXPERIMENT_LOG.md)、[工作紀錄](history/WORK_LOG.md)、[c666完整交接](history/CODEX_HANDOFF_20261014_C666.md) |

引用的公共／離線範圍見[引用可用性](operations/REFERENCE_AVAILABILITY.md)。

此頁為工程分支唯一文件索引。specs／engineering／research／operations／history分別維護契約、功能、研究、續作與歷史。
三個根目錄symlink及 corridor review／checkpoint JSON 保持原位置，避免破壞 locked references；原protocol、核准及凍結收據未修改。
Private或已退役raw references以離線路徑標示，curated Git證據仍可瀏覽；tag不等於raw備份。

## English

This is the engineering index at documentation baseline c6661dd. Main retains the validated R1 code baseline439c866;
the scoped Phase1 release043bed2 remains separate with its original flat paths and hash-bound aliases.
Start with the [current handoff](operations/CODEX_HANDOFF.md), [demo guide](engineering/DEMO_V1.md),
[dependency/reproduction snapshot](operations/CURRENT_WORK_REPRODUCTION.md), [data inventory](../data/README.md)
and [branch/publication scope](operations/BRANCH_PUBLICATION.md).

The core demo has5/5 rehearsed segments; including Saved Agent gives5/6 because the new origin has not recovered
old credentials. R2 completed48 tasks but passed12/40 regular tasks; R3's engineering checks passed and its first actual
model demo failed. Keep05 baseline and approximately50% Phase2 functional effort.
Scoped Phase1 passes18 workflow gates and clean reproduction, but Case3's ADE gain is0% and its initial target remains unmet.
Whole-school geometry is not certified; Case4 is deferred. These scopes do not upgrade one another's authority.

The tables above link every maintained topic. [Specifications](specs/), [engineering](engineering/), [research](research/),
[operations](operations/) and [history](history/) retain their roles. Locked protocols, approvals, original receipts and
root aliases remain unchanged. Retired/private raw paths are offline references. This refresh validates documents and
references only; dated test totals are not new test executions.
