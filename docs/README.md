# 文件導覽 / Documentation

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

接手全部工作、工作樹與依賴時先讀[完整重現交接](operations/CURRENT_WORK_REPRODUCTION.md)；其[有界收據](../data/engineering/work_handoff_20261014/receipt.json)記錄原資產核對、私有材料保存、SQLite／PG恢復與候選副本檢查，不把文書交接當新模型品質或清理完成。

2026-10-14 最新demo与Phase2狀態以[第一版demo](engineering/DEMO_V1.md)為單一操作入口：九分鐘腳本、動態本機port、來源／PG／Ollama依賴、可展示與未達標內容，以及最新[readiness收據](../data/engineering/phase2_repair_0511_20261013/demo_v1_readiness_20261014.json)。工程已發布b1cf0c4，main439c866保留已驗證R1；11 R2全題12/40品質FAIL，734版3736 Python／HTTP68工程PASS但首次真實demo FAILED，新48題未開始；05 baseline与Phase2约50%不提高。各歷史驗證總數不累加。獨立Phase1正式ref043bed2的[受限Case1–3驗收](research/PHASE1_FINAL_REPORT.md)18 gates已PASS與clean重現，Case3 ADE初始目標未達、整校幾何未認證；不再把舊BLOCKED當目前結論。

2026-10-14 的[本機儲存清理紀錄](history/LOCAL_STORAGE_CLEANUP_20261014.md)列出已退役的工作樹、
舊封存／試跑／review 副本與保留項目。依使用者最新指示，舊實體只留文件紀錄；
現行 Phase 2／demo、原模型、模型權重及資料庫仍保留。

<!-- PHYSICAL_HUMAN_REVIEW_20261013_BEGIN -->
本輪[人工核對 checkpoint](history/BLENDER_REVIEW_CHECKPOINT_20261013.md)已停止續作並準備發布：Office revision20、Classroom101 revision15 的35筆人工差異與確認後重跑已完成，Auditorium尚未開始；38個物理檢查仍UNKNOWN。Top-3畫面與事件解數分開：Office回3解，Classroom只有1個未關聯基線。頂部點擊切換3D／2D，8／12／16格只在2D顯示，來源世界軸隨視角更新。這次56項scoped Node與語法／diff檢查PASS；入口建立時Python3186／HTTP154等為歷史收據，不宣稱重跑。完整資料流見[人工核對契約](engineering/BLENDER_PHYSICAL_HUMAN_REVIEW.md)，有界[checkpoint收據](../data/engineering/blender_review_checkpoint_20261013/)另存；等共享Phase2任務完成、保存與遠端核對後才刪除finalization工作樹，不刪其他demo或原資產。
<!-- PHYSICAL_HUMAN_REVIEW_20261013_END -->

先讀 [目前交接](operations/CODEX_HANDOFF.md)；開始實作時使用 [續作 prompt](operations/PHASE1_NEXT_CHAT_PROMPT.md)，並遵守 [開發規則](specs/DEVELOPMENT_RULES.md)。可執行的本機 mock API／replay／consumer 見 [Phase 2 整合](engineering/PHASE2_INTEGRATION.md)；M1–M6 照片到3D事件的操作與重現見 [模擬工程](engineering/SIMULATION_ENGINEERING.md)；局部跨鏡頭索引、事件卡與當次消融見 [局部 pilot](engineering/LOCAL_CAMERA_PILOT.md) 與 [protocol](research/LOCAL_CAMERA_EVENT_PROTOCOL.md)；Agent 的定位、可用工具與資料邊界見 [工程契約](engineering/AGENT_RETRIEVAL_BOUNDARY.md)。

持久調查、RGB 外觀查找、四鏡頭影片與 Three.js 回放、案例／人審／報告匯出的操作入口，見
[本機 Phase 2 產品](engineering/LOCAL_PHASE2_PRODUCT.md)；當次結果與正式待辦分開記錄。
版本化 pixel／外觀／關聯／行為比較、失敗證據與 frozen adapter 見
[研究精度 v2](research/LOCAL_CAMERA_ACCURACY_V2.md)。
並行的雙角色／場景 catalog／人審版本入口見 [共用工作台](engineering/SHARED_WORKBENCH.md)，
它的本機8016及驗證 receipt 與產品8020分開。

2026-10-11 的[系統端口、label 指引與差異歷史](engineering/SYSTEM_PORTS_AND_LABEL_GUIDANCE.md)
說明具體輸入輸出、模擬併發、使用者行為選項、Agent I/O 與穩定 3D 的工程範圍。

同日的 [Blender 相機畫面檢索](engineering/BLENDER_CAMERA_FRAME_RETRIEVAL.md) 接入三組
source-bound 預設情況、300 張既有 Blender camera RGB 與局部平滑來源模型，
加上三個原 fixture，共六個場景。查詢由本機基底演算法產生 Top-K 畫面訊息，沒有 Agent 決策；
來源幾何／校正／像素、合成目標／活動與獨立替代測試逐層標示。
[整理收據](../data/engineering/blender_workbench_20261011/) 與歷史 milestone 驗證分開保存。

2026-10-12 的 [Blender 曲線與事件還原](engineering/BLENDER_MOTION_RECONSTRUCTION.md)
接續同組 RGB 像素／地面投影，以同鏡頭局部 track 產生暫定位置曲線與有限差分速度。
短缺口插值、長缺口／超速／投影失敗斷開，以及來源與未核准物理邊界均明列；
不把投影當直接觀測3D、不跨鏡頭合併身分、不經 Agent。三站曲線 PNG／影片已物化，
每站影片1280×720、H.264／yuv420p／faststart、5 fps、50影格／10秒，
每站100次來源RGB選取均為 `SOURCE_RGB_EXACT`。無 ffprobe，三站以
`FFMPEG_FULL_DECODE_FALLBACK` 完整解碼 PASS，三站 provider manifest／六份媒體讀取 PASS；
完整 Python 驗證（含 physical evidence）3017 passed／357.78秒，無 fail／error／skip；
Node 92 PASS（workbench 79＋product 13），Ruff／strict mypy 191來源檔 PASS。
最終 HTTP 98 requests／254 assertions PASS、`issues=[]`；三站各13/13端口
（11 ACTUAL_BLENDER＋2 SUBSTITUTE）及六份媒體binary／hash／range／scope PASS。
三站1280×720／10秒影片瀏覽器實際播放無解碼錯誤，最終console無warning／error、
一般畫面隱藏opaque event IDs；原`.blend` SHA／size／mtime不變，見[本次收據目錄](../data/engineering/blender_motion_20261012/)。

同日接續的[Blender 跨鏡頭多解還原](engineering/BLENDER_CROSS_CAMERA_RECONSTRUCTION.md)
說明各 site／run 內的時間／速度／floor 限制、多解 Top-K、未關聯基線與3D／曲線／影片
同步契約。Office 回3解，CLASS101 無跨鏡頭證據回1個基線，Auditorium 回3解並明示
beam 截斷／非全域最優；原觀測支持點、短推斷與長缺失分開保留。完整來源圖排名與
窄窗顯示分開標示。[本次收據](../data/engineering/blender_association_20261012/validation.json)
與 camera-local 歷史紀錄獨立。三站PNG／MP4已物化且完整解碼PASS；完整Python3067／
Node110／Ruff／mypy193檔、三站各16/16端口、HTTP160 requests／450 assertions及
瀏覽器三站播放／同步均通過，原`.blend` SHA／size／mtime不變，不沿用舊PASS。

<!-- PHYSICAL_FILTER_20261013_BEGIN -->
前一物理checkpoint（2de9821）的[來源物理篩選與重排](engineering/BLENDER_PHYSICAL_CANDIDATE_FILTER.md) 接入核准局部幾何及最多256解候選池，
保留原觀測、推斷與缺失。三站硬排除0、所有候選仍為UNKNOWN；Office原3／4／2成為Top-3，
CLASS101只有未關聯基線，Auditorium截斷池維持前三。門孔核准仍為0，名稱與局部mesh不增加權限；
長缺口不補直線，無可用位置的基線／摘要也明示UNKNOWN。新v2素材全解碼；Python3140、
Node122（工作台109＋product13）、60/60端口及HTTP175請求／501斷言PASS，三站瀏覽器同步通過，
完成數以[新收據](../data/engineering/blender_physical_20261013/validation.json)為準；歷史PASS不沿用，原`.blend`不開啟、修改或複製。
<!-- PHYSICAL_FILTER_20261013_END -->

使用者最新決策：**8016／frontend/workbench 為統一網頁主入口**。既有與後續頁面能力
接入共用工作台；8020／frontend/product 保留既有工程證據及待遷移功能來源，不再擴張成
另一個主要前端。Product 後端／資料／typed interfaces 已接人物調查／影片／案例；原 frozen lab保留。

[實驗展示覆蓋表](engineering/WORKBENCH_EXPERIMENT_COVERAGE.md) 保留 2026-10-10 網站盤點：
當時三個獨立場景與15家族展示索引；缺少素材、status-only artifacts與formal BLOCKED分開列出。
操作見 [來源模型與行走](engineering/SOURCE_PRESENTATION_WORKBENCH.md) 和
[人物調查／展示庫](engineering/WORKBENCH_INVESTIGATION_GALLERY.md)。
本輪核准04／06的操作、来源及限制見[單一合成run／評測準備](engineering/WORKBENCH_RUN_STUDY.md)。
最新核准05／09合成診斷／10區域出入與停留／11本機模型／12本機PG的實作及限制，見[本機A＋B＋C整合](engineering/PHASE2_LOCAL_BATCH_ABC.md)。
接續的[05／11修正與demo](engineering/PHASE2_LOCAL_REPAIR_0511.md)提供逐欄核對回答及局部追蹤比較；48題驗收與main候選狀態另存新收據，舊A＋B＋C結果保留。

| 資料夾 | 內容 |
| --- | --- |
| [specs/](specs/) | 需求、架構、資料契約、決策與持續規則 |
| [engineering/](engineering/) | 模擬工程、Agent 工具與資料邊界 |
| [research/](research/) | Benchmark protocol、研究結果、展示與重現 |
| [operations/](operations/) | 目前交接、續作 prompt、runtime 與資產物化 |
| [history/](history/) | 工作、實驗與歷史 checkpoint 紀錄 |

### Office Demo / Claude handoff

- [Auditorium display restoration](engineering/WORKBENCH_AUDITORIUM_DISPLAY_REPAIR.md) — Task C source-bound supplemental geometry, focused regressions and partial coverage.
- [Office demo visual acceptance](engineering/WORKBENCH_OFFICE_DEMO_VISUAL_ACCEPTANCE.md) — shared cursor rule, 2D↔3D evidence labels, ground contact UNKNOWN.

- [Root agent rules](../AGENTS.md) and [Claude Code instructions](../CLAUDE.md) — shared scope, boundaries and onboarding order.
- [Claude 初始交接](operations/CLAUDE_INITIAL_HANDOFF.md) — Git baseline、目前證據狀態、第一個 audit 任務。
- [Office Demo MVP](agents/OFFICE_DEMO_MVP.md) — user flow, state labels and acceptance requirements.
- [Claude task sequence](agents/OFFICE_DEMO_TASKS.md) — dependency-ordered frontend tasks and focused verification.
- [Office Demo v1](engineering/DEMO_V1.md) — 現有 demo 流程、依賴與已知限制。
- [Office selected-target API contract](contracts/OFFICE_DEMO_TARGET_V1.md) — WIP additive endpoint 契約。
- [Office fixture config](../configs/office_demo_fixture_v1.json) — source-bound fixture IDs, hashes, cameras and time scope.
- [Office backend/Agent audit](engineering/OFFICE_MVP_AGENT_AUDIT.md) — dated audit evidence and limits.

此頁是唯一文件索引。根目錄另保留 exact corridor review 與 runtime 使用的 checkpoint JSON；三個符號連結維持 locked protocol、核准 review 與歷史 geometry reports 的原路徑。正文位於分類資料夾，不另建逐檔轉址文件。

## English

Start with the [complete work/reproduction handoff](operations/CURRENT_WORK_REPRODUCTION.md) for worktrees and local dependencies; its [bounded receipt](../data/engineering/work_handoff_20261014/receipt.json) separates preservation/restore checks from pending model acceptance and cleanup.

The current [Demo v1](engineering/DEMO_V1.md) is the single guide for the nine-minute workflow, dynamically assigned local port, actual asset/service dependencies, limits and dated [readiness receipt](../data/engineering/phase2_repair_0511_20261013/demo_v1_readiness_20261014.json). Engineeringb1cf0c4 and validated R1 main439c866 are distinct. R2 failed full model quality at12/40; current734 passed3736 Python tests/68 scripted HTTP checks but failed its first actual model demo. No new48 replay has started. Keep05 baseline and Phase2 at approximately50%; historical counts are not added. Independent Phase1 release043bed2 passed18 scoped Case1–3 gates and clean reproduction; its initial Case3 ADE target was unmet and school geometry remains uncertified. See the [formal report](research/PHASE1_FINAL_REPORT.md).

<!-- PHYSICAL_HUMAN_REVIEW_20261013_EN_BEGIN -->
The [human-review checkpoint](history/BLENDER_REVIEW_CHECKPOINT_20261013.md) records Office revision20 and Classroom revision15, 35 local deltas and both authorized full-window reruns. Auditorium is not reviewed; all 38 effective physical checks remain UNKNOWN. Office returns three event candidates; Classroom returns one unassociated baseline despite a Top3 request. The top 3D/2D click switch shows grid choices only in 2D and preserves source-world directions. Fresh scoped validation passed 56 Node tests plus syntax/diff checks; prior full-suite totals remain historical. See the [contract](engineering/BLENDER_PHYSICAL_HUMAN_REVIEW.md) and [bounded receipts](../data/engineering/blender_review_checkpoint_20261013/). Removal of the finalization checkout waits for the shared Phase2 task and verified retention/publication; other checkouts and original assets remain.
<!-- PHYSICAL_HUMAN_REVIEW_20261013_EN_END -->

Read the [current handoff](operations/CODEX_HANDOFF.md), use the [continuation prompt](operations/PHASE1_NEXT_CHAT_PROMPT.md) for implementation, and follow the [development rules](specs/DEVELOPMENT_RULES.md). [Phase 2 integration](engineering/PHASE2_INTEGRATION.md) documents the executable local mock API, replay and consumer; [Simulation engineering](engineering/SIMULATION_ENGINEERING.md) documents the operating RGB-to-3D loop; [Local camera pilot](engineering/LOCAL_CAMERA_PILOT.md) documents indexed association/event cards and evaluation; the [Agent contract](engineering/AGENT_RETRIEVAL_BOUNDARY.md) defines roles, tools and data boundaries.

[Local Phase 2 product](engineering/LOCAL_PHASE2_PRODUCT.md) documents durable investigations,
RGB appearance retrieval, four-camera video/Three.js playback, saved cases, reviews and reports.
[Accuracy v2](research/LOCAL_CAMERA_ACCURACY_V2.md) documents versioned pixel, association and
behavior comparisons, failure evidence and the frozen research adapter.
[Shared workbench](engineering/SHARED_WORKBENCH.md) documents the independently validated
local research/admin scene and review workspace.
The 2026-10-11 [system ports, label guidance and delta history](engineering/SYSTEM_PORTS_AND_LABEL_GUIDANCE.md)
document records concrete interface inputs/outputs, phased concurrency probes, user intent,
MockAgent I/O and stable 3D presentation.
The same-day [Blender camera frame retrieval](engineering/BLENDER_CAMERA_FRAME_RETRIEVAL.md)
milestone adds three source-bound presets and 300 existing camera RGB frames with partial smooth
source-model context. Six catalog scenes include the three original fixtures. Local deterministic
algorithms return Top-K frame messages without an Agent decision, while actual geometry/calibration/pixels,
synthetic target/motion and independent substitute probes retain separate labels.
[Curated receipts](../data/engineering/blender_workbench_20261011/) are separate from historical validation.
The 2026-10-12 [Blender motion reconstruction](engineering/BLENDER_MOTION_RECONSTRUCTION.md)
uses the same RGB-derived floor projections for provisional camera-local position and speed curves.
It marks short-gap interpolation and disconnected long/speed/projection gaps, without observed-3D,
confirmed-identity or Agent claims. Three sites have materialized curve PNGs and videos at
1280×720 H.264/yuv420p/faststart, 5 fps and 50 frames/10 seconds per site, each with 100
`SOURCE_RGB_EXACT` source selections. Without ffprobe, all three passed
`FFMPEG_FULL_DECODE_FALLBACK`; provider manifests and all six media reads passed.
The full Python suite with physical evidence passed 3,017 tests in 357.78 seconds without failures,
errors or skips; 92 Node tests passed (79 workbench + 13 product), plus Ruff and strict mypy for
191 source files. Final HTTP passed 98 requests/254 assertions with `issues=[]`; each site passed
13/13 ports (11 ACTUAL_BLENDER + 2 SUBSTITUTE) and six media binary/hash/range/scope checks passed.
All three 1280×720, ten-second videos played without browser decode errors; the final console had
no warnings/errors, normal views hid opaque event IDs and original `.blend` SHA/size/mtime remained
unchanged. See the
[new receipts](../data/engineering/blender_motion_20261012/).
The same-day [Blender cross-camera reconstruction](engineering/BLENDER_CROSS_CAMERA_RECONSTRUCTION.md)
records independent site/run temporal, speed and floor constraints, distinct Top-K hypotheses,
the unassociated baseline and synchronized 3D/curve/video contracts. Office returns three candidates;
CLASS101 returns one baseline without cross-camera evidence; Auditorium returns three with explicit
beam truncation and no global-optimality claim. Original supporting projections, short inferred
transitions and long missing spans remain separate. Full-source ranking is distinct from windowed
display. Its [new receipt](../data/engineering/blender_association_20261012/validation.json) is separate
from camera-local history. All three curve PNGs/videos are materialized and fully decoded. Fresh
validation passed 3,067 Python tests, 110 Node tests, Ruff/mypy for 193 files, each site's 16/16 ports,
160 HTTP requests/450 assertions and three-site browser playback/synchronization. Original `.blend`
SHA/size/mtime remained unchanged; preceding milestone totals retain their historical scope.

The preceding physical checkpoint (2de9821) [source-authorized physical filter](engineering/BLENDER_PHYSICAL_CANDIDATE_FILTER.md) screens and reranks up to
256 candidates using approved partial geometry. All actual candidates remain UNKNOWN, with zero
hard rejection: Office reranks original3/4/2 into Top-3, CLASS101 keeps one baseline and Auditorium
retains its truncated Top-3. Approved apertures remain zero; long gaps stay missing and empty-body
baselines/ledgers also stay UNKNOWN. Fresh validation passed 3,140 Python and 122 Node tests (109 workbench + 13 product),
60/60 ports and 175 HTTP requests/501 assertions. V2 media fully decoded; actual three-site playback, clock handoff and the 9.8-second final-source cursor passed.
The [new receipt](../data/engineering/blender_physical_20261013/validation.json) records their own final scope. Historical PASS totals remain separate,
without Agent/GT decisions or original Blender opening/change/copy.

The user's latest decision makes workbench/8016 the unified primary web UI. Existing and
future presentation capabilities belong there; product/8020 remains a preserved engineering
lab and migration source. The E1 product investigation, video, case and report interfaces are integrated.
[Experiment coverage](engineering/WORKBENCH_EXPERIMENT_COVERAGE.md) retains the 2026-10-10
inventory of three scoped scenes and fifteen presentation families, with missing assets and formal blockers explicit.

The five folders separate specifications, engineering, research, operations and history. This is the only documentation index. The root retains the exact corridor review, the runtime checkpoint JSON and three symlinks required by locked protocol, review and geometry-report references; maintained text lives in the category folders.

For the Office Demo transition, see [AGENTS.md](../AGENTS.md), [CLAUDE.md](../CLAUDE.md), the [Claude initial handoff](operations/CLAUDE_INITIAL_HANDOFF.md), [MVP](agents/OFFICE_DEMO_MVP.md), [task sequence](agents/OFFICE_DEMO_TASKS.md), [Demo v1 guide](engineering/DEMO_V1.md), [selected-target API contract](contracts/OFFICE_DEMO_TARGET_V1.md), [fixture config](../configs/office_demo_fixture_v1.json), and [backend/Agent audit](engineering/OFFICE_MVP_AGENT_AUDIT.md).
