# F2 鏡頭覆蓋與操作端透視開關（#656，2026-11-22）

## 做了什麼
- `frontend/live-mode/src/coverage.mjs` 與 `src/amidst/q1q5/camera_projection.py`（`visibility_polygon`）：同一演算法，只用靜態牆面（`R004_SCENE_GEOMETRY_2D_V1.json` 的 clearance_segments，車輛 `R004_ENV_*` 不算牆）與鏡頭校正。高度 0.9 m 的身體點投影在畫面內、且鏡頭到該點的 2D 視線不穿牆，就算覆蓋；每 1° 一條射線、每 0.25 m 取樣、最遠 14 m。人與人之間不遮擋。兩版由 `tests/q1q5/test_wall_coverage.py` 逐點比對（誤差 < 1e-6 m）。
- `scene_context.build(..., walls=None)`：新增可選參數。預設不給牆，輸出與 v1 逐位元組相同；給牆時每台鏡頭多 `visible_area_polygon_xy_m`，重疊改用裁切後的格子。**r004 推論目前沒有傳入牆**：該幾何檔標示 `DESIGN_FEASIBILITY_ONLY_NOT_RUNTIME_AUTHORITY`（D207），要等協調者決定能否進推論。
- LIVE A 端（只在操作者畫面）：
  - 3D 畫面加鏡頭圖示＋名稱、被牆裁切的 FOV 地面色塊、盲區紅格；
  - 右側新增「鏡頭覆蓋」小地圖（牆、各鏡頭可視範圍、盲區、自己的位置）；
  - 透視改為開關 `#xray-toggle`，**預設關**；開啟時畫面上方顯示「操作者透視視角，鏡頭看不到」。
- 虛擬鏡頭（偵測器）畫面不受影響：透視與疊圖只在 `drawOperator` 的單次同步 render 內生效，`finally` 立即還原；`cap.shoot()` 在 `drawOperator` 外、shoot 開頭同步 render。

## 如何重現
```bash
cd frontend/live-mode && npm ci --offline --ignore-scripts && node --test test/*.test.mjs
PYTHONPATH=src .venv/bin/python -m pytest tests/q1q5/test_wall_coverage.py tests/q1q5/test_agent_service.py
```
畫面：照 `docs/operations/Q1Q5_LOCAL_TEST_SETUP.md` 起 LIVE（另一個埠，不用 8785），開 `/?role=operator&model=glb&run=A4-1&actor=T&mouse=drag`。

## LOCAL 截圖（`local/evidence/f2-coverage-20261122/`，4 檔，108 KB，可重拍）
| 檔案 | SHA-256 | 內容 |
| --- | --- | --- |
| `01_before_main_xray_always_on.jpg` | `e6a9d24872428011356c5161e6571c4a0190fb87147a7842df19b1bb4966f932` | 改前（main）：操作端牆一律半透明 |
| `02_after_default_opaque_overlay_minimap.jpg` | `de9fc0cd9c741d6058019b8adf3026a0fb4e7969e019132533afddcba18f247b` | 改後預設：牆不透明、鏡頭圖示／FOV／小地圖 |
| `03_after_xray_on_notice.jpg` | `5fe32860495c7907165e5cb6a35350f5d6c0ab00994277faf9f05c352d517d3e` | 改後開透視：紅色提示「操作者透視視角，鏡頭看不到」 |
| `04_after_B_detector_frames_opaque_while_A_xray_on.jpg` | `7305ad915f6e3691c9499e8ae6ece18b5549d74cb5ebdfb3f59a8405bb30c9d5` | A 開透視時，B 端收到的 CAM_EXT_CAR／CAM_W1 偵測畫面：牆實心、無疊圖 |

`SHA256SUMS` 在同一資料夾。

## 限制
- 覆蓋用 2D 牆線段算，N6 烘焙場景的實際幾何（門框、天花板）可能有小差異；LIVE 的 `gt_visible` 仍由 renderer raycast 決定，只在評分端使用。
- 3D 鏡頭圖示與名稱刻意不受深度遮擋（讓操作者找得到鏡頭），只畫鏡頭本身，不畫人。
