> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# Blender 門洞、走廊與人體淨空人工核對

8016 共用工作台的本機工程階段，接續 `2de98213fa361b49699a9b896ead8c152cb9a6c1` 的物理候選篩選。先把 UNKNOWN 做成可逐項核對的來源畫面；未獲使用者確認不重算。2026-10-13 已逐項記錄 Office revision 20、Classroom 101 revision 15，並依明確確認各自重跑完整時間段／Top-3／曲線與影片；Auditorium 尚未開始。視覺紀錄不升格為來源幾何權威，38 個有效物理檢查仍 UNKNOWN。入口建立時 revision 0 的收據保留歷史範圍，不覆寫；當前結果見[人工核對 checkpoint](../history/BLENDER_REVIEW_CHECKPOINT_20261013.md)。

## 已完成與尚未完成

| 工作 | 實際狀態 |
| --- | --- |
| 三組來源幾何／camera 與既有候選的同步核對清單 | 已完成，Office 4 項、Classroom 101 3 項、Auditorium 4 項，共 38 個具體檢查 |
| 頂部導覽與主視覺 | 已完成，點擊切換 3D／2D；8／12／16 格選項只在 2D 顯示。每組僅 2 個來源鏡頭，格數為同鏡頭分時影格 |
| 起始／結束時間選取 | 已完成，完整／前段／中段／後段時間段；同步來源時間軸仍可逐格核對 |
| 審查來源、缺失、觀測／推斷／替代資料與 UNKNOWN | 已完成，受限預覽的省略與來源未分類面保持未知 |
| 本機修訂、併發版本衝突與單次差異文件匯出 | 已完成程式與替代測試；基線收據時實際場景 revision 0，後續只記錄使用者明確確認的範圍 |
| 使用者可見項目核對 | Office／Classroom 已記錄；Auditorium 尚未開始。實際門孔量測、完整拓撲、人體淨空及 camera 對應仍未核准 |
| 確認後重跑 Top-K／曲線／影片 | Office rev20、Classroom rev15 已完成，保留全部 UNKNOWN；人工註記未用作幾何限制，尚無新權威匯入 |
| 真實攝影機串流、正式帳號與部署 | 未實作，未來階段 |

不以 Agent 作執行期判定，不讀 GT，不開啟／保存／複製原 `.blend`。來源 SHA 與證據封存維持既有版本，既有部分批准支持面只在原批准範圍內有權威；標註盒、預覽三角形、診斷見證與名義人體線框均不自動成為碰撞或通行證明。

局部灰色模型採來源三角面六平面裁切；畫面上緣可能是顯示裁切邊，不代表真實牆頂。門洞可手動選取「核對框上緣對齊目前模型的可見上緣」，只將黃色框的顯示副本上緣裁到已綁定來源的顯示上限，原 annotation 頂點、面與 focus 保留。取消可還原來源框。選項僅按 source／review／item／display archive 與裁切高度儲存在本機瀏覽器，不提交人工判定、不寫來源幾何、不提供門孔量測或通行權威；其他門、來源或顯示範圍不繼承此設定。

## 世界座標與人工核對方向

三組 Blender 核對沿用來源世界 XYZ 與來源原點 `(0,0,0)`；封存頂點先經原物件的 `matrix_world`，各分量只依已定比例 `1 BU = 0.0247 m` 換成公尺。工作台不額外交換軸、旋轉、平移或把地板高度歸零；Z 向上。相機平移採相同比例，旋轉保留。依據為 `configs/architectural_scale_school_v3.json`、`scripts/export_physical_authority_evidence.py`、`src/amidst/workbench/blender_scene.py` 與 `frontend/workbench/scene.mjs`。

| 世界軸 | 本機核對方向約定 |
| --- | --- |
| +X／−X | 場景東／場景西 |
| +Y／−Y | 場景北／場景南 |
| +Z／−Z | 上／下 |

東、北等是本次核對的約定名稱，實際地理方位仍未知。3D 角落軸向指示隨視角更新，表示世界軸在畫面中的方向；角落中心不是場景原點，也不是門洞或地面接觸點。

固定截圖另用 O（黃色門洞框的畫面中心）及 L／R／U／D（圖左／右／上／下）記錄人工位置。O 不等於世界原點，畫面 L+D 等描述不直接換成世界通行方向：還需該圖的精確視角、投影／viewport，以及可對應的來源世界點或地面。座標定義與方向標示只供定位，不批准門孔、法向、走廊拓撲或人體淨空；未驗證部分繼續 UNKNOWN。

## 各層輸入、輸出與交流

| 層 | 本次具體輸入與工作 | 輸出到下一層 | 資料與測試來源 |
| --- | --- | --- | --- |
| 來源／匯入 | 已封存 camera RGB、校正、局部 mesh、來源三角形、支持面／孔洞、portal annotation、local scope 診斷與批准人體政策；比對來源與證據 SHA | 綁定 site/run/clock 的來源摘要、索引與局部預覽，不寫原模型 | 三組實際 Blender 來源封存；RGB 內橙色活動目標為預設替代資料 |
| 基底算法／審查索引 | 使用既有固定完整來源的物理候選結果，整理待確認門洞、支持連通、人體淨空；保留每項來源依據與缺失 | `physical_review` 清單、來源預覽、既有投影／推斷／缺失樣本；`camera_frame_wall` 每次最多 16 個索引記錄 | 實際來源和舊候選；沒有新的候選評分或影像掃描；核心測試用明標 SUBSTITUTE fixture |
| API | 瀏覽器只送 session、scene、所選 camera、時間段；服務端檢查 role、source、clock、已發出審查 ref 與版本 | 有界審查 DTO、分時影格媒體 ref、pending 狀態；禁止呼叫方提供幾何或 GT | 三組實際來源 HTTP；造假引用／跨 scene／角色／過時版本由替代端口 fixture 驗證 |
| 3D／2D 工作台 | 顯示來源模型、annotation／支持面／見證；來源時鐘同步投影點／推斷點與最近分時影格；缺失時移除動態點，不外推 | 使用者檢視來源依據、缺失與逐項清單；明確提交才送人工差異 | 實際 browser 與來源 DTO；WebGL 組件測試為 mock，不能替代實際畫面驗證 |
| 狀態／儲存 | 校驗後的人工檢查決定、證據引用、理由、reviewer、expected_revision；SQLite `BEGIN IMMEDIATE` 與版本比較 | append-only local revision、前後變更、parent hash；匯出僅該次差異文件 | SUBSTITUTE 人工輸入與 8 個同時寫入者階段測試；基線收據時實際三組零人工寫入 |
| 確認後重跑 | 使用者確認的時間段與 K，加上既有不可變來源；人工文字不作幾何限制 | Office／Classroom 新鮮候選帳、Top-K、曲線與影片，全部 UNKNOWN 保留；歷史版本不覆寫 | 已做兩站；實際 RGB／校正／局部來源幾何，投影／速度／候選為衍生或推斷，橙色目標與活動為 SUBSTITUTE |

層間錯誤局部處理：來源 hash 不符拒絕該請求；無影格顯示 MISSING；審查 source/scene/session 變更即清除過時引用；併發只允許同 revision 一次成功，另一請求得到版本衝突。替代 fixtures 用於接口、保存、衝突與同步測試，不能被當成三組實際來源的人工確認。

## 具體資料流與端口

`來源證據 + 既有物理候選 → BlenderPhysicalReviewIndex → /api/physical_review → 瀏覽器來源 overlay／時間樣本／待確認清單`。

`camera + 時間段 + 8/12/16 → /api/camera_frame_wall → index frame metadata → /api/media?session_ref=…&scene_id=…&ref=… → camera RGB`。不是 8–16 個新攝像頭；每格列實際 camera 與最近來源 timestamp。短時間窗重複同一來源影格時明列「重複來源影格」。HTTP 不執行 RGB 大規模掃描。

| POST 端口 | 必要輸入 | 具體輸出 |
| --- | --- | --- |
| `/api/physical_review` | `session_ref, scene_id, camera_ids, start, end` | `review_sha256, source_binding, evidence_hashes, items/checklist/pending_gaps, geometry_primitives, synchronized_evidence, review_state`；`baseline_results_unchanged=true, post_confirmation_rerun_performed=false` |
| `/api/camera_frame_wall` | 上述選取與 `slot_count=8/12/16` | 每格 `slot_index, camera_id, requested_timestamp, timestamp/media_ref` 或 null/MISSING、`repeated_source_frame`；索引讀取數 ≤16 |
| `/api/physical_review_decision` | 已發出 scene/review/item、`checks[{check_ref,decision,evidence_refs,comment}], expected_revision, reviewer, reason` | 本機差異 revision；只存改動檢查的前後狀態、證據引用與理由，不存 mesh／模型／影像／候選快照 |
| `/api/physical_review_delta` | `scene_id, review_sha256, revision` 與 session | 只該次差異 JSON；不匯出全部來源／審查快照 |

決定選項 `UNKNOWN / CONFIRMED_LOCAL / CONTRADICTED_LOCAL`。非 UNKNOWN 必須指定該項允許的來源證據並填寫理由；不預先勾選。任何本機 revision 都保留 `source_authority_changed=false, formal_approval=false, rerun_authorized=false`，避免把點選「支持」直接當成來源幾何批准。跨鏡頭事件與候選技術 ID 僅留在 log；主畫面與技術折疊內容均不顯示。

## 逐項待確認內容

門洞：核對來源門框、門扇與牆面；確認實際通行法向及門兩側落腳面；量測最窄淨寬 ≥0.7 m、淨高 ≥1.8 m；確認 source site/camera 空間關係。現有 annotation 範圍不是實際門孔，名稱不能證明房間歸屬。

走廊：核對原支持面三角形接續、實際高度、孔洞與未分類障礙；確認 local支持域之間真正連通；來源時鐘／投影／候選路徑不是跨鏡頭身分證明。核准部分支持面也不能推出全場可通行。

人體淨空：核對原三角面接地高度；補核對牆、門扇、家具與天花的來源面、退化面和封閉體；政策半徑 0.3 m、高 1.7 m 是名義直立圓柱，不是人物量測。線框只附於來源觀測投影；推斷位置僅顯示琥珀點，缺失不畫人體。Office 有 7 組現有來源見證；Classroom 與 Auditorium 缺少對應本體診斷匯出，保持 UNKNOWN。

| 場景 | 待確認項／檢查數 | 完整來源同步投影點／推斷點／缺失點 | 缺失區間 |
| --- | --- | --- | --- |
| Office | 4／14 | 59／0／2 | 3 |
| Classroom 101 | 3／10 | 70／4／0 | 1 |
| Auditorium | 4／14 | 153／39／9 | 18 |

以上是有界審查樣本，非唯一人物數，也非真實軌跡 GT。不同候選可共享原觀測，不將重合樣本平均或強行合併；窄時間段只裁切同步顯示，不改完整來源的候選排序。Classroom 的 CORRIDOR_04 有來源 RGB，但沒有可用投影；缺失保持未知。

## 收據與限制（入口建立時的歷史基線）

入口建立時的歷史完整 Python 3,186 passed，0 failures/errors/skips，`--require-physical-evidence`；510 個後端輸入文件的測試前後指紋一致。核心32／store8／service6 已包含在完整數量中，不另行累加。Node 160 passed（workbench147＋product13），0 failures/cancelled/skips；最終前端程式樹前後一致。Ruff 全 src/tests/scripts 與 strict mypy199來源檔通過。154 次本機 HTTP／5,119 項逐欄位及邊界斷言通過；只讀三組來源並保持人工 revision0。三組實際 browser 核對與畫面牆 8／12／16 格切換通過，無 console warning/error；這些是本機工程驗證，不能當成來源物理認證。


入口建立時的檢查及來源摘要集中在 `data/engineering/blender_physical_review_20261013/`，其中 validation 綁定當時程式樹與實際執行範圍。前一物理篩選 checkpoint 的 3,140 Python／122 Node／60 ports／175 HTTP 是歷史收據，不當成本階段重跑。當時既有 motion／association／physical v1/v2 三組的 36 份曲線、影片和 manifest 核對原 bytes 未變，未重新編碼；Office／Classroom 確認後的新產制另見 checkpoint 收據。

GitHub 只保存程式、文件與有界 hash/count/reason 收據；原 `.blend`、完整 mesh、RGB、追蹤資料、影片、資料庫、session 和實際人審筆記維持本機。正式 Phase 1 Cases 2/3、Exit 與 Phase 2 凍結範圍不因此改變。
