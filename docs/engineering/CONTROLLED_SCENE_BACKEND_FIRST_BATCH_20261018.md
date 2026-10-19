# 受控場景後端第一批：靜態路由、safe資料層與SYNTHETIC骨架

2026-10-18（Asia/Taipei）。base `claude/office-demo-visualization` @ `f481fe0e300198235bd9599ff0091fd33d0381a5`；分支`codex/controlled-scene-backend`。任務1文件先以`6f6c8003cfb34fed8221820350c52f793aca8355` normal push並在[#68](https://github.com/Polalalabear/amidst/issues/68#issuecomment-6248264359)回報，才開始本批。此分支不包含任務1文件commit，沒有合併／rebase／force-push或動main。

本批不需要blend，不建／開blend、不啟動Blender、不渲染、不讀GT／真實影像或原資產。沒有改C4a接地估計器、D18 guard、launcher預設入口（R7）或Claude前端檔案。所有fixture為手寫SYNTHETIC結構，不是新受控場景資料或RGB推論結果。

## 1. 可交付範圍與尚未連接的部分

| 需求 | 實作 | 限制 |
| --- | --- | --- |
| R1／R2 | `controlled_scene_static.py`逐檔URL map，`/workbench-v2/`及設計中v2檔案；`/workbench/`僅六個純模組 | 無目錄、glob或test檔；`app.mjs`／`scene.mjs`不在新legacy前綴白名單。舊`/app.mjs`仍沿舊入口提供 |
| R3 | five three lines模組、四個字型與兩份OFL路由 | 未複製／下載vendor或字型。`Application(vendor_root=…)`可重用既有依賴；Office factory指向evidence checkout的three，launcher預設仍舊版 |
| R5 | 五端點完整性錯誤HTTP409，統一`error_class/reason` | 見契約§2.3.1提案；不傳tile／geometry／token，不把hash／source／pin／uncertainty錯誤降MISSING |
| R6 | 顯式fixture模式、獨立v2 bootstrap與成功回應data_origin | legacy bootstrap不混入fixture場景；只在nested controlled_scene_bootstrap描述另入口 |
| R8 | 白名單外、traversal、encoded traversal、symlink／symlink ancestor、private／assets／review_only拒絕測試 | 實際瀏覽器未跑；WSGI in-process測試，不開listener |
| 資料層 | `load_safe_run`、`adapt_calibration`、rgb_index／runtime_profile讀取；manifest／source／config／geometry／camera binding／RGB hash檢查 | 僅資料載入／完整性，非C7／K7、footprint／C5索引建置或科學readiness。沒有啟用任何真實run |
| R4 | 五端點SYNTHETIC骨架、scope／session guard、D45 uncertainty必填 | 真實消費adapter、media token、C5排名、C4a及K1未接；不假冒完成它們 |

`f481fe0`尚無#65契約檔、#71 player-grid／fixture或#72 v2頁面。故本批從#65 @2643771物化契約工作副本，保留核准原文（歷史狀態字句），**只新增§2.3.1與§6.0提案**；缺少本地引用的Claude文件改連固定版本GitHub。不宣告重新核准CS-A。#71／#72待它們自己的PR進來，沒有cherry-pick／修改Claude檔案。

## 2. 啟動與前端接法（命令提供給後續任務，本輪未啟動）

```sh
uv run python scripts/controlled_scene_backend.py --fixture --port 0 \
  --vendor-root .local-worktrees/phase1-finalization/frontend/workbench/node_modules/three
```

使用既有環境執行；不要為此安裝依賴／建venv。CLI要求顯式`--fixture`、動態127.0.0.1 port，只列fixture URL，不開瀏覽器、不叫舊launcher或停其他服務。它的temporary SQLite是空的local demo session state，沒有真實場景／GT。UI檔不存在時精確路由回404 `ASSET_NOT_MATERIALIZED`，不能把骨架server啟動當v2 READY。

1. v2讀`GET /api/bootstrap?surface=workbench-v2`：取得`data_origin`、scene／run／camera catalog、sampling及`real_run_support: NOT_IMPLEMENTED`。未啟fixture時UNCONFIGURED，不fallback。正常`GET /api/bootstrap`保留legacy scenes／入口，另加`data_origin: LEGACY_RUNTIME`與nested `controlled_scene_bootstrap`，legacy payload不混fixture圖層。
2. 仍用`POST /api/session`取得local session；fixture模式server才給該scene scope，不因UI研究視角取消session guard。五請求均帶scene_id／run_id／session_ref與精確schema_version；不得帶自訂source pin、actor、route或private locator。
3. fixture scene=`controlled-l-corridor`，run=`fixture-controlled-5fps-v1-r001`，camera=`FIX_CAM_01`–`04`，5fps／[0,20)s。它與未物化的真實`ctrl-lcorr-…` run分開；真實run ID發給fixture API會409，不自動換成fixture。
4. request schema=`controlled-scene.<action-kebab>-request.v1`。candidate需要target_region_ref=`AREA_FIXTURE`或floor/frame/unit合法polygon二選一、time_range_s、PASS_THROUGH／ENTER_EXIT、surrounding_policy_ref=`fixture-surround-policy-v1`、page_size、layout_capacity與可選camera_ids/cursor；person／curve用time_range_s，curve可加t_s；synced用t_s／camera_ids（最多8）；evidence用pick（layer／ref／result_sha256／segment_index／t_click_s）。
5. candidate骨架沒有visibility index，所有候選UNKNOWN，整體UNKNOWN而非READY；分頁游標綁query／fixture pin／session，偵測數不排序。synced按Fraction有理grid取LATEST_AT_OR_BEFORE_EXPECTED_GRID，缺格不回退、age與clock分開；本批**沒有任何真實／替代影像**，故tile MISSING或OUT_OF_RANGE，`media_tokens_issued=0`。
6. person示範UNKNOWN ground estimate與UNCONFIRMED身份，不放人形；curve示範INFERRED_HYPOTHESIS範圍帶與未關聯基線，不當測量／身份。time_range只篩選結果，不重編ref；evidence要result pin，未物化support不發跳轉、不捏造來源影像。
7. 五端點成功回應均有resolved_scope、provenance.gt_read=false、data_origin、output_sha256、identity_verdict／agent_used。`output_sha256`排除自身，按registry canonical JSON；固定payload可重現。409只含error，前端必須清空／遮住全部舊tile與3D geometry，不能當MISSING；503必要技術輸入不可讀亦不留成功資料。

### 2.1 Claude前端配合清單

- 精確檔名白名單見`controlled_scene_static.V2_FILES`；新增或改檔名要同步後端map。尚無前端檔案是404，不是本批漏開目錄。#71五份synced_frames fixture URL已逐一預留，不發`*.test.mjs`或未知JSON。
- 字型檔名協調為`fonts/IBMPlexSans-Regular.woff2`、`IBMPlexSansCondensed-SemiBold.woff2`、`IBMPlexMono-Regular.woff2`、`NotoSansTC-Regular.woff2`；OFL文字為`OFL-IBMPlex.txt`／`OFL-NotoSansTC.txt`。實體打包／授權由Claude前端交付；若需要其他weight或subset，每檔再加明確白名單，不能glob。
- three importmap：`three`→`/vendor/three.module.js`，lines可用`/vendor/examples/jsm/lines/Line2.js`等五檔；相對import sibling閉包仍在同一白名單。vendor_root讀共用安裝，不複製node_modules。
- fixture 2D本批只有metadata／MISSING；#71有READY metadata的靜態fixture也沒有真實media。不要將frame_ref直接當URL或套舊`/api/media`；真正token化media adapter待真實run入口另補。
- person／curve缺uncertainty必須阻擋（§6.0提案），UNKNOWN誤差界不得顯示0；Demo須常駐「設計估計；實際位置與接地誤差未量測」，不要將heuristic bounds說成機率／準確度。
- v2瀏覽器驗收與前端資產未完成前，不做R7或宣告v2可展示。D44／C4a v1.1另由Claude起草、Codex確認後才接。

## 3. 資料層wire補充與邊界

`RunRegistration(run_root, manifest_sha256, scene_id, run_id, source_sha256)`由server設定，不來自API body。`load_safe_run`只開`safe_bundle/manifest.json`及它逐項pin的safe JSON；沒有glob、`docs/`掃描、private import或source blend讀取。json拒絕重複key、NaN／Infinity與overflow。路徑逐層O_NOFOLLOW、只讀regular file、拒絕絕對／..／encoded／symlink祖先；讀取上限16MiB是工程保護，非場景品質門檻。

本批具體manifest wire採`schema_version: controlled-scene.manifest.v1`、scene/version/run/clock/source、sampling、config_pins、allowlist、data_origin。allowlist為`{kind:{path,file_sha256}}`，必要kind為scene_static、cameras、event_query、rgb_index、runtime_profile，可另列`geometry:<id>`；路徑僅safe_bundle下一層JSON。必要檔名按kind固定，query准許`event_A.query.json`／`event_B1.query.json`／通用`event_query.json`；geometry為`<id>.geometry.json`（單一幾何可用`geometry.json`）。即使private manifest被錯寫在safe_bundle，也不准以cameras等alias開啟它。`config_pins`必須含body_prior_sha256／detector_config_sha256，由manifest pin一起綁定；實際config adapter另接，不把hash格式合法當人體政策已通過。

光學cameras[]為契約§3.7全部欄位及`calibration_sha256`，canonical光學hash**不含clock**；run_bindings[]另有binding_sha256、run／camera／clock／[0,duration)有效範圍。adapter明確挑選舊Camera schema欄位，保留其他光學metadata，核對rigid matrix／det=1，不轉置、不改尺度、不硬編Office地板。safe floor／geometry引用用途核准必須存在且有pins；只是結構與完整性，不自造遮擋／可走authority。

`rgb_index`採schema_version/run_id/clock_id/records[]/missing[]；expected grid由safe manifest sampling推導，每camera每index必須有record或明確missing reason。record固定camera_id/frame_index/timestamp_s/rgb_ref/file_sha256；missing固定camera_id/frame_index/timestamp_s/reason:RGB_RECORD_ABSENT。canonical rgb_ref=`rgb/<camera>/frame_<index:06d>.png`，實體不存在才MISSING；bytes hash不符則DataIntegrityError。這輪測試僅用任意SYNTHETIC文字代替bytes，不解碼影像。

`runtime_profile`採schema_version/run_id/clock_id/sampling_version/camera_ids/required_inputs/api_available，只能是技術期望，不得含角色／盲窗／配對答案。必要metadata／索引缺失拋RequiredInputUnavailable，不產READY。真正runtime readiness／geometry評估與實際C5索引尚未接，**safe load成功不是候選READY或CS-B通過**。

離線`controlled_scene_evaluation.load_private_manifest_for_frozen_evaluation`在正式service import graph之外，先驗呼叫者提供的frozen output bytes hash，再讀明確private manifest並驗pin；不跟隨其GT entries、不提供HTTP入口。這不是本輪讀真實private資料或授權凍結。後續評估呼叫者須持有已授權且source/run綁定的凍結收據，不能把本函式當授權代理。

## 4. 實際產出 / Actual output

- Model / effort: Codex；精確model／effort UNKNOWN。
- PR / commits: codex/controlled-scene-backend，Draft PR／SHA見交接留言；base固定f481fe0，未合併。
- Files changed: service.py、新增controlled_scene_{api,data,static,evaluation}.py、scripts/controlled_scene_backend.py、Office backend factory的vendor root、兩個focused test檔、本交接、契約工作副本及docs/README索引。
- Commands run and results: 既有phase1環境經uv執行`python -m pytest tests/workbench/test_controlled_scene_data.py tests/workbench/test_controlled_scene_service.py tests/workbench/test_service.py -o addopts='' -q`：**189 passed in 2.83s**；本輪九個Python檔focused `ruff check`：All checks passed；`git diff --check`通過。完整環境／命令見PR實際產出；未跑全套、未啟動服務／瀏覽器。
- Artifacts: code／docs／手寫SYNTHETIC payload；無blend、GT、RGB、影片、run bundle或審查副本。hash見PR。
- Verified: 合成safe資料層完整性、光學／clock分離、缺索引與hash區別、session／scene／run、五端點409形狀與D45、逐檔路由／負向路徑；全部工程fixture證據。
- Not verified: 真實run、實際校正／C4a／C5／K1、渲染／RGB、人形重現、API視覺模型、瀏覽器與font／three實際載入、v2整體驗收。
- Deviations, UNKNOWN items and follow-ups: approved契約尚未在base故物化原文再加提案；前端檔案尚未materialize，已列精確接法。真實run與media／C4a未接，不以fixture或safe load冒稱完成。R7明確延後；#68仍待Claude複核／使用者生成授權。

## 5. D57 loader 修訂（2026-10-19）

§1–4是首批`8bc5118`的歷史紀錄，包含當時的暫定wire與待決事項；不代表D56–D58後的契約已確認。這次只完成D57，M1–M6仍待後續修訂。#77 validator與D58容差由Claude處理，本分支沒有修改它們。

`controlled_scene_data.adapt_rgb_index(raw, expected_file_sha256=...)`是純函式入口，`load_safe_run`在manifest允許且逐檔驗hash後使用它。adapter名稱`controlled-scene.rgb-index-adapter`、版本`d57-v1`；只在記憶體把舊`frames[]`改成`records[]`，其餘D55 metadata保留並繼續驗scene/source/run/clock/sampling/grid。正式`records[]`走原manifest pin驗證；D55額外pin清單只授權legacy `frames[]`，不會阻擋其他正常有pin的正式records索引。

- legacy schema必須精確為`controlled-scene.rgb-index.v1`；實際bytes SHA必須在server-owned清單，且對上該run。清單只有A `9e43237e9c9ac9ea4f2bc97f65e49103a0ec3946b1b555b9d7fbf59850e97d47`、B1 `a5392a6fc5b51257adb82827df376f42290690cbdb52160888eb241f256ecc39`；request／manifest不能新增pin。
- 雙鍵（即使其中一個空陣列）、無鍵、未知版本、未核准legacy hash、manifest hash不符或run綁定不符，全部`DataIntegrityError`，不降為MISSING。沒有`frames ?? records`或空陣列fallback。
- `SafeRun.input_adapter_receipts`保存adapter名稱／版本、來源file SHA、來源schema／collection、target collection、是否轉換及normalized content hash。loader不自動寫檔，不改manifest／原index；離線工具可直接重用同一函式並把receipt納入報告。

### 實際產出 / Actual output

- Model / effort: Codex；精確model／effort UNKNOWN。
- PR / commits: Draft #75，`codex/controlled-scene-backend`，本次parent `8bc51180fd35a07dc375df871dce1843791dff2e`；SHA見PR修訂留言。沒有merge／rebase／force-push，main與整合分支未動。
- Files changed: `src/amidst/workbench/controlled_scene_data.py`、`tests/workbench/test_controlled_scene_data.py`、本交接文件；兩份LOCAL ignored adapter receipt。未改契約、validator、容差、原資產、索引或前端。
- Commands run and results: `PYTHONPATH=src UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline --python /Users/polalabear/Developer/amidst-claude/.venv/bin/python python -m pytest tests/workbench/test_controlled_scene_data.py -o addopts='' -q` → **52 passed in 0.35s**，含13個D57新增案例；同uv前綴執行既有venv的`ruff check src/amidst/workbench/controlled_scene_data.py tests/workbench/test_controlled_scene_data.py --output-format concise` → All checks passed；`git diff --check`通過。同uv／PYTHONPATH執行LOCAL `/private/tmp/d57_verify_real.py` → A150／B1 400 records，只讀兩份已pin safe索引並核對原檔未變。
- Artifacts: LOCAL `data/pilot/controlled_scene_v1/runs/ctrl-lcorr-s1-a-5fps-v1-r001/acceptance/d57_loader_adapter_receipt.json` SHA `2b3bc129e89734339cd134b27e6e2b5da83f6b267e690a82694be4d644dd7bbc`；B1對應run同檔名 SHA `9c500c9f470a40e5f42cfc27e683d090850eb27bdb54523631399facbf879f6d`。兩份收據都標`RGB_INDEX_ADAPTER_ONLY`、`formal_load_safe_run_executed:false`、`runtime_ready:false`。normalized content hash分別`aca7f4000c5903021c3c567aa9899f6aa256c5f35fc2b2b9af439f816c7ace9b`、`6da2ae9ab1cb9d8446d099ec8b06bf25c09aef9d5e2d30366048c550f5c54632`；不是原檔file hash。
- Verified: focused tests核對pin合格、不符、雙鍵、無鍵、exact schema／run／source／sampling／grid、native records保持正常、in-memory轉換與receipt來源hash；測試只用SYNTHETIC文字，合格legacy測試只在test monkeypatch清單加入合成hash，production清單有獨立精確值斷言。真實A／B1只在adapter層讀safe JSON，550筆轉換成功，原索引bytes／SHA未改；沒有讀media或private。
- Not verified: 未對真實完整bundle呼叫`load_safe_run`、未啟動HTTP或做runtime readiness／CS-B驗收；未凍結、未讀GT／影像、未合併；未重跑#77。M1–M6尚未處理，首批不確定度schema等仍為待修狀態。
- Deviations, UNKNOWN items and follow-ups: `460e030`中§1、§2.1／2.2、§3.0–3.3、§3.6／3.7及§7的RGB-only／hash區分／時間證據／用途核准／光學clock分離／GT隔離原則已預核對，沒有新增異議；不把它當新版逐段diff確認。正式v1.1確認以使用者轉交的新SHA為準，D56門檻、D57／D58條文及M1／M3仍待新版核對。即使adapter成功，也不修補其他manifest／geometry授權／runtime缺項或宣告READY。
