"""Bind the repository's own TEST-ONLY glue so `AMIDST_REQUIRE_IMPL=1 pytest tests/q1q5` is self-contained.

Explicitly exported variables always win; nothing here touches real assets (SYNTHETIC inputs only).
"""
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def _bind_synthetic_test_glue():
    os.environ.setdefault("AMIDST_TEAM_EVAL_DRIVER", "team_eval_pack_driver")
    created = None
    if "AMIDST_YYIN_BUILDER_INPUTS" not in os.environ:
        base = Path(tempfile.mkdtemp(prefix="amidst-synthetic-")).resolve()
        created = base
        spec = importlib.util.spec_from_file_location("_make_synthetic_yyin", ROOT / "scripts/make_synthetic_yyin_pack_inputs.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        out = base / "SYNTHETIC_INPUTS"
        module.make(out)
        os.environ["AMIDST_YYIN_BUILDER_INPUTS"] = str(out / "inputs.json")
    yield
    if created is not None:
        os.environ.pop("AMIDST_YYIN_BUILDER_INPUTS", None)
        shutil.rmtree(created, ignore_errors=True)
