"""Synthetic declared footprints (task K8a, contract v1.2, D23).

``SYNTHETIC_DECLARED_FOOTPRINT`` is accepted only for a scene whose configuration
entry says ``data_origin: "SYNTHETIC"`` (K1) or when the trusted caller converts with
``data_origin="SYNTHETIC"`` (K5). Real scenes keep their v1.1 behaviour and output
hashes: the pinned values below were computed on ``claude/k1-restricted`` @ 74c6ace
(engine blob 491cc94, retrieval_evidence blob 87d83f2) before this change.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from test_blind_hypothesis import (
    SCENE,
    _config,
    _gap_times,
    _negative,
    _obstacle_request,
    _obstacle_room,
    _run,
)
from test_blind_hypothesis_pruning import (
    NORTH_AISLE,
    SOUTH_AISLE,
    WINDOW,
    _candidates,
    _evaluations,
    _mismatch_cases,
    _rerun,
    _retrieval,
    _visibility,
)

from amidst.blind_hypothesis import (
    HypothesisRequestError,
    canonical_sha256,
    generate_blind_hypotheses,
    parse_config,
)
from amidst.blind_hypothesis.engine import (
    REQUIRED_VISIBILITY_METHOD,
    SYNTHETIC_VISIBILITY_METHOD,
)
from amidst.blind_hypothesis.retrieval_evidence import negative_evidence_from_retrieval

ROOT = Path(__file__).resolve().parents[2]
K8_CONFIG_PATH = ROOT / "configs" / "k8_synthetic_blind_hypothesis_v1.json"
REAL_CONFIG_PATH = ROOT / "configs" / "blind_hypothesis_v1.json"
SYN = SYNTHETIC_VISIBILITY_METHOD
K8_DETECTOR = {
    "producer": "synthetic-k8",
    "version": "v1",
    "difference_threshold": 30,
    "min_pixels": 28,
}

# Real-path output hashes on 74c6ace (see module docstring).
PINNED_K1 = {
    "first": "0890e2aae9924d748943d8ed9aceebd397972da7edc09783d35532e3881205d0",
    "rerun_south": "e78dc6d5618331eeef548bce084a25d72871a6e4601f8924ed83927f41fda4f3",
    "rerun_south_north": "c6fbc7357efa35e59a2b19261da8489fae2f63e6c56e74d64ba4712bce893161",
    "baseline_entry": "25434f9e8fc53d1234cfb87a7ab4199379683fcb08c6b7cd0b9e947a3bf31a54",
    "real_scene_synthetic_method": (
        "af1b1cbf454340ec23876ee0d67d6480e4385015385eda351e1bbccedfe6ffda"
    ),
}
PINNED_K5 = {
    "south_candidates": "82d69e7b30d6e40def345d2c432f561adfd583186fa699ca3962fb4329e27f59",
    "default": "b09731e75ad5c09497923f0d03e90676f11bcc6d0801b66feb40857892354b04",
    "synthetic_method_everywhere": (
        "6f67f6fbb44882210554761f0a63469522564eb37681b6d57ed52cd95a4d30e3"
    ),
    "frustum": "6f67f6fbb44882210554761f0a63469522564eb37681b6d57ed52cd95a4d30e3",
    "entry_synthetic_only": "f8bd92eef1eb80f4d71a0d80f9579e38fd1af57db6d2e4037ac1cfcb7b56b883",
    "rule_missing": "7ab86ab95b0f7dd80432bd908f6efc86f9a7dd4ad6e7ae24caa90baec8117be3",
    "detector_short": "85832dab997c4740c622aee3e0ec7aae54b27dad724094ba3309fb77aae4552c",
}
PINNED_MOCK_FIXTURE = [
    "00761eb4788ee0694e03bb0a356768fbdae0ad4390d6e9071647cd198b173b16",
    "6ba80a0d8c11bb7a2ad2f86828513b6ffa9c0a966e1a1db7294fa61fe00c8e54",
    "0f9b22fdddf8e6d1b8dae7e051c05050211a8a1e91564aedefaa4010c5ae71b4",
]


# ----------------------------------------------------------------------- helpers


def _synthetic_config(origin: Any = "SYNTHETIC") -> dict[str, Any]:
    config = _config()
    config["scenes"][SCENE]["data_origin"] = origin
    return config


def _declared(ref: str, times: list[float], polygons: list[list[list[float]]]) -> dict[str, Any]:
    return _negative(ref, times, polygons, visible_floor={"method": SYN, "polygons": polygons})


def _generate(
    request: dict[str, Any],
    config: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return generate_blind_hypotheses(
        request,
        config=config,
        config_sha256="c" * 64,
        floor_map=_obstacle_room(),
        source_binding={"run_ref": "run:test", "clock_id": "TEST_CLOCK_5HZ"},
        previous_response=previous,
    )


def _fail(response: dict[str, Any]) -> dict[str, Any]:
    return next(s for s in response["trace"] if s["step"] == "FAIL_CLOSED")


def _convert_with(
    *,
    method: str = REQUIRED_VISIBILITY_METHOD,
    frame_method: str | None = None,
    entry_method: str | None = None,
    rule: Any = "FOOT_AND_TORSO_PROBES_VISIBLE",
    producer: dict[str, Any] | None = None,
    detector: dict[str, Any] | None = None,
    polygons: list[list[list[float]]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    response = _retrieval(WINDOW, method=method)
    if frame_method is not None:
        for frame in response["results"][0]["windows"][0]["frames"]:
            frame["reason"]["footprint_method"] = frame_method
    visibility = _visibility(polygons or [SOUTH_AISLE])
    entry = visibility["visidx:CAM_REAR"]
    if entry_method is not None:
        entry["method"] = entry_method
    if rule is None:
        del entry["visibility_rule"]
    else:
        entry["visibility_rule"] = rule
    if detector is not None:
        entry["detectability"]["detector"] = dict(detector)
    evaluations = _evaluations(response)
    if producer is not None:
        for record in evaluations.values():
            record["detection_producer"] = dict(producer)
    return negative_evidence_from_retrieval(
        response,
        frame_evaluations=evaluations,
        visibility_entries=visibility,
        interval_s=[0.0, 6.0],
        **kwargs,
    )


def _synthetic_convert(**kwargs: Any) -> dict[str, Any]:
    """All three method fields name the declared footprint; trusted origin SYNTHETIC."""

    kwargs.setdefault("method", SYN)
    kwargs.setdefault("entry_method", SYN)
    kwargs.setdefault("data_origin", "SYNTHETIC")
    return _convert_with(**kwargs)


def _reasons(converted: dict[str, Any]) -> set[str]:
    return {row["reason"] for row in converted["frame_outcomes"]}


# ------------------------------------------------- K1: scene data_origin (§3.2, §3.3)


def test_declared_footprint_is_accepted_in_a_synthetic_scene() -> None:
    entry = _declared("negev:synthetic-south", WINDOW, [SOUTH_AISLE])
    response = _generate(_obstacle_request(negative_evidence=[entry]), _synthetic_config())
    assert response["status"] == "READY"
    assert response["negative_evidence_applied"] == ["negev:synthetic-south"]
    assert response["configuration"]["data_origin"] == "SYNTHETIC"
    assert response["provenance"]["data_origin"] == "SYNTHETIC"
    (step,) = [s for s in response["trace"] if s["step"] == "SYNTHETIC_DECLARED_FOOTPRINTS"]
    assert step == {
        "step": "SYNTHETIC_DECLARED_FOOTPRINTS",
        "data_origin": "SYNTHETIC",
        "method": SYN,
        "negative_evidence_refs": ["negev:synthetic-south"],
    }
    # The declared footprint is applied exactly like a ray-cast one of the same shape.
    raycast = _negative("negev:synthetic-south", WINDOW, [SOUTH_AISLE])
    same = _generate(_obstacle_request(negative_evidence=[raycast]), _synthetic_config())
    assert response["reachable_regions"] == same["reachable_regions"]
    assert response["hypotheses"] == same["hypotheses"]
    assert not any(s["step"] == "SYNTHETIC_DECLARED_FOOTPRINTS" for s in same["trace"])


@pytest.mark.parametrize("origin", ["ABSENT", "REAL"])
def test_real_scene_rejects_the_declared_footprint_with_the_unchanged_code(origin: str) -> None:
    config = _config() if origin == "ABSENT" else _synthetic_config("REAL")
    entry = _declared("negev:syn", WINDOW, [SOUTH_AISLE])
    response = _generate(_obstacle_request(negative_evidence=[entry]), config)
    assert response["status"] == "UNKNOWN"
    assert response["reason"] == "NEGATIVE_EVIDENCE_INVALID"
    assert _fail(response)["problem"] == "VISIBILITY_METHOD_NOT_SOURCE_MESH_RAYCAST"
    assert "data_origin" not in response["configuration"]
    assert "data_origin" not in response["provenance"]
    assert response["output_sha256"] == PINNED_K1["real_scene_synthetic_method"]


def test_explicit_real_origin_answers_exactly_like_an_absent_one() -> None:
    request = _obstacle_request()
    assert _generate(request, _synthetic_config("REAL")) == _generate(request, _config())


@pytest.mark.parametrize("origin", ["synthetic", "", None, 1, True, ["SYNTHETIC"]])
def test_invalid_scene_data_origin_fails_closed(origin: Any) -> None:
    config = _synthetic_config(origin)
    with pytest.raises(ValueError):
        parse_config(config, scene_id=SCENE, config_sha256="c" * 64)
    response = _generate(_obstacle_request(), config)
    assert response["status"] == "UNKNOWN"
    assert response["reason"] == "SPEED_CONFIG_UNAVAILABLE"
    assert "data_origin" not in response["configuration"]


def test_fail_closed_synthetic_response_is_still_labelled() -> None:
    config = _synthetic_config()
    config["speed_range_m_s"] = {"min": 0.0, "max": 99.0, "source": "CONFIGURED_NOT_GT"}
    response = _generate(_obstacle_request(), config)
    assert response["reason"] == "SPEED_CONFIG_UNAVAILABLE"
    assert response["configuration"]["data_origin"] == "SYNTHETIC"
    assert response["provenance"]["data_origin"] == "SYNTHETIC"


@pytest.mark.parametrize("method", ["FRUSTUM_ONLY", "", None, ["SYNTHETIC_DECLARED_FOOTPRINT"]])
def test_synthetic_scene_still_rejects_other_methods(method: Any) -> None:
    entry = _negative("negev:x", WINDOW, [SOUTH_AISLE], visible_floor={"method": method})
    response = _generate(_obstacle_request(negative_evidence=[entry]), _synthetic_config())
    assert response["reason"] == "NEGATIVE_EVIDENCE_INVALID"
    assert _fail(response)["problem"] == "VISIBILITY_METHOD_NOT_SOURCE_MESH_RAYCAST"


def test_request_and_evidence_cannot_grant_the_synthetic_method() -> None:
    entry = _declared("negev:syn", WINDOW, [SOUTH_AISLE])
    with pytest.raises(HypothesisRequestError):
        _generate(
            {**_obstacle_request(negative_evidence=[entry]), "data_origin": "SYNTHETIC"}, _config()
        )
    # No ``provenance`` field on an entry (strict field set, contract §3.3).
    tagged = _negative(
        "negev:syn",
        WINDOW,
        [SOUTH_AISLE],
        visible_floor={"method": SYN, "polygons": [SOUTH_AISLE], "data_origin": "SYNTHETIC"},
        provenance={"data_origin": "SYNTHETIC"},
    )
    response = _generate(_obstacle_request(negative_evidence=[tagged]), _synthetic_config())
    assert _fail(response)["problem"] == "FIELDS"
    # A synthetic label inside visible_floor or the endpoints changes nothing in a real scene.
    del tagged["provenance"]
    tagged["sha256"] = canonical_sha256({k: v for k, v in tagged.items() if k != "sha256"})
    request = _obstacle_request(negative_evidence=[tagged])
    request["start"]["ground_estimate"]["provenance"]["data_origin"] = "SYNTHETIC"
    response = _generate(request, _config())
    assert _fail(response)["problem"] == "VISIBILITY_METHOD_NOT_SOURCE_MESH_RAYCAST"


# ------------------------------------------------------ real outputs stay unchanged


def test_real_outputs_keep_their_v1_1_hashes() -> None:
    first = _run(_obstacle_request(), _obstacle_room())
    assert first["output_sha256"] == PINNED_K1["first"]
    south = _candidates([SOUTH_AISLE])
    assert canonical_sha256(south) == PINNED_K5["south_candidates"]
    pruned = _rerun(first, south)
    assert pruned["output_sha256"] == PINNED_K1["rerun_south"]
    north = _candidates([NORTH_AISLE], times=[3.8, 4.0])
    assert _rerun(pruned, south + north)["output_sha256"] == PINNED_K1["rerun_south_north"]
    baseline = _negative("negev:base", _gap_times(0.0, 6.0)[:3], [SOUTH_AISLE])
    with_baseline = _run(_obstacle_request(negative_evidence=[baseline]), _obstacle_room())
    assert with_baseline["output_sha256"] == PINNED_K1["baseline_entry"]
    for response in (first, pruned, with_baseline):
        assert "data_origin" not in response["configuration"]
        assert "data_origin" not in response["provenance"]
        assert not any(s["step"] == "SYNTHETIC_DECLARED_FOOTPRINTS" for s in response["trace"])


def test_mock_fixture_hashes_are_unchanged() -> None:
    fixture = json.loads(
        (ROOT / "tests/fixtures/blind_hypothesis_pruning_mock_v1.json").read_text()
    )
    assert [s["response"]["output_sha256"] for s in fixture["steps"]] == PINNED_MOCK_FIXTURE


def test_real_configs_declare_no_data_origin() -> None:
    config = json.loads(REAL_CONFIG_PATH.read_text())
    assert all("data_origin" not in scene for scene in config["scenes"].values())


# -------------------------------------------------------------- K5 converter (§6)


@pytest.mark.parametrize(
    ("name", "kwargs"),
    [
        ("default", {}),
        ("synthetic_method_everywhere", {"method": SYN, "entry_method": SYN}),
        ("frustum", {"method": "FRUSTUM_ONLY"}),
        ("entry_synthetic_only", {"entry_method": SYN}),
        ("rule_missing", {"rule": None}),
        ("detector_short", {"producer": {"producer": "mock-perception", "version": "v2"}}),
    ],
)
def test_default_origin_matches_the_v1_1_converter(name: str, kwargs: dict[str, Any]) -> None:
    default = _convert_with(**kwargs)
    assert canonical_sha256(default) == PINNED_K5[name]
    assert _convert_with(data_origin="REAL", **kwargs) == default
    assert "data_origin" not in default


def test_real_conversion_rejects_the_declared_footprint() -> None:
    converted = _convert_with(method=SYN, entry_method=SYN)
    assert converted["negative_evidence_candidates"] == []
    assert _reasons(converted) == {"FOOTPRINT_NOT_SOURCE_MESH_RAYCAST"}


def test_synthetic_conversion_keeps_the_method_and_feeds_a_synthetic_scene() -> None:
    converted = _synthetic_convert()
    assert converted["data_origin"] == "SYNTHETIC"
    assert _reasons(converted) == {"ELIGIBLE"}
    (entry,) = converted["negative_evidence_candidates"]
    assert set(entry) == {
        "negative_evidence_ref",
        "origin",
        "camera_id",
        "frame_refs",
        "visibility_ref",
        "detection_result",
        "detection_producer",
        "retrieval_query_id",
        "sha256",
        "visible_floor",
    }
    assert entry["visible_floor"]["method"] == SYN
    assert entry["detection_producer"] == {"producer": "mock-perception", "version": "v2"}
    response = _generate(_obstacle_request(negative_evidence=[entry]), _synthetic_config())
    assert response["status"] == "READY"
    assert response["negative_evidence_applied"] == [entry["negative_evidence_ref"]]
    real = _generate(_obstacle_request(negative_evidence=[entry]), _config())
    assert _fail(real)["problem"] == "VISIBILITY_METHOD_NOT_SOURCE_MESH_RAYCAST"


def test_synthetic_conversion_of_ray_cast_input_only_adds_the_label() -> None:
    real = _convert_with()
    synthetic = _convert_with(data_origin="SYNTHETIC")
    assert synthetic.pop("data_origin") == "SYNTHETIC"
    assert synthetic == real


def test_k8_detector_values_match_with_exact_types() -> None:
    converted = _synthetic_convert(producer=K8_DETECTOR, detector=K8_DETECTOR)
    assert _reasons(converted) == {"ELIGIBLE"}
    (entry,) = converted["negative_evidence_candidates"]
    assert entry["detection_producer"] == {"producer": "synthetic-k8", "version": "v1"}
    # The K8 design's negative control: a producer without the two parameters.
    short = _synthetic_convert(
        producer={"producer": "synthetic-k8", "version": "v1"}, detector=K8_DETECTOR
    )
    assert short["negative_evidence_candidates"] == []
    assert _reasons(short) == {"DETECTOR_PARAMETERS_MISMATCH"}
    as_float = _synthetic_convert(
        producer={**K8_DETECTOR, "difference_threshold": 30.0}, detector=K8_DETECTOR
    )
    assert _reasons(as_float) == {"DETECTOR_PARAMETERS_MISMATCH"}


@pytest.mark.parametrize("mutate", _mismatch_cases())
def test_detector_mismatch_holds_for_synthetic_evidence(mutate: Any) -> None:
    visibility = _visibility([SOUTH_AISLE])
    entry = visibility["visidx:CAM_REAR"]
    entry["method"] = SYN
    mutate(entry)
    response = _retrieval(WINDOW, method=SYN)
    converted = negative_evidence_from_retrieval(
        response,
        frame_evaluations=_evaluations(response),
        visibility_entries=visibility,
        interval_s=[0.0, 6.0],
        data_origin="SYNTHETIC",
    )
    assert converted["negative_evidence_candidates"] == []
    assert _reasons(converted) == {"DETECTOR_PARAMETERS_MISMATCH"}


@pytest.mark.parametrize("rule", [None, "FOOT_PROBE_VISIBLE", "", 3])
def test_d21_rule_holds_for_synthetic_evidence(rule: Any) -> None:
    converted = _synthetic_convert(rule=rule)
    assert converted["negative_evidence_candidates"] == []
    assert _reasons(converted) == {"VISIBILITY_RULE_NOT_ELIGIBLE"}


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        # Result and frames ray-cast, index entry declared: the footprint is not resolved.
        ({"method": REQUIRED_VISIBILITY_METHOD}, "VISIBILITY_ENTRY_UNRESOLVED"),
        ({"frame_method": REQUIRED_VISIBILITY_METHOD}, "FOOTPRINT_NOT_SOURCE_MESH_RAYCAST"),
        ({"entry_method": REQUIRED_VISIBILITY_METHOD}, "VISIBILITY_ENTRY_UNRESOLVED"),
        (
            {"method": "FRUSTUM_ONLY", "entry_method": "FRUSTUM_ONLY"},
            "FOOTPRINT_NOT_SOURCE_MESH_RAYCAST",
        ),
    ],
)
def test_synthetic_conversion_needs_one_consistent_accepted_method(
    kwargs: dict[str, Any], reason: str
) -> None:
    converted = _synthetic_convert(**kwargs)
    assert converted["negative_evidence_candidates"] == []
    assert _reasons(converted) == {reason}


@pytest.mark.parametrize(
    "drop", ["floor_z_m", "polygons", "index_sha256", "method"], ids=lambda k: f"no-{k}"
)
def test_synthetic_entry_with_missing_fields_fails_closed(drop: str) -> None:
    response = _retrieval(WINDOW, method=SYN)
    visibility = _visibility([SOUTH_AISLE])
    visibility["visidx:CAM_REAR"]["method"] = SYN
    del visibility["visidx:CAM_REAR"][drop]
    converted = negative_evidence_from_retrieval(
        response,
        frame_evaluations=_evaluations(response),
        visibility_entries=visibility,
        interval_s=[0.0, 6.0],
        data_origin="SYNTHETIC",
    )
    assert converted["negative_evidence_candidates"] == []
    assert _reasons(converted) == {"VISIBILITY_ENTRY_UNRESOLVED"}


@pytest.mark.parametrize(
    "flag", ["frame_available", "rgb_hash_verified", "provenance_ok", "perception_evaluated"]
)
def test_synthetic_declared_flags_are_still_required(flag: str) -> None:
    response = _retrieval(WINDOW, method=SYN)
    visibility = _visibility([SOUTH_AISLE])
    visibility["visidx:CAM_REAR"]["method"] = SYN
    evaluations = _evaluations(response)
    for record in evaluations.values():
        record[flag] = 1  # truthy but not exactly True
    converted = negative_evidence_from_retrieval(
        response,
        frame_evaluations=evaluations,
        visibility_entries=visibility,
        interval_s=[0.0, 6.0],
        data_origin="SYNTHETIC",
    )
    assert converted["negative_evidence_candidates"] == []
    assert {row["outcome"] for row in converted["frame_outcomes"]} == {"UNKNOWN"}


def test_payload_cannot_switch_on_the_synthetic_method() -> None:
    response = _retrieval(WINDOW, method=SYN)
    response["provenance"] = {"data_origin": "SYNTHETIC"}
    response["data_origin"] = "SYNTHETIC"
    visibility = _visibility([SOUTH_AISLE])
    visibility["visidx:CAM_REAR"].update(method=SYN, data_origin="SYNTHETIC")
    evaluations = _evaluations(response, data_origin="SYNTHETIC")
    converted = negative_evidence_from_retrieval(
        response,
        frame_evaluations=evaluations,
        visibility_entries=visibility,
        interval_s=[0.0, 6.0],
    )
    assert converted["negative_evidence_candidates"] == []
    assert _reasons(converted) == {"FOOTPRINT_NOT_SOURCE_MESH_RAYCAST"}
    assert "data_origin" not in converted


@pytest.mark.parametrize("origin", ["synthetic", "", None, 1, True])
def test_invalid_trusted_origin_raises(origin: Any) -> None:
    with pytest.raises(ValueError):
        _convert_with(data_origin=origin)


def test_synthetic_label_is_kept_on_an_empty_conversion() -> None:
    converted = negative_evidence_from_retrieval(
        {"status": "UNKNOWN"}, frame_evaluations={}, visibility_entries={}, data_origin="SYNTHETIC"
    )
    assert converted["data_origin"] == "SYNTHETIC"
    assert converted["negative_evidence_candidates"] == []


# ------------------------------------------- append-only re-run across data origins


def test_synthetic_rerun_prunes_with_declared_evidence() -> None:
    config = _synthetic_config()
    first = _generate(_obstacle_request(), config)
    (entry,) = _synthetic_convert()["negative_evidence_candidates"]
    rerun = _generate(
        _obstacle_request(
            negative_evidence=[entry], previous_response_sha256=first["output_sha256"]
        ),
        config,
        previous=first,
    )
    assert rerun["status"] == "READY"
    assert rerun["pruning_log"][0]["negative_evidence_ref"] == entry["negative_evidence_ref"]
    assert rerun["provenance"]["data_origin"] == "SYNTHETIC"


@pytest.mark.parametrize(
    ("first_config", "rerun_config"),
    [("REAL", "SYNTHETIC"), ("SYNTHETIC", "REAL")],
)
def test_real_and_synthetic_responses_cannot_be_mixed_in_a_rerun(
    first_config: str, rerun_config: str
) -> None:
    configs = {"REAL": _config(), "SYNTHETIC": _synthetic_config()}
    first = _generate(_obstacle_request(), configs[first_config])
    evidence = [_negative("negev:south", WINDOW, [SOUTH_AISLE])]
    rerun = _generate(
        _obstacle_request(
            negative_evidence=evidence, previous_response_sha256=first["output_sha256"]
        ),
        configs[rerun_config],
        previous=first,
    )
    assert rerun["status"] == "UNKNOWN"
    assert rerun["reason"] == "PROVENANCE_MISMATCH"
    assert _fail(rerun)["problem"] == "PREVIOUS_RESPONSE_CONFIGURATION"
    assert rerun["pruned_hypotheses"] == []


def test_relabelled_previous_response_fails_its_hash() -> None:
    first = _generate(_obstacle_request(), _config())
    forged = copy.deepcopy(first)
    forged["configuration"]["data_origin"] = "SYNTHETIC"
    forged["provenance"]["data_origin"] = "SYNTHETIC"
    rerun = _generate(
        _obstacle_request(previous_response_sha256=first["output_sha256"]),
        _synthetic_config(),
        previous=forged,
    )
    assert rerun["reason"] == "NEGATIVE_EVIDENCE_NOT_APPEND_ONLY"
    assert _fail(rerun)["problem"] == "PREVIOUS_RESPONSE_HASH_MISMATCH"


# --------------------------------------------------------------- K8 configuration


def test_k8_config_is_separate_and_declares_a_synthetic_scene() -> None:
    k8 = json.loads(K8_CONFIG_PATH.read_text())
    real = json.loads(REAL_CONFIG_PATH.read_text())
    assert list(k8["scenes"]) == ["synthetic-office-k8"]
    scene = k8["scenes"]["synthetic-office-k8"]
    assert scene["data_origin"] == "SYNTHETIC"
    assert not set(k8["scenes"]) & set(real["scenes"])
    parsed = parse_config(k8, scene_id="synthetic-office-k8", config_sha256="k" * 64)
    assert parsed.data_origin == "SYNTHETIC"
    assert SYN in parsed.accepted_visibility_methods
    # Same humanoid settings as the real configurations; only the scene differs.
    for key in (
        "speed_range_m_s",
        "nominal_speed_m_s",
        "plausibility_weights",
        "grid_step_m",
        "lattice_metric_factor",
        "limits",
    ):
        assert k8[key] == real[key], key
    assert (scene["time_step_s"], scene["body_radius_m"]) == (0.2, 0.25)
    assert scene["source_sha256"] == scene["safe_inputs_sha256"] == "SYNTHETIC_NONE"
