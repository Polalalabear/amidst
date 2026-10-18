# CS-A：受控場景可行性與契約審查

日期：2026-10-18（Asia/Taipei）。**文件審查完成；建議修訂後交使用者審 CS-A，不能當作 CS-A 已通過。**

本輪只有唯讀查核與文件提交。沒有建 `.blend`、啟動 Blender、做視線運算、渲染、讀 GT／影像／影片、改後端、啟停服務、清理資產或合併分支。繼續使用純文件分支 `codex/office-demo-rehearsal-docs`，不建立 worktree。使用者指定的現行規則以 [AGENTS.md](../../AGENTS.md) 與 [DEVELOPMENT_RULES.md](../DEVELOPMENT_RULES.md) 為準。

## 1. 審查基準與結論

| 來源 | 本次固定版本／證據 |
| --- | --- |
| Codex 提案 | [提案](../agents/CONTROLLED_SCENE_2D_TO_3D_PROPOSAL_20261018.md) @ `59b8f5d91fe35812dfe0046c67709a519b46ed1e` |
| Codex 準備 | [磁碟與後端盤點](CONTROLLED_DEMO_PREPARATION_20261018.md) @ `14a3ffbd1ed6fbef5952b3402fe46daf14be22fb` |
| Claude A 包 | [Draft #65](https://github.com/Polalalabear/amidst/pull/65)，live head `9848d5e5165f6c29555e862c32ec05646a51878b`，OPEN／Draft，base `claude/office-demo-visualization` |
| 契約 | [OFFICE_CONTROLLED_SCENE_V1.md @ 9848d5e](https://github.com/Polalalabear/amidst/blob/9848d5e5165f6c29555e862c32ec05646a51878b/docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md)，615 行 |
| Claude 回覆與 UX | 同一 SHA 的 [回覆](https://github.com/Polalalabear/amidst/blob/9848d5e5165f6c29555e862c32ec05646a51878b/docs/agents/CONTROLLED_SCENE_CLAUDE_REPLY_20261018.md)（411 行）、[UX](https://github.com/Polalalabear/amidst/blob/9848d5e5165f6c29555e862c32ec05646a51878b/docs/agents/CONTROLLED_SCENE_UX_SKETCH_20261018.md)（241 行）；只讀 Git objects，未把 Claude 文件複製進本分支 |
| 最新方向 | [#26 D25](https://github.com/Polalalabear/amidst/issues/26#issuecomment-6245364536)，本次由 `gh` 核對 |
| 人工關卡 | [CS-A #66](https://github.com/Polalalabear/amidst/issues/66)：通過前不能建 `.blend` 或渲染；本次讀取時尚無審查留言 |
| 後端查核 | `4019a44f1dc22130e7b6013179ac86c899ca1200`：C4a／C5／C4b／preset／service；`225f2461ec3b38b6855d8c6b26d4cc17cb77aaba`：launcher／rehearsal；準備文件另固定 `28f050a9c0472f33783ebfd1f15b92030d1dce44`，不宣稱這些是今天所有 PR 的最新 head |

結論：**能承接 A、B1 的小型新場景及後端工作，但這是實作可行性判斷，不是鏡頭／估計品質已通過。**採 4 台共用鏡頭、A 渲染 3 台、B1 渲染 4 台，960×540／5 fps／PNG，B2 與 10 Hz 另版。B 包可從每台一張開始；這四張只能檢查外觀、校正／輸出與初步大小，不能驗收整段覆蓋、盲區或錯開。

CS-A 定稿前要處理的主要修訂：安全／私有 manifest 分離、GT 讀取時機、可重算的 hash 規則、靜態標記的用途權限、完整鏡頭校正、同步缺格／完整性錯誤分流、RGB-only track／候選端點契約。所有下文新增欄位／端點都是**建議文字，尚未實作**；不改寫 Claude owner 的原契約。

## 2. 契約逐條回覆

每列列出對應條文及欄位；「同意」表示供應方向同意，不表示資料已存在。需改的項目均附可併入原文的建議文字。未定的數值不在本次定案。

### 2.1 標頭、§1、§2

| 條文 | 判定 | 回覆／建議文字 |
| --- | --- | --- |
| 標頭、依據與沿用契約 | 修改 | 「依據改列可取得的 Git SHA／路徑；沿用 interval／frame／blind 契約時固定修訂 SHA，`FOOT_RAY_PIXEL_BAND`、D21 及新場景覆寫條文需明列。舊 Office 的 floor、D18、annotation authority 不隨引用移入新 run。」提案已存在 Git，不宜只稱 LOCAL。 |
| §1 新獨立場景、RGB 重現、靜態校正可用、身分與物理 UNKNOWN | 同意 | 靜態背景可用核准模型；人物重現仍只能來自 RGB 證據。 |
| §1 模擬／評估資料 | 修改 | 「事件腳本只在產製隔離側生成影像；GT／遮罩等評估讀取須在輸出凍結且 hash 驗證後。正式服務不得開啟 private 檔案，亦不得以事件標籤決定排序或配對。」§8 的提前 GT 驗收另見本文件 §7。 |
| §2 長度、時間、軸、floor | 同意 | m／s／Blender Z-up，地板由資料宣告，不寫死 0 或舊 Office 高度。 |
| §2 影格對應與 fps | 修改 | 「`frame_index` 是公開的零起算 sample index；另在產製側保存 `blender_frame_start/step/fps/fps_base` 映射。run 使用半開區間，`duration × fps` 必須為整數。`last_timestamp_s` 與 `duration_s` 分欄，不能將最後一張的時間當結束時間。」 |
| §2 Hash | 修改 | 「檔案 bytes hash 與 canonical JSON hash 分名；JSON 使用固定序列化器、`sort_keys=True, separators=(',', ':'), allow_nan=False, ensure_ascii=True`，UTF-8；hash 排除自身與明列的 timing 欄位。拒絕 NaN／Infinity，明訂數值型別與陣列排序。geometry hash 另固定座標、面索引／modifier 評估及排序規則。」這與既有 `registry.content_hash` 實作對齊；不是模糊的『無多餘空白』。 |
| §2 證據狀態 | 同意 | 原始觀測、投影 sibling estimate、推論、MISSING、UNKNOWN 分開；不回填原 `world_position`。 |
| §2.1 只有 sample 時刻是觀測、2D 顯示上一格並標時間 | 同意 | `LATEST_AT_OR_BEFORE` 必須依預期 sample grid 選格，不能跨過缺失 sample 去找更舊的可用影像。 |
| §2.1 內插、盲區與時間刻度 | 修改 | 「只有同一 RGB-derived local track 且兩端有效時可做有界內插；禁止跨 MISSING／UNKNOWN／未關聯缺口。是否缺口由 RGB 記錄判斷，不讀 `designed_blind_intervals`。純播放頭是時間控制；只有由內插得到的空間刻度／幾何標 `INFERRED_INTERPOLATION`。」不能把位於盲區中的 K1 假設切片錯標為內插。 |

### 2.2 §3 Scene schema

| 條文／欄位 | 判定 | 回覆／建議文字 |
| --- | --- | --- |
| §3 五種檔案 | 修改 | 「分成 `safe_bundle/manifest.json` 與私有 production manifest；`event_*.validation.json` 不得列入正式 loader 會遞迴開啟的檔案集合。」安全 manifest 不能含事件腳本或私有 locator。 |
| §3.1 `schema_version/scene_id/scene_version` | 修改 | 「scene ID 採 `controlled-l-corridor`；初版 `scene_version: 1`，不把 v1 同時編入 ID 和版本。這是本次命名提案，依 CS-A 定稿。新增 run-level schema version。」 |
| §3.1 `length_unit/time_unit/world_axes/floors` | 修改 | 「補 `frame_id`、`floor_id` 的支撐面 point/normal、`source_static_sha256` 與已核准作用範圍；首版僅單層平面，超出範圍回 UNKNOWN。」只有 `z_m` 不足以直接產生來源綁定 Plane。 |
| §3.2 ID regex／前綴／custom property／改名／geometry 版本／不重用 | 同意 | 物件 `amidst_id` 不靠顯示名稱；ID 重複使匯出無效；跨檔案引用也須存在且類型相符。 |
| §3.3 `id/class/source_mesh/geometry_version/geometry_sha256/bounds_m` | 修改 | 「保留欄位；增 `source_object_id`、`geometry_ref`、`geometry_encoding_version` 與 `transform_applied: WORLD_METRES`。hash／bbox 本身不能提供 EXACT_MESH 碰撞或靜態 raycast 幾何。」`source_mesh` 僅供追溯。 |
| §3.3 `authority/display_only` | 修改 | 「`ANNOTATED_AT_CREATION` 表示來源方法；另外宣告 `allowed_purposes`、`approval_status`、`scope_ref`、`approval_ref/sha256`。建立時標記不等於所有用途已核准。`display_only=true` 優先拒絕 walkability／occlusion／collision。」 |
| §3.4 `id/floor/support/polygon/holes/status/connections` | 同意 | 標記為新場景唯一推論用 map；未知地面保持 UNKNOWN；connection 必須對稱、portal 有效，交疊轉角需有一致 union／歸屬規則。 |
| §3.4 `approval` | 修改 | 「未跑驗證時 `verified_by: []`、`verification_sha256: null`，另列 `status: NOT_EVALUATED`；執行後才填 verifier 版本、輸入 hash 與報告 hash。K7 的 private route 報告只留私有端，推論可讀收據只含不洩漏路線的靜態核對結果。」不能預填 C7、K7 都已驗證。 |
| §3.4 不一致時改 UNKNOWN | 修改 | 「validator 不自動改檔；輸出 fail／UNKNOWN 報告。consumer 在不一致 scope fail closed；人工修訂須產生新 map 版本與 hash，舊檔不變。」避免『不自動修改』與『改標』矛盾。 |
| §3.5 `id/footprint/height/role/collision_scope/clearance_basis` | 修改 | 「補 `floor_id/base_z_m/geometry_ref/geometry_sha256/body_policy_ref/sha256/allowed_purposes`。EXACT_MESH 必須解析到實際 mesh；FOOTPRINT_EXTRUDED 只證明該近似的碰撞範圍，不能宣稱精確遮擋；角色 DISPLAY 不進物理判斷。」高度／footprint 不足以描述門洞。 |
| §3.6 門 `opening/connects/state/used_in_first_round` | 修改 | 「補 `floor_id`、開口底高、幾何／版本與可用 purpose。`via_portal_id=null` 僅用於已核准的連續地板接界，不代表自動穿牆。固定開門是公開靜態狀態，動態門不在首版。」 |
| §3.6 樓梯 | 修改 | 「樓梯獨立分型，需多層端點／支撐面與幾何，不套 2D 門洞 schema。首版 `stairs: []` 可接受；若有預留實體，`used_in_first_round=false, acceptance=NOT_ACCEPTED`，不進首版路徑。」 |
| §3.7 校正全部欄位 | 修改 | 使用本文件 §3 的映射；補 pixel origin、pixel aspect、render percentage、lens shift、floor／zone、camera model／靜態有效性、schema version。`clock` 不放進可跨 run 共用的 optical calibration hash；run camera binding 另 hash。 |
| §3.8 `event_*.query.json` 全部欄位 | 同意 | `event_id` 僅作 UI 選項／定位該 run；server 從 catalog 解析 source/run/clock。`suggested_queries` 只是預填，不參與配對或 rank。安全檔不能含 actor 數、路線、覆蓋窗或 blind 答案。 |
| §3.8 `event_*.validation.json` 全部欄位 | 修改 | 「全部放 private，新增 schema/source/run/clock/hash；觀察窗需明確列 full-body／foot／partial 與幾何範圍。`cameras_expected_blind` 列明該 run 的相機 ID。時間、間隔、像素門檻均待約定；不進 runtime readiness。」 |
| §3.9 `persons.sim.json` 全部欄位 | 同意 | 只供隔離產製／凍結後評估；固定 2 人是情境設定，不能用來限制偵測數、替人物命名或挑 prior。種子不進正式推論輸入。 |
| §3.10 manifest 的 source／script／config／seed／files／rgb_index／provenance | 修改 | 「安全端只列 allowlisted static/camera/RGB index 與公共 config hashes；generator script/config/seed、validation／GT 檔案清單留 production manifest。safe provenance 可持有不透明 source hash，但不得 resolve private 內容。」`files.side` 只是標籤，不足以構成隔離。 |

### 2.3 §4、§5 情境

| 條文 | 判定 | 回覆／建議文字 |
| --- | --- | --- |
| §4 資料目錄／一份 RGB／不進 Git／不輸出 depth | 同意 | 實際根與檔名見 §5；新根目前只作設計確認，不建立資產。derived 不作觀測，GT 不進 media allowlist。 |
| §4 磁碟預算 | 同意 | A＋B1 550 PNG，0.133–0.398 GiB 是外推、不是新場景實測；1.5 GiB 是資料及 staging 峰值額度，不包含 OS swap。 |
| §5.0 5fps-v1／10hz-v2 | 同意 | fps、解析度、格式依使用者決定。10 Hz 新 run、新 sampling/hash/pin；不覆寫 5 fps，也不自動產生。 |
| §5.1 走廊／房間／portal／AREA 尺寸 | 修改 | 「作為起始候選幾何，不記 VERIFIED；補牆厚／高度、portal 開口、正式支撐面與幾何檔。轉角重疊地板不得重複計面積或建立矛盾連通。」尺寸可建，視野尚 UNKNOWN。 |
| §5.1 四鏡頭、朝向與預期地面範圍 | 修改 | 「位置／朝向是初始值；完整 rotation、K／FOV 與 clip、R102 精確 pose 尚待供應。靜態 footprint 僅供建議鏡頭；不能以地面看不到證明整個人物不可見。」轉角不增加鏡頭。 |
| §5.1 `BLIND_CORNER` | 修改 | 「列成非矩形 L 形空間的明確 polygon／holes；驗收需核對頭／軀幹／腳的實際 RGB，不只 C5 地面足跡。private 預期盲窗不供推論。」不能用一個跨牆矩形當可走盲區。 |
| §5.2 A 人數／直線／10s／3 台／目標／對照鏡頭 | 同意 | A 不呼叫 C4b，不含 CAM_N1；query 表格的 A 範例也須刪掉 CAM_N1（Claude 回覆 Q2 與自己鏡頭表不一致）。 |
| §5.2 全程覆蓋與雙鏡重疊 | 修改 | 「全程逐 sample 至少一台 RGB 可見；目標區域雙鏡的 full-body／foot 規格由使用者在 CS-A 定稿前選。圖中地面範圍只作假設，不是覆蓋證據。」不能由 bbox 底邊推定腳可見。 |
| §5.3 B1 人數／路線／20s／4 台／查詢 | 同意 | 兩人錯開、不交會；P1 轉角盲區、P2 進 R101；名義時間算術見 §4，不輸入系統作查找答案。 |
| §5.3 盲區／錯開／房內消失 | 修改 | 「全身不可見與同影格至多一人均須逐 sample RGB 核對；無室內鏡頭不代表門外鏡頭看不到門內。北端 y=11–11.5 的末段須補覆蓋或另列預期狀態，不能默認只有轉角缺口。」 |
| §5.3 負證據限制 | 同意 | P2 出現在影格時對整張 frame 為 DETECTION_PRESENT；未偵測特定人不等於 whole-frame NO_DETECTION。保留 D21 strict／suggestion 與可偵測性區別。 |
| §5.4 B2 | 同意 | B2 另規格化與驗收；B2 通過前 AMBIGUOUS_MERGE 不得作可用端點／位置，B1 不宣稱交會能力。 |

### 2.4 §6 Consumer API

| 條文／欄位 | 判定 | 回覆／建議文字 |
| --- | --- | --- |
| §6 共通 response | 修改 | 「五個 API 均補 schema_version、server-resolved source/run/clock/sampling、scope/hash、完整 provenance；不回傳 session secret／private locator。例子若省略欄位，標 NON_EXECUTABLE_EXCERPT。」省略的 provenance 不可當正式可驗證 payload。 |
| §6.1 Request 所有欄位 | 同意 | region ref／polygon 二選一、單 floor／frame／m、時間半開區間、catalog 子集、模板 PASS_THROUGH／ENTER_EXIT、政策／cursor 版本化；session／run 權限由 server 核對。polygon 數量上限待約定。 |
| §6.1 `status/reason/query_id/resolved_scope` | 修改 | 「補 `query_sha256`、`candidate_snapshot_sha256`、RGB index／感知版本（如使用）與 request 正規化規則。輸入的 run_id 只能選擇已註冊 run，不能自訂 source pins。」 |
| §6.1 relation／排序／reason／paths／geometry | 修改 | 「三個已知 relation 可沿用；另設 `relation: UNKNOWN`，不能把 metadata 缺失判 NO_INTERSECTION。v1 建議排序僅 relation_tier → overlap_area_m2_desc → camera_id，偵測數留診斷欄位；Q4 待使用者確認。」已知不相交鏡頭仍保留。 |
| §6.1 `image_evidence` | 修改 | 「無感知時 `frames_with_detection:null`、`perception_status:NOT_EVALUATED`，不是 0；列 `evaluated_frames/frame_records_read/count_complete`。不要求定位或 tracking 已成功，候選幾何查詢仍可回答。」 |
| §6.1 availability／總數／cursor／complete／truncated／unknown | 修改 | 「`candidates_total` 是目錄限制後集合，`returned_count` 是本頁；完整性表示全集合已檢視，分頁仍可 complete；`truncated` 只表示因預算無法完整求值，`next_cursor` 表示還有頁。metadata 未知列入 unknown，不省略。」 |
| §6.1 recommended／layout／stats | 同意 | 推薦只是顯示子集；不足留空、不跨 run 湊格；latency 排除 hash。全目錄沒有定位也可查；查詢不讀 private 驗收。 |
| §6.2 與 C5 建議影格分開 | 同意 | 同步 API 是時間點查格，不能用 C5 的最多 64 張建議影格當影片完整播放。端點／8 格見 Q5／Q13。 |
| §6.2 `frame_index/delta/tolerance/frame_rule/tiles` | 修改 | 「用 sampling 的有理 grid 找預期 index；缺該 sample 就 MISSING，不能回退到較早可用影格。增加 `expected_timestamp_s`、`sample_age_s=t−timestamp_s`、`clock_error_s`；sample age 不等於同步誤差。邊界與容差在設定檔約定，不偷偷加 epsilon。」 |
| §6.2 READY／MISSING／OUT_OF_RANGE，hash mismatch 範例 | 修改 | 「加入 UNKNOWN／完整性錯誤分支；檔案缺失為 MISSING，hash/source/pin 不符為 DataIntegrityError（沿用 `RGB_RECORD_HASH_MISMATCH` 等原因），該 run fail closed，無 media token，不 downgrade 成一般缺格。」這與既有完整性規則一致；UX 圖例同步修改。 |
| §6.3 estimate／observation／camera／time／local track／heading | 修改 | 「POINT／SEGMENT 都用完整 interval schema；SEGMENT 欄位是 `near_m/far_m/raw_near_m/raw_far_m`，不是例子的 `a_m/b_m`。補 floor/calibration/frame 及 RGB ref/hash；heading 無 track 或方向有歧義時 UNKNOWN。」區間差分不能任選中點假裝方向。 |
| §6.3 `ground_estimate` 與既有資料 | 同意 | 保留 contact_quality、constraints、authority、identity／physical verdict、provenance/hash；原始 MISSING/null 不能因 sibling estimate READY 被改寫。 |
| §6.3 display／尺寸／區間門檻 | 修改 | 「display 是 UI 設定且另有 config hash；不從 `persons.sim.json` 取尺寸／姿態。per-run 公共人體 prior 須在評估前宣告，適用所有 RGB 元件，不依 actor ID 選。長區間不放中點人形。」現有 D5 常數不是新場景已通過門檻。 |
| §6.4 OBSERVED／CONNECTOR／BLIND／MISSING／PREDICTION | 修改 | 「OBSERVED 只存離散時間戳的區間序列，任何跨 sample 幾何屬 CONNECTOR；盲區保留 K1 多解／未關聯基線，不能指定 actor。MISSING_GAP reason 不用 hash mismatch；完整性錯誤中止載入。PREDICTION 仍留 D 包。」所有連接是虛線，單筆橫向區間可為實線。 |
| §6.4 `support_refs/time_highlight/hypothesis hash/association` | 修改 | 「補 candidate_ref/local_track refs、支持結果 hash、地圖／政策 pins 與 scope；只有合法同 track 兩端才能連接。hypothesis 切片維持 INFERRED_HYPOTHESIS，純時間高亮不能把它改成內插。B1 不能把兩個人連成已確認身份。」 |
| §6.5 pick／nearest／other／relation／jump | 修改 | 「每個 ref server 核對 scene/run/clock/output hash，segment_index 指向該版本；`delta_s` 改名 `support_offset_s=timestamp_s−t_click_s`，與播放器 age 分開。等距時按 timestamp、camera_id、observation_ref 決定，避免不穩定。」 |
| §6.5 五種點擊行為 | 同意 | 觀測回自己的 frame；連接列兩端；盲區列端點／負證據不自動跳；NO_SUPPORT 不跳。禁止自動補 GT／鄰近 run。 |

### 2.5 §7、§8、§9、§10

| 條文 | 判定 | 回覆／建議文字 |
| --- | --- | --- |
| §7 每類資料的可讀邊界 | 修改 | 「safe RGB／已核准 static／calibration／static-only index 可讀；query 只預填；validation、actor／route／seed／mask／GT／depth 全不讀。CS-B 不得在輸出凍結前讀 GT，見 §7 的待決衝突。」靜態 raycast 不讀含人物的 evaluated scene。 |
| §7 拒絕 private 路徑／禁用欄位 | 修改 | 「採遞迴 allowlist、realpath containment、拒 symlink／穿越；不靠敏感欄位黑名單或目錄名稱 alone。安全 manifest 不得 resolve 私有 script／config。錯誤碼見 Q6。」 |
| §7 預填／手動逐位元相同 | 修改 | 「同一正規化 query、snapshot、page／layout、session scope 下比較 canonical semantic payload/output hash；latency 不同可排除。`query_id` 由 hash 導出，不隨機；不得因 preset／手動來源產生不同排序。」若要求完整原始 HTTP bytes 相同，與 latency 欄位矛盾。 |
| §7 GT 面板 | 同意 | 只在凍結後獨立 EVALUATION 面板；正式播放無 GT fallback。 |
| §8 座標／標記／walkable／camera／來源／sampling 驗收 | 同意 | 場景與正式估計分欄；validator 零 schema 錯誤不等於幾何／品質通過。所有尚未跑的項目 NOT_EVALUATED。 |
| §8 覆蓋／blind／錯開／人物 | 修改 | 「CS-B 的 RGB 驗收與凍結後 GT 指標分列；同一相機單人不證明身份關聯。body policy 是預宣告設定，實際接地／淨空通過另證明，未使用 scope UNKNOWN。」 |
| §8 缺影格／GT 隔離／內插／點擊／綠球 | 修改 | 「一般缺檔 MISSING，完整性錯誤 fatal；內插只指推得的幾何。新增禁用目錄／欄位注入、無定位候選查詢、分頁不漏、無 silent truncation、B1 不錯連、原資產不變檢查。」數值門檻仍待約定。 |
| §9 待決問題 | 修改 | 實際有 CS-Q1–CS-Q14，共 14 題（不是任務摘要所稱 11 題）；逐題答覆見 §6。使用者決策題保留 OPEN，不冒充同意。 |
| §10.1 已對齊表 | 同意 | 半開區間、A 3 台、550 張、一份 RGB、候選欄位、未物化 track、多人負證據、同步／suggestion 分開皆同意。 |
| §10.2 差異與準備文件八點映射 | 修改 | 「以本文件 Q1–Q14 回覆更新；Q14 不得讀情境驗收 private 檔，改 safe technical readiness profile。舊 proxy 排除與新 authority adapter 分開處理，不僅是換資料根。」 |

## 3. 校正對應與缺少的可供應欄位（CS-Q1）

本次只讀既有 `data/engineering/office_person_20261016_v1/office/safe_inputs.json` 的 camera/floor metadata，沒有開啟任何媒體。既有 `Camera` 的欄位與 `geometry/calibration.py` 顯示可沿用投影核心，**新 JSON 不能直接送進舊 strict schema**，需顯式 adapter：

| 新契約 §3.7 | 既有輸入／處理 |
| --- | --- |
| `camera_id` | `calibration.camera_id`，外層另有 `camera_ref/authority` |
| `matrix_world` | `camera_to_world`，4×4 row arrays，世界公尺；不 transpose、不再縮放 |
| 新 convention 名稱 | 映射到既有 `convention: BLENDER_NEG_Z_UP_Y`；相同 -Z forward／+Y up 語意，先核對 rotation／determinant |
| `intrinsics.fx_px/fy_px/cx_px/cy_px` | `fx/fy/cx/cy`，沿用 `pixel_origin: TOP_LEFT_CONTINUOUS`，不能另加 0.5 pixel |
| `image_size_px` | `width/height`；補 `pixel_aspect_xy`、render resolution percentage；K 必須對應實際 PNG |
| `sensor_fit/sensor_width_mm/focal_length_mm` | 舊 safe camera 沒有這些欄位；新 exporter 可供應，搭配 shift／sensor height 作產製追溯，正式定位以核對後 K 為準 |
| `clip_m` | `clip_start/clip_end`；同 m，不沿用 Office 24.7 m 數字 |
| `distortion:null` | 明定針孔；新 adapter 驗證後省略舊 Camera 不接受的額外欄位 |
| `floor_id/zone_id/meters_per_unit` | 補齊，`meters_per_unit=1.0`；floor plane point/normal/source hash 另綁定 |
| `clock/valid_time_range_s/visibility_index_ref` | 不是 optical camera 欄位，放 run-camera binding；static pose validity 另定，跨 A／B1 共用光學校正，clock 不共用 |
| `calibration_sha256` | 固定 canonical optical payload hash；safe inputs file hash、camera binding hash、source hash 各自保留 |

新契約還缺的欄位分成三側，避免為了 readiness 洩漏答案：

| 側別 | 最小補件 |
| --- | --- |
| Safe static／public config | AREA／ROOM／CORR 的實際 polygon 與 floor／關聯、walkable 實際 geometry refs、purpose approval、portal opening、地圖未知範圍、body prior／detector config hash；只列 ID 表不足以解析選區與通路 |
| Safe run／runtime | `schema_version, run_id, clock_id, duration_s, sample_count_per_camera, last_timestamp_s, sampling_version, rgb_index_sha256`、camera catalog/calibration refs、expected-grid/missing records；`technical_readiness_profile` 只含 grid／hash／API availability，不含人物預期位置、盲窗或配對 |
| RGB-derived output | local-track schema／producer version／config hash／support refs、association candidate 與未關聯基線、endpoint eligibility、full interval schema、per-result seals；讀不到即 null／UNKNOWN，不填 actor ID |
| Private production／evaluation | Blender frame mapping、完整相機 rotation／R102 pose／lens、walls/portal 詳細 geometry、A 重疊的可見部位、逐段時間及端點、B1 stagger 規則、作者路線與產製設定、validation policy／hash；GT/mask 評估載入時機另見 §7 |

## 4. Q2 場景可行性：可建，但覆蓋尚 UNKNOWN

以下只對提案座標做紙上距離／時間算術，不是 Blender 視線測試，不產生新的接受門檻。1.3 m/s 為原提案的名義速度：

| 檢查 | 算術與判斷 |
| --- | --- |
| A 直線 | 13 m／1.3 = 10 s；目標 x=6.5–9.5 對應 t≈4.231–6.538 s。取樣 0–9.8 s，不存 t=10，最後 sample x=13.74；x=14 是半開區間終點，不應要求已有該 PNG。 |
| B1 P1 | 水平 15.2 m＋北向 10.3 m = 25.5 m，約 19.615 s 可到 (16.2,11.5)，剩餘時間停留／出場方式需明定 private 設定。 |
| 名義 corner window | 到 x=14.5 約 10.385 s；轉角點約 11.692 s；到 y=3.5 約 13.462 s。約 3.077 s 只是地面 FOV 假設下的幾何算術，不是人物已不可見或指定 sample 全盲。 |
| 名義錯開 | W1：P1 到 x=9 約 6.154 s，P2 t≈8 才進場，名義間隔≈1.846 s。W2：P1 x=14.5 約 10.385 s，P2 x=6 約 11.846 s，間隔≈1.462 s。兩者都未驗證 RGB／腳步動畫／身體輪廓。 |
| P2 | t=8＋7/1.3≈13.385 s 到 x=8；再南向 3.7 m，約 16.231 s 到 (8,-2.5)。門洞 y=0 的名義穿越約 14.308 s；進房後仍可能透過門被 W1/W2 看見。 |
| 北端缺口 | CAM_N1 提案地面視野只到 y≈11，但 P1 到 y=11.5。約 19.231 s 後的覆蓋未交代，不能宣稱唯一缺口在轉角。 |
| 轉角的「盲」 | 無轉角鏡頭只是必要配置；頭部可能仍在 W2/N1 視野。C5 的嚴格可偵測足跡以外也不能反推「沒人看得到」。須完整 static pose/lens、實體牆，及後續 RGB 驗收。 |
| 全身／腳點 | 2.8 m 高且起點距 W1 水平僅 0.7 m，近端人物是否出框取決於 pitch/FOV。只寫朝 +x／−x 不足以算可行性。CS-Q3 未決前不承諾全身／腳點皆符合。 |
| 人物可分離 | B1 的時間錯開有利於 local tracking，但不能用腳本把 N1 的再現直接認成 P1，亦不能把 P2 接到 P1。無唯一 RGB 證據就保留多候選或未關聯。 |

可實作方向：保留四鏡頭 ID 與轉角無鏡頭，優先在 B 包調整 pose／FOV／必要的靜態遮擋結構來滿足使用者選定規格；任何實質改變場景／事件範圍先回到契約審查。不因名義視野不成立就加第五台或自行縮短盲窗。所有具體鏡頭覆蓋保持 `UNKNOWN`，尚未做 source geometry、raycast 或 RGB 實驗。

## 5. 新資料根、run ID 與 B 包最小版

### 5.1 位置與命名確認（設計值，未建立）

採內建磁碟既有 `data/pilot` 下獨立根：**`/Users/polalabear/Developer/amidst/data/pilot/controlled_scene_v1`**。啟動端以 checkout-relative `data/pilot/controlled_scene_v1` 解析，不把這台機器的絕對路徑寫進公共 payload。此位置是 canonical，safe bundle 也留根內，不另在 engineering 複製 RGB。Claude 回覆「不放共用 checkout」應改為「不追蹤 Git」；指定根位於既有 checkout 的 ignored data 範圍，本次沒有新建 checkout。

```text
data/pilot/controlled_scene_v1/
  assets/controlled_scene_v1.blend
  runs/<run_id>/
    rgb/<CAM_ID>/frame_<frame_index:06d>.png
    safe_bundle/manifest.json
    safe_bundle/scene_static.json
    safe_bundle/cameras.json
    safe_bundle/event_<A|B1>.query.json
    safe_bundle/rgb_index.json
    safe_bundle/runtime_profile.json
    safe_bundle/outputs/                 # 後續凍結的 RGB-derived outputs
  private_evaluation/<run_id>/
    production_manifest.json
    event_<A|B1>.validation.json
    persons.sim.json
    gt/                                 # 未產生；不得 resolve 到 safe side
  derived/<run_id>/                      # 明列版本與用途的 optional cache
```

- run ID 規則：`ctrl-lcorr-s<scene_version>-<a|b1|b2>-<sampling_version>-r<revision:03d>`。第一版保留名稱 `ctrl-lcorr-s1-a-5fps-v1-r001`、`ctrl-lcorr-s1-b1-5fps-v1-r001`；這些是**預定 ID，不是已存在 run**。
- 10 Hz 改用 `…-10hz-v2-r001`；改影像、camera、產製設定或 source 都產生新 revision／必要時新 scene version，不能就地覆寫已封存檔。scene ID 為 `controlled-l-corridor`，與 scene_version／run_id 分開。
- clock ID：`clock:<run_id>`；同 run 的相機共用一個 sample grid，A／B1 不共用 clock。公共 frame ref 由 source/run/clock/camera/index/hash 產生，不暴露本機路徑／actor ID。
- A 每台 index 0–49、B1 0–99；檔名如 `frame_000000.png`、`frame_000049.png`。PNG bytes hash 存在安全 index；index 以相對 RGB ref 綁定 canonical 檔，不以 symlink 或再複製達成。
- source `.blend` 一旦封存不覆寫；若重新設計需 `controlled_scene_v2.blend` 或明確新版本檔。不觸碰舊校園／Office 資產。
- server 只解析註冊 run 的 safe manifest；media allowlist 逐項解析該 run 的 `rgb/<CAM_ID>/frame_*.png`，拒絕 symlink、越界、private_evaluation／derived、hash 不符。不把整個 CONTROLLED_DATA_ROOT 暴露成靜態目錄。
- 後續可增 `CONTROLLED_DATA_ROOT` 設定，但需明確分開 assets／safe／evaluation 三種 root；不能只把 `OFFICE_ASSETS_REPO` 換成新根就認為現有 loader 可用。本輪不改環境變數或 loader。

### 5.2 B 包可以從「每台一張」開始

**同意，且這是 B 包第一個有界交付。**順序為 CS-A 人工核准、另行授權 B 包 → 生成獨立場景與 static/calibration → 隔離 preview run `ctrl-lcorr-s1-preview-5fps-v1-r001`，四台各一張 → 回報外觀、校正、每張 bytes／hash、磁碟及標記檢查 → 再核准 A 全段 → 再 B1。preview manifest 標 `purpose: CALIBRATION_PREVIEW, complete: false`；不能假扮 A/B1 完整 run，亦不能由它凍結預測。

四張可選各鏡頭適合觀察的一個產製 sample；選樣與 actor 產製設定只在 private 端，正式推論沒有預先答案。不能只渲染所有鏡頭的 t=0，便認為已看過北走廊人物、雙人錯開或全程盲區。

本次 `df -k .`：available **17,720,472 KiB = 18,145,763,328 bytes ≈16.900 GiB**，比準備文件當時的 11.236 GiB 高；只反映可變快照，不推論釋出原因。維持資料＋staging 約 **1.5 GiB** 的已定規模，A/B1 分批、只有一份 RGB、預覽／cache 不預先全生。沿用準備文件的 **12 GiB 起跑目標／8 GiB 停止參考只是既有規劃建議，未實作且不在本次定成新驗收數字**；CS-Q11 仍需在授權 B 包時確認。現在不因空間較多就渲染、升規格或清理。每批重查 free、實際累積 bytes 與 swap；接近產出額度就停下重估，不自行刪資產騰空間。

## 6. 契約 §9：CS-Q1–CS-Q14 全部回答

| 問題 | Codex 回覆／處置 |
| --- | --- |
| CS-Q1 校正 | **修改後可沿用核心**；完整映射見 §3，光學校正與 run-clock 分離，明示 pixel convention；新 schema 不能直接丟舊 loader。 |
| CS-Q2 資料根 | **確認設計位置**為 §5 的 ignored `data/pilot/controlled_scene_v1`，只存一份 canonical RGB；新 allowlist／loader adapter 後續實作，private 不可讀，不保證今天直接可用。 |
| CS-Q3 A 重疊可見部位 | **OPEN／使用者決定。**建議目標區域雙鏡「全身可見且接地部位可核對」，有利於影像驗收；若選腳點版需明定可見範圍，不能稱全身驗收。當前不自行選定，也不以 bbox 下緣當腳。 |
| CS-Q4 偵測數排序 | **建議 v1 不列 rank key，待使用者確認。**用 relation／面積／camera_id；偵測數作附帶證據且標 evaluated/count completeness。理由：未評估、採樣密度及鏡頭 FOV 大小會改數量，無定位候選查詢也應穩定；不是身份或經過機率。 |
| CS-Q5 端點 | **新端點建議定為** `POST /api/candidate_cameras`、`/api/synced_frames`、`/api/person_layer`、`/api/curve_layer`、`/api/evidence_lookup`，皆沿用 session/scene/run guard；不把新 payload 塞進舊 D18 `target_reconstruction`／舊 timeline。後端內部可委派舊核心。端點是待 CS-A 確認的介面設計，尚無 implementation。 |
| CS-Q6 GT 錯誤碼 | 建議 `FORBIDDEN_INFERENCE_INPUT`（HTTP 422，禁用／額外欄位）；`FORBIDDEN_DATA_SCOPE`（HTTP 403，服務端拒絕 private／GT locator）；sealed file/source/hash 錯誤沿用 `DataIntegrityError` 與具體 reason，run unavailable。先 schema/path guard 後 IO，不能在開啟 GT 後才回錯；錯誤不回顯私有路徑。 |
| CS-Q7 C5 上限 | **保留舊限制，不為新 Demo 全域放大。**5 fps B1 400 records 在 512 內，但 64 returned suggestions 仍不等於 400 可全部回傳。10 Hz 800 需有穩定 snapshot 的半開時間分窗／camera batching，跨窗去重 frame key、聚合完整性；cursor 綁 query/index/sampling/pins。新批次也要整體 budget/deadline，數值待約定；不能以無限分頁繞過上限。同步播放走 Q13，不消耗 C5 suggestion cap。 |
| CS-Q8 多組端點 | **同意新 adapter，保留舊 D18 guard 原樣。**A 不呼叫；B1 由 RGB local-track 結束／開始生成候選端點組，附兩端 ref/hash/clock/eligibility、candidate_ref、未關聯基線、多解與全路徑時間／速度檢查。別人的觀測不再是全域 interval 阻擋；同一候選若有中間支持應分段，不跳過。配對不讀 actor／事件盲窗；沒有合法端點就 UNKNOWN。Claude 起草純候選介面、Codex 接 adapter。 |
| CS-Q9 門檻 | **全部仍 OPEN／凍結前由使用者約定。**同步誤差與 sample age 分開、interval 人形門檻、通路距離、B1 間隔、召回／涵蓋、polygon 數量、tracking gap／速度／方向條件、批次預算等寫版本化設定。若門檻影響鏡頭／場景設計，生成前先取得該項決定；不看新 GT 後倒調。 |
| CS-Q10 local track／association | **Codex 主責 RGB-only local tracking／感知 wrapper；Claude 主責可分離純關聯候選介面及演算法，Codex 整合。**local track 最小含 source/run/clock/camera、opaque local_track_ref、ordered observation/frame refs、sample indices/times、gap/termination/ambiguity reason、producer/config/output hashes；不跨鏡頭升成身份。跨鏡頭 candidate 含 endpoint track/obs refs、eligibility、alternatives/unassociated、evidence refs、scope/config/hash。無 track：heading UNKNOWN、不連曲線；沒有 GT 選 prior。 |
| CS-Q11 磁碟 | **舊 11.2 GiB 已過時**，本次約16.90 GiB，高於先前建議目標但非資源保證。保留1.5 GiB產出規模；不清理、不改門檻，授權 B 包前再查並確認 runtime gate。新場景 RAM／swap／耗時 UNKNOWN。 |
| CS-Q12 無定位查詢 | **同意解耦，但更正修改位置**：`TimeFrameIndex(records)` 本身只需 metadata；依賴 `_ground_estimates` 的是 `FrameRetrievalIndex` 初始化／provenance 抽取。新 candidate loader 從 safe catalog/run config 取 provenance，先建 metadata index，感知／定位 enrichment 可選；不為湊 provenance 造假 estimate。 |
| CS-Q13 8 格 | **UI fixture 先驗收 8／>8，真實只3／4台。**新 synced endpoint 每次請求最多畫面容量8台（1/2/4/8是使用者既定容量），單 run/clock/timestamp、逐 tile 回預期 index與狀態；>8用目錄分頁並保留全集合。不要平行打兩次舊 timeline 後假裝同 snapshot；未來真實 >4 camera batching 另訂整體 budget/一致性測試，不在 B 包多建相機。 |
| CS-Q14 wrapper 寫死 | **必改，且不能讀 private 情境驗收表。**讀 safe manifest `sampling/duration/camera_ids/rgb_index` 與 `runtime_profile` 的技術期望；人物可見性、盲窗、正確配對留私有評估。逐檔改造與工時見 §8。 |

## 7. CS-A 尚須記錄的決策與關卡

1. **GT 時機存在實質衝突**：使用者本次 D1 限制為凍結後評估；#65 §8 卻讓 CS-B 讀 GT／mask，而 CS-B 說通過前不得凍結。安全建議文字：「CS-B 以 RGB 人工逐格核對覆蓋／錯開、靜態標記／校正核對及產製完整性通過；GT/mask 數值評估延至輸出凍結後。產製側可依腳本生成 RGB，但不把腳本／GT 當正式系統輸入。」若仍要 CS-B 提前讀 GT，需使用者另行改訂邊界；本次沒有這項授權，也沒有讀 GT。場景設計文件描述作者路線不等於正式推論可讀。
2. **需使用者選擇**：CS-Q3（A 的可見部位）、Q4（是否納入偵測數排序）。Q9 數值統一列 OPEN，依其影響在生成／凍結前約定；本次不發明通過數字。
3. **Claude 契約補件**：依 §2 修訂安全／私有 manifest、hash、校正、purpose、同步與曲線狀態；補 RGB track／候選端點 contract，原檔仍由 Claude 維護，不以本文件當已自動接受。
4. **CS-A #66**：本文件是待人工審查結果，不發 approval、不 merge。**CS-R** 依 Claude 回覆 §3 第6項已定為「先核准合併」；新 API 依賴前須有明確 reusable-module merge/commit baseline，本次不替代為擅自堆疊或實作。CS-B、CS-C 及 CP4 依 D25 的新 Demo 範圍；CP2/CP3 暫停，舊分支／PR 全保留。綠球移除留後續前端小任務，不混入此文件工作。

## 8. 後端重用／wrapper 工作量估計

估計單位為**一位開發者的工作日區間**，含該包 focused verification／文件；是規劃估算，不是承諾日期或已完成工作。不含 Blender 建場景／渲染等待、Claude UI／純演算法／獨立評估、人工關卡等待與 B2。CS-R baseline 未定與 RGB 品質可能影響工時。

| 包／單一 owner 檔案集合 | 重用核心與需改 wrapper | 後續 focused verification 範圍（本次未執行） | 估計 |
| --- | --- | --- | --- |
| C4a：`src/amidst/engineering/hybrid_contact.py`，新 controlled config/adapter | 射線／plane／foot band／區間及eligibility核心可用；改新source/run/floor/camera/body宣告；`SourceClip.tier == SOURCE_DERIVED` 的舊guard不能偽標新annotation，需新受控且核准purpose的adapter／版本分支；不能把舊proxy升權；保留原觀測與interval seals、D8。 | 校正映射、foot band、未知floor/purpose拒絕、完整interval與舊guard不變；對應 hybrid contact focused tests。 | 1–2 |
| 感知與local-track：`perception_v2.py`、`contact_scene.py`、新RGB-only tracker | RGB尺寸/hash與detector可用；按鏡頭有界處理，避免同時堆疊多路；原`_local_tracks=()`和`enable_reconstruction=not self._v2`不能直接開旗標假裝已有motion。新增interval-aware local-track/heading及ambiguous斷線。 | 無GT／actor／script注入、兩人錯開不錯連、缺格／未知／merge斷線、無track圖層、受限RAM資料流。 | 2–4 |
| C5 static index：`export_floor_visibility.py`、`build_floor_visibility_index.py`、`geometry/floor_visibility_index.py` | D21 strict／suggestion、static calibration與detectability core可用；新annotated map/實體mesh/用途輸入、floor/body/config pins及新版index。export只能讀隔離static集合，annotation proxy排除不可直接照搬或全面解除。 | static-only資料流、map/hash/floor/authority、strict與suggestion分離、UNKNOWN保留；不把index當全身盲區證明。 | 1–2 |
| C5 metadata／candidate：`workbench/frame_retrieval.py`、新candidate adapter、`service.py` request/route | bisect time-index可用；移除`FrameRetrievalIndex`取第一筆`_ground_estimates`當provenance；新polygon/通路policy/候選完整性/穩定rank/cursor/seal，未定位也可查。 | 空estimates、缺index、unknown relation、預填等價、catalog分頁不漏／不重、無私有欄位。 | 1.5–3 |
| C5 retrieval wrapper：同上 Codex owner file set | 保留4 cameras／20s／64 suggestions／512 records／5s的舊路由；新schema轉接半開窗、frame keys去重、回報count與截斷；10Hz另版才做有界aggregate。 | 5fps B1 400 records、超64明示、超512 fail closed、跨窗去重、mixed DETECTION_PRESENT不可負證據。 | 0.5–1（5fps）；10Hz另加0.5–1.5 |
| C4b：`workbench/blind_hypothesis_integration.py`、新controlled adapter | 重用K1/K5 pins/freshness/seal與三模式概念；舊D18 fixed pair／two-camera／interval-any-observation guard保留舊run。新candidate-scoped多組端點，不讀private blind窗；A bypass，B1只接合法RGB端點；Claude owner K1/K5/K8c不在本包改。 | 舊D18拒絕回歸、新兩組端點、他人觀測不全域阻擋、同候選中間觀測分段、無合法端點UNKNOWN／無GT替代。 | 1.5–3 |
| 同步／圖層／證據 API：`service.py`、controlled scene adapter | session/role/media核心可用；新增五端點契約轉接、person/curve/evidence refs；解除舊最多4台的UI依賴，用獨立synced endpoint；舊8–16診斷FrameWall不改名冒用。 | 單run/clock/grid、缺格不回退、hash fatal、8台fixture、interval不取中點、pick只解當前sealed版本。 | 1.5–3 |
| preset：`scripts/office_demo_backend.py`、新fixture/config/pins | catalog/optional unavailable/hash驗證可用；把`len(frames)==100`、`assert len(assets)==100`、`5Hz`、`[0,9.8]`、固定hybrid檔改受控manifest adapter（A150/B1400；每台50/100）。新default明確，缺資料不回舊Office當成功；actual expected grid逐台核對。 | 新default缺失fatal、optional unavailable隔離、hash/source/pin fatal；不把duration當last timestamp；原preset行為保留。 | 0.5–1.5 |
| launcher：`scripts/start_office_demo.py`、`start-office-demo.command` | 動態port、PID/cwd/start identity、鎖與fingerprint核心可用；移除新run路徑上的`len(frames)==2`、scene字串、34 records、D18窗readiness；從safe runtime profile檢查新API與RGB availability。 | 自有PID限定stop、default/source變更拒重用、A/B1 catalog、served hash／boundedHTTP；不讀人物期望或private驗收。 | 0.5–1 |
| rehearsal：`scripts/office_rehearsal_check.py` | PASS/FAIL/UNKNOWN、exclusive output、不啟停與hash收據可用；Office binding keys、`person_api:*`、固定C5 freeze檔清單改profile/registry；保護新data/private roots，讀已有凍結結果不regenerate。 | output containment/symlink拒絕、API欄位／refs/hash、未物化UNKNOWN、缺格／分頁收據、禁止GT IO。舊59 PASS不算新驗收。 | 0.5–1 |

上述 5 fps 後端包粗加總 **10.5–21.5 工作日**；共用adapter／schema可減少重複，但RGB tracking與候選歧義可能拉長，不能把總和當交付承諾。若只做「static/run安全載入＋metadata候選＋同步播放」，不含local-track/人物曲線/C4b，建議另拆小包，約3.5–7日，不能用它聲稱2D→3D完整Demo完成。B包建場景／四張preview另開有界任務，不以這個估算啟動。

## 9. 本輪驗證與實際產出

本輪做的是文件與來源核對，不跑程式測試、推論、renderer或整套suite。後端限制是在上列固定Git objects內核對，不聲稱PR已合併或服務已運行。新增文件只連結本分支已存在檔案或可追溯的GitHub固定版本，避免跨分支相對連結失效。

主要查核指令（Git object的讀取均未checkout）：

```sh
pwd
git status --short
git branch --show-current
cat AGENTS.md
cat docs/DEVELOPMENT_RULES.md
git show --stat 59b8f5d
git show --stat 14a3ffb
git show 9848d5e:docs/contracts/OFFICE_CONTROLLED_SCENE_V1.md
git show 9848d5e:docs/agents/CONTROLLED_SCENE_CLAUDE_REPLY_20261018.md
git show 9848d5e:docs/agents/CONTROLLED_SCENE_UX_SKETCH_20261018.md
gh pr view 65 --json number,title,url,headRefName,headRefOid,baseRefName,state,isDraft,files
gh issue view 66 --json title,body,comments
gh issue view 26 --json comments --jq '.comments[] | select(.body | contains("## D25")) | {body,url}'
df -k .
git check-ignore data/pilot/controlled_scene_v1/assets/controlled_scene_v1.blend data/pilot/controlled_scene_v1/runs/example/rgb/CAM_W1/frame_000000.png
git diff --check
UV_CACHE_DIR=/private/tmp/amidst-c4a-uv-cache uv run --no-project --offline --no-sync --python /opt/homebrew/bin/python3 /private/tmp/amidst-csa-doc-check.py
```

另以 `git show 4019a44f:<path>` 定點核對 §8 的 hybrid/perception相關介面、frame_retrieval、service、preset、C4b、domain/camera、geometry/calibration、registry；`git show 225f2461:<path>` 核對 launcher/rehearsal。一次嘗試 `src/amidst/geometry/camera.py` 得不存在，改查實際 `domain/camera.py`／`geometry/calibration.py`；未擴張掃描。`gh` 最初在網路sandbox內連線失敗，經核准的唯讀network呼叫取得上述結果，不把失敗視為遠端沒有資料。

文件檢查結果：4 個本機相對連結存在、14 題順序與完整性、6 個固定 commit objects、影格／磁碟／工時加總算術與無尾端空白，全部 PASS。這是文件核對，不是程式測試。工時初稿加總誤寫11，檢查後改成10.5工作日下限。第一次 `uv run --offline --no-sync` 遇 sandbox 的 system-configuration panic；重試因 checkout 沒有環境而意外建立76 KiB `.venv`，未安裝依賴，已只移除這次新建環境，並以 `--no-project` 和既有系統Python完成文件檢查、確認 `.venv` 不存在。此為本輪操作偏差，未更動原有環境／資產。

## 實際產出 / Actual output

- Model / effort: Codex；精確 model／effort 在可核對 metadata 中 UNKNOWN，不推測。
- PR / commits: 本文件提交在 `codex/office-demo-rehearsal-docs`；精確 commit SHA 見交接回覆與結果留言（避免文件自我引用hash）。本次不建立PR、不push、不merge；#65仍由Claude維護。
- Files changed: `docs/engineering/CONTROLLED_SCENE_CS_A_REVIEW_20261018.md`；`docs/README.md` 索引。
- Commands run and results: 上列唯讀Git/gh/metadata查核完成；4個相對連結、14題全部覆蓋、6個commit objects、550張/磁碟/工時算術與空白檢查PASS；`git diff --check` PASS，新增檔另以staged diff檢查。程式測試0次，非測試PASS數。
- Artifacts: 本Markdown與索引；報告SHA-256見交接／issue留言。沒有新blend/RGB/GT/index/重建輸出；LOCAL `/private/tmp/amidst-csa-*-9848d5e.md`只是三份指定文件的唯讀文字快照。
- Verified: #65固定head／Draft、#66範圍、D25；指定版本wrapper限制；現有camera欄位；磁碟available16.900GiB；兩個候選資料路徑被Git忽略；新命名／安全與私有設計、逐條回覆與14題答案已記錄。
- Not verified: 新場景視線／full-body或foot覆蓋、轉角全身盲區、B1錯開、RGB偵測／跟蹤／區間精度、render RAM/swap/耗時、任何新API實作、8格真實同步、瀏覽器／全Demo；未讀GT／媒體，未驗資產內容hash或現有服務。
- Deviations, UNKNOWN items and follow-ups: §9實際14題而非11題；CS-Q3/Q4/Q9/Q11及§7 GT時機／CS-A人工核准仍OPEN。新欄位與端點皆提案；CS-A結果不是批准，不能據此開始B包／CS-R合併。
