# Q2 review 俯視圖 403 診斷（2026-11-03）

本診斷綁定 `mainline/q1q5@ae1faf373bfd1453b74c971957fd6998e344ca16`，
起點為 [#404 留言 P3-b](https://github.com/Polalalabear/amidst/pull/404#issuecomment-6598528320)。
**建議 demo 後再處理；本 PR 不加入 11-04 demo 前的合併批次，也不授權合併。**

## 根因與判定

這兩個 403 在路由入口發生，尚未執行 authority、scene/run scope 或 session artifact 檢查：

- `src/amidst/q1q5/api.py` 的 `POST_ROUTES` 沒有 `q_camera_map`、`q_physical_prediction`；
  `QAPI.call()` 立即以 `FORBIDDEN_DATA_SCOPE` 拒絕，WSGI `dispatch()` 亦有同一白名單。
- `p1_workbench.P1.call()` 除了建立 session，其他 action 都直接交給 QAPI。
  因此 P1 HTTP 與 WSGI 均能用合法的合成 session 重現 403。
- `demo_launcher.RecordedAPI` 在 QAPI 之前還有唯讀白名單；同兩個 action 在這條路徑回
  `409 RECORDED_READ_ONLY`。這是另一個入口，不能將它寫成 Claude 現場量到的 403。
- 該 base 沒有 `camera_map.py`；`physical_prediction.py` 的純函式已存在，但尚未接到
  session／run 綁定的 HTTP 路由。`DEMO_UI_SUPPORT_V1.md` 仍是 PROPOSED，既有
  `test_demo_camera_map_t.py`／`test_demo_physical_route_t.py` 的 helper 在未實作時 skip。
- [#403](https://github.com/Polalalabear/amidst/pull/403) 修的是已存在的 `q2_artifact`
  對相同 hash／相同內容重複項目的拒絕，與本問題不同。

拒絕未知路由的安全預設是預期的 fail-closed；本次確認的整合缺口是 UI 呼叫的兩項能力
尚未接線，且不可用功能被報成權限錯誤，造成前端持續重試。不能藉此放寬授權，
也不能把缺失路由解讀為圖或物理權限已核准。

## 現場可見影響

`frontend/workbench-v2/track-map-data.mjs` 對兩條失敗路徑都回退到
`fixtures/track-map/synthetic.json`。`track-map-view.mjs`／model／render 會明示
「SYNTHETIC／待接後端 · 鏡頭圖／預測介面尚未接後端」。

- 主攝影機 RGB、時間軸及 Q5 已錄製決策使用其他 API；這兩條失敗不會改寫它們。
- 打開俯視圖時，顯示的是 fixture 的節點、拓撲及 prediction table，並非來源綁定的
  camera map，也沒有執行 `predict_next_cameras`。例如合成 run 只有 A/B 時，fixture
  仍有 A/B/D/E 與 A→B 的 MEDIUM 虛線。看得到圖與線不能當作後端能力驗收。
- map 對同一 scope 先取一次並快取；換 Q2 response 會重設 map key／cache。
  physical 則隨 store 更新經預設 250 ms 節流反覆請求。因此不是兩路每格各呼叫一次。
- `MISSING={404,405,501,503}` 不含 403，故 physical 的 403 不會停止重試。
  關閉／隱藏 dock 也不會停止目前的排程。

本次只有讀碼、合成 API/HTTP 與前端 adapter/model 檢查，沒有重新做真資料瀏覽器驗收。
若 demo 要展示來源綁定地圖或真正的物理預測，目前仍未交付；本 PR 不補做這兩項功能。

## 此 PR 的小修

獨立的 `UNAVAILABLE_POST_ROUTES` 僅識別這兩條 error-only 路徑。合法請求經過原有
非 audit 授權後回 `503 Q_RESOURCE_UNAVAILABLE`，不回成功 schema、圖、觀測或預測：

- map：exact payload、有效 scene/run 字串、fresh authorization 與已設定的 run。
- physical：exact payload、非負整數來源時間、`(session_ref,response_ref)` 本人所有的
  Q2 v1/v2 response，以及 fresh scene authorization。
- 非法 session／foreign scene／跨 session response 仍為 403；無效輸入與禁用鍵仍為 422；
  未設定 run 仍為 `503 Q_RUN_NOT_CONFIGURED`。未知 action 與 transport 防護維持拒絕。
- 錄製唯讀 wrapper 只讓上述 error-only 路徑交回 QAPI 驗證；新推論仍回 409。
- 兩條路徑仍不在已實作的 `POST_ROUTES`，既有 -T helper 仍判定功能缺失。
  `ROUTES` 表示可 dispatch 的路徑，不表示功能已完成。

現有前端收到 503 會將路由標成不可用，停止後續請求。**第一次 503 仍可能出現在 console；
這是降低重複錯誤，不是保證 console 沒有錯誤。SYNTHETIC fallback 的可見內容維持。**
沒有修改前端、純演算法、圖／schema／參數或 authority；沒有啟用模型、讀 key、讀原始媒體或渲染。

後續完整接線需另交付 source-bound camera map、截至來源時間的 observation 組裝與相關 -T
驗收；backend 模式是否應停止使用 fixture、改顯示明確不可用，需交由前端 owner 另案處理。

## 驗證與重現

使用 `tests/q1q5/test_review_ui_unavailable.py` 的 SYNTHETIC fixture，無資料包、媒體或模型。
新增 8 個合法請求目標案例在修前全部失敗：P1／WSGI／直接 QAPI 得 403，wrapper 得 409。
修後的新測試及三份相鄰 focused tests 共 **96 passed**：

```sh
env -i PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  UV_CACHE_DIR=/private/tmp/amidst-demo-launch-uv-cache \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  uv run --no-project --offline --python /opt/homebrew/bin/python3 \
  --with pytest==9.1.1 --with pillow --with pydantic==2.13.5 \
  --with numpy==2.5.3 --with networkx==3.7 --with 'shapely>=2.1.2,<3' \
  --with 'matplotlib>=3.10' python -m pytest -q \
  tests/q1q5/test_review_ui_unavailable.py tests/q1q5/test_api.py \
  tests/q1q5/test_demo_launcher.py tests/q1q5/test_p1_workbench.py -o addopts=''
```

`--offline` 需對應 uv dependencies 已在 cache；`env -i` 清空繼承環境，沒有取得或印出 key。
首次修後測試 90 passed／6 failed 是新測試誤假定禁用鍵一定直接拋 APIError；既有
StoreError 由公開 WSGI 邊界映射為 422。測試已改驗 HTTP status/error body，沒有放寬實作。

以下是 adapter 的合成重現，可在 repo root 執行，沒有網路或媒體讀取：

```sh
node --input-type=module <<'JS'
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createTrackMapData} from './frontend/workbench-v2/track-map-data.mjs';
import {buildScene} from './frontend/workbench-v2/track-map-model.mjs';
const fixture=JSON.parse(fs.readFileSync('frontend/workbench-v2/fixtures/track-map/synthetic.json','utf8'));
const timeline=[{kind:'ON_CAMERA',camera_id:'A',range_us:[0,1000000]}];
for(const status of [403,503]){
  const calls={map:0,physical:0};
  const adapter=createTrackMapData({fixture,getSession:()=> 'SYNTHETIC_SESSION',fetchImpl:async route=>{
    calls[route.endsWith('q_camera_map')?'map':'physical']++;
    return {ok:false,status};
  }});
  let map,physical;
  for(let i=0;i<4;i++){
    map=await adapter.cameraMap({scene_id:'SYNTHETIC_SCENE',run_id:'SYNTHETIC_RUN'});
    physical=await adapter.physical({responseRef:'SYNTHETIC_RESPONSE',asOfUs:500000+i*10000,timeline});
  }
  assert.deepEqual(calls,{map:1,physical:status===403?4:1});
  const scene=buildScene({cameraMap:map.doc,physical:physical.doc,timeline,tUs:600000,
    runCameraIds:['A','B'],origin:'SYNTHETIC',sourceNote:'鏡頭圖／預測介面尚未接後端'});
  assert.deepEqual(scene.nodes.map(n=>n.camera_id),['A','B','D','E']);
  assert.equal(scene.predicted[0].confidence,'MEDIUM');
  console.log({status,calls,origin:map.origin,notes:scene.notes});
}
JS
```

結果：403 對照 map=1／physical=4；503 map=1／physical=1；兩者都保留 SYNTHETIC 圖。
沒有執行全套 Python tests、正式研究實驗、真正地圖／預測功能驗收或 demo 批次合併。
