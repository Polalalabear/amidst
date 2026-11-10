> 已封存（2026-10-27，D91），見 [封存索引](../archive/ARCHIVE_20261027.md)。

# Phase 1 artifact cleanup / Artifact 整理

## 2026-10-14 — 僅保留文件紀錄的實體清理

使用者已明確授權刪除不再使用的工作樹、封存與產物，只留文件紀錄。
實際項目、空間與驗證以[本次清理紀錄](../history/LOCAL_STORAGE_CLEANUP_20261014.md)為準；
canonical `docs/history/storage_cleanup_20261014/` 保存舊 manifest、文字文件及 orphan hash inventory，
不另建立 raw backup。下方 10/13、10/08 的 KEEP／ARCHIVE／未授權描述保留為歷史 snapshot。
現行 finalization、main demo、原始 Blender、模型／PG／人審與目前 final/certified 輸入仍保留。
舊 review durable locator 退役；hydration 改用仍保留、同 manifest hash 的 live `human_review/`。
三個 9 月 orphan 的舊程式不在目前 Git，清理後僅有文件與 hash 紀錄，不能宣稱可完整復原。

English: The new user authorization retires unused physical archives and outputs while keeping
document records. The linked receipt supersedes earlier inventory-only dispositions. Active
runtime/source inputs remain; retired output bytes and old orphan code are not retained.

<a id="cleanup-review-20261013"></a>

## 2026-10-13 — 發布後的worktree／資產清理盤點 / Post-publication cleanup review

本節保存16:39本機盤點與exact93eb611的隔離驗證，不把下方10/08歷史inventory改寫。
指定工程push已完成；`c5956dc`仍是LOCAL ONLY/HOLD，main與frozen Phase2未變。
本輪只補文件，沒有push、main merge、移動、archive或刪除任何專案項目。
候選分類不是執行授權；後續清理前須重新核對程序、dirty狀態、hash與備份。

English: This section records the 16:39 local inventory and exact 93eb611 scoped isolation;
the older 10/08 evidence remains historical. The authorized push is complete, while
c5956dc stays LOCAL ONLY/HOLD and main/frozen refs remain intact. This task only edits
documentation. Eligibility is not deletion permission; recheck processes, dirty state,
hashes and backups before any later action.

### 工作樹與資料 / Checkouts and artifacts

有效worktree為canonical主目錄（c5956dc）、`phase1-finalization`工程目錄，以及
`phase1-preview-workspace`（04c699d）。54d9／c93d／db5d的Git管理目標已不存在，
不能聲稱有可核對的HEAD、clean狀態或完整Git備份。10/08另存3份worktree archive：
phase2-hardening、phase2-foundation、projection-model-upgrade；phase1-recovery是
額外資料復原包，不是第四個worktree。Canonical原始來源與所有私人資料留本機。

English: Three registered checkouts remain; 54d9/c93d/db5d are orphan directories with
unverifiable HEAD/index/status. The 10/08 package has three archived worktrees plus one
separate recovery package. Keep canonical sources and private data local.

| 項目 / Item | 盤點大小 / Size | 條件與分類 / Disposition |
| --- | ---: | --- |
| 三個有效checkout的pytest／Ruff／mypy／Python bytecode快取 | 約86.5MiB | REGENERABLE；停用舊快取的回歸通過，待其他檢查結束後才可清。After active validators finish only. |
| 本輪 `/private/tmp/amidst-cleanup-audit-20261013` 測試副本 | 約654MiB | REGENERABLE；測試已結束，收據另存canonical ignored package；移除不得跟隨連結刪來源或依賴。Do not follow links into dependencies/assets. |
| Preview checkout（含其環境與快取） | 約905MiB | CONDITIONAL；04c699d已合入工程、188個非快取資料有相同副本且獨立重建通過，但8768仍使用此checkout。Retire service and recheck before removal. |
| `blender/working/checkpoints/phase1-semantic-scene-20261005/school_v3.blend` | 468300506bytes | BACKUP；與canonical v3相同hash。現行測試不需它，但刪除會失去獨立source復原副本。Removing loses recovery redundancy. |
| canonical `data/pilot/worktree_archives/20261008-cleanup/phase1-recovery/` 第二份資料備份 | 約51.1MiB | BACKUP；315檔與live復原包及manifest hash相同。只在接受少一份復原保障並保留原包／manifest後才可考慮。Keep primary recovery package. |
| 54d9／c93d／db5d舊checkout | 約14.6／13.9／85.2MiB | KEEP；在可達Git、archive manifest及現行同路徑副本中未找到完整備份。先本機hash manifest封存，再挑可公開code/docs另行保存。No whole-directory upload/deletion. |
| Projection-model-upgrade archive | 約500MiB | KEEP；11288個歷史輸出、原worktree已不存在。Historical evidence, not cache. |
| Phase2 foundation／hardening archive的來源連結 | 無有意義節省 | KEEP歷史manifest；包含3個指向缺失school_v2_research的連結，不恢復／刪除來源。Preserve provenance records. |
| `.venv`、node_modules、全域uv cache、PG cluster、模型權重、人工DB及原始媒體 | 未列為可刪 | KEEP／LOCAL ONLY；依賴、offline重建、私人或正在使用的資料未通過刪除驗證。Outside verified cleanup scope. |
| commit本體、Git blobs／trees | 不以標籤刪除估算空間 | KEEP；沒有不可達commit；47blob／57tree未證明可清，不做強制prune或歷史改寫。No object deletion approved. |

大小屬當時盤點，各列可能重疊（preview大小包含其快取），不相加作回收保證。
4個實體Blender合計1872045411bytes／3種內容：v3為目前來源、v2仍供舊工具及測試、
wall_marked為歷史pilot重現依賴、checkpoint v3為相同內容的復原副本。
另有5個有效Blender連結與3個失效研究副本連結；失效不是來源可刪的證據。

English: Sizes are historical estimates with overlaps, not guaranteed reclaimable totals.
Four regular blends hold three distinct contents: current v3, legacy-tool/test v2,
the historical wall-marked pilot and the byte-identical v3 recovery copy. Five valid links
and three broken research-copy links do not authorize source deletion.

9個可整理的本機分支名稱為 `codex/dataset-infrastructure`、
`codex/deterministic-downstream-scenarios`、`codex/docs-agent-handoff`、
`phase1/finalization-sprint`、`phase1/geometry-authority`、
`phase1/physical-authority-resolution`、`phase1/physical-policy-lightweight`、
`phase1/pilot-dataset-and-wall-inference`、`phase1/pilot-downstream-reconstruction`。
它們均已發布且在工程祖先中；隔離移除名稱前後158個commit均可達。
只整理local label，不刪commit，不回收blob；遠端、工程及指定保留refs須保留。
preview label需等checkout退役；其他4個projection／robustness旁支只有遠端備份，
不與上述9個已包含支線混稱；frozen Phase2、main、工程及c5956dc保持保留。

English: The nine listed local labels were tested in isolation with all 158 commits
still reachable. Removing labels does not remove commits/blobs. Keep remote refs,
the active engineering line, main, frozen Phase2 and c5956dc; preview retirement and
the four remote-backed research side branches need their own conditions.

驗證與完整本機證據hash見[工作紀錄](../history/WORK_LOG.md#publication-cleanup-20261013)。
1061Python／213Node／12preview與1139Git blobs／114runtime inputs只認證93eb611的
所列工程範圍；依賴環境有保留，沒有測試刪除歷史／私人／復原資料的可接受性。
Evidence scope is exact 93eb611 only; runtime absence does not prove historical or
private artifacts disposable. All original sources, backups and archives remain present.

<a id="main-integration-20261013"></a>

### main整合候選 / Main integration candidates

2026-10-13以GitHub main `83ca3f8f1021913079759339ffa248039d3cc6ef` 為比較基準；
本機main為 `2a988dffbe438f47ff7de37055d7e7c67f8ac26f`，其多出的2個docs commits
已在其他GitHub分支保存。已發布工程為93eb611（ahead123）；本機工程為001a0fc
（ahead124）。以下18個feature refs全部也是兩個main的descendant，隔離Git
merge-tree檢查均為fast-forward／無衝突；只寫暫存object store，沒有真的merge或改live refs。
這不等於每條支線已通過現在的整合、產品品質或正式研究驗收。

English: All 18 feature refs can fast-forward from the pinned remote/local main in
isolated graph checks. Published engineering is 93eb611, whereas its current local HEAD
is 001a0fc. Graph compatibility alone is not current integration or quality acceptance;
no live merge/ref/object-store changes were performed by the simulation.

| Branch | 本機SHA／ahead遠端main | 整合判定 / Disposition |
| --- | --- | --- |
| `codex/simulation-engineering` | 001a0fc／124 | 優先評審已發布 `93eb611`；目前HEAD另含A＋B＋C，不能自動等同已發布候選。Review published snapshot separately. |
| `codex/dataset-infrastructure` | 91f4ea6／44 | 已包含於 `93eb611`；隨工程整合，不必逐支合。 |
| `codex/deterministic-downstream-scenarios` | c0717ae／10 | 已包含於 `93eb611`。 |
| `codex/docs-agent-handoff` | 2c586b1／82 | 已包含於 `93eb611`；整支含研究祖先，不是純docs差異。Not a docs-only whole branch. |
| `codex/phase1-preview-workspace` | 04c699d／80 | 已包含於 `93eb611`；服務退役是另一項工作。 |
| `phase1/finalization-sprint` | 883204a／79 | 已包含於 `93eb611`；formal full Exit仍BLOCKED。 |
| `phase1/geometry-authority` | bb66bb7／47 | 已包含於 `93eb611`；局部來源核准範圍不擴大。 |
| `phase1/physical-authority-resolution` | 0bab8ac／51 | 已包含於 `93eb611`。 |
| `phase1/physical-policy-lightweight` | f264db1／52 | 已包含於 `93eb611`；公開輕量路線，不包含c5956dc祖先。 |
| `phase1/pilot-dataset-and-wall-inference` | fdf9e7e／45 | 已包含於 `93eb611`；保留pilot限制。 |
| `phase1/pilot-downstream-reconstruction` | 51f1ec7／46 | 已包含於 `93eb611`。 |
| `phase1/pilot-robustness-validation` | ce2974b／47 | RESEARCH_HOLD；已被8f4055研究線包含。 |
| `phase1/projection-sensitivity` | b90e81a／49 | RESEARCH_HOLD；已被8f4055研究線包含。 |
| `phase1/projection-conditioning-mitigation` | 5f020b0／50 | RESEARCH_HOLD；已被8f4055研究線包含。 |
| `phase1/projection-model-upgrade` | 8f4055f／51 | RESEARCH_HOLD；1166歷史測試不是現行整合驗證，MODEL_UPGRADE_PROMISING不是formal PASS。 |
| `phase2/integration-foundation` | e4e5afc／29 | KEEP_FROZEN_DONOR；已被hardening包含，不直接整支合現行工程。 |
| `phase2/integration-hardening` | 5b51d2c／31 | KEEP_FROZEN_DONOR；723歷史測試、MOCK-only、frozen tag保持。 |
| `phase1/physical-policy-approval` | c5956dc／52 | EXCLUDE_LOCAL_ONLY／HOLD；含約50.90MB新增raw blobs，依使用者指示不進GitHub/main。 |
| `main` | 2a988df／2 | TARGET；保持不變，不作候選支線。 |

建議先評審 **已發布93eb611** 的工程範圍：其3325Python／213Node／mypy204歷史實作
收據的12個code hashes與commit完全一致，另有本對話1061項隔離回歸。它已包含
上表10條其他功能支線，無需逐條合併。執行時必須選明確SHA／擬合併範圍；本機
分支名稱現在指向001a0fc。上述判定是可開始整合評審，不是已授權merge。

001a0fc的550份最終backend與41份owned frontend hashes符合commit；其3436完整
Python＋格式後7項、225owned Node、mypy224與實際模型／PG收據各自保留範圍。
230shared Node包含其他對話方向修改，不作該commit單獨認證。05的switches4→5、
fragmentation7→8及11的6/8題組／未認證語意品質仍未達門檻；建議先處理品質缺口，
或明確接受帶限制的prototype範圍，再決定是否納入main。這是工程建議，不是杜撰
「formal full Exit以前所有工程都禁止進main」的規則。未提交的世界方向／幾何不在候選內。

四條projection旁支相對工程仍有獨有研究commit；若與工程一起整合，實際衝突為
`data/README.md`、舊 `docs/CODEX_HANDOFF.md`、`docs/WORK_LOG.md`，須先解衝突並重測。
Frozen hardening與工程亦衝突於README、舊handoff／worklog及 `tests/conftest.py`；
foundation另外涉及local_repository／replay／wiring。先前選擇性匯入不等於整支已合併。
原Phase1正式Cases2／3／full Exit、人工來源權限及Phase2 freeze均不由Git無衝突解除。

English: Prefer integration review of the exact published 93eb611 engineering scope;
it already carries the ten included feature refs. Its hash-bound historical 3325/213
receipt and this conversation's scoped 1061 regression do not certify local 001a0fc.
ABC has matching final 550 backend and 41 owned frontend hashes. Its 3436 Python tests,
focused formatting verification and 225 owned Node tests retain their separate scopes;
the shared 230 Node tests include concurrent edits. Defer inclusion of the local HEAD
until the 05/11 quality gaps or a clearly limited prototype scope are addressed.
This is a recommendation, not a blanket formal-Exit rule.
Projection and frozen donor cross-merges have the concrete documentation/core conflicts
above and require resolution/retesting. Keep c5956dc local and all formal/frozen gates.
The current user instruction authorizes documentation only, with no push, merge or deletion.

## 2026-10-08 current reviewed artifact inventory / 目前 reviewed 分類

Canonical `reviewed_run_v5` 的結果與重建方式見
[reviewed benchmark](../research/PHASE1_REVIEWED_BENCHMARK.md) 和
[reviewed reproduction](../research/PHASE1_REVIEWED_REPRODUCTION.md)；目前整體仍為
**PHASE1_FINALIZATION_BLOCKED**。本段只更新分類，沒有刪除或移動 artifact。

| Category | Current artifacts and treatment |
| --- | --- |
| KEEP | Curated reports、frozen configs、code/tests/docs、human/reference approval receipts，以及 `data/finalization/reviewed_checkpoint_v2/` 的小型 manifest、freeze、evaluation/reproduction 與 fresh comparison receipts。入口為 [evaluation receipt](../../data/finalization/reviewed_checkpoint_v2/local_evaluation_verification.json)、[reproduction receipt](../../data/finalization/reviewed_checkpoint_v2/local_reproduction_verification.json) 與 [final fresh comparison](../../data/finalization/reviewed_checkpoint_v2/fresh_delivery_comparison_final.json)。 |
| ARCHIVE | 既有 diagnostic/V3、partial V4、failed comparison/trial 與較早 blocked/pending 報告，連同各自 provenance 保留；不改稱目前正式結果。 |
| LOCAL ONLY | 原始 Blender source、大型 raw physical/source evidence、raw datasets、RRD、frame images 與其他 raw media 留在本機並依既有 ignore policy 排除 Git；不刪除、不提交。可重建內容的命令與 source/hash binding 見 reviewed reproduction。 |

沒有選取 DELETE_CANDIDATE。以下既有 inventory、數量與 approval-recording 狀態
保留為歷史 snapshot；目前 certificate／正式局部結果以連結的 V5 curated receipts
為準，原 protocol 不變。

Status: **inventory only** after completed diagnostic verification. Formal validation remains blocked. No artifact was deleted.

2026-10-07 approval-recording update: all four human profiles are APPROVED, with zero
pending human blockers. Decisions are recorded but not applied; physical certificate and
formal Cases remain NOT_RUN. KEEP the explicit approval receipt, read-only validation,
approval summary and integration receipt. Earlier blocked/pending reports and the complete
`hr02_camera_audit` durable package are ARCHIVE/preserved evidence, not deleted or relabelled
as formal results. The new `approvals_recorded/human_review/` durable package is saved and
verified: 272 manifest artifacts / 130829356 bytes and 273 complete copy files; manifest
SHA256 `923eb5f94cbe7bd1e0b45d5185b8189c07f62345c4c067d0fefc148e71e34187`.
Its per-file hashes and copy verification PASS preserve all 188 prior raw media hashes.

保留 source/config/tests/docs、experiment log、reports、manifests/hashes。Raw dataset、RRD、Blender 和大型物理證據只在本機保存。ARCHIVE 是分類，沒有移動或刪除 inherited provenance。

DELETE_CANDIDATE: none selected; no automatic deletion is authorized.

2026-10-07 review supplement: `human_review/frames/spatial_context/*.png` contains
28 locally retained source-model diagnostic views (3 stills +25 camera frames), classified
REGENERABLE. Its separate manifest, HTML/template/builder, exact successful producer archive
and current renderer are KEEP. Regeneration uses the archived producer staged at its original
path in a fresh materialized checkout, then `uv run python human_review/build_spatial_guide.py`;
see [review guide](../../human_review/README.md). Original 57 images and all source/decision files
remain unchanged. Only this task's generated mypy/pytest caches were discarded after a
storage error; no source, render, evidence or DELETE_CANDIDATE item was deleted.

| Path | Category | Size (bytes) | Reason | Canonical replacement | Regeneration |
| --- | --- | --- | --- | --- | --- |
| src | KEEP | 2193916 | source/config/tests/docs or checkpoint evidence | this published finalization branch | git checkout <published-finalization-SHA> |
| scripts | KEEP | 1151850 | source/config/tests/docs or checkpoint evidence | this published finalization branch | git checkout <published-finalization-SHA> |
| configs | KEEP | 46797 | source/config/tests/docs or checkpoint evidence | this published finalization branch | git checkout <published-finalization-SHA> |
| tests | KEEP | 4134870 | source/config/tests/docs or checkpoint evidence | this published finalization branch | git checkout <published-finalization-SHA> |
| docs | KEEP | 417549 | source/config/tests/docs or checkpoint evidence | this published finalization branch | git checkout <published-finalization-SHA> |
| human_review | KEEP | 379737 | source/config/tests/docs or checkpoint evidence | this published finalization branch | git checkout <published-finalization-SHA> |
| data/finalization/checkpoint | KEEP | 344150 | source/config/tests/docs or checkpoint evidence | this published finalization branch | git checkout <published-finalization-SHA> |
| data/finalization/local_run/baseline_regression.json | REGENERABLE | 33402 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/dataset | REGENERABLE | 214602 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/dataset_provenance_draft | ARCHIVE | 214404 | retained pre-final diagnostic draft | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics | REGENERABLE | 15860041 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics.json | REGENERABLE | 26850 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics.json_pre_preview | REGENERABLE | 26850 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics.json_pre_reader | REGENERABLE | 26739 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics_pre_preview | REGENERABLE | 15899573 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics_pre_reader | REGENERABLE | 15899406 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics_sidecar_draft | ARCHIVE | 11908099 | retained pre-final diagnostic draft | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/report_lf | REGENERABLE | 317856 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/verification.json | REGENERABLE | 54044 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/verification.json_pre_preview | REGENERABLE | 54044 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/verification.json_pre_reader | REGENERABLE | 53933 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/baseline_regression.json | REGENERABLE | 33402 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/dataset | REGENERABLE | 214602 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/diagnostics | REGENERABLE | 15859992 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/diagnostics.json | REGENERABLE | 26850 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/report | REGENERABLE | 317884 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/report_lf | REGENERABLE | 317856 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/verification.json | REGENERABLE | 54044 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/scene_audit/phase1_physical_policy_approval_20261006/floor_support_details.json.gz | REGENERABLE | 469557 | large approved evidence kept locally, excluded from Git | data/scene_audit/phase1_physical_policy_approval_20261006/artifact_manifest.json | uv run python -m amidst.materialize_physical_evidence --source-scene <source> |
| data/scene_audit/phase1_physical_policy_approval_20261006/geometry.json.gz | REGENERABLE | 2130611 | large approved evidence kept locally, excluded from Git | data/scene_audit/phase1_physical_policy_approval_20261006/artifact_manifest.json | uv run python -m amidst.materialize_physical_evidence --source-scene <source> |
| data/scene_audit/phase1_physical_policy_approval_20261006/obstacle_collider_details.json.gz | REGENERABLE | 10448625 | large approved evidence kept locally, excluded from Git | data/scene_audit/phase1_physical_policy_approval_20261006/artifact_manifest.json | uv run python -m amidst.materialize_physical_evidence --source-scene <source> |
| data/scene_audit/phase1_physical_policy_approval_20261006/source_evidence.json.gz | REGENERABLE | 35313518 | large approved evidence kept locally, excluded from Git | data/scene_audit/phase1_physical_policy_approval_20261006/artifact_manifest.json | uv run python -m amidst.materialize_physical_evidence --source-scene <source> |
| data/scene_audit/phase1_geometry_authority_20261006 | ARCHIVE | 15426622 | inherited historical provenance; retained unchanged | active physical context plus finalization input lock | git checkout f264db1579882e54cecba22db24ec8798822fd0c -- data/scene_audit/phase1_geometry_authority_20261006 |
| data/scene_audit/phase1_physical_authority_20261006 | ARCHIVE | 11940265 | inherited historical provenance; retained unchanged | active physical context plus finalization input lock | git checkout f264db1579882e54cecba22db24ec8798822fd0c -- data/scene_audit/phase1_physical_authority_20261006 |
| data/scene_audit/school_v3_approved_scale_20261006 | ARCHIVE | 11256456 | inherited historical provenance; retained unchanged | active physical context plus finalization input lock | git checkout f264db1579882e54cecba22db24ec8798822fd0c -- data/scene_audit/school_v3_approved_scale_20261006 |
| blender/school_v3.blend (external local source) | KEEP | 468300506 | immutable private/local research source | SHA256 cd46fa03...e84e; no regenerated replacement | supply exact source; never synthesize or rescale |
| human_review/frames/spatial_context/*.png | REGENERABLE | 29517434 | 28 diagnostic source context views retained locally | spatial_context_manifest.json; no replacement of original 57 images | archived producer at original path in fresh checkout; --frames 25 |
| human_review/history/spatial_context_initial_renderer.py | KEEP | 24686 | exact successful producer provenance | SHA256 8a5d52f4...305cd92 | git checkout finalization review commit |
| human_review/frames/motion_context/*.png | REGENERABLE | 19765351 | new 50-frame source-model body-motion review; older 85 images retained | motion_manifest.json and player.html | source Blender +render_motion_context.py --frames 50 --width 960 in fresh materialized checkout |
| human_review/frames/motion_context/motion_preview.gif | REGENERABLE | 8505740 | independent 10-second palette preview; original PNGs retained | gif_manifest.json; full-resolution player.html | uv run python human_review/make_motion_gif.py |
| human_review/frames/topology_context/topology_preview.png | REGENERABLE | 511640 | model/node/edge comparison from existing motion_025 image; original135PNG/GIF retained | topology_manifest.json and preview_manifest.json | uv run python human_review/render_topology_preview.py in fresh review checkout |
| human_review/frames/topology_context/ template/view/data/manifests | KEEP | small metadata | exact raw graph, display coordinates and hashes | source-bound topology_data.json | uv run python human_review/build_topology_view.py |
| human_review/frames/dashboard_context/integrated_review.jpg | REGENERABLE | 69496 | actual native browser proof of the integrated review workspace | dashboard_integration_manifest.json; original displays retained | capture index.html#visual-review-workspace with topology tab selected; 824x720 viewport |
| human_review/dashboard_template.html and dashboard_integration_manifest.json | KEEP | small source/metadata | inline media navigation with immutable decision payload | original review_template.json and media manifests | uv run python human_review/build_dashboard.py |
| human_review/frames/review_clarity/*.png | REGENERABLE | 13281548 | complete first-floor context, 25 camera-locator frames and pending HR02 body-height view; every old render retained | frames/review_clarity/manifest.json; spatial guide and dashboard | Blender with unchanged school_v3.blend + render_review_clarity.py --frames 25 in fresh output directory; see human_review/README.md |
| human_review/render_review_clarity.py and frames/review_clarity/manifest.json | KEEP | source and small metadata | fixed source/calibration, public visibility, explicit framing margins and pending body placement | immutable review_template.json and original motion/public inputs | same renderer; HTML builders with --clarity-manifest human_review/frames/review_clarity/manifest.json |
| human_review/clarity_integration_manifest.json | KEEP | small metadata | preserved-input hashes and native browser verification receipt | frames/review_clarity/manifest.json plus original review payload | verify immutable inputs and capture the same review UI; historical receipt remains preserved |
| human_review/frames/dashboard_context/clarity_review.jpg | REGENERABLE | 66884 | actual native browser screenshot of the HR02 body-height review | clarity_integration_manifest.json | capture index.html#visual-review-workspace with HR02 body-height display selected |
| human_review/frames/topology_context/template.html, view.html, topology_data.json and topology_manifest.json | KEEP | source and display metadata | synchronized P(t) marker with unchanged two-node/three-edge graph and existing public coordinates | topology_motion_integration_manifest.json; original static preview remains available | uv run python human_review/build_topology_view.py followed by build_dashboard.py with clarity manifest |
| human_review/topology_motion_integration_manifest.json | KEEP | small metadata | unchanged source, old-media hashes and native frame synchronization verification | prior clarity package plus current topology manifest | verify fixed inputs and repeat display-only checks; preserve historical receipt |
| human_review/frames/dashboard_context/topology_motion_review.jpg | REGENERABLE | 60323 | native browser frame25 showing current person position in both model and graph | topology_motion_integration_manifest.json | capture index.html#visual-review-workspace with model/topology tab at frame25 |
| human_review/topology_playback_integration_manifest.json | KEEP | small metadata | fixed playback layout and native zero-shift measurements; pending review unchanged | existing topology_manifest.json | run playback regressions and native layout sampling; preserve historical receipt |
| human_review/frames/dashboard_context/topology_playback_stable.jpg | REGENERABLE | 58511 | actual native browser screenshot of stable model/topology review | topology_playback_integration_manifest.json | capture index.html with model/topology selected at frame25 |
| human_review/inspect_hr02_camera_binding.py, render_hr02_camera_audit.py, build_hr02_camera_review.py, HR02_CAMERA_AUDIT.md | KEEP | 85759 | reproducible GT-free source-instance evidence and review workflow; remeasured after approval note | frames/hr02_camera_audit manifests | commands in human_review/HR02_CAMERA_AUDIT.md |
| human_review/frames/hr02_camera_audit/*.json, template.html, view.html | KEEP | 683797 | immutable public query, exact fresh-process match, render/UI receipts | original input hashes and review payload | frozen Blender query/render to fresh paths, then build_hr02_camera_review.py |
| human_review/frames/hr02_camera_audit/*.png | REGENERABLE | 10855553 | 8 new 1920x1080 diagnostic views with live-instance source geometry; static bases contain no baked person | renderer_manifest.json and render_verification.json | Blender with unchanged source + render_hr02_camera_audit.py --output /fresh/path |
| human_review/history/hr02_initial_camera_render/ | ARCHIVE | 10910996 PNG bytes plus receipts/view | retain all 8 initial images; initial static actor/rays and unsafe evaluated-reference producer are not canonical playback | frames/hr02_camera_audit; exact initial producer in history/hr02_initial_camera_renderer.py | initial producer archived for provenance; use corrected producer for canonical reproduction |
| human_review/history/hr02_initial_ray_audit/ | ARCHIVE | small JSON; per-file sizes in manifest | noncanonical initial trial explicitly records producer drift; no deletion | immutable canonical audit and final_repeat_verification.json | current frozen inspect_hr02_camera_binding.py to fresh output |
| human_review/frames/dashboard_context/hr02_camera_review.jpg | REGENERABLE | 114494 | native browser proof at frame45 with existing motion and new source rays | hr02_camera_integration_manifest.json and native_ui_verification.json | capture shared HR02 camera-audit tab at frame45 |
| human_review/approval_record.json, approval_validation.json, APPROVALS.md | KEEP | final per-file sizes in package manifest | explicit human choices and immutable/source verification; recorded, not applied | decisions.json plus unchanged review_template.json | preserve approval_record; run apply_decisions.py in default read-only validation mode; regenerate documentation without --apply |
| human_review/approval_integration_manifest.json | KEEP | 3354 | approved interface state, preserved prior evidence and native verification | approval_record.json, approval_validation.json and media manifests | verify immutable inputs and capture approved dashboard; preserve receipt |
| human_review/finalize_package.py, write_review_docs.py, README.md, gate.json, manifest.json | KEEP | final per-file sizes in package manifest | validated current decision state; pending behavior retained; certificate/formal stages not falsely promoted | original selected profiles and immutable question payload | uv run python human_review/write_review_docs.py; uv run python human_review/finalize_package.py |
| human_review/frames/dashboard_context/approvals_recorded.jpg | REGENERABLE | 84378 | native browser proof of four recorded approvals, zero Case 1–3 human blockers and one active iframe | approval_integration_manifest.json | capture approved dashboard; preserve resulting exact file size/hash |
| data/pilot/phase1_finalization_human_review_20261007/hr02_camera_audit/human_review/ | ARCHIVE | 130717159 manifest artifact bytes; original manifest retained | complete preapproval review package preserved independently | approvals_recorded/human_review/ verified durable package | preserve old copy; rebuild corrected diagnostics only in a fresh output path |
| /private/tmp/amidst-review-clarity-qa-v1 | ARCHIVE | local diagnostic trial | unadopted flat-lighting map and its exact producer retained; no source/evidence deletion | final clarity renderer and manifest | initial producer only; intentionally stopped after first map, not canonical evidence |

Detailed machine-readable inventory: [CSV](../../data/finalization/checkpoint/artifact_inventory.csv).
The two later human-review supplements above have their own hash-bound manifests;
their source/templates/scripts/small metadata are KEEP and raw renders remain local ignored.
Only generated bytecode caches and an untracked fresh-validation mypy cache were removed
to finish the motion supplement after storage exhaustion. No source, evidence, preview,
decision or DELETE_CANDIDATE item was deleted.

Rebuild this inventory after reproduction:

```sh
uv run python scripts/inventory_phase1_finalization_artifacts.py \
  --local data/finalization/local_run \
  --fresh /absolute/path/to/fresh-checkout/data/finalization/fresh_run
```
