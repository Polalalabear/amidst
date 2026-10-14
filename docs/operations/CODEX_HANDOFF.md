# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

更新：2026-10-14；文件基線 `c6661dd53507805deb4613f30afb31798987bfd5`、main 程式基底 `439c866`。
先讀[全部工作與重現](CURRENT_WORK_REPRODUCTION.md)，再依[demo 指南](../engineering/DEMO_V1.md)操作。
前者是原交接收據的快照；本次文件維護沒有重核 runtime、資產 hash、模型或資料庫。

| 工作 | 現況與下一步 |
| --- | --- |
| main | 已整合經驗證 R1 demo／必要 ABC；後續 Blender／R2／R3／formal scoped 程式未整批合併。 |
| demo | 五段核心5/5；含 Saved Agent 加映5/6。使用當次 `DEMO_URL`，新 origin 尚未恢復舊 token；90秒影片及完整可攜套件未交付。 |
| 05 | 候選未達預定門檻，維持 baseline；不得依曝光 test 再調參。 |
| 11 R2 | 48題完成，常規12/40（中7/20、英5/20）；417 literal錯誤0、DETAIL完整性誤報4。安全邊界8/8、乾淨拒絕2/8、澄清0/8，QUALITY_GATE_NOT_MET。 |
| 11 R3 | 原工程3736 Python／HTTP68 PASS；23 SCRIPTED、0真模型。首次真實demo FAILED；private220候選未套用，新48回放未開始。Phase2仍估約50%。 |
| Blender人審 | Office20／Classroom15共35差異，38物理checks UNKNOWN；Auditorium尚未核對。人審筆記不升權。 |
| Phase1 scoped | [正式043bed2報告](https://github.com/Polalalabear/amidst/blob/043bed2d6dac34698260bd37faefc31b9009d3ca/docs/PHASE1_CASE23_FINAL_REPORT.md)：Case1–3的18 Exit gates PASS、clean重現；Case3 ADE改善0%未達原30%目標。PARTIAL_APPROVED／NOT_CERTIFIED，Case4 DEFERRED。 |

續作依[當前 prompt](PHASE1_NEXT_CHAT_PROMPT.md)與[05／11品質文件](../engineering/PHASE2_LOCAL_REPAIR_0511.md)。
不把 fixture PASS 或舊R2成功demo當成新R3品質通過；原失敗、負結果與凍結收據保留。

本次出版邊界：main 只更新根 README；其他導航／引用分別保留在 `codex/docs-current-progress` 與
`codex/docs-phase1-scoped-progress` 的 PR。工程、正式研究與 frozen refs 不移動；不刪除 worktree／branch／檔案，
不更動其他工作的 index、dirty state、服務或原資產。`c5956dc` 仍是 LOCAL_ONLY/HOLD。
歷史恢復依已發布 checkpoint tags；目前成果與歷史883204a分开，見[分支與發布範圍](BRANCH_PUBLICATION.md)。

[完整 c6661dd 歷史交接](../history/CODEX_HANDOFF_20261014_C666.md)保存各milestone與當時驗證數字；
[工作紀錄](../history/WORK_LOG.md)保存本輪文件維護。歷史總數不累加，也不宣稱本次重跑。

## English

The documentation baseline is c6661dd; main's code baseline is the validated R1 at439c866.
Use the [work/reproduction snapshot](CURRENT_WORK_REPRODUCTION.md), [demo guide](../engineering/DEMO_V1.md)
and [current continuation](PHASE1_NEXT_CHAT_PROMPT.md). R2 completed48 tasks but missed its quality gate;
R3 engineering checks passed while its first real-model demo failed. The private candidate is unapplied;
no new48 replay has started. Keep05 baseline and the Phase2 estimate at approximately50%.

Scoped Phase1 release043bed2 passes18 Case1–3 workflow gates and clean reproduction, with Case3's0% ADE gain
reported as an unmet research target. Whole-school geometry remains uncertified and Case4 deferred.
Main receives only README in this publication; other navigation lives in separate documentation PRs.
Retain active worktrees, other edits, source assets, saved state and frozen refs. No code/model/runtime tests
were rerun during this refresh. The [historical handoff](../history/CODEX_HANDOFF_20261014_C666.md) retains dated evidence.
