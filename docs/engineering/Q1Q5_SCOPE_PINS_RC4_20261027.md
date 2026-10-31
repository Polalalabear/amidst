# rc4 tracking scope 生產端修正（2026-10-27）

回覆 #127 rc4 與本次派工B1。Q1／Q3 的 `resolved_scope` 現在固定包含 `tracking_scope_sha256`（沒有使用tracking scope時為null），hash由完整新回應計算，不補寫舊錄製。production registry一律要求Q2 scope；缺scope時回UNKNOWN／TRACKING_SCOPE_MISSING，seed候選、timeline、journal皆空，Agent不呼叫。scope內容／原始bytes／兩圖inputs的pin不符仍是integrity error，不降成可執行資料。

`from_environment`原本已能讀`tracking_scope_ref`及驗原始bytes，這次補上legacy registry也必須有scope的界線，並把已宣告但缺scope的可恢復前置傳到Q2 UNKNOWN回應。`tracking_scope_required`是trusted server binding flag，production固定true；舊直接建構unit fixture維持可用，不能把其legacy測試當production支援。

engineering producer用`bind_engineering_scope`在新產物加入獨立scope檔與完整有向對，更新兩圖hash與scope pin。僅接受`rSYN`且SYNTHETIC approval_ref；不能替r004核G4。沿用schema中的`G4_approved`欄位是synthetic工程語意，完全不改r004的G4=false／現有scope。linked／dynamic準備器會寫tracking_scope.json及registry ref；runner engineering fixture也提供scope，domain export保存原始bytes（不重序列化）。現有RGB、index、detector、clock、params、D65保持既有輸入，不重新跑detector或render。

B2重錄時必須從新產品**重建工程metadata**，不能沿用舊無scope的registry並補寫response/journal。這會有預期的region/camera/context pins差異，應在新收據逐項列出，不再宣稱7個context完全不變。scope文件也須交給#127／AC7；link-record.v2由產品原生輸出。B1未合入前，不以未合版本宣稱「新合併產品重錄」。

## 實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: Draft `codex/q1q5-scope-pins-rc4`；base `680ca357a31b664bed3feb6a5284dcd7c5c0d94d`，精確head見PR。
- Files changed: Q1/Q3 response、API loader、controller binding、engineering scope helper、linked/runtime export、synthetic registry script、runner fixture與focused tests、本文件；未改Claude kit／frontend／契約。
- Commands run and results: 既有離線uv/Python執行 `pytest -q -p no:cacheprovider tests/q1q5/test_scope_pins_rc4.py tests/q1q5/test_baseline_runner.py tests/q1q5/test_linked_runtime.py tests/q1q5/test_api.py tests/q1q5/test_q5_controller.py`：128 PASS。補production legacy registry assertion後重跑 `test_scope_pins_rc4.py test_api.py`：44 PASS（子集，不相加）。變更11個Python檔 `ruff check --select F,UP,B` PASS；`git diff --check` PASS。先前含I lint列出3個既有import排版問題，本次未重排無關段落。
- Artifacts: code/docs/tests，沒有新RGB／推論／正式錄製；精確檔案SHA見PR。
- Verified: scope key／output hash一致、byte pin傳到Q2與每筆input_pins、原始scope檔export；缺scope在seed前UNKNOWN；損毀scope不執行；synthetic helper拒絕r004。
- Not verified: B1合併、B2三包真模型重錄、#127 rc4完整176份／AC7、HTTP/browser、正式r004／G4／人工正確性。
- Deviations, UNKNOWN items and follow-ups: B2依新合併SHA重錄；此PR不自合，尚不能宣稱176份已通過。
