"""PROPOSED evaluation-only case2 projection scorer; no production decoder.

The caller supplies two independently authored, frozen JSON byte strings and
trusted byte hashes. This module performs no filesystem, runtime or media IO.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics


VERSION = "case2-tracking-proposed-v1"
FORMAT = "case2-evaluation-projection.v1"
UNKNOWN = "UNKNOWN"
METRICS = ("switch_consistency", "switch_latency_ms", "lost_onset_error_ms", "landing_error_m")
ACTIONS = {"SWITCH", "KEEP", "LOST", "ABSTAIN"}
BINDINGS = ("source_id", "run_id", "clock_id", "sample_set_sha256")
ROOT_KEYS = {"format", "role", "data_origin", "evaluation_eligible", "authoring_ref",
             "samples", *BINDINGS}
SAMPLE_KEYS = {"sample_id", "status", "action", "camera_id", "decision_time_us",
               "entry_time_us", "decision_window_us", "entry_window_us", "lost_onset_us",
               "landing"}


class EvaluationError(ValueError):
    """Invalid or unpinned evaluation projection, not a model failure."""


def _require(condition, message):
    if not condition:
        raise EvaluationError(message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _pin(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value not in {UNKNOWN, "MISSING"}


def _time(value):
    return type(value) is int and value >= 0


def _window(value):
    return (isinstance(value, list) and len(value) == 2 and all(_time(x) for x in value)
            and value[0] < value[1])


def _load(raw, expected_pin, role):
    _require(isinstance(raw, bytes) and len(raw) <= 1_048_576, "Projection bytes/size invalid")
    _require(_pin(expected_pin) and _sha(raw) == expected_pin, "Projection byte pin mismatch")

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    def constant(_value):
        raise EvaluationError("Nonfinite JSON number")

    try:
        doc = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError) as exc:
        raise EvaluationError("Invalid projection JSON") from exc
    _require(isinstance(doc, dict) and not set(doc) - ROOT_KEYS, "Closed projection fields required")
    _require(doc.get("format") == FORMAT and doc.get("role") == role, "Explicit projection role required")
    _require(doc.get("evaluation_eligible") is False, "Projection cannot grant evaluation eligibility")
    origins = {"SYNTHETIC"} if role == "prediction" else {"SYNTHETIC", "INDEPENDENT_HUMAN"}
    _require(doc.get("data_origin") in origins, "Unsupported projection origin; production adapter NOT_RUN")
    _require(_text(doc.get("authoring_ref")), "Independent authoring reference required")
    _require(all(_text(doc.get(key)) for key in BINDINGS) and _pin(doc["sample_set_sha256"]),
             "Explicit source/run/clock/sample-set pins required")
    samples = doc.get("samples")
    _require(isinstance(samples, list), "Explicit sample list required")
    by_id = {}
    for row in samples:
        _require(isinstance(row, dict) and not set(row) - SAMPLE_KEYS, "Closed sample fields required")
        sid = row.get("sample_id")
        _require(_text(sid) and sid not in by_id, "Unique sample IDs required")
        _require(isinstance(row.get("status"), str) and row["status"] in {"OBSERVED", "MISSING", UNKNOWN},
                 "Explicit sample status required")
        by_id[sid] = row
    return doc, by_id


def _unknown(reason):
    return {"value": UNKNOWN, "reason": reason}


def _value(value):
    return {"value": value, "reason": None}


def _switch(prediction, reference):
    pa, ra = prediction.get("action"), reference.get("action")
    if not isinstance(pa, str) or not isinstance(ra, str) or pa not in ACTIONS or ra not in ACTIONS:
        return _unknown("ACTION_MISSING"), _unknown("UNMATCHED")
    window = reference.get("decision_window_us")
    decision = prediction.get("decision_time_us")
    if not _window(window) or not _time(decision):
        return _unknown("TIME_ALIGNMENT_MISSING"), _unknown("TIME_ALIGNMENT_MISSING")
    same = pa == ra and window[0] <= decision < window[1]
    if ra == "SWITCH" and pa == "SWITCH":
        pc, rc = prediction.get("camera_id"), reference.get("camera_id")
        entry, entry_window = prediction.get("entry_time_us"), reference.get("entry_window_us")
        if not _text(pc) or not _text(rc):
            return _unknown("CAMERA_MISSING"), _unknown("UNMATCHED")
        if not _time(entry) or not _window(entry_window):
            return _unknown("ENTRY_ALIGNMENT_MISSING"), _unknown("UNMATCHED")
        same = same and pc == rc and decision <= entry and entry_window[0] <= entry < entry_window[1]
    consistency = _value(bool(same))
    # #397 section 1.7 defines latency for matched switch events only.
    latency = _value((decision - window[0]) / 1000) if same and ra == "SWITCH" else _unknown("UNMATCHED_OR_NOT_SWITCH")
    return consistency, latency


def _landing(prediction, reference):
    pp, rp = prediction.get("landing"), reference.get("landing")
    if not isinstance(pp, dict) or not isinstance(rp, dict):
        return _unknown("LANDING_REFERENCE_OR_PREDICTION_MISSING")
    keys = {"frame_id", "unit", "coordinate_authority_ref", "position", "source_time_us"}
    _require(not set(pp) - keys and not set(rp) - keys, "Closed landing fields required")
    if (not _text(rp.get("frame_id")) or pp.get("frame_id") != rp.get("frame_id")
            or pp.get("unit") != "m" or rp.get("unit") != "m"
            or not _text(rp.get("coordinate_authority_ref"))
            or pp.get("coordinate_authority_ref") != rp.get("coordinate_authority_ref")):
        return _unknown("COORDINATE_AUTHORITY_OR_UNIT_MISMATCH")
    if not _time(rp.get("source_time_us")) or pp.get("source_time_us") != rp["source_time_us"]:
        return _unknown("LANDING_TIME_MISMATCH")
    a, b = pp.get("position"), rp.get("position")
    if not (isinstance(a, list) and isinstance(b, list) and len(a) == len(b) == 2
            and all(type(x) in {int, float} and math.isfinite(x) for x in a + b)):
        return _unknown("FINITE_2D_POSITION_MISSING")
    distance = math.dist(a, b)
    return _value(distance) if math.isfinite(distance) else _unknown("NONFINITE_DISTANCE")


def score(prediction_raw, reference_raw, *, expected_prediction_sha256, expected_reference_sha256):
    """Score explicit projections; expected hashes must come from a trusted caller.

    An independence declaration is recorded, never authenticated by this scorer.
    No production CX-8 schema, approved Eq.14 or formal eligibility is implied.
    """
    prediction, preds = _load(prediction_raw, expected_prediction_sha256, "prediction")
    reference, refs = _load(reference_raw, expected_reference_sha256, "reference")
    _require(expected_prediction_sha256 != expected_reference_sha256
             and prediction["authoring_ref"] != reference["authoring_ref"],
             "Prediction and reference must have separate authoring sources")
    mismatches = [key for key in BINDINGS if prediction[key] != reference[key]]
    rows = []
    for sid in sorted(preds.keys() | refs.keys()):
        p, r = preds.get(sid), refs.get(sid)
        reason = ("BINDING_MISMATCH:" + ",".join(mismatches) if mismatches else
                  "REFERENCE_MISSING" if r is None else "PREDICTION_MISSING" if p is None else
                  "REFERENCE_" + r["status"] if r["status"] != "OBSERVED" else
                  "PREDICTION_" + p["status"] if p["status"] != "OBSERVED" else None)
        values = {name: _unknown(reason) for name in METRICS} if reason else {}
        if not reason:
            values["switch_consistency"], values["switch_latency_ms"] = _switch(p, r)
            pt, rt = p.get("lost_onset_us"), r.get("lost_onset_us")
            values["lost_onset_error_ms"] = (_value(abs(pt - rt) / 1000)
                                                if _time(pt) and _time(rt) else _unknown("LOST_ONSET_MISSING"))
            values["landing_error_m"] = _landing(p, r)
        rows.append({"sample_id": sid, **values})
    summary = {}
    for name in METRICS:
        values = [row[name]["value"] for row in rows if row[name]["value"] != UNKNOWN]
        item = {"n_valid": len(values), "n_unknown": len(rows) - len(values)}
        if name == "switch_consistency":
            item.update(n_agreed=sum(values), n_disagreed=len(values) - sum(values),
                        rate_pct=100 * sum(values) / len(values) if values else UNKNOWN)
        else:
            item["median"] = statistics.median(values) if values else UNKNOWN
        summary[name] = item
    return {"scorer_version": VERSION, "definition_status": "PROPOSED", "eq14_status": "UNRESOLVED",
            "real_data_status": "NOT_RUN", "evaluation_eligible": False,
            "production_adapter": "NOT_RUN", "independence_verified": False,
            "prediction_sha256": expected_prediction_sha256, "reference_sha256": expected_reference_sha256,
            "prediction_origin": prediction["data_origin"], "reference_origin": reference["data_origin"],
            "binding": {key: prediction[key] for key in BINDINGS},
            "reference_binding": {key: reference[key] for key in BINDINGS},
            "binding_mismatches": mismatches, "summary": summary, "samples": rows}
