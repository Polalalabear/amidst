# 即時模式 spike 收尾報告（D210，2026-11-15）

分支 `claude/feat-live-mode`。範圍：兩個視窗的 three.js 原型（操作端 `?role=operator`、系統端 `?role=system`，程式在 `frontend/live-mode/`、`src/amidst/live_mode/`）；本報告取代 `docs/engineering/LIVE_MODE_SPIKE_20261115.md` 那份未完成的草稿。這是工程可行性量測，不是辨識或安全的正式驗收。

## 1. 結論

1. **MPS 上 3 鏡頭 × 5 fps 跟不上，判斷確認。** 兩組 3 鏡頭設定的實際處理速率只有 1.9 和 2.2 fps，目標是 5 fps；顯示 95 和 114 個 tick，丟掉 156 和 140 個（62% 和 55%）。8 鏡頭更差，丟掉 66–218 個 tick，即使降到 2 fps 也丟掉 67%。
2. **瓶頸是偵測器 forward，不是渲染、網路或顏色判斷。** 各階段中位數裡 `forward` 占伺服器時間 90% 以上，渲染擷取 36–130 ms，顏色判斷約 1 ms。
3. **每張影像成本約 70–115 ms（MPS）或 345–430 ms（CPU）**，吞吐上限大約 9–14 張/秒（MPS）。需求是「鏡頭數 × fps」：3×5=15、8×5=40、8×2=16 張/秒，都超過上限。
4. **膠囊人形無法當即時偵測目標**（偵測率 16.7%）；N6 WIP 角色約 60%，仍不夠。這和延遲是兩個獨立的問題。

## 2. 結果表

### 2.1 MPS 延遲矩陣（5 組，各 50 秒；量出）

來源：`local/evidence/live-mode-spike-20261115/lat/*.latency.json`（LOCAL，見 §7）。tick 週期 = 1000/fps，50 秒共約 250 個（2 fps 為 100 個）排程 tick。

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

## 5. 建議的可行設定（推論；以下組合沒有直接量過）

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
