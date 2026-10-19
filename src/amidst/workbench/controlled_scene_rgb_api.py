"""Real run RGB access only; inference consumers never fall back to fixture data."""

from __future__ import annotations

import copy
import hashlib
import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from amidst.engineering.registry import content_hash
from amidst.workbench.blender_scene import strip_png_text
from amidst.workbench.controlled_scene_api import ACTIONS, ControlledSceneAPI, finite_number
from amidst.workbench.controlled_scene_data import (
    RequiredInputUnavailable,
    RunRegistration,
    SafeRun,
    load_safe_run,
    no_private,
)
from amidst.workbench.scene_errors import DataIntegrityError

MEDIA_PATH = "/api/controlled_rgb"
TOKEN_TTL_S = 120
MAX_MEDIA_GRANTS = 2048


class RGBMediaError(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status


@dataclass(frozen=True)
class MediaGrant:
    session_ref: str
    registration: RunRegistration
    camera_id: str
    frame_index: int
    file_sha256: str
    served_sha256: str
    expires_at: float


def public_png(raw: bytes) -> bytes:
    try:
        return strip_png_text(raw)
    except ValueError as error:
        raise DataIntegrityError("RGB_PNG_INVALID") from error


class ControlledRGBAPI(ControlledSceneAPI):
    """Separately configured real-only surface, with an explicit playback loader scope."""

    def __init__(self, runs: tuple[RunRegistration, ...], *,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.fixture_mode = False
        self._runs = {r.run_id: r for r in runs}
        if len(self._runs) != len(runs) or not runs:
            raise ValueError("INVALID_RGB_REGISTRATIONS")
        self._clock = clock
        self._media_grants: dict[str, MediaGrant] = {}
        self._integrity_failures: dict[str, str] = {}

    @property
    def scene_ids(self) -> frozenset[str]:
        return frozenset(r.scene_id for r in self._runs.values())

    def _load(self, reg: RunRegistration) -> SafeRun:
        if reg.run_id in self._integrity_failures:
            raise DataIntegrityError(self._integrity_failures[reg.run_id])
        try:
            return load_safe_run(reg, purpose="RGB_PLAYBACK")
        except DataIntegrityError as error:
            self._integrity_failures[reg.run_id] = str(error)
            raise

    def _rgb(self, run: SafeRun, camera: str, index: int) -> tuple[bytes, str] | None:
        try:
            raw = run.read_rgb(camera, index)
            if raw is None:
                return None
            served = public_png(raw)
            return served, hashlib.sha256(served).hexdigest()
        except DataIntegrityError as error:
            self._integrity_failures[run.registration.run_id] = str(error)
            raise

    def bootstrap(self) -> dict[str, Any]:
        scenes: dict[str, dict[str, Any]] = {}
        for reg in self._runs.values():
            run = self._load(reg)
            scene = scenes.setdefault(reg.scene_id, {
                "scene_id": reg.scene_id, "run_ids": [], "runs": [], "camera_ids": []})
            scene["run_ids"].append(reg.run_id)
            scene["camera_ids"] = sorted(set(scene["camera_ids"]) | run.camera_ids)
            profile = run.files["runtime_profile"]
            scene["runs"].append({
                "run_id": reg.run_id, "clock_id": run.manifest["clock_id"],
                "scene_version": run.manifest["scene_version"],
                "data_origin": "ACTUAL_BLENDER", "source_sha256": reg.source_sha256,
                "manifest_sha256": reg.manifest_sha256, "camera_ids": sorted(run.camera_ids),
                "sampling": copy.deepcopy(run.manifest["sampling"]),
                "runtime_readiness": profile["runtime_readiness"],
                "unavailable_inputs": copy.deepcopy(profile["unavailable_inputs"]),
                "capabilities": {a: "AVAILABLE" if a == "synced_frames"
                                 else "NOT_MATERIALIZED" for a in sorted(ACTIONS)},
                "input_adapter_receipts": list(run.input_adapter_receipts),
            })
        return {"schema_version": "controlled-scene.bootstrap.v1", "status": "PARTIAL",
                "data_origin": "ACTUAL_BLENDER", "fixture_marker": None,
                "scenes": list(scenes.values()), "real_run_support": "RGB_PLAYBACK_ONLY",
                "requires_session": True, "gt_read": False}

    def call(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action not in ACTIONS:
            raise ValueError("UNKNOWN_CONTROLLED_ACTION")
        no_private(payload)
        base = {"schema_version", "session_ref", "scene_id", "run_id"}
        if (not base.issubset(payload)
                or payload["schema_version"] != (
                    "controlled-scene." + action.replace("_", "-") + "-request.v1")
                or any(not isinstance(payload[k], str) or not payload[k]
                       for k in ("session_ref", "scene_id", "run_id"))):
            raise ValueError("INVALID_CONTROLLED_REQUEST")
        reg = self._runs.get(payload["run_id"])
        if reg is None or payload["scene_id"] != reg.scene_id:
            raise DataIntegrityError("SOURCE_RUN_PIN_MISMATCH")
        if action != "synced_frames":
            raise RequiredInputUnavailable("CONTROLLED_LAYER_NOT_MATERIALIZED")
        if set(payload) != base | {"t_s", "camera_ids"} or not finite_number(payload["t_s"]):
            raise ValueError("INVALID_CONTROLLED_REQUEST")
        run = self._load(reg)
        cameras = payload["camera_ids"]
        if (not isinstance(cameras, list) or not 1 <= len(cameras) <= 8
                or any(not isinstance(c, str) for c in cameras)
                or len(set(cameras)) != len(cameras) or not set(cameras).issubset(run.camera_ids)):
            raise ValueError("INVALID_CAMERA_SCOPE")
        sampling = run.manifest["sampling"]
        micros = Fraction(str(payload["t_s"])) * 1_000_000
        if micros.denominator != 1:
            raise ValueError("TIME_PRECISION_EXCEEDS_MICROSECOND")
        t_us = int(micros)
        fps = Fraction(str(sampling["fps"]))
        duration_us = int(Fraction(str(sampling["duration_s"])) * 1_000_000)
        inside = 0 <= t_us < duration_us
        index = int(Fraction(t_us, 1_000_000) * fps) if inside else None
        timestamp_us = int(Fraction(index * 1_000_000, 1) / fps) if index is not None else None
        tiles, pending = [], []
        for camera in cameras:
            tile: dict[str, Any] = {"camera_id": camera, "frame_ref": None}
            if index is None:
                tile.update(status="OUT_OF_RANGE", reason="TIME_OUTSIDE_RUN")
            else:
                media = self._rgb(run, camera, index)
                if media is None:
                    tile.update(status="MISSING", reason="RGB_RECORD_ABSENT")
                else:
                    record = run.rgb_record(camera, index)
                    assert record is not None
                    _, served_hash = media
                    tile.update(status="READY", frame_index=index,
                                timestamp_s=timestamp_us / 1_000_000,
                                clock_error_s=0.0, file_sha256=record["file_sha256"],
                                served_sha256=served_hash, media_token_ttl_s=TOKEN_TTL_S)
                    pending.append((tile, camera, record["file_sha256"], served_hash))
            tiles.append(tile)
        # Atomic publication: every requested record is verified before ANY token is issued.
        now = self._clock()
        self._media_grants = {k: v for k, v in self._media_grants.items() if v.expires_at > now}
        while len(self._media_grants) + len(pending) > MAX_MEDIA_GRANTS:
            self._media_grants.pop(next(iter(self._media_grants)))
        for tile, camera, file_hash, served_hash in pending:
            token = secrets.token_urlsafe(32)
            assert index is not None
            self._media_grants[token] = MediaGrant(
                payload["session_ref"], reg, camera, index, file_hash, served_hash,
                now + TOKEN_TTL_S)
            tile["frame_ref"] = MEDIA_PATH + "?token=" + token
        result = {
            "schema_version": "controlled-scene.synced-frames.v1", "status": "READY",
            "data_origin": "ACTUAL_BLENDER", "fixture_marker": None,
            "rgb_source_kind": "BLENDER_CAMERA_RENDER",
            "identity_verdict": "UNCONFIRMED", "agent_used": False,
            "resolved_scope": {"scene_id": reg.scene_id,
                               "scene_version": run.manifest["scene_version"],
                               "run_id": reg.run_id, "clock_id": run.manifest["clock_id"],
                               "source_sha256": reg.source_sha256,
                               "sampling_version": sampling["sampling_version"],
                               "length_unit": "m", "data_origin": "ACTUAL_BLENDER"},
            "provenance": {"producer": "controlled-rgb-playback-v1", "gt_read": False,
                           "manifest_sha256": reg.manifest_sha256,
                           "input_adapter_receipts": list(run.input_adapter_receipts)},
            "t_s": t_us / 1_000_000, "t_us": t_us, "clock_id": run.manifest["clock_id"],
            "sampling_version": sampling["sampling_version"],
            "frame_rule": "LATEST_AT_OR_BEFORE_EXPECTED_GRID", "tiles": tiles,
            "expected_frame_index": index,
            "expected_timestamp_s": (timestamp_us / 1_000_000
                                     if timestamp_us is not None else None),
            "expected_timestamp_us": timestamp_us,
            "sample_age_s": ((t_us - timestamp_us) / 1_000_000
                             if timestamp_us is not None else None),
            "media_tokens_issued": len(pending),
        }
        result["output_sha256"] = content_hash(result)
        return result

    def media(self, token: str, authorize: Callable[[str, str], None]) -> tuple[str, bytes]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token) or token not in self._media_grants:
            raise RGBMediaError(403, "MEDIA_TOKEN_INVALID")
        grant = self._media_grants[token]
        if self._clock() >= grant.expires_at:
            raise RGBMediaError(410, "MEDIA_TOKEN_EXPIRED")
        authorize(grant.session_ref, grant.registration.scene_id)
        reg = self._runs.get(grant.registration.run_id)
        if reg != grant.registration:
            raise DataIntegrityError("MEDIA_GRANT_PIN_MISMATCH")
        run = self._load(reg)
        record = run.rgb_record(grant.camera_id, grant.frame_index)
        if record is None or record["file_sha256"] != grant.file_sha256:
            raise DataIntegrityError("MEDIA_GRANT_PIN_MISMATCH")
        media = self._rgb(run, grant.camera_id, grant.frame_index)
        if media is None:
            raise DataIntegrityError("MEDIA_GRANT_PIN_MISMATCH")
        served, served_hash = media
        if served_hash != grant.served_sha256:
            raise DataIntegrityError("SERVED_RGB_HASH_MISMATCH")
        return "image/png", served
