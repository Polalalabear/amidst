# Amidst 共用工作台 / Shared desktop workbench

這是 `codex/simulation-engineering` 的桌面版第一版工作台。研究與管理共用入口、
場景切換及事件元件；研究角色另外提供局部 3D、場景人審、測試與評估。
目前 catalog 接入三個 Blender 預設情況與三個原凍結合成研究場景，六組來源／run 分別綁定。
手機版不在本輪範圍內。

## 2026-10-12 跨鏡頭多解與同步回放增量

研究入口在三組 Blender 情況新增「跨鏡頭多解還原」，沿用來源 RGB／校正／合法 floor
及相機局部運動快照，不讀 GT、不經 Agent、不開 Blender。`BaselineAssociationIndex`
在每個 site／run／clock 預建有界圖，保留一進一出、同期位置與完整路徑速度限制。
跨鏡頭關聯是暫定假設；人物與行為仍未知，floor-only 不能授予碰撞或可行走權限。

可選Top-K候選或排序外未關聯基線；候選路徑、XYZ／速度曲線與時間游標更新同一3D
canvas，保留模型、視角與影片DOM。觀測投影、局部插值、跨鏡頭短推斷與同期支持原點
分開顯示，不平均融合。長缺口的虛線只表示關聯假設，中間位置保持MISSING；原硬缺口
不因跨鏡頭分組而補好。事件ID只在專用log，正常畫面以候選／路徑序號表示。

`POST /api/cross_camera_reconstruction`接受研究session／scene、1–4鏡頭、≤10秒窗及
嚴格整數K1–5；回應`workbench.blender-association.v1`含graph、candidates、baseline、
原local tracks／camera coverage、缺失、支持觀測、source hashes及search完整性。
**canonical關聯及排名採所選鏡頭完整來源0–9.8秒；查詢窗只裁切曲線／顯示。**
`GET /api/cross_camera_media`僅讀同session／scene已核發且hash核對的PNG／MP4，GET不encode。
預物化素材固定全鏡頭／完整來源／請求K=3，與目前query、rank或baseline的差異明列。
影片時間可同步3D／曲線／原camera圖片，手動時間軸暫停影片；缺失期間不外推游標。

| 情況 | canonical nodes／合法edges／拒絕edges | 結果 |
| --- | ---: | --- |
| Office | 5／4／0 | 3解；5個唯一配置完整枚舉，另留未關聯基線 |
| CLASS101 | 6／0／0 | `NO_CROSS_CAMERA_EVIDENCE`；1基線，CORRIDOR04仍50來源／0投影 |
| Auditorium | 19／52／32 | 3解；beam256、10850次評估，截斷且`complete=false`，非全域最優 |

三站各物化曲線PNG與MP4，影片1280×720 H.264／yuv420p／faststart、5 fps、50影格／
10秒，每站100次來源RGB選取；環境無ffprobe，以`FFMPEG_FULL_DECODE_FALLBACK`
完整解碼PASS。Office三解長缺口分別8.2／6.8／4.2秒，中間位置均MISSING。
本次完整Python含physical evidence為3067 PASS／0 skip／443.27秒，Node110 PASS
（工作台97＋product13）、Ruff／mypy193來源檔PASS；三站各16/16（14實際＋2替代）端口，
合計48/48、0 deferred。HTTP160 requests／450 assertions PASS、issues=[]。
瀏覽器三站候選／排序外基線、Class走廊缺失、Aud截斷提示、影片與3D／曲線／camera
時間同步均驗證；native video seek4.8秒同步通過，手動來源時間軸暫停影片。
既有source Play接管影片後，RGB／3D／曲線同進至9.8秒；兩鏡頭2–4秒K1及單鏡頭
查詢仍與完整來源K3素材caption分開；console0 warning／error。
原`.blend` SHA／468300506 bytes／mtime不變；本次code-tree驗證與下方camera-local／
舊milestone保持獨立範圍。新操作／物化與資料流見
[跨鏡頭契約](BLENDER_CROSS_CAMERA_RECONSTRUCTION.md)及
[獨立收據](../../data/engineering/blender_association_20261012/validation.json)。
原`.blend`／PNG唯讀，不複製原資產、跨site合併、接真實串流或上傳本機媒體。

## 2026-10-12 位置／速度曲線與事件還原入口

Blender 情況新增同相機局部 track 的重建 API與曲線／影片物化入口，接續既有300張
camera RGB產生的安全pixel／floor-projection快照。`PROJECTED_OBSERVATION` 是影像
接地像素經校正投到地面的3D點，並非直接觀測3D。只有同一局部track、有效兩端、
缺口≤1秒且速度≤設定8 m/s，才在來源時間格上增加 `INFERRED_INTERPOLATION`；
速度以原兩端區間中點的 `INFERRED_FINITE_DIFFERENCE` 呈現。長缺口、投影失敗、
超過速度上限或track中斷保留MISSING／斷線，不跨鏡頭或情況合併、不外插。

工作區的重建操作使用目前相機與有限時間範圍，依track分開查看位置及速度；
窄範圍只裁切顯示，不重聚合原track／事件端點或IDs。原始來源畫面、投影點與插值
保持不同標示。沒有量測的鏡頭仍顯示MISSING來源影格覆蓋；CLASS101的CORRIDOR04
有50張來源圖，但沒有像素觀測或投影，不能因另一鏡頭有曲線而宣稱已追蹤該走廊。

`POST /api/motion_reconstruction` 接受 `session_ref`、`scene_id`、`camera_ids`、
`start`／`end`，最多4鏡頭、10秒、400曲線點及32局部tracks。回應包含source／pixel／
reconstruction hashes、完整來源時間與選取範圍、各track samples／velocity／gaps／
暫定events、camera coverage及optional artifacts。影片與PNG只能用伺服器發出的
media reference經 `GET /api/motion_media`取得；request不含檔案路徑，GET不自動encode。
無物化素材回NOT_MATERIALIZED，hash／來源失配回INVALID_OR_STALE_ARTIFACT，
仍可保留有效曲線，不把缺少影片稱為重建完成。

三站曲線PNG／影片已物化，每站影片為1280×720、H.264／yuv420p／faststart、
5 fps、50影格／10秒，顯示完整來源0–9.8秒；每站100次來源RGB選取均為
`SOURCE_RGB_EXACT`，不表示H.264編碼後像素與原PNG逐位相同。環境無ffprobe，
三站以 `FFMPEG_FULL_DECODE_FALLBACK` 完整解碼 PASS，三站provider manifest與六份媒體
讀取均 PASS。完整Python驗證（含physical evidence）3017 passed／357.78秒，無fail／error／skip；
Node 92 PASS（workbench 79＋product 13），Ruff／strict mypy 191來源檔 PASS。最終HTTP
98 requests／254 assertions PASS、`issues=[]`；三站各13/13端口（11 ACTUAL_BLENDER＋
2 SUBSTITUTE）及六份媒體binary／hash／range／scope均PASS。

瀏覽器三站1280×720／10秒影片實際播放無解碼錯誤。Office seek至7.838899秒與camera同步
通過；CLASS101 CORRIDOR04顯示50來源影格／0投影／50缺失，Auditorium單鏡頭2–4秒查詢
與完整all-camera影片caption分開標示。切換scene清除舊影片；最終console無warning／error，
一般畫面隱藏opaque event IDs，原`.blend` SHA／size／mtime不變。窄查詢範圍不會變成另一個
影片時間軸。需要重新物化時，從既有safe scene在新輸出位置執行：

```sh
UV_CACHE_DIR=/private/tmp/amidst-uv-cache uv run --offline --no-sync \
  python scripts/materialize_blender_motion.py \
  --output data/engineering/local_run/blender_motion_v1
```

重跑時使用新輸出位置，不覆蓋舊artifact。原 `.blend`／PNG不改動或複製，物化曲線與
影片保存在ignored local_run；Git只保存程式、文件及整理收據。物理basis僅floor plane，
8 m/s屬工程設定，不授予人類行為、整場碰撞／遮擋／可行走核准。人物／行為仍未確認，
合成目標與活動來源保留。操作與契約見
[Blender事件還原](BLENDER_MOTION_RECONSTRUCTION.md)，
[本次收據](../../data/engineering/blender_motion_20261012/)與下方歷史驗證分開。

## 2026-10-11 Blender 預設情況與基底畫面檢索

Office、CLASS101、Auditorium 各有兩台原來源相機、50 個時間點，合計 300 張既有
Blender camera RGB，960×540、5 Hz、0.0–9.8 秒。三組為獨立模擬 run；同名鏡頭與
同 timestamp 不跨情況合併。橙色目標及活動是合成替代，原模型幾何、校正與 PNG 像素
是本次實際輸入；程序式 E0／E1 fixture 仍是各自的測試資料。

工作區顯示 source-supported 範圍內裁切的原 evaluated mesh，標為
`PARTIAL_DISPLAY_CONTEXT`；預設平滑灰材質僅影響呈現，未載入整份 `.blend`，未新增
封蓋或物理／語意權限。使用者選取相機、有限時間範圍、目標時間與 Top-K，
由 temporal-median 像素元件、合法地面投影與有界 camera/time 索引回傳畫面訊息。
Blender 情況不開啟 Agent 決策、語意仲裁、事件人審或原 product investigation；
行走／跑步／出入仍是使用者意圖，人物與行為保持未確認。

端口測試對所選 Blender 情況重算實際 RGB → 量測 → 投影 → 快照重開 → 檢索 → Top-K
與展示。缺少該來源的 Graph／修改歷史測試使用獨立替代 fixture，明列不同 source/run/clock；
不回填其結果。包含物理推斷曲線的事件還原影片尚未完成。
原 `.blend` 與 PNG 未改動或複製，不接實體攝影機串流。操作及各層資料邊界見
[Blender 相機畫面檢索](BLENDER_CAMERA_FRAME_RETRIEVAL.md)，本次整理收據見
[blender_workbench_20261011](../../data/engineering/blender_workbench_20261011/)。
下列既有測試數字與 receipts 各自保留日期與範圍，不當作本次回歸結果。

## 2026-10-11 系統端口與 label 指引增量

研究入口預設開啟共用工作區，以模擬 3D 為主，來源影像摺疊為輔助證據。
原 canvas、renderer、視角與完整解碼影格在一般更新時保留；事件 ID 僅在專用 log。
圖形整理 label、鏡頭／時間與使用者行為意圖後，顯示有限 Agent input/output，
可執行最多兩個 detail actions。3D 保留全部由有界 AgentInput 供應的來源節點與邊；預設只顯示目前鏡頭標籤，
勾選關聯標註後最多顯示五個簡短標籤，完整關聯可另展開文字。

測試面板可執行獨立假資料的十個系統端口及四階段 SQLite 併發，展開查看實際 I/O。
新發布歷史改存 changed-leaf delta，匯出只含修改文件與來源／版本 hash；v0 可預覽，
沒有修改部分可匯出。詳細資料流、完成狀態及替代測試邊界見
[系統端口與 label 指引](SYSTEM_PORTS_AND_LABEL_GUIDANCE.md)，本次驗證見
[2026-10-11 receipt](../../data/engineering/workbench_20261011/validation.json)。

## 2026-10-10 已接入增量

同一8016導覽新增「人物調查」與「實驗展示」。前者重用原E1 frozen product的計畫／
案例／報告／四鏡頭soft-sync影片；後者提供原Office局部mesh／人形／50格回放和15家族
展示庫。精度v2為第三個獨立experiment scene，保留SUPPORTED／UNKNOWN／盲區替代。
完整操作、角色／GT與source/clock/unit邊界見
[來源模型展示](SOURCE_PRESENTATION_WORKBENCH.md)、
[人物調查／展示庫](WORKBENCH_INVESTIGATION_GALLERY.md) 與
[當次integration receipt](../../data/engineering/workbench_20261010/integration_validation.json)。
下面的2026-10-08遷移表和測試屬歷史基線；不把新功能算作當年的驗證。

## 統一網頁入口

依使用者 2026-10-08 指示，這套工作台是 Amidst 網頁的主要入口。
既有及後續需要網頁展示的場景、影片、事件、調查、測試、評估與 human 審查，
都接入 `frontend/workbench/` 的共用導覽、元件與流程。研究／管理決定資料與操作權限；
展示／測試／人審決定工具與排版。新增場景以 catalog／adapter 接入。

既有 `frontend/product/` 控制室是可遷移的功能與驗證來源；其後端、資料契約、
freeze 及歷史證據繼續保留。主入口使用本機 8016；8010／8012／8020 的既有頁面
各自保留歷史驗證。2026-10-10 已接入下列核心操作；完整 research runner、缺失素材和
status-only RRD／GIF 仍有明確限制，不能宣稱所有歷史展示都可互動重跑。

2026-10-08 實際網站／來源／素材盤點確認：**實驗展示尚未全部接入**。
該日 catalog 僅有 E1／E0；產品調查、MP4、Office／Rerun、preview 及 projection 診斷仍需
遷移或 source adapter。完整現況、素材存在／缺失及有效待修見
[實驗展示覆蓋表](WORKBENCH_EXPERIMENT_COVERAGE.md) 與
[本輪 audit receipt](../../data/engineering/workbench_20261008/website_audit.json)。

以下是**待遷移的對應位置**，不是已實作功能清單：

| 既有能力 | 工作台中的位置 |
| --- | --- |
| 人物片段、RGB 外觀查找與關聯假說 | 左側資源與右側證據／替代解釋 |
| typed investigation plans、執行／停止／續跑、保存案例 | 研究角色的調查工具區 |
| MP4、主鏡頭、速度、seek、同步診斷 | 中央展示與共用時間軸 |
| 多目標、衝突、報告、HTML 匯出與結果 review | 事件／調查資訊區與共用結果審查 |
| 模式比較、benchmark、工具紀錄 | 研究角色的測試／獨立評估面板 |

工作台後端必須將 server-owned role session 綁到已註冊 scene/run/mode/stage，
再重用現有產品服務。舊 product operator session 不能直接取得工作台研究或管理權限。
管理回傳依既有 allowlist；GT 評估仍在獨立端點，Agent 維持限定範圍。
每個遷移 milestone 以共用入口的操作驗證、版本／來源綁定與原功能回歸確認完成。
產品的輸入模式與 INPUT／RESULTS 階段和工作模式分開；場景 annotation、事件判定、
調查報告 review 也分別保存。影片與調查沿用工作台的相關鏡頭／有限時間窗，
保留多解、截斷及缺圖狀態；E0 或其他場景未提供的能力依 capability 顯示缺失。

## 啟動與重現

在現有工程 checkout 執行：

```sh
cd /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization
npm ci --prefix frontend/workbench
uv run --offline --no-sync python -m amidst.workbench --port 8016
```

開啟 [http://127.0.0.1:8016](http://127.0.0.1:8016)。`npm ci` 使用工作台自己的
`package-lock.json` 安裝固定版本的 Three.js；這一步可能下載 npm 套件，
不呼叫外部模型 API。瀏覽器資產由本機服務提供，沒有執行期 CDN 依賴。
Python 指令使用已準備好的本機環境；`--offline --no-sync` 不安裝缺少的依賴。

可另指定伺服器的場景清單與人審資料庫：

```sh
uv run --offline --no-sync python -m amidst.workbench \
  --port 8016 \
  --catalog configs/engineering/workbench_v1.json \
  --state data/engineering/local_run/workbench_v1/reviews.sqlite3
```

`--repo` 可指定資料與前端所在的 repository。預設 catalog 是
[`configs/engineering/workbench_v1.json`](../../configs/engineering/workbench_v1.json)，
預設人審資料庫是 `data/engineering/local_run/workbench_v1/reviews.sqlite3`。
審查紀錄保存在被 Git 忽略的本機 SQLite；重新開啟同一資料庫會續用紀錄。
展示演練與自動測試應使用自己的 `--state`，例如 `/private/tmp/amidst-workbench-qa.sqlite3`，
保留正式操作紀錄。資料庫來源與重新載入的 scene/run 不相符時會拒絕接續，
請核對場景清單或使用新的資料庫，不要覆寫舊紀錄。

工作台不會自動產生缺少的 scene、RGB 或推論。以下 materialization 必須已存在；
它們沒有包含在可發布的程式碼中。新環境準備資料時，依
[局部鏡頭 pilot](LOCAL_CAMERA_PILOT.md) 與
[模擬工程操作文件](SIMULATION_ENGINEERING.md) 的原有流程建立獨立輸出，
再以 catalog 指向經驗證的 checkpoint。不要把新的輸出覆寫到歷史 checkpoint。

## 目前接入的六個場景

| 場景 | 固定資料來源 | 共用畫面可用內容 |
| --- | --- | --- |
| Blender 相機 · Office `blender-office` | `blender_camera_v1/office`；run `blender-pilot-office-baseline-v1` | 2 原相機、100 張 RGB、局部平滑來源模型、基底 Top-K 畫面 |
| Blender 相機 · Classroom 101 `blender-classroom101` | `blender_camera_v1/classroom101`；run `blender-pilot-classroom101-baseline-v1` | 2 原相機、100 張 RGB、獨立預設情況與來源模型、基底 Top-K 畫面 |
| Blender 相機 · Auditorium `blender-auditorium` | `blender_camera_v1/auditorium`；run `blender-pilot-auditorium-baseline-v1` | 2 原相機、100 張 RGB；與 Office 同名鏡頭仍分 run，來源模型與基底檢索 |
| 局部多鏡頭研究場景 `local-camera` | `local_camera_v1/test/checkpoints/final`；model `synthetic-local-camera-v1`，run `local-camera-test-v1` | E1 pinhole；4 鏡頭、244 張 RGB、11 個場景物件、局部行為及盲區候選 |
| 雙鏡頭基礎實驗室 `synthetic-lab` | `simulation_v2`；model `synthetic-lab-v1`，run `simulation-v2` | E0 affine；2 鏡頭、102 張 RGB、6 個場景物件、人物片段及盲區候選 |
| 局部鏡頭精度研究 v2 `local-camera-accuracy-v2` | `accuracy_v2/test/final`；原 E1 model／source run，experiment `accuracy-test-v2-final` | end_to_end／plus／RESULTS；29 segments、165 events，保留 SUPPORTED／UNKNOWN／GAP_ALTERNATIVES |

上述來源路徑皆位於 `data/engineering/local_run/`。E0／E1 是不同模型，
不是同一模型的 development/test 分割；v2 重用 E1 RGB 與校正，另綁 experiment/config/freeze。
新環境的 v2 materialization 依 [研究報告](../research/LOCAL_CAMERA_ACCURACY_V2.md) 重現，
不借用 E1 aggregate digest。loader 在匯入時核對原有來源、演算法、
媒體與凍結結果綁定；查詢再使用已建立的局部索引。

共用 3D 顯示的是來源明確提供的區域多邊形、門線段、可行走面、鏡頭與研究候選。
它不是原始 Blender 的完整建築 mesh，也不表示已取得完整物理或語意權限。
座標為公尺、時間為來源的合成秒數；畫面保留 scene/run 與凍結版本的來源資訊。

E1 提供實際配置的 pinhole 鏡頭位置與內參。E0 只有地面仿射校準，
實體鏡頭姿態為 `UNKNOWN`，不會捏造位置或焦距，也不開放以不存在的 pose 編輯幾何。
六個場景都使用既有 RGB 影格序列；時間軸回放不增加 source frames。

Blender checkpoints 是只含安全欄位、hash 與原資產引用的本機 bundle，沒有複製原圖片或
`.blend`；可依 [Blender 操作文件](BLENDER_CAMERA_FRAME_RETRIEVAL.md) 物化到新位置。
相機平移與 clip 明確由 BU 換算到公尺，原校正 metadata 不回寫。模型是有界來源面裁切，
與原三個 fixture 的配置多邊形分開。公開媒體只剝除 PNG 文字 metadata，保留原像素；
原始與供應 hash 分列，private paths 與模擬 trajectory ID 不對外輸出。

## 操作流程

1. 進入首頁，直接選擇「研究」或「管理」。左側導覽保持固定，右側內容可向下捲動。
   「切換身份」會回到角色入口。
2. 在主控板查看目前場景、鏡頭、局部事件與標註版本；從右上角切換場景。
   所有場景使用同一套前端，不需要重做頁面。
3. 開啟「共用工作區」，選定鏡頭與有限時間窗。事件與人物片段按局部索引取回，
   不會在每次查詢枚舉全量 records。收據顯示讀取數、索引觸及數及是否截斷。
4. 研究角色依場景能力切換「展示／人審／測試」。點選資源列或 3D 物件查看詳情；
   點選事件查看來源、候選及研究判定。展開技術資訊可看到來源與診斷；事件 ID 僅在 log。
5. 研究展示中可選擇少量鏡頭，拖曳時間軸或回放，查看相同來源時間附近的 RGB。
   實際影格時間與缺圖狀態需保留；沒有資料時不複製其他時間影像冒充當前畫面。
   3D 中的可見觀測與盲區候選分開呈現，盲區端點不當成已觀測的連續軌跡。
6. 管理角色查看事件摘要、必要影像、備註與 `OPEN／IN_PROGRESS／RESOLVED` 處理狀態。
   管理主控板下方的 3D 與多鏡頭展示區刻意保留空位。

角色由伺服器建立 session，後端限制管理角色可取得的欄位與可執行操作。
這是可信本機使用的免登入角色切換，任何本機操作者都能重新選擇研究角色；
它不提供帳號、身分驗證或多人部署的真實授權管理。
「展示／測試／人審」是工作模式，不是權限升級途徑。

## 共用人審與版本

場景人審流程是「選取對象 → 編輯草案 → 查看差異 → 驗證 → 人工核准發布」。
可編輯欄位由物件能力決定；第一版以表單及幾何 JSON 編輯，沒有完整 mesh 建模工具。
驗證包含允許的語意、有限與有效幾何、關聯區域，以及相機校準欄位的相容性。
Blender 預設情況的來源相機與展示範圍為唯讀，沒有可編輯欄位，也不開啟這個人審流程。

發布時對外還原 `workbench.scene-overlay.v1` 標註版本。2026-10-11 起，新資料庫發布列
只存來源綁定的 changed-leaf delta、理由、操作者、時間、驗證與父／結果 hash，
由 v0 baseline 與各版本差異還原；既有完整發布列保持相容。草案保留單一修改對象
的修改前後驗證上下文。資料庫採追加紀錄並檢查基底版本，避免舊草案覆蓋新版本。
審查者名稱由本機操作者自行填寫。

人審面板可切換歷史版本預覽；新發布版本可匯出修改部分的 delta JSON 與來源收據。
切換到歷史版本不會回滾目前版本；原始 v0 baseline 也能回看。
研究結果另存「支持／否定／未知／需要更多證據」，不修改演算法原有假說、排序或結果。

**發布標註後，既有推論仍是舊設定的凍結結果。** 影響清單會把相關 run 標為
`NEEDS_RERUN`。人審模式預覽新標註；展示模式保留來源 baseline 與原凍結推論，
避免把新幾何與舊推論混成同一次計算。此版本不會自動重跑演算法，也未提供
從 overlay 一鍵執行新推論的功能；後續新 run 必須明確接入新 annotation/config。

表單驗證通過與本機發布均不是 formal 語意核准。自動測試／UI 演練中的假名審查者
及測試資料庫，只驗證流程，不能充當使用者對真實場景的人工審查證據。

## 新增場景與接口

新增相同來源格式的場景時，先準備經原 loader 驗證的 checkpoint，再在伺服器 catalog
新增一筆設定，無需修改前端：

```json
{
  "schema_version": "workbench.catalog.v1",
  "scenes": [
    {
      "scene_id": "another-local-scene",
      "adapter": "local_camera",
      "checkpoint": "data/engineering/local_run/another_scene/checkpoints/final",
      "label": "另一個研究場景",
      "description": "已驗證的局部鏡頭研究 checkpoint"
    }
  ]
}
```

`adapter` 目前支援 `blender_camera`、`local_camera`、`synthetic_lab` 與 `local_camera_accuracy_v2`；checkpoint 是 repository 內的
相對路徑。scene ID 必須唯一，未知 adapter、絕對路徑、跳出 repository 的路徑及重複 ID
會拒絕載入。尚未存在的 checkpoint 不加入目錄；存在但驗證失敗的 checkpoint 會使
啟動失敗，不會降級成未驗證資料。catalog 是本機伺服器設定，瀏覽器不能傳入任意路徑。

catalog 的 scene ID、名稱與說明只調整展示識別，來源 model/run/hash 維持原有綁定。
新的來源格式需要新增一次 adapter，提供下列共用接口，前端即可依能力顯示：

- `summary()`、`snapshot()`：場景、來源、座標／時間、能力、鏡頭、靜態可審查物件。
- `query(camera_id, start, end)`：有限鏡頭／時間範圍的事件、觀測與檢索收據。
- `event(ref)`、`media(ref)`：同場景直接 reference 查詢；事件能力可缺失，影像像素
  保留原來源。Blender 公開 PNG 僅剝除文字 metadata，原始與供應 bytes 各有 hash。
- `frames(camera_ids, timestamp)`：少量鏡頭的來源影格或明確缺失狀態。
- `frame_query(camera_ids, start, end, target_timestamp, top_k, behavior_intent)`：Blender
  情況的有界基底 Top-K 畫面，不使用 Agent；能力缺失時拒絕執行。
- `motion_reconstruction(camera_ids, start, end)`：同相機局部track的暫定位置／速度與
  明列缺口；窄窗保持canonical端點，optional影片物化另驗source／feature／renderer hashes。
- `evaluation()`：獨立研究端點使用的既有評估摘要。

共用物件包括 `REGION／PORTAL／WALKABLE／CAMERA`，帶有來源識別、語意、
幾何、屬性、允許編輯欄位及 authority。能力缺失時保留缺失狀態，
不從名稱猜測校準、物理幾何或語意。

## 測試與資料邊界

畫面中的「執行目前範圍檢查」檢查來源綁定、靜態物件、有限座標、
局部查詢是否截斷、可用時讀取一張來源影像，以及標註／推論版本狀態。
這是選定鏡頭與時間窗的資料／接口檢查，不會執行整套 pytest、重新產生推論、
重算 benchmark 或證明人物關聯精度。無樣本會顯示 `NOT_RUN`，標註已改但未重跑
則顯示 `NEEDS_RERUN`。

「查看已凍結評估」只讀既有 aggregate evaluation summary，並核對來源 run、model、
dataset、相應 config 與 freeze receipt。缺少評估顯示 `UNAVAILABLE`；
綁定失配顯示 `STALE`。E1 摘要中的 config hash 是 package config，
與整體推論 effective config 的含義不同，另以逐模式 freeze receipt 核對同一次結果。
此 action 以可展開 JSON 顯示認證摘要，沒有完整 experiment／benchmark／reproduction runner。
P14 已實作 aggregate DTO allowlist／獨立內容 digest 認證與發布後 cached test/evaluation
失效處理。v2 的獨立 aggregate 未認證時顯示 UNAVAILABLE；已發表比較走展示庫。
GT debug 是 Gallery 的獨立人類研究分類，不屬此評估 action 或 Agent allowlist。

GT／recipe sidecar 仍留在原 generator／evaluator 邊界，工作台常規場景與展示工具
不開啟它們。研究人的評估面板不擴張 Agent 的權限；原有 Agent 仍使用有限範圍、
排除 GT 的工具。管理 API 不提供評估、原始診斷、人審發布或技術 log。

工作台不接真 camera、不呼叫外部模型 API，不寫入原 Blender、既有 RGB、
registry、歷史 run 或凍結推論。Formal Cases 2/3 與 full Exit 仍為 `BLOCKED`，
Case 4 為 `DEFERRED`；frozen Phase 2 保持有效。此工作限工程分支，未合併 main。

## 已記錄驗證範圍

後端 checkpoint `7e17688af427d6d9a0ff9538a385e848036d7d40` 已普通 push，
記錄了 60 個工作台測試、103 個既有回歸測試，以及 29 次實際 HTTP 請求驗證。
這些數字只描述該後端 checkpoint。第一版桌面交付另外記錄於
[`desktop_validation.json`](../../data/engineering/workbench_20261008/desktop_validation.json)：

- 原生 Blender physical-evidence 回歸與工作台合計 **2,487 passed、0 failed、0 skipped**；
  指令 `pytest --require-physical-evidence --ignore=tests/product -rs`，排除由並行 chat
  獨立驗證及提交的 product suite。這不是全 repository 統一驗證數。
- 最後服務調整後重跑工作台 **60 passed**；前端 Node **15 passed**；
  Ruff `src tests` 與 mypy `src/amidst`（164 source files）通過。
- 實際桌面瀏覽器驗收：研究／管理入口、兩場景切換、局部查詢、3D 與來源 RGB、
  時間軸、管理備註、測試與獨立評估面板、console 無 error／warning。
- 獨立測試資料庫完成草案、差異、驗證、發布 v1、歷史 v0 唯讀預覽及 JSON 匯出；
  重啟服務後版本仍存在。展示保留來源基線 v0，並提示新標註尚未重跑。

UI 演練使用 `/private/tmp` 的獨立 SQLite，不會把演練中的人工核准混入預設操作資料庫。
實際截圖保存在被忽略的 `data/engineering/local_run/workbench_v1/`；不發布 RGB 或 SQLite。

可重跑的工作台檢查：

```sh
uv run --offline --no-sync pytest tests/workbench
uv run --offline --no-sync ruff check src/amidst/workbench tests/workbench
uv run --offline --no-sync mypy src/amidst/workbench
npm test --prefix frontend/workbench
```

## English operator notes

The 2026-10-12 cross-camera extension adds the Research "cross-camera reconstruction" action.
Independent source/run/clock graphs use existing pixel-derived floor motion, configured temporal/
speed/proximity guards, one-to-one assignments and whole-path consistency, without GT or Agent
choices. Distinct Top-K candidates and a separately retained unassociated baseline share the 3D
canvas, XYZ/speed curves and source-clock cursor. Observed projections, local interpolation, short
cross-camera inference, supporting original projections and missing spans retain separate labels.
Long-gap association lines are hypotheses with unknown intermediate positions; local hard gaps
remain unresolved. Normal views use ordinal captions and keep event IDs in logs.

`cross_camera_reconstruction` accepts one to four cameras, at most ten seconds and integer K1–5.
Canonical ranking uses the selected cameras' full 0–9.8-second graph; time windows only slice the
display. `cross_camera_media` serves only verified issued references and never encodes on GET.
Pre-materialized media has fixed full-camera/full-time/requested-K3 scope, distinct from the query,
selected rank or baseline. Video time synchronizes paths/curves/source camera images; manual timeline
changes pause video, and missing spans never extrapolate the cursor.

Office has five nodes/four edges and three candidates with exact enumeration of five assignments;
CLASS101 has six nodes/no eligible cross-camera edges and one baseline, with fifty CORRIDOR04
source frames/zero projections; Auditorium has nineteen nodes/fifty-two eligible/thirty-two rejected
edges and three candidates, with beam256 truncation, 10,850 evaluations and `complete=false`.
All three sites have materialized curve PNGs and 1280×720 H.264/yuv420p/faststart videos with fifty
frames at 5 fps/ten seconds and 100 exact source-RGB selections each. Full decoding passed via
`FFMPEG_FULL_DECODE_FALLBACK`, without ffprobe. Office's three hypotheses retain missing gaps of
8.2/6.8/4.2 seconds. Fresh validation passed 3,067 Python tests with physical evidence and zero skips
in 443.27 seconds, 110 Node tests (97 workbench + 13 product), Ruff/mypy for 193 files, each site's
16/16 ports (14 actual + 2 substitute; total48/48, no deferred), and 160 HTTP requests/450 assertions
with `issues=[]`. Actual browser verification covered all three videos, candidate/baseline selection,
missing corridor and truncation notices, 3D/curve/camera synchronization, native seeking to 4.8 seconds,
manual source-timeline video pausing and narrow 2–4-second K1/single-camera captions versus full-source
K3 media. Existing source Play took over after video playback and advanced RGB/3D/curves
together to 9.8 seconds. The console had zero warnings/errors; original `.blend` SHA/468300506 bytes/mtime remained
unchanged. The independent [receipt](../../data/engineering/blender_association_20261012/validation.json)
binds this code-tree scope; previous totals stay historical. See the
[cross-camera contract](BLENDER_CROSS_CAMERA_RECONSTRUCTION.md).
Identity/behavior and whole-scene collision/walkability remain unconfirmed. Original `.blend`/PNG
assets remain read-only and uncopied, with no real streams or local-media publication.


This desktop-only local workbench contains six independently bound scenes: three Blender presets
and the original E1 four-camera pinhole scene, E0 two-camera affine lab and E1 accuracy-v2 experiment. Install the
locked frontend dependency with `npm ci --prefix frontend/workbench`, then run
`uv run --offline --no-sync python -m amidst.workbench --port 8016`.

By the user's 2026-10-08 decision, this is the primary web entry for existing and future
presentation, investigation, testing and human review. Reuse its navigation, components,
role enforcement and scene adapters. Existing product backend/contracts and historical
receipts remain reusable; older pages have not all been migrated. Product operator sessions
must be mapped through workbench-owned role and scene/run/mode/stage bindings before reuse.

Select Research or Management without a password. This is trusted local role
selection, not authenticated identity. Research exposes scene review, bounded
checks, diagnostics and a separate preexisting-evaluation panel. Management
receives a reduced server response and keeps the future multi-camera/3D area empty.

Use the server-owned catalog to add another compatible checkpoint without UI
changes. A new source format needs an adapter. Static review geometry is configured
scene data, not the original Blender mesh; E0 has no known physical camera pose.

Reviews append source-bound drafts, validations and annotation versions to an
ignored SQLite database. New publication rows store changed-leaf deltas, reconstructed from
the baseline and parent versions; historical full rows remain readable. Delta exports contain
modified document parts and hashes. Publishing preserves the original sources and frozen
results, marks affected runs `NEEDS_RERUN`, and supports historical preview/export.
Automatic inference reruns are not implemented. Test reviewers are flow-test data,
not human semantic authority. UI checks are scoped data checks, not pytest,
benchmark accuracy or formal acceptance. GT sidecars remain outside runtime tools;
formal gates remain blocked and frozen Phase 2 is preserved.

The 2026-10-11 research entry defaults to the stable 3D workspace, with images as expandable
evidence and event IDs in logs. Label preprocessing provides bounded graph/features to a local
MockAgent; behavior presets remain user intent. Ten fresh synthetic interface ports and four
isolated SQLite concurrency phases expose their actual I/O in the testing panel. All graph
edges supplied by bounded AgentInput are retained; compact captions appear on demand. Streaming is future work, accounts and
deployment are deferred, and no external model, RAG accuracy or token reduction is claimed.

The same-day Blender milestone adds Office, CLASS101 and Auditorium with 300 existing source-camera
RGB frames. Actual source geometry, calibration and pixels are distinct from the synthetic orange
target/motion. Support-cropped source triangles use a smooth gray display material and remain
`PARTIAL_DISPLAY_CONTEXT`, rather than a whole-scene model or physical authority extension.
Blender presets return deterministic local Top-K frame messages through `frame_query`, without
Agent decisions or existing product investigation. Their port probes recompute pixels, projection,
snapshot reopening, bounded retrieval and presentation; independent Graph/history probes are
labelled substitutes and do not feed results into the Blender runs. Physical event curves/video
remain unfinished. Original `.blend` and PNG files are unchanged and are not copied, and no
physical camera stream is connected. See [Blender operation and data flow](BLENDER_CAMERA_FRAME_RETRIEVAL.md)
and [curated receipts](../../data/engineering/blender_workbench_20261011/); earlier validation
counts remain historical evidence for their own milestones.

The 2026-10-12 motion entry adds provisional position and interval-midpoint speed curves per
camera-local track. Projected observations are RGB contact-pixel floor intersections, not directly
observed 3D. Interpolation requires valid same-track endpoints, a gap no longer than one second
and the configured 8 m/s cap. Long, excessive-speed and invalid-projection gaps remain disconnected;
there is no camera stitching, extrapolation, Agent or behavior confirmation. Empty-camera coverage
stays MISSING, including CLASS101's fifty CORRIDOR04 frames with no pixel/projection observations.

`motion_reconstruction` returns bounded curves and optional verified media references. Narrow
queries preserve canonical track/event endpoints; an artifact depicts its full source range.
GET media never encodes or accepts paths. All three sites have materialized local curve PNGs
and videos: 1280×720 H.264/yuv420p/faststart, 5 fps and 50 frames/10 seconds each. The 100
`SOURCE_RGB_EXACT` source selections per site describe input selection, not byte-exact encoded
video pixels. With ffprobe unavailable, all three passed `FFMPEG_FULL_DECODE_FALLBACK`;
provider manifests and all six media reads passed. The full Python suite with physical evidence
passed 3,017 tests in 357.78 seconds without failures, errors or skips; 92 Node tests passed
(79 workbench + 13 product), plus Ruff and strict mypy for 191 source files. Final HTTP passed
98 requests/254 assertions with `issues=[]`; each site passed 13/13 ports (11 ACTUAL_BLENDER +
2 SUBSTITUTE), and six media binary/hash/range/scope checks passed.

All three 1280×720, ten-second videos played in the browser without decode errors. Office seeking
to 7.838899 seconds synchronized its camera display; CLASS101 CORRIDOR04 showed fifty source frames,
zero projections and fifty missing samples. Auditorium's single-camera 2–4 second query stayed
distinct from the full all-camera artifact caption. Scene changes cleared old video; the final
console had no warnings/errors and normal views hid opaque event IDs. Original `.blend`
SHA/size/mtime remained unchanged. Use the CLI above with a new output directory to rematerialize.
Original assets remain intact,
and whole-scene collision/occlusion/walkability remain unknown. See the
[motion contract](BLENDER_MOTION_RECONSTRUCTION.md) and
[new receipt directory](../../data/engineering/blender_motion_20261012/).
