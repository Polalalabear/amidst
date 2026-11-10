# 主專案 worktree 與 finalization 退役評估

盤點時間：2026-10-20 13:15 Asia/Taipei。範圍限於 canonical checkout 的三個 `.local-worktrees`、既有 handoff、相關 launcher 與服務。這是唯讀評估結果；只新增本文件，未執行退役。

## 結論與本次要求

- 使用者明確要求保留 Qwen Agent，並將 Qwen 與 OpenAI API 作為語意分析依賴。本次不刪模型、不變更 provider，也不呼叫付費 API。
- 三個 worktree 均未達整樹移除條件。finalization 仍是 Ollama、PostgreSQL、Office evidence/vendor 的實體依賴；formal/clean 保存正式與重現產物。
- 可先規劃「執行服務及必要資料脫離 worktree」，再移除不再需要的 checkout。搬移同一磁碟上的必要模型與資料本身不回收空間。
- 主 checkout 已包含 finalization HEAD 的 Git 歷史；仍須處理 dirty 檔、ignored 資料、環境與 locator，不能只因程式已存在就刪樹。
- 已盤點的 `src/amidst/local_agent` 在主 checkout 與 finalization 都只見 `OllamaProvider` / `OLLAMA_LOOPBACK`；`src`、`configs`、`pyproject.toml`、`uv.lock` 的 OpenAI 文字搜尋無命中。OpenAI API 接線狀態為 UNKNOWN，不能宣稱已完成雙 provider 整合。本次保留此需求，不擴大成 API 實作或修改既有架構規則。

## 工作樹與 Git

下列大小是各目錄分開執行 `du -sk` 的配置用量，跨樹硬連結會重複計入，因此不可相加。整個 `.local-worktrees` 一次量測為 7.289 GiB（7,642,980 KiB）。APFS clone、壓縮與其他程序寫入也會影響實際回收量。

| 路徑（相對 canonical） | HEAD / branch | 獨立用量 | 現況與判斷 |
| --- | --- | ---: | --- |
| `.local-worktrees/phase1-finalization` | `c6661dd53507805deb4613f30afb31798987bfd5` / `codex/simulation-engineering` | 6.205 GiB | 1 modified、2 untracked、24,483 ignored files；服務與 Office 依賴仍在，KEEP |
| `.local-worktrees/phase1-case23-formal` | `043bed2d6dac34698260bd37faefc31b9009d3ca` / `codex/phase1-case23-formal` | 0.877 GiB | tracked clean，但 3,447 ignored files 含 formal release；KEEP |
| `.local-worktrees/phase1-case23-clean` | `c4a8a0acfd3de2a8e266cf8463c9982610e5fe1d` / detached | 0.418 GiB | 9 untracked files、1,075 ignored files；必要 clean reproduction release；KEEP |

`git rev-list --left-right --count HEAD...codex/simulation-engineering` 在 canonical 回傳 `147 0`。三個 HEAD 均可由現存本機 refs 到達；formal/clean 亦由 `phase1-scoped-case123-20261014` 等 refs 保留。沒有 fetch 或核對遠端即時狀態，`origin/*` 僅為本機 cached refs。

finalization 必須先保存或有意識整合的未提交項目：

- `docs/engineering/DEMO_V1.md`：14 行新增 launcher 操作說明。
- `scripts/start_local_demo.py`：untracked，舊 demo 的服務管理與 state preflight。
- `start-demo.command`：untracked，launcher 入口。

主 checkout 與 finalization 的 `pyproject.toml`、`uv.lock`、`src/amidst/local_agent/provider.py` bytes 相同；這不代表整套 runtime 已在主 checkout 重建或驗收。

## finalization 的服務與消費者

PID、埠與 cwd 僅代表此次快照，不可作為未來停止命令的固定值。

| 消費者 | VERIFIED | 退役要求 |
| --- | --- | --- |
| Ollama PID 97769 | listener `127.0.0.1:11437`；cwd 為 finalization；`GET /api/tags` 僅列 `qwen2.5:7b-instruct` | 保留原模型、digest、provider 設定；移出 worktree 後須重新綁定模型位置及服務 cwd/log；需要後續服務切換與驗證 |
| PostgreSQL PID 68475 及子程序 | cluster/cwd 在 finalization；socket `/private/tmp/amidst-pg-abc`、port 55432；`pg_isready` accepting connections | 保留原 DB、角色、schema、設定、必要備份；一致備份與還原／切換驗證完成前不可刪 cluster |
| PostgreSQL 資料 | 唯讀交易查到 `amidst_local` 有 14 個 base tables；當前 database size 121,501,375 bytes；排除稽核連線後 client connections=0 | 單次零連線不能證明沒有未來消費者；不表示資料已可刪除 |
| 舊完整 Workbench | 當次程序／listener 盤點未見 finalization 的 `amidst.workbench` | 未驗證完整重啟或 Agent session 恢復；不將舊 runtime.json 當活服務證據 |
| 主 checkout 的 Office launcher/backend | `scripts/start_office_demo.py` 預設 `OFFICE_EVIDENCE_REPO` 指向 finalization，vendor 由其 `frontend/workbench/node_modules/three` 取得；backend 亦讀原 motion/physical evidence | 必須保存必要 evidence 與 vendor，顯式改綁來源並驗證原 source/run/hash；當前無執行完整 launcher |

`lsof -Fpn` 以三個絕對目錄前綴過濾：finalization 有 34 筆 open-file/cwd entries，來自 PostgreSQL 與 Ollama；formal/clean 當次各 0 筆。這不是永久無消費者證明，也沒有檢查所有其他聊天的任務 ownership。

另確認 Claude 的 8765 review server 讀 canonical controlled-scene runs、使用 `amidst-claude/.venv`；8766 靜態服務 cwd 在 Claude scratchpad。兩者均不屬本次可停服務。

## 必須保留的資料與空間

| 相對 finalization 的位置 | 配置用量 | 判斷 |
| --- | ---: | --- |
| `data/engineering/local_run/phase2_abc/ollama_models` | 4.361 GiB | 保留；5 個必要模型 blobs 的 API 邏輯合計 4,683,087,332 bytes。移動位置不節省此空間 |
| `data/engineering/local_run/phase2_abc/postgres` | 約 0.310 GiB | 作用中 cluster、設定、backups；保留，資料 freshness／一致還原尚未核對 |
| `.venv` | 約 0.757 GiB | 後續可整併候選；必須先證明保留的 Qwen runtime 與其他消費者可由既有適當環境執行。含絕對 shebang/editable 路徑，不能直接搬走就宣稱可用 |
| `frontend/workbench/node_modules/three` | 約 22.25 MiB | 主 Office launcher 仍引用，需保留或在既有環境重用並驗證 |
| `frontend/product/node_modules` | 約 22.25 MiB | 歷史能力與重現依賴尚未判定退役，不列為確定可刪 |
| `data` 其餘部分、`human_review` | 未列入確定可回收量 | 包含 E0/E1、accuracy-v2、ABC certified baseline、0511 負結果、原 source/run pins、人審與收據；需逐組消費者核對 |

formal release 位於 `phase1-case23-formal/data/finalization/reviewed_run_case123_formal_v2_20261014/`，clean release 位於 `phase1-case23-clean/data/finalization/reviewed_run_case123_clean_v2_20261014/`。不能因其未進 Git 或沒有開啟檔案而當成垃圾。原 `.blend`、RGB、GT、校正與凍結 authority 不在可刪範圍。

本輪確定可直接移除的整樹：NONE。日後若 `.venv` 可退役，單項候選約 0.757 GiB，仍不是已證明回收量；資料、模型與必要 vendor 會繼續占用磁碟。

## 交接備份與 state 缺口

canonical `data/pilot/current_dependencies/handoff_20261014/private_handoff_manifest.json` 的 134 個 bindings 已重新驗證 size 與 SHA-256：134 PASS、missing 0、mismatch 0。這只證明保存的交接包與其 manifest 相同，不證明與今天的 live DB 一致。

- 交接包仍包含四個 SQLite 備份及 `state/amidst_local.dump`；備份時間為 2026-10-14。
- 其 manifest 明列 `source_assets_models_moved=false`、`worktrees_removed=false`，不是完整搬離 worktree 的證明。
- `demo_launcher/runtime.json` 與 launcher 都引用 `/private/tmp/amidst-physical-review-workbench-20261013-qa.sqlite3`。此原檔及同 stem 的 `-local-agent`、`-accuracy-v2`、`-operator-study` 三個 siblings 本次皆 MISSING。
- 未搜尋整個電腦尋找 state，未證明沒有別的 state 副本或 override；MISSING 僅指上述四個確切路徑。
- 舊 launcher 有缺件檢查；本次沒有執行 launcher、建立空 DB、恢復覆寫、migration 或新模型推理。
- 現有 dump 能否還原今日必要內容、四 SQLite family 的一致性及 Saved Agent recovery 均 UNKNOWN；歷史還原結果不是本次驗證。

## 建議的退役次序（尚未執行）

1. 將三個 dirty 檔、現存 refs、live state 缺口及本次盤點記錄列為切換前基線。保留 branch/tag 與 frozen release，不使用 reset/force。
2. 先規劃獨立於 worktree 的固定 runtime/data 位置，重用唯一 Qwen 權重、原 PG、必要 evidence 與既有 environment；避免新增 worktree、venv 或大量 raw 副本。目的位置與 consumer 清單需在執行前明確化。
3. 先處理四個 SQLite 原路徑 MISSING：在獨立且不存在的新目標評估恢復交接 state，保留 family 命名與憑證／owner；原包不覆寫。若需實際還原，另行進入受控切換工作。
4. 對 PG 做新的受控一致快照與必要還原驗證，保留原 cluster 到驗證完成。只移除指定實例，不能改用新空 DB 冒充原狀態。
5. 保存並顯式改綁 Qwen、provider、PG、Office evidence/vendor 與 absolute source locators；以保留功能的 focused checks 驗證。Qwen 與 OpenAI API 的語意分析需求保留；OpenAI 接線未確認，不能把本次遷移當雙 provider 驗收。
6. formal/clean 先維持實體原位，直到使用者決定所需重現範圍、必要原產物有明確保存位置且 source-bound 引用已核對；不為刪工作樹再做大型封存副本。
7. 上述依賴解除後，重新核對服務 ownership、open files、dirty、refs、受保護資料與現行 checkpoint，再提出精確退役範圍並執行相應授權。工作樹移除不得 force；遇未保存資料即停止。

既有 `CURRENT_WORK_REPRODUCTION.md` 第 9 節仍記錄共享任務驗收、精確發布、狀態保存與 quiescence 等退役前提。本次未查 GitHub checkpoint 的即時批准狀態，也未宣稱歷史品質門檻已解除。本次新要求足以進行此評估，不代表已完成那些前置驗證。

## 實際產出 / Actual output

- Model / effort: UNKNOWN（本輪未取得可核實的精確 model/effort）。
- PR / commits: NONE；未 stage、commit、push、PR、merge 或變更 refs。
- Files changed: `docs/history/WORKTREE_RETIREMENT_ASSESSMENT_20261020.md`（本文件）。
- Commands run and results: `git status --short --branch`、`git worktree list --porcelain`、各樹 `git ls-files` 與 `git for-each-ref --contains <HEAD>`；`git rev-list --left-right --count HEAD...codex/simulation-engineering` → `147 0`；`du -sk`、`df -k .`、`ps`、`lsof`、`pg_isready`；既有 manifest 的 Python stdlib size/SHA-256 核對 → 134/134 PASS；`GET http://127.0.0.1:11437/api/tags` → 1 個 Qwen 7B；`git diff --check` 通過（新增文件另作 whitespace 檢查）。
- SQL: `BEGIN READ ONLY; SELECT 'client_connections=' || count(*) FROM pg_stat_activity WHERE datname=current_database() AND backend_type='client backend' AND pid<>pg_backend_pid(); SELECT 'tables=' || count(*) FROM information_schema.tables WHERE table_schema='amidst_local' AND table_type='BASE TABLE'; SELECT 'database_bytes=' || pg_database_size(current_database()); COMMIT;` → 0、14、121501375 bytes。
- Artifacts: 本文件；未產生模型、資料庫、媒體或大型 backup。文件 SHA-256 於對話交付，不在文件內自我引用。
- Verified: 三樹現況、Git 可達性、134 個既有交接 bindings、指定 state 路徑缺件、現場服務／consumer／容量與命名範圍內的 OpenAI 搜尋。
- Not verified: 遠端即時 refs/checkpoint、跨聊天 ownership、formal/clean 全產物 hashes、live DB 對備份等價性、state restore、完整重啟／browser acceptance、模型 completion／品質、OpenAI API 整合、環境重建、實際可回收量；未跑程式測試或全套研究流程。
- Deviations, UNKNOWN items and follow-ups: OpenAI 語意分析為本次保留需求，接線未確認；舊 SQLite family 原路徑 MISSING；先解除 runtime/data 對 finalization 的依賴，才能具體評估 checkout 移除。
