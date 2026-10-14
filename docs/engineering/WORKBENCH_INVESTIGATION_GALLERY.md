# 工作台人物調查與研究展示庫

> 目前操作入口： [demo 指南](DEMO_V1.md)與[全部工作／依賴交接](../operations/CURRENT_WORK_REPRODUCTION.md)。本頁固定埠號與日期化測試屬原 checkpoint；當次 URL 使用 `DEMO_URL`，不沿用歷史服務位址。獨立受限 Phase1 驗收見[最新正式報告](../research/PHASE1_FINAL_REPORT.md)，不擴大本頁來源／幾何權限。

本頁保留2026-10-10增量接入的 [共用工作台](SHARED_WORKBENCH.md) 契約與當時8016收據。
研究角色的「人物調查」重用已凍結 E1 product；「實驗展示」另有來源模型回放與
歷史圖表展示庫。三者分別保存來源與權限，不把歷史診斷圖當成新的 camera observations。
本頁記錄 adapter 契約；當次完整 regression、HTTP 與瀏覽器結果綁定
[整合收據](../../data/engineering/workbench_20261010/integration_validation.json) 及其所在 Git tree。

## 2026-10-14 現行示範與品質狀態

操作順序見[九分鐘本機示範](DEMO_V1.md)。歷史 prototype 已交付；本頁下方各日期的
素材數量、測試及瀏覽器結果保留原 scope，不代表當前素材仍在線或已重新驗證。
Office revision20、Classroom101 revision15，共35筆本機人工差異及核准後重跑已有紀錄；
Auditorium尚未核對，38個物理檢查仍為UNKNOWN。現行人工核對契約見
[Blender來源核對](BLENDER_PHYSICAL_HUMAN_REVIEW.md)。

Phase2功能工作量暫估約50%，05維持baseline；11仍為`QUALITY_GATE_NOT_MET`。
R2完整48題的常規通過12／40（中文7／20、英文5／20），安全邊界8／8，模型乾淨拒絕
僅2／8。已凍結R3 context工程3736項及68項隔離HTTP／PG守門通過，後者0次真實模型；
一次current v4實際demo失敗已保留。schema／提示仍是未套用的私有候選，R3的48題
重播尚未開始。精確收據及當前限制見[05／11修正](PHASE2_LOCAL_REPAIR_0511.md)；
工程及fixture通過不提升模型品質認證。

舊v2／v3的`VERIFIED_DTO_FIELDS` literal證據保持可讀，舊execution只讀、需求完成度
`NOT_CHECKED`；既有v3案例的同源欄位核對不升級current語意驗收。工作台context仍需
原PG儲存與本機Ollama模型識別守門，保存案例的讀取也要備妥這些依賴。

## 示範前置與啟動

GitHub clone提供程式、公開收據及fixture；Office／E1／accuracy-v2的RGB與checkpoints、
模型權重、PG與人審狀態均是ignored本機依賴，不能由clone直接重現現有示範。
`--offline --no-sync`使用已準備好的環境，不安裝缺少依賴。現行演示讀取既有素材；
素材缺失時明示不可用，不建立新RGB或推論產物。

在具備原依賴的checkout啟動：

```sh
export PYTHONPATH=src
DEMO_PORT=${DEMO_PORT:-0}
UV_CACHE_DIR=/private/tmp/amidst-uv-cache uv run --offline --no-sync \
  python -m amidst.workbench --repo "$PWD" --port "$DEMO_PORT"
```

`DEMO_PORT=0`讓OS分配空閒埠。另一終端以本次Python服務PID作為`DEMO_PID`，讀取
`lsof -nP -a -p "$DEMO_PID" -iTCP -sTCP:LISTEN`取得實際listener埠，將該值填入
`DEMO_BOUND_PORT`，再設定`DEMO_URL="http://127.0.0.1:$DEMO_BOUND_PORT"`供瀏覽器使用。
CLI印出的0是請求值，不是可瀏覽的address。清理或刪除綁定checkout後，舊絕對locator
須標為offline；重新執行需另行rebind，目前沒有portable replay實作。

## 2026-10-13 · 核准的 01–03 工作台接入

本輪只實作共用範圍接續、accuracy v2 調查 adapter、既有 v2 評估認證與比較，入口維持 8016。
完整驗證結果見[本輪收據](../../data/engineering/workbench_010203_20261013/validation.json)及
[WORK_LOG](../history/WORK_LOG.md)：Python3222、Node183、Ruff／strict mypy201檔、
隔離HTTP86請求／939斷言及8016瀏覽器驗證PASS；下方2026-10-10功能及測試仍是歷史範圍。

| 核准項目 | 操作與資料契約 |
| --- | --- |
| 01 範圍接續 | 共用場景/source run、鏡頭、時間窗及來源游標帶入調查；返回共用工作區或經中間頁返回時重新查詢相同範圍。切場景、照片模式及範圍清除過時 evidence/plan/report 與晚到請求；已保存案例只能恢復同模式/freeze 的合法原範圍。 |
| 02 v2 調查 | E1 product 與 accuracy v2 依 scene 分別路由。v2 從兩種原凍結模式取得 registered observations/events/media，另綁 experiment/variant/config/original freeze；只追加獨立 CASE/REPORT/REVIEW，原 canonical rows 留在記憶體，原 source 不回寫。 |
| 03 v2 評估 | 獨立核對既有比較內容 pin、manifest 及 16 組 variant/mode freezes，僅研究 evaluation 端點取得有限 aggregate DTO；畫面列出分母、母體 hash、回歸與 N/A，只對相同母體畫 Recall@1 比較。 |

v2 僅提供 TRACE/BEHAVIOR、來源影格時間軸、保存案例與報告。Appearance/stitch/MP4 未由此 adapter
提供，按 capability 關閉；沒有新增多人事件。來源 SUPPORTED/UNKNOWN/GAP_ALTERNATIVES 在事件
及獨立 hash 的 case/report 補充中保留，仍不確認 global identity、人的意圖或 physical authority。
E1 的已存在功能保留原契約。無對應 certified adapter 的場景沒有調查入口。

資料路徑為 `原 frozen v2 artifacts → read-only adapter → 有界調查 → 獨立案例/報告 ledger`；
評估另走 `既有 comparison → 獨立內容/來源認證 → bounded aggregate → 研究比較面板`。
兩者不使用 GT 或 evaluator sidecars 提供調查答案，沒有產生新的推論、研究 evaluation、曲線或影片。
缺失、變更內容、錯 run/config/freeze、未認證來源及 stale overlay 均拒絕或明示 STALE/UNAVAILABLE。

2026-10-13此checkpoint當時暫緩07、08、10的多人事件、13、14、15；04、05、06、09、10的其他部分、11、12
當時需再次確認才能開始。該checkpoint不提供新run執行入口、演算法改善、真實攝影機、模型API、正式DB、帳號或部署；
後續授權及現行限制分列於[05／11修正](PHASE2_LOCAL_REPAIR_0511.md)，不改寫這份歷史scope。

## 人物調查：既有 product 的外層接入

[`ProductBridge`](../../src/amidst/workbench/product_bridge.py) 將工作台的 server-owned
研究 session 綁到已註冊的 `local-camera` 場景和獨立 product freeze。
它核對兩個已凍結照片模式的 scope、source/model/run、camera calibration、frame metadata、
原 freeze、product record-set receipt 與 video manifest；缺少或失配時不改用其他場景。
E0 的 `synthetic-lab` 沒有這個 E1 product，能力應顯示不可用。

此接入支援以下既有本機操作：

- 有限 camera/time 查詢、局部人物片段、pixel crop 外觀查找、同鏡頭恢復假說。
- `TRACE`／`COMPARE`／`BEHAVIOR`／`MULTI_TARGET` typed plans、逐步執行、停止、續跑、保存案例。
- 全部候選與替代、report hash review、獨立結果判定和 HTML report 匯出。
- 四鏡頭 MP4、主鏡頭、播放速度、seek、soft-sync 診斷與來源影格 offset。

這些操作讀取已凍結結果、執行有限工具計畫及保存調查紀錄；不執行新的 CV、association
或 benchmark。`inference_execution=false`。照片模式選擇只選取各自已驗證的 frozen outputs，
caller 不能宣告 INPUT／RESULTS、替換內部 product session、跨 mode 使用 plan 或繞過 freeze。
場景 annotation、事件人審與 report review 分開保存，不改 canonical observations 或確認人物身分。
查詢完成、plan 結束與完整 exhaustive inventory 是不同狀態，截斷及未完成原因須保留。

外層 action 為 `product_context/tool/intent/execute/plan/case/cases/report/review/videos/timeline/`
`export_report`；binary 路由為 `/api/product_media`、`/api/product_video`。
每次先核對工作台 role/session/scene，再使用原服務允許的 refs 與 tools。
HTTP payload 不包含 product manifest 的本機 source/video-pool locators；影片只返回 opaque refs。
細節見 [既有產品契約](LOCAL_PHASE2_PRODUCT.md)，不是新 Agent semantic reranking。

## 來源 clock 與人體顯示

E1 仍是 `SYNTHETIC`：244 個實際 RGB refs、四鏡頭、來源／CV 2.5 Hz。
15 fps MP4 是既有影格的 hold presentation，不增加照片、量測、可見證據或推論時間點。
同步診斷與 presentation clock 不能替代 source timestamps，也不能用來估計辨識精度。
人形、朝向與步態為 `DISPLAY_ONLY`；它們不表示測得骨架、動作、人物身分或 GT 軌跡。
3D 可見投影、GAP 候選及 HOLD 使用原服務輸出的合法量測／幾何衍生結果，保留所有替代。

原校園 Office「模型與行走」是另一個 source/context/clock/unit binding。
其 50 格、5 Hz、0–9.8 s 公開 body-base／landmark 和三條原 GAP 路徑維持
`image_measurement=false`，不能改稱 pixel-derived CV。模型展示 PNG 和 4／5／9 s camera audit
stills 也不是連續 camera RGB sequence。裁切 mesh 與人體僅供顯示，不擴大 geometry、portal、
walkability 或 collision authority；native BU 的 0.0247 m normalization 不回寫原 bytes。
來源認證與原校園邊界見 [來源展示契約](SOURCE_PRESENTATION_WORKBENCH.md)。

## 展示庫：固定十五家族

[`Gallery`](../../src/amidst/workbench/presentation_gallery.py) 只索引已核對的有限路徑。
`list()` 回固定家族索引、`detail(family_ref)` 回精簡表格／圖 refs／存在狀態，
`media(media_ref)` 只回驗證過的 PNG bytes。根目錄由 server 配置，不接受 caller 路徑。
`gallery_list`、`gallery_detail` 及 `/api/gallery_media` 全部限定人類研究角色；沒有加入 Agent
allowlist，也不提供 filesystem、SQL、shell、source archive 或 arbitrary media 工具。

下表是本次實際 assembly 的數量，不是重新跑實驗。`E` 是工程 checkout，`C` 是唯讀原素材
來源；C-only 素材沒有複製進 E。未提供 canonical root 時，其入口明示不可用。

| 家族 | 已核對展示素材 | 表格／限制 |
| --- | --- | --- |
| E0 simulation-v2 | E：1 PNG、1 RRD 狀態 | 兩照片模式的兩列工程摘要；affine camera pose 仍 UNKNOWN |
| E1 local-camera | E：7 cards PNG | 兩模式 × 四個固定候選池消融，共八列；不能與 product population 混算 |
| P7–P12 product | E：4 MP4 狀態 | 兩模式 appearance／stitch aggregate，共兩列；互動影片走人物調查 |
| Reviewed Office recovery demos | E：2 PNG、2 RRD 狀態 | Case1／Case3 局部 temporal 結果，full gates 仍 BLOCKED |
| Recovery benchmark／消融 | E：37 PNG | 27 baseline＋45 ablation rows，保留原 BLOCKED／N/A |
| Historical reviewed V5 | E：20 PNG | 27 rows；兩 preview PNG＋兩 RRD 缺失，PARTIAL |
| Office／auditorium／corridor diagnostic | C：6 PNG、6 RRD 狀態 | GT_DEBUG_ONLY；不讀其含 debug 資料的 presentation JSON |
| School downstream 3D pilot | C：1 PNG、1 RRD 狀態 | GT_DEBUG_ONLY；歷史圖片含 GT debug markers，不能進主展示 |
| School rendered pilot | C：16 PNG、2 GIF 狀態 | GT_DEBUG_ONLY；人工／軌跡標記不是未標註 CV input |
| Human-review／四格 preview | E：59 PNG | 原 50 sequence PNG＋八 audit stills＋一 topology；VIEW_ONLY |
| Projection upgrade／mitigation | 無可用 plots/results | 兩個固定 verified-run 位置缺失；存在空目錄也不算結果已物化 |
| Native／mock benchmark | E：28 PNG | native 四列與 mock 21 列分開；SYNTHETIC REGRESSION／MOCK VALIDATION |
| 原 blocked checkpoint | E：8 PNG | 27 historical NOT_RUN／N/A rows，不覆蓋 recovery 結果 |
| Legacy four-case Rerun | C：4 RRD 狀態 | GT_DEBUG_ONLY；低階 mock IDs 不公開，stair fixture 不解鎖 Case4 |
| Research accuracy v2 | E：7 cards PNG | 三列 published test comparison；end_to_end/photos_only 卡片、SUPPORTED／UNKNOWN／GAP_ALTERNATIVES 保留 |

原十四家族 **185 PNG** 完整保留；新增七張 v2 cards 後，總數為 **192 PNG、14 RRD
存在狀態、4 MP4 存在狀態**，另有兩筆 GIF 狀態。
原 preview manifest 的 58 張圖片全部驗證，其中原 sequence 50 格完整；topology 圖獨立計數。
各 PNG 在 assembly 保存實際 SHA，media 每次重驗 hash。未知 model/source/authority 保持
`null`；名稱、檔案存在或灰色 mesh 不構成 calibration／coverage／region authority。
RRD／MP4／GIF 不在 Gallery 開啟、解析或提供 bytes，只有 `EXISTENCE_ONLY/STATUS_ONLY`。

`complete=true` 只表示這十五個固定家族的索引完整，不表示所有素材存在、query 成功、
dataset／benchmark 完整或正式研究通過。`MATERIALIZED` 描述展示素材存在；`PARTIAL`、
`NOT_MATERIALIZED` 和 `CANONICAL_ROOT_UNAVAILABLE` 保留缺項。CSV 超過 128 列明示截斷；
原完整 canonical 表與結果仍另存。

Research accuracy v2 使用已發布的
[curated validation](../../data/engineering/accuracy_20261010/validation.json)，固定 content SHA 為
`01639e15c8ca3a7d66c36ffaf2e464e2180189b737cfe8a9625b072b2dc21555`，由 server code 認證。
Gallery 核對新 experiment `accuracy-test-v2-final`、原 source run `local-camera-test-v1`、
dataset/source/context/config/clock、八 variants × 兩 modes 的原 freeze receipts，
以及 published evidence 與 cards manifest 的 content hash。缺失或失配明示 PARTIAL；
不 follow manifest 的 private `source_locator`，不讀 GT、完整 evaluation/debug 或 remaining errors。

三列比較取自已存 `photos_only` 評估。Baseline／features_full 保持原 tracks、115 pairs；
end_to_end 是新 21 tracks／327 pairs 的另一 population。Recall@1 的 .375／.625／.850
不能合併宣稱同一 population gain；pair precision／recall、contact error、UNKNOWN 和候選數
亦保留原量測。V2 不是 sealed holdout、trained ReID 或 formal research freeze。
七張 cards 綁 end_to_end/photos_only freeze；每張含三至五個已有 source RGB 和合法 3D
投影／候選，`gt_overlay=false`，卡片本身是 presentation，不是新的 CV input。
研究設計、消融與退步見 [Accuracy v2](../research/LOCAL_CAMERA_ACCURACY_V2.md)。

## GT debug、錯誤與發布邊界

所有 Gallery 家族皆為 `normal_presentation_allowed=false`。
預設研究診斷頁排除 `GT_DEBUG_ONLY`；使用者需另選「GT debug（獨立）」才看歷史 debug PNG。
這些圖片可能含 GT／人工標記，僅供人類理解歷史研究，不進來源模型主展示、人物調查、
pixel producer、association 或 Agent tools。圖片標註未知時不宣稱無 GT overlay。
Gallery 不開 GT sidecar、完整 presentation JSON、source archives 或 raw media container。

允許回傳的表格欄位與 aggregate DTO 有明確白名單；額外 identity、private locator 或 raw
metadata 不返回。PNG／JSON／表格有 byte、尺寸、列數與總圖片 budget；未知 refs、路徑逸出、
symlink、非法素材及 media hash 改變均 fail closed，錯誤不帶本機路徑。
前端轉義 metadata／表格文字，research/debug detail 以同一 serial ticket 控制；切 audience、
更換 family、離開頁面或 session 變更後的成功／失敗回應均不能覆蓋當前顯示。

發布只保留允許的程式、文件與 curated receipts。192 張 PNG、MP4、RRD、GIF、source archives
和 GT debug assets 的本機存在不授權上傳、copy 或 rerender。本輪保持原素材 bytes。
原 Phase 1 formal Cases 1–3、fresh 5 Hz frozen dataset、獨立 exhaustive inventory、full evaluation
與 clean-checkout reproduction 仍是獨立研究工作；未量測為 N/A，Case4 DEFERRED。

## 已驗證與待證

原十四家族 Gallery 專項 16 tests 通過。Accuracy v2 增量後，當次專項 **30 tests PASS**，
Ruff／mypy PASS；污染、缺失、scope/mode/variant/card manifest 和 GT poison 邊界均涵蓋。
實際 assembly 在禁止 GT sidecar／debug JSON／archive bytes 讀取的 guard 下核對十五家族／
192 PNG，每張 media hash 重驗成功；歷史 GT_DEBUG_ONLY PNG 仍只屬獨立人類診斷分類。
前端 Gallery 的三個 Node tests 通過，另以 deferred harness 核對：較晚成功回應與較晚錯誤
回應均不能覆蓋新的 family／audience。這些是 adapter／UI 邊界證據，不是 benchmark 重跑。

最終無排除 `pytest --require-physical-evidence -rs` 為 **2873 passed／0 failed／0 errors／0 skipped**。
Ruff src/tests、strict mypy 183 source files、workbench 45＋product 13 Node tests 均 PASS。
63 次實際 HTTP 涵蓋三場景、兩照片模式、角色／stage／ref／scope 拒絕、影片 Range、
十二個 product actions、展示庫與來源模型；逐檔 code/config/source hashes 見整合收據。

實際瀏覽器確認原模型／人體／三候選、逐格／seek／尾段／速度／循環、四鏡頭影片，
以及雙 seed MULTI_TARGET plan 的停止／續跑／完成與 HTML 匯出。此 plan 執行十八次有限工具，
保留四十二替代、九衝突與 UNRESOLVED_PROVISIONAL 身分。Recovery 表格 27／45 列、
v2 三列比較與七 cards 實際顯示。影片同步為 soft-sync，來源仍 2.5 Hz，未據此宣稱精度提升。
原 Blender SHA／size／mtime 不變；先前失敗測試與 P14 receipt 保留，未回寫歷史 PASS。
舊盤點日期的功能缺口見 [實驗展示覆蓋表](WORKBENCH_EXPERIMENT_COVERAGE.md)，本頁是其增量接入契約。

## English scope note

The counts and receipts below describe the historical October 10–13 prototype. Follow the
[nine-minute local demo](DEMO_V1.md) for current operation and the
[05/11 repair record](PHASE2_LOCAL_REPAIR_0511.md) for current limits. Phase2 remains about 50%:
05 keeps its baseline and 11 has not met its quality gate. R2 passed 12/40 regular tasks
(7/20 Chinese, 5/20 English); safety containment was 8/8, with only 2/8 clean model refusals.
The frozen R3 context engineering run passed 3,736 checks and 68 isolated HTTP/PG guards used
zero real-model calls; the first current-v4 actual demo failed and is retained. The private
schema/prompt candidate is unapplied and the R3 48-task replay has not started. Old v2/v3
literal verification remains readable, with read-only execution and goal completion NOT_CHECKED.
Existing RGB/checkpoints, model weights and PG/review state are local dependencies absent from
a GitHub-only clone. Use the dynamic-port command above; port 0 requires reading the actual
listener with lsof and set DEMO_URL from that port. Retired absolute source locators remain
offline pending a separate rebind.

The shared workbench composes the independently frozen E1 product for human research investigation
and a bounded, read-only fifteen-family gallery. It preserves source clocks, modes, IDs and
alternatives. The original 185 PNGs remain; seven certified v2 review cards bring the total to 192.
Legacy RRD/MP4/GIF entries expose existence status only. V2 comparison uses photos_only and reports
the changed end-to-end population separately.
GT debug remains a separate human diagnostic view, with no Agent or inference access. These adapter
checks and the full 2873-test integration run do not certify formal Phase 1 research. Exact code,
configuration, HTTP and browser evidence are bound by the integration receipt above.
