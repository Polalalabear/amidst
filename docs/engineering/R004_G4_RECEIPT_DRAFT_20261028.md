# r004 G4 回條草稿（CQ-02；2026-10-28）

**PROPOSED／PENDING_USER；不是正式回條，沒有核准任何圖、scope、邊、方向或用途。**
採 #260 `d560f224be0f93cf62076f5ae2fa78b0ae957d15` §3–§3.2 白名單；圖依 #294 `0c34287b0b0c21c672f863fd281934f37e8aa24b`。
依賴未經 Claude 複審：#294@0c34287b0b0c21c672f863fd281934f37e8aa24b。#260 格式仍 PROPOSED，沒有冒充已採用 schema。

## 固定輸入與查核邊界

JSON 草稿的 `schema_version`、`status`、`decisions_sha256` 都在頂層，型別均為 string；其值依序是 draft.v1、PROPOSED、64位小寫hex。
三個核准／複核 ref 均為 null；`allowed_purposes`／`approved_purposes` 都是空陣列，表示沒有授予用途，沒有自創用途 token。
可核項目保留 PENDING_USER；E_PORTAL_R102固定維持既有TOPOLOGICAL_ONLY／UNKNOWN限制，不是新核准或可任選升權。空集合明寫 []。每個 run 目前合法候選清單都是 []，待決 payload 的 hash 不會開放任何項目。

| pin | 值 |
| --- | --- |
| `scene_id` | `controlled_scene_v1_s001` |
| `scene_revision` | `r004` |
| `source_sha256` | `466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b` |
| `catalog_sha256` | `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f` |
| `static_sha256` | `bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a` |
| `region_graph_file_sha256` | `a2f737805cf5446c6ba01fa4bebfddd2186d040cbd94314cf573c082191b24e1` |
| `region_graph_content_sha256` | `8c33aba73396851338efcb148bb078d521efbcafbcad1a80f0f3feff7bee0909` |
| `camera_graph_file_sha256` | `e250413a0d0a2aeb61bd98bb1763236b1e39127f919cee1ee3ca3bd906b78409` |
| `camera_graph_content_sha256` | `708586a29ef610190c012c746c217226fc989e57caaf203b09d7000e4dcfba48` |
| `tracking_scope_file_sha256` | `ed5b68995094b060b21a9dba6a05e26a21aa0af15c0f8dcb7fd0bd56424af80a` |

| 輔助靜態／ROI／run 文件 | bytes SHA-256 |
| --- | --- |
| `configs/q1q5/graphs/r004/build_plan_v3_1.json` | `277d0e9376f8d0bcb055d11aac7e856a4ae50b541bf7519c719a998c2f1b3d51` |
| `configs/q1q5/graphs/r004/static_patches_v3_1.json` | `fb4141b5e50267982f0e566268e565a584b1bd9fe80a6bacbe895a45b8498547` |
| `configs/q1q5/graphs/r004/roi_report_v3_1.json` | `0fae137992b1fa76f80f4da6dfa79d4cb8c1a0eb38ca1f2d75c054266866b2c9` |
| `configs/q1q5/graphs/r004/source_pins_v3_1.json` | `f47547c146ccf6ac9c0462f400fc3a21fae3e8c019ac03375659e934b25b24f7` |
| `provenance/source_static_geometry.json`（LOCAL；僅引用既有 pin） | `bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a` |
| `provenance/static_membership.json`（LOCAL；僅引用既有 pin） | `e71f6ad16868ab450bcd093eb50f6fd7ca4a393c73689055235e9505f9e48ca7` |
| `provenance/region_meshes.json`（LOCAL；僅引用既有 pin） | `4dd2861ded335a9b31454672d3ed1591405f5c53644ccc9df64736cfccdb8a8c` |
| `provenance/camera_catalog.json`（LOCAL；僅引用既有 pin） | `3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f` |
| `configs/q1q5/runs/r004_a4_v1.json` | `2f9c77fac097098787a1b23602cc59868677d655a1c4f92c0831c21f9dd0a0b9` |
| `configs/q1q5/runs/r004_b4_v1.json` | `bec1b2829ef2eabcdac74ea9123725ee7e9b486364c27c360b45e70eb707b598` |

source SHA 僅從來源綁定的 run 註冊與既有收據交叉核對，沒有開啟 .blend。沒有讀 GT、renderer軌跡、visibility、depth或劇本 t_X／t_N。
v3_1 ROI 含來源 world頂點、投影與靜態支撐見證；它們不等於首現、身份、通行或碰撞證明。兩圖與 scope 的 frozen bytes 不改。

## yyin 意見及證據適用範圍

10-24：策展收據記錄132/132列VALID、123 T／7 F／2不確定，6個REGION_EDGE與22個CAMERA_TRANSITION為T；VALID不是核准。
來源 `docs/history/Q1Q5_R004_REVIEW_RETURN_20261025.json`，CSV pin `05200de169cfda4ee491e32160977070bc0bbeba3cc93b2cd74c139b23ecd7db`。
這是 v2 審查；本次不把總體22個T配成 v3_1每條的核准，M1的新列尤其沒有對應意見（MISSING）。每列靜態依據是固定圖的transition／ROI及其basis_refs。
10-27三題：BRANCH加深加寬是必要條件，但及時切鏡目的未達成；WIDE下緣有提案幾何、連接MISSING、門指認UNKNOWN；W1↔EXT_CAR雙向失聯意見不升權。
原CSV與完整回件保持LOCAL。本次僅引用已策展摘要及 pin，不發布人工原表。
**D98-1：補交前為人工例外；補交後重跑 verify_pack。** #347處理缺少 `templates/審查表.csv`；本次未匯入補件。10-27包16個固定檔相符，CSV pin `bee91e61004ac13b8e30a6550f77664975c207101788efe1c7f9da16c64df197`。

## 逐邊待核表

| edge_id | 兩側region | frozen值 | 草稿實際值 |
| --- | --- | --- | --- |
| `E_CORNER_N` | CORNER ↔ CORR_N | TOPOLOGICAL_ONLY / UNKNOWN | PENDING_USER / PENDING_USER |
| `E_OUT_VEST` | OUT_W ↔ VEST_W | TOPOLOGICAL_ONLY / UNKNOWN | PENDING_USER / PENDING_USER |
| `E_PORTAL_R101` | CORR_W ↔ R101 | TOPOLOGICAL_ONLY / UNKNOWN | PENDING_USER / PENDING_USER |
| `E_PORTAL_R102` | CORR_N ↔ R102 | TOPOLOGICAL_ONLY / UNKNOWN | TOPOLOGICAL_ONLY / UNKNOWN（固定既有限制） |
| `E_VEST_CORR` | VEST_W ↔ CORR_W | TOPOLOGICAL_ONLY / UNKNOWN | PENDING_USER / PENDING_USER |
| `E_W_CORNER` | CORR_W ↔ CORNER | TOPOLOGICAL_ONLY / UNKNOWN | PENDING_USER / PENDING_USER |

每條用途都未核；E_PORTAL_R102依#260維持TOPOLOGICAL_ONLY／UNKNOWN，屬固定排除，不因門指認或其他邊核准升權。E_CORNER_N沒有用到它的Line 1轉移，核該邊不會創造BRANCH→WIDE。
靜態來源是上表static SHA、region graph的basis_refs、每個ROI的靜態patch；10-24邊T只是意見。

## 逐轉移待核表

下表全部 decision=PENDING_USER、allowed_purposes=[]。用途、建議與yyin意見分欄存JSON；建議／意見不進決定payload。
| transition_id／方向 | 來源出口 | 目的入口 | region_path／edge_path | 適用run |
| --- | --- | --- | --- | --- |
| `T_CAM_BRANCH__CAM_W1` | CAM_BRANCH:EXIT_V3:E_W_CORNER | CAM_W1:ENTRY_V3:E_W_CORNER | CORNER → CORR_W / E_W_CORNER | B4 |
| `T_CAM_BRANCH__CAM_W2` | CAM_BRANCH:EXIT_V3:E_W_CORNER | CAM_W2:ENTRY_V3:E_W_CORNER | CORNER → CORR_W / E_W_CORNER | B4 |
| `T_CAM_EXT_CAR__CAM_W1` | CAM_EXT_CAR:EXIT_V3:NORTH_APPROACH, CAM_EXT_CAR:EXIT_V3:SOUTH_APPROACH | CAM_W1:ENTRY_V3:E_VEST_CORR | OUT_W → VEST_W → CORR_W / E_OUT_VEST, E_VEST_CORR | A4 |
| `T_CAM_EXT_CAR__CAM_W2` | CAM_EXT_CAR:EXIT_V3:NORTH_APPROACH, CAM_EXT_CAR:EXIT_V3:SOUTH_APPROACH | CAM_W2:ENTRY_V3:E_OUT_VEST | OUT_W → VEST_W / E_OUT_VEST | 本兩run均無 |
| `T_CAM_EXT_CLEAR__CAM_W1` | CAM_EXT_CLEAR:EXIT_V3:E_OUT_VEST | CAM_W1:ENTRY_V3:E_VEST_CORR | OUT_W → VEST_W → CORR_W / E_OUT_VEST, E_VEST_CORR | A4 |
| `T_CAM_EXT_CLEAR__CAM_W2` | CAM_EXT_CLEAR:EXIT_V3:E_OUT_VEST | CAM_W2:ENTRY_V3:E_OUT_VEST | OUT_W → VEST_W / E_OUT_VEST | 本兩run均無 |
| `T_CAM_R101_IN__CAM_W1` | CAM_R101_IN:EXIT_V3:E_PORTAL_R101 | CAM_W1:ENTRY_V3:E_PORTAL_R101 | R101 → CORR_W / E_PORTAL_R101 | B4 |
| `T_CAM_R101_IN__CAM_W2` | CAM_R101_IN:EXIT_V3:E_PORTAL_R101 | CAM_W2:ENTRY_V3:E_PORTAL_R101 | R101 → CORR_W / E_PORTAL_R101 | B4 |
| `T_CAM_W1__CAM_BRANCH` | CAM_W1:EXIT_V3:E_W_CORNER | CAM_BRANCH:ENTRY_V3:E_W_CORNER | CORR_W → CORNER / E_W_CORNER | B4 |
| `T_CAM_W1__CAM_EXT_CAR` | CAM_W1:EXIT_V3:E_VEST_CORR | CAM_EXT_CAR:ENTRY_V3:NORTH_APPROACH, CAM_EXT_CAR:ENTRY_V3:SOUTH_APPROACH | CORR_W → VEST_W → OUT_W / E_VEST_CORR, E_OUT_VEST | A4 |
| `T_CAM_W1__CAM_EXT_CLEAR` | CAM_W1:EXIT_V3:E_VEST_CORR | CAM_EXT_CLEAR:ENTRY_V3:E_OUT_VEST | CORR_W → VEST_W → OUT_W / E_VEST_CORR, E_OUT_VEST | A4 |
| `T_CAM_W1__CAM_R101_IN` | CAM_W1:EXIT_V3:E_PORTAL_R101 | CAM_R101_IN:ENTRY_V3:E_PORTAL_R101 | CORR_W → R101 / E_PORTAL_R101 | B4 |
| `T_CAM_W1__CAM_W2` | CAM_W1:EXIT_V3:E_VEST_CORR, CAM_W1:EXIT_V3:E_PORTAL_R101, CAM_W1:EXIT_V3:E_W_CORNER | CAM_W2:ENTRY_V3:E_PORTAL_R101, CAM_W2:ENTRY_V3:E_W_CORNER | CORR_W / [] | B4 |
| `T_CAM_W1__CAM_WIDE` | CAM_W1:EXIT_V3:E_W_CORNER | CAM_WIDE:ENTRY_V3:E_W_CORNER | CORR_W → CORNER / E_W_CORNER | B4 |
| `T_CAM_W2__CAM_BRANCH` | CAM_W2:EXIT_V3:E_W_CORNER | CAM_BRANCH:ENTRY_V3:E_W_CORNER | CORR_W → CORNER / E_W_CORNER | B4 |
| `T_CAM_W2__CAM_EXT_CAR` | CAM_W2:EXIT_V3:E_OUT_VEST | CAM_EXT_CAR:ENTRY_V3:NORTH_APPROACH, CAM_EXT_CAR:ENTRY_V3:SOUTH_APPROACH | VEST_W → OUT_W / E_OUT_VEST | 本兩run均無 |
| `T_CAM_W2__CAM_EXT_CLEAR` | CAM_W2:EXIT_V3:E_OUT_VEST | CAM_EXT_CLEAR:ENTRY_V3:E_OUT_VEST | VEST_W → OUT_W / E_OUT_VEST | 本兩run均無 |
| `T_CAM_W2__CAM_R101_IN` | CAM_W2:EXIT_V3:E_PORTAL_R101 | CAM_R101_IN:ENTRY_V3:E_PORTAL_R101 | CORR_W → R101 / E_PORTAL_R101 | B4 |
| `T_CAM_W2__CAM_W1` | CAM_W2:EXIT_V3:E_PORTAL_R101, CAM_W2:EXIT_V3:E_W_CORNER | CAM_W1:ENTRY_V3:E_VEST_CORR, CAM_W1:ENTRY_V3:E_PORTAL_R101, CAM_W1:ENTRY_V3:E_W_CORNER | CORR_W / [] | B4 |
| `T_CAM_W2__CAM_WIDE` | CAM_W2:EXIT_V3:E_W_CORNER | CAM_WIDE:ENTRY_V3:E_W_CORNER | CORR_W → CORNER / E_W_CORNER | B4 |
| `T_CAM_WIDE__CAM_W1` | CAM_WIDE:EXIT_V3:E_W_CORNER | CAM_W1:ENTRY_V3:E_W_CORNER | CORNER → CORR_W / E_W_CORNER | B4 |
| `T_CAM_WIDE__CAM_W2` | CAM_WIDE:EXIT_V3:E_W_CORNER | CAM_W2:ENTRY_V3:E_W_CORNER | CORNER → CORR_W / E_W_CORNER | B4 |

M1兩個方向分別是 `T_CAM_W1__CAM_W2`、`T_CAM_W2__CAM_W1`；JSON各自PENDING_USER。使用者可各選APPROVED／NOT_APPROVED／UNKNOWN，後兩者都不開放。
選項一：明確核定精確方向、來源出口、目的入口與CORR_W用途，保留路線彈性；代價是必須補完整CQ-21有效視圖與核准綁定，不能只核空路徑。
選項二：維持UNKNOWN（或明確NOT_APPROVED），維持保守不切鏡；代價是這兩方向不能接手。兩個方向互不推定，建議先UNKNOWN，實際值留使用者決定。
R101另有region_purpose_decisions列；E_PORTAL_R101的通行核准不代替進入R101的用途核准。其餘region亦逐列保留PENDING_USER／空用途，沒有隱含許可。

## 每run候選與核准影響（可重算）

| run | 渲染／查找camera_ids | tracking交集 | 目前合法transition_ids | 非零edge_path轉移數 |
| --- | --- | --- | --- | ---: |
| A4-1 | CAM_ENTRY, CAM_EXT_CAR, CAM_EXT_CLEAR, CAM_W1 | CAM_EXT_CAR, CAM_EXT_CLEAR, CAM_W1 | [] | 4 |
| B4-1 | CAM_BRANCH, CAM_R101_IN, CAM_W1, CAM_W2, CAM_WIDE | CAM_BRANCH, CAM_R101_IN, CAM_W1, CAM_W2, CAM_WIDE | [] | 12 |

重算核准影響集合：兩端都在 `run.camera_ids ∩ tracking_scope.tracking_camera_ids` 的既有transition，排除空edge_path，依transition_id排序。得到A4 4條、B4 12條；與#260 F4c一致。
這16條只是條件式影響，不是當前合法候選。逐條完整出口／入口／路徑見上表和JSON；M1另2條只在B4範圍，當前仍排除。
實際開放還必須同時成立：可信兩圖APPROVED、scope APPROVED與G4_approved=true的effective視圖、逐邊walkability/state、逐用途、逐轉移及run範圍核准，並經CQ-21驗證同一pins與兩個可信refs。
若任一必要核准是PENDING_USER／UNKNOWN／缺項，該條不在合法清單；E_PORTAL_R102與D77排除不會因其他項核准而解鎖。M1即使勾APPROVED，CQ-21前仍不開放。
正式候選還依當次腳點命中出口、top_k等契約規則篩選；run清單是允許上界，不代表每一格都會出現。BRANCH死路ROI與北向空檔詳CQ-01收據。

## Hash、選定payload與後續流程

待決草稿 `decisions_sha256 = 7ea8c5e5e37238f406170367563efa58c73be42ef890ffe431d58f8fb18f6323`。這個值只識別目前未決內容，不是可用來開放所有項目的核准hash。
採#260@d560f22 §3.1五鍵白名單，不從物件遞迴猜排除鍵。表列按edge_id／transition_id／region_id／run_id固定字典序；路徑陣列保留方向，不能排序edge_path或region_path。
approval_ref／human_decision_ref／independent_review_ref、recommendation／yyin_opinion、status／date／provenance及hash自身不進payload。ROI／靜態來源由固定圖／static pins綁定；非白名單旁欄不能當authority。
使用者選定後，協調者先製作草稿副本：只把精確選中的逐邊值、逐轉移decision、用途、region用途與run範圍填入；未選項仍保留，依完整effective gates重新導出逐run清單。不得刪待決鍵。
以下程式對該選定副本按完全相同白名單重建payload與hash；可另存payload給獨立檢查。它只做序列化，不是receipt loader、授權驗證器或候選升權工具。

```python
import hashlib, json
from pathlib import Path
doc = json.loads(Path("docs/engineering/R004_G4_RECEIPT_DRAFT_20261028.json").read_bytes())
KEYS = {'input_pins': ['scene_id', 'scene_revision', 'source_sha256', 'catalog_sha256', 'static_sha256', 'region_graph_file_sha256', 'region_graph_content_sha256', 'camera_graph_file_sha256', 'camera_graph_content_sha256', 'tracking_scope_file_sha256', 'run_camera_scopes'], 'edge_decisions': ['edge_id', 'traversability', 'state', 'run_ids', 'allowed_purposes'], 'transition_decisions': ['transition_id', 'from_camera_id', 'to_camera_id', 'via_exit_zone_ids', 'to_entry_zone_ids', 'region_path', 'edge_path', 'run_ids', 'decision', 'allowed_purposes'], 'region_purpose_decisions': ['region_id', 'run_ids', 'decision', 'allowed_purposes', 'exclusions'], 'derived_legal_transitions_by_run': ['run_id', 'transition_ids']}
pins = {k: doc["input_pins"][k] for k in KEYS["input_pins"]}
pins["run_camera_scopes"] = [{k: r[k] for k in ["run_id", "camera_ids", "allowed_purposes", "exclusions"]} for r in pins["run_camera_scopes"]]
payload = {"input_pins": pins, **{name: [{k: row[k] for k in fields} for row in doc[name]] for name, fields in KEYS.items() if name != "input_pins"}}
raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
print(hashlib.sha256(raw).hexdigest())  # 不含尾端換行
```

選定副本的新hash與payload先經固定head複核，再由使用者在checkpoint留言引用同一hash和精確條目；協調者D決策須引用同一hash及留言ID。
若只核部分或改值，先重建完整新payload／新hash，再明確引用新hash核定；不能把舊hash核准套到新選項。回填refs不能改變payload hash。
**CQ-21a待決：**目前白名單沒有graph／scope／G4 effective gates的具體決定欄位；這些由#308補條文。本草稿不自創欄位；若#308改白名單，整份草稿與hash必須重建，不能用本hash代核未綁定gate。

## 等使用者逐項選擇（本文件沒有替使用者決定）

1. 各非零邊／對應方向與用途：A只核A4／B4實際使用範圍（建議，範圍小；未選仍阻擋）；B暫不核（風險低；CX-7持續阻擋）；C釐清靜態證據後再定（較完整；延後正式資料）。
2. M1兩方向：逐方向選APPROVED或保留UNKNOWN／NOT_APPROVED，優缺點見上節；不能成批由整圖核准推導。
3. R101與其他region用途：A逐項寫明必要用途及排除（建議；需#308條文對齊）；B暫不核（保守；使用R101的方向不開放）。沒有預設用途token。
4. BRANCH／WIDE缺項：A保留Line 1範圍並交CQ-22人工確認／CQ-08 v4（建議；缺項仍MISSING／UNKNOWN）；B等確認後再做G4（更完整；延後正式資料）。

## 不在本G4草稿核准範圍

Line 2 v4重疊對／BRANCH↔WIDE新出口或轉移、身份、整場通行與碰撞、劇本凍結、模型／HSV核准、正式研究／AC7、發包與合併。
CAM_ENTRY仍只Q1。D98-2授權渲染須G4＋劇本凍結＋磁碟≥9 GiB全部成立；D99另須U7＋v2劇本凍結；本草稿不解除任何條件。

## 已知差異及驗證限制

#281 P3-A：kit q1q5_conformance.py:1558–1566仍要求TOPOLOGICAL_ONLY_EDGE，與契約§5.4 GRAPH_NOT_APPROVED優先不同；本草稿照契約優先序，沒有改kit。
架構守門#307交付前NOT_RUN；本次純草稿，不執行正式conformance／runtime、不產錄製，不以JSON可解析當schema已採用或正式G4接受。
圖與run註冊在固定head檢查，不讀私有劇本或事件時間；可重算的是範圍與hash，不是實際接回成功或可見性。
