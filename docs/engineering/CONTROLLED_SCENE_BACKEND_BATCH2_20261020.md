# 第二批後端：真實資料接入 v2（2a 交接）

日期：2026-10-20（Asia/Taipei）。依據：[D60 核准契約 v1.1 @ 98451bd](https://github.com/Polalalabear/amidst/blob/98451bd60c0857f38d8638a2548029e557195bf5/docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md)。以下 bootstrap 擴充與 R4 媒體 URL 是**交接提案及本批實作**，待 Claude 納入契約；沒有修改契約、前端或 validator。

## 1. 範圍與 #75 依賴

只完成 2a：兩個既有 Blender RGB run 的註冊、同步取格與 token 媒體服務。`data_origin: ACTUAL_BLENDER` 表示實際 Blender 產出，不代表實拍攝影機或已辨識人物。與 `SYNTHETIC_FIXTURE` 分開配置，未實作的真實圖層不回退到 fixture。

feature `codex/controlled-scene-real-v2-2a` 從 #75 的 `6e1c439137b660db88add84583aa5110976386fb` 分出，Draft PR 暫以 `codex/controlled-scene-backend` 為 base，使差異只包含本批。#75 仍由 Claude／Opus 複審，本批未改它的 head。若 #75 後續修訂，須按使用者授權接入並重跑本批 focused tests。#75 合併後再協調 PR base；本次沒有 merge、rebase、cherry-pick 或改整合分支。

| run | manifest 檔案 SHA-256 | camera scope | index records |
| --- | --- | --- | --- |
| `ctrl-lcorr-s1-a-5fps-v1-r001` | `26465eb77cc5f4f3b6a13f9dec661fd06987655974dda781b58eb9c749c44976` | W1、W2、R102_CTRL | 150 |
| `ctrl-lcorr-s1-b1-5fps-v1-r001` | `8645f531994b7dd73e4abd6be6bd9056e89a39ad429c0ab1105991ac58395e08` | W1、W2、N1、R102_CTRL | 400 |

兩份 source pin 均為 r003 的 `6e7de38dc069d330e0ffbb6c0051cdab304566fdbb7e3e8dfb429af863ae6d8e`。locator 固定為 canonical repo 下 `data/pilot/controlled_scene_v1/runs/<run_id>/`，不掃描相鄰 run。註冊與 pins 在 `controlled_scene_rgb_data.py`，caller 不提供路徑或 pins。舊 Office factory 透過 Git common-dir 的 canonical asset root 註冊，不錯指向 `phase1-finalization` evidence 目錄。

## 2. Bootstrap 與 loader

`GET /api/bootstrap?surface=workbench-v2` 回 `controlled-scene.bootstrap.v1`：

- 頂層 `data_origin: ACTUAL_BLENDER`、`fixture_marker: null`、`status: PARTIAL`、`real_run_support: RGB_PLAYBACK_ONLY`、`gt_read: false`。
- `scenes[]` 每個 scene 有 `scene_id`、`run_ids[]`、鏡頭聯集 `camera_ids[]`，以及新增的 **`runs[]`**。每個 run 各列 `clock_id`、`sampling`、`camera_ids`、manifest/source pins、D57 adapter receipt、`runtime_readiness`、`unavailable_inputs`、`capabilities`。
- A 為 `[0,10)` s／50 samples，B1 為 `[0,20)` s／100 samples，均 5 fps、960×540。A 的 cameras 檔另含 N1，但沒有 A 的 run binding；因此不把 N1 列為 A 的可播放鏡頭，也不造 MISSING tile。
- `capabilities.synced_frames: AVAILABLE` 只表示 RGB 入口具備 metadata；每次取格與 GET 仍驗 hash。其餘四端點 `NOT_MATERIALIZED`，呼叫回 503，不產替代圖層。
- 原 profile 的 `runtime_readiness: NOT_READY` 與未物化 `rgb_perception_index` 原樣保留。取格成功的 `status: READY` 只屬該請求，不代表整個 runtime 或 checkpoint 通過。
- 一般 `/api/bootstrap` 保留 legacy catalog，nested controlled 欄位只給 v2 `surface_ref`，不因 optional controlled bundle 缺少而阻斷舊工作台。

`load_safe_run(registration, purpose="RGB_PLAYBACK")` 是明確的新讀取範圍；預設 `FULL_RUNTIME` 檢查不放寬。只開 manifest 與 allowlist 中的 `scene_static.json`、`cameras.json`、`runtime_profile.json`、`rgb_index.json`，核對原始 bytes pins 和 source/run/clock/grid 綁定。不開 `geometry_files`、body policy、private、acceptance、產製腳本或設計路線。scene_static 只核對來源與 hash，不產生可走或遮擋 authority。

原 optical hash 與 run binding hash 分別核對；不改 float32 矩陣、不轉置、不把 NOT_EVALUATED 升為 APPROVED。RGB scope 的 `SafeRun.calibrations` 留空，另有 `rgb_camera_ids` 限定播放，不是 C4a 校正 adapter 已完成。

索引經 #75 的 **`controlled-scene.rgb-index-adapter / d57-v1`** 在記憶體轉換；receipt 含原檔 SHA、來源 schema／collection、target records 與 normalized content hash。兩份 D55 檔與 hash 不變；非核准 legacy pin、雙鍵、無鍵照 D57 fail closed。grid 每格必須恰有一筆 record 或 explicit missing。

## 3. R4 媒體 URL 提案及實作

### 3.1 URL、scope、有效期

READY tile 的 `frame_ref`：

```text
/api/controlled_rgb?token=<43 字元 opaque base64url token>
```

token 由 `secrets.token_urlsafe(32)` 產生，是 scoped bearer capability，不是登入憑證。不含 session key、filesystem locator 或 private 資訊；持有 URL 的 caller 能在期限內重讀同一個 PNG，不宣稱防止 URL 被複製。grant 綁定發起 session、scene/run/source、manifest pin、camera、frame index、原檔與 served hash。GET 只接受單一 `token`，不能加 run_id、camera_id、ref 或路徑。

工程預設有效期 **120 s**（monotonic clock，到期端點拒絕），僅當前 server instance／process 有效。GET 重查 owner session 存在且具有 scene scope，重新驗必要 safe pins 與對應 RGB 原檔 hash。120 s 是工程提案，不是 CS-Q9 的科學或場景門檻。

記憶體上限 **2048 grants**；新請求先清到期項，再淘汰最舊 grant。已淘汰／重啟後的 token 拒絕，caller 應重新取 synced_frames。仍在 store 的已知到期 token 回 410；清除後與其他未知 token 一樣回 403。token 不持久化、不寫 log／收據，採既有 QuietHandler。本批未承諾多 process 共用 token 或部署認證。

GET 受 localhost Host guard；帶 Origin 必須同源，`Sec-Fetch-Site: cross-site` 拒絕。不使用 Referer 授權。回應帶 `Cache-Control: no-store`、`Referrer-Policy: no-referrer`、`X-Content-Type-Options: nosniff`。

### 3.2 RGB bytes 與同步

先核對 RGB 原檔 `file_sha256`，再重用 `blender_scene.strip_png_text` 移除 tEXt／iTXt／zTXt，保留其餘 chunks 位元組（含像素 chunks）。不解碼、重編碼、覆寫原 PNG 或另存副本。tile 同時回原檔 `file_sha256` 和 HTTP bytes 的 **`served_sha256`**；兩者不能混用。無效 PNG 為完整性錯誤。

所有 requested tiles 都驗完才發 token；任一張 hash／pin／格式錯誤，整份 409，不發本次 token。**觀察到完整性錯誤後該 run 在 API instance 鎖閉**，舊 grant 也不能繼續用；另一獨立 run 不自動被換掉或污染。修復後須新 server instance 重新驗證，不提供瀏覽器 reset／重設 pin。未全量預讀未請求 RGB，也不把未查檔案宣告已驗證。

取格依有理數 fps 與整數微秒比較。D60 時間規則在新入口採 `t_s × 10^6` 必須為整數；次微秒輸入 **400，不自行 round**。請 Claude 將此輸入精度處理寫入 wire 契約。回新增 `t_us`、`expected_timestamp_us`；既有 `_s` 欄位從整數微秒換算。sample age 與 clock error 分開，同 clock sample `clock_error_s = 0`，不保證外部 clock 已同步。

missing[] 格回 MISSING／null frame_ref，不回退；`[0,duration)` 外為 OUT_OF_RANGE／null。已 pin RGB 不存在回 409，必要 metadata 缺失回 503。URL 隨機，`output_sha256` 可核對當次完整回應（排除自身），不承諾同 payload 的 token／hash 固定。

### 3.3 錯誤碼（請 Claude 納入契約）

本批真實 surface 的 bootstrap、synced_frames、media 使用：

```json
{"schema_version":"controlled-scene.error.v1","error":{"error_class":"DataIntegrityError","reason":"RGB_RECORD_HASH_MISMATCH"}}
```

| HTTP | error_class | reason／情境 |
| --- | --- | --- |
| 400 | `InvalidRequest` | `INVALID_CONTROLLED_REQUEST`：query 多鍵／重複鍵、camera 越界、非有限時間、次微秒輸入等 |
| 403 | `MediaAccessError` | `MEDIA_TOKEN_INVALID`：未知、不合法、已清除／淘汰 |
| 403 | `AccessDenied` | `SESSION_DENIED`、`SCENE_DENIED`、`ORIGIN_DENIED`、`HOST_DENIED`、`REAL_RGB_NOT_CONFIGURED` 等 guard 原因碼 |
| 410 | `MediaAccessError` | `MEDIA_TOKEN_EXPIRED`：仍在 store 但已到期 |
| 409 | `DataIntegrityError` | `SAFE_FILE_HASH_MISMATCH`、`SOURCE_RUN_PIN_MISMATCH`、`RGB_RECORD_HASH_MISMATCH`、`PINNED_RGB_RECORD_MISSING`、`RGB_INDEX_INCOMPLETE`、`MEDIA_GRANT_PIN_MISMATCH`、`SERVED_RGB_HASH_MISMATCH`、`RGB_PNG_INVALID` 等 |
| 503 | `RequiredInputUnavailable` | `REQUIRED_SAFE_INPUT_UNAVAILABLE`：必要 safe JSON 不存在；`RGB_RESOURCE_UNAVAILABLE`：其他不可讀 I/O；`CONTROLLED_LAYER_NOT_MATERIALIZED`：2b–2d 尚未接入 |

409 必須清空／遮住本次舊 tiles，不畫成 MISSING。410／失效 token 403 可重新取得 synced_frames，不換其他 run 填圖。未授權 filesystem URL 仍 403／404。#75 fixture 的既有 400／403 wire 不變，本表擴充真實 surface 與媒體 route。

## 4. Claude 前端交接

1. 讀 `scenes[].runs[]` 的 per-run sampling／camera scope，讓使用者選 A 或 B1；不要把 A 套成 20 s，或用鏡頭聯集補 N1。先取 `/api/session`，請求帶 session_ref／scene_id／run_id。
2. READY frame_ref 現在可直接作 image URL。fixture symbolic ref 不變，用 data_origin／mode 分流，不套舊 `/api/media`。
3. HTTP bytes 驗 served_sha256，不用原檔 hash。token 不放永久分享／log，不跨 server 重啟重用。
4. 真實 candidate／person／curve／evidence 未實作，依 capabilities 暫停操作，503 不 fallback。R7 launcher 預設入口不改。
5. bootstrap／媒體欄位與錯誤表由 Claude 更新契約與前端；本輪未改 `frontend/`、`docs/contracts/`、validator #77。

## 5. 2b–2d 計畫（未開工）

以下是**預定**範圍；尚未建立模組或推論輸出。各批先確認 I/O 與 pins，再獨立 PR／focused tests。D47 screening 的產製投影與人工審查 JSON 不進推論。

| 批次 | 預定新增／修改檔案 | 資料流、前置及 #75 依賴 |
| --- | --- | --- |
| **2b** | 新 `src/amidst/workbench/controlled_scene_perception.py`、`src/amidst/engineering/controlled_scene_contact.py`、`src/amidst/workbench/controlled_scene_person.py`；修改 `controlled_scene_data.py`、`controlled_scene_rgb_api.py`；新 `configs/controlled_scene_perception_v1.json`、`tests/workbench/test_controlled_scene_person.py` | RGB → camera-local tracks → C4a 單格區間 → 同 track 軌跡身高範圍 → composed_ground → person_layer。包裝既有 `engineering/perception.py`／`perception_v2.py`／`hybrid_contact.py`，不搬舊 Office config、固定張數或 D47 驗收答案。D61 外部視覺判斷一律 `NOT_USED`，不接姿態模型／OpenAI API。依賴 #75 uncertainty／錯誤 guard、D57、2a scope／RGB hashes；另物化並 pin 感知索引。身高不跨 track、不進關聯排序。靜態用途核准及 float32 optical adapter 尚未完成，缺少時保持 UNKNOWN／不可用；RGB load 不代表投影核准。SEGMENT／POLYGON 等 OPEN 名稱先協調。 |
| **2c** | 新 `src/amidst/workbench/controlled_scene_candidates.py`、`scripts/build_controlled_visibility_index.py`、`configs/controlled_scene_visibility_v1.json`、`tests/workbench/test_controlled_scene_candidates.py`；修改 `controlled_scene_data.py`、`controlled_scene_rgb_api.py` | 新鏡頭＋核准 WALKABILITY／OCCLUSION／VISIBILITY_INDEX 幾何 → floor visibility index → candidate_cameras。重用 `geometry/floor_visibility_index.py` 與 visibility policy 的純入口，預設不改 owner 檔，需要演算法改動先交 Claude。依賴 #75 candidate provenance／錯誤規則、2a bindings；不必等 2b 偵測，D28 不用偵測數排序。通路距離 OPEN，不自己定值；地板不可見不證明全身盲。用途未核准不產 READY 索引。 |
| **2d** | 新 `src/amidst/workbench/controlled_scene_hypotheses.py`、`controlled_scene_curves.py`、`controlled_scene_evidence.py`；修改 `controlled_scene_data.py`、`controlled_scene_rgb_api.py`；新 `tests/workbench/test_controlled_scene_curves.py`、`test_controlled_scene_evidence.py` | 2b RGB/local track/C4a/composed＋2c 索引 → K1／C4b 新事件 adapter → curve_layer／evidence_lookup。重用 Claude K1 純模組與既有 physical integration，另加 adapter，不改舊 D18 guard／固定設定。依賴 #75 M1/M2 uncertainty／closed kinds／immutable refs、2a token 媒體及 2b/2c pins。保留未關聯基線、多解、identity UNCONFIRMED、physical UNKNOWN。曲線條件命名、INFERRED_CONSTRAINED 維持 OPEN，先決策再定 wire；D56 CS-D 方向不算本批已完成。 |

各批工時在確認 schema、geometry authority、#75 複審後再估，本次不以未量測數字承諾時程。不凍結、不讀 GT、不合併，不把批次完成當 checkpoint 核准。

## 6. 實際產出 / Actual output

- Model / effort: Codex；精確 model／effort UNKNOWN。
- PR / commits: `codex/controlled-scene-real-v2-2a`，parent #75 `6e1c439`；提交 SHA／Draft PR URL 見 GitHub 收據。
- Files changed: 新 `controlled_scene_rgb_data.py`、`controlled_scene_rgb_api.py`；修改 `controlled_scene_data.py`、`service.py`、`scripts/office_demo_backend.py`；新 `scripts/check_controlled_rgb_playback.py`、`tests/workbench/test_controlled_scene_rgb.py`；本文件、`docs/README.md`。
- Commands run and results: 下列四檔 focused pytest **307 passed**；七個變動 Python 檔 ruff **All checks passed**；`git diff --check` 通過。真實 WSGI check **2 runs／21 次 RGB GET PASS**（各鏡頭 t=0、5、last sample），沒開 listener。
- Artifacts: **LOCAL** `/private/tmp/controlled-rgb-2a-real-check-20261020.json`，SHA-256 `5bdafcebd5c5ee119da1b8088d7fa6a83db367ea93e8aef562448ca1ff116da4`；含 original／served hashes、D57 receipts、read counts／input hashes，無 token。
- Verified: A 150／B1 400 index records 經 D57 載入；21 次 GET／tile served hash 一致；safe-only read guard；缺格不回退、批次失敗不發 token、run 完整性鎖閉、token 期限／撤銷／scope／hash／路徑拒絕、fixture／legacy 隔離。
- Not verified: 未讀完或驗收全部 550 張影像，未視覺解碼、browser acceptance、感知／C4a／候選／曲線計算、定位準確度或效能驗收；未跑 full suite／mypy。原 .blend／RGB／safe JSON 未改，未讀 private／GT／acceptance。
- Deviations, UNKNOWN items and follow-ups: r003 safe wire 不同於 #75 早期完整 runtime wire，因此明確增加 RGB_PLAYBACK scope，不改舊檔或假裝完整 loader 通過。R4 URL、token 工程值、bootstrap runs 欄位、次微秒政策待 Claude 納入契約；#75 複審待結果。2b–2d 只列計畫。

可重現指令（使用既有環境，不建 venv／安裝依賴）：

```sh
PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python python -m pytest tests/workbench/test_controlled_scene_rgb.py tests/workbench/test_controlled_scene_service.py tests/workbench/test_controlled_scene_data.py tests/workbench/test_service.py -o addopts='' -q
UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python /Users/polalabear/Developer/amidst-claude/.venv/bin/ruff check src/amidst/workbench/controlled_scene_data.py src/amidst/workbench/controlled_scene_rgb_data.py src/amidst/workbench/controlled_scene_rgb_api.py src/amidst/workbench/service.py scripts/office_demo_backend.py scripts/check_controlled_rgb_playback.py tests/workbench/test_controlled_scene_rgb.py --output-format concise
PYTHONPATH=src:scripts UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python python scripts/check_controlled_rgb_playback.py --repo /Users/polalabear/Developer/amidst --output /private/tmp/controlled-rgb-2a-real-check-20261020.json
git diff --check
```

重跑 check 的 `--output` 要換新檔名，不能覆寫收據。首次 uv 在 sandbox 內因 macOS system-configuration panic；之後經權限審查執行上述 focused commands，沒有換環境或安裝套件。
