"""Mechanical SYNTHETIC pipeline; model outputs here are explicitly test doubles."""

import hashlib
import io
import json
from pathlib import Path

import pytest
from PIL import Image
from test_baseline_runner import ScriptedQwen
from test_detection_index import Detector
from test_ollama_runtime import config

from amidst.q1q5.api import from_environment
from amidst.q1q5.baseline_runner import execute_sample, load_cases
from amidst.q1q5.linked_runtime import build_inputs, materialize_rgb, query_inputs
from amidst.q1q5.ollama_runtime import bind_runs


def pin(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(tmp_path):
    class Visible(Detector):
        def __call__(self, image):
            return super().__call__(image) if image.getpixel((0, 0)) == (255, 0, 0) else []

    stream = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(stream, format="PNG")
    (tmp_path / "source.png").write_bytes(stream.getvalue())
    assets = tmp_path / "assets.json"
    assets.write_text(
        json.dumps(
            dict(
                schema_version="q-demo.synthetic-rgb-assets.v1",
                formal_dataset=False,
                sources=[
                    dict(
                        camera_id=c,
                        ref="source.png",
                        file_sha256=pin(tmp_path / "source.png"),
                        image_size_px=[8, 8],
                    )
                    for c in ["A", "B"]
                ],
            )
        )
    )
    rgb = tmp_path / "rgb"
    materialize_rgb(assets, pin(assets), rgb)
    prepared = tmp_path / "prepared"
    build_inputs(
        rgb / "rgb.json",
        pin(rgb / "rgb.json"),
        {"source_root": "/SYNTHETIC", "weights": "/SYNTHETIC.pth", "source_hashes": {}},
        prepared,
        predictor_factory=lambda *a, **k: Visible(),
    )
    return rgb, prepared


def test_same_rgb_registry_and_explicit_real_index_seed(tmp_path, monkeypatch):
    rgb, prepared = inputs(tmp_path)
    assert len(json.loads((rgb / "rgb.json").read_text())["records"]) == 20
    registry = prepared / "registry.json"
    monkeypatch.setenv("AMIDST_Q1Q5_REGISTRY", str(registry))
    monkeypatch.setenv("AMIDST_Q1Q5_REGISTRY_SHA256", pin(registry))
    api = from_environment(None, tmp_path)
    assert len(api.runs) == 1
    seed = json.loads((prepared / "SEED_CANDIDATES.json").read_text())["candidates"][0][
        "observation_id"
    ]
    output = tmp_path / "query"
    query_inputs(prepared, pin(registry), seed, config(), output)
    cases = load_cases(output / "cases.jsonl", pin(output / "cases.jsonl"))
    assert cases[1]["selected_seed"]["observation_id"] == seed
    assert all(
        c["binding_id"] == next(iter(api.runs.values())).bindings.index_sha256 for c in cases
    )
    runtime = json.loads((output / "runtime.json").read_bytes())
    run = next(iter(api.runs.values()))
    provider = ScriptedQwen(run.catalog, "timeout")
    bound = bind_runs(
        [run],
        runtime,
        provider_factory=lambda _: provider,
        scheduler_factory=lambda: lambda *args: None,
    )[0]
    from amidst.q1q5.api import QAPI

    api = QAPI([bound], max_responses=128, max_media_refs=4096)
    protocol = json.loads(
        (
            Path(__file__).resolve().parents[2] / "configs/q1q5/baseline_v1_protocol.json"
        ).read_bytes()
    )

    def authorize(*args, **kwargs):
        pass

    for n, case in enumerate(cases):
        for m, profile in enumerate(protocol["profiles"]):
            result = execute_sample(
                api,
                authorize,
                case,
                profile,
                protocol,
                request_loader=lambda _: None,
                session_ref="LOCAL",
                output=tmp_path / f"sample-{n}-{m}",
                iteration=0,
                protocol_sha256="0" * 64,
                lost_after_us=600000,
            )
            assert result["execution_status"] == "COMPLETE"
            assert result["replay"]["status"] == "PASS"
            if case["task"] == "CONTINUOUS_PURSUIT":
                assert result["domain_status"] == "COMPLETE"
                assert result["events"]["camera_switches"] == 1
                assert result["q5"]["provider_calls"] == int(m == 0)


def test_invalid_seed_and_tampered_registry_fail_before_query_output(tmp_path):
    _, prepared = inputs(tmp_path)
    registry = prepared / "registry.json"
    with pytest.raises(ValueError, match="EXPLICIT_DETECTED_SEED"):
        query_inputs(prepared, pin(registry), "made-up", config(), tmp_path / "bad")
    assert not (tmp_path / "bad").exists()
    with pytest.raises(ValueError):
        query_inputs(prepared, "0" * 64, "made-up", config(), tmp_path / "bad")


def test_rgb_source_pin_tamper_rejected(tmp_path):
    rgb, _ = inputs(tmp_path)
    source = rgb / "media/camera-A.png"
    source.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="RGB_PIN"):
        build_inputs(
            rgb / "rgb.json",
            pin(rgb / "rgb.json"),
            {"source_root": "/SYNTHETIC", "weights": "/SYNTHETIC.pth", "source_hashes": {}},
            tmp_path / "bad",
            predictor_factory=lambda *a, **k: Detector(),
        )
