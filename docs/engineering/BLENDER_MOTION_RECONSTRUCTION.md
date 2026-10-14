# Blender 物理曲線與事件還原 / Blender motion reconstruction

> 目前操作入口： [demo 指南](DEMO_V1.md)與[全部工作／依賴交接](../operations/CURRENT_WORK_REPRODUCTION.md)。本頁固定埠號與日期化測試屬原 checkpoint；當次 URL 使用 `DEMO_URL`，不沿用歷史服務位址。獨立受限 Phase1 驗收見[最新正式報告](../research/PHASE1_FINAL_REPORT.md)，不擴大本頁來源／幾何權限。

本文件保留`4b43aed`的camera-local milestone。後續同來源的跨鏡頭候選關聯、多解Top-K
與3D同步回放見[跨鏡頭還原](BLENDER_CROSS_CAMERA_RECONSTRUCTION.md)；不改寫本次歷史收據。

2026-10-12 已把 Office、Classroom 101、Auditorium 的既有 Blender camera RGB 接入
位置／時間／速度曲線與可回放影片。工作台仍以來源局部 3D 模型為主；每組都有曲線 PNG
和 10 秒 MP4。使用基底演算法，不呼叫 Agent；原 `.blend`、相機校正及原 PNG 不修改、
不複製，不接實體攝影機串流。這是各鏡頭局部像素軌跡的候選還原，尚未證明人物身分、
行為、跨鏡頭事件或完整物理場景。

## 各層如何交流

| 層級／完成狀態 | 具體輸入 → 輸出 | 實際、推斷與替代資料 |
| --- | --- | --- |
| 來源與顯示：完成 | 每組 2 鏡頭 × 50 張 960×540 PNG，5 Hz、0–9.8 s；來源 camera pose／intrinsics、局部 evaluated mesh → 原像素影像、平滑灰色模型與 source/site/run/clock/hash | 建築、校正與 RGB 為 ACTUAL_BLENDER；橙色目標與活動為 SYNTHETIC_SUBSTITUTE；mesh 為 PARTIAL 顯示 |
| 像素量測／投影：完成 | RGB median 差分／components → camera/time、bbox/contact pixel、local track、uncertainty；合法校正與 1F floor → XYZ 或投影失敗 | 真正觀測的是 RGB pixels；XYZ 是接地射線與地板交點的衍生值，不是直接量測 3D |
| 安全狀態與索引：完成 | sanitized frame/measurement/projection/local-track 快照、來源 hashes → 預先建好的 camera/time 索引 | 不讀 renderer observations、trajectory、GT、depth 或 visibility 答案；query 不掃描圖片 |
| 物理曲線：完成 | 同 camera-local track 的 timestamp／XYZ／uncertainty → 位置 samples、速度 intervals、missing gaps、暫定片段 | PROJECTED_OBSERVATION、INFERRED_INTERPOLATION、MISSING 分開；速度是 INFERRED_FINITE_DIFFERENCE，身份 UNCONFIRMED、行為 UNKNOWN |
| 影片物化／回放：完成 | 兩鏡頭的 50 組原時間影格、完整曲線與局部模型 → 1280×720 H.264/yuv420p MP4，5 fps、50 frames、10 s，曲線 PNG | 影格 SOURCE_RGB_EXACT；XY、速度及片段為衍生診斷。不存在的投影顯示 MISSING，不外推。最後 9.8 s 影格停留 0.2 s |
| 工程端口：完成 | 上述來源重新量測與獨立 reopen，再核對曲線、manifest、媒體 bytes/hash → 每組 13/13 PASS | 11 ACTUAL_BLENDER 端口使用本組來源；2 SUBSTITUTE 端口仍用獨立 E0 Graph gap／delta history，不套用到 Blender run |
| 完整物理與正式研究：未完成 | 全場 walkability／collision／occlusion、跨鏡頭 identity／event association、校正誤差界與行為驗證 | 不以目前曲線或影片替代正式研究驗收；formal Cases 2/3／full Exit BLOCKED、Case 4 DEFERRED，Phase 2 FROZEN |

相機平移／clip 距離已在上個基底層由 native BU 明確乘 0.0247 m/BU；本層不重複縮放。
floor Z=`0.4959475898742676` m。相同 FRONT／REAR 相機名稱仍以各自 site/run 綁定，
不跨情況合併、不跨 track 縫合、不把沒有量測的鏡頭補成另一鏡頭的軌跡。

## 演算法、缺失與不確定性

位置曲線的橫軸為來源秒數，縱軸為 X/Y/Z 公尺。觀測投影畫實線／實心點；只有同一
局部 track 的兩個有效投影端點間隔 ≤1 s、隱含速度 ≤8 m/s，才在已登錄的缺失影格
時間作線性插值，標記 INFERRED_INTERPOLATION。8 m/s 是設定工程門檻，不是經驗證的
人體物理模型。長缺口、無效投影、超速或數值問題保持 MISSING／斷線；不外推。

速度 `v=(p₂-p₁)/(t₂-t₁)`、速率 `|v|` 放在區間中點時間，保留兩端來源 references
與 uncertainty。只對有效連接區間求差分；被拒絕的跳躍只記 gap reason 和可計算的
implied speed，不產生合法速度。uncertainty 是像素元件啟發式值，不是機率、標準差或
公尺誤差界。Z 接近常數是地板投影假設的結果，不能解讀成已證明没有垂直運動。

Office 的一筆實際例子：t=0 s、XYZ≈`[34.400553,48.102902,0.495948]` m，
像素接地點 `[776,135]`、MERGED_OR_PARTIAL、uncertainty=0.6；下一投影在 0.2 s。
輸出速度時間 0.1 s、v≈`[-0.313834,0.220560,0]` m/s、速率≈0.383587 m/s，
state=INFERRED_FINITE_DIFFERENCE。它不產生「行走」判定。

| 情況 | camera-local tracks | 投影位置點 | 插值點 | track 內 MISSING 點 | 速度區間 | 拒絕／缺失區間 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Office | 3 | 31 | 0 | 0 | 26 | 2 |
| Classroom 101 | 6 | 70 | 4 | 0 | 64 | 0 |
| Auditorium | 10 | 82 | 19 | 12 | 63 | 18 |

track 內 MISSING counts 不代表每個來源影格都有目標：Office 兩鏡頭只有 23／7 個影格
有投影；Classroom 101 的 CORRIDOR_04 有 50 張來源影像但 0 個量測／投影，整個鏡頭
明列 MISSING。Auditorium 原始 9 筆投影失敗仍保留；其 12 個 MISSING samples 包含曲線
處理留下的其他缺失時間。counts 不是準確率，暫定片段不是已確認 canonical events。

## 工作台與 API

在 8016 研究工作台選擇三組 Blender 預設情況，設定鏡頭及起迄秒數，按「產生物理曲線
與還原」。曲線依本次查詢切片；預先物化 PNG／影片始終顯示完整 0–9.8 s／兩鏡頭，
明列與窄查詢的範圍差異。影片可播放、暫停、跳轉；可選擇同步既有 camera 截圖時間。
Canvas、camera images、video DOM 在一般更新時保留；切換 source/scene 或修改 scope
會拒絕晚到資料。事件 ID 僅在專用 log，正常曲線使用局部軌跡序號。

```json
POST /api/motion_reconstruction
{
  "session_ref": "<server-issued-session>",
  "scene_id": "blender-office",
  "camera_ids": ["CAM_1F_AUDITORIUM_FRONT", "CAM_1F_AUDITORIUM_REAR"],
  "start": 0,
  "end": 9.8
}
```

回應為 `workbench.blender-motion.v1`，含 source_binding／source_features／
reconstruction_sha256、selection、tracks(samples/velocities/gaps/provisional events)、
camera_coverage、policy、summary、retrieval 和 artifacts manifest；`agent_used=false`。
query 上限為 4 鏡頭、10 s、400 points、32 tracks。未知／重複鏡頭、非法／布林／字串
時間、越界及額外參數拒絕；使用 server-owned scene/session，不接受 caller path／GT。

`GET /api/motion_media?session_ref=…&scene_id=…&ref=…` 只接受本 session/scene 先前
核發的 opaque reference。PNG 200；MP4 支援完整 200、單一 byte Range 206 和非法
Range 416。每次核对 input/core/renderer/model/artifact hashes；GET 不編碼。素材缺失
或過期時曲線仍可單獨使用，artifacts 明列 UNAVAILABLE；失效 references 撤銷，不用
其他情況素材補缺。角色、來源或輸入快照失配則拒絕。媒體公開 DTO 不含 private locator。

## 重現、測試與儲存

本次完整 Python `pytest --require-physical-evidence`：3017 passed、0 failures/errors/skips
（357.78 s）；Node 79 workbench＋13 product＝92 passed，Ruff PASS、strict mypy 191 files
PASS。實際 HTTP 98 requests／254 assertions 全部 PASS，含三組13端口、六份媒體bytes／
hash、影片Range／416、單鏡頭與跨session／scene／role拒絕。瀏覽器三站影片已實際播放，
Office手動跳轉及camera同步、Classroom走廊缺失提示、Auditorium窄查詢／完整素材範圍
已確認，最後console無warning／error。既有與新增測試包含在上述總數，不重複加總。

重用上階段已安全物化的 `blender_camera_v1`，不重新 render 或打開 Blender：

```sh
MPLCONFIGDIR=/private/tmp/amidst-mpl-cache UV_CACHE_DIR=/private/tmp/amidst-uv-cache \
uv run --offline --no-sync python scripts/materialize_blender_motion.py \
  --repo "$PWD" --output data/engineering/local_run/blender_motion_v1
UV_CACHE_DIR=/private/tmp/amidst-uv-cache uv run --offline --no-sync \
  python -m amidst.workbench --port 8016
```

本機每站 `curves.png`／`reconstruction.mp4`／private manifest 保留在 ignored local_run。
三影片實際完整解碼 PASS；環境沒有 ffprobe，收據明列 FFMPEG_FULL_DECODE_FALLBACK。
Git 只保存 code/docs/tests 與精簡 hashes/counts/例子/端口收據，不上傳媒體、完整軌跡、
private manifest、DB、GT 或 `.blend`。修改歷史仍採差异文件，不复制原模型。

實際驗證與版本綁定見 [validation](../../data/engineering/blender_motion_20261012/validation.json)、
[HTTP](../../data/engineering/blender_motion_20261012/http_runtime.json)、
[曲線與公開素材清單](../../data/engineering/blender_motion_20261012/motion_summary.json)、
[source integrity](../../data/engineering/blender_motion_20261012/source_integrity.json)。
2026-10-11 的 Top-K checkpoint／影片 DEFERRED 是當時歷史；本次實作與收據另存。
真實串流 FUTURE，正式帳號／部署 DEFERRED。

## English

Three source-bound Blender presets now provide camera-local XYZ/time curves, finite-difference
speed and playable ten-second diagnostic videos. Actual RGB/calibration/partial source geometry
remain read-only; targets and motion are synthetic substitutes. Projected positions, bounded
linear interpolation and speed are derived diagnostics, with explicit missing intervals and
heuristic uncertainty. No Agent, external model, truth answers, cross-camera identity merge,
track stitching, extrapolation, original Blender modification/copy or real camera stream is used.

Curves use the selected query window; pre-materialized PNG/video retain the full two-camera
0–9.8-second scope. Media serving verifies provenance/hashes and issued session/scene references,
supports MP4 byte ranges and never encodes on GET. Missing/stale optional artifacts leave valid
curves usable. Each site reruns thirteen ports, including eleven actual-source ports and two
independent substitute Graph/history ports. Full physical scene authority, identity/behavior,
formal research acceptance, accounts/deployment and streaming retain the boundaries above.
