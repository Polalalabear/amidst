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
