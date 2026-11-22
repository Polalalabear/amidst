# F2 鏡頭覆蓋與操作端透視開關（#656，2026-11-22）

## 做了什麼
- `frontend/live-mode/src/coverage.mjs` 與 `src/amidst/q1q5/camera_projection.py`（`visibility_polygon`）：同一演算法，只用靜態牆面（`R004_SCENE_GEOMETRY_2D_V1.json` 的 clearance_segments，車輛 `R004_ENV_*` 不算牆）與鏡頭校正。高度 0.9 m 的身體點投影在畫面內、且鏡頭到該點的 2D 視線不穿牆，就算覆蓋；每 1° 一條射線、每 0.25 m 取樣、最遠 14 m。人與人之間不遮擋。兩版由 `tests/q1q5/test_wall_coverage.py` 逐點比對（誤差 < 1e-6 m）。
- **D346（協調者 2026-11-22）**：只有 `occluders_full_height` 和 `door_openings` 可以進推論。牆＝`occluders_full_height`（JS、Python 都改用它）。`scene_context.static_geometry(raw_bytes)` 只取這兩項，檔案缺少 D346 例外就拒絕，並記下來源 SHA-256；`build(..., static=None)` 預設輸出與 v1 逐位元組相同。給了 `static` 時，每台鏡頭多 `visible_area_polygon_xy_m`（以 0.1 m 簡化），重疊改用裁切後的格子，`static_geometry` 區段列出門洞和來源 SHA，`sources` 也加上該檔 SHA。幾何 JSON 和產生腳本加了 `must_not_enter_exceptions`；authority pin `D346-G1` 和 authorized change 收據綁在 `a8470a66`。
- `scripts/run_w2_agent.py` `scene_for(label, with_static=False)`：W2 預設不變，維持可重現；E3（F4）才開啟。B4-1 的各鏡頭覆蓋面積從 112–145 m²（未裁切地面足跡）降到 12–33 m²，context 從 12.4k 字增加到 15.2k 字。
- LIVE A 端（只在操作者畫面）：
  - 3D 畫面加鏡頭圖示＋名稱、被牆裁切的 FOV 地面色塊、盲區紅格；
  - 右側新增「鏡頭覆蓋」小地圖（牆、各鏡頭可視範圍、盲區、自己的位置）；
  - 透視改為開關 `#xray-toggle`，**預設關**；開啟時畫面上方顯示「操作者透視視角，鏡頭看不到」。
- 虛擬鏡頭（偵測器）畫面不受影響：透視與疊圖只在 `drawOperator` 的單次同步 render 內生效，`finally` 立即還原；`cap.shoot()` 在 `drawOperator` 外、shoot 開頭同步 render。

## D346 放行前驗證：牆投影對畫面
`scripts/f2_validate_wall_projection.py`：每個看得到的 occluder 面每 5 cm 取一點，用標定把牆腳線（z=0）投影到 A4-1 第 0 幀 RGB，沿法線 ±20 px 找最強的邊（亮度＋2×(G−R)：牆偏暖、地板偏綠，交界主要是色相變化），量它和投影線的距離。只用靜態幾何、標定和原始 RGB，不用 GT 或 depth。

| 鏡頭 | 取樣點 | 中位數 px | p90 px | ≤3 px | 中位數 m | p90 m | 最近邊 ≤3 px |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAM_W1 | 306 | 1 | 1 | 100% | 0.010 | 0.025 | 100% |
| CAM_BRANCH | 185 | 0 | 1 | 99.5% | 0.000 | 0.011 | 99.5% |
| CAM_WIDE | 431 | 1 | 18 | 63.3% | 0.023 | 0.300 | 94.9% |
| CAM_R101_IN | 185 | 0 | 1 | 99.5% | 0.000 | 0.010 | 100% |
| CAM_W2 | 448 | 0 | 1 | 97.5% | 0.000 | 0.028 | 99.8% |

- CAM_WIDE 的 p90 尾巴來自左牆：放大圖 `wallcheck_CAM_WIDE_zoom_left_wall.png` 中投影線就在牆腳上（約 2–3 px），但 15–20 px 外有更強、平行的門框邊，贏過了「最強邊」搜尋。改用「最近的邊」（強度 ≥ 門檻的最近峰值）量，有 94.9% 在 3 px 內。表中主欄位保留保守的「最強邊」數字。
- CAM_ENTRY 在這一幀看不到任何 occluder 的牆腳線（0 個取樣點），沒有納入。
- 結論：牆的位置和畫面吻合（4 台中位數 0–1 px、≥97.5% 在 3 px 內，WIDE 的偏差是量測干擾），**採選項 (1)**，不退回 (2)。

LOCAL：`local/evidence/f2-coverage-20261122/wallcheck/`（`wallcheck.json` `165d676e27dc8619c25fe66536f68e25df867e04cd82e3e0fb048d13c057d1e8`、6 張疊圖＋1 張放大圖、`SHA256SUMS`），可用上面的腳本重新產生。`wallcheck_CAM_ENTRY.png` 是第一次執行留下的（0 個取樣點）。

## 如何重現
```bash
cd frontend/live-mode && npm ci --offline --ignore-scripts && node --test test/*.test.mjs
PYTHONPATH=src .venv/bin/python -m pytest tests/q1q5/test_wall_coverage.py tests/q1q5/test_agent_service.py
PYTHONPATH=src .venv/bin/python scripts/f2_validate_wall_projection.py --frames local/data/r004-4actor-natural-walk-eightcam-20261114/A4-1 \
  --cameras CAM_W1,CAM_BRANCH,CAM_WIDE,CAM_R101_IN,CAM_W2 --out local/evidence/f2-coverage-20261122/wallcheck
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
