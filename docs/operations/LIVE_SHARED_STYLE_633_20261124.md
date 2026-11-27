# #633 stage 2 — Codex-L delivery

狀態：Codex 已完成，待 Claude 審查（後端／LIVE內部部分）。
基底 main `d52ce2f0`，分支 `codex/feat-live-style`；**E5／AO-L 結束前不合併**，
因 server.py 來源SHA會改變B1快照。無部署／重啟8791／8785 pin變更。

## waiting:codex 的原因與解除

#633原本等#617合併，以免重疊operator與server檔案；已確認#617於2026-11-22合併，
merge `1742ed06535a588e3cec96acd9ef345f9a57263e`。現在Codex交付server路由與LIVE內部樣式，
不再等待#617。合併時仍須遵守E5限制與使用者核准。

## 已交付

- `/shared/tokens.css` 直接讀取版本控制中的 `frontend/workbench-v2/tokens.css`。
  LIVE index保留相容 `/src/tokens.css`，此URL也讀同一來源，不讀LIVE鏡像。
  只開單檔路由，不提供workbench目錄；路徑穿越／其他shared檔案404。
  shared檔缺少時404，不悄悄改用舊鏡像。
- LIVE operator的A/B選單尺寸／排版／選取外框與map toggle改class／CSS。
  選取使用原aria-pressed，不改選人、錄製或重播邏輯。
  動態角色色保留唯一 `--actor-swatch` custom property，值仍來自原GLB metadata，未硬編碼角色色。
- LIVE system map移除固定inline CSS尺寸；live.css移除全部!important，保留原後置樣式與響應式map設定。
  原LIVE重播上傳頁的padding未改（本次不碰預錄模式）。

## 留給Claude／檔案邊界

本次沒有修改 `frontend/workbench-v2/` 任何檔案，共用token值與ui.css不用改。
舊 `frontend/live-mode/src/tokens.css` 已不被LIVE index／server讀取，但暫留檔案，
因 `frontend/workbench-v2/tokens-css-mirror.test.mjs` 還把兩份全文相同當成契約。
首次CI指出它也硬認index的/src/tokens.css；現保留此URL並由後端alias共用原檔，未修改workbench測試。
Claude後續應以「LIVE server兩個URL回共同來源」取代鏡像契約，再依使用者刪檔規則退役舊鏡像；
後續若要改URL，再由Claude同步更新 `tokens-css-mirror.test.mjs`／相關 `ui-model.test.mjs` 斷言。
這些workbench測試屬禁止修改範圍，
未在本PR編輯；不宣稱鏡像已從Git刪除。#633整項先不關閉，仍待Claude與UI確認。

## focused verification

```sh
PYTHONPATH=src uv run --offline --no-project --python <existing-env>/bin/python python -B -m pytest tests/live_mode/test_shared_tokens.py -o addopts='' -q
node --check frontend/live-mode/src/operator.mjs
node --check frontend/live-mode/src/system.mjs
node --test frontend/live-mode/test/ab_menu.test.mjs frontend/live-mode/test/hud.test.mjs
git diff --check
```

結果：Python 1 passed（單一共享來源、舊URL alias、source更新、缺失與路徑穿越）；
Node 28 passed、0 failed、1 skipped（GPU browser menu測試，未設定LIVE_AB_BROWSER）；
兩個node syntax check與diff-check PASS。Node依賴唯讀沿用既有runtime node_modules，未安裝或複製。
Artifacts：NONE。沒有開可見瀏覽器、沒有影像／資料外傳。
未驗證：實際GPU menu瀏覽器／截圖與pixel等價、完整前端套件、8791部署及與#690／#703整合。

## 第三段（2026-11-27）：部分退役

決定（使用者，2026-11-27，選項卡「部分退役後關 #633」）：非凍結的伺服器全部改讀正本
`frontend/workbench-v2/tokens.css`，鏡像 `frontend/live-mode/src/tokens.css` 不刪。

- 改讀正本：`src/amidst/live_mode/server.py`（第 502 行，#705／#739 已做）、
  `frontend/live-mode/test/ab_flow.test.mjs`、`ab_menu.test.mjs`、
  `frontend/live-mode/measure/n6_ceiling_compare.mjs`。三個新改的只對 `/src/tokens.css`
  這一個檔明確導向，不開放整個 workbench-v2 目錄。
- 保留鏡像的原因：E3 凍結錄製器 `scripts/evaluation/e3_cases/record.mjs` 用自己的靜態伺服器從
  `frontend/live-mode/src/` 讀 `/src/tokens.css`，而它的 SHA 釘在
  `configs/evaluation/e3_reappearances_v1.json`（producer 雜湊 `8b6d467b…1750`），不能改。
- 鏡像保留到 E3 凍結解除，或錄製器重新登記為止；在那之前
  `frontend/workbench-v2/tokens-css-mirror.test.mjs` 仍要求兩份一字不差，並檢查除 `record.mjs`
  外沒有其他伺服器把 `/src/tokens.css` 解析到鏡像。
