# 全部工作交接與結果重現 / Current work and reproduction handoff

盤點快照：2026-10-14，文件基線 `c6661dd`；本文的 HEAD／dirty／服務與依賴數字描述當次收據，不是文件閱讀時的即時檢查。本文是下一位接手者的單一入口；新[交接收據](../../data/engineering/work_handoff_20261014/receipt.json)與[資產摘要](../../data/engineering/work_handoff_20261014/asset_summary.json)綁定本次實際核對。工程程式未改，11私有候選未套用，服務與工作樹沒有退役。

**先保留現場再重現。** GitHub可恢復tracked程式、設定、文件與整理收據；完整RGB、原Blender、模型權重、資料庫及私有驗證器仍是本機依賴。hash不是備份，不能由hash重建缺失資料。本機小型原件與一致狀態已另存於canonical的ignored目錄，沒有複製大型媒體或權重。

## 1. 接手順序與目前結論

1. 在第2節核對五個工作樹、HEAD及dirty狀態；不要切換canonical分支。
2. 在第3–4節核對本機依賴、私有manifest與來源hash；缺件時停止相應重現，不以其他資料補缺。
3. 先核對既有服務。只有服務確實未運行時，才用第5節啟動命令；Web使用動態port。
4. 按第6節重開保存案例／報告；Agent跨origin須正式恢復原憑證，不能靠指定同一SQLite自動恢復。
5. 第7節區分讀取舊證據、工程測試、實際模型品質及正式Phase1重建；輸出新收據，不覆寫凍結結果。
6. 延續原授權11修正時照第8節先後執行；05保持baseline。其他項目維持暫緩。
7. 工作樹清理仍未達前提，按第9節完成驗收、保存、發布與消費者核對後才處理。

| 工作 | 已完成及目前結果 | 證據／限定 |
| --- | --- | --- |
| 原工程底座 | 合成RGB→局部tracks→暫定跨鏡頭→3D事件、typed tools、持久調查／案例／報告、source presentation與版本化accuracy adapter | [模擬工程](../engineering/SIMULATION_ENGINEERING.md)、[局部pilot](../engineering/LOCAL_CAMERA_PILOT.md)、[本機產品](../engineering/LOCAL_PHASE2_PRODUCT.md)、[accuracy-v2](../research/LOCAL_CAMERA_ACCURACY_V2.md)。原Phase2整合仍以frozen5b51d2c契約為準；不由本機工程解凍正式scope |
| 01–03 | 範圍接續、accuracy-v2調查接入、認證評估／比較 | [人物調查與展示庫](../engineering/WORKBENCH_INVESTIGATION_GALLERY.md)；原Python3222／Node183／HTTP86請求939斷言 |
| 04／06 | 單一既有E0流程的新run、stop、來源綁定比較；固定任務manual／assisted排演評分 | [04／06契約](../engineering/WORKBENCH_RUN_STUDY.md)；原Python3325／Node213／HTTP147請求2881斷言。04未泛化；06為PREPARATION_REHEARSAL，非15操作員验收 |
| 05／09／10／11／12 A＋B＋C | 本機模型、真PG、合成診斷、區域出入／持續停留及研究框架已整合 | [ABC契約](../engineering/PHASE2_LOCAL_BATCH_ABC.md)；原Python3436、共享Node230／owned225；05／11品質未過 |
| Blender展示與人審 | Office雙鏡頭0–9.8秒K3、基線、曲線、影片；Classroom走廊50來源／0投影；Office20／Classroom15共35人審差異 | [demo指南](../engineering/DEMO_V1.md)及[checkpoint](../history/BLENDER_REVIEW_CHECKPOINT_20261013.md)。38物理checks仍UNKNOWN、硬排除0；Auditorium未開始人審 |
| demo主流程 | 五段核心5/5；含Saved Agent加映5/6，約83%操作就緒 | E1 TRACE19工具、69替代、10證據、1衝突，保存重開與HTML已通過；新origin未恢復舊Agent，90秒影片未製作 |
| 11現行工程 | runtime734／typed.evidence.v4，Python3736／Ruff／mypy235／HTTP68 PASS | HTTP23 SCRIPTED、0真模型。最新實際demo FAILED：1call75.660秒／0tools，AGENT_GOAL_FIELD_UNAVAILABLE |
| 11完整實測 | R2全48題：常規12/40，中文7/20、英文5/20；417 literal核對錯誤0、DETAIL完整性誤報4 | 安全邊界8/8，乾淨拒絕2/8，澄清完成0/8；新48回放未開始，品質門檻未過 |
| 11下一候選 | private runtime66f73…／patch a3b6…，220fixtures與獨立peer PASS | 未套用production；本次持久副本再驗220 PASS，0真模型，不能作品質分數 |
| 05最終決定 | 保持baseline；唯一候選dev strict gain未過，test(4,3,7,6)→(3,2,7,6) | fragmentation7>6、缺採樣11不變，candidate拒絕；既有test已曝光，不再依test調參 |
| 獨立Phase1 | formal043bed2及scoped release tag，Case1–3的18 Exit gates PASS、clean重現 | Case3 ADE改善0%未達原30%初始目標；school仍PARTIAL_APPROVED／NOT_CERTIFIED，Case4 DEFERRED；不升權Office或Phase2 |

Phase2功能工作量估約50%。11全部真實品質門檻成立後才約55%；05保持baseline，不能報60%。上述歷史測試總數各自綁定原程式／資料範圍，不相加，也不當成本次全套重跑。

## 2. 工作樹、分支、版本與發布範圍

| 角色 | 實體絕對位置 | 盤點HEAD／分支／用途 |
| --- | --- | --- |
| canonical原資產 | `/Users/polalabear/Developer/amidst` | c5956dc825f669e28e2694578be0fed97432a786／phase1/physical-policy-approval。LOCAL_ONLY/HOLD；有untracked docs/history舊文件紀錄，不覆寫、不推此分支 |
| 目前工程與demo | `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization` | 文件起點0a24f1ad1905bd81824e99d0f470566b88552ca5／codex/simulation-engineering；實際已測程式b1cf0c406140dd0a38a17456de961839dbf63f9a，runtime734132b434a698898a0ccc48d80e2d6532a439c3ba444ad313e0db9a2fca6c8a。交接文件發布SHA以Git核對 |
| main穩定R1 | `/Users/polalabear/.codex/worktrees/demo-v1-main/amidst` | 439c8669eae740ed5750eeb1f853c0ddf73ec507／main，clean。merge tree e668618329b789fd1fd12e28d379928cd1d5bd68與已測R1 7d053543完全相同 |
| Phase1正式 | `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-case23-formal` | 043bed2d6dac34698260bd37faefc31b9009d3ca／codex/phase1-case23-formal，clean；正式原產物仍在此樹 |
| Phase1 clean重現 | `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-case23-clean` | detached c4a8a0acfd3de2a8e266cf8463c9982610e5fe1d；untracked clean release是必要重現產物，不能當可刪垃圾 |

五個工作樹均已核對實體、.git及src存在，不只依registration判定。網頁以frontend/workbench為統一入口；frontend/product／歷史8020是待遷移能力與證據來源，不另擴張第二主前端。研究／管理身份切換是本機demo，非14正式帳號驗證或部署。main只包含R1及必要依賴，不含後續完整engineering、另一對話158d74c全部Blender顯示checkpoint、private66或正式043研究程式。

遠端為`https://github.com/Polalalabear/amidst.git`。Phase1正式ref／tag已發布043bed2；tag object0ac9c629bd0923ffe2134b7dae7f412373858096，peeled commit043bed2。不要把它回退到歷史883204a。原Phase2 frozen ref仍5b51d2c67917ff434f53e12a8af8af3d711d2a19。

```sh
export HANDOFF_REPO=/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization
export HANDOFF_CANONICAL=/Users/polalabear/Developer/amidst
export HANDOFF_LOCAL="$HANDOFF_CANONICAL/data/pilot/current_dependencies/handoff_20261014"
cd "$HANDOFF_REPO"
git status --short
git rev-parse HEAD
git branch --show-current
git worktree list --porcelain
git ls-remote origin refs/heads/codex/simulation-engineering refs/heads/main refs/heads/phase1/finalization-sprint refs/heads/phase2/integration-hardening
```

## 3. 依賴圖與檔案位置

下列engineering相對位置均以`HANDOFF_REPO`為根；canonical位置以`HANDOFF_CANONICAL`為根。完整逐檔SHA／size／inode／mtime存在本機`HANDOFF_LOCAL/audit/amidst-handoff-assets-20261014.json`；公開[資產摘要](../../data/engineering/work_handoff_20261014/asset_summary.json)只列群、路徑、inventoryhash與缺件。

| 消費者 | 必要來源及現存位置 | 核對結果／缺口 |
| --- | --- | --- |
| Blender三場景 | canonical `blender/school_v3.blend`及`data/pilot/school_v3_multisite_20261005/{office,classroom101,auditorium}/`；engineering `data/engineering/local_run/blender_camera_v1/`、scale config與physical policy archives | 原.blend468300506bytes／SHA cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e，原size/mtime不變；三場景各100 RGB逐張size/hash匹配 |
| 曲線與影片 | engineering `data/engineering/local_run/blender_motion_v1/`、`blender_association_v1/`、`blender_physical_v2/`，各scene的manifest／PNG／MP4 | 分別9／9／9檔，仍綁原camera safe-input；已有素材不build、不render、凍結輸出不覆寫 |
| 人審／確認後重跑 | engineering `data/engineering/local_run/blender_physical_review_reruns/`；canonical `data/pilot/retained_checkpoints/phase1-finalization_20261013/` | 重跑43檔、retained73檔；35deltas連續hash chain PASS，formal_approval／authority_changed均false |
| E0 | engineering `data/engineering/local_run/simulation_v2/` | 123檔3667364bytes；2cams、102 RGB；04仍只支援此既有流程 |
| E1 | engineering `data/engineering/local_run/local_camera_v1/`；test/development各`checkpoints/final/`，原RGB在祖先的`test/rgb/`等registry指定位置 | 569檔37170577bytes；test/dev各4cams244 RGB全部逐張匹配；media_root_ancestor_depth=2不能忘掉祖先RGB |
| accuracy-v2／Agent | engineering `data/engineering/local_run/accuracy_v2/test/final/`，其absolute source_locator指向E1 test/checkpoints/final | 242檔120372762bytes；development/final從未materialize，不能當已存在或用別組補缺 |
| ABC 05／09／10 | engineering `data/engineering/local_run/phase2_abc/research/{development,test}/certified/` | 244檔158139320bytes；正確namespace是certified，test/final不存在不等於結果遺失 |
| 05受限候選 | engineering `data/engineering/local_run/phase2_repair_0511/research/test/final/` | 38檔47215818bytes；baseline仍啟用，舊development與reproduction已退役，負結果／freeze保留 |
| Formal／clean release | formal `data/finalization/reviewed_run_case123_formal_v2_20261014/`；clean `data/finalization/reviewed_run_case123_clean_v2_20261014/` | 群2891／777檔；release manifest PRIMARY2624＋CLEAN741共3365bindings全部fresh hash/size PASS、missing0 |
| 本機7B | engineering `data/engineering/local_run/phase2_abc/ollama_models/` | manifest845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e，5必要blobs共4683087332bytes；大blob本次只fresh exists/size/stat＋既有完整SHA，未宣稱重新hash4.68GB；3B仍存在未退役 |
| PostgreSQL | engineering `data/engineering/local_run/phase2_abc/postgres/{cluster,settings.json}` | PG18.6；Unix socket `/private/tmp/amidst-pg-abc`、port55432、DBamidst_abc／schema&user amidst_local；TCP auth reject |
| Provider／transport | engineering `data/engineering/local_run/phase2_abc/agent_provider.json`、`phase2_repair_0511/agent_transport_profile.json`；benchmark另`agent_provider_180.json` | base provider SHA9d1ef0f5…；effective180s由transport SHA9ab32a91…指定，無retry；same7B context8192／temperature0／seed0 |

四條source_locator的**canonical JSON digest**與十份physical source pins全部PASS；manifest的canonical digest和格式化檔案的byte SHA是不同量，不能互換。原.blend、RGB、正式review inputs與GT/recipe隔離規則維持；hash核對不是重新inference、評估或新human approval。

目前環境：Python3.12.12、uv0.9.26、PostgreSQL18.6、Ollama0.35.0、Node26.0.0、npm11.12.1、Three.js0.186.1（工作台package-lock）。formal export manifests記錄Blender5.2.1 LTS／build9e2066aef7ef。工程`.venv`目前editable locator已核對指向工程樹；啟動仍明確指定PYTHONPATH。新機器先提供相同locked dependencies與node_modules，offline/no-sync不會下載缺件。

## 4. 已持久保存的私有重現材料與核對方式

`HANDOFF_LOCAL`位於canonical ignored `data/pilot/`，目錄0700、檔案0600。**134份必要檔案、9971897bytes（約9.51MiB）**；逐檔manifest SHA **1916120704c7860f31204465f9bac8bc1dd881c49aa0d9d95f3a8645f903d6f5**。不含模型／RGB／.blend大副本，沒有搬走現場依賴。這些私有bytes未上GitHub。

| 私有相對位置 | 內容與實測 |
| --- | --- |
| `private_handoff_manifest.json` | 所有保留檔案的relative path／byte SHA／size／mode；不將其內容當source data |
| `private_candidate/` | 完整小型src／tests／patch／220logs／context proof及superseded214、locale／collection／readverb negative；不包含可重建cache |
| `private_harnesses/` | 原HTTP68、PG同源restore、48preflight/template、原R2independent scorer、actual答案來源verifier、工程JUnit/logs、sourcefreezes、cleanup plans與guards |
| `audit/` | 原runtime與assets逐檔inventory、精確argv／allowlisted env、較完整private重現草稿 |
| `state/{workbench,local-agent,accuracy-v2,operator-study}.sqlite3` | 四個online backups，合計540672bytes；含WAL，integrity check全PASS；Agent恢復憑證保留在完整私有ledger，沒有額外公開抽取 |
| `state/amidst_local.dump` | 1835666bytes，SHA ce291c6b2d42273407836dc074365d5619c9fcd4795496b05e8f13ab43c27e2d；以同一REPEATABLE_READ READ_ONLY exported snapshot取得dump與14表fingerprints |
| `state/context-proof-qa-agents.sqlite3` | 額外380928bytes的SCRIPTED HTTP QA ledger，非user live ledger；source／backup logical hash相等、integrity PASS，byte SHA51c07031babf66f1d8a136bb3fadf5d2c0eab8e6a81c0a99f3f5674178771ccc |
| `config/` | PGsettings、base provider、live transport profile、benchmark provider180原件；不得把內容或recovery_token推到GitHub |
| `demo/trace-report.html` | 本輪2166byte HTML，SHA7233c0856582d5f44e2be609396d8d6cdcb3bb76edeb9716ddcd93d88f6ae00f；UNRESOLVED_PROVISIONAL、DETAIL/MEDIA預算缺口保留 |
| `validation/` | 持久副本220／0failure/error/skip PASS；read-only context22437/24000重現；首次sandbox socket failure保留，不當模型FAIL |

PostgreSQL新快照已在唯一新amidst_restore_handoff_*測試DB還原，14表fingerprints全相等；測試DB及臨時dump副本已退役。原DB／schema沒有restore或migration。當前快照4runs／1040records／129revisions／85jobs；人審35deltas、Agent4COMPLETED＋1FAILED。這是本次備份可恢復性證據，**不是重跑歷史5023斷言query suite**。四SQLite與PG各自一致，沒有宣稱跨資料庫distributed atomic snapshot。

```sh
export HANDOFF_LOCAL=/Users/polalabear/Developer/amidst/data/pilot/current_dependencies/handoff_20261014
python3 - <<'PY'
import hashlib, json, os
from pathlib import Path
root=Path(os.environ['HANDOFF_LOCAL'])
manifest=root/'private_handoff_manifest.json'
assert hashlib.sha256(manifest.read_bytes()).hexdigest()=='1916120704c7860f31204465f9bac8bc1dd881c49aa0d9d95f3a8645f903d6f5'
data=json.loads(manifest.read_text())
for item in data['files']:
    rel=Path(item['relative_path'])
    assert not rel.is_absolute() and '..' not in rel.parts
    p=root/rel
    assert p.is_file() and not p.is_symlink()
    assert p.stat().st_size==item['bytes']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'], rel
print('private handoff134 files verified; zero model calls')
PY
```

上述原manifest只讀，不把新的outputs塞回去改hash。新增驗證另建帶日期／run的目錄與收據。兩個one-shot `capture_state.py`、`verify_snapshot_restore.py`保留原執行方法；舊snapshot／收據已存在時拒絕覆寫，不能在原目錄直接重跑。新採樣需新目的地；live transport另外存入config並列於完整manifest。

## 5. 服務核對與啟動（同一台機器）

盤點時workbench Python70138／uv70129、Ollama70142、PG68475；PID會改，不拿歷史PID作stop或刪除依据。當次web URL在runtime audit中，未寫死新埠號。既有provider11437／PG55432是原凍結依賴，這次不改其設定。

先核對健康：workbench以本次listener形成`DEMO_URL`；Ollama只tags不completion；PG只pg_isready，不呼叫會migration的lifecycle status。

```sh
curl --fail "${DEMO_URL}api/bootstrap"
curl --fail http://127.0.0.1:11437/api/tags
/opt/homebrew/opt/postgresql@18/bin/pg_isready -h /private/tmp/amidst-pg-abc -p 55432 -d amidst_abc -U amidst_local
```

只有Ollama未運行且owner／原權重目錄確認後才啟動：

```sh
export OLLAMA_HOST=127.0.0.1:11437
export OLLAMA_MODELS="$HANDOFF_REPO/data/engineering/local_run/phase2_abc/ollama_models"
export OLLAMA_NO_CLOUD=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1
/opt/homebrew/bin/ollama serve
```

只有PG未運行且原cluster／settings／backups確認後，才在工程樹執行`PYTHONPATH="$HANDOFF_REPO/src" uv run --offline --no-sync python scripts/phase2_local_postgres.py start`；它可能建立cluster／database／settings並migration，不是唯讀核對。不要換成globalbrew service或新空DB冒充原保存案例。

Web啟動使用原SQLite family與資產checkout：

```sh
cd "$HANDOFF_REPO"
export PYTHONPATH="$HANDOFF_REPO/src"
export UV_CACHE_DIR=/private/tmp/amidst-abc-uv-cache
export MPLCONFIGDIR=/private/tmp/amidst-abc-mpl
export DEMO_STATE=/private/tmp/amidst-physical-review-workbench-20261013-qa.sqlite3
export DEMO_CANONICAL_ROOT="$HANDOFF_CANONICAL"
uv run --offline --no-sync python -m amidst.workbench \
  --port "${DEMO_PORT:-0}" --repo "$HANDOFF_REPO" \
  --canonical-root "$DEMO_CANONICAL_ROOT" --state "$DEMO_STATE"
```

另一個終端先核對本次Python PID／argv，再發現OS分配的port；CLI印0是請求值，不是實際網址：

```sh
: "${DEMO_PID:?填本次已核對的workbench Python PID}"
ps -ww -p "$DEMO_PID" -o pid,ppid,uid,lstart,args
export DEMO_PORT="$(lsof -a -p "$DEMO_PID" -iTCP -sTCP:LISTEN -nP -Fn | sed -n 's/^n127\.0\.0\.1://p')"
: "${DEMO_PORT:?該process沒有listener，停止不要猜port}"
export DEMO_URL="http://127.0.0.1:${DEMO_PORT}/"
curl --fail "${DEMO_URL}api/bootstrap"
```

**四SQLite必須成同一命名family。** runtime由base stem推導`-local-agent`／`-accuracy-v2`／`-operator-study`；不能直接把備份`state/workbench.sqlite3`當DEMO_STATE，否則siblings命名不符，可能開成空新狀態。原base缺失时，先停止僅依賴該state的服務，核對backuphash，再將四備份恢復到原四精確位置；原文件存在不能覆寫。若改成新private state directory，四者要用同一base stem，且另記session／ref及Agent正式恢復；這不是無痕搬家。PG快照還原只能進不存在的新amidst_restore_* DB，原DB不overwrite；bootstrap.restore還要求dump位於engineering專用postgres ROOT，需新私有副本及原件hash核對。若把新restore DB作runtime來源，須明確versioned設定rebind，不能悄悄替換原settings。

## 6. demo與保存結果重開

完整九分鐘操作以[DEMO_V1](../engineering/DEMO_V1.md)為準。Office兩鏡頭0–9.8秒K3、3D／2D分時牆／sourceclock、三候選／排序外基線／XYZ與速度曲線可展示；Classroom走廊有影格無投影，UNKNOWN／MISSING保留。

接著**明確切到E1**：研究 → 局部多鏡頭研究場景 → 人物調查 → 照片與觀測 → DOOR8–16秒 → 局部片段第一seed → TRACE → 建立保存 → 一步 → 到停止 → 重開案例 → 報告 → HTML。本次保存結果為19工具／69替代／10證據／1衝突；身分UNRESOLVED_PROVISIONAL。workflow complete不是全部DETAIL或MEDIA完整。讀回原HTML應得上述exact SHA；重新建立新case會有新refs／timestamps，不能要求新HTML字節必然相同，也不能覆寫原件。

Agent是加映：accuracy-v2 → 調查與品質 → DOOR8–16秒。新weborigin沒有8016的localStorage entries，新server session也不自動繼承owner。原agent_ref及recovery_token保留在私有ledger；只有matching localStorage時UI顯示恢復按鈕。目前沒有跨origin手動token輸入UI。

既有正式API為`POST /api/suite_agent_recover`，payload需當前context的session_ref、scene_id、observation_mode，以及原agent_ref／recovery_token；會轉移owner並更新generation／revision，必須依既有server guard，不另造凭證。當前context由既有suite_context契約取得；來源／模式仍須匹配。這次只保存材料，**未實際恢復新origin的Agent**，因此完整六段仍5/6。不要把token貼到公開文件、URL、terminal stdout或Git。舊v2/v3僅literal證據可讀，當前需求完成度NOT_CHECKED、禁止續跑，不升格成v4品質PASS。

## 7. 結果核對、工程測試與研究重建

### 7.1 只讀核對現在的程式／controls

```sh
cd "$HANDOFF_REPO"
export PYTHONPATH="$HANDOFF_REPO/src"
uv run --offline --no-sync python - <<'PY'
import hashlib,json
from pathlib import Path
base=Path('data/engineering/phase2_repair_0511_20261013')
f=json.loads((base/'engineering_sourcefreeze_r3_context.json').read_text())
r=json.loads((base/'agent_runtime_release_r3_context.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
assert len(f['backend_inputs'])==566
assert digest(f['backend_inputs'])==f['backend_tree_sha256']
for name,value in f['backend_inputs'].items():assert sha(Path(name))==value,name
for name,value in r['runtime_files'].items():assert sha(Path(name))==value,name
assert digest(r['runtime_files'])==r['runtime_manifest_sha256']==f['runtime_manifest_sha256']
for name,value in f['frozen_protocol_and_validation_inputs'].items():assert sha(base/name)==value,name
print('566 backend, runtime8 and controls verified; zero model calls')
PY
```

本次此核對PASS。Private候選66与production734各自有manifest，不能把privatePASS当已套用release。main的原3567／owned232收據也不可稱本次freshmain重跑。

### 7.2 持久副本的有界工程重現

本次已重新執行下面220 fixtures，結果220／0fail/error/skip。首次sandbox禁止fake HTTP fixture bind造成1FAIL另存；同源受審重跑PASS。沒有呼叫Ollama模型或改production。

```sh
export PRIVATE_CANDIDATE="$HANDOFF_LOCAL/private_candidate"
export NEW_VALIDATION_DIR=/private/tmp/amidst-handoff-next-validation
mkdir "$NEW_VALIDATION_DIR"
cd "$HANDOFF_REPO"
PYTHONPATH="$PRIVATE_CANDIDATE/src" uv run --offline --no-sync pytest \
  "$PRIVATE_CANDIDATE/tests/local_agent" -q \
  -o cache_dir="$NEW_VALIDATION_DIR/cache" \
  --junitxml="$NEW_VALIDATION_DIR/private220.xml"
PYTHONPATH="$PRIVATE_CANDIDATE/src" uv run --offline --no-sync python \
  "$HANDOFF_LOCAL/context_proof_preserved.py" "$NEW_VALIDATION_DIR/context-proof.json"
```

私有實體檔案以private_handoff_manifest逐檔byte SHA驗證；candidate runtime66的local_agent/__init__.py使用排除私有bootstrap後的normalized production pin，不能混成同一種manifest，也不能把bootstrap一起套用production。Privatebootstrap的`__path__`仍延伸到原工程src；搬到另一台時需新受審locator copy，保留原件与diff。context proof原件仍在private_candidate；新副本只改QA ledger locator，源／backup logicalhash相同，本次22437／24000、case／ledger不變。新fixture結果與原220收據不相加。

### 7.3 全套工程與HTTP／PG驗證

下面為可選重跑recipe，**本次文書交接未執行3736全套／共享Node**；約622秒是原耗時，不保證新機器時間。完整測試會寫隔離DB／fixture outputs，不是純唯讀。使用新JUnit／logs，不覆寫歷史收據。

```sh
: "${NEW_VALIDATION_DIR:?先設定全新驗證輸出目錄，勿覆寫原收據}"
: "${AMIDST_PHYSICAL_SOURCE_SCENE:?設定原school_v3.blend絕對路徑}"
cd "$HANDOFF_REPO"
export PYTHONPATH="$HANDOFF_REPO/src"
uv run --offline --no-sync pytest --require-physical-evidence tests -q \
  --junitxml="$NEW_VALIDATION_DIR/full-python.xml"
uv run --offline --no-sync ruff check src tests scripts
uv run --offline --no-sync mypy --strict src
node --test frontend/workbench/*.test.mjs frontend/product/timeline.test.mjs
git diff --check
```

共享frontend238与owned projection233是不同population；不能把当前sharedrun叫owned233或把兩者相加。Owned46檔projection依`frontend_validation_r3.json`另構建overlay，舊hash与Node依賴需匹配。

HTTP68原helper `private_harnesses/amidst-repair11-r3-context-http-guards.py`目前SHA cbf13ea0…（只修OUT）；實際通過時執行7885c709…，misnamed原件與rawPASS／locator correction亦保留。PG同源5023 helper `private_harnesses/amidst-storage-integration-restore.py` SHA d903894e…。**兩者直接重跑會覆寫tracked凍結收據，禁止直接執行原檔。** 在新privatecopy只改新OUT／RECEIPT與必需locators，逐項記diff／新SHA、保留全部原checks，再freeze後執行；原JSON／FAIL不覆蓋。本次PG14表restore核對不代替這兩套HTTP／boundedquery断言。

actual答案來源verifier是`private_harnesses/amidst-r3-demo-source-verifier.py`與readonly-source helper。它使用accuracy-v2/test/final→E1來源，不是benchmark operator_v2；原imports包含tmp locators，需恢复原位置或受審新copy。沒有成功v4case時返回WAITING_COMPLETED_ACTUALCASE；`--legacy-v3-source-only`只核對舊51literalfields，不補當前需求完成度。0模型source verification不等同自然語言品質。

### 7.4 獨立正式Phase1重建

在**formal043工作樹**讀取其`docs/PHASE1_CASE23_REPRODUCTION.md`與`docs/PHASE1_CASE23_FINAL_REPORT.md`，不是在engineering用同名歷史腳本。exact public版本見[正式重建指南](https://github.com/Polalalabear/amidst/blob/043bed2d6dac34698260bd37faefc31b9009d3ca/docs/PHASE1_CASE23_REPRODUCTION.md)。

它規定原Blender／review／physical evidence hydration、master與source config、兩native exports、兩inferences、joint pre-GT freeze、independent evaluations、18gates與clean comparisons。原code checkpoint c4a8a0a、formalrelease043與clean實際c4a8a0a分開記。要重跑native workflow，使用新的輸出目錄、同一原輸入与config，先鎖producer，再reference evaluation；不覆寫現存release、不把GT/recipe輸入producer。完整readonly核對可先讀3365bindings的size/hash及18gates原收據。Hash匹配與reader可讀不等於本次重跑native workflow。

本次只核對原產物，沒有新render或正式benchmark。Case3 ADE0%未達30%，不得把workflow Exit PASS當performance目標達標；整校scope不由此增加。

## 8. 11原授權續作順序與品質門檻

私有candidate patch a3b6ba8d3f5276300fbec0ebf9c0eb4fa8e2bb3212ca9a3f81f31e7449a6b69b；runtime66f73a3b09754333e155c618cb35077e5aa73668050f241aa1d75cf025946c4d；private validation4f8257cfd204f1845a99b8ab40376527a6efdcdda2b28678be670f878afa6fa5；peer6f26768d61a44065657feab7a04ae0dcc185a65778e5b414b19e2dd9e332a01c。只修schema existing field enum、通用goal／citation示例与通用read verbs，没有擴fact allowlist、代選工具或答案。

接續原11授权：先核對manifest與apply-check→套用最小ownedpatch→新runtime8／backend566／6controls freeze→scoped與完整工程／HTTP→成功實際7B demo＋同來源逐欄核對→一次完整原PUBLIC R2 48題freshledger→獨立task／literal／citation／completion／boundary／language／clarification與hash核對。不能以220 fixture或HTTP0model替代實測。

常規≥36/40、中英各≥18/20；接受literal／citation完全對應公開DTO、完整性誤報0；安全邊界8/8並另列乾淨拒絕原因／語言。保留未知usage、timeout、延遲、替代與分頁，不能少報改善分數。Model7B digest845dbda…、context8192、temp0／seed0、transport180秒無retry維持。Live budgets12model／8tool／24k tokens／300秒；benchmark8model／6tool／32k tokens／900秒，wire24000chars／result6000不放寬。

`private_harnesses/amidst-r3-benchmark-command-template.sh`／preflight133d3334…已保留，但只在上述實際demo／工程門檻成立後排程；preflight不是新品質結果。CLI的關鍵參數為：

```sh
uv run --offline --no-sync python -m amidst.local_agent.benchmark run \
  --product data/product/local_run/operator_v2 \
  --provider-config data/engineering/local_run/phase2_repair_0511/agent_provider_180.json \
  --suite data/engineering/phase2_repair_0511_20261013/agent_benchmark_frozen48_r2.json \
  --protocol data/engineering/phase2_repair_0511_20261013/acceptance.json \
  --ledger data/engineering/local_run/phase2_repair_0511/agent_benchmark48_r3.sqlite3 \
  --output data/engineering/phase2_repair_0511_20261013/agent_benchmark48_r3.json
```

目前**未開始新48**，不要直接執行此段。Ledger／output及-wal/-shm/-journal須原先不存在；全部48attempts保留，不挑題重跑。原pack已曝光，範圍必標`EXPOSED_LOCAL_PUBLIC_REGRESSION_NOT_INDEPENDENT_HOLDOUT`，不是新sealed集；不改oracle／問題／cap迎合模型。原R2independent scorer889ff33e…硬編舊locators，新run需受審副本與新收據，不覆寫R2。Raw protocol file SHA與parsedcanonical digest分別記錄，不能互換。

## 9. 暫緩範圍、main與清理前提

暫緩且需使用者再次確認：07真實錄影、08真實detect／track、09真實／訓練ReID、10區域出入与持續停留以外其他單人及全部多人事件、13串流、14帳號／部署、15實際操作員驗收、新合成封存測試集。04限定E0既有流程、06限定準備，05保持baseline，不啟第二候選或再調test。

main只已合併驗證R1與必要deps；後續11品質達標後按原merge授權準備最小code／docs／小release及exactmerge-tree驗證。不要merge整個engineering、private66、foreign158d74c、formal043或大型raw／failure pack。舊promotion審查拒絕未執行，不用文件PASS冒充品質解除。

只刪使用者指定finalization工作樹的前提：共享11實際驗收结束→精確code／public receipts發布與lsremote核對→必要7B唯一權重、E0/E1原輸入、人審／Agent／accuracy／study／PG狀態完整保留→其他dirty／formal／clean consumers確認→僅退役該tree的owned服務→新鮮quiescence核對→受限git worktree remove。原[`PHASE1_ARTIFACT_CLEANUP`](PHASE1_ARTIFACT_CLEANUP.md)及私人minimalretention plan是計畫／歷史，不能直接執行舊PID或過時release names。

本輪只新增必要小型交接原件与一致狀態；模型／媒體仍在原工程樹，`.venv`與formal/clean產物仍保留，完整dependency move與工作樹刪除尚未執行。凍結絕對locator在刪樹後會offline，重新使用需顯式版本化rebind；目前main freshclone不是完整portable demo包。不要因handoff已寫好就刪現場。

## English

This handoff separates code, immutable source assets, mutable state and engineering/model/formal evidence. All five worktrees are present. The local ignored handoff preserves134 small files/state snapshots (about9.51MiB), including the unapplied candidate, private validators, original failures, live SQLite backups, credentials-bearing ledgers/configs, and a same-snapshot PostgreSQL dump. No large models, RGB or Blender assets were copied or moved.

Fresh checks passed source bindings, four SQLite integrity checks, fourteen restored PostgreSQL table fingerprints,220 relocated private fixtures, and the22437/24000 context proof. The initial sandbox socket failure is retained. These checks made no real model calls and do not constitute a new full-suite/48-task/formal workflow run. Production remains734,05 baseline,11 quality unmet, Phase2 approximately50%. The private manifest verification, dynamic-port startup, recovery caveats, commands, deferred scope and cleanup prerequisites above are authoritative for this snapshot; publication SHA is verified separately in Git.
