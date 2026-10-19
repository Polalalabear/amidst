"""Offline D47 auxiliary screening. Never imported by a formal loader/service.

Detection accepts RGB only. Authored route/geometry enter a separate acceptance
comparison *after* detection; no GT, renderer visibility, depth or actor matching.
Run with an existing uv Python containing numpy and Pillow; installs nothing.
"""

import argparse
import ast
import hashlib
import json
import math
import os
import platform
import time
from collections import Counter
from pathlib import Path

import numpy as np
import PIL
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
CONFIG_REF = "configs/controlled_scene_d47_detector_v1.json"
CONFIG_PIN = "3b83a74d236753a9596f56266f80a2585f06d1e5201474c49179c16d17336bff"
SEED_REF = "configs/controlled_scene_cs_b_sampling_v1.json"
SEED_PIN = "584c458b788348f8e7b6f47f69888e2420f5f01590e1d923001d5c94a0a2a3d0"
DESIGN_REF = "docs/engineering/CONTROLLED_SCENE_B_DESIGN_20261018.md"
DESIGN_PIN = "da262df528d9ad0aac3482c6932f29aa73ddd0d9f6f1bf6c847acc5de7263d29"
SOURCE_PIN = "6e7de38dc069d330e0ffbb6c0051cdab304566fdbb7e3e8dfb429af863ae6d8e"
RUN_PINS = {
    "ctrl-lcorr-s1-a-5fps-v1-r001": (
        "9e43237e9c9ac9ea4f2bc97f65e49103a0ec3946b1b555b9d7fbf59850e97d47", 50,
        ["CAM_W1", "CAM_W2", "CAM_R102_CTRL"],
    ),
    "ctrl-lcorr-s1-b1-5fps-v1-r001": (
        "a5392a6fc5b51257adb82827df376f42290690cbdb52160888eb241f256ecc39", 100,
        ["CAM_W1", "CAM_W2", "CAM_N1", "CAM_R102_CTRL"],
    ),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pinned(path, expected):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"PINNED_INPUT_MISSING_OR_SYMLINK: {path}")
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise ValueError(f"HASH_MISMATCH: {path}")
    return raw


def load_design():
    """Extract only approved literal design functions, never run appendix output code."""
    raw = pinned(REPO / DESIGN_REF, DESIGN_PIN).decode()
    code = raw.split("```python\n", 1)[1].split("```", 1)[0]
    names = {"DEG", "CAMS", "BOXES", "DELAY"}
    functions = {"camera", "proj", "blocked", "route1", "route2", "visible"}
    selected = []
    for node in ast.parse(code).body:
        if isinstance(node, ast.FunctionDef) and node.name in functions:
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in names for t in node.targets
        ):
            selected.append(node)
    namespace = {"math": math}
    exec(compile(ast.Module(body=selected, type_ignores=[]), DESIGN_REF, "exec"), namespace)
    return namespace


def components(mask, minimum_area):
    """Exact 4-connected run-length union; no morphology/semantic filtering."""
    parents, spans, previous = [], [], []

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    for y, row in enumerate(mask):
        changes = np.diff(np.pad(row.astype(np.int8), (1, 1)))
        starts, ends = np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)
        current = []
        cursor = 0
        for start, end in zip(starts, ends, strict=True):
            start, end = int(start), int(end)
            label = len(parents)
            parents.append(label)
            spans.append((start, y, end))
            while cursor < len(previous) and previous[cursor][1] <= start:
                cursor += 1
            j = cursor
            while j < len(previous) and previous[j][0] < end:
                other = root(previous[j][2])
                own = root(label)
                if own != other:
                    parents[own] = other
                j += 1
            current.append((start, end, label))
        previous = current
    boxes = {}
    for label, (start, y, end) in enumerate(spans):
        key = root(label)
        if key not in boxes:
            boxes[key] = [start, y, end, y + 1, end - start]
        else:
            b = boxes[key]
            b[0], b[1] = min(b[0], start), min(b[1], y)
            b[2], b[3] = max(b[2], end), max(b[3], y + 1)
            b[4] += end - start
    return sorted((b for b in boxes.values() if b[4] >= minimum_area), key=lambda b: b[:4])


def detect_camera(images, config):
    """RGB-only detector: no access to design, route, expected boxes or identities."""
    stack = np.stack(images)
    background = np.empty(stack.shape[1:], dtype=np.int16)
    for y in range(0, 540, 30):
        background[y:y + 30] = np.median(stack[:, y:y + 30], axis=0).astype(np.int16)
    del stack
    result = []
    for rgb in images:
        difference = np.max(np.abs(rgb.astype(np.int16) - background), axis=2)
        boxes = components(difference > config["rgb_max_channel_difference_gt"],
                           config["minimum_component_area_px"])
        detections = []
        for x0, y0, x1, y1, area in boxes:
            labels = ["RGB_FOREGROUND_COMPONENT_NOT_CONFIRMED_PERSON"]
            if (x1 - x0) / (y1 - y0) > config["ambiguous_width_height_ratio_gt"]:
                labels.append("MERGED_OR_AMBIGUOUS")
            detections.append({
                "bbox_xyxy_px": [x0, y0, x1, y1],
                "score": area / ((x1 - x0) * (y1 - y0)),
                "labels": labels,
                "component_area_px": area,
            })
        result.append(detections)
    return result


def project_body(design, camera_id, position):
    """Nominal 1.70m/r=.25 cylinder; finite-probe DESIGN ESTIMATE, not coverage evidence.

    Presence uses unblocked in-frame nominal probes. Comparison bbox is the full
    projected cylinder (unclipped, including hidden parts), never fitted to RGB.
    Partial bodies consequently tend to be flagged rather than falsely accepted.
    """
    x, y = position
    angles = np.arange(32) * 2 * math.pi / 32
    points = np.array([
        (x + .25 * math.cos(a), y + .25 * math.sin(a), z)
        for a in angles for z in np.linspace(0, 1.70, 9)
    ] + [(x, y, 0), (x, y, 1.70)])
    cam = design["CAMS"][camera_id]
    origin = np.asarray(cam["pos"])
    rays = points - origin
    depth = rays @ cam["forward"]
    u = 480 + cam["fx"] * (rays @ cam["right"]) / depth
    v = 270 - cam["fy"] * (rays @ cam["up"]) / depth
    inside = (depth >= .05) & (depth <= 60) & (u >= 0) & (u < 960) & (v >= 0) & (v < 540)
    clear = inside.copy()
    for _, lo, hi in design["BOXES"]:
        lower, upper = np.zeros(len(points)), np.ones(len(points))
        intersects = np.ones(len(points), dtype=bool)
        for k in range(3):
            parallel = np.abs(rays[:, k]) < 1e-12
            if not lo[k] <= origin[k] <= hi[k]:
                intersects &= ~parallel
            delta = np.where(parallel, 1, rays[:, k])
            a, b = (lo[k] - origin[k]) / delta, (hi[k] - origin[k]) / delta
            lower = np.maximum(lower, np.where(parallel, -np.inf, np.minimum(a, b)))
            upper = np.minimum(upper, np.where(parallel, np.inf, np.maximum(a, b)))
        occluded = intersects & (lower < upper) & (lower < 1 - 1e-9) & (upper > 1e-9)
        clear &= ~occluded
    full = depth > 0
    bbox = None if not full.all() else [float(u.min()), float(v.min()),
                                      float(u.max()), float(v.max())]
    return {"present": bool(clear.any()), "full_body_expected": bool(clear.all()),
            "bbox": bbox, "visible_probe_count": int(clear.sum()), "probe_count": len(points)}


def projection(design, event, camera, timestamp):
    positions = [design["route1"](timestamp)]
    if event == "b1":
        second = design["route2"](timestamp)
        if second is not None:
            positions.append(second)
    bodies = [project_body(design, camera, p) for p in positions]
    visible = [b for b in bodies if b["present"]]
    return {
        "expected_present": bool(visible),
        "expected_bbox_xyxy_px": visible[0]["bbox"] if len(visible) == 1 else None,
        "expected_count": len(visible),
        "full_body_expected": len(visible) == 1 and visible[0]["full_body_expected"],
        "basis": "DESIGN_ESTIMATE_NOT_COVERAGE_EVIDENCE; authored route + nominal H1.70/r0.25; full cylinder bbox, not RGB fit",
        "model_error": "UNKNOWN; finite probes, ideal pinhole and authored opaque AABB union",
    }


def frame_flags(row, event, thresholds):
    flags = []
    detections, projected = row["detections"], row["projection"]
    target = event == "a" and row["camera_id"] in ("CAM_W1", "CAM_W2") and 22 <= row["frame_index"] <= 32
    if target and not detections:
        flags.append("D27_TARGET_PERSON_MISSING")
    if len(detections) >= 2:
        flags.append("MULTIPLE_COMPONENTS_POSSIBLE_PEOPLE")
        if event == "b1":
            flags.append("B1_POSSIBLE_TWO_PEOPLE")
    for d in detections:
        x0, y0, x1, y1 = d["bbox_xyxy_px"]
        if y1 - y0 < thresholds["minimum_height_px"]:
            flags.append("HEIGHT_BELOW_112_PX")
        if min(x0, y0, 960 - x1, 540 - y1) < thresholds["minimum_margin_px"]:
            flags.append("MARGIN_BELOW_16_PX")
        if min(x0, y0, 960 - x1, 540 - y1) <= thresholds["edge_touch_px"]:
            flags.append("FRAME_EDGE_TOUCH")
        if "MERGED_OR_AMBIGUOUS" in d["labels"]:
            flags.append("MERGED_OR_AMBIGUOUS")
    if event == "b1" and 51 <= row["frame_index"] < 68 and detections:
        flags.append("COMPONENT_IN_DESIGN_BLIND_WINDOW")
    if projected["expected_present"] and not detections:
        flags.append("EXPECTED_PERSON_MISSING")
    if bool(detections) != projected["expected_present"]:
        flags.extend(["PROJECTION_INCONSISTENT", "PROJECTION_PRESENCE_MISMATCH"])
    if projected["expected_count"] > 1:
        flags.append("PROJECTION_MULTIPLE_EXPECTED_UNKNOWN_MATCH")
    if projected["expected_present"] and not projected["full_body_expected"]:
        flags.append("PARTIAL_EXPECTED")
    if detections and projected["expected_present"]:
        if len(detections) != 1 or projected["expected_bbox_xyxy_px"] is None:
            flags.append("PROJECTION_COMPARISON_AMBIGUOUS")
        else:
            b, p = detections[0]["bbox_xyxy_px"], projected["expected_bbox_xyxy_px"]
            height = p[3] - p[1]
            relative = abs((b[3] - b[1]) - height) / height if height > 0 else math.inf
            offset = math.hypot((b[0] + b[2] - p[0] - p[2]) / 2,
                                (b[1] + b[3] - p[1] - p[3]) / 2)
            row["projection_comparison"] = {
                "height_relative_error": relative,
                "center_offset_px": offset,
                "center_offset_over_expected_height": offset / height if height > 0 else None,
            }
            if relative > thresholds["height_relative_error_gt"]:
                flags.extend(["PROJECTION_INCONSISTENT", "PROJECTION_HEIGHT_MISMATCH"])
            if offset > thresholds["center_distance_over_projected_height_gt"] * height:
                flags.extend(["PROJECTION_INCONSISTENT", "PROJECTION_CENTER_MISMATCH"])
    return sorted(set(flags))


def sampling_key(seed, run_id, camera, index):
    return digest(json.dumps([seed, run_id, camera, index], ensure_ascii=True,
                             separators=(",", ":")).encode())


def assign_reviews(frames, event, seed, run_id):
    by_camera = {}
    for row in frames:
        row["review_reasons"] = ["FLAGGED"] if row["flags"] else []
        k, camera = row["frame_index"], row["camera_id"]
        if event == "a" and camera in ("CAM_W1", "CAM_W2") and 22 <= k <= 32:
            row["review_reasons"].append("D27_TARGET")
        if event == "b1" and k in (49, 50, 68, 69):
            row["review_reasons"].append("BLIND_BOUNDARY")
        by_camera.setdefault(camera, []).append(row)
    receipts = {}
    for camera, rows in by_camera.items():
        def state(row):
            return len(row["detections"]), any(
                "MERGED_OR_AMBIGUOUS" in d["labels"] for d in row["detections"])
        for k in range(1, len(rows)):
            if state(rows[k]) != state(rows[k - 1]):
                for j in (k - 1, k, k + 1):
                    if 0 <= j < len(rows):
                        rows[j]["review_reasons"].append("SWITCH_BOUNDARY")
        eligible = [r for r in rows if not r["review_reasons"]]
        ordered = sorted(eligible, key=lambda r: (
            sampling_key(seed, run_id, camera, r["frame_index"]), r["frame_index"]))
        selected = ordered[:math.ceil(len(eligible) / 10)]
        for row in selected:
            row["review_reasons"].append("RANDOM_SAMPLE")
        receipts[camera] = {
            "eligible_count": len(eligible), "selected_count": len(selected),
            "eligible_indices_sha256": digest(json.dumps(
                [r["frame_index"] for r in eligible], separators=(",", ":")).encode()),
            "selected_indices": [r["frame_index"] for r in selected],
        }
    for row in frames:
        row["review_reasons"] = sorted(set(row["review_reasons"]))
        row["review_required"] = bool(row["review_reasons"])
        row["human_review_status"] = "MODEL_SCREENED_NOT_HUMAN_REVIEWED"
    return receipts


def load_rgb(run_root, run_id):
    index_pin, count, cameras = RUN_PINS[run_id]
    index = json.loads(pinned(run_root / "safe_bundle/rgb_index.json", index_pin))
    if (index["run_id"] != run_id or index["source_sha256"] != SOURCE_PIN
            or index["clock_id"] != "clock:" + run_id or index["missing"]):
        raise ValueError("SOURCE_RUN_CLOCK_OR_MISSING_ERROR")
    if (index["sampling"]["fps"] != 5 or index["sampling"]["image_size_px"] != [960, 540]
            or index["sampling"]["sample_count_per_camera"] != count):
        raise ValueError("SAMPLING_PIN_MISMATCH")
    rows = index["frames"]  # D55 immutable schema; records/frames migration is separate.
    grid = {(c, k) for c in cameras for k in range(count)}
    if len(rows) != len(grid) or {(r["camera_id"], r["frame_index"]) for r in rows} != grid:
        raise ValueError("RGB_INDEX_INCOMPLETE_OR_DUPLICATE")
    for row in rows:
        expected_ref = f"rgb/{row['camera_id']}/frame_{row['frame_index']:06d}.png"
        if row["rgb_ref"] != expected_ref or row["timestamp_s"] != row["frame_index"] / 5:
            raise ValueError("RGB_REF_OR_CLOCK_PIN_MISMATCH")
        path = run_root / expected_ref
        if path.resolve() != path.absolute() or path.stat().st_nlink != 1:
            raise ValueError("RGB_ALIAS_NOT_ALLOWED")
    return sorted(rows, key=lambda r: (r["camera_id"], r["frame_index"]))


def run_one(root, run_id, config, seed, design):
    started = time.perf_counter()
    run_root = root / "runs" / run_id
    destination = run_root / "acceptance/d47_screening.json"
    if destination.exists():
        raise FileExistsError(f"Do not overwrite acceptance result: {destination}")
    inputs = load_rgb(run_root, run_id)
    frames, timings = [], {}
    for camera in sorted({r["camera_id"] for r in inputs}):
        rows = [r for r in inputs if r["camera_id"] == camera]
        images = []
        for row in rows:
            raw = pinned(run_root / row["rgb_ref"], row["file_sha256"])
            from io import BytesIO
            with Image.open(BytesIO(raw)) as image:
                if image.size != (960, 540) or image.mode != "RGB":
                    raise ValueError("INVALID_RGB_IMAGE")
                images.append(np.asarray(image).copy())
        begin = time.perf_counter()
        detected = detect_camera(images, config)
        timings[camera] = time.perf_counter() - begin
        del images
        event = "b1" if "-b1-" in run_id else "a"
        for source, detection in zip(rows, detected, strict=True):
            row = dict(source, detections=detection,
                       projection=projection(design, event, camera, source["timestamp_s"]))
            row["flags"] = frame_flags(row, event, config["screening"])
            frames.append(row)
        print(json.dumps({"run_id": run_id, "camera_id": camera,
                          "frames": len(rows), "detector_s": timings[camera]}), flush=True)
    event = "b1" if "-b1-" in run_id else "a"
    if event == "a":
        for k in range(50):
            batch = [r for r in frames if r["frame_index"] == k]
            if not any(r["detections"] for r in batch):
                for r in batch:
                    r["flags"] = sorted(set(r["flags"] + ["A_ALL_CAMERAS_NO_COMPONENT"]))
    samples = assign_reviews(frames, event, seed["seed"], run_id)
    summary = {
        "frame_count": len(frames),
        "review_required": sum(r["review_required"] for r in frames),
        "review_reasons": dict(Counter(x for r in frames for x in r["review_reasons"])),
        "flags": dict(Counter(x for r in frames for x in r["flags"])),
        "detector_elapsed_s_by_camera": timings,
        "detector_elapsed_s": sum(timings.values()),
        "wall_elapsed_s": time.perf_counter() - started,
    }
    document = {
        "schema_version": "d47_screening_v1", "run_id": run_id,
        "rgb_index_sha256": RUN_PINS[run_id][0],
        "detector": {"name": config["name"], "version": config["version"],
                     "config_ref": CONFIG_REF, "config_sha256": CONFIG_PIN,
                     "score_kind": config["score_kind"]},
        "sampling": {"seed_ref": SEED_REF, "seed_sha256": SEED_PIN,
                     "rule": "SHA256(UTF8 compact JSON [seed,run_id,camera_id,index]); ascending hex/index; ceil(10% of remaining after FLAGGED/D27/A4)",
                     "receipts": samples},
        "frames": frames,
        "acceptance_only": True, "not_for_runtime_or_safe_bundle": True,
        "formal_acceptance": False, "gt_read": False,
        "projection_provenance": {"design_ref": DESIGN_REF, "design_sha256": DESIGN_PIN,
                                  "source_sha256": SOURCE_PIN,
                                  "purpose": "D54_A2_CS_B_ACCEPTANCE_ONLY",
                                  "calibration_basis": "pinned authored camera design; exported runtime calibration not yet materialized"},
        "producer": {"script_sha256": digest(Path(__file__).read_bytes()),
                     "python": platform.python_version(), "numpy": np.__version__,
                     "pillow": PIL.__version__},
        "summary": summary,
    }
    # Recheck immutable refs and all input bytes before publishing; no partial run success.
    pinned(REPO / CONFIG_REF, CONFIG_PIN)
    pinned(REPO / SEED_REF, SEED_PIN)
    pinned(REPO / DESIGN_REF, DESIGN_PIN)
    load_rgb(run_root, run_id)
    for row in inputs:
        pinned(run_root / row["rgb_ref"], row["file_sha256"])
    if os.statvfs(root).f_bavail * os.statvfs(root).f_frsize < 8 * 1024**3:
        raise ValueError("DISK_BELOW_8_GIB")
    destination.parent.mkdir(exist_ok=True)
    payload = (json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    with destination.open("xb") as stream:
        stream.write(payload)
    print(json.dumps({"output": str(destination), "sha256": digest(payload),
                      "summary": summary}), flush=True)
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(pinned(REPO / CONFIG_REF, CONFIG_PIN))
    seed = json.loads(pinned(REPO / SEED_REF, SEED_PIN))
    design = load_design()
    for run_id in RUN_PINS:
        run_one(args.root.resolve(), run_id, config, seed, design)


if __name__ == "__main__":
    main()
