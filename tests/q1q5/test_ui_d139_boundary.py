"""D139 front-desk boundary: the presentation modules carry no ground-truth / script / renderer words.

Moved out of frontend/workbench-v2/ui-d139.test.mjs: the negative pattern itself is a forbidden string for the
architecture guard's frontend scan, so it lives under tests/ (not scanned) and still runs with the q1q5 suite.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "workbench-v2"
FILES = ("ui-present.mjs", "ui-shell.mjs", "ui-model.mjs")
NEGATIVE = re.compile(r"gt_private|ground_truth|renderer_trajectory|visibility_|depth_map", re.IGNORECASE)


def test_front_desk_modules_have_no_hidden_truth_words():
    for name in FILES:
        text = (FRONTEND / name).read_text(encoding="utf-8")
        assert text, name
        assert NEGATIVE.search(text) is None, f"{name} mentions a forbidden source word"


def test_negative_pattern_would_catch_a_leak():
    for sample in ("x.gt_private", "ground_truth", "renderer_trajectory", "visibility_map", "depth_map"):
        assert NEGATIVE.search(sample), sample
