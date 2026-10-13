"""Real fixed-module workers, separate outputs, frozen source and rejection boundaries."""

import copy
import hashlib
import json
import sqlite3
import subprocess
import time
from pathlib import Path

import pytest

from amidst.engineering.access import digest
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.run_jobs import (
    ACTIVE,
    SOURCE_FILES,
    SingleSyntheticRunManager,
    configured_context,
    encode,
    validate_source,
)
from amidst.workbench.run_worker import execute
from amidst.workbench.scenes import load_synthetic_lab

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def source_scene():
    return load_synthetic_lab(ROOT / "data/engineering/local_run/simulation_v2")


@pytest.fixture
def manager(tmp_path, source_scene):
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    reviews = ReviewStore(tmp_path / "review.sqlite3", {
        source_scene.scene_id: {k: source_scene.snapshot()[k] for k in keys}})
    value = SingleSyntheticRunManager(source_scene, reviews, tmp_path / "jobs")
    yield value
    value.close()


def wait(manager, job, expected="COMPLETED"):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        current = manager.get(manager.scene.scene_id, job["job_ref"])
        if current["state"] not in ACTIVE:
            assert current["state"] == expected, current
            return current
        time.sleep(0.03)
    pytest.fail("real worker did not finish in bounded test window")


def start(manager, key="test", version=0, parameters=None):
    return manager.start(manager.scene.scene_id, version, parameters or {}, key)


def publish(manager, object_id, changes):
    scene_id = manager.scene.scene_id
    version = manager.reviews.state(scene_id)["current_version"]
    draft = manager.reviews.save_draft(scene_id, object_id, changes, version,
                                       "local-test-operator", "synthetic fixture only")
    validation = manager.reviews.validate_draft(draft["draft_id"])
    assert validation["valid"], validation
    return manager.reviews.publish_draft(draft["draft_id"], "local-test-operator",
                                          "synthetic fixture only", version)


def source_hashes(manager):
    root = manager.source_root
    paths = [root / name for name in SOURCE_FILES]
    paths.extend(root / f.relative_path for f in manager.scene.service.frames.values())
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def test_real_workers_repeat_content_and_keep_source_immutable(manager):
    before = source_hashes(manager)
    a = wait(manager, start(manager, "first"))
    b = wait(manager, start(manager, "second"))
    assert a["new_run_id"] != b["new_run_id"]
    assert a["job_ref"] != b["job_ref"]
    first = manager.result(manager.scene.scene_id, a["job_ref"])
    second = manager.result(manager.scene.scene_id, b["job_ref"])
    assert first["deterministic_sha256"] == second["deterministic_sha256"]
    assert first["config_sha256"] == second["config_sha256"]
    assert first["observations"][0]["observation_ref"] != (
        second["observations"][0]["observation_ref"])
    assert first["comparison"]["new"]["measurements"] > 0
    assert first["comparison"]["new"]["candidates"] > 0
    assert first["events"] and first["events"][0]["uncertainty"]
    assert first["view_only"] and not first["formal_phase1_acceptance"]
    assert first["source_run_id"] == manager.scene.run_id
    assert first["source_sha256"] == manager.scene.source_hash
    assert a["progress"] == {"completed": 4, "total": 4}
    assert a["started_at"] and a["finished_at"]
    assert source_hashes(manager) == before
    encoded = encode(first)
    assert str(manager.source_root) not in encoded
    assert "relative_path" not in encoded and "ground_truth" not in encoded
    assert "GT" not in encoded
    assert {p.name for p in (manager.output_root / a["job_ref"]).iterdir()} == {
        "configuration.json", "perception.json", "inference.json", "result.json", "receipt.json"}


def test_idempotency_and_bounded_active_job(manager):
    a = start(manager)
    assert start(manager)["job_ref"] == a["job_ref"]
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        start(manager, parameters={"max_speed_m_s": 2})
    with pytest.raises(ValueError, match="RUN_JOB_ALREADY_ACTIVE"):
        start(manager, "parallel")
    wait(manager, a)
    assert start(manager)["job_ref"] == a["job_ref"]


def test_actual_subprocess_cancel_never_publishes_result(manager):
    a = start(manager)
    cancelled = manager.cancel(manager.scene.scene_id, a["job_ref"])
    assert cancelled["state"] in {"CANCEL_REQUESTED", "CANCELLED"}
    terminal = wait(manager, a, "CANCELLED")
    assert not terminal["result_available"]
    with pytest.raises(ValueError, match="RUN_RESULT_UNAVAILABLE"):
        manager.result(manager.scene.scene_id, a["job_ref"])
    wait(manager, start(manager, "after-cancel"))


def test_actual_worker_source_failure_has_no_completed_result(manager, monkeypatch):
    original = subprocess.Popen

    def corrupt_then_launch(argv, **kwargs):
        with sqlite3.connect(manager.db_path) as db:
            ref = argv[-1]
            row = db.execute("SELECT spec FROM jobs WHERE job_ref=?", (ref,)).fetchone()
            spec = json.loads(row[0])
            spec["source_files"]["static_context.json"] = "0" * 64
            db.execute("UPDATE jobs SET spec=?,spec_hash=? WHERE job_ref=?",
                       (encode(spec), digest(spec), ref))
        return original(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", corrupt_then_launch)
    a = wait(manager, start(manager), "FAILED")
    assert a["failure_code"] == "SOURCE_CHANGED"
    assert not a["result_available"]
    assert not (manager.output_root / a["job_ref"]).exists()


def test_worker_start_failure(manager, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("private local path must never become public")

    monkeypatch.setattr(subprocess, "Popen", unavailable)
    a = start(manager)
    assert a["state"] == "FAILED" and a["failure_code"] == "WORKER_START_FAILED"
    assert "private" not in encode(a)


def test_shutdown_and_restart_preserve_history_not_partial_completion(manager):
    a = start(manager)
    manager.close()
    reopened = SingleSyntheticRunManager(manager.scene, manager.reviews, manager.output_root)
    try:
        row = reopened.get(manager.scene.scene_id, a["job_ref"])
        assert row["state"] == "INTERRUPTED"
        assert row["failure_code"] == "SERVER_SHUTDOWN_INTERRUPTED"
        assert not row["result_available"]
        wait(reopened, start(reopened, "after-restart"))
    finally:
        reopened.close()


def test_recover_crash_state_as_interrupted(manager):
    a = wait(manager, start(manager))
    manager.close()
    with sqlite3.connect(manager.db_path) as db:
        db.execute("UPDATE jobs SET state='RUNNING' WHERE job_ref=?", (a["job_ref"],))
    reopened = SingleSyntheticRunManager(manager.scene, manager.reviews, manager.output_root)
    try:
        row = reopened.get(manager.scene.scene_id, a["job_ref"])
        assert row["state"] == "INTERRUPTED"
        assert row["failure_code"] == "SERVER_RESTART_INTERRUPTED"
        with pytest.raises(ValueError, match="RUN_RESULT_UNAVAILABLE"):
            reopened.result(manager.scene.scene_id, a["job_ref"])
    finally:
        reopened.close()


def test_published_region_overlay_changes_new_context_only(manager):
    original = manager.scene.snapshot()
    region = next(r for r in original["objects"] if r["object_id"] == "region:west")
    changed = copy.deepcopy(region["geometry"])
    for point in changed["points"]:
        if point[0] == 4:
            point[0] = 3.5
    published = publish(manager, "region:west", {"geometry": changed})
    result = manager.result(manager.scene.scene_id,
        wait(manager, start(manager, version=published["version"]))["job_ref"])
    assert result["annotation_version"] == 1
    config_path = manager.output_root / result["job_ref"] / "configuration.json"
    config = json.loads(config_path.read_bytes())
    west = next(r for r in config["effective_context"]["regions"] if r["region_id"] == "west")
    assert west["bounds_xy_m"] == [0, 0, 3.5, 4]
    assert config["effective_context"]["context_sha256"] != manager._context.context_sha256
    assert manager.scene.snapshot() == original
    assert result["overlay_changes"][0]["effect"] == "CONFIGURED_STATIC_CONTEXT"
    # A saved job keeps version 1 even when the current annotation later becomes version 2.
    publish(manager, "region:west", {"label": "West label"})
    assert manager.result(manager.scene.scene_id, result["job_ref"])["annotation_version"] == 1


def test_affine_overlay_and_unsupported_semantics(manager):
    rows = manager.scene.snapshot()["objects"]
    changed = copy.deepcopy(rows)
    camera = next(r for r in changed if r["kind"] == "CAMERA")
    camera["properties"]["ground_to_pixel"][0][2] += 1
    context, changes = configured_context(manager._context, rows, changed)
    assert context.calibrations[0].affine_ground_to_pixel != (
        manager._context.calibrations[0].affine_ground_to_pixel)
    assert changes[0]["field"] == "properties.ground_to_pixel"
    changed = copy.deepcopy(rows)
    changed[0]["semantic"] = "WALL"
    with pytest.raises(ValueError, match="UNSUPPORTED_OVERLAY_FIELD"):
        configured_context(manager._context, rows, changed)
    changed = copy.deepcopy(rows)
    changed[1]["geometry"]["points"][1][0] -= 0.1
    with pytest.raises(ValueError, match="UNSUPPORTED_OVERLAY_GEOMETRY"):
        configured_context(manager._context, rows, changed)


@pytest.mark.parametrize("parameters", [
    {"output_path": "/private/tmp/escape"}, {"role": "research"}, {"graph_search": {}},
    {"max_speed_m_s": True}, {"max_speed_m_s": float("nan")}, {"max_speed_m_s": 100},
])
def test_caller_overspec_and_invalid_parameters(manager, parameters):
    with pytest.raises(ValueError, match="UNSUPPORTED_RUN_PARAMETERS|INVALID_RUN_PARAMETER"):
        start(manager, parameters=parameters)


def test_scope_version_and_owner_guards(manager):
    with pytest.raises(ValueError, match="RUN_SCENE_SCOPE_DENIED"):
        manager.start("local-camera", 0, {}, "foreign")
    with pytest.raises(ValueError, match="RUN_JOB_SCOPE_DENIED"):
        manager.get(manager.scene.scene_id, "../escape")
    with pytest.raises(ValueError, match="ANNOTATION_VERSION_UNAVAILABLE"):
        start(manager, version=99)
    with pytest.raises(ValueError, match="ANNOTATION_VERSION_INVALID"):
        start(manager, version=True)
    with pytest.raises(ValueError, match="RUN_MANAGER_ALREADY_ACTIVE"):
        SingleSyntheticRunManager(manager.scene, manager.reviews, manager.output_root)
    with pytest.raises(ValueError, match="RUN_OUTPUT_SCOPE_DENIED"):
        SingleSyntheticRunManager(manager.scene, manager.reviews, manager.source_root / "forbidden")


def test_changed_registered_source_bytes_fail_closed_without_writing_source(manager, monkeypatch):
    a = wait(manager, start(manager))
    with sqlite3.connect(manager.db_path) as db:
        spec = json.loads(db.execute("SELECT spec FROM jobs WHERE job_ref=?",
                                     (a["job_ref"],)).fetchone()[0])
    original = Path.read_bytes
    target = manager.source_root / "static_context.json"

    def changed(path):
        return original(path) + b"changed" if path == target else original(path)

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        validate_source(spec)
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        manager.result(manager.scene.scene_id, a["job_ref"])


def test_receipt_and_raw_artifact_tamper_detected(manager):
    a = wait(manager, start(manager))
    output = manager.output_root / a["job_ref"]
    receipt = output / "receipt.json"
    raw = output / "perception.json"
    original = receipt.read_bytes()
    raw.chmod(0o644)
    raw.write_bytes(raw.read_bytes() + b"\n")
    changed = json.loads(original)
    changed["artifacts"]["perception.json"] = hashlib.sha256(raw.read_bytes()).hexdigest()
    receipt.chmod(0o644)
    receipt.write_text(encode(changed))
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        manager.result(manager.scene.scene_id, a["job_ref"])


def test_no_truth_eval_render_files_enter_source_allowlist(manager, monkeypatch):
    reads = []
    original = Path.read_bytes

    def record(path):
        reads.append(path)
        assert not any(part in {"ground_truth", "evaluation", "recipe.json"} for part in path.parts)
        assert path.suffix != ".blend"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", record)
    a = wait(manager, start(manager))
    manager.result(manager.scene.scene_id, a["job_ref"])
    assert reads
    assert manager.context(manager.scene.scene_id)["max_active_jobs"] == 1
    assert manager.list(manager.scene.scene_id)["limit"] == 100
    assert not manager.list(manager.scene.scene_id)["truncated"]


def test_actual_pipeline_read_audit_rejects_any_truth_or_generator_access(manager, monkeypatch):
    # Run the identical worker entry point under a read audit, in addition to
    # the real background process tests. No producer or terminal state is mocked.
    def unavailable(*args, **kwargs):
        raise OSError("test harness retains queued spec without launching")

    monkeypatch.setattr(subprocess, "Popen", unavailable)
    job = start(manager)
    with sqlite3.connect(manager.db_path) as db:
        db.execute("UPDATE jobs SET state='QUEUED',phase='QUEUED' WHERE job_ref=?",
                   (job["job_ref"],))
    reads = []
    original = Path.read_bytes
    allowed = set(source_hashes(manager))

    def audit(path):
        reads.append(path)
        if path.suffix != ".py":
            assert path in allowed, path
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", audit)
    execute(manager.db_path, job["job_ref"])
    assert manager.get(manager.scene.scene_id, job["job_ref"])["state"] == "COMPLETED"
    assert len({p for p in reads if p.suffix == ".png"}) == 102
