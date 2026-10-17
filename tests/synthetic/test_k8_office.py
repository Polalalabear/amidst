"""K8b synthetic Office fixture: structure, determinism and isolation (design D23).

Structure is locked, not refs: ``hyp:`` refs and ``output_sha256`` values depend on the
binding and the engine version. The C7 map belongs to Codex (#40/#44) and is not in
this repository; the tests find it through ``$K8_C7_MAP`` or a Codex git ref and are
skipped, loudly, when it is unavailable.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from amidst.blind_hypothesis import (
    candidate_screen,
    engine,
    negative_evidence_from_retrieval,
    retrieval_evidence,
)
from amidst.synthetic import k8_office as k8

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "k8_synthetic_blind_hypothesis_v1.json"
FIXTURE = ROOT / "frontend" / "workbench" / "fixtures" / "k8-synthetic-office.fixture.json"
SCRIPT = ROOT / "scripts" / "k8_generate_synthetic_fixture.py"
REQUEST_KEYS = {
    "schema_version",
    "session_ref",
    "scene_id",
    "candidate_ref",
    "start",
    "end",
    "top_k",
    "negative_evidence",
    "previous_response_sha256",
}
SYN = k8.SYNTHETIC_VISIBILITY_METHOD
# Table geometry (hole 4): x 39.67-44.05, y 49.14-50.71 (design §2).
TABLE_X = (40.0, 43.7)
NORTH_EDGE_Y, SOUTH_EDGE_Y = 50.71, 49.14


@pytest.fixture(scope="module")
def c7_path() -> Path:
    path = k8.locate_c7_map(ROOT)
    if path is None:
        pytest.skip("C7 map not found (set K8_C7_MAP or fetch a Codex branch): UNKNOWN")
    return path


def _script() -> Any:
    spec = importlib.util.spec_from_file_location("k8_generate_synthetic_fixture", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build(c7_path: Path) -> dict[str, Any]:
    return k8.build_fixture(
        c7_map_path=c7_path,
        config_path=CONFIG,
        engine_files={
            "src/amidst/blind_hypothesis/engine.py": Path(engine.__file__),
            "src/amidst/blind_hypothesis/retrieval_evidence.py": Path(retrieval_evidence.__file__),
            "src/amidst/blind_hypothesis/candidate_screen.py": Path(candidate_screen.__file__),
        },
        generator_files={
            "scripts/k8_generate_synthetic_fixture.py": SCRIPT,
            "src/amidst/synthetic/k8_office.py": Path(k8.__file__),
        },
        upstream=_script().UPSTREAM,
    )


@pytest.fixture(scope="module")
def built(c7_path: Path) -> dict[str, Any]:
    return _build(c7_path)


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _routes_side(hypothesis: dict[str, Any]) -> str:
    """'north' / 'south' / 'other' by the route between the table's x extent."""

    ys = [p[1] for p in hypothesis["route_m"] if TABLE_X[0] <= p[0] <= TABLE_X[1]]
    if ys and min(ys) >= NORTH_EDGE_Y - 0.05:
        return "north"
    if ys and max(ys) <= SOUTH_EDGE_Y + 0.05:
        return "south"
    return "other"


# ------------------------------------------------------------------ determinism


def test_rerun_gives_identical_hash_and_text(built: dict[str, Any], c7_path: Path) -> None:
    again = _build(c7_path)
    assert again["fixture_sha256"] == built["fixture_sha256"]
    assert k8.dump_fixture(again) == k8.dump_fixture(built)


def test_committed_fixture_is_what_the_generator_writes(built: dict[str, Any]) -> None:
    assert FIXTURE.read_text(encoding="utf-8") == k8.dump_fixture(built)
    stored = json.loads(FIXTURE.read_text(encoding="utf-8"))
    body = {key: value for key, value in stored.items() if key != "fixture_sha256"}
    assert engine.canonical_sha256(body) == stored["fixture_sha256"]


# ----------------------------------------------------------------- SYNTHETIC mark


def test_everything_is_marked_synthetic(built: dict[str, Any]) -> None:
    assert built["data_origin"] == "SYNTHETIC"
    assert built["provenance"]["data_origin"] == "SYNTHETIC"
    assert built["scene_id"] == k8.SCENE_ID == "synthetic-office-k8"
    prov = built["provenance"]
    assert (prov["run_ref"], prov["clock_id"]) == ("synthetic:k8-office-v1", "SYNTHETIC_K8_5HZ")
    assert prov["source_sha256"] == prov["safe_inputs_sha256"] == "SYNTHETIC_NONE"
    responses = [built["scenarios"]["S1"]["response"], *built["scenarios"]["S2"]["responses"]]
    responses += [step["response"] for step in built["scenarios"]["S3"]["steps"]]
    assert len(responses) == 7
    for response in responses:
        assert response["configuration"]["data_origin"] == "SYNTHETIC"
        assert response["provenance"]["data_origin"] == "SYNTHETIC"
        assert response["provenance"]["source_sha256"] == "SYNTHETIC_NONE"
        assert response["provenance"]["clock_id"] == "SYNTHETIC_K8_5HZ"
    for node in _walk(built["scenarios"]):
        if isinstance(node, dict) and "estimate_kind" in node:
            assert node["provenance"] == {"gt_read": False, "data_origin": "SYNTHETIC"}
            assert node["camera_id"].startswith("SYN_CAM_")
            assert node["observation_ref"].startswith("synthetic-observation:")
        if isinstance(node, dict) and "visible_floor" in node:
            assert node["visible_floor"]["method"] == SYN
            assert node["camera_id"].startswith("SYN_CAM_")
            assert node["detection_producer"] == {"producer": "synthetic-k8", "version": "v1"}
    assert all(
        c["camera_id"].startswith("SYN_CAM_") and not c["rendered"] for c in built["cameras"]
    )


# --------------------------------------------------------------------- scenarios


def test_s1_has_multiple_hypotheses_on_both_sides_of_the_table(built: dict[str, Any]) -> None:
    response = built["scenarios"]["S1"]["response"]
    assert response["status"] == "READY"
    sides = [_routes_side(h) for h in response["hypotheses"]]
    assert len(sides) >= 2
    assert "north" in sides and "south" in sides


def test_s2_gives_all_three_verdicts(built: dict[str, Any]) -> None:
    screen = built["scenarios"]["S2"]["screen"]
    rows = {r["candidate_ref"]: r for r in screen["results"]}
    assert {r["verdict"] for r in rows.values()} == {
        "REACHABLE",
        "UNREACHABLE_UNDER_CONFIG",
        "UNDETERMINED",
    }
    assert rows["synthetic-candidate:R1"]["verdict"] == "REACHABLE"
    assert rows["synthetic-candidate:R2"]["k1_reason"] == "ENDPOINTS_UNREACHABLE"
    assert rows["synthetic-candidate:R3"]["k1_reason"] == "NO_HYPOTHESIS_PASSED_CHECKS"
    assert all(r["identity_verdict"] == "UNCONFIRMED" for r in rows.values())
    assert screen["verdict_basis"] == "CONFIGURED_SPEED_RANGE_NOT_PROBABILITY"
    # The embedded K1 responses are the ones the screen hashed.
    embedded = built["scenarios"]["S2"]["responses"]
    assert [r["output_sha256"] for r in embedded] == [
        r["k1_response_sha256"] for r in screen["results"]
    ]


def test_s3_prunes_north_first_then_south(built: dict[str, Any]) -> None:
    steps = built["scenarios"]["S3"]["steps"]
    base, north, both = (s["response"] for s in steps)
    base_side = {h["hypothesis_ref"]: _routes_side(h) for h in base["hypotheses"]}
    # Step 1: every pruned path is a north route; everything left is on the south side.
    pruned1 = [h["hypothesis_ref"] for h in north["pruned_hypotheses"]]
    assert pruned1 and {base_side[ref] for ref in pruned1} == {"north"}
    assert {_routes_side(h) for h in north["hypotheses"]} == {"south"}
    # Step 2: the south routes of step 1 are pruned; what remains is a longer detour.
    pruned2 = {h["hypothesis_ref"] for h in both["pruned_hypotheses"]}
    assert {h["hypothesis_ref"] for h in north["hypotheses"]} <= pruned2
    assert both["status"] == "READY" and both["hypotheses"]
    shortest_before = min(
        h["plausibility"]["components"]["path_length_m"] for h in base["hypotheses"]
    )
    assert (
        min(h["plausibility"]["components"]["path_length_m"] for h in both["hypotheses"])
        > shortest_before + 2
    )
    assert [len(s["response"]["negative_evidence_applied"]) for s in steps] == [0, 1, 2]


def test_s3_reachable_area_shrinks_as_in_design_section_5(built: dict[str, Any]) -> None:
    areas = built["scenarios"]["S3"]["reachable_area_m2"]
    assert areas == sorted(areas, reverse=True) and len(set(areas)) == 3
    assert areas == pytest.approx([649.0, 611.4, 574.5], abs=0.06)
    convergence = built["scenarios"]["S3"]["convergence"]
    assert convergence["chain_verified"] is True
    chain = [s["response"]["output_sha256"] for s in built["scenarios"]["S3"]["steps"]]
    assert [
        s["request"]["previous_response_sha256"] for s in built["scenarios"]["S3"]["steps"]
    ] == [
        None,
        chain[0],
        chain[1],
    ]


# ------------------------------------------------------------- S3 goes through K5


def test_s3_evidence_is_the_k5_conversion_output(built: dict[str, Any]) -> None:
    steps = built["scenarios"]["S3"]["steps"]
    floor_z = built["map"]["floor_z_m"]
    north = k8.synthetic_negative_evidence("SYN_CAM_N", "north", k8.NORTH_FOOTPRINT, floor_z)
    expected = north["converted"]["negative_evidence_candidates"]
    assert expected and steps[1]["request"]["negative_evidence"] == expected
    assert steps[1]["k5"]["converter"] == "amidst.blind_hypothesis.negative_evidence_from_retrieval"
    assert steps[1]["k5"]["data_origin"] == "SYNTHETIC"
    assert (steps[1]["k5"]["frame_count"], steps[1]["k5"]["eligible_frame_count"]) == (21, 21)
    # Step 2 appends; the north entry is carried over unchanged.
    assert steps[2]["request"]["negative_evidence"][0] == expected[0]
    assert len(steps[2]["request"]["negative_evidence"]) == 2


def test_detector_record_is_integer_typed_and_enforced() -> None:
    assert k8.DETECTOR == {
        "producer": "synthetic-k8",
        "version": "v1",
        "difference_threshold": 30,
        "min_pixels": 28,
    }
    assert type(k8.DETECTOR["difference_threshold"]) is int
    assert type(k8.DETECTOR["min_pixels"]) is int
    retrieval = k8._retrieval_response("SYN_CAM_N", "north")
    entries = k8._visibility_entries("SYN_CAM_N", k8.NORTH_FOOTPRINT, 0.5)
    evaluations = k8._frame_evaluations(retrieval)
    kwargs = {"interval_s": [10.0, 16.0], "data_origin": "SYNTHETIC"}

    def convert(**over: Any) -> dict[str, Any]:
        return negative_evidence_from_retrieval(
            retrieval,
            frame_evaluations=over.get("frame_evaluations", evaluations),
            visibility_entries=entries,
            **{**kwargs, **{k: v for k, v in over.items() if k != "frame_evaluations"}},
        )

    assert len(convert()["negative_evidence_candidates"]) == 1
    # Producer/version only: every frame is UNKNOWN / DETECTOR_PARAMETERS_MISMATCH.
    short = {
        ref: {**rec, "detection_producer": {"producer": "synthetic-k8", "version": "v1"}}
        for ref, rec in evaluations.items()
    }
    out = convert(frame_evaluations=short)
    assert out["negative_evidence_candidates"] == []
    assert {o["reason"] for o in out["frame_outcomes"]} == {"DETECTOR_PARAMETERS_MISMATCH"}
    # A real (default) origin never accepts the declared footprint.
    real = negative_evidence_from_retrieval(
        retrieval,
        frame_evaluations=evaluations,
        visibility_entries=entries,
        interval_s=[10.0, 16.0],
    )
    assert real["negative_evidence_candidates"] == []
    assert {o["reason"] for o in real["frame_outcomes"]} == {"FOOTPRINT_NOT_SOURCE_MESH_RAYCAST"}


# ------------------------------------------------------- D1: no truth in K1 inputs


def test_k1_requests_hold_only_contract_fields_and_no_truth(
    c7_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict[str, Any]] = []
    original = engine.generate_blind_hypotheses

    def spy(request: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        seen.append(json.loads(json.dumps(request)))
        return original(request, **kwargs)

    monkeypatch.setattr(k8, "generate_blind_hypotheses", spy)
    monkeypatch.setattr(candidate_screen, "generate_blind_hypotheses", spy)
    _build(c7_path)
    assert len(seen) == 1 + 3 + 3 + 2 and all(set(r) == REQUEST_KEYS for r in seen)
    for request in seen:
        for node in _walk(request):
            if isinstance(node, dict):
                assert not {str(k).lower() for k in node} & k8.FORBIDDEN_KEYS
        for end in (request["start"], request["end"]):
            assert end["ground_estimate"]["provenance"]["gt_read"] is False


def test_fixture_and_sources_carry_no_ground_truth(built: dict[str, Any]) -> None:
    assert not [n for n in _walk(built) if isinstance(n, dict) and set(n) & k8.FORBIDDEN_KEYS]
    assert built["provenance"]["gt_read"] is False
    assert built["provenance"]["ground_truth_in_requests"] is False
    for source in (Path(k8.__file__), SCRIPT):
        text = source.read_text(encoding="utf-8")
        assert "data/evaluation" not in text
        assert "random" not in text.replace("No randomness", "")


# -------------------------------------------------------------------- provenance


def _git_blob(path: str) -> str:
    return k8.git_blob_sha1(Path(path).read_bytes())


def test_provenance_records_engine_blobs_upstream_shas_and_map(built: dict[str, Any]) -> None:
    prov = built["provenance"]
    engines = prov["engine_files"]
    assert engines["src/amidst/blind_hypothesis/engine.py"]["git_blob"] == _git_blob(
        engine.__file__
    )
    assert engines["src/amidst/blind_hypothesis/retrieval_evidence.py"]["git_blob"] == _git_blob(
        retrieval_evidence.__file__
    )
    assert engines["src/amidst/blind_hypothesis/candidate_screen.py"]["git_blob"] == _git_blob(
        candidate_screen.__file__
    )
    up = prov["upstream"]
    assert (up["k8a_synthetic_method"]["pr"], up["k8c_candidate_screen"]["pr"]) == (58, 57)
    for key in ("k8a_synthetic_method", "k8c_candidate_screen"):
        assert len(up[key]["commit"]) == 40
    assert prov["map_sha256"] == k8.C7_MAP_SHA256 == built["map"]["map_sha256"]
    assert prov["config"]["sha256"] == k8.sha256_bytes(CONFIG.read_bytes())
    assert prov["config"]["parent_config_ref"] == "configs/office_person_blind_hypothesis_v1.json"
    assert prov["map_source"]["path"].endswith("C7_OFFICE_SOURCE_MAP_20261017.json")
    assert prov["detection_producer"] == k8.DETECTOR


def test_wrong_map_bytes_are_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "map.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(k8.SyntheticFixtureError, match="MAP_BUNDLE_HASH_MISMATCH"):
        k8.load_c7_bundle(bad)
