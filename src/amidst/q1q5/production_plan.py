"""Pinned r004 index preparation. No implicit camera selection or model loading."""

import shutil
import subprocess
from pathlib import Path

from amidst.q1q5.detection_index import content_hash
from amidst.q1q5.production_preflight import PreflightError, read_pinned, strict_json

GATES = {"GRAPH_ROI", "HSV", "PARAMETERS", "PROGRAM_REVIEW", "RUN_FREEZE"}


def require(value, reason):
    if not value:
        raise PreflightError(reason)


def document(ref):
    require(isinstance(ref, dict) and set(ref) == {"path", "file_sha256"}, "FILE_REF_REQUIRED")
    return strict_json(read_pinned(Path(ref["path"]), ref["file_sha256"], maximum=16_777_216))


def prepare(plan):
    require(plan["schema_version"] == "q-demo.r004-production-plan.v1", "PLAN_VERSION")
    require(plan["scene_revision"] == "r004" and plan["source_fps"] == 5, "SOURCE_DESIGN")
    require(
        plan["duration_us"] == 30_000_000 and plan["image_size_px"] == [960, 540], "SOURCE_DESIGN"
    )
    require(
        [(r["label"], r["camera_count"]) for r in plan["runs"]] == [("A4", 4), ("B4", 5)],
        "RUN_DESIGN",
    )
    require(
        plan["detector"]["device"] == "cpu" and plan["detector"]["precision"] == "FP32",
        "DETECTOR_DESIGN",
    )
    missing = [
        f"{r['label']}:{key}"
        for r in plan["runs"]
        for key in (
            "run_id",
            "camera_ids",
            "clock_mapping",
            "registration",
            "parameter_set",
            "detector_config",
            "approval_receipts",
        )
        if r.get(key) is None
    ]
    return {
        "schema_version": "q-demo.production-preparation.v1",
        "status": "BLOCKED",
        "missing": missing,
        "production_performed": False,
        "human_approval_verified": False,
        "source_asset_rehashed": False,
    }


def validate_binding(plan, binding):
    """Verify operator supplied approval bytes/scope; not reviewer authentication."""
    prepare(plan)
    fields = {
        "schema_version",
        "label",
        "scene_revision",
        "registration",
        "camera_ids",
        "source_range_us",
        "clock_mapping",
        "parameter_set",
        "detector_config",
        "approval_receipts",
    }
    require(
        set(binding) == fields
        and binding["schema_version"] == "q-demo.index-production-binding.v1",
        "BINDING_VERSION",
    )
    require(binding["scene_revision"] == plan["scene_revision"], "SCENE_REVISION")
    design = next((r for r in plan["runs"] if r["label"] == binding["label"]), None)
    require(design is not None, "RUN_LABEL")
    cameras = binding["camera_ids"]
    require(
        isinstance(cameras, list)
        and all(isinstance(c, str) and c for c in cameras)
        and len(set(cameras)) == len(cameras) == design["camera_count"],
        "CAMERA_SCOPE",
    )
    require(set(cameras).issubset(plan["camera_catalog_calibration_sha256"]), "CAMERA_CATALOG")
    require(binding["source_range_us"] == [0, plan["duration_us"]], "SOURCE_TIME_SCOPE")
    reg = binding["registration"]
    require(
        set(reg) == {"run_root", "manifest_sha256", "scene_id", "run_id", "source_sha256"},
        "REGISTRATION_FIELDS",
    )
    require(all(isinstance(v, str) and v for v in reg.values()), "REGISTRATION_VALUES")
    require(reg["source_sha256"] == plan["static_source_sha256"], "STATIC_SOURCE")
    run_root = Path(reg["run_root"])
    require(
        run_root.is_absolute() and run_root.resolve() == run_root and run_root.is_dir(),
        "CANONICAL_RUN_ROOT",
    )
    scope_hash = content_hash(binding, ("approval_receipts",))
    receipts = binding["approval_receipts"]
    require(
        isinstance(receipts, list) and len(receipts) == len(GATES), "APPROVAL_RECEIPTS_REQUIRED"
    )
    approvals = [document(ref) for ref in receipts]
    require({r.get("gate") for r in approvals} == GATES, "APPROVAL_GATES")
    require(
        all(
            r.get("decision") == "APPROVED"
            and isinstance(r.get("reviewer"), str)
            and r["reviewer"].strip()
            and r.get("scope_sha256") == scope_hash
            for r in approvals
        ),
        "APPROVAL_SCOPE",
    )
    clock, parameters, config = (
        document(binding[k]) for k in ("clock_mapping", "parameter_set", "detector_config")
    )
    from amidst.q1q5.clock_mapping import ClockMapping

    mapping = ClockMapping.from_document(
        clock, expected_run_id=reg["run_id"], expected_clock_id="clock:" + reg["run_id"]
    )
    require(mapping.duration_us == plan["duration_us"], "CLOCK_SCOPE")
    require(
        parameters["approval"]["status"] == "APPROVED"
        and parameters["content_sha256"]
        == content_hash(parameters, ("content_sha256", "parameter_set_id")),
        "PARAMETERS_NOT_APPROVED",
    )
    require(
        parameters["applies_to"]["scene_revision"] == plan["scene_revision"]
        and reg["run_id"] in parameters["applies_to"]["run_ids"],
        "PARAMETER_SCOPE",
    )
    require(
        len({row["name"] for row in parameters["parameters"]}) == len(parameters["parameters"]),
        "DUPLICATE_PARAMETER",
    )
    values = {
        row["name"]: row["value"] for row in parameters["parameters"] if row["status"] == "APPROVED"
    }
    require(
        {"index_score_floor", "stride_samples", "index_grid_origin_frame", "hsv_config"}.issubset(
            values
        ),
        "INDEX_PARAMETERS_MISSING",
    )
    require(
        set(config) == {"source_root", "weights", "source_hashes", "seed", "threads"},
        "DETECTOR_FIELDS",
    )
    require(
        config["seed"] == plan["detector"]["seed"]
        and config["threads"] == plan["detector"]["threads"],
        "DETECTOR_SETTINGS",
    )
    require(
        isinstance(config["source_hashes"], dict) and config["source_hashes"], "MODEL_SOURCE_PINS"
    )
    for key in ("source_root", "weights"):
        path = Path(config[key])
        require(path.is_absolute() and path.resolve() == path, "CANONICAL_MODEL_PATH")
    return reg, values, config


def produce(
    plan, binding, output, *, permit_real_rgb=False, run_loader=None, predictor_factory=None
):
    require(permit_real_rgb is True, "EXPLICIT_REAL_RGB_PERMISSION_REQUIRED")
    reg, values, config = validate_binding(plan, binding)
    output = Path(output)
    allowed = (Path.home() / "amidst-artifacts").resolve()
    require(
        output.is_absolute()
        and output.resolve() == output
        and output.is_relative_to(allowed)
        and output.parent.is_dir()
        and not output.exists(),
        "NEW_CANONICAL_LOCAL_OUTPUT_REQUIRED",
    )
    require(shutil.disk_usage(output.parent).free >= 8 * 1024**3, "DISK_SPACE_BELOW_8_GIB")
    from amidst.q1q5.baseline_runner import save
    from amidst.q1q5.baseline_telemetry import measure_call
    from amidst.q1q5.detection_index import OfficialRTDetrR18, build_detection_index, write_index
    from amidst.q1q5.hsv_color import HSVConfig
    from amidst.workbench.controlled_scene_data import RunRegistration
    from amidst.workbench.controlled_scene_rgb_data import load_rgb_playback

    output.mkdir(mode=0o700)
    before = subprocess.check_output(["df", "-k", str(output)], text=True)
    try:
        registration = RunRegistration(
            Path(reg["run_root"]),
            reg["manifest_sha256"],
            reg["scene_id"],
            reg["run_id"],
            reg["source_sha256"],
        )
        run, load = measure_call(lambda: (run_loader or load_rgb_playback)(registration))
        require(set(run.camera_ids) == set(binding["camera_ids"]), "RGB_CAMERA_SCOPE")
        require(
            run.manifest["sampling"]["fps"] == plan["source_fps"]
            and run.manifest["sampling"]["duration_s"] * 1_000_000 == plan["duration_us"]
            and run.manifest["sampling"]["image_size_px"] == plan["image_size_px"],
            "RGB_SAMPLING_SCOPE",
        )
        for row in run.files["cameras"]["cameras"]:
            if row["camera_id"] in run.camera_ids:
                require(
                    row["calibration_sha256"]
                    == plan["camera_catalog_calibration_sha256"][row["camera_id"]],
                    "RGB_CALIBRATION_SCOPE",
                )
        model, model_load = measure_call(
            lambda: (predictor_factory or OfficialRTDetrR18)(
                Path(config["source_root"]),
                Path(config["weights"]),
                source_hashes=config["source_hashes"],
                seed=config["seed"],
                threads=config["threads"],
            )
        )
        artifact, build = measure_call(
            lambda: build_detection_index(
                run,
                model,
                scene_revision=plan["scene_revision"],
                stride_samples=values["stride_samples"],
                index_grid_origin_frame=values["index_grid_origin_frame"],
                index_score_floor=values["index_score_floor"],
                color_config=HSVConfig(**values["hsv_config"]),
            )
        )
        require(shutil.disk_usage(output).free >= 8 * 1024**3, "DISK_SPACE_BELOW_8_GIB")
        write_index(artifact, output / "index")
        save(
            output / "receipt.json",
            {
                "schema_version": "q-demo.index-production-receipt.v1",
                "status": "COMPLETE",
                "binding_sha256": content_hash(binding),
                "load_safe_metadata": load,
                "load_model": model_load,
                "build_index": build,
                "stats": artifact.stats,
                "inference_fps": None,
                "inference_fps_reason": (
                    "BUILD_WALL_INCLUDES_RGB_HASH_DECODE_HSV_AND_INDEX_ENCODING"
                ),
                "human_approval_independently_authenticated": False,
                "gt_read": False,
            },
        )
        return artifact
    finally:
        save(
            output / "disk.json",
            {
                "before_df_k": before,
                "after_df_k": subprocess.check_output(["df", "-k", str(output)], text=True),
            },
        )
