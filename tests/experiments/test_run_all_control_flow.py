"""run_all.sh --execute control flow with a FAKE interpreter (PYTHON_BIN): soft steps, exit-7 budget skips, resume semantics.

Nothing real runs: every ``python -B scripts/...`` call is answered by the fake below (unknown scripts exit 99), ``-c`` snippets
(STATUS writer, completeness check, Stage 1 ledger check) run on the real interpreter, no network, no key, no model, no money.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUN_ALL = ROOT / "scripts/experiments/run_all.sh"

FAKE = r'''#!__PY__
import json, os, sys, pathlib
argv = sys.argv[1:]
if argv and argv[0] == "-c":
    os.execv(sys.executable, [sys.executable] + argv)          # real snippets (status writer, completeness, Stage 1 budget check)
cfg = json.loads(pathlib.Path(os.environ["FAKE_CFG"]).read_text())
log = pathlib.Path(os.environ["FAKE_LOG"])
def note(tag): log.open("a").write(tag + "\n")
def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default
def many(name):
    i = argv.index(name) + 1
    out = []
    while i < len(argv) and not argv[i].startswith("--"):
        out.append(argv[i]); i += 1
    return out
def fails(tag): return tag in cfg.get("fail", [])
def half(tag): return tag in cfg.get("half", [])
def die(tag, code=1):
    sys.stderr.write("FAKE_FAIL " + tag + "\n"); sys.exit(code)
def wjson(path, doc):
    path = pathlib.Path(path); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(doc))
def complete(out):
    wjson(pathlib.Path(out) / "STATUS.json", {"status": "COMPLETE"})

if argv[0] == "-m":
    note("module:" + argv[1]); sys.exit(0)
script = pathlib.Path(argv[1] if argv[0] == "-B" else argv[0]).name
rest = argv[2:] if argv[0] == "-B" else argv[1:]
argv = rest
cases = many("--cases") if "--cases" in argv else []

if script in ("rescore_aol_zero_latency.py", "generate_unified_analysis.py"):
    note(script)
    if fails(script): die(script)
    sys.exit(0)
if script == "e6_detect_formal.py":
    note("detect"); wjson(pathlib.Path(arg("--out")) / "DETECTION_RECEIPT.json", {"ok": True}); sys.exit(0)
if script == "e6_rule_neutral.py":
    if "--evidence" in argv:
        out = pathlib.Path(arg("--out")); note("rn_old")
        if out.exists(): die("OUTPUT_EXISTS")
        wjson(out / "E3-A1" / "RN_U.json", {"rows": []}); sys.exit(0)
    out = pathlib.Path(arg("--out")); note("rn")
    if out.exists(): die("OUTPUT_EXISTS")
    for i, c in enumerate(cases):
        for arm in ("RN_U", "RN_N"):
            wjson(out / c / (arm + ".json"), {"rows": []})
        if half("rn") and i == 2: die("rn half")
    if fails("rn"): die("rn")
    sys.exit(0)
if script == "e3_f4_run.py":
    note("b1"); out = pathlib.Path(arg("--out"))
    for i, c in enumerate(cases):
        f = out / c / "B1.k1.json"
        if f.exists(): continue
        if half("b1") and i == 3:
            f.parent.mkdir(parents=True, exist_ok=True); f.write_text('{"rows": [1,'); die("b1 half")   # truncated json
        wjson(f, {"arm": "B1", "rows": []})
    if fails("b1"): die("b1")
    sys.exit(0)
if script == "e5_run.py":
    if "--dry-run" in argv:
        for c in cases: print("DRY_RUN", c, json.dumps({"est_total_usd": 0.5}))
        sys.exit(0)
    note("ao"); out = pathlib.Path(arg("--out"))
    for i, c in enumerate(cases):
        for k in (1, 2, 3):
            f = out / c / f"AO.k{k}.json"
            if f.exists(): continue
            if half("ao") and i == 1 and k == 2:
                f.parent.mkdir(parents=True, exist_ok=True); f.write_text('{"arm": "AO", '); die("ao half")
            wjson(f, {"arm": "AO", "rows": []})
    if fails("ao"): die("ao")
    sys.exit(0)
if script == "e6_arms_run.py":
    abl = arg("--ablation")
    if "--dry-run" in argv:
        tag = "abl_est:" + abl if abl else "arms_dry"
        note(tag)
        if fails(tag): die(tag)
        arms = {a: {"estimate_upper_bound": {"est_total_usd": 1.0}} for a in ("DEANCHOR", "DEANCHOR_HIST", "DEANCHOR_HIST_SUM")}
        print(json.dumps({"k": 3, "cases": cases, "arms": arms, "est_total_usd_upper_bound": 1.0})); sys.exit(0)
    out = pathlib.Path(arg("--out"))
    tag = "abl:" + abl if abl else ("diag" if arg("--k") == "1" else "arms")
    note(tag)
    if "--receipt" in argv: note(tag + ":receipt")
    if fails(tag): die(tag)
    for c in cases:
        for a in many("--arms") if "--arms" in argv else ["DEANCHOR"]:
            for k in range(1, int(arg("--k")) + 1):
                f = out / c / f"{a}.k{k}.json"
                if not f.exists(): wjson(f, {"rows": []})
    if tag == "arms" and half("arms"):
        wjson(out / "STATUS.json", {"status": "INCOMPLETE"}); die("arms incomplete")
    complete(out); sys.exit(0)
if script == "e6_select_arm.py":
    sub = argv[0]
    if sub == "select":
        out = pathlib.Path(arg("--out")); note("select")
        wjson(out / "BATCH3_FREEZE.json", {"SELECTED_AGENT": cfg.get("selected", "DEANCHOR_HIST")})
        import hashlib
        (out / "MANIFEST.sha256").write_text(hashlib.sha256((out / "BATCH3_FREEZE.json").read_bytes()).hexdigest() + "  BATCH3_FREEZE.json\n")
        sys.exit(0)
    if sub == "verify-freeze":
        note("verify")
        rec = pathlib.Path(arg("--receipt")).parent / "VERIFY_FREEZE.json"
        if fails("verify"):
            wjson(rec, {"ok": False}); die("verify", 6)
        wjson(rec, {"ok": True}); wjson(arg("--out"), {"per_group_budget_usd": {"AO_ORIG": 1.0}, "agent_arms_budget_usd": 2.0}); sys.exit(0)
    if sub == "budget-check":
        est = pathlib.Path(arg("--estimate")).name.split(".")[0]
        note("budget:" + est)
        wjson(arg("--out"), {"max_usd": 1.0})
        sys.exit(cfg.get("budget_rc", {}).get(est, 0))
if script == "e6_verdict_run.py":
    out = pathlib.Path(arg("--out"))
    explore = "--ablation-runs" in argv
    note("explore" if explore else "verdict")
    if explore: note("ablation_runs:" + ",".join(pathlib.Path(x).name for x in many("--ablation-runs")))
    if out.exists() and (out / "verdict_e6.json").exists(): die("OUTPUT_EXISTS")
    if fails("explore" if explore else "verdict"): die("verdict")
    out.mkdir(parents=True, exist_ok=True)
    (out / "verdict_e6.json").write_text("{}")
    if half("verdict") and not explore: die("verdict half")        # no MANIFEST: half-written
    import hashlib
    (out / "MANIFEST.sha256").write_text(hashlib.sha256(b"{}").hexdigest() + "  verdict_e6.json\n")
    sys.exit(0)
sys.stderr.write("UNKNOWN_SCRIPT " + script + "\n"); sys.exit(99)
'''


class World:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.cfg = tmp / "cfg.json"
        self.log = tmp / "calls.log"
        self.log.write_text("")
        self.fake = tmp / "fakepy"
        self.fake.write_text(FAKE.replace("__PY__", sys.executable))
        self.fake.chmod(0o755)
        self.ledger = tmp / "ledger"
        self.ledger.mkdir()
        (self.ledger / "usage.jsonl").write_text("")
        self.out = tmp / "local/evidence/e6-formal-run-20261127"
        self.freeze = tmp / "local/evidence/e6-batch3-freeze-20261127"
        self.set()

    def set(self, **cfg):
        self.cfg.write_text(json.dumps(cfg))

    def run(self, *args, phase="all"):
        env = dict(os.environ, PYTHON_BIN=str(self.fake), FAKE_CFG=str(self.cfg), FAKE_LOG=str(self.log),
                   AMIDST_API_USAGE_DIR=str(self.ledger))
        for k in ("E6_STOP_AT_BATCH3", "E6_PHASE"):
            env.pop(k, None)
        return subprocess.run(["bash", str(RUN_ALL), "--execute", "--datapack-root=" + str(self.tmp / "local"), f"--e6-phase={phase}", *args],
                              cwd=self.tmp, env=env, capture_output=True, text=True, timeout=120)

    def calls(self):
        return self.log.read_text().split()

    def clear(self):
        self.log.write_text("")

    def status(self):
        return json.loads((self.out / "STATUS.json").read_text())["steps"]


@pytest.fixture()
def w(tmp_path):
    return World(tmp_path)


def states(w):
    return {k: v["state"] for k, v in w.status().items()}


# ------------------------------------------------------------------ (a) soft steps never abort the run
def test_soft_failures_do_not_abort_and_later_steps_still_run(w):
    w.set(fail=["abl:NO_IMAGE", "explore"])
    r = w.run()
    assert r.returncode == 0, r.stderr[-800:]
    calls = w.calls()
    assert "abl:NO_IMAGE" in calls and "abl:NO_SPATIAL" in calls          # NO_IMAGE failed, NO_SPATIAL still ran
    assert "explore" in calls                                              # the exploratory comparison was attempted (and failed softly)
    assert {"rescore_aol_zero_latency.py", "generate_unified_analysis.py", "module:amidst.evaluation.e7_scoring_bridge"} <= set(calls)   # Stage 4-6
    st = states(w)
    assert st["Stage 2e: NO_IMAGE (K=3, paid, exploratory)"] == "SOFT_FAILED"
    assert st["Stage 2e: exploratory comparison (verdict_e6, ablation runs)"] == "SOFT_FAILED"
    assert st["Stage 2e: NO_SPATIAL (K=3, paid, exploratory)"] == "DONE"
    assert st["Stage 2 (E6)"] == "COMPLETE"
    assert "SOFT_FAILED" in r.stderr


def test_soft_dry_run_estimate_failure_skips_only_that_ablation(w):
    w.set(fail=["abl_est:NO_IMAGE"])
    r = w.run()
    assert r.returncode == 0, r.stderr[-800:]
    assert "abl:NO_IMAGE" not in w.calls() and "abl:NO_SPATIAL" in w.calls()
    assert states(w)["Stage 2e: NO_IMAGE dry-run estimate"] == "SOFT_FAILED"


def test_receipt_is_passed_to_every_formal_paid_call(w):
    assert w.run().returncode == 0
    assert "arms:receipt" in w.calls() and "abl:NO_IMAGE:receipt" in w.calls()


# ------------------------------------------------------------------ (b) exit 7 is a skip, not an error; hard failures still reach STATUS
def test_budget_exit_7_is_skipped_not_failed_and_later_hard_failure_still_writes_status(w):
    w.set(budget_rc={"NO_IMAGE": 7}, fail=["rescore_aol_zero_latency.py"])
    r = w.run()
    calls = w.calls()
    assert "budget:NO_IMAGE" in calls and "abl:NO_IMAGE" not in calls      # skipped, never paid
    assert "abl:NO_SPATIAL" in calls                                        # the next ablation still ran
    assert json.loads((w.out / "ablation-status/NO_IMAGE.json").read_text())["state"] == "BUDGET_SKIPPED"
    assert json.loads((w.out / "ablation-NO_IMAGE/STATUS.json").read_text())["status"] == "BUDGET_SKIPPED"
    st = states(w)
    assert any(v == "BUDGET_SKIPPED" for v in st.values())
    # the ERR trap is still armed afterwards: a hard failure in Stage 5 stops the run and is recorded
    assert r.returncode != 0
    assert st["Stage 5: AO-L Zero-Latency Rescoring (0 USD)"] == "FAILED"
    assert "generate_unified_analysis.py" not in calls                     # stopped, did not go on to Stage 6


def test_budget_check_other_nonzero_is_soft_failed_not_fatal(w):
    w.set(budget_rc={"NO_IMAGE": 5})
    r = w.run()
    assert r.returncode == 0
    assert "abl:NO_IMAGE" not in w.calls() and "abl:NO_SPATIAL" in w.calls()
    assert states(w)["Stage 2e: NO_IMAGE budget check"] == "SOFT_FAILED"


def test_hard_step_failure_writes_failed_status_and_stops(w):
    w.set(fail=["verdict"])
    r = w.run()
    assert r.returncode != 0
    assert states(w)["Stage 2d: verdict_e6 scoring (0 USD)"] == "FAILED"
    assert "abl:NO_IMAGE" not in w.calls()                                  # nothing after the failed hard step


def test_batch3_gate_failure_exits_6_and_runs_nothing_formal(w):
    w.set(fail=["verify"])
    r = w.run()
    assert r.returncode == 6
    calls = w.calls()
    assert "b1" not in calls and "ao" not in calls and "arms" not in calls
    assert states(w)["Batch-3 mechanical gate (verify-freeze)"] == "BATCH3_GATE_FAILED"


def test_stop_at_batch3_exits_0_after_the_gate(w):
    os.environ["E6_STOP_AT_BATCH3"] = "1"
    try:
        env = dict(os.environ, PYTHON_BIN=str(w.fake), FAKE_CFG=str(w.cfg), FAKE_LOG=str(w.log), AMIDST_API_USAGE_DIR=str(w.ledger))
        r = subprocess.run(["bash", str(RUN_ALL), "--execute", "--datapack-root=" + str(w.tmp / "local"), "--e6-phase=all"], cwd=w.tmp, env=env,
                           capture_output=True, text=True, timeout=120)
    finally:
        del os.environ["E6_STOP_AT_BATCH3"]
    assert r.returncode == 0 and "verify" in w.calls() and "b1" not in w.calls()
    assert states(w)["E6_STOP_AT_BATCH3=1"] == "STOPPED_AT_BATCH3"


# ------------------------------------------------------------------ (c) resume: only COMPLETE counts, half-written output is redone
def test_second_run_skips_every_completed_step(w):
    assert w.run().returncode == 0
    w.clear()
    r = w.run()
    assert r.returncode == 0, r.stderr[-800:]
    again = set(w.calls()) & {"b1", "rn", "ao", "arms", "verdict", "diag", "detect", "select", "verify", "abl:NO_IMAGE", "abl:NO_SPATIAL", "explore"}
    assert again == set(), again
    assert "complete (resume)" in r.stdout or "skipped" in r.stdout


def test_half_written_rn_dir_is_moved_aside_and_redone(w):
    w.set(half=["rn"])
    assert w.run().returncode != 0
    assert states(w)["Stage 2c: R-N on the formal recording (0 USD, RN_U + RN_N)"] == "FAILED"
    assert (w.out / "rn").is_dir() and not (w.out / "rn/STATUS.json").exists()      # exists but NOT complete
    w.set()
    w.clear()
    r = w.run()
    assert r.returncode == 0, r.stderr[-800:]
    assert w.calls().count("rn") == 1                                        # redone exactly once (the old dir would make the script refuse)
    assert list(w.out.glob("rn.incomplete-*")), "the half-written dir is kept aside, not deleted"
    assert json.loads((w.out / "rn/STATUS.json").read_text())["status"] == "COMPLETE"
    assert "b1" not in w.calls()                                             # completed steps before it were not redone


def test_truncated_b1_and_ao_json_are_quarantined_and_regenerated(w):
    w.set(half=["b1"])
    assert w.run().returncode != 0
    bad = w.out / "b1/E6-S04/B1.k1.json"
    assert bad.exists() and not (w.out / "b1/STATUS.json").exists()
    w.set(half=["ao"])
    w.clear()
    assert w.run().returncode != 0                                           # b1 now completes, ao half-writes
    assert (w.out / "b1/STATUS.json").exists() and not (w.out / "ao_orig/STATUS.json").exists()
    w.set()
    w.clear()
    r = w.run()
    assert r.returncode == 0, r.stderr[-800:]
    assert list(w.out.glob("ao_orig/*/AO.k2.json.corrupt-*")), "the truncated AO file was moved aside"
    for f in list(w.out.glob("ao_orig/*/AO.k*.json")) + list(w.out.glob("b1/*/B1.k1.json")):
        json.loads(f.read_text())                                            # every remaining run file parses
    assert len(list(w.out.glob("ao_orig/*/AO.k*.json"))) == 36
    assert "b1" not in w.calls()                                             # b1 was already complete


def test_directory_that_merely_exists_is_not_complete(w):
    assert w.run().returncode == 0
    (w.out / "b1/STATUS.json").unlink()                                      # exists, but no longer says COMPLETE
    w.clear()
    assert w.run().returncode == 0
    assert "b1" in w.calls()                                                 # redone (all files already exist, the script skips them)


def test_incomplete_arms_status_reruns_but_complete_does_not(w):
    w.set(half=["arms"])
    assert w.run().returncode != 0
    assert json.loads((w.out / "arms/STATUS.json").read_text())["status"] == "INCOMPLETE"
    w.set()
    w.clear()
    assert w.run().returncode == 0
    assert w.calls().count("arms:receipt") == 1                              # the paid step's own SKIP_EXISTS handles the files, it is invoked again
    w.clear()
    assert w.run().returncode == 0
    assert "arms:receipt" not in w.calls()                                   # COMPLETE: not invoked at all, no second spend


def test_half_written_verdict_without_manifest_is_redone(w):
    w.set(half=["verdict"])
    assert w.run().returncode != 0
    assert (w.out / "verdict/verdict_e6.json").exists() and not (w.out / "verdict/MANIFEST.sha256").exists()
    w.set()
    w.clear()
    r = w.run()
    assert r.returncode == 0, r.stderr[-800:]
    assert w.calls().count("verdict") == 1 and list(w.out.glob("verdict.incomplete-*"))
    assert (w.out / "verdict/MANIFEST.sha256").exists()


def test_manifest_alone_counts_as_complete(w):
    assert w.run().returncode == 0
    v = w.out / "verdict"
    (v / "STATUS.json").unlink(missing_ok=True)                              # verdict never had one: MANIFEST verification is what counts
    w.clear()
    assert w.run().returncode == 0 and "verdict" not in w.calls()
    (v / "verdict_e6.json").write_text('{"tampered": 1}')                    # MANIFEST no longer verifies -> redone
    w.clear()
    assert w.run().returncode == 0 and "verdict" in w.calls()


def test_half_written_receipt_without_manifest_is_reselected(w):
    assert w.run().returncode == 0
    (w.freeze / "MANIFEST.sha256").write_text("0" * 64 + "  BATCH3_FREEZE.json\n")
    w.clear()
    r = w.run()
    assert r.returncode == 0, r.stderr[-800:]
    assert "select" in w.calls() and list(w.freeze.glob("BATCH3_FREEZE.json.incomplete-*"))


def test_missing_ledger_in_execute_mode_stops_before_any_e6_step(w):
    (w.ledger / "usage.jsonl").unlink()
    r = w.run()
    assert r.returncode != 0 and "LEDGER_REQUIRED" in (r.stderr + r.stdout)
    assert w.calls() == []


def test_budget_skipped_root_is_passed_to_the_exploratory_comparison(w):
    w.set(budget_rc={"NO_IMAGE": 7})
    r = w.run()
    assert r.returncode == 0, r.stderr[-800:]
    runs = [c for c in w.calls() if c.startswith("ablation_runs:")]
    assert runs == ["ablation_runs:ablation-NO_IMAGE,ablation-NO_SPATIAL"]       # skipped NO_IMAGE listed beside the completed NO_SPATIAL


def test_only_failed_ablations_are_not_passed(tmp_path):
    w = World(tmp_path)
    w.set(fail=["abl:NO_IMAGE"], budget_rc={"NO_SPATIAL": 7})
    assert w.run().returncode == 0
    assert [c for c in w.calls() if c.startswith("ablation_runs:")] == ["ablation_runs:ablation-NO_SPATIAL"]
