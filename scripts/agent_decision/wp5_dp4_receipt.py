"""Curate the LOCAL DP4 dry/fake and --live-with-fake-provider verification outputs."""

import argparse
import hashlib
import json
from pathlib import Path
import re


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    text = (a.work / "verification.log").read_text()
    assert "[100%]" in text and "FAILED " not in text
    count = sum(len(s) for s in re.findall(r"^(\.+)\s+\[\s*\d+%\]", text, re.M))
    assert count == 140
    outputs = []
    paths = []
    for folder in sorted((a.work / "final-tmp").iterdir()):
        if folder.is_symlink() or not folder.name.startswith("test_live_fake_provider_"):
            continue
        out = folder / "out"
        rows = [json.loads(s) for s in (out / "calls.jsonl").read_text().splitlines()]
        summary = json.loads((out / "summary.json").read_text())
        outputs.append(
            {
                "model": rows[0]["model"],
                "method": rows[0]["dp4_method"],
                "rows": len(rows),
                "fake_provider_calls": sum(r["steps"] for r in rows),
                "status": summary["status"],
                "format_error_rate": summary["cells"][0]["format_error_fallback"]["rate"],
                "artifacts": out.relative_to(a.work).as_posix(),
            }
        )
        paths.extend(p for p in out.iterdir() if p.is_file())
    assert len(outputs) == 4 and all(o["rows"] == 24 and o["status"] == "OK" for o in outputs)
    for name in [
        "dry-api-pilot",
        "dry-api-formal",
        "dry-agent-pilot",
        "dry-agent-formal",
        "fake-api",
        "fake-agent",
    ]:
        paths.extend(p for p in (a.work / name).iterdir() if p.is_file())
    paths.extend(a.work / p for p in ["test-first.log", "verification.log", "dry-report.log"])
    files = [
        {
            "path": p.relative_to(a.work).as_posix(),
            "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
        for p in sorted(set(paths))
    ]
    manifest = (
        json.dumps({"path_base": "$AMIDST_ARTIFACTS/cx554-20261117", "files": files}, indent=2)
        + "\n"
    )
    (a.work / "MANIFEST.json").write_text(manifest)
    receipt = {
        "issue": 554,
        "base": "21aacc8ea75b49fe9efd914a0d0198b789066a7a",
        "status": "FOCUSED_PASS",
        "verification": {
            "passed": count,
            "test_first_failed": 8,
            "mode": "fake clients/transports only",
            "paid_calls": 0,
            "real_key_reads": 0,
            "real_ollama_or_openai_calls": 0,
        },
        "live_interface_fake_provider_outputs": outputs,
        "scope": "Raw --live fixture manifests contain synthetic approval flags; these are tests, NOT real authorization or paid runs",
        "artifact_manifest": {
            "path": "$AMIDST_ARTIFACTS/cx554-20261117/MANIFEST.json",
            "sha256": hashlib.sha256(manifest.encode()).hexdigest(),
            "file_count": len(files),
            "bytes": sum(f["bytes"] for f in files),
            "regeneration": "WP5_DP4_HANDOFF_20261117.md focused pytest + dry/fake commands",
        },
        "not_verified": [
            "real provider latency/output/usage",
            "Colab L4 execution",
            "native Windows execution",
            "real question set",
            "paid execution or approval",
            "identity/physical acceptance",
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
