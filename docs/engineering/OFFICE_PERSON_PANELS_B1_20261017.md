# B1：人形場景三個舊面板與 10/24 範圍估計

本次是唯讀診斷／工作量估計及 B3 文件交付，不實作三面板、不產生媒體。基準為 #50 的 cd6c854；#53 維持 Draft，K1/K5 不同步，C6 暫停。不碰 amidst-claude checkout，不啟停現有驗收服務。

## 已確認：NOT_MATERIALIZED_FOR_RUN 是目前預期行為

| 證據路徑（基準 cd6c854） | 已確認行為 |
| --- | --- |
| configs/office_demo_presets_person_v1.json:23–31 | person 指定 rgb-mask-contact-v2，另接 C4b hypothesis binding。 |
| src/amidst/workbench/contact_scene.py:286–303 | v2 明確傳 enable_reconstruction=False；motion／association／physical_source／physical 全列 UNAVAILABLE/NOT_MATERIALIZED_FOR_RUN，physical_review=False。 |
| src/amidst/workbench/blender_scene.py:485–487 | enable_reconstruction=False 時，不建立舊 BaselineMotionIndex／BaselineAssociationIndex。 |
| src/amidst/workbench/service.py:547–558 | 三面板請求在 layer guard 回 UNAVAILABLE 及該 reason。只有帶 blind integration 的 target_reconstruction 例外繼續執行。 |
| scripts/office_demo_backend.py:223–245 | physical source 與三類 media provider 只接 blender-office；person 沒有被接入，也不會拿舊 run 頂替。 |
| src/amidst/workbench/blender_motion.py:261–268 | 舊 motion 需要 PROJECTED 且非 null 的 world_position 才有觀測曲線。 |
| src/amidst/workbench/blender_association.py:83–95 | 舊 association 跳過 null world_position，使用有效本地運動分段建立 nodes。 |

已存在的 C4b freeze 記錄33/33原始 person 觀測為 MISSING/null，兩端是 SEGMENT，target envelope 為 UNKNOWN/SELECTED_PROJECTION_UNAVAILABLE，獨立 blind_hypotheses 為 READY/1條代表假設。這是檔案與程式路徑的 VERIFIED，不是本次 live HTTP／瀏覽器重跑。

因此這不只是欠一個離線 materialize 命令。只開 capability 或重新跑舊 materializer，不能得到有證據支持的舊式觀測運動／跨鏡頭候選；把 SEGMENT 的中點、K1 推測位置或舊 run 位置塞回觀測曲線也不成立。物理審查還依賴舊 physical reconstruction 的 schema／來源 authority，不能只把 C7 檔案路徑代入。

## 10/24 的建議決策

**不安排在 10/24 前補齊這三個舊面板；Demo 步驟5若仍是原本的「跨鏡頭候選＋運動／物理審查」操作，建議拿掉。** 本次沒有啟動這項實作。其前置是合法的 v2 local-track／位置不確定性契約及對應消費端，而非 Blender 渲染；能否產生有用的觀測曲線、需要多少估計器研究仍 UNKNOWN，不能承諾日期。沒有理由為此重新 render。

若團隊想保留一個較小的步驟，可改名為 **「C4b 推測候選審查」**：重用既有 sealed blind_hypotheses／review_evidence、FRONT4.6→REAR8.2及 C7 person map，檢視推論路徑與端點區間，保留原33 MISSING、identity UNCONFIRMED、physical UNKNOWN。這與三個舊面板是不同交付，不能說已確認跨鏡頭同一人、觀測到完整運動或完成物理驗收。現在只有1條代表假設，不承諾候選1/2/3切換。

這個有界替代版無須新渲染；估計 Codex 1–2 工程日、Claude 0.5–1 工程日，加0.5日共同彩排／修正，約2–3.5工作日。若先確認此範圍並能排入工作，10/24前有工程可行性；不是目前已排程或已承諾的交付。估計包含介面與顯示接線，不包含接地演算法研究、影片生成、GT評估或真實物理安全核准；K1/K5仍等雙方核對完成後的一次同步，不搶先接線。

替代版預計觸及的檔案（本次不改）：

| 負責方 | 檔案／目的 |
| --- | --- |
| Claude起草、Codex確認 | docs/contracts/OFFICE_BLIND_HYPOTHESIS_V1.md、docs/contracts/OFFICE_DEMO_TARGET_V1.md：確認推測審查來源、hash／session、選取與 UNKNOWN 邊界。 |
| Codex | src/amidst/workbench/blind_hypothesis_integration.py：整理既有 review_evidence；必要時新增 src/amidst/workbench/person_hypothesis_review.py，提供僅供推測審查的 adapter。 |
| Codex | src/amidst/workbench/service.py：僅在契約需要新查詢時接入，不能把 person 的 observed motion／association capability 改成可用。 |
| Codex | scripts/office_demo_backend.py、tests/workbench/test_blind_hypothesis_integration.py、tests/workbench/test_office_demo_presets.py：person/source-map binding及不借舊 run／不回填觀測的 focused 驗證；若新增 adapter，另增 tests/workbench/test_person_hypothesis_review.py。 |
| Claude | frontend/workbench/app.mjs、frontend/workbench/cross-camera.mjs及其focused tests：把步驟5接到推測層，標明1條假設／來源／未確認狀態，做瀏覽器驗收。實際前端拆檔依 Claude 目前分支確認，本次未檢視另一 checkout。 |

不需要改 scripts/materialize_blender_motion.py、scripts/materialize_blender_association.py 或 scripts/materialize_blender_physical.py 來偽造這個替代版的舊式 observed 結果；不建立舊 run 媒體別名。若要求真正補齊三面板，需另立有觀測依據的任務與契約，不能套用上述2–3.5日估計。

## B3 彩排文件

已在 [啟動器文件](../operations/OFFICE_DEMO_LAUNCHER.md) 最上方加入現行彩排段落：Git common dir與 OFFICE_ASSETS_REPO、evidence/Python設定、tracked修改拒絕，以及同一組 exports 的生命週期命令。原固定 checkout／branch敘述標成歷史，未覆寫歷史驗證結果。

## 實際產出 / Actual output

- Model / effort: gpt-6.1-sol / high，current session turn_context已核對。
- PR / commits: 純文件分支 codex/office-demo-rehearsal-docs，base #50/cd6c854；發布後在 PR／issue記錄精確SHA。#53仍Draft，沒有merge。
- Files changed: docs/operations/OFFICE_DEMO_LAUNCHER.md、本報告、docs/README.md、docs/history/WORK_LOG.md；沒有程式或設定變更。
- Commands run and results: git status/branch；對上述限定檔案的 rg/sed/nl；jq核對現有 C4b freeze 的33 MISSING與端點／target/hypothesis狀態；文件相對連結、shell範例語法及 git diff --check核對。驗證結果隨提交記錄。
- Artifacts: NONE新增資料／媒體／推論；估計是規劃，不是產出結果。
- Verified: v2停用舊重建、service提前返回、legacy-only providers、非null位置前置，以及 launcher環境變數／tracked gate的實際程式邏輯。
- Not verified: 本次未啟動服務、瀏覽器、推論、Blender、materializer、完整測試或替代版實作；沒有把 Claude驗收當成本task結果。
- Deviations, UNKNOWN items and follow-ups: 三面板原版不列入10/24承諾，建議移除原步驟5；有界推測審查是未排程的可選替代估計。K1/K5同步待使用者通知，C6暫停。

文件驗證完成：相對連結0缺失、launcher文件所有sh範例以bash -n只做語法檢查通過；既有freeze的33/33 MISSING、4.6→8.2端點與1條獨立假設核對通過；git diff --check PASS。未執行範例或程式測試。#53 live狀態確認仍isDraft=true、head=ce766f9d6d5639d674da7aaa12d9aec795bdbcab，未變更。

    awk '/^```sh$/{inside=1;next} /^```$/{inside=0;next} inside{print}' docs/operations/OFFICE_DEMO_LAUNCHER.md | /bin/bash -n
    PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline .local-worktrees/phase1-finalization/.venv/bin/python /private/tmp/amidst-b1b3-doc-check.py
    git diff --check

第二個指令的驗證腳本是LOCAL暫存檔，只讀取上述文件與既有fixture/freeze，不進行資料產製。
