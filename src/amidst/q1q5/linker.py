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
                 index_grid_origin_frame, color_label=None):
        self.parameters = parameters
        self.stride = _integer(stride_samples, "stride_samples", 1)
        self.origin = _integer(index_grid_origin_frame, "index_grid_origin_frame")
        self.color_label = color_label
        self.scope = tuple(seed_record[k] for k in ("run_id", "clock_id", "camera_id"))
        if self.scope[0] != parameters.run_id:
            raise LinkError("Seed outside parameter run scope")
        self._validate_record(seed_record)
        if seed_record["frame_state"] != "INFERRED" or not self._on_grid(seed_record["frame_index"]):
            raise LinkError("Seed is not an inferred grid observation")
        found = [o for o in seed_record["detections"] if o["observation_id"] == observation_id]
        if len(found) != 1 or found[0]["class_label"] != "person" or not self._eligible(found[0]):
            raise LinkError("Invalid seed")
        self.last = deepcopy(found[0])
        self.history = [(seed_record["timestamp_us"], deepcopy(found[0]))]
        self.last_time = seed_record["timestamp_us"]
        self.last_frame = seed_record["frame_index"]
        self.grid_frame, self.grid_time = self.last_frame, self.last_time
        self.seen_frame = self.last_frame
        self.first_missing_us = None
        self.state = "PLAYING"
        self.segment_id = "local:" + hashlib.sha256(json.dumps(
            [*self.scope, observation_id, parameters.content_sha256], separators=(",", ":")
        ).encode()).hexdigest()[:16]

    def _on_grid(self, frame):
        return frame >= self.origin and (frame - self.origin) % self.stride == 0

    def _validate_record(self, record):
        if tuple(record.get(k) for k in ("run_id", "clock_id", "camera_id")) != self.scope:
            raise LinkError("Cross run/clock/camera input")
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
        if observation["class_label"] != "person" or observation["score"] < self.parameters.min_score:
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
                "iou": chosen[0] if chosen else None, "elapsed_us": elapsed,
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
