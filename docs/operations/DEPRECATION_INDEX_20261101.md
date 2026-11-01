# 廢棄／過時索引（2026-11-01，D108）

依 [#93 D108-3](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6557942628) 建立。本索引列出 repo 內過時或已被取代的文件、規則條文，以及 GitHub 上過時的 PR、議題與遠端分支，供 2026-11-05 大整理（D104-6）處理。

- **只標記、不處理**：不刪檔、不改寫被列文件的內文、不關閉別人的 PR、不刪分支。分支只列在本表，不加標籤。
- **狀態詞**：`DEPRECATED`（不再使用、只留歷史）、`SUPERSEDED-BY <對象>`（已被取代）、`OUT-OF-DEMO-SCOPE`（仍有價值但不在 11-04 demo 範圍）、`PENDING-CLEANUP-1105`（待 11-05 依條件處理）。
- **GitHub 標籤**（D108-3）：`deprecated`、`superseded`、`out-of-demo-scope`。PENDING-CLEANUP-1105 不另設標籤。標為 superseded 的 PR／議題另有一行留言寫明取代處。
- 現行規則以 `CLAUDE.md`、`AGENTS.md`、`docs/DEVELOPMENT_RULES.md`（D108 改寫版）與 #93 D104～D108 為準。2026-10-27 以前已封存的 91 份文件見 [封存索引](../archive/ARCHIVE_20261027.md)，本表不重複逐檔列出。
- 快照：`origin/mainline/q1q5`＝`0d78599`、`origin/codex/q1q5-staging`＝`434e579`；PR 與議題狀態於 2026-11-01 以 `gh pr list --state all`、`gh issue list --state all` 查得。

## 1. 文件與規則條文

### 1.1 本 PR 從規則檔移除或改寫的條文（D108-1）

| 對象 | 狀態 | 理由 | 出處 |
| --- | --- | --- | --- |
| `CLAUDE.md` 舊閱讀順序（以 `COORDINATOR_HANDOFF_20261027.md` 與兩條線計畫為起點，含「once #252 merges」） | SUPERSEDED-BY 新閱讀順序（#93 D104 起 → #306 → #279 D105 §0 → feature 議題） | 10-27 交接早於 D95～D108；#252、#253 已合併 | D104、D105、D108-1 |
| `CLAUDE.md`「For Office demo tasks…」分工段 | DEPRECATED | Office Demo 線已結束（D63）；現行分工改寫在 `AGENTS.md`「Ownership」 | D63、D91、D107-4 |
| `CLAUDE.md`／`AGENTS.md`「self-selected from the task board: take only `ready` issues…, claim by comment and `in-progress`」 | SUPERSEDED-BY feature 認領（#279 §0 D105 版） | 認領單位改成 feature | D95-2、D103-2、D105 |
| `CLAUDE.md` 模型表「Formal code review (every code PR)」與 Office 範例（K1、K4、C4a…） | SUPERSEDED-BY「Feature review (every feature PR, D104-2)」與現行範例 | Claude 不再逐行審程式，只審四件事 | D104-2、D105-7 |
| `AGENTS.md`「Use `frontend/workbench/` as the primary UI」；`DEVELOPMENT_RULES`「共用網頁工作台」以 `frontend/workbench/` 為主入口 | SUPERSEDED-BY `frontend/workbench-v2/`（唯一 UI 入口） | #306 §2；同時解掉產品規格 U-13 的 UNKNOWN | #306、D108-1 |
| `AGENTS.md`「Task ownership follows §4 of the baseline acceptance plan」 | SUPERSEDED-BY `AGENTS.md`「Ownership」表 | §4 早於 D97～D107（見 1.2） | D97、D104、D107-4 |
| `AGENTS.md`「records its actual output, both in its PR description and as a comment on its issue」 | SUPERSEDED-BY「Actual output 只貼 PR，議題只留 PR 連結」 | 簡化紀錄 | D104-5、D105 B-16 |
| `AGENTS.md`「Claude maintains the `ready`/`blocked`/`needs-auth` labels」 | SUPERSEDED-BY 標籤只留 feature 層級（`codex-claimed`、`needs-claude-review`、`blocked-user`）＋ D108 三個標記標籤 | 標籤只留 feature 層級 | D104-5、D106-1、D108-3 |
| `AGENTS.md`「Codex uploads its current ones in its next PR (CX-4 or CX-10)」 | DEPRECATED | 一次性指示，已過期；通則保留 | D95 後佇列改制 |
| `AGENTS.md` source-of-truth 清單中「#252／#253 once merged」的寫法 | SUPERSEDED-BY 檔案路徑 | #252（`9708fb6`）、#253（`0edd8a3`）已合進 mainline | 進度導覽 |
| `DEVELOPMENT_RULES` 開頭「需求依 PRD、模組責任依 SYSTEM_DESIGN、已採用解法依 ISSUES_AND_DECISIONS」與文件分工表的 `PRD.md`、`SYSTEM_DESIGN.md`、`ISSUES_AND_DECISIONS.md`、`WORK_LOG.md`、`CODEX_HANDOFF.md`、`DATA_SCHEMA.md`／`INTERFACES.md` 列 | SUPERSEDED-BY `docs/specs/Q1Q5_PRODUCT_SPEC.md`、#306、#93、PR 的 Actual output、最新協調者交接 | 這些文件已歸為歷史 | D91-2、#270 |
| `DEVELOPMENT_RULES`「優先重用既有 checkout…不要為每個 milestone 建 worktree、clone」 | SUPERSEDED-BY 本機 checkout 規則（共用乾淨 checkout＋scratchpad `git clone --shared`） | 與 D87 寫入規則、D108-4 衝突 | D87、D108-4 |
| `DEVELOPMENT_RULES` 驗證指令 `uv run pytest`／`ruff check .`／`mypy`（full suite） | SUPERSEDED-BY feature 整合驗收（-T、focused、守門、GT 隔離、`git diff --check`） | 與「只跑 focused」及 D104-2 衝突 | D104-2、D105-7-8 |
| `DEVELOPMENT_RULES`「不串接外部模型 API」（無例外） | SUPERSEDED-BY D107 限定例外（只限俯視圖示意） | 使用者 11-01 指示 | D107 |

GT 隔離、原始資產保護、不渲染（除非授權）、可追溯性與 identity／物理 UNKNOWN 的條文語意都沒有改。

### 1.2 repo 內過時或已被取代、但本 PR 不改內文的文件

| 對象 | 狀態 | 理由 | 出處 |
| --- | --- | --- | --- |
| Office 時期文件（`docs/agents/OFFICE_DEMO_*.md`、`K1_BLOCKERS_DECISION_20261016.md`、`docs/contracts/OFFICE_*_V1.md`、`docs/operations/CLAUDE_INITIAL_HANDOFF.md`、`OFFICE_DEMO_LAUNCHER.md` 等 38 份） | DEPRECATED | 已在封存索引 §1「Office」列出並加檔頭；舊 CLAUDE.md 曾把它們當閱讀起點 | D63、D91（[封存索引](../archive/ARCHIVE_20261027.md)） |
| Phase 1／2、3D 線、早期 Q1–Q5 討論稿（封存索引 §1 其餘 53 份） | DEPRECATED | 已封存 | D91 |
| `docs/specs/PRD.md`、`SYSTEM_DESIGN.md`、`ISSUES_AND_DECISIONS.md`、`DATA_SCHEMA.md`、`INTERFACES.md` | SUPERSEDED-BY `docs/specs/Q1Q5_PRODUCT_SPEC.md` | 已封存，但 D108 前仍被 `DEVELOPMENT_RULES` 當現行引用（本 PR 已改） | D91-2 |
| `docs/engineering/SHARED_WORKBENCH.md`、`frontend/workbench/` | DEPRECATED | UI 唯一入口是 `frontend/workbench-v2/`；舊工作台程式不刪 | #306 §2、D108-1 |
| `docs/engineering/AGENT_RETRIEVAL_BOUNDARY.md` | PENDING-CLEANUP-1105 | 屬 Phase 2，但契約第 35 行釘住其 SHA，未加封存檔頭；契約更新後再處理 | 封存索引 §2 |
| `docs/agents/COORDINATOR_HANDOFF_20261026.md` | SUPERSEDED-BY `COORDINATOR_HANDOFF_20261027.md` | 檔頭已寫明 | D91 |
| `docs/agents/COORDINATOR_HANDOFF_20261027.md` | PENDING-CLEANUP-1105 | 交接快照（#306 A5），早於 D95～D108；流程以 #93 為準。下一份協調者交接上傳後改為 SUPERSEDED-BY 該檔 | D95～D108 |
| `docs/agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md` §4「工作分配」 | SUPERSEDED-BY `AGENTS.md`「Ownership」、feature 議題 #369～#376 | §4 的任務分配早於佇列與 feature 制；§1～§3、§5 與 AC1～AC8 仍現行 | D95、D103、D104 |
| `docs/agents/Q1Q5_TWO_LINE_PLAN_20261027.md` §2～§3 工作分配、§5 里程碑順序 | SUPERSEDED-BY feature 議題與 D105-7 批次順序 | 兩條線的定義（§1）與 §4 並行規則仍現行 | D103、D104、D105 |
| `docs/agents/WORKBENCH_V2_Q1Q5_DESIGN.md` | PENDING-CLEANUP-1105 | 檔頭已註明部分被 #243、#255 更新；demo UI 新規格見 #380（PROPOSED） | D86-3、D107-4 |
| `docs/specs/Q1Q5_PRODUCT_SPEC.md` U-13（工作台入口 UNKNOWN） | SUPERSEDED-BY D108-1（`frontend/workbench-v2/` 唯一入口） | 本 PR 的規則改寫回答了此項；規格內文 11-05 再改 | D108-1 |
| `README.md`「Status」段與 `docs/README.md`（2026-10-27 快照） | PENDING-CLEANUP-1105 | 狀態停在 10-27（例如 #253 仍寫成 PR 連結）；#267 衝突照 D105 B-24 取 mainline 版 | D105 B-24 |
| [#279](https://github.com/Polalalabear/amidst/issues/279) 本文 §0 固定提示（D103 以前的版本） | SUPERSEDED-BY [§0 固定提示 D105 版](https://github.com/Polalalabear/amidst/issues/279#issuecomment-6556632821) | 本文保留作歷史；衝突時以留言為準 | D105、佇列恢復公告 |
| #279 本文的舊任務表、子任務議題的舊佇列標籤 | DEPRECATED | 不再作認領依據 | [舊索引作廢](https://github.com/Polalalabear/amidst/issues/279#issuecomment-6556897337)、D106-1 |
| #279 本文最上方的暫停行與「暫停中（D102）」段落 | DEPRECATED | 佇列已恢復 | D105-9、[佇列恢復](https://github.com/Polalalabear/amidst/issues/279#issuecomment-6556614928) |
| #306 A1 的 pin（`docs/DEVELOPMENT_RULES.md` → `80296358…`） | PENDING-CLEANUP-1105 | 這個值是 symlink 本身（內容是字串 `specs/DEVELOPMENT_RULES.md`）的 SHA，不是規則內文；改內文不會讓 A1 變動。建議 D108-2 更新 pin 時改釘 `docs/specs/DEVELOPMENT_RULES.md` | D108-2 |

## 2. PR

| 對象 | 狀態 | 理由 | 出處 |
| --- | --- | --- | --- |
| [#268](https://github.com/Polalalabear/amidst/pull/268) D91 封存六份 Codex 交接（base staging） | OUT-OF-DEMO-SCOPE | 不在 11-04 範圍，保持開啟 | D106-2 |
| [#189](https://github.com/Polalalabear/amidst/pull/189) Q5 As-Is Statechart 與 Journal Invariants | OUT-OF-DEMO-SCOPE | 同上 | D106-2 |
| [#158](https://github.com/Polalalabear/amidst/pull/158) HSV RGB 提案（G6 pending） | OUT-OF-DEMO-SCOPE | 同上；正式索引用 §11 HSV 初值（D75） | D106-2 |
| [#83](https://github.com/Polalalabear/amidst/pull/83) 決策索引、系統總覽、組員上手指南 | OUT-OF-DEMO-SCOPE | 同上；內容早於 D95 | D106-2 |
| [#82](https://github.com/Polalalabear/amidst/pull/82) K7 r003 靜態幾何驗證（do not merge） | OUT-OF-DEMO-SCOPE | 同上；Office／r003 時期 | D106-2 |
| [#163](https://github.com/Polalalabear/amidst/pull/163) r004 圖 v1 提案（已關閉未合併） | SUPERSEDED-BY #227（`3cc05322`）圖 v3、#235（`747bdfea`）、#294 v3_1 | 11-01 已關閉 | D106-2 |
| [#349](https://github.com/Polalalabear/amidst/pull/349) CQ-22 yyin 三題確認疊圖 | SUPERSEDED-BY D105 B-5 選項 1（demo 後從 #294@`0c34287` 開新分支；repo 只存腳本、RECEIPT、無背景 SVG） | 帶原像素，不合併；分支保留當證據 | D105 B-5、B-28 |
| [#361](https://github.com/Polalalabear/amidst/pull/361) 的 head（CQ27/CQ28） | SUPERSEDED-BY FEAT-2 整合分支的 `git cherry-pick -x e7edc98 3deee9e` | head 夾帶 #240 的 mainline 檔與 #349 原像素；PR 不合併，分支保留 | D105-7-3、B-5 |
| [#274](https://github.com/Polalalabear/amidst/pull/274) L2 工程小場景規劃 | OUT-OF-DEMO-SCOPE | 擱置、保留 Draft、標 stretch；D99 沒選 L2-6 | D105 B-6 |

其他開著的 PR（#127、#240、#243、#254～#256、#258、#260、#261、#266、#267、#269、#271～#273、#275、#277、#278、#294、#295、#305、#348、#350～#368、#377～#380）都在 feature 歸併表或 11-03 批次內，不列為過時。

## 3. 議題

| 對象 | 狀態 | 理由 | 出處 |
| --- | --- | --- | --- |
| #97、#98、#109、#131、#183、#184、#198、#204、#206 | DEPRECATED（已完成關閉，不加標籤） | 11-01 關閉，各留 merge SHA | D106-2 |
| #110、#111、#112、#113、#200 | DEPRECATED（已關閉，不加標籤） | 11-01 10:52Z 關閉；D106 記為未抽查，關閉留言的完成處待 11-05 抽查 | D106-2 |
| #129 QT-33 組員 Q5 切鏡評估器 | DEPRECATED（已關閉） | 取消，組員改當評測者 | D96-4 |
| [#144](https://github.com/Polalalabear/amidst/issues/144) QT-39 契約 #135 補完 | PENDING-CLEANUP-1105 | 條件：FEAT-6 合併後，留言指向 #297 與 feature PR，再關 | D105 B-15 |
| [#153](https://github.com/Polalalabear/amidst/issues/153)、[#156](https://github.com/Polalalabear/amidst/issues/156)、[#170](https://github.com/Polalalabear/amidst/issues/170)、[#178](https://github.com/Polalalabear/amidst/issues/178) kit 議題 | PENDING-CLEANUP-1105 | 條件：FEAT-6（含 #127@`e1415f3`）合進 staging 後，留言引用 merge SHA 再關；第 6 個 kit 議題 UNKNOWN | D105 B-14 |
| [#249](https://github.com/Polalalabear/amidst/issues/249) L2-6 工程小場景、[#290](https://github.com/Polalalabear/amidst/issues/290) CQ-11（#274 回修） | OUT-OF-DEMO-SCOPE | 隨 #274 擱置、保留 | D105 B-6 |
| [#87](https://github.com/Polalalabear/amidst/issues/87) GitHub 整理紀錄（10-20） | DEPRECATED | D63 後的一次性整理紀錄，已被 #93 與本索引取代；保持開啟待 11-05 關 | D63、D108-3 |
| [#263](https://github.com/Polalalabear/amidst/issues/263) 文件封存與現況更新（D91） | PENDING-CLEANUP-1105 | S1～S4（#264、#265、#270、#276）都已合併；11-05 留 merge SHA 後關閉 | D97-8 |
| [#88](https://github.com/Polalalabear/amidst/issues/88) 計畫與契約 #86 核准（checkpoint） | PENDING-CLEANUP-1105 | 契約已由 #219、#237（契約 B）取代；是否記錄核准 UNKNOWN，11-05 抽查 | #237 |
| [#99](https://github.com/Polalalabear/amidst/issues/99) QT-06、[#145](https://github.com/Polalalabear/amidst/issues/145) QT-40 conformance 測試包 | PENDING-CLEANUP-1105 | 可能由 #127 kit（FEAT-6）完成；未抽查，不標 superseded | D105 B-14、B-20 |
| [#108](https://github.com/Polalalabear/amidst/issues/108)、[#114](https://github.com/Polalalabear/amidst/issues/114)、[#116](https://github.com/Polalalabear/amidst/issues/116)、[#117](https://github.com/Polalalabear/amidst/issues/117)、[#123](https://github.com/Polalalabear/amidst/issues/123) 舊 QT 議題（標 `blocked`） | PENDING-CLEANUP-1105 | 舊標籤 `blocked`；部分內容已由 #227、#294、#158 等推進，未抽查 | D106 |
| [#89](https://github.com/Polalalabear/amidst/issues/89)、[#128](https://github.com/Polalalabear/amidst/issues/128)、[#130](https://github.com/Polalalabear/amidst/issues/130)、[#137](https://github.com/Polalalabear/amidst/issues/137)、[#138](https://github.com/Polalalabear/amidst/issues/138) 組員任務（標 `ready`） | PENDING-CLEANUP-1105 | 舊 `ready` 自選標籤；組員角色改為評測者（D96-4），#137 依賴未合併的 #83 | D96-4、D106 |
| [#186](https://github.com/Polalalabear/amidst/issues/186) 本機 Qwen3 未通過 | PENDING-CLEANUP-1105 | 不在 11-04 關鍵路徑；是否仍需處理 UNKNOWN | — |

子任務議題（CQ-xx、-T）照 D106-1 只留 FEAT 歸併連結，不列為過時。

## 4. 遠端分支（只列，不刪、不加標籤）

所有分支一律保留到 11-05 大整理，且刪除需使用者明確授權（AGENTS.md）；帶證據的分支保留。已有 `archive/` tag 的分支在「tag」欄標示。

| 對象 | 狀態 | 理由 | 出處 |
| --- | --- | --- | --- |
| `claude/office-demo-visualization` | DEPRECATED | 舊整合分支，凍結在 `f481fe0`；tag `archive/office-demo-visualization` | D63 |
| Office K 線（Claude）：`claude/k0-data-contracts`、`k1-hypothesis`、`k1-restricted`、`k3-interval-obs`、`k3-presets-ui`、`k4-hypothesis-bands`、`k5-pruning`、`k6-demo-mode`、`k7-map-verify`、`k8-synthetic-design`、`k8a-synthetic-method`、`k8b-synthetic-fixture`、`k8c-candidate-screen`、`office-demo-qa`、`rq1-ground-interval` | PENDING-CLEANUP-1105 | Office Demo 線已結束；`k8-synthetic-design`、`k8a-synthetic-method`、`k8b-synthetic-fixture`、`office-demo-qa` 已有 archive tag | D63、D91 |
| `claude/k7-r003-verification` | OUT-OF-DEMO-SCOPE | 開著的 #82 的 head，不能刪 | D106-2 |
| Office C 線（Codex）：`codex/c3b-review-followup`、`c4a-foot-ray-band`、`c4a-hybrid-contact`、`c4b-person-hypothesis`、`c5-d21-strict-visibility`、`c5-visibility-retrieval`、`c6-multicamera-feasibility`、`c7-source-map`、`k5-frame-wall-fixtures`、`k8a-c4b-presync`、`office-demo-rehearsal-docs`、`office-demo-review-followup`、`office-person-preset` | PENDING-CLEANUP-1105 | Office Demo 線已結束；`c3b-review-followup`、`c6-multicamera-feasibility`、`k5-frame-wall-fixtures`、`k8a-c4b-presync`、`office-demo-rehearsal-docs` 已有 archive tag | D63、D91 |
| controlled-scene／3D 線：`claude/controlled-scene-a`、`codex/controlled-scene-backend`、`codex/controlled-scene-d47-screening`、`codex/controlled-scene-real-v2-2a`、`archive/3d-line` | PENDING-CLEANUP-1105（`archive/3d-line` 保留） | 3D 線已暫停並封存（D63、D87）；`archive/3d-line` 是封存分支本身 | D63、D91 |
| Phase 1／2：`phase1/finalization-sprint`、`phase2/integration-hardening`、`codex/phase1-case23-formal`、`docs/workbench-root-cause-audit` | PENDING-CLEANUP-1105 | Phase 1／2 已結束 | D63、D91 |
| 舊 workbench 任務：`codex/q1q5-workbench-t1`～`t4`、`claude/workbench-v2-design`、`claude/workbench-v2-api` | PENDING-CLEANUP-1105 | T1–T4（#119–#122）已完成關閉，#90 已合併；是否已全進 mainline 待 11-05 以 merge-base 核對 | D75 |
| 舊重錄與 pin：`codex/q1q5-rc3-rerecord`、`codex/q1q5-scope-pins-rc4` | PENDING-CLEANUP-1105 | 已被 rc5（#127@`e1415f3`、#277）取代；仍可能是證據，先核對 | D105 B-20 |
| `claude/docs-archive-20261027` | PENDING-CLEANUP-1105 | D91 文件批次的分支，#264～#276 已合併 | D97-8 |
| `codex/q1q5-d91-archive`（#268 head）、`codex/l2-engineering-scene-plan`（#274 head）、`codex/cq22-r004-confirmation-overlays`（#349 head）、`codex/cq27-yyin-main-pack`（#361 head）、`codex/r004-scene-change-proposal` | 保留 | 開著的 PR head 或證據分支，隨各 PR 處理；`r004-scene-change-proposal` 是否被 staging 的 `R004_REVIEW_V2` 取代 UNKNOWN | D105 B-5、B-6、封存索引 §2 |

本表列的是名稱可辨識為舊線的分支；遠端共 212 個分支，其餘未逐一判定，11-05 依 `git branch -r --merged` 與開放 PR head 再盤點。
