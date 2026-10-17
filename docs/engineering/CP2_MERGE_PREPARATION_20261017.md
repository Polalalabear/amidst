# CP2 合併準備：#44 窄同步與 Codex 堆疊對齊 — 2026-10-17

**第12步 #44 實際新head已是CLEAN（exit0），不再是假設對照。** #44窄同步完成，#46→#47→#50→#53以merge commits對齊並正常發布。#53新head整棵tree與0cb2c22相同，只改ancestry。整合分支`claude/office-demo-visualization`未改，CP2模擬仍只出報告；沒有把這些PR實際合入整合分支。

本文件由#54純文件分支提交；相較該分支先前272e69a，本次只新增本報告與JSON收據。契約#45 v1.2確認留待此任務之後；未同步K8a（等待#58合併），未執行CP3模擬、Agent重播、P1量測、C6或#55。

## 1. 已發布的五個head

| PR | 更新前 | 更新後 | 提交類型 |
| --- | --- | --- | --- |
| #44 | `0942f5a519a6f927ae22f442cbaea04703ab3a4a` | `86b9b243108240c29de89f41e6d798efcd840852` | 窄同步 commit |
| #46 | `a6ce40c2956a8f15b1ad77c9310bce1b203b7e7b` | `f10ea53aae2d11c4bb3363ac7369aa6bb005dfa5` | 兩個 parent 的 merge commit |
| #47 | `6bafe041cad88121d14fdec671adbcc9e117b593` | `0228ce270af2f0c98a63d1b6e822118045a33e2d` | 兩個 parent 的 merge commit |
| #50 | `cd6c854e05c87e6c3c45dac83c8c079121786c3a` | `a4d5dac93c42fee64c031c5eb2953f9960a9e5c3` | 兩個 parent 的 merge commit |
| #53 | `0cb2c2283451cd90946333f1a3c74b29f4c56682` | `4019a44f1dc22130e7b6013179ac86c899ca1200` | 兩個 parent 的 merge commit |

每個merge commit的第一parent是該分支更新前head，第二parent依序為前一層的新head。四次merge均由ort乾淨完成；沒有rebase、force-push或整合分支合併。五個refs經正常`git push --atomic`一起發布，避免部分堆疊發布。

## 2. #44 的精確窄同步

來源：#48 `74c6ace7885d7631ef3f5236d1b430ad3265b6d1`。允許範圍是七個模組路徑及ledger：

- `src/amidst/blind_hypothesis/__init__.py`
- `src/amidst/blind_hypothesis/convergence.py`
- `src/amidst/blind_hypothesis/engine.py`
- `src/amidst/blind_hypothesis/floor_map.py`
- `src/amidst/blind_hypothesis/pruning.py`
- `src/amidst/blind_hypothesis/restricted.py`
- `src/amidst/blind_hypothesis/retrieval_evidence.py`
- `docs/engineering/C4B_DEPENDENCIES_20261017.json`

七份模組逐位元相同。`convergence.py`原本已相同，因此實際commit為5份修改、1份新增restricted.py及ledger，共7個changed files；沒有改`src/amidst/workbench/`、scripts、configs、測試或任何原資產。ledger的K1/K5都釘74c6ace，包含restricted.py hash；C7與非K1/K5 pins保持原值。ledger bytes取自#53 @0cb2c22的已驗證74c6ace紀錄，**只取pins，不帶入#53的C5/service/integration功能**。

#44原有14份其他工程JSON/gzip逐位元保留；往上四層的tree delta也都僅限此窄範圍。舊凍結結果與原producer/dependency紀錄保留其歷史身分，不假裝由新pins重產；本次沒有重凍結任何檔案。

### 2.1 #44 focused verification

```sh
PYTHONPATH=src:scripts OFFICE_TEST_ASSETS=/Users/polalabear/Developer/amidst UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python -m pytest tests/unit/test_hybrid_contact.py tests/unit/test_hybrid_contact_report.py tests/workbench/test_blind_hypothesis_integration.py tests/workbench/test_office_demo_presets.py tests/workbench/test_office_launcher.py tests/workbench/test_target_reconstruction.py -o addopts='' -q
.local-worktrees/phase1-finalization/.venv/bin/ruff check src/amidst/blind_hypothesis
git diff --check
git diff --cached --check
```

**94 passed in67.36s，0failed/skipped。** Ruff及兩項diff checks PASS。測試在#44窄同步內容上執行，之後commit沒有再改內容。沒有跑全套、GT/RQ1評估或其他研究實驗。

### 2.2 #53 的hash相容性

```sh
git rev-parse 0cb2c2283451cd90946333f1a3c74b29f4c56682^{tree}
git rev-parse 4019a44f1dc22130e7b6013179ac86c899ca1200^{tree}
git diff --exit-code 0cb2c2283451cd90946333f1a3c74b29f4c56682 4019a44f1dc22130e7b6013179ac86c899ca1200
```

兩個tree都是`bc2ded36b0a9d83221b31521e14fdcb7ee497a22`，diff為空。#53全部程式、producer/config/dependency pins、測試與凍結檔都不變；新head只承接merge ancestry。保留的D19 freeze仍是NONE／BASELINE／feedback各281.125m²、4498格，聯集37m²／592格，0%收斂。

- [#53現存完整API freeze](https://github.com/Polalalabear/amidst/blob/4019a44f1dc22130e7b6013179ac86c899ca1200/docs/engineering/C5_PERSON_K1_SYNC_D19_20261017.json.gz) SHA-256：`d7dbc907d0c04a12928ee3a92f783ba56148e118684fafd603ee33091371f6e8`。
- 這是tree與既有artifact bytes相同的驗證；本次沒有重跑D19推論、#53的246項或其他中間分支的runtime測試，也不把歷史測試當作本次新跑。#53先前複審的內容不變；Claude彩排合成應改引用新head。

## 3. CP2 13步最新模擬

依[#52 @5c3f89b §9](https://github.com/Polalalabear/amidst/blob/5c3f89ba13fe6342319cfdf2f68ba018fa2db6af/docs/agents/COORDINATOR_HANDOFF_20261017.md#9-合併順序建議cp2cp3需使用者核准)。整合基準固定`dcb89f475f14897e1b272da61d44a25acf8f1fb8`，#48固定74c6ace，#45使用28479b4，這只是Git機械模擬，不是v1.2語意核准。

| 步驟 | PR | 實際head | 結果 / exit | 衝突檔 | 建議解法 |
| --- | --- | --- | --- | --- | --- |
| 1 | #51 | `5c72fe7597aef2d29d7f8fee0e9c2061a994e456` | CLEAN / 0 | NONE | 無需解衝突。 |
| 2 | #45 | `28479b41ab077946e9d4e191726834aad1be54ab` | CLEAN / 0 | NONE | 無需解衝突。 |
| 3 | #33 | `7c01522523d61c7c6453521b59478e6990ec241e` | CLEAN / 0 | NONE | 無需解衝突。 |
| 4 | #36 | `726e390d72acacc3138587e147dfb8b6f908cd5d` | CLEAN / 0 | NONE | 無需解衝突。 |
| 5 | #48 | `74c6ace7885d7631ef3f5236d1b430ad3265b6d1` | CLEAN / 0 | NONE | 無需解衝突。 |
| 6 | #31 | `74af12f533bf3aeb73464f7003e6c52a3853e68c` | CLEAN / 0 | NONE | 無需解衝突。 |
| 7 | #42 | `d0f82b17d5f69a92464fe741d75d653f3c5da22e` | CLEAN / 0 | NONE | 無需解衝突。 |
| 8 | #41 | `1ef9bc9574c356cdc54780ad57fc798d9566468f` | CLEAN / 0 | NONE | 無需解衝突。 |
| 9 | #40 | `4c5416662195771fc3a1015b6a8df1e47cafb886` | CONFLICT / 1 | `docs/README.md`<br>`docs/history/WORK_LOG.md` | README／WORK_LOG保留兩邊連結與日期化紀錄；只在暫存tree解標記。 |
| 10 | #37 | `099513ec5315308544c895f66600467a707aa475` | CONFLICT / 1 | `docs/README.md`<br>`docs/history/WORK_LOG.md` | README保留C7/C3b/policy/C4a/D17-D18入口；WORK_LOG保留各自歷史紀錄。 |
| 11 | #43 | `78367659f048cb4dbb095eb06bef3962cd34b793` | CONFLICT / 1 | `tests/workbench/test_office_demo_presets.py` | 測試保留#51完整性／degraded-readiness案例及#43 person/config案例，不整檔選邊。 |
| 12 | #44 | `86b9b243108240c29de89f41e6d798efcd840852` | CLEAN / 0 | NONE | 七份複本與74c6ace相同；實際head乾淨，沒有套用衝突解法。 |
| 13 | #46 | `f10ea53aae2d11c4bb3363ac7369aa6bb005dfa5` | CLEAN / 0 | NONE | 無需解衝突。 |

結果：**10步CLEAN、3步CONFLICT；#44第12步CLEAN且沒有解衝突介入。** #40/#37/#43仍需報告列出的原衝突解法；後續步驟的CLEAN以前面已採用這些解法為條件。#46第13步也乾淨。

### 3.1 模擬邊界與檢查

- 每步用`git merge-tree --write-tree --messages <先前虛擬commit> <PR-head>`；為保留後續merge-base的正確ancestry，在LOCAL暫存object store以`git commit-tree <tree> -p <ours> -p <theirs>`建立模擬commit。
- `GIT_OBJECT_DIRECTORY`與`GIT_INDEX_FILE`都指向LOCAL `/private/tmp`。沒有在實際工作樹套用衝突解法、沒有修改任何branch ref或實際index。CP2模擬前後branch refs、HEAD與工作樹狀態一致。
- 最新13個head已與GitHub逐一核對相同，整合分支仍是dcb89f4。
- 最終模擬tree的七份K1/K5仍與74c6ace相同，ledger所有file hashes符合；41份受影響Python檔AST語法檢查通過。**這不是合成後程式測試或runtime驗收。**
- LOCAL暫存root：`/private/tmp/amidst-cp2-postsync-audit-jnlakuwi`；逐步stdout、stage-blob IDs、tree IDs、解法與虛擬parent鏈都保留。模擬commit未掛到repo refs，不可當已發布commit引用；/tmp可能被清除，收據保留各精確head及原始衝突訊息。

### 3.2 與上一份報告的差異

上一份報告以#44 @0942f5a模擬，5個K1/K5 add/add衝突；只有「替換七份74c6ace複本＋pins」的假設對照乾淨。這次使用者採用該建議後，#44已發布86b9b24，實際第12步直接乾淨。先前head、衝突清單及報告/收據hash留在新收據的historical_pre_sync_audit，不改寫為當時已乾淨。

## 4. 機器收據與既有RQ1交付

- [本次收據](CP2_MERGE_PREPARATION_20261017.json)，SHA-256：`0f595cfbdf17a7554794672e588a4c04c755056eec6770cd7713bf8b9d55c9f6`。
- RQ1既有[C4a v1.1預測](C4A_PERSON_FOOT_BAND_PREDICTIONS_20261017.json)保留33筆ground_estimate，SHA-256 `c1dfc1bd3baacca514f2066adcfc10036cbcfaf657e5636d8482b837d6dd4616`；本次未重產或讀GT。
- LOCAL driver `/private/tmp/cp2_merge_audit.py` 與各解法檔位置／hash見收據；重新模擬需使用新的暫存state並固定同組heads、日期化文件union及#43測試union。

## 實際產出 / Actual output

- Model / effort: UNKNOWN（session沒有可權威確認的精確model/effort值）。
- PR / commits: #44窄同步與#46/#47/#50/#53四個merge commits見第1節；本報告與JSON在#54純文件分支提交，精確文件commit SHA在PR結果紀錄。未合入integration/main。
- Files changed: #44為5個模組修改＋新增restricted.py＋ledger，共7檔；convergence逐位元核對但未改。#46/#47/#50只承接同7檔，#53 tree零變動。#54本次只新增本報告及JSON。
- Commands run and results: #44原六檔focused94passed/67.36s；Ruff/diff PASS；四次merge乾淨、兩parent順序正確、五refs正常atomic push；CP2 13步如表，第12步實際CLEAN；41Python AST PASS、所有pins PASS；新報告連結/JSON/whitespace檢查PASS。
- Artifacts: 沒有新prediction/media；舊凍結原件保留。本次CP2 JSON SHA見上，其他模擬objects與raw stdout標LOCAL。
- Verified: 七份exact74c6ace bytes、窄scope、新pins、#44focused、堆疊merge ancestry、#53tree/frozen bytes不變、13個實際heads與第12步CLEAN、integration ref未改。
- Not verified: #46/#47/#50各自新head的runtime、合成後測試/full suite/browser、GT/RQ1/RQ2、v1.2語意及K8a。未重新執行#53/D19推論。
- Deviations, UNKNOWN items and follow-ups: NONE scope deviations。Claude複審#44新head，彩排合成改用#53新head；#40/#37/#43仍有既列衝突。checkpoint核准前不合integration；K8a同步仍等#58合併。
