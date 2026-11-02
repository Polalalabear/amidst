# G4 回條綁定補充草案（CQ-21a）

日期：2026-10-29（Asia/Taipei）。**PROPOSED／UNSELECTED；11條均待使用者U8核定。**

本文件是 #308 明確要求的條文選項草案，沒有採用新 wire、authority、purpose enum 或流程；不修改主契約、#260、schema或程式，不產正式回條、不核准任何圖、scope、邊、方向或用途。推薦不是選定值。未核定前 CQ-21 #304 保持 blocked-user，任何未選、PROPOSED、UNKNOWN 或缺件的部分預設 fail closed。

## 來源、現況與不變邊界

- 架構基準：[#306](https://github.com/Polalalabear/amidst/issues/306)。現有回條格式固定於 [#260@d560f224be0f93cf62076f5ae2fa78b0ae957d15](https://github.com/Polalalabear/amidst/blob/d560f224be0f93cf62076f5ae2fa78b0ae957d15/docs/contracts/Q1Q5_D86_G4_RECEIPT_PROPOSAL_20261027.md) §3／§3.1／§3.2，檔案SHA-256 `c697ae8890a4777b06ec60e3fcd375d7096115b2a1ff291726a36a5c6d3cc8d8`；主契約同head的§5.3／§5.4，檔案SHA-256 `51df697727349c88ead6471f5a79432b162b42409305ec26901e88239b1ee667`。
- 缺口來源：[同head增量複審第三節](https://github.com/Polalalabear/amidst/pull/260#issuecomment-6460749502)、[CQ-21預檢](https://github.com/Polalalabear/amidst/issues/304#issuecomment-6460066327)。本文件逐一回答A1–A5、B1–B3、C1–C3。
- 程式現況固定於 staging `434e57922a24d2422226871c0bb672dc7bc3584b`：`api.py:449–491`的registry／run鍵封閉；`RuntimeBindings`沒有receipt；controller重載原圖；response scope、decision input_pins及session成分未帶receipt。這些是現況，不是本文件已改好的行為。
- [CQ-02草稿#348@ac70ed75e4503ab54ec58c08ec58957c179bb72c](https://github.com/Polalalabear/amidst/pull/348)明列五鍵白名單沒有effective gates；它只提供缺口觀察，不是本文件的authority。若U8選擴充白名單，CQ-02的未決payload／hash都必須重建。
- D92-C仍是同一流程信任：使用者checkpoint核准留言＋協調者D決策，不能靠同帳號login或producer自稱核准。沒有新PKI、簽章或第二套外部trusted-pin檔；受控server config仍是bytes pins入口，request不得自帶receipt path／hash／選項升權。
- D80 query preimage、原始graph／scope bytes及其hash不變。GT、renderer軌跡、visibility、depth、私有劇本與評分窗不進adapter、候選、ranking或模型輸入。身份UNCONFIRMED，物理通行與碰撞UNKNOWN。G4、劇本凍結、渲染條件、合併與發包的使用者gate不由本文件解除。

## A 收據綁定

### A1 欄位位置、型別與hash重算

**現況：** §3.1已有canonical公式，但「至少包含」表漏列四個欄位。沒有已採用的正式schema可由本文件代填。

**條文草案／推薦方案：** 四欄放在回條頂層：`schema_version`為非空string，草稿與正式種類必須區分；`status`為封閉狀態string，草稿只能PROPOSED，沒有真實核定不得使用正式核定狀態；`date`為ISO8601日曆日期string（YYYY-MM-DD，不推定為核准時刻）；`decisions_sha256`為64位小寫hex string。載入先驗受控bytes pin、JSON／欄位結構，再按**該已核版本的明列白名單**重建payload、重算SHA-256，比對收據自稱值、使用者留言引用值及D決策引用值；任一矛盾是DataIntegrityError。缺必要核准來源或仍待決不產effective authority。

未擴充版本時沿用#260的五鍵、`sort_keys=True`、`separators=(",", ":")`、`ensure_ascii=True`、`allow_nan=False`、UTF-8且不含尾端換行；建議、yyin意見、refs、status／date／provenance及hash自身不進五鍵payload。表列依ID固定排序，`region_path`／`edge_path`保留有向次序，不能為排序而重排路徑。採B1擴充時須使用新版本的完整白名單，不用遞迴排除法猜欄位。

**需要使用者決定：是，U8。選項：**

1. **TOP_LEVEL_FIELDS（推薦）**：採上列頂層四欄。優點：對齊既有CQ-02草稿及§3.1，重算位置明確；缺點：正式schema仍須另案實作，不能以文件表格當schema接受證據。
2. **HEADER_OBJECT**：四欄集中到一個有封閉欄位的header物件。優點：metadata集中；缺點：會改草稿結構、loader與測試路徑，須重發草稿／bytes pin，不能默認相容。

**影響位置：** 提案欄位表；將來receipt loader與`api.py:449–491`入口驗證。**#309參數：** `contract_option("A1", "TOP_LEVEL_FIELDS")`或`HEADER_OBJECT`；須驗缺欄、錯型別、自稱hash不符、選定值變更與路徑次序變更，未選預設拒絕。

### A2 registry位置與全域／逐run綁定

**現況：** api-registry.v1頂層鍵、run鍵皆封閉；`documents`是ref→DocumentPin映射，run只允許既有tracking_scope_ref選填鍵。不能直接在v1塞任意receipt_ref。

**條文草案／推薦方案：** 保留現行registry.v1結構，在受控`documents`登錄**每個scene_id／scene_revision恰一份、可列多run的receipt**，ref命名規則提議為`g4-approval:<scene_id>:<scene_revision>`。這是待採用的保留namespace，不是目前已可用的入口。啟動時由已驗index／graph的scene與revision決定唯一ref；不掃檔案目錄、不從request取ref、不選「最新」或第一個同類文件。receipt內run_camera_scopes及逐項run_ids是上限，不把某run核准擴到其他run；零份不啟用overlay，多份／矛盾為DataIntegrityError。DocumentPin照現有四欄綁定實際path、file SHA、schema_version及適用content pin。

**需要使用者決定：是，U8。選項：**

1. **DOCUMENTS_SCENE_BUNDLE（推薦）**：採單一scene/revision、多run、documents ref。優點：不暗改registry.v1鍵，可直接使用既有受控metadata store；缺點：同一scene下任一run核准變更都要重發整份receipt及其pin。
2. **REGISTRY_V2_PER_RUN**：registry明確升版，每個run新增有型別的receipt_ref，documents保存各receipt pin。優點：run可獨立更新及核准；缺點：API registry、loader、部署與驗收工具都要配對升版，舊v1不能默默接受新鍵。

**影響位置：** `api.py:449–491`、`store.py:DocumentPin／JsonRunStore`、部署registry。**#309參數：** A2兩值；synthetic registry須測未知run、重複ref／scope、request注入、缺ref，v1多鍵仍拒絕。

### A3 receipt bytes SHA與核准payload hash的發布鏈

**現況：** file SHA是完整回條bytes；decisions SHA是白名單payload，兩者不同。正式回條在使用者核准payload後才產生，不能假稱原核准已引用未存在的file SHA。

**條文草案／推薦方案：** 固定順序為：選定payload／hash→固定head複核→使用者checkpoint引用同一hash及精確條目→協調者D決策引用同一hash及該留言ID→產出含這兩個refs的正式receipt→算其file SHA。協調者在**同一checkpoint／D決策的後續發布紀錄**寫明三者對應：已核decisions SHA、正式receipt file SHA、將發布的registry file SHA／精確版本，並引用原核准及D決策。部署人員只把這份已核對的receipt pin放入同一受控server config，更新外部registry file pin。

發布紀錄在receipt定稿後產生，不回填進已定稿receipt形成自我hash循環；若refs或bytes再變，重新算file SHA並補發布紀錄，但payload不同一定重走使用者核定。loader離線驗bytes／payload自洽；「誰是人類／協調者、發布紀錄是否受授權」仍是D92-C流程審查，不能由同帳號login或hash自述證明。

**需要使用者決定：是，U8。選項：**

1. **COORDINATOR_PUBLICATION_BINDING（推薦）**：採後續發布對照紀錄，由協調者核對既有核准範圍。優點：避免循環hash，不另建第二套信任pin；缺點：離線loader不能自行證明人類授權，須保留發布審查紀錄。
2. **SECOND_HUMAN_BYTES_APPROVAL**：receipt產出後再請使用者引用其file SHA核定registry發布。優點：人類直接核對最終bytes；缺點：多一個核定步驟、refs修改後可能重複等待，仍需避免將第二次留言回填造成循環。

**影響位置：** 受控registry發布紀錄與`api.py`環境pin載入；不新增request授權入口。**#309參數：** A3兩值；須分清file SHA≠decisions SHA，測錯配、payload改值、僅refs改值及缺發布綁定的test-only上下文。機械測試不聲稱驗出真實人類身份。

### A4 核准refs的離線可驗範圍

**現況：** loader離線不能查證GitHub內文；只有兩個URL與receipt自稱hash，不證明兩份內文引用同一決定。

**條文草案／推薦方案：** `approval_ref`與`human_decision_ref`提議各帶固定URL／留言ID（D決策另有決策編號）、該留言**原始UTF-8內文**及其SHA-256；不做換行或Unicode正規化。loader驗內文bytes hash、URL／ID格式及D決策對使用者留言ID的引用，並確認兩份明確核准段落都引用收據重算出的同一decisions SHA；不靠寬鬆substring把建議、否定或待決文字當核准。核准段落的封閉表達／判讀規則仍須隨正式schema一併採用，無法機械判定就不產effective authority。

內文快照僅限authority驗證，不能送入LLM、語意檢索、candidate ranking或一般推論資料。沒有GT／私有劇本或路線內容可夾帶其中。內文hash只證明與受控bytes一致，**不證明人類身份或GitHub即時狀態**；A3受控發布與D92-C流程仍必要。資料矛盾沿DataIntegrityError；來源缺失沿既有未核准gate，不另創原因碼。

**需要使用者決定：是，U8。選項：**

1. **EMBEDDED_REF_TEXT_HASHES（推薦）**：採authority-only內文快照及hash。優點：離線能重算內容、核對同一hash與引用關係；缺點：receipt較大且要訂封閉核准表達，仍不能單靠hash證明作者。
2. **FORMAT_ONLY_PROCESS_TRUST**：loader只驗ref格式／固定ID與payload；由協調者在A3發布時人工確認內文。優點：格式最小、符合既有流程信任；缺點：離線程式無法重驗內文，必須明列這個未驗證界線，不可宣稱「兩份留言內容已由loader驗證」。

**影響位置：** 新receipt loader、JsonRunStore載入邊界與部署發布檢查。**#309參數：** A4兩值；第一案測內文hash／引用hash／留言ID不符及待決文字，第二案只測格式與test-only流程驗證標記，不偽造真核准。

### A5 當前input_pins的來源文件

**現況：** index manifest已有scene_id／revision／run_id，但沒有原source_sha256；兩圖分別有static／catalog content pin。不能說「從目前index即可驗原source SHA」，也不能為了驗pin開啟.blend或GT。

**條文草案／推薦方案：** 在受控documents另登錄既有`q-demo.r004-run-registration.v1`的每run宣告（目前repo的`configs/q1q5/runs/r004_*_v1.json`即含source_sha256／camera catalog SHA），lookup ref由已載入run_id決定並驗其file pin。原source SHA從該宣告取得，只驗已綁定的metadata，不開原資產。scene／revision／run_id須與index、兩圖、clock及declared run一致；source SHA須與所引用的靜態來源收據一致，缺任一可核來源就不授權。

來源對照：兩圖file SHA來自DocumentPin＋load_document_with_bytes原bytes；content SHA來自已驗canonical圖；tracking scope取原JSON bytes SHA；catalog取camera graph的catalog pin並與run註冊／D84來源綁定metadata交叉核對；static取region graph的scene_static_sha256並與已登錄靜態來源收據交叉核對；run camera scope取run註冊、index sampling.per_camera與scope的既有交集。receipt自稱值不能當驗自身的「當前來源」，不能只靠同字串而略過file pin或交叉引用。這些新增metadata載入亦是待實作，不冒稱api.py現已讀取。

**需要使用者決定：是，U8。選項：**

1. **PINNED_RUN_REGISTRATION（推薦）**：復用已有run registration及靜態來源收據，全部以受控documents pin載入。優點：不讀原資產、不發明第二套source宣告；缺點：目前RuntimeBindings沒有這些metadata，要明確增加來源傳遞與交叉檢查。
2. **DEDICATED_BINDINGS_DOCUMENT**：另定專用bindings metadata文件，集中所有當前source／run／catalog／static pins。優點：一次載入、資料位置明確；缺點：新增schema與重複宣告，必須防止和run／graph／index分歧，且採用前預設拒絕。

**影響位置：** `api.py:465–491`、RuntimeBindings、store的已驗metadata讀取；不改RGB／GT讀取範圍。**#309參數：** A5兩值；測缺source宣告、source／scene／run／camera不一致、bytes pin錯誤與拒絕開啟任何原資產locator。

## B effective視圖

### B1 圖、scope與G4的明確gate

**現況：** #260五鍵payload沒有欄位承載兩圖核准、scope核准與G4決定。單一transition的決定不能推定這四項都通過。

**條文草案／推薦方案：** 另提議下一版receipt／draft與**明列新canonical白名單**：保留原五鍵，再加`gate_decisions`與`contract_options`兩鍵。`gate_decisions`是按run_id排序的完整表，每列明列該run的region graph、camera graph、tracking scope與G4四個獨立決定；尚未選定時均是PENDING_USER／UNKNOWN，不能省略或由transition列填出。`contract_options`記錄11條已核選項ID；未選值不能產正式effective視圖。這是候選欄位與版本設計，**不是對現行v1直接加鍵**；正式schema名稱／版本、精確欄位型別與closed enum須隨U8採用紀錄凍結後實作，#309只參數化預期，不能當schema已存在。

只有當前run四個gate均明確核定、兩個可信refs及全部pins成立，且該run／操作用途與逐邊／逐轉移決定都成立，才導出該run的effective兩圖核准、scope核准及G4=true。其他run不跟著升權；任何gate未決維持DRAFT／PROPOSED／G4=false。新白名單及選項map全部進decisions SHA，舊五鍵hash、舊使用者留言或CQ-02待決hash不得覆用。

**需要使用者決定：是，U8。選項：**

1. **EXPLICIT_GATE_TABLE（推薦）**：採獨立逐run gate表與選項map、新receipt版本。優點：四個gate的來源明確、部分核准不擴大整圖；缺點：要升版、重算CQ-02草稿與核准payload。
2. **DERIVED_ALL_SCOPE_GATES**：不新增獨立gate決定欄，明定只有某run完整scope內的**全部**必要region／edge／transition／purpose均經明確核定且無待決，才可導出四個gate；選項／導出規則仍須版本化及綁定。優點：減少重複狀態；缺點：部分核准通常不能啟用，必須精確定義完整集合，不能把一條核准或空集合真值當成全部核准。若完整集合無法確定則維持未核。

**影響位置：** `graphs.py:GraphBundle.approval_status`、`_tracking_scope`、`candidates.py:69–78`、CQ-02 payload builder；新derived gate不得覆寫原圖。**#309參數：** B1兩值；測單transition核定但gate缺件仍不升權、逐run隔離、空集合、部分核定、缺選項map及新／舊payload hash不可混用。

### B2 path有效值與M1零邊

**現況：** loader以原圖最弱邊／任一UNKNOWN算path有效值；零邊effective authority目前UNKNOWN。relation與排名面積是靜態證據欄，不是核准選項。

**條文草案／推薦方案：** 非零邊effective path每次從該run、該用途可用的逐邊結果重算：任一TOPOLOGICAL_ONLY不得成候選；任一CLOSED不得成候選；其餘最弱traversability與任一state=UNKNOWN分別決定path_traversability與path_has_unknown_state。缺逐邊核定不把原圖的空真值或宣告值當證明。state=UNKNOWN與relation=UNKNOWN不混用，前者依既有排序規則可能為3，後者優先為4；不能改tier排序鍵。這只是有效值／排序的導出，**不繞過#260 §3.2的逐邊OPEN核准前提**；receipt沒有明確OPEN決定的路徑仍不開放。E_PORTAL_R102仍受既有TOPOLOGICAL_ONLY限制，核別邊或門指認不能解除。

M1的方向、來源出口、目的入口與CORR_W用途各自明列；核定一個方向不核另一個方向。推薦先保留零邊UNKNOWN／不入候選；即使某轉移列已選核定，也不能在沒有完整同區域authority定義及B1 gates時開放。兩案都不得因核准把relation改成OVERLAP或BLIND_GAP；原relation缺證據就UNKNOWN、ranking area仍null，維持tier4，不推定無碰撞。

**需要使用者決定：是，U8。選項：**

1. **CONSERVATIVE_ZERO_EDGE（推薦）**：非零邊按上式重算，零邊一律UNKNOWN／不入候選。優點：延續當前保守邊界、不需要假造walkability；缺點：M1及同類零邊重疊接手不能自動啟用，須另選第二案才可能開放。
2. **EXPLICIT_SAME_REGION_AUTHORITY**：在四個gate、該方向／出口／入口、CORR_W同區域且對應用途的明確核定全部成立時，另導出該方向的effective可用path；這是核准來源導出，不能由零條邊的空真值導出。提議在新版region_purpose_decisions為這個同區域用途另列traversability／state決定並納入新白名單：只有明確核定walkability及OPEN時，effective path_traversability才可為既有APPROVED_WALKABLE、path_has_unknown_state=false；state未知則保留true及不開放，CLOSED或TOPO則排除。relation保持原靜態值，不能因核定變成OVERLAP。優點：可支援有獨立核定的M1；缺點：要同時採用這些候選欄位／型別／hash規則，U8未補定完整前仍UNKNOWN、不開放。

**影響位置：** `graphs.py:157–161,262–270`、`candidates.py:59,69–78`。**#309參數：** B2兩值；測最弱邊、CLOSED、UNKNOWN tier、M1兩方向隔離、用途缺件、relation不被核准竄改及R102固定排除。

### B3 purposes與範圍上限

**現況：** allowed_purposes沒有封閉詞彙，不能由實作者自創token後默認啟用。run/index與tracking_scope已是§5.4上限。

**條文草案／推薦方案：** 提議待採用的封閉操作用途為`Q1_REGION_FILTER`、`Q2_TRACKING`、`Q5_AUTO_SWITCH`。純camera Q1查找不因本提案新增receipt前置；只有需要圖的region過濾才映射第一個用途。Q2 seed／局部追蹤映射第二個，自動候選／切鏡還要第三個。Q3只解析不讀receipt、不因文字自行授權；形成子請求時再按Q1／Q2／Q5操作檢查。Q4只讀已在合法scope內的證據，不因本用途表擴大輸入。

用途與camera／run集合只能取交集，不得放大既有run註冊、index sampling.per_camera或scope。Q1上限為run/index∩query_camera_ids；Q2／Q5為run/index∩tracking_camera_ids，query_only_camera_ids先排除，CAM_ENTRY仍只Q1。先完成原有完整scope與出口檢查，不能靠receipt刪掉缺出口鏡頭迴避EXIT_ZONES_MISSING。方向須是scope.directed_pairs允許且原圖已存在的transition；receipt不能新增camera／edge／transition／ROI、解除D77排除或推定其他run可用。R101用途獨立於門邊核定；用途未知／未選是空授予集合。

**需要使用者決定：是，U8。選項：**

1. **CLOSED_OPERATION_PURPOSES（推薦）**：採上述三個候選token及操作映射。優點：Q1圖過濾、追蹤與切鏡授權可區分；缺點：新enum及各consumer映射須配對採用，現行產品不得先接受。
2. **SINGLE_TRACKING_PURPOSE**：提議單一`Q2_Q5_TRACKING`用途覆蓋追蹤與切鏡，Q1沿現行圖用途gate。優點：表格較小；缺點：不能單獨限制追蹤／切鏡，R101仍需另列該用途的region核定，不能以單一token跳過scope／方向／gate。

**影響位置：** `api.py`run綁定、`q1_search.py:86`之後圖使用、controller的scope／seed／candidate入口、`candidates.py`allowed_camera_ids。**#309參數：** B3兩值；purpose token由test-only contract資料讀取，未核前不得硬寫成產品enum。測CAM_ENTRY、跨run、未知purpose、scope排除方向及刪鏡頭掩蓋缺出口。

## C 重載與provenance

### C1 overlay掛點與registry重載

**現況：** API啟動載一次圖，controller的`_collect_blocking_reasons`及`_prepare`又由RuntimeBindings.graphs原bytes重新load_graphs，單次wrapper會遺失overlay。

**條文草案／推薦方案：** 實作位置建議為新的`src/amidst/q1q5/receipt_overlay.py`與RuntimeBindings保存的immutable receipt binding；這是位置建議，函式／參數名未核定，不作已存在API。binding保留受控registry generation/file pin、receipt原bytes／file SHA、decisions SHA、已驗來源pins與已核選項。每次load_graphs先驗原圖／scope，再以同一binding重新驗receipt／hash／範圍並建新的run／purpose有效視圖。驗證是純已載入metadata操作，不掃目錄、不抓GitHub、不讀媒體或劇本。

同一session固定同一generation與兩個receipt hashes。registry有合法新版本時只供新API generation／新session，不把舊session悄悄切到新核准；若舊binding所指bytes在重驗時變動或與pin矛盾，DataIntegrityError停止。不得把設定變更偽稱USER_STOPPED；既有journal保留原bytes，不續寫新generation的成功決定。缺receipt仍走既有未核gate，壞pin不降為一般PARTIAL繼續切鏡。

**需要使用者決定：是，U8。選項：**

1. **IMMUTABLE_REVALIDATED_BINDING（推薦）**：session凍結immutable binding，每次圖重載重驗。優點：現有多處load_graphs不會遺失overlay，變動立即被攔；缺點：重複metadata驗證有成本，所有重載call sites都要傳遞binding。
2. **ATOMIC_GENERATION_RELOAD**：整份registry一次驗完後建immutable generation，重載只接受該generation的已驗binding；新generation原子替換只影響新session。優點：驗證可集中且少重做；缺點：須證明物件不可變與generation相符，舊generation資源缺失仍必須fail closed，不能就地換pins。

**影響位置：** `api.py:477–491`、RuntimeBindings、`q5_controller.py:140,269`與Q1使用圖的入口。**#309參數：** C1兩值；目前沒有實作時測試用TEST-ONLY driver seam／環境參數指定介面，缺實作可importorskip但AMIDST_REQUIRE_IMPL=1必fail，不把seam宣稱production契約。測重載前後authority一致、mid-reload bytes變動、跨generation與新session分離。

### C2 response、journal與session綁定版本

**現況：** I3/#278 v2只加time_range_source，沒有receipt兩個hash；現有closed scope／decision input_pins／session hash無法區分不同核准。

**條文草案／推薦方案：** 另提議Q1／Q2／Q3 response的下一版（候選v3）、decision journal下一版（候選v2），在新版本的resolved_scope與decision input_pins中**各以兩個明確nullable hash欄位**綁receipt file SHA及decisions SHA（候選名稱`g4_receipt_file_sha256`／`g4_decisions_sha256`）。只有該新schema已核、consumer／kit與#309配對完成才可產新wire；不能往I3 v2或舊journal偷偷加鍵。未使用receipt的路徑寫null，不能偽造「核准」，也不能把null當可切鏡。

新session_id的hash成分及controller輸入provenance含這兩個hash、run／purpose與binding版本；不同核准內容或receipt bytes必須是不同session lineage。output hash自然包含新scope欄；D80的query preimage／query_sha256不變。link-record.v2可保持原wire，前提是每列仍帶該新session_id且整份links bytes SHA由新response綁定；若將來要在link列直接加receipt鍵，必須另升link版本，不回填舊列。

舊錄製保留原schema／bytes／hash，缺receipt不補null鍵、不重算舊ID。來源外部註明其authority未由新介面重驗；是否可只讀展示由C3決定，不能以舊錄製開放live authority。#278與#305仍成對合併，這個另案升版不能把兩者既有v2改造成含receipt的新格式。

**需要使用者決定：是，U8。選項：**

1. **VERSIONED_INLINE_PROVENANCE（推薦）**：採另升版scope／journal與新session綁定。優點：wire自身有完整來源、replay可直接驗pin；缺點：要更新schema／registry／consumer／kit／錄製，採用前功能預設關閉。
2. **PINNED_EXTERNAL_PROVENANCE**：保持response v2／現journal欄位，另以受控pin的外部session authority紀錄綁output／journal／snapshot及兩個receipt hashes，session lineage仍必須區分。優點：既有consumer較少改動；缺點：多檔一致性及缺sidecar的失敗模式更複雜，不能把只有舊response的replay當成authority已驗證；新sidecar schema仍須核定。

**影響位置：** `q5_controller.py:126,129,416,719`、`q1_search.py:86`、`q3_parse.py:115`、版本schemas／consumer／kit。**#309參數：** C2兩值；test-only contract資料提供候選欄位路徑，未核定不硬編進產品schema。測兩hash均綁定、只改核准就改session/output lineage、D80 query不變、舊錄製bytes不變及禁止v2偷加鍵。

### C3 candidate hash與缺receipt replay

**現況：** 候選集受effective authority影響，原snapshot只hash自身欄位；D80 query hash和原graph hash都不應拿來代替receipt binding。

**條文草案／推薦方案：** 新版candidate snapshot（候選v2）明列receipt file SHA與decisions SHA，兩者都進candidate_snapshot_sha256 preimage；candidate refs由該新digest導出。即使候選名單相同，只換核准內容也不共用snapshot／evidence cache。C2的新decision／response pin綁定同一snapshot及receipt；不改D80 query或原graph hashes。

凡新格式錄製宣告使用receipt，replay必須取得相同受控receipt bytes並驗同一payload、來源與選項；缺件、hash錯、scope變更均拒絕該authority replay，不借用目前較新的receipt、不降級後重算一份看似相同候選。hash或交叉引用矛盾用DataIntegrityError；缺核准不能產新切鏡結果。**以下兩案都不允許缺receipt時恢復或重算已核authority。**

**需要使用者決定：是，U8。選項：**

1. **PINNED_FAIL_CLOSED（推薦）**：新錄製與需要effective authority的replay一律要求原receipt，缺件就失敗。優點：來源最清楚，不把降級當相同重播；缺點：攜帶包必須包含允許的安全receipt metadata及完整pins，缺件不能重播此段authority流程。
2. **LEGACY_READ_ONLY_NO_OVERLAY**：新錄製同第一案；只允許明確的舊格式錄製以原bytes／hash做只讀展示，外部標示未具新receipt binding，不能重跑candidate、controller或取得live authority。優點：保留既有deterministic錄製展示；缺點：舊展示與新authority replay要分開，不能稱舊格式已通過新綁定驗收或把提示回寫原檔。

**影響位置：** `candidates.py`snapshot hash／candidate refs、recording store與RecordedProvider、controller的journal／cache輸入。**#309參數：** `contract_option("C3", "PINNED_FAIL_CLOSED")`或`LEGACY_READ_ONLY_NO_OVERLAY`；兩案都測新格式缺receipt不能重算、錯pin／換receipt拒絕，第二案另測舊bytes只讀且不呼叫live provider／candidate builder。

## contract_option對照與採用順序

下列ID只供 #309 **TEST-ONLY 參數／marker**。預設選定值一律`UNSELECTED`，不是registry鍵、schema enum或正式核准值。推薦欄不得當預設啟用；未知ID、未選、未經U8核定的組合都不能開放overlay。正式採用後，選定profile還須依B1／A1的版本化hash規則綁定，不能只靠本機環境變數宣告使用者已核。

| 組 | 推薦候選值 | 另一候選值 | 目前選定值 |
| --- | --- | --- | --- |
| A1 | TOP_LEVEL_FIELDS | HEADER_OBJECT | UNSELECTED |
| A2 | DOCUMENTS_SCENE_BUNDLE | REGISTRY_V2_PER_RUN | UNSELECTED |
| A3 | COORDINATOR_PUBLICATION_BINDING | SECOND_HUMAN_BYTES_APPROVAL | UNSELECTED |
| A4 | EMBEDDED_REF_TEXT_HASHES | FORMAT_ONLY_PROCESS_TRUST | UNSELECTED |
| A5 | PINNED_RUN_REGISTRATION | DEDICATED_BINDINGS_DOCUMENT | UNSELECTED |
| B1 | EXPLICIT_GATE_TABLE | DERIVED_ALL_SCOPE_GATES | UNSELECTED |
| B2 | CONSERVATIVE_ZERO_EDGE | EXPLICIT_SAME_REGION_AUTHORITY | UNSELECTED |
| B3 | CLOSED_OPERATION_PURPOSES | SINGLE_TRACKING_PURPOSE | UNSELECTED |
| C1 | IMMUTABLE_REVALIDATED_BINDING | ATOMIC_GENERATION_RELOAD | UNSELECTED |
| C2 | VERSIONED_INLINE_PROVENANCE | PINNED_EXTERNAL_PROVENANCE | UNSELECTED |
| C3 | PINNED_FAIL_CLOSED | LEGACY_READ_ONLY_NO_OVERLAY | UNSELECTED |

組合限制也待U8採用：A1的header位置、B1的payload版本、A4的refs形狀、A5的當前來源、C2／C3的版本與hash欄位必須成套，不能各挑一個後仍用舊五鍵hash。B2第二案若缺同區域決定的完整欄位／state規則，不因其ID被勾選就開放M1。B3未知purpose或C1未知generation維持fail closed。

建議落實次序：U8逐條或成套核定→固定採用文件／選項與schema版本／hash白名單→CQ-02重建選定payload與待核hash→使用者實際G4及發布綁定→CQ-21 adapter／consumer／kit配對實作與#309嚴格驗收。**合成adapter測試不需真實G4，但合成核准不授權正式資料。** 若U8只核A組與C3，B組保持未選，demo重疊對不開放authority，符合#279的保守選項。

## 已知差異、驗證與未驗證

- P3-B：A1已把四欄位置／型別與loader重算列為草案，沒有修改#260的欄位表。
- P3-A：`q1q5_conformance.py:1558–1566`的TOPOLOGICAL_ONLY_EDGE要求與主契約GRAPH_NOT_APPROVED優先存在既有不一致。本提案沿主契約優先序：先graph/scope未核，再零邊宣告TOPO、其餘零邊未核，最後非零TOPO；不在文件交件改kit或以豁免冒充符合性PASS。
- 本文件只做條文完整性、來源refs／hash與相稱diff檢查；不執行adapter、registry重載、schema驗證、模型、render、錄製或正式G4。所有程式位置為固定head的閱讀結果，未宣稱新行為已實作。
- ARCH守門NOT_RUN：#307尚未交付，權威pin與指定staging PASS衝突已另提[偏離提案](https://github.com/Polalalabear/amidst/issues/307#issuecomment-6484266639)。本文件不處理或繞過該阻擋。
- 不以#260的PASS_WITH_NOTES、本文Draft PR、#309合成fixture或D97允許疊層，取代U8、真實G4、正式schema採用、Claude複審、合併或研究接受。
