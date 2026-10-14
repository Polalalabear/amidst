# Blender 門、走廊與碰撞候選篩選 / Source-bound physical candidate filtering

> 目前操作入口： [demo 指南](DEMO_V1.md)與[全部工作／依賴交接](../operations/CURRENT_WORK_REPRODUCTION.md)。本頁固定埠號與日期化測試屬原 checkpoint；當次 URL 使用 `DEMO_URL`，不沿用歷史服務位址。獨立受限 Phase1 驗收見[最新正式報告](../research/PHASE1_FINAL_REPORT.md)，不擴大本頁來源／幾何權限。

本階段沿用三組 Blender camera／像素／投影資料，加入既有來源綁定的支撐面、
人體淨空政策與核准碰撞元件，評估跨鏡頭候選並重新排序。來源缺失或權限未核准時
保留 UNKNOWN；不能把顯示 mesh、門的名稱或 annotation box 當成物理碰撞證明。
這是本機基底演算法的工程診斷，沒有 Agent 決策或正式 Phase 1 驗收。

## 已核對的來源與範圍

來源為既有 `school_v3.blend` 的固定 export／authority bundle，source SHA
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`。
只讀既有證據，不開 Blender、不改動或複製 .blend、不接真實串流。
尺度仍為核准的0.0247 m/BU；轉成公尺一次後不重複縮放。

| 項目 | 實際來源狀態 | 可使用的結論 |
| --- | --- | --- |
| 地板支撐 | 48個核准支撐子域、86個source support surfaces | 可核對局部支撐／人體footprint；不能證明全棟可行走、身體或天花板淨空 |
| Office／Classroom101／Auditorium | 各自有來源支撐證據 | 逐點／連接區間核對；其他鏡頭缺失保持缺失 |
| 已知碰撞元件 | 58個核准精確OBSTACLE components；collision scopes為PARTIAL | 可拒絕已知元件的候選名義人體碰撞；沒有碰到元件不代表完整無碰撞 |
| WALL候選 | 73個HIGH_CONFIDENCE；不等於APPROVED | 不自行升格為硬碰撞體 |
| 門／通道 | 28個portal geometry仍為HUMAN_REVIEW；8組門洞淨空診斷的approved pair為0 | 可呈現來源與待審查原因；門洞可通行性保持UNKNOWN |
| 完整人體場域 | approved local physical scope為0，global completeness=false | 不把缺少幾何或支撐連接當成已證明不可達／可達 |

既有核准人體政策為upright cylinder：radius0.3 m、height1.7 m、body clearance0.05 m、
collision tolerance0.001 m。Footprint radius0.35 m；門洞minimum width0.7 m、height1.8 m。
這些是既有核准政策值，不是本輪重新估計的人體尺寸或像素誤差。

## 本輪實際候選結果

| 情況 | 實際檢查候選池 | 新Top-K對應原探索序位 | 局部支撐區間／獨立點 | 拒絕與未知 |
| --- | ---: | --- | --- | --- |
| Office | 5，完整配置枚舉 | 3→1、4→2、2→3；原1仍保留為新4 | 0/26區間、0/1點 | 0硬碰撞拒絕；5解UNKNOWN |
| CLASS101 | 1，未關聯基線 | 1基線，不能補造跨鏡頭Top-3 | 62/68區間、1/1點 | 0硬碰撞拒絕；1解UNKNOWN；CORRIDOR04仍50來源／0投影 |
| Auditorium | 256，有界beam截斷 | 原1、2、3保持前三 | 38/89主區間、2/2次要原區間、0/1獨立點 | 0硬碰撞拒絕；256解UNKNOWN，非全域最優 |

區間／點數為各站第一個保留候選的檢查數；點包含不屬於連續區間的原投影與
同期支持觀測。同期支持點保留原值，不平均融合，也不把另一鏡頭點補成缺口路徑。
次要鏡頭已明確連接的原局部區間也做連續檢查，與主路徑同一段者去重；
只有明確來源連續性才檢查，不把無關支持點連線。次要原區間另計，不灌主路徑支撐加分。
目前58個核准已知元件的bounds未與三站名義人體掃掠範圍相交；這只是已知元件
的條件檢查結果，不表示整場無碰撞。Office支持不足、未核准門洞、完整走廊
可達性／人體淨空及缺失中間位置均保持未知；支撐不足不直接證明不可達。

重排分數為原兼容分數＋0.25×局部支撐區間比例−0.25×min(1,缺失秒數/9.8)。
這是明列權重的工程排序，不能視為身分機率或通行認證。獨立點檢查可拒絕已知
名義佔據碰撞，但不混入區間比例。Office前兩解因缺失時間較少而提升序位。
完整有界探索集合提供原序位、新序位、拒絕／未知原因與分項分數：
「未進本次Top-K」不同於「REJECTED」，排序外未關聯基線另行保留。

Office現有註冊影像的相機ID也叫`CAM_1F_AUDITORIUM_FRONT/REAR`；名稱不是房間
歸屬核准。本輪按原site/run/dataset/features/source hashes隔離，不改相機名稱或
以名稱推定門／走廊連接。局部描邊採該site既有declared support供核對；實際支撐
檢查使用核准1F的59個surface聯集，不用相機或annotation box切割碰撞scope。

## 層級資料流與交流內容

| 層級 | 具體輸入 → 輸出 | 實際／推斷／替代／未知 |
| --- | --- | --- |
| 來源約束匯入 | pinned geometry／floor support／physical authority／policy hashes → GT-free source約束及coverage | 實際來源證據；partial scope、未核准portal與未分類mesh保持狀態 |
| 原像素／投影 | 每站2鏡頭×50張RGB、camera/time/contact/local tracks → 原XYZ與速度 | RGB與校正為實際Blender資料；橙色target/motion為替代；XYZ與速度為衍生 |
| 候選圖 | 原有效片段／時間／速度／同步投影 → 有界beam內不同邊配置 | 不確認身分；保留原hard gaps、overlap support與未關聯baseline |
| 物理檢查 | 候選名義人體、已連接區間、核准支撐／元件 → SUPPORTED_LOCAL_ONLY／REJECTED／UNKNOWN項目與原因 | 局部支持不同於整解通過；已知矛盾可拒絕；缺scope、門洞與缺失中間位置不能硬補結論 |
| 重排 | 有界候選池及檢查分項 → 非拒絕Top-K、拒絕核對列表、完整決策摘要 | UNKNOWN保留；工程分數不是機率；不強迫湊K或宣稱全域最優 |
| 工作台／回放 | 原局部平滑模型、結果與來源clock → 3D路徑／曲線／reason panel／PNG與MP4 | 每解來源／推斷／替代／未知分開；事件IDs只留log |
| 隔離測試 | 小型可核對門／牆／支撐／missing fixtures → 預期理由與守門結果 | 明示SUBSTITUTE，不能當成三站真實門洞或碰撞證明 |

長缺口的端點關聯線不是實際動線。不能因這條示意線穿過幾何而宣稱人物穿牆，
也不能補造detour影片。只有有效連接的候選名義區間才做區間碰撞檢查。
必要的距離／時間下界與完整資料下的可達性需區分；partial支撐或portal缺失只給未知。

物理排名以所選鏡頭完整來源時間作canonical評估；查詢窄窗只切顯示曲線。
新物理PNG／MP4固定全鏡頭、0–9.8 s、請求K3，與本次K／rank／窗範圍分開標示。
舊camera-local與跨鏡頭checkpoint／媒體保持原內容。

## 接口與發布

`POST /api/physical_cross_camera_reconstruction`使用研究session、scene、camera_ids、
start、end、top_k；不接受caller paths、GT、碰撞體、政策或自行擴張authority。
`GET /api/physical_cross_camera_media`只讀本session／scene核發的素材，GET不encoding。
來源與政策失配拒絕；optional媒體缺失不消除有效候選與原觀測。端口probe的物理媒體失配只讓physical.video為FAIL，其餘端口仍回傳自己的結果。
無可用投影點時回NO_RESULT，空基線與ledger仍為UNKNOWN，不能用零次檢查授予SUPPORTED_LOCAL_ONLY。

實際Office查詢傳研究session與以下資料，沒有Agent prompt或caller幾何：

```json
{"scene_id":"blender-office",
 "camera_ids":["CAM_1F_AUDITORIUM_FRONT","CAM_1F_AUDITORIUM_REAR"],
 "start":0,"end":9.8,"top_k":3}
```

基底索引回傳`workbench.blender-physical.v1`：新rank1–3分別帶`original_rank`3、4、2；
每解`physical.verdict=UNKNOWN`、分項`scores`、支撐／碰撞／缺失`checks`與原因；
`decision_ledger`有5個探索配置，原1的`rerank=4`而非REJECTED。
工作台只選取回應的候選、畫source clock與原曲線，不自行重排或補中間位置。
PNG／MP4經新`physical-media:`命名空間核發，不能拿舊`cross-media:`reference冒用。

| 隔離替代測試 | 具體輸入與預期輸出 |
| --- | --- |
| 已知連續碰撞 | SUBSTITUTE核准牆面x=0；候選從[-1,0,0]於0.2秒連到[1,0,0]於0.6秒，速度5 m/s但名義人體穿牆 → 已知元件REJECTED |
| 同端點長缺口 | 將時間差加長至超過可插值窗，中間位置MISSING → 不掃描端點直線，路徑UNKNOWN而非假穿牆 |
| 孤立點／同期支持 | 安全連續區間外另有斷線觀測，或另一鏡頭原支持點落在已知元件 → 該名義佔據碰撞REJECTED；原投影不改值 |
| 缺少完整支撐／門洞 | PARTIAL支撐或HUMAN_REVIEW aperture → UNKNOWN保留，不因找不到連接推定無路 |
| 尺度、scope與來源失配 | 不同source/site、重複縮放、政策或檔案失配 → 拒絕匯入／讀取，不影響原像素層 |
| HTTP／媒體 | caller幾何／政策／GT拒絕；session/scene/reference隔離、hash失配撤銷媒體，曲線候選保持有效 |

上述人工牆與軌跡只測演算法邊界，不能算三站的真實碰撞拒絕案例。

新衍生素材存入ignored `data/engineering/local_run/blender_physical_v2/`。
公開僅code/docs/tests與curated counts／hashes／有限理由與資料流例，不發布原RGB、
.blend、完整mesh／feature／軌跡、GT、影片／PNG、DB或private manifests。

## 本輪完成與驗證（2026-10-13）

已完成三站來源約束匯入、候選池物理檢查／重新排序、逐解reason ledger、研究API／
issued media refs、3D支持域與候選曲線、三PNG／三影片及20端口／站重跑。
完整Python `--require-physical-evidence`為3140 PASS、0failure/error/skip；backend505檔
在全套之前與之後雜湊一致，527.69秒。最終Node122 PASS（workbench109＋product13），
Ruff PASS、strict mypy197 sources PASS；核心36／source9／media18／ports4／HTTP6項新測試
均已包含於Python3140，不另加總。實際60/60端口為54 ACTUAL_BLENDER＋6 SUBSTITUTE；
HTTP175 requests／501 assertions PASS、issues=[]。

三站影片1280×720、H.264/yuv420p/faststart、5 fps、50影格／10秒，來源0–9.8秒；
共300 SOURCE_RGB_EXACT選取，三影片共150影格經完整FFMPEG decode fallback通過。
實際工作台驗證候選／排序外基線與完整ledger、缺失鏡頭、窄窗與完整素材caption、
三站播放及時間軸／3D／曲線交接。原影片的ended事件可能遺漏最後來源影格；共用binder
現於結束強制同步來源9.8秒，保留當前scene／session／播放擁有者守門與手動接管。
目前未量測FPS；DOM／renderer／視角保留由Node回歸核對，不宣稱FPS認證。

未完成：28門洞／8門淨空對的人工核准、完整走廊連通與人體淨空、全場碰撞認證、
人物身分／行為、Class走廊觀測、Aud完整搜尋列舉。缺口位置仍MISSING、條件不足仍UNKNOWN；
真實串流標記FUTURE、正式帳號與部署DEFERRED，Phase1正式gate與Phase2凍結保持。

[驗證收據](../../data/engineering/blender_physical_20261013/validation.json)、
[候選與原因](../../data/engineering/blender_physical_20261013/physical_summary.json)、
[來源權限](../../data/engineering/blender_physical_20261013/source_constraints.json)、
[HTTP](../../data/engineering/blender_physical_20261013/http_runtime.json)、
[原來源不變](../../data/engineering/blender_physical_20261013/source_integrity.json)。

## English

Source-bound physical filtering adds approved support surfaces, the existing body/clearance
policy and exact known collider components to independent Blender candidate pools. Pending
door apertures, partial collision coverage, missing motion and uncertain body support remain
UNKNOWN. Display meshes, names and annotation boxes never become approved colliders.
Known nominal-path contradictions may be rejected, with explicit reasons; absence of known
contact is not collision-free certification. Bounded Top-K, rejected diagnostics and the
unassociated baseline retain their provenance and source clock. No Agent, original Blender
modification/copy, real streaming or formal school acceptance is involved.

The 2026-10-13 rerun passed 3140 Python checks with required physical evidence, 122 Node
checks, lint and strict types (197 sources), 60 system ports (54 actual Blender, 6 independent
substitutes), and 175 HTTP requests / 501 assertions. Six new artifacts were encoded and
validated; the three videos decode all 150 frames. Original source integrity is unchanged.
Office reranks original 3/4/2 into its first three; Classroom has one unassociated baseline;
Auditorium keeps its first three within a truncated 256-candidate pool. Every actual candidate
remains UNKNOWN and known hard-collision rejections are zero. Pending door/clearance authority,
complete connectivity, identity, missing corridor observations and exhaustive search remain open.
