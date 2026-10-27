# D86 Q3 與可信 G4 收據介面提案

2026-10-27。C4。**PROPOSED／待Claude複核；只提介面，不實作產品、不核G4、不改yyin已交題目。**D86第1、2項的產品行為已由使用者選定，這裡待確認的是語法、wire欄位、原因碼與遷移方案；G4 receipt格式則仍是提案。D65數值、D73原因全序、D78兩段journal、D81追蹤鏡頭範圍及D89長度保持。

## 1. Q3口語追蹤（D86-1）

第一版以有版本/hash的封閉規則為baseline，LLM_WITH_RULE_FALLBACK路徑保留。請原owner複核下列文法，再改q3_rules／closed aliases／tests／指南；不是直接把所有關鍵字substring都當追蹤。

| 文字型態 | 提議解析 | 邊界 |
| --- | --- | --- |
| 跟著〈人／外觀條件〉、追蹤〈人／外觀條件〉 | FIND_PERSON → Q2 appearance seed | 類別person；服色只從封閉表解析，仍需真實觀測選seed |
| 〈那個人／紅色的人／封閉person條件〉去了哪裡 | FIND_PERSON → Q2 appearance seed | 「那個」不是身分指代成功，不能填GT／actor／上一人的observation ID |
| 紅色的人 | person＋red外觀條件，依完整句的查找／追蹤語法分Q1或Q2 | 待使用者確認 D86-1 字面範圍；建議要追蹤動詞才判 Q2，其餘沿原查找規則，本列不視為已採用 |
| 哪些鏡頭拍到〈條件〉 | FIND_CAMERAS → Q1 | 不因別處出現「人」而當追蹤 |
| 同句有互斥完整找／追指令、開放詞、跟著車 | NEEDS_CLARIFICATION或既有UNSUPPORTED_CONDITION | 不靠LLM偷偷改意圖、不把車轉成person |

規則沿用§14-9(a)中介輸出，再由同一validator形成Q1/Q2。新語法固定rule version/hash與closed aliases hash，舊錄製原樣重播；新增例句是工程語法測試，不當人工正式題／答案。Q3回應v1目前沒有頂層intent，前端可從 PARSED 的 `structured_query.schema_version` 派生「實際執行的 request 是找／追」並標示來源；這不是解析 intent 的穩定欄位，NEEDS_CLARIFICATION 的 structured_query=null，以及 FIND_PERSON 帶不支援限制而未形成 Q2 時，均不能從此推得解析意圖；本提案不增加第二個可能矛盾的intent欄位。

## 2. 缺時間時查整段已選run（D86-2）

只在 request 的 run 範圍恰為使用者已選定的一個 run_id，且該 run 的 clock 已驗 scope/hash、duration/t0 有效時啟用；伺服器可同時註冊多個 run，不以全站只有一個 run 為條件。自然語句**完全沒有時間字面值**時，產生SOURCE時間`[t0_us,t0_us + source_duration_us)`；現行t0=0，所以A4為[0,50000000)、B4為[0,42000000)。這是D86整run預設，與D89情境卡手動Q2的[0,48)/[0,40)範圍不同，不能互相替代。

- 句子已有完整合法時間：照明示時間處理，不覆寫成整run。
- 有部分時間、無效時間、含「現在」等未支援表達：沿既有明確失敗／反問，不把解析失敗當完全沒時間。
- 無選定run、多run、缺mapping：NEEDS_CLARIFICATION，沿既有MULTI_RUN_SCOPE_UNRESOLVED／CLOCK_MAPPING_MISSING，不猜日期或拼run。
- clock存在但pin／scope錯：integrity error，不回預設成功。

**提議 wire（待使用者選版，未採用）：**建議 Q1／Q2／Q3 response 升 v2，共用 resolved_scope 只新增一個必填、nullable 的 `time_range_source`，不改 v1 strict schema 或舊錄製。封閉值為 `EXPLICIT_SOURCE | EXPLICIT_WALL | DEFAULT_SELECTED_RUN | null`；僅在沒有產生有效時間範圍時為 null。直接 Q1／Q2 request 仍須有明確範圍，沒有可信 parse receipt 不偽稱 DEFAULT_SELECTED_RUN。

```json
{
  "time_range_source": "DEFAULT_SELECTED_RUN"
}
```

不另外設重複的 time_range_reason；DEFAULT_SELECTED_RUN 本身足以標示預設原因，不加入阻擋 reasons[]。成功 PARSED 仍 reason=null／reasons=[]；requested_time 寫真正 SOURCE 範圍，resolved_source_ranges_us 由同一 clock resolver 取得。**建議維持 D80 preimage 原樣** `{request:N(9鍵),bindings:{index,aliases,parameters,clock}}`，不暗加 time_range_source；來源只進 output hash／parse receipt，領域條件相同就保持相同 query lineage。schema/kit/consumer 必須同步支援明確 v2；新產出不能冒用 v1。

待選替代案：只在 Q3 parse response 增加標示，Q1/Q2 維持 v1 但須讀 parse receipt；或另提其他版本方案。原稿「v1 加兩鍵並改 preimage」因破壞 strict schema／D80，撤回作為建議，沒有實作或視為使用者決定。語法範圍（單獨「紅色的人／那個人」）、wire 版本及可信 pin 交付仍交使用者核定。

UI在執行前後顯示「使用整段已選run範圍」與來源/牆鐘界線；不寫「現在」，不把預設範圍改稱觀測涵蓋完整。PARSED仍可能下游PARTIAL／NO_MATCH。指南新增缺時間題型說明，但保留舊人工題目bytes、來源CSV/hash與已回收答案，不回填或重寫。正式評分題必須明寫核定時間，不能走整段預設；yyin 已交題目是否含缺時間反問題與適用評分版本目前 UNKNOWN，採用前由評估 owner 核對，舊題 bytes 不改。

遷移順序：此提案複核→契約採用文字與schema/kit對齊→Q3規則/adapter/closed aliases和focused tests→新產品重錄／前端核對→新版本指南。建議測試涵蓋單run缺時間、完整／部分／無效字面時間、無run/多run/缺clock/壞pin、未知詞、解析模式一致與output hash可重現。

## 3. 可信 G4 收據（格式尚未採用）

目前§5.1已要求可信使用者核准來源，graph/scope自己寫APPROVED/true不授權。**GitHub留言作者login也不夠**：同帳號的agent可貼留言，不能以agent自己的「已核准」證明人類核定。

提議新增獨立`q-demo.g4-approval-receipt.v1`（暫名），原始UTF-8 bytes SHA-256由部署/launcher的**外部受信設定**明列；此pin必須由使用者在實際核定後提供，不能讓producer依自己JSON、自己的布林值或自己的GitHub留言自動加入allowlist。收據以受控ref載入，不接受request自帶path/hash來升權。簽章／憑證系統本次不提為既定依賴；外部pin的交付/owner仍待確認。

收據至少包含：

| 欄位 | 提議規則 |
| --- | --- |
| source／catalog／static／兩圖／tracking scope | scene_id/revision、原source SHA、catalog SHA、static SHA、兩圖file與content SHA、scope原始bytes SHA；全部須與當前輸入一致 |
| approval_ref／human_decision_ref | 實際使用者核定的checkpoint/留言與受信pin交付證據；不能只引用agent產出紀錄 |
| independent_review_ref | Claude固定head複核與僅核定欄位diff檢查，記實際文件/hash，不是人類核准替代物 |
| edge_decisions[] | E_OUT_VEST、E_VEST_CORR、E_W_CORNER、E_PORTAL_R101、E_CORNER_N各自traversability/state；E_PORTAL_R102維持TOPOLOGICAL_ONLY，沒有核定的用途不升權 |
| transition_decisions[] | M1 兩方向逐條列 APPROVED／NOT_APPROVED／UNKNOWN；後兩者分別代表明確不核准及尚未決定，均不能讓空 edge_path 升為 APPROVED_WALKABLE，也不得成為自動候選。列來源出口、目標入口及 CORR_W 同區域 authority；這是未實作提案，現行 loader 行為仍需另案修正 |
| region_purpose_decisions[] | R101 必列 region_id 與 allowed_purposes／exclusions，E_PORTAL_R101 通行核准不能代替 R101 用途核准；未核准用途維持 UNKNOWN |
| derived_legal_transitions_by_run[] | 每個 run 列實際開放的 transition_id、來源／目的、edge_path、核定用途和來源決定；逐邊核准對應哪些候選必須可重算，清單進收據 hash |
| approved_purposes／exclusions | 精確r004用途與鏡頭／run邊界；CAM_ENTRY只Q1、D77四方向仍排除；不承接Line2 v4的D90決策 |
| status／date／provenance | 提案／使用者核定的狀態分開；未有真實核定時不能填APPROVED或偽造核准時間 |

收據內容及核准依據只使用靜態幾何／校正／圖；不得讀 GT、renderer 軌跡、visibility、depth、劇本 t_N／t_X。

loader提議行為：缺受信收據/核定前置→保留GRAPH_NOT_APPROVED／工程PARTIAL；收據bytes pin不符、來源或條目矛盾→DataIntegrityError，停止自動切鏡。存在收據本身不證明實體安全／通行全域正確。凍結／G4／渲染順序不變；D84 camera catalog凍結與G4脫鉤。採用前應先審外部 pin 交付流程、M1 及逐邊值；新增缺／錯 pin、NOT_APPROVED／UNKNOWN M1、R101 未核用途、逐 run 衍生清單不符的 focused tests，不能把此格式提案當已有可信 receipt。

## 實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: 新Draft `codex/q1q5-contract-d86-g4-options`；head見PR。
- Files changed: 主契約的v2歷史註記、§5.1空行、U37例子修正及提案連結；本提案。
- Commands run and results: 更新區塊JSON語法解析、U37兩段state/cause/input pin欄位機械核對；`git diff --check` PASS。純文件，未跑產品測試。
- Artifacts: 兩份Markdown SHA-256見PR；沒有G4核准收據。
- Verified: 提案區分已選產品行為與未定wire、阻擋reasons與範圍解釋、可信外部pin與自宣告布林。
- Not verified: 外部trusted-pin交付設計、schema/kit/runtime實作、實際G4、D86產品／browser／正式題。
- Deviations, UNKNOWN items and follow-ups: 提案待Claude複核後再實作；不改yyin題目、不預先核M1或新增格式為既定契約。

## 本次審查回修（未採用）

回覆 #260 F1–F8：版本建議 v2／單鍵，D80 preimage 不改；selected run 定義、實際 request 與解析 intent 差別、正式題明示時間、R101 用途、M1 三態、逐 run 候選清單與 GT 排除已補。語法範圍、wire 選版與受信 pin 交付三項仍未決，不能由此文件自動採用。F9/F10 在主契約修正，只收緊例子文字與既有 kit 一致，不改產品行為。
