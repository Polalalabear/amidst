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

這是指定範圍的靜態機械檢查，不宣稱能證明任意動態程式的資訊流安全。既有 baseline 命中不等於本次新增使用的許可；新增例外要列精確來源與理由，由擁有者依 #306／#93 取得對應定案，不能自動重新產 baseline 洗掉命中。

## Schema literal 登記

`configs/architecture/schema_registry_v1.json` 是固定 staging 來源的 literal inventory：在 `src/`、`configs/`、`frontend/`、`docs/contracts/` 掃描 `schema_version`／`SCHEMA_VERSION` 的字面字串值。每個值有 source_paths、issue_ref；新增值沒有登記回 SCHEMA_UNREGISTERED，登記缺 issue_ref／source_paths 回 REGISTRY_ENTRY_INVALID。

登記不採納 PROPOSED schema，不核定資料欄位、決策語意或發布用途；`registration_is_approval=false` 固定寫入報告。它不執行 runtime schema 驗證，也不推導透過運算產生的動態版本字串。新增登記必須連到提出／採納該值的任務或決策，不能將掃描器當作新的 authority。

## 對固定 baseline 的獨立重跑

在自己新建的拋棄式 clone checkout 固定 staging，使用此 feature 的腳本與 config 讀取它；不修改共用 checkout，也不把守門檔混入來源 baseline：

```bash
# GUARD_ROOT 指向此 feature 的 checkout；BASELINE_ROOT 是自己建立的拋棄式 clone。
git -C "$BASELINE_ROOT" switch --detach 434e57922a24d2422226871c0bb672dc7bc3584b
uv run python "$GUARD_ROOT/scripts/check_architecture_guard.py" --repo "$BASELINE_ROOT" --base 434e57922a24d2422226871c0bb672dc7bc3584b --config-dir "$GUARD_ROOT/configs/architecture" --report /tmp/arch_guard_staging.json
```

執行前後比對權威 refs；更新只能依 #306 協調者的明確紀錄。每個 feature 的結果記在該 PR Actual output，不再逐子 PR 重複留言（D104／D105）。被前置修正影響時以 merge 接上並重跑自己的守門與驗收。
