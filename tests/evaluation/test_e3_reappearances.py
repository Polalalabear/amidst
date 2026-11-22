"""Run the dependency-free Node GT-event contract in CI as well as locally."""
from pathlib import Path
import subprocess


def test_gt_only_reappearance_contract():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(["node", "--test", "tests/evaluation/e3_reappearance_events.test.mjs"],
                            cwd=root, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
