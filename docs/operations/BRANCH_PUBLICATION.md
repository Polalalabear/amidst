# 分支與文件發布範圍 / Branch and documentation publication

盤點：2026-10-14，依Git／GitHub refs及既有文件，不掃描實作程式碼。
本輪授權main只更新README；工程與Phase1其他文件分別保留在独立PR，沒有程式整合、刪除或清理。

| 分支／成果 | 本輪處理與審查範圍 |
| --- | --- |
| `main`，程式基底439c866 | README-only commit；程式與設定維持原tree。 |
| `codex/readme-current-progress` | 保存本輪README-only commit；同一commit可依授權進main。 |
| `codex/simulation-engineering`，c6661dd | 已在GitHub；仍是現役工程，後續Blender／R2／R3未整批合main。 |
| `codex/docs-current-progress` | 從c6661dd的文件feature；PR base=`codex/simulation-engineering`，本輪不merge。 |
| `phase1/finalization-sprint`，043bed2 | 已發布限定Case1–3成果；保留其ref與正式tag，不回退到883204a。 |
| `codex/phase1-case23-formal`，043bed2 | 保存現役formal工作名稱；與已公開release相同Git內容，沒有新增未驗證程式。 |
| `codex/docs-phase1-scoped-progress` | 從043bed2的flat文件feature；PR base=`phase1/finalization-sprint`，本輪不merge。 |
| `phase2/integration-hardening`，5b51d2c | 原frozen branch與tag保持原值，本輪不解凍。 |
| `phase1/physical-policy-approval`，c5956dc | 原LOCAL_ONLY/HOLD與canonical資產角色保留，不當成本輪待上傳變更。 |
| `codex/deterministic-downstream-scenarios` | 遠端已依先前授權刪除；本機c0717ae與歷史內容保留，不重建遠端。 |

必要工程／正式成果已有GitHub保存；本輪新增README與兩個docs features的普通push。
只提交本輪隔離文件差異；其他對話的未提交／private修改不從共享index收進來。
遠端push後的exact SHA／PR／範圍核對另存出版收據；本表的準備狀態不當作已merge。

## 歷史研究恢復入口 / Historical recovery

以下14個annotated checkpoint tags已以GitHub live `ls-remote`核對peel commit。
本輪保留所有既有branches；tag存在不是本輪刪除授權，也不保存ignored raw／runtime資產。
目前正式tag另為 `phase1-scoped-case123-20261014 → 043bed2`；原frozen tag為
`phase2-integration-hardening-frozen-20261006 → 5b51d2c`。

| 歷史範圍 | 固定tag | Peeled commit |
| --- | --- | --- |
| `codex/dataset-infrastructure` | [checkpoint/codex/dataset-infrastructure-91f4ea6](https://github.com/Polalalabear/amidst/tree/checkpoint/codex/dataset-infrastructure-91f4ea6) | `91f4ea600805739aa9659dfef6a381d71be9a692` |
| `codex/docs-agent-handoff` | [checkpoint/codex/docs-agent-handoff-2c586b1](https://github.com/Polalalabear/amidst/tree/checkpoint/codex/docs-agent-handoff-2c586b1) | `2c586b13f957b1b0d17675b4ff8aa89629681172` |
| `codex/phase1-preview-workspace` | [checkpoint/codex/phase1-preview-workspace-04c699d](https://github.com/Polalalabear/amidst/tree/checkpoint/codex/phase1-preview-workspace-04c699d) | `04c699d8473235392eb18be483766bcc4de42a58` |
| `phase1/finalization-sprint` | [checkpoint/phase1/finalization-sprint-883204a](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/finalization-sprint-883204a) | `883204af854bed301506b39d63ccb33312b79ff2` |
| `phase1/geometry-authority` | [checkpoint/phase1/geometry-authority-bb66bb7](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/geometry-authority-bb66bb7) | `bb66bb74a4a76430f6fa8f79672345385a79e3f0` |
| `phase1/physical-authority-resolution` | [checkpoint/phase1/physical-authority-resolution-0bab8ac](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/physical-authority-resolution-0bab8ac) | `0bab8ac262b93f3c8babad69432744e7e4d1c541` |
| `phase1/physical-policy-lightweight` | [checkpoint/phase1/physical-policy-lightweight-f264db1](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/physical-policy-lightweight-f264db1) | `f264db1579882e54cecba22db24ec8798822fd0c` |
| `phase1/pilot-dataset-and-wall-inference` | [checkpoint/phase1/pilot-dataset-and-wall-inference-fdf9e7e](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/pilot-dataset-and-wall-inference-fdf9e7e) | `fdf9e7e8f2dc695917ba42094a63cc06ca910963` |
| `phase1/pilot-downstream-reconstruction` | [checkpoint/phase1/pilot-downstream-reconstruction-51f1ec7](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/pilot-downstream-reconstruction-51f1ec7) | `51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e` |
| `phase1/pilot-robustness-validation` | [checkpoint/phase1/pilot-robustness-validation-ce2974b](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/pilot-robustness-validation-ce2974b) | `ce2974b25b31a8cb0ec9bc579a84d708d3356bf7` |
| `phase1/projection-conditioning-mitigation` | [checkpoint/phase1/projection-conditioning-mitigation-5f020b0](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/projection-conditioning-mitigation-5f020b0) | `5f020b075d4a670f60007eab7baeb12055f2f5d9` |
| `phase1/projection-model-upgrade` | [checkpoint/phase1/projection-model-upgrade-8f4055f](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/projection-model-upgrade-8f4055f) | `8f4055ffcdc3bf6efd723c7956ac685e1fe033f1` |
| `phase1/projection-sensitivity` | [checkpoint/phase1/projection-sensitivity-b90e81a](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/projection-sensitivity-b90e81a) | `b90e81adb3acc1a0c1e599d488f3113f0842cfb4` |
| `phase2/integration-foundation` | [checkpoint/phase2/integration-foundation-e4e5afc](https://github.com/Polalalabear/amidst/tree/checkpoint/phase2/integration-foundation-e4e5afc) | `e4e5afc3ddd19fdb679e5fe0773c3d7f918a3d2b` |

## 合併與清理仍分開 / Integration and cleanup remain separate

main439c866的R1整合已完成；其他整支工程／研究branches不能只因已push或文件PR通過就認定可整批merge。
R2品質FAIL、R3首次demoFAILED、private候選未採用、新48未開始；05維持baseline。
Phase1 scoped workflow18 gates PASS，但Case3原研究目標未達、整校未認證；它與main第一版demo的契約／布局不同。
後續整合需另選精確已驗證範圍及對應授權，不把本次文件整理當作解除gate。

Worktree與資料的清理條件见[資產清理](PHASE1_ARTIFACT_CLEANUP.md)與[重現交接](CURRENT_WORK_REPRODUCTION.md)。
Shared task、runtime consumers、dirty state、raw保存與恢復locator均核對後才可另外處理；本輪沒有刪除、服務啟停或搬移。

English: Main receives README only. Engineering and scoped Phase1 documentation use separate feature branches and
unmerged PRs against their own active bases. Current code is already published; local c5956dc remains on hold.
Fourteen historical checkpoint tags, the scoped release tag and frozen Phase2 tag preserve Git history; they do not
back up raw assets or authorize cleanup. No other chat's edits, active refs, worktrees, services or source assets are changed.
