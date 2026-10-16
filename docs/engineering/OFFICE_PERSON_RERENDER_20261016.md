# Office 人形尺寸圓柱獨立重渲染（2026-10-16）

Model / effort：**gpt-6.1-sol / high**（實際 session 值）。依 #25 D4–D6 與本次使用者
「Office 重渲染不受影響，照常進行」執行；[PR #34](https://github.com/Polalalabear/amidst/pull/34)
尚未合併。**只渲染 Office 原路線，基準候選與五條對照都未渲染。**

- 新 run_id：`blender-contact-control-office-person-20261016-v1`。
- 純圓柱高 **1.70 m**、半徑 **0.25 m**；新增 renderer 分支不附加舊 capsule 的球頭。
  兩個 renderer 測試確認 exact depth／radius 與不產生頭球，原 capsule 路徑不改。
- 舊 Office 50 個 foot_position、0.0–9.8 s／5 Hz、相同兩台 FRONT／REAR 均保持，
  只在新 plan 設新目標／run_id／trajectory id。未覆寫舊 run、來源 `.blend`、RGB、GT 或校正。
- 原路線設定速度 0.3952 m/s，作為「同路線尺寸診斷」，不混入 C6 基準 `[1.0,2.0]` m/s 設定。
- 100 PNG，960×540、RGB，render exit 0；來源 hash／size／mtime 前後相同。
- dataset SHA-256：`b950101fdbfb5e6b15ebe0bc28c31318e53884eb3a625419db647105aba71275`。
- safe inputs SHA-256：`e9aff43f08955222348407a3435baff05c8a38f6638226a1bd43dc544836c998`。

採 `pilot_workbench_opaque_studio_v1`，來源 evaluated viewport mesh snapshot／OBJECT 不透明灰色、
橘色合成圓柱。這不模擬來源玻璃／alpha 材質，也不是寫回 `.blend` 的場景變更。
來源 source SHA 是 `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`，
468300506 bytes、mtime_ns 1791198236746106977。

## 感知結果與工作台接線

只使用 allowlist 的 source camera/time/media、RGB 與獨立合法 floor/calibration；
perception 沒有讀取 renderer GT、trajectory、visibility 或 depth。
逐 run [perception 設定](../../configs/office_person_contact_v2.json) 宣告 1.70 m／0.25 m；
[fixture](../../configs/office_demo_office_person_fixture_v1.json) 綁定設定 hash。
後端新增 hash 檢查和逐 fixture config；launcher fingerprint 納入該 config，不改既有 Office 的設定。

v2 偵測 **33 個元件，接地投影 0**：33 個 `LOW_INCIDENCE`，其中 4 個還有 `CONTACT_OCCLUDED`。
原指定 FRONT 4.4 s 與 REAR 8.6 s 都偵測到 RGB 元件，但位置保持 MISSING／LOW_INCIDENCE。
縮小高度並不改變原腳點射線的低 incidence，不能宣稱混合估計器或 K1 已可用。
新 run 的品質旗標保留在 LOCAL `contact_quality.json`；API 的被拒絕點按既有 v2 契約保留
`state:MISSING`／`missing_reason`，不偽造 PASS、不選替代端點、不插值或 snapping。

可選的[三場景預設](../../configs/office_demo_presets_person_v1.json)保留原預設，另加
`blender-office-person`。程序內載入驗證：三場景可載入、100 媒體 hash 通過、舊／新
frame_ref／observation_ref 沒有交集、33 個 MISSING 原因保留；新 run 未物化的 motion／association／
physical 層標示 UNAVAILABLE。未啟動或停止任何 Demo／PG／Ollama 服務；沒有宣稱瀏覽器 readiness。

需要顯示時，在已提交且工作樹符合 launcher 條件後，可使用：

```sh
OFFICE_PRESETS=configs/office_demo_presets_person_v1.json ./start-office-demo.command start
```

這是後續啟動入口，本次**沒有執行此啟動指令**。需保留原有服務，按 launcher 的 ownership 檢查處理。

## 可核對產物

[收據與 100 個媒體 hash](OFFICE_PERSON_RERENDER_20261016.json)已納入 PR。
下列完整產物只留 LOCAL，沒有發布 raw RGB／GT：

- `data/pilot/office_person_20261016_v1/trajectory_plan.json`
- `data/pilot/office_person_20261016_v1/rendered/{dataset.json,frames/,ground_truth.json}`
- `data/engineering/office_person_20261016_v1/office/{safe_inputs.json,manifest.json,validation_pin.json,predictions.json,contact_quality.json}`

渲染與 materialization 的精確指令見 PR Actual output；每次重新渲染都須用另一個 run_id 和新目錄。
目前原路線 plan 與新 run 均有 hash；新半徑的完整 body clearance、C7 地圖、混合區間、K1、
瀏覽器與正式研究驗收仍未驗證。FRONT 4.4 s／REAR 8.6 s 新 PNG 已由 agent 開啟目視抽查。
