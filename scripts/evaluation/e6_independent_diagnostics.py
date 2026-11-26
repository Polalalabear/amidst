#!/usr/bin/env python3
"""Independent #717 scoring caller; no Claude analysis scripts, inference or network imports."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCORER_SHA = "acacce396f27e0d7c8bf03d527b22272f2622376ed4a43ae6db0842353f87d08"
CORPORA = ("e3-652-20261122", "e3-reappearances-20261122")
CORPUS_PINS = (
    "853390e3dbecc8209c16c47d6e6a6cd5fc73d57bef2d1c4e11c757f8fa8b812e",
    "5eac93379533485e754f29ebf54f409e7992bd551db822ab6aeea2022aa78517",
)
WRONG = {"WRONG_PERSON", "WRONG_CAMERA"}
SHARED_OPENING = {"E3-A2", "E3-C2", "E3-D2", "E3-C3", "E3-C4", "E3-C5", "E3-C6"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scorer():
    path = ROOT / "src/amidst/evaluation/e3_scoring.py"
    if sha(path) != SCORER_SHA:
        raise ValueError("SCORER_CHANGED")
    spec = importlib.util.spec_from_file_location("e6_frozen_scorer", path)
    sc = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = sc
    spec.loader.exec_module(sc)
    return sc


class Reader:
    def __init__(self, root):
        self.root, self.sources = root.resolve(), {}

    def read(self, path, expected=None):
        path = path.resolve()
        digest = sha(path)
        if expected is not None and digest != expected:
            raise ValueError(f"SHA_MISMATCH {path.name}")
        self.sources[str(path.relative_to(self.root))] = {
            "sha256": digest,
            "bytes": path.stat().st_size,
        }
        return json.loads(path.read_text())


def spans(values, predicate):
    """Half-open tick intervals; includes leading and trailing intervals."""
    out, start = [], None
    for i, value in enumerate([*values, None]):
        hit = i < len(values) and predicate(value)
        if hit and start is None:
            start = i
        if not hit and start is not None:
            out.append((start, i))
            start = None
    return out


def classes(sc, gt, rows):
    ticks = sc.ticks_from_live(gt, rows, "T", tick_us=200_000, size=(320, 180))
    if len(ticks) != len(rows) or [t.t_us // 200_000 for t in ticks] != list(range(len(rows))):
        raise ValueError("GT_ALIGNMENT")
    return ticks, [sc.classify(t) for t in ticks]


def totals(counts):
    visible = sum(
        counts[c] for c in ("CORRECT", "MISLOCALIZED", "WRONG_PERSON", "WRONG_CAMERA", "LOST")
    )
    return {
        "wrong_person_s": 0.2 * sum(counts[c] for c in WRONG),
        "false_lock_s": 0.2 * counts["FALSE_LOCK"],
        "lost_s": 0.2 * counts["LOST"],
        "correct_s": 0.2 * counts["CORRECT"],
        "visible_s": 0.2 * visible,
        "follow_rate": counts["CORRECT"] / visible if visible else None,
        "counts": dict(counts),
    }


def target(row):
    return next(a for a in row["actors"] if a["id"] == "T")


def actor_hits(sc, gt_row, camera, box):
    if box is None or camera is None:
        return []
    return [
        a["id"]
        for a in gt_row["actors"]
        if a["present"]
        and sc.judge_box(box, a.get("gt_boxes", {}).get(camera), (320, 180))["primary"]
    ]


def plan_segments(plan):
    out = []
    for item in plan["inputs"]:
        if not out or out[-1]["keys"] != item["keys"] or out[-1]["dt"] != item["dt"]:
            out.append(
                {"first_step": item["step"], "count": 0, "dt": item["dt"], "keys": item["keys"]}
            )
        out[-1]["count"] += 1
    return out


def call_box(call):
    if call["answer"] == "OWN_BOX":
        return call.get("box_xyxy")
    if call["answer"] == "SELECT":
        return next(
            (
                c["box"]
                for c in call.get("request", {}).get("candidate_list", [])
                if c["camera_id"] == call["camera_id"] and c["detection_id"] == call["detection_id"]
            ),
            None,
        )
    return None


def describe_calls(sc, gt, run, cs):
    out = []
    for i, c in enumerate(run.get("calls", [])):
        ask = c.get("ask_tick", c.get("tick"))
        apply = c.get("applied_tick")
        stop = (
            run["calls"][i + 1].get("applied_tick") if i + 1 < len(run["calls"]) else None
        ) or len(cs)
        cam, box = c.get("camera_id"), call_box(c)
        hits = actor_hits(sc, gt[ask], cam, box)
        if c["answer"] in ("SELECT", "OWN_BOX"):
            answer_correct = ("T" in hits) if box is not None else None
        elif c["answer"] == "NOT_VISIBLE":
            answer_correct = not (target(gt[ask])["present"] and target(gt[ask])["gt_visible"])
        else:
            answer_correct = None  # uncertainty/occlusion has no instantaneous box criterion
        after = Counter(cs[apply:stop]) if apply is not None else Counter()
        out.append(
            {
                "ask_tick": ask,
                "answer": c["answer"],
                "camera_id": cam,
                "selected_box": box,
                "candidate_list_available": "candidate_list" in c.get("request", {}),
                "candidate_list": c.get("request", {}).get("candidate_list"),
                "ask_state": run["rows"][ask]["tracking"],
                "applied_state": run["rows"][apply]["tracking"] if apply is not None else None,
                "tracker_status_counts": dict(
                    Counter(r.get("neutral_status", "MISSING") for r in run["rows"][apply:stop])
                )
                if apply is not None
                else {},
                "answer_actor_hits": hits,
                "answer_correct": answer_correct,
                "accepted": c.get("source") == "AGENT" and c.get("fallback_reason") is None,
                "applied": c.get("applied"),
                "applied_tick": apply,
                "pending_at_end": c.get("pending_at_end"),
                "fallback_reason": c.get("fallback_reason"),
                "after_until_tick": stop,
                "after": totals(after),
                "first_application_class": cs[apply] if apply is not None else None,
            }
        )
    return out


def analyze(evidence, rn=None):
    sc, rd = scorer(), Reader(evidence)
    result = {
        "schema": "e6-independent.v1",
        "scorer_sha256": SCORER_SHA,
        "identity": "UNCONFIRMED",
        "paid_calls": 0,
        "cases": {},
        "sources": rd.sources,
    }
    arm_counts, trim_counts = defaultdict(Counter), defaultdict(Counter)
    return_rates, delays, continuity = defaultdict(list), defaultdict(list), defaultdict(list)
    answer_counts, attribution, self_extension = Counter(), defaultdict(Counter), Counter()
    run_pins = {}
    for base in ("f4-658-20261122", "e5-20261123"):
        path = evidence / base / "MANIFEST.sha256"
        rd.sources[f"{base}/MANIFEST.sha256"] = {"sha256": sha(path), "bytes": path.stat().st_size}
        run_pins[base] = {
            line[66:].removeprefix("./"): line[:64] for line in path.read_text().splitlines()
        }
    for batch, corpus in enumerate(CORPORA):
        root = evidence / corpus
        catalog = rd.read(root / "CORPUS.json")
        manifest = rd.read(root / "MANIFEST.json", CORPUS_PINS[batch])
        pins = {f["path"]: f["sha256"] for f in manifest["files"]}
        if sha(root / "CORPUS.json") != pins["CORPUS.json"]:
            raise ValueError("CATALOG_PIN")
        for case in catalog["cases"]:
            cid = case["case_id"]
            gt_doc = rd.read(root / case["gt_path"], case["gt_sha256"])
            gt_raw = gt_doc["ticks"]
            n_ticks = round(case["duration_s"] * 5)
            gt = gt_raw[:n_ticks]
            if [t["tick"] for t in gt] != list(range(len(gt))):
                raise ValueError("GT_TICKS")
            plan = rd.read(root / case["case_path"], case["case_sha256"])
            input_rel = f"{cid}.input.case.json"
            intent = rd.read(root / input_rel, pins[input_rel])
            vis = [bool(target(t)["present"] and target(t)["gt_visible"]) for t in gt]
            gaps = spans(vis, lambda v: not v)
            # Define the shared opening by source target positions, not by any arm's errors.
            opening_end = next((a for a, b in gaps if b - a >= 5), len(gt))
            detail = {
                "n_ticks": len(gt),
                "duration_s": 0.2 * len(gt),
                "planned": {
                    "case_path": case["case_path"],
                    "case_sha256": case["case_sha256"],
                    "script_id": plan.get("script_id"),
                    "actions": plan["actions"],
                    "input_path": input_rel,
                    "input_sha256": pins[input_rel],
                    "operator_segments": plan_segments(intent),
                    "expected_tick_count": len(plan["expected"]),
                },
                "catalog_points": case["decision_points"],
                "recorded_gt": {
                    "gt_path": case["gt_path"],
                    "gt_sha256": case["gt_sha256"],
                    "blind_intervals": [
                        {
                            "start_tick": a,
                            "end_tick_exclusive": b,
                            "start_s": a / 5,
                            "end_s": b / 5,
                            "catalog_gap_match": [
                                p.get("point_id", p["type"])
                                for p in case["decision_points"]
                                if p.get("gap_start_tick") == a
                            ],
                            "source_matches": {
                                "metrics.gaps": [
                                    p
                                    for p in case.get("metrics", {}).get("gaps", [])
                                    if p["start_tick"] == a
                                ],
                                "diagnostic_events": [
                                    p for p in case.get("diagnostic_events", []) if p["tick"] == a
                                ],
                                "excluded_duplicate_returns": [
                                    p
                                    for p in case.get("excluded_duplicate_returns", [])
                                    if p["gap_start_tick"] == a
                                ],
                            },
                        }
                        for a, b in gaps
                    ],
                    "visible_camera_intervals": [],
                },
                "raw_gt_ticks": len(gt_raw),
                "unscored_gt_tail_ticks": len(gt_raw) - len(gt),
                "opening_end_tick": opening_end,
                "arms": {},
            }
            sets = [tuple(target(t)["gt_visible"]) if target(t)["present"] else () for t in gt]
            for a, b in spans(list(range(len(gt))), lambda _: True):
                start = a
                for i in range(a + 1, b + 1):
                    if i == b or sets[i] != sets[start]:
                        detail["recorded_gt"]["visible_camera_intervals"].append(
                            {"start_tick": start, "end_tick_exclusive": i, "cameras": sets[start]}
                        )
                        start = i
            runs = []
            for arm in ("B1", "A2", "AO"):
                for k in (1,) if arm == "B1" else (1, 2, 3):
                    base = "e5-20261123" if arm == "AO" else "f4-658-20261122"
                    folder = (
                        ("runs-9" if batch == 0 else "runs-665")
                        if arm == "AO"
                        else ("runs-final-9" if batch == 0 else "runs-final-665")
                    )
                    rel = f"{folder}/{cid}/{arm}.k{k}.json"
                    pin_rel = rel if arm != "AO" else f"{cid}/{arm}.k{k}.json"
                    runs.append((arm, k, rd.read(evidence / base / rel, run_pins[base][pin_rel])))
            if rn:
                for arm in ("RN_U", "RN_N"):
                    path = rn / cid / f"{arm}.json"
                    runs.append((arm, 1, json.loads(path.read_text())))
                    result.setdefault("rn_sources", {})[str(path.relative_to(rn))] = sha(path)
            for arm, k, run in runs:
                if (run["case_id"], run["arm"], run["tick_us"], run["size"]) != (
                    cid,
                    arm,
                    200_000,
                    [320, 180],
                ):
                    raise ValueError("RUN_BINDING")
                ticks, cs = classes(sc, gt, run["rows"])
                counts = Counter(cs)
                n = 3 if arm in ("AO", "A2") else 1
                arm_counts[arm].update({c: v / n for c, v in counts.items()})
                # Only seven reappearance extension clips share the prescribed common opening.
                trim = 110 if cid in SHARED_OPENING else 0
                trim_counts[arm].update({c: v / n for c, v in Counter(cs[trim:]).items()})
                returns, blind_events = [], []
                for lo, hi in gaps:
                    if hi - lo < 5:
                        continue
                    blind_events.append(
                        {
                            "start_tick": lo,
                            "end_tick_exclusive": hi,
                            "false_lock_s": cs[lo:hi].count("FALSE_LOCK") / 5,
                            "pre_return_wrong": cs[lo - 1] in WRONG if lo else None,
                        }
                    )
                    if hi == len(cs):
                        continue
                    end = next((i for i in range(hi, len(cs)) if not vis[i]), len(cs))
                    hit = next((i for i in range(hi, end) if cs[i] == "CORRECT"), None)
                    sustained = (
                        next((i for i in range(hit, end) if cs[i] != "CORRECT"), end)
                        if hit is not None
                        else None
                    )
                    r = {
                        "blind_start_tick": lo,
                        "return_tick": hi,
                        "visible_until_tick": end,
                        "first_correct_tick": hit,
                        "eventually": hit is not None,
                        "within_3s": hit is not None and hit - hi <= 15,
                        "delay_s": (hit - hi) / 5 if hit is not None else None,
                        "correct_continuation_s": (sustained - hit) / 5
                        if hit is not None
                        else None,
                        "blind_false_lock_s": cs[lo:hi].count("FALSE_LOCK") / 5,
                        "pre_return_wrong": cs[lo - 1] in WRONG if lo else None,
                        "pre_reacquire_wrong_s": sum(
                            c in WRONG for c in cs[hi : hit if hit is not None else end]
                        )
                        / 5,
                        "pre_reacquire_lost_s": cs[hi : hit if hit is not None else end].count(
                            "LOST"
                        )
                        / 5,
                        "post_reacquire_wrong_s": sum(c in WRONG for c in cs[hit:end]) / 5
                        if hit is not None
                        else 0,
                        "sustained_2s": hit is not None
                        and end - hit >= 10
                        and all(c == "CORRECT" for c in cs[hit : hit + 10]),
                        "post_return_wrong_s": sum(c in WRONG for c in cs[hi:end]) / 5,
                    }
                    returns.append(r)
                    return_rates[arm].append((r["eventually"], r["within_3s"], 1 / n))
                    if hit is not None:
                        delays[arm].append((r["delay_s"], 1 / n))
                        continuity[arm].append((r["correct_continuation_s"], 1 / n))
                calls = describe_calls(sc, gt, run, cs) if arm == "AO" else []
                for c in calls:
                    answer_counts["total"] += 1
                    answer_counts[c["answer"]] += 1
                    if c["answer_correct"] is not None:
                        answer_counts["scoreable"] += 1
                        answer_counts["correct"] += c["answer_correct"]
                    answer_counts["accepted"] += c["accepted"]
                    answer_counts["applied"] += bool(c["applied"])
                    if c["applied_tick"] is not None:
                        category = (
                            "ASK_ABSENT"
                            if not target(gt[c["ask_tick"]])["gt_visible"]
                            else "ASK_CORRECT"
                            if c["answer_correct"] is True
                            else "ASK_WRONG"
                            if c["answer_correct"] is False
                            else "ASK_UNSCOREABLE"
                        )
                        after = c["after"]["counts"]
                        attribution[category].update(
                            {key: value / n / 5 for key, value in after.items()}
                        )
                    before = run["rows"][c["ask_tick"]]["tracking"]
                    old = actor_hits(
                        sc, gt[c["ask_tick"]], before.get("active_cam"), before.get("box")
                    )
                    wrong_old = sorted(set(old) - {"T"}) if "T" not in old else []
                    visible = bool(target(gt[c["ask_tick"]])["gt_visible"])
                    if wrong_old:
                        prefix = "visible" if visible else "blind"
                        self_extension[prefix + "_previous_wrong"] += 1
                        if set(wrong_old) & set(c["answer_actor_hits"]):
                            self_extension[prefix + "_same_wrong_actor"] += 1
                        elif "T" in c["answer_actor_hits"]:
                            self_extension[prefix + "_switch_target"] += 1
                        else:
                            self_extension[prefix + "_other_or_unknown"] += 1
                    if cs[c["ask_tick"]] in WRONG | {"FALSE_LOCK"} and c["answer"] in (
                        "SELECT",
                        "OWN_BOX",
                    ):
                        # Reproduce the earlier label diagnostic, including its pooled OTHER label.
                        old_label = old[0] if old else "OTHER"
                        new_label = c["answer_actor_hits"][0] if c["answer_actor_hits"] else "OTHER"
                        prefix = "label_visible" if visible else "label_blind"
                        self_extension[prefix + "_n"] += 1
                        self_extension[prefix + "_same"] += old_label == new_label
                        self_extension[prefix + "_same_OTHER"] += old_label == new_label == "OTHER"
                detail["arms"].setdefault(arm, []).append(
                    {
                        "k": k,
                        "totals": totals(counts),
                        "trimmed_totals": totals(Counter(cs[trim:])),
                        "returns": returns,
                        "blind_events": blind_events,
                        "opening_wrong_s": sum(c in WRONG for c in cs[:opening_end]) / 5,
                        "wrong_intervals": spans(cs, lambda c: c in WRONG),
                        "calls": calls,
                        "positional_only_ticks": sum(
                            t.shown_camera is not None and not t.boxes for t in ticks
                        ),
                    }
                )
            result["cases"][cid] = detail
    result["totals"] = {a: totals(c) for a, c in arm_counts.items()}
    result["opening_sensitivity"] = {a: totals(c) for a, c in trim_counts.items()}
    result["return_summary"] = {
        a: {
            "eventual_rate": sum(v * w for v, _, w in vals) / sum(w for _, _, w in vals),
            "within_3s_rate": sum(v * w for _, v, w in vals) / sum(w for _, _, w in vals),
            "events_weighted": sum(w for _, _, w in vals),
            "completed_delay_mean_s": sum(v * w for v, w in delays[a])
            / sum(w for _, w in delays[a]),
            "completed_delay_median_s": statistics.median(v for v, _ in delays[a]),
            "continuation_mean_s": sum(v * w for v, w in continuity[a])
            / sum(w for _, w in continuity[a]),
        }
        for a, vals in return_rates.items()
    }
    result["ao_answer_summary"] = dict(answer_counts)
    result["ao_attribution_seconds_k_mean"] = {k: dict(v) for k, v in attribution.items()}
    result["ao_self_extension_box_primary"] = dict(self_extension)
    result["shared_opening_sensitivity"] = {
        "cases": sorted(SHARED_OPENING),
        "cut_s": 22,
        "definition": "posthoc reproduction of seven shared B4 openings; "
        "not target stationary prefix",
    }
    clusters = {
        cid: {
            arm: statistics.mean(r["trimmed_totals"]["wrong_person_s"] for r in runs)
            for arm, runs in case["arms"].items()
        }
        for cid, case in result["cases"].items()
    }
    result["opening_sensitivity_intervals"] = {
        arm: {
            "diff_s": sum(v[arm] - v["B1"] for v in clusters.values()),
            "ci95_s": sc.cluster_bootstrap(
                clusters, lambda values, arm=arm: sum(v[arm] - v["B1"] for v in values), 2000, 660
            ),
            "seed": 660,
            "n": 2000,
            "unit": "clip (posthoc; families not independent)",
        }
        for arm in ("A2", "AO")
    }
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--rn", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError("OUTPUT_EXISTS")
    result = analyze(a.evidence, a.rn)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("totals", "opening_sensitivity", "return_summary", "ao_answer_summary")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
