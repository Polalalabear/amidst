# #418 Office 多教室靜態預覽：待核定參數

狀態：**PROPOSED / USER_APPROVAL_PENDING**。本 PR 只有核定表，尚未建檔、渲染、產生 graph 或執行推論。#418 尚未完成，不交 `review:claude`。

## 本次請核定的方案 A

建立**獨立、程序建模的 Office 示範場景** `office_expanded_r005`：四間教室 R101～R104，四台室內鏡頭、兩台走廊鏡頭。採新 scene ID、新 graph 目錄，保留現有 r004 原始場景及 v3_1。這是新 layout 提案，不宣稱是既有 Office 幾何的復刻；如必須沿用原 Office 房間配置，需先改本核定表，不能把以下座標套到原場景。

機器可讀參數見 [d127_418_parameters.proposed.json](d127_418_parameters.proposed.json)。所有座標是**擬定的靜態 authoring 值**，不是測量值、renderer 觀測或 inference 輸入。單位 m；X/Y 水平、Z 向上；鏡頭 `BLENDER_NEG_Z_UP_Y`，以位置與 look-at 產生旋轉。

| 區域 | 地板範圍 X / Y（m） | 門中心 XY（m） | 室內鏡頭位置 XYZ → look-at XYZ（m） |
| --- | --- | --- | --- |
| R101 | [0,7] / [-6,0] | (3.5,0) | (0.5,-5.5,2.6) → (3.5,-3,1.0) |
| R102 | [9,16] / [-6,0] | (12.5,0) | (9.5,-5.5,2.6) → (12.5,-3,1.0) |
| R103 | [0,7] / [2,8] | (3.5,2) | (0.5,7.5,2.6) → (3.5,5,1.0) |
| R104 | [9,16] / [2,8] | (12.5,2) | (9.5,7.5,2.6) → (12.5,5,1.0) |
| CORR_MAIN | [0,16] / [0,2] | 四個房門 | CAM_CORR_W=(0.5,1,2.6) → (12.5,1,1.2)；CAM_CORR_E=(15.5,1,2.6) → (3.5,1,1.2) |

牆高 3.0 m、厚 0.18 m；門洞寬 1.2 m、高 2.2 m。房號以一般靜態門牌顯示；不把房號或 authored 物件類別當模型答案。走廊分 CORR_W/CORR_E 於 x=8 接合；房間只與對應走廊 segment 有 proposed portal 邊。連通、淨空與物理通行仍 UNKNOWN。

## 物件與渲染清單

每間先放 2 張 chair、1 張 dining table；另各有以下查找目標：R101 laptop + bottle、R102 book + backpack、R103 cup + laptop、R104 bottle + book。這些是 COCO 類別的**建模目標**；只用 repo 程式新建幾何與材質，不下載資產、不載入原始 blend。不保證簡化外觀能被 detector 辨識，實際辨識須獨立 RGB 測試。物件尺寸、房內相對位置與色彩的固定值列於 JSON；不因辨識成績事後挑影格或改標籤。

- 先只渲染 7 張：6 台相機各 1 張靜態 RGB，另 1 張人用俯視 layout。沒有動態人物、動畫、影片或研究評分；短片另列參數核定。
- 960×540、100%、RGB8 PNG，EEVEE、64 samples、固定 seed=7（引擎支援時）；室內各一面積光，1200 W、size=4 m、z=2.8 m；world strength=0.3、Standard 色彩轉換。
- 四室內鏡頭 HFOV=85°，走廊 HFOV=75°；sensor_width=36 mm，sensor_fit=HORIZONTAL，pixel aspect=1，shift=0，clip=[0.05,100] m。匯出完整 K、camera_to_world、calibration hash 與來源 hash，不能只記相機名稱。
- 俯視圖只供靜態 layout 人工檢查，與實際 camera RGB 分開；不進檢索、detector、ranking、reconstruction 或推論。
- 擬定 LOCAL 根目錄：`/Users/polalabear/amidst-artifacts/d127-418-office-expanded-r005`。必須是新目錄；已存在、symlink、來源 hash 不符時拒絕。此路徑目前只是提案，尚未建立。

## 磁碟與授權

[D118](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6580320736) 的 8 GiB 特例原限 CX-7；[D126 擴充場景指示](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6621356045) 已對本工作指定低於 8 GiB 停止。不得拿 D118 推導任意其他工作授權。

本方案另預留最多 256 MiB 建檔／PNG／暫存支出與 256 MiB 余量，開工需至少 **8.5 GiB** 可用；每個建檔／渲染階段前後量測，支出超過預算或 free<8 GiB 即停止、不自動清檔。2026-11-04 本 chat `df -k /private/tmp` 快照 8,750,940 KiB（約 **8.346 GiB**），低於本方案開始門檻；渲染前必須重查，不能沿用快照。核定參數也不豁免磁碟 gate，不在此要求刪除任何資料。

## 後續實作與驗收

1. 使用者在 #418 記錄核定參數版本／hash、允許新建檔與七張靜態 RGB 的明確授權。若改 layout，先更新此表及 JSON。
2. 依 #415 的安全入口模式做新 builder；不帶入 #411 的 synthetic fixture builder 或其他 PR 全部變更。新 code 由 Argon 可負責的純程式部分完成，本機 Blender 驗證由 Codex 執行；不能將預設合成值標成真實資產。
3. 新路徑 `configs/q1q5/graphs/office_expanded_r005/` 產生 region_graph、camera_graph、source_pins 與人工覆蓋 receipt。`covered_regions` 起始 NOT_EVALUATED；看過實際靜態 camera RGB、確認室內範圍並記 camera/frame/hash/人員／日期後，才能寫 `MANUAL_ON_STATIC_FRAME`。射錐或建模位置不是人工覆蓋證據。
4. entry/exit、transitions 均需靜態來源與校正 hash；只有視線或拓撲資料時保留 UNKNOWN/TOPOLOGICAL_ONLY，不發明可切鏡候選或通行 PASS。
5. #410/#443 的 `test_r004_scene_rooms_have_an_indoor_manual_camera` **硬讀 r004/v3_1**，不能只新增此場景便聲稱它消失。請契約 owner 先確認新 scene 的 runtime 選擇與 source-bound 測試入口；既有 v3_1 bytes、歷史 coverage 缺項與斷言均保留，不用改 skip／假 manual 值消除 gate。
6. focused 驗證：新 builder 的無 bpy `--help`／拒絕既有輸出和 symlink／source pins；新 graph 的四房實際 manual 覆蓋與缺證據反例；`git diff --check`；無 allow architecture guard。實際執行的命令、hash、時間及數量於當次記錄，現在均 NOT_RUN。

## 本次實際產出與來源

- 本次新增 2 份核定文件；未改 code、測試、graph、source assets 或他人 checkout。
- 只讀參考 #415 Draft #446@`e76a8a6521ffe7755276fe5e6f123a6ff7d6f0c4` 的建檔程式與 safe camera catalog；這不是對 #446 的獨立採用／驗收。#414 已在 #442，#416 由其他 chat 認領，本 chat 不重做。
- #412 Draft #443@`20ea00fbfc0aa927a1fbc73b048d81641ccdd413` 提供契約測試現況；原 `build_office_expanded_scene.py` 已判定只能當 synthetic fixture，不可當 Blender 成果。
- Blender executable metadata VERIFIED：`/Applications/Blender.app/Contents/MacOS/Blender` 存在。版本、EEVEE API 相容性與實跑 NOT_VERIFIED；未啟動 Blender。
- r004 frozen file SHA-256：region_graph_v3_1 `a2f737805cf5446c6ba01fa4bebfddd2186d040cbd94314cf573c082191b24e1`；camera_graph_v3_1 `e250413a0d0a2aeb61bd98bb1763236b1e39127f919cee1ee3ca3bd906b78409`；build_plan_v3_1 `277d0e9376f8d0bcb055d11aac7e856a4ae50b541bf7519c719a998c2f1b3d51`。
- 未讀 GT／gt_private／原始媒體／真 API key；未渲染、推論、取模型權重或做正式研究。參數表可供核定，不代表 #418 test gate 已完成。
