"""#720: freeze an observation-only answer key before running 20 rule Q3/Q1/Q2 checks.

No HTTP server, image, 3D asset, GT, model transport or launcher-guard override.
The Demo application is constructed with scratch state and agent_queue=None.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def app_and_run(evidence, owned, state):
    from serve_demo_integration import Demo

    app = Demo(
        owned / "data/artifacts",
        owned / "data/p1-v4",
        state,
        job_path=owned / "metadata/cross-camera-job.json",
        job_pin="651906f9ca18a02d8efd300eb9cef57877ad8da758d9a323b590f82feb86d49e",
        owned_root=owned,
        eightcam_required=False,
        agent_queue=None,
    )
    run = next(r for r in app.api.runs.values() if r.title.startswith("A4-1 ·"))
    return app, run


def questions():
    rows = [
        ("找人", "PARSED", "person", None, None, "Q1"),
        ("查詢紅衣人", "PARSED", "person", "red", None, "Q1"),
        ("查詢藍衣人", "PARSED", "person", "blue", None, "Q1"),
        ("找人CAM_W2", "PARSED", "person", None, ["CAM_W2"], "Q1"),
        ("找紅衣人CAM_W2", "PARSED", "person", "red", ["CAM_W2"], "Q1"),
        ("找人CAM_EXT_CAR", "PARSED", "person", None, ["CAM_EXT_CAR"], "Q1"),
        ("找車", "PARSED", "car", None, None, "Q1"),
        ("找車CAM_W2", "PARSED", "car", None, ["CAM_W2"], "Q1"),
        ("追蹤人", "PARSED", "person", None, None, "Q2"),
        ("跟著紅衣人", "PARSED", "person", "red", None, "Q2"),
        ("跟著藍衣人", "PARSED", "person", "blue", None, "Q2"),
        ("找自行車", "PARSED", "bicycle", None, None, "Q1"),
        ("找他", "NEEDS_CLARIFICATION", None, None, None, None),
        ("找紅或藍衣人", "NEEDS_CLARIFICATION", None, None, None, None),
        ("不要紅衣人", "NEEDS_CLARIFICATION", None, None, None, None),
        ("沒有人的鏡頭", "NEEDS_CLARIFICATION", None, None, None, None),
        ("戴眼鏡的人", "UNSUPPORTED_CONDITION", None, None, None, None),
        ("追蹤車", "UNSUPPORTED_CONDITION", None, None, None, None),
        ("追蹤人CAM_W2", "UNSUPPORTED_CONDITION", None, None, None, None),
        ("人13:00:10到13:00:00", "TIME_EXPRESSION_INVALID", None, None, None, None),
    ]
    return [
        {
            "id": i,
            "text": row[0],
            "expected_status": row[1],
            "class_label": row[2],
            "color": row[3],
            "camera_ids": row[4],
            "intent": row[5],
        }
        for i, row in enumerate(rows, 1)
    ]


def oracle(run, question):
    """Read frozen observations only, independent of parser/search/controller execution."""
    b = run.bindings
    score = run.parse_settings.query_min_score
    gap = next(
        p["value"] for p in b.parameter_set["parameters"] if p["name"] == "segment_merge_gap_us"
    )
    if gap is None:
        raise ValueError("ORACLE_GAP_UNKNOWN")
    steps = {
        m["camera_id"]: m["index_interval_us"] * m["stride_samples"]
        for m in b.index.manifest["sampling"]["per_camera"]
    }
    hits, observation_keys = {}, []
    for row in b.index.records:
        cam, t = row["camera_id"], row["timestamp_us"]
        if question["camera_ids"] and cam not in question["camera_ids"]:
            continue
        if row["frame_state"] != "INFERRED" or not 0 <= t < b.clock.duration_us:
            continue
        found = [
            d
            for d in row["detections"]
            if d["class_label"] == question["class_label"]
            and d["score"] >= score
            and (
                question["color"] is None
                or d.get("color", {}).get("verdicts", {}).get(question["color"]) == "STRONG"
            )
        ]
        if found:
            hits.setdefault(cam, []).append(t)
            observation_keys.extend((cam, t, d["observation_id"]) for d in found)
    segments = {}
    for cam, times in hits.items():
        merged = []
        for t in sorted(times):
            end = min(t + steps[cam], b.clock.duration_us)
            if merged and t - merged[-1][1] <= gap:
                merged[-1][1] = end
            else:
                merged.append([t, end])
        segments[cam] = merged
    return {
        "camera_time_segments_us": segments,
        "candidate_count": len(observation_keys),
        "candidate_keys_sha256": hashlib.sha256(
            json.dumps(sorted(observation_keys)).encode()
        ).hexdigest(),
        "query_min_score": score,
        "min_verdict": "STRONG",
        "segment_merge_gap_us": gap,
    }


def tokens(segments, step=200_000):
    return {
        (cam, t)
        for cam, ranges in segments.items()
        for lo, hi in ranges
        for t in range(lo, hi, step)
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["freeze", "run"])
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--owned", type=Path, required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--key", type=Path, required=True)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    app, run = app_and_run(a.evidence.resolve(), a.owned.resolve(), a.state.resolve())
    if a.mode == "freeze":
        if a.key.exists():
            raise ValueError("KEY_EXISTS")
        qs = questions()
        for q in qs:
            if q["expected_status"] == "PARSED":
                q["expected_retrieval"] = oracle(run, q)
        a.key.parent.mkdir(parents=True, exist_ok=True)
        a.key.write_text(
            json.dumps(
                {
                    "scope": "20-rule-functional-questions; "
                    "Q3 API then Q1 search or Q2 seed retrieval",
                    "scene_id": run.catalog["scene_id"],
                    "run_id": run.catalog["run_id"],
                    "index_sha256": run.bindings.index_sha256,
                    "clock_sha256": run.bindings.clock_sha256,
                    "parameter_sha256": run.bindings.parameter_sha256,
                    "gt_read": False,
                    "questions": qs,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )
        print("FROZEN: no parser, Q1 search or Q2 controller executed", sha(a.key))
        return
    if a.out is None or a.out.exists():
        raise ValueError("NEW_OUTPUT_REQUIRED")
    key = json.loads(a.key.read_text())
    if (key["run_id"], key["index_sha256"], key["clock_sha256"], key["parameter_sha256"]) != (
        run.catalog["run_id"],
        run.bindings.index_sha256,
        run.bindings.clock_sha256,
        run.bindings.parameter_sha256,
    ):
        raise ValueError("SOURCE_DRIFT")
    token = app.call("session", {"role": "demo"})["session_ref"]
    out = {"expected_sha256": sha(a.key), "questions": [], "model_calls": 0, "gt_read": False}
    tp = fp = fn = 0
    for q in key["questions"]:
        req = {
            "schema_version": "q-demo.q3-parse-request.v1",
            "session_ref": token,
            "text": q["text"],
            "locale": "zh-TW",
            "context": {
                "scene_id": key["scene_id"],
                "run_ids": [key["run_id"]],
                "clock_mapping_sha256": key["clock_sha256"],
            },
            "parser_mode": "RULE_ONLY",
        }
        parsed = app.call("q3_parse", req)
        r = {
            "id": q["id"],
            "text": q["text"],
            "parse": parsed,
            "parse_pass": parsed["status"] == q["expected_status"],
            "retrieval": None,
            "retrieval_pass": None,
        }
        if parsed["status"] == "PARSED" and q["intent"]:
            query = parsed["structured_query"]
            condition = query["condition"] if q["intent"] == "Q1" else query["seed"]
            color = condition["color"]["label"] if condition["color"] else None
            r["parse_pass"] &= (
                condition["class_label"] == q["class_label"]
                and color == q["color"]
                and query["schema_version"] == f"q-demo.{q['intent'].lower()}-request.v1"
                and query.get("camera_ids") == q["camera_ids"]
            )
            action = "q1_camera_search" if q["intent"] == "Q1" else "q2_seed_candidates"
            actual = app.call(
                action, {"request": query, "parse_response_ref": parsed["output_sha256"]}
            )
            r["retrieval"] = actual
            expected = q["expected_retrieval"]
            if q["intent"] == "Q1":
                segments = {
                    row["camera_id"]: [seg["range_us"] for seg in row["matched_segments"]]
                    for row in actual["results"]
                }
                want, got = tokens(expected["camera_time_segments_us"]), tokens(segments)
                tp += len(want & got)
                fp += len(got - want)
                fn += len(want - got)
                r["retrieval_pass"] = segments == expected["camera_time_segments_us"]
                r["camera_time_counts"] = {
                    "tp": len(want & got),
                    "fp": len(got - want),
                    "fn": len(want - got),
                }
            else:
                keys = sorted(
                    (c["camera_id"], c["timestamp_us"], c["observation_id"])
                    for c in actual["candidates"]
                )
                r["retrieval_pass"] = (
                    len(keys) == expected["candidate_count"]
                    and hashlib.sha256(json.dumps(keys).encode()).hexdigest()
                    == expected["candidate_keys_sha256"]
                )
        out["questions"].append(r)
    out["summary"] = {
        "parse_pass": sum(r["parse_pass"] for r in out["questions"]),
        "parse_n": 20,
        "retrieval_pass": sum(r["retrieval_pass"] is True for r in out["questions"]),
        "retrieval_n": sum(r["retrieval_pass"] is not None for r in out["questions"]),
        "camera_time_tp": tp,
        "camera_time_fp": fp,
        "camera_time_fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(out["summary"], indent=2))


if __name__ == "__main__":
    main()
