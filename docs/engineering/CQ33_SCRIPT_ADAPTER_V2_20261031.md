# CQ-33 adapter v2 與 UNFROZEN 甲卡計畫

2026-10-31（Asia/Taipei）。交付評分端 adapter、producer CLI 草案及 RR／LG／PE1／OV1 四張 private planning config。沒有凍結劇本、開 checkpoint、渲染或建立 safe bundle。

## 來源與 D97 組合

- base #366 `a7bf25d84cd47a0c7b651be78ce7e2839d3fa859`（CQ-32 scorer，含 #258 設計與 #360 測試）。
- 接入 #254 `3ccfc556b183e53d4ef7ca13b6119a92ba27798e` 的 v1 adapter 與 #362 `71a3f34929854951a9b3fce30a53fb812b0ea692` 的 -T，使用 feature merge commits，不合 integration。
- #261 `6ab2a6e37d83bc236380f5a9e8c06027e81eeda0` 只納入 `docs/evaluation/R004_COMPLEX_SCENARIO_CARDS_V2.md` 的精確 bytes（`849ba441c62c453d13d6910b7af914eaca47726809e9d0dfb7297641cc596b69`）；不是整支 mainline 合併。原分支無關 AGENTS／CLAUDE／README／handoff 等文件不帶入本 PR。
- 資料來源依 D99 選甲卡；U6／U7、G4、凍結與渲染條件仍分開。

## 實作行為

`q5_script_adapter_v2.generate_script` 讀取明確 plan／parameter／decision-config bytes pins。private plan 的 `q5-script-plan.v2` 是本任務的 **PROPOSED planning config**，不是新 authority receipt 或 runtime wire；以 v1 plan 的欄位為基礎，逐鏡頭計畫轉成 #258 的 `entry_windows_us`／`plan_anchor_us`。不修改權威 schema、v1 adapter 或 v1 scorer。

`q5_switch_eval_v2.derive_plan_event` 抽出既有整數公式供 scorer／adapter 共用；舊 `derive` 仍逐項驗證原來的分類、窗、固定 O1 及 RETURN 上界。沒有兩份各自實作的窗公式。adapter 自己計算前一窗終點，不相信輸入自填 `t_prev_end_us`。

事前拒絕 D94 開區間、早可見 BLIND、未選 U-D5／LONG_GAP U-D9、超過 selected／預設保守三輪 SEARCHING、BLOCKED_GEOMETRY、未知分類、參數 pin／content／grid 錯誤。第一批只支援 SWITCH／RETURN；NO_SWITCH／LOST_TAIL 及其他批次尚未實作，保持拒絕。

原生 q-demo parameter-set.v1 必須通過 scorer 的 canonical content hash、ID、run 適用範圍及 numeric binding 檢查。Synthetic -T 的精簡參數僅透過 `SyntheticPlanInputs` in-memory seam，要求 SYNTHETIC run／clock／plan ID 與 UNFROZEN status；沒有 CLI 旗標能開此 seam。

BLIND 的 t_L／t_V 及 overlap 的連續區間檢查僅用於測試中的計畫准入，不輸出到 script，不能變成 entry_time、評分時刻或推論輸入。真實計畫的 timing-method evidence 介面尚未採納，即使選 PLAN_CHECK_ONLY 仍 `PLAN_CHECK_EVIDENCE_UNSELECTED`；不能以自填 `evidence_kind` 通過。D93只允許 synthetic EXT pair 測 O1；W1/W2、BRANCH/WIDE 不因此升權。

`scripts/gen_q5_script_v2.py` 是評分端 producer 草案，參數為 `--plan`／`--parameters`／`--decisions-config`、各自 bytes `--<name>-sha256` 及 `--output`。預設全 PENDING config 拒絕產物；顯式安全選項可生成 PROPOSED preview。`--formal` 固定拒絕，FROZEN input／自填 approval URL 不會核准。輸入須 canonical regular file，輸出 exclusive create；無 renderer、模型、API 或 checkpoint 操作。

## 四卡草案的邊界

四個 `configs/evaluation/l2_<rr|lg|pe1|ov1>_script_plan_v2.json` 全部 `UNFROZEN`、approval null、真實 run／clock／parameter ID／content hash UNKNOWN。已給定數字逐字轉為整數微秒；沒有推定新的 clock／run ID。

| 卡 | 保留的計畫 | 仍阻擋的內容 |
| --- | --- | --- |
| RR | 查詢 [0,28) s，run30 s；四次1.2 s暫失；a1/a2 STANDARD | b1/b2分類UNKNOWN；合併或拆分規則與4／5輪預算未定；真失聯未驗 |
| LG | [0,22) s，run24 s；t_X5、W1 t_N12.4 s | SOUTH只為計畫footprint；t_L／t_V、P-OV3、guard、seed未知 |
| PE1 | [0,20) s，run22 s；t_X6、W1 t_N9、W2 t_N10.4 s | BRANCH seed MISSING、競爭候選與真正entry未知 |
| OV1 | [0,24) s，run26 s；兩個t_X6／16 s，固定O1 | P-OV1/2/3、G4、連續路線與逐場次seed未定；不自編第二request |

這些檔案是可審查計畫，**不是可執行／可凍結卡片**。沒有為了通過 adapter 刪除 RR-b、猜 t_L／t_V、縮改 query 或以合成參數核准 r004。S1–S6 與全場景可行性、完整 producer renderer 接線亦未宣稱已驗。U7核定前不產生 freeze candidate／checkpoint 草稿；完成這一步仍需要使用者／協調者決定。

## 驗證

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests/evaluation AMIDST_REQUIRE_IMPL=1 AMIDST_Q5_ADAPTER_V2_DRIVER=q5_adapter_v2_test_driver AMIDST_Q5_V2_DRIVER=q5_v2_test_driver uv run --no-project --offline --no-cache --python /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization/.venv/bin/python python -m pytest -o addopts='' -q -p no:cacheprovider tests/evaluation/test_q5_script_adapter_v2.py tests/unit/test_q5_script_adapter.py tests/evaluation/test_q5_switch_eval_v2.py tests/unit/test_q5_switch_eval.py
```

**225 passed、0 failed、0 skipped（2.93 s）**。範圍為 #326 的 -T／v1 adapter，加上共用公式受影響的 #324 focused 測試。新增 native adapter→scorer 往返使用真正 q-demo parameter-set 結構及 output pins，結果僅 SYNTHETIC；不是正式人體／研究接受。另驗三種輸入 pin、凍結／formal／synthetic 升權拒絕、私有檢查欄位不流出、四卡預設拒絕、CLI 正常 preview／拒絕／不可覆寫。

初次 6 個失敗為 source export 少了固定版 `scripts/eval_q5_switch.py`；補回原 bytes 後相同檢查通過，未修改測試以隱藏缺檔。縮小依賴組合時驗證所有 code／tests／configs／pyproject bytes 與受測組合完全相同，不重跑無關全套。

v1 adapter bytes `dc6f3756420a5fb8632235edb3083d853102d95ce8b9c221be94a93b05dba757`、測試 `2b4c0cac26ee30b2b4fe663fb283d09569378d7a5e28f4e48d6c25951d19a62d` 不變；A15 v1 scorer／測試亦不變。候選 commit 的 `git diff --check` 通過。ARCH **NOT_RUN**（#307未交付）；#127 recorded kit **NOT_RUN／無新product recording**。未做 formal freeze、渲染、推論、原資產修改、Claude複審、合併或發包。
