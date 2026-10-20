"""Camera rules: extrinsic matrix, optics, run binding separation, design pose (D48/D50)."""

from __future__ import annotations

import math
from typing import Any

from .context import Context, bounds_of, is_num
from .contract import CAMERA_CONVENTION
from .report import Collector, Skip, rule

Matrix = list[list[float]]


def _matrix(raw: Any) -> Matrix | None:
    if (
        isinstance(raw, list)
        and len(raw) == 4
        and all(isinstance(r, list) and len(r) == 4 and all(is_num(v) for v in r) for r in raw)
    ):
        return [[float(v) for v in r] for r in raw]
    return None


def _col(m: Matrix, j: int) -> tuple[float, float, float]:
    return (m[0][j], m[1][j], m[2][j])


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _cross(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _angle_deg(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    la, lb = math.sqrt(_dot(a, a)), math.sqrt(_dot(b, b))
    if la == 0 or lb == 0:
        return 180.0
    return math.degrees(math.acos(max(-1.0, min(1.0, _dot(a, b) / (la * lb)))))


def design_frame(yaw_deg: float, pitch_down_deg: float) -> dict[str, tuple[float, float, float]]:
    """Design appendix A camera basis: yaw CCW from +x, pitch down positive, roll 0."""
    y, p = math.radians(yaw_deg), math.radians(pitch_down_deg)
    return {
        "forward": (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), -math.sin(p)),
        "right": (math.sin(y), -math.cos(y), 0.0),
        "up": (math.sin(p) * math.cos(y), math.sin(p) * math.sin(y), math.cos(p)),
    }


def design_fx(width: float, hfov_deg: float) -> float:
    return (width / 2) / math.tan(math.radians(hfov_deg) / 2)


@rule(
    "CAM-001",
    "camera_to_world 是 4×4 列優先、旋轉正交且行列式 +1、最後一列 [0,0,0,1]、convention 正確",
    "契約 §3.7（匯出時要核對旋轉矩陣與行列式）",
)
def camera_extrinsics(ctx: Context, out: Collector) -> None:
    tol = ctx.params.camera_rot_tol
    for index, cam in enumerate(ctx.cameras):
        id_, base = cam.get("camera_id"), f"$.cameras[{index}].camera_to_world"
        if cam.get("convention") != CAMERA_CONVENTION:
            out.err(
                "CAMERA_CONVENTION",
                "cameras",
                f"$.cameras[{index}].convention",
                f"convention 必須是 {CAMERA_CONVENTION}",
                id_,
            )
        m = _matrix(cam.get("camera_to_world"))
        if m is None:
            out.err("MATRIX_SHAPE", "cameras", base, "camera_to_world 必須是 4×4 有限數", id_)
            continue
        if any(abs(a - b) > tol for a, b in zip(m[3], [0.0, 0.0, 0.0, 1.0], strict=True)):
            out.err(
                "MATRIX_BOTTOM_ROW",
                "cameras",
                base,
                "最後一列必須是 [0,0,0,1]（列優先、不轉置）",
                id_,
            )
        cols = [_col(m, j) for j in range(3)]
        for i in range(3):
            for j in range(i, 3):
                expected = 1.0 if i == j else 0.0
                if abs(_dot(cols[i], cols[j]) - expected) > tol:
                    out.err(
                        "MATRIX_NOT_ORTHONORMAL",
                        "cameras",
                        base,
                        "旋轉部分不正交或含縮放（不再縮放）",
                        id_,
                    )
                    break
            else:
                continue
            break
        else:
            det = _dot(_cross(cols[0], cols[1]), cols[2])
            if abs(det - 1.0) > tol:
                out.err(
                    "MATRIX_DETERMINANT",
                    "cameras",
                    base,
                    f"旋轉行列式必須為 +1（右手），實際 {det:.6f}",
                    id_,
                )


@rule(
    "CAM-002",
    "內參與影像尺寸一致：K 對應實際 PNG、無位移時主點在中心、焦距與感光元件一致",
    "契約 §3.7（K 必須對應實際的 PNG；正式定位以核對後的 K 為準）；設計稿 §2",
)
def camera_intrinsics(ctx: Context, out: Collector) -> None:
    tol = ctx.params.camera_k_tol_px
    size = ((ctx.manifest or {}).get("sampling") or {}).get("image_size_px")
    for index, cam in enumerate(ctx.cameras):
        id_, base = cam.get("camera_id"), f"$.cameras[{index}]"
        w, h = cam.get("width"), cam.get("height")
        if not (is_num(w) and is_num(h)):
            continue
        if isinstance(size, list) and len(size) == 2 and [w, h] != size:
            out.err(
                "IMAGE_SIZE_MISMATCH",
                "cameras",
                f"{base}.width",
                f"width×height {w}×{h} 與 manifest.sampling.image_size_px {size} 不一致（K "
                "必須對應實際 PNG）",
                id_,
            )
        if (
            is_num(cam.get("shift_x"))
            and is_num(cam.get("shift_y"))
            and cam["shift_x"] == 0
            and cam["shift_y"] == 0
        ):
            if (
                is_num(cam.get("cx"))
                and abs(cam["cx"] - w / 2) > tol
                or is_num(cam.get("cy"))
                and abs(cam["cy"] - h / 2) > tol
            ):
                out.err(
                    "PRINCIPAL_POINT",
                    "cameras",
                    f"{base}.cx",
                    "shift 為 0 時主點必須在影像中心（cx=width/2、cy=height/2）",
                    id_,
                )
        if (
            is_num(cam.get("fx"))
            and is_num(cam.get("fy"))
            and is_num(cam.get("pixel_aspect_xy"))
            and cam["pixel_aspect_xy"] == 1
            and abs(cam["fx"] - cam["fy"]) > tol
        ):
            out.err(
                "FOCAL_ASPECT", "cameras", f"{base}.fy", "pixel_aspect_xy=1 時 fx 必須等於 fy", id_
            )
        if cam.get("sensor_fit") == "HORIZONTAL" and all(
            is_num(cam.get(k)) for k in ("fx", "focal_length_mm", "sensor_width_mm")
        ):
            expected = cam["focal_length_mm"] * w / cam["sensor_width_mm"]
            if abs(cam["fx"] - expected) > tol:
                out.err(
                    "FOCAL_SENSOR_MISMATCH",
                    "cameras",
                    f"{base}.fx",
                    f"fx={cam['fx']} 與 focal_length_mm×width/sensor_width_mm={expected:.6f} "
                    f"不一致（容差 {tol} px）",
                    id_,
                )


@rule(
    "CAM-003",
    "光學校正與 run 綁定分開：每台鏡頭有綁定、同 run 一個 clock、不同 run 不共用 clock",
    "契約 §3.7（A 和 B1 不共用 clock）、§4 clock ID",
)
def camera_binding_separation(ctx: Context, out: Collector) -> None:
    cam_ids = {c.get("camera_id") for c in ctx.cameras}
    bindings = ctx.run_bindings
    clocks_by_run: dict[Any, set[Any]] = {}
    runs_by_clock: dict[Any, set[Any]] = {}
    bound: set[Any] = set()
    for binding in bindings:
        run, clock = binding.get("run_id"), binding.get("clock_id")
        clocks_by_run.setdefault(run, set()).add(clock)
        runs_by_clock.setdefault(clock, set()).add(run)
        bound.add(binding.get("camera_id"))
    for run, clocks in clocks_by_run.items():
        if len(clocks) > 1:
            out.err(
                "RUN_MULTIPLE_CLOCKS",
                "cameras",
                "$.run_bindings",
                f"run {run} 的鏡頭必須共用同一個 clock（同一 run 同一 sample grid），實際 "
                f"{len(clocks)} 個",
            )
    for clock, runs in runs_by_clock.items():
        if len(runs) > 1:
            out.err(
                "CLOCK_SHARED_ACROSS_RUNS",
                "cameras",
                "$.run_bindings",
                f"clock {clock} 被 {len(runs)} 個 run 共用；A 和 B1 不共用 clock",
            )
    for camera in sorted(c for c in cam_ids if isinstance(c, str)):
        if camera not in bound:
            out.warn(
                "CAMERA_UNBOUND",
                "cameras",
                "$.run_bindings",
                "鏡頭沒有任何 run 綁定（事件 A 不渲染 CAM_N1 時屬正常）",
                camera,
            )
    seen: set[tuple[Any, Any]] = set()
    for binding in bindings:
        key = (binding.get("run_id"), binding.get("camera_id"))
        if key in seen:
            out.err(
                "BINDING_DUPLICATE",
                "cameras",
                "$.run_bindings",
                f"run {key[0]} 對同一台鏡頭有重複綁定",
                key[1] if isinstance(key[1], str) else None,
            )
        seen.add(key)


@rule(
    "CAM-004",
    "鏡頭 pose／內參與設計稿一致（W2 (14.4,2.1,1.8)、yaw 205°、俯角 10°…）",
    "D48、D50；設計稿 §2 與附錄 A",
    "design",
)
def camera_design_pose(ctx: Context, out: Collector) -> None:
    design = ctx.design
    if design is None:
        raise Skip("沒有 design_reference")
    p = ctx.params
    spec = design["cameras"]
    common = spec["common"]
    by_id = {c.get("camera_id"): (i, c) for i, c in enumerate(ctx.cameras)}
    for item in spec["items"]:
        found = by_id.get(item["camera_id"])
        if found is None:
            out.err(
                "CAMERA_MISSING",
                "cameras",
                "$.cameras",
                "設計稿預期的鏡頭不存在",
                item["camera_id"],
            )
            continue
        index, cam = found
        id_, base = item["camera_id"], f"$.cameras[{index}]"
        m = _matrix(cam.get("camera_to_world"))
        if m is not None:
            pos = [m[0][3], m[1][3], m[2][3]]
            drift = math.dist(pos, item["position_m"])
            if drift > p.camera_pos_tol_m:
                out.err(
                    "CAMERA_POSITION",
                    "cameras",
                    f"{base}.camera_to_world",
                    f"位置 {pos} 與設計值 {item['position_m']} 相差 {drift:.4f} m（容差 "
                    f"{p.camera_pos_tol_m} m）",
                    id_,
                )
            frame = design_frame(item["yaw_deg"], item["pitch_down_deg"])
            forward = (-m[0][2], -m[1][2], -m[2][2])
            fwd_err = _angle_deg(forward, frame["forward"])
            # Roll is independent of yaw/pitch: with roll 0 the camera's +X axis is horizontal.
            right = _col(m, 0)
            right_len = math.sqrt(_dot(right, right))
            roll = math.degrees(math.asin(max(-1.0, min(1.0, right[2] / right_len))))
            roll_err = abs(roll - item["roll_deg"])
            if fwd_err > p.camera_angle_tol_deg:
                out.err(
                    "CAMERA_ORIENTATION",
                    "cameras",
                    f"{base}.camera_to_world",
                    f"朝向與設計值（yaw {item['yaw_deg']}°、俯角 {item['pitch_down_deg']}°）相差 "
                    f"{fwd_err:.3f}°（容差 {p.camera_angle_tol_deg}°）",
                    id_,
                )
            if roll_err > p.camera_angle_tol_deg:
                out.err(
                    "CAMERA_ROLL",
                    "cameras",
                    f"{base}.camera_to_world",
                    f"roll {roll:.3f}° 與設計值 {item['roll_deg']}° 相差 {roll_err:.3f}°",
                    id_,
                )
        for key, expected in common.items():
            if key not in cam:
                continue  # SCH-007 reports missing fields
            actual = cam[key]
            differs = (
                actual != expected
                if isinstance(expected, str)
                else not is_num(actual) or abs(actual - expected) > 1e-6
            )
            if differs:
                out.err(
                    "CAMERA_COMMON",
                    "cameras",
                    f"{base}.{key}",
                    f"{key} 應為 {expected!r}，實際 {actual!r}",
                    id_,
                )
        fx_expected = design_fx(common["width"], item["hfov_deg"])
        for key in ("fx", "fy"):
            if is_num(cam.get(key)) and abs(cam[key] - fx_expected) > p.camera_k_tol_px:
                out.err(
                    "CAMERA_FOCAL",
                    "cameras",
                    f"{base}.{key}",
                    f"{key}={cam[key]} 與 hfov {item['hfov_deg']}° 的設計值 {fx_expected:.6f} "
                    f"不符（容差 {p.camera_k_tol_px} px）",
                    id_,
                )
        if is_num(cam.get("focal_length_mm")):
            f_expected = common["sensor_width_mm"] * fx_expected / common["width"]
            if abs(cam["focal_length_mm"] - f_expected) > 1e-5:
                out.err(
                    "CAMERA_FOCAL_MM",
                    "cameras",
                    f"{base}.focal_length_mm",
                    f"focal_length_mm 與設計值 {f_expected:.6f} 不符",
                    id_,
                )


@rule(
    "CAM-005",
    "鏡頭位置不在牆／障礙物內，且與其外框最小間隙 >= .10 m",
    "設計稿 §2（W2 到所有列出 AABB 的最小間隙 .100 m，避免共面）",
    "design",
)
def camera_clearance(ctx: Context, out: Collector) -> None:
    if ctx.design is None:
        raise Skip("沒有 design_reference")
    gap_min, tol = ctx.params.camera_min_gap_m, ctx.params.camera_pos_tol_m * 1e-3
    for cam in ctx.cameras:
        m = _matrix(cam.get("camera_to_world"))
        if m is None:
            continue
        pos = (m[0][3], m[1][3], m[2][3])
        for obj in ctx.solids:
            bounds = bounds_of(obj)
            if bounds is None:
                continue
            lo, hi = bounds
            gap = math.sqrt(sum(max(lo[k] - pos[k], 0.0, pos[k] - hi[k]) ** 2 for k in range(3)))
            if gap < gap_min - tol:
                out.err(
                    "CAMERA_TOO_CLOSE",
                    "cameras",
                    "$.cameras",
                    f"相機位置與 {obj.get('id')} 外框間隙 {gap:.4f} m < {gap_min} m（含在內部為 "
                    "0）",
                    cam.get("camera_id"),
                )
