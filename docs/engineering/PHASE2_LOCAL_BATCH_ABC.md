> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# Phase 2 本機 A＋B＋C 整合

2026-10-14 的目前可展示範圍、實際來源／PostgreSQL／Ollama依賴及動態埠啟動見[第一版demo](DEMO_V1.md)；本文件歷史收據不升格成新版驗收。05維持baseline，11最新完整模型品質未過，Phase2約50%。

2026-10-13 核准範圍：05、09 合成診斷、10 區域出入／持續停留、11 本機模型、12 本機 PostgreSQL，以及同一工作台的整合驗證。入口 `frontend/workbench`／8016「調查與品質」。04 仍只支援既有單一 E0 流程；06 仍是評測準備。07、08、10 其他單人與多人事件、13、14、15 均暫緩，須使用者重新確認。

| 項目 | 本批次工作及驗收邊界 |
| --- | --- |
| 05 | 獨立 producer／實驗 namespace，開發集選設定後凍結測試；固定 detector contacts，保留 switches／混合 tracks／fragmentation／singletons 與 FP／FN／UNKNOWN、人口與分母。沒有成立的精度改善不標成改善。 |
| 09 | 同源合成 association／外觀／片段假說與原候選池排名；非機率，不確認人物、不訓練真實 ReID。 |
| 10 | REGION_ENTRY、REGION_EXIT、SUSTAINED_DWELL；規則及設定版本、同鏡頭證據、去重、trigger／retract 歷史、觀測缺口與左截斷 UNKNOWN。 |
| 11 | Qwen2.5 7B Instruct 經本機 Ollama：自由中文／英文、typed tools、必要澄清、工具收據引用；逐步執行、停止／恢復、來源／模式重驗、執行預算與真實 token／延遲紀錄。 |
| 12 | 真實 PostgreSQL 18，schema migrations、frozen records／CASE／REPORT／REVIEW／JOB、CAS transactions、descriptor index／media metadata／topology cache；同源 SQLite 等價比較、併發與 pg_dump／pg_restore。 |
| C | same-origin API、角色／來源／manual baseline 保護、原影格、瀏覽器操作、完整回歸與不可變來源核對。 |

## 資料及權限

- 原 `.blend`、來源 PNG、既有 accuracy v2／E1 product bytes 與 frozen Phase 2 refs 保持原版本。新的研究輸出只在 ignored `data/engineering/local_run/phase2_abc/research/`。
- GT／reference labels 只供凍結後評估；不給 Agent／producer／工具，工作台只載入受可信發布收據綁定的 aggregate。模型只接收 bounded public metadata，不接收照片、來源路徑、GT、SQL 或任意 filesystem／shell／network tool。
- 固定 loopback endpoint `127.0.0.1:11437`；模型 digest `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`。模型選擇、endpoint、PostgreSQL DSN／schema／路徑均由伺服器管理，瀏覽器不能覆寫。`OLLAMA_NO_CLOUD=1`。
- 模型只能使用此案例選定鏡頭／最多120秒來源窗、實際簽發 refs 與 typed arguments。引用收據有效不自動證明每一句語意正確；八題小型測試只描述其固定合成範圍，不宣稱跨場景泛化或 token 節省。
- PostgreSQL 匯入逐一比對 canonical record receipts 後才切換 product repositories。CASE／REPORT／REVIEW 仍是來源與模式綁定的附加修訂。自然語言案例的完整內部執行／恢復 ledger 仍是本機 SQLite，保存 recovery token 與 generation；PG 保存安全的公開 JOB 摘要與 references；token 不出現在列表、模型提示或公開收據。跨工作台連線需以 token 恢復相同凍結來源。
- 進入 manual baseline 前停止同一 owner 的待執行 Agent 工作；其後全部新 assistance API 仍受既有 guard 拒絕。停止或來源／模式改變後，模型與工具的遲到結果不提交。
- 自然語言工具讀取既有 E1／accuracy v2 的獨立 product freeze；09／10 新研究規則使用各模式的研究 freeze，在下方研究查詢呈現。兩種 freeze、設定與事件 references 分開驗證，不把新研究結果回寫舊 product。
- 原影格仍從已驗證 registry 讀取；PG 只存 hashbound metadata。原人工幾何核對資料庫、人工語意權限與 Phase 1 formal blockers 各自保留。

## 本機操作與重現

PG lifecycle：`uv run python scripts/phase2_local_postgres.py start|status|stop`。專用 ignored cluster、socket `/private/tmp/amidst-pg-abc`、port55432；TCP auth reject，應用使用專用 Unix socket。沒有全域 brew service 或登入自啟。

模型使用官方 Ollama 與官方 `qwen2.5:7b-instruct`，ignored weights 在 `data/engineering/local_run/phase2_abc/ollama_models`。以 `OLLAMA_HOST=127.0.0.1:11437`、上述 `OLLAMA_MODELS`、`OLLAMA_NO_CLOUD=1`、`OLLAMA_NUM_PARALLEL=1` 啟動 `ollama serve`；下載是明確的管理操作，HTTP 查詢不下載或重建模型。固定 provider metadata 存在 ignored `agent_provider.json`。

新研究流程重用既有合成 RGB，不新增 Blender render。開發選擇、正式測試凍結、fresh reproducibility 與 producer／evaluation 隔離驗證見本輪 research receipt。本輪固定測試未通過05門檻：switches4→5、fragmentation7→8，singletons6→2仍不足以接受；工作台兩種模式均使用各自的 baseline freeze。05精度改善目標仍未完成，沒有用同一測試結果再調參。原測試來源曾於歷史實驗使用，不宣稱新的 sealed holdout。新區域規則沒有獨立事件 reference，accuracy為N/A；41筆baseline規則候選（entry34、exit7、dwell0）不是正確事件分母。

每次依據新的 code/artifact snapshot 驗證，不沿用93eb611以前的3325／213 PASS。

本輪驗證收據集中於 `data/engineering/phase2_abc_20261013/`；歷史01–03、04／06及正式研究收據不覆寫。Phase 2 的進度比例為 PRD 功能／剩餘工作估算，沒有官方權重公式，不能以完成項目數或測試通過率代替總目標完成率。

官方 runtime 來源：[Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)、[local/cloud settings](https://docs.ollama.com/faq)、[Qwen2.5 model](https://ollama.com/library/qwen2.5:7b-instruct)。

## 本輪結果與尚未完成的目標

| 項目 | 實際結果 |
| --- | --- |
| 05 | 實驗、凍結、GT隔離與重現驗證完成；`NO_ACCEPTED_CONTINUITY_GAIN`，精度改善目標未完成。固定測試switches4→5、fragmentation7→8，工作台保留baseline。 |
| 09 | 合成診斷可查詢；同池20queries／84可行同身分片段對，完整／移除外觀R@1為0.65／0.45。分母只包含產出的可比較片段，錯接／漏接／未定保留，不認證真實ReID。 |
| 10 | 區域進入、離開與持續停留規則及生命週期已接入；本來源baseline41候選＝entry34／exit7／dwell0，12觀測支持、29UNKNOWN。持續停留邏輯由受控fixture驗證；獨立事件accuracy為N/A。 |
| 11 | `LOCAL_AGENT_PROTOTYPE / QUALITY_GATE_NOT_MET`。真實7B固定開發題組6／8自動通過，5流程完成、2需澄清、1安全拒絕。英文reply只有引言、沒有要求的事實；中文reply把返回前三筆說成全部三件，但完整公開查詢有36候選。部分回答亦省略不確定性與分頁限制，語意正確性未認證。 |
| 12 | 實際PostgreSQL已提供4runs／1040canonical records的工作台讀寫。實際整合DB以同一MVCC snapshot dump／restore，14資料表指紋及680查詢／1332pages一致；CASE／REPORT／REVIEW／公開JOB、descriptor、media metadata、topology cache均核對。 |

11最終題組有16次實際模型請求／16份已知usage，未知usage0；prompt53468、output1391tokens，單次呼叫p50 13.569s／p95 103.287s。這是已用於提示除錯的小型E1開發題組，不能當成密封測試、泛化精度或token節省證據。引用有效與流程完成不等於語意品質通過；前端會依实际收據明列結果截斷並要求核對。停止後的遲到答案／工具結果不提交，實際遲到usage另記DISCARDED，耗時與token預算不因停止／恢復重設。

Phase2整體功能目標暫估約50%（45–55%）。本輪增加本機資料庫、研究規則與模型原型，但05與11品質門檻未通過，因此未達原先以品質驗收成立為前提的約60%目標。此為工作量估算，與正式Phase1Exit／frozen Phase2研究驗收及測試通過率各自獨立。所有暫緩項目仍需使用者重新確認。

## 最終驗證

最終狀態為 `VALIDATED_LOCAL_ENGINEERING_WITH_UNMET_QUALITY_GATES`。可操作整合及守門驗證完成，05與11品質目標仍未完成；總收據見 [validation.json](../../data/engineering/phase2_abc_20261013/validation.json)。

| 驗證 | 實際結果與範圍 |
| --- | --- |
| 完整 Python | 3436 PASS，0 fail／error／skip，1088.886秒；包含 `--require-physical-evidence`。4個警告僅為pytest的record_property與xunit2輸出格式。完整驗證期間550份backend輸入前後hash一致。 |
| Ruff／strict mypy | 全部通過；mypy224來源檔。 |
| 前端 | 共享工作樹230 PASS；排除其他對話的世界方向與畫面牆修改後，本批次獨立文字快照225 PASS。兩個總數各自獨立，不累加。 |
| 實際 HTTP | product136斷言；Agent19斷言，包含真實模型、停止／恢復、重啟後token恢復、跨owner／mode及manual barrier；研究193請求／1247斷言，兩模式41候選及原影格、非法範圍核對。 |
| PostgreSQL | 實際整合DB dump／restore5023斷言，14表指紋、680查詢／1332pages一致。原DB保留；兩份harness失敗紀錄保留並説明修正原因。 |
| 8016瀏覽器 | 完成模型開始／停止後立即恢復、自動等待續跑、保存列表、引用與截斷提示、05／09分母及UNKNOWN區域事件原影格解碼，console warning／error為0。這是流程驗證，不是模型回答語意認證。 |
| 原來源／人審保留 | 202個不可變資產的SHA／大小／mtime及三個frozen refs未變；原E1 test244與development244張RGB共488原檔完整核對、21249斷言。原27筆人工差異逐欄位保留，最後核對時共30筆，允許另一對話的後續追加，不輸出人工payload。 |

瀏覽器曾發現模型取消尚在結束時立即恢復會停在準備狀態；只修正前端重新取得相同案例、驗證owner/source/mode/model後有界等待及自動續跑，加入兩個回歸測試，實際8016已再次通過。後端550份輸入及最終模型題組保持凍結；瀏覽器答案仍可能不完整，因此「流程完成・回答待核對」與來源收據同時呈現。

最後staged diff核對清除整合wrapper的3個空白行尾與前端的1個行尾空白；Python AST及兩份檔案的token序列完全一致。保留完整pytest原輸入hash，另列最終格式後輸入與7個整合測試PASS；Ruff、mypy224檔及Node230／225重新通過，`git diff --cached --check`通過。這7項不加到3436總數，完整Python未因純格式修改重跑；模型／研究核心與題組凍結內容未變。

本批次只建立本機工程checkpoint，不push或merge。其他對話的世界方向、幾何預覽、畫面牆及人工核對紀錄不包含在本批次checkpoint；共享app只提交本批次整合片段，保留其餘工作檔內容。工作台、Ollama與PostgreSQL持續在本機供查看；未設定登入自啟。
