# 即時模式 spike 收尾報告（D210，2026-11-15）

分支 `claude/feat-live-mode`。範圍：兩個視窗的 three.js 原型（操作端 `?role=operator`、系統端 `?role=system`，程式在 `frontend/live-mode/`、`src/amidst/live_mode/`）；本報告取代 `docs/engineering/LIVE_MODE_SPIKE_20261115.md` 那份未完成的草稿。這是工程可行性量測，不是辨識或安全的正式驗收。

## 1. 結論

1. **MPS 上 3 鏡頭 × 5 fps 跟不上，判斷確認。** 兩組 3 鏡頭設定的實際處理速率只有 1.9 和 2.2 fps，目標是 5 fps；顯示 95 和 114 個 tick，丟掉 156 和 140 個（62% 和 55%）。8 鏡頭更差，丟掉 66–218 個 tick，即使降到 2 fps 也丟掉 67%。
2. **瓶頸是偵測器 forward，不是渲染、網路或顏色判斷。** 各階段中位數裡 `forward` 占伺服器時間 90% 以上，渲染擷取 36–130 ms，顏色判斷約 1 ms。
3. **每張影像成本約 70–115 ms（MPS）或 345–430 ms（CPU）**，吞吐上限大約 9–14 張/秒（MPS）。需求是「鏡頭數 × fps」：3×5=15、8×5=40、8×2=16 張/秒，都超過上限。
4. **膠囊人形無法當即時偵測目標**（偵測率 16.7%）；N6 WIP 角色約 60%，仍不夠。這和延遲是兩個獨立的問題。

## 2. 結果表

### 2.1 MPS 延遲矩陣（5 組，各 50 秒；量出）

來源：`local/evidence/live-mode-spike-20261115/lat/*.latency.json`（LOCAL，量測值無法重建為同值，各檔 SHA-256 見 §7 和 `live_mode_spike_20261115/SHA256SUMS_local.txt`）。tick 週期 = 1000/fps，50 秒共約 250 個（2 fps 為 100 個）排程 tick。

| 設定 | 顯示 tick | 丟掉 tick | 丟棄率 | 實際 fps | 延遲 p50 / p95 / max (ms) | first-lock (ms) | switch (ms) | 正確 active 比例 |
|---|---|---|---|---|---|---|---|---|
| 3 鏡頭 320×180 @5 | 95 | 156 | 62% | 1.91 | 421 / 663 / 1078 | 627 | 無事件 | 0.356 |
| 3 鏡頭 640×360 @5 | 114 | 140 | 55% | 2.24 | 292 / 626 / 1053 | 293 | 16 784（n=1） | 0.292 |
| 8 鏡頭 320×180 @2 | 33 | 66 | 67% | 0.66 | 1063 / 2079 / 2210 | 13 709 | 無事件 | 0.179 |
| 8 鏡頭 320×180 @5 | 34 | 218 | 87% | 0.67 | 1111 / 1908 / 2219 | 13 780 | 無事件 | 0.214 |
| 8 鏡頭 640×360 @5 | 43 | 207 | 83% | 0.86 | 978 / 1676 / 1814 | 5 776 | 9 843（n=1） | 0.162 |

說明：
- 延遲 = 系統端顯示時刻 − 操作端擷取時刻，丟掉前 4 個 tick 的暖機。first-lock = 目標第一次被 Ground Truth 判為可見到系統端第一次 TRACKING。switch = 在用鏡頭失去目標後，到系統的 active 鏡頭真正看得到目標的時間（Ground Truth 只用於評估）。`protocol_violations` 五組都是 0。
- 「顯示 tick 數」和 `sent` 相同；丟棄表示操作端為了不堆積而跳過 tick。
- switch 每組最多 1 個事件，**p50/p95 沒有統計意義**；3 鏡頭 320 與 8 鏡頭的兩組 320 都沒有觸發任何 switch。
- 正確 active 比例低（0.16–0.36）同時反映偵測率低與延遲高，無法單獨歸因。

### 2.2 CPU 對照（3 組，各 50 秒；量出；縮小規模）

同一套程式、同一腳本，`--device cpu --threads 4`，伺服器在 port 8796（沒有碰 8785）。只跑 3 組，沒有跑完整 5 組。原始檔在 `docs/evaluation/live_mode_spike_20261115/cpu_*.latency.json`（已移除逐 tick `rows`，其餘欄位不變）。

| 設定 | 顯示 tick | 丟掉 tick | 實際 fps | 延遲 p50 / p95 / max (ms) | first-lock (ms) | switch (ms) | 正確 active 比例 | forward p50 (ms) |
|---|---|---|---|---|---|---|---|---|
| 3 鏡頭 320×180 @5 | 31 | 223 | 0.63 | 1342 / 1733 / 2765 | 7402 | 17 018（n=1） | 0.231 | 1291 |
| 3 鏡頭 640×360 @5 | 34 | 219 | 0.68 | 1290 / 2338 / 2710 | 1030 | 12 857（n=1） | 0.586 | 1216 |
| 8 鏡頭 320×180 @2 | 15 | 84 | 0.30 | 2938 / 3739 / 3945 | 7350 | 無事件 | 0.182 | 2762 |

### 2.3 MPS 對 CPU 的 forward 成本（中位數，每批次；每張 = 批次 ÷ 鏡頭數）

| 設定 | MPS forward (ms) | MPS 每張 | CPU forward (ms) | CPU 每張 | CPU/MPS |
|---|---|---|---|---|---|
| 3 鏡頭 320 | 323 | 108 | 1291 | 430 | 4.0× |
| 3 鏡頭 640 | 218 | 73 | 1216 | 405 | 5.6× |
| 8 鏡頭 320 | 911（@5）| 114 | 2762（@2）| 345 | 3.0× |

CPU 比 MPS 慢約 3–5.6 倍，CPU 全部設定的實際 fps 都在 0.3–0.7；CPU 不是可行路徑。

## 3. 瓶頸分析

- **偵測器 forward 占主導。** MPS 3 鏡頭 320 的伺服器總時間 354 ms 中 forward 是 323 ms；HTTP 往返 358 ms 幾乎等於伺服器時間，所以網路、JPEG 編碼和傳輸可忽略（`channel_to_display` 6–31 ms）。
- **批次是序列的**：伺服器用鎖，一次只推理一批；批次一超過 tick 週期（5 fps = 200 ms），後面的 tick 就被操作端丟掉。3 鏡頭 forward 即 218–323 ms，已超過 200 ms 週期。
- **解析度不是主因。** RT-DETR 輸入固定為 640×640 拉伸，渲染解析度對 forward 時間沒有物理上的影響。表中 640 反而比 320 快（3 鏡頭：218 對 323 ms），這是量測雜訊，不是解析度效果（見下節）。
- **同機負載會污染 MPS 數字（未控制）。** 量測期間 `load1` 約 8.8–13.2（其他 session 同時在跑），GPU 使用率 84–92%（Chrome 的 WebGL 渲染和 MPS 推理共用同一顆 GPU）。因此 MPS 的絕對值偏悲觀，且組間差異（尤其 320 對 640）不能解讀成設定效應。每組只跑一次，沒有重複。要定論需要在空閒機器上重複量測。
- 渲染擷取 36–130 ms/批（8 鏡頭約 125 ms）也不小，但在 forward 之下。

## 4. 偵測率限制（量出，`docs/engineering/live_mode_spike_data/*.summary.json`）

RT-DETR R18、MPS、單人、1 m 格點 × 4 個朝向、8 鏡頭、顯示門檻 0.35；合格樣本 = 射線可見、框 ≥60% 在畫面內、高 ≥16 px；命中 = IoU ≥ 0.3。

| 人物模型 | 320×180 | 480×270 | 640×360 |
|---|---|---|---|
| 膠囊（436 三角面） | 16.7% | 15.8% | 17.4% |
| N6 WIP `character.glb`（約 4.0k 三角面，未審） | 60.6% | 54.9% | 50.7% |

- 膠囊在 320×180 的偵測率只有 **16.7%**（1328 個合格樣本）；門檻放寬到 0.1 時為 85.5%，也就是分數大多落在 0.1–0.35。鏡頭差異大：CAM_W2 55.8%，CAM_ENTRY 5.1%，CAM_BRANCH 0%。這是偵測器不把膠囊當人，不是鏡頭解析度不足（提高解析度沒有改善）。
- glb 角色約 60%，近距離（<4 m、陡俯視、大框）與 CAM_R101_IN、CAM_BRANCH 偏弱。解析度提高反而下降，與固定 640×640 拉伸輸入一致（推論，未單獨驗證）。
- 顏色標籤只要偵測到就是對的。
- 偵測率低會直接拖低 first-lock、switch 與「正確 active 比例」，所以 §2 的追蹤品質數字同時受延遲和偵測兩個因素影響。

## 5. 建議的可行設定（本節為 spike 當時的推論；兩組建議設定已在 §10 以 N6 實測，以 §10 為準）

量測只證明：3 鏡頭×5 fps（15 張/秒）與 8 鏡頭×2 fps（16 張/秒）在這台機器上做不到。以每張 70–115 ms（MPS，且有同機負載）推估，持續吞吐約 9–14 張/秒；保守取約 6–8 張/秒才不會積壓，建議：

| 用途 | 鏡頭數 | fps | 渲染解析度 | 備註 |
|---|---|---|---|---|
| 展示最低可行 | 3（目標路線上的 W1、W2、R101_IN） | 2 | 320×180 | 6 張/秒，低於上限；預期延遲仍 >200 ms，但不丟 tick。**需實測驗證** |
| 2 鏡頭即時感較好 | 2 | 3–4 | 320×180 | 6–8 張/秒；只能涵蓋兩個視角 |
| 8 鏡頭全覆蓋 | 8 | ≤0.7 | 任意 | 每鏡頭每 1.5 秒才一張，不算即時；可考慮「只對最近的 2–3 鏡頭推理，其餘輪詢」 |

- 渲染解析度改 320×180 即可，因為模型輸入固定 640×640，更高解析度只增加渲染與傳輸成本且偵測率沒有變好。
- 與其硬拚 fps，更有效的是減少每 tick 推理的影像數（只推理「active 鏡頭與其圖上鄰居」），這需要改 `src/amidst/live_mode/tracker.py` 的排程，不在本 PR。
- CPU 不建議（比 MPS 慢 3–5.6 倍）。

## 6. 下一步

1. **外觀：等 Codex N6（[#539](https://github.com/Polalalabear/amidst/issues/539)：人物骨架、走/跑/待機動畫、烘焙光照）。** 現在量到的 glb 是未審的 WIP；N6 交付後要重跑偵測掃描（`measure/run_sweeps.sh`）。
2. **偵測改進**：（a）以 N6 角色重測；（b）評估較大的偵測模型或提高模型輸入覆蓋率（目前 640×640 拉伸 16:9 畫面）；（c）降低門檻並以追蹤器時間平滑補回漏偵測；（d）保留「模擬偵測」備援直到偵測率夠用。
3. **延遲**：在空閒機器上重跑 MPS 矩陣並每組重複 ≥3 次；實作只推理 active 鏡頭與鄰居的排程；評估 batch 流水線（渲染與推理重疊）。
4. 實測 §5 建議的 3 鏡頭×2 fps 與 2 鏡頭×3–4 fps。

## 7. LOCAL 證據與可重現

| 檔案（相對 repo 根） | 大小 (bytes) | SHA-256 | 重新產生 |
|---|---|---|---|
| `local/evidence/live-mode-spike-20261115/lat/mps_3cam_320_5fps.latency.json` | 9787 | `1aff62cd13a542d4c6062a92a8dc557a11130fd65a688f2b9957bda50e7ec568` | `measure/run_latency.sh`（MPS 伺服器），不保證同值 |
| 同目錄 `mps_3cam_640_5fps.latency.json` | 11671 | `379a22da84f2a3f17346ede925460e49d8ba4bd65c81bdca28d132365c8af149` | 同上 |
| 同目錄 `mps_8cam_320_2fps.latency.json` | 4167 | `2c0f4e5096e6fa1ab5a9c2c1379cc63fac18b2d608b99388bcf7d9eb23093fa7` | 同上 |
| 同目錄 `mps_8cam_320_5fps.latency.json` | 4310 | `accdbb180283f4cf96e115898fa8d687866974812be8f0f4ff85437fab897234` | 同上 |
| 同目錄 `mps_8cam_640_5fps.latency.json` | 5198 | `a162743462260959ca01644d73d37d1be276322cf0e61245a553138e3e793f7c` | 同上 |
| N6 WIP `character.glb`（session 暫存，不在 repo；LOCAL） | 658508 | `4ab17c44b263b20a814be245aa23fcae898cd5242b42b6af4db9da75f7964ce4` | N6 #539 產出；不可由本 repo 重建 |

已提交到 repo 的檔案（`docs/evaluation/live_mode_spike_20261115/`）：CPU 對照 JSON 三份（已去掉逐 tick rows）與並排截圖 `side_by_side_cpu_3cam_320_5fps.png`（SHA 與大小見 PR 描述）。偵測掃描摘要在 `docs/engineering/live_mode_spike_data/`。

CPU 對照重現（腳本在 `frontend/live-mode/measure/`，伺服器需設 `AMIDST_LIVE_CHARACTER_GLB` 才有 `model=glb`）：

```bash
PYTHONPATH=src:<runtime-deps> python -m amidst.live_mode.server --port 8796 --device cpu --threads 4 --models <rtdetr dir>
cd frontend/live-mode && LIVE_BASE=http://127.0.0.1:8796 OUT=out DEV=cpu node measure/latency.mjs cpu_3cam_320_5fps "auto=B4&duration=42&model=glb&w=320&h=180&fps=5&cams=CAM_W1,CAM_W2,CAM_R101_IN" 50
```

## 8. 截圖

`docs/evaluation/live_mode_spike_20261115/side_by_side_cpu_3cam_320_5fps.png`：左為操作端（第三人稱視角，WASD 控制人物），右為系統端（只看鏡頭像素：3 個啟用鏡頭的畫面、地圖、狀態與事件）。取自 CPU 對照 3 鏡頭 320×180 @5 的第 31 個 tick 附近；其餘 5 個鏡頭黑畫面是因為這組只啟用 3 個鏡頭。

## 9. 沒驗證的部分

- MPS 與 CPU 的數字都是單次 50 秒、同機有其他負載、Chrome 和 MPS 共用 GPU；沒有重複，沒有控制負載。
- CPU 只跑 3 組（不是 5 組）。
- §5 的可行設定是推論。
- switch 與 first-lock 每組事件數 ≤1，不能當統計。
- 沒有跑 Blender、付費 API 或長時間實驗。

## 10. N6 整合（#539 已合併；2026-11-15）

把 N6 素材接進即時模式：`scene.glb`（烘焙、unlit）取代 spike 的擠出牆場景、`cameras.three.json` 取代目錄相機、`character.glb`（T/A/B/C 外觀＋原地 walk/run/idle）取代膠囊與 WIP 人物；干擾者在 `model=glb` 時用變體 A/B/C。素材來自 LOCAL `$AMIDST_ARTIFACTS/data/live-assets-20261115/`（伺服器用 `--assets` 或 `$AMIDST_LIVE_ASSETS`；程式裡沒有絕對路徑；缺素材時退回 spike 場景）。天花板亮度（P2-1）依使用者指示不動。操作端視角在 N6 場景改為高處俯視並隱藏天花板（只影響操作端自己的畫面，虛擬鏡頭照常渲染天花板）。

### 10.1 P2-2 四項契約（`frontend/live-mode/test/n6.test.mjs`，`npm test` 12/12 通過；輸出 `live_mode_n6_20261115/npm_test.txt`）

| 項目 | 測試做什麼 | 結果 |
|---|---|---|
| 座標 Blender (x,y,z)→(x,z,−y)、前方 +X | 轉換矩陣；heading θ 對應 `rotation.y=θ`，局部 +X 落在 (cosθ,0,−sinθ)；真 `character.glb` 的 `setPose(5,2,0)` 落在 (5,0,−2)，鞋尖側（+X）比腳跟側長 | 通過 |
| 相機 row-major、八鏡頭內外參 | `Matrix4.set(...rows.flat())`；刻意驗證 `fromArray` 會讀錯；`world_to_camera` 為 `camera_to_world` 之逆（<1e-5）；three 由 fy/cy 建的投影矩陣等於 JSON 的 `projection_matrix`（<1e-6）；八台 fx/fy/cx/cy/寬高等於來源目錄，`camera_to_world` = R × Blender 矩陣（<1e-5）；Blender 地面點經目錄針孔與 N6 相機投影到同一像素（<0.01 px，八台） | 通過 |
| `KHR_materials_variants` T/A/B/C | 自寫 GLTFLoader 外掛（three 核心不處理）；四個變體名；A 與 T 上衣同色、褲色不同；B、C 與 T 不同；四種褲材質互異；同一份 glTF 複製兩個人各自切換互不影響；`setVariant('Z')` 丟錯 | 通過 |
| `timeScale = 實速 / 名義速度`（walk 1.2、run 2.5） | 0.6→walk×0.5、1.2→walk×1、1.5→walk×1.25、2.5→run×1、1.25(跑)→run×0.5、0→idle；實際推進 `action.time` 驗證 timeScale 有作用；站立腳的世界速度中位數：0.6／1.2／2.0／2.5 m/s 皆為 0.0000 m/s（各約 600 取樣）；對照組：walk 片段以 timeScale=1 走 2.5 m/s，站立腳滑動 1.30 m/s | 通過 |

整合時抓到一個 bug：`SkeletonUtils.clone` 會把 `mesh.userData` 以 JSON 複製，變體材質變成純物件而渲染失敗（`material.onBeforeRender is not a function`）。已改成以 mesh 名稱存在 `gltf.userData.variantTable`，測試也檢查複製後仍是真的材質。截圖證據：走（speed 1.2、timeScale 1）、跑（2.5、1）、待機；腳本路線上慢速段 speed 1.00 → timeScale 0.835（見 `shots.meta.json`）。

### 10.2 偵測率（320×180，MPS，1328 個合格樣本，同一份 `measure/detect_sweep.mjs`，每組 2 次）

| 人物 × 場景 | 偵測率 | 兩次相同？ | 備註 |
|---|---|---|---|
| 膠囊 × spike 場景（§4） | 16.7% | — | 當時量測，單次 |
| WIP glb × spike 場景（§4） | 60.6% | — | 當時量測，單次 |
| **N6 × N6 烘焙場景** | **69.1%** | 是（r1=r2） | 紅標籤正確率 90.0%；每幀誤檢 0；<4 m 44%、4–8 m 66%、12–16 m 82%、>16 m 93%；各鏡頭 CAM_ENTRY 19%、R101_IN 47%、EXT_CAR 67%、其餘 84–95% |
| N6 × spike 場景 | 83.8% | 是 | 隔離場景效應 |
| 膠囊 × N6 烘焙場景 | 25.6% | 是 | 隔離場景效應 |

- 掃描是確定性的（兩次完全相同），所以「2 次」只確認重現性，不是變異估計；偵測率不受機器負載影響（掃描在 load1 約 10–25 時跑，仍相同）。
- N6 比膠囊高 +52 個百分點（同場景 69.1 對 25.6）、比 WIP 高 +8.5。N6 在烘焙場景比在 spike 場景低 14.7 個百分點：烘焙場景牆與地對比較低、整體偏暖，人物陰影不存在，推論是背景與人物的色差變小（未單獨驗證）。膠囊在烘焙場景反而升（16.7→25.6）。
- 仍不到可靠：CAM_ENTRY（19%）、CAM_R101_IN（47%）差。

### 10.3 延遲與兩組建議設定（N6 × 烘焙場景，MPS，320×180，B4 路線，各 50 秒、每組 2 次）

原始檔 `live_mode_n6_20261115/n6_*.latency.json`（已移除逐 tick rows）。load1 為該次 50 秒內的平均；`load.log` 有前後 load。全部 load1 < 8，沒有需標「高負載」的組，但 GPU 使用率 84–94%（Chrome 與 MPS 共用 GPU），其他 session 仍在跑，不是空閒機器。

| 設定 | 次 | 顯示 | 丟掉 | 丟棄率 | 實際 fps | 延遲 p50 / p95 / max (ms) | forward p50 | first-lock (ms) | 切換事件 (ms) | 正確 active | load1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 鏡頭 @2 | 1 | 99 | 1 | 1% | 1.98 | 243 / 278 / 525 | 174 | 471 | 1742, 1761, 2731 | 0.59 | 6.2 |
| 3 鏡頭 @2 | 2 | 98 | 1 | 1% | 1.98 | 240 / 277 / 505 | 173 | 447 | 1753, 1754, 2743 | 0.60 | 4.3 |
| 2 鏡頭 @3 | 1 | 147 | 3 | 2% | 2.94 | 160 / 203 / 564 | 115 | 365 | 2164, 11901 | 0.47 | 6.0 |
| 2 鏡頭 @3 | 2 | 150 | 3 | 2% | 2.94 | 160 / 191 / 366 | 115 | 376 | 11808 | 0.56 | 3.6 |
| 2 鏡頭 @4 | 1 | 159 | 40 | 20% | 3.19 | 195 / 300 / 470 | 146 | 375 | 2188, 11659 | 0.51 | 4.9 |
| 2 鏡頭 @4 | 2 | 152 | 49 | 24% | 3.02 | 194 / 358 / 452 | 147 | 371 | 1178, 2162, 11715 | 0.48 | 4.4 |
| 3 鏡頭 @5（對照） | 1 | 123 | 128 | 51% | 2.45 | 265 / 315 / 774 | 198 | 462 | 1069, 2254, 2684 | 0.62 | 4.8 |
| 3 鏡頭 @5（對照） | 2 | 87 | 166 | 66% | 1.73 | 406 / 1381 / 1838 | 324 | 452 | 1483 | 0.45 | 7.6 |

結論（§5 的推論改成量測值）：
1. **3 鏡頭 × 2 fps：撐得住**（丟 1 個 tick／約 100，延遲 p50 約 240 ms，兩次一致）。
2. **2 鏡頭 × 3 fps：撐得住**（丟 3／150，p50 160 ms，兩次一致）。
3. **2 鏡頭 × 4 fps：撐不住**（丟 20–24%，實際約 3.0–3.2 fps）；2 鏡頭的實際上限約 3 fps。
4. 3 鏡頭 × 5 fps 仍然撐不住（丟 51–66%，且兩次差很大，是負載敏感），和 spike 的結論一致。
5. 每張影像的 forward 成本：3 鏡頭約 58 ms/張、2 鏡頭約 58–73 ms/張，比 spike 當時（70–115 ms）低，那次是更高負載（load1 8.8–13.2）。
6. 切換延遲約 1.2–2.7 s；另有約 11.7 s 的事件是目標離開後在路線尾端重新出現。每組事件 1–3 個，樣本太少，**不當統計結論**。正確 active 比例 0.45–0.62，受偵測率（§10.2）與延遲共同影響，無法單獨歸因。

### 10.4 證據與 SHA-256

資料夾 `docs/evaluation/live_mode_n6_20261115/`（約 1.6 MB，已提交）；完整 SHA-256 見該資料夾 `SHA256SUMS.txt`。

| 檔案 | SHA-256（前 16 碼） |
|---|---|
| `idle_side_by_side.png` | 8e4328d9c6de035e |
| `walk_side_by_side.png` | 528a248be995a024 |
| `run_side_by_side.png` | 3558aa427283ba0f |
| `switch_before_side_by_side.png` | 9e961e8d09df3f84 |
| `switch_after_side_by_side.png` | 46194d5fe2d4164a |
| `shots.meta.json` | be85a12787567dac |
| `npm_test.txt` | 311d1afb1b8aa73c |
| `load.log` | 15d4007c0e18a271 |

LOCAL 輸入素材（不在 repo；N6 #539）：`character.glb` `f46139c0d21aa058…`、`scene.glb` `cf9ef5135774fd21…`、`cameras.three.json` `6deb31b032f4a7ce…`（皆為前 16 碼）。逐樣本 `*.rows.json` 只在 scratchpad，未提交。

重現（伺服器 port 8796，不碰 8785）：

```bash
export AMIDST_ARTIFACTS=<N6 所在的 local 資料夾>
PYTHONPATH=src:<runtime-deps> python -m amidst.live_mode.server --port 8796 --device mps --models <rtdetr dir>
cd frontend/live-mode && LIVE_BASE=http://127.0.0.1:8796 OUT=out measure/run_n6.sh   # 掃描與延遲，REPS=2
LIVE_BASE=http://127.0.0.1:8796 node measure/shots.mjs shots                       # 截圖
```

### 10.5 沒驗證的部分

- 機器不是空閒的（其他 session 同時在跑，GPU 84–94%）；每組只 2 次且偵測率掃描是確定性的，延遲沒有信賴區間。
- 兩組建議設定只跑了 B4 路線單人情境；A4 路線、多目標、長時間（>50 秒）沒跑。
- N6 在烘焙場景的偵測率比 spike 場景低的原因是推論，沒單獨驗證；天花板亮度（P2-1）沒調，因此顏色與偵測可能隨之改變。
- 步態自然度、分件人偶外觀沒有人工驗收；站立腳滑動只在 node 裡以骨骼世界座標驗證，沒做影片逐幀。
- 操作端截圖是無頭 Chrome（Metal）的 1280×720，未在使用者的真實視窗確認；未測 WASD 碰撞在 N6 場景中與烘焙牆的對齊（碰撞仍用目錄牆線段，N6 的 `n6Collider` 節點沒用）。
- `n6Lighting` 的 irradiance 通道（動態 PBR）沒用，場景是 unlit 烘焙貼圖。
- 以上掃描／延遲跑在作者的 scratch clone；CI 只跑 `npm test`（無 LOCAL 素材時 N6 測試為 skip，僅座標約定測試執行）與 pytest。
