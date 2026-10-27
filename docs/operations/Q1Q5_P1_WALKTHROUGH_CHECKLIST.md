# Q1–Q5 P1 工程預驗收走查清單（AC1–AC8）

- 日期：2026-10-25（Claude 撰寫，驗收計畫 CL-4 的準備）
- 依據：[驗收計畫](../agents/Q1Q5_BASELINE_ACCEPTANCE_PLAN.md) §1 AC1–AC8、§2 P1；[本機測試設定](Q1Q5_LOCAL_TEST_SETUP.md)；決定 D71（審核／Demo 模式）、D73（含 X2）、D76（兩階段驗收）、D78（同鏡頭重取得、SWITCHING、stop）（均在[任務板 #93](https://github.com/Polalalabear/amidst/issues/93)）。
- 狀態：**清單已備好，尚未走查。** 等 Codex 的 CX-5 預驗收版交付後，由 Claude 照本表逐步操作並截圖；「實際結果」欄與前置條件的空欄位在走查時才填。
- 場景：Codex 的工程動態場景（[#211](https://github.com/Polalalabear/amidst/pull/211)：8 秒、20 fps、A／B 雙鏡頭、真 RT-DETR 索引）。

## 0. 這份清單的定位

1. **P1 不是正式成績（D76）。** 場景是 Codex 的替代工程場景，不是 r004 A4／B4 正式事件；結果只用來早點找出操作流程與畫面跟隨的問題，不進正式分母，不能拿來宣稱 baseline 正確率。正式驗收是 P2（CX-8、CL-5、CL-6 之後）。
2. 判定只看畫面與紀錄是否照實：不判斷「追得對不對」（無獨立標準答案，誤接回次數維持 null），不判斷身分或物理可行性。
3. 下列「建議查詢句」與「預期畫面」是**建議／推定**，實際以 CX-5 場景內容與 Codex 的操作說明為準；與實際不符時，在「實際結果」寫明差異，不要硬套。
4. 判定用語：**PASS**＝預期畫面與判定條件全部成立；**FAIL**＝可觀察到與條件相反的事實；**UNKNOWN**＝無法取得觀察（例如畫面沒有提供欄位、無法操作）。UNKNOWN 不算 PASS，要在實際輸出的「Not verified」列出。

## 1. 前置條件（走查前填寫）

### 1.1 版本

| 項目 | PR | head SHA | 備註 |
| --- | --- | --- | --- |
| CX-4 baseline 整合分支（`codex/q1q5-baseline-integration`） |  |  |  |
| CX-5 P1 預驗收版 |  |  |  |
| 走查所用的 Codex 操作說明（commit 於 GitHub 的路徑） |  |  | 依 AGENTS.md「Handoff documents go on GitHub」，說明未上 GitHub 即不算完成，退回 NEEDS_CHANGES |
| 場景來源（#211 head `16bdba88…`；若 CX-5 有新版以新版為準） |  |  |  |

### 1.2 啟動指令與位址（待 CX-5 說明填入）

| 項目 | 內容 |
| --- | --- |
| 一行啟動指令（AC1） |  |
| recorded replay 啟動指令（AC1、AC7） |  |
| 工作台網址（一般／`?mode=review`） |  |
| 埠號（不得動使用者正在跑的 63408） |  |
| 啟動所需的 LOCAL 檔案路徑（相對 `$AMIDST_ARTIFACTS`）與 SHA-256 |  |

### 1.3 環境紀錄

| 項目 | 內容 |
| --- | --- |
| 日期時間 |  |
| 機器（型號、macOS 版本） |  |
| 瀏覽器與版本、視窗大小 |  |
| `df -h /`（走查前） |  |
| `df -h /`（走查後） |  |
| 可用空間低於 8 GiB 即停止；Ollama／Qwen 是否在跑 |  |

截圖存放位置：LOCAL `$AMIDST_ARTIFACTS/p1-walkthrough-<日期>/`，檔名格式 `P1-AC<編號>-<步驟>_<描述>.png`。截圖不提交 GitHub；PR／issue 只列檔名與 SHA-256。

## 2. AC1：一行指令啟動，另有 recorded replay

| 步驟 | 操作步驟 | 預期畫面 | 判定方式 | 截圖檔名 | 實際結果 |
| --- | --- | --- | --- | --- | --- |
| 1.1 | 只照 CX-5 的操作說明，不另外查文件，在乾淨 shell 執行 §1.2 的一行啟動指令 | 終端機顯示服務啟動；沒有要求手動設定環境變數、改檔 | PASS：一行指令成功且不需另查文件。FAIL：需要說明以外的步驟，或 SHA-256 核對失敗拒啟動（記錄原因，這是保護機制，不要繞過）。UNKNOWN：說明缺漏無法執行 | `P1-AC1-1.1_launch.png` |  |
| 1.2 | 瀏覽器開啟 §1.2 的工作台網址 | 工作台載入；畫面有鏡頭影像、時間軸、查找輸入；console 無錯誤 | PASS：頁面可操作且 console 無 error。FAIL：空白、缺圖、error | `P1-AC1-1.2_home.png` |  |
| 1.3 | 停止服務，改用 recorded replay 指令啟動（確認未啟動 Ollama／Qwen，或網路／socket 被禁） | 工作台可載入並重播同一 session；不連模型 | PASS：不連模型即可重播，且畫面標示為重播／錄製來源。FAIL：重播需要模型，或看不出是重播。UNKNOWN：無法確認是否連模型 | `P1-AC1-1.3_replay.png` |  |
| 1.4 | 記錄兩種模式的啟動耗時與終端機輸出（回執路徑） | 回執／receipt 檔存在 | PASS：路徑與 SHA-256 已記入 §1.2。UNKNOWN：未產生回執 | `P1-AC1-1.4_receipt.png` |  |

## 3. AC2：選取目標（至少 3 句不同的中文查詢）

**查詢句（句 1–3 與 P1 測試套件逐字一致）**，場景為 A、B 兩台鏡頭、13:00:00–13:00:08、畫面有人：

1. 哪些鏡頭拍到人13:00:00到13:00:08
2. 哪些鏡頭拍到車13:00:00到13:00:08
3. 哪些鏡頭拍到紅衣人13:00:00到13:00:08
4. （補充，非套件句）哪些鏡頭在13:00:02到13:00:06看得到人
5. （補充，非套件句；無結果對照）13:00:20到13:00:30有沒有人——預期不得假造結果，應顯示無結果或要求澄清

來源：句 1–3 取自 `docs/operations/Q1Q5_P1_START.md` 第 13 行與 `src/amidst/q1q5/portable_pack.py` 第 76 行（P1 測試包 README 文字），commit `dae300ac22cfee3ffafda3ab0f005dfe9eb659c9`（PR #234／CX-10，`codex/q1q5-portable-p1-package`）；`docs/engineering/P1_ENGINEERING_ACCEPTANCE_20261026.md` 記錄工程側結果：句 1 READY 2 台、句 2 NO_MATCH 0 台、句 3 READY 2 台。句 4、5 不在套件文件內（`UNKNOWN`：套件是否支援），僅作補充對照。

| 步驟 | 操作步驟 | 預期畫面 | 判定方式 | 截圖檔名 | 實際結果 |
| --- | --- | --- | --- | --- | --- |
| 2.1 | 在查找輸入框輸入句 1，送出 | Q1 結果牆列出符合的鏡頭與時段；每筆含鏡頭名稱、時段、縮圖 | PASS：結果列出的鏡頭與時段與句中條件一致。FAIL：結果與條件不符，或畫面無結果卻不說明 | `P1-AC2-2.1_query1.png` |  |
| 2.2 | 輸入句 2（車） | 結果牆只含句中指定的鏡頭與時段 | 同 2.1；工程側預期 NO_MATCH 0 台：PASS 為照實顯示零結果且不造假；另需結果與句 1 不同 | `P1-AC2-2.2_query2.png` |  |
| 2.3 | 輸入句 3（紅衣人） | 同上 | 同 2.1；工程側預期 READY 2 台（顏色多為 WEAK，不得當身分） | `P1-AC2-2.3_query3.png` |  |
| 2.4 | 輸入句 4（補充；及句 5 作對照） | 句 4 有結果；句 5 無結果／要求澄清 | PASS：句 5 沒有造出不存在的片段，且沒有宣稱「確定沒有人」（見 AC8）。FAIL：句 5 有結果或寫「確定不在」 | `P1-AC2-2.4_query45.png` |  |
| 2.5 | 審核模式下（`?mode=review`）對任一句查看解析結果 | 顯示 Q3 解析來源（規則或 LLM）與解析後條件 | PASS：解析來源與條件可看見且與句子一致。UNKNOWN：Demo 模式下不顯示（這是預期，不算 FAIL） | `P1-AC2-2.5_parse.png` |  |
| 2.6 | 點結果牆中的一筆結果 | 該筆被選為目標，畫面進入 AC3 的檢視 | PASS：選取後目標資訊（鏡頭、時段）與被點的那筆一致 | `P1-AC2-2.6_pick_result.png` |  |
| 2.7 | 回結果牆，改直接點畫面上的偵測框 | 該框被選為目標，目標框突顯 | PASS：選取的是被點的框（不是別的框）；選取後與 2.6 一樣進入跟隨。FAIL：點框無反應或選到別人 | `P1-AC2-2.7_pick_box.png` |  |
| 2.8 | 手動改選目標（從 2.6 改選另一筆／另一框） | 目標切換；若 Agent 曾被規則接手，**不自動重啟 Agent**，由使用者在前端決定是否重啟（D73 X2） | PASS：改選後畫面詢問／提供「是否重啟 Agent」選項，且未自動重啟。FAIL：自動重啟或無法改選。UNKNOWN：本場景未發生 Agent 接手 | `P1-AC2-2.8_reselect.png` |  |

## 4. AC3：查看目標（目標框、鏡頭名稱、來源時間一致）

| 步驟 | 操作步驟 | 預期畫面 | 判定方式 | 截圖檔名 | 實際結果 |
| --- | --- | --- | --- | --- | --- |
| 3.1 | 從 AC2 選取一筆結果後，觀察主畫面 | 主畫面跳到該鏡頭與該時刻，目標框疊在人物上，時間軸標出時段 | PASS：**目標框、鏡頭名稱、來源時間三者一致**——目標框確實套在選取的人物上；鏡頭名稱與結果牆那筆相同；顯示的來源時間落在該筆時段內。FAIL：三者任一不一致（例如框在別人身上、鏡頭名稱與結果不同、時間超出時段） | `P1-AC3-3.1_focus.png` |  |
| 3.2 | 拖動時間軸到時段內外各一點 | 時間軸游標與來源時間同步；時段外不再標示目標 | PASS：時間顯示與畫面內容同步，時段外不顯示目標框（或標示為缺格）。FAIL：時段外仍畫框 | `P1-AC3-3.2_scrub.png` |  |
| 3.3 | 對 A、B 兩台鏡頭各做一次 3.1 | 兩台都滿足一致性 | PASS：兩台都 PASS | `P1-AC3-3.3_AB.png` |  |
| 3.4 | 逐項核對框的來源（審核模式） | 框旁可看到偵測來源（RT-DETR 索引的 observation）與來源時鐘 | PASS：框對應真實 observation，有來源 hash／時間。FAIL：框沒有來源或標示為預測卻被當作觀測 | `P1-AC3-3.4_source.png` |  |

## 5. AC4：跟隨切鏡（至少 1 次成功切鏡、1 次找不到）

| 步驟 | 操作步驟 | 預期畫面 | 判定方式 | 截圖檔名 | 實際結果 |
| --- | --- | --- | --- | --- | --- |
| 4.1 | 選取 A 鏡頭的目標，開始播放；同鏡頭內持續觀察 | 同鏡頭內目標框持續跟著人物（Q2） | PASS：連續多格框都在同一個人上。FAIL：框跳到別人或遺失而無標示。記錄遺失時刻 | `P1-AC4-4.1_same_cam.png` |  |
| 4.2 | 播放至目標離開 A 鏡頭畫面，**單畫面模式**下觀察 | 自動硬切到 Q5 判定的下一台鏡頭（B），出現切換指示 | PASS（成功切鏡）：切換後 B 鏡頭有目標框；鏡頭名稱與來源時間更新且一致；審核模式可看到這次切鏡的決策來源與證據。FAIL：沒切卻宣稱切了，或切到的鏡頭沒有目標框 | `P1-AC4-4.2_switch_before.png`、`P1-AC4-4.2_switch_after.png` |  |
| 4.3 | **多鏡頭模式**重做 4.1–4.2 | 同時顯示多台；目標離開後標出下一台（不硬切） | PASS：下一台被標出且與單畫面模式結論一致。UNKNOWN：本場景無多鏡頭模式 | `P1-AC4-4.3_multi.png` |  |
| 4.4 | 製造「找不到」：選取在 B 鏡頭中離開的目標（或場景中預期找不到下一台的片段，依 CX-5 說明），播放過離開時刻 | 顯示「搜尋中」，之後若仍找不到顯示「回原鏡頭」（或 RETURNED_TO_ORIGIN／TEMP_LOST 的對應字樣） | PASS（找不到）：**必須出現「搜尋中」或「回原鏡頭」**，且不假裝找到（沒有憑空畫出目標框）。FAIL：找不到卻畫框、或無任何提示。UNKNOWN：場景中沒有可重現的找不到情況（要在報告寫明） | `P1-AC4-4.4_notfound.png` |  |
| 4.5 | **D78 檢查 1：同鏡頭 600 ms 內重取得。** 在同一鏡頭內目標短暫消失（<600 ms）後再出現的時段（#218 的情境，依 CX-5 說明找位置） | 目標立即顯示 TEMP_LOST／GAP；600 ms 內重新出現時接回，顯示 REACQUIRED 與來源 | PASS：接回後畫的框**只引用真實觀測**（審核模式可查到真實 observation 與方法／參照）；沒有觀測的時刻仍標 TEMP_LOST／GAP／UNKNOWN，預測不被當成觀測；超過 600 ms 不復活舊 local segment；身分仍 UNCONFIRMED。FAIL：把平移預測畫成觀測、或超時外推。UNKNOWN：CX-5 版本未實作 D78（#219 為 Draft，需確認） | `P1-AC4-4.5_reacquire.png` |  |
| 4.6 | **D78 檢查 2：SWITCHING 兩段紀錄。** 切鏡發生時，在審核模式／journal 查看 | journal 先記 SEARCHING→SWITCHING，再記 SWITCHING→PLAYING，兩筆屬於同一 decision／snapshot／entry | PASS：兩段都存在，同一 decision／snapshot，時間不倒退。FAIL：只有一段、decision 不同、時間倒退。UNKNOWN：UI 不顯示 journal（記錄查看方式） | `P1-AC4-4.6_switching_journal.png` |  |
| 4.7 | **D78 檢查 3：stop／取消。** 切鏡搜尋進行中按 stop（或取消），再觀察是否有晚到的模型結果 | stop 後不再發布結果；晚到的模型結果被拒；既有 journal 與計數保留 | PASS：stop 後晚到結果不更新畫面、不產生重複發布，審核模式可看到拒絕紀錄。FAIL：晚到結果仍切鏡／發布。UNKNOWN：模型端是否真的停止運算無證據（D78 規定保持 UNKNOWN）；**單純 UI 暫停不算後端 stop** | `P1-AC4-4.7_stop.png` |  |

## 6. AC5：模式（RULE_ONLY、AGENT_SEQUENTIAL、Qwen 逾時兜底）

| 步驟 | 操作步驟 | 預期畫面 | 判定方式 | 截圖檔名 | 實際結果 |
| --- | --- | --- | --- | --- | --- |
| 5.1 | 開啟工作台，不動設定，查看模式顯示 | 預設 `RULE_ONLY` | PASS：預設為 RULE_ONLY | `P1-AC5-5.1_default.png` |  |
| 5.2 | 在 RULE_ONLY 下完整跑 AC4 的切鏡情境一次 | 全程由規則決策；審核模式「這一步的來源」為規則 | PASS：每一步來源標示為規則，沒有 LLM 採用。FAIL：RULE_ONLY 卻出現 LLM 來源 | `P1-AC5-5.2_rule_only.png` |  |
| 5.3 | 切換到 `AGENT_SEQUENTIAL` 並重跑同一情境 | 模式顯示為 AGENT_SEQUENTIAL；每一步的來源分開顯示 | PASS：UI 分開顯示「模式」與「這一步的來源」（D73 §14-21）。FAIL：兩者混為一個欄位。UNKNOWN：本機未啟動 Qwen／Ollama 無法選擇 | `P1-AC5-5.3_agent.png` |  |
| 5.4 | 在 AGENT_SEQUENTIAL 下觀察 Qwen 逾時（#211 紀錄顯示 Qwen 全部逾時、LLM_used=0；依實際為準） | 顯示逾時，並顯示由兜底（規則）接手，直到 session 結束 | PASS：畫面與審核模式明示 Agent 故障原因（逾時）與「兜底接手」；接手後該 session 不再自動重啟 Agent；模式仍可分辨為 AGENT_SEQUENTIAL，來源為規則（D71、D73）。FAIL：逾時卻顯示成 LLM 成功，或無任何提示。UNKNOWN：本次 Qwen 沒有逾時（要在報告寫明） | `P1-AC5-5.4_fallback.png` |  |
| 5.5 | 兜底接手後，手動改選目標或模式 | 由使用者在前端決定是否重啟 Agent（D73 X2） | PASS：不自動重啟，提供選項。FAIL：自動重啟 | `P1-AC5-5.5_restart_choice.png` |  |
| 5.6 | 兩種模式各完成一次完整 session，記錄切鏡次數與 `agent_used` 數 | 兩模式各有一份完整結果 | PASS：兩模式各跑完一次。若 Agent 全選 NEXT 後回原鏡頭，記為 RULE_ONLY，但已接受的 NEXT 仍算 `agent_used`（D73 §14-21） | `P1-AC5-5.6_both.png` |  |

## 7. AC6：審核模式與 Demo 模式

| 步驟 | 操作步驟 | 預期畫面 | 判定方式 | 截圖檔名 | 實際結果 |
| --- | --- | --- | --- | --- | --- |
| 6.1 | 在 Demo 模式（不加參數）跑到一次切鏡，截圖 | 只看到系統依追蹤物切換畫面；**不顯示內部判斷**（決策來源、候選分數、fallback 原因） | PASS：畫面沒有內部判斷文字／欄位。FAIL：Demo 模式出現候選、證據 hash、fallback 原因 | `P1-AC6-6.1_demo.png` |  |
| 6.2 | 網址加 `?mode=review`，跑同一次切鏡，在相同時刻截圖 | 顯示每一步的決策來源、候選、證據與 fallback 原因 | PASS：四項（決策來源、候選、證據、fallback 原因，若有發生）都能看到。FAIL：缺任一項。UNKNOWN：某項在本次情境中沒有發生（例如沒有 fallback），註明 | `P1-AC6-6.2_review.png` |  |
| 6.3 | 並排比對 6.1 與 6.2 | 兩者的目標框、鏡頭、來源時間一致，差別只在是否顯示內部判斷 | PASS：主畫面行為一致。FAIL：兩種模式的主畫面行為不同 | `P1-AC6-6.3_compare.png` |  |
| 6.4 | 在 Demo 模式嘗試以 URL 之外的方式開啟內部判斷（例如點畫面元件） | 沒有隱藏入口洩漏內部判斷 | PASS：無入口。FAIL：有 | `P1-AC6-6.4_no_leak.png` |  |

## 8. AC7：可重現（同一 session 的 recorded replay hash 相同；#127 測試包）

| 步驟 | 操作步驟 | 預期畫面／輸出 | 判定方式 | 截圖檔名 | 實際結果 |
| --- | --- | --- | --- | --- | --- |
| 7.1 | 記錄原始錄製檔的 SHA-256、錄製所屬 session／run／clock 識別（`recordings.json` 與錄製檔） | 錄製 hash 已記錄 | PASS：hash 與 CX-5 凍結收據相符。FAIL：不符 | `P1-AC7-7.1_recording_hash.png` |  |
| 7.2 | 用 recorded replay 重播同一 session 兩次，各記錄輸出檔的 SHA-256：`decisions`、`links`（JSONL 原始 bytes，D73 §14-17）、timeline／events、output hash | 兩次輸出 hash | PASS：**兩次所有輸出 hash 相同**。FAIL：任一不同。允許不同者只限牆鐘耗時（`stats`／diagnostics，D73 §14-17），要逐項列出並說明 | `P1-AC7-7.2_hash_compare.png` |  |
| 7.3 | 將重播輸出 hash 與 CX-5 收據／錄製時輸出比對 | 與錄製時一致 | PASS：一致。FAIL：不一致。UNKNOWN：收據沒有提供 | `P1-AC7-7.3_vs_receipt.png` |  |
| 7.4 | 執行 [#127](https://github.com/Polalalabear/amidst/pull/127) 測試包對該 session 的輸出 | 全部通過 | PASS：0 FAIL，不適用項目寫明原因。FAIL：任何 FAIL（#211 已記錄原 kit 對 8 份新輸出有 FAIL，#145 仍 FAIL；不得把 kit 的 FAIL 與產品問題混為一談，兩者分開記）。UNKNOWN：#127 尚未合併或未對齊最終契約 | `P1-AC7-7.4_kit.png` |  |

**#127 測試包執行方式（待填）：**

| 項目 | 內容 |
| --- | --- |
| 測試包 PR／head SHA |  |
| 綁定的契約 SHA（#145 / CL-1） |  |
| 執行指令 |  |
| 輸入（輸出檔路徑、相對 `$AMIDST_ARTIFACTS`） |  |
| 結果（PASS／FAIL／N/A 計數與報告 SHA-256） |  |

## 9. AC8：誠實標示（MISSING／UNKNOWN，不宣稱身分已確認）

| 步驟 | 操作步驟 | 預期畫面 | 判定方式 | 截圖檔名 | 實際結果 |
| --- | --- | --- | --- | --- | --- |
| 8.1 | 把時間軸拖到缺圖／缺格處（#211 中 B 約 5.6 秒起缺圖的測試，依 CX-5 說明） | 明示 MISSING；沒有影像時不出現影像與目標框 | PASS：顯示 MISSING，目標框不出現（img 0 / OBS 0）；拖回可恢復播放。FAIL：靜默顯示舊圖或畫框 | `P1-AC8-8.1_missing.png` |  |
| 8.2 | 觀察沒有觀測的時段（目標不在任何鏡頭） | 顯示 TEMP_LOST／GAP／UNKNOWN 或「搜尋中」 | PASS：用中立字樣，不寫「確定離開」「確定不在」。FAIL：寫成確定 | `P1-AC8-8.2_unknown.png` |  |
| 8.3 | 觀察 4.4 的找不到畫面與 2.4 的句 5 無結果畫面 | 「沒偵測到人」不被寫成「確定不在」（D73 §14-26） | PASS：用語為未偵測／UNKNOWN。FAIL：宣稱確定 | `P1-AC8-8.3_notfound_wording.png` |  |
| 8.4 | 全程檢查所有文字（含審核模式）是否出現「同一個人」「已確認身分」等字樣 | 身分標示為 UNCONFIRMED／未確認；跨鏡頭接續是「候選／推論」 | PASS：沒有任何宣稱身分已確認的文字。FAIL：出現。切鏡後的目標只能稱為跟隨的候選 | `P1-AC8-8.4_identity.png` |  |
| 8.5 | 檢查推論與觀測的區分（審核模式） | 觀測、預測／推論、MISSING、UNKNOWN 在視覺上可分辨 | PASS：四者可分辨。FAIL：混在一起，尤其預測畫得像觀測 | `P1-AC8-8.5_distinguish.png` |  |

## 10. 已知風險與預期的非 PASS

| 項目 | 說明 | 走查時的處理 |
| --- | --- | --- |
| [#218](https://github.com/Polalalabear/amidst/issues/218) 同鏡頭暫失後接不回 | Q2／Q5 在同鏡頭短暫遺失後可能接不回；D78 已核定修法（600 ms 內平移參照、只引用真實觀測），[#219](https://github.com/Polalalabear/amidst/pull/219) 是 Draft，CX-5 是否包含 UNKNOWN | 4.5 看到接不回時，記為「已知風險 #218」，不當作新缺陷；若 CX-5 已含 D78 而仍接不回，才記 FAIL |
| Qwen 逾時 | #211 記錄 Qwen 全部逾時、LLM_used=0；D73 維持 D65 預算 | 5.4 預期看到兜底接手，不算缺陷 |
| #127 測試包對新輸出有 FAIL | #145 仍 FAIL；原因含契約尚待 #144 | 7.4 分開記錄 kit 與產品 |
| `shell.test.mjs` 4 項舊測試失敗 | #211 已揭露（舊 HTML／stub 期待不相容） | 非走查範圍，僅在報告備註 |
| 場景不是 r004 | 替代工程場景，無正確率意義 | 結果不得寫成正式成績 |

## 11. 走查結果怎麼回報

1. **回報位置：**
   - 貼在 CX-5 的 issue／PR 上（編號待 CX-5 交付時填：______），並同步貼在[任務板 #93](https://github.com/Polalalabear/amidst/issues/93) 的 P1 驗收留言；
   - 填完的清單（實際結果欄）以新 PR 提交到 `docs/operations/` 底下，檔名 `Q1Q5_P1_WALKTHROUGH_REPORT_<日期>.md`（截圖維持 LOCAL，只列檔名與 SHA-256）。
2. **格式：**用 [AGENTS.md](../../AGENTS.md) 的「實際產出 / Actual output」範本：
   - `Model / effort`：走查時實際使用的模型與強度；
   - `PR / commits`：CX-4、CX-5 的 PR 與 head SHA（§1.1）；
   - `Commands run and results`：啟動指令、replay 指令、#127 指令；各 AC 的 PASS／FAIL／UNKNOWN 計數（共 AC1–AC8，逐步驟統計）；
   - `Artifacts`：截圖目錄（LOCAL）、錄製與輸出的 SHA-256；
   - `Verified`／`Not verified`：所有 UNKNOWN 步驟與原因；
   - `Deviations, UNKNOWN items and follow-ups`：新發現的缺陷各開 issue；#218 相關另註。
3. **結論用語：**「P1 走查完成，N 項 PASS／M 項 FAIL／K 項 UNKNOWN，交使用者試用」。不得寫「baseline 通過」或任何正確率。最終的 P1 驗收由使用者決定。
4. **失敗處理：**FAIL 的步驟附截圖與重現步驟，由協調者判斷歸 Codex（Blender、估計器、後端、Agent）或 Claude（前端）；同一點失敗兩次升級給協調者。
