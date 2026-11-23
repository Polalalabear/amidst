#!/usr/bin/env python3
"""CX-F4R: independent, read-only F4 caller; only the frozen scorer is imported.

No F4 execution/scoring script, live code, API client, image or index is loaded.
Outputs are new receipts, never replacements for F4's source files.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

SCORER_SHA = "acacce396f27e0d7c8bf03d527b22272f2622376ed4a43ae6db0842353f87d08"
F4_MANIFEST_SHA = "86899282f5e1d14a17a998c933d8f1407cc165042e0997b0d5ca414b66bc13a5"
CORPUS_PINS = {
    "e3-652-20261122": "853390e3dbecc8209c16c47d6e6a6cd5fc73d57bef2d1c4e11c757f8fa8b812e",
    "e3-reappearances-20261122": "5eac93379533485e754f29ebf54f409e7992bd551db822ab6aeea2022aa78517",
}
ARMS = ("B1", "B2", "A1", "A2", "A3")
REAPPEAR = {"REAPPEAR", "BRANCH_RETURN", "SCREEN_RETURN"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_scorer(path):
    if sha(path) != SCORER_SHA:
        raise ValueError("FROZEN_SCORER_SHA_MISMATCH")
    spec = importlib.util.spec_from_file_location("cx_f4_frozen_scorer", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def safe_path(root, rel):
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("SOURCE_PATH_ESCAPE")
    return path


class Inputs:
    def __init__(self, evidence):
        self.evidence = evidence
        self.files = {}

    def read(self, path, expected):
        digest = sha(path)
        if digest != expected:
            raise ValueError(f"SOURCE_SHA_MISMATCH: {path.name}")
        self.files[str(path.relative_to(self.evidence))] = {
            "sha256": digest,
            "bytes": path.stat().st_size,
        }
        return json.loads(path.read_text())

    def corpus(self, name):
        root = self.evidence / name
        manifest = self.read(root / "MANIFEST.json", CORPUS_PINS[name])
        entries = {f["path"]: f["sha256"] for f in manifest["files"]}
        catalog = self.read(root / "CORPUS.json", entries["CORPUS.json"])
        return root, catalog, entries


def summarize_run(sc, run, gt, case):
    tick_us = run["tick_us"]
    assert tick_us == 200_000 and run["size"] == [320, 180]
    assert run["identity"] == "UNCONFIRMED"
    rows = run["rows"]
    assert [r["tick"] for r in rows] == list(range(len(rows)))
    assert len({r["tick"] for r in gt["ticks"]}) == len(gt["ticks"])
    assert len(rows) == round(case["duration_s"] * 1e6 / tick_us)
    ticks = sc.ticks_from_live(gt["ticks"], rows, "T", tick_us=tick_us, size=run["size"])
    assert len(ticks) == len(rows), "GT_ALIGNMENT_MISSING"
    primary = sc.metrics(ticks, "primary", tick_us)
    # The frozen iou metric is unavailable when a displayed tick has only est_xy.
    strict = sc.metrics(ticks, "iou", tick_us)
    # Report-v2's explicitly post-hoc conservative rule: no displayed box -> LOST.
    conservative_ticks = [
        replace(t, shown_camera=None, pos_hit=None, pos_other=None)
        if t.shown_camera and not t.boxes
        else t
        for t in ticks
    ]
    conservative = sc.metrics(conservative_ticks, "iou", tick_us)
    points = []
    ranking = []
    exits = []
    gt_rows = {r["tick"]: r for r in gt["ticks"]}
    for dp in case["decision_points"]:
        lo, hi = dp["evaluation_window_us"]
        points.append(sc.decision_point_correct(ticks, lo, hi - lo))
        if dp["type"] in {"TRUE_EXIT_APPROACH", "TRUE_EXIT_BOUNDARY"}:
            classes = [sc.classify(t) for t in ticks if lo <= t.t_us <= hi]
            exits.append(
                not any(c in {"FALSE_LOCK", "WRONG_PERSON", "WRONG_CAMERA"} for c in classes)
            )
        if dp["type"] not in REAPPEAR:
            continue
        first = next(
            (
                r
                for n, r in sorted(gt_rows.items())
                if n >= dp["tick"]
                and any(a["id"] == "T" and a["present"] and a["gt_visible"] for a in r["actors"])
            ),
            None,
        )
        assert first is not None, "REAPPEARANCE_NO_VISIBLE_TARGET"
        target = next(a for a in first["actors"] if a["id"] == "T")
        # At the pre-return tick the system has not yet observed the return.
        order = rows[max(0, dp["tick"] - 1)]["ranking"]
        first_camera = target["gt_visible"][0]
        ranking.append(
            {
                "tick": dp["tick"],
                "first_visible_tick": first["tick"],
                "target_camera": first_camera,
                "ranked": order,
                "top1": first_camera in order[:1],
                "top3": first_camera in order[:3],
                "random_top1": 1 / len(case["cameras"]),
            }
        )
    return {
        "primary": primary,
        "iou_frozen": strict,
        "iou_conservative": conservative,
        "decision_points": points,
        "ranking_points": ranking,
        "exit_points": exits,
        "completed_reacquire_s": [
            e["latency_s"]
            for e in sc.reacquire_episodes(ticks, [sc.classify(t) for t in ticks], tick_us)
            if not e["censored"]
        ],
    }


def average_runs(sc, runs):
    counts = {
        criterion: {
            key: statistics.mean(r[criterion]["counts"][key] for r in runs)
            for key in runs[0][criterion]["counts"]
        }
        for criterion in ("primary", "iou_conservative")
    }
    majority = [
        sc.majority(r["decision_points"][i] for r in runs)
        for i in range(len(runs[0]["decision_points"]))
    ]
    exits = [
        sc.majority(r["exit_points"][i] for r in runs) for i in range(len(runs[0]["exit_points"]))
    ]
    ranks = [r for run in runs for r in run["ranking_points"]]
    return {
        "k": len(runs),
        "counts": counts,
        "decision_points": majority,
        "exit_points": exits,
        "top1": sum(p["top1"] for p in ranks),
        "top3": sum(p["top3"] for p in ranks),
        "rank_n": len(ranks),
        "no_ranking": sum(not p["ranked"] for p in ranks),
        "random_top1": sum(p["random_top1"] for p in ranks),
        "latencies": [v for run in runs for v in run["completed_reacquire_s"]],
    }


def pooled(values, arm, criterion="primary"):
    rows = [v[arm] for v in values if arm in v]
    counts = Counter()
    for row in rows:
        counts.update(row["counts"][criterion])
    visible = sum(
        counts[c] for c in ("CORRECT", "MISLOCALIZED", "WRONG_PERSON", "WRONG_CAMERA", "LOST")
    )
    return {
        "segments": len(rows),
        "wrong_person_s": 0.2 * (counts["WRONG_PERSON"] + counts["WRONG_CAMERA"]),
        "follow_rate": counts["CORRECT"] / visible if visible else None,
        "lost_s": counts["LOST"] * 0.2,
        "false_lock_s": counts["FALSE_LOCK"] * 0.2,
        "counts": dict(counts),
        "visible_ticks": visible,
        "decision_correct": sum(sum(r["decision_points"]) for r in rows),
        "decision_n": sum(len(r["decision_points"]) for r in rows),
        "top1": sum(r["top1"] for r in rows),
        "top3": sum(r["top3"] for r in rows),
        "rank_n": sum(r["rank_n"] for r in rows),
        "no_ranking": sum(r["no_ranking"] for r in rows),
    }


def compare(sc, segments, arm, base, criterion="primary"):
    clusters = {case: v for case, v in segments.items() if arm in v and base in v}

    def diff(values, field):
        return pooled(values, arm, criterion)[field] - pooled(values, base, criterion)[field]

    mc = sc.mcnemar(
        [
            (a, b)
            for v in clusters.values()
            for a, b in zip(v[arm]["decision_points"], v[base]["decision_points"], strict=True)
        ]
    )
    return {
        "segments": len(clusters),
        "wrong_person_diff_s": diff(list(clusters.values()), "wrong_person_s"),
        "wrong_person_ci_s": sc.cluster_bootstrap(
            clusters, lambda v: diff(v, "wrong_person_s"), 2000, 660
        ),
        "follow_diff": diff(list(clusters.values()), "follow_rate"),
        "follow_ci": sc.cluster_bootstrap(clusters, lambda v: diff(v, "follow_rate"), 2000, 660),
        "mcnemar": mc,
    }


def top1_rate(values, arm):
    n = sum(v[arm]["rank_n"] for v in values if arm in v)
    return sum(v[arm]["top1"] for v in values if arm in v) / n if n else None


def recompute(evidence, scorer):
    sc = load_scorer(scorer)
    inputs = Inputs(evidence)
    f4 = evidence / "f4-658-20261122"
    manifest_path = f4 / "MANIFEST.sha256"
    if sha(manifest_path) != F4_MANIFEST_SHA:
        raise ValueError("F4_MANIFEST_SHA_MISMATCH")
    manifest = {
        line[66:].removeprefix("./"): line[:64] for line in manifest_path.read_text().splitlines()
    }
    inputs.files["f4-658-20261122/MANIFEST.sha256"] = {
        "sha256": sha(manifest_path),
        "bytes": manifest_path.stat().st_size,
    }
    run_results, segments = {}, {}
    for name, batch in [
        ("e3-652-20261122", "runs-final-9"),
        ("e3-reappearances-20261122", "runs-final-665"),
    ]:
        root, catalog, entries = inputs.corpus(name)
        sources_rel = f"{batch}/SOURCES.json"
        sources = inputs.read(f4 / sources_rel, manifest[sources_rel])
        expected_paths = set()
        for case in catalog["cases"]:
            cid = case["case_id"]
            gt = inputs.read(safe_path(root, case["gt_path"]), case["gt_sha256"])
            assert entries[case["gt_path"]] == case["gt_sha256"]
            segments[cid] = {}
            run_results[cid] = {}
            for arm in ARMS:
                if arm == "A3" and batch == "runs-final-665":
                    continue
                ks = (1,) if arm.startswith("B") else (1, 2, 3)
                scores = []
                for k in ks:
                    rel = f"{batch}/{cid}/{arm}.k{k}.json"
                    expected_paths.add(f"{cid}/{arm}.k{k}.json")
                    run = inputs.read(f4 / rel, manifest[rel])
                    assert (run["case_id"], run["arm"], run["k"]) == (cid, arm, k)
                    scores.append(summarize_run(sc, run, gt, case))
                run_results[cid][arm] = scores
                segments[cid][arm] = average_runs(sc, scores)
        assert set(sources) == expected_paths, "FINAL_RUN_SELECTION_MISMATCH"
    comparisons = {
        f"{a}-{b}": compare(sc, segments, a, b)
        for a, b in [("A2", "B1"), ("A3", "B1"), ("A1", "B1"), ("A2", "B2")]
    }
    conservative = compare(sc, segments, "A2", "B1", "iou_conservative")
    ranks = {cid: v for cid, v in segments.items() if v["A2"]["rank_n"]}
    rank_diff = sc.cluster_bootstrap(
        ranks, lambda v: top1_rate(v, "A2") - top1_rate(v, "A1"), 2000, 660
    )
    rank_ci = sc.cluster_bootstrap(ranks, lambda v: top1_rate(v, "A2"), 2000, 660)
    exits = {cid: v for cid, v in segments.items() if v["A2"]["exit_points"]}
    exit_ci = sc.cluster_bootstrap(
        exits,
        lambda v: statistics.mean(
            [
                int(a) - int(b)
                for row in v
                for a, b in zip(row["A2"]["exit_points"], row["B2"]["exit_points"], strict=True)
            ]
        ),
        2000,
        660,
    )
    totals = {a: pooled(list(segments.values()), a) for a in ARMS}

    def h1(arm):
        c = comparisons[f"{arm}-B1"]
        return sc.verdict_h1(
            c["wrong_person_ci_s"],
            c["follow_ci"],
            c["mcnemar"],
            totals[arm]["decision_n"],
            totals[arm]["segments"],
            conservative["follow_diff"] if arm == "A2" else None,
        )

    medians = {
        a: statistics.median(
            [lat for v in segments.values() if a in v for lat in v[a]["latencies"]]
        )
        for a in ("A1", "A2")
    }
    verdicts = {
        "H1": h1("A2"),
        "H1_A3": h1("A3"),
        "H2": sc.verdict_h2(
            comparisons["A1-B1"]["wrong_person_ci_s"],
            comparisons["A2-B2"]["wrong_person_ci_s"],
            exit_ci,
            totals["A2"]["decision_n"],
            len(segments),
        ),
        "H4": sc.verdict_h4(
            rank_diff,
            top1_rate(list(ranks.values()), "A2"),
            1 / 8,
            rank_ci,
            medians["A2"],
            medians["A1"],
            sum(v["A2"]["rank_n"] // 3 for v in ranks.values()),
        ),
    }
    return {
        "schema": "cx-f4-independent.v1",
        "scorer_sha256": SCORER_SHA,
        "bootstrap": {"seed": 660, "n": 2000},
        "identity": "UNCONFIRMED",
        "paid_api_calls": 0,
        "totals": totals,
        "comparisons": comparisons,
        "h4": {
            "a2_a1_top1_diff": top1_rate(list(ranks.values()), "A2")
            - top1_rate(list(ranks.values()), "A1"),
            "diff_ci": rank_diff,
            "a2_top1_ci": rank_ci,
            "random_top1": 1 / 8,
            "reappearance_points": sum(v["A2"]["rank_n"] // 3 for v in ranks.values()),
            "completed_episode_median_s": medians,
        },
        "d_exit_diff_ci": exit_ci,
        "iou_conservative_a2_b1": conservative,
        "verdicts": verdicts,
        "segments": segments,
        "runs": run_results,
        "consumed_sources": inputs.files,
    }


def compare_report_tables(result, report):
    """Compare all 73 segment rows and five totals at the report's display precision.

    The source scorer rounds per-run follow_rate to four decimals; the report
    averages those before printing three decimals. Retain exact count ratios in
    the independent result, and reproduce that presentation step here only.
    """
    checks, differences = 0, []
    for line in report.read_text().splitlines():
        cells = [x.strip() for x in line.split("|")[1:-1]]
        if line.startswith("| E3-"):
            cid, _, arm = cells[:3]
            runs = result["runs"][cid][arm]
            seg = result["segments"][cid][arm]
            display = [
                str(seg["k"]),
                f"{statistics.mean(r['primary']['wrong_person_s'] for r in runs):.2f}",
                f"{statistics.mean(r['primary']['follow_rate'] for r in runs):.3f}",
                f"{statistics.mean(r['primary']['lost_s'] for r in runs):.2f}",
                f"{statistics.mean(r['primary']['false_lock_s'] for r in runs):.2f}",
                f"{sum(seg['decision_points'])}/{len(seg['decision_points'])}",
            ]
            expected = cells[3:9]
            label = f"{cid}/{arm}"
        elif cells and cells[0] in ARMS and len(cells) == 9:
            arm = cells[0]
            total = result["totals"][arm]
            display = [
                str(total["segments"]),
                f"{total['wrong_person_s']:.1f}",
                f"{round(total['follow_rate'], 4):.3f}",
                f"{total['lost_s']:.1f}",
                f"{total['false_lock_s']:.1f}",
                f"{total['decision_correct']}/{total['decision_n']}",
                f"{total['top1']}/{total['rank_n']}",
                f"{total['top3']}/{total['rank_n']}",
            ]
            expected = cells[1:]
            expected[0] = expected[0].split("（")[0]
            label = arm
        else:
            continue
        for column, (actual, wanted) in enumerate(zip(display, expected, strict=True)):
            checks += 1
            if actual != wanted:
                differences.append(
                    {"row": label, "column": column, "computed": actual, "reported": wanted}
                )
    if checks != 478:
        raise ValueError(f"REFERENCE_REPORT_TABLE_LAYOUT_CHANGED: {checks}")
    return {
        "report_sha256": sha(report),
        "numeric_cells_checked": checks,
        "differences": differences,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--scorer", type=Path, default=Path("src/amidst/evaluation/e3_scoring.py"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reference-report", type=Path)
    args = parser.parse_args()
    evidence = args.evidence_root.resolve()
    out = args.out.resolve()
    if any(out.is_relative_to(evidence / p) for p in (*CORPUS_PINS, "f4-658-20261122")):
        raise ValueError("OUTPUT_MUST_NOT_OVERWRITE_SOURCES")
    result = recompute(evidence, args.scorer)
    if args.reference_report:
        result["report_table_comparison"] = compare_report_tables(result, args.reference_report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("totals", "comparisons", "h4", "iou_conservative_a2_b1", "verdicts")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
