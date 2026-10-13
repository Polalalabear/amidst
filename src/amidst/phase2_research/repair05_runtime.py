"""Separately certified DTO repair; the seven inference-freeze sources stay immutable."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import FunctionType
from typing import Any

from amidst.engineering.registry import opaque_ref
from amidst.phase2_research.repair05_adapter import Repair05Service


def runtime_sha256() -> str:
    return sha256(Path(__file__).read_bytes()).hexdigest()


def _legal_ref(kind: str, *bindings: str) -> str:
    return opaque_ref("repairtrack" if kind == "repair05track" else kind, *bindings)


class Repair05Runtime(Repair05Service):
    def __init__(self, output: Path, *, expected_runtime_sha256: str | None = None, **kwargs: Any):
        self.runtime_source_sha256 = runtime_sha256()
        if (
            expected_runtime_sha256 is not None
            and expected_runtime_sha256 != self.runtime_source_sha256
        ):
            raise ValueError("REPAIR05_RUNTIME_CERTIFICATE_MISMATCH")
        original = Repair05Service.__init__
        # Only this constructor's private globals resolve the repaired ref factory.
        # The inherited module and every registry/function identity remain unchanged.
        constructor = FunctionType(
            original.__code__,
            original.__globals__ | {"opaque_ref": _legal_ref},
            original.__name__,
            original.__defaults__,
        )
        constructor.__kwdefaults__ = original.__kwdefaults__
        constructor(self, output, **kwargs)

    def _scope(self, scene_id: str, run_id: str) -> None:
        if runtime_sha256() != self.runtime_source_sha256:
            raise ValueError("REPAIR05_RUNTIME_SOURCE_CHANGED")
        super()._scope(scene_id, run_id)

    def context(self) -> dict[str, Any]:
        return super().context() | {"runtime_sha256": self.runtime_source_sha256}


def load_service(
    output: Path,
    *,
    scene_id: str = "local-camera-accuracy-v2",
    variant: str = "baseline",
    mode: str = "photos_only",
    expected_manifest_sha256: str | None = None,
    expected_evaluation_sha256: str | None = None,
    expected_runtime_sha256: str | None = None,
) -> Repair05Runtime:
    return Repair05Runtime(
        output,
        scene_id=scene_id,
        variant=variant,
        mode=mode,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_evaluation_sha256=expected_evaluation_sha256,
        expected_runtime_sha256=expected_runtime_sha256,
    )
