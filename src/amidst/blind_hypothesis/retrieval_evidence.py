"""Frame-retrieval results to negative-evidence candidates (task K5).

Implements frame-retrieval contract §6 as a pure function: which retrieved frames
may serve as negative evidence for a blind-interval hypothesis, and the
blind-hypothesis §3.3 entry built from them. It reads nothing: the perception
outcome of each frame and the resolved visibility-index entry arrive as data from
the backend.

Only ``NO_DETECTION`` frames qualify: an available, hash-verified RGB record that
the perception run evaluated, with zero measurements in the whole frame, seen
through a ``SOURCE_MESH_RAYCAST`` footprint, strictly inside the open blind
interval. ``DETECTION_PRESENT`` and ``UNKNOWN`` frames are never negative evidence
and are never read as "absent". Evidence holds only at the frame times.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Collection, Mapping, Sequence
from typing import Any

from amidst.blind_hypothesis.engine import REQUIRED_VISIBILITY_METHOD, canonical_sha256

NO_DETECTION = "NO_DETECTION"
DETECTION_PRESENT = "DETECTION_PRESENT"
UNKNOWN = "UNKNOWN"
ORIGIN = "RETRIEVAL_FEEDBACK"
# D21: the footprint must be the stricter C5 rule (foot and torso probes both visible).
# Entries without ``visibility_rule`` (older C5 indexes) are deliberately not eligible.
REQUIRED_VISIBILITY_RULE = "FOOT_AND_TORSO_PROBES_VISIBLE"
_EDGE_TOLERANCE_S = 1e-6


def _real(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _resolved_floor(entry: Any) -> dict[str, Any] | None:
    """The §3.3 ``visible_floor`` copied from a visibility-index entry, or None if unusable."""

    if not isinstance(entry, Mapping) or entry.get("method") != REQUIRED_VISIBILITY_METHOD:
        return None
    floor_z, polygons = _real(entry.get("floor_z_m")), entry.get("polygons")
    index_sha = entry.get("index_sha256")
    if floor_z is None or not isinstance(polygons, list) or not isinstance(index_sha, str):
        return None
    if not index_sha:
        return None
    for ring in polygons:
        if not isinstance(ring, list) or len(ring) < 3:
            return None
        for point in ring:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                return None
            if _real(point[0]) is None or _real(point[1]) is None:
                return None
    return {
        "method": REQUIRED_VISIBILITY_METHOD,
        "floor_z_m": floor_z,
        "polygons": copy.deepcopy(polygons),
        "index_sha256": index_sha,
    }


FrameKey = tuple[str, str, str, str, str]


def frame_key(
    camera_id: Any, frame_ref: Any, visibility_ref: Any, producer: Any, version: Any
) -> FrameKey:
    """Identity of one applied frame: camera, frame, footprint entry and perception run."""

    return (str(camera_id), str(frame_ref), str(visibility_ref), str(producer), str(version))


def applied_frame_keys_from_request(
    hypothesis_request_or_evidence: Mapping[str, Any] | Sequence[Any],
) -> set[FrameKey]:
    """Frames already carried by a hypothesis request, whatever the entry origin.

    Accepts the request mapping (its ``negative_evidence``) or the evidence list. Pass
    the result as ``applied_frame_keys`` so a frame that a ``BLIND_INTERVAL_BASELINE``
    entry already applied is not applied again by a ``RETRIEVAL_FEEDBACK`` entry.
    Malformed entries contribute nothing (they fail the hypothesis request anyway).
    """

    entries = (
        hypothesis_request_or_evidence.get("negative_evidence")
        if isinstance(hypothesis_request_or_evidence, Mapping)
        else hypothesis_request_or_evidence
    )
    keys: set[FrameKey] = set()
    for entry in entries if isinstance(entries, (list, tuple)) else []:
        if not isinstance(entry, Mapping):
            continue
        producer = entry.get("detection_producer")
        producer = producer if isinstance(producer, Mapping) else {}
        frames = entry.get("frame_refs")
        for frame in frames if isinstance(frames, list) else []:
            if isinstance(frame, Mapping) and isinstance(frame.get("frame_ref"), str):
                keys.add(
                    frame_key(
                        entry.get("camera_id"),
                        frame["frame_ref"],
                        entry.get("visibility_ref"),
                        producer.get("producer"),
                        producer.get("version"),
                    )
                )
    return keys


def _evaluation_outcome(evaluation: Any) -> tuple[str, str]:
    """``(outcome, reason)`` from a frame evaluation record, before footprint and interval."""

    if not isinstance(evaluation, Mapping):
        return UNKNOWN, "FRAME_EVALUATION_MISSING"
    if evaluation.get("frame_available") is not True:
        return UNKNOWN, "FRAME_UNAVAILABLE"
    if evaluation.get("rgb_hash_verified") is not True:
        return UNKNOWN, "RGB_HASH_NOT_VERIFIED"
    if evaluation.get("provenance_ok") is not True:
        return UNKNOWN, "PROVENANCE_MISMATCH"
    if evaluation.get("perception_evaluated") is not True:
        return UNKNOWN, "PERCEPTION_NOT_EVALUATED"
    count = evaluation.get("measurement_count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return UNKNOWN, "MEASUREMENT_COUNT_UNKNOWN"
    producer = evaluation.get("detection_producer")
    if count > 0:
        return DETECTION_PRESENT, "MEASUREMENTS_PRESENT"
    if not isinstance(producer, Mapping) or not producer.get("producer"):
        return UNKNOWN, "DETECTION_PRODUCER_MISSING"
    return NO_DETECTION, "ELIGIBLE"


def negative_evidence_from_retrieval(
    retrieval_response: Mapping[str, Any],
    *,
    frame_evaluations: Mapping[str, Mapping[str, Any]],
    visibility_entries: Mapping[str, Mapping[str, Any]],
    interval_s: Sequence[float] | None = None,
    applied_negative_evidence_refs: Collection[str] = (),
    applied_frame_keys: Collection[Sequence[Any]] = (),
) -> dict[str, Any]:
    """Turn a ``workbench.frame-retrieval.v1`` response into negative-evidence drafts.

    ``frame_evaluations`` maps ``frame_ref`` to the backend's perception lookup:
    ``{frame_available, rgb_hash_verified, provenance_ok, perception_evaluated,
    measurement_count, detection_producer: {producer, version}}`` (this shape is a
    K5 proposal; the contract leaves it to the retrieval API, OPEN). A missing or
    malformed record, or any flag not exactly ``True``, makes the frame
    ``UNKNOWN``. ``visibility_entries`` maps ``visibility_ref`` to the resolved
    index entry ``{method, floor_z_m, polygons, index_sha256, visibility_rule}``;
    ``visibility_rule`` must be ``FOOT_AND_TORSO_PROBES_VISIBLE`` (D21), otherwise
    the frame is ``UNKNOWN`` / ``VISIBILITY_RULE_NOT_ELIGIBLE``. Entries from older
    indexes lack the field, so their frames are never eligible (fail closed).

    The blind interval is ``query.hypothesis_interval`` of the response (the used,
    possibly D7-substituted one) and/or ``interval_s``; both given: their
    intersection. Without either, no frame is usable. Frames at the interval
    ends, outside it, or at an original (substituted) endpoint's own time are never
    negative evidence. ``applied_negative_evidence_refs`` lets the caller drop
    drafts whose ref the hypothesis request already carries (second line of defence).

    ``applied_frame_keys`` (see :func:`applied_frame_keys_from_request`) holds the
    ``(camera_id, frame_ref, visibility_ref, producer, version)`` of frames the
    hypothesis request already carries, any origin. Such a frame yields no evidence;
    its row is ``NO_DETECTION`` / ``ALREADY_APPLIED_FRAME`` and not eligible. The same
    frame under another producer or version is a different key, not a duplicate.
    A draft left without frames is not emitted.

    Returns ``negative_evidence_candidates`` (ready to append to a hypothesis
    request) and ``frame_outcomes`` (one row per retrieved frame, for the frame
    wall). Deterministic; an entry with empty ``polygons`` is valid and prunes
    nothing.
    """

    empty: dict[str, Any] = {
        "negative_evidence_candidates": [],
        "frame_outcomes": [],
        "skipped_already_applied": [],
        "interval_s": None,
    }
    if not isinstance(retrieval_response, Mapping) or retrieval_response.get("status") != "READY":
        return empty
    query = retrieval_response.get("query")
    query = query if isinstance(query, Mapping) else {}
    lower, upper = -math.inf, math.inf
    bounds = []
    declared = query.get("hypothesis_interval")
    if isinstance(declared, Mapping):
        bounds.append((_real(declared.get("start_s")), _real(declared.get("end_s"))))
    if interval_s is not None:
        bounds.append((_real(interval_s[0]), _real(interval_s[1])))
    known = bool(bounds)
    for start, end in bounds:
        if start is None or end is None or end <= start:
            known = False
            break
        lower, upper = max(lower, start), min(upper, end)
    known = known and upper > lower
    originals = [
        t
        for item in query.get("endpoint_substitutions") or []
        if isinstance(item, Mapping) and (t := _real(item.get("original_timestamp_s"))) is not None
    ]
    applied_keys = {frame_key(*key) for key in applied_frame_keys}
    query_id = retrieval_response.get("query_id")
    query_id = query_id if isinstance(query_id, str) else None

    outcomes: list[dict[str, Any]] = []
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for result in retrieval_response.get("results") or []:
        if not isinstance(result, Mapping):
            continue
        camera = result.get("camera_id")
        visibility_ref = result.get("visibility_ref")
        method = result.get("method")
        visibility_entry = visibility_entries.get(visibility_ref)
        rule_ok = (
            isinstance(visibility_entry, Mapping)
            and visibility_entry.get("visibility_rule") == REQUIRED_VISIBILITY_RULE
        )
        floor = _resolved_floor(visibility_entry)
        for window in result.get("windows") or []:
            if not isinstance(window, Mapping):
                continue
            for frame in window.get("frames") or []:
                frame_ref = frame.get("frame_ref") if isinstance(frame, Mapping) else None
                ts = _real(frame.get("timestamp_s")) if isinstance(frame, Mapping) else None
                row = {
                    "camera_id": camera,
                    "frame_ref": frame_ref,
                    "timestamp_s": ts,
                    "outcome": UNKNOWN,
                    "reason": "FRAME_MALFORMED",
                    "negative_evidence_eligible": False,
                }
                outcomes.append(row)
                if (
                    not isinstance(frame_ref, str)
                    or not isinstance(camera, str)
                    or ts is None
                    or not isinstance(frame.get("reason"), Mapping)
                ):
                    continue
                footprint = frame["reason"].get("footprint_method", method)
                evaluation = frame_evaluations.get(frame_ref)
                if any(abs(ts - t) <= _EDGE_TOLERANCE_S for t in originals):
                    # The flagged observation's own frame holds a detection by definition.
                    row.update(outcome=DETECTION_PRESENT, reason="ORIGINAL_ENDPOINT_FRAME")
                    continue
                if frame_ref == "UNKNOWN":
                    row["reason"] = "FRAME_REF_UNKNOWN"  # OPEN FR-Q3: cannot be keyed
                    continue
                outcome, reason = _evaluation_outcome(evaluation)
                if outcome == NO_DETECTION and not (
                    footprint == method == REQUIRED_VISIBILITY_METHOD
                ):
                    outcome, reason = UNKNOWN, "FOOTPRINT_NOT_SOURCE_MESH_RAYCAST"
                row.update(outcome=outcome, reason=reason)
                if outcome != NO_DETECTION:
                    continue
                if not known:
                    row["reason"] = "INTERVAL_UNKNOWN"
                elif not lower + _EDGE_TOLERANCE_S < ts < upper - _EDGE_TOLERANCE_S:
                    row["reason"] = "OUTSIDE_OPEN_INTERVAL"
                elif not isinstance(visibility_entry, Mapping):
                    row.update(outcome=UNKNOWN, reason="VISIBILITY_ENTRY_UNRESOLVED")
                elif not rule_ok:
                    row.update(outcome=UNKNOWN, reason="VISIBILITY_RULE_NOT_ELIGIBLE")
                elif floor is None:
                    row.update(outcome=UNKNOWN, reason="VISIBILITY_ENTRY_UNRESOLVED")
                else:
                    producer = evaluation["detection_producer"]
                    key = (
                        camera,
                        str(visibility_ref),
                        str(producer["producer"]),
                        str(producer.get("version")),
                    )
                    if frame_key(camera, frame_ref, visibility_ref, key[2], key[3]) in applied_keys:
                        row["reason"] = "ALREADY_APPLIED_FRAME"
                        continue
                    row["negative_evidence_eligible"] = True
                    groups.setdefault(key, []).append(
                        {"frame_ref": frame_ref, "timestamp_s": ts, "floor": floor}
                    )

    applied = set(applied_negative_evidence_refs)
    candidates: list[dict[str, Any]] = []
    skipped: list[str] = []
    for (camera, visibility_ref, producer, version), items in sorted(groups.items()):
        frames = sorted(
            {(i["timestamp_s"], i["frame_ref"]): i for i in items}.values(),
            key=lambda i: (i["timestamp_s"], i["frame_ref"]),
        )
        frame_refs = [
            {"frame_ref": i["frame_ref"], "timestamp_s": i["timestamp_s"]} for i in frames
        ]
        entry: dict[str, Any] = {
            "negative_evidence_ref": "negev:"
            + canonical_sha256(
                {
                    "query_id": query_id,
                    "camera_id": camera,
                    "visibility_ref": visibility_ref,
                    "detection_producer": [producer, version],
                    "frames": [[f["timestamp_s"], f["frame_ref"]] for f in frame_refs],
                }
            )[:24],
            "origin": ORIGIN,
            "camera_id": camera,
            "frame_refs": frame_refs,
            "visibility_ref": visibility_ref,
            "visible_floor": frames[0]["floor"],
            "detection_result": NO_DETECTION,
            "detection_producer": {"producer": producer, "version": version},
            "retrieval_query_id": query_id,
        }
        entry["sha256"] = canonical_sha256(entry)
        if entry["negative_evidence_ref"] in applied:
            skipped.append(entry["negative_evidence_ref"])
        else:
            candidates.append(entry)
    return {
        "negative_evidence_candidates": candidates,
        "frame_outcomes": outcomes,
        "skipped_already_applied": skipped,
        "interval_s": [lower, upper] if known else None,
    }
