#!/usr/bin/env python3
"""Check a G4 receipt copy against D101-1 option A (minimum-scope approval).

Offline and read-only. Passing means the selected copy matches option A's listed
items; it is not a G4 approval (that needs D101-2 steps 3-5) and it grants no
runtime authority. The payload hash is delegated to scripts/check_g4_receipt.py
(#352), not reimplemented here.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

A4 = "ctrl-lcorr-s1-a4-5fps-v1-r004"
B4 = "ctrl-lcorr-s1-b4-5fps-v1-r004"
# D101-1: four edges, each listed only for the run that uses it.
APPROVED_EDGES = {
    "E_OUT_VEST": [A4], "E_VEST_CORR": [A4],
    "E_W_CORNER": [B4], "E_PORTAL_R101": [B4],
}
# D101-1: the 16 transitions (A4 4, B4 12) with a non-empty edge_path in #348's table.
APPROVED_TRANSITIONS = {
    A4: [
        "T_CAM_EXT_CAR__CAM_W1", "T_CAM_EXT_CLEAR__CAM_W1",
        "T_CAM_W1__CAM_EXT_CAR", "T_CAM_W1__CAM_EXT_CLEAR",
    ],
    B4: [
        "T_CAM_BRANCH__CAM_W1", "T_CAM_BRANCH__CAM_W2", "T_CAM_R101_IN__CAM_W1",
        "T_CAM_R101_IN__CAM_W2", "T_CAM_W1__CAM_BRANCH", "T_CAM_W1__CAM_R101_IN",
        "T_CAM_W1__CAM_WIDE", "T_CAM_W2__CAM_BRANCH", "T_CAM_W2__CAM_R101_IN",
        "T_CAM_W2__CAM_WIDE", "T_CAM_WIDE__CAM_W1", "T_CAM_WIDE__CAM_W2",
    ],
}
M1 = ("T_CAM_W1__CAM_W2", "T_CAM_W2__CAM_W1")
NOT_APPROVED_EDGE = "E_CORNER_N"
# #348 keeps E_PORTAL_R102 TOPOLOGICAL_ONLY / UNKNOWN; option A does not touch it.
# Token sets are UNKNOWN: #260 has not frozen the approved vocabulary, so both the
# draft's "APPROVED" and #352's synthetic "APPROVED_WALKABLE"/"OPEN" are accepted.
APPROVED_TRAVERSABILITY = {"APPROVED", "APPROVED_WALKABLE"}
APPROVED_STATE = {"APPROVED", "OPEN"}
UNAPPROVED = {"NOT_APPROVED", "UNKNOWN"}
UNAPPROVED_TRAVERSABILITY = UNAPPROVED | {"TOPOLOGICAL_ONLY"}

FORBIDDEN_HASHES = {
    "draft_pending": "7ea8c5e5e37238f406170367563efa58c73be42ef890ffe431d58f8fb18f6323",
    "reference": "f1e0bfe664616caf0b5370c16607edfefceacba8eb273747807c2cd645be09a3",
}
GRAPH_COMMIT = "0c34287b0b0c21c672f863fd281934f37e8aa24b"
GRAPH_DIR = "configs/q1q5/graphs/r004/"
GRAPH_PINS = {  # input_pins key -> (file in #294@0c34287, file-byte SHA-256)
    "camera_graph_file_sha256": ("camera_graph_v3_1.json", "e250413a0d0a2aeb61bd98bb1763236b1e39127f919cee1ee3ca3bd906b78409"),
    "region_graph_file_sha256": ("region_graph_v3_1.json", "a2f737805cf5446c6ba01fa4bebfddd2186d040cbd94314cf573c082191b24e1"),
    "tracking_scope_file_sha256": ("tracking_scope_v3_1.json", "ed5b68995094b060b21a9dba6a05e26a21aa0af15c0f8dcb7fd0bd56424af80a"),
}
# Provenance flag `gt_read: false` is allowed; any other GT / visibility / depth key is not.
FORBIDDEN_KEY = re.compile(
    r"^(gt|gt_.*|.*_gt|ground_?truth.*|visib.*|.*_visib.*|depth.*|.*_depth|trajectory|renderer.*)$", re.I)


def load_receipt_checker():
    spec = importlib.util.spec_from_file_location("g4_receipt_checker", ROOT / "scripts/check_g4_receipt.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows(doc, name):
    rows = doc.get(name)
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ValueError(f"{name} must be an array of objects")
    return rows


def check_edges_approved(doc):
    rows = {r.get("edge_id"): r for r in _rows(doc, "edge_decisions")}
    bad = []
    for edge, runs in APPROVED_EDGES.items():
        r = rows.get(edge)
        if r is None:
            bad.append(f"{edge} missing")
        elif r.get("traversability") not in APPROVED_TRAVERSABILITY or r.get("state") not in APPROVED_STATE:
            bad.append(f"{edge} not approved: {r.get('traversability')}/{r.get('state')}")
        elif r.get("run_ids") != runs:
            bad.append(f"{edge} run_ids {r.get('run_ids')} != {runs}")
    return not bad, bad or "4 edges approved with option A run scopes"


def check_edges_rest_unapproved(doc):
    bad = []
    rows = _rows(doc, "edge_decisions")
    if len({r.get("edge_id") for r in rows}) != len(rows):
        bad.append("duplicate edge_id")
    for r in rows:
        edge = r.get("edge_id")
        if edge in APPROVED_EDGES:
            continue
        if edge == NOT_APPROVED_EDGE:
            ok = r.get("traversability") == "NOT_APPROVED" and r.get("state") == "NOT_APPROVED"
        else:
            ok = r.get("traversability") in UNAPPROVED_TRAVERSABILITY and r.get("state") in UNAPPROVED
        if not ok:
            bad.append(f"{edge}: {r.get('traversability')}/{r.get('state')}")
    return not bad, bad or "other edges are NOT_APPROVED/UNKNOWN"


def check_corner_n_not_approved(doc):
    rows = [r for r in _rows(doc, "edge_decisions") if r.get("edge_id") == NOT_APPROVED_EDGE]
    ok = len(rows) == 1 and rows[0].get("traversability") == "NOT_APPROVED" and rows[0].get("state") == "NOT_APPROVED"
    return ok, "E_CORNER_N is NOT_APPROVED" if ok else f"E_CORNER_N must be NOT_APPROVED, got {rows}"


def check_transitions_approved(doc):
    rows = {r.get("transition_id"): r for r in _rows(doc, "transition_decisions")}
    bad = []
    for run, ids in APPROVED_TRANSITIONS.items():
        for tid in ids:
            r = rows.get(tid)
            if r is None:
                bad.append(f"{tid} missing")
            elif r.get("decision") != "APPROVED":
                bad.append(f"{tid} decision {r.get('decision')}")
            elif r.get("run_ids") != [run]:
                bad.append(f"{tid} run_ids {r.get('run_ids')} != {[run]}")
    return not bad, bad or "16 transitions approved (A4 4, B4 12)"


def check_m1_unknown(doc):
    rows = {r.get("transition_id"): r for r in _rows(doc, "transition_decisions")}
    bad = [f"{t}: {rows.get(t, {}).get('decision', 'missing')}" for t in M1 if rows.get(t, {}).get("decision") != "UNKNOWN"]
    return not bad, bad or "both M1 directions are UNKNOWN"


def check_rest_unapproved(doc):
    listed = {t for ids in APPROVED_TRANSITIONS.values() for t in ids}
    bad = []
    for r in _rows(doc, "transition_decisions"):
        if r.get("transition_id") not in listed and r.get("decision") not in UNAPPROVED:
            bad.append(f"transition {r.get('transition_id')}: {r.get('decision')}")
    for r in _rows(doc, "region_purpose_decisions"):
        if r.get("decision") not in UNAPPROVED:
            bad.append(f"region {r.get('region_id')}: {r.get('decision')}")
    return not bad, bad or "other transitions and all regions are NOT_APPROVED/UNKNOWN"


def check_derived_empty(doc):
    rows = _rows(doc, "derived_legal_transitions_by_run")
    ok = {r.get("run_id") for r in rows} == {A4, B4} and all(r.get("transition_ids") == [] for r in rows)
    return ok, "derived legal transitions are [] for A4 and B4" if ok else f"derived lists must be [] for both runs: {rows}"


def check_purposes_empty(doc):
    bad = []
    for name in ("edge_decisions", "transition_decisions", "region_purpose_decisions"):
        bad += [f"{name}:{r.get('edge_id') or r.get('transition_id') or r.get('region_id')}"
                for r in _rows(doc, name) if r.get("allowed_purposes") != []]
    scopes = (doc.get("input_pins") or {}).get("run_camera_scopes")
    bad += [f"run scope {s.get('run_id')}" for s in (scopes if isinstance(scopes, list) else []) if s.get("allowed_purposes") != []]
    if doc.get("approved_purposes", []) != []:
        bad.append("approved_purposes")
    return not bad, bad or "allowed_purposes is [] everywhere"


def check_hash_recompute(doc, receipt_checker):
    stored = doc.get("decisions_sha256")
    recomputed = receipt_checker.decisions_sha256(doc)
    return stored == recomputed, f"stored {stored} recomputed {recomputed}"


def check_hash_not_forbidden(doc):
    stored = doc.get("decisions_sha256")
    hit = [name for name, value in FORBIDDEN_HASHES.items() if stored == value]
    return not hit, f"decisions_sha256 is the {hit[0]} hash, which cannot be approved" if hit else "hash is neither the pending draft nor the reference value"


def check_graph_pins(doc, git_repo=None):
    pins = doc.get("input_pins") or {}
    bad = [f"{k}: {pins.get(k)}" for k, (_, sha) in GRAPH_PINS.items() if pins.get(k) != sha]
    ref = (doc.get("provenance") or {}).get("graph_ref")
    if ref != f"#294@{GRAPH_COMMIT}":
        bad.append(f"provenance.graph_ref: {ref}")
    if git_repo:
        import hashlib
        for key, (name, sha) in GRAPH_PINS.items():
            blob = subprocess.run(["git", "-C", str(git_repo), "show", f"{GRAPH_COMMIT}:{GRAPH_DIR}{name}"],
                                  capture_output=True)
            if blob.returncode or hashlib.sha256(blob.stdout).hexdigest() != sha:
                bad.append(f"git bytes of {name} at {GRAPH_COMMIT[:7]} do not match the pin")
    return not bad, bad or "graph pins match #294@0c34287 v3_1 file bytes"


def check_no_forbidden_keys(doc):
    found = []

    def walk(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "gt_read":
                    if child is not False:
                        found.append(f"{path}/{key}={child!r}")
                elif FORBIDDEN_KEY.match(key):
                    found.append(f"{path}/{key}")
                walk(child, f"{path}/{key}")
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, f"{path}[{i}]")

    walk(doc, "")
    return not found, found or "no GT, visibility or depth keys"


def run_checks(doc, receipt_checker=None, git_repo=None):
    checks = [
        ("A1_edges_approved", "four D101-1 edges approved, option A run scopes", check_edges_approved),
        ("A2_edges_rest_unapproved", "other edges NOT_APPROVED/UNKNOWN (R102 stays TOPOLOGICAL_ONLY)", check_edges_rest_unapproved),
        ("A3_corner_n_not_approved", "E_CORNER_N is NOT_APPROVED", check_corner_n_not_approved),
        ("A4_transitions_approved", "16 listed transitions approved on their own run", check_transitions_approved),
        ("A5_m1_unknown", "both M1 directions UNKNOWN", check_m1_unknown),
        ("A6_rest_unapproved", "other transitions and every region NOT_APPROVED/UNKNOWN", check_rest_unapproved),
        ("A7_derived_empty", "derived legal transition lists are [] for both runs", check_derived_empty),
        ("B_allowed_purposes_empty", "allowed_purposes is [] everywhere", check_purposes_empty),
        ("C_hash_recompute", "decisions_sha256 equals the canonical payload hash", None),
        ("D_hash_not_forbidden", "hash is not the pending draft or reference value", check_hash_not_forbidden),
        ("E_graph_pins", "graph pins are #294@0c34287 v3_1 file bytes", None),
        ("F_no_forbidden_keys", "no GT, visibility or depth keys", check_no_forbidden_keys),
    ]
    results = []
    for check_id, title, fn in checks:
        try:
            if check_id == "C_hash_recompute":
                ok, detail = check_hash_recompute(doc, receipt_checker or load_receipt_checker())
            elif check_id == "E_graph_pins":
                ok, detail = check_graph_pins(doc, git_repo)
            else:
                ok, detail = fn(doc)
        except Exception as exc:  # malformed input is a FAIL, never a crash
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        results.append({"id": check_id, "title": title, "status": "PASS" if ok else "FAIL", "detail": detail})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path, help="G4 receipt JSON (the selected option-A copy)")
    parser.add_argument("--git-repo", type=Path, help="repo holding #294@0c34287, to also compare v3_1 bytes")
    args = parser.parse_args(argv)
    try:
        receipt_checker = load_receipt_checker()
        doc = receipt_checker.parse_json(args.receipt.read_bytes())
    except Exception as exc:
        print(json.dumps({"receipt": str(args.receipt), "overall": "FAIL", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 1
    results = run_checks(doc, receipt_checker, args.git_repo)
    overall = "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL"
    print(json.dumps({"receipt": str(args.receipt), "overall": overall, "checks": results}, ensure_ascii=False, indent=2))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
