# 文件導覽 / Documentation

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

本頁是 Q1–Q5 第一版 Demo 的現行文件索引（2026-10-27，D91）。過去的資料（Office Demo、3D 線、Phase 1／2、早期討論稿）已封存，見[封存](#封存)。即時狀態以[任務板與決策記錄 #93](https://github.com/Polalalabear/amidst/issues/93) 為準。

兩條線並行（D87）：**Line 1** 是 r004 A4-1／B4-1 baseline（D89）；**Line 2** 是複雜場景。

### 規則

- [開發規則](specs/DEVELOPMENT_RULES.md)（根目錄 [DEVELOPMENT_RULES.md](DEVELOPMENT_RULES.md) 是指向它的符號連結）
- [AGENTS.md](../AGENTS.md)、[CLAUDE.md](../CLAUDE.md)：共同規則與 Claude Code 的閱讀順序
- [Q1–Q5 產品規格](specs/Q1Q5_PRODUCT_SPEC.md)（取代已封存的 PRD、系統設計、資料結構與介面文件）

### 契約

- [Q1–Q5 第一版契約](contracts/Q1_Q2_FIRST_DEMO_V1.md)：現行版在 `codex/q1q5-staging`（契約 B，[#237](https://github.com/Polalalabear/amidst/pull/237)）；mainline 的副本不手改。

### Line 1：r004 baseline

- [Baseline 驗收計畫](agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md)：驗收條件 AC1–AC8、工作分配（§4）
- [D79 決策窗文件](evaluation/Q5_DECISION_WINDOW_D79.md)：Q5 逐事件評分範圍
- [A4／B4 情境卡 v1](https://github.com/Polalalabear/amidst/pull/253)（D89；#253 合併後在 `docs/evaluation/R004_A4B4_SCENARIO_CARDS_V1.md`）
- [Workbench v2 設計](agents/WORKBENCH_V2_Q1Q5_DESIGN.md)

### Line 2：複雜場景

- [兩條線計畫](https://github.com/Polalalabear/amidst/pull/252)（D87；#252 合併後在 `docs/agents/Q1Q5_TWO_LINE_PLAN_20261027.md`）
- [複雜情境卡 v2](https://github.com/Polalalabear/amidst/pull/261)（#261）、[Q5 評分規則 v2 設計稿](https://github.com/Polalalabear/amidst/pull/258)（#258）：Draft，尚未合入

### 評估

- [評估文件資料夾](evaluation/)：目前有 D79 決策窗文件；其餘評估文件在上列 Draft PR。

### 營運與交接

- [最新協調者交接（2026-10-27）](agents/COORDINATOR_HANDOFF_20261027.md)；前一份 [2026-10-26](agents/COORDINATOR_HANDOFF_20261026.md)
- [Q1–Q5 進度導覽](operations/Q1Q5_PROGRESS.md)：全部 PR 與 issue 的分類
- [本機測試設定](operations/Q1Q5_LOCAL_TEST_SETUP.md)

### 封存

- [封存索引](archive/ARCHIVE_20261027.md)：Office Demo、3D 線、Phase 1／2、早期 Q1–Q5 討論稿與 `docs/specs/` 的舊規格。原檔留在原位，歷史 `.md` 的檔頭有「已封存」註記；JSON、圖檔與 `history/` 不動。

### 資料夾與符號連結

| 資料夾 | 內容 |
| --- | --- |
| [specs/](specs/) | 開發規則與產品規格；舊 PRD 等已封存 |
| [contracts/](contracts/) | 契約 |
| [agents/](agents/) | 計畫、協調者交接、設計文件 |
| [evaluation/](evaluation/) | 評估與決策窗文件 |
| [engineering/](engineering/) | 工程紀錄（多數已封存，見封存索引） |
| [operations/](operations/) | 進度導覽、測試設定、營運文件 |
| [research/](research/) | 研究紀錄（已封存） |
| [history/](history/) | 歷史 checkpoint 紀錄 |

此頁是唯一文件索引。根目錄另保留 exact corridor review 與 runtime 使用的 checkpoint JSON；三個符號連結維持 locked protocol、核准 review 與歷史 geometry reports 的原路徑。正文位於分類資料夾，不另建逐檔轉址文件。

## English

This page is the current documentation index for the Q1–Q5 first demo (2026-10-27, D91). Older material (the Office demo, the 3D line, Phase 1/2 and early discussion drafts) is archived; see [Archive](#archive). Live status is on the [task board and decision log #93](https://github.com/Polalalabear/amidst/issues/93).

Two lines run in parallel (D87): **Line 1** is the r004 A4-1/B4-1 baseline (D89); **Line 2** covers complex scenes.

- **Rules:** [development rules](specs/DEVELOPMENT_RULES.md) (the root [DEVELOPMENT_RULES.md](DEVELOPMENT_RULES.md) is a symlink to it), [AGENTS.md](../AGENTS.md), [CLAUDE.md](../CLAUDE.md), and the [Q1–Q5 product specification](specs/Q1Q5_PRODUCT_SPEC.md), which replaces the archived PRD, system design, data schema and interfaces.
- **Contract:** [Q1–Q5 first-demo contract](contracts/Q1_Q2_FIRST_DEMO_V1.md). The current version is on `codex/q1q5-staging` (contract B, [#237](https://github.com/Polalalabear/amidst/pull/237)); the mainline copy is not edited by hand.
- **Line 1:** [baseline acceptance plan](agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md), [D79 decision-window document](evaluation/Q5_DECISION_WINDOW_D79.md), [A4/B4 scenario cards v1](https://github.com/Polalalabear/amidst/pull/253) (#253), [workbench v2 design](agents/WORKBENCH_V2_Q1Q5_DESIGN.md).
- **Line 2:** [two-line plan](https://github.com/Polalalabear/amidst/pull/252) (#252), [complex scenario cards v2](https://github.com/Polalalabear/amidst/pull/261) (#261) and the [Q5 scoring v2 design](https://github.com/Polalalabear/amidst/pull/258) (#258); all Draft PRs, not yet merged.
- **Operations:** [latest coordinator handoff (2026-10-27)](agents/COORDINATOR_HANDOFF_20261027.md), [progress guide](operations/Q1Q5_PROGRESS.md), [local test setup](operations/Q1Q5_LOCAL_TEST_SETUP.md).

### Archive

The [archive index](archive/ARCHIVE_20261027.md) lists the Office demo, 3D-line, Phase 1/2, early Q1–Q5 discussion and old `docs/specs/` documents. Original files stay in place; historical `.md` files carry an "archived" header line. JSON, images and `history/` are untouched.

This is the only documentation index. The root retains the exact corridor review, the runtime checkpoint JSON and three symlinks required by locked protocol, review and geometry-report references; the body text lives in the category folders, with no per-file redirect documents.
