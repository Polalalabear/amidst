"""Replay frozen camera observations, then score relock on the separate evaluation record."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from dataclasses import asdict, replace
from pathlib import Path

from amidst.live_mode.relock import (
    RelockConfig,
    RelockPolicy,
    finite_features,
    group_observations,
)
from amidst.live_mode.scheduler import (
    DEFAULT_GRAPH,
    DEFAULT_GRAPH_SHA256,
    CameraScheduler,
    load_graph,
)
from amidst.live_mode.tracker import Projector, Tracker, load_cameras

REPO = Path(__file__).resolve().parents[2]
SCORER = REPO / "frontend/live-mode/measure/t1_analyze.mjs"
EVALUATION_SCENARIO = REPO / "docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json"
OBSERVATION_KEYS = ("bbox", "score", "color", "red_ratio", "blue_ratio")
GATE = 4.0
TRACKED = "ON_TARGET"


def observation_records(recording):
    return [
        {
            "t_capture_ms": tick["t_capture"],
            "dets": {
                camera: [{k: d[k] for k in OBSERVATION_KEYS if k in d} for d in detections]
                for camera, detections in result["dets"].items()
            },
        }
        for tick, result in zip(recording["ticks"], recording["infer"], strict=True)
    ]


def replay_safe(
    records, cameras, size, projector, graph, mode="all", config=None, *, cover_single_uncovered_camera=False
):
    """Policy inputs are only the selected observation fields and capture clocks."""
    tracker = Tracker(projector, gate_m=GATE, relock=config)
    scheduler = CameraScheduler(graph, mode=mode, expand_every=1,
                                cover_single_uncovered_camera=cover_single_uncovered_camera)
    reference = RelockPolicy(RelockConfig())
    result = []
    for i, row in enumerate(records):
        t = row["t_capture_ms"] / 1000
        schedule_trace = {}
        plan = scheduler.plan(tracker.active, tracker.lost, cameras, t_s=t, trace=schedule_trace)
        dets = {
            c: [{key: d[key] for key in OBSERVATION_KEYS if key in d} for d in row["dets"][c]]
            for c in plan["camera_ids"]
            if c in row["dets"]
        }
        previous, previous_t = tracker.est, tracker.t_seen
        tracking = tracker.update(i, dets, size, t)
        scheduler.observe(dets, t)
        all_red = [
            (c, d, d["est_xy"])
            for c, ds in dets.items()
            for d in ds
            if d.get("color") == "red" and d.get("est_xy") is not None
        ]
        representatives = [g[0] for g in group_observations(all_red, 1.5)]
        trace = {
            **schedule_trace,
            "unseen_s": t - previous_t if previous_t is not None else None,
            "reference": reference.reference,
            "groups": [
                {
                    "cam": cam,
                    "est_xy": xy,
                    "features": finite_features(det, reference.config.appearance_fields),
                    "dist_m": math.dist(xy, previous) if previous is not None else None,
                }
                for cam, det, xy in representatives
            ],
        }
        if tracking["state"] == "TRACKING" and tracking["lost_ticks"] == 0 and all_red:
            selected = min(all_red, key=lambda group: math.dist(group[2], tracker.est))
            reference.record_match(selected, all_red)
        result.append({"dets": dets, "tracking": tracking, "schedule": plan, "trace": trace})
    return result


def inventory_file(path, **metadata):
    data = path.read_bytes()
    return {
        **metadata,
        "name": path.name,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def score_replays(entries, traces, folder):
    folder.mkdir(parents=True, exist_ok=True)
    for (label, _, raw), trace in zip(entries, traces, strict=True):
        # Reattach scoring-only fields once every camera decision has finished.
        scored = dict(
            raw,
            label=label,
            infer=[
                {
                    **inf,
                    "dets": row["dets"],
                    "tracking": row["tracking"],
                    "schedule": row["schedule"],
                }
                for inf, row in zip(raw["infer"], trace, strict=True)
            ],
        )
        (folder / f"{label}.t1raw.json").write_text(json.dumps(scored))
    subprocess.run(
        ["node", str(SCORER), str(folder), str(EVALUATION_SCENARIO)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    rows = json.loads((folder / "t1_rows.json").read_text())
    summary = json.loads((folder / "t1_summary.json").read_text())
    return (
        {r["label"]: r["rows"] for r in rows},
        {r["label"]: r["evaluation_only"] for r in summary["runs"]},
    )


def percentiles(values, *quantiles):
    values = sorted(values)
    if not values:
        return [None for _ in quantiles]
    n = len(values) - 1
    return [
        values[int(n * q)] + (values[min(int(n * q) + 1, n)] - values[int(n * q)]) * (n * q % 1)
        for q in quantiles
    ]


def episodes(rows):
    """Evaluation-only visible loss intervals following a successful track."""
    starts = False
    current = []
    groups = []
    for i, row in enumerate(rows):
        status = row["status"]
        if status in ("LOST", "WRONG_PERSON") and starts:
            current.append(i)
        else:
            if current:
                groups.append(current)
                current = []
            starts = starts or status == TRACKED
    if current:
        groups.append(current)
    return groups


def measure_speed(entries, traces):
    measured, reference = [], []
    for (_, _, raw), trace in zip(entries, traces, strict=True):
        for i in range(1, len(trace)):
            a, b = (trace[j]["tracking"] for j in (i - 1, i))
            dt = (raw["ticks"][i]["t_capture"] - raw["ticks"][i - 1]["t_capture"]) / 1000
            if dt < 0.05 or any(x["state"] != "TRACKING" or x["lost_ticks"] for x in (a, b)):
                continue
            measured.append(math.dist(a["est_xy"], b["est_xy"]) / dt)
            p, q = (raw["infer"][j].get("gt_xy") for j in (i - 1, i))
            if p is not None and q is not None:
                reference.append(math.dist(p, q) / dt)

    def summary(samples):
        p50, p95 = percentiles(samples, 0.50, 0.95)
        return {
            "n": len(samples),
            "p50_m_s": p50,
            "p95_m_s": p95,
            "max_m_s": max(samples, default=None),
        }

    return {"projected": summary(measured), "evaluation_only_gt": summary(reference)}


def appearance_report(entries, traces, intervals):
    samples = []
    n = 0
    for (label, _, raw), trace in zip(entries, traces, strict=True):
        for span in intervals[label]:
            for i in span:
                row = trace[i]["trace"]
                truth = raw["infer"][i].get("gt_xy")
                eligible = [
                    g
                    for g in row["groups"]
                    if g["features"] is not None and g["dist_m"] is not None and g["dist_m"] <= 8
                ]
                if truth is None or not eligible or row["reference"] is None:
                    continue
                best = min(eligible, key=lambda c: math.dist(c["est_xy"], truth))
                if math.dist(best["est_xy"], truth) > 1.5:
                    continue
                n += 1
                samples.extend((c is best, c["features"], row["reference"]) for c in eligible)
                break
    report = []
    for indices in ((0,), (1,), (0, 1)):
        fields = tuple(RelockConfig().appearance_fields[i] for i in indices)
        bounds = [percentiles([sample[1][i] for sample in samples], 0.05, 0.95) for i in indices]
        scale = tuple((hi - lo or 1.0) if hi is not None else 1.0 for lo, hi in bounds)
        good, bad = [], []
        for correct, obs, ref in samples:
            d = math.sqrt(
                sum(((obs[i] - ref[i]) / s) ** 2 for i, s in zip(indices, scale, strict=True))
            )
            (good if correct else bad).append(d)
        gap = min(bad) - max(good) if good and bad else None
        enough = n >= 10 and len(good) >= 5 and len(bad) >= 5
        report.append(
            {
                "fields": list(fields),
                "scale": scale,
                "n_episodes": n,
                "n_target": len(good),
                "n_other": len(bad),
                "target_p5_p50_p95": percentiles(good, 0.05, 0.50, 0.95),
                "other_p5_p50_p95": percentiles(bad, 0.05, 0.50, 0.95),
                "gap": gap,
                "tau_app": (max(good) + gap / 2 if gap > 0 else 0.0) if enough else None,
                "margin_app": max(0.0, gap / 2) if enough else None,
            }
        )
    return report


def recovery_counts(traces, rows, intervals):
    result = {}
    for label, trace in traces.items():
        by_mode = {}
        for i, step in enumerate(trace):
            for e in step["tracking"]["events"]:
                if e["type"] != "REACQUIRE" or not e["detail"]:
                    continue
                mode = e["detail"]["mode"]
                group = by_mode.setdefault(mode, {"correct": 0, "wrong": 0, "unknown": 0})
                who = rows[label][i]["following"]
                key = "correct" if who == "T" else "wrong" if who else "unknown"
                group[key] += 1
        correct = sum(mode["correct"] for mode in by_mode.values())
        wrong = sum(mode["wrong"] for mode in by_mode.values())
        unknown = sum(mode["unknown"] for mode in by_mode.values())
        result[label] = {
            "n_episodes": len(intervals[label]),
            "correct": correct,
            "wrong": wrong,
            "unknown": unknown,
            "by_mode": by_mode,
        }
    return result


def entry_audit(entries, traces, scored_rows):
    result = {}
    for (label, _, raw), trace in zip(entries, traces, strict=True):
        visible = ["CAM_ENTRY" in tick.get("gt_visible", []) for tick in raw["ticks"]]
        runs = [i for i, flag in enumerate(visible) if flag and (i == 0 or not visible[i - 1])]
        camera_rows = []
        for start in runs[1:]:
            end = next((i for i in range(start + 1, len(visible)) if not visible[i]), len(visible))
            target_first = auto_first = None
            for i in range(start, end):
                row = trace[i]
                tracking = row["tracking"]
                truth = raw["infer"][i].get("gt_xy")
                if (
                    truth is not None
                    and any(
                        math.dist(option["est_xy"], truth) <= 1.5
                        for option in tracking.get("confirm_candidates", [])
                    )
                    and target_first is None
                ):
                    target_first = i
                if scored_rows[label][i]["status"] == TRACKED and any(
                    event["type"] == "REACQUIRE" for event in tracking["events"]
                ):
                    if target_first is None:
                        target_first = i
                    if auto_first is None:
                        auto_first = i
            t0 = raw["ticks"][start]["t_capture"]
            truth = raw["infer"][start].get("gt_xy")
            old_est = raw["infer"][start - 1]["tracking"].get("est_xy")
            old_dist = [
                math.dist(old_est, det["est_xy"])
                for detections in trace[start]["dets"].values()
                for det in detections
                if truth is not None
                and old_est is not None
                and det.get("color") == "red"
                and det.get("est_xy") is not None
                and math.dist(truth, det["est_xy"]) <= 1.5
            ]
            camera_rows.append(
                {
                    "entry_tick": start,
                    "source_tick": raw["ticks"][start].get("tick"),
                    "state_at_entry": trace[start]["tracking"]["state"],
                    "nearest_target_like_from_recorded_est_m": min(old_dist, default=None),
                    "candidate_distances_at_entry_m": [
                        g["dist_m"]
                        for g in trace[start]["trace"]["groups"]
                        if g["cam"] == "CAM_ENTRY"
                    ],
                    "observed_cameras_at_entry": sorted(trace[start]["dets"]),
                    "correct_candidate_first_tick": target_first,
                    "candidate_delay_ms": raw["ticks"][target_first]["t_capture"] - t0
                    if target_first is not None
                    else None,
                    "auto_reacquire_first_tick": auto_first,
                    "auto_delay_ms": raw["ticks"][auto_first]["t_capture"] - t0
                    if auto_first is not None
                    else None,
                }
            )
        result[label] = camera_rows
    return result


def recovery_comparison(entries, traces, rows, main_rows):
    """Join scores after replay. Every join must preserve the source capture clock."""
    events = []
    main_counts = {"correct": 0, "wrong": 0, "unknown": 0}
    main_event_counts = dict(main_counts)

    def outcome(row):
        who = row["following"]
        return "correct" if who == "T" else "wrong" if who else "unknown"

    def receipt(row):
        return {
            key: row[key]
            for key in ("i", "t_capture", "state", "matched", "following", "status", "events")
        }

    for (label, _, raw), trace in zip(entries, traces, strict=True):
        scored, baseline = rows[label], main_rows[label]
        if len(scored) != len(baseline) or len(scored) != len(trace):
            raise ValueError(f"MAIN_COMPARISON_LENGTH:{label}")
        for i, (row, prior) in enumerate(zip(scored, baseline, strict=True)):
            capture = raw["ticks"][i]["t_capture"]
            if (
                row["i"] != i
                or prior["i"] != i
                or row["t_capture"] != capture
                or prior["t_capture"] != capture
            ):
                raise ValueError(f"MAIN_COMPARISON_CLOCK:{label}:{i}")
            if "REACQUIRE" in prior["events"]:
                main_event_counts[outcome(prior)] += 1
            for event in trace[i]["tracking"]["events"]:
                if event["type"] != "REACQUIRE" or not (event.get("detail") or {}).get("mode"):
                    continue
                last = next((r for r in reversed(scored[:i]) if r["matched"]), None)
                main_counts[outcome(prior)] += 1
                same = prior["matched"] and prior["following"] == row["following"]
                events.append(
                    {
                        "source": label,
                        "tick": i,
                        "source_tick": raw["ticks"][i].get("tick", i),
                        "previous_state": trace[i - 1]["tracking"]["state"] if i else None,
                        **event["detail"],
                        "score": outcome(row),
                        "relock": receipt(row),
                        "main": receipt(prior),
                        "same_main_match": same,
                        "new_wrong": outcome(row) == "wrong" and not same,
                        "last_match_before_loss": receipt(last) if last else None,
                    }
                )
    counts = {name: sum(e["score"] == name for e in events) for name in main_counts}
    return {
        "events": events,
        "relock_counts": counts,
        "main_counts": main_counts,
        "main_reacquire_event_counts": main_event_counts,
        "new_wrong": sum(e["new_wrong"] for e in events),
        "appearance_wrong": sum(
            e["mode"] == "appearance" and e["score"] == "wrong" for e in events
        ),
        "wrong_before_loss": sum(
            e["score"] == "wrong"
            and e["last_match_before_loss"] is not None
            and e["last_match_before_loss"]["following"] not in (None, "T")
            for e in events
        ),
    }


def read_sources(definitions):
    entries = []
    for source in definitions:
        name, directory = source.split("=", 1)
        for path in sorted(Path(directory).glob("*.t1raw.json")):
            entries.append(
                (
                    f"{name}__{path.name.removesuffix('.t1raw.json')}",
                    path,
                    json.loads(path.read_bytes()),
                )
            )
    if len({name for name, _, _ in entries}) != len(entries):
        raise ValueError("DUPLICATE_REPLAY_LABEL")
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--src", action="append", required=True, help="label=fixed observation directory"
    )
    parser.add_argument(
        "--entry-src",
        action="append",
        default=[],
        help="label=supplementary ENTRY observations",
    )
    parser.add_argument("--cameras", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--entry-main-rows",
        type=Path,
        help="original main t1_rows.json for the supplementary recordings",
    )
    parser.add_argument(
        "--sweep-t-short",
        type=lambda s: tuple(float(v) for v in s.split(",")),
        default=(1, 2, 3, 4, 6, 8, 10),
    )
    args = parser.parse_args()
    fixed, entry = read_sources(args.src), read_sources(args.entry_src)
    if not fixed:
        parser.error("at least one fixed observation file is required")
    projector = Projector(load_cameras(str(args.cameras)))
    camera_record = inventory_file(args.cameras)
    graph, binding = load_graph(
        DEFAULT_GRAPH, DEFAULT_GRAPH_SHA256, camera_record["sha256"], list(projector.cams)
    )
    if args.out.exists():
        parser.error("--out must name a fresh directory")
    args.out.mkdir(parents=True)

    def run(entries, name, config=None):
        traces = [
            replay_safe(
                observation_records(raw),
                raw["cfg"]["cams"],
                (raw["cfg"]["w"], raw["cfg"]["h"]),
                projector,
                graph,
                config=config,
            )
            for _, _, raw in entries
        ]
        rows, rates = score_replays(entries, traces, args.out / name)
        return traces, rows, rates

    base, brows, base_rates = run(fixed, "baseline")
    intervals = {label: episodes(rows) for label, rows in brows.items()}
    speed = measure_speed(fixed, base)
    appearance = appearance_report(fixed, base, intervals)
    selected_appearance = max(
        (a for a in appearance if a["tau_app"] is not None),
        key=lambda a: a["gap"],
        default=appearance[-1],
    )
    config = RelockConfig(
        v_walk_m_s=speed["projected"]["p95_m_s"],
        appearance_fields=tuple(selected_appearance["fields"]),
        appearance_scales=tuple(selected_appearance["scale"]),
        tau_app=selected_appearance["tau_app"],
        margin_app=selected_appearance["margin_app"],
    )
    sweeps = {}
    for cutoff in args.sweep_t_short:
        traces, rows, _ = run(fixed, f"short-{cutoff:g}", replace(config, t_short_s=cutoff))
        sweeps[cutoff] = recovery_counts(
            {e[0]: t for e, t in zip(fixed, traces, strict=True)}, rows, intervals
        )
        for label, counts in sweeps[cutoff].items():
            short = counts["by_mode"].get("short_gate", {})
            counts["short_gate"] = short
            counts["eligible_for_selection"] = (
                sum(len(v) for v in intervals.values()) >= 10
                and short.get("correct", 0) + short.get("wrong", 0) >= 5
            )
            counts["unrecovered_episodes"] = len(intervals[label]) - sum(
                any(
                    rows[label][i]["status"] == TRACKED
                    for i in range(span[0], min(span[-1] + 2, len(rows[label])))
                )
                for span in intervals[label]
            )
    selected_per_source = {}
    for label in intervals:
        qualified = [
            t for t, by_label in sweeps.items() if by_label[label]["eligible_for_selection"]
        ]
        values = [t for t in qualified if not sweeps[t][label]["short_gate"].get("wrong")]
        selected_per_source[label] = max(values) if values else (0 if qualified else None)
    selected_short = (
        min(selected_per_source.values()) if None not in selected_per_source.values() else None
    )
    config = replace(config, t_short_s=selected_short)
    final, rows, rates = run(fixed, "relock", config)
    result = {
        "policy_inputs_gt": False,
        "inputs": [inventory_file(path, label=label) for label, path, _ in fixed + entry],
        "calibration": camera_record,
        "graph": binding,
        "n_episodes": sum(map(len, intervals.values())),
        "t_short_s_by_source": selected_per_source,
        "t_short_s_sweep": sweeps,
        "speed": speed,
        "appearance": appearance,
        "config": asdict(config),
        "fixed_baseline": base_rates,
        "fixed_relock": rates,
        "recovery": recovery_counts(
            {e[0]: t for e, t in zip(fixed, final, strict=True)}, rows, intervals
        ),
    }
    comparison_entries, comparison_traces = list(fixed), list(final)
    comparison_rows, main_rows = dict(rows), dict(brows)
    if entry:
        supplementary, supp_rows, rates = run(entry, "entry-supplement", config)
        result["entry_supplement"] = entry_audit(entry, supplementary, supp_rows)
        result["entry_supplement_rates"] = rates
        result["entry_supplement_recovery"] = recovery_counts(
            {e[0]: t for e, t in zip(entry, supplementary, strict=True)},
            supp_rows,
            {label: episodes(rows) for label, rows in supp_rows.items()},
        )
        if args.entry_main_rows is None:
            parser.error("--entry-main-rows is required with --entry-src")
        original = {r["label"]: r["rows"] for r in json.loads(args.entry_main_rows.read_bytes())}
        for label, path, raw in entry:
            main_rows[label] = original[raw.get("label", path.name.removesuffix(".t1raw.json"))]
        result["main_comparison_input"] = inventory_file(args.entry_main_rows)
        comparison_entries.extend(entry)
        comparison_traces.extend(supplementary)
        comparison_rows.update(supp_rows)
    result["r5a"] = recovery_comparison(
        comparison_entries, comparison_traces, comparison_rows, main_rows
    )
    (args.out / "relock.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"n_episodes": result["n_episodes"], "config": result["config"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
