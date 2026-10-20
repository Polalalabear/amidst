"""Pinned JSON/JSONL store for Q1–Q5 (§10); no database or inference side effects."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol


class StoreError(ValueError):
    def __init__(self, message: str, code: str = "DataIntegrityError") -> None:
        self.code = code
        super().__init__(message)


def canonical_hash(value: object, *, exclude: tuple[str, ...] = ()) -> str:
    if isinstance(value, dict):
        value = {k: v for k, v in value.items() if k not in exclude}
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
    ).encode()).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StoreError("Duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise StoreError("Non-finite JSON number")


def _json(raw: bytes) -> dict:
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
        if not isinstance(value, dict):
            raise StoreError("Expected a JSON object")
        # Also catches exponent overflow (1e999 becomes inf in json.loads).
        canonical_hash(value)
        _safe_content(value)
        return value
    except (UnicodeError, ValueError, TypeError) as exc:
        if isinstance(exc, StoreError):
            raise
        raise StoreError("Malformed JSON document") from exc


_FORBIDDEN = {"gt", "private", "private_evaluation", "production", "review_only", "human_review"}
_FORBIDDEN_KEYS = {
    "ground_truth", "actor_id", "material_id", "persons.sim.json", "event_script",
    "production_manifest", "private_evaluation", "mask", "depth", "renderer_trajectory",
}


def _safe_content(value):
    if isinstance(value, dict):
        if _FORBIDDEN_KEYS.intersection(value):
            raise StoreError("Forbidden inference input", "FORBIDDEN_INFERENCE_INPUT")
        for child in value.values():
            _safe_content(child)
    elif isinstance(value, list):
        for child in value:
            _safe_content(child)


def _relative(path: str) -> PurePosixPath:
    if not isinstance(path, str) or not path or "\\" in path or "\0" in path:
        raise StoreError("Invalid store path", "FORBIDDEN_DATA_SCOPE")
    result = PurePosixPath(path)
    if (result.is_absolute() or result.as_posix() != path or ".." in result.parts
            or any(p.lower() in _FORBIDDEN for p in result.parts)
            or result.suffix not in {".json", ".jsonl"}
            or result.name == "persons.sim.json"
            or re.fullmatch(r"event_.*\.validation\.json", result.name)):
        raise StoreError("Path outside safe metadata scope", "FORBIDDEN_DATA_SCOPE")
    return result


@dataclass(frozen=True)
class DocumentPin:
    path: str
    file_sha256: str
    schema_version: str
    content_sha256: str | None = None

    def __post_init__(self):
        _relative(self.path)
        if not isinstance(self.file_sha256, str):
            raise StoreError("File SHA-256 pin required")
        for value in (self.file_sha256, self.content_sha256):
            if value is not None and (
                not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            ):
                raise StoreError("Invalid SHA-256 pin")
        if not isinstance(self.schema_version, str) or not self.schema_version:
            raise StoreError("Schema pin required")


@dataclass(frozen=True)
class DetectionSnapshot:
    manifest: dict
    records: tuple[dict, ...]


class QDemoStore(Protocol):
    def load_document(self, ref: str) -> dict: ...
    def load_detection_index(self, ref: str) -> DetectionSnapshot: ...


class JsonRunStore:
    """Only explicit pins are addressable; no scans, writes, fallback or media access.

    File pins come from trusted configuration, not query parameters. Declaration
    approval is preserved in the returned JSON; loading does not grant authority.
    """

    def __init__(self, root: Path, documents: Mapping[str, DocumentPin]) -> None:
        self.root = Path(root).absolute()
        if self.root.resolve() != self.root or not self.root.is_dir():
            raise StoreError("Store root must be an existing canonical directory")
        self._pins = dict(documents)
        self._loaded_index_hashes: dict[str, str] = {}
        if len({p.path for p in self._pins.values()}) != len(self._pins):
            raise StoreError("Multiple pins for the same path")

    def _read(self, pin: DocumentPin) -> bytes:
        parts = _relative(pin.path).parts
        fd = None
        try:
            fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(leaf, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise StoreError("Pinned metadata must be a regular file")
                raw = stream.read()
        except OSError as exc:
            raise StoreError("Pinned file missing, unreadable or symlinked") from exc
        finally:
            if fd is not None:
                os.close(fd)
        if hashlib.sha256(raw).hexdigest() != pin.file_sha256:
            raise StoreError("Pinned file hash mismatch")
        return raw

    def _pin(self, ref: str) -> DocumentPin:
        if not isinstance(ref, str) or ref not in self._pins:
            raise StoreError("Reference not allowlisted", "FORBIDDEN_DATA_SCOPE")
        return self._pins[ref]

    def load_document(self, ref: str) -> dict:
        pin = self._pin(ref)
        if PurePosixPath(pin.path).suffix != ".json":
            raise StoreError("JSON document required")
        doc = _json(self._read(pin))
        if doc.get("schema_version") != pin.schema_version:
            raise StoreError("Schema version mismatch")
        excluded = ["content_sha256", "stats"]
        for key in ("graph_id", "index_id", "parameter_set_id"):
            if key in doc:
                excluded.append(key)
        digest = canonical_hash(doc, exclude=tuple(excluded))
        if "content_sha256" in doc and doc["content_sha256"] != digest:
            raise StoreError("Content hash mismatch")
        if pin.content_sha256 is not None and (
            doc.get("content_sha256") != pin.content_sha256 or digest != pin.content_sha256
        ):
            raise StoreError("Pinned content hash mismatch")
        return doc

    def load_detection_index(self, ref: str) -> DetectionSnapshot:
        manifest = self.load_document(ref)
        if manifest["schema_version"] != "q-demo.detection-index.v1":
            raise StoreError("Detection index manifest required")
        try:
            relative = _relative(manifest["records_ref"])
            parent = PurePosixPath(self._pin(ref).path).parent
            path = (parent / relative).as_posix()
            record_pins = [p for p in self._pins.values() if p.path == path]
            if len(record_pins) != 1:
                raise StoreError("Records not allowlisted", "FORBIDDEN_DATA_SCOPE")
            pin = record_pins[0]
            if pin.schema_version != "q-demo.detection-record.v1":
                raise StoreError("Record schema pin mismatch")
            if pin.file_sha256 != manifest["records_file_sha256"]:
                raise StoreError("Manifest/records pin mismatch")
            raw = self._read(pin)
            lines = raw.splitlines()
            if not lines or any(not line.strip() for line in lines):
                raise StoreError("Records must be nonempty JSONL without blank records")
            records = tuple(_json(line) for line in lines)
            index_key = canonical_hash(manifest, exclude=(
                "index_id", "content_sha256", "records_ref", "records_file_sha256", "stats",
            ))[:16]
            expected_id = f"detidx:{manifest['scene_revision']}:{manifest['run_id']}:{index_key}"
            if manifest["index_id"] != expected_id:
                raise StoreError("Index ID mismatch")
            cameras = {c["camera_id"] for c in manifest["sampling"]["per_camera"]}
            previous = None
            for record in records:
                if record.get("schema_version", pin.schema_version) != pin.schema_version:
                    raise StoreError("Record schema version mismatch")
                camera, frame = record["camera_id"], record["frame_index"]
                if (camera not in cameras or type(frame) is not int or frame < 0
                        or type(record["timestamp_us"]) is not int or record["timestamp_us"] < 0):
                    raise StoreError("Invalid record scope/time")
                key = (camera, frame)
                if previous is not None and key <= previous:
                    raise StoreError("Duplicate or unsorted frame record")
                previous = key
                if record["frame_ref"] != f"frame:{manifest['run_id']}:{camera}:{frame}":
                    raise StoreError("Frame reference mismatch")
                state = record["frame_state"]
                if state not in {"INFERRED", "NOT_SAMPLED", "NOT_INFERRED", "MISSING"}:
                    raise StoreError("Unknown frame state")
                detections = record["detections"]
                if state == "INFERRED":
                    if not isinstance(detections, list):
                        raise StoreError("INFERRED requires a detections array")
                    for ordinal, detection in enumerate(detections):
                        expected = f"obs:{index_key}:{camera}:{frame}:{ordinal}"
                        if detection["observation_id"] != expected:
                            raise StoreError("Observation reference mismatch")
                elif detections is not None:
                    raise StoreError("Uninferred frames cannot carry detections")
                if state == "NOT_INFERRED" and not record.get("state_reason"):
                    raise StoreError("NOT_INFERRED requires a reason")
            # §2.2: one index key cannot silently identify different produced
            # records. Different trusted catalog refs still share this invariant.
            previous_hash = self._loaded_index_hashes.get(manifest["index_id"])
            if previous_hash is not None and previous_hash != manifest["content_sha256"]:
                raise StoreError("Conflicting contents for the same index ID")
            self._loaded_index_hashes[manifest["index_id"]] = manifest["content_sha256"]
            return DetectionSnapshot(manifest, records)
        except (KeyError, TypeError, IndexError) as exc:
            raise StoreError("Malformed detection index") from exc
