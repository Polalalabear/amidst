# Line 2 linker／Q5 controller 契約提案與 C1–C10 回覆

日期：2026-10-27。狀態：**PROPOSED，未核定、未改產品**。任務 [#248](https://github.com/Polalalabear/amidst/issues/248)，回覆 [#258](https://github.com/Polalalabear/amidst/pull/258) 設計稿 §5。

**固定設計對照基準：**[#258 head `0a87c3045923378f25c464e2bc43629612235233`](https://github.com/Polalalabear/amidst/blob/0a87c3045923378f25c464e2bc43629612235233/docs/evaluation/Q5_SWITCH_EVAL_V2_DESIGN.md)（短碼 `0a87c30`）。依本次使用者提醒，該設計仍有14項待核定；本提案不代選任何待決選項，也不把C1–C10現行程式回覆當評分規則已採用。核定後如設計有變動，另補一份綁定新head／決策編號的對照，保留本次固定基準紀錄。

本文件的「現行」只指 staging `680ca357a31b664bed3feb6a5284dcd7c5c0d94d`。回答依下列固定原始碼與契約，不把未合 PR 當作已發布行為。D73 §14-27 與 D90 保持：產品沒有 `lost_after_us`、沒有 LOST／FOUND enum；長空檔／長暫失只在評估端分類。本次不改 Line 1 圖 v3、G4、D89、D79、#222 或任何現行 schema。

## 1. 給評分器實作者的主要結論

- 第一次 SEARCHING 就算第 1 次。第 N 次正常完成決策；成功 SWITCH 後仍可追蹤。**企圖開始第 N＋1 次**時才終止，不產第 N＋1 個快照。N=6 時，第 6 次不是先終止。
- 連續索引格下，首次決策 `D0 = t_last + L = t_fm + L − Δ`。5 fps、L=0.6 s 時，是第一個缺格後 0.4 s，不是 0.6 s。這是現行條文 §8.2 與程式一致的結果；設計稿中另一相位須由評估端調整／明列差異，不能改產品一格來配窗。
- 原鏡頭長暫失後可逐格直接探測恢復，開**新 local segment**；不必等下一次重搜，不以舊框做無限外推。
- `ENDED_BY_LIMIT` 與 COMPLETE 使用相同 q2-response.v1，包含原始 journal hashes。但 LIMIT 的 timeline 會把 ENDED GAP 填到查詢終點，**不是從停止時刻到查詢終點都有執行證據**。若採前綴評分，停止時間應取終止 journal，不得只看 timeline 尾端。
- `resolved_scope.parameter_set_id`／`parameter_set_sha256` 已存在，無須為 v2 評分新增產品欄位。

## 2. C1–C10：現行行為與位置

以下行號綁定 §5 的固定 SHA；`controller` 指 `src/amidst/q1q5/q5_controller.py`。

### C1：session_max_research_rounds

**VERIFIED。** `_search` 先檢查已用值 `>= N`，未到才加 1、產快照、決策（controller:537–550）。首次計為 1；N=6 可執行六次。第 6 次 RETURN 後仍可在原鏡頭探針恢復；第 6 次 SWITCH 後仍沿新鏡頭追蹤。只有下一次需要 `_search`（或人工改選欲開新 SEARCHING）才因上限終止；若查詢先結束，回 COMPLETE／適用的 PARTIAL。

**條文差異：**契約 §8.6 表格「任何狀態／達到 session_max_research_rounds」過於簡略；本文件提出 §3.1 的精確化文字，沒有把第 N 次提早終止。D73／D90 的 LOST 分類不等於 session 輪數期限。

### C2：決策相位與重搜格點

**VERIFIED。** `LinkParameters.max_gap_samples = L / Δ − 1`（linker:92–98）；失配格的 `gap_samples = elapsed / Δ`，大於導出格數便 SEARCHING，`decision_time_us` 就是目前格的 timestamp（linker:276–308；契約 §8.2）。因此連續缺格時 `D0 = t_fm + L − Δ`。若門檻那格成功接上，則不 SEARCHING。

RETURN 後，每個目前鏡頭的索引格先做探針；仍未取得，且 `timestamp − returned_at >= research_interval_us` 才重搜（controller:662–690）。有效 grid 要求所有使用鏡頭同一 index interval、R 整除 Δ（controller:288–306）；在無重新取得、人工改選、缺資料或提早終止的條件下，`Dk = D0 + kR`，都落在索引格。每次 RETURN 後窗口從當次重搜 timestamp 起，首次窗口從 first missing 起（controller:669、681；契約 §14-13(a)）。

`t_fm` 是第一個**沒有合法連上**的索引格，不等於幾何出口 `t_X`。漏檢、IoU 拒絕、MISSING 都可能使它提早；不能用劇本 `t_X` 反填 controller 的缺格時刻。若 renderer 不參與，計畫路線投影只提供靜態幾何估計，仍不能證明實際 detector 的 t_fm。

### C3：每次重搜是否都有 accepted RETURN

**VERIFIED。** 每次 `_search` 無合法 SWITCH 時，均寫 `state_before=SEARCHING`、`state_after=RETURNED_TO_ORIGIN`、`executed_action=RETURN_TO_ORIGIN`、`accepted=true`（controller:574–578，accepted 預設在:410–420）。之前已 RETURN 也一樣；沒有 CONTINUE_SEARCH action。各次另有進入 SEARCHING 的 action=null journal。

例外要分開：達上限的嘗試只寫 ENDED，不再 RETURN；人工 override 可取消自動提交；stop／錯誤也不補假 RETURN。v2 一窗多 RETURN 應數 accepted action records，不能數所有 SEARCHING／RETURNED 狀態紀錄。

### C4：長暫失後回原鏡頭

**VERIFIED。** LocalLinker 進 SEARCHING 後該 local segment 結束，不能再 step 復活（linker:145–147、221–222）。D78 中心平移僅適用 `0 < elapsed <= L`、有最後兩個真實已連接框且最後真實框未找到合法候選時（linker:255–266；契約 §8.2、§14-30）。

RETURNED_TO_ORIGIN 的每個索引格，先讀目前真實 INFERRED detections；person／query_min_score／指定顏色 STRONG 過濾後**恰有一個**才建立新 linker，並驗它也符合 linker seed 條件（controller:618–634、662–666、376–379；linker:149–163）。沒有以舊框與相隔 3 s 的新框做 IoU／平移，也不確認同一人。0 或多個候選維持 GAP；分數／顏色不合法也不能恢復。

因此 gap=3 s 不自動阻止原鏡頭恢復，無須把原鏡頭塞成候選等待下一次重搜。診斷保留 `UNCONFIRMED_NEW_LOCAL_SEGMENT`、舊／新 segment ID、真實 observation 和時間。timeline 的 REACQUIRED 是展示重新取得，不是身份判定。若 query 門檻低於 linker seed 門檻，仍須符合後者；不可保證任何 query-qualified 候選都可成為 seed。

### C5：v4 重疊對、出口與排序

**(a) UNKNOWN，待 E2／E3 靜態草案與獨立複核。**現行圖 v3 沒有本次要求核定的新轉移。出口使用最後真實 bbox 的 bottom midpoint 對 pixel ROI 判定；唯一命中才選其出口，零／多命中採全部出口的保守候選（candidates:51–56）。靜態 ROI 應畫在原鏡頭投影範圍的出界側，逐方向標註；但 floor footprint 的邊緣不保證人物 bbox／detector 最後支持恰在 `t_X` 前一格。不得以靜態投影宣稱 P-OV2 已驗證，更不能回填 renderer visibility。

v4 草案至少記來源校正／幾何／ROI pins、方向、出口 polygon、幾何投影與遮擋未知項；EXT_CAR↔EXT_CLEAR、BRANCH↔WIDE 可提出，W1↔W2 維持 PENDING_G4，不預決 M1。靜態邊緣無法滿足 O1 前提時，回報 UNKNOWN／不計分建議，由 Claude 與使用者決定評分規則，不由 controller 偷放寬。

**(b) VERIFIED。**依 D28，relation UNKNOWN 為 tier 4；其餘有 `path_has_unknown_state` 為 tier 3；無 unknown 的 OVERLAP 為 tier 1、BLIND_GAP 為 tier 2。同 tier：`ranking_area_m2` 非 null 在先、數值由大到小，再按 camera_id。每個目的鏡頭先挑最佳轉移，保留其他 route IDs；只在合法 run camera scope 篩選後才排序／top-k（candidates:57–90）。因此未核定或 unknown 的重疊轉移不保證排在已核定盲區前。scope 未核准時 candidates:63–74 直接排除，不能藉草案 OVERLAP 標籤取得 tier 1 權限。

**(c) VERIFIED，但須補限定。**entry 是候選窗口、可用媒體／查詢範圍內，timestamp ≥ decision_time 的**最早合法 guard observation**，再以 score 降序、observation_id 排同時刻；不是不帶條件的第一筆 observation（controller:450–459、497–502；q4_evidence:139–140）。SWITCHING 先在 decision_time 寫 accepted SWITCH，PLAYING 在 entry timestamp 寫 completion，無另外設定的等待延遲（controller:566–572）。若 entry 晚於決策，就保留兩者之間 GAP；不倒退取重疊鏡頭早已存在的舊觀測。D90 仍要求原鏡頭失配達 L 進 SEARCHING 後才能自動切換，沒有預先接手。

### C6：LIMIT／COMPLETE 的回應、覆蓋與終止紀錄

**VERIFIED。** `_finish` 對兩種 status 都產 `q-demo.q2-response.v1`、timeline、decisions_ref／decisions_sha256、links_ref／links_sha256、output_sha256 與完整已產 journal（controller:698–721）。JSONL hashes 對原 bytes 計算；output hash 排除 stats。

達上限時 `_search` 在**被拒絕的新搜尋 tick**寫 `state_after=ENDED`、source_time_us=該 tick、decision_time_us=null、executed_action=null、searching_index 仍是 N；隨後把 timeline ENDED GAP 延到 query right（controller:538–539、684）。終止 journal 不表示第 N＋1 次已搜尋。正常走完會 `_emit(state, ENDED, right)`，所以 COMPLETE 有 source_time_us=半開查詢右端的終止紀錄（controller:691–696）。該紀錄是終止界線，不能當右端的真實觀測／切鏡。

**前綴評分限制：**timeline 右端在 LIMIT 也可能等於 query right，故「完整 timeline」只能解釋為輸出結構與 GAP 覆蓋完整。LIMIT 之後未執行，不可憑它宣稱 NO_SWITCH 一直涵蓋到 right。提案 §3.3 使用終止 journal 作 evaluated prefix cutoff，沒有新增產品欄位。

### C7：parameter_binding

**VERIFIED，已有欄位。** `response.resolved_scope.parameter_set_id` 與 `parameter_set_sha256` 初始化為 nullable，成功驗準參數後寫入（controller:122–125、284–287），_finish 原樣輸出。hash 是契約的 canonical **content hash**（排除 parameter_set_id、content_sha256、stats），不是 parameter.json 原始 bytes SHA；request 也必須同 parameter_set_id。

評估端需載入獨立凍結的 parameter-set 原文，重算 content hash，確認 ID／scope／index grid 與 response 相符後，才取得 Δ、L、R、N；只有 hash 字串不足以重算窗。UNKNOWN 回應若尚未跑到參數驗準，值可能 null；不得補猜。若另收 raw file SHA，放評估 receipt，勿覆寫既有 content hash 或暗加現行 strict wire 欄位。

### C8：run 中途 seed 與分場次

**VERIFIED。** Q2 支援 `seed={kind:OBSERVATION, observation_id:…}`，time 可用 SOURCE 的單 run 半開 range_us，或合法 WALL 範圍（controller:255–266、318–324、354–372）。seed 必須在解出的查詢範圍／媒體可用範圍、INFERRED index 格、追蹤相機範圍，且通過 person／score／linker seed 驗證；不能用劇本的 actor ID 當 observation。

各場次各送一個 Q2 request：例如同 run 的 [2,4) s 與 [6,8) s，分別選範圍內顯式 observation。每份 response 的 `resolved_scope.resolved_source_ranges_us` 各只列該場次；不要把同 run 的兩個範圍塞成一份 v1 Q2。session_id 由完整 request、各 pins、selected seed 導出（controller:126–128），不同時間／seed 會導出不同 ID；完全相同輸入重播得到相同 ID，不能假稱每呼叫一次都隨機新 ID。`session_ref` 是既有授權上下文，不拿來冒充場次編號。

### C9：反覆短暫失與計數

**VERIFIED。** PLAYING↔TEMP_LOST 的短暫失不加 searching_index，也沒有反覆次數期限；成功 LINKED 清 first_missing_us、更新最後兩個真實框，維持同一 local segment（linker:291–305）。只要某次連續失配達 L 才開始 SEARCHING。N 不因成功接回、SWITCH、回原探針或人工改選重置；episode Agent 預算與 session 累計分開（controller:540、589–616、662–690；契約 §8.6）。

不能把「反覆但每次 < L」加總後分類成產品 LOST；評估可以另外描述計畫事件，不能回流修改產品狀態。

### C10：searching_index

**VERIFIED。** 每次真正開始 SEARCHING 加 1；同次進 SEARCHING、accepted RETURN 或 SWITCH、SWITCHING completion 沿用同值（controller:410–426、537–578）。新的 SEARCHING 跨次嚴格遞增，RETURN 一定帶此值。尚未 SEARCHING 時是 0；達上限的終止沿用 N，不出 N＋1。

v2 searching_count 建議從**窗內實際進入 SEARCHING 的 journal**取正整數 index 相異值；多條同 index journal 不重數、idx=0 排除。不要對窗內全部記錄的 index 直接 distinct，因為窗開始前的搜尋所留下的 PLAYING／ENDED 紀錄也沿用舊 index。action counts 另外依 accepted、executed_action 和核定時間窗計算。人工 USER SEARCHING 如納入計數，須獨立列來源，不能冒充自動漏檢。

## 3. 待確認的 Line 2 契約文字草稿

下列是提議加入後續 Line 2 文件的精確化文字，**不是本 PR 修改／核定 v1 條文**。現行產品、數值、Line 1 評分分母都維持；Claude 可依 §2 事實修設計稿，但其 §6 使用者待決選項不能由本文件代選。

### 3.1 linker 與 session 時間規則

1. L 是單次連續失配觸發門檻，以最後成功真實觀測為基準；門檻格若匹配成功不算失配。連續 grid 的首次 SEARCHING 為 t_fm＋L−Δ，不額外延遲一格。已觸發 SEARCHING 的舊 local segment 結束。
2. session_max_research_rounds=N 表示最多允許開始 N 次 SEARCHING。第 N 次可正常決策及追蹤；欲開始下一次時記終止。成功取得、人工改選與模式切換不退還 session 累計。
3. RETURN 後每個索引格先探測唯一合法目前觀測。取得則新 segment＋UNCONFIRMED 關聯；未取得且滿 R 才開新 SEARCHING，新窗口從該 tick 起。
4. 不設定 LOST 期限、不增 state enum；不因計畫 g／d 長度裁掉目前合法觀測。

### 3.2 重疊轉移

1. v4 僅是新圖／scope 版本；Line 1 v3 hashes、核准、候選與評分不變。三組雙向轉移逐方向給出口 ROI，W1↔W2 保留 PENDING_G4。
2. 自動接手仍必須原鏡頭失配達 L、進 SEARCHING；依現行 D28、guard 與 earliest legal entry，沒有「已共視所以直接切」捷徑。
3. 出口採最後真實 bbox bottom midpoint；靜態可行性不能確認實際最後偵測格。P-OV2、O1／O2／O3 是否採用由評估端與使用者決定，未驗證時記 UNKNOWN。
4. 未核定圖／scope 不因 OVERLAP relation 自動取得正式候選權限；M1 的授權結果仍另案。

### 3.3 評估側 adapter／receipt，runtime 不 import

評估 v2 可新增其獨立版本的 receipt，綁定 response output_sha256、decisions／links 原 bytes SHA、parameter content hash 及可選 raw file SHA、scene/run/clock/index/graph/scope pins、設計版本、場次 request 與 seed observation。這些是評估產物，**不在現有 q2-response.v1 或 decision-record.v1 暗加欄位**。

- 只有在凍結產品輸出與驗 pins 後，評估端才讀計畫劇本與時刻。g>5.2 s 的 SWITCH、d≥1.8 s 的 RETURN 依 D90 分類，標記是評估類別而非產品狀態；邊界不混同為 g≥5.2 s 或 d>1.8 s。
- 若使用者採前綴評分，cutoff 取同 session 的 ENDED journal source_time_us；實際受評範圍 `[query_left, cutoff)`，終止點本身另外判定。timeline 補到 query right 的 ENDED GAP 不證明後綴的 NO_SWITCH。cutoff／終止紀錄缺失或 hash／scope 不符時 INCOMPLETE，不自補。
- 分別報 searching_count、accepted RETURN／SWITCH 數、USER actions、TERMINATION；不要以多條 journal 當多次決策，也不能用最後一個正確 SWITCH 掩蓋之前錯切。
- C2 相位可能改變設計稿中 RETURN 上限與首次決策的推導，須重算後再送核定。既有 D79／#222 不回寫；LONG 類、OVERLAP 窗及 LIMIT 評分選項仍 PROPOSED。

## 4. 本次限定驗證

**實測，僅 SYNTHETIC 記憶體 fixture；不是人題、模型推論、真實 RGB 或場景驗證。**既有 fixture 使用固定小 PNG 與 hardcoded detector stand-in，未載入或呼叫 detector／LLM 模型。本次未新增／修改程式或測試。

| 情境 | 實測 |
| --- | --- |
| 連續缺格、Δ=0.2 s／L=0.6 s／R=1 s／N=6 | first missing=0.4 s；RETURN 決策 0.8、1.8、2.8、3.8、4.8、5.8 s；index 1–6；6.8 s 嘗試新搜尋才 ENDED_BY_LIMIT；終止 index=6，timeline GAP 卻到 query right=12 s |
| 第 6 次有合法新鏡頭觀測 | 第 6 次 accepted SWITCH；後續持續追蹤至 12 s，COMPLETE |
| 原鏡頭最後觀測 0.2 s、3.2 s 再現 | 3.2 s 當格新 segment 恢復；先前僅三次 RETURN；searching_index 保留 3 |
| 四次短暫失，每次門檻格接回 | 四次 TEMP_LOST，零 SEARCHING，index=0；COMPLETE |
| 同 run 兩個顯式 seed／限定時間 request | [2,4) s、[6,8) s 均 COMPLETE，session IDs 不同，各自 resolved range 與參數 pins 相符 |

既有 focused tests：`tests/q1q5/test_q5_controller.py -k 'disappearance_search_guard or below_guard_never_cuts or session_research_limit or manual_changes_cannot_refund or index_ticks_continue'`：**7 passed**。使用 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests/q1q5 uv run --no-project --offline --no-cache --python "$EXISTING_PYTHON" python -m pytest -q -p no:cacheprovider …`，只重用既有環境。LOCAL probe 的執行器／輸出為當次輔助證據，見 PR Actual output 的 SHA-256；不冒稱 repo 有新增測試。

未驗證：AGENT 真模型、正式產品／場景 run、v4 ROI、遮擋／renderer、人物身份、物理通行、G4、v2 評分器或任何使用者核定。

## 5. 來源 pins

| 檔案 | commit | bytes SHA-256 |
| --- | --- | --- |
| `src/amidst/q1q5/q5_controller.py` | `680ca357a31b664bed3feb6a5284dcd7c5c0d94d` | `7e42cfab8365520bd835f169c945f6eea71f1398e35fda264ddb6732fd312a2a` |
| `src/amidst/q1q5/linker.py` | 同上 | `92d0e70e7ea15e377bfc8a604bf56133b4bf75db68b180671799b56ddaf0a33b` |
| `src/amidst/q1q5/candidates.py` | 同上 | `dd1a36e6041bcd97f0fc8ab12b9d3d6b4e207362be4ca1971fec55b84768283f` |
| `src/amidst/q1q5/q4_evidence.py` | 同上 | `a3dbb0821e9b1861fbadafd02cb09071b08c83fb47a3bc1455fd8ecdf0470dee` |
| `docs/contracts/Q1_Q2_FIRST_DEMO_V1.md` | 同上 | `b700bf86041f4853ae37dd54bbc9d93199a07be3d5d3c87bc8c2f6455570df04` |
| `tests/q1q5/test_q5_controller.py` | 同上 | `9c16062e8ffcea6e100149a76645d1f84665ebb453b5eb4b0e35c2cbfd070aa4` |
| `docs/evaluation/Q5_SWITCH_EVAL_V2_DESIGN.md` | `0a87c3045923378f25c464e2bc43629612235233`（#258） | `3b7991cfe223d24f61340495cea8212e60a5fe0d6d753c2d290f7b31616b1ace` |

決策：[D73](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6395972547)、[D90](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423575212)。未讀 GT、renderer 軌跡／visibility／depth、原始 media 或 `.blend`。

## 實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: 由本文件所在 Draft PR 記錄精確 head；本稿為新提案，不代表核定。
- Files changed: 只新增 `docs/contracts/L2_LINKER_Q5_CONTRACT_PROPOSAL_20261027.md`。
- Commands run and results: 上述 7 個既有 focused cases PASS；LOCAL probe 五組 assertion PASS；文件 C1–C10 完整性／來源 pins 檢查 PASS；`git diff --check` 結果由提交者補於 PR。
- Artifacts: 本文件；LOCAL probe script／JSON output，精確 hashes 見 PR 實際產出，不公開私人 locator。
- Verified: staging 固定 SHA 的 phase、輪數、RETURN、回原探針、參數 pin、限定 seed、計數與終止輸出；SYNTHETIC 結果不代表偵測品質。
- Not verified: 上列場景／模型／G4／v2 評分；本次無產品改動、無渲染、無新推論、無合併。
- Deviations, UNKNOWN items and follow-ups: C5a 出口幾何交 E2／E3；C2 相位與 C6 LIMIT 尾端需 Claude 更新設計稿；所有 v2 評分選項保持 PROPOSED，等使用者核定。
