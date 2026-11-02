> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# Blender 相機畫面檢索 / Blender camera frame retrieval

本文件記錄2026-10-11基底檢索checkpoint；其影片DEFERRED為當時狀態。
2026-10-12已完成三站物理曲線與診斷回放，最新資料流／限制見
[Blender motion reconstruction](BLENDER_MOTION_RECONSTRUCTION.md)。
This document preserves the October 11 checkpoint. Curves and diagnostic replay were added
on October 12; follow the motion document for the current scope and evidence.

## 2026-10-14 現行入口與歷史範圍

現行操作見[九分鐘本機示範](DEMO_V1.md)。本頁的影格counts、Top-K、端口、2969項Python及
68次HTTP收據均屬2026-10-11 checkpoint，不重新宣稱為當前驗證。歷史prototype已交付；
Office revision20、Classroom101 revision15，共35筆本機人工差異及核准後重跑已有紀錄，
Auditorium尚未核對，38個物理檢查仍為UNKNOWN。當前來源與人工權限見
[Blender來源核對](BLENDER_PHYSICAL_HUMAN_REVIEW.md)。

Phase2暫估約50%，05維持baseline，11品質仍為`QUALITY_GATE_NOT_MET`。R2完整48題常規
12／40（中文7／20、英文5／20），安全邊界8／8但乾淨拒絕僅2／8。已凍結R3 context的
3736項工程檢查及68項隔離HTTP／PG守門通過，後者0次真實模型；一次current v4實際demo
失敗另存，schema／提示私有候選尚未套用，R3的48題重播未開始。舊v2／v3的literal驗證
可唯讀查看，需求完成度NOT_CHECKED；同源核對不提升current語意品質。詳見
[05／11修正](PHASE2_LOCAL_REPAIR_0511.md)，不把Blender畫面檢索當作模型驗收。

本階段接入原 `school_v3.blend` 相機的既有 RGB 序列與來源模型，使用基底演算法查詢、
量測、投影及 Top-K 畫面選取。正常查詢不經 Agent，不產生事件還原影片。
原 `.blend` 不修改、不複製，不啟動實體攝影機串流。

## 來源與替代資料

| 層級 | 實際使用的資料 | 替代與限制 |
| --- | --- | --- |
| 影像來源 | 既有 multisite pilot 的 Blender camera RGB；每情況 2 鏡頭 × 50 張，960×540、5 Hz、0–9.8 秒 | 灰色建築為來源幾何；橙色目標與活動是替代模擬，不是真實人物 |
| 相機與模型 | 原來源的 camera pose／intrinsics，以及同 Scene／frame 220／subframe 0 的 evaluated mesh | 顯示為局部裁切的 PARTIAL source context；預設平滑材質只影響顯示 |
| 像素量測 | 從上述 PNG 重算 temporal median 差分、connected components、bbox、contact pixel、local tracks | 簡單元件偵測不是人物辨識；保留缺失、合併與局部 track 斷裂 |
| 投影 | 原相機校正、核准尺度 0.0247 m/BU、來源綁定的 1F floor plane | 接地像素與地面交點有不確定性；不證明整場可行走、遮擋或碰撞核准 |
| 狀態與檢索 | 本次像素量測、投影與 camera/time 索引的安全快照 | 不使用既有 observations、軌跡答案、GT、visibility、depth 或 image diagnostics |
| 判斷與 Top-K | 固定基底排序及已選鏡頭／時間範圍 | 行走、跑步、出入為使用者意圖；人物與行為仍未確認，沒有 Agent 決策 |
| Graph／修改歷史測試 | 另建獨立 E0 fixture，實際測已有 Graph／reconstruction 與 delta history 接口 | 明標 SUBSTITUTE，source/run/clock 與 Blender 情況分開，不回填其結果 |
| 事件曲線與影片 | 後續使用可核對的量測、投影、時間與候選來源 | 本階段 DEFERRED，未把 Top-K 靜態畫面稱為事件還原影片 |

三組情況為 `office`、`classroom101`、`auditorium`。它們共用相同原模型 hash，但有
獨立模擬 run 與影像序列。Office／Auditorium 的同名 FRONT／REAR 相機不能把同時間
影格合併成同一筆資料；每個 opaque frame reference 都綁定 site/run。

原模型 SHA-256 為
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`。
相機的歷史 native BU 平移與 clip distances 顯式乘 0.0247，像素 intrinsics 不縮放；
不回寫歷史 calibration。1F 平面 Z 為 `0.4959475898742676` m，
不使用舊 diagnostic landmark 的 Z75 平面作接地面。

PNG 原檔含 provenance text chunks。服務只剝除 `tEXt/iTXt/zTXt`，保留 IHDR／IDAT
與原像素；原始 hash 與 served hash 分開核對，不修改原 PNG。Private path 與模擬
trajectory identifier 不會隨 public media 或 JSON 輸出。舊 HR02 camera still 與 motion
diagnostic PNG 保留在歷史展示，沒有冒充這組未標註 RGB。

## 工作台操作與實際接口

在本次動態埠工作台選擇 Blender 預設情況。主畫面顯示平滑來源模型與該情況的相機
影像；選取鏡頭、時間範圍、目標時間與 Top-K，執行基底畫面檢索。
結果先以訊息列出鏡頭、來源時間、排序原因、像素／投影狀態與來源種類，並可查看原圖。
Canvas、視角及完整解碼影格保留，晚到回應不能覆蓋新的情況或未送出的輸入。

`POST /api/frame_query` 使用 server-owned session/scene，例如：

```json
{
  "session_ref": "<server-issued-session>",
  "scene_id": "blender-office",
  "camera_ids": ["CAM_1F_AUDITORIUM_FRONT", "CAM_1F_AUDITORIUM_REAR"],
  "start": 0,
  "end": 9.8,
  "target_timestamp": 5,
  "top_k": 3,
  "behavior_intent": "walking"
}
```

Response 的 provider 為 `LOCAL_DETERMINISTIC_BASELINE`、`agent_used=false`；
`items` 每筆含 rank、camera/time、frame/media reference、bbox/contact、projection status、
world point（存在時）、rank key/reasons 與原始影像 hash。行為保持 `UNKNOWN`、身分保持
`UNCONFIRMED`。內部 refs 用於取圖與追蹤，正常畫面不展示事件 ID。

基底排序先取每個選定鏡頭的最佳畫面，再從其餘限定範圍補足。鏡頭內依可靠像素元件、
有效地面投影、距目標時間、來源 timestamp、camera/ref 的穩定順序比較。
這是明列的「鏡頭多樣性＋時間」基準，score 不是機率，不宣稱語意辨識或身分準確率。

匯入時從 RGB 建立一次特徵索引；query 以 camera/time bisect 讀有限資料，不再讀圖片
或全域資料。上限為 4 鏡頭、10 秒、5 個結果；未知／重複鏡頭、非法數值與越界 budget
會拒絕。沒有合法像素量測時回 `NO_RESULT`；缺圖或 hash mismatch 明列狀態，不以另一
情況的影像補缺。相機、run、來源或輸入快照失配會拒絕續用。

`scene/query/timeline/media` 重用工作台的角色與場景邊界。Blender 情況禁止
`semantic_presets/navigation_guide/agent_decision`，也沒有偽造 canonical events。
這些資料只提供基底演算法與顯示，不擴張 Agent allowlist。

## 本次實際輸入、輸出與資料流

以下 counts 來自2026-10-11 checkpoint的8016 HTTP與RGB重算，不是歷史observation或GT counts。

| 情況 | 實際 RGB 輸入 | 重算像素量測／局部 tracks | 有效地面投影／失敗 | 顯示 mesh 三角形 |
| --- | --- | --- | --- | --- |
| Office | 100 PNG、41,387,999 bytes | 31／3 | 31／0 | 1,662 |
| Classroom 101 | 100 PNG、48,379,960 bytes | 70／6 | 70／0 | 542 |
| Auditorium | 100 PNG、41,488,232 bytes | 91／10 | 82／9 | 318 |

Office 有 70 個影格沒有量測；Classroom 101 的量測影格全部含歧義；Auditorium 的
9 個投影失敗保留原狀。這些是基底演算法的輸出，不能用 counts 當成準確率。

實際交流依序為：

1. 唯讀來源抽取器 → RGB producer：只傳 camera/time、960×540 影像 identity/hash、
   source/run/clock 與校正。來源 dataset 內的 observations／trajectory／GT 不傳給 producer。
2. RGB producer → 投影：傳 camera/time、bbox/contact pixel、measurement status、
   local track 與 uncertainty；搭配 source-bound camera matrix／intrinsics、尺度及 floor plane。
3. 投影 → 安全狀態快照：傳 world position 或明確失敗、原影格／量測 refs 與來源 hashes；
   寫到隔離 JSON 再 reopen，核對順序／refs／content hash，不產生已確認事件。
4. 快照 → camera/time 索引 → 基底 Top-K：預先建立 features；query 僅給預設鏡頭、
   0–9.8 秒範圍、目標 5 秒、K=3、walking 意圖。每組本次 query 讀 100 筆索引記錄、
   2 次 camera lookup、0 個 PNG／0 bytes，沒有全域掃描或 Agent 呼叫。
5. Top-K → 工作台：傳排名／理由、camera/time、pixel／projection 狀態、source types
   與受 session/scene 控制的 media refs；取圖時只移除文字 metadata，像素不變。
6. Graph gap／delta history 分別使用獨立 E0 假資料：102 張程序 RGB → 14 observations
   → 4 gaps；另一文件只改 1 個 object 的 label，發布 v1 delta 後 reopen/replay 一致。
   兩個替代端口不把自己的事件或修改套進 Blender run，故可獨立測試且不擋影像檢索層。

本次「目標 5 秒、完整範圍、兩鏡頭、K=3」的實際結果：

| 情況 | Top 1 | Top 2 | Top 3 |
| --- | --- | --- | --- |
| Office | AUDITORIUM_FRONT 4.4 s | AUDITORIUM_REAR 8.6 s | AUDITORIUM_REAR 8.8 s |
| Classroom 101 | CLASS101 5.0 s | CLASS101 4.8 s | CLASS101 4.6 s |
| Auditorium | AUDITORIUM_FRONT 5.0 s | AUDITORIUM_REAR 5.0 s | AUDITORIUM_FRONT 4.8 s |

上表相機 ID 均省略共同前綴 `CAM_1F_`；同名相機仍以各自 site/run 綁定。
Classroom 101 的 CORRIDOR_04 沒有可選畫面，不用別組資料填補。
Office Top 1 的實際 bbox 為 `[826,119,832,147]`、contact 為 `[828.5,146]`，
投影點為 `[34.579774617470896,49.56341554088987,0.4959475898742678]` m。
選取結果、完整 request/response 見 [frame_queries.json](../../data/engineering/blender_workbench_20261011/frame_queries.json)。

## 重現與發布邊界

以下物化流程是2026-10-11的歷史記錄，現行示範直接讀取既有凍結素材，不重跑producer。
GitHub clone不含Office／E1的RGB、checkpoints及原`.blend`，也不含7B模型、PG／人審狀態；
程式與公開收據的存在不保證原素材可重現。缺失素材須明示不可用，不能以另一來源補缺。

當時在既有工程checkout執行 `scripts/materialize_blender_workbench.py`，由 server-owned
source repo 唯讀抽取來源／相機／時間／媒體安全欄位並產生本機 input manifest。
原圖片與 `.blend` 留在唯一來源位置；不搬運 raw assets、不產生新 `.blend` 副本。
生成的安全 input/index/model display materialization 放在被忽略的
`data/engineering/local_run/blender_camera_v1/`；HTTP 不接受 caller filesystem path。

```sh
AMIDST_SOURCE_REPO=/path/to/canonical/amidst  # 原素材所在 checkout
PYTHONPATH=src UV_CACHE_DIR=/private/tmp/amidst-uv-cache uv run --offline --no-sync python scripts/materialize_blender_workbench.py \
  --repo "$PWD" --canonical-repo "$AMIDST_SOURCE_REPO" \
  --output data/engineering/local_run/blender_camera_v1
```

具備原本機依賴後，現行工作台啟動例：

```sh
export PYTHONPATH=src
DEMO_PORT=${DEMO_PORT:-0}
UV_CACHE_DIR=/private/tmp/amidst-uv-cache uv run --offline --no-sync \
  python -m amidst.workbench --repo "$PWD" --port "$DEMO_PORT"
```

`--offline --no-sync`不安裝缺少依賴；保存Agent案例的工作台context仍需原PG儲存與本機
Ollama模型識別守門。`DEMO_PORT=0`由OS選埠；另一終端以本次Python服務PID作為
`DEMO_PID`，用`lsof -nP -a -p "$DEMO_PID" -iTCP -sTCP:LISTEN`讀取真實listener埠，
將該值填入`DEMO_BOUND_PORT`，再設定`DEMO_URL="http://127.0.0.1:$DEMO_BOUND_PORT"`。
CLI印出的0不是address。綁定checkout退役或刪除後，舊絕對locator標為offline，
重新執行需另行rebind；目前沒有portable replay實作。

「整個系統的端口測試」對 Blender 情況實際重跑該組 PNG 的 pixels → projection →
snapshot reopen → bounded frame retrieval → Top-K → presentation。各端口都列出
input/output 與 ACTUAL_BLENDER／SUBSTITUTE／DEFERRED，替代 Graph／history 有自己
的 source/run/clock。測試不修改操作資料、GT、來源模型或歷史 checkpoint。

Git 只保存 code/docs/tests 與整理過的 counts/hashes/queries/port receipts；raw PNG、
DB、GT、mesh archives、`.blend` 不上傳。串流 FUTURE，正式帳號／部署 DEFERRED；
formal research gates 與凍結 Phase 2 保留。

三組端口均為 **11/11 PASS**：9 ACTUAL_BLENDER、2 SUBSTITUTE；另 1 個影片端口
DEFERRED，沒有算進通過數。實際 HTTP 共 68 次，含 role/scope/budget 拒絕、三種
意圖結果一致、重複查詢相同、窄時間窗及跨場景 media 拒絕。逐端口 I/O 見
[Office](../../data/engineering/blender_workbench_20261011/office_ports.json)、
[Classroom 101](../../data/engineering/blender_workbench_20261011/classroom101_ports.json)、
[Auditorium](../../data/engineering/blender_workbench_20261011/auditorium_ports.json)，
[來源與量測清單](../../data/engineering/blender_workbench_20261011/scene_inputs.json)及
[HTTP 驗證](../../data/engineering/blender_workbench_20261011/http_validation.json)。

最終完整 `pytest --require-physical-evidence` 為 **2969 passed、0 failure/error/skip**
（tool elapsed 321.63 s），Node **67 工作台＋13 產品＝80 passed**；Ruff 通過，
strict mypy 189 source files 通過。實際瀏覽器確認三情況查詢、來源影像放大／時間軸、
像素／投影／索引讀取細節、實際／替代端口及唯讀來源介面，最後 reload console
無 error／warning。Canvas／視角／完整解碼 frame 保留另有 Node 驗證，未量測 FPS。
[validation.json](../../data/engineering/blender_workbench_20261011/validation.json)
綁定本次 code-tree／receipts／JUnit hashes，並保留中間問題與修正；
[source_integrity.json](../../data/engineering/blender_workbench_20261011/source_integrity.json)
核對原 `.blend` SHA／size／mtime 未變。以上不是 formal research acceptance。

## English

The [nine-minute local demo](DEMO_V1.md) is the current operation guide; this document preserves
the October 11 prototype and its original counts/receipts. Local review now records Office
revision20 and Classroom revision15 with 35 deltas and authorized reruns; Auditorium is not
reviewed and all 38 physical checks remain UNKNOWN. Phase2 is about 50%, 05 retains the baseline,
and 11 remains QUALITY_GATE_NOT_MET. R2 passed 12/40 regular tasks (7/20 Chinese, 5/20 English),
with 8/8 safety containment and 2/8 clean model refusals. R3 context engineering passed 3,736
checks and 68 isolated HTTP/PG guards used zero real-model calls. Its first current-v4 actual
demo failed; the private schema/prompt candidate is unapplied and the 48-task replay has not started.
See the [05/11 repair record](PHASE2_LOCAL_REPAIR_0511.md); old v2/v3 literal checks remain
read-only, with goal completion NOT_CHECKED. GitHub-only clones lack the existing RGB/checkpoints,
model weights and PG/review state. Use the dynamic-port launch above; inspect the actual
listener when requesting port 0 and set DEMO_URL from that port. Retired locators are offline
until separately rebound.

This milestone connects existing source-bound Blender camera RGB and partial evaluated mesh
to the shared workbench. It recomputes class-agnostic pixel measurements, normalizes source
cameras/floor to metres and returns deterministic Top-K frame messages without an Agent.
Source geometry, camera calibration and rendered pixels are actual Blender inputs; the orange
target and motion are synthetic substitutes. Each preset site/run remains independent.

The frame query uses a bounded camera/time index, prioritizes a reliable component, available
floor projection and requested time, and explicitly preserves camera diversity. It does not
identify people or classify walking/running/enter-exit. Public PNG serving removes text metadata
only, with original and served hashes and unchanged pixel chunks. The original `.blend` and PNGs
are neither modified nor copied.

The port probe reruns these RGB inputs, persists/reopens a safe temporary feature snapshot and
checks actual retrieval/presentation. Independent Graph/history fixtures are labelled substitutes;
event-reconstruction curves/video are deferred. Streaming, accounts/deployment, formal authority
and frozen research boundaries retain their existing status.

The actual reruns read 100 RGB frames per site. Office produced 31 pixel measurements and
31 floor projections, Classroom 101 produced 70 and 70, and Auditorium produced 91 and 82
with nine explicit projection failures. These counts are not accuracy metrics. The displayed
support-cropped source meshes contain 1,662 / 542 / 318 triangles respectively; they are partial
context rather than a complete model. Scale is 0.0247 metres per Blender unit and the approved
source-bound floor plane is at Z=0.4959475898742676 metres.

For a 0–9.8-second window, target time 5 seconds and K=3, Office returned FRONT 4.4 / REAR 8.6 /
REAR 8.8; Classroom 101 returned CLASS101 5.0 / 4.8 / 4.6; Auditorium returned FRONT 5.0 /
REAR 5.0 / FRONT 4.8. The empty corridor camera is not filled with another site's data.
Each query read 100 scoped records with two camera lookups and zero image bytes. Each site's
probe passed eleven ports (nine actual and two independent substitutes), with video separately
deferred. The 68-request HTTP receipt covers scope, role, budget, repeat determinism, intent
parity, media metadata removal and denied Agent/source-edit actions. The linked JSON receipts
contain the exact requests, source bindings and layer inputs/outputs.

Final validation passed all 2,969 Python checks with required physical evidence and no failures,
errors or skips, all 80 Node checks, Ruff and strict mypy for 189 source files. Actual browser
checks verified all three queries, readonly source UI, image/timeline controls and expanded
port/pixel/projection details; the final reload had no console errors or warnings. The validation
receipt binds code, JUnit and curated receipt hashes and records corrected intermediate issues.
Original `.blend` hash, size and modification time are unchanged. Formal research gates remain
unchanged; engineering validation does not certify semantic accuracy or production capacity.
