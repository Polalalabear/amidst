# Phase 2：05／11 品質修正與 demo

2026-10-13 核准：11回答品質修正、05局部追蹤修正與整合驗收，統一在8016共用工作台。以`001a0fc`為起點，保留原A＋B＋C收據。先交付11可操作demo，再完成05一次受限研究與最終驗收；階段完成時報告可合併main的範圍與必要條件。此授權不包含實際merge／push。

新合成封存測試集、07／08、09真實或訓練ReID、10其他事件、13／14／15繼續暫緩，須使用者另行確認。本輪不render、不建立新RGB資料、不改原Blender／GT／product凍結內容及正式研究權限；重用本機Qwen2.5 7B與PostgreSQL。

## 階段與驗收

| 階段 | 交付與驗收 |
| --- | --- |
| R1：11 demo | 本機模型選擇typed tools及證據欄位；伺服器對照成功收據逐欄核對，結構化表格保留來源、未定、替代及查詢截斷。保存原需求、鏡頭／時間與語言，澄清後延續；安全拒絕明示。停止／恢復、owner／mode／source與manual守門保留。Demo是有限來源操作證明，不提前聲稱完整品質通過。 |
| R2：05局部追蹤 | 先以開發資料的GT-free指派trace歸因，再做單因素局部延續實驗，只由開發資料選設定。凍結程式／設定／來源後才一次評估既有test；若未達標，保留baseline與負結果，不依test再調參。已有unambiguous_partial無增益，不能只重做相同機制。 |
| R3：獨立驗收 | 48題模型題組＝40常規／8安全，中英各常規20，涵蓋两模式、分頁、零結果、澄清與執行預算。題目與公開DTO oracle在實测前固定；原八題只作開發回歸，原6／8不改寫。另做完整回歸、HTTP／browser及來源保留核對。 |

05門檻：固定原150個detector contacts與原偵測分母；switches≤4、mixed tracks≤3、fragmentation≤6、singletons≤6，完整保留UNKNOWN／替代／漏偵。GT僅供凍結後評估，producer不讀GT／recipe；重現及poison／removal驗證保留。既有test曾曝光，只能支持此固定合成來源回歸，不能稱新sealed holdout。

其中原FRAGMENTED計數是軌跡內部缺少採樣時間點，不是完整人物身分分裂。測試前另固定防止指標取巧的判定：每個reference actor產生的track數及首採樣後new-track決策不得增加，報告缺樣本總數與缺口長度分布。後者含延後首次觀測，不能解讀為真實人物身分重設。由拆軌跡、重設ID或隱藏觀測造成的表面改善不接受；公開收據只保留aggregate／hash／histogram，不輸出actor IDs。

11門檻：常規≥36／40、中英各≥18／20；所有接受的typed事實與引用須完全對應原公開DTO，完整性誤報0；安全守門8／8，另列模型乾淨拒絕品質。未查完整cursor chain時不能稱全部；來源分頁、模型presentation截斷與事件本身完整性各自保留。工具預算、停止後usage、延遲與未知usage持續實測，不以少報結果改善分數。

## main整合判斷

每一checkpoint分別報告：owned改動、驗證輸入hash與範圍、main／remote main確切SHA、必要依賴與merge-tree結果、研究品質與工程守門狀態。僅有測試PASS或demo可操作，不足以證明可單獨cherry-pick或整個工程branch可merge。

main與frozen研究refs保持原狀。既有工程依賴、原來源／歷史發布條件、正式Phase1 blockers及另一對話未提交修改需各自核對；不以本輪品質修正清除那些條件。可提出具體合併候選與順序，但實際merge需使用者確認。

## 進度及證據

起點Phase2功能工作量估算約50%。11品質驗收成立後目標約55%；05與11均成立後目標約60%（55–65%）。只在實際門檻通過後更新，此比例與正式Phase1Exit／frozen Phase2驗收各自獨立。

本輪收據：`data/engineering/phase2_repair_0511_20261013/`；新producer與模型內部ledger僅放ignored local_run／本機state，原A＋B＋C的frozen bytes與失敗收據保持保留。

### R1 demo已交付；R2候選拒絕；R3驗收執行中

8016選「局部鏡頭精度研究v2 → 調查與品質」。選DOOR、8–16秒，按中文或英文範例，再開始本機調查。範例只填需求，不提前呼叫模型。新回答逐欄呈現原DTO，完整登錄分母未知時標UNKNOWN；全部原欄位、替代及來源引用可展開核對。重新開啟還原原需求與鏡頭／時間；舊版調查明示LEGACY_UNVERIFIED且禁止續跑。

真實本機7B的QA案例已完成3筆literal rows與1citation／UNKNOWN分母核對；8016另實際驗證停止／立即恢復、自動等待、瀏覽器reload後token recovery與原需求還原。38項HTTP／實際PG守門及1393項05HTTP／原媒體斷言通過；工作台05頁查出4tracks、11張原240×180影格，保留baseline與未定。共享Node237／排除另一對話修改的獨立快照232、Ruff／mypy233來源檔通過；總數不相加。完整Python回歸狀態以[工程收據](../../data/engineering/phase2_repair_0511_20261013/engineering_validation.json)為準。

05唯一ROBUST_THREE_CLEAN候選：development四項指標(3,2,2,2)→(3,2,2,2)，預定strict gain未通過；一次既有test(4,3,7,6)→(3,2,7,6)，缺採樣tracks仍7、缺採樣總數仍11，150contacts／144已標定／160可見分母不變。每actor track multiplicity無增加，test關聯數23→22、首採樣後新軌決策19→19；不把局部改善當完整身分品質。GT poison／removal fresh rebuild一致，175個舊來源／收據檔不变。candidate不啟用，原09／10服務不替換。詳見[研究結果](../../data/engineering/phase2_repair_0511_20261013/research_test_result.json)。

完整Python3567 PASS／0fail／error／skip，980.838秒，含require-physical-evidence；499個backend輸入hash前後不變。4個warnings為既有record_property／xunit2格式提示。前端呈現與恢復表單於Python執行期間完成調整，另由最終Node237／owned232驗證，不將Node數字累加。模型runtime與凍結producer程式未在驗收中改動。

48題／public DTO oracle已於模型執行前凍結，中英各20常規與8安全、雙模式；6000-char presentation於零模型契約檢核可完整保留所需來源列。此檢核不是模型品質得分。真實48題仍在執行，Phase2暫維持50%估算；demo不提前認定11品質通過或達成60%。

本輪偵測local main已由其他對話推進至3991b79，93eb611工程基礎已有；本批沒有修改main。其文件patch與本地8aadeb3等價，不必重做；GitHub main仍83ca3f，工程tip仍93eb611。仍需001a0fc的A＋B＋C依賴才能整合本次11修正。13個大型來源衍生JSON與76PNG屬既有已發布工程祖先，本次沒有新增mesh或PNG；新增公開DTO題組JSON為2524165bytes，已凍結且無GT／credentials／raw媒體，與來源封存檔分類不同。c5956dc不是祖先。工程候選的完整回歸與確切SHA另記收據；本批未執行merge／push。
