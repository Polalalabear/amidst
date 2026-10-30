# CQ-33-T：評分端；與推論隔離

這是 #327 的 test-only 合成輸入與手算 golden，**不是正式 plan schema、卡片核定、authority 或 renderer 輸出**。所有數字只為驗公式；沒有原始資產、GT、formal/clean 包 bytes 或私人路徑。正式 adapter v2 尚未交件；本任務不補 stub。

來源：#258 `f19fbcfd2ff64c483fedb00bd9be2e72e97a2af3` 的 §1–3；D93 O1／D94。#261 `6ab2a6e37d83bc236380f5a9e8c06027e81eeda0` 僅提供卡片類型。以下時刻另行合成，並非抄成可執行的實際卡片。RR 只測兩個分開的 STANDARD RETURN 對照，不核定 RR-b 的未決合併規則。

## 手算（秒；JSON 使用整數微秒）

固定 Δ=.2、L=.6、W=6、R=1、N_max=6；G1=5.2。

| 合成卡 | 輸入 | 決策窗 | 進入窗 | SEARCHING |
| --- | --- | --- | --- | --- |
| RR | RETURN 6→7.2；16→17.2 | [1.2,8.2)、[11.2,18.2) | 無 | 2 |
| LG | SWITCH 10→17.4，g7.4 | [min(17.4,15.2)−6,18.4)=[9.2,18.4) | [16.8,18.4) | max(1,ceil((7.4−6.6)/1)+1)+1=3；RETURN上界2 |
| PE1 | SWITCH 10→{13,14.4} | [min(13,14.4)−6,max(13,14.4)+1)=[7,15.4) | A[12.4,14)、B[13.8,15.4) | 1 |
| OV1 | EXT_CAR→EXT_CLEAR，t_X10，O1等效錨10.6 | [4.6,11.6) | [10,11.6) | 1 |

RR／RETURN 端點額外驗：d1.6仍STANDARD、窗[1.6,8.6)；d1.8為LONG_LOSS、窗[1.8,8.8)、RETURN上界2。反例逐卡一份：RR的d1.7拒絕；LG的g8耗4輪，U-D10 PENDING時較嚴≤3故拒絕；PE1的t_L10<t_V12<t_N13−.6拒絕；OV1標BLOCKED_GEOMETRY拒絕。LG反例的t_V17.6≥18−.6，避免混入早可見拒絕原因。

`parameters` 的 canonical UTF-8 JSON（sort_keys，compact separators，ensure_ascii=False）hash 是合成 parameter binding 的 content hash，**不是正式參數檔 pin**。計畫檢查的 t_L/t_V 只是 synthetic pass/fail inputs；不得透過 native script 輸出到評分窗口或推論。未知選項沒有預設升權；移除 test selections 的 LG 必須拒絕。

## TEST-ONLY driver 接法（#326 到位後）

環境變數 `AMIDST_Q5_ADAPTER_V2_DRIVER` 指向測試 glue module，提供 `exercise_case(*, inputs, implementation)`。這個名稱與以下 result envelope 不是產品 API 或 schema；#326 可依正式實作介面接 glue，不必為此改 authority。

- `implementation` 是本 snapshot 的 `amidst.evaluation.q5_script_adapter_v2`。glue 只可把 test-only plan/parameters/selections 轉成實作公開 API 的合法參數；PENDING不是核准。不能回傳 golden、代算窗口或建立假實作。
- 測試傳入前會移除 `expected_*`，glue 看不到期待答案。測試 trace 必須觀察到真 adapter 檔的函式呼叫，並比對其檔案 SHA。
- 回傳 `rejected: bool`、`native_script: dict | None`（實作原樣輸出，不得改寫）、`implementation_file_sha256`、`human_approval_verified: false`。成功另回 `planned_searching`（取實作的計畫檢查結果）。拒絕時依實作 exception/code 對應 test-only `error_category`：`D94_RETURN_GAP`、`SEARCHING_BUDGET`、`EARLY_VISIBLE_BLIND`、`BLOCKED_GEOMETRY`、`PROPOSED_RULE_UNSELECTED`、`VERSION_UNSUPPORTED`。
- v1 輸入可拒絕，或回 `dispatched_version: "v1"` 加原生 v1 script；不能默默轉v2。任何選定 glue 的壞 import 都是 error，不能吞成skip。
- positive test selections 只是在 SYNTHETIC 場合指定待決公式以便覆蓋；不核定 U-D5/U-D9/UK-8/U7。腳本仍 PROPOSED、approval_ref=null、approval_content_sha256=null。若未選定，預設fail closed。

缺實作時一般模式 `pytest.importorskip`；`AMIDST_REQUIRE_IMPL=1` 一律 `CQ33_IMPLEMENTATION_MISSING` fail。實作有了但 glue 未綁時是 `CQ33_TEST_DRIVER_UNBOUND`；strict模式不允許glue skip/xfail。主任務須完成真實 glue，不能以12skip當驗收。

## 依賴到位後怎麼跑

```bash
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/evaluation/test_q5_script_adapter_v2.py tests/unit/test_q5_script_adapter.py
```

執行上式前應依實作接好 `AMIDST_Q5_ADAPTER_V2_DRIVER`，並納入 #254 的 v1 adapter/tests；本 -T PR base 是 staging，**不把 #254 程式複製進本 PR**。本次驗證使用 LOCAL source snapshot，staging@434e57922a24d2422226871c0bb672dc7bc3584b 加上 #254@3ccfc556b183e53d4ef7ca13b6119a92ba27798e 的五個既有檔（adapter、v1 test、CLI、A4/B4 plans），皆保持bytes。

## 實際結果

Model / effort：GPT-6（Codex） / UNKNOWN。正常模式 **74 passed,12 skipped**（1個fixture檢查＋73個既有v1案例；v2實作12缺失）。strict **74 passed,12 failed,0 skipped,0 errors**；失敗都是 `CQ33_IMPLEMENTATION_MISSING`，不是已完成v2功能。最初snapshot缺 `amidst.domain` 造成1 collection error，補齊同一staging SHA的domain/navigation/geometry相依項後已消除；沒有改測試繞過環境。

`python scripts/check_architecture_guard.py`：NOT_RUN，#307尚未交付。#127 kit NOT_APPLICABLE（純adapter test-first，沒有產品回應或recording）。正式U6/U7、渲染、評分與凍結全部未驗。
