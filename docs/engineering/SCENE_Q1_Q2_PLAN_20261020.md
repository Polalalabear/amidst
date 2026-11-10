# 新版場景與 Q1／Q2 工作計畫總結

日期：2026-10-20（Asia/Taipei）。狀態：討論初稿，供 Claude 審查及使用者定案；不是已完成實作或驗收紀錄。

**後續討論入口：** [Q1／Q2 第一版 Demo 修訂稿](Q1_Q2_FIRST_DEMO_CLAUDE_DISCUSSION_20261020.md) 納入使用者最新的 RT-DETR 優先、兩層圖、暫緩 tracking／ReID、Codex 主實作及另一對話的依賴查證。本文件保留前稿內容；模型、分工與第一版範圍有差異時，以後續修訂稿的待定案項目為準，不將前稿候選技術當成已採用。

## 1. 已確認的主線與工作邊界

- **Q1：鏡頭畫面快速檢索。** 使用自然語言搜尋符合條件的鏡頭及時間片段，例如「找出有車子的畫面」。室外搜尋物件選車子；樹木與噴水池不列為必要驗收。
- **Q2：跨鏡頭連續重現。** 指定人物特徵、必要時選定起始觀測，搜尋相關鏡頭中的人物畫面，按共同時間軸連續播放並優化切鏡。
- 直接引入模型讀取實際 RGB、判斷畫面內容及匹配候選；不能只加文字指令解析，再把舊索引當成模型畫面判斷。
- 採成熟辨識／追蹤元件整合，重點放在檢索速度、結果相關性、跨鏡頭關聯與播放流暢度。追蹤演算法研究、精細 3D 重建及研究級可重現性驗證暫緩。
- 仍保留基本場景版本、時間戳、鏡頭校正、來源識別與缺失狀態。Blender 預設角色路線、角色 ID、GT、renderer visibility/depth 不得成為查詢或切鏡答案。
- 展示可連續，人物在盲區內仍屬未觀測。找不到或候選不明確時保留搜尋中／未知，不補出已觀測畫面。

## 2. 場景與版本必須分開標示

| 來源 | 實際路徑 | 對應範圍 |
| --- | --- | --- |
| school v2 | `blender/school_v2.blend`；部分研究工具預設 `blender/working/school_v2_research.blend` | 舊 CLI、攝像頭匯出／校正等工具預設；不代表目前播放來源 |
| school v3 | `blender/school_v3.blend` | 舊 Office、接地控制與人形圓柱測試；舊 C5 四鏡頭／20 秒查詢限制屬此流程 |
| 目前受控場景 r003 | `data/pilot/controlled_scene_v1/assets/controlled_scene_v1_s001_r003.blend` | 本 checkout 登錄的受控 A／B1 RGB 播放來源 |

後端文件的「真實資料接入 v2／2a」是功能批次名稱，不是 `school_v2.blend`。`*_REVIEW.blend` 是另一種用途，不與產製來源混稱。

目前 r003 來源 hash 為 `6e7de38dc069d330e0ffbb6c0051cdab304566fdbb7e3e8dfb429af863ae6d8e`；在本次對話前一輪以 `shasum -a 256` 核對，與後端 source pin 相符。這不代表場景內容、路線或辨識品質已驗收。

使用者已表示原版 r003 自行封存在雲端，並允許直接修改本機 r003，不必另留本機 r004。雲端封存為 **REPORTED**，本輪未查證遠端副本。後續實作沿用 r003 檔名時仍須更新內部場景修訂與來源 hash；既有 A／B1 資料維持舊來源綁定，不改 pin 冒充新場景產物。舊來源本機不再保留時，文件標明其雲端保存與本機復原限制。

## 3. 建議的場景修改初稿

以下是方向，尚未形成逐物件、鏡頭座標及逐時段的最終修改清單：

1. 先盤點 r003 既有區域、模型、人物、攝像頭與動畫，再列出需保留／調整／新增的項目，不假定已有車輛室外區。
2. 檢查並補齊支援車輛搜尋的室外區域；安排有車及無車的鏡頭畫面，讓 Q1 有可區辨的搜尋結果。
3. 至少兩條跨鏡頭路線：室外／入口至直線走廊，以及走廊經轉角短暫消失後進入教室。
4. 人物具有基本身體材質、服裝與行走動畫；先用紅衣／藍衣人物，穩定後再增加分岔或同色干擾人物。
5. 鏡頭依出口、通道、遮擋與人物投影尺寸配置；Camera Graph 表達靜態可能連通，不預先寫入角色真正的下一台鏡頭與到達時間。
6. 先用局部小批 RGB 確認模型辨識與播放效果，再擴大事件範圍。r003 現有 5 fps、960×540 不直接當最終設定；幀率、解析度、時長及資源預算待局部測試決定。

不優先投入開門動畫、全校精修、大量群眾、精細腳點／身高／碰撞或盲區多解。場景複雜度以能測試搜尋、遮擋交接及候選鏡頭為準。

## 4. 已有能力如何沿用

| 已有能力 | 沿用方式 | 新版仍需補上 |
| --- | --- | --- |
| 共用 Workbench、three.js、多畫面與時間軸 | 沿用主入口及播放操作 | Q1 結果呈現、Q2 主畫面切換、預載與連續片段播放 |
| r003 RGB 註冊、同步取格與媒體服務 | 沿用播放底座 | 修改後場景的新 run 與媒體綁定 |
| school v3 鏡頭／時間索引 | 抽用索引與時間窗查找 | 物件類別、人物特徵及片段索引；調整舊範圍限制 |
| 校正匯出、API、scene adapter、目標選取 | 沿用結構與操作 | 新場景資料、Region、模型偵測框與 local track 接入 |
| 舊跨鏡頭分析 | 抽用時間一致性、候選及播放同步邏輯 | 外觀匹配、Camera Graph 與 Handoff Controller |
| 本地 Ollama provider | 可重用呼叫與結構化輸出機制 | 模型畫面判斷與 Q1／Q2 指令契約；純文字 provider 不等於已能看圖 |

RT-DETR、ByteTrack、OSNet／OpenCV、NetworkX 為前述候選整合方案；實際版本、執行後端及與視覺語言模型的分工待定。若讓 LLM 直接看圖，必須使用支援圖片的模型。Qwen2.5 既有文字 Agent 不因保留服務就自動符合此需求；OpenAI API 接線亦未在本輪驗證。

效能方向：離線或增量產生真實模型辨識／特徵索引，查詢時先以索引縮小鏡頭及時間範圍，必要時由視覺模型判斷候選畫面，最後回傳畫面或播放片段。快取鍵須綁定來源與模型版本。此流程尚未實作或量測，不承諾即時處理速度。

## 5. 資料欄位精簡建議

不直接刪改既有 r003 safe bundle 或舊契約。先提出新版精簡契約與 adapter，讓既有資料可保留原意；不因暫緩功能而放寬既有完整性檢查。

| 類型 | 建議 |
| --- | --- |
| scene/run/clock、來源與模型版本 | 保留，集中在資料集／索引描述，以引用減少重複 |
| 鏡頭 ID、Region、解析度、內外參與座標慣例 | 保留於鏡頭設定；前端與模型按用途取得 |
| sensor size/fit、shift、render percentage 等產製細節 | 保留於產製／校正資料，不隨每次搜尋結果傳送 |
| media/frame 引用、camera、時間範圍、可用狀態 | 播放必需 |
| 類別、框、偵測分數、local track、外觀描述引用 | 辨識與檢索所需；特徵向量留後端，分數不冒充身分機率 |
| 候選鏡頭、交接狀態、片段起迄時間 | Q2 必需；多人符合時保留選取／歧義狀態 |
| hash、索引版本、模型紀錄 | 保留於內部紀錄，API 通常回傳引用即可 |
| 身高、腳點、3D 軌跡、碰撞、盲區曲線及精細幾何不確定性 | 本階段暫緩，不作 Q1／Q2 的必備輸入 |
| Blender 路線、角色 ID 與事件答案 | 產製端私有資料，不送入模型檢索、關聯與切鏡 |

對外資料可收斂為六類：場景與鏡頭清單、媒體與時間範圍、辨識結果、Q1 搜尋結果、Q2 候選／交接狀態、按時間排列的播放片段。

能力分別標示可播放、可搜尋、可交接；暫緩的 3D／研究功能不作新版 Q1／Q2 前置條件。缺影像、無偵測、尚未執行模型與系統錯誤須分開，不能全部視為找不到。

## 6. PostgreSQL 的現況與新版角色

### 現有程式可確認的用途

本輪唯讀檢查 `src/amidst/local_storage/migrations.py` 與 `postgres.py`，既有資料結構包含：

- `runs`、`records`：run 範圍／收據及觀測、事件等紀錄。
- `record_cameras`、`record_regions`：按鏡頭／區域與時間查詢的關聯索引。
- `revisions`、`jobs`：資料修訂及工作狀態。
- `descriptor_indexes`、`index_heads`：外觀描述索引與目前版本。
- `media_bindings`：媒體引用及來源綁定，影像 bytes 仍在原檔案儲存。
- `topologies`、`topology_heads`、`topology_cache`：拓樸資料及查詢快取。

這是既有程式 schema，不代表上述資料全部存在於目前 live DB，也不代表新版已接入。

### 新版建議，尚未定案

如果沿用 PostgreSQL，主要儲存 **可查詢的 metadata／索引／狀態**：場景與 run、鏡頭／Region／Graph、模型辨識與人物 track 摘要、外觀索引或其引用、媒體位置與時間、查詢／交接結果。影片、PNG、`.blend`、模型權重留在檔案儲存，DB 保存引用。

不必把所有資料都轉成 PostgreSQL 表。鏡頭設定、固定 Graph、模型參數可先保留版本化 JSON；是否入庫由實際查詢與更新需求決定。是否使用向量索引／pgvector 未決定，不列為既定依賴。

**PostgreSQL 是否為第一版必要服務仍是 OPEN。** 先核對既有索引、實際 consumers 與資料保存需求，再決定沿用現有 PG 或採較輕的儲存方案；不能為釋出空間直接刪除現有 DB。

## 7. Codex 與 Claude 工作分工

| 階段 | Codex：主要實作 | Claude：審查與獨立判斷 | 產出 |
| --- | --- | --- | --- |
| 規劃 | r003 盤點、具體修改方案、資源估算 | 事件意義、鏡頭配置與複雜度審查 | 配置圖、事件／鏡頭表 |
| 契約 | 精簡欄位、API 範例、舊資料 adapter 設計 | 必要欄位、狀態、模型 I/O 與責任邊界審查 | 待定案契約 |
| 場景 | 依定案修改 r003，匯出校正與局部素材 | 預覽畫面及事件可讀性檢查 | 更新場景、局部預覽 |
| 模型 | 畫面辨識、特徵與索引整合 | 獨立查看誤判與不適合畫面 | 可用輸出、待修清單 |
| Q1／Q2 | 快速搜尋、Graph、Handoff Controller | 候選與切鏡規則審查 | 結果及播放清單 |
| Workbench | 前端整合、時間同步、預載與播放優化 | 實際操作與驗收判斷 | 可操作 Demo |

流程：本對話先出具體方案 → Claude 審查 → 整合差異 → 使用者確認定案 → 實作。新版由 Codex 承接 Workbench 實作，Claude 不另建一套；實作前同步舊分工文件與檔案 ownership。

功能檢查限於車輛搜尋、兩條人物路線、錯誤／歧義時的顯示、切鏡時間與流暢度；量測查詢／交接延遲並記錄硬體，不自行訂成功率或延遲門檻。

## 8. 本機空間與舊 worktree 整理

既有 [worktree 退役評估](../history/WORKTREE_RETIREMENT_ASSESSMENT_20261020.md) 記錄 2026-10-20 13:15 的服務、資料與 consumer 狀態，屬既有快照，並非本輪重新驗證。

該評估指出 finalization 曾承載 PostgreSQL、Ollama、Office evidence/vendor，另有未提交項目及 SQLite state 缺口。不能把「程式已合併」或「沒有 client 連線」當作可刪整棵 worktree 的證明。

先確認新版保留功能，再逐項解除其對舊 worktree 的依賴。移動同一磁碟上的必要模型／DB 不會消除其容量；解除 symlink 引用亦不等於回收 target 用量。

舊 checkout 若僅供參考，Git refs、必要文件與已保存的唯一資料可取代其本機工作樹；文件不能取代未提交程式、唯一 DB、原資產或未封存產物。只讀查證先行，清理、停服務、搬移及 restore 另列精確範圍執行。

## 9. 可貼到新對話的唯讀查證訊息

```text
請在 /Users/polalabear/Developer/amidst 做一次範圍明確的唯讀依賴查證，目的是判斷新版 Q1／Q2 Demo 能否脫離舊 worktree，以及哪些本機資料未來可以釋出。這次不執行清理或服務切換。

先讀 AGENTS.md、docs/specs/DEVELOPMENT_RULES.md、docs/engineering/SCENE_Q1_Q2_PLAN_20261020.md、docs/history/WORKTREE_RETIREMENT_ASSESSMENT_20261020.md；依需要讀 docs/operations/CURRENT_WORK_REPRODUCTION.md。以既有盤點為入口，重新核對現況，不直接沿用舊 PID、埠、路徑或容量結論。

請確認：
1. checkout／branch／worktree、dirty／untracked／ignored 唯一資料與其他聊天 ownership；保留所有未提交工作。
2. 主 Office／controlled-scene launcher 的實際路徑依賴，包含 Python environment、three.js vendor、evidence、校正、模型、資料庫；區分 school v2、school v3 與目前 r003。
3. Ollama／Qwen、PostgreSQL 等服務的當前 PID、cwd、listener、資料位置、實際 consumers。保留既有 Qwen／OpenAI 語意分析需求，不把文字 Qwen 視為已支援畫面輸入；不呼叫付費 API 或模型 completion。
4. PostgreSQL 僅在可用連線下做 READ ONLY 查詢：schema／table、估計或有界 row counts、大小、run 範圍與 consumers，並對照程式中的 metadata／records／descriptor／media／topology 用途。不輸出憑證、原始個資或大量資料；不要初始化／遷移 DB。查不到則標 UNKNOWN。
5. 既有備份與 live DB 的時間差、唯一資料和已知 SQLite state 缺口。只查既有 metadata／manifest 與指定路徑；不做 restore、dump、全機掃描或新大型副本。
6. 哪些項目是新版必需、可獨立於 worktree 保存、僅供歷史參考，哪些待查；不要僅憑無 open files 或單次零連線判定可刪。容量以 bytes／GiB 報告，區分目錄用量、重複計算風險及實際可回收量 UNKNOWN。

限制：不建立 worktree／clone／venv，不安裝套件、不啟停或 kill 服務、不改設定／symlink、不搬移／刪除／修改資產、不渲染／推論／migration，不改 Git refs、不 commit／push／PR／merge。不修改其他聊天的檔案。缺權限或 ownership 不明就保留並列出缺口，不繞過保護。

請回覆精簡依賴表、每項 KEEP／可遷移候選／僅參考／UNKNOWN 的依據、最小後續切換與清理順序，以及精確待授權項目。標示 VERIFIED／REPORTED／UNKNOWN／MISSING，說明哪些舊紀錄已被此次查證取代。此查證完成不等於已授權刪除。先回覆結果，不覆寫既有評估文件。
```

## 10. 待定案與本文件實際產出

OPEN：逐項場景修改、最終鏡頭配置、素材規模、模型／VLM 分工與硬體、索引實作、PG 是否必要、精簡契約、驗收門檻、舊依賴退役範圍。

- 本輪只新增這份討論總結；未修改場景、safe bundle、程式、契約或其他聊天文件。
- 未建立／切換 Git branch，未 stage／commit／push，未建立或更新 PR／issue，未 merge。
- 未啟停服務、連 live DB、修改資料、渲染或推論；未執行新對話中的查證任務。
- 現有程式與本地文件已作唯讀對照；本地退役評估的服務／容量數字未在本輪重驗。
- 文件驗證採 whitespace／連結目標與內容檢查，未跑程式測試。檔案 hash 於對話交付，避免文件自我引用。

參考：[2a 交接](CONTROLLED_SCENE_BACKEND_BATCH2_20261020.md)、[現有 PostgreSQL migrations](../../src/amidst/local_storage/migrations.py)、[現有 PostgreSQL adapter](../../src/amidst/local_storage/postgres.py)。
