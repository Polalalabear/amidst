"""Receipts preserve failures/unknowns and never overwrite protected data."""

import json
import subprocess
from types import SimpleNamespace

import pytest
from office_rehearsal_check import Audit, output_target, rehearsal_check


def fake_launcher(tmp_path, monkeypatch):
    import office_rehearsal_check as module

    repo = tmp_path / "repo"
    repo.mkdir()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    launcher = SimpleNamespace(
        REPO=repo,
        ASSETS=repo,
        EVIDENCE=tmp_path / "evidence",
        BUNDLE=None,
        RUNTIME=runtime,
        subprocess=subprocess,
        preflight=lambda: {"head": "frozen"},
    )
    monkeypatch.setattr(module, "artifact_hashes", lambda *args: [])
    return launcher


def test_no_service_receipt_is_unknown_and_no_lifecycle_calls(tmp_path, monkeypatch):
    launcher = fake_launcher(tmp_path, monkeypatch)
    launcher.readiness = lambda *args, **kwargs: pytest.fail("no service must not call HTTP")
    out = tmp_path / "receipt.json"
    assert rehearsal_check(launcher, out) == 2
    report = json.loads(out.read_text())
    assert report["status"] == "UNKNOWN"
    assert report["source"]["head"] == "frozen"
    assert (
        next(x for x in report["checks"] if x["check"] == "managed_record")["detail"]
        == "NO_MANAGED_SERVICE"
    )
    assert list(launcher.RUNTIME.iterdir()) == []
    assert out.stat().st_mode & 0o777 == 0o600


def test_failed_readiness_is_written_and_not_reported_pass(tmp_path, monkeypatch):
    launcher = fake_launcher(tmp_path, monkeypatch)
    (launcher.RUNTIME / "runtime.json").write_text('{"pid":123,"url":"http://127.0.0.1:1/"}')

    def fail(record, config, audit):
        audit.begin("process_identity_listener")
        raise RuntimeError("PID_MISMATCH")

    launcher.readiness = fail
    out = tmp_path / "failure.json"
    assert rehearsal_check(launcher, out) == 1
    report = json.loads(out.read_text())
    assert report["status"] == "FAIL"
    check = next(x for x in report["checks"] if x["check"] == "process_identity_listener")
    assert check["status"] == "FAIL" and "PID_MISMATCH" in check["detail"]
    assert (
        next(x for x in report["checks"] if x["check"] == "preset_catalog")["status"] == "UNKNOWN"
    )


def test_failed_preflight_still_produces_failure_receipt(tmp_path, monkeypatch):
    launcher = fake_launcher(tmp_path, monkeypatch)
    launcher.preflight = lambda: (_ for _ in ()).throw(RuntimeError("SOURCE_CHANGED"))
    out = tmp_path / "failure.json"
    assert rehearsal_check(launcher, out) == 1
    assert json.loads(out.read_text())["checks"][0]["status"] == "FAIL"


def test_output_rejects_assets_gt_symlink_alias_and_existing_file(tmp_path, monkeypatch):
    launcher = fake_launcher(tmp_path, monkeypatch)
    alias = tmp_path / "asset-alias"
    alias.symlink_to(launcher.ASSETS, target_is_directory=True)
    gt = tmp_path / "ground_truth"
    gt.mkdir()
    existing = tmp_path / "existing.json"
    existing.write_bytes(b"original")
    for out in [launcher.REPO / "x.json", alias / "x.json", gt / "x.json", existing]:
        with pytest.raises(ValueError):
            output_target(out, launcher)
    assert existing.read_bytes() == b"original"
    assert list(launcher.REPO.iterdir()) == []


def test_artifact_hash_mismatch_is_fail_and_missing_is_unknown(tmp_path, monkeypatch):
    import office_demo_backend as backend
    from office_rehearsal_check import artifact_hashes

    repo = tmp_path / "repo"
    bundle = tmp_path / "bundle"
    repo.mkdir()
    bundle.mkdir()
    (bundle / "manifest.json").write_text("{}")
    (bundle / "safe_inputs.json").write_text("{}")
    monkeypatch.setattr(
        backend,
        "preset_specs",
        lambda *args: (
            "person",
            [
                {
                    "scene_id": "person",
                    "bundle_path": bundle,
                    "config": {"safe_inputs_sha256": "wrong"},
                }
            ],
        ),
    )
    launcher = SimpleNamespace(
        REPO=repo,
        ASSETS=repo,
        EVIDENCE=repo,
        BUNDLE=None,
        PRESETS=repo / "presets",
        digest=lambda path: __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
    )
    audit = Audit()
    rows = artifact_hashes(launcher, audit)
    assert any(row["kind"] == "frozen_response" and row["sha256"] is None for row in rows)
    checks = list(audit.checks.values())
    assert any(x["status"] == "FAIL" and "ARTIFACT_HASH_MISMATCH" in x["detail"] for x in checks)
    assert any(x["status"] == "UNKNOWN" and x["detail"] == "ARTIFACT_UNAVAILABLE" for x in checks)
