"""Selected-seed, camera-local linking on an explicit pinned index grid.

No tracking model, interpolation, cross-camera identity, media reads or defaults.
Session JSONL serialization belongs to the controller, not this module.
"""
import hashlib
import json
import math
import re
from copy import deepcopy
from dataclasses import dataclass


TRACKABLE_OBJECT_CLASSES: frozenset[str] = frozenset({
    "person",
    "car",
    "bicycle",
    "motorcycle",
    "bus",
    "truck",
    "backpack",
    "handbag",
    "suitcase",
})
TRACKABLE_CLASSES_V1: frozenset[str] = TRACKABLE_OBJECT_CLASSES


def is_trackable_class(class_label: str, *, allow_non_person: bool = True) -> bool:
    """Return True when class_label is supported by the camera-local IoU linker."""
    if not isinstance(class_label, str):
        return False
    if not allow_non_person:
        return class_label == "person"
    return class_label in TRACKABLE_OBJECT_CLASSES


class LinkError(ValueError):
    def __init__(self, message, code="DataIntegrityError"):
        super().__init__(message)
        self.code = code


def _hash(document):
    preimage = {k: v for k, v in document.items()
                if k not in {"content_sha256", "parameter_set_id", "stats"}}
    return hashlib.sha256(json.dumps(preimage, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _number(value, name, low=0, high=None):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (low is not None and value < low) or (high is not None and value > high)):
        raise LinkError(f"Invalid {name}")
    return value


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise LinkError(f"Invalid {name}", "PARAMETER_GRID_MISMATCH")
    return value


@dataclass(frozen=True)
class LinkParameters:
    parameter_set_id: str
    content_sha256: str
    index_id: str
    run_id: str
    interval_us: int
    max_gap_us: int
    max_gap_samples: int
    iou_min: float
    center_dist_max_diag_ratio: float
    min_score: float
    color_rule: str
    ambiguity_margin: float

    @classmethod
    def from_document(cls, document, *, expected_sha256, scene_revision, run_id, index_id,
                      index_interval_us):
        """Validate explicit parameters; missing or unapproved values never become defaults.

        This selected-seed component checks its camera grid. The Q2 controller must
        check every camera in resolved_scope before choosing any seed (§8.2).
        """
        doc = deepcopy(document)
        digest = _hash(doc)
        if (doc.get("schema_version") != "q-demo.parameter-set.v1"
                or digest != expected_sha256 or digest != doc.get("content_sha256")
                or doc.get("parameter_set_id") != "pset:q-demo:" + digest[:16]):
            raise LinkError("Parameter hash/schema mismatch")
        approval = doc.get("approval", {})
        if (approval.get("status") != "APPROVED" or not approval.get("approval_ref")
                or not approval.get("approved_by")):
            raise LinkError("Parameter set not approved", "PARAMETERS_NOT_APPROVED")
        scope = doc["applies_to"]
        if (scope.get("scene_revision") != scene_revision or run_id not in scope.get("run_ids", [])
                or index_id not in scope.get("detection_index_ids", [])):
            raise LinkError("Parameter scope mismatch")
        interval = _integer(index_interval_us, "index_interval_us", 1)
        if type(scope.get("index_interval_us")) is not int or scope["index_interval_us"] != interval:
            raise LinkError("Parameter grid mismatch", "PARAMETER_GRID_MISMATCH")
        items = doc["parameters"]
        if len({p["name"] for p in items}) != len(items):
            raise LinkError("Duplicate parameter")
        params = {p["name"]: p for p in items}
        required = {"link_iou_min", "link_center_dist_max_diag_ratio", "link_max_gap_us",
                    "link_min_score", "link_color_rule", "link_ambiguity_margin"}
        if not required <= params.keys():
            raise LinkError("Missing linker parameters", "PARAMETERS_NOT_APPROVED")
        for name in required | ({"link_max_gap_samples"} & params.keys()):
            if params[name].get("status") != "APPROVED" or not params[name].get("proposal_ref"):
                raise LinkError("Unapproved linker parameter", "PARAMETERS_NOT_APPROVED")
        p = {name: item["value"] for name, item in params.items()}
        gap = _integer(p["link_max_gap_us"], "link_max_gap_us", 1)
        if gap % interval or gap < interval:
            raise LinkError("Gap is not a positive grid multiple", "PARAMETER_GRID_MISMATCH")
        samples = gap // interval - 1
        if "link_max_gap_samples" in p and (type(p["link_max_gap_samples"]) is not int
                                             or p["link_max_gap_samples"] != samples):
            raise LinkError("Derived gap mismatch", "PARAMETER_GRID_MISMATCH")
        # Explicit rule vocabulary of this component. Other values fail closed;
        # no claim that any rule/value has been approved for real runs.
        if p["link_color_rule"] not in {"NOT_NONE", "STRONG", "STRONG_OR_WEAK"}:
            raise LinkError("Unsupported explicit color rule", "PARAMETERS_NOT_APPROVED")
        return cls(doc["parameter_set_id"], digest, index_id, run_id, interval, gap, samples,
                   _number(p["link_iou_min"], "link_iou_min", 0, 1),
                   _number(p["link_center_dist_max_diag_ratio"], "center ratio"),
                   _number(p["link_min_score"], "link_min_score", 0, 1),
                   p["link_color_rule"],
                   _number(p["link_ambiguity_margin"], "ambiguity margin", 0, 1))


def _box(observation):
    box = observation.get("bbox_xyxy_px")
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        raise LinkError("Invalid bbox")
    for number in box:
        _number(number, "bbox coordinate", low=None)
    if box[2] <= box[0] or box[3] <= box[1]:
        raise LinkError("Degenerate bbox")
    return box


def _iou(a, b):
    area = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return area / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - area)


@dataclass(frozen=True)
class LinkStep:
    """Internal result; `link` contains exactly the six contract §8.2 fields."""
    link: dict
    state: str
    transitions: tuple
    timestamp_us: int
    decision_time_us: int | None
    first_missing_us: int | None
    ambiguous_observation_ids: tuple
    local_segment_id: str
    parameter_set_sha256: str
    source_grid: dict
    identity_verdict: str = "UNCONFIRMED"


class LocalLinker:
    """Follow one explicitly selected seed. Each grid cell can attach at most one box.

    SEARCHING terminates this local segment. Starting from a later observation
    requires a new instance/segment; it cannot silently resurrect the old ID.
    """
    def __init__(self, seed_record, observation_id, *, parameters, stride_samples,
                 index_grid_origin_frame, color_label=None, target_class="person",
                 allow_non_person=True):
        self.parameters = parameters
        self.stride = _integer(stride_samples, "stride_samples", 1)
        self.origin = _integer(index_grid_origin_frame, "index_grid_origin_frame")
        if not isinstance(target_class, str) or not target_class.strip():
            raise LinkError("Invalid target class", "UNSUPPORTED_CLASS")
        if color_label is not None and target_class != "person":
            raise LinkError("Color condition is only supported for person", "UNSUPPORTED_CONDITION")
        if not is_trackable_class(target_class, allow_non_person=allow_non_person):
            raise LinkError(f"Class not supported by linker: {target_class}", "CLASS_NOT_SUPPORTED_BY_LINKER")
        self.target_class = target_class
        self.color_label = color_label
        self.scope = tuple(seed_record[k] for k in ("run_id", "clock_id", "camera_id"))
        if self.scope[0] != parameters.run_id:
            raise LinkError("Seed outside parameter run scope")
        self._validate_record(seed_record)
        if seed_record["frame_state"] != "INFERRED" or not self._on_grid(seed_record["frame_index"]):
            raise LinkError("Seed is not an inferred grid observation")
        found = [o for o in seed_record["detections"] if o["observation_id"] == observation_id]
        if len(found) != 1 or found[0]["class_label"] != self.target_class or not self._eligible(found[0]):
            raise LinkError("Invalid seed")
        self.last = deepcopy(found[0])
        self.history = [(seed_record["timestamp_us"], deepcopy(found[0]))]
        self.last_time = seed_record["timestamp_us"]
        self.last_frame = seed_record["frame_index"]
        self.grid_frame, self.grid_time = self.last_frame, self.last_time
        self.seen_frame = self.last_frame
        self.first_missing_us = None
        self.state = "PLAYING"
        seg_preimage = [*self.scope, observation_id, parameters.content_sha256]
        if self.target_class != "person":
            seg_preimage.append(self.target_class)
        self.segment_id = "local:" + hashlib.sha256(json.dumps(
            seg_preimage, separators=(",", ":")
        ).encode()).hexdigest()[:16]

    def _on_grid(self, frame):
        return frame >= self.origin and (frame - self.origin) % self.stride == 0

    def _validate_record(self, record):
        if tuple(record.get(k) for k in ("run_id", "clock_id", "camera_id")) != self.scope:
            raise LinkError("Cross run/clock/camera input", "CROSS_RUN_OR_CLOCK")
        _integer(record.get("frame_index"), "frame_index")
        _integer(record.get("timestamp_us"), "timestamp_us")
        state = record.get("frame_state")
        detections = record.get("detections")
        if state not in {"INFERRED", "NOT_INFERRED", "MISSING", "NOT_SAMPLED"}:
            raise LinkError("Invalid frame state")
        if state == "INFERRED":
            if not isinstance(detections, list):
                raise LinkError("Inferred frame needs explicit detections")
            ids = set()
            for o in detections:
                oid = o.get("observation_id", "")
                match = re.fullmatch(r"obs:([0-9a-f]{16}):([^:]+):(\d+):(\d+)", oid)
                if (not match or match[1] != self.parameters.index_id.split(":")[-1]
                        or match[2] != self.scope[2]
                        or int(match[3]) != record["frame_index"] or oid in ids):
                    raise LinkError("Invalid/duplicate observation ref")
                ids.add(oid)
                _box(o)
                _number(o.get("score"), "score", 0, 1)
                if not isinstance(o.get("class_label"), str):
                    raise LinkError("Invalid class label")
        elif detections is not None:
            raise LinkError("Uninferred frame cannot contain observations")

    def _eligible(self, observation):
        if not isinstance(observation, dict):
            return False
        if observation.get("class_label") != self.target_class:
            return False
        score = observation.get("score")
        if score is None or not isinstance(score, (int, float)) or score < self.parameters.min_score:
            return False
        if self.color_label is None:
            return True
        verdict = (observation.get("color") or {}).get("verdicts", {}).get(self.color_label)
        if verdict not in {"STRONG", "WEAK", "UNKNOWN", "NONE"}:
            raise LinkError("Missing/invalid query color verdict")
        return verdict in {"NOT_NONE": {"STRONG", "WEAK", "UNKNOWN"},
                           "STRONG": {"STRONG"}, "STRONG_OR_WEAK": {"STRONG", "WEAK"}}[self.parameters.color_rule]

    def step(self, record):
        self._validate_record(record)
        frame, timestamp = record["frame_index"], record["timestamp_us"]
        if self.state == "SEARCHING":
            raise LinkError("Segment ended; explicitly select a new seed")
        if frame <= self.seen_frame:
            raise LinkError("Non-monotonic or duplicate frame")
        # Check skipped source cells as well; only explicit NOT_SAMPLED cells may be skipped.
        delta = frame - self.grid_frame
        expected_time_numerator = delta * self.parameters.interval_us
        if (expected_time_numerator % self.stride
                or timestamp != self.grid_time + expected_time_numerator // self.stride):
            raise LinkError("Timestamp/grid mismatch", "PARAMETER_GRID_MISMATCH")
        if not self._on_grid(frame):
            if record["frame_state"] != "NOT_SAMPLED" or delta >= self.stride:
                raise LinkError("Invalid unsampled grid record", "PARAMETER_GRID_MISMATCH")
            self.seen_frame = frame
            return None
        if delta != self.stride or record["frame_state"] == "NOT_SAMPLED":
            raise LinkError("Missing grid cell; supply explicit MISSING", "PARAMETER_GRID_MISMATCH")
        elapsed = timestamp - self.last_time
        previous = _box(self.last)
        reference = list(previous)
        method = "LAST_OBSERVATION_V1"
        def candidates(box):
            choices = []
            diag = math.hypot(box[2] - box[0], box[3] - box[1])
            for observation in record["detections"] or []:
                if not self._eligible(observation):
                    continue
                current = _box(observation)
                overlap = _iou(box, current)
                distance = math.hypot((current[0] + current[2] - box[0] - box[2]) / 2,
                                      (current[1] + current[3] - box[1] - box[3]) / 2)
                if overlap >= self.parameters.iou_min and distance <= diag * self.parameters.center_dist_max_diag_ratio:
                    choices.append((overlap, observation))
            return choices
        choices = candidates(previous) if record["frame_state"] == "INFERRED" else []
        if (not choices and record["frame_state"] == "INFERRED" and len(self.history) == 2
                and 0 < elapsed <= self.parameters.max_gap_us):
            (first_time, first), (last_time, last) = self.history
            first_box, last_box = _box(first), _box(last)
            dt = last_time - first_time
            if dt > 0:
                dx = ((last_box[0] + last_box[2]) - (first_box[0] + first_box[2])) / 2 * elapsed / dt
                dy = ((last_box[1] + last_box[3]) - (first_box[1] + first_box[3])) / 2 * elapsed / dt
                reference = [last_box[0]+dx, last_box[1]+dy, last_box[2]+dx, last_box[3]+dy]
                method = "CENTER_TRANSLATION_V1"
                choices = candidates(reference)
        choices.sort(key=lambda pair: (-pair[0], -pair[1]["score"], pair[1]["observation_id"]))
        ambiguous = (len(choices) > 1 and choices[0][0] - choices[1][0] < self.parameters.ambiguity_margin)
        reason = {"NOT_INFERRED": "FRAME_NOT_INFERRED", "MISSING": "FRAME_MISSING"}.get(
            record["frame_state"], "NO_CANDIDATE")
        chosen = None
        if ambiguous:
            reason = "AMBIGUOUS_LINK"
        elif choices:
            reason, chosen = "LINKED", choices[0]
        elapsed = timestamp - self.last_time
        gap = elapsed // self.parameters.interval_us - int(chosen is not None)
        link = {"prev_observation_id": self.last["observation_id"],
                "next_observation_id": chosen[1]["observation_id"] if chosen else None,
                "iou": _iou(previous, _box(chosen[1])) if chosen else None, "elapsed_us": elapsed,
                "gap_samples": gap, "decision": reason}
        if method != "LAST_OBSERVATION_V1" or self.first_missing_us is not None:
            link["matching_audit"] = {
                "method": method, "reference_bbox_xyxy_px": reference,
                "source_observations": [{"observation_id": o["observation_id"],
                    "timestamp_us": t, "bbox_xyxy_px": _box(o)} for t, o in self.history],
                "elapsed_us": elapsed, "actual_pair_iou": _iou(previous, _box(chosen[1])) if chosen else None,
                "reference_iou": chosen[0] if chosen else None,
                "event": "REACQUIRED" if chosen and self.first_missing_us is not None else "LINKED" if chosen else "NO_MATCH",
                "identity_verdict": "UNCONFIRMED"}
        transitions = []
        if chosen:
            self.history = (self.history + [(timestamp, deepcopy(chosen[1]))])[-2:]
            self.last, self.last_time, self.last_frame = deepcopy(chosen[1]), timestamp, frame
            self.state = "PLAYING"
            self.first_missing_us = None
            transitions.append("PLAYING")
        else:
            if self.first_missing_us is None:
                self.first_missing_us = timestamp
            self.state = "TEMP_LOST"
            transitions.append("TEMP_LOST")
            if gap > self.parameters.max_gap_samples:
                self.state = "SEARCHING"
                transitions.append("SEARCHING")
        self.grid_frame, self.grid_time, self.seen_frame = frame, timestamp, frame
        return LinkStep(link, self.state, tuple(transitions), timestamp,
                        timestamp if self.state == "SEARCHING" else None,
                        self.first_missing_us,
                        tuple(o["observation_id"] for _, o in choices) if ambiguous else (),
                        self.segment_id, self.parameters.content_sha256,
                        {"stride_samples": self.stride, "index_grid_origin_frame": self.origin,
                         "index_interval_us": self.parameters.interval_us})


def _single_view_from_sightings(sightings, as_of_us):
    """Build single-view switching sequence from sightings up to as_of_us."""
    clipped = []
    for s in sightings:
        a, b = s["range_us"]
        if as_of_us is not None:
            if a >= as_of_us:
                continue
            b = min(b, as_of_us)
        if a < b:
            clipped.append({"camera_id": s["camera_id"], "start": a, "end": b})
    if not clipped:
        return []
    clipped.sort(key=lambda item: (item["start"], -item["end"], item["camera_id"]))
    cur = clipped[0]
    cur_cam, cur_start, cur_end = cur["camera_id"], cur["start"], cur["end"]
    t = cur_end
    out = [{"kind": "ON_CAMERA", "camera_id": cur_cam, "range_us": [cur_start, cur_end],
            "evidence_state": "OBSERVED"}]
    while True:
        covering = [c for c in clipped if c["start"] <= t < c["end"]]
        if covering:
            covering.sort(key=lambda item: (-item["end"], item["camera_id"]))
            best = covering[0]
            out.append({"kind": "ON_CAMERA", "camera_id": best["camera_id"],
                        "range_us": [t, best["end"]], "evidence_state": "OBSERVED"})
            t = best["end"]
            continue
        later = [c for c in clipped if c["start"] >= t and c["end"] > t]
        if later:
            later.sort(key=lambda item: (item["start"], -item["end"], item["camera_id"]))
            nxt = later[0]
            if nxt["start"] > t:
                out.append({"kind": "GAP", "camera_id": None,
                            "range_us": [t, nxt["start"]], "evidence_state": "UNKNOWN"})
            out.append({"kind": "ON_CAMERA", "camera_id": nxt["camera_id"],
                        "range_us": [nxt["start"], nxt["end"]], "evidence_state": "OBSERVED"})
            t = nxt["end"]
            continue
        break
    merged = []
    for seg in out:
        if (merged and seg["kind"] == "ON_CAMERA" and merged[-1]["kind"] == "ON_CAMERA"
                and merged[-1]["camera_id"] == seg["camera_id"]
                and merged[-1]["range_us"][1] == seg["range_us"][0]):
            merged[-1]["range_us"][1] = seg["range_us"][1]
        else:
            merged.append(seg)
    if as_of_us is not None and merged[-1]["range_us"][1] < as_of_us:
        merged.append({"kind": "LOST", "camera_id": None,
                       "range_us": [merged[-1]["range_us"][1], as_of_us],
                       "evidence_state": "UNKNOWN"})
    return merged


def link_class_detections(
    records,
    *,
    target_class: str = "person",
    color_label: str | None = None,
    iou_threshold: float = 0.3,
    max_gap_frames: int = 2,
    min_track_len: int = 1,
    min_score: float = 0.4,
    center_dist_max_diag_ratio: float | None = None,
    color_rule: str = "STRONG",
    interval_us: int = 200_000,
    as_of_us: int | None = None,
    allow_non_person: bool = True,
    supported_classes=None,
    strict: bool = False,
    parameters: LinkParameters | None = None,
) -> dict:
    """Link same-camera detections of a trackable class across frames by IoU and gap tolerance."""
    if parameters is not None:
        interval_us = parameters.interval_us
        max_gap_frames = parameters.max_gap_samples
        iou_threshold = parameters.iou_min
        min_score = parameters.min_score
        center_dist_max_diag_ratio = parameters.center_dist_max_diag_ratio
        color_rule = parameters.color_rule
    """Link same-camera detections of a trackable class across frames by IoU and gap tolerance."""
    if not isinstance(target_class, str) or not target_class.strip():
        raise LinkError("Invalid target_class", "UNSUPPORTED_CLASS")
    if supported_classes is not None and target_class not in supported_classes:
        raise LinkError(f"Unsupported class: {target_class}", "UNSUPPORTED_CLASS")
    if color_label is not None:
        if not isinstance(color_label, str) or not color_label.strip():
            raise LinkError("Invalid color_label", "COLOR_UNKNOWN")
        if target_class != "person":
            raise LinkError("Color condition is only supported for person", "UNSUPPORTED_CONDITION")
        if color_rule not in {"NOT_NONE", "STRONG", "STRONG_OR_WEAK"}:
            raise LinkError("Unsupported explicit color rule", "PARAMETERS_NOT_APPROVED")
    if not is_trackable_class(target_class, allow_non_person=allow_non_person):
        if strict:
            raise LinkError(f"Class not supported by linker: {target_class}", "CLASS_NOT_SUPPORTED_BY_LINKER")
        return {
            "status": "UNSUPPORTED",
            "reasons": ["CLASS_NOT_SUPPORTED_BY_LINKER"],
            "target_class": target_class,
            "tracks": [],
            "sightings": [],
            "multi_view": [],
            "single_view": [],
            "identity_verdict": "UNCONFIRMED",
            "evidence_state": "UNKNOWN",
        }
    iou_threshold = _number(iou_threshold, "iou_threshold", 0, 1)
    max_gap_frames = _integer(max_gap_frames, "max_gap_frames", 0)
    min_track_len = _integer(min_track_len, "min_track_len", 1)
    min_score = _number(min_score, "min_score", 0, 1)
    interval_us = _integer(interval_us, "interval_us", 1)
    if center_dist_max_diag_ratio is not None:
        center_dist_max_diag_ratio = _number(center_dist_max_diag_ratio, "center_dist_max_diag_ratio", 0)
    if as_of_us is not None:
        as_of_us = _integer(as_of_us, "as_of_us", 0)

    by_camera = {}
    batch_run_id: str | None = None
    batch_clock_id: str | None = None
    max_record_end_us: int = 0

    for raw in records or []:
        if not isinstance(raw, dict):
            raise LinkError("Invalid frame record")
        cid = raw.get("camera_id")
        if not isinstance(cid, str) or not cid.strip():
            raise LinkError("Invalid camera_id")

        rid = raw.get("run_id")
        if rid is not None:
            if not isinstance(rid, str) or not rid.strip():
                raise LinkError("Invalid run_id", "CROSS_RUN_OR_CLOCK")
            if parameters is not None and rid != parameters.run_id:
                raise LinkError("Seed outside parameter run scope", "CROSS_RUN_OR_CLOCK")
            if batch_run_id is None:
                batch_run_id = rid
            elif batch_run_id != rid:
                raise LinkError("Cross run input", "CROSS_RUN_OR_CLOCK")

        clid = raw.get("clock_id")
        if clid is not None:
            if not isinstance(clid, str) or not clid.strip():
                raise LinkError("Invalid clock_id", "CROSS_RUN_OR_CLOCK")
            if batch_clock_id is None:
                batch_clock_id = clid
            elif batch_clock_id != clid:
                raise LinkError("Cross clock input", "CROSS_RUN_OR_CLOCK")

        frame_idx = _integer(raw.get("frame_index"), "frame_index", 0)
        raw_ts = raw.get("timestamp_us")
        if raw_ts is not None:
            ts_us = _integer(raw_ts, "timestamp_us", 0)
            if ts_us % interval_us != 0:
                raise LinkError("Timestamp/grid mismatch", "PARAMETER_GRID_MISMATCH")
            if strict and ts_us != frame_idx * interval_us:
                raise LinkError("Timestamp/grid mismatch", "PARAMETER_GRID_MISMATCH")
        else:
            ts_us = frame_idx * interval_us

        max_record_end_us = max(max_record_end_us, ts_us + interval_us)

        if as_of_us is not None and ts_us >= as_of_us:
            continue
        state = raw.get("frame_state", "INFERRED")
        if state not in {"INFERRED", "NOT_INFERRED", "MISSING", "NOT_SAMPLED"}:
            raise LinkError("Invalid frame state")
        by_camera.setdefault(cid, []).append((frame_idx, ts_us, state, raw.get("detections")))

    allowed_verdicts = {
        "NOT_NONE": {"STRONG", "WEAK", "UNKNOWN"},
        "STRONG": {"STRONG"},
        "STRONG_OR_WEAK": {"STRONG", "WEAK"},
    }.get(color_rule, {"STRONG"})

    tracks = []
    sightings = []
    for cid in sorted(by_camera):
        frames = sorted(by_camera[cid], key=lambda item: (item[0], item[1]))
        active = []
        finished = []
        for frame_idx, ts_us, state, raw_dets in frames:
            still_active = []
            for trk in active:
                frame_gap = frame_idx - trk["last_frame"] - 1
                time_gap = max(0, (ts_us - trk["last_time"]) // interval_us - 1)
                if frame_gap > max_gap_frames or time_gap > max_gap_frames:
                    finished.append(trk)
                else:
                    still_active.append(trk)
            active = still_active
            if state != "INFERRED":
                continue
            if raw_dets is None:
                raw_dets = []
            if not isinstance(raw_dets, list):
                raise LinkError("Inferred frame needs explicit detections")
            eligible = []
            for idx, det in enumerate(raw_dets):
                if not isinstance(det, dict):
                    raise LinkError("Invalid detection")
                cls_name = det.get("class_label")
                if not isinstance(cls_name, str):
                    raise LinkError("Invalid class label")
                if cls_name != target_class:
                    continue
                raw_score = det.get("score")
                if raw_score is None:
                    if strict:
                        raise LinkError("Missing detection score", "INVALID_SCORE")
                    continue
                score = _number(raw_score, "score", 0, 1)
                if score < min_score:
                    continue
                if color_label is not None:
                    verdict = (det.get("color") or {}).get("verdicts", {}).get(color_label)
                    if verdict not in {"STRONG", "WEAK", "UNKNOWN", "NONE"}:
                        raise LinkError("Missing/invalid query color verdict")
                    if verdict not in allowed_verdicts:
                        continue
                box = _box(det)
                obs_copy = deepcopy(det)
                if "observation_id" not in obs_copy or not isinstance(obs_copy["observation_id"], str):
                    obs_copy["observation_id"] = f"obs:syn:{cid}:{frame_idx}:{idx}"
                eligible.append((obs_copy, box, score))

            candidates = []
            for trk_i, trk in enumerate(active):
                prev_box = trk["last_box"]
                ref_box = prev_box
                if len(trk["steps"]) >= 2 and ts_us > trk["last_time"]:
                    _, t1, _, b1, _ = trk["steps"][-2]
                    _, t2, _, b2, _ = trk["steps"][-1]
                    dt = t2 - t1
                    elapsed = ts_us - t2
                    if dt > 0 and elapsed > interval_us:
                        dx = ((b2[0] + b2[2]) - (b1[0] + b1[2])) / 2 * elapsed / dt
                        dy = ((b2[1] + b2[3]) - (b1[1] + b1[3])) / 2 * elapsed / dt
                        ref_box = [b2[0] + dx, b2[1] + dy, b2[2] + dx, b2[3] + dy]
                for det_i, (obs_copy, box, score) in enumerate(eligible):
                    actual_iou = _iou(prev_box, box)
                    match_iou = max(actual_iou, _iou(ref_box, box))
                    if match_iou < iou_threshold:
                        continue
                    if center_dist_max_diag_ratio is not None:
                        diag = math.hypot(prev_box[2] - prev_box[0], prev_box[3] - prev_box[1])
                        dist = math.hypot((box[0] + box[2] - prev_box[0] - prev_box[2]) / 2,
                                          (box[1] + box[3] - prev_box[1] - prev_box[3]) / 2)
                        if dist > diag * center_dist_max_diag_ratio:
                            continue
                    candidates.append((match_iou, actual_iou, score, obs_copy["observation_id"], trk_i, det_i))

            candidates.sort(key=lambda item: (-item[0], -item[2], item[3], item[4], item[5]))
            matched_tracks = set()
            matched_dets = set()
            for match_iou, actual_iou, _, _, trk_i, det_i in candidates:
                if trk_i in matched_tracks or det_i in matched_dets:
                    continue
                matched_tracks.add(trk_i)
                matched_dets.add(det_i)
                obs_copy, box, _ = eligible[det_i]
                trk = active[trk_i]
                trk["steps"].append((frame_idx, ts_us, obs_copy, box, actual_iou))
                trk["last_frame"] = frame_idx
                trk["last_time"] = ts_us
                trk["last_box"] = box

            for det_i, (obs_copy, box, _) in enumerate(eligible):
                if det_i in matched_dets:
                    continue
                active.append({
                    "camera_id": cid,
                    "steps": [(frame_idx, ts_us, obs_copy, box, None)],
                    "last_frame": frame_idx,
                    "last_time": ts_us,
                    "last_box": box,
                })

        finished.extend(active)
        finished.sort(key=lambda trk: (trk["steps"][0][1], trk["steps"][0][0],
                                       trk["steps"][0][2]["observation_id"]))
        for trk in finished:
            steps = trk["steps"]
            if len(steps) < min_track_len:
                continue
            start_frame = steps[0][0]
            end_frame = steps[-1][0]
            start_us = steps[0][1]
            end_us = steps[-1][1] + interval_us
            if as_of_us is not None:
                end_us = min(end_us, as_of_us)
            if start_us >= end_us:
                continue
            obs_ids = [s[2]["observation_id"] for s in steps]
            frame_indices = [s[0] for s in steps]
            ious = [s[4] for s in steps[1:] if s[4] is not None]
            track_ref_preimage = [batch_run_id or "", batch_clock_id or "", cid, target_class, obs_ids, start_us, end_us]
            track_ref = "local:" + hashlib.sha256(json.dumps(
                track_ref_preimage, separators=(",", ":")
            ).encode()).hexdigest()[:16]
            tracks.append({
                "track_id": track_ref,
                "track_ref": track_ref,
                "camera_id": cid,
                "class_label": target_class,
                "start_frame": start_frame,
                "end_frame": end_frame,
                "range_us": [start_us, end_us],
                "frame_indices": frame_indices,
                "observation_ids": obs_ids,
                "ious": ious,
                "evidence_state": "OBSERVED",
                "identity_verdict": "UNCONFIRMED",
            })
            sightings.append({
                "camera_id": cid,
                "class_label": target_class,
                "range_us": [start_us, end_us],
                "evidence_state": "OBSERVED",
                "observation_ids": obs_ids,
                "track_ref": track_ref,
                "identity_verdict": "UNCONFIRMED",
            })

    sightings.sort(key=lambda s: (s["range_us"][0], s["camera_id"], s["track_ref"]))
    tracks.sort(key=lambda t: (t["range_us"][0], t["camera_id"], t["track_ref"]))

    multi_view = []
    for cid in sorted({s["camera_id"] for s in sightings}):
        cam_s = [s for s in sightings if s["camera_id"] == cid]
        multi_view.append({
            "camera_id": cid,
            "first_us": min(s["range_us"][0] for s in cam_s),
            "last_us": max(s["range_us"][1] for s in cam_s),
        })
    multi_view.sort(key=lambda mv: (mv["first_us"], mv["camera_id"]))

    effective_as_of = as_of_us
    if effective_as_of is None:
        effective_as_of = max_record_end_us if max_record_end_us > 0 else (
            max((s["range_us"][1] for s in sightings), default=0)
        )
    single_view = _single_view_from_sightings(sightings, effective_as_of)

    if not sightings:
        status = "NO_SIGHTING"
    elif single_view and single_view[-1]["kind"] == "LOST":
        status = "LOST"
    else:
        status = "TRACKING"

    return {
        "status": status,
        "reasons": [],
        "target_class": target_class,
        "tracks": tracks,
        "sightings": sightings,
        "multi_view": multi_view,
        "single_view": single_view,
        "identity_verdict": "UNCONFIRMED",
        "evidence_state": "OBSERVED" if sightings else "UNKNOWN",
    }
