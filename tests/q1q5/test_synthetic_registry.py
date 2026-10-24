"""Exercise standard pinned registry path, without live provider calls."""

import importlib.util
import json
from pathlib import Path

import pytest

from amidst.q1q5.api import from_environment
from amidst.q1q5.baseline_runner import load_cases
from amidst.q1q5.production_preflight import sha

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "synthetic_registry", ROOT / "scripts/prepare_q1q5_synthetic_registry.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_generate_load_and_bind_real_runtime_without_any_model_call(tmp_path, monkeypatch):
    out = tmp_path / "new"
    report = module.generate(out, base_url="http://127.0.0.1:11437", model_digest="a" * 64)
    assert report["provider_calls"] == 0 and report["formal_questions"] == 0
    cases = load_cases(out / "cases.jsonl", sha((out / "cases.jsonl").read_bytes()))
    assert len(cases) == 2 and all(row["data_kind"] == "SYNTHETIC" for row in cases)
    for name, file in [("REGISTRY", "registry.json"), ("OLLAMA_RUNTIME", "runtime.json")]:
        monkeypatch.setenv("AMIDST_Q1Q5_" + name, str(out / file))
        monkeypatch.setenv("AMIDST_Q1Q5_" + name + "_SHA256", sha((out / file).read_bytes()))
    api = from_environment(None, ROOT)
    bootstrap = api.bootstrap()["runs"][0]
    assert bootstrap["q3_llm_available"] and bootstrap["agent_available"]
    assert bootstrap["source_kind"] == "SYNTHETIC"
    assert json.loads((out / "runtime.json").read_text())["model_digest"] == "a" * 64
    with pytest.raises(ValueError):
        module.generate(out, base_url="http://127.0.0.1:11437", model_digest="a" * 64)


@pytest.mark.parametrize(
    "base_url,pin", [("https://example.org", "a" * 64), ("http://127.0.0.1:11437", "missing")]
)
def test_no_remote_endpoint_or_implicit_digest(tmp_path, base_url, pin):
    with pytest.raises(ValueError):
        module.generate(tmp_path / "no", base_url=base_url, model_digest=pin)
    assert not (tmp_path / "no").exists()
