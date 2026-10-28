> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# Phase 2：05／11 品質修正與 demo

2026-10-13 核准：11回答品質修正、05局部追蹤修正與整合驗收，統一在8016共用工作台。以`001a0fc`為起點，保留原A＋B＋C收據。先交付11可操作demo，再完成05一次受限研究與最終驗收；階段完成時報告可合併main的範圍與必要條件。當時尚未授權merge／push；2026-10-14 使用者另已核准先合併通過驗證demo與必要依賴到main、繼續11品質修正、05維持baseline，結束時上傳必要內容並刪除目前工作樹，只留紀錄。

新合成封存測試集、07／08、09真實或訓練ReID、10其他事件、13／14／15繼續暫緩，須使用者另行確認。本輪不render、不建立新RGB資料、不改原Blender／GT／product凍結內容及正式研究權限；重用本機Qwen2.5 7B與PostgreSQL。

## 階段與驗收

| 階段 | 交付與驗收 |
| --- | --- |
| R1：11 demo | 本機模型選擇typed tools及證據欄位；伺服器對照成功收據逐欄核對，結構化表格保留來源、未定、替代及查詢截斷。保存原需求、鏡頭／時間與語言，澄清後延續；安全拒絕明示。停止／恢復、owner／mode／source與manual守門保留。Demo是有限來源操作證明，不提前聲稱完整品質通過。 |
| R2：05局部追蹤 | 先以開發資料的GT-free指派trace歸因，再做單因素局部延續實驗，只由開發資料選設定。凍結程式／設定／來源後才一次評估既有test；若未達標，保留baseline與負結果，不依test再調參。已有unambiguous_partial無增益，不能只重做相同機制。 |
| R3：獨立驗收 | 原R1題組＝40常規／8安全，中英各常規20、雙模式、分頁與零結果；原48題未實際包含澄清回覆及專門執行預算題，原文描述於本輪更正。R2另凍結40常規／8安全新公開問題，含8組真實澄清→固定回覆、8 DETAIL及8兩頁查詢；執行預算由fixture／HTTP守門獨立驗證。題目與公開DTO oracle在實测前固定；原八題只作開發回歸，原6／8不改寫。另做完整回歸、HTTP／browser及來源保留核對。 |

05門檻：固定原150個detector contacts與原偵測分母；switches≤4、mixed tracks≤3、fragmentation≤6、singletons≤6，完整保留UNKNOWN／替代／漏偵。GT僅供凍結後評估，producer不讀GT／recipe；重現及poison／removal驗證保留。既有test曾曝光，只能支持此固定合成來源回歸，不能稱新sealed holdout。

其中原FRAGMENTED計數是軌跡內部缺少採樣時間點，不是完整人物身分分裂。測試前另固定防止指標取巧的判定：每個reference actor產生的track數及首採樣後new-track決策不得增加，報告缺樣本總數與缺口長度分布。後者含延後首次觀測，不能解讀為真實人物身分重設。由拆軌跡、重設ID或隱藏觀測造成的表面改善不接受；公開收據只保留aggregate／hash／histogram，不輸出actor IDs。

11門檻：常規≥36／40、中英各≥18／20；所有接受的typed事實與引用須完全對應原公開DTO，完整性誤報0；安全守門8／8，另列模型乾淨拒絕品質。未查完整cursor chain時不能稱全部；來源分頁、模型presentation截斷與事件本身完整性各自保留。工具預算、停止後usage、延遲與未知usage持續實測，不以少報結果改善分數。

## main整合判斷

每一checkpoint分別報告：owned改動、驗證輸入hash與範圍、main／remote main確切SHA、必要依賴與merge-tree結果、研究品質與工程守門狀態。僅有測試PASS或demo可操作，不足以證明可單獨cherry-pick或整個工程branch可merge。

本輪不修改frozen Phase2研究ref；Phase1 ref的独立更新需按其來源收據核對。既有工程依賴、原來源／歷史發布條件、正式Phase1 blockers及另一對話未提交修改需各自核對；不以本輪品質修正清除那些條件。本輪已取得實際merge／push授權；精確選取本批通過驗證程式及必要依賴，其他對話checkpoint不自動納入main。

## 進度及證據

起點Phase2功能工作量估算約50%。11品質驗收成立後目標約55%；05與11均成立後目標約60%（55–65%）。只在實際門檻通過後更新，此比例與正式Phase1Exit／frozen Phase2驗收各自獨立。

本輪收據：`data/engineering/phase2_repair_0511_20261013/`；新producer與模型內部ledger僅放ignored local_run／本機state，原A＋B＋C的frozen bytes與失敗收據保持保留。

### R1 demo已交付；R2品質失敗；R3工程通過、實際回答未通過

8016選「局部鏡頭精度研究v2 → 調查與品質」。選DOOR、8–16秒，按中文或英文範例，再開始本機調查。範例只填需求，不提前呼叫模型。新回答逐欄呈現原DTO，完整登錄分母未知時標UNKNOWN；全部原欄位、替代及來源引用可展開核對。重新開啟還原原需求與鏡頭／時間；舊v2／v3調查保留literal核對但唯讀、禁止續跑，當前需求完成度NOT_CHECKED；更早未驗證版本另標LEGACY_UNVERIFIED。

真實本機7B的QA案例已完成3筆literal rows與1citation／UNKNOWN分母核對；8016另實際驗證停止／立即恢復、自動等待、瀏覽器reload後token recovery與原需求還原。38項HTTP／實際PG守門及1393項05HTTP／原媒體斷言通過；工作台05頁查出4tracks、11張原240×180影格，保留baseline與未定。共享Node237／排除另一對話修改的獨立快照232、Ruff／mypy233來源檔通過；總數不相加。完整Python回歸狀態以[工程收據](../../data/engineering/phase2_repair_0511_20261013/engineering_validation.json)為準。

05唯一ROBUST_THREE_CLEAN候選：development四項指標(3,2,2,2)→(3,2,2,2)，預定strict gain未通過；一次既有test(4,3,7,6)→(3,2,7,6)，缺採樣tracks仍7、缺採樣總數仍11，150contacts／144已標定／160可見分母不變。每actor track multiplicity無增加，test關聯數23→22、首採樣後新軌決策19→19；不把局部改善當完整身分品質。GT poison／removal fresh rebuild一致，175個舊來源／收據檔不变。candidate不啟用，原09／10服務不替換。詳見[研究結果](../../data/engineering/phase2_repair_0511_20261013/research_test_result.json)。

完整Python3567 PASS／0fail／error／skip，980.838秒，含require-physical-evidence；499個backend輸入hash前後不變。4個warnings為既有record_property／xunit2格式提示。前端呈現與恢復表單於Python執行期間完成調整，另由最終Node237／owned232驗證，不將Node數字累加。模型runtime與凍結producer程式未在驗收中改動。

原R1實測因品質門檻已不可能達成而停止：21 attempted（17 COMPLETED／3 FAILED／1 STOPPED），11通過，27未開始。保留[原partial](../../data/engineering/phase2_repair_0511_20261013/agent_benchmark48_r1_partial.json)與診斷，不當作完整48題。3次模型第二請求於120秒回傳 unavailable；另有DETAIL只查列表及兩頁只讀一頁的需求落差。完成回答的literal欄位錯誤0，與未完成任務造成的原scorer缺引用錯誤分開報告。

11 R2 新增原始明確需求守門：指定欄位、FIRST／DETAIL及分頁條件独立核對；未完成時只給固定條件名稱回饋，計入既有預算，安全拒絕仍終止。舊v2 literal證據保留，但唯讀、需求完成度NOT_CHECKED。傳輸profile僅把同一7B本機請求timeout由120調至180秒；不更換模型、8192 context或自動重試，不保證延遲。

R2程式與新40＋8公開問題／DTO oracle已各自凍結；114 runtime、59 benchmark及20 transport針對性測試通過，owned Node233通過。這些fixture和零模型契約檢核不當作模型品質分數。新完整Python3643 PASS／0fail／error／skip、631.945秒，Ruff及strict mypy235來源檔PASS；566份輸入hash不變。初次collection同名測試FAIL另存，不改寫；更名後完整重跑通過。owned Node233與共享238分開記錄，總數不相加。54個隔離HTTP／實際PG守門通過，11次SCRIPTED fixture呼叫、0真實模型；兩次verifier修正另記。

R2實際8016 demo完成：本機7B兩次呼叫、一次工具、162.430秒、prompt8549／output192tokens，3筆來源欄位獨立逐項相等，來源分母UNKNOWN。瀏覽器reload／恢復原需求、鏡頭與時間、相同answer hash且模型呼叫數不增，console0。詳見[新demo收據](../../data/engineering/phase2_repair_0511_20261013/agent_demo_r2.json)。

固定R2完整48題已完成但品質FAIL：常規12／40，中文7／20、英文5／20；417個接受literal欄位核對錯誤0，但4個完成回答誤選列表證據，未完成要求的DETAIL來源。安全邊界8／8，模型正確拒絕原因與語言僅2／8，不能把REFUSED狀態當乾淨拒絕品質。8次澄清回覆均已實際提交，完整完成鏈0／8。108次模型呼叫／108次已知attempt，unknown／timeout均0，prompt476331／output8555tokens，P50模型呼叫58.062秒、P95 110.844秒。全部原問題／oracle及完整失敗收據已原樣上傳engineering，詳見[完整R2結果](../../data/engineering/phase2_repair_0511_20261013/agent_benchmark48_r2.json)與[獨立核對](../../data/engineering/phase2_repair_0511_20261013/agent_benchmark48_r2_independent.json)。

R3已套用經同儕檢核的局部11修正：明確FIRST／DETAIL與分頁要求、DETAIL來源鏈、重複查詢及fact選取的計費回饋、人類澄清後需求保存、限定selector與缺欄位名稱回饋、既有拒絕原因的定義說明。所有回饋仍由模型自行選擇後續動作，伺服器不代選答案、來源或拒絕原因；預算、模型、題目、資料與oracle不变。現行typed.evidence.v4，舊v2／v3回答保留原literal證據並唯讀，完成度NOT_CHECKED。完整工程回歸已通過3736項；新的完整模型回放尚未開始。再次實測將使用同一已曝光PUBLIC R2 48題，範圍明示EXPOSED_LOCAL_PUBLIC_REGRESSION_NOT_INDEPENDENT_HOLDOUT，不能稱獨立holdout。Phase2暫維持50%估算。

2026-10-14 最新工程tip `b1cf0c4`：R3原c24版本與context734版本各自完成Python3736 PASS／0 fail/error/skip；不是兩個總數相加。734 context版622.103秒，Ruff／strict mypy235檔PASS，566份backend輸入不變。明確prompt壓縮24916→22069，仍用24k既有wire上限，不刪除已保存工具收據；[context release](../../data/engineering/phase2_repair_0511_20261013/agent_runtime_release_r3_context.json)、[工程驗證](../../data/engineering/phase2_repair_0511_20261013/engineering_validation_r3_context.json)與[來源凍結](../../data/engineering/phase2_repair_0511_20261013/engineering_sourcefreeze_r3_context.json)各自保留。早先prompt24916超限、PG環境與harness失敗收據未改寫。

新版[HTTP／PG驗證](../../data/engineering/phase2_repair_0511_20261013/agent_http_validation_r3_context.json)68守門PASS，23 SCRIPTED fixture calls、0真實模型；v4完成度literal核對與舊v2/v3唯讀NOT_CHECKED都涵蓋。這不等同模型品質。其後首次真實7B demo只1call／75.660秒、0工具，模型選了不存在的 `query_receipt` 事實欄位，`AGENT_GOAL_FIELD_UNAVAILABLE`終止，原[實際失敗](../../data/engineering/phase2_repair_0511_20261013/agent_demo_r3_context_first_failure.json)已上傳。R2成功162.430秒案例只能作歷史唯讀展示，不能說新版demo已成功。

進一步schema欄位enum、通用需求範例與通用read-verb修正已在private候選通過220 fixtures、Ruff／mypy7檔，兩頁prompt22437／24000；[有界摘要](../../data/engineering/phase2_repair_0511_20261013/agent_private_schema_candidate_r3_summary.json)保存候選與驗證hash、原negative。獨立peer已通過scope／schema／守門保留核對（收據SHA6f26768d…，沒有新增模型品質分數），未套用到734、未開始新48题，不能提前宣布驗收通過。05 baseline與Phase2约50%維持。本輪按使用者新要求先更新已完成工作文件及demo就緒狀態，使用動態本機埠排演；逐段腳本、真實依賴與交付缺口以[第一版demo](DEMO_V1.md)及[readiness收據](../../data/engineering/phase2_repair_0511_20261013/demo_v1_readiness_20261014.json)為準。

R2加入main的嘗試曾由自動核准審查以完整48題品質gate尚未完成拒絕，操作未執行，main仍439c866；待最終真實品質達標後，以最小已驗證demo／必要依賴範圍重新送審，不整批帶入大型失敗收據與題組。

已驗證R1 checkpoint `7d053543316d13272039402d33eb3c3bcab06ba8` 與必要001a0fc A＋B＋C依賴已合併到main `439c8669eae740ed5750eeb1f853c0ddf73ec507`，並push及ls-remote核對。merge tree `e668618329b789fd1fd12e28d379928cd1d5bd68` 與已測R1 tree完全相同；499 backend及45 owned前端檔逐檔對照，引用原3567／232收據，不冒稱重跑。只有WORK_LOG文件衝突，原main行數內容保留。另一對話158d74c Blender視覺checkpoint未一併merge。詳見[合併收據](../../data/engineering/phase2_repair_0511_20261013/main_demo_merge.json)。

工作樹刪除前先完成驗收、精確上傳程式與公開收據，再停止依賴舊路徑的服務。只保留單份必要本機模型／現行人審及資料庫／唯一原始輸入；退役生成物只留hash及紀錄，不建立大型封存。原凍結locator綁定舊絕對路徑，刪除後標為offline；恢復執行需另行重新綁定，不冒稱目前main可直接portable replay。
