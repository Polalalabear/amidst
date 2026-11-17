# #559 D273：近期候選鏡頭與逐 tick 歸因

本文件接續[第三份指示](https://github.com/Polalalabear/amidst/pull/559#issuecomment-6952347393)。
此階段只修排程，不改預設為all、不改偵測門檻、graph、tracker gate或原t1評分。
**目前不是聯合驗收通過；新的串行實跑及最終收據待補。** 保持Draft。

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
