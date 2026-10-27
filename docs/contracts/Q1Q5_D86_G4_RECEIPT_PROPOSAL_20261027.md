# D86 Q3 與可信 G4 收據介面提案

2026-10-27。C4。**D92 的 A／B／C 已由使用者決定；其餘 G4 receipt 格式為 PROPOSED／待 Claude 複核；本 PR 不核 G4、不改 yyin 已交題目。空 edge_path 的 authority guard 已實作，完整 receipt loader 未實作。**D86第1、2項的產品行為已由使用者選定，A／B／C 已依 D92 定案；G4 receipt 的完整欄位、逐邊值與 ingestion 仍是提案。D65數值、D73原因全序、D78兩段journal、D81追蹤鏡頭範圍及D89長度保持。

## 1. Q3口語追蹤（D86-1）

第一版以有版本/hash的封閉規則為baseline，LLM_WITH_RULE_FALLBACK路徑保留。請原owner複核下列文法，再改q3_rules／closed aliases／tests／指南；不是直接把所有關鍵字substring都當追蹤。

| 文字型態 | 提議解析 | 邊界 |
| --- | --- | --- |
| 跟著〈人／外觀條件〉、追蹤〈人／外觀條件〉 | FIND_PERSON → Q2 appearance seed | 類別person；服色只從封閉表解析，仍需真實觀測選seed |
| 〈那個人／紅色的人／封閉person條件〉去了哪裡 | FIND_PERSON → Q2 appearance seed | 「那個」不是身分指代成功，不能填GT／actor／上一人的observation ID |
| 紅色的人 | person＋red外觀條件，依完整句的查找／追蹤語法分Q1或Q2 | D92-A 已核定：要有追蹤動詞才判 Q2，單獨外觀詞／那個人依查找規則判 Q1；D86-1 以此補註為準 |
| 哪些鏡頭拍到〈條件〉 | FIND_CAMERAS → Q1 | 不因別處出現「人」而當追蹤 |
| 同句有互斥完整找／追指令、開放詞、跟著車 | NEEDS_CLARIFICATION或既有UNSUPPORTED_CONDITION | 不靠LLM偷偷改意圖、不把車轉成person |

規則沿用§14-9(a)中介輸出，再由同一validator形成Q1/Q2。新語法固定rule version/hash與closed aliases hash，舊錄製原樣重播；新增例句是工程語法測試，不當人工正式題／答案。Q3回應v1目前沒有頂層intent，前端可從 PARSED 的 `structured_query.schema_version` 派生「實際執行的 request 是找／追」並標示來源；這不是解析 intent 的穩定欄位，NEEDS_CLARIFICATION 的 structured_query=null，以及 FIND_PERSON 帶不支援限制而未形成 Q2 時，均不能從此推得解析意圖；本提案不增加第二個可能矛盾的intent欄位。

## 2. 缺時間時查整段已選run（D86-2）

只在 request 的 run 範圍恰為使用者已選定的一個 run_id，且該 run 的 clock 已驗 scope/hash、duration/t0 有效時啟用；伺服器可同時註冊多個 run，不以全站只有一個 run 為條件。自然語句**完全沒有時間字面值**時，產生SOURCE時間`[0,source_duration_us)`；t0_us 是牆鐘對應的來源錨點，不是來源起點；現行 t0=0，所以A4為[0,50000000)、B4為[0,42000000)。這是D86整run預設，與D89情境卡手動Q2的[0,48)/[0,40)範圍不同，不能互相替代。

- 句子已有完整合法時間：照明示時間處理，不覆寫成整run。
- 有部分時間、無效時間、含「現在」等未支援表達：沿既有明確失敗／反問，不把解析失敗當完全沒時間。
- 無選定run、多run、缺mapping：NEEDS_CLARIFICATION，沿既有MULTI_RUN_SCOPE_UNRESOLVED／CLOCK_MAPPING_MISSING，不猜日期或拼run。
- clock存在但pin／scope錯：integrity error，不回預設成功。

**D92-B 已採用 wire：** Q1／Q2／Q3 response 升 v2，共用 resolved_scope 只新增一個必填、nullable 的 `time_range_source`，不改 v1 strict schema 或舊錄製。封閉值為 `EXPLICIT_SOURCE | EXPLICIT_WALL | DEFAULT_SELECTED_RUN | null`；只有尚未成功形成 requested_time 時為 null；合法但 OUT_OF_RANGE 的明示時間仍保留 EXPLICIT 來源。直接 Q1／Q2 request 仍須有明確範圍，沒有可信 parse receipt 不偽稱 DEFAULT_SELECTED_RUN。

```json
{
  "time_range_source": "DEFAULT_SELECTED_RUN"
}
```

不另外設重複的 time_range_reason；DEFAULT_SELECTED_RUN 本身足以標示預設原因，不加入阻擋 reasons[]。成功 PARSED 仍 reason=null／reasons=[]；requested_time 寫真正 SOURCE 範圍，resolved_source_ranges_us 由同一 clock resolver 取得。**D92-B 維持 D80 preimage 原樣** `{request:N(9鍵),bindings:{index,aliases,parameters,clock}}`，不暗加 time_range_source；來源只進 output hash／parse receipt，領域條件相同就保持相同 query lineage。schema/kit/consumer 必須同步支援明確 v2；新產出不能冒用 v1。

D92 補決定採用上述 v2／單鍵／不改 D80 的方案；原 v1 加兩鍵或更改 preimage 的方案撤回。v1 錄製只以原始 bytes／hash 重播，不回填新鍵。產品與新 schema 的細節見 [I3固定head文件](https://github.com/Polalalabear/amidst/blob/3664e2f55e0c05e64052ce94818d83b3c4700c13/docs/contracts/Q1Q5_RESPONSE_V2_D92_20261027.md)（I3 另案）。

UI在執行前後顯示「使用整段已選run範圍」與來源/牆鐘界線；不寫「現在」，不把預設範圍改稱觀測涵蓋完整。PARSED仍可能下游PARTIAL／NO_MATCH。指南新增缺時間題型說明，但保留舊人工題目bytes、來源CSV/hash與已回收答案，不回填或重寫。正式評分題必須明寫核定時間，不能走整段預設；yyin 已交題目是否含缺時間反問題與適用評分版本目前 UNKNOWN，採用前由評估 owner 核對，舊題 bytes 不改。

遷移順序：此提案複核→契約採用文字與schema/kit對齊→Q3規則/adapter/closed aliases和focused tests→新產品重錄／前端核對→新版本指南。建議測試涵蓋單run缺時間、完整／部分／無效字面時間、無run/多run/缺clock/壞pin、未知詞、解析模式一致與output hash可重現。

## 3. 可信 G4 收據（格式尚未採用）

目前§5.1已要求可信使用者核准來源，graph/scope自己寫APPROVED/true不授權。**GitHub留言作者login也不夠**：同帳號的agent可貼留言，不能以agent自己的「已核准」證明人類核定。

D92-C 已採用信任來源：**checkpoint issue 的使用者核准留言＋協調者記錄的 D 決策**，與其他 D 決策同一標準。兩個 reference 都必須指向當前 source／圖／scope 的實際核定，不能用 producer 自寫 APPROVED／G4=true 取代。這是流程信任，不能由同帳號 login 證明人類身分；收據bytes pin放在與兩圖／scope pin相同的受控server config，不另要求第二套外部trusted-pin檔或簽章。

收據格式仍提議為獨立 `q-demo.g4-approval-receipt.v1`，保存 checkpoint approval comment URL／ID、coordinator D decision URL／編號、固定輸入 bytes pins 與衍生清單；受控 server config 綁定內容後才能載入，不接受 request 自帶 path/hash 升權。沒有實際核准時，不產 APPROVED 收據。本次只修正零邊 path 的保守處理，不實作完整 receipt ingestion。

### 3.1 核准內容hash、草稿與正式狀態

草稿使用 `q-demo.g4-approval-receipt-draft.v1`，status=PROPOSED；不得冒用正式
`q-demo.g4-approval-receipt.v1`。未決欄位一律PENDING_USER或UNKNOWN，不省略、不預先當核准。
每列分列 `recommendation`（建議）、`decision`（實際決定）、`yyin_opinion`（審查意見及來源）；
建議與yyin的T都不能代填decision。無對應意見寫MISSING。

固定canonical payload只有五個鍵：`input_pins`、`edge_decisions`、`transition_decisions`、
`region_purpose_decisions`、`derived_legal_transitions_by_run`。input_pins包含source/catalog/static、兩圖file/content、
scope bytes、run/camera scope；每項決定包含精確ID、方向、來源出口／目標入口、用途及選定值。
重建payload時，各表只取下列明列鍵（建議、yyin意見、來源refs放旁欄，不混進決定值）：
- input_pins：scene_id、scene_revision、source_sha256、catalog_sha256、static_sha256、region_graph_file_sha256、region_graph_content_sha256、camera_graph_file_sha256、camera_graph_content_sha256、tracking_scope_file_sha256，以及run_camera_scopes（run_id、camera_ids、allowed_purposes、exclusions）。
- edge_decisions：edge_id、traversability、state、run_ids、allowed_purposes。
- transition_decisions：transition_id、from_camera_id、to_camera_id、via_exit_zone_ids、to_entry_zone_ids、region_path、edge_path、run_ids、decision、allowed_purposes。
- region_purpose_decisions：region_id、run_ids、decision、allowed_purposes、exclusions。
- derived_legal_transitions_by_run：run_id、transition_ids。這些欄位全部存在，null／UNKNOWN／PENDING_USER亦照原值進hash；不得刪未決欄讓hash看似完整。schema實作前這些名稱是本提案的明確候選格式，不是已採用wire。

表格順序必固定：edge_id、transition_id、region_id、run_id依字典序；每列欄位與陣列不得省略，空集合明寫[]。

`decisions_sha256 = SHA-256(UTF-8(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)))`，
不含尾端換行。ref欄位（approval_ref、human_decision_ref、independent_review_ref等）、recommendation、yyin_opinion、
status/date/provenance與decisions_sha256自身都不進payload。不能用遞迴猜哪些欄位要排除；由上述白名單重建payload。
核准的每一個值及固定輸入pins都必須進hash；只排除來源ref，不排除用途／scope／derived清單。

順序固定：草稿／算hash → Claude固定head複核 → 協調者開checkpoint → 使用者核准留言引用同一decisions_sha256
（及精確條目）→ 協調者D決策引用同一hash與該留言ID → 才產正式收據與ref → 受控server config綁正式收據bytes。
未決payload的核准不會開放未決項。若使用者改值或只核部分，須先重建完整選定payload／新hash並獨立複核，
再由使用者明確引用新hash核定；不能把舊hash的「核准」或勾選解讀成未綁定的新值。
正式收據重新計算同一payload hash，必須同時等於核准留言及D決策所引用者；refs回填不改這個hash。
JSON／source pin矛盾、缺ref／hash、未決項不得升權，整份資料不得自宣告人類核准。

### 3.2 G4生效與CQ-21依賴

收據不是當前loader輸入。D96選擇不改frozen graph bytes，後續CQ-21由受控config讀已核正式回條，
驗證decisions_sha256／兩個可信refs與所有pins後，另建runtime effective authority／purpose／approval視圖。
兩圖、scope的核准狀態及G4_approved都須在有效視圖上有可信依據，逐邊OPEN／walkability、用途、逐轉移核准均成立，
才開放對應run候選；原graph宣告不覆寫、不改hash。這個adapter尚未實作，本PR不新增入口或解除任何guard。
CQ-21以前：零邊一律排除；非零邊仍受原圖／scope與edge核准檢查。F4c的A4 4列、B4 12列只是核准影響清單，
不是現在已開放候選；只有回條或使用者留言，沒有完整effective gate，也不能切鏡。

收據至少包含：

| 欄位 | 提議規則 |
| --- | --- |
| source／catalog／static／兩圖／tracking scope | scene_id/revision、原source SHA、catalog SHA、static SHA、兩圖file與content SHA、scope原始bytes SHA；全部須與當前輸入一致 |
| approval_ref／human_decision_ref | 實際使用者核定的 checkpoint issue 留言＋協調者 D 決策，各列 URL/ID；不能只引用 agent 產出紀錄 |
| independent_review_ref | Claude固定head複核與僅核定欄位diff檢查，記實際文件/hash，不是人類核准替代物 |
| edge_decisions[] | E_OUT_VEST、E_VEST_CORR、E_W_CORNER、E_PORTAL_R101、E_CORNER_N各自traversability/state；E_PORTAL_R102維持TOPOLOGICAL_ONLY，沒有核定的用途不升權 |
| transition_decisions[] | M1 兩方向逐條列 APPROVED／NOT_APPROVED／UNKNOWN；後兩者分別代表明確不核准及尚未決定，均不能讓空 edge_path 升為 APPROVED_WALKABLE，也不得成為自動候選。列來源出口、目標入口及 CORR_W 同區域 authority；loader 已將零邊 path 的 effective authority 設為 UNKNOWN，candidate 排除；原始 graph JSON／hash 保留。完整的逐轉移核准 ingest 仍為提案，故即使自行宣告 APPROVED 也不開放零邊轉移 |
| region_purpose_decisions[] | R101 必列 region_id 與 allowed_purposes／exclusions，E_PORTAL_R101 通行核准不能代替 R101 用途核准；未核准用途維持 UNKNOWN |
| derived_legal_transitions_by_run[] | 每個 run 列實際開放的 transition_id、來源／目的、edge_path、核定用途和來源決定；逐邊核准對應哪些候選必須可重算，清單進收據 hash |
| approved_purposes／exclusions | 精確r004用途與鏡頭／run邊界；CAM_ENTRY只Q1、D77四方向仍排除；不承接Line2 v4的D90決策 |
| status／date／provenance | 提案／使用者核定的狀態分開；未有真實核定時不能填APPROVED或偽造核准時間 |

收據內容及核准依據只使用靜態幾何／校正／圖；不得讀 GT、renderer 軌跡、visibility、depth、劇本 t_N／t_X。

loader提議行為：缺 checkpoint 核准留言／協調者 D 決策／核定前置→保留GRAPH_NOT_APPROVED／工程PARTIAL；收據bytes pin不符、來源或條目矛盾→DataIntegrityError，停止自動切鏡。存在收據本身不證明實體安全／通行全域正確。凍結／G4／渲染順序不變；D84 camera catalog凍結與G4脫鉤。採用前應先審 checkpoint／D 決策對應、M1 及逐邊值；新增缺／錯 pin、NOT_APPROVED／UNKNOWN M1、R101 未核用途、逐 run 衍生清單不符的 focused tests，不能把此格式提案當已有可信 receipt。

## 歷史交件紀錄（CQ-16未重跑此段舊結果）

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: 延續 #260，追加 commit 的精確 SHA 見 PR。
- Files changed: 本文件、主契約、graphs.py／candidates.py、test_graphs.py／test_candidates.py／test_q1_search.py／test_empty_path_authority.py。
- Commands run and results: `uv run --no-project --offline --no-cache --python <EXISTING_PYTHON> python -m pytest -o addopts='' -q -p no:cacheprovider tests/q1q5/test_graphs.py tests/q1q5/test_candidates.py tests/q1q5/test_empty_path_authority.py tests/q1q5/test_q1_search.py` → 125 PASS；契約 JSON blocks／diff／lint 檢查見 PR。
- Artifacts: code/docs/tests；沒有實際 G4 收據，frozen graph bytes／hash 不變。
- Verified: D92 A/B/C 的條文、F4/F6–F10；空 edge_path 的 effective authority=UNKNOWN 且候選排除，不因圖或 G4 布林升權。
- Not verified: 完整 receipt ingestion、實際 checkpoint／逐邊／用途／M1 核准；I3 schema/runtime/browser 另案，正式題評分版本由 owner 核對。
- Deviations, UNKNOWN items and follow-ups: 保留原圖的宣告欄位供 provenance，effective authority 另列而不重寫其 hash；零邊核准 adapter 尚未存在，目前零邊均不自動開放。

## D92 與本次審查回修

回覆 #260 F1–F8：版本建議 v2／單鍵，D80 preimage 不改；selected run 定義、實際 request 與解析 intent 差別、正式題明示時間、R101 用途、M1 三態、逐 run 候選清單與 GT 排除已補。語法範圍、v2／單鍵／D80 與 checkpoint＋D 決策的信任來源已由 D92 核定；其餘 receipt 欄位／實際逐邊值仍為提案，不構成 G4。F9/F10 在主契約修正，只收緊例子文字與既有 kit 一致，不改產品行為。


## F4c：逐 run／逐邊將開放的 transition 清單（僅核准影響，不是核准）

來源為 frozen graph v3 `camera_graph_v3.json`；當前 DRAFT／G4=false，現行正式合法候選清單為空。
下列是若所列 edge_path 全部取得該 run 的 traversability/state 與用途核准時的導出影響；
同一條邊可能同時開放多條轉移。R101 的 allowed_purposes 必須另有對應核准。
M1 兩個空 edge_path 不列入；NOT_APPROVED 與 UNKNOWN 均排除，APPROVED 亦須等待可信逐轉移 adapter，不能只靠 JSON 布林。

| run | transition_id | 必要 edge_path |
| --- | --- | --- |
| A4 | `T_CAM_EXT_CAR__CAM_W1` | `E_OUT_VEST, E_VEST_CORR` |
| A4 | `T_CAM_EXT_CLEAR__CAM_W1` | `E_OUT_VEST, E_VEST_CORR` |
| A4 | `T_CAM_W1__CAM_EXT_CAR` | `E_VEST_CORR, E_OUT_VEST` |
| A4 | `T_CAM_W1__CAM_EXT_CLEAR` | `E_VEST_CORR, E_OUT_VEST` |
| B4 | `T_CAM_BRANCH__CAM_W1` | `E_W_CORNER` |
| B4 | `T_CAM_BRANCH__CAM_W2` | `E_W_CORNER` |
| B4 | `T_CAM_R101_IN__CAM_W1` | `E_PORTAL_R101` |
| B4 | `T_CAM_R101_IN__CAM_W2` | `E_PORTAL_R101` |
| B4 | `T_CAM_W1__CAM_BRANCH` | `E_W_CORNER` |
| B4 | `T_CAM_W1__CAM_R101_IN` | `E_PORTAL_R101` |
| B4 | `T_CAM_W1__CAM_WIDE` | `E_W_CORNER` |
| B4 | `T_CAM_W2__CAM_BRANCH` | `E_W_CORNER` |
| B4 | `T_CAM_W2__CAM_R101_IN` | `E_PORTAL_R101` |
| B4 | `T_CAM_W2__CAM_WIDE` | `E_W_CORNER` |
| B4 | `T_CAM_WIDE__CAM_W1` | `E_W_CORNER` |
| B4 | `T_CAM_WIDE__CAM_W2` | `E_W_CORNER` |
