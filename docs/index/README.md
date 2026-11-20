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
| [CODE_DOC_MAP.md](CODE_DOC_MAP.md) | 程式碼 ↔ 規格／文件對應表（主規格章節、LIVE 模組、其他套件），以及第一輪檢索項目的處理結果 |

## 修改紀錄

每次依檢索紀錄修改規格、文件或索引時追加一列。

| 日期 | 決策／issue | 修改內容 | PR |
| --- | --- | --- | --- |
| 2026-11-19 | D338／[#631](https://github.com/Polalalabear/amidst/issues/631) | 新增 `CODE_DOC_MAP.md`；SWEEP 補記 §2.3（LIVE 樣式）；`Q1Q5_PRODUCT_SPEC.md` 補 §4.4 LIVE、§6.1 決策選錄、鏡頭數、3D 現況，關閉 U-1、U-13；修正 `DEMO_RUNBOOK_20261104.md`、`UI_REDESIGN_V1.md`、`Q1Q5_PROGRESS.md`、`WORKBENCH_V2_Q1Q5_DESIGN.md`、`docs/engineering/LIVE_MODE_SPIKE_20261115.md`；封存文件 `CURRENT_WORK_REPRODUCTION.md`、`OFFICE_DEMO_TASKS.md`（放棄）、`OFFICE_DEMO_MVP.md`、`OFFICE_DEMO_SCRIPT.md`、`SYSTEM_DESIGN.md`、`ISSUES_AND_DECISIONS.md` 只加檔頭；審查修正：§4.3 改寫 #625 已合併（`1d322837`）、後續 #629，工作 1 指向 #633／#634 | [#632](https://github.com/Polalalabear/amidst/pull/632)（Draft） |
| 2026-11-20 | D340／D341／[#649](https://github.com/Polalalabear/amidst/issues/649) | 更正過度宣稱：`RECORDED_RULE_VS_LLM_D325_20261118.md` 開頭加「更正說明」（結論限定在 LLM 覆核、不看圖的架構；「34 個決策點都只有 0／1 候選」更正為 32 個，依 #637；看圖結果見 #647）；`Q1Q5_PRODUCT_SPEC.md` §4.3 的同一敘述加更正；原表格數字未改。正式研究報告（Claude Docs）同步改寫並加附錄三「更正說明」 | 本 PR（Draft） |

## 論文素材

論文與研究紀錄先以 [CODE_DOC_MAP.md](CODE_DOC_MAP.md) 為起點（模組 → 規格章節 → 評估文件）；各章節的素材對應待第二次以後的檢索補上。報告素材另見 [#479](https://github.com/Polalalabear/amidst/issues/479)。
