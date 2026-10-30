"""Opt-in, gate-only counterfactuals over the published #262 diagnosis.

No predictor, linker, controller, media reader or runtime configuration is called.
Passing a gate is not a recovered link, detector recall or confirmed identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

DIAGNOSIS_SHA256 = "495a6e6012c82b3edf45cd0846529449d394b1a653772b6b9b9d3de262884f4a"
DIAGNOSIS_COMMIT = "0f8be9f28e0400d7d1b060b2814677976a69d8a3"
BASELINE = {"link_min_score": 0.4, "link_iou_min": 0.3,
            "link_center_dist_max_diag_ratio": 0.5, "link_max_gap_us": 600_000}


@dataclass(frozen=True)
class Options:
    link_min_score: float | None = None
    link_iou_min: float | None = None
    audit_index_floor: float | None = None


DEFAULT_OPTIONS = Options()


def _number(value, low, high):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not low <= value <= high):
        raise ValueError("Invalid or out-of-scope counterfactual threshold")
    return value


def _geometry_passes(row, threshold, center_limit):
    # The historical linker tries last observation, then translation if empty.
    # For the question "any candidate passes a geometry gate", their union is
    # sufficient. This does not evaluate its ordering/ambiguity/time guards.
    return any(pair["iou"] >= threshold
               and pair["center_distance_diag_ratio"] <= center_limit
               for candidate in row["geometry"]
               for pair in (candidate["last"], candidate["reference"]))


def analyze(diagnosis, options=DEFAULT_OPTIONS):
    thresholds = diagnosis["thresholds"]
    if any(thresholds.get(k) != v for k, v in BASELINE.items()):
        raise ValueError("Historical threshold context changed")
    floor = diagnosis["index_score_floor"]
    score = (thresholds["link_min_score"] if options.link_min_score is None else
             _number(options.link_min_score, floor, thresholds["link_min_score"]))
    iou = (thresholds["link_iou_min"] if options.link_iou_min is None else
           _number(options.link_iou_min, 0, thresholds["link_iou_min"]))
    if options.audit_index_floor is not None:
        _number(options.audit_index_floor, 0, floor)
    score_frames, geometry_frames, multi_person, censored = [], [], [], []
    newly_score_eligible_observations = 0
    seen = set()
    for row in diagnosis["rows"]:
        ref = row["frame_ref"]
        if ref in seen:
            raise ValueError("Duplicate source frame")
        seen.add(ref)
        scores = row["person_scores"]
        for value in scores:
            _number(value, floor, 1)
        if not scores:
            expected = "NO_STORED_PERSON_AT_INDEX_FLOOR"
            censored.append(ref)
        elif max(scores) < thresholds["link_min_score"]:
            expected = "PERSON_BELOW_LINK_SCORE"
        else:
            expected = "LINK_GEOMETRY_REJECTION"
        if row["category"] != expected:
            raise ValueError("Source category and score evidence disagree")
        old_eligible = sum(s >= thresholds["link_min_score"] for s in scores)
        new_eligible = sum(s >= score for s in scores)
        if new_eligible > old_eligible:
            score_frames.append(ref)
            newly_score_eligible_observations += new_eligible - old_eligible
            if new_eligible > 1:
                multi_person.append(ref)
        if expected == "LINK_GEOMETRY_REJECTION":
            if not row["geometry"]:
                raise ValueError("Geometry evidence missing")
            for candidate in row["geometry"]:
                for pair in (candidate["last"], candidate["reference"]):
                    _number(pair["iou"], 0, 1)
                    _number(pair["center_distance_diag_ratio"], 0, math.inf)
            if _geometry_passes(row, thresholds["link_iou_min"],
                                thresholds["link_center_dist_max_diag_ratio"]):
                raise ValueError("Source baseline geometry rejection not reproduced")
            if _geometry_passes(row, iou, thresholds["link_center_dist_max_diag_ratio"]):
                geometry_frames.append(ref)
    return {
        "requested_options": asdict(options),
        "effective_gate_thresholds": {"link_min_score": score, "link_iou_min": iou,
                                      "link_center_dist_max_diag_ratio": 0.5},
        "source_category_counts": dict(sorted(Counter(r["category"] for r in diagnosis["rows"]).items())),
        "newly_score_eligible_frames": sorted(score_frames),
        "newly_score_eligible_frame_count": len(score_frames),
        "newly_score_eligible_observation_count": newly_score_eligible_observations,
        "multiple_score_eligible_person_frames": sorted(multi_person),
        "multiple_score_eligible_is_confirmed_ambiguity": False,
        "newly_passing_geometry_gate_frames": sorted(geometry_frames),
        "newly_passing_geometry_gate_frame_count": len(geometry_frames),
        "changed_gate_frame_count": len(set(score_frames) | set(geometry_frames)),
        "geometry_for_newly_score_eligible_frames": "MISSING_IN_PUBLISHED_DIAGNOSIS",
        "floor_censored_person_frame_count": len(censored),
        "floor_censored_person_frames": sorted(censored),
        "low_floor_recovered_person_frames": None,
        "low_floor_analysis_status": ("INCOMPLETE_RAW_BELOW_FLOOR_MISSING"
                                      if options.audit_index_floor is not None else "NOT_REQUESTED"),
        "recovered_links": None,
        "false_positive_or_recall_denominator": "MISSING",
        "identity_verdict": "UNCONFIRMED",
        "runtime_changed": False,
    }


def load_diagnosis(path):
    if not path.is_absolute() or path.is_symlink() or path.resolve() != path:
        raise ValueError("Canonical nonsymlink source path required")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DIAGNOSIS_SHA256:
        raise ValueError("Published #262 diagnosis pin mismatch")
    document = json.loads(raw)
    if (document.get("schema_version") != "q-demo.p1-reported-gap-diagnosis.v1"
            or document.get("reported_frames") != 28 or len(document["rows"]) != 28
            or document.get("source_recording_id") != "2777741d96ac9aff5bffb2f61a4d2938"):
        raise ValueError("Wrong source diagnosis")
    return document, raw


def build_report(diagnosis, options=DEFAULT_OPTIONS, *, sweep=False):
    scenarios = {"selected": analyze(diagnosis, options)}
    if sweep:
        scenarios["baseline"] = analyze(diagnosis)
        for score in (0.39, 0.38, 0.35, 0.30):
            scenarios[f"score_{score:.2f}"] = analyze(diagnosis, Options(link_min_score=score))
        for iou in (0.299, 0.25, 0.24, 0.225):
            scenarios[f"iou_{iou}"] = analyze(diagnosis, Options(link_iou_min=iou))
        scenarios["combined_0.30_0.225"] = analyze(diagnosis, Options(0.30, 0.225))
        scenarios["audit_floor_0.10"] = analyze(diagnosis, Options(audit_index_floor=0.10))
    return {
        "schema_version": "q-demo.l2-detection-offline-options.v1",
        "status": "PROPOSED_GATE_COUNTERFACTUAL_ONLY",
        "source_diagnosis_commit": DIAGNOSIS_COMMIT,
        "source_diagnosis_sha256": DIAGNOSIS_SHA256,
        "source_recording_id": diagnosis["source_recording_id"],
        "source_product_commit": diagnosis["source_commit"],
        "source_manifest_sha256": diagnosis["source_manifest_sha256"],
        "threshold_authority": {
            "index_score_floor_0.3": "RUN_LEVEL; repository template PROPOSED/null",
            "link_min_score_0.4": "RUN_LEVEL; repository template PROPOSED/null",
            "query_min_score_0.5": "RUN_LEVEL; repository template PROPOSED/null",
            "link_iou_min_0.3": "APPROVED value; overrides in this report PROPOSED",
            "link_center_dist_max_diag_ratio_0.5": "APPROVED; unchanged",
            "link_max_gap_us_600000": "APPROVED; unchanged",
        },
        "scope": {"frames": 28, "full_index_frames": diagnosis["index_frames"],
                  "detector_calls": 0, "render_calls": 0, "controller_calls": 0,
                  "gt_or_renderer_outputs_read": False, "rgb_read": False,
                  "runtime_defaults_changed": False, "formal_acceptance": "NOT_EVALUATED"},
        "scenarios": scenarios,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnosis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--link-min-score", type=float)
    parser.add_argument("--link-iou-min", type=float)
    parser.add_argument("--audit-index-floor", type=float)
    parser.add_argument("--sweep", action="store_true")
    args = parser.parse_args()
    diagnosis, before = load_diagnosis(args.diagnosis)
    report = build_report(diagnosis, Options(args.link_min_score, args.link_iou_min,
                                           args.audit_index_floor), sweep=args.sweep)
    if args.diagnosis.read_bytes() != before:
        raise ValueError("Input changed during analysis")
    if (not args.output.is_absolute() or args.output.resolve() != args.output
            or args.output.exists() or args.output.is_symlink()):
        raise ValueError("New canonical output file required")
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, sort_keys=True, ensure_ascii=True, allow_nan=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
