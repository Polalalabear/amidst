"""Hash explicit E3 case artifacts; exclude dependency caches and in-flight other cases."""
import argparse
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--root", type=Path, required=True)
p.add_argument("--sample", action="store_true")
a = p.parse_args(); root = a.root.resolve()
corpus_name = "CORPUS_SAMPLE.json" if a.sample else "CORPUS.json"
corpus = json.loads((root / corpus_name).read_text())
files = {root / corpus_name}
registry = root / ("RUNTIME_INPUTS_SAMPLE.json" if a.sample else "RUNTIME_INPUTS.json")
if registry.is_file():
    files.add(registry)
for name in ["environment.json", "source_receipt.json", "verification.json", "architecture-guard.json", "focused-pytest.txt", "focused-node.txt", "f1-format-probe.json", "f1_e3_scoring.py", "f1_preregistration.md", "browser-replay.json"]:
    if (root / name).is_file() and not a.sample:
        files.add(root / name)
for c in corpus["cases"]:
    case_id = c["case_id"]
    files.update(root.glob(f"{case_id}.*"))
    for rel in [f"rgb/{case_id}", f"pixels/{case_id}", f"indexes/{case_id}"]:
        files.update(p for p in (root / rel).rglob("*") if p.is_file())
    for rel in [c["gt_path"], f"predictions/{case_id}.jsonl", f"baseline/{case_id}.json"]:
        if (root / rel).is_file():
            files.add(root / rel)
entries = [{"path": f.relative_to(root).as_posix(), "bytes": f.stat().st_size,
            "sha256": hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(files)]
manifest = {"file_count": len(entries), "bytes": sum(f["bytes"] for f in entries), "files": entries,
            "regeneration": "See docs/operations/E3_CASES_20261122.md; renderer/model/runtime outputs may differ, preserve these frozen bytes.",
            "raw_artifacts_committed": False, "dependency_caches_included": False}
target = root / ("MANIFEST_SAMPLE.json" if a.sample else "MANIFEST.json")
target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
print(json.dumps({"path": target.name, "file_count": manifest["file_count"], "bytes": manifest["bytes"],
                  "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}))
