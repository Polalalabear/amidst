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

from amidst.workbench.scene_errors import DataIntegrityError, integrity_error, public_reason

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "configs/office_demo_fixture_v1.json"
DEFAULT_PRESETS = REPO / "configs/office_demo_presets_v1.json"


def assets_repo() -> Path:
    common = subprocess.check_output(
        ["git", "rev-parse", "--git-common-dir"], cwd=REPO, text=True).strip()
    return (REPO / common).resolve().parent


def preset_specs(presets: Path, evidence_repo: Path, asset_repo: Path,
                 office_bundle: Path | None = None) -> tuple[str, list[dict[str, Any]]]:
    value = json.loads(presets.read_text())
    if value["schema_version"] != "office-demo.presets.v1":
        raise ValueError("INVALID_PRESET_SCHEMA")
    specs, seen = [], set()
    for entry in value["presets"]:
        scene_id = entry["scene_id"]
        if scene_id in seen:
            raise ValueError("DUPLICATE_PRESET_SCENE")
        seen.add(scene_id)
        fixture_path = (REPO / entry["fixture"]).resolve()
        error = None
        try:
            fixture = json.loads(fixture_path.read_text())
            if fixture["scene_id"] != scene_id:
                raise DataIntegrityError("PRESET_FIXTURE_SCENE_MISMATCH")
        except (OSError, ValueError, KeyError) as failure:
            if scene_id == value["default_scene_id"] or integrity_error(failure):
                raise
            fixture, error = None, unavailable_reason(failure)
        root = {"evidence": evidence_repo, "assets": asset_repo}[entry["bundle_root"]]
        bundle = (root / entry["bundle"]).resolve()
        if scene_id == "blender-office" and office_bundle is not None:
            bundle = office_bundle.resolve()
        specs.append(entry | {"fixture_path": fixture_path, "config": fixture,
                              "bundle_path": bundle, "load_error": error})
    default = value["default_scene_id"]
    if default not in seen:
        raise ValueError("DEFAULT_PRESET_MISSING")
    specs.sort(key=lambda row: row["scene_id"] != default)
    return default, specs


class PresetCatalog(dict):
    """Only loaded adapters enter the catalog; failures remain public metadata."""
    def __init__(self):
        super().__init__()
        self.unavailable = []


def unavailable_reason(error: Exception) -> str:
    if isinstance(error, FileNotFoundError):
        return "PRESET_DATA_MISSING"
    if isinstance(error, OSError):
        return "PRESET_DATA_UNAVAILABLE"
    return public_reason(error, "PRESET_LOAD_FAILED")


def validate_bundle_files(bundle: Path, config: dict[str, Any]) -> None:
    # Hash verification precedes trusting any safe-input media locator.
    if raw_hash(bundle / "safe_inputs.json") != config["safe_inputs_sha256"]:
        raise DataIntegrityError("FIXTURE_SAFE_INPUT_HASH_MISMATCH")
    manifest = json.loads((bundle / "manifest.json").read_text())
    safe = json.loads((bundle / "safe_inputs.json").read_text())
    for key in ("source_path", "dataset_path", "asset_root"):
        if not Path(manifest[key]).exists():
            raise FileNotFoundError("PRESET_DATA_MISSING")
    frames = safe["frames"]
    if len(frames) != 100 or {f["camera_id"] for f in frames} != set(config["camera_ids"]):
        raise DataIntegrityError("PRESET_FRAME_CAMERA_MISMATCH")
    for frame in frames:
        path = Path(frame["local_path"])
        if not path.exists():
            raise FileNotFoundError("PRESET_DATA_MISSING")
        if (path.is_symlink() or not path.resolve().is_relative_to(Path(manifest["asset_root"]))
                or path.stat().st_size != frame["byte_count"]):
            raise DataIntegrityError("PRESET_MEDIA_INTEGRITY_MISMATCH")


def load_presets(presets: Path, evidence_repo: Path, asset_repo: Path,
                 office_bundle: Path | None = None) -> PresetCatalog:
    default, specs = preset_specs(presets, evidence_repo, asset_repo, office_bundle)
    catalog = PresetCatalog()
    for spec in specs:
        try:
            if spec["load_error"]:
                raise ValueError(spec["load_error"])
            scene = load_scene(spec["bundle_path"], spec["config"],
                               perception_version=spec["perception_version"])
            scene = scene.with_display_identity(
                spec["scene_id"], spec["label"], spec["description"])
            if scene.scene_id != "blender-office":
                config = spec["config"]
                selected = next((r for r in scene.index.observations
                                 if r["observation_ref"] == config["observation_ref"]), None)
                if selected is None or selected["timestamp"] != config["selected_timestamp"]:
                    raise ValueError("PRESET_DEFAULT_OBSERVATION_MISMATCH")
                scene._snapshot["demo_defaults"] = {key: config[key] for key in
                    ("observation_ref", "selected_timestamp", "camera_ids", "time_range", "top_k")}
            if spec.get("hypothesis_binding"):
                from amidst.workbench.blind_hypothesis_integration import bind_hypotheses
                bind_hypotheses(scene, spec["fixture_path"], REPO, spec["hypothesis_binding"])
            catalog[scene.scene_id] = scene
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
            if spec["scene_id"] == default or integrity_error(error):
                raise
            catalog.unavailable.append({key: spec[key] for key in
                ("scene_id", "label", "description")} | {"status": "UNAVAILABLE",
                "available": False, "reason": unavailable_reason(error),
                "product_available": False})
    return catalog


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


def contact_config_path(config):
    path = REPO / config.get("contact_config", "configs/office_contact_v2.json")
    if not path.resolve().is_relative_to((REPO / "configs").resolve()) or path.is_symlink():
        raise DataIntegrityError("FIXTURE_CONTACT_CONFIG_PATH_REJECTED")
    if "contact_config" in config and raw_hash(path) != config["contact_config_sha256"]:
        raise DataIntegrityError("FIXTURE_CONTACT_CONFIG_HASH_MISMATCH")
    return path


def load_scene(bundle: Path, config: dict[str, Any], *,
               perception_version: str = "rgb-mask-contact-v1") -> Any:
    from amidst.engineering.perception_v2 import ContactConfig
    from amidst.workbench.blender_scene import ValidationRunPin
    from amidst.workbench.contact_scene import ContactQualityScene

    validate_bundle_files(bundle, config)
    pin = ValidationRunPin(**config["validation_pin"]) if "validation_pin" in config else None
    hybrid_bytes = (REPO / "configs/hybrid_contact_v1_1.json").read_bytes()
    scene = ContactQualityScene(bundle, validation_pin=pin,
        perception_version=perception_version,
        hybrid_config=json.loads(hybrid_bytes),
        hybrid_config_sha256=hashlib.sha256(hybrid_bytes).hexdigest(),
        contact_config=ContactConfig.model_validate_json(
            contact_config_path(config).read_bytes()))
    if (config["time_range"] != [0.0, 9.8] or config["sampling_hz"] != 5
            or config["reconstruction_rng"] != "NOT_USED"
            or config["source_render_seed"] != "NOT_EXPOSED_BY_SAFE_INPUTS"):
        raise ValueError("FIXTURE_FIXED_SCOPE_MISMATCH")
    binding = scene.live_scope()
    for key in ("source_sha256", "dataset_sha256", "run_id", "clock_id"):
        if key in config and binding[key] != config[key]:
            raise ValueError("FIXTURE_BINDING_MISMATCH:" + key)
    if sorted(config["camera_ids"]) != sorted(r["camera_id"] for r in scene._inputs["cameras"]):
        raise ValueError("FIXTURE_CAMERA_MISMATCH")
    return scene


class SceneMediaProvider:
    """Route optional materialized artifacts by catalog identity before provider validation."""
    def __init__(self, providers):
        self.providers = providers

    def manifest(self, scene, *args):
        provider = self.providers.get(scene.scene_id)
        if provider is None:
            return {"status": "UNAVAILABLE", "items": [], "reason": "NOT_MATERIALIZED_FOR_RUN"}
        return provider.manifest(scene, *args)

    def media(self, scene, ref):
        provider = self.providers.get(scene.scene_id)
        if provider is None:
            raise ValueError("MEDIA_NOT_MATERIALIZED_FOR_RUN")
        return provider.media(scene, ref)


def application(scene: Any, state: Path, ui_repo: Path, evidence_repo: Path, *,
                assets_root: Path | None = None) -> Any:
    from amidst.workbench.blender_association_media import AssociationMediaProvider
    from amidst.workbench.blender_motion_media import MotionMediaProvider
    from amidst.workbench.blender_physical_media import PhysicalMediaProvider
    from amidst.workbench.blender_physical_source import load_physical_source
    from amidst.workbench.controlled_scene_rgb_api import ControlledRGBAPI
    from amidst.workbench.controlled_scene_rgb_data import registrations
    from amidst.workbench.reviews import ReviewStore
    from amidst.workbench.service import Application, Workbench

    catalog = scene if isinstance(scene, dict) else {scene.scene_id: scene}
    office = catalog.get("blender-office")
    if office is not None:
        try:
            office.bind_physical(load_physical_source(evidence_repo.resolve(), "office"))
        except (OSError, ValueError):
            pass  # This optional layer fails closed, independently of other scenes.
        from amidst.workbench.office_display import attach_office_display

        attach_office_display(office, ui_repo)
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    bindings = {}
    for item in catalog.values():
        snapshot = item.snapshot()
        bindings[item.scene_id] = {k: snapshot[k] for k in keys}
    reviews = ReviewStore(state, bindings)
    def provider(factory, directory):
        return SceneMediaProvider({"blender-office": factory(
            evidence_repo / "data/engineering/local_run" / directory)} if office else {})
    workbench = Workbench(catalog, reviews,
        controlled_scene=ControlledRGBAPI(registrations((assets_root or assets_repo()).resolve())),
        motion_media=provider(MotionMediaProvider, "blender_motion_v1"),
        association_media=provider(AssociationMediaProvider, "blender_association_v1"),
        physical_media=provider(PhysicalMediaProvider, "blender_physical_v2"),
        unavailable_scenes=getattr(catalog, "unavailable", []))
    return Application(workbench, ui_repo,
                       vendor_root=evidence_repo / "frontend/workbench/node_modules/three")


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
        app = application(scene, Path(tmp) / "review.sqlite3", args.ui_repo, args.evidence_repo,
                          assets_root=args.assets_repo.resolve())
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
    parser.add_argument("--presets", type=Path, default=DEFAULT_PRESETS)
    parser.add_argument("--assets-repo", type=Path, default=assets_repo())
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

        scene = load_presets(args.presets, args.evidence_repo.resolve(),
                             args.assets_repo.resolve(), args.bundle)
        with tempfile.TemporaryDirectory(prefix="amidst-office-server-") as tmp:
            app = application(
                scene, Path(tmp) / "review.sqlite3", args.ui_repo.resolve(),
                args.evidence_repo.resolve(), assets_root=args.assets_repo.resolve()
            )
            with make_server("127.0.0.1", args.port, app, handler_class=QuietHandler) as server:
                print(f"OFFICE_DEMO_URL=http://127.0.0.1:{server.server_port}/", flush=True)
                server.serve_forever()


if __name__ == "__main__":
    main()
