# finalization 解除耦合與移除計畫（只列計畫，未執行）

> **2026-10-27 更新：**[D90-3](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423763378) 定案——磁碟維持現狀，三個 `.local-worktrees` 不動、不停服務、不搬移；本計畫不執行。之後 CX-7 或 L2-6 需要空間時再評估。

日期：2026-10-20（Asia/Taipei）。Refs [#131](https://github.com/Polalalabear/amidst/issues/131)。依 [D67 第 4 項](https://github.com/Polalalabear/amidst/issues/93#issuecomment-6292484288) 與使用者本次明確指示，將既有 LOCAL 計畫轉入 repo，交 Claude 審查。此授權只限文件交付，不包含任何搬移／刪除／服務變更。**下列搬移、uv sync、DB dump／restore、服務切換、tag、worktree remove 均未執行，也未獲本文件自動放行。**

## 1. 既有唯讀快照（不是本次重新盤點）

本節資料來自同日稍早的 LOCAL 文件，不是本次重新讀取 finalization 的結果。其來源檔是 `/Users/polalabear/amidst-artifacts/r004-scene-change-proposal/FINALIZATION_REMOVAL_PLAN.md`，原始 bytes SHA-256 `bd114e469064895729061d49e546a939c28d8dd8ded1cffd2984c702b4b28450`。PID、HEAD、大小與可用空間均可能已變，真正執行時必須重查；本文件保留它們以說明依賴，不能作為今天可刪除的證據。

| Consumer／資料 | 既有 locator／依賴 | 解除條件 |
| --- | --- | --- |
| Ollama／Qwen | finalization 的 ollama_models；loopback 11437；啟動 cwd 依賴 | owner 停啟窗口、新 OLLAMA_MODELS 環境、模型 digest 一致、舊 cwd 不再占用 |
| PostgreSQL 18 | finalization 的 postgres；loopback 55432 | 一致 dump 與隔離還原驗證、consumer 改綁並保留必要資料 |
| 舊 Office launcher／backend | OFFICE_EVIDENCE_REPO、evidence 與 three vendor | locator 改綁並核對 source/run/hash；缺件保持 MISSING |
| Python 執行環境 | finalization/.venv，含絕對路徑依賴 | 主 repo 按鎖檔重建、focused 驗證，不直接搬 venv |
| SQLite／review／ledger／凍結 evidence | 舊評估記錄的 locator；部分曾 MISSING | 授權範圍內確認保存與 consumers，未確認者阻擋移除 |
| 三個未提交文字檔 | DEMO_V1.md、start_local_demo.py、start-demo.command | bytes／diff 保存、hash 與重建驗證，保留原工作 |

以下數值均屬上述舊快照：

- 根：`/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization`；HEAD `c6661dd53507805deb4613f30afb31798987bfd5`，branch `codex/simulation-engineering`，本機 cached tracking 顯示 behind 3（執行時需重新查遠端）。
- `git status --short --branch`：modified `docs/engineering/DEMO_V1.md`；untracked `scripts/start_local_demo.py`、`start-demo.command`。本輪未保存、提交或改寫這些檔案；以下第 1 步必須先完成保存。
- worktree `du -sk`：6,506,460 KiB（約 6.21 GiB），不是可回收量。
- Qwen store：`data/engineering/local_run/phase2_abc/ollama_models`，4,573,352 KiB（約 4.36 GiB）；目標 `~/.ollama/models` 本輪不存在。
- `.venv`：793,456 KiB（約 0.757 GiB）；主 repo `.venv` 本輪不存在。PG 目錄 `data/engineering/local_run/phase2_abc/postgres`：324,968 KiB（約 0.310 GiB）。
- 唯讀程序／lsof：Ollama PID 97769，cwd 是 finalization，listener `127.0.0.1:11437`；PostgreSQL 18.6 PID 68475，cluster cwd 在 finalization，listener `127.0.0.1:55432`。PID 只是當時快照，不能直接複製作 kill 命令。
- Office launcher `scripts/start_office_demo.py` 的 `OFFICE_EVIDENCE_REPO` 預設仍指 finalization，three vendor 也在其中；`scripts/office_demo_backend.py` 同樣引用 evidence/vendor。新 Q1–Q5 不用 PG，不代表舊 PG／Office 資料可刪。
- 既有退役評估曾記四個 SQLite state 路徑 MISSING；本輪沒有打開或還原這些 DB，也沒有讀取人審／GT。其目前內容、完整性、替代副本為 UNKNOWN，必須在未來隔離恢復任務處理。
- 本輪 `df -k` available 12,529,324 KiB（約 11.95 GiB）；`df -h` 顯示 12Gi。未達 12 GiB 的精確 render gate。磁碟為其他程序共享，兩次 df 差額不能直接歸因於此任務。

## 2. 未來分步執行順序、空間與驗證

所有步驟均先讀 `df -h` 與 `df -k`、記時間／available bytes；完成或中止後再讀一次。另記本步目標的 `du -sk`，區分邏輯 bytes、allocated bytes、預測與實際 free delta。任何檢查不通過就跳過／停止，不 force，不改服務保護或權限繞過。

| 步驟 | 未來工作與精確保存目標 | 暫時空間增減（估算） | 完成條件／回復方式 |
| --- | --- | --- | --- |
| 0 | 取得精確操作授權、重新核對聊天／服務 owner、HEAD／branch／遠端 refs、dirty／ignored／symlink、現行 consumer | 精簡收據 KB 級；實際 UNKNOWN | 任一 owner／路徑不明則 STOP。此計畫不是刪除授權 |
| 1 | 逐項保存上述 3 個 dirty 檔：差異、未追蹤腳本、原檔 bytes hash；在 `~/amidst-artifacts/finalization-retirement/<session>/dirty/` 私有保存，並規劃窄分支提交或使用者接受的保存方式 | 只存 3 個文字檔與 patch；大小執行前 stat，現為 UNKNOWN | hash 與可重建性驗證；不 stash／reset 他人工作，不把未追蹤檔當垃圾。不複製整樹或原始媒體 |
| 2 | 建完整 consumer／保留清單：模型、PG、SQLite family、Office evidence/vendor、凍結 release refs 與 ignored 唯一資料；目的地逐項明確 | 目錄／manifest KB 級；必要資料搬位置不減少大小 | 用檔名／metadata 和已授權收據核對。GT／人工標註原位保留；若需讀它們才能證明等價，本輪禁止，另等授權，不推定可刪 |
| 3 | 未來使用精確 owner 的受控停啟窗口，將 Qwen store **同一磁碟 rename** 至 `~/.ollama/models`；目標若已存在，先核對衝突，不覆蓋或合併未知 blobs | 模型約 4.36 GiB 繼續保留；同 volume rename 預期新增接近 0、回收 0；跨 volume copy 另需約 4.36 GiB，停止重估 | 搬前後檢查 manifests／blobs、digest／size／hash、同一模型 tag。失敗保留原路徑／回復設定；不得刪 Qwen 或只留下空目錄 |
| 4 | 新 Ollama 啟動環境設 `OLLAMA_MODELS=/Users/polalabear/.ollama/models`；延用核准的 loopback endpoint，cwd／log 改 repo 外，provider 用設定指向 | 設定／log KB 級；completion 可能增加 RAM／swap，成本 UNKNOWN | `GET /api/tags`／必要 metadata 可證 tag／digest，不能證語意品質。最小 completion 僅在另獲推論授權且先 df 後執行；服務沒有確實載入新環境就不算完成。launchd 管理時要改實際 job environment，不能只 export 目前 shell |
| 5 | 在主 repo 按鎖檔建立 `.venv`：計畫指令 `uv sync --locked --group dev`，不直接搬舊 venv（絕對 shebang／editable 路徑會失效） | 同時保留舊 env，暫增以舊 env 約 0.757 GiB 作量級參考；新依賴／cache／download 大小 UNKNOWN，不是上界 | 預先檢查 lock、Python、既有 cache 與下載範圍，所有下載先 df。確認 Python／import／指定 focused tests 及服務設定；不跑 full suite。來源與目標 env 並存直到功能驗證 |
| 6 | PG 用匹配 major 18 的 `pg_dump -Fc` 做新一致快照；另保存 globals／必要角色／設定。dump 放 `~/amidst-artifacts/finalization-retirement/<session>/postgres/`，私有權限，絕不進 Git | dump 壓縮量 UNKNOWN；舊 cluster 約 0.310 GiB 不能當 dump 上限。額外 temporary restore cluster 量 UNKNOWN，先估空間再操作 | dump exit 0／hash／`pg_restore --list` 只是可讀，不是已還原；不能以 2026-10-14 舊 dump 當今日一致備份。credential／globals 不出公開報告 |
| 7 | 在與原 cluster 不同、尚不存在的 repo 外 restore 目標做隔離還原；獨立 data dir／socket／動態或已核對空閒 port，不碰現行 PG | 同時保留原 cluster＋dump＋restore：暫增約新 cluster 量＋dump，實際 UNKNOWN | roles／extensions／schema／table counts／必要功能按獲准範圍比對；不讀 GT／人工標註內容。未獲必要 DB 讀取授權的資料保持未驗證並阻擋刪除。停止測試實例後只刪本任務自建、已核對不再使用的 temp cluster；dump 留到使用者決定 |
| 8 | 舊 Office evidence／vendor 與 SQLite state 明確保存及改綁；模型、PG 的長期位置也必須獨立於 worktree | 同 volume 移動必要資料回收 0；若必須複製，額外空間先逐項估；不能為了刪 checkout 再造大型 raw archive | 依既有 source/run/hash 保留狀態與完整性。缺 state 不建立空 DB 冒充恢復；不啟用外部模型 API。未解除 launcher 預設 locator 就不得移除 |
| 9 | 對舊 Office 的精確保留 commit 建立 annotated archive tag，tag message 記 dirty 保存位置／hash／runtime 遷移收據 | Git metadata 小量，不回收 worktree 任何資料 | 執行前 fresh remote SHA、tag 不存在／不衝突；tag 不包含 ignored 模型、DB、state。tag 推送依使用者／協調者授權，禁止刪舊分支或 force tag |
| 10 | fresh `lsof`／cwd／listeners／jobs、git dirty／ignored 與完整保留清單全部通過後，最後才提精確 `git worktree remove <finalization>` | 6.21 GiB 不是可回收值；模型／PG／必要資料已移出且保留，最多只計可重建重複 env／code 等殘餘；APFS 真實 free delta UNKNOWN | **不帶 --force**；工具拒絕或仍有資料未保存就停止。保留 main repo、Claude checkout、formal／clean 工作樹與 refs。移除後 df／du、source-bound locator、Qwen／PG／Office 所需 focused checks；不能承諾正式或瀏覽器驗收 |

## 3. 需要在真正執行前補齊

1. owner 與停機窗口；哪些舊 Office／Saved Agent／SQLite 能力必須維持；哪個精確 ref 作 archive tag。
2. 主 repo 新 venv 的鎖定環境與實際大小；不得假設 `uv sync` 一定離線，亦不在本輪建立 venv。
3. 模型搬移前後的 manifests／digest 檢查與實際 Ollama job environment；Qwen 仍保留，只搬 store。
4. PG 角色／dump／還原驗證範圍。這可能包含不能在本輪開啟的資料，未獲權限就保留原 PG，不以 UNKNOWN 當清理通過。
5. 必要 evidence／vendor／凍結產物／未提交內容的保存清單與逐項 locator；不得把 archive tag 當 ignored 檔備份。
6. 所有空間上界尚未量測，開始時重新算峰值：`extra_peak = new_venv + caches/downloads + dump + restore_cluster + required_copies + transient/swap`。同 volume rename 不列為回收量。磁碟不足就停，不靠先刪 finalization 取得空間。

## 4. 來源 LOCAL 計畫的歷史實際產出

只讀 `git status`／`git worktree list`、指定路徑 `ls`／`du`、程序名稱／`lsof`、launcher 中的 locator；未開媒體、GT、人工標註、DB 內容或模型權重。未呼叫 Ollama 推論。未移動、刪除、dump／restore、建 tag、uv sync 或 worktree remove。當時文件僅為 LOCAL，未放入 #97 的單檔 PR；本次才依 #131 轉入 repo。

## 5. 本次文件交付與驗證界線

本次只讀既有 LOCAL 計畫與 issue 授權、編輯這份文字、檢查連結與 diff，並開 Draft PR；未重新盤點模型或 DB 內容。上述未來指令只作計畫，不曾執行。ignored 3.68 MiB 清單仍在原 LOCAL `MVP_IGNORED_INVENTORY.md`／JSON，等待使用者逐項決定，沒有納入可刪清單或搬移。

#127 是 Q1–Q5 JSON／JSONL 契約檢查，不涵蓋本文件的服務遷移、PG restore 或刪除驗收。本 PR 執行對應版本工具並記錄「無適用產品文件／零產品檢查」；這不表示遷移通過。真正執行之前須另取得精確目標與操作授權，逐步完成第 2 節驗證。
