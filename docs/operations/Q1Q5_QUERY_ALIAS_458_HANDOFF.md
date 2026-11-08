# #458 中文檢索別名交接

此實作保留 80 個 canonical class label 與原 class map pin；中文名稱只用於顯示和輸入正規化。送出的手動 Q1/Q3 request 仍使用 canonical class label。區域選項來自所選 run 的 graph，前端提交原 `region_id`；舊 server 未提供 catalog 時顯示 `UNKNOWN` 並停用區域選項。

`q_bootstrap.runs[].region_catalog` 是 **PROPOSED additive contract**，不是 #410 已核准欄位。內容僅含 `scene_id`、`scene_revision`、`region_graph_sha256` 與 `regions[]` 的 `region_id`、受控 `label`；不含 geometry、coverage 或 GT。後端先驗證 graph 與 index 的 scene/revision 及 graph content pin；無 graph 時為 `null`。前端再核對 catalog 與所選 run 的 scene/revision/pin；不符合即明確錯誤，不猜測區域。

`configs/q1q5/query_alias_v1.json` 的 R101/R102 僅為明列別名。僅在所選 graph 含相應 canonical ID 時有效；不得依 ID 推測其他 revision 的中文名稱。此契約與顯示文字仍需獨立審閱，工程測試不構成正式驗收。
