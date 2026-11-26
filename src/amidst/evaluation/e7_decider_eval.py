"""E7 Local / Colab Decider Evaluation — Inference & Acceleration Comparison (GT-Isolated).

Implements #727 / #731 D384-D387 decider adapters, MANIFEST SHA-256 verification,
hardware provenance collection, strict AO JSON parsing (no retry inflation), and
accelerated vs unaccelerated comparison.

STRICT GT ISOLATION:
    This module is inference-side ONLY. It MUST NEVER import ``e3_scoring`` or
    accept, open, or read any Ground Truth file, ``expected`` event, or answer
    table. All scoring lives strictly in ``amidst.evaluation.e7_scoring_bridge``.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "e7_decider_runs_v1"
VALID_ANSWERS = frozenset({"SELECT", "OWN_BOX", "NOT_VISIBLE", "UNCERTAIN", "STILL_HERE_OCCLUDED"})
SUPPORTED_SCOPES = frozenset({"e3_16_segments", "e6_12_segments", "combined"})
SUPPORTED_INPUT_MODES = frozenset({"image_text", "text_only"})
DEFAULT_SIZE = (320, 180)


class ManifestVerificationError(RuntimeError):
    """Raised immediately when any upload-pack file is missing or fails SHA-256 verification."""


class CustomCodeAuditError(RuntimeError):
    """Raised when a Hugging Face model requiring custom Python code has not passed audit."""


# --------------------------------------------------------------------------- MANIFEST verification
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest_sha256(pack_root: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    """Verify every file listed in ``MANIFEST.sha256`` under ``pack_root``.

    Stops immediately with :class:`ManifestVerificationError` on missing files,
    malformed lines, path traversal, or SHA-256 mismatch.
    """
    mpath = manifest_path if manifest_path is not None else pack_root / "MANIFEST.sha256"
    if not mpath.is_file():
        raise ManifestVerificationError(f"MANIFEST_MISSING: {mpath}")

    verified = 0
    root_resolved = pack_root.resolve()
    for lineno, raw_line in enumerate(mpath.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise ManifestVerificationError(f"MANIFEST_LINE_INVALID:{lineno}: {raw_line!r}")
        expected_sha, rel = parts[0].lower(), parts[1].strip()
        if rel.startswith("*"):
            rel = rel[1:]
        if len(expected_sha) != 64 or any(c not in "0123456789abcdef" for c in expected_sha):
            raise ManifestVerificationError(f"MANIFEST_BAD_SHA:{lineno}: {expected_sha!r}")
        target = (pack_root / rel).resolve()
        try:
            target.relative_to(root_resolved)
        except ValueError as exc:
            raise ManifestVerificationError(f"MANIFEST_PATH_TRAVERSAL:{lineno}: {rel!r}") from exc
        if not target.is_file():
            raise ManifestVerificationError(f"MANIFEST_FILE_MISSING:{lineno}: {rel}")
        actual_sha = sha256_file(target)
        if actual_sha != expected_sha:
            raise ManifestVerificationError(
                f"MANIFEST_SHA_MISMATCH:{lineno}: {rel} expected={expected_sha} actual={actual_sha}"
            )
        verified += 1

    return {
        "manifest_path": mpath.name,
        "manifest_sha256": sha256_file(mpath),
        "files_verified": verified,
        "status": "OK",
    }


# --------------------------------------------------------------------------- Hardware & Environment
def _run_cmd_quiet(cmd: list[str], cwd: Path | None = None) -> str | None:
    try:
        out = subprocess.check_output(cmd, cwd=str(cwd) if cwd else None, stderr=subprocess.DEVNULL, text=True, timeout=5)
        return out.strip() or None
    except Exception:
        return None


def collect_hardware_provenance(repo_root: Path | None = None) -> dict[str, Any]:
    """Record GPU/VRAM, CPU, RAM, CUDA/cuDNN/driver, Python/packages, git commit, and UTC timestamp."""
    gpu_name = None
    vram_mb = None
    driver_version = None
    if shutil.which("nvidia-smi"):
        smi = _run_cmd_quiet(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"]
        )
        if smi:
            first = [x.strip() for x in smi.splitlines()[0].split(",")]
            if len(first) >= 3:
                gpu_name, vram_mb, driver_version = first[0], first[1], first[2]

    cuda_version = None
    cudnn_version = None
    packages: dict[str, str] = {}
    for pkg in ("torch", "transformers", "accelerate", "PIL", "numpy", "matplotlib"):
        try:
            mod = __import__(pkg)
            packages[pkg] = str(getattr(mod, "__version__", "installed"))
            if pkg == "torch":
                cuda_version = getattr(getattr(mod, "version", None), "cuda", None)
                try:
                    cudnn_version = str(mod.backends.cudnn.version()) if mod.backends.cudnn.is_available() else None
                except Exception:
                    cudnn_version = None
        except Exception:
            packages[pkg] = "NOT_INSTALLED"

    ram_gb = None
    try:
        if hasattr(os, "sysconf") and "SC_PAGE_SIZE" in os.sysconf_names and "SC_PHYS_PAGES" in os.sysconf_names:
            ram_gb = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024**3), 2)
    except Exception:
        ram_gb = None

    git_commit = _run_cmd_quiet(["git", "rev-parse", "HEAD"], cwd=repo_root) or "UNKNOWN"

    return {
        "recorded_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": platform.platform(),
        "os": platform.system(),
        "cpu_model": platform.processor() or platform.machine() or "UNKNOWN",
        "cpu_count": os.cpu_count(),
        "ram_gb": ram_gb,
        "gpu_name": gpu_name or "NONE",
        "gpu_vram_mb": vram_mb or "NONE",
        "gpu_driver_version": driver_version or "NONE",
        "cuda_version": cuda_version or "NONE",
        "cudnn_version": cudnn_version or "NONE",
        "python_version": sys.version.split()[0],
        "packages": packages,
        "git_commit": git_commit,
        "identity_status": "UNCONFIRMED",
    }


# --------------------------------------------------------------------------- Request / Response Types
@dataclass(frozen=True)
class DeciderRequest:
    """Inference-only AO decision request (NEVER contains GT, expected, or answer table fields)."""

    request_id: str
    case_id: str
    dataset_group: str  # "e3_16_segments" | "e6_12_segments"
    tick: int
    variable_text: str
    candidates: tuple[dict[str, Any], ...]
    camera_ids: tuple[str, ...]
    image_paths: dict[str, str] = field(default_factory=dict)
    input_mode: str = "image_text"


@dataclass(frozen=True)
class DeciderSpec:
    party_id: str
    label: str
    category: str  # "local_option" | "local_vlm" | "local_diffusion"
    hf_repo_id: str
    hf_revision: str
    weights_sha256: str = "RECORD_AT_RUNTIME"
    requires_custom_code: bool = False
    custom_code_audited: bool = False
    audited_commit: str | None = None
    audit_checklist: tuple[str, ...] = ()
    supported_modes: tuple[str, ...] = ("image_text", "text_only")


def parse_ao_json_response(
    raw_text: str,
    camera_ids: tuple[str, ...],
    candidates: tuple[dict[str, Any], ...],
    size: tuple[int, int] = DEFAULT_SIZE,
) -> tuple[dict[str, Any] | None, str | None]:
    """Strict AO JSON parser matching ``AOpenDecider.parse_answer``. Format errors count as fallback; no retries."""
    if not isinstance(raw_text, str):
        return None, "FORMAT_INVALID"
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            text = "\n".join(lines[1:-1]).strip()
    try:
        doc = json.loads(text)
    except (ValueError, TypeError):
        return None, "FORMAT_INVALID"
    if not isinstance(doc, dict):
        return None, "FORMAT_INVALID"
    ans = doc.get("answer")
    if not isinstance(ans, str) or ans not in VALID_ANSWERS:
        return None, "FORMAT_INVALID"

    cams = set(camera_ids)
    cam = doc.get("camera_id")
    det_id = doc.get("detection_id")

    if ans == "SELECT":
        if not any(c.get("camera_id") == cam and c.get("detection_id") == det_id for c in candidates):
            return None, "UNKNOWN_DETECTION"
    elif ans == "OWN_BOX":
        box = doc.get("box_xyxy")
        valid_box = (
            isinstance(box, list)
            and len(box) == 4
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in box)
            and 0 <= box[0] < box[2] <= size[0]
            and 0 <= box[1] < box[3] <= size[1]
            and isinstance(cam, str)
            and cam in cams
        )
        if not valid_box:
            return None, "BAD_OWN_BOX"
    elif ans == "STILL_HERE_OCCLUDED":
        if not isinstance(cam, str) or cam not in cams:
            return None, "BAD_CAMERA"

    rank: list[str] = []
    raw_rank = doc.get("next_camera_ranking")
    if isinstance(raw_rank, list):
        for c in raw_rank:
            if isinstance(c, str) and c in cams and c not in rank:
                rank.append(c)

    return (
        {
            "answer": ans,
            "camera_id": cam if ans in ("SELECT", "OWN_BOX", "STILL_HERE_OCCLUDED") else None,
            "detection_id": det_id if ans == "SELECT" else None,
            "box_xyxy": list(doc["box_xyxy"]) if ans == "OWN_BOX" else None,
            "next_camera_ranking": rank[:3],
            "confidence": doc.get("confidence"),
            "reason_codes": [str(x)[:40] for x in (doc.get("reason_codes") or [])][:4]
            if isinstance(doc.get("reason_codes"), list)
            else [],
            "reason": str(doc.get("reason", ""))[:200],
        },
        None,
    )


# --------------------------------------------------------------------------- Decider Adapters (NO GT)
class BaseDeciderAdapter:
    """Base adapter for E7 local/Colab deciders. Never receives or reads GT / answer tables."""

    def __init__(self, spec: DeciderSpec):
        self.spec = spec

    def validate_custom_code_gate(self) -> None:
        if self.spec.requires_custom_code:
            if not self.spec.custom_code_audited or not self.spec.audited_commit:
                raise CustomCodeAuditError(
                    f"CUSTOM_CODE_NOT_AUDITED: {self.spec.party_id} ({self.spec.hf_repo_id}) "
                    "requires auditing HF custom .py files and pinning audited_commit before loading."
                )

    def predict_raw(self, req: DeciderRequest, *, accelerated: bool) -> str:
        raise NotImplementedError

    def decide(self, req: DeciderRequest, *, accelerated: bool) -> dict[str, Any]:
        """Execute ONE inference attempt (no retries) and return normalized AO result + latency."""
        t0 = time.perf_counter()
        raw_text = self.predict_raw(req, accelerated=accelerated)
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        parsed, err = parse_ao_json_response(raw_text, req.camera_ids, req.candidates)
        return {
            "request_id": req.request_id,
            "case_id": req.case_id,
            "dataset_group": req.dataset_group,
            "tick": req.tick,
            "input_mode": req.input_mode,
            "accelerated": bool(accelerated),
            "latency_ms": latency_ms,
            "retries_attempted": 0,  # Strict no-retry-inflation invariant
            "fallback_reason": err,
            "parsed": parsed,
            "raw_preview": raw_text[:200] if isinstance(raw_text, str) else "",
        }


class LayaTextDecider(BaseDeciderAdapter):
    """Laya text-only option-selection decider (primary option model; HF custom .py audit gate enforced)."""

    DEFAULT_AUDIT_CHECKLIST = (
        "Read modeling_*.py and configuration_*.py at pinned HF revision before trust_remote_code=True",
        "Verify no network exfiltration, shell execution, or host filesystem reads in custom .py",
        "Record exact audited git commit SHA in DeciderSpec.audited_commit",
    )

    def __init__(
        self,
        hf_repo_id: str = "convaiinnovations/laya",
        hf_revision: str = "PIN_AUDITED_COMMIT_BEFORE_RUN",
        *,
        custom_code_audited: bool = False,
        audited_commit: str | None = None,
        inference_fn: Callable[[DeciderRequest, bool], str] | None = None,
    ):
        spec = DeciderSpec(
            party_id="laya_text",
            label="Laya Text-Only (Option Selector)",
            category="local_option",
            hf_repo_id=hf_repo_id,
            hf_revision=hf_revision,
            requires_custom_code=True,
            custom_code_audited=custom_code_audited,
            audited_commit=audited_commit,
            audit_checklist=self.DEFAULT_AUDIT_CHECKLIST,
            supported_modes=("text_only",),
        )
        super().__init__(spec)
        self._inference_fn = inference_fn

    def predict_raw(self, req: DeciderRequest, *, accelerated: bool) -> str:
        self.validate_custom_code_gate()
        if self._inference_fn is not None:
            return self._inference_fn(req, accelerated)
        raise RuntimeError(
            "LayaTextDecider requires a loaded HF model backend in Colab (or injected inference_fn in tests)."
        )


class QwenVLDecider(BaseDeciderAdapter):
    """Small Qwen-VL (2-8B) autoregressive VLM adapter (image+text primary, text-only ablation)."""

    def __init__(
        self,
        hf_repo_id: str = "Qwen/Qwen2.5-VL-3B-Instruct",
        hf_revision: str = "PIN_REVISION_BEFORE_RUN",
        *,
        party_id: str = "qwen_vl",
        label: str = "Qwen2.5-VL-3B-Instruct",
        inference_fn: Callable[[DeciderRequest, bool], str] | None = None,
    ):
        spec = DeciderSpec(
            party_id=party_id,
            label=label,
            category="local_vlm",
            hf_repo_id=hf_repo_id,
            hf_revision=hf_revision,
            requires_custom_code=False,
            supported_modes=("image_text", "text_only"),
        )
        super().__init__(spec)
        self._inference_fn = inference_fn

    def predict_raw(self, req: DeciderRequest, *, accelerated: bool) -> str:
        if self._inference_fn is not None:
            return self._inference_fn(req, accelerated)
        raise RuntimeError(
            "QwenVLDecider requires a loaded transformers VLM backend in Colab (or injected inference_fn in tests)."
        )


class DiffusionVLMDecider(BaseDeciderAdapter):
    """Vision-capable Diffusion LM adapter (LLaDA-V / MMaDA / Dream class; image+text + text-only)."""

    def __init__(
        self,
        hf_repo_id: str = "GSAI-ML/LLaDA-V",
        hf_revision: str = "PIN_REVISION_BEFORE_RUN",
        *,
        party_id: str = "diffusion_vlm",
        label: str = "Vision Diffusion LM (LLaDA-V class)",
        custom_code_audited: bool = False,
        audited_commit: str | None = None,
        inference_fn: Callable[[DeciderRequest, bool], str] | None = None,
    ):
        spec = DeciderSpec(
            party_id=party_id,
            label=label,
            category="local_diffusion",
            hf_repo_id=hf_repo_id,
            hf_revision=hf_revision,
            requires_custom_code=True,
            custom_code_audited=custom_code_audited,
            audited_commit=audited_commit,
            audit_checklist=LayaTextDecider.DEFAULT_AUDIT_CHECKLIST,
            supported_modes=("image_text", "text_only"),
        )
        super().__init__(spec)
        self._inference_fn = inference_fn

    def predict_raw(self, req: DeciderRequest, *, accelerated: bool) -> str:
        self.validate_custom_code_gate()
        if self._inference_fn is not None:
            return self._inference_fn(req, accelerated)
        raise RuntimeError(
            "DiffusionVLMDecider requires a loaded HF model backend in Colab (or injected inference_fn in tests)."
        )


class StubDecider(BaseDeciderAdapter):
    """Deterministic local stub decider for unit tests (no GPU, no HF download, no GT)."""

    def __init__(
        self,
        spec: DeciderSpec,
        fn: Callable[[DeciderRequest, bool], str],
    ):
        super().__init__(spec)
        self._fn = fn

    def predict_raw(self, req: DeciderRequest, *, accelerated: bool) -> str:
        return self._fn(req, accelerated)


# --------------------------------------------------------------------------- Acceleration Comparison
def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    k = (len(xs) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 3)


def _summarize_decisions(records: list[dict[str, Any]], accel_label: str) -> dict[str, Any]:
    n = len(records)
    latencies = [float(r["latency_ms"]) for r in records]
    fallbacks = sum(1 for r in records if r["fallback_reason"] is not None)
    ans_dist: dict[str, int] = {}
    for r in records:
        if r["parsed"] is not None:
            a = r["parsed"]["answer"]
            ans_dist[a] = ans_dist.get(a, 0) + 1
    return {
        "acceleration_label": accel_label,
        "sample_size": n,
        "latency_p50_ms": _percentile(latencies, 0.50),
        "latency_p95_ms": _percentile(latencies, 0.95),
        "format_fallback_count": fallbacks,
        "format_fallback_rate": round(fallbacks / n, 4) if n else 0.0,
        "retries_total": sum(int(r.get("retries_attempted", 0)) for r in records),
        "answer_distribution": ans_dist,
        "records": records,
    }


def _decision_key(rec: dict[str, Any]) -> tuple[Any, ...]:
    if rec["parsed"] is None:
        return ("FALLBACK", rec["fallback_reason"])
    p = rec["parsed"]
    return (p["answer"], p.get("camera_id"), p.get("detection_id"))


def filter_requests_by_scope(requests: list[DeciderRequest], dataset_scope: str) -> list[DeciderRequest]:
    """Filter requests to ``e3_16_segments``, ``e6_12_segments``, or ``combined``."""
    if dataset_scope not in SUPPORTED_SCOPES:
        raise ValueError(f"UNSUPPORTED_DATASET_SCOPE: {dataset_scope}")
    if dataset_scope == "combined":
        return list(requests)
    return [r for r in requests if r.dataset_group == dataset_scope]


def run_acceleration_comparison(
    decider: BaseDeciderAdapter,
    requests: list[DeciderRequest],
    *,
    dataset_scope: str = "e3_16_segments",
    input_mode: str = "image_text",
    accelerated_label: str = "cuda_bf16",
    unaccelerated_label: str = "cpu",
    unaccelerated_sample_cap: int | None = 20,
) -> dict[str, Any]:
    """Run BOTH accelerated and unaccelerated passes for one decider and compute agreement/differences."""
    if input_mode not in SUPPORTED_INPUT_MODES:
        raise ValueError(f"UNSUPPORTED_INPUT_MODE: {input_mode}")

    scoped = filter_requests_by_scope(requests, dataset_scope)
    mode_reqs = [dataclasses.replace(r, input_mode=input_mode) for r in scoped]

    acc_records = [decider.decide(r, accelerated=True) for r in mode_reqs]
    unacc_reqs = mode_reqs[:unaccelerated_sample_cap] if (unaccelerated_sample_cap and unaccelerated_sample_cap > 0) else mode_reqs
    unacc_records = [decider.decide(r, accelerated=False) for r in unacc_reqs]

    acc_by_id = {r["request_id"]: r for r in acc_records}
    compared = 0
    agreed = 0
    differences: list[dict[str, Any]] = []
    for ur in unacc_records:
        ar = acc_by_id.get(ur["request_id"])
        if ar is None:
            continue
        compared += 1
        ak, uk = _decision_key(ar), _decision_key(ur)
        if ak == uk:
            agreed += 1
        else:
            differences.append(
                {
                    "request_id": ur["request_id"],
                    "case_id": ur["case_id"],
                    "tick": ur["tick"],
                    "accelerated_decision": list(ak),
                    "unaccelerated_decision": list(uk),
                }
            )

    agreement_rate = round(agreed / compared, 4) if compared else None
    return {
        "schema_version": SCHEMA_VERSION,
        "party_id": decider.spec.party_id,
        "label": decider.spec.label,
        "category": decider.spec.category,
        "hf_repo_id": decider.spec.hf_repo_id,
        "hf_revision": decider.spec.hf_revision,
        "weights_sha256": decider.spec.weights_sha256,
        "dataset_scope": dataset_scope,
        "input_mode": input_mode,
        "unaccelerated_sample_cap": unaccelerated_sample_cap,
        "accelerated": _summarize_decisions(acc_records, accelerated_label),
        "unaccelerated": _summarize_decisions(unacc_records, unaccelerated_label),
        "compared_decision_points": compared,
        "decision_agreement_vs_unaccelerated": agreement_rate,
        "differences": differences,
        "notes": (
            f"Unaccelerated ran on first {len(unacc_reqs)}/{len(mode_reqs)} decision points "
            f"(cap={unaccelerated_sample_cap}); agreement={agreement_rate}."
        ),
    }
