"""Generate contract-shaped MOCK fixtures for the K4 blind-hypothesis workbench layer.

Runs the K1 module (``claude/k5-pruning`` @ 726e390 = K1 + K5, PRs #33/#36) on SYNTHETIC maps.
Every field, including D7 ``endpoint_substitutions`` and D11 ``walkable: UNKNOWN``
segments, is K1/K5 output, except the D15 restricted-policy case: K1 passes a region
tier through to ``segments[].tiers`` but does not emit ``restricted_area_crossed``,
``restricted_policy_sample_indices`` or ``restricted_ref``; those three are hand-patched
and named in that case's ``fixture_note``. Nothing here is Office data and
nothing reads GT.

K1 is not part of this branch. Export it first, then run with the repo venv:

    git archive 726e390 src configs/blind_hypothesis_v1.json | tar -x -C <dir>
    .venv/bin/python frontend/workbench/fixtures/generate_blind_hypothesis_fixtures.py --k1-root <dir>

Output: ``blind-hypothesis.fixture.json`` next to this script. Every case carries
``"fixture_note": "MOCK, contract-shaped, not real data"``.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

NOTE = "MOCK, contract-shaped, not real data"
SCENE = "synthetic-test"
OUT = Path(__file__).with_name("blind-hypothesis.fixture.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k1-root", required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.k1_root / "src"))
    try:  # an installed ``amidst`` package would shadow the exported K1 files
        import amidst

        amidst.__path__.insert(0, str(args.k1_root / "src" / "amidst"))
    except ImportError:
        pass
    from shapely.geometry import box

    from amidst.blind_hypothesis import (
        REQUEST_SCHEMA,
        FloorMapDescriptor,
        canonical_sha256,
        PolygonFloorMap,
        generate_blind_hypotheses,
        polygon_floor_map,
    )

    import amidst.blind_hypothesis as k1

    assert Path(k1.__file__).resolve().is_relative_to(args.k1_root.resolve()), k1.__file__  # the exported K1, not an installed copy
    config = json.loads((args.k1_root / "configs" / "blind_hypothesis_v1.json").read_text())
    config["scenes"][SCENE] = {"time_step_s": 0.2, "body_radius_m": 0.25}
    descriptor = FloorMapDescriptor(
        kind="SYNTHETIC_TEST", map_ref="synthetic:test-map", sha256="0" * 64,
        walkable_ref="synthetic:walk", portal_ref="synthetic:portal", floor_id="F",
    )

    def estimate(ref: str, t: float, xy: tuple[float, float]) -> dict[str, Any]:
        return {
            "schema_version": "office-demo.interval-observation.v1", "observation_ref": ref,
            "camera_id": "CAM_MOCK", "timestamp_s": t, "status": "READY", "reason": None,
            "evidence_state": "PROJECTED_OBSERVATION", "estimate_kind": "POINT",
            "point_m": [xy[0], xy[1], 0.0], "segment": None, "pixel_sensitivity_m": 0.1,
            "contact_quality": {"status": "PASS"}, "provenance": {"gt_read": False},
        }

    def endpoint(ref: str, t: float, xy: tuple[float, float]) -> dict[str, Any]:
        return {"observation_ref": ref, "camera_id": "CAM_MOCK", "timestamp_s": t,
                "evidence_state": "PROJECTED_OBSERVATION", "ground_estimate": estimate(ref, t, xy)}

    def request(start: dict[str, Any], end: dict[str, Any], negative: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {"schema_version": REQUEST_SCHEMA, "session_ref": "session:mock", "scene_id": SCENE,
                "candidate_ref": None, "start": start, "end": end, "top_k": 3,
                "negative_evidence": negative or [], "previous_response_sha256": None}

    def run(req: dict[str, Any], floor_map: PolygonFloorMap) -> dict[str, Any]:
        return generate_blind_hypotheses(req, config=config, config_sha256="c" * 64, floor_map=floor_map,
                                         source_binding={"run_ref": "run:mock", "clock_id": "MOCK_CLOCK_5HZ"})

    room = PolygonFloorMap(descriptor, 0.0, {"WALK_ROOM": box(0, 0, 10, 6).difference(box(4, 1.5, 6, 4.5))}, {})
    closed_rooms = polygon_floor_map(
        descriptor=descriptor, floor_z_m=0.0,
        regions={"WALK_A": [[0, 0], [4, 0], [4, 4], [0, 4]], "WALK_B": [[4.4, 0], [8.4, 0], [8.4, 4], [4.4, 4]]},
        portals={},
    )

    # Case 1: READY, K >= 3, one baseline negative-evidence camera that sees the north strip.
    times = [round(4.4 + 0.2 * i, 6) for i in range(1, 21)]
    negative = [{
        "negative_evidence_ref": "negev:mock-baseline", "origin": "BLIND_INTERVAL_BASELINE", "camera_id": "CAM_MOCK_2",
        "frame_refs": [{"frame_ref": f"frame:mock:{t}", "timestamp_s": t} for t in times],
        "visibility_ref": "visibility:mock", "detection_result": "NO_DETECTION",
        "detection_producer": {"producer": "mock-perception", "version": "v2"}, "retrieval_query_id": None,
        "sha256": "1" * 64,
        "visible_floor": {"method": "SOURCE_MESH_RAYCAST", "floor_z_m": 0.0, "index_sha256": "2" * 64,
                          "polygons": [[[0, 4.6], [10, 4.6], [10, 6], [0, 6]]]},
    }]
    negative[0]["sha256"] = canonical_sha256({k: v for k, v in negative[0].items() if k != "sha256"})  # K5: entries carry their canonical hash
    ready = run(request(endpoint("obs:front-4.4", 4.4, (2.0, 3.0)), endpoint("obs:rear-8.6", 8.6, (8.0, 3.0)), negative), room)
    assert ready["status"] == "READY" and len(ready["hypotheses"]) >= 3, ready.get("reason")

    # Case 2: UNKNOWN, closed wall between the rooms (no portal), fail-closed with a reason.
    unknown = run(request(endpoint("obs:front-4.4", 4.4, (1.0, 2.0)), endpoint("obs:rear-8.6", 8.6, (7.0, 2.0))), closed_rooms)
    assert unknown["status"] == "UNKNOWN" and unknown["hypotheses"] == [], unknown["status"]

    # Case 3: K1 output for a D7 START substitution (4.4 s unusable -> 4.2 s) on a map with a walkable:UNKNOWN seating area (D11).
    seating_map = PolygonFloorMap(
        descriptor, 0.0, {"WALK_ROOM": box(0, 0, 10, 6).difference(box(4, 1.5, 6, 4.5)).difference(box(2.5, 3.5, 4.0, 6.0))}, {},
        {"AREA_SEATING": box(2.5, 3.5, 4.0, 6.0)}, {"WALK_ROOM": "ANNOTATION_ONLY"},
    )

    def substitution(original_t: float, substitute_t: float, **overrides: Any) -> dict[str, Any]:
        record = {
            "rule": "SAME_TRACK_NEAREST_USABLE_OUTWARD_V1", "track_ref": "UNKNOWN",
            "original": {"observation_ref": "obs:front-4.4", "timestamp_s": original_t,
                         "ground_estimate_status": "UNKNOWN", "ground_estimate_reason": "HEAD_ANCHOR_UNRELIABLE"},
            "substitute": {"observation_ref": "obs:front-4.2", "timestamp_s": substitute_t},
            "time_offset_s": round(substitute_t - original_t, 6), "max_offset_s": 1.0, "skipped_observation_refs": [],
        }
        record.update(overrides)
        return record

    sub_start = endpoint("obs:front-4.2", 4.2, (2.0, 3.0))
    sub_start["substitution"] = substitution(4.4, 4.2)
    sub = run(request(sub_start, endpoint("obs:rear-8.6", 8.6, (8.0, 3.0))), seating_map)
    assert sub["status"] == "READY" and len(sub["endpoint_substitutions"]) == 1
    unconfirmed = [h for h in sub["hypotheses"] if h["checks"]["walkable"]["unconfirmed_area_crossed"]]
    assert unconfirmed and len(unconfirmed) < len(sub["hypotheses"]), "want both verified and unconfirmed mock paths"
    assert any(r["walkable_unknown_sample_indices"] for r in sub["reachable_regions"])

    # Case 4: a substitution that violates the outward-only rule -> UNKNOWN, ENDPOINT_SUBSTITUTION_INVALID.
    bad_start = endpoint("obs:front-4.4", 4.4, (2.0, 3.0))
    bad_start["substitution"] = substitution(4.2, 4.4)  # substitute is *later* than the original: inward
    invalid = run(request(bad_start, endpoint("obs:rear-8.6", 8.6, (8.0, 3.0))), room)
    assert invalid["status"] == "UNKNOWN" and invalid["reason"] == "ENDPOINT_SUBSTITUTION_INVALID", invalid.get("reason")

    # Case 5: D15 restricted-policy crossing. K1 labels a region tier in segments[].tiers (walkable stays TRUE, result PASS);
    # the three contract-v1.1 fields it does not emit yet are patched by hand below (MOCK).
    restricted_tier = "RESTRICTED_POLICY"
    policy_map = PolygonFloorMap(
        descriptor, 0.0,
        {"WALK_W": box(0, 0, 5, 6), "WALK_E": box(5, 0, 10, 6)}, {}, {},
        {"WALK_W": "ANNOTATION_ONLY", "WALK_E": restricted_tier},
    )
    restricted = run(request(endpoint("obs:front-4.4", 4.4, (1.0, 3.0)), endpoint("obs:rear-8.6", 8.6, (9.0, 3.0))), policy_map)
    assert restricted["status"] == "READY"
    for hyp in restricted["hypotheses"]:
        walkable = hyp["checks"]["walkable"]
        assert walkable["result"] == "PASS"
        walkable["restricted_area_crossed"] = any(restricted_tier in seg["tiers"] for seg in walkable["segments"])  # HAND-PATCHED
    assert all(h["checks"]["walkable"]["restricted_area_crossed"] for h in restricted["hypotheses"])
    for region in restricted["reachable_regions"]:  # HAND-PATCHED: cell centres inside the restricted region
        region["restricted_policy_sample_indices"] = [i for i, c in enumerate(region["samples"]) if c[0] >= 5.0]
    restricted["configuration"]["restricted_ref"] = {  # HAND-PATCHED
        "map_ref": "UNKNOWN", "sha256": "0" * 64, "source": "USER_CONFIRMED_ANNOTATION", "tier": restricted_tier}

    cases = {"ready": ready, "unknown": unknown, "substituted_unconfirmed": sub, "substitution_invalid": invalid, "restricted_policy": restricted}
    out = {"fixture_note": NOTE, "generator": "frontend/workbench/fixtures/generate_blind_hypothesis_fixtures.py",
           "k1_source": "claude/k5-pruning @ 726e390 (K1 + K5), synthetic maps; only the restricted_policy case has hand-patched fields", "cases": {}}
    for name, response in cases.items():
        case = copy.deepcopy(response)
        case["fixture_note"] = NOTE
        if name == "restricted_policy":
            case["fixture_note"] = (NOTE + "; HAND-PATCHED fields: checks.walkable.restricted_area_crossed, "
                                    "reachable_regions[].restricted_policy_sample_indices, configuration.restricted_ref")
        out["cases"][name] = case
    text = json.dumps(out, indent=1, sort_keys=True)
    # Keep number-only arrays (cell centres, positions) on one line so the fixture stays reviewable.
    text = re.sub(r"\[\s*(-?[\d.eE+-]+(?:,\s*-?[\d.eE+-]+)*)\s*\]", lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]", text)
    OUT.write_text(text + "\n")
    print(f"wrote {OUT}", {k: (v['status'], len(v['hypotheses'])) for k, v in cases.items()}, "unconfirmed paths:", len(unconfirmed))


if __name__ == "__main__":
    main()
