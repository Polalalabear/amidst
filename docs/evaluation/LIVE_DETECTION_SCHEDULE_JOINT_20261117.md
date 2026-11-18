# CX-L1 修改 C：新偵測器與排程聯合驗證

依 [D261 第4點](https://github.com/Polalalabear/amidst/issues/552#issuecomment-6940301551) 執行，結果逐條列出，不以吞吐變快替代跟對／失聯／重新鎖定驗收。

## 程式組成與衝突處理

`4ac1738a4127e773fe7e786b09cb1bc042795212` 是兩個 parent 的 **merge commit**：

- 原feature head：`efb2f498fe8955ae7b5de3a441e51d1dec48b778`（修改A）。
- main／#561 merge：`e9db4fdf866620f34557650f4f4c8458767d1b97`。

`server.py` 的 `/config` 保留偵測的 `det_resize_mode/min_score/camera_min_scores/det_size`，也保留排程的 `schedule_mode/schedule_policy`。`infer` 先沿#561算出cams，只對該cams推論；在cams迴圈內用 `threshold = camera_min_scores.get(cam, min_score)`，不把跳過相機填成空偵測。預設仍為letterbox、一般0.15、ENTRY0.05；排程N=1保持#561原樣，沒有為通過評分而調整。

被測runtime head：`06201314e3e98ebe53231dd797d72ecd3891fecb`，tree `cf67e16efbf64796020af77d99da48b6c93756e5`。該commit只另加延遲工具的可選 `RAW=1` 評估紀錄；之後收據工具／文件commit不改runtime。合入的main檔案沿用其來源；沒有自行修改people.py、tracker.py、advisor.py、system.mjs。沒有rebase、force-push、合併PR或更新8785。

Focused checks：`tests/live_mode tests/operations/test_live_launcher.py` **61 passed**，Node **36 passed**，`git diff --check`通過。合併初次測試因#561舊fake State args未給camera_min_scores而1 failed；只補fixture `{}`，不改production fallback，失敗log保留。新增跨排程門檻與HTTP/config測試均通過。

## 固定RGB與實跑方法

1. 重新用 `redetect_route.py` 在既有 `local/evidence/cx552-20261117/routes/packets` 的相同RGB推論，明確用一般0.15、ENTRY0.05；A4 96輪、B4 81輪。GT在偵測全部完成後才讀取並附回評分。
2. `replay_schedule.py` 的輸入只用本次新偵測目錄，不沿用38段舊偵測。先剝除GT／舊投影／舊追蹤，只給原始bbox/score/HSV/clock和safe camera graph，分別重播all和adaptive，完成後才以原t1 scorer計分。固定A4有4台可用鏡頭、B4有3台；不假稱是8台的固定RGB實驗。
3. 另做4次串行MPS實跑：同一code、N6素材、advisor off、8台可用、320×180、要求5fps。all／adaptive各A4 58秒、B4 50秒（劇本50／42秒，包含下一個循環）；丟前4個display tick暖機，延遲為擷取到B畫面display。開啟 `RAW=1`，在operator頁把GT與回應另存評估紀錄，沒有改HTTP request或B畫面的資料流。person-following用原t1 scorer；`correct_active_rate`只代表相機可見性，不能代替跟對。
4. ENTRY重新入鏡定義：在曾經可見後，再次出現ENTRY可見episode，排除首次出現；從第一個可見擷取tick到該episode內首次原scorer判為ON_TARGET的回應完成。另列ENTRY首次被推論及ENTRY為active且跟對的時間。若episode結束仍未鎖定，標censored／UNKNOWN，不把缺值當0。這裡量到的是劇本循環，不是實體返回路線。B4無ENTRY事件則標NOT_OBSERVED。

同一固定錄製各只有1份、實跑每條件各1次，且GPU非獨占；沒有held-out或統計顯著性聲稱。adaptive-A4首次量測因detached Frame中斷，沒有可用收據；保留失敗log並另名重試，不當作成功樣本。server的BrokenPipe與瀏覽器中斷紀錄原樣保留。

## 結果：NOT_PASSED，保持Draft

| 資料／路線 | 跟對 all→adaptive | 跟對不降 | 失聯 all→adaptive | 失聯≤all+0.02 |
| --- | ---: | --- | ---: | --- |
| 固定RGB A4 | 0.705263→0.694737 | **FAIL** | 0.042105→0.052632 | PASS |
| 固定RGB B4 | 0.966667→0.966667 | PASS | 0.016667→0.016667 | PASS |
| 新實跑 A4 | 0.166667→0.171429 | PASS | 0.416667→0.357143 | PASS |
| 新實跑 B4 | 0.450980→0.333333 | **FAIL** | 0.235294→0.303030 | **FAIL** |

固定RGB A4的差異定位在tick56、約29.07秒：all為ON_TARGET，adaptive為LOST；當輪active鄰域只查EXT_CAR/W1，沒有查到all觀測到目標的其他相機，下一輪才擴大。沒有降低不退步門檻，沒有以新實跑A4略高的跟對率抵銷這個失敗。新實跑每組不同取樣tick，不能把其變化當統計因果；其B4失聯增0.067736，仍明確超過指定+0.02。

**Protocol：PASS**，4個有效實跑均0違規。**ENTRY重新入鏡鎖定：UNKNOWN、未通過驗收證明**；A4兩模式各觀測到一次約50秒後ENTRY再可見，但可見episode內均未正確鎖定，兩個target_lock_ms都為null（censored），不能把兩個null當相等或0。ENTRY首次被推論完成的延遲all=883.4ms、adaptive=889.7ms，這只是觀測處理時間，不是正確鎖定延遲；以ENTRY為active且跟對亦未觀測到。B4沒有ENTRY事件（NOT_OBSERVED）。

| 實跑 | 輪/s | p50 ms | p95 ms | 平均推論台數 |
| --- | ---: | ---: | ---: | ---: |
| all-A4 | 1.025 | 822.0 | 948.7 | 8.000 |
| adaptive-A4 | 1.225 | 749.1 | 1092.2 | 6.015 |
| all-B4 | 1.079 | 810.8 | 933.1 | 8.000 |
| adaptive-B4 | 1.390 | 673.0 | 1080.2 | 5.523 |

p50與吞吐改善沒有讓聯合品質條件通過；adaptive的p95反而較高。所有模式均未達要求的5fps。原t1 scorer的GT時鐘擬合offset為0.08–0.12秒，平均位置殘差0.008–0.028m；收據保留每次值。跟對為原工程評分定義，仍不是身分確認。

機器收據：`live_detection_20261117/joint_schedule_validation.json`。LOCAL `MANIFEST.json` SHA-256 **c98407004c5acfb021f0a0c108990603ced2efadd07bf30b0017b253f4212936**，涵蓋37個檔案、2,130,553 bytes（manifest本身另計）。

**合併狀態：#559保持Draft，不宣稱C通過。** 下一步需使用者決定是否接受以`--schedule all`作demo配置（仍承認adaptive未過），或另派排程修正／重新鎖定驗證。這次沒有自行切換預設、調整graph或擴張原始追蹤演算法。

## 重現與 LOCAL

**所有命令在自己的clone執行**；SHARED_LOCAL指向共用唯讀local，PYTHON使用既有uv Python，UV_CACHE_DIR寫自己的clone。C_OUT指向新的LOCAL輸出，勿覆寫既有原始證據。Node依賴使用本clone的 `frontend/live-mode/package-lock.json`。

```bash
C_OUT="$SHARED_LOCAL/evidence/cx552-c-20261117"
export PYTHONDONTWRITEBYTECODE=1
export UV_CACHE_DIR=.local/demo-cache/uv
PYTHONPATH=src:$SHARED_LOCAL/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps uv run --offline --no-project --python "$PYTHON" python -B scripts/live_mode/redetect_route.py --recording "$SHARED_LOCAL/evidence/cx552-20261117/routes" --out "$C_OUT/redetected" --models "$SHARED_LOCAL/data/demo-owned-v1/models/rtdetr" --min-score 0.15 --camera-min-score CAM_ENTRY=0.05
PYTHONPATH=src uv run --offline --no-project --python "$PYTHON" python -B scripts/live_mode/replay_schedule.py --src "new=$C_OUT/redetected" --cameras "$SHARED_LOCAL/data/r004-build-v2-20261021/safe_static/cameras.json" --out "$C_OUT/replay" --expand-every 1
PYTHONPATH=src:$SHARED_LOCAL/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps uv run --offline --no-project --python "$PYTHON" python -B -m amidst.live_mode.server --port 8797 --device mps --models "$SHARED_LOCAL/data/demo-owned-v1/models/rtdetr" --assets "$SHARED_LOCAL/data/live-assets-20261115" --cameras "$SHARED_LOCAL/data/r004-build-v2-20261021/safe_static/cameras.json" --advisor off --schedule all
# 在frontend/live-mode執行，server先all、完成後再adaptive --expand-every 1，勿併行：
LIVE_BASE=http://127.0.0.1:8797 RAW=1 OUT="$C_OUT/latency" node measure/latency.mjs all-A4 'auto=A4&run=A4-1-v2-4actor&duration=50&model=glb&w=320&h=180&fps=5' 58
# B4改label/run/auto為B4、duration=42、量50秒；adaptive兩次改label及server schedule。
# 回repo根產生精簡收據與完整manifest：
PYTHONPATH=src uv run --offline --no-project --python "$PYTHON" python -B scripts/live_mode/joint_detection_schedule_receipt.py --work "$C_OUT" --out docs/evaluation/live_detection_20261117/joint_schedule_validation.json
```

新增證據位於共用 `local/evidence/cx552-c-20261117/`（亦可用 `$AMIDST_ARTIFACTS/cx552-c-20261117/`）。來源179個封包／raw檔的SHA在source_inventory.json；模型、校正、graph的既有hash來源見原cx552收據與/config快照。原cx552／cx553／cx554／cx555及修改A資料均保持不變。Raw RGB不再複製；新偵測、逐tick、評分、延遲和log留LOCAL。精簡JSON收據列manifest SHA、檔數與bytes。可用同一來源重跑，不承諾新時鐘／MPS浮點／檔案bytes完全相同。

未驗證：原生Windows、使用者手動路線、確認身分、實體導航／碰撞、安全、付費advisor、API provider、8785部署。沒有跑本任務以外的全套／Blender／付費實驗。#555原完整更新gate仍是f6d7e8ff的歷史結果，不能替代整合後重新部署的gate。
