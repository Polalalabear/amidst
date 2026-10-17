"""K8 synthetic Office scenarios S1 / S2 / S3 (task K8b, design D23 §2–§8).

Declared inputs only: point endpoints, candidate REAR appearances and rectangular
"visible floor" footprints for two synthetic cameras. K1 and K5 are called as
shipped; the S3 evidence goes through K5 ``negative_evidence_from_retrieval`` with
the trusted ``data_origin="SYNTHETIC"`` switch, exactly like the real frame wall.
No ground truth exists here (design §6: the K8d evaluator owns it), and no K1
request carries anything but the contract fields.

The result is deterministic: same inputs and code give the same ``fixture_sha256``.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from shapely.geometry import shape

from amidst.blind_hypothesis import (
    FloorMapDescriptor,
    PolygonFloorMap,
    canonical_sha256,
    generate_blind_hypotheses,
    negative_evidence_from_retrieval,
    pruning_convergence_summary,
)
from amidst.blind_hypothesis.candidate_screen import screen_cross_camera_candidates
from amidst.blind_hypothesis.engine import REQUEST_SCHEMA, SYNTHETIC_VISIBILITY_METHOD

FIXTURE_SCHEMA = "workbench.k8-synthetic-fixture.v1"
DATA_ORIGIN = "SYNTHETIC"
SCENE_ID = "synthetic-office-k8"
RUN_REF = "synthetic:k8-office-v1"
CLOCK_ID = "SYNTHETIC_K8_5HZ"
SESSION_REF = "session:k8-synthetic"
GENERATOR_VERSION = "k8b-v1"

C7_MAP_NAME = "C7_OFFICE_SOURCE_MAP_20261017.json"
C7_MAP_REPO_PATH = f"docs/engineering/{C7_MAP_NAME}"
C7_MAP_SHA256 = "53c3771327ad71e26f0a5f1f4db580eaafb7bc7d028b9c250c9f401495bbcd61"
C7_MAP_ENV = "K8_C7_MAP"
# Codex branches that hold the C7 map (identical blob 6ac4bba); only the file hash is
# verified at run time.
C7_MAP_GIT_REFS = ("origin/codex/c5-d21-strict-visibility", "origin/codex/c7-source-map")
MAP_VARIANT = "person"

T0_S = 10.0
SENSOR_STEP_S = 0.2
POINT_RADIUS_M = 0.15
TOP_K = 3
FRAME_TIMES_S = tuple(round(T0_S + 1.0 + SENSOR_STEP_S * i, 1) for i in range(21))  # 11.0..15.0

CAM_A, CAM_B = "SYN_CAM_A", "SYN_CAM_B"
CAM_NORTH, CAM_SOUTH = "SYN_CAM_N", "SYN_CAM_S"
START_XY = (38.60, 49.93)
END_XY = (45.20, 49.93)

# Declared (hand-drawn) visible floor of the two synthetic cameras; not ray-cast.
NORTH_FOOTPRINT = [[[39.0, 50.3], [44.8, 50.3], [44.8, 51.6], [39.0, 51.6], [39.0, 50.3]]]
SOUTH_FOOTPRINT = [[[39.0, 48.0], [44.8, 48.0], [44.8, 49.4], [39.0, 49.4], [39.0, 48.0]]]

# Declared detector record; values copied from C5 D21 ``rgb-mask-contact-v2`` so the
# frame wall shows comparable parameters. Integers on purpose (K5 compares types).
DETECTOR = {
    "producer": "synthetic-k8",
    "version": "v1",
    "difference_threshold": 30,
    "min_pixels": 28,
}
VISIBILITY_RULE = "FOOT_AND_TORSO_PROBES_VISIBLE"

# S2 candidates (design §4): ref, camera, position, appearance time.
S2_CANDIDATES = (
    ("synthetic-candidate:R1", CAM_B, END_XY, T0_S + 6.0),
    ("synthetic-candidate:R2", CAM_B, (27.00, 40.00), T0_S + 6.0),
    ("synthetic-candidate:R3", CAM_B, END_XY, T0_S + 3.2),
)

# Fields that must never appear in anything handed to K1/K5 or written to the
# fixture (D1/D9): ground truth, renderer trajectories, visibility and depth.
FORBIDDEN_KEYS = frozenset(
    {
        "ground_truth",
        "gt",
        "truth",
        "truth_trajectory",
        "renderer_trajectory",
        "trajectory",
        "visibility_gt",
        "depth",
    }
)


class SyntheticFixtureError(RuntimeError):
    """A pinned input does not match (map hash, config hash) or a check failed."""


# ----------------------------------------------------------------------- hashing


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    """The git blob id of ``data`` (computed, no git call)."""

    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()  # noqa: S324


def file_identity(path: Path) -> dict[str, str]:
    data = path.read_bytes()
    return {"git_blob": git_blob_sha1(data), "sha256": sha256_bytes(data)}


# ------------------------------------------------------------------- map / config


def locate_c7_map(repo_root: Path | None = None) -> Path | None:
    """Find the C7 map file: ``$K8_C7_MAP``, the repository path, or a Codex git ref.

    The file is never copied into this repository. A git ref is read with ``git show``
    into a temporary file next to the build output; the caller verifies the SHA-256.
    Returns ``None`` when no source has it (UNKNOWN: ask for the Codex branch).
    """

    env = os.environ.get(C7_MAP_ENV)
    if env and Path(env).is_file():
        return Path(env)
    root = repo_root or Path(__file__).resolve().parents[3]
    local = root / C7_MAP_REPO_PATH
    if local.is_file():
        return local
    for ref in C7_MAP_GIT_REFS:
        shown = subprocess.run(  # noqa: S603
            ["git", "-C", str(root), "show", f"{ref}:{C7_MAP_REPO_PATH}"],  # noqa: S607
            capture_output=True,
            check=False,
        )
        if shown.returncode == 0 and sha256_bytes(shown.stdout) == C7_MAP_SHA256:
            cache = Path(os.environ.get("TMPDIR", "/tmp")) / f"k8_c7_{C7_MAP_SHA256[:12]}.json"
            cache.write_bytes(shown.stdout)
            return cache
    return None


def load_c7_bundle(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if sha256_bytes(data) != C7_MAP_SHA256:
        raise SyntheticFixtureError("MAP_BUNDLE_HASH_MISMATCH")
    bundle: dict[str, Any] = json.loads(data)
    if bundle["annotations_as_inputs"] or bundle["gt_read"]:
        raise SyntheticFixtureError("MAP_SOURCE_AUTHORITY_MISMATCH")
    return bundle


def floor_map_from_bundle(bundle: Mapping[str, Any], variant: str = MAP_VARIANT) -> PolygonFloorMap:
    """K1 floor map from the C7 variant, with the descriptor C4b uses.

    Mirrors Codex's ``load_polygon_floor_map`` (C7, not on this branch) so the K1
    response carries the same ``map_ref``; the bytes were pinned by SHA-256 above.
    """

    chosen = bundle["variants"][variant]
    ref = "source-map:" + C7_MAP_SHA256[:24]
    descriptor = FloorMapDescriptor(
        kind="SOURCE_DERIVED",
        map_ref=ref,
        sha256=C7_MAP_SHA256,
        walkable_ref=f"{ref}#{variant}/regions",
        portal_ref=f"{ref}#{variant}/portals",
        floor_id="1F",
    )
    return PolygonFloorMap(
        descriptor=descriptor,
        floor_z_m=chosen["floor_z_m"],
        regions={r["region_id"]: shape(r["geometry"]) for r in chosen["regions"]},
        portals={r["portal_id"]: shape(r["geometry"]) for r in chosen["portals"]},
        unknown_regions={r["region_id"]: shape(r["geometry"]) for r in chosen["unknown_regions"]},
        region_tiers={
            r["region_id"]: r["tier"] for r in chosen["regions"] + chosen["unknown_regions"]
        },
    )


def load_k8_config(path: Path) -> tuple[dict[str, Any], str]:
    data = path.read_bytes()
    config: dict[str, Any] = json.loads(data)
    scene = config["scenes"][SCENE_ID]
    if scene.get("data_origin") != DATA_ORIGIN:
        raise SyntheticFixtureError("K8 config scene is not data_origin SYNTHETIC")
    if scene["floor_map"]["geometry_sha256"] != C7_MAP_SHA256:
        raise SyntheticFixtureError("K8 config pins a different map")
    return config, sha256_bytes(data)


def source_binding() -> dict[str, str]:
    """Synthetic run binding; never borrows a real run, source or safe-inputs hash."""

    return {
        "run_ref": RUN_REF,
        "clock_id": CLOCK_ID,
        "source_sha256": "SYNTHETIC_NONE",
        "safe_inputs_sha256": "SYNTHETIC_NONE",
    }


# ----------------------------------------------------------------- endpoints / K1


def endpoint(tag: str, camera: str, t_s: float, xy: Sequence[float], floor_z_m: float) -> dict:
    """One simulated-sensor endpoint (``interval-observation v1``, POINT)."""

    ref = f"synthetic-observation:{tag}"
    estimate = {
        "schema_version": "office-demo.interval-observation.v1",
        "observation_ref": ref,
        "camera_id": camera,
        "timestamp_s": t_s,
        "status": "READY",
        "reason": None,
        "evidence_state": "PROJECTED_OBSERVATION",
        "estimate_kind": "POINT",
        "point_m": [xy[0], xy[1], floor_z_m],
        "pixel_sensitivity_m": POINT_RADIUS_M,
        "contact_quality": {"status": "PASS"},
        "provenance": {"gt_read": False, "data_origin": DATA_ORIGIN},
    }
    return {
        "observation_ref": ref,
        "camera_id": camera,
        "timestamp_s": t_s,
        "evidence_state": "PROJECTED_OBSERVATION",
        "ground_estimate": estimate,
    }


def k1_request(
    start: Mapping[str, Any],
    end: Mapping[str, Any],
    *,
    candidate_ref: str | None = None,
    evidence: Sequence[Mapping[str, Any]] = (),
    previous_sha256: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": REQUEST_SCHEMA,
        "session_ref": SESSION_REF,
        "scene_id": SCENE_ID,
        "candidate_ref": candidate_ref,
        "start": copy.deepcopy(dict(start)),
        "end": copy.deepcopy(dict(end)),
        "top_k": TOP_K,
        "negative_evidence": copy.deepcopy(list(evidence)),
        "previous_response_sha256": previous_sha256,
    }


def declared_index_ref() -> dict[str, str]:
    """Reference for the declared footprints (not a C5 index)."""

    return {
        "index_ref": "synthetic-declared-footprints:k8-v1",
        "sha256": canonical_sha256(_declared_geometry()),
        "method": SYNTHETIC_VISIBILITY_METHOD,
    }


def _declared_geometry() -> dict[str, Any]:
    return {CAM_NORTH: NORTH_FOOTPRINT, CAM_SOUTH: SOUTH_FOOTPRINT}


class _Context:
    """Bound inputs shared by the scenario runners."""

    def __init__(self, config: Mapping[str, Any], config_sha256: str, floor_map: PolygonFloorMap):
        self.config = config
        self.config_sha256 = config_sha256
        self.floor_map = floor_map
        self.binding = source_binding()

    @property
    def floor_z(self) -> float:
        return self.floor_map.floor_z_m

    def run(
        self,
        request: dict[str, Any],
        *,
        previous: Mapping[str, Any] | None = None,
        index_ref: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return generate_blind_hypotheses(
            request,
            config=self.config,
            config_sha256=self.config_sha256,
            floor_map=self.floor_map,
            source_binding=self.binding,
            visibility_index_ref=index_ref,
            previous_response=previous,
        )


def reachable_area_m2(response: Mapping[str, Any]) -> float:
    return round(sum(r.get("area_m2", 0.0) for r in response["reachable_regions"]), 3)


# ------------------------------------------------------------- K5 synthetic frames


def _retrieval_response(camera: str, name: str) -> dict[str, Any]:
    """A synthetic ``workbench.frame-retrieval.v1`` response for one camera."""

    method = SYNTHETIC_VISIBILITY_METHOD
    frames = [
        {
            "frame_ref": f"synthetic-frame:{camera}:{t:.1f}",
            "timestamp_s": t,
            "reason": {
                "kind": "REACHABLE_REGION_IN_VIEW",
                "footprint_method": method,
                "walkable_status": "TRUE",
            },
        }
        for t in FRAME_TIMES_S
    ]
    return {
        "schema_version": "workbench.frame-retrieval.v1",
        "status": "READY",
        "reason": None,
        "query_id": f"synthetic-query:k8-{name}",
        "query": {
            "query_kind": "HYPOTHESIS",
            "endpoint_substitutions": None,
            "hypothesis_interval": {"start_s": T0_S, "end_s": T0_S + 6.0},
        },
        "results": [
            {
                "camera_id": camera,
                "visibility_ref": f"synthetic-visibility:{camera}",
                "method": method,
                "windows": [
                    {
                        "start_s": frames[0]["timestamp_s"],
                        "end_s": frames[-1]["timestamp_s"],
                        "frames": frames,
                    }  # fmt: skip
                ],
            }
        ],
    }


def _frame_evaluations(retrieval: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Declared perception lookup: no detection in any frame (``measurement_count`` 0)."""

    return {
        frame["frame_ref"]: {
            "frame_available": True,
            "rgb_hash_verified": True,
            "provenance_ok": True,
            "perception_evaluated": True,
            "measurement_count": 0,
            "detection_producer": dict(DETECTOR),
        }
        for result in retrieval["results"]
        for window in result["windows"]
        for frame in window["frames"]
    }


def _visibility_entries(camera: str, polygons: list, floor_z_m: float) -> dict[str, Any]:
    return {
        f"synthetic-visibility:{camera}": {
            "method": SYNTHETIC_VISIBILITY_METHOD,
            "floor_z_m": floor_z_m,
            "polygons": copy.deepcopy(polygons),
            "index_sha256": canonical_sha256({"camera_id": camera, "polygons": polygons}),
            "visibility_rule": VISIBILITY_RULE,
            "detectability": {"detector": dict(DETECTOR)},
        }
    }


def synthetic_negative_evidence(
    camera: str,
    name: str,
    polygons: list,
    floor_z_m: float,
    *,
    applied_refs: Sequence[str] = (),
    applied_frame_keys: Sequence[Sequence[str]] = (),
) -> dict[str, Any]:
    """S3 evidence through K5 (``data_origin="SYNTHETIC"`` set by this trusted caller)."""

    retrieval = _retrieval_response(camera, name)
    converted = negative_evidence_from_retrieval(
        retrieval,
        frame_evaluations=_frame_evaluations(retrieval),
        visibility_entries=_visibility_entries(camera, polygons, floor_z_m),
        interval_s=[T0_S, T0_S + 6.0],
        applied_negative_evidence_refs=applied_refs,
        applied_frame_keys=applied_frame_keys,
        data_origin=DATA_ORIGIN,
    )
    return {"retrieval": retrieval, "converted": converted}


# ------------------------------------------------------------------- scenarios


def run_s1(ctx: _Context) -> dict[str, Any]:
    start = endpoint("s1-start", CAM_A, T0_S, START_XY, ctx.floor_z)
    end = endpoint("s1-end", CAM_B, T0_S + 6.0, END_XY, ctx.floor_z)
    request = k1_request(start, end)
    response = ctx.run(request, index_ref=declared_index_ref())
    return {"request": request, "response": response}


def run_s2(ctx: _Context) -> dict[str, Any]:
    start = endpoint("s2-start", CAM_A, T0_S, START_XY, ctx.floor_z)
    candidates = [
        {
            "candidate_ref": ref,
            "end": endpoint(f"s2-{ref.rsplit(':', 1)[1].lower()}", cam, t, xy, ctx.floor_z),
        }
        for ref, cam, xy, t in S2_CANDIDATES
    ]
    base = {"session_ref": SESSION_REF, "scene_id": SCENE_ID, "top_k": TOP_K,
            "negative_evidence": []}  # fmt: skip
    screen = screen_cross_camera_candidates(
        start,
        candidates,
        base_request=base,
        config=ctx.config,
        config_sha256=ctx.config_sha256,
        floor_map=ctx.floor_map,
        source_binding=ctx.binding,
    )
    # The screen keeps responses by hash only; re-run each pair with the identical
    # request to embed the full K1 response, and check it is the one that was screened.
    requests: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    for candidate, row in zip(candidates, screen["results"], strict=True):
        request = k1_request(start, candidate["end"], candidate_ref=candidate["candidate_ref"])
        response = ctx.run(request)
        if response["output_sha256"] != row["k1_response_sha256"]:
            raise SyntheticFixtureError(f"S2 {candidate['candidate_ref']}: response hash drift")
        requests.append(request)
        responses.append(response)
    return {"screen": screen, "requests": requests, "responses": responses}


def run_s3(ctx: _Context, s1: Mapping[str, Any]) -> dict[str, Any]:
    start, end = s1["request"]["start"], s1["request"]["end"]
    base = s1["response"]
    north = synthetic_negative_evidence(CAM_NORTH, "north", NORTH_FOOTPRINT, ctx.floor_z)
    north_entries = north["converted"]["negative_evidence_candidates"]
    request1 = k1_request(start, end, evidence=north_entries, previous_sha256=base["output_sha256"])
    response1 = ctx.run(request1, previous=base, index_ref=declared_index_ref())
    south = synthetic_negative_evidence(
        CAM_SOUTH,
        "south",
        SOUTH_FOOTPRINT,
        ctx.floor_z,
        applied_refs=[e["negative_evidence_ref"] for e in north_entries],
    )
    south_entries = south["converted"]["negative_evidence_candidates"]
    request2 = k1_request(
        start,
        end,
        evidence=[*north_entries, *south_entries],
        previous_sha256=response1["output_sha256"],
    )
    response2 = ctx.run(request2, previous=response1, index_ref=declared_index_ref())
    steps = [
        {"step": 0, "label": "NO_EVIDENCE", "request": s1["request"], "response": base},
        {
            "step": 1,
            "label": "NORTH_NO_DETECTION",
            "k5": _k5_summary(north),
            "request": request1,
            "response": response1,
        },  # fmt: skip
        {
            "step": 2,
            "label": "NORTH_AND_SOUTH_NO_DETECTION",
            "k5": _k5_summary(south),
            "request": request2,
            "response": response2,
        },  # fmt: skip
    ]
    return {
        "steps": steps,
        "convergence": pruning_convergence_summary([base, response1, response2]),
        "reachable_area_m2": [reachable_area_m2(s["response"]) for s in steps],
    }


def _k5_summary(evidence: Mapping[str, Any]) -> dict[str, Any]:
    converted = evidence["converted"]
    outcomes = converted["frame_outcomes"]
    return {
        "converter": "amidst.blind_hypothesis.negative_evidence_from_retrieval",
        "data_origin": converted["data_origin"],
        "retrieval_query_id": evidence["retrieval"]["query_id"],
        "frame_count": len(outcomes),
        "eligible_frame_count": sum(1 for o in outcomes if o["negative_evidence_eligible"]),
        "outcomes": sorted({f"{o['outcome']}/{o['reason']}" for o in outcomes}),
        "negative_evidence_refs": [
            e["negative_evidence_ref"] for e in converted["negative_evidence_candidates"]
        ],
        "interval_s": converted["interval_s"],
    }


# ------------------------------------------------------------------ fixture build


def _map_for_display(bundle: Mapping[str, Any]) -> dict[str, Any]:
    variant = bundle["variants"][MAP_VARIANT]
    return {
        "variant": MAP_VARIANT,
        "map_sha256": C7_MAP_SHA256,
        "floor_z_m": variant["floor_z_m"],
        "physical_navigation": bundle["physical_navigation"],
        "regions": [
            {"region_id": r["region_id"], "tier": r["tier"], "geometry": r["geometry"]}
            for r in variant["regions"]
        ],
        "portals": [
            {"portal_id": p["portal_id"], "geometry": p["geometry"]} for p in variant["portals"]
        ],
    }


def _scan_forbidden(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                hits.append(f"{path}.{key}")
            hits += _scan_forbidden(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits += _scan_forbidden(item, f"{path}[{index}]")
    return hits


def build_fixture(
    *,
    c7_map_path: Path,
    config_path: Path,
    engine_files: Mapping[str, Path],
    generator_files: Mapping[str, Path],
    upstream: Mapping[str, Any],
) -> dict[str, Any]:
    """Run S1/S2/S3 and assemble the fixture mapping (``fixture_sha256`` filled)."""

    bundle = load_c7_bundle(c7_map_path)
    config, config_sha256 = load_k8_config(config_path)
    floor_map = floor_map_from_bundle(bundle)
    ctx = _Context(config, config_sha256, floor_map)
    s1 = run_s1(ctx)
    s2 = run_s2(ctx)
    s3 = run_s3(ctx, s1)
    for name, outcome in (("S1", s1["response"]), ("S3", s3["steps"][2]["response"])):
        if outcome["status"] != "READY":
            raise SyntheticFixtureError(f"{name}: K1 status {outcome['status']}")

    fixture: dict[str, Any] = {
        "schema_version": FIXTURE_SCHEMA,
        "data_origin": DATA_ORIGIN,
        "scene_id": SCENE_ID,
        "watermark": "SYNTHETIC 合成資料",
        "evidence_notice": (
            "Declared endpoints, cameras, footprints and detections on the Office map; "
            "not observations. Identity UNCONFIRMED; physical navigation UNKNOWN."
        ),
        "provenance": {
            "data_origin": DATA_ORIGIN,
            "generator": {
                "version": GENERATOR_VERSION,
                "files": {name: file_identity(p) for name, p in sorted(generator_files.items())},
                "deterministic": True,
                "seed": None,
                "seed_note": "No randomness: all endpoints, footprints and times are declared.",
            },
            "gt_read": False,
            "ground_truth_in_requests": False,
            "run_ref": RUN_REF,
            "clock_id": CLOCK_ID,
            "source_sha256": "SYNTHETIC_NONE",
            "safe_inputs_sha256": "SYNTHETIC_NONE",
            "map_sha256": C7_MAP_SHA256,
            "map_source": {
                "path": C7_MAP_REPO_PATH,
                "variant": MAP_VARIANT,
                "git_refs_checked": list(C7_MAP_GIT_REFS),
                "note": "Codex C7 file (#40/#44); not copied into this repository. Hash-pinned.",
            },
            "config": {
                "path": "configs/k8_synthetic_blind_hypothesis_v1.json",
                "sha256": config_sha256,
                "parent_config_ref": config["parent_config_ref"],
                "parent_config_sha256": config["parent_config_sha256"],
            },
            "engine_files": {name: file_identity(p) for name, p in sorted(engine_files.items())},
            "upstream": dict(upstream),
            "detection_producer": dict(DETECTOR),
            "visibility_method": SYNTHETIC_VISIBILITY_METHOD,
            "declared_footprints": _declared_geometry(),
        },
        "map": _map_for_display(bundle),
        "cameras": [
            {"camera_id": c, "role": r, "rendered": False}
            for c, r in (
                (CAM_A, "START"),
                (CAM_B, "END_AND_CANDIDATES"),
                (CAM_NORTH, "DECLARED_NEGATIVE_EVIDENCE"),
                (CAM_SOUTH, "DECLARED_NEGATIVE_EVIDENCE"),
            )
        ],
        "scenarios": {
            "S1": {"title": "top-k multi-hypothesis", **s1},
            "S2": {"title": "cross-camera candidate screen", **s2},
            "S3": {"title": "negative-evidence pruning", **s3},
        },
    }
    hits = _scan_forbidden(fixture)
    if hits:
        raise SyntheticFixtureError(f"forbidden ground-truth-like keys: {hits}")
    fixture["fixture_sha256"] = canonical_sha256(fixture)
    return fixture


def dump_fixture(fixture: Mapping[str, Any]) -> str:
    """Stable text form written to disk."""

    return json.dumps(fixture, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
