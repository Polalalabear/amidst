# 新受控 Demo：唯讀產出預算與後端重用準備

日期：2026-10-18（Asia/Taipei）。狀態：**唯讀盤點／估算完成；正式 A 包待確認，未建 `.blend`、未渲染、未修改後端或清理資產。**

使用者已決定採用[新場景提案](../agents/CONTROLLED_SCENE_2D_TO_3D_PROPOSAL_20261018.md)作為新 Demo，舊 Office 人形 run 不再反覆修正。舊分支與 PR 全部保留，不刪、不關。提案的固定提交為 **`59b8f5d91fe35812dfe0046c67709a519b46ed1e`**，純文件分支 `codex/office-demo-rehearsal-docs`。本文件供 Claude 的 `OFFICE_CONTROLLED_SCENE_V1` 與操作草圖作輸入，沒有另立已定案契約。

協調者建議的 B1（兩人錯開）／B2（交會）、3D 第一版接地區間、正式靜態 walkable 與 C7／K7 驗證角色，均已記入提案；具體 schema／門檻待 A 包確認。

## 1. 目前磁碟與估算依據

### 1.1 本次實測

- 本次快照可用 **12,064,919,552 bytes = 11.236 GiB**；背景程式會使數值變動，不是已保留容量。
- `df` 確認專案、Desktop、`/private/tmp` 都在 `/dev/disk3s5`。換到這些位置不會增加可用空間。
- `/Volumes` 本次只有 `Macintosh HD`，沒有確認到已掛載的外接資料磁碟。
- 只讀三份現有 `safe_inputs.json`，核對 300 張 PNG 的檔案大小，沒有解碼、轉檔或讀 GT：

| 現有樣本 | 張數／解析度 | PNG 平均 bytes／張 | RGB 合計 bytes | safe_inputs bytes |
| --- | --- | --- | --- | --- |
| Office person | 100／960×540 | 413,707.90 | 41,370,790 | 262,939 |
| Contact control | 100／960×540 | 417,058.03 | 41,705,803 | 110,542 |
| Legacy Office | 100／960×540 | 413,879.99 | 41,387,999 | 263,022 |

三組平均約 **0.80 bytes/pixel**。新建築、人形、材質與採樣尚不存在，不能把此壓縮率當保證。計算細節與未取整數字見[估算收據](CONTROLLED_DEMO_PREPARATION_20261018.json)。

### 1.2 事件張數與公式

暫定 A：3 鏡頭 × 10 s；B1：4 鏡頭 × 20 s；合計 **110 camera-seconds**。每段時間採 `[0, duration)`、固定幀率，不重複存結束點。若 A 包要求含結束點，七條 camera streams 合計另加 7 張。

| fps | A 張數 | B1 張數 | 合計 |
| --- | --- | --- | --- |
| 5 | 150 | 400 | 550 |
| 10 | 300 | 800 | 1,100 |
| 15 | 450 | 1,200 | 1,650 |
| 30 | 900 | 2,400 | 3,300 |

RGB24 未壓縮 bytes = 張數 × width × height × 3。PNG 規劃範圍用 **0.5–1.5 bytes/pixel**，JPEG 用 **0.08–0.30 bytes/pixel**；後兩者是明示的規劃假設，不是新場景實測、品質保證或格式上限。新場景若壓縮較差，必須重新估算；RGBA 增加 alpha、16-bit／EXR 都另算。

### 1.3 RGB 大小比較（A＋B1，單位 GiB）

每格為預算範圍，不包含 `.blend`、bundle／index、暫存、swap、預覽影片或重跑版本。

| 解析度 | PNG @5 fps | PNG @10 fps | PNG @15 fps | PNG @30 fps |
| --- | --- | --- | --- | --- |
| 640×360 | 0.059–0.177 | 0.118–0.354 | 0.177–0.531 | 0.354–1.062 |
| 960×540 | 0.133–0.398 | 0.266–0.797 | 0.398–1.195 | 0.797–2.390 |
| 1280×720 | 0.236–0.708 | 0.472–1.416 | 0.708–2.124 | 1.416–4.249 |
| 1920×1080 | 0.531–1.593 | 1.062–3.186 | 1.593–4.780 | 3.186–9.559 |

| 解析度 | JPEG @5 fps | JPEG @15 fps | JPEG @30 fps | RGB24 未壓縮 @30 fps |
| --- | --- | --- | --- | --- |
| 640×360 | 0.009–0.035 | 0.028–0.106 | 0.057–0.212 | 2.124 |
| 960×540 | 0.021–0.080 | 0.064–0.239 | 0.127–0.478 | 4.780 |
| 1280×720 | 0.038–0.142 | 0.113–0.425 | 0.227–0.850 | 8.497 |
| 1920×1080 | 0.085–0.319 | 0.255–0.956 | 0.510–1.912 | 19.119 |

JPEG 會改變 RGB 數值，對既有差分閾值、元件與接地估計不保證等價；不能把原 PNG 轉 JPEG 後沿用既有像素結果／hash。RGBA、16-bit PNG、EXR／depth／mask 都不是本次 RGB 預算。推論不能因方便改讀 renderer depth／mask／visibility。

**H.264 預覽大小**可直接按選定碼率估：110 s × bitrate / 8。若為 1／2／4／8／12 Mbit/s，影像本體約 **13.75／27.5／55／110／165 MB**（十進位），另計封裝／音訊；這是碼率算術，不是已編碼或保證可達的視覺品質。CRF 模式沒有固定大小，需另量測。影片可作衍生播放素材，不能讓目前逐張影像 consumer 自動改成 MP4，亦不能宣稱解碼後像素與 PNG 等價。

### 1.4 Bundle 與實際峰值預算

現有 safe bundle 本身只有 manifest／安全資料等 metadata，RGB 以來源路徑／hash 引用，不必再複製一份。新方案也建議 **一份 canonical RGB + metadata bundle**；若另做自包含 bundle，至少再加一份完整 RGB。ZIP 打包、檔案複製、暫存轉檔也可能在完成前占用第二份；不能把 PNG 可再壓縮當作必然節省。

| 項目 | 960×540／5 fps 的規劃額度 | 依據／限制 |
| --- | --- | --- |
| A＋B1 canonical RGB | 0.133–0.398 GiB | 上表，尚未產生。 |
| Manifest、安全 bundle、觀測／區間、靜態 map／index、精簡評估紀錄 | 0.05–0.20 GiB | 保留額度，不是實測；舊 D21 index 約 1.71 MiB、舊 C7 map 約 1.41 MiB，新網格大小另訂。 |
| 新 `.blend`、幾何匯出與設定 | 0.02–0.15 GiB | 假設程式生成小場景、少量材質、不嵌入大貼圖、不複製整個舊校園。 |
| 可選預覽影片／縮圖 | 0.02–0.06 GiB | 只作衍生播放，額外資產；不生成八份相同影片來湊版面。 |
| 一批 staging／衍生寫入餘裕 | 0.25–0.50 GiB | 不包含同時重跑一整套、打包雙份或 OS swap。 |

此小版本的資料／產製暫存合計約 **0.47–1.31 GiB**，建議先編列 **1.5 GiB 磁碟峰值額度**，且分批完成 A、B1。若改 1280×720／5 fps，先編列 2 GiB；更高規格按上表另加，不能套用小版本額度。B2 若也採 4 鏡頭 × 20 s，RGB 相對 A＋B1 另增加 `80/110 = 72.7%`；A＋B1＋B2 共 190 camera-seconds，5 fps 為 950 張。B2 的正式規格尚未確認，沒有把它算成已預算完成。

**建議給 A 包的取捨：**第一輪資料／幾何驗證採 960×540、5 fps、8-bit RGB PNG。此建議不等於人物像素足夠或影片流暢度通過；若 A 包要求更高人物解析度或 15／30 fps 播放，必須明列正式 RGB 頻率與推論採樣頻率，重算容量、記憶體與同步契約。把 5 fps 包成 30 fps 容器不會產生額外真實觀測。

### 1.5 記憶體／swap 與啟動餘裕

`perception_v2.py::produce_contact_v2` 現在會讀取單鏡頭整段 RGB arrays，再做 `np.stack` 與 median background；`contact_scene.py` 的品質對照也有整段載入。B1 的單一鏡頭：

- 960×540／5 fps／20 s：100 張，單份 uint8 RGB arrays 約 **148.3 MiB**。
- 1920×1080／30 fps／20 s：600 張，單份約 **3.48 GiB**；堆疊、暫存與其他程式另加，不能以影片檔很小推論 RAM／swap 也小。

沿用過去實驗「可用容量低於 8 GiB 即停止」的保守概念；先前紀錄曾在首張小 PNG 附近觀察到約 2 GiB swap 配置增加，不能保證新小場景重現同樣數字，也不能假定完全沒有 swap。**新增規劃建議**：1.5 GiB 產出額度＋2 GiB OS／swap 餘裕＋8 GiB 保留，開始前至少約 11.5 GiB，實務以 **12 GiB** 為小版本起跑目標；高規格另評估。這不是目前 launcher 已實作的 render gate。

本次約 11.24 GiB，尚低於此建議起跑目標；A 包也未確認，**本輪不開始渲染**。未啟動 Blender，CPU／GPU／實際渲染 RAM 與耗時仍 UNKNOWN。

## 2. 存放位置與清理建議

### 2.1 存放

若之後有現成外接 SSD，建議把新 canonical 資料放在其獨立資料根；本次未發現已掛載外接磁碟，不能把它計入現有容量。建議結構（占位設計，未建立）：

```text
<CONTROLLED_DATA_ROOT>/
  assets/controlled_scene_v1.blend
  runs/A/rgb/<camera_id>/...
  runs/A/safe_bundle/...
  runs/B1/rgb/<camera_id>/...
  runs/B1/safe_bundle/...
  private_evaluation/<run_id>/...  # 不進 safe bundle 或 media allowlist
  derived/<run_id>/...            # 可重建的預覽／縮圖／cache，逐項標記
```

程式／規格／精簡收據留 Git；原始 `.blend`、RGB、GT 不直接發布 Git。asset root／media allowlist 要縮到允許的 RGB 資料，不把整個資料根或 `private_evaluation` 暴露成可讀媒體。`OFFICE_ASSETS_REPO`／`OFFICE_EVIDENCE_REPO` 現有介面可參考，但新資料根語意與路徑驗證仍需改造，不能宣稱今天就能直接換任意外接目錄運作。

若只用內建磁碟，建議新建獨立版本化資料目錄（例如既有 `data/pilot` 下的新 controlled run）作 canonical 資產，安全 bundle 在對應 `data/engineering` 引用它；不要另外搬到 Desktop 或 `/private/tmp` 假裝釋出容量。不使用 symlink 繞過現有安全拒絕規則，不複製原校園 `.blend` 來建小場景。

### 2.2 可討論的清理順序（沒有執行）

1. 優先用「不複製 RGB、不預先產生多版解析度、不立即打 ZIP、不建新 environment／worktree」避免新增占用。
2. 只考慮已證明可重建且無 consumer 的新衍生預覽、縮圖、完成的 staging；先留 manifest／hash，再按精確路徑取得清理授權。失敗／未完成 run 在必要收據保存前不刪。
3. 本次 `/Users/polalabear/.cache/uv` 配置約 **341 MiB**；`/private/tmp/amidst-c4a-uv-cache` 約 12 KiB；`~/.npm/_cacache` 不存在。前者也不是保證可回收容量，且清除可能影響離線重建；目前沒有已證明可立即釋出數 GB 的快取方案。
4. 舊分支／PR 保留與資產保留是不同層次，但「新 Demo 不再用舊 run」也不授權刪除其 RGB／GT／`.blend`。本次量到舊 person `rendered` 目錄約 **40 MiB**，即使未來可退役也不會解決數 GB 餘裕問題。
5. 不清理 swap、原 Blender／校正／GT、舊 frozen、使用中的 services、Claude scratchpad、既有 venv／node_modules 或其他工作資料。任何未確認 consumer 的目錄都保留。

這些是建議，不是刪除指令或清理核准；本輪沒有移動、停止或刪除任何服務／資產。

## 3. 後端模組重用盤點

### 3.1 檢視基準

目前純文件分支較早，不把其 checkout 中的舊 C5 當最新功能。以本機 Git objects **唯讀 `git show`** 檢視以下固定提交：

- `4019a44f1dc22130e7b6013179ac86c899ca1200`：#53 的 C4a／D21 C5／C4b、loader、service schemas。
- `28f050a9c0472f33783ebfd1f15b92030d1dce44`：#63 K8a 預同步，K1／K5 pins 為 #58 `131869d`。
- `225f2461ec3b38b6855d8c6b26d4cc17cb77aaba`：#64 launcher／rehearsal-check。

這是保存版本的重用盤點，不是聲稱 PR 已合併或遠端 head 仍未變。沒有 checkout／merge 它們，沒有重跑舊 Office 推論或測試。

| 模組／檔案與符號 | 可重用、原則上不用改的核心 | 新 Demo 必須改造／補上的部分 |
| --- | --- | --- |
| C4a：`src/amidst/engineering/hybrid_contact.py` 的 `estimate_contact`、`_foot_segment`、`_height_segment`、`SourceClip`、`k1_endpoint_eligibility` | 校正射線與平面求交、區間輸出、來源 hash／資格 gate、已知幾何裁切介面。 | 新 source/run/尺寸先驗／相機／floor 綁定；正式 walkable 的安全 adapter；多樓層不能套單平面。3D 首版保留近／遠端及 constraints，不能只拿中點。既有 ±2 px 不是新場景準確度保證，也不因舊 REAR 結果調參。 |
| 感知與場景 adapter：`src/amidst/engineering/perception_v2.py`、`src/amidst/workbench/contact_scene.py` | RGB hash／尺寸驗證、元件／品質記錄、原始 MISSING 與 sibling estimates 的分離。 | v2 目前沒有跨時 local tracks（`_local_tracks=()`），且 `enable_reconstruction=not self._v2`；motion／association／physical 層為未物化。因此不能宣稱接上新版 `.blend` 就有多人 3D 回放。需補 RGB-only 局部追蹤／跨鏡頭候選與 interval-aware 人物 payload；不同人物不能用 GT actor ID 選 prior。 |
| C5 時間索引：`src/amidst/workbench/frame_retrieval.py::TimeFrameIndex` | 按相機排序與 bisect 時間窗查找，這個 metadata 核心不需因場景改寫。 | 初始化與新 schema adapter 要解耦「必須已有 `_ground_estimates` 第一筆」的假設；沒有可用定位時仍應能找到候選鏡頭。 |
| C5 靜態可見範圍：`scripts/export_floor_visibility.py`、`scripts/build_floor_visibility_index.py`、`src/amidst/geometry/floor_visibility_index.py` | 靜態 mesh／校正的來源綁定、D21 strict／suggestion 分離、偵測器四欄、UNKNOWN／不可偽造負證據的檢查。 | 新相機、正式 walkable／障礙 mesh、source-frame／floor／body policy／config 與 hash。現有 exporter 會排除 `annotation_only` 等 proxy；新正式幾何角色不可被誤排除，也不可反過來把舊 annotation proxy 升權。來源 ray/index 若需要產製，等 A 包確認後另做。 |
| C5 檢索：`FrameRetrievalIndex.query` 與 `service.py::FrameRetrievalRequest` | TIME_RANGE／HYPOTHESIS 回應、來源／frame-key 去重、frame outcomes、append-only conversion；SHA／role／path guard。 | 現有最多 4 鏡頭、20 s、64 returned frames、512 scanned records／query、5 s cooperative deadline。A、B1 的 3／4 鏡頭本身可落在 camera 限制內，但 B1 5 fps 全窗 400 records、10 fps 800 records：後者會超過 512。需分窗／分頁或新批次契約，不能靜默少回畫面。64 suggestions 不是同步影片完整 frames。 |
| C4b：`src/amidst/workbench/blind_hypothesis_integration.py::bind_hypotheses/reconstruct` | 封存 K1 回應、來源／設定 pins、evidence freshness、append-only、NONE／BASELINE／feedback 與 provenance 驗證概念。 | wrapper 綁定固定 `blind_interval` 兩端 ref／時間／相機，只接受指定兩鏡頭；任何區間內觀測都觸發 `D18_INTERVAL_CONTAINS_OBSERVATION`。不能直接服務全可見 A 或多人 B1。需要新事件／人物候選 adapter，把新流程與舊 D18 guard 分開保留。 |
| K1／K5 與幾何驗證介面 | 純假設／裁切／去重模組可依 A 包輸入格式重用；不必因換場景直接重寫演算法。 | 新 scene／map descriptor 與正式靜態 walkable 來源；C7／K7 作一致性驗證，不能拿舊 C7 當新地圖 authority。整張畫面有人時，不能把「沒看到特定人」當 whole-frame NO_DETECTION；B1／B2 負證據保持保守。這部分與 Claude owner 協調，不自行改其模組。 |
| Preset／bundle：`scripts/office_demo_backend.py::preset_specs/validate_bundle_files/load_scene` | catalog、optional preset 隔離、hash/source/run/clock 檢查、default 失敗停止、safe media 範圍驗證。 | 現有寫死 100 frames、5 Hz、`[0.0,9.8]`、hybrid config 路徑與部分輸出檢查；必須改成 A 包的 manifest／sampling／duration／camera 集合驗證。新 Demo 設為明確預設；缺新資料不能悄悄回舊 Office 當作成功。 |
| Launcher：`scripts/start_office_demo.py`、`start-office-demo.command` | 自有 PID/cwd/start identity、動態 port、metadata／served hash、鎖、來源改變拒絕重用、受限 stop、不另建環境。 | bundle/default 與新資料根；readiness 現有 `len(frames)==2`、人形 scene 字串、34 records／D18 區間等寫死項目。改從受信任 manifest 的情境驗收表取預期，更新 service fingerprint 與測試。 |
| Rehearsal：`scripts/office_rehearsal_check.py`（#64） | PASS／FAIL／UNKNOWN audit、exclusive output、拒絕資產／GT 輸出位置、不啟停服務、每項 hash 收據。 | `person_api:*`、Office binding key、固定 C5 freeze 檔名與 artifact 清單需改為新契約資料；增加候選鏡頭、A／B1、同步／區間／GT 隔離檢查。新 GT／asset root 也要列進輸出保護範圍。不是 59 PASS 歷史結果可直接移用。 |
| API 公共限制：`src/amidst/workbench/service.py` | session／role、嚴格 schema、來源與 media ref 查找。 | timeline／motion／frame query 現最多 4 相機；舊 FrameWallRequest 為 8–16 格診斷牆，不是新 1/2/4/8 同步視圖。8 格要有獨立顯示契約／有界 batching；不可只改前端格數而後端少送四台。 |

**重用不等於已驗收。** 新 source、actor representation、正式 walkable、候選鏡頭搜尋和人物關聯仍需新 fixture／focused checks；這次不執行。原 engine kernel 可保持，但 loader／wrapper／配置大多需改造，沒有「只換 pins 就全部不用改」的結論。

## 4. 新候選鏡頭 API：給 Claude A 包的欄位需求

這不是已實作 endpoint；建議名稱如 `POST /api/candidate_cameras`，名稱／schema／枚舉由 Claude 的 A 包定稿。它回答「哪些鏡頭值得查」，與「返回多少張建議影格」及「人物是否已確認經過」分開。

### 4.1 Request 建議欄位

| 欄位 | 用途／限制 |
| --- | --- |
| `schema_version`、`session_ref`、`scene_id` | 沿用 session／role 邊界；run／clock／source pins 由 server 已註冊 catalog 解析，不讓 client 改檔案路徑或 source hash。 |
| `target_region_ref`（必要，或 A 包明定的合法選區） | 使用正式靜態 region／portal／walkable ID。若支援多邊形選區，要指定 frame/floor/units，且由 server 驗證範圍；不能從 GT 取得目標 actor 位置。 |
| `time_range_s` | 有界、同 run／clock；明定端點與同步容差，不能無界掃描全場。 |
| `query_intent` | 例如「經過／進入／離開／周邊進出」。語意解析與 region 展開由模板或受限解析層負責，不預設恢復 Agent。 |
| `surrounding_policy_ref` 或受限的周邊範圍 | 進出口、鄰接區與時間擴展規則的版本；距離／速度／方向若使用，需事先宣告，不能讀情境腳本的答案。 |
| `camera_ids`（可選） | 使用者限制的 catalog 子集；不填代表受限 catalog 中可搜尋集合，不是只搜尋查詢前畫面上那幾台。 |
| `page_size`／`cursor` | 候選攝影機分頁及穩定排序；cursor 綁 query／scope／index 版本。 |
| `layout_capacity`（可選 UI 提示） | 1／2／4／8；**不改候選完整集合或排序語意**。當頁容量不能冒充候選總數。 |

不接收 `gt_actor_id`、renderer 路徑、已知跨鏡頭身份、私有 media 路徑或測試事件答案。自然語言原文即使保留，也不能成為任意檔案／全域搜尋指令。

### 4.2 Response 建議欄位

| 欄位 | 需要表達的內容 |
| --- | --- |
| `schema_version`、`query_id`、`status`、`reason` | 區分查詢可完成、部分／資料不可用與未知，不能空陣列一律解讀為沒人經過。 |
| `resolved_scope` | server 解析後的 scene/run/clock、時間窗、target region／floor／units、周邊 policy、source／map／camera catalog／index refs 與 hashes。 |
| `candidates[]` | 每台 `camera_id`／label、rank、可追溯 `reason_codes`、與目標／入口／出口的關係、相關區域 refs、建議時間窗。 |
| 候選的幾何依據 | footprint method／ref／hash、suggestion overlap 或 view relation、可見性／detectability 狀態與 UNKNOWN 原因。FOV／suggestion 相交只是候選理由，不自動授權負證據。 |
| 候選的影像證據 | 可選 sample frame／observation refs、該證據的時間與狀態、查找其他影格的安全 ref／token。不能把 GT actor 名稱當人物身份；沒有偵測仍可保留幾何上相關的鏡頭。 |
| `availability`／`unavailable_reason` | 每鏡頭是否有該時段 RGB／校正／index、缺影格時間；不能默默省略缺資料鏡頭。 |
| `candidates_total`、`returned_count`、`next_cursor` | 分頁／顯示資訊，總候選和目前畫面格數分開。 |
| `candidate_set_complete`、`truncated`、`unknown_camera_ids` | 在宣告 catalog／filter／預算內是否完整檢視。metadata 缺失或超 budget 時不能宣稱「所有周邊鏡頭已找齊」。 |
| `recommended_camera_ids`／layout 建議（可選） | 可先顯示哪幾台；候選不足不複製湊格，超八台保留可切頁的完整集合。A 與 B1 不跨 run 混畫面來湊八格。 |
| `stats` | catalog／index／frame 實際讀取量、budget／deadline、latency；明定 hash 排除 timing。 |
| `provenance`、結果 hash | producer/version/config pins、source/run/clock/hash 與 `gt_read=false`；query scope／結果 hash 可封存，不能包含 session secret 或私有路徑。 |

### 4.3 與重現／播放介面的必要銜接

候選鏡頭 API 不回傳真值人物位置，也不直接把曲線生成包進一次全場搜尋。後續 timeline／觀測／重現 response 至少要能攜帶：

- 安全 `frame_ref`、timestamp、camera、校正 ref／hash，以及 frame 是否真實可用。
- RGB-derived observation／local track refs、跨鏡頭候選 refs；不是 Blender actor ID。
- `ground_estimate` 的 POINT／SEGMENT／UNKNOWN、basis、near/far、constraints、quality、provenance 與 output hash。3D 不能要求把 SEGMENT 轉成中點才能顯示。
- 同步規則／採樣率／floor 與座標系。C4a 的可用性與身份、物理可行性是不同欄位。
- 物理曲線的 evidence state、來源觀測 refs、缺口／UNKNOWN 與候選組，不用綠球作必填資料。

## 5. A 包確認前的具體待決項目

1. A／B1 是否確定為 3×10 s、4×20 s；B2 是否另外排程，先不產出？
2. 正式 RGB 解析度／fps 與感知採樣率；是否接受先 5 fps 的資料驗證，流暢播放另做？
3. 每段目標的人體像素、接地可見／遮擋、跨鏡頭重疊與同步容差，能否在生成前形成驗收表？
4. 正式 static walkable／牆／門／stair schema 與 hash；哪些核對由 C7/K7 驗證，如何避免舊 proxy 規則誤排除新幾何？
5. 候選鏡頭 endpoint、候選完整性／分頁／budget；8 格 UI 與目前最多 4 相機 API 的銜接方式。
6. 多人 RGB-only tracking／關聯的模組責任與最小契約；B1 不交會通過不能冒充 B2 交會通過。
7. 接地區間的人物表示法、曲線虛線語意、定位／身份／物理 UNKNOWN 的互動。
8. 可用容量目標、產出 cap、分批檢查與 cache／記憶體上限；本機空間不足時是否使用既有外接資料根或另行授權清理。

## 實際產出 / Actual output

- Model / effort: UNKNOWN
- PR / commits: 純文件分支 `codex/office-demo-rehearsal-docs`；提案提交 `59b8f5d91fe35812dfe0046c67709a519b46ed1e`。本盤點的提交 SHA 見交接回覆；不新建／刪除／關閉舊 PR，也不標記既有任務已完成。
- Files changed: 本文件、`CONTROLLED_DEMO_PREPARATION_20261018.json` 與文件索引；提案與索引另有上述獨立提交。
- Commands run and results: `git status`／`git show` 固定 snapshots；`df -h/-k`、`ls -la /Volumes`、針對已知樣本／cache 的 `du -sk`；既有 offline uv Python 讀三份 safe inputs＋stat 300 張影像，大小全部與 manifest 相符。4 種解析度×4 種 fps 的 16 列 PNG/JPEG/RGB24 公式、B2 950 張算術、固定 Git objects、7 個本機相對連結核對 PASS；`git diff --check` 與新增文件空白檢查無錯誤。沒有執行程式測試。
- Artifacts: 本估算 JSON／Markdown；JSON SHA-256 `32bf4f3ed52d0e49e4a45034597c19e430c6ece0e7a49bf7d7809b3ca9fa2d0c`。LOCAL `/private/tmp/CONTROLLED_DEMO_BUDGET_20261018.json` 是同一精簡估算收據。沒有新 `.blend`／RGB／GT／render output。
- Verified: 檔案大小、同磁碟位置、已掛載 volumes 快照、固定版本中的 hard-coded 限制與可重用介面；最新使用者方向已記錄。
- Not verified: 新場景壓縮率／編碼畫質、實際 Blender RAM／swap／耗時、A 包、任意新資料根可直接載入、多人重現／新的 8 格同步、任何新規格功能或 benchmark。沒有跑測試／推論／渲染／服務。
- Deviations, UNKNOWN items and follow-ups: PNG/JPEG 範圍與 12 GiB 起跑目標為明示規劃假設；舊磁碟保護參考不冒稱已實作新 gate。部分歷史檔案只存在其他 Git snapshots，本次以固定 objects 讀取，不複製整個 code checkout。等 A 包確認後再談程式、場景產製與清理授權。
