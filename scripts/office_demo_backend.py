#!/usr/bin/env python3
"""Reproduce existing Office RGB backend; never render or change source/evaluation data."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from wsgiref.simple_server import make_server

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "configs/office_demo_fixture_v1.json"


def raw_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )


def load_scene(bundle: Path, config: dict[str, Any]) -> Any:
    from amidst.workbench.blender_scene import load_blender_scene

    if raw_hash(bundle / "safe_inputs.json") != config["safe_inputs_sha256"]:
        raise ValueError("FIXTURE_SAFE_INPUT_HASH_MISMATCH")
    scene = load_blender_scene(bundle)
    if (
        config["scene_id"] != scene.scene_id
        or config["time_range"] != [0.0, 9.8]
        or config["sampling_hz"] != 5
        or config["reconstruction_rng"] != "NOT_USED"
        or config["source_render_seed"] != "NOT_EXPOSED_BY_SAFE_INPUTS"
    ):
        raise ValueError("FIXTURE_FIXED_SCOPE_MISMATCH")
    binding = scene.live_scope()
    for key in ("source_sha256", "dataset_sha256"):
        if binding[key] != config[key]:
            raise ValueError("FIXTURE_BINDING_MISMATCH:" + key)
    return scene


def application(scene: Any, state: Path, ui_repo: Path, evidence_repo: Path) -> Any:
    from amidst.workbench.blender_association_media import AssociationMediaProvider
    from amidst.workbench.blender_motion_media import MotionMediaProvider
    from amidst.workbench.blender_physical_media import PhysicalMediaProvider
    from amidst.workbench.blender_physical_source import load_physical_source
    from amidst.workbench.reviews import ReviewStore
    from amidst.workbench.service import Application, Workbench

    try:
        scene.bind_physical(load_physical_source(evidence_repo.resolve(), "office"))
    except ValueError:
        pass  # Original observations remain available; physical layer fails closed.
    from amidst.workbench.office_display import attach_office_display

    attach_office_display(scene, ui_repo)
    snapshot = scene.snapshot()
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    reviews = ReviewStore(state, {scene.scene_id: {k: snapshot[k] for k in keys}})
    workbench = Workbench(
        {scene.scene_id: scene},
        reviews,
        motion_media=MotionMediaProvider(
            evidence_repo / "data/engineering/local_run/blender_motion_v1"
        ),
        association_media=AssociationMediaProvider(
            evidence_repo / "data/engineering/local_run/blender_association_v1"
        ),
        physical_media=PhysicalMediaProvider(
            evidence_repo / "data/engineering/local_run/blender_physical_v2"
        ),
    )
    return Application(workbench, ui_repo)


def post(base: str, action: str, value: dict[str, Any]) -> tuple[int, Any]:
    req = Request(
        base + "/api/" + action, json.dumps(value).encode(), {"Content-Type": "application/json"}
    )
    try:
        with urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def reproduce(args: Any) -> None:
    from amidst.domain.camera import Camera
    from amidst.simulation.virtual_camera import project_world
    from amidst.workbench.service import QuietHandler

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    config = json.loads(args.config.read_text())
    scene = load_scene(args.bundle.resolve(), config)
    inputs = scene.export_safe_inputs()
    baseline = scene.index.snapshot()
    manifest = json.loads((args.bundle / "manifest.json").read_text())
    source = Path(manifest["source_path"])
    assert raw_hash(source) == config["source_sha256"]
    assert raw_hash(Path(manifest["dataset_path"])) == config["dataset_sha256"]
    assets = []
    for frame in inputs["frames"]:
        path = Path(frame["local_path"])
        assert raw_hash(path) == frame["sha256"]
        assert path.stat().st_size == frame["byte_count"]
        mime, served = scene.media(frame["frame_ref"])
        assert mime == "image/png"
        assert hashlib.sha256(served).hexdigest() == frame["served_sha256"]
        assets.append(
            {
                k: frame[k]
                for k in (
                    "frame_ref",
                    "camera_id",
                    "timestamp",
                    "local_path",
                    "sha256",
                    "byte_count",
                    "served_sha256",
                )
            }
        )
    assert len(assets) == 100
    for camera in config["camera_ids"]:
        times = sorted(r["timestamp"] for r in assets if r["camera_id"] == camera)
        assert times == [i / 5 for i in range(50)]
    # Independent forward projection of pixel-derived floor intersections, never GT.
    cameras = {r["camera_id"]: Camera.model_validate(r["calibration"]) for r in inputs["cameras"]}
    errors = []
    for observation in scene.index.observations:
        if observation["world_position"] is None:
            continue
        projection = project_world(
            cameras[observation["camera_id"]], tuple(observation["world_position"])
        )
        assert projection.point_2d is not None
        errors.append(math.dist(projection.point_2d, observation["contact_pixel"]))
    assert len(errors) == 31 and max(errors) < 1e-3
    next_time = min(
        r["timestamp"]
        for r in baseline["measurements"]
        if r["timestamp"] > config["selected_timestamp"]
    )
    assert next_time == config["next_observed_timestamp"]
    absent = [
        i / config["sampling_hz"]
        for i in range(50)
        if config["selected_timestamp"] < i / config["sampling_hz"] < next_time
    ]
    assert not [r for r in baseline["measurements"] if r["timestamp"] in absent]
    selected = next(
        r for r in scene.index.observations if r["observation_ref"] == config["observation_ref"]
    )
    assert selected["track_ref"] == config["track_ref"]
    assert selected["timestamp"] == config["selected_timestamp"]
    request = {
        "scene_id": scene.scene_id,
        "camera_ids": config["camera_ids"],
        "start": config["time_range"][0],
        "end": config["time_range"][1],
        "top_k": config["top_k"],
        "observation_ref": config["observation_ref"],
    }
    checks: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="amidst-office-verify-") as tmp:
        app = application(scene, Path(tmp) / "review.sqlite3", args.ui_repo, args.evidence_repo)
        with make_server("127.0.0.1", 0, app, handler_class=QuietHandler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(base + "/api/bootstrap", timeout=10) as response:
                    assert response.status == 200
                status, session = post(base, "session", {"role": "research"})
                assert status == 200
                live = request | {"session_ref": session["session_ref"]}
                status, result = post(base, "target_reconstruction", live)
                assert status == 200 and result["status"] == "READY", (status, result)
                assert post(base, "target_reconstruction", live) == (200, result)
                checks["http_target_repeat_equal"] = True
                status, unknown = post(
                    base,
                    "target_reconstruction",
                    live | {"observation_ref": "observation:" + "0" * 24},
                )
                assert status == 200 and unknown["status"] == "UNKNOWN"
                checks["unknown_does_not_switch_target"] = True
                status, single = post(
                    base, "target_reconstruction", live | {"camera_ids": [selected["camera_id"]]}
                )
                assert status == 200 and single["status"] == "UNKNOWN"
                checks["single_camera_has_no_continuation"] = True
                assert post(base, "target_reconstruction", live | {"top_k": True})[0] == 400
                assert post(base, "target_reconstruction", live | {"ground_truth": {}})[0] == 400
                checks["strict_request_guards"] = True
                # Existing pre-materialized media is optional, never re-encoded here.
                cross_request = {k: v for k, v in live.items() if k != "observation_ref"}
                status, cross = post(base, "cross_camera_reconstruction", cross_request)
                assert status == 200
                artifact = cross["artifacts"]
                write(output / "media_manifest.json", artifact)
                if artifact["status"] == "AVAILABLE":
                    video = next(i for i in artifact["items"] if i["mime_type"] == "video/mp4")
                    media_url = (
                        base
                        + "/api/cross_camera_media?"
                        + urlencode(
                            {
                                "session_ref": session["session_ref"],
                                "scene_id": scene.scene_id,
                                "ref": video["media_ref"],
                            }
                        )
                    )
                    with urlopen(
                        Request(media_url, headers={"Range": "bytes=0-31"}), timeout=10
                    ) as response:
                        assert response.status == 206 and len(response.read()) == 32
                    checks["existing_video_range_http"] = True
                else:
                    checks["existing_video_range_http"] = artifact["status"]
                # Reopen the source image through the issued observation query/media grant.
                status, query = post(
                    base,
                    "query",
                    {
                        "session_ref": session["session_ref"],
                        "scene_id": scene.scene_id,
                        "camera_id": selected["camera_id"],
                        "start": 4.4,
                        "end": 4.4,
                    },
                )
                assert status == 200
                status, detail = post(
                    base,
                    "scene",
                    {"session_ref": session["session_ref"], "scene_id": scene.scene_id},
                )
                assert status == 200
                # frames grants are issued by timeline, see existing frontend sequence.
                status, timeline = post(
                    base,
                    "timeline",
                    {
                        "session_ref": session["session_ref"],
                        "scene_id": scene.scene_id,
                        "camera_ids": config["camera_ids"],
                        "timestamp": 4.4,
                    },
                )
                assert status == 200, timeline
                url = (
                    base
                    + "/api/media?"
                    + urlencode(
                        {
                            "session_ref": session["session_ref"],
                            "scene_id": scene.scene_id,
                            "ref": selected["frame_ref"],
                        }
                    )
                )
                with urlopen(url, timeout=10) as response:
                    served = response.read()
                    assert response.status == 200
                assert hashlib.sha256(served).hexdigest() == next(
                    f["served_sha256"] for f in assets if f["frame_ref"] == selected["frame_ref"]
                )
                checks["actual_source_image_http_hash"] = True
            finally:
                server.shutdown()
                thread.join(timeout=5)
                assert not thread.is_alive()
    association = result["association"]
    paths = [p for c in association["candidates"] for p in c["paths"]]
    assert all(v["speed_m_s"] <= 8 + 1e-9 for p in paths for v in p["velocities"])
    assert all(
        p["world_position"] is None
        for path in paths
        for p in path["samples"]
        if p["state"] == "MISSING"
    )
    assert all(
        p["world_position"] is None
        for path in paths
        for p in path["samples"]
        if 4.4 < p["timestamp"] < 8.6
    )
    checks.update(
        {
            "camera_pixel_roundtrip_max_error_px": max(errors),
            "camera_pixel_roundtrip_points": len(errors),
            "rgb_hashes_verified": 100,
            "timestamp_alignment": True,
            "measurement_gap_preserved": True,
            "no_speed_cap_violations": True,
            "agent_model_calls": 0,
        }
    )
    physical: dict[str, Any]
    try:
        from amidst.workbench.blender_physical_source import load_physical_source

        scene.bind_physical(load_physical_source(args.evidence_repo.resolve(), "office"))
        p = scene.physical_cross_camera_reconstruction(config["camera_ids"], 0, 9.8, 3)
        write(output / "physical_response.json", p)
        physical = {
            "status": "AVAILABLE",
            "search": p["search"],
            "verdicts": [c["physical"]["verdict"] for c in p["candidates"]],
        }
        assert all(v == "UNKNOWN" for v in physical["verdicts"])
    except ValueError as error:
        physical = {"status": "UNAVAILABLE", "reason": str(error)}
    write(
        output / "fixture_manifest.json",
        {
            "configuration": config,
            "bundle": str(args.bundle.resolve()),
            "source": str(source),
            "assets": assets,
            "calibration": inputs["cameras"],
            "source_binding": inputs["source_binding"],
            "floor_plane": inputs["floor_plane"],
            "selected_observation": selected,
        },
    )
    write(output / "request.json", {"session_ref": "<server-issued-session>"} | request)
    write(output / "response.json", result)
    write(output / "source_observations.json", baseline)
    write(output / "source_query.json", query)
    write(
        output / "trace.json",
        {
            "mode": "DETERMINISTIC",
            "agent_used": False,
            "model_calls": 0,
            "agent_attempted": False,
            "deterministic_trigger": "OFFICE_AGENT_TOOLS_NOT_CONFIGURED",
            "algorithm_trace": result["trace"],
            "physical": physical,
        },
    )
    write(output / "validation.json", checks)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    code_paths = [
        "scripts/office_demo_backend.py",
        "configs/office_demo_fixture_v1.json",
        "src/amidst/workbench/target_reconstruction.py",
        "src/amidst/workbench/service.py",
        "src/amidst/workbench/blender_scene.py",
        "src/amidst/workbench/frame_baseline.py",
        "src/amidst/workbench/blender_motion.py",
        "src/amidst/workbench/blender_association.py",
    ]
    receipt = {
        "schema_version": "office-demo.run.v1",
        "run_id": output.name,
        "commit": commit,
        "config_sha256": raw_hash(args.config),
        "code_hashes": {p: raw_hash(REPO / p) for p in code_paths},
        "response_canonical_sha256": canonical(result),
        "checks": checks,
        "files": {p.name: raw_hash(p) for p in sorted(output.iterdir()) if p.is_file()},
        "limitations": config["limitations"],
        "physical": physical,
        "interactive_acceptance": "NOT_TESTED",
    }
    write(output / "receipt.json", receipt)
    print(
        json.dumps(
            {
                "run_id": output.name,
                "status": "PASS",
                "checks": checks,
                "response_canonical_sha256": canonical(result),
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "_run", "serve", "replay"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--evidence-repo", type=Path, default=REPO)
    parser.add_argument("--ui-repo", type=Path, default=REPO)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if not 0 < args.timeout <= 60:
        parser.error("timeout must be in (0, 60]")
    if args.mode == "replay":
        receipt = json.loads((args.output / "receipt.json").read_text())
        for name, digest in receipt["files"].items():
            assert Path(name).name == name and raw_hash(args.output / name) == digest
        result = json.loads((args.output / "response.json").read_text())
        assert canonical(result) == receipt["response_canonical_sha256"]
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "mode": "RECORDED_REPLAY",
                    "model_calls": 0,
                    "response_canonical_sha256": canonical(result),
                }
            )
        )
    elif args.mode == "run":
        if args.bundle is None or args.output is None:
            parser.error("run requires --bundle and new --output")
        command = [sys.executable, str(Path(__file__).resolve()), "_run", *sys.argv[2:]]
        try:
            subprocess.run(command, timeout=args.timeout, check=True)
        except subprocess.TimeoutExpired:
            print(
                json.dumps(
                    {
                        "status": "UNKNOWN",
                        "reason": "DEMO_RUN_HARD_TIMEOUT",
                        "timeout_s": args.timeout,
                    }
                ),
                flush=True,
            )
            raise SystemExit(2) from None
    elif args.mode == "_run":
        reproduce(args)
    else:
        from amidst.workbench.service import QuietHandler

        if args.bundle is None:
            parser.error("serve requires --bundle")
        scene = load_scene(args.bundle.resolve(), json.loads(args.config.read_text()))
        with tempfile.TemporaryDirectory(prefix="amidst-office-server-") as tmp:
            app = application(
                scene, Path(tmp) / "review.sqlite3", args.ui_repo.resolve(), args.evidence_repo
            )
            with make_server("127.0.0.1", args.port, app, handler_class=QuietHandler) as server:
                print(f"OFFICE_DEMO_URL=http://127.0.0.1:{server.server_port}/", flush=True)
                server.serve_forever()


if __name__ == "__main__":
    main()
