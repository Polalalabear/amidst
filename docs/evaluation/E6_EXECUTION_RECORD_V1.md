# E6 執行紀錄規格 v1（#717；#721 的實作輸入）

本檔只定義紀錄，未啟動 blocked 的 #721。每次執行獨立 run_id；身份
`UNCONFIRMED`，所有推論端欄位不得含 GT、renderer 軌跡、visibility、depth 或劇本答案。

共用來源 envelope：schema_version、run_id、case_id、arm、k、mode、tick_us、size、
source/index/records/RGB descriptor/calibration/config/code/protocol SHA-256。
推論紀錄與 GT 評分紀錄分檔；以 run_id、capture tick、camera_id 關聯。

| 階段 | 必填欄位與意義 |
|---|---|
| REQUEST | request_id、ask_tick、FIRST/POLL/LOST_EARLY、原始請求 SHA、reference SHA、每鏡頭影格 SHA、完整候選清單（camera_id、該次 detection_id、框、score、color evidence、gate reasons）、提問前 own_tracking、neutral_status、last_known_position/tick 或明列 MISSING、獨立 rule_state（若有） |
| RESPONSE | request_id、原始回答或其 LOCAL 路徑與 SHA、模型 digest、answer、selected_camera/detection/box、ranking、confidence、provider latency、usage；provider error/timeout/guard denial 仍須留一筆 |
| VALIDATION | request_id、accepted boolean、reason、validated answer/selected box、是否仍在 pending、call cap 狀態；接受不等於採用 |
| APPLICATION | request_id、ask_tick、apply_tick 或 MISSING、requested box、actual adopted box、source、applied boolean、fallback reason、expired reason、套用前後 own_tracking；UNCERTAIN 是合法不改動，applied=false；pending_at_end 不得冒充已套用 |
| TRACK | 每 tick：own_tracking（含框與估計位置）、neutral_status、tracker_action（FOLLOWING/COASTING/LOST/OCCLUDED_HOLD/ADOPT/CLEAR/NO_CHANGE）、作用中的 request_id、events、last observed tick；中性追蹤與新回答接管分開 |
| SCORE（獨立評分檔） | run_id/request_id、ask_tick 的 GT-side answer judgement、apply_tick 的分類、直到下一次實際接管的每 tick 分類、visible/blind 分母與裁切規則；GT provenance 和主準則/Iou 準則分開 |

「回答當下」以 ask_tick 的候選框評分；「套用後」以實際 run.rows 評分。
本次 AO 描述切片到下一筆已釋放回答，UNCERTAIN 也切片，故是回答時序描述，
不是因果歸因；正式記錄應另保留 active_request_id，跨 UNCERTAIN 連接實際接管。
舊 A2 沒有完整 candidate_list，**MISSING**，不能拿新結果或 GT 補成原請求。
舊 AO 有候選清單、ask/applied tick 與 rows，可派生描述欄位，但缺完整逐階段
原始事件時不得宣稱舊紀錄已符合本規格。

正式 12 段的錄製前設計偏離（起點修正、`TRUE_DEPARTURE`→`FULL_BLIND`、S12 尾段）與關卡結果見 [E6_ROUTES_RECORDING_20261127.md](E6_ROUTES_RECORDING_20261127.md)。
