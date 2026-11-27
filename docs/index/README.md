# docs/index — 程式碼↔文件對應索引

本資料夾存放 Amidst Q1–Q5 專案的**程式碼 ↔ 規格／文件 ↔ 索引**對應紀錄，以及每次檢索的紀錄，供之後：

1. 更新主規格（`docs/specs/Q1Q5_PRODUCT_SPEC.md`）與對應文件；
2. 整理研究紀錄；
3. 撰寫完整版論文時，快速找到模組、文件章節與素材來源。

## 規則

- **只記區段**（模組、檔案、文件章節名稱），不記行號；每項只寫「哪裡需要動、為什麼」，不寫修法細節。
- **檢索紀錄只記錄，不修改**。依紀錄修改規格與文件時另開 issue／PR（例如 D338），並在下方「修改紀錄」追加一筆；檢索紀錄本身只追加補記，不改寫原文。標為「可刪候選」或「可模組化」的項目，刪除或合併都需要使用者授權後另開工作。
- 每次檢索追加一份新的 `SWEEP_<D號>_<階段>_<日期>.md`，不覆寫舊紀錄。
- 文件內不放絕對家目錄路徑。

## 類別標籤

| 標籤 | 意思 |
| --- | --- |
| 文件過時 | 文件描述與現況不符，或引用已退役的路徑 |
| 無文件 | 程式模組沒有對應的規格或工程文件 |
| 冗餘 | 同一邏輯在多處各自實作，或同名不同實作 |
| 可模組化 | 可抽成共用模組，但目前不急 |
| 可刪候選 | 無引用或只有一次性用途；只標記，不刪 |
| spec 缺漏 | 主規格缺少現行功能或與現況矛盾 |

## 檢索紀錄

| 檔案 | 日期 | 範圍 | 狀態 |
| --- | --- | --- | --- |
| [SWEEP_D319_PASS1_20261119.md](SWEEP_D319_PASS1_20261119.md) | 2026-11-19 | D319 冗餘清理第一次檢索：src/、frontend/、scripts/、tests/、docs 各主要資料夾 | 已完成並經 Sonnet 全面核對修正（issue #626）；2026-11-19 補記 §2.3（D338） |

## 對應表

| 檔案 | 內容 |
| --- | --- |
| [CODE_DOC_MAP_DELTA_20261124.md](CODE_DOC_MAP_DELTA_20261124.md) | `ea31b643`..`d52ce2f0` 的逐檔差異（91 檔，UNKNOWN 20）；模組級對應已併入下一列 |
| [CODE_DOC_MAP.md](CODE_DOC_MAP.md) | 程式碼 ↔ 規格／文件對應表（主規格章節、LIVE 模組、其他套件），以及第一輪檢索項目的處理結果 |

## 修改紀錄

每次依檢索紀錄修改規格、文件或索引時追加一列。

| 日期 | 決策／issue | 修改內容 | PR |
| --- | --- | --- | --- |
| 2026-11-19 | D338／[#631](https://github.com/Polalalabear/amidst/issues/631) | 新增 `CODE_DOC_MAP.md`；SWEEP 補記 §2.3（LIVE 樣式）；`Q1Q5_PRODUCT_SPEC.md` 補 §4.4 LIVE、§6.1 決策選錄、鏡頭數、3D 現況，關閉 U-1、U-13；修正 `DEMO_RUNBOOK_20261104.md`、`UI_REDESIGN_V1.md`、`Q1Q5_PROGRESS.md`、`WORKBENCH_V2_Q1Q5_DESIGN.md`、`docs/engineering/LIVE_MODE_SPIKE_20261115.md`；封存文件 `CURRENT_WORK_REPRODUCTION.md`、`OFFICE_DEMO_TASKS.md`（放棄）、`OFFICE_DEMO_MVP.md`、`OFFICE_DEMO_SCRIPT.md`、`SYSTEM_DESIGN.md`、`ISSUES_AND_DECISIONS.md` 只加檔頭；審查修正：§4.3 改寫 #625 已合併（`1d322837`）、後續 #629，工作 1 指向 #633／#634 | [#632](https://github.com/Polalalabear/amidst/pull/632)（Draft） |
| 2026-11-20 | D340／D341／[#649](https://github.com/Polalalabear/amidst/issues/649) | 更正過度宣稱：`RECORDED_RULE_VS_LLM_D325_20261118.md` 開頭加「更正說明」（結論限定在 LLM 覆核、不看圖的架構；「34 個決策點都只有 0／1 候選」更正為 32 個（以決策點計數，請求列 35 筆），依 #637（merge `3cdbbfc9`）；看圖結果見 #647）；`Q1Q5_PRODUCT_SPEC.md` §4.3 的同一敘述加更正；原表格數字未改。正式研究報告（Claude Docs）同步改寫並加附錄三「更正說明」 | 本 PR（Draft） |
| 2026-11-20 | W2／[#645](https://github.com/Polalalabear/amidst/issues/645) | `CODE_DOC_MAP.md` 加 §4.3 主動 Agent 決策器；`Q1Q5_PRODUCT_SPEC.md` §4.3 加 Agent 請求結構；新增 `W2_ACTIVE_AGENT_20261120.md`；`AGENT_VS_RULE_HYPOTHESES_20261120.md` §4.1 加現況對照 | W2 PR（Draft，見 #645） |
| 2026-11-20 | D342 | #648 合併後的全面文件同步：`CODE_DOC_MAP.md` §1 加 `camera_projection.py`、付費護欄與 G7、假設評估（W1、先導、W2）三列；規格 §2 資料流加 Agent 模式、§4.3 補 `ApiGuard` 路徑、G7、H1–H6 目前證據，§8 U-9 關閉、新增 U-18；假設文件新增 §0 目前證據狀態；W1 文件主結果改為多數決並補 `rule_nocolor` 說明（#647 Opus 後續 2、3）；README、AGENTS.md 來源文件清單；`Q1Q5_PROGRESS.md` 補到 #650；authority pin 補登 `docs/specs/DEVELOPMENT_RULES.md` | 本 PR |
| 2026-11-22 | D344／F1 [#660](https://github.com/Polalalabear/amidst/issues/660) | 新增 `E3_PREREGISTRATION_20261122.md`、`E3_SCORER_RECOMPUTE_20261122.md`；`CODE_DOC_MAP.md` 加 E3 統一評分器一列。W2 文件與假設文件 §0 的「IoU 準則 0.761、錯人 6.3 s」依重算結果待後續修正（本 PR 不改） | 本 PR |
| 2026-11-24 | D377／[#722](https://github.com/Polalalabear/amidst/pull/722) | 新增 `E6_PLAN_20261124.md`；`CODE_DOC_MAP.md` 加 E3、F2、F3、E5、E6、ApiGuard 快取與 LIVE 對應；`AGENT_VS_RULE_HYPOTHESES_20261120.md` §0 加 E5 結果與 E6 指向；`docs/README.md`、AGENTS.md、CLAUDE.md 改指 20261124b 交接；`Q1Q5_PROGRESS.md` 補到 #722。根目錄 `README.md` 由 #719 更新，本次不動 | [#722](https://github.com/Polalalabear/amidst/pull/722) |
| 2026-11-27 | D407 | `CODE_DOC_MAP.md` §1 的 E6 列拆成 E6 預登／R-N、路線與錄製、Agent 組、一次跑完四列，新增 E7、AO-L 延遲歸零與統一分析、報告資料夾、重現包四列，俯視圖 3D 補 #714；CLAUDE.md、AGENTS.md、`docs/README.md` 改指 `COORDINATOR_HANDOFF_20261127b.md`；`Q1Q5_PROGRESS.md` 補到 #755 | 本 PR（分支 `claude/docs-update-20261127`） |

## 論文素材

論文與研究紀錄先以 [CODE_DOC_MAP.md](CODE_DOC_MAP.md) 為起點（模組 → 規格章節 → 評估文件）；各章節的素材對應待第二次以後的檢索補上。報告素材另見 [#479](https://github.com/Polalalabear/amidst/issues/479)。
