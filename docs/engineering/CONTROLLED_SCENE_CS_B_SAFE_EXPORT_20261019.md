# CS-B：D47 人工收據保存與 r003 safe 匯出／E 包驗證

## 實際產出 / Actual output
- Model / effort: Codex；精確 model／effort UNKNOWN。
- PR / commits: `ffcb50d0972b9805ab250e8f5cb5a28a0125a572` 已依使用者授權 normal push 至 `codex/controlled-scene-d47-screening`，遠端 SHA 已核對。此文件與原版 validator 完整報告另以窄範圍證據 commit 發布於同分支；沒有新 PR、merge、rebase 或 force-push，main／整合分支未動。
- Files changed: LOCAL ignored 兩個 run 的 `acceptance/d47_human_review.json`、`safe_bundle/scene_static.json`、`cameras.json`、`manifest.json`、`runtime_profile.json`、`body_policy.json`、`geometry/*.json`，及 acceptance 內 validator 報告；本文件與同目錄下報告子目錄是可發布的精簡證據。原 .blend、RGB、rgb_index、seed、既有篩選輸出均未覆寫；未改正式 backend／loader 或 #77 validator。
- Commands run and results: 原文審查 JSON SHA 核對 2/2、required decisions 集合 307/307 一致；r003 白名單唯讀匯出 48 個靜態物件／鏡頭、missing=0；#77 `c12b16e` 的48條原規則、design層及預設容差完整執行，兩 run 均 **44 PASS／4 FAIL／0 SKIPPED，exit 1**。獨立 audit 核對550 RGB、全部safe allowlist／geometry／光學與binding hash、報告 canonical output hash；#77快照44個原碼檔及template與Git物件逐位元一致。`git diff --check` 通過。只重用既有環境，未安裝依賴或建立 venv／worktree。
- Artifacts: 原文人審收據、safe檔與完整報告路徑／SHA如下；生產程式／逐檔稽核收據留在 LOCAL `data/pilot/controlled_scene_v1/production/private/cs_b_safe_export_20261019/`，不進 safe 或服務。
- Verified: 兩份人審 JSON 與 #68 原文逐位元一致，全部必審格 PASS；標明來源為整體確認、並非虛構307筆按鍵。safe 只匯出靜態標記／幾何、實際光學與run綁定、公開body policy、camera／sampling／hash；沒有產製路線、人物ID、盲窗、人工收據或acceptance locator。來源 r003 SHA不變；RGB/index hash不變；各用途及walkability核准維持 `NOT_EVALUATED`，48個unknown scope未消失，runtime明示NOT_READY。
- Not verified: **validator 整體未通過，不能宣告 CS-B 通過或結案。**未凍結、未讀GT／mask／depth、未渲染或重跑模型、未接服務／外部API；沒有K7／C7物理核准。runtime_profile僅為未ready匯出，不代表完整可執行runtime bundle。
- Deviations, UNKNOWN items and follow-ups: 剩下鍵名相容性及R102微量重疊兩類問題，見下；沒有改舊索引、幾何或放寬容差來換PASS。首輪停用原牆的matrix_world快取誤讀已修正並保留失敗證據。CS-B是否核准由使用者決定，本輪不宣告通過。

## D47 人審原文收據

- LOCAL `/Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-a-5fps-v1-r001/acceptance/d47_human_review.json`；SHA-256 **`af713adad6f8a40f2640f5b6318576e0d30655d20a89784bd7f5106d889deb60`**；10461 bytes；95/95 PASS；來源 [#68 留言 6269925967](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6269925967)。
- LOCAL `/Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-b1-5fps-v1-r001/acceptance/d47_human_review.json`；SHA-256 **`fa8d4cfc65b1c3d419171bf2042e2d63e4068c4da6641ad57d1a3ab2ee2dcb92`**；21510 bytes；212/212 PASS；來源 [#68 留言 6269926692](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6269926692)。

直接擷取GitHub留言的JSON code fence內容（UTF-8），沒有parse後重排／重寫；先核對提供SHA，再保存。`review_method = USER_BULK_CONFIRMATION_IN_COORDINATOR_SESSION`、reviewer聲明、note、keypress_recorded_frames全部原樣保留。A其餘55格、B1其餘188格仍是model screened，不能宣稱550格都有人工作結論。

## r003 source 與匯出範圍

- 來源LOCAL `data/pilot/controlled_scene_v1/assets/controlled_scene_v1_s001_r003.blend`，SHA-256 `6e7de38dc069d330e0ffbb6c0051cdab304566fdbb7e3e8dfb429af863ae6d8e`，匯出前後一致。
- `Blender --background --disable-autoexec <r003> --python <extract_static_r003.py>`，只讀明列的48個靜態來源，不讀人物／動畫／GT；沒有frame_set、render或save。包含floor、walk、原牆與joined外殼、marker及camera，類型數量以實際抽出清單為準，不拿fixture替代。
- safe `objects[]`有42個契約ID；6個walkable，2個portal，4台光學校正；A只綁W1／W2／CTRL，B1綁四台。每run44份幾何JSON＋1份公開body policy，真實檔案SHA逐一核對，manifest另外明列geometry_files；正式loader仍未接新匯出，不把尚待確認的geometry_files擴充當已核准的runtime schema。
- WALK polygon由實際r003平面marker面片聯集匯出，未對齊／吸附設計值。總面積 **136.80949624049717m²**（數值幾何，不是物理精度保證）。42個objects及6個walkable核准均NOT_EVALUATED。
- 22個原牆source component保留，geometry_ref指向實際component mesh；`active_geometry_ref`另指r003實際`WALL_JOINED_SHELL`外殼。沒有移動牆／屏障／相機或修改r003；沒有把bounds當完整mesh。
- 相機matrix由實際靜態RNA transform組合；K用實際Blender lens／sensor／PNG尺寸，校正hash不含run／clock，run_bindings獨立hash。runtime_profile明示NOT_READY、rgb_perception_index尚未物化，不以private預期覆蓋補readiness。event query／推論outputs並非本輪匯出範圍。

## 完整 validator 報告

未使用 `--no-design` 或 `--param`；原版 `c12b16ea92427fae605e5fa4f6f40bda93c52e42`，template SHA `e09853f4062466556ac04a8c4d8e6cf80e5c0dbbce2a918a3ccfcef352364d53`。只讀五個safe JSON，不讀geometry檔、RGB或GT；其未檢查的逐檔geometry／RGB hash由本次獨立audit補核，不能混稱是E包自己量測。

| run | 狀態 | PASS／FAIL／SKIPPED | ERROR | WARN | 完整JSON檔SHA-256 |
| --- | --- | --- | --- | --- | --- |
| A | FAIL | 44／4／0 | 153 | 1 | `fcb769889aff738ee74f079fee7f599c08e2ff218db9ecd12f94280c0bdcae7f` |

A 完整報告：[a_marker_validation.json](controlled_scene_cs_b_validation_20261019/a_marker_validation.json)，與 LOCAL `/Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-a-5fps-v1-r001/acceptance/scene_marker_validation.json` 逐位元一致。報告內 canonical `output_sha256` 為 `2f3643b3971dd0dbed6c1d75df5ca22420a47ca0b8cf68577a79607bccefcc4d`；它與檔案SHA是兩種不同hash。

| B1 | FAIL | 44／4／0 | 403 | 0 | `7ae0e344e22ec2ddb83d5d02bfc4fd3c19e8e12b639c7e8559120462e6215e4d` |

B1 完整報告：[b1_marker_validation.json](controlled_scene_cs_b_validation_20261019/b1_marker_validation.json)，與 LOCAL `/Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-b1-5fps-v1-r001/acceptance/scene_marker_validation.json` 逐位元一致。報告內 canonical `output_sha256` 為 `1f022cfd0ad3464a341af67e50c23900444587a39140987cd9aefed542896ad7`；它與檔案SHA是兩種不同hash。


### 殘留兩類問題（四條FAIL規則）

1. **原索引frames／records**：兩個D55 rgb_index仍為`frames[]`，#77只收`records[]`，因此`SCH-010`、`RUN-004`、`RUN-005` FAIL。A有150個、B1有400個`RGB_INDEX_INCOMPLETE`，**這是validator沒有讀到frames鍵，不是550張PNG真的遺失**；獨立hash核對已確認550/550。另各有1個FIELD_TYPE與1個EVENT_FRAME_TOTAL。保持前次「不改舊index」界線，沒有暗加第二鍵、rename、另造合格fixture或跳過規則。需Claude／契約作者確認既有producer版本adapter或版本化索引遷移，參考[#65命名補充](https://github.com/Polalalabear/amidst/pull/65#issuecomment-6259236783)。
2. **R102 source float32微量重疊**：`OBS-002`在每run各1個`SOLID_OVERLAPS_WALKABLE`。實際walk hole東界x=18.149999618530273m，實際遮屏東界x=18.150001525878906m，差1.9073486328125e−6m；交集面積 **4.577635991154239e−6m²**，超過原參數`overlap_area_tol_m2=1e−6`。原報告訊息四位小數印成0.0000m²，但不代表零。本輪保留原始量測，不把它四捨五入消掉、不擴洞或改牆、不放寬容差。需決定以來源派生walk差集、數值容差提案或其他已核准處理方式修正；不是人工影像PASS自動核准。

A的1個WARN是`CAMERA_UNBOUND`／CAM_N1，符合A不渲N1的已知情況；B1沒有WARN。其他44條規則均PASS，包括相機pose／K、W2間隙、D52後牆外框、門、walk形狀／10處扣除面積、用途未核准狀態及safe/private分離。

### 匯出首輪錯誤與修法

停用的22個原牆source objects初次讀到identity的`matrix_world`快取，產生錯誤AABB與重疊報告；匯出器改為先確認靜態物件無parent、animation、constraint，再由RNA location／rotation／scale組成矩陣，沒有改hide、frame、mesh或來源檔。第一次錯誤輸出與FAIL報告保留在各run的`acceptance/safe_export_attempt_01/`，原RGB／rgb_index從未搬移或覆寫。修正後OBS-004全部通過；OBS-002只剩上述R102的真實數值差。沒有把失敗歷史刪除或改寫成PASS。

## Safe檔案SHA與重現指令

A LOCAL base：`/Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-a-5fps-v1-r001/safe_bundle`

| 檔案 | SHA-256 |
| --- | --- |
| scene_static.json | `a0b3a72c3e1967847b206a501ad64a70bfcb2544951e293db5eb064b71e49482` |
| cameras.json | `6599defea9b53592e8300973d3d4c3f4de0f84ea8a6846ca461873b63ce4e063` |
| manifest.json | `26465eb77cc5f4f3b6a13f9dec661fd06987655974dda781b58eb9c749c44976` |
| runtime_profile.json | `a4e67708216c2f02dad51180eb8ca9df8cb38beb681113b342c0fa9a81ee21f3` |
| rgb_index.json | `9e43237e9c9ac9ea4f2bc97f65e49103a0ec3946b1b555b9d7fbf59850e97d47` |

B1 LOCAL base：`/Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-b1-5fps-v1-r001/safe_bundle`

| 檔案 | SHA-256 |
| --- | --- |
| scene_static.json | `a0b3a72c3e1967847b206a501ad64a70bfcb2544951e293db5eb064b71e49482` |
| cameras.json | `b374a737c9ed39178bfd4d32b17cb05ccfbdfc74e4c7ceafef46482a122fa1ad` |
| manifest.json | `8645f531994b7dd73e4abd6be6bd9056e89a39ad429c0ab1105991ac58395e08` |
| runtime_profile.json | `f59f0bedff651e4ff0bb8b839b1bde197d80285c20f3bd57a946f134d00751df` |
| rgb_index.json | `a5392a6fc5b51257adb82827df376f42290690cbdb52160888eb241f256ecc39` |

```sh
PYTHONPATH=/private/tmp/csb-validator-c12b16e/src UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python python /private/tmp/csb-validator-c12b16e/scripts/validate_controlled_scene.py --safe-dir data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-a-5fps-v1-r001/safe_bundle --output data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-a-5fps-v1-r001/acceptance/scene_marker_validation.json
PYTHONPATH=/private/tmp/csb-validator-c12b16e/src UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python python /private/tmp/csb-validator-c12b16e/scripts/validate_controlled_scene.py --safe-dir data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-b1-5fps-v1-r001/safe_bundle --output data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-b1-5fps-v1-r001/acceptance/scene_marker_validation.json
```

以上是本輪已執行指令；報告已存在，後續驗證應改新output檔名以保留歷史。原版validator/CLI/依賴最小快照在`/private/tmp/csb-validator-c12b16e`，不是clone或worktree，Git原碼SHA已稽核。可用`git archive c12b16e`取回相同明列程式；未修改或安裝相依。

**人工收據保存、safe匯出、原版validator執行與報告交付已完成；validator仍FAIL，待上述兩類問題處理。不凍結、不讀GT、不合併，不宣告CS-B通過。**
