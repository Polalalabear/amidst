"""Generate the MOCK blind-hypothesis pruning sequence (task K5).

Writes ``tests/fixtures/blind_hypothesis_pruning_mock_v1.json``: a synthetic room, the
original hypotheses, then two RETRIEVAL_FEEDBACK negative-evidence steps (mock,
contract-shaped frame-retrieval responses converted by
``negative_evidence_from_retrieval``) and the re-runs they cause. Every response is
produced by the real K1/K5 code and carries its ``output_sha256``; the retrieval
inputs are invented. This is demo data for the workbench until the retrieval API (C5)
exists, not Office data and not evidence about any real target.

    .venv/bin/python scripts/generate_blind_pruning_mock_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shapely.geometry import box

from amidst.blind_hypothesis import (
    REQUEST_SCHEMA,
    FloorMapDescriptor,
    PolygonFloorMap,
    canonical_sha256,
    generate_blind_hypotheses,
    negative_evidence_from_retrieval,
    pruning_convergence_summary,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "blind_hypothesis_v1.json"
OUTPUT_PATH = ROOT / "tests" / "fixtures" / "blind_hypothesis_pruning_mock_v1.json"
FIXTURE_NOTE = "MOCK, contract-shaped, not real data"
SCENE = "mock-pruning-room"
FLOOR_Z = 0.0
# Room 8 x 5 m with a 2 x 2.6 m block in the middle; two aisles (north, south) join the ends.
ROOM = [[0.0, 0.0], [8.0, 0.0], [8.0, 5.0], [0.0, 5.0]]
BLOCK = [[3.0, 1.2], [5.0, 1.2], [5.0, 3.8], [3.0, 3.8]]
START, END = (0.75, 2.5), (7.25, 2.5)
DURATION_S = 4.0
STEP_S = 0.2
SOUTH_FOOTPRINT = [[[2.5, 0.0], [5.5, 0.0], [5.5, 1.5], [2.5, 1.5]]]
NORTH_FOOTPRINT = [[[2.9, 3.4], [3.95, 3.4], [3.95, 4.5], [2.9, 4.5]]]


def _descriptor() -> FloorMapDescriptor:
    return FloorMapDescriptor(
        kind="SYNTHETIC_TEST",
        map_ref="mock:pruning-room",
        sha256="0" * 64,
        walkable_ref="mock:walk",
        portal_ref="mock:portal",
        floor_id="F",
    )


def _floor_map() -> PolygonFloorMap:
    walkable = box(0.0, 0.0, 8.0, 5.0).difference(box(3.0, 1.2, 5.0, 3.8))
    return PolygonFloorMap(_descriptor(), FLOOR_Z, {"WALK_ROOM": walkable}, {})


def _endpoint(ref: str, t: float, xy: tuple[float, float]) -> dict[str, Any]:
    estimate = {
        "schema_version": "office-demo.interval-observation.v1",
        "observation_ref": ref,
        "camera_id": "CAM_MOCK",
        "timestamp_s": t,
        "status": "READY",
        "reason": None,
        "evidence_state": "PROJECTED_OBSERVATION",
        "estimate_kind": "POINT",
        "point_m": [xy[0], xy[1], FLOOR_Z],
        "segment": None,
        "pixel_sensitivity_m": 0.1,
        "contact_quality": {"status": "PASS"},
        "provenance": {"gt_read": False},
    }
    return {
        "observation_ref": ref,
        "camera_id": "CAM_MOCK",
        "timestamp_s": t,
        "evidence_state": "PROJECTED_OBSERVATION",
        "ground_estimate": estimate,
    }


def _mock_retrieval(
    camera: str,
    query_id: str,
    times: list[float],
    footprint_polygons: list[list[list[float]]],
    *,
    detection_at: float | None = None,
    unevaluated_at: float | None = None,
) -> dict[str, Any]:
    """Mock ``workbench.frame-retrieval.v1`` response plus the backend lookups it needs."""

    frames = [
        {
            "frame_ref": f"mock-frame:{camera}:{t:.1f}",
            "timestamp_s": t,
            "reason": {
                "kind": "REACHABLE_REGION_IN_VIEW",
                "footprint_method": "SOURCE_MESH_RAYCAST",
                "walkable_status": "TRUE",
            },
        }
        for t in times
    ]
    evaluations = {}
    for frame in frames:
        t = frame["timestamp_s"]
        evaluations[frame["frame_ref"]] = {
            "frame_available": True,
            "rgb_hash_verified": True,
            "provenance_ok": True,
            "perception_evaluated": t != unevaluated_at,
            "measurement_count": 1 if t == detection_at else 0,
            "detection_producer": {"producer": "mock-perception", "version": "v2"},
        }
    visibility_ref = f"mock-visidx:{camera}"
    return {
        "response": {
            "schema_version": "workbench.frame-retrieval.v1",
            "status": "READY",
            "reason": None,
            "query_id": query_id,
            "query": {
                "query_kind": "HYPOTHESIS",
                "hypothesis_interval": {"start_s": 0.0, "end_s": DURATION_S},
                "endpoint_substitutions": [],
            },
            "results": [
                {
                    "camera_id": camera,
                    "visibility_ref": visibility_ref,
                    "method": "SOURCE_MESH_RAYCAST",
                    "windows": [{"start_s": times[0], "end_s": times[-1], "frames": frames}],
                }
            ],
        },
        "frame_evaluations": evaluations,
        "visibility_entries": {
            visibility_ref: {
                "method": "SOURCE_MESH_RAYCAST",
                "floor_z_m": FLOOR_Z,
                "polygons": footprint_polygons,
                "index_sha256": canonical_sha256({"camera": camera, "mock": True}),
                "visibility_rule": "FOOT_AND_TORSO_PROBES_VISIBLE",
            }
        },
    }


def build_fixture() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text())
    config["scenes"][SCENE] = {"time_step_s": STEP_S, "body_radius_m": 0.25}
    config_sha256 = canonical_sha256(config)
    floor_map = _floor_map()

    def run(evidence: list[dict[str, Any]], previous: dict[str, Any] | None) -> dict[str, Any]:
        request = {
            "schema_version": REQUEST_SCHEMA,
            "session_ref": "mock:session",
            "scene_id": SCENE,
            "candidate_ref": None,
            "start": _endpoint("mock-obs:start", 0.0, START),
            "end": _endpoint("mock-obs:end", DURATION_S, END),
            "top_k": 3,
            "negative_evidence": evidence,
            "previous_response_sha256": previous["output_sha256"] if previous else None,
        }
        return generate_blind_hypotheses(
            request,
            config=config,
            config_sha256=config_sha256,
            floor_map=floor_map,
            source_binding={"run_ref": "mock:run", "clock_id": "MOCK_CLOCK_5HZ"},
            previous_response=previous,
        )

    queries = [
        (
            "Retrieval 1: camera over the south aisle sees nobody",
            _mock_retrieval(
                "CAM_MOCK_SOUTH",
                "frq:mock-1",
                [1.4, 1.6, 1.8, 2.0, 2.2, 2.4, 2.6],
                SOUTH_FOOTPRINT,
                detection_at=1.4,
                unevaluated_at=2.6,
            ),
        ),
        (
            "Retrieval 2: camera over the north aisle (west half) sees nobody",
            _mock_retrieval(
                "CAM_MOCK_NORTH",
                "frq:mock-2",
                [1.0, 1.2, 1.8, 2.0],
                NORTH_FOOTPRINT,
            ),
        ),
    ]
    steps: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    response = run([], None)
    steps.append(
        {
            "label": "Original hypotheses (no negative evidence)",
            "request_previous_response_sha256": None,
            "negative_evidence": [],
            "retrieval": None,
            "response_sha256": response["output_sha256"],
            "response": response,
        }
    )
    for label, query in queries:
        conversion = negative_evidence_from_retrieval(
            query["response"],
            frame_evaluations=query["frame_evaluations"],
            visibility_entries=query["visibility_entries"],
            applied_negative_evidence_refs=[e["negative_evidence_ref"] for e in evidence],
        )
        previous = response
        evidence = [*evidence, *conversion["negative_evidence_candidates"]]
        response = run(evidence, previous)
        steps.append(
            {
                "label": label,
                "request_previous_response_sha256": previous["output_sha256"],
                "negative_evidence": evidence,
                "retrieval": {**query, "conversion": conversion},
                "response_sha256": response["output_sha256"],
                "response": response,
            }
        )
    return {
        "fixture_note": FIXTURE_NOTE,
        "schema": "mock.blind-hypothesis-pruning-sequence.v1",
        "scenario": {
            "scene_id": SCENE,
            "room_m": ROOM,
            "block_m": BLOCK,
            "start_m": list(START),
            "end_m": list(END),
            "duration_s": DURATION_S,
            "config_sha256": config_sha256,
        },
        "steps": steps,
        "convergence": pruning_convergence_summary([s["response"] for s in steps]),
    }


def main() -> None:
    fixture = build_fixture()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(fixture, sort_keys=True, indent=1) + "\n")
    for step in fixture["steps"]:
        response = step["response"]
        print(
            step["label"],
            response["status"],
            response["reason"],
            len(response["hypotheses"]),
            len(response["pruned_hypotheses"]),
            response["output_sha256"][:12],
        )
    print("wrote", OUTPUT_PATH.relative_to(ROOT), OUTPUT_PATH.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
