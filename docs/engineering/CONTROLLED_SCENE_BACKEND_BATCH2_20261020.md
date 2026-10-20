# 第二批後端：真實資料接入 v2（2a 交接）

日期：2026-10-20（Asia/Taipei）。依據：[D60 核准契約 v1.1 @ 98451bd](https://github.com/Polalalabear/amidst/blob/98451bd60c0857f38d8638a2548029e557195bf5/docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md)。以下實作已納入 D62 O8/O9 與 #80 複審修正，v1.2 仍待指定 SHA 確認；沒有修改契約、前端或 validator。

## 1. 範圍與 #75 依賴

只完成 2a：兩個既有 Blender RGB run 的註冊、同步取格與 token 媒體服務。`data_origin: ACTUAL_BLENDER` 表示實際 Blender 產出，不代表實拍攝影機或已辨識人物。與 `SYNTHETIC_FIXTURE` 分開配置，未實作的真實圖層不回退到 fixture。

feature `codex/controlled-scene-real-v2-2a` 從 #75 的 `6e1c439137b660db88add84583aa5110976386fb` 分出，Draft PR 暫以 `codex/controlled-scene-backend` 為 base，使差異只包含本批。#75 仍由 Claude／Opus 複審，本批未改它的 head。若 #75 後續修訂，須按使用者授權接入並重跑本批 focused tests。#75 合併後再協調 PR base；首次交付沒有 merge、rebase、cherry-pick 或改整合分支；本輪依授權以新 commit `170a5ef` 帶入 #75 修正 `8aff562`（README 相鄰文字衝突已保留兩批條目）。

| run | manifest 檔案 SHA-256 | camera scope | index records |
| --- | --- | --- | --- |
| `ctrl-lcorr-s1-a-5fps-v1-r001` | `26465eb77cc5f4f3b6a13f9dec661fd06987655974dda781b58eb9c749c44976` | W1、W2、R102_CTRL | 150 |
| `ctrl-lcorr-s1-b1-5fps-v1-r001` | `8645f531994b7dd73e4abd6be6bd9056e89a39ad429c0ab1105991ac58395e08` | W1、W2、N1、R102_CTRL | 400 |

兩份 source pin 均為 r003 的 `6e7de38dc069d330e0ffbb6c0051cdab304566fdbb7e3e8dfb429af863ae6d8e`。locator 固定為所選 assets repo 下 `data/pilot/controlled_scene_v1/runs/<run_id>/`，不掃描相鄰 run。註冊與 pins 在 `controlled_scene_rgb_data.py`，caller 不提供路徑或 pins。Office factory 跟隨 `--assets-repo`（L2）；未指定時才用 Git common-dir 的 canonical asset root。serve 與 reproduce 都傳入相同設定，不用 `phase1-finalization` evidence 目錄代替。

## 2. Bootstrap 與 loader

`GET /api/bootstrap?surface=workbench-v2` 回 `controlled-scene.bootstrap.v1`：

- 頂層 `data_origin: ACTUAL_BLENDER`、`fixture_marker: null`、`status: PARTIAL`、`real_run_support: RGB_PLAYBACK_ONLY`、`gt_read: false`。
- `scenes[]` 每個 scene 有 `scene_id`、`run_ids[]`、鏡頭聯集 `camera_ids[]`，以及新增的 **`runs[]`**。每個 run 各列 `clock_id`、`sampling`、`camera_ids`、manifest/source pins、D57 adapter receipt、`runtime_readiness`、`unavailable_inputs`、`capabilities`。
- A 為 `[0,10)` s／50 samples，B1 為 `[0,20)` s／100 samples，均 5 fps、960×540。A 的 cameras 檔另含 N1，但沒有 A 的 run binding；因此不把 N1 列為 A 的可播放鏡頭，也不造 MISSING tile。
- `capabilities.synced_frames: AVAILABLE` 只表示 RGB 入口具備 metadata；每次取格與 GET 仍驗 hash。其餘四端點 `NOT_MATERIALIZED`，呼叫回 503，不產替代圖層。
- 完整性錯誤按 run 隔離：失敗 run 只列 run_id、data_origin、NOT_READY、integrity（FAILED／error_class／安全 reason）與全 UNAVAILABLE capabilities；不回傳無法信任的 metadata、收據或幾何。其他 run 照常列出與播放。全部 run 完整性失敗才回 409；一般 I/O 仍回 503 且不鎖 run。
- 原 profile 的 `runtime_readiness: NOT_READY` 與未物化 `rgb_perception_index` 原樣保留。`synced_frames.status: READY` 只表示請求已處理；即使全部 tiles 是 MISSING 或 OUT_OF_RANGE 仍可為 READY，不能據此推斷有可播放影格、runtime 或 checkpoint 通過。
- 一般 `/api/bootstrap` 保留 legacy catalog，nested controlled 欄位只給 v2 `surface_ref`，不因 optional controlled bundle 缺少而阻斷舊工作台。

`load_safe_run(registration, purpose="RGB_PLAYBACK")` 是明確的新讀取範圍；預設 `FULL_RUNTIME` 檢查不放寬。只開 manifest 與 allowlist 中的 `scene_static.json`、`cameras.json`、`runtime_profile.json`、`rgb_index.json`，核對原始 bytes pins 和 source/run/clock/grid 綁定。不開 `geometry_files`、body policy、private、acceptance、產製腳本或設計路線。scene_static 只核對來源與 hash，不產生可走或遮擋 authority。

原 optical hash 與 run binding hash 分別核對；不改 float32 矩陣、不轉置、不把 NOT_EVALUATED 升為 APPROVED。RGB scope 的 `SafeRun.calibrations` 留空，另有 `rgb_camera_ids` 限定播放，不是 C4a 校正 adapter 已完成。

索引經 #75 的 **`controlled-scene.rgb-index-adapter / d57-v1`** 在記憶體轉換；receipt 含原檔 SHA、來源 schema／collection、target records 與 normalized content hash。兩份 D55 檔與 hash 不變；非核准 legacy pin、雙鍵、無鍵照 D57 fail closed。grid 每格必須恰有一筆 record 或 explicit missing。

## 3. R4 媒體 URL 提案及實作

### 3.1 URL、scope、有效期

READY tile 的穩定 `frame_ref` 為 `fr-<run_id>-<camera_id>-<frame_index:06d>`；token 網址另放 `media_url`（O8）：

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

取格依有理數 fps 與整數微秒比較。依 D56／D62 O9，先將 `t_s × 10^6` **四捨五入到整數微秒**，恰半微秒時遠離零（不使用 ties-to-even），再作半開 run 範圍與 grid 選格；不加 epsilon。回新增 `t_us`、`expected_timestamp_us`；既有 `_s` 欄位從整數微秒換算。sample age 與 clock error 分開，同 clock sample `clock_error_s = 0`，不保證外部 clock 已同步。

missing[] 格回 MISSING／null frame_ref 與 null media_url，不回退；`[0,duration)` 外為 OUT_OF_RANGE／null。已 pin RGB 不存在回 409，必要 metadata 缺失回 503。URL 隨機。依 #81 §3.1 B2，語意 `output_sha256` 排除自身與 media_tokens_issued，並把每格 media_url 正規化為 null 後計算；相同語意請求的 frame_ref／hash 不因 session 或 token 更新而變動，來源／manifest pin 另由 resolved_scope／provenance 綁定。

### 3.3 錯誤碼（請 Claude 納入契約）

本批真實 surface 的 bootstrap、synced_frames、media 使用：

```json
{"schema_version":"controlled-scene.error.v1","error":{"error_class":"DataIntegrityError","reason":"RGB_RECORD_HASH_MISMATCH"}}
```

| HTTP | error_class | reason／情境 |
| --- | --- | --- |
| 400 | `InvalidRequest` | `INVALID_MEDIA_QUERY`：query 多鍵／重複鍵；`INVALID_CAMERA_SCOPE`：camera 越界；其他 schema／非有限時間為 `INVALID_CONTROLLED_REQUEST`（安全 reason，不回顯路徑） |
| 403 | `MediaAccessError` | `MEDIA_TOKEN_INVALID`：未知、不合法、已清除／淘汰 |
| 403 | `AccessDenied` | `SESSION_DENIED`、`SCENE_DENIED`、`ORIGIN_DENIED`、`HOST_DENIED`、`REAL_RGB_NOT_CONFIGURED` 等 guard 原因碼 |
| 410 | `MediaAccessError` | `MEDIA_TOKEN_EXPIRED`：仍在 store 但已到期 |
| 409 | `DataIntegrityError` | `SAFE_FILE_HASH_MISMATCH`、`SOURCE_RUN_PIN_MISMATCH`、`RGB_RECORD_HASH_MISMATCH`、`PINNED_RGB_RECORD_MISSING`、`RGB_INDEX_INCOMPLETE`、`MEDIA_GRANT_PIN_MISMATCH`、`SERVED_RGB_HASH_MISMATCH`、`RGB_PNG_INVALID` 等 |
| 503 | `RequiredInputUnavailable` | `REQUIRED_SAFE_INPUT_UNAVAILABLE`：必要 safe JSON 不存在；`RGB_RESOURCE_UNAVAILABLE`：其他不可讀 I/O；`CONTROLLED_LAYER_NOT_MATERIALIZED`：2b–2d 尚未接入 |

409 必須清空／遮住本次舊 tiles，不畫成 MISSING。410／失效 token 403 可重新取得 synced_frames，不換其他 run 填圖。未授權 filesystem URL 仍 403／404。#75 fixture 的既有 400／403 wire 不變，本表擴充真實 surface 與媒體 route。

## 4. Claude 前端交接

1. 讀 `scenes[].runs[]` 的 per-run sampling／camera scope，讓使用者選 A 或 B1；不要把 A 套成 20 s，或用鏡頭聯集補 N1。先取 `/api/session`，請求帶 session_ref／scene_id／run_id。
2. READY tile 用 media_url 作 image URL，frame_ref 是穩定來源參照。fixture symbolic ref 不變，用 data_origin／mode 分流，不套舊 `/api/media`。
3. HTTP bytes 驗 served_sha256，不用原檔 hash。token 不放永久分享／log，不跨 server 重啟重用。
4. 真實 candidate／person／curve／evidence 未實作，依 capabilities 暫停操作，503 不 fallback。R7 launcher 預設入口不改。
5. bootstrap／媒體欄位與錯誤表由 Claude 更新契約與前端；本輪未改 `frontend/`、`docs/contracts/`、validator #77。

## 5. 2b–2d 計畫（未開工）

以下是**預定**範圍；尚未建立模組或推論輸出。各批先確認 I/O 與 pins，再獨立 PR／focused tests。D47 screening 的產製投影與人工審查 JSON 不進推論。

| 批次 | 預定新增／修改檔案 | 資料流、前置及 #75 依賴 |
| --- | --- | --- |
| **2b** | 新 `src/amidst/workbench/controlled_scene_perception.py`、`src/amidst/engineering/controlled_scene_contact.py`、`src/amidst/workbench/controlled_scene_person.py`；修改 `controlled_scene_data.py`、`controlled_scene_rgb_api.py`；新 `configs/controlled_scene_perception_v1.json`、`tests/workbench/test_controlled_scene_person.py` | RGB → camera-local tracks → C4a 單格區間 → 同 track 軌跡身高範圍 → composed_ground → person_layer。包裝既有 `engineering/perception.py`／`perception_v2.py`／`hybrid_contact.py`，不搬舊 Office config、固定張數或 D47 驗收答案。D61 外部視覺判斷一律 `NOT_USED`，不接姿態模型／OpenAI API。依賴 #75 uncertainty／錯誤 guard、D57、2a scope／RGB hashes；另物化並 pin 感知索引。身高不跨 track、不進關聯排序。靜態用途核准及 float32 optical adapter 尚未完成，缺少時保持 UNKNOWN／不可用；RGB load 不代表投影核准。O5 已定案 INFERRED_CONSTRAINED、O6 v1 一律 SEGMENT／LENGTH_M；用途未核准不啟動本批。 |
| **2c** | 新 `src/amidst/workbench/controlled_scene_candidates.py`、`scripts/build_controlled_visibility_index.py`、`configs/controlled_scene_visibility_v1.json`、`tests/workbench/test_controlled_scene_candidates.py`；修改 `controlled_scene_data.py`、`controlled_scene_rgb_api.py` | 新鏡頭＋核准 WALKABILITY／OCCLUSION／VISIBILITY_INDEX 幾何 → floor visibility index → candidate_cameras。重用 `geometry/floor_visibility_index.py` 與 visibility policy 的純入口，預設不改 owner 檔，需要演算法改動先交 Claude。依賴 #75 candidate provenance／錯誤規則、2a bindings；不必等 2b 偵測，D28 不用偵測數排序。O11 通路依 portals 拓撲直接相連定義；地板不可見不證明全身盲。用途未核准不產 READY 索引。 |
| **2d** | 新 `src/amidst/workbench/controlled_scene_hypotheses.py`、`controlled_scene_curves.py`、`controlled_scene_evidence.py`；修改 `controlled_scene_data.py`、`controlled_scene_rgb_api.py`；新 `tests/workbench/test_controlled_scene_curves.py`、`test_controlled_scene_evidence.py` | 2b RGB/local track/C4a/composed＋2c 索引 → K1／C4b 新事件 adapter → curve_layer／evidence_lookup。重用 Claude K1 純模組與既有 physical integration，另加 adapter，不改舊 D18 guard／固定設定。依賴 #75 M1/M2 與 N1–N4 uncertainty／closed kinds／immutable refs、2a token 媒體及 2b/2c pins。保留未關聯基線、多解、identity UNCONFIRMED、physical UNKNOWN。O1–O6 已定案，實作須依 D62 封閉名稱與 wrapper；D56 CS-D 方向不算本批已完成。 |

各批工時在確認 schema、geometry authority、#75 複審後再估，本次不以未量測數字承諾時程。不凍結、不讀 GT、不合併，不把批次完成當 checkpoint 核准。

## 6. 首次交付 2078183 的實際產出 / Actual output（歷史）

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


## 7. 2026-10-20 複審修正與暫緩邊界

F1 已以單 run 完整性失敗隔離 bootstrap；F2 共用 reader 修正位於 #75 @8aff562，
本分支透過 170a5ef 帶入。新增測試用生成 PNG 做 chmod 000／0644 恢復，
另注入 EACCES／EMFILE／EIO 於 safe metadata、synced_frames 與既有媒體 grant；
均為 503，無 run 鎖定，恢復可重試。完整性錯誤仍整個 run 鎖閉，不降為 MISSING。
O8/O9 與 L1–L3 見 §2–§4；欄位／語意 hash 正規化對照 #81 §3.1 B2。

2b–2d **未開工**，不因本次修補而取得 O10 授權。以下僅是可分拆提案，待使用者確認：

- RGB-only 元件與 camera-local track：預定 controlled_scene_perception.py、
  configs/controlled_scene_perception_v1.json、test_controlled_scene_person.py。
  輸入僅為已 pin RGB、sampling／run／camera scope 與公開設定；不讀幾何、GT 或姿態模型。
  最多 1 格偵測缺口；explicit missing 或歧義中斷，不跨鏡頭、不確認身份。
  沒有合法投影時不能宣稱已驗 2.0 m/s 速度閘，相關 track／接地狀態保持 UNKNOWN。
- C4a 新 run ground_estimate adapter：預定 engineering/controlled_scene_contact.py、
  controlled_scene_person.py 與同一 focused test；只在光學 adapter／獨立合法支撐面及用途
  pins 可驗證時投影。先設計 hash／source/run/clock guard；缺少合法前置就 fail closed。
  這不授權用目前 NOT_EVALUATED 場景幾何判遮擋、建索引或作 K1 地圖。
- D56 後續 config 必須明列：v_max=2.0 m/s、軌跡身高支持 ≥5 格、全距 ≤0.06 m、
  WHOLE_TRACK、追蹤缺口 ≤1 格、heading 5 格窗、speed 錨點不鏈接且 Δt≤1 s。
  D61 外部視覺判斷固定 NOT_USED。上述完整感知／身高／組成尚未實作或執行。

契約 v1.2 等使用者轉交 SHA 後另確認，不把目前草案當已核准版本。


## 8. 本次修訂的實際產出 / Actual output

- Model / effort: Codex（GPT-6；effort UNKNOWN）。
- PR / commits: Draft #80；#75 @8aff562 以新 commit 170a5ef 帶入，
  後續 F1／O8／O9／L1–L3 commit SHA 以 PR 紀錄為準。
  工作在指定 backend checkout 的 codex/controlled-scene-real-v2-2a-review；
  正常 push 到 #80 原 head ref，不動資產 checkout 的本地分支或未追蹤檔案。
- Files changed: 本文件、scripts/check_controlled_rgb_playback.py、scripts/office_demo_backend.py、
  src/amidst/workbench/controlled_scene_rgb_api.py、service.py、
  tests/workbench/test_controlled_scene_rgb.py；另由 170a5ef 帶入 #75 六檔修正。
- Commands run and results: §6 相同四檔 focused pytest → **408 passed in 13.14s**；
  ruff 檢查本輪與帶入修正的九個 Python 檔 → All checks passed；
  git diff --check／git diff --cached --check 通過。
  首次 helper import 路徑錯誤造成 3 項 collection errors，修正後原測試 376 passed；
  補測後 408 passed。兩處測試行長 E501 已修正。
  bounded WSGI script 使用新 output 路徑：2 runs／21 RGB GET PASS。
- Artifacts: **LOCAL** /private/tmp/controlled-rgb-2a-review-check-20261020.json，
  SHA-256 `5bdafcebd5c5ee119da1b8088d7fa6a83db367ea93e8aef562448ca1ff116da4`。
  沒有覆寫首輪收據，也沒有保存 token 或建立媒體副本。
- Verified: F1 兩個順序的單 run failure／另一 run 播放、全部失敗 409、reason sanitization；
  F2 三種 errno × bootstrap／synced／media 的 503 與恢復、合成檔 chmod 恢復；
  O8 ref／語意 hash 跨 session／token 更新一致，camera／run／frame 不混用；
  O9 半微秒、負值及 run／grid 邊界；L1 具體原因碼、L2 自訂 assets root，
  L3 全 MISSING／OUT_OF_RANGE 的 READY 只表示請求處理完成。
- Not verified: 未跑全套／mypy／瀏覽器／listener／長時間播放；
  未全量讀 550 張、未解碼或評估定位／推論誤差，未驗獨立複審。
  未凍結、未讀 GT／private／acceptance、未改 source assets，未啟動 2b–2d。
- Deviations, UNKNOWN items and follow-ups: #75 用新 commit 移植，無 merge／rebase／force-push。
  failed run 不提供未能驗證的 sampling／camera／pin receipts，只保留最小故障列；
  F2 的暫時 I/O 仍走 503、不標完整性 FAILED。契約 v1.2 待使用者指定 SHA 後確認；
  §7 僅列 2b 分拆設計，實作須等使用者確認與相應合法前置。
