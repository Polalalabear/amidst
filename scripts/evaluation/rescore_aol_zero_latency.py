"""AO-L zero-latency rescoring (#731 item 5, zero paid API calls).

Replays existing AO-L responses from ``e5-aol-20261124/`` as if each valid model
answer were applied immediately at query time (``ask_tick``, zero latency) instead
of after API latency and ``chain_box`` expiration, then scores the resulting
trajectory against the E3 GT sidecars using ``amidst.evaluation.e3_scoring``.

IMPORTANT (Approximation):
    This is explicitly an approximation (``is_approximation: true``). Re-applying
    earlier AO-L answers at ``ask_tick`` changes the ``NeutralTracker`` state on
    subsequent ticks, which in a true zero-latency run would also alter when
    later ``LOST_EARLY`` / ``POLL`` queries are triggered and what ``AO_STATE``
    is sent to the model. Here we keep the recorded AO-L calls fixed and replay
    them at ``ask_tick`` with zero API calls.

GT isolation:
    Replay (``replay_zero_latency_rows``) reads ONLY the AO-L B-log and frozen
    detection index (no GT, no expected events, no answer table). GT sidecars
    (``a-log`` / ``CORPUS.json``) are read exclusively inside ``score_zero_latency_case``.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from amidst.evaluation import e3_scoring as S
from amidst.live_mode.aopen.neutral import NeutralTracker

SCHEMA_VERSION = "aol_zero_latency_rescore_v1"
TICK_US = 200_000
SIZE = (320, 180)
MIN_SCORE = 0.15
CAM_ENTRY_MIN_SCORE = 0.05
VALID_ANSWERS = frozenset({"SELECT", "OWN_BOX", "NOT_VISIBLE", "UNCERTAIN", "STILL_HERE_OCCLUDED"})
APPROXIMATION_NOTE = (
    "Re-scored existing AO-L responses applied immediately at ask_tick (zero latency) "
    "with NeutralTracker continuation; tracker state divergence when an earlier decision "
    "changes is not re-simulated (no new API queries are issued)."
)


class _FallbackProjector:
    """Deterministic pixel-to-ground fallback used only when no camera catalog is supplied (synthetic tests)."""

    def ground(self, camera: str, cx: float, by: float, w: int, h: int) -> list[float]:
        return [round(cx / max(1, w) * 10.0, 4), round(by / max(1, h) * 10.0, 4)]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_frozen_detections_by_tick(e3_root: Path, case_id: str) -> dict[int, dict[str, list[dict]]]:
    """Load frozen person detections (inference-side only, no GT) indexed by tick -> camera_id -> [{bbox, score}]."""
    manifest_path = e3_root / "indexes" / case_id / "detection_index.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw = (manifest_path.parent / manifest["records_ref"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["records_file_sha256"]:
        raise ValueError(f"INDEX_PIN_MISMATCH: {case_id}")
    by_tick: dict[int, dict[str, list[dict]]] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        tick = int(row["frame_index"])
        cam = row["camera_id"]
        min_s = CAM_ENTRY_MIN_SCORE if cam == "CAM_ENTRY" else MIN_SCORE
        dets = [
            {"bbox": list(d["bbox_xyxy_px"]), "score": float(d["score"])}
            for d in row.get("detections") or []
            if d.get("class_label") == "person" and float(d.get("score", 0.0)) >= min_s
        ]
        by_tick.setdefault(tick, {})[cam] = dets
    return by_tick


def _resolve_call_box(call: dict) -> list[float] | None:
    ans = call.get("answer")
    if ans == "OWN_BOX":
        box = call.get("box_xyxy")
        return list(box) if isinstance(box, list) and len(box) == 4 else None
    if ans == "SELECT":
        cam = call.get("camera_id")
        det_id = call.get("detection_id")
        cands = (call.get("request") or {}).get("candidate_list") or []
        for c in cands:
            if c.get("camera_id") == cam and c.get("detection_id") == det_id and c.get("box"):
                return list(c["box"])
    return None


def _is_replayable_answer(call: dict) -> bool:
    """True when the model returned a valid AO answer (including calls that later EXPIRED due to latency)."""
    ans = call.get("answer")
    if ans not in VALID_ANSWERS:
        return False
    reason = call.get("fallback_reason")
    return reason in (None, "EXPIRED", "OCCLUDED_NO_TARGET")


def replay_zero_latency_rows(
    aol_doc: dict,
    dets_by_tick: dict[int, dict[str, list[dict]]],
    projector,
    size: tuple[int, int] = SIZE,
) -> tuple[list[dict], dict]:
    """Replay recorded AO-L calls applied immediately at ``ask_tick`` (inference-side only; NEVER reads GT)."""
    neutral = NeutralTracker(projector, size)
    ranking: list[str] = []

    calls_by_ask: dict[int, list[dict]] = {}
    for call in aol_doc.get("calls") or []:
        ask_tick = call.get("ask_tick")
        if ask_tick is not None:
            calls_by_ask.setdefault(int(ask_tick), []).append(call)

    existing_ticks = [int(r["tick"]) for r in aol_doc.get("rows") or []]
    if existing_ticks:
        ticks = list(range(min(existing_ticks), max(existing_ticks) + 1))
    else:
        ticks = sorted(set(dets_by_tick.keys()) | set(calls_by_ask.keys()))

    stats = {
        "total_calls": len(aol_doc.get("calls") or []),
        "actual_applied_calls": sum(1 for c in (aol_doc.get("calls") or []) if c.get("applied")),
        "actual_expired_calls": sum(1 for c in (aol_doc.get("calls") or []) if c.get("fallback_reason") == "EXPIRED"),
        "zero_latency_applied_calls": 0,
        "recovered_from_expired": 0,
        "skipped_unreplayable": 0,
    }

    rows: list[dict] = []
    for tick in ticks:
        dets = dets_by_tick.get(tick, {})
        neutral.step(tick, neutral.target, dets)
        source = "NEUTRAL" if neutral.target else "NONE"
        events: list[dict] = []

        for call in calls_by_ask.get(tick, []):
            if not _is_replayable_answer(call):
                stats["skipped_unreplayable"] += 1
                continue
            ans = call["answer"]
            cam = call.get("camera_id")
            applied = False
            if ans in ("SELECT", "OWN_BOX"):
                box = _resolve_call_box(call)
                if box is not None and cam:
                    neutral.adopt(tick, cam, box, "AGENT_" + ans)
                    applied = True
            elif ans == "NOT_VISIBLE":
                neutral.clear()
                applied = True
            elif ans == "STILL_HERE_OCCLUDED":
                applied = bool(cam and neutral.occlude(tick, cam))
            elif ans == "UNCERTAIN":
                applied = True  # valid answer; leaves target unchanged

            if call.get("next_camera_ranking"):
                ranking = list(call["next_camera_ranking"])

            if applied:
                source = "AGENT"
                stats["zero_latency_applied_calls"] += 1
                if call.get("fallback_reason") == "EXPIRED":
                    stats["recovered_from_expired"] += 1
                events.append(
                    {
                        "tick": tick,
                        "type": "ADJUDICATED_ZERO_LATENCY",
                        "cam": cam,
                        "detail": {
                            "answer": ans,
                            "was_expired": call.get("fallback_reason") == "EXPIRED",
                            "original_latency_ms": call.get("latency_ms"),
                        },
                    }
                )

        rows.append(
            {
                "tick": tick,
                "tracking": neutral.tracking(),
                "ranking": list(ranking),
                "decision_source": source,
                "neutral_status": neutral.status,
                "events": events,
            }
        )
    return rows, stats


def score_zero_latency_case(
    case: dict,
    a_log: dict,
    actual_aol_doc: dict,
    zero_lat_rows: list[dict],
    tick_us: int = TICK_US,
    size: tuple[int, int] = SIZE,
) -> dict:
    """Scoring side ONLY: compares zero-latency replayed rows vs actual AO-L rows against GT."""
    target = a_log["actor_id"]
    zl_ticks = S.ticks_from_live(a_log["ticks"], zero_lat_rows, target, tick_us=tick_us, size=size)
    act_ticks = S.ticks_from_live(a_log["ticks"], actual_aol_doc["rows"], target, tick_us=tick_us, size=size)

    zl_m = S.metrics(zl_ticks, "primary", tick_us)
    act_m = S.metrics(act_ticks, "primary", tick_us)

    zl_dps = [S.decision_point_correct(zl_ticks, d["timestamp_us"]) for d in case.get("decision_points") or []]
    act_dps = [S.decision_point_correct(act_ticks, d["timestamp_us"]) for d in case.get("decision_points") or []]

    return {
        "case_id": case["case_id"],
        "family": case.get("family", "UNKNOWN"),
        "visible_ticks": zl_m["visible_ticks"],
        "actual_aol": {
            "follow_rate": act_m["follow_rate"],
            "wrong_person_s": act_m["wrong_person_s"],
            "lost_s": act_m["lost_s"],
            "false_lock_s": act_m["false_lock_s"],
            "dp_correct": sum(act_dps),
            "dp_total": len(act_dps),
            "correct_ticks": act_m["counts"]["CORRECT"],
        },
        "zero_latency_aol": {
            "follow_rate": zl_m["follow_rate"],
            "wrong_person_s": zl_m["wrong_person_s"],
            "lost_s": zl_m["lost_s"],
            "false_lock_s": zl_m["false_lock_s"],
            "dp_correct": sum(zl_dps),
            "dp_total": len(zl_dps),
            "correct_ticks": zl_m["counts"]["CORRECT"],
        },
    }


def _aggregate_cases(per_case: list[dict], call_totals: dict, frozen_report: dict | None = None) -> dict:
    vis_total = sum(c["visible_ticks"] for c in per_case)
    act_correct = sum(c["actual_aol"]["correct_ticks"] for c in per_case)
    zl_correct = sum(c["zero_latency_aol"]["correct_ticks"] for c in per_case)

    act_rate = round(act_correct / vis_total, 4) if vis_total else None
    zl_rate = round(zl_correct / vis_total, 4) if vis_total else None
    delta_rate = round(zl_rate - act_rate, 4) if (act_rate is not None and zl_rate is not None) else None

    act_wp = round(sum(c["actual_aol"]["wrong_person_s"] for c in per_case), 3)
    zl_wp = round(sum(c["zero_latency_aol"]["wrong_person_s"] for c in per_case), 3)
    act_lost = round(sum(c["actual_aol"]["lost_s"] for c in per_case), 3)
    zl_lost = round(sum(c["zero_latency_aol"]["lost_s"] for c in per_case), 3)
    act_fl = round(sum(c["actual_aol"]["false_lock_s"] for c in per_case), 3)
    zl_fl = round(sum(c["zero_latency_aol"]["false_lock_s"] for c in per_case), 3)
    act_dp_ok = sum(c["actual_aol"]["dp_correct"] for c in per_case)
    zl_dp_ok = sum(c["zero_latency_aol"]["dp_correct"] for c in per_case)
    dp_total = sum(c["zero_latency_aol"]["dp_total"] for c in per_case)

    total_calls = call_totals["total_calls"]
    expired_calls = call_totals["actual_expired_calls"]
    expired_rate = round(expired_calls / total_calls, 4) if total_calls else None

    frozen_ref = {}
    if frozen_report:
        per_arm = frozen_report.get("per_arm") or {}
        for arm in ("B1", "AO", "AOL"):
            if arm in per_arm:
                pa = per_arm[arm]
                frozen_ref[arm] = {
                    "follow_rate": pa.get("follow_rate"),
                    "wrong_person_s": pa.get("wrong_person_s"),
                    "lost_s": pa.get("lost_s"),
                    "false_lock_s": pa.get("false_lock_s"),
                    "dp_correct": pa.get("dp_correct"),
                    "dp_total": pa.get("dp_total"),
                }

    return {
        "n_segments": len(per_case),
        "visible_ticks_total": vis_total,
        "actual_aol_follow_rate": act_rate,
        "zero_latency_aol_follow_rate": zl_rate,
        "delta_follow_rate": delta_rate,
        "actual_aol_wrong_person_s": act_wp,
        "zero_latency_aol_wrong_person_s": zl_wp,
        "delta_wrong_person_s": round(zl_wp - act_wp, 3),
        "actual_aol_lost_s": act_lost,
        "zero_latency_aol_lost_s": zl_lost,
        "delta_lost_s": round(zl_lost - act_lost, 3),
        "actual_aol_false_lock_s": act_fl,
        "zero_latency_aol_false_lock_s": zl_fl,
        "actual_aol_dp_correct": act_dp_ok,
        "zero_latency_aol_dp_correct": zl_dp_ok,
        "dp_total": dp_total,
        "zero_latency_aol_dp_accuracy": round(zl_dp_ok / dp_total, 4) if dp_total else None,
        "actual_aol_dp_accuracy": round(act_dp_ok / dp_total, 4) if dp_total else None,
        "calls": {
            **call_totals,
            "actual_expired_rate": expired_rate,
        },
        "frozen_reference": frozen_ref,
    }


def run_rescore_from_datapack(
    datapack_root: Path,
    cameras_catalog: Path | None = None,
) -> dict:
    """Run AO-L zero-latency rescoring over all 16 segments in a datapack root."""
    if cameras_catalog is None:
        candidate = datapack_root / "data" / "live-assets-20261115" / "cameras.catalog.json"
        if candidate.is_file():
            cameras_catalog = candidate

    if cameras_catalog is not None and cameras_catalog.is_file():
        from amidst.live_mode.tracker import Projector, load_cameras

        projector = Projector(load_cameras(str(cameras_catalog)))
        camera_sha = sha256_file(cameras_catalog)
    else:
        projector = _FallbackProjector()
        camera_sha = "FALLBACK_SYNTHETIC_PROJECTOR"

    evidence = datapack_root / "evidence"
    aol_root = evidence / "e5-aol-20261124"
    sources = [
        (evidence / "e3-652-20261122", aol_root / "runs-9"),
        (evidence / "e3-reappearances-20261122", aol_root / "runs-665"),
    ]

    frozen_report_path = aol_root / "report.json"
    frozen_report = json.loads(frozen_report_path.read_text(encoding="utf-8")) if frozen_report_path.is_file() else None

    per_case: list[dict] = []
    call_totals = {
        "total_calls": 0,
        "actual_applied_calls": 0,
        "actual_expired_calls": 0,
        "zero_latency_applied_calls": 0,
        "recovered_from_expired": 0,
        "skipped_unreplayable": 0,
    }

    for e3_root, runs_dir in sources:
        corpus_path = e3_root / "CORPUS.json"
        if not corpus_path.is_file():
            continue
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        for case in corpus["cases"]:
            cid = case["case_id"]
            aol_file = runs_dir / cid / "AOL.k1.json"
            if not aol_file.is_file():
                continue
            aol_doc = json.loads(aol_file.read_text(encoding="utf-8"))
            dets_by_tick = load_frozen_detections_by_tick(e3_root, cid)
            zl_rows, cstats = replay_zero_latency_rows(aol_doc, dets_by_tick, projector)
            for k in call_totals:
                call_totals[k] += cstats[k]

            # Scoring side only: load GT a-log and verify pin
            a_raw = (e3_root / case["gt_path"]).read_bytes()
            if hashlib.sha256(a_raw).hexdigest() != case["gt_sha256"]:
                raise ValueError(f"GT_PIN_MISMATCH: {cid}")
            a_log = json.loads(a_raw)
            case_score = score_zero_latency_case(case, a_log, aol_doc, zl_rows)
            case_score["calls"] = cstats
            per_case.append(case_score)

    summary = _aggregate_cases(per_case, call_totals, frozen_report)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "identity_status": "UNCONFIRMED",
        "is_approximation": True,
        "approximation_note": APPROXIMATION_NOTE,
        "camera_catalog_sha256": camera_sha,
        "frozen_report_sha256": sha256_file(frozen_report_path) if frozen_report_path.is_file() else None,
        "summary": summary,
        "per_case": per_case,
    }


def render_markdown(result: dict) -> str:
    s = result["summary"]
    ref = s.get("frozen_reference") or {}
    lines = [
        "# AO-L Zero-Latency Rescoring Report (Approximation)",
        "",
        f"- Generated (UTC): `{result['generated_at_utc']}`",
        f"- Identity status: `{result['identity_status']}`",
        f"- Is approximation: `{result['is_approximation']}`",
        f"- Approximation note: {result['approximation_note']}",
        "",
        "## Summary Comparison (16 E3 Segments)",
        "",
        "| Arm / Mode | Follow Rate | Wrong-Target (s) | Lost (s) | Blind-Lock (s) | Decision Points |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    if "B1" in ref:
        b1 = ref["B1"]
        lines.append(
            f"| B1 (frozen rule) | {b1['follow_rate']:.4f} | {b1['wrong_person_s']:.2f} | {b1['lost_s']:.2f} | "
            f"{b1['false_lock_s']:.2f} | {b1['dp_correct']}/{b1['dp_total']} |"
        )
    if "AO" in ref:
        ao = ref["AO"]
        lines.append(
            f"| AO (frozen offline, K=3) | {ao['follow_rate']:.4f} | {ao['wrong_person_s']:.2f} | {ao['lost_s']:.2f} | "
            f"{ao['false_lock_s']:.2f} | {ao['dp_correct']}/{ao['dp_total']} |"
        )
    lines.append(
        f"| AO-L (actual simlive, K=1) | {s['actual_aol_follow_rate']:.4f} | {s['actual_aol_wrong_person_s']:.2f} | "
        f"{s['actual_aol_lost_s']:.2f} | {s['actual_aol_false_lock_s']:.2f} | "
        f"{s['actual_aol_dp_correct']}/{s['dp_total']} |"
    )
    lines.append(
        f"| **AO-L Zero-Latency (approx)** | **{s['zero_latency_aol_follow_rate']:.4f}** | "
        f"**{s['zero_latency_aol_wrong_person_s']:.2f}** | **{s['zero_latency_aol_lost_s']:.2f}** | "
        f"**{s['zero_latency_aol_false_lock_s']:.2f}** | **{s['zero_latency_aol_dp_correct']}/{s['dp_total']}** |"
    )
    c = s["calls"]
    lines += [
        "",
        "## Latency & Expiration Breakdown",
        "",
        f"- Delta follow rate (Zero-Latency - Actual AO-L): `{s['delta_follow_rate']:+.4f}`",
        f"- Delta lost seconds: `{s['delta_lost_s']:+.2f} s`",
        f"- Delta wrong-target seconds: `{s['delta_wrong_person_s']:+.2f} s`",
        f"- Actual AO-L calls: `{c['total_calls']}` total, `{c['actual_applied_calls']}` applied, "
        f"`{c['actual_expired_calls']}` EXPIRED (`{c['actual_expired_rate']:.4f}`)",
        f"- Zero-latency replayed: `{c['zero_latency_applied_calls']}` applied "
        f"(`{c['recovered_from_expired']}` recovered from EXPIRED)",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datapack-root", type=Path, required=True, help="Read-only datapack root (contains evidence/ and data/)")
    parser.add_argument("--cameras", type=Path, default=None, help="Optional override path to cameras.catalog.json")
    parser.add_argument("--out-json", type=Path, required=True, help="Output JSON path (outside git)")
    parser.add_argument("--out-md", type=Path, default=None, help="Optional output Markdown report path")
    args = parser.parse_args(argv)

    result = run_rescore_from_datapack(args.datapack_root, args.cameras)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.out_md is not None:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(render_markdown(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
