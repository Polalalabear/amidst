"""E8 (#780): the Colab notebook drops each model before loading the next one (L4 OOM, 2026-11-28).

The release helpers live in notebook cell 6; this test runs them on CPU against the real
``build_*_inference_fn`` closures (nothing is downloaded or loaded) and checks that a model held in a
builder cache is freed, and that the GPU guard stops the run when memory does not come back.
"""

from __future__ import annotations

import ast
import gc
import json
import types
import weakref
from pathlib import Path

import pytest

from amidst.evaluation.e7_decider_eval import (
    LAYA_AUDITED_COMMIT,
    build_laya_native_inference_fn,
    build_qwen_vl_inference_fn,
)

NOTEBOOK = Path(__file__).resolve().parents[2] / "notebooks" / "e8_colab_eval.ipynb"
HELPERS = ("gpu_gib", "empty_cuda", "model_caches", "release_backend", "with_backend")


class FakeModel:
    """Stands in for the processor / Qwen model / RLAgent held in a builder cache."""


def cell6_source() -> str:
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    hits = [c for c in cells if "".join(c["source"]).lstrip().startswith("# === CELL 6:")]
    assert len(hits) == 1
    return "".join(hits[0]["source"])


def helpers(load_backend, allocated_gib=0.0):
    tree = ast.parse(cell6_source())
    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in HELPERS]
    assert sorted(d.name for d in defs) == sorted(HELPERS)
    ns = {"gc": gc, "types": types, "load_backend": load_backend, "MEMORY_LOG": [], "RUN_LABEL": "r2",
          "GPU_NAME": "NVIDIA L4", "MEM_RELEASE_MAX_GIB": 1.0}
    exec(compile(ast.Module(body=defs, type_ignores=[]), str(NOTEBOOK), "exec"), ns)
    if allocated_gib:
        ns["gpu_gib"] = lambda kind="allocated": allocated_gib
    return ns


def qwen_fn():
    return build_qwen_vl_inference_fn("Qwen/Qwen2.5-VL-7B-Instruct", "main")


def laya_fn():
    return build_laya_native_inference_fn("laya/laya", LAYA_AUDITED_COMMIT, custom_code_audited=True,
                                          audited_commit=LAYA_AUDITED_COMMIT)


@pytest.mark.parametrize("build", [qwen_fn, laya_fn])
def test_model_in_the_builder_cache_is_freed_after_with_backend(build):
    fn = build()
    caches = None
    refs = []

    def load_backend(cfg):
        nonlocal caches
        ns_caches = ns["model_caches"](fn)
        assert len(ns_caches) == 1                      # exactly the builder's `cache` dict, not provenance or option counts
        caches = ns_caches
        model = FakeModel()
        ns_caches[0]["cuda:torch.bfloat16"] = ("processor", model, "cuda")   # what _ensure_loaded stores
        refs.append(weakref.ref(model))
        return (lambda *a: fn.raw(*a)), fn

    ns = helpers(load_backend)
    out = ns["with_backend"]({"model": "qwen7b"}, "part1", lambda raw, f: "done")
    assert out == "done"
    assert caches[0] == {}
    assert refs[0]() is None                            # nothing else held the model
    assert ns["MEMORY_LOG"] == [{"round": "r2", "model": "qwen7b", "phase": "part1", "peak_gib": 0.0,
                                 "after_release_gib": 0.0, "gpu": "NVIDIA L4"}]
    if build is laya_fn:
        assert fn.provenance["revision"] == LAYA_AUDITED_COMMIT   # provenance is not a model cache and stays


def test_model_is_freed_when_the_work_raises():
    fn = qwen_fn()
    refs = []

    def load_backend(cfg):
        model = FakeModel()
        ns["model_caches"](fn)[0]["cuda:torch.bfloat16"] = ("p", model, "cuda")
        refs.append(weakref.ref(model))
        return (lambda *a: fn.raw(*a)), fn

    def work(raw, f):
        raise RuntimeError("CUDA out of memory. Tried to allocate 1.30 GiB")

    ns = helpers(load_backend)
    with pytest.raises(RuntimeError, match="CUDA out of memory"):
        ns["with_backend"]({"model": "qwen7b"}, "timing", work)
    gc.collect()
    assert refs[0]() is None


def test_guard_stops_the_run_when_gpu_memory_is_not_released():
    ns = helpers(lambda cfg: ((lambda *a: None), qwen_fn()), allocated_gib=6.2)
    with pytest.raises(RuntimeError, match=r"not released after qwen3b \(part1\): 6.20 GiB"):
        ns["with_backend"]({"model": "qwen3b"}, "part1", lambda raw, f: None)


def test_no_module_level_model_references_left_in_cell6():
    """The 2026-11-28 leak: module-level raw/fn/ask/audit kept qwen3b alive while qwen7b loaded."""
    tree = ast.parse(cell6_source())
    names = {t.id for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
             for t in (n.targets if isinstance(n, ast.Assign) else [n.target]) if isinstance(t, ast.Name)}
    names |= {n.target.id for n in tree.body if isinstance(n, ast.For) and isinstance(n.target, ast.Name)}
    assert not names & {"raw", "fn", "ask", "audit", "model"}
    assert "free(" not in cell6_source()
