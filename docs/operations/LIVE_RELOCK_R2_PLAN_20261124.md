# #589 R2 bounded blocker audit — 2026-11-24

狀態：Codex 已完成，待 Claude 審查（A4阻擋審核／計畫）；**#589實作仍blocked**。
本文件在 `codex/feat-live-agent`／Draft #703，沒有本輪R2 runtime修改。
依使用者限制，不改server.py／scheduler.py來做R2，不執行新量測／實際adaptive重播。

## 已解除的歷史前置

GitHub本次唯讀核對：#559已合併 `894bdd9e90fba3210ae62c133110dd65b357e553`；
R1 #608已合併 `cfbfe4e959cbc2abf0db5211026393b18786a40b`，#588 CLOSED。
因此「仍等#588程式合併」已過時。#617也已合併，錄製重播不是目前缺少的程式。

## 現在擋住的項目

1. #93目前仍寫「等relock門檻量測；11-25之後」；#588最後紀錄把R-5a／R-5b契約文字移deferred（D358）。
   `RelockConfig.t_short_s`／`v_walk_m_s`／`tau_app`／`margin_app`的runtime預設都是None，predict=false；
   `State._new_tracker`沒有傳relock設定，實際仍走舊rule gate。
   #690加的gate／reject／cand_id診斷不等於啟用R1。
2. R1報告的runtime appearance scale維持1.0，門檻UNKNOWN；離線GT-derived scale不得帶入runtime。
   早期固定樣本N=7、少於§4.2所需10，是歷史門檻不足證據，本次沒有重新量測。
   #589沒有一份已核定、來源綁定的runtime設定與可採用的門檻／UNKNOWN回退決定。
3. R2仍需server把state／lost_phase／unseen_s／confirm_candidates／REACQUIRE.detail帶入tracking，
   並讓confirm handle綁定HTTP session／epoch。R1內部r<tick>.<rank>不是#690的簽章selection cand_id，不能直接互換。
4. R-4／R-6的adaptive ENTRY整合驗收尚未完成；#574／#566也仍OPEN／blocked。
   原D273 BASELINE_TRACKER_NO_RELOCK的null不是R2通過；不能因候選被排程就宣稱已接回。
5. 本輪E5來源SHA凍結：R2需碰server.py，因此實作／合併待E5閘門及另行排程授權；不動scheduler.py。

## 解除條件（交Claude協調，未擅自去掉blocked）

- Claude／使用者確認本輪R2可開工、#93排程與E5閘門已解除，將#589標ready。
- 提供或核定source／hash綁定的runtime relock設定：量測值依契約§4，或**明確核准§4.5的UNKNOWN回退**。
  契約允許t_short UNKNOWN→原短gate行為、v_walk UNKNOWN→暫用8m、tau_app UNKNOWN→NEEDS_CONFIRM，
  所以不必捏造門檻或把「所有數字量出」冒充唯一解法；需把哪個fallback啟用寫清楚。
- R-5a／R-5b的驗收規則由Claude依D326／D358確認，不自行把「相對main新增錯接0」改回不同門檻。
- 固定R-4／R-6來源、capture clock、camera catalog／graph SHA、runtime commit及focused指令後再執行。

## 後續實作計畫（本次未做）

1. 在已合併#690的runtime基底，給State新增明確且預設關閉的relock設定接線，
   保留失聯／ACQUIRE／SWITCH既有語意，不重排或放寬scheduler。
2. 將R1輸出欄位原樣送tracking；NEEDS_CONFIRM候選另做session／epoch／tick freshness綁定，
   不把#690失聯診斷handle當confirm授權，不新增未核准HTTP端點。
3. 先做合成focused endpoint／relock tests：預設off不變、UNKNOWN走待確認、唯一短gate、
   同色多群、stale／跨session拒絕、confirm優先；再在授權後做adaptive ENTRY。
4. R-4分別列「正確候選首次呈現」與「正確自動接回」capture延遲，null保持null；
   R-6固定RGB A4≥67/95、B4≥58/60，失聯界限依原契約，protocol violations=0。
   若排程漏掉候選另開issue，不在R2改scheduler.py；結果回貼#552／#589／#674。

## 本次可先交的部分

依#589既有留言，在 `docs/evaluation/live_detection_20261118/d273_validation.json`
只加 `accepted_by: D282`。解析前後除這個新欄位外完全相等；不改任何量測值、
`overall: NOT_PASSED`、ENTRY censored或pass:null。此註記記錄既有裁決來源，不代表R2驗收通過。

本次驗證：GitHub合併狀態／#93列、契約§4／§5／R-4／R-6與當前factory只讀核對；
JSON僅新增欄位的一致性assert、git diff --check PASS。純文件／註記，未執行程式測試。
Artifacts：NONE。未讀取大型媒體、未改原始資產、未做量測／重播／付費／部署。
