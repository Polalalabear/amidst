# #559 D273：近期候選鏡頭與逐 tick 歸因

本文件接續[第三份指示](https://github.com/Polalalabear/amidst/pull/559#issuecomment-6952347393)。
此階段只修排程，不改預設為all、不改偵測門檻、graph、tracker gate或原t1評分。
**D273 量測結果為 NOT_PASSED**，被測 runtime 為 4fbc4af1。排程品質與 protocol 條件通過，兩種模式的 ENTRY 正確重鎖延遲均為 null。
[D282](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6966400705) 接受排程結果，將 ENTRY 記為 baseline tracker 已知限制，由 [#585](https://github.com/Polalalabear/amidst/issues/585) 接續。

## 為何選近期候選鏡頭

固定RGB A4 tick55在EXT_CLEAR有紅衣候選，但tracker只認EXT_CAR的近鄰群；
tick56開始時lost仍為0，active鄰域只選EXT_CAR/W1，漏掉all在EXT_CLEAR看到的目標。
只改lost>=1全搜只能救下一輪，無法補當輪。保留「近2秒內任何像素判紅候選的鏡頭」
可在此輪保留EXT_CLEAR，無須假稱該候選身分已確認。2秒是原MPS約1秒服務週期的兩輪
緩衝，用capture clock計，不是按GT／actor位置選窗；未跑參數格點挑最好分數。

CameraScheduler.observe只讀實際推論所得的color與camera id，加上capture clock；
plan在原active鄰域加這些近期鏡頭，最終仍只選available ids，不改任何graph邊。
原UNKNOWN scope全搜與lost擴展規則保留。reset／時鐘倒退清空記憶，過期刪除。
/config.schedule_policy.recent_red_s公開實際窗長；protocol仍用既有reason enum，
ACTIVE_NEIGHBORS的camera_ids可含近期候選鏡頭，並非宣告新增拓樸。

固定RGB的C原manifest37檔已逐檔驗SHA，0不一致。新舊policy均先剝除GT、舊投影與
舊追蹤，只接bbox/score/HSV/clock、safe camera calibration/graph；重播完才附回原
評分包，t1 scorer未改。保留原baseline重播與新policy重播，不覆寫C凍結資料。

| 控制資料 | all跟對／失聯 | 舊adaptive跟對／失聯 | 新adaptive跟對／失聯 |
| --- | --- | --- | --- |
| 固定RGB A4（4台） | .705263／.042105 | .694737／.052632 | .705263／.042105 |
| 固定RGB B4（3台） | .966667／.016667 | .966667／.016667 | .966667／.016667 |

新policy在原C的8台all錄製、逐tick同RGB對照中，也與all的狀態全同；舊policy僅
A4 tick22 WRONG_PERSON→LOST、B4 tick39 WRONG_PERSON→LOST，沒有跟對→失聯差異。
對原adaptive錄製做all重播仍缺原本跳過鏡頭的RGB／偵測，不可當完整all反事實。

## 原B4新實跑下降的可辨識與UNKNOWN

原all為23/51跟對、12/51失聯；adaptive為22/66跟對、20/66失聯。兩者54／69個
總tick、時刻不同。完整all錄製上套舊adaptive只多1個失聯tick（原本WRONG_PERSON），
跟對仍23/51；因此不能把兩次實跑.451→.333全部歸因為排程。

逐tick紀錄為diagnosis.json：

- all-B4：27個可見但未跟對tick仍有target-like紅衣投影，屬追蹤選擇／gate問題；
  1個所有可見鏡頭都處理卻無target-like紅衣投影，屬偵測／顏色／投影管線；3個不在可見分母。
- adaptive-B4：21個未跟對tick已有target-like投影；2個全可見鏡頭已處理仍無此投影；
  21個另有可見鏡頭被跳過，缺失觀測的反事實UNKNOWN，不能說那些鏡頭必定能偵測；
  22個跟對、3個不在分母。
- 以原評分clock fit事後做±.35秒、不得重用tick的最近時間對齊，43對中有2對
  ON_TARGET→LOST；其餘15對跟對、13對跟錯、11對失聯、2對不可見一致。
  此對齊只是描述，不是同RGB因果證明；其餘11個all／26個adaptive tick無配對。

以上把sampling與管線不確定性保留；GT只用於事後判讀，沒有傳回policy。

## ENTRY：all本身的追蹤問題，未算排程通過或失敗

沿用原定義：曾ENTRY可見、離開、再ENTRY可見episode的第一個capture，到該episode
內原scorer第一次ON_TARGET的response；首次出現不當再入鏡，無鎖定保留null/censored。
原固定RGB未錄到再入鏡，不能冒充首次鎖定為RETURN。原C兩個新實跑再入鏡仍censored。

all-A4再入鏡tick51（50.3305s）已處理全部8台，看到2個target-like紅衣投影；
最近target-like投影距前一tracker估計4.7635m，超過原4m gate。後續episode中仍無
ON_TARGET。adaptive-A4 tick62（50.6926s）同樣查全部8台，2個target-like投影，
最近距前估計4.7028m，也在gate外。這是已有目標樣觀測卻未正確重鎖的tracker問題，
不是把ENTRY加入graph即可解決；不在本PR偷改graph v4或放寬gate。新實跑仍需分列。

## 已做focused驗證與重現

Python `tests/live_mode tests/operations/test_live_launcher.py`：67 passed；
Node hud/n6/protocol/schedule：36 passed；新改Python helper/scheduler/tests的ruff check、
git diff --check PASS。server.py保留既有兩組/config鍵及逐cam門檻，沒有碰people.py、
tracker.py、advisor.py、system.mjs或protocol.mjs。

- `scripts/live_mode/replay_schedule.py` 新增評估用 --recent-red-s；0可重建舊無記憶策略，預設2。
- `scripts/live_mode/joint_schedule_diagnostics.py --source <frozen C latency> --baseline <old replay> --recent <new replay> --out <new LOCAL json>`：事後逐tick歸因、clock join與ENTRY gate距離。
- `scripts/live_mode/run_joint_validation.py --out <new LOCAL output> --models <existing RT-DETR> --assets <existing N6> --cameras <safe catalog>`：有限4次串行MPS實跑；advisor off，ephemeral localhost port，明確禁止8785。只正常shutdown自建HTTPserver，沒有kill既有程序。

LOCAL `local/evidence/cx552-d-20261118/diagnosis.json`，SHA-256 `eabdb5622ce23f22b0730360f61585904d0a100ad48c18644a52bd8a0c4d1da8`，1檔281,374bytes。
LOCAL `local/evidence/cx552-d-20261118/recent-fixed/quality.json`，SHA-256 `e3720a63dede0b24c6511ec6efa984a57fe2c0097397c093ec3a72e39c3ece2f`，1檔1,810bytes。
LOCAL `local/evidence/cx552-d-20261118/recent-fresh/quality.json`，SHA-256 `0ccbe145b14f85c25896035ac875c3d4605cb2aa267e4de7a4286aad5183ff11`，1檔2,864bytes。
可用同一凍結C輸入與上述腳本重建；新實跑時鐘、MPS浮點、延遲不保證逐bytes一致。


## 新實跑與逐條驗收

同一runtime `4fbc4af1f5d1e0594561fd3f224c419284658e15`、相同一般0.15／ENTRY0.05、
letterbox、gate4、advisor off、8台、320×180、要求5fps，串行all A4/B4後adaptive A4/B4。
A4各58秒、B4各50秒。4個瀏覽器量測exit0，自建HTTPserver已正常shutdown並join；
沒有kill既有程序或接觸8785。瀏覽器結束時已有請求的BrokenPipe保留在LOCAL log，不藏掉。

| 條件 | all→adaptive 跟對 | 跟對不降 | all→adaptive 失聯 | 失聯≤all+.02 |
| --- | --- | --- | --- | --- |
| 固定RGB A4 | .705263→.705263 | PASS | .042105→.042105 | PASS |
| 固定RGB B4 | .966667→.966667 | PASS | .016667→.016667 | PASS |
| 新實跑A4 | 7/60=.116667→10/69=.144928 | PASS | 28/60=.466667→27/69=.391304 | PASS |
| 新實跑B4 | 20/49=.408163→59/65=.907692 | PASS | 12/49=.244898→2/65=.030769 | PASS |

Protocol：4組全部0違規，PASS。新實跑仍是各1次、不同取樣tick，不把B4明顯變好全部
歸因為排程；固定同RGB對照才隔離排程影響。A4兩模式跟對率仍低，不能當身分追蹤保證。
固定RGB沿用C階段已由redetect_route.py用新偵測器重跑的凍結結果，這次runtime只改排程，
沒有把沿用偵測說成又重跑模型；另4次MPS是本日新像素推論。t1 scorer未改。

ENTRY：新all A4 tick52@50.3294s、adaptive tick62@50.5108s均查全部8台且各有2個
目標樣紅衣投影，最近投影距前估計分別4.7596m／4.6824m，均在4m gate外。
整段仍無正確鎖定，兩個target_lock_ms都null/censored；ENTRY首次處理819.1／880.4ms
只代表處理觀測，不能代替鎖定延遲。B4無ENTRY episode。機器收據標
`BASELINE_TRACKER_NO_RELOCK, pass:null`，不記排程FAIL也不記PASS，整體仍NOT_PASSED。
首次出現與再入鏡分開計算；缺值保留為UNKNOWN。

| 實跑 | 輪/s | p50 ms | p95 ms | 平均推論台數 |
| --- | --- | --- | --- | --- |
| all A4 | 1.040 | 822.3 | 932.3 | 8 |
| all B4 | 1.033 | 843.9 | 968.5 | 8 |
| adaptive A4 | 1.194 | 817.3 | 961.5 | 6.323 |
| adaptive B4 | 1.369 | 733.4 | 883.4 | 5.484 |

完整機器收據：`live_detection_20261118/d273_validation.json`。最終Python focused（含收據的
censoring與隱去絕對LOCAL輸入路徑測試）**71 passed／0 skipped**；Node36 passed／0 skipped。
LOCAL `local/evidence/cx552-d-20261118/MANIFEST.json`，SHA-256 `803e6e09ade8ab128f9e7387e42cf568127858832335892389aff7348f507090`，80清單檔／6,482,648bytes。
原C輸入37檔SHA均相符；原來源、RGB、GLB、校正、權重、scenario、GT都未改。新證據
只含新推論／重播／診斷與log，原RGB不另複製。manifest及public receipt不構成身分或實體安全驗收。

有限實跑與收據命令（在自己的clone，SHARED_LOCAL/PYTHON由執行者指定，輸出用新LOCAL目錄）：

```bash
export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export UV_CACHE_DIR=.local/demo-cache/uv
PYTHONPATH=src:$SHARED_LOCAL/data/q1q5-dynamic-baseline-v1_20261025/runtime-deps uv run --offline --no-project --python "$PYTHON" python -B scripts/live_mode/run_joint_validation.py --out "$D_OUT/fresh" --models "$SHARED_LOCAL/data/demo-owned-v1/models/rtdetr" --assets "$SHARED_LOCAL/data/live-assets-20261115" --cameras "$SHARED_LOCAL/data/r004-build-v2-20261021/safe_static/cameras.json"
PYTHONPATH=src uv run --offline --no-project --python "$PYTHON" python -B -m pytest tests/live_mode tests/operations/test_live_launcher.py -q
node --test frontend/live-mode/test/hud.test.mjs frontend/live-mode/test/n6.test.mjs frontend/live-mode/test/protocol.test.mjs frontend/live-mode/test/schedule.test.mjs
PYTHONPATH=src uv run --offline --no-project --python "$PYTHON" python -B scripts/live_mode/joint_schedule_d_receipt.py --work "$D_OUT" --out docs/evaluation/live_detection_20261118/d273_validation.json --python-passed 71 --node-passed 36
git diff --check
```

`D_OUT`需先有本文件前述baseline/recent固定RGB與原fresh-source重播，receipt在實跑完全結束後才freeze manifest。
它引用LOCAL完整composition的SHA，提交的副本移除絕對輸入路徑。raw composition保留精確args、
runtime檔案SHA與4個exit code；未宣稱最終文件commit也重新實跑了runtime。

## D282 交付決定

ENTRY 正確重鎖延遲維持 UNKNOWN。分段門檻契約與後續驗證由
[#585](https://github.com/Polalalabear/amidst/issues/585) 追蹤。
D282 授權將 main 整合進 #559 的 feature 分支。合併保留 #563 的 /config CORS、POST Host
檢查及 LLM 欄位，並保留偵測／排程欄位與逐鏡頭門檻。整合後的驗證為 Python 與 Node 回歸。
新實跑數字仍對應上文的 D273 runtime。正式審查與合併流程見 #559。
