# Baseline 單一整合來源（CX-4）

起點 staging a958dd4043ebcd5ef2d9fdb362d15f8c4ce3941f。指定 baseline Draft、必要先行 Q1/Q4/Q5/workbench/runtime 與本次 CX-1/2/3 修正，均以 merge commit 收進新分支；完整來源與 head 見 baseline_integration_sources.json。沒有修改共享 checkout/index，沒有合 staging/mainline/main，也沒有更新 #127 原分支。

原 delivery composition 的533個來源檔中，實作缺少的依賴也已納入歷史。衝突以固定 composition 的逐檔來源選版；API保留 d90f2faa 的原子發布修正。評分器與v3圖採本輪新審查修正，歷史錄製／影像仍 LOCAL。

## D73 / D78

- 後續 scoped runtime merge：NEXT 可引用已取得的精確 evidence/snapshot hash，SWITCH仍需強觀測；多run Q3澄清、Q1 UNKNOWN；reasons依固定優先序進hash，未知model digest維持null。
- D78中心平移僅在600ms內作匹配參照，真實框／來源refs與IoU分開記錄。matching_audit受 links raw hash 綁定；不補框、不延後GAP、不確認身分。
- SWITCH接受與entry完成分兩筆，cause_decision_id綁同一次選擇，完成筆不增加模型呼叫。USER stop以授權session+generation阻止晚到成功發布，provider_cancelled=null；UI暫停與停止分開。手動重啟Agent需明選，保留session累計。

## 驗證邊界

整合前既有API/controller/Agent等166 focused PASS；D73/D78指定focused與前端測試見本PR實際產出及D78工程收據。原#127 kit僅作固定比較，未修改；D73 reasons/null digest、D78 matching_audit/cause/control_reason需Claude owner對齊rc2，不能把舊schema檢查冒稱通過。正式G4／A4B4／正式分母不在本PR完成範圍。

P1一行啟動與組員portable包由CX-5/CX-10後續PR提供。CX-6由平行對話執行，不與它競爭Ollama。

## D85 stop / poll 與合併來源

- `q2_stop_session` 在 controller control lock 內取得 stop journal 及 controller 產生的 Q2 快照；`q2_poll_session` 的 API job 維持 `STOPPED`，內層 Q2 為 `PARTIAL` / `USER_STOPPED`，不再回 `response=null`。快照的 decisions / links hash 對應 stop 收據；重複 stop 回相同收據。generation / cancellation 仍拒絕晚到發布，停止的 job 不進已完成 response cache；`provider_cancelled=null` 不宣稱推論已取消。
- 本輪已核對的 staging base 為 `7b05211dfdf93b85aa14bc34d2cc85d5f8819f3e`。已以 merge commit `0c7af6461c5f07de90418f8d4bd1c66fd592c8fb` 納入整合分支（parents：`18529e2cc5a80979877e86d5ec286df0792b11c9`、上述 staging）；來源表 `base` 同步此值。首段 `a958dd4` 是歷史起點，來源 PR 的原 head / merge 收據保留。實際合併 #231 時若 staging 再前進，須先更新此 base 與 merge 收據。
- D85 focused 回歸覆蓋 provider 等待及發布前兩個 stop 時點：立即 poll 得到 controller Q2 快照，解除等待後快照、journal 及計數不被晚到結果覆寫。此驗證使用 synthetic fixtures，未執行真實推論、渲染、正式 G4 或組員 kit 驗收。

### 正式 G4 前待辦（未完成）

- N2：驗證可信 G4 收據的核准者、來源及綁定，不能僅因載入者可改寫的 `status` / `G4_approved` 欄位就視為正式使用者核准。此項仍待實作及 Claude 獨立複核，正式 G4 前必須完成。
- N3：無 scope pin 的舊 graph 必須依契約 §5.4 回 `UNKNOWN`（`TRACKING_SCOPE_MISSING`），不能回退成全部追蹤鏡頭。舊格式 loader 相容路徑仍待修正及獨立複核，正式 G4 前必須完成。
- N5 其餘低優先項：repo q-demo JSON schema 與 `q1q5_conformance.py` 的 `agent-decision.v2` / `link-record.v2` 對齊仍待 consumer / kit owner 後續處理；本輪只修 Ruff I001，不以舊 schema 的結果宣稱 v2 conformance。
- #212、#214、#216 僅於 #231 經複核且實際合併後，留言指向整合 PR / merge SHA 再關閉；分支保留。本輪不自合、不提前關閉。
