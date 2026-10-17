"""RQ1 single-camera ground-contact accuracy report (post-hoc, frozen predictions only).

Reads the CSV/JSON outputs of a contact-control validation run (perception v1 bbox-bottom
vs v2 mask-lowest contact) and summarizes paired error, coverage, speed jumps, v2
rejection reasons, per-pixel sensitivity and the Office kept/rejected comparison.
Ground truth only enters through the frozen ``errors.csv``; nothing here feeds inference.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "amidst.contact-rq1-evaluation.v1"
DEFAULT_MAX_SPEED_M_S = 8.0
CROSSCHECK_TOLERANCE = 1e-9
NO_DETECTION = "NO_DETECTION"
ALL_CAMERAS = "ALL"
VERSIONS = ("v1", "v2")

Position = tuple[float, ...]


@dataclass(frozen=True)
class ErrorRow:
    timestamp: float
    camera_id: str
    v1: tuple[float | None, ...]
    v2: tuple[float | None, ...]


@dataclass(frozen=True)
class ComparisonRow:
    timestamp: float
    camera_id: str
    v1_positions: tuple[Position | None, ...]
    v2_positions: tuple[Position | None, ...]
    v2_reasons: tuple[tuple[str, ...], ...]
    """One reason tuple per v2 component; a frame without components carries one row-level tuple."""
    pixel_sensitivity_m: tuple[float | None, ...]


@dataclass(frozen=True)
class VisibilityRow:
    timestamp: float
    camera_id: str
    bottom_visible: bool
    bottom_incidence: float | None
    incidence_eligible: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _floats(raw: str) -> tuple[float | None, ...]:
    return tuple(None if value is None else float(value) for value in json.loads(raw))


def _positions(raw: str) -> tuple[Position | None, ...]:
    return tuple(
        None if value is None else tuple(float(axis) for axis in value) for value in json.loads(raw)
    )


def _reasons(raw: str) -> tuple[tuple[str, ...], ...]:
    """Normalize ``[["A"], []]`` (per component) and ``["NO_DETECTION"]`` (row level)."""
    parsed = json.loads(raw)
    if parsed and all(isinstance(item, str) for item in parsed):
        return (tuple(parsed),)
    return tuple(tuple(str(reason) for reason in item) for item in parsed)


def _bool(raw: str) -> bool:
    return raw.strip().lower() in {"true", "1", "yes"}


def load_errors(path: Path) -> list[ErrorRow]:
    return [
        ErrorRow(
            timestamp=float(row["timestamp"]),
            camera_id=row["camera_id"],
            v1=_floats(row["v1_errors_m"]),
            v2=_floats(row["v2_errors_m"]),
        )
        for row in _rows(path)
    ]


def load_comparison(path: Path) -> list[ComparisonRow]:
    return [
        ComparisonRow(
            timestamp=float(row["timestamp"]),
            camera_id=row["camera_id"],
            v1_positions=_positions(row["old_world_positions_m"]),
            v2_positions=_positions(row["new_world_positions_m"]),
            v2_reasons=_reasons(row["new_reasons"]),
            pixel_sensitivity_m=_floats(row["pixel_sensitivity_max_m"]),
        )
        for row in _rows(path)
    ]


def load_visibility(path: Path) -> list[VisibilityRow]:
    result = []
    for row in _rows(path):
        incidence = row.get("bottom_incidence", "")
        result.append(
            VisibilityRow(
                timestamp=float(row["timestamp"]),
                camera_id=row["camera_id"],
                bottom_visible=_bool(row["bottom_visible"]),
                bottom_incidence=float(incidence) if incidence not in {"", "None"} else None,
                incidence_eligible=_bool(row["incidence_eligible"]),
            )
        )
    return result


def describe(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean_m": None, "median_m": None, "max_m": None, "min_m": None}
    return {
        "count": len(values),
        "mean_m": statistics.fmean(values),
        "median_m": statistics.median(values),
        "max_m": max(values),
        "min_m": min(values),
    }


def _cameras(camera_ids: Iterable[str]) -> list[str]:
    return sorted(set(camera_ids))


def paired_errors(rows: Sequence[ErrorRow]) -> dict[str, dict[str, list[float]]]:
    """Per camera, component-aligned errors where both v1 and v2 are non-null."""
    paired: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"v1": [], "v2": []})
    for row in rows:
        if len(row.v1) != len(row.v2):
            raise ValueError(f"v1/v2 component count differs at {row.camera_id} t={row.timestamp}")
        for v1, v2 in zip(row.v1, row.v2, strict=True):
            if v1 is not None and v2 is not None:
                paired[row.camera_id]["v1"].append(v1)
                paired[row.camera_id]["v2"].append(v2)
    return dict(paired)


def error_summary(rows: Sequence[ErrorRow]) -> dict[str, Any]:
    paired = paired_errors(rows)
    available: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"v1": [], "v2": []})
    for row in rows:
        for version, values in (("v1", row.v1), ("v2", row.v2)):
            available[row.camera_id][version].extend(v for v in values if v is not None)
    result: dict[str, Any] = {}
    for camera in [*_cameras(row.camera_id for row in rows), ALL_CAMERAS]:
        result[camera] = {
            "paired": {version: describe(_pick(paired, camera, version)) for version in VERSIONS},
            "all_available": {
                version: describe(_pick(available, camera, version)) for version in VERSIONS
            },
        }
    return result


def _pick(source: Mapping[str, dict[str, list[float]]], camera: str, version: str) -> list[float]:
    if camera == ALL_CAMERAS:
        return [v for per in source.values() for v in per[version]]
    return source.get(camera, {"v1": [], "v2": []})[version]


def _has_position(positions: Sequence[Position | None]) -> bool:
    return any(position is not None for position in positions)


def _version_positions(row: ComparisonRow, version: str) -> tuple[Position | None, ...]:
    return row.v1_positions if version == "v1" else row.v2_positions


def coverage(rows: Sequence[ComparisonRow]) -> dict[str, Any]:
    """Timestamps with at least one projected position, per camera and as a camera union."""
    result: dict[str, Any] = {}
    timestamps = sorted({row.timestamp for row in rows})
    for version in VERSIONS:
        per_camera: dict[str, Any] = {}
        for camera in _cameras(row.camera_id for row in rows):
            camera_rows = [row for row in rows if row.camera_id == camera]
            per_camera[camera] = {
                "with_position": sum(
                    _has_position(_version_positions(row, version)) for row in camera_rows
                ),
                "total": len({row.timestamp for row in camera_rows}),
            }
        union = {row.timestamp for row in rows if _has_position(_version_positions(row, version))}
        per_camera[ALL_CAMERAS] = {"with_position": len(union), "total": len(timestamps)}
        result[version] = per_camera
    return result


def _distance(a: Position, b: Position) -> float:
    return math.dist(a, b)


def speed_jumps(
    rows: Sequence[ComparisonRow], version: str, max_speed_m_s: float
) -> dict[str, Any]:
    """Speeds between consecutive timestamps that have a position, per camera.

    With several positions in a frame the smallest pairwise speed is used, i.e. the
    most charitable continuation; a jump is a step strictly above ``max_speed_m_s``.
    """
    result: dict[str, Any] = {}
    for camera in _cameras(row.camera_id for row in rows):
        frames = sorted(
            (
                row.timestamp,
                [p for p in _version_positions(row, version) if p is not None],
            )
            for row in rows
            if row.camera_id == camera
        )
        frames = [frame for frame in frames if frame[1]]
        steps = []
        for (t0, p0), (t1, p1) in zip(frames, frames[1:], strict=False):
            dt = t1 - t0
            if dt <= 0:
                raise ValueError(f"non-increasing timestamps for {camera} at {t0}")
            speed = min(_distance(a, b) for a in p0 for b in p1) / dt
            steps.append({"from_s": t0, "to_s": t1, "dt_s": dt, "speed_m_s": speed})
        jumps = [step for step in steps if step["speed_m_s"] > max_speed_m_s]
        result[camera] = {
            "steps": len(steps),
            "jump_count": len(jumps),
            "max_speed_m_s": max((s["speed_m_s"] for s in steps), default=None),
            "jumps": jumps,
        }
    result[ALL_CAMERAS] = {
        "steps": sum(item["steps"] for item in result.values()),
        "jump_count": sum(item["jump_count"] for item in result.values()),
    }
    return result


def primary_reason(reasons: Sequence[str]) -> str:
    return reasons[0] if reasons else "UNSPECIFIED"


def rejection_summary(rows: Sequence[ComparisonRow]) -> dict[str, Any]:
    """v2 outcome per camera: kept/rejected components and reason label histogram.

    The histogram counts every label (a component can carry several); ``by_primary``
    counts each rejected component once, under its first reason, so it sums to
    ``rejected``.
    """
    result: dict[str, Any] = {}
    totals: dict[str, Any] = {
        "components": 0,
        "kept": 0,
        "rejected": 0,
        "no_detection_timestamps": 0,
        "reasons": Counter(),
        "by_primary": Counter(),
    }
    for camera in _cameras(row.camera_id for row in rows):
        entry: dict[str, Any] = {
            "components": 0,
            "kept": 0,
            "rejected": 0,
            "no_detection_timestamps": 0,
            "reasons": Counter(),
            "by_primary": Counter(),
        }
        for row in rows:
            if row.camera_id != camera:
                continue
            if not row.v2_positions:
                flat = {reason for reasons in row.v2_reasons for reason in reasons}
                if NO_DETECTION in flat or not flat:
                    entry["no_detection_timestamps"] += 1
                continue
            if len(row.v2_reasons) != len(row.v2_positions):
                raise ValueError(f"reason/component count differs at {camera} t={row.timestamp}")
            for position, reasons in zip(row.v2_positions, row.v2_reasons, strict=True):
                entry["components"] += 1
                if position is not None:
                    entry["kept"] += 1
                    continue
                entry["rejected"] += 1
                entry["reasons"].update(reasons)
                entry["by_primary"][primary_reason(reasons)] += 1
        for key in ("components", "kept", "rejected", "no_detection_timestamps"):
            totals[key] += entry[key]
        totals["reasons"].update(entry["reasons"])
        totals["by_primary"].update(entry["by_primary"])
        result[camera] = entry
    result[ALL_CAMERAS] = totals
    return {
        camera: {
            **entry,
            "reasons": dict(sorted(entry["reasons"].items())),
            "by_primary": dict(sorted(entry["by_primary"].items())),
        }
        for camera, entry in result.items()
    }


def _quantiles(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "min_m": None, "median_m": None, "mean_m": None, "max_m": None}
    return {
        "count": len(values),
        "min_m": min(values),
        "median_m": statistics.median(values),
        "mean_m": statistics.fmean(values),
        "max_m": max(values),
    }


def sensitivity_summary(
    rows: Sequence[ComparisonRow], visibility: Sequence[VisibilityRow] = ()
) -> dict[str, Any]:
    """Floor displacement for +/-1 px at the v2 contact pixel, split by v2 outcome."""
    result: dict[str, Any] = {}
    for camera in _cameras(row.camera_id for row in rows):
        kept: list[float] = []
        rejected: list[float] = []
        for row in rows:
            if row.camera_id != camera:
                continue
            for index, value in enumerate(row.pixel_sensitivity_m):
                if value is None:
                    continue
                position = row.v2_positions[index] if index < len(row.v2_positions) else None
                (kept if position is not None else rejected).append(value)
        entry: dict[str, Any] = {
            "all": _quantiles(kept + rejected),
            "v2_kept": _quantiles(kept),
            "v2_rejected": _quantiles(rejected),
        }
        camera_visibility = [row for row in visibility if row.camera_id == camera]
        if camera_visibility:
            incidences = [
                row.bottom_incidence
                for row in camera_visibility
                if row.bottom_incidence is not None
            ]
            entry["visibility"] = {
                "timestamps": len(camera_visibility),
                "bottom_visible": sum(row.bottom_visible for row in camera_visibility),
                "incidence_eligible": sum(row.incidence_eligible for row in camera_visibility),
                "bottom_incidence_min": min(incidences, default=None),
                "bottom_incidence_median": statistics.median(incidences) if incidences else None,
                "bottom_incidence_max": max(incidences, default=None),
            }
        result[camera] = entry
    return result


def office_summary(rows: Sequence[ComparisonRow], max_speed_m_s: float) -> dict[str, Any]:
    """Office regression: v1 positions vs v2 kept/rejected per camera."""
    rejection = rejection_summary(rows)
    v1_jumps = speed_jumps(rows, "v1", max_speed_m_s)
    result: dict[str, Any] = {}
    for camera in [*_cameras(row.camera_id for row in rows), ALL_CAMERAS]:
        camera_rows = [row for row in rows if camera in (ALL_CAMERAS, row.camera_id)]
        result[camera] = {
            "v1_positions": sum(
                position is not None for row in camera_rows for position in row.v1_positions
            ),
            "v1_timestamps_with_position": sum(
                _has_position(row.v1_positions) for row in camera_rows
            ),
            "v1_jump_count": v1_jumps[camera]["jump_count"],
            "v2_components": rejection[camera]["components"],
            "v2_kept": rejection[camera]["kept"],
            "v2_rejected": rejection[camera]["rejected"],
            "v2_reasons": rejection[camera]["reasons"],
            "v2_by_primary": rejection[camera]["by_primary"],
            "no_detection_timestamps": rejection[camera]["no_detection_timestamps"],
        }
    result["v1_jumps"] = {k: v for k, v in v1_jumps.items() if k != ALL_CAMERAS}
    return result


def _close(a: Any, b: Any) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= CROSSCHECK_TOLERANCE
    return bool(a == b)


def crosscheck(
    report: Mapping[str, Any], evaluation: Mapping[str, Any], receipt: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare recomputed values with the producer's own evaluation/receipt claims."""
    errors = report["auditorium"]["errors"][ALL_CAMERAS]
    checks: list[tuple[str, Any, Any]] = []
    paired_claim = evaluation.get("paired_same_frames", {})
    for version in VERSIONS:
        claim = paired_claim.get(version, {})
        mine = errors["paired"][version]
        checks.append((f"paired.{version}.count", mine["count"], claim.get("count")))
        checks.append((f"paired.{version}.mean_m", mine["mean_m"], claim.get("mean_m")))
        checks.append((f"paired.{version}.max_m", mine["max_m"], claim.get("max_m")))
        summary_claim = evaluation.get("summary", {}).get(version, {})
        available = errors["all_available"][version]
        checks.append(
            (f"all.{version}.count", available["count"], summary_claim.get("projected_count"))
        )
        checks.append((f"all.{version}.mean_m", available["mean_m"], summary_claim.get("mean_m")))
    coverage_claim = receipt.get("coverage", {})
    checks.append(
        (
            "coverage.v2.timestamps_with_position",
            report["auditorium"]["coverage"]["v2"][ALL_CAMERAS]["with_position"],
            coverage_claim.get("timestamps_with_at_least_one_v2_position"),
        )
    )
    checks.append(
        (
            "rejection.reasons",
            report["auditorium"]["rejection"][ALL_CAMERAS]["reasons"],
            coverage_claim.get("rejection_reasons"),
        )
    )
    office_claim = receipt.get("office_regression", {})
    office = report["office"][ALL_CAMERAS]
    checks.append(
        ("office.v1_positions", office["v1_positions"], office_claim.get("old_projected_count"))
    )
    checks.append(
        ("office.v2_components", office["v2_components"], office_claim.get("v2_components"))
    )
    checks.append(("office.v2_kept", office["v2_kept"], office_claim.get("v2_projected")))
    items = [
        {"check": name, "recomputed": mine, "claimed": claim, "match": _close(mine, claim)}
        for name, mine, claim in checks
        if claim is not None
    ]
    return {"all_match": all(item["match"] for item in items), "checks": items}


def build_report(
    *,
    errors_csv: Path,
    auditorium_comparison_csv: Path,
    office_comparison_csv: Path,
    visibility_csv: Path,
    evaluation_json: Path,
    receipt_json: Path,
    max_speed_m_s: float = DEFAULT_MAX_SPEED_M_S,
) -> dict[str, Any]:
    inputs = {
        "errors_csv": errors_csv,
        "auditorium_comparison_csv": auditorium_comparison_csv,
        "office_comparison_csv": office_comparison_csv,
        "visibility_csv": visibility_csv,
        "evaluation_json": evaluation_json,
        "receipt_json": receipt_json,
    }
    error_rows = load_errors(errors_csv)
    auditorium = load_comparison(auditorium_comparison_csv)
    office = load_comparison(office_comparison_csv)
    visibility = load_visibility(visibility_csv)
    evaluation = json.loads(evaluation_json.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_json.read_text(encoding="utf-8"))

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "POSTHOC_EVALUATION_ONLY",
        "research_question": "RQ1_SINGLE_CAMERA_GROUND_CONTACT",
        "run_id": receipt.get("run_id", "UNKNOWN"),
        "dataset_sha256": evaluation.get("dataset_sha256", "UNKNOWN"),
        "prediction_sha256": evaluation.get("prediction_sha256", "UNKNOWN"),
        "inputs": {
            role: {"filename": path.name, "sha256": sha256_file(path)}
            for role, path in inputs.items()
        },
        "parameters": {
            "max_speed_m_s": max_speed_m_s,
            "pairing": "COMPONENT_ALIGNED_BOTH_V1_AND_V2_NON_NULL",
            "jump_rule": "CONSECUTIVE_TIMESTAMPS_WITH_POSITION_MIN_PAIRWISE_SPEED_ABOVE_CAP",
            "reason_histogram": "EVERY_LABEL_COUNTED_ON_REJECTED_COMPONENTS",
        },
        "auditorium": {
            "errors": error_summary(error_rows),
            "coverage": coverage(auditorium),
            "jumps": {
                version: speed_jumps(auditorium, version, max_speed_m_s) for version in VERSIONS
            },
            "rejection": rejection_summary(auditorium),
            "pixel_sensitivity": sensitivity_summary(auditorium, visibility),
        },
        "office": office_summary(office, max_speed_m_s),
        "limitations": [
            "SYNTHETIC_SINGLE_ROUTE_NOT_STATISTICAL",
            "GT_USED_ONLY_AFTER_PREDICTIONS_FROZEN",
            "IDENTITY_UNCONFIRMED",
        ],
    }
    report["crosscheck"] = crosscheck(report, evaluation, receipt)
    return report


def time_series(
    rows: Sequence[ErrorRow],
) -> dict[str, list[tuple[float, float | None, float | None]]]:
    """Per camera ``(timestamp, v1, v2)`` using the first component, for charts."""
    series: dict[str, list[tuple[float, float | None, float | None]]] = defaultdict(list)
    for row in sorted(rows, key=lambda r: (r.camera_id, r.timestamp)):
        v1 = row.v1[0] if row.v1 else None
        v2 = row.v2[0] if row.v2 else None
        series[row.camera_id].append((row.timestamp, v1, v2))
    return dict(series)
