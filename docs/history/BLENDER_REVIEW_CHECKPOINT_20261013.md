# Blender 人工核對 checkpoint / Human-review checkpoint

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

2026-10-13 依使用者指示停止場景續作，整理文件、驗證、commit 與 GitHub 發布；`phase1-finalization` 的移除須等共享 Phase 2 任務完成。此次不開始 Auditorium、不泛化場景、不改 main 或 frozen refs。此 checkpoint 保存程式、差異摘要和來源／產物 hash；不提交原 `.blend`、RGB、影片、完整幾何、人審原文或 DB。

### 已完成與尚未完成

| 場景 | 人工差異 | 確認後重跑 | 仍缺依據 |
| --- | ---: | --- | --- |
| Office | revision 20，20 筆 append-only 紀錄 | 完整 0.0–9.8 s，Top-3；3 解全 UNKNOWN、拒絕 0，完整決策帳 5 解。新曲線／影片已產出且全片解碼通過 | 門孔量測／法向、完整走廊拓撲、實際接地／人體間隙／頭頂面、camera 像素對應與房間歸屬 |
| Classroom 101 | revision 15，15 筆紀錄 | 同完整時間段、Top-3 畫面為 4.2／4.4／4.6 s；事件只回 1 個 UNKNOWN 未關聯基線、6 段局部軌跡、0 跨鏡頭邊／0 拒絕 | 第一支持面已更正為教室內；+X 指認區只有網格，沒有來源外部地面；門孔量測、走廊接續、接地／間隙／頭頂面及 camera 對應仍未知 |
| Auditorium | revision 0 | 未人工確認，未啟動確認後重跑；既有截斷候選與素材是歷史結果 | 門洞、走廊與人體淨空逐項核對尚未開始 |

三站合計 11 個核對項／38 checks。可見確認只記錄當下表面、方向與貼合關係，38 個有效物理判定仍 UNKNOWN；不核准幾何或全時段通行。人工歷史的 `formal_approval`、`source_authority_changed`、`rerun_authorized` 仍 false；本次重跑授權另由使用者明確回覆記錄，不能把歷史旗標翻成幾何批准。

Classroom 有 50 張來源 RGB、70 個像素衍生投影、4 個短內插點、64 個有限差分速度。CORRIDOR_04 有 50 張 RGB，但觀測／投影都是 0；不是缺相片，也不補出第二、第三事件解。物理檢查共 144 次：局部支持 63、已知組件範圍外 69、支持域淨空不足 6、全場人體淨空未知 6；實際碰撞三角形測試 0，不代表全場無碰撞。分數 0.227941 是設定的局部支持分數，不是機率。

來源 RGB／校正／局部模型為實際 Blender 資料；橙色目標和活動是替代資料；位置、內插、速度及跨鏡頭路徑為衍生或推斷。原模型 hash `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`、468300506 bytes、mtime_ns 1791198236746106977 前後一致；未開啟、改動或複製 `.blend`，未接串流，不使用 Agent／GT 決策。

### UI 與驗證對應

- `app.mjs`、`workbench-layout.test.mjs`：頂部點擊切換 3D／2D，8／12／16 格選项只在 2D 顯示；格數是兩個鏡頭的分時影格。
- `geometry.mjs`、`scene.mjs`、`scene.test.mjs`、`world-directions.test.mjs`：沿用來源右手 XYZ／Z-up、原點及 0.0247 m/BU，隨視角顯示來源世界軸；不改幾何、法向、來源權限或 canvas 姿態。東／北是核對名稱約定，不是地理方位認證。
- 2026-10-13 checkpoint 的 scoped Node **56/56 PASS**、語法及 owned diff 檢查 PASS，驗證前後相關檔案 hash 一致。這次沒有重新執行歷史完整 Python3186 或 HTTP154／5119，不把它們標成本輪測試。
- Office／Classroom 的新 PNG、MP4、manifest 與歷史 v2 位元組相同，因來源和演算法權限未變；均為重新計算及重新產制，沒有覆寫舊包。每站 1280×720、5fps、50 幀／10 秒；source9.8 s 的最後幀保持 0.2 秒。FFmpeg 全片解碼 PASS，ffprobe N/A。
- Classroom 第一次 editable import 指向另一 checkout；已用明確工作樹 `PYTHONPATH=src` 重建，四份 JSON 逐位元相同。Corrective run 的 61 個預載程式檔前後相同；物理模組晚導入，僅有該輪後置指紋，不假稱前置捕捉。工作台完整播放至 10 秒、來源游標 9.8 s；瀏覽器 MP4 下載未完成，與本機全片解碼分開記錄。

### 發布與保存

公開有界收據位於 [blender_review_checkpoint_20261013](../../data/engineering/blender_review_checkpoint_20261013/)。完整人審 delta、DB snapshot、重跑腳本、JSON、曲線／影片與私人驗證在 canonical checkout 的 ignored `data/pilot/retained_checkpoints/phase1-finalization_20261013/` 保存，續作不依賴待移除工作樹或 `/private/tmp`。保存不得跟隨 symlink 複製 `.blend` 或 GT；來源、舊備份與其他工作樹保持原位置。

盤點時工程 HEAD 已包含三個先前未推提交 `001a0fc`、`8aadeb3`、`7d05354`；它們屬平行 Phase 2 與文件工作，本次不改寫或混稱為人審驗證。三提交新增 121 個 unique blobs，約 6.13 MB，最大 2.52 MB 為公開 benchmark DTO JSON；沒有新增 `.blend`、raw DB／GT 或影音 blobs。main／Phase2 frozen donor 不由此發布自動合併或解凍。最終 commit 與遠端確認以實際 Git receipt 為準，不預編 SHA。

清理條件：共享任務完成、最後 dirty／HEAD／遠端核對、一致 DB 與獨有資料保存、仍使用該 checkout 的服務退役或切換後，才移除這個 Git worktree。其他 main demo、preview、canonical 原資產、分支和歷史保留；本文件發布時不宣稱清理已完成。清理實際結果另存外部本機 receipt。

後續人審需新的明確續作指示：先 Auditorium 逐項核對，再對照三站實際候選／缺失／拒絕與 UNKNOWN；只有可驗證來源證據才更新物理限制。

## English

The user requested a checkpoint and publication, with removal of the shared finalization checkout **after the active Phase 2 task completes**. Human-review continuation is stopped; Auditorium and scene generalization are not started. Office revision20 and Classroom revision15 hold 35 append-only local deltas, without geometry-authority promotion. All 38 effective physical checks remain UNKNOWN.

Both confirmed reruns cover source0.0–9.8 s with requested Top3 and fresh curves/videos. Office returns three UNKNOWN candidates and no rejection. Classroom returns three frames but only one unassociated UNKNOWN event baseline with six local tracklets and no cross-camera links. CORRIDOR_04 has actual RGB but no usable observations/projection. Apertures, external corridor topology, measured contact/gaps/overhead clearance and camera ownership remain unverified.

The six UI files provide 2D-only grid choices and a source-world direction compass; 56 scoped Node tests, syntax and owned diff checks passed with unchanged inputs. Prior full-suite receipts remain historical. Original Blender bytes/mtime are unchanged; no Agent/GT decision, stream, source opening, copying or modification occurred. Fresh media fully decoded and equals historical v2 bytes. The corrective Classroom import scope and unsuccessful browser MP4 download remain explicit limitations.

Publish code, documentation and bounded counts/hashes only. Keep the exact local deltas, consistent DB snapshots, rerun inputs/outputs/scripts and private evidence under the canonical ignored retention directory; no raw assets are added to Git. Existing parallel commits remain separately attributed. Do not remove the checkout until active users are finished and retention, remote publication and service retirement checks pass. Keep main demo, other worktrees, immutable assets and frozen refs.
