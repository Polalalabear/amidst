"""Selected detections project into the optional workbench estimate contract."""

import copy
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
try:
    from demo_dependency_config import configuration, owned_path, resolve_job
    from demo_estimate import estimate_track
    from run_cross_camera_demo import load_run, loads, read_pin
    from serve_demo_integration import Demo
finally:
    sys.path.pop(0)

CATALOG = {
    "cameras": [
        {
            "camera_id": "top",
            "camera_to_world": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 10], [0, 0, 0, 1]],
            "fx": 100,
            "fy": 100,
            "cx": 0,
            "cy": 0,
            "width": 100,
            "height": 100,
        }
    ]
}


def fixture():
    records = [
        {
            "timestamp_us": t,
            "camera_id": "top",
            "detections": [
                {
                    "observation_id": "one",
                    "bbox_xyxy_px": [5, 0, 15, 20],
                }
            ],
        }
        for t in (0, 1_000_000)
    ]
    response = {
        "as_of_us": 500_000,
        "sightings": [{"camera_id": "top", "observation_ids": ["one"]}],
        "single_view": [{"kind": "ON_CAMERA", "camera_id": "top", "range_us": [0, 500_000]}],
    }
    return records, response


def estimate(records, response, catalog=CATALOG):
    return estimate_track(
        records,
        response,
        catalog,
        catalog_sha256="a" * 64,
        index_sha256="b" * 64,
        clock_id="source-clock",
    )


def test_foot_projection_last_position_and_speed_radius_never_read_future():
    records, response = fixture()
    before = copy.deepcopy(records)
    first = estimate(records, response)
    assert first["est_xy"] == pytest.approx([1, -2])
    assert first["uncertainty_m"] == 1
    assert first["last_observed_us"] == 0
    records[1]["detections"][0]["bbox_xyxy_px"] = [90, 90, 99, 99]
    assert estimate(records, response) == first
    assert records[0] == before[0]
    response["as_of_us"] = 2_000_000
    response["single_view"][0]["range_us"][1] = 2_000_000
    assert estimate(records, response)["last_observed_us"] == 1_000_000


def test_missing_calibration_and_ambiguous_selection_remain_unknown():
    records, response = fixture()
    assert estimate(records, response, None)["reason"] == "CALIBRATION_MISSING"
    records[0]["detections"].append({"observation_id": "two", "bbox_xyxy_px": [30, 0, 40, 20]})
    response["sightings"][0]["observation_ids"].append("two")
    assert estimate(records, response)["reason"] == "AMBIGUOUS_SELECTED_OBSERVATIONS"


def test_projection_reads_only_explicit_observation_fields_and_preserves_output_hash():
    records, response = fixture()

    class Bounded(dict):
        def __getitem__(self, key):
            assert key in {
                "timestamp_us",
                "camera_id",
                "detections",
                "observation_id",
                "bbox_xyxy_px",
            }
            return super().__getitem__(key)

    record = Bounded(records[0], gt_private="sentinel", visibility="sentinel")
    record["detections"] = [Bounded(record["detections"][0], actor_id="sentinel", depth="sentinel")]
    result = estimate([record], response)
    assert not any(
        word in json.dumps(result) for word in ("sentinel", "actor_id", "visibility", "depth")
    )
    from types import SimpleNamespace

    from amidst.q1q5.store import canonical_hash

    demo = object.__new__(Demo)
    demo.calibrations = {("scene", "run"): (CATALOG, "a" * 64)}
    demo.api = SimpleNamespace(
        runs={
            ("scene", "run"): SimpleNamespace(
                catalog={"scene_id": "scene", "run_id": "run"},
                bindings=SimpleNamespace(
                    index=SimpleNamespace(records=[record]),
                    index_sha256="b" * 64,
                    clock=SimpleNamespace(clock_id="source-clock"),
                ),
            )
        }
    )
    doc = demo.with_estimate(("scene", "run"), dict(response))
    assert doc["estimate"] == result
    assert doc["output_sha256"] == canonical_hash(doc, exclude=("output_sha256", "stats"))


def test_recorded_a4_b4_projections_from_pinned_observations():
    if "AMIDST_DEMO_HOME" not in os.environ:
        pytest.skip("AMIDST_DEMO_HOME required for the owned recorded observations")
    from collections import Counter

    from amidst.q1q5.cross_camera_demo import Parameters, response

    config, root = configuration()
    job = resolve_job(
        loads(
            read_pin(
                {
                    "path": str(owned_path(root, config["cross_camera_job"])),
                    "sha256": config["cross_camera_job_sha256"],
                }
            )
        ),
        root,
    )
    graph = loads(read_pin(job["graph"]))
    params = Parameters(**job["parameters"])
    bundle = (
        owned_path(root, config["artifacts_root"])
        / "r004-cx7r-20261104-01a19f8b/bundle/safe_bundle"
    )
    catalog_pin = job["graph_binding"]["catalog_sha256"]
    catalog = loads(
        read_pin({"path": str(bundle / "provenance/camera_catalog.json"), "sha256": catalog_pin})
    )
    transitions = {
        (t["from_camera_id"], t["to_camera_id"]): t["transition_id"] for t in graph["transitions"]
    }
    receipt = {"source_job_sha256": config["cross_camera_job_sha256"], "runs": []}
    for spec in job["runs"]:
        tracks, clock, index = load_run(spec, graph, job["graph_binding"], params)
        records = [loads(row) for row in read_pin(spec["inputs"]["records"]).splitlines()]
        estimates = []
        for tick in range(clock["source_duration_us"] // 200_000):
            stamp = (tick + 1) * 200_000
            doc, _, _ = response(
                tracks,
                transitions,
                as_of_us=stamp,
                parameters=params,
                clock_mapping_sha256=spec["inputs"]["clock"]["sha256"],
            )
            result = estimate_track(
                records,
                doc,
                catalog,
                catalog_sha256=catalog_pin,
                index_sha256=index["content_sha256"],
                clock_id=clock["clock_id"],
            )
            estimates.append({"t_us": stamp, **result})
        counts = Counter("UNKNOWN" if e["est_xy"] == "UNKNOWN" else "INFERRED" for e in estimates)
        assert counts["INFERRED"] > 0
        assert all(e.get("last_observed_us", e["t_us"]) <= e["t_us"] for e in estimates)
        receipt["runs"].append(
            {
                "label": spec["label"],
                "run_id": index["run_id"],
                "counts": dict(counts),
                "estimates": estimates,
            }
        )
    output = os.environ.get("AMIDST_TEST_EVIDENCE")
    if output:
        (Path(output) / "projection-replay.json").write_text(json.dumps(receipt, indent=2) + "\n")


def test_api_saves_the_estimate_with_its_final_response_hash():
    from test_api import TOKEN, api_fixture, authorize

    api, run = api_fixture()
    api.track_estimator = lambda *_: {"est_xy": [1, 2], "uncertainty_m": 0.4}
    result = api.call(
        "q_core_track",
        {
            "schema_version": "q-core.track-request.v1",
            "session_ref": TOKEN,
            "scene_id": run.catalog["scene_id"],
            "run_id": run.catalog["run_id"],
            "feature": {"class_label": "person", "color_label": None},
            "region_ids": [],
            "time": None,
            "playback_now_us": run.bindings.clock.duration_us,
        },
        authorize,
    )
    assert result["estimate"] == {"est_xy": [1, 2], "uncertainty_m": 0.4}
    assert api.responses[(TOKEN, result["output_sha256"])]["response"] == result
