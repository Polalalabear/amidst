"""Timeout accounting fixtures do not run a model or certify semantic factuality."""

from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from amidst.local_agent import benchmark

from .test_manager import EVENT, binding


def test_timeout_exports_stopped_case_and_partial_pack_without_another_busy_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def service(mode: str) -> Any:
        bound = binding(mode)
        return SimpleNamespace(
            context=lambda: SimpleNamespace(
                context=bound, session_ref=bound.session_ref, run_ref=bound.run_ref,
                product_freeze_ref=bound.product_freeze_ref, allowed_tools=bound.allowed_tools),
            base=SimpleNamespace(
                cameras={"DOOR": bound.cameras[0]},
                scope=SimpleNamespace(source_sha256=bound.source_sha256),
                store=SimpleNamespace(query_frames=lambda _: [
                    SimpleNamespace(timestamp=0), SimpleNamespace(timestamp=40)])),
            scope=SimpleNamespace(config_sha256=bound.config_sha256),
            call=lambda *_: {"items": [{"event_ref": EVENT, "kind": "UNKNOWN",
                                        "candidate_count": 2}]})

    runtime = SimpleNamespace(services=[service("photos_only"),
                                       service("photos_plus_observations")])
    monkeypatch.setattr(benchmark, "load_product", lambda _: nullcontext(runtime))
    monkeypatch.setattr(benchmark, "OllamaProvider", lambda **_: SimpleNamespace(
        identity=lambda: {"provider": "SCRIPTED_TEST_ONLY"}))
    starts: list[str] = []

    class TimeoutManager:
        def __init__(self, *_: Any, **__: Any) -> None:
            self.case: dict[str, Any] = {}

        def start(self, _scene: str, _owner: str, message: str, **_: Any) -> dict[str, Any]:
            starts.append(message)
            self.case = {"agent_ref": "agent:timeout", "state": "READY", "answer": None,
                         "question": None, "model_receipts": [], "tool_receipts": [],
                         "metrics": {"model_request_attempt_count": 0},
                         "recovery_token": "must-not-export"}
            return self.case.copy()

        def advance(self, *_: Any) -> None:
            self.case = self.case | {"state": "RUNNING", "metrics": {
                "model_request_attempt_count": 1, "usage_unknown_request_count": 1}}

        def wait_idle(self, _: float) -> bool:
            return False

        def stop(self, *_: Any) -> dict[str, Any]:
            self.case = self.case | {"state": "STOPPED"}
            return self.case.copy()

        def close(self) -> None:
            pass

    monkeypatch.setattr(benchmark, "LocalAgentManager", TimeoutManager)
    settings = tmp_path / "provider.json"
    settings.write_text("{}")
    output = tmp_path / "receipt.json"
    receipt = benchmark.run_benchmark(tmp_path / "unused-product", settings, output)
    assert len(starts) == 1
    assert receipt["case_denominator"] == 1 and receipt["task_denominator"] == 8
    assert receipt["tasks"][0]["state"] == "STOPPED"
    assert receipt["request_attempt_denominator"] == 1
    assert receipt["usage_unknown_request_count"] == 1
    assert receipt["attempted_task_count"] == 1 and not receipt["task_pack_completed"]
    assert len(receipt["not_started_tasks"]) == 7
    assert "must-not-export" not in output.read_text()
    assert json.loads(output.read_text())["tasks"][0]["case"]["state"] == "STOPPED"
