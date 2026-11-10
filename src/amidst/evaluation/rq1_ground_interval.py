"""RQ1 evaluation: frozen single-camera ground intervals (C4a v1.1) against Ground Truth.

Ground Truth is read here, in evaluation only, and only after the frozen prediction file's
SHA-256 has been verified. Nothing in this module feeds back into inference or ranking.
The unit of comparison is the horizontal (XY) plane: prediction segments lie on a constant
plane height, so the vertical offset of the GT floor contact is checked, not scored.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Vec2 = tuple[float, float]


class FrozenPredictionError(ValueError):
    """Prediction file hash mismatch or malformed content."""


class GroundTruthError(ValueError):
    """Ground Truth refused or inconsistent with the frozen predictions."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class FrozenPredictions:
    """Predictions whose SHA-256 was verified. Only `load_frozen_predictions` makes one."""

    sha256: str
    run_id: str
    source_sha256: str
    observations: tuple[Mapping[str, Any], ...]
    _token: object

    def __post_init__(self) -> None:
        if self._token is not _VERIFIED:
            raise FrozenPredictionError("FrozenPredictions must come from load_frozen_predictions")


_VERIFIED = object()


def load_frozen_predictions(path: Path, expected_sha256: str) -> FrozenPredictions:
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise FrozenPredictionError(f"prediction SHA-256 mismatch: {actual} != {expected_sha256}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("gt_read") is not False:
        raise FrozenPredictionError("predictions do not declare gt_read=false")
    observations = tuple(data["observations"])
    for obs in observations:
        if obs.get("estimate_kind") != "SEGMENT" or obs.get("status") != "READY":
            raise FrozenPredictionError(
                f"non-SEGMENT/READY observation {obs.get('observation_ref')}"
            )
    return FrozenPredictions(
        sha256=actual,
        run_id=data["run_id"],
        source_sha256=data["source_sha256"],
        observations=observations,
        _token=_VERIFIED,
    )


@dataclass(frozen=True)
class GroundTruthTrack:
    sha256: str
    timestamps_s: tuple[float, ...]
    contact_xyz_m: tuple[tuple[float, float, float], ...]


def load_ground_truth(
    path: Path,
    expected_sha256: str,
    predictions: FrozenPredictions,
    *,
    m_per_unit: float,
    contact_field: str = "foot_position",
) -> GroundTruthTrack:
    """Load GT. Refuses unless `predictions` is a SHA-verified FrozenPredictions."""
    if not isinstance(predictions, FrozenPredictions):
        raise GroundTruthError("GT is loaded only after frozen predictions are verified")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise GroundTruthError(f"GT SHA-256 mismatch: {actual} != {expected_sha256}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("source_asset_sha256") != predictions.source_sha256:
        raise GroundTruthError("GT source asset SHA differs from the predictions' source SHA")
    samples = sorted(data["samples"], key=lambda s: s["timestamp"])
    times = tuple(float(s["timestamp"]) for s in samples)
    if any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise GroundTruthError("GT timestamps are not strictly increasing")
    pts = tuple(
        (
            float(s[contact_field][0]) * m_per_unit,
            float(s[contact_field][1]) * m_per_unit,
            float(s[contact_field][2]) * m_per_unit,
        )
        for s in samples
    )
    return GroundTruthTrack(sha256=actual, timestamps_s=times, contact_xyz_m=pts)


def gt_contact_at(
    track: GroundTruthTrack, t: float, *, exact_tol_s: float = 1e-6
) -> tuple[tuple[float, float, float], str]:
    """GT contact at time t: the sample itself if within tol, else linear interpolation.

    Outside the GT time range raises GroundTruthError (no extrapolation, no nearest-snap).
    """
    ts = track.timestamps_s
    if t < ts[0] - exact_tol_s or t > ts[-1] + exact_tol_s:
        raise GroundTruthError(f"timestamp {t} outside GT range [{ts[0]}, {ts[-1]}]")
    for i, s in enumerate(ts):
        if abs(s - t) <= exact_tol_s:
            return track.contact_xyz_m[i], "EXACT"
    hi = next(i for i, s in enumerate(ts) if s > t)
    lo = hi - 1
    w = (t - ts[lo]) / (ts[hi] - ts[lo])
    a, b = track.contact_xyz_m[lo], track.contact_xyz_m[hi]
    return (
        (a[0] + w * (b[0] - a[0]), a[1] + w * (b[1] - a[1]), a[2] + w * (b[2] - a[2])),
        "LINEAR_INTERPOLATION",
    )


def point_segment_distance(p: Vec2, near: Vec2, far: Vec2) -> tuple[float, float]:
    """Shortest distance from p to segment near->far and the parameter t in [0, 1].

    t=0 is the near end, t=1 the far end. A zero-length segment gives t=0.
    """
    dx, dy = far[0] - near[0], far[1] - near[1]
    len2 = dx * dx + dy * dy
    if len2 == 0.0:
        return math.hypot(p[0] - near[0], p[1] - near[1]), 0.0
    t = ((p[0] - near[0]) * dx + (p[1] - near[1]) * dy) / len2
    t = min(1.0, max(0.0, t))
    cx, cy = near[0] + t * dx, near[1] + t * dy
    return math.hypot(p[0] - cx, p[1] - cy), t


def evaluate_observation(
    obs: Mapping[str, Any],
    track: GroundTruthTrack,
    tolerances_m: Mapping[str, float],
    *,
    exact_tol_s: float = 1e-6,
) -> dict[str, Any]:
    seg = obs["segment"]
    near, far = seg["near_m"], seg["far_m"]
    t_s = float(obs["timestamp_s"])
    gt, mode = gt_contact_at(track, t_s, exact_tol_s=exact_tol_s)
    dist, tpos = point_segment_distance((gt[0], gt[1]), (near[0], near[1]), (far[0], far[1]))
    mid = ((near[0] + far[0]) / 2.0, (near[1] + far[1]) / 2.0)
    row: dict[str, Any] = {
        "observation_ref": obs["observation_ref"],
        "camera_id": obs["camera_id"],
        "basis": obs["basis"],
        "timestamp_s": t_s,
        "time_alignment": mode,
        "segment_length_m": math.hypot(far[0] - near[0], far[1] - near[1]),
        "segment_length_declared_m": float(seg["length_m"]),
        "distance_to_segment_m": dist,
        "position_on_segment": tpos,
        "plane_height_residual_m": gt[2] - float(near[2]),
        "reference_midpoint_error_m": math.hypot(gt[0] - mid[0], gt[1] - mid[1]),
    }
    for name, tol in tolerances_m.items():
        row[f"covered_{name}"] = dist <= tol
    return row


def _summ(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"median": None, "min": None, "max": None, "mean": None}
    return {
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
    }


def aggregate(rows: Sequence[Mapping[str, Any]], tolerance_names: Sequence[str]) -> dict[str, Any]:
    out: dict[str, Any] = {"n": len(rows)}
    for name in tolerance_names:
        k = sum(1 for r in rows if r[f"covered_{name}"])
        out[f"coverage_{name}"] = {
            "covered": k,
            "n": len(rows),
            "rate": k / len(rows) if rows else None,
        }
    out["segment_length_m"] = _summ([r["segment_length_m"] for r in rows])
    out["distance_to_segment_m"] = _summ([r["distance_to_segment_m"] for r in rows])
    out["position_on_segment"] = _summ([r["position_on_segment"] for r in rows])
    out["plane_height_residual_m"] = _summ([r["plane_height_residual_m"] for r in rows])
    out["reference_midpoint_error_m"] = _summ([r["reference_midpoint_error_m"] for r in rows])
    return out


def evaluate_rq1(
    predictions: FrozenPredictions,
    track: GroundTruthTrack,
    tolerances_m: Mapping[str, float],
    *,
    exact_tol_s: float = 1e-6,
) -> dict[str, Any]:
    rows = sorted(
        (
            evaluate_observation(o, track, tolerances_m, exact_tol_s=exact_tol_s)
            for o in predictions.observations
        ),
        key=lambda r: (r["timestamp_s"], r["camera_id"], r["observation_ref"]),
    )
    names = list(tolerances_m)
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for r in rows:
        groups.setdefault(f"basis={r['basis']}", []).append(r)
        groups.setdefault(f"basis={r['basis']}|camera={r['camera_id']}", []).append(r)
        groups.setdefault(f"camera={r['camera_id']}", []).append(r)
    return {
        "per_observation": rows,
        "summary": {"ALL": aggregate(rows, names)}
        | {k: aggregate(v, names) for k, v in sorted(groups.items())},
    }
