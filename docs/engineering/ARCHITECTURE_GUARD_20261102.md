# 架構守門（FEAT-7／#307）

規格依 [#306](https://github.com/Polalalabear/amidst/issues/306)、[#307](https://github.com/Polalalabear/amidst/issues/307)、[#374 歸併](https://github.com/Polalalabear/amidst/issues/374#issuecomment-6556605581)。守門只讀程式、文件、設定與 Git metadata，不執行推論，不開啟原始資產或任何人工回件。

```bash
uv run python -m pytest -q tests/unit/test_architecture_guard.py
uv run python scripts/check_architecture_guard.py --base origin/codex/q1q5-staging --report /tmp/arch_guard.json
git diff --check "$(git merge-base origin/codex/q1q5-staging HEAD)" HEAD
```

使用既有 Python 環境；腳本本身只需標準庫。三項皆通過時 exit 0，否則 exit 1。stdout 與 `--report` 是同一份 JSON，含 base、merge_base、head 及各項 findings。錯誤的 base／Git root／policy 會 fail closed，不能算 PASS。

## 權威檔

`configs/architecture/authority_pins_v1.json` 的每列都來自 #306 原文或 D100(a)／D100(b)／D112-2(c)；主表的已交件／PROPOSED 快照只是可識別 bytes，匹配不表示採納、核准或合併。

- 比較 merge-base 到 HEAD 的 committed 路徑，改到任一受保護路徑回 `AUTHORITY_CHANGED`。新增、刪除、rename 皆按路徑處理。
- 工作目錄內存在的權威檔另驗 SHA-256，未知 bytes 回 `AUTHORITY_DRIFT`；HEAD 有檔但工作目錄缺失回 `AUTHORITY_MISSING`。主表記載但本 checkout 尚未包含的檔列為 registered_but_absent，不宣稱已驗它們。
- `--allow <repo-relative-path>` 只免除該路徑的 changed-path 阻擋，仍驗已登記的 bytes pin。是否有任務授權由審查確認；旗標不是授權。未知 pin 不因 `--allow` 升權。
- D100(a) 明列的兩個 staging 規則歷史 pins 保留；#382 合併前不替換成新規則檔 bytes。
- D100(b)／D105 B-22 的 #305 例外綁 `f22e9dafe495a560eea145a8f5cefcfc871dce0f` 必須已在 HEAD 歷史內；此前只認原 v1 scorer pin，此後只認指定的新 scorer／test pins。不能只複製新 bytes 冒充指定增量，也不雙值永久放寬 v1 scorer。
- #306 A1 是 Git symlink blob，故驗 link text bytes，不跟隨它讀取 target。target 內容並未因此被 A1 pin 保護；路徑中間的 symlink 不可用來逃出 repo。依 D112-2 補正 D108-2，#382 合入後協調者需更新 A13'（`docs/operations/Q1Q5_PROGRESS.md`）與 A1 symlink target 的 pin，不只 A2／A3；同時同步 #267 分支的 `authority_pins_v1.json`。本分支不預先核定未合入的新 bytes。

**A14 歷史 pin（D112-2(c)，使用者選 A）。** #306 已列出 staging@`434e57922a24d2422226871c0bb672dc7bc3584b` 的兩個舊 kit hash。只有該路徑相對固定 staging 的 HEAD bytes 未改，且 #127 rc5 `e1415f32a778f497bdd048d992440718bf0a9310` 未進入受檢 HEAD 歷史時，才接受舊 pin。HEAD 已改檔時即使工作目錄還原舊 bytes 也不能恢復例外；rc5 一進歷史，舊 pin 永久退役，未知或不可用的條件 commit 一律 fail closed。`--allow` 不繞過這些條件。若 FEAT-6 B-20 改了 rc5 bytes，由 FEAT-6 更新 policy，協調者在 #306 重釘 A14。

## 推論隔離

`configs/architecture/inference_import_rules_v1.json` 只掃 `src/amidst/q1q5/**/*.py` 與 `frontend/workbench-v2/**/*.mjs`。Python 用 AST 檢查直接／relative imports、字面值 dynamic imports 與字串常數；前端逐行掃描規定 token。新命中回 FORBIDDEN_IMPORT／FORBIDDEN_STRING，Python 語法錯誤與 source symlink 各自 fail closed。

既有命中快照固定來自 staging@`434e57922a24d2422226871c0bb672dc7bc3584b`。每筆綁相對路徑、kind、`sha256(kind + NUL + value)`、最大既有出現次數與理由；Python value 是 module／完整字串常數，前端 value 是 stripped 整行。新增同樣字串的第二個 occurrence 會超出原計數而失敗；換行號不自動變成新例外。快照不核准既有行為，也不代表已審查其有效性。

這是指定範圍的靜態機械檢查，不宣稱能證明任意動態程式的資訊流安全。既有 baseline 命中不等於本次新增使用的許可，不能自動重新產 baseline 洗掉命中。#306 的模組邊界條文授權 #307 維護清單與允許例外；本次逐項讀取固定 feature head 的 22 個新增命中，將純拒絕清單、`gt_read=false` 斷言／常數、明確否定資料來源的 docstring、CSS `visibility`、SYNTHETIC 負例測試登記在獨立 `exceptions`，未改固定 staging baseline。每筆都有精確 path／kind／hash／count、#307 及原 PR／head 與理由，仍用相同次數上限，新增讀取 GT 或 renderer evidence 的行為不在例外內。

## Schema literal 登記

`configs/architecture/schema_registry_v1.json` 是固定 staging 來源的 literal inventory：在 `src/`、`configs/`、`frontend/`、`docs/contracts/` 掃描 `schema_version`／`SCHEMA_VERSION` 的字面字串值。每個值有 source_paths、issue_ref；新增值沒有登記回 SCHEMA_UNREGISTERED，登記缺 issue_ref／source_paths 回 REGISTRY_ENTRY_INVALID。

登記不採納 PROPOSED schema，不核定資料欄位、決策語意或發布用途；`registration_is_approval=false` 固定寫入報告。它不執行 runtime schema 驗證，也不推導透過運算產生的動態版本字串。新增登記必須連到提出／採納該值的任務或決策，不能將掃描器當作新的 authority。

守門補跑另登記 7 個已交 feature 的 literal，附原 PR／head 與 source_paths；其中 `q-demo.q1-response.v3` 只出現在負例測試，明標 `NEGATIVE_TEST_LITERAL_ONLY_NOT_ADOPTION`。接受 literal inventory 不表示產品接受 v3，也不改 #278／#305 的配對規則。

## 對固定 baseline 的獨立重跑

在自己新建的拋棄式 clone checkout 固定 staging，使用此 feature 的腳本與 config 讀取它；不修改共用 checkout，也不把守門檔混入來源 baseline：

```bash
# GUARD_ROOT 指向此 feature 的 checkout；BASELINE_ROOT 是自己建立的拋棄式 clone。
git -C "$BASELINE_ROOT" switch --detach 434e57922a24d2422226871c0bb672dc7bc3584b
uv run python "$GUARD_ROOT/scripts/check_architecture_guard.py" --repo "$BASELINE_ROOT" --base 434e57922a24d2422226871c0bb672dc7bc3584b --config-dir "$GUARD_ROOT/configs/architecture" --report /tmp/arch_guard_staging.json
```

執行前後比對權威 refs；更新只能依 #306 協調者的明確紀錄。每個 feature 的結果記在該 PR Actual output，不再逐子 PR 重複留言（D104／D105）。被前置修正影響時以 merge 接上並重跑自己的守門與驗收。


## D114-4 P1 重釘與固定 heads 補跑（2026-11-03）

依 #93 D114-4／#306，P1 設計稿改綁 #258@`0b6e800`，SHA-256 `0a4e579b0664ab663e44809ebc0d2670b434c17161d7c24f237b1be4d051cc4c`；以 git show 重算相符。只改 policy 的 ref／sha，PROPOSED 不變，不改設計文件、authority 或決策語意。36 strict focused tests PASS；本 feature 的三項守門 PASS，0 findings。

使用本增量固定腳本／authority policy 讀取各 PR 精確 head，基底固定 staging@434e579。#394／#396 的 scoped rerun 保留各自已提交的 schema registry bytes；初次統一 registry 掃描的缺登記結果亦保留在 JSON。#396 allow 僅沿其既有 PR 命令；不因 allow 繞過 pin。

| PR（#0＝固定 staging） | head | 結果 | exit | report SHA-256 |
| --- | --- | --- | --- | --- |
| #0 | `434e57922a24d2422226871c0bb672dc7bc3584b` | PASS | 0 | `9dc030f7f77b65f80e33148d974126824d3ab62d98d3f1585e980d086cd2d5cf` |
| #389 | `aaf660d76cc2e15315931fc73fac11945b4fe79c` | PASS | 0 | `30542f681a15ceba701c2e06c2d00a560e23430371f6d35daf66c0fadfe78459` |
| #390 | `46e4673f6d7bbc41d43e623882afe438db16893a` | PASS | 0 | `6282a03e0fd5fef8592aa986fe1d7b5b2d12249a2c8b92faa2ba85bf5dd0e28d` |
| #392 | `1ffabe603c5197515c9825f7e40e9ba5a08b1b35` | PASS | 0 | `796d5c62d6bc139a08221f32392b5b4df94a7d11e41bd65258f54cb1681fba59` |
| #393 | `943a72f8a2c5ade5472d5ead00cc5a2f2bb4fdf4` | PASS | 0 | `c7ca277b15789f25e528298469de2390f2237ceafecb97162279d647bd50dcbe` |
| #394 | `28139fbeb652c0d0536a34409a6fd843275fa8c7` | PASS | 0 | `d6559ba084c40fa0991f12498d67aceffb1e6223ce3642537b874e4a345695cc` |
| #395 | `47da051700683dfdc8607cafe41ba1a64d64025e` | PASS | 0 | `74ea9358990a5fc87306dd3b91a4e8b749143a250a4e56c7b7812e09c15ff385` |
| #396 | `1ff272ffea2fa595a153106829ebf2cef3e29c8c` | FAIL | 1 | `a241fd403b002cc8c2bcb94ae0d43fce946ed77a665fade2e8d0abbf92320469` |

完整命令參數（repo/base/config-dir/allow）、policy hashes、初次與最後 findings 收在 `ARCHITECTURE_GUARD_D114_REPORTS_20261103.json`；報告為靜態檢查，不執行推論／渲染／回件。#396 仍因 kit 文件 `91d4f2c4…fad8` 非 A14 rc5 bytes 而 FAIL；P1 新 pin 已不再命中 drift。依 D114-3，FEAT-4 demo 後接 FEAT-6 rc5 再交，不修改本次 policy 使其通過。
