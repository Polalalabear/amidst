"""Offline A/B log scoring. Reads only the two caller-supplied JSON logs.

Actor labels are evaluation annotations, never confirmed identities or runtime inputs.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, deque
from pathlib import Path

SCHEMA_A = "live-ab.a-log.v1"
SCHEMA_B = "live-ab.b-log.v1"
STATUSES = ("ON_TARGET", "WRONG_PERSON", "UNMATCHED", "LOST", "TARGET_OUT_OF_VIEW", "UNKNOWN")


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def point(value):
    return isinstance(value, list) and len(value) == 2 and all(finite(x) for x in value)


def validate(log, schema):
    if not isinstance(log, dict) or log.get("schema_version") != schema:
        raise ValueError("SCHEMA_UNSUPPORTED")
    if not isinstance(log.get("session_id"), str) or not log["session_id"]:
        raise ValueError("SESSION_REQUIRED")
    if not isinstance(log.get("ticks"), list) or any(not isinstance(r, dict) for r in log["ticks"]):
        raise ValueError("TICKS_REQUIRED")
    if any(not isinstance(r.get("tick"), int) or isinstance(r["tick"], bool) for r in log["ticks"]):
        raise ValueError("INVALID_TICK")
    if schema == SCHEMA_B and (
        not isinstance(log.get("actions", []), list)
        or any(not isinstance(r, dict) for r in log.get("actions", []))
    ):
        raise ValueError("INVALID_ACTIONS")


def index_rows(rows):
    result = {}
    for row in rows:
        result.setdefault(row["tick"], []).append(row)
    return result


def actors(row):
    if not isinstance(row.get("actors"), list):
        return None
    result = {}
    for a in row["actors"]:
        if (
            not isinstance(a, dict)
            or not isinstance(a.get("id"), str)
            or a["id"] in result
            or not isinstance(a.get("present"), bool)
        ):
            return None
        if a["present"] and not point(a.get("xy")):
            return None
        result[a["id"]] = a
    return result


def pick_target(action, a_index, b_index):
    source = a_index.get(action.get("tick"), [])
    if len(source) != 1:
        return None, "UNKNOWN", "SOURCE_GT_MISSING_OR_DUPLICATE"
    row = source[0]
    if not finite(row.get("t_capture")):
        return None, "UNKNOWN", "SOURCE_CLOCK_MISSING"
    b_source = b_index.get(action.get("tick"), [])
    if b_source and (len(b_source) != 1 or b_source[0].get("t_capture") != row["t_capture"]):
        return None, "UNKNOWN", "SOURCE_CLOCK_MISMATCH"
    aa = actors(row)
    if aa is None or not point(action.get("est_xy")):
        return None, "UNKNOWN", "SOURCE_GT_OR_PICK_POINT_MISSING"
    distances = sorted(
        (math.dist(action["est_xy"], a["xy"]), name) for name, a in aa.items() if a["present"]
    )
    if not distances or distances[0][0] > 1.5:
        return None, "MISPICK", "MISPICK"
    if len(distances) > 1 and distances[1][0] <= 1.5 and distances[1][0] - distances[0][0] < 0.05:
        return None, "AMBIGUOUS_PICK", "AMBIGUOUS_PICK"
    return distances[0][1], "PICKED", None


def align(row, a_index, b_index):
    source = a_index.get(row["tick"], [])
    if len(source) != 1 or len(b_index[row["tick"]]) != 1:
        return None, "TICK_MISSING_OR_DUPLICATE"
    a = source[0]
    if (
        not finite(row.get("t_capture"))
        or not finite(a.get("t_capture"))
        or row["t_capture"] != a["t_capture"]
        or not finite(row.get("t_resp"))
        or row["t_resp"] < row["t_capture"]
    ):
        return None, "CLOCK_MISMATCH"
    aa = actors(a)
    return (aa, None) if aa is not None else (None, "GT_MISSING")


def classify(row, aa, target):
    if target not in aa:
        return "UNKNOWN", "TARGET_GT_MISSING"
    gt = aa[target]
    if not gt["present"]:
        return "TARGET_OUT_OF_VIEW", None
    visible = gt.get("gt_visible")
    if not isinstance(visible, list) or any(not isinstance(c, str) for c in visible):
        return "UNKNOWN", "GT_VISIBILITY_MISSING"
    if not visible:
        return "TARGET_OUT_OF_VIEW", None
    tr = row.get("tracking")
    if not isinstance(tr, dict):
        return "UNKNOWN", "TRACKING_MISSING"
    state = tr.get("state")
    if state in ("IDLE", "ACQUIRING", "SEARCHING", "NEEDS_PICK"):
        return "UNKNOWN", "NOT_TRACKING"
    if state not in ("TRACKING", "LOST", "TARGET_OUT_OF_VIEW"):
        return "UNKNOWN", "TRACK_STATE_UNSUPPORTED"
    lost = tr.get("lost_ticks")
    if not isinstance(lost, int) or isinstance(lost, bool) or lost < 0:
        return "UNKNOWN", "LOST_TICKS_INVALID"
    if state in ("LOST", "TARGET_OUT_OF_VIEW") or lost > 0 or tr.get("est_xy") is None:
        return "LOST", None
    if not point(tr.get("est_xy")):
        return "UNKNOWN", "ESTIMATE_INVALID"
    if math.dist(tr["est_xy"], gt["xy"]) <= 1.5:
        return "ON_TARGET", None
    if any(
        a["present"] and name != target and math.dist(tr["est_xy"], a["xy"]) <= 1.5
        for name, a in aa.items()
    ):
        return "WRONG_PERSON", None
    return "UNMATCHED", None


def percentile(values, p):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def distribution(values):
    return {"n": len(values), "p50": percentile(values, 0.5), "p95": percentile(values, 0.95)}


def latency(rows):
    samples = sorted(
        (
            (r["t_resp"], r["t_resp"] - r["t_capture"])
            for r in rows
            if finite(r.get("t_resp"))
            and finite(r.get("t_capture"))
            and r["t_resp"] >= r["t_capture"]
        ),
        key=lambda sample: sample[0],
    )
    medians, window = [], deque()
    for at, value in samples:
        window.append((at, value))
        while window[0][0] < at - 1000:
            window.popleft()
        medians.append(statistics.median(v for _, v in window))
    return {
        "raw_ms": distribution([v for _, v in samples]),
        "hud_1s_median_ms": distribution(medians),
        "hud_window": "inclusive last 1000 ms by t_resp; one sample per received response",
        "invalid_samples": len(rows) - len(samples),
    }


def episodes(rows, status, end_time, minimum=1):
    result = []
    start = None
    for i in range(len(rows) + 1):
        current = i < len(rows) and rows[i]["status"] == status
        consecutive = i == 0 or i == len(rows) or rows[i]["tick"] == rows[i - 1]["tick"] + 1
        if start is not None and (not current or not consecutive):
            if i - start >= minimum:
                end = rows[i]["t_capture"] if i < len(rows) else end_time
                result.append(
                    {
                        "start_tick": rows[start]["tick"],
                        "end_tick": rows[i - 1]["tick"],
                        "ticks": i - start,
                        "seconds": max(0, (end - rows[start]["t_capture"]) / 1000),
                        "censored": i == len(rows) or rows[i]["status"] == "UNKNOWN",
                    }
                )
            start = None
        if current and start is None:
            start = i
    return result


def unique_events(log, field):
    events = list(log.get(field, []))
    for r in log["ticks"]:
        events.extend(r.get(field, []) if isinstance(r.get(field), list) else [])
    unique = {}
    for e in events:
        if isinstance(e, dict) and "tick" in e:
            unique[json.dumps(e, sort_keys=True)] = e
    return list(unique.values())


def crowd_statistics(a):
    cfg = a.get("config", {})
    radius, eps = cfg.get("r_person", 0.3), cfg.get("eps_m", 0.02)
    if not finite(radius) or not finite(eps) or radius <= 0 or eps < 0:
        raise ValueError("INVALID_CROWD_CONFIG")
    forced = unique_events(a, "forced_overlap")
    counts = {
        "chain": 0, "nonchain": 0, "player": 0, "unknown_chain": 0,
        "script": 0, "player_phase_shift": 0,
    }
    for e in forced:
        if e.get("kind") == "player":
            counts["player"] += 1
        elif e.get("kind") == "script" and e.get("cause") in ("script", "player_phase_shift"):
            counts[e["cause"]] += 1
            if e["cause"] == "player_phase_shift" and e.get("chain") is True:
                counts["chain"] += 1
        elif e.get("chain") is True:
            counts["chain"] += 1
        elif e.get("chain") is False:
            counts["nonchain"] += 1
        else:
            counts["unknown_chain"] += 1
    raw = adjusted = total = separate = excluded = missing = invalid_forced = 0
    valid_forced = {
        frozenset([e.get("i"), e.get("j")])
        for e in forced
        if e.get("kind") == "script"
        and isinstance(e.get("i"), str)
        and isinstance(e.get("j"), str)
        and e.get("i") != e.get("j")
        and a.get("actor_id") not in (e.get("i"), e.get("j"))
    }
    spawn = unique_events(a, "spawn_adjusted")
    prior_distance = {}
    spawn_pairs = set()
    for index, row in enumerate(a["ticks"]):
        aa = actors(row)
        if aa is None:
            missing += 1
            continue
        player = a.get("actor_id")
        pairs = row.get("forced_pairs", [])
        pair_set = {
            frozenset(p)
            for p in pairs
            if isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) for x in p)
        }
        invalid_forced += len(pair_set - valid_forced)
        pair_set &= valid_forced
        names = [k for k, v in aa.items() if v["present"]]
        for i, name in enumerate(names):
            for other in names[i + 1 :]:
                pair = frozenset([name, other])
                d = math.dist(aa[name]["xy"], aa[other]["xy"])
                if (
                    index == 0
                    and d < 2 * radius
                    and player in pair
                    and any(e.get("i", e.get("actor_id")) == player for e in spawn)
                ):
                    spawn_pairs.add(pair)
                exempt_spawn = pair in spawn_pairs and d >= prior_distance.get(pair, d) - 1e-12
                if d >= 2 * radius or not exempt_spawn:
                    spawn_pairs.discard(pair)
                if player in pair and d < 2 * radius - eps:
                    raw += 1
                    if pair not in pair_set and not exempt_spawn:
                        adjusted += 1
                if pair in pair_set:
                    excluded += 1
                else:
                    total += 1
                    separate += d >= 2 * radius - eps
                prior_distance[pair] = d
    waits = unique_events(a, "block_wait")
    ended_wait = sum(
        e["waited_s"] for e in waits if finite(e.get("waited_s")) and e["waited_s"] >= 0
    )
    final = a["ticks"][-1] if a["ticks"] else {}
    active = final.get("block_wait", [])
    active_wait = (
        sum(
            e["waited_s"]
            for e in active
            if isinstance(e, dict)
            and "tick" not in e
            and finite(e.get("waited_s"))
            and e["waited_s"] >= 0
        )
        if isinstance(active, list)
        else 0
    )
    pauses = final.get("pause_total_i", {})
    pauses = (
        {k: v for k, v in pauses.items() if finite(v) and v >= 0}
        if isinstance(pauses, dict)
        else {}
    )
    return {
        "raw_player_penetrations": raw,
        "player_penetrations": adjusted,
        "separation": separate / total if total else None,
        "forced_pair_samples_excluded": excluded,
        "invalid_forced_pair_samples": invalid_forced,
        "unknown_samples": missing,
        "forced_overlap": counts,
        "forced_overlap_events": forced,
        "spawn_adjusted": spawn,
        "block_wait_total_s": ended_wait + active_wait,
        "pause_total_i": pauses,
        "pause_total_s": sum(pauses.values()),
    }


def score_logs(a, b):
    validate(a, SCHEMA_A)
    validate(b, SCHEMA_B)
    result = {
        "schema_version": "live-ab.score.v1",
        "status": "SCORED",
        "segments": [],
        "unknown_reasons": [],
        "session_id": a["session_id"],
        "identity": "unconfirmed; target_gt is an offline annotation only",
    }
    if a["session_id"] != b["session_id"]:
        result.update(
            status="UNKNOWN", unknown_reasons=["SESSION_MISMATCH"], latency=None, crowd=None
        )
        return result
    a_index, b_index = index_rows(a["ticks"]), index_rows(b["ticks"])
    ordered = sorted(
        b["ticks"], key=lambda r: r.get("t_capture") if finite(r.get("t_capture")) else math.inf
    )
    actions = []
    for action in b.get("actions", []):
        if action.get("ok", True) is False:
            continue
        if not finite(action.get("t_op")):
            result["unknown_reasons"].append("ACTION_CLOCK_MISSING")
            continue
        actions.append(dict(action))
    result["unassigned_ticks"] = []
    for row in ordered:
        _, reason = align(row, a_index, b_index)
        if reason:
            result["unknown_reasons"].append(reason)
        if not finite(row.get("t_capture")):
            result["unassigned_ticks"].append(
                {"tick": row["tick"], "status": "UNKNOWN", "unknown_reason": reason}
            )
    autos = {
        action.get("tick")
        for action in actions
        if action.get("type") == "start"
        and action.get("mode") == "TRACKING"
        and point(action.get("est_xy"))
    }
    for row in ordered:
        for e in (row.get("tracking") or {}).get("events", []):
            if (
                e.get("type") != "ACQUIRE"
                or (e.get("detail") or {}).get("by") != "AUTO_SINGLE"
                or e.get("tick") in autos
            ):
                continue
            autos.add(e.get("tick"))
            source = b_index.get(e.get("tick"), [])
            if len(source) == 1:
                src = source[0]
                if finite(src.get("t_capture")) and point(
                    (src.get("tracking") or {}).get("est_xy")
                ):
                    actions.append(
                        {
                            "type": "auto",
                            "tick": src["tick"],
                            "est_xy": src["tracking"]["est_xy"],
                            "t_op": src["t_capture"],
                        }
                    )
    actions.sort(key=lambda action: action["t_op"])
    current = None
    final_time = max(
        [
            r.get("t_resp", r.get("t_capture", 0))
            for r in ordered
            if finite(r.get("t_resp", r.get("t_capture")))
        ]
        + [0]
    )
    for action in actions:
        kind = action.get("type")
        start_single = (
            kind == "start" and action.get("mode") == "TRACKING" and point(action.get("est_xy"))
        )
        if kind == "reselect" or (kind == "start" and action.get("reselect") is True):
            continue
        closes = kind in ("start", "stop", "pick", "auto")
        if current is not None and closes:
            current["end_t_op"] = action["t_op"]
            current = None
        if kind in ("pick", "auto") or start_single:
            target, status, reason = pick_target(action, a_index, b_index)
            current = {
                "start_t_op": action["t_op"],
                "end_t_op": final_time,
                "candidate_source_tick": action.get("tick"),
                "pick_by": "USER_PICK" if kind == "pick" else "AUTO_SINGLE",
                "pick_status": status,
                "target_gt": target,
                "pick_unknown_reason": reason,
            }
            result["segments"].append(current)
            if reason:
                result["unknown_reasons"].append(reason)
    for segment in result["segments"]:
        rows = []
        for row in ordered:
            capture = row.get("t_capture")
            if not finite(capture) or not segment["start_t_op"] <= capture < segment["end_t_op"]:
                continue
            aa, reason = align(row, a_index, b_index)
            if reason or segment["target_gt"] is None:
                status, reason = "UNKNOWN", reason or segment["pick_unknown_reason"]
            else:
                status, reason = classify(row, aa, segment["target_gt"])
            if reason:
                result["unknown_reasons"].append(reason)
            rows.append(
                {
                    "tick": row["tick"],
                    "t_capture": capture,
                    "status": status,
                    "unknown_reason": reason,
                    "active_cam": (row.get("tracking") or {}).get("active_cam"),
                }
            )
        counts = Counter(r["status"] for r in rows)
        n = sum(counts[k] for k in STATUSES[:4])
        switches = 0
        previous = None
        for row in rows:
            cam = row["active_cam"]
            if row["status"] == "UNKNOWN":
                previous = None
            elif cam:
                switches += bool(previous and previous != cam)
                previous = cam
        wrong = episodes(rows, "WRONG_PERSON", segment["end_t_op"], 2)
        segment.update(
            rows=rows,
            counts={k: counts[k] for k in STATUSES},
            visible_scored_ticks=n,
            rates={k: counts[k] / n if n else None for k in STATUSES[:4]},
            camera_switches=switches,
            wrong_person_episodes=wrong,
            identity_switch_proxy_count=len(wrong),
            lost_episodes=episodes(rows, "LOST", segment["end_t_op"]),
        )
    result["unknown_reasons"] = sorted(set(result["unknown_reasons"]))
    if result["unknown_reasons"]:
        result["status"] = "PARTIAL"
    result["latency"] = latency(ordered)
    result["crowd"] = crowd_statistics(a)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--operator-json", type=Path, required=True)
    ap.add_argument("--system-json", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        if args.out.resolve() in (args.operator_json.resolve(), args.system_json.resolve()) or (
            args.out.exists()
            and any(args.out.samefile(p) for p in [args.operator_json, args.system_json])
        ):
            raise ValueError("OUTPUT_OVERWRITES_INPUT")

        def bad_constant(value):
            raise ValueError(f"NONFINITE_JSON:{value}")

        a = json.loads(args.operator_json.read_text(encoding="utf8"), parse_constant=bad_constant)
        b = json.loads(args.system_json.read_text(encoding="utf8"), parse_constant=bad_constant)
        text = json.dumps(score_logs(a, b), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf8")
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(f"live_ab_score: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
