"""Run the dependency-free Node GT-event contract in CI as well as locally."""
from pathlib import Path
import subprocess


def test_gt_only_reappearance_contract():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(["node", "--test", "tests/evaluation/e3_reappearance_events.test.mjs"],
                            cwd=root, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_shared_registry_rejects_private_fields():
    import importlib.util
    import pytest
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("release_reappearances", root / "scripts/evaluation/e3_cases/release_reappearances.py")
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    producer.check_safe_registry({"runs": [{"run_id": "sample", "index_path": "indexes/sample/detection_index.json"}]})
    for key in ("gt_visible", "gt_boxes", "actor_id", "decision_points", "baseline_snapshot"):
        with pytest.raises(ValueError, match="PRIVATE_RUNTIME_INPUT"):
            producer.check_safe_registry({"runs": [{key: []}]})


def test_release_stops_if_gt_changed_before_index_validation(tmp_path, monkeypatch):
    import hashlib
    import importlib.util
    import json
    import pytest
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("release_reappearances_guard", root / "scripts/evaluation/e3_cases/release_reappearances.py")
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    base = tmp_path / "base"; base.mkdir()
    (base / "MANIFEST.json").write_text("{}")
    monkeypatch.setattr(producer, "BASE_MANIFEST_SHA", hashlib.sha256(b"{}").hexdigest())
    new = tmp_path / "new"; new.mkdir()
    (new / "case.json").write_text("control")
    (new / "gt.json").write_text("changed")
    case = {"case_id": "sample", "family": "B", "case_path": "case.json",
            "case_sha256": hashlib.sha256(b"control").hexdigest(),
            "gt_path": "gt.json", "gt_sha256": "0" * 64}
    frozen = {"status": "GT_AND_SCRIPT_FROZEN_BEFORE_DETECTION_AND_E3",
              "cases": [case] * 4 + [{**case, "family": "C"}] * 3}
    (new / "GT_FREEZE.json").write_text(json.dumps(frozen))
    monkeypatch.setattr(producer, "GT_PIN_CONFIG", new / "GT_FREEZE.json")
    # No indexes/pixels exist: this must reject the changed GT first.
    with pytest.raises(ValueError, match="FROZEN_CASE_OR_GT_CHANGED"):
        producer.release(new, base, tmp_path)
