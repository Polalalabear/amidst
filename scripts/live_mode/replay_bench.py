"""Replay bench: run replay_advisor.py configurations over recorded streams and print on-target / wrong / lost by group.

Evaluation only (replay_advisor.py answers adjudication questions from the recorded true position). No model, no cost.
Run from the repo root with PYTHONPATH=src:<runtime-deps>; needs node for measure/t1_analyze.mjs.

    python scripts/live_mode/replay_bench.py --work <scratch dir> --src t1=<dir> --src sol=<dir> \
        --config "off=--mode off" --config "gate4=--mode off --gate-m 4" --config "review=--mode review"
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import statistics as st
import subprocess
import sys

SCEN = "docs/evaluation/R004_A4B4_SCENARIO_V2_3_4ACTOR_DRAFT.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--src", action="append", required=True, help="name=dir with *.t1raw.json (repeatable)")
    ap.add_argument("--config", action="append", required=True, help='name=<replay_advisor.py arguments> (repeatable)')
    a = ap.parse_args()
    srcs = dict(x.split("=", 1) for x in a.src)
    configs = {x.split("=", 1)[0]: x.split("=", 1)[1].split() for x in a.config}
    res: dict = collections.defaultdict(lambda: collections.defaultdict(list))
    for name, args in configs.items():
        for sname, sdir in srcs.items():
            out = os.path.join(a.work, name, sname)
            shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
            subprocess.run([sys.executable, "scripts/live_mode/replay_advisor.py", "--in", sdir, "--out", out] + args, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["node", "frontend/live-mode/measure/t1_analyze.mjs", out, SCEN], check=True, stdout=subprocess.DEVNULL)
            for r in json.load(open(os.path.join(out, "t1_summary.json")))["runs"]:
                e = r["evaluation_only"]
                row = (e["on_target"], e["wrong_person"], e["lost"])
                res[name][f"{r['label'].split('_')[0]} {'8cam' if r['cams'] == 8 else 'route cams'}"].append(row)
                res[name]["ALL"].append(row)
    groups = sorted({g for d in res.values() for g in d if g != "ALL"}) + ["ALL"]
    print("on-target / wrong / lost (mean), n = streams")
    print("config".ljust(28), *[g.ljust(22) for g in groups])
    table = {}
    for name in configs:
        cells = []
        for g in groups:
            v = res[name][g]
            m = [round(st.mean(x[i] for x in v), 3) if v else None for i in range(3)]
            table.setdefault(name, {})[g] = {"n": len(v), "on_target": m[0], "wrong_person": m[1], "lost": m[2]}
            cells.append((f"{m[0]:.2f}/{m[1]:.2f}/{m[2]:.2f} n{len(v)}" if v else "-").ljust(22))
        print(name.ljust(28), *cells)
    json.dump({"configs": {k: " ".join(v) for k, v in configs.items()}, "table": table}, open(os.path.join(a.work, "bench.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
