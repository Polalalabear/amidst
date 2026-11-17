#!/usr/bin/env python3
"""D176 branch archive: plan, tag, verify, and restore remote branches.

Subcommands (run inside a clone that fetched all branches and tags):

  plan    --inventory inv.csv --out docs/history/branch_archive_map.csv
          Decide delete/keep for every branch and write the archive map.
  tag     --map docs/history/branch_archive_map.csv
          Create the annotated phase-end and key tags locally. A phase-end tag
          points at a synthetic merge commit whose parents are that phase's
          deleted branch tips that no other kept ref reaches (tree = newest
          parent's tree). Does not push.
  verify  --map docs/history/branch_archive_map.csv [--cited cited.txt]
          Check that every deleted tip (and every cited commit) is an ancestor
          of mainline/main or contained in a tag. Exit 1 on any failure.
  restore --map docs/history/branch_archive_map.csv [--branch NAME]
          Print `git push origin <sha>:refs/heads/<name>` for deleted branches.

The phase table lives in branch_phases.json next to this script.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "branch_phases.json").read_text())


def git(*args: str, input: str | None = None) -> str:
    res = subprocess.run(["git", *args], capture_output=True, text=True, input=input)
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout.strip()


def ok(*args: str) -> bool:
    return subprocess.run(["git", *args], capture_output=True).returncode == 0


def phase_of() -> dict[str, str]:
    m: dict[str, str] = {}
    for key, ph in CFG["phases"].items():
        for b in ph["branches"]:
            if b in m:
                raise SystemExit(f"branch {b} listed in two phases")
            m[b] = key
    return m


def reachable_via(sha: str) -> str:
    for name, ref in (("mainline/q1q5", CFG["mainline"]), ("main", CFG["main"])):
        if ok("merge-base", "--is-ancestor", sha, ref):
            return name
    exact = sorted(git("tag", "--points-at", sha).split())
    if exact:
        return f"tag:{exact[0]}"
    tags = sorted(git("tag", "--contains", sha).split())
    return f"tag:{tags[0]}" if tags else ""


def cmd_plan(a: argparse.Namespace) -> int:
    phases = phase_of()
    snap = dt.date.fromisoformat(CFG["snapshot_date"])
    rows = list(csv.DictReader(open(a.inventory)))
    missing = [r["branch"] for r in rows if r["branch"] not in phases]
    if missing:
        raise SystemExit(f"branches without a phase: {missing}")
    out = []
    for r in rows:
        b = r["branch"]
        reason = CFG["keep"].get(b, "")
        if not reason and int(r["open_prs"]) > 0:
            reason = "open PR " + ";".join(p for p in r["prs"].split(";") if ":OPEN" in p)
        age = (snap - dt.date.fromisoformat(r["date"])).days
        if not reason and b.startswith(tuple(CFG["keep_recent_prefixes"])) and age <= CFG["keep_recent_owner_days"]:
            reason = f"updated {r['date']}; pending confirmation from {b.split('/')[0].capitalize()}"
        out.append({
            "branch": b,
            "phase": phases[b],
            "tip_sha": r["tip_sha"],
            "date": r["date"],
            "author": r["author"],
            "commits_not_in_mainline_or_main": r["commits_not_in_mainline_or_main"],
            "prs": r["prs"],
            "status": "kept" if reason else "deleted",
            "keep_reason": reason,
            "reachable_via": "",  # filled by verify --write
            "restore": f"git push origin {r['tip_sha']}:refs/heads/{b}",
        })
    write_map(a.out, out)
    k = sum(1 for o in out if o["status"] == "kept")
    print(f"{len(out)} branches: {len(out) - k} to delete, {k} kept -> {a.out}", file=sys.stderr)
    return 0


def write_map(path: str, rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda r: (list(CFG["phases"]).index(r["phase"]), r["date"], r["branch"]))
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def make_tag(name: str, target: str, message: str) -> None:
    if ok("rev-parse", "-q", "--verify", f"refs/tags/{name}"):
        cur = git("rev-parse", f"{name}^{{commit}}")
        if cur != git("rev-parse", f"{target}^{{commit}}"):
            raise SystemExit(f"tag {name} exists at {cur}, refusing to move it")
        print(f"tag {name} already at target", file=sys.stderr)
        return
    git("tag", "-a", name, target, "-m", message)
    print(f"tag {name} -> {target[:10]}", file=sys.stderr)


def cmd_tag(a: argparse.Namespace) -> int:
    rows = list(csv.DictReader(open(a.map)))
    for name, kt in CFG["key_tags"].items():
        make_tag(name, git("rev-parse", kt["target"] + "^{commit}"), kt["message"])
    kept_refs = [CFG["mainline"], CFG["main"]] + [f"origin/{r['branch']}" for r in rows if r["status"] == "kept"]
    for key, ph in CFG["phases"].items():
        if not ph["end_tag"]:
            continue
        if ph.get("end_tag_target"):
            make_tag(ph["end_tag"], git("rev-parse", ph["end_tag_target"]),
                     f"End of phase '{key}': {ph['title']} (mainline/q1q5 at D176 snapshot).")
            continue
        tips = []
        for r in sorted((r for r in rows if r["phase"] == key and r["status"] == "deleted"),
                        key=lambda r: r["date"], reverse=True):
            sha = r["tip_sha"]
            covered = (any(ok("merge-base", "--is-ancestor", sha, ref) for ref in kept_refs)
                       or bool(git("tag", "--contains", sha)))
            if not covered and sha not in tips:
                tips.append(sha)
        # drop tips that are ancestors of another selected tip
        tips = [t for t in tips if not any(o != t and ok("merge-base", "--is-ancestor", t, o) for o in tips)]
        if not tips:
            continue
        if len(tips) == 1:
            target = tips[0]
        else:
            tree = git("rev-parse", f"{tips[0]}^{{tree}}")
            parents = [x for t in tips for x in ("-p", t)]
            msg = (f"Archive merge for phase '{key}' (D176)\n\nKeeps the tips of {len(tips)} deleted "
                   f"branches reachable. Tree is the newest parent's tree; nothing was merged into a branch.\n"
                   f"See docs/history/branch_archive_map.csv.\n")
            target = git("commit-tree", tree, *parents, "-m", msg)
        make_tag(ph["end_tag"], target, f"End of phase '{key}': {ph['title']}; keeps deleted branch tips reachable.")
    return 0


def cmd_verify(a: argparse.Namespace) -> int:
    rows = list(csv.DictReader(open(a.map)))
    bad = 0
    for r in rows:
        if r["status"] != "deleted":
            continue
        via = reachable_via(r["tip_sha"])
        r["reachable_via"] = via
        if not via:
            bad += 1
            print(f"UNREACHABLE {r['branch']} {r['tip_sha']}")
    if a.cited:
        safe = set(git("rev-list", CFG["mainline"], CFG["main"], "--tags").split())
        keep = [f"origin/{r['branch']}" for r in rows if r["status"] == "kept"]
        safe |= set(git("rev-list", *keep).split()) if keep else set()
        for sha in Path(a.cited).read_text().split():
            if sha not in safe:
                bad += 1
                print(f"CITED-UNREACHABLE {sha}")
    if a.write:
        write_map(a.map, rows)
    print(f"verify: {bad} problem(s)", file=sys.stderr)
    return 1 if bad else 0


def cmd_restore(a: argparse.Namespace) -> int:
    for r in csv.DictReader(open(a.map)):
        if r["status"] == "deleted" and (not a.branch or r["branch"] == a.branch):
            print(r["restore"])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("plan"); p.add_argument("--inventory", required=True); p.add_argument("--out", required=True)
    p = sp.add_parser("tag"); p.add_argument("--map", required=True)
    p = sp.add_parser("verify"); p.add_argument("--map", required=True); p.add_argument("--cited")
    p.add_argument("--write", action="store_true", help="fill reachable_via in the map")
    p = sp.add_parser("restore"); p.add_argument("--map", required=True); p.add_argument("--branch")
    a = ap.parse_args()
    return {"plan": cmd_plan, "tag": cmd_tag, "verify": cmd_verify, "restore": cmd_restore}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
