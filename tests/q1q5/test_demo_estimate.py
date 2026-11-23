"""Selected detections project into the optional workbench estimate contract."""

import copy
import json
import os
import sys
from pathlib import Path

import pytest
from test_bootstrap_class_counts import recorded_demo  # noqa: F401

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
    records[1]["detections"][0]["bbox_xyxy_px"] = [90, 90, 95, 95]
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
    assert doc["display_estimate"] == result
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
    records, response = fixture()
    expected = estimate(records, response)
    api.track_estimator = lambda *_: expected
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
    assert result["display_estimate"] == expected
    assert "estimate" not in result
    assert api.responses[(TOKEN, result["output_sha256"])]["response"] == result


@pytest.mark.parametrize("label", ["B-05", "A4-1", "B4-1", "r005"])
def test_normal_recorded_entry_supplies_a_bound_estimate_or_unknown(label, request):
    demo = request.getfixturevalue("recorded_demo")
    run = next(r for r in demo.api.runs.values() if r.title.startswith(label + " "))
    token = demo.call("session", {"role": "demo"})["session_ref"]
    result = demo.call(
        "q_core_track",
        {
            "schema_version": "q-core.track-request.v1",
            "session_ref": token,
            "scene_id": run.catalog["scene_id"],
            "run_id": run.catalog["run_id"],
            "feature": {"class_label": "person", "color_label": None},
            "region_ids": [],
            "time": None,
            "playback_now_us": run.bindings.clock.duration_us,
        },
    )
    estimate = result["display_estimate"]
    if label in ("B-05", "r005"):
        assert estimate["reason"] == "CALIBRATION_MISSING"
    else:
        assert len(estimate["est_xy"]) == 2
        assert estimate["source_clock_id"] == run.bindings.clock.clock_id
        assert estimate["source_index_sha256"] == run.bindings.index_sha256
        assert estimate["uncertainty_m"] >= 0


def test_bottom_clipped_foot_is_unknown_even_after_an_earlier_projection():
    records, response = fixture()
    records[1]["detections"][0]["bbox_xyxy_px"] = [5, 0, 15, 99]
    response["as_of_us"] = 2_000_000
    response["single_view"][0]["range_us"][1] = 2_000_000
    assert estimate(records, response)["reason"] == "FOOT_TRUNCATED_AT_FRAME_BOTTOM"


def test_unassociated_candidate_in_same_camera_does_not_make_selected_point_ambiguous():
    records, response = fixture()
    records[0]["detections"].append({"observation_id": "other", "bbox_xyxy_px": [30, 0, 40, 20]})
    response["sightings"].append(
        {"camera_id": "top", "observation_ids": ["other"], "selected_for_single_view": False}
    )
    assert estimate(records, response)["est_xy"] == pytest.approx([1, -2])


def latest_fixture():
    records, response = fixture()
    response["as_of_us"] = 2_000_000
    response["single_view"][0]["range_us"][1] = 2_000_000
    return records, response


def horizon_catalog():
    catalog = copy.deepcopy(CATALOG)
    catalog["cameras"][0]["camera_to_world"] = [
        [1, 0, 0, 0],
        [0, 0, -1, 0],
        [0, 1, 0, 10],
        [0, 0, 0, 1],
    ]
    return catalog


def test_foot_within_four_pixel_margin_is_unknown():
    records, response = latest_fixture()
    records[1]["detections"][0]["bbox_xyxy_px"][3] = CATALOG["cameras"][0]["height"] - 3
    assert estimate(records, response)["reason"] == "FOOT_TRUNCATED_AT_FRAME_BOTTOM"


def test_latest_above_horizon_observation_does_not_reuse_earlier_point():
    records, response = latest_fixture()
    catalog = horizon_catalog()
    assert isinstance(estimate(records[:1], response, catalog)["est_xy"], list)
    records[1]["detections"][0]["bbox_xyxy_px"] = [5, -40, 15, -20]
    result = estimate(records, response, catalog)
    assert result["est_xy"] == "UNKNOWN"
    assert result["reason"] == "GROUND_PROJECTION_UNDEFINED"
    assert "last_observed_us" not in result


def test_one_undefined_observation_at_latest_time_invalidates_valid_peer():
    records, response = latest_fixture()
    records[1]["detections"].append(
        {"observation_id": "undefined", "bbox_xyxy_px": [5, -40, 15, -20]}
    )
    response["sightings"][0]["observation_ids"].append("undefined")
    result = estimate(records, response, horizon_catalog())
    assert result["reason"] == "GROUND_PROJECTION_UNDEFINED"
    assert result["est_xy"] == "UNKNOWN"


@pytest.mark.parametrize("invalid", ["bbox_nan", "ground_none", "ground_infinite"])
def test_latest_invalid_projection_is_recorded_as_undefined(invalid, monkeypatch):
    records, response = latest_fixture()
    if invalid == "bbox_nan":
        records[1]["detections"][0]["bbox_xyxy_px"][0] = float("nan")
    else:
        from demo_estimate import Projector

        monkeypatch.setattr(
            Projector, "ground", lambda *_: None if invalid == "ground_none" else [float("inf"), 0]
        )
    assert estimate(records, response)["reason"] == "GROUND_PROJECTION_UNDEFINED"


def test_clipped_foot_reason_wins_over_undefined_projection():
    records, response = latest_fixture()
    records[1]["detections"] = [
        {"observation_id": "one", "bbox_xyxy_px": [5, -40, 15, -20]},
        {"observation_id": "clipped", "bbox_xyxy_px": [5, 0, 15, 97]},
    ]
    response["sightings"][0]["observation_ids"].append("clipped")
    assert (
        estimate(records, response, horizon_catalog())["reason"] == "FOOT_TRUNCATED_AT_FRAME_BOTTOM"
    )


def test_no_selected_observation_reason_is_not_used_for_projection_failure():
    records, response = fixture()
    response["sightings"] = []
    assert estimate(records, response)["reason"] == "NO_PROJECTABLE_SELECTED_OBSERVATION"


def test_display_estimate_schema_covers_values_unknowns_and_optional_attachment():
    from test_api import TOKEN, api_fixture, authorize
    from test_service_agent_track import schema_ok

    from amidst.q1q5.store import canonical_hash

    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "docs/contracts/schemas/q-core.search-track.v1.schema.json"
        ).read_text()
    )
    definition = schema["$defs"]["displayEstimate"]
    assert schema["$defs"]["trackResponse"]["properties"]["display_estimate"] == {
        "$ref": "#/$defs/displayEstimate"
    }
    assert "display_estimate" not in schema["$defs"]["trackResponse"]["required"]
    records, response = fixture()
    known = estimate(records, response)
    assert schema_ok(known, definition)
    assert known["schema_version"] == "q-core.display-estimate.v1"
    for reason in schema["$defs"]["displayEstimate"]["properties"]["reason"]["enum"]:
        assert schema_ok(
            {
                "schema_version": "q-core.display-estimate.v1",
                "est_xy": "UNKNOWN",
                "uncertainty_m": "UNKNOWN",
                "reason": reason,
            },
            definition,
        )
    assert not schema_ok(dict(known, schema_version="q-core.blind-estimate.v1"), definition)
    assert not schema_ok(
        {
            "schema_version": "q-core.display-estimate.v1",
            "est_xy": "UNKNOWN",
            "uncertainty_m": "UNKNOWN",
            "reason": "OTHER",
        },
        definition,
    )
    api, run = api_fixture()
    payload = {
        "schema_version": "q-core.track-request.v1",
        "session_ref": TOKEN,
        "scene_id": run.catalog["scene_id"],
        "run_id": run.catalog["run_id"],
        "feature": {"class_label": "person", "color_label": None},
        "region_ids": [],
        "time": None,
        "playback_now_us": run.bindings.clock.duration_us,
    }
    plain = api.call("q_core_track", payload, authorize)
    track_schema = schema["$defs"]["trackResponse"]
    assert schema_ok(plain, track_schema)
    assert "display_estimate" not in plain

    def attach(_run, doc):
        assert "display_estimate" not in doc
        assert doc == plain
        return known

    api.track_estimator = attach
    augmented = api.call("q_core_track", payload, authorize)
    assert schema_ok(augmented, track_schema)
    assert augmented["display_estimate"] == known
    assert augmented["blind"] == plain["blind"]
    assert augmented["output_sha256"] != plain["output_sha256"]
    assert augmented["output_sha256"] == canonical_hash(
        augmented, exclude=("output_sha256", "stats")
    )
    api.track_estimator = None
    assert api.call("q_core_track", payload, authorize) == plain
