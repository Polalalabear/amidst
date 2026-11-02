# CQ-33 adapter v2 與 UNFROZEN 甲卡計畫

2026-11-02 FEAT-4 續作。四張卡對應五份 private plans（RR 兩個 request）；沒有凍結劇本、開 checkpoint、渲染、索引或建立 safe bundle。

## 現行來源

- 整合依 #371 歸併順序；v1 adapter #254、v2 scorer #366／-T #360／#362 保留可追溯 merge commits，另接已交 FEAT-1 #394 的共用檢查器與 FEAT-7 守門。
- 卡片只引用 #261@`b5302a0ad9a1895d728946d824854b6001b6b66a` 的遠端原文，SHA-256 `02d98c06ac93b5b1eec019d65415eada7b751b4c6e76d3982a28aa36d9efd88b`；本整合樹刪除 #367 夾帶的副本（D105 B-4），不合 mainline 分支。
- U6／U7 已由 D105 定案。CLI 預設採定案檔 `q5_v2_decisions_u6_20261101.json`，SHA `0daa1508e2a67607cdc6bac54684b1b5449d3a651325e5af23dfe0afb1bd3b7e`；舊預設 `q5_v2_decisions.json` 全 PENDING 保持原樣。U-D1／U-D2／U-D4 仍 PENDING_USER，OV1 正式不計分。

## adapter 的已驗行為

`generate_script` 驗 plan／parameter／decision-config 原 bytes pins，private `q5-script-plan.v2` 仍是 PROPOSED planning config，不是 authority receipt。窗／分類與 scorer 共用整數公式；自行算前一窗終點，不信來源自填 t_prev_end。拒絕 D94 開區間、RETURN d≤L、前窗截斷、早可見 BLIND、超出 SEARCHING 預算、BLOCKED_GEOMETRY、未知分類或來源／參數不符。沒有更動 v1 adapter／scorer bytes。

SYNTHETIC 精簡參數及 t_L／t_V 證據只經型別化 in-memory seam；不能從 JSON／CLI 自行開啟。BLIND／OVERLAP 計畫檢查不進 script，也不進評分或推論。正式來源的 timing-method evidence 尚無已定的載入／重算投影；自填 evidence_kind 或計畫數字不能通過。P1-5 的真實 UK-8 路徑尚未完成，預設仍 PLAN_CHECK_EVIDENCE_UNSELECTED；P-OV3 未驗，UNKNOWN 不能通過。

CLI 仍只能輸出 PROPOSED preview。P1-6 的 formal／APPROVED 路徑尚未完成，--formal、FROZEN input／自填 approval URL 固定拒絕；卡片核准不等於 v2 劇本凍結 hash 核准。run／clock／parameter／seed 與新凍結核准尚缺，不能虛構 positive 正式產物。

## 五份計畫

全部 UNFROZEN、approval null、真實 run／clock／參數綁定 UNKNOWN。

| 計畫檔 l2_*_script_plan_v2.json | query／事件 | 計畫搜尋 | 待件 |
| --- | --- | --- | --- |
| rr | S_a [0,14)；RR-a1／a2 STANDARD RETURN | 2≤4 | 同一 RR run 的 W1@0 真實 seed MISSING |
| rr_b | S_b [14,28)；RR-b 合併 LONG_LOSS（17→19.8） | 3≤4 | 同一 run／clock，不重設來源時間；W1@14 只是計畫定位，seed UNKNOWN／observation_id MISSING |
| lg | [0,22)；t_X5、W1 t_N12.4 | 依定案公式重算 | safe_static 真實 UK-8／P-OV3／seed |
| pe1 | [0,20)；t_X6、W1 t_N9／W2 t_N10.4 | 1 | BRANCH seed、真實 BLIND／競爭候選 |
| ov1 | [0,24)；兩個 t_X6／16，固定 O1 | 2 | 正式只展示；P-OV1/2/3、連續路線、G4、新 scope／session來源 |

S_a／S_b 是兩個新 request／session，不能在同一 session 換 seed 歸零；兩份計畫須註冊同一個實際 RR run／clock 才能走資料段。這些計畫不冒充 runtime request 或已核准 script。

## 驗證與尚缺

`AMIDST_REQUIRE_IMPL=1 AMIDST_Q5_ADAPTER_V2_DRIVER=q5_adapter_v2_test_driver PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests/evaluation uv run --no-sync --offline python -m pytest -q tests/evaluation/test_q5_script_adapter_v2.py tests/unit/test_q5_script_adapter.py tests/evaluation/test_feat4_plan_sources.py`：100 passed。新增檢查遠端原卡 head/hash、沒有副本、絕對來源時間與兩個預算；原 adapter -T／v1 斷言保留，只按 D105 更新 RR 草案事件清單。

真實 UK-8、formal freeze、#328→#329→#330 正式資料仍 NOT_RUN／blocked。需要的介面／來源定案列在 #371；不以 source pins 自洽當人類核准，不用 renderer／GT 補未知值。demo 前若未解，依 D105 明列「甲維持 UNFROZEN，走 fallback」。
