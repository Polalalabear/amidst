"""Check a pack against MANIFEST.json and make sure it holds no ground truth. python verify_pack.py <pack root>"""
import hashlib
import json
import sys
from pathlib import Path

FORBIDDEN = ("answers_private", "gt_", "ground_truth", "actor_id", "candidate_actors", "scoring_private", "trajectory")
root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
man = json.loads((root / "MANIFEST.json").read_text())
bad = []
for rel, sha in man["files"].items():
    p = root / rel
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != sha:
        bad.append(f"mismatch: {rel}")
for p in root.rglob("*"):
    if p.is_file() and "RETURN" not in p.parts:
        if any(f in p.name for f in FORBIDDEN):
            bad.append(f"forbidden file name: {p}")
        if p.suffix in (".json", ".jsonl") and p.name != "MANIFEST.json":
            text = p.read_text(encoding="utf-8", errors="replace")
            bad += [f"forbidden key {f!r} in {p}" for f in FORBIDDEN if f in text]
print("INVALID\n" + "\n".join(bad) if bad else f"VALID ({len(man['files'])} files)")
sys.exit(1 if bad else 0)
