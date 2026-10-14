# GitHub 遠端分支清理 / Remote branch cleanup

日期：2026-10-14。使用者要求直接清除不需要、且不影響專案與Phase1／2重要紀錄的GitHub branches。
本輪已刪除14個冗餘**遠端branch名稱**，由21減為7；沒有刪除commit、tag、本機branch、worktree或檔案。
原研究歷史保存於對應annotated checkpoint tags；README提交則已由main與merged PR#3保存。

## 刪除前的核對 / Pre-deletion checks

- 遠端21 heads與所有tags由live `ls-remote`核對；13個historical tags的peel SHA與候選tip逐一相等。
- 9個候選tip已是main f9b563f的祖先；其餘5個由exact checkpoint tags完整保存，未將研究線合併到main。
- 5個shared worktrees沒有checkout任何候選branch；2個open文件PR的head/base均保留。
- repo default branch是main；GitHub queued／in_progress Actions均為空。
- 最新README、工程／formal文件沒有使用候選branch作現役GitHub tree/blob URL；恢復入口使用固定tag。
- 刪除採atomic與expected-tip SHA條件鎖；若任何tip移動或權限拒絕，整批不刪除。沒有改寫commit history。

## 已清除的遠端heads / Removed remote heads

| 原branch | 原tip | 保存位置 | 已完整包含於main |
| --- | --- | --- | --- |
| `codex/dataset-infrastructure` | `91f4ea600805739aa9659dfef6a381d71be9a692` | [checkpoint/codex/dataset-infrastructure-91f4ea6](https://github.com/Polalalabear/amidst/tree/checkpoint/codex/dataset-infrastructure-91f4ea6) | 是 |
| `codex/docs-agent-handoff` | `2c586b13f957b1b0d17675b4ff8aa89629681172` | [checkpoint/codex/docs-agent-handoff-2c586b1](https://github.com/Polalalabear/amidst/tree/checkpoint/codex/docs-agent-handoff-2c586b1) | 是 |
| `codex/phase1-preview-workspace` | `04c699d8473235392eb18be483766bcc4de42a58` | [checkpoint/codex/phase1-preview-workspace-04c699d](https://github.com/Polalalabear/amidst/tree/checkpoint/codex/phase1-preview-workspace-04c699d) | 是 |
| `codex/readme-current-progress` | `7d1237cabddcd2b0e3ff1a838b799fc936522a2c` | [main／merged PR#3](https://github.com/Polalalabear/amidst/pull/3) | 是 |
| `phase1/geometry-authority` | `bb66bb74a4a76430f6fa8f79672345385a79e3f0` | [checkpoint/phase1/geometry-authority-bb66bb7](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/geometry-authority-bb66bb7) | 是 |
| `phase1/physical-authority-resolution` | `0bab8ac262b93f3c8babad69432744e7e4d1c541` | [checkpoint/phase1/physical-authority-resolution-0bab8ac](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/physical-authority-resolution-0bab8ac) | 是 |
| `phase1/physical-policy-lightweight` | `f264db1579882e54cecba22db24ec8798822fd0c` | [checkpoint/phase1/physical-policy-lightweight-f264db1](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/physical-policy-lightweight-f264db1) | 是 |
| `phase1/pilot-dataset-and-wall-inference` | `fdf9e7e8f2dc695917ba42094a63cc06ca910963` | [checkpoint/phase1/pilot-dataset-and-wall-inference-fdf9e7e](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/pilot-dataset-and-wall-inference-fdf9e7e) | 是 |
| `phase1/pilot-downstream-reconstruction` | `51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e` | [checkpoint/phase1/pilot-downstream-reconstruction-51f1ec7](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/pilot-downstream-reconstruction-51f1ec7) | 是 |
| `phase1/pilot-robustness-validation` | `ce2974b25b31a8cb0ec9bc579a84d708d3356bf7` | [checkpoint/phase1/pilot-robustness-validation-ce2974b](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/pilot-robustness-validation-ce2974b) | 否，保留exact tag |
| `phase1/projection-conditioning-mitigation` | `5f020b075d4a670f60007eab7baeb12055f2f5d9` | [checkpoint/phase1/projection-conditioning-mitigation-5f020b0](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/projection-conditioning-mitigation-5f020b0) | 否，保留exact tag |
| `phase1/projection-model-upgrade` | `8f4055ffcdc3bf6efd723c7956ac685e1fe033f1` | [checkpoint/phase1/projection-model-upgrade-8f4055f](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/projection-model-upgrade-8f4055f) | 否，保留exact tag |
| `phase1/projection-sensitivity` | `b90e81adb3acc1a0c1e599d488f3113f0842cfb4` | [checkpoint/phase1/projection-sensitivity-b90e81a](https://github.com/Polalalabear/amidst/tree/checkpoint/phase1/projection-sensitivity-b90e81a) | 否，保留exact tag |
| `phase2/integration-foundation` | `e4e5afc3ddd19fdb679e5fe0773c3d7f918a3d2b` | [checkpoint/phase2/integration-foundation-e4e5afc](https://github.com/Polalalabear/amidst/tree/checkpoint/phase2/integration-foundation-e4e5afc) | 否，保留exact tag |

## 保留的7條分支 / Seven retained branches

| Branch | 保留理由 |
| --- | --- |
| `main` | 穩定R1與已更新README，f9b563f未變。 |
| `codex/simulation-engineering` | 現役Blender／Agent工程，c6661dd未變。 |
| `phase2/integration-hardening` | 原Phase2 FROZEN入口，5b51d2c與frozen tag未變。 |
| `phase1/finalization-sprint` | 最新scoped Case1–3發布043bed2；文件PR#2的base。 |
| `codex/phase1-case23-formal` | 現役formal工作branch，043bed2。 |
| `codex/docs-current-progress` | 工程文件PR#1的source；本次清理紀錄在此分支續補，PR仍未合併。 |
| `codex/docs-phase1-scoped-progress` | Phase1文件PR#2的source，b55b57a未變。 |

Phase1 `phase1-scoped-case123-20261014 → 043bed2`、歷史883204a checkpoint與原Phase2 frozen tag均保留。
13條已退休研究／基礎branch的Git內容仍由相同commit的tags可達；不是刪除Phase1／2研究成果。
Raw Blender、RGB／影片、權重、資料庫、review與runtime依賴仍在原本機器；tag不是这些bytes的備份，本次沒有搬移或清理它們。

## 驗證與恢復 / Verification and restoration

刪除後live refs只少指定14 heads；剩餘7 heads符合原預期SHA，全部16 annotated tags／peels不變。
本機5個worktrees的HEAD／branch／index／dirty／staged狀態與刪除前相同。
本輪只進行Git可達性、精確ref與文件引用檢查；未掃實作程式碼、未重跑程式測試或操作runtime服務。
文件變更只追加到PR#1，不merge main或現役工程branch。完整小型本機收據在ignored
`data/pilot/github_branch_cleanup_20261014/receipt.json`；原private／raw不發布。

若日後需要相同歷史branch名稱，可從表列的保留commit或tag重新建立；不要用別個tag覆蓋原歷史。
在已核對refs的checkout可使用 `git push origin <preserved-commit>:refs/heads/<original-branch>`；
恢復名稱不會自動恢復未追蹤raw、資料庫或舊runtime locator。

English: Fourteen redundant remote heads were removed, reducing21 to7. Nine were fully included in main;
five retain their exact research history under annotated checkpoint tags. Main, active engineering/formal/frozen refs,
both open documentation PRs, all tags and every local branch/worktree/file remain intact. Expected-SHA leases and an
atomic delete prevented stale-tip deletion. Validation used Git metadata and documents only, with no code/runtime tests.
