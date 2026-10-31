# SYNTHETIC CQ-42-T fixtures

These six checklist IDs (two each from B/C/D) are format examples, not the full
#346 checklist or actual browser/rehearsal results. The small text output was
generated for this test. No Blender/media/GT/formal/clean-package bytes are used.

- `positive.SYNTHETIC.json`: complete six-item record and fallback a/b/c.
- `missing-item.SYNTHETIC.json`: missing D-02, rejected.
- `pass-without-evidence.SYNTHETIC.json`: PASS without a hash, rejected.
- `fallback-not-rehearsed.SYNTHETIC.json`: b marked NOT_RUN, rejected.
- `demo-script.SYNTHETIC.md`: mapped steps with 操作／預期／fallback columns.

Evidence hashes are syntactically checked and reported, not read as actual
operation evidence. A valid record can honestly contain FAIL/NOT_RUN items;
those results are never changed into PASS. Only the user can accept #346.

The schemas and test source pins are recorded in the CQ-42-T curated receipt.
