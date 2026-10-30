# CQ-37 長時間軸錄製資料投影

#332；接在 #255 `b871da423a2f672a8d245e6de9f85acba7ce7aef`，base 仍為 #243。

只讀既有 P1 可攜包 v4 的四個 JSON 檔，原始錄製、RGB、GT、劇本未複製到 repo，也未重跑產品。來源釘選與 LOCAL 截圖 hash 見 `docs/history/CQ37_LONG_TIMELINE_20261030.json`。頁面為 `frontend/workbench-v2/long-timeline.html`。

## 載入與邊界

1. 展開「載入 P1 v4 工程錄製」，逐一選取 MANIFEST、指定 RULE_ONLY 錄製、索引 manifest、clock；按「驗證並載入」。File API 只在瀏覽器本機讀取，沒有上傳。
2. 先核對已選定 v4 manifest bytes hash、每個成員 bytes/size，再核對 recording/index/clock/response/journal content pins 與 run/scene/clock/index 綁定。索引 content hash 依現行契約 §2.2 排除根 `content_sha256`、`index_id`；journal 逐列沿用 `checkDecision`。
3. 來源優先序是 #329 複雜事件正式凍結 → CX-8 r004 正式凍結 → P1 工程錄製。目前前兩者尚未交付/選定，維持 fail closed；可選 P1 ENGINEERING fallback，預設既有 SYNTHETIC 示例。不存在接受自行宣告 FORMAL 或自行提供核准 hash 的入口。
4. 錄製本身 source_kind=SYNTHETIC，畫面明示；不提升為 FORMAL。此支線仍使用 #243 的 v1 response validator，v2 未選定，拒絕；#305/#278 的配對整合與 A15 爭議不在此修改。

## 純投影

`projectRecordedTimeline` 只取 allowlist 欄位。每個 ON_CAMERA 引用 observation 以索引 interval 的來源格顯示，限於 segment、requested range 與 inferred coverage 的交集；未提供引用觀測的洞保留 UNKNOWN。GAP 僅來自錄製 timeline 並受 inferred coverage 限制；MISSING 僅來自索引 not_inferred.reason=MISSING；DETECTOR_FAILED、未宣告區域均 UNKNOWN。矛盾覆蓋拒絕，不猜。沒有 Q1 回應就不生成 Q1 clips。

accepted action 標記使用 decision_time_us，標籤另外保留 source_time_us；非 action 狀態標記使用 source_time_us。來源時間皆為整數 µs、半開區間。事件與狀態不建立身分或物理通行結論。`gt_track` getter 誘餌在根、response、timeline、index、sampling、clock、observations、decision 都不被純投影存取或輸出。原始 JSON 的完整性驗證只用選定公開錄製，沒有讀取 GT 檔案。

切換來源先解除 listener、停止 timer，載入錯誤隱藏舊 viewer。短錄製叢集聚焦使用適應 duration 的最小範圍，不再固定以 5 秒吞掉整個 8 秒錄製。

## 驗證

`AMIDST_REQUIRE_IMPL=1 node --test frontend/workbench-v2/long-timeline-data.test.mjs frontend/workbench-v2/timeline-model.test.mjs frontend/workbench-v2/monitor-wall-model.test.mjs` → 38 pass，0 fail，0 skip。

桌面內建瀏覽器：P1 8 秒、A/B 2 鏡頭、36 accepted events；叢集放大到 [875000,1875000) µs，縮小到 [750000,2750000)，下一事件移到 1250000 µs，A 由 OBSERVED 轉 GAP、B 保持 UNKNOWN。既有 8 鏡頭合成牆為 4×2、OBSERVED 4 / GAP 2 / MISSING 1 / UNKNOWN 1。無效載入清除既有示例；擷取的 warn/error log 0 筆。截圖為 LOCAL，未入 Git。

架構守門 NOT_RUN（#307 blocked-user、尚未交件）。#127 NOT_RUN：純 UI 投影，fresh_recordings=0。未驗正式複雜事件/r004、真實 8 鏡頭或長錄製、RGB、375 px、跨瀏覽器、完整無障礙、獨立 Claude 複審、AC7、發包。

## #337 接線

在 demo 模式加入相對連結 `long-timeline.html`；這是 #337 擁有的入口，#332 保留獨立頁，不改 Line 1 index/shell 行為。後續正式來源須有已交件凍結回應與合法來源釘選，不能靠本文件當 authority。
