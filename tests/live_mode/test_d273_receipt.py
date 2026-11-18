"""ENTRY censoring is not equality, zero delay or an automatic scheduling failure."""

import importlib.util
import sys
from pathlib import Path

path = Path(__file__).resolve().parents[2] / "scripts/live_mode"
# Direct-script helper import: keep its module namespace local to this test.
spec = importlib.util.spec_from_file_location("d273_receipt", path / "joint_schedule_d_receipt.py")
module = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(path))
try:
    spec.loader.exec_module(module)
finally:
    sys.path.pop(0)
entry_gate = module.entry_gate


def event(ms):
    return {"censored": ms is None, "target_lock_ms": ms}


def test_failed_all_baseline_is_unknown_not_pass_or_scheduling_failure():
    result = entry_gate([event(None)], [event(None)])
    assert result == {"status": "BASELINE_TRACKER_NO_RELOCK", "pass": None}
    assert entry_gate([event(None)], [event(10)])["pass"] is None
    assert entry_gate([], [])["pass"] is None


def test_measured_adaptive_relock_compares_real_delays_without_relaxing_gate():
    assert entry_gate([event(100)], [event(100)])["pass"] is True
    assert entry_gate([event(100)], [event(101)])["pass"] is False
    assert entry_gate([event(100)], [event(None)])["pass"] is False


def test_unpaired_episodes_are_unknown_even_if_each_observed_delay_is_finite():
    assert entry_gate([event(100)], [event(50), event(50)]) == {
        "status": "UNPAIRED_EPISODES",
        "pass": None,
    }


def test_committed_runtime_receipt_omits_absolute_local_input_paths():
    composition = {
        "head": "a" * 40,
        "runtime_files": {},
        "args": {
            "models": "/private/weights",
            "assets": "/home/secret/assets",
            "cameras": "/camera.json",
            "camera_graph": "/checkout/config.json",
            "schedule": "adaptive",
        },
        "runs": [],
        "paid_calls": 0,
    }
    public = module.public_runtime(composition)
    assert public["settings"] == {"schedule": "adaptive"}
    assert composition["args"]["models"] == "/private/weights"
