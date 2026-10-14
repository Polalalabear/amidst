# Blender 跨鏡頭多解還原 / Blender cross-camera reconstruction

> 目前操作入口： [demo 指南](DEMO_V1.md)與[全部工作／依賴交接](../operations/CURRENT_WORK_REPRODUCTION.md)。本頁固定埠號與日期化測試屬原 checkpoint；當次 URL 使用 `DEMO_URL`，不沿用歷史服務位址。獨立受限 Phase1 驗收見[最新正式報告](../research/PHASE1_FINAL_REPORT.md)，不擴大本頁來源／幾何權限。

本階段在 Office、Classroom 101、Auditorium 各自的來源／run／clock 內建立跨鏡頭
候選關聯，使用確定性基底圖形演算法，保留未關聯基線及多解 Top-K。工作台同步顯示
候選路徑、XYZ／時間／速度曲線與回放；關聯不代表人物身分或行為已確認。
原 `.blend`、原 PNG 與舊 checkpoint 不修改或複製，不開 Blender、不接真實串流，
不呼叫 Agent、外部模型或 renderer 的軌跡／GT／visibility／depth 答案。

## 層級輸入、輸出與資料種類

| 層級 | 具體輸入 → 輸出 | 使用的資料與邊界 |
| --- | --- | --- |
| 來源與像素量測 | 每組2鏡頭×50張960×540 RGB，5 Hz、0–9.8 s → camera/time、bbox/contact、local track、uncertainty | 既有 ACTUAL_BLENDER 影像與校正；橙色目標／活動為 SYNTHETIC_SUBSTITUTE。原影像仍唯讀 |
| 投影／局部運動 | 合法校正、0.0247 m/BU尺度、1F floor Z≈0.495948 m → XYZ、有限差分速度、原局部缺失／拒絕區間 | XYZ為像素與地板交點的衍生值；PROJECTED_OBSERVATION不是直接觀測3D。局部短缺口插值與失敗仍分開 |
| 關聯圖 | 安全frame/measurement/projection快照 → 有效連接片段nodes、跨鏡頭edges及拒絕原因 | 同一site/run/clock；幾何只為 SOURCE_BOUND_FLOOR_ONLY，不把局部顯示mesh當全場碰撞／可行走權限 |
| 多解搜尋 | 所選鏡頭的完整來源時間圖 → 唯一候選邊配置、分組路徑、未關聯nodes與排序外baseline | 時間、距離、速度、同步投影一致性及一進一出限制；設定score不是機率。不強迫匹配或湊足K |
| 曲線／事件片段 | 每解原投影與支持觀測、短跨鏡頭插值、長缺口 → samples/velocities/gaps/provisional event refs | 不平均融合不同鏡頭原投影；另一鏡頭支持點仍保留原值。MISSING中間位置不製造速度或移動游標 |
| 工作台／影片 | source mesh context、上述候選與來源clock → 3D路徑、曲線時間游標、預先物化PNG／MP4 | 同一時間與候選序號；長缺口關聯虛線只表示假設，中間位置仍缺失。事件／track IDs僅專用log |
| 端口隔離 | 本組RGB重算→safe snapshot reopen→graph/Top-K→manifest/bytes hash；獨立E0 Graph/history測試 | ACTUAL_BLENDER與2個SUBSTITUTE端口分開，不把E0候選、GT或delta修改回填Blender run |

三組情況互相獨立。Office／Auditorium即使有相同camera ID，也不共用軌跡、候選或
媒體references。Classroom 101走廊有來源影像而無像素軌跡，不能以另一鏡頭補出關聯。

## 實際完成與尚未完成

| 情況 | 像素量測／原投影 | 圖nodes／合法edges／拒絕edges | 實得候選與限制 |
| --- | --- | --- | --- |
| Office | 31／31 | 5／4／0 | 3解；完整列舉5個合法配置，另留未關聯基線 |
| Classroom 101 | 70／70 | 6／0／0 | 1個未關聯基線，NO_CROSS_CAMERA_EVIDENCE；走廊50張來源影像、0投影 |
| Auditorium | 91／82 | 19／52／32 | 3解；beam256截斷，非完整列舉或全域最優 |

已完成各站的關聯圖、有界多解搜尋、候選XYZ／時間／速度曲線、缺口與原支持點保存、
工作台同步及新曲線PNG／可回放MP4。三組影片均使用100張既有實際RGB，1280×720、
5 fps、50格、10秒，H264/yuv420p/faststart且完整解碼PASS；無ffprobe時明列
FFMPEG_FULL_DECODE_FALLBACK。原.blend SHA／468,300,506 bytes／mtime保持一致。

Office候選連到不同局部片段，不能把各解的長缺口說成同一段已知移動。Auditorium
每解主曲線保留79個原投影，另有3個原投影在overlap_support中；全部82個原投影
仍在local tracks／graph，沒有被平均或刪除。各解保留18個原hard gaps；Classroom
基線內6條局部路徑也不是一個已確認的人物軌跡。

Office候選1／2／3的長缺口分別為0.4–8.6 s（8.2秒）、1.8–8.6 s（6.8秒）、
4.4–8.6 s（4.2秒）。這是不同端點的可能關聯，沒有補造缺口中間軌跡。

本次完整Python **3067 PASS、0 skipped**（`--require-physical-evidence`，443.27秒）、
Node **110 PASS**（workbench97＋product13）、Ruff、mypy193來源檔及diff檢查通過。
每站**16/16端口PASS**（14 ACTUAL＋2隔離SUBSTITUTE），合48/48；實際HTTP
**160 requests／450 assertions PASS**，六份媒體bytes等於disk與manifest hash。
瀏覽器實測三站候選／基線、缺失與截斷警示、影片播放／跳轉時間同步、手動時間軸
暫停影片及窄窗／單鏡頭scope差異；console error／warning皆0。保留scene renderer、
camera pose與media DOM另有Node回歸，沒有以這些檢查宣稱FPS或身分精度認證。
公開[驗證收據](../../data/engineering/blender_association_20261012/validation.json)綁定
本次529份code/config/test檔的code-tree SHA及其餘7份curated receipts；舊收據不回寫。

**尚未完成：**跨鏡頭身分精度／行為確認、完整遮擋／碰撞／走廊通行物理驗證、
Classroom走廊有效追蹤、Auditorium完整候選列舉、真實攝影機串流、正式帳號／部署。
這些不以工程端口PASS代替。觀測缺失與heuristic uncertainty仍保留。

## 關聯與物理限制

原camera-local軌跡先依硬缺口、超速或失敗投影拆成連接片段。跨鏡頭邊分為：

- **時間缺口：**正時間差≤10 s，端點距離／時間差≤設定8 m/s。≤1 s才可插入
  INFERRED_CROSS_CAMERA位置；更長缺口保持MISSING。兩端可畫關聯假設線，不能把線
  當成已知中間動線。沒有外推、detour補造或完整collision判斷。
- **重疊延伸：**必須存在共同來源clock時間的樣本，所有共同投影距離≤設定0.75 m；
  切換後的實際路徑速度仍≤8 m/s。端點接近本身不是同步證據。
- **同期／包含支持：**相容鏡頭可提供CORROBORATING_OVERLAP支持，即使沒有時間延伸。
  保留各鏡頭原投影，不平均成一個觀測，不把沒有handoff的情況稱為0 m/s。

0.75 m及8 m/s均為工程設定，不是校正誤差界或已驗證人體模型。Floor-only限制不能
證明穿牆、不穿牆、遮擋、門／走廊可通行或完整物理事件。像素heuristic uncertainty
保留，不能解讀成機率、標準差或公尺誤差。

每個片段最多一條incoming／outgoing邊，整條路徑需保持時間及切換速度一致；同camera
重疊衝突、非相鄰跨camera同步位置衝突、同原track的硬缺口間接修補均拒絕。
每解按來源時間選一筆原投影作主曲線，其他同期支持點另存，不瞬間跳到第二筆位置。
原局部hard gaps另列`unresolved_local_gaps`，不因拆段或跨鏡頭分組而消失。

排序為各選定邊的configured compatibility score相加，偏好較短缺口、較小速度或同步
距離；score不是人物同一性的機率，也不確認行走／跑步／出入。使用有界beam搜尋，
上限64 nodes、256 edges、beam256、K1–5。`search.complete/truncated`與prefix路徑
guard拒絕數如實輸出；若截斷或非單調prefix被拒，不稱為全域最優或完整列舉。
`baseline_candidate`獨立保留所有未關聯片段；沒有足夠合法候選時不複製結果湊K。

## 工作台與接口

研究工作台選擇一組Blender情況、鏡頭、起迄時間及K，按「跨鏡頭多解還原」。
可切換Top-K候選或排序外未關聯基線。原局部3D模型／視角保留，路徑與時間游標
更新同一canvas；投影、短插值、關聯假設線、位置缺失與支持觀測分開顯示。

**關聯與排名使用所選鏡頭的完整來源0–9.8 s圖；查詢時間窗只切曲線與顯示。**
這保留canonical片段與事件references，不能把窄窗描述為只以窗內證據重新排名。
預先物化素材固定兩鏡頭／完整時間／請求K=3，實際候選數可能少於3；工作台明列其
與本次camera/time/K及選定rank的差異。選rank不重新編碼影片。影片時間可同步3D、
曲線與原camera截圖；手動時間軸暫停影片，缺口游標不延伸。

```json
POST /api/cross_camera_reconstruction
{
  "session_ref": "<server-issued-session>",
  "scene_id": "blender-office",
  "camera_ids": ["CAM_1F_AUDITORIUM_FRONT", "CAM_1F_AUDITORIUM_REAR"],
  "start": 0,
  "end": 9.8,
  "top_k": 3
}
```

回應`workbench.blender-association.v1`含source_binding/source_features/association_sha256、
selection、policy、local tracks/camera_coverage、graph nodes/edges/rejected_edges、
candidates(paths/samples/velocities/gaps/overlap_support)、baseline_candidate、search、
retrieval、summary及optional artifacts。身份UNCONFIRMED、行為UNKNOWN、agent_used=false。
沒有投影回NO_RESULT；有局部軌跡但缺合法跨鏡頭邊回NO_CROSS_CAMERA_EVIDENCE。

Research/session/scene守門，最多4鏡頭、10 s、400 source points、32 local tracks；
K需嚴格整數1–5。非法／重複camera、布林／字串／NaN／inf時間、越界及額外GT／
callerpath／速度修改拒絕。圖與候選在匯入時預建；query讀安全索引與有界圖，不讀PNG、
不掃repository／全資料庫，不擴張Agent接口。

`GET /api/cross_camera_media?session_ref=…&scene_id=…&ref=…`只取本session/scene已核發
的`cross-media`素材。PNG 200，MP4 200／單一Range206／非法416；GET不encoding。
input/source/core/motion/renderer/model/encoder/artifact hashes及public allowlist均核對。
缺失／stale optional素材保留有效候選與曲線，回UNAVAILABLE並撤銷舊refs；來源或安全
快照失配拒絕。公開DTO不含private locator；正常畫面不顯示事件IDs，內部refs保留。

## 重現與發布

重用既有`blender_camera_v1`安全資料；新素材與之前camera-local影片分開：

```sh
MPLCONFIGDIR=/private/tmp/amidst-mpl-cache UV_CACHE_DIR=/private/tmp/amidst-uv-cache \
uv run --offline --no-sync python scripts/materialize_blender_association.py \
  --repo "$PWD" --output data/engineering/local_run/blender_association_v1
UV_CACHE_DIR=/private/tmp/amidst-uv-cache uv run --offline --no-sync \
  python -m amidst.workbench --port 8016
```

每站衍生PNG／MP4／private manifest與完整候選features留在ignored local_run。
Git僅code/docs/tests/curated counts/hashes/例子/端口收據，不上傳原RGB、影片、完整
軌跡／mesh、DB、GT或.blend。修改歷史仍保存差異文件。新證據另存
[association receipts](../../data/engineering/blender_association_20261012/validation.json)，
不回寫4b43aed的camera-local歷史驗證。

## English

Each Blender preset independently produces deterministic provisional cross-camera hypotheses
using source clocks, floor-derived positions, configured speed/proximity constraints and globally
consistent path assignments. Top-K is not an identity probability. An unassociated baseline is
retained separately; insufficient evidence does not fabricate additional candidates.

Observed RGB, projected 3D, bounded inferred transitions, corroborating projections, long missing
spans and synthetic motion remain distinct. Candidate paths and curves share the workbench/video
clock. Canonical association/ranking uses the selected cameras' full source time; a narrow query
only slices displayed curves. Pre-materialized media has fixed full-camera/full-time/requested-K3
scope, explicitly separate from the query and selected rank. No Agent, original Blender changes,
raw copies, real streaming or unapproved whole-scene physical/semantic certification is involved.
Formal gates, frozen Phase2, accounts/deployment and source/GT/publication boundaries are preserved.

Actual validation: 3,067 Python tests with required physical evidence and no skips, 110 Node
tests, Ruff and mypy for 193 source files passed. All 48 ports pass with 42 actual-source and
six isolated substitute ports. A fresh 160-request HTTP run passed all 450 assertions; six
media byte hashes and complete video decodes match. Browser candidate/baseline selection,
missing/truncated notices, playback/seek synchronization and query/media scope were verified.
These are engineering checks, with no formal identity/behavior or whole-scene certification.
