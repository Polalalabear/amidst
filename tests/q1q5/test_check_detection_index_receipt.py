"""QT-25-T: synthetic checker/reader checks, never inference or formal acceptance."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from time import perf_counter

import pytest

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "tests/fixtures/detection_index_receipt/SYNTHETIC"
SCRIPT = ROOT / "scripts/check_detection_index_receipt.py"
KIT_ROOT = Path(os.environ.get("AMIDST_INDEX_KIT_ROOT", ROOT)).absolute()
if not SCRIPT.is_file():
    if os.getenv("AMIDST_REQUIRE_IMPL") == "1":
        pytest.fail("QT-25-T checker implementation missing", pytrace=False)
    pytest.skip("QT-25-T checker implementation missing", allow_module_level=True)
spec = importlib.util.spec_from_file_location("index_receipt_checker", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.fixture
def bundle(tmp_path):
    shutil.copytree(DATA / "valid", tmp_path / "SYNTHETIC")
    return tmp_path / "SYNTHETIC"


def load(root, filename):
    return json.loads((root / filename).read_bytes())


def write(root, filename, value):
    (root / filename).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def records(root):
    return [json.loads(line) for line in (root / "detection_index.records.jsonl").read_text().splitlines()]


def seal(root, index=None, rows=None):
    """Re-pin changed bytes so negatives exercise semantic checks, not stale SHA."""
    if index is not None or rows is not None:
        index = index or load(root, "detection_index.json")
        rows = rows if rows is not None else records(root)
        key = checker.canonical(index, ("index_id", "content_sha256", "records_ref", "records_file_sha256", "stats"))[:16]
        index["index_id"] = f"detidx:{index['scene_revision']}:{index['run_id']}:{key}"
        for row in rows:
            for ordinal, detection in enumerate(row["detections"] or []):
                detection["observation_id"] = f"obs:{key}:{row['camera_id']}:{row['frame_index']}:{ordinal}"
        raw = b"".join((json.dumps(r, sort_keys=True) + "\n").encode() for r in rows)
        (root / "detection_index.records.jsonl").write_bytes(raw)
        index["records_file_sha256"] = checker.sha(raw)
        index["content_sha256"] = checker.canonical(index, ("index_id", "content_sha256", "stats"))
        write(root, "detection_index.json", index)
    receipt = load(root, "receipt.json")
    for pin in receipt["pins"].values():
        pin["file_sha256"] = checker.sha((root / pin["path"]).read_bytes())
    write(root, "receipt.json", receipt)


def check(root, receipt="receipt.json", **kwargs):
    return checker.check_receipt(root / receipt, root, decoder="SYNTHETIC_TEST_ONLY_V1",
                                 kit_root=KIT_ROOT, **kwargs)


@pytest.fixture(scope="session", autouse=True)
def require_pinned_kit():
    try:
        checker.checked_kit(KIT_ROOT)
    except (ValueError, ImportError, OSError) as exc:
        message = f"fixed #127 kit unavailable; configure AMIDST_INDEX_KIT_ROOT/PYTHONPATH: {exc}"
        if os.getenv("AMIDST_REQUIRE_IMPL") == "1":
            pytest.fail(message, pytrace=False)
        pytest.skip(message)


@pytest.fixture(autouse=True)
def require_existing_reader():
    if os.getenv("AMIDST_REQUIRE_IMPL") == "1":
        try:
            __import__("amidst.q1q5.store")
        except ImportError as exc:
            pytest.fail(f"existing JsonRunStore implementation missing: {exc}", pytrace=False)
    else:
        pytest.importorskip("amidst.q1q5.store")


def test_positive_uses_real_reader_and_fixed_kit(bundle, monkeypatch):
    from amidst.q1q5.store import JsonRunStore
    original = JsonRunStore.load_detection_index
    calls = []
    def observed(self, ref):
        result = original(self, ref)
        calls.append(len(result.records))
        return result
    monkeypatch.setattr(JsonRunStore, "load_detection_index", observed)
    result = check(bundle)
    assert calls == [8]
    assert result["status"] == "PASS_SYNTHETIC_ONLY"
    assert result["kit_commit"] == "e1415f32a778f497bdd048d992440718bf0a9310"
    assert result["kit_checks_passed"] == 17
    assert result["authority_verified"] is False
    assert result["formal_acceptance"] == "NOT_EVALUATED"
    assert all(c == {"expected_frames": 4, "recorded_frames": 4, "inferred_frames": 4,
                     "not_evaluated_frames": 0} for c in result["coverage"].values())


@pytest.mark.parametrize("name", ["missing_pin", "coverage_mismatch", "estimated_timing", "mixed_run", "forbidden_key", "wrong_hash"])
def test_negative_receipt_fixtures(bundle, name):
    shutil.copyfile(DATA / "invalid" / (name + ".json"), bundle / "negative.json")
    with pytest.raises((checker.CheckError, ValueError)):
        check(bundle, "negative.json")


def test_default_and_unknown_decoder_fail_closed(bundle):
    for decoder in (None, "q-demo.unadopted-receipt.v99"):
        with pytest.raises(checker.Incomplete):
            checker.check_receipt(bundle / "receipt.json", bundle, decoder=decoder)


def make_gap(root, declared=True):
    rows = [r for r in records(root) if (r["camera_id"], r["frame_index"]) != ("CAM_B", 2)]
    index = load(root, "detection_index.json")
    index["sampling"]["per_camera"][1]["inferred_ranges_us"] = [[0, 400000], [600000, 800000]]
    receipt = load(root, "receipt.json")
    if declared:
        receipt["coverage"]["CAM_B"]["not_evaluated"] = [
            {"state": "NOT_EVALUATED", "frame_range": [2, 3], "reason": "SYNTHETIC absent source sample"}]
    write(root, "receipt.json", receipt)
    seal(root, index, rows)


def test_declared_shortfall_is_accounted_but_never_formal_acceptance(bundle):
    make_gap(bundle)
    result = check(bundle)
    assert result["coverage"]["CAM_B"] == {"expected_frames": 4, "recorded_frames": 3,
                                           "inferred_frames": 3, "not_evaluated_frames": 1}
    assert result["authority_verified"] is False
    assert result["formal_acceptance"] == "NOT_EVALUATED"
    assert {r["frame_state"] for r in records(bundle)} == {"INFERRED"}


def test_missing_frame_without_gap_declaration_rejected(bundle):
    make_gap(bundle, declared=False)
    with pytest.raises(checker.CheckError, match="NOT_EVALUATED"):
        check(bundle)


def test_coarse_ranges_cannot_claim_missing_frame_even_with_gap(bundle):
    make_gap(bundle)
    index = load(bundle, "detection_index.json")
    index["sampling"]["per_camera"][1]["inferred_ranges_us"] = [[0, 800000]]
    seal(bundle, index)
    with pytest.raises(checker.CheckError, match="overclaims"):
        check(bundle)


@pytest.mark.parametrize("state", ["MISSING", "NOT_INFERRED"])
def test_explicit_uninferred_states_require_receipt_gap(bundle, state):
    rows = records(bundle)
    rows[-2].update(frame_state=state, state_reason="SYNTHETIC unavailable sample", detections=None)
    if state == "MISSING": rows[-2]["rgb_file_sha256"] = None
    index = load(bundle, "detection_index.json")
    cam = index["sampling"]["per_camera"][1]
    cam["inferred_ranges_us"] = [[0, 400000], [600000, 800000]]
    cam["not_inferred"] = [{"range_us": [400000, 600000], "reason": "SYNTHETIC unavailable sample"}]
    receipt = load(bundle, "receipt.json")
    receipt["coverage"]["CAM_B"]["not_evaluated"] = [
        {"state": "NOT_EVALUATED", "frame_range": [2, 3], "reason": "SYNTHETIC unavailable sample"}]
    write(bundle, "receipt.json", receipt); seal(bundle, index, rows)
    result = check(bundle)
    assert result["coverage"]["CAM_B"]["recorded_frames"] == 4
    assert result["coverage"]["CAM_B"]["not_evaluated_frames"] == 1


def test_explicit_off_grid_rows_are_sampling_skips_not_new_wire_states(bundle):
    params = load(bundle, "parameter_set.json")
    params["parameters"][1]["value"] = 2
    params["content_sha256"] = checker.canonical(params, ("content_sha256", "parameter_set_id"))
    write(bundle, "parameter_set.json", params)
    index = load(bundle, "detection_index.json")
    index["sampling"]["stride_samples"] = 2
    for cam in index["sampling"]["per_camera"]:
        cam.update(stride_samples=2, index_interval_us=400000)
        cam["sampled_ranges_us"] = cam["inferred_ranges_us"] = [[0, 200000], [400000, 600000]]
    rows = records(bundle)
    for row in rows:
        if row["frame_index"] % 2:
            row.update(frame_state="NOT_SAMPLED", detections=None)
    seal(bundle, index, rows)
    result = check(bundle)
    assert all(c["recorded_frames"] == 4 and c["inferred_frames"] == 2
               and c["not_evaluated_frames"] == 0 for c in result["coverage"].values())


@pytest.mark.parametrize("change", ["empty_reason", "overlap", "outside", "spurious"])
def test_invalid_gap_declarations(bundle, change):
    make_gap(bundle)
    receipt = load(bundle, "receipt.json")
    gaps = receipt["coverage"]["CAM_B"]["not_evaluated"]
    if change == "empty_reason":
        gaps[0]["reason"] = ""
    elif change == "overlap":
        gaps.append(copy.deepcopy(gaps[0]))
    elif change == "outside":
        gaps[0]["frame_range"] = [2, 5]
    else:
        gaps[0]["frame_range"] = [1, 3]
    write(bundle, "receipt.json", receipt)
    with pytest.raises(checker.CheckError):
        check(bundle)


@pytest.mark.parametrize("role", ["index", "records", "detector_config", "hsv_config", "parameter_set", "run_manifest"])
def test_every_raw_byte_pin_is_checked(bundle, role):
    path = bundle / load(bundle, "receipt.json")["pins"][role]["path"]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(checker.CheckError, match="byte-pin mismatch"):
        check(bundle)


@pytest.mark.parametrize("kind", ["hsv", "parameters", "detector", "run", "rgb"])
def test_resealed_byte_pins_do_not_hide_binding_mismatch(bundle, kind):
    if kind == "hsv":
        value = load(bundle, "hsv_config.json"); value["strong_ratio"] = 0.7
        write(bundle, "hsv_config.json", value)
    elif kind == "parameters":
        value = load(bundle, "parameter_set.json"); value["parameters"][0]["value"] = 0.12
        value["content_sha256"] = checker.canonical(value, ("content_sha256", "parameter_set_id"))
        write(bundle, "parameter_set.json", value)
    elif kind == "detector":
        value = load(bundle, "detector_config.json"); value["model"] = "SYNTHETIC-OTHER"
        write(bundle, "detector_config.json", value)
    else:
        value = load(bundle, "run_manifest.json")
        value["run_id" if kind == "run" else "rgb_index_sha256"] = "RUN_Y" if kind == "run" else "0" * 64
        write(bundle, "run_manifest.json", value)
    seal(bundle)
    with pytest.raises(checker.CheckError):
        check(bundle)


@pytest.mark.parametrize("kind", ["cross_run", "timestamp", "outside", "duplicate", "not_evaluated_wire"])
def test_resealed_record_scope_and_wire_corruption_rejected(bundle, kind):
    rows = records(bundle)
    if kind == "cross_run": rows[-1]["frame_ref"] = "frame:RUN_Y:CAM_B:3"
    elif kind == "timestamp": rows[-1]["timestamp_us"] += 1
    elif kind == "outside": rows[-1]["frame_index"] = 4; rows[-1]["frame_ref"] = "frame:RUN_X:CAM_B:4"
    elif kind == "duplicate": rows.append(copy.deepcopy(rows[-1]))
    else: rows[-1]["frame_state"] = "NOT_EVALUATED"; rows[-1]["detections"] = None
    seal(bundle, rows=rows)
    with pytest.raises(ValueError):
        check(bundle)


@pytest.mark.parametrize("key", ["GT", "ground_truth", "trajectory", "renderer_trajectory", "visibility", "depth", "event_script"])
def test_forbidden_index_keys_rejected_even_with_valid_hashes(bundle, key):
    index = load(bundle, "detection_index.json")
    index["provenance"][key] = []
    seal(bundle, index)
    with pytest.raises(ValueError):
        check(bundle)


def test_gt_read_false_allowed_but_true_rejected(bundle):
    assert check(bundle)["status"] == "PASS_SYNTHETIC_ONLY"
    run = load(bundle, "run_manifest.json"); run["provenance"]["gt_read"] = True
    write(bundle, "run_manifest.json", run); seal(bundle)
    with pytest.raises(checker.CheckError, match="gt_read=false"):
        check(bundle)


@pytest.mark.parametrize("value", [True, -1, "estimated", float("inf")])
def test_invalid_timing_values_rejected(value):
    timings = {stage: {"seconds": None, "source": "NOT_MEASURED", "reason": "not run"} for stage in checker.STAGES}
    timings["forward"] = {"seconds": value, "source": "MEASURED", "reason": None}
    with pytest.raises(checker.CheckError): checker.validate_timings(timings)


def test_real_measured_local_parse_time_or_null_reason(bundle):
    receipt = load(bundle, "receipt.json")
    start = perf_counter(); load(bundle, "detection_index.json"); elapsed = perf_counter() - start
    receipt["timings"]["read"] = {"seconds": elapsed, "source": "MEASURED", "reason": None}
    write(bundle, "receipt.json", receipt)
    assert check(bundle)["status"] == "PASS_SYNTHETIC_ONLY"
    receipt["timings"]["forward"]["reason"] = None
    write(bundle, "receipt.json", receipt)
    with pytest.raises(checker.CheckError, match="null timing needs a reason"): check(bundle)


def test_symlink_and_path_escape_rejected(bundle):
    original = bundle / "hsv_config.json"
    original.rename(bundle / "hsv_original.json")
    original.symlink_to("hsv_original.json")
    with pytest.raises(checker.CheckError, match="symlink"): check(bundle)
    with pytest.raises(checker.CheckError, match="unsafe"): checker.read_relative(bundle, "../escape.json")


def test_duplicate_receipt_json_key_rejected(bundle):
    path = bundle / "receipt.json"
    path.write_text(path.read_text().replace('"fixture_role": "SYNTHETIC",', '"fixture_role": "SYNTHETIC", "fixture_role": "SYNTHETIC",'))
    with pytest.raises(checker.CheckError, match="duplicate"): check(bundle)


def test_wrong_kit_source_fails_closed(bundle, tmp_path):
    fake = tmp_path / "kit"; fake.mkdir()
    with pytest.raises(checker.CheckError): checker.checked_kit(fake)


def large_bundle(root):
    count = 1002
    template = records(root)[0]
    run = load(root, "run_manifest.json"); run["sampling"].update(duration_s=200.4, sample_count_per_camera=count)
    write(root, "run_manifest.json", run)
    index = load(root, "detection_index.json")
    for cam in index["sampling"]["per_camera"]:
        cam["sampled_ranges_us"] = cam["inferred_ranges_us"] = [[0, count * 200000]]
    rows = []
    for camera in run["camera_ids"]:
        for frame in range(count):
            row = copy.deepcopy(template)
            row.update(camera_id=camera, frame_index=frame, timestamp_us=frame*200000,
                       frame_ref=f"frame:RUN_X:{camera}:{frame}", detections=[])
            rows.append(row)
    receipt = load(root, "receipt.json")
    for cam in receipt["coverage"].values(): cam["expected_frames"] = count
    write(root, "receipt.json", receipt); seal(root, index, rows)
    return rows, template


def test_fixed_kit_checks_records_after_2000_as_well(bundle):
    rows, template = large_bundle(bundle)
    assert check(bundle)["kit_checks_passed"] == 34
    rows[-1]["detections"] = copy.deepcopy(template["detections"])
    rows[-1]["detections"][0]["score"] = 0.01
    seal(bundle, rows=rows)
    with pytest.raises(checker.CheckError, match="RECORDS_SCORE_FLOOR"):
        check(bundle)


def test_cli_positive_and_fail_closed_default(bundle):
    args = [sys.executable, str(SCRIPT), "--receipt", str(bundle / "receipt.json"), "--index-root", str(bundle)]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "INCOMPLETE"
    result = subprocess.run(args + ["--decoder", "SYNTHETIC_TEST_ONLY_V1", "--kit-root", str(KIT_ROOT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["authority_verified"] is False
