"""Test-only, pinned Git-object composition. Never imported by product code.

No fetch, checkout, assets, model transport or dependency installation. The owning
feature commits are intentionally composed outside the repository, not merged.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLAN = (
    (
        "a958dd4043ebcd5ef2d9fdb362d15f8c4ce3941f",
        (
            "src",
            "tests/q1q5",
            "tests/unit/test_q5_switch_eval.py",
            "configs/q1q5",
            "pyproject.toml",
            "scripts/build_q1q5_detection_index.py",
            "scripts/eval_q5_switch.py",
        ),
    ),
    (
        "798f73711e302a2e49fd495e96958ed254720e6f",
        (
            "src/amidst/q1q5/q5_controller.py",
            "tests/q1q5/test_q5_controller.py",
        ),
    ),
    (
        "e6eb30bae0641af3522b0ab45cb9d12c6b9cc4e1",
        (
            "src/amidst/q1q5/q4_evidence.py",
            "tests/q1q5/test_q4_evidence.py",
        ),
    ),
    (
        "7b0ef332dcec84b6045c8d6b821080c27370265f",
        (
            "src/amidst/q1q5/q1_search.py",
            "tests/q1q5/test_q1_search.py",
        ),
    ),
    (
        "1bb4135965fb53643e9fbbaf8e41fd77e8ffb9c8",
        (
            "src/amidst/q1q5/q5_agent.py",
            "src/amidst/q1q5/agent_tools.py",
            "src/amidst/q1q5/llm_guidance.py",
            "tests/q1q5/test_q5_agent.py",
            "tests/q1q5/test_agent_tools.py",
            "configs/q1q5/prompts/q5_agent_v1.txt",
            "configs/q1q5/prompts/q5_agent_v2.txt",
        ),
    ),
    (
        "d9125b68bdea82769a6c3b20317083d701fb2f1a",
        (
            "src/amidst/q1q5/api.py",
            "src/amidst/q1q5/ollama_runtime.py",
            "src/amidst/q1q5/llm_provider.py",
            "src/amidst/q1q5/q3_parse.py",
            "src/amidst/workbench/service.py",
            "tests/q1q5/test_api.py",
            "tests/q1q5/test_ollama_runtime.py",
            "configs/q1q5/prompts/q3_parse_v2.txt",
        ),
    ),
    (
        "9a56bf8f11d4bff1cb6de60843451bce400ee831",
        (
            "src/amidst/q1q5/event_modes.py",
            "tests/q1q5/test_event_modes.py",
        ),
    ),
    ("994d34c8340855dbf0e28d0273851049df5e6c7d", ("src/amidst/contracts",)),
)


def materialize(destination: Path) -> Path:
    """Write a new external directory; fail rather than reuse an unknown tree."""
    destination = destination.absolute()
    parent = destination.parent.resolve(strict=True)
    if destination.exists() or destination.is_symlink() or parent.is_relative_to(REPO):
        raise ValueError("A new directory outside the repository is required")
    destination = parent / destination.name
    destination.mkdir()
    files = {}
    for commit, paths in PLAN:
        names = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", commit, "--", *paths],
            cwd=REPO,
            text=True,
        ).splitlines()
        if not names:
            raise ValueError(f"Pinned source missing: {commit}")
        for name in names:
            raw = subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=REPO)
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            files[name] = {"commit": commit, "sha256": hashlib.sha256(raw).hexdigest()}
    for name in ("q5_invariant_helpers.py",):
        source = Path(__file__).with_name(name)
        if source.exists():
            raw = source.read_bytes()
            target = destination / "tests/q1q5" / name
            target.write_bytes(raw)
            files[f"tests/q1q5/{name}"] = {
                "commit": "LOCAL_STAGE2_TEST_ONLY",
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
    (destination / "AUDIT_COMPOSITION.json").write_text(
        json.dumps({"kind": "TEST_COMPOSITION_NOT_INTEGRATED_PRODUCT", "files": files}, indent=2),
        encoding="utf-8",
    )
    return destination


@lru_cache(maxsize=1)
def snapshot() -> Path:
    parent = Path(tempfile.mkdtemp(prefix="amidst-q5-stage2-tests-"))
    return materialize(parent / "snapshot")


def run_pinned(body: str) -> dict:
    """Execute one mechanical scenario in an isolated interpreter, return JSON."""
    root = snapshot()
    code = (
        """
import json
from dataclasses import asdict
from test_q5_controller import fixture, request, seed_id, port, run, RuleController
def bundle(r, b):
    return {'response': r.response, 'decisions': r.decisions_bytes.decode(),
            'links': r.links_bytes.decode(), 'snapshots': list(r.snapshots),
            'evidence': list(r.evidence), 'index_records': list(b.index.records),
            'trusted_scope': r.response['resolved_scope']}
"""
        + body
        + "\nprint(json.dumps(result, allow_nan=False))\n"
    )
    env = os.environ | {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": os.pathsep.join((str(root / "src"), str(root / "tests/q1q5"))),
    }
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    result = json.loads(completed.stdout)
    evidence_dir = os.environ.get("Q5_AUDIT_EVIDENCE_DIR")
    if evidence_dir:
        folder = Path(evidence_dir).resolve(strict=True)
        if folder.is_relative_to(REPO):
            raise ValueError("Audit evidence must stay outside the repository")
        key = hashlib.sha256(body.encode()).hexdigest()
        record = json.dumps({"scenario_source": body, "result": result}, sort_keys=True, indent=2)
        # Preserve raw timing evidence; different stats do not replace old runs.
        content_key = hashlib.sha256(record.encode()).hexdigest()[:16]
        path = folder / f"scenario-{key}-{content_key}.json"
        if path.exists():
            if path.read_text(encoding="utf-8") != record:
                raise ValueError("Evidence content-address collision")
        else:
            with path.open("x", encoding="utf-8") as stream:
                stream.write(record)
    return result


if __name__ == "__main__":
    print(materialize(Path(sys.argv[1])))
