# D86 Q3 與可信 G4 收據介面提案

2026-10-27。C4。**PROPOSED／待Claude複核；只提介面，不實作產品、不核G4、不改yyin已交題目。**D86第1、2項的產品行為已由使用者選定，這裡待確認的是語法、wire欄位、原因碼與遷移方案；G4 receipt格式則仍是提案。D65數值、D73原因全序、D78兩段journal、D81追蹤鏡頭範圍及D89長度保持。

## 1. Q3口語追蹤（D86-1）

第一版以有版本/hash的封閉規則為baseline，LLM_WITH_RULE_FALLBACK路徑保留。請原owner複核下列文法，再改q3_rules／closed aliases／tests／指南；不是直接把所有關鍵字substring都當追蹤。

| 文字型態 | 提議解析 | 邊界 |
| --- | --- | --- |
| 跟著〈人／外觀條件〉、追蹤〈人／外觀條件〉 | FIND_PERSON → Q2 appearance seed | 類別person；服色只從封閉表解析，仍需真實觀測選seed |
| 〈那個人／紅色的人／封閉person條件〉去了哪裡 | FIND_PERSON → Q2 appearance seed | 「那個」不是身分指代成功，不能填GT／actor／上一人的observation ID |
| 紅色的人 | person＋red外觀條件，依完整句的查找／追蹤語法分Q1或Q2 | 單獨外觀詞不自動推成Q2；缺行為時沿既有查找規則 |
| 哪些鏡頭拍到〈條件〉 | FIND_CAMERAS → Q1 | 不因別處出現「人」而當追蹤 |
| 同句有互斥完整找／追指令、開放詞、跟著車 | NEEDS_CLARIFICATION或既有UNSUPPORTED_CONDITION | 不靠LLM偷偷改意圖、不把車轉成person |

規則沿用§14-9(a)中介輸出，再由同一validator形成Q1/Q2。新語法固定rule version/hash與closed aliases hash，舊錄製原樣重播；新增例句是工程語法測試，不當人工正式題／答案。Q3回應v1目前沒有頂層intent，前端可從PARSED的`structured_query.schema_version`派生找/追並標示來源；本提案不增加第二個可能矛盾的intent欄位。

## 2. 缺時間時查整段已選run（D86-2）

只在context恰有一個已註冊run，且該run的clock已驗scope/hash、duration/t0有效時啟用。自然語句**完全沒有時間字面值**時，產生SOURCE時間`[t0_us,source_duration_us)`；現行t0=0，所以A4為[0,50000000)、B4為[0,42000000)。這是D86整run預設，與D89情境卡手動Q2的[0,48)/[0,40)範圍不同，不能互相替代。

- 句子已有完整合法時間：照明示時間處理，不覆寫成整run。
- 有部分時間、無效時間、含「現在」等未支援表達：沿既有明確失敗／反問，不把解析失敗當完全沒時間。
- 無選定run、多run、缺mapping：NEEDS_CLARIFICATION，沿既有MULTI_RUN_SCOPE_UNRESOLVED／CLOCK_MAPPING_MISSING，不猜日期或拼run。
- clock存在但pin／scope錯：integrity error，不回預設成功。

**提議wire：**在§2.3共用resolved_scope新增兩個nullable鍵（正式採用後需同步strict schema／kit／consumers）：

```json
{
  "time_range_source": "DEFAULT_SELECTED_RUN",
  "time_range_reason": "DEFAULT_SELECTED_RUN_RANGE"
}
```

`time_range_source`封閉值提議`EXPLICIT_SOURCE | EXPLICIT_WALL | DEFAULT_SELECTED_RUN | null`；`time_range_reason`只在預設整run時是`DEFAULT_SELECTED_RUN_RANGE`，否則null。這是範圍解釋碼，**不加入阻擋用reasons[]**，不破壞§14-12的reason=reasons[0]；成功PARSED仍reason=null／reasons=[]。requested_time寫出真正SOURCE範圍，resolved_source_ranges_us由同一clock resolver取得，不能只改UI文字。這兩個鍵與實際時間範圍進output hash；提議把time_range_source納入query lineage preimage，以區分使用者明示整段與系統預設，確切query_sha256欄位由原owner確認。

UI在執行前後顯示「使用整段已選run範圍」與來源/牆鐘界線；不寫「現在」，不把預設範圍改稱觀測涵蓋完整。PARSED仍可能下游PARTIAL／NO_MATCH。指南新增缺時間題型說明，但保留舊人工題目bytes、來源CSV/hash與已回收答案，不回填或重寫。

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
| transition_decisions[] | M1兩方向逐條選擇，列允許來源出口／目標入口及CORR_W同區域authority；未選擇保持UNKNOWN，不以空edge_path空真值自動升權 |
| approved_purposes／exclusions | 精確r004用途與鏡頭／run邊界；CAM_ENTRY只Q1、D77四方向仍排除；不承接Line2 v4的D90決策 |
| status／date／provenance | 提案／使用者核定的狀態分開；未有真實核定時不能填APPROVED或偽造核准時間 |

loader提議行為：缺受信收據/核定前置→保留GRAPH_NOT_APPROVED／工程PARTIAL；收據bytes pin不符、來源或條目矛盾→DataIntegrityError，停止自動切鏡。存在收據本身不證明實體安全／通行全域正確。凍結／G4／渲染順序不變；D84 camera catalog凍結與G4脫鉤。採用前應先審外部pin交付流程、M1及逐邊值，不能把此格式提案當已有可信receipt。

## 實際產出 / Actual output

- Model / effort: GPT-6 family / UNKNOWN。
- PR / commits: 新Draft `codex/q1q5-contract-d86-g4-options`；head見PR。
- Files changed: 主契約的v2歷史註記、§5.1空行、U37例子修正及提案連結；本提案。
- Commands run and results: 更新區塊JSON語法解析、U37兩段state/cause/input pin欄位機械核對；`git diff --check` PASS。純文件，未跑產品測試。
- Artifacts: 兩份Markdown SHA-256見PR；沒有G4核准收據。
- Verified: 提案區分已選產品行為與未定wire、阻擋reasons與範圍解釋、可信外部pin與自宣告布林。
- Not verified: 外部trusted-pin交付設計、schema/kit/runtime實作、實際G4、D86產品／browser／正式題。
- Deviations, UNKNOWN items and follow-ups: 提案待Claude複核後再實作；不改yyin題目、不預先核M1或新增格式為既定契約。
