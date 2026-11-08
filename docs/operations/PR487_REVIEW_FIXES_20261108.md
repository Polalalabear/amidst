# #445 / #487 審查修正與 D137（2026-11-08）

對照 [審查留言](https://github.com/Polalalabear/amidst/pull/487#issuecomment-6717576841)。所有「已修」以 Node、真實資料、合成 API、DOM／lifecycle、no-allow 架構守門及 diff check 的實跑證據為準。原始 UI `53953a81`、Codex 首輪 `a8c7066c`、Claude 腳本 `5862bb62`，以及 C 自有依賴 `29769639` 都保留；composition 在同目錄 JSON。沒有合併 PR，也沒有動 integration/mainline/main。

| 審查項目 | 狀態 | 實作與驗證 |
| --- | --- | --- |
| P2-1 底部 bar | 已修 | case2／case3 都是 min-height:100% flex，bar 放最後且留在 flow。固定 root 使用 clip，長查詢窗自己捲動。case3 transport 連到監控牆自己的播放、倍速與來源時鐘；舊引擎欄位留在隱藏引擎區，不被重建移除。1440×900／1440×1300 真實資料檢查初始與捲動後 bar 底邊和 viewport 底邊差 <2 px；只捲動內容。合成 gate 同時跑兩種高度並截圖。 |
| P2-2 結果牆 | 已修 | key 包含 output_sha256 與影響畫面的設定／錯誤／phase；選取卡片不重建 DOM，也不再要圖。合成 E2E 檢查原 image node 仍 connected，media grant 次數不增。lightbox 的晚回應不能蓋掉已改選的卡片。 |
| P2-3 停止／改選 | 已修（D137） | 停止只清前端播放、core response/view/selection；保留來源、無 backend stop 呼叫。改選按鈕 disabled，旁邊完整顯示使用者指定的自動種子說明；回查詢窗可重新追蹤。core wire 未變。手動指定種子依 D137 留在 D #489。 |
| P2-4 規格 §12 | 已修 | case1 圖片高度 300 px，與 CSS 一致。 |
| P3-1 CSS scope | 已修 | vars 僅宣告在 #ui-v1／.ui-admin-root；a 規則同樣限定 roots。Chrome DOM gate 比較 legacy 載入 ui.css 與阻擋 ui.css 的 body／text／link computed color，三者完全相同。 |
| P3-2 timer | 已修 | mountTabs 回傳 destroy，清除 interval/hash listener；admin bootstrap 提供 cleanup。DOM gate 同時測 mountUi 的 timers/subscriptions/listeners 全數清除及 mountTabs timer 清除。 |
| P3-4 mountUi DOM | 已修 | 真 Chrome iframe DOM 測 cover、chooser、表單驗證、D137 disabled controls、destroy 後 DOM／timer／listener／store subscriber 清空；不是只做 source string 比對。 |

`core-e2e.mjs` 驅動可見新 UI，合成警告保持可見，clean/head guard 開啟。`core-legacy-e2e.mjs` 與明確標示 legacy 的 real 53 gate 保留相容性證據，不能冒充新 UI 驗收。新的 real gate 也實測來源 RGB、跨鏡頭／多畫面、blind LOW/UNKNOWN、r005 R101/laptop 深連結、設定儲存與還原、lightbox 與 D137 停止後重新查詢。GAP/LOST 不因有曲線被升級成觀察。

## 可重現命令

環境與資產依 `DEMO_OWNED_DEPENDENCIES_20261108.md`。Python lock 已接入 #491 `fa9a199a` 原始交付，Mac 自有 runtime 是 3.12.12；合併後完整重跑結果與 8785 保持運行的交接見 `DEMO_PY312_LOCK_SYNC_20261108.md`。Node 與 browser 均用 repo 安裝的 Playwright。

```sh
./start_445_demo.command --port 8785
AMIDST_REQUIRE_IMPL=1 node --test frontend/workbench-v2/*.test.mjs frontend/event-viewer/*.test.mjs
# 分別將 height 設為 900、1300；output 各用獨立目錄。
CORE_SOURCE="$PWD" CORE_INTEGRATION_HEAD="$(git rev-parse HEAD)" \
 CORE_VIEWPORT_HEIGHT=900 CHROME_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
 SCREENSHOT_DIR="$AMIDST_ARTIFACTS/d135-487-mac-ui/final-synthetic-900" \
 node tests/browser/core-preview/core-e2e.mjs
UI_QA_HEIGHT=900 UI_QA_OUTPUT="$AMIDST_ARTIFACTS/d135-487-mac-ui/final-real-900" \
 node tests/browser/ui-redesign/real-e2e.mjs
UI_DOM_OUTPUT="$AMIDST_ARTIFACTS/d135-487-mac-ui/final-dom" \
 node tests/browser/ui-redesign/dom-e2e.mjs
```

最終 exact head、測試計數、每張圖的 bytes/SHA 與 LOCAL manifest hash 記在 #445 實際產出。大型原件／模型沒有變更；D137 的限制是使用者決定，不是未修問題的豁免。真人視覺驗收／主線合併仍由使用者決定。
