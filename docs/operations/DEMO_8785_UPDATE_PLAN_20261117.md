# 8785 下一次更新準備（#555，2026-11-17）

**修改C後狀態：聯合驗收NOT_PASSED，#559保持Draft，不可用本文件的歷史gate核准新部署。新組成／失敗條件見 `docs/evaluation/LIVE_DETECTION_SCHEDULE_JOINT_20261117.md`。**

**執行位置：所有啟動器／uv命令請在自己的 clone 執行；uv cache 預設寫入該 clone 的 `.local/demo-cache/uv`，不要在pin住的checkout啟動。**

這是更新準備，不是pin核准或部署。讀到的現行pin是`b24d6a26dc3f556f34270055cab45f5c5dd6382b`（D235）；8785資料夾不改檔、不切分支、不commit、不重啟。合併與pin更新都由使用者執行。D234的舊閘門早已過期，不能沿用。

## 版本與本次內容

獨立scratchpad clone，分支`codex/feat-live-detection`，Draft PR #559，同時承載#552和#555。起點`main@31a69177`；從現行pin到起點的範圍為`b24d6a26..31a69177`，包含#543/#545的後續launcher、#544即時模式及之後main整合；逐commit清單列於本次LOCAL收據，不能只挑已看過的修改宣稱涵蓋整段。

本PR再帶入#552的letterbox／分鏡頭門檻和本次launcher：Windows可選8CAM、Mac啟動時間註解，以及`start_live_mode.command`／`.ps1`。Mac總入口亦可`./start_all_demo.command --live-mode`。即時模式獨立8791（可改`--port`），advisor固定off，拒用8785；缺safe_static攝影機目錄會在模型載入前明確報`CAMERA_CATALOG_MISSING`。一般A/B/C一鍵流程不自動啟動即時模式。

## 更新檢查清單

- [x] 讀AGENTS、D248、#555與D234/D235；確認owner:codex/ready並認領。
- [x] 獨立clone，沒有worktree；不改pin住的checkout或原始素材。
- [x] `start_all_demo.ps1`增加CX8Root參數／CX8_ROOT環境變數／預設目錄，存在才帶`--root-8cam`，對齊Mac行為。
- [x] Mac等待註解改為含8CAM實測60–75秒、timeout180秒，表明負載影響。
- [x] 即時入口預設advisor off、獨立埠、缺catalog清楚報錯。
- [x] 本clone更新閘門：unit、dependency --smoke、HTTP、core-e2e、real-e2e 900/1300；結果與hash見下方。
- [ ] Claude審查、GitHub checks綠燈；使用者合併後確認最終候選SHA／tree。
- [ ] 使用者核准pin並更新8785；此任務不執行。

## 在自己的checkout重跑更新閘門

沿D234/D235的同一閘門，資料包唯讀共享，不複製raw。owned runtime要求自己的`.venv`與repo-local Playwright，因此用既有owned Python／離線uv與npm快取安裝鎖定依賴。QA state、測試暫存與輸出在本clone的`local/evidence/cx555-20261117/`。

既有dependency/server會在owned包的`state/`建立新目錄。為遵守本任務不寫`~/amidst`，`scripts/qa_demo_update.py`只把這個tempfile目的地改到本clone，並用audit拒絕寫入owned包。原始asset pins、validator、IO guard及生產設定不改；原有state父目錄必須已存在。這是QA呼叫方式差異，不把它說成已測過真實8785啟動。

```bash
# SHARED_LOCAL唯讀；CHECKOUT為本clone；PYTHON為其.venv/bin/python。
AMIDST_DEMO_HOME="$SHARED_LOCAL/data/demo-owned-v1" PYTHONPATH=src uv run --offline --no-project --python "$PYTHON" python -B scripts/qa_demo_update.py --state-parent local/evidence/cx555-20261117/state dependency --smoke --output local/evidence/cx555-20261117/dependency-check.json
AMIDST_DEMO_HOME="$SHARED_LOCAL/data/demo-owned-v1" PYTHONPATH=src uv run --offline --no-project --python "$PYTHON" python -B scripts/qa_demo_update.py --state-parent local/evidence/cx555-20261117/state serve --port 8795
```

server只在8795，既有8785與其他agent的8791不碰。core-e2e需clean HEAD：`CORE_SOURCE="$CHECKOUT" CORE_INTEGRATION_HEAD=<被測HEAD> SCREENSHOT_DIR=<LOCAL/core> node tests/browser/core-preview/core-e2e.mjs`；real使用`UI_QA_BASE_URL=http://127.0.0.1:8795 UI_QA_OUTPUT=<LOCAL/real-height> UI_QA_HEIGHT=900|1300 node tests/browser/ui-redesign/real-e2e.mjs`。

完整unit沿現行CI的node workbench-v2/event-viewer和pytest q1q5/evaluation/operations/paths及其deselect清單；這次因#555明確要求更新閘門才執行，不把它變成一般task的full-suite要求。pytest的`--basetemp`必須在checkout外的`AMIDST_ARTIFACTS`，因recording/freeze合成fixture要求outside-repo輸出；不放在clone內。unit不設`AMIDST_DEMO_HOME`／`AMIDST_ROOT`，與CI相同；真實來源另由dependency及兩組real E2E驗證。

## 即時模式入口使用

`PYTHONPATH`需含既有RT-DETR runtime依賴（見`LIVE_MODE_HANDOFF_20261116.md`）；LOCAL根可用`AMIDST_ROOT`、`AMIDST_LIVE_ASSETS`、`AMIDST_LIVE_MODELS`、`AMIDST_LIVE_CAMERAS`或CLI覆寫。預設8791若已被其他工作占用，改8797，不終止不明程序。`--check-only`只做前置檢查，不宣稱模型forward或Windows原生啟動通過。啟動後印operator/system連結，畫面沿既有即時UI，沒有新增UI設計採用。

```bash
./start_live_mode.command --port 8797 --check-only
./start_all_demo.command --live-mode --port 8797
# Windows獨立入口：.\start_live_mode.ps1 --port 8797 --check-only
```

## 使用者更新時的順序（未執行）

1. Claude審查與checks完成，使用者合併#559；決定要pin的main commit，記錄其完整SHA/tree及這次實測版本差異。未合併功能不混進8785。
2. 檢查8785 checkout乾淨、main、目前pin=b24d6a26，備份pin；若候選的執行內容不同於本次測試或閘門超過24小時，先在獨立clone重跑，不能沿用舊PASS。
3. 使用者確認停機時間後再依`demo_pin.py`既有流程approve/check、更新與重啟；本任務沒有替使用者核准。
4. HTTP200、四個既有run與實際畫面都確認；即時模式另開獨立埠且advisor off。8785新UI的8CAM列表仍非本任務功能。
5. 出現問題停止更新，保留log與原pin；不提供或執行reset/force-push/刪來源的捷徑。

## 未驗證／後續

Windows原生PowerShell執行依本機工具可用性如實記錄，不以Mac語法檢查替代。沒有付費API、API key讀取、Blender render、GT進推論、pin approve或8785重啟。畫面若需新增設計，先給使用者看再採用；本次僅啟動入口。

## 本次實際閘門

被測程式HEAD **f6d7e8ff5fabab317026e9c33aa26facc2ed7194**，tree **ef2fe1a343e262dd94d9abaaa0faf895e39cb2a8**。core與兩組real E2E均在這個乾淨HEAD上跑；後續提交補收據／文件／收據產生工具及CI測試fixture隔離，demo執行程式不變，不宣稱後續整棵tree和被測tree完全相同。合併後仍由使用者確認最終候選，不自動換pin。

| Gate | 實際結果 | LOCAL（相對`$AMIDST_ARTIFACTS/cx555-20261117/`） | SHA-256 |
| --- | --- | --- | --- |
| unit node | 576 passed，0 failed/skipped | unit-node.log | c5a860738bc5e52c76b10b4d94ffeefae9eff4fec3ad23b6297818e1e596dc06 |
| unit pytest | 2703 passed，108 skipped，17 deselected | unit-pytest-rerun.log | 83a07a987041410dd8cc36c6fb1869146fe50f1688880909e28922f901a92dee |
| dependency --smoke | PASS，4788 entries／2756614124 bytes，4來源RGB hash通過 | dependency-check.json | 369fcbd03e86bb4cce0a466dd1a5d675ba5cd83c03fb68935849b7a917264d13 |
| HTTP | 8795回200 | http-status.txt | 見MANIFEST |
| core-e2e | 130 checks，page_errors空 | core-e2e.log | 2044e62e8fd1feb240a4ea76ae6a6174cad78c0c34cdd5457d02ea104cfce3e7 |
| real-e2e 900 | 347 checks，61圖，errors/http空 | real-e2e-900.log | 073413e1e26f880de0c180ccd40f9313945ba18ce9ad54fa5b98481d51f87499 |
| real-e2e 1300 | 347 checks，61圖，errors/http空 | real-e2e-1300.log | 709686b2ac110660cf37fdcb81bb8443239771ba5dafa867d1ec625cd9da05ff |
| live launcher | 真實8797啟動；config顯示N6、letterbox、0.15／ENTRY0.05、advisor off；check-only通過 | live-config.json／live-launch.log | 見MANIFEST |

`RESULT.txt` SHA-256 **243ba13b10f4dcab3d58d234ba355a6dd96f6b9df2044bde423823197f53100c**，24小時有效至 **2026-11-18 11:45:27 Asia/Taipei**。這只是閘門時效，不是使用者pin核准。8795／8797測試服務都已停止；8785、pin與共享checkout沒改。

已提交精簡收據：`docs/operations/demo_update_20261117/receipt.json`。原始log／截圖／API回應與state留LOCAL，manifest為`$AMIDST_ARTIFACTS/cx555-20261117/MANIFEST.json`，SHA-256 **446f48adf34e9db1cdf5db3eaec1947d66ac4bad3b9028f73c7c5bb7717aad2f**，列171檔、41,206,301 bytes。它不包含可丟棄的pytest合成fixture／uv cache。可用本文件命令與同一owned包重跑，截圖及時間不能保證相同bytes；`scripts/demo_update_receipt.mjs`重建收據與manifest。

第一次unit因把basetemp放在repo內而中止：68 failed、607 passed、52 skipped、17 deselected；其log也保留並計hash。修正暫存位置後同範圍重跑2703全過，沒有更改測試或deselect清單。兩個PowerShell原生測試因本機未安裝PowerShell而skip；不把Mac檢查冒稱Windows驗證。

## 實際產出 / Actual output
- Model / effort: GPT-6 / UNKNOWN（此工作階段未提供可驗證的 effort metadata，不能猜填）
- PR / commits: Draft #559，base main，分支codex/feat-live-detection；#555程式f2a02d93、f6d7e8ff；診斷／#552 b74bc723、70e92239；本次收據commit見PR
- Files changed: start_all_demo.command、start_all_demo.ps1、start_live_mode.command、start_live_mode.ps1、scripts/start_live_mode.py、scripts/qa_demo_update.py、scripts/demo_update_receipt.mjs、tests/operations/test_live_launcher.py、兩版更新計畫及demo_update_20261117/receipt.json
- Commands run and results: 同上閘門；`bash -n start_all_demo.command start_live_mode.command`與`git diff --check`通過；相關cross-platform／launcher測試及最後unit通過，精確參數見本文件
- Artifacts: 上述LOCAL manifest／RESULT SHA；171檔41,206,301 bytes；精簡收據已commit，不靠LOCAL-only交接
- Verified: 自己clone的更新閘門、原owned包唯讀、四個run、兩種高度、live advisor off／獨立埠／缺catalog與型別拒絕、PowerShell 8CAM參數傳遞的程式檢查
- Not verified: Windows原生執行、使用者最終合併commit、pin approve/check或8785重啟；無付費API、API key讀取、render或新UI設計採用
- Deviations, UNKNOWN items and follow-ups: QA只重定向state tempfile而保持validator／IO guard；首次unit暫存位置失敗已保留並修正；最終pin SHA待使用者決定，不改凍結輸入或原場景
