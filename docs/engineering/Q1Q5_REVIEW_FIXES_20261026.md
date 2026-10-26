# #231 重審修正：D73／D78／D81／D82

本輪針對 [#93 指派](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6407462030) 修正產品與交接，整合基底以 merge commit 更新至 staging `63ce04df035fe2f5b02481da9757277f66ae5db6`。不合併 staging/mainline/main，舊 PR 等 #231 核准合併後才收尾。

- `link.iou` 固定為真實 prev/next IoU；位移參照的 IoU 在 `matching_audit.reference_iou`，REACQUIRED 在 audit.event。外推只供匹配，無觀測仍 GAP；D65 數值不變。
- D82 stop 回 `PARTIAL`／`USER_STOPPED`，API job 仍 `STOPPED`。排程回來立即再次檢查 cancellation，阻止停止後同一輪多寫觀測。
- Q2 在執行前收集 clock／參數核准／grid／exit 的全部可判定阻擋，依固定順序輸出，重複執行 hash 一致。
- `agent-decision.v2`：NEXT 只有 evidence 沒有可引用真實觀測時，才能只引用該 evidence_sha256；有觀測就必須引觀測，不接受 snapshot hash。缺／錯 evidence hash 不提供 SWITCH／NEXT，也不拋 KeyError；workflow.blocked_reason 與工具拒碼記錄缺項。
- D81 loader 顯式讀取 `tracking_scope_ref` 的 allowlisted 文件，驗 byte pin、相機分割及完整轉移矩陣；scope wire 為 sorted compact ASCII JSON 加一個 LF。Q2 使用 index 相機∩tracking 相機；query-only 不能作 seed／候選。缺必要 scope 或 query-only seed 回 UNKNOWN；明確帶 scope 的圖若未核 G4 或仍為 DRAFT，controller 回 UNKNOWN／GRAPH_NOT_APPROVED、空 timeline／零模型呼叫，22條轉移（含兩條零邊）皆無合法候選；舊無 scope input pin 的工程圖仍向後相容。
- 候選未收到明確 allowed_camera_ids 時 fail closed；不再默認全圖。公開文件改為可設定 locator，保留原 LOCAL 原始證據；#127 保持取用時歷史 pin、#219 來源列去重。

## 契約介面交接

契約檔已釋出給平行對話單一 owner；本輪不編契約、不宣稱定版。實作的 Q2 阻擋全序為：CLOCK_MAPPING_MISSING、TRACKING_SCOPE_MISSING、SEED_CAMERA_NOT_TRACKED、PARAMETERS_NOT_APPROVED、PARAMETER_GRID_MISMATCH、EXIT_ZONES_MISSING，之後才 TIME_SCOPE_PARTIAL、GRAPH_NOT_APPROVED。其他執行原因以穩定字典序優先；USER_STOPPED 保留主原因。契約 owner 尚須確認全序及 v2／audit／scope／D82 原因碼一致，見 [介面交接](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6414830920)。

## 實際產出 / Actual output

- Model / effort: GPT-6 / UNKNOWN。
- PR / commits: #231（本輪窄 feature 以 merge parent 整合）；圖 #235，D80 #236。來源精確 heads 見 `configs/q1q5/baseline_integration_sources.json` 與提交記錄。
- Files changed: linker/controller/candidates/graphs/AgentTools/guidance/API、schema v2 prompt、portable README、限定測試、來源表與去識別化文件；逐檔見 diff。
- Commands run and results: 原審查指定集合加 C1/P1/portable／D80／圖共469 focused PASS；Node 指定6檔69 PASS；Q5 evaluator 原44 PASS。原先缺 evidence_sha256 的失敗項已補 fixture 與 fail-closed 負例並通過。Ruff F/I/UP/B 與 git diff --check PASS。
- Artifacts: 原始 RGB／索引／模型與舊錄製 LOCAL、不覆寫。新錄製及可攜包另固定來源 commit 與收據後交付，舊 C26 驗收包保留原 pins。
- Verified: 真框/參照 IoU 分開、多阻擋全列且決定性、scope 交集與 query-only 拒錯、stop 不附加觀測、schema v2 引用守衛、來源表去重、公開定位不洩私人根路徑。
- Not verified: 契約 owner 最終對齊、Claude 複核、AC7 全符合性、G4、正式 A4/B4／索引／baseline 與人工正確性。誤接回率仍 null；不把 timeout fallback 算 LLM 成功。
- Deviations, UNKNOWN items and follow-ups: G4 依 D81 等 yyin 三題澄清併入圖複核，正式 metadata 仍缺；未渲染。canonical checkout/index/516 dirty 檔保持，不建 worktree。舊 PR 尚未關閉，符合最新合併後收尾要求。
