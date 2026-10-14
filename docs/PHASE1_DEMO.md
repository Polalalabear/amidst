# Phase 1 diagnostic demo / 診斷展示

**現在入口（2026-10-14）：**[scoped文件索引](README.md)、[最終報告](PHASE1_CASE23_FINAL_REPORT.md)及[正式重建](PHASE1_CASE23_REPRODUCTION.md)。
Case1–3的18 Exit gates已PASS與clean重現；Case3 ADE目標未達、整校NOT_CERTIFIED、Case4 DEFERRED。
下方保留原日期的歷史方法／收據，旧BLOCKED、舊tmp或finalization指令不是目前formal續作。
當前formal工作樹是 `.local-worktrees/phase1-case23-formal`；原 `.local-worktrees/phase1-finalization` 已是工程角色，不可照舊文切換或覆寫。
English: Current scoped acceptance and reproduction are linked above. The dated body is historical; do not run its legacy paths against the active engineering checkout.

Formal Case 1–3 recordings: **N/A / NOT_RUN** until the
[human gate](../human_review/README.md) passes.

Persistent local copies are in the canonical repository's ignored
`data/pilot/phase1_finalization_20261006/local_run/diagnostics/<stream>/demo/`.
Streams are `office`, `auditorium`, and `corridor`. The matching fresh copies are
under `data/pilot/phase1_finalization_20261006/fresh_run/diagnostics/`.

Fresh exported office / corridor / auditorium recordings are local DIAGNOSTIC
artifacts under `data/finalization/local_run/diagnostics/`. Each stream has
`summary.json` and `demo/presentation.json`; its recording and PNG are
`demo/diagnostic.rrd` and `demo/preview.png`. Replay with:

```sh
uv run rerun /absolute/path/to/diagnostic.rrd
```

查看 scene context、校準 cameras、OBSERVED/GAP、projection method/confidence、
configured Top-K/timing（若 legacy Graph contract 可執行）。GT debug 在獨立 entity
layer，初始不顯示；可由 Rerun entity visibility 控制。未取得 authority 的 collider
pruning、floor/scope certification 與 surface-constrained school inference 應顯示
N/A，不得由 annotation box 或空 collider 集合視覺上宣稱 PASS。

The static PNG and canonical presentation JSON are reproducible previews.
Recording-reader checks are saved separately in the checkpoint. A replayable
diagnostic recording is not a formal Case recording or a certified school mesh.
The source Blender file remains unchanged; no new building geometry is invented.
