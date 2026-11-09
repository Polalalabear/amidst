#!/usr/bin/env python3
"""Inventory every remote branch of the repository (D176 branch tidy-up).

Writes one CSV row per remote branch with: tip SHA, date, author, commit
counts, ancestry against mainline/q1q5 and main, linked PRs, tags at or
containing the tip, and whether mainline docs or the given text files cite
the branch name or its short SHA.

Usage (run inside a clone that has fetched all branches and tags):

    python3 scripts/history/branch_inventory.py \
        --prs prs.json --cite-text c93.txt --cite-text c445.txt \
        --out branch_inventory.csv

`prs.json` comes from:
    gh pr list --state all --limit 1000 \
        --json number,headRefName,state,baseRefName,title > prs.json

Read-only: the script never changes refs.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

MAINLINE = "origin/mainline/q1q5"
MAIN = "origin/main"


def git(*args: str, check: bool = True) -> str:
    res = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout.strip()


def is_ancestor(a: str, b: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b]).returncode == 0


def remote_branches() -> list[str]:
    out = git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/")
    return sorted(b for b in out.splitlines() if b not in ("origin", "origin/HEAD"))


def tag_map() -> dict[str, list[str]]:
    """commit SHA -> tags that point at it (peeled)."""
    out = git("for-each-ref", "--format=%(refname:short) %(*objectname) %(objectname)", "refs/tags/")
    m: dict[str, list[str]] = defaultdict(list)
    for line in out.splitlines():
        parts = line.split()
        name, sha = parts[0], parts[1]  # peeled sha if annotated, else object sha
        m[sha].append(name)
    return m


def doc_citations(ref: str, needles: list[str]) -> list[str]:
    hits: list[str] = []
    for n in needles:
        res = subprocess.run(
            ["git", "grep", "-l", "-F", n, ref, "--", "docs/"],
            capture_output=True, text=True,
        )
        for line in res.stdout.splitlines():
            path = line.split(":", 1)[1]
            if path not in hits:
                hits.append(path)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prs", required=True, help="JSON from gh pr list")
    ap.add_argument("--cite-text", action="append", default=[],
                    help="extra text file (issue comments etc.) to search for citations")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    prs_by_head: dict[str, list[dict]] = defaultdict(list)
    for pr in json.loads(Path(args.prs).read_text()):
        prs_by_head[pr["headRefName"]].append(pr)
    texts = {Path(p).name: Path(p).read_text(errors="replace") for p in args.cite_text}
    tags = tag_map()

    rows = []
    for rb in remote_branches():
        name = rb.removeprefix("origin/")
        sha = git("rev-parse", rb)
        date, author = git("log", "-1", "--format=%cs%x09%an", rb).split("\t")
        total = int(git("rev-list", "--count", rb))
        unique = int(git("rev-list", "--count", rb, "--not", MAINLINE, MAIN))
        anc_mainline = is_ancestor(rb, MAINLINE)
        anc_main = is_ancestor(rb, MAIN)
        tags_at = tags.get(sha, [])
        tags_containing = git("tag", "--contains", sha).split()
        prs = prs_by_head.get(name, [])
        open_prs = [p for p in prs if p["state"] == "OPEN"]
        needles = [name, sha[:7]]
        docs = doc_citations(MAINLINE, needles)
        text_hits = [k for k, v in texts.items() if any(n in v for n in needles)]
        rows.append({
            "branch": name,
            "tip_sha": sha,
            "date": date,
            "author": author,
            "commits_total": total,
            "commits_not_in_mainline_or_main": unique,
            "ancestor_of_mainline_q1q5": anc_mainline,
            "ancestor_of_main": anc_main,
            "prs": ";".join(f"#{p['number']}:{p['state']}->{p['baseRefName']}" for p in prs),
            "open_prs": len(open_prs),
            "tags_at_tip": ";".join(tags_at),
            "tags_containing_tip": ";".join(tags_containing),
            "cited_in_mainline_docs": ";".join(docs),
            "cited_in_texts": ";".join(text_hits),
        })

    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} branches -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
